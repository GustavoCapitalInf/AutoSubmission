"""The final review of round 2, F1 (true revenue spec §9.1, §9.2, §10.1, §10.4, §10.8, §11; the owner's ruling of
2026-10-02 on the underwriter's Q7, R2-OW14, beside audit fix batch B11's I51 and the final review's M10): a statement
whose withholding basis is not established publishes no withholding rate.

R2-OW14 made True revenue the default withholding basis. A statement whose revenue is not established (its captured
credits are not the money the bank's Total counts) read True as N/A on the dashboard, yet still published a confirmed
withholding rate over that partial True, with `withholding_review_required` false, and its downloads printed the N/A
figure as the withholding basis. The package already refused the rate on such a member (M10). Now the statement does
too: where the account's basis is True revenue and its revenue is not established, or Verified revenue and its
Verified figure is not, the served copy nulls the confirmed withholding rate, the potential withholding exposure and
each potential lender's exposure (and the basis that lender row would divide by), sets `withholding_review_required`
and `withholding_basis_unestablished`; the downloads leave the basis figures empty; the CLI prints them as N/A; the
package does the same per member and for its own figures. The legacy basis (the bank's own deposits) is unchanged.

Fabricated statements only (CONTOSO BAKERY LLC at Sample Bank, March 2031; NORTHWIND SUPPLY LLC pays it, KAPITUS is
its confirmed funder and TARNMOOR FINANCE a potential lender; whole-dollar amounts), analysed by the real per-account
path (`analysis.pipeline._account_report`) with the real `reconcile()`."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import pytest

from tests.webapp_js_harness import NODE, run_dashboard

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO BAKERY LLC CO ID:0000000002 CCD"
SALE = "NORTHWIND SUPPLY LLC DES:PAYMENT ID:{n}"
POTENTIAL = "ACH DEBIT TARNMOOR FINANCE PAYMENT {n:04d}"
#: What the downloads leave empty, and what the served copy nulls, where the basis is not established.
BASIS_FIGURES = ("eligible_deposits", "withholding_denominator", "potential_withholding_denominator")
RATE_FIGURES = ("withholding_rate", "potential_withholding_exposure")


def _report(*, dropped=True, month=3, number="000000001010"):
    """One month of CONTOSO BAKERY LLC: three NORTHWIND payments of 10,000 (the third lost by the capture when
    `dropped`, its balance still printed), four KAPITUS payments of 850 and five TARNMOOR FINANCE payments of 90. The
    bank's summary prints credits 30,000 and debits 3,850, so it reconciles; with a credit lost the captured credits
    (20,000) are not the Total, and the revenue is not established."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    rows = [(2, SALE.format(n=1), 10000.0), (9, SALE.format(n=2), 10000.0), (16, SALE.format(n=3), 10000.0)]
    rows += [(day, KAPITUS, -850.0) for day in (6, 13, 20, 27)]
    rows += [(day, POTENTIAL.format(n=day), -90.0) for day in (3, 10, 17, 24, 26)]
    rows.sort(key=lambda row: row[0])
    balance, transactions = 5000.0, []
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        if dropped and text == SALE.format(n=3):
            continue
        transactions.append(Transaction(date=f"2031-{month:02d}-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(
        bank="Sample Bank", account_name="CONTOSO BAKERY LLC", account_number=number,
        period_start=f"2031-{month:02d}-01", period_end=f"2031-{month:02d}-28", beginning_balance=5000.0,
        ending_balance=balance, currency="USD", currency_source="printed", stated_total_credits=30000.0,
        stated_total_debits=3850.0, transactions=transactions,
    )
    return pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )


def _stored(monkeypatch, mode, **kwargs):
    from analysis.pipeline import DocumentReport
    from analysis.serialization import document_report_to_dict

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    return document_report_to_dict(DocumentReport(accounts=[_report(**kwargs)]))


def _served(payload, *, export=False):
    from webapp.app import _displayed
    return _displayed(payload, settings={}, export=export)


