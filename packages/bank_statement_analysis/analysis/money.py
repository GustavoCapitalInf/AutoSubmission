"""Shared money parsing for every statement parser (R-2).

Before this module each bank parser carried its own private `_money` /
`_parse_money` clone — 28 near-identical implementations across
`analysis/<bank>.py`, plus a dependency inversion in which thirteen modules
imported `_parse_money` from the *TD Canada* parser because that is where the
most tolerant copy happened to live.

The clones were not gratuitous: banks really do print money differently, and
each clone encoded one bank's format. So this module does not flatten them into
a single "smart" parser that guesses. It separates the **algorithm** (one
engine, here) from the **format** (declarative `AmountFormat` data, also here,
named after the printed form rather than the bank).

Surveyed format axes, all of which appear in the corpus:

* symbols/grouping — ``$1,234.56``, ``C$1 234,56``, ``1 234.56`` (space
  thousands), ``1.234,56`` / ``1234,56`` (decimal comma, FR-CA)
* negative markers — leading ``-``, trailing ``-`` (mainframe convention),
  parentheses ``(1,234.56)``, and ``D``/``DR``/``OD`` suffixes (TD Canada).
  The minus itself is a CLASS, not a character: ``U+2212 MINUS SIGN`` and
  ``U+2013 EN DASH`` are printed for it as readily as ASCII ``-`` (see
  `normalize_sign_glyphs`)
* junk that must be tolerated — ``*`` fill characters, ``+`` prefixes, stray
  whitespace inside cells, values printed as ``.56`` with no leading zero
* strictness — some parsers must reject anything that is not exactly
  ``ddd.dd`` (a wrong match there would fabricate a transaction), others parse
  the first money-shaped token they can find

Return types are deliberately preserved per caller: `float | None` for the
tolerant/optional parsers, `float` for the ones whose callers rely on a raise,
and `Decimal` for the parsers that carry Decimal arithmetic end to end. R-2 is
a packaging change with a byte-identical corpus proof; unifying the *numeric
type* is a separate, financially significant decision (MERGE_PLAN §5) and is
not made here.

A REFUSAL IN THIS MODULE NEVER QUOTES THE DOCUMENT (W3 §MG-C2 D1 for
`read_money`, §MONEY-PRIVACY for everything else). Every exception raised here
is built by `_refusal`: the reader's name and one of four measured shape
categories, and nothing that varies with the cell.

The rule is stated and enforced HERE, at the grammar, because this is the layer
that has the token in its hand — deliberately not at the boundary that
motivated it. Through batch 5 that boundary was `webapp/worker.py`, which
published `str(exc)` as the job error into the durable store; batch 6 closes
that side too (§WORKER-PRIVACY, a sibling card). Neither closure is the other's
excuse: a boundary can only withhold the messages it knows about, and a
grammar that never puts a cell in a message is safe in front of a boundary
nobody has written yet. What must not happen is the pair being read as one
belt with two names — so this module's rule is stated as a property of what it
may RAISE, with no clause about who catches it.

`tests/test_money.py` pins every function against the pre-R-2 implementation it
replaced, over a shared matrix of positive, negative and malformed inputs, and
`tests/test_money_refusals_are_private.py` feeds a poisoned token through every
raising entry point and fails if any fragment of it survives into the raised
exception, its chain, or a rendered traceback.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache

__all__ = [
    "AmountFormat",
    "MINUS_GLYPHS",
    "SIGNED_MONEY_TOKEN",
    "parse_amount",
    "parse_money",
    "parse_money_tokens",
    "read_money",
    "money_refusal",
    "parse_decimal",
    "parse_signed_decimal",
    "parse_decimal_mixed_separator",
    "parse_grouped_float",
    "parse_trailing_minus_dropped",
    "parse_french_amount",
    "parse_digit_scrubbed",
    "pad_leading_decimal",
    "strip_currency",
    "normalize_sign_glyphs",
    "MINUS_CLASS",
    "MAX_INTEGER_DIGITS",
    "STRICT_UNSIGNED",
    "STRICT_LEADING_SIGN",
    "STRICT_EITHER_MINUS",
    "STRICT_EITHER_MINUS_OR_PLUS",
    "STRICT_EITHER_MINUS_OR_PLUS_SPACED",
    "EITHER_MINUS_SPACED",
    "EITHER_MINUS_DROPPED",
    "EITHER_MINUS_PADDED",
    "LEADING_MINUS",
    "LEADING_MINUS_DROPPED",
    "LEADING_MINUS_PADDED",
    "PARENS_OR_LEADING_MINUS",
    "PARENS_OR_LEADING_MINUS_OR_PLUS",
]


# ---------------------------------------------------------------------------
# Small shared primitives
# ---------------------------------------------------------------------------

#: THE MINUS SIGN CLASS — every glyph a statement prints where a minus sign
#: belongs, ASCII hyphen-minus included, stated ONCE and derived from nowhere.
#:
#: This is the whole class rather than "the non-ASCII part of it", and that is
#: the load-bearing choice. Three of its four consumers — `MINUS_CLASS`,
#: `SIGNED_MONEY_TOKEN` and `parse_signed_decimal` — must admit ASCII ``-``,
#: and the fourth, `_MINUS_TABLE`, is indifferent to it (mapping ``-`` to
#: ``-`` is the identity). A canon that omitted ASCII would force each of the
#: three to add it back by hand, which is exactly how this module came to
#: carry TWO definitions of this name: a second, four-glyph ``MINUS_GLYPHS``
#: was bound at module scope beside `parse_signed_decimal` to re-supply the
#: ASCII hyphen, and it silently shadowed this one for every importer while
#: `MINUS_CLASS` and `_MINUS_TABLE` — already evaluated — kept the narrow
#: value. Two exported parsers then read one token with opposite signs:
#: ``parse_money("—$500.00")`` was ``+500.0`` and
#: ``parse_signed_decimal("—$500.00")`` was ``-500.00``. One definition, and
#: `tests/test_money.py` fails the build if a second is ever bound (W3 §MGD).
#:
#: ``U+2212 MINUS SIGN`` is the typographically correct character and is what
#: a web export emits when it renders a negative amount; ``U+2013 EN DASH`` is
#: what OCR and several producers' font maps put in its place. This is not
#: tolerance for OCR noise — these are native-text PDFs, and the layout engine
#: picks a dash by WIDTH rather than by meaning. One issuer's generator prints
#: U+2212 on one statement and U+2013 on the next month's, with ASCII hyphen
#: in the summary block of the same document (measured over Mercury's 31
#: statements: 1,202 U+2212, 687 U+2013, 13 U+002D immediately before a
#: currency symbol; Brex prints 135 ASCII and nothing else, Found 1,611 ASCII,
#: Wealthsimple 2,140 U+2013). To a reader they are the same mark, so a
#: grammar that knows only one does not merely refuse the token — the strict
#: engine returns ``None`` and drops the field, while the tolerant parsers
#: match the digits *after* the glyph and return the amount POSITIVE. That is
#: the dangerous half: a debit booked as a credit.
#:
#: ``U+2010 HYPHEN``, ``U+2011 NON-BREAKING HYPHEN`` and
#: ``U+FF0D FULLWIDTH HYPHEN-MINUS`` are plausible siblings and are
#: deliberately NOT here: no archive document prints one, and a sign class is
#: the last place to add unattested members — each one silently flips the sign
#: of anything that carries it. They are carried candidates, to be added the
#: day a document attests one.
#:
#: ``U+2014 EM DASH`` stays out on the archive's own evidence, and the
#: evidence is worth stating because the shadow admitted it. Across all 3,396
#: documents with offline text, an em dash stands in a sign position exactly
#: TWICE, both on documents that fail to parse:
#:
#: * ``88AAC06119FC`` (Columbia) prints ``03-16 — 39,692.35`` in its Daily
#:   Balances block, between two balances of 56,767.53 and 34,167.30. The dash
#:   is the empty-column placeholder of a three-column grid, and the figure it
#:   precedes is a POSITIVE running balance — admitting the glyph would flip a
#:   number the bank printed positive. It is the only document in the archive
#:   where an em dash precedes a bare money figure at all.
#: * ``FFEBAF819F74`` (TD) prints ``S2 -—ps/25/2zet —— $4812.39]``, which is
#:   OCR wreckage, not a sign.
#:
#: Zero documents in the four families that read a printed sign glyph (brex,
#: mercury, found_lead, wealthsimple) print an em dash in a sign position. An
#: em dash between two DATES is a different mark with the opposite risk
#: profile — punctuation that can never flip a figure — and has its own,
#: deliberately wider class at `analysis.date_tokens.PERIOD_DASH`.
MINUS_GLYPHS = "-−–"

#: The same class as a regex fragment, for consumers that find money tokens
#: with their own pattern before handing them here. Use this rather than a
#: bare ``-`` so a finder cannot match past a sign its parser would honour.
#: Derived, never re-spelled: the ASCII hyphen leads the class, where it is a
#: literal rather than a range.
MINUS_CLASS = "[" + MINUS_GLYPHS + "]"

_MINUS_TABLE = str.maketrans({glyph: "-" for glyph in MINUS_GLYPHS})


def normalize_sign_glyphs(text: str) -> str:
    """Rewrite every printed minus glyph to ASCII ``-``.

    Applied at the entry of every PARSER in this module, so the sign class is
    stated once and each `AmountFormat` — and each tolerant parser — inherits
    it rather than re-enumerating the glyphs. This normalizes the SIGN only;
    no other character is touched.

    The parsers that normalize, exhaustively: `parse_amount` (hence every
    `AmountFormat`), `parse_money`, `parse_money_tokens`, `parse_decimal`,
    `parse_decimal_mixed_separator`, `parse_grouped_float`,
    `parse_trailing_minus_dropped`, `parse_french_amount` and
    `parse_digit_scrubbed`.

    The two exported CLEANING helpers do not, and callers should not assume
    they do: `strip_currency` and `pad_leading_decimal` are string utilities
    that pass a non-ASCII sign straight through. A caller that cleans with
    them and then compares or matches on its own must call this first.
    """
    return text.translate(_MINUS_TABLE)


def pad_leading_decimal(text: str) -> str:
    """``.56`` -> ``0.56``. Several banks print sub-dollar amounts that way."""
    return "0" + text if text.startswith(".") else text


def strip_currency(value: str) -> str:
    """Remove the currency symbol and thousands separators, and trim.

    The cleaning step shared by every money format. Exposed so that parsers
    reading a composite cell (a count and an amount in one column, say) can
    normalize it without re-implementing the cleaning — which is how the clone
    family started.
    """
    return value.replace("$", "").replace(",", "").strip()


@lru_cache(maxsize=None)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


#: The most integer digits a money token may carry. Above this the token is
#: not an amount at all — it is a barcode, a reference number or a page-margin
#: digit run that a flattened layout has pushed into an amount column.
#:
#: The bound exists because such a run is not merely wrong, it is FATAL: the
#: ADB engine quantizes every amount to cents in the default 28-digit Decimal
#: context, so a token of 26 integer digits raises `decimal.InvalidOperation`
#: and takes the whole document down with a crash rather than a decline. The
#: bound belongs here, at the grammar that decides what a money token is —
#: `analysis/adb.py` is a protected module and is not the place to defend
#: against input the grammar should never have admitted.
#:
#: 13 is measured, not chosen: the largest integer part of any well-formed
#: amount in the 3,367-document archive is 11 digits, and 2,143 documents
#: carry bare runs of 14 digits or more (longest 54). The bound therefore
#: sits above every amount anyone has printed and far below the crash.
MAX_INTEGER_DIGITS = 13
_INTEGER_RUN = rf"\d{{1,{MAX_INTEGER_DIGITS}}}"

#: Exactly ``digits.dd``. The workhorse shape for statements whose columns are
#: reliable enough that anything else must be rejected rather than guessed.
#:
#: These are FULLMATCH patterns — `parse_amount` applies them with
#: `re.fullmatch`, which is what makes the digit bound above bite. Used with
#: `re.search` instead they would match the TAIL of an over-long run
#: (``"9" * 20 + ".67"`` yields the last 13 digits and the cents), and the
#: bound would be defeated silently. No consumer does that today; the note is
#: here because the two uses look interchangeable and are not.
CENTS = rf"{_INTEGER_RUN}\.\d{{2}}"
#: As above but tolerating a leading minus inside the token itself.
SIGNED_CENTS = rf"-?{_INTEGER_RUN}\.\d{{2}}"


def _within_digit_bound(text: str) -> bool:
    """Whether `text`'s integer part is short enough to be an amount."""
    whole = text.lstrip("+-").split(".")[0].replace(",", "").replace(" ", "")
    return len(whole) <= MAX_INTEGER_DIGITS


