from __future__ import annotations
from dataclasses import asdict, dataclass, is_dataclass
from analysis.config import load_settings as load_analysis_settings
from analysis.pipeline import Report, analyze_markdown
from analysis.serialization import report_to_dict
from ocr.document import StatementMarkdown
from ocr.local_tesseract import parse_local_tesseract
from ocr.native_text import (
    parse_native_desjardins,
    parse_native_navy_federal,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
)
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html
from .jobs import JobStore


def report_to_json(report: Report) -> dict:
    return report_to_dict(report)


def _native_statement(pdf_bytes: bytes, filename: str) -> StatementMarkdown | None:
    return (
        parse_native_navy_federal(pdf_bytes, source_file=filename)
        or parse_native_td_canada(pdf_bytes, source_file=filename)
        or parse_native_wells_fargo(pdf_bytes, source_file=filename)
        or parse_native_desjardins(pdf_bytes, source_file=filename)
        or parse_native_pdf_text(pdf_bytes, source_file=filename)
    )


def _local_ocr_statement(pdf_bytes: bytes, filename: str) -> StatementMarkdown | None:
    return parse_local_tesseract(pdf_bytes, source_file=filename)


@dataclass
class _AnalysisCandidate:
    doc: StatementMarkdown
    markdown: str
    html: str
    report: object | None
    analysis: dict | None
    error: str | None


def _analyze_doc(
    doc: StatementMarkdown,
    filename: str,
    parse_mode: str,
    *,
    external_attempt_budget: int | None = None,
) -> _AnalysisCandidate:
    markdown = doc.to_markdown()
    html = markdown_to_html(markdown, title=filename)
    try:
        kwargs = {"parse_mode": parse_mode}
        if external_attempt_budget is not None:
            kwargs["external_attempt_budget"] = external_attempt_budget
        try:
            report = analyze_markdown(markdown, **kwargs)
        except TypeError as exc:
            # A number of integrations monkeypatch the historical two-argument
            # function. Preserve that extension point without weakening the real
            # production budget.
            if "external_attempt_budget" not in str(exc):
                raise
            report = analyze_markdown(markdown, parse_mode=parse_mode)
        analysis = report_to_json(report)
        analysis["parse_mode"] = parse_mode
        return _AnalysisCandidate(doc, markdown, html, report, analysis, None)
    except Exception as e:
        return _AnalysisCandidate(doc, markdown, html, None, None, str(e))


def _analysis_is_approved(analysis: dict | None) -> bool:
    if analysis is None:
        return False
    quality = analysis.get("quality") or {}
    corporate_use = quality.get("corporate_use")
    if corporate_use:
        quality_ok = corporate_use == "approved"
    else:
        # Backward-compatible with old/synthetic payloads while production
        # reports always provide corporate_use.
        quality_ok = quality.get("level") == "transaction_level"
    reconciliation = analysis.get("reconciliation") or {}
    integrity = analysis.get("integrity") or {}
    return bool(
        quality_ok
        and reconciliation.get("ok") is not False
        and integrity.get("possible_document_issue") is not True
    )


_SOURCE_CONTRADICTION_FLAGS = {
    "conflicting_statement_summaries",
    "missing_declared_statement_page",
    "not_a_formal_statement",
    "summary_math_inconsistent",
}


def _should_retry_visual_ocr(candidate: _AnalysisCandidate) -> bool:
    if not candidate.doc.model.startswith(("native-", "local-tesseract")):
        return False
    if _analysis_is_approved(candidate.analysis):
        return False
    if candidate.doc.model.startswith("local-tesseract"):
        # Tesseract is only a free preflight. Apparent contradictions in this
        # text may themselves be OCR errors, so one layout-aware read is warranted.
        return True
    flags = set(((candidate.analysis or {}).get("integrity") or {}).get("flags") or [])
    # OCR cannot repair a source PDF that is incomplete, contradictory, or not a
    # formal statement. Those cases should remain review cases without spending
    # another extraction attempt.
    return not bool(flags & _SOURCE_CONTRADICTION_FLAGS)


def _candidate_score(candidate: _AnalysisCandidate) -> int:
    if candidate.analysis is None:
        return -10_000
    analysis = candidate.analysis
    quality = analysis.get("quality") or {}
    reconciliation = analysis.get("reconciliation") or {}
    integrity = analysis.get("integrity") or {}
    metrics = analysis.get("metrics") or {}
    source_validation = analysis.get("source_validation") or {}
    score = 0
    if metrics.get("authoritative") is True:
        score += 2_000
    elif metrics.get("authoritative") is False:
        score -= 2_000
    if source_validation.get("ok") is True:
        score += 800
    elif source_validation.get("ok") is False:
        score -= 800
    if quality.get("corporate_use") == "approved":
        score += 1_000
    if quality.get("level") == "transaction_level":
        score += 250
    if quality.get("transaction_detail_reliable") is True:
        score += 200
    if reconciliation.get("ok") is True:
        score += 500
    if reconciliation.get("summary_ok") is True:
        score += 150
    if integrity.get("possible_document_issue") is not True:
        score += 100
    if integrity.get("risk_level") == "clear":
        score += 50
    if metrics.get("adb_ok") is True:
        score += 25
    return score


