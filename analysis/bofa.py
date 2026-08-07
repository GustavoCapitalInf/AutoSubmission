from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_or_none
from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import table_rows, tables_after

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)


def _money(value: str) -> float | None:
    text = value.strip()
    if not re.fullmatch(r"-?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})|-?\$?0(?:\.00)?", text):
        return None
    return parse_money(text)


def _parse_date(value: str) -> str | None:
    """The row's posting date, or None when that token is not a date.

    Every caller already skips a row this returns None for, which is the right
    handling for a token of the right shape that no calendar can hold: BofA
    native text puts a column that is not the date column at the head of a row
    often enough that discovery found 16 documents where it raised here
    (`iso_or_none`).
    """
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2})", value.strip())
    if not m:
        return None
    month, day, year = m.groups()
    return iso_or_none(2000 + int(year), int(month), int(day))


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"for\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+to\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
    )
    if not m:
        return None
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    }
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), months[sm], int(sd)).isoformat(),
        date(int(ey), months[em], int(ed)).isoformat(),
    )


def _tables_after(markdown: str, heading: str) -> list[str]:
    #: BofA spells a section that breaks across pages "<heading> - continued".
    return tables_after(markdown, heading, continued=r"(?: - continued)?")


def _native_lines(markdown: str, heading: str) -> list[str]:
    pattern = rf"{re.escape(heading)}(?: - continued)?\s+Date\s+Description\s+Amount\s+(.*?)(?=(?:Deposits and other credits|Withdrawals and other debits|Checks\s*$|Service fees|Daily ledger balances|Total {re.escape(heading)}|continued on the next page|Page \d+ of|\Z))"
    chunks: list[str] = []
    chunks.extend(m.group(1) for m in re.finditer(pattern, markdown, re.IGNORECASE | re.DOTALL))
    lines: list[str] = []
    for chunk in chunks:
        text = re.sub(r"\s+", " ", chunk).strip()
        text = re.sub(r"\s+(?=\d{2}/\d{2}/\d{2}\s)", "\n", text)
        for line in text.splitlines():
            line = line.strip()
            if line and not line.lower().startswith(("continued on", "page ")):
                lines.append(line)
    return lines


