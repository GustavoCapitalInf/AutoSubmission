from __future__ import annotations
import os
import sys
from PIL import Image
from pdf2image import convert_from_bytes, pdfinfo_from_bytes

POPPLER_PATH = (
    None if sys.platform != "win32"
    else os.environ.get("POPPLER_PATH", r"C:\poppler-24.08.0\Library\bin")
)

def rasterize_pdf(pdf_bytes: bytes, dpi: int = 300) -> list[Image.Image]:
    """Rasterize every page of a PDF to a PIL image at the given DPI."""
    return convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)


def pdf_page_count(pdf_bytes: bytes) -> int:
    """Return the number of pages without rasterizing (uses pdfinfo)."""
    return pdfinfo_from_bytes(pdf_bytes, poppler_path=POPPLER_PATH)["Pages"]


def rasterize_page(pdf_bytes: bytes, page_index: int, dpi: int = 100) -> Image.Image:
    """Rasterize a single 0-indexed page to a PIL image (for on-demand display)."""
    n = page_index + 1
    return convert_from_bytes(
        pdf_bytes, dpi=dpi, first_page=n, last_page=n, poppler_path=POPPLER_PATH
    )[0]
