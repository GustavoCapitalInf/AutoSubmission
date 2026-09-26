from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.flag_groups import FINANCING_STATES
from analysis.metrics import compute_metrics
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import FAKE_PAYEES, fake_payees, txn  # noqa: F401  (fixture)

PAYEE_ROWS = [(alias, *FAKE_PAYEES[alias]) for alias in FAKE_PAYEES]


@pytest.mark.parametrize(("alias", "entity", "state"), PAYEE_ROWS)
def test_a_known_payee_credit_is_proceeds_only_for_a_financing_group(fake_payees, alias, entity, state):
    record = classify_transaction(f"{alias} DEPOSIT 0001", 5000.0)
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals
    if state in FINANCING_STATES:
        assert record.classification == "other"
        assert record.canonical_entity == entity
        assert record.match_method == "financing_proceeds_credit"
        assert record.matched_rule == "financing_proceeds_credit"
        assert record.contributes_to_lender_credit_exclusion
        assert record.revenue_classification == "non_revenue"
        assert record.revenue_match_method == "financing_proceeds_credit"
        assert record.revenue_canonical_entity == entity
    else:
        assert record.matched_rule != "financing_proceeds_credit"
        assert not record.contributes_to_lender_credit_exclusion
        assert record.revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("description", ["NEXTGEAR CAPITAL PAYMENT", "RTS FINANCIAL PAYMENT"])
def test_owner_named_floor_plan_and_factoring_credits_are_financing_proceeds(description):
    """Spec §2 amendment and §4.2: D1 covers floor-plan and factoring credits."""
    record = classify_transaction(description, 100.0)
    assert record.matched_rule == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion
    assert record.revenue_classification == "non_revenue"


def test_platform_financing_credits_are_proceeds_but_platform_sales_stay_revenue():
    statement = Statement(
        bank="Fabricated Bank",
        account_name="Business Checking",
        transactions=[
            txn("2054-01-02", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-09", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-16", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-17", "SQUARE SETTLEMENT", 800.0),
            txn("2054-01-18", "SHOPIFY CAPITAL PAYOUT", 900.0),
        ],
    )
    records = classify_statement_transactions(statement)
    assert [record.revenue_classification for record in records] == [
        "non_revenue", "non_revenue", "non_revenue", "verified_revenue", "non_revenue",
    ]
    assert {records[index].revenue_match_method for index in (0, 1, 2, 4)} == {"financing_proceeds_credit"}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_credits == 15900.0
    assert metrics.verified_revenue_total == 800.0
    assert metrics.legacy_eligible_deposits == 800.0


@pytest.fixture
def fabricated_payout_entity(monkeypatch):
    """Owner decision 2026-09-25: the credits of a PAYOUT_CREDIT_ENTITIES payee are the
    account holder's own sales, settled by the platform."""
    monkeypatch.setattr(transaction_classifier, "PAYOUT_CREDIT_ENTITIES", ("Fabricated BNPL",))


def test_a_payout_credit_entitys_credit_is_revenue_not_proceeds(fake_payees, fabricated_payout_entity):
    payout = classify_transaction("FABRICATED BNPL MERCHANT PAYOUT 0001", 900.0)
    assert payout.matched_rule != "financing_proceeds_credit"
    assert not payout.contributes_to_lender_credit_exclusion
    assert payout.revenue_classification == "verified_revenue"
    assert payout.revenue_match_method != "financing_proceeds_credit"
    # Another alternative position's credit is still proceeds.
    assert classify_transaction("FABRICATED ALT DEPOSIT 0001", 900.0).matched_rule == "financing_proceeds_credit"


@pytest.mark.parametrize(
    ("description", "classification", "entity"),
    [
        ("ONLINE TRANSFER FROM FABRICATED LENDER 0001", "transfer", "Fabricated Lender"),
        ("ONLINE TRANSFER FROM FABRICATED ALT 0001", "transfer", "Fabricated Alt Capital"),
        ("FABRICATED LINE POLICY 0001", "insurance", "Fabricated Line"),
    ],
)
def test_a_financing_group_credit_an_earlier_rule_claims_is_still_excluded(
    fake_payees, description, classification, entity
):
    """Contract C4, spec §4.4: a financing group's credit is non_revenue proceeds AND is excluded
    from eligible deposits, even when an earlier rule (a transfer, an insurance term) names the row."""
    statement = Statement(
        bank="Fabricated Bank",
        transactions=[
            txn("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 800.0),
            txn("2054-01-03", description, 5000.0),
        ],
    )
    records = classify_statement_transactions(statement)
    record = records[1]
    assert record.classification == classification
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.revenue_canonical_entity == entity
    assert record.contributes_to_lender_credit_exclusion
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_credits == 5000.0
    assert metrics.legacy_eligible_deposits == 800.0


def test_a_payout_entitys_transfer_worded_credit_stays_in_eligible_deposits(fake_payees, fabricated_payout_entity):
    record = classify_transaction("ONLINE TRANSFER FROM FABRICATED BNPL 0001", 900.0)
    assert record.classification == "transfer"
    assert record.revenue_match_method != "financing_proceeds_credit"
    assert not record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize(
    ("description", "rule", "entity"),
    [
        ("LOAN CREDIT", "bank_line_advance_credit", "Fabricated Bank"),
        ("LOC ADVANCE 0001", "loc_draw_credit", "Fabricated Bank"),
        ("ADVANCE FROM LINE OF CREDIT 0001", "loc_draw_credit", "Fabricated Bank"),
        ("ADVANCE 2054 FABRICATED MODEL VIN 0001", "floor_plan_advance_credit", None),
    ],
)
def test_a_credit_whose_words_say_financing_proceeds_is_proceeds(description, rule, entity):
    """Owner decisions 2026-09-25: the bank's own line advance, a line-of-credit draw and a
    per-vehicle floor-plan advance are financing proceeds (D1), with no flag."""
    record = classify_transaction(description, 900.0, bank="Fabricated Bank")
    assert record.classification == "other"
    assert (record.match_method, record.matched_rule, record.canonical_entity) == (
        "financing_proceeds_credit",
        rule,
        entity,
    )
    assert record.contributes_to_lender_credit_exclusion
    assert record.flagged_group is None
    assert record.revenue_classification == "non_revenue"
    assert (record.revenue_match_method, record.revenue_matched_rule) == ("financing_proceeds_credit", rule)
    assert record.revenue_canonical_entity == entity


def test_only_the_exact_bank_line_posting_is_proceeds_by_its_words():
    record = classify_transaction("LOAN CREDIT MEMO 0001", 900.0, bank="Fabricated Bank")
    assert record.revenue_match_method == "strong_non_revenue_rule"
    assert not record.contributes_to_lender_credit_exclusion
