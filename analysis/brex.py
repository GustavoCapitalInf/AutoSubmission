"""Brex business checking, issued over Column N.A.

Three things separate this layout from every other in the registry.

**The summary is a two-column grid.** Every summary row prints ``This Period``
and ``Year-to-Date`` side by side, so each figure appears twice with different
values and a reader that takes "the money on the line" gets the year's number
for the month's statement. The printed column header is what fixes the order,
and it is a required marker: without it there is no way to know which cell is
which, so the document is not this layout.

**A nil cell is a dash.** Brex prints ``-`` where a figure is zero — on
``Fees & Charges`` in all six surveyed statements, and on
``Beginning Account Balance`` for an account's first statement. Read as
"absent" instead of "zero" it would cost the statement its opening balance,
and `analysis.adb` would then derive the opening from the closing balance,
which makes the ledger identity reconcile against itself. Reading it as zero
keeps that check honest, and the reading is corroborated by the document: on
every statement where the dash appears, the printed
``beginning + additions + subtractions`` reproduces the printed ending balance
exactly with the dash valued at zero.

**There is no balance column, and the two directions are printed as separate
grids** — ``Activity - Deposits & Credits`` and
``Activity - Withdrawals & Debits``, each with its own column header and its
own printed total. Direction still comes from the sign on the amount; the grid
a row was printed in is an independent second declaration, and a row whose sign
disagrees with its grid is reported as a contradiction rather than resolved.

A long counterparty name wraps: the date and the name occupy one physical line
and the Method and Amount land on the next. A row therefore opens at a date and
stays open until an amount closes it.
"""
from __future__ import annotations

import re
from decimal import Decimal

from .date_tokens import MONTH_NAME_ALT, iso_from_named_month_day, iso_or_none
from .money import MINUS_GLYPHS, SIGNED_MONEY_TOKEN, parse_signed_decimal
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, Transaction
from .tables import compact_lines, compact_whitespace, unique_line

#: Brex's own support address, printed in the page-1 masthead. Issuer
#: furniture. Deliberately NOT the sponsor-bank line: Column N.A. sponsors
#: other fintechs in this same archive, including Mercury.
_PLATFORM_CONTACT = "support@brex.com"

#: The summary grid's column header. Two figures per row, this period first.
_SUMMARY_COLUMNS = "This Period Year-to-Date"

#: What Brex prints in a summary cell whose value is zero.
_NIL_CELL = "-"

#: One summary cell: a figure, or the nil dash.
_CELL = r"(?:" + re.escape(_NIL_CELL) + r"|" + SIGNED_MONEY_TOKEN + r")"

#: "Apr 1 - Apr 30, 2026" — the period, printed once per page. The year is
#: printed only on the end date and governs both, which is sound because Brex
#: closes its statements on calendar months.
_PERIOD_RE = re.compile(
    r"^(?P<start_month>" + MONTH_NAME_ALT + r")\s+(?P<start_day>\d{1,2})"
    r"\s*[" + MINUS_GLYPHS + r"]\s*"
    r"(?P<end_month>" + MONTH_NAME_ALT + r")\s+(?P<end_day>\d{1,2}),\s+(?P<year>\d{4})$",
    re.IGNORECASE,
)
_ACCOUNT_RE = re.compile(r"^Account Number:\s*(?P<number>[\w-]+)$", re.IGNORECASE)
_HOLDER_RE = re.compile(r"^(?P<name>\S.*?)\s+checking account$", re.IGNORECASE)

#: The two activity grids' column headers. "From" and "To" are how Brex names
#: the counterparty column, and they are also how it declares which grid this
#: is — the heading above them is not reprinted after a page break, but the
#: column header is.
_GRID_HEADER_RE = re.compile(r"^Date\s+(?P<direction>From|To)\s+Method\s+Amount$", re.IGNORECASE)

#: A grid's own printed total.
_GRID_TOTAL_RE = re.compile(
    r"^Total\s+(?P<what>Deposits & Credits|Withdrawals & Debits)\s+"
    r"(?P<value>" + SIGNED_MONEY_TOKEN + r")$",
    re.IGNORECASE,
)

