from __future__ import annotations

import re
from datetime import date

from .money import STRICT_EITHER_MINUS_OR_PLUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_EITHER_MINUS_OR_PLUS)


def _clean_description(desc: str) -> str:
    desc = re.sub(r"--- Page \d+ ---.*?Your Detailed Statement Date Transaction Description Amount \(\$\) Total Balance \(\$\)", " ", desc)
    desc = re.sub(r"\b[01]{16,}\b", " ", desc)
    return re.sub(r"\s+", " ", desc).strip()


DETECTION_MARKERS = (
    required("domain", lambda t: "secumd.org" in t.lower()),
    required("product", lambda t: "Free Business Checking" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_secu_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = re.search(
        r"Statement Period:\s+From:\s+(\d{2})/(\d{2})/(\d{4})\s+To:\s+(\d{2})/(\d{2})/(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    summary = re.search(
        r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+"
        r"([\d,]+\.\d{2})\s+[\d,]+\.\d{2}\s+Free Business Checking\s+\((\d+)\)",
        markdown,
        re.IGNORECASE,
    )
    detail = re.search(
        r"Date Transaction Description Amount \(\$\) Total Balance \(\$\)\s+"
        r"Free Business Checking\s+\((\d+)\)(?P<body>.*?)(?:General Statement policies|--- Page 4)",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not period or not summary or not detail:
        return None

    sm, sd, sy, em, ed, ey = [int(part) for part in period.groups()]
    beginning, credits, debits, interest, ending, account = summary.groups()
    beginning_balance = _money(beginning)
    total_credits = _money(credits)
    total_debits = _money(debits)
    interest_paid = _money(interest)
    ending_balance = _money(ending)
    if None in {beginning_balance, total_credits, total_debits, interest_paid, ending_balance}:
        return None
    if detail.group(1) != account:
        return None

    txns: list[Transaction] = []
    body = re.sub(r"\s+", " ", detail.group("body"))
    for part in re.split(r"(?=\d{2}/\d{2}\s+[+-])", body):
        m = re.match(
            r"(\d{2})/(\d{2})\s+([+-][\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(.+?)"
            r"(?=\s+\d{2}/\d{2}\s+[+-]|\s+\d{2}/\d{2}\s+[\d,]+\.\d{2}\s+Ending Balance|$)",
            part,
        )
        if not m:
            continue
        month, day, amount_raw, balance_raw, desc = m.groups()
        amount = _money(amount_raw)
        balance = _money(balance_raw)
        if amount is None or balance is None:
            return None
        txns.append(
            Transaction(
                date=date(int(sy), int(month), int(day)).isoformat(),
                description=_clean_description(desc),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
                running_balance=balance,
            )
        )

    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - (total_credits or 0.0)) > 0.01:
        return None
    if abs(-sum(t.amount for t in txns if t.amount < 0) - (total_debits or 0.0)) > 0.01:
        return None
    if abs((txns[-1].running_balance or 0.0) - (ending_balance or 0.0)) > 0.01:
        return None

    stmt = Statement(
        bank="SECU Maryland",
        account_name="Free Business Checking",
        account_number=account,
        period_start=date(sy, sm, sd).isoformat(),
        period_end=date(ey, em, ed).isoformat(),
        days_in_period=(date(ey, em, ed) - date(sy, sm, sd)).days + 1,
        beginning_balance=beginning_balance,
        ending_balance=ending_balance,
        stated_total_credits=total_credits,
        stated_total_debits=total_debits,
        stated_interest_paid=interest_paid,
        transactions=txns,
    )
    return stmt
