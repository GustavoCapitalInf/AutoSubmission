"""BMO Bank N.A. (US) — the `Monthly Activity Details` layout.

The third BMO document class this platform reads, and structurally unrelated to
the other two: `analysis/bmo.py` reads an `ACCOUNT SUMMARY TOTALS` block, and
`analysis/bmo_ca_business.py` a `Summary of account` grid whose money columns
are `Amounts debited/credited`. This one prints a US statement — `BMO BANK N.A.`
in its legal block, `bmo.com/contact` in every page header — whose summary is a
single labelled row:

    BEGINNING BALANCE AS OF <date>  NUMBER OF DEPOSITS  DEPOSIT AMOUNT
    NUMBER OF WITHDRAWALS  WITHDRAWAL AMOUNT  SERVICE CHARGES
    ENDING BALANCE AS OF <date>

That row is this parser's instrument: it prints both period totals, both item
counts, both balances and the service charge, and it closes as
`beginning + deposits - withdrawals - service charges = ending` on every
document it has been measured against.

**Direction is printed, not inferred.** This layout brackets a withdrawal —
`($300.00)` — and prints a deposit bare — `$19.77`. The bracket is the
statement's own notation for the Withdrawal column, so no wording vocabulary and
no balance arithmetic is needed to orient a row. The Balance column is printed
only on the last row of each posting day, which `analysis/reconcile.py` already
reads as an intermittent running balance; the days it does print are what
independently checks the direction rule.
"""
from __future__ import annotations

import re
from datetime import date

from .dates import resolve_year
from .money import parse_grouped_float
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace, group_rows

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

#: `$1,234.56` or, for the Withdrawal column and a negative balance,
#: `($1,234.56)`. The dollar sign is printed on every money cell of this
#: layout, which is what keeps a bare reference number out of the columns.
_MONEY = re.compile(r"\(?\$[\d,]+\.\d{2}\)?")
_PERIOD = re.compile(
    r"Date\s+([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s+through\s+"
    r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)
_SUMMARY = re.compile(
    r"BEGINNING BALANCE AS OF .*?ENDING BALANCE AS OF [^\n]*\n\s*"
    rf"({_MONEY.pattern})\s+(\d+)\s+({_MONEY.pattern})\s+(\d+)\s+"
    rf"({_MONEY.pattern})\s+({_MONEY.pattern})\s+({_MONEY.pattern})",
    re.IGNORECASE | re.DOTALL,
)
_ACCOUNT = re.compile(r"Account Summary\s*-\s*(?P<product>[^#\n]+?)\s*#(?P<number>\d+)")
_AVERAGE_LEDGER = re.compile(
    r"AVERAGE LEDGER BALANCE\s+AVERAGE FLOAT\s+AVERAGE COLLECTED BALANCE\s*\n\s*"
    rf"({_MONEY.pattern})",
    re.IGNORECASE,
)
_ROW_DATE = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b",
    re.IGNORECASE,
)
#: The grid's own opening and closing rows. `BEGINNING BALANCE AS OF <date>` is
#: the SUMMARY's column label, not the ledger's first row, and the two are told
#: apart by the label rather than by where they happen to fall in the document.
_LEDGER_OPENS = re.compile(r"^BEGINNING BALANCE(?!\s+AS OF)", re.IGNORECASE)
_LEDGER_CLOSES = re.compile(r"^ENDING BALANCE(?!\s+AS OF)", re.IGNORECASE)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


#: Issuer furniture only (R-4b): the issuer's legal name as printed in its own
#: legal block, the contact URL printed in every page header, and the two
#: section headings of the statement this parser reads. No customer data, no
#: amount, no date.
DETECTION_MARKERS = (
    required("issuer_legal_name", lambda t: "BMO BANK N.A" in t),
    required("issuer_contact_domain", lambda t: "BMO.COM/CONTACT" in t),
    required("activity_heading", lambda t: "MONTHLY ACTIVITY DETAILS" in t),
    required("summary_heading", lambda t: "BEGINNING BALANCE AS OF" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _amount(token: str) -> float:
    """One printed money cell, with the layout's bracket notation applied.

    `($300.00)` is what this statement prints in the Withdrawal column and for a
    negative Balance; the brackets are the sign.
    """
    negative = token.startswith("(")
    value = parse_grouped_float(token.strip("()").replace("$", ""))
    return round(-value if negative else value, 2)


def _period(text: str) -> tuple[date, date] | None:
    match = _PERIOD.search(text)
    if not match:
        return None
    try:
        start = date(
            int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2))
        )
        end = date(
            int(match.group(6)), _MONTHS[match.group(4).lower()], int(match.group(5))
        )
    except (KeyError, ValueError):
        return None
    return (start, end) if start <= end else None


