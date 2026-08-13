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
from analysis.chase import detect as chase_detect, parse_chase_statement
from analysis.parser_registry import registrations, resolve
from analysis.square_checking import (
    DETECTION_MARKERS,
    activity_count_contradictions,
    detect,
    detection_text,
    parse_square_checking_statement,
)

entries.load()


#: A Chase native statement whose period ends overdrawn. Chase prints the sign
#: outside the currency symbol on both balance rows, exactly as it prints one
#: on every debit row of the same summary. Synthetic: the figures are round
#: numbers chosen so the identity is checkable by eye.
OVERDRAWN_CHASE = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance -$100.00\n"
    "Deposits and Additions 1 500.00\n"
    "Electronic Withdrawals 1 -450.00\n"
    "Ending Balance 2 -$50.00\n"
    "*end*summary\n"
    "*start*deposits and additions\n"
    "DEPOSITS AND ADDITIONS\n"
    "DATE DESCRIPTION AMOUNT\n"
    "01/05 Example Deposit Source 500.00\n"
    "Total Deposits and Additions $500.00\n"
    "*end*deposits and additions\n"
    "*start*electronic withdrawal\n"
    "ELECTRONIC WITHDRAWALS\n"
    "DATE DESCRIPTION AMOUNT\n"
    "01/09 Example Counterparty Payment -450.00\n"
    "Total Electronic Withdrawals $450.00\n"
    "*end*electronic withdrawal\n"
)


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

    Deliberately adversarial rather than trivially negative: this Chase
    statement carries THREE of `square_checking`'s four required markers —
    Square's legal entity, its help domain and its routing-number header line,
    all of them plausible on a statement that settles Square deposits — so the
    grid header alone has to carry the negative. A fixture that fired only one
    marker would assert almost nothing.
    """
    chase_statement = (
        "JPMorgan Chase Bank, N.A. Member FDIC\n"
        "*start*summary\nCHECKING SUMMARY\n"
        "01/15 ACH CREDIT SQUARE CHECKING ROUTING NUMBER: 000000000 250.00\n"
        "01/16 ACH DEBIT BLOCK INC. MERCHANT SETTLEMENT 90.00\n"
        "01/17 DISPUTE FILED VIA SQUAREUP.COM/HELP 0.00\n"
    )
    fired = [m.id for m in DETECTION_MARKERS if m.test(detection_text(chase_statement))]
    assert sorted(fired) == [
        "issuer_help_domain", "issuer_legal_footer", "issuer_product_header",
    ]
    assert not detect(chase_statement).claims

    dispatch = resolve(STATEMENT)
    assert dispatch.registration.id == "square_checking"
    assert "chase" not in dict(dispatch.candidates)


def test_a_document_carrying_both_issuers_in_full_goes_to_review_not_to_a_parse():
    """The property that holds when the negative above is defeated outright.

    A synthetic document carrying all four Square markers AND both Chase
    markers is a registry conflict, not a document either parser may read. It
    must resolve `ambiguous` — never first-wins, never a wrong parse.
    """
    collision = (
        "JPMorgan Chase Bank, N.A. Member FDIC\n*start*summary\n" + STATEMENT
    )
    dispatch = resolve(collision)
    assert dispatch.outcome == "ambiguous"
    assert {"chase", "square_checking"} <= set(dict(dispatch.candidates))
    assert dispatch.registration is None


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


def test_a_money_bearing_page_footer_is_not_absorbed_into_the_row_above_it():
    """The footer stands outside the grid, whatever it carries.

    The earlier version of this fixture used a money-free footer and so pinned
    a content assumption ("the footer carries no money") rather than the
    structural fact. A footer carrying a disclosure figure was absorbed into
    its page's last row: the row published the footer's figure as its amount
    while its running balance held the real one — one continuity break, and
    the printed Activities count still matched, so it landed at review rather
    than being refused outright. Both bounds are asserted here.
    """
    text = STATEMENT + (
        "Overdraft protection limit $500.00 applies. squareup.com/help\n"
        "Block Inc. 1955 Broadway, Suite 600 Oakland, CA 94612\n"
        "(000) 000-0000 Available 6am - 6pm PT\n"
    )
    statement = _parse(text)
    assert len(statement.transactions) == 3
    last = statement.transactions[-1]
    assert last.description == "Example Bank Transfer out"
    assert last.amount == -30.00        # the row's own figure, not the footer's
    assert last.running_balance == 150.00
    assert 500.00 not in [abs(t.amount) for t in statement.transactions]
    # and the ledger still closes on the statement's own arithmetic
    moved = round(sum(t.amount for t in statement.transactions), 2)
    assert round(statement.beginning_balance + moved, 2) == statement.ending_balance


def test_a_money_bearing_footer_under_a_wrapped_row_is_still_excluded():
    """The same, with the row's own money cells one line further down — the
    case where a rule bounded only by 'the next row' would still reach past
    the row's printing into the footer."""
    text = (
        HEADER + GRID
        + "6/1/2026 Example Merchant Card spend $80.00 -$20.00\n"
        + "6/2/2026 4 Activities Sales $180.00 $100.00\n"
        + "6/3/2026 Bill Pay * A Very Long Counterparty Name Filling The Column\n"
        + "Transfers $150.00 -$30.00\n"
        + "Overdraft protection limit $500.00 applies. squareup.com/help\n"
    )
    statement = _parse(text)
    assert len(statement.transactions) == 3
    assert statement.transactions[-1].amount == -30.00
    assert statement.transactions[-1].running_balance == 150.00


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


