"""The Wealthsimple `Chequing monthly statement`.

The two hard things about this layout are the printed sign glyph — the family
sets U+2013 and never an ASCII minus — and the row that wraps, which is why
the reader closes a row on its Balance cell rather than on a newline.
"""
from __future__ import annotations

from analysis.dates import source_posting_dates
from analysis.wealthsimple import detect, parse_wealthsimple_statement

HEAD = (
    "Chequing monthly statement\n"
    "Wealthsimple\n"
    "Mar 1 - Mar 31, 2026\n"
    "Cameron Webb 209 - 31 Rodenbush Drive Regina, SK S4R8C7 Canada\n"
    "Account number: 31240401\n"
    "Your March summary MAR 1 BALANCE\n"
    "MAR 31 BALANCE\n"
    "$497.27\n"
    "$94.27\n"
    "Activity\n"
    "DATE POSTED DATE DESCRIPTION AMOUNT (CAD) BALANCE (CAD)\n"
)
FOOT = "Wealthsimple Payments Inc., 400 - 80 Spadina Ave, Toronto, ON, M5V 2J4 Page 1 of 4\n"

ONE_ROW = (
    HEAD
    + "2026-03-01 2026-03-01 Lake Country Coop Lask –$403.00 $94.27\n"
    + FOOT
)


# --------------------------------------------------------------- detection


def test_detection_claims_the_wealthsimple_statement():
    assert detect(ONE_ROW).claims


def test_detection_does_not_claim_another_banks_statement_that_names_wealthsimple():
    """Three CIBC statements in the archive print `INVESTMENT Wealthsimple
    Investments Inc.` as a payee. The issuer word alone must not reach this
    registration."""
    cibc = (
        "CIBC Account Statement\nTransaction details\n"
        "Date Description Withdrawals ($) Deposits ($) Balance ($)\n"
        "Jan 28 INVESTMENT Wealthsimple Investments Inc.\n1,000.00 9,605.61\n"
    )
    assert not detect(cibc).claims


def test_detection_needs_the_activity_header():
    assert not detect("Chequing monthly statement\nWealthsimple\n").claims


# ------------------------------------------------------------ the sign glyph


def test_the_printed_en_dash_is_a_minus():
    stmt = parse_wealthsimple_statement(ONE_ROW)
    assert stmt.transactions[0].amount == -403.00
    assert stmt.transactions[0].direction == "debit"


def test_an_amount_with_no_sign_glyph_is_a_deposit():
    stmt = parse_wealthsimple_statement(
        HEAD.replace("$94.27", "$4,497.27")
        + "2026-03-01 2026-03-01 Interac e-Transfer® Received $4,000.00 $4,497.27\n"
        + FOOT
    )
    assert stmt.transactions[0].amount == 4000.00
    assert stmt.transactions[0].direction == "credit"


def test_the_whole_dash_class_reads_as_a_minus():
    """U+2013 is what the family prints; the rest of the class is admitted so a
    sibling issue set with a true minus sign reads identically rather than
    silently losing its sign."""
    for glyph in ("–", "−", "—", "-"):
        stmt = parse_wealthsimple_statement(
            HEAD + "2026-03-01 2026-03-01 Coop %s$403.00 $94.27\n" % glyph + FOOT
        )
        assert stmt.transactions[0].amount == -403.00, glyph


def test_a_dash_inside_a_description_is_not_a_sign():
    """Only the glyph standing immediately before the amount's currency symbol
    is this cell's sign; the address line and the merchant name print dashes
    of their own."""
    stmt = parse_wealthsimple_statement(
        HEAD.replace("$94.27", "$4,497.27")
        + "2026-03-01 2026-03-01 Co-op Store 209 - 31 Rodenbush $4,000.00 $4,497.27\n"
        + FOOT
    )
    assert stmt.transactions[0].amount == 4000.00
    assert stmt.transactions[0].description == "Co-op Store 209 - 31 Rodenbush"


# --------------------------------------------------------------- the reader


def test_a_row_closes_on_its_balance_cell_so_a_wrapped_description_is_kept():
    """A long description wraps and carries its amount onto the next physical
    line. The row is opened by the two dates and closed by the Balance cell,
    which is its last column."""
    stmt = parse_wealthsimple_statement(
        HEAD.replace("$94.27", "–$2.73")
        + "2026-03-01 2026-03-01 Interac e-Transfer® Out to Justin Webb: Food and gas\n"
        "reimbursement for la ronge works. Company cost\n"
        "–$500.00 –$2.73\n"
        + FOOT
    )
    assert len(stmt.transactions) == 1
    assert stmt.transactions[0].amount == -500.00
    assert "Company cost" in stmt.transactions[0].description