def _ledger_lines(lines: list[str]) -> list[str]:
    """The lines standing inside the activity grid, from its opening balance row
    to its closing one.

    Both bounds are rows the grid itself prints, so the section needs no
    heading search and no list of the page furniture BMO repeats between them.
    """
    start = None
    for index, line in enumerate(lines):
        if _LEDGER_OPENS.match(line):
            start = index
            break
    if start is None:
        return []
    body = []
    for line in lines[start:]:
        if _LEDGER_CLOSES.match(line):
            break
        body.append(line)
    return body


def parse_bmo_us_activity_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None

    text = markdown
    period = _period(text)
    if period is None:
        return None
    period_start, period_end = period

    summary = _SUMMARY.search(text)
    if summary is None:
        return None
    beginning = _amount(summary.group(1))
    deposit_count = int(summary.group(2))
    deposits = _amount(summary.group(3))
    withdrawal_count = int(summary.group(4))
    withdrawals = _amount(summary.group(5))
    service_charges = _amount(summary.group(6))
    ending = _amount(summary.group(7))

    stmt = Statement(bank="BMO", currency="USD")
    stmt.period_start = period_start.isoformat()
    stmt.period_end = period_end.isoformat()
    stmt.beginning_balance = beginning
    stmt.ending_balance = ending
    stmt.stated_total_credits = deposits
    stmt.stated_total_debits = withdrawals
    stmt.stated_credit_count = deposit_count
    stmt.stated_debit_count = withdrawal_count
    stmt.stated_service_charge = service_charges

    account = _ACCOUNT.search(text)
    if account:
        stmt.account_number = account.group("number")
        stmt.account_name = compact_whitespace(account.group("product"))

    average = _AVERAGE_LEDGER.search(text)
    if average:
        stmt.stated_average_balance = _amount(average.group(1))

    lines = [compact_whitespace(raw) for raw in text.splitlines()]
    body = _ledger_lines([line for line in lines if line])
    if not body:
        return None

    transactions: list[Transaction] = []
    for group in group_rows(body, starts_row=lambda line: bool(_ROW_DATE.match(line))):
        head = group[0]
        match = _ROW_DATE.match(head)
        if not match:
            continue
        month = _MONTH_ABBR.get(match.group(1)[:3].lower())
        if month is None:
            continue
        # The grid prints a row's money cells on the row's own line; the lines
        # under it carry the record number, the card number and the merchant
        # location, which stand in the Description column and print no money.
        cells = _MONEY.findall(head)
        if not cells:
            continue
        amount = _amount(cells[-2] if len(cells) >= 2 else cells[-1])
        balance = _amount(cells[-1]) if len(cells) >= 2 else None
        description = compact_whitespace(head[match.end(): head.find(cells[-2] if len(cells) >= 2 else cells[-1])])
        if not description:
            continue
        day = int(match.group(2))
        year = resolve_year(month, day, period_start, period_end)
        if year is None:
            continue
        try:
            posted = date(year, month, day)
        except ValueError:
            continue
        if not (period_start <= posted <= period_end):
            continue
        transactions.append(Transaction(
            date=posted.isoformat(),
            description=description,
            amount=amount,
            direction="credit" if amount > 0 else "debit",
            running_balance=balance,
        ))

    stmt.transactions = transactions
    return stmt


def summary_row_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The ledger's own `ENDING BALANCE` row re-prints the summary's closing
    balance, and the first page re-prints it again in `Statement Summary`.

    Registered as this parser's `integrity_check` so that a document whose three
    printings of one figure disagree is reported as contradicting itself rather
    than silently reduced to whichever the parser read first.
    """
    if stmt.ending_balance is None:
        return []
    printed: list[float] = []
    for raw in markdown.splitlines():
        line = compact_whitespace(raw)
        if not _LEDGER_CLOSES.match(line):
            continue
        cells = _MONEY.findall(line)
        if cells:
            printed.append(_amount(cells[-1]))
    if any(abs(value - stmt.ending_balance) > 0.01 for value in printed):
        return [
            "the account summary and the activity ledger state different "
            "closing balances"
        ]
    return []
