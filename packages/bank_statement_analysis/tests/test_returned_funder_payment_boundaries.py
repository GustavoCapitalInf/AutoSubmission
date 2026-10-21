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


#: Audit round 3, R3-B02 (R3-71): a potential lender's weekly payments (D6's keyword recurrence, NORTHWIND FUNDING) and
#: the payee's named return.
POTENTIAL_PAYMENT = "NORTHWIND FUNDING WEB PMT"
POTENTIAL_RETURN = "NORTHWIND FUNDING RETURNED ITEM"


def _old_lender_refusal(records, credit_index, debit_index):
    """F2(a) as the final review of round 2 left it: only a confirmed funder's paid payment looks back."""
    credit, debit = records[credit_index], records[debit_index]
    if not tc._is_paid_funder_debit(debit):
        return False
    if not (tc._matches_any(credit.normalized_description, tc._SETTLEMENT_REVERSAL_PATTERNS)
            or tc._matches_any(debit.normalized_description, tc._SETTLEMENT_REVERSAL_PATTERNS)):
        return False
    credit_date, debit_date = tc.parse_date(credit.date), tc.parse_date(debit.date)
    if credit_date is None or debit_date is None:
        return debit_index > credit_index
    return debit_date > credit_date


def _revenue_readings(records):
    return [{name: getattr(record, name) for name in vars(record) if name.startswith("revenue_")}
            for record in records if record.amount > 0]


def _potential(rows):
    statement = _statement(rows)
    records = tc.classify_statement_transactions(statement)
    return records, compute_metrics(statement, classifications=records)


def test_r3_71_a_potential_lender_s_return_never_takes_a_later_payment():
    # Audit round 3, R3-B02 (R3-71; the owner's Q5 ruling: "same amount, after it, a return/NSF form"): D6's weekly
    # NORTHWIND FUNDING (a potential lender) and a named return printed the day before its first payment: the return
    # cannot reverse a payment made after it, so no payment is zeroed (classification 5.4 zeroed the 2nd's).
    weekly = [(day, POTENTIAL_PAYMENT, -300.0) for day in (2, 9, 16, 23)]
    records, metrics = _potential([(1, SALE, 10000.0), (1, POTENTIAL_RETURN, 300.0), *weekly])
    debits = records[2:]
    assert [record.classification for record in debits] == ["potential_lender"] * 4
    assert all(record.reversed_by is None for record in debits)
    assert all(record.contributes_to_potential_lender_totals for record in debits)
    assert metrics.potential_lender_debit_total == 1200.0
    assert records[1].reversal_of is None and records[1].settlement_reversal is False
    # The return is non-revenue either way (the revenue side's pair).
    assert records[1].revenue_tier == "non_revenue"


def test_r3_71_a_potential_lender_s_return_takes_the_payment_before_it():
    # Payments on the 3rd, 10th, 17th and 24th, the named return on the 9th: the 3rd's payment is zeroed (default (1)'s
    # zeroing, on the payment the return can reverse), never the 10th's (5.4's nearest day either way).
    rows = [(1, SALE, 10000.0), (3, POTENTIAL_PAYMENT, -300.0), (9, POTENTIAL_RETURN, 300.0),
            *[(day, POTENTIAL_PAYMENT, -300.0) for day in (10, 17, 24)]]
    records, metrics = _potential(rows)
    by_day = {record.date[-2:]: record for record in records if record.amount < 0}
    assert by_day["03"].reversed_by == "transaction:3"
    assert by_day["03"].contributes_to_potential_lender_totals is False
    assert all(by_day[day].reversed_by is None and by_day[day].contributes_to_potential_lender_totals
               for day in ("10", "17", "24"))
    assert metrics.potential_lender_debit_total == 900.0
    assert records[2].reversal_of == "transaction:2"


