from __future__ import annotations

import pytest

from analysis.transaction_classifier import obligations
from analysis.classification import operating_sources
from analysis.classification import tax_forms
from analysis.descriptor import financing
from analysis.transaction_classifier.row import classify_transaction


@pytest.mark.parametrize(
    ("description", "state", "group"),
    [
        ("LINE OF CREDIT PAYMENT 0001", "line_of_credit", "lines_of_credit"),
        ("LOAN PMT LINE OF CREDIT", "line_of_credit", "lines_of_credit"),
        ("ACH DEBIT LOC PAYMENT", "line_of_credit", "lines_of_credit"),
        ("ACH DEBIT FABRICATED HOME MORTGAGE PMT", "mortgage", "mortgages"),
        ("VEHICLE LOAN PAYMENT 0001", "vehicle_financing", "vehicle_financing"),
        ("AUTO LN PMT 0001", "vehicle_financing", "vehicle_financing"),
        ("AUTO LEASE FABRICATED", "vehicle_financing", "vehicle_financing"),
        ("VEHICLE PAYMENT FABRICATED", "vehicle_financing", "vehicle_financing"),
        ("EQUIPMENT RENTAL FABRICATED", "lease_or_rental", "leases_rentals"),
        ("FABRICATED LEASING PMT", "lease_or_rental", "leases_rentals"),
        ("LEASE PAYMENT FABRICATED", "lease_or_rental", "leases_rentals"),
        ("CHECKCARD 0102 EQUIPMENT LEASE", "lease_or_rental", "leases_rentals"),
        ("CREDIT CARD PAYMENT FABRICATED", "credit_card_payment", "credit_cards"),
        # Owner decisions 2026-09-25 (fabricated rows).
        ("PAYOFF 2054 FABRICATED MODEL VIN 0001", "floor_plan_financing", "floor_plan"),
        ("WEB PMT HOME EQUITY LOAN 0001", "mortgage", "mortgages"),
        ("WEB PMT FABRICATEDHOMEEQUITYLOAN 0001", "mortgage", "mortgages"),
        ("STUDENT LOAN PAYMENT 0001", "personal_loan", "personal_loans"),
        ("ORIG CO NAME COMMERCIAL LOAN ORIG ID 0001", "bank_loan", "bank_loans"),
        ("SAVINGS BANK LOAN PMT 0001", "bank_loan", "bank_loans"),
        ("CREDIT CARD ECS PAYMENT 0001", "credit_card_payment", "credit_cards"),
        ("VISA DES PAYMENT ID 0001", "credit_card_payment", "credit_cards"),
        ("ORIG CO NAME MASTERCARD ORIG ID 0001 CO ENTRY DESCR PAYMENT SEC CCD", "credit_card_payment", "credit_cards"),
        ("ONLINE BANKING PMT TO CRD 0001", "credit_card_payment", "credit_cards"),
        ("PAYMENT TO VSA 0001", "credit_card_payment", "credit_cards"),
    ],
)
def test_an_unnamed_obligation_debit_takes_its_descriptor_group(description, state, group):
    record = classify_transaction(description, -400.0)
    assert record.classification == state
    assert record.flagged_group == group
    assert record.contributes_to_flagged_totals
    assert record.canonical_entity is None
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("Office rent payment", "rent"),
        ("PROPERTY RENTAL PAYMENT", "rent"),
        ("AUTO PAYMENT FABRICATED GYM", "other"),
        ("FABRICATED BANK PAYMENT 0001", "other"),
        ("FABRICATED PRET CAFE 0001", "other"),
    ],
)
def test_rent_autopay_and_a_bare_pret_are_not_flagged(description, state):
    """Landlord rent (D3), autopay wording and a bare PRET (also a restaurant's name) are no
    flagged obligation. An unnamed LOAN PAYMENT is the statement bank's loan since the owner
    decision of 2026-09-25 (D5); Task 9 pins it."""
    record = classify_transaction(description, -400.0)
    assert record.classification == state
    assert record.flagged_group is None


