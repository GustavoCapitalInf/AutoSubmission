"""The Zions Bancorporation `Statement of Accounts` layout (W3 §CITI3 card C).

Fixtures are hand-built in the layout's printed shape with invented names and
figures. Both trade names the archive holds are exercised, because the whole
point of the registration is that neither of them is what identifies the
document.
"""
from __future__ import annotations

from analysis import zions
from analysis.schema import Statement

_RULE = "." * 20


def _document(
    *,
    brand: str = "Direct Inquiries to: 800-000-0000 WWW.NSBANK.COM",
    footer: str = "A division of Zions Bancorporation, N.A.",
    product: str = "BUSINESS GROWTH CHECKING",
    account: str = "1234567890",
    this_statement: str = "March 31, 2054",
    last_statement: str = "February 27, 2054",
    days: str = "32",
    counts: str = "1                        1                         1",
    amounts: str = "1,000.00             500.00                100.00-                 200.00-                 1,200.00",
    checks_column: bool = True,
    deposits: str = "03/06 03/06          500.00 ONLINE XFER FROM DDA ****1301 ID:000864120",
    charges: str = (
        "03/02 03/02           100.00- MONTHLY SVC CHG "
        "03/03 03/03           200.00- Check No: 000000001234"
    ),
    daily: str = "02/28 $1,000.00 03/02 $900.00 03/03 $700.00\n03/06 $1,200.00",
    summary_table: str = (
        "Account Type Account Number Account Ending Balance "
        "BUSINESS GROWTH CHECKING 1234567890 $1,200.00"
    ),
    summary_title: str = "SUMMARY OF ACCOUNT BALANCE",
    extra_block: str = "",
) -> str:
    legend = (
        "Previous Balance              Deposits/Credits                "
        "Withdrawals/Debits                     Checks Processed                        Ending Balance"
        if checks_column
        else "Previous Balance Deposits/Credits              Withdrawals/Debits Ending Balance"
    )
    return (
        "Page  1 of  4\n"
        "Statement of Accounts\n"
        f"This Statement: {this_statement} Last Statement: {last_statement}\n"
        f"Account:  {account}\n"
        f"{brand}\n"
        "EXAMPLE COMPANY LLC 1 EXAMPLE ST\n"
        f"{summary_title}\n"
        f"{summary_table}\n"
        f"{product} {account} 0152 a {legend}\n"
        f"Count: {counts}\n"
        f"Amount:                   {amounts}\n"
        f"{_RULE} DEPOSITS/CREDITS\n"
        "Posting            Effective Date                 Date Amount                   Description\n"
        f"{deposits}\n"
        f"{_RULE} CHARGES/DEBITS\n"
        "Posting            Effective Date                 Date Amount                   Description\n"
        f"{charges}\n"
        f"{_RULE} CHECKS PROCESSED\n"
        "Number............Date...........................Amount\n"
        "1234         03/03 $200.00\n"
        f"{_RULE} ACTIVITY COUNT\n"
        "During this period Total Items 5\n"
        f"{_RULE} DAILY BALANCE\n"
        "Date.......................................Balance\n"
        f"{daily}\n"
        f"{_RULE} INTEREST\n"
        "Interest Earned This Statement Period $0.00 Number Of Days This Statement Period "
        f"{days} Interest Paid Year-To-Date  2026 $0.00\n"
        f"{extra_block}"
        f"{footer}\n"
    )


#: A second account printing zero for every column and carrying no row.
_INERT_SAVINGS = (
    "BUSINESS SAVINGS 5795685527 0451 Previous Balance Deposits/Credits "
    "Withdrawals/Debits Ending Balance\n"
    "Count:                     0                       0\n"
    "Amount:                    0.00                    0.00                    0.00                   0.00\n"
    f"{_RULE} DEPOSITS/CREDITS\n"
    "There were no transactions this period.\n"
    f"{_RULE} CHARGES/DEBITS\n"
    "There were no transactions this period.\n"
    f"{_RULE} ACTIVITY COUNT\n"
    "During this period Total Items 0\n"
    f"{_RULE} DAILY BALANCE\n"
    "Date.......................................Balance\n"
    "02/28 $0.00\n"
    f"{_RULE} INTEREST\n"
    "Interest Earned This Statement Period $0.00 Number Of Days This Statement Period 32 "
    "Interest Paid Year-To-Date  2026 $0.00\n"
)


# ---------------------------------------------------------------------------
# detection — the issuer, not the trade name
# ---------------------------------------------------------------------------

def test_detects_the_nevada_state_bank_issue():
    assert zions.detect(_document()).claims