def test_r3_71_an_undated_potential_return_pairs_only_with_a_payment_printed_before_it():
    weekly = [(day, POTENTIAL_PAYMENT, -300.0) for day in (2, 9, 16, 23)]
    before = _run([(1, SALE, 10000.0), (0, POTENTIAL_RETURN, 300.0), *weekly])
    assert all(record.reversed_by is None for record in before if record.amount < 0)
    after_one = _run([(1, SALE, 10000.0), weekly[0], (0, POTENTIAL_RETURN, 300.0), *weekly[1:]])
    assert [record.reversed_by for record in after_one if record.amount < 0] == ["transaction:3", None, None, None]


#: R3-71's cases, each read with F2(a) as round 2 left it (`_old_lender_refusal`) and as R3-B02 reads it.
R3_71_CASES = {
    "later": [(1, SALE, 10000.0), (1, POTENTIAL_RETURN, 300.0),
              *[(day, POTENTIAL_PAYMENT, -300.0) for day in (2, 9, 16, 23)]],
    "before": [(1, SALE, 10000.0), (3, POTENTIAL_PAYMENT, -300.0), (9, POTENTIAL_RETURN, 300.0),
               *[(day, POTENTIAL_PAYMENT, -300.0) for day in (10, 17, 24)]],
    "kapitus_later": [(1, SALE, 10000.0), (2, NAMED_RETURN, 850.0), (3, KAPITUS, -850.0), (10, KAPITUS, -850.0)],
    "kapitus_before": [(1, SALE, 10000.0), (3, KAPITUS, -850.0), (5, NAMED_RETURN, 850.0), (6, KAPITUS, -850.0)],
    "other_debit": [(1, SALE, 10000.0), (2, "REVERSAL ACH DEBIT SAMPLE SUPPLY CO", 300.0),
                    (3, "SAMPLE SUPPLY CO ACH DEBIT", -300.0)],
}


@pytest.mark.parametrize("name", sorted(R3_71_CASES))
def test_r3_71_moves_no_revenue_reading(monkeypatch, name):
    rows = R3_71_CASES[name]
    after = _run(rows)
    monkeypatch.setattr(tc, "_returns_a_later_lender_payment", _old_lender_refusal)
    before = _run(rows)
    assert _revenue_readings(after) == _revenue_readings(before)


def test_r3_71_a_non_lender_debit_keeps_classification_5_4_s_pair():
    # A debit that is no lender's keeps 5.4's nearest pair, either way (moving it would move revenue-side pairs).
    records = _run(R3_71_CASES["other_debit"])
    assert records[2].classification not in ("confirmed_lender", "potential_lender")
    assert (records[2].reversed_by, records[1].reversal_of) == ("transaction:2", "transaction:3")


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
    from analysis.package import passes
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
    monkeypatch.setattr(passes, "_returned_funder_payments_across", lambda *args, **kwargs: None)
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
        f"{funder}: a payment was returned. The $850.00 payment on Mar 27, 2031 was returned unpaid on Apr 2, 2031 (the "
        "bank printed: \"ACH RETURN ITEM NSF\"). It isn't counted as paid, but it still counts in the withholding "
        "rate. From: mar.pdf → apr.pdf."]
    assert result["debit"] == [
        "Returned unpaid on 2031-04-02 (apr.pdf): out of paid to lenders, still in the withholding rate."]
    assert result["credit"] == [f"Returns the 2031-03-27 payment to {funder} in mar.pdf."]
    assert "Returned" in result["chip"]


# ---------------------------------------------------------------- audit round 3, R3-B23: the download section
# R3-67, its download half (the owner's Q5 of 2026-10-02, "show a 'returned funder payment' warning"; spec §10.8's
# R2-OW13 bullet): the package CSV/XLSX write one `returned_funder_payment_<n>` section per served
# `returned_funder_payments` item, after the funder sections: its fields (an empty cell where the item has none), then
# `words`, the dashboard's warning line (app.js returnedFunderPaymentWarning) with the money in the item's own unit, as
# the overlapping statements' words write it; a refused package keeps each item in its own unit and sums nothing.

