"""Content-addressed artifact cache.

Identical bytes are never OCR'd twice and identical markdown is never analyzed
twice. This module is the whole cache: key composition, the on-disk payload
store, and the three memoizing wrappers the webapp worker and the CLI
consumers (``batch.py``, the discovery runner) call.

It is Flask-free: importing it starts nothing, binds nothing and needs no
application context, so ``python -m discovery`` uses the same cache the web
dashboard fills.

Stages (each cached independently)
----------------------------------
``ocr``       raw PDF bytes  -> ``StatementMarkdown`` (pages, model,
              ``page_integrity``)
``analysis``  statement markdown -> the ``document_report_to_dict`` payload
``report``    statement markdown -> the rendered HTML artifact

Chaining is by content, not by job: the analysis stage is keyed on the hash of
the markdown it analyzes, not on the PDF hash. A document whose OCR is cached
but whose analysis settings changed re-analyzes without re-OCR, and two PDFs
that OCR to the same markdown share one analysis.

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
hex SHA-256, the convention of ``ocr/inspect.py`` (``content_sha256``) and
``corpus_gate.sha256_upper``.

``input`` per stage:

* ``ocr``      : ``content_sha256(pdf_bytes)``, the raw PDF bytes and nothing else.
* ``analysis`` : :func:`analysis_input_sha`, a digest over both inputs the
  analysis reads: ``text_sha256(admissible_text(markdown))`` (the markdown
  without its source-filename comment) and :func:`sheets_sha256`, a digest over
  the intake object's page partition. ``admissible_text`` strips the
  ``<!-- source: … | pages: N | … -->`` header, and ``to_markdown`` is not
  injective over that text: an honest three-sheet document and a forged
  one-sheet document that prints the separators render to the same string and
  have different correct answers on ``missing_declared_statement_page``. A
  sheet count is not enough either (two two-sheet lists can render to one
  string with opposite answers), so the key carries the partition. The header
  is not re-admitted, because it also carries the filename.
* ``report``   : ``text_sha256(markdown)``, the whole markdown with the filename
  comment. The rendered artifact can show provenance, so the filename stays key
  material here.

The sheet evidence lives in the analysis stage's input hash and not in
:func:`analysis_settings_key`: the settings key is a per-run constant, and the
telemetry observer's read-only artifact join (under ``telemetry/``) indexes the
whole artifact table on one value of it. A per-document value there would
blind that join without any visible error.

``settings`` per stage: every knob that can change that stage's output, and
nothing else.

``ocr`` (:func:`ocr_settings_key`)
    ``force_ocr``, ``allow_local_ocr``, ``allow_visual_ocr``: the ladder
    capability flags. The worker passes ``force_ocr=False,
    allow_local_ocr=True, allow_visual_ocr=False``; discovery passes
    ``force_ocr=False, allow_visual_ocr=False`` and its mode's
    ``allow_local_ocr``. :func:`ocr.pipeline.parse_statement` refuses
    ``force_ocr=True`` and ``allow_visual_ocr=True``; those shapes remain
    computable keys only for historical reconstruction
    (``telemetry/run_of_record.py``, ``tools/train/provenance.py``).
    ``dpi``, ``fallback_dpi``: frozen key material, no rung reads them. They
    are hashed with the defaults 300 and 250 so existing keys stay valid.
    ``ocr_model``, ``ocr_base_url``, ``ngram_size``, ``window_size``: frozen
    literals (:data:`FROZEN_OCR_SETTINGS`) unless a caller passes its own
    ``ocr_settings`` for a historical reconstruction; the environment does not
    move them.
    ``stage_version`` = :data:`OCR_STAGE_VERSION`.

    Present only when ``stage_version >= 5``, so reconstructing a v4 key
    reproduces the v4 dict byte for byte (see :func:`ocr_settings_key` and
    ``telemetry/run_of_record.py``):

    ``extractor``: ``"offline"`` or ``"visual"``, derived from the capability
    flags by :func:`_ocr_extractor`. It labels the settings partition; the
    artifact's own ``model`` field records which rung produced it.
    ``"allow_paddle_ocr": False`` stays in the material so existing keys stay
    valid.
    ``postprocess_state`` / ``postprocess_admitted``: the frozen
    ``"quarantined"`` / ``()`` for every extractor label.
    ``raster_version`` = ``ocr.rasterize.RASTER_VERSION``.
    ``extraction_schema_version`` = :data:`EXTRACTION_SCHEMA_VERSION`.
    ``endpoint_class``: from ``ocr_settings`` via ``getattr``, default
    ``"loopback"`` (the :data:`FROZEN_OCR_SETTINGS` value).
    ``tesseract_version``, ``poppler_version``, ``pymupdf_version``: the
    binary and library versions the offline rungs depend on, from
    :func:`ocr_toolchain_versions`. ``"unknown"`` when a version cannot be read,
    which partitions conservatively (a new key, a re-read) instead of reusing
    an artifact a different binary produced.
    ``research_partition``: present only when non-empty, a research run's own
    partition id. Production calls omit it, so the production key is unchanged.

``analysis`` (:func:`analysis_settings_key`)
    ``parse_mode`` (``auto`` | ``deterministic``) and
    ``withholding_denominator_mode``, the part of ``analysis.config.Settings``
    that reaches the output; ``model`` and ``escalation_model`` as the frozen
    literals :data:`FROZEN_ANALYSIS_MODEL` /
    :data:`FROZEN_ANALYSIS_ESCALATION_MODEL`; ``stage_version`` =
    :data:`ANALYSIS_STAGE_VERSION`; ``parser_registry`` =
    ``analysis.parser_registry.registry_fingerprint()``;
    ``reconstruction_mode``; ``generic_structurer`` =
    ``analysis.structurer.structurer_enabled()``; and
    ``hosted_extraction_opt_in`` as the frozen literal
    :data:`FROZEN_HOSTED_EXTRACTION_OPT_IN`.

    The registry fingerprint is a digest over the registration set itself: ids,
    bank labels, bands, ``supersedes`` edges, each marker's id and kind, the
    declared names of ``parse``/``normalize``/``integrity_checks``, and the
    ``formal_statement`` trio. A registration added, removed, rewired or
    re-banded therefore re-keys every analysis without a stage bump. It is in
    the settings key rather than the input hash because the registry is a
    per-run constant.

    ``reconstruction_mode`` (``off | research | production``, environment
    ``RECONSTRUCTION_MODE``) decides whether the generic rung runs on a
    document no parser claimed, which changes that document's payload, so it
    partitions the key as ``parse_mode`` does. ``generic_structurer`` is the
    derived boolean, read through the structurer's own accessor over the same
    settings object.

    The analysis input hash also carries the sha of the evidence a
    geometry-fed analysis consumed (absent for text-only); see
    :func:`analysis_input_sha`.

``report`` (:func:`report_settings_key`)
    ``title`` (the rendered document title) and ``stage_version`` =
    :data:`REPORT_STAGE_VERSION`.

Excluded from the keys, with reasons:

* ``source_file`` / filename: a label, not a knob. It is re-stamped onto the
  cached ``StatementMarkdown`` on read, so the markdown header names the file
  being processed while a re-upload under a new name still skips OCR. The
  analysis stage hashes ``admissible_text(markdown)``, the same filename-free
  text the pipeline analyzes. Keying on the filename would store one copy of
  the same answer per rename.
* ``max_workers``, ``timeout``, ``retries``, ``api_key``: retired visual-rung
  transport settings. Secrets must never be hashed into a key written to disk.
* the ``on_stage`` callback and the preflight ``profile``: the profile is
  derived from the bytes already in the key.

Over-partitioning is safe, under-partitioning is not: the frozen knobs affect
no offline result but still partition the key, so no cached reading is
re-keyed.

Code changes are not captured by any key, with one exception. If the OCR
ladder, the analysis pipeline or the renderer changes its output, bump
:data:`OCR_STAGE_VERSION` / :data:`ANALYSIS_STAGE_VERSION` /
:data:`REPORT_STAGE_VERSION` in the same commit; bumping
:data:`CACHE_FORMAT_VERSION` invalidates everything.

The exception: the parser registry's own shape (the fields
``registry_key_material`` enumerates) is hashed into the analysis settings key,
so registering, removing, re-banding or rewiring a parser invalidates the
analysis stage without a bump. Nothing wider is covered. Two things look like
registry data and are not: ``analysis.count_semantics``'s per-parser-id
``SEMANTICS``/``CountMapping`` table, and every parser's own extraction code.
Changes to either, to the money grammar, to the ADB engine or to the pipeline
need an :data:`ANALYSIS_STAGE_VERSION` bump.

A cached read must be indistinguishable from a fresh one. For the OCR stage
the reconstructed document carries the model, the pages and the per-page
integrity records (truncation flags, signals, finish reason). The ``PageText``
str subclass is not reconstructed: its completion signals are distilled into
``page_integrity`` inside ``ocr/pipeline.py`` before the document exists.

Persistence
-----------
Under the ``WEBAPP_DATA_DIR`` convention (``webapp.storage.default_data_dir``):
payloads are JSON files at ``<data_dir>/artifacts/<stage>/<first2 of key>/<key>.json``
(written to a temporary name and ``os.replace``d, so a reader never sees a
half-written artifact), and the index rows live in the ``artifact_cache`` table
of the same SQLite store. Large artifacts never enter the database. A missing
or unreadable payload file is a miss and its index row is dropped: the cache
degrades to "recompute", never to "wrong answer".

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
        compute=lambda: document_report_to_dict(
            analyze_document(md, parse_mode="auto", sheets=doc.pages)
        ),
        cache=cache, parse_mode="auto", sheets=doc.pages,
    )

``sheets`` is the intake object's page list, and it must be the same list the
``compute`` call analyzes: it is key material, so handing the cache one
partition and the analysis another stores an answer under a key that does not
describe it. A caller with no intake object passes nothing and gets the
fail-closed behaviour end to end.

``compute`` is a zero-argument callable invoked only on a miss; passing
``cache=None`` disables caching (compute always runs), which is how a caller
opts out without branching. Exceptions from ``compute`` propagate and are never
cached: a failed extraction is not an artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from analysis.parser_registry import admissible_text, registry_fingerprint
from evidence.canonical import EvidenceError, from_json, to_json
from ocr.config import ProvenanceTokenError
from ocr.document import StatementMarkdown
from ocr.inspect import content_sha256
from ocr.truncation import PageIntegrity

from .settings import _replace as _replace_retrying
from .storage import Storage

__all__ = [
    "ArtifactCache",
    "CacheResult",
    "CACHE_FINDING_EVIDENCE_DRIFT",
    "cache_finding_of",
    "CACHE_FORMAT_VERSION",
    "OCR_STAGE_VERSION",
    "ANALYSIS_STAGE_VERSION",
    "REPORT_STAGE_VERSION",
    "EXTRACTION_SCHEMA_VERSION",
    "STAGE_OCR",
    "STAGE_ANALYSIS",
    "STAGE_REPORT",
    "analysis_input_sha",
    "analysis_settings_key",
    "cached_analysis",
    "cached_ocr",
    "cached_report",
    "content_sha256",
    "ocr_settings_key",
    "ocr_toolchain_versions",
    "open_cache",
    "report_settings_key",
    "sheets_sha256",
    "text_sha256",
]

#: Bump when the payload envelope changes; invalidates every cached artifact of every stage.
CACHE_FORMAT_VERSION = 1

#: Bump when the OCR ladder's output changes for unchanged settings; invalidates every cached OCR artifact.
OCR_STAGE_VERSION = 5
#: Bump when the analysis output changes for unchanged settings; invalidates every cached analysis (OCR stays
#: cached). Bump it with ``CLASSIFICATION_VERSION`` too: Re-analyze reads this cache, so a classification bump
#: alone would serve the old entry with the old classification stamp.
ANALYSIS_STAGE_VERSION = 39
#: Bump when the rendered HTML changes for unchanged settings; invalidates every cached report.
REPORT_STAGE_VERSION = 3
#: Bump when the fields a cached ``StatementMarkdown`` records change; it is OCR key material, so it invalidates
#: every cached OCR artifact.
EXTRACTION_SCHEMA_VERSION = 3

STAGE_OCR = "ocr"
STAGE_ANALYSIS = "analysis"
STAGE_REPORT = "report"

#: The one member of :class:`CacheResult`'s ``finding`` vocabulary: a cached OCR entry's ``evidence`` /
#: ``page_extractor`` failed the consistency check `cached_ocr` runs on every restore, so the entry was
#: treated as a miss and recomputed.
CACHE_FINDING_EVIDENCE_DRIFT = "cached_evidence_drift"

T = TypeVar("T")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def text_sha256(text: str) -> str:
    """UPPERCASE hex SHA-256 of a string's UTF-8 bytes — the same convention
    as ``content_sha256`` for raw bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _fingerprint(settings: dict[str, Any]) -> str:
    return text_sha256(_canonical_json(settings))


