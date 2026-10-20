"""W3 §RBCCIBC card A — the English `CIBC Account Statement` layout.

CIBC prints the same three-column posting grid RBC does:

    Date | Description | Withdrawals ($) | Deposits ($) | Balance ($)

so it is read by the same shared `tables.read_grid_rows`, and the two
structural rules that reader encodes (a lone cell is an amount; two adjacent
cells are an amount and its running balance) do the same work here. What is
CIBC's own is the furniture around the grid, and it differs in four ways that
each cost a document if they are read as RBC's:

  * the grid is compressed HORIZONTALLY — the column header, the opening row
    and the first posting arrive on one physical line, and a line routinely
    carries the tail of one row and the whole of the next. So the Date column
    is consumed wherever it is printed, not only at the start of a line;
  * a continuation page re-prints the running balance as `Balance forward`,
    which is the opening row again: a balance with no amount beside it, and
    not a transaction;
  * the summary prints its two totals as bare `Withdrawals -` / `Deposits +`
    rows and no instance counts at all;
  * a foreign-currency account states its currency on the closing-balance row
    and nowhere else.

Every fixture below is synthetic. Nothing here names a customer, and no
constant in `analysis/cibc.py` comes from a corpus document.
"""
from __future__ import annotations

from analysis.cibc import parse_cibc_statement
from analysis.reconcile import reconcile

HEAD = """
CIBC Account Statement
For Nov 1 to Nov 30, 2053
Account number 00-00000
Branch transit number 00000
Account summary Contact information
Opening balance on Nov 1, 2053 ${opening}
Withdrawals - {debits}
Deposits + {credits}
Closing balance on Nov 30, 2053 {code}= ${closing}
Transaction details
"""

GRID = "Date Description Withdrawals ($) Deposits ($) Balance ($)"


def statement(body, *, opening, closing, credits, debits, code=""):
    return HEAD.format(
        opening=opening, closing=closing, credits=credits, debits=debits,
        code=f"{code} " if code else "",
    ) + body


def amounts(stmt):
    return [t.amount for t in stmt.transactions]


def descriptions(stmt):
    return [t.description for t in stmt.transactions]


def balances(stmt):
    return [t.running_balance for t in stmt.transactions]


# ---------------------------------------------------------------------------
# The layout, end to end
# ---------------------------------------------------------------------------

def test_the_english_layout_is_detected_and_parsed():
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00 Nov 3 PRE-AUTH DEBIT SUPPLIER\n"
        "100.00 900.00\n"
        "Nov 5 DEPOSIT\n"
        "250.00 1,150.00\n"
        "Closing balance $1,150.00\n",
        opening="1,000.00", closing="1,150.00", credits="250.00", debits="100.00",
    ))
    assert stmt is not None
    assert stmt.bank == "CIBC"
    assert stmt.currency == "CAD"
    assert stmt.period_start == "2053-11-01"
    assert stmt.period_end == "2053-11-30"
    assert stmt.account_number == "00-00000"
    assert descriptions(stmt) == ["PRE-AUTH DEBIT SUPPLIER", "DEPOSIT"]
    assert amounts(stmt) == [-100.0, 250.0]
    assert balances(stmt) == [900.0, 1150.0]
    assert reconcile(stmt).ok


def test_the_first_posting_shares_the_column_headers_own_line():
    """The header, the opening row and the first posting arrive together.

    Reading the opening row as owning the whole line discarded a real
    transaction — the defect card D fixed inside the shared grid reader.
    """
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00 Nov 3 PRE-AUTH DEBIT SUPPLIER 100.00 900.00\n"
        "Closing balance $900.00\n",
        opening="1,000.00", closing="900.00", credits="0.00", debits="100.00",
    ))
    assert stmt is not None
    assert descriptions(stmt) == ["PRE-AUTH DEBIT SUPPLIER"]
    assert amounts(stmt) == [-100.0]


def test_a_balance_forward_is_the_opening_row_again_and_not_a_transaction():
    """A continuation page re-prints the running balance, and carries the next
    row's description on the same line."""
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00 Nov 3 PRE-AUTH DEBIT SUPPLIER 100.00 900.00\n"
        "--- Page 2 ---\n"
        f"{GRID} Nov 4 Balance forward $900.00 SERVICE CHARGE\n"
        "5.00 895.00\n"
        "Closing balance $895.00\n",
        opening="1,000.00", closing="895.00", credits="0.00", debits="105.00",
    ))
    assert stmt is not None
    assert descriptions(stmt) == ["PRE-AUTH DEBIT SUPPLIER", "SERVICE CHARGE"]
    assert amounts(stmt) == [-100.0, -5.0]
    assert balances(stmt) == [900.0, 895.0]
    assert reconcile(stmt).ok


def test_several_printed_rows_on_one_physical_line_are_separated():
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 ITEM ONE 100.00 900.00 ITEM TWO 50.00 850.00\n"
        "Closing balance $850.00\n",
        opening="1,000.00", closing="850.00", credits="0.00", debits="150.00",
    ))
    assert stmt is not None
    assert descriptions(stmt) == ["ITEM ONE", "ITEM TWO"]
    assert amounts(stmt) == [-100.0, -50.0]


