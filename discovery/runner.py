"""Per-document discovery processing. Consumes merged platform pieces only.

Resolution is the **production intake ladder** (`ocr.pipeline.parse_statement`)
and nothing else. That is a binding ruling with a scar behind it: H-3's first
corpus anchor used the generic `parse_native_pdf_text` directly and silently
produced different markdown for four banks (Navy Federal, TD Canada, Wells,
Desjardins all have layout-specific readers that come first), which showed up
as five phantom failures. Discovery measures coverage; measuring it through a
different reader than production uses would make every number a fiction.

Offline by construction in every mode this wave runs:

- `parse_mode="deterministic"` — the LLM extraction branch is unreachable, so
  no Gemini call can occur even in principle.
- `allow_visual_ocr=False` — `ocr.pipeline` imports `ocr.ocr_client` lazily
  *inside* the visual rung, so in discovery mode the model client module is
  never even imported. A test asserts exactly that.
- Local Tesseract only in `--scanned` (tranche 2), never in tranche 0/1.

Documents the mode cannot read are RECORDED, never skipped: a scanned document
in an offline tranche is `deferred_scanned`, and a document that would need the
visual rung is `deferred_visual_ocr`.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from corpus_artifacts import cached_markdown
from ocr.inspect import inspect_pdf
from telemetry import (
    DispatchCollector,
    StageTimer,
    build_record,
    dispatch_section,
    document_section,
    model_calls_for,
    score_vector,
    source_section,
)

from .inventory import DedupIndex

MODE_PROFILE_ONLY = "profile-only"
MODE_DIGITAL = "digital"
MODE_SCANNED = "scanned"
MODE_DRY_RUN = "dry-run"

#: Committed OCR artifacts exist for the six image-only PINNED statements only.
#: They are what lets the dry run cover all 109 with zero OCR; no archive
#: document has one, so an archive scan defers instead.
ARTIFACT_CACHE = Path("tests/corpus_cache")


@dataclass
class DocumentRow:
    """One discovery row. Adjudication-grade, not telemetry-grade.

    This carries the relative path and folder label a human needs to act on a
    finding; it is written to a gitignored directory. Account identifiers are
    masked to last-4 and no transaction-level detail appears here at all.
    """

    relative_path: str
    folder_label: str
    content_sha256: str
    byte_size: int
    valid_pdf: bool = False
    encrypted: bool = False
    classification: str = "unknown"
    page_count: int = 0
    likely_account_count: int = 0
    dedup_status: str = "unique"
    duplicate_of: str | None = None
    source_path: str = "none"
    source_model: str | None = None
    truncated_pages: int = 0
    parser_id: str | None = None
    parser_score: float | None = None
    dispatch_outcome: str | None = None
    candidates: list[str] = field(default_factory=list)
    near_miss: list[str] = field(default_factory=list)
    outcome_class: str = "failed"
    outcome_reason: str = "not_processed"
    error_type: str | None = None
    statement_bank: str | None = None
    account_last4: str | None = None
    cache_ocr: str = "bypass"
    cache_analysis: str = "bypass"
    elapsed_ms: float = 0.0

    def as_dict(self) -> dict:
        row = asdict(self)
        row["candidates"] = "; ".join(self.candidates)
        row["near_miss"] = "; ".join(self.near_miss)
        return row


def _mask_last4(value: str | None) -> str | None:
    """Account identifiers appear as last-4 or not at all."""
    if not value:
        return None
    digits = [character for character in str(value) if character.isalnum()]
    return "".join(digits[-4:]) if len(digits) >= 4 else "".join(digits)


def _fmt(pairs) -> list[str]:
    return [f"{identifier}:{score:g}" for identifier, score in pairs]


class DiscoveryRunner:
    """Processes documents one at a time; owns no routing decisions of its own."""

    _last_ocr_cached = False

    def __init__(
        self,
        root: Path,
        *,
        mode: str,
        run_id: str,
        sink=None,
        cache=None,
        dedup: DedupIndex | None = None,
    ) -> None:
        self.root = root
        self.mode = mode
        self.run_id = run_id
        self.sink = sink
        self.cache = cache
        self.dedup = dedup if dedup is not None else DedupIndex.with_pinned_corpus()
        self.allow_local_ocr = mode == MODE_SCANNED
        self.allow_artifacts = mode == MODE_DRY_RUN

    # -- resolution ---------------------------------------------------------

    def _read(self, raw: bytes, source_file: str, profile):
        """(document, markdown, note). Production ladder, offline rungs only.

        Served through D-3's content-addressed cache, so identical bytes under
        identical settings are never re-read across tranches or re-runs. The
        cache is keyed on content + settings, and `allow_visual_ocr=False` is
        part of that key, so a tranche-1 miss cannot be served a tranche-2
        artifact or vice versa.
        """
        from ocr.pipeline import parse_statement

        def compute():
            return parse_statement(
                raw,
                source_file=source_file,
                profile=profile,
                force_ocr=False,
                allow_local_ocr=self.allow_local_ocr,
                allow_visual_ocr=False,   # never: no model client is constructed
            )

        if self.cache is None:
            document, cached = compute(), False
        else:
            from webapp.artifact_cache import cached_ocr

            result = cached_ocr(
                raw,
                compute=compute,
                cache=self.cache,
                source_file=source_file,
                content_hash=profile.content_sha256,
                force_ocr=False,
                allow_local_ocr=self.allow_local_ocr,
                allow_visual_ocr=False,
            )
            document, cached = result.value, result.cached
        self._last_ocr_cached = cached
        if document is not None:
            return document, document.to_markdown(), None
        if self.allow_artifacts:
            markdown = cached_markdown(raw, ARTIFACT_CACHE)
            if markdown is not None:
                return None, markdown, "committed_artifact"
        return None, None, (
            "deferred_scanned" if self.allow_local_ocr else "deferred_offline_rungs"
        )

    # -- one document -------------------------------------------------------

    def process(self, relative_path: str, folder_label: str) -> DocumentRow:
        started = time.perf_counter()
        path = self.root / relative_path
        raw = path.read_bytes()
        timer, collector = StageTimer(), DispatchCollector()

        with timer.time("preflight"):
            profile = inspect_pdf(raw)

        row = DocumentRow(
            relative_path=relative_path,
            folder_label=folder_label,
            content_sha256=profile.content_sha256,
            byte_size=len(raw),
            valid_pdf=profile.valid_pdf,
            encrypted=profile.encrypted,
            classification=profile.classification,
            page_count=profile.page_count,
            likely_account_count=profile.likely_account_count,
        )
        status, first_seen = self.dedup.classify(profile.content_sha256, relative_path)
        row.dedup_status, row.duplicate_of = status, first_seen

        if self.mode == MODE_PROFILE_ONLY:
            row.outcome_reason = "profile_only"
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        if not profile.valid_pdf or profile.encrypted:
            row.outcome_class = "failed"
            row.outcome_reason = "encrypted" if profile.encrypted else "invalid_pdf"
            self._emit(row, profile, None, None, None, collector, timer,
                       error_reason=row.outcome_reason)
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        with timer.time("ocr"):
            document, markdown, note = self._read(raw, Path(relative_path).name, profile)

        if markdown is None:
            # Recorded, never skipped: this document is real work that this
            # tranche deliberately did not do.
            row.outcome_class = "failed"
            row.outcome_reason = (
                "deferred_scanned" if note == "deferred_offline_rungs" else "deferred_visual_ocr"
            )
            row.source_path = "none"
            self._emit(row, profile, None, None, None, collector, timer,
                       error_reason=row.outcome_reason)
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        source = source_section(document)
        row.source_path = "committed_artifact" if note == "committed_artifact" else source["path"]
        row.source_model = source["model"]
        row.truncated_pages = source["truncation"]["truncated_page_count"]

        payload, error_type = None, None
        analysis_cached = False
        with timer.time("analysis"):
            try:
                def analyse():
                    return report_to_dict(analyze_markdown(
                        markdown, parse_mode="deterministic", on_dispatch=collector
                    ))

                if self.cache is None:
                    payload = analyse()
                else:
                    from webapp.artifact_cache import cached_analysis

                    result = cached_analysis(
                        markdown, compute=analyse, cache=self.cache,
                        parse_mode="deterministic",
                    )
                    payload, analysis_cached = result.value, result.cached
            except Exception as exc:
                error_type = type(exc).__name__

        dispatch = collector.dispatch
        if dispatch is not None:
            row.dispatch_outcome = dispatch.outcome
            row.parser_id = dispatch.parser_id
            row.parser_score = (
                dispatch.detection.score if dispatch.detection is not None else None
            )
            row.candidates = _fmt(dispatch.candidates)

        scores, registration_count = score_vector(markdown)
        row.near_miss = _fmt([(i, s) for i, s in scores if s < 0.5][:5])

        if payload is not None:
            statement = payload.get("statement") or {}
            row.statement_bank = statement.get("bank")
            row.account_last4 = _mask_last4(statement.get("account_number"))

        from telemetry.record import classify_outcome

        row.outcome_class, row.outcome_reason = classify_outcome(
            payload,
            error_type=error_type,
            error_reason=_failure_reason(error_type, dispatch),
        )
        row.error_type = error_type

        # Cache disposition comes from CacheResult.cached, the same source
        # H-3 uses, so the CLI reports it identically to the webapp.
        timer.set_cache("ocr", _disposition(self.cache, self._last_ocr_cached))
        timer.set_cache("analysis", _disposition(self.cache, analysis_cached))
        stages = timer.as_dict()
        row.cache_ocr = stages["ocr"]["cache"]
        row.cache_analysis = stages["analysis"]["cache"]

        self._emit(
            row, profile, document, markdown, payload, collector, timer,
            error_type=error_type,
            scores=(scores, registration_count),
            escalated=bool(payload.get("escalated")) if payload else False,
        )
        row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return row

    # -- telemetry ----------------------------------------------------------

    def _emit(
        self, row, profile, document, markdown, payload, collector, timer,
        *, error_type=None, error_reason=None, scores=None, escalated=False,
    ) -> None:
        """One H-3 record per enumerated document. Never raises.

        The record shape is H-3's, unchanged and unextended: discovery is a
        telemetry CONSUMER. Note what does NOT cross into it — the relative
        path, the folder label, the bank label and the masked account live in
        the discovery row only, because the H-3 sensitivity invariant forbids
        them and the discovery report is a different artifact with a different
        audience.
        """
        if self.sink is None:
            return
        try:
            if scores is None:
                scores = score_vector(markdown) if markdown else ([], 0)
            vector, registration_count = scores
            self.sink.write(build_record(
                run_id=self.run_id,
                emitter="discovery",
                document=document_section(
                    profile.content_sha256, row.byte_size, profile,
                    duplicate_of_prior_record=row.dedup_status != "unique",
                ),
                source=source_section(document),
                dispatch=dispatch_section(
                    collector.dispatch, vector, registration_count,
                    source="live" if collector.seen else "unavailable",
                ),
                stages=timer.as_dict(),
                model_calls=model_calls_for(document, payload),
                payload=payload,
                escalated=escalated,
                error_type=error_type,
                error_reason=error_reason,
            ))
        except Exception:
            return None


def _disposition(cache, cached: bool) -> str:
    return "bypass" if cache is None else ("hit" if cached else "miss")


def _failure_reason(error_type: str | None, dispatch) -> str | None:
    if error_type is None:
        return None
    if error_type == "AmbiguousParserError":
        return "parser_ambiguous"
    if dispatch is not None and dispatch.outcome == "unclaimed":
        return "no_parser_matched"
    return "exception"
