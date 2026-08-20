"""W3 coverage wave / DECLINES-D: the shapes wilson_muir and square_checking
could not survive.

Every fixture here is a SYNTHETIC reproduction of a *structural shape* named by
the decline census over the run of record's 132 `parser_declined` documents
(W3 §DECLINESD D1). The layout sentinels are each platform's own — the same
ones its detector keys on — and every counterparty, holder, date, amount and
account number is invented. The arithmetic inside each fixture is real, because
the arithmetic is what the readers gate on.

WM1 the open category list
    Wilson & Muir prints its summary strip as a TABLE of `<category> [<count>]
    <amount>[+]` rows between two dated balance rows. The reader memorized six
    category names welded together with `\\s+`, so a period that also printed
    `Automatic Teller Withdrawals` or `Miscellaneous Fees` — categories the same
    account prints in other months — refused the whole document on its summary.
    The strip is now read as the table it is, and the platform's own identity
    (`forward + credits - debits = ending`) is what makes an unmemorized
    category safe to total.

WM2 the count the platform omits
    A category with no items prints its total and no count (`Debits 0.00`).
    Requiring a count refused three statements on a row that says zero — the
    same convention `core_processor_sectioned._counts` already names.

WM3 the section that ends where the next one begins
    `CHECKS AND OTHER DEBITS` is printed only when the period contains cheques.
    Closing the electronic-debit section at that heading emptied the section on
    exactly the statements that print no cheques, and the whole debit ledger
    then read as zero against a six-figure printed total.

SQ1 the location column
    Square prints its summary as `Starting balance / Activities / Ending
    balance`. A multi-location merchant's statement prints the same three
    columns under a leading `Location` column, with the location's name in the
    row's first cell. The pattern required the first money cell to stand
    immediately after the column header, so four consecutive statements of one
    merchant were refused on their summary while their activity grid, their
    period and their account number all read perfectly.
"""
from __future__ import annotations

from analysis.square_checking import parse_square_checking_statement
from analysis.wilson_muir import parse_wilson_muir_statement

# ------------------------------------------------------------- wilson_muir

_WM_HEAD = (
    "WILSON & MUIR BK & TRUST\n"
    "EXAMPLE HOLDINGS LLC\n"
    "Statement Date: 01/30/2026 Account No.: #4321 Page: 1\n"
    "SMALL BUSINESS PACKAGE SUMMARY Type :     **REG    Status :    Active\n"
)

#: The strip's own identity: 1,000.00 + (500.00 + 300.00) - (100.00 + 50.00 +
#: 200.00 + 25.00 + 10.00) = 1,415.00. Two of the seven categories —
#: `Automatic Teller Withdrawals` and `Miscellaneous Fees` — are outside the
#: six the reader used to memorize, and each stands BETWEEN two that are in it.
_WM_STRIP = (
    "Category Number Amount Balance Forward From 12/31/25 1,000.00 "
    "Deposits 2 500.00+ "
    "Debits 1 100.00 "
    "Automatic Teller Withdrawals 1 50.00 "
    "Automatic Withdrawals 1 200.00 "
    "Automatic Deposits 1 300.00+ "
    "Card Activity 1 25.00 "
    "Miscellaneous Fees 1 10.00 "
    "Ending Balance On 01/30/26 1,415.00 "
    "Foreign Items Deposited 1 Items Deposited 2 "
    "Average Balance (Ledger) 1,200.00+\n"
)

_WM_LEDGER = (
    "ALL CREDIT ACTIVITY\n"
    "Date Type Amount Date Type Amount\n"
    "01/05/26 Deposit 300.00 01/12/26 Deposit 200.00\n"
    "01/20/26 Automatic Deposit 300.00\n"
    "ELECTRONIC DEBITS\n"
    "Date Type Amount Date Type Amount\n"
    "01/06/26 ATM Withdrawal 50.00 01/14/26 Automatic Withdrawal 200.00\n"
    "01/18/26 Card Purchase 25.00 01/28/26 Service Fee 10.00\n"
    "CHECKS AND OTHER DEBITS\n"
    "Date Check Amount\n"
    "01/09/26 1001 100.00\n"
    "DAILY BALANCE SUMMARY\n"
    "Date Balance\n"
    "01/30/26 1,415.00\n"
)