def _job(job_id, payload):
    from webapp.jobs import Job
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def _package(*members):
    from webapp.app import _package_analysis
    return _package_analysis([_job(job_id, payload) for job_id, payload in members], settings={})


# ---------------------------------------------------------------- the served statement

@pytest.mark.parametrize("mode", ["true_revenue", "verified_revenue"])
def test_f1_a_revenue_basis_not_established_publishes_no_rate_and_asks_for_review(monkeypatch, mode):
    stored = _stored(monkeypatch, mode)
    assert stored["metrics"]["deposits_source"] == "bank_stated_reconciled"
    # The analysis itself is unchanged: the stored payload keeps the rate over the partial figure.
    assert stored["metrics"]["withholding_rate"] == pytest.approx(17.0)
    snapshot = json.dumps(stored, sort_keys=True)
    served = _served(stored)
    metrics = served["metrics"]
    assert metrics["withholding_denominator_mode"] == mode
    assert metrics["revenue_established"] is False and metrics["verified_revenue_established"] is False
    assert metrics["withholding_rate"] is None and metrics["potential_withholding_exposure"] is None
    assert metrics["withholding_review_required"] is True
    assert metrics["withholding_basis_unestablished"] is True
    # The served copy keeps the basis figures (the package sums its members' and refuses the rate itself, M10); the
    # dashboard reads the flag and the downloads leave them empty. The numerators and the legacy basis are kept.
    assert metrics["withholding_denominator"] == metrics["eligible_deposits"] == 20000.0
    assert metrics["withholding_numerator"] == 3400.0 and metrics["potential_withholding_numerator"] == 450.0
    assert metrics["legacy_eligible_deposits"] == 30000.0
    (lender,) = served["detection"]["potential_lenders"]
    assert lender["funder"] == "Tarnmoor Finance" and lender["debit_count"] == 5 and lender["total_debited"] == 450.0
    assert lender["potential_withholding_exposure"] is None and lender["eligible_deposit_denominator"] is None
    # A copy: the stored analysis is never rewritten.
    assert json.dumps(stored, sort_keys=True) == snapshot


def test_f1_the_legacy_basis_keeps_its_rate(monkeypatch):
    served = _served(_stored(monkeypatch, "legacy_eligible_deposits"))
    metrics = served["metrics"]
    assert metrics["revenue_established"] is False
    assert metrics["withholding_rate"] == pytest.approx(3400.0 / 30000.0 * 100)
    assert metrics["potential_withholding_exposure"] == pytest.approx(1.5)
    assert metrics["withholding_review_required"] is False
    assert "withholding_basis_unestablished" not in metrics
    (lender,) = served["detection"]["potential_lenders"]
    assert lender["eligible_deposit_denominator"] == 30000.0 and lender["potential_withholding_exposure"] == 1.5


def test_f1_an_established_statement_is_served_as_before(monkeypatch):
    stored = _stored(monkeypatch, "true_revenue", dropped=False)
    served = _served(stored)
    metrics = served["metrics"]
    assert metrics["revenue_established"] is True
    assert "withholding_basis_unestablished" not in metrics
    assert {key: metrics[key] for key in stored["metrics"]} == stored["metrics"]
    assert metrics["withholding_rate"] == pytest.approx(3400.0 / 30000.0 * 100)
    assert served["detection"]["potential_lenders"] == stored["detection"]["potential_lenders"]


# ---------------------------------------------------------------- the downloads

