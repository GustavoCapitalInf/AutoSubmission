"""W3-5: the visual-OCR rung inside discovery's offline-first ladder.

Nothing here reaches a server. The visual rung is faked at its ONE home —
`ocr.ocr_client.ocr_page` / `_build_client`, exactly the seam
`tests/test_pipeline.py` established — so these tests prove the COMPOSITION
(when the rung is asked for, what is cached, what is flagged, what is recorded)
without ever proving the model. The live smoke test lives in
`tests/test_live_smoke.py` behind the `live` marker.

The claimable text is a real committed OCR artifact from the pinned corpus, so
"the visual read claimed" is a genuine registry dispatch and not a stub.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from discovery.inventory import DedupIndex
from discovery.runner import (
    MODE_DIGITAL,
    MODE_SCANNED,
    MODE_SCANNED_VISUAL,
    PARSER_ID_LIVE_DETECT,
    PARSER_ID_LIVE_DISPATCH,
    DiscoveryRunner,
)
from ocr.availability import DEFAULT_PROBE_TIMEOUT, VisualOcrStatus, probe_visual_ocr
from ocr.document import StatementMarkdown

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "Bank Statements"
#: An image-only corpus statement whose committed OCR artifact a
#: registration both claims AND publishes: the offline rung has to be able
#: to succeed for "the visual rung was not reached" to mean anything.
#:
#: It was `Misc/Columbia May 26 complete.pdf` until W3 §REPAIRDOC removed the
#: two amount-rewriting repairs from `analysis/columbia_bank.py`. That
#: document now DECLINES at parse — it is a pinned refusal
#: (`corpus_gate.PINNED_REFUSALS`) — so as a fixture it would silently invert
#: every assertion here from "claimed offline" to "unclaimed".
SCANNED = "Misc/First Farmers 2026 01-document.pdf"
DIGITAL = "Chase/Chase Mar.pdf"

#: A real image-only statement: the profile reports zero native text, so the
#: native rung is skipped and only the OCR rungs can serve it.
SCAN_BYTES = (CORPUS / SCANNED).read_bytes()

#: The committed OCR artifact for that statement — text a real parser claims.
CLAIMABLE = None

#: Text no registration can claim: the class-5 shape (a read happened, it is
#: just not good enough for anyone to recognise).
JUNK = "scan noise\nlllll ooooo\n0000 ....\nno recognisable statement structure"

#: A visual page cut off mid-table: O-3's structural tail signal must fire.
TRUNCATED = "<table><tr><td>DATE</td><td>AMOUNT</td></tr><tr><td>05/01</td><td>12.00"


def _claimable() -> str:
    global CLAIMABLE
    if CLAIMABLE is None:
        from corpus_artifacts import cached_markdown

        CLAIMABLE = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
        assert CLAIMABLE, "the committed artifact is the claimable fixture"
    return CLAIMABLE


@pytest.fixture(autouse=True)
def pinned_ocr_env(monkeypatch):
    """Hermetic OCR settings: the cache key and `source.model` are settings."""
    monkeypatch.setenv("OCR_MODEL", "baidu/Unlimited-OCR")
    monkeypatch.setenv("OCR_BASE_URL", "http://localhost:8000/v1")


@pytest.fixture
def scan_tree(tmp_path: Path) -> Path:
    (tmp_path / "BankZ").mkdir()
    (tmp_path / "BankZ" / "scan.pdf").write_bytes(SCAN_BYTES)
    return tmp_path


def _tesseract(monkeypatch, text: str | None):
    """Pin the local-Tesseract rung's answer (never runs the real binary).

    `text=None` is the rung finding nothing — the `deferred_visual_ocr` shape.
    The document is stamped with the source file exactly as the real extractor
    does, because that string is part of the markdown the analysis stage keys on.
    """
    def fake(pdf_bytes, source_file="", **kwargs):
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file,
                                 model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


def _visual(monkeypatch, text, *, calls=None):
    """Install a fake visual rung returning one page of `text`."""
    from ocr.config import load_settings

    monkeypatch.setattr("ocr.pipeline.load_settings", load_settings)
    monkeypatch.setattr("ocr.pipeline.rasterize_pdf", lambda b, dpi=300: ["img0"])
    monkeypatch.setattr("ocr.ocr_client._build_client", lambda settings: object())

    def fake_ocr_page(image, *, settings, client, on_delta=None):
        if calls is not None:
            calls.append(image)
        if isinstance(text, Exception):
            raise text
        return text

    monkeypatch.setattr("ocr.ocr_client.ocr_page", fake_ocr_page)


def _forbid_visual(monkeypatch):
    monkeypatch.setattr("ocr.pipeline.load_settings",
                        lambda **k: pytest.fail("the visual rung must not run"))


def _runner(root: Path, mode: str = MODE_SCANNED_VISUAL, **kwargs) -> DiscoveryRunner:
    kwargs.setdefault("dedup", DedupIndex())
    kwargs.setdefault("sink", None)
    kwargs.setdefault("cache", None)
    return DiscoveryRunner(root, mode=mode, run_id="test-run", **kwargs)


# ---------------------------------------------------------------------------
# 1. Availability: probe up front, refuse to start, never guess
# ---------------------------------------------------------------------------


def test_probe_reports_a_reachable_endpoint_as_usable():
    status = probe_visual_ocr(list_models=lambda: ["baidu/Unlimited-OCR"])
    assert status.available and status.usable
    assert status.model == "baidu/Unlimited-OCR"
    assert "ready" in status.message()


def test_probe_never_raises_and_keeps_only_the_exception_class():
    def boom():
        raise ConnectionRefusedError("[Errno 111] Connection refused")

    status = probe_visual_ocr(list_models=boom)
    assert status.available is False and status.usable is False
    assert status.error_type == "ConnectionRefusedError"
    assert "unreachable" in status.message()
    assert status.base_url in status.message()


def test_probe_refuses_a_server_that_does_not_serve_our_model():
    """Every completion would 404 — a certain-failure configuration."""
    status = probe_visual_ocr(list_models=lambda: ["some-other-model"])
    assert status.available is True
    assert status.model_advertised is False
    assert status.usable is False
    assert "some-other-model" in status.message()


def test_probe_does_not_second_guess_an_endpoint_that_advertises_nothing():
    """An empty list is an absence of evidence, not evidence of absence."""
    status = probe_visual_ocr(list_models=lambda: [])
    assert status.usable is True


def test_probe_does_not_inherit_the_long_ocr_timeout():
    """A preflight must answer fast; OCR_TIMEOUT defaults to 120 s."""
    from ocr.config import load_settings

    assert DEFAULT_PROBE_TIMEOUT < load_settings().timeout


def test_the_cli_refuses_to_start_when_the_endpoint_is_unusable(monkeypatch, tmp_path):
    import shutil

    import discovery.cli as cli

    monkeypatch.setattr(shutil, "which", lambda name: "tesseract")
    monkeypatch.setattr(cli, "probe_visual_ocr", lambda **k: VisualOcrStatus(
        available=False, base_url="http://localhost:8000/v1",
        model="baidu/Unlimited-OCR", detail="refused",
        error_type="APIConnectionError",
    ))
    monkeypatch.setattr(cli, "run", lambda *a, **k: pytest.fail(
        "no document may be enumerated when the endpoint is unusable"))

    assert cli.main(["--scanned-visual", "--root", str(tmp_path)]) == 2


def test_the_cli_still_requires_tesseract_for_the_visual_mode(monkeypatch, tmp_path):
    """--scanned-visual is --scanned PLUS a rung; it does not replace one."""
    import shutil

    import discovery.cli as cli

    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(cli, "probe_visual_ocr", lambda **k: pytest.fail(
        "the tesseract check comes first; do not touch the endpoint"))
    assert cli.main(["--scanned-visual", "--root", str(tmp_path)]) == 2


def test_the_cli_starts_when_the_endpoint_is_usable(monkeypatch, tmp_path):
    import shutil

    import discovery.cli as cli

    seen = {}
    monkeypatch.setattr(shutil, "which", lambda name: "tesseract")
    monkeypatch.setattr(cli, "probe_visual_ocr", lambda **k: VisualOcrStatus(
        available=True, base_url="http://localhost:8000/v1",
        model="baidu/Unlimited-OCR", advertised=("baidu/Unlimited-OCR",),
    ))

    def fake_run(root, mode, out, **kwargs):
        seen.update(mode=mode, **kwargs)
        return {"run_id": "r", "mode": mode, "documents": 0, "processed": 0,
                "deferred": 0, "deferred_reasons": {}, "dispatched": 0,
                "dispatch_cached": 0, "deterministic_coverage": 0.0,
                "dispatch": {}, "outcome": {}, "reasons": {}, "classification": {},
                "dedup": {}, "source_path": {}, "folder_agreement": {},
                "label_unmatched_pairs": [], "parsers": {}, "folders": {},
                "unknown_layout_clusters": {}, "ambiguity_clusters": {},
                "near_miss_parsers": {}, "truncated_documents": 0, "visual_rung": {},
                "cache": {}, "inventory": {}, "output_dir": str(tmp_path)}

    monkeypatch.setattr(cli, "run", fake_run)
    assert cli.main(["--scanned-visual", "--root", str(tmp_path), "--quiet"]) == 0
    assert seen["mode"] == MODE_SCANNED_VISUAL
    assert seen["visual_escalation"] is True

    assert cli.main(["--scanned-visual", "--root", str(tmp_path), "--quiet",
                     "--no-visual-escalation"]) == 0
    assert seen["visual_escalation"] is False


def test_the_escalation_knob_is_refused_outside_the_visual_mode(monkeypatch, tmp_path):
    """Silently ignoring it would let an operator believe a policy was applied."""
    import discovery.cli as cli

    monkeypatch.setattr(cli, "run", lambda *a, **k: pytest.fail("must not run"))
    assert cli.main(["--digital", "--no-visual-escalation",
                     "--root", str(tmp_path)]) == 2


# ---------------------------------------------------------------------------
# 2. Ladder parity: no existing mode changes its resolution path
# ---------------------------------------------------------------------------


def test_importing_the_cli_does_not_pull_in_the_model_client():
    """The availability probe is deliberately client-free at import time, so
    `python -m discovery --digital` keeps its offline guarantee unchanged."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c",
         "import sys, discovery.cli; print('ocr.ocr_client' in sys.modules)"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False", result.stdout


