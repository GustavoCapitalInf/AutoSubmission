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


def test_source_posting_dates_ignores_a_printed_section_total_row():
    """A section total the bank dates in the Date column is not a posting.

    BMO's Canadian business layout closes its ledger with
    `<date> Closing totals <debited> <credited>`; read as a posting it invents
    an activity day the document never had (W3_TRACKA_LOG §BMO-LAYOUTS §M6.2).
    """
    from analysis.dates import source_posting_dates

    start, end = date(2026, 4, 1), date(2026, 4, 30)
    md = "\n".join([
        "Apr 02 Payroll deposit 1,200.00 3,400.00",   # a real posting row
        "Apr 30 Closing totals 8,051.66 2,245.03",    # the printed section total
    ])
    assert source_posting_dates(md, start, end) == {date(2026, 4, 2)}


def test_source_posting_dates_ignores_bare_and_labelled_total_rows_alike():
    """The shapes the exclusion has to cover, including the two it already did
    (`Total for` / `Totals for`), so the generalisation cannot silently drop
    them."""
    from analysis.dates import source_posting_dates

    start, end = date(2026, 4, 1), date(2026, 4, 30)
    for row in [
        "Apr 30 Closing totals 8,051.66 2,245.03",
        "Apr 30 Totals 8,051.66 2,245.03",
        "Apr 30 Total 8,051.66",
        "Apr 30 Closing totals",
        "Apr 30 Totals: $8,051.66",
        "Apr 30 Total for this period 8,051.66",
        "Apr 30 Totals for April 8,051.66",
    ]:
        assert source_posting_dates(row, start, end) == set(), row


def test_source_posting_dates_keeps_a_posting_whose_description_contains_totals():
    """The negative fixture the shared-utility standard requires: `total` /
    `totals` INSIDE a description is a merchant, not a section total, and the
    row keeps its posting date."""
    from analysis.dates import source_posting_dates

    start, end = date(2026, 4, 1), date(2026, 4, 30)
    md = "\n".join([
        "Apr 03 POS PURCHASE TOTAL WINE & MORE 45.00 1,200.00",
        "Apr 04 ACH DEBIT TOTALS INC PAYROLL 300.00 900.00",
        "Apr 05 CHECK 1042 TOTAL LANDSCAPING SERVICES 75.00 825.00",
    ])
    assert source_posting_dates(md, start, end) == {
        date(2026, 4, 3), date(2026, 4, 4), date(2026, 4, 5),
    }


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


# ---- the wrapped section total (W3 §CITI3) -----------------------------------
#
# These four pin `_WRAPPED_TOTAL_LABEL`, and they live HERE rather than only in
# the cell that added it: the rule belongs to `analysis/dates.py` and is shared
# by every registration, so retiring one parser's test file must not silently
# drop its only coverage.

def test_source_posting_dates_ignores_the_date_of_a_wrapped_section_total():
    """Where a total's label and column captions fill the line, the bank's own
    date for that total prints alone below it and its figures below that."""
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Jun 30, 2026 Jun 30, 2026 SOME MERCHANT -$12.00 $1,200.00",
        "Totals Amount Account balance as of",
        "06/30/2026",
        "-$200.00 $1,200.00",
    ])
    assert date(2026, 6, 30) not in source_posting_dates(
        md, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_a_wrapped_total_only_suppresses_the_line_directly_below_it():
    """The rule reaches exactly one line. A bare date further down, with an
    ordinary line between, keeps the existing money-proximity behaviour."""
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Totals Amount Account balance as of",
        "06/30/2026",
        "-$200.00 $1,200.00",
        "06/15/2026",
        "SOME MERCHANT 42.00",
    ])
    got = source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30))
    assert date(2026, 6, 15) in got
    assert date(2026, 6, 30) not in got


def test_a_total_that_prints_its_own_money_suppresses_nothing():
    """Only a label whose figures WRAPPED reaches the line below it."""
    from analysis.dates import source_posting_dates

    md = "Totals 1,234.56 7,890.12\n06/30/2026\nSOME MERCHANT 42.00\n"
    assert date(2026, 6, 30) in source_posting_dates(
        md, date(2026, 6, 1), date(2026, 6, 30)
    )


