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
from tests.test_escalation_tripwires import _all_asts_for_source, _tree_sources

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
    whatever the Paddle read would have said.

    P21-ROUTING closure (MAJOR-4): with a genuinely CLAIMED, usable Tesseract
    read (the shape this test drives), the escalation is refused by the
    ROUTER, not by `_upgrade_eligible` — `evidence.usable` is True here, so
    `upgrade_triggers` is empty and `EscalationRouter.decide` refuses with
    `no_admitted_trigger` before `_upgrade_eligible` is ever consulted
    (confirmed directly: `test_upgrade_eligible_return_true_survives_a_
    claimed_usable_read` below reproduces that `_upgrade_eligible() ->
    return True` does not change this test's outcome at all). The shape
    `_upgrade_eligible` actually exists to refuse — unusable evidence AND an
    already-claimed payload, where the router DOES admit a trigger — is
    `test_upgrade_eligible_refuses_an_unusable_but_already_claimed_read`,
    immediately below."""
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
    assert row.escalation_refused == "no_admitted_trigger"  # the ROUTER refused it


def test_upgrade_eligible_return_true_survives_a_claimed_usable_read(scan_tree, monkeypatch):
    """Reproduction, kept as a standing negative control: mutating
    `_upgrade_eligible` to `return True` unconditionally does NOT change the
    outcome of the test above — the router already refused before eligibility
    was ever asked. This is the exact shape MAJOR-4 found: the mechanism the
    card credited for CASE 9 is not the one enforcing it here."""
    import discovery.runner as runner_module
    from corpus_artifacts import cached_markdown

    monkeypatch.setattr(runner_module.DiscoveryRunner, "_upgrade_eligible", lambda self, c, p: True)
    claimable = cached_markdown(SCAN_BYTES, ROOT / "tests" / "corpus_cache")
    _tesseract(monkeypatch, claimable)
    monkeypatch.setattr(
        "ocr.paddle_rung.read_document",
        lambda *a, **k: pytest.fail("Paddle must never run: the router refused it first"),
    )
    row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.paddle_rung == "not_attempted"


def test_upgrade_eligible_refuses_an_unusable_but_already_claimed_read(scan_tree, monkeypatch):
    """P21-ROUTING closure (MAJOR-4): the ONE shape `_upgrade_eligible`
    exists to refuse — evidence BELOW the char floor (so the router DOES
    admit `extractor_output_unusable`, unlike the test above) whose analysis
    nonetheless yields a payload (a D-3 analysis-cache-shaped hit: no live
    `Dispatch` was observed this run, i.e. `collector.seen` is False, but a
    payload already exists) — must never reach Paddle. `return True` here
    (RX5) SURVIVES every other test in this module; this is the one that
    dies for it."""
    import discovery.runner as runner_module

    _tesseract(monkeypatch, BELOW_FLOOR)  # unusable -> extractor_output_unusable IS admitted

    def _fake_analyse(self, markdown, collector, sheets=None):
        # No live Dispatch observed (collector.seen stays False) but a
        # payload exists anyway — the D-3-cache-hit shape `_upgrade_eligible`
        # docstring's first bullet names.
        return {"fake": "cached-shaped payload"}, None, True

    monkeypatch.setattr(runner_module.DiscoveryRunner, "_analyse", _fake_analyse)
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.escalation_trigger == "extractor_output_unusable"  # the router DID admit it
    assert row.paddle_rung == "not_attempted"  # but eligibility refused the attempt
    assert row.escalation_extractor == ""  # never even named for THIS attempt
    assert fake.requests == []


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
        if isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
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


# `test_case12_worker_enabled_extractors_keeps_paddle_disabled` pinned the worker's router capability set; the worker
# has no router call and no capability set since the model-code removal (slice S1), so the pin went with its subject.
# The call-site pin below still holds the worker to no Paddle read at all.


def test_case12_webapp_worker_has_no_allow_paddle_ocr_call_site():
    import webapp.worker as worker_module

    tree = ast.parse(inspect.getsource(worker_module))
    offenders = [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.keyword) and node.arg == "allow_paddle_ocr"
    ]
    assert offenders == [], f"webapp/worker.py must never pass allow_paddle_ocr: lines {offenders}"


#: P21-ROUTING closure (MAJOR-2). The exact, reviewed set of files that may
#: ever pass `allow_paddle_ocr=True`, each with the reason it is safe — not
#: merely a set of names, so a third site cannot be added by widening the
#: assertion without a reviewed reason alongside it:
#:
#: * `discovery/runner.py` (`_read_paddle`) — the ONE method that reads a
#:   document and may reach the Paddle rung's `/ocr` endpoint. TWO sites:
#:   the `parse_statement(...)` call inside its `compute()` closure and the
#:   `cached_ocr(...)` call that keys the Paddle partition (the two flags
#:   MUST agree — `cached_ocr`'s own docstring says why).
#: * `tools/train/provenance.py` (inside `_TREE_PROBE`, a subprocess-run
#:   string program) — KEY COMPUTATION ONLY: `ac.ocr_settings_key(force_ocr=
#:   True, ..., allow_paddle_ocr=True)` derives a settings-key fingerprint
#:   for the `paddle_ocr_key` provenance partition. It reads no document,
#:   opens no socket, and cannot reach the Paddle rung at all — confirmed by
#:   reading the call site itself (`ocr_settings_key`, not `parse_statement`
#:   or `read_document`). ONE site.
#:
#: P21-ROUTING closure-2 (MINOR-B): the pin is a COUNT per file, not a set
#: of file names — a second site inside an already-expected file (E7) fails.
EXPECTED_ALLOW_PADDLE_OCR_TRUE_SITES: dict[str, tuple[int, str]] = {
    "discovery/runner.py": (2, "reads a document (_read_paddle: parse_statement + cached_ocr)"),
    "tools/train/provenance.py": (1, "key computation only, no document, no socket (_TREE_PROBE)"),
}


#: The callables that CONSUME the flag: a `**{...}` with a key the scan
#: cannot read is an offender only at one of these (an unrelated
#: `LineBox(**{**dict(line), ...})` in `evidence/` is not a Paddle site).
_ALLOW_PADDLE_OCR_CONSUMERS = frozenset({"parse_statement", "ocr_settings_key", "cached_ocr", "_ocr_extractor"})


def _callee_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _allow_paddle_ocr_sites(sources: list[tuple[str, str]]) -> tuple[dict[str, int], list[str]]:
    """`(sites per file, offenders)` over `sources` (file trees AND embedded
    program strings). A SITE is the keyword `allow_paddle_ocr=True` with a
    literal `True`. An OFFENDER (MINOR-B) is any spelling the scan cannot
    certify as `False`: a non-`Constant` value (`bool(1)`, a call, a name
    other than the same-named parameter), a `Constant` other than
    `True`/`False` (`1`, `"yes"`), a `**{...}` dict-literal unpacking that
    carries the key, a `**{...}` with a computed key at a flag consumer, or
    a local re-binding of the name `allow_paddle_ocr` anywhere (which is
    what would make the one permitted pass-through —
    `allow_paddle_ocr=allow_paddle_ocr`, the parameter plumbing inside
    `webapp/artifact_cache.py`, whose CALLER's keyword is scanned at the
    caller — mean something other than the caller's literal)."""
    by_file: dict[str, int] = {}
    offenders: list[str] = []
    for relative, source in sources:
        for tree in _all_asts_for_source(source):
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Name) and node.id == "allow_paddle_ocr"
                    and isinstance(node.ctx, ast.Store)
                ):
                    offenders.append(f"{relative}:{node.lineno} — the name allow_paddle_ocr is re-bound")
                if not isinstance(node, ast.Call):
                    continue
                callee = _callee_name(node.func)
                for kw in node.keywords:
                    if kw.arg == "allow_paddle_ocr":
                        value = kw.value
                        if isinstance(value, ast.Constant) and value.value is True:
                            by_file[relative] = by_file.get(relative, 0) + 1
                        elif isinstance(value, ast.Constant) and value.value is False:
                            continue
                        elif isinstance(value, ast.Name) and value.id == "allow_paddle_ocr":
                            continue  # the same-named parameter passed through; its caller is scanned
                        else:
                            offenders.append(
                                f"{relative}:{value.lineno} — allow_paddle_ocr= is "
                                f"{ast.dump(value)}, not a literal True/False"
                            )
                    elif kw.arg is None and isinstance(kw.value, ast.Dict):
                        for key in kw.value.keys:
                            readable = isinstance(key, ast.Constant) and isinstance(key.value, str)
                            if readable and key.value == "allow_paddle_ocr":
                                offenders.append(
                                    f"{relative}:{kw.value.lineno} — **{{'allow_paddle_ocr': ...}} "
                                    f"dict-unpacked around the keyword scan"
                                )
                            elif not readable and callee in _ALLOW_PADDLE_OCR_CONSUMERS:
                                offenders.append(
                                    f"{relative}:{kw.value.lineno} — **{{...}} with a computed key "
                                    f"at {callee}(), which the scan cannot read"
                                )
    return by_file, offenders


