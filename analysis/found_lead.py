"""Found — the fintech statement issued over Lead Bank.

Found prints two documents from one generator: a closed monthly
``Account Statement`` and a mid-month ``Activity (Month to Date)``. They share
this module and this reader, and they are **two registrations**, because the
issuer says they are two things:

    "The information in this document is not a bank statement and therefore
    should not be relied upon as a bank statement."

That sentence is printed on the month-to-date document and on no other — 3 of
the 15 surveyed documents carry it, and the 12 closed statements do not. It is
the same finding the registry already models for a Chase transaction export, so
it is modelled the same way: `found_lead_activity` registers with
``formal_statement=False`` and carries the issuer's own words as its note, and
the document is routed to review rather than published as a validated bank
statement. The two registrations cannot both claim: the disclaimer is a
REQUIRED marker on one and an EXCLUDING marker on the other.

Two things about the layout decide the rest of the design.

**A pending item is not a posting.** The month-to-date document prints a
``Pending transactions`` grid above the settled one, and the bank marks every
row of it as unsettled by printing ``--`` in BOTH the Date and the Balance
column — it has no posting date and no effect on the balance yet. Booking those
rows would inflate the ledger against the bank's own totals. They are excluded
on the two printed marks together, not on the section heading alone, and the
heading is then required to agree: a row that claims to be pending outside the
pending grid means this reader has lost its place, and the document is refused.

**The Fees line is a memo inside the debit total, not a separate deduction.**
``beginning + credits - debits`` reproduces the printed ending balance exactly
on all 15 surveyed statements, with the printed ``Fees`` figure already
contained in ``Purchases & other debits``. It is published as
`stated_service_charge` for reporting and is deliberately NOT subtracted a
second time.
"""
from __future__ import annotations

import re
from decimal import Decimal

from .date_tokens import MONTH_NAME_ALT, iso_from_named_month_day, iso_or_none
from .money import SIGNED_MONEY_TOKEN, parse_signed_decimal
from .parser_registry import corroborating, excluding, make_detector, required
from .schema import Statement, Transaction
from .tables import compact_lines, unique_line

#: The platform's own disclosure line and its sponsor's, printed in the footer
#: of every page. Issuer furniture: neither names a counterparty.
_PLATFORM_DISCLOSURE = "Found is a financial technology company, not a bank."
_SPONSOR_DISCLOSURE = "Banking services are provided by Lead Bank, Member FDIC."

#: The issuer's own refusal of the word "statement", printed only on the
#: month-to-date document. Matched on the clause rather than the whole
#: paragraph: the paragraph is flowed text and the PDF breaks it at a different
#: word depending on the page, but this clause survives on one line in all
#: three surveyed documents.
_NOT_A_STATEMENT_DISCLAIMER = "is not a bank statement and therefore should not be relied upon"

#: The posting grid's column header, reprinted at the top of every page.
_GRID_HEADER = "Date Description Amount Balance"

#: The two grid headings. The settled grid is titled "Transactions"; the
#: month-to-date document adds an unsettled one above it.
_SETTLED_SECTION = "Transactions"
_PENDING_SECTION = "Pending transactions"

#: What Found prints in a column that has no value yet.
_NIL_CELL = "--"

_TITLE_RE = re.compile(
    r"^(?:" + MONTH_NAME_ALT + r")\s+\d{4}\s+"
    r"(?:Account Statement|Activity \(Month to Date\))$",
    re.IGNORECASE,
)

#: "Beginning balance on February 1, 2026 $0.00" — the summary prints the
#: period boundary INSIDE the label of each balance, which is where this parser
#: takes the period from: one printed date per balance, each with its own year.
_BALANCE_RE = re.compile(
    r"^(?P<which>Beginning|Ending)\s+balance\s+on\s+"
    r"(?P<month>" + MONTH_NAME_ALT + r")\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})\s+"
    r"(?P<value>" + SIGNED_MONEY_TOKEN + r")$",
    re.IGNORECASE,
)

#: "February 1 to February 28, 2026" — the period, printed a second time in the
#: header block. Read only by the integrity check.
_PERIOD_RE = re.compile(
    r"^(?P<start_month>" + MONTH_NAME_ALT + r")\s+(?P<start_day>\d{1,2})\s+to\s+"
    r"(?P<end_month>" + MONTH_NAME_ALT + r")\s+(?P<end_day>\d{1,2}),\s+(?P<year>\d{4})$",
    re.IGNORECASE,
)

#: Routing and account number are printed as bare digit groups under a
#: flattened two-column label block, so the label is no longer beside its
#: value. The two GROUPINGS differ, and that is what tells them apart.
_ACCOUNT_NUMBER_RE = re.compile(r"^\d{4} \d{4} \d{4}$")

