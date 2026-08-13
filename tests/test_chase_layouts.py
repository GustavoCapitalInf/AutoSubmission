"""W3 §CHASE-LAYOUTS — the layouts opened by the `Chase × no_parser_matched`
unclaimed-layout cell.

The cell's documents are filed under `Chase/`, which is a filing convention
rather than an issuer claim. Only one of its families turned out to be a
readable layout no registration owned: Square Checking, which Block, Inc.
issues and which names Chase only as the counterparty of a recurring transfer.
That coincidence is the R4-3 hazard in miniature, so it is pinned here in both
directions rather than assumed away.

Every fixture below is synthetic. No customer, account number, amount or date
from the archive appears in this file.
"""
from __future__ import annotations

import pytest

from analysis import parser_registry_entries as entries
from analysis.parser_registry import registrations, resolve
from analysis.square_checking import (
    DETECTION_MARKERS,
    activity_count_contradictions,
    detect,
    detection_text,
    parse_square_checking_statement,
)

entries.load()


HEADER = (
    "Square Checking Routing number: 000000000\n"
    "Account number: 4321\n"
    "Checking statement June 1 - June 30, 2026\n"
    "Example Trading Co\n"
    "Starting balance Activities Ending balance $100.00 3 $150.00\n"
    "Block Inc. 1955 Broadway, Suite 600 Oakland, CA 94612\n"
    "squareup.com/help\n"
)
GRID = "Date Details Activity type Balance Amount\n"
ROWS = (
    "6/1/2026 Example Merchant Card spend $80.00 -$20.00\n"
    "6/2/2026 4 Activities Sales $180.00 $100.00\n"
    "6/3/2026 Example Bank Transfer out $150.00 -$30.00\n"
)
STATEMENT = HEADER + GRID + ROWS


def _parse(text):
    statement = parse_square_checking_statement(text)
    assert statement is not None
    return statement


# --------------------------------------------------------------- detection


def test_the_layout_is_claimed_by_exactly_one_registration():
    dispatch = resolve(STATEMENT)
    assert dispatch.outcome == "claimed"
    assert dispatch.registration.id == "square_checking"
    # The ambiguity protection exercised rather than assumed.
    assert len(dispatch.candidates) == 1


@pytest.mark.parametrize("marker", [marker.id for marker in DETECTION_MARKERS])
def test_no_single_marker_is_enough_to_claim(marker):
    """The single-marker invariant, stated for this registration.

    Each required marker is removed in turn; none of the remaining three may
    carry a claim on its own.
    """
    only = {
        "issuer_product_header": "Square Checking Routing number: 000000000\n",
        "issuer_legal_footer": "Block Inc. 1955 Broadway, Suite 600 Oakland, CA\n",
        "issuer_help_domain": "squareup.com/help\n",
        "activity_grid_header": GRID,
    }[marker]
    assert not detect(only).claims


def test_a_bank_named_in_a_transaction_line_is_not_a_claim():
    """The R4-3 property, in the direction that produced this cell.

    A Chase statement that pays Square, and a Square statement that pays Chase,
    must each be claimed by their own issuer's registration and by no other.
    """
    chase_statement = (
        "JPMorgan Chase Bank, N.A. Member FDIC\n"
        "*start*summary\nCHECKING SUMMARY\n"
        "01/15 ACH DEBIT SQUARE INC SQUAREUP.COM/HELP 250.00\n"
    )
    assert not detect(chase_statement).claims

    dispatch = resolve(STATEMENT)
    assert dispatch.registration.id == "square_checking"
    assert "chase" not in dict(dispatch.candidates)


def test_the_square_layout_is_not_claimed_by_any_other_registration():
    for registration in registrations():
        if registration.id == "square_checking":
            continue
        assert not registration.detect(STATEMENT).claims, registration.id


def test_detection_does_not_read_the_source_filename():
    echoed = (
        "<!-- source: Square Checking Routing number: squareup.com/help "
        "Block Inc. Date Details Activity type Balance Amount.pdf | pages: 1 -->\n"
        "nothing else here\n"
    )
    assert not resolve(echoed).outcome == "claimed"


def test_inter_word_spacing_in_the_furniture_is_not_load_bearing():
    """A property of the text layer, not of the statement (§BMO-LAYOUTS M3.1).

    Only the gaps between words are relaxed; no money or date token is.
    """
    assert detect(STATEMENT.replace("Block Inc.", "Block   Inc.")).claims


# ------------------------------------------------------------- self-invalidation


def test_a_header_with_no_grid_is_not_a_parseable_statement():
    assert parse_square_checking_statement(HEADER) is None


def test_a_grid_with_no_summary_row_is_not_a_parseable_statement():
    without_summary = "\n".join(
        line for line in STATEMENT.splitlines() if "Starting balance Activities" not in line
    )
    assert parse_square_checking_statement(without_summary) is None


def test_a_document_this_parser_does_not_recognise_is_declined():
    assert parse_square_checking_statement("BANK OF AMERICA\nACCOUNT SUMMARY\n") is None


# ------------------------------------------------------------------ extraction


def test_the_summary_row_supplies_both_period_balances():
    statement = _parse(STATEMENT)
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 150.00
    assert statement.bank == "Square"


def test_the_period_comes_from_the_statement_title_line():
    statement = _parse(STATEMENT)
    assert statement.period_start == "2026-06-01"
    assert statement.period_end == "2026-06-30"


