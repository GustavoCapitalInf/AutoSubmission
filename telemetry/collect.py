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

    @property
    def prepared(self) -> Any | None:
        """The `PreparedDocument` the collected dispatch was decided on.

        `resolve` publishes the text it swept so that a second sweep over the
        same document does not have to prepare it again; `score_vector` is
        that second sweep. Read with `getattr` and never unwrapped here,
        because this class's contract is that it keeps whatever object it was
        handed — including, in
        `test_the_collector_never_raises_whatever_it_is_handed`, something
        that is not a `Dispatch` at all.
        """
        return getattr(self.dispatch, "prepared", None)


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


def score_vector(
    markdown: str, collector: DispatchCollector | None = None
) -> tuple[list[tuple[str, float]], int]:
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

    **`collector` is the first sweep's preparation, offered to the second
    (W3 #PREPHAND).** Purity is what makes the re-sweep admissible; it does
    not make it free. `PreparedDocument` (DETECT-BUDGET) reduced ONE sweep
    from 104 text preparations to 33, and the discovery run pays for two
    sweeps per document — `analyze_markdown`'s and this one — so the second
    was paying 33 preparations to recompute, character for character, texts
    the first had just produced. A caller that collected the dispatch for this
    document hands the collector over and the second sweep prepares nothing.

    The reuse is **guarded on the text, not on the caller's word**: it is
    taken only when the prepared document's admissible text IS this markdown's
    admissible text. That is precisely the soundness condition, because
    everything a `PreparedDocument` holds is a pure function of that text — so
    a prepared document that passes the guard cannot produce a different
    report than a fresh one, and one that fails it (a collector from another
    document, a cache hit that never dispatched, a visual re-read that was not
    adopted) is simply ignored and the sweep runs as before. Passing nothing
    is always correct; passing the wrong thing cannot be wrong twice.
    """
    from analysis import parser_registry_entries  # noqa: F401  (registers all parsers)
    from analysis.parser_registry import admissible_text, detection_report, registrations

    document: Any = markdown
    prepared = collector.prepared if collector is not None else None
    if prepared is not None:
        admissible = getattr(prepared, "admissible", None)
        # `is` first: the pipeline hands `resolve` a document prepared from
        # this very string, so the fast path is the production path. The
        # equality is what makes the guard sound rather than merely quick —
        # and it costs one `admissible_text`, which is one preparation
        # against the thirty-three it decides whether to skip.
        if admissible is markdown or admissible == admissible_text(markdown):
            document = prepared

    scored = [
        (parser_id, round(detection.score, 6))
        for parser_id, detection in detection_report(document)
        if detection.score > 0.0
    ]
    return scored, len(registrations())
