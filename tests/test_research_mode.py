"""P22-TRUTHTABLE item 6 (D7, D8, case 23): the research run mode.

    python -m discovery --research-paddle --population <shas.txt> --research-partition <id>
                        --data-dir <research dir> --out <run dir>

Every refusal is proven at the door (M12 the two literals, M13 a production
`--data-dir`, M14 a holdout sha), the trigger `operator_forced_paddle` is
proven reachable in this mode ONLY (M11), `enabled == {"paddle"}` is a mode
constant (M10 is the D4 AST tripwire in `tests/test_escalation_tripwires.py`),
and the end-to-end proof runs on SYNTHETIC rendered PDFs against the
in-process fake worker: exactly one request per page, rows carry the
partition, `run_of_record` refuses the partition.

Hermeticity (cell K's idiom, `tests/test_run_of_record.py`): the gitignored
`.env` of the main checkout carries REAL `PADDLE_*` connection variables and
`load_dotenv(override=False)` re-injects any that are ABSENT — so every test
here sets every `PADDLE_*` variable to a value of its own (present-but-empty
= unconfigured) and never depends on the host. The customer-data literal is
set ONLY inside a test's own (monkeypatched) process environment or inside a
subprocess's environment, and never against `Bank Statements/`.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from discovery import cli
from discovery.inventory import DedupIndex
from discovery.runner import (
    LOCAL_OCR_MODES,
    MODE_DIGITAL,
    MODE_DRY_RUN,
    MODE_PROFILE_ONLY,
    MODE_RESEARCH_PADDLE,
    MODE_SCANNED,
    MODE_SCANNED_PADDLE,
    MODE_SCANNED_VISUAL,
    PADDLE_RESEARCH,
    RESEARCH_TRIGGERS,
    DiscoveryRunner,
    holdout_sha16s_from_digest,
    read_population,
    refuse_production_data_dir,
)
from ocr.document import StatementMarkdown
from ocr.escalation import ADMITTED_TRIGGERS, ALL_TRIGGERS, OPERATOR_FORCED_PADDLE, EscalationRouter
from ocr.paddle_config import (
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
)
from tests.paddle_fake_worker import FakeWorker
from tests.paddle_synthetic import build_ledger_page, render_image_pdf, render_native_pdf, synthetic_paddle_result

ROOT = Path(__file__).resolve().parents[1]
PARTITION = "synthetic-2031-a"

_PADDLE_ENV_NAMES = (
    "PADDLE_PROVIDER", "PADDLE_EXECUTION_CLASS", "PADDLE_VAST_HOST", "PADDLE_VAST_SSH_PORT",
    "PADDLE_VAST_SSH_USER", PADDLE_REMOTE_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    "PADDLE_WORKER_URL", "PADDLE_WORKER_PORT", "PADDLE_TUNNEL_LOCAL_PORT", "PADDLE_RUNTIME_DIR",
)


def _unconfigure_paddle(monkeypatch) -> None:
    for name in list(os.environ):
        if name.startswith("PADDLE_"):
            monkeypatch.setenv(name, "")
    for name in _PADDLE_ENV_NAMES:
        monkeypatch.setenv(name, "")


def _remote_paid_env(monkeypatch, worker_url: str, *, remote: bool = True, customer: bool = True) -> None:
    _unconfigure_paddle(monkeypatch)
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


def _tesseract(monkeypatch, text: str | None):
    def fake(pdf_bytes, source_file="", **kwargs):
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


@pytest.fixture
def synthetic_root(tmp_path: Path) -> dict:
    """Three rendered SYNTHETIC PDFs: two image-only pages in the population,
    one native page outside it. Nothing here comes from a real document."""
    root = tmp_path / "root"
    (root / "SynthA").mkdir(parents=True)
    (root / "SynthB").mkdir(parents=True)
    # `page_c` is DELIBERATELY the largest: at 4 rows the rendered PDF carries
    # 215 characters and profiles `mixed`, so the intake ladder reaches for
    # Tesseract and the native rung never claims it — which would make the
    # "a natively-read document is admitted to the research read too" proof
    # below vacuous (it would take the recovery path like the two scans). At
    # 12 rows it profiles `digital` and the native rung reads it, so the
    # research admission is proven on a document Phase 1 handles PERFECTLY,
    # which is the case D8 is actually about.
    page_a, page_b, page_c = build_ledger_page(6), build_ledger_page(9), build_ledger_page(12)
    (root / "SynthA" / "scan-a.pdf").write_bytes(render_image_pdf(page_a))
    (root / "SynthA" / "scan-b.pdf").write_bytes(render_image_pdf(page_b))
    (root / "SynthB" / "native-c.pdf").write_bytes(render_native_pdf(page_c))
    from ocr.inspect import inspect_pdf

    shas = {name: inspect_pdf((root / folder / name).read_bytes()).content_sha256
            for folder, name in (("SynthA", "scan-a.pdf"), ("SynthA", "scan-b.pdf"), ("SynthB", "native-c.pdf"))}
    population = tmp_path / "population.txt"
    population.write_text(
        "# synthetic research population\n"
        f"{shas['scan-a.pdf']}\n"
        f"{shas['scan-b.pdf'].lower()}\n"
        "\n", encoding="utf-8",
    )
    digest = tmp_path / "MANIFEST_DIGEST.txt"
    digest.write_text(
        "# MANIFEST_DIGEST: a synthetic test digest\nstore_version: 1\nrecord_count: 0\n"
        "chain_head: GENESIS\nholdout_chain_head: GENESIS\nadjudicated_sha16:\nholdout_sha16_status:\n",
        encoding="utf-8",
    )
    pages = {page_a: 1, page_b: 1, page_c: 1}
    return {"root": root, "shas": shas, "population": population, "digest": digest,
            "pages": {"scan-a.pdf": page_a, "scan-b.pdf": page_b, "native-c.pdf": page_c},
            "data_dir": tmp_path / "research_data", "out": tmp_path / "out", "tmp": tmp_path}


def _research_args(fx: dict, **overrides) -> list[str]:
    values = {
        "--population": str(fx["population"]), "--research-partition": PARTITION,
        "--data-dir": str(fx["data_dir"]), "--root": str(fx["root"]), "--out": str(fx["out"]),
        "--holdout-digest": str(fx["digest"]),
    }
    values.update(overrides)
    argv = ["--research-paddle", "--skip-baseline", "--quiet"]
    for flag, value in values.items():
        if value is not None:
            argv += [flag, value]
    return argv


# ---------------------------------------------------------------------------
# the vocabulary and the mode constant
# ---------------------------------------------------------------------------


def test_the_trigger_is_admitted_and_mirrored():
    from telemetry.record import EXTRACTION_TRIGGERS

    assert OPERATOR_FORCED_PADDLE == "operator_forced_paddle"
    assert OPERATOR_FORCED_PADDLE in ALL_TRIGGERS and OPERATOR_FORCED_PADDLE in ADMITTED_TRIGGERS
    assert EXTRACTION_TRIGGERS == ALL_TRIGGERS
    assert RESEARCH_TRIGGERS == frozenset({OPERATOR_FORCED_PADDLE})


def test_research_mode_enables_exactly_paddle_as_a_mode_constant(tmp_path):
    runner = DiscoveryRunner(tmp_path, mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                             population=frozenset({"A" * 64}), research_partition=PARTITION)
    assert runner.enabled_extractors == frozenset({"paddle"})
    assert runner.allow_local_ocr and MODE_RESEARCH_PADDLE in LOCAL_OCR_MODES
    assert runner.research_partition == PARTITION


def test_a_research_runner_requires_a_population_and_a_partition(tmp_path):
    with pytest.raises(ValueError, match="population"):
        DiscoveryRunner(tmp_path, mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                        research_partition=PARTITION)
    with pytest.raises(ValueError, match="research_partition"):
        DiscoveryRunner(tmp_path, mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                        population=frozenset({"A" * 64}))
    with pytest.raises(ValueError, match="research_partition"):
        DiscoveryRunner(tmp_path, mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                        population=frozenset({"A" * 64}), research_partition="not valid!")


@pytest.mark.parametrize("mode", [MODE_DIGITAL, MODE_SCANNED, MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE,
                                  MODE_PROFILE_ONLY, MODE_DRY_RUN])
def test_a_partition_or_a_population_outside_research_mode_is_refused(tmp_path, mode):
    with pytest.raises(ValueError, match="research"):
        DiscoveryRunner(tmp_path, mode=mode, run_id="t", dedup=DedupIndex(), research_partition=PARTITION)
    with pytest.raises(ValueError, match="research"):
        DiscoveryRunner(tmp_path, mode=mode, run_id="t", dedup=DedupIndex(), population=frozenset({"A" * 64}))


def test_read_population_accepts_comments_and_case_and_refuses_junk(tmp_path):
    path = tmp_path / "p.txt"
    path.write_text("# c\n" + "a" * 64 + "\n\n" + "B" * 64 + "  # trailing\n", encoding="utf-8")
    assert read_population(path) == frozenset({"A" * 64, "B" * 64})
    path.write_text("not-a-sha\n", encoding="utf-8")
    with pytest.raises(ValueError, match="population"):
        read_population(path)
    path.write_text("# only a comment\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        read_population(path)


def test_the_holdout_digest_reader_reads_only_the_status_block(tmp_path):
    digest = tmp_path / "d.txt"
    digest.write_text(
        "# header\nstore_version: 1\nrecord_count: 2\nchain_head: GENESIS\nholdout_chain_head: GENESIS\n"
        "adjudicated_sha16:\n- AAAAAAAAAAAAAAAA\nholdout_sha16_status:\n- BBBBBBBBBBBBBBBB unseen\n"
        "- CCCCCCCCCCCCCCCC evaluated\n", encoding="utf-8")
    assert holdout_sha16s_from_digest(digest) == frozenset({"BBBBBBBBBBBBBBBB", "CCCCCCCCCCCCCCCC"})
    assert holdout_sha16s_from_digest(ROOT / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt") == frozenset()
    with pytest.raises(ValueError, match="digest"):
        holdout_sha16s_from_digest(tmp_path / "missing.txt")


# ---------------------------------------------------------------------------
# the door: preflight refusals (M12, M13, M14)
# ---------------------------------------------------------------------------


def test_research_mode_refuses_without_both_literals(synthetic_root, monkeypatch, capsys):
    """M12's killer, both halves: each missing literal is NAMED."""
    fx = synthetic_root
    for remote, customer, missing in ((False, True, PADDLE_REMOTE_OPT_IN_ENV),
                                      (True, False, PADDLE_CUSTOMER_DATA_OPT_IN_ENV),
                                      (False, False, PADDLE_REMOTE_OPT_IN_ENV)):
        _remote_paid_env(monkeypatch, "http://127.0.0.1:1", remote=remote, customer=customer)
        assert cli.main(_research_args(fx)) == 2
        err = capsys.readouterr().err
        assert "research-paddle cannot start" in err and missing in err
        assert not (fx["out"]).exists()