#: The fields of a `returned_funder_payment_<n>` section, in order, before its words.
RETURNED_SECTION_FIELDS = (
    "funder", "amount", "debit_date", "debit_location", "credit_date", "credit_location", "credit_description",
    "source_job", "source_document", "source_account", "source_currency", "cross_statement", "credit_job",
    "credit_document", "credit_account", "represented_date", "represented_location", "represented_kind",
    "represented_job", "represented_document", "represented_account")


def _returned_sections(package):
    """Each `returned_funder_payment_<n>` section of the package rows, {n: {field: value}}, and the fields' order."""
    from webapp.app import _package_rows

    sections, order = {}, {}
    for section, field, value in _package_rows(package):
        if section.startswith("returned_funder_payment_"):
            index = int(section.rsplit("_", 1)[1])
            sections.setdefault(index, {})[field] = value
            order.setdefault(index, []).append(field)
    return sections, order


def test_r3_67_the_package_rows_write_a_section_per_returned_funder_payment():
    """F1: March, and an April whose payment of April 1 the bank returns on April 2 (rule D inside April)."""
    from tests.test_package_matching import _package

    march, april = _months(_april(extra=((1, KAPITUS_BAKERY, -850.0),)))
    package = _package(("mar", march), ("apr", april))
    sections, order = _returned_sections(package)
    assert list(sections) == [1] and order[1] == [*RETURNED_SECTION_FIELDS, "words"]
    section = sections[1]
    assert (section["funder"], section["amount"], section["debit_date"], section["credit_date"]) == (
        "KAPITUS", 850.0, "2031-04-01", "2031-04-02")
    assert (section["source_job"], section["source_document"], section["source_currency"]) == ("apr", "apr.pdf", "USD")
    assert (section["credit_description"], section["debit_location"], section["credit_location"]) == (
        BARE_BOUNCE, _location(april, 1, -850.0), _location(april, 2, 850.0))
    # A field the item does not carry is an empty cell.
    assert all(section[field] == "" for field in ("source_account", "cross_statement", "credit_job", "credit_document",
                                                  "credit_account", "represented_date", "represented_document"))
    # Audit round 3, R3-MERGE: the dashboard's words since the owner's request of 2026-10-07 (the hosting line's plain
    # voice), which R3-67's rule carries into the section; every fact of the old words stays.
    assert section["words"] == ('KAPITUS: a payment was returned. The 850.00 USD payment on Apr 1, 2031 was returned '
                                'unpaid on Apr 2, 2031 (the bank printed: "ACH RETURN ITEM NSF"). It isn\'t counted as '
                                'paid, but it still counts in the withholding rate. From: apr.pdf.')


def test_r3_67_a_cross_statement_return_names_both_documents_in_its_section():
    """F2: F2(b)'s bare bounce of April 2 returning March 27's payment."""
    from tests.test_package_matching import _package

    package = _package(*zip(("mar", "apr"), _months(_april())))
    sections, _order = _returned_sections(package)
    section = sections[1]
    assert (section["cross_statement"], section["credit_job"], section["credit_document"]) == (True, "apr", "apr.pdf")
    # Audit round 3, R3-MERGE: the dashboard's words since the owner's request of 2026-10-07 (the hosting line's plain
    # voice), which R3-67's rule carries into the section; every fact of the old words stays.
    assert section["words"] == (
        'KAPITUS: a payment was returned. The 850.00 USD payment on Mar 27, 2031 was returned unpaid on Apr 2, 2031 (the '
        'bank printed: "ACH RETURN ITEM NSF"). It isn\'t counted as paid, but it still counts in the withholding rate. '
        'From: mar.pdf → apr.pdf.')


