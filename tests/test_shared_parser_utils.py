"""Tests for `analysis/date_tokens.py` and `analysis/tables.py` (R-2).

Same discipline as `tests/test_money.py`: each pre-R-2 clone is reproduced
verbatim as a frozen oracle and asserted identical to its replacement over a
shared input matrix, then the shared API is tested on its own terms.
"""
from __future__ import annotations

import re
from datetime import date
from html import unescape

import pytest

from analysis import date_tokens as dt
from analysis import tables as tb


def _both(fn_a, fn_b, value):
    out = []
    for fn in (fn_a, fn_b):
        try:
            out.append(("ok", fn(value)))
        except Exception as exc:  # noqa: BLE001 - equivalence includes failures
            out.append(("raise", type(exc).__name__))
    return out[0], out[1]


def assert_equivalent(oracle, replacement, inputs):
    mismatches = []
    for value in inputs:
        left, right = _both(oracle, replacement, value)
        if left != right:
            mismatches.append(f"{value!r}: legacy={left} shared={right}")
    assert not mismatches, "behaviour drift:\n  " + "\n  ".join(mismatches)


# ===========================================================================
# date_tokens
# ===========================================================================

SLASH_TOKENS = (
    "01/15", "1/5", "12/31", "02/29", "02/30", "13/01", "00/01", "01/00",
    "1/15/26", "01/15/2026", "", "  01/15  ", "01-15", "abc", "01/",
    "/15", "01/15/", "1", "01/15/26/99", "0115",
)

DASH_TOKENS = tuple(t.replace("/", "-") for t in SLASH_TOKENS) + SLASH_TOKENS

MDY_TOKENS = (
    "1/15/26", "01/15/26", "12/31/99", "1/1/00", "01/15/2026", "12/31/1999",
    "02/29/24", "02/29/26", "13/01/26", "01/15", "", "abc", "1/15/26/99",
    "  1/15/26  ",
)


def _legacy_iso_slash(mmdd: str, year: int = 2026) -> str:   # capital_one, chase, linkbank, td_us, truist
    month, day = [int(part) for part in mmdd.split("/", 1)]
    return date(year, month, day).isoformat()


def _legacy_iso_dash(mmdd: str, year: int = 2026) -> str:    # b1, santander
    month, day = [int(part) for part in mmdd.split("-", 1)]
    return date(year, month, day).isoformat()


def _legacy_iso_kwyear(mmdd: str, year: int = 2026) -> str:  # farmers_merchants, first_community, wells
    month, day = [int(part) for part in mmdd.split("/")]
    return date(year, month, day).isoformat()


def _legacy_iso_strict(mmdd: str, year: int = 2026) -> str | None:   # pnc, regions
    m = re.fullmatch(r"(\d{2})/(\d{2})", mmdd.strip())
    if not m:
        return None
    return date(year, int(m.group(1)), int(m.group(2))).isoformat()


def _legacy_iso_bluevine(mmddyy: str) -> str:
    month, day, year = [int(part) for part in mmddyy.split("/")]
    return date(2000 + year, month, day).isoformat()


def _legacy_iso_first_farmers(value: str) -> str:
    month, day, year = [int(part) for part in value.split("/")]
    return date(2000 + year if year < 100 else year, month, day).isoformat()


def test_iso_from_month_day_matches_slash_clone():
    assert_equivalent(
        _legacy_iso_slash, lambda t: dt.iso_from_month_day(t, 2026), SLASH_TOKENS
    )


def test_iso_from_month_day_matches_dash_clone():
    assert_equivalent(
        _legacy_iso_dash,
        lambda t: dt.iso_from_month_day(t, 2026, separator="-"),
        DASH_TOKENS,
    )


def test_iso_from_month_day_matches_keyword_year_clone():
    assert_equivalent(
        _legacy_iso_kwyear, lambda t: dt.iso_from_month_day(t, 2026), SLASH_TOKENS
    )


def test_iso_from_month_day_strict_matches_clone():
    assert_equivalent(
        _legacy_iso_strict,
        lambda t: dt.iso_from_month_day_strict(t, 2026),
        SLASH_TOKENS,
    )


def test_iso_from_month_day_year_matches_always_pivot_clone():
    assert_equivalent(
        _legacy_iso_bluevine,
        lambda t: dt.iso_from_month_day_year(t, century="always"),
        MDY_TOKENS,
    )


def test_iso_from_month_day_year_matches_short_pivot_clone():
    assert_equivalent(
        _legacy_iso_first_farmers, dt.iso_from_month_day_year, MDY_TOKENS
    )


def test_iso_from_month_day_uses_the_supplied_year():
    assert dt.iso_from_month_day("01/15", 2025) == "2025-01-15"
    assert dt.iso_from_month_day("12-31", 2026, separator="-") == "2026-12-31"


def test_iso_from_month_day_rejects_impossible_dates():
    with pytest.raises(ValueError):
        dt.iso_from_month_day("02/30", 2026)
    with pytest.raises(ValueError):
        dt.iso_from_month_day("13/01", 2026)


def test_iso_from_month_day_leap_day_depends_on_the_year():
    assert dt.iso_from_month_day("02/29", 2024) == "2024-02-29"
    with pytest.raises(ValueError):
        dt.iso_from_month_day("02/29", 2026)


def test_iso_from_month_day_strict_returns_none_for_non_dates():
    assert dt.iso_from_month_day_strict("Balance", 2026) is None
    assert dt.iso_from_month_day_strict("1/5", 2026) is None      # not zero-padded
    assert dt.iso_from_month_day_strict(" 01/15 ", 2026) == "2026-01-15"


