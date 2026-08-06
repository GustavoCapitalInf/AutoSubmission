"""Wave 2 / D-3 — content-hash artifact cache.

Two things are proven here and nothing else may substitute for them:

1. **Zero recomputation on identical bytes.** A call-counting fake stands in
   for the OCR ladder and for the analysis pipeline; re-processing the same
   PDF must leave both counters untouched. That is the hard requirement, so
   it is asserted at the worker level (the real ``run_job``), not against the
   cache primitives.
2. **Restart durability.** The store is torn down and reopened over the same
   data directory — exactly what a process restart constructs, the same
   simulation D-1 uses — and the hit must still occur.

Everything else here defends the cache KEY: each knob that changes a stage's
output must partition it, and nothing that leaves output unchanged may.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

import pytest

from ocr.document import StatementMarkdown
from ocr.truncation import PageIntegrity
from webapp.artifact_cache import (
    ANALYSIS_STAGE_VERSION,
    OCR_STAGE_VERSION,
    ArtifactCache,
    CACHE_FORMAT_VERSION,
    STAGE_ANALYSIS,
    STAGE_OCR,
    STAGE_REPORT,
    analysis_settings_key,
    cache_key,
    cached_analysis,
    cached_ocr,
    cached_report,
    content_sha256,
    ocr_settings_key,
    open_cache,
    report_settings_key,
    text_sha256,
)
from webapp.jobs import JobStore
from webapp.storage import Storage
from webapp.worker import run_job

PDF = b"%PDF-1.7\nartifact cache fixture body"
OTHER_PDF = b"%PDF-1.7\nartifact cache fixture body (different)"


@dataclass
class _OcrSettings:
    """Stand-in for ocr.config.Settings — only the keyed attributes matter."""

    model: str = "baidu/Unlimited-OCR"
    base_url: str = "http://localhost:8000/v1"
    ngram_size: int = 35
    window_size: int = 128
    max_workers: int = 1
    timeout: float = 120.0
    retries: int = 3
    api_key: str = "EMPTY"


@dataclass
class _AnalysisSettings:
    model: str = "gemini-3.5-flash-lite"
    escalation_model: str = "gemini-3.5-flash"
    withholding_denominator_mode: str = "legacy_eligible_deposits"
    api_key: str = ""


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def cache(data_dir):
    return ArtifactCache(Storage(data_dir))


def _reopen(data_dir) -> ArtifactCache:
    """A brand-new Storage + ArtifactCache over the same directory — what a
    process restart builds."""
    return ArtifactCache(Storage(data_dir))


def _doc(pages=("page one",), model="fake-ocr", source_file="s.pdf") -> StatementMarkdown:
    return StatementMarkdown(source_file=source_file, model=model, pages=list(pages))


# ---------------------------------------------------------------------------
# key composition
# ---------------------------------------------------------------------------


def test_content_hash_follows_the_established_uppercase_convention():
    import hashlib

    assert content_sha256(PDF) == hashlib.sha256(PDF).hexdigest().upper()
    assert text_sha256("abc") == hashlib.sha256(b"abc").hexdigest().upper()


def test_cache_key_joins_stage_input_and_settings():
    base = cache_key(STAGE_OCR, content_sha256(PDF), "SETTINGS")
    assert base == cache_key(STAGE_OCR, content_sha256(PDF), "SETTINGS")  # stable
    # Any one of the three components changing changes the key.
    assert base != cache_key(STAGE_ANALYSIS, content_sha256(PDF), "SETTINGS")
    assert base != cache_key(STAGE_OCR, content_sha256(OTHER_PDF), "SETTINGS")
    assert base != cache_key(STAGE_OCR, content_sha256(PDF), "OTHER")
    assert len(base) == 64 and base == base.upper()


@pytest.mark.parametrize(
    "changed",
    [
        {"force_ocr": True},
        {"allow_local_ocr": True},
        {"allow_visual_ocr": False},
        {"dpi": 200},
        {"fallback_dpi": None},
        {"ocr_settings": _OcrSettings(model="other/model")},
        {"ocr_settings": _OcrSettings(base_url="http://elsewhere/v1")},
        {"ocr_settings": _OcrSettings(ngram_size=40)},
        {"ocr_settings": _OcrSettings(window_size=256)},
    ],
)
def test_every_ocr_knob_partitions_the_key(changed):
    baseline = dict(
        force_ocr=False,
        allow_local_ocr=False,
        allow_visual_ocr=True,
        dpi=300,
        fallback_dpi=250,
        ocr_settings=_OcrSettings(),
    )
    assert ocr_settings_key(**baseline) != ocr_settings_key(**{**baseline, **changed})


def test_ocr_key_ignores_knobs_that_cannot_change_output():
    """max_workers, timeout, retries and the API key must NOT partition: page
    concurrency is documented in ocr/config.py as output-neutral, transport
    settings are not output, and a secret must never be hashed into a key that
    is written to disk."""
    base = ocr_settings_key(ocr_settings=_OcrSettings())
    for irrelevant in (
        _OcrSettings(max_workers=8),
        _OcrSettings(timeout=5.0),
        _OcrSettings(retries=9),
        _OcrSettings(api_key="a-real-secret"),
    ):
        assert ocr_settings_key(ocr_settings=irrelevant) == base


@pytest.mark.parametrize(
    "changed",
    [
        {"parse_mode": "deterministic"},
        {"analysis_settings": _AnalysisSettings(model="gemini-other")},
        {"analysis_settings": _AnalysisSettings(escalation_model="gemini-pro")},
        {"analysis_settings": _AnalysisSettings(withholding_denominator_mode="verified_revenue")},
    ],
)
def test_every_analysis_knob_partitions_the_key(changed):
    baseline = dict(parse_mode="auto", analysis_settings=_AnalysisSettings())
    assert analysis_settings_key(**baseline) != analysis_settings_key(
        **{**baseline, **changed}
    )


def test_analysis_key_ignores_the_api_key():
    assert analysis_settings_key(
        analysis_settings=_AnalysisSettings(api_key="secret")
    ) == analysis_settings_key(analysis_settings=_AnalysisSettings())


def test_report_key_partitions_on_title():
    assert report_settings_key(title="a.pdf") != report_settings_key(title="b.pdf")


# ---------------------------------------------------------------------------
# storage behavior
# ---------------------------------------------------------------------------


def test_round_trip_for_every_stage(cache):
    ocr_key = ocr_settings_key(ocr_settings=_OcrSettings())
    cache.put_ocr(content_sha256(PDF), ocr_key, _doc(pages=["one", "two"]))
    hit, document = cache.get_ocr(content_sha256(PDF), ocr_key)
    assert hit is True
    # D-3b: the stored document also carries O-3's per-page integrity records
    # (empty here — this fixture was never assessed by the ladder).
    assert document == {"model": "fake-ocr", "pages": ["one", "two"], "page_integrity": []}

    analysis_key = analysis_settings_key(analysis_settings=_AnalysisSettings())
    cache.put_analysis(text_sha256("# md"), analysis_key, {"statement": {"bank": "B"}})
    assert cache.get_analysis(text_sha256("# md"), analysis_key) == {
        "statement": {"bank": "B"}
    }

    report_key = report_settings_key(title="s.pdf")
    cache.put_report(text_sha256("# md"), report_key, "<h1>md</h1>")
    assert cache.get_report(text_sha256("# md"), report_key) == "<h1>md</h1>"


def test_miss_returns_none_without_writing_anything(cache):
    assert cache.get_ocr(content_sha256(PDF), "NOPE") == (False, None)
    assert cache.get_analysis(text_sha256("x"), "NOPE") is None
    assert cache.storage.cache_entries() == []


def test_payload_lives_on_disk_and_not_in_sqlite(cache, data_dir):
    """Large artifacts are files; SQLite holds only the index row."""
    bulky = "LEDGER-ROW " * 5000
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"markdown": bulky})

    row = cache.storage.cache_lookup(STAGE_ANALYSIS, key)
    assert row is not None
    path = cache.root / row["artifact_path"]
    assert path.is_file()
    assert bulky in path.read_text(encoding="utf-8")
    assert row["byte_size"] > 50_000
    # The database file itself never saw the payload.
    assert b"LEDGER-ROW LEDGER-ROW" not in (data_dir / "webapp.db").read_bytes()


def test_index_row_records_the_key_material_and_hits(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    row = cache.storage.cache_lookup(STAGE_ANALYSIS, key)
    assert row["input_sha256"] == text_sha256("md")
    assert row["settings_key"] == "SETTINGS"
    assert row["format_version"] == CACHE_FORMAT_VERSION
    assert row["hit_count"] == 0 and row["last_hit_at"] is None

    cache.get_analysis(text_sha256("md"), "SETTINGS")
    cache.get_analysis(text_sha256("md"), "SETTINGS")
    row = cache.storage.cache_lookup(STAGE_ANALYSIS, key)
    assert row["hit_count"] == 2 and row["last_hit_at"]


def test_stats_reports_entries_bytes_and_hits(cache):
    cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    cache.put_report(text_sha256("md"), "SETTINGS", "<p>x</p>")
    cache.get_analysis(text_sha256("md"), "SETTINGS")

    stats = cache.stats()
    assert stats[STAGE_ANALYSIS]["entries"] == 1
    assert stats[STAGE_ANALYSIS]["hits"] == 1
    assert stats[STAGE_ANALYSIS]["bytes"] > 0
    assert stats[STAGE_REPORT]["entries"] == 1
    assert stats[STAGE_REPORT]["hits"] == 0


def test_cache_survives_a_restart(data_dir):
    cache = ArtifactCache(Storage(data_dir))
    ocr_key = ocr_settings_key(ocr_settings=_OcrSettings())
    cache.put_ocr(content_sha256(PDF), ocr_key, _doc(pages=["persisted"]))
    del cache

    reopened = _reopen(data_dir)
    hit, document = reopened.get_ocr(content_sha256(PDF), ocr_key)
    assert hit is True
    assert document["pages"] == ["persisted"]


def test_a_vanished_payload_file_is_a_miss_and_self_heals(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    path = cache.root / cache.storage.cache_lookup(STAGE_ANALYSIS, key)["artifact_path"]
    path.unlink()

    assert cache.get_analysis(text_sha256("md"), "SETTINGS") is None
    # The dangling index row is dropped rather than left to miss forever.
    assert cache.storage.cache_lookup(STAGE_ANALYSIS, key) is None


def test_a_corrupt_payload_file_is_a_miss(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    path = cache.root / cache.storage.cache_lookup(STAGE_ANALYSIS, key)["artifact_path"]
    path.write_text("{not json", encoding="utf-8")

    assert cache.get_analysis(text_sha256("md"), "SETTINGS") is None
    assert cache.storage.cache_lookup(STAGE_ANALYSIS, key) is None


def test_a_payload_from_another_cache_format_is_a_miss(cache):
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    path = cache.root / cache.storage.cache_lookup(STAGE_ANALYSIS, key)["artifact_path"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cache_format"] = CACHE_FORMAT_VERSION + 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert cache.get_analysis(text_sha256("md"), "SETTINGS") is None


def test_open_cache_uses_the_webapp_data_dir_convention(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path / "env-dir"))
    cache = open_cache()
    assert cache.root == tmp_path / "env-dir" / "artifacts"
    # An explicit directory still wins, so a CLI run can point elsewhere.
    assert open_cache(tmp_path / "explicit").root == tmp_path / "explicit" / "artifacts"


def test_artifact_cache_refuses_ambiguous_construction(data_dir):
    with pytest.raises(ValueError):
        ArtifactCache(Storage(data_dir), data_dir=data_dir)


# ---------------------------------------------------------------------------
# memoizing wrappers (the API the CLI consumers call)
# ---------------------------------------------------------------------------


def test_cached_ocr_computes_once_then_serves_from_the_cache(cache):
    calls = []

    def compute():
        calls.append(1)
        return _doc(pages=["ledger"])

    first = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert first.cached is False and len(calls) == 1

    second = cached_ocr(PDF, compute=compute, cache=cache, source_file="s.pdf")
    assert second.cached is True
    assert len(calls) == 1
    assert second.value.pages == ["ledger"]
    assert second.value.model == "fake-ocr"


def test_cached_ocr_restamps_the_source_file_instead_of_keying_on_it(cache):
    """A duplicate uploaded under a new name must still skip OCR, and the
    markdown header must name the file being processed NOW."""
    calls = []

    def compute():
        calls.append(1)
        return _doc(pages=["ledger"], source_file="original.pdf")

    cached_ocr(PDF, compute=compute, cache=cache, source_file="original.pdf")
    renamed = cached_ocr(PDF, compute=compute, cache=cache, source_file="copy.pdf")

    assert renamed.cached is True and len(calls) == 1
    assert renamed.value.source_file == "copy.pdf"
    assert "source: copy.pdf" in renamed.value.to_markdown()


def test_cached_ocr_partitions_on_the_capability_flags(cache):
    calls = []

    def compute():
        calls.append(1)
        return _doc()

    cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False)
    cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=True)
    # Different rung, different artifact — the second read must not be served
    # the first one's text.
    assert len(calls) == 2


def test_cached_ocr_caches_a_negative_result(cache):
    """The deterministic preflight returning None is a deterministic outcome
    of the same bytes and settings; re-running the offline rungs for it would
    re-pay local Tesseract on every re-upload."""
    calls = []

    def compute():
        calls.append(1)
        return None

    first = cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False)
    second = cached_ocr(PDF, compute=compute, cache=cache, allow_visual_ocr=False)
    assert first.value is None and second.value is None
    assert second.cached is True
    assert len(calls) == 1

    # D-3b: the artifact shape gained page_integrity — a negative result still
    # stores a null document rather than an empty one, and still round-trips.
    settings_key = ocr_settings_key(allow_visual_ocr=False)
    hit, document = cache.get_ocr(content_sha256(PDF), settings_key)
    assert (hit, document) == (True, None)


def test_cached_analysis_computes_once_and_partitions_on_settings(cache):
    calls = []

    def compute():
        calls.append(1)
        return {"statement": {"bank": "Test Bank"}}

    first = cached_analysis(
        "# md", compute=compute, cache=cache, parse_mode="auto",
        analysis_settings=_AnalysisSettings(),
    )
    second = cached_analysis(
        "# md", compute=compute, cache=cache, parse_mode="auto",
        analysis_settings=_AnalysisSettings(),
    )
    assert first.cached is False and second.cached is True
    assert second.value == {"statement": {"bank": "Test Bank"}}
    assert len(calls) == 1

    # A changed extraction model re-analyzes rather than serving the old model's
    # answer.
    third = cached_analysis(
        "# md", compute=compute, cache=cache, parse_mode="auto",
        analysis_settings=_AnalysisSettings(model="gemini-other"),
    )
    assert third.cached is False and len(calls) == 2


def test_cached_analysis_never_caches_a_failure(cache):
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("no deterministic parser matched this statement")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cached_analysis("# md", compute=boom, cache=cache,
                            analysis_settings=_AnalysisSettings())
    assert len(calls) == 2
    assert cache.storage.cache_entries(STAGE_ANALYSIS) == []


def test_cached_report_computes_once(cache):
    calls = []

    def compute():
        calls.append(1)
        return "<h1>md</h1>"

    assert cached_report("# md", compute=compute, cache=cache, title="s.pdf").cached is False
    again = cached_report("# md", compute=compute, cache=cache, title="s.pdf")
    assert again.cached is True and again.value == "<h1>md</h1>"
    assert len(calls) == 1


def test_cache_none_disables_caching_entirely(tmp_path):
    calls = []

    def compute():
        calls.append(1)
        return _doc()

    for _ in range(3):
        result = cached_ocr(PDF, compute=compute, cache=None)
        assert result.cached is False and result.cache_key is None
    assert len(calls) == 3


def test_stages_are_independent(cache):
    """The point of keying the analysis stage on the MARKDOWN hash: changing
    an analysis knob re-analyzes without re-reading the document."""
    ocr_calls, analysis_calls = [], []

    def read():
        ocr_calls.append(1)
        return _doc(pages=["ledger"])

    def analyze():
        analysis_calls.append(1)
        return {"statement": {"bank": "Test Bank"}}

    def cycle(analysis_settings):
        document = cached_ocr(PDF, compute=read, cache=cache, source_file="s.pdf").value
        cached_analysis(
            document.to_markdown(), compute=analyze, cache=cache,
            analysis_settings=analysis_settings,
        )

    cycle(_AnalysisSettings())
    cycle(_AnalysisSettings())
    assert (len(ocr_calls), len(analysis_calls)) == (1, 1)

    cycle(_AnalysisSettings(model="gemini-other"))
    # Re-analyzed, NOT re-read.
    assert (len(ocr_calls), len(analysis_calls)) == (1, 2)


# ---------------------------------------------------------------------------
# the hard requirement, proven through the real worker
# ---------------------------------------------------------------------------


class _CallCounter:
    """Counts every OCR-ladder and analysis-pipeline invocation. Any nonzero
    delta on a re-run of identical bytes fails the D-3 acceptance criterion."""

    def __init__(self) -> None:
        self.ocr = 0
        self.analysis = 0

    def install(self, monkeypatch, pages=("ledger page",)) -> None:
        def fake_parse(pdf_bytes, source_file="", **kwargs):
            self.ocr += 1
            return StatementMarkdown(
                source_file=source_file, model="fake-ocr", pages=list(pages)
            )

        def fake_analyze(markdown, parse_mode="auto"):
            self.analysis += 1
            return object()

        monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
        monkeypatch.setattr("webapp.worker.analyze_markdown", fake_analyze)
        monkeypatch.setattr(
            "webapp.worker.report_to_json",
            lambda report: {"statement": {"bank": "Test Bank"},
                            "quality": {"level": "transaction_level"}},
        )


def _run(store: JobStore, filename="s.pdf", pdf_bytes=PDF, **kwargs):
    job = store.create(filename, pdf_bytes=pdf_bytes)
    run_job(job.id, pdf_bytes, filename, store, **kwargs)
    return store.get(job.id)


def test_reupload_of_identical_bytes_performs_zero_ocr_and_zero_llm_calls(
    monkeypatch, data_dir
):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    first = _run(store)
    assert (counter.ocr, counter.analysis) == (1, 1)
    assert first.status == "done"

    second = _run(store)
    # THE acceptance criterion: not one further call.
    assert (counter.ocr, counter.analysis) == (1, 1)
    assert second.status == "done"
    assert second.markdown == first.markdown
    assert second.html == first.html
    assert second.analysis == first.analysis
    assert second.parse_model == first.parse_model


def test_cached_reprocessing_survives_a_restart(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch)

    first = _run(JobStore(Storage(data_dir)))
    assert (counter.ocr, counter.analysis) == (1, 1)

    # Tear down and reopen over the same data directory — a process restart.
    restarted = JobStore(Storage(data_dir))
    second = _run(restarted)
    assert (counter.ocr, counter.analysis) == (1, 1)
    assert second.markdown == first.markdown
    assert second.analysis == first.analysis


def test_distinct_bytes_are_never_served_from_another_documents_cache(
    monkeypatch, data_dir
):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    _run(store, filename="a.pdf", pdf_bytes=PDF)
    _run(store, filename="b.pdf", pdf_bytes=OTHER_PDF)
    assert (counter.ocr, counter.analysis) == (2, 2)


def test_changed_analysis_settings_reanalyze_without_reocr(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    _run(store)
    assert (counter.ocr, counter.analysis) == (1, 1)

    # A different extraction model must not be served the old model's answer —
    # but it must not re-OCR either.
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-pro-experiment")
    _run(store)
    assert (counter.ocr, counter.analysis) == (1, 2)


def test_a_cache_hit_still_fills_the_live_viewer_buffer(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch, pages=("ledger page",))
    store = JobStore(Storage(data_dir))

    _run(store)
    job = _run(store)
    assert counter.ocr == 1
    # Nothing was OCR'd, yet the viewer's live panel still has the pages.
    assert "ledger page" in store.get(job.id).live_text


def test_cache_hits_are_audit_logged(monkeypatch, data_dir):
    counter = _CallCounter()
    counter.install(monkeypatch)
    store = JobStore(Storage(data_dir))

    _run(store)
    assert store.storage.audit_events("cache_hit") == []

    second = _run(store)
    events = store.storage.audit_events("cache_hit", job_id=second.id)
    stages = {json.loads(event["detail"])["stage"] for event in events}
    assert stages == {STAGE_OCR, STAGE_ANALYSIS, STAGE_REPORT}


def test_the_index_is_a_derived_cache_not_an_append_only_ledger(cache):
    """Unlike review_decisions/audit_log, artifact_cache rows may be updated
    and deleted — it holds nothing that is not recomputable."""
    key = cache.put_analysis(text_sha256("md"), "SETTINGS", {"ok": True})
    with sqlite3.connect(cache.storage.db_path) as conn:
        conn.execute(
            "UPDATE artifact_cache SET hit_count = 5 WHERE cache_key = ?", (key,)
        )
        conn.execute("DELETE FROM artifact_cache WHERE cache_key = ?", (key,))
    assert cache.storage.cache_lookup(STAGE_ANALYSIS, key) is None


# ---------------------------------------------------------------------------
# D-3b: O-3 page-integrity flags survive the cache
# ---------------------------------------------------------------------------


def _flagged_doc() -> StatementMarkdown:
    """Two pages: one clean, one truncated with both evidence classes."""
    return StatementMarkdown(
        source_file="scan.pdf",
        model="fake-ocr",
        pages=["clean page", "<table><tr><td>cut off"],
        page_integrity=[
            PageIntegrity(page_index=0, truncated=False, signals=[], finish_reason="stop"),
            PageIntegrity(
                page_index=1,
                truncated=True,
                signals=["model_finish_reason_length", "open_table_at_tail"],
                finish_reason="length",
            ),
        ],
    )


def test_cached_ocr_preserves_o3_page_integrity(cache):
    """A cached read must be indistinguishable from a fresh one: dropping the
    truncation flags would turn an intake defect back into a silent one."""
    fresh = _flagged_doc()
    calls = []

    def compute():
        calls.append(1)
        return fresh

    cached_ocr(PDF, compute=compute, cache=cache, source_file="scan.pdf")
    served = cached_ocr(PDF, compute=compute, cache=cache, source_file="scan.pdf")

    assert served.cached is True and len(calls) == 1
    document = served.value
    assert document.has_truncated_pages is True
    assert document.truncated_pages == fresh.truncated_pages == [1]
    assert [item.to_dict() for item in document.page_integrity] == [
        item.to_dict() for item in fresh.page_integrity
    ]
    # Field by field, so a partial reconstruction cannot pass on the dict alone.
    clean, truncated = document.page_integrity
    assert (clean.page_index, clean.truncated, clean.signals, clean.finish_reason) == (
        0, False, [], "stop",
    )
    assert truncated.page_index == 1 and truncated.truncated is True
    assert truncated.signals == [
        "model_finish_reason_length", "open_table_at_tail",
    ]
    assert truncated.finish_reason == "length"
    assert all(isinstance(item, PageIntegrity) for item in document.page_integrity)
    # And nothing else about the document moved.
    assert document.pages == fresh.pages and document.model == fresh.model


def test_a_document_without_integrity_records_round_trips_as_unassessed(cache):
    """An empty page_integrity means "the ladder did not assess this" and must
    stay empty rather than being invented on read."""
    cached_ocr(PDF, compute=lambda: _doc(pages=["a"]), cache=cache)
    served = cached_ocr(PDF, compute=lambda: pytest.fail("must be cached"), cache=cache)
    assert served.value.page_integrity == []
    assert served.value.has_truncated_pages is False


def test_a_document_shaped_object_without_the_o3_field_still_stores(cache):
    """O-3's own readers tolerate objects that predate the field (its test
    doubles return plain strings); the cache does the same rather than
    raising on a hand-built extractor result."""

    class _PreO3Doc:
        model = "legacy-extractor"
        pages = ["only a page list and a model"]

    cache.put_ocr(content_sha256(PDF), "SETTINGS", _PreO3Doc())
    hit, document = cache.get_ocr(content_sha256(PDF), "SETTINGS")
    assert hit is True
    assert document["page_integrity"] == []


def test_the_ocr_stage_version_bump_invalidates_pre_o3_entries(cache, monkeypatch):
    """The standing stage-version criterion, exercised: an artifact written
    under the pre-O-3 shape (v1) must MISS under v2 rather than be served
    without its truncation flags."""
    import webapp.artifact_cache as module

    assert OCR_STAGE_VERSION == 2  # pinned: D-3b bumped it from 1
    calls = []

    def compute():
        calls.append(1)
        return _flagged_doc()

    monkeypatch.setattr(module, "OCR_STAGE_VERSION", 1)
    assert cached_ocr(PDF, compute=compute, cache=cache).cached is False
    assert cached_ocr(PDF, compute=compute, cache=cache).cached is True
    assert len(calls) == 1

    monkeypatch.setattr(module, "OCR_STAGE_VERSION", 2)
    under_v2 = cached_ocr(PDF, compute=compute, cache=cache)
    assert under_v2.cached is False and len(calls) == 2
    # The v1 entry is still on disk under its own key — invalidated, not
    # corrupted, and it never leaks into a v2 read.
    assert len(cache.storage.cache_entries(STAGE_OCR)) == 2


def test_stage_version_constants_are_part_of_the_settings_keys():
    """Code changes are invisible to a content hash; the stage version is the
    only lever that invalidates artifacts after a pipeline change, so it must
    actually be in the key."""
    import webapp.artifact_cache as module

    before = analysis_settings_key(analysis_settings=_AnalysisSettings())
    original = module.ANALYSIS_STAGE_VERSION
    try:
        module.ANALYSIS_STAGE_VERSION = original + 1
        assert analysis_settings_key(analysis_settings=_AnalysisSettings()) != before
    finally:
        module.ANALYSIS_STAGE_VERSION = original
    assert ANALYSIS_STAGE_VERSION == original
