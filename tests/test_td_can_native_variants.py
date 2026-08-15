"""W3 Track A / REEF-TD: TD Canada native-text layout families.

Every fixture here is a SYNTHETIC reproduction of a *structural shape* found in
the withheld td_canada population (W3-2 cell `td_canada_native x
detail_coverage`, 61 documents). The institution and column markers are TD's
own layout sentinels — the same ones the existing TD tests use, because they
are what the parser keys on — and every description, counterparty, date, amount
and account number is invented.

The one thing this layout loses, and why:

    DESCRIPTION        CHEQUE/DEBIT   DEPOSIT/CREDIT   DATE    BALANCE

TD prints five columns, but the native text layer emits each printed row as a
single line with the column gaps collapsed to single spaces, so a row arrives
as `<description> <amount> <DATE> [<balance>]`. The amount survives; *which of
the two money columns it came from* does not. Direction used to be read from
the description's trailing transaction code, which is not what the grid
encodes.

The bank prints the answer anyway: a running BALANCE on the last row of each
date group. Between two printed balances the signed amounts must equal the
difference the bank printed, so the lost column is recoverable arithmetic.

The families:

F1 two-money-column row   the amount is printed in one of two adjacent money
                          columns and the flattened text keeps neither the gap
                          nor the column; the transaction code disagrees with
                          the printed balance
F2 page-carried balance   a printed balance also arrives as the next page's
                          `BALANCE FORWARD` carry, which closes the group the
                          page break landed inside
F3 cheque-enclosure line  the ledger terminator is `<n> CHQS ENCLOSED`; the
                          count is statement data, and matching a literal count
                          left the ledger open past the end of the page
F4 underdetermined group  the printed balance delta admits more than one split
                          of the printed amounts — fail closed by design
F5 converted-amount row   a foreign-currency row prints its original amount
                          before the converted one
F6 overdraft balance      a printed balance carries the `OD` suffix and is
                          therefore negative

Each family carries a negative fixture: the rule must fire on the printed
structure, never on remembered wording.
"""
from __future__ import annotations

import pytest

from analysis.pipeline import analyze_markdown
from analysis.reconcile import reconcile
from analysis.td_can import (
    _credit_counts_from_balances,
    _MAX_GROUP_ROWS,
    parse_native_td_canada_statement,
)

#: The layout sentinels this parser recognises itself in, plus an invented
#: branch/account. Nothing below is a real institution's customer data.
_HEAD = """
--- Page 1 ---
Accounts issued by: THE TORONTO-DOMINION BANK
Statement of Account Account Type Statement From - To
Branch No. Account No. JAN 31/26 - FEB 28/26
BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY B
1111 1111-2222222 Page 1 of 1
DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE
"""

_TAIL = """
0 CHQS ENCLOSED NEXT STATEMENT DATE IS MAR 31/26
MONTHLY AVER. CR. BAL. $500.00
Credits {credits}
Debits {debits}
"""


def _statement(ledger: str, *, credits: str = "0 0.00", debits: str = "0 0.00") -> str:
    return _HEAD + ledger.strip("\n") + _TAIL.format(credits=credits, debits=debits)


def _amounts(stmt):
    return [t.amount for t in stmt.transactions]


# ---------------------------------------------------------------------------
# F1 - the printed BALANCE column decides the column, not the description
# ---------------------------------------------------------------------------

class TestF1TwoMoneyColumnRow:
    #: Identical rows, identical descriptions, identical amounts. The ONLY
    #: difference is the balance the bank printed at the end of the group — and
    #: it flips both directions. Nothing here can be answered from wording.
    LEDGER = """
BALANCE FORWARD JAN31 100.00
UNLISTED VENDOR ABC 40.00 FEB01
MONTHLY PLAN FEE 10.00 FEB01 {closing}
"""

    def test_uncoded_row_is_a_deposit_when_the_balance_rose(self):
        # 100.00 + 40.00 - 10.00 = 130.00: the uncoded row is the deposit.
        stmt = parse_native_td_canada_statement(
            _statement(self.LEDGER.format(closing="130.00"))
        )
        assert _amounts(stmt) == [40.0, -10.0]

    def test_same_rows_are_both_withdrawals_when_the_balance_fell(self):
        # 100.00 - 40.00 - 10.00 = 50.00: same text, opposite answer.
        stmt = parse_native_td_canada_statement(
            _statement(self.LEDGER.format(closing="50.00"))
        )
        assert _amounts(stmt) == [-40.0, -10.0]

    def test_printed_balance_outranks_a_credit_transaction_code(self):
        # `MSP` is one of TD's own credit codes, and the old reading trusted
        # it. The printed balance says this one was a withdrawal.
        stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
