"""W3 §COREISS2: the core processor's SIGNED-COUNTS `Statement of Account`.

Every figure, name, date and account token below is INVENTED. The archive's
own documents are never quoted here — what is reproduced is the printed
GRAMMAR (label wording, section order, sign placement, page furniture), which
is what the reader is registered on.

Each test is named after the gate it kills, and the mutation table in W3
§COREISS2 records which mutant each one caught.
"""
from __future__ import annotations

from datetime import date

import pytest

from analysis import core_processor_signed_counts as reader

#: The two balances are separated from their dates by U+00A0 on every archive
#: document of this family, so the fixture prints one of them that way and the
#: other with an ordinary space: `\s` covers both and neither is asserted.
NBSP = " "

STATEMENT = f"""
--- Page 1 ---

Statement Date: 3/28/26
Return Service Requested Primary Account Sample Holder XXXXXX0000
SAMPLE HOLDER LLC 1 SAMPLE STREET SAMPLE TOWN XX 00000-0000
Statement of Account SAMPLE BUSINESS CHECKING Account Title: Sample Holder LLC
Beginning Balance{NBSP}3/02/26 $ 1,000.00
Summary
Credits (3) +$1,300.00 Interest Paid +$.00 Debits (4) -$700.00
Ending Balance 3/31/26 $ 1,600.00
Deposits & Credits Date Description Amount
3/02 ALPHA INBOUND CCD CO#0000000000 26/03/02 ID # - 000000 TRACE # - 000000 $500.00
3/03 BETA INBOUND $300.00 3/04 GAMMA INBOUND $500.00
Debits & Withdrawals Date Description Amount
3/02 SAMPLE ANALYSIS CHARGE $100.00-
Page 1

--- Page 2 (empty) ---

--- Page 3 ---

Account Number: XXXXXX0000
Date Description Amount 3/03 FR00000000000 CK DEP 3/1 CK DEP AS $250.00 S/B$150.00 $100.00-
3/05 A DESCRIPTOR LONG ENOUGH THAT ITS AMOUNT IS PUSHED ONTO THE NEXT LINE
$200.00-
Checks in Number Order Date Check Number Amount
3/04 101 $300.00 3/06 102 -See above- (*) Indicates gap in check number sequence
Summary Average Ledger Bal $1,500.00 Interest Paid $.00 Days in the Statement Period 30 Average Collected Bal $1,500.00 Service Charge(s) $.00 Images Included 2
Daily Balance Information 3/02 1,400.00 3/03 1,600.00 3/04 1,800.00 3/05 1,600.00 3/06 1,600.00 3/09 1,600.00
Page 3

--- Page 4 ---

This page intentionally left blank.
Page 4

--- Page 5 ---

Date 3/28/26 Primary Acct No. XXXXXX0000
Check Page
#101 03/04/2026 $300.00
Page 5
"""


def parsed(text: str = STATEMENT):
    return reader.parse_core_processor_signed_counts_statement(text)


def test_the_five_printed_oracles_close_and_the_statement_publishes():
    stmt = parsed()
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end, stmt.days_in_period) == (
        "2026-03-02", "2026-03-31", 30,
    )
    assert (stmt.beginning_balance, stmt.ending_balance) == (1000.00, 1600.00)
    assert (stmt.stated_credit_count, stmt.stated_debit_count) == (3, 4)
    assert (stmt.stated_total_credits, stmt.stated_total_debits) == (1300.00, 700.00)
    assert len(stmt.transactions) == 7
    assert [snapshot.date for snapshot in stmt.stated_daily_balances] == [
        "2026-03-02", "2026-03-03", "2026-03-04",
        "2026-03-05", "2026-03-06", "2026-03-09",
    ]
    assert stmt.bank_reported_average_balance == 1500.00
    assert stmt.bank_reported_average_label == "Average Ledger Bal"


def test_the_issuer_is_not_printed_so_no_bank_is_published():
    """This template carries no masthead, no FDIC line and no web address.

    An unnamed issuer is a gap a human can close; a guessed one is a finding
    nobody knows to question.
    """
    assert parsed().bank is None


