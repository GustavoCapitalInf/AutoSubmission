"""Report-emission masking.

Any account number appearing in ANY emitted report is masked to last-4
(``****1234``).  Reports never carry full transaction ledgers or holder
addresses; transactions are referenced by date + amount + truncated
description (<= 40 chars).
"""
from __future__ import annotations

import re
from typing import Any

#: A bare digit run of 7+ (not part of a decimal number or ISO date) is
#: treated as a potential account identifier and masked.  Amounts are always
#: emitted with decimals and dates with dashes, so they never match.
_LONG_DIGITS = re.compile(r"(?<![\d.\-])\d{7,}(?![\d.\-])")
#: MoneyThumb's own partial masking ("xxxx1234") is normalized to ours.
_MT_MASKED = re.compile(r"\bx{2,}(\d{2,4})\b", re.IGNORECASE)


def mask_account(value: Any) -> str | None:
    """Explicit account-identifier masking: keep at most the last 4 chars."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() == "unknown":
        return "unknown"
    tail = text[-4:] if len(text) > 4 else text
    return f"****{tail}" if len(text) > 4 else tail


def mask_text(text: str) -> str:
    masked = _MT_MASKED.sub(lambda m: f"****{m.group(1)}", text)
    return _LONG_DIGITS.sub(lambda m: f"****{m.group(0)[-4:]}", masked)


def truncate_description(description: Any, limit: int = 40) -> str:
    text = str(description or "").strip()
    return text[:limit]


def transaction_ref(txn: dict[str, Any]) -> dict[str, Any]:
    """Reduce a ledger row to date + amount + truncated description."""
    return {
        "date": txn.get("date"),
        "amount": txn.get("amount"),
        "description": mask_text(truncate_description(txn.get("description"))),
    }


def mask_structure(node: Any) -> Any:
    """Recursively mask every string in an emission-ready structure."""
    if isinstance(node, dict):
        return {key: mask_structure(value) for key, value in node.items()}
    if isinstance(node, (list, tuple)):
        return [mask_structure(item) for item in node]
    if isinstance(node, str):
        return mask_text(node)
    return node