#: A plain decimal number: an optional sign, digits, an optional point and
#: fraction (or a bare ``.56``), and nothing else.
#:
#: `Decimal` and `float` accept far more than a statement prints as money —
#: ``NaN``, ``Infinity``, ``sNaN``, exponent notation (``1e30``) and PEP 515
#: underscores (``1_000.00``) — and the raising family below converted
#: whatever they accepted (audit 2026-10-13 PARSERS-4; the non-finite part was
#: already a carried latent). Exponent notation also
#: defeated `MAX_INTEGER_DIGITS`, whose `_within_digit_bound` counts
#: CHARACTERS: ``1e30`` is four of them, and the ``Decimal("1E+30")`` it
#: became is exactly the value the ADB engine's cents quantize cannot hold.
#: Every raising reader therefore requires this shape, after its own cleaning
#: and before converting, and refuses anything else through `_refusal`.
#:
#: Whitespace around the number is stripped before matching, because the two
#: converters always ignored it (tab, newline and NBSP padding included): a
#: padded cell still reads as the number inside it.
_PLAIN_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def _is_plain_number(text: str) -> bool:
    """Whether the cleaned token is a plain decimal number (see `_PLAIN_NUMBER`)."""
    return _PLAIN_NUMBER.fullmatch(text.strip()) is not None


