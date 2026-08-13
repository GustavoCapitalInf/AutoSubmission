"""W3 §CHASE-CLOSURE — the two Chase residuals §CHASE-LAYOUTS left standing.

Card A′: `chase.py` refused a period in which nothing happened, because an
empty ledger and an unreadable ledger looked the same to it. The guard added
here separates them **on the bank's own printing** — instances stated, totals
stated, and the two balances — and never on the emptiness itself.

Card B1: Chase's savings statement is a different printed product with a
different grid, and it now has its own registration.

Every fixture below is synthetic. No customer, account number, amount or date
from the archive appears in this file.
"""
from __future__ import annotations

import re
from contextlib import contextmanager

import pytest

from analysis import chase, parser_registry_entries as entries
from analysis.chase import detect as chase_detect, parse_chase_statement

entries.load()


# ===========================================================================
# Card A′ — a period in which nothing happened
# ===========================================================================

#: Chase's statement for a period with no activity: the summary block prints an
#: instance count of 0 against every section and a closing balance equal to the
#: opening one, and no detail section is printed at all. Synthetic; the figures
#: are round numbers chosen so the identity is checkable by eye.
ZERO_ACTIVITY = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance $0.00\n"
    "Deposits and Additions 0 $0.00\n"
    "Checks Paid 0 $0.00\n"
    "Electronic Withdrawals 0 $0.00\n"
    "Fees 0 $0.00\n"
    "Ending Balance 0 $0.00\n"
    "*end*summary\n"
)

#: The same furniture on a period that plainly is NOT empty: the bank states
#: two deposits and one withdrawal, and the balance moved. The detail sections
#: are absent — which is what a reader that cannot read them looks like — so
#: this is the exact document the relaxed branch must never admit.
STATED_ACTIVITY_EMPTY_LEDGER = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance $1,000.00\n"
    "Deposits and Additions 2 $500.00\n"
    "Electronic Withdrawals 1 -$200.00\n"
    "Ending Balance 3 $1,300.00\n"
    "*end*summary\n"
)

#: No section prints an instance count at all, and the two balances disagree:
#: something moved this account and this document does not say what. Refused.
NO_COUNTS_BALANCES_DISAGREE = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "Beginning Balance $1,000.00\n"
    "Ending Balance $1,300.00\n"
    "*end*summary\n"
)

#: Zero instances, equal balances — and a stated deposit *total* that is not
#: zero. The document contradicts itself; the count alone would have admitted
#: it, which is why the stated totals are part of the test.
ZERO_COUNTS_NONZERO_TOTAL = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance $1,000.00\n"
    "Deposits and Additions 0 $250.00\n"
    "Ending Balance 0 $1,000.00\n"
    "*end*summary\n"
)

#: A zero-activity period on an account that is not empty: the balance simply
#: did not move. Nothing in the rule is about the figure being zero.
ZERO_ACTIVITY_NONZERO_BALANCE = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance $2,500.00\n"
    "Deposits and Additions 0 $0.00\n"
    "Checks Paid 0 $0.00\n"
    "Electronic Withdrawals 0 $0.00\n"
    "Fees 0 $0.00\n"
    "Ending Balance 0 $2,500.00\n"
    "*end*summary\n"
)


def test_a_period_in_which_nothing_happened_is_a_statement():
    statement = parse_chase_statement(ZERO_ACTIVITY)
    assert statement is not None
    assert statement.beginning_balance == 0.0
    assert statement.ending_balance == 0.0
    assert statement.transactions == []


def test_the_admitted_period_is_the_one_the_bank_printed_as_empty():
    """The rule is about the bank's printing, not about the figure being zero:
    an account holding a balance through a period with no activity is the same
    document class."""
    statement = parse_chase_statement(ZERO_ACTIVITY_NONZERO_BALANCE)
    assert statement is not None
    assert statement.beginning_balance == statement.ending_balance == 2500.0
    assert statement.transactions == []


