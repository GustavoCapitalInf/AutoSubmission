"""Page rendering for the vision models: pdfium in-process, model-fit JPEG, hashes, timings.

No PyMuPDF (AGPL) and no subprocess. Nothing is written to disk; page bytes exist only in
memory, as in `ocr/paddle_rung.py`.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Iterable

import pypdfium2 as pdfium
from PIL import Image

from vlm.receipts import sha256_bytes

DEFAULT_LONG_EDGE = 1540
DEFAULT_JPEG_QUALITY = 90
RENDER_VERSION = 1
PDF_MAGIC = b"%PDF"


@dataclass(frozen=True)
class RenderedPage:
    index: int
    width: int
    height: int
    jpeg: bytes
    jpeg_sha256: str
    pixel_sha256: str
    pdf_width_pt: float
    pdf_height_pt: float
    rotation_deg: int
    render_ms: float
    encode_ms: float


def _pdfium_versions() -> tuple[str, str]:
    info = getattr(pdfium, "PDFIUM_INFO", None)
    build = str(getattr(info, "build", "") or "")
    wrapper = getattr(pdfium, "V_PYPDFIUM2", None) or getattr(pdfium, "__version__", None)
    if wrapper is None:
        try:
            import importlib.metadata as md

            wrapper = md.version("pypdfium2")
        except Exception:  # noqa: BLE001 — version is informational
            wrapper = ""
    return str(wrapper), build


def render_settings() -> dict:
    wrapper, build = _pdfium_versions()
    return {
        "render_version": RENDER_VERSION,
        "renderer": "pypdfium2",
        "pypdfium2_version": wrapper,
        "pdfium_version": build,
        "long_edge": DEFAULT_LONG_EDGE,
        "jpeg_quality": DEFAULT_JPEG_QUALITY,
    }


def page_count(pdf_bytes: bytes) -> int:
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        return len(doc)
    finally:
        doc.close()


def _encode(image: Image.Image, quality: int) -> tuple[bytes, str, float]:
    started = time.perf_counter()
    if image.mode != "RGB":
        image = image.convert("RGB")
    pixel_sha = sha256_bytes(image.tobytes())
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, subsampling=0)
    return buffer.getvalue(), pixel_sha, (time.perf_counter() - started) * 1000.0


def _fit(image: Image.Image, long_edge: int) -> Image.Image:
    longest = max(image.width, image.height)
    if longest == long_edge:
        return image
    scale = long_edge / longest
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.LANCZOS)


def render_pages(pdf_bytes: bytes, *, long_edge: int = DEFAULT_LONG_EDGE,
                 quality: int = DEFAULT_JPEG_QUALITY,
                 page_indices: Iterable[int] | None = None) -> list[RenderedPage]:
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        indices = list(range(len(doc))) if page_indices is None else list(page_indices)
        pages: list[RenderedPage] = []
        for index in indices:
            page = doc[index]
            try:
                width_pt, height_pt = page.get_size()
                scale = long_edge / max(width_pt, height_pt)
                started = time.perf_counter()
                image = page.render(scale=scale).to_pil()
                render_ms = (time.perf_counter() - started) * 1000.0
                image = _fit(image, long_edge)
                jpeg, pixel_sha, encode_ms = _encode(image, quality)
                pages.append(RenderedPage(
                    index=index, width=image.width, height=image.height, jpeg=jpeg,
                    jpeg_sha256=sha256_bytes(jpeg), pixel_sha256=pixel_sha,
                    pdf_width_pt=float(width_pt), pdf_height_pt=float(height_pt),
                    rotation_deg=int(page.get_rotation()), render_ms=render_ms, encode_ms=encode_ms,
                ))
            finally:
                page.close()
        return pages
    finally:
        doc.close()


def render_image(raw: bytes, *, long_edge: int = DEFAULT_LONG_EDGE, quality: int = DEFAULT_JPEG_QUALITY,
                 index: int = 0) -> RenderedPage:
    started = time.perf_counter()
    with Image.open(io.BytesIO(raw)) as opened:
        opened.load()
        image = _fit(opened.convert("RGB"), long_edge)
    render_ms = (time.perf_counter() - started) * 1000.0
    jpeg, pixel_sha, encode_ms = _encode(image, quality)
    return RenderedPage(index=index, width=image.width, height=image.height, jpeg=jpeg,
                        jpeg_sha256=sha256_bytes(jpeg), pixel_sha256=pixel_sha, pdf_width_pt=0.0,
                        pdf_height_pt=0.0, rotation_deg=0, render_ms=render_ms, encode_ms=encode_ms)


def render_document(raw: bytes, *, long_edge: int = DEFAULT_LONG_EDGE,
                    quality: int = DEFAULT_JPEG_QUALITY) -> list[RenderedPage]:
    if raw[:4] == PDF_MAGIC:
        return render_pages(raw, long_edge=long_edge, quality=quality)
    return [render_image(raw, long_edge=long_edge, quality=quality)]
