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
# v6: more printed forms -- a weekday in front ("Thu, Apr. 30, 2026"), an ordinal ("April 30th"), a month name
#     joined by dashes or slashes ("30-Apr-26"), a compact day and month ("30APR", "30APR26"), dotted numbers
#     ("04.30.26"), the year first ("2026/04/30"). A numeric date reads in the order the statement's own numeric
#     dates prove (a first number above 12 is a day, so is a second one); where nothing proves an order, a statement
#     in US dollars reads month first (a quarter's "05/06" is May 6, never June 5). Dates proving both orders
#     leave every ambiguous date ambiguous.
DATE_RESOLVER_VERSION = 6
_ISO = re.compile(r"([0-9]{4})[-/.]([0-9]{1,2})[-/.]([0-9]{1,2})")
_NUMERIC = re.compile(r"([0-9]{1,2})([/\-.])([0-9]{1,2})(?:\2([0-9]{2}|[0-9]{4}))?")
_WEEKDAY = re.compile(r"^(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day|nesday|sday|urday)?\.?,?\s+",
                      re.IGNORECASE)
_ORDINAL = re.compile(r"(?<=[0-9])(?:st|nd|rd|th)\b", re.IGNORECASE)
_NAMED_SEPARATORS = re.compile(r"(?<=[0-9A-Za-z])[-/](?=[0-9A-Za-z])")
_COMPACT_DAY_MONTH = re.compile(
    r"([0-9]{1,2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)([0-9]{2}|[0-9]{4})?",
    re.IGNORECASE | re.ASCII,
)
_MONTH_FIRST = re.compile(r"([^\W\d_]+)\.?\s+([0-9]{1,2})(?:,?\s+([0-9]{2}|[0-9]{4}))?")
_DAY_FIRST = re.compile(r"([0-9]{1,2})\s+([^\W\d_]+)\.?(?:,?\s+([0-9]{2}|[0-9]{4}))?")
_COMPACT_MONTH_DAY = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)([0-9]{1,2})",
    re.IGNORECASE | re.ASCII,
)
# A numeric date a page's text layer prints WITH its year, one separator throughout ("03/31/2031", "31-03-31", a
# dotted DD.MM.YYYY); numeric_order decides what it proves. Never part of a longer number, never an amount, and
# never a year-less "24/7" or "1/16" (review 8): only the rows' own date texts prove an order without a year.
_PRINTED_NUMERIC_DATE = re.compile(r"(?<![\d/.\-])(?:\d{1,2}([/\-])\d{1,2}\1(?:\d{4}|\d{2})|\d{1,2}\.\d{1,2}\.\d{4})"
                                   r"(?![\d/.\-])")
# The US-dollar month-first default applies to a period of at most this many days.
_MONTH_FIRST_DAYS = 35


@dataclass(frozen=True)
class DateResolution:
    rows: tuple[CandidateRow, ...]
    evidence: tuple[dict, ...]
    unresolved: int
    # The order numeric dates were read in ("month_first", "day_first") and why, or None (either order).
    numeric_order: str | None = None
    numeric_order_source: str | None = None


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


def _plain_date(date_text) -> str | None:
    """The printed date text without spacing variation, a leading weekday or ordinal suffixes; None when empty."""
    if not isinstance(date_text, str) or not date_text.strip():
        return None
    return _ORDINAL.sub("", _WEEKDAY.sub("", " ".join(date_text.split()))).strip()


def numeric_order(date_texts) -> str | None:
    """The order a statement's own numeric dates prove: "day_first" when one prints a first number above 12 (it can
    only be a day), "month_first" when one prints a second number above 12; "conflicting" when both are printed;
    None when no date proves either."""
    day_first = month_first = False
    for text in date_texts:
        numeric = _NUMERIC.fullmatch(_plain_date(text) or "")
        # Two dotted numbers without a year ("25.10") can be an amount: never proof of an order.
        if numeric is None or (numeric[2] == "." and numeric[4] is None):
            continue
        first, second = int(numeric[1]), int(numeric[3])
        day_first |= 12 < first <= 31 and 1 <= second <= 12
        month_first |= 12 < second <= 31 and 1 <= first <= 12
    if day_first and month_first:
        return "conflicting"
    return "day_first" if day_first else "month_first" if month_first else None


