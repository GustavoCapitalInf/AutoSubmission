"""Owner ruling 2026-10-02 (the underwriter's Q5, audit I29; true revenue spec §2.1, §6.2, §9.1, §9.2, §10.1, §11,
§14.3, §17.1, §19.1, §20; audit round 2, R2-OW13): "Match the return to the funder payment it reverses, take the
bounced amount out of "paid to lenders" but keep it in the withholding rate. Keep the funder in the lender count, and
show a "returned funder payment" warning".

A confirmed funder's payment the bank returned unpaid leaves paid to lenders (`contributes_to_lender_totals`: the
metrics' `lender_debits`, the lender table's total, the package's paid figure) and keeps `contributes_to_withholding_rate`
and `contributes_to_lender_count`; the debit carries `returned_funder_payment_by` (the return credit's location) and the
credit `returns_funder_payment` (the debit's location). Two ways in:

- a named pair classification 5.4's lender side makes (`_apply_reversal_pair_context`), which now keeps a confirmed
  funder's lender count and withholding (its `reversed_by` as before; every other debit zeroed as before);
- rule D (`_apply_returned_funder_payments`, pass 7b, after the true-revenue pass so it reads the credit's final tier):
  a bounce-worded credit out of True (`_RETURNED_PAYMENT_CREDIT_PATTERNS`, no fee word) equal to the cent to a confirmed
  funder's paid debit 0 to 7 days before it; Bank of America's printed RECEIVED ON day first, then the latest debit,
  then the nearest row; skipped when an equal non-lender debit is as near; a credit the revenue side paired pairs only
  with its partner, and a credit naming a confirmed funder only with that funder's debits. It never sets reversed_by
  and never moves a revenue reading.

The metrics' `withholding_numerator` is the paid lender debits plus the returned funder payments; the funder stays in
the lender count and listed when every payment bounced; the package sums the members' numerators.

Fabricated rows only (CONTOSO PLUMBING LLC; FABRIKAM, NORTHWIND and SAMPLE payees; KAPITUS, ONDECK and CanaCap, public
funders of the registry, as the lender tests use them; March 2054; neutral whole amounts)."""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, fields, replace

import pytest

from analysis import transaction_classifier as tc
from analysis.detect import detect
from analysis.metrics import WITHHOLDING_FORMULA, compute_metrics
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction

HOLDER = "CONTOSO PLUMBING LLC"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000001 CCD"
KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD"
ONDECK = "ONDECK CAPITAL DES:PAYMENT ID:000000003 INDN:CONTOSO PLUMBING LLC CO ID:0000000004 CCD"
CANACAP = "CANACAP BUS"
RENT = "NORTHWIND RENTALS DES:RENT ID:000000005 INDN:CONTOSO PLUMBING LLC CO ID:0000000006 PPD"
BOFA = "Bank of America"
BOFA_RETURN = "RETURN OF POSTED CHECK ITEM"
T1_RETURN = "RETURN OF POSTED CHECK ITEM RECEIVED ON 03/03 03/05"
NAMED_RETURN = "KAPITUS RETURNED ACH ITEM 0001"
RETURNED_UNPAID = ("Returned unpaid by {}: out of paid to lenders, kept in the withholding rate (the owner's ruling on "
                   "the underwriter's Q5).")


def _statement(rows, bank=BOFA, *, balances=False) -> Statement:
    """The rows (day, description, amount) in their order; day 0 prints no date. `balances` prints a running balance."""
    transactions, balance = [], 50000.0
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2054-03-{day:02d}" if day else "", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit",
                                        running_balance=balance if balances else None))
    return Statement(account_name=HOLDER, bank=bank, period_start="2054-03-01", period_end="2054-03-31",
                     transactions=transactions)


def _run(rows, bank=BOFA):
    return tc.classify_statement_transactions(_statement(rows, bank))


def _pairs(records):
    """{debit location: credit location} of every returned funder payment, and the credits' side agrees."""
    debits = {r.source_location: r.returned_funder_payment_by for r in records if r.returned_funder_payment_by}
    credits = {r.returns_funder_payment: r.source_location for r in records if r.returns_funder_payment}
    assert debits == credits
    return debits


#: name -> (rows, bank, {debit location: credit location}) of rule D (no named pair in any of them).
RULE_D = {
    # T1: three daily KAPITUS debits; Bank of America's return names the 03-03 one (RECEIVED ON), not the latest.
    "T1": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, KAPITUS, -850.0), (4, KAPITUS, -850.0),
            (5, T1_RETURN, 850.0), (6, SALE, 10000.0)], BOFA, {"transaction:3": "transaction:5"}),
    # T2: TD Canada Trust's RTN NSF the same day as the CanaCap debit: the only payment, returned.
    "T2": ([(1, SALE, 10000.0), (3, CANACAP, -5295.0), (3, "RTN NSF", 5295.0)], "TD Canada Trust",
           {"transaction:2": "transaction:3"}),
    # T3: Zions' ITEM RET NOT PAID the day after an ONDECK debit.
    "T3": ([(1, SALE, 10000.0), (2, ONDECK, -700.0), (3, "ITEM RET NOT PAID", 700.0)], "Zions Bank",
           {"transaction:2": "transaction:3"}),
    # T10: two funders at one amount: the later debit (KAPITUS) is taken.
    "T10": ([(1, SALE, 10000.0), (2, ONDECK, -500.0), (3, KAPITUS, -500.0), (4, BOFA_RETURN, 500.0)], BOFA,
            {"transaction:3": "transaction:4"}),
    # T11: two returns, two debits: each return its own RECEIVED ON day.
    "T11": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, KAPITUS, -850.0),
             (5, "RETURN OF POSTED CHECK ITEM RECEIVED ON 03/02 03/05", 850.0),
             (5, "RETURN OF POSTED CHECK ITEM RECEIVED ON 03/03 03/05", 850.0)], BOFA,
            {"transaction:2": "transaction:4", "transaction:3": "transaction:5"}),
    # T13: Desjardins' French returned item (R2-B08's arm (a)).
    "T13": ([(1, SALE, 10000.0), (2, "CANACAP PAD", -400.0), (3, "EFFET RETOURNE", 400.0)], "Desjardins",
            {"transaction:2": "transaction:3"}),
    # T14: the window's edge, 7 days.
    "T14": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (9, BOFA_RETURN, 850.0)], BOFA,
            {"transaction:2": "transaction:3"}),
    # Undated rows: the debit printed before the return.
    "undated": ([(1, SALE, 10000.0), (0, CANACAP, -850.0), (0, "RTN NSF", 850.0)], "TD Canada Trust",
                {"transaction:2": "transaction:3"}),
    # A return the revenue side paired with the funder's debit (a shared reference), inside the window: its partner.
    "partner": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (4, "ITEM RET NOT PAID ID 000000001", 850.0)], BOFA,
                {"transaction:2": "transaction:3"}),
    # A held return (Citibank's ACH DR RETURN, possible_return): paired, and it stays held.
    "held": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, "ACH DR RETURN", 850.0)], "Citibank",
             {"transaction:2": "transaction:3"}),
}

