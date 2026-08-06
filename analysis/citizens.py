from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .schema import Statement, Transaction
from .tables import section_between

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _money(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace("$", "")
    if value.startswith("."):
        value = "0" + value
    return parse_money(value)


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"Beginning\s+([A-Za-z]+)\s+(\d{2}),\s+(\d{4})\s+through\s+([A-Za-z]+)\s+(\d{2}),\s+(\d{4})",
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
    return (
        date(int(sy), start_month, int(sd)).isoformat(),
        date(int(ey), end_month, int(ed)).isoformat(),
    )


def _summary(markdown: str) -> tuple[float, float, float, float] | None:
    m = re.search(
        r"Balance Calculation\s+Previous Balance\s+(-?[\d,]+\.?\d{0,2}|-\.\d{2}|\.\d{2})\s+"
        r"Checks\s+-\s+([\d,]+\.?\d{0,2}|\.\d{2})\s+"
        r"Debits\s+-\s+([\d,]+\.?\d{0,2}|\.\d{2})\s+"
        r"Deposits\s+&\s+Credit\s+\+\s+([\d,]+\.?\d{0,2}|\.\d{2})\s+"
        r"Current Balance\s+=\s+(-?[\d,]+\.?\d{0,2}|-\.\d{2}|\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    beginning, checks, debits, credits, ending = (_money(value) for value in m.groups())
    if None in {beginning, checks, debits, credits, ending}:
        return None
    return beginning, checks + debits, credits, ending  # type: ignore[operator,return-value]


def _average_balance(markdown: str) -> float | None:
    m = re.search(
        r"average daily checking balance used to qualify this statement period is:\s+\$?([\d,]+)",
        markdown,
        re.IGNORECASE,
    )
    return _money(m.group(1)) if m else None


def _account(markdown: str) -> str | None:
    m = re.search(r"Business Advisor Checking for\s+([X\d-]+)", markdown, re.IGNORECASE)
    return m.group(1) if m else None


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def _parse_inline_rows(text: str, *, year: int, sign: int) -> list[Transaction]:
    compact = re.sub(r"\s+", " ", text)
    compact = re.sub(r"^(?:Total (?:Debits|Deposits & Credits)|Other Debits(?: \(Continued\))?|Date Amount Description|\+\s*[\d,]+\.\d{2}|-\s*[\d,]+\.\d{2})\s+", "", compact, flags=re.IGNORECASE)
    rows = re.split(r"\s+(?=\d{2}/\d{2}\s+(?:\d[\d,]*\.\d{2}|\.\d{2})\s)", compact)
    txns: list[Transaction] = []
    for row in rows:
        m = re.match(r"^(\d{2})/(\d{2})\s+(\d[\d,]*\.\d{2}|\.\d{2})\s+(.+?)\s*$", row.strip())
        if not m:
            continue
        month, day, amount_raw, desc = m.groups()
        amount = _money(amount_raw)
        if amount is None:
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=date(year, int(month), int(day)).isoformat(),
            description=re.sub(r"\s+", " ", desc).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
        ))
    return txns


def _parse_checks(markdown: str, *, year: int) -> list[Transaction]:
    section = section_between(markdown, r"Checks .*?Total Checks\s+", r"(?:Debits|Deposits & Credits|Current Balance|Please See)")
    txns: list[Transaction] = []
    for check_no, amount_raw, month, day in re.findall(r"(\d+\*?)\s+([\d,]+\.\d{2}|\.\d{2})\s+(\d{2})/(\d{2})", section):
        amount = _money(amount_raw)
        if amount is None:
            continue
        txns.append(Transaction(
            date=date(year, int(month), int(day)).isoformat(),
            description=f"Check {check_no}",
            amount=-abs(amount),
            direction="debit",
        ))
    return txns


def parse_citizens_statement(markdown: str) -> Statement | None:
    if "citizensbank.com" not in markdown.lower() or "Business Advisor Checking" not in markdown:
        return None
    period = _period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None
    start, end = period
    year = int(end[:4])
    beginning, debits, credits, ending = summary
    stmt = Statement(
        bank="Citizens Bank",
        account_name="Business Advisor Checking",
        account_number=_account(markdown),
        period_start=start,
        period_end=end,
        days_in_period=_days(start, end),
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_average_balance=_average_balance(markdown),
    )
    debits_text = section_between(markdown, r"Other Debits\s+", r"Deposits & Credits")
    credits_text = section_between(markdown, r"Deposits & Credits.*?Date Amount Description\s+", r"Current Balance\s+Daily Balance")
    txns = _parse_checks(markdown, year=year)
    txns.extend(_parse_inline_rows(debits_text, year=year, sign=-1))
    txns.extend(_parse_inline_rows(credits_text, year=year, sign=1))
    if not txns:
        return None
    stmt.transactions = txns
    return stmt
