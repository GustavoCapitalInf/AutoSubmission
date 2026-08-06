from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day
from .money import PARENS_OR_LEADING_MINUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _money(value: str | None) -> float | None:
    return parse_amount(value, PARENS_OR_LEADING_MINUS)


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"Statement Period:\s+([A-Z][a-z]{2})\s+(\d{2})\s+(\d{4})-([A-Z][a-z]{2})\s+(\d{2})\s+(\d{4})",
        markdown,
    )
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), _MONTHS[sm], int(sd)).isoformat(),
        date(int(ey), _MONTHS[em], int(ed)).isoformat(),
    )


def _summary(markdown: str, stmt: Statement) -> Statement:
    text = re.sub(r"\s+", " ", markdown)
    fields = {
        "beginning_balance": r"Beginning Balance\s+([\d,]+\.\d{2})",
        "stated_average_balance": r"Average Collected Balance\s+([\d,]+\.\d{2})",
        "days_in_period": r"Days in Period\s+(\d+)",
        "ending_balance": r"Ending Balance\s+(-?[\d,]+\.\d{2})",
    }
    updates: dict[str, float | int] = {}
    for key, pattern in fields.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        updates[key] = int(m.group(1)) if key == "days_in_period" else (_money(m.group(1)) or 0.0)

    credits = 0.0
    debits = 0.0
    for label in ("Deposits", "Electronic Deposits", "Other Credits"):
        label_pattern = r"(?<!Electronic )\bDeposits\b" if label == "Deposits" else re.escape(label)
        m = re.search(rf"{label_pattern}\s+([\d,]+\.\d{{2}})", text, re.IGNORECASE)
        if m:
            credits += abs(_money(m.group(1)) or 0.0)
    for label in ("Checks Paid", "Electronic Payments", "Other Withdrawals", "Service Charges"):
        m = re.search(rf"\b{re.escape(label)}\s+([\d,]+\.\d{{2}})", text, re.IGNORECASE)
        if m:
            amount = abs(_money(m.group(1)) or 0.0)
            debits += amount
            if label == "Service Charges":
                updates["stated_service_charge"] = amount
    updates["stated_total_credits"] = round(credits, 2)
    updates["stated_total_debits"] = round(debits, 2)
    return stmt.model_copy(update=updates) if updates else stmt


def _section(markdown: str, heading: str) -> tuple[str, float | None]:
    heading_pattern = re.escape(heading)
    if heading == "Deposits":
        heading_pattern = r"(?<!Electronic )\bDeposits\b"
    pattern = re.compile(
        rf"{heading_pattern}\s+(?:POSTING DATE DESCRIPTION AMOUNT|No\. Checks:.*?DATE SERIAL NO\. AMOUNT.*?)"
        rf"(?P<body>.*?)Subtotal:\s+(?P<total>[\d,]+\.\d{{2}})",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(markdown)
    if not m:
        return "", None
    return m.group("body"), abs(_money(m.group("total")) or 0.0)


def _line_items(section_text: str, *, year: int, sign: int) -> list[Transaction]:
    expanded = re.sub(r"\s+(?=\d{2}/\d{2}\s+)", "\n", section_text)
    lines = [line.strip() for line in expanded.splitlines()]
    txns: list[Transaction] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        start = re.match(r"^(\d{2}/\d{2})\s+(.+)", line)
        if not start:
            idx += 1
            continue
        date_text = start.group(1)
        parts = [start.group(2)]
        idx += 1
        while idx < len(lines) and not re.match(r"^\d{2}/\d{2}\s+", lines[idx]) and not lines[idx].startswith("Subtotal:"):
            parts.append(lines[idx])
            idx += 1
        amount = _amount_from_parts(parts)
        if amount is None:
            continue
        desc_parts = _description_parts(parts, amount)
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=iso_from_month_day(date_text, year),
            description=re.sub(r"\s+", " ", " ".join(desc_parts)).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def _amount_from_parts(parts: list[str]) -> float | None:
    first_line_amounts = re.findall(r"\b\d[\d,]*\.\d{2}\b", parts[0])
    if first_line_amounts:
        return _money(first_line_amounts[-1])
    for part in parts[1:]:
        if re.fullmatch(r"\$?[\d,]+\.\d{2}", part.strip()):
            return _money(part)
    return None


def _description_parts(parts: list[str], amount: float) -> list[str]:
    amount_text = f"{abs(amount):,.2f}"
    out: list[str] = []
    removed = False
    for part in parts:
        if not removed:
            new = re.sub(rf"\$?{re.escape(amount_text)}\b", "", part, count=1).strip()
            if new != part:
                removed = True
            if new:
                out.append(new)
        else:
            out.append(part)
    return out


def _checks(section_text: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for mmdd, serial, amount in re.findall(r"(\d{2}/\d{2})\s+(\d+\*?)\s+([\d,]+\.\d{2})", section_text):
        txns.append(Transaction(
            date=iso_from_month_day(mmdd, year),
            description=f"Check {serial}",
            amount=round(-abs(_money(amount) or 0.0), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def _parse_section(markdown: str, heading: str, *, year: int, sign: int) -> tuple[list[Transaction], float | None]:
    body, total = _section(markdown, heading)
    if total is None:
        return [], None
    if heading == "Checks Paid":
        return _checks(body, year=year), total
    return _line_items(body, year=year, sign=sign), total


DETECTION_MARKERS = (
    required("bank_name", lambda t: "TD Bank, N.A." in t),
    required("title", lambda t: "STATEMENT OF ACCOUNT" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_td_us_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    if period is None:
        return None
    year = int(period[1][:4])
    stmt = Statement(bank="TD Bank", account_name="TD Business Simple Checking", period_start=period[0], period_end=period[1])
    acct = re.search(r"Primary Account #:\s*([0-9-]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1)
    stmt = _summary(markdown, stmt)
    if stmt.beginning_balance is None or stmt.ending_balance is None:
        return None

    all_txns: list[Transaction] = []
    section_specs = [
        ("Deposits", 1),
        ("Electronic Deposits", 1),
        ("Other Credits", 1),
        ("Checks Paid", -1),
        ("Electronic Payments", -1),
        ("Other Withdrawals", -1),
        ("Service Charges", -1),
    ]
    for heading, sign in section_specs:
        txns, total = _parse_section(markdown, heading, year=year, sign=sign)
        if total is None:
            continue
        if abs(sum(abs(t.amount) for t in txns) - total) > 0.02:
            return None
        all_txns.extend(txns)
    if not all_txns:
        return None
    stmt.transactions = all_txns
    return stmt
