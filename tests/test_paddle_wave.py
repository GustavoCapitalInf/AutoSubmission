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
    # …and the MODULE PATH never appears as text either, which is what kills
    # the `importlib.import_module("ocr.paddle_rung")` dodge the AST checks
    # above cannot see. It is the module that is forbidden, not the word: the
    # discovery row has a COLUMN called `paddle_rung` (the rung's disposition
    # for that document) and reading a column is not importing a module — the
    # refusal-reason mapping reads exactly that column, and must.
    source = WAVE_TOOL.read_text(encoding="utf-8")
    assert "ocr.paddle_rung" not in source
    assert "import paddle_rung" not in source


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


@pytest.mark.parametrize("row,expected,why", [
    ({"paddle_refusal_reason": "paddle_evidence_malformed", "paddle_rung": "failed",
      "source_path": "native", "error_type": "RuntimeError"},
     "paddle_evidence_malformed", "the rung's own closed reason wins over everything"),
    ({"paddle_rung": "failed", "source_path": "local_tesseract", "error_type": "RuntimeError"},
     "paddle_rung_failed_unnamed",
     "another rung read the document, so error_type is the DOCUMENT's outcome, not Paddle's"),
    ({"paddle_rung": "failed", "source_path": "none", "error_type": "PaddleTransportError"},
     "PaddleTransportError", "the rung's failure WAS the document's: error_type is the cause"),
    ({"paddle_rung": "", "source_path": "native", "error_type": "RuntimeError"},
     "paddle_not_attempted", "no trigger reached the rung: not a Paddle outcome at all"),
    ({"paddle_rung": "research", "source_path": "paddle", "outcome_reason": "withheld_adb"},
     "paddle_evidence_missing", "a financial outcome is not an extractor failure"),
    ({"paddle_rung": "research", "source_path": "paddle"}, "paddle_evidence_missing", "no evidence recorded"),
    ({"paddle_rung": "not_attempted", "outcome_reason": "approved"},
     "paddle_not_attempted", "a skipped rung does not inherit an analysis verdict"),
])
def test_the_refusal_reason_is_a_paddle_reason_not_the_documents_outcome(row, expected, why):
    """The U755 run's finding, as a test. `error_type` is not a Paddle column:
    when the rung fails and the ladder falls closed to another rung, the runner
    rebinds it to the DOCUMENT's outcome — for an unresolved statement,
    `RuntimeError` ("no deterministic parser matched"). Reading it as the
    Paddle cause reported 318 unresolved documents as a `RuntimeError` bucket
    that said nothing whatever about Paddle. It IS the cause in exactly one
    shape: the rung's failure was also the document's, so nothing rebound it."""
    from tools.paddle_wave import _refusal_reason

    assert _refusal_reason(row) == expected, why


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


@pytest.mark.parametrize("running", [False, True])
def test_retention_process_count_distinguishes_the_inspector_from_the_worker(running):
    from tools.paddle_wave import _WORKER_PROCESS_AWK
    from tools.paddle_vast import REMOTE_WORKER_PATH

    awk = shutil.which("awk")
    if awk is None and os.name == "nt":
        candidate = Path("C:/Program Files/Git/usr/bin/awk.exe")
        if candidate.exists():
            awk = str(candidate)
    if awk is None:
        pytest.skip("the remote inspection uses POSIX awk")
    # Shell command text and an unrelated Python script are not worker processes.
    processes = (
        f"sh sh -c find /runtime ! -name paddle_worker.py {REMOTE_WORKER_PATH}\n"
        f"bash bash -c echo {REMOTE_WORKER_PATH}\n"
        "python python /runtime/unrelated.py\n"
    )
    if running:
        processes += f"python3.12 /runtime/bin/python3.12 {REMOTE_WORKER_PATH}\n"
    result = subprocess.run(
        [awk, _WORKER_PROCESS_AWK.format(worker=REMOTE_WORKER_PATH)],
        input=processes, text=True, capture_output=True, check=True,
    )
    assert int(result.stdout.strip()) == int(running)


@pytest.mark.parametrize("case", ["clean", "missing", "ps_failure", "find_failure", "nested"])
def test_retention_executes_the_shell_and_refuses_incomplete_inspection(tmp_path, case):
    from tools import paddle_wave as wave

    bash = shutil.which("bash")
    if os.name == "nt":
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(candidate) if candidate.exists() else None
    if bash is None:
        pytest.skip("the remote inspection uses a POSIX shell")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "paddle_worker.py").write_text("# synthetic worker\n", encoding="utf-8")
    (runtime / "worker.log").write_text("", encoding="utf-8")
    if case == "nested":
        (runtime / "spool").mkdir()
        (runtime / "spool" / "page.bin").write_bytes(b"synthetic retained bytes")
    inspected = runtime / "missing" if case == "missing" else runtime
    command = wave._ATTESTATION_COMMAND.format(
        directory=inspected.as_posix(), worker=(runtime / "paddle_worker.py").as_posix(), since=0,
    ).replace("find /tmp", f'find "{runtime.as_posix()}"')
    prefix = "ps() { return 1; }; " if case == "ps_failure" else "ps() { return 0; }; "
    if case == "find_failure":
        prefix += "find() { return 1; }; "
    completed = subprocess.run([bash, "-c", prefix + command], capture_output=True, text=True)
    result = attest_retention(
        _FakeSettings(), runner=lambda *args, **kwargs: completed,
        retention_declared=True, sleep=lambda seconds: None,
    )
    assert result.passed is (case == "clean")
    assert result.inspected is (case in {"clean", "nested"})
    if case == "nested":
        assert result.unexpected_files == 1


