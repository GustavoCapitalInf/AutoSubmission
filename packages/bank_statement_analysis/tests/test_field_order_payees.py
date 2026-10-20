"""5.3 (owner ruling 2026-09-27): admitted payees printed in the bank's field order (FIELD_ORDER_PAYEE_FORMS).
Fabricated descriptors in the Chase and Truist layouts; the payees are the registry's admitted American Express
entities."""
from __future__ import annotations

import pytest

from analysis.classification_registry import FIELD_ORDER_PAYEE_FORMS, PAYEE_GROUP_REGISTRIES
from analysis.transaction_classifier import classify_transaction

CHASE_LOAN = ("Orig CO Name:American Express Orig ID:1234567890 Desc Date:540105 CO Entry Descr:Loan Pmt Sec:CCD "
              "Trace#:1234 Ind Name:Fab Holder")
CHASE_LOAN_GLUED = "Orig CO Name:American Express Orig ID:1234567890 Desc Date: CO Entry Descr:Loan PmtSec:CCD"
TRUIST_LOAN = "ACH CORP DEBIT LOAN PMT AMERICAN EXPRESS FAB HOLDER CUSTOMER ID 0001"
CHASE_CARD = "Orig CO Name:American Express Orig ID:1234567890 Desc Date:540105 CO Entry Descr:ACH Pmt Sec:PPD"


@pytest.mark.parametrize("description", [CHASE_LOAN, CHASE_LOAN_GLUED, TRUIST_LOAN])
def test_amex_loan_payments_in_field_order_are_an_alternative_position(description):
    record = classify_transaction(description, -500.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "alternative_position", "American Express Loans", "alternative_positions")
    assert (record.match_method, record.matched_rule, record.matched_alias) == (
        "known_payee_field_order", "alternative_position_field_order", None)
    assert not record.contributes_to_potential_lender_totals and not record.contributes_to_withholding_rate


def test_a_chase_amex_card_payment_is_a_named_credit_card_payment():
    record = classify_transaction(CHASE_CARD, -500.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "credit_card_payment", "American Express [credit card payment]", "credit_cards")


@pytest.mark.parametrize(
    "description",
    [
        # a merged row, in either order: the other originator's LOAN PMT stays in review
        "Orig CO Name:American Express Orig ID:1 Desc Date:540105 CO Entry Descr:ACH Pmt Sec:CCD "
        "Orig CO Name:Fab Funding Orig ID:2 Desc Date:540105 CO Entry Descr:Loan Pmt Sec:CCD",
        "Orig CO Name:American Express Orig ID:1 Desc Date:540105 CO Entry Descr:Loan Pmt Sec:CCD "
        "Orig CO Name:Fab Funding Orig ID:2 Desc Date:540105 CO Entry Descr:ACH Pmt Sec:CCD",
        # a wire memo that names Amex: the payee is the beneficiary
        "A/C: Fabricated Funding Ref: Loan Payment American Express Card",
    ],
)
def test_a_merged_row_or_a_memo_never_becomes_an_amex_payment(description):
    assert classify_transaction(description, -500.0).classification == "potential_lender"


def test_credits_keep_todays_rules():
    record = classify_transaction(
        "Orig CO Name:American Express Orig ID:1234567890 Desc Date:540105 CO Entry Descr:Loan Sec:CCD", 3000.0)
    assert record.classification == "other"
    assert record.revenue_match_method == "strong_non_revenue_rule"
    assert not record.contributes_to_lender_credit_exclusion


def test_every_field_order_entity_is_a_known_payee_entity():
    entities = {entity for registry in PAYEE_GROUP_REGISTRIES.values() for entity in registry}
    assert set(FIELD_ORDER_PAYEE_FORMS) <= entities
