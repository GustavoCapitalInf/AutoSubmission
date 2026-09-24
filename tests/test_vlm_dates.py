"""Date resolution uses fabricated reviewed fields, with no baseline or clock."""
from dataclasses import asdict, replace
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.dates import DATE_RESOLVER_VERSION, resolve_reviewed_dates


def _row(text, *, explicit=None, locator="b1t0r1"):
    return CandidateRow(explicit, text, "FABRICATED EXACT DESCRIPTION  0001", Decimal("25.00"),
                        "credit", Decimal("125.00"), 3, "stage_a+stage_b", locator,
                        "column", (0.1, 0.2, 0.8, 0.3), Decimal("25.00"))


@pytest.mark.parametrize("text,start,end,expected", [
    ("01/02", "2031-01-01", "2031-01-31", "2031-01-02"),
    ("01/02", "2031-02-01", "2031-02-28", "2031-02-01"),
    ("13/04", "2031-04-01", "2031-04-30", "2031-04-13"),
    ("04/13", "2031-04-01", "2031-04-30", "2031-04-13"),
    ("03-03", "2031-01-01", "2031-12-31", "2031-03-03"),
    ("31 December", "2030-12-15", "2031-01-14", "2030-12-31"),
    ("Jan. 2", "2030-12-15", "2031-01-14", "2031-01-02"),
    ("SEPTEMBER 9", "2031-09-01", "2031-09-30", "2031-09-09"),
    ("9 Sept.", "2031-09-01", "2031-09-30", "2031-09-09"),
    ("Feb 29", "2024-02-01", "2024-02-29", "2024-02-29"),
    ("29/02", "2024-01-01", "2024-12-31", "2024-02-29"),
    ("2031-1-2", "2031-01-01", "2031-01-31", "2031-01-02"),
    ("January 2, 2031", "2031-01-01", "2031-01-31", "2031-01-02"),
    ("2 January 2031", "2031-01-01", "2031-01-31", "2031-01-02"),
    ("12/31/99", "1999-12-01", "2000-01-31", "1999-12-31"),
    ("01/02/00", "1999-12-01", "2000-01-31", "2000-01-02"),
    ("January 2, 31", "1931-01-01", "1931-01-31", "1931-01-02"),
    ("01/02", "0001-01-01", "0001-01-31", "0001-01-02"),
    ("  Jan.\n 2  ", "2031-01-01", "2031-01-31", "2031-01-02"),
])
def test_resolves_only_the_unique_source_interpretation(text, start, end, expected):
    row = _row(text)
    original = asdict(row)
    result = resolve_reviewed_dates([row], period_start=start, period_end=end)
    assert result.unresolved == 0 and result.rows[0].date == expected
    assert asdict(result.rows[0]) == {**original, "date": expected}
    assert asdict(row) == original and row.date is None
    assert result.evidence == ({
        "field": "date", "original_date": None, "resolved_date": expected, "date_text": text,
        "page": 3, "locator": row.locator,
        "period_start": start, "period_end": end,
        "source": "deterministic_reviewed_date_text_and_period", "status": "resolved",
        "reason": "resolved", "candidate_dates": [expected],
    },)


@pytest.mark.parametrize("text,start,end", [
    ("01/02", "2031-01-01", "2031-02-28"),
    ("04/07/2031", "2031-01-01", "2031-12-31"),
    ("Jan 2", "2030-01-01", "2031-12-31"),
    ("02/29", "2024-01-01", "2028-12-31"),
    ("12/31/99", "1999-01-01", "2099-12-31"),
])
def test_multiple_numeric_orders_or_years_remain_ambiguous(text, start, end):
    row = _row(text)
    result = resolve_reviewed_dates([row], period_start=start, period_end=end)
    assert result.rows[0] is row and result.unresolved == 1
    assert result.evidence[0]["reason"] == "reviewed_date_ambiguous"
    assert len(result.evidence[0]["candidate_dates"]) >= 2


@pytest.mark.parametrize("text", [
    "Feb 29", "February 30", "00/02", "13/13", "January 32", "Janitor 2", "Febtober 2",
    "2031-02-30", "2030-02-02", "02/02/30", "02/02/031", "02/02-2031",
    "Deposit February 2", "February 2 trailing text", "February2", "", " ", None,
])
def test_invalid_out_of_period_or_unrecognized_source_is_not_repaired(text):
    row = _row(text)
    result = resolve_reviewed_dates([row], period_start="2031-02-01", period_end="2031-02-28")
    assert result.rows[0] is row and result.unresolved == 1
    assert result.evidence[0]["reason"] == "reviewed_date_unresolved"
    assert result.evidence[0]["resolved_date"] is None


@pytest.mark.parametrize("start,end,reason", [
    (None, "2031-01-31", "reviewed_period_missing"),
    ("2031-01-01", None, "reviewed_period_missing"),
    ("2031-02-01", "2031-01-31", "reviewed_period_invalid"),
    ("2031-02-30", "2031-03-31", "reviewed_period_invalid"),
    ("01/01/2031", "2031-01-31", "reviewed_period_invalid"),
    ("20310101", "2031-01-31", "reviewed_period_invalid"),
    (["2031-01-01", "2031-02-01"], "2031-02-28", "reviewed_period_invalid"),
])
def test_missing_invalid_or_conflicting_period_inputs_leave_rows_untouched(start, end, reason):
    row = _row("Jan 2")
    result = resolve_reviewed_dates([row], period_start=start, period_end=end)
    assert result.rows[0] is row and result.unresolved == 1
    assert result.evidence[0]["reason"] == reason


