from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from ocr.config import load_settings as load_ocr_settings
from ocr.private_artifacts import private_artifact_path
from ocr.visual_pair_config import (
    MODEL_TOKEN as VISUAL_PAIR_MODEL_TOKEN,
    check_remote_authorization, load_visual_pair_settings,
)
from analysis.pipeline import DocumentReport, analyze_document
from analysis.serialization import document_report_to_dict
from ocr.document import StatementMarkdown
from ocr.escalation import (
    OFFLINE_RUNGS_PRODUCED_NO_TEXT,
    OPERATOR_FORCED_VISUAL,
    OPERATOR_FORCED_VISUAL_PAIR,
    DETERMINISTIC_PARSE_UNVALIDATED,
    Escalation,
    EscalationRouter,
    ExtractionQualityGate,
    router_inputs,
)
from ocr.inspect import DocumentProfile, content_sha256, inspect_pdf
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html
from telemetry import (
    DispatchCollector,
    StageTimer,
    build_record,
    dispatch_section,
    document_section,
    model_calls_for,
    new_run_id,
    open_sqlite_sink,
    score_vector,
    source_section,
)
from .artifact_cache import ArtifactCache, cached_analysis, cached_ocr, cached_report
from .jobs import JobStore

#: One run id per worker process, so every job this server handled groups
#: together in the coverage report.
_RUN_ID = new_run_id()


def document_to_json(document: DocumentReport) -> dict:
    """The published payload for one DOCUMENT.

    The seam moved off `report_to_dict` at L1-S3: every account this document
    carries is published, and RULE S makes that byte-identical to what this
    function returned before on every document carrying one — which is every
    document `analyze_document` produces at this tree.
    """
    return document_report_to_dict(document)


# O-1: the worker owns NO routing decisions. The single intake ladder
# (native -> tesseract -> visual OCR) lives in ocr.pipeline.parse_statement,
# driven by the preflight DocumentProfile; this module only expresses mode
# policy (deterministic short-circuits and the analysis-driven visual-OCR
# escalation) and job-store bookkeeping. The ladder reports each rung through
# on_stage, mapped here to the dashboard's historical stage labels.
_STAGE_NAMES = {
    "native": "reading",
    "local_ocr": "reading_local_ocr",
    "visual_ocr": "reading_visual_ocr",
}

#: The named stages this module publishes at its exception boundary. Constants
#: of ours, never anything read out of a document, so a stage name cannot
#: itself be a leak. `preflight`/`reading`/`analysis` are the three coarse
#: phases `run_job` runs in; the store's finer `stage` column
#: (`reading_visual_ocr`, `analyzing`, …) still records which rung was live.
_PHASE_PREFLIGHT = "preflight"
_PHASE_READING = "reading"
_PHASE_ANALYSIS = "analysis"

#: The job states `run_job` may NOT leave behind (#PRIVACY3, closing
#: #WORKERPRIV m-7). `queued`/`processing` mean "a worker is still on it"; once
#: `run_job` has returned or unwound, no worker is, so either one is a job that
#: will never move again. The store's own vocabulary is
#: queued/processing/done/error/interrupted (`webapp/jobs.py:35`).
_NON_TERMINAL_STATUSES = frozenset({"queued", "processing"})

#: What a job that reached neither `set_result` nor an exception arm is marked
#: with. A fixed literal: by definition there is no exception object here to
#: name a class from, and there is certainly nothing read out of a document.
_STUCK_JOB_FAILURE = (
    "the worker stopped without publishing a result "
    "(message withheld; an exception message can quote statement text)"
)

