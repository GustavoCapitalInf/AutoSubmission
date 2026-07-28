from __future__ import annotations

import re
from datetime import date
from html import unescape

from .schema import Statement, Transaction

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub("", value))).strip()


def _rows(markdown: str) -> list[list[str]]:
    return [[_clean(cell) for cell in _CELL_RE.findall(row)] for row in _ROW_RE.findall(markdown)]


def _money(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    neg = text.startswith("(") or text.endswith("-")
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        return None
    amount = float(cleaned)
    return -amount if neg else amount


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"ACCOUNT SUMMARY FOR PERIOD\s+([A-Z]+)\s+(\d{1,2}),\s+(\d{4})\s+-\s+([A-Z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    months = {
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
        "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
    }
    sm, sd, sy, em, ed, ey = m.groups()
    start = date(int(sy), months[sm.upper()], int(sd)).isoformat()
    end = date(int(ey), months[em.upper()], int(ed)).isoformat()
    return start, end


def _iso(mmdd: str, year: int) -> str:
    month, day = [int(part) for part in mmdd.split("/", 1)]
    return date(year, month, day).isoformat()


def parse_capital_one_statement(markdown: str) -> Statement | None:
    if "CAPITALONE" not in markdown.upper().replace(" ", ""):
        return None
    if "ACCOUNT SUMMARY FOR PERIOD" not in markdown.upper():
        return None

    period = _period(markdown)
    if period is None:
        return None
    period_start, period_end = period
    year = int(period_end[:4])

    stmt = Statement(
        bank="Capital One",
        account_name="Business Basic Checking",
        period_start=period_start,
        period_end=period_end,
    )

    acct = re.search(r"\bBusiness Basic Checking\s+([0-9]{6,})\b", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)

    rows = _rows(markdown)
    prev_balance = stmt.beginning_balance
    in_detail = False
    txns: list[Transaction] = []

    for cells in rows:
        if len(cells) == 2:
            label, raw = cells
            value = _money(raw)
            low = label.lower()
            if "previous balance" in low:
                stmt.beginning_balance = value
                prev_balance = value
            elif "deposits/credits" in low:
                count = re.search(r"\b(\d+)\b", label)
                stmt.stated_credit_count = int(count.group(1)) if count else stmt.stated_credit_count
                stmt.stated_total_credits = value
            elif "checks/debits" in low:
                count = re.search(r"\b(\d+)\b", label)
                stmt.stated_debit_count = int(count.group(1)) if count else stmt.stated_debit_count
                stmt.stated_total_debits = abs(value) if value is not None else None
            elif "service charge" in low:
                stmt.stated_service_charge = abs(value) if value is not None else None
            elif "ending balance" in low:
                stmt.ending_balance = value
            elif "number of days" in low and value is not None:
                stmt.days_in_period = int(abs(value))
            elif "average collected balance" in low:
                stmt.stated_average_balance = value
            continue

        if len(cells) >= 5 and [c.lower() for c in cells[:5]] == [
            "date", "description", "deposits/credits", "withdrawals/debits", "resulting balance",
        ]:
            in_detail = True
            continue
        if not in_detail or len(cells) < 5:
            continue
        if cells[0].lower() == "total":
            in_detail = False
            continue
        if not re.fullmatch(r"\d{2}/\d{2}", cells[0]):
            continue
        balance = _money(cells[4])
        if balance is None:
            continue
        printed_credit = _money(cells[2])
        printed_debit = _money(cells[3])
        if prev_balance is not None:
            amount = round(balance - prev_balance, 2)
        elif printed_credit is not None:
            amount = round(abs(printed_credit), 2)
        elif printed_debit is not None:
            amount = -round(abs(printed_debit), 2)
        else:
            continue
        txns.append(Transaction(
            date=_iso(cells[0], year),
            description=cells[1],
            amount=amount,
            direction="credit" if amount >= 0 else "debit",
            running_balance=balance,
        ))
        prev_balance = balance

    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt
