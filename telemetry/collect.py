"""Collectors: the pipeline callback, stage timing, and the score vector.

The one seam into `analysis/` is `DispatchCollector`, passed as
`analyze_markdown(..., on_dispatch=collector)`. Its contract with the pipeline
is **it must not raise and must not mutate** — `analysis/pipeline.py`
deliberately has no `try/except` around the call, because swallowing exceptions
inside a protected module would be new control flow there to cover a defect
here. So the guarantee lives on this side, and a test proves it holds even when
handed nonsense.
"""
from __future__ import annotations

import time
from typing import Any


class DispatchCollector:
    """Captures the Dispatch of record. Never raises, never mutates.

    Callable so it can be passed straight as `on_dispatch`. It keeps the object
    it was given; the *projection* to a record (which drops
    `Dispatch.statement`, i.e. every amount and description) happens in
    `record.dispatch_section`, so nothing here can leak by accident.
    """

    __slots__ = ("dispatch", "calls", "errors")

    def __init__(self) -> None:
        self.dispatch: Any | None = None
        self.calls = 0
        self.errors = 0

    def __call__(self, dispatch: Any) -> None:
        try:
            self.calls += 1
            self.dispatch = dispatch
        except Exception:  # pragma: no cover - defensive; assignment cannot raise
            self.errors += 1

    @property
    def seen(self) -> bool:
        return self.dispatch is not None


class StageTimer:
    """Wall-clock milliseconds per stage, plus that stage's cache disposition.

    `cache` is one of "hit" | "miss" | "bypass": bypass means the stage does not
    go through the artifact cache at all (the CLI path, or preflight).
    """

    def __init__(self) -> None:
        self._stages: dict[str, dict] = {}

    def record(self, stage: str, ms: float, cache: str = "bypass") -> None:
        self._stages[stage] = {"ms": round(ms, 1), "cache": cache}

    def set_cache(self, stage: str, cache: str) -> None:
        self._stages.setdefault(stage, {"ms": 0.0, "cache": cache})["cache"] = cache

    def time(self, stage: str, cache: str = "bypass"):
        return _StageContext(self, stage, cache)

    def as_dict(self) -> dict:
        return dict(self._stages)


class _StageContext:
    def __init__(self, timer: StageTimer, stage: str, cache: str) -> None:
        self._timer, self._stage, self._cache = timer, stage, cache
        self._started = 0.0

    def __enter__(self) -> "_StageContext":
        self._started = time.perf_counter()
        return self

    def __exit__(self, *exc_info) -> None:
        elapsed_ms = (time.perf_counter() - self._started) * 1000
        existing = self._timer.as_dict().get(self._stage)
        cache = existing["cache"] if existing and existing["cache"] != "bypass" else self._cache
        self._timer.record(self._stage, elapsed_ms, cache)

    def cache(self, disposition: str) -> None:
        self._cache = disposition


def score_vector(markdown: str) -> tuple[list[tuple[str, float]], int]:
    """Every registration's non-zero detection score for this document.

    Sourced from `parser_registry.detection_report`, i.e. a second detect
    sweep. That is admissible where re-calling `resolve()` was not, because
    `detect` is pure and total by the R-3 protocol contract: re-running it over
    the same markdown provably reproduces the run of record, while `resolve`
    would re-execute parsers and describe a re-enactment.

    Measured cost: 1.8-11.7 ms per document across the corpus layout range,
    against seconds of OCR. Zeros are dropped — a zero means "no evidence", is
    identical for every registration that has it, and is reconstructible as
    "every registration not listed" from `registration_count`.
    """
    from analysis import parser_registry_entries  # noqa: F401  (registers all parsers)
    from analysis.parser_registry import detection_report, registrations

    scored = [
        (parser_id, round(detection.score, 6))
        for parser_id, detection in detection_report(markdown)
        if detection.score > 0.0
    ]
    return scored, len(registrations())
