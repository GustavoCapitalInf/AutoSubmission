"""First Citizens Bank business checking statements.

What makes this layout tractable is that the bank prints a complete control
record in `Your Account(s) At A Glance`: the beginning balance, the ending
balance, a count AND a total for each of the four posting sections, and the
monthly service charge. Those figures satisfy their own arithmetic —

    beginning + deposits + other credits - checks - other debits
        - monthly service charge = ending

— so the block is checked against itself before any figure in it is believed,
and a block that does not close is not read at all.

Both balances are READ from that block. Nothing here derives an opening from
an ending or lifts a closing out of a grid position; the parser this replaced
computed `beginning = ending - credits + debits` from its own transaction
sums, so its reconciliation could not fail no matter what it had parsed.

Be precise about what that buys, because it is easy to overclaim. It does NOT
make `analysis.reconcile` an independent test of the detail for this bank.
`_matches` already requires each section's parsed total to equal the total the
bank printed for it, and the printed summary closes on its own arithmetic, so
on any statement this parser accepts, `beginning + sum(postings) == ending`
follows algebraically: reconciliation restates the gate one layer down rather
than testing it. The one path that can still fail it is a billed service
charge whose itemisation could not be located, where
`_service_charge_posting` returns nothing and the row is omitted rather than
dated by guesswork.

What the change actually buys is the GATE. The parse is checked against the
counts and totals THIS document prints, where before it was checked against
four constants memorized off one statement — so a misread section is rejected
instead of being silently reconciled, and the check travels to every statement
in the family instead of exactly one. This module therefore carries no memory
of any particular statement's figures, dates, or counterparties. Every section
is optional: a month with no deposits prints no deposits section, and the
printed count for that section is then zero.

Intake note (`ocr/native_text.py`): the GENERIC native-text extractor flattens
this bank's description column — every description in a section arrives
concatenated onto one line, while the dates and amounts arrive as separate
positional runs on the lines beneath it. Everything below still reads that
flattened form and still works on it, because it is what a document extracted
before `+first-citizens-layout` existed looks like, and because it is the
honest floor: from a flattened column, dates and amounts are recoverable per
posting and free-text descriptions are not, except where the section prints a
structured row (checks) or holds a single posting. The previous parser split
that column on a list of ~25 remembered merchant names, which is what tied it
to one document; nothing here guesses a boundary.

`parse_native_first_citizens` now recovers the column properly, from the
printed table's own geometry, and reports one row per posting at the end of
the document. `_described` OVERLAYS those rows onto the postings this module
already read, and it is a cross-check before it is a convenience: a section
takes the printed descriptions only when the extractor's rows reproduce that
section's parsed dates and amounts exactly, in order, one for one. Two
independent readings of the same table therefore have to agree before any
description is published, and where they do not the section keeps its label.
No amount, date, count or balance depends on the overlay — it is text only,
and a document extracted without the rows parses exactly as it did before.

The At-A-Glance box arrives in two shapes and the difference is the
extractor's, not the bank's: most documents emit the box's column heading
(`Statement Period Days / Average Ledger Balance`) before its cells, and some
emit part of the cell run ABOVE it. `_summary_block` therefore bounds the block
on both sides, by the grid's own cell shapes. The four `3df19105_*1301`
documents DO print a control row, and one of them is not dormant.
"""
from __future__ import annotations

import re
from datetime import date

from .holder_name import NO_READING, HolderReading, read_address_line
from .money import parse_grouped_float
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace

_MONEY = r"\d[\d,]*\.\d{2}"
_MONEY_RE = re.compile(_MONEY)
_MMDD_RE = re.compile(r"\d{2}-\d{2}")

#: The summary's own header. The value row sits within a few lines of it, but
#: the extractor does not emit those lines in a stable order, so the block is
#: read by token shape rather than by offset (see `_summary`).
_SUMMARY_ANCHOR_RE = re.compile(
    r"^Statement Period Days\s+Average Ledger Balance\s*$",
    re.IGNORECASE | re.MULTILINE,
)

