"""Shared money parsing for every statement parser (R-2 / MASTER_PLAN P1-1a).

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
  parentheses ``(1,234.56)``, and ``D``/``DR`` suffixes (TD Canada)
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

`tests/test_money.py` pins every function against the pre-R-2 implementation it
replaced, over a shared matrix of positive, negative and malformed inputs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache

__all__ = [
    "AmountFormat",
    "parse_amount",
    "parse_money",
    "parse_money_tokens",
    "parse_decimal",
    "parse_decimal_mixed_separator",
    "parse_grouped_float",
    "parse_french_amount",
    "parse_digit_scrubbed",
    "pad_leading_decimal",
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

def pad_leading_decimal(text: str) -> str:
    """``.56`` -> ``0.56``. Several banks print sub-dollar amounts that way."""
    return "0" + text if text.startswith(".") else text


@lru_cache(maxsize=None)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


#: Exactly ``digits.dd``. The workhorse shape for statements whose columns are
#: reliable enough that anything else must be rejected rather than guessed.
CENTS = r"\d+\.\d{2}"
#: As above but tolerating a leading minus inside the token itself.
SIGNED_CENTS = r"-?\d+\.\d{2}"


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
        Which markers mean "negative". Several banks use more than one.
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

    text = value
    for char in fmt.remove:
        text = text.replace(char, "")
    text = text.strip()

    if fmt.pad_leading_decimal == "before_sign":
        text = pad_leading_decimal(text)

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

_TOKEN_RE = re.compile(r"(-)?(\d+(?:\.\d{2,3})?)([A-Z/-]*)?", re.IGNORECASE)
_TOKENS_RE = re.compile(r"\$?(\d[\d,]*(?:\.\d{2,3})?)([D*-]?)")


def parse_money(value: str | None) -> float | None:
    """First money-shaped token in `value`, sign-aware, rounded to cents.

    Tolerant by design: it searches rather than anchors, ignores ``*`` fill
    characters, accepts three decimal places (some statements print rates in
    the same column), and reads a trailing ``D``/``DR`` or ``-`` as a debit
    marker. Used wherever the surrounding layout already established that the
    cell is an amount, so over-matching a reference number is not a risk.

    Zero is returned as ``+0.0`` regardless of markers — a signed zero would
    round-trip badly through the reconciliation identities.
    """
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").replace("*", "").strip()
    m = _TOKEN_RE.search(text)
    if not m:
        return None
    amount = float(m.group(2))
    if amount == 0:
        return 0.0
    if m.group(1) or (m.group(3) and ("D" in m.group(3).upper() or "-" in m.group(3))):
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
    for number, suffix in _TOKENS_RE.findall(value):
        text = number.replace(",", "")
        amount = float(text)
        if "D" in suffix.upper() or "-" in suffix:
            amount *= -1
        out.append(round(amount, 2))
    return out


# ---------------------------------------------------------------------------
# Raising / Decimal parsers
# ---------------------------------------------------------------------------

def parse_decimal(value: str) -> Decimal:
    """``$1,234.56`` -> ``Decimal("1234.56")``; raises ValueError otherwise.

    For parsers that keep Decimal end to end so that their own totals are exact.
    """
    try:
        return Decimal(value.replace("$", "").replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(value) from exc


def parse_decimal_mixed_separator(value: str, *, single_comma_only: bool = False) -> Decimal:
    """Decimal parse where the comma may be a thousands separator OR the
    decimal mark, decided structurally rather than by locale.

    A comma is read as the decimal mark only when there is no ``.`` in the
    token and the comma is followed by exactly two digits — i.e. ``1234,56``.
    ``1,234.56`` and ``1,234`` keep the US reading. `single_comma_only`
    additionally requires that there be exactly one comma, which is the
    stricter rule one layout needs to avoid re-reading ``1,23,45``.
    """
    text = value.replace("$", "").strip()
    comma_is_decimal = (
        "." not in text
        and (text.count(",") == 1 if single_comma_only else "," in text)
        and len(text.rsplit(",", 1)[1]) == 2
    )
    if comma_is_decimal:
        whole, cents = text.rsplit(",", 1)
        text = f"{whole.replace(',', '')}.{cents}"
    else:
        text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(value) from exc


def parse_grouped_float(value: str) -> float:
    """``1,234.56`` -> ``1234.56``; raises ValueError on anything else."""
    return float(value.replace(",", ""))


def parse_french_amount(value: str, *, parens: bool = False) -> float:
    """FR-CA money: space thousands separator and comma decimal mark.

    ``1 234,56`` -> ``1234.56``. With `parens`, ``(1 234,56)`` is negative —
    the bracket convention French-language Canadian statements use instead of
    a minus sign. Raises ValueError when the token is not a number.
    """
    if parens:
        bracketed = value.strip()
        negative = bracketed.startswith("(") and bracketed.endswith(")")
        text = value.strip("()")
    else:
        negative = False
        text = value
    amount = float(text.replace(" ", "").replace(",", "."))
    return round(-amount if negative else amount, 2)


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
    """
    text = value.strip()
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
    amount = float(cleaned)
    return -amount if negative else amount