def test_detects_the_amegy_bank_issue():
    """The same printed layout under a different trade name. Registering on
    either brand would leave the other unclaimed — the mistake `rbc_french`
    made with its two products."""
    amegy = _document(
        brand=(
            "Direct Inquiries to: 800-000-0000 WWW.AMEGYBANK.COM\n"
            'Amegy Bank - The "A" Bank'
        )
    )
    assert "NSBANK" not in amegy
    assert zions.detect(amegy).claims


def test_neither_trade_name_is_required():
    plain = _document(brand="Direct Inquiries to: 800-000-0000")
    assert "NSBANK" not in plain and "AMEGY" not in plain
    assert zions.detect(plain).claims


def test_the_corporate_footer_alone_is_not_evidence():
    assert not zions.detect(
        "A division of Zions Bancorporation, N.A.\nBeginning Balance\n"
    ).claims


def test_detection_does_not_depend_on_the_filename():
    named = "<!-- SOURCE: Zions Statement of Accounts.pdf -->\nBeginning Balance\n"
    assert not zions.detect(named).claims


# ---------------------------------------------------------------------------
# the summary grid
# ---------------------------------------------------------------------------

def test_reads_the_grid_the_period_and_the_product():
    stmt = zions.parse_zions_statement(_document())
    assert stmt is not None
    assert stmt.bank == "Zions Bancorporation"
    assert stmt.account_number == "1234567890"
    assert stmt.account_name == "BUSINESS GROWTH CHECKING"
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00


def test_the_period_opens_the_day_after_the_previous_statement():
    stmt = zions.parse_zions_statement(_document())
    assert stmt.period_start == "2054-02-28"
    assert stmt.period_end == "2054-03-31"
    assert stmt.days_in_period == 32


def test_a_printed_day_count_that_contradicts_the_two_dates_fails_closed():
    """The bank counts the period's days itself. If that disagrees with the
    span its own dates describe, the period has not been read correctly."""
    assert zions.parse_zions_statement(_document(days="45")) is None


def test_the_debit_total_covers_both_printed_debit_columns():
    stmt = zions.parse_zions_statement(_document())
    assert stmt.stated_total_credits == 500.00
    assert stmt.stated_total_debits == 300.00  # 100.00 withdrawals + 200.00 cheques


def test_the_debit_count_covers_the_same_scope_as_the_debit_total():
    """A count narrower than its own total is what W3 §FIXUPS-1 corrected on
    `first_community`."""
    stmt = zions.parse_zions_statement(_document())
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count == 2  # 1 withdrawal + 1 cheque
    assert sum(1 for t in stmt.transactions if t.amount < 0) == stmt.stated_debit_count
    assert sum(1 for t in stmt.transactions if t.amount > 0) == stmt.stated_credit_count


def test_a_product_renamed_mid_archive_is_still_read():
    """`BUSINESS GROWTH CHECKING` became `BUSINESS ELEVATE CHECKING` inside
    the archive's own date range. What identifies the grid is the printed
    column legend, not the product name."""
    stmt = zions.parse_zions_statement(_document(product="BUSINESS ELEVATE CHECKING"))
    assert stmt is not None
    assert stmt.account_name == "BUSINESS ELEVATE CHECKING"


# ---------------------------------------------------------------------------
# the posting sections
# ---------------------------------------------------------------------------

def test_reads_both_posting_sections_with_the_signs_the_layout_prints():
    stmt = zions.parse_zions_statement(_document())
    assert [t.amount for t in stmt.transactions] == [-100.00, -200.00, 500.00]
    assert [t.direction for t in stmt.transactions] == ["debit", "debit", "credit"]


def test_the_posting_date_column_is_the_posting_date():
    stmt = zions.parse_zions_statement(
        _document(deposits="03/06 03/09          500.00 SOME DEPOSIT")
    )
    assert [t.date for t in stmt.transactions if t.amount > 0] == ["2054-03-06"]


def test_a_row_whose_sign_contradicts_its_section_fails_closed():
    """The section IS the direction column and the row prints the sign that
    column implies; where they disagree the row was not read correctly."""
    assert zions.parse_zions_statement(
        _document(
            charges=(
                "03/02 03/02           100.00 MONTHLY SVC CHG "
                "03/03 03/03           200.00- Check No: 000000001234"
            )
        )
    ) is None


def test_cheques_are_published_once_not_twice():
    """`CHECKS PROCESSED` is a register of cheques already posted in
    `CHARGES/DEBITS`. Reading it would publish each of them a second time."""
    stmt = zions.parse_zions_statement(_document())
    cheques = [t for t in stmt.transactions if "Check No" in t.description]
    assert len(cheques) == 1
    assert len(stmt.transactions) == 3
    assert sum(-t.amount for t in stmt.transactions if t.amount < 0) == 300.00


