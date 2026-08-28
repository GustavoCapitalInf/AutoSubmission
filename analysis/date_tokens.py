"""Row-level date tokens -> ISO strings (R-2 shared utilities).

Scope boundary with `analysis/dates.py`: that module owns *statement-level*
date semantics — tolerant parsing of an already-extracted date, and re-deriving
transaction years from the statement period. This module owns the much smaller
job that sat duplicated in twelve parsers: turning the token a bank printed at
the head of a transaction row (``01/15``, ``01-15``, ``1/15/26``) into an ISO
date string, given the year the parser derived from the statement period.

Deliberately strict. These helpers raise `ValueError` (or return `None`, for
the guarded variant) on anything that is not the expected token shape, because
their callers have already matched a row-date regex: a token reaching them that
does not parse means the parser's own layout assumption is wrong, and inventing
a date would be worse than failing.

Twelve pre-R-2 `_iso` clones collapse to the three functions below; the
remaining five are genuinely bank-specific (month-name tokens, embedded
platform formats) and stay in their parsers.
"""
from __future__ import annotations

import re
from datetime import date, datetime

__all__ = [
    "MAX_DATE_TOKEN_CHARS",
    "MONTH_NAME_ALT",
    "MONTH_NUMBERS",
    "PERIOD_DASH",
    "date_refusal",
    "iso_or_none",
    "iso_from_month_day",
    "iso_from_month_day_strict",
    "iso_from_month_day_year",
    "iso_from_named_month_day",
    "parsed_datetime",
    "period_from_long_dates",
    "iso_unique_in_period",
    "iso_within_period",
    "year_within_period",
]

_MONTH_DAY_RE = re.compile(r"(\d{2})/(\d{2})")

# ---------------------------------------------------------------------------
# THE REFUSAL LAW FOR THIS MODULE (W3 §PRIVACY3, the date-side half of
# §MONEYPRIV's law).
#
# Every refusal this module raises names a READER and a measured SHAPE, and
# never the token. The date grammar leaked the same two ways the money grammar
# did, and the more dangerous half was invisible for the same reason: there was
# no `raise` to grep for. `iso_from_month_day` and `iso_from_month_day_year`
# document "raises ValueError for a token that is not month/day" and then let
# `int()` be that raise — `invalid literal for int() with base 10: '<the cell>'`
# — while `date()` echoes an out-of-range YEAR that the document supplied.
#
# The law is about what this module may RAISE. It carries no clause about who
# catches it: `analysis/parser_registry._guarded` reduces a parser crash to a
# class name today, and a boundary can only withhold the messages it knows
# about, so a grammar that never puts the cell in a message is safe in front of
# a boundary nobody has written yet.
# ---------------------------------------------------------------------------

#: The longest token any date reader in this module will describe as
#: "over-long" rather than measure further. A bound, not a format: it exists so
#: `_refusal_class` can answer without looking at the characters.
MAX_DATE_TOKEN_CHARS = 32


def _refusal_class(token: str) -> str:
    """WHY the date grammar refused, as a category — never the text itself.

    Four fixed strings, each chosen by a MEASUREMENT on the token ("is it
    empty", "does it hold a digit", "how long is it"), so no branch can return
    a value that varies with the content. That closure is the privacy property:
    a category that interpolated any part of the token would be a leak wearing
    a reason's clothes. The single interpolation is `MAX_DATE_TOKEN_CHARS`, a
    constant of this module.
    """
    stripped = token.strip()
    if not stripped:
        return "the cell is empty"
    if not any(ch.isdigit() for ch in stripped):
        return "no digits in the cell"
    if len(stripped) > MAX_DATE_TOKEN_CHARS:
        return f"longer than the {MAX_DATE_TOKEN_CHARS}-character bound"
    return "not a date in the reader's format"


def date_refusal(reader: str, token: str) -> ValueError:
    """THE refusal. Every raise in this module is built here.

    One constructor rather than one message per site, because the property
    being defended is a property of the SET — "no exception this module raises
    quotes the document" — and a property of a set is only as strong as its
    widest member. `token` is passed in only to be MEASURED: it reaches the
    message through nothing but `_refusal_class`'s four-value classification.

    It RETURNS the exception rather than raising it, and that is load-bearing:
    the call site writes ``raise date_refusal(...)`` from OUTSIDE the ``except``
    block that swallowed the conversion error, so what is raised carries
    neither a ``__cause__`` nor a ``__context__``. `int()`'s own ValueError
    quotes its argument verbatim and `date()` echoes an out-of-range year, so a
    chained refusal would pass a test written on ``str(exc)`` and fail the
    moment anything rendered a traceback. ``from None`` is no better: it clears
    ``__cause__`` and sets a rendering hint while ``__context__`` still holds
    the object. Raising after the handler has finished is what removes it.

    Public, unlike `money._refusal`, because the parser layer's own date sites
    refuse through it: `td_can._native_date_to_iso` is a caller, and a parser
    that grows a sixth date shape should reach for this rather than write a
    twelfth message.
    """
    return ValueError(
        f"date grammar refused a printed token "
        f"({_refusal_class(token)}; reader={reader})"
    )


