"""W3 §COREISS2: the core processor's `Activity Summary` running-balance issue.

Every figure, name, date and account token below is INVENTED. What is
reproduced is the printed GRAMMAR — the box, the product line's leading
counts, the duplex mailer sheet, the reconciliation worksheet, the imaging
sequence numbers that land between two postings, the cheque recap and the
trailing image index — because that is what the reader is registered on.

Each test is named after the gate it kills; the mutation table in W3 §COREISS2
records which mutant each one caught.
"""
from __future__ import annotations

import pytest

from analysis import core_processor_activity_summary as reader

STATEMENT = """
--- Page 1 ---

!Ab1C2 mn(_ ZE+ 4JB5S9:z Y(MV *Z@/S + AAAAAAAAAAAAAAAAAAAAAA
P O Box 1, Sample Town, XX 00000 000.000.0000
000000-00A**000000 SAMPLE HOLDER LLC 1 SAMPLE STREET SAMPLE TOWN XX 00000
00000001

--- Page 2 ---

00000002

--- Page 3 ---

!Ab1C2 mn*V#Y H+ 4JB5 T95{< tEV *Z + AAAAAAAAAAAAAAAAAAAAAA
P O Box 1, Sample Town, XX 00000 000.000.0000
Statement of Account Statement Dates:  4/01/26 thru 4/30/26
Page:  2  of 5
Activity Summary
Account Number 1234567 Days in Cycle 30 Average Ledger Balance $300.00 Avg Collected Balance $250.00
Sample Free Business Checking Beginning Balance $1,000.00 2 Deposits/Credits $900.00 3 Checks/Debits $1,700.00 Service Charge $0.00 Interest Paid $0.00 Balance this Statement $200.00
Statement Balance $200.00
Debits $1,700.00
Credits $900.00
Total For This Period Total Year-To-Date
Overdraft item fees year to date $0.00 $0.00 Return item fees year to date $0.00 $0.00
Account Activity
Date Description Amount Balance
4/01 SAMPLE INBOUND TRANSFER $400.00 $1,400.00
4/02 SAMPLE STORE $5.00 OFF SAMPLE TOWN 04/01/26 x0000 TXID:0000000000000000:00 -$200.00 $1,200.00
00000003
4/03 INCLEARING CHECK 101 -$1,400.00 -$200.00

--- Page 4 ---

IN CASE OF ERRORS OR QUESTIONS ABOUT YOUR ELECTRONIC TRANSFERS write us or telephone us at the location and telephone number that appears on the front of this statement as soon as you can.
MONTH                                    20 ACCOUNT RECONCILIATION
BALANCE SHOWN ON THIS STATEMENT
$
TOTAL  $
00000004

--- Page 5 ---

Account Number:  1234567 Statement Dates:  4/01/26 thru 4/30/26 Page:  3  of  5 !Ab1C2 mn(]e G+
Account Activity (Continued)
Date Description Amount Balance
4/04 SAMPLE MAINTENANCE ITEM -$100.00 -$300.00
4/05 SAMPLE INBOUND TRANSFER $500.00 $200.00
Checks in Number Order
Date Check No Amount Date Check No Amount Date Check No Amount
4/03 101 $1,400.00
* Indicates Break in Check Number Sequence
00000005

--- Page 6 ---

Account Number:  1234567 Statement Dates:  4/01/26 thru 4/30/26
1234567 04/01/26 0 $400.00 1234567 04/05/26 0 $500.00
1234567 04/03/26 101 $1400.00
00000007
"""


def parsed(text: str = STATEMENT):
    return reader.parse_core_processor_activity_summary_statement(text)


def test_the_six_printed_oracles_close_and_the_statement_publishes():
    stmt = parsed()
    assert stmt is not None
    assert (stmt.period_start, stmt.period_end, stmt.days_in_period) == (
        "2026-04-01", "2026-04-30", 30,
    )
    assert (stmt.beginning_balance, stmt.ending_balance) == (1000.00, 200.00)
    assert (stmt.stated_credit_count, stmt.stated_debit_count) == (2, 3)
    assert (stmt.stated_total_credits, stmt.stated_total_debits) == (900.00, 1700.00)
    assert stmt.account_number == "1234567"
    assert stmt.account_name == "Sample Free Business Checking"
    assert stmt.bank_reported_average_balance == 300.00
    assert stmt.bank_reported_average_label == "Average Ledger Balance"
    assert len(stmt.transactions) == 5
    assert [txn.running_balance for txn in stmt.transactions] == [
        1400.00, 1200.00, -200.00, -300.00, 200.00,
    ]


def test_the_issuer_is_not_printed_so_no_bank_is_published():
    """A post-office box and a telephone number are not an identity."""
    assert parsed().bank is None