#: name -> (rows, bank) of the controls: no returned funder payment.
CONTROLS = {
    "T5": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (11, BOFA_RETURN, 850.0)], BOFA),  # 9 days later
    "T6": ([(1, SALE, 10000.0), (2, BOFA_RETURN, 850.0), (3, KAPITUS, -850.0)], BOFA),  # printed before the debit
    "T7": ([(1, SALE, 10000.0), (2, KAPITUS, -36.0), (3, "NSF FEE REFUND", 36.0)], BOFA),  # the fee's refund
    "T8": ([(1, SALE, 10000.0), (2, RENT, -850.0), (3, BOFA_RETURN, 850.0)], BOFA),  # equal only to the rent
    "T9": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, RENT, -850.0), (4, BOFA_RETURN, 850.0)], BOFA),  # guard
    "T12": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, "SAMPLE STORE REFUND", 850.0)], BOFA),  # a refund
    # A return code inside a company's name (no legal-form word may follow arms (2) to (6)).
    "legal_form": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, "SAMPLE RTN TRUCKING LLC", 850.0)], BOFA),
    # A return naming ONDECK, whose own debit is 19 days earlier: never KAPITUS's equal debit 2 days earlier.
    "named_funder": ([(1, SALE, 10000.0), (1, ONDECK, -850.0), (18, KAPITUS, -850.0),
                      (20, "ONDECK RETURNED ACH ITEM", 850.0)], BOFA),
    # A return the revenue side paired with the funder's debit 10 days earlier: left alone.
    "partner_out": ([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (12, "ITEM RET NOT PAID ID 000000001", 850.0)], BOFA),
    # The return printed before an undated debit.
    "undated_order": ([(1, SALE, 10000.0), (0, "RTN NSF", 850.0), (0, CANACAP, -850.0)], "TD Canada Trust"),
}


# ---------------------------------------------------------------------------------------------- the record fields


def test_the_record_carries_the_two_fields_after_settlement_reversal():
    names = [field.name for field in fields(tc.TransactionClassification)]
    position = names.index("settlement_reversal")
    assert names[position + 1:position + 3] == ["returned_funder_payment_by", "returns_funder_payment"]
    record = tc.classify_transaction(KAPITUS, -850.0)
    assert (record.returned_funder_payment_by, record.returns_funder_payment) == (None, None)


# ---------------------------------------------------------------------------------------------- rule D


@pytest.mark.parametrize("name", sorted(RULE_D))
def test_a_bounce_worded_return_takes_the_funder_payment_out_of_paid(name):
    rows, bank, expected = RULE_D[name]
    records = _run(rows, bank)
    assert _pairs(records) == expected
    by_location = {record.source_location: record for record in records}
    for debit_location, credit_location in expected.items():
        debit = by_location[debit_location]
        assert debit.classification == "confirmed_lender"
        assert (debit.contributes_to_lender_totals, debit.contributes_to_withholding_rate,
                debit.contributes_to_lender_count, debit.contributes_to_flagged_totals) == (False, True, True, False)
        # Rule D never sets reversed_by, so the reconciliation and the settled-activity counts read the row as before.
        assert debit.reversed_by is None
        assert debit.reason.endswith(RETURNED_UNPAID.format(credit_location))
        credit = by_location[credit_location]
        assert (credit.reversal_of, credit.settlement_reversal) == (None, False)
    # Every other confirmed lender debit is still paid.
    for record in records:
        if record.classification == "confirmed_lender" and record.source_location not in expected:
            assert record.contributes_to_lender_totals and record.returned_funder_payment_by is None


def test_t1_the_received_on_day_wins_and_the_metrics_split_paid_from_withholding():
    rows, bank, _ = RULE_D["T1"]
    statement = _statement(rows, bank)
    records = tc.classify_statement_transactions(statement)
    credit = records[4]
    assert credit.returns_funder_payment == "transaction:3"
    assert (credit.revenue_classification, credit.revenue_tier, credit.revenue_tier_reason,
            credit.revenue_match_method) == ("non_revenue", "non_revenue", None, "reversal_cancellation_exclusion")
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lender_debits, metrics.lender_debit_count) == (1700.0, 2)
    assert (metrics.returned_funder_payment_total, metrics.returned_funder_payment_count) == (850.0, 1)
    assert [record.source_location for record in metrics.returned_funder_payment_evidence] == ["transaction:3"]
    assert metrics.withholding_numerator == 2550.0
    assert metrics.withholding_numerator == round(metrics.lender_debits + metrics.returned_funder_payment_total, 2)
    assert metrics.lenders_detected == 1
    assert metrics.true_revenue_total == 20000.0
    # Audit round 3, final review (R3-FF), F5: the words name the lump sums and the re-debited returns it leaves out.
    assert metrics.withholding_formula == WITHHOLDING_FORMULA == (
        "abs(paid lender debits - worded lump-sum payoffs + returned funder payments not re-debited) / withholding "
        "basis * 100")
    assert metrics.withholding_rate == pytest.approx(2550.0 / metrics.withholding_denominator * 100)
    assert ("1 returned funder payment (850.00 USD): out of paid to lenders, kept in the withholding rate"
            in metrics.notes)
    result = detect(statement, classifications=records)
    [kapitus] = result.known_funders
    assert (kapitus.funder, kapitus.debit_count, kapitus.total_debited) == ("KAPITUS", 2, 1700.0)
    assert (kapitus.returned_count, kapitus.returned_total) == (1, 850.0)
    assert kapitus.returned_payments == [{"amount": 850.0, "debit_date": "2054-03-03", "debit_location": "transaction:3",
                                          "credit_date": "2054-03-05", "credit_location": "transaction:5"}]
    # The returned row joins its funder's rows; lender_evidence stays the paid rows.
    assert len(kapitus.evidence) == 3
    assert [record.source_location for record in result.lender_evidence] == ["transaction:2", "transaction:4"]
    assert result.returned_funder_payments == [{
        "funder": "KAPITUS", "amount": 850.0, "debit_date": "2054-03-03", "debit_location": "transaction:3",
        "credit_date": "2054-03-05", "credit_location": "transaction:5", "credit_description": T1_RETURN}]