def test_the_scanned_tranche_still_defers_and_never_reaches_the_rung(
    scan_tree: Path, monkeypatch
):
    """Tranche 2's numbers are of record: --scanned must be untouched."""
    _tesseract(monkeypatch, None)
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree, MODE_SCANNED).process("BankZ/scan.pdf", "BankZ")
    assert (row.outcome_class, row.outcome_reason) == ("deferred", "deferred_visual_ocr")
    assert row.visual_rung == "not_attempted"
    assert row.source_path == "none"


def test_the_digital_tranche_still_defers_scanned_documents(scan_tree: Path, monkeypatch):
    _forbid_visual(monkeypatch)
    row = _runner(scan_tree, MODE_DIGITAL).process("BankZ/scan.pdf", "BankZ")
    assert (row.outcome_class, row.outcome_reason) == ("deferred", "deferred_scanned")
    assert row.visual_rung == "not_attempted"


def test_an_offline_read_that_claims_never_reaches_the_rung(scan_tree: Path, monkeypatch):
    """Offline-first: the rung is a fallback, never a default."""
    _tesseract(monkeypatch, _claimable())
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")
    assert row.parser_id == "first_farmers"
    assert row.source_path == "local_tesseract"
    assert row.visual_rung == "not_attempted"


def test_a_native_text_document_is_never_escalated(tmp_path: Path, monkeypatch):
    """An unclaimed NATIVE read is a layout problem (class 1), not an OCR one.

    Re-reading text we already have perfectly, with a GPU, cannot conjure a
    parser that does not exist — and there are ~660 such documents.
    """
    (tmp_path / "BankN").mkdir()
    (tmp_path / "BankN" / "text.pdf").write_bytes((CORPUS / DIGITAL).read_bytes())

    monkeypatch.setattr(
        "ocr.pipeline._native_statement",
        lambda pdf_bytes, source_file="": StatementMarkdown(
            source_file=source_file, model="native-pdf-text", pages=[JUNK]),
    )
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract",
                        lambda *a, **k: pytest.fail("the native rung already served this"))
    _forbid_visual(monkeypatch)
    row = _runner(tmp_path).process("BankN/text.pdf", "BankN")
    assert row.source_path == "native"
    assert row.dispatch_outcome == "unclaimed"
    assert row.visual_rung == "not_attempted"


