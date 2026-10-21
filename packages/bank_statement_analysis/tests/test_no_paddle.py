"""No Paddle knob is left (owner ruling, 2026-10-13: the product uses no model; model-code removal, slice S5).

No module passes `allow_paddle_ocr=True` or names a Paddle data scope, the ladder takes no Paddle knob and refuses
`force_ocr=True`, the cache takes no Paddle option, and the parse CLI has no `--dpi`. That the PaddleOCR rung and its
tools stay deleted, and that nothing imports them, is `tests/test_no_model_clients.py`'s scan.
"""
from __future__ import annotations

import ast
import inspect

import pytest

from tests.test_no_model_clients import ROOT, tracked_python_files


def _calls_naming(source: str, keyword: str) -> list[int]:
    """Calls passing `keyword=` anything but the literal False or the caller's own same-named parameter."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg != keyword:
                    continue
                if isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    continue
                if isinstance(kw.value, ast.Name) and kw.value.id == keyword:
                    continue
                lines.append(node.lineno)
    return lines


def test_no_module_passes_a_paddle_knob_or_a_paddle_data_scope():
    """Outside tests, no call passes `allow_paddle_ocr` anything but the literal False, and nothing names
    `paddle_data_scope` at all (the ladder parameter left with the rung)."""
    offenders = []
    for relative in tracked_python_files():
        if relative.startswith("tests/") or not (ROOT / relative).is_file():
            continue
        source = (ROOT / relative).read_text(encoding="utf-8")
        hits = _calls_naming(source, "allow_paddle_ocr") + _calls_naming(source, "paddle_data_scope")
        tree = ast.parse(source)
        hits += [node.lineno for node in ast.walk(tree)
                 if (isinstance(node, ast.arg) and node.arg == "paddle_data_scope")
                 or (isinstance(node, ast.Name) and node.id == "paddle_data_scope")]
        if hits:
            offenders.append(f"{relative}: {hits}")
    assert offenders == [], offenders


def test_the_ladder_takes_no_paddle_knob_and_refuses_forcing(monkeypatch):
    from ocr.pipeline import FORCED_OCR_REMOVED, parse_statement

    parameters = set(inspect.signature(parse_statement).parameters)
    assert not parameters & {"allow_paddle_ocr", "paddle_data_scope", "dpi"}
    monkeypatch.setattr("ocr.pipeline.inspect_pdf", lambda *a, **k: pytest.fail("nothing may be read"))
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda *a, **k: pytest.fail("nothing may be read"))
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: pytest.fail("nothing may be read"))
    for flags in ({}, {"allow_local_ocr": True}):
        with pytest.raises(ValueError) as refused:
            parse_statement(b"%PDF-1.4", source_file="x.pdf", force_ocr=True, **flags)
        assert str(refused.value) == FORCED_OCR_REMOVED


def test_the_cache_takes_no_paddle_knob():
    from webapp.artifact_cache import cached_ocr, ocr_settings_key

    for function in (ocr_settings_key, cached_ocr):
        assert "allow_paddle_ocr" not in inspect.signature(function).parameters


def test_the_parse_cli_has_no_dpi_flag(tmp_path, capsys):
    import parse

    with pytest.raises(SystemExit) as raised:
        parse.main([str(tmp_path / "x.pdf"), "--dpi", "300"])
    assert raised.value.code == 2
    assert "--dpi" in capsys.readouterr().err
