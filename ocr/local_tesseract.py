from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .document import StatementMarkdown
from .rasterize import pdf_page_count_at, rasterize_pages_to_files

#: The rung's document floor: a read with fewer non-blank characters than this, over all pages, is no read (None).
#: `ocr/escalation.py::CHAR_FLOOR` duplicates it by reference; change both or neither.
TEXT_FLOOR_CHARS = 200

#: Pages one pdftoppm call renders (audit 2026-10-13, INTAKE-1/BE-3). The rung used to render the WHOLE document
#: into memory before it read page 1 (about 22 MB per 200 dpi letter page, linear in the page count, within the
#: upload limit's 500 pages). Now a range of this many pages goes to PPM files in the rung's temporary folder and
#: each page is decoded, saved as the same PNG, deleted and read before the next: memory holds one decoded page, and
#: temporary disk at most this many raw pages (about 11 MB each). Measured on a 26-page fabricated scan: a range of
#: 8 costs about 0.1 s per page over one call for the whole document, one call per page about 0.5 s.
RASTER_CHUNK_PAGES = 8

_PPM_PAGE = re.compile(r"-(\d+)\.ppm\Z")


class LocalOcrIncomplete(RuntimeError):
    """The rung could not read every page for a reason that is not a property of the pages: fewer rendered pages
    than the document has.

    Raised, never answered with a partial read (the missing pages would simply be absent from what is analysed and
    published) or with None (`webapp.artifact_cache.cached_ocr` keeps a None for these bytes and settings, so a
    passing host problem would become a permanent "no text"): an exception leaves the cache untouched, the worker
    marks the job failed in its reading stage, and the next upload of the same bytes reads afresh. The message is
    fixed text: it names no file, page content or path."""


def _check_rendered(paths: list[str], first: int, last: int) -> None:
    """Fail closed unless pdftoppm wrote exactly the pages asked for, in order (pdf2image ignores its exit status, so
    a full disk or a crash would otherwise shorten the read silently)."""
    numbers = []
    for path in paths:
        match = _PPM_PAGE.search(os.path.basename(path))
        numbers.append(int(match.group(1)) if match else None)
    if numbers != list(range(first, last + 1)):
        raise LocalOcrIncomplete("pdftoppm did not render every page asked for")


def parse_local_tesseract(pdf_bytes: bytes, source_file: str = "", *, dpi: int = 200) -> StatementMarkdown | None:
    """OCR an image-only PDF with local Tesseract.

    This is intentionally deterministic/local and does not call the visual LLM OCR
    service. It is used as a fallback for scanned statements that have no usable
    native PDF text.

    Pages are rendered RASTER_CHUNK_PAGES at a time into this call's temporary folder and read one at a time, each
    raw page deleted once its PNG is written (audit 2026-10-13, INTAKE-1/BE-3): the PNG tesseract reads for every page
    is byte-identical to the whole-document raster's. None, as before: no tesseract binary, a document Poppler cannot
    render, or fewer than TEXT_FLOOR_CHARS characters read. `LocalOcrIncomplete`: pdftoppm rendered fewer pages than
    the document has; never a short read.
    """
    if shutil.which("tesseract") is None:
        return None
    pages: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        pdf_path = tmpdir / "document.pdf"
        try:
            pdf_path.write_bytes(pdf_bytes)
            page_count = pdf_page_count_at(pdf_path)
        except Exception:
            return None
        for first in range(1, page_count + 1, RASTER_CHUNK_PAGES):
            last = min(first + RASTER_CHUNK_PAGES - 1, page_count)
            raster_dir = tmpdir / f"raster_{first}"
            try:
                raster_dir.mkdir()
                ppm_paths = rasterize_pages_to_files(pdf_path, raster_dir, first_page=first, last_page=last, dpi=dpi)
            except Exception:
                return None
            _check_rendered(ppm_paths, first, last)
            for idx, ppm_path in enumerate(ppm_paths, start=first):
                image_path = tmpdir / f"page_{idx}.png"
                out_base = tmpdir / f"page_{idx}"
                try:
                    opened = Image.open(ppm_path)
                except Exception:
                    return None
                with opened as image:  # closed before the raw page is deleted (Windows refuses an open file)
                    image.save(image_path)  # outside the try, as before: a save error propagates
                os.remove(ppm_path)
                try:
                    subprocess.run(
                        ["tesseract", str(image_path), str(out_base), "--psm", "6"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    pages.append(out_base.with_suffix(".txt").read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    pages.append("")
                image_path.unlink()
                out_base.with_suffix(".txt").unlink(missing_ok=True)
            raster_dir.rmdir()
    if sum(len(page.strip()) for page in pages) < TEXT_FLOOR_CHARS:
        return None
    return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=pages)