def _assert_allow_paddle_ocr_sites_pinned(
    sources: list[tuple[str, str]], expected: dict[str, int],
) -> None:
    by_file, offenders = _allow_paddle_ocr_sites(sources)
    assert offenders == [], "\n".join(offenders)
    assert by_file == expected, f"allow_paddle_ocr=True sites per file: {by_file} != {expected}"


def test_case12_allow_paddle_ocr_true_appears_only_at_the_reviewed_call_sites():
    """Repo-wide (production code, `tests/` excluded by `_tracked_python_files`;
    embedded program strings — e.g. `tools/train/provenance.py`'s
    `_TREE_PROBE`, MAJOR-2's own finding — included, indented and f-string
    programs too since MINOR-B): `allow_paddle_ocr=True` appears EXACTLY the
    number of times per file `EXPECTED_ALLOW_PADDLE_OCR_TRUE_SITES` names,
    each for the reason given there — never the webapp (Ruling A), and never
    anywhere that reads a document except `_read_paddle` itself — and no
    spelling the scan cannot certify exists anywhere."""
    _assert_allow_paddle_ocr_sites_pinned(
        _tree_sources(),
        {relative: count for relative, (count, _reason) in EXPECTED_ALLOW_PADDLE_OCR_TRUE_SITES.items()},
    )


