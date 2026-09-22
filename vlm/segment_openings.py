"""Narrow source binding for an explicitly printed page opening.

This supplements a missing reviewer metadata field, never a transaction row.
The caller persists the complete layout under evidence_sha256 before using it.
No adjacent-line, running-balance, bank-name, or arithmetic inference is used.
"""
import re
from decimal import Decimal
import math

from vlm.tables import classify_columns, parse_html_tables
from vlm.textparse import parse_money

OPENING_RULE = "unique_explicit_balance_forward_before_transactions_v1"
_LABELS = {"balance forward", "balance brought forward", "opening balance", "beginning balance"}
_LOCATOR = re.compile(r"b(\d+)t(\d+)r(\d+)")


def extract_printed_opening(layout, *, evidence_sha256):
    if (layout.errors or layout.truncated or not layout.rows
            or re.fullmatch(r"[0-9a-f]{64}", evidence_sha256) is None):
        return None
    positions = []
    for candidate in layout.rows:
        match = _LOCATOR.fullmatch(candidate.locator)
        if match is None or candidate.page != layout.page:
            return None
        positions.append(tuple(map(int, match.groups())))
    first = min(positions)
    found = []
    label_count = 0
    for block in layout.blocks:
        for table_index, grid in enumerate(parse_html_tables(block.content)):
            columns = classify_columns(grid)
            for row_index, cells in enumerate(grid):
                labels = [index for index, cell in enumerate(cells)
                          if " ".join(cell.casefold().strip().rstrip(":").split()) in _LABELS]
                label_count += len(labels)
                if len(labels) != 1 or columns.balance is None or columns.description != labels[0]:
                    continue
                if columns.balance >= len(cells) or columns.balance == labels[0]:
                    continue
                # A compact printed date can resemble a currency-prefixed
                # number to parse_money. Its classified column is date evidence,
                # never a second balance or amount observation.
                money = [(index, parse_money(cell)) for index, cell in enumerate(cells)
                         if index != columns.date]
                money = [(index, value) for index, value in money if value is not None]
                if len(money) != 1 or money[0][0] != columns.balance:
                    continue
                position = (block.order, table_index, row_index)
                if position >= first:
                    continue
                value = float(money[0][1])
                if not math.isfinite(value) or Decimal(str(value)) != money[0][1]:
                    continue
                found.append({"page": layout.page, "value": value,
                              "source": "stage_a_printed_opening",
                              "locator": f"b{block.order}t{table_index}r{row_index}",
                              "evidence_sha256": evidence_sha256, "rule": OPENING_RULE})
    return found[0] if label_count == len(found) == 1 else None