def test_r3_67_a_re_debited_return_reads_counted_once_in_its_section():
    """R3-B02 (the owner's answer of 2026-10-07 to R3-73, "Count it once"): a return the funder re-debited in the next
    statement names the re-debit and is counted once in the rate, as the dashboard's warning reads."""
    from tests.test_package_matching import _package
    from tests.test_represented_funder_payments import MARCH as TUESDAYS
    from tests.test_represented_funder_payments import _months as _tuesday_months

    march, april = _tuesday_months([*TUESDAYS, (28, BARE_BOUNCE, 850.0)],
                                   [(2, NW_APRIL, 30000.0), (3, KAPITUS_BAKERY, -850.0)]
                                   + [(day, KAPITUS_BAKERY, -850.0) for day in (1, 8, 15, 22)])
    sections, _order = _returned_sections(_package(("mar", march), ("apr", april)))
    section = sections[1]
    assert (section["represented_date"], section["represented_kind"], section["represented_job"],
            section["represented_document"]) == ("2031-04-03", "re_presented", "apr", "apr.pdf")
    # Audit round 3, R3-MERGE: the dashboard's words since the owner's request of 2026-10-07 (the hosting line's plain
    # voice), which R3-67's rule carries into the section; every fact of the old words stays.
    assert section["words"] == (
        'KAPITUS: a payment was returned. The 850.00 USD payment on Mar 25, 2031 was returned unpaid on Mar 28, 2031 (the '
        'bank printed: "ACH RETURN ITEM NSF"). It was taken again on Apr 3, 2031 (apr.pdf). It isn\'t counted as paid; '
        'it is counted once in the withholding rate, by the second debit. From: mar.pdf.')


def test_r3_67_a_package_without_a_return_writes_no_section():
    """F3 (control)."""
    from tests.test_package_matching import _package

    march, _april_payload = _months(_april())
    package = _package(("mar", march))
    assert package["returned_funder_payments"] == []
    assert _returned_sections(package) == ({}, {})


def test_r3_67_a_refused_package_keeps_each_returned_payment_in_its_own_unit():
    """F4: a CAD account and a USD account, each with a payment the bank returned the next day: the package refuses
    its money across currencies, and each section names its own unit; no returned money is summed."""
    import csv
    import io

    from tests.test_package_matching import ACCOUNT_B, _package, _payload
    from webapp.app import _masked, _package_csv, _package_for_export

    cad = _payload([(2, NW_MARCH, 30000.0), (5, KAPITUS_BAKERY, -850.0), (6, BARE_BOUNCE, 850.0)], month=3,
                   opening=5000.0, currency="CAD")
    usd = _payload([(3, NW_APRIL, 30000.0), (7, KAPITUS_BAKERY, -850.0), (8, BARE_BOUNCE, 850.0)], month=3,
                   opening=5000.0, number=ACCOUNT_B)
    package = _package(("cad", cad), ("usd", usd))
    totals = package["totals"]
    assert totals["cross_currency_totals_refused"] is True
    assert (totals["returned_funder_payment_total"], totals["returned_funder_payment_count"]) == (None, 2)
    sections, _order = _returned_sections(package)
    assert [(section["source_currency"], section["amount"]) for section in sections.values()] == [
        ("CAD", 850.0), ("USD", 850.0)]
    # Audit round 3, R3-MERGE: the dashboard's words since the owner's request of 2026-10-07 (the hosting line's plain
    # voice), which R3-67's rule carries into the section; every fact of the old words stays.
    assert sections[1]["words"].startswith("KAPITUS: a payment was returned. The 850.00 CAD payment on Mar 5, 2031 ")
    assert sections[2]["words"].startswith("KAPITUS: a payment was returned. The 850.00 USD payment on Mar 7, 2031 ")
    cells = {(row[0], row[1]): row[2] for row in csv.reader(io.StringIO(_package_csv(_masked(_package_for_export(
        package))))) if len(row) == 3}
    assert cells[("totals", "returned_funder_payment_total")] == ""
    assert cells[("returned_funder_payment_2", "words")] == sections[2]["words"]


