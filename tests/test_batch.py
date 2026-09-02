"""batch.py: the CSV error cell carries the exception CLASS NAME only.

MINOR-8 (PHASE2_P20SEAM_REVIEW.md): `batch.py:312` used to write
`f"{type(e).__name__}: {e}"` into the CSV `error` cell — the same pattern
`coverage_audit.py` and `deterministic_coverage_audit.py` used before their
retirement (P20-SEAM / OQ7). This card's own new raise path
(`ocr.config.ProvenanceTokenError` on a hostile `source_file`) quotes the
whole filename in its message (`ocr/document.py`'s docstring), so a refused
filename would have landed verbatim in a local report. The cell carries the
class name only now, matching every other class-name-only sink in this tree.
"""
from __future__ import annotations

import csv
import sys

import batch


def test_error_cell_carries_the_class_name_only(monkeypatch, tmp_path, capsys):
    md = tmp_path / "statement.md"
    md.write_text("--- Page 1 ---\n\nsome text\n", encoding="utf-8")
    out = tmp_path / "triage.csv"

    def boom(markdown, **kwargs):
        raise RuntimeError("SENSITIVE ACCOUNT 000111222 BALANCE $9,876.54")

    monkeypatch.setattr(batch, "analyze_document", boom)
    monkeypatch.setattr(sys, "argv", ["batch.py", str(md), "--out", str(out)])
    monkeypatch.setenv("TELEMETRY_DISABLED", "1")

    batch.main()

    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["error"] == "RuntimeError"
    assert "SENSITIVE" not in rows[0]["error"]
    assert "9,876.54" not in rows[0]["error"]
    assert rows[0]["needs_review"] == "REVIEW"

    # traceback.print_exc() still prints the full detail to the console for a
    # developer debugging the run — only the durable CSV artifact is reduced.
    err = capsys.readouterr().err
    assert "RuntimeError" in err