#: MINOR-B: the re-review's surviving shapes, each planted into a copy of a
#: file that is ALREADY in the expected set (so only the count or the
#: offender rule can catch it), plus the direct-site spellings.
_KEY_CALL = (
    "import webapp.artifact_cache as ac\n"
    "k = ac.ocr_settings_key(force_ocr=True, allow_local_ocr=False,\n"
    "                        allow_visual_ocr=False, allow_paddle_ocr=True)\n"
)
ALLOW_PADDLE_OCR_PLANTED_SHAPES: dict[str, str] = {
    "E7 second clean site": '\n_SECOND = r"""\n' + _KEY_CALL + '"""\n',
    "E2b indented (dedent-style) string": (
        '\nimport textwrap\n_SECOND = textwrap.dedent("""\n    ' + _KEY_CALL.replace("\n", "\n    ") + '""")\n'
    ),
    "E3b f-string program": '\n_X = 1\n_SECOND = f"""\n' + _KEY_CALL + 'print({_X})\n"""\n',
    "E8b direct **{'allow_paddle_ocr': True}": (
        "\nfrom webapp.artifact_cache import ocr_settings_key\n"
        "_K = ocr_settings_key(force_ocr=True, **{'allow_paddle_ocr': True})\n"
    ),
    "computed dict key": (
        "\nfrom webapp.artifact_cache import ocr_settings_key\n"
        "_N = 'allow_' + 'paddle_ocr'\n_K = ocr_settings_key(force_ocr=True, **{_N: True})\n"
    ),
    "non-Constant value bool(1)": (
        "\nfrom webapp.artifact_cache import ocr_settings_key\n"
        "_K = ocr_settings_key(force_ocr=True, allow_paddle_ocr=bool(1))\n"
    ),
    "non-bool Constant 1": (
        "\nfrom webapp.artifact_cache import ocr_settings_key\n"
        "_K = ocr_settings_key(force_ocr=True, allow_paddle_ocr=1)\n"
    ),
    "a Name value": (
        "\nfrom webapp.artifact_cache import ocr_settings_key\n"
        "_T = True\n_K = ocr_settings_key(force_ocr=True, allow_paddle_ocr=_T)\n"
    ),
    "the same-named parameter re-bound locally": (
        "\nfrom webapp.artifact_cache import ocr_settings_key\n"
        "allow_paddle_ocr = True\n_K = ocr_settings_key(force_ocr=True, allow_paddle_ocr=allow_paddle_ocr)\n"
    ),
}