def test_the_currency_stays_at_the_schema_default():
    """No issuer means no issuer jurisdiction, and a jurisdiction default is
    affirmative evidence rather than an absence rule (ratified doctrine)."""
    stmt = parsed()
    assert (stmt.currency, stmt.currency_source) == ("USD", "schema_default")


def test_the_slash_prefixed_counts_of_another_registration_are_not_claimed():
    """`Deposits/Credits (28) $x` is `fiserv_premier`'s clause, not this one.

    The bare label and the explicit SIGN are both required, and the lookbehind
    is what keeps `DEPOSITS/CREDITS (N)` from satisfying `CREDITS (N)`.
    """
    other = (
        "Statement of Account\n"
        "Previous Balance $1,000.00 Deposits/Credits (3) +$1,300.00 "
        "Checks/Debits (4) -$700.00 Ending Balance $1,600.00\n"
        "Beginning Balance 3/02/26 $ 1,000.00\n"
        "Ending Balance 3/31/26 $ 1,600.00\n"
    )
    assert reader.detect(other).claims is False


@pytest.mark.parametrize(
    "summary",
    [
        "Deposits/Credits (3) +$1,300.00 Interest Paid +$.00 Debits (4) -$700.00",
        "Credits (3) +$1,300.00 Interest Paid +$.00 Checks/Debits (4) -$700.00",
    ],
    ids=["credit-label-slash-prefixed", "debit-label-slash-prefixed"],
)
def test_a_slash_prefixed_label_does_not_satisfy_the_bare_counts_marker(summary):
    """Each label carries its own lookbehind, so each is tested on its own.

    Tested together, either lookbehind could be deleted without the
    conjunction noticing — the other half would still refuse the document.
    """
    text = STATEMENT.replace(
        "Credits (3) +$1,300.00 Interest Paid +$.00 Debits (4) -$700.00", summary
    )
    assert reader.detect(text).claims is False


def test_an_unsigned_credit_total_does_not_satisfy_the_counts_marker():
    text = STATEMENT.replace("Credits (3) +$1,300.00", "Credits (3) $1,300.00")
    assert reader.detect(text).claims is False


def test_an_unsigned_debit_total_does_not_satisfy_the_counts_marker():
    text = STATEMENT.replace("Debits (4) -$700.00", "Debits (4) $700.00")
    assert reader.detect(text).claims is False


def test_undated_balances_do_not_satisfy_the_period_marker():
    text = STATEMENT.replace(f"Beginning Balance{NBSP}3/02/26", "Beginning Balance")
    assert reader.detect(text).claims is False


def test_the_period_is_the_dated_balances_and_never_the_statement_date():
    """`Statement Date:` disagrees with the true period on four of the eight
    archive documents, and the periods do not align to calendar months."""
    text = STATEMENT.replace("Statement Date: 3/28/26", "Statement Date: 9/09/26")
    stmt = parsed(text)
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end) == ("2026-03-02", "2026-03-31")


def test_a_printed_length_that_contradicts_the_dated_span_refuses():
    text = STATEMENT.replace("Days in the Statement Period 30", "Days in the Statement Period 31")
    assert parsed(text) is None


def test_the_summary_identity_must_close_before_a_row_is_read():
    text = STATEMENT.replace("Ending Balance 3/31/26 $ 1,600.00", "Ending Balance 3/31/26 $ 1,650.00")
    assert parsed(text) is None


def test_the_identity_is_checked_independently_of_the_daily_grid():
    """Printed interest that the closing balance does not account for.

    Both counts, both totals and every day of the grid still close on this
    input, so only the summary's own identity can refuse it.
    """
    text = STATEMENT.replace("Interest Paid +$.00", "Interest Paid +$50.00")
    assert parsed(text) is None


