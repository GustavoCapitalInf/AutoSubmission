"""Resolve a missing row date only from reviewed text and a reviewed period.

The caller must first establish one consistent Stage B period from its field
evidence. This helper has no native/baseline input and does not choose a locale
or current year. It enumerates valid source interpretations inside that period
and replaces only a null date with exactly one possible result. Original rows
and printed date text remain unchanged; the replacement is for the gate only.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import re

from vlm.assemble import CandidateRow
from vlm.textparse import month_number, parse_date


# v3: French month names (janv, févr, avr, mai, juin, juil, août, déc ...), accents optional.
# v4: a row printing no date at all takes the date of the row above it on the same page (date printed once a day).
# v5: a row read without a date takes the date its page's text layer prints for it; otherwise only the row
#     above in the same printed table (never across a section, a page or from a reviewer's addition).
DATE_RESOLVER_VERSION = 5
_ISO = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})")
_NUMERIC = re.compile(r"([0-9]{1,2})([/\-])([0-9]{1,2})(?:\2([0-9]{2}|[0-9]{4}))?")
_MONTH_FIRST = re.compile(r"([^\W\d_]+)\.?\s+([0-9]{1,2})(?:,?\s+([0-9]{2}|[0-9]{4}))?")
_DAY_FIRST = re.compile(r"([0-9]{1,2})\s+([^\W\d_]+)\.?(?:,?\s+([0-9]{2}|[0-9]{4}))?")
_COMPACT_MONTH_DAY = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)([0-9]{1,2})",
    re.IGNORECASE | re.ASCII,
)


@dataclass(frozen=True)
class DateResolution:
    rows: tuple[CandidateRow, ...]
    evidence: tuple[dict, ...]
    unresolved: int


def _period(period_start, period_end):
    if period_start is None or period_end is None:
        return None, None, "reviewed_period_missing"
    try:
        if not isinstance(period_start, str) or not isinstance(period_end, str):
            raise ValueError
        start, end = date.fromisoformat(period_start), date.fromisoformat(period_end)
        if start.isoformat() != period_start or end.isoformat() != period_end or start > end:
            raise ValueError
    except ValueError:
        return None, None, "reviewed_period_invalid"
    return start, end, None


def _source_parts(date_text):
    """Return possible (month, day) pairs and the exact printed year token."""
    if not isinstance(date_text, str) or not date_text.strip():
        return (), None
    raw = " ".join(date_text.split())
    iso = _ISO.fullmatch(raw)
    if iso:
        return ((int(iso[2]), int(iso[3])),), iso[1]
    numeric = _NUMERIC.fullmatch(raw)
    if numeric:
        first, second = int(numeric[1]), int(numeric[3])
        # Neither ordering receives preference. Equal interpretations describe
        # one date, not two distinct possibilities.
        return tuple(dict.fromkeys(((first, second), (second, first)))), numeric[4]
    compact = _COMPACT_MONTH_DAY.fullmatch(raw)
    if compact:
        # A compact printed token supplies only month/day. The reviewed period
        # must still select exactly one valid year through _possibilities.
        return ((month_number(compact[1]), int(compact[2])),), None
    match = _MONTH_FIRST.fullmatch(raw)
    if match:
        month, day, year = month_number(match[1]), int(match[2]), match[3]
    else:
        match = _DAY_FIRST.fullmatch(raw)
        if not match:
            return (), None
        month, day, year = month_number(match[2]), int(match[1]), match[3]
    return (((month, day),), year) if month is not None else ((), None)


def date_text_parts(date_text) -> tuple:
    """The (month, day) readings of a printed date text; empty when it is not one."""
    return _source_parts(date_text)[0]


def reads_as(date_text, iso) -> bool:
    """Whether a printed date text (01/05, 05/01, Jan 5, DEC31, 2031-01-05) can mean this ISO date: its month and
    day in either order a numeric print allows, and its printed year when it has one."""
    try:
        filled = date.fromisoformat(str(iso))
    except ValueError:
        return False
    parts, printed_year = _source_parts(date_text)
    if (filled.month, filled.day) not in parts:
        return False
    if printed_year is None:
        return True
    return int(printed_year) == (filled.year if len(printed_year) == 4 else filled.year % 100)


def _possibilities(date_text, start: date, end: date) -> tuple[str, ...]:
    parts, printed_year = _source_parts(date_text)
    if not parts:
        return ()
    years = range(start.year, end.year + 1)
    if printed_year is not None:
        if len(printed_year) == 4:
            years = (int(printed_year),)
        else:
            # A two-digit printed year is restricted by the reviewed period;
            # parse_date's legacy 2000-century default must never decide it.
            years = tuple(year for year in years if year % 100 == int(printed_year))
    candidates = set()
    lower, upper = start.isoformat(), end.isoformat()
    for year in years:
        for month, day in parts:
            # Reuse the existing calendar parser through its unambiguous ISO
            # branch, including leap-day validation and years below 100.
            parsed = parse_date(f"{year:04d}-{month:02d}-{day:02d}")
            if parsed is not None and lower <= parsed <= upper:
                candidates.add(parsed)
    return tuple(sorted(candidates))


_TABLE = re.compile(r"^(?P<table>(?:g\d+c\d+/)?b\d+(?:t\d+|l))")


def _printed_table(row):
    """(page, printed table or text block) a proposer row was read from; None for a reviewer's addition."""
    match = _TABLE.match(row.locator or "")
    return (row.page, match.group("table")) if match else None