def test_the_empty_ledger_is_exactly_what_the_previous_rule_refused():
    """The regression direction, asserted rather than described.

    The rule this guard replaced was `if not txns ... return None`, so a
    statement whose published ledger is empty is precisely the document it
    declined. Pinning the emptiness pins that this test would fail against the
    pre-guard tree.
    """
    statement = parse_chase_statement(ZERO_ACTIVITY)
    assert statement is not None and not statement.transactions


@pytest.mark.parametrize(
    "document",
    [STATED_ACTIVITY_EMPTY_LEDGER, NO_COUNTS_BALANCES_DISAGREE, ZERO_COUNTS_NONZERO_TOTAL],
    ids=["instances_stated", "balances_disagree", "total_stated"],
)
def test_an_empty_ledger_is_not_by_itself_a_zero_activity_statement(document):
    """The direction that matters. A section this reader failed to read leaves
    the same empty `txns` a genuinely empty period does; only the bank's own
    printing separates them, and on these three it says the period was not
    empty. Refusal is the fail-closed outcome, not a missed opportunity.
    """
    assert parse_chase_statement(document) is None


def test_the_document_is_still_detected_the_same_way():
    """The guard is a parse-level change; the markers and `detection_text` are
    untouched. Asserted over both directions rather than argued."""
    for document in (ZERO_ACTIVITY, STATED_ACTIVITY_EMPTY_LEDGER):
        detection = chase_detect(document)
        assert detection.matched == ("bank_name", "section_sentinels")
        assert detection.score == 0.5


def test_a_statement_with_a_ledger_is_unaffected_by_the_guard():
    """The relaxed branch is reachable only when the ledger is empty, so a
    document that reads normally cannot traverse it."""
    from tests.test_chase_layouts import OVERDRAWN_CHASE

    statement = parse_chase_statement(OVERDRAWN_CHASE)
    assert statement is not None
    assert len(statement.transactions) == 2


# ===========================================================================
# Card C — the money guard admits what the money finder finds
# ===========================================================================

#: The guard as it stood before card C. Restored in-process by the fixtures
#: below, which is what makes them regression tests rather than descriptions:
#: each one is verified to reproduce the defect against this pattern.
PRE_CARD_C_GUARD = re.compile(r"\(?-?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})?-?\)?")


@contextmanager
def pre_card_c_guard():
    """`analysis/chase.py` with the pre-card-C money guard put back."""
    shipped = chase._AMOUNT_RE
    chase._AMOUNT_RE = PRE_CARD_C_GUARD
    try:
        yield
    finally:
        chase._AMOUNT_RE = shipped


#: The two printed conventions co-occurring: the sign stands outside the
#: currency symbol, and the column's padding falls between them. The fee is
#: small on purpose — see the tolerance fixture below. The identity closes
#: exactly: 1,000.00 + 500.00 - 200.00 - 0.75 = 1,299.25.
DETACHED_SIGN_FEE = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance $1,000.00\n"
    "Deposits and Additions 1 500.00\n"
    "Electronic Withdrawals 1 - 200.00\n"
    "Fees 1 - $0.75\n"
    "Ending Balance 3 $1,299.25\n"
    "*end*summary\n"
    "*start*deposits and additions\n"
    "DEPOSITS AND ADDITIONS\n"
    "DATE DESCRIPTION AMOUNT\n"
    "01/05 Example Deposit Source 500.00\n"
    "Total Deposits and Additions $500.00\n"
    "*end*deposits and additions\n"
    "*start*electronic withdrawal\n"
    "ELECTRONIC WITHDRAWALS\n"
    "DATE DESCRIPTION AMOUNT\n"
    "01/09 Example Counterparty Payment 200.00\n"
    "Total Electronic Withdrawals $200.00\n"
    "*end*electronic withdrawal\n"
    "*start*fees section\n"
    "FEES\n"
    "DATE DESCRIPTION AMOUNT\n"
    "01/31 Example Monthly Service Fee 0.75\n"
    "Total Fees $0.75\n"
    "*end*fees section\n"
)


