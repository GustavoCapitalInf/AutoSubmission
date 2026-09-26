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


EXPECTED_POSITIONS = [
    {
        "group": "alternative_positions", "payee": "Fabricated Alt Capital", "matched_alias": "FABRICATED ALT",
        "count": 2, "total_debited": 1400.0, "cadence": "weekly", "avg_gap_days": 7.0,
        "first_date": "2054-01-06", "last_date": "2054-01-13",
        "source_locations": ["transaction:2", "transaction:3"],
    },
    {
        "group": "alternative_positions", "payee": "Fabricated BNPL", "matched_alias": "FABRICATED BNPL",
        "count": 1, "total_debited": 900.0, "cadence": "single", "avg_gap_days": None,
        "first_date": "2054-01-08", "last_date": "2054-01-08",
        "source_locations": ["transaction:4"],
    },
    {
        "group": "credit_cards", "payee": "Credit cards", "matched_alias": None,
        "count": 2, "total_debited": 800.0, "cadence": "irregular", "avg_gap_days": 10.0,
        "first_date": "2054-01-10", "last_date": "2054-01-20",
        "source_locations": ["transaction:7", "transaction:8"],
    },
    {
        "group": "mortgages", "payee": "Mortgages", "matched_alias": None,
        "count": 2, "total_debited": 2400.0, "cadence": "monthly", "avg_gap_days": 31.0,
        "first_date": "2054-01-05", "last_date": "2054-02-05",
        "source_locations": ["transaction:5", "transaction:6"],
    },
    {
        "group": "leases_rentals", "payee": "Leases & rentals", "matched_alias": None,
        "count": 1, "total_debited": 200.0, "cadence": "single", "avg_gap_days": None,
        "first_date": "2054-01-12", "last_date": "2054-01-12",
        "source_locations": ["transaction:9"],
    },
]


def test_detection_groups_flagged_rows_by_group_then_total(fake_payees):
    from analysis.detect import find_flagged_positions
    from analysis.transaction_classifier import classify_statement_transactions

    statement = flagged_statement()
    positions = find_flagged_positions(statement, classify_statement_transactions(statement))
    assert [(position.group, position.payee) for position in positions] == [
        (entry["group"], entry["payee"]) for entry in EXPECTED_POSITIONS
    ]


def test_the_payload_publishes_flagged_positions_and_the_row_fields(fake_payees):
    from analysis.serialization import report_to_dict
    from tests.flag_group_fixtures import flagged_report

    payload = report_to_dict(flagged_report())
    assert payload["detection"]["flagged_positions"] == EXPECTED_POSITIONS
    assert payload["metrics"]["flagged_groups"] == FLAGGED_GROUPS_EXPECTED
    for transaction in payload["statement"]["transactions"]:
        assert "flagged_group" in transaction["classification"]
        assert "contributes_to_flagged_totals" in transaction["classification"]
    assert payload["metrics"]["lender_debits"] == 1000.0


def test_a_detection_result_without_flagged_rows_publishes_an_empty_list():
    from analysis.detect import DetectionResult

    assert DetectionResult().flagged_positions == []


def test_a_premium_financier_is_a_flagged_position_under_its_own_name(fake_premium_finance):
    from analysis.detect import find_flagged_positions
    from analysis.transaction_classifier import classify_statement_transactions

    statement = flagged_statement(PREMIUM_ROWS)
    [position] = find_flagged_positions(statement, classify_statement_transactions(statement))
    assert (position.group, position.payee, position.matched_alias) == (
        "premium_financing",
        "Fabricated Premium Finance",
        "FABRICATED PFC",
    )
    assert (position.count, position.total_debited, position.cadence) == (2, 600.0, "monthly")
    assert position.source_locations == ["transaction:1", "transaction:2"]


def test_the_batch_row_lists_flagged_positions_as_group_and_payee(fake_payees):
    from pathlib import Path

    import batch
    from tests.flag_group_fixtures import flagged_report

    row = batch._row(Path("fabricated.pdf"), flagged_report())
    assert "flagged_positions" in batch.FIELDS
    assert row["flagged_positions"] == (
        "alternative_positions:Fabricated Alt Capital; alternative_positions:Fabricated BNPL; "
        "credit_cards:Credit cards; mortgages:Mortgages; leases_rentals:Leases & rentals"
    )
    assert row["mca_funders"] == "Fabricated Lender"


def test_the_text_report_prints_a_flagged_positions_block(fake_payees):
    from analyze import _render
    from tests.flag_group_fixtures import flagged_report

    rendered = _render(flagged_report())
    assert "## Flagged positions (not lenders; outside lender math)" in rendered
    assert "  - Alternative positions: Fabricated Alt Capital: 2 debit(s), $1,400.00 (weekly)" in rendered
    assert "  - Mortgages: Mortgages: 2 debit(s), $2,400.00 (monthly)" in rendered


def test_the_text_report_says_none_without_flagged_rows():
    from analyze import _render
    from analysis.detect import detect
    from analysis.metrics import compute_metrics
    from analysis.pipeline import DocumentIntegrity, Quality, Report
    from analysis.reconcile import reconcile

    statement = Statement(transactions=[txn("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 500.0)])
    report = Report(
        statement=statement,
        reconciliation=reconcile(statement),
        metrics=compute_metrics(statement),
        detection=detect(statement),
        quality=Quality(level="transaction_level", transaction_detail_reliable=True, summary_totals_reliable=True),
        integrity=DocumentIntegrity(risk_level="clear", flags=[], notes=[]),
        model_used="fabricated-test",
        escalated=False,
    )
    assert "  Flagged positions: none" in _render(report)
