"""W3 §DECLINESE — the printing classes behind sixteen declines.

Four refusal sites, measured by replay over the run of record:
`huntington.py:681` (8 documents), `huntington.py:662` (4), `chase.py:716` (3)
and `chase.py:595` (1). One of the four was a reader that had memorized a shape
its bank prints wider; the other three are honest refusals, and the fixtures
that pin them as refusals are as much a part of this cell as the widening.

Each fixture below is a PRINTING CLASS, assembled from parts so that a test can
change exactly one printed thing and assert what the reader does about it.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import date

import pytest

from analysis import chase, huntington
from analysis.chase import parse_chase_statement
from analysis.chase_savings import detect as chase_savings_detect
from analysis.huntington import parse_huntington_statement
from analysis.schema import Statement

# ===========================================================================
# E3 — chase: the one-grid printing of the checking product
# ===========================================================================

CHASE_HEADER = (
    "January 1, 2054 through January 31, 2054\n"
    "JPMorgan Chase Bank, N.A. P O Box 44959 Indianapolis, IN 46244 - 4959\n"
    "Account Number: 000000670732314\n"
)

#: The personal checking summary: an AMOUNT column and no INSTANCES column, so
#: not one row carries a count. (E4.)
CHASE_SUMMARY = (
    "*start*summary\n"
    "Chase Premier Plus Checking\n"
    "CHECKING SUMMARY\n"
    "AMOUNT\n"
    "Beginning Balance $1,000.00\n"
    "Deposits and Additions 1,500.00\n"
    "ATM & Debit Card Withdrawals -200.00\n"
    "Electronic Withdrawals -1,050.00\n"
    "Fees -25.00\n"
    "Ending Balance $1,225.00\n"
    "*end*summary\n"
)

#: The grid. Its first row's Amount cell is WRAPPED onto the line above it,
#: which is how this producer prints a credit whose Description column is full;
#: the debit rows print both cells inline, one of them with the padding between
#: the sign and the figure. The Beginning/Ending Balance lines are the grid's
#: own bounds and are not rows.
CHASE_GRID = (
    "*start*transaction detail\n"
    "TRANSACTION DETAIL\n"
    "DATE DESCRIPTION AMOUNT BALANCE\n"
    "Beginning Balance $1,000.00\n"
    "1,500.00\n"
    "01/05 Remote Online Deposit 1 2,500.00\n"
    "01/12 Card Purchase           01/10 Example Store Columbus OH Card 0117 -200.00 2,300.00\n"
    "01/20 Example Vendor  Web ID: 1234567890 -1,050.00 1,250.00\n"
    "01/31 Monthly Service Fee - 25.00 1,225.00\n"
    "Ending Balance $1,225.00\n"
    "*end*transaction detail\n"
)


def chase_document(**parts: str) -> str:
    blocks = dict(header=CHASE_HEADER, summary=CHASE_SUMMARY, grid=CHASE_GRID)
    blocks.update(parts)
    return "".join(blocks[name] for name in ("header", "summary", "grid"))


def test_the_one_grid_printing_is_read_whole():
    """Three archive documents refused at `chase.py:716` print this. The rows
    were on the page; the reader knew only the six direction-named sections."""
    stmt = parse_chase_statement(chase_document())
    assert stmt is not None
    assert stmt.bank == "Chase"
    assert [t.amount for t in stmt.transactions] == [1500.0, -200.0, -1050.0, -25.0]
    assert [t.date for t in stmt.transactions] == [
        "2054-01-05", "2054-01-12", "2054-01-20", "2054-01-31",
    ]
    assert [t.running_balance for t in stmt.transactions] == [
        2500.0, 2300.0, 1250.0, 1225.0,
    ]
    assert stmt.beginning_balance == 1000.0
    assert stmt.ending_balance == 1225.0


def test_the_wrapped_amount_cell_belongs_to_the_row_below_it():
    """The credit's amount is printed on its own line ABOVE its row. Read as
    that row's own trailing cell it would become a second balance and the row
    would lose its amount entirely."""
    stmt = parse_chase_statement(chase_document())
    assert stmt is not None
    first = stmt.transactions[0]
    assert first.amount == 1500.0
    assert first.running_balance == 2500.0
    assert first.description == "Remote Online Deposit 1"


def test_the_direction_is_the_printed_sign_not_the_wording():
    stmt = parse_chase_statement(chase_document())
    assert stmt is not None
    assert [t.direction for t in stmt.transactions] == [
        "credit", "debit", "debit", "debit",
    ]


def test_the_posting_date_is_the_first_of_the_two_dates_a_card_row_prints():
    """A card row prints the transaction date second. Dating the row by it
    attributes an end-of-day balance to a day the bank does not recognise."""
    stmt = parse_chase_statement(chase_document())
    assert stmt is not None
    card = stmt.transactions[1]
    assert card.date == "2054-01-12"
    assert card.description.startswith("Card Purchase")


def test_a_grid_whose_running_balance_does_not_follow_is_refused():
    """The per-row oracle. One printed balance moves and nothing else, so the
    sums still agree and only the bank's own running total disagrees."""
    grid = CHASE_GRID.replace("-200.00 2,300.00", "-200.00 2,301.00")
    assert parse_chase_statement(chase_document(grid=grid)) is None