def _readable(text: str) -> bool:
    """The raising family's admission test: a plain number within the bound."""
    return _is_plain_number(text) and _within_digit_bound(text)


def _brackets_are_one_pair_around(text: str) -> bool:
    """No bracket at all, or exactly one ``(`` first and one ``)`` last.

    A bracket format reads the PAIR as the sign, but its strip takes either
    bracket off on its own, so a token holding one of them (``(5.00``,
    ``5.00)``) used to come back POSITIVE (audit 2026-10-13 PARSERS-4). A
    bracket anywhere else (``((5.00)``, ``-(5.00)``) is not the printed
    convention either. Every such token now refuses.
    """
    opens, closes = text.count("("), text.count(")")
    if opens == closes == 0:
        return True
    return opens == closes == 1 and text.startswith("(") and text.endswith(")")


# ---------------------------------------------------------------------------
# The strict engine: clean -> detect sign -> strip sign -> validate -> convert
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AmountFormat:
    """How one printed money format encodes value, sign and padding.

    Fields apply in the order the engine applies them, which is the order the
    per-bank clones used:

    ``remove``
        Characters deleted anywhere in the token before anything else
        (currency symbols, thousands separators, embedded spaces, ``+``).
        Whitespace is stripped from both ends afterwards.
    ``pad_leading_decimal``
        ``"before_sign"`` or ``"after_sign"`` — when a bare ``.56`` should be
        rewritten to ``0.56``, and whether that happens before or after the
        sign markers are removed. Empty means never.
    ``leading_minus`` / ``trailing_minus`` / ``parens``
        Which markers mean "negative". Several banks use more than one. A
        trailing ``-`` in a format without ``trailing_minus``, or a bracket
        that is not one pair around the whole token in a ``parens`` format,
        refuses the token (audit 2026-10-13 PARSERS-4) rather than being
        stripped and ignored.
    ``strip_chars`` / ``lstrip_chars`` / ``remove_chars``
        How the sign markers are then taken off: ``str.strip`` (both ends),
        ``str.lstrip`` (leading only), or deletion everywhere followed by a
        whitespace strip. These are not interchangeable — a bank that deletes
        every ``-`` also accepts ``12-34.56`` as ``1234.56``, and one that only
        lstrips does not.
    ``pattern``
        What must remain for the token to be money at all. Anything else
        returns ``None``: silently mis-reading a reference number as an amount
        is the failure mode this guard exists to prevent.
    """

    remove: str = "$,"
    pad_leading_decimal: str = ""
    leading_minus: bool = False
    trailing_minus: bool = False
    parens: bool = False
    strip_chars: str = ""
    lstrip_chars: str = ""
    remove_chars: str = ""
    pattern: str = CENTS