@pytest.mark.parametrize("output,why", [
    ("PROC=1\nPIDFILE=0\nIMAGES=0\nREQUESTS=0\nOTHER=0\n", "a worker still running"),
    ("PROC=0\nPIDFILE=1\nIMAGES=0\nREQUESTS=0\nOTHER=0\n", "a pidfile left behind"),
    ("PROC=0\nPIDFILE=0\nIMAGES=3\nREQUESTS=0\nOTHER=0\n", "page bytes on disk"),
    ("PROC=0\nPIDFILE=0\nIMAGES=0\nREQUESTS=2\nOTHER=0\n", "request artefacts"),
    ("PROC=0\nPIDFILE=0\nIMAGES=0\nREQUESTS=0\nOTHER=5\n", "unexpected files"),
])
def test_m8_a_fake_ssh_runner_that_lists_a_leftover_fails_the_attestation(output, why):
    """M8's killer. An attestation that reported `none` because the worker
    said so, without looking, would pass every one of these. The process case
    is looked at repeatedly and STILL fails: the grace below is bounded, not a
    way out."""
    attestation = attest_retention(_FakeSettings(), runner=_ssh_runner(output),
                                   retention_declared=True, sleep=lambda _seconds: None)
    assert not attestation.passed, why
    assert attestation.inspected


def test_a_worker_still_exiting_is_given_a_bounded_grace_and_then_believed():
    """The CTRL run's own finding, as a test. The inspection ran about two
    seconds after `stop` and counted a process that was already exiting; half
    an hour later the same probe answered `PROC=0` with nothing whatever under
    the worker's directory. That was a race in the INSTRUMENT reported as a
    retention failure on the instance — the worst kind of false alarm, because
    it makes a real one easier to wave away. So the process is given a bounded
    grace to die and the record says how many looks it took; a process that
    outlives the grace still fails (the case above)."""
    answers = iter([
        "PROC=1\nPIDFILE=0\nIMAGES=0\nREQUESTS=0\nOTHER=0\nTMPIMG=0\n",
        CLEAN_INSTANCE,
    ])
    slept: list[float] = []

    def runner(args, **kwargs):
        return _FakeCompleted(next(answers))

    attestation = attest_retention(_FakeSettings(), runner=runner, retention_declared=True,
                                   sleep=slept.append)
    assert attestation.passed and attestation.probes == 2
    assert slept == [5.0]


def test_the_temp_image_count_is_scoped_to_this_session(tmp_path):
    """`/tmp` belongs to the whole image, not to this worker. The CTRL run
    found one synthetic PNG there, written by the operator's own live test two
    hours before the session started, and counted it beside our work. The
    count now asks the instance for files NEWER than the session, so the
    number means "left by this session" — which is the only reading anyone can
    act on. It stays RECORDED rather than gated, because a file in a shared
    directory is an observation, not a verdict on this worker."""
    runner = _ssh_runner(CLEAN_INSTANCE)
    attest_retention(_FakeSettings(), runner=runner, retention_declared=True,
                     since_epoch=1_757_600_000.9)
    command = runner.seen[0][-1]
    assert "-newermt '@1757600000'" in command
    assert "/tmp" in command

    default = _ssh_runner(CLEAN_INSTANCE)
    attest_retention(_FakeSettings(), runner=default, retention_declared=True)
    assert "-newermt '@0'" in default.seen[0][-1]  # no session start given: count everything


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
        "probes", "error", "passed",
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


def test_report_reads_each_populations_nested_run_directory(tmp_path):
    data = tmp_path / "research"
    runs = tmp_path / "runs"
    for name, elapsed in (("CTRL", 17), ("U755", 23)):
        state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name=name)
        state.chunks.append({"run_dir": "synthetic-session"})
        state.save(WaveState.path_for(data, PARTITION, name))
        directory = runs / name / "synthetic-session"
        directory.mkdir(parents=True)
        with (directory / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["inference_ms", "page_count"])
            writer.writeheader()
            writer.writerow({"inference_ms": elapsed, "page_count": 1})
    report = wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=runs)
    for name, elapsed in (("CTRL", 17), ("U755", 23)):
        measured = report["populations"][name]["telemetry"]
        assert measured["documents_measured"] == 1
        assert measured["inference_ms_per_document"]["p50"] == elapsed
        assert measured["bytes_up_basis"] == "raw_png_payload_before_base64_and_transport_compression"
        assert measured["bytes_down_basis"] == "json_reserialization_estimate_before_transport_compression"
        assert measured["transport_bytes_measured"] is False

    # A caller may also pass one population's run root, the original flat shape.
    flat = wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=runs / "CTRL")
    assert flat["populations"]["CTRL"]["telemetry"]["documents_measured"] == 1

    duplicate = runs / "synthetic-session"
    shutil.copytree(runs / "CTRL" / "synthetic-session", duplicate)
    with pytest.raises(WaveRefused, match="ambiguous population run directory"):
        wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=runs)