def test_a_grid_that_does_not_close_on_the_stated_ending_balance_is_refused():
    """Isolated on purpose: every row follows from the one above it, the
    ledger's credit and debit sums are exactly the summary's stated totals, and
    the only thing wrong is that the summary's own Ending Balance is not where
    the chain lands. Nothing but the closing check can see this."""
    summary = CHASE_SUMMARY.replace(
        "Ending Balance $1,225.00", "Ending Balance $1,235.00"
    )
    assert parse_chase_statement(chase_document(summary=summary)) is None


def test_the_cent_is_the_tolerance():
    """Every check here is against a figure Chase printed on the same page, so
    there is nothing for a tolerance to absorb. One cent of drift in the bank's
    own running balance refuses the document."""
    grid = CHASE_GRID.replace("-200.00 2,300.00", "-200.00 2,300.01")
    assert parse_chase_statement(chase_document(grid=grid)) is None


def test_a_grid_whose_credits_contradict_the_stated_total_is_refused():
    """The chain is untouched; only the summary's own credit total moves. This
    is the check that says the `stated_total_credits` this parser publishes was
    read off the right row."""
    summary = CHASE_SUMMARY.replace(
        "Deposits and Additions 1,500.00", "Deposits and Additions 1,600.00"
    )
    assert parse_chase_statement(chase_document(summary=summary)) is None


def test_a_grid_whose_debits_contradict_the_stated_total_is_refused():
    summary = CHASE_SUMMARY.replace(
        "Electronic Withdrawals -1,050.00", "Electronic Withdrawals -1,060.00"
    )
    assert parse_chase_statement(chase_document(summary=summary)) is None


def test_a_grid_row_this_reader_cannot_resolve_refuses_the_document():
    """A dated line the grid prints that carries no money cell at all. Dropping
    it would leave the running balance intact — nothing was added — so the
    chain cannot see it, and a row silently dropped here is a row missing from
    the sums the ledger is then gated against."""
    grid = CHASE_GRID.replace(
        "01/20 Example Vendor",
        "01/18 Example Reversal Pending\n01/20 Example Vendor",
    )
    assert parse_chase_statement(chase_document(grid=grid)) is None


