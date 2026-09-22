"""Stage A parser output → candidate transaction rows (deterministic, provenance kept)."""
from __future__ import annotations

import re
import json
import math
from dataclasses import dataclass, replace
from decimal import Decimal

from vlm.tables import ColumnMap, classify_columns, parse_html_tables
from vlm.textparse import parse_date, parse_money

SKIP_DESCRIPTION = re.compile(r"^(total|totals|subtotal|sub-total|ending balance|beginning balance|balance forward|closing balance|opening balance)\b", re.IGNORECASE)
# A printed balance line, which a reviewer may propose as a missed transaction. Narrower than
# SKIP_DESCRIPTION on purpose: a real merchant can be named "Total ...".
BALANCE_LINE = re.compile(r"^(beginning balance|opening balance|ending balance|closing balance|previous balance|balance forward|balance (?:brought|carried) forward)\b", re.IGNORECASE)


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
    bbox: tuple[float, float, float, float] | None = None
    printed_amount: Decimal | None = None
    # The printed word naming the row's kind when its only text cell is a cheque number ("Check" from a
    # "Check Nbr" column). Structure, not text: the ledger applies it after review (labelled_description).
    description_label: str | None = None


# A column that holds cheque numbers: "Check Nbr", "Check No.", "CHECK #", "Cheque Number", "Chk No".
CHEQUE_NUMBER_HEADER = re.compile(r"^\s*(?P<word>check|cheque|chk)s?\s*(?:no\.?|nbr\.?|num\.?|number|#)\s*$",
                                  re.IGNORECASE)
_BARE_CHEQUE_NUMBER = re.compile(r"#?\s*\d+\s*\*?")


def labelled_description(row: CandidateRow) -> CandidateRow:
    """A row whose description is only a cheque number is named as the statement names the column it sits in:
    the printed label, then the number ("Check 1234"), which is how the production parsers write cheques
    and the word the analysis counts them by. Any other description is left exactly as read."""
    if row.description_label and _BARE_CHEQUE_NUMBER.fullmatch(row.description.strip()):
        return replace(row, description=f"{row.description_label} {row.description.strip()}")
    return row


@dataclass(frozen=True)
class Block:
    label: str
    bbox: tuple[float, float, float, float] | None
    content: str
    order: int
    page: int


@dataclass(frozen=True)
class DotsLayout:
    page: int
    blocks: tuple[Block, ...]
    rows: tuple[CandidateRow, ...]
    errors: tuple[str, ...]
    truncated: bool
    warnings: tuple[str, ...] = ()


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


def _description_cells(row: list[str], colmap: ColumnMap) -> str:
    # OCR sometimes splits one printed description into an extra, unlabeled cell.
    # Keep those cells in source order instead of dropping account/check references.
    value_columns = {colmap.date, colmap.debit, colmap.credit, colmap.amount, colmap.balance}
    return " ".join(cell.strip() for index, cell in enumerate(row)
                    if index not in value_columns and cell.strip())


def rows_from_grid(grid: list[list[str]], colmap: ColumnMap, *, page: int, table_index: int,
                   year_hint: int | None = None, day_first: bool = False) -> list[CandidateRow]:
    if colmap.balance is None and colmap.amount is None and colmap.debit is None and colmap.credit is None:
        return []
    label = None
    if colmap.header_row is not None and colmap.header_row < len(grid):
        header = grid[colmap.header_row]
        value_columns = {colmap.date, colmap.debit, colmap.credit, colmap.amount, colmap.balance}
        text_columns = [index for index in range(len(header)) if index not in value_columns]
        match = CHEQUE_NUMBER_HEADER.match(header[text_columns[0]]) if len(text_columns) == 1 else None
        label = match.group("word") if match else None
    rows: list[CandidateRow] = []
    last_date: str | None = None
    for row_index, row in enumerate(grid):
        if colmap.header_row is not None and row_index == colmap.header_row:
            continue
        description = _description_cells(row, colmap)
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
                                 locator=f"t{table_index}r{row_index}", direction_source=source,
                                 printed_amount=debit if debit is not None else credit, description_label=label))
    return rows


SECTION_CREDIT = re.compile(r"\b(deposits?|credits?|additions|money in|paid in|deposits and (?:other )?credits)\b", re.IGNORECASE)
SECTION_DEBIT = re.compile(r"\b(withdrawals?|debits?|checks?|cheques?|fees|charges|payments|money out|paid out|subtractions|withdrawals and (?:other )?debits)\b", re.IGNORECASE)
BALANCE_SECTION = re.compile(
    r"\b(?:daily|ledger|running|ending|available|collected)\s+balances?\b|\bbalance\s+summary\b",
    re.IGNORECASE)


