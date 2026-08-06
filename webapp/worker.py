from __future__ import annotations
from analysis.pipeline import Report, analyze_markdown
from analysis.serialization import report_to_dict
from ocr.document import StatementMarkdown
from ocr.inspect import DocumentProfile, inspect_pdf
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html
from .artifact_cache import ArtifactCache, cached_analysis, cached_ocr, cached_report
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


def _analyze_doc(
    doc: StatementMarkdown,
    filename: str,
    parse_mode: str,
    cache: ArtifactCache | None = None,
    job_id: str | None = None,
    store: JobStore | None = None,
) -> tuple[str, str, dict | None, str | None]:
    markdown = doc.to_markdown()
    rendered = cached_report(
        markdown,
        compute=lambda: markdown_to_html(markdown, title=filename),
        cache=cache,
        title=filename,
    )
    html = rendered.value
    _note_cache(store, job_id, rendered)
    try:
        analyzed = cached_analysis(
            markdown,
            compute=lambda: report_to_json(analyze_markdown(markdown, parse_mode=parse_mode)),
            cache=cache,
            parse_mode=parse_mode,
        )
        _note_cache(store, job_id, analyzed)
        # Copy before stamping: on a cache hit the payload came straight out
        # of the artifact store, and `parse_mode` is a serving-time annotation
        # rather than part of the cached analysis (it already partitions the
        # analysis cache key).
        analysis = dict(analyzed.value)
        analysis["parse_mode"] = parse_mode
        return markdown, html, analysis, None
    except Exception as e:
        return markdown, html, None, str(e)


def _note_cache(store: JobStore | None, job_id: str | None, result) -> None:
    if store is not None and job_id is not None and result.cached:
        store.record_cache_hit(job_id, result.stage, result.cache_key)


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
) -> StatementMarkdown | None:
    """One intake-ladder run, served from the D-3 artifact cache when these
    exact bytes were already read under these exact settings.

    The capability flags are passed identically to ``parse_statement`` and to
    the cache key — they decide which rung produces the text, so they must
    partition the cache. A cached read replays its pages into the live buffer
    (the ladder's own ``on_page_replace`` contract) so the viewer still fills
    in even though nothing was OCR'd.
    """
    result = cached_ocr(
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
    if result.cached:
        _note_cache(store, job_id, result)
        if result.value is not None:
            for index, page in enumerate(result.value.pages):
                on_replace(index, page)
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
    try:
        profile = inspect_pdf(pdf_bytes)

        def on_stage(rung: str) -> None:
            store.set_stage(job_id, _STAGE_NAMES[rung])

        def on_delta(page: int, chunk: str) -> None:
            store.append_page_live(job_id, page, chunk)

        def on_replace(page: int, text: str) -> None:
            store.set_page_live(job_id, page, text)

        def read(**flags) -> StatementMarkdown | None:
            return _read_document(
                job_id, store, cache, pdf_bytes, filename, profile,
                on_stage=on_stage, on_delta=on_delta, on_replace=on_replace,
                **flags,
            )

        def analyze(doc: StatementMarkdown) -> tuple[str, str, dict | None, str | None]:
            return _analyze_doc(doc, filename, parse_mode, cache, job_id, store)

        if parse_mode == "deterministic":
            # Offline rungs only (native, then tesseract); no visual OCR yet.
            doc = read(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False)
            if doc is not None:
                store.set_stage(job_id, "analyzing", doc.model)
                markdown, html, analysis, analysis_error = analyze(doc)
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

            doc = read(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True)
            store.set_stage(job_id, "analyzing", doc.model)
            markdown, html, analysis, analysis_error = analyze(doc)
            store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
            return

        # Auto mode: the full ladder in one call (force_ocr jumps straight to
        # the visual rung, exactly as before).
        doc = read(force_ocr=force_ocr, allow_local_ocr=True, allow_visual_ocr=True)
        store.set_stage(job_id, "analyzing", doc.model)
        markdown, html, analysis, analysis_error = analyze(doc)
        store.set_result(job_id, markdown, html, analysis, analysis_error, doc.model)
    except Exception as e:
        store.set_error(job_id, str(e))