#: The one shape check 2 cannot see, kept as a fixture so it is visible rather
#: than discovered. Row two has LOST its Date column, so `tables.group_rows`
#: absorbs it into row one; row one's Amount is exactly 0.00, so the merged
#: group's arithmetic is indistinguishable from row two's alone.
ABSORBED_ROW_SUMMARY = (
    "*start*summary\n"
    "Chase Premier Plus Checking\n"
    "CHECKING SUMMARY\n"
    "AMOUNT\n"
    "Beginning Balance $1,000.00\n"
    "Deposits and Additions 0.00\n"
    "Electronic Withdrawals -100.00\n"
    "Ending Balance $900.00\n"
    "*end*summary\n"
)
ABSORBED_ROW_GRID = (
    "*start*transaction detail\n"
    "TRANSACTION DETAIL\n"
    "DATE DESCRIPTION AMOUNT BALANCE\n"
    "Beginning Balance $1,000.00\n"
    "01/10 Example Zero Adjustment 0.00 1,000.00\n"
    "Example Vendor Payment -100.00 900.00\n"
    "Ending Balance $900.00\n"
    "*end*transaction detail\n"
)


def test_a_row_that_lost_its_date_column_is_absorbed_and_the_chain_cannot_see_it():
    """The named exception to check 2, PINNED rather than claimed absent.

    `tables.group_rows` starts a row at the printed Date column, so a row that
    lost its date is not a row: it joins its predecessor. The merged group is
    read as one transaction taking the last two money cells — the absorbed
    row's own — and when the predecessor's Amount is 0.00 the running balance
    is unchanged by the merge. Every gate therefore passes on a ledger that is
    one row short with the two descriptions run together.

    This asserts today's behaviour, which is WRONG about the document and right
    about the arithmetic. It is the `group_rows` contract, shared with
    `chase_savings`, and closing it needs a row-count oracle this grid does not
    print. Pinned so a future fix shows up as this test failing rather than as
    a silent change. Measured NOT to occur on the archive: the three movers'
    published token multisets are exact against the printed grids, and the
    whole-archive sweep is clean.
    """
    stmt = parse_chase_statement(
        CHASE_HEADER + ABSORBED_ROW_SUMMARY + ABSORBED_ROW_GRID
    )
    assert stmt is not None
    assert len(stmt.transactions) == 1, "the grid prints two rows"
    only = stmt.transactions[0]
    assert only.amount == -100.0
    assert only.running_balance == 900.0
    assert "Example Zero Adjustment" in only.description
    assert "Example Vendor Payment" in only.description


ABSORBED_ROW_SUMMARY_NONZERO = ABSORBED_ROW_SUMMARY.replace(
    "Electronic Withdrawals -100.00", "Electronic Withdrawals -150.00"
).replace("Ending Balance $900.00", "Ending Balance $850.00")
ABSORBED_ROW_GRID_NONZERO = (
    ABSORBED_ROW_GRID
    .replace("01/10 Example Zero Adjustment 0.00 1,000.00",
             "01/10 Example Adjustment -50.00 950.00")
    .replace("Example Vendor Payment -100.00 900.00",
             "Example Vendor Payment -100.00 850.00")
    .replace("Ending Balance $900.00", "Ending Balance $850.00")
)


def test_the_absorbed_row_is_only_invisible_when_it_costs_the_chain_nothing():
    """What BOUNDS the exception, on a document a bank could actually print.

    The absorbed row's predecessor is dropped whatever its Amount says — the
    merged group is read from its LAST two money cells. What decides whether
    that is visible is the printed BALANCE column: in a real statement the
    absorbed row's balance already includes its predecessor's amount, so
    skipping a non-zero predecessor lands the chain somewhere the bank did not
    print and check 2 refuses at that row. Only a predecessor whose amount is
    0.00 leaves the printed balances unchanged, which is why the exception
    above exists at all and why it is narrow.

    Note what this test had to fix about itself: moving the predecessor's
    Amount alone leaves the successor's printed Balance contradicting its own
    page, and a document that contradicts itself is refused for the wrong
    reason. The whole downstream printing moves with it here.
    """
    assert parse_chase_statement(
        CHASE_HEADER + ABSORBED_ROW_SUMMARY_NONZERO + ABSORBED_ROW_GRID_NONZERO
    ) is None


