"""The local Tesseract rung reads one page at a time and fails closed on a host failure (audit 2026-10-13: INTAKE-1,
BE-3, REL-01).

* Memory: the rung renders the document in bounded page ranges into files and decodes one page at a time, instead of
  holding every page of the whole document in memory before the first page is read. The pixels Tesseract reads are
  unchanged: the PNG handed to Tesseract for every page is byte-identical to the one the whole-document raster
  (`ocr.rasterize.rasterize_pdf`, the rung's former input) produces.
* Time: every pdftoppm and tesseract process has a time limit and the document a deadline. A limit passed, a short
  render, a tesseract killed by a signal, or a tesseract that cannot be started raises `LocalOcrIncomplete`: never a
  partial read (a blank page beside read ones) and never `None` (which the artifact cache would keep for these bytes).
* Host failures in the raster steps (final review of the audit, finding 1): a full, failing or read-only disk, a disk
  quota, or memory run out while the PDF is written and counted, a page range is rendered, or a rendered page is
  opened and saved raises `LocalOcrIncomplete` too. Only Poppler's refusal of the document itself still reads as None.

Every PDF here is fabricated (SAMPLE pages carrying a page number and noise); Tesseract is stubbed so the tests read
the exact PNG bytes the rung hands over. The tests that render need Poppler and skip without it.
"""
from __future__ import annotations

import errno
import hashlib
import io
import random
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw, UnidentifiedImageError
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError

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
# Host failures refuse the whole read: never a partial read, never a None.
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


def test_a_tesseract_past_its_time_limit_refuses_the_whole_read(stub):
    _poppler_or_skip()
    stub.fail = {2: subprocess.TimeoutExpired(["tesseract"], 1.0)}
    with pytest.raises(rung.LocalOcrTimeout):
        rung.parse_local_tesseract(_fabricated_scan(3), source_file="sample.pdf")
    assert issubclass(rung.LocalOcrTimeout, rung.LocalOcrIncomplete)


def test_every_tesseract_call_carries_a_time_limit(stub):
    _poppler_or_skip()
    rung.parse_local_tesseract(_fabricated_scan(2), source_file="sample.pdf")
    assert stub.timeouts and all(0 < limit <= rung.STEP_TIMEOUT_SECONDS for limit in stub.timeouts)


def test_a_pdftoppm_past_its_time_limit_refuses_the_whole_read(stub, monkeypatch):
    _poppler_or_skip()
    from pdf2image.exceptions import PDFPopplerTimeoutError

    seen = []

    def slow(pdf_path, output_folder, *, timeout=None, **kwargs):
        seen.append(timeout)
        raise PDFPopplerTimeoutError("Run poppler timeout.")

    monkeypatch.setattr(rung, "rasterize_pages_to_files", slow)
    with pytest.raises(rung.LocalOcrTimeout):
        rung.parse_local_tesseract(_fabricated_scan(2), source_file="sample.pdf")
    assert seen and 0 < seen[0] <= rung.STEP_TIMEOUT_SECONDS