def test_research_mode_refuses_a_wrong_literal_value(synthetic_root, monkeypatch, capsys):
    fx = synthetic_root
    _remote_paid_env(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setenv(PADDLE_CUSTOMER_DATA_OPT_IN_ENV, "yes")
    assert cli.main(_research_args(fx)) == 2
    assert PADDLE_CUSTOMER_DATA_OPT_IN_ENV in capsys.readouterr().err


def test_research_mode_requires_its_three_arguments(synthetic_root, monkeypatch, capsys):
    fx = synthetic_root
    _remote_paid_env(monkeypatch, "http://127.0.0.1:1")
    for flag in ("--population", "--research-partition", "--data-dir"):
        assert cli.main(_research_args(fx, **{flag: None})) == 2
        assert flag in capsys.readouterr().err


def test_research_flags_are_refused_outside_research_mode(synthetic_root, monkeypatch, capsys):
    fx = synthetic_root
    _remote_paid_env(monkeypatch, "http://127.0.0.1:1")
    argv = ["--digital", "--skip-baseline", "--root", str(fx["root"]), "--out", str(fx["out"]),
            "--population", str(fx["population"])]
    assert cli.main(argv) == 2
    assert "--research-paddle only" in capsys.readouterr().err


def test_a_malformed_partition_is_refused_at_the_door(synthetic_root, monkeypatch, capsys):
    fx = synthetic_root
    _remote_paid_env(monkeypatch, "http://127.0.0.1:1")
    assert cli.main(_research_args(fx, **{"--research-partition": "bad id!"})) == 2
    assert "research-partition" in capsys.readouterr().err


@pytest.mark.parametrize("bad", [
    "webapp_data", ".claude/recovery/webapp_data_train11_cold", "somewhere/webapp_data_train9_cold",
    ".claude/recovery/anything",
])
def test_a_production_data_dir_is_refused(synthetic_root, monkeypatch, capsys, bad):
    """M13's killer: the production cache and every cold cache are refused
    by shape and by location, resolved against the checkout root."""
    fx = synthetic_root
    _remote_paid_env(monkeypatch, "http://127.0.0.1:1")
    with pytest.raises(ValueError, match="production"):
        refuse_production_data_dir(Path(bad))
    with pytest.raises(ValueError, match="production"):
        refuse_production_data_dir(ROOT / bad)
    assert cli.main(_research_args(fx, **{"--data-dir": str(ROOT / bad)})) == 2
    assert "production" in capsys.readouterr().err
    assert not (ROOT / bad / "webapp.db").exists() or bad != "somewhere/webapp_data_train9_cold"


def test_the_default_webapp_data_dir_is_refused_by_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path / "prod_cache"))
    with pytest.raises(ValueError, match="production"):
        refuse_production_data_dir(tmp_path / "prod_cache")
    refuse_production_data_dir(tmp_path / "research_cache")  # a sibling is fine


