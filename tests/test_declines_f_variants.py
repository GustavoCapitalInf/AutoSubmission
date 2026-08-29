"""DECLINES-F: the At-A-Glance grid prints on both sides of its own heading.

Every fixture here is a synthetic statement in the First Citizens
`Central Bank Operations` family, not a copy of a customer document, and every
one of them satisfies the arithmetic the bank prints:

    beginning + deposits + other credits - checks - other debits
        - monthly service charge = ending

The trait under test is STRUCTURAL and was measured over the family: the
extractor emits the grid's column heading (`Statement Period Days / Average
Ledger Balance`) in a position that varies, so cells the bank printed can
arrive ABOVE it. Four archive documents of one account print their control row,
their day count and/or their beginning balance there; before `_summary_block`
the reader looked only forwards, found an incomplete block and refused a
control record that was complete (W3_TRACKA_LOG §DECLINESF).
"""
from __future__ import annotations

import pytest

from analysis.first_citizens import (
    _SUMMARY_ANCHOR_RE,
    _summary,
    _summary_block,
    parse_first_citizens_statement,
)

ANCHOR = "Statement Period Days Average Ledger Balance"

#: The last furniture the bank prints before the grid. It is not one of the
#: grid's four cell shapes, which is what stops the backward scan.
FURNITURE = "Account Number :   000111222333 Enclosures In Statement:   0"

CONTROL = "+ 1 + 1 500.00+ 1 250.00- 1 750.00- 0.00"
DAYS = "30"
BEGINNING = "1,000.00"
DEPOSITS_TOTAL = "1,000.00"
AVERAGE = "1,800.00+"
ENDING = "1,500.00"


def _grid(above: list[str], below: list[str]) -> list[str]:
    """The head of a statement whose grid cells straddle the column heading."""
    return [
        "Central Bank Operations - DAC02 P.O. Box 27131 Raleigh, NC 27611-7131",
        "Your Account(s) At A Glance",
        "Checking Balance",
        "+",
        "Statement Period: April 1 , 2054     Thru April 30, 2054 "
        "Account Number : 000111222333",
        "Business Banking",
        FURNITURE,
        *above,
        ANCHOR,
        *below,
    ]


BODY = [
    "Deposits To Your Account",
    "Date Amount Date Amount Date Amount",
    "04             1,000.00",
    "-05",
    "Other Credits To Your Account",
    "Date Description Amount Acme Supply Payout",
    "04-10",
    "500.00",
    "Total",
    "500.00",
    "Checks Paid From Your Account",
    "Check No. Date Amount Check No. Date Amount Check No. Date Amount",
    "1001 04-12 250.00",
    "*Prior Check Number(s) Not Included or Out of Sequence.",
    "Other Debits From Your Account",
    "Date Description Amount Beta Freight Co",
    "04-20",
    "750.00",
    "Total",
    "750.00",
    "Daily Balance Summary",
    "Date Balance Date Balance Date Balance",
    "04             1,500.00+",
    "-20",
    "An updated Master Treasury Management Services Agreement (MSA) is available.",
]

#: The three printings measured in the archive. `shipped` is what every
#: document read before this card printed; `control_above` is the shape of the
#: three dormant months; `beginning_above` is the shape of the month that
#: posts a wire in and a wire out.
LAYOUTS = {
    "shipped": ([], [CONTROL, DAYS, BEGINNING, "Beginning Balance",
                     "Deposits Other Credits Checks Other Debits Monthly Service Charge",
                     DEPOSITS_TOTAL, AVERAGE, "+", ENDING, "Ending  Balance"]),
    "control_above": ([CONTROL, BEGINNING, DAYS],
                      ["Beginning Balance", DEPOSITS_TOTAL, AVERAGE,
                       "Deposits Other Credits Checks Other Debits Monthly Service Charge",
                       ENDING, "+", "Ending  Balance"]),
    "beginning_above": ([BEGINNING],
                        [CONTROL, DAYS, "Beginning Balance",
                         "Deposits Other Credits Checks Other Debits Monthly Service Charge",
                         DEPOSITS_TOTAL, AVERAGE, ENDING, "+", "Ending  Balance"]),
}


def statement(layout: str = "shipped", *, extra_above: list[str] | None = None,
              body: list[str] | None = None) -> str:
    above, below = LAYOUTS[layout]
    above = list(above)
    if extra_above:
        above = extra_above + above
    return "\n".join(_grid(above, below) + (BODY if body is None else body)) + "\n"


