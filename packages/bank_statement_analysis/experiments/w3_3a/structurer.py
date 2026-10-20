"""W3-3a spike: a layout-agnostic statement structurer. NOT PRODUCTION.

The question this exists to answer, and nothing else:

> Can a structurer that knows **no bank** fill the same `Statement` schema from
> native/OCR text well enough that the SAME reconciliation gate passes on
> documents no deterministic parser claims?

The design premise is that a bank statement is not really 47 layouts. It is one
structure — a period, an opening balance, a sequence of dated signed amounts,
a closing balance — printed 47 ways. A parser encodes one printing. A
structurer encodes the structure and infers the printing from the document's
own internal consistency:

1. **Rows** are lines that start with something date-shaped and contain money.
2. **Column roles** are chosen by hypothesis, not by knowledge: for each
   candidate reading of a row's money tokens, does the resulting sequence of
   balances actually chain (`balance[i] - balance[i-1] == amount[i]`)? The
   reading that chains is the reading the bank used. Nothing else can produce
   that agreement by chance across dozens of rows.
3. **Signs** come from that chain where it exists, and from the section a row
   sits under where it does not. If neither is available the structurer
   REFUSES — an unsigned amount is the one thing that must never be guessed,
   because a debit read as a credit reconciles nowhere and misleads everywhere.
4. **Summary figures** come from label windows (adapted from the prototype
   `analysis/grounding.py` at 54a9e8d, which had the same idea in the opposite
   direction: it checked that a claimed value sat beside an appropriate label).

Everything the structurer produces is a hypothesis. `analysis.reconcile` is
what decides whether it is true, exactly as it does for the LLM path and for
the 46 parsers — trust comes from the gate, never from the extractor (AD-7).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from analysis.money import parse_money
from analysis.schema import Statement, Transaction

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
_MONTH_WORD = r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?"

#: Every row-date shape seen across the corpus and the archive folders, as one
#: alternation. A structurer cannot ask which one a bank uses; it reads them all
#: and lets the chain test say whether it read the right column.
_DATE_PATTERNS = (
    re.compile(r"^(?P<d>\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"^(?P<d>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),
    re.compile(r"^(?P<d>\d{1,2}[/-]\d{1,2})(?!\d)"),
    re.compile(rf"^(?P<d>{_MONTH_WORD}\s+\d{{1,2}}(?:,?\s+\d{{4}})?)\b", re.IGNORECASE),
    re.compile(rf"^(?P<d>\d{{1,2}}\s+{_MONTH_WORD}(?:\s+\d{{4}})?)\b", re.IGNORECASE),
)

#: The same shapes, unanchored and boundary-guarded, for variant B below.
_INLINE_DATE_PATTERNS = tuple(
    re.compile(r"(?<![\w/-])" + pattern.pattern.lstrip("^"), pattern.flags)
    for pattern in _DATE_PATTERNS
)

_MONEY_RE = re.compile(r"(?<![\d./-])\(?-?\$?\s?\d{1,3}(?:,\d{3})*\.\d{2}\)?-?(?![\d/])")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_PAGE_RE = re.compile(r"^---\s*Page\s+\d+.*---\s*$", re.IGNORECASE)


def _iso(token: str, *, default_year: int | None) -> str | None:
    """Any of the row-date shapes above -> ISO, or None if it is not a date.

    Calendar validity is part of the question (`13/45` is shaped like a date
    and is not one) — the same rule W3-1's `iso_or_none` states for parsers.
    """
    text = token.strip().upper().replace(".", "")
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        year, month, day = (int(part) for part in m.groups())
        return _date_or_none(year, month, day)
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if m:
        month, day, year = (int(part) for part in m.groups())
        if year < 100:
            year += 2000
        return _date_or_none(year, month, day)
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})", text)
    if m and default_year:
        return _date_or_none(default_year, int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(rf"({_MONTH_WORD})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?", text)
    if m:
        year = int(m.group(3)) if m.group(3) else default_year
        return _date_or_none(year, _MONTHS[m.group(1)[:3]], int(m.group(2))) if year else None
    m = re.fullmatch(rf"(\d{{1,2}})\s+({_MONTH_WORD})(?:\s+(\d{{4}}))?", text)
    if m:
        year = int(m.group(3)) if m.group(3) else default_year
        return _date_or_none(year, _MONTHS[m.group(2)[:3]], int(m.group(1))) if year else None
    return None


def _date_or_none(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _money_value(token: str) -> float | None:
    """A money token's signed value. Parens and trailing minus mean negative."""
    text = token.strip()
    negative = text.startswith("(") or text.endswith(")") or text.endswith("-") or text.startswith("-")
    value = parse_money(text.strip("()-").replace("$", "").strip())
    if value is None:
        return None
    return -abs(value) if negative else abs(value)


