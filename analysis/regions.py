from __future__ import annotations

import re
from datetime import date
from html import unescape

from .date_tokens import iso_from_month_day_strict, period_from_long_dates
from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import TAG_RE, table_rows, tables_after

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
_NATIVE_HEADINGS = (
    "DEPOSITS & CREDITS",
    "WITHDRAWALS",
    "FEES",
    "RETURNED CHECKS",
    "CHECKS",
    "DAILY BALANCE SUMMARY",
)


def _money(value: str) -> float | None:
    text = value.strip().replace("–", "-")
    if not re.search(r"\d+(?:\.\d{2})?", text):
        return None
    neg = text.endswith("-") or text.startswith("-")
    amount = abs(parse_money(re.sub(r"[^0-9,.-]", "", text)) or 0.0)
    return -amount if neg else amount


def _plain_text(markdown: str) -> str:
    text = _IMG_RE.sub("", markdown)
    text = unescape(TAG_RE.sub(" ", text))
    return re.sub(r"[ \t]+", " ", text)


def _tables_after(markdown: str, heading: str) -> list[str]:
    #: Regions repeats the bare heading on each page; no "continued" suffix.
    return tables_after(markdown, heading)


def _parse_section(markdown: str, heading: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for table in _tables_after(markdown, heading):
        for cells in table_rows(table):
            if len(cells) < 3:
                continue
            txn_date = iso_from_month_day_strict(cells[0], year)
            if txn_date is None:
                continue
            amount_idx = next((idx for idx in range(len(cells) - 1, 1, -1) if _money(cells[idx]) is not None), None)
            if amount_idx is None:
                continue
            amount = _money(cells[amount_idx])
            if amount is None:
                continue
            signed = round(abs(amount) * sign, 2)
            txns.append(Transaction(
                date=txn_date,
                description=" ".join(cells[1:amount_idx]).strip(),
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=None,
            ))
    return txns


def _native_chunks(markdown: str, heading: str) -> list[str]:
    heading_re = re.escape(heading)
    start_re = re.compile(rf"(?im)^\s*{heading_re}(?:\s+\(CONTINUED\))?\s*$")
    boundary_re = re.compile(
        r"(?im)^\s*(?:"
        + "|".join(re.escape(h) for h in _NATIVE_HEADINGS)
        + r")(?:\s+\(CONTINUED\))?\s*$|^\s*Total\b|^\s*For all your banking needs\b|^\s*--- Page\b"
    )
    chunks: list[str] = []
    for match in start_re.finditer(markdown):
        start = match.end()
        end_match = boundary_re.search(markdown, start)
        chunks.append(markdown[start:end_match.start() if end_match else len(markdown)])
    return chunks


def _native_rows(markdown: str, heading: str) -> list[str]:
    rows: list[str] = []
    for chunk in _native_chunks(markdown, heading):
        chunk = re.sub(r"(?im)^\s*Date\s+Check\s+No\.\s+Amount\s*", "", chunk)
        parts = re.split(r"\s+(?=\d{2}/\d{2}\s)", chunk.strip())
        for part in parts:
            row = re.split(r"\s+Total\b|For all your banking needs\b", part.strip(), maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if re.match(r"^\d{2}/\d{2}\b", row):
                rows.append(row)
    return rows


def _parse_native_section(markdown: str, heading: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for row in _native_rows(markdown, heading):
        m = re.match(r"^(\d{2}/\d{2})\s+(.+)\s+(\d[\d,]*\.\d{2})(?:\s+\*)?\s*$", row)
        if not m:
            continue
        txn_date = iso_from_month_day_strict(m.group(1), year)
        amount = _money(m.group(3))
        if txn_date is None or amount is None:
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=re.sub(r"\s+", " ", m.group(2)).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def _parse_native_checks(markdown: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for row in _native_rows(markdown, "CHECKS"):
        m = re.match(r"^(\d{2}/\d{2})\s+(\d{3,})\s+\*?\s*(\d[\d,]*\.\d{2})\b", row)
        if m:
            txn_date = iso_from_month_day_strict(m.group(1), year)
            amount = _money(m.group(3))
            description = f"Check {m.group(2)}"
        else:
            m = re.match(r"^(\d{2}/\d{2})\s+(\d[\d,]*\.\d{2})\b", row)
            if not m:
                continue
            txn_date = iso_from_month_day_strict(m.group(1), year)
            amount = _money(m.group(2))
            description = "Check"
        if txn_date is None or amount is None:
            continue
        txns.append(Transaction(
            date=txn_date,
            description=description,
            amount=round(-abs(amount), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return _plain_text(markdown).upper()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "REGIONS" in t),
    required("summary_section", lambda t: "SUMMARY" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_regions_statement(markdown: str) -> Statement | None:
    text = _plain_text(markdown)
    if not detect(markdown).claims:
        return None
    period = period_from_long_dates(text)
    if period is None:
        return None
    year = int(period[1][:4])

    stmt = Statement(bank="Regions Bank", period_start=period[0], period_end=period[1])
    acct = re.search(r"ACCOUNT #\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    name = re.search(r"Page 1 of \d+\s*\n([A-Z][A-Z0-9 &-]+)\s*\n[A-Z][a-z]+ \d{1,2},", text)
    if name:
        stmt.account_name = name.group(1).strip()
    else:
        name = re.search(r"\n([A-Z][A-Z0-9 &/-]+)\s*\n[A-Z][a-z]+ \d{1,2},", text)
        if name:
            stmt.account_name = name.group(1).strip()

    summary_match = re.search(r"SUMMARY\s*(<table>.*?</table>)", markdown, re.IGNORECASE | re.DOTALL)
    if not summary_match:
        stmt = repair_regions_summary(text, stmt)
        txns = []
        txns.extend(_parse_native_section(markdown, "DEPOSITS & CREDITS", year=year, sign=1))
        txns.extend(_parse_native_section(markdown, "WITHDRAWALS", year=year, sign=-1))
        txns.extend(_parse_native_section(markdown, "FEES", year=year, sign=-1))
        txns.extend(_parse_native_section(markdown, "RETURNED CHECKS", year=year, sign=1))
        txns.extend(_parse_native_checks(markdown, year=year))
        if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
            return None
        stmt.transactions = txns
        return stmt

    fees = checks = 0.0
    for cells in table_rows(summary_match.group(1)):
        if len(cells) < 2:
            continue
        label = cells[0].lower()
        amount = _money(cells[1])
        if "beginning balance" in label:
            stmt.beginning_balance = abs(amount) if amount is not None else None
        elif "deposits" in label:
            stmt.stated_total_credits = abs(amount) if amount is not None else None
        elif "withdrawals" in label:
            stmt.stated_total_debits = abs(amount) if amount is not None else None
        elif "fees" in label and amount is not None:
            fees = abs(amount)
            stmt.stated_service_charge = fees
        elif label == "checks" and amount is not None:
            checks = abs(amount)
        elif "ending balance" in label:
            stmt.ending_balance = amount
        if len(cells) >= 4 and "average balance" in cells[2].lower():
            stmt.stated_average_balance = abs(_money(cells[3]) or 0.0)
    if stmt.stated_total_debits is not None:
        stmt.stated_total_debits = round(stmt.stated_total_debits + fees + checks, 2)

    txns = []
    txns.extend(_parse_section(text, "DEPOSITS & CREDITS", year=year, sign=1))
    txns.extend(_parse_section(text, "WITHDRAWALS", year=year, sign=-1))
    txns.extend(_parse_section(text, "FEES", year=year, sign=-1))
    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt


def _money_after(label: str, text: str) -> float | None:
    m = re.search(label + r"\s+\$?([\d,]+(?:\.\d{2})?)(?:\s*(-))?", text, re.IGNORECASE)
    if not m:
        return None
    value = abs(parse_money(m.group(1)) or 0.0)
    return -value if m.group(2) else value


def repair_regions_summary(markdown: str, stmt: Statement) -> Statement:
    """Normalize Regions summary fields, including trailing minus signs."""
    if "REGIONS" not in markdown.upper() or "SUMMARY" not in markdown.upper():
        return stmt

    text = unescape(re.sub(r"<[^>]+>", " ", markdown))
    beginning = _money_after(r"Beginning Balance", text)
    deposits = _money_after(r"Total Deposits & Credits", text) or _money_after(r"Deposits & Credits", text)
    withdrawals = _money_after(r"Total Withdrawals", text) or _money_after(r"Withdrawals", text)
    fees = _money_after(r"Total Fees", text) or _money_after(r"Fees", text)
    returned = _money_after(r"Total Returned Checks", text) or _money_after(r"Returned Checks", text)
    checks = _money_after(r"Total Checks", text) or _money_after(r"(?<!Returned )Checks", text)
    ending = _money_after(r"Ending Balance", text)
    avg = _money_after(r"Average Monthly Statement Balance", text)
    if avg is None:
        avg = _money_after(r"Average Balance", text)

    updates = {}
    if beginning is not None:
        updates["beginning_balance"] = beginning
    if ending is not None:
        updates["ending_balance"] = ending
    if deposits is not None:
        total_credits = abs(deposits) + abs(returned or 0.0)
        updates["stated_total_credits"] = round(total_credits, 2)
    if withdrawals is not None:
        total_debits = abs(withdrawals) + abs(fees or 0.0) + abs(checks or 0.0)
        updates["stated_total_debits"] = round(total_debits, 2)
        updates["stated_service_charge"] = None
    if avg is not None:
        updates["stated_average_balance"] = abs(avg)
    return stmt.model_copy(update=updates) if updates else stmt
