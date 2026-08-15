"""A core-processor statement template whose summary partitions the ledger.

The template prints a six-row summary grid, two-column transaction grids under
its own section names, and a `Balance By Date` grid that walks the period day
by day.  Read together those are seven independent constraints on one ledger,
and this reader publishes nothing unless every one of them holds::

      PREVIOUS BALANCE      b0
    + N CREDITS       C          rows the bank counted as deposits
    - M DEBITS        D          rows the bank counted as withdrawals
    - SERVICE CHARGES S          rows the bank did NOT count
    + INTEREST PAID   I          rows the bank did NOT count
      ENDING BALANCE  b1         and b0 + C - D - S + I == b1

**The trap is the partition.**  `S` and `I` are not summaries of `D` and `C` —
they are the money the printed COUNTS deliberately exclude, while the printed
TOTALS exclude it too and the balance identity puts it back.  A reader that
folds a fee row into the debit total produces a statement that still looks
plausible: the balance chain closes, because the money is right either way,
and only the COUNTS disagree.  Measured over the family that motivated this
module, folding produced a count disagreement on every document.  So the
counts are load-bearing here, not decoration, and this reader refuses a
document whose printed counts it cannot reproduce exactly.

What the code does NOT contain is a list of fee wordings.  The rows the bank
excluded from its counts are called `SERVICE CHARGE`, `CASH ITEM CHARGES`,
`CASHITEMCHARGES`, `ANALYSIS SERVICE CHG` and `ITEM FEE` in one family alone,
while `OVERDRAFT CHARGE`, `NSF CHARGE`, `STOP PAY CHARGE` and `WIRE TFR FEE`
are ordinary counted debits on the very same statements — a vocabulary cannot
separate those, and a vocabulary that tried would be a memorised list of one
archive's wordings.  The partition is read from the ARITHMETIC the document
prints instead: the bank says how many rows it counted, so the rows it did not
count are the remainder, and their number and total are both fixed by the
printed figures (:func:`_partition_holds`).

Neither is there a list of the summary's own labels.  A summary term that
prints a COUNT enumerates rows; a term that prints no count is a lump the
counts exclude; and the `+` or `-` the bank prints in front of a term is its
direction.  Reading the grid that way (:func:`_summary`) is what makes the
partition the document's statement about itself rather than this module's
assumption about it.

The issuer is deliberately NOT published.  See :func:`_parse`.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .money import MINUS_CLASS, STRICT_UNSIGNED, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction

# ---------------------------------------------------------------------------
# Printed money
# ---------------------------------------------------------------------------

#: An ordinary printed amount.  Bounded on the left so a reference number
#: cannot be read as one, and delegated to `analysis.money` for the value.
_CENTS = r"\d[\d,]{0,15}\.\d{2}"

#: The platform prints a figure below one dollar with no integer part - a zero
#: is `.00`.  On a scanned print stream the leading dot is routinely resolved
#: as a hyphen (`-00`), and both spellings occur on the SAME document, one per
#: line.  Reading them as the sub-dollar amount they are is safe here in the
#: strong sense rather than the tolerant one: every figure this reader takes
#: from the summary is checked against the balance identity and against the
#: two grids, so a mis-read zero cannot reach a published payload - it fails
#: the document closed instead.
#:
#: A LEADING minus is therefore never a sign on this template.  A negative
#: figure prints its minus on the RIGHT (`248.74-`, as the average-balance
#: statistic does), so `_figure` admits no leading sign at all and an
#: overdrawn summary balance is refused rather than guessed.  No document in
#: the measured population prints one on a figure this reader publishes.
_SUB_DOLLAR = r"[.\-]\d{2}"

_FIGURE = rf"(?:{_CENTS}|{_SUB_DOLLAR})"
_SUB_DOLLAR_RE = re.compile(rf"^{_SUB_DOLLAR}$")


def _figure(token: str) -> float | None:
    """The value of one printed figure, or None when it is not money."""
    if _SUB_DOLLAR_RE.match(token):
        return parse_amount("0." + token[1:], STRICT_UNSIGNED)
    return parse_amount(token, STRICT_UNSIGNED)


# ---------------------------------------------------------------------------
# The printed summary grid
# ---------------------------------------------------------------------------

#: The grid's heading, which also prints the account's product name.  The
#: heading is truncated by the page edge on some scans (`... Account Summa`),
#: so the word `Summary` is matched by its stem, and the product is optional
#: because it is the account's name rather than the grid's.
_SUMMARY_HEAD_RE = re.compile(
    r"(?m)^\s*(?:([A-Za-z][A-Za-z ]{0,40}?)\s+)?Account\s+Summ\w*\s*$"
)

#: The grid's two bookends, each on its own printed line.
_PREVIOUS_RE = re.compile(rf"(?mi)^\s*PREVIOUS BALANCE\s+({_FIGURE})(?!\d)")
_ENDING_RE = re.compile(rf"(?mi)^\s*ENDING BALANCE\s+({_FIGURE})(?!\d)")

#: One term of the grid between those bookends.
#:
#: Anchored at the start of a printed line, which is what keeps the grid's
#: RIGHT-HAND COLUMN out of it.  This template interleaves undated statistics
#: (`AVERAGE BALANCE`, `YTD INTEREST PAID`) into the same rows, one label per
#: line with its figure landing on the line below - the two-column arrangement
#: `analysis/community_section.py` documents.  A statistic prints no operator,
#: so requiring the line to OPEN with `+` or `-` excludes every one of them
#: structurally, with no list of their names anywhere in this file.
#:
#: The figure taken is the FIRST one after the label, because the second is
#: the right-hand column's.
_TERM_RE = re.compile(
    rf"(?mi)^\s*(?P<op>\+|{MINUS_CLASS})\s*"
    rf"(?:(?P<count>\d{{1,6}})\s+)?"
    rf"(?P<label>[A-Za-z][A-Za-z ]{{2,30}}?)\s+(?P<figure>{_FIGURE})(?!\d)"
)


class _Summary:
    """The printed grid, read as the bank's own statement about its ledger."""

    __slots__ = ("product", "beginning", "ending", "credit_count", "credits",
                 "debit_count", "debits", "uncounted_credit", "uncounted_debit")

    def __init__(self, product, beginning, ending, credit_count, credits,
                 debit_count, debits, uncounted_credit, uncounted_debit):
        self.product = product
        self.beginning = beginning
        self.ending = ending
        self.credit_count = credit_count
        self.credits = credits
        self.debit_count = debit_count
        self.debits = debits
        #: The money the printed counts EXCLUDE, per direction: interest
        #: credited, and service charges levied.
        self.uncounted_credit = uncounted_credit
        self.uncounted_debit = uncounted_debit

    @property
    def identity_holds(self) -> bool:
        """`b0 + C - D - S + I == b1`, with the signs the bank printed."""
        walked = (self.beginning + self.credits + self.uncounted_credit
                  - self.debits - self.uncounted_debit)
        return abs(round(walked - self.ending, 2)) <= _TOLERANCE


