"""Synthetic regressions for two explicit slash-separated direction headers."""
from decimal import Decimal

import pytest

from vlm.assemble import rows_from_grid
from vlm.tables import ColumnMap, _header_role, classify_columns


@pytest.mark.parametrize("header,role", [
    ("CHEQUE/DEBIT", "debit"),
    ("cheque/debit", "debit"),
    ("  Cheque/Debit\t", "debit"),
    ("DEPOSIT/CREDIT", "credit"),
    ("deposit/credit", "credit"),
    ("\tDeposit/Credit  ", "credit"),
])
def test_exact_compound_headers_have_their_explicit_direction(header, role):
    assert _header_role(header) == role


@pytest.mark.parametrize("header", [
    "DEBIT/CREDIT", "CREDIT/DEBIT", "CHEQUE/CREDIT", "DEPOSIT/DEBIT",
    "cheque/debit note", "note deposit/credit",
])
def test_ambiguous_or_unrecognized_compound_headers_are_not_generalized(header):
    assert _header_role(header) is None


@pytest.mark.parametrize("header,role", [
    ("DATE CHEQUE/DEBIT", "date"),
    ("DESCRIPTION DEPOSIT/CREDIT", "description"),
    ("DEPOSIT/CREDIT BALANCE", "balance"),
    ("Checks/Debits", "debit"),
    ("Deposits/Credits", "credit"),
    ("CHEQUE / DEBIT", "debit"),
    ("DEPOSIT / CREDIT", "credit"),
    ("Running Balance", "balance"),
    ("Transaction Date", "date"),
    ("Amount", "amount"),
])
def test_existing_roles_and_matching_priority_are_preserved(header, role):
    assert _header_role(header) == role


def _sparse_grid():
    return [
        ["DESCRIPTION", "CHEQUE/DEBIT", "DEPOSIT/CREDIT", "DATE", "BALANCE"],
        ["SYNTHETIC debit  exact", "12.34", "", "01/02/2031", "87.66"],
        ["SYNTHETIC snapshot", "", "", "01/03/2031", "87.66"],
        ["SYNTHETIC snapshot", "", "", "01/04/2031", "87.66"],
        ["SYNTHETIC credit exact", "", "20.00", "01/05/2031", "107.66"],
        ["SYNTHETIC snapshot", "", "", "01/06/2031", "107.66"],
        ["SYNTHETIC snapshot", "", "", "01/07/2031", "107.66"],
        ["SYNTHETIC reversal exact", "(2.00)", "", "01/08/2031", "109.66"],
    ]


@pytest.mark.parametrize("headerless_transaction_amount", [False, True])
def test_sparse_direction_columns_are_mapped_without_replacing_other_roles(headerless_transaction_amount):
    grid = _sparse_grid()
    columns = classify_columns(grid, headerless_transaction_amount=headerless_transaction_amount)
    assert columns == ColumnMap(date=3, description=0, debit=1, credit=2,
                                amount=None, balance=4, header_row=0)
    rows = rows_from_grid(grid, columns, page=2, table_index=0)
    assert len(rows) == 3
    assert [row.description for row in rows] == [grid[index][0] for index in (1, 4, 7)]
    assert [row.date for row in rows] == ["2031-01-02", "2031-01-05", "2031-01-08"]
    assert [row.amount for row in rows] == [Decimal("12.34"), Decimal("20.00"), Decimal("2.00")]
    assert [row.printed_amount for row in rows] == [Decimal("12.34"), Decimal("20.00"), Decimal("-2.00")]
    assert [row.direction for row in rows] == ["debit", "credit", "debit"]
    assert all(row.direction_source == "column" for row in rows)
    assert [row.balance for row in rows] == [Decimal("87.66"), Decimal("107.66"), Decimal("109.66")]
    assert [row.locator for row in rows] == ["t0r1", "t0r4", "t0r7"]


def test_ambiguous_header_stays_unassigned_in_an_otherwise_recognized_header_row():
    grid = [
        ["DESCRIPTION", "DEBIT/CREDIT", "DATE", "BALANCE"],
        ["SYNTHETIC source", "12.34", "01/02/2031", "87.66"],
    ]
    assert classify_columns(grid) == ColumnMap(date=2, description=0, debit=None,
                                               credit=None, amount=None, balance=3, header_row=0)
