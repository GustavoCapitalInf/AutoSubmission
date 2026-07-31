from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from .rasterize import rasterize_pdf, rasterize_page
from .document import StatementMarkdown
from .config import load_settings
from .native_text import (
    parse_native_desjardins,
    parse_native_navy_federal,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
)


def parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 300,
                    model: str | None = None, page_ocr_fn=None,
                    on_page_delta=None, max_workers: int | None = None,
                    fallback_dpi: int | None = 250, on_page_replace=None,
                    force_ocr: bool = False) -> StatementMarkdown:
    """Rasterize the PDF and OCR its pages into one StatementMarkdown.

    Pages are OCR'd concurrently (up to `max_workers` at a time; defaults to
    Settings.max_workers). vLLM batches concurrent requests on the GPU, so this
    cuts wall-clock time on multi-page statements without changing per-page
    output. Results are always reassembled in page order.

    `fallback_dpi` (default 250) guards against a DPI-specific table
    mis-segmentation: if a page comes back with the tell-tale orphan amount-only
    table, it is re-OCR'd once at the fallback DPI and the cleaner read is kept.
    Set to None to disable. The default `dpi` of 300 is tuned for dense
    check-detail tables; the lower fallback recovers wide-gap description tables
    (e.g. Truist) that 300 splits.

    If `on_page_delta` is given, raw model output streams to it live as
    `on_page_delta(page_index, chunk)` — the web UI joins these per-page buffers
    (in page order) to show what the OCR is reading in real time. `page_ocr_fn`
    is injectable for tests and receives a single page image."""
    if page_ocr_fn is None and not force_ocr:
        native = parse_native_navy_federal(pdf_bytes, source_file=source_file)
        if native is None:
            native = parse_native_td_canada(pdf_bytes, source_file=source_file)
        if native is None:
            native = parse_native_wells_fargo(pdf_bytes, source_file=source_file)
        if native is None:
            native = parse_native_desjardins(pdf_bytes, source_file=source_file)
        if native is None:
            native = parse_native_pdf_text(pdf_bytes, source_file=source_file)
        if native is not None:
            if on_page_replace is not None:
                for i, page in enumerate(native.pages):
                    on_page_replace(i, page)
            return native

    settings = load_settings(model_override=model)
    workers = max_workers if max_workers is not None else settings.max_workers

    if page_ocr_fn is None:
        from .ocr_client import (ocr_page, _build_client, looks_missegmented,
                                 looks_truncated_td, recover_truncated_td_page)
        client = _build_client(settings)

        def use_alt(page_index, alt):
            # A fallback/recovery re-OCR happened off-stream, so the live buffer the
            # web UI renders still holds the original (broken) read — overwrite it.
            if on_page_replace is not None:
                on_page_replace(page_index, alt)
            return alt

        def ocr_call(image, page_index):
            cb = None
            if on_page_delta is not None:
                cb = lambda chunk, p=page_index: on_page_delta(p, chunk)
            out = ocr_page(image, settings=settings, client=client, on_delta=cb)
            # Re-OCR a mis-segmented page once at the fallback DPI (no streaming);
            # keep it only if it actually resolves the split.
            if (fallback_dpi and fallback_dpi != dpi and looks_missegmented(out)):
                alt_img = rasterize_page(pdf_bytes, page_index, dpi=fallback_dpi)
                alt = ocr_page(alt_img, settings=settings, client=client)
                if not looks_missegmented(alt):
                    return use_alt(page_index, alt)
            # A truncated TD page-1 (the QR-code refusal derails generation) reads
            # fully under some render variant — try them and keep a recovered read.
            if page_index == 0 and looks_truncated_td(out):
                alt = recover_truncated_td_page(pdf_bytes, page_index,
                                                settings=settings, client=client)
                if alt is not None:
                    return use_alt(page_index, alt)
            return out
    else:
        def ocr_call(image, page_index):
            return page_ocr_fn(image)

    pages = rasterize_pdf(pdf_bytes, dpi=dpi)
    results: list[str | None] = [None] * len(pages)

    if workers <= 1 or len(pages) <= 1:
        for i, image in enumerate(pages):
            results[i] = ocr_call(image, i)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(ocr_call, image, i): i for i, image in enumerate(pages)}
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result()

    return StatementMarkdown(source_file=source_file, model=settings.model,
                             pages=[r or "" for r in results])
