from __future__ import annotations

from .schema import Statement


def repair_first_community_posted_activity(stmt: Statement) -> Statement:
    """Drop First Community balance-neutral failed debit attempts from cashflow.

    This statement family lists some rejected EFT attempts in account activity
    with a debit amount, but the printed running balance does not move. Those are
    useful review evidence, but they are not posted withdrawals for balance math.
    """
    bank = (stmt.bank or "").upper()
    if "FIRST COMMUNITY" not in bank:
        return stmt
    if not stmt.transactions:
        return stmt

    prev = stmt.beginning_balance
    kept = []
    removed_debits = 0.0
    for t in stmt.transactions:
        balance = t.running_balance
        if (
            prev is not None
            and balance is not None
            and round(balance - prev, 2) == 0.0
            and t.amount < 0
            and t.description.upper().startswith("EFT -")
        ):
            removed_debits = round(removed_debits + abs(t.amount), 2)
            continue
        kept.append(t)
        if balance is not None:
            prev = balance

    if not removed_debits:
        return stmt

    updates = {"transactions": kept}
    if stmt.stated_total_debits is not None:
        updates["stated_total_debits"] = round(stmt.stated_total_debits - removed_debits, 2)
    return stmt.model_copy(update=updates)
