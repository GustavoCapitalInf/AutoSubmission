"""Burke & Herbert Bank, the mainframe `ACTIVITY IN DATE ORDER` layout
(W3 §HUNT-CELL).

The whole activity region arrives as ONE physical line, so the fixtures here
are one-line activity blocks. What is being pinned in almost every case is the
row-by-row balance chain: it is the only oracle that can see a row split in the
wrong place, and it is what makes this layout readable at all.
"""
from __future__ import annotations

from analysis.burke_herbert import detect, parse_burke_herbert_statement

HEADER = (
    "Page 1 of 2 Date  4/30/26 PO Box 179, Moorefield, WV 26836\n"
    "ACCOUNT NUMBER         XXXXXX6768\n"
    "ACME CONTRACTING WV LLC 1 MAIN RD HUNTINGTON WV  25701\n"
    "C H E C K I N G  A C C O U N T\n"
)
SUMMARY = (
    "Business Advantage Checking                NUMBER OF ENCLOSURES         4 "
    "ACCOUNT NUMBER                XXXXXX6768   Statement Dates   4/01/26 thru  "
    "4/30/26 PREVIOUS BALANCE                  100.00- "
    "DAYS THIS STATEMENT PERIOD           30 "
    "2 DEPOSITS/CREDITS          1,500.00   AVERAGE LEDGER BALANCE           500.00 "
    "4 CHECKS/DEBITS               400.00   AVERAGE COLLECTED BAL            500.00 "
    "SERVICE CHARGE                       .00 INTEREST                             .00 "
    "ENDING BALANCE                   1,000.00\n"
)
ACTIVITY = (
    "============================== ACTIVITY IN DATE ORDER ============================= "
    "DATE DESCRIPTION         CHECK#                       AMOUNT             BALANCE "
    "4/02 RETURNED ITEM FEE                                 50.00- 150.00- "
    "4/05 DEPOSIT                                        1,000.00              850.00 "
    "4/10 ATM W/D 1339 04/09/26 00000264                  300.00- 550.00 "
    "PAI ATM 4231 HUGHES BRANCH RD, HUNTINGTON   WV C# 0517 "
    "4/20 DEPOSIT                                          500.00            1,050.00 "
    "4/25 INQ SVC 1452 04/24/26 00047885                     .50- 1,049.50 "
    "4/28 WITHDRAWAL                                        49.50- 1,000.00\n"
)
FOOTER = (
    "PO Box 179, Moorefield, WV 26836  *  Telephone Banking 1-877-440-0800 "
    "Client Care Center:  1-855-571-5824 *  Online at burkeandherbertbank.com\n"
)


def document(**parts: str) -> str:
    blocks = dict(header=HEADER, summary=SUMMARY, activity=ACTIVITY, footer=FOOTER)
    blocks.update(parts)
    return "".join(blocks[name] for name in ("header", "summary", "activity", "footer"))


# ---------------------------------------------------------------- the happy read

def test_the_statement_is_published_whole():
    stmt = parse_burke_herbert_statement(document())
    assert stmt is not None
    assert stmt.bank == "Burke & Herbert Bank"
    assert stmt.account_name == "Business Advantage Checking"
    assert stmt.account_number == "XXXXXX6768"
    assert stmt.period_start == "2026-04-01"
    assert stmt.period_end == "2026-04-30"
    assert stmt.days_in_period == 30
    assert stmt.beginning_balance == -100.00
    assert stmt.ending_balance == 1000.00


def test_every_row_of_the_flattened_activity_line_is_read():
    stmt = parse_burke_herbert_statement(document())
    assert [(t.date, t.amount, t.running_balance) for t in stmt.transactions] == [
        ("2026-04-02", -50.00, -150.00),
        ("2026-04-05", 1000.00, 850.00),
        ("2026-04-10", -300.00, 550.00),
        ("2026-04-20", 500.00, 1050.00),
        ("2026-04-25", -0.50, 1049.50),
        ("2026-04-28", -49.50, 1000.00),
    ]


def test_the_printed_counts_are_carried_as_the_banks_own_oracle():
    """This layout prints the COUNT beside each direction's total, which most
    do not. Carrying them makes the platform's stated-count check live here."""
    stmt = parse_burke_herbert_statement(document())
    assert stmt.stated_credit_count == 2
    assert stmt.stated_debit_count == 4
    assert stmt.stated_total_credits == 1500.00
    assert stmt.stated_total_debits == 400.00


def test_an_overdrawn_opening_balance_is_negative():
    """`100.00-` is the mainframe trailing minus, and it is the only negative
    marker this print has — on the summary and on every row alike."""
    stmt = parse_burke_herbert_statement(document())
    assert stmt.beginning_balance == -100.00
    assert stmt.transactions[0].running_balance == -150.00