def test_the_guard_admits_every_shape_the_finder_finds():
    """The card-C invariant, stated as a property rather than as examples.

    `_SUMMARY_AMOUNT` finds the money in a summary row; `_AMOUNT_RE` guards
    what `_money` is allowed to scrub. A shape the first finds and the second
    refuses is not a refusal — it is a silent `0.00`, because every caller
    reads `abs(_money(...) or 0.0)`. The two must not drift apart again.
    """
    refused = [
        sign + symbol + number
        for sign in ("", "-", "- ", "-  ")
        for symbol in ("", "$", "$ ", "$  ")
        for number in ("0.00", "500.00", "530,178.70", "1,234,567.89")
        if re.fullmatch(chase._SUMMARY_AMOUNT, sign + symbol + number)
        and chase._money(sign + symbol + number) is None
    ]
    assert refused == [], f"the finder finds these and the guard refuses them: {refused}"


def test_a_detached_sign_summary_row_published_zero_before_card_c():
    """The defect, reproduced against the pre-card-C guard.

    Not a description of a bug: the fixture is run through the shipped parser
    twice, and the pre-card-C reading is asserted to be the wrong number.
    """
    with pre_card_c_guard():
        before = parse_chase_statement(DETACHED_SIGN_FEE)
    assert before is not None
    # The bank printed $0.75. The parser published nothing at all for it, and
    # the fee's absence from the debit total is the same silent zero.
    assert before.stated_service_charge == 0.0
    assert before.stated_total_debits == 200.00

    after = parse_chase_statement(DETACHED_SIGN_FEE)
    assert after is not None
    assert after.stated_service_charge == 0.75
    assert after.stated_total_debits == 200.75


def test_the_misread_fee_hid_inside_the_reconciliation_tolerance():
    """Why this one is worth a card: nothing downstream caught it.

    The bank-stated summary identity is accepted within ±1.00 (see
    `analysis/reconcile.py`), so a fee small enough to sit inside that window
    left the document reconciling — and shipping — with a stated service
    charge and a stated debit total that were both wrong. The fix does not
    move the tolerance; it removes the error that was hiding under it.
    """
    from analysis.reconcile import reconcile

    def residual(stmt):
        """The identity reconcile checks, with the service charge separate."""
        base = stmt.beginning_balance + stmt.stated_total_credits - stmt.stated_total_debits
        return round(base - (stmt.stated_service_charge or 0.0) - stmt.ending_balance, 2)

    with pre_card_c_guard():
        wrong = parse_chase_statement(DETACHED_SIGN_FEE)
        before = reconcile(wrong)
    # The document does not close — it is off by exactly the fee that was
    # read as zero — and nothing says so, because 0.75 is inside the window.
    assert residual(wrong) == 0.75
    assert before.summary_ok is True
    assert before.ok is True
    assert before.issues == []

    right = parse_chase_statement(DETACHED_SIGN_FEE)
    after = reconcile(right)
    assert residual(right) == -0.75  # the charge is now counted in both terms
    assert after.summary_ok is True
    assert after.issues == []


@pytest.mark.parametrize(
    "shape",
    ["( $500.00", "$-500.00"],
    ids=["unclosed_paren_with_gap", "sign_inside_the_symbol"],
)
def test_card_c_admits_the_detached_sign_and_nothing_else(shape):
    """The alignment is bound to the sign, not floated across the prefix.

    These two shapes are unattested on real Chase documents and stay out, so
    the guard widened by exactly one printed spelling. Recorded as a pin
    because "we only meant to admit one shape" is otherwise unverifiable.
    """
    assert chase._money(shape) is None
    with pre_card_c_guard():
        assert chase._money(shape) is None


def test_a_statement_that_read_correctly_before_is_unchanged():
    """The other direction: on every spelling that already parsed, card C is
    inert. The archive-wide form of this is the claimed-population sweep."""
    from tests.test_chase_layouts import OVERDRAWN_CHASE

    for document in (OVERDRAWN_CHASE, ZERO_ACTIVITY):
        with pre_card_c_guard():
            before = parse_chase_statement(document)
        after = parse_chase_statement(document)
        assert (before is None) == (after is None)
        if after is not None:
            assert before.__dict__ == after.__dict__
