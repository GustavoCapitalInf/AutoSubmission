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


# --- Audit round 3, R3-B20 (R3-48; true revenue spec §10.4's I51 and R52): where the revenue is not established, the
# Zelle figures keep what the captured rows say (the count and total, the non-revenue part) and drop every part of True
# or Held. Z1 printed with a bank-summary credit total $30.00 above its rows: a tied ledger, revenue not established.

#: Z1's rows' credits: 10,000.00 + 1,234.56 + 2,000.00 + 2,000.00 + 2,500.00 + 300.00.
_Z1_CREDITS = 18034.56


def _unestablished(name="Z1", credits=_Z1_CREDITS):
    from tests import zelle_setting_fixtures as fx
    return fx.case_document(name, stated_credits=round(credits + 30.0, 2)).accounts[0]


def test_render_of_an_unestablished_statement_prints_the_captured_zelle_rows_only():
    import analyze

    report = _unestablished()
    assert report.metrics.deposits_source == "bank_stated_unverified"
    lines = analyze._render(report).splitlines()
    assert "  True revenue          : N/A (not established)" in lines
    assert ("  Zelle deposits: $7,734.56 (4), captured rows only; in True revenue and held for review: N/A (not "
            "established) (Mark Zelle Payments as True Revenue: Yes; --zelle-true-revenue no excludes them)") in lines
    assert not any("in True revenue," in line or "held for review (" in line for line in lines)


def test_render_of_an_unestablished_statement_keeps_the_zelle_non_revenue_part():
    import analyze

    lines = analyze._render(_unestablished("Z4_TRUCK", 9000.0)).splitlines()
    assert ("  Zelle deposits: $9,000.00 (1), captured rows only; in True revenue and held for review: N/A (not "
            "established), $9,000.00 non-revenue (Mark Zelle Payments as True Revenue: Yes; --zelle-true-revenue no "
            "excludes them)") in lines


def test_render_of_an_established_statement_keeps_today_s_zelle_line():
    """The established line is byte-identical to the one
    test_render_prints_the_yes_figures_and_the_zelle_line_by_default pins."""
    import analyze

    assert ("  Zelle deposits: $7,734.56 (4): $1,234.56 in True revenue, $6,500.00 held for review "
            "(Mark Zelle Payments as True Revenue: Yes; --zelle-true-revenue no excludes them)") in analyze._render(
        _z1().accounts[0]).splitlines()


def test_the_batch_row_of_an_unestablished_statement_leaves_the_zelle_in_true_cell_empty():
    from pathlib import Path

    row = batch._row(Path("fabricated.md"), _unestablished())
    assert (row["zelle_in_true_revenue_total"], row["zelle_deposit_total"], row["true_revenue_total"]) == (
        "", "7734.56", "")
    assert row["revenue_established"] == "NO"
    established = batch._row(Path("fabricated.md"), _z1().accounts[0])
    assert (established["zelle_in_true_revenue_total"], established["zelle_deposit_total"]) == ("1234.56", "7734.56")


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


# --- The owner's request of 2026-10-06 (lender payment changes; R2-OW18, I2): seven columns right after
# recurring_debit_groups, counts by kind and the items as kind:lender_label. Fabricated rows
# (tests/zelle_setting_fixtures.py: one KAPITUS debit, so no change).


