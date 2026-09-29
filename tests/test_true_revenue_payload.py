"""Classification 5.6 (true revenue spec §5.1, §5.4, §9.1, §10.7 server rules, §11, §12, T6 to T10): the contribution
flags, the metrics, the detection lists, the serialized views and their rebuild, the review writer, the gate and the
True-revenue withholding mode. Fabricated rows only."""
from __future__ import annotations

from analysis.revenue import REVENUE_TIER_REASONS, revenue_contribution_flags, tier_of_state
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction


def test_the_flags_follow_the_state_and_the_tier():
    assert revenue_contribution_flags("verified_revenue", "verified")["contributes_to_true_revenue"]
    counted = revenue_contribution_flags("unverified_deposit", "counted_flagged")
    assert counted["contributes_to_true_revenue"] and counted["contributes_to_counted_flagged"]
    assert counted["contributes_to_unverified_deposit"] and counted["contributes_to_potential_revenue"]
    held = revenue_contribution_flags("unverified_deposit", "excluded_pending_review")
    assert not held["contributes_to_true_revenue"] and held["contributes_to_excluded_pending_review"]
    assert not revenue_contribution_flags("non_revenue", "non_revenue")["contributes_to_true_revenue"]
    assert not revenue_contribution_flags("verified_revenue", None)["contributes_to_true_revenue"]


def test_every_reason_code_names_a_middle_tier():
    assert {tier for tier, _label in REVENUE_TIER_REASONS.values()} == {"counted_flagged", "excluded_pending_review"}
    assert len(REVENUE_TIER_REASONS) == 26


def test_a_record_carries_the_tier_its_state_fixes():
    assert (tier_of_state("verified_revenue"), tier_of_state("non_revenue"), tier_of_state("unverified_deposit")) == (
        "verified", "non_revenue", None)
    verified = classify_transaction("FABRIKAM MERCH DEP 1234567", 250.0, direction="credit")
    assert (verified.revenue_tier, verified.revenue_initial_tier, verified.revenue_tier_reason) == (
        "verified", "verified", None)
    assert verified.contributes_to_true_revenue
    transfer = classify_transaction("INTERNAL TRANSFER FROM SAVINGS", 100.0, direction="credit")
    assert transfer.revenue_tier == "non_revenue" and not transfer.contributes_to_true_revenue
    assert classify_transaction("CARD PURCHASE FABRIKAM SUPPLY", -120.0, direction="debit").revenue_tier is None


def test_a_proven_duplicate_credit_is_tiered_non_revenue():
    records = classify_statement_transactions(Statement(account_name="CONTOSO BAKERY LLC", transactions=[
        Transaction(date="2054-03-02", description="FABRIKAM MERCH DEP 1234567", amount=250.0, direction="credit",
                    running_balance=1250.0),
        Transaction(date="2054-03-02", description="FABRIKAM MERCH DEP 1234567", amount=250.0, direction="credit",
                    running_balance=1250.0),
    ]))
    assert [record.revenue_tier for record in records] == ["verified", "non_revenue"]
    assert not records[1].contributes_to_true_revenue
