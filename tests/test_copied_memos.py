"""Audit round 3, R3-B22 (true revenue spec §4's T7, §10.1, §11; the owner's rulings of 2026-10-02 on the underwriter's
Q5, "show a 'returned funder payment' warning", and Q7, True revenue the default withholding basis): the summaries an
analyst copies into a credit memo (`generateSummary`).

R3-01: the statement memo's decision read idle and unverified notes, material potential lender debits and the quality
word, never T7's revenue gate (`metrics.revenue_review_required`), so a statement whose pill read "Review required"
copied "Status: approved."; its decision is now the pill's (`accountDecision`), and both memos state the money held for
review (`revenueSummarySentence`'s held clause, between the verified pair and non-revenue, only where the revenue is
established). R3-67 (the memo half): the package memo listed each funder's paid total only, so a funder whose every
payment bounced read $0.00 beside a withholding rate that keeps its returned payments; each funder line now names its
returned payments, one "- Returned funder payment: ..." line follows per served item, and the sentence names the
returned payments before the rate. R3-68: the memos name the withholding basis their rates divide by.

Fabricated statements only: CONTOSO BAKERY LLC at Sample Bank (2031), FABRIKAM and NORTHWIND payers, the public funders
KAPITUS and ONDECK as the existing fixtures name them, neutral whole-dollar amounts; analysed by the real analysis path
and run through the whole webapp/static/app.js in node (tests/webapp_js_harness.py)."""
from __future__ import annotations

import json
import re

import pytest

from tests.webapp_js_harness import NODE, run_dashboard

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

HOLDER = "CONTOSO BAKERY LLC"
#: A repeat payer: three equal ACH payments from FABRIKAM SUPPLY INC are Verified revenue.
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO BAKERY LLC CO ID:0000000001 CCD"
#: A wire that prints no sender: held for review (`wire_no_sender`).
WIRE = "WIRE TRANSFER IN REF 000000000"
ONDECK_BAKERY = "ONDECK CAPITAL DES:PAYMENT ID:000000003 INDN:CONTOSO BAKERY LLC CO ID:0000000004 CCD"

#: The memo's decision, as the generated text ends.
STATUS = re.compile(r"Status: ([a-z ]+)\.$")
MEMO = "generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));"


def _bakery(wire=None, *, month=3, opening=5000.0, dropped=False):
    """One month of CONTOSO BAKERY LLC whose ledger reconciles: three FABRIKAM payments of 4,000 and, where `wire` is
    given, a wire of that amount printing no sender. The bank's summary prints the credits, so the revenue is
    established; with `dropped` the capture loses the third FABRIKAM payment (its balance still printed), so the
    captured credits are not the bank's Total and the revenue is not established."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.pipeline import DocumentReport
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction
    from analysis.serialization import document_report_to_dict

    rows = [(2, SALE, 4000.0), (9, SALE, 4000.0), (16, SALE, 4000.0)]
    if wire is not None:
        rows.append((12, WIRE, wire))
    rows.sort(key=lambda row: row[0])
    balance, transactions = opening, []
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        if dropped and day == 16:
            continue
        transactions.append(Transaction(date=f"2031-{month:02d}-{day:02d}", description=text, amount=amount,
                                        direction="credit", running_balance=balance))
    statement = Statement(
        bank="Sample Bank", account_name=HOLDER, account_number="000000001010", period_start=f"2031-{month:02d}-01",
        period_end=f"2031-{month:02d}-28", beginning_balance=opening, ending_balance=balance, currency="USD",
        currency_source="printed", stated_total_credits=round(sum(row[2] for row in rows), 2), stated_total_debits=0.0,
        transactions=transactions,
    )
    report = pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )
    return document_report_to_dict(DocumentReport(accounts=[report]))


def _served(payload):
    from webapp.app import _displayed
    return _displayed(payload, settings={})


def _job(job_id, payload):
    from webapp.jobs import Job
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def _package(*members):
    from webapp.app import _package_analysis
    return _package_analysis([_job(job_id, payload) for job_id, payload in members], settings={})


def _statement_memo(served, extra=""):
    """The statement page opened on `served`, then the memo, its decision and the pill."""
    from tests.test_webapp_true_revenue_ui import _open

    return run_dashboard(_open("s", served) + extra + """
generateSummary();
console.log(JSON.stringify({memo: els.summaryBox.textContent, own: accountDecision(currentAnalysis),
  label: labelize(accountDecision(currentAnalysis)), pill: els.decisionPill.textContent}));
""")


def _package_memo(package):
    ids = sorted({row["id"].split("#")[0] for row in package["documents"]})
    return run_dashboard(f"""
const pkg = {json.dumps(package)};
currentJobIds = {json.dumps(ids)}; renderPackageAnalysis(pkg); generateSummary();
console.log(JSON.stringify({{memo: els.summaryBox.textContent,
  warnings: (pkg.returned_funder_payments || []).map((item) => returnedFunderPaymentWarning(item, 'USD'))}}));
""")


# ---------------------------------------------------------------- R3-01: the statement memo's decision is the pill's

@needs_node
@pytest.mark.parametrize("wire, gate", [(15000.0, "share of posted credits"), (1500.0, "share of True plus held")])
def test_r3_01_a_statement_the_revenue_gate_sends_to_review_copies_review_required(wire, gate):
    """M1 and M2: a reconciled, approved statement whose held wire T7 gates (M1, held 15,000 of 27,000 posted; M2, held
    1,500 beside True of 12,000, at or over the $500 floor), with no potential lender debit."""
    served = _served(_bakery(wire))
    metrics = served["metrics"]
    assert served["quality"]["corporate_use"] == "approved" and served["reconciliation"]["ok"] is True
    assert metrics["revenue_review_required"] is True, gate
    assert metrics["potential_lender_debit_total"] == 0.0
    assert (metrics["excluded_pending_review_total"], metrics["excluded_pending_review_count"]) == (wire, 1)
    result = _statement_memo(served)
    assert (result["own"], result["pill"]) == ("review_required", "Review required")
    assert result["memo"].endswith("Status: review required.")  # was "Status: approved."
    held = f"${wire:,.2f}"
    assert (f"True revenue $12,000.00 ($12,000.00 a month), verified revenue $12,000.00 ($12,000.00 a month), "
            f"held for review {held} (1 credit), non-revenue $0.00 ($0.00 a month).") in result["memo"]


@needs_node
def test_r3_01_the_control_without_a_held_credit_reads_approved_and_names_nothing_held():
    """M3."""
    served = _served(_bakery())
    assert served["metrics"]["revenue_review_required"] is False
    assert served["metrics"]["excluded_pending_review_count"] == 0
    result = _statement_memo(served)
    assert (result["own"], result["pill"]) == ("approved", "Approved")
    assert result["memo"].endswith("Status: approved.")
    assert "held for review" not in result["memo"]
    assert ("True revenue $12,000.00 ($12,000.00 a month), verified revenue $12,000.00 ($12,000.00 a month), "
            "non-revenue $0.00 ($0.00 a month).") in result["memo"]


@needs_node
def test_r3_01_an_idle_main_account_still_sends_the_memo_to_review():
    """M4: the idle main account's note still leads, and the memo still reads review required."""
    from tests.test_webapp_studio_views import _all_accounts, _document, _serve

    memo = run_dashboard(_all_accounts("off") + _serve(idle=_document("idle")) + """
currentJobId = 'idle'; currentJobIds = ['idle']; loadResults('idle'); await settle();
""" + MEMO)
    assert "had no activity" in memo and memo.endswith("Status: review required.")


def _f1_items(monkeypatch):
    """The final review of round 2's F1 statements (tests/test_withholding_basis_unestablished.py): a reconciled ledger
    whose basis is not established, on each basis, and the same statement with its quality reading manual review."""
    from tests.test_withholding_basis_unestablished import _reconciled_stored
    from tests.test_withholding_basis_unestablished import _served as f1_served

    items = [f1_served(_reconciled_stored(monkeypatch, mode))
             for mode in ("true_revenue", "verified_revenue", "legacy_eligible_deposits")]
    manual = items[0]
    items.append({**manual, "quality": {**manual["quality"], "corporate_use": "manual_review_required"}})
    return items


