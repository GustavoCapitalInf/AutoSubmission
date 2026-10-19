"""The CitiBusiness `CHECKING ACTIVITY` statement.

Citibank prints this statement's ledger in five columns — Date, Description,
Debits, Credits, Balance — and the text layer destroys the two that matter:
an amount arrives as a bare figure with no way to tell which money column it
stood in. The direction is therefore read from the arithmetic the bank
printed, exactly as `cibc` reads its three-column grid: the movement between
two printed balances IS the signed amount, and a row whose printed magnitude
does not match that movement fails the document closed rather than being
signed by guesswork.

The layout reaches us in two flattenings. One puts a row's two money cells at
the END of the row (`04/01 ELECTRONIC CREDIT ... Apr 01 1,560.00 6,280.68`);
the other puts them immediately after the transaction type and prints the rest
of the description AFTER them (`06/01 FUNDS TRANSFER 1,400.00 5,608.97 WIRE
FROM ... Jun 01`). Both are the same printed grid, so this module reads the
invariant rather than either arrangement: after the Date column a row prints
exactly two money cells, the first the amount and the second the balance, and
the Description column is whatever is printed around them.

One trap is worth naming. The `SERVICE CHARGE SUMMARY` block at the top of
every one of these statements covers the PREVIOUS period — a May statement
carries April's analysis — so the `Average Daily Collected Balance` it prints
is not this period's average and is deliberately never published.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_unique_in_period
from .holder_name import CITY_STATE_ZIP, NO_READING, HolderReading, first_page, page_lines, read_address_line
from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: Audit round 2, R2-B05 (R04 part 2): Citibank's page-1 header line, from its statement period to the relationship
#: manager's label; a reading that ran the mailing block onto it prints the holder's name and street between them (the
#: name can open before the period's dates: 'Statement Period CONTOSO LLC Jun 1 - Jun 30, 2054 DBA NORTHWIND 100
#: SAMPLE RD Relationship Manager').
_HEADER_LINE = re.compile(r"CITIBANK, N\. ?A\. Account\b.*?\bStatement Period\b(?P<between>.*?)\bRelationship Manager\b")
#: The statement period inside that header ('Jun 1 - Jun 30, 2054').
_HEADER_PERIOD = re.compile(r"\b[A-Z][a-z]{2} \d{1,2} - [A-Z][a-z]{2} \d{1,2}, \d{4}\b")


def _holder_reading(markdown: str) -> HolderReading:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name from page 1's mailing address: the name and street the
    header line prints between its period and the relationship manager's label (the period's dates aside), or, where
    the header prints none, the next line when it closes on a state and ZIP, without the address; NO_READING otherwise.
    Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: with the account title printed after the name."""
    lines = page_lines(first_page(markdown))
    for index, line in enumerate(lines):
        match = _HEADER_LINE.search(line)
        if match is None:
            continue
        between = " ".join(_HEADER_PERIOD.sub(" ", match.group("between")).split())
        if between:
            return read_address_line(between)
        following = lines[index + 1] if index + 1 < len(lines) else ""
        return read_address_line(following) if CITY_STATE_ZIP.search(following) else NO_READING
    return NO_READING

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

#: One printed money cell. A cell stands in a column, so it begins a
#: whitespace-delimited token; a figure quoted INSIDE a reference does not.
#: The EDI remittance advice `RMR*IV*DMSAHD-2605*AI*508497.83*508497.83*0.`
#: names the payment amount twice inside the description, and without this
#: rule those quotations read as two more columns.
_MONEY = r"(?:(?<=\s)|(?<=^))\d[\d,]*\.\d{2}-?(?![\d.,])"
_MONEY_RE = re.compile(_MONEY)
#: The Date column: `04/01`. Never a longer date and never part of a longer
#: digit run, which is what keeps `BOX# 07730/0001157` from opening a row.
_ROW_DATE_RE = re.compile(r"(?<![\d/])(\d{2})/(\d{2})(?![\d/])")

