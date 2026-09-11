"""P23-WAVE (Phase 2.3, cell W): the resumable evidence-wave runner.

    python -m tools.paddle_wave populations | preflight | run | report

Everything here runs against SYNTHETIC pages rendered from literal strings
(`tests/paddle_synthetic.py`, dates at `SYNTHETIC_YEAR`) and the in-process
`FakeWorker`. No test in this file reads the archive, opens a socket beyond
loopback, or sets an opt-in literal anywhere but inside its own monkeypatched
environment.

Hermeticity, in this file's house style (cell K's idiom, reused by T): the
gitignored `.env` of a developer machine carries REAL `PADDLE_*` connection
variables and `load_dotenv(override=False)` re-injects any that are ABSENT —
so every test blanks every `PADDLE_*` name first and then sets exactly its own.

The mutation table `tools/p23wave_mutation_table.py` names which test kills
which mutant; the docstrings below name it from the other side.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ocr.paddle_config import (
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
)
from tests.paddle_fake_worker import FakeWorker
from tests.paddle_synthetic import build_ledger_page, render_image_pdf, synthetic_paddle_result
from tools.paddle_wave import (
    CONFIGURATIONS,
    DEFERRED_CONFIGURATIONS,
    OUTCOME_EVIDENCE,
    OUTCOME_REFUSED,
    POPULATION_ORDER,
    PRODUCTION_CONFIG,
    DocumentOutcome,
    RetentionAttestation,
    WaveRefused,
    WaveState,
    attest_retention,
    derive_populations,
    main,
    missing_opt_in_literals,
    population_digests,
    refuse_out_of_order,
    resolve_configuration,
    retain_rasters_for,
    run_wave,
    wave_report,
)

ROOT = Path(__file__).resolve().parents[1]
WAVE_TOOL = ROOT / "tools" / "paddle_wave.py"
PARTITION = CONFIGURATIONS[PRODUCTION_CONFIG]["partition"]

_PADDLE_ENV_NAMES = (
    "PADDLE_PROVIDER", "PADDLE_EXECUTION_CLASS", "PADDLE_VAST_HOST", "PADDLE_VAST_SSH_PORT",
    "PADDLE_VAST_SSH_USER", PADDLE_REMOTE_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    "PADDLE_WORKER_URL", "PADDLE_WORKER_PORT", "PADDLE_TUNNEL_LOCAL_PORT", "PADDLE_RUNTIME_DIR",
)


def _blank_paddle(monkeypatch) -> None:
    for name in list(os.environ):
        if name.startswith("PADDLE_"):
            monkeypatch.setenv(name, "")
    for name in _PADDLE_ENV_NAMES:
        monkeypatch.setenv(name, "")


def _remote_paid_env(monkeypatch, worker_url: str, *, remote: bool = True,
                     customer: bool = True) -> None:
    _blank_paddle(monkeypatch)
    monkeypatch.setenv("PADDLE_PROVIDER", "vast.ai")
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", "remote_paid")
    monkeypatch.setenv("PADDLE_VAST_HOST", "test-host.invalid")
    monkeypatch.setenv("PADDLE_VAST_SSH_PORT", "22")
    monkeypatch.setenv("PADDLE_VAST_SSH_USER", "test-user")
    monkeypatch.setenv("PADDLE_WORKER_URL", worker_url)
    if remote:
        monkeypatch.setenv(PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL)
    if customer:
        monkeypatch.setenv(PADDLE_CUSTOMER_DATA_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL)
    monkeypatch.setenv("RECONSTRUCTION_MODE", "off")


BOTH_LITERALS = {
    PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL,
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV: PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
}


# ---------------------------------------------------------------------------
# M10: the runner never reads a page itself
# ---------------------------------------------------------------------------


def test_m10_the_wave_runner_never_imports_the_rung_or_calls_read_document():
    """The whole architecture of this cell in one assertion. The wave decides
    WHICH documents are studied and WHETHER a study may start; the reading is
    the research mode's, through the router the Phase 2.2 cells reviewed. A
    tool that could call `read_document` itself would be a second, unreviewed
    extraction path wearing an orchestrator's name."""
    tree = ast.parse(WAVE_TOOL.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.append(module)
            imported.extend(f"{module}.{alias.name}" for alias in node.names)
    assert not [name for name in imported if name.startswith("ocr.paddle_rung")], imported
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree) if isinstance(node, ast.Call)
    }
    assert "read_document" not in called
    assert "parse_statement" not in called
    source = WAVE_TOOL.read_text(encoding="utf-8")
    assert "paddle_rung" not in source


def test_the_wave_tool_never_names_the_paddle_capability_flag():
    """The other half of M10, and the reason `recorded_evidence_for` reads the
    cache's index instead of recomputing a settings key.

    `tests/test_paddle_routing.py::test_case12_...` pins, repo-wide, the exact
    set of call sites that may name `allow_paddle_ocr` — the boundary that
    keeps "this call can cause a Paddle read" a reviewed property rather than a
    spelling anyone may reach for. `discovery/cli.py` already declined to join
    that set for a PROVENANCE field; an orchestrator that reads no page has
    even less claim to it. Scanned here as well as there so the reason travels
    with the tool: the repo pin says WHAT the set is, this says why this file
    is not in it."""
    tree = ast.parse(WAVE_TOOL.read_text(encoding="utf-8"))
    named = [
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
        for keyword in node.keywords if keyword.arg == "allow_paddle_ocr"
    ]
    assert named == [], f"allow_paddle_ocr= named at lines {named} of {WAVE_TOOL.name}"
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree) if isinstance(node, ast.Call)
    }
    assert "ocr_settings_key" not in called


