from __future__ import annotations

import re
from datetime import date

from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.startswith("-") or text.endswith("-")
    text = text.strip("-")
    if not re.fullmatch(r"\d+\.\d{2}", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def parse_midflorida_statement(markdown: str) -> Statement | None:
    if "midflorida.com" not in markdown.lower() or "Free Business Checking" not in markdown:
        return None

    summary = re.search(
        r"Free Business Checking\s+-\s+([X\d]+).*?"
        r"(\d{2}/\d{2}/\d{4})\s+Beginning Balance\s+(-?\$[\d,]+\.\d{2})\s+"
        r"(\d+)\s+Credit\(s\)\s+This Period\s+(\$[\d,]+\.\d{2})\s+"
        r"(\d+)\s+Debit\(s\)\s+This Period\s+(\$[\d,]+\.\d{2})\s+"
        r"(\d{2}/\d{2}/\d{4})\s+Ending Balance\s+(-?\$[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not summary:
        return None
    (
        account,
        start_raw,
        beginning_raw,
        credit_count,
        credits_raw,
        debit_count,
        debits_raw,
        end_raw,
        ending_raw,
    ) = summary.groups()

    activity = re.search(
        r"Account Activity(?P<body>.*?)(?:Checks Cleared|Overdraft and Returned Item Fees)",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not activity:
        return None

    beginning = _money(beginning_raw)
    ending = _money(ending_raw)
    credits = _money(credits_raw)
    debits = _money(debits_raw)
    if beginning is None or ending is None or credits is None or debits is None:
        return None

    txns: list[Transaction] = []
    prev_balance = beginning
    body = re.sub(r"\s+", " ", activity.group("body"))
    for part in re.split(r"(?=\d{2}/\d{2}/\d{4}\s+)", body):
        m = re.match(
            r"(\d{2})/(\d{2})/(\d{4})\s+(.+?)\s+(-?\$[\d,]+\.\d{2})\s+(-?\$[\d,]+\.\d{2})(?:\s|$)",
            part,
        )
        if not m:
            continue
        month, day, year, desc, amount_raw, balance_raw = m.groups()
        desc = re.sub(r"\s+", " ", desc).strip()
        if desc in {"Beginning Balance", "Ending Balance"}:
            continue
        amount = _money(amount_raw)
        balance = _money(balance_raw)
        if amount is None or balance is None:
            return None
        signed = amount if balance >= prev_balance else -abs(amount)
        if abs(round(prev_balance + signed, 2) - round(balance, 2)) > 0.01:
            return None
        txns.append(
            Transaction(
                date=date(int(year), int(month), int(day)).isoformat(),
                description=desc,
                amount=round(signed, 2),
                direction="credit" if signed >= 0 else "debit",
                running_balance=balance,
            )
        )
        prev_balance = balance

    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - credits) > 0.01:
        return None
    if abs(-sum(t.amount for t in txns if t.amount < 0) - debits) > 0.01:
        return None
    if abs((txns[-1].running_balance or 0.0) - ending) > 0.01:
        return None

    start_month, start_day, start_year = [int(part) for part in start_raw.split("/")]
    end_month, end_day, end_year = [int(part) for part in end_raw.split("/")]
    stmt = Statement(
        bank="MIDFLORIDA Credit Union",
        account_name="Free Business Checking",
        account_number=account,
        period_start=date(start_year, start_month, start_day).isoformat(),
        period_end=date(end_year, end_month, end_day).isoformat(),
        days_in_period=(date(end_year, end_month, end_day) - date(start_year, start_month, start_day)).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_credit_count=int(credit_count),
        stated_debit_count=int(debit_count),
        transactions=txns,
    )
    return stmt
