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

from .collect import (
    DETERMINISTIC_MODEL_SUFFIX,
    DispatchCollector,
    StageTimer,
    reconstructed_claim,
    score_vector,
    sole_surviving_claimant,
)
from .diagnostics import (
    ADVISORY_CODES,
    CLASS_OF,
    CLASS_PRECEDENCE,
    DIAGNOSABLE_CLASSES,
    DIAGNOSTICS_VERSION,
    VOCABULARY,
    diagnose,
    empty_diagnostics,
)
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
    DISPATCH_SOURCES,
    OUTCOME_CLASSES,
    SCORE_CAP,
    SOURCE_CACHED,
    SOURCE_LIVE,
    SOURCE_UNAVAILABLE,
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
    "ADVISORY_CODES",
    "CLASS_OF",
    "CLASS_PRECEDENCE",
    "DEFERRED_REASONS",
    "DETERMINISTIC_MODEL_SUFFIX",
    "DIAGNOSABLE_CLASSES",
    "DIAGNOSTICS_VERSION",
    "DISABLE_ENV",
    "DISPATCH_SOURCES",
    "DispatchCollector",
    "JsonlSink",
    "NullSink",
    "OUTCOME_CLASSES",
    "SCORE_CAP",
    "SOURCE_CACHED",
    "SOURCE_LIVE",
    "SOURCE_UNAVAILABLE",
    "SqliteSink",
    "StageTimer",
    "TELEMETRY_VERSION",
    "TOP_LEVEL_KEYS",
    "VOCABULARY",
    "build_record",
    "classify_outcome",
    "diagnose",
    "dispatch_section",
    "empty_diagnostics",
    "document_section",
    "model_calls_for",
    "new_run_id",
    "open_jsonl_sink",
    "open_sqlite_sink",
    "read_jsonl",
    "reconstructed_claim",
    "score_vector",
    "sole_surviving_claimant",
    "source_path_for",
    "source_section",
    "telemetry_disabled",
]
