"""5.3 (2026-09-27): existing rules read the bank wording they missed, so these rows change state. Fabricated
descriptors only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction
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


# --- B2: cheque spellings ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    ["CHQ 123", "CHQ#123", "SHARE DRAFT (12345)", "Draft Withdrawal Draft # 1234", "CHK 1234", "IMAGE CHK 1234", "CK #1234"],
)
def test_canadian_and_credit_union_cheque_spellings_are_cheques(description):
    record = classify_transaction(description, -500.0)
    assert (record.classification, record.matched_rule, record.is_check) == ("other", "check", True)


@pytest.mark.parametrize(
    "description",
    ["PRE-AUTHORIZED PAYMENT BUS CHQ FAB CAPITAL", "ACH DEBIT FAB CAPITAL SHARE DRAFT",
     "Draft Withdrawal ACH FAB CAPITAL LLC", "PAID TO - FAB CAPITAL CHK 1234567"],
)
def test_a_cheque_word_that_is_not_the_instrument_never_claims_the_row(description):
    assert classify_transaction(description, -500.0).matched_rule != "check"


def test_a_known_payee_after_the_cheque_number_is_still_named(fake_payees):
    assert classify_transaction("CHQ 417 FABRICATED LENDER", -500.0).classification == "confirmed_lender"


# --- B4: card-payment wording, and an issuer printed alone --------------------------------------------------------

def test_the_run_together_creditcard_is_card_payment_wording():
    assert _state("BARCLAYCARD US DES:CREDITCARD ID:0001 INDN:FAB HOLDER CO ID:0002 PPD") == (
        "credit_card_payment", "credit_card_payment", "Barclays Bank Delaware [credit card payment]")


def test_a_recurring_card_payment_memo_is_a_card_payment():
    assert _state("NFCU ACH 0001 CREDIT CARD RECUR")[:2] == ("credit_card_payment", "credit_card_payment")


def _d6_states(description: str) -> set[tuple[str, str]]:
    statement = Statement(transactions=[txn(f"2054-01-{day:02d}", description, -300.0) for day in WEEKLY])
    return {(record.classification, record.match_method) for record in classify_statement_transactions(statement)}


@pytest.mark.parametrize("description", ["VISA TD ABC123", "CAPTL ONE MC ABC123", "Electronic Withdrawal To APPLECARD GSBANK"])
def test_an_issuer_printed_alone_stays_unflagged_and_is_not_a_d6_payee(description):
    assert _d6_states(description) == {("other", "default")}


@pytest.mark.parametrize("description", ["FABRICATED SYF CAPITAL LLC", "SYF FAB CAPITAL LLC"])
def test_an_issuer_token_inside_a_funder_name_never_hides_it(description):
    assert _d6_states(description) == {("potential_lender", "recurring_fixed_debit")}


# --- B6: mortgage wording, a transfer to the bank's loans, the bank's own loan interest ----------------------------

@pytest.mark.parametrize("description", ["FAB SERVICER DES:MTG PYMTS ID:0001", "MTGE PAYMENT 1234", "MTG PYMT 1234"])
def test_mortgage_payment_abbreviations_are_mortgages(description):
    assert _state(description, -900.0)[:2] == ("mortgage", "mortgage_descriptor")


def test_a_transfer_to_the_banks_loans_is_its_own_loan():
    assert _state("Loan payment ICPAYMENT TRANSFER TO LOANS 1234", -300.0, bank="Fabricated Bank") == (
        "bank_loan", "own_bank_loan_transfer", "Fabricated Bank")


def test_the_banks_own_loan_interest_is_a_bank_loan():
    assert _state("LOAN INTEREST CHARGE", -100.0, bank="Fabricated Bank") == (
        "bank_loan", "unnamed_loan_payment", "Fabricated Bank")


def test_loan_interest_that_names_a_payee_is_not_the_banks():
    assert _state("FAB CAPITAL LOAN INTEREST", -100.0)[0] != "bank_loan"


# --- B7: POS labels ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description",
    ["MOBILE PURCHASE 0105 FAB MART MIAMI FL", "RETAIL PURCHASE 123456789012 FAB GAS",
     "PIN PURCHASE FAB MART SPRINGFIELD IL 0109", "C/ACHAT 12345678901 FAB EPICERIE", "ACHAT AU DETAIL FAB EPICERIE",
     "ACHAT PAR CARTE 0105 FAB EPICERIE", "DEBIT ACHAT EN LIGNE FAB BOUTIQUE"],
)
def test_bank_card_purchase_labels_are_pos_purchases(description):
    assert _state(description, -10.0)[:2] == ("pos", "point_of_sale_purchase")


def test_a_french_receivables_purchase_is_not_a_pos_purchase():
    # ACHAT alone is also a factor's or lessor's wording: only the evidenced card forms are POS
    assert _state("ACHAT DE CREANCES FAB AFFACTURAGE", -900.0)[0] != "pos"


def test_a_known_payee_paid_by_card_keeps_its_group(fake_payees):
    assert _state("MOBILE PURCHASE 0105 FABRICATED LENDER", -100.0)[0] == "confirmed_lender"


# --- B8: related-party loans -----------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "description", ["SHAREHOLDER LOAN REPAYMENT 1234567", "ACH DEBIT OWNER LOAN REPAYMENT", "DUE TO SHAREHOLDER 1234"]
)
def test_a_loan_from_the_businesss_own_people_names_no_lender(description):
    assert _state(description, -1000.0)[:2] == ("other", "related_party_loan")


def test_a_named_payee_with_owner_loan_words_keeps_the_potential_rules():
    assert _state("FAB CAPITAL OWNER LOAN PMT", -1000.0)[0] == "potential_lender"