# ---------------------------------------------------------------------------
# 3. Recovery — the 13 deferred_visual_ocr documents
# ---------------------------------------------------------------------------


def test_a_document_no_offline_rung_can_read_is_recovered_by_the_visual_rung(
    scan_tree: Path, monkeypatch
):
    _tesseract(monkeypatch, None)
    _visual(monkeypatch, _claimable())

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "recovered"
    assert row.source_path == "visual"
    assert row.source_model == "baidu/Unlimited-OCR"
    assert row.parser_id == "first_farmers"
    assert row.outcome_class in {"validated", "review"}
    # It is no longer deferred: the mode exists to attempt exactly this.
    assert row.outcome_class != "deferred"


def test_a_document_the_visual_rung_also_cannot_serve_gets_a_terminal_outcome(
    scan_tree: Path, monkeypatch
):
    """The deferral taxonomy stays intact: not deferred, not silently lost."""
    _tesseract(monkeypatch, None)
    _visual(monkeypatch, JUNK)

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "recovered"      # the rung DID produce text
    assert row.source_path == "visual"
    assert row.outcome_class == "failed"       # nobody could claim it
    assert row.outcome_reason == "no_parser_matched"


# ---------------------------------------------------------------------------
# 4. Upgrade — discovery class 5 (tesseract text nobody could claim)
# ---------------------------------------------------------------------------


