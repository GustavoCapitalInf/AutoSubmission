"""The bank's printed daily balances, checked against the rows (audit 2026-10-13 REC-1, step 1).

`analysis/adb.py` lets each bank-printed end-of-day balance REPLACE the carry
the rows reconstruct for its day. That is the documented design (the bank's
table outranks reconstruction) and it stays. What was missing is any record
of whether the two agreed: the one check that touches a snapshot day,
`running_balances_support_daily_ledger`, reads the ledger AFTER the override,
and a wrong printed cell on a day with no posting, healed by a later cell,
passed every check.

Step 1 is ADVISORY ONLY. `validations["bank_daily_balances_agree_with_rows"]`
records, day over day, whether each printed balance equals the carry the rows
reach that day before the override; a disagreement adds one warning, saying
the bank's table was used. It is never a required check: `ok`, the ADB, the
NSF days and the outcome are exactly what they were. Making it required is
the owner's call (step 2).

Fabricated statements only: round figures, the year 2054.
"""
from __future__ import annotations

from analysis.adb import compute_average_daily_balance
from analysis.schema import Statement, StatementDailyBalance, Transaction

CHECK = "bank_daily_balances_agree_with_rows"
NEEDLE = "disagree with the balance the transactions reach"


def _txn(day: str, amount: float, bal: float | None = None) -> Transaction:
    return Transaction(
        date=day, description="DEPOSIT" if amount > 0 else "WITHDRAWAL", amount=amount,
        direction="credit" if amount > 0 else "debit", running_balance=bal,
    )


def _statement(grid: dict[str, float], *, rows=None) -> Statement:
    """Five days; opening 100.00, one deposit of 50.00 on day 2, ending 150.00."""
    return Statement(
        period_start="2054-02-01", period_end="2054-02-05",
        beginning_balance=100.0, ending_balance=150.0,
        transactions=rows if rows is not None else [_txn("2054-02-02", 50.0)],
        stated_daily_balances=[
            StatementDailyBalance(date=day, balance=balance) for day, balance in grid.items()
        ],
    )


def _warnings(result) -> list[str]:
    return [w for w in result.warnings if NEEDLE in w]


def test_a_grid_that_agrees_with_the_rows_is_recorded_as_agreeing():
    result = compute_average_daily_balance(_statement({"2054-02-02": 150.0, "2054-02-05": 150.0}))
    assert result.validations[CHECK] is True
    assert _warnings(result) == []
    assert result.ok


def test_no_printed_daily_balance_means_no_check():
    result = compute_average_daily_balance(_statement({}))
    assert CHECK not in result.validations
    assert result.ok


def test_a_wrong_cell_on_a_quiet_day_healed_by_a_later_cell_is_now_visible():
    """The gap the finding names: day 3 prints 900.00 with no posting, day 4
    heals it. Every required check passes, the ADB is the grid's, and nothing
    said so. Now the check is False and one warning names both days (day 3
    disagrees with the rows, and day 4 with the carry day 3's cell left)."""
    grid = {"2054-02-02": 150.0, "2054-02-03": 900.0, "2054-02-04": 150.0}
    result = compute_average_daily_balance(_statement(grid))
    assert result.validations[CHECK] is False
    [warning] = _warnings(result)
    assert warning.startswith("2 bank-printed daily balance(s) disagree")
    assert "2054-02-03" in warning and "2054-02-04" in warning
    assert "the bank's daily balance was used" in warning
    # advisory: the override, the ADB and `ok` are untouched
    assert [d.ending_balance for d in result.daily_balances] == [100.0, 150.0, 900.0, 150.0, 150.0]
    assert result.average_daily_balance == 290.0
    assert result.ok


def test_the_same_with_a_running_balance_on_every_row_is_also_visible():
    """`running_balances_support_daily_ledger` compares two printings on a
    posting day, so it cannot see a quiet day's cell. This check can."""
    grid = {"2054-02-03": 900.0, "2054-02-04": 150.0}
    result = compute_average_daily_balance(
        _statement(grid, rows=[_txn("2054-02-02", 50.0, bal=150.0)]))
    assert result.validations["running_balances_support_daily_ledger"] is True
    assert result.validations[CHECK] is False
    assert result.ok


def test_a_wrong_cell_on_a_posting_day_with_no_running_balance_is_visible():
    grid = {"2054-02-02": 160.0, "2054-02-04": 150.0}
    result = compute_average_daily_balance(_statement(grid))
    assert result.validations[CHECK] is False
    [warning] = _warnings(result)
    assert warning.startswith("2 bank-printed daily balance(s) disagree")
    assert result.ok


def test_the_bank_daily_book_history_shape_stays_authoritative_and_is_recorded():
    """The shape `tests/test_adb.py` pins as authoritative end-of-day evidence:
    the table is used (the ADB is the table's) and the disagreement is now on
    the record."""
    s = Statement(
        period_start="2054-02-01", period_end="2054-02-04",
        beginning_balance=100.0, ending_balance=500.0,
        transactions=[_txn("2054-02-02", 400.0)],
        stated_daily_balances=[
            StatementDailyBalance(date="2054-02-02", balance=300.0),
            StatementDailyBalance(date="2054-02-04", balance=500.0),
        ],
    )
    result = compute_average_daily_balance(s)
    assert result.average_daily_balance == 300.0
    assert result.ok
    assert result.validations[CHECK] is False


def test_the_comparison_starts_from_the_opening_the_override_starts_from():
    """Computed from the same carry the override uses (the resolved opening,
    including any carry-in or initialization fold), so a cell on the first day
    that prints the opening balance agrees."""
    result = compute_average_daily_balance(_statement({"2054-02-01": 100.0, "2054-02-02": 150.0}))
    assert result.validations[CHECK] is True


def test_the_check_never_decides_ok_or_the_figures():
    """Advisory, never required: the same statement with and without the
    wrong cell differs in this one key, its warning, and the days the grid
    overrides; `ok` and every other validation are identical."""
    base = compute_average_daily_balance(_statement({"2054-02-04": 150.0}))
    wrong = compute_average_daily_balance(_statement({"2054-02-03": 900.0, "2054-02-04": 150.0}))
    assert base.validations[CHECK] is True and wrong.validations[CHECK] is False
    assert base.ok and wrong.ok
    assert {k: v for k, v in base.validations.items() if k != CHECK} == {
        k: v for k, v in wrong.validations.items() if k != CHECK}


def test_the_telemetry_vocabulary_names_both_codes_as_advisory():
    from telemetry.diagnostics import ADB_CHECKS, ADVISORY_CODES, diagnose

    assert CHECK in ADB_CHECKS
    assert f"adb:{CHECK}" in ADVISORY_CODES
    assert "adb_state:bank_daily_balances_disagree_with_rows" in ADVISORY_CODES
    grid = {"2054-02-03": 900.0, "2054-02-04": 150.0}
    result = compute_average_daily_balance(_statement(grid))
    payload = {
        "statement": {"transactions": []},
        "reconciliation": {"issues": [], "continuity_breaks": 0},
        "metrics": {"average_daily_balance": None, "adb": {
            "validations": result.validations, "warnings": result.warnings}},
        "integrity": {"flags": []},
        "quality": {"corporate_use": "manual_review_required"},
    }
    diagnosis = diagnose(payload, "review")
    assert f"adb:{CHECK}" in diagnosis["codes"]
    assert "adb_state:bank_daily_balances_disagree_with_rows" in diagnosis["codes"]
    assert "adb_state:unmapped_warning" not in diagnosis["codes"]
    assert diagnosis["primary_class"] == "advisory_only"