def test_f1_the_statement_downloads_leave_the_basis_empty(monkeypatch):
    from webapp.app import _account_analysis_rows, _analysis_csv

    exported = _served(_stored(monkeypatch, "true_revenue"), export=True)
    metrics = exported["metrics"]
    for key in (*BASIS_FIGURES, *RATE_FIGURES):
        assert metrics[key] is None, key
    assert metrics["withholding_numerator"] == 3400.0 and metrics["legacy_eligible_deposits"] == 30000.0
    (lender,) = exported["detection"]["potential_lenders"]
    assert lender["eligible_deposit_denominator"] is None and lender["potential_withholding_exposure"] is None
    rows = {(section, field): value for section, field, value in _account_analysis_rows(exported)}
    for key in (*BASIS_FIGURES, *RATE_FIGURES):
        assert rows[("metrics", key)] == "", key
    assert rows[("metrics", "withholding_basis_unestablished")] is True
    cells = {(row[0], row[1]): row[2] for row in csv.reader(io.StringIO(_analysis_csv(exported))) if len(row) >= 3}
    assert cells[("metrics", "withholding_denominator")] == "" and cells[("metrics", "withholding_rate")] == ""
    # An established statement's download keeps every figure.
    established = _served(_stored(monkeypatch, "true_revenue", dropped=False), export=True)["metrics"]
    assert established["withholding_denominator"] == 30000.0
    assert established["withholding_rate"] == pytest.approx(3400.0 / 30000.0 * 100)


# ---------------------------------------------------------------- the package

def test_f1_the_package_follows_the_rule_per_member_and_for_its_own_figures(monkeypatch):
    from webapp.app import _package_for_export

    package = _package(("mar", _stored(monkeypatch, "true_revenue")))
    (row,) = package["documents"]
    assert row["withholding_rate"] is None and row["potential_withholding_exposure"] is None
    assert row["withholding_review_required"] is True and row["withholding_basis_unestablished"] is True
    totals = package["totals"]
    assert totals["package_withholding_rate"] is None and totals["potential_withholding_exposure"] is None
    assert totals["withholding_review_required"] is True and totals["withholding_basis_unestablished"] is True
    (rollup,) = package["potential_lenders"]
    assert rollup["potential_withholding_exposure"] is None and rollup["eligible_deposit_denominator"] is None
    (match,) = package["detection"]["potential_lenders"]
    assert match["potential_withholding_exposure"] is None and match["eligible_deposit_denominator"] is None
    exported = _package_for_export(package)
    for key in BASIS_FIGURES:
        assert exported["totals"][key] is None, key
    for key in ("withholding_denominator", "potential_withholding_denominator"):
        assert exported["documents"][0][key] is None, key
    assert exported["totals"]["withholding_numerator"] == 3400.0


def test_f1_a_package_with_one_member_not_established_marks_its_own_figures_only(monkeypatch):
    package = _package(("mar", _stored(monkeypatch, "true_revenue", dropped=False)),
                       ("apr", _stored(monkeypatch, "true_revenue", month=4)))
    rows = {row["id"]: row for row in package["documents"]}
    assert rows["mar"]["withholding_rate"] == pytest.approx(3400.0 / 30000.0 * 100)
    assert "withholding_basis_unestablished" not in rows["mar"]
    assert rows["apr"]["withholding_rate"] is None and rows["apr"]["withholding_basis_unestablished"] is True
    totals = package["totals"]
    assert totals["package_withholding_rate"] is None and totals["withholding_basis_unestablished"] is True
    # Every member established: the package publishes its rate and no flag.
    whole = _package(("mar", _stored(monkeypatch, "true_revenue", dropped=False)),
                     ("apr", _stored(monkeypatch, "true_revenue", dropped=False, month=4)))
    assert whole["totals"]["package_withholding_rate"] == pytest.approx(6800.0 / 60000.0 * 100, abs=0.01)
    assert "withholding_basis_unestablished" not in whole["totals"]
    assert whole["potential_lenders"][0]["eligible_deposit_denominator"] == 60000.0


def test_f1_a_legacy_package_keeps_its_rate(monkeypatch):
    package = _package(("mar", _stored(monkeypatch, "legacy_eligible_deposits")))
    assert package["totals"]["package_withholding_rate"] == pytest.approx(11.33)
    assert "withholding_basis_unestablished" not in package["totals"]
    assert "withholding_basis_unestablished" not in package["documents"][0]


# ---------------------------------------------------------------- the CLI

def _line(text, label):
    (line,) = [line for line in text.splitlines() if line.startswith(f"  {label}")]
    return line