_HOLDER_RE = re.compile(r"^(?:Business|Legal) name:\s*(?P<name>\S.*)$", re.IGNORECASE)

#: One posting. Date and Balance are ``--`` on an unsettled row and printed on
#: a settled one; the amount always carries its sign.
_ROW_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{2}|" + re.escape(_NIL_CELL) + r")\s+"
    r"(?P<description>\S.*?)\s+"
    r"(?P<amount>" + SIGNED_MONEY_TOKEN + r")\s+"
    r"(?P<balance>" + re.escape(_NIL_CELL) + r"|" + SIGNED_MONEY_TOKEN + r")$"
)

#: A line that ends in money. Inside an open grid that is a row this reader
#: failed to read, never page furniture.
_TRAILING_MONEY_RE = re.compile(SIGNED_MONEY_TOKEN + r"$")

_SUMMARY_CREDITS_RE = re.compile(
    r"^Deposits & other credits\s+(?P<value>" + SIGNED_MONEY_TOKEN + r")$", re.IGNORECASE
)
_SUMMARY_DEBITS_RE = re.compile(
    r"^Purchases & other debits\s+(?P<value>" + SIGNED_MONEY_TOKEN + r")$", re.IGNORECASE
)
_SUMMARY_FEES_RE = re.compile(
    r"^Fees\s+(?P<value>" + SIGNED_MONEY_TOKEN + r")$", re.IGNORECASE
)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


#: The evidence that says "Found, over Lead Bank" and nothing about which of
#: the issuer's two documents this is.
_ISSUER_MARKERS = (
    required("platform_disclosure", lambda t: _PLATFORM_DISCLOSURE.upper() in t),
    required("sponsor_disclosure", lambda t: _SPONSOR_DISCLOSURE.upper() in t),
    required(
        "summary_block",
        lambda t: "ACCOUNT SUMMARY" in t
        and "DEPOSITS & OTHER CREDITS" in t
        and "PURCHASES & OTHER DEBITS" in t,
    ),
    corroborating("activity_grid", lambda t: _GRID_HEADER.upper() in t),
    corroborating("statement_title", lambda t: any(
        _TITLE_RE.match(line.strip()) for line in t.splitlines()
    )),
)


def _declines_to_be_a_statement(text: str) -> bool:
    return _NOT_A_STATEMENT_DISCLAIMER.upper() in text


#: The closed monthly statement: the issuer's furniture, and the absence of its
#: own disclaimer. EXCLUDING rather than "not required", so this registration
#: scores 0.0 on a month-to-date document before any other marker runs and the
#: two can never resolve `ambiguous`.
DETECTION_MARKERS = (
    *_ISSUER_MARKERS,
    excluding("month_to_date_disclaimer", _declines_to_be_a_statement),
)

#: The month-to-date view, identified by the sentence in which the issuer
#: refuses the word "statement".
ACTIVITY_DETECTION_MARKERS = (
    *_ISSUER_MARKERS,
    required("month_to_date_disclaimer", _declines_to_be_a_statement),
)

detect = make_detector(DETECTION_MARKERS, detection_text)
activity_detect = make_detector(ACTIVITY_DETECTION_MARKERS, detection_text)

#: The guard on the module-level `parse`, which is the issuer evidence alone:
#: which of the two documents this is changes how the platform REPORTS the
#: result, not how the grid is read, and `resolve` has already decided that
#: question before either registration's `parse` is reached.
_issuer_detect = make_detector(_ISSUER_MARKERS, detection_text)