@needs_node
def test_r3_01_the_memo_s_status_is_the_pill_s_decision_on_every_shape(monkeypatch):
    """M5: the memo's Status equals labelize(accountDecision(currentAnalysis)) on M1 to M3 and on F1's fixtures; F1's
    manual-review item keeps "manual review required", as its pill does."""
    items = [_served(_bakery(15000.0)), _served(_bakery(1500.0)), _served(_bakery()), *_f1_items(monkeypatch)]
    result = run_dashboard(f"""
const items = {json.dumps(items)};
const out = items.map((item) => {{
  currentAnalysis = item; currentDocument = null; generateSummary();
  return {{memo: els.summaryBox.textContent, label: labelize(accountDecision(item))}};
}});
console.log(JSON.stringify(out));
""")
    statuses = [STATUS.search(item["memo"]).group(1) for item in result]
    assert statuses == [item["label"] for item in result]
    assert statuses == ["review required", "review required", "approved", "review required", "review required",
                        "approved", "manual review required"]


@needs_node
def test_r3_01_a_statement_whose_revenue_is_not_established_names_nothing_held():
    """M6: the held wire is still held, but True reads N/A, and so does the held money: no clause."""
    served = _served(_bakery(15000.0, dropped=True))
    metrics = served["metrics"]
    assert metrics["revenue_established"] is False and metrics["excluded_pending_review_count"] == 1
    result = _statement_memo(served)
    assert "True revenue N/A, verified revenue N/A, non-revenue $0.00 ($0.00 a month, captured rows only)." in (
        result["memo"])
    assert "held for review" not in result["memo"]


@needs_node
def test_r3_01_a_package_memo_names_its_held_money_and_keeps_its_decision():
    """M7: a package of M1 (March) and M3 (April) states the held wire; its Decision is the served one."""
    from tests.test_package_matching import _closing

    march = _bakery(15000.0)
    closing = _closing([(2, SALE, 4000.0), (9, SALE, 4000.0), (12, WIRE, 15000.0), (16, SALE, 4000.0)], 5000.0)
    package = _package(("mar", march), ("apr", _bakery(month=4, opening=closing)))
    totals = package["totals"]
    assert (totals["excluded_pending_review_total"], totals["excluded_pending_review_count"]) == (15000.0, 1)
    assert totals["decision"] == "review_required"
    memo = _package_memo(package)["memo"]
    assert ("True revenue $24,000.00 ($12,000.00 a month), verified revenue $24,000.00 ($12,000.00 a month), held for "
            "review $15,000.00 (1 credit), non-revenue $0.00 ($0.00 a month).") in memo
    assert "Decision: review required." in memo


@needs_node
def test_r3_01_the_held_clause_counts_and_refuses_as_the_cards_do():
    """The clause reads its count's plural, the count alone where a package refuses its money, and nothing where the
    revenue is not established or nothing is held."""
    result = run_dashboard("""
const sentence = (source, flags) => revenueSummarySentence(source, 'USD', flags, {});
const base = {true_revenue_total: 100, verified_revenue_total: 50, non_revenue_total: 0};
const yes = {established: true, verifiedEstablished: true};
console.log(JSON.stringify([
  sentence({...base, excluded_pending_review_total: 1500, excluded_pending_review_count: 2}, yes),
  sentence({...base, excluded_pending_review_total: null, excluded_pending_review_count: 3}, yes),
  sentence({...base, excluded_pending_review_total: 1500, excluded_pending_review_count: 1},
           {established: false, verifiedEstablished: false}),
  sentence({...base, excluded_pending_review_total: 0, excluded_pending_review_count: 0}, yes),
  sentence({...base}, yes),
]));
""")
    assert ", verified revenue $50.00 (N/A a month), held for review $1,500.00 (2 credits), non-revenue" in result[0]
    assert ", held for review 3 credits, non-revenue" in result[1]
    assert all("held for review" not in text for text in result[2:])

