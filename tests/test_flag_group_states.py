from __future__ import annotations

from typing import get_args

import pytest

from analysis.flag_groups import FLAG_GROUPS
from analysis.schema import Statement
from analysis.transaction_classifier import (
    CLASSIFICATION_STATES,
    CLASSIFICATION_VERSION,
    ClassificationState,
    _build_record,
    classify_statement_transactions,
    classify_transaction,
)
from tests.flag_group_fixtures import txn
from webapp.artifact_cache import ANALYSIS_STAGE_VERSION

#: The flag groups that are classification states. Premium financing is the one
#: group without a state: its rows stay insurance and a rule sets the flag (C1).
STATE_GROUPS = [group for group in FLAG_GROUPS if group.state is not None]


def _record(state: str, amount: float, *, posted: bool = True):
    return _build_record(
        description="FABRICATED ROW",
        text="FABRICATED ROW",
        classification=state,
        amount=amount,
        date_value="2054-01-05",
        bank=None,
        account=None,
        account_name=None,
        source_direction="debit" if amount < 0 else "credit",
        direction_consistent=True,
        source_page=None,
        source_location="transaction:1",
        match_method="test",
        confidence_score=0.9,
        reason="Fabricated test row.",
        is_posted=posted,
    )


def test_the_state_list_carries_every_flag_group_and_the_retired_lease_state():
    assert get_args(ClassificationState) == CLASSIFICATION_STATES
    assert len(set(CLASSIFICATION_STATES)) == len(CLASSIFICATION_STATES)
    for group in STATE_GROUPS:
        assert group.state in CLASSIFICATION_STATES
    assert [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"]
    # Retired in 5.0 but kept, so records stored before 5.0 still validate.
    assert "lease_or_equipment_financing" in CLASSIFICATION_STATES


def test_the_classification_and_analysis_stage_versions_move_together():
    # Re-pinned 5.0/19 -> 5.1/20: the D6 clarification (2026-09-26) changes the stored rows. Re-pinned 5.1/20 ->
    # 5.2/21: the second D6 clarification (2026-09-27, compensation memos and masked recipient accounts) does too.
    # 5.3/22: the false-positive release (2026-09-27): D6 skips, rule extensions, routing, naming, Debt relief.
    # 5.4/23: the owner ruling of 2026-09-28: Idea Financial is a counted lender, no longer a line of credit.
    assert CLASSIFICATION_VERSION == "5.4"
    assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.4"
    assert ANALYSIS_STAGE_VERSION == 23


@pytest.mark.parametrize("group", STATE_GROUPS, ids=lambda group: group.state)
def test_a_posted_flag_group_debit_contributes_to_flagged_totals_only(group):
    record = _record(group.state, -100.0)
    assert record.flagged_group == group.key
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_lender_count
    assert not record.contributes_to_lender_totals
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals
    assert not record.contributes_to_potential_withholding_exposure
    assert not record.contributes_to_insurance_totals


@pytest.mark.parametrize("group", STATE_GROUPS, ids=lambda group: group.state)
def test_only_a_factoring_credit_contributes_and_an_unposted_row_never_does(group):
    """Owner ruling 2026-09-26: a factor's payout counts in the Factoring totals as a credit. No other group's
    credit counts, and an unposted row of any group never does."""
    credit = _record(group.state, 100.0)
    unposted = _record(group.state, -100.0, posted=False)
    unposted_credit = _record(group.state, 100.0, posted=False)
    assert credit.flagged_group == unposted.flagged_group == group.key
    assert credit.contributes_to_flagged_totals is (group.state == "factoring")
    assert not unposted.contributes_to_flagged_totals
    assert not unposted_credit.contributes_to_flagged_totals


@pytest.mark.parametrize(
    "state",
    ["confirmed_lender", "potential_lender", "insurance", "lease_or_equipment_financing", "rent", "other"],
)
def test_a_state_outside_the_flag_groups_carries_no_flag(state):
    record = _record(state, -100.0)
    assert record.flagged_group is None
    assert not record.contributes_to_flagged_totals


def test_a_proven_duplicate_flagged_debit_leaves_the_flagged_totals():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
        ]
    )
    first, duplicate = classify_statement_transactions(statement)
    assert first.flagged_group == duplicate.flagged_group == "credit_cards"
    assert first.contributes_to_flagged_totals
    assert duplicate.duplicate_of == "transaction:1"
    assert not duplicate.contributes_to_flagged_totals


def test_a_settlement_reversed_flagged_debit_leaves_the_flagged_totals():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "ACH CREDIT CARD PAYMENT FABRICATED", -250.0),
            txn("2054-01-04", "RETURNED ACH CREDIT CARD PAYMENT FABRICATED", 250.0),
        ]
    )
    debit, credit = classify_statement_transactions(statement)
    assert debit.flagged_group == "credit_cards"
    assert credit.settlement_reversal
    assert debit.reversed_by == "transaction:2"
    assert not debit.contributes_to_flagged_totals
