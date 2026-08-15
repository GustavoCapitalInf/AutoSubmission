"""The ratified ADB doctrine, pinned.

One statement yields ONE user-facing Average Daily Balance, and it is always
the canonical calendar-day underwriting figure over the printed period. The
alternates, the bank-reported comparison and the deprecated aliases all exist
so that fact can be audited without being negotiable.
"""
from __future__ import annotations

from datetime import date

import pytest

from analysis.adb import (
    UNDERWRITING_ADB_ALTERNATE_BASES,
    UNDERWRITING_ADB_BASIS,
    UNDERWRITING_ADB_POLICY,
    AverageDailyBalanceResult,
    _federal_bank_holidays,
    compute_average_daily_balance,
)
from analysis.metrics import (
    BANK_REPORTED_AVERAGE_HYPOTHESES,
    compute_metrics,
)
from analysis.schema import Statement, Transaction
from analysis.serialization import _metrics_dict


def _statement(rows, *, start, end, opening, closing, average=None, label=None):
    return Statement(
        bank="Test Bank",
        period_start=start,
        period_end=end,
        beginning_balance=opening,
        ending_balance=closing,
        bank_reported_average_balance=average,
        bank_reported_average_label=label,
        transactions=[
            Transaction(
                date=day,
                description=description,
                amount=amount,
                direction="credit" if amount > 0 else "debit",
            )
            for day, description, amount in rows
        ],
    )


# --- the frozen stamps -----------------------------------------------------


def test_the_basis_and_policy_are_defaults_not_assignments():
    """A result object cannot exist without declaring its basis. This is the
    property the corpus gate's total assertion rests on: every early return in
    `compute_average_daily_balance` still yields a stamped result."""
    assert AverageDailyBalanceResult().underwriting_adb_basis == UNDERWRITING_ADB_BASIS
    assert AverageDailyBalanceResult().underwriting_adb_policy == UNDERWRITING_ADB_POLICY
    # The two paths that return before any ledger is built.
    no_period = compute_average_daily_balance(Statement())
    assert no_period.underwriting_adb is None
    assert no_period.underwriting_adb_basis == UNDERWRITING_ADB_BASIS
    no_opening = compute_average_daily_balance(
        Statement(period_start="2026-01-01", period_end="2026-01-31")
    )
    assert no_opening.underwriting_adb_basis == UNDERWRITING_ADB_BASIS


def test_the_basis_literal_is_the_calendar_day_printed_period():
    assert UNDERWRITING_ADB_BASIS == "calendar_day_printed_period"
    assert UNDERWRITING_ADB_POLICY == "canonical_v1"


# --- the deprecated aliases ------------------------------------------------


def test_average_daily_balance_is_a_read_write_alias_of_underwriting_adb():
    result = AverageDailyBalanceResult()
    result.underwriting_adb = 12.34
    assert result.average_daily_balance == 12.34
    result.average_daily_balance = 56.78
    assert result.underwriting_adb == 56.78


def test_stated_average_balance_is_a_read_write_alias_on_the_statement():
    stmt = Statement(stated_average_balance=100.0)
    assert stmt.bank_reported_average_balance == 100.0
    stmt.stated_average_balance = 200.0
    assert stmt.bank_reported_average_balance == 200.0
    stmt.bank_reported_average_balance = 300.0
    assert stmt.stated_average_balance == 300.0
    # Both names are on the wire: the rename is additive, not a removal.
    dumped = stmt.model_dump()
    assert dumped["bank_reported_average_balance"] == 300.0
    assert dumped["stated_average_balance"] == 300.0


# --- exactly one public ADB ------------------------------------------------


