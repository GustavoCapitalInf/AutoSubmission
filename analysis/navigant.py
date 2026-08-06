from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .money import parse_decimal
from .schema import Statement, Transaction


_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
_MONEY_RE = re.compile(r"-?[\d,]+\.\d{2}")
_ROW_START_RE = re.compile(
    r"(?=\b\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b)"
)


def _money(value: str) -> Decimal:
    return parse_decimal(value)


def _transaction_stream(markdown: str) -> str:
    parts: list[str] = []
    page_blocks = re.split(r"(?m)^--- Page \d+(?: \(empty\))? ---\s*$", markdown)
    header = "Date Transaction Description Deposits Withdrawals Balance"
    for block in page_blocks:
        if header not in block:
            continue
        body = block.split(header, 1)[1]
        body = re.split(
            r"Checks Paid on this Account|1005 DOUGLAS PIKE|NAVIGANTCU\.ORG|â€¢\s*â€¢",
            body,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        parts.append(body)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def parse_navigant_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if (
        "NAVIGANTCU.ORG" not in upper
        or "QUEST BALANCE CHECKING" not in upper
        or "ACCOUNT SUMMARY" not in upper
        or "STATEMENT PERIOD" not in upper
    ):
        return None

    period = re.search(
        r"(\d{2})-(\d{2})-(\d{4})\s+to\s+(\d{2})-(\d{2})-(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    summary = re.search(
        r"Beginning Balance Deposits Interest Paid Checks Withdrawals Service Charges Ending Balance\s+"
        r"(?P<opening>-?[\d,]+\.\d{2})\s*\+\s*"
        r"(?P<credits>[\d,]+\.\d{2})\s*\+\s*"
        r"(?P<interest>[\d,]+\.\d{2})\s*-\s*"
        r"(?P<checks>[\d,]+\.\d{2})\s*-\s*"
        r"(?P<withdrawals>[\d,]+\.\d{2})\s*-\s*"
        r"(?P<service>[\d,]+\.\d{2})\s*=\s*"
        r"(?P<ending>-?[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    account = re.search(
        r"Account Summary for Quest Balance Checking\s*-\s*([Xx\d]+)", markdown
    )
    holder = re.search(r"\n([A-Z][A-Z ]+ LLC)\s+\d+\s+", markdown)
    if not period or not summary or not account:
        return None

    sm, sd, sy, em, ed, ey = [int(part) for part in period.groups()]
    start = date(sy, sm, sd)
    end = date(ey, em, ed)
    opening = _money(summary.group("opening"))
    ending = _money(summary.group("ending"))
    credits = _money(summary.group("credits"))
    checks = _money(summary.group("checks"))
    withdrawals = _money(summary.group("withdrawals"))
    service = _money(summary.group("service"))
    interest = _money(summary.group("interest"))

    previous = opening
    transactions: list[Transaction] = []
    for chunk in _ROW_START_RE.split(_transaction_stream(markdown)):
        match = re.match(
            r"(\d{2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(.*)",
            chunk,
        )
        if not match:
            continue
        day, month_name, remainder = match.groups()
        values = list(_MONEY_RE.finditer(remainder))
        if len(values) < 2:
            return None
        printed_amount = _money(values[-2].group())
        running_balance = _money(values[-1].group())
        description = re.sub(r"\s+", " ", remainder[: values[-2].start()]).strip()
        signed_amount = running_balance - previous
        if abs(signed_amount) != printed_amount:
            return None
        txn_date = date(end.year, _MONTHS[month_name], int(day))
        if txn_date < start or txn_date > end:
            return None
        transactions.append(
            Transaction(
                date=txn_date.isoformat(),
                description=description,
                amount=float(signed_amount),
                direction="credit" if signed_amount > 0 else "debit",
                running_balance=float(running_balance),
            )
        )
        previous = running_balance

    if not transactions or previous != ending:
        return None
    if opening + sum((Decimal(str(t.amount)) for t in transactions), Decimal()) != ending:
        return None
    summary_ending = opening + credits + interest - checks - withdrawals - service
    if summary_ending != ending:
        return None

    return Statement(
        bank="Navigant Credit Union",
        account_name="Quest Balance Checking",
        account_number=account.group(1),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=(end - start).days + 1,
        beginning_balance=float(opening),
        ending_balance=float(ending),
        stated_total_credits=float(credits),
        stated_total_debits=float(checks + withdrawals),
        stated_service_charge=float(service),
        stated_interest_paid=float(interest),
        transactions=transactions,
    ).model_copy(
        update={"account_name": "Quest Balance Checking" if holder is None else f"{holder.group(1).title()} - Quest Balance Checking"}
    )
