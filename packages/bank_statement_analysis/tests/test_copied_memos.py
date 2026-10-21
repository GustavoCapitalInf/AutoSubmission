"""Audit round 3, R3-B22 (true revenue spec §4's T7, §10.1, §11; the owner's rulings of 2026-10-02 on the underwriter's
Q5, "show a 'returned funder payment' warning", and Q7, True revenue the default withholding basis): the summaries an
analyst copies into a credit memo (`generateSummary`).

R3-01: the statement memo's decision read idle and unverified notes, material potential lender debits and the quality
word, never T7's revenue gate (`metrics.revenue_review_required`), so a statement whose pill read "Review required"
copied "Status: approved."; its decision is now the pill's (`accountDecision`), and both memos state the money held for
review (`revenueSummarySentence`'s held clause, between True revenue and non-revenue, only where the revenue is
established; since the owner's request of 2026-10-11 the memos carry no verified revenue clause). R3-67 (the memo half): the package memo listed each funder's paid total only, so a funder whose every
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
    from analysis.served_view import displayed
    return displayed(payload, settings={})


def _job(job_id, payload):
    from webapp.jobs import Job
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def _package(*members):
    from analysis.package import package_analysis
    return package_analysis([_job(job_id, payload) for job_id, payload in members], settings={})


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
// Audit round 3, R3-MERGE: as the Lenders tab words them since the owner's request of 2026-10-07, each statement named
// from the package's rows (paymentChangeSources).
const sources = paymentChangeSources(pkg.documents);
console.log(JSON.stringify({{memo: els.summaryBox.textContent,
  warnings: (pkg.returned_funder_payments || []).map((item) => returnedFunderPaymentWarning(item, 'USD', sources))}}));
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
    assert (f"True revenue $12,000.00 ($12,000.00 a month), "
            f"held for review {held} (1 credit), non-revenue $0.00 ($0.00 a month).") in result["memo"]
    assert "verified" not in result["memo"].lower()


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
    assert "True revenue $12,000.00 ($12,000.00 a month), non-revenue $0.00 ($0.00 a month)." in result["memo"]


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
    assert "True revenue N/A, non-revenue $0.00 ($0.00 a month, captured rows only)." in result["memo"]
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
    assert ("True revenue $24,000.00 ($12,000.00 a month), held for "
            "review $15,000.00 (1 credit), non-revenue $0.00 ($0.00 a month).") in memo
    assert "verified" not in memo.lower()
    assert "Decision: review required." in memo


@needs_node
def test_r3_01_the_held_clause_counts_and_refuses_as_the_cards_do():
    """The clause reads its count's plural, the count alone where a package refuses its money, and nothing where the
    revenue is not established or nothing is held."""
    result = run_dashboard("""
