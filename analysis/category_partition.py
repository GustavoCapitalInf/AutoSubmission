"""A community-bank core whose summary is a signed category PARTITION.

W3 §GLANCE. The batch-8 census ranked this family ninth
(`accounts_at_a_glance_category_number_amount`, 8 documents under three
mastheads) and named it after the `ACCOUNTS AT A GLANCE` relationship block.
That block is furniture, not the invariant: one of the eight prints no
`ACCOUNTS AT A GLANCE` and no masthead at all. What every document prints is a
line of the form

    <product> SUMMARY Type :  **REG   Status :  Active
    Category Number Amount  <label> [<count>] <amount>[+]  ...

and that line is what this reader is built on.

The partition, and how its signs are READ rather than memorised
---------------------------------------------------------------
The categories do not map one-to-one onto credits and debits: `Deposits`,
`Automatic Deposits` and `Miscellaneous Credits` are money in, while `Debits`,
`Card Activity`, `Automatic Withdrawals`, `Automatic Teller Withdrawals`,
`Miscellaneous Debits`, `Miscellaneous Fees` and the service-charge total are
money out. A reader that memorised that list would be one printing away from
booking a credit as a debit, so **no category label appears anywhere in this
module's sign decision**. The platform marks the direction itself, on the
amount: a category of money IN carries a TRAILING PLUS, a category of money
OUT carries no mark at all. Three entries are not categories and are read as
what they are — `Balance Forward From <date>`, `Ending Balance On <date>` and
the bank's own `Average Balance (<basis>)`.

The map that reading produces then has to close the summary's own arithmetic:

    Balance Forward + sum(marked +) - sum(unmarked) == Ending Balance

A partition whose signs the reader got wrong does not close, and the document
is refused. That identity is the first of the gates below and it is the reason
the sign rule can be structural: the printing proposes and the arithmetic
disposes.

**Three meanings, two characters, and the column tells them apart.** A
trailing plus on an AMOUNT is a direction. A trailing minus on a BALANCE is a
sign — this platform prints an overdrawn balance and an overdrawn balance
forward that way. The third combination, a trailing minus on a category
amount, is a printing no document in the family carries, and this reader
refuses it rather than guessing which of the two it meant.

Two ledger shapes under one core
--------------------------------
========================  ==================================  =========================
printing                  UNIFIED issue                       SECTIONED issue
========================  ==================================  =========================
ledger                    one `STATEMENT PERIOD ACTIVITY`     `ALL CREDIT ACTIVITY`,
                          table, `Date Check/Description      `ELECTRONIC DEBITS`,
                          Amount Balance`                     `CHECKS AND OTHER DEBITS`
direction of a row        the TRAILING PLUS on its amount     the SECTION it is printed
                                                              in
running balance           printed on every row                not printed
`CHECKS AND OTHER DEBITS` a RECAP of rows the unified table   a ledger section in its
                          already carries                     own right
========================  ==================================  =========================

Which shape a document is, is decided by what it prints: a document carrying
the unified table reads that table and treats every other transaction block as
a recap; a document without it reads the named sections. The direction of a
row is NEVER read from its description, and the census found the printing that
proves why — one statement carries the same description string as a credit in
`ALL CREDIT ACTIVITY` and as a debit in `ELECTRONIC DEBITS`.

What the reader refuses to read
-------------------------------
**The `COLLECTED BALANCE SUMMARY` is not a daily ledger, and this reader does
not read it.** The platform prints exactly one dated balance grid per
statement, under one of two headings it chooses itself: `DAILY BALANCE
SUMMARY`, which is the end-of-day LEDGER balance, or `COLLECTED BALANCE
SUMMARY`, which is that balance MINUS uncollected float. Under the ADB
doctrine ratified 2026-08-15 the canonical underwriting average is the
calendar-day series of end-of-day LEDGER balances, so a collected series is not
daily evidence of it — it is a different quantity that happens to agree on the
cycles that end with nothing in float. It is a silent trap rather than a noisy
one, which is exactly why the heading is treated as decisive: a reader keying
on "the last grid row equals the ending balance" would pass most of these
documents and publish a wrong average on all of them.

The seed line both grids print — `Beginning Ledger Balance on <date> was
<amount>` — says `Ledger` on both, and IS read on both: it is a third printing
of the opening balance and is gated against the partition's. Only the CELLS of
a collected grid are refused.

**The recaps.** The statement restates money it has already posted, three
times over: an `IMAGE STATEMENT` appendix that reprints every cheque and
deposit, an `ITEMIZED SERVICE CHARGE` block that itemises a charge posted as
one row, and — on the unified issue — a cheque grid that reprints rows the
unified table already carries. None of them is a ledger section here. Two of
them are turned into gates instead (see below).

The per-day oracle this family owes, and where it comes from
------------------------------------------------------------
Everything above proves the ledger is COMPLETE — the right rows, the right
total, the right closing balance. None of it proves any row is on the right
DAY, and a misdated row moves the average while leaving every arithmetic gate
satisfied. So a document must carry at least one independent per-day oracle,
and this reader will not publish one that carries none:

* the UNIFIED issue prints a running balance on every row: the walk from the
  printed balance forward through every row onto the printed ending balance is
  a per-row proof of order and of value;
* a `DAILY BALANCE SUMMARY` is a per-day proof: every cell must equal the
  walked end-of-day balance and the days it prints must be exactly the days
  the ledger posts on;
* where neither is printed the document is DECLINED. It is not published on
  the strength of its arithmetic alone and it is certainly not published on a
  collected grid.

The issuer, which this template does not print in a field
----------------------------------------------------------
`Statement.bank` is None on every document this reader publishes, under the
honest-unknown-issuer ruling of 2026-08-14. What the three printings offer is
a masthead welded to a PO box and a telephone number, a `Branch Name` — which
is a branch office, the §LCPERIOD L4 mistake — and a bare contact domain. None
of them is an institution FIELD bounded on both sides, and one document prints
no institution anywhere above its ledger. The product name IS a field: it is
what the summary line prints to the left of `SUMMARY Type :`, and it is
published as `account_name`.

Currency is the schema default, and that is the honest answer here
-------------------------------------------------------------------
No document in the family prints a currency word, an ISO code or a currency
symbol anywhere — not in the summary, not in the grids, not on a row. The
census measured that directly. Under CURRENCY_DOCTRINE §B a jurisdiction
default is affirmative evidence about a PROVEN institution, and this reader
proves no institution at all: it publishes `bank=None` by construction. So
`currency` is left at the schema default and `currency_source` says
`schema_default`, which is the truth about it. The family is named as a future
mover if the platform ever proves the institution behind these mastheads.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .date_tokens import iso_or_none
from .money import MINUS_CLASS, MINUS_GLYPHS, STRICT_UNSIGNED, parse_amount
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import compact_whitespace, dated_cells, section_runs, unique_match

# ---------------------------------------------------------------------------
# The grammar
# ---------------------------------------------------------------------------

#: A token may not begin part-way through another token, and may not be
#: continued by one. `(` is inside the class for a reason this family supplies
#: rather than for symmetry: one printing welds an authorization stamp
#: `(mm/dd/yy hh:mm:ss)` within a row's description, in the same notation as
#: the row date, and a date-anchored reader that admits it shatters the row
#: (51 of them on one document). A row date is never parenthesised here; the
#: stamp always is.
_TOKEN_START = r"(?<![\w.,/(-])"
_DATE_END = r"(?![\w/-])"
#: Nothing may follow a figure that could have been part of it, and the sign
#: glyphs are in the class as well as the word characters: without them a
#: figure printed `1,234.56-` would match as unsigned with the minus left
#: outside, which is a debit published as a credit.
_FIGURE_END = r"(?![\w.,+" + MINUS_GLYPHS + r"])"

#: `mm/dd/yy`, and only ever two year digits. The page header prints
#: `Statement Date:` with a FOUR-digit year on every page of every document,
#: and the right boundary above is what keeps that year from reading as a row
#: date whose row has no amount — the refusal that would cost every document
#: in the family.
_ROW_DATE = r"(?:1[0-2]|0?[1-9])/(?:3[01]|[12][0-9]|0?[1-9])/[0-9]{2}"
#: `1,234.56`. NOT the bare sub-dollar `.56`: this platform prints the leading
#: zero on every sub-dollar amount the family prints, and admitting the bare
#: form would let the relationship block's bare sub-dollar loan total read as an
#: amount.
_FIGURE = r"[0-9][0-9,]*\.[0-9]{2}"
#: The sign this platform prints AFTER a figure, at most one space away. Which
#: of the three meanings it carries depends on the column — see the module
#: docstring — so it is captured here and decided by the caller.
_TRAILING_SIGN = r"(?:\s?(" + MINUS_CLASS + r"|\+))?"

_DATE_TOKEN = _TOKEN_START + r"(" + _ROW_DATE + r")" + _DATE_END
_AMOUNT_TOKEN = _TOKEN_START + r"(" + _FIGURE + r")" + _TRAILING_SIGN + _FIGURE_END

_DATE_RE = re.compile(_DATE_TOKEN)
_AMOUNT_RE = re.compile(_AMOUNT_TOKEN)


def _magnitude(value: str) -> float | None:
    """A printed figure as a positive number, or None if it is not one."""
    return parse_amount(value, STRICT_UNSIGNED)


def _signed(match: re.Match[str], *, group: int = 1) -> tuple[float, str] | None:
    """`(magnitude, mark)` for one amount token, or None if it is not money.

    `mark` is `"+"`, `"-"` (whatever glyph the platform used, canonicalised)
    or `""`. The caller decides what the mark MEANS in the column it read it
    from; nothing here assumes.
    """
    magnitude = _magnitude(match.group(group))
    if magnitude is None:
        return None
    mark = match.group(group + 1) or ""
    return magnitude, ("-" if mark and mark != "+" else mark)


def _row_date(token: str, start: date, end: date) -> str | None:
    """A printed `mm/dd/yy` row date as an ISO date inside the period, or None.

    The platform prints the year on every row, so it is READ rather than
    inferred from the period; the period is then what says the reading is
    right. Two digits by grammar, and this family's documents are 21st
    century — a token that is not a date at all, or that falls outside the
    printed period, is refused rather than repaired.
    """
    month, day, year = (int(part) for part in token.split("/"))
    iso = iso_or_none(year + 2000, month, day)
    if iso is None or not start <= date.fromisoformat(iso) <= end:
        return None
    return iso


# ---------------------------------------------------------------------------
# Detection: the partition's own furniture, and nothing about an issuer
# ---------------------------------------------------------------------------

#: The summary's own heading line. `Type` and `Status` are the platform's
#: account-control fields and they are what separate this line from a product
#: name printed anywhere else on the page.
_SUMMARY_HEADER_RE = re.compile(
    r"^(.{1,60}?)\s+SUMMARY\s+Type\s*:\s*\S+\s+Status\s*:\s*(\S+)\s*$", re.MULTILINE
)
#: The partition's column header, and everything to the right of it on the
#: same line. The whole partition is printed on one line by this platform, so
#: the line IS the region: a partition the layer split across lines is one
#: this reader has not seen and refuses.
_PARTITION_LINE_RE = re.compile(
    r"^.*?Category\s+Number\s+Amount\s+(\S.*)$", re.MULTILINE
)
#: The two dated entries of the partition, as LABELS. Together with the header
#: above they are what says this is the family rather than some other summary
#: that happens to print the word Category.
_BALANCE_FORWARD_LABEL_RE = re.compile(r"Balance Forward From\s+" + _ROW_DATE)
_ENDING_BALANCE_LABEL_RE = re.compile(r"Ending Balance On\s+" + _ROW_DATE)
#: The platform's own statement of how many CALENDAR days the cycle covers.
#: Corroborating for detection and a gate at parse.
_CYCLE_DAYS_RE = re.compile(r"This Statement Cycle Reflects\s+([0-9]{1,3})\s+Days")

#: **Case is load-bearing and this registration has no normalization.** The
#: section names are the platform's capitals and the partition labels are its
#: title case; an upper-casing normalization would let `BALANCE FORWARD FROM`
#: — which a different scanned template prints — reach these patterns.
DETECTION_MARKERS = (
    required(
        "platform_category_partition",
        lambda t: bool(_SUMMARY_HEADER_RE.search(t))
        and bool(_PARTITION_LINE_RE.search(t)),
    ),
    required(
        "platform_dated_partition_balances",
        lambda t: bool(_BALANCE_FORWARD_LABEL_RE.search(t))
        and bool(_ENDING_BALANCE_LABEL_RE.search(t)),
    ),
    corroborating(
        "platform_printed_cycle_days",
        lambda t: bool(_CYCLE_DAYS_RE.search(t)),
    ),
)

detect = make_detector(DETECTION_MARKERS)


# ---------------------------------------------------------------------------
# The printed summary
# ---------------------------------------------------------------------------

#: The three partition entries that are not categories. Each is recognised by
#: the platform's own wording for it, and each is what it says it is: two
#: dated balances and the bank's own average. Everything else on the line is a
#: movement category whose direction is read off its amount.
_OPENING_ENTRY_RE = re.compile(r"^Balance Forward From\s+(" + _ROW_DATE + r")$")
_CLOSING_ENTRY_RE = re.compile(r"^Ending Balance On\s+(" + _ROW_DATE + r")$")
_AVERAGE_ENTRY_RE = re.compile(r"^Average Balance\s*(\([A-Za-z][A-Za-z ]{0,18}\))?$")
#: A movement category: a printed name, and — for every category except the
#: service-charge total — a printed item COUNT immediately before its amount.
_CATEGORY_ENTRY_RE = re.compile(r"^([A-Za-z][A-Za-z ]*[A-Za-z])(?:\s+([0-9]{1,4}))?$")

#: The account number, printed in the page header of every page and again on
#: every appendix page. TWO different values is not a reading to choose
#: between: it is a document carrying more than one account, which this reader
#: has no schema for (L-1).
_ACCOUNT_NUMBER_RE = re.compile(r"Account No\.\s*:\s*([X*x0-9]{4,})(?![0-9])")

#: The relationship block, when the document prints one, and the roll-up it
#: closes on. The block is a table of the customer's accounts: more than one
#: amount to the right of its column header is more than one account listed,
#: and the roll-up is then a third printing of this statement's own closing
#: balance.
_GLANCE_ROW_RE = re.compile(
    r"Account No\.\s+Sub Acct\.\s+Account Title\s+Acct Type\s+Balance\s+([^\n]*)"
)
_GLANCE_TOTAL_RE = re.compile(r"Your Total Deposits\s*=\s*" + _AMOUNT_TOKEN)

#: The service-charge recap's own total. The partition prints the charge as a
#: category with NO item count; this line is what says how much of the ledger
#: that uncounted category accounts for, and it is read as the bound on it.
_SERVICE_CHARGE_TOTAL_RE = re.compile(
    r"TOTAL SERVICE CHARGE\s*:\s*" + _AMOUNT_TOKEN
)

#: The seed both balance grids print above their cells.
_GRID_SEED_RE = re.compile(
    r"Beginning Ledger Balance on\s+(" + _ROW_DATE + r")\s+was\s+" + _AMOUNT_TOKEN
)


@dataclass(frozen=True)
class _Category:
    """One movement row of the partition: what it is called, how many items it
    covers (None where the platform prints no count) and how much it moved."""

    label: str
    count: int | None
    amount: float
    credit: bool


@dataclass(frozen=True)
class _Summary:
    """Every figure the partition prints, and the period it prints them for."""

    product: str | None
    account: str
    seed: str
    start: str
    end: str
    beginning: float
    ending: float
    categories: tuple[_Category, ...]
    average: float | None
    average_label: str | None

    @property
    def credits(self) -> float:
        return round(sum(c.amount for c in self.categories if c.credit), 2)

    @property
    def debits(self) -> float:
        return round(sum(c.amount for c in self.categories if not c.credit), 2)

    def expected_rows(self, *, credit: bool) -> int:
        """How many postings one direction's categories account for.

        Every category prints a count except the service-charge total, and a
        category printing no count and no money accounts for no rows. The
        platform posts the charge it prints without a count as ONE aggregated
        row and itemises it in a recap of its own — measured on every document
        in the family that carries one — so an uncounted category with money
        in it is one row here. A printing where it is not refuses the document
        at the count gate rather than publishing a ledger it has miscounted.
        """
        total = 0
        for category in self.categories:
            if category.credit is not credit:
                continue
            if category.count is not None:
                total += category.count
            elif category.amount:
                total += 1
        return total

    @property
    def uncounted(self) -> float:
        """What the categories printing no item count add up to."""
        return round(
            sum(c.amount for c in self.categories if c.count is None), 2
        )


def _entries(region: str) -> list[tuple[str, re.Match[str]]] | None:
    """`(label, amount match)` for every entry on the partition line, or None.

    None when the line holds text no entry accounts for. A partition read only
    in part is not a weaker oracle than a whole one — it is a summary this
    reader has misread, and every gate below compares the ledger against it.
    """
    found = list(_AMOUNT_RE.finditer(region))
    if not found:
        return None
    entries: list[tuple[str, re.Match[str]]] = []
    cursor = 0
    for match in found:
        entries.append((region[cursor:match.start()].strip(), match))
        cursor = match.end()
    if region[cursor:].strip():
        return None
    return entries


def _summary(markdown: str) -> _Summary | None:
    """The whole printed summary, or None if any part of it is unreadable."""
    header = unique_match(markdown, _SUMMARY_HEADER_RE)
    line = unique_match(markdown, _PARTITION_LINE_RE)
    account = unique_match(markdown, _ACCOUNT_NUMBER_RE)
    if header is None or line is None or account is None:
        return None

    entries = _entries(line.group(1))
    if entries is None:
        return None

    opening: tuple[str, float] | None = None
    closing: tuple[str, float] | None = None
    average: tuple[float, str] | None = None
    categories: list[_Category] = []
    for label, match in entries:
        read = _signed(match)
        if read is None:
            return None
        magnitude, mark = read
        if (found := _OPENING_ENTRY_RE.match(label)) is not None:
            if opening is not None or mark == "+":
                return None
            opening = (found.group(1), -magnitude if mark else magnitude)
            continue
        if (found := _CLOSING_ENTRY_RE.match(label)) is not None:
            if closing is not None or mark == "+":
                return None
            closing = (found.group(1), -magnitude if mark else magnitude)
            continue
        if (found := _AVERAGE_ENTRY_RE.match(label)) is not None:
            if average is not None:
                return None
            average = (-magnitude if mark == "-" else magnitude, label)
            continue
        found = _CATEGORY_ENTRY_RE.match(label)
        # A trailing MINUS on a category amount is the one combination of mark
        # and column this platform has never printed. Refused rather than
        # resolved: the two readings of it are a negative credit and a
        # positive debit, and nothing on the page chooses between them.
        if found is None or mark == "-":
            return None
        categories.append(_Category(
            label=found.group(1),
            count=int(found.group(2)) if found.group(2) else None,
            amount=magnitude,
            credit=mark == "+",
        ))
    if opening is None or closing is None or not categories:
        return None

    seed, beginning = opening
    end, ending = closing
    period = _period(markdown, seed, end)
    if period is None:
        return None
    start = period

    # `_period` has already read both printed dates and refused the document
    # if either was not a date, so neither `_iso` can be None here.
    product = header.group(1).strip()
    return _Summary(
        product=product or None,
        account=account.group(1),
        seed=str(_iso(seed)),
        start=start,
        end=str(_iso(end)),
        beginning=beginning,
        ending=ending,
        categories=tuple(categories),
        average=average[0] if average else None,
        average_label=average[1] if average else None,
    )


def _iso(token: str) -> str | None:
    """A printed `mm/dd/yy` as an ISO date with no period to check it against."""
    month, day, year = (int(part) for part in token.split("/"))
    return iso_or_none(year + 2000, month, day)


def _period(markdown: str, seed: str, end: str) -> str | None:
    """The ISO day the period OPENS, or None when the printing disagrees.

    The partition dates its two balances but not its period: the balance
    forward is a balance on the day the LAST statement closed, so the period
    opens the day after. The platform then states the period's length itself —
    `This Statement Cycle Reflects N Days` — and that sentence is the check:
    it is a CALENDAR count on all eight archive documents, which is the same
    basis the ADB doctrine reports on, so a document whose two printings of
    its own period disagree is refused.
    """
    opened, closed = _iso(seed), _iso(end)
    days = unique_match(markdown, _CYCLE_DAYS_RE)
    if opened is None or closed is None or days is None:
        return None
    start = date.fromisoformat(opened) + timedelta(days=1)
    if start > date.fromisoformat(closed):
        return None
    if (date.fromisoformat(closed) - start).days + 1 != int(days.group(1)):
        return None
    return start.isoformat()


# ---------------------------------------------------------------------------
# The document's own sections
# ---------------------------------------------------------------------------

#: The one table the UNIFIED issue prints its whole ledger in.
_UNIFIED_HEADING = "STATEMENT PERIOD ACTIVITY"
#: The SECTIONED issue's ledger, and the direction each section declares. The
#: heading is the platform's own statement of a row's direction and it is the
#: only thing this reader will take a direction from on that issue.
_CREDIT_HEADING = "ALL CREDIT ACTIVITY"
_DEBIT_HEADINGS = ("ELECTRONIC DEBITS", "CHECKS AND OTHER DEBITS")
#: The two balance grids, told apart by the heading the platform chose.
_LEDGER_GRID_HEADING = "DAILY BALANCE SUMMARY"
_COLLECTED_GRID_HEADING = "COLLECTED BALANCE SUMMARY"
#: Blocks that restate money already posted. In the list as BOUNDARIES: they
#: are what stops the section above them running to the end of the document.
_RECAP_HEADINGS = (
    "ITEMIZED SERVICE CHARGE", "IMAGE STATEMENT", "ACCOUNTS AT A GLANCE",
    "PRIVACY NOTICE",
)
_SECTION_NAMES = (
    (_UNIFIED_HEADING, _CREDIT_HEADING)
    + _DEBIT_HEADINGS
    + (_LEDGER_GRID_HEADING, _COLLECTED_GRID_HEADING)
    + _RECAP_HEADINGS
)
_SECTION_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in _SECTION_NAMES) + r")\b")

#: The longest description this reader will publish. A bound has to exist — a
#: span the layer filled with a page of furniture is not a description — and
#: the longest one the family's own rows print is 78 characters.
_DESCRIPTION_LIMIT = 200
#: A row that prints no description of its own. The cheque recap grid and the
#: three-up deposit grid print a serial or a type where a description belongs,
#: and `compact_whitespace` of an empty span is the empty string.
_UNDESCRIBED = "Transaction"


def _described(span: str) -> str:
    """What the bank printed between a row's date and its amount."""
    text = compact_whitespace(span).strip(" |")
    if len(text) > _DESCRIPTION_LIMIT:
        boundary = text.rfind(" ", 0, _DESCRIPTION_LIMIT + 1)
        text = text[:boundary].rstrip() if boundary > 0 else ""
    return text or _UNDESCRIBED


