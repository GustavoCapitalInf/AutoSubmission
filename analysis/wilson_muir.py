from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_from_month_day_year
from .money import STRICT_EITHER_MINUS_OR_PLUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import section_between


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_EITHER_MINUS_OR_PLUS)


def _parse_mmddyy(raw: str) -> str:
    return iso_from_month_day_year(raw, century="always")


def _dated_amount_rows(section: str, sign: int) -> list[Transaction]:
    body = re.sub(r"\s+", " ", section)
    rows: list[Transaction] = []
    for part in re.split(r"(?=\d{2}/\d{2}/\d{2}\s+)", body):
        m = re.match(r"(\d{2}/\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s|$)", part)
        if not m:
            continue
        date_raw, desc, amount_raw = m.groups()
        amount = _money(amount_raw)
        if amount is None:
            return []
        rows.append(
            Transaction(
                date=_parse_mmddyy(date_raw),
                description=re.sub(r"\s+", " ", desc).strip(),
                amount=round(abs(amount) * sign, 2),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return rows


def _check_rows(section: str) -> list[Transaction]:
    body = re.sub(r"\s+", " ", section)
    rows: list[Transaction] = []
    for m in re.finditer(r"(\d{2}/\d{2}/\d{2})\s+(?:(\d+\*?)\s+)?([\d,]+\.\d{2})", body):
        date_raw, check_no, amount_raw = m.groups()
        amount = _money(amount_raw)
        if amount is None:
            return []
        desc = "Check"
        if check_no:
            desc = f"Check {check_no.rstrip('*')}"
        rows.append(
            Transaction(
                date=_parse_mmddyy(date_raw),
                description=desc,
                amount=round(-abs(amount), 2),
                direction="debit",
            )
        )
    return rows


DETECTION_MARKERS = (
    required("bank_name", lambda t: "WILSON & MUIR" in t),
    required("section", lambda t: "SMALL BUSINESS PACKAGE SUMMARY" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_wilson_muir_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    summary = re.search(
        r"Statement Date:\s+(\d{2}/\d{2}/\d{4})\s+Account No\.:\s+#?(\d+).*?"
        r"Balance Forward From\s+(\d{2}/\d{2}/\d{2})\s+([\d,]+\.\d{2})\s+"
        r"Deposits\s+(\d+)\s+([\d,]+\.\d{2})\+\s+"
        r"Debits\s+(\d+)\s+([\d,]+\.\d{2})\s+"
        r"Automatic Withdrawals\s+(\d+)\s+([\d,]+\.\d{2})\s+"
        r"Automatic Deposits\s+(\d+)\s+([\d,]+\.\d{2})\+\s+"
        r"Card Activity\s+(\d+)\s+([\d,]+\.\d{2})\s+"
        r"Ending Balance On\s+(\d{2}/\d{2}/\d{2})\s+([\d,]+\.\d{2})\s+"
        r".*?Average Balance \(Ledger\)\s+([\d,]+\.\d{2})\+?",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not summary:
        return None
    (
        statement_date,
        account,
        beginning_date,
        beginning_raw,
        deposit_count,
        deposits_raw,
        debit_count,
        debits_raw,
        automatic_withdrawal_count,
        automatic_withdrawals_raw,
        automatic_deposit_count,
        automatic_deposits_raw,
        card_count,
        card_raw,
        ending_date,
        ending_raw,
        average_raw,
    ) = summary.groups()

    deposits = _money(deposits_raw)
    debits = _money(debits_raw)
    auto_withdrawals = _money(automatic_withdrawals_raw)
    auto_deposits = _money(automatic_deposits_raw)
    card_activity = _money(card_raw)
    beginning = _money(beginning_raw)
    ending = _money(ending_raw)
    average = _money(average_raw)
    if None in {deposits, debits, auto_withdrawals, auto_deposits, card_activity, beginning, ending, average}:
        return None

    credit_section = section_between(markdown, r"ALL CREDIT ACTIVITY", r"ELECTRONIC DEBITS")
    electronic_section = section_between(markdown, r"ELECTRONIC DEBITS", r"CHECKS AND OTHER DEBITS")
    check_section = section_between(markdown, r"CHECKS AND OTHER DEBITS", r"DAILY BALANCE SUMMARY")
    txns = _dated_amount_rows(credit_section, 1)
    txns.extend(_dated_amount_rows(electronic_section, -1))
    txns.extend(_check_rows(check_section))

    if not txns:
        return None
    stated_credits = round((deposits or 0.0) + (auto_deposits or 0.0), 2)
    stated_debits = round((debits or 0.0) + (auto_withdrawals or 0.0) + (card_activity or 0.0), 2)
    if abs(sum(t.amount for t in txns if t.amount > 0) - stated_credits) > 0.01:
        return None
    if abs(-sum(t.amount for t in txns if t.amount < 0) - stated_debits) > 0.01:
        return None

    end_month, end_day, end_year = [int(part) for part in ending_date.split("/")]
    _stmt_month, _stmt_day, stmt_year = [int(part) for part in statement_date.split("/")]
    period_end = date(2000 + end_year, end_month, end_day)
    start_month, start_day, start_year = [int(part) for part in beginning_date.split("/")]
    # The "balance forward" date is the previous cycle close; activity starts the next calendar day.
    period_start = date(2000 + start_year, start_month, start_day) + timedelta(days=1)
    stmt = Statement(
        bank="Wilson & Muir Bank & Trust",
        account_name="Small Business Package",
        account_number=f"#{account}",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        # Derived from the printed period bounds (R-1 item 10 - previously a
        # hardcoded 30-day guess). The year-consistency check keeps the value
        # fail-closed when the statement date conflicts with the period end.
        days_in_period=(
            (period_end - period_start).days + 1
            if stmt_year == period_end.year
            else None
        ),
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=stated_credits,
        stated_total_debits=stated_debits,
        stated_credit_count=int(deposit_count) + int(automatic_deposit_count),
        stated_debit_count=int(debit_count) + int(automatic_withdrawal_count) + int(card_count),
        bank_reported_average_balance=average,
        bank_reported_average_label=(
            "Average Balance (Ledger)" if average is not None else None
        ),
        transactions=txns,
    )
    return stmt
