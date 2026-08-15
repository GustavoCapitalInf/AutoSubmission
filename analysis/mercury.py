"""Mercury — the fintech statement issued over Column N.A. and Choice Financial.

Mercury is not a bank; it is a platform that prints one statement layout over
whichever sponsor bank holds the deposits, and the sponsor is named only in a
footer line. The layout is therefore Mercury's, not the sponsor's, and this
module keys on Mercury's own furniture.

Three properties of the printed grid decide the whole design.

**The balance column prints once per DAY, not once per row.** ``End of Day
Balance`` is exactly what it says: the last posting of a calendar day carries
the balance and every earlier posting of that day carries none. A reader that
expects a balance on every row either drops the rows without one or hands the
day's balance to the wrong posting. Rows without a balance publish
``running_balance=None``, which is the state
``analysis.reconcile.reconcile`` already accumulates across.

**The date column prints once per DAY as well**, so a row with no date
continues the day above it — across page breaks included, because Mercury
splits a day's postings over two pages without reprinting the date.

**The Type column is not a direction column.** It names the product ("ACH In",
"Transfer Out", "Credit Account Payment", "Intl. Transaction Fee") or, on a
card posting, the masked card number — and it contradicts the printed sign
often enough that reading direction from it would be a defect rather than a
risk. Measured over the 31 surveyed statements and their 2,696 postings:

===============================  ======  ==================================
Type cell                        rows    against the printed sign
===============================  ======  ==================================
a masked card number             639     no direction word at all; 27 are
                                         credits (refunds)
``Credit Account Payment``       120     says "Credit", every one a DEBIT
``Credit Cashback Deposit``      118     says "Credit", every one a CREDIT
``Intl. Transaction Fee``        155     a fee, and 4 of them are CREDITS
``Wire`` / ``Wire Payment``      28      the same instrument in both
                                         directions
===============================  ======  ==================================

**Direction comes from the sign printed on the amount, and from nothing
else.** The same is true of the icon glyph described below: it agrees with the
sign on 2,057 rows and cannot be relied on for the other 639, so it is used as
a COLUMN BOUNDARY and never as evidence about direction.
"""
from __future__ import annotations

import re
from decimal import Decimal

from .date_tokens import MONTH_NAME_ALT, PERIOD_DASH, iso_from_named_month_day
from .money import SIGNED_MONEY_TOKEN, parse_signed_decimal
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, Transaction
from .tables import compact_lines, compact_whitespace, unique_line

#: Mercury sets the Type column behind a small icon from its own webfont, and
#: that font maps its icons into the Unicode Private Use Area. A PUA codepoint
#: means nothing on its own — which is the point: this is not read as a symbol
#: but as INK, the one mark of the Description | Type column boundary that
#: survives PDF flattening.
#:
#: Measured over the 31 surveyed statements: 2,696 of 2,696 posting rows carry
#: exactly one, no row carries two, and no occurrence falls anywhere outside
#: the posting grid. Requiring it is therefore a structural test that a line is
#: a posting row, and it is the reason this parser can refuse an unread line
#: instead of silently dropping it.
_TYPE_MARK_RE = re.compile("[-]")

#: "April 2026 statement April 1, 2026-April 30, 2026 (30 days) All dates in UTC"
#:
#: The separator is `PERIOD_DASH`, the date-range class, not the money sign
#: class this line used to borrow: a dash between two dates is punctuation and
#: may be read widely, where the same width in a sign position would invert an
#: amount (W3 §MGD). All 31 archive documents print the ASCII hyphen.
_PERIOD_RE = re.compile(
    r"^(?:" + MONTH_NAME_ALT + r")\s+\d{4}\s+statement\s+"
    r"(?P<start_month>" + MONTH_NAME_ALT + r")\s+(?P<start_day>\d{1,2}),\s+(?P<start_year>\d{4})"
    r"\s*" + PERIOD_DASH + r"\s*"
    r"(?P<end_month>" + MONTH_NAME_ALT + r")\s+(?P<end_day>\d{1,2}),\s+(?P<end_year>\d{4})"
    r"\s*\((?P<days>\d{1,3})\s+days?\)",
    re.IGNORECASE,
)

