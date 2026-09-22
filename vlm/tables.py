"""HTML tables (as document parsers emit them) → text grids → column roles."""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re

from vlm.textparse import is_date_like, is_money_like

HEADER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "date": ("date", "posted", "post date", "trans date", "transaction date", "effective", "date posted"),
    "description": ("description", "details", "transaction", "particulars", "memo", "activity", "narrative", "payee", "transactions"),
    "debit": ("debit", "debits", "withdrawal", "withdrawals", "payments", "money out", "paid out", "charges", "checks/debits", "withdrawals/debits", "subtractions"),
    "credit": ("credit", "credits", "deposit", "deposits", "money in", "paid in", "additions", "deposits/credits", "deposits/additions"),
    "amount": ("amount", "transaction amount", "amt"),
    "balance": ("balance", "running balance", "ledger balance", "ending balance", "balance forward", "daily balance"),
}
ROLE_PRIORITY = ("balance", "debit", "credit", "amount", "date", "description")


@dataclass(frozen=True)
class ColumnMap:
    date: int | None
    description: int | None
    debit: int | None
    credit: int | None
    amount: int | None
    balance: int | None
    header_row: int | None


class _TableParser(HTMLParser):
    def __init__(self, *, preserve_whitespace: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._span = 1
        self._preserve_whitespace = preserve_whitespace

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._span = 1
            for name, value in attrs:
                if name == "colspan" and value and value.isdigit():
                    self._span = max(1, int(value))
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            raw = "".join(self._cell)
            text = raw.strip() if self._preserve_whitespace else " ".join(raw.split())
            self._row.extend([text] * self._span)
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_html_tables(html: str, *, preserve_whitespace: bool = False) -> list[list[list[str]]]:
    parser = _TableParser(preserve_whitespace=preserve_whitespace)
    parser.feed(html or "")
    parser.close()
    return [table for table in parser.tables if table]


def _header_role(cell: str) -> str | None:
    text = " ".join(cell.lower().replace("_", " ").split())
    if not text:
        return None
    # These explicit compound labels name one direction. Match the whole
    # normalized header; splitting arbitrary slash labels would also interpret
    # ambiguous headings such as "debit/credit" as a single direction.
    compound_direction = {"cheque/debit": "debit", "deposit/credit": "credit"}.get(text)
    if compound_direction is not None:
        return compound_direction
    for role in ROLE_PRIORITY:
        for keyword in HEADER_KEYWORDS[role]:
            if text == keyword or text.startswith(keyword + " ") or text.endswith(" " + keyword) or text == keyword + "s":
                return role
    return None


def _column(grid: list[list[str]], index: int) -> list[str]:
    return [row[index] for row in grid if index < len(row)]


def _fragmented_card_amount(grid: list[list[str]], date_col: int,
                            money_cols: list[int]) -> int | None:
    """Recognize a card suffix split out of a headerless description by dots.

    A bare integer alone is not identifier evidence. Require a four-digit
    suffix supported by card wording, optional occupancy, and the same suffix
    moving into the preceding text-fragment column on another row. The final
    monetary column stays fixed and supplies every dated row's decimal amount.
    If any evidence is missing, retain the ordinary column interpretation.
    """
    if len(money_cols) != 2:
        return None
    reference, monetary = money_cols
    if monetary != reference + 1 or reference < 3:
        return None
    dated = [row for row in grid if date_col < len(row) and is_date_like(row[date_col])]
    if not dated or any(len(row) != monetary + 1 for row in dated):
        return None
    if any(not is_money_like(row[monetary]) or not re.search(
            r"\.\d{2}(?:\s*(?:CR|DR))?\s*[)-]?\s*$", row[monetary], re.I) for row in dated):
        return None
    suffix_rows = [row for row in dated if row[reference].strip()]
    if not 0 < len(suffix_rows) < len(dated):
        return None
    if any(re.fullmatch(r"[0-9]{4}", row[reference].strip()) is None for row in suffix_rows):
        return None
    fragment_cols = [col for col in range(reference) if col != date_col and
                     any(any(char.isalpha() for char in row[col]) and not is_money_like(row[col])
                         for row in dated)]
    if len(fragment_cols) < 2 or reference - 1 not in fragment_cols:
        return None
    suffixes = {row[reference].strip() for row in suffix_rows}
    card_supported = {row[reference].strip() for row in suffix_rows
                      if re.search(r"\bcard\b", " ".join(row[col] for col in fragment_cols), re.I)}
    if suffixes != card_supported:
        return None
    if not any(not row[reference].strip() and row[reference - 1].strip() in suffixes for row in dated):
        return None
    return monetary


def classify_columns(grid: list[list[str]], *, headerless_transaction_amount: bool = False) -> ColumnMap:
    """Classify printed columns; optionally retain dots' headerless single-amount rows.

    The opt-in is narrow: a date column, a textual description column, and
    one numeric amount column, without an explicit balance label. It also
    recognizes a card suffix that moves between description fragment columns.
    Existing callers retain their historical mapping. No direction is supplied.
    """
    empty = ColumnMap(None, None, None, None, None, None, None)
    if not grid:
        return empty
    width = max(len(row) for row in grid)
    for row_index, row in enumerate(grid[:3]):
        roles = [_header_role(cell) for cell in row]
        if sum(1 for r in roles if r) >= 2:
            assigned: dict[str, int] = {}
            for col, role in enumerate(roles):
                if role and role not in assigned:
                    assigned[role] = col
            return ColumnMap(assigned.get("date"), assigned.get("description"), assigned.get("debit"),
                             assigned.get("credit"), assigned.get("amount"), assigned.get("balance"), row_index)
    stats = []
    for col in range(width):
        cells = [c for c in _column(grid, col) if c.strip()]
        dates = sum(1 for c in cells if is_date_like(c))
        money = sum(1 for c in cells if is_money_like(c) and not is_date_like(c))
        avg_len = (sum(len(c) for c in cells) / len(cells)) if cells else 0.0
        stats.append((col, len(cells), dates, money, avg_len))
    date_col = max((s for s in stats if s[1] and s[2] * 2 >= s[1]), key=lambda s: (s[2], -s[0]), default=None)
    money_cols = [s[0] for s in stats if s[1] and s[3] * 2 >= s[1] and (date_col is None or s[0] != date_col[0])]
    if headerless_transaction_amount and date_col is not None:
        fragmented_amount = _fragmented_card_amount(grid, date_col[0], money_cols)
        if fragmented_amount is not None:
            money_cols = [fragmented_amount]
    balance = money_cols[-1] if money_cols else None
    others = [c for c in money_cols if c != balance]
    amount = debit = credit = None
    if len(others) == 1:
        amount = others[0]
    elif len(others) >= 2:
        debit, credit = others[-2], others[-1]
    used = {c for c in (balance, amount, debit, credit, date_col[0] if date_col else None) if c is not None}
    text_cols = [s for s in stats if s[0] not in used and s[1]]
    description = max(text_cols, key=lambda s: (s[4], -s[0]))[0] if text_cols else None
    if (headerless_transaction_amount and len(money_cols) == 1
            and date_col is not None and description is not None):
        single_money = money_cols[0]
        explicitly_balance = any(
            single_money < len(row) and _header_role(row[single_money]) == "balance"
            for row in grid[:3])
        dated_descriptions = [row[description] for row in grid
                              if description < len(row) and date_col[0] < len(row)
                              and is_date_like(row[date_col[0]])]
        if not explicitly_balance and any(any(char.isalpha() for char in cell)
                                          for cell in dated_descriptions):
            amount, balance = single_money, None
    return ColumnMap(date_col[0] if date_col else None, description, debit, credit, amount, balance, None)
