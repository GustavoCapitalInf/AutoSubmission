from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .document import StatementMarkdown
from .rasterize import rasterize_pdf


def parse_local_tesseract(pdf_bytes: bytes, source_file: str = "", *, dpi: int = 200) -> StatementMarkdown | None:
    """OCR an image-only PDF with local Tesseract.

    This is intentionally deterministic/local and does not call the visual LLM OCR
    service. It is used as a fallback for scanned statements that have no usable
    native PDF text.
    """
    if shutil.which("tesseract") is None:
        return None
    try:
        images = rasterize_pdf(pdf_bytes, dpi=dpi)
    except Exception:
        return None
    pages: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for idx, image in enumerate(images, start=1):
            image_path = tmpdir / f"page_{idx}.png"
            out_base = tmpdir / f"page_{idx}"
            image.save(image_path)
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
    if sum(len(page.strip()) for page in pages) < 200:
        return None
    return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=pages)