def test_without_the_received_on_day_the_latest_debit_is_taken():
    rows = [(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, KAPITUS, -850.0), (4, KAPITUS, -850.0),
            (5, BOFA_RETURN, 850.0)]
    assert _pairs(_run(rows)) == {"transaction:4": "transaction:5"}
    # A RECEIVED ON day no candidate is dated: the latest debit.
    rows[4] = (5, "RETURN OF POSTED CHECK ITEM RECEIVED ON 02/27 03/05", 850.0)
    assert _pairs(_run(rows)) == {"transaction:4": "transaction:5"}


def test_t2_a_funder_whose_every_payment_bounced_stays_counted_and_listed():
    rows, bank, _ = RULE_D["T2"]
    statement = _statement(rows, bank)
    records = tc.classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lender_debits, metrics.lender_debit_count) == (0.0, 0)
    assert (metrics.withholding_numerator, metrics.lenders_detected) == (5295.0, 1)
    [canacap] = detect(statement, classifications=records).known_funders
    assert (canacap.funder, canacap.debit_count, canacap.total_debited) == ("CanaCap", 0, 0.0)
    assert (canacap.returned_count, canacap.returned_total) == (1, 5295.0)


def test_t4_a_named_pair_keeps_a_confirmed_funders_count_and_withholding():
    statement = _statement([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (4, NAMED_RETURN, 850.0)])
    records = tc.classify_statement_transactions(statement)
    debit, credit = records[1], records[2]
    # 5.4's pair as before: reversed_by, and the credit's settlement-reversal fields and revenue reading.
    assert debit.reversed_by == "transaction:3"
    assert (credit.reversal_of, credit.settlement_reversal) == ("transaction:2", True)
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "matched_reversal_pair")
    # Today zeroed: the lender count and the withholding stay; paid, flagged, potential and insurance leave.
    assert (debit.contributes_to_lender_totals, debit.contributes_to_withholding_rate,
            debit.contributes_to_lender_count, debit.contributes_to_flagged_totals,
            debit.contributes_to_potential_lender_totals, debit.contributes_to_insurance_totals) == (
        False, True, True, False, False, False)
    assert (debit.returned_funder_payment_by, credit.returns_funder_payment) == ("transaction:3", "transaction:2")
    assert debit.reason.endswith(RETURNED_UNPAID.format("transaction:3"))
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lender_debits, metrics.withholding_numerator, metrics.lenders_detected) == (0.0, 850.0, 1)
    assert (metrics.returned_funder_payment_total, metrics.returned_funder_payment_count) == (850.0, 1)


def test_a_named_pair_on_a_potential_lender_is_zeroed_as_before():
    """T15: D6's weekly NORTHWIND FUNDING debits and a named NORTHWIND FUNDING RETURNED ITEM: the paired potential
    debit is zeroed as today (no returned flag), the potential exposure reads the three others, and rule D reads no
    potential lender's debit."""
    weekly = [(day, "NORTHWIND FUNDING WEB PMT", -300.0) for day in (2, 9, 16, 23)]
    statement = _statement([(1, SALE, 10000.0), *weekly, (25, "NORTHWIND FUNDING RETURNED ITEM", 300.0)])
    records = tc.classify_statement_transactions(statement)
    paired = records[4]
    assert (paired.classification, paired.reversed_by) == ("potential_lender", "transaction:6")
    assert (paired.contributes_to_potential_lender_totals, paired.contributes_to_potential_withholding_exposure,
            paired.contributes_to_potential_lender_count) == (False, False, False)
    assert paired.returned_funder_payment_by is None and records[5].returns_funder_payment is None
    assert all(r.contributes_to_potential_lender_totals for r in records[1:4])
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.potential_lender_debit_total, metrics.returned_funder_payment_count) == (900.0, 0)
    # A bounce-worded return equal only to a potential lender's debit is left alone.
    unnamed = _run([(1, SALE, 10000.0), *weekly, (25, BOFA_RETURN, 300.0)])
    assert _pairs(unnamed) == {}
    assert all(r.contributes_to_potential_lender_totals for r in unnamed[1:5])


@pytest.mark.parametrize("name", sorted(CONTROLS))
def test_a_control_moves_no_flag(name):
    rows, bank = CONTROLS[name]
    records = _run(rows, bank)
    assert _pairs(records) == {}
    for record in records:
        if record.classification == "confirmed_lender":
            assert record.contributes_to_lender_totals and record.contributes_to_withholding_rate
        assert record.returned_funder_payment_by is None and record.returns_funder_payment is None


def test_the_guard_skips_only_an_equal_non_lender_debit_as_near():
    # T9's rent debit one day before the return is nearer than KAPITUS (two days): skipped. Farther: paired.
    farther = [(1, SALE, 10000.0), (1, RENT, -850.0), (3, KAPITUS, -850.0), (4, BOFA_RETURN, 850.0)]
    assert _pairs(_run(farther)) == {"transaction:3": "transaction:4"}
    # As near (the same day as the funder's debit): skipped.
    as_near = [(1, SALE, 10000.0), (3, RENT, -850.0), (3, KAPITUS, -850.0), (4, BOFA_RETURN, 850.0)]
    assert _pairs(_run(as_near)) == {}


def test_each_debit_pairs_once_and_a_second_return_finds_the_earlier_debit():
    rows = [(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, KAPITUS, -850.0), (5, BOFA_RETURN, 850.0),
            (6, BOFA_RETURN, 850.0)]
    assert _pairs(_run(rows)) == {"transaction:3": "transaction:4", "transaction:2": "transaction:5"}
    single = [(1, SALE, 10000.0), (2, KAPITUS, -850.0), (5, BOFA_RETURN, 850.0), (6, BOFA_RETURN, 850.0)]
    assert _pairs(_run(single)) == {"transaction:2": "transaction:3"}


def test_a_named_pair_s_credit_is_never_read_again_by_rule_d():
    rows = [(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, KAPITUS, -850.0), (4, NAMED_RETURN, 850.0)]
    records = _run(rows)
    assert [r.reversed_by for r in records[1:3]] == [None, "transaction:4"]
    assert _pairs(records) == {"transaction:3": "transaction:4"}
    assert records[1].contributes_to_lender_totals


def test_the_tier_filter_reads_no_credit_the_revenue_side_counts():
    rows, bank, _ = RULE_D["T14"]
    records = _run(rows, bank)
    base = [replace(r, returned_funder_payment_by=None, returns_funder_payment=None,
                    contributes_to_lender_totals=r.contributes_to_lender_totals or r.classification == "confirmed_lender")
            for r in records]
    assert tc._returned_funder_payment_pairs(base, set()) == [(2, 1)]
    for tier in ("verified", "counted_flagged"):
        counted = list(base)
        counted[2] = replace(base[2], revenue_tier=tier)
        assert tc._returned_funder_payment_pairs(counted, set()) == []
    held = list(base)
    held[2] = replace(base[2], revenue_tier="excluded_pending_review")
    assert tc._returned_funder_payment_pairs(held, set()) == [(2, 1)]
    lender_credit = list(base)
    lender_credit[2] = replace(base[2], contributes_to_lender_credit_exclusion=True)
    assert tc._returned_funder_payment_pairs(lender_credit, set()) == []
    # Duplicates are read by neither side.
    assert tc._returned_funder_payment_pairs(base, {1}) == [] == tc._returned_funder_payment_pairs(base, {2})


