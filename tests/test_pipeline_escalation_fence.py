"""P22-FENCE (Phase 2.2 cell F; ruling R9; Ruling A in code) — CHARACTERISATION.

THIS FILE, AS COMMITTED FIRST, DOCUMENTS THE BEHAVIOUR THAT IS ABOUT TO BE
REMOVED. Every test below PASSES at the cell's base (`train12` `b23cb50`, code
tree `4f7d798`) and each one names an edge the doctrine forbids:

* **Edge 1 — the selection.** `analysis/pipeline.py`'s escalation block runs a
  SECOND hosted extraction with `settings.escalation_model` whenever the first
  fails reconciliation, reconciles the alternate, and "prefer[s] whichever
  extraction's summary reconciles, falling back to fewer overall issues"
  (`REPO_VALIDATOR_MEMO.md` §9 row 8). That is the exact pattern Gustavo's R9
  forbids: "multiple extractions -> compare financial reconciliation -> prefer
  whichever extraction reconciles". The test reproduces it on a fake extractor
  whose PRIMARY fails and whose ALTERNATE reconciles: the base adopts the
  alternate (`model_used == settings.escalation_model`, `escalated is True`,
  two calls).
* **Edge 2 — the Class-B -> hosted hop.** In the webapp's default
  `parse_mode="auto"`, a dispatch that is `unclaimed`, `parser_exception` or
  `ambiguous` falls through to `extract_statement` with NO opt-in of any kind
  in the environment — the hop Ruling A refused as doctrine ("No 'parser
  failure -> hosted model' hop"). Three tests reproduce it, one per outcome;
  the card names the first two and the third reaches the SAME call site.

The fix commit that follows inverts these tests in place (the alternate is
NEVER adopted; the second call NEVER happens; the hop requires the exact
opt-in literal) and adds the tripwires. The docstrings are rewritten there;
until then, read every assertion here as "this is what the base does", not as
"this is what is wanted".

Hygiene: no network (the extractor is a monkeypatched fake at the
`analysis.pipeline` import site); `GEMINI_API_KEY` is asserted absent; every
fixture is synthetic furniture with invented figures and dates in 2054.
"""
from __future__ import annotations

import os

import pytest

from analysis import parser_registry as pr
from analysis import pipeline
from analysis.config import Settings
from analysis.schema import Statement, Transaction

#: The name of the opt-in variable the fix commit will introduce. Spelled here
#: only to prove it is ABSENT while the base behaviour is characterised: the
#: base reaches the hosted extractor with nothing set at all.
_OPT_IN_ENV = "HOSTED_EXTRACTION_OPT_IN"

#: A document NO registration claims — the shape `tests/test_q3_native_only.py`
#: already uses for the same purpose.
UNCLAIMED_MARKDOWN = (
    "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
    "\n\n--- Page 1 ---\ncompletely unrecognisable text, no template furniture\n"
)

#: Documents claimed only by the synthetic registrations registered below,
#: for exactly the duration of one test.
CRASHING_MARKDOWN = (
    "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
    "\n\n--- Page 1 ---\nP22FENCE SYNTHETIC CRASHING REGISTRATION PROBE\n"
)
AMBIGUOUS_MARKDOWN = (
    "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
    "\n\n--- Page 1 ---\nP22FENCE SYNTHETIC AMBIGUOUS REGISTRATION PROBE\n"
)


def _statement(amount: float) -> Statement:
    """One posting of `amount` between a 1,000.00 opening and a 1,500.00
    closing, no stated totals. `reconcile`'s only check that can fire is the
    sum identity (`ok = not issues`; `summary_ok` stays `None` without stated
    totals), so `amount == 500.0` reconciles and anything else does not."""
    return Statement(
        bank=None,
        period_start="2054-01-01",
        period_end="2054-01-31",
        beginning_balance=1000.00,
        ending_balance=1500.00,
        transactions=[Transaction(
            date="2054-01-05",
            description="A POSTING",
            amount=amount,
            direction="credit",
        )],
    )


def _failing_statement() -> Statement:
    return _statement(100.00)


def _reconciling_statement() -> Statement:
    return _statement(500.00)


class _FakeExtractor:
    """Stands in for `analysis.pipeline.extract_statement` and COUNTS: `calls`
    is the list of `model=` arguments in call order. `by_model` maps a model
    name to a factory so every call returns a fresh Statement."""

    def __init__(self, by_model):
        self.by_model = by_model
        self.calls: list[str | None] = []

    def __call__(self, markdown, *, settings=None, model=None):
        self.calls.append(model)
        return self.by_model[model]()


def _settings() -> Settings:
    """Two DIFFERENT model names, so the base's `escalation_model != model`
    clause is satisfied and the selection edge is reachable."""
    return Settings(api_key="", model="model-a", escalation_model="model-b")


@pytest.fixture
def clean_environment(monkeypatch):
    """No hosted key, no opt-in of any kind: the base is characterised with
    the environment an ordinary webapp process has."""
    assert "GEMINI_API_KEY" not in os.environ, "GEMINI_API_KEY must never be set"
    monkeypatch.delenv(_OPT_IN_ENV, raising=False)
    monkeypatch.delenv("GENERIC_STRUCTURER_ENABLED", raising=False)


