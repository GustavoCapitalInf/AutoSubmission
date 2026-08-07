"""H-3 telemetry: one write-only record per statement per run.

What it answers: *what happened to this document, and what did it cost* — so
the deterministic-coverage rate and its failure taxonomy are a query rather
than log archaeology. Schema and rulings:
`docs/moneythumb-replacement/H3_SCHEMA.md`.

Three properties hold everywhere in this package:

- **Write-only side-band.** Nothing here is read back by analysis, and no
  analysis output changes because telemetry is on. The corpus gate is
  byte-identical merge authority, so an observable change to a report would be
  stop-the-line.
- **Non-sensitive by construction.** Hashes, registry ids, enum codes, counts,
  timings. Never customer names, account numbers, amounts, statement text, or
  filenames. See `record` for the two traps this costs us.
- **Cannot fail a job.** Every sink swallows its own failures: a telemetry
  defect degrades to a missing measurement, never a failed analysis.

    python -m telemetry.report --jsonl telemetry_runs/<run_id>.jsonl
"""
from __future__ import annotations

from .collect import DispatchCollector, StageTimer, score_vector
from .emit import (
    DISABLE_ENV,
    JsonlSink,
    NullSink,
    SqliteSink,
    open_jsonl_sink,
    open_sqlite_sink,
    read_jsonl,
    telemetry_disabled,
)
from .record import (
    DEFERRED_REASONS,
    OUTCOME_CLASSES,
    SCORE_CAP,
    TELEMETRY_VERSION,
    TOP_LEVEL_KEYS,
    build_record,
    classify_outcome,
    dispatch_section,
    document_section,
    model_calls_for,
    new_run_id,
    source_path_for,
    source_section,
)

__all__ = [
    "DEFERRED_REASONS",
    "DISABLE_ENV",
    "DispatchCollector",
    "JsonlSink",
    "NullSink",
    "OUTCOME_CLASSES",
    "SCORE_CAP",
    "SqliteSink",
    "StageTimer",
    "TELEMETRY_VERSION",
    "TOP_LEVEL_KEYS",
    "build_record",
    "classify_outcome",
    "dispatch_section",
    "document_section",
    "model_calls_for",
    "new_run_id",
    "open_jsonl_sink",
    "open_sqlite_sink",
    "read_jsonl",
    "score_vector",
    "source_path_for",
    "source_section",
    "telemetry_disabled",
]