#: The printed column header of the posting grid. Mercury reprints it at the
#: top of every page, and it is what opens the grid for this reader.
_GRID_HEADER = "Date (UTC) Description Type Amount End of Day Balance"

#: The grid's own closing row: the statement balance, printed a second time
#: under the Balance column.
_GRID_TOTAL_RE = re.compile(r"^Total\s+(?P<total>" + SIGNED_MONEY_TOKEN + r")$")

#: One posting. Date and balance are both optional because both columns print
#: once per day; the amount and the Type mark are not.
#:
#: The row is split at the Type mark rather than at "the last money on the
#: line", and that is load-bearing rather than tidy. With the balance column
#: optional, a description ENDING in a money token is ambiguous —
#: ``Alpha $5.00 -$10.00`` reads equally well as (amount $5.00, balance
#: -$10.00) and as (description "Alpha $5.00", amount -$10.00, no balance) —
#: and a non-greedy pattern silently picks the first. §RBCCIBC lost nine
#: documents to exactly that shape (`SERVICE CHARGE ... FEE$16.95` booked
#: twice). The mark makes the question structural instead of a guess: the
#: money columns are what follows it, and the description is what precedes it.
#: Measured over the surveyed set: 0 of 2,696 descriptions contain a money
#: token, so this changes no reading today and removes the way it could break.
#:
#: `description` may be EMPTY: a row whose Description cell is blank prints its
#: Type mark straight after the date, and a group that demanded a non-space
#: character there would backtrack and swallow the DATE into the description —
#: costing the row its posting day. Ocean's review is what found that, by
#: asking whether this pattern really differed from the one it replaced.
_ROW_RE = re.compile(
    r"^(?:(?P<month>" + MONTH_NAME_ALT + r")\s+(?P<day>\d{1,2})\s+)?"
    r"(?P<description>.*?)\s*"
    r"(?P<mark>[-])"
    r"(?P<type>[^-]*?)\s+"
    r"(?P<amount>" + SIGNED_MONEY_TOKEN + r")"
    r"(?:\s+(?P<balance>" + SIGNED_MONEY_TOKEN + r"))?$",
    re.IGNORECASE,
)

#: A line that ends in money. Inside an open grid, a line that is one of these
#: and is NOT a posting row is a row this reader failed to place.
_TRAILING_MONEY_RE = re.compile(SIGNED_MONEY_TOKEN + r"$")

_ACCOUNT_RE = re.compile(r"^Account Number\s+(?P<number>[\w-]+)$", re.IGNORECASE)
_ACCOUNT_TYPE_RE = re.compile(r"^Account Type\s+(?P<kind>\S.*)$", re.IGNORECASE)

