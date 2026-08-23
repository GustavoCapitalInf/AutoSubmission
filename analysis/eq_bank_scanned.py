"""EQ Bank (Equitable Bank) monthly statement, as scanned — W3 §TANGERINE.

WHAT THE ARCHIVE HOLDS. Five documents, one account, five consecutive months,
each month's printed closing balance the next month's printed opening balance.
The SN3 census filed the family under the working name `tangerine`; the cached
OCR text of all five names a different issuer and the string "tangerine" does
not occur in any of them. The issuer this reader registers is the one the page
furniture prints: the contact domain in the summary block and the address and
copyright line in the footer of every page.

THE PRINTED SHAPE. A summary block of four terms that close on each other.
The figures below are INVENTED — they are the same invented figures the tests
use, and no amount, name, account number or date from any archive document
appears anywhere in this module, in `tests/test_eq_bank_scanned.py`, or in
W3 §TANGERINE (`webapp_data/` is gitignored by design and no archive content
is reproduced anywhere in this repository):

    Opening balance     $1,037.41
    Total deposits    + $713.26
    Total withdrawals - $268.13
    Closing balance   = $1,482.54

— and then one `Activity details` grid, repeated under its column head on
every page, whose columns are Date, Description, Withdrawals, Deposits and
**Balance**: a RUNNING balance printed on every row.

THE CARD IS THE DIRECTION OF A ROW, and the running balance is what solves it.
The scan flattens the two money columns into one run of text, so the column a
figure sat in is not recoverable from position. The bank does print a minus
before a withdrawal's figure, and on this archive's 330 rows that minus
survived every time — but a minus is one glyph, and a reader that took it as
the answer would silently invert a row the moment Tesseract dropped one.

So the DIRECTION IS DERIVED FROM ARITHMETIC and the minus is checked against
it: each row's amount must equal the absolute difference between the balance
printed on it and the balance printed on the row before (the opening balance
seeds the first), and the sign of that difference is the direction. A
DESCRIPTION VOCABULARY WOULD BE WORSE THAN USELESS HERE and the archive proves
it rather than the claim resting on taste: one row of this family reads
`Interac e-Transfer sent to es <name>` and is a CREDIT — the reversal of the
identically-worded debit two rows above it — and `Interac e-Transfer
cancelled` is a credit on two documents. Memorising either would be reading
our own list instead of the document (R-1), and would get those rows wrong.

WHAT THIS READER REFUSES (fabricated rows and hallucinated values are the
class killers of a scanned registration, so they are named):

* a row whose printed amount is not the absolute step between two printed
  balances, or whose step is zero — the walk stops and the document refuses;
* a DROPPED row, by the same walk: the next row's step no longer equals its
  amount. The walk is anchored at the printed opening balance and must arrive
  at the printed closing balance, so a row lost at either end refuses too.
  This reader therefore has a complete-coverage oracle and needs no stated
  count (this template prints none);
* a line inside a ledger region that is not a row: every non-blank line
  between a column head and its page's footer must parse, so an illegible
  printing fails the document closed instead of contributing a partial grid;
* a summary term printed twice with two different values (a repeat that
  AGREES is free corroboration and is accepted);
* a posting date the document does not determine — see `_resolve_dates`;
* a header, account number or period whose two READINGS disagree.

  That last one is narrower than it first sounds and the difference is worth
  stating rather than leaving to be discovered. `tables.unique_match` — the
  shared helper, which a private near-copy of this module's own stood in for
  until W3 §SCANHYG — compares the MATCHES its pattern found: two pages that
  both parse as a header and disagree refuse the document. A page whose header
  the scan garbled BELOW the pattern is not a second reading at all — it
  matches nothing, contributes nothing, and the remaining good reading is
  taken. So this refuses contradiction, not illegibility, and a document whose
  only legible header is on one page is read from that page.

WHAT IT DOES NOT SET, deliberately: `Statement.currency`. See §CURRENCY below.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import (
    MONTH_NAME_ALT,
    MONTH_NUMBERS,
    day_readings,
    iso_unique_in_period,
    sole_day,
)
from .money import MINUS_CLASS, parse_money
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import unique_match
from .td_can import normalize_mojibake

#: A printed figure on this template: always two decimals, always behind a `$`.
#: Bounded on both sides so a reference number cannot supply the head of one.
_FIGURE = r"(?<![\d.,])\d[\d,]{0,15}\.\d{2}(?![\d,]*\d)"

#: The one header line, reprinted at the top of every page: holder, account
#: number, and the period in full dates. Read as a whole rather than in three
#: independent searches, so a document that prints two different accounts or
#: two different periods contradicts itself instead of blending.
_HEADER_RE = re.compile(
    rf"^(?P<holder>\S.*?)\s+Account\s*#\s*(?P<account>\d[\d\- ]{{2,30}}?)\s+"
    rf"(?P<start_month>{MONTH_NAME_ALT})\s+(?P<start_day>\d{{1,2}}),\s*(?P<start_year>\d{{4}})"
    rf"\s+to\s+"
    rf"(?P<end_month>{MONTH_NAME_ALT})\s+(?P<end_day>\d{{1,2}}),\s*(?P<end_year>\d{{4}})\s*$",
    re.IGNORECASE | re.MULTILINE,
)
#: The statement's own title, also on every page. A SECOND, independent
#: reading of which month this is: it must name the month the period opens in.
_TITLE_RE = re.compile(
    rf"^(?P<month>{MONTH_NAME_ALT})\s+(?P<year>\d{{4}})\s+Statement\b",
    re.IGNORECASE | re.MULTILINE,
)
_SUMMARY_TERMS = {
    "opening": re.compile(rf"Opening balance\s+\$({_FIGURE})", re.IGNORECASE),
    "deposits": re.compile(rf"Total deposits\s*\+\s*\$({_FIGURE})", re.IGNORECASE),
    "withdrawals": re.compile(
        rf"Total withdrawals\s*{MINUS_CLASS}\s*\$({_FIGURE})", re.IGNORECASE
    ),
    "closing": re.compile(rf"Closing balance\s*=\s*\$({_FIGURE})", re.IGNORECASE),
}
#: Printed beside the four terms, and not part of their identity.
_INTEREST_RE = re.compile(rf"Total interest earned\s+\$({_FIGURE})", re.IGNORECASE)

_PAGE_BREAK_RE = re.compile(r"^---\s*Page\s+\d+\s*---\s*$", re.MULTILINE)
#: The ledger's column head, reprinted on every page. Opens a ledger region.
_COLUMN_HEAD_RE = re.compile(
    r"^Date\s+Description\s+Withdrawals\s+Deposits\s+Balance\s*$", re.IGNORECASE
)
#: The page footer's own declaration, which closes a ledger region. Required:
#: a page whose furniture is illegible is a page whose ledger may be too, and
#: this reader would rather refuse than guess where the grid stopped.
_FOOTER_RE = re.compile(r"Page\s+\d+\s+of\s+\d+", re.IGNORECASE)
#: One printed ledger row. The day token is captured as PRINTED and decoded
#: later: the scan turns some day numbers into a stray glyph, and what to do
#: about that is a question about the document's chronology, not about this
#: regex (`_resolve_dates`).
_ROW_RE = re.compile(
    rf"^(?P<month>{MONTH_NAME_ALT})\s*(?P<day>\S{{1,3}})\s+(?P<description>\S.*?)\s+"
    rf"(?P<sign>{MINUS_CLASS}\s*)?\$(?P<amount>{_FIGURE})\s+"
    rf"(?P<balance_sign>{MINUS_CLASS}\s*)?\$(?P<balance>{_FIGURE})\s*$",
    re.IGNORECASE,
)

EQ_BANK_DETECTION_MARKERS = (
    # The issuer's own contact domain, printed in the summary block.
    required("issuer_contact_domain", lambda t: "EQBANK.CA" in t),
    # This template's summary head.
    required("summary_head", lambda t: "YOUR ACTIVITY SUMMARY" in t),
    # The ledger column head — and specifically the RUNNING BALANCE column
    # this reader's direction oracle is built on. Required at DETECTION and
    # not merely at parse: a printing without it is one whose row directions
    # this reader cannot solve, and claiming it would strand a document
    # another reader could take.
    required(
        "running_balance_columns",
        lambda t: re.search(r"WITHDRAWALS\s+DEPOSITS\s+BALANCE", t) is not None,
    ),
)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in: scanned sources arrive with
    double-encoded accents, so repair them before matching."""
    return normalize_mojibake(markdown).upper()


