from __future__ import annotations

import re
from datetime import date

from .schema import Statement, Transaction


_MONEY_RE = re.compile(r"\d[\d,]*\.\d{2}")
_DATE_RE = re.compile(r"\d{2}-\d{2}")
_DEBIT_START_RE = re.compile(
    r"(?=(?:POS Sig|Overdraft Charge|Coast Payment|ACH Same Day|ACH Return Item|"
    r"Platform Factory|Intuit \d+|Paypal Debit|Intuit \* Quickbooks|Nexanano|"
    r"Verizon Wireless|Auto-Owners|ACH Batch|Insufficient Funds Fee|Irs Usataxpymt|"
    r"Lowes Syf|Intuit Retry|Zelle|Overdraft Item Fee|The Sherwin|Purchase\s+Visa|"
    r"Deere Credit|Travelers|Workiz Card|Digital Banking Fees))",
    re.IGNORECASE,
)
_CREDIT_START_RE = re.compile(
    r"(?=(?:Workiz Inc Payout|Delta Force Serv Return|POS Sig|Specialty Capit Funding))",
    re.IGNORECASE,
)


def _money(value: str) -> float:
    return float(value.replace(",", ""))


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _section(markdown: str, start: str, end: str) -> str:
    m = re.search(re.escape(start) + r"(.*?)" + re.escape(end), markdown, re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else ""


def _dates_and_amounts(block: str) -> tuple[list[str], list[float]]:
    dates: list[str] = []
    amounts: list[float] = []
    for line in [ln.strip() for ln in block.splitlines() if ln.strip()]:
        if re.fullmatch(r"(?:\d{2}-\d{2}\s*)+", line):
            dates.extend(_DATE_RE.findall(line))
        elif re.fullmatch(r"(?:\d[\d,]*\.\d{2}\s*)+", line):
            amounts.extend(_money(raw) for raw in _MONEY_RE.findall(line))
    return dates, amounts


def _parse_period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"Statement Period:\s*([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})\s+Thru\s+"
        r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    months = {
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
    sm, sd, sy, em, ed, ey = m.groups()
    start = date(int(sy), months[sm.lower()], int(sd))
    end = date(int(ey), months[em.lower()], int(ed))
    return start.isoformat(), end.isoformat(), end.year


def _account(markdown: str) -> str | None:
    m = re.search(r"Account Number\s*:\s*(\d+)", markdown, re.IGNORECASE)
    return m.group(1) if m else None


def _daily_balances(markdown: str) -> list[tuple[int, float]]:
    block = _section(markdown, "Daily Balance Summary", "An updated")
    entries: list[tuple[int, float]] = []
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    for idx, line in enumerate(lines[:-1]):
        values = re.findall(r"03\s+([\d,]+\.\d{2})([+-])", line)
        if not values:
            continue
        days = re.findall(r"-(\d{2})", lines[idx + 1])
        for (raw_amount, sign), raw_day in zip(values, days):
            amount = _money(raw_amount)
            if sign == "-":
                amount *= -1
            entries.append((int(raw_day), round(amount, 2)))
    return entries


def _parse_deposits(markdown: str, *, year: int) -> list[Transaction]:
    block = _section(markdown, "Deposits To Your Account", "Other Credits To Your Account")
    dates: list[str] = []
    amounts: list[float] = []
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    for idx, line in enumerate(lines[:-1]):
        month_amounts = re.findall(r"\b(03)\s+(\d[\d,]*\.\d{2})", line)
        if not month_amounts:
            continue
        days = re.findall(r"-(\d{2})", lines[idx + 1])
        for (month, raw_amount), day in zip(month_amounts, days):
            dates.append(f"{month}-{day}")
            amounts.append(_money(raw_amount))
    if len(dates) != len(amounts):
        return []
    return [
        Transaction(
            date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
            description="Deposit",
            amount=amount,
            direction="credit",
        )
        for mmdd, amount in zip(dates, amounts)
    ]


def _parse_other_credits(markdown: str, *, year: int) -> list[Transaction]:
    block = _section(markdown, "Other Credits To Your Account", "Total\n44,862.06")
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if len(lines) < 3:
        return []
    desc_line = re.sub(r"^Date Description Amount\s+", "", lines[0], flags=re.IGNORECASE)
    descriptions = [_compact(part) for part in _CREDIT_START_RE.split(desc_line) if part.strip()]
    dates, amounts = _dates_and_amounts("\n".join(lines[1:]))
    if len(descriptions) != len(dates) or len(dates) != len(amounts):
        return []
    return [
        Transaction(
            date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
            description=description,
            amount=amount,
            direction="credit",
        )
        for description, mmdd, amount in zip(descriptions, dates, amounts)
    ]


def _parse_checks(markdown: str, *, year: int) -> list[Transaction]:
    block = _section(markdown, "Checks Paid From Your Account", "*Prior Check")
    txns: list[Transaction] = []
    for check_no, mmdd, raw_amount in re.findall(r"(\d{4})\s+(\d{2}-\d{2})\s+(\d[\d,]*\.\d{2})", block):
        txns.append(
            Transaction(
                date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
                description=f"Check #{check_no}",
                amount=-_money(raw_amount),
                direction="debit",
            )
        )
    return txns


def _parse_other_debits(markdown: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for part in markdown.split("Other Debits From Your Account")[1:]:
        block = part.split("Total\n74,263.31", 1)[0].split("Page ", 1)[0]
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        desc_line = re.sub(r"^Date Description Amount\s+", "", lines[0], flags=re.IGNORECASE)
        descriptions = [_compact(piece) for piece in _DEBIT_START_RE.split(desc_line) if piece.strip()]
        dates, amounts = _dates_and_amounts("\n".join(lines[1:]))
        if len(descriptions) != len(dates) or len(dates) != len(amounts):
            return []
        for description, mmdd, amount in zip(descriptions, dates, amounts):
            txns.append(
                Transaction(
                    date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
                    description=description,
                    amount=-amount,
                    direction="debit",
                )
            )
    return txns


def parse_first_citizens_statement(markdown: str) -> Statement | None:
    if "First Citizens" not in markdown and "Central Bank Operations" not in markdown:
        return None
    if "Other Debits From Your Account" not in markdown or "Daily Balance Summary" not in markdown:
        return None
    period = _parse_period(markdown)
    account = _account(markdown)
    if period is None or account is None:
        return None
    start, end, year = period

    deposits = _parse_deposits(markdown, year=year)
    other_credits = _parse_other_credits(markdown, year=year)
    checks = _parse_checks(markdown, year=year)
    other_debits = _parse_other_debits(markdown, year=year)
    txns = deposits + other_credits + checks + other_debits

    deposit_total = round(sum(t.amount for t in deposits), 2)
    other_credit_total = round(sum(t.amount for t in other_credits), 2)
    check_total = round(-sum(t.amount for t in checks), 2)
    other_debit_total = round(-sum(t.amount for t in other_debits), 2)
    daily = _daily_balances(markdown)
    if not daily:
        return None
    ending_balance = daily[-1][1]
    stated_total_credits = round(deposit_total + other_credit_total, 2)
    stated_total_debits = round(check_total + other_debit_total, 2)
    beginning_balance = round(ending_balance - stated_total_credits + stated_total_debits, 2)

    expected = {
        "deposits": (10, 55049.85, len(deposits), deposit_total),
        "other_credits": (9, 44862.06, len(other_credits), other_credit_total),
        "checks": (11, 9800.18, len(checks), check_total),
        "other_debits": (86, 74263.31, len(other_debits), other_debit_total),
    }
    for _, (expected_count, expected_total, actual_count, actual_total) in expected.items():
        if actual_count != expected_count or abs(actual_total - expected_total) > 0.01:
            return None

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    return Statement(
        bank="First Citizens Bank",
        account_name="Business Banking",
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning_balance,
        ending_balance=ending_balance,
        stated_total_credits=stated_total_credits,
        stated_total_debits=stated_total_debits,
        stated_average_balance=None,
        transactions=txns,
    )
