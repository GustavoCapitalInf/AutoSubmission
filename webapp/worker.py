from __future__ import annotations
from dataclasses import asdict

from analysis.pipeline import Report, analyze_markdown
from ocr.document import StatementMarkdown
from ocr.local_tesseract import parse_local_tesseract
from ocr.native_text import (
    parse_native_desjardins,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
)
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html
from .jobs import JobStore


def report_to_json(report: Report) -> dict:
    return {
        "statement": report.statement.model_dump(),
        "reconciliation": asdict(report.reconciliation),
        "metrics": asdict(report.metrics),
        "detection": {
            "known_funders": [
                {
                    **{k: v for k, v in asdict(match).items() if k != "transactions"},
                    "transactions": [t.model_dump() for t in match.transactions],
                }
                for match in report.detection.known_funders
            ],
            "recurring_debits": [
                {
                    **{k: v for k, v in asdict(item).items() if k != "transactions"},
                    "transactions": [t.model_dump() for t in item.transactions],
                }
                for item in report.detection.recurring_debits
            ],
        },
        "quality": asdict(report.quality),
        "integrity": asdict(report.integrity),
        "model_used": report.model_used,
        "escalated": report.escalated,
    }


def _native_statement(pdf_bytes: bytes, filename: str) -> StatementMarkdown | None:
    return (
        parse_native_td_canada(pdf_bytes, source_file=filename)
        or parse_native_wells_fargo(pdf_bytes, source_file=filename)
        or parse_native_desjardins(pdf_bytes, source_file=filename)
        or parse_native_pdf_text(pdf_bytes, source_file=filename)
    )


def _local_ocr_statement(pdf_bytes: bytes, filename: str) -> StatementMarkdown | None:
    return parse_local_tesseract(pdf_bytes, source_file=filename)


def _analyze_doc(doc: StatementMarkdown, filename: str, parse_mode: str) -> tuple[str, str, dict | None, str | None]:
    markdown = doc.to_markdown()
    html = markdown_to_html(markdown, title=filename)
    try:
        analysis = report_to_json(analyze_markdown(markdown, parse_mode=parse_mode))
        analysis["parse_mode"] = parse_mode
        return markdown, html, analysis, None
    except Exception as e:
        return markdown, html, None, str(e)


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
        if parse_mode == "deterministic":
            store.set_stage(job_id, "reading")
            doc = _native_statement(pdf_bytes, filename)
            if doc is None:
                store.set_stage(job_id, "reading_local_ocr")
                doc = _local_ocr_statement(pdf_bytes, filename)
            if doc is not None:
                for page, text in enumerate(doc.pages):
                    store.set_page_live(job_id, page, text)
                store.set_stage(job_id, "analyzing", doc.model)
                markdown, html, analysis, analysis_error = _analyze_doc(doc, filename, parse_mode)
                if analysis is not None or not force_ocr:
                    store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
                    return
            elif not force_ocr:
                markdown = (
                    f"<!-- source: {filename} | model: deterministic-native-preflight -->\n\n"
                    "No usable native PDF text was found."
                )
                html = markdown_to_html(markdown, title=filename)
                store.set_result(
                    job_id,
                    markdown,
                    html,
                    None,
                    "native PDF text unavailable or too sparse, and local Tesseract OCR did not produce usable statement text; turn on Force visual OCR to use the OCR service, or use Auto mode",
                    "deterministic-native-preflight",
                )
                return

            store.set_stage(job_id, "reading_visual_ocr")
            doc = parse_statement(
                pdf_bytes, source_file=filename,
                on_page_delta=lambda page, chunk: store.append_page_live(job_id, page, chunk),
                on_page_replace=lambda page, text: store.set_page_live(job_id, page, text),
                force_ocr=True,
            )
            store.set_stage(job_id, "analyzing", doc.model)
            markdown, html, analysis, analysis_error = _analyze_doc(doc, filename, parse_mode)
            store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
            return

        effective_force_ocr = force_ocr and parse_mode != "deterministic"
        doc = None
        if not effective_force_ocr:
            store.set_stage(job_id, "reading")
            doc = _native_statement(pdf_bytes, filename)
            if doc is None:
                store.set_stage(job_id, "reading_local_ocr")
                doc = _local_ocr_statement(pdf_bytes, filename)
            if doc is not None:
                for page, text in enumerate(doc.pages):
                    store.set_page_live(job_id, page, text)
        if doc is None:
            store.set_stage(job_id, "reading_visual_ocr" if effective_force_ocr else "reading")
            doc = parse_statement(
                pdf_bytes, source_file=filename,
                on_page_delta=lambda page, chunk: store.append_page_live(job_id, page, chunk),
                on_page_replace=lambda page, text: store.set_page_live(job_id, page, text),
                force_ocr=effective_force_ocr,
            )
        store.set_stage(job_id, "analyzing", doc.model)
        markdown = doc.to_markdown()
        html = markdown_to_html(markdown, title=filename)
        analysis = None
        analysis_error = None
        try:
            analysis = report_to_json(analyze_markdown(markdown, parse_mode=parse_mode))
            analysis["parse_mode"] = parse_mode
        except Exception as e:
            analysis_error = str(e)
            if parse_mode == "deterministic" and force_ocr and doc.model.startswith("native-"):
                store.set_stage(job_id, "reading_visual_ocr")
                doc = parse_statement(
                    pdf_bytes, source_file=filename,
                    on_page_delta=lambda page, chunk: store.append_page_live(job_id, page, chunk),
                    on_page_replace=lambda page, text: store.set_page_live(job_id, page, text),
                    force_ocr=True,
                )
                store.set_stage(job_id, "analyzing", doc.model)
                markdown = doc.to_markdown()
                html = markdown_to_html(markdown, title=filename)
                try:
                    analysis = report_to_json(analyze_markdown(markdown, parse_mode=parse_mode))
                    analysis["parse_mode"] = parse_mode
                    analysis_error = None
                except Exception as retry_error:
                    analysis_error = f"{analysis_error}; visual OCR retry also failed: {retry_error}"
        store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
    except Exception as e:
        store.set_error(job_id, str(e))