SOMEWHERE INC MSP 40.00 FEB01
MONTHLY PLAN FEE 10.00 FEB01 50.00
"""))
        assert _amounts(stmt) == [-40.0, -10.0]

    def test_a_resolved_statement_reconciles_against_the_bank_summary(self):
        # The summary block is evidence the solver never reads, so this is a
        # real check and not a restatement of the input.
        md = _statement(
            self.LEDGER.format(closing="130.00"), credits="1 40.00", debits="1 10.00"
        )
        report = analyze_markdown(md)
        assert report.model_used == "td-canada-trust-deterministic"
        assert report.reconciliation.ok

    def test_the_group_spans_dates_not_just_one_day(self):
        # TD prints one balance per date group, so a group routinely covers
        # several printed dates. Segmentation is by printed balance, not date.
        stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 40.00 FEB01
SECOND UNCODED ROW 25.00 FEB02
THIRD UNCODED ROW 10.00 FEB03 155.00
"""))
        assert _amounts(stmt) == [40.0, 25.0, -10.0]


# ---------------------------------------------------------------------------
# F2 - a page-carried BALANCE FORWARD is a printed balance like any other
# ---------------------------------------------------------------------------

def test_f2_page_carry_closes_the_group_the_page_break_landed_in():
    """Splitting at the carry determines a group that merging leaves ambiguous.

    Merged, the three amounts (10, 20, 30) can reach the printed change either
    as {30} or as {10, 20}. Split at the carried balance, each half has exactly
    one answer.
    """
    md = """
--- Page 1 ---
Accounts issued by: THE TORONTO-DOMINION BANK
Branch No. Account No. JAN 31/26 - FEB 28/26
BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY B
1111 1111-2222222 Page 1 of 2
DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 20.00 FEB01
0 CHQS ENCLOSED NEXT STATEMENT DATE IS MAR 31/26
--- Page 2 ---
Accounts issued by: THE TORONTO-DOMINION BANK
Branch No. Account No. JAN 31/26 - FEB 28/26
BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY B
1111 1111-2222222 Page 2 of 2
DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE
BALANCE FORWARD FEB01 130.00
THIRD UNCODED ROW 30.00 FEB02 100.00
0 CHQS ENCLOSED NEXT STATEMENT DATE IS MAR 31/26
MONTHLY AVER. CR. BAL. $500.00
Credits 2 30.00
Debits 1 30.00
"""
    stmt = parse_native_td_canada_statement(md)
    assert _amounts(stmt) == [10.0, 20.0, -30.0]
    assert stmt.beginning_balance == 100.0
    assert stmt.ending_balance == 100.0


def test_f2_negative_the_first_balance_forward_is_the_opening_not_a_carry():
    stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
ONLY UNCODED ROW 40.00 FEB01 140.00
"""))
    assert stmt.beginning_balance == 100.0
    assert _amounts(stmt) == [40.0]


# ---------------------------------------------------------------------------
# F3 - the ledger terminator carries a count, and the count is data
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("enclosed", ["0", "1", "7", "10"])
def test_f3_ledger_closes_whatever_cheque_count_is_enclosed(enclosed):
    """The terminator used to be matched as a literal zero count, so on every
    statement that encloses a cheque the ledger stayed open across the summary
    block and on into the next page's letterhead.

    The row-shaped line after the terminator is a deliberate probe, not a claim
    about what TD prints there: it pins the boundary, so that whatever ends up
    below the terminator can never be read as a ledger row.
    """
    md = _HEAD + f"""
BALANCE FORWARD JAN31 100.00
ONLY UNCODED ROW 40.00 FEB01 140.00
{enclosed} CHQS ENCLOSED NEXT STATEMENT DATE IS MAR 31/26
STRAY TRAILER ROW 5.00 FEB02
MONTHLY AVER. CR. BAL. $500.00
Credits 1 40.00
Debits 0 0.00
"""
    stmt = parse_native_td_canada_statement(md)
    assert _amounts(stmt) == [40.0]
    assert stmt.stated_total_credits == 40.0
    assert stmt.stated_total_debits == 0.0


def test_f3_negative_a_row_whose_description_mentions_cheques_is_not_a_terminator():
    stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
2 CHQS RETURNED FEE 40.00 FEB01
ANOTHER UNCODED ROW 10.00 FEB02 50.00
"""))
    assert _amounts(stmt) == [-40.0, -10.0]