def _parse_native_section(markdown: str, heading: str, *, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for line in _native_lines(markdown, heading):
        m = re.match(r"(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<body>.+)", line)
        if not m:
            continue
        body = re.split(r"\s+(?:Subtotal for|Total withdrawals and other debits|Total deposits and other credits)\b", m.group("body"), maxsplit=1, flags=re.IGNORECASE)[0]
        amounts = list(re.finditer(r"-?\$?\s*[0-9][0-9,]*\.[0-9]{2}", body))
        if not amounts:
            continue
        amount_match = amounts[-1]
        amount = _money(amount_match.group(0))
        txn_date = _parse_date(m.group("date"))
        if amount is None or txn_date is None:
            continue
        desc = (body[:amount_match.start()] + body[amount_match.end():]).strip()
        desc = re.sub(r"\s+", " ", desc)
        if not desc or desc.lower().startswith("total"):
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def _parse_native_checks(markdown: str) -> list[Transaction]:
    m = re.search(
        r"\bChecks\s+Date Check # Amount Date Check # Amount\s+(.*?)\s+Total checks\s+-?\$?[0-9][0-9,]*\.[0-9]{2}",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    txns: list[Transaction] = []
    text = re.sub(r"\s+", " ", m.group(1))
    for txn_date, check_no, amount_text in re.findall(
        r"(\d{2}/\d{2}/\d{2})\s+(\d+\*?)\s+(-?[0-9][0-9,]*\.[0-9]{2})",
        text,
    ):
        amount = _money(amount_text)
        iso_date = _parse_date(txn_date)
        if amount is None or iso_date is None:
            continue
        txns.append(Transaction(
            date=iso_date,
            description=f"Check {check_no}",
            amount=round(-abs(amount), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def _parse_native_service_fees(markdown: str) -> list[Transaction]:
    m = re.search(
        r"\bService fees\b.*?Date Transaction description Amount\s+(.*?)\s+Total service fees\s+-?\$?[0-9][0-9,]*\.[0-9]{2}",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    text = re.sub(r"\s+", " ", m.group(1)).strip()
    text = re.sub(r"\s+(?=\d{2}/\d{2}/\d{2}\s)", "\n", text)
    txns: list[Transaction] = []
    for line in text.splitlines():
        row = re.match(r"(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<body>.+)", line.strip())
        if not row:
            continue
        amounts = list(re.finditer(r"-?\$?\s*[0-9][0-9,]*\.[0-9]{2}", row.group("body")))
        if not amounts:
            continue
        amount_match = amounts[-1]
        amount = _money(amount_match.group(0))
        txn_date = _parse_date(row.group("date"))
        if amount is None or txn_date is None:
            continue
        desc = (row.group("body")[:amount_match.start()] + row.group("body")[amount_match.end():]).strip()
        desc = re.sub(r"\s+", " ", desc)
        txns.append(Transaction(
            date=txn_date,
            description=desc,
            amount=round(-abs(amount), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def _native_money_after(text: str, label: str, *, absolute: bool = True) -> float | None:
    m = re.search(label + r"\s+(-?\$?\s*[0-9][0-9,]*\.[0-9]{2})", text, re.IGNORECASE)
    if not m:
        return None
    amount = _money(m.group(1))
    if amount is None:
        return None
    return abs(amount) if absolute else amount


def _parse_native_summary(text: str, stmt: Statement) -> bool:
    stmt.beginning_balance = _native_money_after(text, r"Beginning balance on [^\n$]+", absolute=False)
    stmt.ending_balance = _native_money_after(text, r"Ending balance on [^\n$]+", absolute=False)
    stmt.stated_total_credits = _native_money_after(text, r"Deposits and other credits")
    withdrawals = _native_money_after(text, r"Withdrawals and other debits")
    checks = _native_money_after(text, r"Checks")
    service = _native_money_after(text, r"Service fees")
    if withdrawals is not None:
        stmt.stated_total_debits = round(withdrawals + (checks or 0.0) + (service or 0.0), 2)
    if service is not None:
        stmt.stated_service_charge = service
    avg = _native_money_after(text, r"Average ledger balance:")
    if avg is not None:
        stmt.stated_average_balance = avg
    days = re.search(r"# of days in cycle:\s*(\d+)", text, re.IGNORECASE)
    if days:
        stmt.days_in_period = int(days.group(1))
    credit_count = re.search(r"# of deposits/credits:\s*(\d+)", text, re.IGNORECASE)
    if credit_count:
        stmt.stated_credit_count = int(credit_count.group(1))
    debit_count = re.search(r"# of withdrawals/debits:\s*(\d+)", text, re.IGNORECASE)
    if debit_count:
        stmt.stated_debit_count = int(debit_count.group(1))
    return stmt.beginning_balance is not None and stmt.ending_balance is not None


def _table_total(table: str, label: str) -> float | None:
    for cells in table_rows(table):
        if len(cells) < 2 or label.lower() not in cells[0].lower():
            continue
        for cell in reversed(cells):
            amount = _money(cell)
            if amount is not None:
                return abs(amount)
    return None


def _parse_section(markdown: str, heading: str, *, total_label: str, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    missing: list[tuple[str, str]] = []
    stated_total = 0.0

    for table in _tables_after(markdown, heading):
        for cells in table_rows(table):
            if len(cells) < 3 or cells[0].lower() == "date":
                continue
            txn_date = _parse_date(cells[0])
            if txn_date is None:
                continue
            amount_idx = next((idx for idx in range(len(cells) - 1, 1, -1) if _money(cells[idx]) is not None), None)
            if amount_idx is None:
                desc = " ".join(cells[1:]).strip()
                if desc:
                    missing.append((txn_date, desc))
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
        total = _table_total(table, total_label)
        if total is not None:
            stated_total += total

    parsed_total = round(sum(abs(t.amount) for t in txns), 2)
    missing_total = round(stated_total - parsed_total, 2) if stated_total else 0.0
    if len(missing) == 1 and missing_total > 0:
        txn_date, desc = missing[0]
        signed = round(missing_total * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return _IMG_RE.sub("", markdown).upper()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "BANK OF AMERICA" in t),
    required("summary_section", lambda t: "ACCOUNT SUMMARY" in t),
    # A TD statement paying a Bank of America card carries both of the above.
    # Require the issuer's own domain, the same class of evidence eight other
    # parsers already detect on (R3_DETECTION_FINDING.md).
    required("issuer_domain", lambda t: "BANKOFAMERICA.COM" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_bofa_statement(markdown: str) -> Statement | None:
    text = _IMG_RE.sub("", markdown)
    if not detect(markdown).claims:
        return None
    period = _period(text)
    if period is None:
        return None

    stmt = Statement(bank="Bank of America", period_start=period[0], period_end=period[1])
    acct = re.search(r"Account number:\s*([0-9 ]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = re.sub(r"\s+", "", acct.group(1))
    acct_name = re.search(r"Your\s+(.+?)\s+for\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+to", text, re.IGNORECASE | re.DOTALL)
    if acct_name:
        stmt.account_name = re.sub(r"\s+", " ", acct_name.group(1)).strip()

    summary_match = re.search(r"Account summary\s*(<table>.*?</table>)", text, re.IGNORECASE | re.DOTALL)
    if summary_match:
        for cells in table_rows(summary_match.group(1)):
            if len(cells) < 2:
                continue
            label = cells[0].lower()
            amount = _money(cells[1])
            extra = cells[2] if len(cells) > 2 else ""
            if "beginning balance" in label:
                stmt.beginning_balance = abs(amount) if amount is not None else None
            elif "deposits and other credits" in label:
                stmt.stated_total_credits = abs(amount) if amount is not None else None
            elif "withdrawals and other debits" in label:
                stmt.stated_total_debits = abs(amount) if amount is not None else None
            elif label == "checks" and amount is not None:
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + abs(amount), 2)
            elif "service fees" in label and amount is not None:
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + abs(amount), 2)
                stmt.stated_service_charge = abs(amount)
            elif "ending balance" in label:
                stmt.ending_balance = abs(amount) if amount is not None else None

            count = re.search(r"# of deposits/credits:\s*(\d+)", extra, re.IGNORECASE)
            if count:
                stmt.stated_credit_count = int(count.group(1))
            count = re.search(r"# of withdrawals/debits:\s*(\d+)", extra, re.IGNORECASE)
            if count:
                stmt.stated_debit_count = int(count.group(1))
            avg = re.search(r"Average ledger balance:\s*(\$?[\d,]+\.\d{2})", extra, re.IGNORECASE)
            if avg:
                stmt.stated_average_balance = abs(parse_money(avg.group(1)) or 0.0)
    elif not _parse_native_summary(text, stmt):
        return None

    txns = []
    txns.extend(_parse_section(text, "Deposits and other credits", total_label="Total deposits and other credits", sign=1))
    txns.extend(_parse_section(text, "Withdrawals and other debits", total_label="Total withdrawals and other debits", sign=-1))
    if not txns:
        txns.extend(_parse_native_section(text, "Deposits and other credits", sign=1))
        txns.extend(_parse_native_section(text, "Withdrawals and other debits", sign=-1))
    txns.extend(_parse_native_checks(text))
    txns.extend(_parse_native_service_fees(text))
    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt


def repair_bofa_summary(markdown: str, stmt: Statement) -> Statement:
    """Normalize Bank of America summary fields.

    BofA prints withdrawals/debits, checks, and service fees as separate account
    summary lines. For underwriting outflow totals and reconciliation, those must
    be treated as one debit total.
    """
    text = markdown
    if "BANK OF AMERICA" not in text.upper() or "ACCOUNT SUMMARY" not in text.upper():
        return stmt

    def money_after(label: str, *, absolute: bool = True) -> float | None:
        m = re.search(label + r"\s+(-?\$?[\d,]+\.\d{2})", text, re.IGNORECASE)
        if not m:
            return None
        amount = parse_money(m.group(1))
        if amount is None:
            return None
        return abs(amount) if absolute else amount

    def int_after(label: str) -> int | None:
        m = re.search(label + r"\s+(\d+)", text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    updates = {}
    beginning = money_after(r"Beginning balance on [A-Z][a-z]+ \d{1,2}, \d{4}", absolute=False)
    ending = money_after(r"Ending balance on [A-Z][a-z]+ \d{1,2}, \d{4}", absolute=False)
    credits = money_after(r"Deposits and other credits")
    withdrawals = money_after(r"Withdrawals and other debits")
    checks = money_after(r"Checks")
    service = money_after(r"Service fees")
    avg = money_after(r"Average ledger balance:")
    credit_count = int_after(r"# of deposits/credits:")
    debit_count = int_after(r"# of withdrawals/debits:")
    check_count = int_after(r"Total # of checks")

    if beginning is not None:
        updates["beginning_balance"] = beginning
    if ending is not None:
        updates["ending_balance"] = ending
    if credits is not None:
        updates["stated_total_credits"] = credits
    if withdrawals is not None:
        updates["stated_total_debits"] = round(withdrawals + (checks or 0.0) + (service or 0.0), 2)
    if credit_count is not None:
        updates["stated_credit_count"] = credit_count
    if debit_count is not None:
        updates["stated_debit_count"] = debit_count + (check_count or 0)
    if avg is not None:
        updates["stated_average_balance"] = avg
    if service is not None:
        updates["stated_service_charge"] = None

    repaired = stmt.model_copy(update=updates) if updates else stmt
    if any(t.running_balance is not None for t in repaired.transactions):
        repaired = repaired.model_copy(update={
            "transactions": [t.model_copy(update={"running_balance": None}) for t in repaired.transactions]
        })
    return repaired