def test_f1_the_cli_prints_the_rate_and_the_basis_as_n_a(monkeypatch):
    import analyze
    import batch

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "true_revenue")
    report = _report()
    text = analyze._render(report)
    assert _line(text, "Lender debits") == (
        "  Lender debits         : 4 row(s), $3,400.00  (withholding N/A (not established))")
    assert _line(text, "Withholding working") == (
        "  Withholding working   : $3,400.00 / N/A (not established) True revenue")
    assert _line(text, "Potential debits") == (
        "  Potential debits      : 5 row(s), $450.00 (exposure N/A (not established); review required)")
    assert _line(text, "Potential working") == "  Potential working     : $450.00 / N/A (not established) True revenue"
    assert "    - Tarnmoor Finance: 5 debit(s), $450.00; N/A (not established) exposure / N/A (not established) " \
           "deposits" in text.splitlines()
    row = batch._row(Path("contoso.pdf"), report)
    for key in ("withholding_denominator", "withholding_rate", "potential_withholding_denominator",
                "potential_withholding_exposure"):
        assert row[key] == "", key
    assert row["withholding_numerator"] == "3400.00" and row["needs_review"] == "REVIEW"
    # The legacy basis prints as before.
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "legacy_eligible_deposits")
    legacy = _report()
    text = analyze._render(legacy)
    assert _line(text, "Lender debits") == "  Lender debits         : 4 row(s), $3,400.00  (withholding 11.33%)"
    assert _line(text, "Withholding working") == (
        "  Withholding working   : $3,400.00 / $30,000.00 Legacy eligible deposits")
    assert batch._row(Path("contoso.pdf"), legacy)["withholding_rate"] == "11.33"


# ---------------------------------------------------------------- the dashboard

@needs_node
def test_f1_the_dashboard_reads_the_basis_as_n_a_and_says_why(monkeypatch, tmp_path):
    from tests.test_webapp_true_revenue_ui import BASIS_ROWS, METRIC_ROWS, _open

    served = _served(_stored(monkeypatch, "true_revenue"))
    package = _package(("mar", _stored(monkeypatch, "true_revenue")))
    result = run_dashboard(METRIC_ROWS + BASIS_ROWS + _open("s", served) + f"""
const statement = basis(metricRows(els.metricsGrid.innerHTML));
currentJobIds = ['mar']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{statement, package: basis(metricRows(els.metricsGrid.innerHTML))}}));
""")
    statement = result["statement"]
    assert statement["Withholding Basis"]["value"] == "N/A"
    assert statement["Confirmed Withholding"] == {
        "value": "N/A",
        "note": "The withholding basis (true revenue) is not established, so no rate is published; analyst review "
                "is required"}
    assert statement["Potential Withholding Exposure"] == {
        "value": "N/A",
        "note": "$450.00 potential lender debits; the withholding basis (true revenue) is not established, so no "
                "exposure is published; analyst review is required"}
    package_rows = result["package"]
    assert package_rows["Withholding Basis"]["value"] == "N/A"
    assert package_rows["Confirmed Withholding"]["value"] == "N/A"
    assert package_rows["Confirmed Withholding"]["note"] == (
        "The withholding basis (true revenue) is not established on every statement, so no rate is published; "
        "analyst review is required")


@needs_node
def test_f1_a_potential_lender_row_reads_n_a_where_the_basis_is_not_established():
    result = run_dashboard("""
const row = lenderRowHtml({funder: 'Tarnmoor Finance', classification: 'potential_lender', debit_count: 5,
  total_debited: 450, potential_lender_debit_total: 450, eligible_deposit_denominator: null,
  potential_withholding_exposure: null}, 'USD');
const legacy = lenderRowHtml({funder: 'Tarnmoor Finance', classification: 'potential_lender', debit_count: 5,
  total_debited: 450, potential_lender_debit_total: 450, eligible_deposit_denominator: 30000,
  potential_withholding_exposure: 1.5}, 'USD');
console.log(JSON.stringify({row, legacy}));
""")
    assert "<td>N/A</td>" in result["row"]
    assert "1.50%" in result["legacy"] and "$30,000.00 withholding basis" in result["legacy"]


