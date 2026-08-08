"""Content-addressed artifact cache (Wave 2 / D-3).

Identical bytes must never be OCR'd twice and identical markdown must never be
re-extracted twice. This module is the whole cache: key composition, the
on-disk payload store, and the three memoizing wrappers the webapp worker and
the CLI consumers (``batch.py``, the Wave-2 discovery runner) call.

It is deliberately Flask-free — importing it starts nothing, binds nothing and
needs no application context, so ``python -m discovery`` can use exactly the
same cache the web dashboard fills.

Stages (each cached INDEPENDENTLY)
----------------------------------
``ocr``       raw PDF bytes  -> ``StatementMarkdown`` (pages + model +
              O-3 ``page_integrity``)
``analysis``  statement markdown -> the ``report_to_dict`` payload
``report``    statement markdown -> the rendered HTML artifact

Chaining is by content, not by job: the analysis stage is keyed on the hash of
the markdown it is about to analyze, not on the PDF hash. That is what makes
the stages independent — a document whose OCR is cached but whose ANALYSIS
settings changed re-analyzes WITHOUT re-OCR, and two different PDFs that
happen to OCR to the same markdown share one analysis.

Cache key composition (exact)
-----------------------------
::

    settings_key = SHA256_UPPER(canonical_json(<stage settings dict>))
    cache_key    = SHA256_UPPER(canonical_json({
        "cache_format": CACHE_FORMAT_VERSION,
        "stage":        <stage>,
        "input":        <input sha256, UPPER hex>,
        "settings":     settings_key,
    }))

``canonical_json`` is ``json.dumps(obj, sort_keys=True, separators=(",", ":"))``
so key material is stable across runs and platforms. Every hash is UPPERCASE
hex SHA-256 — the one convention established by ``ocr/inspect.py``
(``content_sha256``) and ``corpus_gate.sha256_upper``.

``input`` per stage:

* ``ocr``      — ``content_sha256(pdf_bytes)``: the raw PDF bytes, nothing else.
* ``analysis`` — ``text_sha256(markdown)``: the UTF-8 bytes of the exact
  markdown that will be analyzed.
* ``report``   — ``text_sha256(markdown)``: same.

``settings`` per stage — every knob that can change that stage's output, and
nothing else (surveyed from ``webapp/worker.py`` and the functions it calls,
``ocr.pipeline.parse_statement`` / ``analysis.pipeline.analyze_markdown`` /
``ocr.render.markdown_to_html``):

``ocr`` (:func:`ocr_settings_key`)
    ``force_ocr``, ``allow_local_ocr``, ``allow_visual_ocr`` — the ladder
    capability flags; they decide WHICH rung produces the text (the worker's
    deterministic preflight passes ``allow_visual_ocr=False``, auto mode
    passes ``allow_local_ocr=True``, the escalation call passes
    ``force_ocr=True``).
    ``dpi``, ``fallback_dpi`` — rasterization and the mis-segmentation retry.
    ``ocr_model``, ``ocr_base_url``, ``ngram_size``, ``window_size`` — the
    visual-OCR service knobs from ``ocr.config.Settings``.
    ``stage_version`` = :data:`OCR_STAGE_VERSION`.

``analysis`` (:func:`analysis_settings_key`)
    ``parse_mode`` (``auto`` | ``deterministic``), ``model``,
    ``escalation_model``, ``withholding_denominator_mode`` — the whole of
    ``analysis.config.Settings`` that reaches the output, plus
    ``stage_version`` = :data:`ANALYSIS_STAGE_VERSION`.

``report`` (:func:`report_settings_key`)
    ``title`` (the rendered document title) and ``stage_version`` =
    :data:`REPORT_STAGE_VERSION`.

Deliberately EXCLUDED from the keys, with reasons:

* ``source_file`` / filename — a LABEL, not a knob. It is re-stamped onto the
  cached ``StatementMarkdown`` on read, so the markdown header always names
  the file actually being processed while a re-upload under a new name still
  skips OCR entirely. (It does reach the analysis stage input by another
  route: it is printed into the markdown header, so a renamed duplicate is a
  different analysis input and re-analyzes. That is correct — parser
  detection reads the markdown as a whole — and it still costs zero OCR.)
* ``max_workers`` — page concurrency; ``ocr/config.py`` documents that it does
  not change output.
* ``timeout``, ``retries``, ``api_key`` — transport and secrets. Secrets must
  never be hashed into a key that is written to disk.
* callbacks (``on_stage``, ``on_page_delta``, ``on_page_replace``,
  ``page_ocr_fn``) and the preflight ``profile`` — the profile is derived from
  the bytes already in the key.

Over-partitioning is safe, under-partitioning is not: when the native rung
wins, the visual-OCR service knobs did not affect the result yet still
partition the key. That costs a cheap offline recompute after an env change
and never returns a stale artifact.

CODE changes are NOT captured by any key. If the OCR ladder or the analysis
pipeline changes its output, bump :data:`OCR_STAGE_VERSION` /
:data:`ANALYSIS_STAGE_VERSION` / :data:`REPORT_STAGE_VERSION` in the same
commit; bumping :data:`CACHE_FORMAT_VERSION` invalidates everything.
D-3b is the first exercise of that rule: O-3 added ``page_integrity`` to
``StatementMarkdown``, so the OCR artifact's shape changed and
:data:`OCR_STAGE_VERSION` went 1 -> 2. Entries written before it lack the
field and are invalidated rather than silently served without flags.

A cached read must be INDISTINGUISHABLE from a fresh one. For the OCR stage
that means the reconstructed document carries the model, the pages and the
O-3 per-page integrity records (truncation flags, signals, finish reason).
The one thing not reconstructed is the ``PageText`` str subclass the visual
rung produces: its model-side completion signals are consumed only inside
``ocr/pipeline.py``, which distils them into ``page_integrity`` BEFORE the
document exists — so no consumer of a ``StatementMarkdown`` can tell.

Persistence
-----------
Under the existing ``WEBAPP_DATA_DIR`` convention (``webapp.storage.
default_data_dir``): payloads are JSON files at
``<data_dir>/artifacts/<stage>/<first2 of key>/<key>.json`` (written to a temp
name and ``os.replace``d, so a reader never sees a half-written artifact), and
the index rows live in the ``artifact_cache`` table of the same SQLite store
(schema v3, forward-only migration per D-1). Large artifacts therefore never
enter the database. A missing or unreadable payload file is treated as a MISS
and its index row is dropped — the cache degrades to "recompute", never to
"wrong answer".

Module-level API for CLI consumers (discovery runner / batch.py)
----------------------------------------------------------------
::

    from webapp.artifact_cache import (
        open_cache, cached_ocr, cached_analysis, cached_report,
    )

    cache = open_cache()                    # WEBAPP_DATA_DIR, or an explicit dir

    ocr = cached_ocr(
        pdf_bytes,
        compute=lambda: parse_statement(pdf_bytes, source_file=name,
                                        allow_local_ocr=True,
                                        allow_visual_ocr=False),
        cache=cache, source_file=name,
        force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False,
    )
    doc = ocr.value            # StatementMarkdown | None   (None IS cached)
    ocr.cached                 # True -> compute() was never called

    result = cached_analysis(
        doc.to_markdown(),
        compute=lambda: report_to_dict(analyze_markdown(md, parse_mode="auto")),
        cache=cache, parse_mode="auto",
    )

``compute`` is a zero-argument callable invoked ONLY on a miss; passing
``cache=None`` disables caching entirely (compute always runs), which is how a
caller opts out without branching. Exceptions from ``compute`` propagate and
are never cached: a failed extraction is not an artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from ocr.document import StatementMarkdown
from ocr.inspect import content_sha256
from ocr.truncation import PageIntegrity

from .storage import Storage

__all__ = [
    "ArtifactCache",
    "CacheResult",
    "CACHE_FORMAT_VERSION",
    "OCR_STAGE_VERSION",
    "ANALYSIS_STAGE_VERSION",
    "REPORT_STAGE_VERSION",
    "STAGE_OCR",
    "STAGE_ANALYSIS",
    "STAGE_REPORT",
    "analysis_settings_key",
    "cached_analysis",
    "cached_ocr",
    "cached_report",
    "content_sha256",
    "ocr_settings_key",
    "open_cache",
    "report_settings_key",
    "text_sha256",
]

#: Bump to invalidate EVERY cached artifact (payload envelope change).
CACHE_FORMAT_VERSION = 1

#: Bump when the OCR ladder's output changes for unchanged settings.
#: v2 (D-3b): O-3's ``page_integrity`` joined the cached OCR artifact.
OCR_STAGE_VERSION = 2
#: Bump when the analysis pipeline's output changes for unchanged settings.
# 1 -> 2: Track A cell 1 (chase variant completeness, merge of b70496c)
# changed chase extraction output for unchanged settings — cached chase
# analyses from v1 would keep serving pre-fix withheld results forever.
# 2 -> 3: Track A cells 2+3 (TD Canada direction recovery, RBC grid reader
# + balance-chain sign solving; merges of 2dea5ba and 488580f) change
# analysis output for unchanged settings. One composed bump after both
# merges — no pre-TD/RBC artifact can survive into the post-merge
# measurement.
ANALYSIS_STAGE_VERSION = 3
#: Bump when the HTML renderer's output changes for unchanged settings.
REPORT_STAGE_VERSION = 1

STAGE_OCR = "ocr"
STAGE_ANALYSIS = "analysis"
STAGE_REPORT = "report"

T = TypeVar("T")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def text_sha256(text: str) -> str:
    """UPPERCASE hex SHA-256 of a string's UTF-8 bytes — the same convention
    as ``content_sha256`` for raw bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _fingerprint(settings: dict[str, Any]) -> str:
    return text_sha256(_canonical_json(settings))


