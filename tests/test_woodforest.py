"""The Woodforest National Bank layout.

Every fixture is a printed shape taken from the archive family, reduced to the
smallest document that still exercises it. The subject of most of them is the
one thing this layout makes hard: the Credits and Debits columns are adjacent
and the text layer destroys which of the two a magnitude stood in, so
direction comes from the running balance the bank prints beside it.
"""
from __future__ import annotations

from analysis.adb import compute_average_daily_balance
from analysis.woodforest import (
    detect,
    initialization_postings,
    parse_woodforest_statement,
)

HEADER = (
    "00131374040126102556\n"
    "Statement Period: March 01  - March 31, 2026 Page 1 of 6\n"
    "Account Information & Customer Service 1-(877) 968-7962\n"
    "P.O. Box 7889 The Woodlands, TX 77387\n"
    "Visit Us Online at www.woodforest.com\n"
    "Summary of Accounts\n"
    "ACCOUNT TYPE AND NUMBER BALANCE FORWARD TOTAL DEBITS TOTAL CREDITS CLOSING BALANCE\n"
)
GRID = "Transactions\nDate Credits Debits Balance Description\n"


def document(summary_row: str, rows: str) -> str:
    return HEADER + summary_row + "\n" + "Business Simple Checking 1205009515\n" + GRID + rows + "\n"


SIMPLE = document(
    "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00",
    "03-02 200.00 800.00 POS DB ONE 03-03 500.00 1,300.00 POS CR TWO "
    "03-04 100.00 1,200.00 POS DB THREE",
)


# --------------------------------------------------------------- detection


def test_detection_claims_the_woodforest_statement():
    assert detect(SIMPLE).claims


def test_detection_needs_more_than_the_bank_word():
    """Another issuer's statement can name Woodforest in a payee line. Several
    in the archive do; neither printed column header appears on any of them."""
    other = (
        "CHASE\nStatement Period: March 01  - March 31, 2026 Page 1 of 6\n"
        "03-02 200.00 800.00 ACH DEBIT WOODFOREST NATIONAL BANK TRANSFER\n"
    )
    assert not detect(other).claims


def test_detection_needs_the_activity_header_too():
    """The summary block alone is not the statement: without the posting grid
    there is no ledger to publish."""
    assert not detect(HEADER + "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00\n").claims


# ------------------------------------------------------- the summary oracle


def test_the_summary_row_is_the_periods_arithmetic():
    stmt = parse_woodforest_statement(SIMPLE)
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_total_credits == 500.00
    assert stmt.account_number == "1205009515"
    assert stmt.account_name == "Business Simple Checking"
    assert stmt.bank == "Woodforest National Bank"
    assert stmt.currency == "USD"


def test_neither_total_prints_a_count_so_neither_count_is_claimed():
    """Deriving the counts from the ledger would manufacture the oracle the
    platform checks the ledger against."""
    stmt = parse_woodforest_statement(SIMPLE)
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_an_overdrawn_balance_forward_keeps_its_minus():
    stmt = parse_woodforest_statement(
        document(
            "Woodforest Checking 1099068957 -92.32 100.00 500.00 307.68",
            "03-02 500.00 407.68 ACH CREDIT 03-03 100.00 307.68 POS DB ONE",
        )
    )
    assert stmt.beginning_balance == -92.32
    assert stmt.transactions[0].amount == 500.00


# ------------------------------------------------- direction from the balance


def test_direction_comes_from_the_printed_running_balance():
    """The magnitude is the bank's printed cell; only the movement between two
    printed balances says which column it stood in."""
    stmt = parse_woodforest_statement(SIMPLE)
    assert [t.amount for t in stmt.transactions] == [-200.00, 500.00, -100.00]
    assert [t.direction for t in stmt.transactions] == ["debit", "credit", "debit"]
    assert [t.running_balance for t in stmt.transactions] == [800.00, 1300.00, 1200.00]


def test_the_walk_is_seeded_from_balance_forward():
    """This layout prints no opening row inside the grid, so the first row's
    direction is only knowable from the summary's BALANCE FORWARD."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 0.00 0.00 1,000.00 1,000.00",
            "01-23 1,000.00 1,000.00 OPENING DEPOSIT",
        )
    )
    assert stmt.transactions[0].amount == 1000.00
    assert stmt.transactions[0].direction == "credit"


def test_a_magnitude_that_contradicts_the_balance_movement_is_not_corrected():
    """Disagreement withholds: the row keeps a debit reading and the document
    then fails the platform's ledger checks. The sign is never invented to make
    the arithmetic close."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 0.00 0.00 1,000.00",
            "03-02 250.00 9,999.99 POS DB CONTRADICTS",
        )
    )
    assert stmt.transactions[0].amount == -250.00


