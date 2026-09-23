"""Fabricated reviewed-date cases; no page, baseline, clock, or model input."""
from dataclasses import asdict, replace
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.dates import DATE_RESOLVER_VERSION, resolve_reviewed_dates
from vlm.textparse import parse_date


def _row(text, *, explicit=None, locator="b0t0r1"):
    return CandidateRow(explicit, text, "SYNTHETIC exact  source", Decimal("12.34"),
                        "debit", Decimal("87.66"), 2, "stage_a+stage_b", locator,
                        "column", (.1, .2, .9, .3), Decimal("12.34"))


def test_compact_dates_enumerate_both_years_without_mutating_original_evidence():
    rows = [_row("dEc31"), _row("JAN29", locator="b0t0r2")]
    originals = [asdict(row) for row in rows]
    result = resolve_reviewed_dates(rows, period_start="2030-12-15", period_end="2031-01-31")
    assert DATE_RESOLVER_VERSION == 5
    assert result.unresolved == 0
    assert [row.date for row in result.rows] == ["2030-12-31", "2031-01-29"]
    assert [asdict(row) for row in rows] == originals
    for original, resolved, evidence in zip(originals, result.rows, result.evidence):
        assert asdict(resolved) == {**original, "date": resolved.date}
        assert evidence == {
            "field": "date", "original_date": None, "resolved_date": resolved.date,
            "date_text": original["date_text"], "page": 2, "locator": original["locator"],
            "period_start": "2030-12-15", "period_end": "2031-01-31",
            "source": "deterministic_reviewed_date_text_and_period", "status": "resolved",
            "reason": "resolved", "candidate_dates": [resolved.date],
        }


@pytest.mark.parametrize("month,name", list(enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)))
def test_only_the_printed_compact_month_and_day_are_used(month, name):
    row = _row(name.upper() + "9")
    result = resolve_reviewed_dates([row], period_start="2031-01-01", period_end="2031-12-31")
    assert result.rows[0].date == f"2031-{month:02d}-09"
    assert row.date is None and result.rows[0].date_text == row.date_text


@pytest.mark.parametrize("text", [
    "JAN32", "JAN00", "APR31", "FEB29", "FEB30", "JAN029", "JAN292031", "JAN29 31",
    "JAN29.", "JAN.29", "JAN-29", "29JAN", "January29", "SEPT29", "ſep29",
    "Janitor29", "JAN29 trailing", "prefix JAN29", "", None,
])
def test_invalid_or_unrecognized_compact_dates_stay_unresolved(text):
    row = _row(text)
    result = resolve_reviewed_dates([row], period_start="2031-01-01", period_end="2031-12-31")
    assert result.rows[0] is row and result.unresolved == 1
    assert result.evidence[0]["reason"] == "reviewed_date_unresolved"
    assert result.evidence[0]["candidate_dates"] == []


def test_compact_leap_day_uses_existing_calendar_validation():
    row = _row("FEB29")
    result = resolve_reviewed_dates([row], period_start="2024-02-01", period_end="2024-02-29")
    assert result.rows[0].date == "2024-02-29" and result.unresolved == 0
    assert row.date is None


@pytest.mark.parametrize("text", ["DEC14", "JAN31", "FEB01"])
def test_compact_date_outside_reviewed_period_is_not_shifted(text):
    row = _row(text)
    result = resolve_reviewed_dates([row], period_start="2030-12-15", period_end="2031-01-30")
    assert result.rows[0] is row and result.unresolved == 1
    assert result.evidence[0]["candidate_dates"] == []


def test_multiple_in_period_years_remain_ambiguous_despite_neighbor_date():
    explicit = _row("JAN28", explicit="2031-01-28", locator="explicit")
    missing = _row("JAN29")
    result = resolve_reviewed_dates([explicit, missing], period_start="2030-01-01", period_end="2031-12-31")
    assert result.rows == (explicit, missing) and result.unresolved == 1
    assert result.rows[0] is explicit and result.rows[1] is missing
    assert result.evidence[0]["reason"] == "reviewed_date_ambiguous"
    assert result.evidence[0]["candidate_dates"] == ["2030-01-29", "2031-01-29"]


@pytest.mark.parametrize("start,end,reason", [
    (None, "2031-01-31", "reviewed_period_missing"),
    ("2030-12-15", None, "reviewed_period_missing"),
    (None, None, "reviewed_period_missing"),
    ("2031-02-01", "2031-01-31", "reviewed_period_invalid"),
    ("2031-02-30", "2031-03-31", "reviewed_period_invalid"),
    ("12/15/2030", "2031-01-31", "reviewed_period_invalid"),
    (["2030-12-15"], "2031-01-31", "reviewed_period_invalid"),
])
def test_missing_or_invalid_period_cannot_borrow_a_neighbor_year(start, end, reason):
    explicit = _row("JAN28", explicit="2031-01-28", locator="explicit")
    missing = _row("JAN29")
    result = resolve_reviewed_dates([explicit, missing], period_start=start, period_end=end)
    assert result.rows == (explicit, missing) and result.unresolved == 1
    assert result.evidence[0]["reason"] == reason
    assert result.evidence[0]["candidate_dates"] == []


@pytest.mark.parametrize("explicit", ["2031-01-28", "2032-01-29", "INVALID EXPLICIT DATE", ""])
def test_compact_printed_token_never_overwrites_an_explicit_date(explicit):
    row = _row("JAN29", explicit=explicit)
    result = resolve_reviewed_dates([row], period_start="2030-12-15", period_end="2031-01-31")
    assert result.rows == (row,) and result.rows[0] is row
    assert result.evidence == () and result.unresolved == 0


def test_compact_support_is_limited_to_reviewed_date_resolution():
    assert parse_date("JAN29", year_hint=2031) is None
    assert parse_date("DEC31", year_hint=2030) is None
    first = _row("JAN29")
    duplicate = replace(first, locator="separate-printed-occurrence")
    result = resolve_reviewed_dates([first, duplicate], period_start="2031-01-01", period_end="2031-01-31")
    assert len(result.rows) == len(result.evidence) == 2
    assert [row.locator for row in result.rows] == [first.locator, duplicate.locator]
    assert first.date is None and duplicate.date is None
