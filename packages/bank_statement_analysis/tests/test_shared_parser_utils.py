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
    "1/15/54", "01/15/2054", "", "  01/15  ", "01-15", "abc", "01/",
    "/15", "01/15/", "1", "01/15/26/99", "0115",
)

DASH_TOKENS = tuple(t.replace("/", "-") for t in SLASH_TOKENS) + SLASH_TOKENS

MDY_TOKENS = (
    "1/15/54", "01/15/54", "12/31/99", "1/1/00", "01/15/2054", "12/31/1999",
    "02/29/52", "02/29/54", "13/01/54", "01/15", "", "abc", "1/15/26/99",
    "  1/15/54  ",
)


def _legacy_iso_slash(mmdd: str, year: int = 2054) -> str:   # capital_one, chase, linkbank, td_us, truist
    month, day = [int(part) for part in mmdd.split("/", 1)]
    return date(year, month, day).isoformat()


def _legacy_iso_dash(mmdd: str, year: int = 2054) -> str:    # b1, santander
    month, day = [int(part) for part in mmdd.split("-", 1)]
    return date(year, month, day).isoformat()


def _legacy_iso_kwyear(mmdd: str, year: int = 2054) -> str:  # farmers_merchants, first_community, wells
    month, day = [int(part) for part in mmdd.split("/")]
    return date(year, month, day).isoformat()


def _legacy_iso_strict(mmdd: str, year: int = 2054) -> str | None:   # pnc, regions
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
        _legacy_iso_slash, lambda t: dt.iso_from_month_day(t, 2054), SLASH_TOKENS
    )


def test_iso_from_month_day_matches_dash_clone():
    assert_equivalent(
        _legacy_iso_dash,
        lambda t: dt.iso_from_month_day(t, 2054, separator="-"),
        DASH_TOKENS,
    )


def test_iso_from_month_day_matches_keyword_year_clone():
    assert_equivalent(
        _legacy_iso_kwyear, lambda t: dt.iso_from_month_day(t, 2054), SLASH_TOKENS
    )


#: Tokens of the right SHAPE that no calendar can hold. The pre-R-2 clone
#: raised on these; `iso_from_month_day_strict` deliberately no longer does
#: (see the divergence test below), so they are asserted separately rather than
#: as part of the frozen-oracle matrix.
#: `02/29` is impossible in 2054 and legal in 2052 — the year the caller
#: supplies is part of the question, which is why this is decided by the
#: calendar and not by a wider regex.
IMPOSSIBLE_SLASH_TOKENS = ("02/29", "02/30", "13/01", "00/01", "01/00")


def test_iso_from_month_day_strict_matches_clone():
    assert_equivalent(
        _legacy_iso_strict,
        lambda t: dt.iso_from_month_day_strict(t, 2054),
        tuple(t for t in SLASH_TOKENS if t not in IMPOSSIBLE_SLASH_TOKENS),
    )


def test_iso_from_month_day_strict_diverges_from_the_clone_on_impossible_dates():
    """The one deliberate behaviour change to an R-2 shared utility (W3-1).

    The clone raised `ValueError` for `13/01`. Its callers ask "is this cell a
    date row?" and skip the row on None, so a raise there is not a stricter
    answer — it is an unhandled one, and discovery found 17 documents where it
    escaped the parser and aborted the whole document. The frozen oracle is
    kept for every other token, and the divergence is named here rather than
    re-baselined into it.
    """
    for token in IMPOSSIBLE_SLASH_TOKENS:
        with pytest.raises(ValueError):
            _legacy_iso_strict(token)
        assert dt.iso_from_month_day_strict(token, 2054) is None
    # ...and a leap day is still a date in a leap year.
    assert dt.iso_from_month_day_strict("02/29", 2052) == "2052-02-29"


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
    assert dt.iso_from_month_day("01/15", 2053) == "2053-01-15"
    assert dt.iso_from_month_day("12-31", 2054, separator="-") == "2054-12-31"