def _stored_evidence_record(cache, sha: str, settings_key: str, raster_sha: str) -> None:
    """Write ONE OCR cache record for `sha` under `settings_key` whose document
    carries evidence recording `raster_sha` for page 0. Written through the
    cache's own `put` so the INDEX row (`input_sha256`, `settings_key`) is the
    real one `recorded_evidence_for` reads."""
    from evidence.canonical import ExtractionEvidence, PageEvidence, PageFrame, to_json
    from webapp.artifact_cache import STAGE_OCR

    frame = PageFrame.pixel(page_index=0, raster_width_px=2550, raster_height_px=3300,
                            dpi=300.0, pdf_width_pt=612.0, pdf_height_pt=792.0,
                            raster_sha256=raster_sha)
    evidence = ExtractionEvidence(
        document_sha256=sha.lower(), extractor_id="paddle-ocr", model_token="paddle-ocr+ppocrv5",
        pages=(PageEvidence(frame=frame, words=()),),
    )
    cache.put(STAGE_OCR, sha.upper(), settings_key,
              {"document": {"model": "paddle-ocr+ppocrv5", "pages": [""],
                            "page_integrity": [], "page_extractor": ["paddle-ocr+ppocrv5"],
                            "evidence": to_json(evidence), "native_evidence": None,
                            "native_evidence_sha256": None}})


def test_the_retained_raster_is_found_through_the_caches_index_not_a_rebuilt_key(tmp_path):
    """The record is located by the key the RUN recorded, whatever that key is
    — proven by storing it under a settings key this tool could not possibly
    reconstruct. A reconstructed key is a second copy of the read's call shape
    and can drift from it (a DPI default, a stage version, a host whose pins
    load differently); the index cannot."""
    from webapp.artifact_cache import open_cache
    from tools.paddle_wave import recorded_evidence_for

    sha = "B" * 64
    cache = open_cache(tmp_path)
    _stored_evidence_record(cache, sha, "a-settings-key-no-caller-would-guess", "c" * 64)
    evidence = recorded_evidence_for(cache, sha)
    assert evidence is not None
    assert [page.frame.raster_sha256 for page in evidence.pages] == ["c" * 64]
    assert recorded_evidence_for(cache, "D" * 64) is None


def test_two_configurations_in_one_research_directory_are_refused_not_guessed(tmp_path):
    """A second configuration under a second partition pointed at the same
    `--data-dir` makes "which read is this page's raster" ambiguous. Identical
    recorded rasters are not ambiguous — the bytes are the same bytes — and are
    allowed; DIFFERENT ones are refused, because a sha-named archive cannot
    show later that one configuration's pixels were written under the other's
    name."""
    from webapp.artifact_cache import open_cache
    from tools.paddle_wave import recorded_evidence_for

    sha = "E" * 64
    cache = open_cache(tmp_path)
    _stored_evidence_record(cache, sha, "key-of-configuration-one", "c" * 64)
    _stored_evidence_record(cache, sha, "key-of-configuration-two", "c" * 64)
    assert recorded_evidence_for(cache, sha) is not None  # same bytes, no ambiguity

    _stored_evidence_record(cache, sha, "key-of-configuration-three", "d" * 64)
    with pytest.raises(WaveRefused, match="ambiguous research data directory"):
        recorded_evidence_for(cache, sha)


def test_m9_no_cost_rate_price_or_billing_token_anywhere_in_the_tool():
    """D5: cost is out of scope. The tool's CODE is scanned, not only its
    report keys, because a cost column starts life as a variable name — over
    `_code_lines`, the same comment-and-docstring-stripped view the
    no-hardcodes scans use, so the prose that NAMES the forbidden tokens (this
    file's, and the tool's own) does not make the scan unsatisfiable."""
    from tests.test_no_statement_hardcodes import _code_lines

    for number, line in _code_lines(WAVE_TOOL):
        lowered = line.lower()
        for token in ("cost", "price", "usd", "billing", "invoice", "dollar", "_rate"):
            assert token not in lowered, f"{number}: {token} in {line.strip()!r}"


# ---------------------------------------------------------------------------
# M3 / case 5: the two literals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("present,missing", [
    (PADDLE_REMOTE_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_ENV),
    (PADDLE_CUSTOMER_DATA_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_ENV),
])
def test_m3_each_literal_alone_refuses_and_names_the_other(present, missing):
    """M3's killer. One literal is not an opt-in: a preflight that accepted
    either alone would let a half-authorized command send a customer page."""
    environ = {present: BOTH_LITERALS[present]}
    assert missing_opt_in_literals(environ) == [missing]
    assert missing_opt_in_literals(dict(BOTH_LITERALS)) == []
    assert missing_opt_in_literals({}) == [PADDLE_REMOTE_OPT_IN_ENV,
                                           PADDLE_CUSTOMER_DATA_OPT_IN_ENV]


def test_a_near_miss_literal_value_is_not_an_opt_in():
    for name in BOTH_LITERALS:
        environ = dict(BOTH_LITERALS, **{name: BOTH_LITERALS[name].lower()})
        assert missing_opt_in_literals(environ) == [name]
        environ = dict(BOTH_LITERALS, **{name: "yes"})
        assert missing_opt_in_literals(environ) == [name]


def test_the_refusal_never_prints_the_literal_that_lifts_it(tmp_path, monkeypatch, capsys):
    _blank_paddle(monkeypatch)
    population = tmp_path / "CTRL.shas"
    population.write_text("A" * 64 + "\n", encoding="utf-8")
    code = main(["preflight", "--population", str(population),
                 "--data-dir", str(tmp_path / "research")])
    assert code == 2
    err = capsys.readouterr().err
    assert PADDLE_REMOTE_OPT_IN_ENV in err and PADDLE_CUSTOMER_DATA_OPT_IN_ENV in err
    assert PADDLE_REMOTE_OPT_IN_LITERAL not in err
    assert PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL not in err


# ---------------------------------------------------------------------------
# M11 / case 1: T's containment door, through this tool
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [
    "webapp_data", "webapp_data/research", ".claude/recovery/webapp_data_train12_cold",
    ".claude/recovery/webapp_data_train12_cold/sub", "somewhere/webapp_data_train9_cold",
])
def test_m11_a_production_or_cold_cache_data_dir_is_refused_through_the_wave(
    tmp_path, monkeypatch, capsys, bad,
):
    """M11's killer. The wave reuses T's door rather than re-deriving it, so
    there is exactly one definition of "a research run writes to its own
    directory" and a second one cannot drift away from it."""
    _blank_paddle(monkeypatch)
    for name, value in BOTH_LITERALS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path / "never_the_one_under_test"))
    population = tmp_path / "CTRL.shas"
    population.write_text("A" * 64 + "\n", encoding="utf-8")
    assert main(["preflight", "--population", str(population),
                 "--data-dir", str(ROOT / bad)]) == 2
    err = capsys.readouterr().err
    assert "production" in err or "recovery" in err, err