def parsed_datetime(token: str, fmt: str, *, reader: str) -> datetime:
    """`datetime.strptime`, refusing without quoting the token.

    `strptime`'s own ValueError is
    ``time data '<the printed date>' does not match format '<ours>'`` — the
    inherited-leak shape of §MONEYPRIV MP0, and the reason the twenty sites the
    batch-6 ledger named have no `raise` to grep for. `fmt` is the caller's own
    format constant and never reaches the message either; it is only the reader
    name that identifies the site.
    """
    try:
        parsed = datetime.strptime(token, fmt)
    except (ValueError, OverflowError):
        parsed = None  # -> the one refusal, below and unchained
    if parsed is None:
        raise date_refusal(reader, token)
    return parsed


def iso_or_none(year: int, month: int, day: int) -> str | None:
    """The ISO date, or None when those three numbers are not one.

    A row-date regex proves a token's SHAPE and nothing more. `26/13/24` and
    `42/13` match `MM/DD/YY` and `MM/DD` perfectly and are not dates — they are
    a column that is not the date column (a check number, an amount fragment,
    an OCR misread). Discovery hit exactly that on 17 documents and `date()`
    raised `ValueError` out of the parser.

    Callers that already treat an unreadable token as "not a date row" want the
    same answer here, so the guarded helpers below funnel through this one
    place rather than each growing a `try`. Guessing what the digits were meant
    to be is never an option: the row is dropped and reconciliation decides
    whether what remains is publishable.

    **`OverflowError` is caught here and at every other conversion guard in
    this module** (RAISE-PRIVACY-3, #HYGIENE8, closing the contract defect W3
    §PRIVACY3 P10 items 6-7 pinned rather than fixed). `date(2026, 1, N)` for
    an N past 2**31 - the C `int` `date()` parses its arguments into, on every
    platform - raises `OverflowError`, which is an `ArithmeticError`
    and not a `ValueError`, so a bare `except ValueError` let it out of a
    function whose whole contract is "or None". Measured over this module's
    eleven entry points, EIGHT let it escape; the two that did not were saved
    by a regex bound on the token rather than by a handler, which is exactly
    the kind of protection that disappears when a caller changes.

    The message is a fixed CPython sentence, so this was never a privacy
    defect - it is a fail-closed one, and the rule is now uniform: a conversion
    guard in this module catches both, so a reader does not have to work out
    which arithmetic a particular `date()` call can overflow on.
    """
    try:
        return date(year, month, day).isoformat()
    except (ValueError, OverflowError):
        return None


def iso_from_month_day(token: str, year: int, *, separator: str = "/") -> str:
    """``("01/15", 2026)`` -> ``"2026-01-15"``.

    The year is supplied by the caller because the bank did not print one on
    the row; `analysis.dates.assign_transaction_years` later corrects it for
    statement periods that cross a year boundary. Raises `ValueError` for a
    token that is not ``month<sep>day`` — through `date_refusal`, which names
    this reader and the token's SHAPE and never the token (see the refusal law
    above). `int()` used to be that raise, and it quoted the cell.
    """
    try:
        month, day = [int(part) for part in token.split(separator, 1)]
        iso = date(year, month, day).isoformat()
    except (ValueError, OverflowError):
        iso = None  # -> the one refusal, below and unchained
    if iso is None:
        raise date_refusal("iso_from_month_day", token)
    return iso


def iso_from_month_day_strict(token: str, year: int) -> str | None:
    """As above, but returns None instead of raising when `token` is not
    exactly ``MM/DD``.

    For parsers that feed this straight from a table cell whose contents they
    have not otherwise validated, where a non-date cell is an ordinary
    occurrence rather than a defect. "Not exactly MM/DD" includes a token of
    the right shape that no calendar can hold (`42/13`) — see `iso_or_none`.
    """
    m = _MONTH_DAY_RE.fullmatch(token.strip())
    if not m:
        return None
    return iso_or_none(year, int(m.group(1)), int(m.group(2)))