# --------------------------------------------------------------------------
# A second printing, whose grid puts TWO unsigned cells above the heading.
#
# The shipped fixture cannot exercise the order of the BACKWARD run, because
# every measured straddling printing carries at most one unsigned cell above
# the heading — with one cell there is nothing to order. This printing carries
# two, and its beginning balance and deposits total DIFFER, so reading the
# backward run in the wrong order swaps them.
#
#   beginning 2,000.00 + deposits 1,000.00 + other credits 500.00
#       - cheques 250.00 - other debits 750.00 - charge 0.00 = 2,500.00
# --------------------------------------------------------------------------

TWO_ABOVE_CONTROL = "+ 1 + 1 500.00+ 1 250.00- 1 750.00- 0.00"
TWO_ABOVE_BODY = [
    "Deposits To Your Account",
    "Date Amount Date Amount Date Amount",
    "04             1,000.00",
    "-05",
    "Other Credits To Your Account",
    "Date Description Amount Acme Supply Payout",
    "04-10",
    "500.00",
    "Total",
    "500.00",
    "Checks Paid From Your Account",
    "Check No. Date Amount Check No. Date Amount Check No. Date Amount",
    "1001 04-12 250.00",
    "*Prior Check Number(s) Not Included or Out of Sequence.",
    "Other Debits From Your Account",
    "Date Description Amount Beta Freight Co",
    "04-20",
    "750.00",
    "Total",
    "750.00",
    "Daily Balance Summary",
    "Date Balance Date Balance Date Balance",
    "04             2,500.00+",
    "-20",
    "An updated Master Treasury Management Services Agreement (MSA) is available.",
]


def two_above() -> str:
    """A grid whose beginning balance AND deposits total print above the heading."""
    above = [TWO_ABOVE_CONTROL, DAYS, "2,000.00", "1,000.00"]
    below = ["Beginning Balance",
             "Deposits Other Credits Checks Other Debits Monthly Service Charge",
             AVERAGE, "+", "2,500.00", "Ending  Balance"]
    return "\n".join(_grid(above, below) + TWO_ABOVE_BODY) + "\n"


# --------------------------------------------------------------------------
# The widening: cells above the heading are the grid's own
# --------------------------------------------------------------------------

@pytest.mark.parametrize("layout", ["shipped", "control_above", "beginning_above"])
def test_reads_the_grid_whichever_side_of_its_heading_the_cells_print_on(layout):
    parsed = parse_first_citizens_statement(statement(layout))
    assert parsed is not None
    assert parsed.beginning_balance == 1000.00
    assert parsed.ending_balance == 1500.00
    assert parsed.days_in_period == 30
    assert parsed.bank_reported_average_balance == 1800.00
    assert parsed.stated_total_credits == 1500.00
    assert parsed.stated_total_debits == 1000.00
    assert len(parsed.transactions) == 4


@pytest.mark.parametrize("layout", ["control_above", "beginning_above"])
def test_the_three_unsigned_cells_keep_their_printed_order_across_the_heading(layout):
    """Beginning, deposits total, ending — in DOCUMENT order, not block order.

    The backward scan prepends its cells, so a beginning balance printed above
    the heading has to arrive before the deposits total printed below it. Read
    the other way the deposits total becomes the beginning balance, the section
    gate refuses the document, and this reads None.
    """
    summary = _summary(statement(layout))
    assert summary is not None
    assert (summary.beginning, summary.deposits[1], summary.ending) == (
        1000.00, 1000.00, 1500.00
    )


# --------------------------------------------------------------------------
# The backward scan is bounded by SHAPE, and fails closed
# --------------------------------------------------------------------------

def test_the_backward_scan_stops_at_the_first_line_that_is_not_a_grid_cell():
    """A money cell printed ABOVE the block's furniture is not in the block.

    Without the stop the scan would walk to the top of the page and collect
    the `Checking Balance` figure the bank prints there, which is a fourth
    unsigned cell and would refuse a document that reads perfectly.
    """
    text = statement("control_above").replace(
        FURNITURE, f"9,999.00\n{FURNITURE}"
    )
    parsed = parse_first_citizens_statement(text)
    assert parsed is not None
    assert parsed.beginning_balance == 1000.00


def test_declines_a_grid_whose_backward_scan_reaches_a_fourth_unsigned_cell():
    """Four unsigned cells is a block this reader did not understand.

    `500.00` is chosen so that the three-cell reading a permissive gate would
    fall back on — take the first three and drop the rest — CLOSES on the
    bank's own arithmetic (500 + 1,000 + 500 - 250 - 750 = 1,000) and passes
    every section check. Only the count of unsigned cells separates a document
    that reads from a document that publishes someone else's beginning balance.
    """
    text = statement("control_above", extra_above=["500.00"])
    assert _summary(text) is None
    assert parse_first_citizens_statement(text) is None
    # And the general case: a fourth cell that closes nothing is refused too.
    assert _summary(statement("control_above", extra_above=["9,999.00"])) is None