def test_iso_from_month_day_year_century_pivots():
    assert dt.iso_from_month_day_year("1/15/26") == "2026-01-15"
    assert dt.iso_from_month_day_year("1/15/2026") == "2026-01-15"
    assert dt.iso_from_month_day_year("1/15/26", century="always") == "2026-01-15"


def test_iso_from_month_day_year_rejects_unknown_century_mode():
    with pytest.raises(ValueError):
        dt.iso_from_month_day_year("1/15/26", century="pivot-1970")


# ===========================================================================
# tables
# ===========================================================================

TEXTS = (
    "", "   ", "one", "one  two", "one\ntwo", "  leading", "trailing  ",
    "a\t\tb", "line\r\nline", " nbsp ", "multi   space   run",
    "<td>1,234.56</td>", "<b>bold</b> text", "&amp; entity", "&lt;tag&gt;",
    "<td colspan='2'>x</td>", "a<br/>b", "&nbsp;", "100%", "<>", "< >",
)

_LEGACY_TAG_RE = re.compile(r"<[^>]+>")
_LEGACY_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_LEGACY_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)


def _legacy_compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _legacy_clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(_LEGACY_TAG_RE.sub("", value))).strip()


def _legacy_rows(table: str) -> list[list[str]]:
    return [
        [_legacy_clean(cell) for cell in _LEGACY_CELL_RE.findall(row)]
        for row in _LEGACY_ROW_RE.findall(table)
    ]


TABLES = (
    "",
    "<table><tr><td>Date</td><td>Amount</td></tr></table>",
    "<table><tr><td>01/15</td><td>$1,234.56</td><td>Balance</td></tr>"
    "<tr><td>01/16</td><td>$2.00</td><td>x</td></tr></table>",
    "<table><tr><th>h</th></tr><tr><td>a</td></tr></table>",
    "<table><TR><TD>upper</TD></TR></table>",
    "<table><tr><td colspan='2'>wide</td></tr></table>",
    "<table><tr><td>multi\nline\ncell</td></tr></table>",
    "<table><tr><td>&amp;co</td></tr></table>",
    "<tr><td>bare row</td></tr>",
    "no tags at all",
)


def test_compact_whitespace_matches_clone():
    assert_equivalent(_legacy_compact, tb.compact_whitespace, TEXTS)


def test_clean_cell_matches_clone():
    assert_equivalent(_legacy_clean, tb.clean_cell, TEXTS)


def test_table_rows_matches_clone():
    assert_equivalent(_legacy_rows, tb.table_rows, TABLES)


def test_shared_regexes_match_the_clones_they_replace():
    assert tb.TAG_RE.pattern == _LEGACY_TAG_RE.pattern
    assert tb.ROW_RE.pattern == _LEGACY_ROW_RE.pattern
    assert tb.CELL_RE.pattern == _LEGACY_CELL_RE.pattern


HEADING_DOC = """
Deposits and Credits
some preamble
<table><tr><td>01/15</td><td>10.00</td></tr></table>
Deposits and Credits - continued
<table><tr><td>01/16</td><td>20.00</td></tr></table>
Deposits and Credits (continued)
<table><tr><td>01/17</td><td>30.00</td></tr></table>
"""


def _legacy_tables_after(markdown: str, heading: str, continued: str) -> list[str]:
    pattern = re.compile(
        rf"(?m)^\s*{re.escape(heading)}{continued}\s*$.*?(<table>.*?</table>)",
        re.IGNORECASE | re.DOTALL,
    )
    return [m.group(1) for m in pattern.finditer(markdown)]


@pytest.mark.parametrize("continued", ["", r"(?: - continued)?", r"(?: \(continued\))?"])
def test_tables_after_matches_clone(continued):
    assert tb.tables_after(HEADING_DOC, "Deposits and Credits", continued=continued) == (
        _legacy_tables_after(HEADING_DOC, "Deposits and Credits", continued)
    )


def test_tables_after_finds_one_table_per_heading_occurrence():
    plain = tb.tables_after(HEADING_DOC, "Deposits and Credits")
    assert len(plain) == 1
    assert "01/15" in plain[0]

    with_dash = tb.tables_after(
        HEADING_DOC, "Deposits and Credits", continued=r"(?: - continued)?"
    )
    assert len(with_dash) == 2


def test_tables_after_returns_empty_for_a_missing_heading():
    assert tb.tables_after(HEADING_DOC, "Checks Paid") == []


SECTION_DOC = "Additions\nrow one\nrow two\nSubtractions\nrow three\nService Charges\n"


def _legacy_section(markdown: str, start: str, end: str) -> str:
    m = re.search(start + r"(?P<body>.*?)" + end, markdown, re.IGNORECASE | re.DOTALL)
    return m.group("body") if m else ""


@pytest.mark.parametrize(
    "start,end",
    [
        ("Additions", "Subtractions"),
        ("Subtractions", "Service Charges"),
        ("Additions", "Nowhere"),
        ("Nowhere", "Subtractions"),
        (r"^\s*Additions\s*$", r"^\s*Subtractions\s*$"),
    ],
)
def test_section_between_matches_clone(start, end):
    assert tb.section_between(SECTION_DOC, start, end) == _legacy_section(
        SECTION_DOC, start, end
    )


def test_section_between_returns_the_body_and_empty_when_absent():
    body = tb.section_between(SECTION_DOC, "Additions", "Subtractions")
    assert "row one" in body and "row three" not in body
    assert tb.section_between(SECTION_DOC, "Missing", "Subtractions") == ""


def test_table_rows_keeps_row_positions_for_th_only_rows():
    rows = tb.table_rows("<table><tr><th>h</th></tr><tr><td>a</td></tr></table>")
    assert rows == [[], ["a"]]
