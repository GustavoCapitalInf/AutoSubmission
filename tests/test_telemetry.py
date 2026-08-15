"""H-3 telemetry: the record, the seam, the sinks, and the invariants.

The corpus-wide anchor lives in `test_telemetry_corpus.py` (corpus-marked).
Everything here is fast and runs by default.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from telemetry import (
    DEFERRED_REASONS,
    DISABLE_ENV,
    DispatchCollector,
    JsonlSink,
    NullSink,
    OUTCOME_CLASSES,
    SCORE_CAP,
    StageTimer,
    TOP_LEVEL_KEYS,
    build_record,
    classify_outcome,
    dispatch_section,
    document_section,
    new_run_id,
    open_jsonl_sink,
    open_sqlite_sink,
    read_jsonl,
    score_vector,
    source_path_for,
    source_section,
)
from telemetry.prices import PRICE_TABLE_VERSION, estimate
from telemetry.record import model_calls_for
from telemetry.report import render, summarize

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def claimed_markdown() -> str:
    """A real corpus document a deterministic parser claims.

    The seam tests need a document that resolves without an LLM: a synthetic
    stub falls through to extraction and would need an API key.
    """
    from ocr.native_text import parse_native_pdf_text

    source = ROOT / "Bank Statements" / "Chase" / "Chase Mar.pdf"
    document = parse_native_pdf_text(source.read_bytes(), source_file=source.name)
    assert document is not None
    return document.to_markdown()


def _record(**overrides) -> dict:
    base = dict(
        run_id="run-1",
        emitter="batch",
        document=document_section("A" * 64, 1234, None),
        source=source_section(None),
        dispatch=dispatch_section(None, [], 46, source="unavailable"),
        stages={"analysis": {"ms": 1.0, "cache": "miss"}},
        model_calls=[],
        payload=None,
    )
    base.update(overrides)
    return build_record(**base)


# --- the record shape -------------------------------------------------------


def test_record_has_exactly_the_declared_top_level_keys():
    assert set(_record()) == set(TOP_LEVEL_KEYS)


def test_source_path_is_derived_from_the_document_model():
    assert source_path_for("native-pdf-text") == "native"
    assert source_path_for("native-pdf-text+navy-federal-layout") == "native"
    assert source_path_for("local-tesseract-ocr") == "local_tesseract"
    assert source_path_for("deterministic-native-preflight") == "none"
    assert source_path_for("qwen2.5-vl-7b") == "visual"
    assert source_path_for(None) == "none"


def test_truncation_distinguishes_not_assessed_from_clean():
    class _Doc:
        model = "native-pdf-text"
        pages = ["a"]
        page_integrity = []

    section = source_section(_Doc())
    assert section["truncation"]["assessed"] is False
    assert section["truncation"]["truncated_page_count"] == 0


def test_truncation_reports_indices_and_signals():
    from ocr.truncation import PageIntegrity

    class _Doc:
        model = "local-tesseract-ocr"
        pages = ["a", "b", "c"]
        page_integrity = [
            PageIntegrity(page_index=0),
            PageIntegrity(page_index=1, truncated=True, signals=["open_table_at_tail"]),
            PageIntegrity(page_index=2, truncated=True, signals=["open_row_at_tail"]),
        ]

    truncation = source_section(_Doc())["truncation"]
    assert truncation == {
        "assessed": True,
        "truncated_page_count": 2,
        "truncated_page_indices": [1, 2],
        "signals": ["open_row_at_tail", "open_table_at_tail"],
    }


# --- outcome classification -------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (None, ("failed", "no_analysis")),
        ({"metrics": {"average_daily_balance": None}}, ("withheld", "withheld_adb")),
        (
            {"metrics": {"average_daily_balance": 1.0},
             "integrity": {"flags": ["parser_ambiguous"]}},
            ("review", "parser_ambiguous"),
        ),
        (
            {"metrics": {"average_daily_balance": 1.0},
             "integrity": {"flags": ["missing_declared_statement_page"]}},
            ("review", "integrity_flags"),
        ),
        (
            {"metrics": {"average_daily_balance": 1.0},
             "quality": {"corporate_use": "manual_review_required"}},
            ("review", "quality_needs_review"),
        ),
        (
            {"metrics": {"average_daily_balance": 1.0},
             "quality": {"corporate_use": "approved"}},
            ("validated", "approved"),
        ),
    ],
)
def test_outcome_classification(payload, expected):
    assert classify_outcome(payload) == expected


def test_deferral_is_declared_never_inferred():
    """`deferred` outranks everything, but only on an explicit declaration.

    Inferring it from an absent payload would let a genuine failure hide as a
    decision, which is the one thing this class must not do.
    """
    assert classify_outcome(None) == ("failed", "no_analysis")
    assert classify_outcome(None, deferred="deferred_scanned") == (
        "deferred", "deferred_scanned"
    )
    # It outranks a payload that would otherwise classify.
    approved = {"metrics": {"average_daily_balance": 1.0},
                "quality": {"corporate_use": "approved"}}
    assert classify_outcome(approved, deferred="profile_only")[0] == "deferred"
    assert "deferred" in OUTCOME_CLASSES


def test_an_unknown_deferral_reason_is_refused():
    """The vocabulary is closed: a typo must not become a new bucket."""
    with pytest.raises(ValueError, match="unknown deferral reason"):
        classify_outcome(None, deferred="because_i_said_so")
    for reason in DEFERRED_REASONS:
        assert classify_outcome(None, deferred=reason) == ("deferred", reason)


def test_a_deferred_record_names_no_error():
    record = _record(deferred="deferred_scanned")
    assert record["outcome"]["class"] == "deferred"
    assert record["outcome"]["reason"] == "deferred_scanned"
    assert record["outcome"]["error_type"] is None


def test_withheld_outranks_review():
    """A withheld value is not merely 'needs review' — it is a refusal."""
    payload = {
        "metrics": {"average_daily_balance": None},
        "quality": {"corporate_use": "manual_review_required"},
        "integrity": {"flags": ["ledger_sum_mismatch"]},
    }
    assert classify_outcome(payload)[0] == "withheld"


# --- the pipeline seam ------------------------------------------------------


def test_the_callback_does_not_change_the_report():
    """The whole side-band claim, on a real parse."""
    without = report_to_dict(analyze_markdown(claimed_markdown(), parse_mode="deterministic"))
    collector = DispatchCollector()
    with_callback = report_to_dict(
        analyze_markdown(claimed_markdown(), parse_mode="deterministic", on_dispatch=collector)
    )
    assert json.dumps(with_callback, sort_keys=True) == json.dumps(without, sort_keys=True)
    assert collector.calls == 1


def test_the_collector_never_raises_whatever_it_is_handed():
    """The pipeline has no try/except around on_dispatch; this is why."""
    collector = DispatchCollector()
    for value in (None, object(), 42, "not-a-dispatch"):
        collector(value)
    assert collector.calls == 4
    assert collector.errors == 0


def test_a_collector_sees_the_dispatch_of_record():
    collector = DispatchCollector()
    analyze_markdown(claimed_markdown(), parse_mode="deterministic", on_dispatch=collector)
    assert collector.seen
    assert collector.dispatch.outcome in {"claimed", "ambiguous", "unclaimed"}


def test_dispatch_section_never_carries_the_parsed_statement():
    """Dispatch.statement is the full financial record; it must not be projected."""
    collector = DispatchCollector()
    analyze_markdown(claimed_markdown(), parse_mode="deterministic", on_dispatch=collector)
    section = dispatch_section(collector.dispatch, [], 46, source="live")
    assert set(section) == {
        "source", "outcome", "parser_id", "score", "candidates", "attempted",
        "exceptions", "scores", "scores_floor", "scores_capped", "registration_count",
    }
    assert "statement" not in json.dumps(section)


# --- parser crashes (W3-1) --------------------------------------------------


def test_dispatch_section_projects_parser_failures_by_class_name_only():
    """The crash facts survive into telemetry; the message never does.

    Before the W3-1 boundary a crash escaped `resolve`, no Dispatch existed,
    and the record carried one anonymous `outcome.error_type` for the whole
    document. These three fields are what make a crash cluster countable.
    """
    from analysis.parser_registry import Dispatch, ParserFailure

    dispatch = Dispatch(
        "parser_exception",
        exceptions=(
            ParserFailure("us_bank", "parse", "AttributeError"),
            ParserFailure("bank_of_america", "detect", "ValueError"),
        ),
    )
    section = dispatch_section(dispatch, [], 46, source="live")

    assert section["outcome"] == "parser_exception"
    assert section["exceptions"] == [
        ["us_bank", "parse", "AttributeError"],
        ["bank_of_america", "detect", "ValueError"],
    ]
    assert section["parser_id"] is None


def test_a_dispatch_without_exceptions_reports_an_empty_list():
    collector = DispatchCollector()
    analyze_markdown(claimed_markdown(), parse_mode="deterministic", on_dispatch=collector)
    assert dispatch_section(collector.dispatch, [], 46, source="live")["exceptions"] == []


def test_a_crash_flag_is_classified_as_review_with_its_own_reason():
    """`integrity_flags` would fold the crash into the anonymous bucket."""
    payload = {
        "metrics": {"average_daily_balance": 1000.0},
        "quality": {"corporate_use": "manual_review_required"},
        "integrity": {"flags": ["parser_exception"]},
    }
    assert classify_outcome(payload) == ("review", "parser_exception")


# --- the near-miss vector ---------------------------------------------------


def test_score_vector_drops_zeros_and_sorts_best_first():
    scores, registrations = score_vector(claimed_markdown())
    assert registrations >= 43
    assert scores, "a Chase statement must score above zero somewhere"
    assert all(score > 0 for _, score in scores)
    assert [score for _, score in scores] == sorted((s for _, s in scores), reverse=True)
    assert len(scores) < registrations, "zeros must not be recorded"


def test_score_vector_is_capped_and_says_so():
    long_vector = [(f"p{i}", 1.0 - i / 100) for i in range(SCORE_CAP + 5)]
    section = dispatch_section(None, long_vector, 46, source="live")
    assert len(section["scores"]) == SCORE_CAP
    assert section["scores_capped"] is True
    assert dispatch_section(None, long_vector[:2], 46, source="live")["scores_capped"] is False


# --- the double sweep: the near-miss vector reuses the analysis sweep -------
#
# `analyze_markdown` sweeps the registry to route the document and this module
# sweeps it again to record what nearly claimed it. The second sweep is
# admissible because `detect` is pure — but purity made it correct, not free,
# and it was re-preparing text the first sweep had just produced (#PREPHAND).


def _analysed_collector() -> DispatchCollector:
    collector = DispatchCollector()
    analyze_markdown(claimed_markdown(), parse_mode="deterministic", on_dispatch=collector)
    return collector


def test_the_collector_publishes_the_preparation_the_analysis_swept():
    collector = _analysed_collector()
    from analysis.parser_registry import PreparedDocument, admissible_text

    assert isinstance(collector.prepared, PreparedDocument)
    assert collector.prepared.admissible == admissible_text(claimed_markdown())
    assert collector.prepared.preparations > 1, (
        "the real registry normalizes; a document that cost one preparation "
        "would make the reuse assertions vacuous"
    )


def test_the_near_miss_sweep_prepares_nothing_when_given_the_collector(monkeypatch):
    """The handoff, in operations: no second preparation of any text."""
    from analysis import parser_registry as pr

    collector = _analysed_collector()
    swept = collector.prepared.preparations

    prepares: list[str] = []
    real = pr.prepare
    monkeypatch.setattr(pr, "prepare", lambda md: prepares.append(md) or real(md))

    scores, registrations = score_vector(claimed_markdown(), collector)

    assert prepares == [], "the near-miss sweep prepared the document a second time"
    assert collector.prepared.preparations == swept, (
        "the near-miss sweep re-ran a normalization the analysis had already run"
    )
    assert scores and registrations >= 43


def test_the_near_miss_vector_is_identical_with_and_without_the_collector():
    """The equivalence the reuse has to earn, on a real claimed document."""
    assert score_vector(claimed_markdown(), _analysed_collector()) == score_vector(
        claimed_markdown()
    )


def test_a_collector_from_another_document_is_ignored():
    """The guard, and the proof it is not vacuous: the foreign preparation
    really would have produced a different vector."""
    from analysis.parser_registry import prepare, resolve

    foreign_text = "<!-- SOURCE: x.pdf -->\nnothing any parser here has heard of"
    foreign = DispatchCollector()
    foreign(resolve(prepare(foreign_text)))
    assert foreign.prepared is not None

    assert score_vector(foreign_text)[0] != score_vector(claimed_markdown())[0]
    assert score_vector(claimed_markdown(), foreign) == score_vector(claimed_markdown())


def test_a_str_subclass_cannot_talk_its_way_into_another_documents_preparation():
    """The `Sticky` hazard `PreparedDocument.text_for` documents, one level out.

    A `str` subclass that compares equal to everything would pass a naive
    guard and be handed a foreign document's prepared texts — a near-miss
    vector describing the wrong document. It cannot: both sides of the
    comparison are values `admissible_text` returned, and `re.sub` produces an
    exact `str` whatever it was given.
    """
    from analysis.parser_registry import prepare, resolve

    class Sticky(str):
        def __eq__(self, other):
            return True

        def __hash__(self):
            return 0

    foreign = DispatchCollector()
    foreign(resolve(prepare("<!-- SOURCE: x.pdf -->\nnothing any parser here has heard of")))

    assert score_vector(Sticky(claimed_markdown()), foreign) == score_vector(claimed_markdown())


def test_a_collector_that_never_saw_a_dispatch_is_ignored():
    """The D-3 analysis cache hit: nothing dispatched, so nothing to reuse."""
    assert score_vector(claimed_markdown(), DispatchCollector()) == score_vector(
        claimed_markdown()
    )


def test_the_collector_offers_no_preparation_when_handed_nonsense():
    """The collector's contract is that it keeps what it was given; reading a
    preparation off it must not become a new way for telemetry to raise."""
    collector = DispatchCollector()
    for value in (None, object(), 42, "not-a-dispatch"):
        collector(value)
        assert collector.prepared is None
    assert collector.errors == 0


# --- cost -------------------------------------------------------------------


def test_unpriced_model_is_named_never_guessed():
    cost = estimate([
        {"model": "some-hosted-vlm", "purpose": "visual_ocr", "calls": 3,
         "prompt_tokens": None, "completion_tokens": 900},
    ])
    assert cost["amount"] is None
    assert cost["complete"] is False
    assert cost["unpriced_models"] == ["some-hosted-vlm"]
    assert cost["price_table_version"] == PRICE_TABLE_VERSION


def test_a_priced_model_costs_exact_arithmetic(monkeypatch):
    from telemetry import prices

    monkeypatch.setitem(prices.PRICES, "priced-model", (2.0, 4.0))
    cost = prices.estimate([
        {"model": "priced-model", "purpose": "extraction", "calls": 1,
         "prompt_tokens": 1000, "completion_tokens": 500},
    ])
    assert cost["amount"] == pytest.approx(2.0 + 2.0)
    assert cost["complete"] is True


def test_local_paths_cost_nothing_and_that_is_a_fact_not_an_unknown():
    cost = estimate([
        {"model": "local-tesseract-ocr", "purpose": "local_tesseract", "calls": 1,
         "prompt_tokens": None, "completion_tokens": None},
    ])
    assert cost["amount"] == 0.0
    assert cost["complete"] is True


def test_model_calls_count_extraction_escalation():
    payload = {"model_used": "gemini-flash", "escalated": True}
    calls = model_calls_for(None, payload)
    assert calls == [{
        "stage": "analysis", "model": "gemini-flash", "purpose": "extraction",
        "calls": 2, "prompt_tokens": None, "completion_tokens": None,
    }]
    assert model_calls_for(None, {"model_used": "chase-deterministic"}) == []


# --- sinks and storage ------------------------------------------------------


def test_jsonl_sink_appends_and_reads_back(tmp_path):
    sink = JsonlSink(tmp_path / "run.jsonl")
    first, second = _record(), _record()
    sink.write(first)
    sink.write(second)
    records = read_jsonl(tmp_path / "run.jsonl")
    assert [r["record_id"] for r in records] == [first["record_id"], second["record_id"]]


def test_a_sink_failure_is_swallowed(tmp_path):
    sink = JsonlSink(tmp_path / "run.jsonl")
    sink.write({"not": "a record", "unserialisable": object()})
    assert sink.failures == 1
    assert sink.written == 0


def test_kill_switch_swaps_in_the_null_sink(monkeypatch, tmp_path):
    monkeypatch.setenv(DISABLE_ENV, "1")
    assert isinstance(open_jsonl_sink(tmp_path / "x.jsonl", "run"), NullSink)
    assert isinstance(open_sqlite_sink(object()), NullSink)
    monkeypatch.setenv(DISABLE_ENV, "0")
    assert isinstance(open_jsonl_sink(tmp_path / "x.jsonl", "run"), JsonlSink)


def test_telemetry_is_on_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv(DISABLE_ENV, raising=False)
    assert isinstance(open_jsonl_sink(tmp_path / "x.jsonl", "run"), JsonlSink)


def test_storage_v4_is_additive_and_append_only(tmp_path):
    from webapp.storage import SCHEMA_VERSION, Storage

    store = Storage(tmp_path)
    assert store.schema_version() == SCHEMA_VERSION == 4
    store.create_job("j1", filename="f.pdf")
    record = _record(job_id="j1")
    store.append_telemetry(record)
    store.append_telemetry(record)  # idempotent on record_id
    assert len(store.telemetry_records()) == 1

    db = next(tmp_path.rglob("*.db"))
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM telemetry")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE telemetry SET run_id = 'x'")


def test_sqlite_columns_are_projections_of_the_record(tmp_path):
    from webapp.storage import Storage

    store = Storage(tmp_path)
    record = _record(
        dispatch=dispatch_section(None, [("chase", 0.5)], 46, source="cached"),
        payload={"metrics": {"average_daily_balance": 1.0},
                 "quality": {"corporate_use": "approved"}},
    )
    store.append_telemetry(record)
    stored = store.telemetry_records()[0]
    assert stored == record

    db = next(tmp_path.rglob("*.db"))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM telemetry").fetchone()
    assert row["content_sha256"] == record["document"]["content_sha256"]
    assert row["outcome_class"] == record["outcome"]["class"]
    assert row["source_path"] == record["source"]["path"]
    assert row["run_id"] == record["run_id"]
    assert json.loads(row["record"]) == record


# --- the coverage command ---------------------------------------------------


def _corpus_like_records() -> list[dict]:
    approved = {"metrics": {"average_daily_balance": 1.0},
                "quality": {"corporate_use": "approved"}}
    withheld = {"metrics": {"average_daily_balance": None}}
    records = []
    for _ in range(3):
        records.append(_record(
            payload=approved,
            dispatch=dispatch_section(None, [], 46, source="live") | {"outcome": "claimed",
                                                                     "parser_id": "chase"},
        ))
    records.append(_record(
        payload=withheld,
        dispatch=dispatch_section(None, [], 46, source="live") | {"outcome": "unclaimed"},
    ))
    return records


def test_coverage_summary_counts_what_it_says(tmp_path):
    summary = summarize(_corpus_like_records())
    assert summary["total"] == 4
    assert summary["dispatch"] == {"claimed": 3, "unclaimed": 1}
    assert summary["outcome"] == {"validated": 3, "withheld": 1}
    assert summary["deterministic_coverage"] == pytest.approx(0.75)
    assert "deterministic coverage" in render(summary, "run-1")


def test_jsonl_and_sqlite_report_identically(tmp_path):
    from webapp.storage import Storage

    records = _corpus_like_records()
    sink = JsonlSink(tmp_path / "run.jsonl")
    store = Storage(tmp_path / "data")
    for record in records:
        sink.write(record)
        store.append_telemetry(record)

    from_jsonl = summarize(read_jsonl(tmp_path / "run.jsonl"))
    from_sqlite = summarize(store.telemetry_records())
    assert from_jsonl == from_sqlite
    assert render(from_jsonl) == render(from_sqlite)


def test_report_cli_runs_on_a_jsonl_file(tmp_path):
    sink = JsonlSink(tmp_path / "run.jsonl")
    for record in _corpus_like_records():
        sink.write(record)
    result = subprocess.run(
        [sys.executable, "-m", "telemetry.report", "--jsonl", str(tmp_path / "run.jsonl")],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "deterministic coverage" in result.stdout


# --- structural guarantees --------------------------------------------------


def test_batch_emits_without_importing_the_webapp():
    """T12: the CLI path must not drag in Flask/SQLite plumbing."""
    code = (
        "import sys, batch, telemetry;"
        "webapp = [m for m in sys.modules if m == 'webapp' or m.startswith('webapp.')];"
        "print(webapp)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", f"batch.py pulled in {result.stdout.strip()}"


def test_run_ids_are_unique_and_sortable():
    first, second = new_run_id(), new_run_id()
    assert first != second
    assert first[:4].isdigit()
