import threading
import time

import fitz
import pytest

from ocr.pipeline import parse_statement


def test_parse_statement_uses_injected_ocr(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=200: ["p0", "p1", "p2"])
    calls = []

    def fake_ocr(image):
        calls.append(image)
        return f"# md for {image}"

    doc = parse_statement(b"%PDF-fake", source_file="s.pdf", dpi=150,
                          model="baidu/Unlimited-OCR", page_ocr_fn=fake_ocr)
    assert doc.source_file == "s.pdf"
    assert doc.model == "baidu/Unlimited-OCR"
    # Results reassembled in page order regardless of completion order.
    assert doc.pages == ["# md for p0", "# md for p1", "# md for p2"]
    assert len(calls) == 3
    assert "--- Page 3 ---" in doc.to_markdown()


def test_parse_statement_ocrs_pages_concurrently(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf",
                        lambda b, dpi=200: [f"p{i}" for i in range(4)])
    concurrent = 0
    peak = 0
    lock = threading.Lock()

    def slow_ocr(image):
        nonlocal concurrent, peak
        with lock:
            concurrent += 1
            peak = max(peak, concurrent)
        time.sleep(0.05)
        with lock:
            concurrent -= 1
        return f"md {image}"

    doc = parse_statement(b"%PDF-fake", page_ocr_fn=slow_ocr, max_workers=3)
    assert doc.pages == ["md p0", "md p1", "md p2", "md p3"]
    assert peak >= 2  # pages actually ran in parallel


_ORPHAN = ("<table><tr><td>AMOUNT($)</td></tr><tr><td>66.07</td></tr>"
           "<tr><td>1.00</td></tr><tr><td>2.00</td></tr></table>")
_CLEAN = ("<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT($)</td></tr>"
          "<tr><td>03/19</td><td>x</td><td>66.07</td></tr></table>")


def test_parse_statement_reocrs_missegmented_page_at_fallback_dpi(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["main"])
    monkeypatch.setattr("ocr.pipeline.rasterize_page", lambda b, i, dpi=250: "alt")

    def fake_ocr(image, *, settings, client, on_delta=None):
        return _ORPHAN if image == "main" else _CLEAN  # 300 splits, 250 is clean

    monkeypatch.setattr("ocr.ocr_client.ocr_page", fake_ocr)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    doc = parse_statement(b"%PDF", max_workers=1)
    assert doc.pages == [_CLEAN]  # kept the clean fallback read


def test_parse_statement_keeps_original_when_fallback_also_bad(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["main"])
    monkeypatch.setattr("ocr.pipeline.rasterize_page", lambda b, i, dpi=250: "alt")
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: _ORPHAN)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    doc = parse_statement(b"%PDF", max_workers=1)
    assert doc.pages == [_ORPHAN]  # fallback no better -> keep original


def test_parse_statement_no_fallback_when_disabled(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["main"])
    calls = []

    def fake_page(b, i, dpi=250):
        calls.append(i)
        return "alt"

    monkeypatch.setattr("ocr.pipeline.rasterize_page", fake_page)
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: _ORPHAN)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    doc = parse_statement(b"%PDF", max_workers=1, fallback_dpi=None)
    assert doc.pages == [_ORPHAN]
    assert calls == []  # fallback disabled -> no re-rasterize


_TD_TRUNC = "TD Bank STATEMENT OF ACCOUNT\nPage 1 of 10\nCust Ref #: 826"
_TD_FULL = ("TD Bank STATEMENT OF ACCOUNT\nACCOUNT SUMMARY\n"
            "Beginning Balance 11,982.22\nDEPOSIT 20,000.00\n" + "x" * 200)


def test_parse_statement_recovers_truncated_td_page(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["main"])
    dpis = []

    def fake_page(b, i, dpi=200):
        dpis.append(dpi)
        return f"rec-{dpi}"

    monkeypatch.setattr("ocr.rasterize.rasterize_page", fake_page)  # used by recovery
    monkeypatch.setattr("ocr.ocr_client._mask_qr", lambda image: image)

    def fake_ocr(image, *, settings, client, on_delta=None):
        return _TD_TRUNC if image == "main" else _TD_FULL  # any recovery variant is full

    monkeypatch.setattr("ocr.ocr_client.ocr_page", fake_ocr)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    replaced = []
    doc = parse_statement(b"%PDF", max_workers=1,
                          on_page_replace=lambda p, t: replaced.append((p, t)))
    assert doc.pages == [_TD_FULL]  # kept the recovered full read
    assert dpis and dpis[0] == 300  # masked 300 DPI recovery is tried first
    # the live buffer for page 0 is overwritten with the recovered read (web UI fix)
    assert replaced == [(0, _TD_FULL)]


def test_parse_statement_no_td_recovery_for_normal_page(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["main"])
    calls = []
    monkeypatch.setattr("ocr.rasterize.rasterize_page",
                        lambda b, i, dpi=200: calls.append(dpi) or "rec")
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: _TD_FULL)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    doc = parse_statement(b"%PDF", max_workers=1)
    assert doc.pages == [_TD_FULL]
    assert calls == []  # full TD page -> no recovery