def test_the_document_deadline_bounds_every_step_and_refuses_past_it(stub, monkeypatch):
    _poppler_or_skip()
    clock = {"now": 1000.0}
    monkeypatch.setattr(rung, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
    monkeypatch.setattr(rung, "DOCUMENT_DEADLINE_SECONDS", 150.0)
    real_stub = _StubTesseract.__call__

    def advancing(self, cmd, *args, **kwargs):
        result = real_stub(self, cmd, *args, **kwargs)
        clock["now"] += 100.0  # every page takes 100 s of the 150 s deadline
        return result

    monkeypatch.setattr(_StubTesseract, "__call__", advancing)
    with pytest.raises(rung.LocalOcrTimeout):
        rung.parse_local_tesseract(_fabricated_scan(3), source_file="sample.pdf")
    # page 1 had the full step limit, page 2 only what was left of the deadline, page 3 never ran
    assert stub.timeouts == [rung.STEP_TIMEOUT_SECONDS, 50.0]


def test_a_tesseract_killed_by_a_signal_refuses(stub):
    """A negative return code is a POSIX signal (the kernel's OOM killer sends SIGKILL): the host failed, not the page."""
    _poppler_or_skip()
    stub.fail = {1: -9}
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(_fabricated_scan(2), source_file="sample.pdf")


def test_a_tesseract_that_cannot_start_refuses(stub):
    _poppler_or_skip()
    stub.fail = {1: OSError("cannot start")}
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(_fabricated_scan(2), source_file="sample.pdf")


def test_the_refusal_names_nothing_from_the_document(stub):
    _poppler_or_skip()
    stub.fail = {1: subprocess.TimeoutExpired(["tesseract", "SAMPLE-SECRET"], 1.0)}
    with pytest.raises(rung.LocalOcrTimeout) as caught:
        rung.parse_local_tesseract(_fabricated_scan(1), source_file="SAMPLE-SECRET.pdf")
    assert "SAMPLE-SECRET" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_a_refused_read_is_never_cached_and_a_later_read_succeeds(stub, tmp_path):
    """Through the artifact cache the worker reads with: a timed-out read leaves no entry (None would have been kept),
    and the next read of the same bytes reads every page."""
    _poppler_or_skip()
    from webapp.artifact_cache import ArtifactCache, cached_ocr
    from webapp.storage import Storage

    cache = ArtifactCache(Storage(tmp_path / "data"))
    pdf_bytes = _fabricated_scan(3)

    def read():
        return cached_ocr(pdf_bytes, compute=lambda: rung.parse_local_tesseract(pdf_bytes, source_file="s.pdf"),
                          cache=cache, source_file="s.pdf", force_ocr=False, allow_local_ocr=True,
                          allow_visual_ocr=False)

    stub.fail = {2: subprocess.TimeoutExpired(["tesseract"], 1.0)}
    with pytest.raises(rung.LocalOcrTimeout):
        read()
    assert cache.storage.cache_entries("ocr") == []
    stub.fail = {}
    result = read()
    assert result.cached is False
    assert _page_digests(result.value) == _oracle_png_digests(pdf_bytes)
    assert read().cached is True


# ---------------------------------------------------------------------------------------------------------------------
# Host failures in the raster steps refuse the read too (final review of the audit, finding 1). Before, every
# exception there read as None, which the artifact cache keeps: a full disk made "no text" permanent for those bytes.
# Only Poppler's refusal of the document itself still reads as None.
# ---------------------------------------------------------------------------------------------------------------------

_HOST_OS_ERRORS = [
    pytest.param(lambda: OSError(errno.ENOSPC, "No space left on device"), id="ENOSPC"),
    pytest.param(lambda: OSError(errno.EIO, "Input/output error"), id="EIO"),
    pytest.param(lambda: OSError(errno.EROFS, "Read-only file system"), id="EROFS"),
    pytest.param(lambda: OSError(errno.EDQUOT, "Disk quota exceeded"), id="EDQUOT"),
    pytest.param(lambda: OSError(errno.ENOMEM, "Cannot allocate memory"), id="ENOMEM"),
    pytest.param(lambda: OSError(errno.EAGAIN, "Resource temporarily unavailable"), id="EAGAIN"),
    pytest.param(lambda: OSError(errno.EMFILE, "Too many open files"), id="EMFILE"),
    pytest.param(lambda: OSError(errno.ENFILE, "Too many open files in system"), id="ENFILE"),
    pytest.param(lambda: OSError(errno.EACCES, "Permission denied"), id="EACCES"),
]
_HOST_FAILURES = [*_HOST_OS_ERRORS, pytest.param(MemoryError, id="MemoryError")]


def _raising(make):
    def raise_it(*args, **kwargs):
        raise make()
    return raise_it


def _fake_render(monkeypatch):
    """pdftoppm without Poppler: one tiny grey colour PPM (P6, pdftoppm's own format) per page asked for, named as
    pdftoppm names them, written as raw bytes (so a test may replace PIL's save)."""
    def render(pdf_path, output_folder, *, first_page, last_page, **kwargs):
        paths = []
        for number in range(first_page, last_page + 1):
            path = Path(output_folder) / f"sample-{number}.ppm"
            path.write_bytes(b"P6\n8 8\n255\n" + bytes([128]) * 192)
            paths.append(str(path))
        return paths

    monkeypatch.setattr(rung, "pdf_page_count_at", lambda *a, **k: 2)
    monkeypatch.setattr(rung, "rasterize_pages_to_files", render)


@pytest.mark.parametrize("failure", _HOST_FAILURES)
def test_a_host_failure_while_the_pages_are_counted_refuses(stub, monkeypatch, failure):
    monkeypatch.setattr(rung, "pdf_page_count_at", _raising(failure))
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")
    assert stub.calls == []


@pytest.mark.parametrize("failure", _HOST_OS_ERRORS)
def test_a_host_failure_pdfinfo_reports_as_not_installed_refuses(stub, monkeypatch, failure):
    """pdf2image's pdfinfo turns every OSError of its own process start (a fork refused for memory, say) into
    PDFInfoNotInstalledError; the host's error is the exception it was raised during."""
    def count(*args, **kwargs):
        try:
            raise failure()
        except OSError:
            raise PDFInfoNotInstalledError("Unable to get page count. Is poppler installed and in PATH?")

    monkeypatch.setattr(rung, "pdf_page_count_at", count)
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")


def test_writing_the_pdf_to_a_full_disk_refuses(stub, monkeypatch):
    real_write = Path.write_bytes

    def write(self, data):
        if self.name == "document.pdf":
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_write(self, data)

    monkeypatch.setattr(Path, "write_bytes", write)
    monkeypatch.setattr(rung, "pdf_page_count_at", lambda *a, **k: pytest.fail("counted a PDF never written"))
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")


@pytest.mark.parametrize("failure", _HOST_FAILURES)
def test_a_host_failure_while_a_page_range_renders_refuses(stub, monkeypatch, failure):
    monkeypatch.setattr(rung, "pdf_page_count_at", lambda *a, **k: 2)
    monkeypatch.setattr(rung, "rasterize_pages_to_files", _raising(failure))
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")
    assert stub.calls == []


def test_a_raster_folder_on_a_read_only_disk_refuses(stub, monkeypatch):
    _fake_render(monkeypatch)
    real_mkdir = Path.mkdir

    def mkdir(self, *args, **kwargs):
        if self.name.startswith("raster_"):
            raise OSError(errno.EROFS, "Read-only file system")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")


@pytest.mark.parametrize("failure", _HOST_FAILURES)
def test_a_host_failure_while_a_rendered_page_is_opened_refuses(stub, monkeypatch, failure):
    _fake_render(monkeypatch)
    monkeypatch.setattr(rung.Image, "open", _raising(failure))
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")
    assert stub.calls == []


@pytest.mark.parametrize("failure", _HOST_FAILURES)
def test_a_host_failure_while_a_page_is_saved_refuses(stub, monkeypatch, failure):
    _fake_render(monkeypatch)
    monkeypatch.setattr(Image.Image, "save", _raising(failure))
    with pytest.raises(rung.LocalOcrIncomplete):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")
    assert stub.calls == []


def test_the_fake_render_reads_every_page_when_the_host_is_healthy(stub, monkeypatch):
    """The control for the four tests above: the same stand-ins, nothing failing, two pages read."""
    _fake_render(monkeypatch)
    stub_text = "SAMPLE TEXT " * 30
    monkeypatch.setattr(rung, "_read_page", lambda *a, **k: stub_text)
    document = rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")
    assert document is not None and document.pages == [stub_text, stub_text]


def test_a_save_error_that_is_not_the_host_still_propagates_as_before(stub, monkeypatch):
    _fake_render(monkeypatch)
    monkeypatch.setattr(Image.Image, "save", _raising(lambda: ValueError("unknown file extension")))
    with pytest.raises(ValueError):
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf")


def _wrapped_missing_pdfinfo():
    try:
        raise FileNotFoundError(errno.ENOENT, "No such file or directory")
    except OSError:
        try:
            raise PDFInfoNotInstalledError("Unable to get page count. Is poppler installed and in PATH?")
        except PDFInfoNotInstalledError as wrapped:
            return wrapped


@pytest.mark.parametrize("refusal", [
    pytest.param(lambda: PDFPageCountError("Unable to get page count.\nSyntax Error: SAMPLE"), id="page-count"),
    pytest.param(lambda: ValueError("broken"), id="value-error"),
    pytest.param(lambda: OSError("pdfinfo could not read it"), id="oserror-without-errno"),
    pytest.param(_wrapped_missing_pdfinfo, id="pdfinfo-not-found"),
])
def test_poppler_refusing_the_document_while_counting_still_reads_as_none(stub, monkeypatch, refusal):
    monkeypatch.setattr(rung, "pdf_page_count_at", _raising(refusal))
    assert rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf") is None


@pytest.mark.parametrize("refusal", [
    pytest.param(lambda: PDFSyntaxError("Syntax Error: SAMPLE"), id="syntax-error"),
    pytest.param(lambda: ValueError("broken"), id="value-error"),
    pytest.param(lambda: OSError("pdftoppm could not run"), id="oserror-without-errno"),
])
def test_poppler_refusing_a_page_range_still_reads_as_none(stub, monkeypatch, refusal):
    monkeypatch.setattr(rung, "pdf_page_count_at", lambda *a, **k: 2)
    monkeypatch.setattr(rung, "rasterize_pages_to_files", _raising(refusal))
    assert rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf") is None


@pytest.mark.parametrize("refusal", [
    pytest.param(lambda: UnidentifiedImageError("cannot identify image file"), id="not-an-image"),
    pytest.param(lambda: FileNotFoundError(errno.ENOENT, "No such file or directory"), id="no-such-file"),
])
def test_a_rendered_page_pil_cannot_open_still_reads_as_none(stub, monkeypatch, refusal):
    _fake_render(monkeypatch)
    monkeypatch.setattr(rung.Image, "open", _raising(refusal))
    assert rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="sample.pdf") is None