def _postings(lines: list[str]) -> tuple[list[Transaction], int] | None:
    """(settled transactions, pending rows excluded). None if a line was unread.

    A grid opens at the printed column header and closes at the first line
    that is not a posting row — the page footer, and on the month-to-date
    document a paragraph of flowed legal text.

    Two things are NOT tolerated, and both are the same concern: a dropped row
    is invisible to every arithmetic check downstream, because the rows that
    remain still sum to their own total, walk to the closing balance and
    reconcile. So the document is refused when

    * a line inside an open grid carries MONEY and is not a row — that is a
      posting this reader could not place, not furniture; and
    * a posting row appears outside an open grid — that means the reader lost
      its place and has been stepping over rows since.
    """
    transactions: list[Transaction] = []
    pending = 0
    section: str | None = None
    inside = False

    for line in lines:
        lowered = line.lower()
        if lowered == _PENDING_SECTION.lower():
            section, inside = _PENDING_SECTION, False
            continue
        if lowered == _SETTLED_SECTION.lower():
            section, inside = _SETTLED_SECTION, False
            continue
        if line == _GRID_HEADER:
            inside = True
            continue

        match = _ROW_RE.match(line)
        if match is None:
            if inside and _TRAILING_MONEY_RE.search(line):
                # A line carrying money that is not a row this reader can
                # place. Closing the grid on it would step over it silently.
                return None
            inside = False
            continue
        if not inside:
            return None

        unsettled = match.group("date") == _NIL_CELL
        if unsettled != (match.group("balance") == _NIL_CELL):
            # Half a pending row: the two nil marks are one fact about the row
            # and they cannot disagree. If they do, the columns have not been
            # read the way they were printed.
            return None
        if unsettled:
            if section != _PENDING_SECTION:
                return None
            pending += 1
            continue
        if section != _SETTLED_SECTION:
            return None

        # The row pattern proved the token's SHAPE only: `13/45/26` matches
        # it perfectly and is not a date. A Date cell that holds no date means
        # the columns were not read as they were printed, so the document is
        # refused rather than the row dropped — and `date()` never raises out
        # of the parser.
        month, day, year = (int(part) for part in match.group("date").split("/"))
        posted = iso_or_none(2000 + year, month, day)
        if posted is None:
            return None
        amount = parse_signed_decimal(match.group("amount"))
        transactions.append(
            Transaction(
                date=posted,
                description=match.group("description"),
                amount=float(amount),
                direction="debit" if amount < 0 else "credit",
                running_balance=float(parse_signed_decimal(match.group("balance"))),
            )
        )
    return transactions, pending


def parse_found_lead_statement(markdown: str) -> Statement | None:
    if not _issuer_detect(markdown).claims:
        return None

    lines = compact_lines(markdown)
    balances: dict[str, tuple[str, Decimal]] = {}
    for line in lines:
        match = _BALANCE_RE.match(line)
        if not match:
            continue
        day = iso_from_named_month_day(
            match.group("month"), match.group("day"), match.group("year")
        )
        if day is None:
            return None
        which = match.group("which").lower()
        value = (day, parse_signed_decimal(match.group("value")))
        if balances.setdefault(which, value) != value:
            return None
    if "beginning" not in balances or "ending" not in balances:
        return None
    (period_start, beginning), (period_end, ending) = balances["beginning"], balances["ending"]
    if period_start > period_end:
        return None

    credits = next(
        (parse_signed_decimal(m.group("value"))
         for m in map(_SUMMARY_CREDITS_RE.match, lines) if m),
        None,
    )
    debits = next(
        (parse_signed_decimal(m.group("value"))
         for m in map(_SUMMARY_DEBITS_RE.match, lines) if m),
        None,
    )
    fees = next(
        (parse_signed_decimal(m.group("value"))
         for m in map(_SUMMARY_FEES_RE.match, lines) if m),
        None,
    )
    if credits is None or debits is None:
        return None

    account = unique_line(lines, _ACCOUNT_NUMBER_RE)
    if account is None:
        return None
    holder = next(
        (m.group("name") for m in map(_HOLDER_RE.match, lines) if m), None
    )

    read = _postings(lines)
    if read is None:
        return None
    transactions, _pending = read
    if not transactions:
        return None

    return Statement(
        bank="Lead Bank (Found)",
        account_name=holder,
        account_number=account.group(0),
        period_start=period_start,
        period_end=period_end,
        days_in_period=None,
        beginning_balance=float(beginning),
        ending_balance=float(ending),
        currency="USD",
        stated_total_credits=float(abs(credits)),
        stated_total_debits=float(abs(debits)),
        # A memo line inside the debit total (see the module docstring), so it
        # is reported and never deducted a second time.
        stated_service_charge=None if fees is None else float(abs(fees)),
        transactions=transactions,
    )


def printed_period_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The period Found prints in its header block, against the one in its
    balance labels.

    Two independent printings of the same fact: the header block states
    "February 1 to February 28, 2026" and each summary balance carries its own
    boundary date inside its label. The statement is built from the labels, so
    the header block is a free second opinion — and a document whose two
    printings disagree is telling a human something.
    """
    notes: list[str] = []
    for line in compact_lines(markdown):
        match = _PERIOD_RE.match(line)
        if not match:
            continue
        year = match.group("year")
        printed_start = iso_from_named_month_day(
            match.group("start_month"), match.group("start_day"), year
        )
        printed_end = iso_from_named_month_day(
            match.group("end_month"), match.group("end_day"), year
        )
        if printed_start != stmt.period_start or printed_end != stmt.period_end:
            notes.append(
                f"the header block states a period of {printed_start} to "
                f"{printed_end}, but the summary balances are labelled "
                f"{stmt.period_start} and {stmt.period_end}"
            )
        break
    return notes