def _unified_rows(
    runs: list[str], *, start: date, end: date
) -> list[Transaction] | None:
    """Every posting the unified table printed, in printed order, or None.

    Each row prints exactly two figures — its amount and the balance after it —
    and the reader requires exactly two rather than taking the last two: a
    description carrying a third figure is a row whose columns this reader
    cannot tell apart, and guessing which two of three are the money is how a
    reference number becomes an amount.
    """
    postings: list[Transaction] = []
    for run in runs:
        dates = list(_DATE_RE.finditer(run))
        for index, found in enumerate(dates):
            stop = dates[index + 1].start() if index + 1 < len(dates) else len(run)
            span = run[found.end():stop]
            figures = list(_AMOUNT_RE.finditer(span))
            if len(figures) != 2:
                return None
            money, balance = (_signed(figures[0]), _signed(figures[1]))
            iso = _row_date(found.group(1), start, end)
            if money is None or balance is None or iso is None:
                return None
            # The amount's mark is a DIRECTION and the balance's is a SIGN;
            # neither column accepts the other's mark.
            if money[1] == "-" or balance[1] == "+":
                return None
            credit = money[1] == "+"
            postings.append(Transaction(
                date=iso,
                description=_described(span[: figures[0].start()]),
                amount=round(money[0] if credit else -money[0], 2),
                direction="credit" if credit else "debit",
                running_balance=round(
                    -balance[0] if balance[1] == "-" else balance[0], 2),
            ))
    return postings


