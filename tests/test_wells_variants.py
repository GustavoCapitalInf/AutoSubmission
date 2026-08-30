"""Wells Fargo layout families — W3 Track A cell 5.

Every document below is synthetic: the amounts, dates, account numbers and
counterparties are invented, and each fixture exists to pin one *structural*
rule of the printed grid. See `docs/moneythumb-replacement/W3_TRACKA_LOG.md`
section WELLS for the family table these names come from.

Two kinds of fixture, and the difference matters:

* families W-F1..W-F6 demonstrate a defect — they fail against the pre-change
  parser and pass against this one;
* the `negative` fixtures constrain a new rule rather than demonstrating a
  defect. Several of them passed before as well; that is the point — the new
  reader had to be built so they still do.
"""
from __future__ import annotations

import pytest

from analysis.wells import parse_wells_statement


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------

#: The two markers the registry dispatches on, plus the year evidence R-1
#: requires. Printed exactly as the native rung emits a Wells page header.
_HEADER = "Wells Fargo Everyday Checking\nMarch 31, 2054         Page 1 of 4"


def _document(*blocks: str) -> str:
    return "\n".join([_HEADER, *blocks])


def _account(number: str = "1234567890", primary: bool = True) -> str:
    marker = "  (primary account)" if primary else ""
    return f"Account number:   {number}{marker}"


def _history(*rows: str) -> str:
    return "\n".join(["Transaction history", "WF_NATIVE_TRANSACTIONS", *rows,
                      "WF_NATIVE_TRANSACTIONS_END"])


def _amounts(stmt) -> list[float]:
    return [t.amount for t in stmt.transactions]


def _summary_of(stmt) -> tuple:
    return (stmt.period_start, stmt.period_end, stmt.beginning_balance,
            stmt.ending_balance, stmt.stated_total_credits, stmt.stated_total_debits)


#: One ordinary row, so a document that is only exercising its summary block
#: still has a ledger and is therefore parsed at all.
_ONE_ROW = _history("WF_TX|3/2|Deposit From A Customer|500.00||1,500.00")


# ---------------------------------------------------------------------------
# W-F1 — the consumer summary vocabulary
# ---------------------------------------------------------------------------

class TestF1ConsumerVocabulary:
    """A consumer statement labels its activity rows Additions/Subtractions.

    The direction is the label's FIRST word — the word that names the column —
    so the second word is data, not vocabulary to enumerate.
    """

    def test_f1_a_consumer_summary_is_read(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "A CUSTOMER NAME",
            "Beginning balance on 3/1 $1,000.00 Deposits/Additions 500.00 "
            "Withdrawals/Subtractions -  200.00",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 1000.0, 1300.0, 500.0, 200.0)

    def test_f1_the_business_vocabulary_is_unchanged(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 "
            "Withdrawals/Debits -  200.00",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 1000.0, 1300.0, 500.0, 200.0)


# ---------------------------------------------------------------------------
# W-F2 — the closed-account balance label
# ---------------------------------------------------------------------------