def test_the_currency_stays_at_the_schema_default():
    stmt = parsed()
    assert (stmt.currency, stmt.currency_source) == ("USD", "schema_default")


def test_the_leading_counts_cohort_that_prints_previous_balance_is_not_claimed():
    """`Days in Cycle` inside an `Activity Summary` box is the anti-collision
    clause against the archive's large `Days in the statement period` cohort."""
    other = (
        "Statement of Account\n"
        "Account Number 1234567 Statement Dates 4/01/26 thru 4/30/26 "
        "Previous Balance 1,000.00 Days in the statement period 30 "
        "2 Deposits/Credits $900.00 3 Checks/Debits $1,700.00 "
        "Service Charge $0.00 Current Balance 200.00\n"
    )
    assert reader.detect(other).claims is False


def test_the_box_alone_without_the_cycle_length_is_not_claimed():
    text = STATEMENT.replace("Days in Cycle 30", "Days in Period 30")
    assert reader.detect(text).claims is False


def test_the_box_heading_must_be_printed_on_its_own_line():
    """A statement that MENTIONS an activity summary in its disclosure prose
    has not printed the box; only a line that is the heading has."""
    text = STATEMENT.replace(
        "\nActivity Summary\n", "\nSee your Activity Summary below for details.\n", 1
    )
    assert reader.detect(text).claims is False


def test_the_product_line_without_the_closing_label_is_not_claimed():
    text = STATEMENT.replace("Balance this Statement $200.00", "Current Balance $200.00")
    assert reader.detect(text).claims is False


def test_a_cycle_length_that_contradicts_the_printed_dates_refuses():
    """The cycle length is the denominator of the canonical calendar-day ADB,
    and the dates are its second, independent printing."""
    text = STATEMENT.replace("Days in Cycle 30", "Days in Cycle 31")
    assert parsed(text) is None


def test_the_restated_trio_must_agree_with_the_box():
    for before, after in (
        ("Statement Balance $200.00", "Statement Balance $250.00"),
        ("Debits $1,700.00", "Debits $1,750.00"),
        ("Credits $900.00", "Credits $950.00"),
    ):
        assert parsed(STATEMENT.replace(before, after, 1)) is None


def test_the_summary_identity_must_close_before_a_row_is_read():
    text = STATEMENT.replace(
        "Interest Paid $0.00 Balance this Statement $200.00",
        "Interest Paid $0.00 Balance this Statement $210.00",
    ).replace("Statement Balance $200.00", "Statement Balance $210.00")
    assert parsed(text) is None


def test_the_identity_is_checked_independently_of_the_chain():
    """Printed interest that the closing balance does not account for.

    Both counts, both totals, the restated trio and the whole running-balance
    chain still close on this input, so only the identity can refuse it.
    """
    text = STATEMENT.replace(
        "Service Charge $0.00 Interest Paid $0.00", "Service Charge $0.00 Interest Paid $50.00"
    )
    assert parsed(text) is None


def test_both_printed_counts_are_checked_independently_of_the_totals():
    """One posting printed as two that sum to it, chained correctly: every
    total and the whole chain still close, and only the count disagrees."""
    text = STATEMENT.replace(
        "4/01 SAMPLE INBOUND TRANSFER $400.00 $1,400.00",
        "4/01 SAMPLE INBOUND ONE $150.00 $1,150.00\n"
        "4/01 SAMPLE INBOUND TWO $250.00 $1,400.00",
    )
    assert parsed(text) is None


def test_both_printed_totals_are_checked_independently_of_the_identity():
    """Both printed totals moved by the same amount, in the box and in the
    restatement: the identity still closes and both counts still match."""
    text = (
        STATEMENT
        .replace("2 Deposits/Credits $900.00", "2 Deposits/Credits $850.00")
        .replace("3 Checks/Debits $1,700.00", "3 Checks/Debits $1,650.00")
        .replace("Debits $1,700.00", "Debits $1,650.00")
        .replace("Credits $900.00", "Credits $850.00")
    )
    assert parsed(text) is None


def test_a_break_in_the_running_balance_chain_refuses():
    text = STATEMENT.replace("-$200.00 $1,200.00", "-$200.00 $1,250.00")
    assert parsed(text) is None


def test_the_minus_leads_the_sigil_so_overdrawn_rows_are_not_lost():
    """`-$1,234.56`, never `1,234.56-`: a reader anchored on `$` loses exactly
    the overdraft rows, which is the one tokenizer trap in this family."""
    stmt = parsed()
    overdrawn = [txn for txn in stmt.transactions if txn.running_balance < 0]
    assert [txn.amount for txn in overdrawn] == [-1400.00, -100.00]
    assert [txn.running_balance for txn in overdrawn] == [-200.00, -300.00]