#: The activity table's own printed column header. It re-opens the table on
#: every continuation page.
_GRID_RE = re.compile(r"Date\s+Description\s+Debits\s+Credits\s+Balance", re.IGNORECASE)
#: `Statement Period Apr 1 - Apr 30, 2026`, with or without the colon the
#: continuation pages add. Only the closing year is printed.
_PERIOD_RE = re.compile(
    r"Statement Period:?\s+([A-Za-z]{3})\w*\s+(\d{1,2})\s*-\s*([A-Za-z]{3})\w*\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)
_BEGINNING_RE = re.compile(r"Beginning Balance:\s*\$?([\d,]+\.\d{2}-?)", re.IGNORECASE)
_ENDING_RE = re.compile(r"Ending Balance:\s*\$?([\d,]+\.\d{2}-?)", re.IGNORECASE)
#: The row that closes the ledger. Debits first, credits second — checked
#: against the balance walk on every document of the family.
_TOTALS_RE = re.compile(
    r"Total Debits/Credits\s+([\d,]+\.\d{2}-?)\s+([\d,]+\.\d{2}-?)", re.IGNORECASE
)
#: The relationship block reprints the closing balance of the checking
#: product. `closing_balance_contradictions` is what compares the two.
_RELATIONSHIP_RE = re.compile(
    r"Relationship Summary:\s*Checking\s+\$?([\d,]+\.\d{2}-?)", re.IGNORECASE
)
_ACCOUNT_RE = re.compile(r"CITIBANK,\s*N\.\s*A\.\s*Account\s+(\d+)", re.IGNORECASE)
_SECTION_END_RE = re.compile(r"Total Debits/Credits|CUSTOMER SERVICE INFORMATION")
#: Page furniture inside the ledger's span, each printed on its own line.
_FURNITURE_RE = re.compile(r"^(--- Page \d+( \(empty\))? ---|000/R1/\S*)$")
_CONTINUED_RE = re.compile(r"CHECKING ACTIVITY Continued", re.IGNORECASE)

DETECTION_MARKERS = (
    required("bank_name", lambda t: bool(re.search(r"CITIBANK,\s*N\.\s*A\.", t))),
    required("product", lambda t: "CITIBUSINESS" in t),
    required("activity_section", lambda t: "CHECKING ACTIVITY" in t),
    required("activity_header", lambda t: bool(_GRID_RE.search(t))),
)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


detect = make_detector(DETECTION_MARKERS, detection_text)


def _amount(token: str) -> float | None:
    """A printed cell, including the trailing minus an overdrawn balance
    carries (`277.50-`)."""
    return parse_money(token)


def _period(markdown: str) -> tuple[date, date] | None:
    match = _PERIOD_RE.search(markdown)
    if not match:
        return None
    start_month, start_day, end_month, end_day, year = match.groups()
    try:
        first = _MONTHS[start_month.upper()]
        last = _MONTHS[end_month.upper()]
        end = date(int(year), last, int(end_day))
        # Only the closing year is printed; a period that starts in a later
        # month than it ends crossed a year boundary.
        start = date(int(year) - (1 if first > last else 0), first, int(start_day))
    except (KeyError, ValueError):
        return None
    return (start, end) if start <= end else None


def _ledger_text(markdown: str) -> str:
    """The activity table's text, furniture removed, pages joined.

    Everything before the first printed column header is the statement's
    header block and the service-charge analysis; everything from the totals
    row on is the statement's footer. Only what lies between is the grid.
    """
    stop = _SECTION_END_RE.search(markdown)
    body = markdown[: stop.start()] if stop else markdown
    lines = []
    for raw in body.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line and not _FURNITURE_RE.match(line):
            lines.append(line)
    text = _CONTINUED_RE.sub(" ", " ".join(lines))

    headers = list(_GRID_RE.finditer(text))
    if not headers:
        return ""
    spans = []
    for index, header in enumerate(headers):
        stop_at = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        spans.append(text[header.end():stop_at])
    return " ".join(spans)


def _rows(markdown: str, *, start: date, end: date, beginning: float) -> list[Transaction] | None:
    """The ledger's posting rows, or None if any row is unreadable."""
    text = _ledger_text(markdown)
    if not text:
        return None
    cuts = list(_ROW_DATE_RE.finditer(text))
    if not cuts:
        return None

    rows: list[Transaction] = []
    previous = beginning
    for index, cut in enumerate(cuts):
        stop = cuts[index + 1].start() if index + 1 < len(cuts) else len(text)
        body = text[cut.end():stop]
        cells = list(_MONEY_RE.finditer(body))
        if len(cells) != 2:
            return None
        magnitude = _amount(cells[0].group(0))
        balance = _amount(cells[1].group(0))
        posting = iso_unique_in_period(int(cut.group(1)), int(cut.group(2)), start=start, end=end)
        if magnitude is None or balance is None or posting is None:
            return None

        # The Description column is printed around the money cells, not always
        # before them: one flattening puts the whole description first, the
        # other splits it either side of the two figures.
        description = " ".join(
            part
            for part in (
                body[: cells[0].start()].strip(),
                body[cells[1].end():].strip(),
            )
            if part
        )
        description = re.sub(r"\s+", " ", description).strip()
        if not description:
            return None

        # Direction from the statement's own arithmetic. The movement between
        # two printed balances is the signed amount; where it disagrees with
        # the printed magnitude the row is not readable and the document fails
        # closed rather than publishing a sign nobody printed.
        delta = round(balance - previous, 2)
        if abs(abs(delta) - abs(magnitude)) > 0.01:
            return None
        amount = delta if delta else 0.0
        rows.append(
            Transaction(
                date=posting,
                description=description,
                amount=amount,
                direction="credit" if amount > 0 else "debit",
                running_balance=balance,
            )
        )
        previous = balance
    return rows


def parse_citibusiness_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    if not detect(markdown).claims:
        return None

    period = _period(markdown)
    beginning_match = _BEGINNING_RE.search(markdown)
    ending_match = _ENDING_RE.search(markdown)
    if period is None or not beginning_match or not ending_match:
        return None
    start, end = period
    beginning = _amount(beginning_match.group(1))
    ending = _amount(ending_match.group(1))
    if beginning is None or ending is None:
        return None

    rows = _rows(markdown, start=start, end=end, beginning=beginning)
    if not rows:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Citibank"
    holder = _holder_reading(markdown)
    if holder.name:
        stmt.holder_name, stmt.account_title = holder
    stmt.period_start = start.isoformat()
    stmt.period_end = end.isoformat()
    stmt.beginning_balance = beginning
    stmt.ending_balance = ending
    account = _ACCOUNT_RE.search(markdown)
    if account:
        stmt.account_number = account.group(1)

    totals = _TOTALS_RE.search(markdown)
    if totals:
        debits, credits = _amount(totals.group(1)), _amount(totals.group(2))
        # The row prints two magnitudes and no instance count beside either,
        # so both stated counts stay None: deriving them from the ledger would
        # manufacture the oracle the ledger is checked against.
        if debits is not None:
            stmt.stated_total_debits = abs(debits)
        if credits is not None:
            stmt.stated_total_credits = abs(credits)

    # `Average Daily Collected Balance` is printed on every one of these
    # statements and is NOT this period's: the `SERVICE CHARGE SUMMARY` block
    # it belongs to covers the previous analysis period. It is therefore never
    # read into `stated_average_balance`.
    stmt.transactions = rows
    return stmt


def closing_balance_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The relationship block against the ledger's own closing balance.

    Citibank prints the checking product's closing balance twice: once beside
    `Relationship Summary: Checking` at the top of page 1 and once as the
    ledger's `Ending Balance`. Where the two disagree the document contradicts
    itself and no reading of it is authoritative.
    """
    match = _RELATIONSHIP_RE.search(markdown)
    if not match or stmt.ending_balance is None:
        return []
    relationship = _amount(match.group(1))
    if relationship is None:
        return []
    if abs(relationship - stmt.ending_balance) > 0.01:
        return [
            "the Relationship Summary's checking balance does not equal the "
            "CHECKING ACTIVITY ending balance"
        ]
    return []
