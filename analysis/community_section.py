from __future__ import annotations

import re
from datetime import datetime

from .schema import Statement, Transaction


_DATE = r"\d{2}/\d{2}/\d{4}"
_MONEY = r"\$[\d,]+\.\d{2}"


def _money(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    return float(text)


def _iso(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat()


def _clean(text: str) -> str:
    text = re.sub(r"--- Page \d+ ---", " ", text)
    text = re.sub(r"\b[A-F0-9]{32}\b \d{8} [A-Za-z ]+", " ", text)
    text = re.sub(r"\b(?:GREEN CONVERGENCE|FIELD TRUCKING LLC).*?Page \d+ of \d+", " ", text)
    text = re.sub(r"Account Number:\s*[X0-9]+", " ", text)
    text = re.sub(r"(?:Business Checking|Small Business Checking) - [X0-9]+ \(continued\)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _account_block(markdown: str, account_heading: str | None = None) -> str:
    if not account_heading:
        return markdown
    start = markdown.find(account_heading)
    if start == -1:
        return ""
    return markdown[start:]


def _summary(block: str):
    return re.search(
        r"Account Summary Date Description Amount\s+"
        r"(" + _DATE + r") Beginning (?:Statement )?Balance (" + _MONEY + r")\s+"
        r"(\d+) Credit\(s\) This Period (" + _MONEY + r")\s+"
        r"(\d+) Debit\(s\) This Period (" + _MONEY + r")\s+"
        r"(" + _DATE + r") Ending (?:Statement )?Balance (" + _MONEY + r")",
        _clean(block),
        re.IGNORECASE | re.DOTALL,
    )


def _section_bodies(text: str, headers: list[str], stops: list[str]) -> list[str]:
    header = r"(?:" + "|".join(headers) + r")"
    stop = r"(?:" + "|".join(stops) + r")"
    pattern = header + r"\s+Date Description Amount\s+(.*?)(?=\s+" + stop + r"\s+(?:Date|Check|Total|$)|$)"
    return [m.group(1) for m in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)]


def _dated_amount_rows(body: str, *, sign: int, year: int) -> list[Transaction]:
    text = _clean(body)
    dates = list(re.finditer(r"\b" + _DATE + r"\b", text))
    txns: list[Transaction] = []
    for i, match in enumerate(dates):
        end = dates[i + 1].start() if i + 1 < len(dates) else len(text)
        chunk = text[match.start():end].strip()
        amounts = list(re.finditer(_MONEY, chunk))
        if not amounts:
            continue
        amount_match = amounts[-1]
        desc = re.sub(r"\s+", " ", chunk[len(match.group()):amount_match.start()]).strip()
        amount = _money(amount_match.group())
        if amount is None:
            continue
        if datetime.strptime(match.group(), "%m/%d/%Y").year != year:
            return []
        txns.append(
            Transaction(
                date=_iso(match.group()),
                description=desc,
                amount=round(sign * amount, 2),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return txns


def _check_rows(block: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for section in re.finditer(
        r"Checks Cleared\s+(.*?)(?=\s+(?:Daily Balances|Overdraft and Returned Item Fees|Service Charge Summary|Thank you)|$)",
        block,
        re.IGNORECASE | re.DOTALL,
    ):
        body = _clean(section.group(1))
        for match in re.finditer(r"(\d+\*?)\s+(" + _DATE + r")\s+(" + _MONEY + r")", body):
            amount = _money(match.group(3))
            if amount is None:
                continue
            if datetime.strptime(match.group(2), "%m/%d/%Y").year != year:
                return []
            txns.append(
                Transaction(
                    date=_iso(match.group(2)),
                    description=f"Check {match.group(1)}",
                    amount=round(-amount, 2),
                    direction="debit",
                )
            )
    return txns


def _daily_balances(block: str) -> dict[str, float]:
    start = re.search(r"Daily Balances\b(.*?)(?:Overdraft and Returned Item Fees|Service Charge Summary|Thank you|$)", block, re.IGNORECASE | re.DOTALL)
    if not start:
        return {}
    balances: dict[str, float] = {}
    for match in re.finditer(r"(" + _DATE + r")\s+(" + _MONEY + r")", _clean(start.group(1))):
        amount = _money(match.group(2))
        if amount is not None:
            balances[_iso(match.group(1))] = amount
    return balances


def _apply_daily_balances(txns: list[Transaction], balances: dict[str, float]) -> list[Transaction]:
    if not balances:
        return txns
    last_index: dict[str, int] = {}
    for i, txn in enumerate(txns):
        last_index[txn.date] = i
    updated = list(txns)
    for txn_date, balance in balances.items():
        idx = last_index.get(txn_date)
        if idx is not None:
            updated[idx] = updated[idx].model_copy(update={"running_balance": balance})
    return updated


def _parse_sectioned_statement(
    markdown: str,
    *,
    bank: str,
    account_name: str,
    account_heading: str | None = None,
    account_number_pattern: str | None = None,
) -> Statement | None:
    block = _account_block(markdown, account_heading)
    if not block:
        return None
    summary = _summary(block)
    if not summary:
        return None
    start_date, beginning, credit_count, credits, debit_count, debits, end_date, ending = summary.groups()
    start_year = datetime.strptime(start_date, "%m/%d/%Y").year
    end_year = datetime.strptime(end_date, "%m/%d/%Y").year
    if start_year != end_year:
        return None

    txns: list[Transaction] = []
    for body in _section_bodies(
        block,
        [r"Deposits(?: \(continued\))?", r"Other Credits(?: \(continued\))?"],
        [r"Other Credits", r"Electronic Debits", r"Other Debits", r"Checks Cleared", r"Daily Balances", r"Overdraft", r"Service Charge Summary", r"Thank you"],
    ):
        txns.extend(_dated_amount_rows(body, sign=1, year=end_year))
    for body in _section_bodies(
        block,
        [r"Electronic Debits(?: \(continued\))?", r"Other Debits(?: \(continued\))?"],
        [r"Other Debits", r"Checks Cleared", r"Daily Balances", r"Overdraft", r"Service Charge Summary", r"Thank you"],
    ):
        txns.extend(_dated_amount_rows(body, sign=-1, year=end_year))
    txns.extend(_check_rows(block, year=end_year))
    if not txns:
        return None
    txns.sort(key=lambda t: t.date)

    stmt = Statement(
        bank=bank,
        account_name=account_name,
        account_number=None,
        period_start=_iso(start_date),
        period_end=_iso(end_date),
        days_in_period=(datetime.strptime(end_date, "%m/%d/%Y").date() - datetime.strptime(start_date, "%m/%d/%Y").date()).days + 1,
        beginning_balance=_money(beginning),
        ending_balance=_money(ending),
        stated_total_credits=_money(credits),
        stated_total_debits=_money(debits),
        stated_credit_count=int(credit_count),
        stated_debit_count=int(debit_count),
        transactions=_apply_daily_balances(txns, _daily_balances(block)),
    )
    if account_number_pattern:
        acct = re.search(account_number_pattern, block, re.IGNORECASE)
        if acct:
            stmt.account_number = acct.group(1)

    credit_total = round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2)
    debit_total = round(sum(abs(t.amount) for t in stmt.transactions if t.amount < 0), 2)
    credit_rows = sum(1 for t in stmt.transactions if t.amount > 0)
    debit_rows = sum(1 for t in stmt.transactions if t.amount < 0)
    if (
        abs(credit_total - (stmt.stated_total_credits or 0.0)) > 0.02
        or abs(debit_total - (stmt.stated_total_debits or 0.0)) > 0.02
        or credit_rows != stmt.stated_credit_count
        or debit_rows != stmt.stated_debit_count
    ):
        return None
    return stmt


def parse_mission_valley_statement(markdown: str) -> Statement | None:
    if "Mission Valley Bank" not in markdown or "GREEN CONVERGENCE" not in markdown:
        return None
    return _parse_sectioned_statement(
        markdown,
        bank="Mission Valley Bank",
        account_name="Business Checking",
        account_number_pattern=r"Business Checking\s*-\s*([X0-9]+)",
    )


def parse_dakota_west_statement(markdown: str) -> Statement | None:
    if "dakotawestcu.com" not in markdown.lower() or "Small Business Checking - 35127380" not in markdown:
        return None
    return _parse_sectioned_statement(
        markdown,
        bank="Dakota West Credit Union",
        account_name="Small Business Checking",
        account_heading="Small Business Checking - 35127380",
        account_number_pattern=r"Small Business Checking\s*-\s*(\d+)",
    )