def test_report_rederives_refusals_from_the_recorded_chunk_without_rewriting_state(tmp_path):
    data, runs = tmp_path / "research", tmp_path / "runs"
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    sha = "F" * 64
    state.record(sha, DocumentOutcome(outcome=OUTCOME_REFUSED, reason="approved", pages=1, chunk=1))
    fields = ["content_sha256", "paddle_rung", "source_path", "paddle_refusal_reason", "outcome_reason"]
    for index, reason in ((0, "paddle_evidence_malformed"), (1, "")):
        directory = runs / "CTRL" / f"synthetic-{index}"
        directory.mkdir(parents=True)
        state.chunks.append({"index": index, "run_dir": directory.name})
        with (directory / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(dict(zip(fields, [sha, "failed", "local_tesseract", reason, "approved"])))
    state_path = WaveState.path_for(data, PARTITION, "CTRL")
    state.save(state_path)
    original = state_path.read_bytes()
    measured = wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=runs)["populations"]["CTRL"]
    assert measured["refused_by_reason"] == {"paddle_rung_failed_unnamed": 1}
    assert measured["refusal_reason_source"] == "recorded_rows"
    assert measured["refusals_rederived"] == 1 and measured["refusals_without_rows"] == 0
    assert state_path.read_bytes() == original
    # The old financial reason remains in private state, but cannot become an
    # ordinary report key. Reading recorded rows above still preserves history.
    with pytest.raises(WaveRefused, match="wave_refusal_code_unknown"):
        wave_report(data_dir=data, config=PRODUCTION_CONFIG)
    assert state_path.read_bytes() == original
    missing = wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=tmp_path / "missing")["populations"]["CTRL"]
    assert missing["refused_by_reason"] == {"paddle_refusal_row_unavailable": 1}
    assert missing["refusals_without_rows"] == 1


def test_completed_population_resume_has_no_remote_lifecycle(tmp_path):
    population = _populations_dir(tmp_path, CTRL=["B" * 64])
    data = tmp_path / "research"
    state = _state_with(data, "CTRL", ["B" * 64], OUTCOME_EVIDENCE)
    state.version = 1
    from tools.paddle_wave import population_digests
    state.population_set_sha256 = population_digests(population / "CTRL.shas")["set_sha256"]
    state.save(WaveState.path_for(data, PARTITION, "CTRL"))

    class UnusedLifecycle:
        def up(self):
            raise AssertionError("a completed population must not start a worker")

        def down(self, **kwargs):
            raise AssertionError("a no-work resume has no worker session to attest")

    result = run_wave(
        population_file=population / "CTRL.shas", population_name="CTRL",
        populations_dir=population, config=PRODUCTION_CONFIG, data_dir=data,
        out_dir=tmp_path / "runs", root=tmp_path / "archive", lifecycle=UnusedLifecycle(),
        environ={PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL,
                 PADDLE_CUSTOMER_DATA_OPT_IN_ENV: PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL},
    )
    assert result["session"]["chunks"] == 0
    assert result["attestation"] is None
    resumed = WaveState.load(WaveState.path_for(data, PARTITION, "CTRL"))
    assert resumed.version == 1
    assert len(resumed.sessions) == 1 and resumed.sessions[0]["documents"] == 0


# ---------------------------------------------------------------------------
# Research custody and the versioned ordinary export (synthetic bytes only)
# ---------------------------------------------------------------------------

EXPORT_SESSION = "2035-01-02T030405.000000-0000-abcdef12"


def _export_row(**changes):
    row = {
        "content_sha256": "A" * 64, "evidence_sha256": "b" * 64,
        "page_count": "2", "stage_evidence": "present", "source_path": "paddle",
        "cache_paddle": "miss", "bytes_up": "17", "bytes_down": "19",
        "inference_ms": "6.5", "vram_mb": "0", "peak_rss_mb": "not measured",
        "elapsed_ms": "9.5", "research_partition": PARTITION,
        "paddle_rung": "research", "paddle_refusal_reason": "", "error_type": "",
        "outcome_reason": "approved", "relative_path": "synthetic-private-name/document.pdf",
        "folder_label": "synthetic-private-folder", "duplicate_of": "synthetic-private-alias",
        "statement_account": "synthetic-private-account", "source_model": "synthetic-private-model",
        "future_customer_field": "synthetic-private-future",
    }
    row.update(changes)
    return row