def test_an_unclaimed_tesseract_read_is_re_read_and_upgraded(scan_tree: Path, monkeypatch):
    _tesseract(monkeypatch, JUNK)
    _visual(monkeypatch, _claimable())

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "upgraded"
    assert row.source_path == "visual"
    assert row.parser_id == "first_farmers"
    assert row.outcome_class in {"validated", "review"}


def test_when_the_visual_read_also_fails_the_offline_read_stays_of_record(
    scan_tree: Path, monkeypatch
):
    _tesseract(monkeypatch, JUNK)
    _visual(monkeypatch, "different noise, still unclaimable")

    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "no_upgrade"
    assert row.source_path == "local_tesseract"   # the visual read is not adopted
    assert (row.outcome_class, row.outcome_reason) == ("failed", "no_parser_matched")


def test_no_visual_escalation_recovers_but_does_not_re_read(scan_tree: Path, monkeypatch):
    _tesseract(monkeypatch, JUNK)
    _forbid_visual(monkeypatch)

    row = _runner(scan_tree, visual_escalation=False).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "not_attempted"
    assert row.source_path == "local_tesseract"

    # ...while recovery still happens: the two policies are independent.
    _tesseract(monkeypatch, None)
    _visual(monkeypatch, _claimable())
    row = _runner(scan_tree, visual_escalation=False).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "recovered"


def test_a_claimed_document_whose_parser_crashed_is_not_escalated(
    scan_tree: Path, monkeypatch
):
    """A parser defect (W3-1) is not an OCR defect; do not spend GPU time on it."""
    import discovery.runner as runner_module

    _tesseract(monkeypatch, _claimable())
    _forbid_visual(monkeypatch)

    real = runner_module.analyze_document

    def crashing(markdown, **kwargs):
        real(markdown, **kwargs)          # dispatches for real -> claimed
        raise AttributeError("simulated parser defect")

    monkeypatch.setattr(runner_module, "analyze_document", crashing)
    row = _runner(scan_tree).process("BankZ/scan.pdf", "BankZ")
    assert row.dispatch_outcome == "claimed"
    assert row.error_type == "AttributeError"
    assert row.visual_rung == "not_attempted"


# ---------------------------------------------------------------------------
# 5. Mid-run failure: that document fails closed, the run continues
# ---------------------------------------------------------------------------


