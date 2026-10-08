"""The final review of round 2, F2 (true revenue spec §6.2 passes 4 and 7b and the package passes, §9.2, §10.1, §10.6,
§10.8, §11, §17.1; the owner's ruling of 2026-10-02 on the underwriter's Q5, "Match the return to the funder payment it
reverses, take the bounced amount out of "paid to lenders" but keep it in the withholding rate. Keep the funder in the
lender count, and show a "returned funder payment" warning"; audit round 2, R2-OW13): a return is matched only to a
payment made before it, and a bounce whose payment sits in the previous statement is matched by the package.

(a) Classification 5.4's lender-side pair takes the nearest equal debit by its absolute day gap, so a funder-named return
printed at a month's start paired with a LATER payment, whose restore (R2-OW13) took a payment that was paid out of
"paid to lenders" and warned that it was "returned" before it was debited. A confirmed funder's paid payment now pairs,
on the lender side and for the restore, only with a return dated on or after it (printed after it where either row
prints no date); rule D already looks back 0 to 7 days. Nothing else in the 5.4 pairs moves (another debit's pair, the
revenue side's pairs and every revenue reading).

(b) Rule D reads one statement, so a bounce-worded return whose payment sits in the previous statement of the same
account was matched by neither statement. The package's pass 4 now matches a member's unpaired bounce-worded credit to
the same account's immediately preceding statement's confirmed-funder payment 0 to 7 days before it, with rule D's
guards; it takes that payment out of the package's paid to lenders, keeps it in the package's withholding numerator and
lender count, and shows R2-OW13's warning naming both documents. Each statement viewed alone is unchanged.

Fabricated rows only (CONTOSO PLUMBING LLC and CONTOSO BAKERY LLC; FABRIKAM, NORTHWIND and SAMPLE payees; KAPITUS and
ONDECK, public funders of the registry, as the lender tests use them; 2054 and 2031; neutral whole amounts)."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis.detect import detect
from analysis.metrics import compute_metrics
from tests.test_returned_funder_payments import KAPITUS, NAMED_RETURN, SALE, _pairs, _run, _statement
from tests.webapp_js_harness import NODE, run_dashboard

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

# ---------------------------------------------------------------- (a) the named pair's restore looks back only


def test_f2a_a_named_return_never_pairs_with_a_payment_dated_after_it():
    # The return prints on the 2nd; the funder's payments on the 3rd and the 10th (the statement starts after the
    # payment it returns, which sits in the previous statement).
    statement = _statement([(1, SALE, 10000.0), (2, NAMED_RETURN, 850.0), (3, KAPITUS, -850.0), (10, KAPITUS, -850.0)])
    records = tc.classify_statement_transactions(statement)
    assert _pairs(records) == {}
    credit = records[1]
    for debit in (records[2], records[3]):
        assert debit.reversed_by is None and debit.returned_funder_payment_by is None
        assert (debit.contributes_to_lender_totals, debit.contributes_to_withholding_rate,
                debit.contributes_to_lender_count) == (True, True, True)
    # No lender-side pair: the credit is no settlement reversal of either payment.
    assert (credit.reversal_of, credit.settlement_reversal, credit.returns_funder_payment) == (None, False, None)
    # The revenue side's pair is unchanged (a return is non-revenue either way).
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "matched_reversal_pair")
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lender_debits, metrics.withholding_numerator, metrics.returned_funder_payment_count) == (
        1700.0, 1700.0, 0)
    assert detect(statement, classifications=records).returned_funder_payments == []


def test_f2a_a_named_return_pairs_with_the_payment_on_or_before_it():
    # The payment two days before the return, and another the day after it (nearer): the earlier one is returned.
    statement = _statement([(1, SALE, 10000.0), (3, KAPITUS, -850.0), (5, NAMED_RETURN, 850.0), (6, KAPITUS, -850.0)])
    records = tc.classify_statement_transactions(statement)
    assert _pairs(records) == {"transaction:2": "transaction:3"}
    assert records[1].reversed_by == "transaction:3" and records[3].reversed_by is None
    assert records[3].contributes_to_lender_totals is True
    (item,) = detect(statement, classifications=records).returned_funder_payments
    assert (item["debit_date"], item["credit_date"]) == ("2054-03-03", "2054-03-05")
    # The same day still pairs (a payment and its return printed on one day).
    same_day = _run([(1, SALE, 10000.0), (4, KAPITUS, -850.0), (5, KAPITUS, -850.0), (5, NAMED_RETURN, 850.0),
                     (6, KAPITUS, -850.0)])
    assert _pairs(same_day) == {"transaction:3": "transaction:4"}


def test_f2a_an_undated_payment_pairs_only_when_printed_before_the_return():
    assert _pairs(_run([(1, SALE, 10000.0), (0, KAPITUS, -850.0), (0, NAMED_RETURN, 850.0)])) == {
        "transaction:2": "transaction:3"}
    assert _pairs(_run([(1, SALE, 10000.0), (0, NAMED_RETURN, 850.0), (0, KAPITUS, -850.0)])) == {}


def test_f2a_a_pair_on_any_other_debit_is_classification_5_4_s_as_before():
    # D6's weekly NORTHWIND FUNDING (a potential lender) and a named return printed the day before its first debit:
    # 5.4's pair zeroes that later potential debit as before; only a confirmed funder's paid payment looks back.
    weekly = [(day, "NORTHWIND FUNDING WEB PMT", -300.0) for day in (2, 9, 16, 23)]
    records = _run([(1, SALE, 10000.0), (1, "NORTHWIND FUNDING RETURNED ITEM", 300.0), *weekly])
    paired = records[2]
    assert (paired.classification, paired.reversed_by) == ("potential_lender", "transaction:2")
    assert paired.contributes_to_potential_lender_totals is False
    assert (records[1].reversal_of, records[1].settlement_reversal) == ("transaction:3", True)


# ---------------------------------------------------------------- (b) the package matches a bounce across statements

KAPITUS_BAKERY = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO BAKERY LLC CO ID:0000000002 CCD"
BARE_BOUNCE = "ACH RETURN ITEM NSF"
NAMED_BOUNCE = KAPITUS_BAKERY + " RETURNED ITEM"
NW_MARCH, NW_APRIL = "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:2"
UTILITY = "NORTHWIND UTILITIES BILL PAY"
#: March: a NORTHWIND sale and four weekly KAPITUS payments; the last, on the 27th, bounces in April.
MARCH = [(2, NW_MARCH, 30000.0)] + [(day, KAPITUS_BAKERY, -850.0) for day in (6, 13, 20, 27)]


def _april(bounce=BARE_BOUNCE, day=2, extra=(), payments=(3, 10, 17, 24)):
    return [(day, bounce, 850.0), (3, NW_APRIL, 30000.0), *extra] + [
        (payment, KAPITUS_BAKERY, -850.0) for payment in payments]


def _months(april_rows, *, march_rows=MARCH, april_month=4, april_number=None):
    from tests.test_package_matching import ACCOUNT_A, _closing, _payload

    march = _payload(march_rows, month=3, opening=5000.0)
    april = _payload(april_rows, month=april_month, opening=_closing(march_rows, 5000.0),
                     number=april_number or ACCOUNT_A)
    return march, april


def _location(payload, day, amount):
    (row,) = [row for row in payload["statement"]["transactions"]
              if row["date"].endswith(f"-{day:02d}") and row["amount"] == amount]
    return row["classification"]["source_location"]


def _leg(package, job_id):
    return next(row for row in package["transactions"] if row["source_job"] == job_id
                and (row["classification"].get("package_match") or {}).get("kind") == "returned_funder_payment")


def test_f2b_a_bare_bounce_returns_the_previous_statement_s_payment():
    import copy

    from tests.test_package_matching import _doc, _ledger_row, _package

    march, april = _months(_april())
    stored = copy.deepcopy((march, april))
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    # Out of paid to lenders, kept in the withholding numerator and the lender count.
    assert (totals["lender_debits"], totals["lender_debit_count"]) == (5950.0, 7)
    assert totals["withholding_numerator"] == 6800.0
    assert (totals["returned_funder_payment_total"], totals["returned_funder_payment_count"]) == (850.0, 1)
    assert totals["lenders_detected"] == 1
    debit_location, credit_location = _location(march, 27, -850.0), _location(april, 2, 850.0)
    funder = _ledger_row(package, "mar", debit_location)["classification"]["canonical_entity"]
    (rollup,) = package["funders"]
    assert (rollup["funder"], rollup["debit_count"], rollup["total_debited"]) == (funder, 7, 5950.0)
    assert (rollup["returned_payment_count"], rollup["returned_payment_total"]) == (1, 850.0)
    # R2-OW13's warning, naming both documents.
    (item,) = package["returned_funder_payments"]
    assert item == {
        "funder": funder, "amount": 850.0, "debit_date": "2031-03-27", "debit_location": debit_location,
        "credit_date": "2031-04-02", "credit_location": credit_location, "credit_description": BARE_BOUNCE,
        "source_job": "mar", "source_document": "mar.pdf", "source_currency": "USD",
        "credit_job": "apr", "credit_document": "apr.pdf", "cross_statement": True,
    }
    # The two legs, on the package's copies only.
    debit = _ledger_row(package, "mar", debit_location)["classification"]
    assert (debit["contributes_to_lender_totals"], debit["contributes_to_withholding_rate"],
            debit["contributes_to_lender_count"], debit["returned_funder_payment_by"]) == (
        False, True, True, credit_location)
    assert debit["package_match"]["kind"] == "returned_funder_payment"
    assert (debit["package_match"]["credit"]["job"], debit["package_match"]["credit"]["date"]) == ("apr", "2031-04-02")
    credit = _ledger_row(package, "apr", credit_location)["classification"]
    assert credit["package_match"]["kind"] == "returned_funder_payment"
    assert (credit["package_match"]["debit"]["job"], credit["package_match"]["debit"]["funder"]) == ("mar", funder)
    assert credit["returns_funder_payment"] is None and credit["revenue_tier"] == "non_revenue"
    match = next(entry for entry in package["package_matches"] if entry["kind"] == "returned_funder_payment")
    assert (match["moved"], match["gap_days"], match["debit"]["funder"]) == (True, 6, funder)
    assert (_doc(package, "mar")["lender_debits"], _doc(package, "mar")["returned_funder_payment_total"]) == (
        2550.0, 850.0)
    assert (_doc(package, "apr")["lender_debits"], _doc(package, "apr")["returned_funder_payment_total"]) == (
        3400.0, 0.0)
    # Revenue never moves; each statement alone keeps its figures; the stored payloads are untouched.
    assert totals["true_revenue_total"] == 60000.0
    assert _package(("apr", april))["totals"]["lender_debits"] == 3400.0
    assert _package(("mar", march))["totals"]["lender_debits"] == 3400.0
    assert (march, april) == stored


def test_f2b_a_named_return_the_statement_cannot_pair_is_matched_across():
    from tests.test_package_matching import _package

    march, april = _months(_april(NAMED_BOUNCE))
    # Inside April the return pairs with no payment (they are all after it: F2(a)).
    assert all(not row["classification"].get("returned_funder_payment_by")
               for row in april["statement"]["transactions"])
    totals = _package(("mar", march), ("apr", april))["totals"]
    assert (totals["lender_debits"], totals["returned_funder_payment_total"]) == (5950.0, 850.0)


#: name -> the keyword arguments of _months: a bounce the package never matches.
CONTROLS_B = {
    # Thirteen days after the last March payment: outside rule D's window (April's payments come after it).
    "window": dict(april_rows=_april(day=9, payments=(10, 17, 24))),
    # A return naming another confirmed funder never takes KAPITUS's payment.
    "other_funder": dict(april_rows=_april("ONDECK CAPITAL RETURNED ACH ITEM")),
    # An equal non-lender debit as near or nearer (rule D's guard), in either statement.
    "guard_march": dict(april_rows=_april(), march_rows=[*MARCH, (28, UTILITY, -850.0)]),
    "guard_april": dict(april_rows=_april(extra=((1, UTILITY, -850.0),))),
    # Not the next statement of the account (a month missing), or another account.
    "gap_month": dict(april_rows=_april(), april_month=5),
    "other_account": dict(april_rows=_april(), april_number="000000002020"),
    # A payment in April before the return: rule D pairs it inside April, and the package adds nothing.
    "paired_in_april": dict(april_rows=_april(extra=((1, KAPITUS_BAKERY, -850.0),))),
}


@pytest.mark.parametrize("name", sorted(CONTROLS_B))
def test_f2b_controls_match_nothing(name):
    from tests.test_package_matching import _package

    march, april = _months(**CONTROLS_B[name])
    package = _package(("mar", march), ("apr", april))
    assert not any(entry["kind"] == "returned_funder_payment" for entry in package.get("package_matches") or [])
    assert not any(item.get("cross_statement") for item in package["returned_funder_payments"])
    payments = sum(1 for payload in (march, april) for row in payload["statement"]["transactions"]
                   if row["description"] == KAPITUS_BAKERY)
    returned = 1 if name == "paired_in_april" else 0
    assert package["totals"]["lender_debits"] == 850.0 * (payments - returned)
    assert package["totals"]["returned_funder_payment_count"] == returned


def test_f2b_the_package_download_lists_the_match():
    from tests.test_package_matching import _package
    from webapp.app import _package_rows

    package = _package(*zip(("mar", "apr"), _months(_april())))
    rows = {(section, field): value for section, field, value in _package_rows(package)}
    section = next(section for (section, field), value in rows.items()
                   if field == "kind" and value == "returned_funder_payment")
    assert section.startswith("package_match_") and rows[(section, "moved")] is True
    assert '"funder"' in rows[(section, "debit")] and rows[(section, "gap_days")] == 6


def test_f2b_r1_the_package_s_payment_changes_read_the_matched_payment_as_an_attempt(monkeypatch):
    """Review round 1 of the fix run (finding 2): R2-OW18's package payment changes read the package's overlays, so a
    payment pass 4 matched is a returned attempt there, as R2-OW13's restore makes it inside one statement. KAPITUS is
    paid 850 weekly in March, its last March payment (the 27th) bounces on April 2 (a bare ACH RETURN ITEM NSF), and
    April pays 600 weekly: the decrease's last payment at the old amount is March 20, not the bounced 27th."""
    import webapp.app as app
    from tests.test_package_matching import _package

    april_rows = [(2, BARE_BOUNCE, 850.0), (3, NW_APRIL, 30000.0)] + [
        (day, KAPITUS_BAKERY, -600.0) for day in (3, 10, 17, 24)]
    march, april = _months(april_rows)
    fields = ("kind", "lender", "amount_before", "amount_after", "change_percent", "payments_before", "payments_after",
              "last_before_date", "first_after_date", "from_job", "to_job", "cross_statement")
    (item,) = _package(("mar", march), ("apr", april))["lender_payment_changes"]
    assert {field: item[field] for field in fields} == {
        "kind": "decrease", "lender": "KAPITUS", "amount_before": 850.0, "amount_after": 600.0, "change_percent": -29,
        "payments_before": 3, "payments_after": 4, "last_before_date": "2031-03-20", "first_after_date": "2031-04-03",
        "from_job": "mar", "to_job": "apr", "cross_statement": True}
    assert item["locations"]["last_before"] == _location(march, 20, -850.0)
    # Without pass 4 (the package before F2(b)) the bounced payment was the last paid one.
    monkeypatch.setattr(app, "_returned_funder_payments_across", lambda *args, **kwargs: None)
    (before,) = _package(("mar", march), ("apr", april))["lender_payment_changes"]
    assert (before["payments_before"], before["last_before_date"]) == (4, "2031-03-27")
    assert before["locations"]["last_before"] == _location(march, 27, -850.0)
    assert {field: before[field] for field in fields if field not in ("payments_before", "last_before_date")} == {
        field: item[field] for field in fields if field not in ("payments_before", "last_before_date")}


