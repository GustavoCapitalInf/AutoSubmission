from __future__ import annotations
import os
import sys
from PIL import Image
from pdf2image import convert_from_bytes

POPPLER_PATH = (
    None if sys.platform != "win32"
    else os.environ.get("POPPLER_PATH", r"C:\poppler-24.08.0\Library\bin")
)

def rasterize_pdf(pdf_bytes: bytes, dpi: int = 300) -> list[Image.Image]:
    """Rasterize every page of a PDF to a PIL image at the given DPI."""
    return convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
