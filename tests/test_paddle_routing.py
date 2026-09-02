"""P21-ROUTING (Phase 2.1, cell R) — the Paddle rung wired into the ONE
ladder and the ONE router, proved through the REAL `DiscoveryRunner`.

Cases 1, 2, 3, 4, 9, 10, 12, 18 (runner half), 19, 20 (CASE 14 lives in
`tests/test_q3_native_only.py`, alongside every other Q3 case). Every Paddle
request in this file goes to the in-process `tests.paddle_fake_worker.
FakeWorker` on an ephemeral loopback port, or to a directly-mocked
`ocr.paddle_rung.read_document` (for CASE 9, which needs a specific claimable
text without depending on PaddleOCR's own geometry-to-text fidelity for a
real bank's detection markers — the rung's OWN text-from-geometry behaviour
is `tests/test_paddle_adapter.py`'s to prove). Zero real network egress
either way: `PADDLE_VAST_HOST` is never read from the real environment here,
and no test in this file sets `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN`.
"""
from __future__ import annotations

import ast
import inspect
import os
import sys
from pathlib import Path

import pytest

from discovery.inventory import DedupIndex
from discovery.runner import DiscoveryRunner, MODE_SCANNED_PADDLE
from evidence.canonical import ExtractionEvidence, LineBox, PageEvidence, PageFrame, WordBox
from ocr.document import StatementMarkdown
from ocr.paddle_rung import PaddleRead
from tests.paddle_fake_worker import FakeWorker
from tests.test_escalation_tripwires import _tracked_python_files

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "Bank Statements"
SCANNED = "Misc/First Farmers 2026 01-document.pdf"
SCAN_BYTES = (CORPUS / SCANNED).read_bytes()

#: Mirrored from `tests/test_escalation_router.py` (each test file keeps its
#: own fixtures deliberately — see that module's own comment on the same
#: pattern): dense, legible, genuinely usable, unclaimable prose (Class B).
USABLE_UNCLAIMABLE = (
    "This is a long, entirely legible page of prose that no bank statement "
    "parser in this registry has ever been written to recognise. It repeats "
    "ordinary sentences so that its total character count and alphanumeric "
    "density comfortably clear every floor the extraction quality gate "
    "checks, while never once taking the shape of a dated ledger row, an "
    "account number block, or a running balance column. " * 6
)

#: Usable under the admitted triad, density-SURFACED (never a trigger).
PADDED_TABULAR = (
    "\n".join(
        "DATE" + " " * 14 + "DESCRIPTION" + " " * 26 + "AMOUNT" + " " * 18 + "BALANCE"
        for _ in range(12)
    )
    + "\n"
)

#: Below CHAR_FLOOR (200): the U-extract shape (`extractor_output_unusable`).
BELOW_FLOOR = "x" * 40


def _tesseract(monkeypatch, text: str | None):
    def fake(pdf_bytes, source_file="", **kwargs):
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


def _runner(root: Path, **kwargs) -> DiscoveryRunner:
    kwargs.setdefault("dedup", DedupIndex())
    kwargs.setdefault("sink", None)
    kwargs.setdefault("cache", None)
    return DiscoveryRunner(root, mode=MODE_SCANNED_PADDLE, run_id="test-run", **kwargs)


@pytest.fixture
def scan_tree(tmp_path: Path) -> Path:
    (tmp_path / "BankZ").mkdir()
    (tmp_path / "BankZ" / "scan.pdf").write_bytes(SCAN_BYTES)
    return tmp_path


def _local_free_env(monkeypatch, worker_url: str) -> None:
    """A `local_free` fake worker: no opt-in literal needed at all — the way
    to drive the recovered/upgraded paths end to end without exercising the
    remote-paid opt-in gates (those are CASE 13/20's own tests)."""
    monkeypatch.setenv("PADDLE_PROVIDER", "local")
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", "local_free")
    monkeypatch.setenv("PADDLE_WORKER_URL", worker_url)
    monkeypatch.delenv("PADDLE_REMOTE_OPT_IN", raising=False)
    monkeypatch.delenv("PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN", raising=False)


