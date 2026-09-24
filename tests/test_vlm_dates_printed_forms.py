"""Fabricated printed date forms (resolver v6): a leading weekday, ordinals, a month name joined by dashes or
slashes, a compact day and month, dotted numbers, the year first; the numeric order a statement's own dates prove;
and a reviewer's period year that the page's text layer contradicts."""
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.dates import DATE_RESOLVER_VERSION, numeric_order, reads_as, resolve_reviewed_dates
from vlm.native_text import PrintedEvidence
from vlm.review import candidate_records, merge_review
from vlm.schema import empty_review


def _row(text, *, locator="b1t0r1", explicit=None):
    return CandidateRow(explicit, text, "FABRICATED EXACT DESCRIPTION  0001", Decimal("25.00"),
                        "credit", Decimal("125.00"), 3, "stage_a+stage_b", locator,
                        "column", (0.1, 0.2, 0.8, 0.3), Decimal("25.00"))


def test_version():
    assert DATE_RESOLVER_VERSION == 6


@pytest.mark.parametrize("text,expected", [
    ("Thu, Apr. 30, 2031", "2031-04-30"),
    ("Wednesday April 30th", "2031-04-30"),
    ("April 30th, 2031", "2031-04-30"),
    ("30th April", "2031-04-30"),
    ("30-Apr-31", "2031-04-30"),
    ("30-Apr-2031", "2031-04-30"),
    ("Apr-30", "2031-04-30"),
    ("30/Apr/2031", "2031-04-30"),
    ("30APR", "2031-04-30"),
    ("30APR31", "2031-04-30"),
    ("30apr2031", "2031-04-30"),
    ("04.30.31", "2031-04-30"),
    ("30.04.2031", "2031-04-30"),
    ("2031/04/30", "2031-04-30"),
    ("2031.04.30", "2031-04-30"),
])
def test_printed_forms_resolve_inside_the_period(text, expected):
    result = resolve_reviewed_dates([_row(text)], period_start="2031-04-01", period_end="2031-04-30")
    assert result.unresolved == 0 and result.rows[0].date == expected


@pytest.mark.parametrize("text", [
    "Thu, Apr. 31, 2031", "30-Apx-31", "30APR30", "31APR", "04.31.31", "2031/04/31", "Sat 2031",
    "Apr 30 FABRICATED", "30.04.31.2031", "30-04/2031",
])
def test_malformed_or_out_of_period_forms_stay_unresolved(text):
    result = resolve_reviewed_dates([_row(text)], period_start="2031-04-01", period_end="2031-04-30")
    assert result.unresolved == 1 and result.rows[0].date is None


def test_a_month_in_us_dollars_reads_numeric_dates_month_first():
    rows = [_row("05/06")]
    dollars = resolve_reviewed_dates(rows, period_start="2031-05-01", period_end="2031-05-31", month_first=True)
    assert dollars.rows[0].date == "2031-05-06"
    assert (dollars.numeric_order, dollars.numeric_order_source) == ("month_first", "statement_currency")


def test_a_longer_period_needs_the_order_proven_by_the_statement_itself():
    # A quarter: "05/06" is May 6 or June 5; US dollars alone do not decide it (review 7, finding 3).
    rows = [_row("05/06")]
    neutral = resolve_reviewed_dates(rows, period_start="2031-04-01", period_end="2031-06-30", month_first=True)
    assert neutral.unresolved == 1 and neutral.evidence[0]["candidate_dates"] == ["2031-05-06", "2031-06-05"]
    assert neutral.numeric_order is None
    # The page's text layer printing its period month first proves the order.
    printed = [PrintedEvidence(native="Statement period 04/01/2031 - 06/30/2031\n05/06 FABRICATED DEPOSIT 25.00")]
    proven = resolve_reviewed_dates([replace_page(rows[0], 1)], period_start="2031-04-01", period_end="2031-06-30",
                                    printed_pages=printed, month_first=True)
    assert proven.rows[0].date == "2031-05-06" and proven.numeric_order_source == "printed_dates"
    # An annual statement printing quarterly dividends day first stays unresolved rather than misdated.
    dividends = [_row(text, locator=f"b1t0r{index}") for index, text in enumerate(("01/03", "01/06", "01/09", "01/12"))]
    annual = resolve_reviewed_dates(dividends, period_start="2031-01-01", period_end="2031-12-31", month_first=True)
    assert annual.unresolved == 4 and all(row.date is None for row in annual.rows)


def test_a_year_less_print_in_the_text_layer_proves_no_order():
    # Review 8, finding 1: "24/7" on an annual US-dollar statement proved day-first and misdated every row.
    rows = [replace_page(_row(f"{month:02d}/01", locator=f"b1t0r{month}"), 1) for month in range(2, 13)]
    helpline = [PrintedEvidence(native="We are here for you 24/7 at 1-800-555-0100\n02/01 FABRICATED INTEREST 25.00")]
    result = resolve_reviewed_dates(rows, period_start="2031-01-01", period_end="2031-12-31", printed_pages=helpline,
                                    month_first=True)
    assert result.numeric_order is None and result.unresolved == len(rows)
    # A date printing its year proves the order.
    period = [PrintedEvidence(native="Statement period 01/01/2031 - 12/31/2031\nWe are here for you 24/7")]
    result = resolve_reviewed_dates(rows, period_start="2031-01-01", period_end="2031-12-31", printed_pages=period,
                                    month_first=True)
    assert result.numeric_order == "month_first" and result.unresolved == 0
    assert result.rows[0].date == "2031-02-01"


def test_a_month_name_date_printing_a_two_digit_year_vouches_for_its_year():
    # Review 8, finding 10.
    printed = PrintedEvidence(native="Statement date 01-MAR-31\nAccount opened 03/01/2020")
    assert printed.date_contradicted("2031-03-01") is False and printed.date_contradicted("2021-03-01") is True