#: The analysis pipeline's DECLARED refusals (#WORKERPRIV D2).
#:
#: `analysis/pipeline.py` raises a small number of refusals that are FIXED
#: LITERALS of ours: they say why the deterministic path declined and carry no
#: document content by construction. This is the one that a user can act on —
#: `webapp/static/app.js:friendlyAnalysisError` matches it and answers "use
#: Auto mode, or add a deterministic parser for this bank", which is the most
#: common and most actionable outcome the deterministic mode produces.
#:
#: Matching is EXACT and the value published is the member of this tuple, not
#: the exception's own string, so what crosses the boundary is provably a
#: constant in this file. A message that merely CONTAINS a declared literal
#: (an exception that quoted a cell alongside it) does not match and is
#: reduced like any other. The information that crosses is one bit per member
#: — "the pipeline declared this refusal" — which is a registry-level fact,
#: not statement content.
#:
#: Deliberately NOT keyed on exception type: the refusal is a bare
#: `RuntimeError`, and `AmbiguousParserError`/`ParserCrashError` subclass it,
#: so a type test would admit every RuntimeError in the process. Those two DO
#: carry safe messages (registry ids, class names) but their text VARIES, so
#: they cannot be pinned to a constant here — they publish their class name,
#: which already names the finding.
_DECLARED_ANALYSIS_REFUSALS: tuple[str, ...] = (
    "no deterministic parser matched this statement",
    "visual pair requires human review",
)

#: Phase 3.1 adds the reviewed pair to the worker's capability vocabulary.
#: Each router seam selects a fixed subset; Paddle remains disabled.
WORKER_ENABLED_EXTRACTORS: frozenset[str] = frozenset({"visual", "visual_pair"})
WORKER_LEGACY_EXTRACTORS: frozenset[str] = frozenset({"visual"})
WORKER_PAIR_EXTRACTORS: frozenset[str] = frozenset({"visual_pair"})


def _force_ocr_decision(doc, profile: DocumentProfile | None, analysis: dict | None) -> Escalation:
    """P20-ROUTER item 3: the deterministic `force_ocr` fallback's ONE router
    call — the only legal path from "the offline ladder did not produce a
    claim" to the visual rung in this module.

    START = the operator's explicit flag, `OPERATOR_FORCED_VISUAL`. It is the
    SOLE trigger here (unlike `discovery/runner.py`'s automatic, unattended
    UPGRADE path, which never admits it — see that trigger's docstring in
    `ocr/escalation.py`): `force_ocr` is set by a human or API caller BEFORE
    any stage runs, for exactly this one document, which is a different
    epistemic situation from a bulk pipeline reaching for a second engine
    because the first one did not balance.

    STOP = `analysis is not None`. This is legal ONLY because in deterministic
    mode a payload exists IFF a parser claimed: `analysis/pipeline.py:917-918`
    raises `RuntimeError("no deterministic parser matched this statement")`
    (and `AmbiguousParserError` / `ParserCrashError` before it) on every other
    `resolve` outcome — `tests/test_escalation_router.py` pins that exact
    string. `EscalationRouter.decide` checks `stop` FIRST, before any trigger,
    so a document that already claimed — even one that will go on to fail
    financial validation (Class C) — can never reach `OPERATOR_FORCED_VISUAL`,
    regardless of the flag. That is what makes "no C -> OCR edge" hold at this
    call site too, and it is a STRICTER reading than the literal ruling this
    card implements it against (which names `stop` for "validated" specifically
    on the discovery runner's own upgrade path) — flagged in the P20-ROUTER
    report rather than silently narrowed.
    """
    evidence = ExtractionQualityGate.assess(doc, profile)
    triggers = frozenset({OPERATOR_FORCED_VISUAL})
    if doc is None:
        triggers = triggers | frozenset({OFFLINE_RUNGS_PRODUCED_NO_TEXT})
    return EscalationRouter.decide(router_inputs(
        profile=profile, evidence=evidence, triggers=triggers,
        attempted=("local_tesseract",), stop=analysis is not None,
        enabled=WORKER_LEGACY_EXTRACTORS,
    ))