def _remote_paid_env(monkeypatch, worker_url: str, *, opted_in: bool = True) -> None:
    monkeypatch.setenv("PADDLE_PROVIDER", "vast.ai")
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", "remote_paid")
    monkeypatch.setenv("PADDLE_VAST_HOST", "test-host.invalid")
    monkeypatch.setenv("PADDLE_VAST_SSH_PORT", "22")
    monkeypatch.setenv("PADDLE_VAST_SSH_USER", "test-user")
    monkeypatch.setenv("PADDLE_WORKER_URL", worker_url)
    if opted_in:
        monkeypatch.setenv("PADDLE_REMOTE_OPT_IN", "I_ACCEPT_REMOTE_PAID_PADDLE_OCR")
    else:
        monkeypatch.delenv("PADDLE_REMOTE_OPT_IN", raising=False)
    # D8/CASE 20: never set in this phase. Asserted absent at module scope too.
    monkeypatch.delenv("PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN", raising=False)


# ---------------------------------------------------------------------------
# The suite-wide guarantee CASE 20 depends on.
# ---------------------------------------------------------------------------


def test_the_customer_data_opt_in_literal_is_never_set_in_the_suite_environment():
    assert os.environ.get("PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN") is None


# ---------------------------------------------------------------------------
# CASE 1 (+ its U-extract shape, + CASE 20's refusal leg)
# ---------------------------------------------------------------------------


def test_case1_recovery_names_paddle_and_local_free_recovers(scan_tree, monkeypatch):
    """A `--scanned-paddle` run on an image-only PDF whose Tesseract rung
    returns `None`: the router names `paddle`
    (`escalation_trigger = offline_rungs_produced_no_text`), `_read_paddle`
    runs (the fake worker sees the page), and with a `local_free` fake the
    read proceeds all the way to `recovered`."""
    _tesseract(monkeypatch, None)
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.escalation_trigger == "offline_rungs_produced_no_text"
    assert row.escalation_extractor == "paddle"
    assert row.paddle_rung == "recovered"
    assert row.visual_rung == "not_attempted"
    assert len(fake.requests) >= 1
    assert row.paddle_provider == "local"
    assert row.paddle_execution_class == "local_free"


def test_case1_refusal_leg_remote_paid_refuses_customer_scope(scan_tree, monkeypatch):
    """CASE 20's other half: the SAME run, against a `remote_paid` fake
    (opted in), REFUSES the customer-scope document before any `/ocr` byte
    leaves — `paddle_rung = refused_customer_data`, and nothing else is
    tried."""
    _tesseract(monkeypatch, None)
    with FakeWorker() as fake:  # DEFAULT_IDENTITY is already vast.ai/remote_paid
        _remote_paid_env(monkeypatch, fake.url, opted_in=True)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.paddle_rung == "refused_customer_data"
    assert row.outcome_class == "failed"
    assert row.outcome_reason == "paddle_refused"
    assert row.error_type == "PaddleRefused"
    assert fake.requests == []  # no /ocr request ever sent


def test_case1_u_extract_shape_upgrade_also_names_paddle(scan_tree, monkeypatch):
    """The U-extract shape (a gate-unusable, below-floor Tesseract read)
    likewise names `paddle` — through the UPGRADE path this time, not
    RECOVERY."""
    _tesseract(monkeypatch, BELOW_FLOOR)
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.escalation_trigger == "extractor_output_unusable"
    assert row.escalation_extractor == "paddle"
    assert row.evidence_quality == "unusable"
    assert len(fake.requests) >= 1


# ---------------------------------------------------------------------------
# CASE 2: usable-but-unclaimable never escalates.
# ---------------------------------------------------------------------------