def test_the_batch_csv_carries_the_lender_payment_change_columns():
    from pathlib import Path

    from tests import zelle_setting_fixtures as fx

    # Audit round 3, R3-B05 (the owner's answer of 2026-10-07 to R3-25): and the catch-up count, before the items.
    start = batch.FIELDS.index("recurring_debit_groups") + 1
    assert batch.FIELDS[start:start + 8] == [
        "lender_payment_decreases", "lender_payment_increases", "lender_payment_cadence_changes",
        "lender_payment_new_streams", "lender_payment_pauses", "lender_payment_possible_stops",
        "lender_payment_catch_ups", "lender_payment_changes"]
    row = batch._row(Path("fabricated.md"), fx.document(fx.FREE).accounts[0])
    assert [row[name] for name in batch.FIELDS[start:start + 8]] == [0, 0, 0, 0, 0, 0, 0, ""]
    columns = batch._payment_change_columns([
        {"kind": "decrease", "lender_label": "KAPITUS", "lender_state": "confirmed"},
        {"kind": "decrease", "lender_label": "KAPITUS", "lender_state": "confirmed", "schedule_confirmed": False},
        {"kind": "stop", "lender_label": "Unidentified lender obligation (weekly, 300.00)", "lender_state": "potential",
         "stop_confirmed": False}])
    assert (columns["lender_payment_decreases"], columns["lender_payment_possible_stops"]) == (2, 1)
    assert columns["lender_payment_changes"] == (
        "decrease:KAPITUS; decrease:KAPITUS (possible); stop:Unidentified lender obligation (weekly, 300.00) (potential)")


# --- Audit round 2, R2-B16 (R52; true revenue spec §10.4): the triage CSV reads the dashboard's revenue rules. The
# four fabricated statements of tests/test_analyze_cli.py (T1 to T4), analysed by the real per-account path.

_EMPTY_WHEN_NOT_ESTABLISHED = ("true_revenue_total", "counted_flagged_total", "excluded_pending_review_total",
                               "unverified_deposit_total", "maximum_revenue", "verified_revenue_total")


def _cli_row(report):
    from pathlib import Path
    return batch._row(Path("fabricated.md"), report)


def test_the_batch_columns_name_the_identity_and_the_flags():
    assert "revenue_reconciles" not in batch.FIELDS
    start = batch.FIELDS.index("maximum_revenue")
    assert batch.FIELDS[start:start + 7] == [
        "maximum_revenue", "revenue_tiers_sum_to_posted", "revenue_reconciliation_delta", "revenue_balanced",
        "revenue_established", "verified_revenue_established", "cash_flow"]


def test_t1_the_batch_row_of_a_tied_ledger_is_balanced():
    from tests.test_analyze_cli import ties

    row = _cli_row(ties())
    assert (row["revenue_balanced"], row["revenue_established"], row["verified_revenue_established"],
            row["revenue_tiers_sum_to_posted"]) == ("yes", "yes", "yes", "yes")
    assert (row["true_revenue_total"], row["maximum_revenue"], row["needs_review"]) == ("2500.00", "2500.00", "")


def test_t2_the_batch_row_of_a_misread_opening_is_not_balanced_and_needs_review():
    from tests.test_analyze_cli import misread_opening

    row = _cli_row(misread_opening())
    assert (row["revenue_tiers_sum_to_posted"], row["revenue_established"], row["revenue_balanced"],
            row["needs_review"]) == ("yes", "yes", "NO", "REVIEW")
    assert row["true_revenue_total"] != ""


def test_t3_the_batch_row_of_a_dropped_credit_leaves_the_figures_empty():
    from tests.test_analyze_cli import dropped_credit

    row = _cli_row(dropped_credit())
    assert all(row[key] == "" for key in _EMPTY_WHEN_NOT_ESTABLISHED)
    assert (row["revenue_established"], row["verified_revenue_established"], row["revenue_balanced"]) == (
        "NO", "NO", "NO")
    # Non-revenue, the deposits and the identity's delta stay.
    assert row["non_revenue_total"] != "" and row["total_deposits"] == "3200.00"
    assert row["revenue_reconciliation_delta"] == "0.00"
    assert row["needs_review"] == "REVIEW"


def test_t4_only_the_new_term_asks_for_review_where_the_revenue_is_not_established():
    from tests.test_analyze_cli import stated_above

    report = stated_above()
    assert report.quality.corporate_use == "approved" and report.metrics.revenue_review_required is False
    row = _cli_row(report)
    assert row["needs_review"] == "REVIEW"
    assert row["true_revenue_total"] == "" and row["revenue_established"] == "NO"
    assert row["summary_reconciles"] == "n/a" and row["transaction_detail_reliable"] == "yes"