# ---------------------------------------------------------------------------
# F4 - an underdetermined group fails closed
# ---------------------------------------------------------------------------

def test_f4_underdetermined_group_does_not_reconcile():
    """`{30}` and `{10, 20}` both reproduce the printed balance, so the grid
    does not say which rows were deposits. The rows are still emitted with the
    transaction-code reading, and the bank's own stated totals — which the
    solver never reads — reject the statement."""
    md = _statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 20.00 FEB01
THIRD UNCODED ROW 30.00 FEB01 100.00
""", credits="1 30.00", debits="2 30.00")
    stmt = parse_native_td_canada_statement(md)
    # the code reading: nothing here carries a TD credit code, so all debits
    assert _amounts(stmt) == [-10.0, -20.0, -30.0]
    assert not reconcile(stmt).ok
    assert not analyze_markdown(md).reconciliation.ok


def test_f4_ambiguity_does_not_leak_into_neighbouring_groups():
    """A group the grid cannot settle must not poison the ones it can."""
    stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 20.00 FEB01
THIRD UNCODED ROW 30.00 FEB01 100.00
FOURTH UNCODED ROW 40.00 FEB02 140.00
"""))
    assert _amounts(stmt)[-1] == 40.0


# ---------------------------------------------------------------------------
# F5 / F6 - shapes that were already right, pinned so the grouping keeps them
# ---------------------------------------------------------------------------

def test_f5_converted_amount_next_to_the_date_column_is_the_row_amount():
    """A foreign-currency row prints the original amount inside the
    description and the converted amount in the money column."""
    stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
FUEL STOP 12 $ 8.00 11.00 FEB01 89.00
"""))
    assert _amounts(stmt) == [-11.0]
    assert stmt.transactions[0].description == "FUEL STOP 12 $ 8.00"


def test_f6_overdraft_suffixed_balances_are_negative():
    stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 20.00OD
UNCODED DEPOSIT ROW 50.00 FEB01 30.00
"""))
    assert stmt.beginning_balance == -20.0
    assert _amounts(stmt) == [50.0]
    assert stmt.ending_balance == 30.0


def test_f6_overdraft_closing_balance_is_negative():
    stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 20.00
UNCODED ROW ONE 50.00 FEB01 30.00OD
"""))
    assert _amounts(stmt) == [-50.0]
    assert stmt.ending_balance == -30.0


# ---------------------------------------------------------------------------
# The solver itself
# ---------------------------------------------------------------------------

class TestCreditCountsFromBalances:
    def test_unique_split_is_returned(self):
        assert _credit_counts_from_balances([4000, 1000], 3000) == {4000: 1, 1000: 0}

    def test_all_debits(self):
        assert _credit_counts_from_balances([4000, 1000], -5000) == {4000: 0, 1000: 0}

    def test_all_credits(self):
        assert _credit_counts_from_balances([4000, 1000], 5000) == {4000: 1, 1000: 1}

    def test_two_splits_are_not_a_determination(self):
        # {3000} and {1000, 2000} both reach the same printed change.
        assert _credit_counts_from_balances([1000, 2000, 3000], 0) is None

    def test_a_delta_no_split_can_reach_is_not_a_determination(self):
        assert _credit_counts_from_balances([4000, 1000], 999) is None

    def test_a_delta_larger_than_the_rows_is_not_a_determination(self):
        assert _credit_counts_from_balances([4000, 1000], 6000) is None

    def test_equal_amounts_are_counted_not_identified(self):
        # One of the two 1000s is a deposit; the arithmetic cannot say which,
        # and every total is the same either way.
        assert _credit_counts_from_balances([1000, 1000], 0) == {1000: 1}

    def test_no_rows_is_not_a_determination(self):
        assert _credit_counts_from_balances([], 0) is None

    def test_group_row_bound_is_enforced(self):
        amounts = [1] * (_MAX_GROUP_ROWS + 1)
        assert _credit_counts_from_balances(amounts, len(amounts)) is None

    def test_equal_amount_tie_break_prefers_the_coded_row(self):
        # Same amount twice, one deposit. The arithmetic is indifferent, so
        # TD's own credit code decides which row carries it.
        stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
SOMEWHERE INC MSP 40.00 FEB01
UNLISTED VENDOR ABC 40.00 FEB01 100.00
"""))
        assert _amounts(stmt) == [40.0, -40.0]


# ---------------------------------------------------------------------------
# Fall-back behaviour: no printed balance at all
# ---------------------------------------------------------------------------