def _sectioned_rows(
    runs: list[str], *, credit: bool, start: date, end: date
) -> list[Transaction] | None:
    """Every posting one named section printed, or None if one is unreadable.

    None rather than "skip": a row whose date the period cannot place, or that
    prints no amount before the next row opens, is a row we could not read,
    and dropping it silently is how a ledger comes to disagree with a printed
    count while still looking complete.
    """
    postings: list[Transaction] = []
    for run in runs:
        cells = dated_cells(run, date_pattern=_DATE_RE, value_pattern=_AMOUNT_RE)
        if cells is None:
            return None
        for cell in cells:
            iso = _row_date(cell.date, start, end)
            amount = _magnitude(cell.value)
            if iso is None or amount is None:
                return None
            postings.append(Transaction(
                date=iso,
                description=_described(cell.described),
                amount=round(amount if credit else -amount, 2),
                direction="credit" if credit else "debit",
            ))
    return postings


def _recap_pairs(runs: list[str], *, start: date, end: date) -> list[tuple[str, float]] | None:
    """`(day, magnitude)` for every row a recap grid reprints, or None."""
    pairs: list[tuple[str, float]] = []
    for run in runs:
        cells = dated_cells(run, date_pattern=_DATE_RE, value_pattern=_AMOUNT_RE)
        if cells is None:
            return None
        for cell in cells:
            iso = _row_date(cell.date, start, end)
            amount = _magnitude(cell.value)
            if iso is None or amount is None:
                return None
            pairs.append((iso, amount))
    return pairs


