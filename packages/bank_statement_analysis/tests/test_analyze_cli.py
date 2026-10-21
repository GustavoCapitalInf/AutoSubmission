"""Audit round 2, R2-B16 (R52; true revenue spec §10.4): the CLI reads the dashboard's revenue rules.

`analyze.py` prints "Revenue reconciliation: Balanced" only where the statement's ledger reconciles and its revenue is
established (app.js statementRevenueBalanced), names the four-tier identity on its own line, and prints a figure the
account's revenue flags do not establish as N/A; `analyze.py --json` carries both flags; `batch.py` names the identity
`revenue_tiers_sum_to_posted`, adds `revenue_balanced`, `revenue_established` and `verified_revenue_established`,
leaves the unestablished figures empty (audit B11's I51) and asks for review when the revenue is not established.

Every statement is fabricated (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE; March 2031; whole-dollar amounts) and analysed by
the real per-account path (`analysis.pipeline._account_report`) with the real `reconcile()`; nothing is set after the
analysis."""
from __future__ import annotations

from pathlib import Path

import analyze
import batch
from tests.helpers import _cp1252_stdout

#: The payers each fabricated account is paid by: never a name the account itself carries (the holder holds).
_PAYERS = {"CONTOSO LLC": ("NORTHWIND SUPPLY LLC", "FABRIKAM INC"), "FABRIKAM LLC": ("NORTHWIND SUPPLY LLC", "CONTOSO INC"),
           "NORTHWIND LLC": ("CONTOSO SUPPLY LLC", "FABRIKAM INC"), "SAMPLE LLC": ("NORTHWIND SUPPLY LLC", "FABRIKAM INC")}
#: The bank-stated credits of the rows below: 1,200 + 800 + 500.
_CREDITS = 2500.0
_DEBITS = 500.0


def _rows(name: str, *, extra_credit: float | None = None) -> list[tuple[int, str, float]]:
    first, second = _PAYERS[name]
    rows = [(3, f"{first} DES:PAYMENT ID:1", 1200.0), (8, f"{second} DES:PAYMENT ID:2", 800.0)]
    if extra_credit is not None:
        rows.append((10, f"{first} DES:PAYMENT ID:3", extra_credit))
    return rows + [(12, "MOBILE DEPOSIT", 500.0), (15, "CARD PURCHASE OFFICE SUPPLY STORE", -300.0),
                   (20, "UTILITY BILL PAY", -200.0)]


def _account(name: str, *, printed_opening: float | None = None, drop: int | None = None,
             stated_credits: float | None = None, stated_debits: float | None = None, extra_credit: float | None = None):
    """One account's Report: the rows' running balances from an opening of 1,000.00; `printed_opening` is the opening
    the statement prints (a misread one), `drop` a row the capture lost (its balance still printed), and the stated
    totals what the bank's summary prints."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    opening, balance, transactions = 1000.0, 1000.0, []
    for index, (day, description, amount) in enumerate(_rows(name, extra_credit=extra_credit)):
        balance = round(balance + amount, 2)
        if index == drop:
            continue
        transactions.append(Transaction(date=f"2031-03-{day:02d}", description=description, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(
        bank="FABRICATED COMMUNITY BANK", account_name=name, account_number="000000001010",
        period_start="2031-03-01", period_end="2031-03-28",
        beginning_balance=opening if printed_opening is None else printed_opening, ending_balance=balance,
        currency="USD", currency_source="printed", stated_total_credits=stated_credits,
        stated_total_debits=stated_debits, transactions=transactions,
    )
    return pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )


def ties():
    """T1: CONTOSO LLC's ledger ties."""
    return _account("CONTOSO LLC")


def misread_opening():
    """T2: FABRIKAM LLC's opening balance misread by $500."""
    return _account("FABRIKAM LLC", printed_opening=1500.0)


def dropped_credit():
    """T3: NORTHWIND LLC's capture lost one $700 credit; the bank's totals are printed."""
    return _account("NORTHWIND LLC", extra_credit=700.0, drop=2, stated_credits=_CREDITS + 700.0, stated_debits=_DEBITS)


