"""Re-analysis of a saved statement (docs/superpowers/specs/2026-09-24-lender-detection-design.md §8.6, D12).

`rerun_analysis` runs the statement's stored PDF through the worker's own read and analysis path
(`webapp.worker.run_job`), its reading served from the artifact cache only: a re-analysis only analyzes a reading
already made, and no reading rung runs. It writes nothing into the cache, whose one writer stays the upload queue's
worker. The run writes into a stand-in for the job store, so the saved job is not touched until the route accepts the
new analysis.

`replay_reviews` puts the analyst's revenue decisions (the append-only `review_decisions` table) back onto a fresh
analysis of the same statement, only where the posting is unchanged: the row at the same account and location has the
same description and amount. The others are counted, so the analyst can be told how many reviews need redoing.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

from analysis import zelle_view
from analysis.payload_shape import payload_accounts
from analysis.revenue import (
    LEGACY_REVENUE_STATE_MAP,
    REVIEWABLE_NON_REVENUE_REASONS,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
)

from .artifact_cache import ArtifactCache
from .jobs import Job, JobStore
from .worker import run_job

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


def _awaits_review(record: Mapping, decision: object) -> bool:
    """The row awaits this decision (true revenue spec §10.7): a deposit the rules left unverified awaits any
    decision, as it always has; a credit a rule verified (5.6, a record with a tier) awaits only a reject, because the
    analyst's word wins over a rule. A confirm on a rule-verified row, or any decision on a row a non-revenue rule
    decided, does not await review: the review writer would refuse it (analysis/revenue.py), so it is reported as
    decided by the rules, never as needing redoing. R2-OW03 (the underwriter's Q3): a Zelle deposit the owner's policy
    excluded (REVIEWABLE_NON_REVENUE_REASONS) awaits a confirm only, so a stored confirm is replayed and a stored
    reject, which the writer refuses on a row already non-revenue, is reported as decided by the rules."""
    initial = record.get("revenue_initial_classification")
    initial = LEGACY_REVENUE_STATE_MAP.get(initial, initial)
    if initial == "unverified_deposit":
        return True
    tiered = isinstance(record.get("revenue_tier"), str)
    if initial == "non_revenue":
        return (
            tiered and decision == "confirm"
            and record.get("revenue_tier_reason") in REVIEWABLE_NON_REVENUE_REASONS
        )
    return initial == "verified_revenue" and decision == "reject" and tiered


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

    The owner's amendment of 2026-10-06 to the underwriter's Q3 (spec §10.7; R2-OW17): a fresh analysis that carries
    the counted Zelle reading's edits (analysis/zelle_view.py) is replayed in both readings, each on its own: a decision
    is written to a reading where that reading's record awaits it, and every other reading stays at its analysis state,
    which is exactly the review writer's reset, so the live state and the re-analysed one agree. A decision is replayed
    when any reading takes it, refused only when every reading that awaits it refuses it, and decided by the rules only
    when no reading awaits it. Without such edits this is today's replay exactly.
    """
    identities = [_identity(row) for row in history]
    latest: dict[tuple, int] = {}
    for index, identity in enumerate(identities):
        key = ("unreadable", index) if identity is None else identity[:4]
        latest.pop(key, None)  # the later decision replaces the earlier one, and is replayed in its own turn
        latest[key] = index
    carrying = False
    readings = [analysis]
    if zelle_view.reading(analysis, counted=False) is not analysis:  # an account carries the edits key
        no, yes, carrying = zelle_view.split_readings(analysis)
        readings = [no, yes] if carrying else [no]  # unusable edits: the key dropped, today's replay on the rest
    try:
        accounts = [payload_accounts(reading, surface=_REPLAY_SURFACE) for reading in readings]
    except ValueError:
        accounts = [[] for _reading in readings]
    waiting: list[list[tuple[int, int]]] = [[] for _reading in readings]
    redo: list[int] = []
    ruled: list[int] = []
    for index in latest.values():
        if history[index].get("decision") == "reset":
            continue
        places = [_places(holders, identities[index]) for holders in accounts]
        if len(places[0]) != 1:
            if not _redone(identities[index], identities[index + 1:]):
                redo.append(index)
            continue
        awaited = False
        for position, found in enumerate(places):
            number, record = found[0]
            if _awaits_review(record, history[index].get("decision")):
                waiting[position].append((index, number))
                awaited = True
        if not awaited:
            ruled.append(index)
    results = [_applied(reading, history, queue) for reading, queue in zip(readings, waiting)]
    applied = sorted({index for _updated, taken, _refused in results for index in taken})
    refused = sorted({index for _updated, _taken, lost in results for index in lost} - set(applied))
    updated = results[0][0] if not carrying else zelle_view.join_readings(results[0][0], results[1][0])
    return Replay(updated, _ids(history, applied), _ids(history, sorted(redo + refused)), _ids(history, ruled))


#: Why a re-analysis stops where the worker would read the statement: the reading it needs is not in the artifact
#: cache (a pruned cache, a new OCR toolchain, or a reading the statement never had, such as the visual pair's where
#: the deterministic path claimed it before). The reading is served from the cache only (spec §8.6.2): a re-analysis
#: runs on the request thread, outside the upload queue's single worker slot, which keeps two OCR jobs from running
#: at once.
READING_NOT_CACHED = (
    "the reading this re-analysis needs is not cached, and a re-analysis only analyzes a reading already made; "
    "upload the statement again instead"
)

#: Why a re-run that produced an analysis is still not accepted: under the current rules the analysis comes from
#: another cached reading of the statement than the one the saved analysis was made from (the worker chose the other
#: of its deterministic and visual-pair paths). The saved analysis and the source view beside it describe one reading,
#: so the saved job is kept.
READS_DIFFERENTLY = (
    "under the current rules the analysis comes from another reading of the statement than the saved one"
)


class _ReadingRefused(Exception):
    """Raised inside `run_job` where a re-analysis would read the statement. The worker's own boundary catches it
    (`run_job`'s `except Exception`) and records its fixed stage failure on the stand-in store; `rerun_analysis`
    answers READING_NOT_CACHED from the stand-in's flag instead."""


class _CacheOnly:
    """The artifact cache as a re-analysis sees it: every stage reads through the real cache, a reading the cache does
    not hold is never computed, and nothing is written into it.

    `cached_ocr` asks `get_ocr` before it computes (webapp/artifact_cache.py), and the worker's reading ladder and its
    visual pair both read through `cached_ocr`, so a miss stops the run before any reader or remote model is called.
    On the visual pair's path this is the only guard: the pair does work before it names its first step.

    The upload queue's worker stays the cache's one writer. The cache writes each entry through one fixed temporary
    file, so a write from this request thread to an entry an upload of the same statement is writing at that moment
    could fail the upload. The three writes below are the only ones the worker's cache helpers make (`cached_ocr`,
    `cached_analysis`, `cached_report`), and each helper ignores the key a write returns. The new analysis is saved
    with the job, and the next upload of the statement caches it."""

    def __init__(self, cache: ArtifactCache, run: _CapturedJobStore) -> None:
        self._cache = cache
        self._run = run

    def __getattr__(self, name: str):
        return getattr(self._cache, name)

    def get_ocr(self, content_hash: str, settings_key: str) -> tuple[bool, dict | None]:
        hit, document = self._cache.get_ocr(content_hash, settings_key)
        if not hit:
            self._run.refuse_reading()
        return hit, document

    def put_ocr(self, content_hash: str, settings_key: str, document: object) -> None:
        # In a re-analysis this is reached only when the visual pair answered again from its own local evidence, over
        # a cached reading that failed its own checks (every rung of the ladder names itself first and is stopped).
        # That entry is left for the next upload to repair.
        return None

    def put_analysis(self, markdown_hash: str, settings_key: str, analysis: dict) -> None:
        return None

    def put_report(self, markdown_hash: str, settings_key: str, html: str) -> None:
        return None


class _CapturedJobStore:
    """What `run_job` is handed during a re-analysis, in place of the job store.

    Its cache is `_CacheOnly`, so no reading rung runs and nothing is written into the cache. Cache hits are recorded
    in the real audit log (the evidence that the reading was served from the cache), but every job-state write lands
    here, so the saved job keeps its status, its stage and its analysis until the route accepts the new one. It has no
    `storage`, so the run writes no telemetry record (`telemetry.emit.open_sqlite_sink` opens a null sink): telemetry
    counts intake runs, and the audit log records the re-analysis. Its methods are exactly the ones `webapp/worker.py`
    calls on its store."""

    def __init__(self, store: JobStore, job: Job) -> None:
        self._store = store
        self.cache = _CacheOnly(store.cache, self)
        self.job = Job(id=job.id, filename=job.filename, force_ocr=job.force_ocr, parse_mode=job.parse_mode,
                       page_count=job.page_count, content_sha256=job.content_sha256)
        self.result: tuple[str, str, dict | None, str | None, str | None] | None = None
        self.error: str | None = None
        self.reading_refused = False

    def refuse_reading(self) -> None:
        """Stop the run where the worker would read the statement."""
        self.reading_refused = True
        raise _ReadingRefused()

    def get(self, job_id: str) -> Job | None:
        return self.job if job_id == self.job.id else None

    def record_cache_hit(self, job_id: str, stage: str, cache_key: str | None) -> None:
        self._store.record_cache_hit(job_id, stage, cache_key)

    def set_status(self, job_id: str, status: str) -> None:
        self.job.status = status

    def set_stage(self, job_id: str, stage: str, parse_model: str | None = None) -> None:
        # "analyzing" is the one stage the worker names outside a read (`run_job`). Every other stage is a rung of its
        # reading ladder or a step of the visual pair, named just before it reads: a cached reading that fails its own
        # checks is read again by `cached_ocr` after `get_ocr` has answered a hit, and it is stopped here.
        if stage != "analyzing":
            self.refuse_reading()
        self.job.stage = stage

    def append_page_live(self, job_id: str, page: int, chunk: str) -> None:
        # Only a live read streams text.
        self.refuse_reading()

    def set_page_live(self, job_id: str, page: int, text: str) -> None:
        # A cached reading replays its pages here.
        return None

    def set_result(self, job_id: str, markdown: str, html: str, analysis: dict | None = None,
                   analysis_error: str | None = None, parse_model: str | None = None) -> None:
        self.job.status = "done"
        self.result = (markdown, html, analysis, analysis_error, parse_model)

    def set_error(self, job_id: str, error: str) -> None:
        self.job.status = "error"
        self.error = error


@dataclass(frozen=True)
class Rerun:
    """A re-run's new analysis; or None, with the reason it is not accepted: text the worker already publishes for
    that outcome (`_stage_failure`, `_analysis_failure`, its no-native-text notice), READING_NOT_CACHED, or
    READS_DIFFERENTLY."""

    analysis: dict | None
    reason: str | None = None


def rerun_analysis(store: JobStore, job: Job, pdf_bytes: bytes) -> Rerun:
    """Run a saved job's statement through `webapp.worker.run_job` again, with the job's own read flag and parse mode,
    into a `_CapturedJobStore`, its reading from the artifact cache only. Nothing of the saved job is written here."""
    run = _CapturedJobStore(store, job)
    run_job(job.id, pdf_bytes, job.filename, run, force_ocr=job.force_ocr, parse_mode=job.parse_mode)
    if run.reading_refused:
        return Rerun(None, READING_NOT_CACHED)
    if run.error is not None or run.result is None:
        return Rerun(None, run.error)
    markdown, _html, analysis, analysis_error, _parse_model = run.result
    if analysis is None:
        return Rerun(None, analysis_error)
    if markdown != job.markdown:
        return Rerun(None, READS_DIFFERENTLY)
    return Rerun(analysis)
