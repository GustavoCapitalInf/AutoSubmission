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
    assert doc.pages == ["# md for p0", "# md for p1", "# md for p2"]
    assert len(calls) == 3
    assert "--- Page 3 ---" in doc.to_markdown()
