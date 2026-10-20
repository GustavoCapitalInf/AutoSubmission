"""Discovery's offline ladder after the visual OCR rung was removed (model-code removal, slice S2).

Carried from the deleted `tests/test_visual_rung.py`: the offline modes' own pins (the `--scanned` no-text outcome
and the `--digital` deferral, an offline read that claims, the offline summary reporting no visual activity) and the
`ROW_FIELDS` block-order pin, which `discovery/report.py`'s append-only column list must keep. Added: the retired
`--scanned-visual` mode is refused (by the runner and the CLI), and the visual OCR client modules are gone.

Slice S5 (declared, re-pinned): `--scanned`'s document the offline ladder reads nothing from moved from
`deferred:deferred_visual_ocr` to `refused:insufficient_evidence`, in the row and in its telemetry record, and
`--no-visual-escalation` left the CLI with the Paddle mode it applied to.

Nothing here reaches a server; the local-Tesseract rung is pinned with a fake, never the real binary.
"""
from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from discovery.inventory import DedupIndex
from discovery.runner import (
    LOCAL_OCR_MODES,
    MODE_DIGITAL,
    MODE_SCANNED,
    MODE_SCANNED_VISUAL,
    DiscoveryRunner,
)
from ocr.document import StatementMarkdown
from tests.statements import statements_dir

ROOT = Path(__file__).resolve().parents[1]
#: An image-only corpus statement whose committed OCR artifact a registration both claims AND publishes (see the
#: history of `tests/test_visual_rung.py` for why it is this document).
SCANNED = "Misc/First Farmers 2026 01-document.pdf"


def _scan_bytes() -> bytes:
    """A real image-only statement: the profile reports zero native text, so the native rung is skipped and only the
    Tesseract rung can serve it."""
    return (statements_dir() / SCANNED).read_bytes()


def _claimable() -> str:
    from corpus_artifacts import cached_markdown

    text = cached_markdown(_scan_bytes(), ROOT / "tests" / "corpus_cache")
    assert text, "the committed artifact is the claimable fixture"
    return text


@pytest.fixture
def scan_tree(tmp_path: Path) -> Path:
    (tmp_path / "BankZ").mkdir()
    (tmp_path / "BankZ" / "scan.pdf").write_bytes(_scan_bytes())
    return tmp_path


def _tesseract(monkeypatch, text: str | None):
    """Pin the local-Tesseract rung's answer (never runs the real binary). `text=None` is the rung finding nothing —
    the shape `--scanned` refuses as `insufficient_evidence` (it was `deferred_visual_ocr` until slice S5)."""
    def fake(pdf_bytes, source_file="", **kwargs):
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


@pytest.fixture
def ladder_calls(monkeypatch):
    """Every `parse_statement` call the runner makes, with its flags: the visual rung is gone, so a call that asks
    for it (or forces) would be a regression the ladder itself refuses; this records that none is made."""
    import ocr.pipeline as pipeline

    real = pipeline.parse_statement
    calls: list[dict] = []

    def spy(pdf_bytes, source_file="", **kwargs):
        calls.append(dict(kwargs))
        return real(pdf_bytes, source_file, **kwargs)

    monkeypatch.setattr(pipeline, "parse_statement", spy)
    return calls


def _runner(root: Path, mode: str, **kwargs) -> DiscoveryRunner:
    kwargs.setdefault("dedup", DedupIndex())
    kwargs.setdefault("sink", None)
    kwargs.setdefault("cache", None)
    return DiscoveryRunner(root, mode=mode, run_id="test-run", **kwargs)


def _no_visual_read(calls: list[dict]) -> None:
    assert calls, "the runner read the document through the ladder"
    assert all(call.get("allow_visual_ocr") is False and call.get("force_ocr") is False for call in calls), calls


# ---------------------------------------------------------------------------
# Carried from tests/test_visual_rung.py (behaviour unchanged)
# ---------------------------------------------------------------------------