#: Named `detect` because this module holds exactly one reader, which is the
#: convention `tests/test_parser_registry_entries.py` checks a registration
#: against its module by.
detect = make_detector(EQ_BANK_DETECTION_MARKERS, detection_text)


def _cents(token: str) -> int | None:
    """A printed figure as a whole number of cents, or None if it is not one."""
    amount = parse_money(token)
    if amount is None:
        return None
    return int(round(amount * 100))


class _Row:
    """One printed ledger row, before its date and direction are known."""

    __slots__ = ("month", "day_token", "description", "printed_minus", "cents", "balance")

    def __init__(
        self,
        month: str,
        day_token: str,
        description: str,
        printed_minus: bool,
        amount_cents: int,
        balance_cents: int,
    ) -> None:
        self.month = month
        self.day_token = day_token
        self.description = description
        self.printed_minus = printed_minus
        self.cents = amount_cents
        self.balance = balance_cents


def _read_rows(source: str) -> list[_Row] | None:
    """Every printed ledger row in printed order, or None if a line is not one.

    A ledger region is what lies between a page's column head and that page's
    footer declaration. Rows are taken from those regions and from nowhere
    else, and EVERY non-blank line inside one must parse: a region holding a
    line this reader cannot read is a region whose grid may be incomplete, and
    a partial grid published as a whole one is the failure this refuses.
    """
    rows: list[_Row] = []
    for page in _PAGE_BREAK_RE.split(source):
        inside = False
        for line in page.splitlines():
            stripped = line.strip()
            if not inside:
                inside = _COLUMN_HEAD_RE.match(stripped) is not None
                continue
            if not stripped:
                continue
            if _FOOTER_RE.search(stripped):
                inside = False
                continue
            match = _ROW_RE.match(stripped)
            if match is None:
                return None
            amount = _cents(match.group("amount"))
            balance = _cents(match.group("balance"))
            if amount is None or balance is None:
                return None
            rows.append(
                _Row(
                    match.group("month"),
                    match.group("day"),
                    match.group("description").strip(),
                    match.group("sign") is not None,
                    amount,
                    -balance if match.group("balance_sign") else balance,
                )
            )
        if inside:
            # The region never closed: this page's footer declaration is not
            # legible, so where its grid ended is not known.
            return None
    return rows


