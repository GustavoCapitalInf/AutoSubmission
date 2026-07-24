import threading
import time

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

    def fake_ocr(image, *, settings, client, on_delta=None):
        return _TD_TRUNC if image == "main" else _TD_FULL  # any recovery variant is full

    monkeypatch.setattr("ocr.ocr_client.ocr_page", fake_ocr)
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    doc = parse_statement(b"%PDF", max_workers=1)
    assert doc.pages == [_TD_FULL]  # kept the recovered full read
    assert dpis and dpis[0] == 200  # first recovery variant tried


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