#: Money comparisons are exact to the cent everywhere in this module.  The
#: template prints every figure it is checked against, so a tolerance wide
#: enough to absorb a rounding difference would also absorb a mis-read digit.
_TOLERANCE = 0.011


def _summary(text: str) -> _Summary | None:
    """The printed summary grid of `text`, or None when it is not fully read.

    Fail-closed by construction: a grid missing a bookend, missing either
    counted direction, or printing a term this reader cannot resolve yields
    None rather than a partially-filled summary, because every check
    downstream compares the ledger against these figures.
    """
    head = _SUMMARY_HEAD_RE.search(text)
    if head is None:
        return None
    previous = _PREVIOUS_RE.search(text, head.end())
    if previous is None:
        return None
    ending = _ENDING_RE.search(text, previous.end())
    if ending is None:
        return None

    beginning = _figure(previous.group(1))
    closing = _figure(ending.group(1))
    if beginning is None or closing is None:
        return None

    counted: dict[int, tuple[int, float]] = {}
    uncounted: dict[int, float] = {1: 0.0, -1: 0.0}
    for term in _TERM_RE.finditer(text, previous.end(), ending.start()):
        value = _figure(term.group("figure"))
        if value is None:
            return None
        sign = 1 if term.group("op") == "+" else -1
        if term.group("count") is None:
            uncounted[sign] += value
            continue
        if sign in counted:
            # Two counted terms on one side is a grid this reader has not
            # been shown.  Adding them up would be a guess about which rows
            # each one enumerates, and the count check is what the guess
            # would silently disable.
            return None
        counted[sign] = (int(term.group("count")), value)

    if 1 not in counted or -1 not in counted:
        return None
    credit_count, credits = counted[1]
    debit_count, debits = counted[-1]
    return _Summary(
        product=" ".join((head.group(1) or "").split()),
        beginning=beginning,
        ending=closing,
        credit_count=credit_count,
        credits=credits,
        debit_count=debit_count,
        debits=debits,
        uncounted_credit=round(uncounted[1], 2),
        uncounted_debit=round(uncounted[-1], 2),
    )


