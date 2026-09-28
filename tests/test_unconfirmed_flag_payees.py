"""5.3 (owner ruling 2026-09-27): a review entity of a flag group takes its flag on debits, marked unconfirmed, and
keeps the potential tier's credit exclusion. Fabricated descriptors; the payee names are the registry's business
names, or fabricated ones through a patched registry."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.classification_registry import POTENTIAL_LENDER_ALIASES, REVIEW_FLAG_ENTITIES
from analysis.detect import find_flagged_positions
from analysis.flag_groups import FLAG_GROUP_BY_STATE
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import fake_payees, txn  # noqa: F401  (fixture)

#: Fabricated review entities, one per routed group, and one whose business type the ledger does not know.
FABRICATED_REVIEW = {
    "FABRIKAM AUTO CR (probable)": ("FABRIKAM AUTO CR",),
    "FABRIKAM HOME SERVICER (unconfirmed)": ("FABRIKAM HOME SVCR",),
    "FABRIKAM TOOLHIRE (probable)": ("FABRIKAM TOOLHIRE",),
    "FABRIKAM CONSUMER LOANS (probable)": ("FABRIKAM CONS LN",),
    "FABRIKAM UNKNOWN PAD (unidentified)": ("FABRIKAM UNK PAD",),
}
FABRICATED_ROUTES = {
    "FABRIKAM AUTO CR (probable)": "vehicle_financing",
    "FABRIKAM HOME SERVICER (unconfirmed)": "mortgage",
    "FABRIKAM TOOLHIRE (probable)": "lease_or_rental",
    "FABRIKAM CONSUMER LOANS (probable)": "personal_loan",
}


@pytest.fixture
def review_payees(monkeypatch):
    monkeypatch.setattr(transaction_classifier, "POTENTIAL_LENDER_ALIASES", FABRICATED_REVIEW)
    monkeypatch.setattr(transaction_classifier, "REVIEW_FLAG_ENTITIES", FABRICATED_ROUTES)


@pytest.mark.parametrize(("entity", "state"), sorted(FABRICATED_ROUTES.items()))
def test_a_review_payee_of_a_flag_group_takes_its_flag_marked_unconfirmed(review_payees, entity, state):
    alias = FABRICATED_REVIEW[entity][0]
    record = classify_transaction(f"ACH DEBIT {alias} 0001", -400.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == (state, entity, alias)
    assert (record.match_method, record.matched_rule) == ("unconfirmed_flag_payee_alias", f"{state}_review_registry")
    assert record.review_required and record.confidence_score == 0.82
    assert record.flagged_group == FLAG_GROUP_BY_STATE[state].key and record.contributes_to_flagged_totals
    assert not record.contributes_to_potential_lender_totals and not record.contributes_to_lender_totals


@pytest.mark.parametrize("entity", sorted(FABRICATED_REVIEW))
def test_a_review_payees_credit_keeps_the_potential_tiers_exclusion(review_payees, entity):
    record = classify_transaction(f"{FABRICATED_REVIEW[entity][0]} DEPOSIT 0001", 900.0)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "non_revenue", "potential_lender_registry_credit_exclusion")
    assert record.flagged_group is None and not record.contributes_to_lender_credit_exclusion


def test_a_review_payee_the_ledger_does_not_route_stays_a_potential_lender(review_payees):
    record = classify_transaction("ACH DEBIT FABRIKAM UNK PAD 0001", -400.0)
    assert (record.classification, record.match_method) == ("potential_lender", "candidate_lender_alias")


def test_every_routed_entity_is_a_potential_table_entity():
    assert REVIEW_FLAG_ENTITIES and set(REVIEW_FLAG_ENTITIES) <= set(POTENTIAL_LENDER_ALIASES)
    assert set(REVIEW_FLAG_ENTITIES.values()) <= {
        "vehicle_financing", "mortgage", "lease_or_rental", "personal_loan", "debt_relief"}


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("Misc Payment National Money", "personal_loan"),
        ("iA Auto CAB 0001", "vehicle_financing"),
        ("Hillcrest Acceptance Card spend", "vehicle_financing"),
        ("UAS DES:EPAYMENT ID:0001 INDN:FAB HOLDER CO ID:0002 PPD", "personal_loan"),
        ("WESTLAKE PAYMENT, LOS ANGELES, CA", "vehicle_financing"),
        # Kept in the potential tier on purpose (the verifiers' changes): a counted reading exists.
        ("Orig CO Name:Westlake Orig ID:0001 Desc Date: CO Entry Descr:Payment Sec:CCD", "potential_lender"),
        ("TABLE ROCK INVST DES:PAYMENT ID:0001 PPD", "potential_lender"),
        ("Fleetlogic Cons Coll 0001", "potential_lender"),
        # A business type read from a payment code alone is never routed.
        ("Pre-Authorized Payment, WOW FACTOR RLS/LOY", "potential_lender"),
    ],
)
def test_the_registrys_review_payees_in_their_printed_forms(description, state):
    assert classify_transaction(description, -300.0).classification == state


def test_a_flagged_position_of_a_routed_payee_is_marked_unconfirmed(review_payees, fake_payees):
    statement = Statement(bank="Fabricated Bank", transactions=[
        txn("2054-01-05", "ACH DEBIT FABRIKAM AUTO CR 0001", -400.0),
        txn("2054-01-12", "ACH DEBIT FABRIKAM AUTO CR 0001", -400.0),
        txn("2054-01-06", "ACH DEBIT FABRICATED CARMAKER FINANCIAL 0001", -500.0),
    ])
    positions = find_flagged_positions(statement, classify_statement_transactions(statement))
    assert [(position.payee, position.review_required) for position in positions] == [
        ("FABRIKAM AUTO CR (probable)", True), ("Fabricated Carmaker Financial", False)]
