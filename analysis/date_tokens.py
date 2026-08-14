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
    "iso_or_none",
    "iso_from_month_day",
    "iso_from_month_day_strict",
    "iso_from_month_day_year",
    "period_from_long_dates",
    "year_within_period",
    "iso_within_period",
]

_MONTH_DAY_RE = re.compile(r"(\d{2})/(\d{2})")


def iso_or_none(year: int, month: int, day: int) -> str | None:
    """The ISO date, or None when those three numbers are not one.

    A row-date regex proves a token's SHAPE and nothing more. `26/13/24` and
    `42/13` match `MM/DD/YY` and `MM/DD` perfectly and are not dates — they are
    a column that is not the date column (a check number, an amount fragment,
    an OCR misread). Discovery hit exactly that on 17 documents and `date()`
    raised `ValueError` out of the parser.

    Callers that already treat an unreadable token as "not a date row" want the
    same answer here, so the guarded helpers below funnel through this one
    place rather than each growing a `try`. Guessing what the digits were meant
    to be is never an option: the row is dropped and reconciliation decides
    whether what remains is publishable.
    """
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


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
    occurrence rather than a defect. "Not exactly MM/DD" includes a token of
    the right shape that no calendar can hold (`42/13`) — see `iso_or_none`.
    """
    m = _MONTH_DAY_RE.fullmatch(token.strip())
    if not m:
        return None
    return iso_or_none(year, int(m.group(1)), int(m.group(2)))


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
    # The pattern's `([A-Z][a-z]+)` matches any capitalized word, so a phrase
    # shaped like a long period but headed by something else ("Jan 5, 2026
    # through Feb 4, 2026", "Balance 5, 2026 through February 4, 2026") reaches
    # here. That is a NON-MATCH, not an error: the contract above says callers
    # treat None as "try another period format", and a KeyError escaping into
    # them is a crash (ParserCrashError in deterministic mode, and in the
    # webapp's auto mode a silent fall-through to LLM extraction).
    start_month, end_month = _MONTH_NAMES.get(sm), _MONTH_NAMES.get(em)
    if start_month is None or end_month is None:
        return None
    return (
        date(int(sy), start_month, int(sd)).isoformat(),
        date(int(ey), end_month, int(ed)).isoformat(),
    )


def year_within_period(month: int, day: int, start: date, end: date) -> int | None:
    """The year a bare `month/day` row belongs to, decided by the period.

    A statement whose period does not cross a year boundary has one candidate
    and this is trivially that year. One that does cross has two, and the
    correct one is the only one that puts the row inside the printed period —
    which is a fact about the document rather than a rule about which half of
    the period a month "usually" falls in.

    None when neither candidate lands inside the period, including when the
    numbers are not a date at all (`02/30`): a row-date regex proves a token's
    shape and nothing more, so the caller must be able to refuse it.
    """
    for year in dict.fromkeys((start.year, end.year)):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            return year
    return None


def iso_within_period(token: str, start: date, end: date) -> str | None:
    """``("03/05", …)`` -> ``"2026-03-05"`` when it falls inside the period.

    `year_within_period` applied to a `month/day` token, for the parsers whose
    rows carry no year and whose statement period is the only evidence of one.
    None for a token that is not `month/day`, or that no candidate year places
    inside the period.
    """
    parts = token.split("/")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    month, day = (int(part) for part in parts)
    year = year_within_period(month, day, start, end)
    return date(year, month, day).isoformat() if year else None
