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
                          of the printed amounts; the balance still fixes the
                          credit SUBTOTAL, and TD's own codes rank the splits
                          that reach it (W3 §WITHHELDTD)
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
    _credit_count_candidates,
    _credit_counts_from_balances,
    _credit_target,
    _MAX_GROUP_ROWS,
    _MAX_SPLIT_CANDIDATES,
    _native_direction_code,
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

def test_f4_an_underdetermined_group_still_honours_the_printed_subtotal():
    """`{30}` and `{10, 20}` both reproduce the printed balance, so the grid
    does not say WHICH rows were deposits — but it does say the deposits total
    30.00, and that is not in doubt.

    The shipped reader used to drop the subtotal along with the row question:
    it kept the transaction-code reading, which here makes all three rows
    debits and a group the bank printed as a zero net change into a 60.00 one.
    That reading contradicts the page. The reader now keeps the subtotal and
    changes as little as the arithmetic requires — one row rather than two —
    and the bank's own printed COUNTS, which the chooser never reads, agree
    (W3 §WITHHELDTD)."""
    md = _statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 20.00 FEB01
THIRD UNCODED ROW 30.00 FEB01 100.00
""", credits="1 30.00", debits="2 30.00")
    stmt = parse_native_td_canada_statement(md)
    assert _amounts(stmt) == [-10.0, -20.0, 30.0]
    assert reconcile(stmt).ok
    assert analyze_markdown(md).reconciliation.ok


def test_f4_the_printed_counts_are_never_read_by_the_chooser():
    """The same ledger with the counts printed the OTHER way round is read
    identically — the chooser ranks on the balance and the codes, and the
    counts stay an independent oracle over the answer (they now disagree, and
    the platform says so rather than the parser bending to them)."""
    md = _statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 20.00 FEB01
THIRD UNCODED ROW 30.00 FEB01 100.00
""", credits="2 30.00", debits="1 30.00")
    stmt = parse_native_td_canada_statement(md)
    assert _amounts(stmt) == [-10.0, -20.0, 30.0]
    assert stmt.stated_credit_count == 2
    assert sum(1 for t in stmt.transactions if t.direction == "credit") == 1


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
    """TD prints these codes; the parser read only half of them.

    Each has a sibling printed in the same position by the same channel and
    meaning the opposite, which is what makes the code — and not the wording
    around it — the evidence. Both halves are now READ: `_native_direction_code`
    answers True, False or None, and the third value is the point. A row TD
    labelled a withdrawal and a row TD labelled nothing were the same answer to
    the shipped reader, and `_split_supported_by_codes` ranks on exactly that
    difference (W3 §WITHHELDTD).

    The vocabulary is asserted directly rather than through a document, for the
    reason the marker-boundary cases below make plain: in a document the
    printed balance fixes the credit subtotal first, so a fixture can only show
    a code CHANGING an answer where two admissible splits disagree about a row
    the code speaks for. Both kinds of test are here.
    """

    @pytest.mark.parametrize("description,code", [
        # The e-transfer pair: the direction is the leading verb.
        ("E-TFR ***a1B EPAY", True),
        ("E-TRANSFER ***a1B EPAY", True),
        ("SEND E-TFR ***a1B", False),
        # ...and the two forms TD leads with their own verb, which state
        # nothing about the direction and are left to the printed balances.
        ("CANCEL E-TFR ***a1B", None),
        ("RECLAIM E-TFR ***a1B", None),
        # The machine pair.
        ("TD ATM DEP 000000", True),
        ("TD ATM W/D 000000", False),
        # The deposit-channel pair; the unit number is statement data.
        ("GC 0000-DEPOSIT", True),
        ("GC 0000-CASH WITHDRA", False),
        # The account-transfer pair.
        ("UI494 TFR-FR 1111111", True),
        ("UW503 TFR-TO 1111111", False),
        # Trailing structural codes.
        ("SOMEWHERE INC MSP", True),
        ("SOMEWHERE INC CLN", True),
        ("SOMEWHERE INC PAY", True),
        ("SOMEWHERE INC GST", True),
        ("SOMEWHERE INC BUS", False),
        # Marker boundaries. Each of the four exists because a mutation of the
        # rule survived every other test in this file:
        #   E-TFRFEE ...        `startswith("E-TFR")` without the trailing space
        #   ACME E-TFR CORP     `"E-TFR " in text` (matched anywhere)
        #   REVERSAL TD ATM DEP `"TD ATM DEP" in text`
        #   REVERSAL GC n-DEP.  `_GC_DEPOSIT_RE.search` instead of `.match`
        # The native text layer collapses column gaps, so a joined token is the
        # standing risk in this parser: `E-TFRFEE` is not `E-TFR`.
        ("E-TFRFEE ***a1B", None),
        ("ACME E-TFR CORP", None),
        ("REVERSAL TD ATM DEP 000000", None),
        ("REVERSAL GC 0000-DEPOSIT", None),
        ("REVERSAL GC 0000-CASH WITHDRA", None),
        # A counterparty name is never a code, whichever way it usually falls.
        ("UNLISTED VENDOR ABC", None),
        ("UNLISTED EXAMPLE ROW", None),
    ])
    def test_the_code_vocabulary(self, description, code):
        assert _native_direction_code(description) is code

    #: A group the printed balance leaves open between `{30}` and `{10, 20}`.
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

    def test_an_uncoded_third_row_takes_the_smallest_change(self):
        """The baseline the two tests below are measured against: with no code
        anywhere, the reader honours the printed subtotal by moving ONE row."""
        assert self._read("UNLISTED VENDOR ABC") == [-10.0, -20.0, 30.0]

    def test_a_withdrawal_code_moves_the_deposit_off_that_row(self):
        """TD labelled the 30.00 row a withdrawal, and the balance says the
        deposits total 30.00, so the deposits are the 10.00 and the 20.00. The
        smallest-change reading would have put the deposit on the labelled row;
        a code the bank PRINTED outranks it."""
        assert self._read("SEND E-TFR ***a1B") == [10.0, 20.0, -30.0]

    def test_the_sibling_withdrawal_codes_do_the_same(self):
        """The half of each channel pair that was previously unread. Without
        them these two rows fell through to the default and were indexed as
        "TD says nothing", which is how a printed withdrawal could be handed
        the deposit label."""
        assert self._read("TD ATM W/D 000000") == [10.0, 20.0, -30.0]
        assert self._read("GC 0000-CASH WITHDRA") == [10.0, 20.0, -30.0]

    def test_a_deposit_code_keeps_the_deposit_on_its_row(self):
        """The other half of each pair, in the same fixture: the code reading
        already reaches the printed subtotal, so the reading it produces stands
        unchanged and no candidate is ever ranked."""
        for row in ("E-TFR ***a1B EPAY", "TD ATM DEP 000000", "GC 0000-DEPOSIT"):
            assert self._read(row) == [-10.0, -20.0, 30.0]

    def test_a_marker_that_does_not_open_the_description_is_not_a_code(self):
        """The document-level half of the boundary cases: none of these four
        may act as a withdrawal code, so each reads as the uncoded baseline."""
        for row in ("E-TFRFEE ***a1B", "ACME E-TFR CORP",
                    "REVERSAL TD ATM DEP 000000", "REVERSAL GC 0000-DEPOSIT"):
            assert self._read(row) == [-10.0, -20.0, 30.0]

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
        """W3 FILENAME-BOUNDARY / F-PROVENANCE, and here the counterfeit is
        REAL: this reader's anchor is the word `ACCOUNT`, not a line position,
        so a file named `ACCOUNT - USD.pdf` puts the exact token in the source
        comment. Unstripped, the comment flips a Canadian-dollar statement to
        USD; `admissible_text` — the production seam every parser sits behind —
        removes it first. Delete the boundary and this test fails, which is the
        property the earlier version of it did not have."""
        from analysis.parser_registry import admissible_text
        from analysis.td_can import _native_printed_currency

        comment = "<!-- source: ACCOUNT - USD.pdf | pages: 1 | model: x | empty: 0 -->\n\n"

        # (a) On a document whose product states no denomination, the filename
        #     is the ONLY thing carrying one: unstripped it decides the answer
        #     outright, turning an operator's rename into a published currency.
        silent = _statement(self.LEDGER).replace("ACCOUNT - CAD", "ACCOUNT")
        assert _native_printed_currency(comment + silent) == "USD"
        assert _native_printed_currency(admissible_text(comment + silent)) is None

        # (b) On a document that DOES state CAD, the filename does not flip the
        #     answer — the two-denominations guard catches it — but it destroys
        #     a good read: real evidence degrades to the bare default.
        stated = _statement(self.LEDGER)
        assert _native_printed_currency(comment + stated) is None
        assert _native_printed_currency(admissible_text(comment + stated)) == "CAD"

        admissible = admissible_text(comment + stated)
        assert "source:" not in admissible
        stmt = parse_native_td_canada_statement(admissible)
        assert stmt is not None
        assert stmt.currency == "CAD"
        assert stmt.account_name == "BUSINESS CHEQUING ACCOUNT - CAD"

    def test_the_account_name_carries_the_printed_suffix_not_a_fixed_one(self):
        """D-5. The name was the fixed string `BUSINESS CHEQUING ACCOUNT - CAD`,
        written whenever the header printed `BUSINESS CHEQUING`. Reading the
        denomination without reading the name off the same printed line
        published `currency='USD'` beside a name asserting `- CAD` on the three
        U.S.-dollar statements of this layout — one payload contradicting
        itself, from one line."""
        cad = parse_native_td_canada_statement(_statement(self.LEDGER))
        assert (cad.currency, cad.account_name) == (
            "CAD", "BUSINESS CHEQUING ACCOUNT - CAD",
        )
        usd = parse_native_td_canada_statement(
            _statement(self.LEDGER).replace("ACCOUNT - CAD", "ACCOUNT - USD")
        )
        assert (usd.currency, usd.account_name) == (
            "USD", "BUSINESS CHEQUING ACCOUNT - USD",
        )

    def test_the_account_name_drops_the_suffix_when_none_is_printed(self):
        """No document of this layout prints `BUSINESS CHEQUING` without a
        denomination today, so this is the fail-closed branch rather than an
        observed one: the name states what the page states, and a suffix is
        never invented to fill the gap."""
        from analysis.td_can import _native_product_name

        assert _native_product_name(None) == "BUSINESS CHEQUING ACCOUNT"
        document = _statement(self.LEDGER).replace("ACCOUNT - CAD", "ACCOUNT")
        stmt = parse_native_td_canada_statement(document)
        assert stmt is not None
        assert stmt.currency == "CAD"  # the layout default still stands
        assert stmt.account_name == "BUSINESS CHEQUING ACCOUNT"

    def test_the_printed_plan_token_is_not_appended_to_the_account_name(self):
        """The `Account Type` column also carries the plan (`EVERY DAY B`).
        It is printed, and it is deliberately not published: appending it would
        move the name on all 73 documents of this layout — six of them pinned —
        on `account`, an audited column, for no correctness gain. Only the
        suffix was ever wrong."""
        stmt = parse_native_td_canada_statement(_statement(self.LEDGER))
        assert "EVERY DAY" in _statement(self.LEDGER)
        assert stmt.account_name == "BUSINESS CHEQUING ACCOUNT - CAD"