# ---------------------------------------------------------------- the review decision (the fix run's review round 1)
# The ruling sends a statement whose basis is not established to review. A statement whose ledger does not reconcile is
# already `manual_review_required`, and one with potential lender debits (the statement above) already reads review, so
# the shape that shows the decision is a reconciled ledger whose captured credits are not the bank's Total.

FABRIKAM_DEBIT = "FABRIKAM SUPPLY ACH DEBIT 0001"
FABRIKAM_REVERSAL = "FABRIKAM SUPPLY ACH REVERSAL 0001"


def _reconciled_report(*, month=3, totals_count_the_pair=False):
    """One month of CONTOSO BAKERY LLC whose ledger reconciles: three NORTHWIND payments of 10,000, four KAPITUS
    payments of 850, and a FABRIKAM SUPPLY debit of 300 reversed two days later. The bank's summary prints credits
    30,000 and debits 3,400 (its Totals leave the reversed pair out), so the ledger reconciles (`reconciliation.ok`, the
    quality approved) while the captured credits (30,300) are not the Total: the revenue is not established. With
    `totals_count_the_pair` the Totals count the pair (30,300 and 3,700) and the revenue is established. No potential
    lender and no held credit, so no other review gate fires."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    rows = [(2, SALE.format(n=1), 10000.0), (9, SALE.format(n=2), 10000.0), (16, SALE.format(n=3), 10000.0)]
    rows += [(day, KAPITUS, -850.0) for day in (6, 13, 20, 27)]
    rows += [(19, FABRIKAM_DEBIT, -300.0), (21, FABRIKAM_REVERSAL, 300.0)]
    rows.sort(key=lambda row: row[0])
    balance, transactions = 5000.0, []
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2031-{month:02d}-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    pair = 300.0 if totals_count_the_pair else 0.0
    statement = Statement(
        bank="Sample Bank", account_name="CONTOSO BAKERY LLC", account_number="000000001010",
        period_start=f"2031-{month:02d}-01", period_end=f"2031-{month:02d}-28", beginning_balance=5000.0,
        ending_balance=balance, currency="USD", currency_source="printed", stated_total_credits=30000.0 + pair,
        stated_total_debits=3400.0 + pair, transactions=transactions,
    )
    return pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )


def _reconciled_stored(monkeypatch, mode, **kwargs):
    from analysis.pipeline import DocumentReport
    from analysis.serialization import document_report_to_dict

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    return document_report_to_dict(DocumentReport(accounts=[_reconciled_report(**kwargs)]))


@pytest.mark.parametrize("mode", ["true_revenue", "verified_revenue"])
def test_f1_r1_a_reconciled_statement_whose_basis_is_not_established_sends_its_package_to_review(monkeypatch, mode):
    stored = _reconciled_stored(monkeypatch, mode)
    served = _served(stored)
    metrics = served["metrics"]
    # The shape: the ledger reconciles and nothing else gates.
    assert stored["reconciliation"]["ok"] is True and served["quality"]["corporate_use"] == "approved"
    assert metrics["deposits_source"] == "bank_stated_reconciled"
    assert (metrics["total_deposits"], metrics["effective_total_deposits"]) == (30300.0, 30000.0)
    assert metrics["revenue_established"] is False and metrics["revenue_review_required"] is False
    assert metrics["potential_lender_debit_total"] == 0.0 and metrics["potential_withholding_review_required"] is False
    assert metrics["withholding_basis_unestablished"] is True and metrics["withholding_rate"] is None
    # Its package goes to review, as the statement does (the dashboard test below).
    package = _package(("mar", stored))
    assert package["totals"]["decision"] == "review_required"
    assert package["totals"]["package_withholding_rate"] is None
    # The control: the Totals count the pair, the revenue is established and the package is approved.
    control = _reconciled_stored(monkeypatch, mode, month=4, totals_count_the_pair=True)
    assert "withholding_basis_unestablished" not in _served(control)["metrics"]
    assert _package(("apr", control))["totals"]["decision"] == "approved"
    # Beside that established member, the package still goes to review.
    both = _package(("mar", stored), ("apr", control))
    assert both["totals"]["decision"] == "review_required"
    assert {row["id"]: row.get("withholding_basis_unestablished") for row in both["documents"]} == {
        "mar": True, "apr": None}


def test_f1_r1_the_legacy_basis_keeps_the_decision(monkeypatch):
    stored = _reconciled_stored(monkeypatch, "legacy_eligible_deposits")
    served = _served(stored)
    assert served["metrics"]["revenue_established"] is False
    assert "withholding_basis_unestablished" not in served["metrics"]
    package = _package(("mar", stored))
    assert package["totals"]["decision"] == "approved"
    # The legacy basis is the bank's own Total (less lender funding), established whatever the capture.
    assert package["totals"]["package_withholding_rate"] == pytest.approx(3400.0 / 30000.0 * 100, abs=0.01)


@needs_node
@pytest.mark.parametrize("mode, decision", [("true_revenue", "Review required"), ("verified_revenue", "Review required"),
                                            ("legacy_eligible_deposits", "Approved")])
def test_f1_r1_the_dashboard_s_statement_decisions_read_review(monkeypatch, mode, decision):
    """The statement's pill, its decision as accountDecision returns it (the Recent list's dot reads it too), the
    statement window's subtitle, the summary an analyst copies, and the package's pill."""
    from tests.test_webapp_true_revenue_ui import _open

    stored = _reconciled_stored(monkeypatch, mode)
    served = _served(stored)
    package = _package(("mar", stored))
    result = run_dashboard(_open("s", served) + f"""