# ---------------------------------------------------------------------------
# The printed grids
# ---------------------------------------------------------------------------

#: A section heading of this template: its own name, alone on a printed line.
#: The bullet the platform prints in front of it reaches OCR as assorted
#: letter-shaped noise (`e`, `e@`, `@`), so a short run of non-word characters
#: and single letters is allowed before the name and nothing after it.
_SECTION_RE = re.compile(
    r"(?m)^[^\w\n]{0,4}(?:[A-Za-z@]{1,2}[^\w\n]{0,3})?"
    r"(Deposits and Other Credits|Checks|Other Debits|Balance By Date)\s*$"
)

#: Where the ledger stops.  Both alternatives are the printed heading of a
#: block that follows every ledger on this template - the cheque-image sheet
#: and the back-of-form disclosures - and the disclosures are the reason the
#: boundary is needed at all: their fine print contains the phrase `other
#: debits`, so a section allowed to run to the end of the document would take
#: the whole disclosure page into the ledger.
_LEDGER_END_RE = re.compile(r"(?i)Close\s+Date\s*:|\bIn\s?case of errors\b")

#: The printed column legend under a section heading.  This template prints
#: its grids in SEVERAL columns per page, and the legend is the unit repeated
#: once per column, so it states both what a row is and how many rows a
#: printed line may carry.  Reading it - rather than assuming a column count -
#: is what makes the duplication guard in `_grid_rows` a real bound.
_LEGEND_UNITS = {
    ("date", "amount", "description"): "amount",
    ("date", "serial", "amount"): "serial",
    ("date", "balance"): "balance",
}


def _legend(line: str) -> tuple[str, int] | None:
    """`(kind, columns)` for a printed legend line, or None if unreadable."""
    words = [word.lower() for word in line.split()]
    for unit, kind in _LEGEND_UNITS.items():
        size = len(unit)
        if not words or len(words) % size or tuple(words[:size]) != unit:
            continue
        columns = len(words) // size
        if all(tuple(words[i * size:(i + 1) * size]) == unit for i in range(columns)):
            return kind, columns
    return None


def _sections(text: str) -> list[tuple[str, str, int, str]] | None:
    """`(name, kind, columns, body)` for every printed grid, in order.

    None when a section prints a legend this reader cannot resolve - an
    unknown grid is refused rather than read with a guessed shape.
    """
    end = _LEDGER_END_RE.search(text)
    ledger = text[:end.start()] if end else text
    marks = list(_SECTION_RE.finditer(ledger))
    sections: list[tuple[str, str, int, str]] = []
    for index, mark in enumerate(marks):
        stop = marks[index + 1].start() if index + 1 < len(marks) else len(ledger)
        body = ledger[mark.end():stop]
        legend_line, _, rest = body.lstrip("\n").partition("\n")
        legend = _legend(legend_line)
        if legend is None:
            return None
        kind, columns = legend
        sections.append((mark.group(1).lower(), kind, columns, rest))
    return sections


_DATE_RE = r"(?<![\d/])(\d{1,2}/\d{1,2})"
_ROW_AMOUNT_RE = re.compile(rf"{_DATE_RE}\s+({_FIGURE})(?!\d)")
_ROW_SERIAL_RE = re.compile(rf"{_DATE_RE}\s+(\d{{2,7}})\s*\*?\s+({_FIGURE})(?!\d)")


def _grid_rows(body: str, kind: str, columns: int) -> list[tuple[str, float, str]] | None:
    """`(mm/dd, value, description)` for every row of one grid.

    Read ONE PRINTED LINE AT A TIME, and a line may yield at most `columns`
    rows - the bound the section's own printed legend declared.

    That bound is the guard this layout needs.  A multi-column grid is
    flattened by OCR into lines that each carry several rows plus the
    continuation text of the rows above them, so a reader scanning the
    section as one blob has no way to tell a row it has already read from one
    it has not.  A line yielding more rows than the grid has columns means the
    line was mis-segmented, and this returns None rather than publishing the
    duplicate: a duplicated row keeps the balance chain closing only if its
    amount is zero, but it moves the COUNT, which is exactly the constraint
    this template prints and the reason the count is checked at all.

    A row's description is the text between its own amount and the START OF
    THE NEXT ROW ON THE SAME LINE, and deliberately no more.  This platform
    prints a row's trailing reference number on the line BELOW it, in that
    row's column - so the continuation lines of two side-by-side rows arrive
    interleaved with no column boundary left in the text, and attributing one
    to a row would be a guess with a plausible-looking result.  What is
    published is what the row's own line printed.
    """
    pattern = _ROW_SERIAL_RE if kind == "serial" else _ROW_AMOUNT_RE
    rows: list[tuple[str, float, str]] = []
    for line in body.splitlines():
        matches = list(pattern.finditer(line))
        if len(matches) > columns:
            return None
        for index, match in enumerate(matches):
            value = _figure(match.group(pattern.groups))
            if value is None:
                return None
            stop = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            trailing = line[match.end():stop]
            if kind == "serial":
                description = f"Check {match.group(2)}"
            else:
                description = " ".join(trailing.split())
            rows.append((match.group(1), value, description))
    return rows


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