def _grid_seed(runs: list[str], summary: _Summary) -> bool:
    """Is the grid's own seed the opening balance the partition printed?

    Both headings print it, and both call it a LEDGER balance — so this is the
    platform's third printing of the opening balance and it is read on the
    collected grid as well as on the ledger one. Only the CELLS below it are
    refused there.
    """
    if len(runs) != 1:
        return False
    seed = _GRID_SEED_RE.search(runs[0])
    if seed is None:
        return False
    read = _signed(seed, group=2)
    if read is None or _iso(seed.group(1)) != summary.seed:
        return False
    magnitude, mark = read
    if mark == "+":
        return False
    return abs(round(-magnitude if mark else magnitude, 2)
               - round(summary.beginning, 2)) <= _TOLERANCE


def _grid(runs: list[str], *, summary: _Summary) -> dict[str, float] | None:
    """The ledger daily grid as a day-to-balance map, or None.

    The seed is gated first (`_grid_seed`) and the cells are read from what
    follows it. Each cell is a date and exactly ONE figure, whose trailing
    minus is the platform's overdrawn mark; a cell marked `+` is refused,
    because the balance column of this platform prints a minus or nothing.

    A day printed TWICE refuses the document rather than overwriting the first
    reading: the grid arrives three records to a physical line, so a duplicate
    day is evidence the columns were recovered wrongly and a map that silently
    kept the last one would hide it.
    """
    if not _grid_seed(runs, summary):
        return None
    run = runs[0]
    seed = _GRID_SEED_RE.search(run)
    assert seed is not None  # `_grid_seed` just matched it on this same run
    body = run[seed.end():]

    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    printed: dict[str, float] = {}
    dates = list(_DATE_RE.finditer(body))
    for index, found in enumerate(dates):
        stop = dates[index + 1].start() if index + 1 < len(dates) else len(body)
        figures = list(_AMOUNT_RE.finditer(body[found.end():stop]))
        if len(figures) != 1:
            return None
        read = _signed(figures[0])
        iso = _row_date(found.group(1), start, end)
        if read is None or iso is None or iso in printed:
            return None
        magnitude, mark = read
        if mark == "+":
            return None
        printed[iso] = round(-magnitude if mark else magnitude, 2)
    return printed or None


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------

