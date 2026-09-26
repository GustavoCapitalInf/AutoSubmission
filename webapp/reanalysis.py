"""Re-analysis of a saved statement (docs/superpowers/specs/2026-09-24-lender-detection-design.md §8.6, D12).

`replay_reviews` puts the analyst's revenue decisions (the append-only `review_decisions` table) back onto a fresh
analysis of the same statement, only where the posting is unchanged: the row at the same account and location has the
same description and amount. The others are counted, so the analyst can be told how many reviews need redoing.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

from analysis.payload_shape import payload_accounts
from analysis.revenue import (
    LEGACY_REVENUE_STATE_MAP,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
)

#: Named once: it reaches a shape refusal's message.
_REPLAY_SURFACE = "webapp/reanalysis.py::replay_reviews"


@dataclass(frozen=True)
class Replay:
    """A fresh analysis with the decisions replayed, and the `review_decisions` ids replayed, needing redoing, and
    decided by a rule (their row no longer awaits review, so there is nothing to redo)."""

    analysis: dict
    replayed: tuple[int, ...]
    not_replayed: tuple[int, ...]
    decided_by_rules: tuple[int, ...] = ()


def _money(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 2)


def _prior_state(row: Mapping) -> dict | None:
    """The classification record a decision changed, as the review route recorded it; None when it cannot be read."""
    text = row.get("prior_state")
    if not isinstance(text, str):
        return None
    try:
        prior = json.loads(text)
    except ValueError:
        return None
    return prior if isinstance(prior, dict) else None


def _identity(row: Mapping) -> tuple | None:
    """What a decision was made on, from its recorded prior state: (account number, location, description, amount to
    the cent, date). None when the prior state cannot be read."""
    prior = _prior_state(row)
    if prior is None:
        return None
    return (prior.get("account"), row.get("source_location"), prior.get("original_description"),
            _money(prior.get("amount")), prior.get("date"))


def _records(holder: Mapping) -> Iterator[dict]:
    """One account's classification records, in ledger order."""
    for transaction in (holder.get("statement") or {}).get("transactions") or []:
        if isinstance(transaction, dict) and isinstance(transaction.get("classification"), dict):
            yield transaction["classification"]


def _same_posting(record: Mapping, identity: tuple) -> bool:
    """The row is the one the decision was made on (spec §8.6.5): the same account number, location, description and
    amount to the cent. The date is not compared: the spec names these four."""
    account, location, description, amount, _date = identity
    return (record.get("source_location") == location
            and isinstance(description, str) and record.get("original_description") == description
            and amount is not None and _money(record.get("amount")) == amount
            and record.get("account") == account)


def _places(accounts: Sequence[Mapping], identity: tuple | None) -> list[tuple[int, dict]]:
    """Every (1-based account number, record) holding the posting `identity` names, across every account."""
    if identity is None:
        return []
    return [(number, record)
            for number, holder in enumerate(accounts, start=1)
            for record in _records(holder)
            if _same_posting(record, identity)]


def _applied(analysis: dict, history: Sequence[Mapping],
             waiting: Sequence[tuple[int, int]]) -> tuple[dict, list[int], list[int]]:
    """`analysis` with the decisions `waiting` names applied, and the history indexes applied and refused. `waiting`
    holds (history index, 1-based account number) pairs.

    Every decision is written onto ONE copy of `analysis`, whose revenue views are rebuilt once, after the last: the
    cost is one copy and one rebuild however many decisions there are. A decision the review writer refuses is refused
    alone; the writer checks everything before it writes, so the copy is as it was. When the rebuilt views do not hold,
    which no decision can cause (a posted credit with no valid classification record), every decision is refused and
    `analysis` is returned as it was handed, as the review routes keep the saved analysis when their rebuild refuses."""
    if not waiting:
        return analysis, [], []
    candidate = deepcopy(analysis)
    applied: list[int] = []
    refused: list[int] = []
    for index, account in waiting:
        row = history[index]
        decided_at = row.get("decided_at")
        try:
            record_serialized_revenue_review(
                candidate, source_location=row.get("source_location"), decision=row.get("decision"),
                account=account, reviewed_at=decided_at if isinstance(decided_at, str) else None)
        except (LookupError, ValueError):
            refused.append(index)
            continue
        applied.append(index)
    if not applied:
        return analysis, [], refused
    try:
        rebuild_serialized_revenue_views(candidate)
    except (LookupError, ValueError):
        return analysis, [], sorted(refused + applied)
    return candidate, applied, refused