_SUMMARY_LABELS = {
    "beginning": "Beginning Balance",
    "debits": "Total withdrawals",
    "credits": "Total deposits",
    "ending": "Statement balance",
}


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    # Mercury's own contact line, printed in the footer of every page. Issuer
    # furniture: it names the platform, not a counterparty and not a customer.
    required("platform_contact", lambda t: "HELP@MERCURY.COM" in t),
    # The posting grid's column header, in full. Six columns in this order —
    # including a Type column and a date column declared to be UTC — is the
    # structural sentinel of this layout.
    required("activity_grid", lambda t: _GRID_HEADER.upper() in t),
    # The summary block's own two labels. "Statement balance" rather than
    # "Ending balance" is Mercury's wording.
    required(
        "summary_block",
        lambda t: "ACCOUNT ACTIVITY" in t and "STATEMENT BALANCE" in t,
    ),
    # The sponsor-bank disclosure. Corroborating and not required: the sponsor
    # differs between statements (Column N.A. and Choice Financial Group both
    # appear in the surveyed set) and other fintechs print the same sentence
    # over the same sponsors, so it is evidence FOR Mercury only alongside the
    # markers above — never on its own.
    corroborating(
        "sponsor_disclosure",
        lambda t: "BANKING SERVICES PROVIDED BY" in t and "MEMBER FDIC" in t,
    ),
    corroborating("account_details", lambda t: "ACCOUNT DETAILS" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _summary_figure(lines: list[str], label: str) -> Decimal | None:
    pattern = re.compile(
        r"^" + re.escape(label) + r"\s+(?P<value>" + SIGNED_MONEY_TOKEN + r")$",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.match(line)
        if match:
            return parse_signed_decimal(match.group("value"))
    return None


def _account_holder(lines: list[str]) -> str | None:
    """The name printed between the period header and `Account details`.

    Positional, and deliberately so: Mercury prints the holder on its own line
    with no label, and the two lines that bracket it are both fixed furniture.
    Anything other than exactly one line between them means this is not the
    layout that was surveyed, and the caller gets None rather than a guess.
    """
    for index, line in enumerate(lines):
        if _PERIOD_RE.match(line):
            if index + 2 < len(lines) and lines[index + 2].lower() == "account details":
                return lines[index + 1]
            return None
    return None


def _postings(
    lines: list[str], period_start: str, period_end: str
) -> tuple[list[Transaction], Decimal | None, int] | None:
    """(transactions, the grid's printed total, lines seen inside the grid).

    None when a line inside the grid could not be read. A dropped row is
    invisible to every arithmetic check downstream — the remaining rows still
    sum to their own total — so this reader refuses the document instead.
    """
    transactions: list[Transaction] = []
    printed_total: Decimal | None = None
    seen = 0
    current_date: str | None = None
    inside = False

    for line in lines:
        if line == _GRID_HEADER:
            inside = True
            continue
        total = _GRID_TOTAL_RE.match(line)
        if total:
            printed_total = parse_signed_decimal(total.group("total"))
            inside = False
            continue

        match = _ROW_RE.match(line)
        if match is None:
            if inside and _TRAILING_MONEY_RE.search(line):
                # A line carrying money that this reader cannot place as a
                # posting — no Type mark, so no column boundary. Stepping over
                # it would drop a row, and a dropped row is invisible to every
                # arithmetic check downstream because the rows that remain
                # still sum to their own total.
                return None
            # Page furniture (and, outside the grid, the summary block's
            # row-shaped `Beginning Balance $0.00`). The grid closes here and
            # the next page's column header reopens it.
            inside = False
            continue
        if not inside:
            # A posting outside an open grid means this reader lost its place.
            return None
        seen += 1

        # Description and Type, rejoined by the space their columns already
        # put between them. Any FURTHER mark inside the description (a row
        # printing two icons) is scrubbed the same way: a Private Use glyph is
        # column furniture and must never survive into a published field.
        body = _TYPE_MARK_RE.sub(
            " ", f"{match.group('description')} {match.group('type')}"
        )
        if match.group("month"):
            day = iso_from_named_month_day(
                match.group("month"), match.group("day"), period_start[:4]
            )
            # A Date cell holds a day of THIS statement's period, so a leading
            # month word that resolves OUTSIDE it is not the date: the token is
            # given back to the description — dropping it would edit what the
            # bank printed — and the row continues the day above.
            #
            # SCOPE, stated honestly (Ocean's review): this rejects only the
            # out-of-period case. A merchant name opening with a month word
            # that happens to land INSIDE the period ("May 15 Holdings" on a
            # May statement) is still read as a date, and would re-date the row
            # and the end-of-day balance attributed to it. The balance walk
            # and `posting_dates_cover_source` are what would catch it; no
            # surveyed row prints the shape, and the period test is a
            # narrowing, never a widening.
            if day is not None and period_start <= day <= period_end:
                current_date = day
            else:
                body = f"{match.group('month')} {match.group('day')} {body}"
        if current_date is None:
            return None

        amount = parse_signed_decimal(match.group("amount"))
        balance = (
            parse_signed_decimal(match.group("balance"))
            if match.group("balance")
            else None
        )
        transactions.append(
            Transaction(
                date=current_date,
                # Description and Type, as printed, with the icon that divided
                # them replaced by the space the columns already put there.
                # The schema has no Type field, so the alternative is to drop
                # what the bank printed.
                description=compact_whitespace(body),
                amount=float(amount),
                direction="debit" if amount < 0 else "credit",
                running_balance=None if balance is None else float(balance),
            )
        )
    return transactions, printed_total, seen


def parse_mercury_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None

    lines = compact_lines(markdown)
    period = unique_line(lines, _PERIOD_RE)
    account = unique_line(lines, _ACCOUNT_RE)
    account_type = unique_line(lines, _ACCOUNT_TYPE_RE)
    if period is None or account is None:
        return None
    period_start = iso_from_named_month_day(
        period.group("start_month"), period.group("start_day"), period.group("start_year")
    )
    period_end = iso_from_named_month_day(
        period.group("end_month"), period.group("end_day"), period.group("end_year")
    )
    if period_start is None or period_end is None or period_start > period_end:
        return None

    beginning = _summary_figure(lines, _SUMMARY_LABELS["beginning"])
    ending = _summary_figure(lines, _SUMMARY_LABELS["ending"])
    credits = _summary_figure(lines, _SUMMARY_LABELS["credits"])
    debits = _summary_figure(lines, _SUMMARY_LABELS["debits"])
    if beginning is None or ending is None or credits is None or debits is None:
        return None

    holder = _account_holder(lines)
    if holder is None:
        return None

    read = _postings(lines, period_start, period_end)
    if read is None:
        return None
    transactions, printed_total, seen = read

    if not transactions:
        # A period with no activity is a statement, not a parse failure — on
        # the bank's own evidence and no other. The rule Ocean ruled for Chase
        # (A-prime) and applied in §SCOTIA-REBUILD F9, in the terms Mercury
        # prints: the grid must have been EMPTY rather than unread (`seen`),
        # both stated totals zero, and the two balances printed and equal. An
        # empty ledger on any other document means the detail was not read,
        # and that still refuses.
        printed_zero_activity = (
            seen == 0
            and credits == 0
            and debits == 0
            and beginning == ending
        )
        if not printed_zero_activity:
            return None

    return Statement(
        bank="Mercury",
        account_name=f"{holder} {account_type.group('kind')}".strip()
        if account_type
        else holder,
        account_number=account.group("number"),
        period_start=period_start,
        period_end=period_end,
        days_in_period=int(period.group("days")),
        beginning_balance=float(beginning),
        ending_balance=float(ending),
        currency="USD",
        # Mercury prints withdrawals as a negative figure; the schema wants the
        # magnitude.
        stated_total_credits=float(credits),
        stated_total_debits=float(abs(debits)),
        transactions=transactions,
    )


def printed_total_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The two figures Mercury prints twice, checked against each other.

    The grid closes with a ``Total`` row that repeats the statement balance
    under the Balance column, and the period header states its own length in
    days. Neither is used to BUILD the statement, so each is an independent
    printing of a figure the summary already gave — and a document whose two
    printings disagree contradicts itself, which is a finding for a human
    rather than something to resolve by preferring one of them.
    """
    notes: list[str] = []
    lines = compact_lines(markdown)

    for line in lines:
        total = _GRID_TOTAL_RE.match(line)
        if total and stmt.ending_balance is not None:
            printed = parse_signed_decimal(total.group("total"))
            if printed != Decimal(str(round(stmt.ending_balance, 2))):
                notes.append(
                    "the transaction grid's printed Total "
                    f"({float(printed):,.2f}) does not equal the statement "
                    f"balance ({stmt.ending_balance:,.2f})"
                )
            break

    period = unique_line(lines, _PERIOD_RE)
    if period is not None and stmt.period_start and stmt.period_end:
        from datetime import date

        start = date.fromisoformat(stmt.period_start)
        end = date.fromisoformat(stmt.period_end)
        spanned = (end - start).days + 1
        if int(period.group("days")) != spanned:
            notes.append(
                f"the header states a {period.group('days')}-day period but the "
                f"printed dates span {spanned} day(s)"
            )
    return notes
