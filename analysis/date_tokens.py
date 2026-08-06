"""Row-level date tokens -> ISO strings (R-2 shared utilities).

Scope boundary with `analysis/dates.py`: that module owns *statement-level*
date semantics — tolerant parsing of an already-extracted date, and re-deriving
transaction years from the statement period. This module owns the much smaller
job that sat duplicated in twelve parsers: turning the token a bank printed at
the head of a transaction row (``01/15``, ``01-15``, ``1/15/26``) into an ISO
date string, given the year the parser derived from the statement period.

Deliberately strict. These helpers raise `ValueError` (or return `None`, for
the guarded variant) on anything that is not the expected token shape, because
their callers have already matched a row-date regex: a token reaching them that
does not parse means the parser's own layout assumption is wrong, and inventing
a date would be worse than failing.

Twelve pre-R-2 `_iso` clones collapse to the three functions below; the
remaining five are genuinely bank-specific (month-name tokens, embedded
platform formats) and stay in their parsers.
"""
from __future__ import annotations

import re
from datetime import date

__all__ = [
    "iso_from_month_day",
    "iso_from_month_day_strict",
    "iso_from_month_day_year",
    "period_from_long_dates",
]

_MONTH_DAY_RE = re.compile(r"(\d{2})/(\d{2})")


def iso_from_month_day(token: str, year: int, *, separator: str = "/") -> str:
    """``("01/15", 2026)`` -> ``"2026-01-15"``.

    The year is supplied by the caller because the bank did not print one on
    the row; `analysis.dates.assign_transaction_years` later corrects it for
    statement periods that cross a year boundary. Raises `ValueError` for a
    token that is not ``month<sep>day``.
    """
    month, day = [int(part) for part in token.split(separator, 1)]
    return date(year, month, day).isoformat()


def iso_from_month_day_strict(token: str, year: int) -> str | None:
    """As above, but returns None instead of raising when `token` is not
    exactly ``MM/DD``.

    For parsers that feed this straight from a table cell whose contents they
    have not otherwise validated, where a non-date cell is an ordinary
    occurrence rather than a defect.
    """
    m = _MONTH_DAY_RE.fullmatch(token.strip())
    if not m:
        return None
    return date(year, int(m.group(1)), int(m.group(2))).isoformat()


def iso_from_month_day_year(token: str, *, century: str = "short") -> str:
    """``"1/15/26"`` -> ``"2026-01-15"``; the bank printed its own year.

    `century` controls the two-digit-year pivot:

    * ``"short"`` — add 2000 only to years below 100, so a four-digit year is
      taken as printed.
    * ``"always"`` — add 2000 unconditionally, for layouts whose year field is
      always two digits.

    Raises `ValueError` on anything that is not ``month/day/year``.
    """
    if century not in ("short", "always"):
        raise ValueError(f"unknown century mode: {century}")
    month, day, year = [int(part) for part in token.split("/")]
    if century == "always" or year < 100:
        year += 2000
    return date(year, month, day).isoformat()


#: "January 5, 2026 through February 4, 2026" — a full-month-name statement
#: period. Several banks print the period in exactly this form.
_LONG_PERIOD_RE = re.compile(
    r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+through\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})"
)
_MONTH_NAMES = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


def period_from_long_dates(markdown: str) -> tuple[str, str] | None:
    """First "<Month> D, YYYY through <Month> D, YYYY" span, as ISO strings.

    Returns None when the document does not print its period this way, which
    callers treat as "try another period format", not as an error.
    """
    m = _LONG_PERIOD_RE.search(markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), _MONTH_NAMES[sm], int(sd)).isoformat(),
        date(int(ey), _MONTH_NAMES[em], int(ed)).isoformat(),
    )