def parse_amount(value: str | None, fmt: AmountFormat) -> float | None:
    """Parse `value` as money in `fmt`, or return None if it is not money."""
    if not value:
        return None

    text = normalize_sign_glyphs(value)
    for char in fmt.remove:
        text = text.replace(char, "")
    text = text.strip()

    if fmt.pad_leading_decimal == "before_sign":
        text = pad_leading_decimal(text)

    # A sign marker the format cannot read whole is not taken off and ignored
    # (audit 2026-10-13 PARSERS-4): one bracket without its partner, or a
    # trailing ``-`` in a format that does not honour one, refuses the token.
    # Before, the strip removed either and the amount came back POSITIVE.
    if fmt.parens and not _brackets_are_one_pair_around(text):
        return None
    if text.endswith("-") and not fmt.trailing_minus:
        return None

    negative = (
        (fmt.leading_minus and text.startswith("-"))
        or (fmt.trailing_minus and text.endswith("-"))
        or (fmt.parens and text.startswith("(") and text.endswith(")"))
    )

    if fmt.strip_chars:
        text = text.strip(fmt.strip_chars)
    if fmt.lstrip_chars:
        text = text.lstrip(fmt.lstrip_chars)
    if fmt.remove_chars:
        for char in fmt.remove_chars:
            text = text.replace(char, "")
        text = text.strip()

    if fmt.pad_leading_decimal == "after_sign":
        text = pad_leading_decimal(text)

    if not _compiled(fmt.pattern).fullmatch(text):
        return None
    amount = float(text)
    return -amount if negative else amount


# --- the surveyed strict formats -------------------------------------------
# Named for the printed form. Each name is used by one or more banks; the
# mapping lives at the import site so a bank's format is visible in its parser.

#: ``$1,234.56`` only. No sign markers accepted at all — the section heading
#: carries the direction.
STRICT_UNSIGNED = AmountFormat()

#: ``$1,234.56`` / ``-1234.56``; the minus stays inside the token and is
#: converted by `float`.
STRICT_LEADING_SIGN = AmountFormat(pattern=SIGNED_CENTS)

#: ``-1,234.56`` or ``1,234.56-`` (trailing-minus mainframe convention).
STRICT_EITHER_MINUS = AmountFormat(
    leading_minus=True, trailing_minus=True, strip_chars="-",
)

#: As above, additionally tolerating an explicit ``+`` marker on credits.
STRICT_EITHER_MINUS_OR_PLUS = AmountFormat(
    leading_minus=True, trailing_minus=True, strip_chars="+-",
)

#: As above, for layouts that also print spaces inside the amount cell.
STRICT_EITHER_MINUS_OR_PLUS_SPACED = AmountFormat(
    remove="$, ", leading_minus=True, trailing_minus=True, strip_chars="+-",
)

#: ``1 234.56-`` — spaces inside the cell, leading or trailing minus.
EITHER_MINUS_SPACED = AmountFormat(
    remove="$, ", leading_minus=True, trailing_minus=True, strip_chars="-",
)

#: Leading or trailing minus, with every ``-`` deleted rather than trimmed
#: (tolerates OCR that scatters the marker into the middle of the cell).
EITHER_MINUS_DROPPED = AmountFormat(
    leading_minus=True, trailing_minus=True, remove_chars="-",
)

#: Leading or trailing minus, plus bare ``.56`` sub-dollar amounts.
EITHER_MINUS_PADDED = AmountFormat(
    pad_leading_decimal="after_sign",
    leading_minus=True,
    trailing_minus=True,
    strip_chars="-",
)

#: Leading minus only, trimmed from the front.
LEADING_MINUS = AmountFormat(leading_minus=True, lstrip_chars="-")

#: Leading minus only, with every ``-`` deleted rather than trimmed.
LEADING_MINUS_DROPPED = AmountFormat(leading_minus=True, remove_chars="-")

#: Leading minus only, plus bare ``.56`` sub-dollar amounts.
LEADING_MINUS_PADDED = AmountFormat(
    pad_leading_decimal="before_sign", leading_minus=True, lstrip_chars="-",
)

#: ``(1,234.56)`` or ``-1,234.56``.
PARENS_OR_LEADING_MINUS = AmountFormat(
    parens=True, leading_minus=True, strip_chars="()", lstrip_chars="-",
)

#: ``(1,234.56)`` / ``-1,234.56`` / ``+1,234.56``.
PARENS_OR_LEADING_MINUS_OR_PLUS = AmountFormat(
    remove="$,+", parens=True, leading_minus=True, strip_chars="-()",
)


# ---------------------------------------------------------------------------
# The tolerant token parser (formerly analysis/td_can.py::_parse_money)
# ---------------------------------------------------------------------------

#: A money token is a WHOLE number, not a fragment of one. Both boundaries
#: are load-bearing and neither is redundant:
#:
#: ``(?<![\d.])``
#:     the match may not begin part-way through a number. Without it, a token
#:     the trailing boundary has already refused is re-entered one digit later
#:     and matched anyway — ``34.9`` would refuse ``34`` and then return
#:     ``9.0``.
#: ``(?![.,]?\d)``
#:     what follows may not continue the number. This is what makes ONE
#:     decimal place not-money: money prints two (or three, in a rate column),
#:     and the optional decimal group is what let ``34.9`` match its integer
#:     part alone and return ``34.0`` — a silently truncated amount, the worst
#:     failure this module can have, because it is a plausible number. The
#:     comma is in the class because the token parser groups with it, so
#:     ``1,234.5`` must not fall back to matching ``1``.
#:
#: THE RULE, EXACTLY AS IMPLEMENTED — a money token carries either no decimal
#: point at all or exactly TWO OR THREE decimals, and is adjacent to neither a
#: digit nor a dot on either side. Three consequences worth stating plainly,
#: because "one decimal is not money" is a shorter claim than the code makes:
#:
#: * these parsers SEARCH, so refusing a token is not the same as returning
#:   None: the search resumes and yields the next token that does qualify.
#:   ``parse_money("34.9 100.00")`` is ``100.0``, not ``None``. None comes back
#:   only when no qualifying token exists anywhere in the input.
#: * the refusal covers more than one decimal place. A dot-adjacent token is
#:   refused (``1.2.3``, ``12.345.67``) and so is anything with four or more
#:   decimals (``34.9999``, and the ``0.000668276`` exchange-rate factor that
#:   chase's own local grammar already had to defend against).
#: * `parse_digit_scrubbed` does NOT get this rule. It keeps only digits and
#:   dots and calls `float`, so it still reads ``34.9`` as ``34.9`` — the true
#:   value, not a truncation. It was never the defect and is left alone;
#:   callers bound it with `guard` instead.
#:
#: A layout that legitimately prints one decimal pads it at its own call site,
#: where the format lives (`analysis/scotia.py::_amount_value` is the surveyed
#: example). Nothing in the archive prints a one-decimal amount unpadded.
_NOT_PART_OF_A_LONGER_NUMBER = r"(?<![\d.])"
_NOT_CONTINUED = r"(?![.,]?\d)"