WILSON_MUIR_WIDE_CATEGORIES = _WM_HEAD + _WM_STRIP + _WM_LEDGER

#: The identical period with the two unmemorized categories folded away: their
#: amounts (50.00 + 10.00) leave the strip, so the closing balance rises by 60
#: and the ledger loses the two rows that carried them.
WILSON_MUIR_MEMORIZED_CATEGORIES_ONLY = (
    _WM_HEAD
    + (
        "Category Number Amount Balance Forward From 12/31/25 1,000.00 "
        "Deposits 2 500.00+ "
        "Debits 1 100.00 "
        "Automatic Withdrawals 1 200.00 "
        "Automatic Deposits 1 300.00+ "
        "Card Activity 1 25.00 "
        "Ending Balance On 01/30/26 1,475.00 "
        "Average Balance (Ledger) 1,200.00+\n"
    )
    + (
        "ALL CREDIT ACTIVITY\n"
        "01/05/26 Deposit 300.00 01/12/26 Deposit 200.00\n"
        "01/20/26 Automatic Deposit 300.00\n"
        "ELECTRONIC DEBITS\n"
        "01/14/26 Automatic Withdrawal 200.00 01/18/26 Card Purchase 25.00\n"
        "CHECKS AND OTHER DEBITS\n"
        "01/09/26 1001 100.00\n"
        "DAILY BALANCE SUMMARY\n"
        "01/30/26 1,475.00\n"
    )
)

#: WM2/WM3: a period with no cheques. `Debits` prints its zero total with no
#: count, and the statement prints no `CHECKS AND OTHER DEBITS` heading at all —
#: the electronic-debit section runs straight into the daily-balance summary.
#: 1,000.00 + 800.00 - 285.00 = 1,515.00.
WILSON_MUIR_NO_CHEQUE_SECTION = (
    _WM_HEAD
    + (
        "Category Number Amount Balance Forward From 12/31/25 1,000.00 "
        "Deposits 2 500.00+ "
        "Debits 0.00 "
        "Automatic Teller Withdrawals 1 50.00 "
        "Automatic Withdrawals 1 200.00 "
        "Automatic Deposits 1 300.00+ "
        "Card Activity 1 25.00 "
        "Miscellaneous Fees 1 10.00 "
        "Ending Balance On 01/30/26 1,515.00 "
        "Average Balance (Ledger) 1,200.00+\n"
    )
    + (
        "ALL CREDIT ACTIVITY\n"
        "01/05/26 Deposit 300.00 01/12/26 Deposit 200.00\n"
        "01/20/26 Automatic Deposit 300.00\n"
        "ELECTRONIC DEBITS\n"
        "01/06/26 ATM Withdrawal 50.00 01/14/26 Automatic Withdrawal 200.00\n"
        "01/18/26 Card Purchase 25.00 01/28/26 Service Fee 10.00\n"
        "DAILY BALANCE SUMMARY\n"
        "01/30/26 1,515.00\n"
    )
)


def test_wilson_muir_reads_a_category_it_was_never_told_about():
    """WM1: two unmemorized categories, each between two memorized ones."""
    statement = parse_wilson_muir_statement(WILSON_MUIR_WIDE_CATEGORIES)

    assert statement is not None
    assert statement.beginning_balance == 1000.00
    assert statement.ending_balance == 1415.00
    assert statement.stated_total_credits == 800.00
    assert statement.stated_total_debits == 385.00