def _export_custody(parent, rows=None, *, session=EXPORT_SESSION):
    directory = parent / session
    directory.mkdir(parents=True)
    rows = [_export_row()] if rows is None else rows
    with (directory / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    provenance = {"run_of_record": {"partitions": {
        "mode": "research-paddle", "research_partition": PARTITION,
    }}, "private_extra": "synthetic-private-provenance"}
    (directory / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    (directory / "hash_map.csv").write_text("synthetic-private-hash-map", encoding="utf-8")
    (directory / "report.json").write_text('{"billing":"synthetic-private-cost"}', encoding="utf-8")
    kwargs = {
        "configuration": PRODUCTION_CONFIG, "partition": PARTITION, "population_name": "CTRL",
        "expected_source_rows_sha256": hashlib.sha256((directory / "rows.csv").read_bytes()).hexdigest(),
        "expected_source_provenance_sha256": hashlib.sha256((directory / "provenance.json").read_bytes()).hexdigest(),
        "expected_session": session,
    }
    return directory, kwargs


def _read_export(directory, kwargs):
    from tools.paddle_wave import read_wave_technical_export

    return read_wave_technical_export(
        directory, expected_configuration=kwargs["configuration"], expected_partition=kwargs["partition"],
        expected_population=kwargs["population_name"], expected_session=kwargs["expected_session"],
        expected_source_rows_sha256=kwargs["expected_source_rows_sha256"],
        expected_source_provenance_sha256=kwargs["expected_source_provenance_sha256"],
    )


def test_export_positive_allowlist_preserves_aliases_missing_values_and_originals(tmp_path):
    from tools.paddle_wave import EXPORT_MARKER, EXPORT_ROWS, TECHNICAL_FIELDS, write_wave_technical_export

    rows = [_export_row(), _export_row(cache_paddle="hit", bytes_up="", bytes_down="",
                                     inference_ms="", vram_mb="", elapsed_ms="0.0")]
    source, kwargs = _export_custody(tmp_path / "private", rows)
    before = {item.name: item.read_bytes() for item in source.iterdir()}
    destination = write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
    assert {item.name for item in destination.iterdir()} == {EXPORT_MARKER, EXPORT_ROWS}
    projected = _read_export(destination, kwargs)
    assert len(projected) == 2 and all(tuple(row) == TECHNICAL_FIELDS for row in projected)
    for original, exported in zip(rows, projected):
        assert exported == {key: "" if key == "wave_refusal_reason" else original[key] for key in TECHNICAL_FIELDS}
    assert projected[1]["bytes_up"] == "" and projected[1]["inference_ms"] == ""
    assert projected[0]["vram_mb"] == "0" and projected[0]["peak_rss_mb"] == "not measured"
    assert all(b"synthetic-private" not in item.read_bytes() for item in destination.iterdir())
    assert before == {item.name: item.read_bytes() for item in source.iterdir()}
    with pytest.raises(WaveRefused, match="destination_exists"):
        write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)


@pytest.mark.parametrize("field,value", [
    ("source_path", "synthetic-private-source"), ("stage_evidence", "synthetic-private-status"),
    ("cache_paddle", "synthetic-private-cache"), ("research_partition", "synthetic-private-partition"),
    ("content_sha256", "synthetic-private-hash"), ("evidence_sha256", "synthetic-private-evidence"),
    ("page_count", "-1"), ("bytes_up", "3.0"), ("bytes_down", "synthetic-private-count"),
    ("inference_ms", "nan"), ("inference_ms", "1e9999"), ("vram_mb", "-1"),
    ("peak_rss_mb", "synthetic-private-memory"), ("elapsed_ms", "synthetic-private-time"),
])
def test_export_rejects_unsafe_values_before_publication(tmp_path, field, value):
    from tools.paddle_wave import write_wave_technical_export

    source, kwargs = _export_custody(tmp_path / "private", [_export_row(**{field: value})])
    with pytest.raises(WaveRefused) as caught:
        write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
    assert value not in str(caught.value)
    assert not (tmp_path / "ordinary" / EXPORT_SESSION / "wave_export.json").exists()


@pytest.mark.parametrize("field", ["paddle_refusal_reason", "error_type"])
def test_export_and_report_refuse_unknown_derived_refusal_keys(tmp_path, field):
    from tools.paddle_wave import _project_wave_technical_rows, _reported_refusals

    row = _export_row(source_path="local_tesseract", stage_evidence="absent", paddle_rung="failed",
                      **{field: "synthetic-private-reason"})
    # error_type is used only for a row whose rung has no explicit failure code.
    if field == "error_type":
        row["source_path"] = "none"
    with pytest.raises(WaveRefused, match="wave_refusal_code_unknown"):
        _project_wave_technical_rows([row], PARTITION)
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.record("A" * 64, DocumentOutcome(OUTCOME_REFUSED, "synthetic-private-reason"))
    with pytest.raises(WaveRefused, match="wave_refusal_code_unknown"):
        _reported_refusals(state, None)
    state.documents["A" * 64].reason = ""
    assert _reported_refusals(state, None)["refused_by_reason"] == {"unrecorded": 1}


def test_export_requires_independent_rows_provenance_and_session_bindings(tmp_path):
    from tools.paddle_wave import write_wave_technical_export

    source, kwargs = _export_custody(tmp_path / "private")
    for key in ("expected_source_rows_sha256", "expected_source_provenance_sha256"):
        with pytest.raises(WaveRefused, match="binding_mismatch"):
            write_wave_technical_export(source, tmp_path / "ordinary", **{**kwargs, key: "0" * 64})
    with pytest.raises(WaveRefused, match="session_mismatch"):
        write_wave_technical_export(source, tmp_path / "ordinary", **{
            **kwargs, "expected_session": "2035-01-02T030405.000000-0000-abcdef13"})
    original = (source / "provenance.json").read_bytes()
    # Same research mode/partition is insufficient to authenticate a replacement.
    (source / "provenance.json").write_bytes(original + b"\n")
    with pytest.raises(WaveRefused, match="provenance_binding_mismatch"):
        write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)


@pytest.mark.parametrize("field,value", [
    ("source_rows_sha256", "0" * 64), ("source_provenance_sha256", "0" * 64),
    ("source_session", "2035-01-02T030405.000000-0000-abcdef13"),
    ("row_count", 2), ("schema_version", 99), ("fields", ["relative_path"]),
    ("configuration", "synthetic-private-configuration"), ("partition", "synthetic-private-partition"),
])
def test_export_reader_refuses_forged_or_corrupt_marker(tmp_path, field, value):
    from tools.paddle_wave import write_wave_technical_export

    source, kwargs = _export_custody(tmp_path / "private")
    destination = write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
    path = destination / "wave_export.json"
    marker = json.loads(path.read_text(encoding="utf-8"))
    marker[field] = value
    path.write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(WaveRefused):
        _read_export(destination, kwargs)