_TOLERANCE = 0.005


def _matches_the_printed_partition(
    rows: list[Transaction], summary: _Summary, charge: float | None
) -> bool:
    """The partition's own arithmetic, and the ledger against it.

    Five printings, checked independently of one another:

    * `Balance Forward + credits - debits == Ending Balance`, which is the
      summary closing on itself and the proof that the signs were read right;
    * each direction's rows sum to that direction's categories;
    * each direction's row COUNT equals the items its categories declare;
    * the categories printing no item count sum to the service-charge recap's
      own printed total — the platform's second statement of the same figure,
      and zero where it prints no recap.
    """
    identity = summary.beginning + summary.credits - summary.debits
    if abs(identity - summary.ending) > _TOLERANCE:
        return False
    if abs(summary.uncounted - (charge or 0.0)) > _TOLERANCE:
        return False
    for credit, printed in ((True, summary.credits), (False, summary.debits)):
        side = [row for row in rows
                if (row.direction == "credit") is credit]
        if len(side) != summary.expected_rows(credit=credit):
            return False
        if abs(sum(abs(row.amount) for row in side) - printed) > _TOLERANCE:
            return False
    return True


def _walks_to_the_printed_ending(rows: list[Transaction], summary: _Summary) -> bool:
    """The printed running balance, walked row by row from the balance forward.

    The unified issue prints a balance after every posting, so the walk is a
    per-ROW proof rather than a per-day one: it fixes the order the postings
    were applied in as well as their values, and a row on the wrong day inside
    a run of same-day rows is the only construction it cannot see.
    """
    running = summary.beginning
    for row in rows:
        running = round(running + row.amount, 2)
        if row.running_balance is None or abs(row.running_balance - running) > _TOLERANCE:
            return False
    return abs(running - summary.ending) <= _TOLERANCE