def _stage_failure(stage: str, exc: BaseException) -> str:
    """The only exception text this module may put in the durable store.

    `analysis/pipeline.py` states the law for the deterministic seam — every
    crash reduced to the exception's CLASS NAME, never its message, because a
    message routinely quotes the cell of the document that provoked it
    (H3_SCHEMA I1, W3 §MG-C2 D1). That comment names THIS module as the reason
    the law exists, and this module held the two holes it names: `_analyze_doc`
    returned `str(e)` as the job's `analysis_error` and `run_job` stored
    `str(e)` as the job's `error`.

    Both are DURABLE — written through `JobStore` into the `jobs` table in
    `webapp/storage.py` — and both are served verbatim to the browser by
    `/status`, `/result` and `/analysis`. A refusal that quoted an account
    number was therefore published, survived a restart, and sat in front of a
    user. `read_money` closed the loudest source and `apply_statement_repairs`
    closed the widest seam; this closes the BOUNDARY, which is the part that
    holds for the exceptions neither card could see — an `int()` on a mangled
    cell, a `KeyError` on a mis-shaped grid, a third-party reader quoting a
    token it choked on.

    Deliberately NO second sink for the message. This module has no logger
    today, and adding one to hold the full text would MOVE the content rather
    than stop it: a new durable, unmasked, unaudited copy of the same fragment
    (#WORKERPRIV D1). The operator channel already exists and is already
    compliant — the telemetry record carries `error_type` (the class name) and
    the per-stage timings, so WHICH stage raised and WHAT raised are both
    recoverable without the text. Reproducing a crash needs the document, and
    the document is in the store already.
    """
    return (
        f"{stage} stage failed: {type(exc).__name__} "
        "(message withheld; an exception message can quote statement text)"
    )


def _analysis_failure(exc: BaseException) -> str:
    """The analysis boundary's published reason.

    A declared refusal keeps its named reason (see
    `_DECLARED_ANALYSIS_REFUSALS`); anything else is reduced to class name plus
    stage. Fail-closed: the reduction is the default and the allow-list is a
    closed tuple of constants, so a new refusal message the pipeline invents is
    withheld until someone deliberately admits it here.
    """
    message = str(exc)
    for declared in _DECLARED_ANALYSIS_REFUSALS:
        if message == declared:
            return declared  # this module's constant, not the exception's text
    return _stage_failure(_PHASE_ANALYSIS, exc)



def _visual_pair_summary_html(doc: StatementMarkdown, *, policy: str) -> str:
    """Counts and a safely escaped local view of retained source evidence."""
    from math import isfinite
    from webapp.visual_pair_review import retained_evidence_html

    evidence = getattr(doc, "visual_pair", None)
    if not isinstance(evidence, dict):
        return ""
    confidence = evidence.get("confidence") or {}
    if not isinstance(confidence, dict):
        return ""
    counts = confidence.get("counts") or {}
    counts = counts if isinstance(counts, dict) else {}
    score = confidence.get("score")
    score_text = (f"{score:.1%}" if type(score) in (int, float)
                  and isfinite(score) and 0 <= score <= 1 else "unavailable")
    labels = (("agreed", "confirmed"), ("corrected", "corrected"),
              ("added", "added"), ("rejected", "rejected"), ("unresolved", "unresolved"))
    row_counts = []
    for key, label in labels:
        value = counts.get(key)
        row_counts.append(f"{value if type(value) is int and value >= 0 else 0} {label}")
    gate = evidence.get("gate") or {}
    passed = isinstance(gate, dict) and gate.get("admitted") is True
    status = ("Human review required before publishing metrics."
              if policy == "always_review" else "Statement checks passed.")
    if not passed:
        status = "Statement checks failed; metrics are withheld."
    if confidence.get("methodology") == "evidence_v2":
        band = {"very_high": "very high", "high": "high", "moderate": "moderate", "low": "low",
                "held": "held"}.get(confidence.get("band"), "unavailable")
        components = confidence.get("components") if isinstance(confidence.get("components"), dict) else {}
        names = (("stated_totals", "printed totals"), ("stated_counts", "printed counts"),
                 ("amounts_printed", "amounts printed on the page"), ("two_readers", "both readers agree"),
                 ("descriptions_in_text_layer", "descriptions in the PDF text"),
                 ("running_balances", "running balances"))
        parts = []
        for key, label in names:
            value = components.get(key)
            parts.append(f"{label} {value:.0%}" if type(value) in (int, float) and isfinite(value)
                         and 0 <= value <= 1 else f"{label} n/a")
        headline = f"Extraction confidence: {score_text} ({band})"
        explanation = ("The score is the share of this reading that was verified independently, by the "
                       "statement's own printed figures and by two readers; it is not a probability.")
        detail = '<p>Verified: ' + ', '.join(parts) + '</p>'
    else:
        headline = f"Provisional extraction confidence: {score_text}"
        explanation = ("This score measures reader agreement and statement checks; "
                       "it is not a probability of correctness.")
        detail = ""
    return (
        '<section class="visual-pair-summary" role="note" '
        'style="padding:1rem;border:1px solid #b98a30;background:#fff8e6;color:#453313;margin-bottom:1rem">'
        f'<strong>{headline}</strong>'
        f'<p>{status} {explanation}</p>' + detail +
        '<p>Rows: ' + ', '.join(row_counts) + '</p></section>'
        + retained_evidence_html(evidence)
    )