def test_a_server_failure_mid_run_fails_that_document_closed(scan_tree: Path, monkeypatch):
    from telemetry import JsonlSink, read_jsonl

    (scan_tree / "BankZ" / "second.pdf").write_bytes(SCAN_BYTES)
    _tesseract(monkeypatch, None)
    _visual(monkeypatch, ConnectionError("connection refused"))

    sink = JsonlSink(scan_tree / "telemetry.jsonl")
    runner = _runner(scan_tree, sink=sink)
    row = runner.process("BankZ/scan.pdf", "BankZ")

    assert row.visual_rung == "failed"
    assert (row.outcome_class, row.outcome_reason) == ("failed", "ocr_failed")
    assert row.error_type == "ConnectionError"
    assert row.source_path == "none"

    # The run continues: the next document is still processed and recorded.
    second = runner.process("BankZ/second.pdf", "BankZ")
    assert second.outcome_class == "failed"

    records = read_jsonl(scan_tree / "telemetry.jsonl")
    assert len(records) == 2
    assert records[0]["outcome"]["error_type"] == "ConnectionError"
    assert records[0]["outcome"]["fallback_reason"] == "visual_ocr_failed"
    # Exception CLASS names only — a message can quote the document.
    assert "connection refused" not in __import__("json").dumps(records[0])


def test_a_failed_visual_read_is_never_cached(scan_tree: Path, monkeypatch, tmp_path):
    """A transient outage must not pin a permanent 'this document is dead'."""
    from webapp.artifact_cache import open_cache

    cache = open_cache(tmp_path / "data")
    _tesseract(monkeypatch, None)
    _visual(monkeypatch, ConnectionError("down"))
    assert _runner(scan_tree, cache=cache).process(
        "BankZ/scan.pdf", "BankZ").visual_rung == "failed"

    _visual(monkeypatch, _claimable())
    row = _runner(scan_tree, cache=cache).process("BankZ/scan.pdf", "BankZ")
    assert row.visual_rung == "recovered"
    assert row.cache_visual == "miss"      # nothing negative was stored


# ---------------------------------------------------------------------------
# 6. D-3 cache: the visual knobs partition the key, and nothing is re-OCR'd
# ---------------------------------------------------------------------------


def test_the_visual_read_occupies_its_own_cache_partition():
    """Same bytes, two reads: the capability flags are key material."""
    from webapp.artifact_cache import ocr_settings_key

    offline = ocr_settings_key(force_ocr=False, allow_local_ocr=True,
                               allow_visual_ocr=False)
    visual = ocr_settings_key(force_ocr=True, allow_local_ocr=False,
                              allow_visual_ocr=True)
    assert offline != visual


@pytest.mark.parametrize("knob,value", [
    ("model", "some-other-ocr-model"),
    ("base_url", "http://elsewhere:9000/v1"),
    ("ngram_size", 7),
    ("window_size", 64),
])
def test_every_visual_service_knob_partitions_the_cache_key(knob, value):
    """Over-partitioning is safe; serving a stale read across a knob change is not."""
    from dataclasses import replace

    from ocr.config import load_settings
    from webapp.artifact_cache import ocr_settings_key

    base = load_settings()
    def key(settings):
        return ocr_settings_key(force_ocr=True, allow_local_ocr=False,
                                allow_visual_ocr=True, ocr_settings=settings)

    assert key(base) != key(replace(base, **{knob: value}))


def test_identical_content_and_settings_are_never_re_ocrd(
    scan_tree: Path, monkeypatch, tmp_path
):
    from webapp.artifact_cache import open_cache

    cache = open_cache(tmp_path / "data")
    calls: list = []
    _tesseract(monkeypatch, None)
    _visual(monkeypatch, _claimable(), calls=calls)

    first = _runner(scan_tree, cache=cache).process("BankZ/scan.pdf", "BankZ")
    assert first.cache_visual == "miss"
    assert len(calls) == 1

    second = _runner(scan_tree, cache=cache).process("BankZ/scan.pdf", "BankZ")
    assert second.cache_visual == "hit"
    assert len(calls) == 1                       # the GPU was not touched again
    assert second.source_path == "visual"
    assert second.source_model == first.source_model