def test_a_host_failure_refusal_names_nothing_from_the_document(stub, monkeypatch):
    monkeypatch.setattr(rung, "pdf_page_count_at", lambda *a, **k: 1)
    monkeypatch.setattr(rung, "rasterize_pages_to_files",
                        _raising(lambda: OSError(errno.ENOSPC, "SAMPLE-SECRET", "SAMPLE-SECRET.pdf")))
    with pytest.raises(rung.LocalOcrIncomplete) as caught:
        rung.parse_local_tesseract(b"%PDF-SAMPLE", source_file="SAMPLE-SECRET.pdf")
    assert type(caught.value) is rung.LocalOcrIncomplete  # a host failure, not a time limit
    assert "SAMPLE-SECRET" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_a_host_failure_is_never_cached_and_a_later_read_succeeds(stub, monkeypatch, tmp_path):
    """Through the artifact cache: a full disk while rendering leaves no entry (the None it used to answer would have
    been kept for these bytes), and the next read of the same bytes reads every page."""
    _poppler_or_skip()
    from webapp.artifact_cache import ArtifactCache, cached_ocr
    from webapp.storage import Storage

    cache = ArtifactCache(Storage(tmp_path / "data"))
    pdf_bytes = _fabricated_scan(3)

    def read():
        return cached_ocr(pdf_bytes, compute=lambda: rung.parse_local_tesseract(pdf_bytes, source_file="s.pdf"),
                          cache=cache, source_file="s.pdf", force_ocr=False, allow_local_ocr=True,
                          allow_visual_ocr=False)

    real_render = rung.rasterize_pages_to_files
    monkeypatch.setattr(rung, "rasterize_pages_to_files",
                        _raising(lambda: OSError(errno.ENOSPC, "No space left on device")))
    with pytest.raises(rung.LocalOcrIncomplete):
        read()
    assert cache.storage.cache_entries("ocr") == []
    monkeypatch.setattr(rung, "rasterize_pages_to_files", real_render)
    result = read()
    assert result.cached is False
    assert _page_digests(result.value) == _oracle_png_digests(pdf_bytes)


