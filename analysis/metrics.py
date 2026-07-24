"""Stage 3a — deterministic analytics. Every number a funder cares about is
computed here in plain Python from the reconciled ledger, never by the LLM.

Daily average balance (ADB) is the headline figure: the mean of each calendar
day's closing balance across the statement period, carrying the last known
balance forward across days with no activity.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from .schema import Statement

# NSF / overdraft / returned-item fee signatures seen in real statements.
_NSF_RE = re.compile(
    r"\b(nsf|non[- ]?sufficient|insufficient funds|overdraft|returned item|"
    r"return(ed)? (deposit|check|item)|uncollected funds)\b",
    re.IGNORECASE,
)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%d %b %Y", "%b %d, %Y"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class Metrics:
    days_in_period: int | None = None
    # Bank-printed average balance ("Average Ledger" etc.) when the statement shows
    # one — authoritative and needs no computation. `average_daily_balance` below is
    # our own figure computed from dated running balances (used when there's no
    # printed one, or to cross-check it).
    stated_average_balance: float | None = None
    average_daily_balance: float | None = None
    min_balance: float | None = None
    max_balance: float | None = None
    negative_days: int = 0
    total_deposits: float = 0.0
    total_withdrawals: float = 0.0
    num_deposits: int = 0
    num_withdrawals: int = 0
    nsf_count: int = 0                     # from line items (a lower bound if detail is incomplete)
    stated_nsf_count: int | None = None    # bank-printed count this period, when available
    notes: list[str] = field(default_factory=list)


def daily_closing_balances(stmt: Statement) -> dict[date, float]:
    """Map each calendar day in the period to its closing balance, carrying the
    last known running balance forward across no-activity days. Requires dated
    transactions with running balances; returns {} if those aren't available."""
    start = _parse_date(stmt.period_start)
    end = _parse_date(stmt.period_end)
    dated = [(d, t) for t in stmt.transactions if (d := _parse_date(t.date)) is not None]
    if not dated or any(t.running_balance is None for _, t in dated):
        return {}
    if start is None:
        start = min(d for d, _ in dated)
    if end is None:
        end = max(d for d, _ in dated)

    # Last running balance recorded on each day (transactions are in order).
    eod: dict[date, float] = {}
    for d, t in dated:
        if start <= d <= end:
            eod[d] = t.running_balance

    balances: dict[date, float] = {}
    # Balance entering the period: the opening balance, else the first day's close.
    carry = stmt.beginning_balance
    if carry is None:
        carry = dated[0][1].running_balance
    day = start
    while day <= end:
        if day in eod:
            carry = eod[day]
        balances[day] = carry
        day += timedelta(days=1)
    return balances


def compute_metrics(stmt: Statement) -> Metrics:
    m = Metrics()
    m.stated_average_balance = stmt.stated_average_balance
    m.stated_nsf_count = stmt.stated_nsf_count
    for t in stmt.transactions:
        if t.amount >= 0:
            m.total_deposits += t.amount
            m.num_deposits += 1
        else:
            m.total_withdrawals += -t.amount
            m.num_withdrawals += 1
        if _NSF_RE.search(t.description):
            m.nsf_count += 1
    m.total_deposits = round(m.total_deposits, 2)
    m.total_withdrawals = round(m.total_withdrawals, 2)

    balances = daily_closing_balances(stmt)
    if balances:
        vals = list(balances.values())
        m.days_in_period = len(vals)
        m.average_daily_balance = round(sum(vals) / len(vals), 2)
        m.min_balance = round(min(vals), 2)
        m.max_balance = round(max(vals), 2)
        m.negative_days = sum(1 for v in vals if v < 0)
    elif m.stated_average_balance is None:
        m.notes.append(
            "no average balance available: statement prints none and lacks dated "
            "running balances to compute one"
        )
    else:
        m.days_in_period = stmt.days_in_period
        m.notes.append("using the bank's printed average balance (no running balances to compute our own)")
    return m