def stated_above():
    """T4: SAMPLE LLC's bank prints credits $30 above its rows and no debit total; nothing is held."""
    return _account("SAMPLE LLC", stated_credits=_CREDITS + 30.0)


def _line(text: str, label: str) -> str:
    (line,) = [line for line in text.splitlines() if line.startswith(f"  {label}")]
    return line


def test_t1_a_ledger_that_ties_reads_balanced_and_prints_its_figures():
    report = ties()
    assert report.reconciliation.ok is True and report.metrics.deposits_source == "line_items"
    text = analyze._render(report)
    assert _line(text, "Revenue reconciliation") == "  Revenue reconciliation: Balanced"
    assert _line(text, "Tiers sum to posted") == "  Tiers sum to posted   : yes (delta $0.00)"
    assert _line(text, "True revenue") == "  True revenue          : $2,500.00  (3 credit(s))"
    assert _line(text, "Maximum revenue") == "  Maximum revenue       : $2,500.00"
    assert "N/A" not in text.split("## Metrics")[1].split("## MCA")[0]


def test_t2_a_misread_opening_reads_review_required_and_never_balanced():
    report = misread_opening()
    assert report.reconciliation.ok is False and report.metrics.revenue_tiers_sum_to_posted is True
    text = analyze._render(report)
    assert _line(text, "Revenue reconciliation") == (
        "  Revenue reconciliation: Review required (ledger does not reconcile)")
    assert "balanced" not in text.lower()
    assert _line(text, "Tiers sum to posted") == "  Tiers sum to posted   : yes (delta $0.00)"
    # The revenue is established (the line items are the Total's source), so its figures print.
    assert _line(text, "True revenue").startswith("  True revenue          : $")


def test_t3_a_dropped_credit_reads_n_a_where_the_revenue_is_not_established():
    report = dropped_credit()
    assert report.metrics.deposits_source == "bank_stated_reconciled"
    assert report.metrics.effective_total_deposits == _CREDITS + 700.0 and report.metrics.total_deposits == _CREDITS
    text = analyze._render(report)
    for label in ("True revenue", "Verified revenue", "Counted, not verified", "Held for review",
                  "Unverified deposits", "Maximum revenue"):
        assert _line(text, label).endswith(": N/A (not established)"), label
    # Non-revenue stays: its rows are known non-revenue, captured rows only.
    assert _line(text, "Non-revenue credits").startswith("  Non-revenue credits   : $")
    assert _line(text, "Revenue reconciliation") == (
        "  Revenue reconciliation: Review required (ledger does not reconcile)")


def test_t4_credits_stated_above_the_rows_on_a_tied_ledger_read_review_required():
    report = stated_above()
    assert report.reconciliation.ok is True and report.quality.corporate_use == "approved"
    assert report.metrics.deposits_source == "bank_stated_unverified"
    text = analyze._render(report)
    assert _line(text, "Revenue reconciliation") == (
        "  Revenue reconciliation: Review required (captured credits differ from the bank-stated total)")
    assert _line(text, "True revenue") == "  True revenue          : N/A (not established)"
    assert "balanced" not in text.lower()


def test_the_json_carries_both_revenue_flags_and_keeps_every_figure():
    from analysis.pipeline import DocumentReport
    from analysis.serialization import document_report_to_dict

    from analysis.revenue_view import UNESTABLISHED_WITHHOLDING_KEYS

    for report, flags in ((ties(), (True, True)), (stated_above(), (False, False))):
        document = DocumentReport(accounts=[report])
        payload = analyze._json_safe(document)
        assert (payload["metrics"]["verified_revenue_established"], payload["metrics"]["revenue_established"]) == flags
        stored = document_report_to_dict(document)["metrics"]
        # The final review of round 2, F1: on the True-revenue basis (the default) a statement whose revenue is not
        # established publishes no withholding rate and asks for review, as the dashboard serves it; every other figure
        # is kept.
        moved = (*UNESTABLISHED_WITHHOLDING_KEYS, "withholding_review_required") if not flags[1] else ()
        assert {key: payload["metrics"][key] for key in stored if key not in moved} == {
            key: value for key, value in stored.items() if key not in moved}
        if moved:
            assert all(payload["metrics"][key] is None for key in UNESTABLISHED_WITHHOLDING_KEYS)
            assert payload["metrics"]["withholding_review_required"] is True
            assert payload["metrics"]["withholding_basis_unestablished"] is True


