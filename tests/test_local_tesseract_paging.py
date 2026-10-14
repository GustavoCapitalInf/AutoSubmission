"""The local Tesseract rung reads one page at a time (audit 2026-10-13: INTAKE-1, BE-3).

* Memory: the rung renders the document in bounded page ranges into files and decodes one page at a time, instead of
  holding every page of the whole document in memory before the first page is read. The pixels Tesseract reads are
  unchanged: the PNG handed to Tesseract for every page is byte-identical to the one the whole-document raster
  (`ocr.rasterize.rasterize_pdf`, the rung's former input) produces.
* A short render (fewer pages than the document has, or other pages than asked for) raises `LocalOcrIncomplete`:
  never a short read and never `None` (which the artifact cache would keep for these bytes).

Every PDF here is fabricated (SAMPLE pages carrying a page number and noise); Tesseract is stubbed so the tests read
the exact PNG bytes the rung hands over. The tests that render need Poppler and skip without it.
"""
from __future__ import annotations

import hashlib
import io
import random
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import ocr.local_tesseract as rung
from ocr.rasterize import pdf_page_count, rasterize_pdf


def _fabricated_scan(pages: int, *, size=(600, 800), seed: int = 7) -> bytes:
    """An image-only PDF: each page a different SAMPLE picture (page number, bars, noise), 200 dpi."""
    rng = random.Random(seed)
    images = []
    for number in range(1, pages + 1):
        image = Image.new("RGB", size, "white")
        draw = ImageDraw.Draw(image)
        draw.text((40, 40), f"SAMPLE STATEMENT PAGE {number} OF {pages}", fill="black")
        for row in range(number % 7 + 3):
            y = 120 + row * 60
            draw.rectangle((40, y, 40 + rng.randrange(100, size[0] - 80), y + 20), fill="black")
        for _ in range(400):
            image.putpixel((rng.randrange(size[0]), rng.randrange(size[1])), (128, 128, 128))
        images.append(image)
    buffer = io.BytesIO()
    images[0].save(buffer, "PDF", resolution=200.0, save_all=True, append_images=images[1:])
    return buffer.getvalue()


def _poppler_or_skip() -> None:
    try:
        pdf_page_count(_fabricated_scan(1))
    except Exception:
        pytest.skip("Poppler (pdfinfo/pdftoppm) is not available")


def _oracle_png_digests(pdf_bytes: bytes) -> list[str]:
    """The rung's former input, page by page: the whole-document raster, each page saved as PNG."""
    digests = []
    with tempfile.TemporaryDirectory() as tmp:
        for index, image in enumerate(rasterize_pdf(pdf_bytes, dpi=200), start=1):
            path = Path(tmp) / f"page_{index}.png"
            image.save(path)
            digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
    return digests


class _StubTesseract:
    """Answers `tesseract <png> <out_base> --psm 6` in-process: the page text is the PNG's sha256 (repeated past the
    rung's 200-character floor). Records what was asked, how many PPM files were on disk at that moment, and the
    timeout each call carried. `fail` maps a 1-based call number to an exception (or a return code) for that call."""

    def __init__(self, fail: dict | None = None) -> None:
        self.calls: list[list[str]] = []
        self.timeouts: list[float | None] = []
        self.ppm_on_disk: list[int] = []
        self.fail = fail or {}
        self._real = subprocess.run

    def __call__(self, cmd, *args, **kwargs):
        if not (isinstance(cmd, list) and cmd and cmd[0] == "tesseract" and "--psm" in cmd):
            return self._real(cmd, *args, **kwargs)
        self.calls.append(list(cmd))
        self.timeouts.append(kwargs.get("timeout"))
        png = Path(cmd[1])
        self.ppm_on_disk.append(sum(1 for _ in png.parent.rglob("*.ppm")))
        failure = self.fail.get(len(self.calls))
        if isinstance(failure, BaseException):
            raise failure
        if isinstance(failure, int):
            raise subprocess.CalledProcessError(failure, cmd)
        digest = hashlib.sha256(png.read_bytes()).hexdigest()
        Path(cmd[2] + ".txt").write_text((digest + "\n") * 4, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0)


@pytest.fixture
def stub(monkeypatch):
    tesseract = _StubTesseract()
    monkeypatch.setattr(rung.subprocess, "run", tesseract)
    real_which = rung.shutil.which
    monkeypatch.setattr(rung.shutil, "which", lambda name, *a, **k: "tesseract" if name == "tesseract"
                        else real_which(name, *a, **k))
    return tesseract


def _page_digests(document) -> list[str]:
    return [page.split()[0] for page in document.pages]


# ---------------------------------------------------------------------------------------------------------------------
# Memory: pages in bounded ranges, one decoded page at a time, identical pixels.
# ---------------------------------------------------------------------------------------------------------------------


def test_every_page_tesseract_reads_is_the_png_the_whole_document_raster_made(stub, monkeypatch):
    """11 pages in ranges of 4 (4 + 4 + 3): page order across the ranges and past page 9, and the PNG bytes of every
    page, equal the whole-document raster the rung used before."""
    _poppler_or_skip()
    monkeypatch.setattr(rung, "RASTER_CHUNK_PAGES", 4)
    pdf_bytes = _fabricated_scan(11)
    document = rung.parse_local_tesseract(pdf_bytes, source_file="sample.pdf")
    assert document is not None
    assert document.model == "local-tesseract-ocr"
    assert _page_digests(document) == _oracle_png_digests(pdf_bytes)
    assert [Path(call[1]).name for call in stub.calls] == [f"page_{n}.png" for n in range(1, 12)]
    assert [call[3:] for call in stub.calls] == [["--psm", "6"]] * 11