const pill = els.decisionPill.textContent;
const own = accountDecision(currentAnalysis);
generateSummary();
const summary = els.summaryBox.textContent;
openStatementModal('s');
renderStatementModal('s', {json.dumps(served)}, '');
const subtitle = els.statementModalSubtitle.textContent;
currentJobIds = ['mar']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{pill, own, summary, subtitle, packagePill: els.decisionPill.textContent}}));
""")
    assert result["own"] == ("approved" if decision == "Approved" else "review_required")
    assert result["pill"] == decision
    assert result["summary"].endswith(f"Status: {labelled(decision)}.")
    assert result["subtitle"].endswith(f"- {labelled(decision)}")
    assert result["packagePill"] == f"Package decision · {decision}"


def labelled(decision):
    """The words `labelize` gives a decision (the subtitle and the summary), beside the pill's sentence case."""
    return {"Review required": "review required", "Approved": "approved"}[decision]


@needs_node
def test_f1_r1_the_flag_alone_moves_the_decision(monkeypatch):
    served = _served(_reconciled_stored(monkeypatch, "true_revenue"))
    plain = {**served, "metrics": {key: value for key, value in served["metrics"].items()
                                   if key != "withholding_basis_unestablished"}}
    control = _served(_reconciled_stored(monkeypatch, "true_revenue", totals_count_the_pair=True))
    result = run_dashboard(f"""
console.log(JSON.stringify([accountDecision({json.dumps(served)}), accountDecision({json.dumps(plain)}),
                            accountDecision({json.dumps(control)})]));
""")
    assert result == ["review_required", "approved", "approved"]


@needs_node
def test_f1_r1_a_decision_that_already_reads_review_keeps_its_words(monkeypatch):
    """The flag sends a passing decision to review; a statement already in review keeps its own words (a ledger that
    does not reconcile reads "manual review required", as before), and a summary-only one goes to review."""
    served = _served(_reconciled_stored(monkeypatch, "true_revenue"))

    def with_quality(corporate_use):
        return {**served, "quality": {**served["quality"], "corporate_use": corporate_use}}

    items = [with_quality(word) for word in ("manual_review_required", "summary_only", "approved")]
    result = run_dashboard(f"""
const items = {json.dumps(items)};
const decisions = items.map((item) => accountDecision(item));
currentAnalysis = items[0]; currentDocument = null; generateSummary();
console.log(JSON.stringify({{decisions, summary: els.summaryBox.textContent}}));
""")
    assert result["decisions"] == ["manual_review_required", "review_required", "review_required"]
    assert result["summary"].endswith("Status: manual review required.")


