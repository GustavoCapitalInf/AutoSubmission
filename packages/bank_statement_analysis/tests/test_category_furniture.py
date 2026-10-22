"""Audit round 3, R3-B08 (R3-92; true revenue spec §7.0, §17.1): statement furniture a parser glued onto a credit's
text (TD's back panel, a Symitar credit union's fee and balance summaries, Citizens' continued-page header) never
decides the credit's category. The category chain (the fee, transfer, tax, payroll, utility, rent, check and
subscription rules) and the record's is_check, is_ach and is_pos_context flags read a credit without its furniture
(without_statement_furniture), as every credit revenue rule already reads it (revenue_text); the record's text and
description keep the furniture, and the registry, lender-credit, dealer-funding, NSF and refund readers keep their
text. A debit keeps today's text until the owner admits the G7 move (§17.1, "Debit readings waiting on a G7
admission"). Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction

HOLDER = "NORTHWIND PLUMBING LLC"
TD_PANEL = ("CALL 1 800 000 0000 FOR 24 HOUR BANK BY PHONE HOW TO BALANCE YOUR ACCOUNT SUBTRACT ANY SERVICES CHARGES "
            "SHOWN ON THIS STATEMENT")
SYMITAR_SUMMARY = "FEE SUMMARY THIS PERIOD THIS PERIOD YEAR TO DATE TOTAL OVERDRAFT FEES 0 00"
CITIZENS_HEADER = "PLEASE SEE ADDITIONAL INFORMATION ON NEXT PAGE ATM PURCHASES CONTINUED"


def _records(rows, bank):
    return classify_statement_transactions(Statement(bank=bank, account_name=HOLDER, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


@pytest.mark.parametrize(("bank", "kept", "furniture"), [
    ("TD Bank", "DEPOSIT CONTOSO SUPPLY", TD_PANEL),
    ("Sample Federal Credit Union", "DEPOSIT CONTOSO SUPPLY", SYMITAR_SUMMARY),
])
def test_r3_92_a_credit_s_furniture_never_decides_its_category(bank, kept, furniture):
    [glued] = _records([(f"{kept} {furniture}", 500.0)], bank)
    [clean] = _records([(kept, 500.0)], bank)
    assert glued.classification != "fee"
    assert (glued.classification, glued.matched_rule) == (clean.classification, clean.matched_rule)
    # The revenue reading already read the row without its furniture: unchanged.
    assert (glued.revenue_tier, glued.revenue_tier_reason, glued.revenue_match_method) == (
        clean.revenue_tier, clean.revenue_tier_reason, clean.revenue_match_method)
    assert glued.revenue_tier == "counted_flagged"
    # The record keeps the text as printed.
    assert furniture.split()[0] in glued.normalized_description
    assert not glued.is_nsf_event


@pytest.mark.parametrize(("furniture", "flag"), [
    ("CLEARED CHECK RECAP 1234 100 00", "is_check"),
    ("CALL 1 800 000 0000 FOR 24 HOUR BANK BY PHONE ACH ITEMS", "is_ach"),
    ("PLEASE SEE ADDITIONAL INFORMATION ON NEXT PAGE POS PURCHASES CONTINUED", "is_pos_context"),
])
def test_r3_92_a_credit_s_furniture_never_sets_its_check_ach_or_pos_flag(furniture, flag):
    [record] = _records([(f"DEPOSIT CONTOSO SUPPLY {furniture}", 500.0)], "Fabrikam Bank")
    assert getattr(record, flag) is False
    assert record.matched_rule != "check"


def test_r3_92_a_credit_s_own_words_still_decide_its_category_and_flags():
    [check, ach] = _records(
        [("CHECK DEPOSIT 1234 " + TD_PANEL, 500.0), ("ACH CREDIT CONTOSO SUPPLY " + TD_PANEL, 500.0)], "TD Bank"
    )
    assert check.is_check and check.matched_rule == "check"
    assert ach.is_ach


def test_r3_92_debits_keep_today_s_text_by_default():
    # The owner's G7 admission is pending (§17.1): if admitted, flip these to credit_card_payment (credit_cards,
    # flagged) and pos.
    card, pos = _records([
        ("CCD DEBIT AMEX EPAYMENT ACH PMT " + TD_PANEL, -120.0),
        ("POS PURCHASE CONTOSO MARKET " + CITIZENS_HEADER, -38.0),
    ], "TD Bank")
    assert (card.classification, card.flagged_group) == ("fee", None)
    assert pos.classification == "other"
    assert pos.is_pos_context
    assert not card.is_nsf_event and not pos.is_nsf_event


@pytest.mark.parametrize(("text", "amount", "classification"), [
    ("SERVICE CHARGE REFUND", 15.0, "refund_or_reversal"),
    ("MONTHLY SERVICE FEE", -15.0, "fee"),
    ("MONTHLY SERVICE FEE", 15.0, "fee"),
    ("NSF RETURNED ITEM " + TD_PANEL, 400.0, "nsf_or_return"),
])
def test_r3_92_the_real_fee_refund_and_nsf_rows_keep_their_classes(text, amount, classification):
    record = classify_transaction(text, amount, bank="TD Bank")
    assert record.classification == classification
    assert record.is_nsf_event is (classification == "nsf_or_return")
