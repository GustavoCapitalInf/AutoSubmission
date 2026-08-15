"""The Woodforest National Bank layout.

Every fixture is a printed shape taken from the archive family, reduced to the
smallest document that still exercises it. The subject of most of them is the
one thing this layout makes hard: the Credits and Debits columns are adjacent
and the text layer destroys which of the two a magnitude stood in, so
direction comes from the running balance the bank prints beside it.
"""
from __future__ import annotations

from datetime import date, timedelta

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


def printed_average(text: str) -> str:
    """What Woodforest itself would print as `Average Balance` here.

    The family divides by (cycle days + 1) on a zero-forward statement,
    counting the day before the period — see G8 in `initialization_postings`.

    Fixtures use this so that a document built to break exactly ONE condition
    stays internally consistent in every other respect. Without it the printed
    average stops matching the mutated ledger, G8b refuses first, and the
    condition actually under test is never reached — which is precisely how an
    earlier version of this file came to have thirteen refusal fixtures of
    which only three pinned anything.
    """
    stmt = parse_woodforest_statement(text)
    assert stmt is not None, "fixture does not parse"
    probe = stmt.model_copy(deep=True)
    year, month, day = (int(part) for part in stmt.period_start.split("-"))
    probe.period_start = (date(year, month, day) - timedelta(days=1)).isoformat()
    value = compute_average_daily_balance(probe).average_daily_balance
    assert value is not None, "fixture has no computable average"
    return f"{value:,.2f}"