def _external_attempt_count(candidate: _AnalysisCandidate) -> int:
    document_attempts = len(getattr(candidate.doc, "external_attempts", []))
    if candidate.analysis is None:
        return document_attempts
    extraction = candidate.analysis.get("extraction") or {}
    return document_attempts + int(extraction.get("attempt_count") or 0)


def _attach_processing_trace(
    selected: _AnalysisCandidate,
    candidates: list[_AnalysisCandidate],
    *,
    visual_retry_error: str | None = None,
    external_attempt_limit: int | None = None,
) -> None:
    if selected.analysis is None or "reconciliation" not in selected.analysis:
        return
    all_external_attempts = []
    cost_complete = True
    for candidate in candidates:
        for attempt in getattr(candidate.doc, "external_attempts", []):
            attempt_record = asdict(attempt) if is_dataclass(attempt) else dict(attempt)
            attempt_record["document_source_model"] = candidate.doc.model
            all_external_attempts.append(attempt_record)
            if attempt_record.get("estimated_cost_usd") is None:
                cost_complete = False
        if candidate.analysis is None:
            continue
        extraction = candidate.analysis.get("extraction") or {}
        for attempt in extraction.get("attempts") or []:
            attempt_record = dict(attempt)
            attempt_record["document_source_model"] = candidate.doc.model
            all_external_attempts.append(attempt_record)
            if attempt_record.get("estimated_cost_usd") is None:
                cost_complete = False
    estimated_cost = round(
        sum(
            float(attempt.get("estimated_cost_usd") or 0.0)
            for attempt in all_external_attempts
        ),
        8,
    )
    selected.analysis["extraction"] = {
        "attempt_count": len(all_external_attempts),
        "attempts": all_external_attempts,
        "estimated_cost_usd": estimated_cost,
        "cost_complete": cost_complete,
        "attempt_limit": external_attempt_limit,
        "budget_exhausted": (
            external_attempt_limit is not None
            and external_attempt_limit > 0
            and len(all_external_attempts) >= external_attempt_limit
        ),
    }
    selected.analysis["processing"] = {
        "selected_source_model": selected.doc.model,
        "candidate_count": len(candidates),
        "visual_retry_performed": len(candidates) > 1,
        "visual_retry_error_type": visual_retry_error,
        "candidates": [
            {
                "source_model": candidate.doc.model,
                "analysis_succeeded": candidate.analysis is not None,
                "reconciliation_ok": ((candidate.analysis or {}).get("reconciliation") or {}).get("ok"),
                "corporate_use": ((candidate.analysis or {}).get("quality") or {}).get("corporate_use"),
                "integrity_risk": ((candidate.analysis or {}).get("integrity") or {}).get("risk_level"),
                "primary_ocr_error_type": getattr(candidate.doc, "metadata", {}).get(
                    "primary_ocr_error_type"
                ),
                "selected": candidate is selected,
            }
            for candidate in candidates
        ],
    }


def _visual_statement(
    job_id: str | None,
    pdf_bytes: bytes,
    filename: str,
    store: JobStore | None,
    *,
    external_attempt_budget: int = 0,
) -> StatementMarkdown:
    if store is not None and job_id is not None:
        store.set_stage(job_id, "reading_visual_ocr")
    try:
        return parse_statement(
            pdf_bytes,
            source_file=filename,
            on_page_delta=(
                (lambda page, chunk: store.append_page_live(job_id, page, chunk))
                if store is not None and job_id is not None
                else None
            ),
            on_page_replace=(
                (lambda page, text: store.set_page_live(job_id, page, text))
                if store is not None and job_id is not None
                else None
            ),
            force_ocr=True,
        )
    except Exception as primary_error:
        if external_attempt_budget <= 0:
            raise
        from ocr.gemini_document import parse_gemini_document

        fallback = parse_gemini_document(pdf_bytes, source_file=filename)
        fallback.metadata["primary_ocr_error_type"] = type(primary_error).__name__
        _publish_pages(store, job_id, fallback)
        return fallback


def _store_candidate(job_id: str, candidate: _AnalysisCandidate, store: JobStore) -> None:
    store.set_result(
        job_id,
        candidate.markdown,
        candidate.html,
        candidate.analysis,
        candidate.error,
        candidate.doc.model,
    )


def _set_stage(
    store: JobStore | None,
    job_id: str | None,
    stage: str,
    parse_model: str | None = None,
) -> None:
    if store is not None and job_id is not None:
        store.set_stage(job_id, stage, parse_model)


def _publish_pages(
    store: JobStore | None,
    job_id: str | None,
    doc: StatementMarkdown,
) -> None:
    if store is not None and job_id is not None:
        for page, text in enumerate(doc.pages):
            store.set_page_live(job_id, page, text)


