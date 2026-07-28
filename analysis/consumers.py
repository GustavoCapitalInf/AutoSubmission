from __future__ import annotations

import re
from datetime import date

from .schema import Statement, Transaction


_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _money(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    if not re.fullmatch(r"\d+\.\d{2}", text):
        return None
    return float(text)


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"Statement Period:\s*([A-Za-z]{3})\s+(\d{2}),\s+(\d{4})\s+to\s+([A-Za-z]{3})\s+(\d{2}),\s+(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    start_month = _MONTHS.get(sm.lower())
    end_month = _MONTHS.get(em.lower())
    if not start_month or not end_month:
        return None
    start = date(int(sy), start_month, int(sd))
    end = date(int(ey), end_month, int(ed))
    return start.isoformat(), end.isoformat(), end.year


def _primary_checking_section(markdown: str) -> str:
    flat = re.sub(r"\s+", " ", markdown)
    start = flat.find("BusinessPlus Checking (S70) - 0836327000")
    if start < 0:
        return ""
    end = flat.find("Account Fee Summary", start)
    return flat[start:end if end > start else len(flat)]


def parse_consumers_statement(markdown: str) -> Statement | None:
    if "ConsumersCU.org" not in markdown and "Consumers Credit Union" not in markdown:
        return None
    period = _period(markdown)
    section = _primary_checking_section(markdown)
    if period is None or not section:
        return None
    start, end, year = period

    summary = re.search(
        r"BusinessPlus Checking \(S70\) - (\d+).*?"
        r"Beginning Balance\s+\$([\d,]+\.\d{2})\s+"
        r"Total Check\(s\) & Debits \(-\)\s+-\s+\$([\d,]+\.\d{2})\s+"
        r"Ending Balance\s+\$([\d,]+\.\d{2})\s+"
        r"Total Deposit\(s\) \(\+\)\s+\+\s+\$([\d,]+\.\d{2})",
        section,
        re.IGNORECASE,
    )
    if not summary:
        return None
    account, beginning_raw, debits_raw, ending_raw, credits_raw = summary.groups()
    beginning = _money(beginning_raw)
    debits = _money(debits_raw)
    ending_balance = _money(ending_raw)
    credits = _money(credits_raw)
    if None in {beginning, debits, ending_balance, credits}:
        return None

    txns: list[Transaction] = []
    prev_balance = beginning
    for segment in re.split(r"(?=\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}\s+)", section):
        row = re.match(r"([A-Za-z]{3})\s+(\d{2})\s+(.+)", segment)
        if not row:
            continue
        month_name, day, rest = row.groups()
        if rest.startswith("Previous Balance"):
            continue
        amounts = re.findall(r"\$[\d,]+\.\d{2}", rest)
        if len(amounts) < 2:
            continue
        amount = _money(amounts[-2])
        balance = _money(amounts[-1])
        if amount is None or balance is None or prev_balance is None:
            return None
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - amount) > 0.01:
            return None
        desc = rest[:rest.rfind(amounts[-2])]
        desc = re.sub(r"\s+", " ", desc).strip()
        month = _MONTHS.get(month_name.lower())
        if not month:
            return None
        txn_year = year - 1 if month > int(end[5:7]) else year
        txns.append(
            Transaction(
                date=date(txn_year, month, int(day)).isoformat(),
                description=desc,
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=balance,
            )
        )
        prev_balance = balance

    if not txns:
        return None
    if abs(sum(tx.amount for tx in txns if tx.amount > 0) - (credits or 0.0)) > 0.01:
        return None
    if abs(-sum(tx.amount for tx in txns if tx.amount < 0) - (debits or 0.0)) > 0.01:
        return None
    if abs((txns[-1].running_balance or 0.0) - (ending_balance or 0.0)) > 0.01:
        return None

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    return Statement(
        bank="Consumers Credit Union",
        account_name="BusinessPlus Checking",
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning,
        ending_balance=ending_balance,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_nsf_count=0,
        transactions=txns,
    )