@pytest.mark.parametrize("shape", sorted(ALLOW_PADDLE_OCR_PLANTED_SHAPES))
def test_allow_paddle_ocr_pin_catches_every_planted_shape(shape):
    """Each shape appended to a COPY of `tools/train/provenance.py` (already
    expected with count 1) fails the pin — by count (a second literal site)
    or by the offender rule (a spelling the scan cannot certify). The tree
    is never touched."""
    real = (ROOT / "tools" / "train" / "provenance.py").read_text(encoding="utf-8")
    planted = real + ALLOW_PADDLE_OCR_PLANTED_SHAPES[shape]
    with pytest.raises(AssertionError):
        _assert_allow_paddle_ocr_sites_pinned(
            [("tools/train/provenance.py", planted)], {"tools/train/provenance.py": 1},
        )


def test_allow_paddle_ocr_pin_is_not_vacuous_on_the_real_files():
    """The negative control: the unmodified files pass with exactly their
    expected counts, so the parametrized failures above are the plants'."""
    for relative, (count, _reason) in EXPECTED_ALLOW_PADDLE_OCR_TRUE_SITES.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        _assert_allow_paddle_ocr_sites_pinned([(relative, source)], {relative: count})


def test_case12_scanned_paddle_and_scanned_visual_never_both_enabled():
    """Two-engine escalation is not possible in this phase: a runner's
    `enabled_extractors` holds at most one member (D4, design item 8).

    MINOR-7: all SIX modes, not four — `profile-only` and `dry-run` are
    structurally just as `<=1` as the other four (the `__init__` expression
    is a single conditional with no mode left unhandled), but a pin that
    exercises only four of six is completeness debt worth closing rather
    than leaving implicit."""
    for mode in ("scanned-visual", "scanned-paddle", "scanned", "digital", "profile-only", "dry-run"):
        runner = DiscoveryRunner(
            Path("."), run_id="t", sink=None, cache=None, dedup=DedupIndex(), mode=mode,
        )
        assert len(runner.enabled_extractors) <= 1, mode


# ---------------------------------------------------------------------------
# P21-ROUTING closure MINOR-4: the `--scanned-paddle` CLI preflight, tested.
# ---------------------------------------------------------------------------


def test_cli_refuses_to_start_when_the_paddle_worker_is_unusable(monkeypatch, tmp_path):
    import shutil

    import discovery.cli as cli
    from ocr.paddle_client import PaddleWorkerStatus

    monkeypatch.setattr(shutil, "which", lambda name: "tesseract")
    monkeypatch.setattr(
        cli, "probe_paddle_ocr",
        lambda **k: PaddleWorkerStatus(available=False, reason="paddle_remote_opt_in_required"),
    )
    monkeypatch.setattr(
        cli, "run",
        lambda *a, **k: pytest.fail("no document may be enumerated when the Paddle worker is unusable"),
    )

    assert cli.main(["--scanned-paddle", "--root", str(tmp_path)]) == 2