def analyze_pdf(
    pdf_bytes: bytes,
    filename: str,
    *,
    force_ocr: bool = False,
    parse_mode: str = "auto",
    store: JobStore | None = None,
    job_id: str | None = None,
) -> _AnalysisCandidate:
    """Run the authoritative, cost-bounded PDF-to-report routing cascade."""
    if parse_mode not in {"auto", "deterministic"}:
        raise ValueError(f"unknown parse_mode: {parse_mode}")

    external_attempt_limit = load_analysis_settings().max_external_extraction_attempts
    if parse_mode == "deterministic":
        _set_stage(store, job_id, "reading")
        doc = _native_statement(pdf_bytes, filename)
        if doc is None:
            _set_stage(store, job_id, "reading_local_ocr")
            doc = _local_ocr_statement(pdf_bytes, filename)
        if doc is not None:
            _publish_pages(store, job_id, doc)
            _set_stage(store, job_id, "analyzing", doc.model)
            candidate = _analyze_doc(
                doc,
                filename,
                parse_mode,
                external_attempt_budget=0,
            )
            if candidate.analysis is not None or not force_ocr:
                _attach_processing_trace(
                    candidate,
                    [candidate],
                    external_attempt_limit=0,
                )
                return candidate
        elif not force_ocr:
            markdown = (
                f"<!-- source: {filename} | model: deterministic-native-preflight -->\n\n"
                "No usable native PDF text was found."
            )
            empty_doc = StatementMarkdown(
                source_file=filename,
                model="deterministic-native-preflight",
                pages=[],
            )
            return _AnalysisCandidate(
                empty_doc,
                markdown,
                markdown_to_html(markdown, title=filename),
                None,
                None,
                "native PDF text unavailable or too sparse, and local Tesseract OCR did not produce usable statement text; turn on Force visual OCR to use the OCR service, or use Auto mode",
            )

        doc = _visual_statement(job_id, pdf_bytes, filename, store)
        _set_stage(store, job_id, "analyzing", doc.model)
        candidate = _analyze_doc(
            doc,
            filename,
            parse_mode,
            external_attempt_budget=0,
        )
        _attach_processing_trace(
            candidate,
            [candidate],
            external_attempt_limit=0,
        )
        return candidate

    effective_force_ocr = force_ocr
    doc = None
    if not effective_force_ocr:
        _set_stage(store, job_id, "reading")
        doc = _native_statement(pdf_bytes, filename)
        if doc is None:
            _set_stage(store, job_id, "reading_local_ocr")
            doc = _local_ocr_statement(pdf_bytes, filename)
        if doc is not None:
            _publish_pages(store, job_id, doc)
    if doc is None:
        doc = _visual_statement(
            job_id,
            pdf_bytes,
            filename,
            store,
            external_attempt_budget=external_attempt_limit,
        )

    _set_stage(store, job_id, "analyzing", doc.model)
    local_preflight = doc.model.startswith("local-tesseract")
    first = _analyze_doc(
        doc,
        filename,
        "deterministic" if local_preflight else parse_mode,
        external_attempt_budget=(
            0
            if local_preflight
            else max(0, external_attempt_limit - len(getattr(doc, "external_attempts", [])))
        ),
    )
    if local_preflight and first.analysis is not None:
        first.analysis["parse_mode"] = parse_mode
    candidates = [first]
    visual_retry_error = None
    if not effective_force_ocr and _should_retry_visual_ocr(first):
        try:
            remaining_attempts = (
                external_attempt_limit
                if local_preflight
                else 0
                if first.analysis is None
                else max(0, external_attempt_limit - _external_attempt_count(first))
            )
            visual_doc = _visual_statement(
                job_id,
                pdf_bytes,
                filename,
                store,
                external_attempt_budget=remaining_attempts,
            )
            _set_stage(store, job_id, "analyzing", visual_doc.model)
            remaining_attempts = max(
                0,
                remaining_attempts - len(getattr(visual_doc, "external_attempts", [])),
            )
            candidates.append(
                _analyze_doc(
                    visual_doc,
                    filename,
                    parse_mode,
                    external_attempt_budget=remaining_attempts,
                )
            )
        except Exception as retry_error:
            visual_retry_error = type(retry_error).__name__

    selected = max(candidates, key=_candidate_score)
    _attach_processing_trace(
        selected,
        candidates,
        visual_retry_error=visual_retry_error,
        external_attempt_limit=external_attempt_limit,
    )
    return selected


def run_job(
    job_id: str,
    pdf_bytes: bytes,
    filename: str,
    store: JobStore,
    force_ocr: bool = False,
    parse_mode: str = "auto",
) -> None:
    store.set_status(job_id, "processing")
    try:
        selected = analyze_pdf(
            pdf_bytes,
            filename,
            force_ocr=force_ocr,
            parse_mode=parse_mode,
            store=store,
            job_id=job_id,
        )
        _store_candidate(job_id, selected, store)
    except Exception as e:
        store.set_error(job_id, str(e))