# ------------------------------------------- the overdrawn Chase summary (C6.1)


def test_an_overdrawn_chase_summary_is_read_with_its_sign():
    """The C6.1 capability: an overdrawn period is a balance, not a missing one.

    Before the fix the two balance rows carried their own unsigned copy of the
    money pattern, so `-$100.00` matched nothing, `_parse_native_summary`
    returned False and the whole statement went unclaimed.
    """
    statement = parse_chase_statement(OVERDRAWN_CHASE)
    assert statement is not None
    assert statement.beginning_balance == -100.00
    assert statement.ending_balance == -50.00


def test_the_overdrawn_statement_reconciles_on_its_own_arithmetic():
    """Reading the sign is only correct if the ledger then closes with it."""
    statement = parse_chase_statement(OVERDRAWN_CHASE)
    assert statement.stated_total_credits == 500.00
    assert statement.stated_total_debits == 450.00
    moved = round(sum(txn.amount for txn in statement.transactions), 2)
    assert moved == 50.00
    assert round(statement.beginning_balance + moved, 2) == statement.ending_balance


def test_the_captured_rows_reproduce_the_printed_section_totals():
    statement = parse_chase_statement(OVERDRAWN_CHASE)
    credits = round(sum(t.amount for t in statement.transactions if t.amount > 0), 2)
    debits = round(-sum(t.amount for t in statement.transactions if t.amount < 0), 2)
    assert credits == 500.00   # Total Deposits and Additions $500.00
    assert debits == 450.00    # Total Electronic Withdrawals $450.00


def test_a_positive_chase_summary_is_unchanged_by_the_sign_fix():
    """The pattern is a strict superset: on a statement that read correctly
    before, the captured balances are identical."""
    positive = (
        OVERDRAWN_CHASE
        .replace("Beginning Balance -$100.00", "Beginning Balance $100.00")
        .replace("Ending Balance 2 -$50.00", "Ending Balance 2 $150.00")
    )
    statement = parse_chase_statement(positive)
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 150.00


def test_the_sign_fix_did_not_move_chase_detection():
    """C6.1 is a parse-level fix. Detection must be exactly what R4-3 left."""
    detection = chase_detect(OVERDRAWN_CHASE)
    assert detection.claims
    assert detection.matched == ("bank_name", "section_sentinels")
    # The overdrawn balance is not detection evidence, and removing it cannot
    # change whether Chase claims its own statement.
    without = OVERDRAWN_CHASE.replace("-$100.00", "$100.00").replace("-$50.00", "$50.00")
    assert chase_detect(without).matched == detection.matched
    assert chase_detect(without).score == detection.score


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