def test_export_reader_refuses_extra_files_changed_rows_and_missing_marker(tmp_path):
    from tools.paddle_wave import write_wave_technical_export

    source, kwargs = _export_custody(tmp_path / "private")
    destination = write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
    extra = destination / "hash_map.csv"
    extra.write_text("synthetic-private-name", encoding="utf-8")
    with pytest.raises(WaveRefused, match="files_invalid"):
        _read_export(destination, kwargs)
    extra.unlink()
    rows_path = destination / "wave_technical_rows.csv"
    rows_path.write_bytes(rows_path.read_bytes() + b"\n")
    with pytest.raises(WaveRefused, match="rows_hash_mismatch"):
        _read_export(destination, kwargs)
    (destination / "wave_export.json").unlink()
    with pytest.raises(WaveRefused):
        _read_export(destination, kwargs)


@pytest.mark.parametrize("kind", ["source_rows", "source_directory", "output_directory"])
def test_export_rechecks_lexical_bindings_before_completion_marker(tmp_path, monkeypatch, kind):
    import tools.paddle_wave as wave

    source, kwargs = _export_custody(tmp_path / "private")
    output = tmp_path / "ordinary"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "rows.csv").write_bytes((source / "rows.csv").read_bytes())
    (outside / "provenance.json").write_bytes((source / "provenance.json").read_bytes())
    resolve, atomic = Path.resolve, wave._atomic_export_file
    retargeted = False
    watched = {"source_rows": source / "rows.csv", "source_directory": source,
               "output_directory": output}[kind]

    def changed_resolve(path, *args, **kwargs):
        if retargeted and path == watched:
            return outside / "rows.csv" if kind == "source_rows" else outside
        return resolve(path, *args, **kwargs)

    def after_rows(path, raw, *, validate):
        nonlocal retargeted
        atomic(path, raw, validate=validate)
        if path.name == wave.EXPORT_ROWS:
            retargeted = True

    monkeypatch.setattr(Path, "resolve", changed_resolve)
    monkeypatch.setattr(wave, "_atomic_export_file", after_rows)
    with pytest.raises(WaveRefused, match="binding_changed|path_escaped"):
        wave.write_wave_technical_export(source, output, **kwargs)
    assert not (output / EXPORT_SESSION / wave.EXPORT_MARKER).exists()
    assert not (outside / wave.EXPORT_MARKER).exists()


def test_export_reader_detects_same_byte_leaf_retarget(tmp_path, monkeypatch):
    import tools.paddle_wave as wave

    source, kwargs = _export_custody(tmp_path / "private")
    destination = wave.write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
    watched = destination / wave.EXPORT_ROWS
    outside = tmp_path / "outside.csv"
    outside.write_bytes(watched.read_bytes())
    resolve, closed = Path.resolve, wave._closed_bytes
    retargeted = False

    def changed_resolve(path, *args, **kwargs):
        return outside if retargeted and path == watched else resolve(path, *args, **kwargs)

    def after_first_read(path, **kwargs):
        nonlocal retargeted
        raw = closed(path, **kwargs)
        if path == watched:
            retargeted = True
        return raw

    monkeypatch.setattr(Path, "resolve", changed_resolve)
    monkeypatch.setattr(wave, "_closed_bytes", after_first_read)
    with pytest.raises(WaveRefused, match="binding_changed|source_changed"):
        _read_export(destination, kwargs)


@pytest.mark.parametrize("version", [True, "synthetic-private-version", 99, None])
def test_new_state_version_refusal_is_value_free(tmp_path, capsys, version):
    data = tmp_path / "research"
    path = WaveState.path_for(data, PARTITION, "CTRL")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": version}), encoding="utf-8")
    assert main(["report", "--config", PRODUCTION_CONFIG, "--data-dir", str(data)]) == 2
    error = capsys.readouterr().err
    assert "wave_state_version_unknown" in error
    assert "synthetic-private-version" not in error and str(path) not in error


@pytest.mark.parametrize("version,storage", [(1, "research-private-v1"), (1, None), (2, None), (2, "unknown")])
def test_state_rejects_new_storage_in_old_format_and_unknown_markers(tmp_path, version, storage):
    import tools.paddle_wave as wave

    state = WaveState(version=version, config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.chunks = [{"storage": storage}]
    path = tmp_path / "state.json"
    state.save(path)
    with pytest.raises(WaveRefused, match="storage_unknown"):
        WaveState.load(path)
    with pytest.raises(WaveRefused, match="storage_unknown"):
        wave._recorded_chunk_rows(state, state.chunks[0], data_dir=tmp_path, out_dir=None)


def test_new_state_writes_version_two_and_loader_preserves_legacy_version(tmp_path):
    # Serialization control only. The independent closure review runs the
    # actual preserved version-one loader against new state bytes.
    state = WaveState()
    path = tmp_path / "state.json"
    state.save(path)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] != 1
    legacy = WaveState(version=1)
    legacy.save(path)
    assert WaveState.load(path).version == 1