# ---------------------------------------------------------------------------
# Edge 1 — the reconciliation-based selection between two hosted extractions
# ---------------------------------------------------------------------------


def test_characterisation_base_adopts_the_alternate_extraction_that_reconciles(
    clean_environment, monkeypatch,
):
    """CHARACTERISATION OF THE REMOVED BEHAVIOUR (R9). At base, an unclaimed
    document in auto mode is extracted with `settings.model`; because that
    result fails reconciliation, the base extracts AGAIN with
    `settings.escalation_model`, reconciles that too, and ADOPTS the alternate
    because its reconciliation passed. Two hosted calls; the report says the
    escalation model produced it and `escalated is True`."""
    fake = _FakeExtractor({
        "model-a": _failing_statement,
        "model-b": _reconciling_statement,
    })
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()

    report = pipeline.analyze_markdown(
        UNCLAIMED_MARKDOWN, parse_mode="auto", settings=settings,
    )

    assert fake.calls == [settings.model, settings.escalation_model]
    assert report.model_used == settings.escalation_model
    assert report.escalated is True
    assert report.reconciliation.ok is True
    assert [t.amount for t in report.statement.transactions] == [500.00]


# ---------------------------------------------------------------------------
# Edge 2 — the auto-mode Class-B -> hosted hop, one test per dispatch outcome
# ---------------------------------------------------------------------------


def test_characterisation_base_auto_mode_unclaimed_reaches_the_hosted_extractor_with_no_opt_in(
    clean_environment, monkeypatch,
):
    """CHARACTERISATION (Ruling A's refused edge). Nothing claims the
    document; nothing in the environment opts in; the base calls the hosted
    extractor anyway, once, with `settings.model`."""
    fake = _FakeExtractor({"model-a": _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()

    report = pipeline.analyze_markdown(
        UNCLAIMED_MARKDOWN, parse_mode="auto", settings=settings,
    )

    assert fake.calls == [settings.model]
    assert report.model_used == settings.model
    assert report.escalated is False


def test_characterisation_base_auto_mode_parser_exception_reaches_the_hosted_extractor(
    clean_environment, monkeypatch,
):
    """CHARACTERISATION. A registration WE have crashes on the document
    (`dispatch.outcome == "parser_exception"`); deterministic mode raises
    `ParserCrashError`; the base's auto mode instead hops to the hosted
    extractor and carries the crash as the `parser_exception` review flag."""
    def explode(markdown: str):
        raise AttributeError("synthetic crash")

    registration = pr.register(pr.Registration(
        id="_p22fence_synthetic_crash",
        bank="P22FENCE Synthetic Crash",
        markers=(pr.required(
            "probe", lambda t: "P22FENCE SYNTHETIC CRASHING REGISTRATION PROBE" in t,
        ),),
        parse=explode,
    ))
    fake = _FakeExtractor({"model-a": _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()
    try:
        with pytest.raises(pr.ParserCrashError):
            pipeline.analyze_markdown(
                CRASHING_MARKDOWN, parse_mode="deterministic", settings=settings,
            )
        assert fake.calls == []
        report = pipeline.analyze_markdown(
            CRASHING_MARKDOWN, parse_mode="auto", settings=settings,
        )
    finally:
        pr._REGISTRY.pop(registration.id, None)

    assert fake.calls == [settings.model]
    assert "parser_exception" in report.integrity.flags
    assert report.escalated is False


def test_characterisation_base_auto_mode_ambiguous_reaches_the_hosted_extractor(
    clean_environment, monkeypatch,
):
    """CHARACTERISATION. Two registrations claim the document
    (`dispatch.outcome == "ambiguous"`); deterministic mode raises
    `AmbiguousParserError`; the base's auto mode hops to the hosted extractor
    and carries the ambiguity as the `parser_ambiguous` review flag. The card
    enumerates `unclaimed` and `parser_exception`; this outcome reaches the
    SAME call site and is recorded here so the fence's scope is measured, not
    assumed."""
    def never_reached(markdown: str):
        raise AssertionError("an ambiguous dispatch parses nothing")

    ids = ("_p22fence_synthetic_ambiguous_a", "_p22fence_synthetic_ambiguous_b")
    registered = [pr.register(pr.Registration(
        id=identifier,
        bank=f"P22FENCE Synthetic Ambiguous {identifier[-1].upper()}",
        markers=(pr.required(
            "probe", lambda t: "P22FENCE SYNTHETIC AMBIGUOUS REGISTRATION PROBE" in t,
        ),),
        parse=never_reached,
    )) for identifier in ids]
    fake = _FakeExtractor({"model-a": _reconciling_statement})
    monkeypatch.setattr(pipeline, "extract_statement", fake)
    settings = _settings()
    try:
        with pytest.raises(pr.AmbiguousParserError):
            pipeline.analyze_markdown(
                AMBIGUOUS_MARKDOWN, parse_mode="deterministic", settings=settings,
            )
        assert fake.calls == []
        report = pipeline.analyze_markdown(
            AMBIGUOUS_MARKDOWN, parse_mode="auto", settings=settings,
        )
    finally:
        for registration in registered:
            pr._REGISTRY.pop(registration.id, None)

    assert fake.calls == [settings.model]
    assert "parser_ambiguous" in report.integrity.flags
    assert report.escalated is False
