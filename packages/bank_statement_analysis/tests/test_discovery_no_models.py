"""Discovery after the model rungs were removed (owner ruling, 2026-10-13: the product uses no model; model-code
removal, slice S5).

* `--scanned` on a document the offline ladder (Tesseract included) reads nothing from ends in the declared,
  fail-closed `refused:insufficient_evidence`, in the row AND in its telemetry record (it was
  `deferred:deferred_visual_ocr`); `--digital` still defers such a document (`deferred:deferred_scanned`).
* N5 for discovery: an image-only document goes through `--scanned` with every outbound connection refused and
  counted, and none is attempted (once with the Tesseract rung stubbed, once with the real local binary).
* The three retired mode names stay vocabulary and the runner refuses each; the CLI has none of their flags.
* The summary keeps every key (`research` None, `research_rows` 0, `escalation_budget` None, `escalations_used` 0),
  R counts both spellings of "the offline ladder read nothing", and a historical research run's rows summarize
  EXACTLY as they did at the slice's parent (57ca19a; the expected values below were computed there).
* The per-document `_last_*` reset pin, moved from the deleted `tests/test_paddle_routing.py`.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import shutil
import socket
from pathlib import Path

import pytest

from discovery.inventory import DedupIndex
from discovery.report import offline_ladder_read_nothing, render_report, summarize
from discovery.runner import (
    LOCAL_OCR_MODES,
    MODE_DIGITAL,
    MODE_RESEARCH_PADDLE,
    MODE_SCANNED,
    MODE_SCANNED_PADDLE,
    MODE_SCANNED_VISUAL,
    RETIRED_MODES,
    DiscoveryRunner,
    DocumentRow,
)

ROOT = Path(__file__).resolve().parents[1]


def _image_only_pdf() -> bytes:
    """A fabricated one-page PDF holding a blank image and no text layer."""
    import fitz

    with fitz.open() as document:
        page = document.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64), 0)
        pixmap.clear_with(255)
        page.insert_image(page.rect, pixmap=pixmap)
        return document.tobytes()


@pytest.fixture
def image_tree(tmp_path: Path) -> Path:
    (tmp_path / "root" / "BankZ").mkdir(parents=True)
    (tmp_path / "root" / "BankZ" / "image.pdf").write_bytes(_image_only_pdf())
    return tmp_path / "root"


@pytest.fixture
def no_outbound(monkeypatch):
    """Every outbound connection is refused and counted."""
    attempts = []

    def refuse(self, address):  # noqa: ANN001
        attempts.append(type(address).__name__)
        raise ConnectionRefusedError("an outbound connection was attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    return attempts


def _run_one(root: Path, mode: str, telemetry_path: Path):
    from telemetry import JsonlSink

    runner = DiscoveryRunner(root, mode=mode, run_id="test-run", sink=JsonlSink(telemetry_path), cache=None,
                             dedup=DedupIndex())
    row = runner.process("BankZ/image.pdf", "BankZ")
    records = [json.loads(line) for line in telemetry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    return row, records[0]


# --- the declared move: refused:insufficient_evidence, in the row and the record ---------------------------------


def test_scanned_refuses_a_document_the_offline_ladder_reads_nothing_from(image_tree, tmp_path, monkeypatch,
                                                                         no_outbound):
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)
    row, record = _run_one(image_tree, MODE_SCANNED, tmp_path / "t.jsonl")
    assert (row.outcome_class, row.outcome_reason) == ("refused", "insufficient_evidence")
    assert row.source_path == "none"
    assert row.stage_extract == "none" and row.stage_verdict == "refused"
    assert (row.reason_l2, row.primary_reason_layer, row.primary_reason) == ("E0_no_evidence", "l2", "E0_no_evidence")
    assert (row.visual_rung, row.paddle_rung, row.escalation_trigger, row.escalation_refused,
            row.escalation_extractor) == ("not_attempted", "not_attempted", "", "", "")
    assert row.as_dict()["outcome_reason"] == "insufficient_evidence"
    outcome = record["outcome"]
    assert (outcome["class"], outcome["reason"]) == ("refused", "insufficient_evidence")
    assert outcome["fallback_reason"] is None and outcome["escalated"] is False
    assert no_outbound == []


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="local Tesseract not installed")
def test_scanned_with_the_real_local_tesseract_refuses_with_no_outbound_connection(image_tree, tmp_path,
                                                                                  no_outbound):
    """N5 for discovery: the real Tesseract rung runs on the machine, reads nothing from a blank image, and the
    document is refused; no connection is attempted."""
    row, record = _run_one(image_tree, MODE_SCANNED, tmp_path / "t.jsonl")
    assert (row.outcome_class, row.outcome_reason) == ("refused", "insufficient_evidence")
    assert (record["outcome"]["class"], record["outcome"]["reason"]) == ("refused", "insufficient_evidence")
    assert no_outbound == []


def test_digital_still_defers_a_document_only_tesseract_could_read(image_tree, tmp_path, no_outbound):
    row, record = _run_one(image_tree, MODE_DIGITAL, tmp_path / "t.jsonl")
    assert (row.outcome_class, row.outcome_reason) == ("deferred", "deferred_scanned")
    assert (record["outcome"]["class"], record["outcome"]["reason"]) == ("deferred", "deferred_scanned")
    assert no_outbound == []


def test_the_no_text_site_assigns_the_refusal_as_one_literal_the_taxonomy_guard_sees():
    """D5: the literal tuple assignment, so `runner_reason_literals` (the taxonomy's drift guard) reads it."""
    from telemetry.unresolved_taxonomy import runner_reason_literals

    source = (ROOT / "discovery" / "runner.py").read_text(encoding="utf-8")
    assert source.count('row.outcome_class, row.outcome_reason = "refused", "insufficient_evidence"') == 1
    assert 'refused="insufficient_evidence"' in source
    literals = runner_reason_literals(source, (ROOT / "telemetry" / "record.py").read_text(encoding="utf-8"))
    assert "insufficient_evidence" in literals and "deferred_visual_ocr" not in literals


def test_a_scanned_run_summarizes_the_refusal_and_keeps_every_summary_key(image_tree, tmp_path, monkeypatch,
                                                                          no_outbound):
    import discovery.cli as cli

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)
    summary = cli.run(image_tree, MODE_SCANNED, tmp_path / "out", skip_baseline=True, use_cache=False)
    assert (summary["processed"], summary["deferred"], summary["deferred_reasons"]) == (1, 0, {})
    assert summary["outcome"] == {"refused": 1}
    assert summary["reasons"] == {"insufficient_evidence": 1}
    assert summary["dispatch_unavailable"] == 1
    assert summary["diagnostic_labels"]["R"] == 1 and summary["diagnostic_labels"]["refused"] == 1
    assert (summary["research"], summary["research_rows"]) == (None, 0)
    assert (summary["escalation_budget"], summary["escalations_used"]) == (None, 0)
    for key in ("visual_rung", "paddle_rung", "escalation_extractor", "escalation_trigger", "failure_class"):
        assert summary[key] == {}, key
    run_dir = Path(summary["output_dir"])
    assert not (run_dir / "provenance.json").exists()  # only a research run wrote one here
    text = (run_dir / "report.txt").read_text(encoding="utf-8")
    assert f"  R  offline ladder produced no text     {1:>7}" in text.splitlines()
    assert f"  refused                                {1:>7}" in text.splitlines()
    assert no_outbound == []