_PERIOD_RE = re.compile(
    rf"(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})\s*{MINUS_CLASS}\s*(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})"
)


def _period(text: str) -> tuple[date, date] | None:
    """The statement period, which the page header of every page prints.

    Every printing must agree.  A document whose pages disagree about their
    own period has been assembled from more than one statement, and reading
    the first printing would attribute one statement's rows to another's
    figures.
    """
    printed = {match.groups() for match in _PERIOD_RE.finditer(text)}
    if len(printed) != 1:
        return None
    a_month, a_day, a_year, b_month, b_day, b_year = printed.pop()
    try:
        start = date(int(a_year), int(a_month), int(a_day))
        end = date(int(b_year), int(b_month), int(b_day))
    except ValueError:
        return None
    return (start, end) if start < end else None


def _resolve(token: str, *, start: date, end: date) -> date | None:
    """A printed `mm/dd` resolved to the year that places it in the period.

    Bounded by the period itself, so a period spanning a year boundary is
    resolved correctly and a row the template never prints - one dated outside
    its own statement period - is not resolved at all.
    """
    month, day = (int(part) for part in token.split("/"))
    for year in (start.year, end.year):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            return candidate
    return None


# ---------------------------------------------------------------------------
# The oracle
# ---------------------------------------------------------------------------

#: How much search this reader will do before it stops trying to justify a
#: document.  The walk below is bounded twice over already - by the number of
#: rows the bank says it left out, and by the figure they must come to, which
#: prunes every partial sum that has passed it - and over the measured
#: population the excluded count is 0, 1 or 2 and the search never exceeds a
#: few hundred states.  The cap is therefore not a tuning knob but a promise
#: that `parse` is cheap and total: a pathological document is refused rather
#: than searched, which is the fail-closed direction.
_PARTITION_STATES = 20000


def _partition_holds(values: list[float], *, counted: int, total: float,
                     uncounted: float) -> bool:
    """Does one direction's rows reproduce the partition the bank printed?

    The bank printed how many rows it counted (`counted`), what they came to
    (`total`), and what the rows it did NOT count came to (`uncounted`).  The
    rows this reader captured satisfy that description when

    * they number `counted` plus however many the bank left out, and
    * some `len(values) - counted` of them come to exactly `uncounted`,

    which together force the remaining `counted` rows to come to `total`.

    Which rows those are is not decided, and deliberately so: every row is
    published either way, with the date, description and amount the bank
    printed on it, so the partition is a CHECK on the capture rather than an
    output of it.  Insisting the subset be unique would refuse documents whose
    published payload is not in question - two $18.00 fees are two $18.00
    fees.  What the check does establish is the distribution, not just the
    sum: where the bank left out one row, exactly one captured row must equal
    the excluded figure to the cent.
    """
    excluded = len(values) - counted
    if excluded < 0:
        return False
    if abs(round(sum(values) - total - uncounted, 2)) > _TOLERANCE:
        return False
    reachable: dict[int, set[float]] = {0: {0.0}}
    states = 1
    for value in values:
        for size in sorted(reachable, reverse=True):
            if size + 1 > excluded:
                continue
            nxt = reachable.setdefault(size + 1, set())
            for partial in reachable[size]:
                candidate = round(partial + value, 2)
                if candidate <= uncounted + _TOLERANCE:
                    nxt.add(candidate)
        states = sum(len(sums) for sums in reachable.values())
        if states > _PARTITION_STATES:
            return False
    return any(abs(candidate - uncounted) <= _TOLERANCE
               for candidate in reachable.get(excluded, ()))


