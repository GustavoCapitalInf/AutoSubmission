from __future__ import annotations
import os
import sys
from PIL import Image
from pdf2image import convert_from_bytes, convert_from_path, pdfinfo_from_bytes, pdfinfo_from_path

POPPLER_PATH = (
    None if sys.platform != "win32"
    else os.environ.get("POPPLER_PATH", r"C:\poppler-24.08.0\Library\bin")
)

#: Bump when this module's rasterization output changes for unchanged inputs
#: (a different resampling filter, a different Poppler invocation, a changed
#: default DPI-independent behavior). It is OCR cache-key material
#: (`webapp/artifact_cache.py::ocr_settings_key`, P20-ARTIFACTS/F-6): the
#: offline local-Tesseract rung and the visual rung both rasterize through
#: this module before OCR'ing, so a silent rasterization change would
#: otherwise serve a stale artifact for unchanged settings. v1 is the value
#: at Phase 2.0 (P20-ARTIFACTS) — no rasterization change; the constant is
#: introduced so the key HAS a version to bump the day one lands.
#: v2 (P22-IDENTITY closure-2, review F-1): the raster renders the CROPBOX
#: (`use_cropbox=True`), not Poppler's default MediaBox, so a Paddle raster
#: and the native display frame (`page.rect`, the CropBox) share one origin
#: and one size — on a page whose CropBox is shifted from its MediaBox the
#: native word boxes were offset from the raster's ink by the CropBox origin
#: and the frame disagreed with the raster. Every OCR partition at v5+ keys
#: on this value; no run of record holds a Paddle artifact yet, so the only
#: partitions that ever rasterised a CropBox≠MediaBox page are Tesseract
#: reads of scans (measured at the closure: see the cell's W3) and the
#: research partitions of Phase 2.3 — the OCR cache is rebuilt at the
#: train's cold run regardless (schema 3).
RASTER_VERSION = 2

def rasterize_pdf(pdf_bytes: bytes, dpi: int = 300) -> list[Image.Image]:
    """Rasterize every page of a PDF to a PIL image at the given DPI.

    The CROPBOX is rendered (`use_cropbox=True`; RASTER_VERSION 2) — what a
    viewer shows and what PyMuPDF's `page.rect` / word coordinates are
    relative to — so a raster's pixel frame and the native display frame
    describe the same rectangle."""
    return convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH, use_cropbox=True)


def rasterize_pages_to_files(
    pdf_path: str | os.PathLike, output_folder: str | os.PathLike, *,
    first_page: int, last_page: int, dpi: int, timeout: float | None = None,
) -> list[str]:
    """Rasterize pages `first_page`..`last_page` (1-based, inclusive) of the PDF at `pdf_path` into PPM files in
    `output_folder`, returning their paths in page order.

    The same Poppler call as `rasterize_pdf` (`pdftoppm -r <dpi> -cropbox -f <first> -l <last>`; RASTER_VERSION 2);
    only the output target differs: files named `<prefix>-<page>.ppm` instead of one stdout stream holding every
    page, so a caller can decode and release one page at a time (audit 2026-10-13, INTAKE-1/BE-3). The pixels are
    the same, so RASTER_VERSION does not move. `timeout` (seconds) kills a pdftoppm that runs past it and raises
    pdf2image's `PDFPopplerTimeoutError`. pdf2image does not read pdftoppm's exit status, so a caller must check that
    it got the pages it asked for."""
    return convert_from_path(
        os.fspath(pdf_path), dpi=dpi, first_page=first_page, last_page=last_page,
        output_folder=os.fspath(output_folder), paths_only=True, poppler_path=POPPLER_PATH,
        use_cropbox=True, timeout=timeout,
    )


def pdf_page_count_at(pdf_path: str | os.PathLike, *, timeout: float | None = None) -> int:
    """The page count of the PDF at `pdf_path` (pdfinfo), killed past `timeout` seconds."""
    return pdfinfo_from_path(os.fspath(pdf_path), poppler_path=POPPLER_PATH, timeout=timeout)["Pages"]


def pdf_page_count(pdf_bytes: bytes) -> int:
    """Return the number of pages without rasterizing (uses pdfinfo)."""
    return pdfinfo_from_bytes(pdf_bytes, poppler_path=POPPLER_PATH)["Pages"]


def rasterize_page(pdf_bytes: bytes, page_index: int, dpi: int = 100, timeout: float = 120) -> Image.Image:
    """Rasterize a single 0-indexed page to a PIL image (for on-demand display). `timeout` kills a `pdftoppm`
    that runs past it (pdf2image's `PDFPopplerTimeoutError`) so a hung page cannot pin the server's thread."""
    n = page_index + 1
    return convert_from_bytes(
        pdf_bytes, dpi=dpi, first_page=n, last_page=n, poppler_path=POPPLER_PATH, use_cropbox=True,
        timeout=timeout,
    )[0]