def test_rows_with_no_printed_balance_keep_the_transaction_code_reading():
    stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
SOMEWHERE INC MSP 40.00 FEB01
MONTHLY PLAN FEE 10.00 FEB01
"""))
    assert _amounts(stmt) == [40.0, -10.0]
    assert stmt.ending_balance is None


# ---------------------------------------------------------------------------
# C1 - three more of TD's own structural codes
# ---------------------------------------------------------------------------

class TestC1AdditiveCreditCodes:
    """TD prints these three; the parser read none of them as credits.

    Each has a sibling printed in the same position by the same channel and
    meaning the opposite, which is what makes the code — and not the wording
    around it — the evidence. The group below is deliberately underdetermined
    (`{30}` and `{10, 20}` both reproduce the printed balance), because that is
    the only place a transaction code decides anything: where the grid can
    answer, it outranks the code, and the last test pins that it still does.
    """

    LEDGER = """
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 20.00 FEB01
{row} 30.00 FEB01 100.00
"""

    def _read(self, row: str):
        return _amounts(parse_native_td_canada_statement(
            _statement(self.LEDGER.format(row=row))
        ))

    def test_an_incoming_e_transfer_is_a_credit(self):
        # `SEND E-TFR ...` leaves the account; a bare `E-TFR ...` arrives in
        # it. Only the spelled-out `E-TRANSFER` was ever read.
        assert self._read("E-TFR ***a1B EPAY") == [-10.0, -20.0, 30.0]

    def test_an_outgoing_e_transfer_is_still_a_debit(self):
        assert self._read("SEND E-TFR ***a1B") == [-10.0, -20.0, -30.0]

    def test_a_deposit_at_a_td_machine_is_a_credit(self):
        assert self._read("TD ATM DEP 000000") == [-10.0, -20.0, 30.0]

    def test_a_withdrawal_at_the_same_machine_is_not(self):
        assert self._read("TD ATM W/D 000000") == [-10.0, -20.0, -30.0]

    def test_a_deposit_channel_row_is_a_credit(self):
        assert self._read("GC 0000-DEPOSIT") == [-10.0, -20.0, 30.0]

    def test_the_same_channels_cash_withdrawal_is_not(self):
        # The unit number is statement data, so the marker cannot contain it;
        # the direction is the printed suffix, and this is the other suffix.
        assert self._read("GC 0000-CASH WITHDRA") == [-10.0, -20.0, -30.0]

    # Each code is a whole leading TOKEN of the description, because that is
    # where TD prints the channel: at the start of its own column. The four
    # tests below are the ones that say so, and each exists because a mutation
    # of the rule survived every other test in this file:
    #
    #   E-TFRFEE ...        `startswith("E-TFR")` without the trailing space
    #   ACME E-TFR CORP     `"E-TFR " in text` (matched anywhere)
    #   REVERSAL TD ATM DEP `"TD ATM DEP" in text`
    #   REVERSAL GC n-DEP.  `_GC_DEPOSIT_RE.search` instead of `.match`
    #
    # None of them can be rescued by the `SEND E-TFR` guard, which is what made
    # `test_an_outgoing_e_transfer_is_still_a_debit` insufficient on its own.

    def test_a_longer_token_that_merely_begins_with_the_code_is_not_a_transfer(self):
        # The native text layer collapses column gaps, so a joined token is the
        # standing risk in this parser: `E-TFRFEE` is not `E-TFR`.
        assert self._read("E-TFRFEE ***a1B") == [-10.0, -20.0, -30.0]

    def test_the_transfer_code_must_open_the_description(self):
        assert self._read("ACME E-TFR CORP") == [-10.0, -20.0, -30.0]

    def test_the_atm_code_must_open_the_description(self):
        # A reversal of a deposit is not a deposit.
        assert self._read("REVERSAL TD ATM DEP 000000") == [-10.0, -20.0, -30.0]

    def test_the_deposit_channel_code_must_open_the_description(self):
        assert self._read("REVERSAL GC 0000-DEPOSIT") == [-10.0, -20.0, -30.0]

    def test_the_printed_balance_still_outranks_the_new_codes(self):
        # 100.00 - 40.00 - 10.00 = 50.00. The grid says the incoming-transfer
        # row left the account, and the grid wins.
        stmt = parse_native_td_canada_statement(_statement("""