#: The marker this template prints beside an overdrawn balance in its daily
#: grid.  The grid prints magnitudes, and this is how it prints the sign.
_OVERDRAWN_RE = re.compile(r"^\s*OD\b")


def _daily(rows: list[tuple[str, float, str]], *, start: date,
           end: date) -> dict[date, float] | None:
    """The `Balance By Date` grid as `{day: balance}`, or None if malformed.

    The grid opens on the day BEFORE the period - the balance the summary
    calls `PREVIOUS BALANCE`, printed a second time - so that one date is
    resolved outside the period on purpose.  A repeated date means the grid
    was read twice and the walk it anchors would be meaningless.
    """
    opening = start - timedelta(days=1)
    balances: dict[date, float] = {}
    for token, value, trailing in rows:
        day = _resolve(token, start=opening, end=end)
        if day is None:
            return None
        if _OVERDRAWN_RE.match(trailing):
            value = -value
        if day in balances:
            return None
        balances[day] = value
    return balances


def _walk_agrees(txns: list[Transaction], grid: dict[date, float], *,
                 beginning: float, ending: float, start: date) -> bool:
    """Does the printed daily grid agree with the ledger, day for day?

    The second opinion, and an independent one: it is printed from the bank's
    own posting engine rather than derived from the rows above it, so it
    catches a row read on the wrong day or into the wrong direction even where
    the direction totals still come out right.

    Three things must hold.  The grid must open on the previous balance; it
    must close on the ending balance; and it must list EXACTLY the days the
    ledger posted on - a grid day the ledger never touched, or a posting day
    the grid never printed, means one of the two is incomplete.
    """
    opening = start - timedelta(days=1)
    if grid.get(opening) is None or abs(grid[opening] - beginning) > _TOLERANCE:
        return False
    posted: dict[date, float] = {}
    for txn in txns:
        day = date.fromisoformat(txn.date)
        posted[day] = round(posted.get(day, 0.0) + txn.amount, 2)
    if set(posted) != set(grid) - {opening}:
        return False
    running = beginning
    for day in sorted(posted):
        running = round(running + posted[day], 2)
        if abs(running - grid[day]) > _TOLERANCE:
            return False
    return abs(running - ending) <= _TOLERANCE


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

#: What this template is, in the two pieces of its own furniture that no other
#: registered reader prints.
#:
#: The first is the four-way summary: a grid bookended by `PREVIOUS BALANCE`
#: and `ENDING BALANCE` that prints at least one COUNTED and one UNCOUNTED
#: term between them.  That uncounted term is the partition itself, and it is
#: the structural fact that separates this template from every layout whose
#: summary is just an opening balance, two totals and a closing balance.
#:
#: The second is the daily grid, matched by its own printed heading.  It is
#: required rather than corroborating because the reader will not publish
#: without it: the walk is one of the seven constraints, and a document that
#: does not print the grid cannot satisfy them all.
#:
#: The two term patterns are told apart by ONE character - whether a digit or
#: a letter follows the operator - which is the same structural distinction
#: `_summary` makes, spelled as a pattern so the marker and the reader cannot
#: drift into disagreeing about what a partitioned summary is.
_COUNTED_TERM_RE = re.compile(
    rf"(?mi)^\s*(?:\+|{MINUS_CLASS})\s*\d{{1,6}}\s+[A-Za-z][A-Za-z ]{{2,30}}?\s+{_FIGURE}(?!\d)"
)
_UNCOUNTED_TERM_RE = re.compile(
    rf"(?mi)^\s*(?:\+|{MINUS_CLASS})\s*[A-Za-z][A-Za-z ]{{2,30}}?\s+{_FIGURE}(?!\d)"
)
_DAILY_HEAD_RE = re.compile(r"(?m)^[^\w\n]{0,4}(?:[A-Za-z@]{1,2}[^\w\n]{0,3})?Balance By Date\s*$")


def _has_partitioned_summary(text: str) -> bool:
    previous = _PREVIOUS_RE.search(text)
    if previous is None:
        return False
    ending = _ENDING_RE.search(text, previous.end())
    if ending is None:
        return False
    region = text[previous.end():ending.start()]
    return bool(_COUNTED_TERM_RE.search(region)
                and _UNCOUNTED_TERM_RE.search(region))


DETECTION_MARKERS = (
    required("partitioned_summary", _has_partitioned_summary),
    required("balance_by_date_grid", lambda text: bool(_DAILY_HEAD_RE.search(text))),
)

detect = make_detector(DETECTION_MARKERS)


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

