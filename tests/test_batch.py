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


# --- The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): the CLI's Zelle reading ------------------
# --zelle-true-revenue {yes,no}, yes by default as on the Settings page. Fabricated rows (tests/zelle_setting_fixtures).


def _z1():
    from tests import zelle_setting_fixtures as fx
    return fx.case_document("Z1")


def test_render_prints_the_yes_figures_and_the_zelle_line_by_default():
    import analyze

    report = _z1().accounts[0]
    text = analyze._render(report)
    assert "True revenue          : $11,534.56" in text
    assert ("  Zelle deposits: $7,734.56 (4): $1,234.56 in True revenue, $6,500.00 held for review "
            "(Mark Zelle Payments as True Revenue: Yes; --zelle-true-revenue no excludes them)") in text.splitlines()


def test_render_under_no_prints_today_s_lines_exactly():
    import dataclasses

    import analyze

    report = _z1().accounts[0]
    text = analyze._render(report, zelle_true_revenue=False)
    assert "True revenue          : $10,300.00" in text and "Zelle deposits:" not in text
    assert text == analyze._render(dataclasses.replace(report, zelle_counted=None), zelle_true_revenue=False)


def test_render_names_a_zelle_asset_sale_as_non_revenue():
    import analyze
    from tests import zelle_setting_fixtures as fx

    text = analyze._render(fx.case_document("Z4_TRUCK").accounts[0])
    assert ("  Zelle deposits: $9,000.00 (1): $0.00 in True revenue, $0.00 held for review, $9,000.00 non-revenue "
            "(Mark Zelle Payments as True Revenue: Yes; --zelle-true-revenue no excludes them)") in text.splitlines()


def test_the_batch_row_reads_the_chosen_reading():
    from pathlib import Path

    report = _z1().accounts[0]
    yes, no = batch._row(Path("fabricated.md"), report), batch._row(Path("fabricated.md"), report, False)
    assert (yes["zelle_true_revenue"], yes["zelle_deposit_total"], yes["zelle_in_true_revenue_total"]) == (
        "yes", "7734.56", "1234.56")
    assert (no["zelle_true_revenue"], no["zelle_deposit_total"], no["zelle_in_true_revenue_total"]) == (
        "no", "7734.56", "0.00")
    assert (yes["true_revenue_total"], no["true_revenue_total"]) == ("11534.56", "10300.00")
    # needs_review's revenue_review_required term follows the reading (the other terms are clear on this fixture).
    assert report.quality.corporate_use != "manual_review_required"
    assert report.metrics.revenue_reconciles and report.zelle_counted.metrics.revenue_reconciles
    assert report.zelle_counted.metrics.revenue_review_required is True and report.metrics.revenue_review_required is False
    assert (yes["needs_review"], no["needs_review"]) == ("REVIEW", "")
    assert {"zelle_true_revenue", "zelle_deposit_total", "zelle_in_true_revenue_total"} <= set(batch.FIELDS)


def test_a_zelle_free_row_carries_the_fixed_columns():
    from pathlib import Path

    from tests import zelle_setting_fixtures as fx
    row = batch._row(Path("fabricated.md"), fx.document(fx.FREE).accounts[0])
    assert (row["zelle_true_revenue"], row["zelle_deposit_total"], row["zelle_in_true_revenue_total"]) == (
        "yes", "0.00", "0.00")


def test_analyze_json_under_no_carries_no_zelle_key():
    import analyze

    payload = analyze._json_safe(_z1(), zelle_true_revenue=False)
    assert "zelle_counted_reading" not in payload and "zelle_deposits" not in payload["metrics"]
    assert not any("zelle_deposit" in transaction for transaction in payload["statement"]["transactions"])
    shown = analyze._json_safe(_z1())
    assert shown["metrics"]["zelle_deposits"]["counted_as_true_revenue"] is True
    assert sum(1 for transaction in shown["statement"]["transactions"] if transaction.get("zelle_deposit")) == 4


def test_the_flag_reaches_both_clis(monkeypatch, tmp_path, capsys):
    import analyze

    md = tmp_path / "statement.md"
    md.write_text("--- Page 1 ---\n\nfabricated\n", encoding="utf-8")
    monkeypatch.setattr(analyze, "analyze_document", lambda markdown, **kwargs: _z1())
    monkeypatch.setattr(sys, "argv", ["analyze.py", str(md), "--zelle-true-revenue", "no"])
    analyze.main()
    assert "Zelle deposits:" not in capsys.readouterr().out
    out = tmp_path / "triage.csv"
    monkeypatch.setattr(batch, "analyze_document", lambda markdown, **kwargs: _z1())
    monkeypatch.setattr(sys, "argv", ["batch.py", str(md), "--out", str(out), "--zelle-true-revenue", "no"])
    monkeypatch.setenv("TELEMETRY_DISABLED", "1")
    batch.main()
    with open(out, newline="", encoding="utf-8") as f:
        [row] = list(csv.DictReader(f))
    assert (row["zelle_true_revenue"], row["true_revenue_total"]) == ("no", "10300.00")