def test_a_cached_analysis_does_not_trigger_a_spurious_escalation(
    scan_tree: Path, monkeypatch, tmp_path
):
    """On a D-3 analysis hit no dispatch is OBSERVED this run. Guessing
    'unclaimed' there would escalate the entire archive to the GPU on every
    re-run — `_needs_visual_upgrade` reads `collector.seen` and the payload,
    never the row.

    Updated at §DISCOBS. The row now carries a RECONSTRUCTED verdict, so
    `dispatch_outcome is None` is no longer the way to say "nothing was
    observed" — `parser_id_source` is, and it is the sharper assertion: it
    distinguishes the two states the old line conflated. The escalation guard
    is unchanged and is what the last line still proves; `_forbid_visual`
    would fail the test outright if the rung ran.
    """
    from webapp.artifact_cache import open_cache

    cache = open_cache(tmp_path / "data")
    _tesseract(monkeypatch, _claimable())
    _forbid_visual(monkeypatch)

    first = _runner(scan_tree, cache=cache).process("BankZ/scan.pdf", "BankZ")
    assert first.cache_analysis == "miss" and first.parser_id == "first_farmers"
    assert first.parser_id_source == PARSER_ID_LIVE_DISPATCH

    second = _runner(scan_tree, cache=cache).process("BankZ/scan.pdf", "BankZ")
    assert second.cache_analysis == "hit"
    assert second.parser_id_source == PARSER_ID_LIVE_DETECT   # nothing observed...
    assert second.dispatch_outcome == "claimed"               # ...but not unknown
    assert second.parser_id == first.parser_id
    assert second.visual_rung == "not_attempted"              # ...and no guess either


# ---------------------------------------------------------------------------
# 7. O-3 truncation is assessed on every visual read
# ---------------------------------------------------------------------------


def test_a_truncated_visual_page_is_flagged_on_the_row_and_in_telemetry(
    scan_tree: Path, monkeypatch
):
    from telemetry import JsonlSink, read_jsonl

    _tesseract(monkeypatch, None)
    _visual(monkeypatch, TRUNCATED)

    sink = JsonlSink(scan_tree / "telemetry.jsonl")
    row = _runner(scan_tree, sink=sink).process("BankZ/scan.pdf", "BankZ")
    assert row.truncated_pages == 1

    record = read_jsonl(scan_tree / "telemetry.jsonl")[0]
    truncation = record["source"]["truncation"]
    assert truncation["assessed"] is True
    assert truncation["truncated_page_count"] == 1
    assert "open_table_at_tail" in truncation["signals"]


def test_truncation_flags_survive_the_visual_cache_round_trip(
    scan_tree: Path, monkeypatch, tmp_path
):
    """D-3b's rule: a cached read must be indistinguishable from a fresh one."""
    from webapp.artifact_cache import open_cache

    cache = open_cache(tmp_path / "data")
    _tesseract(monkeypatch, None)
    _visual(monkeypatch, TRUNCATED)

    first = _runner(scan_tree, cache=cache).process("BankZ/scan.pdf", "BankZ")
    second = _runner(scan_tree, cache=cache).process("BankZ/scan.pdf", "BankZ")
    assert second.cache_visual == "hit"
    assert second.truncated_pages == first.truncated_pages == 1


# ---------------------------------------------------------------------------
# 8. H-3 telemetry: path, timings, pages, cost accounting
# ---------------------------------------------------------------------------


def test_the_record_carries_the_path_timings_pages_and_model_id(
    scan_tree: Path, monkeypatch
):
    import json

    from telemetry import JsonlSink, read_jsonl

    _tesseract(monkeypatch, None)
    _visual(monkeypatch, _claimable())

    sink = JsonlSink(scan_tree / "telemetry.jsonl")
    row = _runner(scan_tree, sink=sink).process("BankZ/scan.pdf", "BankZ")
    record = read_jsonl(scan_tree / "telemetry.jsonl")[0]

    assert record["source"]["path"] == "visual"
    assert record["source"]["model"] == "baidu/Unlimited-OCR"
    assert record["outcome"]["fallback_reason"] == "visual_ocr_recovered"

    # Timings for the rung, separate from the offline attempt that preceded it.
    assert record["stages"]["visual_ocr"]["ms"] >= 0
    assert record["stages"]["visual_ocr"]["cache"] == "bypass"
    assert "ocr" in record["stages"]

    # Cost accounting: model id + page count, so throughput is measurable.
    ocr_calls = [c for c in record["models"]["calls"] if c["purpose"] == "visual_ocr"]
    assert len(ocr_calls) == 1
    assert ocr_calls[0]["model"] == "baidu/Unlimited-OCR"
    assert ocr_calls[0]["calls"] == record["source"]["page_count"] == 1

    # Ocean ruling (W3-5 Q1): the local Unlimited-OCR endpoint is a
    # FREE_MODEL — $0 vendor cost is a known fact, not an unknown price.
    # Infra cost stays operational (pages + timings above), never vendor.
    cost = record["models"]["cost"]
    assert "baidu/Unlimited-OCR" not in cost["unpriced_models"]
    assert cost["complete"] is True
    assert cost["amount"] == 0.0

    # The H-3 sensitivity invariant is unchanged by the new rung.
    blob = json.dumps(record)
    assert "BankZ" not in blob and "scan.pdf" not in blob
    assert row.content_sha256 in blob