def section_direction(text: str) -> str | None:
    """The direction a printed section heading implies for the table below it ("Deposits and other
    credits" → credit, "Checks paid" → debit); None when the heading names both or neither."""
    head = (text or "").strip().splitlines()[0] if text and text.strip() else ""
    if len(head) > 80:
        return None
    credit, debit = bool(SECTION_CREDIT.search(head)), bool(SECTION_DEBIT.search(head))
    if credit and not debit:
        return "credit"
    if debit and not credit:
        return "debit"
    return None


def rows_from_blocks(blocks: list[Block], *, year_hint: int | None = None, day_first: bool = False) -> list[CandidateRow]:
    """Tables become rows; a single-amount table inherits the direction of the section heading printed
    directly above it (`direction_source="section"`), as the reader's sectioned parsers do."""
    rows: list[CandidateRow] = []
    table_index = 0
    heading: str | None = None
    for block in blocks:
        if block.label != "table":
            heading = section_direction(block.content) if block.label in ("text", "paragraph_title", "doc_title", "header") else heading
            continue
        for grid in parse_html_tables(block.content):
            table_rows = rows_from_grid(grid, classify_columns(grid), page=block.page, table_index=table_index,
                                        year_hint=year_hint, day_first=day_first)
            if heading is not None:
                table_rows = [replace(r, direction=heading, direction_source="section") if r.direction == "unknown" else r
                              for r in table_rows]
            rows.extend(table_rows)
            table_index += 1
        heading = None
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


_TEXT_DATE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
    r"[A-Za-z]{3,9}\.?\s+\d{1,2}(?:,?\s+\d{4})?|\d{1,2}\s+[A-Za-z]{3,9}(?:\s+\d{4})?)\s+(.+)$"
)
_TEXT_MONEY = re.compile(r"(?:\(?[-−]?[$€£]?\d[\d,]*\.\d{2}\)?-?(?:\s?(?:CR|DR))?)$")


def _text_rows(block: Block, *, heading: str | None, year_hint: int | None,
               day_first: bool) -> list[CandidateRow]:
    """Conservative text rows: printed date + description + amount [+ balance].

    Ambiguous undated text remains in the layout for the reviewer. Descriptions are
    never normalized, and repeated source lines remain distinct candidates.
    """
    rows: list[CandidateRow] = []
    for index, line in enumerate(block.content.splitlines()):
        match = _TEXT_DATE.match(line)
        if not match:
            continue
        date_text, tail = match.groups()
        money = _TEXT_MONEY.search(tail)
        if not money:
            continue
        last = parse_money(money[0])
        description = tail[:money.start()].rstrip()
        preceding = _TEXT_MONEY.search(description)
        if preceding:
            amount, balance = parse_money(preceding[0]), last
            description = description[:preceding.start()].rstrip()
        else:
            amount, balance = last, None
        if amount is None or not description or SKIP_DESCRIPTION.match(description):
            continue
        direction = heading or ("debit" if amount < 0 else "unknown")
        rows.append(CandidateRow(
            parse_date(date_text, year_hint=year_hint, day_first=day_first), date_text, description,
            abs(amount), direction, balance, block.page, "stage_a", f"b{block.order}l{index}",
            "section" if heading else "printed", block.bbox,
        ))
    return rows


def _markdown_grid(content: str) -> list[list[str]]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines or not all("|" in line for line in lines):
        return []
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in lines
            if not re.fullmatch(r"[|:\-\s]+", line)]


def _complete_html_tables(content: str) -> bool:
    """Recognize the observed bare-table response without repairing fragments.

    Missing element boxes are explicit, not synthesized from page dimensions.
    Balanced structural tags prevent a visibly cut table becoming a shorter read.
    """
    if not re.fullmatch(r"<table\b[^>]*>.*</table\s*>", content, re.I | re.S):
        return False
    for tag in ("table", "tr", "td", "th"):
        opened = len(re.findall(rf"<{tag}\b[^>]*>", content, re.I))
        closed = len(re.findall(rf"</{tag}\s*>", content, re.I))
        if opened != closed:
            return False
    return bool(parse_html_tables(content, preserve_whitespace=True))


