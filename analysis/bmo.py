from __future__ import annotations

import calendar
import re
from datetime import date

from .dates import resolve_year
from .money import parse_money
from .schema import Statement, Transaction

_ROW_RE = re.compile(
    r"(\d{1,2}/\d{1,2})\s+(.*?)\s+\$\s*(\d[\d,]*\.\d{2})\s+"
    r"\$\s*(\d[\d,]*\.\d{2})(?=\s+\d{1,2}/\d{1,2}|\s+Page\s+\d+\b|\s*$)",
    re.IGNORECASE,
)
# Only used when contradictory printed balances make column direction
# impossible to infer. A valid BMO ledger is oriented from balance continuity.
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
    parsed = parse_money(cleaned)
    if parsed is None:
        raise ValueError(value)
    return parsed


def _is_withdrawal(description: str) -> bool:
    upper = description.upper()
    return any(key in upper for key in _WITHDRAWAL_KEYS)


def _statement_period(text: str) -> tuple[date, date] | None:
    match = re.search(
        r"Statement Period:\s*([A-Za-z]+)\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        month = list(calendar.month_name).index(match.group(1).title())
        year = int(match.group(2))
    except ValueError:
        return None
    start = date(year, month, 1)
    return start, date(year, month, calendar.monthrange(year, month)[1])


def _account_name(markdown: str, text: str) -> str | None:
    for raw_line in markdown.splitlines():
        line = _compact(raw_line)
        match = re.match(
            r"(?P<name>.+?)\s+\d+\s+\S.*?\bAccount Number:",
            line,
            re.IGNORECASE,
        )
        if match:
            return match.group("name").strip()
    match = re.search(
        r"Customer Service:\s*[\d() +.-]+\s+(?P<name>.+?)\s+\d+\s+\S.*?"
        r"\bAccount Number:",
        text,
        re.IGNORECASE,
    )
    return match.group("name").strip() if match else None


def _signed_amount(
    description: str,
    amount: float,
    running_balance: float,
    previous_balance: float | None,
) -> float:
    if previous_balance is not None:
        credit_matches = abs(previous_balance + amount - running_balance) <= 0.01
        debit_matches = abs(previous_balance - amount - running_balance) <= 0.01
        if credit_matches != debit_matches:
            return amount if credit_matches else -amount
    return -amount if _is_withdrawal(description) else amount


def parse_bmo_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if "BMO" not in upper and "BANK OF MONTREAL" not in upper:
        return None
    if "TRANSACTION DETAILS" not in upper or "ACCOUNT SUMMARY" not in upper:
        return None

    text = _compact(markdown)
    period = _statement_period(text)
    if period is None:
        return None
    period_start, period_end = period
    currency = re.search(r"Currency:\s*([A-Z]{3})\b", text, re.IGNORECASE)
    stmt = Statement(
        bank="BMO",
        currency=currency.group(1).upper() if currency else "CAD",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )

    acct = re.search(r"Account Number:\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    stmt.account_name = _account_name(markdown, text)

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
        r"Transaction Details\s+Date\s+Description\s+Withdrawal\s+Deposit\s+Balance\s+"
        r"(.*?)(?=\s+Account Summary Totals\b|\s+Important Information\b|$)",
        text,
        re.IGNORECASE,
    )
    if not details:
        return stmt if stmt.account_number else None

    block = details.group(1)
    txns: list[Transaction] = []
    previous_balance = stmt.beginning_balance
    for mmdd, raw_desc, raw_amount, raw_balance in _ROW_RE.findall(block):
        desc = _compact(raw_desc)
        if not desc:
            continue
        amount = abs(_amount(raw_amount))
        balance = _amount(raw_balance)
        amount = _signed_amount(desc, amount, balance, previous_balance)
        month, day = (int(part) for part in mmdd.split("/"))
        year = resolve_year(month, day, period_start, period_end)
        if year is None:
            continue
        try:
            transaction_date = date(year, month, day)
        except ValueError:
            continue
        previous_balance = balance
        txns.append(Transaction(
            date=transaction_date.isoformat(),
            description=desc,
            amount=round(amount, 2),
            direction="credit" if amount > 0 else "debit",
            running_balance=balance,
        ))

    stmt.transactions = txns
    return stmt
