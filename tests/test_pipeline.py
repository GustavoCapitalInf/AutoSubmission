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