def test_iso_from_month_day_rejects_impossible_dates():
    with pytest.raises(ValueError):
        dt.iso_from_month_day("02/30", 2054)
    with pytest.raises(ValueError):
        dt.iso_from_month_day("13/01", 2054)


def test_iso_from_month_day_leap_day_depends_on_the_year():
    assert dt.iso_from_month_day("02/29", 2052) == "2052-02-29"
    with pytest.raises(ValueError):
        dt.iso_from_month_day("02/29", 2054)


def test_iso_from_month_day_strict_returns_none_for_non_dates():
    assert dt.iso_from_month_day_strict("Balance", 2054) is None
    assert dt.iso_from_month_day_strict("1/5", 2054) is None      # not zero-padded
    assert dt.iso_from_month_day_strict(" 01/15 ", 2054) == "2054-01-15"


def test_iso_from_month_day_year_century_pivots():
    assert dt.iso_from_month_day_year("1/15/54") == "2054-01-15"
    assert dt.iso_from_month_day_year("1/15/2054") == "2054-01-15"
    assert dt.iso_from_month_day_year("1/15/54", century="always") == "2054-01-15"


def test_iso_from_month_day_year_rejects_unknown_century_mode():
    with pytest.raises(ValueError):
        dt.iso_from_month_day_year("1/15/54", century="pivot-1970")


# ---------------------------------------------------------------------------
# PERIOD_DASH — the range dash, and why it is not the sign class (W3 §MGD)
# ---------------------------------------------------------------------------
#
# Three parsers built their period pattern out of `money.MINUS_GLYPHS`, because
# it was the only dash class the platform exported. That coupling is how U+2042
# EM DASH came to sit in a SIGN class: the period line legitimately needs it,
# and the sign class inherited it. The two are now separate constants with
# opposite widths, and these tests pin the asymmetry in both directions.

def test_the_period_dash_admits_every_dash_a_date_range_is_printed_with():
    compiled = re.compile(dt.PERIOD_DASH)
    for glyph in "-−–—":
        assert compiled.fullmatch(glyph), hex(ord(glyph))
    assert re.compile(dt.PERIOD_DASH).groups == 0


def test_the_period_dash_is_strictly_wider_than_the_money_sign_class():
    """The em dash is the whole of the difference, and it is deliberate: a dash
    between two DATES carries no value and cannot invert one, so admitting it
    costs nothing and refusing it costs the document its period. A dash before
    a FIGURE is the opposite bet — see `analysis/money.py::MINUS_GLYPHS`."""
    from analysis import money

    period = {chr(c) for c in range(0x20, 0x3000)
              if re.fullmatch(dt.PERIOD_DASH, chr(c))}
    sign = {chr(c) for c in range(0x20, 0x3000)
            if re.fullmatch(money.MINUS_CLASS, chr(c))}
    assert sign < period
    assert period - sign == {"—"}


def test_the_three_repointed_period_patterns_keep_their_em_dash():
    """The coupling, pinned where it was broken. `MINUS_GLYPHS` is a SIGN
    class; a parser that imports it to separate two dates inherits whatever the
    sign class is narrowed to next, which is what happened to these three.

    NOT a claim about the whole platform, and the difference matters:
    `balance_by_date._PERIOD_RE` still builds a `mm/dd/yyyy - mm/dd/yyyy` range
    out of `money.MINUS_CLASS` and is deliberately left alone. Repointing it
    would WIDEN it by one glyph, which can claim documents it does not claim
    today — a movement this cell has no evidence for and no mandate to make.
    Carried at W3 §MGD MGD10.
    """
    from analysis import brex, mercury, wealthsimple

    for module in (brex, mercury, wealthsimple):
        pattern = module._PERIOD_RE.pattern
        assert "—" in pattern, module.__name__
        assert dt.PERIOD_DASH in pattern, module.__name__


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


def _legacy_period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+through\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
    )
    if not m:
        return None
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    }
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), months[sm], int(sd)).isoformat(),
        date(int(ey), months[em], int(ed)).isoformat(),
    )


