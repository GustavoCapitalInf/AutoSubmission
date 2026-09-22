"""Deterministic parsing of printed money, dates and descriptions. `decimal` throughout."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_CURRENCY = re.compile(r"^(?:[A-Z]{3}\s*)?[$€£¥]?\s*")
_MONEY_CORE = re.compile(r"^\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?$|^\d+(?:\.\d{1,2})?$")
_DATE_LIKE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?|"
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?:\s+\d{4})?)$",
    re.IGNORECASE,
)
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
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
    if raw.endswith("-"):
        negative, raw = True, raw[:-1].strip()
    if raw.startswith("-"):
        negative, raw = True, raw[1:].strip()
    raw = _CURRENCY.sub("", raw).strip()
    if not _MONEY_CORE.match(raw):
        return None
    try:
        value = Decimal(raw.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -value if negative else value


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
    match = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{1,2}),?(?:\s+(\d{4}))?", raw)
    if match:
        month = _MONTHS.get(match[1][:3].lower())
        year = int(match[3]) if match[3] else year_hint
        return _iso(year, month, int(match[2])) if month and year else None
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})(?:,?\s+(\d{4}))?", raw)
    if match:
        month = _MONTHS.get(match[2][:3].lower())
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