def iso_from_month_day_year(token: str, *, century: str = "short") -> str:
    """``"1/15/26"`` -> ``"2026-01-15"``; the bank printed its own year.

    `century` controls the two-digit-year pivot:

    * ``"short"`` — add 2000 only to years below 100, so a four-digit year is
      taken as printed.
    * ``"always"`` — add 2000 unconditionally, for layouts whose year field is
      always two digits.

    Raises `ValueError` on anything that is not ``month/day/year`` — through
    `date_refusal` (see the refusal law above). `int()` used to be that raise
    and it quoted the cell; `date()` echoes an out-of-range YEAR, which the
    document supplies.
    """
    if century not in ("short", "always"):
        # An API misuse by OUR caller, not a reading of the document: `century`
        # is one of two literals a parser module writes. A fixed message, and
        # it names the two legal values rather than echoing the illegal one.
        raise ValueError("unknown century mode: expected 'short' or 'always'")
    try:
        month, day, year = [int(part) for part in token.split("/")]
        if century == "always" or year < 100:
            year += 2000
        iso = date(year, month, day).isoformat()
    except (ValueError, OverflowError):
        iso = None  # -> the one refusal, below and unchained
    if iso is None:
        raise date_refusal("iso_from_month_day_year", token)
    return iso


#: "January 5, 2026 through February 4, 2026" — a full-month-name statement
#: period. Several banks print the period in exactly this form.
_LONG_PERIOD_RE = re.compile(
    r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+through\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})"
)
_MONTH_NAMES = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}

#: Month name -> number, case-folded, accepting the full name and the
#: three-letter abbreviation of it. Derived from `_MONTH_NAMES` rather than
#: written out again: one table, so a month can never mean two things.
#:
#: Both spellings occur on ONE document — a statement heads itself "April 2026
#: statement … April 1, 2026" and then dates each posting row "Apr 01", so a
#: parser reading that layout needs the two forms to resolve identically.
MONTH_NUMBERS: dict[str, int] = {
    key: number
    for name, number in _MONTH_NAMES.items()
    for key in (name.casefold(), name[:3].casefold())
}

#: Alternation of every accepted month spelling, longest first so that
#: "January" is never truncated to "Jan" mid-match. For embedding in a
#: parser's own row pattern; carries no groups.
MONTH_NAME_ALT = "|".join(
    sorted((re.escape(key) for key in MONTH_NUMBERS), key=len, reverse=True)
)

#: The dash a statement prints BETWEEN two dates — ``Apr 1 - Apr 30, 2026``,
#: ``April 1, 2026—April 30, 2026``. For embedding in a parser's own period
#: pattern; carries no groups.
#:
#: This class is deliberately WIDER than `analysis.money.MINUS_CLASS`, and the
#: asymmetry is the point rather than an oversight. The two marks have
#: opposite risk profiles:
#:
#: * a glyph admitted to the SIGN class silently inverts the direction of
#:   every amount that carries it, so that class is narrowed to what documents
#:   attest and nothing else;
#: * a glyph admitted to the RANGE class can only make a period line match.
#:   It carries no value and cannot change one. What it CAN do is fail to
#:   match — and the period is required, so an unrecognised range dash costs
#:   the whole document.
#:
#: The em dash therefore belongs here and not there. Both classes were once
#: one string in `money.py`, which is how U+2014 reached the sign class: two
#: parsers built their period pattern out of ``MINUS_GLYPHS`` because it was
#: the only dash class the platform exported (W3 §MGD). `square_checking` had
#: already reached the same conclusion privately, with an even wider class.
#:
#: Membership is exactly what those consumers carried before the split —
#: ASCII hyphen-minus, U+2212, U+2013, U+2014 — so repointing them changes no
#: pattern. Every archive document of the three families prints the ASCII
#: hyphen here (brex 6/6, mercury 31/31, wealthsimple 16/16).
PERIOD_DASH = "[-−–—]"


def iso_from_named_month_day(month: str, day: str | int, year: str | int) -> str | None:
    """``("April", 1, 2026)`` / ``("Apr", "01", "2026")`` -> ``"2026-04-01"``.

    Returns None — never raises — when the month word is not a month or the
    three numbers are not a calendar date, because the callers reach this from
    a regex that has proved a token's SHAPE and nothing more (`iso_or_none`).
    """
    number = MONTH_NUMBERS.get(month.strip().casefold())
    if number is None:
        return None
    try:
        return iso_or_none(int(year), number, int(day))
    except (ValueError, OverflowError):
        return None