def test_wilson_muir_counts_every_category_the_strip_printed():
    """WM1: the stated counts are the strip's, not the six memorized rows'.

    The debit count is 5 — `Debits`, the ATM withdrawal, the automatic
    withdrawal, the card activity and the miscellaneous fee — and a reader
    that knew only three of those categories would state 3 against a ledger
    that correctly lists 5.
    """
    statement = parse_wilson_muir_statement(WILSON_MUIR_WIDE_CATEGORIES)

    assert statement is not None
    assert statement.stated_credit_count == 3
    assert statement.stated_debit_count == 5
    assert len([t for t in statement.transactions if t.amount > 0]) == 3
    assert len([t for t in statement.transactions if t.amount < 0]) == 5


def test_wilson_muir_still_reads_the_strip_it_always_could():
    """WM1 ablation: the memorized six alone read exactly as before."""
    statement = parse_wilson_muir_statement(WILSON_MUIR_MEMORIZED_CATEGORIES_ONLY)

    assert statement is not None
    assert statement.stated_total_credits == 800.00
    assert statement.stated_total_debits == 325.00
    assert statement.ending_balance == 1475.00
    assert statement.stated_credit_count == 3
    assert statement.stated_debit_count == 3


def test_wilson_muir_category_order_is_not_key_material():
    """WM1: the strip is a set of rows, so printing them in another order is
    the same statement. Only the order of the category lines differs."""
    reordered = WILSON_MUIR_WIDE_CATEGORIES.replace(
        "Debits 1 100.00 Automatic Teller Withdrawals 1 50.00 ",
        "Automatic Teller Withdrawals 1 50.00 Debits 1 100.00 ",
    )
    assert reordered != WILSON_MUIR_WIDE_CATEGORIES

    original = parse_wilson_muir_statement(WILSON_MUIR_WIDE_CATEGORIES)
    shuffled = parse_wilson_muir_statement(reordered)

    assert original is not None and shuffled is not None
    assert original.stated_total_credits == shuffled.stated_total_credits
    assert original.stated_total_debits == shuffled.stated_total_debits
    assert original.stated_debit_count == shuffled.stated_debit_count


def test_wilson_muir_reads_a_zero_category_that_printed_no_count():
    """WM2: `Debits 0.00` is the platform saying "none", not a missing field."""
    statement = parse_wilson_muir_statement(WILSON_MUIR_NO_CHEQUE_SECTION)

    assert statement is not None
    assert statement.stated_total_debits == 285.00
    assert statement.stated_debit_count == 4


def test_wilson_muir_reads_the_debits_of_a_statement_with_no_cheque_section():
    """WM3: the electronic section ends at the heading actually printed.

    The regression this pins is silent and total: with the section closed at a
    heading the document never prints, the debit ledger read ZERO while the
    strip stated 285.00 — and the document was declined on a gate that was
    right about a ledger the reader had thrown away.
    """
    statement = parse_wilson_muir_statement(WILSON_MUIR_NO_CHEQUE_SECTION)

    assert statement is not None
    debits = [t for t in statement.transactions if t.amount < 0]
    assert len(debits) == 4
    assert round(-sum(t.amount for t in debits), 2) == 285.00
    assert "CHECKS AND OTHER DEBITS" not in WILSON_MUIR_NO_CHEQUE_SECTION


def test_wilson_muir_declines_a_strip_row_it_cannot_read():
    """WM1 fail-closed: a row shape the category pattern does not consume is a
    category this reader would otherwise drop from the totals it then gates the
    ledger against."""
    assert parse_wilson_muir_statement(
        WILSON_MUIR_WIDE_CATEGORIES.replace(
            "Card Activity 1 25.00 ", "Card Activity 1 25.00 ~~ 7 ", 1
        )
    ) is None


def test_wilson_muir_declines_a_strip_whose_identity_does_not_close():
    """WM1 fail-closed: the `+` marker is trusted BECAUSE the identity checks
    it. A credit category printed without its marker is read as a debit, and
    the identity then misses by twice its amount."""
    assert parse_wilson_muir_statement(
        WILSON_MUIR_WIDE_CATEGORIES.replace(
            "Automatic Deposits 1 300.00+ ", "Automatic Deposits 1 300.00 ", 1
        )
    ) is None