# ---------------------------------------------------------------------------------------------------------------------
# The callers: the web worker ends the job in a terminal error, the discovery run fails the document and goes on.
# ---------------------------------------------------------------------------------------------------------------------


class _ReadDoc:
    model = "local-tesseract-ocr"
    pages = ["SAMPLE"]

    def to_markdown(self):
        return "SAMPLE"


def test_the_worker_ends_a_job_whose_read_timed_out_in_error_and_caches_nothing(monkeypatch, tmp_path):
    from webapp.jobs import JobStore
    from webapp.storage import Storage
    from webapp.worker import run_job

    store = JobStore(Storage(tmp_path / "data"))
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)

    def timed_out(*args, **kwargs):
        raise rung.LocalOcrTimeout("tesseract ran past its time limit")

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", timed_out)
    first = store.create("scan.pdf", pdf_bytes=b"%PDF-SAMPLE-scan")
    run_job(first.id, b"%PDF-SAMPLE-scan", "scan.pdf", store, parse_mode="deterministic")
    failed = store.get(first.id)
    assert failed.status == "error"
    assert failed.error == (
        "reading stage failed: LocalOcrTimeout "
        "(message withheld; an exception message can quote statement text)"
    )
    assert store.cache.storage.cache_entries("ocr") == []

    # The same bytes again, the host healthy: read afresh (no cached "no text"), and the job reaches analysis.
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: _ReadDoc())
    monkeypatch.setattr("webapp.worker.analyze_document", lambda *a, **k: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda report: {"quality": {"level": "transaction_level"}})
    again = store.create("scan.pdf", pdf_bytes=b"%PDF-SAMPLE-scan")
    run_job(again.id, b"%PDF-SAMPLE-scan", "scan.pdf", store, parse_mode="deterministic")
    assert store.get(again.id).status == "done"
    assert store.get(again.id).parse_model == "local-tesseract-ocr"


