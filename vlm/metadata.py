"""Rule-based statement metadata from printed text lines (Stage A arm); merged with Stage B."""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from decimal import Decimal

from vlm.textparse import parse_date, parse_money

BEGIN_RE = re.compile(r"\b(beginning balance|opening balance|previous balance|balance forward|starting balance|balance brought forward|previous statement balance)\b", re.I)
END_RE = re.compile(r"\b(ending balance|closing balance|new balance|balance at end|current balance|statement balance|ending ledger balance|closing ledger balance)\b", re.I)
MONEY_TOKEN = re.compile(r"\(?-?[$€£]?\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?-?|\(?-?[$€£]?\s?\d+\.\d{2}\)?-?")
DATE_TOKEN = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]{3,9}\.? \d{1,2},? \d{4}|\d{1,2} [A-Za-z]{3,9},? \d{4})"
PERIOD_RE = re.compile(rf"({DATE_TOKEN})\s*(?:to|-|–|—|through|thru)\s*({DATE_TOKEN})", re.I)
CURRENCY_RE = re.compile(r"\b(USD|CAD|EUR|GBP|AUD|NZD|MXN)\b")
LAST4_RE = re.compile(r"\b(?:account|acct)\.?\s*(?:number|no\.?|#)?\s*[:#]?\s*[\dXx*\-\s]*?(\d{4})\b", re.I)


@dataclass(frozen=True)
class AccountMeta:
    beginning_balance: Decimal | None
    ending_balance: Decimal | None
    period_start: str | None
    period_end: str | None
    currency: str | None
    account_last4: str | None
    bank: str | None
    sources: tuple[str, ...]


EMPTY_META = AccountMeta(None, None, None, None, None, None, None, ())


def _money_after(lines: list[str], index: int) -> Decimal | None:
    for candidate in (lines[index], lines[index + 1] if index + 1 < len(lines) else ""):
        tokens = MONEY_TOKEN.findall(candidate)
        for token in reversed(tokens):
            value = parse_money(token.strip())
            if value is not None:
                return value
    return None


def extract_meta(lines: list[str], *, year_hint: int | None = None) -> AccountMeta:
    beginning = ending = None
    start = end = currency = last4 = None
    sources: list[str] = []
    for index, line in enumerate(lines):
        if beginning is None and BEGIN_RE.search(line):
            beginning = _money_after(lines, index)
            if beginning is not None:
                sources.append("beginning:rule")
        if ending is None and END_RE.search(line):
            ending = _money_after(lines, index)
            if ending is not None:
                sources.append("ending:rule")
        if start is None:
            match = PERIOD_RE.search(line)
            if match:
                first, second = parse_date(match[1], year_hint=year_hint), parse_date(match[2], year_hint=year_hint)
                if first and second:
                    start, end = first, second
                    sources.append("period:rule")
        if currency is None:
            match = CURRENCY_RE.search(line)
            if match:
                currency = match[1].upper()
                sources.append("currency:rule")
            elif "€" in line:
                currency = "EUR"
                sources.append("currency:symbol")
            elif "£" in line:
                currency = "GBP"
                sources.append("currency:symbol")
        if last4 is None:
            match = LAST4_RE.search(line)
            if match:
                last4 = match[1]
                sources.append("last4:rule")
    return AccountMeta(beginning, ending, start, end, currency, last4, None, tuple(sources))


def merge_meta(first: AccountMeta, second: AccountMeta) -> AccountMeta:
    values = {}
    for field in fields(AccountMeta):
        if field.name == "sources":
            continue
        a, b = getattr(first, field.name), getattr(second, field.name)
        values[field.name] = a if a is not None else b
    return AccountMeta(sources=tuple(dict.fromkeys(first.sources + second.sources)), **values)


def year_from_meta(meta: AccountMeta) -> int | None:
    for value in (meta.period_end, meta.period_start):
        if value:
            return int(value[:4])
    return None
