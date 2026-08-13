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

import pytest

from analysis import parser_registry_entries as entries
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