def sheets_sha256(sheets: Sequence[str] | None) -> str | None:
    """A digest over the intake page PARTITION, or ``None`` for no page list.

    ``None`` and ``[]`` are different facts and hash differently: no evidence of
    page structure is not the same as a document with no sheets, and the
    analysis fail-closes on the first while the second is a real (if degenerate)
    partition.

    Per-sheet digests rather than the concatenated text, because the whole point
    is the BOUNDARIES: ``["ab", "c"]`` and ``["a", "bc"]`` must not collide, and
    joining them would make them identical. Sheet text is hashed rather than
    embedded so that key material stays bounded whatever the document's size.

    ORDER IS KEY MATERIAL, deliberately. ``["a", "b"]`` and ``["b", "a"]`` hash
    differently although both render to the same markdown under a caller that
    reordered them, so three sheets have six permutations and six keys for one
    answer. That is over-partitioning, which this module's contract says is the
    safe direction: it costs a recompute and never returns a stale artifact.
    It is also unreachable in production — the markdown is rendered from the
    same ordered list that is hashed here — so the cost is theoretical and the
    conservatism is free.

    THE ACCEPTED TYPE is a re-iterable sequence of ``str``, and everything else
    is refused rather than coerced. Three ways a call site can get this wrong,
    all of them silent without the guards:

    * ``str`` — refused for the same reason ``assess_document_integrity``
      refuses it: ``str`` is itself a ``Sequence[str]``, so ``sheets=markdown``
      type-checks and then iterates one CHARACTER per sheet. There it would
      clear a fraud-relevant flag; here it would partition the cache by
      something meaningless.
    * a one-shot iterable (generator, map, zip, an exhausted iterator) —
      refused because hashing CONSUMES it, and the caller then hands the
      analysis an empty sequence. The analysis fail-closes on that, so the
      answer is conservative, but it is stored under the key of a partition
      that WAS proven: a later caller supplying the same pages properly gets
      served the fail-closed answer. Nothing in the payload looks wrong, which
      is what makes it worth a refusal rather than a note.
    * non-``str`` members — refused with a message that names the offender,
      because the alternative is an ``AttributeError`` from inside
      ``text_sha256`` with no indication of which call site is at fault.

    Only a call site can reach any of these — no document's content can — so
    raising costs nothing at runtime and fails a mis-wiring loudly.
    """
    if sheets is None:
        return None
    if isinstance(sheets, str):
        raise TypeError(
            "sheets must be the intake object's page list, not the document "
            "text: a str is a Sequence[str] of single characters"
        )
    if not isinstance(sheets, Sequence):
        raise TypeError(
            "sheets must be a re-iterable sequence of page strings, not a "
            f"one-shot iterable ({type(sheets).__name__}): hashing it here "
            "would consume it and leave the analysis with no page structure"
        )
    for index, sheet in enumerate(sheets):
        if not isinstance(sheet, str):
            raise TypeError(
                f"sheets[{index}] is {type(sheet).__name__}, not a page string"
            )
    return text_sha256(_canonical_json([text_sha256(sheet) for sheet in sheets]))


