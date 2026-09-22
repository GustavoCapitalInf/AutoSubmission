"""The reader's validated rows (CTRL) as truth for row-level comparison, and the matcher."""
from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from analysis.payload_shape import payload_accounts
from vlm.assemble import CandidateRow
from vlm.textparse import normalise_description, to_decimal


@dataclass(frozen=True)
class TruthRow:
    date: str
    description: str
    amount: Decimal
    direction: str
    balance: Decimal | None


@dataclass(frozen=True)
class TruthAccount:
    account_number: str | None
    beginning: Decimal | None
    ending: Decimal | None
    period_start: str | None
    period_end: str | None
    currency: str | None
    rows: tuple[TruthRow, ...]


def _money(value) -> Decimal | None:
    return None if value is None else to_decimal(value)


def truth_from_payload(payload: dict) -> list[TruthAccount]:
    accounts: list[TruthAccount] = []
    for account in payload_accounts(payload, surface="vlm.truth"):
        statement = account.get("statement") or {}
        rows = tuple(
            TruthRow(date=str(t.get("date") or ""), description=str(t.get("description") or ""),
                     amount=abs(to_decimal(t.get("amount") or 0)), direction=str(t.get("direction") or ""),
                     balance=_money(t.get("running_balance")))
            for t in statement.get("transactions") or []
        )
        accounts.append(TruthAccount(
            account_number=statement.get("account_number"), beginning=_money(statement.get("beginning_balance")),
            ending=_money(statement.get("ending_balance")), period_start=statement.get("period_start"),
            period_end=statement.get("period_end"), currency=statement.get("currency"), rows=rows,
        ))
    return accounts


class ReaderTruth:
    """Read-only join to the run-of-record cache; returns None when the reader produced no payload.

    The cache holds a SQLite connection, which SQLite binds to the thread that opened it; the pipelined runner
    matches documents from worker threads (2026-09-18: a whole repeat wave failed with ProgrammingError), so
    each thread gets its own read-only cache, all closed together."""

    def __init__(self, data_dir: Path, run_dir: Path, *, cache_factory=None, rows: dict | None = None) -> None:
        self._data_dir, self._run_dir = Path(data_dir), Path(run_dir)
        if cache_factory is None:
            from tools.cohort_replay import ColdCache

            cache_factory = lambda: ColdCache(self._data_dir, self._run_dir)  # noqa: E731
        self._factory = cache_factory
        if rows is None:
            from vlm.partitions import run_rows

            rows = run_rows(self._run_dir)
        self._rows = rows
        self._local = threading.local()
        self._caches: list = []
        self._lock = threading.Lock()

    def _cache(self):
        cache = getattr(self._local, "cache", None)
        if cache is None:
            cache = self._factory()
            self._local.cache = cache
            with self._lock:
                self._caches.append(cache)
        return cache

    def accounts(self, sha: str) -> list[TruthAccount] | None:
        row = self._rows.get(sha.upper())
        if row is None:
            return None
        cache = self._cache()
        markdown, pages = cache.text(sha.upper(), row)
        if markdown is None:
            return None
        payload = cache.baseline_payload(markdown, pages)
        return None if payload is None else truth_from_payload(payload)

    def close(self) -> None:
        with self._lock:
            caches, self._caches = self._caches, []
        for cache in caches:
            try:
                cache.close()
            except Exception:  # noqa: BLE001 - a worker thread's read-only connection dies with its thread
                pass


@dataclass(frozen=True)
class RowMatch:
    truth_rows: int
    candidate_rows: int
    matched: int
    exact_balance: int
    exact_description: int
    missing: int
    extra: int
    balance_mismatch: int = 0   # matched rows where both sides print a balance and they differ


def match_rows(candidates: list[CandidateRow], truth: TruthAccount) -> RowMatch:
    pool: Counter = Counter((t.date, t.amount, t.direction) for t in truth.rows)
    by_key: dict[tuple, list[TruthRow]] = {}
    for t in truth.rows:
        by_key.setdefault((t.date, t.amount, t.direction), []).append(t)
    matched = exact_balance = exact_description = balance_mismatch = 0
    for candidate in candidates:
        key = (candidate.date, candidate.amount, candidate.direction)
        if pool.get(key, 0) <= 0:
            continue
        pool[key] -= 1
        matched += 1
        twin = by_key[key].pop(0)
        if candidate.balance is not None and twin.balance is not None:
            if candidate.balance == twin.balance:
                exact_balance += 1
            else:
                balance_mismatch += 1
        if normalise_description(candidate.description) == normalise_description(twin.description):
            exact_description += 1
    return RowMatch(truth_rows=len(truth.rows), candidate_rows=len(candidates), matched=matched,
                    exact_balance=exact_balance, exact_description=exact_description,
                    missing=len(truth.rows) - matched, extra=len(candidates) - matched, balance_mismatch=balance_mismatch)