PERIOD_DOCS = (
    "January 5, 2054 through February 4, 2054",
    "period: December 31, 2053 through January 30, 2054 (30 days)",
    "February 1, 2054 through February 29, 2054",
    "February 1, 2053 through February 29, 2053",
    "January 5 2054 through February 4 2054",
    "January 5, 2054 to February 4, 2054",
    "",
    "no period here",
)


@pytest.mark.parametrize("doc", PERIOD_DOCS)
def test_period_from_long_dates_matches_clone(doc):
    left, right = _both(_legacy_period, dt.period_from_long_dates, doc)
    assert left == right


#: The inputs where the shared helper DELIBERATELY no longer matches the frozen
#: oracle, moved out of the parity matrix above so that matrix keeps meaning
#: "identical to the code it replaced" rather than being quietly relaxed.
DIVERGENT_PERIOD_DOCS = (
    "Jan 5, 2054 through Feb 4, 2054",
    "Balance 5, 2054 through February 4, 2054",
)


@pytest.mark.parametrize("doc", DIVERGENT_PERIOD_DOCS)
def test_period_from_long_dates_no_longer_raises_where_the_clone_did(doc):
    """W3 FILENAME-BOUNDARY: a phrase that merely LOOKS like a long period is a
    non-match, not a crash.

    `([A-Z][a-z]+)` matches any capitalized word, so the oracle's `months[sm]`
    raised `KeyError` on an abbreviated month or an ordinary capitalized word.
    The documented contract is that None means "try another period format"; the
    escaping KeyError was a `ParserCrashError` in deterministic mode and, in the
    webapp's auto mode, a silent fall-through to LLM extraction. This asserts
    both halves — what the clone did, and what the replacement does instead.
    """
    assert _both(_legacy_period, dt.period_from_long_dates, doc) == (
        ("raise", "KeyError"),
        ("ok", None),
    )


def test_period_from_long_dates_reads_the_first_span():
    assert dt.period_from_long_dates(
        "January 5, 2054 through February 4, 2054"
    ) == ("2054-01-05", "2054-02-04")


def test_period_from_long_dates_returns_none_for_other_period_formats():
    assert dt.period_from_long_dates("01/05/2054 - 02/04/2054") is None


# ---------------------------------------------------------------------------
# iso_unique_in_period (W3 §CITI3): a Date column that prints no year
# ---------------------------------------------------------------------------

def test_iso_unique_in_period_uses_the_only_year_that_fits():
    start, end = date(2054, 4, 1), date(2054, 4, 30)
    assert dt.iso_unique_in_period(4, 15, start=start, end=end) == "2054-04-15"


def test_iso_unique_in_period_resolves_a_period_that_crosses_a_year():
    start, end = date(2054, 12, 1), date(2055, 1, 31)
    assert dt.iso_unique_in_period(12, 31, start=start, end=end) == "2054-12-31"
    assert dt.iso_unique_in_period(1, 2, start=start, end=end) == "2055-01-02"


def test_iso_unique_in_period_declines_a_token_outside_the_period():
    start, end = date(2054, 4, 1), date(2054, 4, 30)
    assert dt.iso_unique_in_period(6, 15, start=start, end=end) is None


def test_iso_unique_in_period_declines_an_ambiguous_token():
    """A period longer than a year can hold the same month/day twice; the
    document never printed which, so neither is published."""
    start, end = date(2053, 1, 1), date(2054, 12, 31)
    assert dt.iso_unique_in_period(6, 15, start=start, end=end) is None


def test_iso_unique_in_period_declines_an_impossible_date():
    start, end = date(2054, 2, 1), date(2054, 3, 31)
    assert dt.iso_unique_in_period(2, 30, start=start, end=end) is None