def _is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789ABCDEFabcdef" for c in value)


def analysis_input_sha(
    markdown: str, sheets: Sequence[str] | None = None, *, evidence_sha256: str | None = None,
) -> str:
    """The analysis stage's input hash: the admissible text, the page partition,
    and, when the analysis was fed geometry, the sha of the evidence it
    came from.

    The one place this is derived. The telemetry observer (under ``telemetry/``)
    reconstructs the same document out of the OCR artifact and must resolve the
    same key; a second copy of this composition could drift and leave the
    observer silently blind.

    ``evidence_sha256`` is the `evidence_sha256` of the canonical evidence a
    `DocumentGeometry` handed to `analyze_document` was built from (a native
    read's `native_evidence`), or ``None`` for a text-only analysis. A
    geometry-fed analysis therefore hashes differently from a text-only
    analysis of the same markdown: two artifacts with identical page strings
    and different word boxes must not share a key. The material carries an
    ``"evidence"`` field only when a sha is given, so a text-only call hashes
    the two-field composition that the telemetry observer's artifact join
    (which looks historical artifacts up by this function, with no version
    parameter) still resolves. A malformed sha (anything but ``None`` or 64
    hex characters, in particular the empty string, which would mean
    "geometry-fed, no lineage") is refused.
    """
    material: dict[str, Any] = {
        "text": text_sha256(admissible_text(markdown)),
        "sheets": sheets_sha256(sheets),
    }
    if evidence_sha256 is not None:
        if not _is_sha256_hex(evidence_sha256):
            raise ValueError(
                "evidence_sha256 must be None (text-only analysis) or a 64-character "
                "hex digest of the evidence that fed geometry"
            )
        material["evidence"] = evidence_sha256.upper()
    return text_sha256(_canonical_json(material))


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