@pytest.mark.parametrize("text, bounce", [
    ("RETURN OF POSTED CHECK ITEM RECEIVED ON 03 03", True), ("RETURN OF POSTED ITEM", True),
    ("ITEM RET NOT PAID", True), ("RET ITEM", True), ("RTN NSF", True), ("RETN 0001", True), ("NSF RETURN", True),
    ("UNPAID ITEM", True), ("NOT PAID", True), ("REJECTED", True), ("ACH REJECT", True),
    ("ITEM RETURNED NSF", True), ("RETURNED NSF CHEQUE", True), ("CHEQUE RETURNED NSF", True), ("ACH DR RETURN", True),
    ("RETURN ITEM OVERDRAFT", True), ("CREDIT RETURNED CK 1234", True), ("1234 RETURNED EFT NAF", True),
    ("RETURNED PAD", True), ("PAYMENT RETURNED", True), ("EFFET RETOURNE", True), ("EFFETS RETOURNES", True),
    ("EFFET RET", True), ("CHEQUE REFUSE SANS PROVISION", True), ("EFFET REFUSE SANS PROV", True),
    # Never a refund, a reversal word alone, a correction, a card return, a fee or a code inside a company's name.
    ("SAMPLE STORE REFUND", False), ("REVERSAL", False), ("ERROR CORRECTION", False), ("PURCHASE RETURN", False),
    ("NSF FEE REFUND", False), ("RETURNED ITEM FEE", False), ("RETURN ITEM CHARGE", False),
    ("SAMPLE RTN TRUCKING LLC", False), ("NSF SAMPLE SUPPLY INC", False), ("REJECT SUPPLY CORP", False),
    ("UNPAIDCONTOSO", False), ("BRTN 1234", False),
])
def test_the_bounce_forms(text, bounce):
    assert tc._returned_payment_credit(tc.normalize_transaction_description(text)) is bounce


def test_the_french_arms_are_r2_b08_s_arms_a_and_c():
    patterns = [pattern.pattern for pattern in tc._RETURNED_PAYMENT_CREDIT_PATTERNS]
    assert patterns[-2:] == [tc._RETURN_REFUND_R2_B08_ARMS[0], tc._RETURN_REFUND_R2_B08_ARMS[2]]
    assert tc.RETURNED_FUNDER_PAYMENT_WINDOW_DAYS == 7


# ---------------------------------------------------------------------------------------------- MUST NOT CHANGE


def _without_rule_d(monkeypatch, rows, bank):
    # Audit round 4, R4-78: the pass also takes the statement's calendar and bank (its unworded arm), as keywords.
    monkeypatch.setattr(tc, "_apply_returned_funder_payments", lambda records, duplicates, **_statement: records)
    return _run(rows, bank)


_REVENUE_FIELDS = tuple(f.name for f in fields(tc.TransactionClassification)
                        if f.name.startswith("revenue_") or f.name.startswith("contributes_to_")
                        and f.name not in ("contributes_to_lender_totals", "contributes_to_flagged_totals"))


@pytest.mark.parametrize("name", sorted(RULE_D) + sorted(CONTROLS))
def test_rule_d_moves_no_revenue_reading_and_no_other_flag(monkeypatch, name):
    """T16: every credit's state, tier, reason and every revenue field are rule D's input's; on a debit only the paid
    and flagged flags, the reason and the new field move; reversed_by and settlement_reversal never."""
    rows, bank = (RULE_D[name][:2] if name in RULE_D else CONTROLS[name])
    after = _run(rows, bank)
    before = _without_rule_d(monkeypatch, rows, bank)
    for old, new in zip(before, after):
        assert {key: getattr(old, key) for key in _REVENUE_FIELDS} == {key: getattr(new, key) for key in _REVENUE_FIELDS}
        assert (old.reversed_by, old.settlement_reversal, old.reversal_of, old.classification, old.is_nsf_event) == (
            new.reversed_by, new.settlement_reversal, new.reversal_of, new.classification, new.is_nsf_event)
        if new.returned_funder_payment_by is None:
            assert replace(new, returns_funder_payment=None) == replace(old, returns_funder_payment=None)


def test_t17_the_reconciliation_reads_the_same_reversal_pairs(monkeypatch):
    """A statement whose stated totals do not match its rows, so reconcile reads the reversal pairs: identical with and
    without rule D (it sets no reversed_by and no settlement_reversal)."""
    rows = [(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, KAPITUS, -850.0), (4, NAMED_RETURN, 850.0),
            (6, BOFA_RETURN, 850.0)]
    statement = _statement(rows).model_copy(update={"stated_total_credits": 10000.0, "stated_total_debits": 850.0})
    after = asdict(reconcile(statement))
    monkeypatch.setattr(tc, "_apply_returned_funder_payments", lambda records, duplicates, **_statement: records)
    assert asdict(reconcile(statement)) == after
    assert after["reversal_pair_count"] == 1


def test_the_nsf_count_lender_credits_and_eligible_deposits_do_not_move(monkeypatch):
    rows, bank, _ = RULE_D["T2"]
    statement = _statement(rows, bank)
    after = compute_metrics(statement, classifications=tc.classify_statement_transactions(statement))
    monkeypatch.setattr(tc, "_apply_returned_funder_payments", lambda records, duplicates, **_statement: records)
    before = compute_metrics(statement, classifications=tc.classify_statement_transactions(statement))
    for key in ("nsf_count", "lender_credits", "legacy_eligible_deposits", "eligible_deposits", "ach_debit_count",
                "loan_count", "potential_lender_debit_total", "lenders_detected", "true_revenue_total",
                "verified_revenue_total", "non_revenue_total", "excluded_pending_review_total"):
        assert getattr(after, key) == getattr(before, key), key
    assert (before.lender_debits, after.lender_debits) == (5295.0, 0.0)
    assert before.withholding_numerator == after.withholding_numerator == 5295.0


# ---------------------------------------------------------------------------------------------- payloads and packages


