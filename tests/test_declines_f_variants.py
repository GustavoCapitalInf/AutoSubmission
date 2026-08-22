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
        "Statement Period: April 1 , 2026     Thru April 30, 2026 "
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


def test_the_forward_scan_stops_at_the_printed_boundary():
    """The forward bound is the printed structure and stays that way.

    Asserted on the block itself rather than on the parse, because the bare
    cells a runaway forward scan collects also trip the three-cell count — so a
    parse-level assertion would pass with this bound removed and would be
    naming a gate it does not test.
    """
    text = statement("shipped")
    anchor = _SUMMARY_ANCHOR_RE.search(text)
    block = _summary_block(text, anchor)
    assert block[-1] == "Ending  Balance"
    assert "Deposits To Your Account" not in block
    assert not any(line.startswith("Date ") for line in block)


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
    """Drop the control row and the block is three cells with no record."""
    text = dormant().replace("+ 0 0 0.00 0 0.00 0 0.00 0.00\n", "")
    assert _summary(text) is None
    assert parse_first_citizens_statement(text) is None