def test_a_research_directory_of_its_own_is_accepted(tmp_path, monkeypatch, capsys):
    _blank_paddle(monkeypatch)
    for name, value in BOTH_LITERALS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path / "prod"))
    population = tmp_path / "CTRL.shas"
    population.write_text("A" * 64 + "\n", encoding="utf-8")
    assert main(["preflight", "--population", str(population),
                 "--data-dir", str(tmp_path / "research_data")]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["documents"] == 1 and printed["partition"] == PARTITION
    assert printed["predecessors_complete"] == []


# ---------------------------------------------------------------------------
# The configuration registry: this cell runs the production block only
# ---------------------------------------------------------------------------


def test_the_only_configuration_this_cell_runs_is_the_production_block():
    assert set(CONFIGURATIONS) == {PRODUCTION_CONFIG}
    assert resolve_configuration(PRODUCTION_CONFIG)["partition"] == PARTITION


@pytest.mark.parametrize("deferred", sorted(DEFERRED_CONFIGURATIONS))
def test_a_deferred_configuration_is_refused_by_name_with_its_owner(deferred):
    """An A/B configuration must not silently run the production pins under
    another partition's name. The refusal says who owns it."""
    with pytest.raises(WaveRefused, match="cell V"):
        resolve_configuration(deferred)


def test_an_unknown_configuration_is_refused():
    with pytest.raises(WaveRefused, match="unknown configuration"):
        resolve_configuration("paddle-v9-imaginary")


def test_the_research_partition_id_is_the_configuration_block_name():
    """Ocean's ruling of 2026-09-11. The umbrella card's `research/paddle-v5-prod`
    was prose the partition shape cannot carry, and a `research-` prefixed
    rewrite of it — shape-legal — is NOT the ruled id either: the id IS the
    configuration block's name. One configuration, one partition, one spelling;
    what makes a partition research is that a run carries one at all, which
    `telemetry/run_of_record.py` refuses on, never how it is spelled."""
    for name, block in CONFIGURATIONS.items():
        assert block["partition"] == name


def test_the_partition_id_matches_the_shape_the_research_mode_admits():
    """`research/paddle-v5-prod` cannot be a partition id: the pattern admits
    no separator. The ruled id is the configuration block's own name (pinned
    just above), and it lives in one place."""
    import re

    from discovery.runner import RESEARCH_PARTITION_PATTERN

    for block in CONFIGURATIONS.values():
        assert re.fullmatch(RESEARCH_PARTITION_PATTERN, block["partition"])


# ---------------------------------------------------------------------------
# M7 / case 8 / D3: the control sample first
# ---------------------------------------------------------------------------


def _populations_dir(tmp_path: Path, **contents: list[str]) -> Path:
    directory = tmp_path / "populations"
    directory.mkdir(parents=True, exist_ok=True)
    for name, shas in contents.items():
        (directory / f"{name}.shas").write_text(
            f"# {name}\n" + "\n".join(shas) + "\n", encoding="utf-8")
    return directory


def _state_with(data_dir: Path, name: str, shas: list[str], outcome: str) -> WaveState:
    state = WaveState(population_name=name, partition=PARTITION)
    for sha in shas:
        state.record(sha, DocumentOutcome(outcome=outcome, reason="" if outcome == OUTCOME_EVIDENCE
                                          else "paddle_worker_unreachable"))
    state.save(WaveState.path_for(data_dir, PARTITION, name))
    return state


def test_m7_u755_refuses_to_start_while_the_control_sample_has_an_unattempted_document(tmp_path):
    """M7's killer. The order is a property of the evidence: the agreement
    baseline and the false-accept instrument are calibrated on the control
    sample BEFORE an unresolved document is read."""
    ctrl = ["A" * 64, "B" * 64]
    directory = _populations_dir(tmp_path, CTRL=ctrl, U755=["C" * 64], SLICE=["D" * 64])
    data_dir = tmp_path / "research"
    _state_with(data_dir, "CTRL", ctrl[:1], OUTCOME_EVIDENCE)
    with pytest.raises(WaveRefused, match="CTRL still has 1"):
        refuse_out_of_order("U755", data_dir=data_dir, partition=PARTITION,
                            populations_dir=directory)


def test_the_control_sample_itself_has_no_predecessor_to_wait_for(tmp_path):
    directory = _populations_dir(tmp_path, CTRL=["A" * 64])
    assert refuse_out_of_order("CTRL", data_dir=tmp_path / "research", partition=PARTITION,
                               populations_dir=directory) == []


def test_a_refused_document_counts_as_attempted_for_the_order_rule(tmp_path):
    """A permanently unreadable control document must not make the rule
    unsatisfiable: it HAS had its controlled opportunity and its refusal is
    recorded. `pending` and `unattempted` are different questions on purpose."""
    ctrl = ["A" * 64, "B" * 64]
    directory = _populations_dir(tmp_path, CTRL=ctrl, U755=["C" * 64])
    data_dir = tmp_path / "research"
    state = _state_with(data_dir, "CTRL", ctrl[:1], OUTCOME_EVIDENCE)
    state.record(ctrl[1], DocumentOutcome(outcome=OUTCOME_REFUSED, reason="ocr_failed"))
    state.save(WaveState.path_for(data_dir, PARTITION, "CTRL"))
    assert refuse_out_of_order("U755", data_dir=data_dir, partition=PARTITION,
                               populations_dir=directory) == ["CTRL"]
    # ... and it is still PENDING, so a later session retries it (M12)
    assert state.pending(ctrl) == [ctrl[1]]
    assert state.unattempted(ctrl) == []


def test_the_slice_waits_for_both_earlier_populations(tmp_path):
    directory = _populations_dir(tmp_path, CTRL=["A" * 64], U755=["B" * 64], SLICE=["C" * 64])
    data_dir = tmp_path / "research"
    _state_with(data_dir, "CTRL", ["A" * 64], OUTCOME_EVIDENCE)
    with pytest.raises(WaveRefused, match="U755 still has 1"):
        refuse_out_of_order("SLICE", data_dir=data_dir, partition=PARTITION,
                            populations_dir=directory)
    _state_with(data_dir, "U755", ["B" * 64], OUTCOME_EVIDENCE)
    assert refuse_out_of_order("SLICE", data_dir=data_dir, partition=PARTITION,
                               populations_dir=directory) == ["CTRL", "U755"]


def test_a_predecessor_run_under_a_different_partition_does_not_satisfy_the_order(tmp_path):
    """"That evidence was not produced under this configuration" is the
    honest answer: the state file is per partition by construction."""
    directory = _populations_dir(tmp_path, CTRL=["A" * 64], U755=["B" * 64])
    data_dir = tmp_path / "research"
    _state_with(data_dir, "CTRL", ["A" * 64], OUTCOME_EVIDENCE)
    with pytest.raises(WaveRefused, match="CTRL still has 1"):
        refuse_out_of_order("U755", data_dir=data_dir, partition="research-somewhere-else",
                            populations_dir=directory)


# ---------------------------------------------------------------------------
# M12: the state file and what "done" means
# ---------------------------------------------------------------------------


def test_m12_a_refused_sha_stays_pending_so_a_resume_never_reads_past_it(tmp_path):
    """M12's killer. A state that treated a refusal as finished would resume
    PAST a document whose only record is that something went wrong, and the
    wave would report a population it did not read."""
    population = ["A" * 64, "B" * 64, "C" * 64]
    state = WaveState(population_name="CTRL", partition=PARTITION)
    state.record(population[0], DocumentOutcome(outcome=OUTCOME_EVIDENCE, pages=2))
    state.record(population[1], DocumentOutcome(outcome=OUTCOME_REFUSED,
                                                reason="paddle_runtime_mismatch", pages=3))
    assert state.pending(population) == [population[1], population[2]]
    assert state.unattempted(population) == [population[2]]
    counts = state.counts()
    assert counts == {"attempted": 2, "evidence": 1, "refused": 1,
                      "pages_evidence": 2, "pages_refused": 3}
    assert state.refusals_by_reason() == {"paddle_runtime_mismatch": 1}


def test_the_state_outcome_vocabulary_is_closed():
    state = WaveState()
    with pytest.raises(WaveRefused, match="third state"):
        state.record("A" * 64, DocumentOutcome(outcome="probably_fine"))


def test_the_state_round_trips_and_refuses_a_version_it_does_not_understand(tmp_path):
    path = tmp_path / "s.json"
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.record("A" * 64, DocumentOutcome(outcome=OUTCOME_EVIDENCE, pages=1, chunk=0))
    state.save(path)
    restored = WaveState.load(path)
    assert restored.documents["A" * 64].pages == 1
    assert restored.partition == PARTITION
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(WaveRefused, match="refusing to resume"):
        WaveState.load(path)


def test_a_state_built_for_another_population_is_refused_on_resume(tmp_path, monkeypatch):
    _blank_paddle(monkeypatch)
    for name, value in BOTH_LITERALS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path / "prod"))
    data_dir = tmp_path / "research"
    directory = _populations_dir(tmp_path, CTRL=["A" * 64])
    state = WaveState(population_name="CTRL", partition=PARTITION,
                      population_set_sha256="0" * 64)
    state.save(WaveState.path_for(data_dir, PARTITION, "CTRL"))
    with pytest.raises(WaveRefused, match="different population"):
        run_wave(population_file=directory / "CTRL.shas", population_name="CTRL",
                 populations_dir=directory, config=PRODUCTION_CONFIG, data_dir=data_dir,
                 out_dir=tmp_path / "out", root=tmp_path / "root")