#: Frozen key material: stored OCR keys contain these values (the retired OCR client's postprocess state).
POSTPROCESS_STATE_DEFAULT = "quarantined"
ADMITTED_POSTPROCESS_DEFAULT: tuple[str, ...] = ()

#: Frozen key material: every stored OCR key, Tesseract readings included, hashes these retired visual-OCR
#: service defaults. They name a model and an endpoint nothing calls; changing them re-keys every cached reading.
@dataclass(frozen=True)
class _FrozenOcrSettings:
    """What `ocr_settings_key` reads when no ``ocr_settings`` is passed: the same five attributes, by
    `getattr`, as a settings object a historical reconstruction passes."""

    model: str = "baidu/Unlimited-OCR"
    base_url: str = "http://localhost:8000/v1"
    ngram_size: int = 35
    window_size: int = 128
    endpoint_class: str = "loopback"


FROZEN_OCR_SETTINGS = _FrozenOcrSettings()

#: Frozen key material: every stored analysis key hashes these values of the removed hosted extractor and its
#: opt-in. They name models nothing calls; changing them re-keys every stored analysis.
FROZEN_ANALYSIS_MODEL = "gemini-3.5-flash-lite"
FROZEN_ANALYSIS_ESCALATION_MODEL = "gemini-3.5-flash"
FROZEN_HOSTED_EXTRACTION_OPT_IN = False

#: A duplicate of ``ocr.rasterize.RASTER_VERSION``, used only when that import fails: ``ocr/rasterize.py``
#: imports ``pdf2image`` and ``PIL`` at module level, and a missing backend must not make every OCR cache lookup
#: raise. ``test_raster_version_fallback_matches_the_source_module`` pins the two equal.
_RASTER_VERSION_FALLBACK = 2

