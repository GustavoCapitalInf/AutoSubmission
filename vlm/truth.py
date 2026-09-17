"""The reader's validated rows (CTRL) as truth for row-level comparison, and the matcher."""
from __future__ import annotations

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
    """Read-only join to the run-of-record cache; returns None when the reader produced no payload."""

    def __init__(self, data_dir: Path, run_dir: Path) -> None:
        from tools.cohort_replay import ColdCache
        from vlm.partitions import run_rows

        self._cache = ColdCache(Path(data_dir), Path(run_dir))
        self._rows = run_rows(Path(run_dir))

    def accounts(self, sha: str) -> list[TruthAccount] | None:
        row = self._rows.get(sha.upper())
        if row is None:
            return None
        markdown, pages = self._cache.text(sha.upper(), row)
        if markdown is None:
            return None
        payload = self._cache.baseline_payload(markdown, pages)
        return None if payload is None else truth_from_payload(payload)

    def close(self) -> None:
        self._cache.close()


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
