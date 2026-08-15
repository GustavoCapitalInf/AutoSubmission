from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day
from .money import EITHER_MINUS_PADDED, parse_amount, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, EITHER_MINUS_PADDED)


DETECTION_MARKERS = (
    required("domain", lambda t: "LINKBANK.COM" in t),
    required("section", lambda t: "Activity in Date Order" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_linkbank_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    number = r"[\d,]+\.\d{2}-?|\.\d{2}-?"
    summary = re.search(
        r"Account Number\s+([X0-9]+)\s+Statement Dates\s+(\d{1,2})/(\d{2})/(\d{2})\s+thru\s+(\d{1,2})/(\d{2})/(\d{2})\s+"
        r"Previous Balance\s+(" + number + r")\s+Days in the Statement Period\s+(\d+)\s+"
        r"(\d+)\s+Deposits/Credits\s+(" + number + r").*?"
        r"(\d+)\s+Checks/Debits\s+(" + number + r").*?"
        r"Service Charge\s+(" + number + r").*?"
        r"Current Balance\s+(" + number + r")",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not summary:
        return None
    (
        acct,
        sm,
        sd,
        sy,
        em,
        ed,
        ey,
        beginning,
        days,
        credit_count,
        credits,
        debit_count,
        debits,
        service_charge,
        ending,
    ) = summary.groups()
    start_year = 2000 + int(sy)
    end_year = 2000 + int(ey)
    stmt = Statement(
        bank="LINKBANK",
        account_name="Business Checking",
        account_number=acct,
        period_start=date(start_year, int(sm), int(sd)).isoformat(),
        period_end=date(end_year, int(em), int(ed)).isoformat(),
        days_in_period=int(days),
        beginning_balance=_money(beginning),
        ending_balance=_money(ending),
        stated_total_credits=_money(credits),
        stated_total_debits=_money(debits),
        stated_credit_count=int(credit_count),
        stated_debit_count=int(debit_count),
        stated_service_charge=abs(read_money(service_charge, _money) or 0.0),
    )
    average = re.search(r"Average Ledger\s+(" + number + r")", markdown, re.IGNORECASE)
    if average:
        stmt.stated_average_balance = _money(average.group(1))
    start = markdown.find("Activity in Date Order")
    end = markdown.find("Checks in Number Order", start)
    if start == -1 or end == -1 or stmt.beginning_balance is None:
        return None
    text = re.sub(r"\s+", " ", markdown[start:end])
    text = re.sub(r"\s+(?=\d{1,2}/\d{2}\s+)", "\n", text)
    number = r"(?:[\d,]+\.\d{2}|\.\d{2})-?"
    row_re = re.compile(r"^(\d{1,2}/\d{2})\s+(.+?)\s+(" + number + r")\s+(" + number + r")(?=\s|$)")

    txns: list[Transaction] = []
    prev_balance = stmt.beginning_balance
    for raw in text.splitlines():
        m = row_re.match(raw.strip())
        if not m:
            continue
        amount = _money(m.group(3))
        balance = _money(m.group(4))
        if amount is None or balance is None:
            return None
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - abs(amount)) > 0.02:
            return None
        txns.append(
            Transaction(
                date=iso_from_month_day(m.group(1), end_year),
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
    if abs((txns[-1].running_balance or 0.0) - (stmt.ending_balance or 0.0)) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