def test_the_grid_is_checked_independently_of_the_summary_identity():
    """The mirror: the identity closes on the printed interest, and the grid
    ends one interest payment short of the printed closing balance."""
    text = (
        STATEMENT
        .replace("Interest Paid +$.00", "Interest Paid +$50.00")
        .replace("Ending Balance 3/31/26 $ 1,600.00", "Ending Balance 3/31/26 $ 1,650.00")
    )
    assert parsed(text) is None


def test_the_credit_count_is_checked_independently_of_the_credit_total():
    """One posting printed as two that sum to it: every total still closes,
    the grid still closes, and only the printed count disagrees."""
    text = STATEMENT.replace(
        "3/02 ALPHA INBOUND CCD CO#0000000000 26/03/02 ID # - 000000 TRACE # - 000000 $500.00",
        "3/02 ALPHA INBOUND ONE $200.00 3/02 ALPHA INBOUND TWO $300.00",
    )
    assert parsed(text) is None


def test_both_printed_totals_are_checked_independently_of_the_identity():
    """Both printed totals moved by the same amount: the identity still
    closes, the grid still closes, both counts still match."""
    text = (
        STATEMENT
        .replace("Credits (3) +$1,300.00", "Credits (3) +$1,250.00")
        .replace("Debits (4) -$700.00", "Debits (4) -$650.00")
    )
    assert parsed(text) is None


def test_the_cheque_section_is_counted_on_the_debit_side():
    """The printed debit count and total INCLUDE `Checks in Number Order`.

    Reading only `Debits & Withdrawals` leaves every archive document of this
    family short by nine to nineteen items.
    """
    stmt = parsed()
    debits = [txn for txn in stmt.transactions if txn.direction == "debit"]
    assert len(debits) == 4
    assert sorted(-txn.amount for txn in debits) == [100.00, 100.00, 200.00, 300.00]
    without = STATEMENT.replace("Checks in Number Order Date Check Number Amount", "Cheque recap")
    assert parsed(without) is None


def test_a_reference_amount_inside_a_description_is_never_the_row_amount():
    """The correction row prints two money tokens before its own.

    A "first amount on the line" rule reads the first reference and a "last
    amount" rule reads the second; only the TRAILING MINUS survives.
    """
    stmt = parsed()
    correction = [txn for txn in stmt.transactions if "CK DEP" in txn.description]
    assert len(correction) == 1
    assert correction[0].amount == -100.00
    assert "$250.00" in correction[0].description and "S/B$150.00" in correction[0].description


def test_a_credit_description_cannot_cross_a_money_token():
    """With an unconstrained description the engine spans a debit-shaped token
    into the FOLLOWING posting's amount and merges two rows into one — dated
    from the first and valued from the second."""
    text = STATEMENT.replace(
        "3/03 BETA INBOUND $300.00 3/04 GAMMA INBOUND $500.00",
        "3/03 BETA INBOUND $300.00- 3/04 GAMMA INBOUND $500.00",
    )
    rows = reader._rows(
        reader._sections(text)["credit"], reader._CREDIT_ROW_RE,
        date(2026, 3, 2), date(2026, 3, 31), 1,
    )
    assert [(row.date, row.amount) for row in rows] == [
        ("2026-03-02", 500.00), ("2026-03-04", 500.00),
    ]
    assert parsed(text) is None


def test_two_postings_concatenated_onto_one_line_are_two_rows():
    stmt = parsed()
    credits = [txn for txn in stmt.transactions if txn.direction == "credit"]
    assert len(credits) == 3
    assert sorted(txn.amount for txn in credits) == [300.00, 500.00, 500.00]


def test_an_amount_pushed_onto_the_following_line_still_belongs_to_its_row():
    stmt = parsed()
    wrapped = [txn for txn in stmt.transactions if "PUSHED ONTO THE NEXT LINE" in txn.description]
    assert len(wrapped) == 1
    assert (wrapped[0].date, wrapped[0].amount) == ("2026-03-05", -200.00)


def test_a_cheque_printed_without_an_amount_is_not_a_posting():
    """`-See above-` marks a cheque already posted in the ledger, and the
    printed debit count excludes it."""
    stmt = parsed()
    assert len([txn for txn in stmt.transactions if txn.description.startswith("10")]) == 1