def test_parse_statement_no_td_recovery_after_first_page(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: [_TD_FULL, _TD_TRUNC])
    calls = []
    monkeypatch.setattr("ocr.rasterize.rasterize_page",
                        lambda b, i, dpi=200: calls.append((i, dpi)) or "rec")

    def fake_ocr(image, *, settings, client, on_delta=None):
        return image

    monkeypatch.setattr("ocr.ocr_client.ocr_page", fake_ocr)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    doc = parse_statement(b"%PDF", max_workers=1)
    assert doc.pages == [_TD_FULL, _TD_TRUNC]
    assert calls == []


def test_parse_statement_streams_page_indexed_deltas(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=200: ["p0", "p1"])

    captured = []

    class FakeClient:
        pass

    def fake_ocr_page(image, *, settings, client, on_delta=None):
        if on_delta:
            on_delta(f"chunk-{image}")
        return f"md {image}"

    monkeypatch.setattr("ocr.ocr_client.ocr_page", fake_ocr_page)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: FakeClient())

    parse_statement(b"%PDF-fake", max_workers=2,
                    on_page_delta=lambda page, chunk: captured.append((page, chunk)))

    assert sorted(captured) == [(0, "chunk-p0"), (1, "chunk-p1")]


# ---------------------------------------------------------------------------
# O-1: the single intake ladder (native -> tesseract -> visual OCR).
# Rungs are patched at their ONE home in ocr.pipeline; the extractors
# themselves are never touched.
# ---------------------------------------------------------------------------


class _NativeDoc:
    model = "native-pdf-text"
    pages = ["native page one", "native page two"]

    def to_markdown(self):
        return "# native"


class _TesseractDoc:
    model = "local-tesseract-ocr"
    pages = ["tesseract page"]

    def to_markdown(self):
        return "# tesseract"


def _forbid_visual(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.load_settings",
                        lambda **k: pytest.fail("visual OCR rung must not run"))


def _mock_visual(monkeypatch, text="# visual"):
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr("ocr.ocr_client.ocr_page",
                        lambda image, *, settings, client, on_delta=None: text)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())


def test_ladder_native_rung_wins_and_replays_pages(monkeypatch):
    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda pdf_bytes, source_file="": _NativeDoc())
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract",
                        lambda *a, **k: pytest.fail("tesseract rung must not run"))
    _forbid_visual(monkeypatch)

    replayed = []
    stages = []
    doc = parse_statement(b"%PDF-fake", allow_local_ocr=True,
                          on_page_replace=lambda p, t: replayed.append((p, t)),
                          on_stage=stages.append)
    assert doc.model == "native-pdf-text"
    assert replayed == [(0, "native page one"), (1, "native page two")]
    assert stages == ["native"]


def test_ladder_tesseract_rung_is_capability_gated(monkeypatch):
    tesseract_calls = []

    def fake_tesseract(pdf_bytes, source_file="", **kwargs):
        tesseract_calls.append(source_file)
        return _TesseractDoc()

    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake_tesseract)
    _forbid_visual(monkeypatch)

    # Without the capability the rung is skipped entirely (the CLI's posture)...
    assert parse_statement(b"%PDF-fake", allow_local_ocr=False, allow_visual_ocr=False) is None
    assert tesseract_calls == []
    # ...with it, the scan is served locally and visual OCR is never reached.
    doc = parse_statement(b"%PDF-fake", allow_local_ocr=True, allow_visual_ocr=False)
    assert doc.model == "local-tesseract-ocr"
    assert tesseract_calls == ["" ]


def test_ladder_stops_before_visual_when_not_allowed(monkeypatch):
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    _forbid_visual(monkeypatch)
    stages = []
    assert parse_statement(b"%PDF-fake", allow_visual_ocr=False, on_stage=stages.append) is None
    assert stages == ["native"]  # the withheld visual rung was never announced


def test_ladder_force_ocr_skips_offline_rungs(monkeypatch):
    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda *a, **k: pytest.fail("native rung must not run under force_ocr"))
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract",
                        lambda *a, **k: pytest.fail("tesseract rung must not run under force_ocr"))
    _mock_visual(monkeypatch)

    stages = []
    doc = parse_statement(b"%PDF-fake", force_ocr=True, allow_local_ocr=True,
                          max_workers=1, on_stage=stages.append)
    assert doc.pages == ["# visual"]
    assert stages == ["visual_ocr"]


def test_ladder_profile_skips_native_for_textless_pdf(monkeypatch):
    # A REAL image-only PDF: the profile reports zero native text, so the
    # ladder never even calls the native extractors (safe: they all gate on
    # extracted text markers).
    blank = fitz.open()
    blank.new_page()
    pdf_bytes = blank.tobytes()

    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda *a, **k: pytest.fail("native rung must be profile-skipped"))
    _forbid_visual(monkeypatch)

    stages = []
    result = parse_statement(pdf_bytes, allow_visual_ocr=False, on_stage=stages.append)
    assert result is None
    assert stages == []  # no rung ran at all


def test_ladder_announces_every_rung_in_order(monkeypatch):
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)
    _mock_visual(monkeypatch)

    stages = []
    doc = parse_statement(b"%PDF-fake", allow_local_ocr=True, max_workers=1,
                          on_stage=stages.append)
    assert doc.pages == ["# visual"]
    assert stages == ["native", "local_ocr", "visual_ocr"]