def returned_payload(rows, *, bank=BOFA, currency="USD", account="000000002020"):
    """The analysed payload of a fabricated statement, as `report_to_dict` writes it (printed balances, reconciled)."""
    from analysis.pipeline import analyze_statement
    from analysis.serialization import document_report_to_dict

    statement = _statement(rows, bank, balances=True)
    statement = statement.model_copy(update={
        "beginning_balance": 50000.0, "ending_balance": statement.transactions[-1].running_balance,
        "account_number": account, "currency": currency, "currency_source": "printed"})
    return document_report_to_dict(analyze_statement(statement, reconciliation=reconcile(statement), markdown="",
                                                     sheets=[], model_used="fabricated-test"))


def t1_payload(**kwargs):
    return returned_payload(RULE_D["T1"][0], **kwargs)


def t4_payload(**kwargs):
    return returned_payload([(1, SALE, 10000.0), (2, KAPITUS, -850.0), (4, NAMED_RETURN, 850.0)],
                            account="000000003030", **kwargs)


def _package(*payloads):
    from webapp.app import _package_analysis
    from webapp.jobs import Job

    return _package_analysis([Job(id=f"job-{n}", filename=f"statement-{n}.pdf", status="done", analysis=payload,
                                  content_sha256=f"job-{n}") for n, payload in enumerate(payloads, start=1)],
                             settings={})


def _account(payload):
    from analysis.payload_shape import payload_accounts

    [account] = payload_accounts(payload, surface="tests/test_returned_funder_payments.py")
    return account


def test_the_payload_carries_the_fields_the_metrics_and_the_detection():
    account = _account(t1_payload())
    rows = [row["classification"] for row in account["statement"]["transactions"]]
    assert rows[2]["returned_funder_payment_by"] == "transaction:5" and rows[4]["returns_funder_payment"] == "transaction:3"
    assert all(row["returned_funder_payment_by"] is None for index, row in enumerate(rows) if index != 2)
    metrics = account["metrics"]
    assert (metrics["lender_debits"], metrics["withholding_numerator"]) == (1700.0, 2550.0)
    assert (metrics["returned_funder_payment_total"], metrics["returned_funder_payment_count"]) == (850.0, 1)
    assert [row["source_location"] for row in metrics["returned_funder_payment_evidence"]] == ["transaction:3"]
    detection = account["detection"]
    [kapitus] = detection["known_funders"]
    assert (kapitus["debit_count"], kapitus["total_debited"]) == (2, 1700.0)
    assert (kapitus["returned_payment_count"], kapitus["returned_payment_total"]) == (1, 850.0)
    assert len(kapitus["transactions"]) == 3
    assert detection["returned_funder_payments"] == [{
        "funder": "KAPITUS", "amount": 850.0, "debit_date": "2054-03-03", "debit_location": "transaction:3",
        "credit_date": "2054-03-05", "credit_location": "transaction:5", "credit_description": T1_RETURN}]
    assert len(detection["lender_evidence"]) == 2


def test_t18_a_package_sums_paid_returned_and_the_members_numerators():
    package = _package(t1_payload(), t4_payload())
    totals = package["totals"]
    assert (totals["lender_debits"], totals["lender_debit_count"]) == (1700.0, 2)
    assert totals["withholding_numerator"] == 3400.0
    assert (totals["returned_funder_payment_total"], totals["returned_funder_payment_count"]) == (1700.0, 2)
    assert totals["package_withholding_rate"] == round(3400.0 / totals["withholding_denominator"] * 100, 2)
    assert totals["lenders_detected"] == 1
    assert totals["withholding_formula"] == (
        "abs(paid lender debits - worded lump-sum payoffs + returned funder payments not re-debited) / withholding "
        "basis * 100")
    assert totals["potential_withholding_formula"] == "abs(potential_lender_debit_total) / withholding basis * 100"
    [kapitus] = package["funders"]
    assert (kapitus["funder"], kapitus["debit_count"], kapitus["total_debited"], kapitus["documents"]) == (
        "KAPITUS", 2, 1700.0, 2)
    assert (kapitus["returned_payment_count"], kapitus["returned_payment_total"]) == (2, 1700.0)
    rows = {row["id"]: row for row in package["documents"]}
    assert (rows["job-1"]["lender_debits"], rows["job-1"]["withholding_numerator"]) == (1700.0, 2550.0)
    assert (rows["job-2"]["lender_debits"], rows["job-2"]["withholding_numerator"]) == (0.0, 850.0)
    assert (rows["job-1"]["returned_funder_payment_total"], rows["job-1"]["returned_funder_payment_count"]) == (850.0, 1)
    assert [(item["source_job"], item["source_document"], item["source_currency"], item["debit_location"],
             item["credit_description"]) for item in package["returned_funder_payments"]] == [
        ("job-1", "statement-1.pdf", "USD", "transaction:3", T1_RETURN),
        ("job-2", "statement-2.pdf", "USD", "transaction:2", NAMED_RETURN)]
    # The package's lender evidence keeps the withholding flag, so the returned rows are listed and marked.
    evidence = package["lender_evidence"]
    assert len(evidence) == 4
    assert sorted(record["returned_funder_payment_by"] or "" for record in evidence) == [
        "", "", "transaction:3", "transaction:5"]


def _strip_returned(node):
    """The payload as a release before R2-OW13 stored it: no returned key anywhere."""
    if isinstance(node, dict):
        for key in ("returned_funder_payment_by", "returns_funder_payment", "returned_funder_payment_total",
                    "returned_funder_payment_count", "returned_funder_payment_evidence", "returned_funder_payments",
                    "returned_payment_count", "returned_payment_total"):
            node.pop(key, None)
        for value in node.values():
            _strip_returned(value)
    elif isinstance(node, list):
        for value in node:
            _strip_returned(value)
    return node


def test_t19_a_payload_stored_before_the_ruling_reads_its_stored_figures(monkeypatch):
    monkeypatch.setattr(tc, "_apply_returned_funder_payments", lambda records, duplicates, **_statement: records)
    old = _strip_returned(t1_payload())
    monkeypatch.undo()
    package = _package(old)
    row, totals = package["documents"][0], package["totals"]
    assert (row["lender_debits"], row["withholding_numerator"]) == (2550.0, 2550.0)
    assert (row["returned_funder_payment_total"], row["returned_funder_payment_count"]) == (0.0, 0)
    assert (totals["withholding_numerator"], totals["returned_funder_payment_count"]) == (2550.0, 0)
    assert package["returned_funder_payments"] == []
    assert package["funders"][0]["returned_payment_count"] == 0
    # A member without classification records reads its stored metrics: an older one its numerator, a current one its
    # paid figure, its numerator and its returned payments.
    for payload, expected in ((old, (2550.0, 2550.0, 0.0, 0)), (t1_payload(), (1700.0, 2550.0, 850.0, 1))):
        bare = copy.deepcopy(payload)
        for transaction in _account(bare)["statement"]["transactions"]:
            transaction.pop("classification", None)
        row = _package(bare)["documents"][0]
        assert (row["lender_debits"], row["withholding_numerator"], row["returned_funder_payment_total"],
                row["returned_funder_payment_count"]) == expected