def test_cli_paddle_preflight_prints_only_the_closed_token_never_a_host(monkeypatch, tmp_path, capsys):
    import shutil

    import discovery.cli as cli
    from ocr.paddle_client import PaddleWorkerStatus

    monkeypatch.setattr(shutil, "which", lambda name: "tesseract")
    monkeypatch.setattr(
        cli, "probe_paddle_ocr",
        lambda **k: PaddleWorkerStatus(available=False, reason="paddle_config_missing"),
    )
    monkeypatch.setattr(cli, "run", lambda *a, **k: pytest.fail("must not enumerate"))

    cli.main(["--scanned-paddle", "--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert "paddle_config_missing" in captured.err
    assert "discovery: --scanned-paddle cannot start." in captured.err
    # a closed token only — no host/port/user shape anywhere in the message
    for hostile in ("127.0.0.1", "http://", "ssh", ".invalid", "@"):
        assert hostile not in captured.err.lower()


def test_cli_starts_when_the_paddle_worker_is_usable(monkeypatch, tmp_path):
    import shutil

    import discovery.cli as cli
    from ocr.paddle_client import PaddleWorkerStatus

    monkeypatch.setattr(shutil, "which", lambda name: "tesseract")
    monkeypatch.setattr(
        cli, "probe_paddle_ocr",
        lambda **k: PaddleWorkerStatus(available=True, reason="ok", identity={"contract": 1}),
    )

    seen = {}

    def fake_run(root, mode, out_dir, **kwargs):
        seen["mode"] = mode
        return {
            "run_id": "t", "mode": mode, "documents": 0, "processed": 0, "deferred": 0,
            "deferred_reasons": {}, "dispatched": 0, "dispatch": {}, "outcome": {},
            "reasons": {}, "classification": {}, "dedup": {}, "source_path": {},
            "folder_agreement": {}, "label_unmatched_pairs": [], "parsers": {},
            "folders": {}, "unknown_layout_clusters": {}, "declined_clusters": {},
            "crash_clusters": {}, "ambiguity_clusters": {}, "near_miss_parsers": {},
            "truncated_documents": 0, "visual_rung": {}, "paddle_rung": {},
            "escalation_trigger": {}, "escalation_extractor": {},
            "escalation_budget": None, "escalations_used": 0, "cache": {},
            "output_dir": str(out_dir), "template_claim_pairs": [], "parser_id_source": {},
            "dispatch_cached": 0, "dispatch_unavailable": 0, "dispatch_inconclusive": 0,
            "deterministic_coverage": 0.0,
        }

    monkeypatch.setattr(cli, "run", fake_run)
    result = cli.main(["--scanned-paddle", "--root", str(tmp_path), "--quiet"])
    assert result == 0
    assert seen["mode"] == "scanned-paddle"


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
# P21-ROUTING closure MINOR-2: the refusal REASON survives on the row, not
# only the exception class name — the silent-PP-OCRv6 hazard D5 exists to
# catch (`paddle_runtime_mismatch`) is visible per row.
# ---------------------------------------------------------------------------


def test_a_runtime_mismatch_refusal_surfaces_its_reason_on_the_row(scan_tree, monkeypatch):
    _tesseract(monkeypatch, None)  # RECOVERY
    # A worker that answers /health and /version but disagrees with the D5
    # pins on one field (a stand-in for a silently-upgraded PaddleOCR/model):
    # `verify_identity` refuses with reason "paddle_runtime_mismatch" before
    # any /ocr request is sent.
    with FakeWorker(
        identity_overrides={
            "provider": "local", "execution_class": "local_free",
            "paddleocr_version": "9.9.9",
        },
    ) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert row.paddle_rung == "failed"
    assert row.outcome_reason == "ocr_failed"
    assert row.error_type == "PaddleRefused"
    assert row.paddle_refusal_reason == "paddle_runtime_mismatch"
    assert fake.requests == []  # refused before any /ocr request


def test_a_successful_paddle_read_leaves_paddle_refusal_reason_empty(scan_tree, monkeypatch):
    _tesseract(monkeypatch, None)
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        row = _runner(scan_tree, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert row.paddle_rung == "recovered"
    assert row.paddle_refusal_reason == ""


# ---------------------------------------------------------------------------
# P21-ROUTING closure MAJOR-1: a drifted cached OCR entry surfaces on the row
# as `cache_finding`, through the REAL DiscoveryRunner + a real ArtifactCache.
# ---------------------------------------------------------------------------


def test_a_drifted_cache_entry_surfaces_as_cache_finding_on_the_row(scan_tree, monkeypatch, tmp_path):
    from webapp.artifact_cache import (
        CACHE_FINDING_EVIDENCE_DRIFT, cache_key, ocr_settings_key, open_cache,
    )

    cache = open_cache(tmp_path / "data")
    _tesseract(monkeypatch, None)  # RECOVERY

    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        first = _runner(scan_tree, cache=cache, visual_escalation=True).process(
            "BankZ/scan.pdf", "BankZ")
        assert first.paddle_rung == "recovered"
        assert first.cache_finding == ""

        # Corrupt the just-written Paddle OCR artifact directly: rewrite its
        # `pages` so it disagrees with its own stored `evidence` — the drift
        # shape MAJOR-1 exists for.
        input_sha = first.content_sha256
        settings_key = ocr_settings_key(
            force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True,
        )
        key = cache_key("ocr", input_sha, settings_key)
        path = cache._artifact_path("ocr", key)
        import json as _json

        payload = _json.loads(path.read_text(encoding="utf-8"))
        payload["artifact"]["document"]["pages"] = ["a completely different page"]
        path.write_text(_json.dumps(payload), encoding="utf-8")

        second = _runner(scan_tree, cache=cache, visual_escalation=True).process(
            "BankZ/scan.pdf", "BankZ")

    assert second.paddle_rung == "recovered"  # recomputed successfully, not served drifted
    assert second.cache_finding == CACHE_FINDING_EVIDENCE_DRIFT


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


# `test_m16_two_engines_enabled_at_once_is_never_constructed` named mutant M16 against the worker's
# WORKER_ENABLED_EXTRACTORS constant, which left with the worker's router calls (model-code removal, slice S1).


# ---------------------------------------------------------------------------
# P21-ROUTING closure-2 MAJOR-A: `cache_finding` never leaks from one
# document onto a later document processed by the SAME runner.
# ---------------------------------------------------------------------------


def _tesseract_by_name(monkeypatch, texts: dict[str, str | None]) -> None:
    """A per-document Tesseract fake keyed on the file name: `None` (the
    RECOVERY shape, escalates) or a text (Class B when unclaimable)."""
    def fake(pdf_bytes, source_file="", **kwargs):
        text = texts[source_file]
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


@pytest.fixture
def two_scan_tree(tmp_path: Path) -> Path:
    """Two DISTINCT documents: B is the same fixture with a trailing comment
    so its sha differs (the re-review's exact shape)."""
    (tmp_path / "BankZ").mkdir()
    (tmp_path / "BankZ" / "scanA.pdf").write_bytes(SCAN_BYTES)
    (tmp_path / "BankZ" / "scanB.pdf").write_bytes(SCAN_BYTES + b"\n%B-variant\n")
    return tmp_path


def _drift_paddle_artifact(cache, content_sha256: str) -> None:
    from webapp.artifact_cache import cache_key, ocr_settings_key
    import json as _json

    settings_key = ocr_settings_key(
        force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True,
    )
    path = cache._artifact_path("ocr", cache_key("ocr", content_sha256, settings_key))
    payload = _json.loads(path.read_text(encoding="utf-8"))
    payload["artifact"]["document"]["pages"] = ["a completely different page"]
    path.write_text(_json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("order", ["A_then_B", "B_then_A"])
def test_a_cache_finding_never_leaks_onto_a_later_document_on_the_same_runner(
    two_scan_tree, monkeypatch, tmp_path, order,
):
    """MAJOR-A, the re-review's reproduction and its mirror, on ONE
    `DiscoveryRunner` with a real `ArtifactCache`: document A's Paddle
    artifact is drifted (so A's row carries `cached_evidence_drift`);
    document B is Class B (usable, unclaimable — `_read_paddle` never runs
    on it) and its row must carry `""` whether it is processed AFTER the
    drifted A (the leak shape: `_last_paddle_finding` still held A's value)
    or before it. Reproduced at 97ab9cb: B after A → `cached_evidence_drift`
    on B's row; fixed by `_reset_per_document_state()` at the top of
    `process()`."""
    from webapp.artifact_cache import CACHE_FINDING_EVIDENCE_DRIFT, open_cache

    cache = open_cache(tmp_path / "data")
    _tesseract_by_name(monkeypatch, {"scanA.pdf": None, "scanB.pdf": USABLE_UNCLAIMABLE})
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        runner = _runner(two_scan_tree, cache=cache, visual_escalation=True)

        first_a = runner.process("BankZ/scanA.pdf", "BankZ")
        assert first_a.paddle_rung == "recovered" and first_a.cache_finding == ""
        _drift_paddle_artifact(cache, first_a.content_sha256)

        if order == "A_then_B":
            drifted_a = runner.process("BankZ/scanA.pdf", "BankZ")
            b = runner.process("BankZ/scanB.pdf", "BankZ")
        else:
            b = runner.process("BankZ/scanB.pdf", "BankZ")
            drifted_a = runner.process("BankZ/scanA.pdf", "BankZ")
            b_after = runner.process("BankZ/scanB.pdf", "BankZ")
            assert b_after.cache_finding == ""

    assert drifted_a.paddle_rung == "recovered"
    assert drifted_a.cache_finding == CACHE_FINDING_EVIDENCE_DRIFT
    assert b.paddle_rung == "not_attempted"
    assert b.escalation_refused == "no_admitted_trigger"
    assert b.cache_finding == "", "a finding about A landed on B's row"


def test_every_per_document_last_attribute_is_reset_at_the_top_of_process():
    """MAJOR-A's structural half: every `_last_*` class attribute of
    `DiscoveryRunner` (they are all per-document cache dispositions) is
    assigned in `_reset_per_document_state`, and `process()` calls that
    method BEFORE its first `self._read*(` call — so a new `_last_*`
    attribute cannot be added without its reset, and the reset cannot drift
    below a read."""
    import discovery.runner as runner_module

    class_attrs = {
        name for name in vars(DiscoveryRunner)
        if name.startswith("_last_") and not callable(getattr(DiscoveryRunner, name))
    }
    assert class_attrs, "the per-document attributes vanished; re-pin"

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


# ---------------------------------------------------------------------------
# P21-ROUTING closure-2 MINOR-D: a drift followed by a FAILED recompute keeps
# the finding on the row, beside `error_type`.
# ---------------------------------------------------------------------------


def test_a_drift_followed_by_a_failed_recompute_keeps_the_finding_on_the_row(
    scan_tree, monkeypatch, tmp_path,
):
    """A drifted Paddle artifact, then a fake worker that REFUSES connections
    on the recompute: the row records `paddle_rung = failed`, `error_type =
    PaddleTransportError` — AND `cache_finding = cached_evidence_drift`,
    because `cached_ocr` attached the finding to the exception it let
    through. Reproduced at 97ab9cb: `cache_finding == ""` on that row."""
    from webapp.artifact_cache import CACHE_FINDING_EVIDENCE_DRIFT, open_cache

    cache = open_cache(tmp_path / "data")
    _tesseract(monkeypatch, None)  # RECOVERY
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        _local_free_env(monkeypatch, fake.url)
        first = _runner(scan_tree, cache=cache, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")
    assert first.paddle_rung == "recovered"
    _drift_paddle_artifact(cache, first.content_sha256)

    with FakeWorker(
        identity_overrides={"provider": "local", "execution_class": "local_free"},
        fail_mode="connection_refused",
    ) as fake:
        _local_free_env(monkeypatch, fake.url)
        second = _runner(scan_tree, cache=cache, visual_escalation=True).process("BankZ/scan.pdf", "BankZ")

    assert second.paddle_rung == "failed"
    assert second.outcome_reason == "ocr_failed"
    assert second.error_type == "PaddleTransportError"
    assert second.cache_finding == CACHE_FINDING_EVIDENCE_DRIFT


def test_read_visual_records_the_drift_finding_when_its_recompute_fails(scan_tree, monkeypatch, tmp_path):
    """The `_read_visual` mirror of the test above, at the method seam: a
    drifted VISUAL artifact and a `parse_statement` that raises on the
    recompute → the error type is returned AND `_last_visual_finding`
    carries the drift for `_project_cache_finding` to project."""
    import json as _json

    from discovery.runner import MODE_SCANNED_VISUAL
    from ocr.inspect import inspect_pdf
    from webapp.artifact_cache import CACHE_FINDING_EVIDENCE_DRIFT, cache_key, ocr_settings_key, open_cache

    cache = open_cache(tmp_path / "data")
    profile = inspect_pdf(SCAN_BYTES)
    settings_key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True)
    from tests.test_artifact_cache import _doc_with_evidence

    cache.put_ocr(profile.content_sha256, settings_key, _doc_with_evidence())
    path = cache._artifact_path("ocr", cache_key("ocr", profile.content_sha256, settings_key))
    payload = _json.loads(path.read_text(encoding="utf-8"))
    payload["artifact"]["document"]["pages"] = ["drifted"]
    path.write_text(_json.dumps(payload), encoding="utf-8")

    def _raise(*a, **k):
        raise RuntimeError("visual endpoint unreachable")

    monkeypatch.setattr("ocr.pipeline.parse_statement", _raise)
    runner = DiscoveryRunner(
        scan_tree, mode=MODE_SCANNED_VISUAL, run_id="t", sink=None, cache=cache, dedup=DedupIndex(),
    )
    document, markdown, error = runner._read_visual(SCAN_BYTES, "scan.pdf", profile)
    assert (document, markdown, error) == (None, None, "RuntimeError")
    assert runner._last_visual_finding == CACHE_FINDING_EVIDENCE_DRIFT