def _analyze_doc(
    doc: StatementMarkdown,
    filename: str,
    parse_mode: str,
    cache: ArtifactCache | None = None,
    job_id: str | None = None,
    store: JobStore | None = None,
    collector: DispatchCollector | None = None,
    timer: StageTimer | None = None,
) -> tuple[str, str, dict | None, str | None]:
    markdown = doc.to_markdown()
    with _timed(timer, "report"):
        rendered = cached_report(
            markdown,
            compute=lambda: markdown_to_html(markdown, title=filename),
            cache=cache,
            title=filename,
        )
    html = rendered.value
    _note_cache(store, job_id, rendered, timer)
    try:
        if getattr(doc, "visual_pair", None) is not None or doc.model == VISUAL_PAIR_MODEL_TOKEN:
            from vlm.pair_adapter import analyze_visual_pair

            policy = load_visual_pair_settings().review_policy
            summary = _visual_pair_summary_html(doc, policy=policy)
            html = html.replace("<body>", "<body>" + summary, 1) if "<body>" in html else summary + html
            with _timed(timer, "analysis"):
                report = analyze_visual_pair(
                    doc, on_dispatch=collector,
                    review_policy="hold" if policy == "always_review" else policy,
                )
                analysis = document_to_json(report)
            analysis["parse_mode"] = parse_mode
            analysis["visual_pair_confidence"] = dict(doc.visual_pair.get("confidence") or {})
            return markdown, html, analysis, None
        with _timed(timer, "analysis"):
            # `doc.pages` is the intake object's own page list, and it goes to
            # both the analysis and the cache. `assess_document_integrity` reads
            # it to tell an unlabelled sheet apart from an absent page, and it
            # refuses to recover that structure from `markdown` because a page
            # can print the separator line (W3 §PIPEFIX P4b.1); the cache keys
            # on it for the same reason (W3 §WIRING W3).
            analyzed = cached_analysis(
                markdown,
                compute=lambda: document_to_json(
                    analyze_document(
                        markdown, parse_mode=parse_mode, on_dispatch=collector,
                        sheets=doc.pages,
                    )
                ),
                cache=cache,
                parse_mode=parse_mode,
                sheets=doc.pages,
            )
        _note_cache(store, job_id, analyzed, timer)
        # Copy before stamping: on a cache hit the payload came straight out
        # of the artifact store, and `parse_mode` is a serving-time annotation
        # rather than part of the cached analysis (it already partitions the
        # analysis cache key).
        analysis = dict(analyzed.value)
        analysis["parse_mode"] = parse_mode
        return markdown, html, analysis, None
    except Exception as e:
        # #WORKERPRIV site 1. This return value becomes the job's DURABLE
        # `analysis_error` (`store.set_result`), which `/analysis`, `/result`
        # and `/status` serve verbatim. The markdown and the rendered report
        # still publish — the document was read, only the analysis refused —
        # so the user gets the statement plus a named reason, and never the
        # exception's own text.
        return markdown, html, None, _analysis_failure(e)