def test_a_population_that_names_a_holdout_sha_is_refused_at_the_door(synthetic_root, monkeypatch, capsys):
    """M14's killer (the CLI half): the population intersects the holdout
    digest list -> refused before any document is enumerated."""
    fx = synthetic_root
    _remote_paid_env(monkeypatch, "http://127.0.0.1:1")
    held = fx["shas"]["scan-a.pdf"][:16]
    fx["digest"].write_text(fx["digest"].read_text(encoding="utf-8") + f"- {held} unseen\n", encoding="utf-8")
    assert cli.main(_research_args(fx)) == 2
    err = capsys.readouterr().err
    assert "holdout" in err and "1" in err
    assert held not in err  # the refusal counts; it never prints a sha


def test_the_runner_refuses_a_holdout_sha_before_any_read(synthetic_root, monkeypatch):
    """M14's killer (the runner half): a runner handed the holdout set
    refuses the row itself — no offline read, no Paddle read."""
    fx = synthetic_root
    sha = fx["shas"]["scan-a.pdf"]
    runner = DiscoveryRunner(fx["root"], mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                             population=frozenset({sha}), research_partition=PARTITION,
                             holdout_sha16=frozenset({sha[:16]}))

    def never(*args, **kwargs):
        raise AssertionError("a holdout document must never be read")

    monkeypatch.setattr(runner, "_read", never)
    monkeypatch.setattr(runner, "_read_paddle", never)
    row = runner.process("SynthA/scan-a.pdf", "SynthA")
    assert (row.outcome_class, row.outcome_reason) == ("deferred", "research_refused_holdout")
    assert row.research_partition == PARTITION
    assert row.escalation_trigger == "" and row.paddle_rung == "not_attempted"


