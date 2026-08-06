from __future__ import annotations

import re
from datetime import datetime

from .money import STRICT_LEADING_SIGN, parse_amount
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_LEADING_SIGN)


def parse_demo_national_statement(markdown: str) -> Statement | None:
    if "SAMPLE BUSINESS BANK STATEMENT" not in markdown or "Bank: Demo National Bank" not in markdown:
        return None
    period = re.search(r"Statement Period:\s+([A-Za-z]+ \d{1,2}, \d{4}) - ([A-Za-z]+ \d{1,2}, \d{4})", markdown)
    summary = re.search(
        r"Beginning Balance\s+\$([\d,]+\.\d{2}).*?"
        r"Deposits / Credits\s+(\d+)\s+\$([\d,]+\.\d{2}).*?"
        r"Checks / Debits\s+(\d+)\s+\$([\d,]+\.\d{2}).*?"
        r"Ending Balance\s+\$([\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not period or not summary:
        return None
    period_start = datetime.strptime(period.group(1), "%B %d, %Y").date()
    period_end = datetime.strptime(period.group(2), "%B %d, %Y").date()
    beginning, credit_count, credits, debit_count, debits, ending = summary.groups()
    stmt = Statement(
        bank="Demo National Bank",
        account_name="Business Checking",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        days_in_period=(period_end - period_start).days + 1,
        beginning_balance=_money(beginning),
        ending_balance=_money(ending),
        stated_total_credits=_money(credits),
        stated_total_debits=_money(debits),
        stated_credit_count=int(credit_count),
        stated_debit_count=int(debit_count),
    )
    acct = re.search(r"Account Number:\s*([X0-9]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1)

    activity = re.search(r"Checking Account Activity\s+Date Description.*?Balance\s+(.*?)(?:Savings Account Activity|End of statement)", markdown, re.IGNORECASE | re.DOTALL)
    if not activity or stmt.beginning_balance is None:
        return None
    txns: list[Transaction] = []
    prev_balance = stmt.beginning_balance
    for m in re.finditer(r"(?m)^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s*$", activity.group(1)):
        amount = _money(m.group(3))
        balance = _money(m.group(4))
        if amount is None or balance is None:
            return None
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - amount) > 0.02:
            return None
        txns.append(
            Transaction(
                date=datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat(),
                description=re.sub(r"\s+", " ", m.group(2)).strip(),
                amount=signed,
                direction="credit" if signed > 0 else "debit",
                running_balance=balance,
            )
        )
        prev_balance = balance
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - (stmt.stated_total_credits or 0.0)) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - (stmt.stated_total_debits or 0.0)) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
