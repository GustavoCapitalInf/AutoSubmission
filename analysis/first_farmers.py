from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .date_tokens import iso_from_month_day_year
from .money import parse_decimal_mixed_separator
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


_MONEY = r"\d[\d,]*[\.,]\d{2}"


def _money(value: str) -> Decimal:
    return parse_decimal_mixed_separator(value, single_comma_only=True)


def _description(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" .")
    if re.search(r"\bPURCHASE\b", cleaned, re.IGNORECASE):
        return f"Debit Card Purchase: {cleaned}"
    return cleaned


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    # R4-1: "FIRST FARMERS" is broken across lines by OCR in the committed
    # artifact and matched only from the source filename. The issuer's
    # tele-banking domain survives the scan and is in the statement body.
    required("issuer_domain", lambda t: "FFBT.COM" in t),
    required("product", lambda t: "BUSINESS BASIC CHECKING ACCOUNT" in t),
    required("opening_label", lambda t: "BALANCE LAST STATEMENT" in t),
    required("period_label", lambda t: "TOTAL DAYS IN STATEMENT PERIOD" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_first_farmers_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if not detect(markdown).claims:
        return None

    product = re.search(r"BUSINESS BASIC CHECKING ACCOUNT\s+([X\d]+)", markdown, re.IGNORECASE)
    holder = re.search(r"\n([A-Z][A-Za-z ]+ LLC)\s+\d+", markdown)
    opening = re.search(
        rf"BALANCE LAST STATEMENT.*?(\d{{2}}/\d{{2}}/\d{{2}})\s+({_MONEY})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    period = re.search(
        r"TOTAL DAYS IN STATEMENT PERIOD\s+"
        r"(\d{2}/\d{2}/\d{2})\s+THROUGH\s+(\d{2}/\d{2}/\d{2}):\s+(\d+)",
        markdown,
        re.IGNORECASE,
    )
    summary = re.search(
        rf"TOTAL CREDITS\s+\((\d+)\)\s+({_MONEY})\s+"
        rf"AVG AVAILABLE BALANCE\s+({_MONEY})\s+"
        rf"TOTAL DEBITS\s+\((\d+)\)\s+({_MONEY})\s+"
        rf"AVERAGE BALANCE\s+({_MONEY})",
        markdown,
        re.IGNORECASE,
    )
    ending = re.search(
        rf"BALANCE THIS STATEMENT.*?(\d{{2}}/\d{{2}}/\d{{2}})\s+({_MONEY})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not product or not opening or not period or not summary or not ending:
        return None

    start = date.fromisoformat(iso_from_month_day_year(period.group(1)))
    end = date.fromisoformat(iso_from_month_day_year(period.group(2)))
    opening_balance = _money(opening.group(2))
    ending_balance = _money(ending.group(2))
    credit_count = int(summary.group(1))
    total_credits = _money(summary.group(2))
    debit_count = int(summary.group(4))
    total_debits = _money(summary.group(5))
    average_balance = _money(summary.group(6))

    detail_match = re.search(
        r"BALANCE LAST STATEMENT.*?\d{2}/\d{2}/\d{2}\s+" + _MONEY +
        r"(?P<body>.*?)BALANCE THIS STATEMENT",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not detail_match:
        return None
    body = re.sub(r"\s+", " ", detail_match.group("body")).strip()
    row_re = re.compile(
        rf"(?P<amount>{_MONEY})\s+"
        r"(?P<date>\d{2}/\d{2}/\d{2})\s+"
        rf"(?P<balance>{_MONEY})"
    )
    previous = opening_balance
    cursor = 0
    transactions: list[Transaction] = []
    for match in row_re.finditer(body):
        description = _description(body[cursor : match.start()])
        if not description:
            return None
        magnitude = _money(match.group("amount"))
        running_balance = _money(match.group("balance"))
        signed_amount = running_balance - previous
        if abs(signed_amount) != magnitude:
            return None
        transactions.append(
            Transaction(
                date=iso_from_month_day_year(match.group("date")),
                description=description,
                amount=float(signed_amount),
                direction="credit" if signed_amount > 0 else "debit",
                running_balance=float(running_balance),
            )
        )
        previous = running_balance
        cursor = match.end()

    if previous != ending_balance:
        return None
    if len([t for t in transactions if t.amount > 0]) != credit_count:
        return None
    if len([t for t in transactions if t.amount < 0]) != debit_count:
        return None
    if sum((Decimal(str(t.amount)) for t in transactions if t.amount > 0), Decimal()) != total_credits:
        return None
    if -sum((Decimal(str(t.amount)) for t in transactions if t.amount < 0), Decimal()) != total_debits:
        return None

    account_holder = holder.group(1) if holder else None
    return Statement(
        bank="First Farmers Bank & Trust",
        account_name=(
            f"{account_holder} - Business Basic Checking" if account_holder else "Business Basic Checking"
        ),
        account_number=product.group(1),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=int(period.group(3)),
        beginning_balance=float(opening_balance),
        ending_balance=float(ending_balance),
        stated_total_credits=float(total_credits),
        stated_total_debits=float(total_debits),
        stated_credit_count=credit_count,
        stated_debit_count=debit_count,
        stated_average_balance=float(average_balance),
        transactions=transactions,
    )
