from __future__ import annotations
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html
from .jobs import JobStore


def run_job(job_id: str, pdf_bytes: bytes, filename: str, store: JobStore) -> None:
    store.set_status(job_id, "processing")
    try:
        doc = parse_statement(
            pdf_bytes, source_file=filename,
            on_page_delta=lambda page, chunk: store.append_page_live(job_id, page, chunk),
            on_page_replace=lambda page, text: store.set_page_live(job_id, page, text),
        )
        markdown = doc.to_markdown()
        html = markdown_to_html(markdown, title=filename)
        store.set_result(job_id, markdown, html)
    except Exception as e:
        store.set_error(job_id, str(e))