def test_the_scanned_tranche_refuses_what_the_ladder_cannot_read_and_never_reaches_a_further_rung(
        scan_tree: Path, tmp_path: Path, monkeypatch, ladder_calls):
    """DECLARED MOVE (slice S5): a document the offline ladder, Tesseract included, reads nothing from was
    `deferred:deferred_visual_ocr` ("left for the visual rung"); no model rung remains, so --scanned now refuses
    it, fail-closed, as `refused:insufficient_evidence`, in the row and in its telemetry record alike. Nothing
    further is read."""
    import json

    from telemetry import JsonlSink

    _tesseract(monkeypatch, None)

    sink_path = tmp_path / "telemetry.jsonl"
    row = _runner(scan_tree, MODE_SCANNED, sink=JsonlSink(sink_path)).process("BankZ/scan.pdf", "BankZ")
    assert (row.outcome_class, row.outcome_reason) == ("refused", "insufficient_evidence")
    assert row.visual_rung == "not_attempted"
    assert row.source_path == "none"
    (record,) = [json.loads(line) for line in sink_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert (record["outcome"]["class"], record["outcome"]["reason"]) == ("refused", "insufficient_evidence")
    _no_visual_read(ladder_calls)


def test_the_digital_tranche_still_defers_scanned_documents(scan_tree: Path, ladder_calls):
    row = _runner(scan_tree, MODE_DIGITAL).process("BankZ/scan.pdf", "BankZ")
    assert (row.outcome_class, row.outcome_reason) == ("deferred", "deferred_scanned")
    assert row.visual_rung == "not_attempted"
    _no_visual_read(ladder_calls)


def test_an_offline_read_that_claims_is_the_read_of_record(scan_tree: Path, monkeypatch, ladder_calls):
    _tesseract(monkeypatch, _claimable())

    row = _runner(scan_tree, MODE_SCANNED).process("BankZ/scan.pdf", "BankZ")
    assert row.parser_id == "first_farmers"
    assert row.source_path == "local_tesseract"
    assert row.visual_rung == "not_attempted"
    assert row.cache_visual == "bypass"
    _no_visual_read(ladder_calls)


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


def test_row_fields_keep_the_visual_columns_and_the_router_and_paddle_block_order():
    """`ROW_FIELDS` is append-only (plan D7): the visual columns stay as fixed values, and the router and Paddle
    blocks are CONTIGUOUS and IN THIS ORDER, wherever the list happens to end. A historical run's visual rows still
    summarize as they did."""
    from discovery.report import ROW_FIELDS, render_report, summarize
    from discovery.runner import DocumentRow

    assert {"visual_rung", "cache_visual"} <= set(ROW_FIELDS)
    router = ROW_FIELDS.index("failure_class")
    assert ROW_FIELDS[router:router + 4] == [
        "failure_class", "escalation_trigger", "evidence_quality", "escalation_refused",
    ]
    assert ROW_FIELDS[router + 4:router + 11] == [
        "paddle_rung", "cache_paddle", "escalation_extractor", "evidence_sha256",
        "paddle_provider", "paddle_execution_class", "offline_source_model",
    ]
    assert ROW_FIELDS[router + 11:router + 13] == ["cache_finding", "paddle_refusal_reason"]

    def row(**kwargs):
        base = dict(relative_path="F/a.pdf", folder_label="F", content_sha256="A" * 64, byte_size=1)
        base.update(kwargs)
        return DocumentRow(**base)

    historical = [
        row(visual_rung="upgraded", dispatch_outcome="claimed", parser_id="first_farmers",
            outcome_class="validated", outcome_reason="approved"),
        row(visual_rung="recovered", dispatch_outcome="claimed", parser_id="chase",
            outcome_class="validated", outcome_reason="approved"),
        row(visual_rung="failed", outcome_class="failed", outcome_reason="ocr_failed"),
    ]
    summary = summarize(historical, mode=MODE_SCANNED_VISUAL, run_id="r")
    assert summary["visual_rung"] == {"upgraded": 1, "recovered": 1, "failed": 1}
    assert "visual OCR rung" in render_report(summary)


# ---------------------------------------------------------------------------
# Added in slice S2: the retired mode is refused, and the client is gone
# ---------------------------------------------------------------------------


def test_the_retired_visual_mode_stays_a_name_and_the_runner_refuses_it(tmp_path: Path, monkeypatch):
    """Append-only vocabulary (plan D13): the name stays in LOCAL_OCR_MODES; constructing a runner with it raises
    before anything is read."""
    assert MODE_SCANNED_VISUAL == "scanned-visual"
    assert MODE_SCANNED_VISUAL in LOCAL_OCR_MODES
    monkeypatch.setattr("ocr.pipeline.parse_statement", lambda *a, **k: pytest.fail("nothing may be read"))
    with pytest.raises(ValueError, match="retired"):
        _runner(tmp_path, MODE_SCANNED_VISUAL)


def test_the_cli_has_no_scanned_visual_flag(tmp_path: Path, monkeypatch, capsys):
    import discovery.cli as cli

    monkeypatch.setattr(cli, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(SystemExit) as raised:
        cli.main(["--scanned", "--scanned-visual", "--root", str(tmp_path)])
    assert raised.value.code == 2  # argparse: unrecognized argument
    assert "--scanned-visual" in capsys.readouterr().err
    assert not hasattr(cli, "probe_visual_ocr")


def test_the_no_visual_escalation_knob_is_refused_in_every_mode(tmp_path: Path, monkeypatch):
    """Silently ignoring it would let an operator believe a policy was applied. It used to be refused outside the
    Paddle mode; since slice S5 the flag does not exist at all, so argparse refuses it in every mode."""
    import discovery.cli as cli

    monkeypatch.setattr(cli, "run", lambda *a, **k: pytest.fail("must not run"))
    for mode in ("--digital", "--scanned", "--dry-run"):
        with pytest.raises(SystemExit) as raised:
            cli.main([mode, "--no-visual-escalation", "--root", str(tmp_path)])
        assert raised.value.code == 2


def test_the_visual_ocr_client_modules_are_gone():
    for name in ("ocr.ocr_client", "ocr.availability"):
        assert importlib.util.find_spec(name) is None, name
        with pytest.raises(ImportError):
            importlib.import_module(name)


def test_no_offline_entry_point_imports_a_model_client():
    """A fresh process: discovery, the parse and batch CLIs and the pipeline import no visual OCR client and no
    OpenAI-compatible client."""
    code = (
        "import sys, discovery.cli, discovery.runner, ocr.pipeline, parse, batch; "
        "banned = ('ocr.ocr_client', 'ocr.availability', 'openai'); "
        "print(sorted(m for m in sys.modules if m in banned or m.startswith('openai.')))"
    )
    result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, cwd=ROOT,
                            timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "[]", result.stdout