def test_the_upgrade_is_visible_in_the_record(scan_tree: Path, monkeypatch):
    from telemetry import JsonlSink, read_jsonl

    _tesseract(monkeypatch, JUNK)
    _visual(monkeypatch, _claimable())

    sink = JsonlSink(scan_tree / "telemetry.jsonl")
    _runner(scan_tree, sink=sink).process("BankZ/scan.pdf", "BankZ")
    record = read_jsonl(scan_tree / "telemetry.jsonl")[0]

    assert record["outcome"]["fallback_reason"] == "visual_ocr_upgraded"
    assert record["source"]["path"] == "visual"
    assert record["dispatch"]["parser_id"] == "first_farmers"
    assert record["stages"]["visual_analysis"]["ms"] >= 0


# ---------------------------------------------------------------------------
# 9. The rollup
# ---------------------------------------------------------------------------


def test_the_report_ranks_what_the_visual_rung_bought():
    from discovery.report import ROW_FIELDS, render_report, summarize
    from discovery.runner import DocumentRow

    def row(**kwargs):
        base = dict(relative_path="F/a.pdf", folder_label="F",
                    content_sha256="A" * 64, byte_size=1)
        base.update(kwargs)
        return DocumentRow(**base)

    rows = [
        row(visual_rung="upgraded", dispatch_outcome="claimed", parser_id="first_farmers",
            outcome_class="validated", outcome_reason="approved"),
        row(visual_rung="upgraded", dispatch_outcome="claimed", parser_id="first_farmers",
            outcome_class="validated", outcome_reason="approved"),
        row(visual_rung="recovered", dispatch_outcome="claimed", parser_id="chase",
            outcome_class="validated", outcome_reason="approved"),
        row(visual_rung="failed", outcome_class="failed", outcome_reason="ocr_failed"),
        row(dispatch_outcome="claimed", parser_id="chase",
            outcome_class="validated", outcome_reason="approved"),
    ]
    summary = summarize(rows, mode=MODE_SCANNED_VISUAL, run_id="r")
    assert summary["visual_rung"] == {"upgraded": 2, "recovered": 1, "failed": 1}
    report = render_report(summary)
    assert "visual OCR rung" in report
    assert report.isascii()
    assert {"visual_rung", "cache_visual"} <= set(ROW_FIELDS)
    # P20-ROUTER (Phase 2.0) then P21-ROUTING (Phase 2.1): each block appended
    # at the END in turn, so an existing reader by name is unaffected — see
    # `discovery/report.py`'s `ROW_FIELDS` comment.
    assert ROW_FIELDS[-13:-9] == [
        "failure_class", "escalation_trigger", "evidence_quality", "escalation_refused",
    ]
    assert ROW_FIELDS[-9:-2] == [
        "paddle_rung", "cache_paddle", "escalation_extractor", "evidence_sha256",
        "paddle_provider", "paddle_execution_class", "offline_source_model",
    ]
    assert ROW_FIELDS[-2:] == ["cache_finding", "paddle_refusal_reason"]


def test_offline_modes_report_no_visual_activity():
    from discovery.report import render_report, summarize
    from discovery.runner import DocumentRow

    rows = [DocumentRow(relative_path="F/a.pdf", folder_label="F",
                        content_sha256="A" * 64, byte_size=1,
                        dispatch_outcome="claimed", parser_id="chase",
                        outcome_class="validated", outcome_reason="approved")]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["visual_rung"] == {}
    assert "visual OCR rung" not in render_report(summary)
