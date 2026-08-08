"""Bank of America native-layout families (W3 Track A, cell 4).

One fixture per structural family found in the `bank_of_america` withheld
population, plus the negative fixtures that constrain each new rule. Every
document here is synthetic: no archive bytes, no customer, and no amount or
date copied from a real statement. What is reproduced is the *shape* the bank
prints — which is the thing the parser is allowed to know.

The families are recorded in `docs/moneythumb-replacement/W3_TRACKA_LOG.md`
(§BOFA).
"""
from __future__ import annotations

import pytest

from analysis.bofa import parse_bofa_statement, repair_bofa_summary
from analysis.reconcile import reconcile

BUSINESS_SUMMARY = """
bankofamerica.com
Bank of America, N.A.
Your Business Advantage Fundamentals Banking
for January 1, 2026 to January 31, 2026 Account number: 1111 2222 3333
Account summary
Beginning balance on January 1, 2026 $1,000.00
# of deposits/credits: {credits_n}
Deposits and other credits {credits}
# of withdrawals/debits: {debits_n}
Withdrawals and other debits -{debits}
# of days in cycle: 31
Checks -{checks}
Service fees -{fees}
Ending balance on January 31, 2026 ${ending}
Your checking account
"""

CONSUMER_SUMMARY = """
bankofamerica.com
Bank of America, N.A.
Your Adv Plus Banking
for January 1, 2026 to January 31, 2026 Account number: 1111 2222 3333
Account summary
Beginning balance on January 1, 2026 $1,000.00
Deposits and other additions {credits}
ATM and debit card subtractions -{atm}
Other subtractions -{other}
Checks -0.00
Service fees -0.00
Ending balance on January 31, 2026 ${ending}
Your checking account
"""


def business(*, credits="0.00", debits="0.00", checks="0.00", fees="0.00",
             ending="1,000.00", credits_n=0, debits_n=0, body="") -> str:
    return BUSINESS_SUMMARY.format(
        credits=credits, debits=debits, checks=checks, fees=fees, ending=ending,
        credits_n=credits_n, debits_n=debits_n,
    ) + body


def amounts(stmt) -> list[float]:
    return [t.amount for t in stmt.transactions]


# ---------------------------------------------------------------------------
# F1 — a date-shaped token inside the description
# ---------------------------------------------------------------------------