def test_the_bounding_fixture_is_a_consistent_printing():
    """A refusal is only evidence about the gate it is meant to exercise if the
    document is otherwise sound. The same grid with its Date column intact —
    the only difference — publishes both rows and reconciles."""
    intact = ABSORBED_ROW_GRID_NONZERO.replace(
        "Example Vendor Payment -100.00 850.00",
        "01/20 Example Vendor Payment -100.00 850.00",
    )
    stmt = parse_chase_statement(
        CHASE_HEADER + ABSORBED_ROW_SUMMARY_NONZERO + intact
    )
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [-50.0, -100.0]
    assert [t.running_balance for t in stmt.transactions] == [950.0, 850.0]


def test_the_grid_is_not_read_when_the_named_sections_already_read():
    """The grid and the six sections are alternative printings of the same
    activity. Reading both would double every row, so the grid is reached only
    where the sections produced nothing."""
    sections = (
        "*start*deposits and additions\n"
        "DEPOSITS AND ADDITIONS\n"
        "DATE DESCRIPTION AMOUNT\n"
        "01/05 Remote Online Deposit 1,500.00\n"
        "*end*deposits and additions\n"
    )
    stmt = parse_chase_statement(chase_document(grid=sections + CHASE_GRID))
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [1500.0]


def test_a_summary_whose_balances_are_unreadable_never_reaches_the_grid():
    """The HTML summary branch does not fail closed on its own — it sets what
    it could read and returns. A grid walked from a balance that was never read
    would be walked from nothing."""
    html_summary = (
        "*start*summary\n"
        "CHECKING SUMMARY\n"
        "<table>\n"
        "<tr><td>Beginning Balance</td><td></td><td>one thousand</td></tr>\n"
        "<tr><td>Ending Balance</td><td></td><td>one thousand</td></tr>\n"
        "</table>\n"
        "*end*summary\n"
    )
    assert parse_chase_statement(chase_document(summary=html_summary)) is None


def test_the_zero_activity_guard_still_refuses_a_grid_this_reader_cannot_read():
    """§CHASE-CLOSURE card A′ is untouched: emptiness is still never its own
    proof that the period was empty."""
    unread = (
        "*start*daily ending balance\n"
        "DAILY ENDING BALANCE\n"
        "DATE AMOUNT\n"
        "01/05 1,500.00\n"
        "*end*daily ending balance\n"
    )
    quiet = (
        "*start*summary\n"
        "Chase Business Complete Checking\n"
        "CHECKING SUMMARY\n"
        "INSTANCES AMOUNT\n"
        "Beginning Balance $0.00\n"
        "Ending Balance $0.00\n"
        "*end*summary\n"
    )
    assert parse_chase_statement(CHASE_HEADER + quiet) is not None
    assert parse_chase_statement(CHASE_HEADER + quiet + unread) is None


def test_the_grid_reader_is_the_one_chase_savings_already_ships():
    """Not a description: the identity of the function objects. A copy of the
    grid reader in `chase.py` would drift from the one that reads the savings
    product, and this is what says there is only one."""
    from analysis import chase_savings

    assert chase._grid_lines is chase_savings._grid_lines
    assert chase._grid_rows is chase_savings._grid_rows
    assert chase._transaction is chase_savings._transaction


def test_the_savings_registration_cannot_claim_this_checking_document():
    """Which is why `chase.py` has to call the reader rather than be routed to
    it: `chase_savings` carries an EXCLUDING marker on CHECKING SUMMARY."""
    detection = chase_savings_detect(chase_document())
    assert not detection.claims


# ===========================================================================
# E4 — chase: the CHECKING SUMMARY that prints no INSTANCES column
# ===========================================================================

def test_a_summary_row_that_prints_no_instance_count_is_still_read():
    stmt = parse_chase_statement(chase_document())
    assert stmt is not None
    assert stmt.stated_total_credits == 1500.0
    assert stmt.stated_total_debits == 1275.0
    assert stmt.stated_service_charge == 25.0


