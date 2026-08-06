from __future__ import annotations

import re
from datetime import date

from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace


_MONEY_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?: \d{3})+|\d+)\.\d{2}(?!\d)")
_ROW_RE = re.compile(r"^\s*([A-Z]{3})\s+(\d{1,2})\s+([A-Z]{2,4})\s+(.*)")
_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def _money(value: str) -> float:
    return float(value.replace(" ", ""))


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"From\s+([A-Za-z]+)\s+(\d{1,2})\s+to\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    start_month, start_day, end_month, end_day, year = m.groups()
    y = int(year)
    start = date(y, months[start_month.lower()], int(start_day))
    end = date(y, months[end_month.lower()], int(end_day))
    return start.isoformat(), end.isoformat(), y


def _account_number(markdown: str) -> str | None:
    m = re.search(r"\b(SJ\s+\d{3}-\d{5}-\d)\b", markdown)
    return compact_whitespace(m.group(1)) if m else None


def _beginning_balance(markdown: str) -> float | None:
    m = re.search(r"Balance forward\s+([\d ]+\.\d{2})", markdown)
    return _money(m.group(1)) if m else None


def _transaction_blocks(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    current: list[str] | None = None
    for line in markdown.splitlines():
        if _ROW_RE.match(line):
            if current:
                rows.append(current)
            current = [line]
            continue
        if current is None:
            continue
        stripped = line.strip()
        if (
            stripped.startswith(("PCA", "SHR", "Notify", "--- Page"))
            or "STATEMENT OF ACCOUNT" in line
            or ("Page " in line and " of " in line)
        ):
            rows.append(current)
            current = None
            continue
        current.append(line)
    if current:
        rows.append(current)
    return rows


def _signed_amount(raw_amount: float, raw_balance: float, previous_balance: float) -> tuple[float, float] | None:
    for amount in (raw_amount, -raw_amount):
        for balance in (raw_balance, -raw_balance):
            if abs(round(previous_balance + amount, 2) - balance) <= 0.01:
                return round(amount, 2), round(balance, 2)
    return None


def _description(block_text: str, first_line: str, amount_token: str) -> str:
    m = _ROW_RE.match(first_line)
    desc = m.group(4) if m else first_line
    if len(block_text.splitlines()) > 1:
        desc = block_text[block_text.find(desc):]
    amount_idx = desc.rfind(amount_token)
    if amount_idx > 0:
        desc = desc[:amount_idx]
    return compact_whitespace(desc)


def _transactions(markdown: str, *, year: int, beginning_balance: float) -> list[Transaction] | None:
    txns: list[Transaction] = []
    previous = beginning_balance
    for block in _transaction_blocks(markdown):
        first = block[0]
        row = _ROW_RE.match(first)
        if not row:
            return None
        month_name, day, code, _ = row.groups()
        month = _MONTHS.get(month_name.upper())
        if month is None:
            return None
        text = "\n".join(block)
        money = _MONEY_RE.findall(text)
        if len(money) < 2:
            return None
        raw_amount = _money(money[-2])
        raw_balance = _money(money[-1])
        signed = _signed_amount(raw_amount, raw_balance, previous)
        if signed is None:
            return None
        amount, balance = signed
        desc = _description(text, first, money[-2])
        txns.append(
            Transaction(
                date=date(year, month, int(day)).isoformat(),
                description=f"{code} {desc}".strip(),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
                running_balance=balance,
            )
        )
        previous = balance
    return txns


DETECTION_MARKERS = (
    required("bank_name", lambda t: "CAISSE DESJARDINS" in t),
    required("product", lambda t: "DESJARDINS CORPORATE BUILD-UP ACCOUNT" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_desjardins_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    account = _account_number(markdown)
    beginning = _beginning_balance(markdown)
    if period is None or account is None or beginning is None:
        return None
    start, end, year = period
    txns = _transactions(markdown, year=year, beginning_balance=beginning)
    if not txns:
        return None
    ending = txns[-1].running_balance
    if ending is None:
        return None
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    return Statement(
        bank="Desjardins",
        account_name="USD Desjardins Corporate Build-Up Account",
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        currency="USD",
        transactions=txns,
    )
