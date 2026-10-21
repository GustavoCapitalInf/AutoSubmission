"""Audit round 3, R3-B03 (R3-20; true revenue spec §9.1, §10.1, §10.4, §11, §17.1 the R2-OW14 follow-ups (1)): a
revenue withholding basis under a floor publishes no rate.

Since R2-OW14 made True revenue the default withholding basis, the only guard was a basis of $0 or less: $0 of True gave
N/A, `withholding_review_required` and a note, while $1.00 of True published 140,000% (four KAPITUS payments of 350.00
over one dollar) with no flag and no note. A True or Verified basis under WITHHOLDING_BASIS_FLOOR (REVENUE_REVIEW_HELD_FLOOR,
500 in the statement's own unit, the floor T7 already uses) is now read as $0 is: no rate, no potential exposure, each
potential lender's row with no basis and no exposure, `withholding_review_required`, `withholding_basis_below_floor` and
a note that says why; never a gate. The legacy basis (the bank's own deposits less lender funding) keeps today's
behaviour.

Fabricated statements only (CONTOSO TILE LLC at Sample Bank, March 2054; own-account transfers in, KAPITUS its
confirmed funder, NORTHWIND FUNDING WEB PMT a weekly potential payee; neutral amounts), analysed by the real per-account
path (`analysis.pipeline._account_report`) with the real `reconcile()`."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.webapp_js_harness import NODE, run_dashboard
from tests.helpers import _package

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO TILE LLC CO ID:0000000002 CCD"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO TILE LLC CO ID:0000000001 CCD"
TRANSFER = "ONLINE TRANSFER FROM SAV 0000"
POTENTIAL = "NORTHWIND FUNDING WEB PMT"
ZERO_NOTE = "withholding rate is unavailable because True revenue is zero or missing"
ZERO_POTENTIAL_NOTE = "potential withholding exposure is unavailable because True revenue is zero or missing"


def _report(extra=(), *, transfers=True, potential=True, month=3, number="000000001010"):
    """One month of CONTOSO TILE LLC: four own-account transfers in of 9,000.00 (non-revenue) unless `transfers` is
    false, four KAPITUS payments of 350.00, four NORTHWIND FUNDING payments of 200.00 when `potential`, and `extra`
    ((day, description, amount) rows). The bank's summary prints the captured totals, so the revenue is established."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    rows = [(day, TRANSFER, 9000.0) for day in (2, 9, 16, 23)] if transfers else []
    rows += [(day, KAPITUS, -350.0) for day in (3, 10, 17, 24)]
    if potential:
        rows += [(day, POTENTIAL, -200.0) for day in (4, 11, 18, 25)]
    rows += list(extra)
    rows.sort(key=lambda row: row[0])
    balance, transactions = 5000.0, []
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2054-{month:02d}-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(
        bank="Sample Bank", account_name="CONTOSO TILE LLC", account_number=number,
        period_start=f"2054-{month:02d}-01", period_end=f"2054-{month:02d}-28", beginning_balance=5000.0,
        ending_balance=balance, currency="USD", currency_source="printed",
        stated_total_credits=round(sum(t.amount for t in transactions if t.amount > 0), 2),
        stated_total_debits=round(-sum(t.amount for t in transactions if t.amount < 0), 2),
        transactions=transactions,
    )
    return pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )


def _stored(monkeypatch, mode="true_revenue", extra=(), **kwargs):
    from analysis.pipeline import DocumentReport
    from analysis.serialization import document_report_to_dict

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    return document_report_to_dict(DocumentReport(accounts=[_report(extra, **kwargs)]))


def _served(payload):
    from analysis.served_view import displayed
    return displayed(payload, settings={})


def _withholding_notes(metrics):
    return [note for note in metrics["notes"] if "withholding" in note]


def _cash(amount, day=5):
    return [(day, "CASH DEPOSIT", amount)]


# ---------------------------------------------------------------- the helper

@pytest.mark.parametrize(("denominator", "mode", "publishable"), [
    (0.0, "true_revenue", False), (-1.0, "true_revenue", False), (1.0, "true_revenue", False),
    (499.99, "true_revenue", False), (500.0, "true_revenue", True), (20000.0, "true_revenue", True),
    (1.0, "verified_revenue", False), (500.0, "verified_revenue", True),
    # The legacy basis bypasses the floor; a stored payload with no mode reads as legacy.
    (1.0, "legacy_eligible_deposits", True), (0.0, "legacy_eligible_deposits", False), (1.0, None, True),
])
def test_the_helper_reads_the_floor_on_the_revenue_bases_only(denominator, mode, publishable):
    from analysis.revenue import REVENUE_REVIEW_HELD_FLOOR, WITHHOLDING_BASIS_FLOOR, withholding_basis_publishable

    assert WITHHOLDING_BASIS_FLOOR == REVENUE_REVIEW_HELD_FLOOR == 500
    assert withholding_basis_publishable(denominator, mode) is publishable


