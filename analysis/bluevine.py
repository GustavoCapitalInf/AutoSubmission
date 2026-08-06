from __future__ import annotations

import re
from datetime import datetime

from .date_tokens import iso_from_month_day_year
from .money import LEADING_MINUS, parse_amount
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, LEADING_MINUS)


def _iso(mmddyy: str) -> str:
    return iso_from_month_day_year(mmddyy, century="always")


def parse_bluevine_statement(markdown: str) -> Statement | None:
    if "Bluevine Inc." not in markdown or "Activity summary" not in markdown:
        return None
    period = re.search(
        r"Statement Period:\s+.+?\((\w+ \d{1,2}, \d{4}) - (\w+ \d{1,2}, \d{4})\)",
        markdown,
    )
    summary = re.search(
        r"Beginning Balance on \d{2}/\d{2}/\d{4}\s+\$([\d,]+\.\d{2})\s+"
        r"Deposits/credits\s+\$([\d,]+\.\d{2})\s+"
        r"Withdrawals/debits\s+\$(-?[\d,]+\.\d{2})\s+"
        r"Ending balance on \d{2}/\d{2}/\d{4}\s+\$([\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if not period or not summary:
        return None
    period_start = datetime.strptime(period.group(1), "%B %d, %Y").date()
    period_end = datetime.strptime(period.group(2), "%B %d, %Y").date()
    beginning, credits, debits, ending = [_money(part) for part in summary.groups()]
    if None in (beginning, credits, debits, ending):
        return None

    stmt = Statement(
        bank="Bluevine",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        days_in_period=(period_end - period_start).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=abs(debits or 0.0),
    )
    acct = re.search(r"Account Number:\s*([0-9]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1)

    txns: list[Transaction] = []
    for m in re.finditer(r"(?m)^(\d{2}/\d{2}/\d{2})\s+(.+?)\s+\$(-?[\d,]+\.\d{2})\s*$", markdown):
        amount = _money(m.group(3))
        if amount is None:
            return None
        txns.append(
            Transaction(
                date=_iso(m.group(1)),
                description=re.sub(r"\s+", " ", m.group(2)).strip(),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
            )
        )
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - (credits or 0.0)) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - abs(debits or 0.0)) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