_TOKEN_RE = re.compile(
    rf"{_NOT_PART_OF_A_LONGER_NUMBER}(-)?({_INTEGER_RUN}(?:\.\d{{2,3}})?){_NOT_CONTINUED}"
    rf"([A-Z/-]*)?",
    re.IGNORECASE,
)
_TOKENS_RE = re.compile(
    rf"(?<![\d.,])\$?(\d[\d,]*(?:\.\d{{2,3}})?){_NOT_CONTINUED}([D*-]?)"
)


def _pad_bare_decimal(text: str) -> str:
    """``.56`` -> ``0.56``, behind an optional sign.

    A bare sub-dollar amount is one of the surveyed axes this module tolerates
    (see the module docstring), but the tolerant parser never actually read
    one: with no leading digit the search skipped the dot and matched ``56``,
    returning the amount a HUNDRED TIMES too large. Now that a token must be a
    whole number, the same shape would be refused instead — so the leading
    zero is restored here, which is what the strict engine has always done via
    its `pad_leading_decimal` field and what the callers that meet this shape
    (`analysis/pnc.py`, `analysis/citizens.py`) do at their own call sites.
    """
    sign, rest = ("-", text[1:]) if text.startswith("-") else ("", text)
    # A digit must actually follow the dot: padding a lone "." would
    # manufacture a zero out of punctuation.
    if rest.startswith(".") and rest[1:2].isdigit():
        return f"{sign}0{rest}"
    return text


#: The suffixes that mark a debit, matched as WHOLE marker tokens.
#:
#: The rule was once "the suffix CONTAINS a D", which is not a rule about
#: markers at all: it made ``100.00CREDIT`` negative, because "CREDIT" has a D
#: in it. Any suffix a flattened cell welds to an amount could invert its sign.
#:
#: The set is what the archive actually prints. ``OD`` is TD Canada's overdraft
#: marker on a running balance (``371.96OD`` — the balance is overdrawn, so it
#: IS negative); it appears 596 times across 50 documents, 39 of them claimed
#: and 37 validated, so dropping it in the name of an "exact D/DR" rule would
#: have inverted the balance walk on every one of them.
#:
#: THE MARKER MUST BE WELDED TO THE AMOUNT, and that boundary is load-bearing
#: rather than incidental: the suffix group cannot cross whitespace, so a
#: DETACHED ``OD``/``DR``/``D`` is description text and leaves the sign alone.
#: The archive prints detached ones 212 times across 23 documents, 6 of them
#: VALIDATED — PNC prints ``36.00 OD Fee`` (an overdraft fee, a positive
#: amount) and Huntington prints ``282.12 OD PROTECTION TRANSFER``. Relaxing
#: the whitespace boundary to "read the next word as a marker" would negate a
#: real fee on documents that validate today. `tests/test_money.py` pins it.
_DEBIT_MARKERS = frozenset({"D", "DR", "OD"})


def parse_money(value: str | None) -> float | None:
    """First money-shaped token in `value`, sign-aware, rounded to cents.

    Tolerant by design: it searches rather than anchors, ignores ``*`` fill
    characters, accepts three decimal places (some statements print rates in
    the same column), and reads a trailing debit marker (``D``/``DR``/``OD``)
    or ``-``. Used wherever the surrounding layout already established that
    the cell is an amount, so over-matching a reference number is not a risk.

    Zero is returned as ``+0.0`` regardless of markers — a signed zero would
    round-trip badly through the reconciliation identities.
    """
    if not value:
        return None
    text = normalize_sign_glyphs(value)
    text = text.replace("$", "").replace(",", "").replace("*", "").strip()
    text = _pad_bare_decimal(text)
    m = _TOKEN_RE.search(text)
    if not m:
        return None
    amount = float(m.group(2))
    if amount == 0:
        return 0.0
    suffix = (m.group(3) or "").upper()
    # "/" is a separator TD prints inside the marker cell ("1234.56/D"), not
    # part of the marker; a "-" anywhere in the suffix is the trailing-minus
    # convention and is honoured on its own.
    marker = suffix.replace("/", "").strip("-")
    if m.group(1) or "-" in suffix or marker in _DEBIT_MARKERS:
        amount *= -1
    return round(amount, 2)


def parse_money_tokens(value: str | None) -> list[float]:
    """Every money-shaped token in `value`, in order, sign-aware.

    Used to read a whole flattened table cell whose column boundaries the PDF
    extraction destroyed.
    """
    if not value:
        return []
    out = []
    for number, suffix in _TOKENS_RE.findall(normalize_sign_glyphs(value)):
        text = number.replace(",", "")
        if not _within_digit_bound(text):
            continue
        amount = float(text)
        if "D" in suffix.upper() or "-" in suffix:
            amount *= -1
        out.append(round(amount, 2))
    return out


