from __future__ import annotations

import re

from .schema import Statement
from .td_can import _parse_money


def repair_bofa_summary(markdown: str, stmt: Statement) -> Statement:
    """Normalize Bank of America summary fields.

    BofA prints withdrawals/debits, checks, and service fees as separate account
    summary lines. For underwriting outflow totals and reconciliation, those must
    be treated as one debit total.
    """
    text = markdown
    if "BANK OF AMERICA" not in text.upper() or "ACCOUNT SUMMARY" not in text.upper():
        return stmt

    def money_after(label: str) -> float | None:
        m = re.search(label + r"\s+(-?\$?[\d,]+\.\d{2})", text, re.IGNORECASE)
        return abs(_parse_money(m.group(1))) if m else None

    def int_after(label: str) -> int | None:
        m = re.search(label + r"\s+(\d+)", text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    updates = {}
    beginning = money_after(r"Beginning balance on [^\n$]+")
    ending = money_after(r"Ending balance on [^\n$]+")
    credits = money_after(r"Deposits and other credits")
    withdrawals = money_after(r"Withdrawals and other debits")
    checks = money_after(r"Checks")
    service = money_after(r"Service fees")
    avg = money_after(r"Average ledger balance:")
    credit_count = int_after(r"# of deposits/credits:")
    debit_count = int_after(r"# of withdrawals/debits:")
    check_count = int_after(r"Total # of checks")

    if beginning is not None:
        updates["beginning_balance"] = beginning
    if ending is not None:
        updates["ending_balance"] = ending
    if credits is not None:
        updates["stated_total_credits"] = credits
    if withdrawals is not None:
        updates["stated_total_debits"] = round(withdrawals + (checks or 0.0) + (service or 0.0), 2)
    if credit_count is not None:
        updates["stated_credit_count"] = credit_count
    if debit_count is not None:
        updates["stated_debit_count"] = debit_count + (check_count or 0)
    if avg is not None:
        updates["stated_average_balance"] = avg
    if service is not None:
        updates["stated_service_charge"] = None

    repaired = stmt.model_copy(update=updates) if updates else stmt
    if any(t.running_balance is not None for t in repaired.transactions):
        repaired = repaired.model_copy(update={
            "transactions": [t.model_copy(update={"running_balance": None}) for t in repaired.transactions]
        })
    return repaired
