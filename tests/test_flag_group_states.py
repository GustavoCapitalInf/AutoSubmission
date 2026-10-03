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
    # 5.5/24: the true-revenue bug fixes (2026-09-28 design, §7). 5.6/25: its definitional rules (§8).
    # 5.6/26: the audit's holder-identity batch (B9) changes two parsers and the payload's statement shape (the
    # holder's name as its own field); the classification version stays 5.6 on the true-revenue branch.
    # 5.6/27: the audit's lost-payer-text batch (B10) changes six parsers' credit descriptions.
    # 5.6/28: the audit's package and review-gate batch (B11) changes the stored revenue gate (T7) and adds the
    # four-tier identity's own name to the metrics.
    # 5.6/29: audit round 2's holder batch (R2-B04) changes the stored holder_unscreened metric and the holder holds.
    # 5.6/30: audit round 2's holder-reader batch (R2-B05) has fourteen more parsers publish the holder's name.
    # 5.6/31: audit round 2's Navy Federal batch (R2-B06) reads a retail product's amount-first rows as printed.
    assert CLASSIFICATION_VERSION == "5.6"
    assert classify_transaction("FABRICATED ROW", -10.0).classification_version == "5.6"
    assert ANALYSIS_STAGE_VERSION == 31


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


@pytest.mark.parametrize(("debit_text", "credit_text"), [
    ("NORTHWIND LOAN PAYMENT ACH DEBIT", "RETURN NORTHWIND LOAN ACH RTN R01"),
    ("SAMPLE LOAN PYMT ACH", "SAMPLE LOAN PYMT RETURN ACH REJT"),
    ("VIREMENT SAMPLE LOAN PAIEMENT", "VIREMENT SAMPLE LOAN PAIEMENT ANNULE"),
])
def test_a_widened_marker_pair_never_moves_the_debit_s_lender_reading(debit_text, credit_text):
    # Final review I6 (true revenue spec §20): the widened reversal-pair markers (the return codes, ANNULE) change the
    # credit's revenue reading only. The debit keeps classification 5.4's lender, potential-lender and withholding
    # contributions, and no reversed_by, as when no credit prints a 5.4 marker.
    statement = Statement(transactions=[txn("2054-01-02", debit_text, -500.0), txn("2054-01-03", credit_text, 500.0)])
    debit, credit = classify_statement_transactions(statement)
    [alone] = classify_statement_transactions(Statement(transactions=[txn("2054-01-02", debit_text, -500.0)]))
    assert credit.revenue_classification == "non_revenue"
    assert debit.reversed_by is None and not credit.settlement_reversal
    for field in ("classification", "contributes_to_lender_count", "contributes_to_lender_totals",
                  "contributes_to_potential_lender_count", "contributes_to_potential_lender_totals",
                  "contributes_to_withholding_rate", "contributes_to_potential_withholding_exposure",
                  "contributes_to_flagged_totals"):
        assert getattr(debit, field) == getattr(alone, field), field


def test_a_5_4_marker_pair_still_zeroes_the_debit_s_lender_reading():
    statement = Statement(transactions=[txn("2054-01-02", "NORTHWIND LOAN PAYMENT ACH DEBIT", -500.0),
                                        txn("2054-01-03", "RETURNED PAYMENT NORTHWIND LOAN ACH", 500.0)])
    debit, credit = classify_statement_transactions(statement)
    assert credit.revenue_match_method == "matched_reversal_pair" and credit.settlement_reversal
    assert debit.reversed_by == "transaction:2"
    assert not debit.contributes_to_potential_lender_totals and not debit.contributes_to_withholding_rate