# ---------------------------------------------------------------------------
# W3 §FINTECH additions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("month,day,year,expected", [
    ("April", 1, 2054, "2054-04-01"),
    ("Apr", "01", "2054", "2054-04-01"),
    ("APRIL", 1, 2054, "2054-04-01"),
    ("apr", 1, 2054, "2054-04-01"),
    ("September", 30, 2054, "2054-09-30"),
    ("Sep", 30, 2054, "2054-09-30"),
])
def test_iso_from_named_month_day_reads_both_printed_spellings(month, day, year, expected):
    """One statement prints both: "April 2054 statement ... April 1, 2054" in
    its header and "Apr 01" on every posting row."""
    assert dt.iso_from_named_month_day(month, day, year) == expected


@pytest.mark.parametrize("month,day,year", [
    ("Balance", 1, 2054),      # a capitalized word that is not a month
    ("Janury", 1, 2054),       # a misspelling
    ("February", 30, 2054),    # a shape that no calendar can hold
    ("April", "x", 2054),      # not a number
])
def test_iso_from_named_month_day_returns_none_rather_than_raising(month, day, year):
    """Callers reach this from a regex that proved a token's SHAPE only, so a
    non-date is an ordinary occurrence and never an exception — an escaping
    error is a `ParserCrashError` in deterministic mode."""
    assert dt.iso_from_named_month_day(month, day, year) is None


def test_the_month_table_has_one_entry_per_spelling_and_no_duplicates():
    """Twelve months, two spellings each, minus the one month whose name is
    already three letters and is therefore its own abbreviation."""
    assert len(dt.MONTH_NUMBERS) == 23
    assert dt.MONTH_NUMBERS["may"] == 5
    assert dt.MONTH_NUMBERS["march"] == dt.MONTH_NUMBERS["mar"] == 3


def test_the_month_alternation_prefers_the_longer_spelling():
    """Written longest-first so "January" is never truncated to "Jan"
    mid-match, which would leave "uary" in the caller's next group."""
    pattern = re.compile(r"^(" + dt.MONTH_NAME_ALT + r")", re.IGNORECASE)
    assert pattern.match("January 5").group(1) == "January"
    assert pattern.match("Jan 5").group(1) == "Jan"


def test_compact_lines_drops_blanks_and_compacts_what_remains():
    assert tb.compact_lines("  a   b \n\n\n  c\t d \n") == ["a b", "c d"]


def test_unique_line_returns_the_match_when_every_occurrence_is_identical():
    """A page header reprinted on every page is one value, not three."""
    pattern = re.compile(r"^Account Number:\s*(\w+)$")
    lines = ["Account Number: 12345", "other", "Account Number: 12345"]
    assert tb.unique_line(lines, pattern).group(1) == "12345"


@pytest.mark.parametrize("lines", [
    [],
    ["nothing here"],
    # two DIFFERENT values under one pattern: more than one account in the PDF
    # (L-1), or a pattern catching something else. Either way, not a choice to
    # make silently.
    ["Account Number: 12345", "Account Number: 67890"],
])
def test_unique_line_returns_none_when_the_value_is_not_unique(lines):
    assert tb.unique_line(lines, re.compile(r"^Account Number:\s*(\w+)$")) is None


# ---------------------------------------------------------------------------
# unique_match / section_runs — the two helpers W3 §LCPERIOD lifted out of the
# second and third core-processor templates, which held byte-identical copies
# ---------------------------------------------------------------------------

_SUMMARY_ROW = re.compile(r"Total additions\s+([\d,]+\.\d{2})")


def test_unique_match_reads_a_row_a_strip_prints_once():
    assert tb.unique_match("Total additions 300.00\n", _SUMMARY_ROW).group(1) == "300.00"


def test_unique_match_reads_a_row_a_strip_prints_twice_identically():
    """Not the same fact as printing it twice DIFFERENTLY: a page header
    repeats, and the test is on the captured groups."""
    region = "Total additions 300.00\n...\nTotal additions 300.00\n"
    assert tb.unique_match(region, _SUMMARY_ROW).group(1) == "300.00"


