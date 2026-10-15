import types
import parse as cli


def test_main_writes_markdown(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.md"
    fake_doc = types.SimpleNamespace(
        to_markdown=lambda: "<!-- x -->\n\n--- Page 1 ---\n\n# hi\n")
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="": fake_doc)
    rc = cli.main([str(pdf), "--out", str(out)])
    assert rc == 0
    assert out.read_text(encoding="utf-8").startswith("<!-- x -->")


def test_main_writes_html_when_flag_set(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.html"
    fake_doc = types.SimpleNamespace(to_markdown=lambda: "# Hello")
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="": fake_doc)
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

    def boom(pdf_bytes, source_file=""):
        raise RuntimeError("reader crashed")

    monkeypatch.setattr(cli, "parse_statement", boom)
    rc = cli.main([str(pdf)])
    assert rc == 1
    assert "failed to parse statement" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Model-code removal, slice S2: this CLI reads native PDF text only. `--visual`
# (the probed visual OCR opt-in) and `--model` were removed with the visual OCR
# client; the probe tests that stood here went with them.
# ---------------------------------------------------------------------------


def test_main_reads_native_text_only(monkeypatch, tmp_path):
    """The CLI asks the ladder for no OCR rung: only the source name reaches
    `parse_statement`, so the ladder's own defaults apply (no Tesseract, no
    visual rung). The Paddle-only `dpi` stopped being passed in slice S5,
    when `--dpi` was removed (declared)."""
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    seen = {}
    fake_doc = types.SimpleNamespace(to_markdown=lambda: "# hi")

    def fake_parse_statement(pdf_bytes, source_file="", **kwargs):
        seen.update(kwargs, source_file=source_file)
        return fake_doc

    monkeypatch.setattr(cli, "parse_statement", fake_parse_statement)
    rc = cli.main([str(pdf)])
    assert rc == 0
    assert seen == {"source_file": "s.pdf"}


def test_main_has_no_visual_model_or_dpi_flag(tmp_path, capsys):
    """`--visual` and `--model` were removed in slice S2, `--dpi` (read only by
    the model OCR rungs) in slice S5."""
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    for argv in ([str(pdf), "--visual"], [str(pdf), "--model", "some/model"], [str(pdf), "--dpi", "150"]):
        try:
            cli.main(argv)
        except SystemExit as exc:
            assert exc.code == 2  # argparse: unrecognized arguments
        else:
            raise AssertionError(f"{argv[1]} must no longer be accepted")
        assert argv[1] in capsys.readouterr().err


def test_parse_imports_no_visual_ocr_probe():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(cli))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not modules & {"ocr.availability", "ocr.ocr_client", "ocr.config"}, modules


def test_main_none_document_fails_closed(monkeypatch, tmp_path, capsys):
    """The offline ladder can return None (`parse_statement`'s own contract);
    this must not crash on `doc.to_markdown()`, and the message (declared,
    slice S2) says what this CLI reads instead of naming a removed flag."""
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(cli, "parse_statement", lambda pdf_bytes, source_file="", **kwargs: None)
    rc = cli.main([str(pdf)])
    assert rc == 1
    err = capsys.readouterr().err
    assert err == cli.NO_NATIVE_TEXT + "\n"
    assert "native PDF text only" in err and "--visual" not in err


# ---------------------------------------------------------------------------
# Audit 2026-10-13, EXP-5: a redirected stdout on Windows is cp1252, and native
# statement text carries ligatures (U+FB00 to U+FB05) and private-use glyphs it
# cannot encode: the markdown died with UnicodeEncodeError (exit 1, an empty
# file). parse.py now writes UTF-8 to stdout, as --out already does. The stdout
# here is a cp1252 TextIOWrapper, the Windows host's redirected stdout, on any
# host. Fabricated text only.
# ---------------------------------------------------------------------------


def _cp1252_stdout(monkeypatch):
    import io
    import sys

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\r\n")
    monkeypatch.setattr(sys, "stdout", stream)
    return stream


_LIGATURES = "--- Page 1 ---\n\n03/03 SAMPLE Ofﬁce reﬁnd\n03/08 Staﬀing \n"


def test_exp5_ligatures_reach_a_redirected_stdout(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    fake_doc = types.SimpleNamespace(to_markdown=lambda: _LIGATURES)
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="": fake_doc)
    stream = _cp1252_stdout(monkeypatch)
    rc = cli.main([str(pdf)])
    stream.flush()
    assert rc == 0
    assert stream.buffer.getvalue() == (_LIGATURES + "\n").replace("\n", "\r\n").encode("utf-8")


def test_exp5_the_redirected_markdown_matches_the_out_file(monkeypatch, tmp_path):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "s.md"
    fake_doc = types.SimpleNamespace(to_markdown=lambda: _LIGATURES)
    monkeypatch.setattr(cli, "parse_statement",
                        lambda pdf_bytes, source_file="": fake_doc)
    assert cli.main([str(pdf), "--out", str(out)]) == 0
    stream = _cp1252_stdout(monkeypatch)
    assert cli.main([str(pdf)]) == 0
    stream.flush()
    # print adds its own line end; the text itself is the --out file's, character for character.
    assert stream.buffer.getvalue().decode("utf-8") == out.read_text(encoding="utf-8").replace("\n", "\r\n") + "\r\n"
