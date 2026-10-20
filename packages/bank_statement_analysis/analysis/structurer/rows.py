"""Rows and column roles, decided by the document's own arithmetic.

A statement is one structure printed many ways: a period, an opening balance,
a sequence of dated signed amounts, a closing balance. A parser encodes one
printing. This module encodes the structure and INFERS the printing, and it
never asserts a reading it cannot check:

* **which column holds the date** — with geometry, the x-position where dates
  actually cluster; without it, the head of the line;
* **which column holds the running balance** — the reading under which
  `balance[i] - balance[i-1] == amount[i]` holds across the document. A wrong
  column cannot produce that agreement dozens of times by accident;
* **which sign each amount carries** — from the balance chain where it exists;
  from separated debit/credit columns where geometry shows two money columns;
  from the direction word in the nearest heading otherwise; and **nowhere
  else**. An amount whose direction cannot be established is not published,
  because a debit read as a credit reconciles nowhere and misleads everywhere.

Every accepted row keeps its provenance (page, line, and the span of the
amount as printed) so `grounding.py` can verify it against the source
independently of the reasoning that produced it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .geometry import DocumentGeometry, GeoLine
from .tokens import DATE_PATTERNS, MoneyToken, money_tokens, read_date

__all__ = [
    "MIN_CHAIN_AGREEMENT",
    "MIN_CHAIN_ROWS",
    "RowCandidate",
    "SourceLine",
    "build_rows",
    "source_lines_from_geometry",
    "source_lines_from_text",
]

#: A reading of the columns is accepted only if the document's own balances
#: agree with it this often. Chosen high on purpose: the failure mode this
#: guards against is a plausible-but-wrong column, and a wrong column produces
#: agreement near zero, so anything short of "almost always" means the reading
#: is not established. Not fitted to any document — moving it is a design
#: change, and the property tests in tests/test_structurer_safety.py are what
#: would have to be re-argued.
MIN_CHAIN_AGREEMENT = 0.9
#: ...over at least this many rows. Three rows can agree by coincidence.
MIN_CHAIN_ROWS = 5

_PAGE_MARKER_RE = re.compile(r"^---\s*Page\s+(\d+)(?:\s*\(empty\))?\s*---\s*$", re.IGNORECASE)
_SOURCE_COMMENT_RE = re.compile(r"^<!--.*?-->\s*$", re.MULTILINE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

_CREDIT_WORDS = ("DEPOSIT", "CREDIT", "ADDITION", "MONEY IN", "AMOUNT RECEIVED", "PAYMENTS RECEIVED")
_DEBIT_WORDS = (
    "WITHDRAWAL", "DEBIT", "CHECKS", "CHECK PAID", "SUBTRACTION", "MONEY OUT",
    "FEE", "CHARGE", "PAYMENT", "PURCHASE",
)
_SUMMARY_WORDS = ("SUMMARY", "TOTAL", "BALANCE FORWARD", "DAILY BALANCE")

#: A dated line carrying money is not automatically a transaction. Statements
#: print summary lines in exactly that shape — "Your balance forward on Jul 31,
#: 2023  $34,313.58", "Total deposits 12,004.10", a closing-balance line — and
#: reading one as a posting both invents a transaction and (when it sits in the
#: previous period, as opening balances do) drags the ledger outside its own
#: statement period. Matched as a PREFIX of the row text so that a real
#: description merely containing the word "total" is untouched.
_ROW_EXCLUSION_RE = re.compile(
    r"^(?:YOUR\s+|LESS\s+|PLUS\s+)?"
    r"(?:SUB[-\s]?)?"
    r"(?:TOTALS?|BALANCE\s+FORWARD|BALANCE\s+BROUGHT\s+FORWARD|OPENING\s+BALANCE|"
    r"BEGINNING\s+BALANCE|CLOSING\s+BALANCE|ENDING\s+BALANCE|PREVIOUS\s+BALANCE|"
    r"NEW\s+BALANCE|DAILY\s+BALANCE|AVERAGE\s+|SOLDE\s+|STATEMENT\s+PERIOD)"
    r"\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceLine:
    """One line of the document, from either input, with where it came from."""

    page: int
    text: str
    index: int
    geo: GeoLine | None = None

    def x_at(self, offset: int) -> float | None:
        return self.geo.x_at(offset) if self.geo is not None else None


@dataclass(frozen=True)
class RowCandidate:
    """One transaction row, with everything needed to check it later."""

    date: str
    description: str
    amount: float
    running_balance: float | None
    page: int
    line_index: int
    date_text: str
    amount_text: str
    sign_source: str

    @property
    def direction(self) -> str:
        return "credit" if self.amount >= 0 else "debit"


@dataclass
class RowSet:
    rows: list[RowCandidate] = field(default_factory=list)
    chain_agreement: float = 0.0
    chained: bool = False
    reason: str = "ok"
    seen_row_lines: int = 0


# ---------------------------------------------------------------------------
# Input adapters
# ---------------------------------------------------------------------------

def source_lines_from_text(markdown: str) -> list[SourceLine]:
    """Flat markdown -> lines, tracking the page each one sits on.

    Table markup is flattened row-wise: a `<tr>` becomes one line, so a table
    row reads like a text row and the rest of the module needs no branch.
    """
    text = _SOURCE_COMMENT_RE.sub("", markdown)

    def flatten_row(match: re.Match) -> str:
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", match.group(1), re.IGNORECASE | re.DOTALL)
        body = " ".join(_HTML_TAG_RE.sub(" ", cell) for cell in cells) or match.group(1)
        return "\n" + re.sub(r"\s+", " ", _HTML_TAG_RE.sub(" ", body)).strip() + "\n"

    text = re.sub(r"<tr\b[^>]*>(.*?)</tr>", flatten_row, text, flags=re.IGNORECASE | re.DOTALL)
    text = _HTML_TAG_RE.sub(" ", text)

    lines: list[SourceLine] = []
    page = 1
    for raw in text.splitlines():
        stripped = re.sub(r"[ \t]+", " ", raw).strip()
        if not stripped:
            continue
        marker = _PAGE_MARKER_RE.match(stripped)
        if marker:
            page = int(marker.group(1))
            continue
        lines.append(SourceLine(page, stripped, len(lines)))
    return lines


def source_lines_from_geometry(geometry: DocumentGeometry) -> list[SourceLine]:
    return [
        SourceLine(line.page, line.text, index, line)
        for index, line in enumerate(geometry.lines)
        if line.text.strip()
    ]


# ---------------------------------------------------------------------------
# Column geography
# ---------------------------------------------------------------------------

def _first_date(text: str, default_year: int | None) -> tuple[str, str, int, int] | None:
    """(raw token, iso, start, end) for the first readable date in `text`."""
    best: tuple[str, str, int, int] | None = None
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            iso = read_date(match.group("d"), default_year=default_year)
            if iso is None:
                continue
            if best is None or match.start() < best[2]:
                best = (match.group("d"), iso, match.start(), match.end())
            break
    return best


def _cluster(values: list[float], tolerance: float) -> list[list[float]]:
    """1-D clustering by gap. Columns on a page are separated by real space."""
    if not values:
        return []
    ordered = sorted(values)
    clusters = [[ordered[0]]]
    for value in ordered[1:]:
        if value - clusters[-1][-1] <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return clusters


def _date_column(lines: list[SourceLine], default_year: int | None) -> tuple[float, float] | None:
    """The x-band where dates are printed, or None without geometry.

    This is the single measurement the 3a spike lacked: a row is a row because
    its date sits in the date column, not because the flattening happened to
    put the date first. A check number, a posting code or a running left-hand
    column ahead of the date stops being fatal.
    """
    positions: list[float] = []
    for line in lines:
        if line.geo is None:
            return None
        found = _first_date(line.text, default_year)
        if not found:
            continue
        x = line.x_at(found[2])
        if x is not None:
            positions.append(x)
    if len(positions) < MIN_CHAIN_ROWS:
        return None
    clusters = _cluster(positions, tolerance=6.0)
    biggest = max(clusters, key=len)
    if len(biggest) < MIN_CHAIN_ROWS or len(biggest) < 0.5 * len(positions):
        return None
    return (min(biggest) - 6.0, max(biggest) + 6.0)


def _money_columns(lines: list[SourceLine], row_lines: list[int]) -> list[tuple[float, float]]:
    """Bands where money is printed, left to right. Geometry only."""
    positions: list[float] = []
    for index in row_lines:
        line = lines[index]
        if line.geo is None:
            return []
        for token in money_tokens(line.text):
            x = line.x_at(token.start)
            if x is not None:
                positions.append(x)
    clusters = [c for c in _cluster(positions, tolerance=12.0) if len(c) >= MIN_CHAIN_ROWS]
    return [(min(c) - 12.0, max(c) + 12.0) for c in clusters]


def _column_of(line: SourceLine, token: MoneyToken, columns: list[tuple[float, float]]) -> int | None:
    x = line.x_at(token.start)
    if x is None:
        return None
    for index, (low, high) in enumerate(columns):
        if low <= x <= high:
            return index
    return None


# ---------------------------------------------------------------------------
# Section context — the fallback sign source
# ---------------------------------------------------------------------------

def _section_sign(text: str) -> int | None:
    """+1/-1 when a heading names a direction, else None.

    Direction words are banking furniture in the document's own language, not
    knowledge of an institution: no bank, product or document is named, and the
    same list reads a bank whose parser does not exist.
    """
    upper = text.upper()
    if any(word in upper for word in _SUMMARY_WORDS):
        return None
    credit = any(word in upper for word in _CREDIT_WORDS)
    debit = any(word in upper for word in _DEBIT_WORDS)
    if credit == debit:
        return None
    return 1 if credit else -1


# ---------------------------------------------------------------------------
# Row building
# ---------------------------------------------------------------------------

@dataclass
class _RawRow:
    line_index: int
    page: int
    date: str
    date_text: str
    description: str
    tokens: list[MoneyToken]
    columns: list[int | None]
    section_sign: int | None


def _collect(lines: list[SourceLine], default_year: int | None,
             date_band: tuple[float, float] | None) -> list[_RawRow]:
    rows: list[_RawRow] = []
    section_sign: int | None = None
    for line in lines:
        found = _first_date(line.text, default_year)
        in_band = True
        if found and date_band is not None:
            x = line.x_at(found[2])
            in_band = x is not None and date_band[0] <= x <= date_band[1]
        elif found and date_band is None:
            # No geometry: the date must lead the line, or the "row" is really a
            # sentence that mentions a date.
            in_band = found[2] <= 2

        if not found or not in_band:
            sign = _section_sign(line.text)
            if sign is not None:
                section_sign = sign
            elif rows and not money_tokens(line.text) and len(line.text) < 120:
                # A continuation of the previous row's description. Only ever
                # text: a line carrying money is a row we did not recognise,
                # and swallowing it into a description would hide it.
                rows[-1].description = f"{rows[-1].description} {line.text}".strip()
            continue

        raw_token, iso, start, end = found
        tokens = money_tokens(line.text)
        if not tokens:
            continue
        description = (line.text[:start] + " " + line.text[end:])
        if _ROW_EXCLUSION_RE.match(re.sub(r"\s+", " ", description).strip(" .-|")):
            continue
        for token in tokens:
            description = description.replace(token.text, " ")
        rows.append(_RawRow(
            line_index=line.index,
            page=line.page,
            date=iso,
            date_text=raw_token,
            description=re.sub(r"\s+", " ", description).strip(" .-|"),
            tokens=tokens,
            columns=[],
            section_sign=section_sign,
        ))
    return rows


def _score_chain(raws: list[_RawRow], opening: float | None) -> tuple[float, int]:
    """How often `balance[i] - balance[i-1]` equals this row's amount, reading
    the last money token on a row as the balance and the one before it as the
    amount. The only hypothesis worth testing first: it is what almost every
    balance-carrying layout prints, and a layout that prints something else
    scores near zero here rather than being mistaken for this one."""
    agree = checked = 0
    previous = opening
    for raw in raws:
        if len(raw.tokens) < 2:
            continue
        balance = raw.tokens[-1].value
        amount = raw.tokens[-2].magnitude
        if previous is not None:
            checked += 1
            if abs(abs(round(balance - previous, 2)) - amount) <= 0.02:
                agree += 1
        previous = balance
    return (agree / checked if checked else 0.0), checked


def build_rows(lines: list[SourceLine], *, default_year: int | None,
               opening_balance: float | None) -> RowSet:
    """Rows, columns and signs — or a refusal that says which step failed."""
    date_band = _date_column(lines, default_year)
    raws = _collect(lines, default_year, date_band)
    if not raws:
        return RowSet(reason="no_dated_rows")

    row_lines = [raw.line_index for raw in raws]
    line_by_index = {line.index: line for line in lines}
    columns = _money_columns(lines, row_lines) if lines and lines[0].geo is not None else []
    if columns:
        for raw in raws:
            raw.columns = [_column_of(line_by_index[raw.line_index], token, columns)
                           for token in raw.tokens]

    # Hypothesis 1: the last money token on a row is the running balance and
    # the one before it is the amount. This is the reading almost every
    # balance-carrying layout uses, and the chain test is what proves it here.
    best_agreement, checked = _score_chain(raws, opening_balance)
    chained = best_agreement >= MIN_CHAIN_AGREEMENT and checked >= MIN_CHAIN_ROWS

    # Which money band is debits and which is credits, decided once for the
    # document rather than per row: the answer is a property of the layout, and
    # recomputing it inside the loop would make row building quadratic.
    debit_column, credit_column = (
        columns_debit_credit(raws, columns) if len(columns) >= 3 else (None, None)
    )

    rows: list[RowCandidate] = []
    previous = opening_balance
    for raw in raws:
        amount: float | None = None
        balance: float | None = None
        sign_source = ""

        if chained and len(raw.tokens) >= 2:
            balance = raw.tokens[-1].value
            magnitude = raw.tokens[-2].magnitude
            if previous is not None:
                delta = round(balance - previous, 2)
                if abs(abs(delta) - magnitude) <= 0.02:
                    amount, sign_source = delta, "balance_chain"
            previous = balance

        if amount is None and debit_column is not None and credit_column is not None:
            # Geometry says the money on this page sits in three or more bands:
            # the classic debit / credit / balance layout, where the COLUMN is
            # the sign and no chain is needed.
            for token, column in zip(raw.tokens, raw.columns):
                if column == credit_column:
                    amount, sign_source = token.magnitude, "credit_column"
                    break
                if column == debit_column:
                    amount, sign_source = -token.magnitude, "debit_column"
                    break

        if amount is None and not chained and raw.section_sign is not None:
            # Only where the document has no balance column to speak with. In a
            # chained document the balances are the authority, and a row they
            # do not explain is a row we have misread — taking the heading's
            # word for its direction there would let a row contradict the
            # ledger it belongs to, which is exactly the kind of internally
            # inconsistent statement that reconciles and lies.
            magnitude = raw.tokens[-1].magnitude if len(raw.tokens) == 1 else raw.tokens[-2].magnitude
            amount, sign_source = magnitude * raw.section_sign, "section_heading"

        if amount is None:
            continue

        token_text = next(
            (token.text for token in raw.tokens if abs(token.magnitude - abs(amount)) <= 0.005),
            raw.tokens[-1].text,
        )
        rows.append(RowCandidate(
            date=raw.date,
            description=raw.description or "(no description)",
            amount=round(amount, 2),
            running_balance=balance,
            page=raw.page,
            line_index=raw.line_index,
            date_text=raw.date_text,
            amount_text=token_text,
            sign_source=sign_source,
        ))

    if not rows:
        return RowSet(reason="no_signable_rows", chain_agreement=best_agreement,
                      seen_row_lines=len(raws))
    return RowSet(rows=rows, chain_agreement=best_agreement, chained=chained,
                  seen_row_lines=len(raws))


def columns_debit_credit(raws: list[_RawRow], columns: list[tuple[float, float]]
                         ) -> tuple[int | None, int | None]:
    """Which money band is debits and which is credits.

    Decided by the balance column's own movement: for each row that carries a
    balance, the sign of the change says which band the row's other amount sat
    in. Sign is therefore still read off the document's arithmetic — geometry
    only says which cells to compare.
    """
    if len(columns) < 3:
        return None, None
    balance_column = len(columns) - 1
    votes: dict[int, dict[str, int]] = {}
    previous: float | None = None
    for raw in raws:
        balance = next(
            (token.value for token, column in zip(raw.tokens, raw.columns)
             if column == balance_column),
            None,
        )
        if balance is None:
            continue
        if previous is not None:
            direction = "credit" if balance > previous else "debit"
            for token, column in zip(raw.tokens, raw.columns):
                if column is None or column == balance_column:
                    continue
                if abs(abs(round(balance - previous, 2)) - token.magnitude) <= 0.02:
                    votes.setdefault(column, {"credit": 0, "debit": 0})[direction] += 1
        previous = balance

    debit_column = credit_column = None
    for column, tally in votes.items():
        if tally["credit"] >= 3 and tally["credit"] > 3 * tally["debit"]:
            credit_column = column
        elif tally["debit"] >= 3 and tally["debit"] > 3 * tally["credit"]:
            debit_column = column
    return debit_column, credit_column