def test_declines_a_grid_with_a_second_day_count_above_the_heading():
    assert _summary(statement("control_above", extra_above=["12"])) is None


def test_declines_a_grid_with_a_second_signed_cell_above_the_heading():
    assert _summary(statement("control_above", extra_above=["2,222.00+"])) is None


def test_declines_a_grid_printing_a_control_row_on_each_side_of_the_heading():
    """Two control rows is two records; neither is the one to read."""
    assert _summary(statement("shipped", extra_above=[CONTROL])) is None


def test_a_grid_with_two_unsigned_cells_above_the_heading_keeps_their_order():
    """The BACKWARD run has an order of its own, and it is document order.

    Every straddling printing measured in the archive carries at most one
    unsigned cell above the heading, where order cannot be observed — so this
    printing carries two, and its beginning balance and deposits total differ.
    Read the backward run bottom-up and they swap: the deposits total becomes
    the beginning balance, the record still CLOSES on the bank's arithmetic
    (1,000 + 2,000 + 500 - 250 - 750 = 2,500), and only the section check
    refuses it. Without that ordering the reader would publish a beginning
    balance the bank printed as a deposits total.
    """
    parsed = parse_first_citizens_statement(two_above())
    assert parsed is not None
    assert parsed.beginning_balance == 2000.00
    assert parsed.ending_balance == 2500.00
    assert parsed.stated_total_credits == 1500.00


def test_the_backward_run_is_placed_before_the_forward_run():
    """Provenance, not just content: the cells above the heading come first."""
    text = statement("control_above")
    anchor = _SUMMARY_ANCHOR_RE.search(text)
    before, after = _summary_block(text, anchor)
    assert before == [CONTROL, BEGINNING, DAYS]
    assert after[0] == "Beginning Balance"
    assert after[-1] == "Ending  Balance"


# --------------------------------------------------------------------------
# The OPTIONAL cells cannot arrive from the back on their own
# --------------------------------------------------------------------------

def test_declines_a_day_count_that_arrives_from_above_without_its_control_row():
    """`days` is optional, so a FIRST one has no second to contradict it.

    `days_in_period` is not evidence-only — `metrics.py` falls back to it where
    a validated daily ledger is absent — so a stray day count above a heading
    whose grid does not straddle it would publish a period length the bank
    never printed. The shipped printing carries no day count at all.
    """
    above, below = LAYOUTS["shipped"]
    stripped = [line for line in below if line != DAYS]
    text = "\n".join(_grid(["7"], stripped) + BODY) + "\n"
    assert _summary(text) is None
    assert parse_first_citizens_statement(text) is None


def test_declines_a_signed_cell_that_arrives_from_above_without_its_control_row():
    """The same rule for the average ledger balance, which is also optional."""
    above, below = LAYOUTS["shipped"]
    stripped = [line for line in below if line != AVERAGE]
    text = "\n".join(_grid(["9,999.99-"], stripped) + BODY) + "\n"
    assert _summary(text) is None
    assert parse_first_citizens_statement(text) is None


def test_admits_an_optional_cell_from_above_when_the_control_row_is_there_too():
    """The straddling printing is exactly this shape, and it must still read."""
    parsed = parse_first_citizens_statement(statement("control_above"))
    assert parsed is not None
    assert parsed.days_in_period == 30


def test_a_bare_cell_alone_above_the_heading_is_still_admitted():
    """The provenance rule guards the OPTIONAL cells, and only those.

    An unsigned cell is protected by the exactly-three count, so it needs no
    provenance rule — and one archive printing puts its beginning balance, and
    nothing else, above the heading.
    """
    parsed = parse_first_citizens_statement(statement("beginning_above"))
    assert parsed is not None
    assert parsed.beginning_balance == 1000.00


def test_the_forward_scan_stops_at_the_printed_boundary():
    """The forward bound is the printed structure and stays that way.

    Asserted on the block itself rather than on the parse, because the bare
    cells a runaway forward scan collects also trip the three-cell count — so a
    parse-level assertion would pass with this bound removed and would be
    naming a gate it does not test.
    """
    text = statement("shipped")
    anchor = _SUMMARY_ANCHOR_RE.search(text)
    before, after = _summary_block(text, anchor)
    assert before == []
    assert after[-1] == "Ending  Balance"
    assert "Deposits To Your Account" not in after
    assert not any(line.startswith("Date ") for line in after)


def test_declines_a_grid_whose_ending_prints_beyond_the_boundary():
    """Two unsigned cells is not a control record, wherever the third went."""
    above, below = LAYOUTS["shipped"]
    cut = below.index(ENDING)
    text = "\n".join(
        _grid(list(above), below[:cut] + ["Deposits To Your Account"] + below[cut:])
        + BODY
    ) + "\n"
    assert _summary(text) is None


# --------------------------------------------------------------------------
# The gates the widening must not have disabled
# --------------------------------------------------------------------------

def test_declines_a_control_record_that_does_not_close_on_its_own_arithmetic():
    text = statement("control_above").replace(f"\n{ENDING}\n", "\n1,600.00\n")
    assert _summary(text) is None
    assert parse_first_citizens_statement(text) is None


def test_declines_a_section_the_printed_total_contradicts():
    body = list(BODY)
    body[body.index("500.00", body.index("Other Credits To Your Account"))] = "600.00"
    assert parse_first_citizens_statement(
        statement("control_above", body=body)
    ) is None


def test_declines_a_section_the_printed_count_contradicts():
    body = list(BODY)
    index = body.index("Other Credits To Your Account")
    body[index + 2:index + 4] = ["04-10", "250.00", "04-11", "250.00"]
    assert parse_first_citizens_statement(
        statement("control_above", body=body)
    ) is None


# --------------------------------------------------------------------------
# The dormant month, which is the shape that started this card
# --------------------------------------------------------------------------

DORMANT_ABOVE = ["+ 0 0 0.00 0 0.00 0 0.00 0.00", "200.00", "28"]
DORMANT_BELOW = ["Beginning Balance", "0.00", "200.00+",
                 "Deposits Other Credits Checks Other Debits Monthly Service Charge",
                 "200.00", "+", "Ending  Balance"]


def dormant() -> str:
    return "\n".join(_grid(DORMANT_ABOVE, DORMANT_BELOW) + [
        "Direct Customer Inquiry Calls To Personal 1-888-000-0000",
        "Page 1 of 3",
    ]) + "\n"


def test_a_month_with_no_activity_publishes_the_balances_the_bank_printed():
    parsed = parse_first_citizens_statement(dormant())
    assert parsed is not None
    assert parsed.beginning_balance == 200.00
    assert parsed.ending_balance == 200.00
    assert parsed.transactions == []
    assert parsed.stated_credit_count == 0
    assert parsed.stated_debit_count == 0
    assert parsed.stated_total_credits == 0.00
    assert parsed.stated_total_debits == 0.00
    assert parsed.bank_reported_average_balance == 200.00
    assert parsed.bank_reported_average_label == "Average Ledger Balance"


def test_a_month_with_no_activity_still_needs_its_control_row():
    """Drop the control row and the block is three cells with no record.

    On THIS printing two rules agree: the provenance rule refuses it (the day
    count above the heading has lost the control row it needed for company) and
    the shape test would refuse it anyway. The test below is the one that
    isolates the shape test, and it exists because the mutation table caught
    this one no longer doing the job its name claims.
    """
    text = dormant().replace("+ 0 0 0.00 0 0.00 0 0.00 0.00\n", "")
    assert _summary(text) is None
    assert parse_first_citizens_statement(text) is None


def test_declines_a_block_that_prints_no_control_row_at_all():
    """No control row anywhere, and nothing above the heading to refuse first.

    Three unsigned cells, one day count and one signed cell all print BELOW the
    heading, so the provenance rule never fires and the backward run is empty.
    The only thing standing between this block and a published record is the
    control-row requirement itself — and there is no record without one: the
    counts and per-section totals the parse is gated on live on that row.
    """
    above, below = LAYOUTS["shipped"]
    stripped = [line for line in below if line != CONTROL]
    text = "\n".join(_grid(list(above), stripped) + BODY) + "\n"
    anchor = _SUMMARY_ANCHOR_RE.search(text)
    assert _summary_block(text, anchor)[0] == []
    assert _summary(text) is None
    assert parse_first_citizens_statement(text) is None


# --------------------------------------------------------------------------
# The printed product line
# --------------------------------------------------------------------------

def test_publishes_the_product_line_the_bank_printed():
    """The account number is printed twice and the product stands between them.

    The first of those two lines begins `Statement Period:`, not
    `Account Number`, which is why the anchored pattern matched nothing in this
    family and every document published a memorized literal instead.
    """
    parsed = parse_first_citizens_statement(statement("shipped"))
    assert parsed is not None
    assert parsed.account_name == "Business Banking"

    other = statement("shipped").replace(
        "\nBusiness Banking\n", "\nProfessional Business Checking\n"
    )
    parsed = parse_first_citizens_statement(other)
    assert parsed is not None
    assert parsed.account_name == "Professional Business Checking"


def test_publishes_no_product_name_when_no_product_line_is_printed():
    """An unread product is not a product this reader may name."""
    text = statement("shipped").replace("\nBusiness Banking\n", "\n")
    parsed = parse_first_citizens_statement(text)
    assert parsed is not None
    assert parsed.account_name is None
    assert parsed.beginning_balance == 1000.00