def test_a_transfer_between_the_holders_own_accounts_takes_no_step_8_rule():
    """Owner decision 2026-09-25: a fintech transfer to a sub-account the holder named with
    auto-loan words is no vehicle loan; an unnamed auto-loan bill payment still is."""
    moved = classify_transaction("TRANSFER TO CAR LOAN TRANSFER OUT", -400.0)
    assert (moved.classification, moved.flagged_group) == ("other", None)
    assert classify_transaction("AUTO LOAN BILL PAYMENT 0001", -400.0).classification == "vehicle_financing"


@pytest.mark.parametrize(
    ("description", "rule"),
    [
        ("PAYMENT - AUTOMATIC LOAN PMT 0001", "own_bank_loan_payment"),
        ("AUTOMATED LOAN PAYMENT 0001", "own_bank_loan_payment"),
        ("PAYMENT TO COMMERCIAL LOAN 0001", "own_bank_loan_payment"),
        ("INTEREST PAYMENT CUSTOMER 0001 OBLIGATION 0002", "commercial_loan_billing"),
        ("VERSEMENT PRET 0001", "french_loan_wording"),
        ("INT P A TERME 0001", "french_loan_wording"),
    ],
)
def test_the_statement_banks_own_loan_wording_is_its_bank_loan(description, rule):
    """Owner decisions 2026-09-25 (D5): the statement bank's own loan wording, no lender named."""
    record = classify_transaction(description, -900.0, bank="Fabricated Bank")
    assert (record.classification, record.canonical_entity, record.matched_rule) == (
        "bank_loan",
        "Fabricated Bank",
        rule,
    )
    assert record.flagged_group == "bank_loans"
    assert not record.review_required


def test_another_banks_unnamed_loan_names_no_bank():
    """Owner decision 2026-09-25 (D5): a generic savings-bank or commercial-loan originator is
    another bank's loan, so the statement bank is not named."""
    record = classify_transaction("SAVINGS BANK LOAN PMT 0001", -900.0, bank="Fabricated Bank")
    assert (record.classification, record.canonical_entity) == ("bank_loan", None)
    assert record.matched_rule == "outside_bank_loan_payment"


def test_a_review_tier_payee_with_lease_wording_is_a_lease_by_its_wording():
    """Owner decision 2026-09-25: Clover Equipment is in review, never counted. Every one of its
    aliases carries lease or rental wording, which step 8 reads before the potential tier."""
    # Moves here unchanged from the order table of tests/test_lender_insurance_classification.py.
    record = classify_transaction("Clover equipment rent/leases", -100.0)
    assert (record.classification, record.canonical_entity) == ("lease_or_rental", None)
    assert record.flagged_group == "leases_rentals"
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


@pytest.fixture
def fabricated_bank(monkeypatch):
    monkeypatch.setattr(obligations, "BANK_NAME_ALIASES", {"Fabricated Bank": ("FABRICATED BANK",)})


