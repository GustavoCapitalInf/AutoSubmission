"""Square Checking — the Block, Inc. `Checking statement` layout.

Found in the unclaimed-layout cell of the `Chase/` folder: a folder label is a
filing convention, not an issuer claim, and this statement is Square's, not
Chase's. Chase appears on it only the way any bank appears on any statement —
as the counterparty of a recurring transfer — which is exactly the R4-3 hazard
the detection markers below are written to avoid.

The layout is unusually well-instrumented, and every rule here is anchored on
something the statement prints about itself:

    Square Checking Routing number: ...
    Account number: ...
    Checking statement <Month> <D> - <Month> <D>, <YYYY>
    Starting balance Activities Ending balance   <money> <count> <money>
    ...
    Date Details Activity type Balance Amount
    <M/D/YYYY> <details> <activity type> <balance> <amount>

**Direction is printed, not inferred.** The Amount column carries its own sign
(`-$18.42` for a card spend, `$317.00` for a sale), so no description wording
and no arithmetic is needed to orient a row.

**The Balance column is the row's, and it is printed on every row.** The grid
header names the printed column order — Balance *then* Amount — so the row's
last two money cells are read in that order rather than by guessing which of
the two is larger. Every row's balance therefore follows from the row above,
which is what `analysis/reconcile.py` checks and what makes a mis-read row a
continuity break instead of a ledger that quietly balances with itself.

Three independent printings check each other on every document: the summary
row's starting and ending balances, the `Activities` count against the number
of rows read, and the running balance printed on each row.
"""
from __future__ import annotations

import re
from datetime import date

from .money import parse_grouped_float
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace, group_rows

_MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11,
    "DECEMBER": 12,
}
_MONTH_NAMES = "|".join(_MONTHS)

#: Every money cell of this layout is printed with the currency symbol, and the
#: sign — when there is one — stands outside it: `-$1,234.56`, `+$920.00`.
#: Requiring the symbol is what keeps a bare reference number in the Details
#: column out of the money columns.
_MONEY = re.compile(r"[-+]?\$-?[\d,]+\.\d{2}")

_PERIOD = re.compile(
    rf"CHECKING STATEMENT\s+({_MONTH_NAMES})\s+(\d{{1,2}})\s*[-‐-―]\s*"
    rf"({_MONTH_NAMES})\s+(\d{{1,2}}),\s*(\d{{4}})",
    re.IGNORECASE,
)
_SUMMARY = re.compile(
    rf"STARTING BALANCE ACTIVITIES ENDING BALANCE\s+({_MONEY.pattern})\s+(\d+)\s+({_MONEY.pattern})",
    re.IGNORECASE,
)
#: The account number is masked by the issuer; only the trailing digits survive
#: the mask, and they are the only part of it this statement ever prints.
_ACCOUNT = re.compile(r"ACCOUNT NUMBER:\s*\S*?(\d{4})\s*$", re.IGNORECASE | re.MULTILINE)
_GRID_HEADER = "DATE DETAILS ACTIVITY TYPE BALANCE AMOUNT"
#: A row starts where the grid starts one: the printed Date column.
_ROW_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})\b")
#: The grid's own column header, reprinted at the top of every page. It closes
#: whatever row was open and starts nothing — grid furniture, not a row.
_GRID_HEADER_LINE = re.compile(rf"^{_GRID_HEADER}$", re.IGNORECASE)


def _normalized(markdown: str) -> str:
    """The statement with the text layer's spacing normalized and nothing else.

    Inter-word spacing is a property of the text layer, not of the statement
    (the §BMO-LAYOUTS M3.1 rule): the same furniture renders as `Block Inc.`
    and `Block  Inc.` out of different producers. Only the gaps between words
    are touched — no money or date token is relaxed, and **case is preserved**,
    because the Details column is description text this platform publishes.
    """
    return "\n".join(compact_whitespace(line) for line in markdown.splitlines())


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in: normalized spacing, upper
    case, so a producer's capitalisation cannot decide whether we claim."""
    return _normalized(markdown).upper()