# ------------------------------------------------------------- the row reader


def test_a_date_inside_a_description_does_not_open_a_row():
    """A row opens only where the grid prints one: a date followed by its
    amount cell AND its balance cell. A description does not print two money
    cells in that order."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 200.00 0.00 800.00",
            "03-02 200.00 800.00 POS DB INVOICE 03-04 REF 000000001014568",
        )
    )
    assert len(stmt.transactions) == 1
    assert stmt.transactions[0].description == "POS DB INVOICE 03-04 REF 000000001014568"


def test_the_grid_stops_at_the_blocks_printed_after_it():
    """`Account Summary` and the daily balance table are not postings."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 200.00 0.00 800.00",
            "03-02 200.00 800.00 POS DB ONE\n"
            "Account Summary\n"
            "Average Balance $900.00 Number of Days in Cycle 31\n"
            "Daily Closing Balance Summary\n"
            "Date Balance\n03-02 800.00 03-03 800.00\n",
        )
    )
    assert len(stmt.transactions) == 1
    assert stmt.days_in_period == 31
    assert stmt.stated_average_balance == 900.00


def test_a_posting_may_fall_a_day_outside_the_printed_period():
    """A mid-cycle account opening posts its first deposit the day before the
    stated period starts, and the bank's own totals include it. The year is
    resolved to the period it is NEAREST to rather than required to be inside
    it, so the row is read as printed."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 0.00 0.00 1,000.00 1,000.00",
            "01-23 1,000.00 1,000.00 OPENING DEPOSIT",
        ).replace(
            "Statement Period: March 01  - March 31, 2026",
            "Statement Period: January 24  - January 31, 2026",
        )
    )
    assert stmt.transactions[0].date == "2026-01-23"


def test_a_period_that_crosses_the_year_boundary_dates_both_months():
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 300.00 0.00 700.00",
            "12-28 100.00 900.00 POS DB ONE 01-03 200.00 700.00 POS DB TWO",
        ).replace(
            "Statement Period: March 01  - March 31, 2026",
            "Statement Period: December 25  - January 24, 2026",
        )
    )
    assert [t.date for t in stmt.transactions] == ["2025-12-28", "2026-01-03"]


# ------------------------------------------------------------- failing closed


def test_a_multi_account_document_fails_closed():
    """The single-account extraction schema cannot carry two ledgers, so the
    document is declined rather than published under one account's name."""
    text = document(
        "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00\n"
        "Business Simple Checking 1205009999 2,000.00 100.00 100.00 2,000.00",
        "03-02 200.00 800.00 POS DB ONE",
    )
    assert detect(text).claims
    assert parse_woodforest_statement(text) is None


def test_a_second_account_split_by_a_page_break_still_fails_closed():
    """The L-1 guard must not fail OPEN.

    A summary block whose rows straddle a page break prints the page marker
    and the page's own header between them. A reader that stopped collecting
    at the first non-matching line would see one account on a two-account
    document and publish it — the exact inversion of what this guard is for.
    """
    text = (
        HEADER
        + "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00\n"
        + "--- Page 2 ---\n"
        + "Statement Period: March 01  - March 31, 2026 Page 2 of 6\n"
        + "Business Simple Checking 1205009999 2,000.00 100.00 100.00 2,000.00\n"
        + "Business Simple Checking 1205009515\n"
        + GRID
        + "03-02 200.00 800.00 POS DB ONE\n"
    )
    assert detect(text).claims
    assert parse_woodforest_statement(text) is None


def test_the_summary_region_ends_where_the_document_closes_it():
    """Collecting across the region must not run past it: the account section
    that follows prints the same product name and number, and the postings
    below it print money of their own."""
    stmt = parse_woodforest_statement(SIMPLE)
    assert stmt is not None
    assert stmt.account_number == "1205009515"


def test_a_grid_whose_columns_arrive_out_of_order_fails_closed():
    """Three archive documents emit the cells of each row in a scrambled
    reading order — description, balance, date, amount — which cannot be
    reassembled from the linear text stream. No row matches the printed
    column order, so nothing is published."""
    text = document(
        "Second Chance Checking 1358422002 119,237.77 2,954.03 49,025.50 165,309.24",
        "POS CR CASH APP RICHARD SMITH\n120,237.77\n03-04\n1,000.00\n"
        "POS CR CASH APP RICHARD SMITH\n121,478.27\n03-04\n1,240.50\n",
    )
    assert detect(text).claims
    assert parse_woodforest_statement(text) is None


