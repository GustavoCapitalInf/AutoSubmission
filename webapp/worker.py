from __future__ import annotations
from dataclasses import asdict

from analysis.pipeline import Report, analyze_markdown
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
        "model_used": report.model_used,
        "escalated": report.escalated,
    }


def run_job(job_id: str, pdf_bytes: bytes, filename: str, store: JobStore, force_ocr: bool = False) -> None:
    store.set_status(job_id, "processing")
    try:
        store.set_stage(job_id, "reading_visual_ocr" if force_ocr else "reading")
        doc = parse_statement(
            pdf_bytes, source_file=filename,
            on_page_delta=lambda page, chunk: store.append_page_live(job_id, page, chunk),
            on_page_replace=lambda page, text: store.set_page_live(job_id, page, text),
            force_ocr=force_ocr,
        )
        store.set_stage(job_id, "analyzing", doc.model)
        markdown = doc.to_markdown()
        html = markdown_to_html(markdown, title=filename)
        analysis = None
        analysis_error = None
        try:
            analysis = report_to_json(analyze_markdown(markdown))
        except Exception as e:
            analysis_error = str(e)
        store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
    except Exception as e:
        store.set_error(job_id, str(e))