class TestF2ClosingBalanceLabel:
    def test_f2_a_closed_account_prints_closing_balance(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Final Statement for this closed account",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 "
            "Withdrawals/Debits -  1,500.00",
            "Closing balance on 3/31 $0.00",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert (stmt.period_end, stmt.ending_balance) == ("2054-03-31", 0.0)


# ---------------------------------------------------------------------------
# W-F3 — summary rows separated by page furniture
# ---------------------------------------------------------------------------

class TestF3FurnitureBetweenSummaryRows:
    """Each label owns its own printed row.

    The native rung emits one text block per line in (y, x) order, so the
    prose printed in the same band as the summary — the account-terms line,
    the routing numbers, the account holder — lands between the summary's own
    rows. Nothing may be assumed about what is adjacent to what.
    """

    def test_f3_a_summary_split_across_lines_by_furniture_is_read(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "A CUSTOMER NAME",
            "Beginning balance on 3/1 $1,000.00",
            "California account terms and conditions apply",
            "Deposits/Credits 500.00",
            "For Direct Deposit use Routing Number (RTN):  121042882",
            "Withdrawals/Debits -  200.00",
            "For Wire Transfers use Routing Number (RTN):  121000248",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 1000.0, 1300.0, 500.0, 200.0)

    def test_f3_negative_a_routing_number_is_not_an_amount_cell(self):
        """A digit run with no cents is not a printed money cell."""
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1",
            "For Direct Deposit use Routing Number (RTN):  121042882",
            "Deposits/Credits 500.00",
            "Withdrawals/Debits -  200.00",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert stmt.period_start == "2054-03-01"
        assert stmt.beginning_balance is None


# ---------------------------------------------------------------------------
# W-F4 — the unsigned withdrawal cell
# ---------------------------------------------------------------------------

class TestF4UnsignedWithdrawalCell:
    """The direction of an activity row is its label's, not its cell's sign.

    Wells prints a minus in front of the withdrawals figure, but the glyph is
    not always in the text layer. Requiring it lost the whole summary block.
    """

    @pytest.mark.parametrize("printed", ["-  200.00", "- 200.00", "200.00", "-200.00"])
    def test_f4_a_withdrawal_row_is_a_magnitude(self, printed):
        doc = _document(
            _account(),
            "Statement period activity summary",
            f"Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits {printed}",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert stmt.stated_total_debits == 200.0

    def test_f4_negative_a_printed_negative_balance_keeps_its_sign(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $47.37 Deposits/Credits 500.00 Withdrawals/Debits -  700.00",
            "Ending balance on 3/31 -$148.07",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert (stmt.beginning_balance, stmt.ending_balance) == (47.37, -148.07)


# ---------------------------------------------------------------------------
# W-F5 — a description that carries the record delimiter
# ---------------------------------------------------------------------------

_EDI_ROW = ("WF_TX|3/4|< Business to Business ACH Debit - A Vendor Pymnt 100001362074 "
            "500022281|Iea*0001*500022281|||590.93|")


class TestF5DelimiterBearingDescription:
    """An ACH row quotes EDI text that contains the record's own delimiter.

    Splitting the record left to right shifted every field after the
    description by one: the amount vanished and reference text was read as a
    money cell. Only the description can carry a delimiter and exactly three
    cells follow it, so the tail is taken from the right.
    """

    def test_f5_an_edi_description_does_not_shift_the_amount_columns(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 0.00 Withdrawals/Debits -  590.93",
            "Ending balance on 3/31 $409.07",
            "Overdraft Protection",
            _history(_EDI_ROW),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [-590.93]
        assert stmt.transactions[0].direction == "debit"
        assert stmt.transactions[0].description.endswith("500022281|Iea*0001*500022281|")

    def test_f5_negative_an_ordinary_row_is_unaffected(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  10.00",
            "Ending balance on 3/31 $1,490.00",
            "Overdraft Protection",
            _history(
                "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
                "WF_TX|3/3|Purchase authorized on 03/02 A Merchant||10.00|1,490.00",
            ),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [500.0, -10.0]
        assert [t.running_balance for t in stmt.transactions] == [1500.0, 1490.0]


# ---------------------------------------------------------------------------
# W-F6 — the multi-account statement
# ---------------------------------------------------------------------------

_TWO_ACCOUNTS = _document(
    "Summary of accounts",
    _account("1111111111", primary=True),
    "Statement period activity summary",
    "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  200.00",
    "Ending balance on 3/31 $1,300.00",
    "Overdraft Protection",
    _history(
        "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
        "WF_TX|3/3|Purchase authorized on 03/02 A Merchant||200.00|1,300.00",
    ),
    "Totals $500.00 $200.00",
    _account("2222222222", primary=False),
    "Statement period activity summary",
    "Beginning balance on 3/1 $50.00 Deposits/Credits 0.00 Withdrawals/Debits -  20.00",
    "Ending balance on 3/31 $30.00",
    "Overdraft Protection",
    _history("WF_TX|3/9|Service Charge||20.00|30.00"),
    "Totals $0.00 $20.00",
)


class TestF6MultiAccountStatement:
    """A Wells statement can carry more than one account.

    Each account owns a section that opens with its own number line, and one
    of them is marked `(primary account)`. `Statement` is single-account
    (MASTER_PLAN L-1), so the published ledger is the primary account's — the
    union of both against one account's summary is arithmetic over two
    different ledgers.
    """

    def test_f6_only_the_primary_account_ledger_is_published(self):
        stmt = parse_wells_statement(_TWO_ACCOUNTS)
        assert _amounts(stmt) == [500.0, -200.0]
        assert stmt.account_number == "1111111111"

    def test_f6_the_summary_published_is_the_primary_accounts(self):
        stmt = parse_wells_statement(_TWO_ACCOUNTS)
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 1000.0, 1300.0, 500.0, 200.0)

    def test_f6_the_second_accounts_ledger_reconciles_when_it_is_the_primary(self):
        """The rule is the marker, not the position: swap it and the other
        section is published."""
        swapped = (_TWO_ACCOUNTS
                   .replace("Account number:   1111111111  (primary account)",
                            "Account number:   1111111111")
                   .replace("Account number:   2222222222",
                            "Account number:   2222222222  (primary account)"))
        stmt = parse_wells_statement(swapped)
        assert _amounts(stmt) == [-20.0]
        assert stmt.account_number == "2222222222"
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 50.0, 30.0, 0.0, 20.0)

    def test_f6_negative_a_single_account_statement_is_unaffected(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  200.00",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            _history(
                "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
                "WF_TX|3/3|Purchase authorized on 03/02 A Merchant||200.00|1,300.00",
            ),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [500.0, -200.0]
        assert stmt.account_number == "1234567890"


# ---------------------------------------------------------------------------
# Fail-closed rules
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_a_row_whose_amount_is_in_neither_money_column_is_dropped(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  0.00",
            "Ending balance on 3/31 $1,500.00",
            "Overdraft Protection",
            _history(
                "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
                "WF_TX|3/3|Purchase authorized on 03/02 A Merchant|||",
            ),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [500.0]

    def test_a_row_whose_amount_is_in_both_money_columns_is_dropped(self):
        """The grid did not say which side the row is on, so the parser does
        not choose one; the bank's stated totals then refuse the document."""
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  38.65",
            "Ending balance on 3/31 $1,461.35",
            "Overdraft Protection",
            _history(
                "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
                "WF_TX|3/6|Purchase authorized on 03/05 A Merchant|8,175.00|38.65|",
            ),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [500.0]

    def test_a_summary_cell_printed_before_its_label_is_not_claimed_by_it(self):
        """A text layer that emits the value column ahead of the label column
        determines nothing; the period is still read, because the period is
        printed inside the label."""
        doc = _document(
            _account(),
            "Statement period activity summary",
            "540,916.15 Beginning balance on 6/1 Deposits/Credits Withdrawals/Debits - 44,275.81",
            "Ending balance on 6/30 $1,450,000.05",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert (stmt.period_start, stmt.period_end) == ("2054-06-01", "2054-06-30")
        assert stmt.beginning_balance is None
        assert stmt.stated_total_credits is None
        assert stmt.stated_total_debits == 44275.81
        assert stmt.ending_balance == 1450000.05

    def test_a_statement_with_no_ledger_publishes_nothing(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 0.00 Withdrawals/Debits -  0.00",
            "Ending balance on 3/31 $1,000.00",
            "WF_NATIVE_TRANSACTIONS",
            "WF_NATIVE_TRANSACTIONS_END",
        )
        assert parse_wells_statement(doc) is None


# ---------------------------------------------------------------------------
# Rules that constrain the block boundary
# ---------------------------------------------------------------------------

class TestSummaryBlockBoundary:
    def test_negative_the_transaction_history_column_header_is_not_a_summary_row(self):
        """`Deposits/ Credits` is the printed column header of the ledger, and
        it is below the heading that closes the summary block."""
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  200.00",
            "Ending balance on 3/31 $1,300.00",
            "Transaction history",
            "Date Check Number Description Deposits/ Credits Withdrawals/ Debits Ending daily balance",
            "WF_NATIVE_TRANSACTIONS",
            "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
            "WF_NATIVE_TRANSACTIONS_END",
            "Totals $500.00 $200.00",
        )
        stmt = parse_wells_statement(doc)
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 1000.0, 1300.0, 500.0, 200.0)

    def test_negative_a_heading_word_inside_prose_does_not_close_the_block(self):
        """A heading owns its line: the same words inside a sentence do not."""
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00",
            "See your Transaction history below for Overdraft Protection details",
            "Deposits/Credits 500.00 Withdrawals/Debits -  200.00",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            _ONE_ROW,
        )
        stmt = parse_wells_statement(doc)
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 1000.0, 1300.0, 500.0, 200.0)

    def test_negative_the_ledgers_ending_daily_balance_column_is_never_a_summary_row(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  200.00",
            "Ending balance on 3/31 $1,300.00",
            "Overdraft Protection",
            "Transaction history",
            "Ending daily balance 3/2 Deposit From A Customer 500.00 1,500.00",
            "WF_NATIVE_TRANSACTIONS",
            "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
            "WF_NATIVE_TRANSACTIONS_END",
        )
        stmt = parse_wells_statement(doc)
        assert stmt.ending_balance == 1300.0
        assert _amounts(stmt) == [500.0]


class TestPeriodEvidence:
    def test_a_period_that_crosses_new_year_dates_its_opening_to_the_prior_year(self):
        doc = "\n".join([
            "Wells Fargo Business Checking",
            "January 30, 2054         Page 1 of 4",
            _account(),
            "Statement period activity summary",
            "Beginning balance on 12/31 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  200.00",
            "Ending balance on 1/30 $1,300.00",
            "Overdraft Protection",
            _ONE_ROW.replace("WF_TX|3/2|", "WF_TX|1/2|"),
        ])
        stmt = parse_wells_statement(doc)
        assert (stmt.period_start, stmt.period_end) == ("2053-12-31", "2054-01-30")

    def test_the_summary_rows_are_read_even_when_the_ledger_is_printed_first(self):
        """`Account number:` opens the section; order inside it is the bank's."""
        doc = _document(
            _account(),
            _ONE_ROW,
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  0.00",
            "Ending balance on 3/31 $1,500.00",
        )
        stmt = parse_wells_statement(doc)
        assert _summary_of(stmt) == ("2054-03-01", "2054-03-31", 1000.0, 1500.0, 500.0, 0.0)
        assert _amounts(stmt) == [500.0]


class TestTheHistorysOwnRestatement:
    """The `Totals` row is the bank restating the history, not a posting (§ROWCAP).

    Where the restatement's band meets the last posting's, the grid emits one
    record carrying both, and the restatement's figures then read as that
    posting's amount — the statement's whole debit total published as a single
    debit that never happened. The currency symbol is the layout's own
    distinction: Wells sets it on the summary block and on the `Totals` row,
    and on no posting amount.
    """

    def test_a_restated_total_in_an_amount_cell_is_not_a_posting(self):
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  40.00",
            "Ending balance on 3/31 $1,460.00",
            _history(
                "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
                "WF_TX|3/31|Monthly Service Fee $500.00||$40.00|",
            ),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [500.0]

    def test_the_same_record_without_the_symbol_is_an_ordinary_posting(self):
        """The control: only the symbol separates the two readings."""
        doc = _document(
            _account(),
            "Statement period activity summary",
            "Beginning balance on 3/1 $1,000.00 Deposits/Credits 500.00 Withdrawals/Debits -  40.00",
            "Ending balance on 3/31 $1,460.00",
            _history(
                "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
                "WF_TX|3/31|Monthly Service Fee||40.00|1,460.00",
            ),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [500.0, -40.0]

    def test_negative_a_currency_symbol_in_the_description_does_not_refuse_the_row(self):
        """Only the two money COLUMNS are read for the symbol.

        Wells quotes the authorized amount inside a posting's own description
        (`Transaction Posted on <date> $<amount> ...`); that is description
        text and the row's printed cell is still its amount.
        """
        doc = _document(
            _account(),
            _ONE_ROW.replace(
                "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00",
                "WF_TX|3/2|Transaction Posted on 03/01 $500.00 From A Customer|500.00||1,500.00",
            ),
        )
        stmt = parse_wells_statement(doc)
        assert _amounts(stmt) == [500.0]