def test_the_direction_comes_from_the_printed_balance_movement():
    """The text layer destroys the column, so the sign is the arithmetic the
    bank printed — not the wording of the description."""
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 PAY CERTAS HOME AUTO INS CO\n"
        "500.00 1,500.00\n"
        "Nov 4 PAY CERTAS HOME AUTO INS CO\n"
        "500.00 1,000.00\n"
        "Closing balance $1,000.00\n",
        opening="1,000.00", closing="1,000.00", credits="500.00", debits="500.00",
    ))
    assert stmt is not None
    assert amounts(stmt) == [500.0, -500.0]
    assert [t.direction for t in stmt.transactions] == ["credit", "debit"]


# ---------------------------------------------------------------------------
# The summary block
# ---------------------------------------------------------------------------

def test_the_two_stated_totals_are_magnitudes_and_no_counts_are_claimed():
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 ITEM 100.00 900.00\n"
        "Closing balance $900.00\n",
        opening="1,000.00", closing="900.00", credits="0.00", debits="100.00",
    ))
    assert stmt is not None
    assert stmt.stated_total_debits == 100.0
    assert stmt.stated_total_credits == 0.0
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_a_foreign_currency_account_states_its_currency_on_the_closing_row():
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 WIRE TSF 100.00 900.00\n"
        "Closing balance $900.00\n",
        opening="1,000.00", closing="900.00", credits="0.00", debits="100.00",
        code="USD",
    ))
    assert stmt is not None
    assert stmt.currency == "USD"


# ---------------------------------------------------------------------------
# The money cells this grid prints inside a description
# ---------------------------------------------------------------------------

def test_a_tariff_quoted_in_the_description_is_not_a_second_cell():
    """`SERVICE CHARGE CAPPED MONTHLY FEE$16.95 RECORD-KEEPING N/A` names the
    fee and the row's own cell then prints it again. Reading the quoted figure
    as a cell booked the fee twice — nine documents in this family.
    """
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 SERVICE CHARGE CAPPED MONTHLY FEE$16.95 RECORD-KEEPING  N/A\n"
        "16.95 983.05\n"
        "Closing balance $983.05\n",
        opening="1,000.00", closing="983.05", credits="0.00", debits="16.95",
    ))
    assert stmt is not None
    assert amounts(stmt) == [-16.95]
    assert balances(stmt) == [983.05]
    assert reconcile(stmt).ok


def test_a_foreign_currency_operand_of_an_exchange_rate_is_not_a_cell():
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $10,000.00\n"
        "Nov 3 INTERNET GLOBAL MONEY TRANSFER 450000.00 PKR @.005 603303235213\n"
        "2,250.00 7,750.00\n"
        "Closing balance $7,750.00\n",
        opening="10,000.00", closing="7,750.00", credits="0.00", debits="2,250.00",
    ))
    assert stmt is not None
    assert amounts(stmt) == [-2250.0]


def test_a_deposit_note_fee_rate_is_not_a_cell():
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 DEPOSIT NOTE FEE SELF-SERVICE 6170.0 AT 2.25/1,000\n"
        "13.88 986.12\n"
        "Closing balance $986.12\n",
        opening="1,000.00", closing="986.12", credits="0.00", debits="13.88",
    ))
    assert stmt is not None
    assert amounts(stmt) == [-13.88]


# ---------------------------------------------------------------------------
# Negatives
# ---------------------------------------------------------------------------

def test_negative_a_month_name_inside_a_description_does_not_open_a_row():
    """A date token is the Date column only where the grid can print one: at
    the start of the table's text, or right after a completed balance cell."""
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 PRE-AUTH DEBIT MAY 12 HOLDINGS LTD\n"
        "100.00 900.00\n"
        "Closing balance $900.00\n",
        opening="1,000.00", closing="900.00", credits="0.00", debits="100.00",
    ))
    assert stmt is not None
    assert descriptions(stmt) == ["PRE-AUTH DEBIT MAY 12 HOLDINGS LTD"]
    assert amounts(stmt) == [-100.0]


def test_negative_a_header_with_no_ledger_is_not_a_statement():
    assert parse_cibc_statement(statement(
        f"{GRID}\n", opening="1,000.00", closing="1,000.00",
        credits="0.00", debits="0.00",
    )) is None


def test_negative_the_french_layout_is_not_claimed_by_the_english_parser():
    from analysis.cibc import parse_cibc_french_statement

    french = "CIBC\nDétail de vos opérations\nDate Description Retraits\n"
    assert parse_cibc_statement(french) is None
    assert parse_cibc_french_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\nNov 3 ITEM 100.00 900.00\n",
        opening="1,000.00", closing="900.00", credits="0.00", debits="100.00",
    )) is None


def test_negative_a_page_footer_never_becomes_a_row():
    stmt = parse_cibc_statement(statement(
        f"{GRID} Nov 1 Opening balance $1,000.00\n"
        "Nov 3 ITEM 100.00 900.00\n"
        "(continued on next page)\n"
        "10774E BUS-2018/09 Page 1 of 3\n"
        "Closing balance $900.00\n",
        opening="1,000.00", closing="900.00", credits="0.00", debits="100.00",
    ))
    assert stmt is not None
    assert descriptions(stmt) == ["ITEM"]
