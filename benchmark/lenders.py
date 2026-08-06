"""Lender-name canonicalization for MCA comparisons.

Our FunderMatch registry uses internal canonical labels (ONDECK, CFGMS,
EBF HOLDINGS, ...) while MoneyThumb uses display names (OnDeck Capital,
CFG Merchant Solutions, ...).  Both are normalized here to a shared canonical
key so per-lender rows line up.  Ledger-search tokens let the harness find
direct source evidence for a lender either side detected.
"""
from __future__ import annotations

import re


def _norm(name: str) -> str:
    text = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    return re.sub(r"\s+", " ", text).strip()


#: normalized alias -> canonical key.
_ALIASES: dict[str, str] = {
    "ONDECK": "ONDECK CAPITAL",
    "ONDECK CAPITAL": "ONDECK CAPITAL",
    "ON DECK CAPITAL": "ONDECK CAPITAL",
    "CFGMS": "CFG MERCHANT SOLUTIONS",
    "CFG MERCHANT SOLUTIONS": "CFG MERCHANT SOLUTIONS",
    "EBF HOLDINGS": "EVEREST BUSINESS FUNDING",
    "EVEREST BUSINESS FUNDING": "EVEREST BUSINESS FUNDING",
    "EMINENT FUNDING": "EMINENT FUNDING",
    # MoneyThumb's display label for the ledger's "AFC FUNDING CORP" rows.
    "ADVANCED FINANCIAL COMPANY": "ADVANCED FINANCIAL COMPANY",
    "AFC FUNDING CORP": "ADVANCED FINANCIAL COMPANY",
    "INTUIT FINANCING": "INTUIT FINANCING",
    "AFFIRM": "AFFIRM",
    "SNAP FINANCE": "SNAP FINANCE",
    "U S SMALL BUSINESS ADMINISTRATION": "US SMALL BUSINESS ADMINISTRATION",
    "US SMALL BUSINESS ADMINISTRATION": "US SMALL BUSINESS ADMINISTRATION",
}

#: canonical key -> ledger-description search tokens (lowercase).
LEDGER_TOKENS: dict[str, tuple[str, ...]] = {
    "ONDECK CAPITAL": ("ondeck",),
    "CFG MERCHANT SOLUTIONS": ("cfg merchant", "cfgms", "cfg merch"),
    "EVEREST BUSINESS FUNDING": ("everest", "ebf"),
    "EMINENT FUNDING": ("eminent",),
    "ADVANCED FINANCIAL COMPANY": ("afc funding", "advanced financial"),
    "INTUIT FINANCING": ("intuit financing",),
    "AFFIRM": ("affirm",),
    "SNAP FINANCE": ("snap finance", "snap fin"),
    "US SMALL BUSINESS ADMINISTRATION": ("sba", "small business administration"),
}

#: Canonical lenders that are financing counterparties but not MCA funders -
#: the documented scope difference between our general lender detection and
#: MT's MCA-specific list (FIELD_MAPPING section 4).
NON_MCA_SCOPE: frozenset[str] = frozenset(
    {"AFFIRM", "SNAP FINANCE", "US SMALL BUSINESS ADMINISTRATION"}
)


def canonical_lender(name: str | None) -> str:
    if not name:
        return "UNKNOWN"
    normalized = _norm(name)
    if normalized in _ALIASES:
        return _ALIASES[normalized]
    for alias, canonical in _ALIASES.items():
        if normalized.startswith(alias) or alias.startswith(normalized):
            return canonical
    return normalized


def ledger_tokens(canonical: str) -> tuple[str, ...]:
    return LEDGER_TOKENS.get(canonical, (canonical.lower(),))
