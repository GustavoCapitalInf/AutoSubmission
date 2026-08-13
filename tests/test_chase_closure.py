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
from analysis.chase_savings import (
    DETECTION_MARKERS as SAVINGS_MARKERS,
    detect as detect_savings,
    detection_text as savings_detection_text,
    parse_chase_savings_statement,
)
from analysis.parser_registry import by_id, resolve

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


# ===========================================================================
# Card B1 — the Chase savings product
# ===========================================================================

#: A Chase savings statement. Synthetic; the figures are round numbers chosen
#: so that every printing the platform checks can be verified by eye:
#: 1,000.00 + 500.00 = 1,500.00 - 200.00 = 1,300.00 + 200.00 = 1,500.00.
#:
#: Both amount-cell spellings this product prints are present. Rows 1 and 3
#: carry the AMOUNT cell wrapped onto the line ABOVE the row, which is what a
#: full Description column does to this grid; row 2 prints both cells inline,
#: with the sign detached from the figure.
SAVINGS_HEADER = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2026 through January 31, 2026\n"
    "Account Number: 000000000000000\n"
    "*start*summary\n"
    "Chase Business Total Savings\n"
    "SAVINGS SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance $1,000.00\n"
    "Deposits and Additions 2 700.00\n"
    "Other Withdrawals 1 - 200.00\n"
    "Ending Balance 3 $1,500.00\n"
    "Annual Percentage Yield Earned This Period 0.50%\n"
    "Interest Paid This Period $0.00\n"
    "*end*summary\n"
)
SAVINGS_GRID = (
    "*start*transaction detail\n"
    "TRANSACTION DETAIL\n"
    "DATE DESCRIPTION AMOUNT BALANCE\n"
    "Beginning Balance $1,000.00\n"
    "500.00\n"
    "01/05 Example Inbound Transfer 1,500.00\n"
    "01/09 Example Outbound Transfer - 200.00 1,300.00\n"
    "200.00\n"
    "01/31 Example Interest Payment 1,500.00\n"
    "Ending Balance $1,500.00\n"
    "*end*transaction detail\n"
)
SAVINGS = SAVINGS_HEADER + SAVINGS_GRID


def _savings():
    statement = parse_chase_savings_statement(SAVINGS)
    assert statement is not None
    return statement


# --------------------------------------------------------------- detection

def test_the_savings_layout_is_claimed_by_exactly_one_registration():
    dispatch = resolve(SAVINGS)
    assert dispatch.outcome == "claimed"
    assert dispatch.registration.id == "chase_savings"
    assert len(dispatch.candidates) == 1


def test_the_supersedes_edge_is_what_keeps_this_document_out_of_review():
    """The edge does real work, and this proves it rather than assuming it.

    A Chase savings statement carries `chase`'s own two required markers - the
    bank name and the `*start*summary` sentinel - so both registrations claim
    it. Without the edge that is two claimants, which resolves `ambiguous` and
    routes a perfectly readable document to review.
    """
    assert chase_detect(SAVINGS).claims
    assert detect_savings(SAVINGS).claims
    assert by_id("chase_savings").supersedes == frozenset({"chase"})
    assert resolve(SAVINGS).outcome == "claimed"


def test_chase_still_declines_the_savings_layout_on_its_own():
    """The edge shadows a parser that was never going to read this document:
    `chase` hard-requires CHECKING SUMMARY."""
    assert parse_chase_statement(SAVINGS) is None


def test_the_checking_product_is_positively_excluded():
    """The safety property the `supersedes` edge rests on.

    `chase_savings` cannot claim a checking statement - not "does not happen
    to", but is ruled out by an EXCLUDING marker - so the edge can never
    silence `chase` on a document `chase` owns. A combined statement printing
    both summaries therefore stays with `chase`.
    """
    from tests.test_chase_layouts import OVERDRAWN_CHASE

    assert not detect_savings(OVERDRAWN_CHASE).claims
    combined = SAVINGS.replace("SAVINGS SUMMARY", "SAVINGS SUMMARY\nCHECKING SUMMARY")
    detection = detect_savings(combined)
    assert detection.score == 0.0
    assert detection.excluded_by == "checking_summary"
    assert parse_chase_savings_statement(combined) is None


