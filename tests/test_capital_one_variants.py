"""MONEYFIX-1 card C — the Capital One amount cell is guarded and signed.

`analysis/capital_one.py` read every amount with

    parse_digit_scrubbed(value, parens=True, trailing_minus=True)

— no `guard=`, and no `leading_minus=True`. `parse_digit_scrubbed` keeps only
digits and dots, so without a guard it does not READ a cell, it RENDERS any
text as a number: `Page 3 of 8` became 38.0 and `REF#000000012345` became
12345.0. `analysis/money.py` documents the guard as existing for precisely
this ("silently mis-reading a reference number as an amount is the failure
mode this guard exists to prevent"), and `analysis/chase.py` already passes
one. Separately, a printed `-$1,234.56` lost its sign and published +1234.56.
(F-MONEYFMT finding 5.)

Both readers in the module are exposed: the two-cell Account-summary reader
takes the second cell of ANY two-cell row before it looks at the label, and
the detail reader takes columns 2, 3 and 4 of any row whose first cell is a
date. Every fixture below is synthetic.
"""
from __future__ import annotations

import pytest

from analysis.capital_one import _money
from analysis.money import parse_digit_scrubbed


def pre_fix_money(value: str) -> float | None:
    """The call this module made BEFORE the fix, quoted verbatim, so each
    fixture proves the defect in process rather than describing it."""
    return parse_digit_scrubbed(value, parens=True, trailing_minus=True)


# ---------------------------------------------------------------------------
# C1 — text that is not money is refused instead of rendered
# ---------------------------------------------------------------------------

HOSTILE = [
    ("Page 3 of 8", 38.0),
    ("REF#000000012345", 12345.0),
    ("1,234.56 (see page 3)", 1234.563),
    ("Number of Days in Cycle 31", 31.0),
    ("Check #1099 returned", 1099.0),
    ("see reverse", None),
]


@pytest.mark.parametrize("cell,pre_fix_value", HOSTILE,
                         ids=[c for c, _ in HOSTILE])
def test_c1_a_cell_that_is_not_an_amount_is_refused(cell, pre_fix_value):
    assert pre_fix_money(cell) == pre_fix_value, "pre-fix reading changed"
    assert _money(cell) is None


def test_c1_the_scrub_used_to_invent_a_number_from_page_furniture():
    """Named separately because it is the whole finding in one line."""
    assert pre_fix_money("Page 3 of 8") == 38.0
    assert _money("Page 3 of 8") is None


# ---------------------------------------------------------------------------
# C2 — a printed minus is a minus
# ---------------------------------------------------------------------------

def test_c2_a_leading_minus_is_honoured_not_dropped():
    assert pre_fix_money("-$1,234.56") == 1234.56   # sign silently dropped
    assert _money("-$1,234.56") == -1234.56


def test_c2_the_other_two_negative_markers_still_read_as_before():
    """`parens` and `trailing_minus` were already passed; adding the third
    marker must not disturb them."""
    assert _money("($1,234.56)") == -1234.56
    assert _money("1,234.56-") == -1234.56


# ---------------------------------------------------------------------------
# C3 — every shape Capital One actually prints still reads
#
# Measured over every cell this parser passes to `_money` across its whole
# claimed population plus its class-1 declines in run 6893a75b — 28 documents,
# 5,238 distinct cells — the guard refuses none. Those cells are exactly three
# shapes, all pinned here.
# ---------------------------------------------------------------------------

PRINTED = [
    ("1,234.56", 1234.56),
    ("$1,234.56", 1234.56),
    ("($1,234.56)", -1234.56),
    ("$0.00", 0.0),
    ("0.00", 0.0),
    ("$1,234,567.89", 1234567.89),
    ("31", 31.0),
]


@pytest.mark.parametrize("cell,expected", PRINTED, ids=[c for c, _ in PRINTED])
def test_c3_every_printed_shape_reads_exactly_as_it_did(cell, expected):
    assert _money(cell) == expected
    assert _money(cell) == pre_fix_money(cell), "a printed shape moved"


def test_c3_an_empty_cell_is_still_none():
    assert _money("") is None
    assert _money("   ") is None