def consistent_document(summary_row: str, rows: str, **kwargs) -> str:
    """`opening_document` carrying the average the bank would have printed."""
    draft = opening_document(summary_row, rows, average="0.00", **kwargs)
    return opening_document(
        summary_row, rows, average=printed_average(draft), **kwargs
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


# --- what DISCRIMINATES an opening: each condition pinned on its own --------
#
# Every fixture in this block carries, via `consistent_document`, the average
# the bank would itself print for the document AS MUTATED. That is what makes
# the named condition the only one that can refuse — and it is verified rather
# than asserted: deleting the named guard from `initialization_postings` turns
# that fixture red on its own.


def test_a_non_zero_balance_forward_is_not_an_account_opening():
    """G1. An account that carried a balance into the period already existed,
    so nothing it posted before the period is initial funding."""
    text = consistent_document(
        "Business Simple Checking 1205009515 100.00 200.00 1,000.00 900.00",
        "01-23 1,000.00 1,100.00 "
        "01-24 15.00 1,085.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 900.00 POS DB ONE",
        daily="01-23 1,100.00 01-24 1,085.00 01-31 900.00",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_a_debit_dated_the_day_before_is_not_an_account_opening():
    """G3, and the reason G3 exists.

    An NSF charge posted the day before a zero-forward statement satisfies
    every other condition here: the forward is zero, the row is dated the day
    immediately before, it leads the grid, its walk reproduces the printed
    balance, the bank's daily table prints that day, the cycle length matches,
    the ledger closes with it and not without it, and the bank's own printed
    average is reproduced exactly over the n+1 window. Without G3 this
    publishes — an opening balance of -50.00, an ADB computed on top of it,
    and the whole thing described as an account opening.

    An account is opened by money ARRIVING.
    """
    text = consistent_document(
        "Business Simple Checking 1205009515 0.00 200.00 1,000.00 800.00",
        "01-23 50.00 -50.00 NSF CHARGE "
        "01-24 1,000.00 950.00 DEPOSIT "
        "01-31 150.00 800.00 POS DB ONE",
        daily="01-23 -50.00 01-24 950.00 01-31 800.00",
    )
    stmt = parse_woodforest_statement(text)
    row = stmt.transactions[0]
    assert (row.date, row.amount, row.direction) == ("2026-01-23", -50.00, "debit")
    assert initialization_postings(text, stmt) == []


def test_a_debit_beside_the_opening_deposit_is_still_refused():
    """G3's direction half, isolated.

    Two postings on the day before: the funding deposit AND a 50.00 charge.
    The carry they leave is +950.00, so the "opening balance must be positive"
    half of G3 is satisfied and only the "every declared posting is a credit"
    half can refuse.

    Refusing is the fail-closed reading and it is deliberate. The deposit is
    initial funding; the charge is not, and nothing printed here proves the
    charge belongs to the opening rather than being ordinary activity the bank
    happened to post early. A rule that admits "the opening deposit and
    whatever else shares its date" is a wider rule than the one that was
    approved.
    """
    text = consistent_document(
        "Business Simple Checking 1205009515 0.00 250.00 1,000.00 750.00",
        "01-23 1,000.00 1,000.00 DEPOSIT "
        "01-23 50.00 950.00 NSF CHARGE "
        "01-24 15.00 935.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 750.00 POS DB ONE",
        daily="01-23 950.00 01-24 935.00 01-31 750.00",
    )
    stmt = parse_woodforest_statement(text)
    assert [t.amount for t in stmt.transactions[:2]] == [1000.00, -50.00]
    assert initialization_postings(text, stmt) == []


def test_the_daily_balance_summary_must_print_the_opening_day():
    """G6. The bank's independent statement that the day is this account's."""
    text = consistent_document(
        OPENING_SUMMARY, OPENING_ROWS, daily="01-24 985.00 01-31 800.00"
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_the_printed_cycle_length_must_be_the_printed_period():
    """G7. If the bank's own day count does not match the period we read, the
    period is not established and nothing may be measured against it."""
    text = consistent_document(OPENING_SUMMARY, OPENING_ROWS, cycle_days="9")
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_the_printed_average_must_confirm_the_read():
    """G8b. `961.88` is the mean over the printed period once the deposit is
    folded into the opening balance — the answer a reader gets when the
    opening day is not counted. Woodforest prints the nine-day figure.

    Note what this does and does not prove: it confirms the READ, not the
    interpretation. See G8 in `initialization_postings` — the same n+1
    identity holds on a zero-forward statement with no pre-period row at all.
    """
    text = opening_document(OPENING_SUMMARY, OPENING_ROWS, average="961.88")
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_the_printed_average_pins_the_opening_amount():
    """G8b as a mutation test. Every figure on this document is internally
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
    """G8b. No oracle, no exception."""
    text = opening_document(OPENING_SUMMARY, OPENING_ROWS, average=None)
    stmt = parse_woodforest_statement(text)
    assert stmt.stated_average_balance is None
    assert initialization_postings(text, stmt) == []


# --- defence in depth: refusals another condition also catches --------------
#
# These documents are refused, and each names the condition it is aimed at —
# but deleting that condition alone leaves the suite green, because a stronger
# one catches the same document. They are kept because they are the shapes a
# reader will ask about, and they are labelled honestly rather than counted as
# independent evidence. The subsumption is reasoned in `initialization_postings`.


def test_a_row_two_days_before_the_period_is_not_an_opening():
    """G2 (also caught by G8a: the probe window starts at period_start - 1, so
    a start-2 posting fails the probe's own `transactions_within_period`)."""
    text = opening_document(
        OPENING_SUMMARY,
        "01-22 1,000.00 1,000.00 "
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 800.00 POS DB ONE",
        daily="01-22 1,000.00 01-24 985.00 01-31 800.00",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_a_row_after_the_period_is_never_an_opening():
    """G2, the adversarial half of the ruling's gate 6: a stray row dated
    outside the period that is NOT the initialization event must leave the
    document withheld, even with a genuine opening deposit beside it.
    (Also caught by G8a.)"""
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
    """G5 (also caught by G4a: this parser derives each amount from the
    balance movement, so out-of-order rows break the ledger as well)."""
    text = opening_document(
        OPENING_SUMMARY,
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-23 1,000.00 1,000.00 "
        "01-31 185.00 800.00 POS DB ONE",
        daily="01-23 1,000.00 01-24 985.00 01-31 800.00",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_an_event_the_ledger_does_not_need_is_refused():
    """G4a (which IS the probe's `ledger_reconciles_to_closing`, so G8a catches
    it too). The bank's own totals here exclude the pre-period deposit, so a
    document claiming it as the opening would not reach the printed closing
    balance."""
    text = opening_document(
        "Business Simple Checking 1205009515 0.00 200.00 0.00 -200.00",
        "01-23 1,000.00 1,000.00 "
        "01-24 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 800.00 POS DB ONE",
    )
    assert initialization_postings(text, parse_woodforest_statement(text)) == []


def test_a_pre_period_row_that_moves_nothing_is_not_an_opening():
    """G4b (now subsumed by G3: with a zero forward and a positive opening
    carry, `forward + in-period` cannot equal the closing balance that
    `carry + in-period` equals). A pre-period row netting to zero establishes
    no opening balance, and is refused either way."""
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


def test_a_zero_forward_statement_with_no_pre_period_row_proves_nothing():
    """The shape that disproves the old story about G8.

    `E0A4A5DB` in the archive is exactly this: `BALANCE FORWARD` 0.00, a
    mid-cycle period, and NO out-of-period row — and the bank's printed
    average is still reproduced exactly over `[period_start - 1 .. period_end]`
    with a phantom 0.00 day, because that n+1 divisor is the family's
    convention on zero-forward statements rather than a signature of an
    opening. There is nothing to declare here and nothing is declared.
    """
    text = consistent_document(
        "Business Simple Checking 1205009515 0.00 200.00 1,000.00 800.00",
        "01-24 1,000.00 1,000.00 DEPOSIT "
        "01-25 15.00 985.00 DEBIT CARD SETUP FEE "
        "01-31 185.00 800.00 POS DB ONE",
        daily="01-24 1,000.00 01-25 985.00 01-31 800.00",
    )
    stmt = parse_woodforest_statement(text)
    assert stmt.beginning_balance == 0.00
    assert all(t.date >= stmt.period_start for t in stmt.transactions)
    assert initialization_postings(text, stmt) == []