@pytest.mark.parametrize("region", [
    "",
    "no summary here",
    # the document contradicting itself about its own summary
    "Total additions 300.00\n...\nTotal additions 400.00\n",
])
def test_unique_match_declines_absence_and_contradiction(region):
    assert tb.unique_match(region, _SUMMARY_ROW) is None


_HEADING = re.compile(r"\b(DEBITS|CREDITS|DAILY BALANCES)\b")


def test_section_runs_keeps_each_occurrence_of_a_heading_as_its_own_run():
    """A section broken across a page reprints its heading. Concatenating the
    runs would put the page furniture between them inside the description of
    the row the second run opens with."""
    runs = tb.section_runs(
        "DEBITS\nrow a\nCREDITS\nrow b\nDEBITS\nrow c\nDAILY BALANCES\ngrid\n",
        _HEADING,
    )
    assert runs["DEBITS"] == ["\nrow a\n", "\nrow c\n"]
    assert runs["CREDITS"] == ["\nrow b\n"]
    assert runs["DAILY BALANCES"] == ["\ngrid\n"]


def test_section_runs_lets_a_heading_the_caller_ignores_close_the_run_before_it():
    """How a template's trailing blocks stop its last section: the name need
    only be in the pattern, not in what the caller reads."""
    heading = re.compile(r"\b(DAILY BALANCES|INTEREST INFORMATION)\b")
    runs = tb.section_runs(
        "DAILY BALANCES\ngrid\nINTEREST INFORMATION\n04-30 12.34\n", heading)
    assert runs["DAILY BALANCES"] == ["\ngrid\n"]


def test_section_runs_returns_nothing_for_a_document_with_no_heading():
    assert tb.section_runs("no sections at all\n", _HEADING) == {}


# ---------------------------------------------------------------------------
# dated_cells — the scan W3 §GRAM4 lifted out of the third core-processor
# template when the FOURTH summary grammar of the same processor needed it
# ---------------------------------------------------------------------------

_CELL_DATE = re.compile(r"(?<![\w.,/-])((?:1[0-2]|0?[1-9])-(?:3[01]|[12][0-9]|0?[1-9]))(?![\w/-])")
_CELL_VALUE = re.compile(r"(?<![\w.,/-])((?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2}))(?![\w.,])")


def _cells(run):
    return tb.dated_cells(run, date_pattern=_CELL_DATE, value_pattern=_CELL_VALUE)


def test_dated_cells_reads_two_printed_rows_off_one_physical_line():
    """The printing a line-anchored pattern silently halves."""
    cells = _cells("2-2 Preauthorized Debit 600.00 2-3 Preauthorized Debit 300.00")
    assert [(cell.date, cell.value) for cell in cells] == [("2-2", "600.00"), ("2-3", "300.00")]


def test_dated_cells_reads_a_row_whose_description_arrives_between_it_and_its_amount():
    """The interleaving this processor's text layer prints: a block of
    descriptions stands between a run of dates and the amounts that answer
    them, so a cell closes at the first value before the NEXT date."""
    run = (
        "3-13 Preauthorized Credit 50,000.00 3-17 Preauthorized Credit\n"
        "AS AMERICA INC. INTC 1500010009 CCD KAPITUS SERVICIN CCD\n"
        "213,750.00 3-20 Preauthorized Credit 10,053.20\n"
    )
    assert [(cell.date, cell.value) for cell in _cells(run)] == [
        ("3-13", "50,000.00"), ("3-17", "213,750.00"), ("3-20", "10,053.20"),
    ]


def test_dated_cells_reads_the_sub_dollar_figure_this_processor_prints_bare():
    assert [cell.value for cell in _cells("2-5 Preauthorized Debit .14")] == [".14"]


def test_dated_cells_returns_none_when_a_date_closes_no_cell():
    """None, never a short list: a dropped row is how a ledger comes to
    disagree with a printed total while still looking complete."""
    assert _cells("2-2 Preauthorized Debit 600.00 2-3 Preauthorized Debit") is None


