import types
import parse as cli


def test_main_writes_markdown(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.md"
    fake_doc = types.SimpleNamespace(
        to_markdown=lambda: "<!-- x -->\n\n--- Page 1 ---\n\n# hi\n")
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="", dpi=200, model=None, allow_visual_ocr=False: fake_doc)
    rc = cli.main([str(pdf), "--out", str(out), "--dpi", "150"])
    assert rc == 0
    assert out.read_text(encoding="utf-8").startswith("<!-- x -->")


def test_main_writes_html_when_flag_set(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.html"
    fake_doc = types.SimpleNamespace(to_markdown=lambda: "# Hello")
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="", dpi=200, model=None, allow_visual_ocr=False: fake_doc)
    rc = cli.main([str(pdf), "--out", str(out), "--html"])
    assert rc == 0
    written = out.read_text(encoding="utf-8")
    assert "<html" in written.lower()
    assert "<h1>Hello</h1>" in written
    assert "<title>s.pdf</title>" in written


def test_main_missing_pdf_returns_2(capsys):
    rc = cli.main(["does_not_exist.pdf"])
    assert rc == 2
    assert "cannot read PDF" in capsys.readouterr().err


def test_main_failure_returns_1(monkeypatch, tmp_path, capsys):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")

    def boom(pdf_bytes, source_file="", dpi=200, model=None, allow_visual_ocr=False):
        raise RuntimeError("endpoint down")

    monkeypatch.setattr(cli, "parse_statement", boom)
    rc = cli.main([str(pdf)])
    assert rc == 1
    assert "failed to parse statement" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# P20-SEAM / OQ7: offline by default, `--visual` is the explicit probed opt-in
# ---------------------------------------------------------------------------


def test_main_default_is_offline_only(monkeypatch, tmp_path):
    """The CLI default test (mutation table): a defect that flips this default
    back to True would send an image-bearing request with no probe."""
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    seen = {}
    fake_doc = types.SimpleNamespace(to_markdown=lambda: "# hi")

    def fake_parse_statement(pdf_bytes, source_file="", dpi=200, model=None, allow_visual_ocr=True):
        seen["allow_visual_ocr"] = allow_visual_ocr
        return fake_doc

    monkeypatch.setattr(cli, "parse_statement", fake_parse_statement)
    rc = cli.main([str(pdf)])
    assert rc == 0
    assert seen["allow_visual_ocr"] is False


def test_main_visual_flag_refused_when_endpoint_unusable(monkeypatch, tmp_path, capsys):
    """`--visual` probes first; an unusable/refused endpoint never reaches
    `parse_statement` at all (fail closed, one console line, non-zero exit)."""
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    called = []

    class _Status:
        usable = False

        def message(self):
            return "visual-OCR server unreachable"

    def fake_probe(**kwargs):
        return _Status()

    def fake_parse_statement(*a, **kw):
        called.append(True)
        raise AssertionError("parse_statement must not be called after a refused probe")

    monkeypatch.setattr("ocr.availability.probe_visual_ocr", fake_probe)
    monkeypatch.setattr(cli, "parse_statement", fake_parse_statement)
    rc = cli.main([str(pdf), "--visual"])
    assert rc == 3
    assert "visual-OCR server unreachable" in capsys.readouterr().err
    assert called == []


def test_main_visual_flag_allowed_when_endpoint_usable(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    seen = {}
    fake_doc = types.SimpleNamespace(to_markdown=lambda: "# hi")

    class _Status:
        usable = True

    def fake_probe(**kwargs):
        return _Status()

    def fake_parse_statement(pdf_bytes, source_file="", dpi=200, model=None, allow_visual_ocr=False):
        seen["allow_visual_ocr"] = allow_visual_ocr
        return fake_doc

    monkeypatch.setattr("ocr.availability.probe_visual_ocr", fake_probe)
    monkeypatch.setattr(cli, "parse_statement", fake_parse_statement)
    rc = cli.main([str(pdf), "--visual"])
    assert rc == 0
    assert seen["allow_visual_ocr"] is True


def test_main_none_document_fails_closed(monkeypatch, tmp_path, capsys):
    """`allow_visual_ocr=False` can now make the offline ladder return None
    (`parse_statement`'s own contract); this must not crash on
    `doc.to_markdown()`."""
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(
        cli, "parse_statement",
        lambda pdf_bytes, source_file="", dpi=200, model=None, allow_visual_ocr=False: None,
    )
    rc = cli.main([str(pdf)])
    assert rc == 1
    assert "--visual" in capsys.readouterr().err
