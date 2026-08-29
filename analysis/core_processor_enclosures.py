"""A FOURTH core processor's template: the enclosures / average-ledger block.

The batch-8 census ranked this the largest unclaimed printed identity in the
archive (`CENSUS_BATCH8_DIGITAL.md` rank 1, 58 documents), and it is the next
grammar of the core-processor complex after §LCPERIOD (`core_processor_daily`),
§GRAM4 (`core_processor_counted`) and §JHA/§SCANB (`core_processor_sectioned`).
Like all of those it is registered on the TEMPLATE's own furniture, because the
institution is not in the text layer of most members: the archive prints this
one under roughly thirty small-bank mastheads, and three of them — the issuers
`burke_herbert`, `farmers_merchants` and `linkbank` already read — are the only
ones that print anything a reader could take an issuer's name from. Those three
registrations supersede this one, exactly as `first_farmers` supersedes
`core_processor_sectioned`.

The template
------------
One printed line carries the whole summary — the flattened text layer welds the
platform's two columns into it, left cell then right cell, in this order::

    <product>  Number of Enclosures N   Account Number <number>
    Statement Dates m/dd/yy thru m/dd/yy
    Previous Balance <fig>      Days in the statement period N
    <n> Deposits/Credits <fig>  Average Ledger <fig>
    <m> Checks/Debits <fig>     Average Collected <fig>
    Service Charge <fig>
    Interest Paid <fig>
    Ending Balance <fig>

then an ASCII pipe box of `Total For This Period | Total Year-to-Date` fee
counters, then the ledger as named blocks, and on most members a three-up
`Date Balance` grid of end-of-day balances.

**The strip is one printed line, on all 54 addressable archive members, and the
closing-balance label occurs exactly once in the whole document (measured, both
54/54).** That is what makes the region cheap and safe to bound: the same
labels are printed again in the fee box, in a fee-detail section and in the
back-of-statement disclosures, and a read that ran past the line would find
them.

Label drift is the rule rather than the exception, so every label below is a
short alternation of what the archive prints and nothing else — `Previous
Balance` / `Balance Last Statement`; `Ending` / `Current` / `Balance This
Statement`; `Service Charge` / `Service Fee` / `Maintenance Charge`;
`Average Ledger` / `Average Ledger Bal.` / `Average Ledger Balance`;
`Days in the` / `Days This` statement period. Case drifts too — the same
template prints the strip in title case under one masthead and in capitals
under another — so this module's summary patterns are case-insensitive, which
is the opposite of `core_processor_counted`'s rule and for the opposite
reason: there case separates two grammars of ONE processor, here it separates
nothing at all.

What the document has to prove before anything is published
-----------------------------------------------------------
1. **the summary's own identity**: `previous + credits - debits - service
   charge + interest == ending`. This template prints the service charge and
   the interest OUTSIDE its two direction totals, which is what makes the
   identity a fifth independent reading rather than a restatement of the
   fourth;
2. **the credit count**, and **the credit total**;
3. **the debit count**, and **the debit total**;
4. **the daily-balance grid**, where the template prints one: every day it
   prints equals the walked end-of-day balance, and every day the ledger posts
   on appears in it.

A document that cannot satisfy all of them publishes nothing. Where the grid
is not printed the first three still are, and the ledger they close is what
`analysis/adb.py` reconstructs the calendar-day series from; the reader
publishes and the ADB doctrine decides, exactly as `core_processor_sectioned`
does for the same absence.

The printed counts EXCLUDE two rows this ledger nonetheless posts
-----------------------------------------------------------------
Measured by `tools/coreenc_count_scope.py` over the 48 members this reader
publishes — the whole MEASURABLE population, because a document that declines
captures no rows to count: on every document whose captured credit rows
outnumber the printed credit count, they outnumber it by exactly one and the
excess is exactly the printed `Interest Paid` figure (5 documents, which are
every one that prints an interest credit at all); on every document whose debit
rows outnumber the printed debit count, the excess is exactly the printed
service charge (19 documents, two of them posting it as two rows — again every
one that prints a service charge at all). The bank prints `N Deposits/Credits`
about its deposit categories and bills its own interest and its own fee on
separate summary lines; both postings are real and are published, and the
count gate is stated in the scope the bank counts in. That is the third class
`analysis/count_semantics.py` describes, which is why this parser is left at
the table's default (`UNSURVEYED`, incomparable) and says so in
`SECTION_LEVEL_ORACLES` rather than declaring half an adjustment: the mapping
schema can express `+1 when a service charge was billed` and has no field for
`+1 when interest was credited`, and declaring only the half it can express
would manufacture a flag on every interest-bearing member.

The blocks, and why the banner rather than the sign decides direction
----------------------------------------------------------------------
The template names each block and repaints the name on every page, so
`tables.section_runs` over the banner alternation is the split. The banner is
also what says which direction the block's rows post in — never the sign of
the amount, which this platform prints inconsistently: measured over the 48
published by `tools/coreenc_archive_census.py signs`, the debit blocks print
3,730 rows with a trailing minus and 372 without (the collapsed cheque grids
print magnitudes), while the credit blocks print 736 without a sign and NONE
with. A reader keyed on the sign books 372 debits as deposits. Only the date-order issue, which prints
one undivided ledger under `ACTIVITY IN DATE ORDER` / `Transaction Activity`,
has no column to read, and there the printed sign is the only evidence there
is.

**A block the platform calls a SUMMARY is a restatement exactly when the ledger
prints a running balance.** The archive splits perfectly on that printing: of
the twelve members carrying a `Summary by Check Number` / `Summary of Deposits`
/ `Summary of Withdrawals` block, the eight whose ledger header names a
`Balance` column restate rows the ledger already posted, and the four whose
header does not (`Date Description Amount`) print cheques that appear nowhere
else. Reading a summary as postings on the first eight double-counts; skipping
it on the last four loses the whole cheque side. The header is the platform's
own statement about which of the two it is: a ledger that prints a balance
after every row is a ledger that carries every row.

The fee-detail block (`Service Charges and Itemized Fees`, `Service Charge
Detail`) is read as a BLOCK and published as no rows at all: it itemizes the
one `Total Service Charge` posting the debit ledger already carries, and
publishing both would post the fee twice.

Two printed tokens that open no row, and the gate that proves both calls
-------------------------------------------------------------------------
* **the cross-reference cheque row.** One issuer's cheque grid prints
  `date serial -See above-` for an item detailed in the ledger above instead of
  repeating its amount. That is a printed pointer, not a second posting, and it
  is skipped — a decision the count gate then proves on all four members that
  carry one, because a wrong call there moves a count;
* **a date with ANOTHER DATE between it and the next figure.** A row here is a
  date and the first figure printed before the next date opens, so a token of
  that shape opens nothing: the row it would open is closed by a row that
  starts later. Six members print one, and neither printing is the bank's —
  three weld a wrapped description across the date column so the layer emits
  the row's own date twice with a fragment of its description between, and
  three carry a `mm/dd` inside a merchant's printed name (a card statement's
  `Member <mm>/<dd>` renewal note). `_without_non_opening_dates` blanks the
  token, leaving every other character where it stood.

  An earlier form of this module declined all six instead (W3 §COREENC), on
  the ground that dropping a row is how a ledger comes to disagree with a
  printed total while still looking complete. That ground is what the change
  rests on rather than against: this template gates BOTH printed counts, BOTH
  printed totals and — where it is printed — the daily-balance grid, so a
  blanked token that really was a row leaves the ledger short of the bank's own
  count and its total short by that row's amount, and the document declines at
  `_matches_the_printed_summary` instead. Measured on all six: after the
  blanking both counts land inside the interest/fee allowance, both totals
  close to the cent, and the printed grid — an independent second printing of
  the same period — agrees on every day (W3 §CPDECL).

  **What the rule costs is a description, never a day and never a figure.**
  It always blanks the token that closes no cell, never the one that does, so
  a row keeps the day of the date that actually opens it — which is what stops
  a merchant's `Member <mm>/<dd>` from dating a posting. Text printed before
  the surviving date is then not in the row's span and is not published, so a
  description can come out shorter than the bank printed it. It is bounded to a
  token with another date AFTER it in the same run: a run that simply stops
  mid-row is what a truncated page looks like, and there the refusal stands.

The issuer, and the currency
-----------------------------
`Statement.bank` is None on every document this reader publishes, under the
honest-unknown-issuer ruling of 2026-08-14. No arrangement here bounds an
institution name on both sides: what the page prints above the holder's address
is a PO box, a phone ladder and, on a minority, a sentence of marketing prose
naming the bank in the middle of it. A name read out of prose is a guess, and a
wrong name is worse than no name.

`Statement.currency` is left at the schema default. Measured over all 58
members of the census family: zero occurrences of `CAD`, `USD`, any Canadian
province, postal pattern or `Transit`. The evidence that these are US accounts
is a bare `$`, a `Member FDIC` footer on ten of them and US mailing addresses —
furniture, not a printed denomination — so under
`docs/moneythumb-replacement/CURRENCY_DOCTRINE.md` this reader publishes the
default and names itself, here, as a future mover if a US jurisdiction-default
packet is ever approved. It does not claim `jurisdiction_default` today: that
class is for affirmative evidence, and a PO box is not one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .date_tokens import iso_from_month_day_year, iso_within_period
from .money import (
    EITHER_MINUS_PADDED, MINUS_CLASS, STRICT_UNSIGNED, pad_leading_decimal,
    parse_amount,
)
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import attributed_descriptions, dated_cells, section_runs, unique_match

# ---------------------------------------------------------------------------
# The grammar
# ---------------------------------------------------------------------------

#: A token may not begin part-way through another token, and may not be
#: continued by one. `/` and `.` and `,` are inside the classes so a date
#: cannot start inside a longer date and a figure cannot start inside a longer
#: number; the `-` is there because this template's ledger welds a sign to the
#: figure on either side and a reference number to a description with a hyphen.
_TOKEN_START = r"(?<![\w.,/-])"
_DATE_END = r"(?![\w/-])"
_FIGURE_END = r"(?![\w.,])"

#: `1,234.56`, and the bare `.56` this platform prints for every sub-dollar
#: figure including the `.00` its zero fees are printed as.
_MONEY = r"(?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2})"

#: `m/dd/yy` — the notation the period sentence is printed in, on all 54.
_PERIOD_DATE = r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{2}"

#: `m/d`, the form every ledger and grid row prints, as CALENDAR RANGES rather
#: than digit runs (§GRAM4's law). The year is not printed on a row and is
#: resolved against the statement period, which is the only evidence of one.
_ROW_DATE = r"(?:1[0-2]|0?[1-9])/(?:3[01]|[12][0-9]|0?[1-9])"

#: A SUMMARY figure. The strip's sign is a right-aligned COLUMN rather than a
#: mark welded to the figure: three members print an overdrawn balance as
#: `<figure> -`, with the space, and four print it welded. The gap is bounded
#: at two spaces because that is what the archive prints, and the sign is a
#: separate group because no shared `AmountFormat` both admits an interior
#: space and pads a bare `.00` — the magnitude is still read by the shared
#: engine, and only the template's own sign column is applied here.
_SUMMARY_FIGURE = (_TOKEN_START + r"\$?(" + _MONEY + r")" + _FIGURE_END
                   + r"(?:[ ]{0,2}(" + MINUS_CLASS + r"))?")

#: A LEDGER figure: the sign is welded to the figure, on either side. Both are
#: printed — `<figure>-` in the sectioned issue's debit blocks and `-<figure>`
#: in the one issue that prints the amount before its description — and
#: neither carries a space, so this token admits none. Without that bound the OCR
#: layer's own `--- Page N ---` separator reads as a signed figure: measured,
#: it stands two spaces after a figure 117 times in this family and is never a
#: sign.
_LEDGER_FIGURE = (_TOKEN_START + r"(" + MINUS_CLASS + r"?\$?" + _MONEY
                  + MINUS_CLASS + r"?)" + _FIGURE_END)

_DATE_RE = re.compile(_TOKEN_START + r"(" + _ROW_DATE + r")" + _DATE_END)
_LEDGER_FIGURE_RE = re.compile(_LEDGER_FIGURE)


def _ledger_amount(token: str) -> float | None:
    """A printed ledger figure as a signed number, or None if it is not one."""
    return parse_amount(token, EITHER_MINUS_PADDED)


def _summary_amount(match: re.Match[str], group: int) -> float | None:
    """A printed summary figure as a signed number, or None.

    `group` is the offset of the magnitude inside the match; the sign column
    is the group after it. The magnitude goes through the shared engine, and
    the only thing done here is applying the sign the strip printed beside it.
    """
    amount = parse_amount(pad_leading_decimal(match.group(group)), STRICT_UNSIGNED)
    if amount is None:
        return None
    return -amount if match.group(group + 1) else amount


# ---------------------------------------------------------------------------
# Detection: the template's own furniture, and nothing about an issuer
# ---------------------------------------------------------------------------

#: The period sentence. On its own it reaches 79 of the archive's 3,380
#: documents and eight printed identities; it is a claim about this archive
#: rather than about the template, which is why it is composed rather than
#: registered alone (R4-3, and the two-required-marker invariant in
#: `tests/test_parser_conformance.py`).
_PERIOD_RE = re.compile(
    r"STATEMENT DATES\s+(" + _PERIOD_DATE + r")\s+THRU\s+(" + _PERIOD_DATE + r")")

#: The words the template heads its two direction rows with. Short, closed, and
#: the template's own: the count row is `<n> Deposits/Credits`, `<n> Deposits`
#: or `<n> Credits` on the credit side and `<m> Checks/Debits`, `<m> Debits` or
#: `<m> Checks/Charges` on the debit side, over the 54 addressable members.
_CREDIT_WORDS = r"(?:DEPOSITS?/CREDITS?|DEPOSITS?|CREDITS?)"
_DEBIT_WORDS = r"(?:CHECKS?/DEBITS?|CHECKS?/CHARGES?|CHECKS?|DEBITS?)"

#: **The second required marker, and the one that makes this a template rather
#: than a phrase.** The platform's two-column block prints its credit count row
#: in the left cell and its ledger-average statistic in the right cell of the
#: SAME printed line, and the flattened layer welds them into
#: `<n> Deposits/Credits <total> Average Ledger <figure>`. Measured over the
#: whole archive, the conjunction of this and the period sentence reaches 67
#: documents — the 54 addressable members of the census family, the ten this
#: platform prints under the three mastheads that already have their own
#: readers, and three scanned printings of the same block. Nothing else in
#: 3,380 documents.
#:
#: The count is optional here and required by the summary read below, because
#: one scanned member prints `Deposits/Credits .00 Average Ledger` with the
#: count suppressed on a zero direction. Registering on the pairing rather than
#: on `Average Ledger` alone is what refuses the three-count summary of a
#: DIFFERENT issue of the same processor (census rank 62), which prints its
#: WITHDRAWALS row in that cell.
_LEDGER_STATISTIC_RE = re.compile(
    r"(?<![0-9])(?:[0-9]{1,4}\s+)?" + _CREDIT_WORDS + r"\s+\$?" + _MONEY
    + r"[\s|]*AVERAGE LEDGER")

#: The platform's own period statistic. Coextensive with the pair above on this
#: archive, so it corroborates rather than gates: an issuer that suppresses the
#: statistic still prints the template.
_PERIOD_DAYS = r"DAYS\s+(?:IN\s+TH(?:E|IS)|THIS)\s+STATEMENT PERIOD"
_PERIOD_DAYS_RE = re.compile(_PERIOD_DAYS + r"\s+(?<![0-9])([0-9]{1,3})(?![0-9])")


def detection_text(markdown: str) -> str:
    """This registration's normalization, held as registry data so the
    upper-casing runs once per document rather than once per marker
    (§JHA J11.3). Case is not load-bearing anywhere in this template: the same
    printed block arrives in title case under one masthead and in capitals
    under another."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("platform_statement_dates", lambda t: bool(_PERIOD_RE.search(t))),
    required("platform_ledger_average_cell",
             lambda t: bool(_LEDGER_STATISTIC_RE.search(t))),
    corroborating("platform_period_days",
                  lambda t: bool(_PERIOD_DAYS_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


# ---------------------------------------------------------------------------
# The printed summary strip
# ---------------------------------------------------------------------------

_I = re.IGNORECASE

_STRIP_PERIOD_RE = re.compile(
    r"STATEMENT DATES\s+(" + _PERIOD_DATE + r")\s+THRU\s+(" + _PERIOD_DATE + r")", _I)
_PREVIOUS_RE = re.compile(
    r"(?:PREVIOUS BALANCE|BALANCE LAST STATEMENT)\s+" + _SUMMARY_FIGURE, _I)
_DAYS_RE = re.compile(_PERIOD_DAYS + r"\s+(?<![0-9])([0-9]{1,3})(?![0-9])", _I)
_CREDITS_RE = re.compile(
    r"(?<![0-9])([0-9]{1,4})\s+" + _CREDIT_WORDS + r"\s+" + _SUMMARY_FIGURE, _I)
_DEBITS_RE = re.compile(
    r"(?<![0-9])([0-9]{1,4})\s+" + _DEBIT_WORDS + r"\s+" + _SUMMARY_FIGURE, _I)
#: `Monthly Service Fee` is spelt out so the alternation cannot end a label
#: half-way and read the same figure under a name the bank did not print.
_SERVICE_RE = re.compile(
    r"(?:MONTHLY SERVICE FEE|SERVICE CHARGE|SERVICE FEE|MAINTENANCE CHARGE)\s+"
    + _SUMMARY_FIGURE, _I)
_INTEREST_RE = re.compile(r"INTEREST PAID\s+" + _SUMMARY_FIGURE, _I)
_CLOSING_RE = re.compile(
    r"(?:ENDING BALANCE|CURRENT BALANCE|BALANCE THIS STATEMENT)\s+"
    + _SUMMARY_FIGURE, _I)
#: The period's ledger average, published as the BANK-REPORTED average —
#: evidence, never the platform's ADB, which `analysis/adb.py` computes on the
#: canonical calendar-day basis. It gates nothing, which is what leaves it free
#: to be an independent opinion, and it is OPTIONAL because two members' text
#: layers drop its cents (`Average Ledger 422`) while every gated figure on the
#: same line keeps them.
_AVERAGE_RE = re.compile(
    r"AVERAGE LEDGER(?:\s+BAL(?:ANCE)?\.?)?\s+" + _SUMMARY_FIGURE, _I)
#: The account field, inside the strip. The number is printed bare, masked with
#: `X`, or introduced by the platform's own `Acct. Ending` / `Ending` marker.
_ACCOUNT_RE = re.compile(
    r"ACCOUNT NUMBER\s+(?:ACCT\.?\s+ENDING\s+|ENDING\s+)?([Xx*0-9]{4,})(?![0-9])", _I)
#: What the platform prints between the product name and the account field. The
#: product name is everything the strip opens with before it, and this is its
#: right-hand bound — the template's, not a guess about how long a name is.
_PRODUCT_END_RE = re.compile(
    r"\s*(?:NUMBER OF (?:ENCLOSURES|IMAGES)|ACCT\.?\s+ENCLOSURES|ENCLOSURES"
    r"|ACCOUNT NUMBER)", _I)
#: A product name this template could plausibly print. The bound keeps a page
#: of welded furniture out of the slot on a member whose strip opens with
#: something else; the longest name the archive prints in it is 27 characters.
_PRODUCT_NAME_LIMIT = 60


@dataclass(frozen=True)
class _Summary:
    """Every figure the printed strip carries."""

    account: str
    product: str | None
    start: str
    end: str
    days: int
    previous: float
    closing: float
    credit_count: int
    credits: float
    debit_count: int
    debits: float
    service_charge: float
    interest: float
    average: float | None


def _strip(markdown: str) -> str | None:
    """The summary strip: the printed LINE the period sentence sits on, cut at
    the closing balance that ends it.

    Both bounds are the template's own. The line is the bound because this
    platform emits the whole two-column block as one run of text; the closing
    balance is the bound because an interest-bearing member prints its
    year-to-date interest AFTER it, on the same line, under the same label as
    the period's own.
    """
    period = unique_match(markdown, _STRIP_PERIOD_RE)
    if period is None:
        return None
    opens = markdown.rfind("\n", 0, period.start()) + 1
    closes = markdown.find("\n", period.end())
    line = markdown[opens: closes if closes >= 0 else len(markdown)]
    closing = unique_match(line, _CLOSING_RE)
    return line[: closing.end()] if closing else None


def _product_name(strip: str) -> str | None:
    """The product name the strip opens with, or None.

    A line that is one token sequence REPEATED is declined rather than
    collapsed: this processor's text layer emits a printed string up to four
    times over — fill, stroke and two shadows — and publishing the repetition
    publishes a name no statement carries, while collapsing it is a repair
    (§GRAM4's rule, and its reason).
    """
    bound = _PRODUCT_END_RE.search(strip)
    if bound is None:
        return None
    printed = re.sub(r"\s+", " ", strip[: bound.start()]).strip()
    words = printed.split()
    if not words or not printed[:1].isalpha() or len(printed) > _PRODUCT_NAME_LIMIT:
        return None
    if any(len(words) % size == 0 and words == words[:size] * (len(words) // size)
           for size in range(1, len(words) // 2 + 1)):
        return None
    return printed


def _period(printed_start: str, printed_end: str) -> tuple[str, str] | None:
    """The printed period as two ISO dates, or None if it is not a period.

    The pattern proves the SHAPE of a date and nothing more — a thirteenth
    month has that shape and is not a day — and a raise inside `parse` is
    recorded as a crash of ours rather than as the decline it should be
    (`parser_registry.ParserFailure`), so it is caught here.
    """
    try:
        return (iso_from_month_day_year(printed_start),
                iso_from_month_day_year(printed_end))
    except ValueError:
        return None


def _summary(markdown: str) -> _Summary | None:
    """Every figure the strip prints, or None if any one of them is missing.

    All or nothing: every gate below compares the ledger against these
    figures, so a partly-read strip would weaken the gates instead of failing
    them. `unique_match` throughout, because a strip that prints a row twice
    with two different figures is the document contradicting itself about its
    own summary and there is no rule that says which printing to believe.
    """
    strip = _strip(markdown)
    if strip is None:
        return None
    period = unique_match(strip, _STRIP_PERIOD_RE)
    account = unique_match(strip, _ACCOUNT_RE)
    previous = unique_match(strip, _PREVIOUS_RE)
    days = unique_match(strip, _DAYS_RE)
    credits_ = unique_match(strip, _CREDITS_RE)
    debits = unique_match(strip, _DEBITS_RE)
    service = unique_match(strip, _SERVICE_RE)
    interest = unique_match(strip, _INTEREST_RE)
    closing = unique_match(strip, _CLOSING_RE)
    if None in (period, account, previous, days, credits_, debits,
                service, interest, closing):
        return None

    printed_period = _period(period.group(1), period.group(2))
    if printed_period is None:
        return None
    figures = {
        "previous": _summary_amount(previous, 1),
        "closing": _summary_amount(closing, 1),
        "credits": _summary_amount(credits_, 2),
        "debits": _summary_amount(debits, 2),
        "service_charge": _summary_amount(service, 1),
        "interest": _summary_amount(interest, 1),
    }
    if any(value is None for value in figures.values()):
        return None
    average = unique_match(strip, _AVERAGE_RE)
    return _Summary(
        account=account.group(1),
        product=_product_name(strip),
        start=printed_period[0],
        end=printed_period[1],
        days=int(days.group(1)),
        credit_count=int(credits_.group(1)),
        debit_count=int(debits.group(1)),
        average=_summary_amount(average, 1) if average else None,
        **figures,
    )


# ---------------------------------------------------------------------------
# The ledger's blocks
# ---------------------------------------------------------------------------

#: What the platform prints as a block's column header, immediately under its
#: banner and again on every page the block runs onto.
_COLUMN_HEADER = (r"(?:DATE(?:\s+TRANSACTION)?\s+"
                  r"(?:DESCRIPTION|CHECK|BALANCE|AMOUNT|NO\.?|NUMBER)"
                  r"|REFERENCE\s+DATE\s+AMOUNT)")

#: The banner each block is printed under, and the role the banner declares.
#: This is the TEMPLATE's vocabulary — every phrase here is a heading this
#: platform prints, mined from the archive's own pages — and not a list of
#: banks, merchants or products. Order matters: the longest phrase that opens
#: at a position wins, so `Deposits and Other Credits` cannot be read as the
#: bare `Credits` banner of the issue below it.
#:
#: The bare `CREDITS` / `DEBITS` banners are the one pair that needs an anchor.
#: Both words are ordinary prose on a bank statement — they stand 137 and 271
#: times in this family outside a banner position — so they are a banner only
#: where the platform repaints its column header directly after them, which is
#: what a banner does and a sentence does not.
_ROLE_BANNERS = (
    ("grid", r"DAILY BALANCE(?:S|\s+INFORMATION|\s+SUMMARY)?|BALANCE BY DATE", r""),
    ("charge", r"SERVICE CHARGES?\s+(?:DETAIL|BREAKDOWN)"
               r"|SERVICE CHARGES AND ITEMIZED FEES|ITEMIZED FEES", r""),
    ("summary_credit", r"SUMMARY OF DEPOSITS", r""),
    ("summary_checks", r"SUMMARY BY CHECK NUMBER", r""),
    ("summary_debit", r"SUMMARY OF WITHDRAWALS", r""),
    ("credit", r"DEPOSITS AND (?:OTHER )?(?:ADDITIONS|CREDITS)", r""),
    ("checks", r"CHECKS IN (?:NUMERICAL|NUMBER|SERIAL NUMBER) ORDER|CHECKS PAID", r""),
    ("debit", r"(?:ELECTRONIC )?CHECKS AND (?:OTHER )?(?:WITHDRAWALS|DEBITS)"
              r"|WITHDRAWALS AND (?:DEDUCTIONS|DEBITS)|OTHER DEBITS", r""),
    ("dated", r"ACTIVITY IN DATE ORDER|TRANSACTION ACTIVITY", r""),
    ("credit", r"CREDITS", r"(?=\s*" + _COLUMN_HEADER + r")"),
    ("debit", r"DEBITS", r"(?=\s*" + _COLUMN_HEADER + r")"),
    # The cheque and deposit IMAGE appendix. It is here as a BOUNDARY, not as a
    # block: it restates every item as
    # `CHECK <serial> Date: <mm>/<dd> Amount: $<figure>`, and on 30 of this
    # family's members it follows the
    # daily-balance grid, whose run would otherwise swallow it and read every
    # restated amount as a grid cell. Its rows are the only ones on the page
    # that print their date and amount as LABELLED fields rather than in
    # columns, which is the whole rule.
    ("appendix", r"DATE:\s*[0-9]{1,2}/[0-9]{1,2}(?:/[0-9]{2,4})?\s+AMOUNT:", r""),
)

#: The split pattern: group 1 is the banner, which `tables.section_runs`
#: requires and which `_role_of` reads back.
_BANNER_RE = re.compile(
    "(" + "|".join(pattern + anchor for _role, pattern, anchor in _ROLE_BANNERS) + ")", _I)
#: The same alternations WITHOUT their anchors, for reading a captured banner
#: back to its role: a lookahead cannot fire against a string that ends where
#: the banner ends.
_ROLE_PATTERNS = tuple((role, re.compile(pattern, _I))
                       for role, pattern, _anchor in _ROLE_BANNERS)

#: The platform's own cross-reference: a cheque the grid holds no amount for
#: because the ledger above prints it in full.
_CROSS_REFERENCE_RE = re.compile(r"-\s*See above\s*-", _I)

#: A ledger header that names a running BALANCE column. Its presence is the
#: platform's statement that the ledger carries every posting — see the module
#: docstring — and the `Withdrawal(-) Deposit(+) Balance` issue is why the
#: intervening cells are matched as words rather than as a character run.
_RUNNING_BALANCE_RE = re.compile(
    r"DATE\s+DESCRIPTION\s+(?:[A-Za-z()+-]+\s+){0,3}BALANCE(?![A-Za-z])", _I)


def _role_of(banner: str) -> str | None:
    """The role a captured banner declares, or None if it declares none."""
    printed = re.sub(r"\s+", " ", banner).strip()
    for role, pattern in _ROLE_PATTERNS:
        if pattern.fullmatch(printed):
            return role
    return None


def _blocks(markdown: str) -> dict[str, list[tuple[str, list[str]]]]:
    """The document's ledger, as `{role: [(section, [run, ...]), ...]}`.

    `tables.section_runs` does the split, and its two properties are both
    load-bearing here: a section broken across a page reprints its banner and
    each occurrence is kept as its OWN run, because everything between the last
    row of one and the banner of the next is page furniture that a
    concatenation would put inside a description; and a banner the caller does
    not read still bounds the run before it, which is how the image appendix
    stops the grid.

    Sections are keyed by their printed banner, normalized for whitespace, so
    that `attributed_descriptions` below receives one section's runs together.
    """
    found: dict[str, list[tuple[str, list[str]]]] = {}
    sections: dict[str, tuple[str, list[str]]] = {}
    for banner, runs in section_runs(markdown, _BANNER_RE).items():
        role = _role_of(banner)
        if role is None:
            continue
        name = re.sub(r"\s+", " ", banner).strip().upper()
        if name in sections:
            sections[name][1].extend(runs)
            continue
        section = (role, list(runs))
        sections[name] = section
        found.setdefault(role, []).append((name, section[1]))
    return found


# ---------------------------------------------------------------------------
# The rows
# ---------------------------------------------------------------------------

#: What this template prints as furniture around a description rather than as
#: part of it: the flattened layer's column rule and the ASCII rules the pipe
#: box is drawn with.
_DESCRIPTION_FURNITURE = " |_"
#: The longest description this reader will publish.
#: `tables.attributed_descriptions` cuts at a token boundary rather than
#: through a word, because half a token is a string the bank did not print.
_DESCRIPTION_LIMIT = 200
#: A cheque's serial number, the leading cell of the platform's collapsed
#: `Date Check No Amount` grid. The platform marks a break in the sequence with
#: a trailing `*` and prints a cheque it holds no serial for as a bare pair.
_SERIAL_RE = re.compile(r"([0-9]{2,8})\s*\*?")
#: Every block role this reader reads, in the order it reads them, with what
#: the role says about its rows: the direction the BANNER declares (None where
#: the block is the date-order issue's undivided ledger and the printed sign is
#: the only evidence), whether the block is a collapsed `Date Check No Amount`
#: grid whose leading cell is a serial rather than a description, whether it is
#: a block the platform calls a SUMMARY, and the label to publish where the
#: block prints no description of its own.
_ROLE_READING = {
    "credit": ("credit", False, False, "Deposit"),
    "debit": ("debit", False, False, "Debit"),
    "checks": ("debit", True, False, "Check"),
    "dated": (None, False, False, "Transaction"),
    "summary_credit": ("credit", False, True, "Deposit"),
    "summary_debit": ("debit", False, True, "Debit"),
    "summary_checks": ("debit", True, True, "Check"),
}


@dataclass(frozen=True)
class _Posting:
    """One row, before the period places its year."""

    day: str
    amount: float
    credit: bool
    description: str


def _section_rows(runs: list[str], *, role: str) -> list[_Posting] | None:
    """Every posting one section printed, or None if a row is unreadable.

    None rather than "skip". A row whose amount is not money, or that prints no
    amount before the next row opens, is a row we could not read, and dropping
    it silently is how a ledger comes to disagree with a printed count while
    still looking complete. The exception is the platform's own cross-reference
    marker, which says in words that the amount is printed elsewhere.

    The direction is the BLOCK the bank printed the row in, never the sign of
    the amount — except in the date-order issue, which prints one undivided
    ledger and no column to read.
    """
    direction, serialled, _restated, default = _ROLE_READING[role]
    read: list[tuple[str, list]] = []
    for run in runs:
        cells = dated_cells(
            _without_non_opening_dates(_without_cross_references(run)),
            date_pattern=_DATE_RE, value_pattern=_LEDGER_FIGURE_RE)
        if cells is None:
            return None
        read.append((run, cells))
    described = attributed_descriptions(
        [cells for _run, cells in read],
        strip=_DESCRIPTION_FURNITURE, limit=_DESCRIPTION_LIMIT,
    )
    postings: list[_Posting] = []
    for (_run, cells), texts in zip(read, described):
        for index, cell in enumerate(cells):
            amount = _ledger_amount(cell.value)
            if amount is None:
                return None
            if serialled:
                serial = _SERIAL_RE.fullmatch(cell.described.strip(" |*"))
                description = f"{default} {serial.group(1)}" if serial else default
            else:
                description = texts[index] or default
            postings.append(_Posting(
                day=cell.date,
                amount=abs(amount),
                credit=(amount > 0) if direction is None else direction == "credit",
                description=description,
            ))
    return postings


def _without_non_opening_dates(run: str) -> str:
    """The run with the date tokens that open NO ROW blanked out.

    A row of this ledger is a date and then the first figure printed before the
    next date opens. A date token with ANOTHER DATE between it and the next
    figure therefore opens nothing: the run says so itself, because the row it
    would open is closed by a row that starts later. `tables.dated_cells`
    refuses the whole document for one, and on this family that refusal was
    costing six members over a token that is not a posting date at all. The
    archive prints the shape two ways, both of them the flattened layer's doing
    rather than the bank's:

    * the row's own date emitted TWICE with a fragment of its description
      between the two, where the layer welded the amount column through the
      middle of the description (this family's `<desc> fr <amount> om <desc>`
      weld, one column further left);
    * a `mm/dd` inside a merchant's own printed name — a card statement's
      `Member <mm>/<dd>` renewal note, in the description of a real row.

    **Blanked rather than removed**, and the honest statement of what that buys
    is smaller than it looks: measured over the whole cohort — the members this
    reader claims plus the declines, both forms compared field for field — the
    two publish IDENTICAL statements, because the text between a non-opening
    date and the next one lies outside every cell's own span and
    `tables.dated_cells` gives a row's description as what stands between its
    date and its amount. Blanking is kept because it is the MINIMAL edit: every
    other character keeps its position and its content, so "only the token that
    claimed to open a row stopped claiming it" is checkable by looking rather
    than by reasoning. The mutation table records the equivalence as a
    surviving mutant instead of pretending the choice is load-bearing
    (W3 §CPDECL).

    **The gate that proves the call is the one that already proves
    `_without_cross_references`**: both printed counts and both printed totals.
    A date this blanks that really WAS a row whose amount the layer lost leaves
    the ledger one row short of the bank's own count and its total short by
    that row's amount, and the document declines at
    `_matches_the_printed_summary` instead of here. So the reading is not
    trusted, it is checked — against the cent, in both directions, by the bank.

    A date that closes no cell with NO further date after it is left alone and
    still refuses the document. That is a different shape — a run that stops
    mid-row, which is what a truncated page looks like — and this rule has no
    evidence about it.
    """
    dates = list(_DATE_RE.finditer(run))
    blanked: list[str] = []
    cursor = 0
    for index, found in enumerate(dates[:-1]):
        stop = dates[index + 1].start()
        if _LEDGER_FIGURE_RE.search(run[found.end():stop]) is not None:
            continue
        blanked.append(run[cursor:found.start(1)])
        blanked.append(" " * len(found.group(1)))
        cursor = found.end(1)
    if not blanked:
        return run
    blanked.append(run[cursor:])
    return "".join(blanked)


def _without_cross_references(run: str) -> str:
    """The run with the platform's cross-reference rows removed.

    A cheque grid prints `date serial -See above-` where the item is detailed
    in the ledger above rather than repeating its amount. Left in, the date
    closes no cell and `dated_cells` declines the whole document; read as a
    row, the cheque is posted twice. It is neither: it is a pointer, and the
    count gate is what proves the call on every member that prints one.
    """
    if not _CROSS_REFERENCE_RE.search(run):
        return run
    kept: list[str] = []
    dates = list(_DATE_RE.finditer(run))
    cursor = 0
    for index, found in enumerate(dates):
        stop = dates[index + 1].start() if index + 1 < len(dates) else len(run)
        span = run[found.end():stop]
        marker = _CROSS_REFERENCE_RE.search(span)
        value = _LEDGER_FIGURE_RE.search(span)
        if marker is not None and (value is None or marker.start() < value.start()):
            kept.append(run[cursor: found.start()])
            cursor = stop
    kept.append(run[cursor:])
    return "".join(kept)


def _ledger(markdown: str, blocks: dict[str, list[tuple[str, list[str]]]]) -> list[_Posting] | None:
    """Every posting the document printed, or None if one is unreadable.

    The fee-detail block is deliberately absent: it itemizes the single service
    charge the debit ledger already carries. The SUMMARY blocks are read only
    where the ledger prints no running balance — see the module docstring.
    """
    running = bool(_RUNNING_BALANCE_RE.search(markdown))
    postings: list[_Posting] = []
    for role, (_direction, _serialled, restated, _default) in _ROLE_READING.items():
        if running and restated:
            continue
        for _name, runs in blocks.get(role, []):
            found = _section_rows(runs, role=role)
            if found is None:
                return None
            postings.extend(found)
    return postings


def _grid(runs: list[str], *, start: date, end: date) -> dict[str, float] | None:
    """One printed daily-balance block as a day-to-balance map, or None.

    A day printed twice with two different balances refuses the document: the
    grid arrives three columns to a line and a duplicate is evidence the column
    recovery went wrong, which a map that silently kept the last reading would
    hide. A day printed twice with the SAME balance is the page header
    repeating, and is not that.
    """
    printed: dict[str, float] = {}
    for run in runs:
        cells = dated_cells(run, date_pattern=_DATE_RE, value_pattern=_LEDGER_FIGURE_RE)
        if cells is None:
            return None
        for cell in cells:
            iso = iso_within_period(cell.date, start, end)
            balance = _ledger_amount(cell.value)
            if iso is None or balance is None:
                return None
            if iso in printed and abs(printed[iso] - balance) > 0.005:
                return None
            printed[iso] = balance
    return printed


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------

#: The cent the printed figures are rounded to.
_TOLERANCE = 0.005


def _matches_the_printed_summary(rows: list[Transaction], summary: _Summary) -> bool:
    """Both printed counts, both printed totals, and the summary's identity.

    The identity is checked first and on the printed figures alone, so a
    summary this reader misread fails before its figures are used to judge a
    ledger. `previous + credits - debits - service charge + interest ==
    ending`: this template prints the charge and the interest outside its two
    direction totals, which is what makes this a fifth independent printing.

    Each direction is then allowed the ONE row class the bank's own count
    leaves out — the interest it credited and the fee it billed — and only for
    the exact figure it printed. `> dcnt` rather than `== dcnt + 1` on the
    debit side because one member posts its charge as two rows; the TOTAL is
    pinned to the cent either way, so the looser count admits no ledger the
    money does not already close.
    """
    identity = (summary.previous + summary.credits - summary.debits
                - summary.service_charge + summary.interest)
    if abs(identity - summary.closing) > _TOLERANCE:
        return False
    credits_ = [row for row in rows if row.direction == "credit"]
    debits = [row for row in rows if row.direction == "debit"]
    credited = sum(row.amount for row in credits_)
    debited = -sum(row.amount for row in debits)
    counted_credits = (
        (len(credits_) == summary.credit_count
         and abs(credited - summary.credits) <= _TOLERANCE)
        or (summary.interest > 0 and len(credits_) == summary.credit_count + 1
            and abs(credited - summary.credits - summary.interest) <= _TOLERANCE)
    )
    counted_debits = (
        (len(debits) == summary.debit_count
         and abs(debited - summary.debits) <= _TOLERANCE)
        or (summary.service_charge > 0 and len(debits) > summary.debit_count
            and abs(debited - summary.debits - summary.service_charge) <= _TOLERANCE)
    )
    return counted_credits and counted_debits


def _matches_the_printed_grid(
    rows: list[Transaction], printed: dict[str, float], summary: _Summary
) -> bool:
    """The daily-balance grid, walked against the ledger, in both directions.

    An independent second opinion: a ledger that reproduces every summary
    figure and still disagrees with the grid has the right totals on the wrong
    days, which is what a duplicated row paired with a dropped one looks like.

    The grid prints an end-of-day balance for every day the account moved, and
    on some issues ALSO for the first day of the period when nothing posted on
    it — the opening balance, printed a second time. That cell is admitted
    against the printed opening balance and against nothing else, and a grid
    day the ledger never posts on that is not it fails the document.
    """
    walked: dict[str, float] = {}
    running = summary.previous
    for row in sorted(rows, key=lambda item: item.date):
        running = round(running + row.amount, 2)
        walked[row.date] = running
    if set(walked) - set(printed):
        return False
    surplus = set(printed) - set(walked)
    if surplus and (surplus != {summary.start}
                    or abs(printed[summary.start] - summary.previous) > _TOLERANCE):
        return False
    return all(abs(walked[day] - balance) <= _TOLERANCE
               for day, balance in printed.items() if day in walked)


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

def parse_core_processor_enclosures_statement(markdown: str) -> Statement | None:
    """Any issuer's statement on the enclosures / average-ledger template.

    Declines — rather than guesses — in six named situations, each of them a
    fact about the document rather than a gap in this reader:

    * it prints no summary strip, or one with a hole in it, or one that prints
      a figure twice with two different readings;
    * its printed period is not a period;
    * it prints no ledger block this template names;
    * a row's amount is not money;
    * a run STOPS mid-row — its last date prints no amount and no further date
      follows it, which is what a truncated page looks like. A date with
      another DATE before the next figure is a different shape and opens no
      row at all (`_without_non_opening_dates`);
    * a row's date is not a day of the printed period;
    * the ledger does not reproduce both printed counts and both printed
      totals, or disagrees with the printed daily-balance grid.
    """
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    if summary is None:
        return None
    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    if end < start:
        return None

    blocks = _blocks(markdown)
    postings = _ledger(markdown, blocks)
    if not postings:
        return None

    rows: list[Transaction] = []
    for posting in postings:
        iso = iso_within_period(posting.day, start, end)
        if iso is None:
            return None
        rows.append(Transaction(
            date=iso,
            description=posting.description,
            amount=round(posting.amount if posting.credit else -posting.amount, 2),
            direction="credit" if posting.credit else "debit",
        ))
    if not _matches_the_printed_summary(rows, summary):
        return None

    printed_grid: dict[str, float] = {}
    for _name, runs in blocks.get("grid", []):
        found = _grid(runs, start=start, end=end)
        if found is None:
            return None
        for day, balance in found.items():
            if day in printed_grid and abs(printed_grid[day] - balance) > _TOLERANCE:
                return None
            printed_grid[day] = balance
    if printed_grid and not _matches_the_printed_grid(rows, printed_grid, summary):
        return None

    return Statement(
        # The template prints no institution FIELD — see the module docstring.
        bank=None,
        account_name=summary.product,
        account_number=summary.account,
        period_start=summary.start,
        period_end=summary.end,
        days_in_period=summary.days,
        beginning_balance=summary.previous,
        ending_balance=summary.closing,
        stated_total_credits=summary.credits,
        stated_total_debits=summary.debits,
        stated_credit_count=summary.credit_count,
        stated_debit_count=summary.debit_count,
        stated_service_charge=summary.service_charge,
        stated_interest_paid=summary.interest,
        bank_reported_average_balance=summary.average,
        bank_reported_average_label=(
            "Average Ledger" if summary.average is not None else None
        ),
        stated_daily_balances=[
            StatementDailyBalance(date=day, balance=balance)
            for day, balance in sorted(printed_grid.items())
        ],
        transactions=sorted(rows, key=lambda row: row.date),
    )