def _matches_the_printed_grid(
    rows: list[Transaction], printed: dict[str, float], summary: _Summary
) -> bool:
    """The ledger daily grid, walked against the ledger, in both directions.

    Every day the grid prints equals the walked end-of-day balance, and every
    day the ledger posts on appears in the grid — so neither a day the reader
    invented nor a day it lost can pass. The grid prints only the days the
    account moved on; the days between carry forward, which is the ADB
    engine's job and not this reader's.
    """
    walked: dict[str, float] = {}
    running = summary.beginning
    for row in sorted(rows, key=lambda item: item.date):
        running = round(running + row.amount, 2)
        walked[row.date] = running
    if set(printed) != set(walked):
        return False
    return all(abs(walked[day] - balance) <= _TOLERANCE
               for day, balance in printed.items())


def _matches_the_relationship_block(markdown: str, summary: _Summary) -> bool:
    """The relationship block, when the document prints one.

    Two things at once, and the first is why the block is read at all: the
    grid lists the customer's accounts, so MORE THAN ONE amount to the right
    of its column header is more than one account in this document and the
    single-account schema must not publish one of them (L-1). The roll-up it
    closes on is then a third printing of this statement's closing balance.
    """
    rows = list(_GLANCE_ROW_RE.finditer(markdown))
    if not rows:
        return True
    # Printed twice and differently is the document contradicting itself about
    # its own relationship; printed twice identically is a page header.
    if len({found.group(1) for found in rows}) != 1:
        return False
    row = rows[0]
    if len(_AMOUNT_RE.findall(row.group(1))) != 1:
        return False
    total = unique_match(markdown, _GLANCE_TOTAL_RE)
    listed = _signed(_AMOUNT_RE.search(row.group(1)))  # type: ignore[arg-type]
    if total is None or listed is None or listed[1] == "+":
        return False
    read = _signed(total)
    if read is None or read[1] == "+":
        return False
    balances = [
        round(-magnitude if mark else magnitude, 2) for magnitude, mark in (listed, read)
    ]
    return all(abs(balance - summary.ending) <= _TOLERANCE for balance in balances)


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