def _refusal_class(text: str) -> str:
    """WHY the grammar refused, as a category — never the text itself.

    A refusal message crosses an exception boundary, so it may carry no
    statement content whatsoever: the exception-boundary law is registry ids
    and class names only. (Through batch 5 the boundary in question was
    `webapp/worker.py`, which published `str(exc)` as the job error; batch 6's
    §WORKER-PRIVACY withholds it there. The category rule below does not rest
    on that — it is about what this function may return, not about who reads
    it.) These categories are derived FROM the
    token and describe only its shape, which is what a diagnosis actually
    needs — the token itself is in the document, and the document is where it
    stays. (W3 §MG-C2 D1; extended to the whole raising family by
    §MONEY-PRIVACY.)

    The four categories are a closed vocabulary. Each is a fixed string chosen
    by a MEASUREMENT on the token — "does it hold a digit", "how long is the
    integer run", "how many decimals" — so no branch can return a value that
    varies with the content. That closure is the privacy property: a category
    that interpolated any part of the token would be a leak wearing a
    reason's clothes.
    """
    stripped = strip_currency(normalize_sign_glyphs(text)).strip()
    if not any(ch.isdigit() for ch in stripped):
        return "no digits in the cell"
    integer_part = re.split(r"[.,]", stripped.lstrip("-+"), maxsplit=1)[0]
    if len(integer_part) > MAX_INTEGER_DIGITS:
        return f"integer run longer than the {MAX_INTEGER_DIGITS}-digit bound"
    decimals = re.search(r"\.(\d+)\b", stripped)
    if decimals and len(decimals.group(1)) not in (2, 3):
        return "decimal places are neither two nor three"
    return "not a money token"


def _refusal(reader: str, token: str) -> ValueError:
    """THE refusal. Every raise in this module is built here (§MONEY-PRIVACY).

    One constructor rather than nine `raise` statements, because the property
    being defended is a property of the SET: "no exception this module raises
    quotes the document". A property of a set is only as strong as its widest
    member, and nine hand-written messages are nine chances to write the tenth
    one with an f-string in it. Here there is one message, it is assembled from
    the reader's NAME (a symbol in this file) and `_refusal_class`'s closed
    vocabulary, and `token` is passed in only to be MEASURED — it reaches the
    message through nothing but that four-value classification.

    It RETURNS the exception rather than raising it, and that is load-bearing:
    the call site writes ``raise _refusal(...)`` from OUTSIDE the ``except``
    block that swallowed the conversion error, so the exception it raises
    carries neither a ``__cause__`` nor a ``__context__``. That matters because
    `float`'s own ValueError quotes its argument verbatim
    (``could not convert string to float: '<the cell>'``) — a chained refusal
    would pass the privacy test on ``str(exc)`` and fail it the moment anything
    rendered a traceback. The chain is severed at the source instead of being
    suppressed at each renderer.
    """
    return ValueError(
        f"money grammar refused a printed token "
        f"({_refusal_class(token)}; reader={reader})"
    )


def money_refusal(reader: str, token: str) -> ValueError:
    """`_refusal` under a PUBLIC name, for money sites outside this module.

    Added by W3 §PRIVACY3, and the reason is a guard rather than taste.
    `analysis/bmo.py` and `analysis/farmers_merchants.py` hold the same
    `_amount` refusal this module's family holds, and repointing them at the
    shared constructor is the whole fix — but importing `_refusal` by its
    private name trips
    `tests/test_no_parser_helper_clones.py::test_no_parser_imports_a_private_helper_from_another_parser`,
    whose remedy text is exactly "promote the helper into a shared module under
    `analysis/`". This module is already declared one (`SHARED_UTILITIES`), so
    the promotion is the name and nothing else.

    `_refusal` stays: every `raise` in this module is still
    ``raise _refusal(...)``, byte for byte, so §MONEYPRIV's AST chain-guard
    reads the same file it always did. This wrapper adds a frame that is gone
    by the time anything is raised, because it RETURNS the exception (§MP2) —
    the call site writes ``raise money_refusal(...)`` from outside any handler,
    exactly as the eleven sites in here do.

    Its sibling is `date_tokens.date_refusal`, which is public from birth for
    the same reason.
    """
    return _refusal(reader, token)


def read_money(
    token: str | None,
    reader: Callable[[str], float | None] = parse_money,
) -> float | None:
    """Read `token` as money, telling ABSENCE apart from a REFUSAL.

    Use this where the token is REGEX-GUARANTEED — a capture group, a cell a
    pattern already matched — so that a `None` from the reader can only mean
    the grammar refused. Do NOT use it as a column-finding PROBE over
    arbitrary cells: a probe asks "is this money?" and must be answered, not
    raised at. Those callers keep a reader that returns `None` (W3 §MG-C2
    D2/D3, `regions._money`).

    The idiom this exists to replace is ``parse_money(x) or 0.0`` (and its
    kin ``abs(_money(x) or 0.0)``), which cannot tell the two apart. Under it
    a token the grammar REFUSED was published as a hard ``0.00`` — a figure
    the bank printed, replaced by a number it did not, silently, on a document
    the platform then went on to reconcile and approve. Cards §MG3 and §MG4
    deliberately WIDENED what the grammar refuses (one-decimal tokens,
    dot-adjacent tokens, runs past the 13-digit bound), so every one of those
    refusals had a fail-open waiting for it. That is the shape this kills.

    ABSENCE is not a refusal. No token at all — ``None``, or whitespace —
    means the statement does not print that figure, and the answer stays
    ``None`` so the caller's ``or 0.0`` can still supply the arithmetic
    identity for a section the document genuinely does not have. Only a token
    that is THERE and that the grammar declines is an error.

    A refusal raises ``ValueError``: the documented contract of the raising
    family (§MG4), the convention ``chase._money_required`` and
    ``banco_popular`` already follow, and fail-closed at the pipeline — the
    document declines instead of publishing a number nobody printed.

    **The message never quotes the token.** It names the reader and the
    refusal CLASS, because statement content may not cross an exception
    boundary — the rule holds whatever any particular boundary does with the
    message, and it is `_refusal` that enforces it for every raise in this
    module. See :func:`_refusal_class`.

    `reader` is the caller's own money reader, because the grammar is shared
    but the FORMAT is local: a parser that anchors with its own guard passes
    that guard's reader here rather than reimplementing this check.

    Measured over the frozen archive (W3 §MG-C2): **zero** refusals of a
    present token at any call site, over the 3,367 documents that have a
    cached artifact (of 3,380 distinct shas; the other 13 are the run's
    deferred set). Every ``None`` the archive produces today is an absence,
    which is why closing the fail-open moves nothing and is worth doing before
    something does.
    """
    if token is None:
        return None
    text = token if isinstance(token, str) else str(token)
    if not text.strip():
        return None
    amount = reader(text)
    if amount is None:
        raise _refusal(getattr(reader, "__name__", "reader"), text)
    return amount