# ---------------------------------------------------------------------------
# M8 / case 12: the retention attestation
# ---------------------------------------------------------------------------


class _FakeSettings:
    """Enough `PaddleSettings` surface for the masker and the SSH builder."""

    vast_host = "fake-host.invalid"
    vast_ssh_user = "fake-user"
    vast_ssh_port = 22
    worker_token = "fake-token"


class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


CLEAN_INSTANCE = "PROC=0\nPIDFILE=0\nIMAGES=0\nREQUESTS=0\nOTHER=0\nTMPIMG=0\n"


def _ssh_runner(output: str, returncode: int = 0):
    seen: list[list[str]] = []

    def runner(args, **kwargs):
        seen.append(list(args))
        return _FakeCompleted(output, returncode)

    runner.seen = seen  # type: ignore[attr-defined]
    return runner


def test_the_attestation_passes_only_on_a_clean_stopped_instance():
    runner = _ssh_runner(CLEAN_INSTANCE)
    attestation = attest_retention(_FakeSettings(), runner=runner, retention_declared=True)
    assert attestation.passed
    assert attestation.inspected and not attestation.worker_process_alive
    # it inspected over SSH, and the command it ran names the worker directory
    assert runner.seen and runner.seen[0][0] == "ssh"
    assert "paddle_worker.py" in runner.seen[0][-1]


@pytest.mark.parametrize("output,why", [
    ("PROC=1\nPIDFILE=0\nIMAGES=0\nREQUESTS=0\nOTHER=0\n", "a worker still running"),
    ("PROC=0\nPIDFILE=1\nIMAGES=0\nREQUESTS=0\nOTHER=0\n", "a pidfile left behind"),
    ("PROC=0\nPIDFILE=0\nIMAGES=3\nREQUESTS=0\nOTHER=0\n", "page bytes on disk"),
    ("PROC=0\nPIDFILE=0\nIMAGES=0\nREQUESTS=2\nOTHER=0\n", "request artefacts"),
    ("PROC=0\nPIDFILE=0\nIMAGES=0\nREQUESTS=0\nOTHER=5\n", "unexpected files"),
])
def test_m8_a_fake_ssh_runner_that_lists_a_leftover_fails_the_attestation(output, why):
    """M8's killer. An attestation that reported `none` because the worker
    said so, without looking, would pass every one of these."""
    attestation = attest_retention(_FakeSettings(), runner=_ssh_runner(output),
                                   retention_declared=True)
    assert not attestation.passed, why
    assert attestation.inspected