def _source_parts(date_text, order: str | None = None):
    """Return possible (month, day) pairs and the exact printed year token. ``order`` ("month_first" or
    "day_first"): a numeric date reads in that order only, when its numbers allow it."""
    raw = _plain_date(date_text)
    if raw is None:
        return (), None
    iso = _ISO.fullmatch(raw)
    if iso:
        return ((int(iso[2]), int(iso[3])),), iso[1]
    numeric = _NUMERIC.fullmatch(raw)
    if numeric:
        first, second = int(numeric[1]), int(numeric[3])
        if order == "month_first" and 1 <= first <= 12:
            return ((first, second),), numeric[4]
        if order == "day_first" and 1 <= second <= 12:
            return ((second, first),), numeric[4]
        # Neither ordering receives preference. Equal interpretations describe
        # one date, not two distinct possibilities.
        return tuple(dict.fromkeys(((first, second), (second, first)))), numeric[4]
    compact = _COMPACT_MONTH_DAY.fullmatch(raw)
    if compact:
        # A compact printed token supplies only month/day. The reviewed period
        # must still select exactly one valid year through _possibilities.
        return ((month_number(compact[1]), int(compact[2])),), None
    compact = _COMPACT_DAY_MONTH.fullmatch(raw)
    if compact:
        return ((month_number(compact[2]), int(compact[1])),), compact[3]
    named = _NAMED_SEPARATORS.sub(" ", raw)
    match = _MONTH_FIRST.fullmatch(named)
    if match:
        month, day, year = month_number(match[1]), int(match[2]), match[3]
    else:
        match = _DAY_FIRST.fullmatch(named)
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


def _possibilities(date_text, start: date, end: date, order: str | None = None) -> tuple[str, ...]:
    parts, printed_year = _source_parts(date_text, order)
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


def _undated_row_date(row, above, printed_pages, start, end, order: str | None = None):
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
        candidates = _possibilities(governing, start, end, order) if start is not None else ()
        if len(candidates) != 1:
            return None
        return candidates[0], {"source": "deterministic_text_layer_date", "reason": "date_printed_for_the_row",
                               "printed_date_text": governing, "candidate_dates": list(candidates)}
    # A row of a table printed k-up never takes the date of the row above: that can be the neighbouring
    # column group's (assemble.unfold_side_by_side).
    if (above is not None and not getattr(row, "side_by_side", False) and _printed_table(row) is not None
            and _printed_table(row) == _printed_table(above)):
        return above.date, {"source": "deterministic_date_printed_on_row_above",
                            "reason": "date_printed_once_for_the_day", "inherited_from": above.locator,
                            "candidate_dates": [above.date]}
    return None


def resolve_reviewed_dates(rows, *, period_start: str | None, period_end: str | None,
                           printed_pages=None, month_first: bool = False) -> DateResolution:
    """Return gate rows and evidence for every originally-null date.

    ``period_start`` and ``period_end`` must come from the caller's uniquely
    agreeing reviewed field evidence. Conflicting page periods must not be
    collapsed to a selected pair before calling this function. Missing,
    invalid or reversed periods leave all null dates unresolved. No explicit
    row date is overwritten, even if it is invalid or outside the period.
    A row read without any date text takes the date its page prints for it
    (_undated_row_date; ``printed_pages`` is one PrintedEvidence or None per page). Numeric dates read in the
    order the statement's own dates prove (numeric_order: its rows' date texts and every numeric date its pages'
    text layers print); ``month_first`` (a statement in US dollars) reads them month first only where nothing
    proves an order and the period is a month at most: a day-first date misread month first falls outside a
    month (held), but can stay inside a quarter or a year.
    """
    start, end, period_error = _period(period_start, period_end)
    rows = tuple(rows)
    printed_dates = [token for page in printed_pages or () if page is not None and page.native
                     for token in (match.group(0) for match in _PRINTED_NUMERIC_DATE.finditer(page.native))]
    proven = numeric_order([*(row.date_text for row in rows), *printed_dates])
    within_a_month = start is not None and (end - start).days < _MONTH_FIRST_DAYS
    order, order_source = ((proven, "printed_dates") if proven in ("day_first", "month_first") else
                           ("month_first", "statement_currency") if month_first and proven is None and within_a_month
                           else (None, None))
    resolved_rows, evidence = [], []
    unresolved = 0
    above = None  # the row above in the listing, once its date is known
    for row in rows:
        if row.date is not None:
            resolved_rows.append(row)
            above = row
            continue
        undated = (_undated_row_date(row, above, printed_pages, start, end, order)
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
        candidates = _possibilities(row.date_text, start, end, order) if period_error is None else ()
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
    return DateResolution(tuple(resolved_rows), tuple(evidence), unresolved, order, order_source)
