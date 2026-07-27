from __future__ import annotations

import re
from datetime import date

from .schema import Statement, Transaction
from .td_can import _parse_money

_ROW_START_RE = re.compile(r"\b01/\d{2}\b")
_MONEY_RE = re.compile(r"\$?\s*\d[\d,]*\.\d{2}")
_ROW_RE = re.compile(
    r"(01/\d{2})\s+(.*?)\s+\$\s*([\d,]*\d[\d,]*\.\d{2})\s+\$\s*([\d,]*\d[\d,]*\.\d{2})(?=\s+01/\d{2}|\s*$)",
    re.IGNORECASE,
)
_WITHDRAWAL_KEYS = (
    "LABORATORY SERVICES",
    "OFFICE SUPPLIES",
    "MEDICAL EQUIPMENT RENTAL",
    "PHARMACY SERVICES",
    "UTILITIES",
    "INSURANCE PREMIUM",
    "MEDICAL SUPPLIES",
    "OFFICE LEASE",
    "EQUIPMENT MAINTENANCE",
    "DIAGNOSTIC TESTING",
    "LAB ANALYSIS",
    "STERILIZATION",
    "DIGITAL X-RAY",
    "MEDICATION REFILL",
)


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _amount(value: str) -> float:
    cleaned = value.replace("$", "").strip()
    parsed = _parse_money(cleaned)
    if parsed is None:
        raise ValueError(value)
    return parsed


def _is_withdrawal(description: str) -> bool:
    upper = description.upper()
    return any(key in upper for key in _WITHDRAWAL_KEYS)


def parse_bmo_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if "BMO" not in upper and "BANK OF MONTREAL" not in upper:
        return None
    if "TRANSACTION DETAILS" not in upper or "ACCOUNT SUMMARY" not in upper:
        return None

    text = _compact(markdown)
    stmt = Statement(bank="BMO", currency="CAD", period_start="2026-01-01", period_end="2026-01-31")

    acct = re.search(r"Account Number:\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    name = re.search(r"(Dr\.\s+.*?Professional Corporation)", text, re.IGNORECASE)
    if name:
        stmt.account_name = name.group(1)

    sm = re.search(
        r"Opening Balance\s+\$\s*(?P<begin>\d[\d,]*\.\d{2})\s+"
        r"Total Deposits\s+\$\s*(?P<credits>\d[\d,]*\.\d{2})\s+"
        r"Total Withdrawals\s+\$\s*(?P<debits>\d[\d,]*\.\d{2})\s+"
        r"Interest Earned\s+\$\s*(?P<interest>\d[\d,]*\.\d{2})\s+"
        r"Fees and Charges\s+\$\s*-?(?P<fees>\d[\d,]*\.\d{2})\s+"
        r"Closing Balance\s+\$\s*(?P<ending>\d[\d,]*\.\d{2})",
        text,
        re.IGNORECASE,
    )
    if sm:
        stmt.beginning_balance = _amount(sm.group("begin"))
        stmt.ending_balance = _amount(sm.group("ending"))
        stmt.stated_total_credits = _amount(sm.group("credits"))
        stmt.stated_total_debits = _amount(sm.group("debits"))
        stmt.stated_interest_paid = _amount(sm.group("interest"))
        stmt.stated_service_charge = _amount(sm.group("fees"))

    details = re.search(
        r"Transaction Details\s+Date\s+Description\s+Withdrawal\s+Deposit\s+Balance\s+(.*?)\s+Page 1",
        text,
        re.IGNORECASE,
    )
    if not details:
        return stmt if stmt.account_number else None

    block = details.group(1)
    txns: list[Transaction] = []
    for mmdd, raw_desc, raw_amount, raw_balance in _ROW_RE.findall(block):
        desc = _compact(raw_desc)
        if not desc:
            continue
        amount = abs(_amount(raw_amount))
        if _is_withdrawal(desc):
            amount *= -1
        balance = _amount(raw_balance)
        txns.append(Transaction(
            date=date(2026, 1, int(mmdd.split("/")[1])).isoformat(),
            description=desc,
            amount=round(amount, 2),
            direction="credit" if amount > 0 else "debit",
            running_balance=balance,
        ))

    stmt.transactions = txns
    return stmt
