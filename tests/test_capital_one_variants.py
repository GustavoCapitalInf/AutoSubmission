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


# ===========================================================================
# DECLINES-B — the printed cycle summary and its boundary charge
# ===========================================================================
# Every fixture below is synthetic and built from the printed cycle summary
# Capital One flattens onto one line, plus the ACCOUNT DETAIL grid it indexes.

from analysis.capital_one import (  # noqa: E402
    _is_cycle_charge,
    _normalize_cycle_service_charge_dates,
    parse_capital_one_statement,
)
from analysis.schema import Transaction  # noqa: E402

ISSUER_NOTICE = "AN IMPORTANT MESSAGE TO OUR CLIENTS\n"


def native_document(*, service_charge: str = "($15.00)", debits: str = "($200.00)",
                    rows: str = "", detail_total: str = "$200.00") -> str:
    """A Capital One statement printed in the native (non-table) layout.

    The summary is one flattened line, in the printed order, exactly as the
    bank lays its two-column grid out.
    """
    return (
        "Capital One\n"
        f"{ISSUER_NOTICE}"
        "ACCOUNT SUMMARY FOR PERIOD MARCH 01, 2026 - MARCH 31, 2026\n"
        "Business Basic Checking 123456789\n"
        "Previous Balance 02/28/26 $1,000.00 "
        "Number of Days in Cycle 31 "
        "2 Deposits/Credits $500.00 "
        "Minimum Balance This Cycle $800.00 "
        f"3 Checks/Debits {debits} "
        "Average Collected Balance $900.00 "
        f"Service Charges {service_charge} "
        "Ending Balance 03/31/26 $1,300.00\n"
        "ACCOUNT DETAIL FOR PERIOD MARCH 01, 2026 - MARCH 31, 2026\n"
        f"{rows}"
        f"Total {detail_total} {detail_total}\n"
    )


ROWS = (
    "03/02 ACH deposit A COUNTERPARTY $300.00 $1,300.00\n"
    "03/05 TRANSFER WITHDRAWAL To ....0000 $200.00 $1,100.00\n"
    "03/09 Mobile Deposit $200.00 $1,300.00\n"
)


# ---------------------------------------------------------------------------
# D1 — a bracket is a sign marker, not part of the cell's grammar
# ---------------------------------------------------------------------------
# Capital One brackets a summary cell to mark it negative. A cycle in which
# nothing was charged prints `Service Charges $0.00`, never `($0.00)`, so a
# regex requiring the bracket refused every zero-charge statement whole.

def test_d1_a_zero_service_charge_prints_without_a_bracket_and_is_read():
    stmt = parse_capital_one_statement(
        native_document(service_charge="$0.00", rows=ROWS)
    )
    assert stmt is not None
    assert stmt.stated_service_charge == 0.0
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1300.00


def test_d1_a_charged_cycle_still_reads_exactly_as_before():
    stmt = parse_capital_one_statement(
        native_document(service_charge="($15.00)", rows=ROWS)
    )
    assert stmt is not None
    assert stmt.stated_service_charge == 15.00


@pytest.mark.parametrize("printed,expected", [
    ("$0.00", 0.0),
    ("($15.00)", 15.0),
    ("($4.00)", 4.0),
    ("($1,234.56)", 1234.56),
])
def test_d1_every_printed_service_charge_shape_reads_as_its_magnitude(printed, expected):
    stmt = parse_capital_one_statement(
        native_document(service_charge=printed, rows=ROWS)
    )
    assert stmt is not None
    assert stmt.stated_service_charge == expected


def test_d1_the_debit_cell_is_read_in_either_printed_form():
    for printed in ("($200.00)", "$200.00"):
        stmt = parse_capital_one_statement(
            native_document(debits=printed, rows=ROWS)
        )
        assert stmt is not None, printed
        assert stmt.stated_total_debits == 200.00


def test_d1_negative_a_summary_that_is_not_printed_publishes_no_balances():
    # The whole block is still required: a partial summary is not a summary.
    doc = native_document(rows=ROWS).replace("Number of Days in Cycle 31 ", "")
    assert parse_capital_one_statement(doc) is None


# ---------------------------------------------------------------------------
# D2 — the cycle charge the summary states, wherever the ledger posts it
# ---------------------------------------------------------------------------
# The bank posts its cycle charge on the day the charge falls, which can be
# after the cycle it belongs to has closed. The ledger row is then outside the
# printed period, and the ADB engine fails closed on the whole document rather
# than move a row it was not told about.

def txn(date_: str, description: str, amount: float) -> Transaction:
    return Transaction(date=date_, description=description, amount=amount,
                       direction="credit" if amount >= 0 else "debit")


def test_d2_a_charge_named_in_the_ledger_is_moved_onto_the_cycle_end():
    rows = [txn("2026-03-31", "Maintenance charge", -15.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2026-03-29", 15.00)
    assert moved[0].date == "2026-03-29"
    assert "printed 2026-03-31" in moved[0].description


def test_d2_the_printed_total_identifies_a_charge_the_ledger_words_differently():
    # `Cash deposit limit exceeded` is not a maintenance charge by name, but
    # it is exactly the figure the summary states under `Service Charges`.
    rows = [txn("2026-02-28", "Cash deposit limit exceeded", -12.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2026-02-27", 12.00)
    assert moved[0].date == "2026-02-27"
    assert "printed 2026-02-28" in moved[0].description


def test_d2_negative_an_ordinary_debit_at_the_boundary_is_never_moved():
    rows = [txn("2026-02-28", "TRANSFER WITHDRAWAL To ....0000", -500.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2026-02-27", 12.00)
    assert moved[0].date == "2026-02-28"
    assert moved[0].description == "TRANSFER WITHDRAWAL To ....0000"


def test_d2_negative_a_zero_charge_identifies_nothing_by_amount():
    # Without a printed charge there is no figure to match, so only the
    # ledger's own wording can name a cycle charge.
    assert _is_cycle_charge(txn("2026-02-28", "Some fee", 0.0), 0.0) is False
    assert _is_cycle_charge(txn("2026-02-28", "Some fee", -12.00), None) is False


def test_d2_negative_a_credit_of_the_charge_amount_is_not_the_charge():
    assert _is_cycle_charge(txn("2026-02-28", "Refund", 12.00), 12.00) is False


def test_d2_negative_a_charge_far_outside_the_cycle_is_left_where_it_printed():
    rows = [txn("2026-03-10", "Maintenance charge", -15.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2026-02-27", 15.00)
    assert moved[0].date == "2026-03-10"


def test_d2_negative_a_charge_inside_the_cycle_is_not_moved():
    rows = [txn("2026-02-20", "Maintenance charge", -15.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2026-02-27", 15.00)
    assert moved[0].date == "2026-02-20"
    assert "printed" not in moved[0].description