def test_a_mixed_currency_package_refuses_the_returned_money_and_keeps_its_count():
    package = _package(t1_payload(), returned_payload(RULE_D["T2"][0], bank="TD Canada Trust", currency="CAD",
                                                      account="000000004040"))
    totals = package["totals"]
    assert totals["cross_currency_totals_refused"] is True
    assert totals["returned_funder_payment_total"] is None and totals["returned_funder_payment_count"] == 2
    assert totals["withholding_numerator"] is None and totals["lender_debits"] is None
    funders = {item["funder"]: item for item in package["funders"]}
    assert {name: (item["returned_payment_count"], item["returned_payment_total"]) for name, item in funders.items()} == {
        "KAPITUS": (1, None), "CanaCap": (1, None)}
    # Each warning item keeps its own statement's money and unit.
    assert [(item["amount"], item["source_currency"]) for item in package["returned_funder_payments"]] == [
        (850.0, "USD"), (5295.0, "CAD")]


def test_the_served_copy_and_the_review_writer_keep_the_fields():
    from analysis.revenue import rebuild_serialized_revenue_views, record_serialized_revenue_review
    from webapp.app import _displayed

    payload = json.loads(json.dumps(_displayed(t1_payload(), settings={})))
    rebuild_serialized_revenue_views(payload)
    account = _account(payload)
    assert account["metrics"]["withholding_numerator"] == 2550.0
    record_serialized_revenue_review(payload, source_location="transaction:1", decision="reject")
    rebuild_serialized_revenue_views(payload)
    rows = [row["classification"] for row in _account(payload)["statement"]["transactions"]]
    assert (rows[2]["returned_funder_payment_by"], rows[4]["returns_funder_payment"]) == ("transaction:5", "transaction:3")
    assert _account(payload)["metrics"]["withholding_numerator"] == 2550.0


def test_the_batch_csv_and_the_cli_name_the_returned_payments():
    import batch
    from analyze import _render
    from analysis.pipeline import analyze_statement

    assert batch.FIELDS.index("returned_funder_payment_count") == batch.FIELDS.index("lender_debit_count") + 1
    assert batch.FIELDS.index("returned_funder_payment_total") == batch.FIELDS.index("lender_debit_count") + 2
    statement = _statement(RULE_D["T1"][0], balances=True)
    statement = statement.model_copy(update={"beginning_balance": 50000.0,
                                             "ending_balance": statement.transactions[-1].running_balance})
    report = analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                               model_used="fabricated-test")
    text = _render(report.accounts[0])
    assert "  Returned funder payments: 1 row(s), $850.00 (kept in withholding)" in text
    assert "    - KAPITUS: 2 txns, 1 returned unpaid, $1,700.00 debited (alias 'KAPITUS')" in text


# ---------------------------------------------------------------------------------------------- audit round 3, R3-B02
# R3-21 (the owner's Q5 ruling: "Revenue is unaffected (the return credit is non-revenue as today)"; the MCA principle:
# the business's own payment coming back is never revenue; the brief's default (a), refuse Confirm): a held return
# credit rule D matched to a confirmed funder's payment cannot be confirmed as revenue. Mark Non-Revenue and Reset stay.

#: The refusal, word for word as analysis/revenue.py, webapp/app.py and the privacy table hold it.
RETURNS_FUNDER_PAYMENT_REFUSAL = "a credit that returns a confirmed funder's payment can only be marked non-revenue"
#: Citibank's 'ACH DR RETURN' (held as possible_return) a day after the second of three weekly KAPITUS payments.
R3_21_ROWS = [(1, SALE, 20000.0), (2, KAPITUS, -850.0), (9, KAPITUS, -850.0), (10, "ACH DR RETURN", 850.0),
              (16, KAPITUS, -850.0)]


def r3_21_payload(extra=()):
    return returned_payload(sorted([*R3_21_ROWS, *extra], key=lambda row: row[0]), bank="Citibank",
                            account="000000005050")


def _row_of(payload, location):
    return next(row["classification"] for row in _account(payload)["statement"]["transactions"]
                if row["classification"]["source_location"] == location)


def _figures(payload):
    metrics = _account(payload)["metrics"]
    return (metrics["true_revenue_total"], metrics["lender_debits"], metrics["returned_funder_payment_total"],
            metrics["withholding_numerator"])


def test_r3_21_a_matched_held_return_refuses_confirm_and_keeps_reject_and_reset():
    from analysis.revenue import apply_serialized_revenue_review

    payload = r3_21_payload()
    credit = _row_of(payload, "transaction:4")
    assert (credit["revenue_tier"], credit["revenue_tier_reason"], credit["returns_funder_payment"]) == (
        "excluded_pending_review", "possible_return", "transaction:3")
    assert _figures(payload) == (20000.0, 1700.0, 850.0, 2550.0)
    before = copy.deepcopy(payload)
    with pytest.raises(ValueError) as refused:
        apply_serialized_revenue_review(payload, source_location="transaction:4", decision="confirm")
    assert str(refused.value) == RETURNS_FUNDER_PAYMENT_REFUSAL
    assert payload == before  # every check comes before the first write
    apply_serialized_revenue_review(payload, source_location="transaction:4", decision="reject")
    rejected = _row_of(payload, "transaction:4")
    assert (rejected["revenue_tier"], rejected["revenue_review_status"]) == ("non_revenue", "rejected")
    assert _figures(payload) == (20000.0, 1700.0, 850.0, 2550.0)
    assert _row_of(payload, "transaction:3")["returned_funder_payment_by"] == "transaction:4"
    apply_serialized_revenue_review(payload, source_location="transaction:4", decision="reset")
    reset = _row_of(payload, "transaction:4")
    assert (reset["revenue_tier"], reset["revenue_tier_reason"], reset["revenue_review_status"]) == (
        "excluded_pending_review", "possible_return", "pending")


def test_r3_21_a_record_stored_before_r2_ow13_carries_no_key_and_confirms_as_before():
    from analysis.revenue import apply_serialized_revenue_review

    payload = r3_21_payload()
    _row_of(payload, "transaction:4").pop("returns_funder_payment")
    apply_serialized_revenue_review(payload, source_location="transaction:4", decision="confirm")
    assert _row_of(payload, "transaction:4")["revenue_tier"] == "verified"


