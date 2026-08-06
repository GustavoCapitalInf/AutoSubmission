from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_from_month_day
from .money import LEADING_MINUS_PADDED, parse_amount
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, LEADING_MINUS_PADDED)


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"Last statement:\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+This statement:\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+Total days in statement period:\s+(\d+)",
        markdown,
    )
    if not m:
        return None
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    }
    lm, ld, ly, tm, td, ty, days = m.groups()
    start = date(int(ly), months[lm], int(ld)) + timedelta(days=1)
    end = date(int(ty), months[tm], int(td))
    return start.isoformat(), end.isoformat(), int(days)


def _iso(mmdd: str, year: int) -> str:
    return iso_from_month_day(mmdd, year, separator="-")


def _ending_totals(markdown: str) -> tuple[float, float, float] | None:
    m = re.search(
        r"Ending totals(?:\s+Ending totals){3}\s+"
        r"(\d[\d,]*\.\d{2}|\.\d{2})(?:\s+(?:\d[\d,]*\.\d{2}|\.\d{2})){3}\s+"
        r"(-?[\d,]+\.\d{2})(?:\s+-?[\d,]+\.\d{2}){3}\s+"
        r"\$([\d,]+\.\d{2})(?:\s+\$[\d,]+\.\d{2}){3}",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    credits = abs(_money(m.group(1)) or 0.0)
    debits = abs(_money(m.group(2)) or 0.0)
    ending = _money(m.group(3)) or 0.0
    return credits, debits, ending


def _transactions(markdown: str, *, year: int, beginning_balance: float) -> list[Transaction]:
    activity = re.search(r"DAILY ACTIVITY.*?(?=Ending totals)", markdown, re.IGNORECASE | re.DOTALL)
    if not activity:
        return []
    text = re.sub(r"\s+(?=\d{2}-\d{2}\s+'?\s*[A-Z])", "\n", activity.group(0))
    row_re = re.compile(r"(?m)^(\d{2}-\d{2})\s+'?\s*(.+?)\s+(-?[\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$")
    txns: list[Transaction] = []
    prev_balance = beginning_balance
    for m in row_re.finditer(text):
        mmdd, desc, raw_amount, raw_balance = m.groups()
        if "Beginning balance" in desc:
            continue
        amount = _money(raw_amount)
        balance = _money(raw_balance)
        if amount is None or balance is None:
            continue
        signed = round(balance - prev_balance, 2)
        if abs(signed - amount) > 0.01:
            signed = amount
        txns.append(Transaction(
            date=_iso(mmdd, year),
            description=re.sub(r"\s+", " ", desc).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=balance,
        ))
        prev_balance = balance
    return txns


def parse_b1_statement(markdown: str) -> Statement | None:
    if "B1Bank" not in markdown or "DAILY ACTIVITY" not in markdown:
        return None
    period = _period(markdown)
    totals = _ending_totals(markdown)
    beginning = re.search(r"\d{2}-\d{2}\s+Beginning balance\s+\$([\d,]+\.\d{2})", markdown)
    if period is None or totals is None or not beginning:
        return None
    period_start, period_end, days = period
    credits, debits, ending = totals
    stmt = Statement(
        bank="B1Bank",
        account_name="Essential Business Checking",
        period_start=period_start,
        period_end=period_end,
        days_in_period=days,
        beginning_balance=_money(beginning.group(1)),
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
    )
    acct = re.search(r"Account number\s+([X*0-9]+)", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    avg = re.search(r"Average balance\s+\$([\d,]+\.\d{2})", markdown, re.IGNORECASE)
    if avg:
        stmt.stated_average_balance = _money(avg.group(1))

    txns = _transactions(markdown, year=int(period_end[:4]), beginning_balance=stmt.beginning_balance or 0.0)
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - debits) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
