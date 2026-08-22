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
    """Two deposit ledgers cannot be represented by the single-account schema,
    so the document is declined rather than published under one account's
    name."""
    text = HEAD + ACTIVE + _money_market("05/02/26 -25.00 -19.81 Card purchase FUEL STOP")
    assert detect(text).claims
    assert parse_symitar_statement(text) is None


# ----------------------------------- the sibling that posted only its yield
#
# W3 §DECLINESG. Until this card the fixture above used a DIVIDEND posting as
# its example of a second active ledger, and three archive documents were
# refused for earning one cent. A dividend is the credit union crediting the
# account the yield it earned, which this platform names in its own equation
# row as a column separate from `Credits / Deposits`; it is not member
# activity, and `_yield_only` reads it only under three conditions that must
# all hold.


def _money_market(body: str, *, opening: str = "5.18") -> str:
    return (
        "Money Market ( ID 0000 )\n"
        + GRID
        + f"05/01/26 $ {opening} Beginning Balance {body}\n"
    )


DIVIDEND_ONLY = _money_market("05/01/26 0.01 5.19 Dividend Deposit Annual Percentage Yield Earned")


def test_a_sibling_that_posted_only_its_own_dividend_is_not_a_second_ledger():
    stmt = parse_symitar_statement(HEAD + ACTIVE + DIVIDEND_ONLY)
    assert stmt is not None
    assert stmt.account_name == "Free Business Checking"
    assert stmt.account_number == "0210"
    assert len(stmt.transactions) == 2
    assert all("Dividend" not in t.description for t in stmt.transactions)


def test_the_dividend_sibling_skip_is_byte_identical_to_the_dormant_one():
    """The published payload must not depend on WHICH way the platform
    declared the sibling idle."""
    assert parse_symitar_statement(HEAD + ACTIVE + DIVIDEND_ONLY) == parse_symitar_statement(SIMPLE)


def test_a_sibling_with_one_ordinary_posting_beside_its_dividend_is_a_second_ledger():
    """Isolates the FIRST condition: the other two hold here — the section's
    arithmetic closes (6.18 + 0.01 - 1.00 = 5.19) and 5.19 is what
    `ACCOUNT SUMMARY` states — so only "every posting is a dividend" can be
    doing the refusing."""
    text = HEAD + ACTIVE + _money_market(
        "05/01/26 0.01 6.19 Dividend Deposit 05/04/26 -1.00 5.19 Card purchase FUEL STOP",
        opening="6.18",
    )
    assert parse_symitar_statement(text) is None


def test_the_dividend_read_is_anchored_at_the_posting_type():
    """A counterparty whose NAME carries the word is not the account's own
    yield. Isolates the anchor and nothing else: the posting is a CREDIT, the
    arithmetic closes (5.18 + 0.01 = 5.19) and 5.19 is what `ACCOUNT SUMMARY`
    states — so reading the description with `search` instead of `match` would
    skip this sibling and publish the document."""
    text = HEAD + ACTIVE + _money_market(
        "05/04/26 0.01 5.19 ACH Deposit DIVIDEND SOLAR REFUND"
    )
    assert parse_symitar_statement(text) is None


def test_the_dividend_sibling_must_close_its_own_arithmetic():
    """Isolates the SECOND condition: the posting is a dividend and the last
    printed balance is exactly the 5.19 `ACCOUNT SUMMARY` states, but the
    section's own walk does not reach it (5.18 + 0.05 = 5.23). A section whose
    arithmetic this reader cannot close is a ledger it has not accounted for."""
    text = HEAD + ACTIVE + _money_market("05/01/26 0.05 5.19 Dividend Deposit")
    assert parse_symitar_statement(text) is None


def test_the_dividend_sibling_must_agree_with_the_document_s_own_summary():
    """`ACCOUNT SUMMARY` states 5.19 for this account. A section that closes
    its own arithmetic on a different figure is contradicted by the document
    and is not skipped."""
    text = HEAD + ACTIVE + _money_market("05/01/26 0.01 5.30 Dividend Deposit", opening="5.29")
    assert parse_symitar_statement(text) is None


def test_a_dividend_named_posting_that_takes_money_out_is_not_yield():
    """Yield is paid INTO the account. Isolates the direction clause: the
    posting is dividend-anchored, the section's arithmetic closes
    (5.20 - 0.01 = 5.19) and 5.19 is what `ACCOUNT SUMMARY` states, so only
    "and is a CREDIT" can be doing the refusing. This is also the shape a
    counterparty NAMED after the word would take."""
    text = HEAD + ACTIVE + _money_market(
        "05/01/26 -0.01 5.19 Dividend Solar Payment", opening="5.20"
    )
    assert parse_symitar_statement(text) is None


def test_a_sibling_this_reader_cannot_bound_is_never_dismissed_as_idle():
    """The guard in front of the three conditions, and its direction.

    A section whose opening balance this reader cannot find, or whose ending
    balance the document states nowhere, is the section it knows LEAST about —
    so it counts as a ledger and the document refuses. Skipping it instead
    would dismiss, as idle, precisely the account nothing here can check.
    """
    no_opening = (
        "Money Market ( ID 0000 )\n" + GRID + "05/04/26 -1.00 4.18 Card purchase FUEL STOP\n"
    )
    assert parse_symitar_statement(HEAD + ACTIVE + no_opening) is None
    unstated = (
        "Vacation Club ( ID 0330 )\n"
        + GRID
        + "05/01/26 $ 5.18 Beginning Balance 05/01/26 0.01 5.19 Dividend Deposit\n"
    )
    assert "0330" not in HEAD
    assert parse_symitar_statement(HEAD + ACTIVE + unstated) is None


def test_a_sole_deposit_account_that_posted_only_its_dividend_still_refuses():
    """Skipping the only deposit section leaves nothing to publish, and a
    ledger of dividends is not a statement of the member's activity."""
    assert parse_symitar_statement(HEAD + DIVIDEND_ONLY) is None


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
