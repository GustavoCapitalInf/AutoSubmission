from __future__ import annotations

import re
from datetime import date, timedelta

from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.startswith("-") or text.endswith("-")
    text = text.replace("-", "").strip()
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _iso(mmdd: str, year: int) -> str:
    month, day = [int(part) for part in mmdd.split("/", 1)]
    return date(year, month, day).isoformat()


def _summary(markdown: str) -> tuple[Statement, int] | None:
    m = re.search(
        r"(?:TRUIST\s+)?[A-Z0-9 ]+CHECKING[^\n]*?\s+(\d{4,})\s+"
        r"Account summary Your previous balance as of (\d{2})/(\d{2})/(\d{4})\s+\$?(-?[\d,]+\.\d{2})\s+"
        r"Checks\s+-\s+([\d,]+\.\d{2})\s+"
        r"Other withdrawals, debits and service charges\s+-\s+([\d,]+\.\d{2})\s+"
        r"Deposits, credits and interest\s+\+\s+([\d,]+\.\d{2})\s+"
        r"Your new balance as of (\d{2})/(\d{2})/(\d{4})\s+=\s+\$?(-?[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    acct, sm, sd, sy, beginning, checks, other_debits, credits, em, ed, ey, ending = m.groups()
    start = date(int(sy), int(sm), int(sd)) + timedelta(days=1)
    end = date(int(ey), int(em), int(ed))
    stmt = Statement(
        bank="Truist",
        account_name="Checking",
        account_number=acct,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        beginning_balance=_money(beginning),
        ending_balance=_money(ending),
        stated_total_credits=abs(_money(credits) or 0.0),
        stated_total_debits=round(abs(_money(checks) or 0.0) + abs(_money(other_debits) or 0.0), 2),
    )
    return stmt, end.year


def _first_account_block(markdown: str) -> str:
    starts = list(re.finditer(
        r"(?:TRUIST\s+)?[A-Z0-9 \-]+CHECKING[^\n]*?\d{4,}\s+Account summary",
        markdown,
        re.IGNORECASE,
    ))
    for idx, start in enumerate(starts):
        next_start = starts[idx + 1].start() if idx + 1 < len(starts) else len(markdown)
        block = markdown[start.start():next_start]
        if "Account summary Your previous balance" in block:
            return block
    return markdown


def _section(block: str, heading: str, total_label: str) -> tuple[str, float | None]:
    pattern = re.compile(
        rf"{re.escape(heading)}\s+DATE .*? AMOUNT\(\$\)\s+(.*?)\s+{re.escape(total_label)}\s*=\s*\$?([\d,]+\.\d{{2}})",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(block)
    if not m:
        return "", None
    return m.group(1), abs(_money(m.group(2)) or 0.0)


def _parse_dated_amount_rows(text: str, *, year: int, sign: int) -> list[Transaction]:
    text = re.sub(
        r"\s+continued\s+.*?--- Page \d+ ---\s+.*?\(continued\)\s+DATE DESCRIPTION AMOUNT\(\$\)\s+",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    clean = re.sub(r"Â§ PAGE\s+\d+\s+OF\s+\d+\s+\d*", " ", text)
    clean = re.sub(r"\s+\d+\s+Â?§\s+", " ", clean)
    clean = re.sub(r"Page \d+ of \d+ [0-9/]+ [A-Z]{2} \d+", " ", clean)
    clean = re.sub(r"\bcontinued\b", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    rows = re.split(r"\s+(?=\d{2}/\d{2}\s+)", clean)
    txns: list[Transaction] = []
    for row in rows:
        m = re.match(r"^(\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s*$", row)
        if not m:
            continue
        amount = _money(m.group(3))
        if amount is None:
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=_iso(m.group(1), year),
            description=re.sub(r"\s+", " ", m.group(2)).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def _parse_checks(block: str, *, year: int) -> list[Transaction]:
    m = re.search(r"Checks\s+DATE CHECK # AMOUNT\(\$\)(.*?)Total checks\s*=\s*\$?([\d,]+\.\d{2})", block, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    text = re.sub(r"\* indicates.*", " ", m.group(1), flags=re.IGNORECASE | re.DOTALL)
    txns: list[Transaction] = []
    for mmdd, check_no, amount in re.findall(r"(\d{2}/\d{2})\s+(\*?\d+~?)\s+([\d,]+\.\d{2})", text):
        txns.append(Transaction(
            date=_iso(mmdd, year),
            description=f"Check {check_no}",
            amount=round(-abs(_money(amount) or 0.0), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def parse_truist_statement(markdown: str) -> Statement | None:
    if "TRUIST" not in markdown.upper() or "Account summary Your previous balance" not in markdown:
        return None
    block = _first_account_block(markdown)
    parsed_summary = _summary(block)
    if parsed_summary is None:
        return None
    stmt, year = parsed_summary

    checks = _parse_checks(block, year=year)
    other_text, other_total = _section(
        block,
        "Other withdrawals, debits and service charges",
        "Total other withdrawals, debits and service charges",
    )
    credit_text, credit_total = _section(
        block,
        "Deposits, credits and interest",
        "Total deposits, credits and interest",
    )
    other = _parse_dated_amount_rows(other_text, year=year, sign=-1)
    credits = _parse_dated_amount_rows(credit_text, year=year, sign=1)

    if other_total is None or credit_total is None:
        return None
    if abs(sum(abs(t.amount) for t in other) - other_total) > 0.02:
        return None
    if abs(sum(t.amount for t in credits) - credit_total) > 0.02:
        return None
    if checks and stmt.stated_total_debits is not None:
        check_total = sum(abs(t.amount) for t in checks)
        expected_checks = round(stmt.stated_total_debits - other_total, 2)
        if abs(check_total - expected_checks) > 0.02:
            return None

    txns = checks + other + credits
    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt
