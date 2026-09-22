"""Synthetic-only checks for the visual pair's 300-DPI lossless PNG pin."""
from __future__ import annotations

import base64
import hashlib
import io
import json

from PIL import Image
import pytest

from ocr.visual_pair_config import (
    VisualPairConfigError,
    VisualPairSettings,
    load_visual_pair_settings,
)
from vlm.client import VlmClient
from vlm.assemble import DotsLayout
from vlm.proposal_recovery import recover_proposal_page
from vlm.render import render_pages


def _letter_pdf() -> bytes:
    """Build one fabricated 612x792-point page entirely in memory."""
    content = b"BT /F1 12 Tf 36 756 Td (SYNTHETIC RENDER TEST) Tj ET\n0 0 0 RG 36 720 m 576 720 l S\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
    ]
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(result)


def test_visual_pair_defaults_and_environment_loader_pin_300_dpi_png():
    for settings in (VisualPairSettings(), load_visual_pair_settings({})):
        assert settings.render_dpi == 300
        assert settings.render_format == "PNG"


def test_visual_pair_manifest_reports_the_actual_rgb_png_render_pin():
    from vlm.pair import visual_pair_manifest

    renderer = visual_pair_manifest()["renderer"]
    assert renderer["render_version"] == 2
    assert renderer["renderer"] == "pypdfium2"
    assert renderer["dpi"] == 300
    assert renderer["image_format"] == "PNG"
    assert renderer["color_mode"] == "RGB"
    assert "long_edge" not in renderer
    assert "jpeg_quality" not in renderer


@pytest.mark.parametrize("dpi", [72, 150, 299, 301, None, "300", True])
def test_visual_pair_refuses_other_render_dpi(dpi):
    with pytest.raises(VisualPairConfigError):
        VisualPairSettings(render_dpi=dpi)


@pytest.mark.parametrize("image_format", ["JPEG", "WEBP", "png", "", None])
def test_visual_pair_refuses_other_render_formats(image_format):
    with pytest.raises(VisualPairConfigError):
        VisualPairSettings(render_format=image_format)


def test_letter_pdf_300_dpi_is_lossless_rgb_png_without_long_edge_resize():
    pages = render_pages(_letter_pdf(), dpi=300, image_format="PNG")
    assert len(pages) == 1
    page = pages[0]
    assert page.index == 0
    assert (page.pdf_width_pt, page.pdf_height_pt) == (612.0, 792.0)
    # PDFium rounds the floating-point 300/72 scaled height up to 3301.
    assert (page.width, page.height) == (2550, 3301)
    # Legacy attribute names remain part of the shared rendering API.
    assert page.jpeg.startswith(b"\x89PNG\r\n\x1a\n")
    assert page.jpeg_sha256 == hashlib.sha256(page.jpeg).hexdigest()
    with Image.open(io.BytesIO(page.jpeg)) as decoded:
        decoded.load()
        assert decoded.format == "PNG"
        assert decoded.mode == "RGB"
        assert decoded.size == (2550, 3301)
        # PNG must retain precisely the RGB pixels hashed before encoding.
        assert hashlib.sha256(decoded.tobytes()).hexdigest() == page.pixel_sha256
        assert decoded.getextrema()[0][0] < 255


def test_client_preserves_png_bytes_and_declares_png_mime_without_network(monkeypatch):
    image = Image.new("RGB", (3, 2), (255, 255, 255))
    image.putpixel((1, 1), (11, 23, 37))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    requests = []

    def capture_request(self, method, path, body):
        requests.append((method, path, body))
        return b'{"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}]}', 0.0

    monkeypatch.setattr(VlmClient, "_request", capture_request)
    result = VlmClient("http://127.0.0.1:9").chat(
        "synthetic-model", "Synthetic image only", image_jpeg=png,
    )
    assert len(requests) == 1
    method, path, raw = requests[0]
    assert (method, path) == ("POST", "/v1/chat/completions")
    content = json.loads(raw)["messages"][0]["content"]
    assert content[0]["type"] == "image_url"
    prefix, encoded = content[0]["image_url"]["url"].split(",", 1)
    assert prefix == "data:image/png;base64"
    assert base64.b64decode(encoded, validate=True) == png
    assert result.request_bytes == raw
    assert result.request_sha256 == hashlib.sha256(raw).hexdigest()


def test_png_recovery_crops_preserve_exact_source_rgb_pixels():
    source = Image.new("RGB", (37, 101))
    source.putdata([
        ((x * 17) % 256, (y * 13) % 256, (x + y * 3) % 256)
        for y in range(source.height) for x in range(source.width)
    ])
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")
    png = buffer.getvalue()
    seen = []

    def read_fabricated_crop(crop):
        seen.append(crop)
        return DotsLayout(crop.page, (), (), (), False)

    failed = DotsLayout(1, (), (), ("stage_a_truncated",), True)
    result = recover_proposal_page(png, failed, read_fabricated_crop)
    assert result.attempted and result.recovered
    assert len(seen) == 2
    assert [crop.bounds_px for crop in seen] == [(0, 0, 37, 57), (0, 44, 37, 101)]
    assert result.audit["original"]["layout"]["truncated"] is True
    assert result.audit["effective_complete"] is True
    for crop in seen:
        assert crop.jpeg.startswith(b"\x89PNG\r\n\x1a\n")
        assert crop.source_jpeg_sha256 == hashlib.sha256(png).hexdigest()
        assert crop.jpeg_sha256 == hashlib.sha256(crop.jpeg).hexdigest()
        with Image.open(io.BytesIO(crop.jpeg)) as decoded:
            decoded.load()
            assert decoded.format == "PNG" and decoded.mode == "RGB"
            assert decoded.size == (crop.width, crop.height)
            expected_pixels = source.crop(crop.bounds_px).tobytes()
            assert decoded.tobytes() == expected_pixels
            assert crop.pixel_sha256 == hashlib.sha256(expected_pixels).hexdigest()
