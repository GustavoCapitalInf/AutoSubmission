from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from .rasterize import rasterize_pdf
from .document import StatementMarkdown
from .config import load_settings


def parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 300,
                    model: str | None = None, page_ocr_fn=None,
                    on_page_delta=None, max_workers: int | None = None) -> StatementMarkdown:
    """Rasterize the PDF and OCR its pages into one StatementMarkdown.

    Pages are OCR'd concurrently (up to `max_workers` at a time; defaults to
    Settings.max_workers). vLLM batches concurrent requests on the GPU, so this
    cuts wall-clock time on multi-page statements without changing per-page
    output. Results are always reassembled in page order.

    If `on_page_delta` is given, raw model output streams to it live as
    `on_page_delta(page_index, chunk)` — the web UI joins these per-page buffers
    (in page order) to show what the OCR is reading in real time. `page_ocr_fn`
    is injectable for tests and receives a single page image."""
    settings = load_settings(model_override=model)
    workers = max_workers if max_workers is not None else settings.max_workers

    if page_ocr_fn is None:
        from .ocr_client import ocr_page, _build_client
        client = _build_client(settings)

        def ocr_call(image, page_index):
            cb = None
            if on_page_delta is not None:
                cb = lambda chunk, p=page_index: on_page_delta(p, chunk)
            return ocr_page(image, settings=settings, client=client, on_delta=cb)
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
