"""EQ Bank (Equitable Bank) monthly statement, as scanned — W3 §TANGERINE.

WHAT THE ARCHIVE HOLDS. Five documents, one account, five consecutive months,
each month's printed closing balance the next month's printed opening balance.
The SN3 census filed the family under the working name `tangerine`; the cached
OCR text of all five names a different issuer and the string "tangerine" does
not occur in any of them. The issuer this reader registers is the one the page
furniture prints: the contact domain in the summary block and the address and
copyright line in the footer of every page.

THE PRINTED SHAPE. A summary block of four terms that close on each other —

    Opening balance     $242.99
    Total deposits    + $10,451.12
    Total withdrawals - $4,812.68
    Closing balance   = $5,881.43

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
* a header, account number or period that two pages disagree about.

WHAT IT DOES NOT SET, deliberately: `Statement.currency`. See §CURRENCY below.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import MONTH_NAME_ALT, MONTH_NUMBERS, iso_unique_in_period
from .money import MINUS_CLASS, parse_money
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
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


def _sole(pattern: re.Pattern[str], source: str):
    """The document's single reading of a term, or None.

    `search` alone takes the first occurrence and never notices a second, so a
    statement whose summary or header is printed twice — a continuation page
    reprinting it, a two-account document, an OCR duplication — could publish
    one reading under another's heading and look ordinary. A repeat that
    AGREES is free corroboration and is accepted; a repeat that disagrees is
    the document contradicting itself, and refuses it.
    """
    found = pattern.findall(source)
    if not found or len(set(found)) > 1:
        return None
    return pattern.search(source)


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

    2. A DAY THE SCAN DESTROYED IS DERIVED FROM THE PRINTED ORDER, OR NOT AT
       ALL. Tesseract renders some day numbers as a stray glyph (`&`, `g`),
       and a token holding no digit at all says nothing. Such a row's date is
       bounded by its legible neighbours, and is accepted ONLY where that
       bound is a single day — the nearest resolved date before it equals the
       nearest resolved date after it, and that date falls in the month the
       row itself prints. Two candidate days means the document does not
       determine the date, and publishing either would publish a chronology
       the bank did not print.

    3. THE SEQUENCE MUST BE NON-DECREASING. This grid is printed in date
       order, so monotonicity is a fact about the document — and it is what
       catches a day token whose digits ARE legible and wrong: a `10` scanned
       as `1O` reads as day 1 in the middle of a run of 9s and 11s, and no
       amount of arithmetic would ever notice, because a misdated row still
       sums and still reconciles. It corrupts the daily ledger, and therefore
       the Average Daily Balance, silently.
    """
    latest = period_end + timedelta(days=1)
    resolved: list[date | None] = []
    for row in rows:
        month = MONTH_NUMBERS.get(row.month.strip().casefold())
        digits = "".join(character for character in row.day_token if character.isdigit())
        if month is None:
            return None
        if not digits:
            resolved.append(None)
            continue
        day = int(digits)
        if not 1 <= day <= 31:
            return None
        iso = iso_unique_in_period(month, day, start=period_start, end=latest)
        if iso is None:
            return None
        resolved.append(date.fromisoformat(iso))

    for index, entry in enumerate(resolved):
        if entry is not None:
            continue
        before = next((d for d in reversed(resolved[:index]) if d is not None), None)
        after = next((d for d in resolved[index + 1 :] if d is not None), None)
        lower = before if before is not None else period_start
        if after is None or lower != after:
            return None
        month = MONTH_NUMBERS.get(rows[index].month.strip().casefold())
        if month != after.month:
            return None
        resolved[index] = after

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

    header = _sole(_HEADER_RE, source)
    title = _sole(_TITLE_RE, source)
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
        term = _sole(pattern, source)
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
    interest = _sole(_INTEREST_RE, source)
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