def replace_page(row, page):
    from dataclasses import replace
    return replace(row, page=page)


def test_the_statements_own_dates_prove_the_order():
    # "13/05" can only be May 13: the statement prints day first, whatever its currency.
    rows = [_row("05/06"), _row("13/05", locator="b1t0r2")]
    result = resolve_reviewed_dates(rows, period_start="2031-04-01", period_end="2031-06-30", month_first=True)
    assert [row.date for row in result.rows] == ["2031-06-05", "2031-05-13"]
    assert (result.numeric_order, result.numeric_order_source) == ("day_first", "printed_dates")
    # "05/13" can only be May 13: month first, proven without any currency.
    rows = [_row("05/06"), _row("05/13", locator="b1t0r2")]
    result = resolve_reviewed_dates(rows, period_start="2031-04-01", period_end="2031-06-30")
    assert [row.date for row in result.rows] == ["2031-05-06", "2031-05-13"]
    assert (result.numeric_order, result.numeric_order_source) == ("month_first", "printed_dates")
    # A date with a year proves the order just the same; an explicit row's printed text counts too.
    rows = [_row("05/06"), _row("20/05/2031", locator="b1t0r2", explicit="2031-05-20")]
    result = resolve_reviewed_dates(rows, period_start="2031-04-01", period_end="2031-06-30", month_first=True)
    assert result.rows[0].date == "2031-06-05"


def test_dates_proving_both_orders_leave_ambiguous_dates_ambiguous():
    rows = [_row("05/06"), _row("13/05", locator="b1t0r2"), _row("05/14", locator="b1t0r3")]
    assert numeric_order(row.date_text for row in rows) == "conflicting"
    result = resolve_reviewed_dates(rows, period_start="2031-04-01", period_end="2031-06-30", month_first=True)
    assert result.rows[0].date is None and result.numeric_order is None
    assert [row.date for row in result.rows[1:]] == ["2031-05-13", "2031-05-14"]


def test_two_dotted_numbers_without_a_year_prove_nothing():
    # "25.10" can be an amount read into a date cell.
    assert numeric_order(["25.10"]) is None and numeric_order(["25.10.31"]) == "day_first"
    assert numeric_order(["04/05", "Apr 30", None, "", "2031-04-30"]) is None


def test_a_printed_date_can_mean_only_its_own_readings():
    assert reads_as("Thu, Apr. 30, 2031", "2031-04-30") and not reads_as("Thu, Apr. 30, 2031", "2030-04-30")
    assert reads_as("05/06", "2031-05-06") and reads_as("05/06", "2031-06-05")
    assert reads_as("30APR31", "2031-04-30") and not reads_as("30APR31", "2032-04-30")


NATIVE = """FABRICATED NATIONAL BANK
Statement period: March 1, 2031 through March 31, 2031
Beginning balance 1,000.00   Ending balance 3,500.00
03/02 FABRICATED DEPOSIT 2,500.00
"""


def test_the_text_layer_contradicts_a_misread_period_year():
    printed = PrintedEvidence(native=NATIVE)
    assert printed.date_contradicted("2021-03-01") is True and printed.date_contradicted("2021-03-31") is True
    assert printed.date_contradicted("2031-03-01") is False and printed.date_contradicted("2031-03-31") is False
    # A date the page never prints in any year: absence proves nothing.
    assert printed.date_contradicted("2021-04-30") is False
    # A row dated the same day without a year ("03/02 ...") vouches for no year (review 7, finding 4).
    assert printed.date_contradicted("2021-03-02") is False
    with_row = PrintedEvidence(native=NATIVE + "03/01 FABRICATED FEE 5.00\n")
    assert with_row.date_contradicted("2021-03-01") is True and with_row.date_contradicted("2031-03-01") is False
    # Numeric prints with a year contradict just the same; no text layer, no judgement.
    assert PrintedEvidence(native="Period 03/01/2031 - 03/31/2031").date_contradicted("2021-03-31") is True
    assert PrintedEvidence(native="Period 03/01/31 - 03/31/31").date_contradicted("2021-03-31") is True
    assert PrintedEvidence(native=None, proposer=NATIVE).date_contradicted("2021-03-01") is None
    # The same day printed in two years (a year-to-date column): a reading of the right year always wins.
    both = PrintedEvidence(native="Year to date since March 1, 2030\nStatement period March 1, 2031")
    assert both.date_contradicted("2031-03-01") is False and both.date_contradicted("2030-03-01") is False
    assert both.date_contradicted("2029-03-01") is True
    # A word that merely contains a month name is not a date.
    assert PrintedEvidence(native="Summary 1, 2030").date_contradicted("2031-03-01") is False


def test_the_reviewer_period_date_the_text_layer_contradicts_is_dropped():
    row = CandidateRow("2031-03-02", "03/02", "FABRICATED DEPOSIT", Decimal("2500.00"), "credit", None, 1,
                       "stage_a", "b1t0r0", "column", (0.1, 0.2, 0.9, 0.3), Decimal("2500.00"))
    payload = empty_review("statement_page")
    payload["reviews"] = [{"candidate_id": record["candidate_id"], "verdict": "confirm",
                           "observed_description": record["row"]["description"], "corrections": [], "reason": ""}
                          for record in candidate_records([row])]
    payload["account"].update(period_start="2021-03-01", period_end="2031-03-31")
    merged = merge_review([row], payload, page=1, printed=PrintedEvidence(native=NATIVE))
    assert merged.account["period_start"] is None and merged.account["period_end"] == "2031-03-31"
    assert {"scope": "account", "page": 1, "field": "period_start",
            "code": "review_figure_not_printed"} in merged.diagnostics