def test_a_sha_outside_the_population_is_skipped_without_a_read(synthetic_root, monkeypatch):
    fx = synthetic_root
    runner = DiscoveryRunner(fx["root"], mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                             population=frozenset({fx["shas"]["scan-a.pdf"]}), research_partition=PARTITION)

    def never(*args, **kwargs):
        raise AssertionError("a document outside the population must never be read")

    monkeypatch.setattr(runner, "_read", never)
    row = runner.process("SynthB/native-c.pdf", "SynthB")
    assert (row.outcome_class, row.outcome_reason) == ("deferred", "research_skipped_not_in_population")
    assert row.research_partition == PARTITION
    assert row.document_class in ("KIND_UNCERTAIN", "STATEMENT_COMPLETE", "STATEMENT_PARTIAL")


# ---------------------------------------------------------------------------
# the trigger is reachable in research mode ONLY (M11)
# ---------------------------------------------------------------------------


class _Spy:
    def __init__(self):
        self.seen: list[frozenset] = []
        self.real = EscalationRouter.decide

    def __call__(self, inputs):
        self.seen.append(inputs.triggers)
        return self.real(inputs)


#: A synthetic offline read, long enough to clear the extraction gate's
#: character floor. `None` means "the offline ladder produced nothing".
#:
#: Both values are needed and the reason is a mutant that SURVIVED the first
#: version of this test (M11, reproduced 2026-09-10): with the offline ladder
#: producing nothing, every document takes the RECOVERY path, and a mutant
#: that admits the research trigger on the UPGRADE path is live but never
#: executed. A test named after a gate is not a test of that gate. With a real
#: offline read the scan reaches the upgrade decision in the two modes that
#: have an escalation extractor at all, and the mutant dies there.
_OFFLINE_READS = (None, "SYNTHETIC LEDGER LINE FOR THE OFFLINE READ " * 12)