def test_private_and_legacy_report_equivalence_and_mixed_authority(tmp_path):
    import tools.paddle_wave as wave

    data, legacy_root = tmp_path / "research", tmp_path / "legacy"
    source, kwargs = _export_custody(legacy_root / "CTRL", [
        _export_row(), _export_row(content_sha256="C" * 64, source_path="local_tesseract",
            stage_evidence="absent", paddle_rung="failed", paddle_refusal_reason="paddle_evidence_malformed",
            inference_ms="", bytes_up="", bytes_down="", vram_mb=""),
    ])
    state = WaveState(version=1, config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.chunks = [{"index": 0, "run_dir": source.name}]
    state.record("A" * 64, DocumentOutcome(OUTCOME_EVIDENCE, pages=2, chunk=0))
    state.record("C" * 64, DocumentOutcome(OUTCOME_REFUSED, "ocr_failed", pages=2, chunk=0))
    path = WaveState.path_for(data, PARTITION, "CTRL")
    state.save(path)
    original = path.read_bytes()
    before = wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=legacy_root)
    assert path.read_bytes() == original
    private_parent = wave._custody_run_parent(data, PARTITION, "CTRL")
    private = private_parent / source.name
    shutil.copytree(source, private)
    state.version = 2
    state.chunks[0].update(storage=wave.PRIVATE_RUN_STORAGE,
        rows_sha256=kwargs["expected_source_rows_sha256"],
        provenance_sha256=kwargs["expected_source_provenance_sha256"])
    state.save(path)
    assert wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=legacy_root) == before
    # Public tampering cannot alter authoritative report numerics.
    exported = wave.write_wave_technical_export(private, tmp_path / "ordinary", **kwargs)
    (exported / wave.EXPORT_ROWS).write_text("synthetic-private-corrupt", encoding="utf-8")
    assert wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=tmp_path / "ordinary") == before
    # A v2 state may retain an old markerless chunk beside the new custody chunk.
    old, _ = _export_custody(legacy_root / "CTRL", session="2035-01-02T030405.000000-0000-abcdef13")
    state.chunks.append({"index": 1, "run_dir": old.name})
    state.save(path)
    mixed = wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=legacy_root)
    assert mixed["populations"]["CTRL"]["telemetry"]["documents_measured"] == 2
    # Missing custody is a refusal even if a legacy-looking copy exists.
    (private / "rows.csv").unlink()
    with pytest.raises(WaveRefused):
        wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=legacy_root)


def _small_wave_args(tmp_path):
    populations = _populations_dir(tmp_path, CTRL=["A" * 64])
    return dict(population_file=populations / "CTRL.shas", population_name="CTRL",
        populations_dir=populations, config=PRODUCTION_CONFIG, data_dir=tmp_path / "research",
        out_dir=tmp_path / "ordinary", root=tmp_path / "archive", environ=BOTH_LITERALS,
        retain_rasters=False)


def test_completed_private_chunk_survives_export_failure_with_truthful_session(tmp_path, monkeypatch):
    import tools.paddle_wave as wave

    args = _small_wave_args(tmp_path)
    args["population_file"].write_text("A" * 64 + "\n" + "C" * 64 + "\n", encoding="utf-8")
    events = []
    persisted_before_export = []

    class Lifecycle:
        def up(self):
            events.append("up")
            return {"retention_declared": True}

        def down(self, **kwargs):
            events.append("down")
            return RetentionAttestation(True, True, False, False, 0, 0, 0)

    def runner(argv, **kwargs):
        events.append("child")
        private = Path(argv[argv.index("--out") + 1])
        assert private.is_relative_to(args["data_dir"])
        assert not private.is_relative_to(args["out_dir"])
        _export_custody(private, [_export_row(), _export_row(content_sha256="C" * 64,
            stage_evidence="absent", source_path="local_tesseract", paddle_rung="failed")])
        return subprocess.CompletedProcess(argv, 0)

    def refused_export(*unused, **kwargs):
        events.append("export")
        state = WaveState.load(WaveState.path_for(args["data_dir"], PARTITION, "CTRL"))
        assert state.version == 2 and state.counts()["evidence"] == 1
        assert state.chunks[0]["status"] == "complete"
        assert state.chunks[0]["storage"] == wave.PRIVATE_RUN_STORAGE
        assert state.counts()["refused"] == 1
        assert state.documents["C" * 64].reason == "paddle_rung_failed_unnamed"
        assert state.documents["C" * 64].chunk == state.documents["A" * 64].chunk == 0
        persisted_before_export.append(True)
        raise WaveRefused("synthetic-private-rejected-output")

    monkeypatch.setattr(wave, "write_wave_technical_export", refused_export)
    with pytest.raises(wave.WaveExportFailed, match="offline_retry_required") as caught:
        run_wave(**args, subprocess_runner=runner, lifecycle=Lifecycle())
    assert "synthetic-private" not in str(caught.value)
    state = WaveState.load(WaveState.path_for(args["data_dir"], PARTITION, "CTRL"))
    assert state.chunks[0]["export_status"] == "failed"
    assert state.sessions[-1]["chunks"] == 1 and state.sessions[-1]["documents"] == 2
    assert state.sessions[-1]["export_status"] == "failed" and state.counts()["evidence"] == 1
    assert events == ["up", "child", "export", "down"]
    assert persisted_before_export == [True]
    assert state.pending(["A" * 64, "C" * 64]) == ["C" * 64]
    assert not list(args["out_dir"].glob("*/wave_export.json"))