def _admissible_days(month: int, *, lower: date, upper: date) -> dict[int, str]:
    """`day-of-month -> the one ISO date it can mean`, for a row printing
    `month` somewhere inside `lower .. upper`.

    Everything the DOCUMENT determines about a row's date before its own cell
    is read: the window, and the month the row itself prints. The year comes
    out of `iso_unique_in_period` and therefore only where the window decides
    it uniquely, which is the same refusal a bare month/day gets everywhere
    else in this platform. Thirty-one bounded probes rather than a walk, so a
    period the scan damaged into spanning years cannot turn this into a loop.
    """
    found: dict[int, str] = {}
    for day in range(1, 32):
        iso = iso_unique_in_period(month, day, start=lower, end=upper)
        if iso is not None:
            found[day] = iso
    return found


def _resolve_dates(
    rows: list[_Row], *, period_start: date, period_end: date
) -> list[date] | None:
    """One date per row, taken from the document, or None if it does not say.

    Three things happen here and each is a refusal, not a repair.

    1. THE YEAR IS THE PERIOD'S. Rows print a month name and a day and no
       year. A row resolves only if exactly ONE candidate year puts it inside
       the printed period — extended by exactly one day, because this template
       posts the following cycle's opening interest credit into this
       statement and dates it `period_end + 1`, and the bank's own printed
       closing balance includes it. That one day is the whole extension: a row
       dated further out is a mis-read and refuses the document.

    2. A DAMAGED DAY CELL IS ENUMERATED, AND ONE READING IS ACCEPTED ONLY WHERE
       ONE IS POSSIBLE. Tesseract renders some day numbers as a stray glyph
       (`&`, `g`) and sometimes leaves the glyph BESIDE the digit it damaged
       (`8&`). `date_tokens.day_readings` answers the question that separates
       those two — when is a glyph in a day cell a digit? — without memorising
       what any glyph is: a decimal glyph is what the bank printed, a
       non-decimal glyph is either a digit or ink, and every combination is
       enumerated. `sole_day` then intersects those readings with what the
       document already determines, in two passes:

       * the printed period and the row's own printed month, which is enough
         for `8&` (a second digit beside the 8 would date the row to the
         eighty-somethingth of the month, so the glyph can only be ink);
       * failing that, the days its nearest LEGIBLE neighbours bound it
         between, which is enough for a lone glyph in a run of one day.

       Two surviving readings means the document does not determine the date,
       and dating the row by preference would publish a chronology the bank did
       not print. THE READER THIS REPLACED deleted every non-decimal glyph and
       took what was left, so `1&` in a period containing both the 1st and the
       14th read as the 1st, silently and with nothing to notice it.

    3. THE SEQUENCE MUST BE NON-DECREASING. This grid is printed in date
       order, so monotonicity is a fact about the document, and it catches a
       day token whose digits ARE legible and WRONG in the only way anything
       here can: a `10` scanned as `1O` reads as day 1 in the middle of a run
       of 9s and 11s, and no arithmetic would ever notice, because a misdated
       row still sums and still reconciles to the closing balance while
       corrupting the daily ledger and therefore the ADB.

       THE RESIDUAL, STATED. Monotonicity catches only a misread that BREAKS
       the order. A wrong day that still lands between its neighbours does
       not break it and is published silently: a true `18` misread as `16`
       between a `15` and a `20` satisfies every gate in this reader. Nothing
       in the document contradicts it — the balances, the totals and the
       closing identity are all indifferent to which of those days a row sat
       on — so this is a limit of the evidence rather than of the reader, and
       it is recorded so that no one later reads the order check as a
       guarantee that every published date is right.
    """
    latest = period_end + timedelta(days=1)
    months: list[int] = []
    for row in rows:
        month = MONTH_NUMBERS.get(row.month.strip().casefold())
        if month is None:
            return None
        months.append(month)

    resolved: list[date | None] = []
    for row, month in zip(rows, months):
        window = _admissible_days(month, lower=period_start, upper=latest)
        readings = day_readings(row.day_token)
        if not readings:
            # No reading of this cell is a day at all: `88`, or a cell that ran
            # into the column next door.
            return None
        day = sole_day(row.day_token, window)
        if day is not None:
            resolved.append(date.fromisoformat(window[day]))
            continue
        if row.day_token.isdecimal():
            # A cell every glyph of which survived has exactly ONE reading, so
            # arriving here means the printed period does not admit it: the row
            # is dated outside the statement it is printed on.
            return None
        resolved.append(None)

    for index, entry in enumerate(resolved):
        if entry is not None:
            continue
        before = next((d for d in reversed(resolved[:index]) if d is not None), None)
        after = next((d for d in resolved[index + 1 :] if d is not None), None)
        lower = before if before is not None else period_start
        if after is None:
            # Nothing legible after it: the printed order bounds this row on
            # one side only, and one side is not a bound.
            return None
        window = _admissible_days(months[index], lower=lower, upper=after)
        day = sole_day(rows[index].day_token, window)
        if day is None:
            return None
        resolved[index] = date.fromisoformat(window[day])

    dates = [entry for entry in resolved if entry is not None]
    if len(dates) != len(rows):
        return None
    if any(later < earlier for earlier, later in zip(dates, dates[1:])):
        return None
    return dates