def cache_key(stage: str, input_sha256: str, settings_key: str) -> str:
    """The composed key. See the module docstring for the exact fields."""
    return text_sha256(
        _canonical_json(
            {
                "cache_format": CACHE_FORMAT_VERSION,
                "stage": stage,
                "input": input_sha256,
                "settings": settings_key,
            }
        )
    )


# ----------------------------------------------------------------------
# settings fingerprints — one function per stage, each enumerating exactly
# the knobs that can change that stage's output
# ----------------------------------------------------------------------


def ocr_settings_key(
    *,
    force_ocr: bool = False,
    allow_local_ocr: bool = False,
    allow_visual_ocr: bool = True,
    dpi: int = 300,
    fallback_dpi: int | None = 250,
    ocr_settings: Any | None = None,
) -> str:
    """Fingerprint of every knob that changes OCR output.

    ``ocr_settings`` is an ``ocr.config.Settings`` (or anything with the same
    attributes); when omitted it is loaded from the environment, so callers
    that never touch the OCR service still partition correctly if
    ``OCR_MODEL`` changes under them."""
    if ocr_settings is None:
        from ocr.config import load_settings as _load_ocr_settings

        ocr_settings = _load_ocr_settings()
    return _fingerprint(
        {
            "stage_version": OCR_STAGE_VERSION,
            "force_ocr": bool(force_ocr),
            "allow_local_ocr": bool(allow_local_ocr),
            "allow_visual_ocr": bool(allow_visual_ocr),
            "dpi": int(dpi),
            "fallback_dpi": None if fallback_dpi is None else int(fallback_dpi),
            "ocr_model": str(getattr(ocr_settings, "model", "")),
            "ocr_base_url": str(getattr(ocr_settings, "base_url", "")),
            "ngram_size": int(getattr(ocr_settings, "ngram_size", 0)),
            "window_size": int(getattr(ocr_settings, "window_size", 0)),
        }
    )


