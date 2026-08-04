from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .schema import Statement, Transaction


_ROW_RE = re.compile(
    r"^(?P<label>.*?)\s+"
    r"(?P<date>[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+"
    r"(?P<status>Settled|Returned)\s+"
    r"(?P<amount>[+-]\$[\d,]+\.\d{2})\s+"
    r"(?P<balance>-?\$[\d,]+\.\d{2})$"
)


def _money(value: str) -> Decimal:
    try:
        return Decimal(value.replace("$", "").replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(value) from exc


def _description(label: str, status: str, amount: Decimal) -> str:
    label = re.sub(r"\s+", " ", label).strip()
    prefix = "Returned " if status == "Returned" else ""

    transfer = re.match(r"^(.*?)\s+Transfer\s+(From|To)$", label, re.IGNORECASE)
    if transfer:
        account, direction = transfer.groups()
        return f"{prefix}Internal Account Transfer {direction.title()}: {account.strip()}"

    if label.upper().endswith(" ACH PULL"):
        entity = label[:-9].strip()
        return f"{prefix}ACH Pull: {entity}"
    if label.upper().endswith(" ACH"):
        entity = label[:-4].strip()
        direction = "Credit" if amount > 0 else "Debit"
        if amount > 0 and re.fullmatch(r"INTUIT\s+\d{6,}", entity, re.IGNORECASE):
            entity = f"Intuit Payments {entity.split()[-1]}"
        return f"{prefix}ACH {direction}: {entity}"
    if label.upper().endswith(" VISA"):
        entity = label[:-5].strip()
        kind = "Debit Card Credit" if amount > 0 else "Debit Card Purchase"
        return f"{prefix}{kind}: {entity}"
    if label.upper() == "ATM WITHDRAWAL ATM WITHDRAWAL":
        return f"{prefix}ATM Withdrawal"
    return f"{prefix}{label}".strip()


def parse_relay_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if (
        "RELAY FINANCIALS TECHNOLOGY" not in upper
        or "ACCOUNT STATEMENT" not in upper
        or "OPENING BALANCE" not in upper
        or "CLOSING BALANCE" not in upper
    ):
        return None

    period = re.search(
        r"(?P<holder>[^\n|]+?)\s*\|\s*"
        r"(?P<start>[A-Z][a-z]{2}\s+\d{1,2})\s*-\s*"
        r"(?P<end>[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})",
        markdown,
    )
    summary = re.search(
        r"Opening Balance\s+\$?(?P<opening>[\d,]+\.\d{2})\s+"
        r"Closing Balance\s+\$?(?P<closing>-?[\d,]+\.\d{2})\s+"
        r"Deposits\s+\+\$?(?P<credits>[\d,]+\.\d{2})\s+"
        r"Withdrawals\s+-\$?(?P<debits>[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    account = re.search(r"Account Number:\s*([X\d-]+)", markdown, re.IGNORECASE)
    if not period or not summary or not account:
        return None

    end = datetime.strptime(period.group("end"), "%b %d, %Y").date()
    start = datetime.strptime(
        f"{period.group('start')}, {end.year}", "%b %d, %Y"
    ).date()
    opening = _money(summary.group("opening"))
    closing = _money(summary.group("closing"))
    credits = _money(summary.group("credits"))
    debits = _money(summary.group("debits"))

    source_rows: list[tuple[datetime, Decimal, Decimal, str]] = []
    for raw_line in markdown.splitlines():
        match = _ROW_RE.match(raw_line.strip())
        if not match:
            continue
        txn_date = datetime.strptime(match.group("date"), "%b %d, %Y")
        amount = _money(match.group("amount"))
        balance = _money(match.group("balance"))
        description = _description(match.group("label"), match.group("status"), amount)
        source_rows.append((txn_date, amount, balance, description))

    if not source_rows:
        return None

    # Relay prints newest first, including reverse posting order within a day.
    # Reversing the full row list restores the exact ledger order.
    transactions = [
        Transaction(
            date=txn_date.date().isoformat(),
            description=description,
            amount=float(amount),
            direction="credit" if amount > 0 else "debit",
            running_balance=float(balance),
        )
        for txn_date, amount, balance, description in reversed(source_rows)
    ]

    previous = opening
    for transaction in transactions:
        expected = previous + Decimal(str(transaction.amount))
        actual = Decimal(str(transaction.running_balance))
        if expected != actual:
            return None
        previous = actual
    if previous != closing:
        return None
    if sum((Decimal(str(t.amount)) for t in transactions if t.amount > 0), Decimal()) != credits:
        return None
    if -sum((Decimal(str(t.amount)) for t in transactions if t.amount < 0), Decimal()) != debits:
        return None

    holder = re.sub(r"\s+", " ", period.group("holder")).strip()
    return Statement(
        bank="Thread Bank (Relay)",
        account_name=f"{holder} - Operations",
        account_number=account.group(1),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=(end - start).days + 1,
        beginning_balance=float(opening),
        ending_balance=float(closing),
        stated_total_credits=float(credits),
        stated_total_debits=float(debits),
        transactions=transactions,
    )