def test_a_sub_dollar_amount_printed_without_its_leading_zero_is_read():
    stmt = parse_burke_herbert_statement(document())
    assert stmt.transactions[4].amount == -0.50


def test_a_full_date_inside_a_description_does_not_open_a_row():
    """Card rows print the transaction's own `04/09/26` in the description.
    Six rows are printed; a date token that opened a row there would make
    seven, and the chain would break at that point."""
    stmt = parse_burke_herbert_statement(document())
    assert len(stmt.transactions) == 6
    assert "04/09/26" in stmt.transactions[2].description


def test_a_rows_continuation_text_belongs_to_the_row_it_follows():
    stmt = parse_burke_herbert_statement(document())
    assert "PAI ATM" in stmt.transactions[2].description


def test_the_ledger_closes_on_the_printed_ending_balance():
    stmt = parse_burke_herbert_statement(document())
    total = round(sum(t.amount for t in stmt.transactions), 2)
    assert round(stmt.beginning_balance + total, 2) == stmt.ending_balance


# ------------------------------------------------------------------ refusals

def test_a_broken_balance_chain_is_refused():
    """One printed balance moved. Both direction totals still match, both
    counts still match, and the statement still closes on its ending balance —
    only the row-by-row chain sees it."""
    assert parse_burke_herbert_statement(document(
        activity=ACTIVITY.replace("300.00- 550.00", "300.00- 555.00")
    )) is None


def test_a_direction_total_that_does_not_match_the_rows_is_refused():
    assert parse_burke_herbert_statement(document(
        summary=SUMMARY.replace("2 DEPOSITS/CREDITS          1,500.00",
                                "2 DEPOSITS/CREDITS          1,400.00")
    )) is None


def test_a_printed_credit_count_that_does_not_match_the_rows_is_refused():
    assert parse_burke_herbert_statement(document(
        summary=SUMMARY.replace("2 DEPOSITS/CREDITS", "3 DEPOSITS/CREDITS")
    )) is None


def test_a_printed_count_that_does_not_match_the_rows_is_refused():
    """The money is untouched: only the bank's own row count moves. A ledger
    that splits or merges rows keeps both totals right and gets this wrong."""
    assert parse_burke_herbert_statement(document(
        summary=SUMMARY.replace("4 CHECKS/DEBITS", "5 CHECKS/DEBITS")
    )) is None


def test_a_ledger_that_does_not_close_on_the_printed_ending_balance_is_refused():
    assert parse_burke_herbert_statement(document(
        summary=SUMMARY.replace("ENDING BALANCE                   1,000.00",
                                "ENDING BALANCE                   1,001.00")
    )) is None


def test_a_row_dated_outside_the_printed_period_is_refused():
    assert parse_burke_herbert_statement(document(
        activity=ACTIVITY.replace("4/20 DEPOSIT", "6/20 DEPOSIT")
    )) is None


def test_a_statement_with_no_activity_region_is_refused():
    assert parse_burke_herbert_statement(document(activity="")) is None


def test_a_statement_with_no_printed_period_is_refused():
    assert parse_burke_herbert_statement(document(
        summary=SUMMARY.replace("Statement Dates   4/01/26 thru  4/30/26", "")
    )) is None


# ------------------------------------------------------------------- detection

def test_the_issuer_name_in_its_own_ledger_is_not_what_claims():
    """These statements name Burke & Herbert inside their OWN transaction
    descriptions, as the location of an ATM. The name is not a marker."""
    assert not detect(
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 ATM W/D Burke & Herbert Bank 6399 Route 60 250.00\n"
    ).claims


def test_the_activity_banner_alone_does_not_claim():
    """`ACTIVITY IN DATE ORDER` is the mainframe platform's banner, and
    LINKBANK prints it over a different issuer's statement."""
    assert not detect(
        "LINKBANK.COM\nActivity in Date Order\n"
        "PREVIOUS BALANCE 100.00 DAYS THIS STATEMENT PERIOD 30\n"
    ).claims


def test_this_issuers_insufficient_funds_notice_is_not_a_statement():
    """It carries the issuer's domain and no ledger at all. One such document
    is in the surveyed archive."""
    assert not detect(
        "PO Box 268, Alexandria, VA 22313\n"
        "NOTICE OF ITEMS WITH INSUFFICIENT FUNDS\n"
        "PLEASE DEDUCT A HANDLING CHARGE OF: 0.00 BALANCE: 927.81-\n"
        "Online at burkeandherbertbank.com EP6281P\n"
    ).claims


def test_the_header_without_a_ledger_is_not_parsed():
    assert parse_burke_herbert_statement(HEADER + SUMMARY + FOOTER) is None