#: One printed posting section, or the page furniture that closes the summary.
#: Used both to bound the summary block and to bound each section.
#: The debits section is renamed when the bank bills a monthly service charge
#: in the same period, so the header is a pattern rather than a name.
_OTHER_DEBITS_PATTERN = (
    r"Other Debits (?:From Your Account|And Monthly Service Charge)"
)

_BOUNDARY_RE = re.compile(
    r"^(?:Deposits To Your Account"
    r"|Other Credits To Your Account"
    r"|Checks Paid From Your Account"
    rf"|{_OTHER_DEBITS_PATTERN}"
    r"|Monthly Service Charge Description"
    r"|Commercial Advantage Service Charge"
    r"|Daily Balance Summary"
    r"|Total\s*$"
    r"|\*\s*Prior Check"
    r"|Direct Customer Inquiry"
    r"|An updated"
    r"|FOLLOW THESE EASY STEPS"
    r"|Statement Period:"
    r"|Page \d+ of \d+"
    r"|--- Page)",
    re.IGNORECASE,
)

#: The summary control row: a beginning-balance sign, then a count and a signed
#: total for each of the four sections, then the monthly service charge. The
#: deposits total and the beginning/ending amounts are NOT on this row — the
#: extractor emits them on their own lines — so only their signs appear here.
#: A section whose count is zero prints its total without a sign, and the
#: deposits sign is omitted entirely when no deposit posted.
_CONTROL_ROW_RE = re.compile(
    rf"^([+-])\s+(\d+)\s+(?:([+-])\s+)?"
    rf"(\d+)\s+({_MONEY})([+-])?\s+"
    rf"(\d+)\s+({_MONEY})([+-])?\s+"
    rf"(\d+)\s+({_MONEY})([+-])?\s+"
    rf"({_MONEY})([+-])?$"
)

_BARE_MONEY_RE = re.compile(rf"^({_MONEY})$")
_SIGNED_MONEY_RE = re.compile(rf"^({_MONEY})([+-])$")
_DAY_COUNT_RE = re.compile(r"^(\d{1,2})$")

#: Section headers, and the description used for a posting the intake flattened
#: beyond per-row attribution.
_DEPOSITS = "Deposits To Your Account"
_OTHER_CREDITS = "Other Credits To Your Account"
_CHECKS = "Checks Paid From Your Account"
_OTHER_DEBITS = _OTHER_DEBITS_PATTERN

_SECTION_LABELS = {
    _DEPOSITS: "Deposit",
    _OTHER_CREDITS: "Other Credit",
    _OTHER_DEBITS: "Other Debit",
}

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _money(value: str) -> float:
    return parse_grouped_float(value)


def _signed(amount: str, sign: str | None) -> float:
    return -_money(amount) if sign == "-" else _money(amount)


def _lines(block: str) -> list[str]:
    return [line.strip() for line in block.splitlines() if line.strip()]