def test_a_flag_computed_from_the_report_matches_the_served_copy():
    """The CLI's flags are the webapp's: analysis/revenue_view.py on the serialized account."""
    from analysis.revenue_view import apply_revenue_view
    from analysis.serialization import report_to_dict

    for report in (ties(), misread_opening(), dropped_credit(), stated_above()):
        served = apply_revenue_view(report_to_dict(report))["metrics"]
        assert analyze._revenue_flags(report) == (served["verified_revenue_established"],
                                                  served["revenue_established"])


# --- Audit 2026-10-13, EXP-5: a redirected stdout on Windows is cp1252, and statement text carries characters it cannot
# encode (ligatures such as U+FB03, private-use glyphs): the report crashed with UnicodeEncodeError and wrote nothing.
# analyze.py now writes UTF-8 to stdout, as --json already does. Given a PDF, it prints one line naming parse.py and
# batch.py and exits 2 (it used to die with a UnicodeDecodeError traceback). The stdout here is a cp1252 TextIOWrapper,
# the redirected stdout of the Windows host, on any host. Fabricated rows (tests/zelle_setting_fixtures.py).


def _run_analyze(monkeypatch, path, analyze_document):
    import sys

    monkeypatch.setattr(analyze, "analyze_document", analyze_document)
    monkeypatch.setattr(sys, "argv", ["analyze.py", str(path)])
    analyze.main()


def test_exp5_a_ligature_in_the_report_reaches_a_redirected_stdout(monkeypatch, tmp_path):
    from tests import zelle_setting_fixtures as fx

    document = fx.document(fx.FREE, holder="CONTOSO OﬃCE LLC")
    md = tmp_path / "SAMPLE.md"
    md.write_text("--- Page 1 ---\n\nfabricated\n", encoding="utf-8")
    stream = _cp1252_stdout(monkeypatch)
    _run_analyze(monkeypatch, md, lambda markdown, **kwargs: document)
    stream.flush()
    text = stream.buffer.getvalue().decode("utf-8")
    assert "# Bank of America - CONTOSO OﬃCE LLC" in text
    assert text == analyze._render(document.accounts[0]).replace("\n", "\r\n") + "\r\n"


def test_exp5_the_markdown_is_read_as_before(monkeypatch, tmp_path):
    """Universal newlines, as `open(..., encoding="utf-8")` read it: a CRLF file reaches the analysis with LF only."""
    from tests import zelle_setting_fixtures as fx

    document, seen = fx.document(fx.FREE), []
    md = tmp_path / "SAMPLE.md"
    md.write_bytes("--- Page 1 ---\r\n\r\nfabricated OﬃCE\r\n".encode("utf-8"))
    _cp1252_stdout(monkeypatch)
    _run_analyze(monkeypatch, md, lambda markdown, **kwargs: seen.append(markdown) or document)
    assert seen == ["--- Page 1 ---\n\nfabricated OﬃCE\n"]


def _refused(monkeypatch, capsys, path):
    import pytest

    def never(markdown, **kwargs):
        raise AssertionError("a PDF must not reach the analysis")

    with pytest.raises(SystemExit) as stopped:
        _run_analyze(monkeypatch, path, never)
    assert stopped.value.code == 2
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1
    assert err.startswith("error: ") and "parse.py" in err and "batch.py" in err
    assert "Traceback" not in err


def test_exp5_a_pdf_gets_a_one_line_error(monkeypatch, tmp_path, capsys):
    pdf = tmp_path / "SAMPLE.PDF"
    pdf.write_bytes(b"%PDF-1.7\n\xe2\xe3\xcf\xd3 fabricated\n")
    _refused(monkeypatch, capsys, pdf)


def test_exp5_a_pdf_under_another_name_gets_the_same_error(monkeypatch, tmp_path, capsys):
    renamed = tmp_path / "SAMPLE.md"
    renamed.write_bytes(b"%PDF-1.7\n\xe2\xe3\xcf\xd3 fabricated\n")
    _refused(monkeypatch, capsys, renamed)