@pytest.mark.parametrize("offline_text", _OFFLINE_READS)
@pytest.mark.parametrize("mode", [MODE_DIGITAL, MODE_SCANNED, MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE, MODE_DRY_RUN])
def test_no_other_mode_can_supply_the_research_trigger(synthetic_root, monkeypatch, mode, offline_text):
    """M11's killer: every router decision made in every other mode over a
    scan AND a native document, on BOTH the recovery path (the offline ladder
    produced nothing) and the upgrade path (it produced a read no reader
    claimed), carries no `operator_forced_paddle`."""
    fx = synthetic_root
    _tesseract(monkeypatch, offline_text)
    spy = _Spy()
    monkeypatch.setattr(EscalationRouter, "decide", staticmethod(spy))
    monkeypatch.setattr("ocr.availability.probe_visual_ocr", lambda: None, raising=False)
    _remote_paid_env(monkeypatch, "http://127.0.0.1:1", remote=False, customer=False)
    runner = DiscoveryRunner(fx["root"], mode=mode, run_id="t", dedup=DedupIndex(), sink=None, cache=None)
    for folder, name in (("SynthA", "scan-a.pdf"), ("SynthB", "native-c.pdf")):
        try:
            row = runner.process(f"{folder}/{name}", folder)
        except Exception:  # a transport failure in the visual/paddle rung is not what this test measures
            continue
        assert row.escalation_trigger != OPERATOR_FORCED_PADDLE
        assert row.research_partition == ""
    for triggers in spy.seen:
        assert OPERATOR_FORCED_PADDLE not in triggers, (mode, triggers)


def test_research_mode_supplies_exactly_the_research_trigger_for_every_population_document(synthetic_root, monkeypatch):
    fx = synthetic_root
    _tesseract(monkeypatch, None)
    spy = _Spy()
    monkeypatch.setattr(EscalationRouter, "decide", staticmethod(spy))
    with FakeWorker() as fake:
        _remote_paid_env(monkeypatch, fake.url)
        population = frozenset({fx["shas"]["scan-a.pdf"], fx["shas"]["native-c.pdf"]})
        runner = DiscoveryRunner(fx["root"], mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                                 population=population, research_partition=PARTITION)
        scan = runner.process("SynthA/scan-a.pdf", "SynthA")
        native = runner.process("SynthB/native-c.pdf", "SynthB")
    assert spy.seen == [RESEARCH_TRIGGERS, RESEARCH_TRIGGERS]
    for row in (scan, native):
        assert row.escalation_trigger == OPERATOR_FORCED_PADDLE
        assert row.escalation_extractor == "paddle"
        assert row.research_partition == PARTITION
        assert row.paddle_rung == PADDLE_RESEARCH == "research"
        assert row.stage_extract == "paddle"
    assert native.offline_source_model.startswith("native-pdf-text")


def test_the_worker_source_names_no_research_trigger():
    """The webapp's one `decide(` site (`_force_ocr_decision`) never names the
    research trigger — by source, not by discipline."""
    source = (ROOT / "webapp" / "worker.py").read_text(encoding="utf-8")
    assert "OPERATOR_FORCED_PADDLE" not in source and "operator_forced_paddle" not in source