def test_the_page_furniture_after_the_last_row_is_not_swallowed_into_it():
    """Conditional, and the condition is that the final row closes. If it
    never closed, the boilerplate would be accumulated into it until something
    completed an amount/balance pair; that fails the balance walk rather than
    publishing quietly, and it happens on none of the 16 family documents."""
    stmt = parse_wealthsimple_statement(
        ONE_ROW
        + "Wealthsimple chequing accounts are offered by Wealthsimple "
        "Investments Inc., a member of CIRO, and funds are held in trust.\n"
    )
    assert len(stmt.transactions) == 1
    assert stmt.transactions[0].description == "Lake Country Coop Lask"


def test_the_posted_date_is_the_published_one():
    """The document states which of its two dates is the accounting one:
    "Posted date is when the transaction is processed and finalized. Use this
    for accounting purposes." """
    stmt = parse_wealthsimple_statement(
        HEAD + "2026-03-01 2026-03-04 Coop –$403.00 $94.27\n" + FOOT
    )
    assert stmt.transactions[0].date == "2026-03-04"


# ------------------------------------------------------------- the summary


def test_the_summary_labels_are_checked_against_the_printed_period():
    """The two labels are printed before their two figures, so the pairing is
    positional. Each label carries its own date, and a document whose labels
    do not match the printed period is declined rather than paired by order
    alone."""
    stmt = parse_wealthsimple_statement(ONE_ROW)
    assert stmt.beginning_balance == 497.27
    assert stmt.ending_balance == 94.27
    assert stmt.currency == "CAD"
    assert stmt.bank == "Wealthsimple"
    assert stmt.account_number == "31240401"

    mismatched = ONE_ROW.replace("MAR 31 BALANCE", "MAR 29 BALANCE")
    assert parse_wealthsimple_statement(mismatched) is None


def test_no_total_is_printed_so_none_is_claimed():
    stmt = parse_wealthsimple_statement(ONE_ROW)
    assert stmt.stated_total_credits is None
    assert stmt.stated_total_debits is None
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


# ------------------------------------------------------------- failing closed


def test_a_zero_activity_statement_is_declined():
    """One archive document prints the grid header, an opening and closing
    balance of $0.00 and no rows at all. Publishing an empty ledger is the
    platform's zero-activity rule to extend, not this parser's to assume."""
    empty = (
        HEAD.replace("$497.27", "$0.00").replace("$94.27", "$0.00")
        + "Date is when the transaction happened.\n"
        + FOOT
    )
    assert detect(empty).claims
    assert parse_wealthsimple_statement(empty) is None


# ------------------------------- the shared posting-date heuristic, narrowed


def test_a_dated_balance_label_is_not_a_posting_row():
    """`AUG 31 BALANCE` is this layout's closing-balance label, with the date
    as the label's own qualifier — so none of the compound wordings the
    heuristic already excludes ever forms. Read as a posting row it invented an
    activity day the statement never had, and two documents whose last day
    carries no posting were withheld for a reason untrue of them."""
    from datetime import date

    markdown = (
        "Your August summary AUG 1 BALANCE\n"
        "AUG 31 BALANCE\n"
        "$0.00\n"
        "$3,760.07\n"
        "2025-08-05 2025-08-05 Coop –$403.00 $94.27\n"
    )
    found = source_posting_dates(markdown, date(2025, 8, 1), date(2025, 8, 31))
    assert date(2025, 8, 31) not in found
    # And nothing else is found either: this layout prints TWO dates on every
    # posting row, which the heuristic reads as a balance grid rather than a
    # posting. So on this family the check is vacuous, not load-bearing — the
    # label was the only date it ever saw, and it was the wrong one.
    assert found == set()


def test_a_single_date_posting_row_is_still_found():
    """The narrowing removes the label, not posting rows."""
    from datetime import date

    found = source_posting_dates(
        "Aug 05 Coop purchase 403.00 1,200.00\n", date(2025, 8, 1), date(2025, 8, 31)
    )
    assert date(2025, 8, 5) in found


def test_a_posting_row_whose_description_ends_in_balance_keeps_its_date():
    """The exclusion is the bare word with no money on the line; a real
    posting row prints its figure."""
    from datetime import date

    markdown = "Aug 31 TRANSFER TO SAVINGS BALANCE 403.00 1,200.00\n"
    found = source_posting_dates(markdown, date(2025, 8, 1), date(2025, 8, 31))
    assert date(2025, 8, 31) in found
