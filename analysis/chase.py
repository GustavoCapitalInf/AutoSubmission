from __future__ import annotations

import re
from datetime import date
from html import unescape

from .schema import Statement, Transaction

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub("", value))).strip()


def _rows(table: str) -> list[list[str]]:
    return [[_clean(cell) for cell in _CELL_RE.findall(row)] for row in _ROW_RE.findall(table)]


def _money(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    if not re.fullmatch(r"\(?-?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})?-?\)?", text):
        return None
    neg = text.startswith("(") or text.startswith("-") or text.endswith("-")
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        return None
    amount = float(cleaned)
    return -amount if neg else amount


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+through\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
    )
    if not m:
        return None
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    }
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), months[sm], int(sd)).isoformat(),
        date(int(ey), months[em], int(ed)).isoformat(),
    )


def _iso(mmdd: str, year: int) -> str:
    month, day = [int(part) for part in mmdd.split("/", 1)]
    return date(year, month, day).isoformat()


def _tables_after(markdown: str, heading: str) -> list[str]:
    pattern = re.compile(
        rf"(?m)^\s*{re.escape(heading)}(?: \(continued\))?\s*$.*?(<table>.*?</table>)",
        re.IGNORECASE | re.DOTALL,
    )
    return [m.group(1) for m in pattern.finditer(markdown)]


def _parse_txn_table(table: str, *, year: int, sign: int) -> tuple[list[Transaction], list[tuple[str, str]]]:
    txns: list[Transaction] = []
    missing_amounts: list[tuple[str, str]] = []
    for cells in _rows(table):
        if len(cells) < 3:
            continue
        if cells[0].upper() == "DATE" or cells[0].lower().startswith("total"):
            continue
        if not re.fullmatch(r"\d{2}/\d{2}", cells[0]):
            continue
        amount_idx = next((idx for idx in range(len(cells) - 1, 1, -1) if _money(cells[idx]) is not None), None)
        if amount_idx is None:
            desc = " ".join(cells[1:]).strip()
            if desc:
                missing_amounts.append((_iso(cells[0], year), desc))
            continue
        amount = _money(cells[amount_idx])
        if amount is None:
            continue
        desc = " ".join(cells[1:amount_idx]).strip()
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=_iso(cells[0], year),
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns, missing_amounts


def _table_total(table: str, label: str) -> float | None:
    for cells in _rows(table):
        if len(cells) < 2:
            continue
        if label.lower() not in cells[0].lower():
            continue
        for cell in reversed(cells):
            amount = _money(cell)
            if amount is not None:
                return abs(amount)
    return None


def _parse_section(markdown: str, heading: str, *, total_label: str, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    missing_amounts: list[tuple[str, str]] = []
    stated_total = 0.0
    for table in _tables_after(markdown, heading):
        table_txns, table_missing = _parse_txn_table(table, year=year, sign=sign)
        txns.extend(table_txns)
        missing_amounts.extend(table_missing)
        total = _table_total(table, total_label)
        if total is not None:
            stated_total += total

    parsed_total = round(sum(abs(t.amount) for t in txns), 2)
    missing_total = round(stated_total - parsed_total, 2) if stated_total else 0.0
    if len(missing_amounts) == 1 and missing_total > 0:
        txn_date, desc = missing_amounts[0]
        signed = round(missing_total * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def parse_chase_statement(markdown: str) -> Statement | None:
    text = _IMG_RE.sub("", markdown)
    if "JPMorgan Chase Bank" not in text and "\nCHASE\n" not in text:
        return None
    if "CHECKING SUMMARY" not in text:
        return None

    period = _period(text)
    if period is None:
        return None
    period_start, period_end = period
    year = int(period_end[:4])

    stmt = Statement(bank="Chase", period_start=period_start, period_end=period_end)
    acct = re.search(r"Account Number:\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    name = re.search(r"CHECKING SUMMARY\s*\n([^\n<]+)", text, re.IGNORECASE)
    if name:
        stmt.account_name = name.group(1).strip()

    summary_match = re.search(r"CHECKING SUMMARY.*?(<table>.*?</table>)", text, re.IGNORECASE | re.DOTALL)
    if not summary_match:
        return None
    debit_total = 0.0
    debit_count = 0
    for cells in _rows(summary_match.group(1)):
        if len(cells) < 3:
            continue
        label = cells[0].lower()
        instances = re.sub(r"[^0-9]", "", cells[1])
        amount = _money(cells[2])
        if "beginning balance" in label:
            stmt.beginning_balance = amount
        elif "deposits and additions" in label:
            stmt.stated_credit_count = int(instances) if instances else None
            stmt.stated_total_credits = amount
        elif "atm" in label or "electronic withdrawals" in label or "fees" in label:
            if amount is not None:
                debit_total += abs(amount)
            if instances:
                debit_count += int(instances)
            if "fees" in label and amount is not None:
                stmt.stated_service_charge = abs(amount)
        elif "ending balance" in label:
            stmt.ending_balance = amount
    stmt.stated_total_debits = round(debit_total, 2) if debit_total else None
    stmt.stated_debit_count = debit_count or None

    txns: list[Transaction] = []
    txns.extend(_parse_section(
        text,
        "DEPOSITS AND ADDITIONS",
        total_label="Total Deposits and Additions",
        year=year,
        sign=1,
    ))
    txns.extend(_parse_section(
        text,
        "ATM & DEBIT CARD WITHDRAWALS",
        total_label="Total ATM & Debit Card Withdrawals",
        year=year,
        sign=-1,
    ))
    txns.extend(_parse_section(
        text,
        "ELECTRONIC WITHDRAWALS",
        total_label="Total Electronic Withdrawals",
        year=year,
        sign=-1,
    ))
    txns.extend(_parse_section(
        text,
        "FEES",
        total_label="Total Fees",
        year=year,
        sign=-1,
    ))

    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt
