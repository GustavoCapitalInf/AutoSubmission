"""Audit round 3, R3-B01 (R3-80; the owner's rule of 2026-09-25, "the bank's overdraft charge for an item is a fee, even
when it prints the item's payee", completed): a bank's charge that names a funder is a charge, never a funder payment.

Two DEBIT-ONLY word tuples beside the NSF and fee words (analysis/transaction_classifier/), read before the registry:
`_DEBIT_ITEM_CHARGE_NSF_PATTERNS` (step 2: a returned or unpaid item's CHARGE/CHG, `nsf_or_return`) and
`_DEBIT_BANK_CHARGE_FEE_PATTERNS` (step 6: a stop-payment charge, an OD item charge and a bare stop-payment instruction at
the row's start, `fee`). A credit keeps today's reading, so no revenue reading moves. The forms that may be the funder's
own debit (`ACH DEBIT RETURNED <funder>`, a bare `UNPAID ITEM <funder>`, `OVERDRAFT ITEM <funder> DES:PAYMENT`) keep
today's reading, a recorded residual (true revenue spec §20).

Fabricated rows only (CONTOSO BAKERY LLC; FABRIKAM SUPPLY INC sales; KAPITUS, ONDECK CAPITAL, FORA FINANCIAL and FORWARD
FINANCING, public funders of the registry; 2054 dates; neutral whole amounts)."""
from __future__ import annotations

import pytest

from analysis import lender_payment_changes as lpc
from analysis import transaction_classifier as tc
from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction

HOLDER = "CONTOSO BAKERY LLC"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO BAKERY LLC CO ID:0000000001 CCD"
KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO BAKERY LLC CO ID:0000000002 CCD"
BANKS = ("Bank of America", "JPMorgan Chase")

#: Read as a bank charge (`fee`), never a lender.
FEE_CHARGES = (
    "STOP PAYMENT KAPITUS",
    "ACH STOP PAYMENT FORWARD FINANCING",
    "STOP PAY REQUEST FORWARD FINANCING",
    "STOP PAYMENT ORDER ONDECK CAPITAL",
    "STOP PMT CHG FORWARD FINANCING",
    "STOP PAYMENT CHARGE FORA FINANCIAL",
    "OD ITEM CHARGE ONDECK CAPITAL",
    "STOP PAY CHARGE",
    "STOP PAYMENT CHARGE 0000",
)
#: Read as a returned item's charge (`nsf_or_return`), never a lender.
NSF_CHARGES = (
    "RETURNED ITEM CHARGE FORA FINANCIAL",
    "RETURN ITEM CHARGE KAPITUS",
    "UNPAID ITEM CHARGE FORA FINANCIAL",
    "RETURNED ITEM CHARGE",
)


def _no_lender_contribution(record) -> bool:
    return not (record.contributes_to_lender_totals or record.contributes_to_withholding_rate
                or record.contributes_to_lender_count or record.contributes_to_potential_lender_totals)


@pytest.mark.parametrize("bank", BANKS)
@pytest.mark.parametrize("printed", FEE_CHARGES)
def test_a_stop_payment_or_item_charge_is_a_fee_never_a_lender(printed, bank):
    record = tc.classify_transaction(printed, -35.0, bank=bank)
    assert (record.classification, record.matched_rule, record.canonical_entity) == (
        "fee", "bank_or_processing_fee", None)
    assert _no_lender_contribution(record)


@pytest.mark.parametrize("bank", BANKS)
@pytest.mark.parametrize("printed", NSF_CHARGES)
def test_a_returned_or_unpaid_item_charge_is_a_returned_item_never_a_lender(printed, bank):
    record = tc.classify_transaction(printed, -35.0, bank=bank)
    assert (record.classification, record.matched_rule, record.canonical_entity) == (
        "nsf_or_return", "nsf_or_return", None)
    assert _no_lender_contribution(record)


def _statement(rows, *, period_end="2054-03-31", bank="Bank of America") -> Statement:
    """The rows (ISO day, description, amount) in their order."""
    transactions = [Transaction(date=day, description=text, amount=amount,
                                direction="credit" if amount > 0 else "debit") for day, text, amount in rows]
    return Statement(account_name=HOLDER, bank=bank, period_start="2054-03-01", period_end=period_end,
                     transactions=transactions)


def test_a_stop_payment_naming_a_funder_makes_no_lender_of_it():
    # Today: 1 lender, 35.00 paid and 35.00 in the withholding numerator, from one stop-payment charge.
    statement = _statement([("2054-03-02", SALE, 12000.0), ("2054-03-09", SALE, 12000.0),
                            ("2054-03-16", "STOP PAYMENT FORA FINANCIAL", -35.0)])
    records = tc.classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lenders_detected, metrics.lender_debits, metrics.withholding_numerator) == (0, 0.0, 0.0)
    assert metrics.true_revenue_total == 24000.0
    assert records[2].classification == "fee"