# ---------------------------------------------------------------- audit round 3, R3-B03 (R3-27): mixed bases
# A package whose members were analysed under different withholding bases summed each member's own basis and published
# one rate over the blend (legacy eligible deposits beside True revenue), labelled "Mixed denominator configuration",
# with no review: an MCA holdback is measured on one revenue definition across the months read (standard §1 point 4,
# §4.4; the owner's Q7, "2 Make True revenue the default"). A package now publishes a rate only on one basis: a mixed one
# publishes no package rate and no potential exposure, names each member's basis and goes to review (F1/M10's
# precedent), while each member row keeps its own basis and rate. Fabricated months of CONTOSO BAKERY LLC (the
# package-matching fixtures' account): a FABRIKAM card deposit of 18,000.00, a DEPOSIT of 6,000.00, a TRANSFER FROM
# SAVINGS of 12,000.00 and four FORWARD FINANCING payments of 1,200.00.

FORWARD = "FORWARD FINANCING DES:PAYMENT ID:ABC INDN:CONTOSO BAKERY LLC CO ID:XYZ CCD"


def _mixed_rows(tag):
    return [
        (3, f"FABRIKAM MERCHANT SVCS DES:DEPOSIT ID:{tag}", 18000.0),
        (10, "DEPOSIT", 6000.0),
        (12, "ONLINE TRANSFER FROM SAVINGS", 12000.0),
    ] + [(day, FORWARD, -1200.0) for day in (4, 11, 18, 25)]


def _mixed_month(monkeypatch, month, opening, mode=None):
    from tests.test_package_matching import _payload

    if mode is None:
        monkeypatch.delenv("WITHHOLDING_DENOMINATOR_MODE", raising=False)
    else:
        monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    payload = _payload(_mixed_rows(str(month)), month=month, opening=opening)
    monkeypatch.delenv("WITHHOLDING_DENOMINATOR_MODE", raising=False)
    return payload


def _may_june(monkeypatch, may_mode="legacy_eligible_deposits", june_mode=None):
    from tests.test_package_matching import _closing

    may = _mixed_month(monkeypatch, 5, 4000.0, may_mode)
    june = _mixed_month(monkeypatch, 6, _closing(_mixed_rows("5"), 4000.0), june_mode)
    return may, june


def _assert_mixed_refusal(package, modes):
    totals = package["totals"]
    assert totals["package_withholding_rate"] is None and totals["package_withholding_rate_raw"] is None
    assert totals["potential_withholding_exposure"] is None
    assert totals["withholding_review_required"] is True
    assert totals["withholding_basis_mixed"] is True
    assert totals["withholding_denominator_mode"] == "mixed"
    assert totals["withholding_denominator_label"] == "Mixed denominator configuration"
    assert totals["withholding_basis_by_member"] == [
        {"source_job": job, "mode": mode, "label": label} for job, mode, label in modes]
    assert totals["decision"] == "review_required"


LEGACY = ("legacy_eligible_deposits", "Legacy eligible deposits")
TRUE = ("true_revenue", "True revenue")


def test_r3_27_a_package_mixing_bases_publishes_no_rate_and_asks_for_review(monkeypatch):
    may, june = _may_june(monkeypatch)
    package = _package(("may", may), ("jun", june))
    _assert_mixed_refusal(package, [("may", *LEGACY), ("jun", *TRUE)])  # the rate was 16.0, approved
    rows = {row["id"]: row for row in package["documents"]}
    assert rows["may"]["withholding_rate"] == pytest.approx(4800.0 / 36000.0 * 100)
    assert rows["may"]["withholding_denominator_mode"] == "legacy_eligible_deposits"
    assert rows["jun"]["withholding_rate"] == pytest.approx(20.0)
    assert rows["jun"]["withholding_denominator_mode"] == "true_revenue"
    # The order of the members does not matter.
    _assert_mixed_refusal(_package(("jun", june), ("may", may)), [("jun", *TRUE), ("may", *LEGACY)])