def test_wilson_muir_declines_a_ledger_short_of_its_own_strip():
    """WM1 fail-closed: the strip may be readable and the ledger still not be.
    A dropped debit row leaves a strip that closes and a ledger that does not."""
    assert parse_wilson_muir_statement(
        WILSON_MUIR_WIDE_CATEGORIES.replace("01/28/26 Service Fee 10.00", "", 1)
    ) is None


# --------------------------------------------------------- square_checking

_SQ_TAIL = (
    "Date Details Activity type Balance Amount\n"
    "3/04/2026 EXAMPLE CUSTOMER SALE Payment processing $1,300.00 $300.00\n"
    "3/11/2026 EXAMPLE SUPPLY CO Card spend $1,250.00 -$50.00\n"
    "Block Inc. 1955 Broadway, Suite 815 Oakland, CA 94612\n"
    "squareup.com/help\n"
)
_SQ_HEAD = (
    "Square Checking Routing number: 000000000\n"
    "Account number: XXXXXXXX1234\n"
    "Checking statement March 1 - March 31, 2026\n"
)

#: The single-location printing, which this parser has always read.
SQUARE_PLAIN_SUMMARY = (
    _SQ_HEAD
    + "Starting balance Activities Ending balance\n"
    + "$1,000.00 2 $1,250.00\n"
    + _SQ_TAIL
)

#: The same statement as a multi-location merchant receives it: one extra
#: printed column, and the location's name standing in the row's first cell.
SQUARE_LOCATION_SUMMARY = (
    _SQ_HEAD
    + "Location Starting balance Activities Ending balance\n"
    + "Example Location One $1,000.00 2 $1,250.00\n"
    + _SQ_TAIL
)


def test_square_reads_the_location_column_it_also_prints():
    """SQ1: the location cell is a column, not a missing summary."""
    statement = parse_square_checking_statement(SQUARE_LOCATION_SUMMARY)

    assert statement is not None
    assert statement.beginning_balance == 1000.00
    assert statement.ending_balance == 1250.00


def test_square_location_column_changes_nothing_else():
    """SQ1 ablation: the two printings are the same statement."""
    plain = parse_square_checking_statement(SQUARE_PLAIN_SUMMARY)
    located = parse_square_checking_statement(SQUARE_LOCATION_SUMMARY)

    assert plain is not None and located is not None
    assert plain.beginning_balance == located.beginning_balance
    assert plain.ending_balance == located.ending_balance
    assert plain.period_start == located.period_start
    assert plain.period_end == located.period_end
    assert [t.amount for t in plain.transactions] == [
        t.amount for t in located.transactions
    ]


def test_square_counts_the_activities_of_a_located_summary():
    """SQ1: the printed `Activities` count must still reach the integrity
    check — a summary read through a different pattern that lost the count
    would silently disable the contradiction this platform can prove."""
    from analysis.square_checking import activity_count_contradictions

    statement = parse_square_checking_statement(SQUARE_LOCATION_SUMMARY)

    assert statement is not None
    assert activity_count_contradictions(SQUARE_LOCATION_SUMMARY, statement) == []
    assert activity_count_contradictions(
        SQUARE_LOCATION_SUMMARY.replace(
            "Example Location One $1,000.00 2 $1,250.00",
            "Example Location One $1,000.00 3 $1,250.00",
        ),
        statement,
    ) != []


def test_square_declines_a_summary_listing_more_than_one_location():
    """SQ1 fail-closed: two location rows are two ledgers, and the extraction
    schema carries one account per statement (L-1). Publishing the first row's
    balances against a grid holding both locations' rows would be a statement
    about neither."""
    two_locations = SQUARE_LOCATION_SUMMARY.replace(
        "Example Location One $1,000.00 2 $1,250.00\n",
        "Example Location One $1,000.00 2 $1,250.00\n"
        "Example Location Two $2,000.00 4 $2,400.00\n",
    )
    assert parse_square_checking_statement(two_locations) is None
