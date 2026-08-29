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
        "ACCOUNT SUMMARY FOR PERIOD MARCH 01, 2054 - MARCH 31, 2054\n"
        "Previous Balance 02/28/54 $1,000.00 "
        "Number of Days in Cycle 31 "
        "2 Deposits/Credits $500.00 "
        "Minimum Balance This Cycle $800.00 "
        f"3 Checks/Debits {debits} "
        "Average Collected Balance $900.00 "
        f"Service Charges {service_charge} "
        "Ending Balance 03/31/54 $1,300.00\n"
        "ACCOUNT DETAIL FOR PERIOD MARCH 01, 2054 - MARCH 31, 2054\n"
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


def test_d1_the_debit_cell_reads_as_a_magnitude_from_its_printed_bracket():
    stmt = parse_capital_one_statement(native_document(debits="($200.00)", rows=ROWS))
    assert stmt is not None
    assert stmt.stated_total_debits == 200.00


def test_d1_a_zero_debit_total_needs_no_bracket():
    # Nothing was withdrawn, so there is no sign to mark.
    zero = native_document(debits="$0.00", rows=ROWS, detail_total="$0.00")
    stmt = parse_capital_one_statement(zero.replace("3 Checks/Debits", "0 Checks/Debits"))
    assert stmt is not None
    assert stmt.stated_total_debits == 0.00


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
    rows = [txn("2054-03-31", "Maintenance charge", -15.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2054-03-29", -15.00)
    assert moved[0].date == "2054-03-29"
    assert "printed 2054-03-31" in moved[0].description


def test_d2_the_printed_total_identifies_a_charge_the_ledger_words_differently():
    # `Cash deposit limit exceeded` is not a maintenance charge by name, but
    # it is exactly the figure the summary states under `Service Charges`.
    rows = [txn("2054-02-28", "Cash deposit limit exceeded", -12.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2054-02-27", -12.00)
    assert moved[0].date == "2054-02-27"
    assert "printed 2054-02-28" in moved[0].description


def test_d2_negative_an_ordinary_debit_at_the_boundary_is_never_moved():
    rows = [txn("2054-02-28", "TRANSFER WITHDRAWAL To ....0000", -500.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2054-02-27", -12.00)
    assert moved[0].date == "2054-02-28"
    assert moved[0].description == "TRANSFER WITHDRAWAL To ....0000"


def test_d2_negative_a_zero_charge_identifies_nothing_by_amount():
    # Without a printed charge there is no figure to match, so only the
    # ledger's own wording can name a cycle charge.
    assert _is_cycle_charge(txn("2054-02-28", "Some fee", 0.0), 0.0) is False
    assert _is_cycle_charge(txn("2054-02-28", "Some fee", -12.00), None) is False


def test_d2_negative_a_credit_of_the_charge_amount_is_not_the_charge():
    assert _is_cycle_charge(txn("2054-02-28", "Refund fee", 12.00), -12.00) is False


def test_d2_negative_a_charge_far_outside_the_cycle_is_left_where_it_printed():
    rows = [txn("2054-03-10", "Maintenance charge", -15.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2054-02-27", -15.00)
    assert moved[0].date == "2054-03-10"


def test_d2_negative_a_charge_inside_the_cycle_is_not_moved():
    rows = [txn("2054-02-20", "Maintenance charge", -15.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2054-02-27", -15.00)
    assert moved[0].date == "2054-02-20"
    assert "printed" not in moved[0].description


# ---------------------------------------------------------------------------
# D3 — the printed sign is read, and each total is published by a stated rule
# ---------------------------------------------------------------------------
# Adversarial review, closures 1 and 2. Widening the cell to admit the
# unbracketed form made an unbracketed NON-ZERO cell parse for the first time,
# and `abs()` then mapped `($15.00)` and `$15.00` onto the same published
# 15.00 — a charge and a service-charge refund, indistinguishable.

def test_d3_a_bracketed_charge_and_an_unbracketed_one_do_not_collapse():
    charged = parse_capital_one_statement(
        native_document(service_charge="($15.00)", rows=ROWS))
    refunded = parse_capital_one_statement(
        native_document(service_charge="$15.00", rows=ROWS))
    assert charged is not None
    assert charged.stated_service_charge == 15.00
    # The unbracketed non-zero cell points the wrong way for its column, so the
    # summary is refused outright rather than published as if it were a charge.
    assert refunded is None


def test_d3_a_zero_charge_is_not_a_wrong_way_cell():
    stmt = parse_capital_one_statement(native_document(service_charge="$0.00", rows=ROWS))
    assert stmt is not None
    assert stmt.stated_service_charge == 0.0


def test_d3_a_bracketed_credits_total_is_refused_not_published_negative():
    # `stated_total_credits` was the one summary cell read without `abs()`, so
    # a bracketed cell published -500.0 with nothing downstream to catch it.
    assert parse_capital_one_statement(
        native_document(rows=ROWS).replace(
            "2 Deposits/Credits $500.00", "2 Deposits/Credits ($500.00)")) is None


def test_d3_an_unbracketed_debit_total_is_refused():
    assert parse_capital_one_statement(
        native_document(debits="$200.00", rows=ROWS)) is None


def test_d3_balances_keep_their_sign_while_totals_are_magnitudes():
    stmt = parse_capital_one_statement(
        native_document(rows=ROWS).replace(
            "Average Collected Balance $900.00", "Average Collected Balance ($59.78)"))
    assert stmt is not None
    assert stmt.stated_average_balance == -59.78     # a balance keeps its sign
    assert stmt.stated_total_debits == 200.00        # a total is a magnitude
    assert stmt.stated_service_charge == 15.00


# ---------------------------------------------------------------------------
# D4 — matching an amount is not identifying a fee
# ---------------------------------------------------------------------------
# Adversarial review, closure 3. The arithmetic arm re-dated ANY debit whose
# amount equalled the printed charge inside the window — including a purchase,
# which it also relabelled with a `(printed ...)` annotation.

def test_d4_a_purchase_of_the_charge_amount_is_never_re_dated():
    rows = [txn("2054-02-28", "STARBUCKS STORE 12345 CARROLLTON TX", -12.00)]
    moved = _normalize_cycle_service_charge_dates(rows, "2054-02-27", -12.00)
    assert moved[0].date == "2054-02-28", "a purchase was moved onto the cycle end"
    assert moved[0].description == "STARBUCKS STORE 12345 CARROLLTON TX"


@pytest.mark.parametrize("description", [
    "STARBUCKS STORE 12345 CARROLLTON TX",
    "TRANSFER WITHDRAWAL To ....0450 UTIDMMPERSZFAR2YPHS",
    "ACH Withdrawal AMEX EPAYMENT ACH PMT",
    "Mobile Deposit",
])
def test_d4_no_ordinary_row_is_a_fee_however_well_the_amount_matches(description):
    assert _is_cycle_charge(txn("2054-02-28", description, -12.00), -12.00) is False


@pytest.mark.parametrize("description", [
    "Cash deposit limit exceeded",
    "Service charge",
    "NSF charge",
    "Overdraft fee",
])
def test_d4_a_fee_worded_row_of_the_printed_amount_is_the_cycle_charge(description):
    assert _is_cycle_charge(txn("2054-02-28", description, -12.00), -12.00) is True


def test_d4_the_guard_compares_signs_not_magnitudes():
    # A printed service-charge REFUND (+12.00) must not adopt a -12.00 fee row.
    assert _is_cycle_charge(txn("2054-02-28", "NSF charge", -12.00), 12.00) is False
    assert _is_cycle_charge(txn("2054-02-28", "NSF charge", -12.00), -12.00) is True


def test_d4_the_wording_arm_is_unchanged_and_needs_no_printed_amount():
    rows = [txn("2054-02-28", "Maintenance charge", -15.00)]
    assert _normalize_cycle_service_charge_dates(rows, "2054-02-27", None)[0].date == "2054-02-27"


# ---------------------------------------------------------------------------
# D5 — the published account name is read, never named
# ---------------------------------------------------------------------------
# Adversarial review, closure 5. The parser published
# `account_name="Business Basic Checking"` on every document — the same R-1
# class removed from us_bank, and a worse instance: the phrase appears in NONE
# of the documents this parser validates. Its only occurrence anywhere is in a
# filename, which the admissibility boundary strips before any parser runs.

def test_d5_a_layout_printing_no_product_line_publishes_no_product_name():
    stmt = parse_capital_one_statement(native_document(rows=ROWS))
    assert stmt is not None
    assert stmt.account_name is None
    assert stmt.account_number is None


def test_d5_a_printed_account_line_is_read_structurally():
    doc = native_document(rows=ROWS).replace(
        "ACCOUNT SUMMARY FOR PERIOD",
        "Business Enhanced Checking 123456789\nACCOUNT SUMMARY FOR PERIOD")
    stmt = parse_capital_one_statement(doc)
    assert stmt is not None
    assert stmt.account_name == "Business Enhanced Checking"
    assert stmt.account_number == "123456789"


def test_d5_negative_the_product_name_is_never_taken_from_the_filename():
    # The boundary strips the filename comment, so a parser cannot see it; this
    # pins that the reader does not reach for it by another route either.
    doc = "<!-- source: Business_Basic_Checking_1593_MAR_2026.pdf -->\n" + native_document(rows=ROWS)
    stmt = parse_capital_one_statement(doc)
    assert stmt is not None
    assert stmt.account_name is None