@pytest.mark.parametrize(
    "marker", [m.id for m in SAVINGS_MARKERS if m.kind == "required"]
)
def test_no_single_savings_marker_is_enough_to_claim(marker):
    """The single-marker invariant, stated for this registration."""
    only = {
        "section_sentinels": "*start*summary\n",
        "savings_summary": "SAVINGS SUMMARY\n",
        "transaction_detail_grid": "Date Description Amount Balance\n",
    }[marker]
    assert not detect_savings(only).claims


def test_a_savings_product_named_in_a_transaction_line_is_not_a_claim():
    """The R4-3 property. Deliberately adversarial rather than trivially
    negative: this other bank's statement fires TWO of the three required
    markers from its own transaction lines, so the Chase text-layer sentinel
    alone has to carry the negative."""
    other_bank = (
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 TRANSFER TO SAVINGS SUMMARY ACCOUNT 250.00\n"
        "01/16 SEE DATE DESCRIPTION AMOUNT BALANCE OVERLEAF 0.00\n"
    )
    fired = sorted(
        m.id for m in SAVINGS_MARKERS
        if m.kind == "required" and m.test(savings_detection_text(other_bank))
    )
    assert fired == ["savings_summary", "transaction_detail_grid"]
    assert not detect_savings(other_bank).claims


def test_savings_detection_reads_nothing_from_the_source_filename():
    document = (
        "<!-- source: Chase SAVINGS SUMMARY statement.pdf | pages: 1 | "
        "model: native-pdf-text | empty: 0 -->\n\nSome other bank statement\n"
    )
    assert detect_savings(document).score == 0.0


# ------------------------------------------------------------------- parse

def test_the_savings_ledger_reproduces_every_figure_the_statement_prints():
    """The in-document instrument, as a fixture: printings that do not derive
    from one another all have to agree."""
    statement = _savings()
    assert [t.amount for t in statement.transactions] == [500.00, -200.00, 200.00]
    assert [t.running_balance for t in statement.transactions] == [1500.00, 1300.00, 1500.00]

    prev = statement.beginning_balance
    for txn in statement.transactions:
        assert round(prev + txn.amount, 2) == txn.running_balance
        prev = txn.running_balance

    moved = sum(t.amount for t in statement.transactions)
    assert round(statement.beginning_balance + moved, 2) == statement.ending_balance == 1500.00
    assert statement.transactions[-1].running_balance == statement.ending_balance
    assert statement.stated_credit_count == 2
    assert statement.stated_debit_count == 1
    assert statement.stated_total_credits == 700.00
    assert statement.stated_total_debits == 200.00


def test_the_amount_cell_that_wrapped_above_its_row_belongs_to_that_row():
    """The structural rule, exercised in both directions on one document.
    Rows 1 and 3 print their amount on the line above; row 2 prints it inline.
    """
    statement = _savings()
    assert statement.transactions[0].amount == 500.00
    assert statement.transactions[2].amount == 200.00


def test_a_bare_money_line_inside_a_row_is_its_balance_not_the_next_amount():
    """The other half of the same rule, and why it is decided by the group
    boundary rather than by the token.

    Here the Description column wraps as well, so the row's own balance lands
    on a line of its own and the description continues after it. A rule that
    read "a bare money line is the next row's amount" would steal this row's
    balance and mis-read every row after it.
    """
    split_row = SAVINGS.replace(
        "01/05 Example Inbound Transfer 1,500.00\n",
        "01/05 Example Inbound Transfer Reference\n1,500.00\n0000000001\n",
    )
    statement = parse_chase_savings_statement(split_row)
    assert statement is not None
    assert [t.amount for t in statement.transactions] == [500.00, -200.00, 200.00]
    assert [t.running_balance for t in statement.transactions] == [1500.00, 1300.00, 1500.00]