# ---------------------------------------------------------------- the statement

def test_a_zero_true_basis_reads_as_today(monkeypatch):
    metrics = _stored(monkeypatch)["metrics"]
    assert metrics["true_revenue_total"] == 0.0
    assert metrics["withholding_rate"] is None and metrics["potential_withholding_exposure"] is None
    assert metrics["withholding_review_required"] is True
    assert metrics["withholding_basis_below_floor"] is False
    assert _withholding_notes(metrics) == [ZERO_NOTE, ZERO_POTENTIAL_NOTE]


def test_a_one_dollar_true_basis_publishes_no_rate_and_says_why(monkeypatch):
    stored = _stored(monkeypatch, extra=_cash(1.0))
    metrics = stored["metrics"]
    assert metrics["true_revenue_total"] == 1.0 and metrics["withholding_numerator"] == 1400.0
    assert metrics["withholding_rate"] is None  # was 140000.0
    assert metrics["potential_withholding_exposure"] is None  # was 80000.0
    assert metrics["withholding_review_required"] is True
    assert metrics["withholding_basis_below_floor"] is True
    # The basis is kept: it is a real figure, only under the floor.
    assert metrics["withholding_denominator"] == metrics["potential_withholding_denominator"] == 1.0
    assert _withholding_notes(metrics) == [
        "withholding rate is unavailable because True revenue (1.00 USD) is under the withholding basis floor "
        "(500.00 USD)",
        "potential withholding exposure is unavailable because True revenue (1.00 USD) is under the withholding "
        "basis floor (500.00 USD)",
    ]
    (lender,) = stored["detection"]["potential_lenders"]
    assert lender["funder"] == "Northwind Funding" and lender["total_debited"] == 800.0
    assert lender["eligible_deposit_denominator"] is None and lender["potential_withholding_exposure"] is None
    # The served copy publishes the same figures (no F1 flag: the basis is established).
    served = _served(stored)["metrics"]
    assert served["withholding_rate"] is None and "withholding_basis_unestablished" not in served


def test_the_floor_is_500_in_the_statement_s_unit(monkeypatch):
    under = _stored(monkeypatch, extra=_cash(499.99))["metrics"]
    assert under["withholding_rate"] is None and under["withholding_basis_below_floor"] is True
    at = _stored(monkeypatch, extra=_cash(500.0))
    metrics = at["metrics"]
    assert metrics["withholding_rate"] == pytest.approx(280.0)
    assert metrics["potential_withholding_exposure"] == pytest.approx(160.0)
    assert metrics["withholding_review_required"] is False and metrics["withholding_basis_below_floor"] is False
    assert _withholding_notes(metrics) == []
    (lender,) = at["detection"]["potential_lenders"]
    assert lender["eligible_deposit_denominator"] == 500.0 and lender["potential_withholding_exposure"] == 160.0


def test_the_verified_basis_reads_the_same_floor(monkeypatch):
    # A verified sale of 300.00 and a counted cash deposit of 9,000.00: Verified 300.00, under the floor.
    stored = _stored(monkeypatch, "verified_revenue", extra=[(5, SALE, 300.0), (6, "CASH DEPOSIT", 9000.0)])
    metrics = stored["metrics"]
    assert metrics["verified_revenue_total"] == 300.0
    assert metrics["withholding_rate"] is None and metrics["withholding_basis_below_floor"] is True
    assert _withholding_notes(metrics)[0] == (
        "withholding rate is unavailable because Verified revenue (300.00 USD) is under the withholding basis floor "
        "(500.00 USD)")
    # On True (9,300.00) the same statement publishes.
    true = _stored(monkeypatch, extra=[(5, SALE, 300.0), (6, "CASH DEPOSIT", 9000.0)])["metrics"]
    assert true["withholding_rate"] == pytest.approx(1400.0 / 9300.0 * 100)


def test_the_legacy_basis_publishes_as_today(monkeypatch):
    stored = _stored(monkeypatch, "legacy_eligible_deposits", extra=_cash(1.0), transfers=False)
    metrics = stored["metrics"]
    assert metrics["legacy_eligible_deposits"] == metrics["withholding_denominator"] == 1.0
    assert metrics["withholding_rate"] == pytest.approx(140000.0)
    assert metrics["potential_withholding_exposure"] == pytest.approx(80000.0)
    assert metrics["withholding_review_required"] is False and metrics["withholding_basis_below_floor"] is False
    (lender,) = stored["detection"]["potential_lenders"]
    assert lender["eligible_deposit_denominator"] == 1.0 and lender["potential_withholding_exposure"] == 80000.0


# ---------------------------------------------------------------- the package