def parse_eq_bank_scanned_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    source = normalize_mojibake(markdown)

    header = unique_match(source, _HEADER_RE)
    title = unique_match(source, _TITLE_RE)
    if header is None or title is None:
        return None
    start_month = MONTH_NUMBERS.get(header.group("start_month").strip().casefold())
    end_month = MONTH_NUMBERS.get(header.group("end_month").strip().casefold())
    title_month = MONTH_NUMBERS.get(title.group("month").strip().casefold())
    if start_month is None or end_month is None or title_month is None:
        return None
    try:
        period_start = date(
            int(header.group("start_year")), start_month, int(header.group("start_day"))
        )
        period_end = date(
            int(header.group("end_year")), end_month, int(header.group("end_day"))
        )
    except ValueError:
        return None
    if period_end < period_start:
        return None
    # The title is a second, independent printing of which cycle this is. A
    # header whose period the title contradicts is a document disagreeing with
    # itself about its own month, and a mis-scanned period date is exactly how
    # that happens.
    if (title_month, int(title.group("year"))) != (period_start.month, period_start.year):
        return None

    summary: dict[str, int] = {}
    for name, pattern in _SUMMARY_TERMS.items():
        term = unique_match(source, pattern)
        if term is None:
            return None
        value = _cents(term.group(1))
        if value is None:
            return None
        summary[name] = value
    # The fail-fast: a mis-read summary is rejected before a row is parsed.
    if summary["opening"] + summary["deposits"] - summary["withdrawals"] != summary["closing"]:
        return None

    rows = _read_rows(source)
    if not rows:
        return None
    dates = _resolve_dates(rows, period_start=period_start, period_end=period_end)
    if dates is None:
        return None

    # THE WALK. Each row's printed amount must be the absolute step between
    # the balance printed on it and the balance printed before it, and the
    # step's sign is the row's direction. A zero step is refused: it is a row
    # the balances do not account for.
    transactions: list[Transaction] = []
    credit_total = debit_total = 0
    balance = summary["opening"]
    for row, day in zip(rows, dates):
        step = row.balance - balance
        if abs(step) != row.cents or step == 0:
            return None
        credit = step > 0
        # The printed minus, checked against the arithmetic rather than
        # trusted instead of it. Two independent readings of one fact: the
        # glyph the bank printed, and the difference between two balances it
        # printed. Where they disagree the document is not readable with
        # confidence, and this reader would rather be the one that says so.
        if row.printed_minus == credit:
            return None
        if credit:
            credit_total += row.cents
        else:
            debit_total += row.cents
        transactions.append(
            Transaction(
                date=day.isoformat(),
                description=row.description,
                amount=round(step / 100, 2),
                direction="credit" if credit else "debit",
                running_balance=round(row.balance / 100, 2),
            )
        )
        balance = row.balance
    if balance != summary["closing"]:
        return None
    # The bank's own two totals, against the two sides the walk produced.
    # Redundant with the walk over MONEY and kept anyway: a grid short of a
    # row should be reported as a short grid, not as "the ledger did not
    # close", and each check's redundancy depends on every other one holding.
    if credit_total != summary["deposits"] or debit_total != summary["withdrawals"]:
        return None

    # THE ONE-DAY CLOSING EXTENSION IS A WIDENING, AND A WIDENING IS ADMITTED
    # ONLY ON THE DOCUMENT'S OWN EVIDENCE.
    #
    # `_resolve_dates` reads rows dated `period_end + 1` because this issuer
    # posts the following cycle's opening interest credit into this statement
    # and dates it there, and its own printed closing balance includes it. That
    # is the justification for the widening, and until now it was not the
    # CONDITION of it: the window was a date bound and nothing more, so a DEBIT
    # on that day — or an unrelated credit that is no accrual at all — parsed
    # exactly like the interest posting, carried no flag and reached the
    # payload as an ordinary transaction (W3 §TANGERINE TG9.3, closed here).
    # This platform admits a widening only where the document accepts it: the
    # comma-decimal and the slash-less cheque date next door are held to their
    # section's printed total, and this one is held to the shape of the thing
    # it exists for.
    #
    # What this reader can be SURE of is the rows' kind and their place, so
    # that is what it gates on, and the SIZE of the accrual — the printed
    # `Total interest earned` against their sum, and the in-period ledger
    # against `closing - sum` — is a comparison between two printings and
    # belongs where a contradiction between two printings belongs, in
    # `closing_accrual_contradictions` below. Whether the ADB may then be
    # published is neither: `analysis/adb.py` refuses any out-of-period row and
    # that refusal is Gustavo's bundled ruling (TG9 + TG10), untouched here.
    out_of_period = [index for index, day in enumerate(dates) if day > period_end]
    if out_of_period:
        # Contiguous and last. Implied by the non-decreasing gate above, which
        # is why it is stated rather than relied on: each check's redundancy
        # here depends on every other one holding.
        if out_of_period != list(range(len(dates) - len(out_of_period), len(dates))):
            return None
        for index in out_of_period:
            posting = transactions[index]
            if posting.direction != "credit" or posting.amount <= 0:
                return None

    stmt = Statement(
        bank="EQ Bank",
        account_name=header.group("holder").strip(),
        account_number=re.sub(r"\s+", "", header.group("account")),
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        beginning_balance=round(summary["opening"] / 100, 2),
        ending_balance=round(summary["closing"] / 100, 2),
        stated_total_credits=round(summary["deposits"] / 100, 2),
        stated_total_debits=round(summary["withdrawals"] / 100, 2),
    )
    # §CURRENCY. `Statement.currency` is NOT SET HERE, and the omission is the
    # decision rather than an oversight. Every printed figure on this family
    # carries a bare `$`; the cached OCR text of all five archive documents
    # contains no `CAD`, no `USD` and no other currency token anywhere. The
    # issuer's evidence is Canadian — a `.ca` contact domain, an Ontario head
    # office in the footer of every page, Interac e-Transfer postings — and
    # CURRENCY_DOCTRINE.md §A/§B says a proven jurisdiction gives a native
    # default, never the `$` symbol and never the absence of contrary
    # evidence. §C sets the price of asserting one: a read-only measurement
    # packet over the whole affected population, eight proofs, before any
    # pinned movement. This cell did not run that packet, so the field keeps
    # the SCHEMA DEFAULT and this reader asserts nothing. The family is named
    # as a future currency mover in W3 §TANGERINE.
    #
    # This template prints no transaction counts and no average of its own, so
    # `stated_credit_count`, `stated_debit_count`, `days_in_period` and
    # `bank_reported_average_balance` stay unset: a count derived from our own
    # parse is not a figure the bank stated.
    interest = unique_match(source, _INTEREST_RE)
    if interest is not None:
        earned = _cents(interest.group(1))
        if earned is not None:
            stmt.stated_interest_paid = round(earned / 100, 2)
    # The end-of-day balance of every day the account moved, which is the
    # balance printed on that day's LAST row. Days outside the printed period
    # are excluded: a snapshot the period does not contain is not a snapshot
    # of this period, and `analysis/adb.py` refuses the whole document for one.
    snapshots: dict[date, int] = {}
    for day, txn in zip(dates, transactions):
        if period_start <= day <= period_end:
            snapshots[day] = int(round(txn.running_balance * 100))
    stmt.stated_daily_balances = [
        StatementDailyBalance(date=day.isoformat(), balance=round(value / 100, 2))
        for day, value in sorted(snapshots.items())
    ]
    stmt.transactions = transactions
    return stmt


