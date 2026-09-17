"""Stage A parser output → candidate transaction rows (deterministic, provenance kept)."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal

from vlm.tables import ColumnMap, classify_columns, parse_html_tables
from vlm.textparse import parse_date, parse_money

SKIP_DESCRIPTION = re.compile(r"^(total|totals|subtotal|sub-total|ending balance|beginning balance|balance forward|closing balance|opening balance)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CandidateRow:
    date: str | None
    date_text: str
    description: str
    amount: Decimal
    direction: str
    balance: Decimal | None
    page: int
    source: str
    locator: str
    direction_source: str = "printed"


@dataclass(frozen=True)
class Block:
    label: str
    bbox: tuple[float, float, float, float]
    content: str
    order: int
    page: int


def blocks_from_worker(raw: dict, *, page: int, width: int, height: int) -> list[Block]:
    blocks: list[Block] = []
    for order, item in enumerate(raw.get("blocks") or []):
        if not isinstance(item, dict):
            continue
        box = item.get("bbox") or [0, 0, 0, 0]
        try:
            x0, y0, x1, y1 = (float(v) for v in box[:4])
        except (TypeError, ValueError):
            x0 = y0 = x1 = y1 = 0.0
        if width and height:
            norm = (round(x0 / width, 6), round(y0 / height, 6), round(x1 / width, 6), round(y1 / height, 6))
        else:
            norm = (0.0, 0.0, 0.0, 0.0)
        blocks.append(Block(label=str(item.get("label") or "text"), bbox=norm, content=str(item.get("content") or ""),
                            order=int(item.get("order", order)), page=page))
    return sorted(blocks, key=lambda b: b.order)


def _cell(row: list[str], index: int | None) -> str:
    return row[index].strip() if index is not None and index < len(row) else ""


def rows_from_grid(grid: list[list[str]], colmap: ColumnMap, *, page: int, table_index: int,
                   year_hint: int | None = None, day_first: bool = False) -> list[CandidateRow]:
    if colmap.balance is None and colmap.amount is None and colmap.debit is None and colmap.credit is None:
        return []
    rows: list[CandidateRow] = []
    last_date: str | None = None
    for row_index, row in enumerate(grid):
        if colmap.header_row is not None and row_index == colmap.header_row:
            continue
        description = _cell(row, colmap.description)
        debit = parse_money(_cell(row, colmap.debit))
        credit = parse_money(_cell(row, colmap.credit))
        amount = parse_money(_cell(row, colmap.amount))
        balance = parse_money(_cell(row, colmap.balance))
        if debit is None and credit is None and amount is None:
            if rows and description and balance is None:
                rows[-1] = replace(rows[-1], description=(rows[-1].description + " " + description).strip())
            continue
        if SKIP_DESCRIPTION.match(description):
            continue
        date_text = _cell(row, colmap.date)
        date = parse_date(date_text, year_hint=year_hint, day_first=day_first) if date_text else None
        if date is None and not date_text:
            date = last_date
        else:
            last_date = date or last_date
        if debit is not None:
            magnitude, direction, source = abs(debit), "debit", "column"
        elif credit is not None:
            magnitude, direction, source = abs(credit), "credit", "column"
        else:
            magnitude = abs(amount)
            direction = "debit" if amount < 0 else "unknown"
            source = "printed"
        rows.append(CandidateRow(date=date, date_text=date_text, description=description, amount=magnitude,
                                 direction=direction, balance=balance, page=page, source="stage_a",
                                 locator=f"t{table_index}r{row_index}", direction_source=source))
    return rows


def rows_from_blocks(blocks: list[Block], *, year_hint: int | None = None, day_first: bool = False) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    table_index = 0
    for block in blocks:
        if block.label != "table":
            continue
        for grid in parse_html_tables(block.content):
            rows.extend(rows_from_grid(grid, classify_columns(grid), page=block.page, table_index=table_index,
                                       year_hint=year_hint, day_first=day_first))
            table_index += 1
    return rows


def text_lines_from_blocks(blocks: list[Block]) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        if block.label == "table":
            for grid in parse_html_tables(block.content):
                lines.extend(" ".join(c for c in row if c) for row in grid)
        else:
            lines.extend(line.strip() for line in block.content.splitlines() if line.strip())
    return lines