def test_the_default_range_reads_the_same_pages(stub):
    _poppler_or_skip()
    pdf_bytes = _fabricated_scan(10)
    document = rung.parse_local_tesseract(pdf_bytes, source_file="sample.pdf")
    assert _page_digests(document) == _oracle_png_digests(pdf_bytes)


def test_pages_are_rendered_in_bounded_ranges_and_decoded_one_at_a_time(stub, monkeypatch):
    _poppler_or_skip()
    monkeypatch.setattr(rung, "RASTER_CHUNK_PAGES", 3)
    ranges = []
    real_render = rung.rasterize_pages_to_files

    def recording_render(pdf_path, output_folder, *, first_page, last_page, **kwargs):
        ranges.append((first_page, last_page))
        return real_render(pdf_path, output_folder, first_page=first_page, last_page=last_page, **kwargs)

    open_now = {"count": 0, "peak": 0}
    real_open = rung.Image.open

    class _Counted:
        def __init__(self, image):
            self._image = image
            open_now["count"] += 1
            open_now["peak"] = max(open_now["peak"], open_now["count"])

        def __enter__(self):
            self._image.__enter__()
            return self._image

        def __exit__(self, *exc):
            open_now["count"] -= 1
            return self._image.__exit__(*exc)

    monkeypatch.setattr(rung, "rasterize_pages_to_files", recording_render)
    monkeypatch.setattr(rung.Image, "open", lambda *a, **k: _Counted(real_open(*a, **k)))
    document = rung.parse_local_tesseract(_fabricated_scan(8), source_file="sample.pdf")
    assert len(document.pages) == 8
    assert ranges == [(1, 3), (4, 6), (7, 8)]
    assert open_now == {"count": 0, "peak": 1}
    # Never more raw pages on disk than one range, and each one is gone once its PNG is written.
    assert max(stub.ppm_on_disk) <= 3
    assert stub.ppm_on_disk == [2, 1, 0, 2, 1, 0, 1, 0]


def test_the_rung_no_longer_renders_the_whole_document_into_memory(stub, monkeypatch):
    _poppler_or_skip()
    monkeypatch.setattr(rung, "rasterize_pdf", lambda *a, **k: pytest.fail("whole-document raster"), raising=False)
    document = rung.parse_local_tesseract(_fabricated_scan(2), source_file="sample.pdf")
    assert len(document.pages) == 2


def test_nothing_is_left_in_the_temporary_folder(stub, monkeypatch, tmp_path):
    _poppler_or_skip()
    monkeypatch.setattr(rung.tempfile, "tempdir", str(tmp_path))
    rung.parse_local_tesseract(_fabricated_scan(3), source_file="sample.pdf")
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------------------------------------------------
# What stays as it was.
# ---------------------------------------------------------------------------------------------------------------------


def test_a_document_that_cannot_be_rendered_reads_as_none_as_before(stub, monkeypatch):
    monkeypatch.setattr(rung, "pdf_page_count_at", lambda *a, **k: (_ for _ in ()).throw(ValueError("broken")))
    assert rung.parse_local_tesseract(b"%PDF-not really", source_file="sample.pdf") is None


def test_a_page_range_that_fails_to_render_reads_as_none_as_before(stub, monkeypatch):
    _poppler_or_skip()

    def broken(*a, **k):
        raise OSError("pdftoppm could not run")

    monkeypatch.setattr(rung, "rasterize_pages_to_files", broken)
    assert rung.parse_local_tesseract(_fabricated_scan(2), source_file="sample.pdf") is None


def test_a_page_tesseract_refuses_reads_as_blank_as_before(stub, monkeypatch):
    """tesseract ran and exited non-zero on one image: that page reads as no text, the others are kept."""
    _poppler_or_skip()
    stub.fail = {2: 1}
    pdf_bytes = _fabricated_scan(3)
    document = rung.parse_local_tesseract(pdf_bytes, source_file="sample.pdf")
    oracle = _oracle_png_digests(pdf_bytes)
    assert document.pages[1] == ""
    assert [document.pages[0].split()[0], document.pages[2].split()[0]] == [oracle[0], oracle[2]]


def test_too_little_text_still_reads_as_none(stub, monkeypatch):
    _poppler_or_skip()
    stub.fail = {1: 1}
    assert rung.parse_local_tesseract(_fabricated_scan(1), source_file="sample.pdf") is None
    assert rung.TEXT_FLOOR_CHARS == 200


def test_no_tesseract_binary_reads_as_none(monkeypatch):
    monkeypatch.setattr(rung.shutil, "which", lambda name, *a, **k: None)
    assert rung.parse_local_tesseract(_fabricated_scan(1), source_file="sample.pdf") is None


# ---------------------------------------------------------------------------------------------------------------------
# A short render refuses the whole read: never a short read, never a None.
# ---------------------------------------------------------------------------------------------------------------------


def test_a_short_render_refuses(stub, monkeypatch):
    _poppler_or_skip()
    real_render = rung.rasterize_pages_to_files

    def short(pdf_path, output_folder, **kwargs):
        return real_render(pdf_path, output_folder, **kwargs)[:-1]

    monkeypatch.setattr(rung, "rasterize_pages_to_files", short)
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(_fabricated_scan(3), source_file="sample.pdf")


def test_a_render_that_names_other_pages_refuses(stub, monkeypatch):
    _poppler_or_skip()
    real_render = rung.rasterize_pages_to_files

    def reversed_pages(pdf_path, output_folder, **kwargs):
        return list(reversed(real_render(pdf_path, output_folder, **kwargs)))

    monkeypatch.setattr(rung, "rasterize_pages_to_files", reversed_pages)
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(_fabricated_scan(3), source_file="sample.pdf")
