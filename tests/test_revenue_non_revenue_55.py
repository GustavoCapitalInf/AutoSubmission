"""Classification 5.5 (true revenue spec §6.3, §7.11, T5): the narrowed non-revenue rules, the newly named non-revenue,
the tightened CUSTOMER descriptor, and the channel gate's declared demotions. Fabricated rows only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import (
    classify_statement_transactions,
    classify_transaction,
    prints_internal_transfer_designation,
)


def _credit(printed: str, *, holder: str | None = None):
    return classify_transaction(printed, 300.0, account_name=holder, direction="credit")


@pytest.mark.parametrize("printed", [
    "SAMPLE STATE MEDICAID DES:REIMBURSEMENT ID:1",
    "FABRIKAM HEALTH DES:HCCLAIMPMT REIMBURSEMENT ID:1",
    "SAMPLE COUNTY GEMT REIMBURSEMENT 1234",
])
def test_reimbursement_with_a_claim_signal_leaves_non_revenue(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


@pytest.mark.parametrize("printed", [
    "UNITEDHEALTHCARE DES:REIMBURSEMENT ID:1",
    "STATE OF TEXAS DES:TRAVEL REIMBURSEMENT ID:1",
    "FABRIKAM INC DES:EXPENSE REIMBURSEMENT ID:1",
])
def test_reimbursement_without_a_claim_signal_stays_non_revenue(printed):
    assert _credit(printed).revenue_classification == "non_revenue"


def test_exp_reimb_is_not_the_whole_word_so_it_is_not_non_revenue():
    assert _credit("FABRIKAM INC DES:EXP REIMB ID:1").revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("printed", [
    "WIRE FROM 12 OAK LN SAMPLEVILLE",
    "ATM DEPOSIT 450 PINE HILL LN SAMPLEVILLE",
])
def test_a_street_ln_no_longer_reads_as_a_loan(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


def test_a_loan_ln_still_reads_as_a_loan():
    assert _credit("1234 COMMERCIAL LN PMT").revenue_classification == "non_revenue"
    assert _credit("000123 AUTO LN DISB").revenue_classification == "non_revenue"
    assert classify_transaction("TRUIST LN PYMT", -500.0).normalized_description == "TRUIST LOAN PYMT"


def test_rbc_s_funds_transfer_credit_names_its_sender():
    record = _credit("FUNDS TRANSFER CREDIT TT FABRIKAM SUPPLY LTD SAMPLEVILLE")
    assert record.revenue_classification == "unverified_deposit"
    assert not prints_internal_transfer_designation("FUNDS TRANSFER CREDIT TT FABRIKAM SUPPLY LTD SAMPLEVILLE")
    assert prints_internal_transfer_designation("FUNDS TRANSFER FROM SAVINGS 1234")


@pytest.mark.parametrize(("printed", "state"), [
    ("DEBIT CARD CREDIT VISA DIRECT SQUARE INC", "verified_revenue"),
    ("Debit Card Credit: Stripe Payout", "verified_revenue"),
    ("Debit Card Credit: Stripe", "non_revenue"),
    ("DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA", "non_revenue"),
    ("DEBIT CARD CREDIT DOORDASH*FABRIKAM DELI", "non_revenue"),
    ("POS CREDIT PAYPAL *FABRIKAM STORE", "non_revenue"),
])
def test_a_card_credit_is_released_only_for_a_push_or_a_processor_payout(printed, state):
    assert _credit(printed).revenue_classification == state


def test_three_card_refunds_never_verify_each_other():
    for printed in ("DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA", "DEBIT CARD CREDIT DOORDASH*FABRIKAM DELI",
                    "POS CREDIT PAYPAL *FABRIKAM STORE"):
        records = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[
            Transaction(date=f"2054-03-{day:02d}", description=printed, amount=20.0 + day, direction="credit")
            for day in (2, 9, 16)
        ]))
        assert {record.revenue_classification for record in records} == {"non_revenue"}


def test_customer_id_and_a_customer_check_never_verify():
    assert _credit("ACH CORP CREDIT FABRIKAM SUPPLY CUSTOMER ID 12345 PAYMENT").revenue_classification == (
        "unverified_deposit")
    assert _credit("FABRIKAM CUSTOMER CHECK PAYMENT").revenue_classification == "unverified_deposit"
    assert _credit("FABRIKAM CUSTOMER ACH PAYMENT").revenue_classification == "verified_revenue"


@pytest.mark.parametrize(("printed", "rule"), [
    ("FABRIKAM DES:PAYMENT RTN ID:1", "returned_cancelled_reversed_or_provisional_credit"),
    ("FABRIKAM WIRE RECALLED 1234", "returned_cancelled_reversed_or_provisional_credit"),
    ("FABRIKAM DES:CHBK REVSL ID:1", "returned_cancelled_reversed_or_provisional_credit"),
    ("IRS TREAS 310 DES:TAX REF ID:1", "non_operating_credit"),
    ("SAMPLE STATE DES:TAXRFD ID:1", "non_operating_credit"),
    ("FRANCHISE TAX BD DES:CASTTAXRFD ID:1 PPD", "non_operating_credit"),   # glued to the state (review I6)
    ("IRS TREAS 310 DES:TAXEIC ID:1", "non_operating_credit"),
    ("SQUARE INC DES:SQ CAP1234 ID:1", "square_capital_credit"),
    ("SBAD TREAS 310 DES:MISC PAY ID:1", "sba_disbursement_credit"),
    ("EIDL 1234 SAMPLE", "sba_disbursement_credit"),
    ("FABRIKAM DES:ACCTVERIFY ID:1", "non_operating_credit"),
    ("FABRIKAM MICRO DEPOSIT", "non_operating_credit"),
])
def test_the_newly_named_non_revenue(printed, rule):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_matched_rule) == ("non_revenue", rule)


def test_square_capital_and_sba_proceeds_leave_eligible_deposits():
    record = _credit("SQUARE INC DES:SQ CAP1234 ID:1")
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("printed", [
    "ZELLE PAYMENT FROM JOHN SMITH MEMO INVOICE PAYMENT CONF 99",
    "MOBILE DEPOSIT CUSTOMER PAYMENT REF 1234",
    "CUSTOMER DEPOSIT",
    "ZELLE PAYMENT FROM FABRIKAM SUPPLY LLC CONF 99",
    "RTP CREDIT FROM FABRIKAM LLC INV 1234",
])
def test_the_channel_gate_never_verifies(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


def test_a_real_time_payout_verifies_through_the_registry_only():
    records = classify_statement_transactions(Statement(account_name="SAMPLE SHOP LLC", transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=f"RTP CREDIT AMAZON COM {day}", amount=400.0 + day,
                    direction="credit")
        for day in (2, 9, 16)
    ]))
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}