def test_a_package_under_the_floor_publishes_no_rate_and_keeps_its_decision(monkeypatch):
    first = _stored(monkeypatch, extra=_cash(200.0), potential=False)
    second = _stored(monkeypatch, extra=_cash(250.0), potential=False, month=4)
    package = _package(("mar", first), ("apr", second))
    totals = package["totals"]
    assert totals["withholding_denominator"] == 450.0 and totals["withholding_numerator"] == 2800.0
    assert totals["package_withholding_rate"] is None and totals["package_withholding_rate_raw"] is None
    assert totals["withholding_review_required"] is True and totals["withholding_basis_below_floor"] is True
    # Never a gate: the package's decision reads as it would with the rate published.
    assert totals["decision"] == "approved"
    for row in package["documents"]:
        assert row["withholding_rate"] is None and row["withholding_review_required"] is True
    published = _package(("mar", first), ("apr", _stored(monkeypatch, extra=[(5, SALE, 20000.0)], potential=False,
                                                        month=4)))
    assert published["totals"]["package_withholding_rate"] == pytest.approx(2800.0 / 20200.0 * 100, abs=0.01)
    assert "withholding_basis_below_floor" not in published["totals"]
    assert published["totals"]["decision"] == "approved"


def test_a_package_under_the_floor_gives_its_potential_lenders_no_basis(monkeypatch):
    package = _package(("mar", _stored(monkeypatch, extra=_cash(200.0))))
    totals = package["totals"]
    assert totals["potential_withholding_exposure"] is None and totals["withholding_basis_below_floor"] is True
    (rollup,) = package["potential_lenders"]
    assert rollup["eligible_deposit_denominator"] is None and rollup["potential_withholding_exposure"] is None
    (match,) = package["detection"]["potential_lenders"]
    assert match["eligible_deposit_denominator"] is None and match["potential_withholding_exposure"] is None


def test_a_legacy_package_under_500_publishes_as_today(monkeypatch):
    stored = _stored(monkeypatch, "legacy_eligible_deposits", extra=_cash(200.0), transfers=False, potential=False)
    totals = _package(("mar", stored))["totals"]
    assert totals["package_withholding_rate"] == pytest.approx(700.0)
    assert totals["withholding_review_required"] is False and "withholding_basis_below_floor" not in totals


# ---------------------------------------------------------------- the dashboard

def test_the_dashboard_s_floor_mirrors_the_python_constant():
    from analysis.revenue import WITHHOLDING_BASIS_FLOOR

    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    (value,) = re.findall(r"^const WITHHOLDING_BASIS_FLOOR = (\d+(?:\.\d+)?);$", source, re.M)
    assert float(value) == WITHHOLDING_BASIS_FLOOR


@needs_node
def test_the_card_reads_n_a_and_says_why_and_the_decision_does_not_move(monkeypatch):
    from tests.test_webapp_true_revenue_ui import BASIS_ROWS, METRIC_ROWS, _open

    served = _served(_stored(monkeypatch, extra=_cash(1.0), potential=False))
    plain = {**served, "metrics": {**served["metrics"], "withholding_basis_below_floor": False,
                                   "withholding_review_required": False}}
    package = _package(("mar", _stored(monkeypatch, extra=_cash(200.0), potential=False)))
    result = run_dashboard(METRIC_ROWS + BASIS_ROWS + _open("s", served) + f"""
const statement = basis(metricRows(els.metricsGrid.innerHTML));
const decisions = [accountDecision({json.dumps(served)}), accountDecision({json.dumps(plain)})];
currentJobIds = ['mar']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{statement, decisions, package: basis(metricRows(els.metricsGrid.innerHTML)),
  floor: WITHHOLDING_BASIS_FLOOR}}));
""")
    assert result["floor"] == 500
    assert result["statement"]["Confirmed Withholding"] == {
        "value": "N/A",
        "note": "The withholding basis (true revenue, $1.00) is under $500.00, so no rate is published; analyst review "
                "is required"}
    # The flag never moves a decision.
    assert result["decisions"][0] == result["decisions"][1]
    assert result["package"]["Confirmed Withholding"] == {
        "value": "N/A",
        "note": "The withholding basis (true revenue, $200.00) is under $500.00, so no rate is published; analyst "
                "review is required"}


@needs_node
def test_the_potential_note_says_why_under_the_floor(monkeypatch):
    from tests.test_webapp_true_revenue_ui import BASIS_ROWS, METRIC_ROWS, _open

    served = _served(_stored(monkeypatch, extra=_cash(1.0)))
    result = run_dashboard(METRIC_ROWS + BASIS_ROWS + _open("s", served) + """
console.log(JSON.stringify(basis(metricRows(els.metricsGrid.innerHTML))));
""")
    assert result["Potential Withholding Exposure"] == {
        "value": "N/A",
        "note": "$800.00 potential lender debits; the withholding basis (true revenue, $1.00) is under $500.00, so no "
                "exposure is published; analyst review is required"}