@pytest.mark.parametrize(
    "preceding",
    [
        # a merchant name that CONTAINS the word, from the archive census
        "POS Debit- Business Debit Card 7853 06-08-26 Total Quality Logi 180-05",
        # column headers that END in it
        "DATE DESCRIPTION CURRENCY AMOUNT FEES TOTAL*",
        "Date Description Total Items Item Fee Amount Excess Dr/Cr Fee",
        # a sentence that merely mentions it
        "Note:  The total charge for the following services will be posted",
    ],
)
def test_the_word_total_away_from_the_line_start_suppresses_nothing(preceding):
    """The anchor is what keeps the rule off genuine posting dates. Each of
    these was measured above a real posting date in the archive."""
    from analysis.dates import source_posting_dates

    md = f"{preceding}\n06/09/2026\nSOME MERCHANT 42.00\n"
    assert date(2026, 6, 9) in source_posting_dates(
        md, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_a_total_opening_description_above_a_lone_date_is_the_known_falsifier():
    """The rule's boundary, stated as a test rather than left implicit.

    `_WRAPPED_TOTAL_LABEL` cannot tell a wrapped total's label from a posting
    description that happens to OPEN with the word and print no amount on its
    own line. Such a row's date is suppressed. No document in the surveyed
    archive prints this shape; it is pinned so the limit is visible, and it
    fails closed in the safe direction — a suppressed date can only relax
    `posting_dates_cover_source`, never tighten it.
    """
    from analysis.dates import source_posting_dates

    md = "Total Wine & More\n06/09/2026\n42.00 1,200.00\n"
    assert date(2026, 6, 9) not in source_posting_dates(
        md, date(2026, 6, 1), date(2026, 6, 30)
    )


# ---- POSTDATE-HEURISTIC (W3 §WITHHELDGRIDS) ---------------------------------
#
# Classes of printed line that open with a date and are not posting rows.
# Each pair below is the exclusion AND the thing it must not touch, because a
# rule that only ever removes dates is trivially satisfiable by removing all
# of them: the negative half is what pins the rule's edge.
#
# WHICH HALF A TEST IS, stated out loud, because the review's MINOR-10 found
# two tests believing they pinned a change they did not:
#
# * a GATE pin fails on the base tree (`10cc722`). It is the evidence that the
#   rule beside it does something.
# * a NEGATIVE pin passes on the base tree BY CONSTRUCTION - it asserts a date
#   the rule must not take - and a REGRESSION pin passes on base because it
#   restores base behaviour a withdrawn rule had broken. Neither is a coverage
#   hole, and both say so in their own docstring.
#
# `python -m tools.withheldgrids_tests_at_base` is the instrument: it extracts
# `10cc722`, overlays only these four test files, and reports which side of the
# line each added test falls on.

def test_an_interest_rate_row_is_not_a_posting_date():
    """`Interest Rate Changes` prints the period's first day beside a rate.

    The bank posts no transaction for it, so read as a posting it invents an
    activity day and fails `posting_dates_cover_source` for something that is
    not true of the document.

    It is refused by the money-proximity rule, and only because a money figure
    prints exactly two decimals: a dedicated "the remainder is a rate" rule was
    written first, measured against all three archive documents in this class,
    found to pin nothing that the proximity rule does not already pin, and
    removed rather than left in as an untested branch.
    """
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "06/02/2026 SOME MERCHANT 42.00",
        "Interest Rate Changes",
        "Interest Rate As Of Date Interest Rate",
        "06/01/2026 0.0000%",
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 2)
    }


def test_a_four_decimal_rate_is_not_read_as_money_by_the_proximity_test():
    """The money-presence bound, isolated from the rate-remainder rule.

    A rate on a line that ALSO carries description text is not caught by the
    remainder rule, so the only thing standing between `0.0000%` and the
    proximity test is that a money figure prints exactly two decimals.
    """
    from analysis.dates import source_posting_dates

    md = "06/09/2026 RATE NOTICE\n0.0000%\nmore notice text\nand more\n"
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == set()


def test_a_description_containing_a_percentage_keeps_its_posting_date():
    """NEGATIVE pin (passes at base by construction). A row that prints a
    rate AND an amount is still a posting row: it is the amount that decides,
    not the presence of a percentage."""
    from analysis.dates import source_posting_dates

    md = "06/09/2026 RATE 24.99% FINANCE CHARGE 45.00 1,200.00\n"
    assert date(2026, 6, 9) in source_posting_dates(
        md, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_the_money_presence_test_reads_a_comma_decimal_amount():
    """A French statement's rows print `1 234,56`, and the scan is shared.

    Without the comma the proximity test reports "no money anywhere" for a
    whole French document and drops every one of its posting dates, which
    disables `posting_dates_cover_source` on exactly the layouts whose columns
    are hardest to read.

    The date is printed BARE and its description on the next line, so the
    proximity test is the only thing standing between this row and refusal on
    the base tree as well as on this one — the first draft of this test put a
    description on the date's own line, which took the row down the branch
    base never applies the test to, and it passed for the wrong reason (the
    review's MINOR-10).
    """
    from analysis.dates import source_posting_dates

    md = "9 janv\nVirement recu UN CLIENT\n1 234,56\n"
    assert date(2026, 1, 9) in source_posting_dates(
        md, date(2026, 1, 1), date(2026, 1, 31)
    )


def test_a_masthead_line_under_a_page_number_is_not_a_posting_date():
    """A statement's masthead — its statement date, the holder, the account —
    is reprinted at the top of every page and begins with a date.

    What refuses it is that no amount is printed on it or within three
    non-empty lines of it, which is true of a masthead and of no posting row.
    Never its wording, which is customer data; and — since the review's
    MAJOR-2 — never its position either, because a real posting row printed
    under a page break sits in exactly the same position.
    """
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Page  1 of  2",
        "April 30, 2026 A CUSTOMER NAME 1234567890",
        "P.O. BOX 00000 A CITY, ST 00000-0000",
        "A CITY ST 00000",
        "Member FDIC",
        "04/09 A MERCHANT 42.00",
    ])
    assert source_posting_dates(md, date(2026, 4, 1), date(2026, 4, 30)) == {
        date(2026, 4, 9)
    }