def _ids(history: Sequence[Mapping], indexes: Iterable[int]) -> tuple[int, ...]:
    return tuple(history[index].get("id") for index in indexes)


def _redone(identity: tuple | None, later: Sequence[tuple | None]) -> bool:
    """Whether a decision made after this one (`later`, their identities) redid it: on the same account number, and
    either the same row (the analyst decided that row again, whatever it printed by then) or the same posting wherever
    it sat by then (the same description, amount and date). Two postings of one account alike in all three are the one
    case this cannot tell apart; a decision on one of them then passes for a redo of the other, and the count says one
    review too few."""
    if identity is None:
        return False
    return any(other is not None and other[0] == identity[0]
               and (other[1] == identity[1] or other[2:] == identity[2:])
               for other in later)


def _awaits_review(record: Mapping) -> bool:
    """The row is a deposit the analyst decides, not one a rule decided: the review writer refuses any other
    (analysis/revenue.py), so the analyst could not redo a decision on it."""
    initial = record.get("revenue_initial_classification")
    return LEGACY_REVENUE_STATE_MAP.get(initial, initial) == "unverified_deposit"


def replay_reviews(analysis: dict, history: Sequence[Mapping]) -> Replay:
    """Replay `history` (`JobStore.review_history` rows, oldest first) onto `analysis`, a fresh analysis of the
    statement the decisions were made on. `analysis` itself is never changed: the decisions are applied to one copy,
    kept only when its rebuilt revenue views hold.

    A decision is replayed only onto the one row, across every account, whose account number, location, description
    and amount are the ones it was made on; a location names a row, so a posting that moved is not followed. Of several
    decisions on one such row the latest is replayed: each sets the state outright. A reset asks for the pending state
    a fresh analysis already has, so it is neither replayed nor counted. Replayed decisions keep the time the analyst
    made them.

    A decision that is not replayed needs redoing, unless a later decision redid it (`_redone`). One whose row a rule
    of the current analysis now decides cannot be redone (the analyst can no longer review that row), so it is
    reported apart, as decided by the rules (spec §8.6.5: anything that cannot be replayed is reported back). Nothing
    here writes a decision: the replay is part of the re-analysis, which the audit log records.
    """
    identities = [_identity(row) for row in history]
    latest: dict[tuple, int] = {}
    for index, identity in enumerate(identities):
        key = ("unreadable", index) if identity is None else identity[:4]
        latest.pop(key, None)  # the later decision replaces the earlier one, and is replayed in its own turn
        latest[key] = index
    try:
        accounts = payload_accounts(analysis, surface=_REPLAY_SURFACE)
    except ValueError:
        accounts = []
    waiting: list[tuple[int, int]] = []
    redo: list[int] = []
    ruled: list[int] = []
    for index in latest.values():
        if history[index].get("decision") == "reset":
            continue
        places = _places(accounts, identities[index])
        if len(places) != 1:
            if not _redone(identities[index], identities[index + 1:]):
                redo.append(index)
            continue
        number, record = places[0]
        if not _awaits_review(record):
            ruled.append(index)
            continue
        waiting.append((index, number))
    updated, applied, refused = _applied(analysis, history, waiting)
    return Replay(updated, _ids(history, applied), _ids(history, sorted(redo + refused)), _ids(history, ruled))