def text_lines(markdown: str) -> list[str]:
    """Flatten the document into lines, whatever the reader produced.

    Native text arrives as lines; the OCR/table readers arrive as HTML tables.
    Cells become space-separated fields on one line, which is the only shape
    this spike works in — deliberately, because a structurer that needs a table
    grid cannot read the half of the archive that has none.
    """
    def flatten_row(match: re.Match) -> str:
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", match.group(1), re.IGNORECASE | re.DOTALL)
        body = " ".join(_HTML_TAG_RE.sub(" ", cell) for cell in cells) or match.group(1)
        return "\n" + re.sub(r"\s+", " ", _HTML_TAG_RE.sub(" ", body)).strip() + "\n"

    text = re.sub(r"<tr\b[^>]*>(.*?)</tr>", flatten_row, markdown, flags=re.IGNORECASE | re.DOTALL)
    text = _HTML_TAG_RE.sub(" ", text)
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line and not _PAGE_RE.match(line):
            lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# Section context (the fallback sign source)
# ---------------------------------------------------------------------------

_CREDIT_WORDS = ("DEPOSIT", "CREDIT", "ADDITION", "MONEY IN", "PAYMENTS RECEIVED")
_DEBIT_WORDS = (
    "WITHDRAWAL", "DEBIT", "CHECKS", "CHECK PAID", "SUBTRACTION", "MONEY OUT",
    "FEE", "CHARGE", "PAYMENT",
)
_SUMMARY_WORDS = ("SUMMARY", "TOTAL", "BALANCE FORWARD")


def _section_sign(line: str) -> int | None:
    """+1 / -1 when a heading names a direction, else None.

    Direction words are English banking furniture, not bank knowledge: no
    institution, product or document is named here, and the same list works for
    a bank whose parser does not exist.
    """
    upper = line.upper()
    if any(word in upper for word in _SUMMARY_WORDS) and not _MONEY_RE.search(line):
        return None
    credit = any(word in upper for word in _CREDIT_WORDS)
    debit = any(word in upper for word in _DEBIT_WORDS)
    if credit == debit:
        return None
    return 1 if credit else -1


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------

@dataclass
class RawRow:
    date: str
    description: str
    amounts: list[float]
    section_sign: int | None


@dataclass
class StructureResult:
    statement: Statement | None
    reason: str
    rows_seen: int = 0
    rows_used: int = 0
    chained: bool = False
    notes: list[str] = field(default_factory=list)


#: Variant B of row detection (measured in the investigation): the date token
#: may appear anywhere in the first `_INLINE_WINDOW` characters rather than at
#: the very start. Flattening a multi-column page puts a check number, a
#: posting code or a running left-hand column ahead of the date often enough
#: that "line starts with a date" is a layout assumption in disguise.
_INLINE_WINDOW = 40