def test_offline_export_never_resumes_refused_documents_or_mutates_state(tmp_path, monkeypatch):
    import tools.paddle_wave as wave

    source, kwargs = _export_custody(tmp_path / "private", [_export_row(
        stage_evidence="absent", source_path="local_tesseract", paddle_rung="failed")])
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.record("A" * 64, DocumentOutcome(OUTCOME_REFUSED, "ocr_failed"))
    path = tmp_path / "state.json"
    state.save(path)
    before = path.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("offline export attempted extraction or state mutation")

    monkeypatch.setattr(WaveState, "pending", forbidden)
    monkeypatch.setattr(WaveState, "save", forbidden)
    monkeypatch.setattr(wave, "run_wave", forbidden)
    monkeypatch.setattr(wave.Lifecycle, "up", forbidden)
    monkeypatch.setattr(wave.Lifecycle, "down", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    result = wave.write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
    assert _read_export(result, kwargs)[0]["wave_refusal_reason"] == "paddle_rung_failed_unnamed"
    assert path.read_bytes() == before


@pytest.mark.parametrize("shape", ["same", "inside", "outside"])
def test_wave_refuses_overlapping_storage_before_discovery(tmp_path, shape):
    args = _small_wave_args(tmp_path)
    data = args["data_dir"]
    args["out_dir"] = {"same": data, "inside": data / "ordinary", "outside": data.parent}[shape]

    def forbidden(*args, **kwargs):
        raise AssertionError("overlap reached discovery")

    with pytest.raises(WaveRefused, match="storage_roots_overlap"):
        run_wave(**args, subprocess_runner=forbidden)


def test_wave_refuses_multiple_new_custody_children_before_recording(tmp_path):
    args = _small_wave_args(tmp_path)

    def runner(argv, **kwargs):
        parent = Path(argv[argv.index("--out") + 1])
        _export_custody(parent)
        _export_custody(parent, session="2035-01-02T030405.000000-0000-abcdef13")
        return subprocess.CompletedProcess(argv, 0)

    with pytest.raises(WaveRefused, match="wave_child_run_ambiguous"):
        run_wave(**args, subprocess_runner=runner)
    state = WaveState.load(WaveState.path_for(args["data_dir"], PARTITION, "CTRL"))
    assert not state.documents and not state.chunks


def test_wave_log_and_report_attestation_refuse_unbounded_fields(tmp_path, capsys):
    from tools.paddle_wave import WaveLog, _validate_attestation

    with pytest.raises(WaveRefused, match="wave_event_fields_invalid"):
        WaveLog(None)("chunk.end", relative_path="synthetic-private-path")
    assert "synthetic-private" not in capsys.readouterr().out
    valid = RetentionAttestation(True, True, False, False, 0, 0, 0).as_record()
    _validate_attestation(valid)
    for poisoned in ({**valid, "cost": "synthetic-private-cost"}, {**valid, "error": "synthetic-private-error"}):
        with pytest.raises(WaveRefused):
            _validate_attestation(poisoned)


@pytest.mark.parametrize("target", ["provenance", "marker"])
def test_non_object_export_metadata_refuses_without_echo(tmp_path, target):
    import tools.paddle_wave as wave

    source, kwargs = _export_custody(tmp_path / "private")
    if target == "provenance":
        path = source / "provenance.json"
        path.write_text('["synthetic-private-object"]', encoding="utf-8")
        kwargs["expected_source_provenance_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        operation = lambda: wave.write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
    else:
        destination = wave.write_wave_technical_export(source, tmp_path / "ordinary", **kwargs)
        (destination / wave.EXPORT_MARKER).write_text('["synthetic-private-object"]', encoding="utf-8")
        operation = lambda: _read_export(destination, kwargs)
    with pytest.raises(WaveRefused) as caught:
        operation()
    assert "synthetic-private-object" not in str(caught.value)


def test_recorded_private_reader_detects_same_byte_leaf_retarget(tmp_path, monkeypatch):
    import tools.paddle_wave as wave

    data = tmp_path / "research"
    source, kwargs = _export_custody(wave._custody_run_parent(data, PARTITION, "CTRL"))
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    chunk = {"storage": wave.PRIVATE_RUN_STORAGE, "run_dir": source.name,
             "rows_sha256": kwargs["expected_source_rows_sha256"],
             "provenance_sha256": kwargs["expected_source_provenance_sha256"]}
    watched = source / "rows.csv"
    outside = tmp_path / "outside.csv"
    outside.write_bytes(watched.read_bytes())
    resolve, closed = Path.resolve, wave._closed_bytes
    changed = False

    def changed_resolve(path, *args, **kwargs):
        return outside if changed and path == watched else resolve(path, *args, **kwargs)

    def changed_after_read(path, **kwargs):
        nonlocal changed
        raw = closed(path, **kwargs)
        if path == watched:
            changed = True
        return raw

    monkeypatch.setattr(Path, "resolve", changed_resolve)
    monkeypatch.setattr(wave, "_closed_bytes", changed_after_read)
    with pytest.raises(WaveRefused, match="binding_changed"):
        wave._recorded_chunk_rows(state, chunk, data_dir=data, out_dir=None)


@pytest.mark.parametrize("name", ["../escape", "folder/run", "folder\\run", "..", "/outside"])
def test_recorded_run_names_cannot_escape_the_selected_root(tmp_path, name):
    import tools.paddle_wave as wave

    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    with pytest.raises(WaveRefused, match="run_name_invalid"):
        wave._recorded_run_directory(state, tmp_path, name)


def test_mixed_chunks_bind_latest_refusal_and_exact_technical_denominators(tmp_path):
    import tools.paddle_wave as wave

    data, legacy = tmp_path / "research", tmp_path / "legacy"
    old, _ = _export_custody(legacy / "CTRL", [
        _export_row(page_count="1", inference_ms="10"),
        _export_row(content_sha256="C" * 64, source_path="local_tesseract", stage_evidence="absent",
                    paddle_rung="failed", paddle_refusal_reason="paddle_evidence_malformed", inference_ms=""),
    ])
    new, kwargs = _export_custody(wave._custody_run_parent(data, PARTITION, "CTRL"), [
        _export_row(page_count="2", inference_ms="30", bytes_up="31", bytes_down="37"),
        _export_row(content_sha256="C" * 64, source_path="local_tesseract", stage_evidence="absent",
                    paddle_rung="failed", inference_ms=""),
        _export_row(cache_paddle="hit", inference_ms="", bytes_up="", bytes_down="", vram_mb="",
                    peak_rss_mb="200", elapsed_ms="7"),
    ], session="2035-01-02T030405.000000-0000-abcdef13")
    state = WaveState(config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.chunks = [{"index": 0, "run_dir": old.name},
                    {"index": 1, "run_dir": new.name, "storage": wave.PRIVATE_RUN_STORAGE,
                     "rows_sha256": kwargs["expected_source_rows_sha256"],
                     "provenance_sha256": kwargs["expected_source_provenance_sha256"]}]
    state.record("A" * 64, DocumentOutcome(OUTCOME_EVIDENCE, pages=2, chunk=1))
    state.record("C" * 64, DocumentOutcome(OUTCOME_REFUSED, "ocr_failed", pages=2, chunk=1))
    path = WaveState.path_for(data, PARTITION, "CTRL")
    state.save(path)
    before = path.read_bytes()
    result = wave_report(data_dir=data, config=PRODUCTION_CONFIG, out_dir=legacy)["populations"]["CTRL"]
    assert result["refused_by_reason"] == {"paddle_rung_failed_unnamed": 1}
    telemetry = result["telemetry"]
    assert telemetry["documents_measured"] == 2
    assert telemetry["inference_ms_per_document"] == {"p50": 20.0, "p95": 30.0, "max": 30.0}
    assert telemetry["inference_ms_per_page_mean"] == {"p50": 12.5, "p95": 15.0, "max": 15.0}
    assert telemetry["bytes_up_total"] == 48 and telemetry["bytes_down_total"] == 56
    assert telemetry["peak_rss_mb"] == {}  # the cache alias is not a measured Paddle row
    assert path.read_bytes() == before


def test_active_legacy_continuation_advances_before_child_and_keeps_old_chunks(tmp_path):
    args = _small_wave_args(tmp_path)
    state = WaveState(version=1, config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    old_chunk = {"index": 0, "run_dir": "legacy-synthetic", "status": "complete"}
    state.chunks = [old_chunk]
    path = WaveState.path_for(args["data_dir"], PARTITION, "CTRL")
    state.save(path)
    observations = []

    def runner(argv, **kwargs):
        current = WaveState.load(path)
        assert current.version == 2 and current.chunks == [old_chunk]
        observations.append(True)
        _export_custody(Path(argv[argv.index("--out") + 1]))
        return subprocess.CompletedProcess(argv, 0)

    result = run_wave(**args, subprocess_runner=runner)
    assert observations == [True]
    assert result["state"].version == 2
    assert result["state"].chunks[0] == old_chunk
    assert result["state"].chunks[1]["storage"] == "research-private-v1"


def test_failed_private_state_persistence_never_reaches_export_and_stops_lifecycle(tmp_path, monkeypatch):
    import tools.paddle_wave as wave

    args = _small_wave_args(tmp_path)
    events = []
    save = WaveState.save

    class Lifecycle:
        def up(self):
            return {"retention_declared": True}

        def down(self, **kwargs):
            events.append("down")
            return RetentionAttestation(True, True, False, False, 0, 0, 0)

    def fail_completed_save(state, path):
        if any(chunk.get("status") == "complete" for chunk in state.chunks):
            raise OSError("synthetic state write failure")
        return save(state, path)

    def forbidden(*args, **kwargs):
        events.append("export")
        raise AssertionError("export ran before private state persisted")

    def runner(argv, **kwargs):
        _export_custody(Path(argv[argv.index("--out") + 1]))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(WaveState, "save", fail_completed_save)
    monkeypatch.setattr(wave, "write_wave_technical_export", forbidden)
    with pytest.raises(OSError, match="synthetic state write failure"):
        run_wave(**args, subprocess_runner=runner, lifecycle=Lifecycle())
    assert events == ["down"]
    assert not list(args["out_dir"].glob("*/wave_export.json"))


@pytest.mark.parametrize("error", ["remote_inspection_failed", "remote_inspection_incomplete", "PaddleVastError"])
def test_failed_attestation_preserves_only_the_defined_unavailable_sentinels(tmp_path, error):
    from tools.paddle_wave import _validate_attestation

    record = RetentionAttestation(True, False, True, True, -1, -1, -1, error=error).as_record()
    _validate_attestation(record)
    state = WaveState(version=1, config=PRODUCTION_CONFIG, partition=PARTITION, population_name="CTRL")
    state.sessions = [{"attestation": record}]
    state.save(WaveState.path_for(tmp_path, PARTITION, "CTRL"))
    published = wave_report(data_dir=tmp_path, config=PRODUCTION_CONFIG)["attestations"][0]
    assert published == {"population": "CTRL", **record}
    for key, value in (("request_artefacts", -2), ("page_byte_files", -3), ("temp_image_files", -1),
                       ("probes", -1), ("inspected", True), ("error", "synthetic-private-error")):
        with pytest.raises(WaveRefused):
            _validate_attestation({**record, key: value})
