from __future__ import annotations

import pytest

from analysis.metrics import compute_metrics
from analysis.schema import Statement
from tests.flag_group_fixtures import (  # noqa: F401  (fake_payees and fake_premium_finance are fixtures)
    FLAGGED_GROUPS_EXPECTED,
    FLAGGED_ROWS,
    fake_payees,
    fake_premium_finance,
    flagged_statement,
    txn,
)

#: Two premium-finance debits and one ordinary insurance debit (fake_premium_finance).
PREMIUM_ROWS: tuple[tuple[str, str, float], ...] = (
    ("2054-01-05", "ACH DEBIT FABRICATED PFC", -300.0),
    ("2054-02-05", "ACH DEBIT FABRICATED PFC", -300.0),
    ("2054-01-09", "FABRICATED INSURER PMT", -100.0),
)


def test_metrics_sum_flagged_rows_per_group_in_flag_group_order(fake_payees):
    metrics = compute_metrics(flagged_statement())
    assert metrics.flagged_groups == FLAGGED_GROUPS_EXPECTED
    assert list(metrics.flagged_groups) == list(FLAGGED_GROUPS_EXPECTED)


def test_flagged_groups_never_move_lender_withholding_or_eligible_deposits(fake_payees):
    lender_and_deposit = tuple(row for row in FLAGGED_ROWS if "FABRICATED LENDER" in row[1] or row[2] > 0)
    without = compute_metrics(flagged_statement(lender_and_deposit))
    with_flagged = compute_metrics(flagged_statement())
    assert without.flagged_groups == {}
    for name in (
        "lender_debits", "lender_debit_count", "lenders_detected", "lender_credits",
        "eligible_deposits", "legacy_eligible_deposits", "withholding_numerator",
        "withholding_denominator", "withholding_rate", "potential_lender_debit_total",
        "potential_lender_debit_count", "potential_withholding_exposure",
    ):
        assert getattr(with_flagged, name) == getattr(without, name), name
    assert with_flagged.withholding_rate == pytest.approx(10.0)


def test_a_proven_duplicate_flagged_row_is_counted_once():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
            txn("2054-01-02", "CREDIT CARD PAYMENT FABRICATED", -250.0, balance=750.0),
        ]
    )
    assert compute_metrics(statement).flagged_groups == {
        "credit_cards": {"count": 1, "total": 250.0, "payees": 1}
    }


def test_premium_financing_counts_as_insurance_and_as_its_flagged_group(fake_premium_finance):
    metrics = compute_metrics(flagged_statement(PREMIUM_ROWS))
    assert (metrics.insurance_count, metrics.insurance_total) == (3, 700.0)
    assert metrics.flagged_groups == {"premium_financing": {"count": 2, "total": 600.0, "payees": 1}}