def test_the_nested_adb_object_never_carries_a_second_adb_number():
    """`metrics.average_daily_balance` is the sole public figure. Neither the
    canonical name nor the deprecated alias may reappear inside `metrics.adb`,
    or the payload would offer a consumer two ADBs to choose between."""
    stmt = _statement(
        [("2026-01-02", "DEP", 100.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=100.0,
    )
    data = _metrics_dict(compute_metrics(stmt))
    assert "average_daily_balance" not in data["adb"]
    assert "underwriting_adb" not in data["adb"]
    assert data["average_daily_balance"] is not None
    # The stamps survive serialisation; the alternates ride internally.
    assert data["adb"]["underwriting_adb_basis"] == UNDERWRITING_ADB_BASIS
    assert set(data["adb"]["underwriting_adb_alternates"]) == set(
        UNDERWRITING_ADB_ALTERNATE_BASES
    )


def test_an_unvalidated_ledger_publishes_no_figure_on_any_basis():
    """The alternates are nulled alongside the canonical value. An unvalidated
    ledger has no defensible ADB, and that is true of every denominator, not
    only the one we publish."""
    stmt = _statement(
        [("2026-01-02", "DEP", 100.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=999.0,
    )
    data = _metrics_dict(compute_metrics(stmt))
    assert data["average_daily_balance"] is None
    assert data["adb"]["ok"] is False
    assert set(data["adb"]["underwriting_adb_alternates"]) == set(
        UNDERWRITING_ADB_ALTERNATE_BASES
    )
    assert all(
        value is None for value in data["adb"]["underwriting_adb_alternates"].values()
    )
    # The STAMPS stay: an auditor needs to know which methodology refused.
    assert data["adb"]["underwriting_adb_basis"] == UNDERWRITING_ADB_BASIS
    assert data["adb"]["underwriting_adb_policy"] == UNDERWRITING_ADB_POLICY


# --- the alternates --------------------------------------------------------


def test_every_alternate_basis_is_computed_from_the_same_ledger():
    """Five bases, one ledger. A three-day period Thu-Sat with one posting:
    the day sets differ, so the figures differ, and each is checkable by hand.
    2026-01-01 is a Thursday and a federal holiday; 01-03 is a Saturday."""
    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=300.0,
    )
    result = compute_average_daily_balance(stmt)
    assert [entry.ending_balance for entry in result.daily_balances] == [0.0, 300.0, 300.0]
    assert result.underwriting_adb == 200.0            # (0 + 300 + 300) / 3
    alternates = result.underwriting_adb_alternates
    assert set(alternates) == set(UNDERWRITING_ADB_ALTERNATE_BASES)
    assert alternates["banking_day"] == 300.0          # only Fri 01-02 is a banking day
    assert alternates["weekday_only"] == 150.0         # Thu 0 + Fri 300, over 2
    assert alternates["posting_day"] == 300.0          # only 01-02 posts
    assert alternates["credit_only"] == 200.0          # nothing negative to floor
    assert alternates["beginning_of_day"] == 100.0     # 0, 0, 300 over 3


def test_credit_only_floors_overdrawn_days_and_canonical_does_not():
    stmt = _statement(
        [("2026-01-01", "FEE", -100.0), ("2026-01-02", "DEP", 400.0)],
        start="2026-01-01", end="2026-01-02", opening=0.0, closing=300.0,
    )
    result = compute_average_daily_balance(stmt)
    assert result.underwriting_adb == 100.0            # (-100 + 300) / 2
    assert result.underwriting_adb_alternates["credit_only"] == 150.0  # (0 + 300) / 2


def test_an_alternate_over_an_empty_day_set_is_none_not_a_number():
    """A period that is entirely weekend has no banking day. The honest answer
    is None; a zero would be a figure computed over nothing."""
    stmt = _statement(
        [], start="2026-01-03", end="2026-01-04", opening=50.0, closing=50.0,
    )
    result = compute_average_daily_balance(stmt)
    assert result.underwriting_adb == 50.0
    assert result.underwriting_adb_alternates["banking_day"] is None
    assert result.underwriting_adb_alternates["weekday_only"] is None
    assert result.underwriting_adb_alternates["posting_day"] is None


def test_the_federal_bank_calendar_observes_sunday_forward_and_not_saturday():
    """The Reserve Bank rule, which is not the federal-employee rule: a Sunday
    holiday closes the Monday, a Saturday holiday closes nothing."""
    # 2027-07-04 is a Sunday -> Monday 07-05 is the closure.
    assert date(2027, 7, 5) in _federal_bank_holidays(2027)
    assert date(2027, 7, 4) not in _federal_bank_holidays(2027)
    # 2026-07-04 is a Saturday -> the Reserve Banks stay open Friday 07-03.
    assert date(2026, 7, 3) not in _federal_bank_holidays(2026)
    # The eleven statutory holidays resolve to eleven or fewer observed dates.
    assert 9 <= len(_federal_bank_holidays(2026)) <= 11
    # Thanksgiving 2026 is 2026-11-26, the fourth Thursday.
    assert date(2026, 11, 26) in _federal_bank_holidays(2026)


# --- the bank-reported comparison -----------------------------------------


def test_hypothesis_agrees_when_the_two_figures_are_the_same():
    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=300.0,
        average=200.0, label="Average Daily Balance",
    )
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance == 200.0
    assert metrics.bank_reported_average_variance == 0.0
    assert metrics.bank_reported_average_hypothesis == "agrees"


def test_hypothesis_credit_only_floored_when_the_bank_zeroes_overdrawn_days():
    """Ours keeps the overdraft signed; the bank floors it. Same ledger."""
    stmt = _statement(
        [("2026-01-01", "FEE", -100.0), ("2026-01-02", "DEP", 400.0)],
        start="2026-01-01", end="2026-01-02", opening=0.0, closing=300.0,
        average=150.0, label="Average Balance",
    )
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance == 100.0
    assert metrics.bank_reported_average_hypothesis == "credit_only_floored"


def test_hypothesis_beginning_of_day_alignment_is_an_off_by_one_day():
    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=300.0,
        average=100.0, label="Average Ledger Balance",
    )
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance == 200.0
    assert metrics.bank_reported_average_hypothesis == "beginning_of_day_alignment"


def test_hypothesis_collected_or_float_rests_on_the_printed_heading():
    """No arithmetic identity holds, so the bank's own claim about its basis is
    the only discriminator left - which is exactly why the label is captured."""
    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=300.0,
        average=321.0, label="Average Collected Balance",
    )
    assert compute_metrics(stmt).bank_reported_average_hypothesis == "collected_or_float"


