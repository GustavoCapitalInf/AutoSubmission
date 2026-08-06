from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from .money import parse_decimal_mixed_separator
from .schema import Statement, StatementDailyBalance, Transaction


_MONEY = r"\d[\d,]*[\.,]\d{2}"


@dataclass(frozen=True)
class _Row:
    date: date
    description: str
    amount: Decimal
    sequence: int


def _money(value: str) -> Decimal:
    return parse_decimal_mixed_separator(value)


def _section(markdown: str, start: str, stop: str) -> str:
    match = re.search(start + r"(?P<body>.*?)" + stop, markdown, re.IGNORECASE | re.DOTALL)
    return match.group("body") if match else ""


def _clean_description(value: str) -> str:
    text = re.sub(r"^[\s=_~â€”â€“-]+", "", value)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^AGH\b", "ACH", text, flags=re.IGNORECASE)
    text = re.sub(r"^ACH GREDIT\b", "ACH Credit", text, flags=re.IGNORECASE)
    text = re.sub(r"^AGH CREDIT\b", "ACH Credit", text, flags=re.IGNORECASE)
    return text


def _rows(block: str, *, start: date, end: date, sequence: int) -> tuple[list[_Row], int]:
    output: list[_Row] = []
    line_re = re.compile(
        rf"^[^0-9\n]{{0,16}}(?P<month>\d{{2}})-(?P<day>\d{{2}})\b"
        rf"(?P<description>.*?)\s+(?P<amount>{_MONEY})\s*$"
    )
    for raw_line in block.splitlines():
        match = line_re.match(raw_line.strip())
        if not match:
            continue
        raw_month = int(match.group("month"))
        raw_day = int(match.group("day"))
        description = _clean_description(match.group("description"))
        txn_month = raw_month
        txn_day = raw_day
        if raw_month != start.month or not 1 <= raw_month <= 12:
            embedded = re.search(r"\b(20\d{2})(\d{2})(\d{2})\b", description)
            if embedded:
                _, embedded_month, embedded_day = embedded.groups()
                txn_month, txn_day = int(embedded_month), int(embedded_day)
            else:
                txn_month = start.month
        try:
            txn_date = date(end.year, txn_month, txn_day)
        except ValueError:
            continue
        if not start <= txn_date <= end:
            continue
        output.append(
            _Row(
                date=txn_date,
                description=description,
                amount=_money(match.group("amount")),
                sequence=sequence,
            )
        )
        sequence += 1
    return output, sequence


def _counterparty_key(description: str) -> str:
    normalized = re.sub(r"[^A-Z0-9 ]+", " ", description.upper())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"^ACH (?:CREDIT|DEBIT) ", "", normalized)
    tokens: list[str] = []
    for token in normalized.split():
        if any(char.isdigit() for char in token):
            break
        if token in {"ACHPMT", "HCCLAIMPMT", "HCLAIMPMT", "CLAIMPMT", "EDIRPAY"}:
            break
        tokens.append(token)
        if len(tokens) == 3:
            break
    return " ".join(tokens)


def _repair_repeated_amounts(rows: list[_Row], target: Decimal) -> list[_Row]:
    repaired = list(rows)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(repaired):
        groups[_counterparty_key(row.description)].append(index)

    while True:
        current = sum((row.amount for row in repaired), Decimal())
        current_error = abs(current - target)
        best: tuple[Decimal, int, Decimal] | None = None
        for indexes in groups.values():
            counts = Counter(repaired[index].amount for index in indexes)
            mode, frequency = counts.most_common(1)[0]
            if frequency < 3 or frequency * 2 < len(indexes):
                continue
            for index in indexes:
                if repaired[index].amount == mode:
                    continue
                candidate_error = abs(current - repaired[index].amount + mode - target)
                if candidate_error >= current_error:
                    continue
                candidate = (candidate_error, index, mode)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            return repaired
        _, index, mode = best
        repaired[index] = replace(repaired[index], amount=mode)


def _daily_snapshots(block: str, *, year: int) -> dict[date, Decimal]:
    snapshots: dict[date, Decimal] = {}
    for month, day, amount in re.findall(rf"(\d{{2}})-(\d{{2}})\s+({_MONEY})", block):
        try:
            snapshots[date(year, int(month), int(day))] = _money(amount)
        except ValueError:
            continue
    return snapshots


def _ending_by_date(opening: Decimal, rows: list[tuple[_Row, int]]) -> dict[date, Decimal]:
    balance = opening
    output: dict[date, Decimal] = {}
    for row, sign in sorted(rows, key=lambda item: (item[0].date, item[0].sequence)):
        balance += row.amount * sign
        output[row.date] = balance
    return output


