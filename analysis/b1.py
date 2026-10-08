from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_from_month_day
from .money import LEADING_MINUS_PADDED, parse_amount, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, LEADING_MINUS_PADDED)


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"Last statement:\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+This statement:\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+Total days in statement period:\s+(\d+)",
        markdown,
    )
    if not m:
        return None
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    }
    lm, ld, ly, tm, td, ty, days = m.groups()
    start = date(int(ly), months[lm], int(ld)) + timedelta(days=1)
    end = date(int(ty), months[tm], int(td))
    return start.isoformat(), end.isoformat(), int(days)


def _iso(mmdd: str, year: int) -> str:
    return iso_from_month_day(mmdd, year, separator="-")


def _ending_totals(markdown: str) -> tuple[float, float, float] | None:
    m = re.search(
        r"Ending totals(?:\s+Ending totals){3}\s+"
        r"(\d[\d,]*\.\d{2}|\.\d{2})(?:\s+(?:\d[\d,]*\.\d{2}|\.\d{2})){3}\s+"
        r"(-?[\d,]+\.\d{2})(?:\s+-?[\d,]+\.\d{2}){3}\s+"
        r"\$([\d,]+\.\d{2})(?:\s+\$[\d,]+\.\d{2}){3}",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    credits = abs(read_money(m.group(1), _money) or 0.0)
    debits = abs(read_money(m.group(2), _money) or 0.0)
    ending = read_money(m.group(3), _money) or 0.0
    return credits, debits, ending


#: Audit round 3, R3-B09 (R3-91): the incoming-wire labels this issuer prints on
#: a wire credit's row (`Incoming Wire`), as a short list of wire wording, never
#: a sender's name.
_INCOMING_WIRE_LABEL = re.compile(
    r"^[^A-Za-z]*(?:INCOMING(?: (?:USD|FX|INTL|INTERNATIONAL|DOMESTIC|FOREIGN))? WIRE|DOMESTIC WIRE|FEDWIRE|WIRE)"
    r"(?![A-Za-z])",
    re.IGNORECASE,
)
#: A line that opens a row (a date, then the description), or the section's
#: furniture: the page break's marker, the reprinted column header and heading.
_ROW_LEAD = re.compile(r"^\d{2}-\d{2}\s")
_FURNITURE = re.compile(r"^(?:-{3} Page \d+ -{3}|Date Date\b|DAILY ACTIVITY\b)", re.IGNORECASE)


def _lines_below(text: str, end: int) -> list[str]:
    """Audit round 3, R3-B09 (R3-91): the lines printed under a row whose
    figures end at `end`, up to the next row's line, a blank line (a page break
    follows one) or the section's furniture: the row's continuation, which the
    one-line row pattern does not read."""
    lines: list[str] = []
    for line in text[end:].split("\n")[1:]:
        if not line.strip() or _ROW_LEAD.match(line) or _FURNITURE.match(line.strip()):
            break
        lines.append(line.strip())
    return lines


def _transactions(markdown: str, *, year: int, beginning_balance: float) -> list[Transaction]:
    activity = re.search(r"DAILY ACTIVITY.*?(?=Ending totals)", markdown, re.IGNORECASE | re.DOTALL)
    if not activity:
        return []
    text = re.sub(r"\s+(?=\d{2}-\d{2}\s+'?\s*[A-Z])", "\n", activity.group(0))
    row_re = re.compile(r"(?m)^(\d{2}-\d{2})\s+'?\s*(.+?)\s+(-?[\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$")
    txns: list[Transaction] = []
    prev_balance = beginning_balance
    for m in row_re.finditer(text):
        mmdd, desc, raw_amount, raw_balance = m.groups()
        if "Beginning balance" in desc:
            continue
        amount = _money(raw_amount)
        balance = _money(raw_balance)
        if amount is None or balance is None:
            continue
        signed = round(balance - prev_balance, 2)
        if abs(signed - amount) > 0.01:
            signed = amount
        description = re.sub(r"\s+", " ", desc).strip()
        # Audit round 3, R3-B09 (R3-91): an incoming wire's sender prints on the
        # lines under its row. They are kept apart from its description, never
        # read as its payer (Transaction.unread_payer_text), and the wire is
        # marked as read only by its label. Every other row is unchanged.
        below = " ".join(_lines_below(text, m.end(4))) if signed > 0 and _INCOMING_WIRE_LABEL.match(description) else ""
        txns.append(Transaction(
            date=_iso(mmdd, year),
            description=description,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=balance,
            payer_text_unread=bool(below),
            unread_payer_text=re.sub(r"\s+", " ", below).strip(),
        ))
        prev_balance = balance
    return txns


DETECTION_MARKERS = (
    required("bank_name", lambda t: "B1Bank" in t),
    required("section", lambda t: "DAILY ACTIVITY" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_b1_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    totals = _ending_totals(markdown)
    beginning = re.search(r"\d{2}-\d{2}\s+Beginning balance\s+\$([\d,]+\.\d{2})", markdown)
    if period is None or totals is None or not beginning:
        return None
    period_start, period_end, days = period
    credits, debits, ending = totals
    stmt = Statement(
        bank="B1Bank",
        account_name="Essential Business Checking",
        period_start=period_start,
        period_end=period_end,
        days_in_period=days,
        beginning_balance=_money(beginning.group(1)),
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
    )
    acct = re.search(r"Account number\s+([X*0-9]+)", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    avg = re.search(r"Average balance\s+\$([\d,]+\.\d{2})", markdown, re.IGNORECASE)
    if avg:
        stmt.bank_reported_average_balance = _money(avg.group(1))
        stmt.bank_reported_average_label = "Average balance"

    txns = _transactions(markdown, year=int(period_end[:4]), beginning_balance=stmt.beginning_balance or 0.0)
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - debits) > 0.02:
        return None
    stmt.transactions = txns
    return stmt
