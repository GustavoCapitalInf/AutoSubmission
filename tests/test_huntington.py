"""The Huntington sectioned business deposit statement (W3 §HUNT-CELL).

Every fixture here is built from `document()`, which assembles a statement that
balances, and each test changes exactly one printed thing. That is deliberate:
the parser's whole safety argument is that four printed oracles agree, so the
tests that matter are the ones that break one oracle and assert the parser
publishes nothing rather than publishing the other three.
"""
from __future__ import annotations

import pytest

from analysis.huntington import detect, parse_huntington_statement

HEADER = (
    "THE HUNTINGTON NATIONAL BANK PO BOX 1558 EA1W37 COLUMBUS OH 43216-1558\n"
    "ACME WIDGETS LLC 1 MAIN ST COLUMBUS OH 43219-6229\n"
    "Have a Question or Concern?\n"
    "Stop by your nearest Huntington office or contact us at:\n"
    "Huntington Business Checking 100 Account: -------5638\n"
)
FOOTER = (
    "Investments are offered through the Huntington Investment Company, "
    "Registered Investment Advisor, member FINRA/SIPC.\n"
    "The Huntington National Bank is Member FDIC. , Huntington and 24-Hour Grace "
    "are federally registered service marks of Huntington Bancshares Incorporated.\n"
    "Statement Period from 01/01/26 to 01/31/26 Page 1 of 2\n"
)

SUMMARY = (
    "Beginning Balance $1,000.00 Credits (+) 1,050.00 Regular Deposits 750.00 "
    "Electronic Deposits 300.00 Debits (-) 300.00 Regular Checks Paid 100.00 "
    "Electronic Withdrawals 200.00 Total Service Charges (-) 20.00 "
    "Ending Balance $1,730.00\n"
)
PERIOD = (
    "Statement Activity From: 01/01/26 to 01/31/26\n"
    "Days in Statement Period 31\n"
    "Average Ledger Balance* 1,500.00 Average Collected Balance* 1,500.00\n"
    "* The above balances correspond to the service charge cycle for this account.\n"
)
DEPOSITS = (
    "Deposits (+) Account:-------5638\n"
    "Date Amount Serial # Type Date Amount Serial # Type\n"
    "01/05 500.00 387142655 Remote 01/12 250.00 Brch/ATM\n"
)
CREDITS = (
    "Other Credits (+) Account:-------5638\n"
    "Date Amount Description\n"
    "01/08 300.00 ACME PAYMENTS DEPOSIT 260108 653201322886\n"
)
CHECKS = (
    "Checks (-) Account:-------5638\n"
    "Date Amount Check # Date Amount Check #\n"
    "01/09 100.00 1001\n"
)
DEBITS = (
    "Other Debits (-) Account:-------5638\n"
    "Date Amount Description\n"
    "01/15 200.00 PURCHASE SUPPLY CO COLUMBUS OH XXXXXXXXXXXX2836\n"
)
FEE_DETAIL = (
    "Service Charge Detail Account:-------5638\n"
    "Date Service Charge (-) Waives and Discounts (+) Description\n"
    "01/20 25.00 MONTHLY SERVICE FEE\n"
    "01/20 5.00 24-HOUR GRACE OVERDRAFT FEE WAIVER\n"
)
FEE_SUMMARY = (
    "Service Charge Summary Account:-------5638\n"
    "Previous Month Service Charges (-) $25.00 Other Credits (+) 5.00 "
    "Total Service Charges (-) $20.00\n"
)
BALANCES = (
    "Balance Activity Account:-------5638\n"
    "Date Balance Date Balance Date Balance\n"
    "12/31 1,000.00 01/05 1,500.00 01/08 1,800.00 01/09 1,700.00\n"
    "01/12 1,950.00 01/15 1,750.00 01/20 1,730.00\n"
)


def document(**parts: str) -> str:
    """The balanced statement, with any named part replaced."""
    blocks = dict(
        header=HEADER, summary=SUMMARY, period=PERIOD, deposits=DEPOSITS,
        credits=CREDITS, checks=CHECKS, debits=DEBITS, fee_detail=FEE_DETAIL,
        fee_summary=FEE_SUMMARY, balances=BALANCES, footer=FOOTER,
    )
    blocks.update(parts)
    return "".join(blocks[name] for name in (
        "header", "summary", "period", "deposits", "credits", "checks",
        "debits", "fee_detail", "fee_summary", "balances", "footer",
    ))


# ---------------------------------------------------------------- the happy read

def test_the_balanced_statement_is_published_whole():
    stmt = parse_huntington_statement(document())
    assert stmt is not None
    assert stmt.bank == "Huntington National Bank"
    assert stmt.account_name == "Huntington Business Checking 100"
    assert stmt.account_number == "5638"
    assert stmt.period_start == "2026-01-01"
    assert stmt.period_end == "2026-01-31"
    assert stmt.days_in_period == 31
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1730.00
    assert stmt.stated_total_credits == 1050.00
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_service_charge == 20.00


def test_the_published_ledger_is_every_printed_row_and_nothing_else():
    stmt = parse_huntington_statement(document())
    assert [(t.date, t.amount) for t in stmt.transactions] == [
        ("2026-01-05", 500.00),
        ("2026-01-08", 300.00),
        ("2026-01-09", -100.00),
        ("2026-01-12", 250.00),
        ("2026-01-15", -200.00),
        ("2026-01-20", -25.00),
        ("2026-01-20", 5.00),
    ]


def test_the_ledger_closes_on_the_printed_ending_balance():
    stmt = parse_huntington_statement(document())
    total = round(sum(t.amount for t in stmt.transactions), 2)
    assert round(stmt.beginning_balance + total, 2) == stmt.ending_balance


def test_the_banks_own_end_of_day_balances_are_carried_as_evidence():
    stmt = parse_huntington_statement(document())
    # The row dated before the period opens is the previous period's closing
    # balance, not one of this period's daily balances.
    assert [(d.date, d.balance) for d in stmt.stated_daily_balances] == [
        ("2026-01-05", 1500.00),
        ("2026-01-08", 1800.00),
        ("2026-01-09", 1700.00),
        ("2026-01-12", 1950.00),
        ("2026-01-15", 1750.00),
        ("2026-01-20", 1730.00),
    ]


def test_the_issuer_prints_no_instance_counts_so_none_are_claimed():
    """Deriving them from the ledger would manufacture the oracle the platform
    checks the ledger against."""
    stmt = parse_huntington_statement(document())
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_the_service_charge_cycle_average_is_not_published_as_the_period_average():
    """The statement prints `Average Ledger Balance` under its own footnote
    saying the figure belongs to the service charge cycle, which is not the
    statement period."""
    stmt = parse_huntington_statement(document())
    assert stmt.stated_average_balance is None


def test_two_rows_printed_on_one_line_are_two_rows():
    """The deposit and cheque columns are printed two-up."""
    stmt = parse_huntington_statement(document())
    deposits = [t for t in stmt.transactions if t.date in ("2026-01-05", "2026-01-12")]
    assert [t.amount for t in deposits] == [500.00, 250.00]


def test_legal_furniture_after_a_section_is_not_a_transaction():
    stmt = parse_huntington_statement(document())
    assert not any("FINRA" in t.description for t in stmt.transactions)
    assert not any("Member FDIC" in t.description for t in stmt.transactions)


def test_a_section_reprinted_after_a_page_break_continues_the_same_section():
    split = (
        "Other Debits (-) Account:-------5638\n"
        "Date Amount Description\n"
        "01/15 150.00 PURCHASE SUPPLY CO COLUMBUS OH XXXXXXXXXXXX2836\n"
        "Statement Period from 01/01/26 to 01/31/26 Page 1 of 2\n"
        "Other Debits (-) Account:-------5638\n"
        "Date Amount Description\n"
        "01/15 50.00 PURCHASE SUPPLY CO COLUMBUS OH XXXXXXXXXXXX2836\n"
    )
    stmt = parse_huntington_statement(document(debits=split))
    assert stmt is not None
    assert round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2) == 325.00


# ---------------------------------------------------- the trailing minus, both ends

OVERDRAWN_SUMMARY = (
    "Beginning Balance $1,000.00- Credits (+) 1,050.00 Regular Deposits 750.00 "
    "Electronic Deposits 300.00 Debits (-) 300.00 Regular Checks Paid 100.00 "
    "Electronic Withdrawals 200.00 Total Service Charges (-) 20.00 "
    "Ending Balance $270.00-\n"
)
OVERDRAWN_BALANCES = (
    "Balance Activity Account:-------5638\n"
    "Date Balance Date Balance Date Balance\n"
    "12/31 1,000.00- 01/05 500.00- 01/08 200.00- 01/09 300.00-\n"
    "01/12 50.00- 01/15 250.00- 01/20 270.00-\n"
)