def test_hypothesis_unexplained_is_the_honest_answer_and_a_finding():
    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=300.0,
        average=321.0, label="Average Ledger Balance",
    )
    assert compute_metrics(stmt).bank_reported_average_hypothesis == "unexplained"


def test_a_one_day_period_never_reports_an_alignment_it_cannot_evidence():
    """The TD NARROW shape. Over a single calendar day the "balance entering
    each day" IS the opening balance, so a bank that simply printed its opening
    balance was being reported as evidence of an off-by-one-day averaging
    convention. Reproduced before the guard existed; pinned here."""
    stmt = _statement(
        [("2026-02-28", "DEP", 400.0)],
        start="2026-02-28", end="2026-02-28", opening=100.0, closing=500.0,
        average=100.0, label="Average Balance",
    )
    result = compute_average_daily_balance(stmt)
    assert len({entry.ending_balance for entry in result.daily_balances}) == 1
    assert result.underwriting_adb_alternates["beginning_of_day"] == 100.0
    metrics = compute_metrics(stmt)
    assert metrics.bank_reported_average_variance == 400.0
    assert metrics.bank_reported_average_hypothesis == "indeterminate_flat"


def test_a_flat_ledger_reports_indeterminate_rather_than_unexplained():
    """Every basis over a constant series is that constant, so the alternates
    cannot discriminate. Saying so is more honest than `unexplained`, which
    implies evidence was weighed and found wanting."""
    stmt = _statement(
        [], start="2026-02-02", end="2026-02-06", opening=750.0, closing=750.0,
        average=900.0, label="Average Balance",
    )
    assert compute_metrics(stmt).bank_reported_average_hypothesis == "indeterminate_flat"


def test_a_flat_ledger_that_agrees_still_says_so():
    stmt = _statement(
        [], start="2026-02-02", end="2026-02-06", opening=750.0, closing=750.0,
        average=750.0, label="Average Balance",
    )
    assert compute_metrics(stmt).bank_reported_average_hypothesis == "agrees"


def test_the_flat_guard_suppresses_only_the_two_degenerate_discriminators():
    """`collected_or_float` reads the printed heading and never touches the
    series, and `n_plus_1_zero_forward` is a different identity over different
    terms. Neither degenerates on a flat ledger, so neither is suppressed -
    suppressing the second would lose the mid-cycle account-opening class."""
    collected = _statement(
        [], start="2026-02-02", end="2026-02-06", opening=750.0, closing=750.0,
        average=900.0, label="Average Collected Balance",
    )
    assert compute_metrics(collected).bank_reported_average_hypothesis == "collected_or_float"

    # A zero-forward period funded on day one and then static: flat, and the
    # bank divides by one more day than it printed.
    opening_day = _statement(
        [("2026-03-02", "OPENING DEPOSIT", 1200.0)],
        start="2026-03-02", end="2026-03-05", opening=0.0, closing=1200.0,
        average=960.0, label="Average Balance",
    )
    result = compute_average_daily_balance(opening_day)
    assert len({entry.ending_balance for entry in result.daily_balances}) == 1
    # ours 1200.00 over 4 days; theirs (4800 + 0) / 5 = 960.00
    assert compute_metrics(opening_day).bank_reported_average_hypothesis == (
        "n_plus_1_zero_forward"
    )


