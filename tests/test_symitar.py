"""The Symitar member statement.

One PDF, several of a member's accounts. The fixtures below are about the
three distinctions that decide what may be published: a loan facility is not a
deposit ledger, a dormant sibling is not a second ledger, and a second ACTIVE
deposit account is one the single-account schema cannot carry.
"""
from __future__ import annotations

from analysis.symitar import detect, parse_symitar_statement

HEAD = (
    "Statement of Account\n"
    "Account Number Statement Period Page\n"
    "05/01/26 thru 05/31/26 ***8010 1 of 4\n"
    "ACCOUNT SUMMARY\n"
    "0210 Free Business Checking $ 1,200.00 0000 Money Market $ 5.19\n"
)
GRID = "Posting Date Deposit Withdrawal Balance Description\n"

EQUATION = (
    "Beginning Balance Credits / Deposits Dividends Debits / Withdrawals "
    "Ending Balance YTD Dividends\n"
    "$ 1,000.00 $ 500.00 $ 0.00 $ 300.00 $ 1,200.00 $ 41.44\n"
)

ACTIVE = (
    "Free Business Checking ( ID 0210 )\n"
    + GRID
    + "05/01/26 $ 1,000.00 Beginning Balance "
    "05/02/26 -300.00 700.00 Card purchase LES SCHWAB "
    "05/03/26 500.00 1,200.00 ACH Deposit MERCHANT SERVICE\n"
)
DORMANT = (
    "Money Market ( ID 0000 )\n"
    + GRID
    + "05/01/26 $ 5.19 Beginning Balance No Transactions This Period "
    "05/31/26 $ 5.19 Ending Balance\n"
)
LOAN = (
    "CV 3 Flex (Account #xxxxxx5489)\n"
    "Beginning Balance: $ 55,682.92 Ending Balance: $ 55,457.24\n"
    "Date Amount Fees Interest Principal Balance Description\n"
    "05/01 55,682.92 Beginning Balance 05/05 660.00 434.32 225.68 55,457.24 Regular Payment\n"
)

SIMPLE = HEAD + ACTIVE + DORMANT


# --------------------------------------------------------------- detection


def test_detection_claims_the_member_statement():
    assert detect(SIMPLE).claims


def test_detection_needs_the_deposit_grid():
    assert not detect(HEAD + "Free Business Checking ( ID 0210 )\n").claims


def test_detection_needs_an_account_section():
    assert not detect(HEAD + GRID).claims


# ------------------------------------------------------- one active account


def test_a_dormant_sibling_does_not_fail_close_the_document():
    """The share account prints `No Transactions This Period` beside a
    beginning balance equal to its ending balance. Declining because it exists
    would fail-close a perfectly readable statement."""
    stmt = parse_symitar_statement(SIMPLE)
    assert stmt is not None
    assert stmt.account_name == "Free Business Checking"
    assert stmt.account_number == "0210"
    assert len(stmt.transactions) == 2


def test_two_active_deposit_accounts_are_l1_blocked():
    """A dividend posting makes the money-market account active too. Two
    deposit ledgers cannot be represented by the single-account schema, so the
    document is declined rather than published under one account's name."""
    second = (
        "Money Market ( ID 0000 )\n"
        + GRID
        + "05/01/26 $ 5.18 Beginning Balance 05/01/26 0.01 5.19 Dividend Deposit\n"
    )
    text = HEAD + ACTIVE + second
    assert detect(text).claims
    assert parse_symitar_statement(text) is None


def test_a_loan_section_is_not_a_deposit_ledger():
    """The member's credit facilities print their own grid with payment and
    interest columns. They contribute no transaction and do not make the
    document multi-account."""
    stmt = parse_symitar_statement(HEAD + ACTIVE + DORMANT + LOAN)
    assert stmt is not None
    assert len(stmt.transactions) == 2
    assert all("Regular Payment" not in t.description for t in stmt.transactions)