def test_an_overdrawn_balance_is_negative_at_both_ends_of_the_period():
    """`$1,000.00-` is this issuer's only negative marker. Read as a magnitude
    the statement still sums — against a sign-flipped closing balance."""
    stmt = parse_huntington_statement(
        document(summary=OVERDRAWN_SUMMARY, balances=OVERDRAWN_BALANCES)
    )
    assert stmt is not None
    assert stmt.beginning_balance == -1000.00
    assert stmt.ending_balance == -270.00
    assert stmt.stated_daily_balances[0].balance == -500.00


def test_a_trailing_minus_on_a_transaction_row_is_refused():
    """The section carries the direction; a signed figure inside it means the
    column and the figure disagree, and this layout never prints one."""
    assert parse_huntington_statement(
        document(debits=DEBITS.replace("200.00 PURCHASE", "200.00- PURCHASE"))
    ) is None


def test_a_sub_dollar_fee_printed_without_its_leading_zero_is_read():
    fee_detail = (
        "Service Charge Detail Account:-------5638\n"
        "Date Service Charge (-) Waives and Discounts (+) Description\n"
        "01/20 .60 BRANCH CASH DEPOSIT PROCESSING FEE\n"
    )
    fee_summary = (
        "Service Charge Summary Account:-------5638\n"
        "Previous Month Service Charges (-) $.60 Total Service Charges (-) $.60\n"
    )
    summary = SUMMARY.replace(
        "Total Service Charges (-) 20.00", "Total Service Charges (-) .60"
    ).replace("Ending Balance $1,730.00", "Ending Balance $1,749.40")
    balances = BALANCES.replace("01/20 1,730.00", "01/20 1,749.40")
    stmt = parse_huntington_statement(
        document(summary=summary, fee_detail=fee_detail,
                 fee_summary=fee_summary, balances=balances)
    )
    assert stmt is not None
    assert [t.amount for t in stmt.transactions if t.date == "2026-01-20"] == [-0.60]


# ------------------------------------------------- the fee columns, and their proof

def test_a_waiver_is_a_credit_and_a_charge_is_a_debit():
    stmt = parse_huntington_statement(document())
    fees = [t for t in stmt.transactions if t.date == "2026-01-20"]
    assert [(t.amount, t.direction) for t in fees] == [(-25.00, "debit"), (5.00, "credit")]


def test_the_waiver_column_is_found_where_the_printed_totals_say_it_starts():
    """Three charges then two waivers, with no date regression to mark the
    hand-off: the boundary is the one the Service Charge Summary states."""
    fee_detail = (
        "Service Charge Detail Account:-------5638\n"
        "Date Service Charge (-) Waives and Discounts (+) Description\n"
        "01/18 10.00 MONTHLY SERVICE FEE\n"
        "01/19 15.00 ONLINE PAYMENT CENTER FEES\n"
        "01/20 20.00 WIRE TRANSFER FEES\n"
        "01/20 15.00 TOTAL RELATIONSHIP SERVICE FEE WAIVE\n"
        "01/20 10.00 24-HOUR GRACE OVERDRAFT FEE WAIVER\n"
    )
    fee_summary = (
        "Service Charge Summary Account:-------5638\n"
        "Previous Month Service Charges (-) $45.00 Other Credits (+) 25.00 "
        "Total Service Charges (-) $20.00\n"
    )
    balances = BALANCES.replace(
        "01/12 1,950.00 01/15 1,750.00 01/20 1,730.00",
        "01/12 1,950.00 01/15 1,750.00 01/18 1,740.00 01/19 1,725.00 01/20 1,730.00",
    )
    stmt = parse_huntington_statement(
        document(fee_detail=fee_detail, fee_summary=fee_summary, balances=balances)
    )
    assert stmt is not None
    assert [t.amount for t in stmt.transactions if t.amount in
            (-10.0, -15.0, -20.0, 15.0, 10.0)] == [-10.00, -15.00, -20.00, 15.00, 10.00]


def test_a_fee_split_the_printed_totals_do_not_support_is_refused():
    """The rows are unchanged; only the stated split moves. No position
    satisfies both sides, so nothing is published."""
    assert parse_huntington_statement(document(fee_summary=(
        "Service Charge Summary Account:-------5638\n"
        "Previous Month Service Charges (-) $23.00 Other Credits (+) 3.00 "
        "Total Service Charges (-) $20.00\n"
    ))) is None


