import types
import parse as cli


def test_main_writes_markdown(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.md"
    fake_doc = types.SimpleNamespace(
        to_markdown=lambda: "<!-- x -->\n\n--- Page 1 ---\n\n# hi\n")
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="", dpi=200, model=None: fake_doc)
    rc = cli.main([str(pdf), "--out", str(out), "--dpi", "150"])
    assert rc == 0
    assert out.read_text(encoding="utf-8").startswith("<!-- x -->")


def test_main_writes_html_when_flag_set(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.html"
    fake_doc = types.SimpleNamespace(to_markdown=lambda: "# Hello")
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="", dpi=200, model=None: fake_doc)
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

    def boom(pdf_bytes, source_file="", dpi=200, model=None):
        raise RuntimeError("endpoint down")

    monkeypatch.setattr(cli, "parse_statement", boom)
    rc = cli.main([str(pdf)])
    assert rc == 1
    assert "failed to parse statement" in capsys.readouterr().err