def test_m8_an_inspection_that_could_not_run_fails_closed():
    """"We could not check" and "there was nothing there" are the same
    silence; only one of them is safe."""
    assert not attest_retention(_FakeSettings(), runner=_ssh_runner("", returncode=255),
                                retention_declared=True).inspected
    assert not attest_retention(_FakeSettings(), runner=_ssh_runner("", returncode=255),
                                retention_declared=True).passed
    assert not attest_retention(_FakeSettings(), runner=_ssh_runner("PROC=0\n"),
                                retention_declared=True).passed

    def explode(args, **kwargs):
        raise OSError("boom")

    failed = attest_retention(_FakeSettings(), runner=explode, retention_declared=True)
    assert not failed.passed and not failed.inspected
    assert failed.error and "boom" not in failed.error


def test_a_worker_that_does_not_declare_retention_fails_even_on_a_clean_instance():
    attestation = attest_retention(_FakeSettings(), runner=_ssh_runner(CLEAN_INSTANCE),
                                   retention_declared=False)
    assert attestation.inspected and not attestation.passed


def test_the_attestation_record_is_closed_and_names_no_path():
    record = RetentionAttestation(
        retention_declared=True, inspected=True, worker_process_alive=False,
        pidfile_present=False, request_artefacts=0, page_byte_files=0, unexpected_files=0,
    ).as_record()
    assert set(record) == {
        "retention_declared", "inspected", "worker_process_alive", "pidfile_present",
        "request_artefacts", "page_byte_files", "unexpected_files", "temp_image_files",
        "error", "passed",
    }
    for value in record.values():
        assert isinstance(value, (bool, int, str))


def test_the_attestation_output_is_masked_before_it_is_parsed(monkeypatch):
    """A remote command's stdout is remote text. It goes through the lifecycle
    tool's masker before anything here reads it, so a host that appeared in an
    error line could not reach a log."""
    import tools.paddle_vast as vast

    settings = _FakeSettings()
    masked = vast.mask_text(f"PROC=0 {settings.vast_host} {settings.vast_ssh_user}", settings)
    assert settings.vast_host not in masked and settings.vast_ssh_user not in masked


# ---------------------------------------------------------------------------
# The lifecycle: the session token is minted by `start`, so the settings in
# hand are stale from that moment until they are re-read
# ---------------------------------------------------------------------------


def test_the_lifecycle_stops_deploys_starts_and_then_RE_READS_the_session_token(monkeypatch):
    """`start` mints the per-session worker token and writes it to the
    gitignored runtime directory. A lifecycle that kept the settings object it
    loaded BEFORE that would authenticate as nobody for the rest of the
    session — every later call 401s and the wave reports an unusable worker it
    had just started. The re-read is the fix; this pins it, and pins the stop
    that precedes the deploy (without it a worker still alive from an earlier
    session keeps the port and answers with the OLD token, so a token rotation
    would silently not take effect)."""
    import tools.paddle_vast as vast
    from tools.paddle_wave import Lifecycle, WaveLog

    calls: list[str] = []
    stale, fresh = _FakeSettings(), _FakeSettings()
    stale.worker_token = "stale"
    fresh.worker_token = "fresh"
    stale.tunnel_local_port = fresh.tunnel_local_port = 18765
    stale.worker_port = fresh.worker_port = 8765
    available = {"value": False}

    monkeypatch.setattr(vast, "cmd_check", lambda s, **k: calls.append("check") or
                        {"versions_match_pins": True, "gpu": "a GPU",
                         "remote_paddleocr_version": "3.7.0"})
    monkeypatch.setattr(vast, "_port_listening", lambda port: True)
    monkeypatch.setattr(vast, "cmd_stop", lambda s, **k: calls.append("stop") or {})
    monkeypatch.setattr(vast, "cmd_deploy", lambda s, **k: calls.append("deploy") or
                        {"scp_ok": True, "self_check_ok": True})

    def start(settings, **kwargs):
        calls.append("start")
        available["value"] = True
        return {}

    monkeypatch.setattr(vast, "cmd_start", start)
    monkeypatch.setattr(vast, "cmd_status", lambda s, **k: calls.append(f"status:{s.worker_token}") or
                        {"probe": {"available": available["value"], "reason": "ok", "error_type": None},
                         "tunnel_running": True})
    monkeypatch.setattr("ocr.paddle_config.load_paddle_settings", lambda *a, **k: fresh)
    monkeypatch.setattr("ocr.paddle_client.PaddleClient",
                        lambda settings, **k: type("C", (), {"version": lambda self: {"retention": "none"}})())

    record = Lifecycle(settings=stale, log=WaveLog(None)).up()
    assert record["retention_declared"] is True
    assert calls == ["check", "status:stale", "stop", "deploy", "start", "status:fresh"]


@pytest.mark.parametrize("check,expected", [
    ({"versions_match_pins": False, "gpu": None, "remote_paddleocr_version": None},
     "did not answer"),
    ({"versions_match_pins": False, "gpu": "a GPU", "remote_paddleocr_version": "9.9.9"},
     "do not match the pins"),
])
def test_an_unreachable_instance_and_a_drifted_one_are_different_refusals(
    monkeypatch, check, expected,
):
    """An instance that could not be REACHED and one whose model pins DRIFTED
    are different facts with different operator actions — start or
    re-provision the machine, versus review an upgrade that actually happened.
    `cmd_check` reports both as `versions_match_pins: False`, so the lifecycle
    tells them apart by whether anything on the instance answered at all.
    Without this, a stopped instance is reported as a silent PP-OCRv6 hazard
    and the next operator goes looking for an upgrade that never occurred."""
    import tools.paddle_vast as vast
    from tools.paddle_wave import Lifecycle, WaveLog

    monkeypatch.setattr(vast, "cmd_check", lambda s, **k: dict(check))
    with pytest.raises(WaveRefused, match=expected):
        Lifecycle(settings=_FakeSettings(), log=WaveLog(None)).up()