def test_dated_cells_returns_an_empty_list_for_a_run_with_no_dates():
    """Distinct from None: a section that printed nothing is not a section
    that printed something unreadable."""
    assert _cells("Date Description Debits\n") == []


def test_dated_cells_describes_only_what_stands_between_the_date_and_the_value():
    cell, = _cells("3-9 Account Transfer Cr. 40,000.00")
    assert cell.described == " Account Transfer Cr. "


def test_dated_cells_bounds_each_cell_so_the_caller_can_read_what_precedes_a_row():
    """`run[previous.end:cell.start]` is the leading cell of a
    `Number Date Amount` cheque grid — two rows on one line, each keeping its
    own serial."""
    run = "2068 3-9 143.86 2070 * 3-2 3,276.93"
    first, second = _cells(run)
    assert run[:first.start] == "2068 "
    assert run[first.end:second.start] == " 2070 * "
    assert run[first.start:first.end] == "3-9 143.86"


# ---------------------------------------------------------------------------
# SCAN-DAY-GLYPH — when is a glyph in a scanned day cell a digit? (W3 §SCANHYG)
# ---------------------------------------------------------------------------


def test_a_legible_digit_is_what_the_bank_printed():
    """The scan mangles a printed glyph; it does not invent a legible digit
    where none was. A reader that doubted the digits that survived could read
    nothing at all."""
    assert dt.day_readings("8") == frozenset({8})
    assert dt.day_readings("18") == frozenset({18})
    assert dt.day_readings("08") == frozenset({8})


def test_a_stray_glyph_BESIDE_a_legible_digit_can_only_be_ink():
    """The `8&` shape, and it needs no glyph table: read as a digit the stray
    glyph would date the row to the eighty-somethingth of the month, and there
    is no such day. So the only reading that IS a day is the one that treats it
    as ink — derived, not assumed."""
    assert dt.day_readings("8&") == frozenset({8})
    assert dt.day_readings("1&1") == frozenset({11})


def test_a_stray_glyph_STANDING_ALONE_is_every_single_digit_day():
    """The same glyph in the other position, and the reason a confusion table
    would be wrong: the cell says only that ONE glyph was printed there."""
    assert dt.day_readings("&") == frozenset(range(1, 10))
    assert dt.day_readings("g") == dt.day_readings("&")


def test_a_stray_glyph_BEFORE_a_digit_is_not_resolved_by_deleting_it():
    """`&8` is `8`, `18` or `28`, and the reader this gate replaced answered
    `8` by deleting the glyph — silently, and with nothing able to notice."""
    assert dt.day_readings("&8") == frozenset({8, 18, 28})


def test_a_cell_no_reading_makes_a_day_of_returns_nothing():
    for token in ("", "88", "99", "0", "abcd", "1234"):
        assert dt.day_readings(token) == frozenset(), token


def test_a_cell_wider_than_the_bound_is_not_enumerated():
    """Longer than a day cell plus one piece of stray ink is a capture that ran
    into the column next door; enumerating it would be guessing at scale."""
    assert dt.MAX_DAY_CELL_GLYPHS == 3
    assert dt.day_readings("&&&") != frozenset()
    assert dt.day_readings("&&&&") == frozenset()


def test_a_superscript_is_a_stray_glyph_and_never_a_crash():
    """`str.isdigit()` is True for U+00B2 and `int()` rejects it. This module
    uses `isdecimal` throughout, so the conversion is total."""
    assert dt.day_readings("\u00b2") == frozenset(range(1, 10))
    assert dt.day_readings("1\u00b2") == frozenset({1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19})


def test_sole_day_resolves_only_where_the_document_admits_one_reading():
    assert dt.sole_day("g", {9}) == 9
    assert dt.sole_day("g", {8, 9}) is None
    assert dt.sole_day("&", {7, 8, 9}) is None
    assert dt.sole_day("8&", range(1, 32)) == 8
    assert dt.sole_day("8&", {1, 2, 3}) is None
    assert dt.sole_day("", {1}) is None