def test_the_grid_bound_rows_are_not_transactions():
    """`Beginning Balance` and `Ending Balance` inside the grid are the
    period's endpoints. Publishing them as rows would double-count both."""
    statement = _savings()
    assert len(statement.transactions) == 3
    assert not any("balance" in t.description.lower() for t in statement.transactions)


def test_a_flattened_grid_does_not_absorb_its_closing_bound():
    """One producer prints the whole grid on a single physical line. The
    closing bound then stands at the end of the last row, where its figure
    would be read as that row's Balance cell - the `square_checking`
    money-bearing-footer defect in this layout's shape.
    """
    flattened = SAVINGS_HEADER + (
        "*start*transaction detail\n"
        "TRANSACTION DETAIL\n"
        "DATE DESCRIPTION AMOUNT BALANCE\n"
        "Beginning Balance $1,000.00\n"
        "01/05 Example Inbound Transfer 500.00 1,500.00 "
        "01/09 Example Outbound Transfer - 200.00 1,300.00 "
        "01/31 Example Interest Payment 200.00 1,500.00 Ending Balance $1,500.00\n"
        "*end*transaction detail\n"
    )
    statement = parse_chase_savings_statement(flattened)
    assert statement is not None
    assert [t.amount for t in statement.transactions] == [500.00, -200.00, 200.00]
    assert [t.running_balance for t in statement.transactions] == [1500.00, 1300.00, 1500.00]


def test_direction_is_the_printed_sign_and_not_the_description():
    statement = _savings()
    assert [t.direction for t in statement.transactions] == ["credit", "debit", "credit"]


def test_the_savings_description_is_sliced_between_date_and_money_columns():
    """Sliced by position, because an amount's characters occur again inside
    the balance printed beside it. Case is published as the bank printed it."""
    statement = _savings()
    assert [t.description for t in statement.transactions] == [
        "Example Inbound Transfer",
        "Example Outbound Transfer",
        "Example Interest Payment",
    ]


def test_the_savings_posting_date_is_the_first_printed_date():
    """A transfer row prints the transaction date after the posting date;
    dating a row by the second attributes its end-of-day balance to a day the
    bank does not recognise."""
    two_dates = SAVINGS.replace(
        "01/09 Example Outbound Transfer", "01/09 01/08 Example Outbound Transfer"
    )
    statement = parse_chase_savings_statement(two_dates)
    assert statement is not None
    assert [t.date for t in statement.transactions] == ["2026-01-05", "2026-01-09", "2026-01-31"]


def test_a_savings_header_with_no_grid_is_not_a_statement():
    assert parse_chase_savings_statement(SAVINGS_HEADER) is None


def test_a_savings_grid_with_no_summary_figures_is_not_a_statement():
    bare = (
        "JPMorgan Chase Bank, N.A.\nJanuary 1, 2026 through January 31, 2026\n"
        "*start*summary\nSAVINGS SUMMARY\n*end*summary\n"
    )
    assert parse_chase_savings_statement(bare + SAVINGS_GRID) is None


def test_savings_detection_is_invariant_to_the_text_layers_spacing_and_case():
    """The BMO-LAYOUTS M3.1 rule: this product's own sentinel arrives both as
    `*start*transaction detail` and `*start*transactiondetail`."""
    respaced = SAVINGS.replace("DATE DESCRIPTION", "DATE  DESCRIPTION").replace(
        "*start*transaction detail", "*start*transactiondetail"
    )
    assert detect_savings(respaced).claims
    assert parse_chase_savings_statement(respaced) is not None
    assert detect_savings(SAVINGS.upper()).claims
