from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .schema import Statement, StatementDailyBalance, Transaction

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
    value = value.replace("$", "").strip()
    if value.startswith("."):
        value = "0" + value
    return parse_money(value)


def _period(markdown: str) -> tuple[str, str] | None:
    text = re.sub(r"\s+", " ", markdown)
    m = re.search(
        r"Account Statement From:\s+([A-Za-z]+)\s+(\d{2}),\s+(\d{4})\s+To:\s+([A-Za-z]+)\s+(\d{2}),\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    start_month = _MONTHS.get(sm.lower())
    end_month = _MONTHS.get(em.lower())
    if not start_month or not end_month:
        return None
    return date(int(sy), start_month, int(sd)).isoformat(), date(int(ey), end_month, int(ed)).isoformat()


def _summary(markdown: str) -> tuple[float, float, float, float, float, float]:
    text = re.sub(r"\s+", " ", markdown)
    start = text.find("FlexiChecking")
    end = text.find("FlexInvestments", start)
    section = text[start:end if end > start else len(text)]
    beginning_m = re.search(r"Beginning Balance\s+\$?([\d,]+\.\d{2})", section, re.IGNORECASE)
    credits_m = re.search(r"(\d+)\s+Additions\s+\+\s+([\d,]+\.\d{2})", section, re.IGNORECASE)
    debits_m = re.search(r"(\d+)\s+Subtractions\s+-\s+([\d,]+\.\d{2})", section, re.IGNORECASE)
    misc_m = re.search(r"Miscellaneous debits and credits\s+\+\s+([\d,]+\.\d{2})", section, re.IGNORECASE)
    service_m = re.search(r"Service charges\s+-\s+([\d,]+\.\d{2})", section, re.IGNORECASE)
    ending_m = re.search(r"Ending Balance\s+\$?([\d,]+\.\d{2})", section, re.IGNORECASE)
    if not (beginning_m and credits_m and debits_m and service_m and ending_m):
        raise ValueError("Banco Popular summary not found")
    beginning = _money(beginning_m.group(1))
    credits = _money(credits_m.group(2))
    debits = _money(debits_m.group(2))
    misc = _money(misc_m.group(1) if misc_m else None) or 0.0
    service = _money(service_m.group(1))
    end = _money(ending_m.group(1))
    if beginning is None or credits is None or debits is None or service is None or end is None:
        raise ValueError("Banco Popular summary amount parse failed")
    return beginning, round(credits + misc, 2), debits, service, end, misc


def _account(markdown: str) -> str | None:
    m = re.search(r"Account Number\s+([\d-]+)", markdown, re.IGNORECASE)
    return m.group(1) if m else None


def _average_balance(markdown: str) -> float | None:
    m = re.search(r"Average balance during this cycle:\s+\$?([\d,]+\.\d{2})", markdown, re.IGNORECASE)
    return _money(m.group(1)) if m else None


def _daily_book_balances(
    markdown: str, period_start: str, period_end: str
) -> list[StatementDailyBalance]:
    """Parse Banco Popular's explicit Date/Book Balance history."""
    match = re.search(
        r"Daily Balance History(?P<body>.*?)Average balance during this cycle:",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []

    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    row_re = re.compile(
        r"(?<!\d)(\d{2})-(\d{2})\s+([\d,]+\.\d{2})(-?)\s+"
        r"[\d,]+\.\d{2}-?"
    )
    balances: list[StatementDailyBalance] = []
    for month_raw, day_raw, amount_raw, negative in row_re.findall(match.group("body")):
        month = int(month_raw)
        day = int(day_raw)
        candidates = []
        for year in range(start.year, end.year + 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if start <= candidate <= end:
                candidates.append(candidate)
        if len(candidates) != 1:
            continue
        amount = _money(amount_raw)
        if amount is None:
            continue
        balances.append(
            StatementDailyBalance(
                date=candidates[0].isoformat(),
                balance=round(-abs(amount) if negative else abs(amount), 2),
            )
        )
    return sorted(balances, key=lambda balance: balance.date)


def _detail_text(markdown: str) -> str:
    idx = markdown.lower().find("account detail")
    return markdown[idx:] if idx >= 0 else markdown


def _section(markdown: str, start: str, end: str) -> str:
    detail = _detail_text(markdown)
    m = re.search(start + r"(?P<body>.*?)" + end, detail, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group("body")
    if start == r"Additions":
        m = re.search(r"(?im)^\s*Additions\s*$\s*(?P<body>.*?)(?=^\s*Subtractions\s*$)", detail, re.DOTALL)
        return m.group("body") if m else ""
    if "Subtractions" in start:
        m = re.search(r"(?im)^\s*Subtractions\s*$\s*(?P<body>.*?)(?=^\s*Service Charges\s*$)", detail, re.DOTALL)
        return m.group("body") if m else ""
    if "Miscellaneous" in start:
        m = re.search(
            r"(?im)^\s*Miscellaneous debits and credits\s*$\s*(?P<body>.*?)(?=^\s*Service Charges\s*$)",
            detail,
            re.DOTALL,
        )
        return m.group("body") if m else ""
    return ""


def _row_strings(section: str) -> list[str]:
    section = re.sub(r"(Date Reference Description Amount)\s+(?=\d{2}-\d{2})", r"\1\n", section)
    rows: list[str] = []
    current: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        if (
            line.startswith("--- Page")
            or line.startswith("ADS")
            or line.startswith(("From:", "To:", "Page ", "Account Number"))
            or "continued" in line.lower()
            or line == "HORIZON HEALTH AND MANAGEMENT CONSULTING"
        ):
            continue
        if re.match(r"^\d{2}-\d{2}\s+", line):
            if current:
                rows.append(" ".join(current))
            current = [line]
        elif current:
            if re.match(r"^\d{2,3}\s+Total|^Total ", line):
                rows.append(" ".join(current))
                current = []
            else:
                current.append(line)
    if current:
        rows.append(" ".join(current))
    return rows


def _parse_rows(section: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for row in _row_strings(section):
        amounts = re.findall(r"(?:\d[\d,]*\.\d{2}|\.\d{2})", row)
        if not amounts:
            continue
        amount = _money(amounts[-1])
        if amount is None:
            continue
        if "*PAID EFT CHARGE" in row.upper():
            continue
        m = re.match(r"^(\d{2})-(\d{2})\s+(.+)$", row)
        if not m:
            continue
        month, day, desc = m.groups()
        amount_idx = desc.rfind(amounts[-1])
        if amount_idx >= 0:
            desc = (desc[:amount_idx] + " " + desc[amount_idx + len(amounts[-1]):]).strip()
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=date(year, int(month), int(day)).isoformat(),
            description=re.sub(r"\s+", " ", desc).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
        ))
    return txns


def _misc_transactions(markdown: str, *, year: int) -> list[Transaction]:
    section = _section(markdown, r"Miscellaneous debits and credits", r"Service Charges")
    txns: list[Transaction] = []
    for row in _row_strings(section):
        m = re.match(r"^(\d{2})-(\d{2})\s+(.+?)\s+([+-])\s*(?:\$)?([\d,]+\.\d{2}|\.\d{2})$", row)
        if not m:
            continue
        month, day, desc, sign_token, amount_raw = m.groups()
        amount = _money(amount_raw)
        if amount is None:
            continue
        signed = abs(amount) if sign_token == "+" else -abs(amount)
        txns.append(Transaction(
            date=date(year, int(month), int(day)).isoformat(),
            description=re.sub(r"\s+", " ", desc).strip(),
            amount=round(signed, 2),
            direction="credit" if signed >= 0 else "debit",
        ))
    return txns


def parse_banco_popular_statement(markdown: str) -> Statement | None:
    if "FLEXICUENTA DE NEGOCIOS" not in markdown or "Banco Popular" not in markdown and "TeleBanco Comercial" not in markdown:
        return None
    period = _period(markdown)
    if period is None:
        return None
    start, end = period
    year = int(end[:4])
    try:
        beginning, credits, debits, service_charge, ending, _misc = _summary(markdown)
    except ValueError:
        return None
    credit_section = _section(markdown, r"Additions", r"\nSubtractions\nOther debits")
    debit_section = _section(markdown, r"\nSubtractions\nOther debits", r"(?:\nMiscellaneous debits and credits|\nService Charges)")
    txns = _parse_rows(credit_section, year=year, sign=1)
    txns.extend(_parse_rows(debit_section, year=year, sign=-1))
    txns.extend(_misc_transactions(markdown, year=year))
    if service_charge:
        txns.append(Transaction(
            date=end,
            description="Service charges",
            amount=round(-service_charge, 2),
            direction="debit",
        ))
    if not txns:
        return None
    stmt = Statement(
        bank="Banco Popular",
        account_name="FlexiChecking",
        account_number=_account(markdown),
        period_start=start,
        period_end=end,
        days_in_period=(date.fromisoformat(end) - date.fromisoformat(start)).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_service_charge=service_charge,
        stated_average_balance=_average_balance(markdown),
        stated_daily_balances=_daily_book_balances(markdown, start, end),
        transactions=txns,
    )
    return stmt
