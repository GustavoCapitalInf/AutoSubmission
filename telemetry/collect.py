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

    **Say plainly what "nothing" means.** Reusing the preparation reuses its
    MARKER MEMO too, so the second sweep is not a cheaper sweep — it is a
    replay: measured on the largest pinned document, `Marker.test` is called
    190 times in the first sweep and **0 times** in the second, and every
    `Detection` here is assembled from values the first sweep computed. The
    paragraph above says re-running `detect` reproduces the run of record;
    with a collector, the record is reproduced by not re-running it, which is
    the same value for the same reason (`Marker.test` and the normalizers are
    pure by contract) and is worth stating rather than implying. What is NOT
    replayed is a crash: a marker that raises is never memoized, so the
    `_guarded` seam is entered on this sweep exactly as on the first — proven
    by deliberate injection over the whole archive, 2 raises per crashing
    registration per document (#PREPHAND PH5.1).

    The reuse is **guarded on the type and then on the text, not on the
    caller's word**: it is taken only from a real `PreparedDocument` whose
    admissible text IS this markdown's admissible text. Both halves are
    load-bearing. The text half is the soundness condition, because everything
    a `PreparedDocument` holds is a pure function of that text — so one that
    passes cannot produce a different report than a fresh sweep, and one that
    fails (a collector from another document, a cache hit that never
    dispatched, a visual re-read that was not adopted) is ignored and the
    sweep runs as before. The type half is what keeps the failure mode
    harmless: `detection_report` prepares anything that is not a
    `PreparedDocument`, so a duck-typed stand-in that merely compared equal
    would reach `admissible_text` as a non-string and raise — out of here,
    through `discovery/runner.py`'s one un-`try`'d call site, aborting a
    document over a telemetry detail. Passing nothing is always correct;
    passing the wrong thing is ignored.
    """
    from analysis import parser_registry_entries  # noqa: F401  (registers all parsers)
    from analysis.parser_registry import (
        PreparedDocument,
        admissible_text,
        detection_report,
        registrations,
    )

    document: Any = markdown
    prepared = collector.prepared if collector is not None else None
    if isinstance(prepared, PreparedDocument):
        # The identity check is not decoration: `re.sub` returns the string it
        # was given when it substitutes nothing, so a document carrying no
        # source comment IS its own admissible text and the guard is free. The
        # production path is the other one — the OCR and native-text layers
        # write a `<!-- SOURCE: ... -->` header on every document they
        # produce — so in the discovery run this pays one `admissible_text`
        # per document, against the thirty-four preparations it decides
        # whether to skip.
        #
        # `prepared.admissible` is whatever `admissible_text` returned, i.e.
        # an exact `str`, and so is the right-hand side; a `str` subclass
        # carrying its own `__eq__` therefore cannot talk its way into another
        # document's preparation — the hazard `PreparedDocument.text_for`
        # documents, one level out.
        admissible = prepared.admissible
        if admissible is markdown or admissible == admissible_text(markdown):
            document = prepared

    scored = [
        (parser_id, round(detection.score, 6))
        for parser_id, detection in detection_report(document)
        if detection.score > 0.0
    ]
    return scored, len(registrations())
