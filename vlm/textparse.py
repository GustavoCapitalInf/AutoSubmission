"""Deterministic parsing of printed money, dates and descriptions. `decimal` throughout."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_CURRENCY = re.compile(r"^(?:[A-Z]{3}\s*)?[$€£¥]?\s*")
_TRAILING_CURRENCY = re.compile(r"\s*(?:[$€£¥]|\b[A-Z]{3})$")
_MONEY_CORE = re.compile(r"^\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?$|^\d+(?:\.\d{1,2})?$")
# Decimal comma (French and Canadian statements): 3 000,00 / 3.000,00 / 119,55; the thousands may be grouped by
# a space, a no-break or thin space, or a dot.
_MONEY_COMMA = re.compile(r"^\d{1,3}(?:[   .]\d{3})+,\d{2}$|^\d+,\d{2}$")
_GROUPING = re.compile(r"[   .]")
# Month names as statements print them, English and French, compared without accents.
_MONTH_NAMES = (("jan", "january", "janv", "janvier"), ("feb", "february", "fev", "fevr", "fevrier"),
                ("mar", "march", "mars"), ("apr", "april", "avr", "avril"), ("may", "mai"), ("jun", "june", "juin"),
                ("jul", "july", "juil", "juillet"), ("aug", "august", "aou", "aout"),
                ("sep", "sept", "september", "septembre"), ("oct", "october", "octobre"),
                ("nov", "november", "novembre"), ("dec", "december", "decembre"))
MONTHS = {name: month for month, names in enumerate(_MONTH_NAMES, 1) for name in names}
_MONTH_WORD = (r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|janv|f[ée]v|f[ée]vr|mars|avr|mai|juin|juil|"
               r"ao[uû]t?|d[ée]c)[^\W\d_]*")
_DATE_LIKE = re.compile(
    rf"^(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?|"
    rf"{_MONTH_WORD}\.?\s+\d{{1,2}}(?:,?\s+\d{{4}})?|"
    rf"\d{{1,2}}\s+{_MONTH_WORD}\.?(?:\s+\d{{4}})?)$",
    re.IGNORECASE,
)
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def parse_money(text: str | None) -> Decimal | None:
    if text is None:
        return None
    raw = text.strip().replace("−", "-").replace("–", "-")
    if not raw:
        return None
    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative, raw = True, raw[1:-1].strip()
    upper = raw.upper()
    if upper.endswith("CR"):
        raw = raw[:-2].strip()
    elif upper.endswith("DR"):
        negative, raw = True, raw[:-2].strip()
    raw = _TRAILING_CURRENCY.sub("", raw).strip()
    if raw.endswith("-"):
        negative, raw = True, raw[:-1].strip()
    if raw.startswith("-"):
        negative, raw = True, raw[1:].strip()
    raw = _CURRENCY.sub("", raw).strip()
    if _MONEY_CORE.match(raw):
        number = raw.replace(",", "")
    elif _MONEY_COMMA.match(raw):
        number = _GROUPING.sub("", raw).replace(",", ".")
    else:
        return None
    try:
        value = Decimal(number).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -value if negative else value


def month_number(name: str | None) -> int | None:
    """The month a printed month name means (English or French, abbreviated or full, with or without accents
    or a final period), or None."""
    import unicodedata

    plain = "".join(char for char in unicodedata.normalize("NFKD", str(name or "").strip().rstrip(".").lower())
                    if not unicodedata.combining(char))
    return MONTHS.get(plain)


def is_money_like(text: str | None) -> bool:
    return parse_money(text) is not None


def is_date_like(text: str | None) -> bool:
    return bool(text) and _DATE_LIKE.match(text.strip()) is not None


def _iso(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _year(value: str) -> int:
    number = int(value)
    return number + 2000 if number < 100 else number


def parse_date(text: str | None, *, year_hint: int | None = None, day_first: bool = False) -> str | None:
    if not text:
        return None
    raw = text.strip().rstrip(".").replace(".", " ")
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if match:
        return _iso(int(match[1]), int(match[2]), int(match[3]))
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", raw)
    if match:
        first, second = int(match[1]), int(match[2])
        year = _year(match[3]) if match[3] else year_hint
        if year is None:
            return None
        month, day = (second, first) if day_first else (first, second)
        result = _iso(year, month, day)
        if result is None and not day_first and first > 12:
            result = _iso(year, second, first)
        return result
    match = re.fullmatch(r"([^\W\d_]{3,9})\s+(\d{1,2}),?(?:\s+(\d{4}))?", raw)
    if match:
        month = month_number(match[1])
        year = int(match[3]) if match[3] else year_hint
        return _iso(year, month, int(match[2])) if month and year else None
    match = re.fullmatch(r"(\d{1,2})\s+([^\W\d_]{3,9})(?:,?\s+(\d{4}))?", raw)
    if match:
        month = month_number(match[2])
        year = int(match[3]) if match[3] else year_hint
        return _iso(year, month, int(match[1])) if month and year else None
    return None


def normalise_description(text: str | None) -> str:
    cleaned = _PUNCT.sub(" ", (text or "").lower())
    return _WS.sub(" ", cleaned).strip()


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    parsed = parse_money(str(value))
    if parsed is None:
        raise ValueError("not_money")
    return parsed


def money_str(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"
