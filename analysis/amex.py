from __future__ import annotations

import re
from datetime import date

from .schema import Statement, Transaction
from .td_can import _parse_money


def _money(value: str | None) -> float | None:
    if value is None:
        return None
    return _parse_money(value.replace("$", ""))


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(r"Earned Period\s+(\d{2})/(\d{2})/(\d{4})\s+-\s+(\d{2})/(\d{2})/(\d{4})", markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    return date(int(sy), int(sm), int(sd)).isoformat(), date(int(ey), int(em), int(ed)).isoformat()


def _amount_after(markdown: str, label: str) -> float | None:
    m = re.search(rf"{label}\s+(?:as of\s+\d{{2}}/\d{{2}}/\d{{4}}\s+)?(-?\$?[\d,]+\.\d{{2}})", markdown, re.IGNORECASE)
    return _money(m.group(1)) if m else None


def _days(markdown: str) -> int | None:
    m = re.search(r"Days in Statement Period\s+(\d+)", markdown, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _account(markdown: str) -> str | None:
    m = re.search(r"Account Ending:\s*(\*\d+)", markdown, re.IGNORECASE)
    return m.group(1) if m else None


def _account_name(markdown: str) -> str | None:
    m = re.search(r"Account Name:\s*([^\n\r]+)", markdown, re.IGNORECASE)
    return m.group(1).strip() if m else "Business Checking"


def _parse_transactions(markdown: str) -> list[Transaction]:
    lines = [line.strip() for line in markdown.splitlines()]
    txns: list[Transaction] = []
    i = 0
    date_re = re.compile(r"^(\d{2})/(\d{2})/(\d{4})\s+(.+)$")
    amount_re = re.compile(r"^(-?\$[\d,]+\.\d{2})\s+(-?\$[\d,]+\.\d{2})$")
    while i < len(lines):
        m = date_re.match(lines[i])
        if not m:
            i += 1
            continue
        month, day, year, title = m.groups()
        title = title.strip()
        if title.lower().startswith(("beginning balance", "ending balance")):
            i += 1
            continue
        if i + 1 >= len(lines):
            i += 1
            continue
        amount_match = amount_re.match(lines[i + 1])
        if not amount_match:
            i += 1
            continue
        amount = _money(amount_match.group(1))
        balance = _money(amount_match.group(2))
        if amount is None or balance is None:
            i += 2
            continue
        desc_parts = [title]
        j = i + 2
        while j < len(lines):
            if date_re.match(lines[j]):
                break
            if lines[j].startswith("--- Page") or "Continued on next page" in lines[j]:
                break
            if "Accounts offered by American Express" in lines[j]:
                break
            if lines[j] and not lines[j].startswith(("p. ", "Statement Date:", "Date Description")):
                desc_parts.append(lines[j])
            j += 1
        txns.append(Transaction(
            date=date(int(year), int(month), int(day)).isoformat(),
            description=re.sub(r"\s+", " ", " ".join(desc_parts)).strip(),
            amount=round(amount, 2),
            direction="credit" if amount >= 0 else "debit",
            running_balance=round(balance, 2),
        ))
        i = j
    return txns


def parse_amex_statement(markdown: str) -> Statement | None:
    if "americanexpress.com/businesscheckinghome" not in markdown or "Business Checking Account Statement" not in markdown:
        return None
    period = _period(markdown)
    if period is None:
        return None
    beginning = _amount_after(markdown, "Beginning Balance")
    credits = _amount_after(markdown, "Total Credits This Period")
    debits = _amount_after(markdown, "Total Debits This Period")
    ending = _amount_after(markdown, "Ending Balance")
    if beginning is None or credits is None or debits is None or ending is None:
        return None
    txns = _parse_transactions(markdown)
    if not txns:
        return None
    return Statement(
        bank="American Express",
        account_name=_account_name(markdown),
        account_number=_account(markdown),
        period_start=period[0],
        period_end=period[1],
        beginning_balance=beginning,
        ending_balance=ending,
        days_in_period=_days(markdown),
        stated_total_credits=abs(credits),
        stated_total_debits=abs(debits),
        transactions=txns,
    )