def _repair_single_section_delta(
    debit_rows: list[_Row],
    *,
    target: Decimal,
    opening: Decimal,
    all_credit_rows: list[_Row],
    other_debits: list[_Row],
    checks: list[_Row],
    snapshots: dict[date, Decimal],
) -> list[_Row] | None:
    current = sum((row.amount for row in debit_rows), Decimal())
    delta = current - target
    if delta == 0:
        return debit_rows

    groups: dict[str, list[_Row]] = defaultdict(list)
    for row in debit_rows:
        groups[_counterparty_key(row.description)].append(row)

    candidates: list[tuple[int, int, list[_Row]]] = []
    for index, row in enumerate(debit_rows):
        related = groups[_counterparty_key(row.description)]
        mode, frequency = Counter(item.amount for item in related).most_common(1)[0]
        if frequency >= 3 and frequency * 2 >= len(related) and row.amount == mode:
            continue
        candidate_amount = row.amount - delta
        if candidate_amount <= 0 or candidate_amount.as_tuple().exponent != -2:
            continue
        candidate_rows = list(debit_rows)
        candidate_rows[index] = replace(row, amount=candidate_amount)
        signed_rows = (
            [(item, 1) for item in all_credit_rows]
            + [(item, -1) for item in candidate_rows]
            + [(item, -1) for item in other_debits]
            + [(item, -1) for item in checks]
        )
        reconstructed = _ending_by_date(opening, signed_rows)
        score = sum(reconstructed.get(day) == amount for day, amount in snapshots.items())
        candidates.append((score, -index, candidate_rows))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    if candidates[0][0] < max(3, len(snapshots) * 3 // 4):
        return None
    return candidates[0][2]


def parse_columbia_bank_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if (
        "COLUMBIA BANK" not in upper
        or "MARKETPLACE CHECKING" not in upper
        or "DEPOSITS/ADDITIONS" not in upper
        or "DAILY BALANCES" not in upper
    ):
        return None

    dates = re.search(
        r"Last statement:\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s+"
        r"This statement:\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
        markdown,
    )
    summary = re.search(
        rf"Account number\s+([X\d]+)\s+Beginning balance\s+\$?({_MONEY})\s+"
        rf"Low balance\s+\$?({_MONEY})\s+Deposits/Additions\s+\$?({_MONEY})\s+"
        rf"Average balance\s+\$?({_MONEY})\s+Withdrawals/Subtractions\s+\$?({_MONEY})\s+"
        rf".*?Interest earned\s+\$?({_MONEY})\s+Ending balance\s+\$?({_MONEY})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not dates or not summary:
        return None

    previous_end = datetime.strptime(dates.group(1), "%B %d, %Y").date()
    period_end = datetime.strptime(dates.group(2), "%B %d, %Y").date()
    period_start = previous_end + timedelta(days=1)
    account, opening_raw, _low, credits_raw, average_raw, debits_raw, interest_raw, ending_raw = summary.groups()
    opening = _money(opening_raw)
    ending = _money(ending_raw)
    total_credits = _money(credits_raw)
    total_debits = _money(debits_raw)

    deposit_block = _section(
        markdown,
        r"Deposits/Additions\s+Date Description Additions",
        r"Total Additions",
    )
    ach_debit_block = _section(
        markdown,
        r"ACH and Electronic Payments/Subtractions\s+Date Description Subtractions",
        r"Total ACH and Electronic Payments/Subtractions",
    )
    ach_credit_block = _section(
        markdown,
        r"ACH and Electronic Deposits/Additions\s+Date Description Additions",
        r"Total ACH and Electronic Deposits/Additions",
    )
    other_debit_block = _section(
        markdown,
        r"Other Withdrawals/Subtractions\s+Date Description Subtractions",
        r"Total Other Withdrawals/Subtractions",
    )
    daily_block = _section(markdown, r"Daily Balances", r"Overdraft Fee Summary")
    checks_block = _section(markdown, r"Checks\s+Check # Amount Date", r"\(\* Skip in check sequence")
    if not all((deposit_block, ach_debit_block, ach_credit_block, other_debit_block, daily_block, checks_block)):
        return None

    sequence = 0
    deposits, sequence = _rows(deposit_block, start=period_start, end=period_end, sequence=sequence)
    ach_debits, sequence = _rows(ach_debit_block, start=period_start, end=period_end, sequence=sequence)
    ach_credits, sequence = _rows(ach_credit_block, start=period_start, end=period_end, sequence=sequence)
    other_debits, sequence = _rows(other_debit_block, start=period_start, end=period_end, sequence=sequence)

    checks: list[_Row] = []
    for check_number, amount, month, day in re.findall(
        rf"(\d{{3,}})\s+\$?({_MONEY})\s+(\d{{2}})-(\d{{2}})", checks_block
    ):
        checks.append(
            _Row(
                date=date(period_end.year, int(month), int(day)),
                description=f"Check {check_number}",
                amount=_money(amount),
                sequence=sequence,
            )
        )
        sequence += 1

    ach_debit_total_match = re.search(
        rf"Total ACH and Electronic Payments/Subtractions\s+\$?({_MONEY})", markdown,
        re.IGNORECASE,
    )
    ach_credit_total_match = re.search(
        rf"Total ACH and Electronic Deposits/Additions\s+\$?({_MONEY})", markdown,
        re.IGNORECASE,
    )
    other_total_match = re.search(
        rf"Total Other Withdrawals/Subtractions\s+\$?({_MONEY})", markdown,
        re.IGNORECASE,
    )
    if not ach_debit_total_match or not ach_credit_total_match or not other_total_match:
        return None
    ach_debit_total = _money(ach_debit_total_match.group(1))
    ach_credit_total = _money(ach_credit_total_match.group(1))
    other_total = _money(other_total_match.group(1))

    ach_debits = _repair_repeated_amounts(ach_debits, ach_debit_total)
    ach_credits = _repair_repeated_amounts(ach_credits, ach_credit_total)
    snapshots = _daily_snapshots(daily_block, year=period_end.year)
    ach_debits = _repair_single_section_delta(
        ach_debits,
        target=ach_debit_total,
        opening=opening,
        all_credit_rows=deposits + ach_credits,
        other_debits=other_debits,
        checks=checks,
        snapshots=snapshots,
    )
    if ach_debits is None:
        return None

    if sum((row.amount for row in deposits), Decimal()) + ach_credit_total != total_credits:
        return None
    if sum((row.amount for row in ach_debits), Decimal()) != ach_debit_total:
        return None
    if sum((row.amount for row in ach_credits), Decimal()) != ach_credit_total:
        return None
    if sum((row.amount for row in other_debits), Decimal()) != other_total:
        return None
    if ach_debit_total + other_total + sum((row.amount for row in checks), Decimal()) != total_debits:
        return None

    signed_rows = (
        [(row, 1) for row in deposits + ach_credits]
        + [(row, -1) for row in ach_debits + other_debits + checks]
    )
    reconstructed = _ending_by_date(opening, signed_rows)
    if not reconstructed or reconstructed[max(reconstructed)] != ending:
        return None

    ordered = sorted(signed_rows, key=lambda item: (item[0].date, item[0].sequence))
    last_index_by_date: dict[date, int] = {}
    transactions: list[Transaction] = []
    for row, sign in ordered:
        amount = row.amount * sign
        last_index_by_date[row.date] = len(transactions)
        transactions.append(
            Transaction(
                date=row.date.isoformat(),
                description=row.description,
                amount=float(amount),
                direction="credit" if amount > 0 else "debit",
            )
        )
    for txn_date, index in last_index_by_date.items():
        transactions[index] = transactions[index].model_copy(
            update={"running_balance": float(reconstructed[txn_date])}
        )

    daily_evidence: list[StatementDailyBalance] = []
    for snapshot_date in sorted(snapshots):
        if not period_start <= snapshot_date <= period_end:
            continue
        amount = reconstructed.get(snapshot_date, snapshots[snapshot_date])
        daily_evidence.append(
            StatementDailyBalance(date=snapshot_date.isoformat(), balance=float(amount))
        )

    name = re.search(r"\n([A-Z][A-Z ]+ (?:PLLC|LLC))\s*\n", markdown)
    return Statement(
        bank="Columbia Bank",
        account_name=(
            f"{name.group(1).title()} - Marketplace Checking" if name else "Marketplace Checking"
        ),
        account_number=account,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        days_in_period=(period_end - period_start).days + 1,
        beginning_balance=float(opening),
        ending_balance=float(ending),
        stated_total_credits=float(total_credits),
        stated_total_debits=float(total_debits),
        stated_average_balance=float(_money(average_raw)),
        stated_interest_paid=float(_money(interest_raw)),
        stated_daily_balances=daily_evidence,
        transactions=transactions,
    )