const sentence = (source, flags) => revenueSummarySentence(source, 'USD', flags, {});
const base = {true_revenue_total: 100, verified_revenue_total: 50, non_revenue_total: 0};
const yes = {established: true};
console.log(JSON.stringify([
  sentence({...base, excluded_pending_review_total: 1500, excluded_pending_review_count: 2}, yes),
  sentence({...base, excluded_pending_review_total: null, excluded_pending_review_count: 3}, yes),
  sentence({...base, excluded_pending_review_total: 1500, excluded_pending_review_count: 1},
           {established: false}),
  sentence({...base, excluded_pending_review_total: 0, excluded_pending_review_count: 0}, yes),
  sentence({...base}, yes),
]));
""")
    assert "True revenue $100.00 (N/A a month), held for review $1,500.00 (2 credits), non-revenue" in result[0]
    assert ", held for review 3 credits, non-revenue" in result[1]
    assert all("held for review" not in text for text in result[2:])


# ---------------------------------------------------------------- R3-67: returned funder payments in the package memo

def _returned_package():
    """P1: March, whose only ONDECK payment of 1,200 the bank returns two days later; April, one of whose four KAPITUS
    payments of 850 the bank returns the next day by "ACH RETURN ITEM NSF"."""
    from tests.test_returned_funder_payment_boundaries import BARE_BOUNCE, MARCH, _april, _months

    march_rows = sorted([*MARCH, (9, ONDECK_BAKERY, -1200.0), (11, BARE_BOUNCE, 1200.0)], key=lambda row: row[0])
    march, april = _months(sorted(_april(day=4), key=lambda row: row[0]), march_rows=march_rows)
    return _package(("mar", march), ("apr", april))


def _lender_lines(memo):
    return memo.split("\n\nPackage lender summary:\n", 1)[1].split("\n")


@needs_node
def test_r3_67_the_package_memo_names_each_funder_s_returned_payments_and_warns_per_item():
    package = _returned_package()
    totals = package["totals"]
    assert (totals["lender_debits"], totals["withholding_numerator"], totals["withholding_denominator"]) == (
        5950.0, 8000.0, 60000.0)
    assert (totals["returned_funder_payment_count"], totals["returned_funder_payment_total"]) == (2, 2050.0)
    assert len(package["returned_funder_payments"]) == 2
    result = _package_memo(package)
    memo = result["memo"]
    lines = _lender_lines(memo)
    assert lines[:2] == [
        "KAPITUS: $5,950.00 across 2 statement(s), 1 returned unpaid ($850.00, still in the withholding rate)",
        "ONDECK: $0.00 across 1 statement(s), 1 returned unpaid ($1,200.00, still in the withholding rate)"]
    # One "- <warning>" per served item, in served order, as the Lenders tab words it.
    assert lines[2:4] == [f"- {warning}" for warning in result["warnings"]]
    # Audit round 3, R3-MERGE: in the plain voice of the owner's request of 2026-10-07 (it read "Returned funder
    # payment: ..." and "Not counted as paid; still in the withholding rate.").
    assert all(": a payment was returned. " in line for line in lines[2:4])
    assert "It isn't counted as paid, but it still counts in the withholding rate." in lines[2]
    assert ("0 NSF events, $5,950.00 confirmed lender debits paid (2 returned funder payments, $2,050.00), 13.33% "
            "confirmed withholding") in memo


@needs_node
def test_r3_67_a_cross_statement_bounce_names_both_documents():
    """P2: the F2(b) fixture: March 27's KAPITUS payment returned on April 2."""
    from tests.test_returned_funder_payment_boundaries import _april, _months

    march, april = _months(_april())
    package = _package(("mar", march), ("apr", april))
    result = _package_memo(package)
    lines = _lender_lines(result["memo"])
    assert lines[0] == ("KAPITUS: $5,950.00 across 2 statement(s), 1 returned unpaid ($850.00, still in the "
                        "withholding rate)")
    # Audit round 3, R3-MERGE: the note names both statements by their months, as the Lenders tab does since the owner's
    # request of 2026-10-07 (it named "(mar.pdf)" and "(apr.pdf)").
    (warning,) = [line for line in lines if line.startswith("- KAPITUS: a payment was returned. ")]
    assert warning == f"- {result['warnings'][0]}"
    assert warning.endswith(" From: March 2031 → April 2031 statements.")
    assert "$5,950.00 confirmed lender debits paid (1 returned funder payment, $850.00), " in result["memo"]


@needs_node
def test_r3_67_a_re_debited_return_reads_counted_once_never_still_in_the_rate():
    """R3-B02 (the owner's answer of 2026-10-07 to R3-73, "Count it once"): a return the funder re-debited in the next
    statement is out of the rate, its re-debit (in paid) counting the payment once, so its funder line never says the
    returned money is still in the rate; the warning line says it is counted once."""
    from tests.test_represented_funder_payments import BARE_BOUNCE, KAPITUS_BAKERY, MARCH, NW_APRIL, _months

    march, april = _months([*MARCH, (28, BARE_BOUNCE, 850.0)],
                           [(2, NW_APRIL, 30000.0), (3, KAPITUS_BAKERY, -850.0)]
                           + [(day, KAPITUS_BAKERY, -850.0) for day in (1, 8, 15, 22)])
    package = _package(("mar", march), ("apr", april))
    assert (package["totals"]["withholding_numerator"], package["totals"]["lender_debits"]) == (6800.0, 6800.0)
    result = _package_memo(package)
    lines = _lender_lines(result["memo"])
    assert lines[0] == ("KAPITUS: $6,800.00 across 2 statement(s), 1 returned unpaid ($850.00, re-debited: counted "
                        "once in the withholding rate)")
    assert lines[1] == f"- {result['warnings'][0]}" and "counted once in the withholding rate" in lines[1]
    assert "still in the withholding rate" not in result["memo"]


@needs_node
def test_r3_67_a_package_without_a_return_reads_as_before():
    """P3: no "returned" word, and the funder lines as they read before the batch."""
    from tests.test_returned_funder_payment_boundaries import KAPITUS_BAKERY, NW_APRIL, _months

    march, april = _months([(3, NW_APRIL, 30000.0)] + [(day, KAPITUS_BAKERY, -850.0) for day in (3, 10, 17, 24)])
    package = _package(("mar", march), ("apr", april))
    assert package["returned_funder_payments"] == [] and package["totals"]["returned_funder_payment_count"] == 0
    memo = _package_memo(package)["memo"]
    assert "returned" not in memo.lower()
    assert _lender_lines(memo) == ["KAPITUS: $6,800.00 across 2 statement(s)"]
    assert "$6,800.00 confirmed lender debits" not in memo and "NSF events, 11.33% confirmed withholding" in memo


