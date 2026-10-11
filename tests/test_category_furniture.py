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
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction

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


@pytest.mark.parametrize(("furniture", "bank"), [(TD_PANEL, "TD Bank"), (SYMITAR_SUMMARY, "Sample Federal Credit Union")])
def test_r4_24_recorded_residual_a_funder_debit_with_td_s_back_panel_reads_fee_under_default_b(furniture, bank):
    """Audit round 4, R4-24: the lender stake of §17.1's open R3-92 question ("Debit readings waiting on a G7
    admission"), pinned as the code reads it under the shipped default (b). A confirmed funder's debit with TD's back
    panel or a Symitar fee summary glued on reads as a bank fee (the fee rule runs before the known payee on the debit's
    full text): out of paid to lenders, the withholding rate and the payment changes. This pin changes only with the
    owner's answer to R3-92 (option (a) or (c) would read it as the funder's payment)."""
    [glued] = _records([("CCD DEBIT ONDECK CAPITAL " + furniture, -500.0)], bank)
    [clean] = _records([("CCD DEBIT ONDECK CAPITAL", -500.0)], bank)
    assert (glued.classification, glued.matched_rule, glued.canonical_entity) == ("fee", "bank_or_processing_fee", None)
    assert not glued.contributes_to_lender_totals and not glued.contributes_to_withholding_rate
    assert (clean.classification, clean.canonical_entity) == ("confirmed_lender", "ONDECK")
    # Citizens' continued-page header holds no fee word: the funder's debit keeps its reading.
    [citizens] = _records([("CCD DEBIT ONDECK CAPITAL " + CITIZENS_HEADER, -500.0)], "Citizens Bank")
    assert (citizens.classification, citizens.canonical_entity) == ("confirmed_lender", "ONDECK")


def test_r4_24_recorded_residual_td_s_fdic_footer_reads_a_registry_less_loan_payment_as_td_s_loan():
    """Audit round 4, R4-24: the residual neither (a) nor (c) closes: TD's FDIC footer on a registry-less LOAN PMT debit
    names TD Bank, so the bank-loan reader (which reads the full row) reads it as TD's own loan; without the footer
    it is an unidentified lender obligation."""
    [footer] = _records([("LOAN PMT FABRIKAM EQUIPMENT BANK DEPOSITS FDIC INSURED TD BANK N A", -500.0)], "TD Bank")
    [clean] = _records([("LOAN PMT FABRIKAM EQUIPMENT", -500.0)], "TD Bank")
    assert (footer.classification, footer.canonical_entity) == ("bank_loan", "TD Bank")
    assert clean.classification == "potential_lender"


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