def _note_cache(
    store: JobStore | None, job_id: str | None, result, timer: StageTimer | None = None
) -> None:
    # Two different consumers of the same fact, deliberately not merged: the
    # audit row is the webapp's durable event history (D-3), while the
    # telemetry disposition is per-record and must also work on the CLI path,
    # where no audit row is ever written. Telemetry reads CacheResult.cached
    # directly rather than re-reading the audit log (H3_SCHEMA §7).
    if timer is not None:
        timer.set_cache(result.stage, "hit" if result.cached else "miss")
    if store is not None and job_id is not None and result.cached:
        store.record_cache_hit(job_id, result.stage, result.cache_key)


class _NullTimerContext:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        return None


def _timed(timer: StageTimer | None, stage: str):
    return timer.time(stage) if timer is not None else _NullTimerContext()


def _emit(
    store: JobStore,
    job_id: str,
    profile: DocumentProfile | None,
    byte_size: int,
    doc: StatementMarkdown | None,
    markdown: str | None,
    analysis: dict | None,
    analysis_error: str | None,
    collector: DispatchCollector,
    timer: StageTimer,
    error_type: str | None = None,
) -> None:
    """Write one telemetry record. Never raises — I4.

    A telemetry defect must cost a measurement, not a job: this is called from
    both the success and the failure paths of `run_job`, including from inside
    its `except`.
    """
    try:
        sink = open_sqlite_sink(getattr(store, "storage", None))
        # The collector holds this job's dispatch, so the near-miss sweep
        # reuses its prepared text instead of preparing the document a second
        # time (#PREPHAND). Guarded on the text inside `score_vector`: on a
        # D-3 analysis cache hit nothing dispatched and the sweep runs whole.
        scores, registration_count = score_vector(markdown, collector) if markdown else ([], 0)
        dispatch = dispatch_section(
            collector.dispatch, scores, registration_count, payload=analysis,
        )
        sink.write(build_record(
            run_id=_RUN_ID,
            emitter="webapp",
            job_id=job_id,
            document=document_section(
                profile.content_sha256 if profile else "", byte_size, profile
            ),
            source=source_section(doc),
            dispatch=dispatch,
            stages=timer.as_dict(),
            model_calls=model_calls_for(doc, analysis),
            payload=analysis,
            escalated=bool((analysis or {}).get("escalated")),
            error_type=error_type,
            error_reason="analysis_error" if analysis_error and not error_type else None,
        ))
    except Exception:
        return None


def _cached_ocr_timed(timer: StageTimer | None, pdf_bytes: bytes, **kwargs):
    with _timed(timer, "ocr"):
        return cached_ocr(pdf_bytes, **kwargs)