def test_a_listed_bank_with_loan_wording_is_a_bank_loan(fabricated_bank):
    record = classify_transaction("FABRICATED BANK LOAN PYMT 0001", -900.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == (
        "bank_loan",
        "Fabricated Bank",
        "FABRICATED BANK",
    )
    assert record.match_method == "bank_name_alias"
    assert record.flagged_group == "bank_loans"
    assert classify_transaction("FABRICATED BANK PAYMENT 0001", -900.0).classification == "other"


def test_a_listed_bank_with_french_loan_wording_is_a_bank_loan(fabricated_bank):
    """Owner decision 2026-09-25: PRET is loan wording for the bank-name rule (D5)."""
    record = classify_transaction("FABRICATED BANK PRET 0001", -900.0)
    assert (record.classification, record.canonical_entity, record.match_method) == (
        "bank_loan",
        "Fabricated Bank",
        "bank_name_alias",
    )


def test_a_transfer_to_the_statement_banks_own_loan_is_a_bank_loan():
    named = classify_transaction("TRANSFER TO LOAN 0001", -900.0, bank="Fabricated Bank")
    unnamed = classify_transaction("TRANSFER TO LOAN 0001", -900.0)
    assert (named.classification, named.canonical_entity) == ("bank_loan", "Fabricated Bank")
    assert named.matched_rule == "own_bank_loan_transfer"
    assert (unnamed.classification, unnamed.canonical_entity) == ("bank_loan", None)


def test_the_owner_truist_example_is_a_bank_loan():
    record = classify_transaction("TRUIST LN 0001 PYMT", -900.0)
    assert record.classification == "bank_loan"
    assert record.flagged_group == "bank_loans"


def test_a_listed_card_issuer_needs_payment_wording(monkeypatch):
    patched_card_issuer_context_aliases = {"Fabricated Issuer": ("FABRICATED ISSUER",)}
    monkeypatch.setattr(operating_sources, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    monkeypatch.setattr(tax_forms, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    monkeypatch.setattr(financing, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    monkeypatch.setattr(obligations, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    paid = classify_transaction("FABRICATED ISSUER EPAYMENT 0001", -300.0)
    bare = classify_transaction("FABRICATED ISSUER 0001", -300.0)
    assert (paid.classification, paid.canonical_entity, paid.matched_alias) == (
        "credit_card_payment",
        "Fabricated Issuer",
        "FABRICATED ISSUER",
    )
    assert bare.classification == "other"


@pytest.mark.parametrize("description", ["FABRICATED ISSUER PAYMNT 0001", "FABRICATED ISSUER EPAYMENTSEC CCD"])
def test_card_issuer_wording_reads_paymnt_and_a_payment_word_glued_to_its_sec_label(monkeypatch, description):
    """Owner decision 2026-09-25: Synchrony prints PAYMNT, and Chase's field layout can glue
    the payment word to its SEC label."""
    patched_card_issuer_context_aliases = {"Fabricated Issuer": ("FABRICATED ISSUER",)}
    monkeypatch.setattr(operating_sources, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    monkeypatch.setattr(tax_forms, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    monkeypatch.setattr(financing, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    monkeypatch.setattr(obligations, "CARD_ISSUER_CONTEXT_ALIASES", patched_card_issuer_context_aliases)
    record = classify_transaction(description, -300.0)
    assert (record.classification, record.canonical_entity) == ("credit_card_payment", "Fabricated Issuer")


def test_unnamed_equipment_financing_is_a_potential_lender_for_review():
    record = classify_transaction("ACH DEBIT EQUIPMENT FINANCE", -600.0)
    assert record.classification == "potential_lender"
    assert record.canonical_entity == "Unidentified lender obligation"
    assert record.match_method == "unnamed_equipment_financing"
    assert record.review_required
    assert record.contributes_to_potential_lender_totals
    assert not record.contributes_to_withholding_rate
    assert record.flagged_group is None


@pytest.mark.parametrize("description", ["LINE OF CREDIT ADVANCE", "CREDIT CARD PAYMENT RECEIVED", "LEASE DEPOSIT FABRICATED"])
def test_obligation_descriptors_never_apply_to_credits(description):
    record = classify_transaction(description, 500.0)
    assert record.classification == "other"
    assert record.flagged_group is None


@pytest.mark.parametrize("amount", [-400.0, 400.0])
@pytest.mark.parametrize(
    "description",
    [
        "LEASE PAYMENT FABRICATED",
        "EQUIPMENT RENT FABRICATED",
        "VEHICLE PAYMENT FABRICATED",
        "AUTO LEASE FABRICATED",
        "EQUIPMENT FINANCING FABRICATED",
    ],
)
def test_the_retired_lease_state_is_never_produced(description, amount):
    assert classify_transaction(description, amount).classification != "lease_or_equipment_financing"