_toolchain_versions_cache: dict[str, str] | None = None

#: The closed shape of a research partition id. Key material when non-empty, and written verbatim into
#: `provenance.json`, so the charset is closed like every provenance token's.
_RESEARCH_PARTITION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def _validate_research_partition(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("research_partition must be a str (empty for production)")
    if value == "":
        return ""
    if _RESEARCH_PARTITION_RE.fullmatch(value) is None:  # fullmatch: `$` would admit a trailing newline
        raise ValueError(
            "research_partition must match [A-Za-z0-9][A-Za-z0-9._-]{0,63} (or be empty for production)"
        )
    return value


def _ocr_extractor(*, force_ocr: bool, allow_local_ocr: bool, allow_visual_ocr: bool) -> str:
    """The extractor label a call names.

    ``"visual"`` for the retired forced-escalation shape (``force_ocr=True`` and
    ``allow_visual_ocr=True``), kept so historical reconstructions compute that
    partition's key; ``"offline"`` for every other shape. ``allow_local_ocr``
    partitions the key on its own, so it does not enter the label.

    The label adds no partitioning power: it is a function of ``force_ocr`` and
    ``allow_visual_ocr``, which are already key material. The truth table is
    pinned by ``test_extractor_is_visual_only_for_the_forced_escalation_shape``."""
    return "visual" if (force_ocr and allow_visual_ocr) else "offline"


def _ocr_postprocess_readout(extractor: str) -> tuple[str, tuple[str, ...]]:
    """``(postprocess_state, postprocess_admitted)`` for the OCR settings key: the frozen values, for every
    extractor label."""
    del extractor  # every label reads the same frozen pins
    return POSTPROCESS_STATE_DEFAULT, ADMITTED_POSTPROCESS_DEFAULT


def ocr_toolchain_versions() -> dict[str, str]:
    """``{"tesseract_version", "poppler_version", "pymupdf_version"}``.

    Never raises; a version that cannot be read is the sentinel
    ``"unknown"``, which partitions the OCR settings key conservatively (a
    fresh key, a re-read) instead of reusing an artifact a different binary
    produced. Shells out to the `tesseract` / `pdftoppm` executables and
    imports PyMuPDF (`fitz`). Computed once per process: it is read on every
    OCR cache lookup."""
    global _toolchain_versions_cache
    if _toolchain_versions_cache is not None:
        return dict(_toolchain_versions_cache)
    versions = {
        "tesseract_version": "unknown",
        "poppler_version": "unknown",
        "pymupdf_version": "unknown",
    }
    import shutil
    import subprocess

    try:
        tesseract = shutil.which("tesseract")
        if tesseract:
            completed = subprocess.run(
                [tesseract, "--version"], capture_output=True, text=True, timeout=10
            )
            first = next(
                (line.strip() for line in (completed.stdout + "\n" + completed.stderr).splitlines()
                 if line.strip()),
                None,
            )
            if first:
                versions["tesseract_version"] = first
    except Exception:  # never raises: an unreadable version is "unknown"
        pass
    try:
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            completed = subprocess.run(
                [pdftoppm, "-v"], capture_output=True, text=True, timeout=10
            )
            first = next(
                (line.strip() for line in (completed.stderr + "\n" + completed.stdout).splitlines()
                 if line.strip()),
                None,
            )
            if first:
                versions["poppler_version"] = first
    except Exception:
        pass
    try:
        import fitz  # PyMuPDF

        versions["pymupdf_version"] = str(
            getattr(fitz, "VersionBind", None) or getattr(fitz, "version", None) or "unknown"
        )
    except Exception:
        pass
    _toolchain_versions_cache = versions
    return dict(versions)


def ocr_settings_key(
    *,
    force_ocr: bool = False,
    allow_local_ocr: bool = False,
    allow_visual_ocr: bool = True,
    dpi: int = 300,
    fallback_dpi: int | None = 250,
    ocr_settings: Any | None = None,
    stage_version: int | None = None,
    research_partition: str = "",
) -> str:
    """Fingerprint of every knob that changes OCR output.

    ``research_partition``: empty for every production call, and then not in
    the material at all. A non-empty id (closed shape, `_RESEARCH_PARTITION_RE`)
    is key material of its own partition, so a research run's artifacts never
    collide with production's, and `telemetry/run_of_record.py` refuses a run
    recorded under one as historical truth.

    ``ocr_settings`` is anything with the attributes ``model``, ``base_url``,
    ``ngram_size``, ``window_size`` and ``endpoint_class``, read by
    ``getattr`` (the historical reconstructions in
    ``telemetry/run_of_record.py`` and ``tools/train/provenance.py`` pass
    one). When omitted, the frozen :data:`FROZEN_OCR_SETTINGS` literals are
    hashed; the environment does not move the key.

    ``stage_version`` defaults to the live :data:`OCR_STAGE_VERSION` (5+: the
    v5 key material below is included). Passing an EXPLICIT older version
    reconstructs the key exactly as that version computed it: passing ``4``
    reproduces the 9-field v4 key byte for byte, with none of the v5 fields.
    That lets ``telemetry/run_of_record.py`` reconstruct a historical run's
    own OCR key instead of today's shape under an old version number.

    ``"allow_paddle_ocr": False`` stays in the v5+ material so existing keys
    stay valid."""
    if ocr_settings is None:
        # Frozen key material: never read from the environment.
        ocr_settings = FROZEN_OCR_SETTINGS
    version = OCR_STAGE_VERSION if stage_version is None else int(stage_version)
    partition = _validate_research_partition(research_partition)
    if partition and version < 5:
        # A pre-v5 key has no partition field; dropping a research partition there would hand a research run a
        # production-shaped key.
        raise ValueError(
            "research_partition requires OCR stage version 5 or later; a pre-v5 key cannot carry one"
        )
    settings: dict[str, Any] = {
        "stage_version": version,
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
    if version >= 5:
        extractor = _ocr_extractor(
            force_ocr=force_ocr, allow_local_ocr=allow_local_ocr, allow_visual_ocr=allow_visual_ocr,
        )
        postprocess_state, postprocess_admitted = _ocr_postprocess_readout(extractor)
        try:
            from ocr.rasterize import RASTER_VERSION as _raster_version
        except ImportError:  # pdf2image/PIL missing: never raise for one integer
            _raster_version = _RASTER_VERSION_FALLBACK

        toolchain = ocr_toolchain_versions()
        settings.update(
            {
                "extractor": extractor,
                # Frozen key material: the retired Paddle rung's partition flag, always False.
                "allow_paddle_ocr": False,
                "postprocess_state": postprocess_state,
                "postprocess_admitted": list(postprocess_admitted),
                "raster_version": int(_raster_version),
                "extraction_schema_version": int(EXTRACTION_SCHEMA_VERSION),
                "endpoint_class": str(getattr(ocr_settings, "endpoint_class", "loopback")),
                "tesseract_version": toolchain["tesseract_version"],
                "poppler_version": toolchain["poppler_version"],
                "pymupdf_version": toolchain["pymupdf_version"],
            }
        )
        if partition:
            # Present only when non-empty, so production keys are unchanged.
            settings["research_partition"] = partition
    return _fingerprint(settings)


def analysis_settings_key(
    *, parse_mode: str = "auto", analysis_settings: Any | None = None
) -> str:
    """Fingerprint of every knob that changes extraction/analysis output.

    Includes the parser registry's fingerprint. The registry is a per-run
    constant, so it belongs here and not in the input hash; the page partition
    is per-document and goes into :func:`analysis_input_sha`, because a
    per-document value here would blind the telemetry join's one-value index.

    ``registry_fingerprint`` is imported, never recomposed: telemetry's
    ``_ArtifactJoin`` reconstructs this key to find a run's payloads. It also
    loads the production registry if the calling process has not (see
    ``analysis.parser_registry._ensure_registry_loaded``).

    ``reconstruction_mode`` is ``Settings.reconstruction_mode`` (``off |
    research | production``), which decides whether the generic rung runs; it
    partitions the key as ``parse_mode`` does. ``generic_structurer`` is
    derived from the same settings object through
    ``structurer_enabled(analysis_settings)``, so the key and the rung cannot
    disagree about what "enabled" means.

    Frozen key material: ``model``, ``escalation_model`` and
    ``hosted_extraction_opt_in`` are literals for every call, including one
    that passes a settings object. They named the removed hosted extractor and
    its opt-in; changing them would re-key every stored analysis.
    ``parse_mode`` stays key material: Auto and Deterministic read alike and
    are cached apart.
    """
    if analysis_settings is None:
        from analysis.config import load_settings as _load_analysis_settings

        analysis_settings = _load_analysis_settings()
    # Function-local, like ``analysis.config``: importing this module must stay
    # cheap, and the structurer package is only needed when a key is derived.
    from analysis.structurer import structurer_enabled
    return _fingerprint(
        {
            "stage_version": ANALYSIS_STAGE_VERSION,
            "parse_mode": str(parse_mode),
            # Frozen key material: never read from ``analysis_settings`` or the environment.
            "model": FROZEN_ANALYSIS_MODEL,
            "escalation_model": FROZEN_ANALYSIS_ESCALATION_MODEL,
            "withholding_denominator_mode": str(
                getattr(analysis_settings, "withholding_denominator_mode", "")
            ),
            "parser_registry": registry_fingerprint(),
            "reconstruction_mode": str(getattr(analysis_settings, "reconstruction_mode", "off")),
            "generic_structurer": bool(structurer_enabled(analysis_settings)),
            # Frozen key material: the removed opt-in was never set by any
            # default environment.
            "hosted_extraction_opt_in": FROZEN_HOSTED_EXTRACTION_OPT_IN,
        }
    )


def report_settings_key(*, title: str = "") -> str:
    """Fingerprint of every knob that changes the rendered report artifact."""
    return _fingerprint({"stage_version": REPORT_STAGE_VERSION, "title": str(title)})


@dataclass(frozen=True)
class CacheResult:
    """What a memoizing wrapper returns.

    ``cached`` is the whole proof surface: ``True`` means ``compute`` was never
    called, so this stage did no work.

    ``finding`` is ``None`` on every ordinary hit, miss or bypass, and
    ``"cached_evidence_drift"`` when :func:`cached_ocr` found a cached entry
    whose ``evidence``/``page_extractor`` failed its consistency check and
    recomputed it. Without it, a repaired corrupt entry would look like an
    ordinary miss once the recompute overwrites it."""

    value: Any
    cached: bool
    stage: str
    cache_key: str | None
    finding: str | None = None


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
        """Write a payload file through a temporary file of its own and rename it into place, so two writers of
        the same entry at once (a CLI pointed at a live server's data directory) cannot fail each other. The rename
        is retried briefly on the Windows refusal while a reader has the target open; the temporary file is always
        removed. The temporary name ends in ``.tmp``, so nothing that lists ``*.json`` payloads sees it."""
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = _canonical_json(payload).encode("utf-8")
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem[:16]}-", suffix=".json.tmp")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(blob)
            _replace_retrying(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
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
        can observe is stored: model, pages, the per-page integrity records,
        ``page_extractor`` and ``evidence``. ``pages`` is normalized to plain
        ``str``: ``PageText``'s signals are already distilled into
        ``page_integrity``.

        ``page_integrity`` / ``page_extractor`` are read through ``getattr``,
        so a document-shaped object without a field (a test double) stores as
        "not assessed" / "not populated" instead of raising. ``evidence``
        serializes via ``evidence.canonical.to_json`` when present, else
        ``None``. ``native_evidence`` serializes the same way, and
        ``native_evidence_sha256`` stores its sha beside it for a restore to
        re-verify.

        ``visual_pair`` / ``visual_pair_sha256`` are written only for a
        document that carries visual-pair evidence; no reader produces one,
        and the shape stays so stored readings keep their format."""
        evidence = getattr(document, "evidence", None) if document is not None else None
        native_evidence = getattr(document, "native_evidence", None) if document is not None else None
        return self.put(
            STAGE_OCR,
            content_hash,
            settings_key,
            {
                "document": None
                if document is None
                else {
                    "model": document.model,
                    **({"visual_pair": document.visual_pair,
                        "visual_pair_sha256": _fingerprint(document.visual_pair)}
                       if getattr(document, "visual_pair", None) is not None else {}),
                    "pages": [str(page) for page in document.pages],
                    "page_integrity": [
                        item.to_dict()
                        for item in (getattr(document, "page_integrity", None) or [])
                    ],
                    "page_extractor": list(getattr(document, "page_extractor", None) or []),
                    "evidence": to_json(evidence) if evidence is not None else None,
                    "native_evidence": to_json(native_evidence) if native_evidence is not None else None,
                    "native_evidence_sha256": (
                        native_evidence.evidence_sha256 if native_evidence is not None else None
                    ),
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
    """Rebuild ``PageIntegrity`` records from a cached OCR artifact.

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


def _restore_native_evidence(document: dict):
    """The record's ``native_evidence`` rebuilt, or ``None`` for a schema-2
    record. Raises ``EvidenceError`` (the drift :func:`cached_ocr` turns into
    a miss with a finding) when the blob does not reproduce the sha the record
    claims in ``native_evidence_sha256``, or when that sha is stored with no
    blob. A blob that reproduces its own hash beside a stale stored sha is
    still a drift."""
    payload = document.get("native_evidence")
    claimed = document.get("native_evidence_sha256")
    if payload is None:
        if claimed:
            raise EvidenceError("native_evidence_sha256 stored without its native_evidence")
        return None
    restored = from_json(payload)
    if not isinstance(claimed, str) or restored.evidence_sha256 != claimed:
        raise EvidenceError("native_evidence does not reproduce the record's native_evidence_sha256")
    return restored


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
    research_partition: str = "",
) -> CacheResult:
    """Memoize one intake-ladder run over ``pdf_bytes``.

    ``research_partition`` is threaded to :func:`ocr_settings_key` unchanged:
    empty for production, a partition id for a research run.

    A hit restores ``native_evidence`` and re-verifies it against the record's
    ``native_evidence_sha256`` (see :func:`_restore_native_evidence`); a
    mismatch is the same miss with a finding as a drifted ``evidence``. A
    schema-2 record (neither key present) restores with
    ``native_evidence=None``.

    The capability flags must mirror the ``ocr.pipeline.parse_statement`` call
    that ``compute`` performs — they are the cache key, so a mismatch would
    serve one rung's output for another's.

    A NEGATIVE outcome (the deterministic preflight returning ``None``) is
    cached too: it is a deterministic function of the same bytes and settings,
    and not caching it would leave the local-Tesseract rung re-running on every
    re-upload of a scan.

    ``content_hash`` may be supplied when the caller already computed it (the
    webapp has it from the preflight profile) to avoid re-hashing.

    A hit also restores ``page_extractor`` and ``evidence``
    (``evidence.canonical.from_json``). A payload whose stored evidence does
    not round-trip (its own hash does not reproduce, or the reconstructed
    ``StatementMarkdown`` refuses the page-count/page-text consistency check)
    is a drifted copy: it is never served. This function falls through to a
    fresh ``compute()`` as on a miss, overwrites the drifted entry, and
    returns ``finding=CACHE_FINDING_EVIDENCE_DRIFT``. Every other path (hit,
    miss, bypass) returns ``finding=None``.

    When a drift was detected and the recompute raises, no
    :class:`CacheResult` exists to carry the finding, so it is attached to the
    exception as the attribute :func:`cache_finding_of` reads back. The
    exception propagates unchanged in type and message. The drifted entry is
    not overwritten on that path, so the next call finds and reports it
    again. An exception with no drift behind it carries no attribute.
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
        research_partition=research_partition,
    )
    key = cache_key(STAGE_OCR, input_sha, settings_key)
    hit, document = cache.get_ocr(input_sha, settings_key)
    drifted = False
    if hit:
        try:
            evidence_payload = document.get("evidence") if document is not None else None
            # A stored reading that carries visual-pair evidence restores only when the evidence reproduces the
            # hash stored beside it.
            if document is not None and document.get("visual_pair") is not None:
                if _fingerprint(document["visual_pair"]) != document.get("visual_pair_sha256"):
                    raise ProvenanceTokenError("visual pair cache evidence hash mismatch")
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
                    page_extractor=list(document.get("page_extractor") or []),
                    evidence=from_json(evidence_payload) if evidence_payload is not None else None,
                    native_evidence=_restore_native_evidence(document),
                    visual_pair=document.get("visual_pair"),
                )
            )
        except (EvidenceError, ProvenanceTokenError, TypeError, KeyError):
            drifted = True  # a drifted cached copy: fall through to a fresh compute() below
        else:
            return CacheResult(value, True, STAGE_OCR, key, finding=None)
    try:
        document_out = compute()
    except Exception as exc:
        if drifted:
            # No CacheResult will exist to carry the finding, so the
            # exception carries it. Every BaseException instance accepts
            # attribute assignment (the C-level struct owns a __dict__), so
            # this cannot itself fail; the type and message are untouched.
            exc.cache_finding = CACHE_FINDING_EVIDENCE_DRIFT
        raise
    cache.put_ocr(input_sha, settings_key, document_out)
    return CacheResult(
        document_out, False, STAGE_OCR, key,
        finding=CACHE_FINDING_EVIDENCE_DRIFT if drifted else None,
    )


def cache_finding_of(exc: BaseException) -> str | None:
    """The cache finding :func:`cached_ocr` attached to ``exc`` before letting
    it propagate out of a failed recompute: ``CACHE_FINDING_EVIDENCE_DRIFT``
    when the entry the recompute was replacing had drifted, else ``None``.
    The one reader of the attribute."""
    finding = getattr(exc, "cache_finding", None)
    return finding if isinstance(finding, str) and finding else None


def cached_analysis(
    markdown: str,
    *,
    compute: Callable[[], dict],
    cache: ArtifactCache | None = None,
    parse_mode: str = "auto",
    analysis_settings: Any | None = None,
    sheets: Sequence[str] | None = None,
    evidence_sha256: str | None = None,
) -> CacheResult:
    """Memoize extraction+analysis over the EXACT markdown being analyzed.

    ``sheets`` is the intake object's page list, which ``analyze_markdown``
    reads as well as the markdown — so it is key material, and it must be the
    same list ``compute`` passes down. Omit it only where the caller genuinely
    has no intake object; the analysis then fail-closes and the key records
    that it did.

    ``evidence_sha256`` is the sha of the evidence behind the
    `DocumentGeometry` ``compute`` hands to ``analyze_document``, or ``None``
    when it hands none. Key material, threaded to :func:`analysis_input_sha`:
    a geometry-fed analysis and a text-only one of the same markdown never
    share an entry. Whoever passes geometry passes the sha.

    Only successful results are cached: ``compute`` raising propagates
    untouched, because a failed extraction is not an artifact.
    """
    if cache is None:
        return CacheResult(compute(), False, STAGE_ANALYSIS, None)
    # Key on what the analysis actually reads, not on the bytes we were handed:
    # `analyze_markdown` strips the source-filename comment at its parse seam,
    # so two uploads of one statement under two filenames share one entry. It
    # also reads the intake page list, which that strip removes from the text,
    # so the partition is carried explicitly.
    input_sha = analysis_input_sha(markdown, sheets, evidence_sha256=evidence_sha256)
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
