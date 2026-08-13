"""Per-document discovery processing. Consumes merged platform pieces only.

Resolution is the **production intake ladder** (`ocr.pipeline.parse_statement`)
and nothing else. That is a binding ruling with a scar behind it: H-3's first
corpus anchor used the generic `parse_native_pdf_text` directly and silently
produced different markdown for four banks (Navy Federal, TD Canada, Wells,
Desjardins all have layout-specific readers that come first), which showed up
as five phantom failures. Discovery measures coverage; measuring it through a
different reader than production uses would make every number a fiction.

Offline by construction in every mode except `--scanned-visual`:

- `parse_mode="deterministic"` — the LLM extraction branch is unreachable, so
  no Gemini call can occur even in principle. TRUE IN EVERY MODE, including
  `--scanned-visual`: the visual rung reads pixels into markdown, it does not
  extract, and no paid vendor is reachable from any discovery mode.
- `allow_visual_ocr=False` — `ocr.pipeline` imports `ocr.ocr_client` lazily
  *inside* the visual rung, so in the offline modes the model client module is
  never even imported. A test asserts exactly that.
- Local Tesseract only in `--scanned` / `--scanned-visual`, never in tranche 0/1.

Documents the mode cannot read are RECORDED, never skipped: a scanned document
in an offline tranche is `deferred_scanned`, and a document that would need the
visual rung is `deferred_visual_ocr`.

The visual rung (W3-5, `--scanned-visual`)
------------------------------------------
`--scanned-visual` is the SAME production ladder with its last rung enabled: it
is `--scanned` plus the local Unlimited-OCR server (our own GPU, `$0` vendor).
Discovery's policy around it stays offline-first, and there are exactly two ways
a document reaches it:

1. **Recovery** — the offline rungs produced nothing at all. In `--scanned`
   that document is `deferred_visual_ocr`; here it gets the visual read.
2. **Upgrade** — the offline read came from local Tesseract and no parser
   claimed the text it produced (discovery class 5: a text-QUALITY failure, not
   a layout-knowledge one). The visual rung reads the same pages again and the
   result is adopted only if it actually claims. A NATIVE-text document that
   goes unclaimed is a layout problem and is never escalated — spending GPU time
   re-reading text we already have perfectly is the one thing this rung must
   not do.

Both paths call `parse_statement(force_ocr=True, allow_visual_ocr=True)`, which
is the same rung the webapp uses, through the same D-3 cache, with the same O-3
truncation assessment. The offline rungs are not re-run (they already ran, and
`force_ocr` is part of the cache key), so the two reads occupy two disjoint
cache partitions of the same bytes.

The deferral taxonomy does not soften: a document the visual rung ALSO cannot
serve stops being `deferred` and becomes an explicit terminal `failed` —
`ocr_failed` when the rung raised (server down mid-run: that document fails
closed, the run continues), `no_parser_matched` when it produced text nobody
claimed. Nothing is lost silently.
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
    source_path_for,
    source_section,
)

from .inventory import DedupIndex

MODE_PROFILE_ONLY = "profile-only"
MODE_DIGITAL = "digital"
MODE_SCANNED = "scanned"
MODE_SCANNED_VISUAL = "scanned-visual"
MODE_DRY_RUN = "dry-run"

#: Modes that run the local Tesseract rung.
LOCAL_OCR_MODES = frozenset({MODE_SCANNED, MODE_SCANNED_VISUAL})

#: What the visual rung did for one document. Row-level vocabulary (the
#: adjudication artifact); it reaches telemetry as `outcome.fallback_reason`
#: prefixed with `visual_ocr_`, which is an enum code like every other.
VISUAL_NOT_ATTEMPTED = "not_attempted"
VISUAL_RECOVERED = "recovered"      # offline rungs served nothing; visual did
VISUAL_UPGRADED = "upgraded"        # unclaimed Tesseract read replaced by a claim
VISUAL_NO_UPGRADE = "no_upgrade"    # escalation ran, did not claim; offline kept
VISUAL_FAILED = "failed"            # the rung raised (endpoint down/transport)

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
    #: "<parser_id>:<stage>:<ExceptionClass>" per registration that raised.
    #: Registry ids and exception class names only — never a message (W3-1).
    parser_exceptions: list[str] = field(default_factory=list)
    outcome_class: str = "failed"
    outcome_reason: str = "not_processed"
    error_type: str | None = None
    statement_bank: str | None = None
    account_last4: str | None = None
    cache_ocr: str = "bypass"
    cache_analysis: str = "bypass"
    cache_visual: str = "bypass"
    visual_rung: str = "not_attempted"
    elapsed_ms: float = 0.0

    def as_dict(self) -> dict:
        row = asdict(self)
        row["candidates"] = "; ".join(self.candidates)
        row["near_miss"] = "; ".join(self.near_miss)
        row["parser_exceptions"] = "; ".join(self.parser_exceptions)
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
    _last_visual_cached = False

    def __init__(
        self,
        root: Path,
        *,
        mode: str,
        run_id: str,
        sink=None,
        cache=None,
        dedup: DedupIndex | None = None,
        visual_escalation: bool = True,
    ) -> None:
        self.root = root
        self.mode = mode
        self.run_id = run_id
        self.sink = sink
        self.cache = cache
        self.dedup = dedup if dedup is not None else DedupIndex.with_pinned_corpus()
        self.allow_local_ocr = mode in LOCAL_OCR_MODES
        self.allow_visual_ocr = mode == MODE_SCANNED_VISUAL
        # Escalation is a policy knob ON TOP of the rung: `--no-visual-escalation`
        # recovers the documents nothing could read without spending GPU time
        # re-reading Tesseract output.
        self.visual_escalation = bool(visual_escalation) and self.allow_visual_ocr
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

    def _read_visual(self, raw: bytes, source_file: str, profile):
        """(document, markdown, error_type). The visual rung, cached, fail-closed.

        `force_ocr=True` goes straight to the visual rung: the offline rungs
        either already ran on this document or provably cannot serve it, and
        re-running them would only burn time. It is also what keeps this read in
        its own D-3 partition — `force_ocr`, `allow_local_ocr` and
        `allow_visual_ocr` are all cache-key material, as are the visual service
        knobs (`ocr_model`, `ocr_base_url`, `ngram_size`, `window_size`,
        `dpi`, `fallback_dpi`), so a visual artifact can never be served for an
        offline read or across a model/endpoint change.

        The endpoint can die mid-run. `ocr_page` retries and then re-raises, so
        that exception is caught HERE and returned as an error type: this
        document fails closed and the run continues. A failure is never cached —
        `cached_ocr` only stores what `compute` returned.
        """
        from ocr.pipeline import parse_statement

        def compute():
            return parse_statement(
                raw,
                source_file=source_file,
                profile=profile,
                force_ocr=True,
                allow_local_ocr=False,
                allow_visual_ocr=True,
            )

        try:
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
                    force_ocr=True,
                    allow_local_ocr=False,
                    allow_visual_ocr=True,
                )
                document, cached = result.value, result.cached
        except Exception as exc:
            self._last_visual_cached = False
            return None, None, type(exc).__name__
        self._last_visual_cached = cached
        if document is None:
            return None, None, None
        return document, document.to_markdown(), None

    def _analyse(self, markdown: str, collector):
        """(payload, error_type, cached). Deterministic mode; never raises."""
        def analyse():
            return report_to_dict(analyze_markdown(
                markdown, parse_mode="deterministic", on_dispatch=collector
            ))

        try:
            if self.cache is None:
                return analyse(), None, False
            from webapp.artifact_cache import cached_analysis

            result = cached_analysis(
                markdown, compute=analyse, cache=self.cache,
                parse_mode="deterministic",
            )
            return result.value, None, result.cached
        except Exception as exc:
            return None, type(exc).__name__, False

    def _needs_visual_upgrade(self, document, collector, payload) -> bool:
        """Is this the class-5 shape — a Tesseract read nobody could claim?

        Deliberately narrow, in three ways:

        * **Tesseract only.** A native-text document that goes unclaimed is a
          layout problem (discovery class 1), and re-reading perfect text with a
          GPU cannot fix a missing parser.
        * **A live dispatch only.** On a D-3 analysis cache hit no dispatch
          exists this run; guessing "unclaimed" there would escalate the entire
          archive on every re-run. A cached payload means it analysed fine.
        * **Not for parser crashes.** A claimed document whose parser then threw
          is a parser defect (W3-1), not an OCR one, so it is left alone.
        """
        if not self.visual_escalation or document is None:
            return False
        if source_path_for(document.model) != "local_tesseract":
            return False
        if collector.seen:
            return collector.dispatch.outcome != "claimed"
        return payload is None

    # -- one document -------------------------------------------------------

    def process(
        self, relative_path: str, folder_label: str,
        *, disk_relative_path: str | None = None,
    ) -> DocumentRow:
        # relative_path is the document's IDENTITY (manifest spelling, from
        # enumerate_root); disk_relative_path is where the bytes actually live
        # when a case-insensitive filesystem kept a different casing
        # (Inventory.disk_spelling). Only the read uses the disk spelling.
        started = time.perf_counter()
        path = self.root / (disk_relative_path or relative_path)
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
            row.outcome_class, row.outcome_reason = "deferred", "profile_only"
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        if not profile.valid_pdf or profile.encrypted:
            row.outcome_class = "failed"
            row.outcome_reason = "encrypted" if profile.encrypted else "invalid_pdf"
            self._emit(row, profile, None, None, None, collector, timer,
                       error_reason=row.outcome_reason)
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        name = Path(relative_path).name
        with timer.time("ocr"):
            document, markdown, note = self._read(raw, name, profile)

        if markdown is None and not self.allow_visual_ocr:
            # Recorded, never skipped: real work this tranche deliberately did
            # not do. `deferred` is its own outcome class precisely so that
            # `failed` can keep meaning "attempted and errored" — the two are
            # different findings and DSC-2 acts on them differently.
            row.outcome_class = "deferred"
            row.outcome_reason = (
                "deferred_scanned" if note == "deferred_offline_rungs" else "deferred_visual_ocr"
            )
            row.source_path = "none"
            self._emit(row, profile, None, None, None, collector, timer,
                       deferred=row.outcome_reason)
            row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return row

        if markdown is None:
            # RECOVERY: exactly the `deferred_visual_ocr` class of tranche 2.
            # The mode exists to attempt these, so from here on the document can
            # no longer be deferred — it either reads or it fails, explicitly.
            with timer.time("visual_ocr"):
                document, markdown, visual_error = self._read_visual(raw, name, profile)
            timer.set_cache("visual_ocr", _disposition(self.cache, self._last_visual_cached))
            row.cache_visual = timer.as_dict()["visual_ocr"]["cache"]
            if markdown is None:
                # The rung was asked and produced nothing: an exception (server
                # down) or, only in principle, a cached negative. Either way the
                # document is terminal, and `error_type` tells the two apart.
                row.visual_rung = VISUAL_FAILED
                row.outcome_class, row.outcome_reason = "failed", "ocr_failed"
                row.error_type = visual_error
                row.source_path = "none"
                self._emit(row, profile, None, None, None, collector, timer,
                           error_type=visual_error, error_reason="ocr_failed",
                           fallback_reason=_fallback_reason(row.visual_rung))
                row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
                return row
            row.visual_rung = VISUAL_RECOVERED
            note = None

        source = source_section(document)
        row.source_path = "committed_artifact" if note == "committed_artifact" else source["path"]
        row.source_model = source["model"]
        row.truncated_pages = source["truncation"]["truncated_page_count"]

        with timer.time("analysis"):
            payload, error_type, analysis_cached = self._analyse(markdown, collector)

        if self._needs_visual_upgrade(document, collector, payload):
            # UPGRADE (discovery class 5): Tesseract produced text and no parser
            # could claim it. Read the pixels again with the visual rung and keep
            # that read ONLY if it analyses — in deterministic mode a payload
            # exists if and only if a parser claimed, so "it analysed" IS the
            # adoption test, and it stays correct on a D-3 cache hit where no
            # dispatch is observable.
            with timer.time("visual_ocr"):
                visual_doc, visual_md, visual_error = self._read_visual(raw, name, profile)
            timer.set_cache("visual_ocr", _disposition(self.cache, self._last_visual_cached))
            row.cache_visual = timer.as_dict()["visual_ocr"]["cache"]
            row.visual_rung = VISUAL_FAILED if visual_error else VISUAL_NO_UPGRADE
            if visual_md is not None:
                visual_collector = DispatchCollector()
                with timer.time("visual_analysis"):
                    visual_payload, visual_error_type, visual_cached = self._analyse(
                        visual_md, visual_collector
                    )
                if visual_payload is not None:
                    row.visual_rung = VISUAL_UPGRADED
                    document, markdown, collector = visual_doc, visual_md, visual_collector
                    payload, error_type, analysis_cached = (
                        visual_payload, visual_error_type, visual_cached
                    )
                    source = source_section(document)
                    row.source_path = source["path"]
                    row.source_model = source["model"]
                    row.truncated_pages = source["truncation"]["truncated_page_count"]

        dispatch = collector.dispatch
        if dispatch is not None:
            row.dispatch_outcome = dispatch.outcome
            row.parser_id = dispatch.parser_id
            row.parser_score = (
                dispatch.detection.score if dispatch.detection is not None else None
            )
            row.candidates = _fmt(dispatch.candidates)
            row.parser_exceptions = [
                f"{failure.parser_id}:{failure.stage}:{failure.exception}"
                for failure in dispatch.exceptions
            ]

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
            fallback_reason=_fallback_reason(row.visual_rung),
        )
        row.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return row

    # -- telemetry ----------------------------------------------------------

    def _emit(
        self, row, profile, document, markdown, payload, collector, timer,
        *, error_type=None, error_reason=None, deferred=None, scores=None,
        escalated=False, fallback_reason=None,
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
                deferred=deferred,
                fallback_reason=fallback_reason,
            ))
        except Exception:
            return None


def _disposition(cache, cached: bool) -> str:
    return "bypass" if cache is None else ("hit" if cached else "miss")


def _fallback_reason(visual_rung: str) -> str | None:
    """The row's visual disposition as an H-3 enum code.

    It travels in `outcome.fallback_reason` — an existing, previously unused
    record field whose meaning is exactly this: the ladder did not stop where it
    normally stops. No telemetry field was added for W3-5.
    """
    if visual_rung == VISUAL_NOT_ATTEMPTED:
        return None
    return f"visual_ocr_{visual_rung}"


def _failure_reason(error_type: str | None, dispatch) -> str | None:
    """Why this document failed, in the vocabulary the report ranks by.

    The `parser_exception` branch is what the W3-1 boundary bought: before it,
    a crashing parser produced no `Dispatch` at all, so the run recorded the
    bare exception class of whatever escaped and every crash landed in the
    undifferentiated `exception` bucket. Now the dispatch says a parser broke,
    the deterministic mode's own `RuntimeError` no longer disguises it as
    "no parser matched", and the row names the failure class it belongs to.
    """
    if error_type is None:
        return None
    if error_type == "AmbiguousParserError":
        return "parser_ambiguous"
    if dispatch is not None and dispatch.outcome == "parser_exception":
        return "parser_exception"
    if dispatch is not None and dispatch.outcome == "unclaimed":
        return "no_parser_matched"
    return "exception"