def test_r3_21_a_stored_confirm_is_decided_by_the_rules_on_replay():
    from webapp.reanalysis import _awaits_review, replay_reviews

    stored = r3_21_payload()
    credit = _row_of(stored, "transaction:4")
    assert not _awaits_review(credit, "confirm")
    assert _awaits_review(credit, "reject") and _awaits_review(credit, "reset")
    history = [{"id": 21, "source_location": "transaction:4", "decision": "confirm", "prior_state": json.dumps(credit),
                "decided_at": "2054-04-01T00:00:00+00:00"}]
    replay = replay_reviews(r3_21_payload(), history)
    assert (replay.replayed, replay.not_replayed, replay.decided_by_rules) == ((), (), (21,))
    held = _row_of(replay.analysis, "transaction:4")
    assert (held["revenue_tier"], held["revenue_review_status"]) == ("excluded_pending_review", "pending")


def test_r3_21_a_confirm_shown_under_yes_leaves_the_no_reading_at_its_analysis_state():
    """The Zelle readings (R2-OW17): the No reading excludes a bounce-worded Zelle credit and rule D pairs it there; the
    Yes reading counts it unpaired. A confirm shown under Yes applies in Yes; the No reading refuses it and returns to its
    analysis state (`with_both_readings` step 3). A confirm shown under No is refused."""
    from analysis import zelle_view
    from tests import zelle_setting_fixtures as fx

    stored = fx.case("Z5")
    location = fx.row(stored, fx.BOUNCE)["classification"]["source_location"]
    no, yes, carrying = zelle_view.split_readings(copy.deepcopy(stored))
    assert carrying
    assert fx.row(no, fx.BOUNCE)["classification"]["returns_funder_payment"]
    assert not fx.row(yes, fx.BOUNCE)["classification"].get("returns_funder_payment")
    updated = zelle_view.with_both_readings(copy.deepcopy(stored), shown=True,
                                            decisions=[(location, "confirm", None)])
    no, yes, _carrying = zelle_view.split_readings(updated)
    counted, excluded = fx.row(yes, fx.BOUNCE)["classification"], fx.row(no, fx.BOUNCE)["classification"]
    assert (counted["revenue_tier"], counted["revenue_review_status"]) == ("verified", "confirmed")
    assert (excluded["revenue_tier"], excluded["revenue_tier_reason"], excluded["revenue_review_status"]) == (
        "non_revenue", "zelle_excluded", "not_required")
    with pytest.raises(ValueError) as refused:
        zelle_view.with_both_readings(copy.deepcopy(stored), shown=False, decisions=[(location, "confirm", None)])
    assert str(refused.value) == RETURNS_FUNDER_PAYMENT_REFUSAL


# ---------------------------------------------------------------- audit round 4, R4-78: a bank's unworded returns
# The owner's Q5 of 2026-10-02 ("Match the return to the funder payment it reverses ..."): Citizens Bank returns a
# funder's ACH debit unpaid as a credit of the same cents that repeats the debit's own words (its trace suffix), with no
# return word, one or two business days later, beside its own RETURNED ITEM FEE row. §17.1's returned-payment default
# (10): such a credit returns that payment, the previous business day's debit (or the one whose words it repeats) taken,
# no more such credits a day than the fee rows' items. Fabricated rows: KAPITUS's daily payments of March 2054 (no US
# bank holiday in the month), each with its own trace letter.

CITIZENS = "Citizens Bank"
MARCH_2054_BUSINESS_DAYS = (2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 23, 24, 25, 26, 27, 30, 31)
FEE_ONE = "RETURNED ITEM FEE (1 AT $35.00 EACH)"
DAILY_PAYMENT = -412.5


def _trace(day: int) -> str:
    """KAPITUS's daily payment of `day`, its own trace letter after the reference."""
    return f"KAPITUS PAYMENT 00000001{chr(ord('A') + MARCH_2054_BUSINESS_DAYS.index(day))}"


def _daily(extra=(), *, days=MARCH_2054_BUSINESS_DAYS):
    """A sale on the 1st, KAPITUS's payment on each of `days`, then the `extra` rows; in day order, a day's payment
    printed before that day's extra rows."""
    rows = [(1, SALE, 20000.0)] + [(day, _trace(day), DAILY_PAYMENT) for day in days] + list(extra)
    return sorted(rows, key=lambda row: row[0])


#: The 10th's payment (a Tuesday) repeated on Wednesday the 11th, the 13th's (a Friday) on Monday the 16th, each beside
#: the bank's one-item returned-item fee.
R4_78_RETURNS = [(11, _trace(10), 412.5), (11, FEE_ONE, -35.0), (16, _trace(13), 412.5), (16, FEE_ONE, -35.0)]


def _by_day(records, amount):
    return {int(record.date[-2:]): record for record in records if record.amount == amount}


def test_r4_78_an_unworded_repeat_beside_the_bank_s_fee_returns_the_previous_day_s_payment():
    # Base: nothing paired; lender_debits includes both returned payments.
    statement = _statement(_daily(R4_78_RETURNS), CITIZENS)
    records = tc.classify_statement_transactions(statement)
    debits, credits = _by_day(records, DAILY_PAYMENT), _by_day(records, 412.5)
    assert _pairs(records) == {debits[10].source_location: credits[11].source_location,
                               debits[13].source_location: credits[16].source_location}
    for day in (10, 13):
        debit = debits[day]
        assert (debit.classification, debit.contributes_to_lender_totals, debit.contributes_to_withholding_rate,
                debit.contributes_to_lender_count, debit.contributes_to_flagged_totals) == (
            "confirmed_lender", False, True, True, False)
        assert debit.reversed_by is None
        assert debit.reason.endswith(RETURNED_UNPAID.format(debit.returned_funder_payment_by))
    # The credit day's own payment of the same cents stays paid.
    for day in (11, 16):
        assert debits[day].contributes_to_lender_totals and debits[day].returned_funder_payment_by is None
    for credit in credits.values():
        assert (credit.classification, credit.matched_rule, credit.revenue_tier) == (
            "other", "financing_proceeds_credit", "non_revenue")
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_debits == 22 * 412.5 - 825.0
    assert metrics.withholding_numerator == 22 * 412.5
    assert (metrics.returned_funder_payment_total, metrics.returned_funder_payment_count) == (825.0, 2)
    assert metrics.lenders_detected == 1
    items = detect(statement, classifications=records).returned_funder_payments
    assert [(item["debit_date"], item["credit_date"]) for item in items] == [
        ("2054-03-10", "2054-03-11"), ("2054-03-13", "2054-03-16")]