def test_the_error_row_carries_only_the_file_the_review_and_the_class_name(monkeypatch, tmp_path):
    md = tmp_path / "statement.md"
    md.write_text("--- Page 1 ---\n\nfabricated\n", encoding="utf-8")
    out = tmp_path / "triage.csv"

    def boom(markdown, **kwargs):
        raise RuntimeError("fabricated failure")

    monkeypatch.setattr(batch, "analyze_document", boom)
    monkeypatch.setattr(sys, "argv", ["batch.py", str(md), "--out", str(out)])
    monkeypatch.setenv("TELEMETRY_DISABLED", "1")
    batch.main()
    with open(out, newline="", encoding="utf-8") as handle:
        [row] = list(csv.DictReader(handle))
    assert {key for key, value in row.items() if value} == {"file", "needs_review", "error"}
    assert (row["needs_review"], row["error"]) == ("REVIEW", "RuntimeError")


# --- Audit round 3, R3-B22 (R3-68; the owner's Q7 of 2026-10-02: True revenue the default withholding basis, the others
# selectable; true revenue spec §11, §13): the row names the basis its withholding columns divide by, which each run
# reads from WITHHOLDING_DENOMINATOR_MODE, so two CSVs with the same header no longer read alike on different bases.
# Fabricated rows (tests/test_copied_memos.py's BASIS_ROWS: CONTOSO BAKERY LLC, March 2031).


def test_r3_68_the_basis_columns_sit_before_the_withholding_figures():
    start = batch.FIELDS.index("insurance_total") + 1
    assert batch.FIELDS[start:][:5] == [
        "withholding_denominator_mode", "withholding_denominator_label", "withholding_numerator",
        "withholding_denominator", "withholding_rate"]


def test_r3_68_the_row_names_its_basis_beside_its_denominator_and_rate(monkeypatch):
    from pathlib import Path

    from tests.test_copied_memos import basis_report

    rows = {mode: batch._row(Path("contoso.md"), basis_report(monkeypatch, mode))
            for mode in ("true_revenue", "legacy_eligible_deposits", "verified_revenue")}
    read = {mode: (row["withholding_denominator_mode"], row["withholding_denominator_label"],
                   row["withholding_denominator"], row["withholding_rate"]) for mode, row in rows.items()}
    assert read == {
        "true_revenue": ("true_revenue", "True revenue", "25000.00", "13.60"),
        "legacy_eligible_deposits": ("legacy_eligible_deposits", "Legacy eligible deposits", "30000.00", "11.33"),
        "verified_revenue": ("verified_revenue", "Verified revenue", "20000.00", "17.00")}
    # needs_review reads as before on every basis.
    assert {row["needs_review"] for row in rows.values()} == {""}


def test_r3_68_an_unestablished_basis_names_its_basis_and_leaves_its_figures_empty(monkeypatch):
    from pathlib import Path

    from tests.test_withholding_basis_unestablished import _report

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "true_revenue")
    row = batch._row(Path("contoso.md"), _report())
    assert (row["withholding_denominator_mode"], row["withholding_denominator_label"]) == (
        "true_revenue", "True revenue")
    assert (row["withholding_denominator"], row["withholding_rate"]) == ("", "")
    assert row["needs_review"] == "REVIEW"


def test_r3_68_the_error_row_leaves_the_basis_cells_empty(monkeypatch, tmp_path):
    md = tmp_path / "statement.md"
    md.write_text("--- Page 1 ---\n\nfabricated\n", encoding="utf-8")
    out = tmp_path / "triage.csv"

    def boom(markdown, **kwargs):
        raise RuntimeError("fabricated failure")

    monkeypatch.setattr(batch, "analyze_document", boom)
    monkeypatch.setattr(sys, "argv", ["batch.py", str(md), "--out", str(out)])
    monkeypatch.setenv("TELEMETRY_DISABLED", "1")
    batch.main()
    with open(out, newline="", encoding="utf-8") as handle:
        [row] = list(csv.DictReader(handle))
    assert (row["withholding_denominator_mode"], row["withholding_denominator_label"]) == ("", "")