def test_a_masthead_whose_money_is_printed_two_lines_below_it_is_counted():
    """DISCLOSURE pin (passes at base — base counts this date too).

    The cost of refusing the masthead by PROXIMITY and not by position.

    A position rule was tried — refuse a moneyless candidate inside the run of
    moneyless lines a page number opens — and it is gone (W3 §WITHHELDGRIDS
    WG12, the review's MAJOR-2): it fired before the lookahead and cost a real
    printed posting day on 16 archive documents. What remains is the proximity
    rule, and this is the shape proximity does not catch. Pinned so the
    boundary is visible rather than implied, exactly as the wrapped-total
    falsifier above is.
    """
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Page  1 of  2",
        "April 30, 2026 A CUSTOMER NAME 1234567890",
        "P.O. BOX 00000 A CITY, ST 00000-0000",
        "04/09 A MERCHANT 42.00",
    ])
    assert date(2026, 4, 30) in source_posting_dates(
        md, date(2026, 4, 1), date(2026, 4, 30)
    )


def test_a_posting_row_below_a_page_number_keeps_its_date():
    """REGRESSION pin (passes at base). A real row printed under a page break
    keeps its date; base does this too, and the position rule that briefly did
    not is gone."""
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Page  2 of  2",
        "04/08 AN EARLIER MERCHANT 15.00 900.00",
        "04/09",
        "A MERCHANT",
        "42.00 858.00",
    ])
    got = source_posting_dates(md, date(2026, 4, 1), date(2026, 4, 30))
    assert {date(2026, 4, 8), date(2026, 4, 9)} == got


def test_a_posting_row_directly_under_a_page_number_keeps_its_date():
    """REGRESSION pin: it FAILS at the reviewed tip `f97b3d2` and passes at
    base, which is the whole point.

    THE reviewer's shape (MAJOR-2): a bare posting date printed
    immediately under a page number, with its amount two non-empty lines below
    it. No money line separates the page number from the date, so the
    withdrawn position rule refused this row and deleted a printed posting day
    — at two lines, not at the "more than three" the record claimed. Money
    proximity vouches for the row and that is the whole test.
    """
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Page  1 of  2",
        "06/09",
        "A MERCHANT",
        "42.00 858.00",
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 9)
    }


def test_a_posting_row_under_a_page_number_and_a_caption_keeps_its_date():
    """REGRESSION pin (fails at the reviewed tip, passes at base). The
    reviewer's second shape: a moneyless caption line between the page number
    and the row. Two printed lines of furniture above a real posting row are
    not evidence that the row is furniture."""
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Page  1 of  2",
        "Transaction Detail",
        "06/09",
        "A MERCHANT",
        "42.00 858.00",
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 9)
    }


def test_a_boundary_row_labelled_on_the_next_line_is_not_a_posting_date():
    """The column-per-line layout prints a row's description BELOW its date,
    so the not-a-posting labels have to be read where that layout puts them."""
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Date", "Transaction Detail", "Amount($)", "Balance($)",
        "0.00",
        "06-01",
        "Beginning Balance",
        "900.00",
        "900.00",
        "06-02",
        "A MERCHANT",
        "42.00 858.00",
        "06-30",
        "Ending Balance",
        "858.00",
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 2)
    }


def test_a_bare_date_with_a_real_description_below_it_keeps_its_date():
    """NEGATIVE pin (passes at base by construction). The forward label test
    reaches exactly one line and only refuses the labels `_NOT_A_POSTING_ROW`
    already names."""
    from analysis.dates import source_posting_dates

    md = "06-02\nA MERCHANT\n42.00 858.00\n"
    assert date(2026, 6, 2) in source_posting_dates(
        md, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_a_marketing_sentence_opening_with_a_date_is_not_a_posting_date():
    """No prose recognition: the sentence is refused because no amount is
    printed on it or near it, which is true of every message block and of no
    posting row."""
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "This June, be wary of scams targeting older adults",
        "June 15 is an awareness day, and now is a great time to learn how to",
        "- One kind of scam, described at length without a figure in sight",
        "- Another kind of scam, also described without a figure",
        "Remember, always be cautious when you are asked for information",
        "6/9 A MERCHANT",
        "42.00",
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 9)
    }


