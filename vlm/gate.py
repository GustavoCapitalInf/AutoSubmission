"""The deterministic gate. The model proposes; `analysis.reconcile.reconcile` (the reader's own
arithmetic) decides, with date, duplicate and direction checks on top. Never partial admission."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from vlm.assemble import CandidateRow
from vlm.metadata import AccountMeta
from vlm.textparse import normalise_description

GATE_VERSION = 1
REASONS = ("no_rows", "proposal_invalid", "missing_beginning_balance", "missing_ending_balance",
           "direction_unknown", "date_unparsed", "date_out_of_period", "date_not_monotonic", "duplicate_row",
           "sum_mismatch", "continuity_break", "currency_conflict")
PERIOD_GRACE_DAYS = 5


@dataclass(frozen=True)
class GateVerdict:
    admitted: bool
    reasons: tuple[str, ...]
    row_count: int
    admitted_rows: tuple[CandidateRow, ...]
    computed_ending: Decimal | None
    continuity_breaks: int
    chain_derived_directions: int
    checks: dict


def resolve_directions(rows: list[CandidateRow], beginning: Decimal | None) -> tuple[list[CandidateRow], int]:
    resolved: list[CandidateRow] = []
    previous = beginning
    flagged = 0
    for row in rows:
        current = row
        if row.direction == "unknown" and previous is not None and row.balance is not None:
            delta = row.balance - previous
            if abs(delta) == row.amount and row.amount > 0:
                current = replace(row, direction="credit" if delta > 0 else "debit", direction_source="chain")
                flagged += 1
        resolved.append(current)
        if current.balance is not None:
            previous = current.balance
    return resolved, flagged


def _signed(row: CandidateRow) -> float:
    return float(row.amount if row.direction == "credit" else -row.amount)


def statement_from(rows: list[CandidateRow], meta: AccountMeta) -> Statement:
    return Statement(
        bank=meta.bank, account_name=None, account_number=meta.account_last4,
        period_start=meta.period_start, period_end=meta.period_end,
        beginning_balance=float(meta.beginning_balance) if meta.beginning_balance is not None else None,
        ending_balance=float(meta.ending_balance) if meta.ending_balance is not None else None,
        currency=meta.currency or "USD",
        transactions=[Transaction(date=row.date or "", description=row.description, amount=_signed(row),
                                  direction=row.direction if row.direction != "unknown" else "debit",
                                  running_balance=float(row.balance) if row.balance is not None else None)
                      for row in rows],
    )


def gate(rows: list[CandidateRow], meta: AccountMeta, *, tolerance: Decimal = Decimal("0.01")) -> GateVerdict:
    reasons: list[str] = []
    checks: dict = {"gate_version": GATE_VERSION, "derived": []}
    if not rows:
        return GateVerdict(False, ("no_rows",), 0, (), None, 0, 0, checks)
    if any(row.amount <= 0 for row in rows):
        reasons.append("proposal_invalid")
    beginning, ending = meta.beginning_balance, meta.ending_balance
    first, last = rows[0], rows[-1]
    if beginning is None and first.balance is not None and first.direction in ("credit", "debit"):
        beginning = first.balance - first.amount if first.direction == "credit" else first.balance + first.amount
        checks["derived"].append("beginning_balance")
    if ending is None and last.balance is not None:
        ending = last.balance
        checks["derived"].append("ending_balance")
    if beginning is None:
        reasons.append("missing_beginning_balance")
    if ending is None:
        reasons.append("missing_ending_balance")
    resolved, flagged = resolve_directions(rows, beginning)
    if any(row.direction == "unknown" for row in resolved):
        reasons.append("direction_unknown")
    dates = [row.date for row in resolved]
    if any(value is None for value in dates):
        reasons.append("date_unparsed")
    parsed = [date.fromisoformat(value) for value in dates if value]
    if meta.period_start and meta.period_end and parsed:
        lower = date.fromisoformat(meta.period_start) - timedelta(days=PERIOD_GRACE_DAYS)
        upper = date.fromisoformat(meta.period_end) + timedelta(days=PERIOD_GRACE_DAYS)
        if any(value < lower or value > upper for value in parsed):
            reasons.append("date_out_of_period")
    if any(later < earlier for earlier, later in zip(parsed, parsed[1:])):
        reasons.append("date_not_monotonic")
    seen: set[tuple] = set()
    for row in resolved:
        if row.balance is None:
            continue
        key = (row.date, normalise_description(row.description), row.amount, row.direction, row.balance)
        if key in seen:
            reasons.append("duplicate_row")
            break
        seen.add(key)
    computed_ending: Decimal | None = None
    continuity_breaks = 0
    if beginning is not None and ending is not None and "direction_unknown" not in reasons and "proposal_invalid" not in reasons:
        meta_for_reader = replace(meta, beginning_balance=beginning, ending_balance=ending)
        result = reconcile(statement_from(resolved, meta_for_reader))
        if result.computed_ending is not None:
            computed_ending = Decimal(str(result.computed_ending)).quantize(Decimal("0.01"))
        continuity_breaks = int(result.continuity_breaks or 0)
        checks["reader_issues"] = list(result.issues)
        delta = abs(Decimal(str(result.sum_delta))) if result.sum_delta is not None else None
        if not result.ok or delta is None or delta > tolerance:
            reasons.append("sum_mismatch")
        if continuity_breaks:
            reasons.append("continuity_break")
    ordered = tuple(dict.fromkeys(reasons))
    admitted = not ordered
    return GateVerdict(admitted, ordered, len(resolved), tuple(resolved) if admitted else (), computed_ending,
                       continuity_breaks, flagged, checks)
