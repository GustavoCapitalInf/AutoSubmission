"""A core processor's SECTIONED statement template, read without naming a bank.

This is the second core-processor template the registry reads generically, and
it is registered the way W3 §JHA-CELL established for the first: on the
**template's own furniture**, with the **issuer read out of each document**.
The archive prints this one under five different issuers, and one of them —
the running-balance issue below — already has its own reader. Registering the
template per issuer would mean a new registration, a new marker pair and a new
fixture for every institution that ever buys the product, and would leave every
issuer nobody has met yet unread.

The template
------------
Every document of it prints, in this order:

    <product name> ACCOUNT <number>
    LAST STATEMENT mm/dd/yy <opening>  MINIMUM BALANCE <fig>  N CREDITS <total>
    AVG AVAILABLE BALANCE <fig>  M DEBITS <total>  AVERAGE BALANCE <fig>
    THIS STATEMENT mm/dd/yy <closing>
    TOTAL DAYS IN STATEMENT PERIOD mm/dd/yy THROUGH mm/dd/yy: N

then its ledger, as named sections — `DEPOSITS`, `OTHER CREDITS`, `CHECKS`,
`OTHER DEBITS` — and finally a `DAILY BALANCE` grid of end-of-day balances.

Two printed issues share that furniture. This module reads the SECTIONED one.
The other prints one running-balance ledger instead of the sections and is read
by an issuer-specific registration that supersedes this one, exactly as the four
issuer readers of the first core-processor template supersede its general form.
This module claims that issue too — it is the same platform, on the same
furniture — and then declines it at `parse`, because a ledger without sections
is not the ledger this reader knows how to walk.

What the document has to prove before anything is published
-----------------------------------------------------------
Five printed figures and one printed grid, all of them, exactly:

1. the row count in each direction equals the count the summary prints;
2. the row total in each direction equals the total the summary prints;
3. `opening + credits - debits == closing`, the summary's own identity;
4. where the document prints a `DAILY BALANCE` grid, every day in it equals
   the end-of-day balance of the walked ledger, and every day the ledger posts
   on appears in the grid.

They are five independent printings of the same period, so a dropped row, a
duplicated row or a mis-read amount breaks at least two of them. A document
that cannot satisfy all of them publishes nothing — and this template's scanned
issues routinely cannot, because OCR substitutes look-alike letters for digits
inside the date column (a leading zero read as a lower-case `o`), which drops
the row that carries it. That is a fact about the scan, not a gap in this
reader, and the honest answer is the refusal.

Look-alike glyphs are refused rather than absorbed
--------------------------------------------------
Every date and money token in this module is matched with an explicit `[0-9]`
class and a boundary that forbids the token from starting inside another one.
Both halves are load-bearing:

* `\\d` is Unicode-aware in Python and admits digits from other scripts, and
  this archive's documents really do carry look-alike codepoints — one issuer's
  column header prints `DATE` with a Cyrillic `U+0415`. A money grammar that
  reads a look-alike as a digit publishes a figure the bank never printed;
* without the boundary, a date whose leading zero OCR turned into a letter
  still matches one character in, as a single-digit month — and the
  glyph-corrupted row is then silently published on the wrong day. The
  boundary makes the corrupted row invisible instead, which the count check
  then catches.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day_year, iso_within_period
from .money import STRICT_UNSIGNED, pad_leading_decimal, parse_amount
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction

# ---------------------------------------------------------------------------
# The grammar
# ---------------------------------------------------------------------------

#: A token may not begin part-way through another token. `/` and `.` are in the
#: class so a date cannot start inside a longer date and an amount cannot start
#: inside a longer number; the letters are what refuse `o2/11`.
_TOKEN_START = r"(?<![0-9A-Za-z.,/])"
#: ...and may not be continued by one.
_DATE_END = r"(?![0-9/])"
_FIGURE_END = r"(?![0-9.,])"

#: `mm/dd/yy`, the form every summary and period line on this template prints.
_SHORT_DATE = r"[0-9]{2}/[0-9]{2}/[0-9]{2}"
#: `m/d`, the form every ledger row prints. The year is not printed and is
#: resolved against the statement period, which is the only evidence of one.
_ROW_DATE = r"[0-9]{1,2}/[0-9]{1,2}"
#: `1,234.56`, and the bare `.56` this platform prints for a sub-dollar figure.
_FIGURE = r"(?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2})"

_DATE_TOKEN = _TOKEN_START + r"(" + _ROW_DATE + r")" + _DATE_END
_FIGURE_TOKEN = _TOKEN_START + r"(" + _FIGURE + r")" + _FIGURE_END


def _figure(value: str) -> float | None:
    """A printed figure as a number, or None if it is not one.

    `pad_leading_decimal` first because this platform prints a sub-dollar
    figure as `.56`; `STRICT_UNSIGNED` because every figure it prints is a
    MAGNITUDE whose direction is the row or column it sits in. A summary total
    that arrived carrying a sign would contradict the row it is printed on, and
    refusing to read one is right.
    """
    return parse_amount(pad_leading_decimal(value), STRICT_UNSIGNED)


# ---------------------------------------------------------------------------
# Detection: the template's own furniture, and nothing about an issuer
# ---------------------------------------------------------------------------

#: The period line, which is this template's signature. Measured over the 3,396
#: documents in the D-3 artifact store that have offline text: it appears in 39
#: of them and every one is this platform — no near misses. It is nonetheless
#: composed with the summary-balance labels below rather than registered alone,
#: because a single phrase is a claim about this archive and a conjunction is a
#: claim about the template (R4-3, and the two-required-marker invariant in
#: tests/test_parser_conformance.py).
_PERIOD_RE = re.compile(
    r"TOTAL DAYS IN STATEMENT PERIOD\s+(" + _SHORT_DATE + r")\s+THROUGH\s+("
    + _SHORT_DATE + r")\s*:?\s*([0-9]{1,3})(?![0-9])"
)

#: The labels of the summary's two BALANCE rows. Both printed issues carry
#: them: the sectioned one prints `LAST STATEMENT`, the running-balance one
#: prints `BALANCE LAST STATEMENT`, and the substring is common to both — which
#: is what makes this a marker of the PLATFORM rather than of one of its
#: issues. On their own the two labels reach 152 archive documents; composed
#: with the period line above they reach exactly the 39, with nothing added and
#: nothing lost.
_OPENING_LABEL = "LAST STATEMENT"
_CLOSING_LABEL = "THIS STATEMENT"

#: The platform's own period statistic. Coextensive with the period line on
#: this archive (39 documents, the same 39), so it corroborates rather than
#: gates: an issuer that suppresses the statistic still prints the template.
_STATISTIC_LABEL = "AVG AVAILABLE BALANCE"


def detection_text(markdown: str) -> str:
    """This registration's normalization, held as registry data so the upper-
    casing runs once per document instead of once per marker (§JHA J11.3)."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("platform_period_line", lambda t: bool(_PERIOD_RE.search(t))),
    required(
        "summary_balance_labels",
        lambda t: _OPENING_LABEL in t and _CLOSING_LABEL in t,
    ),
    corroborating("period_statistics", lambda t: _STATISTIC_LABEL in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


# ---------------------------------------------------------------------------
# The issuer, read out of the document
# ---------------------------------------------------------------------------

#: The account heading: the product name the statement prints, then the word
#: the template separates it from the account number with, then the number.
#: The number is a masked run — OCR reads the mask as `X` or `x` — and the
#: product name is a token sequence that must START with a word, so it cannot
#: begin inside the page furniture printed before it on the same line (the
#: left-edge lesson of §JHA J4.5).
#: A product name STARTS with a word and may then carry short numbers
#: (`BUSINESS 150 CHECKING`) and the dash an issuer separates a regional
#: variant with (`No Minimum Business Checking - KY Region`). Spelling it as a
#: token sequence rather than as a run of permitted characters is what keeps
#: the left edge honest: no token can be a date, a masked account number or the
#: tail of an amount, so the name cannot begin inside the page furniture or
#: inside the figure printed before it (§JHA J4.5).
_NAME_WORD = r"[A-Za-z][A-Za-z&'./]*"
_NAME_TOKEN = r"(?:" + _NAME_WORD + r"|[0-9]{1,3}|-)"
_ACCOUNT_HEADING_RE = re.compile(
    r"(" + _NAME_WORD + r"(?: " + _NAME_TOKEN + r")*)\s+"
    r"ACCOUNT\s+([Xx0-9]{4,})(?![0-9])"
)

#: The platform's own page field. It CLOSES the institution slot: the routing
#: and batch codes stand between the institution's name and this, and the
#: name's right-hand bound is therefore the template's rather than a guess.
_PAGE_FIELD_RE = re.compile(r"\bPAGE\s*:", re.IGNORECASE)
#: The rest of that contact block. Required as corroboration: it is what says
#: the run of words at the top of the page is the issuer's own address block
#: and not something the page happens to open with.
_CONTACT_FURNITURE_RE = re.compile(r"\bTELEPHONE\s*:", re.IGNORECASE)

#: A word of an institution's name: letters and the punctuation a legal name
#: carries, plus a STANDALONE `&` — `FIRST FARMERS BANK & TRUST` is one name,
#: and a rule that stops at the ampersand publishes a DIFFERENT institution's
#: name rather than a shorter version of this one.
_ISSUER_WORD = r"(?:[A-Za-z][A-Za-z'.-]*,?|&)"
_ISSUER_RE = re.compile(r"^\s*(" + _ISSUER_WORD + r"(?: " + _ISSUER_WORD + r")*)")

#: A colon-terminated opening field is a LABEL, and a label is furniture, not a
#: name. Deliberately unbounded in length, and admitting digits and hyphens: an
#: earlier form of this rule bounded all three and the review escaped it three
#: ways, including with `Return-Service-Requested` — which this template really
#: does print, in the same slot, as `Return Service Requested`.
#:
#: Applied to the text BEFORE the platform's own `PAGE:` field (see
#: `_institution_slot`), because that field is a colon too and a rule that saw
#: it would call every masthead line furniture.
_LABEL_RE = re.compile(r"^[^:\n]*:")
#: The page separator the OCR layer inserts between pages. Not printed text.
_PAGE_MARKER_RE = re.compile(r"^\s*-{2,}\s*Page \b", re.IGNORECASE)
#: A routing or batch code. The platform prints a GROUP of them between the
#: institution's name and its `PAGE:` field, and a token carrying a digit is
#: one of those — never part of a name.
_CODE_TOKEN_RE = re.compile(r"^\S*[0-9]\S*$")

#: Words this TEMPLATE prints as its own furniture. A candidate name made only
#: of these is the template talking about itself, however it is positioned —
#: `STATEMENT OF ACCOUNT` is a heading, not an institution. This is a list of
#: the TEMPLATE's vocabulary, not a list of banks: nothing here names, excludes
#: or privileges any institution, and a bank whose name happens to contain one
#: of these words still publishes because the test is that EVERY word matches.
_FURNITURE_WORDS = frozenset(
    """ACCOUNT ACCOUNTS AMOUNT AVAILABLE AVERAGE AVG BALANCE CHECK CHECKS
    CREDIT CREDITS DAILY DATE DAYS DEBIT DEBITS DEPOSIT DEPOSITS DESCRIPTION
    DOCUMENTS IN LAST MINIMUM OF OTHER PAGE PERIOD REF REQUESTED RETURN
    SERVICE STATEMENT STATEMENTS SUMMARY TELEPHONE THIS THROUGH TOTAL""".split()
)


def _masthead(markdown: str) -> str:
    """Everything the statement prints before it names the account.

    Scoped for the same reason §JHA scopes its issuer read: the transaction
    descriptions further down carry the domains and the names of everyone the
    holder paid, and four of this archive's documents print a merchant domain
    or another bank's name inside them. Reading the whole document would see
    those; reading the masthead cannot.
    """
    heading = _ACCOUNT_HEADING_RE.search(markdown)
    return markdown[: heading.start()] if heading else markdown


def _printed_lines(masthead: str) -> list[str]:
    """The masthead's PRINTED lines. The OCR layer's own `--- Page N ---`
    separator is ours, not the bank's, and a reader that counted it as the
    first line would find no issuer on any document."""
    return [line for line in masthead.splitlines()
            if line.strip() and not _PAGE_MARKER_RE.match(line)]


#: The platform's masthead FIELDS. A line carrying one of them is the
#: template's own header row; a line carrying none of them, opening with a
#: word, directly under the institution slot is the institution's name
#: CONTINUING onto a second line.
_MASTHEAD_FIELD_RE = re.compile(r"\b(?:PAGE|ACCOUNT|TELEPHONE|DOCUMENTS)\s*:", re.IGNORECASE)


def _continues_the_name(lines: list[str]) -> bool:
    """Whether the line under the institution slot carries the rest of a name.

    `FIRST NATIONAL BANK` over `OF EXAMPLETOWN` is one institution printed on
    two lines, and a reader that takes the first line publishes a DIFFERENT
    bank's name — the failure mode this whole read exists to avoid, because a
    wrong name is worse than no name. There is no rule that says where such a
    name ends, so the honest answer is to publish none of it.
    """
    if len(lines) < 2:
        return False
    following = lines[1].lstrip()
    return following[:1].isalpha() and not _MASTHEAD_FIELD_RE.search(following)


def _institution_slot(lines: list[str]) -> str | None:
    """The text of the platform's INSTITUTION SLOT, or None.

    The slot is not "the top of the page" — proximity is not a role, and the
    review published a program manager's banner by sitting one above a contact
    block. It is the field the platform itself reserves, and the ONE arrangement
    this read accepts is the one in which the template bounds the name on BOTH
    sides:

        UNITED COMMUNITY (204) 000 00016 02 PAGE: 1
        SOUTHSTATE BANK, N.A. 101 00031 O1 PAGE: 1
        ^ the name opens the line   ^ codes  ^ the platform's own field closes it

    Left edge: the start of the first printed line. Right edge: the platform's
    `PAGE:` field, with every token between it and the name a routing or batch
    code. Neither edge is a guess about how long a name is.

    **This is an ATTESTATION-SCOPED read.** The archive prints a second
    arrangement in which the header field wraps to the next line and the rest
    of the first line is the issuer's ADDRESS:

        UNITED COMMUNITY (10( POB0X 2537
        000 00010 02 PAGE: 1 ACCOUNT: XXXXXXXXXXX3311

    It is deliberately NOT read. There the template bounds the name on the left
    only, and where it ends is unknowable: the two archive documents of that
    arrangement separate cleanly just because OCR happened to put a digit in
    the first address token, and a constructed `FIRST EXAMPLE BANK PO BOX 2537`
    publishes `FIRST EXAMPLE BANK PO BOX` under the same rule. A wrong name is
    worse than no name, so that arrangement yields None. It costs two archive
    documents their label and no document its figures.
    """
    if _continues_the_name(lines):
        return None
    page = _PAGE_FIELD_RE.search(lines[0])
    return lines[0][: page.start()] if page else None


def _issuer(markdown: str) -> str | None:
    """The institution this document names as its own, or None.

    Five guards, and it is worth being exact about what each one does, because
    the review defeated an earlier form of this read four different ways:

    * the SCOPE. Only the masthead is read, so the merchant domains and the
      counterparty bank names in the ledger below it are out of range — four of
      this archive's documents print one, and the first core-processor cell had
      `walmart.com` published as an issuer when its own scope slipped;
    * the CONTACT BLOCK corroborates. Without the platform's `TELEPHONE:`
      furniture nothing is published. Measured over the archive this is the
      guard that actually fires: it is what declines all 16 of the documents
      that publish no name;
    * the INSTITUTION SLOT binds the name to the ROLE rather than to a position
      (`_institution_slot`). A banner above a contact block is not in the slot;
    * the LABEL rule. Any colon-terminated opening field is furniture — a
      folio, a statement date, an account field, a `Return-Service-Requested`.
      No archive document reaches it, because the contact-block guard declines
      them first; it is here for the layout that carries a contact block AND
      opens on a label, which the review built and this archive has not;
    * the FURNITURE rule. A candidate made only of words this template prints
      as its own headings is the template talking about itself.

    The DIGIT rule inside `_ISSUER_WORD` ends the name where the platform's
    routing and batch codes begin.

    A document that satisfies none of it gets None, not a guess. The arithmetic
    does not depend on the name, so an unnamed issuer costs a label rather than
    a document — the honest-unknown-issuer ruling of 2026-08-14. Several
    issuers on this template print their name only inside a logo, which is an
    image, and inventing one from the holder's address would be a fabrication.
    """
    masthead = _masthead(markdown)
    if not _CONTACT_FURNITURE_RE.search(masthead):
        return None
    lines = _printed_lines(masthead)
    if not lines:
        return None
    opening = _institution_slot(lines)
    if opening is None or _LABEL_RE.match(opening):
        return None
    name = _ISSUER_RE.match(opening)
    if not name:
        return None
    codes = opening[name.end():].split()
    if not codes or not all(_CODE_TOKEN_RE.match(token) for token in codes):
        return None
    printed = re.sub(r"\s+", " ", name.group(1)).strip().strip(",")
    if not printed:
        return None
    words = [word.strip(",.&'-").upper() for word in printed.split()]
    if all(not word or word in _FURNITURE_WORDS for word in words):
        return None
    return printed


# ---------------------------------------------------------------------------
# The printed summary
# ---------------------------------------------------------------------------

#: A summary BALANCE row: the label, the date it is a balance ON, and the
#: figure. The date is what separates a balance from a statistic — the platform
#: prints `MINIMUM BALANCE`, `AVG AVAILABLE BALANCE` and `AVERAGE BALANCE`
#: undated, and that structural rule excludes all three without this module
#: holding a list of their names.
def _balance_row(label: str) -> re.Pattern[str]:
    return re.compile(
        r"\b" + label + r"\s+" + _TOKEN_START + r"(" + _SHORT_DATE + r")" + _DATE_END
        + r"\s+" + _FIGURE_TOKEN
    )


_OPENING_RE = _balance_row(_OPENING_LABEL)
_CLOSING_RE = _balance_row(_CLOSING_LABEL)


#: A summary COUNT row: `16 CREDITS 136,128.65`. The count is optional because
#: the platform omits it when there were none (`CREDITS .00`) — and an absent
#: count is admitted ONLY against a zero total (`_counts` below), so a count
#: that OCR dropped from a non-zero row cannot be read as "no items". The
#: boundary before the count is what keeps the cents of the figure printed to
#: the left of the label from being read as one.
def _count_row(label: str) -> re.Pattern[str]:
    return re.compile(
        r"(?:" + _TOKEN_START + r"([0-9]{1,4})" + r"(?![0-9])\s+)?"
        + label + r"\s+" + _FIGURE_TOKEN
    )


_CREDITS_RE = _count_row("CREDITS")
_DEBITS_RE = _count_row("DEBITS")

#: The period's ledger average, printed UNDATED beside the balances. Published
#: as `stated_average_balance` because it is the bank's own figure and the
#: schema asks for the ledger one; it gates nothing, which is what leaves it
#: free to be an independent opinion on the average this platform computes.
#: The platform prints an AVAILABLE-balance average beside it, and the two are
#: different statistics — the label here is the whole one, so the other cannot
#: match it.
_AVERAGE_RE = re.compile(r"\bAVERAGE BALANCE\s+" + _FIGURE_TOKEN)

#: Where the summary strip stops. Each alternative is the printed name of the
#: block that follows it, so the boundary is the document's own furniture.
_SECTION_NAMES = ("OTHER CREDITS", "OTHER DEBITS", "DAILY BALANCE", "DEPOSITS", "CHECKS")
#: Case-SENSITIVE on purpose: the platform prints its section names in capitals,
#: and thirteen of this archive's documents also carry the same words in
#: lower-case prose (`...more of your deposits clear sooner`, the interest
#: disclosure's `average daily balance method`). Case is the only thing that
#: tells the heading from the sentence.
_SECTION_RE = re.compile(r"\b(" + "|".join(_SECTION_NAMES) + r")\b")


class _Summary:
    """The figures the summary strip prints, and the counts beside them."""

    __slots__ = ("start", "end", "days", "opening", "closing",
                 "credit_count", "credits", "debit_count", "debits", "average")

    def __init__(self, **fields) -> None:
        for name, value in fields.items():
            setattr(self, name, value)


def _once(region: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    """The one reading of a summary row, or None.

    A row the strip prints twice, differently, is the document contradicting
    itself about its own summary, and there is no rule that says which printing
    to believe. Taking the first would be picking one, so this declines — which
    is also what makes the strip's BOUNDARY load-bearing rather than decorative:
    the small print at the foot of the statement prints these labels again, and
    a read that ran to the end of the document would find them.
    """
    found = list(pattern.finditer(region))
    if not found or len({match.groups() for match in found}) != 1:
        return None
    return found[0]


def _counts(region: str, pattern: re.Pattern[str]) -> tuple[int, float] | None:
    """`(count, total)` for one direction of the summary strip.

    Fail-closed twice over: a row this does not find at all yields None rather
    than a zero, and a row whose count the platform did not print is admitted
    only when the total it did print is zero — the one case where "no count"
    and "no items" are the same statement about the document.
    """
    match = _once(region, pattern)
    if not match:
        return None
    total = _figure(match.group(2))
    if total is None:
        return None
    if match.group(1) is None:
        return (0, 0.0) if total == 0.0 else None
    return int(match.group(1)), total


def _period_dates(printed_start: str, printed_end: str) -> tuple[str, str] | None:
    """The printed period as two ISO dates, or None if it is not a period.

    The pattern proves the SHAPE of a date and nothing more: a thirteenth
    month has that shape and is not a day. `iso_from_month_day_year` raises on
    such a token, and a raise inside `parse` is recorded as a crash of ours
    rather than as the decline it should be (`parser_registry.ParserFailure`),
    so it is caught here.
    """
    try:
        return (iso_from_month_day_year(printed_start),
                iso_from_month_day_year(printed_end))
    except ValueError:
        return None


def _summary_region(markdown: str) -> str | None:
    """The summary strip alone: from the account heading to the ledger.

    Cut at the first section heading because the disclosures at the foot of
    the statement print `THIS STATEMENT` again, in the sentence that tells the
    holder to compare it against their own records.
    """
    heading = _ACCOUNT_HEADING_RE.search(markdown)
    if not heading:
        return None
    rest = markdown[heading.end():]
    section = _SECTION_RE.search(rest)
    return rest[: section.start()] if section else rest


def _summary(markdown: str) -> _Summary | None:
    """Every figure the summary strip prints, or None if any is missing.

    A strip with a hole in it yields None rather than a partly-filled summary:
    every gate below compares the published ledger against these figures, so a
    missing one would weaken the gate instead of failing it.
    """
    region = _summary_region(markdown)
    if region is None:
        return None
    period = _once(region, _PERIOD_RE)
    opening = _once(region, _OPENING_RE)
    closing = _once(region, _CLOSING_RE)
    if not (period and opening and closing):
        return None
    printed_period = _period_dates(period.group(1), period.group(2))
    if printed_period is None:
        return None
    credits_ = _counts(region, _CREDITS_RE)
    debits = _counts(region, _DEBITS_RE)
    if credits_ is None or debits is None:
        return None
    opening_amount = _figure(opening.group(2))
    closing_amount = _figure(closing.group(2))
    if opening_amount is None or closing_amount is None:
        return None
    return _Summary(
        start=printed_period[0],
        end=printed_period[1],
        days=int(period.group(3)),
        opening=opening_amount,
        closing=closing_amount,
        credit_count=credits_[0], credits=credits_[1],
        debit_count=debits[0], debits=debits[1],
        average=_average(region),
    )


def _average(region: str) -> float | None:
    match = _AVERAGE_RE.search(region)
    return _figure(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

#: A row of ANY section: the posting date and the amount, in that order. Every
#: section of this template prints rows in that shape and differs only in what
#: it prints to the LEFT of the date — nothing in the deposit grid, a
#: description in the two `OTHER` sections, a cheque serial in `CHECKS` — so
#: the rows are found by one pattern and the left-hand text is read afterwards
#: from the gap between one row and the next. Written the other way round, with
#: the description inside the pattern, a row that begins a line with nothing
#: before it does not match at all and is silently lost.
_ROW_RE = re.compile(_DATE_TOKEN + r"\s+" + _FIGURE_TOKEN)

#: A cheque's serial number, at the end of the text printed before its row. The
#: platform marks a break in the serial sequence with a trailing `*`, and
#: prints a cheque it holds no serial for as a bare `date amount` pair.
_SERIAL_RE = re.compile(r"(?<![0-9])([0-9]{2,8})\s*\*?\s*$")

#: The ledger's sections, in the order the template prints them, with the
#: direction each one's rows are postings in — which is the COLUMN the bank
#: printed the row in, never the sign of the amount — and the description to
#: publish where the section prints none. `None` marks the cheque section: its
#: rows are debits, and the text before each one is a serial, not a
#: description.
_LEDGER_SECTIONS = (
    ("DEPOSITS", True, "Deposit"),
    ("OTHER CREDITS", True, "Credit"),
    ("OTHER DEBITS", False, "Debit"),
    ("CHECKS", None, "Check"),
)


def _sections(markdown: str) -> dict[str, list[str]]:
    """The document's ledger, split on the platform's own section headings.

    A section broken across a page reprints its heading, so a name can occur
    more than once and each occurrence is kept as its own RUN. The rows of all
    the runs are one section — the summary counts the whole of it however many
    pages it took — but the runs are not concatenated, because everything
    between the last row of one and the heading of the next is the page
    furniture, and a concatenation puts that furniture inside the description
    of the row the next run opens with.
    """
    marks = [(m.start(), m.end(), m.group(1)) for m in _SECTION_RE.finditer(markdown)]
    blocks: dict[str, list[str]] = {}
    for index, (_start, end, name) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(markdown)
        blocks.setdefault(name, []).append(markdown[end:stop])
    return blocks


#: What the platform prints as a section's column header. It sits between the
#: heading and the first row, so it lands in that row's gap and would otherwise
#: be published as part of its description. Anchored at the start, because a
#: header only ever opens a section — a word of it appearing later in the gap
#: is a word of the description.
#: `CONTINUED` is in the list because it is the marker the platform prints on a
#: section that a page break interrupted, immediately before that section
#: reprints its column header.
_COLUMN_HEADER_RE = re.compile(
    r"^(?:CONTINUED|REF|CHECK|DESCRIPTION|DATE|AMOUNT|BALANCE|#|\W)*", re.IGNORECASE
)


def _printed_before(gap: str) -> str:
    """The description the bank printed to the left of a row.

    The TAIL of what is left, not the head: a gap spans everything since the
    previous row, so on a page break it opens with the page furniture and
    closes with the description of the row it belongs to.
    """
    printed = re.sub(r"\s+", " ", gap).strip(" .-|*")
    printed = _COLUMN_HEADER_RE.sub("", printed, count=1).strip()
    return printed[-200:].strip()


def _rows(runs: list[str], *, credit: bool | None, start: date, end: date,
          default: str) -> list[Transaction] | None:
    """Every posting a section printed, or None if one of them is unreadable.

    None rather than "skip" on purpose. A row whose date the period cannot
    place, or whose amount is not money, is a row we could not read — and
    dropping it silently is exactly how a ledger comes to disagree with a
    printed total by one row while still looking complete.

    `credit=None` marks the cheque section, whose rows are debits and whose
    left-hand text is a serial number rather than a description.
    """
    rows: list[Transaction] = []
    for run in runs:
        cursor = 0
        for match in _ROW_RE.finditer(run):
            gap = _printed_before(run[cursor : match.start()])
            cursor = match.end()
            iso = iso_within_period(match.group(1), start, end)
            amount = _figure(match.group(2))
            if iso is None or amount is None:
                return None
            if credit is None:
                serial = _SERIAL_RE.search(gap)
                description = f"{default} {serial.group(1)}" if serial else default
            else:
                description = gap or default
            rows.append(Transaction(
                date=iso,
                description=description,
                amount=round(amount if credit else -amount, 2),
                direction="credit" if credit else "debit",
            ))
    return rows


def _daily_balances(runs: list[str], *, start: date, end: date) -> list[StatementDailyBalance] | None:
    printed = []
    for run in runs:
        for match in _ROW_RE.finditer(run):
            iso = iso_within_period(match.group(1), start, end)
            balance = _figure(match.group(2))
            if iso is None or balance is None:
                return None
            printed.append(StatementDailyBalance(date=iso, balance=balance))
    return printed


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------

def _matches_the_printed_summary(rows: list[Transaction], summary: _Summary) -> bool:
    """The four printed figures, and the identity that ties them together."""
    credits_ = [row for row in rows if row.direction == "credit"]
    debits = [row for row in rows if row.direction == "debit"]
    if len(credits_) != summary.credit_count or len(debits) != summary.debit_count:
        return False
    if abs(sum(row.amount for row in credits_) - summary.credits) > 0.005:
        return False
    if abs(-sum(row.amount for row in debits) - summary.debits) > 0.005:
        return False
    identity = summary.opening + summary.credits - summary.debits
    if abs(identity - summary.closing) > 0.005:
        return False
    return abs(summary.opening + sum(row.amount for row in rows) - summary.closing) <= 0.005


def _matches_the_printed_grid(
    rows: list[Transaction], printed: list[StatementDailyBalance], opening: float
) -> bool:
    """The `DAILY BALANCE` grid, walked against the ledger.

    An independent second opinion: the grid is a different printing of the same
    period, so a ledger that reproduces every summary figure and still
    disagrees with the grid has the right totals in the wrong days — which is
    what a duplicated row paired with a dropped one looks like.

    Checked in both directions. Every day the grid prints must equal the walked
    end-of-day balance, and every day the ledger posts on must appear in the
    grid, so neither a day the reader invented nor a day it lost can pass.
    """
    walked: dict[str, float] = {}
    running = opening
    for row in sorted(rows, key=lambda item: item.date):
        running = round(running + row.amount, 2)
        walked[row.date] = running
    if {entry.date for entry in printed} != set(walked):
        return False
    return all(abs(walked[entry.date] - entry.balance) <= 0.005 for entry in printed)


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

def parse_core_processor_sectioned_statement(markdown: str) -> Statement | None:
    """Any issuer's statement on the sectioned issue of this template.

    Declines — rather than guesses — in four named situations, each of which is
    a fact about the document rather than a gap in this reader:

    * it prints no account heading, or no complete summary strip;
    * it prints the running-balance ledger instead of the sections. That issue
      has its own reader, which supersedes this registration;
    * a row's date or amount is not readable as one. A scanned issue of this
      template routinely substitutes letters for digits in the date column, and
      a row read on the wrong day is worse than a document declined;
    * the ledger does not reproduce every figure the summary printed, or
      disagrees with the printed daily-balance grid.
    """
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    if summary is None:
        return None
    heading = _ACCOUNT_HEADING_RE.search(markdown)
    if heading is None:
        return None

    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    if end < start:
        return None

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

    printed_grid: list[StatementDailyBalance] = []
    if "DAILY BALANCE" in sections:
        found_grid = _daily_balances(sections["DAILY BALANCE"], start=start, end=end)
        if found_grid is None:
            return None
        printed_grid = found_grid
        if not _matches_the_printed_grid(rows, printed_grid, summary.opening):
            return None

    return Statement(
        bank=_issuer(markdown),
        account_name=re.sub(r"\s+", " ", heading.group(1)).strip(),
        account_number=heading.group(2),
        period_start=summary.start,
        period_end=summary.end,
        days_in_period=summary.days,
        beginning_balance=summary.opening,
        ending_balance=summary.closing,
        stated_total_credits=summary.credits,
        stated_total_debits=summary.debits,
        stated_credit_count=summary.credit_count,
        stated_debit_count=summary.debit_count,
        stated_average_balance=summary.average,
        stated_daily_balances=printed_grid,
        transactions=sorted(rows, key=lambda row: row.date),
    )