#: A posting opens with its date. Everything after it is the counterparty and
#: the method, which the flattened line no longer separates.
_ROW_OPEN_RE = re.compile(r"^(?P<date>\d{1,2}/\d{1,2})\s+(?P<rest>\S.*)$")

#: A row closes on the amount, which is the last cell of the line it lands on.
_ROW_CLOSE_RE = re.compile(r"(?P<amount>" + SIGNED_MONEY_TOKEN + r")$")

_SUMMARY_ROWS = {
    "beginning": "Beginning Account Balance",
    "credits": "Additions",
    "debits": "Subtractions",
    "fees": "Fees & Charges",
    "ending": "Ending Account Balance",
}

#: The same two figures, printed a second time as the detail rows under
#: `Additions` and `Subtractions`. Read only by the integrity check.
_SUMMARY_DETAIL = {"credits": "Deposits & Credits", "debits": "Withdrawals & Debits"}


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("platform_contact", lambda t: _PLATFORM_CONTACT.upper() in t),
    # The two-column summary grid, by its printed header and its two balance
    # labels. "Account Balance" rather than plain "Balance" is Brex's wording.
    required(
        "summary_columns",
        lambda t: _SUMMARY_COLUMNS.upper() in t
        and _SUMMARY_ROWS["beginning"].upper() in t
        and _SUMMARY_ROWS["ending"].upper() in t,
    ),
    # A Method column beside a counterparty column named From or To.
    required(
        "activity_grid",
        lambda t: any(
            _GRID_HEADER_RE.match(line.strip()) for line in t.splitlines()
        ),
    ),
    corroborating(
        "split_activity_sections",
        lambda t: "DEPOSITS & CREDITS" in t and "WITHDRAWALS & DEBITS" in t,
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _summary_cell(lines: list[str], label: str) -> Decimal | None:
    """The `This Period` figure on one summary row. A nil dash reads as zero."""
    pattern = re.compile(
        r"^" + re.escape(label) + r"\s+(?P<period>" + _CELL + r")\s+(?P<ytd>" + _CELL + r")$",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.match(line)
        if match:
            cell = match.group("period")
            return Decimal(0) if cell == _NIL_CELL else parse_signed_decimal(cell)
    return None


def _postings(lines: list[str], year: int) -> tuple[list[Transaction], list[str]] | None:
    """(transactions, sign-vs-grid contradictions). None if a row was unread."""
    transactions: list[Transaction] = []
    contradictions: list[str] = []
    direction: str | None = None
    pending: list[str] | None = None

    for line in lines:
        header = _GRID_HEADER_RE.match(line)
        if header:
            if pending is not None:
                return None
            direction = "credit" if header.group("direction").lower() == "from" else "debit"
            continue
        if _GRID_TOTAL_RE.match(line):
            if pending is not None:
                return None
            direction = None
            continue
        if direction is None:
            continue

        opened = _ROW_OPEN_RE.match(line)
        if opened:
            if pending is not None:
                # The previous row never found its amount and this one has
                # already started. Reading on would attach this row's money to
                # that row's counterparty.
                return None
            pending = [opened.group("date"), opened.group("rest")]
        elif pending is not None:
            pending[1] = f"{pending[1]} {line}"
        elif _ROW_CLOSE_RE.search(line):
            # A line carrying money with no row open to attach it to. Closing
            # the grid on it would step over a posting silently, and a dropped
            # row is invisible to every arithmetic check downstream.
            return None
        else:
            # Page furniture between two rows of the same grid. The grid closes
            # here; the column header reopens it on the next page.
            direction = None
            continue

        closed = _ROW_CLOSE_RE.search(pending[1])
        if closed is None:
            continue
        amount = parse_signed_decimal(closed.group("amount"))
        description = compact_whitespace(pending[1][: closed.start()])
        # `_ROW_OPEN_RE` proved the token's SHAPE and nothing more: `13/45`
        # matches it perfectly and is not a date. `iso_or_none` is where that
        # is decided, and a Date cell that holds no date means the columns were
        # not read as they were printed — so the document is refused rather
        # than the row silently dropped, and `date()` never raises out of the
        # parser (the defect class discovery hit on 17 documents).
        month, day = (int(part) for part in pending[0].split("/"))
        date = iso_or_none(year, month, day)
        if date is None or not description:
            return None
        printed = "debit" if amount < 0 else "credit"
        if printed != direction:
            contradictions.append(
                f"{date} {description[:40]!r} is printed in the "
                f"{'Deposits & Credits' if direction == 'credit' else 'Withdrawals & Debits'} "
                f"grid but carries a {printed}'s sign"
            )
        transactions.append(
            Transaction(
                date=date,
                description=description,
                amount=float(amount),
                direction=printed,
                running_balance=None,
            )
        )
        pending = None

    return (None if pending is not None else (transactions, contradictions))


def parse_brex_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None

    lines = compact_lines(markdown)
    period = unique_line(lines, _PERIOD_RE)
    account = unique_line(lines, _ACCOUNT_RE)
    holder = unique_line(lines, _HOLDER_RE)
    if period is None or account is None:
        return None
    year = period.group("year")
    period_start = iso_from_named_month_day(
        period.group("start_month"), period.group("start_day"), year
    )
    period_end = iso_from_named_month_day(
        period.group("end_month"), period.group("end_day"), year
    )
    if period_start is None or period_end is None or period_start > period_end:
        return None

    beginning = _summary_cell(lines, _SUMMARY_ROWS["beginning"])
    ending = _summary_cell(lines, _SUMMARY_ROWS["ending"])
    credits = _summary_cell(lines, _SUMMARY_ROWS["credits"])
    debits = _summary_cell(lines, _SUMMARY_ROWS["debits"])
    fees = _summary_cell(lines, _SUMMARY_ROWS["fees"])
    if beginning is None or ending is None or credits is None or debits is None:
        return None

    read = _postings(lines, int(year))
    if read is None:
        return None
    transactions, _contradictions = read
    if not transactions:
        return None

    return Statement(
        bank="Brex",
        account_name=holder.group("name") if holder else None,
        account_number=account.group("number"),
        period_start=period_start,
        period_end=period_end,
        beginning_balance=float(beginning),
        ending_balance=float(ending),
        currency="USD",
        stated_total_credits=float(abs(credits)),
        stated_total_debits=float(abs(debits)),
        stated_service_charge=None if fees is None else float(abs(fees)),
        transactions=transactions,
    )


def printed_total_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """Brex prints each direction's total three times; do the three agree?

    Once in the summary's ``Additions`` / ``Subtractions`` row, once in the
    detail row beneath it, and once as the closing ``Total`` of the matching
    activity grid. Only the first is used to build the statement, so the other
    two are independent printings — and a row printed in the wrong grid for its
    sign is the fourth thing this check can see.
    """
    notes: list[str] = []
    lines = compact_lines(markdown)

    for key, stated in (
        ("credits", stmt.stated_total_credits),
        ("debits", stmt.stated_total_debits),
    ):
        if stated is None:
            continue
        magnitude = Decimal(str(round(stated, 2)))
        detail = _summary_cell(lines, _SUMMARY_DETAIL[key])
        if detail is not None and abs(detail) != magnitude:
            notes.append(
                f"the summary's {_SUMMARY_ROWS[key]} row states "
                f"{float(magnitude):,.2f} but its {_SUMMARY_DETAIL[key]} row "
                f"states {float(abs(detail)):,.2f}"
            )
        for line in lines:
            total = _GRID_TOTAL_RE.match(line)
            if total and total.group("what").lower() == _SUMMARY_DETAIL[key].lower():
                printed = abs(parse_signed_decimal(total.group("value")))
                if printed != magnitude:
                    notes.append(
                        f"the {_SUMMARY_DETAIL[key]} grid totals "
                        f"{float(printed):,.2f} but the summary states "
                        f"{float(magnitude):,.2f}"
                    )
                break

    period = unique_line(lines, _PERIOD_RE)
    if period is not None:
        read = _postings(lines, int(period.group("year")))
        if read is not None:
            notes.extend(read[1])
    return notes