def test_the_research_trigger_is_named_only_inside_the_research_constant_in_the_runner():
    import ast

    source = (ROOT / "discovery" / "runner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    uses = [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == "OPERATOR_FORCED_PADDLE"]
    assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "RESEARCH_TRIGGERS" for t in node.targets))
    imports = {node.lineno for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert all(line == assignment.lineno or line in imports for line in uses), uses


# ---------------------------------------------------------------------------
# the end-to-end synthetic proof (case 23): the runner, in process
# ---------------------------------------------------------------------------


def test_end_to_end_one_fake_worker_request_per_page_rows_carry_the_partition(synthetic_root, monkeypatch):
    fx = synthetic_root
    _tesseract(monkeypatch, None)
    pages = fx["pages"]

    def result_for(page_index, image_bytes):
        # both population documents are one-page ledgers; the fake answers from the known positions
        return synthetic_paddle_result(pages["scan-a.pdf"] if page_index == 0 else pages["scan-b.pdf"])

    with FakeWorker(result_for=result_for) as fake:
        _remote_paid_env(monkeypatch, fake.url)
        population = read_population(fx["population"])
        runner = DiscoveryRunner(fx["root"], mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                                 population=population, research_partition=PARTITION)
        rows = [runner.process("SynthA/scan-a.pdf", "SynthA"), runner.process("SynthA/scan-b.pdf", "SynthA"),
                runner.process("SynthB/native-c.pdf", "SynthB")]
    assert len(fake.requests) == 2  # exactly one request per page of the population (two one-page documents)
    assert sorted(r["page_index"] for r in fake.requests) == [0, 0]
    for row in rows[:2]:
        assert row.research_partition == PARTITION
        assert row.paddle_rung == "research" and row.escalation_trigger == OPERATOR_FORCED_PADDLE
        assert row.source_path == "paddle" and row.stage_extract == "paddle" and row.stage_evidence == "present"
        assert row.evidence_sha256 and row.paddle_provider == "vast.ai" and row.paddle_execution_class == "remote_paid"
        assert row.stage_geometry == "not_attempted" and row.stage_layout == "not_attempted"
        assert row.stage_candidate in ("claimed", "unclaimed", "parser_exception", "ambiguous", "error")
        assert row.stage_verdict == row.outcome_class
        assert row.document_class in KINDS_ALLOWED
    assert (rows[2].outcome_class, rows[2].outcome_reason) == ("deferred", "research_skipped_not_in_population")
    assert rows[2].research_partition == PARTITION


KINDS_ALLOWED = ("STATEMENT_COMPLETE", "STATEMENT_PARTIAL", "STATEMENT_ILLEGIBLE", "ACTIVITY_EXPORT",
                 "NOT_A_STATEMENT", "FILE_INVALID", "KIND_UNCERTAIN")


def test_research_reads_are_keyed_under_the_partition_in_their_own_cache(synthetic_root, monkeypatch, tmp_path):
    from webapp.artifact_cache import cache_key, ocr_settings_key, open_cache

    fx = synthetic_root
    _tesseract(monkeypatch, None)
    cache = open_cache(fx["data_dir"])
    with FakeWorker(result_for=lambda i, b: synthetic_paddle_result(fx["pages"]["scan-a.pdf"])) as fake:
        _remote_paid_env(monkeypatch, fake.url)
        runner = DiscoveryRunner(fx["root"], mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                                 cache=cache, population=frozenset({fx["shas"]["scan-a.pdf"]}),
                                 research_partition=PARTITION)
        first = runner.process("SynthA/scan-a.pdf", "SynthA")
        second = runner.process("SynthA/scan-a.pdf", "SynthA")
    assert first.cache_paddle == "miss" and second.cache_paddle == "hit"
    assert len(fake.requests) == 1  # the second run was served from the research partition
    partition_key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
                                     allow_paddle_ocr=True, research_partition=PARTITION)
    production_key = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
                                      allow_paddle_ocr=True)
    assert partition_key != production_key
    assert cache._artifact_path("ocr", cache_key("ocr", first.content_sha256, partition_key)).exists()
    assert not cache._artifact_path("ocr", cache_key("ocr", first.content_sha256, production_key)).exists()