def test_a_bare_date_row_whose_next_line_is_a_column_caption_keeps_its_date():
    """NEGATIVE pin (passes at base — base had no such stop).

    The money lookahead does NOT stop at a column caption.

    A stop was tried, on the theory that money printed after a caption belongs
    to the table the caption announces. Ablated over the 2,558 archive
    documents the run of record resolves to cached text it changed the source
    set of NONE of them, and adversarially it costs exactly this row its
    printed posting date (W3 §WITHHELDGRIDS WG12, the review's MINOR-7).
    Removed, and the shape it got wrong is pinned here.
    """
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "06/09",
        "Posting Date Description Amount",
        "42.00 858.00",
    ])
    assert date(2026, 6, 9) in source_posting_dates(
        md, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_a_dot_leadered_daily_balance_block_is_a_grid_not_a_ledger():
    """One issuer prints its grid heading and caption welded to dot leaders,
    so neither matched and a SECOND account's grid rows were read as postings
    of the account being published."""
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "06/09 A MERCHANT 42.00 858.00",
        "." * 40,
        "There were no transactions this period.",
        "Date" + "." * 30 + "Balance",
        "06/15 $1.00",
        "." * 40,
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 9)
    }


def test_a_dot_leadered_heading_does_not_open_a_grid_section():
    """NEGATIVE pin (passes at base — base matched the heading on the printed
    line too).

    The leaders are read for the grid's CAPTION and not for its HEADING, and
    that asymmetry is a measurement: stripping them before the heading match
    as well opens a daily-balance section on two more archive documents and
    swallows a printed posting day each of their own ledgers posts, while
    opening nothing the caption does not already open
    (`tools/withheldgrids_srcdates_audit.py`, the review's MAJOR-1).
    """
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "..... Daily Balances .....",
        "06/09 A MERCHANT 42.00 858.00",
        "06/15 ANOTHER MERCHANT 1.00 857.00",
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 9), date(2026, 6, 15)
    }


def test_a_bare_date_balance_caption_does_not_open_a_grid_section():
    """NEGATIVE pin (passes at base — base had no such caption at all).

    `Date` and `Balance` are two ordinary words; the leaders are what make
    the pair a caption.

    Consulted on a bare line the caption opened a daily-balance section on four
    archive documents that print those words as ordinary text, and each lost a
    printed posting day its own ledger posts (W3 §WITHHELDGRIDS WG12, the
    review's MAJOR-1). The dot-leadered form above still opens the section.
    """
    from analysis.dates import source_posting_dates

    md = "\n".join([
        "Date Balance",
        "06/09 A MERCHANT 42.00 858.00",
        "06/15 ANOTHER MERCHANT 1.00 857.00",
    ])
    assert source_posting_dates(md, date(2026, 6, 1), date(2026, 6, 30)) == {
        date(2026, 6, 9), date(2026, 6, 15)
    }


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
                # The package layer aggregates only across a proven single
                # currency (CURRENCY DOCTRINE §F), so the unit these figures
                # are in has to be declared like a real payload declares it.
                "statement": {"currency": "USD", "period_start": "2026-01-01", "period_end": "2026-01-31", "transactions": []},
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
    # Still bound directly to the authoritative API field with no frontend
    # recalculation; the second argument only DENOMINATES the same value
    # (CURRENCY DOCTRINE §D), exactly as the single-statement card above and
    # the balance cards below already do.
    assert "formatMoney(doc.average_daily_balance, docCurrency)" in javascript
    assert "formatMoney(totals.average_daily_balance, currency)" in javascript
    assert "metrics.average_balance" not in javascript
    assert "doc.average_balance" not in javascript
    assert "m.average_balance" not in javascript
    assert "metrics.stated_average_balance" not in javascript
    assert "daily_balances.reduce" not in javascript


def test_dashboard_balance_cards_bind_to_backend_fields_without_recalculation():
    javascript = Path("webapp/static/app.js").read_text(encoding="utf-8")
    assert 'formatMoney(statement.ending_balance, currency)' in javascript
    assert 'formatMoney(metrics.min_balance, currency)' in javascript
    assert 'formatMoney(metrics.max_balance, currency)' in javascript
    assert "daily_balances" not in javascript
    assert javascript.count("metrics.min_balance") == 2
    assert javascript.count("metrics.max_balance") == 1


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
