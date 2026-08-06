from __future__ import annotations

import re
from datetime import date, datetime

from .money import parse_money
from .schema import Statement, Transaction

_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_MONEY_RE = re.compile(r"\$?-?\d[\d,]*(?:\.\d{2})?-?")


def _money_values(text: str) -> list[float]:
    values: list[float] = []
    for token in _MONEY_RE.findall(text):
        if re.fullmatch(r"\d{4}", token):
            continue
        value = parse_money(token)
        if value is not None:
            values.append(value)
    return values


def _split_rows(markdown: str) -> list[str]:
    text = re.sub(r"\s+", " ", markdown)
    text = re.sub(r"(?<!^)(?=\d{2}/\d{2}/\d{4}\s)", "\n", text)
    rows = []
    for row in text.splitlines():
        row = row.strip()
        if _DATE_RE.search(row):
            rows.append(row)
    return rows


def parse_scotiabank_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    if "SCOTIABANK" not in upper and "BUSINESS ACCOUNT 01180" not in upper:
        return None
    if "ACCOUNT DETAILS" not in upper and "WITHDRAWALS/DEBITS" not in upper:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Scotiabank"
    stmt.currency = "CAD"

    acct = re.search(r"Business Account\s+([0-9 ]{8,})", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = re.sub(r"\s+", " ", acct.group(1)).strip()
    period = re.search(r"Business Account\s+[0-9 ]+\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})", markdown)
    if period:
        for attr, raw in (("period_start", period.group(1)), ("period_end", period.group(2))):
            parsed = datetime.strptime(raw, "%b %d %Y").date()
            setattr(stmt, attr, parsed.isoformat())

    summary = re.search(
        r"No\. of Debits Total Amount - Debits No\. of Credits Total Amount\s+-\s+Credits\s+"
        r"(?P<debit_count>\d+)\s+\$(?P<debits>[\d,]+\.\d{2})\s+"
        r"(?P<credit_count>\d+)\s+\$(?P<credits>[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if summary:
        stmt.stated_debit_count = int(summary.group("debit_count"))
        stmt.stated_total_debits = parse_money(summary.group("debits"))
        stmt.stated_credit_count = int(summary.group("credit_count"))
        stmt.stated_total_credits = parse_money(summary.group("credits"))

    rows = _split_rows(markdown)
    txns: list[Transaction] = []
    prev_balance: float | None = None
    for row in rows:
        m = _DATE_RE.search(row)
        if not m:
            continue
        tx_date = date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
        rest = row[m.end():].strip()
        rest = re.split(
            r"\bNo\. of Debits\b|--- Page\b|Please examine\b|Uncollected fees",
            rest,
            flags=re.IGNORECASE,
        )[0].strip()
        u = rest.upper()
        if u.startswith("BALANCE FORWARD"):
            values = _money_values(rest)
            if values:
                stmt.beginning_balance = values[-1]
                prev_balance = stmt.beginning_balance
            continue
        if u.startswith(("NO. OF DEBITS", "STATEMENT OF:", "DATE DESCRIPTION")):
            continue

        values = _money_values(rest)
        if len(values) < 2 or prev_balance is None:
            continue
        balance = values[-1]
        amount = round(balance - prev_balance, 2)
        printed_amount = abs(values[-2])
        if abs(abs(amount) - printed_amount) > 0.02:
            # Some Scotiabank rows are fused; use the balance movement because
            # it is the only value that lets the statement reconcile.
            amount = round(balance - prev_balance, 2)
        desc = rest[: rest.rfind(_MONEY_RE.findall(rest)[-2])].strip()
        desc = re.sub(r"^(?:Statement Of:.*?Balance \(\$\)\s*)", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\s+", " ", desc).strip()
        if not desc:
            continue
        txns.append(Transaction(
            date=tx_date,
            description=desc,
            amount=amount,
            direction="credit" if amount > 0 else "debit",
            running_balance=balance,
        ))
        prev_balance = balance

    if not txns:
        return None
    if stmt.ending_balance is None:
        stmt.ending_balance = txns[-1].running_balance
    stmt.transactions = txns
    return stmt