# --- R keeps its meaning across the two spellings ----------------------------------------------------------------


def _row(**kwargs) -> DocumentRow:
    base = dict(relative_path="F/a.pdf", folder_label="F", content_sha256="A" * 64, byte_size=1)
    base.update(kwargs)
    return DocumentRow(**base)


def test_r_counts_both_spellings_of_the_offline_ladder_reading_nothing():
    assert offline_ladder_read_nothing(_row(outcome_class="deferred", outcome_reason="deferred_visual_ocr"))
    assert offline_ladder_read_nothing(_row(outcome_class="refused", outcome_reason="insufficient_evidence",
                                            source_path="none"))
    # the new spelling needs all three facts
    assert not offline_ladder_read_nothing(_row(outcome_class="refused", outcome_reason="insufficient_evidence",
                                                source_path="local_tesseract"))
    assert not offline_ladder_read_nothing(_row(outcome_class="failed", outcome_reason="insufficient_evidence",
                                                source_path="none"))
    assert not offline_ladder_read_nothing(_row(outcome_class="deferred", outcome_reason="deferred_scanned"))
    rows = [_row(content_sha256=c * 64, outcome_class="refused", outcome_reason="insufficient_evidence")
            for c in "AB"] + [_row(content_sha256="C" * 64, outcome_class="deferred",
                                   outcome_reason="deferred_visual_ocr")]
    labels = summarize(rows, mode=MODE_SCANNED, run_id="r")["diagnostic_labels"]
    assert (labels["R"], labels["refused"]) == (3, 2)


# --- a historical research run summarizes exactly as at the parent -----------------------------------------------


