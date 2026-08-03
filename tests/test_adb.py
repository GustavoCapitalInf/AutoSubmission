"""Underwriting-grade Average Daily Balance: one test per rule in the spec."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from analysis.adb import compute_average_daily_balance
from analysis.dates import assign_transaction_years, parse_date, resolve_year
from analysis.metrics import compute_metrics
from analysis.schema import Statement, StatementDailyBalance, Transaction


def _txn(day: str, amount: float, desc: str = "ITEM", bal: float | None = None) -> Transaction:
    return Transaction(
        date=day,
        description=desc,
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=bal,
    )


# ---- the core definition -----------------------------------------------------

def test_adb_is_daily_ending_balance_over_calendar_days():
    # 10-day period, activity on 2 days. The divisor must be 10, not 2.
    s = Statement(
        period_start="2026-03-01", period_end="2026-03-10",
        beginning_balance=1000.0, ending_balance=1400.0,
        transactions=[
            _txn("2026-03-02", 500.0, bal=1500.0),
            _txn("2026-03-05", -100.0, bal=1400.0),
        ],
    )
    r = compute_average_daily_balance(s)
    assert r.calendar_day_count == 10
    assert len(r.daily_balances) == 10
    # 03-01 1000 | 03-02..03-04 1500 | 03-05..03-10 1400
    expected = [1000.0] + [1500.0] * 3 + [1400.0] * 6
    assert [d.ending_balance for d in r.daily_balances] == expected
    assert r.daily_balance_sum == round(sum(expected), 2)
    assert r.average_daily_balance == round(sum(expected) / 10, 2)
    assert r.ok


def test_same_day_transactions_use_only_that_days_ending_balance():
    # Four postings on one day contribute exactly one balance, not four.
    s = Statement(
        period_start="2026-04-01", period_end="2026-04-03",
        beginning_balance=100.0, ending_balance=250.0,
        transactions=[
            _txn("2026-04-02", 500.0),
            _txn("2026-04-02", -200.0),
            _txn("2026-04-02", -100.0),
            _txn("2026-04-02", -50.0, bal=250.0),
        ],
    )
    r = compute_average_daily_balance(s)
    assert [d.ending_balance for d in r.daily_balances] == [100.0, 250.0, 250.0]
    assert r.daily_balances[1].transaction_count == 4
    assert r.average_daily_balance == round(600 / 3, 2)
    assert r.ok


def test_no_activity_days_inherit_previous_balance_including_weekends():
    # 2026-03-07/08 is a Sat/Sun; both must appear and inherit Friday's balance.
    s = Statement(
        period_start="2026-03-06", period_end="2026-03-09",
        beginning_balance=0.0, ending_balance=900.0,
        transactions=[_txn("2026-03-06", 900.0, bal=900.0)],
    )
    r = compute_average_daily_balance(s)
    assert [d.date for d in r.daily_balances] == [
        "2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09",
    ]
    assert date(2026, 3, 7).weekday() == 5 and date(2026, 3, 8).weekday() == 6
    assert [d.source for d in r.daily_balances[1:]] == ["carried", "carried", "carried"]
    assert r.average_daily_balance == 900.0


def test_negative_balances_are_summed_not_clamped():
    s = Statement(
        period_start="2026-05-01", period_end="2026-05-04",
        beginning_balance=100.0, ending_balance=-200.0,
        transactions=[
            _txn("2026-05-02", -300.0, bal=-200.0),
        ],
    )
    r = compute_average_daily_balance(s)
    balances = [d.ending_balance for d in r.daily_balances]
    assert balances == [100.0, -200.0, -200.0, -200.0]
    assert r.daily_balance_sum == -500.0
    assert r.average_daily_balance == -125.0  # would be +25.0 if clamped at zero
    assert r.negative_days == 3


def test_opening_and_closing_days_are_both_included():
    s = Statement(
        period_start="2026-06-01", period_end="2026-06-30",
        beginning_balance=500.0, ending_balance=500.0, transactions=[],
    )
    r = compute_average_daily_balance(s)
    assert r.calendar_day_count == 30
    assert r.daily_balances[0].date == "2026-06-01"
    assert r.daily_balances[-1].date == "2026-06-30"
    assert r.average_daily_balance == 500.0


def test_full_month_divisor_uses_calendar_days_not_posting_days():
    # 31-day month, a single posting. Averaging posting days would give 2000.
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-31",
        beginning_balance=0.0, ending_balance=3100.0,
        transactions=[_txn("2026-01-31", 3100.0, bal=3100.0)],
    )
    r = compute_average_daily_balance(s)
    assert r.calendar_day_count == 31
    assert r.average_daily_balance == 100.0  # (30 days at 0 + 1 day at 3100) / 31


# ---- balance reconstruction --------------------------------------------------

def test_printed_running_balances_validate_but_do_not_drive_the_ledger():
    s = Statement(
        period_start="2026-02-01", period_end="2026-02-03",
        beginning_balance=1000.0, ending_balance=1300.0,
        transactions=[
            _txn("2026-02-01", 200.0, bal=1200.0),
            _txn("2026-02-02", 100.0, bal=1300.0),
        ],
    )
    r = compute_average_daily_balance(s)
    assert [d.source for d in r.daily_balances] == ["reconstructed", "reconstructed", "carried"]
    assert r.validations["running_balances_support_daily_ledger"] is True


def test_wrong_running_balance_cannot_change_adb_and_fails_validation():
    s = Statement(
        period_start="2026-02-01", period_end="2026-02-02",
        beginning_balance=100.0, ending_balance=150.0,
        transactions=[_txn("2026-02-01", 50.0, bal=999.0)],
    )
    r = compute_average_daily_balance(s)
    assert [d.ending_balance for d in r.daily_balances] == [150.0, 150.0]
    assert r.average_daily_balance == 150.0
    assert r.validations["running_balances_support_daily_ledger"] is False
    assert r.ok is False


def test_final_same_day_running_balance_is_the_end_of_day_evidence():
    s = Statement(
        period_start="2026-02-01", period_end="2026-02-02",
        beginning_balance=100.0, ending_balance=150.0,
        transactions=[
            _txn("2026-02-01", 100.0, bal=150.0),
            _txn("2026-02-01", -50.0, bal=999.0),
        ],
    )
    r = compute_average_daily_balance(s)
    assert r.average_daily_balance == 150.0
    assert r.validations["running_balances_support_daily_ledger"] is False
    assert r.ok is False


def test_bank_daily_book_history_is_authoritative_end_of_day_evidence():
    s = Statement(
        period_start="2026-02-01", period_end="2026-02-04",
        beginning_balance=100.0, ending_balance=500.0,
        transactions=[_txn("2026-02-02", 400.0)],
        stated_daily_balances=[
            StatementDailyBalance(date="2026-02-02", balance=300.0),
            StatementDailyBalance(date="2026-02-04", balance=500.0),
        ],
    )
    r = compute_average_daily_balance(s)
    assert [d.ending_balance for d in r.daily_balances] == [100.0, 300.0, 300.0, 500.0]
    assert [d.source for d in r.daily_balances] == [
        "carried", "bank_daily_summary", "carried", "bank_daily_summary",
    ]
    assert r.average_daily_balance == 300.0
    assert r.ok


def test_half_cent_average_uses_financial_half_up_rounding():
    s = Statement(
        period_start="2026-02-01", period_end="2026-02-02",
        beginning_balance=1.0, ending_balance=1.01,
        transactions=[_txn("2026-02-02", 0.01)],
    )
    r = compute_average_daily_balance(s)
    assert r.daily_balance_sum == 2.01
    assert r.average_daily_balance == 1.01


def test_missing_running_balances_are_reconstructed_from_amounts():
    # No row prints a balance at all: reconstruct the whole ledger from amounts.
    s = Statement(
        period_start="2026-02-01", period_end="2026-02-04",
        beginning_balance=1000.0, ending_balance=1250.0,
        transactions=[
            _txn("2026-02-01", 500.0),
            _txn("2026-02-03", -250.0),
        ],
    )
    r = compute_average_daily_balance(s)
    assert [d.ending_balance for d in r.daily_balances] == [1500.0, 1500.0, 1250.0, 1250.0]
    assert [d.source for d in r.daily_balances] == [
        "reconstructed", "carried", "reconstructed", "carried",
    ]
    assert r.ok and r.reconciled


def test_transactions_out_of_list_order_are_sorted_chronologically():
    # Parsers emit section-grouped rows (all deposits, then all checks), so the
    # list is not in date order. The ledger must still be chronological.
    s = Statement(
        period_start="2026-07-01", period_end="2026-07-05",
        beginning_balance=0.0, ending_balance=150.0,
        transactions=[
            _txn("2026-07-04", 100.0, "DEPOSIT"),
            _txn("2026-07-02", 200.0, "DEPOSIT"),
            _txn("2026-07-03", -150.0, "CHECK"),
        ],
    )
    r = compute_average_daily_balance(s)
    assert [d.ending_balance for d in r.daily_balances] == [0.0, 200.0, 50.0, 150.0, 150.0]
    assert r.ok


def test_opening_balance_derived_when_statement_omits_it():
    s = Statement(
        period_start="2026-08-01", period_end="2026-08-03",
        beginning_balance=None, ending_balance=800.0,
        transactions=[_txn("2026-08-02", 300.0)],
    )
    r = compute_average_daily_balance(s)
    assert r.opening_balance == 500.0
    assert r.opening_balance_source == "derived_from_closing"
    # Crucially the period is NOT truncated to the first transaction day.
    assert r.calendar_day_count == 3
    assert r.daily_balances[0].date == "2026-08-01"
    assert [d.ending_balance for d in r.daily_balances] == [500.0, 800.0, 800.0]


def test_reconciliation_failure_is_warned_but_still_returns_a_figure():
    s = Statement(
        period_start="2026-09-01", period_end="2026-09-03",
        beginning_balance=1000.0, ending_balance=5000.0,
        transactions=[_txn("2026-09-02", 100.0)],
    )
    r = compute_average_daily_balance(s)
    assert r.reconciled is False
    assert r.validations["ledger_reconciles_to_closing"] is False
    assert not r.ok
    assert any("does not reconcile" in w for w in r.warnings)
    assert r.average_daily_balance is not None  # still reported, flagged


# ---- date handling across a year boundary ------------------------------------

def test_resolve_year_places_december_in_opening_year():
    start, end = date(2025, 12, 1), date(2026, 1, 2)
    assert resolve_year(12, 15, start, end) == 2025
    assert resolve_year(1, 2, start, end) == 2026
    assert resolve_year(12, 1, start, end) == 2025


def test_assign_transaction_years_repairs_a_year_crossing_period():
    # A parser stamped the period-end year (2026) on every MM/DD row.
    s = Statement(
        period_start="2025-12-01", period_end="2026-01-02",
        beginning_balance=0.0, ending_balance=300.0,
        transactions=[
            _txn("2026-12-05", 100.0),   # actually 2025-12-05
            _txn("2026-12-20", 100.0),   # actually 2025-12-20
            _txn("2026-01-02", 100.0),   # correct as-is
        ],
    )
    fixed = assign_transaction_years(s)
    assert [t.date for t in fixed.transactions] == [
        "2025-12-05", "2025-12-20", "2026-01-02",
    ]


def test_assign_transaction_years_is_a_noop_within_one_year():
    s = Statement(
        period_start="2026-03-01", period_end="2026-03-31",
        transactions=[_txn("2026-03-15", 10.0)],
    )
    assert assign_transaction_years(s) is s


def test_adb_across_year_boundary_uses_every_day():
    s = Statement(
        period_start="2025-12-01", period_end="2026-01-02",
        beginning_balance=0.0, ending_balance=330.0,
        transactions=[
            _txn("2025-12-31", 300.0, bal=300.0),
            _txn("2026-01-02", 30.0, bal=330.0),
        ],
    )
    r = compute_average_daily_balance(s)
    assert r.calendar_day_count == 33  # 31 days of Dec + Jan 1 + Jan 2
    assert r.daily_balances[0].date == "2025-12-01"
    assert r.daily_balances[-1].date == "2026-01-02"
    # 30 days at 0, then 12-31 and 01-01 at 300, then 01-02 at 330
    assert r.daily_balance_sum == round(300 * 2 + 330, 2)
    assert r.average_daily_balance == round(930 / 33, 2)
    assert r.ok


def test_parse_date_accepts_the_formats_parsers_emit():
    assert parse_date("2026-01-02") == date(2026, 1, 2)
    assert parse_date("01/02/2026") == date(2026, 1, 2)
    assert parse_date("Jan 2, 2026") == date(2026, 1, 2)
    assert parse_date("2 January 2026") == date(2026, 1, 2)
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("not a date") is None


# ---- validation --------------------------------------------------------------

def test_validations_all_pass_on_a_clean_statement():
    s = Statement(
        period_start="2026-02-01", period_end="2026-02-05",
        beginning_balance=1000.0, ending_balance=1100.0,
        transactions=[
            _txn("2026-02-02", 200.0, bal=1200.0),
            _txn("2026-02-04", -100.0, bal=1100.0),
        ],
    )
    r = compute_average_daily_balance(s)
    for name in (
        "daily_balance_count_equals_calendar_days",
        "daily_balances_contiguous",
        "covers_opening_day",
        "covers_closing_day",
        "final_balance_matches_statement_closing",
        "ledger_reconciles_to_closing",
        "opening_balance_matches_statement",
    ):
        assert r.validations[name] is True, name
    assert r.ok
    assert r.warnings == []


def test_daily_series_is_contiguous_with_no_gaps():
    s = Statement(
        period_start="2026-01-28", period_end="2026-02-02",
        beginning_balance=10.0, ending_balance=10.0, transactions=[],
    )
    r = compute_average_daily_balance(s)
    assert [d.date for d in r.daily_balances] == [
        "2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31",
        "2026-02-01", "2026-02-02",
    ]
    assert r.validations["daily_balances_contiguous"] is True


def test_leap_day_is_included():
    s = Statement(
        period_start="2028-02-01", period_end="2028-02-29",
        beginning_balance=100.0, ending_balance=100.0, transactions=[],
    )
    r = compute_average_daily_balance(s)
    assert r.calendar_day_count == 29
    assert r.daily_balances[-1].date == "2028-02-29"


def test_bank_stated_average_disagreement_is_flagged_not_silently_accepted():
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-02",
        beginning_balance=100.0, ending_balance=100.0,
        stated_average_balance=99999.0, transactions=[],
    )
    r = compute_average_daily_balance(s)
    assert r.validations["agrees_with_bank_stated_average"] is False
    assert any("differs from the bank-printed" in w for w in r.warnings)


def test_missing_period_and_dates_yields_no_figure_with_a_warning():
    s = Statement(beginning_balance=100.0, ending_balance=100.0, transactions=[])
    r = compute_average_daily_balance(s)
    assert r.average_daily_balance is None
    assert r.calendar_day_count is None
    assert any("cannot determine a statement period" in w for w in r.warnings)
    assert not r.ok


def test_inferred_or_inverted_period_is_never_reportable():
    inferred = Statement(
        period_end="2026-01-03",
        beginning_balance=100.0,
        ending_balance=150.0,
        transactions=[_txn("2026-01-02", 50.0, bal=150.0)],
    )
    inferred_result = compute_average_daily_balance(inferred)
    assert inferred_result.average_daily_balance is not None
    assert inferred_result.validations["statement_period_dates_valid"] is False
    assert inferred_result.ok is False

    inverted = Statement(
        period_start="2026-01-03",
        period_end="2026-01-01",
        beginning_balance=100.0,
        ending_balance=100.0,
        transactions=[],
    )
    inverted_result = compute_average_daily_balance(inverted)
    assert inverted_result.validations["statement_period_dates_valid"] is False
    assert inverted_result.ok is False


def test_undated_transactions_are_reported():
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-02",
        beginning_balance=0.0, ending_balance=0.0,
        transactions=[_txn("", 50.0)],
    )
    r = compute_average_daily_balance(s)
    assert any("no parseable date" in w for w in r.warnings)


def test_out_of_period_transaction_is_excluded_and_fails_validation():
    s = Statement(
        period_start="2026-01-10", period_end="2026-01-12",
        beginning_balance=0.0, ending_balance=100.0,
        transactions=[_txn("2026-01-05", 100.0)],
    )
    r = compute_average_daily_balance(s)
    assert any("outside the statement period" in w for w in r.warnings)
    assert r.daily_balances[0].ending_balance == 0.0
    assert r.validations["transactions_within_period"] is False
    assert r.validations["final_balance_matches_statement_closing"] is False
    assert r.ok is False


# ---- determinism and reproducibility ----------------------------------------

def test_result_is_deterministic_and_order_independent():
    txns = [
        _txn("2026-01-03", -40.0),
        _txn("2026-01-01", 100.0),
        _txn("2026-01-02", 60.0),
    ]
    base = dict(
        period_start="2026-01-01", period_end="2026-01-05",
        beginning_balance=0.0, ending_balance=120.0,
    )
    first = compute_average_daily_balance(Statement(**base, transactions=txns))
    shuffled = compute_average_daily_balance(
        Statement(**base, transactions=[txns[1], txns[2], txns[0]])
    )
    again = compute_average_daily_balance(Statement(**base, transactions=txns))
    assert first.average_daily_balance == shuffled.average_daily_balance == again.average_daily_balance
    assert [d.ending_balance for d in first.daily_balances] == [
        d.ending_balance for d in shuffled.daily_balances
    ]


def test_debug_report_shows_every_day_and_the_final_arithmetic():
    s = Statement(
        period_start="2026-02-02", period_end="2026-02-04",
        beginning_balance=0.0, ending_balance=10683.44,
        transactions=[
            _txn("2026-02-02", 171.86, bal=171.86),
            _txn("2026-02-03", 13389.48, bal=13561.34),
            _txn("2026-02-04", -2877.90, bal=10683.44),
        ],
    )
    r = compute_average_daily_balance(s)
    report = r.debug_report()
    assert "2026-02-02" in report and "171.86" in report
    assert "2026-02-03" in report and "13,561.34" in report
    assert "2026-02-04" in report and "10,683.44" in report
    assert f"Divided by days       : 3" in report
    assert f"${r.average_daily_balance:,.2f}" in report
    assert "PASS" in report


# ---- metrics integration -----------------------------------------------------

def test_metrics_exposes_the_full_adb_working():
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-04",
        beginning_balance=100.0, ending_balance=400.0,
        transactions=[_txn("2026-01-02", 300.0, bal=400.0)],
    )
    m = compute_metrics(s)
    assert m.average_daily_balance == round((100 + 400 + 400 + 400) / 4, 2)
    assert m.daily_balance_sum == 1300.0
    assert m.calendar_day_count == 4
    assert m.adb_ok is True
    assert m.adb is not None
    assert len(m.adb.daily_balances) == 4
    assert m.days_in_period == 4
    assert m.min_balance == 100.0 and m.max_balance == 400.0


# ---- date-collapse guard -----------------------------------------------------

_COLLAPSE_SOURCE = """Date Description Cheques & Debits ($) Deposits & Credits ($) Balance ($)
Opening balance 100.00
02 Feb Monthly fee 10.00 90.00
03 Feb Royal Foreign Exchange deposit
Reference 0521903 500.00 590.00
04 Feb Misc Payment 90.00 500.00
Closing balance 500.00
"""


def test_guard_catches_a_parser_that_folded_posting_dates_together():
    # The statement prints three posting dates; the parser produced two because
    # it dropped the "03 Feb" line (which carries no amount). Every arithmetic
    # check still passes - the amounts and the closing balance are right - so the
    # date guard is the only thing that can catch this.
    s = Statement(
        period_start="2026-02-02", period_end="2026-02-04",
        beginning_balance=100.0, ending_balance=500.0,
        transactions=[
            _txn("2026-02-02", -10.0, "Monthly fee", bal=90.0),
            _txn("2026-02-02", 500.0, "Reference 0521903", bal=590.0),   # really 03 Feb
            _txn("2026-02-04", -90.0, "Misc Payment", bal=500.0),
        ],
    )
    clean = compute_average_daily_balance(s)
    assert clean.validations["ledger_reconciles_to_closing"] is True
    assert clean.validations["final_balance_matches_statement_closing"] is True
    assert clean.ok is True          # arithmetic alone cannot see the problem

    guarded = compute_average_daily_balance(s, source_markdown=_COLLAPSE_SOURCE)
    assert guarded.validations["posting_dates_cover_source"] is False
    assert guarded.ok is False
    assert guarded.parsed_posting_days == 2
    assert guarded.source_posting_days == 3
    assert guarded.missing_posting_dates == ["2026-02-03"]
    assert any("folded together" in w for w in guarded.warnings)


def test_guard_passes_when_the_parser_covers_every_posting_date():
    s = Statement(
        period_start="2026-02-02", period_end="2026-02-04",
        beginning_balance=100.0, ending_balance=500.0,
        transactions=[
            _txn("2026-02-02", -10.0, "Monthly fee", bal=90.0),
            _txn("2026-02-03", 500.0, "Reference 0521903", bal=590.0),
            _txn("2026-02-04", -90.0, "Misc Payment", bal=500.0),
        ],
    )
    r = compute_average_daily_balance(s, source_markdown=_COLLAPSE_SOURCE)
    assert r.validations["posting_dates_cover_source"] is True
    assert r.missing_posting_dates == []
    assert r.ok is True


def test_guard_is_absent_when_no_source_text_is_supplied():
    s = Statement(
        period_start="2026-02-02", period_end="2026-02-03",
        beginning_balance=0.0, ending_balance=50.0,
        transactions=[_txn("2026-02-02", 50.0, bal=50.0)],
    )
    r = compute_average_daily_balance(s)
    assert "posting_dates_cover_source" not in r.validations
    assert r.source_posting_days is None


def test_source_posting_dates_ignores_headers_grids_and_footers():
    from analysis.dates import source_posting_dates

    start, end = date(2026, 2, 1), date(2026, 2, 28)
    md = "\n".join([
        "02 Feb Monthly fee 10.00 90.00",               # a real posting row
        "February 1, 2026 through February 28, 2026",   # period header
        "02/03 -225.43 02/12 4.68 02/22 -14.82",        # daily-balance summary grid
        "02/28/2026 Ending Balance $288.40",            # balance label
        "February 28, 2026          Page 10 of 10",     # page footer
        "February 5, 2026",                             # bare date in a page header
        "To:",
        "February 20, 2026",
        "FLEXICUENTA DE NEGOCIOS",
    ])
    assert source_posting_dates(md, start, end) == {date(2026, 2, 2)}


def test_source_posting_dates_accepts_a_bare_date_line_followed_by_amounts():
    # Navy Federal prints the date on its own line above the description/amounts.
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "05-18",
        "POS Debit- Business Debit Card 0875",
        "162.00 0.48",
        "05-19",
        "Transfer From Checking",
        "1,800.00 0.48",
    ])
    got = source_posting_dates(md, date(2026, 5, 1), date(2026, 5, 31))
    assert got == {date(2026, 5, 18), date(2026, 5, 19)}


# ---- which average the dashboards display ------------------------------------

def test_validated_computed_adb_is_preferred_over_the_bank_printed_average():
    # Banks usually print average COLLECTED balance, which lags by float days.
    # When our daily ledger validates, the computed figure is what gets reported.
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-04",
        beginning_balance=100.0, ending_balance=500.0,
        stated_average_balance=999.0,
        transactions=[_txn("2026-01-02", 400.0, bal=500.0)],
    )
    m = compute_metrics(s)
    assert m.adb_ok is True
    assert m.average_daily_balance == round((100 + 500 + 500 + 500) / 4, 2)  # 400.0
    assert "average_balance" not in vars(m)
    assert "average_balance_source" not in vars(m)
    assert m.stated_average_balance == 999.0  # still available for cross-checking


def test_unvalidated_ledger_never_substitutes_the_bank_printed_average():
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-03",
        beginning_balance=100.0, ending_balance=9999.0,
        stated_average_balance=250.0,
        transactions=[_txn("2026-01-02", 50.0)],
    )
    m = compute_metrics(s)
    assert m.adb_ok is False
    assert m.average_daily_balance is None
    assert m.daily_balance_sum is None
    assert m.stated_average_balance == 250.0


def test_unvalidated_ledger_with_no_printed_average_is_withheld():
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-03",
        beginning_balance=100.0, ending_balance=9999.0,
        transactions=[_txn("2026-01-02", 50.0)],
    )
    m = compute_metrics(s)
    assert m.adb_ok is False
    assert m.average_daily_balance is None
    assert m.daily_balance_sum is None


def test_package_rollup_weights_each_statement_by_its_own_calendar_days():
    # A 31-day statement at 100 and a 28-day statement at 200 must weight by
    # days, not average the two averages.
    from webapp.app import _package_analysis

    class _Job:
        def __init__(self, jid, days, adb):
            self.id = jid
            self.filename = f"{jid}.pdf"
            self.status = "done"
            self.analysis_error = None
            self.error = None
            self.analysis = {
                "statement": {"period_start": "2026-01-01", "period_end": "2026-01-31", "transactions": []},
                "metrics": {
                    "average_daily_balance": adb,
                    "calendar_day_count": days,
                    "adb_ok": True,
                },
                "quality": {"corporate_use": "approved", "level": "transaction_level"},
                "integrity": {"risk_level": "clear"},
                "detection": {"known_funders": []},
            }

    pkg = _package_analysis([_Job("a", 31, 100.0), _Job("b", 28, 200.0)])
    expected = round((100.0 * 31 + 200.0 * 28) / 59, 2)
    assert pkg["totals"]["average_daily_balance"] == expected
    assert [d["adb_calendar_days"] for d in pkg["documents"]] == [31, 28]
    assert all(d["adb_validated"] for d in pkg["documents"])
    assert [d["average_daily_balance"] for d in pkg["documents"]] == [100.0, 200.0]


def test_csv_export_emits_one_row_per_day_not_a_json_blob():
    from webapp.app import _analysis_rows

    s = Statement(
        period_start="2026-01-01", period_end="2026-01-03",
        beginning_balance=0.0, ending_balance=90.0,
        transactions=[_txn("2026-01-02", 90.0, bal=90.0)],
    )
    from dataclasses import asdict

    rows = _analysis_rows({"metrics": asdict(compute_metrics(s))})
    daily = [r for r in rows if r[0] == "adb_daily_balance"]
    assert [(r[1], r[2]) for r in daily] == [
        ("2026-01-01", 0.0), ("2026-01-02", 90.0), ("2026-01-03", 90.0),
    ]
    assert ("metrics", "average_daily_balance", 60.0) in rows
    assert ("adb", "calendar_day_count", 3) in rows
    assert not any(r[0] == "adb" and r[1] == "average_daily_balance" for r in rows)
    assert any(r[0] == "adb_validation" for r in rows)
    # the raw nested structure must not be dumped into the metrics section
    assert not any(r[0] == "metrics" and r[1] == "adb" for r in rows)


def test_metrics_retains_full_internal_adb_working():
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-03",
        beginning_balance=0.0, ending_balance=90.0,
        transactions=[_txn("2026-01-02", 90.0, bal=90.0)],
    )
    metrics = compute_metrics(s)
    assert metrics.average_daily_balance == 60.0
    assert metrics.calendar_day_count == 3
    assert metrics.adb is not None
    first = metrics.adb.daily_balances[0]
    assert (first.date, first.ending_balance, first.source, first.transaction_count) == (
        "2026-01-01", 0.0, "carried", 0,
    )


def test_existing_dashboard_field_binds_directly_to_authoritative_api_adb():
    javascript = Path("webapp/static/app.js").read_text(encoding="utf-8")
    assert "formatMoney(metrics.average_daily_balance, currency)" in javascript
    assert "formatMoney(doc.average_daily_balance)" in javascript
    assert "formatMoney(totals.average_daily_balance)" in javascript
    assert "metrics.average_balance" not in javascript
    assert "doc.average_balance" not in javascript
    assert "m.average_balance" not in javascript
    assert "metrics.stated_average_balance" not in javascript
    assert "daily_balances.reduce" not in javascript


def test_dashboard_has_no_adb_audit_components_or_duplicate_visible_fields():
    javascript = Path("webapp/static/app.js").read_text(encoding="utf-8")
    assert javascript.count('"Average Daily Balance"') == 5
    for forbidden in (
        "Printed ADB",
        "Parser ADB",
        "ADB Difference",
        "ADB Confidence",
        "ADB Mismatch",
    ):
        assert forbidden not in javascript
