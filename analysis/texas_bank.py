from __future__ import annotations

import re
from datetime import date

from .money import STRICT_EITHER_MINUS, parse_amount
from .schema import Statement, Transaction
from .tables import section_between


_START_TOKENS = r"(?:ACH_|ACH|RDA|CARR|POS|DBT|Payment|CRCARDPMT|PHONE|PAYMENTS|SERVICE)"


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_EITHER_MINUS)


def _parse_mmddyy(raw: str) -> str:
    month, day, year = [int(part) for part in raw.split("/")]
    return date(2000 + year, month, day).isoformat()


def _rows(section: str, sign: int) -> list[Transaction]:
    body = re.sub(r"\n(?=(?:[\d,]+\.\d{2}-)\s*$)", " ", section)
    body = re.sub(r"\s+", " ", body)
    parts = re.split(rf"(?=\d{{2}}/\d{{2}}/\d{{2}}\s+{_START_TOKENS})", body)
    txns: list[Transaction] = []
    for part in parts:
        m = re.match(
            r"(\d{2}/\d{2}/\d{2})\s+(.+?)\s+((?:[\d,]+\.\d{2})-?)(?:\s|$)",
            part,
        )
        if not m:
            continue
        date_raw, desc, amount_raw = m.groups()
        amount = _money(amount_raw)
        if amount is None:
            return []
        signed = round(abs(amount) * sign, 2)
        txns.append(
            Transaction(
                date=_parse_mmddyy(date_raw),
                description=re.sub(r"\s+", " ", desc).strip(),
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
            )
        )
    return txns


def parse_texas_bank_statement(markdown: str) -> Statement | None:
    if "Texas Bank and Trust" not in markdown and "6250TEXAS" not in markdown:
        return None
    summary = re.search(
        r"Account Number\s+(\d+)\s+Balance on\s+(\d{2}/\d{2}/\d{2})\s+([\d,]+\.\d{2})\s+"
        r"Date From\s+(\d{2}/\d{2}/\d{2})\s+Deposits\s+\(\s*(\d+)\s*\)\s+\+\s+([\d,]+\.\d{2})\s+"
        r"Date To\s+(\d{2}/\d{2}/\d{2}).*?"
        r"Days in Statement Period\s+(\d+)\s+Checks/Debits\s+\(\s*(\d+)\s*\)\s+-\s+([\d,]+\.\d{2})\s+"
        r"Average Ledger\s+([\d,]+\.\d{2})\s+Service Charge\s+-\s+([\d,]+\.\d{2}).*?"
        r"Balance on\s+\d{2}/\d{2}/\d{2}\s+([\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not summary:
        return None
    (
        account,
        beginning_date,
        beginning_raw,
        start_raw,
        credit_count,
        credits_raw,
        end_raw,
        days,
        debit_count,
        debits_raw,
        avg_raw,
        service_raw,
        ending_raw,
    ) = summary.groups()

    credits = _money(credits_raw)
    debits = _money(debits_raw)
    service_charge = _money(service_raw)
    beginning = _money(beginning_raw)
    ending = _money(ending_raw)
    average = _money(avg_raw)
    if None in {credits, debits, service_charge, beginning, ending, average}:
        return None

    txns = _rows(section_between(markdown, r"Deposits and Other Credits", r"Withdrawals and Other Debits"), 1)
    txns.extend(_rows(section_between(markdown, r"Withdrawals and Other Debits", r"Daily Balance Information"), -1))
    if not txns:
        return None
    credit_sum = sum(t.amount for t in txns if t.amount > 0)
    debit_sum = -sum(t.amount for t in txns if t.amount < 0)
    expected_debits_with_service = round((debits or 0.0) + (service_charge or 0.0), 2)
    if abs(credit_sum - (credits or 0.0)) > 0.01:
        return None
    if abs(debit_sum - expected_debits_with_service) > 0.01:
        return None

    if beginning_date != start_raw:
        return None
    stmt = Statement(
        bank="Texas Bank and Trust",
        account_name="Small Business Checking",
        account_number=account,
        period_start=_parse_mmddyy(start_raw),
        period_end=_parse_mmddyy(end_raw),
        days_in_period=int(days),
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_credit_count=int(credit_count),
        stated_debit_count=int(debit_count),
        stated_average_balance=average,
        stated_service_charge=service_charge,
        transactions=txns,
    )
    return stmt