def _rows(lines: list[str], default_year: int | None, *, date_anywhere: bool = False) -> list[RawRow]:
    rows: list[RawRow] = []
    section_sign: int | None = None
    for line in lines:
        matched = None
        for pattern in _DATE_PATTERNS:
            m = pattern.match(line)
            if m:
                matched = m
                break
        if matched is None and date_anywhere:
            for pattern in _INLINE_DATE_PATTERNS:
                m = pattern.search(line[:_INLINE_WINDOW])
                if m and _MONEY_RE.search(line, m.end()):
                    matched = m
                    break
        if matched is None:
            sign = _section_sign(line)
            if sign is not None:
                section_sign = sign
            continue
        iso = _iso(matched.group("d"), default_year=default_year)
        if iso is None:
            continue
        body = line[matched.end():]
        tokens = list(_MONEY_RE.finditer(body))
        if not tokens:
            continue
        amounts = [value for value in (_money_value(t.group(0)) for t in tokens) if value is not None]
        if not amounts:
            continue
        description = _MONEY_RE.sub("", body).strip(" .-|")
        rows.append(RawRow(iso, re.sub(r"\s+", " ", description), amounts, section_sign))
    return rows


# ---------------------------------------------------------------------------
# Column-role inference: the hypothesis test
# ---------------------------------------------------------------------------

def _chain_score(rows: list[RawRow], opening: float | None) -> tuple[float, list[Transaction]]:
    """How well does "last money token is the running balance" hold?

    Returns (agreement ratio, transactions). Agreement is measured against the
    document's own arithmetic: consecutive balances must differ by the row's
    amount. A layout where the last column is not a balance produces near-zero
    agreement, which is exactly how the hypothesis is rejected.
    """
    usable = [row for row in rows if len(row.amounts) >= 2]
    if len(usable) < 3:
        return 0.0, []
    agree = 0
    checked = 0
    transactions: list[Transaction] = []
    previous = opening
    for row in usable:
        amount, balance = abs(row.amounts[-2]), row.amounts[-1]
        signed: float | None = None
        if previous is not None:
            delta = round(balance - previous, 2)
            checked += 1
            if abs(abs(delta) - amount) <= 0.02:
                agree += 1
                signed = round(delta, 2)
        if signed is None:
            if row.section_sign is None:
                previous = balance
                continue
            signed = round(amount * row.section_sign, 2)
        transactions.append(Transaction(
            date=row.date,
            description=row.description or "(no description)",
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=balance,
        ))
        previous = balance
    return (agree / checked if checked else 0.0), transactions


def _sectioned(rows: list[RawRow]) -> list[Transaction]:
    """Fallback reading: one money column, sign from the section heading."""
    transactions: list[Transaction] = []
    for row in rows:
        if row.section_sign is None:
            continue
        amount = abs(row.amounts[0] if len(row.amounts) == 1 else row.amounts[-1])
        signed = round(amount * row.section_sign, 2)
        transactions.append(Transaction(
            date=row.date,
            description=row.description or "(no description)",
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
        ))
    return transactions


# ---------------------------------------------------------------------------
# Summary fields
# ---------------------------------------------------------------------------

#: Label -> field. Adapted from `analysis/grounding.py` (54a9e8d), which used
#: the same label vocabulary to VALIDATE a value's placement; here it is used
#: to find one. Banking furniture only: no institution is named.
_LABELS: tuple[tuple[str, str], ...] = (
    ("BEGINNING BALANCE", "beginning_balance"),
    ("OPENING BALANCE", "beginning_balance"),
    ("PREVIOUS BALANCE", "beginning_balance"),
    ("BALANCE FORWARD", "beginning_balance"),
    ("BALANCE BROUGHT FORWARD", "beginning_balance"),
    ("ENDING BALANCE", "ending_balance"),
    ("CLOSING BALANCE", "ending_balance"),
    ("NEW BALANCE", "ending_balance"),
    ("FINAL BALANCE", "ending_balance"),
    ("TOTAL DEPOSITS", "stated_total_credits"),
    ("TOTAL CREDITS", "stated_total_credits"),
    ("DEPOSITS AND OTHER CREDITS", "stated_total_credits"),
    ("TOTAL WITHDRAWALS", "stated_total_debits"),
    ("TOTAL DEBITS", "stated_total_debits"),
    ("WITHDRAWALS AND OTHER DEBITS", "stated_total_debits"),
    ("AVERAGE DAILY BALANCE", "stated_average_balance"),
    ("AVERAGE LEDGER BALANCE", "stated_average_balance"),
    ("AVERAGE COLLECTED BALANCE", "stated_average_balance"),
)