def test_an_imaging_sequence_number_between_two_rows_is_skipped_not_refused():
    """The processor emits a bare sequence number once per physical page and
    sometimes lands it BETWEEN two postings, so it must be filtered as a LINE."""
    assert "00000003" in reader._ledger(STATEMENT)
    stmt = parsed()
    assert len(stmt.transactions) == 5


def test_a_page_break_closes_the_ledger_region_until_the_banner_reprints():
    """The reconciliation worksheet prints bare `$` tokens on the back of a
    ledger page; only the template's own re-printed banner reopens the region."""
    region = reader._ledger(STATEMENT)
    assert "BALANCE SHOWN ON THIS STATEMENT" not in region
    assert "TOTAL  $" not in region
    assert any(line.startswith("4/05") for line in region)


def test_the_ledger_is_cut_at_the_cheque_recap_banner():
    """The recap grid and the trailing image index both RESTATE postings that
    are already in the ledger."""
    region = reader._ledger(STATEMENT)
    assert not any("101 $1,400.00" in line for line in region)
    assert not any(line.startswith("1234567 04/") for line in region)


def test_a_money_token_inside_a_descriptor_is_not_the_row_amount():
    """The running balance is always last and the amount always second-to-last,
    so the description is read greedily."""
    stmt = parsed()
    carded = [txn for txn in stmt.transactions if "OFF SAMPLE TOWN" in txn.description]
    assert len(carded) == 1
    assert (carded[0].amount, carded[0].running_balance) == (-200.00, 1200.00)
    assert "$5.00" in carded[0].description


def test_a_zero_amount_row_refuses_even_when_every_other_oracle_closes():
    """A zero row carries no sign, and this ledger prints one undivided
    section, so there is nothing to recover its direction from.

    The printed debit count and total are moved to ACCOMMODATE the extra row
    here, so the chain, the identity, the restated trio and both totals all
    still close: only the refusal itself can turn this document away.
    """
    text = (
        STATEMENT
        .replace("3 Checks/Debits $1,700.00", "4 Checks/Debits $1,700.00")
        .replace(
            "4/04 SAMPLE MAINTENANCE ITEM -$100.00 -$300.00",
            "4/04 SAMPLE MAINTENANCE ITEM -$100.00 -$300.00\n"
            "4/04 SAMPLE ZERO ITEM $0.00 -$300.00",
        )
    )
    assert parsed(text) is None


def test_two_activity_summary_boxes_refuse_rather_than_publishing_one_account():
    box = (
        "Activity Summary\n"
        "Account Number 7654321 Days in Cycle 30 "
        "Average Ledger Balance $300.00 Avg Collected Balance $250.00\n"
    )
    assert parsed(STATEMENT.replace("Account Activity\n", box + "Account Activity\n", 1)) is None


def test_the_last_row_must_land_on_the_printed_closing_balance():
    """Interest credited OUTSIDE the ledger, which is the only shape that can
    separate this check from the identity.

    With `Interest Paid` and `Service Charge` both zero — as every archive
    document of this family prints them — the identity plus the two totals
    plus the chain already force the last balance onto the closing figure, so
    this gate is invisible there. It is the gate that fires the day a fee or a
    credit is printed in the box and not in the ledger.
    """
    text = (
        STATEMENT
        .replace("Service Charge $0.00 Interest Paid $0.00", "Service Charge $0.00 Interest Paid $50.00")
        .replace("Balance this Statement $200.00", "Balance this Statement $250.00")
        .replace("Statement Balance $200.00", "Statement Balance $250.00")
    )
    assert parsed(text) is None


def test_the_reader_never_reads_a_page_index_so_the_mailer_sheet_is_harmless():
    """Two archive members waste their first physical sheet on a mailer, so the
    printed `Page: n of m` starts at 2 on PDF page 3."""
    stmt = parsed()
    extra = STATEMENT.replace("--- Page 1 ---", "--- Page 1 ---\n\n00000000\n\n--- Page 1b ---", 1)
    again = parsed(extra)
    assert again is not None
    assert again.model_dump() == stmt.model_dump()


def test_a_header_with_no_ledger_publishes_nothing():
    header = STATEMENT.split("Account Activity")[0]
    assert reader.detect(header).claims is True
    assert parsed(header) is None


@pytest.mark.parametrize(
    "mangled",
    [
        "",
        "Statement of Account",
        "Activity Summary\nDays in Cycle 30\n",
        STATEMENT.replace("$", ""),
        STATEMENT.replace("4/01/26", "notadate"),
        STATEMENT.replace("Days in Cycle 30", "Days in Cycle 0"),
    ],
)
def test_no_input_makes_this_reader_raise(mangled):
    assert reader.parse_core_processor_activity_summary_statement(mangled) is None