def test_a_document_with_no_summary_row_fails_closed():
    text = HEADER + GRID + "03-02 200.00 800.00 POS DB ONE\n"
    assert parse_woodforest_statement(text) is None


# ------------------------------------- the account-opening initialization event
#
# Two archive statements (`c183e584_Feb`, `fad3db75_document`) are mid-cycle
# account openings: BALANCE FORWARD is 0.00 and the funding deposit posts the
# day BEFORE the period the bank prints, while the bank's own TOTAL CREDITS
# counts it and its own daily balance table prints a closing balance for that
# day. Every printed figure on both matches the published ledger; the ADB
# engine refuses them because it requires every transaction to fall inside the
# period. `initialization_postings` is the EVIDENCE half of the narrow
# exception — it proves the interpretation from the document's own print and
# publishes nothing. See §WFINIT in `W3_TRACKA_LOG.md`.

OPENING_PERIOD = "Statement Period: January 24  - January 31, 2026"


def opening_document(
    summary_row: str,
    rows: str,
    *,
    average: str | None = "966.11",
    cycle_days: str = "8",
    daily: str = "01-23 1,000.00 01-24 985.00 01-31 800.00",
    period: str = OPENING_PERIOD,
) -> str:
    """A mid-cycle opening, reduced to the blocks the evidence rests on."""
    printed_average = (
        f"Average Balance ${average} Average Collected Balance ${average} "
        if average is not None
        else ""
    )
    return (
        document(summary_row, rows).replace(
            "Statement Period: March 01  - March 31, 2026", period
        )
        + "Account Summary\n"
        + printed_average
        + f"Number of Days in Cycle {cycle_days}\n"
        + "Daily Closing Balance Summary\n"
        + "Date Balance\n"
        + daily
        + "\nACCOUNT RECONCILIATION\n"
    )


OPENING_SUMMARY = "Business Simple Checking 1205009515 0.00 200.00 1,000.00 800.00"
OPENING_ROWS = (
    "01-23 1,000.00 1,000.00 "
    "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
    "01-31 185.00 800.00 POS DB ONE"
)
OPENING = opening_document(OPENING_SUMMARY, OPENING_ROWS)


def test_the_opening_deposit_is_proven_by_the_documents_own_print():
    stmt = parse_woodforest_statement(OPENING)
    proven = initialization_postings(OPENING, stmt)
    assert [(t.date, t.amount) for t in proven] == [("2026-01-23", 1000.00)]


def test_the_row_prints_no_description_and_is_proven_anyway():
    """`fad3db75_document`'s opening row prints a date, an amount and a
    balance and NOTHING else — there is no 'opening deposit' wording to key
    on, which is why the evidence is the arithmetic the bank prints around
    it rather than the words it does not."""
    stmt = parse_woodforest_statement(OPENING)
    assert stmt.transactions[0].description == ""


def test_proving_the_event_changes_nothing_the_parser_publishes():
    """The prover is deliberately not wired: `analysis/adb.py` is protected,
    so until Ocean rules the two documents stay withheld. Pinned so a wiring
    change cannot land silently."""
    stmt = parse_woodforest_statement(OPENING)
    assert stmt.period_start == "2026-01-24"
    assert stmt.beginning_balance == 0.00
    assert stmt.transactions[0].date == "2026-01-23"
    result = compute_average_daily_balance(stmt)
    assert result.ok is False
    assert result.validations["transactions_within_period"] is False
    assert result.out_of_period_transaction_count == 1


def test_a_document_with_no_out_of_period_row_proves_nothing():
    assert initialization_postings(SIMPLE, parse_woodforest_statement(SIMPLE)) == []


# --- the seven conditions, each killed on its own ---------------------------