def test_r3_67_the_section_reaches_the_package_csv_and_xlsx():
    """Through the download route's chain (`_masked(_package_for_export(...))`, then the writers), every cell through
    the escaped-row path."""
    import csv
    import io

    from tests.test_package_matching import _package
    from tests.test_webapp_true_revenue import _sheet_rows
    from webapp.app import _masked, _package_csv, _package_for_export, _package_xlsx

    exported = _masked(_package_for_export(_package(*zip(("mar", "apr"), _months(_april())))))
    # Audit round 3, R3-MERGE: the dashboard's words since the owner's request of 2026-10-07 (the hosting line's plain
    # voice), which R3-67's rule carries into the section; every fact of the old words stays.
    words = ('KAPITUS: a payment was returned. The 850.00 USD payment on Mar 27, 2031 was returned unpaid on Apr 2, 2031 '
             '(the bank printed: "ACH RETURN ITEM NSF"). It isn\'t counted as paid, but it still counts in the withholding '
             'rate. From: mar.pdf → apr.pdf.')
    csv_rows = list(csv.reader(io.StringIO(_package_csv(exported))))
    assert ["returned_funder_payment_1", "words", words] in csv_rows
    assert ["returned_funder_payment_1", "cross_statement", "True"] in csv_rows
    xlsx_rows = _sheet_rows(_package_xlsx(exported))
    assert ["returned_funder_payment_1", "words", words] in xlsx_rows
    assert ["returned_funder_payment_1", "amount", 850.0] in xlsx_rows
    # The section follows the funder sections.
    sections = [row[0] for row in csv_rows if len(row) == 3]
    assert sections.index("returned_funder_payment_1") > max(
        index for index, section in enumerate(sections) if section.startswith("funder_"))


#: Fabricated warning items covering each branch of app.js returnedFunderPaymentWarning.
WARNING_ITEMS = [
    {"funder": "KAPITUS", "amount": 850.0, "debit_date": "2031-04-01", "credit_date": "2031-04-02",
     "credit_description": BARE_BOUNCE, "source_document": "apr.pdf", "source_currency": "USD"},
    {"funder": "KAPITUS", "amount": 1234.5, "debit_date": "2031-03-27", "credit_date": "2031-04-02",
     "credit_description": "=SAMPLE RETURN", "source_document": "mar.pdf", "source_currency": "CAD",
     "credit_document": "apr.pdf", "cross_statement": True},
    {"funder": None, "amount": 850.0, "debit_date": None, "credit_date": None, "credit_description": None,
     "source_currency": None, "cross_statement": True},
    {"funder": "ONDECK", "amount": 1200.0, "debit_date": "2031-03-09", "credit_date": "2031-03-11",
     "credit_description": BARE_BOUNCE, "source_currency": "USD", "represented_date": "2031-03-12",
     "represented_kind": "re_presented"},
    {"funder": "ONDECK", "amount": 1200.0, "debit_date": "2031-03-09", "credit_date": "2031-03-11",
     "source_currency": "USD", "represented_date": "2031-03-16", "represented_kind": "caught_up",
     "represented_document": "apr.pdf"},
]


@needs_node
def test_r3_67_the_section_s_words_are_the_dashboard_s_warning():
    """The words are app.js returnedFunderPaymentWarning's line on every branch (in-statement, cross-statement with and
    without its documents, re-presented, caught up, no funder, no dates, no unit), the money written as the
    downloads write money (`850.00 USD`, no unit when the item has none) in place of the dashboard's formatted money."""
    import json

    from webapp.app import _returned_funder_payment_words

    result = run_dashboard(f"""
const items = {json.dumps(WARNING_ITEMS)};
console.log(JSON.stringify(items.map((item) => ({{
  line: returnedFunderPaymentWarning(item, 'USD'),
  money: formatMoney(item.amount, "source_currency" in item ? item.source_currency : 'USD'),
}}))));
""")
    for item, dashboard in zip(WARNING_ITEMS, result, strict=True):
        money = f"{item['amount']:,.2f}" + (f" {item['source_currency']}" if item.get("source_currency") else "")
        assert _returned_funder_payment_words(item) == dashboard["line"].replace(dashboard["money"], money, 1)