def closing_accrual_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The postings this issuer dates AFTER its printed period end, held
    against the two other printings of the same fact on the same page.

    WHY THIS IS A FINDING AND NOT NOISE. The reader's date window extends one
    day past the printed period because the bank posts the following cycle's
    opening interest credit into this statement and dates it there, and its own
    printed closing balance includes it. The document states the SIZE of that
    accrual twice more — as the summary's `Total interest earned` term, and as
    the gap between the printed closing balance and the balance the in-period
    ledger reaches. Where the three do not agree, the page contradicts itself
    about what those trailing rows are, and that is what a human needs to see:
    the reader has admitted rows outside the printed period on the strength of
    a story the document does not corroborate.

    Where they DO agree the check says nothing, which is the archive's case on
    every document of this family that parses. The corroboration is then a
    measurement anyone can reproduce, and it is the evidence base for the
    closing-accrual seam that would let `analysis/adb.py` publish these
    documents' averages — a seam that is Gustavo's bundled ruling (W3
    §TANGERINE TG9 + TG10) and is NOT implemented here or anywhere on this
    branch.

    The interest term is re-read from the DOCUMENT rather than taken from
    `stated_interest_paid`, so the check compares two independent printings
    even against a reader that stops publishing the term. Total by
    construction: a check that raises is a document routed to review for no
    finding.
    """
    if not stmt.period_end or stmt.ending_balance is None or stmt.beginning_balance is None:
        return []
    try:
        period_end = date.fromisoformat(stmt.period_end)
    except ValueError:
        return []
    trailing: list[Transaction] = []
    in_period_total = 0
    for txn in stmt.transactions:
        try:
            day = date.fromisoformat(txn.date)
        except (TypeError, ValueError):
            return []
        if day > period_end:
            trailing.append(txn)
        else:
            in_period_total += int(round(txn.amount * 100))
    if not trailing:
        return []

    notes: list[str] = []
    accrued = sum(int(round(txn.amount * 100)) for txn in trailing)
    plural = "" if len(trailing) == 1 else "s"
    printed = unique_match(normalize_mojibake(markdown), _INTEREST_RE)
    term = _cents(printed.group(1)) if printed is not None else None
    if term is None:
        notes.append(
            f"{len(trailing)} posting{plural} dated after the printed period end, and no "
            "legible interest term on the page to corroborate them against"
        )
    elif term != accrued:
        notes.append(
            f"the {len(trailing)} posting{plural} dated after the printed period end sum to "
            f"{accrued / 100:,.2f}, which is not the {term / 100:,.2f} the same page states "
            "as interest earned"
        )
    in_period_closing = int(round(stmt.beginning_balance * 100)) + in_period_total
    if int(round(stmt.ending_balance * 100)) - accrued != in_period_closing:
        notes.append(
            f"the ledger inside the printed period reaches {in_period_closing / 100:,.2f}, "
            f"which is not the printed closing balance less those postings "
            f"({(int(round(stmt.ending_balance * 100)) - accrued) / 100:,.2f})"
        )
    return notes