def test_the_export_prints_the_bank_figure_once_per_section_not_three_times():
    """The alias stays in the JSON payload, where a consumer of the old name
    would otherwise break, and is suppressed from the flat analyst exports,
    where three identical numbers read as an extraction fault."""
    from webapp.app import _analysis_rows

    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=300.0,
        average=250.0, label="Average Ledger Balance",
    )
    payload = {"statement": stmt.model_dump(), "metrics": _metrics_dict(compute_metrics(stmt))}
    assert payload["statement"]["stated_average_balance"] == 250.0

    rows = _analysis_rows(payload)
    printed = [(section, key) for section, key, value in rows if value == 250.0]
    assert printed == [
        ("statement", "bank_reported_average_balance"),
        ("metrics", "stated_average_balance"),
    ]


def test_the_hypothesis_vocabulary_is_closed():
    assert set(BANK_REPORTED_AVERAGE_HYPOTHESES) == {
        "agrees",
        "credit_only_floored",
        "collected_or_float",
        "beginning_of_day_alignment",
        "n_plus_1_zero_forward",
        "indeterminate_flat",
        "unexplained",
    }


def test_the_variance_is_signed_ours_minus_theirs():
    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=300.0,
        average=250.0, label="Average Ledger Balance",
    )
    metrics = compute_metrics(stmt)
    assert metrics.bank_reported_average_variance == -50.0
    assert metrics.bank_reported_average_variance_pct == -20.0


def test_a_withheld_ledger_publishes_no_variance_and_no_hypothesis():
    """Nothing defensible to compare, so nothing is reported - the same
    fail-closed rule the ADB itself follows."""
    stmt = _statement(
        [("2026-01-02", "DEP", 300.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=999.0,
        average=250.0, label="Average Ledger Balance",
    )
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance is None
    assert metrics.bank_reported_average_variance is None
    assert metrics.bank_reported_average_variance_pct is None
    assert metrics.bank_reported_average_hypothesis is None


def test_the_n_plus_one_zero_forward_hypothesis_names_the_woodforest_shape():
    """A zero balance forward, and the bank divides by one day MORE than the
    period it printed, counting the day the account opened."""
    stmt = _statement(
        [("2026-01-01", "OPENING DEPOSIT", 900.0)],
        start="2026-01-01", end="2026-01-03", opening=0.0, closing=900.0,
        average=675.0, label="Average Balance",
    )
    # ours: (900 + 900 + 900) / 3 = 900. theirs: (2700 + 0) / 4 = 675.
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance == 900.0
    assert metrics.bank_reported_average_hypothesis == "n_plus_1_zero_forward"


# --- the printed label -----------------------------------------------------


def test_a_parser_that_reads_a_printed_average_records_its_heading():
    """`bank_reported_average_label` is the bank's own claim about its own
    figure, captured verbatim where the parser already reads the number. It is
    what makes `collected_or_float` a discriminator rather than a guess."""
    from analysis.td_can import parse_td_canada_statement

    markdown = (
        "\n--- Page 1 ---\n"
        "Accounts issued by: THE TORONTO-DOMINION BANK\n"
        "Statement of Account Account Type Statement From - To\n"
        "Branch No. Account No. JAN 31/26 - FEB 28/26\n"
        "BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY B\n"
        "1111 1111-2222222 Page 1 of 1\n"
        "DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE\n"
        "BALANCE FORWARD JAN31 100.00\n"
        "UNCODED ROW 40.00 FEB01 140.00\n"
        "0 CHQS ENCLOSED NEXT STATEMENT DATE IS MAR 31/26\n"
        "MONTHLY AVER. CR. BAL. $500.00\n"
        "Credits 0 0.00\n"
        "Debits 0 0.00\n"
    )
    stmt = parse_td_canada_statement(markdown)
    assert stmt is not None
    assert stmt.bank_reported_average_balance == 500.0
    assert stmt.bank_reported_average_label == "MONTHLY AVER. CR. BAL."


def test_a_statement_with_no_printed_average_carries_no_label():
    stmt = _statement([], start="2026-01-01", end="2026-01-02", opening=1.0, closing=1.0)
    assert stmt.bank_reported_average_balance is None
    assert stmt.bank_reported_average_label is None