def test_a_discovery_run_fails_a_refused_read_closed_and_goes_on(monkeypatch, tmp_path):
    from discovery.inventory import DedupIndex
    from discovery.runner import MODE_SCANNED, DiscoveryRunner

    root = tmp_path / "root"
    (root / "SampleBank").mkdir(parents=True)
    (root / "SampleBank" / "first.pdf").write_bytes(_fabricated_scan(1, seed=1))
    (root / "SampleBank" / "second.pdf").write_bytes(_fabricated_scan(1, seed=2))
    calls = []

    def fake_rung(pdf_bytes, source_file="", **kwargs):
        calls.append(source_file)
        if source_file == "first.pdf":
            raise rung.LocalOcrTimeout("tesseract ran past its time limit")
        return None

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake_rung)
    import json

    from telemetry import JsonlSink

    sink_path = tmp_path / "telemetry.jsonl"
    runner = DiscoveryRunner(root, mode=MODE_SCANNED, run_id="test-run", sink=JsonlSink(sink_path), cache=None,
                             dedup=DedupIndex())
    first = runner.process("SampleBank/first.pdf", "SampleBank")
    second = runner.process("SampleBank/second.pdf", "SampleBank")
    assert calls == ["first.pdf", "second.pdf"]
    assert (first.outcome_class, first.outcome_reason, first.error_type, first.source_path) == (
        "failed", "ocr_failed", "LocalOcrTimeout", "none")
    # the second read, healthy and empty, is the ordinary "Tesseract ran and read nothing usable": DECLARED MOVE
    # (model-code removal, slice S5) from `deferred:deferred_visual_ocr` to the fail-closed
    # `refused:insufficient_evidence`, in the row and in its telemetry record
    assert (second.outcome_class, second.outcome_reason) == ("refused", "insufficient_evidence")
    records = [json.loads(line) for line in sink_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [(r["outcome"]["class"], r["outcome"]["reason"]) for r in records] == [
        ("failed", "ocr_failed"), ("refused", "insufficient_evidence")]