# ---------------------------------------------------------------- R3-68: the basis the memos' rates divide by

KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO BAKERY LLC CO ID:0000000002 CCD"
#: Two NORTHWIND payments of 10,000 (Verified), a counter deposit of 5,000 (counted), a transfer in from the business's
#: own savings of 5,000 (non-revenue) and four KAPITUS payments of 850: True 25,000, Verified 20,000, legacy 30,000.
BASIS_ROWS = [
    (2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 10000.0),
    (5, "DEPOSIT", 5000.0),
    (9, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:2", 10000.0),
    (12, "ONLINE BANKING TRANSFER FROM SAV 0000 CONFIRMATION# 0000000000", 5000.0),
] + [(day, KAPITUS, -850.0) for day in (6, 13, 20, 27)]
#: The owner's request of 2026-10-11 (true revenue spec §2.2, §10.1): the verified basis is named "narrower revenue
#: basis", never "verified revenue".
BASES = {"true_revenue": "true revenue", "legacy_eligible_deposits": "legacy eligible deposits",
         "verified_revenue": "narrower revenue basis"}


def basis_report(monkeypatch, mode):
    """The statement of BASIS_ROWS (CONTOSO BAKERY LLC, March 2031) analysed on the withholding basis `mode`."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    balance, transactions = 5000.0, []
    for day, text, amount in sorted(BASIS_ROWS, key=lambda row: row[0]):
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2031-03-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(
        bank="Sample Bank", account_name=HOLDER, account_number="000000001010", period_start="2031-03-01",
        period_end="2031-03-31", beginning_balance=5000.0, ending_balance=balance, currency="USD",
        currency_source="printed", stated_total_credits=30000.0, stated_total_debits=3400.0, transactions=transactions,
    )
    return pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )


def _basis_payload(monkeypatch, mode):
    from analysis.pipeline import DocumentReport
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(DocumentReport(accounts=[basis_report(monkeypatch, mode)]))


@needs_node
@pytest.mark.parametrize("mode", list(BASES))
def test_r3_68_the_package_memo_names_its_basis(monkeypatch, mode):
    """M8: the package memo of one statement on each basis ends its sentence with the basis."""
    memo = _package_memo(_package(("mar", _basis_payload(monkeypatch, mode))))["memo"]
    assert f" potential exposure (withholding basis: {BASES[mode]}). " in memo


@needs_node
def test_r3_68_a_mixed_package_names_its_mixed_configuration(monkeypatch):
    from tests.test_withholding_basis_unestablished import _may_june

    may, june = _may_june(monkeypatch)
    package = _package(("may", may), ("jun", june))
    assert package["totals"]["withholding_denominator_label"] == "Mixed denominator configuration"
    memo = _package_memo(package)["memo"]
    assert "N/A confirmed withholding" in memo
    assert " potential exposure (withholding basis: mixed denominator configuration). " in memo


@needs_node
def test_r3_68_the_statement_memo_names_its_basis_and_an_unestablished_one(monkeypatch):
    from tests.test_withholding_basis_unestablished import _reconciled_stored
    from tests.test_withholding_basis_unestablished import _served as f1_served

    true_memo = _statement_memo(_served(_basis_payload(monkeypatch, "true_revenue")))["memo"]
    assert " potential lender debits at 0% exposure (withholding basis: true revenue). " in true_memo
    legacy_memo = _statement_memo(_served(_basis_payload(monkeypatch, "legacy_eligible_deposits")))["memo"]
    assert " exposure (withholding basis: legacy eligible deposits). " in legacy_memo
    unestablished = _statement_memo(f1_served(_reconciled_stored(monkeypatch, "true_revenue")))["memo"]
    assert " potential lender debits at N/A exposure (withholding basis: true revenue, not established). " in (
        unestablished)
    # A stored payload with no mode was analysed on the legacy basis, as the Withholding Basis card says.
    stored = _served(_basis_payload(monkeypatch, "true_revenue"))
    for key in ("withholding_denominator_mode", "withholding_denominator_label"):
        stored["metrics"].pop(key, None)
    assert " exposure (withholding basis: legacy eligible deposits). " in _statement_memo(stored)["memo"]
