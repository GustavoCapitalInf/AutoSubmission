"""Sinks. One `write(record)` API; the emitters never know which they hold.

Telemetry is ON by default on both paths (Ocean ruling 8): the point of H-3 is
coverage measurement, and the sensitivity invariant is what makes always-on
safe. `TELEMETRY_DISABLED=1` swaps in `NullSink` everywhere.

Every sink swallows its own failures (H3_SCHEMA I4). A telemetry defect must
degrade to a missing measurement, never to a failed analysis — the record is
about the work, it is not the work.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

#: Env kill-switch. Documented in README's telemetry section.
DISABLE_ENV = "TELEMETRY_DISABLED"

#: Default JSONL destination for CLI runs. Gitignored: telemetry is run output.
DEFAULT_RUN_DIR = Path("telemetry_runs")

_TRUE = {"1", "true", "yes", "on"}


def telemetry_disabled() -> bool:
    return (os.environ.get(DISABLE_ENV) or "").strip().lower() in _TRUE


class NullSink:
    """Accepts and discards. The kill-switch, and the default in tests."""

    def write(self, record: dict) -> None:
        return None

    def close(self) -> None:
        return None


class JsonlSink:
    """Append-only JSON Lines. No SQLite, no webapp import — batch.py's sink."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.written = 0
        self.failures = 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.failures += 1

    def write(self, record: dict) -> None:
        try:
            line = json.dumps(record, sort_keys=True, ensure_ascii=False)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            self.written += 1
        except Exception:
            self.failures += 1

    def close(self) -> None:
        return None


class SqliteSink:
    """Writes through `Storage.append_telemetry` (schema v4). Webapp path."""

    def __init__(self, storage: Any) -> None:
        self._storage = storage
        self.written = 0
        self.failures = 0

    def write(self, record: dict) -> None:
        try:
            self._storage.append_telemetry(record)
            self.written += 1
        except Exception:
            self.failures += 1

    def close(self) -> None:
        return None


def read_jsonl(path: str | Path) -> list[dict]:
    """Every record in a JSONL file. Malformed lines are skipped, not fatal."""
    records: list[dict] = []
    handle_path = Path(path)
    if not handle_path.is_file():
        return records
    for line in handle_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def open_jsonl_sink(path: str | Path | None, run_id: str):
    """The CLI's sink: JSONL unless the kill-switch is set."""
    if telemetry_disabled():
        return NullSink()
    return JsonlSink(path if path is not None else DEFAULT_RUN_DIR / f"{run_id}.jsonl")


def open_sqlite_sink(storage: Any | None):
    """The webapp's sink: SQLite unless the kill-switch is set."""
    if storage is None or telemetry_disabled():
        return NullSink()
    return SqliteSink(storage)