@needs_node
def test_f2b_the_dashboard_warns_naming_both_documents():
    import json

    from tests.test_package_matching import _package

    package = _package(*zip(("mar", "apr"), _months(_april())))
    debit_row, credit_row = _leg(package, "mar"), _leg(package, "apr")
    result = run_dashboard(f"""
const pkg = {json.dumps(package)};
const items = pkg.returned_funder_payments.map((item) => returnedFunderPaymentWarning(item, 'USD'));
console.log(JSON.stringify({{items, debit: packageMatchNotes({json.dumps(debit_row)}),
  credit: packageMatchNotes({json.dumps(credit_row)}), chip: returnedFunderChip({json.dumps(debit_row)})}}));
""")
    funder = debit_row["classification"]["canonical_entity"]
    # The owner's request of 2026-10-07 (dashboard clarity): a headline, plain sentences and both statements (without
    # the page's rows here, by their files).
    assert result["items"] == [
        f"{funder}: a payment bounced. The $850.00 payment on Mar 27, 2031 was returned unpaid on Apr 2, 2031 (the bank "
        "printed: \"ACH RETURN ITEM NSF\"). It isn't counted as paid, but it still counts in the withholding rate. "
        "From: mar.pdf → apr.pdf."]
    assert result["debit"] == [
        "Returned unpaid on 2031-04-02 (apr.pdf): out of paid to lenders, still in the withholding rate."]
    assert result["credit"] == [f"Returns the 2031-03-27 payment to {funder} in mar.pdf."]
    assert "Returned" in result["chip"]