# ---------------------------------------------------------------------------
# W3 §WITHHELDTD — the printed balance is the authority, and the codes rank the
# readings it admits. Each test below names the gate it pins; the mutation
# table in the log names the mutant each one kills.
# ---------------------------------------------------------------------------

class TestPrintedBalanceOutranksTheCodes:
    def test_the_target_is_the_printed_change_and_nothing_else(self):
        """`(delta + S) / 2`, in cents. 40 out, 10 in, printed change −30."""
        assert _credit_target([4000, 1000], -3000) == 1000

    @pytest.mark.parametrize("amounts,delta,why", [
        ([4000, 1001], -3000, "odd parity: no integer-cent split produces it"),
        ([4000, 1000], 6000, "target above the group's own total"),
        ([4000, 1000], -6000, "target below zero"),
        ([], 0, "an empty group states nothing"),
        ([1] * (_MAX_GROUP_ROWS + 1), 0, "more rows than the bound admits"),
    ])
    def test_the_target_refuses_rather_than_inventing_one(self, amounts, delta, why):
        assert _credit_target(amounts, delta) is None, why

    def test_the_candidates_all_reach_the_printed_target(self):
        candidates = _credit_count_candidates([3000, 2000, 1000], 0)
        assert candidates and len(candidates) == 2
        for counts in candidates:
            assert sum(value * n for value, n in counts.items()) == 3000

    def test_a_target_nothing_reaches_yields_no_candidates(self):
        """A target inside `[0, S]` that no subset of the printed amounts can
        make: 15.00 out of rows of 20.00 and 10.00. In range, and unreachable —
        so the printed balance and the printed amounts disagree, and the reader
        says nothing rather than choosing the nearest."""
        assert _credit_target([2000, 1000], 0) == 1500
        assert _credit_count_candidates([2000, 1000], 0) == []

    def test_a_zero_amount_row_is_not_a_dimension_of_the_search(self):
        """A genuine `$0.00` posting (a returned ACH) reaches this parser. The
        arithmetic has nothing to say about its column — calling it a deposit
        changes no subtotal — so it is not searched over, and the candidate
        carries no entry for it. Two consequences, both deliberate: there is no
        `left // value` that can divide by zero, and a `$0.00` row TD coded as
        a deposit is published as a withdrawal on a group this branch reaches.
        No money moves either way, and the bank's printed COUNT says so."""
        assert _credit_count_candidates([1000, 0], 1000) == [{1000: 1}]
        assert _credit_count_candidates([1000, 0, 0], 1000) == [{1000: 1}]

    def test_a_group_of_nothing_but_zero_rows_does_not_raise(self):
        """The degenerate shape the guard above used to exist for."""
        assert _credit_count_candidates([0, 0], 0) == [{}]

    def test_the_enumeration_reports_its_own_bound_rather_than_running_long(self):
        """Fifty distinct powers-of-two-ish amounts reach one target in far
        more ways than `_MAX_SPLIT_CANDIDATES`; the walk stops and says so, and
        `None` is not `[]` — "more work than a parser may do" is a different
        answer from "no reading exists"."""
        amounts = [100 + 2 * i for i in range(40)]
        delta = 0            # target = half the group's total
        result = _credit_count_candidates(amounts, delta)
        assert result is None
        assert _MAX_SPLIT_CANDIDATES > 1     # the bound admits the "exactly one" test

    def test_a_bounded_out_group_keeps_the_code_reading(self):
        """The whole-document consequence of the bound: no invention, and the
        reading the shipped parser produces today."""
        rows = "\n".join(
            f"UNCODED ROW {i:02d} {100 + 2 * i}.00 FEB01" for i in range(40)
        )
        total = sum(10000 + 200 * i for i in range(40)) / 100
        stmt = parse_native_td_canada_statement(_statement(
            f"BALANCE FORWARD JAN31 {total:.2f}\n{rows}\nLAST UNCODED ROW 5.00 FEB01 {total:.2f}\n"
        ))
        # every row a debit — the code reading, untouched by the enumeration
        assert all(t.amount < 0 for t in stmt.transactions)

    def test_a_group_whose_codes_already_match_the_page_is_left_exactly_alone(self):
        """The byte-identity property the archive replay rests on: where the
        code reading reproduces the printed change, no candidate is ranked and
        the reading is the one the shipped parser produced."""
        md = _statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 20.00 FEB01