# ---------------------------------------------------------------------------
# Raising / Decimal parsers
#
# THE REFUSAL LAW FOR THIS SECTION (W3 §MONEY-PRIVACY, extending §MG-C2 D1).
# Every function below refuses by raising `_refusal(...)`, and none of them
# quotes the token. Until batch 6 each one raised `ValueError(value)` — the
# printed cell as the message — while `webapp/worker.py` published `str(exc)`
# as the job error into the durable store, so a refusal put statement content
# somewhere it may not go. Batch 4 closed exactly this law one layer up, at
# `read_money`; this closes it at the layer the parsers actually call, and
# §WORKER-PRIVACY closes the boundary end in the same batch. The source fix is
# the one that generalises: it holds for every reader of the message, not only
# for the one boundary that was known to publish it.
#
# Two shapes are involved and only one of them is visible as a `raise`:
#
# * the explicit `raise ValueError(value)` guarding the digit bound, and
# * the conversion itself. `float("N/A")` raises
#   ``could not convert string to float: 'N/A'`` — the token, verbatim, from
#   the standard library — and these functions' documented contract was to let
#   that escape. `Decimal` is the quiet one (`InvalidOperation` says only
#   `ConversionSyntax`), which is precisely why the float callers were the
#   worse leak and looked the same in the source.
#
# So the pattern below is uniform: TRY the conversion, swallow its error, and
# raise the one named refusal from outside the handler — never `from exc`,
# which would keep the quoting exception alive as a `__cause__` for any
# traceback renderer to print.
# ---------------------------------------------------------------------------

def parse_decimal(value: str) -> Decimal:
    """``$1,234.56`` -> ``Decimal("1234.56")``; raises ValueError otherwise.

    For parsers that keep Decimal end to end so that their own totals are exact.

    The refusal names the reader and the refusal CLASS and never echoes the
    cell — see `_refusal`.
    """
    text = normalize_sign_glyphs(value).replace("$", "").replace(",", "").strip()
    if _readable(text):
        try:
            return Decimal(text)
        except InvalidOperation:
            pass                      # -> the one refusal, below and unchained
    raise _refusal("parse_decimal", value)


#: One money cell with an optional printed sign: ``$0.69``, ``-$1,234.56``,
#: ``− $1,234.56``, ``+ $3.57``. A SUB-PATTERN — no anchors and no capturing
#: groups, so a parser can compose it into a row pattern without its group
#: numbers shifting underneath the row's own groups.
#:
#: The space is optional because the sign and the figure are two CELLS: layouts
#: that set the sign in the label column print it one space away, and the same
#: issuer prints it welded to the symbol elsewhere. Both are the same column.
#:
#: The sign half is `MINUS_GLYPHS` and is not re-spelled here — this pattern
#: is the finder for `parse_signed_decimal`, and a finder that admits a glyph
#: its parser refuses hands the parser a token it must then decline. Keeping
#: them one class is what makes the two agree by construction.
SIGNED_MONEY_TOKEN = r"[" + MINUS_GLYPHS + r"+]?\s?\$[\d,]+\.\d{2}"


def parse_signed_decimal(value: str) -> Decimal:
    """A signed money cell -> `Decimal`, sign preserved. Raises `ValueError`.

    For layouts that print the direction as a sign glyph on the amount itself
    rather than as a column heading, where the sign is the ONLY direction
    evidence the platform should trust (a "Type" or "Method" column names the
    product, not the direction — see `analysis/mercury.py`).

    Delegates the numeric conversion to `parse_decimal`, so what is added here
    is the sign reading and nothing else; anything that is not money still
    raises rather than being guessed at. The refusal is therefore
    `parse_decimal`'s and says ``reader=parse_decimal`` — the function that
    actually declined the token rather than the entry point, which is what a
    diagnosis follows. It quotes nothing either way (§MONEY-PRIVACY).

    The sign is read from `MINUS_GLYPHS`, the one class this module states, so
    a glyph outside it is not a sign HERE either. ``—$500.00`` therefore
    RAISES rather than resolving: the em dash survives into `parse_decimal`,
    which declines a token it cannot convert. That is the fail-closed answer
    and the deliberate one — the alternative readings are ``+500.00`` (the
    tolerant parsers' answer, a debit booked as a credit) and ``-500.00`` (the
    shadowed class's answer, which would have flipped the one archive document
    that prints the shape, where the em dash is a column placeholder on a
    positive balance). A document that genuinely prints an em-dash sign
    declines instead of publishing a figure nobody printed.
    """
    text = value.strip()
    negative = bool(text) and text[0] in MINUS_GLYPHS
    if negative or text.startswith("+"):
        text = text[1:].lstrip()
    amount = parse_decimal(text)
    return -amount if negative else amount