_ACCOUNT_RE = re.compile(r"(?i)Account\s+Number\s*:\s*(\d{4,})")

_CREDIT_SECTIONS = frozenset({"deposits and other credits"})
_DEBIT_SECTIONS = frozenset({"checks", "other debits"})


def _account_number(text: str) -> str | None:
    """The account number, when the document prints ONE.

    Two different numbers means the file holds more than one account and the
    `Statement` schema holds one (MASTER_PLAN L-1), so neither is published.
    """
    printed = {match.group(1) for match in _ACCOUNT_RE.finditer(text)}
    return printed.pop() if len(printed) == 1 else None


def parse_balance_by_date_statement(markdown: str) -> Statement | None:
    """Any issuer's statement on this template, or None.

    Declines - rather than guesses - whenever the document's own printed
    evidence does not close: an unreadable summary grid, a grid whose legend
    this reader does not know, a printed line carrying more rows than its grid
    has columns, a count or total that the captured rows do not reproduce, a
    balance identity that does not hold, or a daily grid that disagrees with
    the ledger it is printed beside.
    """
    if not detect(markdown).claims:
        return None
    return _parse(markdown)


def _parse(text: str) -> Statement | None:
    summary = _summary(text)
    if summary is None or not summary.identity_holds:
        return None
    period = _period(text)
    if period is None:
        return None
    start, end = period

    sections = _sections(text)
    if not sections:
        return None

    txns: list[Transaction] = []
    credits: list[float] = []
    debits: list[float] = []
    daily_rows: list[tuple[str, float, str]] = []
    for name, kind, columns, body in sections:
        rows = _grid_rows(body, kind, columns)
        if rows is None:
            return None
        if name == "balance by date":
            daily_rows.extend(rows)
            continue
        if name not in _CREDIT_SECTIONS and name not in _DEBIT_SECTIONS:
            return None
        sign = 1 if name in _CREDIT_SECTIONS else -1
        for token, value, description in rows:
            day = _resolve(token, start=start, end=end)
            if day is None:
                return None
            (credits if sign > 0 else debits).append(value)
            txns.append(Transaction(
                date=day.isoformat(),
                description=description or "(no description)",
                amount=round(sign * value, 2),
                direction="credit" if sign > 0 else "debit",
            ))

    if not txns or not daily_rows:
        return None
    if not _partition_holds(credits, counted=summary.credit_count,
                            total=summary.credits,
                            uncounted=summary.uncounted_credit):
        return None
    if not _partition_holds(debits, counted=summary.debit_count,
                            total=summary.debits,
                            uncounted=summary.uncounted_debit):
        return None

    grid = _daily(daily_rows, start=start, end=end)
    if grid is None:
        return None
    txns.sort(key=lambda txn: (txn.date, -txn.amount, txn.description))
    if not _walk_agrees(txns, grid, beginning=summary.beginning,
                        ending=summary.ending, start=start):
        return None

    opening = start - timedelta(days=1)
    return Statement(
        # Honest-unknown-issuer (Gustavo's ruling, W3 batch 3).  This template
        # prints its issuer's wordmark as a GRAPHIC: the masthead's text is a
        # post-office box, a city and a mailing endorsement, and no name.  The
        # only place the issuer is named in text is the back-of-form billing
        # disclosures, which is precisely the region
        # `analysis/community_section.py` proved can name an institution the
        # statement merely cites rather than the one that issued it.  Some
        # months a labelled masthead domain is printed in the marketing line,
        # and some months a different message occupies it - keying identity on
        # that would make the published issuer depend on which advertisement
        # the bank ran.  So nothing is published, and the figures stand on the
        # document's own arithmetic.
        bank=None,
        account_name=summary.product or None,
        account_number=_account_number(text),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=(end - start).days + 1,
        beginning_balance=summary.beginning,
        ending_balance=summary.ending,
        stated_total_credits=summary.credits,
        stated_total_debits=summary.debits,
        stated_credit_count=summary.credit_count,
        stated_debit_count=summary.debit_count,
        stated_service_charge=summary.uncounted_debit,
        stated_interest_paid=summary.uncounted_credit,
        # The grid's opening entry is the previous balance printed again, and
        # it is dated OUTSIDE the period.  It has done its work as evidence
        # (`_walk_agrees`); publishing it would hand the ADB engine a snapshot
        # it must reject as out of period.
        stated_daily_balances=[
            StatementDailyBalance(date=day.isoformat(), balance=balance)
            for day, balance in sorted(grid.items()) if day != opening
        ],
        transactions=txns,
    )
