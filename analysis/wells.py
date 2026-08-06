from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .schema import Statement, Transaction

_PERIOD_RE = re.compile(r"Statement period activity summary.*?Beginning balance on (\d{1,2})/(\d{1,2})", re.IGNORECASE | re.DOTALL)
_SUMMARY_RE = re.compile(
    r"Beginning balance on (?P<bm>\d{1,2})/(?P<bd>\d{1,2})\s+(?P<begin>-?\$?[\d,]+\.\d{2})\s+"
    r"Deposits/Credits\s+(?P<credits>[\d,]+\.\d{2})\s+"
    r"Withdrawals/Debits\s+-\s+(?P<debits>[\d,]+\.\d{2}).*?"
    r"Ending balance on (?P<em>\d{1,2})/(?P<ed>\d{1,2})\s+(?P<ending>-?\$?[\d,]+\.\d{2})",
    re.IGNORECASE | re.DOTALL,
)
_AVG_RE = re.compile(r"Average ledger balance\s+\$?[\d,]+\.\d{2}\s+(-?\$?[\d,]+\.\d{2})", re.IGNORECASE)


def _infer_year(markdown: str) -> int | None:
    """First 4-digit year printed in the document, or None.

    No fabricated default: a statement whose text carries no year evidence
    cannot be dated, and the parser fails closed instead of guessing (R-1
    item 9 - the previous hardcoded ``2026`` fallback invented dates).
    """
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", markdown)]
    return years[0] if years else None


def _iso(mmdd: str, *, year: int) -> str:
    m, d = [int(p) for p in mmdd.split("/")]
    return date(year, m, d).isoformat()


def _amount(text: str) -> float | None:
    return parse_money(text.replace("$", ""))


def _is_credit(desc: str) -> bool:
    text = desc.upper()
    return any(key in text for key in (
        "DEPOSIT",
        "ALLSTATE",
        "TRANSFER FROM",
        "ONLINE TRANSFER FROM",
        "CREDIT",
    ))


def parse_wells_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    if "WF_NATIVE_TRANSACTIONS" not in markdown or "WELLS FARGO" not in markdown.upper():
        return None
    year = _infer_year(markdown)
    if year is None:
        return None
    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Wells Fargo"

    acct = re.search(r"Account number:\s*([0-9]+)", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)

    sm = _SUMMARY_RE.search(markdown)
    if sm:
        stmt.period_start = date(year, int(sm.group("bm")), int(sm.group("bd"))).isoformat()
        stmt.period_end = date(year, int(sm.group("em")), int(sm.group("ed"))).isoformat()
        if stmt.period_end < stmt.period_start:
            stmt.period_start = date(year - 1, int(sm.group("bm")), int(sm.group("bd"))).isoformat()
        stmt.beginning_balance = _amount(sm.group("begin"))
        stmt.ending_balance = _amount(sm.group("ending"))
        stmt.stated_total_credits = _amount(sm.group("credits"))
        stmt.stated_total_debits = _amount(sm.group("debits"))
    avg = _AVG_RE.search(markdown)
    if avg:
        stmt.stated_average_balance = _amount(avg.group(1))

    txns: list[Transaction] = []
    for line in markdown.splitlines():
        if not line.startswith("WF_TX|"):
            continue
        _, mmdd, desc, credit, debit, balance = (line.split("|", 5) + [""])[:6]
        desc = desc.strip()
        if not desc or desc.upper().startswith(("TOTALS", "ENDING BALANCE")):
            continue
        if credit:
            amt = abs(_amount(credit) or 0.0)
            signed = amt
        elif debit:
            amt = abs(_amount(debit) or 0.0)
            signed = -amt
        else:
            # Rare native alignment issue: one amount may land in the credit
            # column even for a withdrawal. Fall back to description semantics.
            continue
        txns.append(Transaction(
            date=_iso(mmdd, year=year),
            description=desc,
            amount=round(signed, 2),
            direction="credit" if signed > 0 else "debit",
            running_balance=_amount(balance) if balance else None,
        ))

    if not txns:
        return None
    stmt.transactions = txns
    return stmt
