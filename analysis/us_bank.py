from __future__ import annotations

import re
from datetime import date

from .money import EITHER_MINUS_SPACED, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
_DATE_RE = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
_MONEY_RE = r"\$?\s*[\d,]+\.\d{2}-?"


def _money(value: str | None) -> float | None:
    return parse_amount(value, EITHER_MINUS_SPACED)


def _iso(month_day: str, year: int) -> str:
    month, day = month_day.split()
    return date(year, _MONTHS[month], int(day)).isoformat()


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"(?P<start_month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(?P<start_day>\d{1,2}),\s+(?P<start_year>\d{4})\s+through\s+"
        r"(?P<end_month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(?P<end_day>\d{1,2}),\s+(?P<end_year>\d{4})",
        markdown,
    )
    if not m:
        return None
    start = date(int(m.group("start_year")), _MONTHS[m.group("start_month")], int(m.group("start_day")))
    end = date(int(m.group("end_year")), _MONTHS[m.group("end_month")], int(m.group("end_day")))
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _summary(markdown: str) -> dict[str, float | int] | None:
    m = re.search(
        r"Beginning Balance on \w+ \d+\s+\$\s*([\d,]+\.\d{2}).*?"
        r"Ending Balance on\s+\w+ \d+,\s+\d{4}\s+\$\s*([\d,]+\.\d{2})",
        markdown,
        re.DOTALL,
    )
    days = re.search(r"Number of Days in Statement Period\s+(\d+)", markdown)
    other_deposits = re.search(r"Other Deposits\s+(\d+)\s+([\d,]+\.\d{2})", markdown)
    other_withdrawals = re.search(r"Other Withdrawals\s+(\d+)\s+([\d,]+\.\d{2})-", markdown)
    customer_deposits = re.search(r"Customer Deposits\s+(\d+)\s+([\d,]+\.\d{2})", markdown)
    interest = re.search(r"Interest Earned this Period\s+\$\s*([\d,]+\.\d{2})", markdown)
    if not m or not days or not other_deposits or not other_withdrawals:
        return None
    customer_count = int(customer_deposits.group(1)) if customer_deposits else 0
    customer_total = _money(customer_deposits.group(2)) if customer_deposits else 0.0
    return {
        "beginning": _money(m.group(1)) or 0.0,
        "ending": _money(m.group(2)) or 0.0,
        "days": int(days.group(1)),
        "credits": (customer_total or 0.0) + (_money(other_deposits.group(2)) or 0.0),
        "debits": abs(_money(other_withdrawals.group(2)) or 0.0),
        "credit_count": customer_count + int(other_deposits.group(1)),
        "debit_count": int(other_withdrawals.group(1)),
        "interest": _money(interest.group(1)) or 0.0,
    }


def _section_chunks(markdown: str, heading: str) -> list[str]:
    header_re = re.compile(
        re.escape(heading)
        + r"(?: \(continued\))?\s+(?:Date Description of Transaction Ref Number Amount|Number Date Ref Number Amount)\s+",
        re.IGNORECASE,
    )
    stops = [
        f"Total {heading}",
        "Products and services available",
        "--- Page",
        "Other Withdrawals",
        "Other Deposits",
        "Customer Deposits",
        "This page intentionally",
    ]
    chunks: list[str] = []
    for match in header_re.finditer(markdown):
        start = match.end()
        end = len(markdown)
        for stop in stops:
            if stop == heading:
                continue
            idx = markdown.find(stop, start)
            if idx != -1:
                end = min(end, idx)
        chunk = markdown[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _rows(text: str, *, year: int, sign: int) -> list[Transaction]:
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"\s+(?=" + _DATE_RE + r"\s+)", "\n", normalized)
    txns: list[Transaction] = []
    for raw in normalized.splitlines():
        m = re.match(r"^(" + _DATE_RE + r")\s+(.+)$", raw.strip())
        if not m:
            continue
        body = m.group(2)
        tokens = list(re.finditer(_MONEY_RE, body))
        if not tokens:
            return []
        amount_token = tokens[-1]
        amount = abs(_money(amount_token.group(0)) or 0.0) * sign
        description = body[: amount_token.start()].strip()
        txns.append(
            Transaction(
                date=_iso(m.group(1), year),
                description=re.sub(r"\s+", " ", description),
                amount=round(amount, 2),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return txns


DETECTION_MARKERS = (
    required("bank_name", lambda t: "U.S. Bank National Association" in t),
    required("section", lambda t: "Account Summary" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_us_bank_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None
    period_start, period_end, period_days = period
    stmt = Statement(
        bank="U.S. Bank",
        account_name="Platinum Business Money Market",
        period_start=period_start,
        period_end=period_end,
        days_in_period=int(summary.get("days") or period_days),
        beginning_balance=float(summary["beginning"]),
        ending_balance=float(summary["ending"]),
        stated_total_credits=float(summary["credits"]),
        stated_total_debits=float(summary["debits"]),
        stated_credit_count=int(summary["credit_count"]),
        stated_debit_count=int(summary["debit_count"]),
        stated_interest_paid=float(summary["interest"]),
    )
    acct = re.search(r"Account Number\s+([0-9 -]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1).strip()

    year = int(period_end[:4])
    txns: list[Transaction] = []
    for chunk in _section_chunks(markdown, "Customer Deposits"):
        txns.extend(_rows(chunk, year=year, sign=1))
    for chunk in _section_chunks(markdown, "Other Deposits"):
        txns.extend(_rows(chunk, year=year, sign=1))
    for chunk in _section_chunks(markdown, "Other Withdrawals"):
        txns.extend(_rows(chunk, year=year, sign=-1))

    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - stmt.stated_total_credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - stmt.stated_total_debits) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