def _parse_period(markdown: str) -> tuple[date, date] | None:
    match = re.search(
        r"Statement Period:\s*([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})\s+Thru\s+"
        r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not match:
        return None
    start_month, start_day, start_year, end_month, end_day, end_year = match.groups()
    if start_month.lower() not in _MONTHS or end_month.lower() not in _MONTHS:
        return None
    try:
        start = date(int(start_year), _MONTHS[start_month.lower()], int(start_day))
        end = date(int(end_year), _MONTHS[end_month.lower()], int(end_day))
    except ValueError:
        return None
    return (start, end) if start <= end else None


def _account(markdown: str) -> str | None:
    match = re.search(r"Account Number\s*:\s*(\d+)", markdown, re.IGNORECASE)
    return match.group(1) if match else None


def _account_name(markdown: str) -> str | None:
    """The printed product line, which sits between the two account-number lines.

    The bank prints the account number twice around it — once at the end of the
    `Statement Period:` line and once on its own line with the enclosure count —
    and the product name is what stands between them.

    The first of those two lines does NOT begin with `Account Number`; it begins
    with `Statement Period:`, and the number is printed at its end. Anchoring
    the pattern at the start of that line therefore matched **nothing in this
    family**: measured over all 39 documents this parser claims, the regex
    matched 0 of them and every one published the fallback literal
    `"Business Banking"` — false on 13 of the 39, which print
    `Business Banking II`, `Professional Business Checking` or
    `Analysis Business Checking`. The literal is gone: an unread product is not
    a product this reader may name, so it returns None and the field publishes
    as the honest unknown (the same rule §DECLB applied to `us_bank`'s and
    `capital_one`'s memorized product names).
    """
    match = re.search(
        r"^.*Account Number\s*:.*$\n^(.+)$\n^.*Account Number\s*:",
        markdown,
        re.IGNORECASE | re.MULTILINE,
    )
    return compact_whitespace(match.group(1)) if match else None


#: Audit B9 (I13, I38): the holder's line, printed directly above the summary heading: the holder's name, an account
#: designation the bank prints after it (a premium trust, an operating, a wire or a producer-payable account) and the
#: mailing address, run together, sometimes with a balance after the ZIP. Read only when it closes on a state and ZIP.
_HOLDER_LINE = re.compile(r"^([^\n]*)\n(?=Your Account\(s\) At A Glance)", re.MULTILINE)
_STATE_ZIP = re.compile(r"\b[A-Z]{2} \d{5}(?:-\d{4})?\b")


def _holder_reading(markdown: str) -> HolderReading:
    """Audit B9 (I13, I38): the account holder's name from the line above `Your Account(s) At A Glance`, without the
    account designation and the address (analysis.holder_name.read_address_line); NO_READING when that line is no
    mailing address. `_account_name` keeps publishing the product line. Owner ruling 2026-10-02 (Q10), audit round 2,
    R2-OW10: with the designation the line prints after the name (a premium trust, an operating, a wire or a
    producer-payable account) as the account's title."""
    match = _HOLDER_LINE.search(markdown)
    if match is None or not _STATE_ZIP.search(match.group(1)):
        return NO_READING
    return read_address_line(match.group(1))


def _resolve(month: int, day: int, start: date, end: date) -> date | None:
    """The one in-period date with this month and day, or None if not unique.

    A statement period can straddle a year boundary, so the year is chosen by
    the period rather than assumed. A month/day that lands outside the period,
    or that is not a real calendar date, yields nothing and the caller fails
    closed rather than inventing a posting date.
    """
    matches = []
    for year in {start.year, end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            matches.append(candidate)
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else None


class _Summary:
    """The printed At-A-Glance control record, once it has closed on itself."""

    def __init__(
        self,
        *,
        beginning: float,
        ending: float,
        days: int | None,
        average: float | None,
        deposits: tuple[int, float],
        other_credits: tuple[int, float],
        checks: tuple[int, float],
        other_debits: tuple[int, float],
        service_charge: float,
    ) -> None:
        self.beginning = beginning
        self.ending = ending
        self.days = days
        self.average = average
        self.deposits = deposits
        self.other_credits = other_credits
        self.checks = checks
        self.other_debits = other_debits
        self.service_charge = service_charge

    @property
    def total_credits(self) -> float:
        return round(self.deposits[1] + self.other_credits[1], 2)

    @property
    def total_debits(self) -> float:
        return round(self.checks[1] + self.other_debits[1], 2)

    def closes(self) -> bool:
        walked = (
            self.beginning
            + self.total_credits
            - self.total_debits
            - self.service_charge
        )
        return abs(round(walked - self.ending, 2)) < 0.005


#: The grid's four cell shapes, in the order `_summary` reads them. Kept as one
#: reading because three callers ask the same question of the same line — is
#: this a cell at all (`_is_summary_cell`), which side of the heading did an
#: OPTIONAL cell arrive from (`_summary`), and what does it hold (`_summary`
#: again) — and two readings of one line are two chances to disagree.
_CELL_SHAPES = (
    ("control", _CONTROL_ROW_RE),
    ("bare", _BARE_MONEY_RE),
    ("signed", _SIGNED_MONEY_RE),
    ("days", _DAY_COUNT_RE),
)

#: The two cells the record can do without: `days` and the average ledger
#: balance. Both are OPTIONAL, so neither is protected by a count gate the way
#: the control row and the three unsigned cells are, and a first one arriving
#: from the wrong side of the heading would publish unopposed.
_OPTIONAL_CELLS = frozenset({"signed", "days"})


def _cell_kind(line: str) -> str | None:
    """Which of the grid's four cell shapes this physical line is, or None."""
    for kind, pattern in _CELL_SHAPES:
        if pattern.match(line):
            return kind
    return None


def _is_summary_cell(line: str) -> bool:
    """Is this physical line one of the At-A-Glance grid's own cells?

    Anything else on a line is furniture, a heading or another block, and
    `_summary_block` uses exactly that to know where the grid ends.
    """
    return _cell_kind(line) is not None


def _summary_block(markdown: str, anchor: re.Match[str]) -> tuple[list[str], list[str]]:
    """The grid's cell lines either side of its printed column heading.

    `Statement Period Days / Average Ledger Balance` is a COLUMN HEADING of the
    At-A-Glance grid, not its first line, and the extractor does not always
    emit it first: on the `3df19105_*1301` statements the control row, the day
    count and the beginning balance are all emitted ABOVE it. Reading the grid
    only forwards therefore loses cells the bank printed, and the shape test in
    `_summary` then refuses a control record that is complete — which is what
    it did on four documents, one of which posts a wire in and a wire out.

    Backwards the block is bounded by the same four cell shapes the forward
    scan recognises: the first line above the heading that is not one of them
    ends it. Nothing the forward scan would reject can therefore enter through
    the back, and a document whose heading is preceded by its own furniture —
    which is every printing measured before this one — contributes no lines at
    all and reads exactly as it did. Forwards the block is bounded by the
    printed structure, unchanged.

    The two runs are returned SEPARATELY because provenance is load bearing:
    `_summary` refuses an optional cell that arrives from above the heading
    without the control row arriving with it. Each run is in document order —
    `before.reverse()` is what puts the backward run back into it, and the
    three unsigned cells are read positionally.
    """
    before: list[str] = []
    for line in reversed(_lines(markdown[: anchor.start()])):
        if not _is_summary_cell(line):
            break
        before.append(line)
    before.reverse()
    after: list[str] = []
    for line in _lines(markdown[anchor.end():]):
        if _BOUNDARY_RE.match(line):
            break
        after.append(line)
    return before, after


def _summary(markdown: str) -> _Summary | None:
    """Read the At-A-Glance control record, or nothing.

    The extractor emits this block's cells in an order that varies between
    documents — `days` may precede or follow the beginning balance, the ending
    amount may precede or follow its own sign, and the whole run may precede or
    follow the block's own column heading (`_summary_block`) — so cells are
    recognised by token shape, not position. Within a shape the printed order
    is stable: the three unsigned money cells are the beginning balance, the
    deposits total and the ending balance, in that order.

    A block that does not expose exactly one control row and exactly three
    unsigned money cells returns None rather than guess, and what it reads is
    then believed only if the record closes on its own arithmetic.

    Those two counts protect the control row and the three unsigned cells. They
    do NOT protect `days` and the average ledger balance, which are OPTIONAL:
    the record is read without them, so a FIRST one has no second to contradict
    it and would publish unopposed. That matters because `days_in_period` is
    not evidence-only — `metrics.py` falls back to it where a validated daily
    ledger is absent. The provenance rule below is what closes it: an optional
    cell may arrive from above the heading only in the company of the control
    row, which is the printing that says the grid straddles the heading at all.
    Measured over the 39 documents this parser claims, that is exactly what the
    four straddling printings do and no document is refused by it.
    """
    anchor = _SUMMARY_ANCHOR_RE.search(markdown)
    if anchor is None:
        return None
    before, after = _summary_block(markdown, anchor)
    kinds = [_cell_kind(line) for line in before]
    if _OPTIONAL_CELLS.intersection(kinds) and "control" not in kinds:
        return None
    block = before + after

    control = None
    bare: list[float] = []
    signed: list[float] = []
    days: list[int] = []
    for line in block:
        row = _CONTROL_ROW_RE.match(line)
        if row is not None:
            if control is not None:
                return None
            control = row
            continue
        money = _BARE_MONEY_RE.match(line)
        if money is not None:
            bare.append(_money(money.group(1)))
            continue
        marked = _SIGNED_MONEY_RE.match(line)
        if marked is not None:
            signed.append(_signed(marked.group(1), marked.group(2)))
            continue
        count = _DAY_COUNT_RE.match(line)
        if count is not None:
            days.append(int(count.group(1)))

    if control is None or len(bare) != 3 or len(days) > 1 or len(signed) > 1:
        return None

    (
        beginning_sign,
        deposit_count,
        deposit_sign,
        credit_count,
        credit_total,
        credit_sign,
        check_count,
        check_total,
        check_sign,
        debit_count,
        debit_total,
        debit_sign,
        service_total,
        service_sign,
    ) = control.groups()

    beginning_amount, deposit_total, ending_amount = bare
    summary = _Summary(
        beginning=-beginning_amount if beginning_sign == "-" else beginning_amount,
        ending=ending_amount,
        days=days[0] if days else None,
        average=signed[0] if signed else None,
        deposits=(
            int(deposit_count),
            -deposit_total if deposit_sign == "-" else deposit_total,
        ),
        other_credits=(int(credit_count), _signed(credit_total, credit_sign)),
        checks=(int(check_count), abs(_signed(check_total, check_sign))),
        other_debits=(int(debit_count), abs(_signed(debit_total, debit_sign))),
        service_charge=abs(_signed(service_total, service_sign)),
    )
    return summary if summary.closes() else None


def _section_blocks(markdown: str, header: str) -> list[str]:
    """Every printed run of one section, in document order.

    `header` is a regular expression, because one section's printed name
    varies with what the bank billed that month. A section that spills across
    a page prints its header again, so a section is a list of blocks rather
    than a single span. Each block ends at the next structural boundary —
    another section, the printed `Total`, or page furniture — never at a
    remembered amount.
    """
    blocks: list[str] = []
    for part in re.split(header, markdown, flags=re.IGNORECASE)[1:]:
        collected: list[str] = []
        for line in _lines(part):
            if _BOUNDARY_RE.match(line):
                break
            collected.append(line)
        if collected:
            blocks.append("\n".join(collected))
    return blocks


def _positional_runs(block: str) -> tuple[list[str], list[float]]:
    """Dates and amounts from a section whose columns arrive as parallel runs."""
    dates: list[str] = []
    amounts: list[float] = []
    for line in _lines(block):
        if re.fullmatch(r"(?:\d{2}-\d{2}\s*)+", line):
            dates.extend(_MMDD_RE.findall(line))
        elif re.fullmatch(rf"(?:{_MONEY}\s*)+", line):
            amounts.extend(_money(raw) for raw in _MONEY_RE.findall(line))
    return dates, amounts


def _flattened_postings(
    markdown: str,
    header: str,
    *,
    start: date,
    end: date,
    credit: bool,
) -> list[Transaction] | None:
    """Postings from a section whose description column the intake flattened.

    Dates and amounts pair positionally and are trusted; descriptions are not
    recoverable per row unless the section printed exactly one posting, in
    which case the whole run belongs to it.
    """
    label = _SECTION_LABELS[header]
    postings: list[Transaction] = []
    for block in _section_blocks(markdown, header):
        lines = _lines(block)
        if not lines:
            continue
        run = re.sub(
            r"^Date\s+Description\s+Amount\s*", "", lines[0], flags=re.IGNORECASE
        ).strip()
        dates, amounts = _positional_runs("\n".join(lines[1:]))
        if len(dates) != len(amounts):
            return None
        for index, (mmdd, amount) in enumerate(zip(dates, amounts)):
            when = _resolve(int(mmdd[:2]), int(mmdd[3:]), start, end)
            if when is None:
                return None
            described = len(dates) == 1 and bool(run)
            description = compact_whitespace(run) if described else label
            postings.append(
                Transaction(
                    date=when.isoformat(),
                    description=description,
                    amount=amount if credit else -amount,
                    direction="credit" if credit else "debit",
                    # Audit B10 (I60): the section label stands in for a
                    # description the bank printed and this reader did not
                    # read; `_described` lifts the mark where the overlay
                    # reads the column. (The deposits grid prints no
                    # description column, so its label marks nothing.)
                    payer_text_unread=credit and not described,
                )
            )
    return postings


def _parse_deposits(markdown: str, *, start: date, end: date) -> list[Transaction] | None:
    """The deposits grid: month/amount cells above their own day cells."""
    postings: list[Transaction] = []
    for block in _section_blocks(markdown, _DEPOSITS):
        lines = _lines(block)
        for index, line in enumerate(lines[:-1]):
            cells = re.findall(rf"\b(\d{{2}})\s+({_MONEY})", line)
            if not cells:
                continue
            days = re.findall(r"-(\d{2})", lines[index + 1])
            if len(days) != len(cells):
                return None
            for (month, amount), day in zip(cells, days):
                when = _resolve(int(month), int(day), start, end)
                if when is None:
                    return None
                postings.append(
                    Transaction(
                        date=when.isoformat(),
                        description=_SECTION_LABELS[_DEPOSITS],
                        amount=_money(amount),
                        direction="credit",
                    )
                )
    return postings


#: One cheque in the checks grid. The number is optional: the bank prints a
#: cheque it could not read the serial of with an empty number column, and its
#: own check-image list then shows a bare `Chk#`. Requiring the number dropped
#: such a row and left the section one cheque short of the printed count.
_CHECK_ROW_RE = re.compile(rf"(?:(\d{{2,6}})\s+)?(\d{{2}}-\d{{2}})\s+({_MONEY})")


def _parse_checks(markdown: str, *, start: date, end: date) -> list[Transaction] | None:
    """The checks grid, which prints a structured row per cheque."""
    postings: list[Transaction] = []
    for block in _section_blocks(markdown, _CHECKS):
        for number, mmdd, amount in _CHECK_ROW_RE.findall(block):
            when = _resolve(int(mmdd[:2]), int(mmdd[3:]), start, end)
            if when is None:
                return None
            postings.append(
                Transaction(
                    date=when.isoformat(),
                    description=f"Check #{number}" if number else "Check",
                    amount=-_money(amount),
                    direction="debit",
                )
            )
    return postings


#: Where a billed service charge is itemised. The bank prints it in one of two
#: places, and in BOTH it carries its own posting date and its own amount —
#: neither is inferred here. It sits outside the four section totals, which is
#: why the summary subtracts it separately.
_SERVICE_CHARGE_BLOCKS = (
    r"Monthly Service Charge Description",
    r"[A-Z][a-z]+ Service Charge\s*$",
)


def _service_charge_posting(
    markdown: str, charge: float, *, start: date, end: date
) -> Transaction | None:
    """The billed monthly service charge, as the posting the bank itemised.

    Returns nothing when the charge is not billed, or when the itemisation
    cannot be found and confirmed against the summary figure. A charge that
    cannot be located is left out rather than dated by guesswork: the
    statement still parses, and its detail simply does not close, which is the
    honest outcome and the one `analysis.reconcile` is there to report.
    """
    if charge <= 0:
        return None
    for pattern in _SERVICE_CHARGE_BLOCKS:
        for match in re.finditer(pattern, markdown, re.IGNORECASE | re.MULTILINE):
            window = markdown[match.end():]
            lines: list[str] = []
            for line in _lines(window):
                if _BOUNDARY_RE.match(line) and not lines:
                    continue
                if _BOUNDARY_RE.match(line):
                    break
                lines.append(line)
            body = "\n".join(lines)
            dates = _MMDD_RE.findall(body)
            amounts = [_money(raw) for raw in _MONEY_RE.findall(body)]
            if not dates or not any(abs(a - charge) < 0.005 for a in amounts):
                continue
            when = _resolve(int(dates[0][:2]), int(dates[0][3:]), start, end)
            if when is None:
                continue
            return Transaction(
                date=when.isoformat(),
                description="Monthly Service Charge",
                amount=-charge,
                direction="debit",
            )
    return None


#: The layout extractor's report, delimited so a document that never went
#: through it is simply a document with no rows (`ocr/native_text.py`).
#: The leading `\n?` is not cosmetic: it makes the excision exact, so the
#: document a reader below sees is the document it would have seen had the
#: intake never reported anything.
_ROWS_RE = re.compile(
    r"\n?^FC_NATIVE_TRANSACTIONS$(?P<body>.*?)^FC_NATIVE_TRANSACTIONS_END$",
    re.MULTILINE | re.DOTALL,
)


def _report(markdown: str) -> tuple[list[tuple[str, str, str, str]], str]:
    """The intake's rows, and the document with the report REMOVED.

    Removed, not merely ignored. Every row repeats the section heading it was
    printed under, so a report left in place is a second printing of
    `Other Debits From Your Account` inside the text that `_section_blocks`
    splits on and `_service_charge_posting` scans. Cutting it out at this one
    seam is a property of the module; asking each reader to skip it would be a
    promise renewed at every future edit.

    A malformed block yields no rows rather than a partial reading — the
    overlay is keyed on reproducing a whole section, so half a report fails
    that check anyway, and failing here is cheaper and louder. The report is
    still cut out: it is not statement text whether or not it parses.

    Rows: `(section, MM-DD, amount, description)`.
    """
    match = _ROWS_RE.search(markdown)
    if match is None:
        return [], markdown
    printed = markdown[: match.start()] + markdown[match.end():]
    rows: list[tuple[str, str, str, str]] = []
    for line in _lines(match.group("body")):
        fields = line.split("|", 4)
        if len(fields) != 5 or fields[0] != "FC_TX":
            return [], printed
        _prefix, section, mmdd, amount, description = fields
        if _MMDD_RE.fullmatch(mmdd) is None or _MONEY_RE.fullmatch(amount) is None:
            return [], printed
        rows.append((section, mmdd, amount, description))
    return rows, printed


def _described(
    postings: list[Transaction],
    rows: list[tuple[str, str, str, str]],
    header: str,
    *,
    start: date,
    end: date,
) -> list[Transaction]:
    """The same postings, carrying the descriptions the bank printed for them.

    Fail-closed by section. The extractor read the table by geometry and this
    module read it positionally out of the flattened column; the printed text is
    published only where those two readings agree on every date and every amount
    of the section, in printed order. Any disagreement — a row count that
    differs, a date that resolves elsewhere, a cent out — returns the postings
    untouched, so the section keeps the honest label it has today. A row the
    bank printed with an empty description column leaves that one posting
    labelled; nothing is synthesised for it.
    """
    section = [row for row in rows if re.fullmatch(header, row[0], re.IGNORECASE)]
    if len(section) != len(postings):
        return postings
    described: list[Transaction] = []
    for posting, (_name, mmdd, amount, description) in zip(postings, section):
        when = _resolve(int(mmdd[:2]), int(mmdd[3:]), start, end)
        if when is None or when.isoformat() != posting.date:
            return postings
        if abs(_money(amount) - abs(posting.amount)) >= 0.005:
            return postings
        text = compact_whitespace(description)
        # A COPY with one field replaced, not a rebuild: `Transaction` carries
        # `running_balance` as well, and a rebuild naming four fields would
        # silently drop a fifth the day this parser starts populating one.
        # Audit B10 (I60): the column was read, so the row is no longer marked
        # as read only by its label (an empty column printed no payer).
        described.append(
            posting.model_copy(update={"description": text or posting.description, "payer_text_unread": False})
        )
    return described


def _matches(printed: tuple[int, float], postings: list[Transaction]) -> bool:
    """A parsed section agrees with the count AND the total the bank printed."""
    count, total = printed
    if len(postings) != count:
        return False
    parsed = round(sum(abs(posting.amount) for posting in postings), 2)
    return abs(parsed - abs(total)) < 0.005


DETECTION_MARKERS = (
    # The processing centre that prints every statement in this family, or the
    # bank's own name. The name alone appears on any statement that merely pays
    # First Citizens (R4-3), which is what the second marker excludes.
    required(
        "bank_name",
        lambda t: "First Citizens" in t or "Central Bank Operations" in t,
    ),
    # The printed summary this parser reads. Structural, and present on every
    # statement in the family. The marker it replaces — the firstcitizens.com
    # URL — occurs only inside a Treasury-agreement notice the bank inserted
    # for part of 2026, so it was absent from 17 of the 41 genuine First
    # Citizens statements in the archive and present on documents that are not
    # statements at all.
    required(
        "summary_block",
        lambda t: "Your Account(s) At A Glance" in t
        or "Statement Period Days Average Ledger Balance" in t,
    ),
)

detect = make_detector(DETECTION_MARKERS)


def parse_first_citizens_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None

    # Detection has run on exactly the bytes dispatch scored. From here down
    # `markdown` is the DOCUMENT: the intake's row report is evidence about the
    # statement, not part of it, and nothing below can read it as printing.
    reported, markdown = _report(markdown)

    period = _parse_period(markdown)
    account = _account(markdown)
    summary = _summary(markdown)
    if period is None or account is None or summary is None:
        return None
    start, end = period

    deposits = _parse_deposits(markdown, start=start, end=end)
    other_credits = _flattened_postings(
        markdown, _OTHER_CREDITS, start=start, end=end, credit=True
    )
    checks = _parse_checks(markdown, start=start, end=end)
    other_debits = _flattened_postings(
        markdown, _OTHER_DEBITS, start=start, end=end, credit=False
    )
    if deposits is None or other_credits is None or checks is None or other_debits is None:
        return None

    # Every section is checked against the count and the total the bank printed
    # for it. This is what the previous parser did with four remembered
    # constants; the document supplies them.
    if not (
        _matches(summary.deposits, deposits)
        and _matches(summary.other_credits, other_credits)
        and _matches(summary.checks, checks)
        and _matches(summary.other_debits, other_debits)
    ):
        return None

    # Only now, with every section closed against the record the bank printed,
    # are the printed descriptions laid over the two sections that have one.
    # This changes text and nothing else: same dates, same amounts, same counts,
    # same balances, and the gate above has already run either way.
    if reported:
        other_credits = _described(
            other_credits, reported, _OTHER_CREDITS, start=start, end=end
        )
        other_debits = _described(
            other_debits, reported, _OTHER_DEBITS, start=start, end=end
        )

    # The service charge is billed outside the four section totals, so it is
    # recovered from its own itemisation rather than counted against them.
    charge = _service_charge_posting(
        markdown, summary.service_charge, start=start, end=end
    )
    billed = [charge] if charge is not None else []

    holder = _holder_reading(markdown)
    return Statement(
        bank="First Citizens Bank",
        account_name=_account_name(markdown),
        holder_name=holder.name,
        account_title=holder.title,
        account_number=account,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=summary.days if summary.days is not None else (end - start).days + 1,
        beginning_balance=summary.beginning,
        ending_balance=summary.ending,
        stated_total_credits=summary.total_credits,
        stated_total_debits=summary.total_debits,
        stated_credit_count=summary.deposits[0] + summary.other_credits[0],
        stated_debit_count=summary.checks[0] + summary.other_debits[0],
        bank_reported_average_balance=summary.average,
        bank_reported_average_label=(
            "Average Ledger Balance" if summary.average is not None else None
        ),
        stated_service_charge=summary.service_charge,
        transactions=deposits + other_credits + checks + other_debits + billed,
    )
