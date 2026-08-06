from __future__ import annotations

import re
from datetime import date

from .money import LEADING_MINUS_DROPPED, parse_amount
from .schema import Statement, Transaction

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
_FULL_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


def _money(value: str | None) -> float | None:
    return parse_amount(value, LEADING_MINUS_DROPPED)


def _statement_date(markdown: str) -> date | None:
    m = re.search(r"Statement date\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})", markdown)
    if not m:
        return None
    month, day, year = m.groups()
    return date(int(year), _FULL_MONTHS[month], int(day))


def _txn_date(month: str, day: str, statement_year: int) -> str:
    return date(statement_year, _MONTHS[month], int(day)).isoformat()


def _summary(markdown: str) -> dict[str, float | int] | None:
    beginning = re.search(r"Your balance forward on [A-Z][a-z]{2} \d{1,2}, \d{4}\s+\$([\d,]+\.\d{2})", markdown)
    debits = re.search(r"Debits to your account \((\d+) items\)\s+-\s+\$([\d,]+\.\d{2})", markdown)
    credits = re.search(r"Credits to your account \((\d+) items\)\s+\+\s+\$([\d,]+\.\d{2})", markdown)
    ending = re.search(r"Your closing balance on [A-Z][a-z]{2} \d{1,2}, \d{4}\s+=\s+\$([\d,]+\.\d{2})", markdown)
    if not (beginning and debits and credits and ending):
        return None
    return {
        "beginning": _money(beginning.group(1)) or 0.0,
        "debit_count": int(debits.group(1)),
        "debits": abs(_money(debits.group(2)) or 0.0),
        "credit_count": int(credits.group(1)),
        "credits": abs(_money(credits.group(2)) or 0.0),
        "ending": _money(ending.group(1)) or 0.0,
    }


def _transactions(markdown: str, *, statement_year: int, beginning_balance: float) -> list[Transaction]:
    row_re = re.compile(
        r"(?m)^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+"
        r"(.+?)\s+\$([\d,]+\.\d{2})\s+(-\s*)?([\d,]+\.\d{2})\s*$"
    )
    txns: list[Transaction] = []
    prev_balance = beginning_balance
    for m in row_re.finditer(markdown):
        month, day, desc, raw_amount, neg_balance, raw_balance = m.groups()
        if desc.strip().lower() in {"balance forward", "closing balance"}:
            continue
        balance = _money(("- " if neg_balance else "") + raw_balance)
        printed_amount = _money(raw_amount)
        if balance is None or printed_amount is None:
            continue
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - abs(printed_amount)) > 0.01:
            signed = printed_amount if _looks_like_credit(desc) else -abs(printed_amount)
        txns.append(Transaction(
            date=_txn_date(month, day, statement_year),
            description=re.sub(r"\s+", " ", desc).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=balance,
        ))
        prev_balance = balance
    return txns


def _looks_like_credit(description: str) -> bool:
    desc = description.upper()
    return any(token in desc for token in (
        "DIRECT DEPOSIT",
        "MOBILE DEPOSIT",
        "TRANSFER RECEIVED",
        "E-TRANSFER RECEIVED",
        "TRANSFER RETURNED",
        "TRANSFER CANCEL",
    ))


def parse_atb_statement(markdown: str) -> Statement | None:
    if "ATB Financial" not in markdown or "Deposit Account Statement" not in markdown:
        return None
    statement_date = _statement_date(markdown)
    summary = _summary(markdown)
    if statement_date is None or summary is None:
        return None

    period_start = date(statement_date.year, statement_date.month, 1).isoformat()
    period_end = statement_date.isoformat()
    stmt = Statement(
        bank="ATB Financial",
        account_name="Unlimited Business Banking",
        period_start=period_start,
        period_end=period_end,
        beginning_balance=summary["beginning"],
        ending_balance=summary["ending"],
        stated_total_credits=summary["credits"],
        stated_total_debits=summary["debits"],
        stated_credit_count=summary["credit_count"],
        stated_debit_count=summary["debit_count"],
    )
    acct = re.search(r"\n(\d{8,})\s+Transit #", markdown)
    if acct:
        stmt.account_number = acct.group(1)

    txns = _transactions(markdown, statement_year=statement_date.year, beginning_balance=float(summary["beginning"]))
    if not txns:
        return None
    stmt.transactions = txns
    return stmt