BALANCE FORWARD JAN31 100.00
E-TFR ***a1B EPAY 40.00 FEB01
MONTHLY PLAN FEE 10.00 FEB01 50.00
"""))
        assert _amounts(stmt) == [-40.0, -10.0]


# ---------------------------------------------------------------------------
# F7 — the printed denomination (W3 #CURRENCY).
#
# The `Account Type` column carries the account's currency as a suffix on the
# product name — `BUSINESS CHEQUING ACCOUNT - CAD`, `... - USD` — wrapped
# across two lines by the column width on most issues. Three archive documents
# of this layout print `ACCOUNT - USD` and were published as CAD by a constant.
# One prints `BUSINESS INVESTOR ACCOUNT`, a product with no denomination at
# all, and keeps the layout's default.
# ---------------------------------------------------------------------------

class TestF7PrintedDenomination:
    LEDGER = """
BALANCE FORWARD JAN31 100.00
UNLISTED VENDOR ABC 40.00 FEB01 60.00
"""

    def test_the_cad_product_suffix_publishes_cad(self):
        stmt = parse_native_td_canada_statement(_statement(self.LEDGER))
        assert stmt is not None
        assert stmt.currency == "CAD"

    def test_the_usd_product_suffix_publishes_usd(self):
        """The mover class."""
        document = _statement(self.LEDGER).replace("ACCOUNT - CAD", "ACCOUNT - USD")
        stmt = parse_native_td_canada_statement(document)
        assert stmt is not None
        assert stmt.currency == "USD"

    def test_the_suffix_is_read_when_the_column_wraps_it_onto_its_own_line(self):
        """The ordinary printing: the column is too narrow for the product."""
        document = _statement(self.LEDGER).replace(
            "BUSINESS CHEQUING ACCOUNT - USD", "BUSINESS CHEQUING\nACCOUNT - USD",
        ).replace(
            "BUSINESS CHEQUING ACCOUNT - CAD", "BUSINESS CHEQUING\nACCOUNT - USD",
        )
        stmt = parse_native_td_canada_statement(document)
        assert stmt is not None
        assert stmt.currency == "USD"

    def test_a_product_with_no_denomination_keeps_the_layout_default(self):
        """`BUSINESS INVESTOR ACCOUNT` states no currency, so neither do we —
        and the branch address is not consulted to guess one."""
        document = _statement(self.LEDGER).replace(
            "BUSINESS CHEQUING ACCOUNT - CAD", "BUSINESS\nINVESTOR\nACCOUNT",
        )
        stmt = parse_native_td_canada_statement(document)
        assert stmt is not None
        assert stmt.currency == "CAD"

    def test_negative_a_cad_draft_posting_is_not_the_account_denomination(self):
        """TD prints `CAD DRAFT 11512638` as a posting description on eight
        archive documents: the DRAFT's denomination, not the account's. A bare
        token scan would flip a U.S.-dollar account on its own ledger."""
        document = _statement(
            """
BALANCE FORWARD JAN31 100.00
CAD DRAFT 11512638 40.00 FEB01 60.00
"""
        ).replace("ACCOUNT - CAD", "ACCOUNT - USD")
        stmt = parse_native_td_canada_statement(document)
        assert stmt is not None
        assert stmt.currency == "USD"

    def test_negative_two_denominations_printed_keep_the_default(self):
        """A statement of several accounts in different currencies states no
        single one, so the reader refuses rather than picking the first."""
        from analysis.td_can import _native_printed_currency

        document = _statement(self.LEDGER).replace(
            "BUSINESS CHEQUING ACCOUNT - CAD",
            "BUSINESS CHEQUING ACCOUNT - CAD\nBUSINESS CHEQUING ACCOUNT - USD",
        )
        assert _native_printed_currency(document) is None
        stmt = parse_native_td_canada_statement(document)
        assert stmt is not None
        assert stmt.currency == "CAD"

    def test_negative_the_source_filename_cannot_set_the_currency(self):
        """W3 FILENAME-BOUNDARY. The three archive documents that print
        `ACCOUNT - USD` are also named `TD USD JAN.pdf` and friends. The right
        answer here comes from the `Account Type` column; a reader that could
        also see the operator's filename would be right by luck on these three
        and wrong on the next document someone renames."""
        from analysis.td_can import _native_printed_currency

        document = _statement(self.LEDGER)
        commented = (
            "<!-- source: TD USD JAN.pdf | pages: 1 | model: x | empty: 0 -->\n\n"
            + document
        )
        assert _native_printed_currency(commented) == "CAD"
        stmt = parse_native_td_canada_statement(commented)
        assert stmt is not None
        assert stmt.currency == "CAD"
