from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions
from tests.flag_group_fixtures import txn

UNIDENTIFIED = "Unidentified lender obligation"


def _statement(rows) -> Statement:
    return Statement(transactions=[txn(day, description, amount) for day, description, amount in rows])


def test_fixed_weekly_debits_of_an_unknown_payee_become_a_potential_lender():
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", f"ACH DEBIT FABRICATED WIDGETS LLC {day:04d}", -400.0) for day in (2, 9, 16, 23)]
    ))
    assert {record.classification for record in records} == {"potential_lender"}
    assert {record.match_method for record in records} == {"recurring_fixed_debit"}
    # classify_cadence (unchanged) renders an integral mean gap without a decimal.
    assert {record.matched_rule for record in records} == {"weekly_fixed_debit_7_day_average"}
    assert {record.canonical_entity for record in records} == {"Fabricated Widgets LLC"}
    assert all(record.review_required for record in records)
    assert all(
        record.contributes_to_potential_lender_totals and record.contributes_to_potential_withholding_exposure
        for record in records
    )
    assert not any(record.contributes_to_withholding_rate for record in records)


def test_fixed_daily_debits_without_an_organisation_name_stay_unidentified():
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", "ACH DEBIT PAT EXAMPLE", -150.0) for day in (5, 6, 7, 8, 9)]
    ))
    assert {(record.classification, record.canonical_entity) for record in records} == {
        ("potential_lender", UNIDENTIFIED)
    }


NOT_PROMOTED = {
    "two rows": [
        ("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0),
        ("2054-01-09", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0),
    ],
    "monthly": [(day, "ACH DEBIT FABRICATED WIDGETS LLC", -400.0) for day in ("2054-01-05", "2054-02-05", "2054-03-05")],
    "different amounts": [
        (f"2054-01-{day:02d}", "ACH DEBIT FABRICATED WIDGETS LLC", amount)
        for day, amount in ((2, -100.0), (9, -110.0), (16, -120.0))
    ],
    "transfer wording": [(f"2054-01-{day:02d}", "TRANSFER TO PAT EXAMPLE", -300.0) for day in (2, 9, 16)],
    "channel words only": [(f"2054-01-{day:02d}", f"AB{day:02d} TFR TO 0000000", -300.0) for day in (2, 9, 16)],
    "no payee words": [(f"2054-01-{day:02d}", f"ACH DEBIT {day:04d}", -300.0) for day in (2, 9, 16)],
    "credits": [(f"2054-01-{day:02d}", "FABRICATED WIDGETS LLC", 400.0) for day in (2, 9, 16)],
}


@pytest.mark.parametrize("rows", list(NOT_PROMOTED.values()), ids=list(NOT_PROMOTED))
def test_recurrence_without_a_fixed_daily_or_weekly_unknown_payee_is_not_promoted(rows):
    records = classify_statement_transactions(_statement(rows))
    assert not any(record.classification == "potential_lender" for record in records)


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("CARD PURCHASE FABRICATED STORE", "pos"),
        ("ONLINE TRANSFER TO SAVINGS", "transfer"),
        ("MONTHLY SERVICE FEE", "fee"),
        ("ADP PAYROLL FABRICATED", "payroll"),
        ("IRS TAX PAYMENT FABRICATED", "tax"),
        ("ELECTRIC UTILITY FABRICATED", "utility"),
        ("RENT FABRICATED LANDLORD", "rent"),
        ("FABRICATED INSURANCE PREMIUM", "insurance"),
        ("CHECK FABRICATED CLEANING", "other"),
    ],
)
def test_recurring_rows_a_rule_already_claimed_are_never_promoted(description, state):
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", description, -300.0) for day in (2, 9, 16, 23)]
    ))
    assert {record.classification for record in records} == {state}


def test_proven_duplicates_do_not_make_a_recurring_group():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=600.0),
            txn("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=600.0),
            txn("2054-01-09", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=200.0),
        ]
    )
    records = classify_statement_transactions(statement)
    assert not any(record.classification == "potential_lender" for record in records)


def test_financing_keyword_rows_of_two_unnamed_payees_are_not_merged():
    records = classify_statement_transactions(_statement([
        ("2054-01-02", "ADVANCE PAT EXAMPLE PMT", -200.0),
        ("2054-01-09", "ADVANCE LEE SAMPLE PMT", -200.0),
        ("2054-01-16", "ADVANCE PAT EXAMPLE PMT", -200.0),
        ("2054-01-23", "ADVANCE LEE SAMPLE PMT", -200.0),
    ]))
    assert {record.match_method for record in records} == {"financing_keyword_review"}


def test_fixed_debits_join_the_recurring_debit_view():
    """The CLI's "Recurring fixed debits" lines and batch.py's recurring_debit_groups
    read detect.find_recurring_debits, so the D6 rows must reach it."""
    from analysis.detect import find_recurring_debits

    statement = _statement(
        [(f"2054-01-{day:02d}", f"ACH DEBIT FABRICATED WIDGETS LLC {day:04d}", -400.0) for day in (2, 9, 16, 23)]
    )
    [recurring] = find_recurring_debits(statement)
    assert (recurring.description_key, recurring.amount, recurring.count, recurring.cadence) == (
        "Fabricated Widgets LLC",
        400.0,
        4,
        "weekly",
    )
