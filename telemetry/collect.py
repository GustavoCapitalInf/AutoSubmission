"""Collectors: the pipeline callback, stage timing, the score vector, and the
one reconstruction the record is allowed to make from it.

The one seam into `analysis/` is `DispatchCollector`, passed as
`analyze_markdown(..., on_dispatch=collector)`. Its contract with the pipeline
is **it must not raise and must not mutate** — `analysis/pipeline.py`
deliberately has no `try/except` around the call, because swallowing exceptions
inside a protected module would be new control flow there to cover a defect
here. So the guarantee lives on this side, and a test proves it holds even when
handed nonsense.

`reconstructed_claim` is the other direction: what can be said about routing
when there was no callback to collect, because the analysis was served from
the D-3 cache. It lives here, beside `score_vector`, because it reads the same
sweep and the same registry — and it lives in ONE place because two consumers
need the identical answer: `record.dispatch_section` (the H-3 record) and
`discovery.runner._project_identity` (the `rows.csv` row). A second derivation
would let the two artifacts of one run disagree about the same document.
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


#: A `model_used` this suffix identifies a payload a REGISTRY parser produced.
#: Not a new fact: `analysis/pipeline.py` builds it on the deterministic branch
#: only, and `record.model_calls_for` already reads exactly this suffix to mean
#: "no model call was made". Both readings are the same claim — that no LLM
#: touched this payload — so they are pinned to one constant rather than two
#: string literals that could drift apart.
DETERMINISTIC_MODEL_SUFFIX = "-deterministic"


def sole_surviving_claimant(scores) -> tuple[str, float] | None:
    """`(parser_id, score)` when this document's detection implies exactly one
    claimant after `supersedes` pruning, else `None`.

    This is `parser_registry._surviving_claimants` re-expressed over a score
    vector that has already been computed, and it is exact rather than
    approximate for three reasons that are worth stating because the whole
    reconstruction rests on them:

    * `scores` is `score_vector`, i.e. `detection_report`, i.e. the same
      `safe_detect` sweep over the same `PreparedDocument` that `resolve`
      runs. `detect` is pure and total by the R-3 protocol contract, which is
      the argument `score_vector`'s own docstring already makes: re-running it
      over the same markdown provably reproduces the run of record.
    * `Detection.claims` is `score >= CLAIM_THRESHOLD`, and every score the
      registry can produce is already six-decimal exact (`round(..., 6)`, or
      the literals `0.5` / `1.0`), so `score_vector`'s rounding is the identity
      here and cannot move a registration across the threshold. `score_vector`
      drops zeros only, and a claimant is never a zero.
    * `supersedes` pruning is computed over ALL claimants before pruning,
      exactly as `_surviving_claimants` does.

    Reading the registry (ids and `supersedes` edges) is reading OUR constants,
    the same admissibility `discovery.evidence.registration_labels` relies on.

    Moved here from `discovery/runner.py` (§DISCOBS DO2) when the H-3 record
    became the second consumer: the row and the record must name the same
    parser for the same document, and the cheapest way to guarantee that is
    for there to be only one function that can name one.
    """
    from analysis import parser_registry_entries  # noqa: F401  (registers all parsers)
    from analysis.parser_registry import CLAIM_THRESHOLD, registrations

    superseded_by = {reg.id: reg.supersedes for reg in registrations()}
    claimants = [
        (parser_id, score) for parser_id, score in scores
        if score >= CLAIM_THRESHOLD and parser_id in superseded_by
    ]
    dominated = {
        target for parser_id, _score in claimants for target in superseded_by[parser_id]
    }
    survivors = [
        (parser_id, score) for parser_id, score in claimants if parser_id not in dominated
    ]
    return survivors[0] if len(survivors) == 1 else None


def reconstructed_claim(scores, payload: dict | None) -> tuple[str, float] | None:
    """The parser behind a payload no `Dispatch` was observed for, or `None`.

    WHEN THIS IS ASKED. On a D-3 analysis cache hit `analyze_markdown` never
    runs, so no callback fires and there is no `Dispatch` — while the payload,
    and therefore the outcome, is served in full. Before §DISCOBS the row and
    the record both answered "nothing known" there; the row stopped doing so in
    batch 5, and the record stops doing so here.

    WHY ONE DETECTION SWEEP NAMES THE PARSER. A payload produced by a registry
    parser is itself the evidence that `resolve` had exactly one survivor:
    every other outcome raises before a payload exists (`ambiguous` ->
    AmbiguousParserError, `parser_exception` -> ParserCrashError, `unclaimed`
    -> the deterministic branch's RuntimeError), and `resolve` declares
    `ambiguous` BEFORE any parse runs. So the survivor is the parser of record,
    `attempted` was empty, and the outcome was `claimed`. Nothing is guessed.

    FAIL-CLOSED, THREE TIMES, and the first guard is why this is not just
    `sole_surviving_claimant`:

    1. **The payload must be a deterministic parser's.** The discovery runner
       could rely on `parse_mode="deterministic"` for this; the H-3 record
       cannot, because `batch.py` and the webapp worker run `parse_mode="auto"`
       where a payload can come from LLM extraction with no parser behind it at
       all. `model_used` ending in `-deterministic` is the pipeline's own mark
       for "no model produced this" (`model_calls_for` reads it for cost), so
       an LLM payload reconstructs nothing.
    2. **Not the generic structurer** (W3-3c, opt-in, off), the one branch that
       publishes a payload with no parser behind it. Its `model_used` carries
       the same suffix, so it is excluded by name — its own constant, not a
       string here.
    3. **Not a sweep that names anything other than exactly one survivor.**
       Zero or many, while a payload exists, means the invariant above was
       broken by a stale artifact (the REGFP window: a registry composition
       changed under a warm cache without a stage bump). That is a finding, and
       the answer is to name nobody rather than to pick.

    WHAT IT DOES NOT CATCH, stated plainly. Inside that same REGFP window a
    cached payload may have been authored by a parser that TODAY loses a
    `supersedes` contest; today's sweep then names one survivor, the new
    winner, confidently and wrongly. One survivor is not a symptom, so no guard
    here fires. That is a stale-cache corruption this reconstruction INHERITS,
    not one it creates — before it, the same warm run served the same payload
    and published the same outcome with no parser named at all — and the
    structural fix is the REGFP card (the registry fingerprint in the analysis
    cache key), not a guess here.

    NEVER reconstructed: `attempted` (proven empty by the argument above) and
    `exceptions` (a detect-stage crash in some other registration scores 0.0
    and 0.0 is dropped, so it is not recoverable from a score vector; the field
    stays empty and says nothing rather than saying "no parser crashed").
    """
    from analysis.structurer import STRUCTURER_MODEL

    # Guarded on the type, not on the caller's word — `score_vector`'s rule,
    # for the same reason: this runs inside emit paths that swallow their own
    # exceptions (I4), so a caller that hands over something that is not a
    # serialized payload must reconstruct nothing rather than cost a record.
    model_used = payload.get("model_used") if isinstance(payload, dict) else None
    model_used = model_used if isinstance(model_used, str) else ""
    if not model_used.endswith(DETERMINISTIC_MODEL_SUFFIX):
        return None
    if model_used == STRUCTURER_MODEL:
        return None
    return sole_surviving_claimant(scores)
