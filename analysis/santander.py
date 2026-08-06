from __future__ import annotations

import re
from datetime import date

from .money import PARENS_OR_LEADING_MINUS_OR_PLUS, parse_amount
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, PARENS_OR_LEADING_MINUS_OR_PLUS)


def _iso(mmdd: str, year: int) -> str:
    month, day = [int(part) for part in mmdd.split("-", 1)]
    return date(year, month, day).isoformat()


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"Statement Period\s+(\d{2})/(\d{2})/(\d{2})\s+TO\s+(\d{2})/(\d{2})/(\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    sm, sd, sy, em, ed, ey = [int(part) for part in m.groups()]
    start = date(2000 + sy, sm, sd)
    end = date(2000 + ey, em, ed)
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _summary(markdown: str) -> tuple[float, float, float, float, float] | None:
    m = re.search(
        r"Beginning Balance\s+(-?\$?[\d,]+\.\d{2})\s+"
        r"Ending Balance\s+(-?\$?[\d,]+\.\d{2})\s+"
        r"Deposits/Credits\s+\+?\$?([\d,]+\.\d{2})\s+"
        r"Average Daily Balance\s+\$?([\d,]+\.\d{2})\s+"
        r"Withdrawals/Debits\s+-?\$?([\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    beginning, ending, credits, average, debits = [_money(part) for part in m.groups()]
    if None in (beginning, ending, credits, average, debits):
        return None
    return beginning or 0.0, ending or 0.0, credits or 0.0, average or 0.0, debits or 0.0


def _activity_text(markdown: str) -> str | None:
    m = re.search(
        r"Account Activity\s*(.*?)(?:Please contact us immediately|--- Page \d+ ---\s*\d{6,}\s+#)",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    text = m.group(1)
    text = re.sub(r"Santander Bank, N\.A\..*?Page \d+ of \d+", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"Page \d+ of \d+\s+\d+", " ", text)
    text = re.sub(
        r"Account Activity \(Cont\. for Acct# [^)]+\)\s*Date Description Credits Debits Balance",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"Date Description Credits Debits Balance", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+(?=\d{2}-\d{2}\s+)", "\n", text)


def _transactions(markdown: str, *, year: int, beginning_balance: float) -> list[Transaction]:
    text = _activity_text(markdown)
    if not text:
        return []

    rows: list[tuple[str, str]] = []
    current: list[str] | None = None
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        m = re.match(r"^(\d{2}-\d{2})\s+(.+)$", line)
        if m:
            if current:
                rows.append((current[0], current[1]))
            current = [m.group(1), m.group(2)]
        elif current:
            current[1] += " " + line
    if current:
        rows.append((current[0], current[1]))

    txns: list[Transaction] = []
    prev_balance = beginning_balance
    for mmdd, body in rows:
        if body.startswith(("Beginning Balance", "Ending Balance")):
            continue
        money_tokens = list(re.finditer(r"-?\$?[\d,]+\.\d{2}", body))
        if len(money_tokens) < 2:
            return []
        amount = _money(money_tokens[-2].group(0))
        balance = _money(money_tokens[-1].group(0))
        if amount is None or balance is None:
            return []
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - abs(amount)) > 0.02:
            return []
        description = body[: money_tokens[-2].start()].strip()
        txns.append(
            Transaction(
                date=_iso(mmdd, year),
                description=re.sub(r"\s+", " ", description),
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=balance,
            )
        )
        prev_balance = balance
    return txns


def parse_santander_statement(markdown: str) -> Statement | None:
    if "Santander" not in markdown or "Account Activity" not in markdown:
        return None
    period = _period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None
    period_start, period_end, days = period
    beginning, ending, credits, average, debits = summary
    stmt = Statement(
        bank="Santander Bank",
        account_name="Business Banking Analyzed Checking",
        period_start=period_start,
        period_end=period_end,
        days_in_period=days,
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_average_balance=average,
    )
    acct = re.search(r"Primary Account #:\s*([0-9]+)", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)

    txns = _transactions(markdown, year=int(period_end[:4]), beginning_balance=beginning)
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - debits) > 0.02:
        return None
    if abs((txns[-1].running_balance or 0.0) - ending) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
