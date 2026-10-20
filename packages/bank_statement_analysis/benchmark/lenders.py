"""Lender-name canonicalization for MCA comparisons.

Our FunderMatch registry uses internal canonical labels (ONDECK, CFGMS,
EBF HOLDINGS, ...) while MoneyThumb uses display names (OnDeck Capital,
CFG Merchant Solutions, ...).  Both are normalized here to a shared canonical
key so per-lender rows line up.  Ledger-search tokens let the harness find
direct source evidence for a lender either side detected.
"""
from __future__ import annotations

import re
from typing import Any, Iterable


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


def flagged_lender_groups(detections: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Canonical key -> {"group", "count", "total"} over ``detection.flagged_positions``.

    Replaces the old NON_MCA_SCOPE set (owner ruling 2026-09-24): a
    counterparty our payload carries as a flagged position is outside lender
    math by ruling, so a MoneyThumb lender that matches one is reported as
    flagged here, never as a miss.
    """
    flagged: dict[str, dict[str, Any]] = {}
    for detection in detections:
        for position in detection.get("flagged_positions") or []:
            canonical = canonical_lender(position.get("payee"))
            entry = flagged.setdefault(
                canonical, {"group": position.get("group"), "count": 0, "total": 0.0}
            )
            entry["count"] += int(position.get("count") or 0)
            entry["total"] = round(
                entry["total"] + abs(float(position.get("total_debited") or 0.0)), 2
            )
    return flagged


def ledger_tokens(canonical: str) -> tuple[str, ...]:
    return LEDGER_TOKENS.get(canonical, (canonical.lower(),))