def test_the_ledger_is_terminated_by_the_printed_statistics():
    """`Summary Average Ledger Bal` ends the ledger and cannot be resumed, so
    the cheque-image captions after it are never postings."""
    sections = reader._sections(STATEMENT)
    assert "#101" not in sections["check"] and "#101" not in sections["debit"]
    assert sections["daily"].startswith("3/02")
    unterminated = STATEMENT.replace("Summary Average Ledger Bal", "Statistics Average Ledger Bal")
    assert parsed(unterminated) is None


def test_a_page_break_suspends_a_section_and_only_the_column_header_reopens_it():
    sections = reader._sections(STATEMENT)
    assert "Account Number: XXXXXX0000" not in sections["debit"]
    assert "CK DEP" in sections["debit"]
    orphaned = STATEMENT.replace(
        "Date Description Amount 3/03 FR00000000000", "3/03 FR00000000000"
    )
    assert parsed(orphaned) is None


def test_a_row_on_a_day_the_grid_never_prints_refuses_even_when_both_totals_close():
    """Counts and totals gate the ledger as a whole; only the grid binds a row
    to a DAY, and a wrong day is a wrong average daily balance."""
    text = (
        STATEMENT
        .replace("Credits (3) +$1,300.00", "Credits (4) +$1,350.00")
        .replace("Debits (4) -$700.00", "Debits (5) -$750.00")
        .replace("3/03 BETA INBOUND $300.00", "3/10 EPSILON INBOUND $50.00 3/03 BETA INBOUND $300.00")
        .replace("3/02 SAMPLE ANALYSIS CHARGE $100.00-", "3/02 SAMPLE ANALYSIS CHARGE $100.00- 3/10 ZETA CHARGE $50.00-")
    )
    assert parsed(text) is None


def test_the_grid_must_end_on_the_printed_closing_balance():
    text = STATEMENT.replace("3/05 1,600.00", "3/05 1,700.00")
    assert parsed(text) is None


def test_a_grid_printed_out_of_order_refuses():
    """Two carry-forward days carrying the same balance: the walk cannot see
    the swap, so only the ordering check can."""
    text = STATEMENT.replace(
        "3/06 1,600.00 3/09 1,600.00", "3/09 1,600.00 3/06 1,600.00"
    )
    assert parsed(text) is None


def test_a_mangled_date_token_refuses_rather_than_raising():
    text = STATEMENT.replace("3/02 SAMPLE ANALYSIS CHARGE", "3/00 SAMPLE ANALYSIS CHARGE")
    assert parsed(text) is None


def test_two_account_masks_under_a_label_publish_no_account_number():
    text = STATEMENT.replace("Account Number: XXXXXX0000", "Account Number: XXXXXX1111")
    stmt = parsed(text)
    assert stmt is not None and stmt.account_number is None


def test_the_product_is_published_and_the_holder_is_the_name_of_last_resort():
    stmt = parsed()
    assert stmt.account_name == "SAMPLE BUSINESS CHECKING"
    bare = STATEMENT.replace(
        "Statement of Account SAMPLE BUSINESS CHECKING Account Title: Sample Holder LLC",
        "Statement of Account Account Title: Sample Holder LLC",
    )
    assert parsed(bare).account_name == "Sample Holder LLC"


def test_a_header_with_no_ledger_publishes_nothing():
    header = STATEMENT.split("Deposits & Credits")[0]
    assert reader.detect(header).claims is True
    assert parsed(header) is None


@pytest.mark.parametrize(
    "mangled",
    [
        "",
        "Statement of Account",
        "Credits (3) +$1,300.00 Debits (4) -$700.00",
        STATEMENT.replace("$", ""),
        STATEMENT.replace("3/02", "notadate"),
    ],
)
def test_no_input_makes_this_reader_raise(mangled):
    assert reader.parse_core_processor_signed_counts_statement(mangled) is None