SOMEWHERE INC MSP 30.00 FEB01 100.00
""")
        assert _amounts(parse_native_td_canada_statement(md)) == [-10.0, -20.0, 30.0]

    def test_a_group_the_page_contradicts_on_parity_is_left_to_the_codes(self):
        """101.00 − 100.00 = 1.00 against amounts of 10 and 20: `delta + S` is
        odd, so no split of these amounts produces the printed change. A row is
        missing or misread, the arithmetic refuses, and nothing is invented."""
        md = _statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.01 FEB01
SECOND UNCODED ROW 20.00 FEB01 101.00
""")
        assert _amounts(parse_native_td_canada_statement(md)) == [-10.01, -20.0]

    def test_the_reading_is_the_same_on_every_run(self):
        """A ranking with an unstable tie-break would publish a different
        ledger on a different dict ordering."""
        md = _statement("""
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 10.00 FEB01
SECOND UNCODED ROW 10.00 FEB01
THIRD UNCODED ROW 20.00 FEB01
FOURTH UNCODED ROW 20.00 FEB01 100.00
""")
        readings = {tuple(_amounts(parse_native_td_canada_statement(md))) for _ in range(8)}
        assert len(readings) == 1


class TestATieBeyondEveryOracleRefuses:
    """Review MAJOR-2. Four rows of 400, 300, 200 and 100 across a printed
    change of zero: the deposits must total 500.00, and `{300, 200}` and
    `{400, 100}` both reach it, both contradict no printed code, both move two
    rows off the default — and both call TWO rows deposits, so the bank's own
    printed COUNT cannot tell them apart either.

    Nothing the document prints separates the two readings, so the reader does
    not choose one. It leaves the group on the code reading, which here does
    not reproduce the printed change, and the ledger therefore does not close:
    the document withholds instead of publishing a coin toss.
    """

    LEDGER = """
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 400.00 FEB01
SECOND UNCODED ROW 300.00 FEB01
THIRD UNCODED ROW 200.00 FEB01
FOURTH UNCODED ROW 100.00 FEB01 100.00
"""

    def test_both_readings_are_admissible_and_count_alike(self):
        candidates = _credit_count_candidates([40000, 30000, 20000, 10000], 0)
        assert len(candidates) == 2
        for counts in candidates:
            assert sum(value * n for value, n in counts.items()) == 50000
            assert sum(counts.values()) == 2

    def test_the_group_is_left_on_the_code_reading(self):
        stmt = parse_native_td_canada_statement(_statement(self.LEDGER))
        assert _amounts(stmt) == [-400.0, -300.0, -200.0, -100.0]

    def test_and_the_document_does_not_publish(self):
        md = _statement(self.LEDGER, credits="2 500.00", debits="2 500.00")
        assert not reconcile(parse_native_td_canada_statement(md)).ok
        assert not analyze_markdown(md).reconciliation.ok

    def test_a_code_on_one_row_breaks_the_tie_and_the_ledger_closes(self):
        """The same four amounts with TD's own withdrawal code on one row:
        `{400, 100}` now contradicts a printed code and `{300, 200}` does not,
        so the page decides and the document publishes."""
        md = _statement(
            self.LEDGER.replace("FIRST UNCODED ROW", "SEND E-TFR ***a1B"),
            credits="2 500.00", debits="2 500.00",
        )
        stmt = parse_native_td_canada_statement(md)
        assert _amounts(stmt) == [-400.0, 300.0, 200.0, -100.0]
        assert reconcile(stmt).ok

    #: Not every tie is unbreakable, and building one that is not takes care.
    #: With every row uncoded, "rows moved off the default" IS the credit count,
    #: so two readings that tie on it cannot differ in count. Writing
    #: `moved = k + C - 2j` and `contradictions = (C - j) + d` over k credited
    #: rows, j of them credit-coded and d of them debit-coded, a tie on both
    #: keys needs `k1 - k2 = 2(j1 - j2)` and `d1 - d2 = j1 - j2` — one reading
    #: credits one more credit-coded row AND one more debit-coded row than the
    #: other, and two more rows in total. This is the smallest such ledger:
    #: `{300}` against `{100, 100, 100}`, both totalling the printed 300.00
    #: deposit subtotal, both contradicting two printed codes, both moving two
    #: rows — and calling ONE row a deposit against THREE.
    SEPARABLE = """
BALANCE FORWARD JAN31 100.00
UNLISTED ALPHA MSP 300.00 FEB01
UNLISTED BETA MSP 100.00 FEB01
UNLISTED GAMMA MSP 100.00 FEB01
SEND E-TFR ***a1B 100.00 FEB01 100.00
"""

    def test_a_tie_the_printed_counts_can_separate_is_not_refused(self):
        """The printed credit count is 3 on one reading and 1 on the other, so
        the bank's own footer can certify the choice. Both keys being spent,
        the enumeration's fixed order decides — and refusing here would
        withhold a document the evidence CAN settle."""
        candidates = _credit_count_candidates([30000, 10000, 10000, 10000], 0)
        assert sorted(sum(c.values()) for c in candidates) == [1, 3]
        stmt = parse_native_td_canada_statement(_statement(self.SEPARABLE))
        assert _amounts(stmt) == [-300.0, 100.0, 100.0, 100.0]

    def test_and_the_printed_count_is_what_certifies_it(self):
        """Printed `Credits 3`: the reading agrees and the document publishes.
        The chooser never reads that footer — it is the check, not the input,
        and on the other reading it would have said so."""
        md = _statement(self.SEPARABLE, credits="3 300.00", debits="1 300.00")
        stmt = parse_native_td_canada_statement(md)
        assert sum(1 for t in stmt.transactions if t.direction == "credit") == 3
        assert reconcile(stmt).ok
