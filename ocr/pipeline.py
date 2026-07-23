from __future__ import annotations
from .rasterize import rasterize_pdf
from .document import StatementMarkdown
from .config import load_settings


def parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 200,
                    model: str | None = None, page_ocr_fn=None, on_delta=None) -> StatementMarkdown:
    """Rasterize the PDF and OCR each page into one StatementMarkdown.

    If `on_delta` is given, raw model output streams to it live (with a
    '--- Page N ---' marker before each page) — used by the web UI to show what
    the OCR is reading in real time. `page_ocr_fn` is injectable for tests."""
    settings = load_settings(model_override=model)
    if page_ocr_fn is None:
        from .ocr_client import ocr_page
        page_ocr_fn = lambda image: ocr_page(image, settings=settings, on_delta=on_delta)
    pages = rasterize_pdf(pdf_bytes, dpi=dpi)
    markdown_pages = []
    for i, image in enumerate(pages):
        if on_delta is not None:
            on_delta(f"\n\n--- Page {i + 1} ---\n\n")
        markdown_pages.append(page_ocr_fn(image))
    return StatementMarkdown(source_file=source_file, model=settings.model, pages=markdown_pages)
