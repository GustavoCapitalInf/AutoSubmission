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
from vlm.textparse import parse_date


DATE_RESOLVER_VERSION = 1
_MONTHS = {
    name: month
    for month, names in enumerate((
        ("jan", "january"), ("feb", "february"), ("mar", "march"),
        ("apr", "april"), ("may",), ("jun", "june"), ("jul", "july"),
        ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"),
        ("nov", "november"), ("dec", "december"),
    ), 1)
    for name in names
}
_ISO = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})")
_NUMERIC = re.compile(r"([0-9]{1,2})([/\-])([0-9]{1,2})(?:\2([0-9]{2}|[0-9]{4}))?")
_MONTH_FIRST = re.compile(r"([A-Za-z]+)\.?\s+([0-9]{1,2})(?:,?\s+([0-9]{2}|[0-9]{4}))?")
_DAY_FIRST = re.compile(r"([0-9]{1,2})\s+([A-Za-z]+)\.?(?:,?\s+([0-9]{2}|[0-9]{4}))?")


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
    match = _MONTH_FIRST.fullmatch(raw)
    if match:
        month, day, year = _MONTHS.get(match[1].lower()), int(match[2]), match[3]
    else:
        match = _DAY_FIRST.fullmatch(raw)
        if not match:
            return (), None
        month, day, year = _MONTHS.get(match[2].lower()), int(match[1]), match[3]
    return (((month, day),), year) if month is not None else ((), None)


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


def resolve_reviewed_dates(rows, *, period_start: str | None, period_end: str | None) -> DateResolution:
    """Return gate rows and evidence for every originally-null date.

    ``period_start`` and ``period_end`` must come from the caller's uniquely
    agreeing reviewed field evidence. Conflicting page periods must not be
    collapsed to a selected pair before calling this function. Missing,
    invalid or reversed periods leave all null dates unresolved. No explicit
    row date is overwritten, even if it is invalid or outside the period.
    """
    start, end, period_error = _period(period_start, period_end)
    resolved_rows, evidence = [], []
    unresolved = 0
    for row in rows:
        if row.date is not None:
            resolved_rows.append(row)
            continue
        candidates = _possibilities(row.date_text, start, end) if period_error is None else ()
        resolved = candidates[0] if len(candidates) == 1 else None
        reason = (period_error or ("resolved" if resolved is not None else
                                  "reviewed_date_ambiguous" if candidates else "reviewed_date_unresolved"))
        resolved_rows.append(replace(row, date=resolved) if resolved is not None else row)
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