def test_a_fee_split_the_printed_totals_do_not_pin_uniquely_is_refused():
    """A zero-amount fee row sits on the boundary: the totals are satisfied
    whether it is the last charge or the first waiver. The money is identical
    either way, so no arithmetic check can ever see the difference — but the
    row's printed COLUMN is its direction, and the document does not say which
    column it stood in."""
    fee_detail = (
        "Service Charge Detail Account:-------5638\n"
        "Date Service Charge (-) Waives and Discounts (+) Description\n"
        "01/20 25.00 MONTHLY SERVICE FEE\n"
        "01/20 .00 FRAUD PROTECTION SERVICE FEES\n"
        "01/20 5.00 24-HOUR GRACE OVERDRAFT FEE WAIVER\n"
    )
    assert parse_huntington_statement(document(fee_detail=fee_detail)) is None


def test_a_service_charge_summary_that_does_not_add_up_is_refused():
    """Its own identity is checked first, so a mis-read of the block cannot
    license a mis-split."""
    assert parse_huntington_statement(document(fee_summary=(
        "Service Charge Summary Account:-------5638\n"
        "Previous Month Service Charges (-) $25.00 Other Credits (+) 5.00 "
        "Total Service Charges (-) $99.00\n"
    ))) is None


def test_itemised_fees_with_no_summary_to_split_them_are_refused():
    assert parse_huntington_statement(document(fee_summary="")) is None


def test_a_service_charge_the_document_never_itemises_is_refused():
    """The shape eight documents in the surveyed folder are printed in: the
    summary accounts for fees that no block itemises, so that money has no
    date and no row. Publishing the rest would publish a ledger the statement
    itself says is short."""
    assert parse_huntington_statement(
        document(fee_detail="", fee_summary="")
    ) is None


def test_the_intermediate_net_line_is_not_counted_as_a_charge():
    """`Net Service Charges` is printed between the two columns' totals.
    Adding it would count the previous month's charges twice."""
    fee_summary = (
        "Service Charge Summary Account:-------5638\n"
        "Previous Month Service Charges (-) $25.00 "
        "Credits - Previous Month Charges (+) 5.00 Net Service Charges $20.00 "
        "Total Service Charges (-) $20.00\n"
    )
    stmt = parse_huntington_statement(document(fee_summary=fee_summary))
    assert stmt is not None
    assert stmt.stated_service_charge == 20.00


# ------------------------------------------------------------- the four refusals

def test_a_summary_that_does_not_balance_is_refused():
    assert parse_huntington_statement(document(
        summary=SUMMARY.replace("Ending Balance $1,730.00", "Ending Balance $1,731.00")
    )) is None


def test_subtotals_that_do_not_add_up_to_their_printed_total_are_refused():
    assert parse_huntington_statement(document(
        summary=SUMMARY.replace("Regular Deposits 750.00", "Regular Deposits 749.00")
    )) is None


def test_a_section_that_does_not_add_up_to_its_printed_subtotal_is_refused():
    assert parse_huntington_statement(document(
        credits=CREDITS.replace("300.00 ACME", "299.00 ACME")
    )) is None


def test_per_direction_sums_are_checked_even_when_the_net_is_right():
    """Both printed totals understate by the same amount, so the summary still
    balances, its own components still add up, and the ledger still closes on
    the printed ending balance. Only the per-direction comparison sees it —
    which is the comparison that catches a row read into the wrong column."""
    summary = (
        "Beginning Balance $1,000.00 Credits (+) 1,000.00 Regular Deposits 700.00 "
        "Electronic Deposits 300.00 Debits (-) 250.00 Regular Checks Paid 50.00 "
        "Electronic Withdrawals 200.00 Total Service Charges (-) 20.00 "
        "Ending Balance $1,730.00\n"
    )
    assert parse_huntington_statement(document(summary=summary)) is None


def test_a_signed_figure_inside_a_direction_column_is_refused_on_its_own():
    """Everything else about this statement agrees: the summary balances, its
    components add up, both per-direction sums match and the day-by-day walk
    closes — all because the trailing minus has turned a printed DEBIT into a
    published credit. The only thing that says otherwise is that a
    direction-bearing column does not print a sign."""
    summary = (
        "Beginning Balance $1,000.00 Credits (+) 1,150.00 Regular Deposits 750.00 "
        "Electronic Deposits 300.00 Other Credits 100.00 Debits (-) 400.00 "
        "Regular Checks Paid 100.00 Electronic Withdrawals 300.00 "
        "Total Service Charges (-) 20.00 Ending Balance $1,730.00\n"
    )
    debits = (
        "Other Debits (-) Account:-------5638\n"
        "Date Amount Description\n"
        "01/15 300.00 PURCHASE SUPPLY CO COLUMBUS OH XXXXXXXXXXXX2836\n"
        "01/16 100.00- PURCHASE SUPPLY CO REFUND XXXXXXXXXXXX2836\n"
    )
    balances = (
        "Balance Activity Account:-------5638\n"
        "Date Balance Date Balance Date Balance\n"
        "12/31 1,000.00 01/05 1,500.00 01/08 1,800.00 01/09 1,700.00\n"
        "01/12 1,950.00 01/15 1,650.00 01/16 1,750.00 01/20 1,730.00\n"
    )
    assert parse_huntington_statement(
        document(summary=summary, debits=debits, balances=balances)
    ) is None