def test_a_stop_payment_charge_after_a_funder_s_last_payment_keeps_its_possible_stop():
    # R2-OW18: four weekly KAPITUS payments, then the bank's stop-payment charge naming KAPITUS near the period's end.
    # Read as a payment-sized one-off, the charge was presence and removed the possible stop it is evidence of.
    rows = [("2054-03-02", SALE, 12000.0), ("2054-03-09", SALE, 12000.0)]
    rows += [(f"2054-03-{day:02d}", KAPITUS, -400.0) for day in (2, 9, 16, 23)]
    rows.append(("2054-04-27", "STOP PAYMENT KAPITUS", -30.0))
    rows.sort(key=lambda row: row[0])
    statement = _statement(rows, period_end="2054-04-30")
    records = tc.classify_statement_transactions(statement)
    items = lpc.statement_payment_changes(records, period_start=statement.period_start,
                                          period_end=statement.period_end, currency="USD")
    stops = [item for item in items if item["kind"] == "stop"]
    assert [(item["lender"], item["stop_confirmed"], item["last_presence_date"]) for item in stops] == [
        ("KAPITUS", False, "2054-03-23")]


# ---------------------------------------------------------------------------------------------------- controls


@pytest.mark.parametrize(
    ("printed", "state"),
    [
        ("STOP PAYMENT FEE KAPITUS", "fee"),
        ("RTN STOP PAYMENT KAPITUS", "nsf_or_return"),
        ("RETURNED ITEM FEE KAPITUS", "nsf_or_return"),
    ],
)
def test_the_existing_fee_and_returned_item_words_read_as_before(printed, state):
    assert tc.classify_transaction(printed, -35.0).classification == state


@pytest.mark.parametrize(
    ("printed", "entity"),
    [
        # The recorded residual (true revenue spec §20): each may be the funder's own debit (or a payment paid into
        # overdraft), so it keeps today's lender reading.
        ("ACH DEBIT RETURNED ONDECK CAPITAL", "ONDECK"),
        ("UNPAID ITEM FORA FINANCIAL", "FORA FINANCIAL"),
        ("OVERDRAFT ITEM KAPITUS DES:PAYMENT", "KAPITUS"),
    ],
)
def test_the_forms_that_may_be_the_funder_s_own_debit_keep_their_lender_reading(printed, entity):
    record = tc.classify_transaction(printed, -400.0)
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", entity)
    assert record.contributes_to_lender_totals


def test_a_payee_whose_name_holds_stop_is_never_read_as_a_stop():
    # STOP is not at the row's start, and PAYMENTS is no stop form: today's reading.
    printed = "FABRIKAM STOP PAYMENTS LLC DES:PAYMENT ID:0001 INDN:CONTOSO BAKERY LLC CO ID:0000000003 CCD"
    record = tc.classify_transaction(printed, -500.0)
    assert (record.classification, record.matched_rule) == ("other", "no_classification_rule")


def _without_the_new_words(monkeypatch):
    monkeypatch.setattr(tc, "_DEBIT_ITEM_CHARGE_NSF_PATTERNS", ())
    monkeypatch.setattr(tc, "_DEBIT_BANK_CHARGE_FEE_PATTERNS", ())


@pytest.mark.parametrize("printed", [*FEE_CHARGES, *NSF_CHARGES, "ACH RETURN KAPITUS STOP PAYMENT"])
def test_a_credit_keeps_today_s_reading(monkeypatch, printed):
    # The tuples are debit-only: a credit printing the same words reads exactly as without them.
    after = tc.classify_transaction(printed, 35.0)
    _without_the_new_words(monkeypatch)
    before = tc.classify_transaction(printed, 35.0)
    assert after == before


def test_a_funder_s_return_printing_stop_payment_still_pairs(monkeypatch):
    # A KAPITUS payment and the bank's return of it printing STOP PAYMENT: paired as today (the debit returned unpaid).
    rows = [("2054-03-02", SALE, 12000.0), ("2054-03-03", KAPITUS, -400.0),
            ("2054-03-05", "ACH RETURN KAPITUS STOP PAYMENT", 400.0)]
    after = tc.classify_statement_transactions(_statement(rows))
    _without_the_new_words(monkeypatch)
    before = tc.classify_statement_transactions(_statement(rows))
    assert after == before
    debit = after[1]
    assert debit.classification == "confirmed_lender"
    assert (debit.returned_funder_payment_by or debit.reversed_by) == "transaction:3"
    assert debit.contributes_to_withholding_rate and not debit.contributes_to_lender_totals
