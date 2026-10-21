from __future__ import annotations

import re
from datetime import date

from .money import parse_trailing_minus_dropped
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace


_MONEY_RE = re.compile(r"\$?\d[\d,]*\.\d{2}-?")


def _money(value: str) -> float:
    return parse_trailing_minus_dropped(value)


def _summary(markdown: str) -> tuple[str, str, str, int, float, int, float, float, float] | None:
    m = re.search(
        r"Date Range:\s*(\d{2})/(\d{2})/(\d{4})\s+-\s+(\d{2})/(\d{2})/(\d{4}).*?"
        r"FREE BUSINESS CHECKING ID (\d+) Beginning Balance\s+\$?([\d,]+\.\d{2})-\s+"
        r"(\d+)\s+Total Deposits for\s+([\d,]+\.\d{2})-\s+"
        r"(\d+)\s+Total Withdrawals for\s+([\d,]+\.\d{2})-\s+"
        r"Ending Balance\s+\$?([\d,]+\.\d{2})-",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    sm, sd, sy, em, ed, ey, account, beginning, dep_count, dep_total, wd_count, wd_total, ending = m.groups()
    start = date(int(sy), int(sm), int(sd)).isoformat()
    end = date(int(ey), int(em), int(ed)).isoformat()
    return (
        start,
        end,
        account,
        int(dep_count),
        _money(dep_total),
        int(wd_count),
        _money(wd_total),
        _money(beginning),
        _money(ending),
    )


def _business_checking_block(markdown: str, account: str) -> str:
    marker = f"FREE BUSINESS CHECKING ID {account} Beginning Balance"
    start = markdown.find(marker)
    if start < 0:
        return ""
    block = marker + markdown[start + len(marker):]
    end = block.find("Fees Paid")
    return block[:end] if end > 0 else block


def _row_starts(block: str, month: int) -> list[re.Match[str]]:
    return list(
        re.finditer(
            rf"\b{month:02d}/\d{{2}}\s+(?:Recurring\s+)?(?:Deposit|Withdrawal|Draft)\b",
            block,
            re.IGNORECASE,
        )
    )


def _clean_row(row: str) -> str:
    return re.split(
        r"Page \d+ of \d+|--- Page|Member Number:|Account Statement|Summary by Check Number|Fees Paid",
        row,
    )[0]


def _choose_signed_values(
    label: str,
    raw_amount: float,
    raw_balance: float,
    previous_balance: float,
) -> tuple[float, float] | None:
    amount_candidates = [raw_amount, -raw_amount] if "Deposit" in label else [-raw_amount, raw_amount]
    for amount in amount_candidates:
        for balance in (raw_balance, -raw_balance):
            if abs(round(previous_balance + amount, 2) - balance) <= 0.01:
                return round(amount, 2), round(balance, 2)
    return None


def _description(row: str, label_match: re.Match[str], amount_token: str) -> str:
    rest = row[label_match.end() - label_match.start():]
    amount_idx = rest.rfind(amount_token)
    if amount_idx > 0:
        rest = rest[:amount_idx]
    desc = compact_whitespace(rest)
    return desc or label_match.group(0).split(None, 1)[-1]


def _parse_transactions(
    block: str,
    *,
    month: int,
    year: int,
    beginning_balance: float,
    ending_balance: float,
    expected_total_rows: int,
) -> list[Transaction] | None:
    starts = _row_starts(block, month)
    if len(starts) != expected_total_rows:
        return None

    txns: list[Transaction] = []
    previous_balance = beginning_balance
    for idx, start in enumerate(starts):
        row = _clean_row(block[start.start():starts[idx + 1].start() if idx + 1 < len(starts) else len(block)])
        money = _MONEY_RE.findall(row)
        if len(money) < 2:
            return None
        raw_amount = _money(money[-2])
        raw_balance = _money(money[-1])
        signed = _choose_signed_values(start.group(0), raw_amount, raw_balance, previous_balance)
        if signed is None:
            return None
        amount, balance = signed
        mm, dd = [int(part) for part in start.group(0)[:5].split("/")]
        txns.append(
            Transaction(
                date=date(year, mm, dd).isoformat(),
                description=_description(row, start, money[-2]),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
                running_balance=balance,
            )
        )
        previous_balance = balance

    if not txns or abs((txns[-1].running_balance or 0.0) - ending_balance) > 0.01:
        return None
    return txns


DETECTION_MARKERS = (
    required("domain", lambda t: "altanafcu.org" in t),
    required("product", lambda t: "FREE BUSINESS CHECKING ID" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_altana_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    if summary is None:
        return None
    start, end, account, deposit_count, deposit_total, withdrawal_count, withdrawal_total, beginning, ending = summary
    block = _business_checking_block(markdown, account)
    if not block:
        return None

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    txns = _parse_transactions(
        block,
        month=start_date.month,
        year=start_date.year,
        beginning_balance=beginning,
        ending_balance=ending,
        expected_total_rows=deposit_count + withdrawal_count,
    )
    if txns is None:
        return None

    label_deposits = 0
    label_withdrawals = 0
    label_deposit_total = 0.0
    row_labels = _row_starts(block, start_date.month)
    for idx, label in enumerate(row_labels):
        row = _clean_row(block[label.start():row_labels[idx + 1].start() if idx + 1 < len(row_labels) else len(block)])
        money = _MONEY_RE.findall(row)
        raw_amount = _money(money[-2])
        if "Deposit" in label.group(0):
            label_deposits += 1
            label_deposit_total += raw_amount
        else:
            label_withdrawals += 1

    if label_deposits != deposit_count or abs(round(label_deposit_total, 2) - deposit_total) > 0.01:
        return None
    if label_withdrawals != withdrawal_count:
        return None

    stmt = Statement(
        bank="Altana Federal Credit Union",
        account_name="Free Business Checking",
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        transactions=txns,
    )
    # The statement's withdrawal summary is label-based and excludes some balance-
    # increasing adjustment rows. Keep true underwriting totals from line items.
    stmt.stated_credit_count = deposit_count
    stmt.stated_debit_count = withdrawal_count
    return stmt
