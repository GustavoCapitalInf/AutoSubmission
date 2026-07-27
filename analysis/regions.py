from __future__ import annotations

import re
from html import unescape

from .schema import Statement
from .td_can import _parse_money


def _money_after(label: str, text: str) -> float | None:
    m = re.search(label + r"\s+\$?([\d,]+\.\d{2})(?:\s*(-))?", text, re.IGNORECASE)
    if not m:
        return None
    value = abs(_parse_money(m.group(1)) or 0.0)
    return -value if m.group(2) else value


def repair_regions_summary(markdown: str, stmt: Statement) -> Statement:
    """Normalize Regions summary fields, including trailing minus signs."""
    if "REGIONS" not in markdown.upper() or "SUMMARY" not in markdown.upper():
        return stmt

    text = unescape(re.sub(r"<[^>]+>", " ", markdown))
    beginning = _money_after(r"Beginning Balance", text)
    deposits = _money_after(r"Total Deposits & Credits", text) or _money_after(r"Deposits & Credits", text)
    withdrawals = _money_after(r"Total Withdrawals", text) or _money_after(r"Withdrawals", text)
    fees = _money_after(r"Total Fees", text) or _money_after(r"Fees", text)
    returned = _money_after(r"Total Returned Checks", text) or _money_after(r"Returned Checks", text)
    checks = _money_after(r"Total Checks", text) or _money_after(r"(?<!Returned )Checks", text)
    ending = _money_after(r"Ending Balance", text)
    avg = _money_after(r"Average Monthly Statement Balance", text)

    updates = {}
    if beginning is not None:
        updates["beginning_balance"] = beginning
    if ending is not None:
        updates["ending_balance"] = ending
    if deposits is not None:
        total_credits = abs(deposits) + abs(returned or 0.0)
        updates["stated_total_credits"] = round(total_credits, 2)
    if withdrawals is not None:
        total_debits = abs(withdrawals) + abs(fees or 0.0) + abs(checks or 0.0)
        updates["stated_total_debits"] = round(total_debits, 2)
        updates["stated_service_charge"] = None
    if avg is not None:
        updates["stated_average_balance"] = abs(avg)
    return stmt.model_copy(update=updates) if updates else stmt
