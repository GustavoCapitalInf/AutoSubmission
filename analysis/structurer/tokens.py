"""Date and money tokens, as a layout-agnostic structurer must read them.

Every parser in `analysis/` knows which shape its bank prints and matches that
one. A structurer knows no bank, so it must read them all and let the
document's own arithmetic say which reading was right (`rows.py`). This module
is only the reading; it decides nothing.

Two rules it does enforce, because they are about truth rather than layout:

* **shape is not validity.** `13/45/24` matches `MM/DD/YY` perfectly and is not
  a date. Calendar validity is checked through `analysis.date_tokens.iso_or_none`
  — the same helper W3-1 introduced when exactly this cost us 17 crashes.
* **a year is never invented.** A row printing `01/05` has no year, and the
  structurer supplies one only from a year the DOCUMENT prints (period line, or
  the majority year among dated rows that carry one). `grounding.py` then
  re-verifies the resulting date against the page. Reaching for `date.today()`
  here would silently re-date an archived statement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..date_tokens import iso_or_none
from ..money import MINUS_CLASS, MINUS_GLYPHS, normalize_sign_glyphs, parse_money

__all__ = [
    "MONEY_RE",
    "MoneyToken",
    "document_year",
    "iso_from_any",
    "money_tokens",
    "money_value",
    "read_date",
]

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
#: Month names in the languages the archive actually contains (English and
#: Canadian French — RBC/Desjardins/TD Canada print both). Extending this list
#: is adding a language, not adding a bank.
_MONTH_WORD = (
    r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|"
    r"JANV|FEVR|MARS|AVR|MAI|JUIN|JUIL|AOUT|SEPT|OCTO|NOVE|DECE)[A-Z]*\.?"
)
_FRENCH_MONTHS = {
    "JANV": 1, "FEVR": 2, "MARS": 3, "AVR": 4, "MAI": 5, "JUIN": 6,
    "JUIL": 7, "AOUT": 8, "SEPT": 9, "OCTO": 10, "NOVE": 11, "DECE": 12,
}

#: Every row-date shape, anchored so a caller can also use them unanchored.
DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?P<d>\d{4}-\d{2}-\d{2})(?!\d)"),
    re.compile(r"(?P<d>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})(?!\d)"),
    re.compile(r"(?P<d>\d{1,2}[/.-]\d{1,2})(?!\d)"),
    re.compile(rf"(?P<d>{_MONTH_WORD}\s+\d{{1,2}}(?:,?\s+\d{{4}})?)(?!\d)", re.IGNORECASE),
    re.compile(rf"(?P<d>\d{{1,2}}\s+{_MONTH_WORD}(?:\s+\d{{4}})?)(?!\d)", re.IGNORECASE),
)

#: Money as printed: optional currency mark, thousands groups, two decimals,
#: with parentheses or a trailing/leading minus for negatives.
#:
#: THE SIGN HALF IS `money.MINUS_CLASS`, not a bare ASCII hyphen, and the same
#: class appears in all three positions — leading, trailing, and the guard
#: lookbehind. A structurer knows no bank, so it meets every glyph the archive
#: prints where a minus belongs (U+2212 on one month's statement and U+2013 on
#: the next, from one issuer's generator — W3 §MGD). Matching only ASCII here
#: did not merely refuse a signed token: the sign fell OUTSIDE the token, the
#: digits matched on their own, and the amount was read POSITIVE. A debit
#: booked as a credit, generically, on every document no registration claims.
#:
#: The three positions move together or not at all. Widening the token without
#: widening the lookbehind would read the right-hand amount of `1,000.00−500.00`
#: as a new token, where ASCII yields none; widening the lookbehind without the
#: token would refuse a signed amount outright. Both ends match the ASCII rule
#: exactly, which is the property the differential in `tests/test_structurer.py`
#: pins.
#:
#: ASCII leads the character class because a hyphen there is a literal rather
#: than the start of a range — the same reason `money.MINUS_CLASS` is spelled
#: that way and derived rather than re-spelled.
MONEY_RE = re.compile(
    rf"(?<![{MINUS_GLYPHS}\d./])"
    rf"(?P<token>\(?{MINUS_CLASS}?[$€£]?\s?\d{{1,3}}(?:,\d{{3}})*\.\d{{2}}\)?{MINUS_CLASS}?)"
    r"(?![\d/])"
)

_YEAR_NEAR_DATE_RE = re.compile(
    rf"(?:{_MONTH_WORD}\s+\d{{1,2}},?\s+|\d{{1,2}}[/.-]\d{{1,2}}[/.-])((?:19|20)?\d{{2}})(?!\d)",
    re.IGNORECASE,
)


def _month_number(word: str) -> int | None:
    key = word.upper().rstrip(".")
    if key[:4] in _FRENCH_MONTHS and key[:3] not in _MONTHS:
        return _FRENCH_MONTHS[key[:4]]
    return _MONTHS.get(key[:3])


def read_date(token: str, *, default_year: int | None) -> str | None:
    """One date token in any supported shape -> ISO, or None if it is not a date.

    `default_year` is used only for shapes that print no year at all; passing
    None means such a token cannot be read, which is the correct answer for a
    document that never prints a year anywhere.
    """
    text = re.sub(r"\s+", " ", token.strip().upper())
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return iso_or_none(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", text)
    if m:
        month, day, year = (int(part) for part in m.groups())
        return iso_or_none(year + 2000 if year < 100 else year, month, day)
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})", text)
    if m and default_year:
        return iso_or_none(default_year, int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(rf"({_MONTH_WORD})\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?", text)
    if m:
        year = int(m.group(3)) if m.group(3) else default_year
        month = _month_number(m.group(1))
        return iso_or_none(year, month, int(m.group(2))) if year and month else None
    m = re.fullmatch(rf"(\d{{1,2}})\s+({_MONTH_WORD})(?:\s+(\d{{4}}))?", text)
    if m:
        year = int(m.group(3)) if m.group(3) else default_year
        month = _month_number(m.group(2))
        return iso_or_none(year, month, int(m.group(1))) if year and month else None
    return None


def iso_from_any(text: str, *, default_year: int | None) -> str | None:
    """The first readable date anywhere in `text`."""
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            iso = read_date(match.group("d"), default_year=default_year)
            if iso:
                return iso
    return None


@dataclass(frozen=True)
class MoneyToken:
    """One printed amount, with where it was printed."""

    text: str
    value: float
    start: int
    end: int

    @property
    def magnitude(self) -> float:
        return abs(self.value)


def money_value(token: str) -> float | None:
    """A money token's SIGNED value; parentheses and a trailing minus are both
    the accounting negative, which several banks use interchangeably.

    THE SIGN CLASS IS NOT SPELLED HERE. `normalize_sign_glyphs` rewrites every
    glyph the shared canon admits to ASCII ``-`` first, so the two tests below
    read the whole class rather than one third of it. Before that call this
    reader tested ``startswith("-")`` for ASCII alone and then returned
    ``-abs(value) if negative else abs(value)``: `parse_money` had already
    recovered the sign of a U+2212 or U+2013 amount, and the ``abs()`` threw it
    away — so `money_value` answered POSITIVE where the shared grammar answered
    negative (W3 §MGD MGD10 finding 1). Normalizing first is what makes the two
    agree; the equality is pinned token by token in
    `tests/test_structurer.py::test_the_sign_is_the_shared_grammars_answer`.

    The `abs()` stays, and after the normalization it is a no-op on every token
    `MONEY_RE` can produce: the sign has been stripped from `cleaned` by then,
    so `parse_money` returns a magnitude and this line only re-applies the
    accounting sign the flag holds. It is load-bearing for one shape the
    tokenizer cannot emit and a direct caller could — a welded debit marker
    (``100.00D``), which `parse_money` reads as negative and this reader still
    reports as a magnitude. That residual is named rather than fixed: changing
    it would move ASCII behaviour on a token no caller in the tree produces.
    """
    text = normalize_sign_glyphs(token.strip())
    negative = (
        text.startswith("(") or text.endswith(")")
        or text.startswith("-") or text.endswith("-")
    )
    cleaned = text.strip("()-").lstrip("$€£").strip()
    value = parse_money(cleaned)
    if value is None:
        return None
    return -abs(value) if negative else abs(value)


def money_tokens(text: str) -> list[MoneyToken]:
    tokens: list[MoneyToken] = []
    for match in MONEY_RE.finditer(text):
        value = money_value(match.group("token"))
        if value is not None:
            tokens.append(MoneyToken(match.group("token"), value, match.start(), match.end()))
    return tokens


def document_year(lines: list[str]) -> int | None:
    """The year this document is about: the majority year among its own dates.

    Never the current year. A statement is a historical record, and a
    structurer that dates a 2023 row to today produces a document that
    reconciles against nothing and misleads an underwriter.
    """
    years: dict[int, int] = {}
    for line in lines:
        for token in _YEAR_NEAR_DATE_RE.findall(line):
            year = int(token)
            if year < 100:
                year += 2000
            if 1990 <= year <= 2100:
                years[year] = years.get(year, 0) + 1
    if not years:
        return None
    return max(years.items(), key=lambda item: (item[1], item[0]))[0]