def parse_decimal_mixed_separator(value: str, *, single_comma_only: bool = False) -> Decimal:
    """Decimal parse where the comma may be a thousands separator OR the
    decimal mark, decided structurally rather than by locale.

    A comma is read as the decimal mark only when there is no ``.`` in the
    token and the comma is followed by exactly two digits — i.e. ``1234,56``.
    ``1,234.56`` and ``1,234`` keep the US reading. `single_comma_only`
    additionally requires that there be exactly one comma, which is the
    stricter rule one layout needs to avoid re-reading ``1,23,45``.

    Under `single_comma_only`, a two-digit tail after a SECOND comma
    (``1,234,56``, ``1,23,45``) is neither reading and refuses (audit
    2026-10-13 PARSERS-4). It used to fall through to the US reading, which
    deletes every comma and returns a hundred times the cents reading.
    """
    text = normalize_sign_glyphs(value).replace("$", "").strip()
    two_digit_tail = "," in text and len(text.rsplit(",", 1)[1]) == 2
    if single_comma_only and "." not in text and text.count(",") > 1 and two_digit_tail:
        raise _refusal("parse_decimal_mixed_separator", value)
    comma_is_decimal = (
        "." not in text
        and (text.count(",") == 1 if single_comma_only else "," in text)
        and two_digit_tail
    )
    if comma_is_decimal:
        whole, cents = text.rsplit(",", 1)
        text = f"{whole.replace(',', '')}.{cents}"
    else:
        text = text.replace(",", "")
    if _readable(text):
        try:
            return Decimal(text)
        except InvalidOperation:
            pass                      # -> the one refusal, below and unchained
    raise _refusal("parse_decimal_mixed_separator", value)


def parse_grouped_float(value: str) -> float:
    """``1,234.56`` -> ``1234.56``; raises ValueError on anything else.

    The refusal names the reader and the refusal CLASS and never echoes the
    cell — see `_refusal`.
    """
    text = normalize_sign_glyphs(value).replace(",", "")
    if _readable(text):
        try:
            return float(text)
        except ValueError:
            pass                      # -> the one refusal, below and unchained
    raise _refusal("parse_grouped_float", value)


def parse_trailing_minus_dropped(value: str) -> float:
    """``1,234.56-`` -> ``1234.56``: the trailing minus is discarded, not
    applied.

    One layout prints a trailing marker on every amount in a section whose
    direction the section heading already fixes, so honouring it would
    double-negate. Raises `ValueError` when the token is not a number — naming
    the reader and the refusal CLASS, never the cell (see `_refusal`).
    """
    text = normalize_sign_glyphs(value).replace("$", "").replace(",", "").rstrip("-")
    if _readable(text):
        try:
            return float(text)
        except ValueError:
            pass                      # -> the one refusal, below and unchained
    raise _refusal("parse_trailing_minus_dropped", value)


def parse_french_amount(value: str, *, parens: bool = False) -> float:
    """FR-CA money: space thousands separator and comma decimal mark.

    ``1 234,56`` -> ``1234.56``. With `parens`, ``(1 234,56)`` is negative —
    the bracket convention French-language Canadian statements use instead of
    a minus sign. Raises ValueError when the token is not a number — naming
    the reader and the refusal CLASS, never the cell (see `_refusal`).

    With `parens`, a bracket that is not one pair around the whole cell
    (``(1 066,25`` with its closing bracket lost) refuses rather than reading
    POSITIVE (audit 2026-10-13 PARSERS-4): `analysis/rbc.py` records the time
    a capture that dropped the closing bracket sign-flipped every overdrawn
    balance of the French family.
    """
    normalized = normalize_sign_glyphs(value)
    if parens:
        bracketed = normalized.strip()
        if not _brackets_are_one_pair_around(bracketed):
            raise _refusal("parse_french_amount", value)
        negative = bracketed.startswith("(") and bracketed.endswith(")")
        text = normalized.strip("()")
    else:
        negative = False
        text = normalized
    text = text.replace(" ", "").replace(",", ".")
    if _readable(text):
        try:
            amount = float(text)
        except ValueError:
            pass                      # -> the one refusal, below and unchained
        else:
            return round(-amount if negative else amount, 2)
    raise _refusal("parse_french_amount", value)


def parse_digit_scrubbed(
    value: str,
    *,
    parens: bool = False,
    leading_minus: bool = False,
    trailing_minus: bool = False,
    guard: re.Pattern[str] | None = None,
) -> float | None:
    """Sign markers first, then keep only digits and dots.

    For layouts whose amount cells collect stray characters that no
    enumeration of separators would cover. `guard`, when supplied, must
    fullmatch the (stripped) token first, so scrubbing never turns arbitrary
    text into a number.

    NOT a member of the raising family, and the return annotation is the
    contract: a token this cannot read comes back as ``None``. There is one
    exception and it is inherited rather than designed — scrubbing keeps DOTS,
    so a cell holding two of them (``12.34.56``, or a bare ``.1.2``) reaches
    `float` as a string `float` cannot convert and has always raised. That
    raise quoted the scrubbed cell, so §MONEY-PRIVACY re-routes it through
    `_refusal` like every other refusal in this module. It is deliberately
    still a RAISE: turning it into ``None`` would hand the caller's absence
    branch a token that is present, which is a behaviour change with an
    archive sweep of its own and no place in a card whose expected movement is
    zero. Unreachable at all three live call sites today — `analysis/chase.py`,
    `analysis/chase_savings.py` and `analysis/capital_one.py` each pass a
    `guard` that admits at most one decimal point — which is why closing it
    costs nothing and is worth doing before a fourth caller arrives without one.
    """
    text = normalize_sign_glyphs(value).strip()
    if not text:
        return None
    if guard is not None and not guard.fullmatch(text):
        return None
    negative = (
        (parens and text.startswith("("))
        or (leading_minus and text.startswith("-"))
        or (trailing_minus and text.endswith("-"))
    )
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        return None
    if not _within_digit_bound(cleaned):
        return None
    try:
        amount = float(cleaned)
    except ValueError:
        pass                          # -> the one refusal, below and unchained
    else:
        return -amount if negative else amount
    raise _refusal("parse_digit_scrubbed", value)