def _historical_research_rows() -> list:
    """Fabricated rows of the shapes the retired modes wrote (copied verbatim from
    remove-models/s5-paddle/research_table_probe.py, which computed the expected values at 57ca19a)."""
    def row(sha: str, **kwargs):
        base = dict(relative_path=f"F/{sha[:4]}.pdf", folder_label="F", content_sha256=sha, byte_size=1)
        base.update(kwargs)
        return DocumentRow(**base)

    partition = "p23-wave-a"
    return [
        row("A" * 64, research_partition=partition, escalation_trigger="operator_forced_paddle",
            paddle_rung="research", escalation_extractor="paddle", source_path="paddle", stage_extract="paddle",
            stage_evidence="present", evidence_quality="usable", stage_candidate="claimed",
            stage_verdict="validated", dispatch_outcome="claimed", parser_id="chase",
            outcome_class="validated", outcome_reason="approved"),
        row("B" * 64, research_partition=partition, escalation_trigger="operator_forced_paddle",
            paddle_rung="research", escalation_extractor="paddle", source_path="paddle", stage_extract="paddle",
            stage_evidence="present", evidence_quality="unusable", stage_candidate="unclaimed",
            stage_verdict="failed", dispatch_outcome="unclaimed", outcome_class="failed",
            outcome_reason="no_parser_matched"),
        row("C" * 64, research_partition=partition, outcome_class="deferred",
            outcome_reason="research_skipped_not_in_population"),
        row("D" * 64, research_partition=partition, outcome_class="deferred",
            outcome_reason="research_refused_holdout"),
        row("E" * 64, dispatch_outcome="claimed", parser_id="chase", source_path="native",
            outcome_class="validated", outcome_reason="approved"),
        row("F" * 64, source_path="none", outcome_class="deferred", outcome_reason="deferred_visual_ocr"),
        row("0" * 64, paddle_rung="failed", escalation_extractor="paddle", source_path="none",
            outcome_class="failed", outcome_reason="ocr_failed", escalation_trigger="offline_rungs_produced_no_text"),
        row("1" * 64, source_path="none", outcome_class="failed", outcome_reason="escalation_refused",
            escalation_refused="escalation_budget_exhausted",
            escalation_trigger="offline_rungs_produced_no_text"),
    ]


#: Computed at the slice's parent (57ca19a) over `_historical_research_rows()` with `research_partition` unset.
_EXPECTED_AT_PARENT = json.loads(
    '{"deferred": 1, "deferred_reasons": {"deferred_visual_ocr": 1}, "diagnostic_labels": {"R": 1, "U": 0, '
    '"density_surfaced": "not carried on rows", "failure_class": {"A": 0, "B": 0, "C": 0}, "note": '
    '"overlapping; never summed", "refused": 0, "truncation_flagged": 0}, "dispatch_unavailable": 2, '
    '"documents": 4, "escalation_budget": null, "escalation_extractor": {"paddle": 1}, "escalation_trigger": '
    '{"offline_rungs_produced_no_text": 2}, "escalations_used": 0, "outcome": {"failed": 2, "validated": 1}, '
    '"paddle_rung": {"failed": 1}, "processed": 3, "reasons": {"approved": 1, "escalation_refused": 1, '
    '"ocr_failed": 1}, "research": {"attempted": 2, "e_gate": {"unusable": 1, "usable": 1}, "evidence": '
    '{"present": 2}, "outcome": {"deferred": 2, "failed": 1, "validated": 1}, "partition": "p23-wave-a", '
    '"refused_holdout": 1, "rows": 4, "skipped_not_in_population": 1, "stages": {"stage_candidate": '
    '{"claimed": 1, "unclaimed": 1}, "stage_evidence": {"present": 2}, "stage_extract": {"paddle": 2}, '
    '"stage_geometry": {"not_attempted": 2}, "stage_layout": {"not_attempted": 2}, "stage_verdict": '
    '{"failed": 1, "validated": 1}}}, "research_rows": 4, "source_path": {"native": 1, "none": 2}}'
)
#: sha16 of `render_report` over the same rows (`research_partition="p23-wave-a"`, budget 2, used 1), at 57ca19a.
_EXPECTED_REPORT_SHA16_AT_PARENT = "96a9f8ec2ed9c1cf"


@pytest.mark.parametrize("kwargs", [{}, {"research_partition": "p23-wave-a", "escalation_budget": 2,
                                         "escalations_used": 1}])
def test_a_historical_research_run_summarizes_exactly_as_at_the_parent(kwargs):
    summary = summarize(_historical_research_rows(), mode=MODE_RESEARCH_PADDLE, run_id="r", **kwargs)
    expected = dict(_EXPECTED_AT_PARENT)
    expected.update({k: v for k, v in kwargs.items() if k in ("escalation_budget", "escalations_used")})
    assert {key: summary[key] for key in expected} == expected
    if kwargs:
        digest = hashlib.sha256(render_report(summary).encode()).hexdigest()[:16]
        assert digest == _EXPECTED_REPORT_SHA16_AT_PARENT