def test_a_count_the_statement_does_not_print_is_not_invented():
    """Deriving it from the ledger would manufacture the oracle
    `analysis/count_semantics.py` checks the ledger against."""
    stmt = parse_chase_statement(chase_document())
    assert stmt is not None
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_the_counted_printing_is_read_exactly_as_it_was():
    """The business layout heads its grid INSTANCES AMOUNT. The counted
    spelling is tried first, so nothing about it moves."""
    stmt = Statement(bank="Chase", period_start="2054-01-01", period_end="2054-01-31")
    counted = (
        "*start*summary\n"
        "CHECKING SUMMARY\n"
        "INSTANCES AMOUNT\n"
        "Beginning Balance $1,000.00\n"
        "Deposits and Additions 3 1,500.00\n"
        "Electronic Withdrawals 2 -1,275.00\n"
        "Ending Balance $1,225.00\n"
        "*end*summary\n"
    )
    assert chase._parse_native_summary(counted, stmt) is True
    assert stmt.stated_credit_count == 3
    assert stmt.stated_debit_count == 2
    assert stmt.stated_total_credits == 1500.0
    assert stmt.stated_total_debits == 1275.0


def test_the_two_summary_spellings_cannot_read_the_same_row():
    """Why trying the counted spelling first is belt-and-braces rather than the
    thing that keeps a counted row safe: the two are DISJOINT under this
    grammar. An amount must carry cents, and a count cannot, so the count-less
    pattern finds nothing at all on a counted row — measured here rather than
    argued, because the day the money grammar admits a cents-less figure the
    ordering stops being decorative and starts being load-bearing."""
    counted_row = "Deposits and Additions 3 1,500.00 Ending Balance $1,225.00"
    bare = re.search(
        rf"Deposits and Additions\s+({chase._SUMMARY_AMOUNT})",
        counted_row, re.IGNORECASE,
    )
    assert bare is None
    assert chase._summary_row(counted_row, "Deposits and Additions") == (3, 1500.0)


def test_a_mixed_printing_publishes_no_debit_count_at_all():
    """A count summed over the counted rows of a mixed printing is a real
    number describing PART of a total — a false contradiction against a
    complete ledger."""
    stmt = Statement(bank="Chase", period_start="2054-01-01", period_end="2054-01-31")
    mixed = (
        "*start*summary\n"
        "CHECKING SUMMARY\n"
        "Beginning Balance $1,000.00\n"
        "Deposits and Additions 3 1,500.00\n"
        "Electronic Withdrawals 2 -1,250.00\n"
        "Fees -25.00\n"
        "Ending Balance $1,225.00\n"
        "*end*summary\n"
    )
    assert chase._parse_native_summary(mixed, stmt) is True
    assert stmt.stated_total_debits == 1275.0
    assert stmt.stated_debit_count is None


def test_the_combined_debit_row_is_not_read_twice_by_its_shorter_labels():
    """`Other Withdrawals` and `Fees` are both prefixes of the Commercial
    Checking layout's combined row. The counted spelling was safe because a
    count had to follow immediately; the count-less spelling is safe because a
    COMMA does."""
    stmt = Statement(bank="Chase", period_start="2054-01-01", period_end="2054-01-31")
    combined = (
        "*start*summary\n"
        "CHECKING SUMMARY\n"
        "Beginning Balance $1,000.00\n"
        "Deposits and Additions 1,500.00\n"
        "Other Withdrawals, Fees & Charges -275.00\n"
        "Ending Balance $2,225.00\n"
        "*end*summary\n"
    )
    assert chase._parse_native_summary(combined, stmt) is True
    assert stmt.stated_total_debits == 275.0


def test_an_amount_the_money_grammar_refuses_leaves_the_row_unread():
    """A figure printed without cents is not this layout's money. It is left
    unstated rather than rounded into one."""
    stmt = Statement(bank="Chase", period_start="2054-01-01", period_end="2054-01-31")
    centless = (
        "*start*summary\n"
        "CHECKING SUMMARY\n"
        "Beginning Balance $1,000.00\n"
        "Deposits and Additions $500\n"
        "Ending Balance $1,500.00\n"
        "*end*summary\n"
    )
    assert chase._parse_native_summary(centless, stmt) is True
    assert stmt.stated_total_credits is None


