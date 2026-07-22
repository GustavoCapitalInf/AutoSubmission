from __future__ import annotations
from .rasterize import rasterize_pdf
from .document import StatementMarkdown
from .config import load_settings


def parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 200,
                    model: str | None = None, page_ocr_fn=None) -> StatementMarkdown:
    settings = load_settings(model_override=model)
    if page_ocr_fn is None:
        from .ocr_client import ocr_page
        page_ocr_fn = lambda image: ocr_page(image, settings=settings)
    pages = rasterize_pdf(pdf_bytes, dpi=dpi)
    markdown_pages = [page_ocr_fn(image) for image in pages]
    return StatementMarkdown(source_file=source_file, model=settings.model, pages=markdown_pages)