def _summary(lines: list[str]) -> dict[str, float]:
    """First money token following each label, on the same line."""
    found: dict[str, float] = {}
    for line in lines:
        upper = line.upper()
        for label, field_name in _LABELS:
            index = upper.find(label)
            if index < 0:
                continue
            token = _MONEY_RE.search(line, index + len(label))
            if token is None:
                continue
            value = _money_value(token.group(0))
            if value is None:
                continue
            found.setdefault(field_name, value)
    for key in ("stated_total_credits", "stated_total_debits", "stated_average_balance"):
        if key in found:
            found[key] = abs(found[key])
    return found


_PERIOD_RE = re.compile(
    r"(?P<a>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    rf"{_MONTH_WORD}\s+\d{{1,2}},?\s+\d{{4}})"
    r"\s*(?:-|to|through|thru|au)\s*"
    r"(?P<b>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    rf"{_MONTH_WORD}\s+\d{{1,2}},?\s+\d{{4}})",
    re.IGNORECASE,
)


_YEAR_NEAR_DATE_RE = re.compile(
    rf"(?:{_MONTH_WORD}\s+\d{{1,2}},?\s+|\d{{1,2}}[/-]\d{{1,2}}[/-])((?:19|20)?\d{{2}})(?!\d)",
    re.IGNORECASE,
)


def _document_year(lines: list[str]) -> int | None:
    """The year the document is mostly about.

    Rows print `MM/DD` or `Mon D` with no year; a structurer that cannot supply
    one reads no rows at all. The year is taken from the dates that DO carry
    one, by majority — never from the clock, which would silently re-date an
    archived statement.
    """
    years: dict[int, int] = {}
    for line in lines:
        for token in _YEAR_NEAR_DATE_RE.findall(line):
            year = int(token)
            if year < 100:
                year += 2000
            if 1990 <= year <= 2100:
                years[year] = years.get(year, 0) + 1
    if not years:
        return None
    return max(years.items(), key=lambda item: (item[1], item[0]))[0]


def _period(lines: list[str]) -> tuple[str, str] | None:
    for line in lines:
        m = _PERIOD_RE.search(line)
        if not m:
            continue
        start = _iso(m.group("a"), default_year=None)
        end = _iso(m.group("b"), default_year=None)
        if start and end and start <= end:
            span = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if 20 <= span <= 100:
                return start, end
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

MIN_CHAIN_AGREEMENT = 0.8


def structure(markdown: str, *, date_anywhere: bool = False) -> StructureResult:
    """Best-effort `Statement`, or a refusal with a reason. Never raises."""
    lines = text_lines(markdown)
    if not lines:
        return StructureResult(None, "no_text")

    period = _period(lines)
    default_year = int(period[1][:4]) if period else _document_year(lines)
    summary = _summary(lines)
    rows = _rows(lines, default_year, date_anywhere=date_anywhere)
    if not rows:
        return StructureResult(None, "no_dated_rows")

    agreement, chained_txns = _chain_score(rows, summary.get("beginning_balance"))
    if agreement >= MIN_CHAIN_AGREEMENT and chained_txns:
        transactions, chained = chained_txns, True
    else:
        transactions, chained = _sectioned(rows), False
    if not transactions:
        return StructureResult(
            None, "no_signable_rows", rows_seen=len(rows), chained=chained,
            notes=[f"chain_agreement={agreement:.2f}"],
        )

    if not period:
        dates = sorted(t.date for t in transactions)
        period = (dates[0], dates[-1])

    statement = Statement(
        bank=None,
        period_start=period[0],
        period_end=period[1],
        transactions=sorted(transactions, key=lambda t: t.date),
        **{key: value for key, value in summary.items()},
    )
    if statement.ending_balance is None and chained and transactions[-1].running_balance is not None:
        statement.ending_balance = transactions[-1].running_balance
    return StructureResult(
        statement,
        "structured",
        rows_seen=len(rows),
        rows_used=len(transactions),
        chained=chained,
        notes=[f"chain_agreement={agreement:.2f}"],
    )