# --- the retired modes and flags ---------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", [MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE, MODE_RESEARCH_PADDLE])
def test_each_retired_mode_stays_vocabulary_and_refuses_to_start(tmp_path, monkeypatch, mode):
    assert mode in LOCAL_OCR_MODES and mode in RETIRED_MODES
    monkeypatch.setattr("ocr.pipeline.parse_statement", lambda *a, **k: pytest.fail("nothing may be read"))
    with pytest.raises(ValueError, match="retired"):
        DiscoveryRunner(tmp_path, mode=mode, run_id="t", dedup=DedupIndex())
    assert set(RETIRED_MODES) == {MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE, MODE_RESEARCH_PADDLE}
    assert (MODE_SCANNED_PADDLE, MODE_RESEARCH_PADDLE) == ("scanned-paddle", "research-paddle")


@pytest.mark.parametrize("argv", [
    ["--scanned-paddle"],
    ["--research-paddle"],
    ["--scanned", "--population", "p.txt"],
    ["--scanned", "--research-partition", "p23-a"],
    ["--scanned", "--data-dir", "d"],
    ["--scanned", "--holdout-digest", "h.txt"],
    ["--scanned", "--no-visual-escalation"],
])
def test_the_cli_has_none_of_the_retired_flags(tmp_path, monkeypatch, capsys, argv):
    import discovery.cli as cli

    monkeypatch.setattr(cli, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(SystemExit) as raised:
        cli.main([*argv, "--root", str(tmp_path)])
    assert raised.value.code == 2  # argparse: unrecognized argument
    for name in ("probe_paddle_ocr", "DEFAULT_HOLDOUT_DIGEST", "_write_research_provenance"):
        assert not hasattr(cli, name), name


def test_the_runner_constructor_takes_no_escalation_or_research_input():
    parameters = set(inspect.signature(DiscoveryRunner.__init__).parameters)
    assert parameters == {"self", "root", "mode", "run_id", "sink", "cache", "dedup"}


def test_the_runner_holds_no_escalation_machinery():
    import discovery.runner as runner_module

    for name in ("_read_paddle", "_project_paddle_refusal", "_upgrade_eligible", "_apply_budget"):
        assert not hasattr(DiscoveryRunner, name), name
    for name in ("estimate_class_a_population", "refuse_production_data_dir", "_profile_triggers"):
        assert not hasattr(runner_module, name), name
    tree = ast.parse(inspect.getsource(runner_module))
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"decide", "EscalationRouter", "router_inputs", "RouterInputs", "enabled_extractors",
                        "visual_escalation", "escalation_budget", "escalations_used", "allow_paddle_ocr"}


# --- the per-document reset pin (moved from tests/test_paddle_routing.py) ----------------------------------------


def test_every_per_document_last_attribute_is_reset_at_the_top_of_process():
    """MAJOR-A's structural half: every `_last_*` class attribute of `DiscoveryRunner` (they are all per-document
    cache dispositions) is assigned in `_reset_per_document_state`, and `process()` calls that method BEFORE its
    first `self._read*(` call — so a new `_last_*` attribute cannot be added without its reset, and the reset cannot
    drift below a read."""
    import discovery.runner as runner_module

    class_attrs = {
        name for name in vars(DiscoveryRunner)
        if name.startswith("_last_") and not callable(getattr(DiscoveryRunner, name))
    }
    assert class_attrs == {"_last_ocr_cached", "_last_ocr_finding"}

    tree = ast.parse(inspect.getsource(runner_module))
    class_node = next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "DiscoveryRunner"
    )
    methods = {n.name: n for n in class_node.body if isinstance(n, ast.FunctionDef)}
    reset = methods["_reset_per_document_state"]
    reset_targets = {
        node.attr for node in ast.walk(reset)
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name) and node.value.id == "self"
    }
    assert reset_targets == class_attrs, (
        f"per-document attributes without a reset: {class_attrs - reset_targets}; "
        f"resets of nothing: {reset_targets - class_attrs}"
    )

    process = methods["process"]
    reset_calls = [
        node.lineno for node in ast.walk(process)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_reset_per_document_state"
    ]
    read_calls = [
        node.lineno for node in ast.walk(process)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr.startswith("_read")
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
    ]
    assert reset_calls, "process() never calls _reset_per_document_state"
    assert read_calls, "process() has no _read* call; re-pin"
    assert min(reset_calls) < min(read_calls), "the reset must precede every read"