def test_a_ledger_that_misses_the_banks_own_end_of_day_balance_is_refused():
    """The sums still agree; only a DATE moves. This is the check that no
    arithmetic oracle can make, and the one the average daily balance rests
    on."""
    assert parse_huntington_statement(document(
        debits=DEBITS.replace("01/15 200.00", "01/16 200.00")
    )) is None


def test_a_statement_printing_no_end_of_day_balances_is_refused():
    """Without the table there is no evidence the dates are right, so the
    ledger is not published on the sums alone."""
    assert parse_huntington_statement(document(balances="")) is None


def test_a_statement_with_no_period_is_refused():
    assert parse_huntington_statement(document(period="")) is None


# ------------------------------------------------------------ the second account

LINE_OF_CREDIT = (
    "Business Overdraft Protection Account Account:-------5638\n"
    "Statement Activity From: 01/01/26 to 01/31/26\n"
    "Beginning Balance $0.00 Payments (-) 500.00 Advances (+) 499.00 "
    "Interest Expense (+) 1.00 Ending Balance $0.00\n"
)


def test_a_statement_carrying_a_second_account_is_declined_not_half_published():
    """A Business Overdraft Protection line of credit is a second account with
    its own balance chain. The schema carries one account per statement, so
    publishing this would mean dropping the other account silently."""
    assert parse_huntington_statement(document() + LINE_OF_CREDIT) is None


def test_the_second_account_is_still_recognised_as_this_issuers_layout():
    """It is declined at parse, not excluded at detection: the document IS a
    Huntington statement of this layout, and reporting it as a bank nobody has
    seen would put it in the wrong queue."""
    assert detect(document() + LINE_OF_CREDIT).claims


# ------------------------------------------------------------------- detection

def test_the_issuer_name_alone_does_not_claim():
    """Another bank's statement recording an ATM withdrawal at a Huntington
    branch prints the name; the archive contains exactly that."""
    other = (
        "BURKE & HERBERT BANK\nACTIVITY IN DATE ORDER\n"
        "2/23 ATM W/D 1954 02/20/26 00005039 89.00- 20,720.25\n"
        "HUNTINGTON BAN 5704 ROUTE 60 EAST HUNTINGTON WV C# 0517\n"
        "THE HUNTINGTON NATIONAL BANK\n"
    )
    assert not detect(other).claims


def test_the_summary_grid_alone_does_not_claim():
    assert not detect(SUMMARY + PERIOD + BALANCES).claims


def test_the_issuer_naming_itself_twice_without_its_grid_does_not_claim():
    """The return address and the service-mark footer are both furniture of
    this issuer, and both appear on documents that are not this layout — the
    insufficient-funds notice class among them. The grid is what claims."""
    notice = (
        "THE HUNTINGTON NATIONAL BANK PO BOX 1558 COLUMBUS OH 43216-1558\n"
        "ACME WIDGETS LLC 1 MAIN ST COLUMBUS OH 43219-6229\n"
        "NOTICE OF ITEMS WITH INSUFFICIENT FUNDS\n"
        "PLEASE DEDUCT A HANDLING CHARGE OF: 0.00 BALANCE: 927.81-\n"
        "Huntington Bancshares Incorporated\n"
    )
    assert not detect(notice).claims


def test_a_text_layer_with_no_readable_money_cannot_be_claimed():
    assert not detect(document().replace(".00", "-00").replace(".60", "-60")).claims


@pytest.mark.parametrize("part", ["deposits", "credits", "checks", "debits"])
def test_every_section_is_required_to_reconcile_not_merely_read(part):
    """Dropping any one section leaves the others readable and the summary
    intact, and the parser still publishes nothing."""
    assert parse_huntington_statement(document(**{part: ""})) is None