def test_the_bank_printed_daily_balances_are_published():
    stmt = zions.parse_zions_statement(_document())
    assert [(d.date, d.balance) for d in stmt.stated_daily_balances] == [
        ("2054-02-28", 1000.00),
        ("2054-03-02", 900.00),
        ("2054-03-03", 700.00),
        ("2054-03-06", 1200.00),
    ]


def test_total_items_is_not_used_as_a_count_oracle():
    """`During this period Total Items 5` exceeds the summary's own counts
    here, as it does across the family (measured: by between 0 and 12). It is
    not the transaction count and is never read."""
    stmt = zions.parse_zions_statement(_document())
    assert stmt.stated_credit_count + stmt.stated_debit_count == 3
    assert "Total Items 5" in _document()


def test_a_grid_with_no_ledger_is_not_a_statement():
    assert zions.parse_zions_statement(
        _document(
            deposits="There were no transactions this period.",
            charges="There were no transactions this period.",
        )
    ) is None


# ---------------------------------------------------------------------------
# more than one account on one PDF
# ---------------------------------------------------------------------------

def test_an_inert_second_account_does_not_block_the_funded_one():
    stmt = zions.parse_zions_statement(
        _document(
            summary_title="SUMMARY OF ACCOUNT BALANCES",
            summary_table=(
                "Account Type Account Number Account Ending Balance "
                "BUSINESS GROWTH CHECKING 1234567890 $1,200.00 "
                "BUSINESS SAVINGS 5795685527 $0.00 Total $1,200.00"
            ),
            extra_block=_INERT_SAVINGS,
        )
    )
    assert stmt is not None
    assert stmt.account_number == "1234567890"
    assert len(stmt.transactions) == 3


def test_a_four_column_grid_without_a_cheque_column_is_read():
    """A savings product prints no `Checks Processed` column, so its grid
    carries four amounts and two counts rather than five and three."""
    stmt = zions.parse_zions_statement(
        _document(
            checks_column=False,
            counts="1                       1",
            amounts="1,000.00             500.00                300.00-                 1,200.00",
            charges="03/02 03/02           300.00- MONTHLY SVC CHG",
        )
    )
    assert stmt is not None
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_debit_count == 1


def test_two_funded_accounts_on_one_pdf_fail_closed():
    funded_second = _INERT_SAVINGS.replace(
        "Amount:                    0.00                    0.00                    0.00                   0.00",
        "Amount:                    50.00                    10.00                    0.00                   60.00",
    ).replace(
        f"{_RULE} DEPOSITS/CREDITS\nThere were no transactions this period.",
        f"{_RULE} DEPOSITS/CREDITS\n03/04 03/04          10.00 SOME OTHER DEPOSIT",
    )
    assert zions.parse_zions_statement(
        _document(
            summary_title="SUMMARY OF ACCOUNT BALANCES", extra_block=funded_second
        )
    ) is None


# ---------------------------------------------------------------------------
# the integrity check
# ---------------------------------------------------------------------------

def test_a_total_that_agrees_with_the_published_balance_raises_nothing():
    markdown = _document(
        summary_title="SUMMARY OF ACCOUNT BALANCES",
        summary_table=(
            "Account Type Account Number Account Ending Balance "
            "BUSINESS GROWTH CHECKING 1234567890 $1,200.00 "
            "BUSINESS SAVINGS 5795685527 $0.00 Total $1,200.00"
        ),
        extra_block=_INERT_SAVINGS,
    )
    stmt = zions.parse_zions_statement(markdown)
    assert zions.balance_summary_contradictions(markdown, stmt) == []


def test_a_total_that_exceeds_the_published_balance_is_reported():
    """If the accounts treated as inert were not inert, the published figure
    is a part presented as the whole."""
    markdown = _document(
        summary_title="SUMMARY OF ACCOUNT BALANCES",
        summary_table=(
            "Account Type Account Number Account Ending Balance "
            "BUSINESS GROWTH CHECKING 1234567890 $1,200.00 "
            "BUSINESS SAVINGS 5795685527 $0.00 Total $9,999.00"
        ),
        extra_block=_INERT_SAVINGS,
    )
    stmt = zions.parse_zions_statement(markdown)
    flags = zions.balance_summary_contradictions(markdown, stmt)
    assert flags and "SUMMARY OF ACCOUNT BALANCES total" in flags[0]


def test_the_integrity_check_is_wired_to_the_registration():
    from analysis.parser_registry import registrations
    from analysis.parser_registry_entries import load

    load()
    entry = next(r for r in registrations() if r.id == "zions")
    assert zions.balance_summary_contradictions in entry.integrity_checks


def test_the_published_statement_is_a_statement_object():
    assert isinstance(zions.parse_zions_statement(_document()), Statement)
