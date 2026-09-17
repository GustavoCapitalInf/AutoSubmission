import io

from PIL import Image

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from vlm import render


def _pdf() -> bytes:
    return render_native_pdf(build_ledger_page(n_rows=4))


def test_page_count_and_dimensions():
    pdf = _pdf()
    assert render.page_count(pdf) == 1
    pages = render.render_pages(pdf, long_edge=1000)
    assert len(pages) == 1
    page = pages[0]
    assert page.index == 0 and max(page.width, page.height) == 1000
    assert page.pdf_width_pt == 612.0 and page.pdf_height_pt == 792.0
    assert page.jpeg[:3] == b"\xff\xd8\xff"
    assert Image.open(io.BytesIO(page.jpeg)).size == (page.width, page.height)
    assert page.render_ms >= 0 and page.encode_ms >= 0


def test_render_is_deterministic():
    a = render.render_pages(_pdf())[0]
    b = render.render_pages(_pdf())[0]
    assert a.jpeg_sha256 == b.jpeg_sha256 and a.pixel_sha256 == b.pixel_sha256


def test_page_indices_subset():
    pdf = _pdf()
    assert render.render_pages(pdf, page_indices=[]) == []
    assert [p.index for p in render.render_pages(pdf, page_indices=[0])] == [0]


def test_render_image_input():
    image = Image.new("RGB", (400, 200), (255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    page = render.render_image(buf.getvalue(), long_edge=800)
    assert (page.width, page.height) == (800, 400) and page.pdf_width_pt == 0.0


def test_render_document_dispatches_on_magic():
    assert len(render.render_document(_pdf())) == 1
    image = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    assert len(render.render_document(buf.getvalue())) == 1


def test_render_settings_are_pinned():
    settings = render.render_settings()
    assert settings["render_version"] == 1 and settings["long_edge"] == 1540 and settings["jpeg_quality"] == 90
    assert settings["pdfium_version"]