# ===========================================================================
# E2 — huntington:681, the printing class that states a fee it never dates
# ===========================================================================

#: Eight archive documents are printed like this: the summary states a
#: `Total Service Charges (-)` OUTSIDE `Debits (-)`, and the statement then
#: prints no `Service Charge Detail`, no `Service Charge Summary` and no
#: `Balance Activity` grid at all. Both of `_validate`'s remaining checks fail
#: on it, and NOTHING in the document supplies what they want: the fee has no
#: date and there is no printed date oracle of any kind.
HUNT_HEADER = (
    "THE HUNTINGTON NATIONAL BANK PO BOX 1558 EA1W37 COLUMBUS OH 43216-1558\n"
    "ACME WIDGETS LLC 1 MAIN ST COLUMBUS OH 43219-6229\n"
    "Huntington Unlimited Checking Account: -------5638\n"
)
HUNT_FOOTER = (
    "The Huntington National Bank is Member FDIC. , Huntington and 24-Hour Grace "
    "are federally registered service marks of Huntington Bancshares Incorporated.\n"
    "Statement Period from 01/01/54 to 01/31/54 Page 1 of 1\n"
)
HUNT_SUMMARY = (
    "Beginning Balance $1,000.00 Credits (+) 1,050.00 Regular Deposits 750.00 "
    "Electronic Deposits 300.00 Debits (-) 300.00 Electronic Withdrawals 300.00 "
    "Total Service Charges (-) 20.00 Ending Balance $1,730.00\n"
)
HUNT_PERIOD = (
    "Statement Activity From: 01/01/54 to 01/31/54\n"
    "Days in Statement Period 31\n"
    "Average Ledger Balance* 1,500.00 Average Collected Balance* 1,500.00\n"
    "* The above balances correspond to the service charge cycle for this account.\n"
)
HUNT_SECTIONS = (
    "Deposits (+) Account:-------5638\n"
    "Date Amount Serial # Type Date Amount Serial # Type\n"
    "01/05 500.00 387142655 Remote 01/12 250.00 Brch/ATM\n"
    "Other Credits (+) Account:-------5638\n"
    "Date Amount Description\n"
    "01/08 300.00 ACME PAYMENTS DEPOSIT 260108 653201322886\n"
    "Other Debits (-) Account:-------5638\n"
    "Date Amount Description\n"
    "01/15 300.00 PURCHASE SUPPLY CO COLUMBUS OH XXXXXXXXXXXX2836\n"
)
UNDATED_FEE_STATEMENT = HUNT_HEADER + HUNT_SUMMARY + HUNT_PERIOD + HUNT_SECTIONS + HUNT_FOOTER


@contextmanager
def _with_the_printed_ending_as_the_only_date_oracle():
    """The most generous reading of this class that is still arithmetic.

    The class prints no `Balance Activity` grid, so `_validate`'s fourth check
    refuses it for having no end-of-day balance at all. This substitutes the
    ONE dated balance the summary itself implies — the printed Ending Balance,
    at the printed period end — and changes nothing else. Nothing is
    fabricated: both figures are the statement's own.
    """
    shipped = huntington._validate

    def relaxed(summary, section_txns, fee_txns, service_net, balances):
        return shipped(
            summary, section_txns, fee_txns, service_net,
            balances or [(date(2054, 1, 31), summary["Ending Balance"])],
        )

    huntington._validate = relaxed
    try:
        yield
    finally:
        huntington._validate = shipped


def test_the_statement_that_states_a_fee_it_never_dates_is_refused():
    assert parse_huntington_statement(UNDATED_FEE_STATEMENT) is None


