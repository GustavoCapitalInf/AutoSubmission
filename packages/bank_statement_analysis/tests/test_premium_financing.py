from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction
from tests.flag_group_fixtures import fake_premium_finance, txn  # noqa: F401  (fixture)


def test_a_premium_finance_debit_stays_insurance_and_is_flagged(fake_premium_finance):
    record = classify_transaction("ACH DEBIT FABRICATED PFC 0001", -300.0)
    assert record.classification == "insurance"
    assert (record.canonical_entity, record.matched_alias) == ("Fabricated Premium Finance", "FABRICATED PFC")
    assert record.matched_rule == "premium_finance_provider"
    assert record.flagged_group == "premium_financing"
    assert record.contributes_to_flagged_totals
    assert record.contributes_to_insurance_totals
    assert not record.contributes_to_lender_count
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


def test_a_premium_financier_wins_over_a_shorter_insurer_alias(fake_premium_finance):
    record = classify_transaction("FABRICATED INSURER FUNDING PMT", -300.0)
    assert (record.classification, record.canonical_entity) == ("insurance", "Fabricated Insurer Funding")
    assert record.flagged_group == "premium_financing"


def test_an_ordinary_insurer_carries_no_flag(fake_premium_finance):
    record = classify_transaction("FABRICATED INSURER PMT", -300.0)
    assert (record.classification, record.canonical_entity) == ("insurance", "Fabricated Insurer")
    assert record.matched_rule == "verified_insurance_provider"
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
    assert record.contributes_to_insurance_totals


def test_a_premium_finance_credit_keeps_the_insurance_credit_treatment(fake_premium_finance):
    record = classify_transaction("FABRICATED PFC 0001", 300.0)
    assert record.classification == "insurance"
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "insurance_provider_credit_exclusion"
    assert record.revenue_canonical_entity == "Fabricated Premium Finance"
    assert not record.contributes_to_lender_credit_exclusion


def test_a_proven_duplicate_premium_finance_debit_leaves_the_flagged_totals(fake_premium_finance):
    statement = Statement(
        transactions=[
            txn("2054-01-02", "ACH DEBIT FABRICATED PFC", -300.0, balance=700.0),
            txn("2054-01-02", "ACH DEBIT FABRICATED PFC", -300.0, balance=700.0),
        ]
    )
    first, duplicate = classify_statement_transactions(statement)
    assert first.contributes_to_flagged_totals
    assert duplicate.flagged_group == "premium_financing"
    assert not duplicate.contributes_to_flagged_totals
    assert not duplicate.contributes_to_insurance_totals


@pytest.mark.parametrize(
    "description",
    # The last is fabricated: the bare ACH company name FIRST INSURANCE is FIRST Insurance
    # Funding (owner decision 2026-09-25).
    ["IPFS CORP PMT", "FIRST INSURANCE FUNDING PMT", "FIRST INSURANCE DES INSURANCE"],
)
def test_owner_named_premium_financiers_are_insurance_and_flagged(description):
    record = classify_transaction(description, -300.0)
    assert record.classification == "insurance"
    assert record.flagged_group == "premium_financing"
    assert record.contributes_to_insurance_totals


def test_the_bare_first_insurance_originator_is_first_insurance_funding():
    record = classify_transaction("FIRST INSURANCE DES INSURANCE", -300.0)
    assert (record.canonical_entity, record.matched_alias) == ("FIRST Insurance Funding", "FIRST INSURANCE")
    assert record.matched_rule == "premium_finance_provider"
    assert record.contributes_to_flagged_totals


@pytest.mark.parametrize(
    ("description", "entity", "alias", "method"),
    [
        ("FABRICATED INSURER PREMIUM FINANCE 0001", "Fabricated Insurer", "FABRICATED INSURER", "insurance_provider_alias"),
        ("ACH DEBIT PREM FIN 0001", "Insurance provider not identified", None, "insurance_descriptor"),
        ("INSPREMFIN 0001", "Insurance provider not identified", None, "insurance_descriptor"),
    ],
)
def test_premium_finance_wording_is_premium_financing_under_the_insurer_it_names(
    fake_premium_finance, description, entity, alias, method
):
    """Owner decision 2026-09-25: premium-finance wording with no premium-finance payee named."""
    record = classify_transaction(description, -300.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == ("insurance", entity, alias)
    assert (record.match_method, record.matched_rule) == (method, "premium_finance_descriptor")
    assert record.flagged_group == "premium_financing"
    assert record.contributes_to_flagged_totals
    assert record.contributes_to_insurance_totals


def test_a_premium_finance_wording_credit_carries_no_flag(fake_premium_finance):
    record = classify_transaction("PREM FIN 0001", 300.0)
    assert record.classification == "insurance"
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