def test_a_non_zero_balance_forward_is_not_an_account_opening():
    """G1. An account that carried a balance into the period already existed,
    so nothing it posted before the period is initial funding."""
    text = opening_document(
        "Business Simple Checking 1205009515 100.00 200.00 1,000.00 900.00",
        "01-23 1,000.00 1,100.00 "
        "01-24 15.00 1,085.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 900.00 POS DB ONE",
        daily="01-23 1,100.00 01-24 1,085.00 01-31 900.00",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_a_row_two_days_before_the_period_is_not_an_opening():
    """G2. `immediately before` is the day before, not a window."""
    text = opening_document(
        OPENING_SUMMARY,
        "01-22 1,000.00 1,000.00 "
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 800.00 POS DB ONE",
        daily="01-22 1,000.00 01-24 985.00 01-31 800.00",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_a_row_after_the_period_is_never_an_opening():
    """G2, the adversarial half. A stray row dated outside the period that is
    NOT the initialization event must leave the document withheld — including
    when a genuine opening deposit sits beside it."""
    text = opening_document(
        "Business Simple Checking 1205009515 0.00 250.00 1,000.00 750.00",
        "01-23 1,000.00 1,000.00 "
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 800.00 POS DB ONE "
        "02-03 50.00 750.00 POS DB STRAY",
        daily="01-23 1,000.00 01-24 985.00 01-31 800.00",
    )
    stmt = parse_woodforest_statement(text)
    assert stmt.transactions[-1].date == "2026-02-03"
    assert initialization_postings(text, stmt) == []


def test_an_opening_row_that_is_not_the_leading_row_is_refused():
    """G3. The account's balance history has to BEGIN with the event."""
    text = opening_document(
        OPENING_SUMMARY,
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-23 1,000.00 1,000.00 "
        "01-31 185.00 800.00 POS DB ONE",
        daily="01-23 1,000.00 01-24 985.00 01-31 800.00",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_the_walk_from_balance_forward_must_reproduce_the_printed_balance():
    """G3. The printed balance beside the row is the bank's own check on it."""
    text = opening_document(
        OPENING_SUMMARY,
        "01-23 1,000.00 1,001.00 "
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 800.00 POS DB ONE",
        daily="01-23 1,001.00 01-24 985.00 01-31 800.00",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_an_event_the_ledger_does_not_need_is_refused():
    """G4, first half. The printed ledger must CLOSE with the event. Here the
    bank's own totals exclude the pre-period deposit, so a document claiming it
    as the opening would not reach the printed closing balance."""
    text = opening_document(
        "Business Simple Checking 1205009515 0.00 200.00 0.00 -200.00",
        "01-23 1,000.00 1,000.00 "
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 800.00 POS DB ONE",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_a_pre_period_row_that_moves_nothing_is_not_an_opening():
    """G4, second half. A pre-period row that nets to zero leaves the ledger
    closing exactly as it would without it, so it establishes no opening
    balance and cannot be initial funding — the one shape where 'the ledger
    does not close without it' is the condition that does the refusing."""
    text = opening_document(
        "Business Simple Checking 1205009515 0.00 200.00 0.00 -200.00",
        "01-23 0.00 0.00 "
        "01-24 15.00 -15.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 -200.00 POS DB ONE",
        daily="01-23 0.00 01-24 -15.00 01-31 -200.00",
    )
    stmt = parse_woodforest_statement(text)
    assert stmt.transactions[0].date == "2026-01-23"
    assert initialization_postings(text, stmt) == []


def test_the_daily_balance_summary_must_print_the_opening_day():
    """G5. The bank's independent statement that the day is this account's."""
    text = opening_document(
        OPENING_SUMMARY, OPENING_ROWS, daily="01-24 985.00 01-31 800.00"
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_the_printed_cycle_length_must_be_the_printed_period():
    """G6. If the bank's own day count does not match the period we read, the
    period is not established and nothing may be measured against it."""
    text = opening_document(OPENING_SUMMARY, OPENING_ROWS, cycle_days="9")
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_the_printed_average_must_confirm_the_opening_window():
    """G7. `961.88` is the mean over the printed period once the deposit is
    folded into the opening balance — the answer a reader gets when the
    opening day is NOT part of the account's balance history. The bank prints
    the nine-day figure instead, and that is what makes the extra day the
    bank's own claim rather than ours."""
    text = opening_document(OPENING_SUMMARY, OPENING_ROWS, average="961.88")
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_the_printed_average_pins_the_opening_amount():
    """G7 as a mutation test. Every figure on this document is internally
    consistent for a 2,000.00 opening — the summary identity, the walk, the
    daily table and the closing balance all agree — and the ONE printed figure
    that did not move refuses it."""
    text = opening_document(
        "Business Simple Checking 1205009515 0.00 200.00 2,000.00 1,800.00",
        "01-23 2,000.00 2,000.00 "
        "01-24 15.00 1,985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 1,800.00 POS DB ONE",
        daily="01-23 2,000.00 01-24 1,985.00 01-31 1,800.00",
    )
    stmt = parse_woodforest_statement(text)
    assert stmt.transactions[0].amount == 2000.00
    assert initialization_postings(text, stmt) == []


def test_a_document_that_prints_no_average_proves_nothing():
    """G7. Every other condition holds and the one independent oracle is
    absent, so the exception is unreachable: no oracle, no exception."""
    text = opening_document(OPENING_SUMMARY, OPENING_ROWS, average=None)
    stmt = parse_woodforest_statement(text)
    assert stmt.stated_average_balance is None
    assert initialization_postings(text, stmt) == []