def parse_category_partition_statement(markdown: str) -> Statement | None:
    """Any issuer's statement on this core's signed category partition.

    Declines — rather than guesses — in named situations, each of them a fact
    about the document rather than a gap in this reader:

    * it prints no partition, one this reader cannot read end to end, or more
      than one (which is more than one account: L-1);
    * its two printings of its own period disagree;
    * a category amount carries a trailing minus, or a balance a trailing plus;
    * the partition does not close on itself, or the ledger disagrees with any
      printed count or total;
    * a row's date or amount is not readable as one, or a row prints no amount
      before the next row opens;
    * the relationship block lists more than one account;
    * the printed running balance does not walk onto the printed ending
      balance, or the ledger daily grid disagrees with the walked ledger;
    * **it prints no per-day oracle at all** — no running balance and no
      `DAILY BALANCE SUMMARY`. A `COLLECTED BALANCE SUMMARY` is not one, and
      publishing an average against it, or against nothing, is the failure this
      refusal exists to prevent.
    """
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    if summary is None or not summary.start or not summary.end or not summary.seed:
        return None
    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)

    sections = section_runs(markdown, _SECTION_RE)
    unified = sections.get(_UNIFIED_HEADING, [])
    if unified:
        rows = _unified_rows(unified, start=start, end=end)
        if rows is None:
            return None
        # Every other transaction block on this issue restates rows the
        # unified table already carries. The cheque grid is read anyway — as a
        # CHECK: its rows must be among the debits the table printed.
        recap = _recap_pairs(
            sections.get("CHECKS AND OTHER DEBITS", []), start=start, end=end)
        if recap is None or not _reprints(recap, rows):
            return None
    else:
        rows = []
        for heading, credit in (
            (_CREDIT_HEADING, True),
            *((heading, False) for heading in _DEBIT_HEADINGS),
        ):
            found = _sectioned_rows(
                sections.get(heading, []), credit=credit, start=start, end=end)
            if found is None:
                return None
            rows.extend(found)

    # The service-charge recap's own total. Printed at all and not printed
    # ONCE — two different figures under one label — is the document
    # contradicting itself, and the uncounted-category gate below is exactly
    # what would then be checked against a figure nobody can choose.
    printed = list(_SERVICE_CHARGE_TOTAL_RE.finditer(markdown))
    if printed and len({found.groups() for found in printed}) != 1:
        return None
    charged = _signed(printed[0]) if printed else None
    if printed and (charged is None or charged[1] != ""):
        return None
    total_charge = charged[0] if charged else None

    if not _matches_the_printed_partition(rows, summary, total_charge):
        return None
    if not _matches_the_relationship_block(markdown, summary):
        return None

    # A collected grid's CELLS are refused, but the seed line it shares with
    # the ledger grid says `Beginning Ledger Balance` and is read: it is this
    # platform's third printing of the opening balance.
    if _COLLECTED_GRID_HEADING in sections and not _grid_seed(
        sections[_COLLECTED_GRID_HEADING], summary
    ):
        return None

    # The per-day oracle. One of the two, or nothing is published.
    grid = None
    if _LEDGER_GRID_HEADING in sections:
        grid = _grid(sections[_LEDGER_GRID_HEADING], summary=summary)
        if grid is None or not _matches_the_printed_grid(rows, grid, summary):
            return None
    if unified and not _walks_to_the_printed_ending(rows, summary):
        return None
    if grid is None and not unified:
        return None

    return Statement(
        #: The template prints no institution FIELD — see the module docstring.
        bank=None,
        account_name=summary.product,
        account_number=summary.account,
        period_start=summary.start,
        period_end=summary.end,
        days_in_period=(end - start).days + 1,
        beginning_balance=summary.beginning,
        ending_balance=summary.ending,
        stated_total_credits=summary.credits,
        stated_total_debits=summary.debits,
        stated_credit_count=summary.expected_rows(credit=True),
        stated_debit_count=summary.expected_rows(credit=False),
        stated_service_charge=total_charge,
        bank_reported_average_balance=summary.average,
        bank_reported_average_label=summary.average_label,
        stated_daily_balances=[
            StatementDailyBalance(date=day, balance=balance)
            for day, balance in sorted((grid or {}).items())
        ],
        transactions=sorted(rows, key=lambda row: row.date),
    )


def _reprints(recap: list[tuple[str, float]], rows: list[Transaction]) -> bool:
    """Is every row the cheque recap prints one the unified table also printed?

    A multiset containment rather than a set one: the same amount really is
    paid twice on one day in this archive, and a set test would let a recap
    with a row the ledger does not carry pass.
    """
    outstanding: dict[tuple[str, float], int] = {}
    for row in rows:
        if row.amount < 0:
            key = (row.date, round(-row.amount, 2))
            outstanding[key] = outstanding.get(key, 0) + 1
    for key in recap:
        remaining = outstanding.get(key, 0)
        if not remaining:
            return False
        outstanding[key] = remaining - 1
    return True
