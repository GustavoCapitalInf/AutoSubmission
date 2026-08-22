"""A third core processor's template, read without naming a bank.

Ocean's card called these documents a printed VARIANT of the second core
processor's template (W3 §SCANB S9.9): the same platform, printing its period
line in sentence case with long-form dates instead of the hard
`mm/dd/yy THROUGH mm/dd/yy` form `core_processor_sectioned._PERIOD_RE`
requires. The characterization says otherwise, and says it in every part of
the document except the period sentence — so this is a new registration rather
than a widened period grammar. §LCPERIOD L2 holds the measurement; the short
form is the table below.

=======================  ==================================  ==================================
printing                 `core_processor_sectioned`          this template
=======================  ==================================  ==================================
period                   `TOTAL DAYS IN STATEMENT PERIOD     `Last statement: March 31, 2026`
                         03/31/26 THROUGH 04/30/26: 30`      `This statement: April 30, 2026`
                                                             `Total days in statement period: 30`
summary                  `N CREDITS <total>` / `M DEBITS`    `Total additions` / `Total
                         — COUNTS and totals                 subtractions` — totals, NO counts
opening / closing        `LAST STATEMENT mm/dd/yy <fig>`     `Beginning balance $<fig>` /
                         `THIS STATEMENT mm/dd/yy <fig>`     `Ending balance $<fig>`
account heading          `<PRODUCT> ACCOUNT <number>`        `Account number <number>`
ledger sections          `DEPOSITS` `OTHER CREDITS`          `DEBITS` `CREDITS` `CHECKS`
                         `OTHER DEBITS` `CHECKS`
grid                     `DAILY BALANCE`                     `DAILY BALANCES`
row date                 `m/d`                               `mm-dd`
issuer field             the institution slot, bounded by    none — see `_issuer_is_not_printed`
                         `PAGE:` on the right
=======================  ==================================  ==================================

Not one grammar is shared. Widening the other module's period line would have
made it CLAIM these 20 documents on its two required markers — the summary
labels match, because `Last statement:` upper-cases to a string containing
`LAST STATEMENT` — and then decline all 20 at `parse`, which is a detector
that lies. Worse, three of the 20 are already read by `b1` and the second
claim would have resolved them `ambiguous`: a validated document to review, a
regression, from a card whose whole purpose was recall.

The template
------------
Every document of it prints, in this order:

    Last statement: <Month D, YYYY>  This statement: <Month D, YYYY>
    Total days in statement period: N
    Direct inquiries to: <telephone>
    <product name>
    Account number <number> [Enclosures N] [Low balance $<fig>]
        [Average balance $<fig>] [Avg collected balance $<fig>]
    Beginning balance $<fig>  Total additions <fig>
        Total subtractions <fig>  Ending balance $<fig>

then its ledger as named sections — `CHECKS`, `DEBITS`, `CREDITS` — and a
`DAILY BALANCES` grid of end-of-day balances that OPENS on the day before the
period, carrying the opening balance.

Two printed issues share that furniture, exactly as on the other two core
processors. This module reads the SECTIONED one. The other prints one
running-balance ledger under `DAILY ACTIVITY`, closed by an `Ending totals`
row, and is read by an issuer-specific registration (`b1`) that supersedes
this one — the same relationship `first_farmers` has to
`core_processor_sectioned` and the four issuer readers have to
`community_section`. This module claims that issue too, because it is the same
platform on the same furniture, and then declines it at `parse`: it prints no
`Total additions`, so the summary this reader gates on does not exist.

What the document has to prove before anything is published
-----------------------------------------------------------
This platform prints NO transaction counts, so §SCANB's first gate is simply
not available here. What it prints instead is a per-day grid that OPENS on the
opening balance, and that turns out to be the stronger evidence: a dropped row
breaks its direction's total AND every grid day after it, where a count check
sees only the count. Five printings, all of them, exactly:

1. the row total in each direction equals the total the summary prints;
2. `beginning + additions - subtractions == ending`, the summary's identity;
3. the grid's PRE-PERIOD day equals the printed beginning balance — the
   platform's own second printing of it;
4. every in-period day of the grid equals the end-of-day balance of the walked
   ledger, and every day the ledger posts on appears in the grid;
5. the printed day count equals the span the two printed statement dates
   describe.

A document that cannot satisfy all of them publishes nothing.

**The gate set's blind spot, named rather than left to be found.** Move value
between two rows that share a date and a direction and every one of the five
still holds; so does splitting one row into two on the same day and direction,
which a count check WOULD catch and this platform gives us no count to check.
Both are forgery signatures rather than OCR ones — a scan drops a row or
mangles a digit, which moves a total and every subsequent grid day — and
claiming this reader can separate a forged ledger from an honest one would be
the overstatement this record exists to avoid.

Look-alike glyphs are refused rather than absorbed
--------------------------------------------------
The same law as §SCANB S5, with one correction to its rationale and one
addition this template's row date forces. Every date and money token is
matched with an explicit `[0-9]` class and with boundaries on BOTH sides that
forbid the token from starting or ending inside another one.

The correction: §SCANB S5 says the Unicode-aware digit class "publishes a
figure the bank never printed" because it admits digits from other scripts.
Measured, it does admit them — and Python's `int()` and `float()` then map
every one of them to its own numeric value, so the Unicode class reads
`٢٥٠.00` as 250.00 and publishes exactly what the ASCII class publishes. The
ASCII class is therefore a CONSERVATISM, not the guard S5 credits it with
(§LCPERIOD L6.1).

The figure the bank never printed comes from the BOUNDARY, not from the class,
and finding that is what this correction was worth: with §SCANB's boundary
class the same `٢٥٠.00` matches the bare sub-dollar alternative `.00` and
publishes 0.00. The boundary classes here are `\\w` for exactly that reason
(§LCPERIOD L6.2).

What the archive's scans really substitute is LETTERS — a leading zero read as
`o`, a Cyrillic `Е` inside `DATE` — and both classes refuse those.

**The boundaries are the half that does the work**, and here they include the
hyphen, which is load-bearing in both directions. This template dates its rows
`mm-dd` and prints a card
purchase's own date inside the description as `mm-dd-yy`:

    04-02 ' Debit Card Purchase   -300.00
    MERCHANT PURCHASE TERMINAL 07615556
    XXXXXXXXXXXX1494 04-01-26 12:00 AM

Without the RIGHT-hand boundary `04-01` in the description is a posting date
and the row is published twice. Without the LEFT-hand one `01-26` in the same
token is another, and its month is 1 in a statement that never printed one —
a token the period cannot place, which this reader refuses the whole document
for. So the pair is not belt-and-braces: each half prevents a different
failure, one silent and one loud.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_from_named_month_day, iso_within_period
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
#: continued by one. Two things differ from §SCANB's form of the same rule and
#: both are deliberate:
#:
#: * the hyphen is in all three classes, because this template's row date is
#:   hyphenated and its descriptions carry hyphenated dates — see the module
#:   docstring;
#: * the classes are `\w`, not `[0-9A-Za-z]`. Measured: with the ASCII form,
#:   `٢٥٠.00` — an amount whose integer part OCR rendered in another script —
#:   matches the BARE sub-dollar alternative `.00`, because the character
#:   before the dot is not in `[0-9A-Za-z.,/-]`. The reader would publish 0.00
#:   where the bank printed 250.00, which is the exact failure the ASCII digit
#:   class is supposed to prevent, arriving through the BOUNDARY instead. `\w`
#:   closes it. Over the store the two forms publish the identical 13
#:   documents, so the stronger one costs nothing (§LCPERIOD L6.2).
_TOKEN_START = r"(?<![\w.,/-])"
_DATE_END = r"(?![\w/-])"
_FIGURE_END = r"(?![\w.,])"

#: `mm-dd`, the form every ledger row and every grid cell prints. The year is
#: not printed and is resolved against the statement period, which is the only
#: evidence of one.
_ROW_DATE = r"[0-9]{2}-[0-9]{2}"
#: `1,234.56`, and the bare `.56` a sub-dollar figure is printed as.
_FIGURE = r"(?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2})"

_DATE_TOKEN = _TOKEN_START + r"(" + _ROW_DATE + r")" + _DATE_END
#: A LEDGER figure. Unsigned, because every amount this template prints in a
#: section is a MAGNITUDE whose direction is the column it sits in. An amount
#: that arrived carrying a sign would contradict its own section, and refusing
#: to read one is right.
_FIGURE_TOKEN = _TOKEN_START + r"(" + _FIGURE + r")" + _FIGURE_END
#: A BALANCE figure. Signed, because a balance can be overdrawn and this
#: template prints that as `$-210.46`. `MINUS_CLASS` rather than a literal
#: `-` so the shared money grammar's glyph set applies here too.
_BALANCE = MINUS_CLASS + r"?" + _FIGURE
_BALANCE_TOKEN = _TOKEN_START + r"(" + _BALANCE + r")" + _FIGURE_END

#: The same three tokens, compiled, for `tables.dated_cells` — which takes the
#: caller's patterns rather than owning a grammar of its own.
_DATE_RE = re.compile(_DATE_TOKEN)
_FIGURE_RE = re.compile(_FIGURE_TOKEN)
_BALANCE_RE = re.compile(_BALANCE_TOKEN)


def _magnitude(value: str) -> float | None:
    """A printed section figure as a positive number, or None.

    `pad_leading_decimal` first, because this platform prints a sub-dollar
    figure as `.00`; `STRICT_UNSIGNED` because a section figure is a magnitude
    whose direction is its column.
    """
    return parse_amount(pad_leading_decimal(value), STRICT_UNSIGNED)


def _balance(value: str) -> float | None:
    """A printed balance as a number, or None.

    Overdrawn balances print a LEADING minus and nothing on this template
    prints a trailing one, so the leading form is the only one admitted — a
    trailing-minus token here would be a figure from some other layout.

    The padding is applied before the sign is read, which leaves one printing
    unread: a negative sub-dollar balance (`$-.55`) pads to nothing and is
    refused. No document in the store prints one — measured — and the refusal
    is fail-closed, so it costs a document rather than publishing a wrong
    figure. Carded at §LCPERIOD L7.5.
    """
    return parse_amount(pad_leading_decimal(value), LEADING_MINUS)


# ---------------------------------------------------------------------------
# Detection: the template's own furniture, and nothing about an issuer
# ---------------------------------------------------------------------------

#: The period sentence, in the three pieces the template prints it in. They are
#: read SEPARATELY rather than as one phrase because one issuer's text layer
#: interleaves the page and account fields between them:
#:
#:     Last statement: April 15, 2026 Page 1 of 9 This statement: May 15, 2026
#:     XXXXXX5074 Total days in statement period: 30
#:
#: A contiguous pattern reads that document as not printing a period at all.
_LONG_DATE = r"([A-Z][a-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})"
_OPENING_DATE_RE = re.compile(r"Last statement:\s+" + _LONG_DATE)
_CLOSING_DATE_RE = re.compile(r"This statement:\s+" + _LONG_DATE)
_DAYS_RE = re.compile(r"Total days in statement period:\s*([0-9]{1,3})(?![0-9])")

#: The platform's own contact field. Coextensive with the period sentence on
#: this archive — all 20 documents that print the sentence print this, and the
#: one document that prints this without the sentence is the same platform's
#: other printed issue — so it corroborates rather than gates.
_CONTACT_FIELD = "Direct inquiries to:"

#: **Case is load-bearing and this registration therefore has no
#: normalization.** Sentence case is what separates this template's period
#: sentence from `core_processor_sectioned`'s upper-case period line, and an
#: upper-casing normalization would make the two indistinguishable. Measured
#: over the 3,396 documents of the D-3 artifact store with offline text: the
#: two required markers below are satisfied by exactly 20 documents, every one
#: of them this platform, with no near miss — and by neither of the two
#: documents that print `Total Days in Statement Period` in title case, which
#: are a different platform entirely (§LCPERIOD L2.1).
DETECTION_MARKERS = (
    required(
        "platform_period_endpoints",
        lambda t: bool(_OPENING_DATE_RE.search(t)) and bool(_CLOSING_DATE_RE.search(t)),
    ),
    required("platform_period_days", lambda t: bool(_DAYS_RE.search(t))),
    corroborating("platform_contact_field", lambda t: _CONTACT_FIELD in t),
)

detect = make_detector(DETECTION_MARKERS)


# ---------------------------------------------------------------------------
# The issuer, which this template does not print in a field
# ---------------------------------------------------------------------------

#: Why `Statement.bank` is None on every document this reader publishes.
#:
#: The SCAN-B hardening is that an issuer is published only from an arrangement
#: in which the TEMPLATE bounds the name on BOTH sides, attested and fixtured;
#: anything else is None, because a wrong name is worse than no name. This
#: template offers two candidate fields and neither is one:
#:
#: * the masthead line under the contact field prints the institution and then
#:   its address, with nothing between them:
#:
#:       Direct inquiries to: 833-896-2850
#:       Enterprise Bank & Trust PO Box 66940 St Louis MO 63166
#:
#:   Left edge only. This is precisely the wrapped-field arrangement §SCANB S3
#:   refused: a digit rule ends `El Dorado Savings Bank 4040 El Dorado Road` in
#:   the right place and ends `Enterprise Bank & Trust PO Box 66940` in the
#:   wrong one, and the difference is which word of the address happens to
#:   carry the first digit. Worse here than there — one issuer prints the
#:   holder's own address block between the contact field and its own;
#: * the closing courtesy sentence IS bounded on both sides — by the template's
#:   phrase on the left and by the end of the line on the right — and it is
#:   still not an institution field, because what the sentence names is
#:   whatever the issuer chose to put in it. Measured over the store, the same
#:   sentence yields `us.`, `United!` and — on eight documents of this
#:   platform's own sibling arrangement — `Orange CO Airport Office`, which is
#:   a BRANCH. A slot that names a branch on a sibling layout is prose, not a
#:   field, and reading it would publish a wrong name for a real bank.
#:
#: So `bank=None`, under the honest-unknown-issuer ruling of 2026-08-14: the
#: arithmetic does not depend on the label, so an unnamed issuer costs a label
#: rather than a document. The three documents whose issuer IS published on
#: this platform are `b1`'s, and they keep their label because `b1` supersedes
#: this registration.
_issuer_is_not_printed = None


# ---------------------------------------------------------------------------
# The printed summary
# ---------------------------------------------------------------------------

#: The account field. The number is printed masked (`XXXXXX6480`) by two
#: issuers and in full by a third, so the class admits both; the boundary is
#: what stops it reading the first four digits of a longer run.
_ACCOUNT_RE = re.compile(r"Account number\s+([Xx*0-9]{4,})(?![0-9])")

#: The summary's four figures. Each label is matched with the figure that
#: follows it directly, with no line anchoring, because one issuer's text
#: layer prints the strip as one line and another's as two interleaved
#: columns:
#:
#:     Account number XXXXXX5074   Beginning balance $1,614.92
#:     Low balance $311.45         Total additions 253,668.46
#:
#: The two BALANCE labels take the `$` the template prints; the two TOTAL
#: labels do not print one. Requiring what is printed and nothing else is what
#: makes the pattern refuse a label whose figure OCR lost.
_BEGINNING_RE = re.compile(r"Beginning balance\s+\$" + _BALANCE_TOKEN)
_ENDING_RE = re.compile(r"Ending balance\s+\$" + _BALANCE_TOKEN)
_ADDITIONS_RE = re.compile(r"Total additions\s+" + _FIGURE_TOKEN)
_SUBTRACTIONS_RE = re.compile(r"Total subtractions\s+" + _FIGURE_TOKEN)

#: The period's average, printed undated beside the balances. Published as
#: `stated_average_balance` because it is the bank's own figure; it gates
#: nothing, which is what leaves it free to be an independent opinion on the
#: average this platform computes. The `$` is required: the same two words open
#: `Average balance for APY $12,992.17` in the interest block, which is a
#: different statistic, and the `$` is what tells them apart without this
#: module holding a list of statistic names.
_AVERAGE_RE = re.compile(r"Average balance\s+\$" + _BALANCE_TOKEN)

#: The ledger's section headings, and the two blocks the template prints AFTER
#: the grid. The latter are in the list as BOUNDARIES, not as sections: without
#: them the grid's block runs to the end of the document and the interest
#: block's dated figures would be read as grid days. §SCANB S9.2 carded that
#: exposure on the other template; here the template names the blocks, so it
#: can be closed rather than carded.
_SECTION_NAMES = (
    "OVERDRAFT/RETURN ITEM FEES", "INTEREST INFORMATION",
    "DAILY BALANCES", "CREDITS", "DEBITS", "CHECKS",
)
#: Case-SENSITIVE on purpose, and for the same reason as on the other core
#: processor: the template prints its section names in capitals and the
#: disclosures below print the same words in prose.
_SECTION_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in _SECTION_NAMES) + r")\b")


class _Summary:
    """The figures the summary strip prints."""

    __slots__ = ("start", "end", "days", "beginning", "ending",
                 "additions", "subtractions", "average")

    def __init__(self, **fields) -> None:
        for name, value in fields.items():
            setattr(self, name, value)


#: The one reading of a summary row, or None. Shared with the second core
#: processor's template (W3 §LCPERIOD L5.2) — both had a byte-identical copy,
#: and `tests/test_no_parser_helper_clones.py` is what said so.
_once = unique_match


def _long_date(match: re.Match[str]) -> str | None:
    """`("April", "30", "2026")` as an ISO date, or None if it is not one.

    The pattern proves the SHAPE and nothing more: `Fiscal 30, 2026` has that
    shape, and so does `February 31, 2026`.

    The reading itself is `date_tokens.iso_from_named_month_day`, which is
    where it always belonged: this module had re-derived the shared helper's
    two lines, and the clone became visible when the fourth grammar of the
    same processor needed the same reading (W3 §GRAM4). Behaviour-identical —
    the helper case-folds the month word and funnels through `iso_or_none`
    exactly as the copy did.
    """
    return iso_from_named_month_day(match.group(1), match.group(2), match.group(3))


def _front_matter(markdown: str) -> str:
    """Everything the statement prints before its ledger begins.

    Scoped because the period sentence is page-1 furniture and the ledger below
    it is 20 pages of descriptions the bank did not write.
    """
    section = _SECTION_RE.search(markdown)
    return markdown[: section.start()] if section else markdown


def _period(front: str) -> tuple[str, str, int] | None:
    """`(start, end, printed days)`, or None.

    The two printed dates are the dates of the two STATEMENTS, not of the
    period: the period opens the day after the last statement closed. That is
    the platform's own convention and the grid confirms it on every document —
    the grid's first cell is dated the day the last statement closed and
    carries the opening balance.
    """
    opening = _once(front, _OPENING_DATE_RE)
    closing = _once(front, _CLOSING_DATE_RE)
    days = _once(front, _DAYS_RE)
    if not (opening and closing and days):
        return None
    previous, end = _long_date(opening), _long_date(closing)
    if previous is None or end is None:
        return None
    start = (date.fromisoformat(previous) + timedelta(days=1)).isoformat()
    return start, end, int(days.group(1))


def _summary_region(markdown: str) -> str | None:
    """The summary strip alone: from the account field to the ledger."""
    account = _ACCOUNT_RE.search(markdown)
    if not account:
        return None
    rest = markdown[account.end():]
    section = _SECTION_RE.search(rest)
    return rest[: section.start()] if section else rest


def _summary(markdown: str) -> _Summary | None:
    """Every figure the summary strip prints, or None if any is missing.

    A strip with a hole in it yields None rather than a partly-filled summary:
    every gate below compares the published ledger against these figures, so a
    missing one would weaken the gate instead of failing it.
    """
    period = _period(_front_matter(markdown))
    region = _summary_region(markdown)
    if period is None or region is None:
        return None
    start, end, days = period
    rows = [_once(region, pattern) for pattern in
            (_BEGINNING_RE, _ENDING_RE, _ADDITIONS_RE, _SUBTRACTIONS_RE)]
    if any(row is None for row in rows):
        return None
    beginning, ending = _balance(rows[0].group(1)), _balance(rows[1].group(1))
    additions, subtractions = _magnitude(rows[2].group(1)), _magnitude(rows[3].group(1))
    if None in (beginning, ending, additions, subtractions):
        return None
    average = _once(region, _AVERAGE_RE)
    return _Summary(
        start=start, end=end, days=days,
        beginning=beginning, ending=ending,
        additions=additions, subtractions=subtractions,
        average=_balance(average.group(1)) if average else None,
    )


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

# A row of any section is a posting date, then — in the two described sections
# — the description the bank printed between the date and the amount, then the
# amount. `_rows` finds it as TWO tokens rather than as one pattern with the
# description inside, because the description runs onto the lines BELOW the
# amount on most rows and a greedy pattern would swallow the next row. It also
# lets two rows share one line, which this platform prints
# (`04-21 Withdrawal 3,000.00 04-21 ' Outgoing Wire-Olb 10,000.00`) and a
# line-anchored pattern would silently halve.
#
# That scan is `tables.dated_cells`, shared with the FOURTH summary grammar of
# this same processor (W3 §GRAM4): both templates print a ledger grid and a
# daily-balance grid whose flattened text layer has lost its columns, and both
# recover a cell the same way — it opens at a date and closes at the first
# value printed before the next date. The patterns stay here; only the scan
# moved (§LCPERIOD L5.2's discipline, one template on).

#: A cheque's serial number. The cheque section prints a three-column grid —
#: `Number Date Amount` — so the serial is the row's LEADING token, and it is
#: read as the WHOLE of what the bank printed to the left of the date on that
#: row's own line. `fullmatch`, not a search anchored at the end.
#:
#: The difference is not stylistic. An end-anchored search over the whole gap
#: takes any trailing digits as a serial, and the review found three
#: constructions that do exactly that:
#:
#: * `Continued on page 27` between two rows publishes `Check 27`;
#: * a masked account number in the page furniture publishes `Check 0000`;
#: * a gap longer than the description truncation splits a serial mid-token
#:   and publishes `765432` where the bank printed `7654321` — a WRONG number
#:   rather than a missing one, which is the worst of the three.
#:
#: None of them is reachable on today's archive (the family prints one cheque
#: row, and it is serialled), and all three are pinned below. The structural
#: read costs nothing and cannot be reached by furniture at all, because
#: furniture is never a bare digit run alone on a row's line.
#:
#: The platform marks a break in the serial sequence with a trailing `*`.
_SERIAL_RE = re.compile(r"([0-9]{2,8})\s*\*?")

#: The ledger's sections, with the direction each one's rows are postings in —
#: which is the COLUMN the bank printed the row in, never the sign of the
#: amount — and the description to publish where the section prints none.
#: `None` marks the cheque section: its rows are debits, and the text before
#: each one is a serial rather than a description.
_LEDGER_SECTIONS = (
    ("CREDITS", True, "Credit"),
    ("DEBITS", False, "Debit"),
    ("CHECKS", None, "Check"),
)


def _sections(markdown: str) -> dict[str, list[str]]:
    """The document's ledger, split on the platform's own section headings.

    The split itself is `tables.section_runs`, shared with the second core
    processor's template (W3 §LCPERIOD L5.2). Here a section broken across a
    page reprints its column header but not its heading, so most sections are
    one run; the two blocks the template prints AFTER the grid are in
    `_SECTION_NAMES` as boundaries, and it is `section_runs` treating every
    heading as a run boundary that makes them close the grid.
    """
    return section_runs(markdown, _SECTION_RE)


#: What this template prints as furniture around a description rather than as
#: part of it. The apostrophe is the platform's own column rule: it prints
#: `04-01 ' Outgoing Wire-Olb` and the quote is not part of the label.
_DESCRIPTION_FURNITURE = " '.-|*"
#: The longest description this reader will publish. A bound has to exist — a
#: span the layer filled with a page of furniture is not a description — and
#: `tables.attributed_descriptions` cuts at a token boundary rather than
#: through a word, because half a token is a string the bank did not print.
#: No row of this reader's 13 validated documents comes near it: every one of
#: them prints its whole description on the row's own line and its merchant
#: block BELOW the amount, where no row's span can reach (W3 §DESCATTRIB DA3).
_DESCRIPTION_LIMIT = 200


def _row_lead(gap: str) -> str:
    """What the bank printed to the left of a row's date on that row's OWN
    line — the leading cell of the printed grid, and nothing above it.

    Everything before the last newline is a different printed line: a column
    header, a page break's furniture, the previous row. Scoping to the line is
    what makes `_SERIAL_RE`'s `fullmatch` a structural read of a grid cell
    rather than a hunt for digits in a gap.
    """
    return gap[gap.rfind("\n") + 1:].strip(" |\t")


def _rows(runs: list[str], *, credit: bool | None, start: date, end: date,
          default: str) -> list[Transaction] | None:
    """Every posting a section printed, or None if one of them is unreadable.

    None rather than "skip" on purpose. A row whose date the period cannot
    place, or that prints no amount before the next row begins, is a row we
    could not read — and dropping it silently is exactly how a ledger comes to
    disagree with a printed total by one row while still looking complete.
    """
    rows: list[Transaction] = []
    for run in runs:
        cells = dated_cells(run, date_pattern=_DATE_RE, value_pattern=_FIGURE_RE)
        if cells is None:
            return None
        cursor = 0
        # The descriptions are read for the RUN, not for a row at a time: what
        # a row's span owns depends on how many rows' merchant blocks the
        # flattened layer still had in hand when it flushed into that span
        # (W3 §DESCATTRIB; `tables.attributed_descriptions`). This template
        # prints its blocks below the amount rather than inside the span, so
        # the rule attributes nothing here — and that is a measurement, not an
        # assumption: the same call is what the sibling grammar needs.
        described = attributed_descriptions(
            cells, strip=_DESCRIPTION_FURNITURE, limit=_DESCRIPTION_LIMIT)
        for index, cell in enumerate(cells):
            iso = iso_within_period(cell.date.replace("-", "/"), start, end)
            amount = _magnitude(cell.value)
            if iso is None or amount is None:
                return None
            # Everything printed since the PREVIOUS row's amount, not since its
            # date: the cheque section's serial is the leading cell of this
            # row, and a gap that still held the previous row's amount would
            # put that amount on this row's line.
            gap, cursor = run[cursor : cell.start], cell.end
            if credit is None:
                serial = _SERIAL_RE.fullmatch(_row_lead(gap))
                description = f"{default} {serial.group(1)}" if serial else default
            else:
                description = described[index] or default
            rows.append(Transaction(
                date=iso,
                description=description,
                amount=round(amount if credit else -amount, 2),
                direction="credit" if credit else "debit",
            ))
    return rows


def _grid(runs: list[str], *, seed: date, end: date) -> list[StatementDailyBalance] | None:
    """The `DAILY BALANCES` grid, as printed.

    Read over `[seed, end]` rather than over the period, because this
    template's grid OPENS on the day the last statement closed — the day the
    opening balance is a balance on. `_matches_the_printed_grid` is what then
    uses that first cell as the platform's own second printing of the opening
    figure.
    """
    printed: list[StatementDailyBalance] = []
    for run in runs:
        cells = dated_cells(run, date_pattern=_DATE_RE, value_pattern=_BALANCE_RE)
        if cells is None:
            return None
        for cell in cells:
            iso = iso_within_period(cell.date.replace("-", "/"), seed, end)
            amount = _balance(cell.value)
            if iso is None or amount is None:
                return None
            printed.append(StatementDailyBalance(date=iso, balance=amount))
    return printed


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------

def _matches_the_printed_summary(rows: list[Transaction], summary: _Summary) -> bool:
    """Both printed totals, and the identity that ties them to the balances."""
    credits_ = sum(row.amount for row in rows if row.direction == "credit")
    debits = -sum(row.amount for row in rows if row.direction == "debit")
    if abs(credits_ - summary.additions) > 0.005:
        return False
    if abs(debits - summary.subtractions) > 0.005:
        return False
    identity = summary.beginning + summary.additions - summary.subtractions
    return abs(identity - summary.ending) <= 0.005


def _matches_the_printed_grid(
    rows: list[Transaction], printed: list[StatementDailyBalance],
    *, beginning: float, seed: str
) -> bool:
    """The grid, walked against the ledger, in both directions.

    Three things at once, and they are independent of the totals above:

    * the grid's PRE-PERIOD cell is the platform's own second printing of the
      opening balance, so it is compared against the summary's;
    * every day the grid prints must equal the walked end-of-day balance;
    * every day the ledger posts on must appear in the grid, so neither a day
      the reader invented nor a day it lost can pass.
    """
    walked: dict[str, float] = {seed: beginning}
    running = beginning
    for row in sorted(rows, key=lambda item: item.date):
        running = round(running + row.amount, 2)
        walked[row.date] = running
    if {entry.date for entry in printed} != set(walked):
        return False
    return all(abs(walked[entry.date] - entry.balance) <= 0.005 for entry in printed)


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

def _product_name(markdown: str) -> str | None:
    """The product name the statement prints above its account field, or None.

    The template prints it on its own line directly above `Account number`.
    On some documents this text layer emits that line FOUR times over — fill,
    stroke and two shadows of one printed string, which is also why the holder
    block above it reads `RABBIT TWISTER HOLDINGS, LLC` four times:

        Checking For Small Business Checking For Small Business Checking For
        Small Business Checking For Small Business

    The bank printed that once. Publishing it as printed publishes a name no
    statement carries; collapsing it is a REPAIR, and this wave refuses rather
    than repairs. So a line that is one token sequence repeated is declined —
    the label is lost, the document is not — and a line printed once is
    published exactly as it stands.
    """
    account = _ACCOUNT_RE.search(markdown)
    if account is None:
        return None
    above = markdown[: markdown.rfind("\n", 0, account.start()) + 1].rstrip("\n")
    line = above[above.rfind("\n") + 1:].strip()
    words = line.split()
    if not words or not line[:1].isalpha():
        return None
    for size in range(1, len(words) // 2 + 1):
        if len(words) % size == 0 and words == words[:size] * (len(words) // size):
            return None
    return re.sub(r"\s+", " ", line)


def parse_core_processor_daily_statement(markdown: str) -> Statement | None:
    """Any issuer's statement on the sectioned issue of this template.

    Declines — rather than guesses — in five named situations, each of which is
    a fact about the document rather than a gap in this reader:

    * it prints no account field, or no complete summary strip;
    * it prints the running-balance ledger instead of the sections. That issue
      has its own reader, which supersedes this registration;
    * the two printed statement dates do not span the printed number of days;
    * a row's date or amount is not readable as one, or a row prints no amount
      before the next row starts. A scanned issue of this template substitutes
      letters for digits, and a row read on the wrong day is worse than a
      document declined;
    * the ledger does not reproduce both printed totals, or disagrees with the
      printed daily-balance grid.
    """
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    if summary is None:
        return None

    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    if end < start or (end - start).days + 1 != summary.days:
        return None
    seed = start - timedelta(days=1)

    sections = _sections(markdown)
    if not sections.keys() & {name for name, _credit, _default in _LEDGER_SECTIONS}:
        return None

    rows: list[Transaction] = []
    for name, credit, default in _LEDGER_SECTIONS:
        block = sections.get(name)
        if block is None:
            continue
        found = _rows(block, credit=credit, start=start, end=end, default=default)
        if found is None:
            return None
        rows.extend(found)

    if not _matches_the_printed_summary(rows, summary):
        return None

    # The grid is REQUIRED, unlike the other core processor's. There it is a
    # second opinion on top of two printed counts; here the platform prints no
    # count at all, and the grid is the only per-day evidence there is. A
    # document whose grid heading a scan corrupted (`DALY BALANCES`) is a
    # document we can check two ways instead of five, and the honest answer to
    # that is the refusal.
    printed = _grid(sections.get("DAILY BALANCES", []), seed=seed, end=end)
    if printed is None or not _matches_the_printed_grid(
        rows, printed, beginning=summary.beginning, seed=seed.isoformat()
    ):
        return None

    account = _ACCOUNT_RE.search(markdown)
    return Statement(
        bank=_issuer_is_not_printed,
        account_name=_product_name(markdown),
        account_number=account.group(1) if account else None,
        period_start=summary.start,
        period_end=summary.end,
        days_in_period=summary.days,
        beginning_balance=summary.beginning,
        ending_balance=summary.ending,
        stated_total_credits=summary.additions,
        stated_total_debits=summary.subtractions,
        stated_average_balance=summary.average,
        #: The pre-period cell is deliberately NOT published. It is a real
        #: printing and it is already used as a gate, but the field's contract
        #: is in-period dated snapshots and the ADB engine treats an
        #: out-of-period one as a defect of the statement.
        stated_daily_balances=[entry for entry in printed
                               if entry.date != seed.isoformat()],
        transactions=sorted(rows, key=lambda row: row.date),
    )