def test_f1_a_wire_detail_date_does_not_open_a_row():
    """`PMT DET:… 26/02/03 …` is printed inside the description of ONE row
    whose Amount cell wraps onto the next line. Segmenting on any date-shaped
    token split that row in two and lost both halves."""
    md = business(credits="10,300.00", credits_n=1, ending="11,300.00", body="""
Deposits and other credits Date Description Amount
01/03/26 WIRE TYPE:WIRE IN DATE: 260103 TRN:2026010300000001 ORIG:A COUNTERPARTY ID:000000001 PMT DET:BOH OF 26/01/03 /CATPURP/CTRC
10,300.00
Total deposits and other credits $10,300.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [10300.0]
    assert stmt.transactions[0].date == "2026-01-03"
    assert "/CATPURP/CTRC" in stmt.transactions[0].description


def test_f1_an_adjustment_row_carries_its_own_reference_date():
    """`Temporary Credit Adjustment on <date> <amount>` is one printed line."""
    md = business(credits="14.70", credits_n=1, ending="1,014.70", body="""
Deposits and other credits Date Description Amount
01/31/26 Temporary Credit Adjustment on 01/28/26 14.70
Total deposits and other credits $14.70
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [14.7]
    assert stmt.transactions[0].date == "2026-01-31"      # the DATE column
    assert stmt.transactions[0].description == "Temporary Credit Adjustment on 01/28/26"


def test_f1_negative_a_date_that_does_start_a_line_still_starts_a_row():
    md = business(credits="30.00", credits_n=2, ending="1,030.00", body="""
Deposits and other credits Date Description Amount
01/05/26 Deposit one 10.00
01/06/26 Deposit two 20.00
Total deposits and other credits $30.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [10.0, 20.0]
    assert [t.date for t in stmt.transactions] == ["2026-01-05", "2026-01-06"]


def test_f1_negative_an_uncalendarable_row_date_is_dropped_not_guessed():
    md = business(credits="10.00", credits_n=1, ending="1,010.00", body="""
Deposits and other credits Date Description Amount
26/13/24 Incoming transfer 10.00
Total deposits and other credits $10.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is None or all("Incoming transfer" not in t.description for t in stmt.transactions)


# ---------------------------------------------------------------------------
# F2 — the Amount column wraps onto its own line
# ---------------------------------------------------------------------------

def test_f2_a_bare_amount_line_completes_the_row_above_it():
    md = business(debits="500.00", debits_n=1, ending="500.00", body="""
Withdrawals and other debits Date Description Amount
01/09/26 A DESCRIPTION LONG ENOUGH THAT THE AMOUNT COLUMN WRAPPED
-500.00
Total withdrawals and other debits -$500.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-500.0]


def test_f2_a_bare_amount_cell_outranks_a_money_token_ending_the_description():
    """The description prints its own figures (`… MI TAX: 6.66`) and the real
    Amount cell wraps below. Taking the line-terminal token reads the tax."""
    md = business(fees="117.68", ending="882.32", body="""
Service fees
Date Transaction description Amount
01/09/26 ACCT ORDER00413 DES:FEE PMT INFO: PRODUCT(S): 101.40 S&H: 9.62 MI TAX: 6.66
-117.68
Total service fees -$117.68
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-117.68]
    assert "MI TAX: 6.66" in stmt.transactions[0].description


def test_f2_negative_a_completed_row_is_not_extended_by_the_next_line():
    md = business(debits="60.00", debits_n=2, ending="940.00", body="""
Withdrawals and other debits Date Description Amount
01/09/26 A completed row -50.00
Card account # XXXX XXXX XXXX 1234
01/10/26 PURCHASE 0110 A CARD ROW -10.00
Subtotal for card account # XXXX XXXX XXXX 1234 -$10.00 Total withdrawals and other debits -$60.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-50.0, -10.0]
    assert stmt.transactions[0].description == "A completed row"


# ---------------------------------------------------------------------------
# F3 — the printed section total / card subtotal glued onto a row's line
# ---------------------------------------------------------------------------

def test_f3_a_section_total_printed_after_the_last_row_is_not_that_row_amount():
    md = business(debits="263.62", debits_n=1, ending="736.38", body="""
Withdrawals and other debits - continued Date Description Amount 01/30/26 A CARD ROW -263.62 Subtotal for card account # XXXX XXXX XXXX 4300 -$263.62 Total withdrawals and other debits -$263.62
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-263.62]


def test_f3_a_card_subtotal_is_never_a_row():
    md = business(debits="30.00", debits_n=2, ending="970.00", body="""
Withdrawals and other debits Date Description Amount
Card account # XXXX XXXX XXXX 4300
01/10/26 PURCHASE 0110 ONE -10.00
01/11/26 PURCHASE 0111 TWO -20.00
Subtotal for card account # XXXX XXXX XXXX 4300 -$30.00
Total withdrawals and other debits -$30.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-10.0, -20.0]


# ---------------------------------------------------------------------------
# F4 — a description that begins with the word the total line begins with
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("description", [
    "Total Quality Lo DES:PAYMENTS ID:7858 CTX ADDITIONAL INFORMATION IS AVAILABLE",
    "TOTALWINE 1147 01/28 #000000000 PURCHASE TOTALWINE 1147 A CITY CA",
])
def test_f4_a_counterparty_named_total_is_still_a_row(description):
    md = business(debits="24.33", debits_n=1, ending="975.67", body=f"""
Withdrawals and other debits Date Description Amount
01/12/26 {description} -24.33
Total withdrawals and other debits -$24.33
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-24.33]
    assert stmt.transactions[0].description == description


def test_f4_negative_the_printed_section_total_is_never_a_row():
    md = business(credits="10.00", credits_n=1, ending="1,010.00", body="""
Deposits and other credits Date Description Amount
01/05/26 Deposit one 10.00
Total deposits and other credits $10.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [10.0]


# ---------------------------------------------------------------------------
# F5 — the Checks table
# ---------------------------------------------------------------------------

def test_f5_a_single_column_checks_table_is_read():
    """Most BofA statements print two `Date Check # Amount` column groups; a
    statement with one cheque prints one, and the doubled header was required."""
    md = business(checks="750.00", ending="250.00", body="""
Checks
Date Check # Amount
01/09/26 1021 -750.00
Total checks -$750.00 Total # of checks 1
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-750.0]
    assert stmt.transactions[0].description == "Check 1021"


def test_f5_a_check_the_bank_printed_no_number_for_is_still_a_row():
    md = business(checks="500.00", ending="500.00", body="""
Checks
Date Check # Amount Date Check # Amount
01/11/26 -300.00 01/15/26 1595 -200.00
Total checks -$500.00 Total # of checks 2
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-300.0, -200.0]
    assert [t.description for t in stmt.transactions] == ["Check", "Check 1595"]


def test_f5_a_gap_marked_check_number_keeps_its_marker():
    md = business(checks="68.79", ending="931.21", body="""
Checks
Date Check # Amount Date Check # Amount
01/07/26 1575* -68.79
Total checks -$68.79 Total # of checks 1
*   There is a gap in sequential check numbers
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-68.79]
    assert stmt.transactions[0].description == "Check 1575*"


def test_f5_negative_the_account_summary_checks_line_never_opens_the_section():
    """`Checks -7,500.00` in the summary is a stated total, not a heading."""
    md = business(credits="10.00", checks="750.00", credits_n=1, ending="260.00", body="""
Deposits and other credits Date Description Amount
01/05/26 Deposit one 10.00
Total deposits and other credits $10.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [10.0]


# ---------------------------------------------------------------------------
# F6 — the consumer section vocabulary
# ---------------------------------------------------------------------------

def test_f6_the_consumer_layout_is_read_on_both_sides():
    md = CONSUMER_SUMMARY.format(credits="500.00", atm="30.00", other="70.00", ending="1,400.00") + """
Deposits and other additions Date Description Amount
01/03/26 Transfer from a counterparty 500.00
Total deposits and other additions $500.00
Withdrawals and other subtractions
ATM and debit card subtractions
Date Description Amount
01/04/26 PURCHASE 0104 A STORE -30.00
Total ATM and debit card subtractions -$30.00
Other subtractions
Date Description Amount
01/05/26 Zelle payment to a counterparty -70.00
Total other subtractions -$70.00
"""
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [500.0, -30.0, -70.0]
    assert stmt.stated_total_credits == 500.0
    assert stmt.stated_total_debits == 100.0
    assert reconcile(repair_bofa_summary(md, stmt)).ok


def test_f6_the_consumer_summary_sums_both_printed_outflow_lines():
    md = CONSUMER_SUMMARY.format(credits="500.00", atm="30.00", other="70.00", ending="1,400.00")
    stmt = repair_bofa_summary(md, __import__("analysis.schema", fromlist=["Statement"]).Statement(
        bank="Bank of America"))

    assert stmt.stated_total_credits == 500.0
    assert stmt.stated_total_debits == 100.0
    assert stmt.beginning_balance == 1000.0
    assert stmt.ending_balance == 1400.0


# ---------------------------------------------------------------------------
# F7 — an OCR-degraded column header
# ---------------------------------------------------------------------------

def test_f7_a_scanned_column_header_does_not_hide_the_section():
    """Local OCR renders `Date Description Amount` as `Date __Description 2.0.2.2
    AMO`. The rows below it are still the rows the bank printed."""
    md = business(debits="55.40", debits_n=1, ending="944.60", body="""
Withdrawals and other debits
Date __Description 2.0.2.2 AMO
Card account # XXXX XXXX XXXX 4906
01/06/26 PURCHASE 0106 A STORE -55.40
Subtotal for card account # XXXX XXXX XXXX 4906 -$55.40
Total withdrawals and other debits -55.40
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-55.4]


# ---------------------------------------------------------------------------
# F8 — page furniture
# ---------------------------------------------------------------------------

def test_f8_a_section_continues_across_a_page_break():
    md = business(credits="30.00", credits_n=2, ending="1,030.00", body="""
Deposits and other credits Date Description Amount
01/05/26 Deposit one 10.00
continued on the next page
Page 3 of 4

--- Page 4 ---

A COMPANY LLC   !   Account # 1111 2222 3333   !   January 1, 2026 to January 31, 2026
Deposits and other credits - continued Date Description Amount 01/06/26 Deposit two 20.00
Total deposits and other credits $30.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [10.0, 20.0]


def test_f8_negative_the_daily_ledger_series_is_never_activity():
    md = business(credits="10.00", credits_n=1, ending="1,010.00", body="""
Deposits and other credits Date Description Amount
01/05/26 Deposit one 10.00
Total deposits and other credits $10.00
Daily ledger balances Date Balance ($) Date Balance($) Date Balance ($)
01/01 1,000.00 01/05 1,010.00 01/31 1,010.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [10.0]


def test_f8_negative_the_page_header_line_never_joins_a_description():
    md = business(debits="500.00", debits_n=1, ending="500.00", body="""
Withdrawals and other debits Date Description Amount
01/09/26 A ROW WHOSE AMOUNT WRAPPED
-500.00
continued on the next page
Page 3 of 4

--- Page 4 ---

A COMPANY LLC   !   Account # 1111 2222 3333   !   January 1, 2026 to January 31, 2026
Total withdrawals and other debits -$500.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert amounts(stmt) == [-500.0]
    assert stmt.transactions[0].description == "A ROW WHOSE AMOUNT WRAPPED"


# ---------------------------------------------------------------------------
# Direction is the printed section, not the sign of a zero
# ---------------------------------------------------------------------------

def test_a_waived_fee_of_zero_is_still_an_outflow_row():
    md = business(fees="0.00", body="""
Service fees
Date Transaction description Amount
01/09/26 Prfd Rwds for Bus-Wire Fee Waiver of $30 -0.00
Total service fees -$0.00
""")
    stmt = parse_bofa_statement(md)

    assert stmt is not None
    assert [t.direction for t in stmt.transactions] == ["debit"]


# ---------------------------------------------------------------------------
# End to end: the document's own arithmetic closes
# ---------------------------------------------------------------------------

def test_every_section_together_reconciles_against_the_printed_summary():
    md = business(
        credits="1,000.00", debits="600.00", checks="300.00", fees="25.00",
        credits_n=2, debits_n=3, ending="1,075.00", body="""
Deposits and other credits Date Description Amount
01/03/26 WIRE TYPE:WIRE IN DATE: 260103 PMT DET:BOH OF 26/01/03 /CATPURP/CTRC
900.00
01/04/26 Total Quality Lo DES:PAYMENTS ID:7858 100.00
Total deposits and other credits $1,000.00
Withdrawals and other debits Date Description Amount
Card account # XXXX XXXX XXXX 4300
01/05/26 PURCHASE 0105 ONE -200.00
01/06/26 PURCHASE 0106 TWO -300.00
01/07/26 Temporary Credit Reversal on 01/06/26 -100.00
Subtotal for card account # XXXX XXXX XXXX 4300 -$600.00 Total withdrawals and other debits -$600.00
Checks
Date Check # Amount
01/08/26 -300.00
Total checks -$300.00 Total # of checks 1
Service fees
Date Transaction description Amount
01/09/26 Wire Transfer Fee -25.00
Total service fees -$25.00
""")
    stmt = repair_bofa_summary(md, parse_bofa_statement(md))

    assert amounts(stmt) == [900.0, 100.0, -200.0, -300.0, -100.0, -300.0, -25.0]
    assert stmt.stated_total_credits == 1000.0
    assert stmt.stated_total_debits == 925.0
    assert reconcile(stmt).ok