def test_a_period_that_opens_in_the_previous_year_is_dated_from_the_month_order():
    """Only the closing year is printed. An opening month standing after the
    closing month is the only ordering that can mean the year before."""
    text = STATEMENT.replace(
        "Checking statement June 1 - June 30, 2026",
        "Checking statement December 28 - January 27, 2026",
    ).replace("6/1/2026", "12/28/2025").replace("6/2/2026", "1/2/2026").replace(
        "6/3/2026", "1/27/2026")
    statement = _parse(text)
    assert statement.period_start == "2025-12-28"
    assert statement.period_end == "2026-01-27"
    assert len(statement.transactions) == 3


def test_the_printed_column_order_decides_which_cell_is_the_amount():
    """The grid header names it: Balance, then Amount. Reading the two cells
    the other way round would invert every row of the ledger."""
    statement = _parse(STATEMENT)
    amounts = [txn.amount for txn in statement.transactions]
    balances = [txn.running_balance for txn in statement.transactions]
    assert amounts == [-20.00, 100.00, -30.00]
    assert balances == [80.00, 180.00, 150.00]


def test_direction_is_printed_rather_than_inferred_from_the_wording():
    statement = _parse(STATEMENT)
    assert [txn.direction for txn in statement.transactions] == ["debit", "credit", "debit"]


def test_every_printed_running_balance_follows_from_the_row_above():
    statement = _parse(STATEMENT)
    running = statement.beginning_balance
    for txn in statement.transactions:
        running = round(running + txn.amount, 2)
        assert txn.running_balance == running
    assert running == statement.ending_balance


def test_the_description_is_the_text_between_the_date_and_the_money_columns():
    statement = _parse(STATEMENT)
    assert statement.transactions[0].description == "Example Merchant Card spend"
    assert statement.transactions[1].description == "4 Activities Sales"


def test_a_wrapped_details_cell_pushes_the_money_columns_onto_the_next_line():
    """A long counterparty name fills the Details column, and the Activity
    type, Balance and Amount print on the physical line below. The row is one
    row; reading the two lines separately loses it and breaks the continuity of
    the row after it."""
    text = STATEMENT.replace(
        "6/2/2026 4 Activities Sales $180.00 $100.00\n",
        "6/2/2026 Bill Pay * A Very Long Counterparty Name That Fills The Column\n"
        "Transfers $180.00 $100.00\n",
    )
    statement = _parse(text)
    assert len(statement.transactions) == 3
    row = statement.transactions[1]
    assert row.amount == 100.00
    assert row.running_balance == 180.00
    assert row.description == (
        "Bill Pay * A Very Long Counterparty Name That Fills The Column Transfers"
    )


def test_the_page_footer_under_a_row_is_not_read_as_part_of_it():
    text = STATEMENT + (
        "Block Inc. 1955 Broadway, Suite 600 Oakland, CA 94612\n"
        "squareup.com/help\n"
        "(000) 000-0000 Available 6am - 6pm PT\n"
    )
    statement = _parse(text)
    assert len(statement.transactions) == 3
    assert statement.transactions[-1].description == "Example Bank Transfer out"


def test_the_reprinted_grid_header_closes_the_row_above_it():
    """The column header opens each page's grid. It is furniture: it must not
    continue the row that ended the page before it."""
    text = HEADER + GRID + ROWS + GRID + "6/4/2026 Example Merchant Card spend $140.00 -$10.00\n"
    statement = _parse(text)
    assert len(statement.transactions) == 4
    assert statement.transactions[2].description == "Example Bank Transfer out"


def test_a_row_dated_outside_the_printed_period_is_not_admitted():
    text = STATEMENT + "7/4/2026 Example Merchant Card spend $140.00 -$10.00\n"
    statement = _parse(text)
    assert len(statement.transactions) == 3


def test_a_reference_number_in_the_details_column_is_not_a_money_cell():
    """Every money cell of this layout is printed with the currency symbol,
    which is what keeps a bare digit run out of the columns."""
    text = STATEMENT.replace(
        "6/1/2026 Example Merchant Card spend $80.00 -$20.00",
        "6/1/2026 Example Merchant SEQ# 123456 Card spend $80.00 -$20.00",
    )
    statement = _parse(text)
    assert statement.transactions[0].amount == -20.00
    assert statement.transactions[0].running_balance == 80.00
    assert "123456" in statement.transactions[0].description


def test_the_masked_account_number_keeps_only_the_digits_the_issuer_prints():
    assert _parse(STATEMENT).account_number == "4321"


# -------------------------------------------------------------- integrity check


def test_the_printed_activity_count_is_checked_against_the_ledger():
    statement = _parse(STATEMENT)
    assert activity_count_contradictions(STATEMENT, statement) == []


def test_a_ledger_that_contradicts_the_printed_activity_count_is_reported():
    text = STATEMENT.replace(
        "Starting balance Activities Ending balance $100.00 3 $150.00",
        "Starting balance Activities Ending balance $100.00 9 $150.00",
    )
    statement = _parse(text)
    assert activity_count_contradictions(text, statement) == [
        "the statement summary states a different number of activities "
        "than the activity grid lists"
    ]


def test_the_registration_carries_that_check():
    registration = next(r for r in registrations() if r.id == "square_checking")
    assert activity_count_contradictions in registration.integrity_checks


# ------------------------------------------------------------------- purity


def test_detect_is_pure_and_total():
    for document in ("", "nothing here", STATEMENT):
        assert detect(document) == detect(document)
        assert detection_text(document) == detection_text(document)


def test_parsing_preserves_the_case_the_statement_prints():
    """`detection_text` upper-cases so a producer's capitalisation cannot
    decide whether we claim; `parse` must not read through it, because the
    Details column is description text this platform publishes."""
    assert detection_text("Card spend") == "CARD SPEND"
    assert "Card spend" in _parse(STATEMENT).transactions[0].description
