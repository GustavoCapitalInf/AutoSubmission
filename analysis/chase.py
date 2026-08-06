from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day, period_from_long_dates
from .money import parse_digit_scrubbed
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import clean_cell, table_rows, tables_after

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
_EXPORT_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


#: A Chase amount cell as printed: optional parenthesis/minus/dollar wrapper
#: around a grouped decimal. Scrubbing is only allowed on tokens matching this.
_AMOUNT_RE = re.compile(r"\(?-?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})?-?\)?")


def _money(value: str) -> float | None:
    return parse_digit_scrubbed(
        value, parens=True, leading_minus=True, trailing_minus=True, guard=_AMOUNT_RE
    )


def _money_required(value: str) -> float:
    amount = _money(value)
    if amount is None:
        raise ValueError(value)
    return amount


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in: page images carry no words."""
    return _IMG_RE.sub("", markdown)


EXPORT_DETECTION_MARKERS = (
    required("export_header", lambda t: "Printed from Chase for Business" in t),
    required("transactions_section", lambda t: "Transactions" in t),
)

DETECTION_MARKERS = (
    required("bank_name", lambda t: "JPMorgan Chase Bank" in t or "\nCHASE\n" in t),
)

detect_export = make_detector(EXPORT_DETECTION_MARKERS, detection_text)
detect = make_detector(DETECTION_MARKERS, detection_text)


def _parse_chase_business_export(markdown: str) -> Statement | None:
    if not detect_export(markdown).claims:
        return None
    if "CHECKING SUMMARY" in markdown:
        return None

    account = re.search(r"BUS COMPLETE CHK\s+\(\.\.\.(\d+)\)", markdown, re.IGNORECASE)
    name = re.search(
        r"BUS COMPLETE CHK\s+\(\.\.\.\d+\)\s*\nBUS COMPLETE CHK\s+\(\.\.\.\d+\)\s*\n([A-Z0-9 &.'-]+)",
        markdown,
    )
    display_rows: list[Transaction] = []
    current_date: date | None = None
    month_names = "|".join(_EXPORT_MONTHS)
    row_date_re = re.compile(
        rf"^({month_names})[a-z]*\s+(\d{{1,2}}),?\s*(\d{{4}})\s+(.+)$",
        re.IGNORECASE,
    )

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("---") or line.lower().startswith("pending "):
            continue
        date_match = row_date_re.match(line)
        if date_match:
            raw_month, raw_day, raw_year, line = date_match.groups()
            current_date = date(int(raw_year), _EXPORT_MONTHS[raw_month[:3].title()], int(raw_day))
        if current_date is None:
            continue
        money_matches = list(re.finditer(r"-?\$\d[\d,]*\.\d{2}", line))
        if len(money_matches) < 2:
            continue
        amount_match = money_matches[-2]
        balance_match = money_matches[-1]
        description = line[:amount_match.start()].strip()
        if not description:
            continue
        amount = _money_required(amount_match.group(0))
        balance = _money_required(balance_match.group(0))
        display_rows.append(Transaction(
            date=current_date.isoformat(),
            description=clean_cell(description),
            amount=round(amount, 2),
            direction="credit" if amount > 0 else "debit",
            running_balance=round(balance, 2),
        ))

    if len(display_rows) < 3:
        return None
    transactions = list(reversed(display_rows))
    beginning = round((transactions[0].running_balance or 0.0) - transactions[0].amount, 2)
    ending = transactions[-1].running_balance
    if ending is None:
        return None
    stmt = Statement(
        bank="Chase Transaction Export",
        account_name=name.group(1).strip() if name else None,
        account_number=f"...{account.group(1)}" if account else None,
        period_start=transactions[0].date,
        period_end=transactions[-1].date,
        beginning_balance=beginning,
        ending_balance=ending,
        currency="USD",
        transactions=transactions,
    )
    return stmt


def _tables_after(markdown: str, heading: str) -> list[str]:
    #: Chase spells a section that breaks across pages "<heading> (continued)".
    return tables_after(markdown, heading, continued=r"(?: \(continued\))?")


def _native_blocks(markdown: str, heading: str) -> list[str]:
    blocks = []
    for match in re.finditer(r"\*start\*[^\n]*\n(.*?)\*end\*", markdown, re.IGNORECASE | re.DOTALL):
        block = match.group(1)
        if re.search(rf"(?im)^\s*{re.escape(heading)}(?:\s|\(|$)", block):
            blocks.append(block)
    return blocks


_ROW_STARTERS = (
    "Orig CO Name",
    "Real Time Payment",
    "Real Time Transfer",
    "Remote Online Deposit",
    "Payment Received",
    "Payment Sent",
    "Payment To",
    "Zelle Payment",
    "Deposit",
    "Fee Reversal",
    "Recurring Card Purchase",
    "Card Purchase",
    "ATM Withdrawal",
    "Withdrawal",
    "Monthly Service Fee",
    "Service Charges",
    "Book Transfer",
    "Online Transfer",
    "Online Transfer From",
    "Online Transfer To",
    "Online ACH Payment",
    "Online Payment",
    "Overdraft Fee",
)


def _native_lines(block: str) -> list[str]:
    text = re.sub(r"\s+", " ", block.replace("\n", " ")).strip()
    text = re.sub(r"DATE DESCRIPTION AMOUNT\s+", "DATE DESCRIPTION AMOUNT\n", text, flags=re.IGNORECASE)
    starters = "|".join(re.escape(item) for item in _ROW_STARTERS)
    text = re.sub(
        rf"\s+(?=(\d{{2}}/\d{{2}}\s+(?:\d{{2}}/\d{{2}}\s+)?(?:{starters})\b))",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+(?=(?:Total|ATM & Debit Card Summary|DAILY ENDING BALANCE)\b)", "\n", text, flags=re.IGNORECASE)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_native_section(markdown: str, heading: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for block in _native_blocks(markdown, heading):
        for line in _native_lines(block):
            if line.upper().startswith(("DATE DESCRIPTION AMOUNT", "TOTAL ", heading.upper())):
                continue
            m = re.match(r"(?P<date>\d{2}/\d{2})\s+(?P<body>.+)", line)
            if not m:
                continue
            if m.group("body").lower().startswith("date "):
                continue
            amounts = list(re.finditer(r"\$?\s*[0-9][0-9,]*\.[0-9]{2}", m.group("body")))
            if not amounts:
                continue
            amount_match = amounts[-1]
            amount = _money(amount_match.group(0))
            if amount is None:
                continue
            desc = (m.group("body")[:amount_match.start()] + m.group("body")[amount_match.end():]).strip()
            desc = re.sub(r"\s+", " ", desc)
            if not desc or desc.lower().startswith("total"):
                continue
            signed = round(abs(amount) * sign, 2)
            txns.append(Transaction(
                date=iso_from_month_day(m.group("date"), year),
                description=desc,
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=None,
            ))
    return txns


def _parse_native_checks(markdown: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for block in _native_blocks(markdown, "CHECKS PAID"):
        for check_no, mmdd, amount_text in re.findall(
            r"\b(\d{3,})\s+\*?\s*\^?\s+(\d{2}/\d{2})\s+\$?\s*([0-9][0-9,]*\.[0-9]{2})",
            block,
        ):
            amount = _money(amount_text)
            if amount is None:
                continue
            txns.append(Transaction(
                date=iso_from_month_day(mmdd, year),
                description=f"Check Paid {check_no}",
                amount=round(-abs(amount), 2),
                direction="debit",
                running_balance=None,
            ))
    return txns


def _parse_native_summary(text: str, stmt: Statement) -> bool:
    match = re.search(r"CHECKING SUMMARY(.*?)\*end\*summary", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return False
    summary = re.sub(r"\s+", " ", match.group(1)).strip()

    beginning = re.search(r"Beginning Balance\s+(\$?[0-9][0-9,]*\.[0-9]{2})", summary, re.IGNORECASE)
    ending = re.search(r"Ending Balance(?:\s+\d+)?\s+(\$?[0-9][0-9,]*\.[0-9]{2})", summary, re.IGNORECASE)
    deposits = re.search(r"Deposits and Additions\s+(\d+)\s+(-?\$?[0-9][0-9,]*\.[0-9]{2})", summary, re.IGNORECASE)
    if beginning:
        stmt.beginning_balance = _money(beginning.group(1))
    if ending:
        stmt.ending_balance = _money(ending.group(1))
    if deposits:
        stmt.stated_credit_count = int(deposits.group(1))
        stmt.stated_total_credits = abs(_money(deposits.group(2)) or 0.0)

    debit_total = 0.0
    debit_count = 0
    for label in ("Checks Paid", "ATM & Debit Card Withdrawals", "Electronic Withdrawals", "Other Withdrawals", "Fees"):
        m = re.search(rf"{re.escape(label)}\s+(\d+)\s+(-?\$?[0-9][0-9,]*\.[0-9]{{2}})", summary, re.IGNORECASE)
        if not m:
            continue
        debit_count += int(m.group(1))
        amount = abs(_money(m.group(2)) or 0.0)
        debit_total += amount
        if label == "Fees":
            stmt.stated_service_charge = amount
    stmt.stated_debit_count = debit_count or None
    stmt.stated_total_debits = round(debit_total, 2) if debit_total else None
    return stmt.beginning_balance is not None and stmt.ending_balance is not None


def _parse_txn_table(table: str, *, year: int, sign: int) -> tuple[list[Transaction], list[tuple[str, str]]]:
    txns: list[Transaction] = []
    missing_amounts: list[tuple[str, str]] = []
    for cells in table_rows(table):
        if len(cells) < 3:
            continue
        if cells[0].upper() == "DATE" or cells[0].lower().startswith("total"):
            continue
        if not re.fullmatch(r"\d{2}/\d{2}", cells[0]):
            continue
        amount_idx = next((idx for idx in range(len(cells) - 1, 1, -1) if _money(cells[idx]) is not None), None)
        if amount_idx is None:
            desc = " ".join(cells[1:]).strip()
            if desc:
                missing_amounts.append((iso_from_month_day(cells[0], year), desc))
            continue
        amount = _money(cells[amount_idx])
        if amount is None:
            continue
        desc = " ".join(cells[1:amount_idx]).strip()
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=iso_from_month_day(cells[0], year),
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns, missing_amounts


def _table_total(table: str, label: str) -> float | None:
    for cells in table_rows(table):
        if len(cells) < 2:
            continue
        if label.lower() not in cells[0].lower():
            continue
        for cell in reversed(cells):
            amount = _money(cell)
            if amount is not None:
                return abs(amount)
    return None


def _parse_section(markdown: str, heading: str, *, total_label: str, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    missing_amounts: list[tuple[str, str]] = []
    stated_total = 0.0
    for table in _tables_after(markdown, heading):
        table_txns, table_missing = _parse_txn_table(table, year=year, sign=sign)
        txns.extend(table_txns)
        missing_amounts.extend(table_missing)
        total = _table_total(table, total_label)
        if total is not None:
            stated_total += total

    parsed_total = round(sum(abs(t.amount) for t in txns), 2)
    missing_total = round(stated_total - parsed_total, 2) if stated_total else 0.0
    if len(missing_amounts) == 1 and missing_total > 0:
        txn_date, desc = missing_amounts[0]
        signed = round(missing_total * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def parse_chase_statement(markdown: str) -> Statement | None:
    text = _IMG_RE.sub("", markdown)
    export = _parse_chase_business_export(text)
    if export is not None:
        return export
    if not detect(markdown).claims:
        return None
    if "CHECKING SUMMARY" not in text:
        return None

    period = period_from_long_dates(text)
    if period is None:
        return None
    period_start, period_end = period
    year = int(period_end[:4])

    stmt = Statement(bank="Chase", period_start=period_start, period_end=period_end)
    acct = re.search(r"Account Number:\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    name = re.search(r"CHECKING SUMMARY\s*\n([^\n<]+)", text, re.IGNORECASE)
    if name:
        stmt.account_name = name.group(1).strip()

    summary_match = re.search(r"CHECKING SUMMARY.*?(<table>.*?</table>)", text, re.IGNORECASE | re.DOTALL)
    if summary_match:
        debit_total = 0.0
        debit_count = 0
        for cells in table_rows(summary_match.group(1)):
            if len(cells) < 3:
                continue
            label = cells[0].lower()
            instances = re.sub(r"[^0-9]", "", cells[1])
            amount = _money(cells[2])
            if "beginning balance" in label:
                stmt.beginning_balance = amount
            elif "deposits and additions" in label:
                stmt.stated_credit_count = int(instances) if instances else None
                stmt.stated_total_credits = amount
            elif any(name in label for name in ("checks paid", "atm", "electronic withdrawals", "other withdrawals", "fees")):
                if amount is not None:
                    debit_total += abs(amount)
                if instances:
                    debit_count += int(instances)
                if "fees" in label and amount is not None:
                    stmt.stated_service_charge = abs(amount)
            elif "ending balance" in label:
                stmt.ending_balance = amount
        stmt.stated_total_debits = round(debit_total, 2) if debit_total else None
        stmt.stated_debit_count = debit_count or None
    elif not _parse_native_summary(text, stmt):
        return None

    txns: list[Transaction] = []
    txns.extend(_parse_section(
        text,
        "DEPOSITS AND ADDITIONS",
        total_label="Total Deposits and Additions",
        year=year,
        sign=1,
    ))
    txns.extend(_parse_section(
        text,
        "ATM & DEBIT CARD WITHDRAWALS",
        total_label="Total ATM & Debit Card Withdrawals",
        year=year,
        sign=-1,
    ))
    txns.extend(_parse_section(
        text,
        "ELECTRONIC WITHDRAWALS",
        total_label="Total Electronic Withdrawals",
        year=year,
        sign=-1,
    ))
    txns.extend(_parse_section(
        text,
        "FEES",
        total_label="Total Fees",
        year=year,
        sign=-1,
    ))
    if not txns:
        txns.extend(_parse_native_section(text, "DEPOSITS AND ADDITIONS", year=year, sign=1))
        txns.extend(_parse_native_checks(text, year=year))
        txns.extend(_parse_native_section(text, "ATM & DEBIT CARD WITHDRAWALS", year=year, sign=-1))
        txns.extend(_parse_native_section(text, "ELECTRONIC WITHDRAWALS", year=year, sign=-1))
        txns.extend(_parse_native_section(text, "OTHER WITHDRAWALS", year=year, sign=-1))
        txns.extend(_parse_native_section(text, "FEES", year=year, sign=-1))

    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt


#: Public entry point for the Chase online transaction export, which R-3
#: registers in its own right. `parse_chase_statement` still tries it first;
#: that inner call goes away when the pipeline switches to registry dispatch.
parse_chase_export_statement = _parse_chase_business_export