def test_case2_usable_unclaimed_never_escalates_to_paddle(scan_tree, monkeypatch):
    _tesseract(monkeypatch, USABLE_UNCLAIMABLE)
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.paddle_rung == "not_attempted"
    assert row.escalation_extractor == ""
    assert row.escalation_refused == "no_admitted_trigger"
    assert row.failure_class == "B"
    assert fake.requests == []


# ---------------------------------------------------------------------------
# CASE 3: Class C (claimed, financially failed) never escalates.
# ---------------------------------------------------------------------------


def test_case3_claimed_but_financially_failing_never_escalates(scan_tree, monkeypatch):
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, claimable)

    import telemetry.record as record_module

    real_classify = record_module.classify_document

    def force_c(payload, **kwargs):
        klass, reason = real_classify(payload, **kwargs)
        if klass == "validated":
            return "review", "forced_for_case3_test"
        return klass, reason

    monkeypatch.setattr(record_module, "classify_document", force_c)

    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.dispatch_outcome == "claimed"
    assert row.outcome_class != "validated"
    assert row.failure_class == "C"
    assert row.paddle_rung == "not_attempted"
    assert fake.requests == []


# ---------------------------------------------------------------------------
# CASE 4: density-surfaced-only (usable) never escalates.
# ---------------------------------------------------------------------------


def test_case4_density_surfaced_but_usable_never_escalates(scan_tree, monkeypatch):
    _tesseract(monkeypatch, PADDED_TABULAR)
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.paddle_rung == "not_attempted"
    assert row.evidence_quality == "usable"
    assert row.escalation_refused == "no_admitted_trigger"
    assert fake.requests == []


# ---------------------------------------------------------------------------
# CASE 9 / CASE 19: the UPGRADE path adopts a Paddle read; no fusion; the
# offline read's own model is preserved on the row.
# ---------------------------------------------------------------------------


def _claimable_paddle_read() -> PaddleRead:
    """A `PaddleRead` whose evidence reproduces a REAL committed corpus
    markdown exactly, line for line (each source line becomes one canonical
    line via an explicit, one-word-per-line `LineBox` list — bypassing
    `group_lines`'s own segmentation, which is `tests/test_paddle_adapter.py`
    's fixture to prove, not this module's). This is what lets a genuine
    registered parser CLAIM the Paddle-fed read without this test depending
    on PaddleOCR's own geometry-to-text fidelity for one bank's specific
    detection markers."""
    from corpus_artifacts import cached_markdown

    text = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    assert text, "the committed artifact is the claimable fixture"
    lines_text = text.split("\n")
    words: list[WordBox] = []
    lines: list[LineBox] = []
    y = 10.0
    for index, line_text in enumerate(lines_text):
        word_ids: tuple[str, ...] = ()
        if line_text.strip():
            wid = f"p0.l{index}.w0"
            words.append(WordBox(
                word_id=wid, page_index=0, text=line_text,
                x0=10.0, y0=y, x1=10.0 + max(len(line_text), 1) * 4.0, y1=y + 10.0,
                confidence=1.0, line_ref=index,
            ))
            word_ids = (wid,)
        lines.append(LineBox(
            line_id=f"p0.L{index}", page_index=0, y_top=y, y_bottom=y + 10.0,
            word_ids=word_ids, text=line_text,
        ))
        y += 15.0
    frame = PageFrame.pdf_points(page_index=0, width_pt=4000.0, height_pt=max(y + 50.0, 1000.0))
    page = PageEvidence(frame=frame, words=tuple(words), lines=tuple(lines))
    evidence = ExtractionEvidence(
        document_sha256="A" * 64, extractor_id="paddle-ocr", model_token="paddle-ocr+ppocrv5",
        pages=(page,), runtime={"provider": "local", "execution_class": "local_free", "worker_contract": 1},
    )
    return PaddleRead(
        pages=list(evidence.page_texts()), evidence=evidence,
        page_extractor=["paddle-ocr+ppocrv5"], telemetry={},
    )