# ---------------------------------------------------------------------------
# the end-to-end synthetic proof (case 23): the CLI, in a subprocess whose
# environment alone carries the customer-data literal
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="the research mode's offline ladder needs tesseract on PATH")
def test_cli_end_to_end_writes_a_research_run_that_run_of_record_refuses(synthetic_root):
    from telemetry.run_of_record import ResearchPartitionRefused, partitions_for_run

    fx = synthetic_root
    pages = fx["pages"]
    by_sha16 = {fx["shas"]["scan-a.pdf"][:16]: pages["scan-a.pdf"], fx["shas"]["scan-b.pdf"][:16]: pages["scan-b.pdf"]}

    def result_for(page_index, image_bytes):
        return synthetic_paddle_result(pages["scan-a.pdf"])  # any well-formed synthetic result will do for the proof

    env = {name: value for name, value in os.environ.items() if not name.startswith("PADDLE_")}
    for name in _PADDLE_ENV_NAMES:
        env[name] = ""
    with FakeWorker(result_for=result_for) as fake:
        env.update({
            "PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "remote_paid",
            "PADDLE_VAST_HOST": "test-host.invalid", "PADDLE_VAST_SSH_PORT": "22", "PADDLE_VAST_SSH_USER": "test-user",
            "PADDLE_WORKER_URL": fake.url, PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL,
            PADDLE_CUSTOMER_DATA_OPT_IN_ENV: PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
            "RECONSTRUCTION_MODE": "off", "WEBAPP_DATA_DIR": str(fx["tmp"] / "never_used_prod"),
            "PYTHONIOENCODING": "utf-8",
        })
        completed = subprocess.run(
            [sys.executable, "-m", "discovery", *_research_args(fx)],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=900,
        )
        requests = list(fake.requests)
    assert completed.returncode == 0, completed.stderr[-4000:]
    assert len(requests) == 2, requests
    run_dir = next(p for p in fx["out"].iterdir() if p.is_dir())
    rows = list(csv.DictReader((run_dir / "rows.csv").open(encoding="utf-8", newline="")))
    assert len(rows) == 3
    research = [r for r in rows if r["outcome_reason"] != "research_skipped_not_in_population"]
    assert len(research) == 2
    for row in research:
        assert row["research_partition"] == PARTITION and row["escalation_trigger"] == OPERATOR_FORCED_PADDLE
        assert row["paddle_rung"] == "research" and row["source_path"] == "paddle"
        assert row["content_sha256"][:16] in by_sha16
    skipped = next(r for r in rows if r["outcome_reason"] == "research_skipped_not_in_population")
    assert skipped["research_partition"] == PARTITION
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["research"]["partition"] == PARTITION and summary["research"]["attempted"] == 2
    assert summary["raw_coverage"]["denominator"] == 0  # every row is research: the headline is empty by construction
    provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["run_of_record"]["partitions"]["research_partition"] == PARTITION
    assert provenance["run_of_record"]["partitions"]["mode"] == MODE_RESEARCH_PADDLE
    with pytest.raises(ResearchPartitionRefused):
        partitions_for_run(run_dir)
    # The research run wrote its artifacts to ITS OWN directory and none to the
    # production cache. The assertion is about ARTIFACTS, not about the
    # database file: `python -m discovery` creates an empty
    # `$WEBAPP_DATA_DIR/webapp.db` at IMPORT time on every run and always has
    # — `discovery/inventory.py` imports `corpus_gate`, which imports
    # `adb_forensic_audit`, which imports `webapp.app`, which constructs a
    # `JobStore()` at module level. That is a pre-existing import-time side
    # effect of the whole CLI, unrelated to this mode and outside this card's
    # file ownership; it is recorded as a finding rather than asserted away.
    assert not (fx["tmp"] / "never_used_prod" / "artifacts").exists()
    assert (fx["data_dir"] / "webapp.db").exists()
    assert list((fx["data_dir"] / "artifacts").rglob("*.json"))