def test_r4_78_the_repeated_trace_wins_over_an_equal_debit_two_days_back():
    # The credit on Wednesday the 11th repeats Monday the 9th's words: that payment is returned, not the 10th's.
    records = _run(_daily([(11, _trace(9), 412.5), (11, FEE_ONE, -35.0)]), CITIZENS)
    debits, credits = _by_day(records, DAILY_PAYMENT), _by_day(records, 412.5)
    assert _pairs(records) == {debits[9].source_location: credits[11].source_location}


def test_r4_78_on_a_day_no_more_credits_pair_than_the_fee_s_items():
    # Two repeats on the 11th beside one fee item, none on the 12th: only the first, in row order, pairs.
    records = _run(_daily([(11, _trace(9), 412.5), (11, _trace(10), 412.5), (11, FEE_ONE, -35.0)]), CITIZENS)
    first, second = [record for record in records if record.amount == 412.5]
    assert first.returns_funder_payment is not None and second.returns_funder_payment is None
    # A two-item fee row the next business day pairs both.
    two = "RETURNED ITEM FEE (2 AT $35.00 EACH)"
    records = _run(_daily([(11, _trace(9), 412.5), (11, _trace(10), 412.5), (12, two, -70.0)]), CITIZENS)
    assert all(record.returns_funder_payment for record in records if record.amount == 412.5)


WEEKLY_MONDAYS = (2, 9, 16, 23, 30)
R4_78_CONTROLS = {
    # No fee row the credit's day or the next business day (the fee two business days later).
    "no_fee": (_daily([(11, _trace(10), 412.5), (13, FEE_ONE, -35.0)]), CITIZENS),
    # The only equal payment is dated the credit's own day.
    "same_day_only": (_daily([(16, _trace(16), 412.5), (16, FEE_ONE, -35.0)], days=WEEKLY_MONDAYS), CITIZENS),
    # Three business days after the payment.
    "three_days_later": (_daily([(12, _trace(9), 412.5), (12, FEE_ONE, -35.0)], days=WEEKLY_MONDAYS), CITIZENS),
    # A credit of other cents.
    "other_cents": (_daily([(11, _trace(10), 400.0), (11, FEE_ONE, -35.0)]), CITIZENS),
    # A credit naming another funder, which has no payment here.
    "other_funder": (_daily([(11, "ONDECK CAPITAL PAYMENT 0001", 412.5), (11, FEE_ONE, -35.0)]), CITIZENS),
    # TD Canada Trust's returns wait on audit I41 (their sign orientation is the owner's).
    "td_canada_trust": (_daily(R4_78_RETURNS), "TD Canada Trust"),
    # Rule D's guard: an equal non-lender debit as near as the payment.
    "guard": (_daily([(10, "FABRIKAM SUPPLY", -412.5), (11, _trace(10), 412.5), (11, FEE_ONE, -35.0)]), CITIZENS),
}


@pytest.mark.parametrize("name", sorted(R4_78_CONTROLS))
def test_r4_78_a_control_pairs_nothing(name):
    rows, bank = R4_78_CONTROLS[name]
    records = _run(rows, bank)
    assert _pairs(records) == {}
    assert all(record.contributes_to_lender_totals for record in records if record.classification == "confirmed_lender")


def test_r4_78_control_a_bounce_worded_credit_stays_rule_d_s(monkeypatch):
    # A bounce-worded return beside the fee is rule D's (the latest equal payment, the same day), with or without the
    # new arm.
    rows = _daily([(11, BOFA_RETURN, 412.5), (11, FEE_ONE, -35.0)])
    after = _pairs(_run(rows, CITIZENS))
    monkeypatch.setattr(tc, "_unworded_return_pairs", lambda *args, **kwargs: [])
    assert _pairs(_run(rows, CITIZENS)) == after
    debit = _by_day(_run(rows, CITIZENS), DAILY_PAYMENT)[11]
    assert after == {debit.source_location: debit.returned_funder_payment_by}


def test_r4_78_moves_no_revenue_reading(monkeypatch):
    """As T16: every credit's state, tier, reason and revenue field are the arm's input's; on a debit only the paid and
    flagged flags, the reason and the returned field move."""
    rows = _daily(R4_78_RETURNS)
    after = _run(rows, CITIZENS)
    monkeypatch.setattr(tc, "_unworded_return_pairs", lambda *args, **kwargs: [])
    before = _run(rows, CITIZENS)
    assert _pairs(before) == {}
    for old, new in zip(before, after):
        assert {key: getattr(old, key) for key in _REVENUE_FIELDS} == {key: getattr(new, key) for key in _REVENUE_FIELDS}
        assert (old.reversed_by, old.settlement_reversal, old.reversal_of, old.classification, old.is_nsf_event) == (
            new.reversed_by, new.settlement_reversal, new.reversal_of, new.classification, new.is_nsf_event)
        if new.returned_funder_payment_by is None:
            assert replace(new, returns_funder_payment=None) == replace(old, returns_funder_payment=None)
    statement = _statement(rows, CITIZENS)
    figures = [compute_metrics(statement, classifications=records) for records in (before, after)]
    for key in ("true_revenue_total", "verified_revenue_total", "non_revenue_total", "lender_credits",
                "eligible_deposits", "nsf_count", "lenders_detected", "withholding_numerator"):
        assert getattr(figures[0], key) == getattr(figures[1], key), key


def test_r4_78_the_payment_changes_read_the_bounces_as_attempts():
    # KAPITUS paid 412.50 daily through Friday the 20th; then five debits of 35.00, the 23rd to the 27th, each come back
    # the next business day beside the bank's one-item fee of the same 35.00 (the gate's own row, never the guard), and
    # nothing is debited after; the statement runs to April 10. Base: the bounced attempts read as payments: a false
    # -92% decrease, and the possible stop dated at the last bounced debit (the 27th).
    from analysis import lender_payment_changes as lpc

    rows = [(1, SALE, 20000.0)] + [(day, _trace(day), DAILY_PAYMENT) for day in MARCH_2054_BUSINESS_DAYS if day <= 20]
    for paid, back in ((23, 24), (24, 25), (25, 26), (26, 27), (27, 30)):
        rows += [(paid, _trace(paid), -35.0), (back, _trace(paid), 35.0), (back, FEE_ONE, -35.0)]
    statement = _statement(sorted(rows, key=lambda row: row[0]), CITIZENS).model_copy(
        update={"period_end": "2054-04-10"})
    records = tc.classify_statement_transactions(statement)
    assert len(_pairs(records)) == 5
    items = lpc.statement_payment_changes(records, period_start=statement.period_start,
                                          period_end=statement.period_end, currency="USD")
    assert [item["kind"] for item in items] == ["stop"]
    [stop] = items
    assert (stop["lender"], stop["last_payment_date"], stop["payments"], stop["last_attempt_returned"]) == (
        "KAPITUS", "2054-03-20", 15, {"date": "2054-03-27"})
