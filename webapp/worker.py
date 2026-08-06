from __future__ import annotations
from analysis.pipeline import Report, analyze_markdown
from analysis.serialization import report_to_dict
from ocr.document import StatementMarkdown
from ocr.inspect import inspect_pdf
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html
from .jobs import JobStore


def report_to_json(report: Report) -> dict:
    return report_to_dict(report)


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
    # Persistence (D-1): every set_status/set_stage transition and the final
    # set_result/set_error below write through the JobStore facade into the
    # durable store (webapp/storage.py). Reaching a terminal state also
    # releases the job's in-memory pdf_bytes; afterwards /page and /render
    # serve the PDF from the on-disk content-hash store.
    store.set_status(job_id, "processing")
    try:
        profile = inspect_pdf(pdf_bytes)

        def on_stage(rung: str) -> None:
            store.set_stage(job_id, _STAGE_NAMES[rung])

        def on_delta(page: int, chunk: str) -> None:
            store.append_page_live(job_id, page, chunk)

        def on_replace(page: int, text: str) -> None:
            store.set_page_live(job_id, page, text)

        if parse_mode == "deterministic":
            # Offline rungs only (native, then tesseract); no visual OCR yet.
            doc = parse_statement(
                pdf_bytes, source_file=filename, profile=profile,
                allow_local_ocr=True, allow_visual_ocr=False,
                on_stage=on_stage, on_page_delta=on_delta, on_page_replace=on_replace,
            )
            if doc is not None:
                store.set_stage(job_id, "analyzing", doc.model)
                markdown, html, analysis, analysis_error = _analyze_doc(doc, filename, parse_mode)
                if analysis is not None or not force_ocr:
                    store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
                    return
                # Analysis failed and the operator forced OCR: escalate to the
                # visual rung below (mode policy, not ladder routing).
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

            doc = parse_statement(
                pdf_bytes, source_file=filename, profile=profile, force_ocr=True,
                on_stage=on_stage, on_page_delta=on_delta, on_page_replace=on_replace,
            )
            store.set_stage(job_id, "analyzing", doc.model)
            markdown, html, analysis, analysis_error = _analyze_doc(doc, filename, parse_mode)
            store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
            return

        # Auto mode: the full ladder in one call (force_ocr jumps straight to
        # the visual rung, exactly as before).
        doc = parse_statement(
            pdf_bytes, source_file=filename, profile=profile,
            force_ocr=force_ocr, allow_local_ocr=True,
            on_stage=on_stage, on_page_delta=on_delta, on_page_replace=on_replace,
        )
        store.set_stage(job_id, "analyzing", doc.model)
        markdown, html, analysis, analysis_error = _analyze_doc(doc, filename, parse_mode)
        store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
    except Exception as e:
        store.set_error(job_id, str(e))