def _undated_row_date(row, above, printed_pages, start, end):
    """The date of a row read without one: (date, evidence) or None.

    On a page with a text layer the PDF itself says (PrintedEvidence.governing_date): a date column after the
    row's amount; else the date that begins the nearest line above it (a statement printing each day's date
    once, on the day's first row); else, when no line above it on its page is dated, the previous page's last
    dated line (the day continues onto this page). Where the text layer cannot locate the row, or on a scanned
    page, the date of the row above it in the same printed table: never across a table, a section or a page,
    never from a reviewer's addition (review 4)."""
    printed = (printed_pages[row.page - 1] if printed_pages is not None and 0 < row.page <= len(printed_pages)
               else None)
    governing = printed.governing_date(row.amount, row.balance) if printed is not None else None
    if governing == "" and 1 < row.page <= len(printed_pages or ()) and printed_pages[row.page - 2] is not None:
        governing = printed_pages[row.page - 2].last_date_text or None
    if governing:
        candidates = _possibilities(governing, start, end) if start is not None else ()
        if len(candidates) != 1:
            return None
        return candidates[0], {"source": "deterministic_text_layer_date", "reason": "date_printed_for_the_row",
                               "printed_date_text": governing, "candidate_dates": list(candidates)}
    if above is not None and _printed_table(row) is not None and _printed_table(row) == _printed_table(above):
        return above.date, {"source": "deterministic_date_printed_on_row_above",
                            "reason": "date_printed_once_for_the_day", "inherited_from": above.locator,
                            "candidate_dates": [above.date]}
    return None


def resolve_reviewed_dates(rows, *, period_start: str | None, period_end: str | None,
                           printed_pages=None) -> DateResolution:
    """Return gate rows and evidence for every originally-null date.

    ``period_start`` and ``period_end`` must come from the caller's uniquely
    agreeing reviewed field evidence. Conflicting page periods must not be
    collapsed to a selected pair before calling this function. Missing,
    invalid or reversed periods leave all null dates unresolved. No explicit
    row date is overwritten, even if it is invalid or outside the period.
    A row read without any date text takes the date its page prints for it
    (_undated_row_date; ``printed_pages`` is one PrintedEvidence or None per page).
    """
    start, end, period_error = _period(period_start, period_end)
    resolved_rows, evidence = [], []
    unresolved = 0
    above = None  # the row above in the listing, once its date is known
    for row in rows:
        if row.date is not None:
            resolved_rows.append(row)
            above = row
            continue
        undated = (_undated_row_date(row, above, printed_pages, start, end)
                   if not str(row.date_text or "").strip() and period_error is None else None)
        if undated is not None:
            resolved, detail = undated
            resolved_rows.append(replace(row, date=resolved))
            evidence.append({
                "field": "date", "original_date": None, "resolved_date": resolved,
                "date_text": row.date_text, "page": row.page, "locator": row.locator,
                "period_start": period_start, "period_end": period_end, "status": "resolved", **detail,
            })
            above = resolved_rows[-1]
            continue
        candidates = _possibilities(row.date_text, start, end) if period_error is None else ()
        resolved = candidates[0] if len(candidates) == 1 else None
        reason = (period_error or ("resolved" if resolved is not None else
                                  "reviewed_date_ambiguous" if candidates else "reviewed_date_unresolved"))
        resolved_rows.append(replace(row, date=resolved) if resolved is not None else row)
        above = resolved_rows[-1] if resolved is not None else None
        unresolved += resolved is None
        evidence.append({
            "field": "date", "original_date": None, "resolved_date": resolved,
            "date_text": row.date_text, "page": row.page, "locator": row.locator,
            "period_start": period_start, "period_end": period_end,
            "source": "deterministic_reviewed_date_text_and_period",
            "status": "resolved" if resolved is not None else "unresolved", "reason": reason,
            "candidate_dates": list(candidates),
        })
    return DateResolution(tuple(resolved_rows), tuple(evidence), unresolved)