def period_from_long_dates(markdown: str) -> tuple[str, str] | None:
    """First "<Month> D, YYYY through <Month> D, YYYY" span, as ISO strings.

    Returns None when the document does not print its period this way, which
    callers treat as "try another period format", not as an error.
    """
    m = _LONG_PERIOD_RE.search(markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    # The pattern's `([A-Z][a-z]+)` matches any capitalized word, so a phrase
    # shaped like a long period but headed by something else ("Jan 5, 2026
    # through Feb 4, 2026", "Balance 5, 2026 through February 4, 2026") reaches
    # here. That is a NON-MATCH, not an error: the contract above says callers
    # treat None as "try another period format", and a KeyError escaping into
    # them is a crash (ParserCrashError in deterministic mode, and in the
    # webapp's auto mode a silent fall-through to LLM extraction).
    start_month, end_month = _MONTH_NAMES.get(sm), _MONTH_NAMES.get(em)
    if start_month is None or end_month is None:
        return None
    # `(\d{1,2})` admits a day no month has, and `date()` echoes the offending
    # NUMBER — "day 99 must be in range 1..30 for month 4 in year 2026" on
    # 3.13+ — so the printed day and year would ride out on the message. The
    # raise is DELIBERATELY kept (the docstring's "returns None" contract is a
    # separate, movement-bearing fix, ledgered in W3 §PRIVACY3); only the
    # message changes.
    try:
        span = (
            date(int(sy), start_month, int(sd)).isoformat(),
            date(int(ey), end_month, int(ed)).isoformat(),
        )
    except (ValueError, OverflowError):
        span = None  # -> the one refusal, below and unchained
    if span is None:
        raise date_refusal("period_from_long_dates", m.group(0))
    return span


def iso_unique_in_period(month: int, day: int, *, start: date, end: date) -> str | None:
    """The one date inside the printed period a bare month/day can mean.

    A Date column that prints no year is ambiguous the moment a period
    straddles a year boundary: `01/02` inside `Dec 1 - Jan 31` belongs to the
    later year, and `12/31` to the earlier one. The period decides, and only
    where it decides UNIQUELY — a token that lands inside the period under
    both candidate years, or under neither, returns None so the caller can
    fail closed rather than guess a year the document never printed.

    Shared because the alternative is a clone: two registrations reading a
    `MM/DD` posting column need exactly this, and the guard in
    `tests/test_no_parser_helper_clones.py` is what says so out loud.
    """
    hits = []
    for year in {start.year, end.year}:
        try:
            candidate = date(year, month, day)
        except (ValueError, OverflowError):
            continue
        if start <= candidate <= end:
            hits.append(candidate)
    return hits[0].isoformat() if len(hits) == 1 else None


def year_within_period(month: int, day: int, start: date, end: date) -> int | None:
    """The year a bare `month/day` row belongs to, decided by the period.

    A statement whose period does not cross a year boundary has one candidate
    and this is trivially that year. One that does cross has two, and the
    correct one is the only one that puts the row inside the printed period —
    which is a fact about the document rather than a rule about which half of
    the period a month "usually" falls in.

    None when neither candidate lands inside the period, including when the
    numbers are not a date at all (`02/30`): a row-date regex proves a token's
    shape and nothing more, so the caller must be able to refuse it.
    """
    for year in dict.fromkeys((start.year, end.year)):
        try:
            candidate = date(year, month, day)
        except (ValueError, OverflowError):
            continue
        if start <= candidate <= end:
            return year
    return None


def iso_within_period(token: str, start: date, end: date) -> str | None:
    """``("03/05", …)`` -> ``"2026-03-05"`` when it falls inside the period.

    `year_within_period` applied to a `month/day` token, for the parsers whose
    rows carry no year and whose statement period is the only evidence of one.
    None for a token that is not `month/day`, or that no candidate year places
    inside the period.
    """
    parts = token.split("/")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    month, day = (int(part) for part in parts)
    year = year_within_period(month, day, start, end)
    # This `date()` cannot raise, and that is a measurement rather than a hope:
    # `year_within_period` returns a year ONLY for a candidate it already
    # constructed with these same month/day inside its own `try`, so the triple
    # is proven before it gets here. No refusal handler, because a handler that
    # can never fire is noise a later reader has to re-derive (W3 §PRIVACY3).
    return date(year, month, day).isoformat() if year else None