def test_case9_upgrade_adopts_a_paddle_read_no_fusion(scan_tree, monkeypatch):
    _tesseract(monkeypatch, BELOW_FLOOR)  # unusable -> EXTRACTOR_OUTPUT_UNUSABLE
    fake_read = _claimable_paddle_read()
    monkeypatch.setattr("ocr.paddle_rung.read_document", lambda *a, **k: fake_read)

    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.paddle_rung == "upgraded"
    assert row.escalation_extractor == "paddle"
    assert row.dispatch_outcome == "claimed"
    # CASE 9: the offline read's OWN model is preserved, not lost, even
    # though the Paddle read is the one adopted and published.
    assert row.offline_source_model == "local-tesseract-ocr"
    assert row.source_path == "paddle"
    assert row.evidence_sha256 == fake_read.evidence.evidence_sha256
    assert row.paddle_provider == "local"
    assert row.paddle_execution_class == "local_free"


def test_case9_a_claimed_offline_read_is_never_escalated_to_paddle(scan_tree, monkeypatch):
    """The other half of "no fusion, no choice by which one reconciles": an
    offline read that ALREADY claimed is never handed to Paddle at all,
    whatever the Paddle read would have said — `_upgrade_eligible` (unchanged
    by this cell) refuses on `payload is not None` alone."""
    from corpus_artifacts import cached_markdown

    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, claimable)
    monkeypatch.setattr(
        "ocr.paddle_rung.read_document",
        lambda *a, **k: pytest.fail("Paddle must never run: the offline read already claimed"),
    )
    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.dispatch_outcome == "claimed"
    assert row.paddle_rung == "not_attempted"


# ---------------------------------------------------------------------------
# CASE 10: postprocess quarantine — AST + runtime spy.
# ---------------------------------------------------------------------------


def test_case10_paddle_branch_never_references_the_postprocess_chain():
    import ocr.pipeline as pipeline_module

    source = inspect.getsource(pipeline_module)
    tree = ast.parse(source)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "parse_statement"
    )
    paddle_if = None
    for node in ast.walk(func):
        if isinstance(node, ast.If):
            dumped = ast.dump(node.test)
            if "allow_paddle_ocr" in dumped and "allow_visual_ocr" not in dumped:
                paddle_if = node
                break
    assert paddle_if is not None, "the paddle branch guard was not found"
    names: set[str] = set()
    for node in ast.walk(paddle_if):
        if isinstance(node, ast.Name):
            names.add(node.id)
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    forbidden = {"ocr_client", "postprocess", "apply_admitted"}
    assert not (names & forbidden), names & forbidden


def test_case10_a_paddle_read_never_touches_ocr_client_at_runtime(scan_tree, monkeypatch):
    class _Poison:
        def __getattr__(self, name):
            raise AssertionError(f"ocr.ocr_client.{name} touched by a Paddle read")

    monkeypatch.setitem(sys.modules, "ocr.ocr_client", _Poison())
    _tesseract(monkeypatch, None)
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.paddle_rung == "recovered"


# ---------------------------------------------------------------------------
# CASE 12: no automatic remote fallback.
# ---------------------------------------------------------------------------


def test_case12_worker_enabled_extractors_is_visual_only():
    from webapp.worker import WORKER_ENABLED_EXTRACTORS

    assert WORKER_ENABLED_EXTRACTORS == frozenset({"visual"})


def test_case12_webapp_worker_has_no_allow_paddle_ocr_call_site():
    import webapp.worker as worker_module

    tree = ast.parse(inspect.getsource(worker_module))
    offenders = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.keyword) and node.arg == "allow_paddle_ocr"
    ]
    assert offenders == [], f"webapp/worker.py must never pass allow_paddle_ocr: lines {offenders}"


