"""Welch State Bank, `More Than Free Business Checking` — W3 §WELCH.

WHAT THE ARCHIVE HOLDS. Seventeen born-digital statements, ONE account of one
business, a near-contiguous monthly run. The census filed sixteen of them and
filed the seventeenth under another family as a misfile; a whole-archive
marker probe over all 3,380 distinct documents put it back here and found no
eighteenth. The concentration is the honest risk of this registration and it
is recorded rather than smoothed over: every gate below was proven against one
customer's printings, so the reader's behaviour on an unseen Welch template —
a multi-account statement, an interest-bearing section, a service-charge
block, an `Other Credits` banner without a `Deposits` one — is UNMEASURED. It
fails closed on each of them, which is the most that can be claimed.

HOW THE ISSUER IDENTIFIES ITSELF, and why not by name. The wordmark
`Welch State Bank` is printed only on the trailing check-image page, which two
of the seventeen do not have. What every printing carries is the masthead: a
six-branch contact ladder of `<phone> fax: <phone>` lines beside six PO boxes,
the first of which is the bank's own home office. That PO box is the
institution's self-identification on this template and it is what this
registration is built on — institution furniture, in the same class as a
routing number or a contact domain, and not a fact about any statement.

THE PRINTED SHAPE. All figures below are INVENTED, and are the same invented
figures `tests/test_welch_state_bank.py` uses; no amount, name, account
number, check number or date from any archive document appears in this
module, in that test file, or in W3 §WELCH:

    Account Number 1234567 Beginning Balance 1,000.00 Days in Statement
    Period 30 2 Deposits/Other Credits 500.00 3 Checks/Other Debits 250.00
    Ending Balance 1,250.00

One line, and it is the whole oracle: both COUNTS lead their labels, both
totals follow them, and `beginning + credits - debits = ending`. A negative
figure carries a TRAILING minus (`250.00-`), the mainframe convention.

THREE ROW GRAMMARS, and the columns are collapsed. This is a native PDF text
layer whose composition puts an entire section's rows onto ONE physical line
after its column head, breaking mid-section where it feels like it, and
interleaving two-up tables column-major. So:

1. THE LEDGER, under a `Deposits/Other Credits` or `Other Debits` banner and a
   `Date Description Amount` head. Field order is DESCRIPTION -> `mm/dd` ->
   AMOUNT: a leading-date row regex matches nothing here. Rows are read by
   anchoring on the `mm/dd amount` pair and taking the description as the text
   before it. Amounts are UNSIGNED — the direction comes from the banner.
2. `Checks Cleared`, `Listed in numerical order`: a two-column-pair table
   `Date Check Amount Date Check Amount` with SINGLE-DIGIT months, a `*` check
   suffix meaning gap-in-sequence, and a `(*) indicates gap in sequence`
   footer. Its rows are DEBITS and the printed debit count includes them; a
   reader that ignores this table is short one to five rows on most documents.
3. `Daily Ending Balance`: a three-column-pair `DATE BALANCE` grid, sometimes
   spilling under a `(continued)` repeat of its own banner. It prints the
   first day of the period and then only days that moved, so it is the bank's
   own dated evidence and `analysis/adb.py` forward-fills the rest.

`analysis/tables.dated_cells` — the shared reader for a flattened grid — is
deliberately NOT used, and the reason is the grammar rather than taste: it
opens a cell AT a date and closes it at the first value before the next date,
which is precisely the shape this template's dominant section does not have.
Here a cell CLOSES at its `date amount` pair and opens where the previous one
closed. The two date-leading grammars (the check table and the daily grid)
would fit it, but reading one template through two mechanisms would mean two
extents to reason about and two places to state the residue rule below, so all
three grammars are read by the one function that can express all three.
`tables.unique_match` IS used, for every term read once per document.

DESCRIPTIONS ARE LINE-SCOPED, which is this template's answer to DESC-ATTRIB.
A description is only ever the text between two anchors ON ONE LINE, so a row
can never inherit the tail of the row above it or of the page furniture
printed between two ledger lines — and this template prints plenty: a
reprinted page header, a mail-sort control token, a stray print flag. Measured
across the whole family: 211 ledger lines carry an anchor, and on every one of
them the line is consumed exactly — no residue after the last anchor, and no
anchor without a description in front of it.

WHAT THIS READER REFUSES. Every one of these is a refusal and none is a
repair (the batch-7 repair doctrine: a parser never writes an amount):

* a summary box that does not close, or that is printed twice with two
  different readings, or whose account number the masthead contradicts;
* a printed count this reader's rows do not match, per direction. This is the
  COMPLETE-COVERAGE oracle and it is what licenses ignoring a line inside a
  ledger region that holds no anchor: a dropped row is not silently dropped,
  it is a count that no longer matches and a document that refuses;
* a printed total this reader's rows do not sum to, per direction;
* a ledger or check amount printed with a minus. The banner already states the
  direction, so a signed figure is the document contradicting itself; no
  archive printing does it;
* a daily grid that does not replay: every grid day must be the period's first
  day or a day this reader posted to, its printed balance must equal the
  balance the replay reaches at the end of that day, the days must be distinct
  and inside the period, and the walk must land on the printed ending balance;
* a posting or grid date the printed period does not uniquely place
  (`iso_unique_in_period`), which also refuses `02/30` and a mangled token;
* a line inside a region that holds an anchor but is not wholly consumed by
  `description + anchor` pairs.

WHAT IT DOES NOT PUBLISH, deliberately:

* `account_name` carries the PRODUCT line — read positionally as the line
  immediately above the summary box, not as a memorized product string, so a
  Welch statement for another product still reads. The ACCOUNT HOLDER is not
  published: this template runs the holder's name and postal address together
  in one undelimited mailing block, and choosing where the name ends would be
  guessing rather than reading.
* `stated_service_charge` — the fee box prints `Total Overdraft Fees` and
  `Total Returned Item Fees` as two separate period/year-to-date pairs. Either
  one alone is not the period's service charge and adding them up asserts that
  the bank prints no third category, which no document here proves.
* `bank_reported_average_balance` — this template prints no average of its own.
* `stated_nsf_count` — the fee box prints fee AMOUNTS, never a count.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .date_tokens import iso_from_month_day_year, iso_unique_in_period
from .money import STRICT_EITHER_MINUS, STRICT_UNSIGNED, parse_amount
from .parser_registry import admissible_text, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import unique_match

#: A printed figure on this template: two decimals, an optional TRAILING minus.
#: Bounded on both sides so a reference number cannot supply the head of one
#: and a longer run cannot supply its tail.
_FIGURE = r"(?<![\d.,])\d[\d,]{0,15}\.\d{2}-?(?![\d,.])"

#: The masthead's branch contact ladder: a telephone number and the fax number
#: printed beside it, once per branch. Institution furniture — the bank's own
#: contact block — and STRUCTURAL: no number is written down here, only the
#: shape of the ladder and how many rungs it must have to count as one.
_LADDER_RE = re.compile(r"\d{3}-\d{3}-\d{4}\s+fax:\s*\d{3}-\d{3}-\d{4}", re.IGNORECASE)
_LADDER_MINIMUM_RUNGS = 3

#: The bank's home office, as the masthead prints it. The one place the
#: institution names itself on every printing of this template: the wordmark
#: appears only on the trailing check-image page, which not every statement
#: has. Institution furniture, in the class the wave rules admit alongside
#: routing numbers and contact domains.
_HOME_OFFICE_RE = re.compile(r"PO\s+Box\s+\d+\s+Welch,\s*OK", re.IGNORECASE)

#: The one-line summary box, read WHOLE. Reading it in seven searches would let
#: a document that prints two of them publish one term under another's
#: heading; read as one match, a second printing is a second match and
#: `tables.unique_match` refuses the disagreement.
_SUMMARY_RE = re.compile(
    rf"Account Number\s+(?P<account>\d[\d-]*)\s+"
    rf"Beginning Balance\s+(?P<beginning>{_FIGURE})\s+"
    rf"Days in Statement Period\s+(?P<days>\d{{1,3}})\s+"
    rf"(?P<credit_count>\d{{1,5}})\s+Deposits/Other Credits\s+(?P<credits>{_FIGURE})\s+"
    rf"(?P<debit_count>\d{{1,5}})\s+Checks/Other Debits\s+(?P<debits>{_FIGURE})\s+"
    rf"Ending Balance\s+(?P<ending>{_FIGURE})",
    re.IGNORECASE,
)
#: The masthead's own printing of the account number — a SECOND reading, which
#: must agree with the summary box's.
_MASTHEAD_ACCOUNT_RE = re.compile(r"^ACCOUNT NUMBER\s+(\d[\d-]*)\s*$", re.MULTILINE)
#: The printed period. Both endpoints carry the bank's own two-digit year, so
#: nothing here has to infer a century from the rows.
_PERIOD_RE = re.compile(
    r"^STATEMENT DATES\s+(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*$",
    re.MULTILINE,
)

_CREDIT_BANNER_RE = re.compile(r"^Deposits/Other Credits\s*$", re.IGNORECASE)
_DEBIT_BANNER_RE = re.compile(r"^Other Debits\s*$", re.IGNORECASE)
_CHECKS_BANNER_RE = re.compile(r"^Checks Cleared\s*$", re.IGNORECASE)
_GRID_BANNER_RE = re.compile(
    r"^Daily Ending Balance(?:\s*\(continued\))?\s*$", re.IGNORECASE
)
#: The check table's own footer, which closes it.
_CHECKS_FOOTER_RE = re.compile(r"^\(\*\)\s*indicates gap in sequence\s*$", re.IGNORECASE)

#: The column heads, which lead the first line of their region and are not
#: rows. Each may repeat on the line: the two- and three-up tables print their
#: head once per column pair.
_LEDGER_HEAD_RE = re.compile(r"^Date Description Amount\s*", re.IGNORECASE)
_CHECKS_HEAD_RE = re.compile(
    r"^(?:Listed in numerical order\s*)?(?:Date Check Amount\s*)+", re.IGNORECASE
)
_GRID_HEAD_RE = re.compile(r"^(?:DATE BALANCE\s*)+", re.IGNORECASE)

#: One ledger posting: `mm/dd` then the amount. The description is whatever
#: precedes it on the line, which is why this pattern is an ANCHOR rather than
#: a whole-row match.
_LEDGER_ANCHOR_RE = re.compile(
    rf"(?<![\d/])(?P<month>[0-9]{{1,2}})/(?P<day>[0-9]{{1,2}})\s+(?P<amount>{_FIGURE})"
)
#: One cleared check: date, check number with its optional gap marker, amount.
_CHECK_ANCHOR_RE = re.compile(
    rf"(?<![\d/])(?P<month>[0-9]{{1,2}})/(?P<day>[0-9]{{1,2}})\s+"
    rf"(?P<number>[0-9]{{1,10}})\*?\s+(?P<amount>{_FIGURE})"
)
#: One printed end-of-day balance.
_GRID_ANCHOR_RE = re.compile(
    rf"(?<![\d/])(?P<month>[0-9]{{1,2}})/(?P<day>[0-9]{{1,2}})\s+(?P<balance>{_FIGURE})"
)

WELCH_DETECTION_MARKERS = (
    # The institution, by the only furniture every printing carries.
    required("issuer_home_office_po_box", lambda t: _HOME_OFFICE_RE.search(t) is not None),
    # The masthead's multi-branch contact ladder — structural, no number in it.
    required(
        "branch_contact_ladder",
        lambda t: len(_LADDER_RE.findall(t)) >= _LADDER_MINIMUM_RUNGS,
    ),
    # The summary box with its LEADING counts. Required at DETECTION and not
    # merely at parse, because it is this reader's whole oracle: a printing
    # without it is one whose rows this reader cannot prove complete, and
    # claiming it would strand a document another reader could take.
    required("summary_counts_grammar", lambda t: _SUMMARY_RE.search(t) is not None),
)

#: Named `detect` because this module holds exactly one reader, which is the
#: convention `tests/test_parser_registry_entries.py` checks a registration
#: against its module by.
detect = make_detector(WELCH_DETECTION_MARKERS)


def _cents(token: str, *, signed: bool) -> int | None:
    """A printed figure as whole cents, or None if it is not one.

    `signed` selects the trailing-minus mainframe convention, which the
    summary box and the daily grid use and the ledger never does.
    """
    amount = parse_amount(token, STRICT_EITHER_MINUS if signed else STRICT_UNSIGNED)
    if amount is None:
        return None
    return int(round(amount * 100))


@dataclass(frozen=True)
class _Summary:
    account: str
    days: int
    beginning: int
    ending: int
    credits: int
    debits: int
    credit_count: int
    debit_count: int


def _read_summary(source: str) -> _Summary | None:
    """The printed summary box, or None if it is absent, doubled or does not
    close. The fail-fast: a mis-read summary is rejected before a row is read."""
    match = unique_match(source, _SUMMARY_RE)
    if match is None:
        return None
    figures = {}
    for name in ("beginning", "ending", "credits", "debits"):
        value = _cents(match.group(name), signed=True)
        if value is None:
            return None
        figures[name] = value
    if figures["beginning"] + figures["credits"] - figures["debits"] != figures["ending"]:
        return None
    # The masthead's independent printing of the account number. A document
    # that prints two different accounts is not one this reader will guess
    # between; a masthead printed twice and disagreeing refuses through
    # `unique_match` for the same reason.
    masthead = unique_match(source, _MASTHEAD_ACCOUNT_RE)
    if masthead is None or masthead.group(1) != match.group("account"):
        return None
    return _Summary(
        account=match.group("account"),
        days=int(match.group("days")),
        beginning=figures["beginning"],
        ending=figures["ending"],
        credits=figures["credits"],
        debits=figures["debits"],
        credit_count=int(match.group("credit_count")),
        debit_count=int(match.group("debit_count")),
    )


def _read_period(source: str) -> tuple[date, date] | None:
    """The printed statement period, or None if it is absent or contradicted."""
    match = unique_match(source, _PERIOD_RE)
    if match is None:
        return None
    try:
        start = date.fromisoformat(iso_from_month_day_year(match.group(1)))
        end = date.fromisoformat(iso_from_month_day_year(match.group(2)))
    except ValueError:
        # `iso_from_month_day_year` raises for a token no calendar can hold.
        return None
    if end < start:
        return None
    return start, end


def _product_line(source: str) -> str | None:
    """The product this statement is for, read POSITIONALLY.

    This template prints the product on its own line immediately above the
    summary box. Reading it by position rather than by a memorized product
    name is what lets a Welch statement for some other product still publish
    its own product; a line that carries a digit is not a product line and is
    declined rather than published as one, because the line above the summary
    box is the page header on a printing this reader has not seen.
    """
    summary = unique_match(source, _SUMMARY_RE)
    if summary is None:
        return None
    lines = source.splitlines()
    for index in range(source[: summary.start()].count("\n") - 1, -1, -1):
        candidate = lines[index].strip()
        if not candidate:
            continue
        if any(character.isdigit() for character in candidate):
            return None
        return re.sub(r"\s+", " ", candidate) if len(candidate) <= 60 else None
    return None


@dataclass(frozen=True)
class _Posting:
    iso: str
    description: str
    cents: int
    credit: bool


def _consume(
    line: str, anchor: re.Pattern[str], *, described: bool
) -> list[tuple[str, re.Match[str]]] | None:
    """`(text before anchor, anchor)` for every anchor on `line`, or None.

    The whole-line rule, which is what keeps a description attached to its own
    posting. A line holding at least one anchor must be consumed EXACTLY, and
    what "exactly" means differs by grammar:

    * `described=True` — the LEDGER, whose rows print a description column.
      Every anchor must be preceded on this line by non-empty text, and that
      text is the row's description. Nothing may be left after the last
      anchor. Because the text can only come from between two anchors of the
      SAME line, a row can never inherit the tail of the row above it, nor the
      page furniture this template prints between two ledger lines.
    * `described=False` — the two-up check table and the three-up daily grid,
      which have no description column. Nothing at all may sit between two
      anchors or after the last one, so a figure that is not part of a printed
      pair refuses the document instead of being absorbed into a neighbour.

    A line holding no anchor is page furniture — a reprinted header, a
    mail-sort control token, a stray print flag — and returns an empty list.
    The printed counts are what prove no posting was lost that way.
    """
    spans = list(anchor.finditer(line))
    if not spans:
        return []
    consumed: list[tuple[str, re.Match[str]]] = []
    cursor = 0
    for span in spans:
        before = line[cursor : span.start()].strip()
        if described and not before:
            return None
        if not described and before:
            return None
        consumed.append((re.sub(r"\s+", " ", before), span))
        cursor = span.end()
    if line[cursor:].strip():
        return None
    return consumed


def _read_regions(
    source: str, *, period_start: date, period_end: date
) -> tuple[list[_Posting], list[tuple[str, int]]] | None:
    """Every posting and every printed end-of-day balance, or None.

    One pass, one state machine: a banner opens its region and the next banner
    closes the previous one, so the order the template prints its sections in
    is read off the document rather than assumed.
    """
    postings: list[_Posting] = []
    snapshots: list[tuple[str, int]] = []
    region: str | None = None

    for raw in source.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _CREDIT_BANNER_RE.match(line):
            region = "credit"
            continue
        if _DEBIT_BANNER_RE.match(line):
            region = "debit"
            continue
        if _CHECKS_BANNER_RE.match(line):
            region = "checks"
            continue
        if _GRID_BANNER_RE.match(line):
            region = "grid"
            continue
        if region is None:
            continue
        if region == "checks" and _CHECKS_FOOTER_RE.match(line):
            region = None
            continue

        if region in ("credit", "debit"):
            body = _LEDGER_HEAD_RE.sub("", line, count=1)
            consumed = _consume(body, _LEDGER_ANCHOR_RE, described=True)
            if consumed is None:
                return None
            for description, span in consumed:
                iso = _posting_date(span, period_start, period_end)
                cents = _cents(span.group("amount"), signed=False)
                if iso is None or cents is None:
                    return None
                postings.append(
                    _Posting(iso, description, cents, credit=region == "credit")
                )
        elif region == "checks":
            body = _CHECKS_HEAD_RE.sub("", line, count=1)
            consumed = _consume(body, _CHECK_ANCHOR_RE, described=False)
            if consumed is None:
                return None
            for _before, span in consumed:
                iso = _posting_date(span, period_start, period_end)
                cents = _cents(span.group("amount"), signed=False)
                if iso is None or cents is None:
                    return None
                postings.append(
                    _Posting(iso, f"Check {span.group('number')}", cents, credit=False)
                )
        else:
            body = _GRID_HEAD_RE.sub("", line, count=1)
            consumed = _consume(body, _GRID_ANCHOR_RE, described=False)
            if consumed is None:
                # A grid line this reader cannot read whole is a grid whose
                # extent is unknown, and the ADB is computed off this grid.
                return None
            for _before, span in consumed:
                iso = _posting_date(span, period_start, period_end)
                cents = _cents(span.group("balance"), signed=True)
                if iso is None or cents is None:
                    return None
                snapshots.append((iso, cents))
    return postings, snapshots


def _posting_date(
    span: re.Match[str], period_start: date, period_end: date
) -> str | None:
    """The one date inside the printed period this `mm/dd` token can mean.

    Rows print no year. `iso_unique_in_period` decides it from the period and
    refuses where the period does not decide uniquely — which also refuses a
    token of the right shape that no calendar holds (`02/30`) and a day this
    statement's period does not contain.

    `int()` here is TOTAL, and the anchors above are why: their date groups
    spell `[0-9]` rather than using the shorthand digit class, which matches
    every Unicode decimal digit. A decorative or mis-mapped glyph that happened
    to land in that category would otherwise be converted into a day rather
    than noticed. Spelled out, such a token is not a date ANCHOR at all: its
    row never parses, the printed count no longer matches, and the document
    refuses — the stronger answer, because a conversion guard here could only
    ever drop the row silently.
    """
    return iso_unique_in_period(
        int(span.group("month")), int(span.group("day")),
        start=period_start, end=period_end,
    )


def _grid_replays(
    snapshots: list[tuple[str, int]],
    postings: list[_Posting],
    *,
    summary: _Summary,
    period_start: date,
) -> bool:
    """Whether the bank's printed daily grid agrees with the parsed ledger.

    The fourth oracle, and the only one that can see a MISDATED row: the count
    and total gates and the closing identity are all indifferent to which day a
    posting sat on, and the ADB is not.
    """
    if not snapshots:
        return False
    days = [iso for iso, _balance in snapshots]
    if len(set(days)) != len(days):
        return False
    moved: dict[str, int] = {}
    for posting in postings:
        moved[posting.iso] = moved.get(posting.iso, 0) + (
            posting.cents if posting.credit else -posting.cents
        )
    opening = period_start.isoformat()
    # Every day the account moved must be printed, and every printed day must
    # be one that moved or the period's first day. Either direction failing is
    # a grid that is not a complete record of this ledger.
    if set(days) != set(moved) | {opening}:
        return False
    balance = summary.beginning
    for iso, printed in sorted(snapshots):
        balance += moved.get(iso, 0)
        if balance != printed:
            return False
    return balance == summary.ending


def parse_welch_state_bank_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    source = admissible_text(markdown)

    summary = _read_summary(source)
    period = _read_period(source)
    if summary is None or period is None:
        return None
    period_start, period_end = period

    regions = _read_regions(source, period_start=period_start, period_end=period_end)
    if regions is None:
        return None
    postings, snapshots = regions
    if not postings:
        return None

    credits = [p for p in postings if p.credit]
    debits = [p for p in postings if not p.credit]
    # The bank's own two counts and two totals, against the four figures this
    # reader produced. The counts are the COMPLETE-COVERAGE oracle: this
    # template prints no running balance on a ledger row, so nothing else here
    # would notice a posting that never parsed.
    if len(credits) != summary.credit_count or len(debits) != summary.debit_count:
        return None
    if sum(p.cents for p in credits) != summary.credits:
        return None
    if sum(p.cents for p in debits) != summary.debits:
        return None
    if not _grid_replays(
        snapshots, postings, summary=summary, period_start=period_start
    ):
        return None

    stmt = Statement(
        bank="Welch State Bank",
        account_name=_product_line(source),
        account_number=summary.account,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        beginning_balance=round(summary.beginning / 100, 2),
        ending_balance=round(summary.ending / 100, 2),
        # CURRENCY_DOCTRINE §B, `institution_default`. No `USD`, no `CAD` and
        # no other currency token is printed anywhere on this template; the
        # only glyph is a bare `$` on the check-image page, which the doctrine
        # says is not evidence of a denomination. What IS evidence is the
        # institution: a home office and five branch PO boxes in Oklahoma
        # behind a single U.S. area code. That is an assertion FROM IDENTITY
        # and not a reading, so it is filed in the class that owes evidence
        # rather than dressed up as one that has it. The value equals the
        # schema default, so nothing moves financially either way; what moves
        # is that the payload now says where it came from.
        currency="USD",
        currency_source="institution_default",
        days_in_period=summary.days,
        stated_total_credits=round(summary.credits / 100, 2),
        stated_total_debits=round(summary.debits / 100, 2),
        stated_credit_count=summary.credit_count,
        stated_debit_count=summary.debit_count,
    )
    stmt.stated_daily_balances = [
        StatementDailyBalance(date=iso, balance=round(cents / 100, 2))
        for iso, cents in sorted(snapshots)
    ]
    stmt.transactions = [
        Transaction(
            date=posting.iso,
            description=posting.description,
            amount=round((posting.cents if posting.credit else -posting.cents) / 100, 2),
            direction="credit" if posting.credit else "debit",
        )
        for posting in sorted(postings, key=lambda p: p.iso)
    ]
    return stmt
