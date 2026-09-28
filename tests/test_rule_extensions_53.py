"""5.3 (2026-09-27): existing rules read the bank wording they missed, so these rows change state. Fabricated
descriptors only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import fake_payees, txn  # noqa: F401  (fixture)

WEEKLY = (2, 9, 16, 23)


def _state(description: str, amount: float = -100.0, *, bank: str | None = None) -> tuple[str, str, str | None]:
    record = classify_transaction(description, amount, bank=bank)
    return record.classification, record.matched_rule, record.canonical_entity


# --- B1: bank charges and returned items --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    [
        "OVERDRAWN HANDLING CHGS", "WIRE TRANS SVC CHARGE 0001", "INTERAC-SC-1234", "ACH BATCH CHARGE, ACH CHARGE SBIB",
        "W/D SVC 01/05 FAB PAI ATM", "FRAIS DECOUVERT 01/05", "FRAIS, CHEQUE SANS PROVISION", "EXTENDED OVERDRAFT CHG",
        "OD CHARGE", "PAID ITEM CHARGE", "UNCOLLECTED FUNDS CHARGE", "MERCHANT SERVICES CHG",
    ],
)
def test_bank_charges_in_abbreviated_and_french_wording_are_fees(description):
    assert _state(description, -5.0)[:2] == ("fee", "bank_or_processing_fee")


@pytest.mark.parametrize("description", ["RTN STOP PAYT 1234", "FR. EFFET RET.", "RETURNED STOP PAYMENT 1234"])
def test_returned_items_in_abbreviated_and_french_wording_are_nsf_or_return(description):
    assert _state(description, -100.0)[0] == "nsf_or_return"


def test_a_deposited_item_returned_under_a_stop_payment_is_a_reversal():
    assert _state("Deposited Item Returned Stop Payment 1234", 700.0)[0] == "refund_or_reversal"


def test_french_loan_wording_after_frais_stays_a_bank_loan():
    assert _state("FRAIS INTERETS SUR PRET 1234", -50.0, bank="Fabricated Bank")[:2] == ("bank_loan", "french_loan_wording")


def test_a_returned_funder_debit_credit_keeps_its_financing_proceeds_revenue(fake_payees):
    record = classify_transaction("FABRICATED LENDER ACH DEBIT RETURNED STOP PAYMENT", 400.0)
    assert record.classification == "nsf_or_return"
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion
