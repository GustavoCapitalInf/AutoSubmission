from __future__ import annotations

import re

from .date_tokens import date_refusal, iso_from_month_day, iso_or_none
from .money import money_refusal, parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace

_DATE_RE = re.compile(r"(?<![\d/])(\d{2}/\d{2})(?!/\d{2})")
_MONEY_RE = re.compile(r"\d[\d,]*\.\d{2}-?")


def _amount(value: str) -> float:
    """The printed cell as a number, refusing rather than inventing one.

    The refusal names this reader and the token's SHAPE, never the cell
    (`money._refusal`, W3 §MONEYPRIV; this site is §PRIVACY3's). Control flow is
    unchanged: the same tokens raise, with the same class, at the same line.
    """
    parsed = parse_money(value)
    if parsed is None:
        raise money_refusal("farmers_merchants._amount", value)
    return parsed


def _statement_year(markdown: str) -> int:
    match = re.search(r"Statement Dates\s+\d{2}/\d{2}/(\d{2})\s+thru", markdown, re.IGNORECASE)
    return 2000 + int(match.group(1)) if match else 2026


def _parse_summary(markdown: str, stmt: Statement) -> None:
    text = compact_whitespace(markdown)
    m = re.search(
        r"Account Number\s+(?P<acct>\d+)\s+Statement Dates\s+"
        r"(?P<start>\d{2}/\d{2}/\d{2})\s+thru\s+(?P<end>\d{2}/\d{2}/\d{2})\s+"
        r"Previous Balance\s+(?P<begin>\d[\d,]*\.\d{2}-?)\s+"
        r"Days in the statement period\s+(?P<days>\d+)\s+"
        r"(?P<credit_count>\d+)\s+Deposits/Credits\s+(?P<credits>\d[\d,]*\.\d{2})\s+"
        r"Average Ledger\s+(?P<avg>\d[\d,]*)\s+"
        r"(?P<debit_count>\d+)\s+Checks/Debits\s+(?P<debits>\d[\d,]*\.\d{2})\s+"
        r"Average Collected\s+\d[\d,]*\s+"
        r"Service Charge\s+(?P<service>\d[\d,]*\.\d{2})\s+"
        r"Interest Paid\s+(?P<interest>(?:\d+)?\.\d{2})\s+"
        r"Ending Balance\s+(?P<ending>\d[\d,]*\.\d{2})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return
    year = 2000 + int(m.group("end").split("/")[-1])
    start_m, start_d, _ = [int(part) for part in m.group("start").split("/")]
    end_m, end_d, _ = [int(part) for part in m.group("end").split("/")]
    stmt.account_number = m.group("acct")
    # RAISE-PRIVACY-4, the MAJOR-2 class W3 §H14 carried out of #HYGIENE8:
    # `(?P<start>\d{2}/\d{2}/\d{2})` proves three digit pairs and nothing more,
    # so a period cell printed `13/40/31` reaches `date()`, whose ValueError
    # echoes the printed month (and the printed day and year on a day-range
    # failure) — measured at the base tree as `month must be in 1..12, not 13`.
    # Funnelled through `iso_or_none` and refused from OUTSIDE the funnel; the
    # class stays `ValueError`, so this document refuses exactly as it refused
    # before, and the two cells are read in the order they were read before, so
    # the start cell still refuses first.
    period_start = iso_or_none(year, start_m, start_d)
    if period_start is None:
        raise date_refusal("farmers_merchants._parse_summary", m.group("start"))
    stmt.period_start = period_start
    period_end = iso_or_none(year, end_m, end_d)
    if period_end is None:
        raise date_refusal("farmers_merchants._parse_summary", m.group("end"))
    stmt.period_end = period_end
    stmt.beginning_balance = _amount(m.group("begin"))
    stmt.ending_balance = _amount(m.group("ending"))
    stmt.days_in_period = int(m.group("days"))
    stmt.stated_credit_count = int(m.group("credit_count"))
    stmt.stated_debit_count = int(m.group("debit_count"))
    stmt.stated_total_credits = _amount(m.group("credits"))
    stmt.stated_total_debits = _amount(m.group("debits"))
    printed_average = _amount(m.group("avg"))
    stmt.bank_reported_average_balance = printed_average
    stmt.bank_reported_average_label = (
        "Average Ledger" if printed_average is not None else None
    )
    stmt.stated_service_charge = _amount(m.group("service"))
    stmt.stated_interest_paid = _amount(m.group("interest"))


def _parse_rows(block: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    starts = list(_DATE_RE.finditer(block))
    for idx, match in enumerate(starts):
        row = block[match.start():starts[idx + 1].start() if idx + 1 < len(starts) else len(block)]
        money = _MONEY_RE.findall(row)
        if not money:
            continue
        raw_amount = money[-1]
        desc = row[len(match.group(0)):row.rfind(raw_amount)]
        desc = re.sub(r"\b\d{2}/\d{2}/\d{2}\b", "", desc)
        desc = compact_whitespace(desc)
        if not desc or desc.upper().startswith(("ID #", "TRACE #", "BALANCE FEE IN SERVICE CHARGE")):
            continue
        amount = abs(_amount(raw_amount)) * sign
        txns.append(Transaction(
            date=iso_from_month_day(match.group(0), year=year),
            description=desc,
            amount=round(amount, 2),
            direction="credit" if amount > 0 else "debit",
            running_balance=None,
        ))
    return txns


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    # The second branch used to require the account holder's trading name,
    # which R-1's zero-customer-names rule forbids and its file-scoped grep
    # missed (the literal is now in that guard's scan list, so it cannot come
    # back - which is also why it is described here rather than quoted). This
    # statement carries no issuer identification whatsoever - no bank name, no
    # domain, no FDIC footer - so the branch is now the layout's own product
    # and section headings.
    required("bank_name", lambda t: ("FARMERS" in t and "MERCHANTS BANK" in t)
        or ("BUSINESS/COMMERCIAL" in t and "CHECKS/DEBITS" in t)),
    required("credits_section", lambda t: "DEPOSITS AND CREDITS" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_farmers_merchants_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if not detect(markdown).claims:
        return None

    stmt = Statement(bank="Farmers & Merchants Bank", currency="USD",
                     currency_source="institution_default")
    # The holder line is the one carrying a "doing business as" clause — a
    # generic legal-entity marker. It used to name this statement's account
    # holder outright (a second R-1 residual in this file, found by the
    # layer-wide literal scan R-4b added). Same capture on the corpus document.
    name = re.search(r"\n([A-Z0-9 &.'-]+ DBA .*?)\n", markdown)
    if name:
        stmt.account_name = compact_whitespace(name.group(1))
    _parse_summary(markdown, stmt)
    year = _statement_year(markdown)

    text = compact_whitespace(markdown)
    deposits = checks = ""
    dm = re.search(r"DEPOSITS AND CREDITS\s+Date\s+Description\s+Amount\s+(.*?)\s+CHECKS AND CHARGES", text, re.IGNORECASE)
    if dm:
        deposits = dm.group(1)
    cm = re.search(r"CHECKS AND CHARGES\s+Date\s+description\s+Amount\s+(.*)", text, re.IGNORECASE)
    if cm:
        checks = cm.group(1)

    txns = _parse_rows(deposits, year=year, sign=1) + _parse_rows(checks, year=year, sign=-1)
    if not txns and stmt.account_number is None:
        return None
    stmt.transactions = txns
    return stmt
