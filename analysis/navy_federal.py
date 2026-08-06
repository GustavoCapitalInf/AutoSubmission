from __future__ import annotations

import re
from datetime import date

from .money import STRICT_EITHER_MINUS_OR_PLUS_SPACED, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_EITHER_MINUS_OR_PLUS_SPACED)


def _is_date(line: str) -> bool:
    return re.fullmatch(r"\d{2}-\d{2}", line) is not None


def _parse_period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(r"Statement Period\s+(\d{2})/(\d{2})/(\d{2})\s+-\s+(\d{2})/(\d{2})/(\d{2})", markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = [int(part) for part in m.groups()]
    start = date(2000 + sy, sm, sd)
    end = date(2000 + ey, em, ed)
    return start.isoformat(), end.isoformat(), end.year


def _summary(markdown: str) -> tuple[str, float, float, float, float] | None:
    flat = re.sub(r"\s+", " ", markdown)
    m = re.search(
        r"Business Checking\s+(\d+)\s+"
        r"(\$?[\d,]+\.\d{2}-?)\s+(\$?[\d,]+\.\d{2})\s+"
        r"(\$?[\d,]+\.\d{2})\s+(\$?[\d,]+\.\d{2}-?)\s+\$?[\d,]+\.\d{2}",
        flat,
    )
    if not m:
        return None
    account, beginning, credits, debits, ending = m.groups()
    parsed = (_money(beginning), _money(credits), _money(debits), _money(ending))
    if any(value is None for value in parsed):
        return None
    return account, parsed[0], parsed[1], parsed[2], parsed[3]  # type: ignore[return-value]


def _average_balance(markdown: str) -> float | None:
    m = re.search(r"Average Daily Balance - Current Cycle:\s+\$?([\d,]+\.\d{2}-?)", markdown)
    return _money(m.group(1)) if m else None


def _checking_section(markdown: str, account: str) -> str:
    start = markdown.find(f"Business Checking - {account}")
    if start < 0:
        return ""
    candidates = [
        markdown.find("Mbr Business Savings", start),
        markdown.find("Bus Money Mkt Savings", start),
        markdown.find("Checking Line", start),
        markdown.find("Disclosure", start),
    ]
    stops = [idx for idx in candidates if idx > start]
    end = min(stops) if stops else len(markdown)
    return markdown[start:end]


def _line_is_noise(line: str, account: str) -> bool:
    return (
        line.startswith("---")
        or line.startswith("Page ")
        or line.startswith("Statement Period")
        or line.startswith("Access No")
        or line.startswith("For ")
        or line.startswith("(Continued")
        or line == f"Business Checking - {account}"
        or line in {"Date", "Transaction Detail", "Amount($)", "Balance($)", "Items Paid", "Item"}
        or line.startswith("Average Daily Balance")
    )


def _amount_balance(line: str) -> tuple[float, float] | None:
    m = re.fullmatch(r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})(?:\s+(-))?", line)
    if m:
        amount = _money(m.group(1))
        balance = _money(m.group(2) + (m.group(3) or ""))
        if amount is not None and balance is not None:
            return amount, balance
    return None


def _separate_amount_balance(lines: list[str], idx: int) -> tuple[float, float, int] | None:
    if idx + 1 >= len(lines):
        return None
    if not re.fullmatch(r"[\d,]+\.\d{2}", lines[idx]):
        return None
    if not re.fullmatch(r"[\d,]+\.\d{2}(?:\s+-)?", lines[idx + 1]):
        return None
    amount = _money(lines[idx])
    balance = _money(lines[idx + 1])
    if amount is None or balance is None:
        return None
    return amount, balance, idx + 2


def _consume_following_date_desc(lines: list[str], idx: int) -> tuple[str, str, int] | None:
    if idx >= len(lines) or not _is_date(lines[idx]):
        return None
    txn_date = lines[idx]
    idx += 1
    parts: list[str] = []
    while idx < len(lines):
        line = lines[idx]
        if (
            _is_date(line)
            or line == "-"
            or "Ending Balance" in line
            or _amount_balance(line) is not None
            or re.fullmatch(r"[\d,]+\.\d{2}(?:\s+-)?", line)
        ):
            break
        parts.append(line)
        idx += 1
    return txn_date, " ".join(parts), idx