def test_r3_27_a_member_stored_with_no_mode_reads_as_legacy_and_mixes(monkeypatch):
    may, june = _may_june(monkeypatch)

    def strip(node):
        if isinstance(node, dict):
            node.pop("withholding_denominator_mode", None)
            node.pop("withholding_denominator_label", None)
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)

    strip(may)
    _assert_mixed_refusal(_package(("may", may), ("jun", june)), [("may", *LEGACY), ("jun", *TRUE)])


def test_r3_27_an_untiered_legacy_member_beside_a_true_member_mixes(monkeypatch):
    from tests.test_webapp_true_revenue import _untiered

    may, june = _may_june(monkeypatch)
    package = _package(("may", _untiered(may)), ("jun", june))
    _assert_mixed_refusal(package, [("may", *LEGACY), ("jun", *TRUE)])
    assert package["totals"]["true_revenue_total"] is None  # True is N/A with an untiered member, as before


def test_r3_27_both_members_on_true_publish_as_before(monkeypatch):
    may, june = _may_june(monkeypatch, may_mode=None)
    totals = _package(("may", may), ("jun", june))["totals"]
    assert totals["package_withholding_rate"] == pytest.approx(20.0)
    assert totals["withholding_denominator_mode"] == "true_revenue"
    assert totals["decision"] == "approved"
    assert "withholding_basis_mixed" not in totals and "withholding_basis_by_member" not in totals


def test_r3_27_a_failed_member_adds_no_basis(monkeypatch):
    from webapp.app import _package_analysis
    from webapp.jobs import Job

    may, june = _may_june(monkeypatch, may_mode=None)
    jobs = [Job(id="may", filename="may.pdf", status="error", analysis=None, content_sha256="may"),
            Job(id="jun", filename="jun.pdf", status="done", analysis=june, content_sha256="jun")]
    totals = _package_analysis(jobs, settings={})["totals"]
    assert totals["withholding_denominator_mode"] == "true_revenue"  # was "mixed"
    assert totals["withholding_denominator_label"] == "True revenue"
    assert "withholding_basis_mixed" not in totals
    assert totals["package_withholding_rate"] == pytest.approx(20.0)
    assert totals["decision"] == "review_required"  # for the failure, as before
    # A package with no ready member keeps today's mode and label.
    none_ready = _package_analysis([jobs[0]], settings={})["totals"]
    assert none_ready["withholding_denominator_mode"] == "legacy_eligible_deposits"
    assert none_ready["withholding_denominator_label"] == "Legacy eligible deposits"


@needs_node
def test_r3_27_the_dashboard_says_why_and_prints_n_a_everywhere(monkeypatch):
    from tests.test_webapp_true_revenue_ui import BASIS_ROWS, METRIC_ROWS

    may, june = _may_june(monkeypatch)
    package = _package(("may", may), ("jun", june))
    result = run_dashboard(METRIC_ROWS + BASIS_ROWS + f"""
currentJobIds = ['may', 'jun']; renderPackageAnalysis({json.dumps(package)});
const cards = basis(metricRows(els.metricsGrid.innerHTML));
generateSummary();
console.log(JSON.stringify({{cards, totals: els.totalsGrid.innerHTML, status: els.statusList.innerHTML,
  summary: els.summaryBox.textContent}}));
""")
    assert result["cards"]["Confirmed Withholding"] == {
        "value": "N/A",
        "note": "The statements were analysed on different withholding bases (1 on legacy eligible deposits, 1 on true "
                "revenue), so no package rate is published; re-analyze them on one basis; analyst review is required"}
    assert result["cards"]["Potential Withholding Exposure"]["value"] == "N/A"
    assert result["cards"]["Withholding Basis"]["value"] == "N/A"
    assert "Confirmed withholding" in result["totals"] and "16%" not in result["totals"]
    assert re.search(r"Confirmed withholding</[^>]+>\s*<[^>]+>N/A", result["status"])
    assert "N/A confirmed withholding" in result["summary"] and "16%" not in result["summary"]

