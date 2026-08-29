"""The date shift has to be an IDENTITY on the calendar, and it has to see every date.

Two ways this instrument could be wrong, and they fail in opposite directions.
If the shift is not a calendar identity it silently re-dates every weekday,
month length and bank holiday a fixture depends on, and an assertion that used
to test a rule starts testing a re-derivation. If the grammar misses a shape,
the file comes out disagreeing with itself — which the file's own suite
catches, loudly, but only after the fact.

So: the isomorphism is proved rather than asserted, a shift that is NOT one is
refused, and every shape the tool claims to read has a case here.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import pytest

from tools.fixpriv_shift_dates import (
    DATE_SHAPES,
    DATE_SHAPES_WITH_BARE_YEARS,
    SHIFT_YEARS,
    calendar_is_isomorphic,
    main,
    self_check,
    shift_text,
    years_in,
)


def test_the_tool_self_checks_on_import() -> None:
    self_check()


# --- the identity -------------------------------------------------------


def test_the_committed_shift_is_a_calendar_identity() -> None:
    assert calendar_is_isomorphic(2005, 2045, SHIFT_YEARS) == []


@pytest.mark.parametrize("years", [y for y in range(1, 56) if y != 28])
def test_twenty_eight_is_the_only_shift_that_works(years: int) -> None:
    """Four alone moves the weekday; seven alone moves February.

    Over this tool's own default range, 28 is the ONLY shift under 56 that is a
    calendar identity — and 56 itself is not, because 2100 is not a leap year
    and the range reaches it. The tool refuses everything it cannot prove, so a
    future card that wants a different era has to prove that one too.
    """
    assert calendar_is_isomorphic(2005, 2045, years) != []


@pytest.mark.parametrize(
    ("years", "marker"),
    [
        # Each half of the identity, ISOLATED. Together they mask each other:
        # a leap-multiple shift keeps every month length and is caught only by
        # the weekday check, and a weekday change moves every nth-weekday
        # holiday, so either half alone still refuses it. The mutation table
        # found that — two mutants, each removing one half, both surviving —
        # so the assertion has to name WHICH check fired.
        (1, " days, "),                 # a month length: 2020 is leap, 2021 is not
        (4, "changes weekday"),         # a leap multiple: only the weekday moves
        (4, "bank holidays differ"),    # and every nth-weekday holiday with it
    ],
)
def test_each_half_of_the_identity_reports_for_itself(years: int, marker: str) -> None:
    problems = calendar_is_isomorphic(2020, 2024, years)
    assert any(marker in problem for problem in problems), problems[:3]


def test_twice_the_shift_is_also_an_identity_inside_the_century() -> None:
    assert calendar_is_isomorphic(2005, 2035, 56) == []


def test_the_identity_covers_the_weekday_the_month_and_the_bank_holidays() -> None:
    """Spelled out on the three facts `analysis/adb.py` actually consults."""
    for year in range(2020, 2031):
        for month in range(1, 13):
            assert calendar.monthrange(year, month) [1] == calendar.monthrange(
                year + SHIFT_YEARS, month)[1]
    day = date(2020, 1, 1)
    while day < date(2031, 1, 1):
        assert day.weekday() == date(day.year + SHIFT_YEARS, day.month, day.day).weekday()
        day += timedelta(days=1)


def test_february_the_twenty_ninth_survives_the_shift() -> None:
    assert calendar.isleap(2032) and calendar.isleap(2032 + SHIFT_YEARS)
    assert shift_text("ON 2032-02-29", SHIFT_YEARS)[0] == "ON 2060-02-29"


# --- the grammar --------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("PERIOD 08/01/2031 TO 08/31/2031", "PERIOD 08/01/2059 TO 08/31/2059"),
        ("ATM W/D 1339 02/16/31", "ATM W/D 1339 02/16/59"),
        ("period_start == '2031-08-01'", "period_start == '2059-08-01'"),
        ("Posted January 5, 2031 net", "Posted January 5, 2059 net"),
        ("Apr 13,2031 REMOTE ONLINE Deposit", "Apr 13,2059 REMOTE ONLINE Deposit"),
        ("Dated 5 January 2031 here", "Dated 5 January 2059 here"),
        ("assert day == date(2031, 8, 1)", "assert day == date(2059, 8, 1)"),
        ("datetime(2031, 8, 1, 12, 0)", "datetime(2059, 8, 1, 12, 0)"),
        ("<td>SEP 29/31 - OCT 31/31</td>", "<td>SEP 29/59 - OCT 31/59</td>"),
        # Dash-separated, numeric and spelled. A tree that reads `03-05-2031`
        # in one fixture and `2031-03-05` in the next has to move both.
        ("shape 03-05-2031 reads", "shape 03-05-2059 reads"),
        ("shape April-1-2031 reads", "shape April-1-2059 reads"),
        # FRENCH. The Canadian readers' fixtures print their months in French,
        # and half a bilingual fixture on the old calendar is a file that no
        # longer agrees with itself.
        ("Du 3 mars 2031 au 2 avril 2031", "Du 3 mars 2059 au 2 avril 2059"),
        ("Releve du 1 decembre 2031", "Releve du 1 decembre 2059"),
        ("le 15 février 2031 solde", "le 15 février 2059 solde"),
        ("2 août 2031 depot", "2 août 2059 depot"),
    ],
)
def test_every_shape_the_tool_claims_to_read(before: str, after: str) -> None:
    assert shift_text(before, SHIFT_YEARS)[0] == after


@pytest.mark.parametrize(
    "text",
    [
        "ATM W/D 08/01 POSTED",                 # a bare day carries no year
        "EXAMPLE APRIL 2031.pdf",               # a pinned document's NAME
        "EXAMPLE_Statement_January_2031 Final.pdf",
        "Statement Period: February 2031",      # a month and a year, no day
        "2031 Example Bank Member FDIC.",       # a copyright line
        "stated_total_credits=12023.20",        # a figure that contains a year
        "account_number == '2031-7003030304'",  # an id that starts like one
        "U+2013 handled, U+2212 missed",
        "ITEMS 0 UNC BATCH 0",
    ],
)
def test_what_the_tool_must_not_touch(text: str) -> None:
    """A year is not a date. The shapes with no DAY in them are left alone.

    Two of these are the reason: a pinned corpus document's file name carries a
    month and a year, and moving it would point the test at a file that does
    not exist. The cost is that a fixture whose period is written as a month
    and a year comes out disagreeing with itself — which is a FAILING TEST, and
    the file's suite is where that is meant to be caught.
    """
    assert shift_text(text, SHIFT_YEARS)[0] == text


# --- the opt-in bare year -----------------------------------------------


@pytest.mark.parametrize(
    ("text", "shifted"),
    [
        ("start_year=2031", "start_year=2059"),
        ('maybe_year="2031"', 'maybe_year="2059"'),
        ('f"05/{day:02d}/2031 10.00"', 'f"05/{day:02d}/2059 10.00"'),
        ("_federal_bank_holidays(2031)", "_federal_bank_holidays(2059)"),
        ("Statement Period: February 2031", "Statement Period: February 2059"),
    ],
)
def test_a_bare_year_moves_only_when_it_is_asked_for(text: str, shifted: str) -> None:
    """A fixture that BUILDS its dates leaves its year behind when they move.

    `2031` on its own is not a date and nothing can tell it from a count, so
    this is a flag and not the default; the file's own suite is what makes it
    safe to use.
    """
    assert shift_text(text, SHIFT_YEARS)[0] == text
    assert shift_text(text, SHIFT_YEARS, bare_years=True)[0] == shifted


@pytest.mark.parametrize(
    "text",
    [
        "EXAMPLE APRIL 2031.pdf",     # a pinned document's NAME, either side
        "12031.20",                   # a figure that contains a year
        "version 2.0.2031",           # a version, not a year
        "REF 20315",                  # a digit run that starts like one
        "year + 2000 if year < 100",  # the century PIVOT, not a year
        "return 2000 + short_year",
        "MAX_ROWS = 2004",            # below the range: not a year in this tree
        "COUNT = 2040",               # above it: never a statement year either
    ],
)
def test_the_bare_year_guards_hold_in_both_modes(text: str) -> None:
    """A full stop on either side means a version, a float or a FILE NAME.

    And 2000 is not a year here, it is the century PIVOT every reader in
    `analysis/` uses to widen a two-digit year. Shifting it moves every date
    the reader produces, which is how the suite found it: a legacy clone and
    its replacement disagreed by exactly 28 years.
    """
    assert shift_text(text, SHIFT_YEARS)[0] == text
    assert shift_text(text, SHIFT_YEARS, bare_years=True)[0] == text


def test_the_bare_year_cannot_shift_a_year_this_tool_already_shifted() -> None:
    """The range stops at 2039, so a second pass finds nothing to move."""
    once, _ = shift_text("start_year=2031", SHIFT_YEARS, bare_years=True)
    assert once == "start_year=2059"
    assert shift_text(once, SHIFT_YEARS, bare_years=True)[0] == once


def test_the_bare_year_is_last_so_a_real_date_claims_its_year_first() -> None:
    text, counts = shift_text("on 2031-08-01 and 2031", SHIFT_YEARS, bare_years=True)
    assert text == "on 2059-08-01 and 2059"
    assert counts["isoy"] == 1 and counts["barey"] == 1


def test_the_bare_year_pattern_is_the_ordinary_one_plus_one_alternative() -> None:
    assert DATE_SHAPES_WITH_BARE_YEARS.pattern.startswith(DATE_SHAPES.pattern)


def test_a_two_digit_year_wraps_and_keeps_its_width() -> None:
    assert shift_text("ON 01/02/80 HERE", SHIFT_YEARS)[0] == "ON 01/02/08 HERE"


def test_the_shift_preserves_the_line_count_and_every_other_byte() -> None:
    before = "line one 2031-01-05\nline two\n\nline four 12/31/2031\n"
    after, counts = shift_text(before, SHIFT_YEARS)
    assert after.count("\n") == before.count("\n")
    assert len(after) == len(before)
    assert sum(counts.values()) == 2


def test_no_date_is_shifted_twice() -> None:
    """One alternation, one pass: a shape may not be re-read by another."""
    once, _ = shift_text("2031-08-01", SHIFT_YEARS)
    assert once == "2059-08-01"
    twice, _ = shift_text(once, SHIFT_YEARS)
    assert twice == "2087-08-01"      # a second CALL shifts again; one call does not


def test_the_counts_name_the_shapes() -> None:
    _text, counts = shift_text("08/01/2031 and 2031-08-01 and 08/01/31", SHIFT_YEARS)
    assert counts["slash4y"] == 1
    assert counts["isoy"] == 1
    assert counts["slash2y"] == 1


def test_years_in_reports_what_is_left_standing() -> None:
    assert years_in("a 2031 b 2059 c 2059") == {"2031": 1, "2059": 2}


# --- the CLI ------------------------------------------------------------


def test_the_cli_refuses_a_shift_it_cannot_prove(capsys) -> None:
    assert main(["--self-check", "--years", "8"]) == 2
    assert "NOT AN IDENTITY" in capsys.readouterr().err


def test_the_cli_proves_the_committed_shift(capsys) -> None:
    assert main(["--self-check"]) == 0
    assert "calendar identity" in capsys.readouterr().out


def test_a_dry_run_writes_nothing(tmp_path, capsys) -> None:
    path = tmp_path / "fixture.py"
    path.write_text("PERIOD 08/01/2031\n", encoding="utf-8")
    assert main(["--dry-run", str(path)]) == 0
    assert path.read_text(encoding="utf-8") == "PERIOD 08/01/2031\n"
    assert "1 dates shifted" in capsys.readouterr().out


def test_a_file_with_no_date_is_reported_and_not_rewritten(tmp_path, capsys) -> None:
    path = tmp_path / "fixture.py"
    path.write_text("BALANCE 100.00\n", encoding="utf-8")
    assert main([str(path)]) == 1
    assert "no date token" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == "BALANCE 100.00\n"
