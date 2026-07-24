"""Stage 3b — MCA / lender detection. Two complementary, fully deterministic
signals, each returning the evidence transactions so a human can audit:

  1. Known-entity match: transaction descriptions vs a maintained funder/lender
     dictionary (fast, precise, explainable).
  2. Recurring-debit pattern: fixed-amount debits repeating on a regular (daily or
     weekly) cadence — the MCA remittance signature — even when the name is a
     generic ACH/merchant descriptor.

The dictionary is intentionally easy to extend; add aliases as you see new funders.
"""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from statistics import mean, pstdev
from .schema import Statement, Transaction
from .metrics import _parse_date

# Known merchant-cash-advance funders and common alt-lenders. Keys are canonical
# names; values are lowercase alias substrings to match against descriptions.
KNOWN_FUNDERS: dict[str, list[str]] = {
    "Kapitus": ["kapitus", "colonial funding"],
    "OnDeck": ["ondeck", "on deck capital"],
    "Forward Financing": ["forward financing"],
    "Fora Financial": ["fora financial"],
    "Rapid Finance": ["rapid finance", "rapidadvance"],
    "Credibly": ["credibly"],
    "BlueVine": ["bluevine"],
    "Fundbox": ["fundbox"],
    "Square Capital / Loans": ["square capital", "square loans", "sq *loans"],
    "PayPal Working Capital": ["paypal working capital", "paypal wc"],
    "Reliant Funding": ["reliant funding"],
    "Everest Business Funding": ["everest business"],
    "Mantis Funding": ["mantis funding"],
    "CFG Merchant Solutions": ["cfg merchant"],
    "Libertas Funding": ["libertas"],
    "Fundomate": ["fundomate"],
    "National Funding": ["national funding"],
    "Newtek": ["newtek"],
    "Headway Capital": ["headway capital"],
    "Lendio": ["lendio"],
    "Enova / Headway": ["enova"],
}


@dataclass
class FunderMatch:
    funder: str
    matched_alias: str
    transactions: list[Transaction] = field(default_factory=list)
    total_debited: float = 0.0


@dataclass
class RecurringDebit:
    description_key: str
    amount: float
    count: int
    cadence: str            # "daily", "weekly", or "irregular"
    avg_gap_days: float | None
    transactions: list[Transaction] = field(default_factory=list)


@dataclass
class DetectionResult:
    known_funders: list[FunderMatch] = field(default_factory=list)
    recurring_debits: list[RecurringDebit] = field(default_factory=list)


def find_known_funders(stmt: Statement) -> list[FunderMatch]:
    matches: dict[str, FunderMatch] = {}
    for t in stmt.transactions:
        desc = t.description.lower()
        for funder, aliases in KNOWN_FUNDERS.items():
            hit = next((a for a in aliases if a in desc), None)
            if hit:
                m = matches.get(funder) or FunderMatch(funder=funder, matched_alias=hit)
                m.transactions.append(t)
                if t.amount < 0:
                    m.total_debited += -t.amount
                matches[funder] = m
    for m in matches.values():
        m.total_debited = round(m.total_debited, 2)
    return sorted(matches.values(), key=lambda m: len(m.transactions), reverse=True)


# Strip trailing IDs/dates so "ACH Debit Kapitus 0102" and "...0103" group together.
_NORMALIZE_RE = re.compile(r"[0-9]{2,}|#\w+|\bx+\d+\b", re.IGNORECASE)


def _desc_key(desc: str) -> str:
    return re.sub(r"\s+", " ", _NORMALIZE_RE.sub("", desc.lower())).strip()


def _classify_cadence(dates: list[date]) -> tuple[str, float | None]:
    ds = sorted(dates)
    gaps = [(b - a).days for a, b in zip(ds, ds[1:]) if (b - a).days > 0]
    if not gaps:
        return "irregular", None
    g = mean(gaps)
    spread = pstdev(gaps) if len(gaps) > 1 else 0.0
    if g <= 1.6 and spread <= 1.5:
        return "daily", round(g, 1)          # business-day daily (~1 with weekend gaps)
    if 5 <= g <= 9 and spread <= 2.5:
        return "weekly", round(g, 1)
    return "irregular", round(g, 1)


def find_recurring_debits(stmt: Statement, *, min_count: int = 3) -> list[RecurringDebit]:
    """Group debits by (normalized description, exact amount); flag groups that
    repeat >= min_count times as candidate advance remittances."""
    groups: dict[tuple[str, float], list[Transaction]] = defaultdict(list)
    for t in stmt.transactions:
        if t.amount < 0:
            groups[(_desc_key(t.description), round(t.amount, 2))].append(t)

    out: list[RecurringDebit] = []
    for (key, amount), txns in groups.items():
        if len(txns) < min_count:
            continue
        dates = [d for t in txns if (d := _parse_date(t.date)) is not None]
        cadence, avg_gap = _classify_cadence(dates) if len(dates) >= 2 else ("irregular", None)
        out.append(RecurringDebit(
            description_key=key or "(blank)", amount=abs(amount), count=len(txns),
            cadence=cadence, avg_gap_days=avg_gap, transactions=txns,
        ))
    # Most suspicious first: regular cadence and high frequency.
    out.sort(key=lambda r: (r.cadence in ("daily", "weekly"), r.count), reverse=True)
    return out


def detect(stmt: Statement, *, min_count: int = 3) -> DetectionResult:
    return DetectionResult(
        known_funders=find_known_funders(stmt),
        recurring_debits=find_recurring_debits(stmt, min_count=min_count),
    )