# ---------------------------------------------------------------------------
# Card item 5: the populations
# ---------------------------------------------------------------------------


def _synthetic_run_dir(tmp_path: Path) -> Path:
    """A three-row rows.csv in the run of record's own column shape."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    columns = ["relative_path", "folder_label", "content_sha256", "page_count",
               "outcome_class", "source_path"]
    rows = [
        ["F/one.pdf", "F", "1" * 64, "3", "validated", "local_tesseract"],
        ["F/two.pdf", "F", "2" * 64, "5", "validated", "native"],
        ["G/three.pdf", "G", "3" * 64, "9", "validated", "native"],
        ["G/four.pdf", "G", "4" * 64, "2", "failed", "native"],
        ["G/five.pdf", "G", "5" * 64, "1", "review", "none"],
    ]
    with (run_dir / "rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)
    return run_dir


def test_the_populations_are_derived_from_the_rows_and_nothing_else(tmp_path):
    run_dir = _synthetic_run_dir(tmp_path)
    derived = derive_populations(run_dir, ctrl_target=3, pinned={"a": "2" * 64, "b": "9" * 64})
    assert derived["CTRL"]["shas"][0] == "1" * 64  # the Tesseract-validated one, always
    assert len(derived["CTRL"]["shas"]) == 3
    # unresolved = every distinct sha with NO validated row: `failed` and `review` alike
    assert derived["U755"]["shas"] == ["4" * 64, "5" * 64]
    # the slice is the audited manifest intersected with what the run can reach
    assert derived["SLICE"]["shas"] == ["2" * 64]
    assert derived["SLICE"]["strata"]["unreachable"] == 1


def test_the_control_sample_is_reproducible_from_its_seed(tmp_path):
    run_dir = _synthetic_run_dir(tmp_path)
    first = derive_populations(run_dir, ctrl_target=2, seed="one", pinned={})
    again = derive_populations(run_dir, ctrl_target=2, seed="one", pinned={})
    assert first["CTRL"]["shas"] == again["CTRL"]["shas"]
    other = derive_populations(run_dir, ctrl_target=2, seed="two", pinned={})
    assert set(other["CTRL"]["shas"]) <= {"1" * 64, "2" * 64, "3" * 64}


def test_the_control_sample_keeps_every_tesseract_validated_document_whatever_the_target(tmp_path):
    """The scanned control is the population where a Paddle read has a
    directly comparable predecessor; it is never sampled away."""
    run_dir = _synthetic_run_dir(tmp_path)
    for target in (1, 2, 3, 50):
        derived = derive_populations(run_dir, ctrl_target=target, pinned={})
        assert "1" * 64 in derived["CTRL"]["shas"]


def test_a_population_file_reports_two_digests_and_names_no_verdict(tmp_path):
    run_dir = _synthetic_run_dir(tmp_path)
    from tools.paddle_wave import write_population_files

    derived = derive_populations(run_dir, ctrl_target=3, pinned={"a": "2" * 64})
    digests = write_population_files(derived, tmp_path / "pop", run_dir=run_dir, seed="seed")
    for name in POPULATION_ORDER:
        text = (tmp_path / "pop" / f"{name}.shas").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("#"):
                continue
            assert len(line.strip()) == 64  # a bare sha, never a sha with a verdict beside it
        assert digests[name]["set_sha256"] == population_digests(
            tmp_path / "pop" / f"{name}.shas")["set_sha256"]
    # the set digest survives a comment edit; the file digest does not
    path = tmp_path / "pop" / "CTRL.shas"
    before = population_digests(path)
    path.write_text("# another comment\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    after = population_digests(path)
    assert after["set_sha256"] == before["set_sha256"]
    assert after["file_sha256"] != before["file_sha256"]


def test_a_population_naming_a_held_out_document_is_refused_by_count(tmp_path):
    from tools.paddle_wave import refuse_holdout_members

    held = frozenset({("7" * 64)[:16]})
    with pytest.raises(WaveRefused, match="1 of this population") as excinfo:
        refuse_holdout_members(["7" * 64, "8" * 64], held=held)
    assert "7" * 64 not in str(excinfo.value)
    refuse_holdout_members(["8" * 64], held=held)


# ---------------------------------------------------------------------------
# The synthetic end-to-end wave: the FakeWorker, the real research mode
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_wave(tmp_path: Path) -> dict:
    """Two one-page image-only SYNTHETIC documents in a root of their own, a
    populations directory naming them as CTRL, and a research data directory.
    Nothing here comes from a real document."""
    from ocr.inspect import inspect_pdf

    root = tmp_path / "root"
    (root / "Synth").mkdir(parents=True)
    pages = {}
    shas = {}
    for name, rows in (("one.pdf", 4), ("two.pdf", 6)):
        page = build_ledger_page(rows)
        pdf_bytes = render_image_pdf(page)
        (root / "Synth" / name).write_bytes(pdf_bytes)
        pages[name] = page
        shas[name] = inspect_pdf(pdf_bytes).content_sha256
    populations = _populations_dir(tmp_path, CTRL=[shas["one.pdf"], shas["two.pdf"]])
    return {
        "root": root, "pages": pages, "shas": shas, "populations": populations,
        "data_dir": tmp_path / "research_data", "out": tmp_path / "out", "tmp": tmp_path,
    }


def _wave(fixture: dict, **overrides):
    kwargs = dict(
        population_file=fixture["populations"] / "CTRL.shas", population_name="CTRL",
        populations_dir=fixture["populations"], config=PRODUCTION_CONFIG,
        data_dir=fixture["data_dir"], out_dir=fixture["out"], root=fixture["root"],
        chunk_size=1, skip_baseline=True,
    )
    kwargs.update(overrides)
    return run_wave(**kwargs)


@pytest.mark.skipif(shutil.which("tesseract") is None,
                    reason="the research mode's offline ladder needs tesseract on PATH")
def test_the_synthetic_wave_reads_every_page_once_resumes_and_then_hits_the_cache(
    synthetic_wave, monkeypatch,
):
    """The card's whole end-to-end proof, in one run: one request per page, a
    killed chunk resumed from disk, and a re-read served entirely from the
    research partition with sha equality.

    * **M1 / D4** — the count identity: every document of the population is
      attempted or refused, and nothing is silently skipped.
    * **M6 / case 2** — a population sha is read ONCE per configuration: the
      second pass makes no request and the evidence sha is unchanged.
    * **M12** — the resume continues from the state file, not from the start.
    """
    fixture = synthetic_wave
    pages = fixture["pages"]

    def result_for(page_index, image_bytes):
        return synthetic_paddle_result(pages["one.pdf"])

    with FakeWorker(result_for=result_for) as fake:
        _remote_paid_env(monkeypatch, fake.url)
        monkeypatch.setenv("WEBAPP_DATA_DIR", str(fixture["tmp"] / "never_used_prod"))
        # ONE chunk only: the wave stops with the second document untouched,
        # exactly as a spend-limited agent would leave it.
        first = _wave(fixture, max_chunks=1)
        assert first["session"]["chunks"] == 1
        state = WaveState.load(WaveState.path_for(fixture["data_dir"], PARTITION, "CTRL"))
        assert state.counts()["attempted"] == 1
        assert len(fake.requests) == 1  # one request, one page

        # RESUME: a fresh call reads the state off disk and continues.
        second = _wave(fixture)
        assert second["session"]["chunks"] == 1  # only the remaining document
        assert len(fake.requests) == 2

        state = WaveState.load(WaveState.path_for(fixture["data_dir"], PARTITION, "CTRL"))
        counts = state.counts()
        assert counts["attempted"] == 2 == counts["evidence"] + counts["refused"]
        assert counts["evidence"] == 2, state.refusals_by_reason()
        assert counts["pages_evidence"] == 2

        evidence_shas = _evidence_shas(fixture["data_dir"], fixture["shas"].values())

        # A THIRD pass with the state removed: every document is pending again,
        # the chunk runs, and not one request is made.
        WaveState.path_for(fixture["data_dir"], PARTITION, "CTRL").unlink()
        third = _wave(fixture)
        assert len(fake.requests) == 2, "a document was read twice under one configuration"
        assert third["session"]["documents"] == 2

    assert _evidence_shas(fixture["data_dir"], fixture["shas"].values()) == evidence_shas
    hits = sum(int(chunk.get("cache_hits") or 0) for chunk in
               WaveState.load(WaveState.path_for(fixture["data_dir"], PARTITION,
                                                 "CTRL")).chunks)
    assert hits == 2


@pytest.mark.skipif(shutil.which("tesseract") is None,
                    reason="the research mode's offline ladder needs tesseract on PATH")
def test_d4_every_document_is_attempted_or_refused_when_the_worker_fails(
    synthetic_wave, monkeypatch,
):
    """M1's killer, and D4's whole statement. The worker answers every request
    with an error; not one document produces evidence; and the population count
    still equals attempted, which equals evidence plus refused. A wave that
    SKIPPED a document on an exception would report a smaller population than
    the one it named — the difference between "we read 755" and "we read the
    ones that worked"."""
    fixture = synthetic_wave
    with FakeWorker(fail_mode="http_500") as fake:
        _remote_paid_env(monkeypatch, fake.url)
        monkeypatch.setenv("WEBAPP_DATA_DIR", str(fixture["tmp"] / "never_used_prod"))
        _wave(fixture)
    state = WaveState.load(WaveState.path_for(fixture["data_dir"], PARTITION, "CTRL"))
    counts = state.counts()
    assert counts["attempted"] == 2, "a document was skipped rather than recorded"
    assert counts["attempted"] == counts["evidence"] + counts["refused"]
    assert counts["evidence"] == 0 and counts["refused"] == 2
    # every refusal carries a reason from the row's own closed vocabulary
    reasons = state.refusals_by_reason()
    assert sum(reasons.values()) == 2
    assert "unrecorded" not in reasons, reasons
    # and the whole population is pending again, because nothing was learned
    population = {sha.upper() for sha in fixture["shas"].values()}
    assert set(state.pending(population)) == population
    assert state.unattempted(population) == []