def analysis_settings_key(
    *, parse_mode: str = "auto", analysis_settings: Any | None = None
) -> str:
    """Fingerprint of every knob that changes extraction/analysis output."""
    if analysis_settings is None:
        from analysis.config import load_settings as _load_analysis_settings

        analysis_settings = _load_analysis_settings()
    return _fingerprint(
        {
            "stage_version": ANALYSIS_STAGE_VERSION,
            "parse_mode": str(parse_mode),
            "model": str(getattr(analysis_settings, "model", "")),
            "escalation_model": str(getattr(analysis_settings, "escalation_model", "")),
            "withholding_denominator_mode": str(
                getattr(analysis_settings, "withholding_denominator_mode", "")
            ),
        }
    )


def report_settings_key(*, title: str = "") -> str:
    """Fingerprint of every knob that changes the rendered report artifact."""
    return _fingerprint({"stage_version": REPORT_STAGE_VERSION, "title": str(title)})


@dataclass(frozen=True)
class CacheResult:
    """What a memoizing wrapper returns.

    ``cached`` is the whole proof surface: ``True`` means ``compute`` was never
    called, i.e. zero OCR / zero LLM work for this stage."""

    value: Any
    cached: bool
    stage: str
    cache_key: str | None


class ArtifactCache:
    """Read/write access to the content-addressed artifact store.

    One instance per data directory. Safe to construct repeatedly (it owns no
    connection; ``Storage`` opens one per call), and safe to share between the
    request threads and the single worker thread under the same single-writer
    discipline documented in ``webapp/storage.py``.
    """

    def __init__(
        self, storage: Storage | None = None, data_dir: str | Path | None = None
    ) -> None:
        if storage is None:
            storage = Storage(data_dir)
        elif data_dir is not None:
            raise ValueError("pass either a Storage or a data_dir, not both")
        self.storage = storage
        self.root = storage.artifact_root()

    # -- payload files -------------------------------------------------

    def _artifact_path(self, stage: str, key: str) -> Path:
        # Two-character shard: a flat directory of millions of discovery
        # artifacts is hostile to every filesystem tool.
        return self.root / stage / key[:2] / f"{key}.json"

    def _write_payload(self, path: Path, payload: dict) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = _canonical_json(payload).encode("utf-8")
        tmp = path.with_suffix(".json.tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, path)
        return len(blob)

    # -- generic get/put -----------------------------------------------

    def get(self, stage: str, input_sha256: str, settings_key: str) -> dict | None:
        """The cached payload envelope, or None on a miss.

        A row whose payload file is missing or unreadable is a MISS and the
        row is dropped, so a half-deleted data directory self-heals."""
        key = cache_key(stage, input_sha256, settings_key)
        row = self.storage.cache_lookup(stage, key)
        if row is None:
            return None
        path = self.root / row["artifact_path"]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.storage.cache_forget(stage, key)
            return None
        if not isinstance(payload, dict) or payload.get("cache_format") != CACHE_FORMAT_VERSION:
            self.storage.cache_forget(stage, key)
            return None
        self.storage.cache_record_hit(stage, key)
        return payload

    def put(
        self, stage: str, input_sha256: str, settings_key: str, artifact: dict
    ) -> str:
        """Write an artifact and index it. Returns the cache key."""
        key = cache_key(stage, input_sha256, settings_key)
        path = self._artifact_path(stage, key)
        payload = {
            "cache_format": CACHE_FORMAT_VERSION,
            "stage": stage,
            "input_sha256": input_sha256,
            "settings_key": settings_key,
            "artifact": artifact,
        }
        byte_size = self._write_payload(path, payload)
        self.storage.cache_record(
            stage,
            key,
            input_sha256=input_sha256,
            settings_key=settings_key,
            artifact_path=str(path.relative_to(self.root)),
            byte_size=byte_size,
            format_version=CACHE_FORMAT_VERSION,
        )
        return key

    # -- stage-typed helpers -------------------------------------------

    def get_ocr(self, content_hash: str, settings_key: str) -> tuple[bool, dict | None]:
        """``(hit, document_dict_or_None)``. The second element is ``None``
        both on a miss and on a cached NEGATIVE result, so the hit flag is the
        one that decides whether to call the ladder."""
        payload = self.get(STAGE_OCR, content_hash, settings_key)
        if payload is None:
            return False, None
        return True, payload["artifact"].get("document")

    def put_ocr(
        self, content_hash: str, settings_key: str, document: StatementMarkdown | None
    ) -> str:
        """Store an OCR result. Everything a consumer of ``StatementMarkdown``
        can observe is stored: model, pages, and O-3's per-page integrity
        records — a cached read is not allowed to be a read with the
        truncation flags quietly missing. ``pages`` is normalized to plain
        ``str`` because the visual rung's ``PageText`` carries only the
        model-side signals already distilled into ``page_integrity``.

        ``page_integrity`` is read through ``getattr`` — the same tolerance
        O-3 built into its own readers — so a document-shaped object that
        predates the field (a hand-built extractor result, a test double)
        stores as "not assessed" instead of raising."""
        return self.put(
            STAGE_OCR,
            content_hash,
            settings_key,
            {
                "document": None
                if document is None
                else {
                    "model": document.model,
                    "pages": [str(page) for page in document.pages],
                    "page_integrity": [
                        item.to_dict()
                        for item in (getattr(document, "page_integrity", None) or [])
                    ],
                }
            },
        )

    def get_analysis(self, markdown_hash: str, settings_key: str) -> dict | None:
        payload = self.get(STAGE_ANALYSIS, markdown_hash, settings_key)
        return None if payload is None else payload["artifact"]["analysis"]

    def put_analysis(self, markdown_hash: str, settings_key: str, analysis: dict) -> str:
        return self.put(STAGE_ANALYSIS, markdown_hash, settings_key, {"analysis": analysis})

    def get_report(self, markdown_hash: str, settings_key: str) -> str | None:
        payload = self.get(STAGE_REPORT, markdown_hash, settings_key)
        return None if payload is None else payload["artifact"]["html"]

    def put_report(self, markdown_hash: str, settings_key: str, html: str) -> str:
        return self.put(STAGE_REPORT, markdown_hash, settings_key, {"html": html})

    # -- reporting -----------------------------------------------------

    def stats(self) -> dict[str, dict[str, int]]:
        """Per-stage ``{entries, bytes, hits}`` — the discovery runner's
        cache-effectiveness report in one call."""
        return self.storage.cache_stats()


def open_cache(data_dir: str | Path | None = None) -> ArtifactCache:
    """Open (creating if needed) the artifact cache for a data directory.

    ``data_dir=None`` uses the ``WEBAPP_DATA_DIR`` convention, so a CLI run and
    the dashboard share one cache by default. This is the entry point CLI
    consumers should call."""
    return ArtifactCache(Storage(data_dir))


# ----------------------------------------------------------------------
# memoizing wrappers — the API the worker and the CLI both call
# ----------------------------------------------------------------------


def _page_integrity(entries: object) -> list[PageIntegrity]:
    """Rebuild O-3 ``PageIntegrity`` records from a cached OCR artifact.

    Read defensively (missing keys default to the dataclass's own "no
    evidence" values) so a payload written by an older shape degrades to an
    unflagged record rather than raising — though the OCR stage version is
    what actually keeps such payloads from being served at all."""
    rebuilt: list[PageIntegrity] = []
    for index, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        rebuilt.append(
            PageIntegrity(
                page_index=int(entry.get("page_index", index)),
                truncated=bool(entry.get("truncated", False)),
                signals=list(entry.get("signals") or []),
                finish_reason=entry.get("finish_reason"),
            )
        )
    return rebuilt


def cached_ocr(
    pdf_bytes: bytes,
    *,
    compute: Callable[[], StatementMarkdown | None],
    cache: ArtifactCache | None = None,
    source_file: str = "",
    content_hash: str | None = None,
    force_ocr: bool = False,
    allow_local_ocr: bool = False,
    allow_visual_ocr: bool = True,
    dpi: int = 300,
    fallback_dpi: int | None = 250,
    ocr_settings: Any | None = None,
) -> CacheResult:
    """Memoize one intake-ladder run over ``pdf_bytes``.

    The capability flags must mirror the ``ocr.pipeline.parse_statement`` call
    that ``compute`` performs — they are the cache key, so a mismatch would
    serve one rung's output for another's.

    A NEGATIVE outcome (the deterministic preflight returning ``None``) is
    cached too: it is a deterministic function of the same bytes and settings,
    and not caching it would leave the local-Tesseract rung re-running on every
    re-upload of a scan.

    ``content_hash`` may be supplied when the caller already computed it (the
    webapp has it from the O-1 preflight profile) to avoid re-hashing.
    """
    if cache is None:
        return CacheResult(compute(), False, STAGE_OCR, None)
    input_sha = content_hash or content_sha256(pdf_bytes)
    settings_key = ocr_settings_key(
        force_ocr=force_ocr,
        allow_local_ocr=allow_local_ocr,
        allow_visual_ocr=allow_visual_ocr,
        dpi=dpi,
        fallback_dpi=fallback_dpi,
        ocr_settings=ocr_settings,
    )
    key = cache_key(STAGE_OCR, input_sha, settings_key)
    hit, document = cache.get_ocr(input_sha, settings_key)
    if hit:
        value = (
            None
            if document is None
            # source_file is re-stamped, never keyed: the markdown header must
            # name the file being processed now, not the one that filled the
            # cache.
            else StatementMarkdown(
                source_file=source_file,
                model=document.get("model", ""),
                pages=list(document.get("pages") or []),
                page_integrity=_page_integrity(document.get("page_integrity")),
            )
        )
        return CacheResult(value, True, STAGE_OCR, key)
    document_out = compute()
    cache.put_ocr(input_sha, settings_key, document_out)
    return CacheResult(document_out, False, STAGE_OCR, key)


def cached_analysis(
    markdown: str,
    *,
    compute: Callable[[], dict],
    cache: ArtifactCache | None = None,
    parse_mode: str = "auto",
    analysis_settings: Any | None = None,
) -> CacheResult:
    """Memoize extraction+analysis over the EXACT markdown being analyzed.

    Only successful results are cached — ``compute`` raising propagates
    untouched, because an extraction failure (a transient model error as much
    as a genuine no-parser-matched) is not an artifact worth pinning.
    """
    if cache is None:
        return CacheResult(compute(), False, STAGE_ANALYSIS, None)
    input_sha = text_sha256(markdown)
    settings_key = analysis_settings_key(
        parse_mode=parse_mode, analysis_settings=analysis_settings
    )
    key = cache_key(STAGE_ANALYSIS, input_sha, settings_key)
    hit = cache.get_analysis(input_sha, settings_key)
    if hit is not None:
        return CacheResult(hit, True, STAGE_ANALYSIS, key)
    analysis = compute()
    if isinstance(analysis, dict):
        cache.put_analysis(input_sha, settings_key, analysis)
    return CacheResult(analysis, False, STAGE_ANALYSIS, key)


def cached_report(
    markdown: str,
    *,
    compute: Callable[[], str],
    cache: ArtifactCache | None = None,
    title: str = "",
) -> CacheResult:
    """Memoize the rendered HTML report artifact for a markdown document."""
    if cache is None:
        return CacheResult(compute(), False, STAGE_REPORT, None)
    input_sha = text_sha256(markdown)
    settings_key = report_settings_key(title=title)
    key = cache_key(STAGE_REPORT, input_sha, settings_key)
    hit = cache.get_report(input_sha, settings_key)
    if hit is not None:
        return CacheResult(hit, True, STAGE_REPORT, key)
    html = compute()
    if isinstance(html, str):
        cache.put_report(input_sha, settings_key, html)
    return CacheResult(html, False, STAGE_REPORT, key)
