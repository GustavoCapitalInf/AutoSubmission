"""Shared, deterministic date handling for statement parsing.

Two jobs:

1. `parse_date` — one tolerant ISO/US date parser used by every downstream
   stage, so "2026-01-02", "01/02/2026" and "Jan 2, 2026" all resolve the
   same way no matter which parser produced the row.

2. `assign_transaction_years` — repair the calendar year on transactions when
   a statement period crosses a year boundary.

Why (2) is needed: most bank statements print transaction dates as MM/DD with
no year, so the per-bank parsers derive one year from the statement period
(typically `int(period_end[:4])`) and stamp it on every row. That is correct
for the ~97% of statements that sit inside a single year and silently wrong
for the rest. For a period of 2025-12-01 through 2026-01-02, a 12/15 row
becomes 2026-12-15 — six months in the future, outside the period, and it
would corrupt any chronological reconstruction built on top of it.

This module fixes it centrally rather than in each parser: the month and day
that the bank printed are preserved, and only the year is re-derived from the
statement period. One auditable rule, applied to every bank at once.
"""
from __future__ import annotations

from datetime import date, datetime

from .schema import Statement

_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%m-%d-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%B %d %Y",
)


def parse_date(value: str | date | None) -> date | None:
    """Parse a statement date. Returns None rather than raising: a missing or
    unreadable date must not abort an entire statement."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    # Fast path: ISO, possibly with a time component appended.
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _with_year(day: date, year: int) -> date | None:
    """Rebuild `day` in `year`, tolerating Feb 29 landing on a common year."""
    try:
        return date(year, day.month, day.day)
    except ValueError:
        return None


def resolve_year(
    month: int,
    day: int,
    period_start: date | None,
    period_end: date | None,
) -> int | None:
    """Pick the calendar year for a printed MM/DD within a statement period.

    A statement period spans at most ~2 months, so a given month/day belongs to
    exactly one of the period's candidate years in all but pathological cases.
    Preference order:

      1. the candidate year that places the date inside the period (earliest,
         if somehow both do)
      2. the month-sequence rule: months at or after the start month belong to
         the start year, earlier months belong to the end year
      3. the end year
    """
    if period_start is None and period_end is None:
        return None
    if period_start is None:
        return period_end.year
    if period_end is None:
        return period_start.year

    candidates = []
    for year in sorted({period_start.year, period_end.year}):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        candidates.append(candidate)

    inside = [c for c in candidates if period_start <= c <= period_end]
    if inside:
        return min(inside).year
    if period_start.year == period_end.year:
        return period_start.year
    # Outside the period (a check written before the period, say). Fall back to
    # the month sequence: Dec belongs to the opening year, Jan to the closing one.
    return period_start.year if month >= period_start.month else period_end.year


def assign_transaction_years(stmt: Statement) -> Statement:
    """Re-derive transaction years from the statement period.

    Only touches statements whose period crosses a year boundary, and only
    changes the year — the bank-printed month and day are authoritative and are
    never modified. A no-op for single-year periods, which is the common case.
    """
    period_start = parse_date(stmt.period_start)
    period_end = parse_date(stmt.period_end)
    if period_start is None or period_end is None:
        return stmt
    if period_start.year == period_end.year:
        return stmt

    changed = False
    transactions = []
    for txn in stmt.transactions:
        parsed = parse_date(txn.date)
        if parsed is None:
            transactions.append(txn)
            continue
        year = resolve_year(parsed.month, parsed.day, period_start, period_end)
        if year is None or year == parsed.year:
            transactions.append(txn)
            continue
        corrected = _with_year(parsed, year)
        if corrected is None:
            transactions.append(txn)
            continue
        changed = True
        transactions.append(txn.model_copy(update={"date": corrected.isoformat()}))

    if not changed:
        return stmt
    return stmt.model_copy(update={"transactions": transactions})