def _evidence_shas(data_dir: Path, shas) -> dict[str, str]:
    from webapp.artifact_cache import ocr_settings_key, open_cache

    cache = open_cache(Path(data_dir))
    key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
                           allow_paddle_ocr=True, research_partition=PARTITION)
    found = {}
    for sha in shas:
        hit, record = cache.get_ocr(sha.upper(), key)
        if hit and record and record.get("evidence"):
            found[sha.upper()] = record["evidence"]["evidence_sha256"]
    return found


@pytest.mark.skipif(shutil.which("tesseract") is None,
                    reason="the research mode's offline ladder needs tesseract on PATH")
def test_the_wave_retains_one_raster_per_page_proven_against_the_evidence(
    synthetic_wave, monkeypatch,
):
    """D2 / case 3. The retained PNG is not merely "a render of that page": its
    sha256 equals the `raster_sha256` the immutable evidence already records,
    so it is provably the image the worker saw."""
    fixture = synthetic_wave
    pages = fixture["pages"]
    with FakeWorker(result_for=lambda i, b: synthetic_paddle_result(pages["one.pdf"])) as fake:
        _remote_paid_env(monkeypatch, fake.url)
        monkeypatch.setenv("WEBAPP_DATA_DIR", str(fixture["tmp"] / "never_used_prod"))
        _wave(fixture)
    raster_root = fixture["data_dir"] / "rasters"
    assert raster_root.is_dir()
    from evidence.canonical import from_json
    from webapp.artifact_cache import ocr_settings_key, open_cache

    cache = open_cache(fixture["data_dir"])
    key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
                           allow_paddle_ocr=True, research_partition=PARTITION)
    for sha in fixture["shas"].values():
        hit, record = cache.get_ocr(sha.upper(), key)
        assert hit and record["evidence"]
        evidence = from_json(record["evidence"])
        for page in evidence.pages:
            target = raster_root / sha.upper() / f"p{page.frame.page_index:04d}.png"
            assert target.exists(), target
            assert hashlib.sha256(target.read_bytes()).hexdigest() == page.frame.raster_sha256