def _read_document(
    job_id: str,
    store: JobStore,
    cache: ArtifactCache | None,
    pdf_bytes: bytes,
    filename: str,
    profile: DocumentProfile,
    *,
    force_ocr: bool,
    allow_local_ocr: bool,
    allow_visual_ocr: bool,
    on_stage,
    on_delta,
    on_replace,
    timer: StageTimer | None = None,
) -> StatementMarkdown | None:
    """One intake-ladder run, served from the D-3 artifact cache when these
    exact bytes were already read under these exact settings.

    The capability flags are passed identically to ``parse_statement`` and to
    the cache key — they decide which rung produces the text, so they must
    partition the cache. A cached read replays its pages into the live buffer
    (the ladder's own ``on_page_replace`` contract) so the viewer still fills
    in even though nothing was OCR'd.
    """
    result = _cached_ocr_timed(
        timer,
        pdf_bytes,
        compute=lambda: parse_statement(
            pdf_bytes,
            source_file=filename,
            profile=profile,
            force_ocr=force_ocr,
            allow_local_ocr=allow_local_ocr,
            allow_visual_ocr=allow_visual_ocr,
            on_stage=on_stage,
            on_page_delta=on_delta,
            on_page_replace=on_replace,
        ),
        cache=cache,
        source_file=filename,
        content_hash=profile.content_sha256,
        force_ocr=force_ocr,
        allow_local_ocr=allow_local_ocr,
        allow_visual_ocr=allow_visual_ocr,
    )
    _note_cache(store, job_id, result, timer)
    if result.cached and result.value is not None:
        for index, page in enumerate(result.value.pages):
            on_replace(index, page)
    return result.value



def _pair_fallback_needed(analysis: dict | None, trigger: str) -> bool:
    if analysis is None:
        return True
    if trigger == "broad":
        from telemetry.record import classify_document

        return classify_document(analysis)[0] != "validated"
    return False


def _pair_decision(doc, profile, *, forced: bool) -> Escalation:
    return EscalationRouter.decide(router_inputs(
        profile=profile, evidence=ExtractionQualityGate.assess(doc, profile),
        triggers=frozenset({OPERATOR_FORCED_VISUAL_PAIR if forced
                            else DETERMINISTIC_PARSE_UNVALIDATED}),
        attempted=(), stop=False, enabled=WORKER_PAIR_EXTRACTORS,
    ))


def _read_visual_pair(job_id, store, cache, pdf_bytes, filename, profile, *, timer):
    from vlm.pair import extract_visual_pair

    settings = load_visual_pair_settings()
    # Even a cache hit must not bypass revoked remote customer authorization.
    # A web upload always has customer scope; it cannot opt into synthetic.
    check_remote_authorization(settings, data_scope="customer", pdf_sha256=content_sha256(pdf_bytes).lower())
    evidence_dir = private_artifact_path("visual_pair_evidence")

    def compute():
        with TemporaryDirectory(prefix="visual-pair-input-") as temporary:
            pdf = Path(temporary) / "statement.pdf"
            pdf.write_bytes(pdf_bytes)
            result = extract_visual_pair(
                pdf, settings=settings, evidence_dir=evidence_dir,
                progress=lambda stage: store.set_stage(job_id, stage),
                data_scope="customer",
            )
        return replace(result, source_file=filename)

    result = _cached_ocr_timed(
        timer, pdf_bytes, compute=compute, cache=cache, source_file=filename,
        content_hash=profile.content_sha256 if profile is not None else content_sha256(pdf_bytes), force_ocr=True,
        allow_local_ocr=False, allow_visual_ocr=False, allow_visual_pair=True,
        visual_pair_settings=settings,
    )
    _note_cache(store, job_id, result, timer)
    if result.value is None:
        raise RuntimeError("visual pair produced no document")
    for index, page in enumerate(result.value.pages):
        store.set_page_live(job_id, index, page)
    return result.value

