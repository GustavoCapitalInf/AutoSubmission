"""The deterministic gate. The model proposes; `analysis.reconcile.reconcile` (the reader's own
arithmetic) decides, with anchor, date, duplicate and direction checks on top. Never partial admission.

Review closures (CEILING-HARNESS-REVIEW-X):
* MAJOR-1  at most ONE anchor may be derived from the rows; with neither balance printed the gate refuses
           (`anchors_underdetermined`), because a proposal would then be checked only against itself.
* GATE-3   chain-derived directions are accepted only when BOTH anchors are printed (the sum check is then
           independent of the chain); otherwise `chain_direction_unanchored`.
* MAJOR-2  a repeated (date, description, amount, direction) is a `duplicate_row` unless printed balances
           distinguish the two rows, or the bank's printed per-direction count vouches for the pair.
* MAJOR-4  the bank's printed totals and counts reach `reconcile`; a failing summary identity is
           `summary_mismatch`, a failing count is `count_mismatch`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from vlm.assemble import CandidateRow
from vlm.metadata import AccountMeta
from vlm.textparse import normalise_description

GATE_VERSION = 4
REASONS = ("no_rows", "proposal_invalid", "anchors_underdetermined", "anchor_derived", "missing_beginning_balance",
           "missing_ending_balance", "direction_unknown", "chain_direction_unanchored", "date_unparsed",
           "duplicate_row", "sum_mismatch", "continuity_break",
           "summary_mismatch", "count_mismatch", "coverage_mismatch", "currency_conflict", "anchor_disagreement")
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
    anchored: str = "none"   # "both" | "one" | "none" — how many anchors were PRINTED


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


def _f(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def statement_from(rows: list[CandidateRow], meta: AccountMeta) -> Statement:
    return Statement(
        bank=meta.bank, account_name=None, account_number=meta.account_last4,
        period_start=meta.period_start, period_end=meta.period_end,
        beginning_balance=_f(meta.beginning_balance), ending_balance=_f(meta.ending_balance),
        currency=meta.currency or "USD",
        stated_total_credits=_f(meta.stated_total_credits), stated_total_debits=_f(meta.stated_total_debits),
        stated_credit_count=meta.stated_credit_count, stated_debit_count=meta.stated_debit_count,
        transactions=[Transaction(date=row.date or "", description=row.description, amount=_signed(row),
                                  direction=row.direction if row.direction != "unknown" else "debit",
                                  running_balance=_f(row.balance))
                      for row in rows],
    )


def orient(rows: list[CandidateRow]) -> tuple[list[CandidateRow], bool]:
    """Statements that list newest first are reversed into chronological order (a deterministic rule keyed
    on the printed dates: more descending than ascending steps). Returns (rows, reversed)."""
    dates = [row.date for row in rows if row.date]
    down = sum(1 for a, b in zip(dates, dates[1:]) if b < a)
    up = sum(1 for a, b in zip(dates, dates[1:]) if b > a)
    if down > up:
        return list(reversed(rows)), True
    return list(rows), False


def collapse_daily_balances(rows: list[CandidateRow]) -> tuple[list[CandidateRow], int]:
    """Banks that print one end-of-day balance repeat it on every row of that day. Keep it on the LAST
    row of each same-date run of identical balances (the reader's continuity check accumulates the
    day's amounts up to a printed balance). Returns (rows, collapsed_count)."""
    out = list(rows)
    collapsed = 0
    index = 0
    while index < len(out):
        run_end = index
        while (run_end + 1 < len(out) and out[run_end + 1].date == out[index].date
               and out[run_end + 1].balance is not None and out[run_end + 1].balance == out[index].balance):
            run_end += 1
        if run_end > index and out[index].balance is not None:
            for position in range(index, run_end):
                out[position] = replace(out[position], balance=None)
                collapsed += 1
        index = run_end + 1
    return out, collapsed


def _duplicates(rows: list[CandidateRow]) -> tuple[int, int]:
    """(distinguished_repeats, unverifiable_repeats): a repeat of (date, description, amount, direction)
    is distinguished when both rows print balances and they differ."""
    seen: dict[tuple, list[CandidateRow]] = {}
    distinguished = unverifiable = 0
    for row in rows:
        key = (row.date, normalise_description(row.description), row.amount, row.direction)
        twins = seen.setdefault(key, [])
        for twin in twins:
            if twin.balance is not None and row.balance is not None and twin.balance != row.balance:
                distinguished += 1
            else:
                unverifiable += 1
        twins.append(row)
    return distinguished, unverifiable


def gate(rows: list[CandidateRow], meta: AccountMeta, *, tolerance: Decimal = Decimal("0.01")) -> GateVerdict:
    reasons: list[str] = []
    checks: dict = {"gate_version": GATE_VERSION, "derived": []}
    if not rows:
        return GateVerdict(False, ("no_rows",), 0, (), None, 0, 0, checks)
    if any(row.amount <= 0 for row in rows):
        reasons.append("proposal_invalid")
    rows, reversed_order = orient(rows)
    rows, collapsed = collapse_daily_balances(rows)
    checks["reversed_order"] = reversed_order
    checks["collapsed_daily_balances"] = collapsed
    printed_beginning, printed_ending = meta.beginning_balance is not None, meta.ending_balance is not None
    anchored = "both" if printed_beginning and printed_ending else ("one" if printed_beginning or printed_ending else "none")
    checks["anchored"] = anchored
    beginning, ending = meta.beginning_balance, meta.ending_balance
    first, last = rows[0], rows[-1]
    if anchored == "none":
        reasons.append("anchors_underdetermined")
    else:
        if beginning is None and first.balance is not None and first.direction in ("credit", "debit"):
            beginning = first.balance - first.amount if first.direction == "credit" else first.balance + first.amount
            checks["derived"].append("beginning_balance")
        if ending is None and last.balance is not None:
            ending = last.balance
            checks["derived"].append("ending_balance")
    if beginning is None and "anchors_underdetermined" not in reasons:
        reasons.append("missing_beginning_balance")
    if ending is None and "anchors_underdetermined" not in reasons:
        reasons.append("missing_ending_balance")
    if checks["derived"]:
        # A derived anchor leaves one end of the ledger unverified (a truncated read at that end still
        # reconciles), so the verdict is recorded but NOT admitted; the report counts this class apart.
        reasons.append("anchor_derived")
    resolved, flagged = resolve_directions(rows, beginning)
    if any(row.direction == "unknown" for row in resolved):
        reasons.append("direction_unknown")
    if flagged and anchored != "both":
        reasons.append("chain_direction_unanchored")
    dates = [row.date for row in resolved]
    if any(value is None for value in dates):
        reasons.append("date_unparsed")
    parsed = [date.fromisoformat(value) for value in dates if value]
    # Date order and period membership are RECORDED, not refusal reasons: sectioned statements restart
    # dates per section and banks list checks by number; the reader's own arithmetic decides admission.
    outside = 0
    if meta.period_start and meta.period_end and parsed:
        lower = date.fromisoformat(meta.period_start) - timedelta(days=PERIOD_GRACE_DAYS)
        upper = date.fromisoformat(meta.period_end) + timedelta(days=PERIOD_GRACE_DAYS)
        outside = sum(1 for value in parsed if value < lower or value > upper)
    checks["dates_outside_period"] = outside
    checks["date_order_breaks"] = sum(1 for earlier, later in zip(parsed, parsed[1:]) if later < earlier)
    distinguished, unverifiable = _duplicates(resolved)
    checks["repeats"] = {"distinguished": distinguished, "unverifiable": unverifiable}
    computed_ending: Decimal | None = None
    continuity_breaks = 0
    counts_vouch = False
    if beginning is not None and ending is not None and "direction_unknown" not in reasons and "proposal_invalid" not in reasons:
        meta_for_reader = replace(meta, beginning_balance=beginning, ending_balance=ending)
        result = reconcile(statement_from(resolved, meta_for_reader))
        if result.computed_ending is not None:
            computed_ending = Decimal(str(result.computed_ending)).quantize(Decimal("0.01"))
        continuity_breaks = int(result.continuity_breaks or 0)
        checks["reader_issues"] = list(result.issues)
        checks["summary_ok"] = result.summary_ok
        checks["credit_count_matches"] = result.stated_credit_count_matches
        checks["debit_count_matches"] = result.stated_debit_count_matches
        delta = abs(Decimal(str(result.sum_delta))) if result.sum_delta is not None else None
        if delta is None or delta > tolerance:
            reasons.append("sum_mismatch")
        if continuity_breaks:
            reasons.append("continuity_break")
        if result.summary_ok is False:
            reasons.append("summary_mismatch")
        if result.stated_credit_count_matches is False or result.stated_debit_count_matches is False:
            reasons.append("count_mismatch")
        if not result.ok and not any(r in reasons for r in ("sum_mismatch", "summary_mismatch")):
            reasons.append("coverage_mismatch")   # RR-7: a reconcile issue that is neither the sum nor the summary
    if unverifiable:
        reasons.append("duplicate_row")   # RR-2: an unverifiable repeat is never amnestied by a matching count
    ordered = tuple(dict.fromkeys(reasons))
    admitted = not ordered
    return GateVerdict(admitted, ordered, len(resolved), tuple(resolved) if admitted else (), computed_ending,
                       continuity_breaks, flagged, checks, anchored)