def parse_dots_layout(raw: str | list | dict, *, page: int, width: int, height: int,
                      finish_reason: str | None = None, year_hint: int | None = None,
                      day_first: bool = False) -> DotsLayout:
    """Decode dots.mocr layout without repairing or silently salvaging invalid JSON.

    Every return retains the page slot and an explicit truncation/error status.
    Boxes reference the source layout element (a whole table for table rows), not
    an invented per-row crop; the locator identifies the row inside that element.
    """
    errors: list[str] = []
    warnings: list[str] = []
    unboxed = False
    truncated = finish_reason == "length"
    if truncated:
        errors.append("stage_a_truncated")
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```") and text.endswith("```"):
            text = re.sub(r"^```(?:json|html|svg)?\s*", "", text, flags=re.I)[:-3].strip()
        if re.match(r"^(?:<\?xml\b.*?\?>\s*)?<svg\b", text, re.I | re.S):
            # Observed dots responses sometimes redraw a page as SVG instead
            # of transcribing its layout. Even a complete SVG can omit every
            # source word, and its coordinate frame need not match the image.
            # Retain the exact response in the caller's CAS; do not convert
            # vector paths or incidental <text> labels into OCR evidence.
            return DotsLayout(page, (), (), tuple(errors + ["layout_unsupported_svg"]), truncated)
        if _complete_html_tables(text):
            # dots.mocr sometimes emits a complete HTML table instead of its
            # layout envelope. The table is still source evidence, but no box
            # was supplied. Give it a block/row locator without inventing a box.
            raw = [{"category": "Table", "bbox": None, "text": text}]
            unboxed = True
            warnings.append("layout_unboxed")
        else:
            try:
                raw = json.loads(text)
            except (ValueError, TypeError):
                return DotsLayout(page, (), (), tuple(errors + ["layout_invalid_json"]), truncated)
    # The full benchmark prompt permits one layout element as the final JSON
    # object. Validate it identically to an element in the established array
    # form; unknown object envelopes are not inferred or silently unwrapped.
    if isinstance(raw, dict) and "category" in raw:
        raw = [raw]
    if not isinstance(raw, list):
        return DotsLayout(page, (), (), tuple(errors + ["layout_not_array"]), truncated)
    blocks: list[Block] = []
    for order, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("category"), str):
            errors.append(f"layout_element_invalid:{order}")
            continue
        label = item["category"].strip().lower().replace("-", "_")
        content = item.get("text", "" if label in ("picture", "image") else None)
        if not isinstance(content, str):
            errors.append(f"layout_element_invalid:{order}")
            continue
        box = item.get("bbox")
        if unboxed and box is None:
            norm = None
        elif (not isinstance(box, list) or len(box) != 4 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in box)
                or width <= 0 or height <= 0 or not (0 <= box[0] <= box[2] <= width and 0 <= box[1] <= box[3] <= height)):
            errors.append(f"layout_box_invalid:{order}")
            continue
        else:
            norm = tuple(round(v / (width if i % 2 == 0 else height), 6) for i, v in enumerate(box))
        blocks.append(Block(label, norm, content, order, page))
    rows: list[CandidateRow] = []
    heading: str | None = None
    balance_section = False
    for block in blocks:
        # dots also emits complete Markdown grids under the Text category.
        # Preserve that category and its provenance while assembling the cells;
        # pipe-delimited rows cannot match the plain date-line reader below.
        markdown = _markdown_grid(block.content) if block.label in ("table", "text") else []
        if block.label == "text" and not any(
                "-" in line and re.fullmatch(r"[|:\-\s]+", line)
                for line in block.content.splitlines()):
            markdown = []
        if block.label == "table" or markdown:
            grids = parse_html_tables(block.content, preserve_whitespace=True) or ([markdown] if markdown else [])
            for index, grid in enumerate(grids):
                columns = classify_columns(grid, headerless_transaction_amount=not balance_section)
                for row in rows_from_grid(grid, columns, page=page, table_index=index,
                                          year_hint=year_hint, day_first=day_first):
                    if row.direction == "unknown" and heading:
                        row = replace(row, direction=heading, direction_source="section")
                    rows.append(replace(row, locator=f"b{block.order}{row.locator}", bbox=block.bbox))
            if not grids:
                rows.extend(_text_rows(block, heading=heading, year_hint=year_hint, day_first=day_first))
            heading = None
            balance_section = False
        else:
            rows.extend(_text_rows(block, heading=heading, year_hint=year_hint, day_first=day_first))
            if block.label in ("text", "paragraph_title", "section_header", "title", "doc_title", "header", "page_header"):
                heading = section_direction(block.content)
                first_line = block.content.strip().splitlines()[0] if block.content.strip() else ""
                balance_section = len(first_line) <= 80 and bool(BALANCE_SECTION.search(first_line))
    return DotsLayout(page, tuple(blocks), tuple(rows), tuple(errors), truncated, tuple(warnings))
