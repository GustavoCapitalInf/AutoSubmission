"""Rule-based statement metadata from printed text lines (Stage A arm); merged with Stage B.

Review closures: META-1 (the money token is the first one AFTER the label on its line, not the last
one on the line); MAJOR-4 (the bank's printed totals and counts are extracted so the reader's summary
identity and count coverage can decide).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from decimal import Decimal

from vlm.textparse import parse_date, parse_money

BEGIN_RE = re.compile(r"\b(beginning balance|opening balance|previous balance|balance forward|starting balance|balance brought forward|previous statement balance)\b", re.I)
END_RE = re.compile(r"\b(ending balance|closing balance|new balance|balance at end|current balance|statement balance|ending ledger balance|closing ledger balance)\b", re.I)
TOTAL_CREDITS_RE = re.compile(r"\b(total deposits and (?:other )?credits|deposits and (?:other )?credits|total deposits|total credits|deposits/credits|total additions|credits total|deposits total)\b", re.I)
TOTAL_DEBITS_RE = re.compile(r"\b(total withdrawals and (?:other )?debits|withdrawals and (?:other )?debits|total withdrawals|total debits|checks and (?:other )?debits|withdrawals/debits|total subtractions|total payments|debits total|withdrawals total)\b", re.I)
COUNT_PAREN_RE = re.compile(r"\((\d{1,4})\)")
COUNT_WORD_RE = re.compile(r"\b(\d{1,4})\s+(deposits?|credits?|withdrawals?|debits?|checks?|items?|transactions?)\b", re.I)
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
    stated_total_credits: Decimal | None = None
    stated_total_debits: Decimal | None = None
    stated_credit_count: int | None = None
    stated_debit_count: int | None = None
    # Phase 3.1 source fields. Defaults preserve the existing proposal callers;
    # the visual pair supplies these before gating so summary identities use
    # exactly the same printed evidence as downstream analysis.
    account_name: str | None = None
    account_number: str | None = None
    days_in_period: int | None = None
    stated_service_charge: Decimal | None = None
    stated_interest_paid: Decimal | None = None
    stated_nsf_count: int | None = None
    bank_reported_average_balance: Decimal | None = None
    bank_reported_average_label: str | None = None
    stated_daily_balances: tuple[tuple[str, Decimal], ...] | None = None


EMPTY_META = AccountMeta(None, None, None, None, None, None, None, ())


def _money_after(lines: list[str], index: int, label_end: int) -> Decimal | None:
    """The first money token printed AFTER the label on its own line; else the first on the next line."""
    for text, start in ((lines[index], label_end), (lines[index + 1] if index + 1 < len(lines) else "", 0)):
        for match in MONEY_TOKEN.finditer(text):
            if match.start() < start:
                continue
            value = parse_money(match.group(0).strip())
            if value is not None:
                return value
    return None


def _count_after(line: str, label_end: int) -> int | None:
    """RR-6: the printed count belongs to the label's own field — the text between the label and its money
    token — never to a later column of a joined summary row and never to an earlier one."""
    tail = line[label_end:]
    money = MONEY_TOKEN.search(tail)
    field = tail[: money.start()] if money else tail
    match = COUNT_PAREN_RE.search(field)
    if match:
        return int(match.group(1))
    match = COUNT_WORD_RE.search(field)
    return int(match.group(1)) if match else None


def extract_meta(lines: list[str], *, year_hint: int | None = None) -> AccountMeta:
    beginning = ending = credits_total = debits_total = None
    credit_count = debit_count = None
    start = end = currency = last4 = None
    sources: list[str] = []
    for index, line in enumerate(lines):
        if beginning is None:
            match = BEGIN_RE.search(line)
            if match:
                beginning = _money_after(lines, index, match.end())
                if beginning is not None:
                    sources.append("beginning:rule")
        if ending is None:
            match = END_RE.search(line)
            if match:
                ending = _money_after(lines, index, match.end())
                if ending is not None:
                    sources.append("ending:rule")
        if credits_total is None:
            match = TOTAL_CREDITS_RE.search(line)
            if match:
                value = _money_after(lines, index, match.end())
                if value is not None:
                    credits_total = abs(value)
                    sources.append("total_credits:rule")
                count = _count_after(line, match.end())
                if count is not None and credit_count is None:
                    credit_count = count
                    sources.append("credit_count:rule")
        if debits_total is None:
            match = TOTAL_DEBITS_RE.search(line)
            if match:
                value = _money_after(lines, index, match.end())
                if value is not None:
                    debits_total = abs(value)
                    sources.append("total_debits:rule")
                count = _count_after(line, match.end())
                if count is not None and debit_count is None:
                    debit_count = count
                    sources.append("debit_count:rule")
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
    return AccountMeta(beginning, ending, start, end, currency, last4, None, tuple(sources),
                       credits_total, debits_total, credit_count, debit_count)


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
