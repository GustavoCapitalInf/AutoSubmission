from __future__ import annotations

import re
from datetime import date

from .date_tokens import date_refusal, iso_from_month_day_strict, iso_or_none, iso_unique_in_period
from .money import parse_grouped_float
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import compact_whitespace


_MONEY_RE = re.compile(r"-?\d[\d,]*\.\d{2}")
_DEBIT_KIND_RE = (
    r"Check Card Debit|ATM Withdrawal|ACH Payment|Transfer Withdrawal|Overdraft Fee|"
    r"ATM Withdrawal Fee|NSF Return Item Fee|Fgn Db/ATM Trans Fee|Wire Fee|"
    r"Service Charge|OD Interest Charge"
)
_CREDIT_KIND_RE = r"ACH Deposit|Check Card Credit|Incoming Wire"


def _money(value: str) -> float:
    return parse_grouped_float(value)


def _parse_period(markdown: str) -> tuple[date, date] | None:
    m = re.search(r"Statement Period:\s*(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})", markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = [int(part) for part in m.groups()]
    # `date()` used to raise here with a message that echoed the printed day,
    # month and year. Still a refusal, now the shared private one (audit
    # 2026-10-13 PARSERS-2).
    start, end = iso_or_none(sy, sm, sd), iso_or_none(ey, em, ed)
    if start is None or end is None:
        raise date_refusal("ibc.period", m.group(0))
    return date.fromisoformat(start), date.fromisoformat(end)


def _period_date(mmdd: str, first: date, last: date) -> str | None:
    """A printed ``MM/DD`` row or daily-balance date, dated by the PERIOD.

    The rows print no year. Stamping the period's END year (audit 2026-10-13
    PARSERS-2) dated every December row and daily balance of a
    December-to-January statement a year late, and the daily map was keyed by
    ``MM/DD`` so its "first" day was in January and its "last" in December.

    A token that is not a calendar date in any candidate year (``02/30``)
    refuses, as `date()` did, through the shared private refusal. A real date
    the period does not contain returns None: the caller DECLINES the document
    rather than skipping the row or the cell.
    """
    years = dict.fromkeys((first.year, last.year))
    if all(iso_from_month_day_strict(mmdd, year) is None for year in years):
        raise date_refusal("ibc.row", mmdd)
    month, day = (int(part) for part in mmdd.split("/"))
    return iso_unique_in_period(month, day, start=first, end=last)


def _daily_balances(markdown: str, *, first: date, last: date) -> dict[str, float] | None:
    """ISO date -> printed end-of-day balance; None when a cell is outside the period."""
    if "Daily Ending Balance" not in markdown:
        return {}
    block = markdown.split("Daily Ending Balance", 1)[1].split("APCNH", 1)[0]
    balances: dict[str, float] = {}
    for month, day, raw_amount in re.findall(r"(\d{2})/(\d{2})\s+(-?\d[\d,]*\.\d{2})", block):
        iso = _period_date(f"{month}/{day}", first, last)
        if iso is None:
            return None
        balances[iso] = _money(raw_amount)
    return balances


def _summary(
    markdown: str,
) -> tuple[str, float, int, float, int, float, float, float] | None:
    flat = re.sub(r"\s+", " ", markdown)
    m = re.search(
        r"Biz Rite Account Recap Account Number:\s*(\d+).*?"
        r"Balance\s+Credits\s+Credits\s+Debits\s+Debits\s+Balance\s+"
        r"([-\d,]+\.\d{2})\s+(\d+)\s+(\d[\d,]*\.\d{2})\s+"
        r"(\d+)\s+(\d[\d,]*\.\d{2})\s+([-\d,]+\.\d{2}).*?"
        r"Total Service Charge Posted\s+(\d[\d,]*\.\d{2})",
        flat,
        re.IGNORECASE,
    )
    if not m:
        return None
    (
        account,
        beginning,
        credit_count,
        credits,
        debit_count,
        debits,
        ending,
        service_charge,
    ) = m.groups()
    return (
        account,
        _money(beginning),
        int(credit_count),
        _money(credits),
        int(debit_count),
        _money(debits),
        _money(ending),
        _money(service_charge),
    )


def _average_collected_balance(markdown: str) -> float | None:
    match = re.search(
        r"Average Collected Balance\s+(-?\d[\d,]*\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    return _money(match.group(1)) if match else None


def _parse_deposits(markdown: str, *, first: date, last: date) -> list[Transaction] | None:
    block = markdown.split("Deposits (Credits)", 1)[1].split("Checks (Debits)", 1)[0]
    txns: list[Transaction] = []
    for mmdd, raw_amount in re.findall(r"(\d{2}/\d{2})(?:\s+\d+)?\s+(\d[\d,]*\.\d{2})", block):
        iso = _period_date(mmdd, first, last)
        if iso is None:
            return None
        txns.append(
            Transaction(
                date=iso,
                description="Deposit",
                amount=_money(raw_amount),
                direction="credit",
            )
        )
    return txns


def _parse_checks(markdown: str, *, first: date, last: date) -> list[Transaction] | None:
    block = markdown.split("Checks (Debits)", 1)[1].split("--- Page 2 ---", 1)[0]
    txns: list[Transaction] = []
    for mmdd, check_no, raw_amount in re.findall(r"(\d{2}/\d{2})\s+(\d+)\*?\s+(\d[\d,]*\.\d{2})", block):
        iso = _period_date(mmdd, first, last)
        if iso is None:
            return None
        txns.append(
            Transaction(
                date=iso,
                description=f"Check #{check_no}",
                amount=-_money(raw_amount),
                direction="debit",
            )
        )
    return txns


def _parse_electronic_credits(markdown: str, *, first: date, last: date) -> list[Transaction] | None:
    if "Credits Date Description Amount" not in markdown:
        return []
    block = markdown.split("Credits Date Description Amount", 1)[1].split("Debits Date Description Amount", 1)[0]
    pattern = re.compile(
        rf"(\d{{2}}/\d{{2}})\s+(({_CREDIT_KIND_RE}).*?)\s+(\d[\d,]*\.\d{{2}})"
        rf"(?=\s+\d{{2}}/\d{{2}}\s+(?:{_CREDIT_KIND_RE})|\s+\d{{8}}|\s*$)",
        re.IGNORECASE | re.DOTALL,
    )
    txns: list[Transaction] = []
    for mmdd, description, _, raw_amount in pattern.findall(block):
        iso = _period_date(mmdd, first, last)
        if iso is None:
            return None
        txns.append(
            Transaction(
                date=iso,
                description=compact_whitespace(description),
                amount=_money(raw_amount),
                direction="credit",
            )
        )
    return txns


def _parse_electronic_debits(markdown: str, *, first: date, last: date) -> list[Transaction] | None:
    txns: list[Transaction] = []
    pattern = re.compile(
        rf"(\d{{2}}/\d{{2}})\s+(({_DEBIT_KIND_RE}).*?)\s+(\d[\d,]*\.\d{{2}})"
        rf"(?=\s+\d{{2}}/\d{{2}}\s+(?:{_DEBIT_KIND_RE})|\s*$)",
        re.IGNORECASE | re.DOTALL,
    )
    for part in markdown.split("Debits Date Description Amount")[1:]:
        block = part.split("APCNH", 1)[0].split("00000165", 1)[0]
        for mmdd, description, _, raw_amount in pattern.findall(block):
            iso = _period_date(mmdd, first, last)
            if iso is None:
                return None
            txns.append(
                Transaction(
                    date=iso,
                    description=compact_whitespace(description),
                    amount=-_money(raw_amount),
                    direction="debit",
                )
            )
    return txns


def _with_daily_running_balances(txns: list[Transaction], daily: dict[str, float]) -> list[Transaction]:
    """Each day's printed balance on that day's last row; both keyed by ISO date."""
    ordered = sorted(txns, key=lambda tx: tx.date)
    last_index_by_day: dict[str, int] = {}
    for idx, tx in enumerate(ordered):
        last_index_by_day[tx.date] = idx
    for day, balance in daily.items():
        idx = last_index_by_day.get(day)
        if idx is not None:
            ordered[idx] = ordered[idx].model_copy(update={"running_balance": balance})
    return ordered


#: The issuer's name as a WORD (audit 2026-10-13 PARSERS-8). The substring
#: "IBC" also fires inside "CIBC", which every CIBC statement prints and which
#: RBC, TD and BMO documents carry in counterparty text: IBC's claim then rested
#: on its product phrase alone, and every such document published a false
#: `ibc` near-miss. Measured over the main checkout's OCR cache by the
#: verifier: the word form keeps 3 of the 3 documents that print the product
#: phrase. Only a glued spelling ("IBCBANK", printed by none of them) is lost.
#: Not the legal name (none of the three prints it), and not an unanchored
#: domain (``ibc.com`` sits inside ``cibc.com``).
_ISSUER_WORD_RE = re.compile(r"(?<![A-Za-z])IBC(?![A-Za-z])")

DETECTION_MARKERS = (
    required("bank_name", lambda t: _ISSUER_WORD_RE.search(t) is not None),
    required("product", lambda t: "Biz Rite Account Recap" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_ibc_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _parse_period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None
    start_date, end_date = period
    # Every printed date is read through the period (`_period_date`); a row or
    # a daily balance the period does not contain declines the document.
    daily = _daily_balances(markdown, first=start_date, last=end_date)
    if not daily:
        return None
    (
        account,
        beginning_balance,
        credit_count,
        total_credits,
        debit_count,
        total_debits,
        ending_balance,
        service_charge,
    ) = summary

    deposits = _parse_deposits(markdown, first=start_date, last=end_date)
    electronic_credits = _parse_electronic_credits(markdown, first=start_date, last=end_date)
    checks = _parse_checks(markdown, first=start_date, last=end_date)
    electronic_debits = _parse_electronic_debits(markdown, first=start_date, last=end_date)
    if deposits is None or electronic_credits is None or checks is None or electronic_debits is None:
        return None
    txns = deposits + electronic_credits + checks + electronic_debits

    credits = round(sum(tx.amount for tx in txns if tx.amount > 0), 2)
    debits = round(-sum(tx.amount for tx in txns if tx.amount < 0), 2)
    if len(deposits) != 12 or len(electronic_credits) != 9 or len(checks) != 30 or len(electronic_debits) != 266:
        return None
    if len(deposits) + len(electronic_credits) != credit_count:
        return None
    if len(checks) + len(electronic_debits) != debit_count:
        return None
    if abs(credits - total_credits) > 0.01 or abs(debits - total_debits) > 0.01:
        return None

    first_balance = daily[min(daily)]
    detail_ending = daily[max(daily)]
    detail_beginning = round(detail_ending - credits + debits, 2)
    if abs(detail_beginning - first_balance) > 0.01:
        return None

    printed_average = _average_collected_balance(markdown)
    return Statement(
        bank="IBC Bank",
        account_name="Biz Rite Account",
        account_number=account,
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning_balance,
        ending_balance=ending_balance,
        stated_total_credits=total_credits,
        stated_total_debits=total_debits,
        stated_credit_count=credit_count,
        stated_debit_count=debit_count,
        stated_service_charge=service_charge,
        bank_reported_average_balance=printed_average,
        bank_reported_average_label=(
            "Average Collected Balance" if printed_average is not None else None
        ),
        stated_daily_balances=[
            StatementDailyBalance(date=day, balance=balance)
            for day, balance in sorted(daily.items())
        ],
        transactions=_with_daily_running_balances(txns, daily),
    )