def run_job(
    job_id: str,
    pdf_bytes: bytes,
    filename: str,
    store: JobStore,
    force_ocr: bool = False,
    parse_mode: str = "auto",
) -> None:
    # Persistence (D-1): every set_status/set_stage transition and the final
    # set_result/set_error below write through the JobStore facade into the
    # durable store (webapp/storage.py). Reaching a terminal state also
    # releases the job's in-memory pdf_bytes; afterwards /page and /render
    # serve the PDF from the on-disk content-hash store.
    #
    # Cache (D-3): every expensive stage below goes through the content-hash
    # artifact cache bound to the same data directory, so re-processing
    # byte-identical content performs zero OCR and zero LLM calls.
    store.set_status(job_id, "processing")
    cache = store.cache
    # Telemetry (H-3): write-only side-band. The collector observes the R-3
    # Dispatch through the analysis's on_dispatch seam; the timer collects
    # per-stage wall clock and cache disposition. Neither can change a result,
    # and _emit swallows its own failures.
    timer = StageTimer()
    collector = DispatchCollector()
    profile: DocumentProfile | None = None
    doc: StatementMarkdown | None = None
    # The named stage for the job-level exception boundary below (#WORKERPRIV
    # site 2). Advanced inside the `read`/`analyze` closures rather than at
    # their six call sites, so a new mode branch cannot forget it.
    #
    # KNOWN GRANULARITY, stated rather than hidden: `set_result` runs after
    # `analyze` returns, so a storage-layer crash while publishing is
    # attributed to `analysis`. The class name is exact either way, and the
    # telemetry record's per-stage timings separate the two.
    phase = _PHASE_PREFLIGHT
    try:
        ocr_settings = load_ocr_settings()
        pair_enabled = ocr_settings.allow_visual_pair
        legacy_visual = ocr_settings.visual_pair_legacy_visual
        # inspect_pdf itself reads native text for classification. A forced
        # pair request bypasses that probe as well as the native parser.
        if not (force_ocr and not legacy_visual):
            with timer.time("preflight"):
                profile = inspect_pdf(pdf_bytes)

        def on_stage(rung: str) -> None:
            store.set_stage(job_id, _STAGE_NAMES[rung])

        def on_delta(page: int, chunk: str) -> None:
            store.append_page_live(job_id, page, chunk)

        def on_replace(page: int, text: str) -> None:
            store.set_page_live(job_id, page, text)

        def read(**flags) -> StatementMarkdown | None:
            nonlocal phase
            phase = _PHASE_READING
            return _read_document(
                job_id, store, cache, pdf_bytes, filename, profile,
                on_stage=on_stage, on_delta=on_delta, on_replace=on_replace,
                timer=timer, **flags,
            )

        def analyze(doc: StatementMarkdown) -> tuple[str, str, dict | None, str | None]:
            nonlocal phase
            phase = _PHASE_ANALYSIS
            return _analyze_doc(
                doc, filename, parse_mode, cache, job_id, store,
                collector=collector, timer=timer,
            )

        def pair_read(*, forced: bool) -> StatementMarkdown:
            nonlocal phase
            phase = _PHASE_READING
            if _pair_decision(doc, profile, forced=forced).extractor != "visual_pair":
                raise RuntimeError("visual pair escalation refused")
            return _read_visual_pair(
                job_id, store, cache, pdf_bytes, filename, profile, timer=timer,
            )

        if force_ocr and not legacy_visual:
            # The operator override bypasses native extraction AND analysis.
            doc = pair_read(forced=True)
        else:
            doc = read(
                force_ocr=force_ocr,
                allow_local_ocr=not force_ocr,
                allow_visual_ocr=legacy_visual and (force_ocr or parse_mode == "auto"),
            )
            if doc is not None:
                store.set_stage(job_id, "analyzing", doc.model)
                # With the pair enabled, an unmatched layout must reach the
                # reviewed structured rows without visiting the legacy LLM.
                if pair_enabled and parse_mode == "auto":
                    phase = _PHASE_ANALYSIS
                    markdown, html, analysis, analysis_error = _analyze_doc(
                        doc, filename, "deterministic", cache, job_id, store,
                        collector=collector, timer=timer,
                    )
                    if analysis is not None:
                        analysis["parse_mode"] = parse_mode
                else:
                    markdown, html, analysis, analysis_error = analyze(doc)
            else:
                analysis = None
            if pair_enabled and _pair_fallback_needed(
                analysis, ocr_settings.visual_pair_fallback_trigger,
            ):
                doc = pair_read(forced=False)
            elif doc is None:
                markdown = (
                    f"<!-- source: {filename} | model: deterministic-native-preflight -->\n\n"
                    "No usable native PDF text was found."
                )
                html = markdown_to_html(markdown, title=filename)
                store.set_result(
                    job_id, markdown, html, None,
                    "native PDF text unavailable or too sparse, and local Tesseract OCR did not produce usable statement text; turn on Force visual OCR to use the OCR service, or use Auto mode",
                    "deterministic-native-preflight",
                )
                _emit(store, job_id, profile, len(pdf_bytes), None, None, None,
                      "native text unavailable", collector, timer,
                      error_type="NoUsableNativeText")
                return
            else:
                store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
                _emit(store, job_id, profile, len(pdf_bytes), doc, markdown,
                      analysis, analysis_error, collector, timer)
                return

        store.set_stage(job_id, "analyzing", doc.model)
        markdown, html, analysis, analysis_error = analyze(doc)
        store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
        _emit(store, job_id, profile, len(pdf_bytes), doc, markdown,
              analysis, analysis_error, collector, timer)
    except Exception as e:
        # #WORKERPRIV site 2. The DURABLE job error is the class name plus the
        # named stage that raised. Until this hunk the line below was
        # `store.set_error(job_id, str(e))` — with the comment that follows it,
        # which described `_emit` while the store write beside it published the
        # very text the comment forbids.
        store.set_error(job_id, _stage_failure(phase, e))
        # Class name only, never the message: exception text routinely quotes a
        # fragment of the document (H3_SCHEMA I1).
        _emit(store, job_id, profile, len(pdf_bytes), doc, None, None, None,
              collector, timer, error_type=type(e).__name__)
    except BaseException as e:
        # #PRIVACY3, closing #WORKERPRIV m-7. The arm above catches `Exception`,
        # so a `BaseException` — `KeyboardInterrupt`, `SystemExit`, a
        # `MemoryError`'s escalation, a `GeneratorExit` — killed the queue
        # thread with a traceback on stderr and left the job at `processing`
        # with `error=None` FOREVER: no durable write, no telemetry record, and
        # a dashboard that polls a job which will never move again. The store's
        # startup `mark_interrupted` only reaches it after a RESTART; a
        # long-lived server never restarts.
        #
        # Fail-closed: the job is marked failed with the same fixed vocabulary
        # the arm above uses, so a status is written before anything else
        # happens.
        #
        # AND THEN IT RE-RAISES, which is the whole difference between this arm
        # and the one above. Swallowing `SystemExit` would defeat a shutdown and
        # swallowing `KeyboardInterrupt` would defeat Ctrl-C; the defect was
        # never that the thread died, it was that the job did not find out. The
        # thread still dies, exactly as it did before, and the stderr traceback
        # this raise produces is UNCHANGED — recorded, not decided, because
        # where a worker crash's full text should go is the D-2b/D-7 logging
        # question (#WORKERPRIV WP6.5), not something an exception-boundary card
        # gets to invent.
        store.set_error(job_id, _stage_failure(phase, e))
        _emit(store, job_id, profile, len(pdf_bytes), doc, None, None, None,
              collector, timer, error_type=type(e).__name__)
        raise
    finally:
        # The last resort, and it exists because both arms above can themselves
        # be interrupted: a `BaseException` raised INSIDE a handler (between
        # `set_error` and `_emit`, or during either) leaves the same stuck job
        # the arms exist to prevent. A `finally` is the only place that runs on
        # every exit — including the four `return`s in the body, where the job
        # is already `done` and this is a no-op read.
        #
        # It never overwrites a terminal state and it never raises: a status
        # check that could itself crash the thread would be a fifth way to
        # leave the job stuck.
        try:
            job = store.get(job_id)
            if job is not None and job.status in _NON_TERMINAL_STATUSES:
                store.set_error(job_id, _STUCK_JOB_FAILURE)
        except Exception:
            pass