# ------------------------------------------------------------- the oracles


def test_the_summary_ending_balance_closes_the_account_with_no_equation_row():
    stmt = parse_symitar_statement(SIMPLE)
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00
    assert stmt.bank == "Symitar Credit Union"
    assert stmt.currency == "USD"
    assert stmt.period_start == "2026-05-01"
    assert stmt.period_end == "2026-05-31"


def test_the_six_figure_equation_row_is_the_per_account_oracle():
    """`Beginning + Credits/Deposits + Dividends - Debits/Withdrawals =
    Ending`. Dividends are credited to the account and post as their own rows,
    so the stated credit total is the two credit columns together."""
    text = HEAD + (
        "Business Checking (Account #xxxxxx9247)\n"
        + EQUATION
        + "Date Deposit Withdrawal Balance Description\n"
        "05/01 1,000.00 Beginning Balance "
        "05/02 -300.00 700.00 Point of Sale Withdrawal "
        "05/03 500.00 1,200.00 External Deposit\n"
    )
    stmt = parse_symitar_statement(text)
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00
    assert stmt.stated_total_credits == 500.00
    assert stmt.stated_total_debits == 300.00


def test_two_disagreeing_opening_balances_fail_closed():
    """The equation row and the grid's own opening row both state the opening
    balance. Where they disagree the document contradicts itself."""
    text = HEAD + (
        "Business Checking (Account #xxxxxx9247)\n"
        + EQUATION
        + "Date Deposit Withdrawal Balance Description\n"
        "05/01 9,999.99 Beginning Balance 05/03 500.00 1,200.00 External Deposit\n"
    )
    assert detect(text).claims
    assert parse_symitar_statement(text) is None


# ----------------------------------------------------------- the row reader


def test_amount_and_balance_are_read_before_the_description():
    stmt = parse_symitar_statement(SIMPLE)
    first = stmt.transactions[0]
    assert first.amount == -300.00
    assert first.direction == "debit"
    assert first.running_balance == 700.00
    assert first.description == "Card purchase LES SCHWAB"


def test_the_amount_carries_its_own_printed_sign():
    stmt = parse_symitar_statement(SIMPLE)
    assert [t.amount for t in stmt.transactions] == [-300.00, 500.00]


def test_a_two_digit_year_is_read_as_printed():
    stmt = parse_symitar_statement(SIMPLE)
    assert [t.date for t in stmt.transactions] == ["2026-05-02", "2026-05-03"]


def test_a_short_date_is_resolved_against_the_printed_period():
    """The second issue prints `MM/DD` with no year."""
    text = HEAD + (
        "Business Checking (Account #xxxxxx9247)\n"
        + EQUATION
        + "Date Deposit Withdrawal Balance Description\n"
        "05/01 1,000.00 Beginning Balance "
        "05/02 -300.00 700.00 Point of Sale "
        "05/03 500.00 1,200.00 External Deposit\n"
    )
    stmt = parse_symitar_statement(text)
    assert [t.date for t in stmt.transactions] == ["2026-05-02", "2026-05-03"]


def test_a_document_with_no_active_deposit_account_is_declined():
    assert parse_symitar_statement(HEAD + DORMANT) is None


def test_a_row_whose_date_cannot_be_resolved_refuses_the_document():
    """A row the grid printed but this reader cannot resolve is a hole in the
    ledger. It refuses the document rather than shrinking it silently — the
    convention `woodforest._postings` follows. `02/30` is not a date in any
    year the period spans."""
    text = HEAD + (
        "Free Business Checking ( ID 0210 )\n"
        + GRID
        + "05/01/26 $ 1,000.00 Beginning Balance "
        "02/30 -300.00 700.00 Card purchase "
        "05/03/26 500.00 1,200.00 ACH Deposit\n"
    )
    assert detect(text).claims
    assert parse_symitar_statement(text) is None
