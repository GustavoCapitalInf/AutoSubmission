from __future__ import annotations

import re
from datetime import date

from .schema import Statement, StatementDailyBalance, Transaction


_MONEY_RE = re.compile(r"-?\d[\d,]*\.\d{2}")
_DEBIT_KIND_RE = (
    r"Check Card Debit|ATM Withdrawal|ACH Payment|Transfer Withdrawal|Overdraft Fee|"
    r"ATM Withdrawal Fee|NSF Return Item Fee|Fgn Db/ATM Trans Fee|Wire Fee|"
    r"Service Charge|OD Interest Charge"
)
_CREDIT_KIND_RE = r"ACH Deposit|Check Card Credit|Incoming Wire"


def _money(value: str) -> float:
    return float(value.replace(",", ""))


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _parse_period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(r"Statement Period:\s*(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})", markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = [int(part) for part in m.groups()]
    start = date(sy, sm, sd)
    end = date(ey, em, ed)
    return start.isoformat(), end.isoformat(), end.year


def _daily_balances(markdown: str) -> dict[str, float]:
    if "Daily Ending Balance" not in markdown:
        return {}
    block = markdown.split("Daily Ending Balance", 1)[1].split("APCNH", 1)[0]
    balances: dict[str, float] = {}
    for month, day, raw_amount in re.findall(r"(\d{2})/(\d{2})\s+(-?\d[\d,]*\.\d{2})", block):
        balances[f"{month}/{day}"] = _money(raw_amount)
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


def _parse_deposits(markdown: str, *, year: int) -> list[Transaction]:
    block = markdown.split("Deposits (Credits)", 1)[1].split("Checks (Debits)", 1)[0]
    txns: list[Transaction] = []
    for mmdd, raw_amount in re.findall(r"(\d{2}/\d{2})(?:\s+\d+)?\s+(\d[\d,]*\.\d{2})", block):
        txns.append(
            Transaction(
                date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
                description="Deposit",
                amount=_money(raw_amount),
                direction="credit",
            )
        )
    return txns


def _parse_checks(markdown: str, *, year: int) -> list[Transaction]:
    block = markdown.split("Checks (Debits)", 1)[1].split("--- Page 2 ---", 1)[0]
    txns: list[Transaction] = []
    for mmdd, check_no, raw_amount in re.findall(r"(\d{2}/\d{2})\s+(\d+)\*?\s+(\d[\d,]*\.\d{2})", block):
        txns.append(
            Transaction(
                date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
                description=f"Check #{check_no}",
                amount=-_money(raw_amount),
                direction="debit",
            )
        )
    return txns


def _parse_electronic_credits(markdown: str, *, year: int) -> list[Transaction]:
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
        txns.append(
            Transaction(
                date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
                description=_compact(description),
                amount=_money(raw_amount),
                direction="credit",
            )
        )
    return txns


def _parse_electronic_debits(markdown: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    pattern = re.compile(
        rf"(\d{{2}}/\d{{2}})\s+(({_DEBIT_KIND_RE}).*?)\s+(\d[\d,]*\.\d{{2}})"
        rf"(?=\s+\d{{2}}/\d{{2}}\s+(?:{_DEBIT_KIND_RE})|\s*$)",
        re.IGNORECASE | re.DOTALL,
    )
    for part in markdown.split("Debits Date Description Amount")[1:]:
        block = part.split("APCNH", 1)[0].split("00000165", 1)[0]
        for mmdd, description, _, raw_amount in pattern.findall(block):
            txns.append(
                Transaction(
                    date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
                    description=_compact(description),
                    amount=-_money(raw_amount),
                    direction="debit",
                )
            )
    return txns


def _with_daily_running_balances(txns: list[Transaction], daily: dict[str, float], *, year: int) -> list[Transaction]:
    ordered = sorted(txns, key=lambda tx: tx.date)
    last_index_by_day: dict[str, int] = {}
    for idx, tx in enumerate(ordered):
        dt = date.fromisoformat(tx.date)
        last_index_by_day[f"{dt.month:02d}/{dt.day:02d}"] = idx
    for mmdd, balance in daily.items():
        idx = last_index_by_day.get(mmdd)
        if idx is not None:
            ordered[idx] = ordered[idx].model_copy(update={"running_balance": balance})
    return ordered


def parse_ibc_statement(markdown: str) -> Statement | None:
    if "IBC" not in markdown or "Biz Rite Account Recap" not in markdown:
        return None
    period = _parse_period(markdown)
    summary = _summary(markdown)
    daily = _daily_balances(markdown)
    if period is None or summary is None or not daily:
        return None
    start, end, year = period
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

    deposits = _parse_deposits(markdown, year=year)
    electronic_credits = _parse_electronic_credits(markdown, year=year)
    checks = _parse_checks(markdown, year=year)
    electronic_debits = _parse_electronic_debits(markdown, year=year)
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

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    return Statement(
        bank="IBC Bank",
        account_name="Biz Rite Account",
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning_balance,
        ending_balance=ending_balance,
        stated_total_credits=total_credits,
        stated_total_debits=total_debits,
        stated_credit_count=credit_count,
        stated_debit_count=debit_count,
        stated_service_charge=service_charge,
        stated_average_balance=_average_collected_balance(markdown),
        stated_daily_balances=[
            StatementDailyBalance(
                date=date(year, int(mmdd[:2]), int(mmdd[3:])).isoformat(),
                balance=balance,
            )
            for mmdd, balance in sorted(daily.items())
        ],
        transactions=_with_daily_running_balances(txns, daily, year=year),
    )