def test_this_printing_class_prints_no_date_oracle_at_all():
    """Not an assumption about the fixture: the three blocks whose absence is
    the whole finding are absent, and the sections that ARE printed add up to
    the summary's own totals exactly."""
    for block in ("Service Charge Detail", "Service Charge Summary",
                  "Balance Activity", "Daily Balance"):
        assert block not in UNDATED_FEE_STATEMENT
    lines = huntington._lines(UNDATED_FEE_STATEMENT)
    summary = huntington._summary(lines)
    period = huntington._period(UNDATED_FEE_STATEMENT)
    blocks = huntington._blocks(lines)
    txns = huntington._transactions(blocks, *period)
    assert round(sum(t.amount for t in txns if t.amount > 0), 2) == summary["Credits (+)"]
    assert round(-sum(t.amount for t in txns if t.amount < 0), 2) == summary["Debits (-)"]
    assert huntington._daily_balances(blocks, *period) == []


def test_no_date_oracle_the_summary_implies_would_close_this_class():
    """The measurement this class turns on, made permanent. Give the reader
    the one dated balance the summary itself implies and the document is STILL
    refused, because the published ledger misses the printed ending balance by
    exactly the service charge the statement states and never dates. There is
    no widened read of this class that closes."""
    with _with_the_printed_ending_as_the_only_date_oracle():
        assert parse_huntington_statement(UNDATED_FEE_STATEMENT) is None

    lines = huntington._lines(UNDATED_FEE_STATEMENT)
    summary = huntington._summary(lines)
    txns = huntington._transactions(
        huntington._blocks(lines), *huntington._period(UNDATED_FEE_STATEMENT)
    )
    residue = round(
        summary["Beginning Balance"] + sum(t.amount for t in txns)
        - summary["Ending Balance"], 2
    )
    assert residue == summary["Total Service Charges (-)"]


def test_the_relaxation_harness_reaches_the_gate_it_claims_to():
    """A relaxation that refused for some other reason would make the test
    above pass while testing nothing. With the same relaxation, a statement of
    this class whose fee IS zero publishes."""
    no_fee = HUNT_SUMMARY.replace(
        "Total Service Charges (-) 20.00 Ending Balance $1,730.00",
        "Total Service Charges (-) 0.00 Ending Balance $1,750.00",
    )
    document = HUNT_HEADER + no_fee + HUNT_PERIOD + HUNT_SECTIONS + HUNT_FOOTER
    assert parse_huntington_statement(document) is None
    with _with_the_printed_ending_as_the_only_date_oracle():
        assert parse_huntington_statement(document) is not None


# ===========================================================================
# E5 — chase:595, the text layer that carries only its own section markers
# ===========================================================================

#: One archive document is printed like this: eight pages of a real statement
#: whose text layer holds every `*start*…*end*` sentinel and NO content — no
#: summary, no rows, no money. `classification` called it digital because a
#: text layer exists, so the OCR ladder never escalated it.
EMPTY_TEXT_LAYER = (
    "May 01, 2054 through May 29, 2054\n"
    "JPMorgan Chase Bank, N.A. P O Box 44959 Indianapolis, IN 46244 - 4959\n"
    "Account Number:\n"
    "*start*summary\n"
    "*end*summary\n"
    "*start*deposits and additions\n"
    "*end*deposits and additions\n"
    "*start*checks paid section3\n"
    "*end*checks paid section3\n"
    "*start*daily ending balance2\n"
    "*end*daily ending balance2\n"
)


def test_a_text_layer_with_no_content_is_refused_at_the_summary():
    """`chase.py:595`. The refusal is honest and this cell does not widen it:
    a reader relaxed until an empty text layer parses is a reader that
    publishes a statement nobody printed. Carded for the intake ladder."""
    assert parse_chase_statement(EMPTY_TEXT_LAYER) is None


def test_the_empty_text_layer_is_still_claimed_as_this_issuers_layout():
    """It is declined at parse, not excluded at detection: the sentinels are
    Chase's own, and reporting it as a bank nobody has seen would put it in the
    wrong queue."""
    assert chase.detect(EMPTY_TEXT_LAYER).claims


@pytest.mark.parametrize("block", ["summary", "deposits and additions"])
def test_the_empty_text_layer_prints_no_money_anywhere(block):
    assert f"*start*{block}\n*end*{block}" in EMPTY_TEXT_LAYER
    assert re.search(r"\d[\d,]*\.\d{2}", EMPTY_TEXT_LAYER) is None