def test_m5_the_production_path_writes_no_raster_file(tmp_path, monkeypatch):
    """M5's killer. Raster retention is the RESEARCH partition's rule (D2);
    a production partition keeps `raster_sha256` and no file. The retention
    function refuses to run without a partition at all, and the production
    read leaves no `rasters/` directory behind."""
    from discovery.inventory import DedupIndex
    from discovery.runner import MODE_SCANNED_PADDLE, DiscoveryRunner
    from webapp.artifact_cache import open_cache

    from ocr.inspect import inspect_pdf

    with pytest.raises(WaveRefused, match="empty research partition"):
        retain_rasters_for("A" * 64, pdf_bytes=b"", data_dir=tmp_path, partition="")

    page = build_ledger_page(4)
    pdf_bytes = render_image_pdf(page)
    root = tmp_path / "root"
    (root / "Synth").mkdir(parents=True)
    (root / "Synth" / "one.pdf").write_bytes(pdf_bytes)
    data_dir = tmp_path / "production_style_cache"
    cache = open_cache(data_dir)
    with FakeWorker(result_for=lambda i, b: synthetic_paddle_result(page)) as fake:
        _remote_paid_env(monkeypatch, fake.url)
        monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)
        runner = DiscoveryRunner(root, mode=MODE_SCANNED_PADDLE, run_id="t", dedup=DedupIndex(),
                                 cache=cache)
        row = runner.process("Synth/one.pdf", "Synth")
    assert row.source_path == "paddle" and row.research_partition == ""
    assert not (data_dir / "rasters").exists()
    assert inspect_pdf(pdf_bytes).content_sha256  # the sha the evidence keys on still exists


# ---------------------------------------------------------------------------
# M4 / case 14: the telemetry is transient
# ---------------------------------------------------------------------------


def test_m4_the_telemetry_never_enters_the_artifact_or_a_cache_key(tmp_path, monkeypatch):
    """M4's killer. The stored OCR payload is byte-identical with the field
    set and unset, a restore carries none, and neither cache key mentions it —
    so a live read and a cached one can never disagree about the DOCUMENT
    while disagreeing about what it cost to make."""
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import analysis_input_sha, ocr_settings_key, open_cache

    _remote_paid_env(monkeypatch, "http://127.0.0.1:18765")
    cache = open_cache(tmp_path / "cache")
    telemetry = {"pages": [{"page_index": 0, "inference_ms": 2.0, "bytes_sent": 11,
                            "bytes_received": 22, "gpu_memory_used_mib": 512}],
                 "totals": {"pages": 1, "inference_ms_total": 2.0, "bytes_sent_total": 11,
                            "bytes_received_total": 22}}
    common = dict(source_file="synthetic.pdf", model="native-pdf-text", pages=["A PAGE"])
    with_telemetry = StatementMarkdown(**common, extraction_telemetry=telemetry)
    without = StatementMarkdown(**common)
    key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
                           allow_paddle_ocr=True, research_partition=PARTITION)
    cache.put_ocr("A" * 64, key, with_telemetry)
    _, stored_with = cache.get_ocr("A" * 64, key)
    cache.put_ocr("B" * 64, key, without)
    _, stored_without = cache.get_ocr("B" * 64, key)
    assert json.dumps(stored_with, sort_keys=True) == json.dumps(stored_without, sort_keys=True)
    assert "telemetry" not in json.dumps(stored_with)
    assert with_telemetry.to_markdown() == without.to_markdown()
    assert analysis_input_sha(with_telemetry.to_markdown()) == analysis_input_sha(
        without.to_markdown())


# ---------------------------------------------------------------------------
# Card item 7: the report
# ---------------------------------------------------------------------------


def test_the_report_states_the_count_identity_and_carries_no_cost_key(tmp_path):
    data_dir = tmp_path / "research"
    directory = _populations_dir(tmp_path, CTRL=["A" * 64, "B" * 64])
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.record("A" * 64, DocumentOutcome(outcome=OUTCOME_EVIDENCE, pages=4))
    state.record("B" * 64, DocumentOutcome(outcome=OUTCOME_REFUSED, reason="ocr_failed", pages=2))
    state.chunks.append({"index": 0, "documents": 2, "status": "complete", "cache_hits": 1,
                         "rasters_written": 4, "rasters_mismatched": 0})
    state.save(WaveState.path_for(data_dir, PARTITION, "CTRL"))
    report = wave_report(data_dir=data_dir, config=PRODUCTION_CONFIG, populations_dir=directory)
    entry = report["populations"]["CTRL"]
    assert entry["attempted"] == 2 and entry["evidence"] == 1 and entry["refused"] == 1
    assert entry["count_identity_holds"] and entry["complete"]
    assert entry["pages_attempted"] == 6
    assert entry["refused_by_reason"] == {"ocr_failed": 1}
    assert entry["cache_hits"] == 1 and entry["rasters_written"] == 4
    rendered = json.dumps(report).lower()
    for token in ("cost", "price", "usd", "billing", "rate"):
        assert token not in rendered, token


def test_the_report_names_an_incomplete_population_rather_than_rounding_it_off(tmp_path):
    data_dir = tmp_path / "research"
    directory = _populations_dir(tmp_path, CTRL=["A" * 64, "B" * 64, "C" * 64])
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.record("A" * 64, DocumentOutcome(outcome=OUTCOME_EVIDENCE, pages=1))
    state.save(WaveState.path_for(data_dir, PARTITION, "CTRL"))
    entry = wave_report(data_dir=data_dir, config=PRODUCTION_CONFIG,
                        populations_dir=directory)["populations"]["CTRL"]
    assert entry["population_documents"] == 3 and entry["unattempted"] == 2
    assert entry["complete"] is False