def _parse_native_transactions(
    markdown: str, account: str, *, year: int, beginning: float
) -> list[Transaction] | None:
    txns: list[Transaction] = []
    prev_balance = beginning
    for line in markdown.splitlines():
        if not line.startswith("NFCU_TX|"):
            continue
        parts = line.split("|", 5)
        if len(parts) != 6 or parts[1] != account:
            continue
        _, _, txn_date, printed_amount, printed_balance, description = parts
        if not _is_date(txn_date):
            return None
        amount = _money(printed_amount)
        balance = _money(printed_balance)
        if amount is None or balance is None:
            return None
        signed = round(balance - prev_balance, 2)
        if abs(abs(signed) - abs(amount)) > 0.01:
            return None
        txns.append(
            Transaction(
                date=date(year, int(txn_date[:2]), int(txn_date[3:])).isoformat(),
                description=re.sub(r"\s+", " ", description).strip()
                or "Navy Federal transaction",
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=balance,
            )
        )
        prev_balance = balance
    return txns or None


def _parse_transactions(section: str, account: str, *, year: int, beginning: float) -> list[Transaction] | None:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    lines = [line for line in lines if not _line_is_noise(line, account)]

    idx = 0
    while idx < len(lines):
        if (
            re.fullmatch(r"[\d,]+\.\d{2}-?", lines[idx])
            and idx + 2 < len(lines)
            and _is_date(lines[idx + 1])
            and lines[idx + 2] == "Beginning Balance"
        ):
            parsed_beginning = _money(lines[idx])
            if parsed_beginning is None or abs(parsed_beginning - beginning) > 0.01:
                return None
            idx += 3
            break
        idx += 1
    else:
        return None

    prev_balance = beginning
    current_date: str | None = None
    desc_parts: list[str] = []
    txns: list[Transaction] = []

    while idx < len(lines):
        line = lines[idx]
        if _is_date(line):
            current_date = line
            desc_parts = []
            idx += 1
            continue
        if line == "-":
            idx += 1
            continue
        if "Ending Balance" in line:
            break

        pair = _amount_balance(line)
        next_idx = idx + 1
        if pair is None:
            separate = _separate_amount_balance(lines, idx)
            if separate is not None:
                amount, balance, next_idx = separate
                pair = amount, balance

        if pair is not None:
            amount, balance = pair
            if next_idx < len(lines) and lines[next_idx] == "-":
                next_idx += 1
            signed = round(balance - prev_balance, 2)
            if abs(abs(signed) - abs(amount)) > 0.01:
                return None

            txn_date = current_date
            description = " ".join(desc_parts).strip()
            # Compatibility path for OCR text without native layout markers.
            # Digitally generated Navy Federal PDFs use the coordinate-aware rows
            # above, where date and description ownership is explicit.
            if signed > 0:
                following = _consume_following_date_desc(lines, next_idx)
                if following is not None:
                    txn_date, description, next_idx = following
                    current_date = txn_date
            if txn_date is None:
                return None
            description = re.sub(r"\s+", " ", description).strip() or "Navy Federal transaction"
            txns.append(
                Transaction(
                    date=date(year, int(txn_date[:2]), int(txn_date[3:])).isoformat(),
                    description=description,
                    amount=signed,
                    direction="credit" if signed >= 0 else "debit",
                    running_balance=balance,
                )
            )
            prev_balance = balance
            desc_parts = []
            idx = next_idx
            continue

        desc_parts.append(line)
        idx += 1

    return txns


DETECTION_MARKERS = (
    required("bank_name", lambda t: "Navy Federal" in t),
    required("section", lambda t: "Summary of your deposit accounts" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_navy_federal_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _parse_period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None
    start, end, year = period
    account, beginning, credits, debits, ending_balance = summary
    section = _checking_section(markdown, account)
    if not section:
        return None
    if "NFCU_NATIVE_TRANSACTIONS_BEGIN" in markdown:
        txns = _parse_native_transactions(markdown, account, year=year, beginning=beginning)
    else:
        txns = _parse_transactions(section, account, year=year, beginning=beginning)
    if not txns:
        return None
    if abs(sum(tx.amount for tx in txns if tx.amount > 0) - credits) > 0.01:
        return None
    if abs(-sum(tx.amount for tx in txns if tx.amount < 0) - debits) > 0.01:
        return None
    if abs((txns[-1].running_balance or 0.0) - ending_balance) > 0.01:
        return None

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    stmt = Statement(
        bank="Navy Federal Credit Union",
        account_name="Business Checking",
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning,
        ending_balance=ending_balance,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_average_balance=_average_balance(section),
        transactions=txns,
    )
    return stmt