def test_explicit_dates_are_never_overwritten_and_source_order_is_preserved():
    first = _row("01/02", explicit="2031-01-03", locator="explicit")
    invalid = _row("01/02", explicit="INVALID EXPLICIT DATE", locator="invalid")
    missing = _row("01/02", locator="missing")
    duplicate = replace(missing, locator="separate-occurrence")
    rows = [first, invalid, missing, duplicate]
    result = resolve_reviewed_dates(rows, period_start="2031-01-01", period_end="2031-01-31")
    assert result.rows[:2] == (first, invalid) and result.rows[0] is first and result.rows[1] is invalid
    assert [row.locator for row in result.rows] == [row.locator for row in rows]
    assert len(result.rows) == 4 and len(result.evidence) == 2 and result.unresolved == 0
    assert all(row.date == "2031-01-02" for row in result.rows[2:])
    assert missing.date is duplicate.date is None


def test_a_row_printing_no_date_takes_the_date_printed_once_above_it_in_its_table():
    # Statements that print each day's date once leave the other rows' date cells empty (scanned page: no
    # text layer, so the row above in the same printed table decides).
    first = _row("6 oct", locator="b1t0r1")
    same_day = [_row("", locator="b1t0r2"), _row(None, locator="b1t0r3")]
    result = resolve_reviewed_dates([first, *same_day], period_start="2031-10-01", period_end="2031-10-31")
    assert [row.date for row in result.rows] == ["2031-10-06"] * 3 and result.unresolved == 0
    assert [item["reason"] for item in result.evidence] == ["resolved", "date_printed_once_for_the_day",
                                                           "date_printed_once_for_the_day"]
    assert result.evidence[1]["inherited_from"] == "b1t0r1"
    # Never across a table or section (review 4), a page, from a reviewer's addition, or from an unknown date.
    other_table = _row("", locator="b2t0r1")
    next_page = replace(_row("", locator="b1t0r4"), page=4)
    added = _row("", locator="added0")
    unknown = _row("Febtober 2", locator="b1t0r5")
    after_unknown = _row("", locator="b1t0r6")
    result = resolve_reviewed_dates([first, other_table, next_page, added, unknown, after_unknown],
                                    period_start="2031-10-01", period_end="2031-10-31")
    assert [row.date for row in result.rows] == ["2031-10-06", None, None, None, None, None]


def test_on_a_text_layer_page_the_date_the_page_prints_for_the_row_decides():
    from vlm.native_text import PrintedEvidence
    page_one = PrintedEvidence(native="03/28 FABRICATED DEPOSIT 25.00 125.00\n03/31 FABRICATED FEE 1.00 124.00\n")
    page_two = PrintedEvidence(native="FABRICATED CARD 7.00 117.00\n04/02 FABRICATED PAYROLL 9.00 126.00\n"
                                      "FABRICATED CARD 3.00 123.00\n")
    rows = [replace(_row("", locator="b1t0r1"), page=2, amount=Decimal("7.00"), balance=Decimal("117.00")),
            replace(_row("04/02", locator="b1t0r2"), page=2, amount=Decimal("9.00"), balance=Decimal("126.00")),
            replace(_row("", locator="added0"), page=2, amount=Decimal("3.00"), balance=Decimal("123.00"))]
    result = resolve_reviewed_dates(rows, period_start="2031-03-01", period_end="2031-04-30",
                                    printed_pages=[page_one, page_two])
    # The top row continues the previous page's last day; the reviewer's addition is under the 04/02 line.
    assert [row.date for row in result.rows] == ["2031-03-31", "2031-04-02", "2031-04-02"]
    assert result.evidence[0]["source"] == "deterministic_text_layer_date"
    assert result.evidence[0]["printed_date_text"] == "03/31"


def test_a_row_the_text_layer_locates_but_cannot_date_takes_no_date_from_the_row_above():
    # Review 13, finding 2: "no date" from the page is a hold, never the date of the row above in the same table
    # (here a line printed k-up with no header: the date after the amount can be the next column's).
    from vlm.native_text import PrintedEvidence
    page = PrintedEvidence(native="03/06 100.00 03/09 300.00\n200.00 03/10 400.00\n")
    first = replace(_row("03/06", locator="b1t0r1"), page=1, amount=Decimal("100.00"), balance=None)
    second = replace(_row("", locator="b1t0r2"), page=1, amount=Decimal("200.00"), balance=None)
    result = resolve_reviewed_dates([first, second], period_start="2031-03-01", period_end="2031-03-31",
                                    printed_pages=[page])
    assert [row.date for row in result.rows] == ["2031-03-06", None] and result.unresolved == 1
    # Located nowhere on its page (no text layer), the row above in its table still decides.
    result = resolve_reviewed_dates([first, second], period_start="2031-03-01", period_end="2031-03-31",
                                    printed_pages=[PrintedEvidence(native=None)])
    assert [row.date for row in result.rows] == ["2031-03-06", "2031-03-06"]


def test_no_clock_baseline_or_neighbor_date_supplies_missing_year():
    explicit = _row("Jan 2", explicit="2031-01-02")
    missing = _row("Jan 3", locator="missing")
    result = resolve_reviewed_dates([explicit, missing], period_start=None, period_end=None)
    assert result.rows == (explicit, missing) and result.unresolved == 1
    assert DATE_RESOLVER_VERSION == 6


def test_a_row_of_a_table_printed_k_up_never_takes_the_date_of_the_row_above():
    # Review 5 finding 8: in reading order the row above can be the neighbouring column group's cheque.
    first = _row("6 oct", locator="b1t0r1")
    neighbour = replace(_row("", locator="b1t0r2"), side_by_side=True)
    result = resolve_reviewed_dates([first, neighbour], period_start="2031-10-01", period_end="2031-10-31")
    assert [row.date for row in result.rows] == ["2031-10-06", None] and result.unresolved == 1