#: Issuer furniture only (R-4b): the product name printed beside the routing
#: number in the statement header, the issuer's legal entity and help domain in
#: every page footer, and the printed column header of the activity grid.
#: Nothing here is a customer, an amount or a date, and nothing here can be
#: satisfied by another bank's statement merely naming Square in a row.
DETECTION_MARKERS = (
    required("issuer_product_header", lambda t: "SQUARE CHECKING ROUTING NUMBER:" in t),
    required("issuer_legal_footer", lambda t: "BLOCK INC." in t),
    required("issuer_help_domain", lambda t: "SQUAREUP.COM/HELP" in t),
    required("activity_grid_header", lambda t: _GRID_HEADER in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _amount(token: str) -> float:
    """One printed money cell. The sign stands outside the currency symbol."""
    negative = token.startswith("-") or token.startswith("$-")
    value = parse_grouped_float(token.lstrip("-+").replace("$", "").lstrip("-"))
    return round(-value if negative else value, 2)


def _period(text: str) -> tuple[date, date] | None:
    """The period the statement names in its own title line.

    Only one year is printed, and it belongs to the closing date; a period that
    opens in the previous calendar year is recognised by its opening month
    standing after its closing month, which is the only ordering that can occur.
    """
    match = _PERIOD.search(text)
    if not match:
        return None
    start_month = _MONTHS[match.group(1).upper()]
    end_month = _MONTHS[match.group(3).upper()]
    year = int(match.group(5))
    try:
        end = date(year, end_month, int(match.group(4)))
        start = date(
            year - 1 if start_month > end_month else year,
            start_month,
            int(match.group(2)),
        )
    except ValueError:
        return None
    return (start, end) if start <= end else None


def parse_square_checking_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None

    text = _normalized(markdown)
    period = _period(text)
    if period is None:
        return None
    period_start, period_end = period

    summary = _SUMMARY.search(text)
    if summary is None:
        return None

    stmt = Statement(bank="Square", currency="USD")
    stmt.period_start = period_start.isoformat()
    stmt.period_end = period_end.isoformat()
    stmt.beginning_balance = _amount(summary.group(1))
    stmt.ending_balance = _amount(summary.group(3))

    account = _ACCOUNT.search(text)
    if account:
        stmt.account_number = account.group(1)

    lines = [line for line in (raw.strip() for raw in text.splitlines()) if line]
    transactions: list[Transaction] = []
    for group in group_rows(
        lines,
        starts_row=lambda line: bool(_ROW_DATE.match(line)),
        ends_row=lambda line: bool(_GRID_HEADER_LINE.match(line)),
    ):
        joined = compact_whitespace(" ".join(group))
        match = _ROW_DATE.match(joined)
        if not match:
            continue
        # A row's money cells are the last two the row prints. Everything after
        # them is the page footer Square repeats under each page's last row,
        # which carries no money and so cannot be mistaken for a cell.
        cells = list(_MONEY.finditer(joined))
        if len(cells) < 2:
            continue
        try:
            posted = date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
        except ValueError:
            continue
        if not (period_start <= posted <= period_end):
            continue
        # Matches, not strings: the amount's characters occur again inside the
        # balance printed beside it, so the description is sliced by position.
        description = compact_whitespace(joined[match.end():cells[-2].start()])
        if not description:
            continue
        # The grid header prints the column order: Balance, then Amount.
        balance = _amount(cells[-2].group(0))
        amount = _amount(cells[-1].group(0))
        transactions.append(Transaction(
            date=posted.isoformat(),
            description=description,
            amount=amount,
            direction="credit" if amount > 0 else "debit",
            running_balance=balance,
        ))

    if not transactions:
        return None
    stmt.transactions = transactions
    return stmt


def activity_count_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """Square prints how many activities the period contains, beside the two
    balances the same row states.

    Registered as this parser's `integrity_check` so a document whose printed
    count and printed ledger disagree is reported as contradicting itself rather
    than published as though the ledger were complete.
    """
    summary = _SUMMARY.search(_normalized(markdown))
    if summary is None:
        return []
    if int(summary.group(2)) != len(stmt.transactions):
        return [
            "the statement summary states a different number of activities "
            "than the activity grid lists"
        ]
    return []
