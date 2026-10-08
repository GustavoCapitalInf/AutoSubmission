"""The fourth summary grammar of the same core processor, read as a partition.

W3 §LCPERIOD L7.3 named this cohort and ranked it: 8 unclaimed documents that
print the third core-processor template's period SENTENCE and none of its
summary — "not 'add a period marker': a fourth summary grammar", and "the
RICHEST oracle of the three templates". This module is that reader.

What the template shares with `core_processor_daily`, and what it does not
------------------------------------------------------------------------
========================  ==================================  =============================
printing                  `core_processor_daily`              this template
========================  ==================================  =============================
period                    `Last statement: March 31, 2026`    the same two sentences, and
                          `This statement: April 30, 2026`    NO `Total days` line at all
                          `Total days in statement period:`
summary                   `Total additions` / `Total          a counted PARTITION: three
                          subtractions` — totals, no counts   printed categories per
                                                              direction, each with its own
                                                              COUNT and total, then
                                                              `Total credits` / `Total debits`
opening / closing         `Beginning balance $<fig>`          `Beginning balance (1/30/2026)`
                          `Ending balance $<fig>`             `Ending balance (2/27/2026)`
                          — undated                           — DATED, on their own lines
account heading           `Account number <number>`           `Account #:` AND
                                                              `Account number <number>`
ledger sections           `DEBITS` `CREDITS` `CHECKS`         one section per printed
                                                              CATEGORY: `ELECTRONIC CREDITS`
                                                              `OTHER CREDITS` `CHECKS PAID`
                                                              `ELECTRONIC DEBITS`
                                                              `OTHER DEBITS` `DEPOSITS`
grid                      `DAILY BALANCES`, opening on the    the same, in four columns
                          day BEFORE the period               whose cells arrive OUT of
                                                              document order
row date                  `mm-dd`                             `m-d`, unpadded
contact furniture         `Direct inquiries to:`              `Contact us:`
========================  ==================================  =============================

The two required markers are the period sentence PAIR and the two DATED
summary balances. Measured over the 3,396 documents of the D-3 artifact store
with offline text: the period pair alone is printed by 32 documents across
four grammars of this one processor, the dated balances alone by exactly 8,
and the conjunction by the same 8 — no near miss in either direction. The
dated balances are what separate this grammar from the three siblings that
share its period sentence: `core_processor_daily`'s 20 print `Beginning
balance $` undated, and the Columbia cohort's 3 print the same undated form
(§LCPERIOD L7.3's "FOURTH arrangement", another cell's card).

The summary is a PARTITION, and that is the whole oracle
--------------------------------------------------------
    Beginning balance (1/30/2026)
    $14,367.54
    Credits
    Deposits (0) + 0.00  Electronic cr (2) + 9,372.24  Other credits (0) + 0.00
    Total credits
    +$9,372.24
    Debits
    Checks paid (0) - 0.00  Electronic db (22) - 5,655.95  Other debits (0) - 0.00
    Total debits
    - $5,655.95
    Ending balance (2/27/2026)
    $18,083.83

Six printed categories, each with a COUNT and a TOTAL, and each heading a
ledger section of its own name. The third core processor prints no count at
all (§LCPERIOD L3) and the second prints one per direction (§SCANB); this one
prints six of each, which is why the card called it the richest oracle in the
complex. What a document must prove before anything is published:

1. **every category's printed COUNT equals the number of rows in the section
   that category heads** — six independent checks, and the one thing no other
   template in this complex can offer: a row split in two, or two rows merged,
   moves a count even when it does not move a total;
2. **every category's printed TOTAL equals those rows' amounts** — six more;
3. **each direction's three category totals sum to the direction's printed
   total** — the partition closing on itself, which is a printing independent
   of (2) because the bank prints both the parts and the sum;
4. **`beginning + credits - debits == ending`**, the summary's own identity,
   against the two printed balances;
5. **the two DATED balances agree with the two printed statement dates** —
   the period is printed twice, in two different notations, and a document
   whose `Beginning balance (…)` is not dated the day its last statement
   closed is a document we have misread;
6. **the `DAILY BALANCES` grid reconciles**: its pre-period cell equals the
   printed beginning balance, every in-period cell equals the walked
   end-of-day balance, and every day the ledger posts on appears in the grid.

A document that cannot satisfy all of them publishes nothing.

**What the gate set still cannot see, named rather than left to be found.**
Moving value between two rows that share a date, a direction AND a category
holds every one of the six. The counted partition is what shrinks §LCPERIOD
L3's blind spot rather than closing it: there, a row split in two survived
every gate; here it moves the category's count, so the surviving construction
needs two rows that already exist. Both are forgery signatures rather than
OCR ones.

**The grid opens the day BEFORE the period, and that cell is opening state.**
The ADB doctrine (ratified 2026-08-15) is that the canonical underwriting ADB
is the calendar days of the PRINTED period; a balance dated before the period
opens is initialization, never a denominator day. This template says so twice
in its own printing: the grid's first cell and the parenthesised date on
`Beginning balance` are the same day, and it is the day the LAST statement
closed. So that cell is used as a gate and excluded from
`stated_daily_balances`, whose contract is in-period snapshots (§LCPERIOD
L7.8 — publishing it would withhold every document).

The issuer, which this template does not print in a field
----------------------------------------------------------
`Statement.bank` is None on every document this reader publishes, under the
honest-unknown-issuer ruling of 2026-08-14, and this cohort is where §LCPERIOD
L4's evidence CAME from: what these documents print under `Contact us:` and in
their closing courtesy sentence is `Orange CO Airport Office` — a BRANCH.
Reading that slot would publish a branch office as the name of a bank. The
documents also print a bare `cnb.com`; a domain is not an institution field
either, and no arrangement here bounds an institution name on both sides.

Look-alike glyphs are refused rather than absorbed
---------------------------------------------------
The same law as §SCANB S5 with §LCPERIOD L6's two corrections: `[0-9]` classes
throughout, and `\\w` boundary classes on BOTH sides of every token — the
boundary is the half that does the work, because with an ASCII boundary class
an amount whose integer part a scan rendered in another script matches the
bare sub-dollar alternative `.00` and publishes 0.00 where the bank printed
250.00. This template prints genuine sub-dollar figures (`.14`, `.55`), so
that alternative is load-bearing here rather than defensive.

**The row date is where this template differs, and it needs a real calendar
class.** Rows are dated `m-d` UNPADDED (`2-2`, `3-17`), which is two
characters shorter than the sibling's `mm-dd` and therefore far easier for a
description to imitate: these ledgers carry `BILL.COM P26031002 - 4974025 INV
26-2` and `INV 26-3` on ordinary rows, and an invoice suffix like that one
satisfies a one-or-two-digit-run row-date grammar perfectly. So the month and
day are matched as CALENDAR ranges rather than as digit runs — an invoice
number is not a month, and the left boundary then stops the pattern
from restarting inside the token at `6-2`.

Measured, and stated as measured: with a plain digit-run class **3 of the 8
documents refuse** — the three that print the BILL.COM invoice suffixes — and
the other 5 publish BYTE-IDENTICALLY, because they print no token of that
shape. A phantom row appears in a section whose printed count then disagrees,
so the gates catch it; that is the point of them. But a reader that refuses
three honest documents out of eight is a reader that cannot read the template,
and the calendar class costs nothing on the five it does not affect.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .date_tokens import iso_from_named_month_day, iso_or_none, iso_within_period
from .money import (
    LEADING_MINUS, MINUS_CLASS, STRICT_UNSIGNED, pad_leading_decimal, parse_amount,
)
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import (
    attributed_descriptions, dated_cells, section_runs, unique_match,
)

# ---------------------------------------------------------------------------
# The grammar
# ---------------------------------------------------------------------------

#: A token may not begin part-way through another token, and may not be
#: continued by one. `\w` rather than `[0-9A-Za-z]` for the reason §LCPERIOD
#: L6.2 measured, and the hyphen is inside all three classes because this
#: template's row date is hyphenated and its descriptions carry hyphenated
#: reference numbers.
_TOKEN_START = r"(?<![\w.,/-])"
_DATE_END = r"(?![\w/-])"
_FIGURE_END = r"(?![\w.,])"

#: `m-d`, unpadded, as a CALENDAR range rather than a digit run — see the
#: module docstring. The leading zero is admitted because nothing about the
#: template forbids an issuer from printing one, and admitting it refuses
#: nothing: `26-2` still cannot match, at either offset.
_ROW_DATE = r"(?:1[0-2]|0?[1-9])-(?:3[01]|[12][0-9]|0?[1-9])"
#: `1,234.56`, and the bare `.56` this template really does print.
_FIGURE = r"(?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2})"
#: `1/30/2026`, the notation the two dated summary balances are printed in.
_PRINTED_DATE = r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})"

_DATE_TOKEN = _TOKEN_START + r"(" + _ROW_DATE + r")" + _DATE_END
#: A LEDGER figure: unsigned, because every amount printed in a section is a
#: MAGNITUDE whose direction is the category the section belongs to.
_FIGURE_TOKEN = _TOKEN_START + r"(" + _FIGURE + r")" + _FIGURE_END
#: A BALANCE figure: signed, because a balance can be overdrawn. `MINUS_CLASS`
#: rather than a literal `-`, so the shared money grammar's glyph set applies.
_BALANCE_TOKEN = _TOKEN_START + r"(" + MINUS_CLASS + r"?" + _FIGURE + r")" + _FIGURE_END

_DATE_RE = re.compile(_DATE_TOKEN)
_FIGURE_RE = re.compile(_FIGURE_TOKEN)
_BALANCE_RE = re.compile(_BALANCE_TOKEN)


def _magnitude(value: str) -> float | None:
    """A printed section or category figure as a positive number, or None."""
    return parse_amount(pad_leading_decimal(value), STRICT_UNSIGNED)


def _balance(value: str) -> float | None:
    """A printed balance as a number, or None.

    Leading minus only: this template prints an overdrawn balance as `$-1.23`
    and prints no trailing sign anywhere, so a trailing-minus token here would
    be a figure from some other layout. A negative SUB-DOLLAR balance (`$-.55`)
    pads to nothing and is refused, fail-closed — the same printing §LCPERIOD
    L7.5 carded on the sibling, and the fix belongs to `analysis/money.py`
    rather than to a second copy here.
    """
    return parse_amount(pad_leading_decimal(value), LEADING_MINUS)


# ---------------------------------------------------------------------------
# Detection: the template's own furniture, and nothing about an issuer
# ---------------------------------------------------------------------------

#: The period sentence, read in two pieces rather than as one phrase, because
#: the two are printed in either order and with page furniture between them:
#: `This statement: February 27, 2026 Last statement: January 30, 2026`.
_LONG_DATE = r"([A-Z][a-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})"
_OPENING_DATE_RE = re.compile(r"Last statement:\s+" + _LONG_DATE)
_CLOSING_DATE_RE = re.compile(r"This statement:\s+" + _LONG_DATE)

#: The two DATED summary balances, as LABELS. This is the marker that
#: separates the fourth grammar from the three siblings printing the same
#: period sentence, and it is a template printing rather than an issuer's:
#: the parenthesised date is how this summary states the day each balance is
#: a balance ON.
_BEGINNING_LABEL_RE = re.compile(r"Beginning balance\s+\(" + _PRINTED_DATE + r"\)")
_ENDING_LABEL_RE = re.compile(r"Ending balance\s+\(" + _PRINTED_DATE + r"\)")

#: The summary's own closing rows. Coextensive with the two markers above on
#: this archive but one document wider, so it corroborates rather than gates.
_TOTAL_CREDITS_LABEL = "Total credits"
_TOTAL_DEBITS_LABEL = "Total debits"

#: **Case is load-bearing, so this registration has no normalization.**
#: Sentence case is what separates this processor's fourth grammar from
#: `core_processor_sectioned`'s upper-case period line, and an upper-casing
#: normalization would make the two indistinguishable.
DETECTION_MARKERS = (
    required(
        "platform_period_endpoints",
        lambda t: bool(_OPENING_DATE_RE.search(t)) and bool(_CLOSING_DATE_RE.search(t)),
    ),
    required(
        "platform_dated_summary_balances",
        lambda t: bool(_BEGINNING_LABEL_RE.search(t)) and bool(_ENDING_LABEL_RE.search(t)),
    ),
    corroborating(
        "platform_counted_partition",
        lambda t: _TOTAL_CREDITS_LABEL in t and _TOTAL_DEBITS_LABEL in t,
    ),
)

detect = make_detector(DETECTION_MARKERS)


# ---------------------------------------------------------------------------
# The printed summary
# ---------------------------------------------------------------------------

#: Where the summary strip begins. The template prints the product name on the
#: line directly above it and the ledger directly below it.
_SUMMARY_HEADING = "Account Summary"

#: The account field, printed twice: once as a masthead label whose value
#: stands on the next line, and once inside the summary strip. Both are read
#: and they must agree — see `_summary`.
_ACCOUNT_LABEL_RE = re.compile(r"Account #:\s*\n\s*([Xx*0-9]{4,})(?![0-9])")
_ACCOUNT_NUMBER_RE = re.compile(r"Account number\s+([Xx*0-9]{4,})(?![0-9])")

#: The two dated balances, with their figures. The figure is printed on the
#: line BELOW its label, which is why there is no line anchoring here.
_BEGINNING_RE = re.compile(
    r"Beginning balance\s+\(" + _PRINTED_DATE + r"\)\s+\$" + _BALANCE_TOKEN)
_ENDING_RE = re.compile(
    r"Ending balance\s+\(" + _PRINTED_DATE + r"\)\s+\$" + _BALANCE_TOKEN)

#: Each direction's printed total. The sign is REQUIRED and is the direction
#: the template declares, so a summary printing `Total credits - $…` fails to
#: match and the document is refused rather than read with the sign ignored.
_TOTAL_CREDITS_RE = re.compile(
    _TOTAL_CREDITS_LABEL + r"\s+\+\s*\$\s*" + _FIGURE_TOKEN)
_TOTAL_DEBITS_RE = re.compile(
    _TOTAL_DEBITS_LABEL + r"\s+" + MINUS_CLASS + r"\s*\$\s*" + _FIGURE_TOKEN)

#: The period's average, printed undated beside the balances. Published as the
#: BANK-REPORTED average — evidence, never the platform's ADB, which
#: `analysis/adb.py` computes on the canonical calendar-day basis. It gates
#: nothing, which is what leaves it free to be an independent opinion.
#: The `$` is required: `Avg. collected balance $…` is a different statistic
#: printed on the same line, and this pattern must not reach it.
_AVERAGE_RE = re.compile(r"Average balance\s+\$" + _BALANCE_TOKEN)


@dataclass(frozen=True)
class _Category:
    """One cell of the summary's counted partition, and the section it heads.

    The template names its own categories, so they are DATA here rather than
    six near-identical patterns: the printed label, the section heading it
    heads, the direction its rows post in — which is the category the bank
    printed them under, never the sign of an amount — and the description to
    publish where a section prints none.
    """

    label: str
    heading: str
    credit: bool
    default: str
    #: The cheque grid prints `Number Date Amount`, so the serial is the row's
    #: LEADING cell rather than a description between the date and the amount.
    serialled: bool = False


_CATEGORIES = (
    _Category("Deposits", "DEPOSITS", True, "Deposit"),
    _Category("Electronic cr", "ELECTRONIC CREDITS", True, "Electronic credit"),
    _Category("Other credits", "OTHER CREDITS", True, "Other credit"),
    _Category("Checks paid", "CHECKS PAID", False, "Check", serialled=True),
    _Category("Electronic db", "ELECTRONIC DEBITS", False, "Electronic debit"),
    _Category("Other debits", "OTHER DEBITS", False, "Other debit"),
)


def _category_pattern(category: _Category) -> re.Pattern[str]:
    """`Electronic db (22) - 5,655.95` — the count and the total, with the
    sign the direction requires.

    The category figures print no `$` and the direction totals do; requiring
    exactly what is printed is what makes a pattern refuse a row whose figure
    OCR lost rather than read the next one along.
    """
    sign = r"\+" if category.credit else MINUS_CLASS
    return re.compile(
        re.escape(category.label) + r"\s*\(\s*([0-9]{1,4})\s*\)\s*"
        + sign + r"\s*" + _FIGURE_TOKEN
    )


_CATEGORY_PATTERNS = {category.label: _category_pattern(category)
                      for category in _CATEGORIES}

#: The template's own headings: one per printed category, the grid, and the
#: back-of-statement legend. The legend is in the list as a BOUNDARY, not as a
#: section: without it the grid's block runs to the end of the document and
#: anything the disclosures print would be read as grid cells. No archive
#: document's disclosures carry a date token (measured), so this is
#: precautionary rather than proven, and it is named so nobody mistakes it for
#: a guard that has done work.
_DISCLOSURE_HEADING = "PLEASE EXAMINE THIS STATEMENT"
_GRID_HEADING = "DAILY BALANCES"
_SECTION_NAMES = (
    tuple(category.heading for category in _CATEGORIES)
    + (_GRID_HEADING, _DISCLOSURE_HEADING)
)
#: Case-SENSITIVE on purpose: the template prints its section names in
#: capitals and its summary prints the same words in sentence case
#: (`Checks paid (4)` heads `CHECKS PAID`), so case is what tells the summary
#: from the ledger.
_SECTION_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in _SECTION_NAMES) + r")\b")


@dataclass(frozen=True)
class _Summary:
    """Every figure the summary partition prints."""

    account: str
    start: str
    end: str
    seed: str
    beginning: float
    ending: float
    credits: float
    debits: float
    counts: dict[str, int]
    totals: dict[str, float]
    average: float | None


def _long_date(match: re.Match[str]) -> str | None:
    """A `<Month> D, YYYY` match as an ISO date, or None if it is not one.

    The pattern proves the SHAPE and nothing more — `Fiscal 30, 2026` has that
    shape, and so does `February 31, 2026` — so the shared reader is the one
    that decides, and it returns None rather than raising on both.
    """
    return iso_from_named_month_day(match.group(1), match.group(2), match.group(3))


def _slash_date(match: re.Match[str], group: int) -> str | None:
    """`(1/30/2026)` as an ISO date, or None if those three numbers are not
    one. `group` is the offset of the month inside the match."""
    return iso_or_none(int(match.group(group + 2)), int(match.group(group)),
                       int(match.group(group + 1)))


def _front_matter(markdown: str) -> str:
    """Everything the statement prints above its ledger.

    Scoped because the period sentence and the summary are page-1 furniture,
    and the ledger below them is pages of descriptions the bank did not write.
    """
    heading = _SECTION_RE.search(markdown)
    return markdown[: heading.start()] if heading else markdown


def _summary_region(markdown: str) -> str | None:
    """The summary partition alone: from its own heading to the ledger."""
    at = markdown.find(_SUMMARY_HEADING)
    if at < 0:
        return None
    return _front_matter(markdown[at:])


def _period(front: str) -> tuple[str, str] | None:
    """`(the day the last statement closed, the day this one closes)`, or None.

    Both are the dates of STATEMENTS, not of the period: the period opens the
    day AFTER the last statement closed, which is what the grid's first cell
    and the parenthesised date on `Beginning balance` independently confirm.
    """
    opening = unique_match(front, _OPENING_DATE_RE)
    closing = unique_match(front, _CLOSING_DATE_RE)
    if not (opening and closing):
        return None
    previous, end = _long_date(opening), _long_date(closing)
    if previous is None or end is None:
        return None
    return previous, end


def _counted_partition(region: str) -> tuple[dict[str, int], dict[str, float]] | None:
    """Every category's printed count and total, or None if one is unreadable.

    All six or nothing. A partition with a hole in it is not a weaker oracle,
    it is a summary this reader has misread: the direction totals below are
    checked against the SUM of these, so a missing category would silently
    move the check rather than fail it.
    """
    counts: dict[str, int] = {}
    totals: dict[str, float] = {}
    for category in _CATEGORIES:
        printed = unique_match(region, _CATEGORY_PATTERNS[category.label])
        if printed is None:
            return None
        total = _magnitude(printed.group(2))
        if total is None:
            return None
        counts[category.label] = int(printed.group(1))
        totals[category.label] = total
    return counts, totals


def _summary(markdown: str) -> _Summary | None:
    """The whole printed summary, or None if any part of it is missing.

    Every gate below compares the published ledger against these figures, so
    a partly-read summary would weaken the gates instead of failing them.
    """
    region = _summary_region(markdown)
    period = _period(_front_matter(markdown))
    if region is None or period is None:
        return None
    previous, end = period

    numbered = unique_match(markdown, _ACCOUNT_LABEL_RE)
    named = unique_match(region, _ACCOUNT_NUMBER_RE)
    beginning = unique_match(region, _BEGINNING_RE)
    ending = unique_match(region, _ENDING_RE)
    credits_ = unique_match(region, _TOTAL_CREDITS_RE)
    debits = unique_match(region, _TOTAL_DEBITS_RE)
    if None in (numbered, named, beginning, ending, credits_, debits):
        return None
    # The account number is printed twice, in two different fields. Two
    # different values is not a reading to choose between: it is a document
    # carrying more than one account, which this reader has no schema for.
    if numbered.group(1) != named.group(1):
        return None

    partition = _counted_partition(region)
    if partition is None:
        return None
    counts, totals = partition

    # The period, printed twice in two notations. The dated balances are what
    # say which day each balance is a balance ON, and a summary that disagrees
    # with its own statement dates has been misread.
    if _slash_date(beginning, 1) != previous or _slash_date(ending, 1) != end:
        return None

    opening_balance = _balance(beginning.group(4))
    closing_balance = _balance(ending.group(4))
    total_credits = _magnitude(credits_.group(1))
    total_debits = _magnitude(debits.group(1))
    if None in (opening_balance, closing_balance, total_credits, total_debits):
        return None

    average = unique_match(region, _AVERAGE_RE)
    return _Summary(
        account=named.group(1),
        start=(date.fromisoformat(previous) + timedelta(days=1)).isoformat(),
        end=end,
        seed=previous,
        beginning=opening_balance,
        ending=closing_balance,
        credits=total_credits,
        debits=total_debits,
        counts=counts,
        totals=totals,
        average=_balance(average.group(1)) if average else None,
    )


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

#: A cheque's serial number, read as the WHOLE of what the bank printed to the
#: left of the date on that row's own line — the leading cell of the printed
#: `Number Date Amount` grid, not a hunt for trailing digits in the gap
#: (§LCPERIOD L5.3, whose three constructions are fixtured for this reader
#: too). The platform marks a break in the serial sequence with a trailing `*`,
#: and prints two cheque rows on one line.
_SERIAL_RE = re.compile(r"([0-9]{2,8})\s*\*?")


#: What this template prints as furniture around a description rather than as
#: part of it: the flattened layer's column rule. Stripping anything else would
#: publish something the statement does not carry.
_DESCRIPTION_FURNITURE = " |"
#: The longest description this reader will publish. A bound has to exist —
#: a span the layer filled with a page of furniture is not a description — and
#: `tables.attributed_descriptions` cuts at a token boundary rather than
#: through a word, because half a token is a string the bank did not print.
#: With the attribution fixed the bound is headroom rather than a cut: the
#: longest description the complex's 21 validated documents publish is 121
#: characters, and no row reaches 200 (W3 §DESCATTRIB DA8).
_DESCRIPTION_LIMIT = 200


def _row_lead(gap: str) -> str:
    """What the bank printed to the left of a row's date on that row's OWN
    line. Everything before the last newline is a different printed line."""
    return gap[gap.rfind("\n") + 1:].strip(" |\t")


def _rows(runs: list[str], *, category: _Category,
          start: date, end: date) -> list[Transaction] | None:
    """Every posting one category's section printed, or None if one is
    unreadable.

    None rather than "skip": a row whose date the period cannot place, or that
    prints no amount before the next row opens, is a row we could not read,
    and dropping it silently is how a ledger comes to disagree with a printed
    count while still looking complete. Here it would disagree with a count as
    well as a total, which is the whole reason this template is worth reading.
    """
    postings: list[Transaction] = []
    read = []
    for run in runs:
        cells = dated_cells(run, date_pattern=_DATE_RE, value_pattern=_FIGURE_RE)
        if cells is None:
            return None
        read.append((run, cells))
    # The descriptions are read for the whole SECTION, not for a row or even a
    # run at a time: what a row's span owns depends on how many rows' merchant
    # blocks the flattened layer still had in hand when it flushed into that
    # span, and a block outstanding when a page break ends one run lands in the
    # FIRST span of the next (W3 §DESCATTRIB DA4.1;
    # `tables.attributed_descriptions`).
    #
    # Audit B10 (I05): on a CREDIT section the flush printed below a row's
    # amount is read by the same count (`_block_below_is_one`), so a credit
    # carries the originator the bank printed under its `Preauthorized Credit`
    # label; a credit whose block the count cannot attribute is marked as read
    # only by its label. Debit sections keep their labels until the owner
    # admits the debit readings (G7).
    #
    # Audit round 2, R2-B07 (R07): a marked credit also keeps the text of the
    # flush it was marked at (`Transaction.unread_payer_text`), kept apart from
    # its description because the flush is several rows' blocks welded
    # together, so the true-revenue pass can hold a run that prints a lender's
    # block. Credit sections only: a debit keeps its label and no text (G7).
    credit_text = category.credit and not category.serialled
    unread: list[list[bool]] = []
    unread_text: list[list[str]] = []
    described = attributed_descriptions(
        [cells for _run, cells in read],
        strip=_DESCRIPTION_FURNITURE, limit=_DESCRIPTION_LIMIT,
        below=_block_below_is_one if credit_text else None,
        unread=unread,
        unread_text=unread_text if credit_text else None,
    )
    if len(unread) != len(read):
        unread = [[False] * len(cells) for _run, cells in read]
    if len(unread_text) != len(read):
        unread_text = [[""] * len(cells) for _run, cells in read]
    for (run, cells), texts, marks, flushes in zip(read, described, unread, unread_text):
        cursor = 0
        for index, cell in enumerate(cells):
            iso = iso_within_period(cell.date.replace("-", "/"), start, end)
            amount = _magnitude(cell.value)
            if iso is None or amount is None:
                return None
            # Everything printed since the PREVIOUS row's amount, not since
            # its date: a gap reaching back to the previous date would still
            # hold that row's amount, and on the cheque grid that amount would
            # be read as this row's serial.
            lead, cursor = run[cursor : cell.start], cell.end
            if category.serialled:
                serial = _SERIAL_RE.fullmatch(_row_lead(lead))
                description = f"{category.default} {serial.group(1)}" if serial \
                    else category.default
            else:
                description = texts[index] or category.default
            postings.append(Transaction(
                date=iso,
                description=description,
                amount=round(amount if category.credit else -amount, 2),
                direction="credit" if category.credit else "debit",
                payer_text_unread=category.credit and marks[index],
                unread_payer_text=flushes[index] if credit_text and marks[index] else "",
            ))
    return postings


#: Audit B10 (I05): the ACH standard entry class codes this template prints as
#: the LAST field of every ACH block (`<originator> <entry> <id> <receiver>
#: CCD`): layout grammar, never a payer's name.
#:
#: Audit round 3, R3-B09 (R3-87): a class-code word followed by a legal form
#: is part of a name, never a code (CashArc's ACH company name prints
#: `CASH-ARC LLC`), whatever the case of the form and the separator before it,
#: so a lone block of such a name is one block and is attributed. The
#: true-revenue pass splits an unread run by the same rule
#: (`true_revenue._UNREAD_BLOCK_END`).
_ACH_CLASS_CODE = re.compile(
    r"(?<![A-Za-z0-9])(?:CCD|CTX|PPD|WEB|IAT|TEL|POP|ARC|BOC|RCK|CIE)(?![A-Za-z0-9])"
    r"(?![ \t]+(?i:LLC|L\.L\.C|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC)"
    r"(?![A-Za-z0-9]))"
)


def _block_below_is_one(lines: list[str]) -> bool:
    """Audit B10 (I05): a flush printed below a row's amount, read when that row
    alone is outstanding (`tables.attributed_descriptions`), is one block on
    this template only when it is ONE line holding at most one ACH class code.
    The layer welds several rows' blocks onto one line with a single space, and
    it can flush the blocks of rows whose dates open BELOW, after a row printed
    alone on its line (measured on the archive's debits), so the count alone
    does not prove the line is this row's; the class code each ACH block closes
    on does, where it prints once."""
    return len(lines) == 1 and len(_ACH_CLASS_CODE.findall(lines[0])) <= 1


def _grid(runs: list[str], *, seed: date, end: date) -> dict[str, float] | None:
    """The `DAILY BALANCES` grid as a day-to-balance map, or None.

    Read over `[seed, end]` rather than over the period, because this
    template's grid OPENS on the day the last statement closed — the day the
    opening balance is a balance on, and the platform's own second printing of
    it.

    A day printed TWICE refuses the document rather than overwriting the first
    reading. That is not the sibling's rule and the difference is this
    template's own: it prints its grid in four columns whose cells arrive out
    of document order (a `2-23` cell after the `2-26` one), so a duplicate day
    is evidence the column recovery went wrong, and a map that silently kept
    the last one would hide it.
    """
    printed: dict[str, float] = {}
    for run in runs:
        cells = dated_cells(run, date_pattern=_DATE_RE, value_pattern=_BALANCE_RE)
        if cells is None:
            return None
        for cell in cells:
            iso = iso_within_period(cell.date.replace("-", "/"), seed, end)
            balance = _balance(cell.value)
            if iso is None or balance is None or iso in printed:
                return None
            printed[iso] = balance
    return printed


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------

def _matches_the_printed_partition(
    ledger: dict[str, list[Transaction]], summary: _Summary
) -> bool:
    """Every printed count, every printed total, and both direction sums.

    Fourteen comparisons over eight independent printings: six counts, six
    category totals, and the two direction totals the bank prints as well as
    the parts. The direction check is independent of the category checks
    because the bank prints both — a scan that mangled one category's total
    into another's would satisfy neither.
    """
    for category in _CATEGORIES:
        rows = ledger.get(category.label, [])
        if len(rows) != summary.counts[category.label]:
            return False
        if abs(sum(abs(row.amount) for row in rows)
               - summary.totals[category.label]) > 0.005:
            return False
    for credit, printed in ((True, summary.credits), (False, summary.debits)):
        parts = sum(summary.totals[category.label] for category in _CATEGORIES
                    if category.credit is credit)
        if abs(parts - printed) > 0.005:
            return False
    identity = summary.beginning + summary.credits - summary.debits
    return abs(identity - summary.ending) <= 0.005


def _matches_the_printed_grid(
    rows: list[Transaction], printed: dict[str, float], summary: _Summary
) -> bool:
    """The grid, walked against the ledger, in both directions.

    Three independent things at once:

    * the grid's PRE-PERIOD cell is the platform's second printing of the
      opening balance, so it is compared against the summary's;
    * every day the grid prints equals the walked end-of-day balance;
    * every day the ledger posts on appears in the grid, so neither a day the
      reader invented nor a day it lost can pass.
    """
    walked = {summary.seed: summary.beginning}
    running = summary.beginning
    for row in sorted(rows, key=lambda item: item.date):
        running = round(running + row.amount, 2)
        walked[row.date] = running
    if set(printed) != set(walked):
        return False
    return all(abs(walked[day] - balance) <= 0.005 for day, balance in printed.items())


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

#: A product name this template could plausibly print. The slot is the line
#: directly above the summary heading, and the bound is what keeps a
#: disclosure paragraph out of it if an issuer ever prints one there — the
#: eight archive documents print `Analyzed Business Checking`, 26 characters.
_PRODUCT_NAME_LIMIT = 60


def _product_name(markdown: str) -> str | None:
    """The product name printed directly above the summary heading, or None.

    A line that is one token sequence REPEATED is declined rather than
    collapsed. This processor's text layer emits a line up to four times over
    — fill, stroke and two shadows of one printed string — and publishing
    `Checking For Small Business Checking For Small Business …` publishes a
    name no statement carries, while collapsing it is a repair. The label is
    lost, the document is not.
    """
    at = markdown.find(_SUMMARY_HEADING)
    if at < 0:
        return None
    above = markdown[: markdown.rfind("\n", 0, at) + 1].rstrip("\n")
    line = re.sub(r"\s+", " ", above[above.rfind("\n") + 1:].strip())
    words = line.split()
    if not words or not line[:1].isalpha() or len(line) > _PRODUCT_NAME_LIMIT:
        return None
    if any(len(words) % size == 0 and words == words[:size] * (len(words) // size)
           for size in range(1, len(words) // 2 + 1)):
        return None
    return line


def parse_core_processor_counted_statement(markdown: str) -> Statement | None:
    """Any issuer's statement on the counted-partition grammar of this
    processor.

    Declines — rather than guesses — in six named situations, each a fact
    about the document rather than a gap in this reader:

    * it prints no `Account Summary` partition, or one with a hole in it;
    * its two printed account numbers disagree, which is a document carrying
      more than one account;
    * its dated balances disagree with its two printed statement dates;
    * a row's date or amount is not readable as one, or a row prints no amount
      before the next row starts;
    * any printed count or total disagrees with the section it heads;
    * the grid is absent, prints a day twice, or disagrees with the walked
      ledger. The grid is REQUIRED: it is the only per-day evidence there is.
    """
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    if summary is None:
        return None

    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    seed = date.fromisoformat(summary.seed)
    if end < start:
        return None

    sections = section_runs(markdown, _SECTION_RE)
    ledger: dict[str, list[Transaction]] = {}
    for category in _CATEGORIES:
        found = _rows(sections.get(category.heading, []), category=category,
                      start=start, end=end)
        if found is None:
            return None
        ledger[category.label] = found

    if not _matches_the_printed_partition(ledger, summary):
        return None

    rows = [row for category in _CATEGORIES for row in ledger[category.label]]
    printed = _grid(sections.get(_GRID_HEADING, []), seed=seed, end=end)
    if printed is None or not _matches_the_printed_grid(rows, printed, summary):
        return None

    return Statement(
        #: The template prints no institution FIELD — see the module docstring.
        bank=None,
        account_name=_product_name(markdown),
        account_number=summary.account,
        period_start=summary.start,
        period_end=summary.end,
        #: Deliberately absent: this grammar prints no day count, and the
        #: canonical ADB denominator is the printed period's calendar days,
        #: which `analysis/adb.py` derives for itself.
        days_in_period=None,
        beginning_balance=summary.beginning,
        ending_balance=summary.ending,
        stated_total_credits=summary.credits,
        stated_total_debits=summary.debits,
        stated_credit_count=sum(summary.counts[category.label]
                                for category in _CATEGORIES if category.credit),
        stated_debit_count=sum(summary.counts[category.label]
                               for category in _CATEGORIES if not category.credit),
        bank_reported_average_balance=summary.average,
        bank_reported_average_label="Average balance" if summary.average is not None else None,
        #: The pre-period cell is a real printing and it IS used as a gate,
        #: but the field's contract is IN-PERIOD snapshots and the ADB engine
        #: treats an out-of-period one as a defect of the statement. It is
        #: opening state, never a denominator day (ADB doctrine, 2026-08-15).
        stated_daily_balances=[
            StatementDailyBalance(date=day, balance=balance)
            for day, balance in sorted(printed.items()) if day != summary.seed
        ],
        transactions=sorted(rows, key=lambda row: row.date),
    )