def test_case12_allow_paddle_ocr_true_appears_only_at_the_one_reviewed_call_site():
    """Repo-wide (production code, `tests/` excluded by `_tracked_python_files`):
    the ONLY file that ever passes `allow_paddle_ocr=True` is
    `discovery/runner.py` (`_read_paddle`) — never the webapp (Ruling A)."""
    offending_files: set[str] = set()
    for path in _tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.keyword) and node.arg == "allow_paddle_ocr"
                and isinstance(node.value, ast.Constant) and node.value.value is True
            ):
                offending_files.add(str(path.relative_to(ROOT)).replace("\\", "/"))
    assert offending_files == {"discovery/runner.py"}, offending_files


def test_case12_scanned_paddle_and_scanned_visual_never_both_enabled():
    """Two-engine escalation is not possible in this phase: a runner's
    `enabled_extractors` holds at most one member (D4, design item 8)."""
    for mode_kwargs in (
        dict(mode="scanned-visual"), dict(mode="scanned-paddle"), dict(mode="scanned"),
        dict(mode="digital"),
    ):
        runner = DiscoveryRunner(
            Path("."), run_id="t", sink=None, cache=None, dedup=DedupIndex(), **mode_kwargs,
        )
        assert len(runner.enabled_extractors) <= 1


# ---------------------------------------------------------------------------
# CASE 18 (runner half): transport failures fail closed, no second attempt.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fail_mode", ["connection_refused", "http_500", "malformed_json"])
def test_case18_transport_failures_fail_closed_with_no_second_attempt(scan_tree, monkeypatch, fail_mode):
    _tesseract(monkeypatch, None)  # RECOVERY

    def _visual_spy(self, *a, **k):
        pytest.fail("_read_visual must never be called from --scanned-paddle mode")

    monkeypatch.setattr(DiscoveryRunner, "_read_visual", _visual_spy)

    with FakeWorker(
        identity_overrides={"provider": "local", "execution_class": "local_free"}, fail_mode=fail_mode,
    ) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.paddle_rung == "failed"
    assert row.outcome_class == "failed"
    assert row.outcome_reason == "ocr_failed"
    assert row.error_type == "PaddleTransportError"
    assert row.source_path == "none"


# ---------------------------------------------------------------------------
# CASE 20: the runner's `"customer"` literal — pinned by AST.
# ---------------------------------------------------------------------------


def test_read_paddle_passes_the_literal_customer_scope_by_ast():
    import discovery.runner as runner_module

    tree = ast.parse(inspect.getsource(runner_module))
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_read_paddle"
    )
    calls = [
        node for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "parse_statement"
    ]
    assert len(calls) == 1, "expected exactly one parse_statement(...) call inside _read_paddle"
    scope_kw = next(kw for kw in calls[0].keywords if kw.arg == "paddle_data_scope")
    assert isinstance(scope_kw.value, ast.Constant)
    assert scope_kw.value.value == "customer"


# ---------------------------------------------------------------------------
# Mutation table killers not already covered by the tests above.
# ---------------------------------------------------------------------------


def test_m1_upgrade_triggers_never_admit_on_dispatch_outcome(scan_tree, monkeypatch):
    """M1: if the upgrade trigger set ever gained
    `dispatch.outcome != "claimed"`, a Class-B (usable, unclaimed) document
    would escalate — CASE 2's own assertion (`paddle_rung == "not_attempted"`,
    zero requests) is the kill; restated here under the mutant's own name so
    the mutation table has a one-to-one test to point at."""
    test_case2_usable_unclaimed_never_escalates_to_paddle(scan_tree, monkeypatch)


def test_m16_two_engines_enabled_at_once_is_never_constructed():
    """M16: the worker's constant becoming `{"visual", "paddle"}` is exactly
    what CASE 12's `enabled_extractors` cardinality test (<=1 member) and the
    `WORKER_ENABLED_EXTRACTORS == {"visual"}` pin both kill; this test names
    the mutant directly against the production constant."""
    from webapp.worker import WORKER_ENABLED_EXTRACTORS

    assert WORKER_ENABLED_EXTRACTORS != frozenset({"visual", "paddle"})
