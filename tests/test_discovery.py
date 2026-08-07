"""DSC-1: the discovery runner.

The dry-run acceptance test is corpus-marked (it re-analyses all 109). Every
other test here is fast and runs by default, including the two invariants that
make the runner safe to point at 3,506 unknown documents: it never reaches a
model, and the report never invents a finding.

Synthetic trees are built from real corpus bytes copied into `tmp_path`. No
test writes to the corpus, the archive, or the shared `webapp_data` cache.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

import corpus_gate
from discovery.inventory import (
    FROZEN_PDFS,
    DedupIndex,
    Inventory,
    baseline_deviations,
    dry_run_deviations,
    enumerate_root,
    pinned_hashes,
    pinned_manifest,
)
from discovery.report import (
    ROW_FIELDS,
    folder_agreement,
    render_report,
    summarize,
    write_hash_map,
    write_rows,
)
from discovery.runner import (
    MODE_DIGITAL,
    MODE_DRY_RUN,
    MODE_PROFILE_ONLY,
    DiscoveryRunner,
    DocumentRow,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "Bank Statements"
DIGITAL = "Chase/Chase Mar.pdf"
SCANNED = "Misc/Columbia May 26 complete.pdf"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A synthetic corpus root: one digital, one duplicate, one broken, one non-PDF."""
    (tmp_path / "BankX").mkdir()
    (tmp_path / "BankY").mkdir()
    digital = (CORPUS / DIGITAL).read_bytes()
    (tmp_path / "BankX" / "statement.pdf").write_bytes(digital)
    (tmp_path / "BankX" / "again.pdf").write_bytes(digital)
    (tmp_path / "BankY" / "broken.pdf").write_bytes(b"%PDF-1.4 not really a pdf\n")
    (tmp_path / "BankY" / "notes.txt").write_text("not a pdf", encoding="utf-8")
    return tmp_path


def _runner(root: Path, mode: str = MODE_DIGITAL, **kwargs) -> DiscoveryRunner:
    kwargs.setdefault("dedup", DedupIndex())
    return DiscoveryRunner(root, mode=mode, run_id="test-run", sink=None,
                           cache=None, **kwargs)


# --- inventory and partition ------------------------------------------------


def test_enumeration_counts_files_pdfs_and_bytes(tree: Path):
    inventory = enumerate_root(tree)
    assert inventory.files == 4          # three PDFs plus the .txt
    assert inventory.pdf_count == 3
    assert inventory.total_bytes == sum(
        p.stat().st_size for p in tree.rglob("*") if p.is_file()
    )
    assert inventory.pinned == ()        # nothing here is in the manifest...
    assert len(inventory.discovery) == 3  # ...so everything is discovery


def test_the_partition_is_the_pinned_manifest(tree: Path):
    """A pinned document under the root belongs to the truth set, not discovery."""
    manifest = pinned_manifest()
    target = tree / manifest[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((CORPUS / manifest[0]).read_bytes())

    inventory = enumerate_root(tree)
    assert manifest[0] in inventory.pinned
    assert manifest[0] not in inventory.discovery


def test_a_case_different_pinned_path_is_still_pinned(tree: Path):
    """The Scotiabank case: on-disk spelling differs from the manifest.

    An exact-match partition would move that statement into the discovery set,
    where it would be counted as an unknown document and skew every rollup.
    """
    wanted = "ScotiaBank/Scotiabank -2.pdf"
    assert wanted in pinned_manifest()
    on_disk = tree / "scotiabank" / "scotiabank -2.pdf"
    on_disk.parent.mkdir(parents=True, exist_ok=True)
    on_disk.write_bytes((CORPUS / wanted).read_bytes())

    inventory = enumerate_root(tree)
    assert inventory.pinned == ("scotiabank/scotiabank -2.pdf",)
    assert "scotiabank/scotiabank -2.pdf" not in inventory.discovery
    assert inventory.case_mismatches == ((wanted, "scotiabank/scotiabank -2.pdf"),)
    assert wanted not in inventory.missing_pinned


def test_baseline_deviations_name_every_difference(tree: Path):
    deviations = baseline_deviations(enumerate_root(tree))
    assert any("files" in line for line in deviations)
    assert any("PDFs" in line for line in deviations)
    assert any("pinned corpus document missing" in line for line in deviations)


def test_a_case_collision_is_a_deviation_not_a_guess():
    """On Linux two case-different paths are different files; refuse to guess."""
    inventory = Inventory(
        root=Path("."), files=1, pdfs=("a/B.pdf",), total_bytes=1,
        pinned=(), discovery=("a/B.pdf",), case_collisions=("a/b.pdf",),
    )
    assert any("collide case-insensitively" in line
               for line in baseline_deviations(inventory))


def test_dry_run_checks_the_truth_set_not_the_archive(tree: Path):
    """The dry run must be runnable in a clean checkout, so it never asks for
    3,615 PDFs — only for the 109 it is defined over."""
    deviations = dry_run_deviations(enumerate_root(tree))
    assert any("pinned corpus PDFs: 0" in line for line in deviations)
    assert not any(str(FROZEN_PDFS) in line for line in deviations)


# --- dedup ------------------------------------------------------------------


def test_dedup_flags_repeats_within_the_run_and_against_the_pinned_corpus():
    index = DedupIndex.with_pinned_corpus()
    pinned_path, pinned_sha = next(iter(pinned_hashes().items()))

    assert index.classify("A" * 64, "one.pdf") == ("unique", None)
    assert index.classify("A" * 64, "two.pdf") == ("duplicate", "one.pdf")
    assert index.classify(pinned_sha, "archive/copy.pdf") == (
        "pinned_corpus_duplicate", pinned_path
    )
    # The pinned document itself, at its own path, is not a duplicate of itself.
    assert index.classify(pinned_sha, pinned_path)[0] == "unique"


# --- modes ------------------------------------------------------------------


def test_profile_only_never_parses(tree: Path, monkeypatch):
    """Tranche 0 is intake facts. Nothing is read, nothing is dispatched."""
    import discovery.runner as runner_module

    monkeypatch.setattr(
        runner_module, "analyze_markdown",
        lambda *a, **k: pytest.fail("profile-only must not analyse"),
    )
    row = _runner(tree, MODE_PROFILE_ONLY).process("BankX/statement.pdf", "BankX")
    assert row.outcome_reason == "profile_only"
    assert row.classification == "digital"
    assert row.parser_id is None
    assert row.source_path == "none"


def test_an_invalid_pdf_is_recorded_not_crashed(tree: Path):
    row = _runner(tree).process("BankY/broken.pdf", "BankY")
    assert row.outcome_class == "failed"
    assert row.outcome_reason == "invalid_pdf"
    assert row.valid_pdf is False


def test_a_scanned_document_is_deferred_never_skipped(tree: Path, tmp_path: Path):
    """Tranche 1 does not OCR. The document is recorded as work not done.

    `deferred` is its own outcome class so that `failed` keeps meaning
    "attempted and errored" — DSC-2 acts on those two findings differently.
    """
    from telemetry import JsonlSink, read_jsonl

    scanned = tree / "BankZ" / "scan.pdf"
    scanned.parent.mkdir()
    scanned.write_bytes((CORPUS / SCANNED).read_bytes())

    sink = JsonlSink(tmp_path / "telemetry.jsonl")
    runner = DiscoveryRunner(tree, mode=MODE_DIGITAL, run_id="t", sink=sink,
                             cache=None, dedup=DedupIndex())
    row = runner.process("BankZ/scan.pdf", "BankZ")

    assert row.outcome_class == "deferred"
    assert row.outcome_reason == "deferred_scanned"
    assert row.classification == "scanned"
    assert row.source_path == "none"
    assert row.parser_id is None

    record = read_jsonl(tmp_path / "telemetry.jsonl")[0]
    assert record["outcome"]["class"] == "deferred"
    assert record["outcome"]["reason"] == "deferred_scanned"
    assert record["outcome"]["error_type"] is None

    summary = summarize([row], mode=MODE_DIGITAL, run_id="r")
    assert summary["deferred"] == 1
    assert summary["processed"] == 0
    assert summary["outcome"] == {}


def test_profile_only_rows_are_deferred_not_failed(tree: Path):
    """Tranche 0 asked no question, so nothing there failed."""
    row = _runner(tree, MODE_PROFILE_ONLY).process("BankX/statement.pdf", "BankX")
    assert (row.outcome_class, row.outcome_reason) == ("deferred", "profile_only")


def test_the_dry_run_reads_scanned_statements_from_committed_artifacts(tmp_path: Path):
    """That is what lets the dry run cover all 109 with zero OCR."""
    row = _runner(CORPUS, MODE_DRY_RUN).process(SCANNED, "Misc")
    assert row.source_path == "committed_artifact"
    assert row.parser_id == "columbia_bank"
    assert row.outcome_class in {"validated", "review"}


# --- the offline guarantee --------------------------------------------------


def test_no_model_extraction_can_happen(tree: Path, monkeypatch):
    """parse_mode='deterministic' makes the LLM branch unreachable."""
    import analysis.pipeline as pipeline

    monkeypatch.setattr(
        pipeline, "extract_statement",
        lambda *a, **k: pytest.fail("discovery must never call the extraction model"),
    )
    row = _runner(tree).process("BankX/statement.pdf", "BankX")
    assert row.parser_id == "chase"


def test_the_visual_ocr_client_module_is_never_even_imported(tree: Path):
    """`ocr.pipeline` imports `ocr.ocr_client` lazily inside the visual rung,
    so `allow_visual_ocr=False` means no model client exists in the process."""
    code = (
        "import sys; from pathlib import Path;"
        "from discovery.runner import DiscoveryRunner, MODE_DIGITAL;"
        "from discovery.inventory import DedupIndex;"
        f"r = DiscoveryRunner(Path({str(tree)!r}), mode=MODE_DIGITAL, run_id='t',"
        " sink=None, cache=None, dedup=DedupIndex());"
        "r.process('BankX/statement.pdf', 'BankX');"
        "print('ocr.ocr_client' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    # Compare only the LAST stdout line: on the CI runner a library prints a
    # harmless warning line to stdout before our sentinel (observed in run
    # 31137747002), and the sentinel is the verdict, not the noise around it.
    assert result.stdout.strip().splitlines()[-1] == "False", (
        "a model client was imported: " + result.stdout.strip()
    )


# --- report -----------------------------------------------------------------


def _row(**kwargs) -> DocumentRow:
    base = dict(relative_path="F/a.pdf", folder_label="F",
                content_sha256="A" * 64, byte_size=1)
    base.update(kwargs)
    return DocumentRow(**base)


def test_folder_agreement_buckets():
    assert folder_agreement(_row(folder_label="Chase", parser_id="chase")) == "agree"
    assert folder_agreement(
        _row(folder_label="Others", parser_id="altana")) == "unlabelled_folder"
    assert folder_agreement(_row(parser_id=None)) == "no_claim"
    # An abbreviation is UNMATCHED, not a disagreement: naming it "disagree"
    # would manufacture a detection-accuracy problem out of string matching.
    assert folder_agreement(
        _row(folder_label="BofA", parser_id="bank_of_america")) == "label_unmatched"


def test_cached_rows_do_not_count_as_unclaimed():
    """Regression: a re-run served from the D-3 analysis cache re-dispatches
    nothing, and counting those as unclaimed reported ~0% coverage and turned
    every folder into an 'unknown-layout cluster'."""
    rows = [
        _row(dispatch_outcome="claimed", parser_id="chase", outcome_class="validated",
             outcome_reason="approved"),
        _row(dispatch_outcome=None, outcome_class="validated", outcome_reason="approved",
             cache_analysis="hit"),
    ]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["dispatched"] == 1
    assert summary["dispatch_cached"] == 1
    assert summary["deterministic_coverage"] == 1.0
    assert summary["unknown_layout_clusters"] == {}
    assert "served from cache" in render_report(summary)


def test_deferred_documents_are_outside_the_coverage_denominator():
    rows = [
        _row(dispatch_outcome="claimed", parser_id="chase", outcome_class="validated",
             outcome_reason="approved"),
        _row(outcome_class="deferred", outcome_reason="deferred_scanned"),
    ]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["documents"] == 2
    assert summary["processed"] == 1
    assert summary["deferred"] == 1
    assert summary["deferred_reasons"] == {"deferred_scanned": 1}
    assert summary["deterministic_coverage"] == 1.0


def test_unknown_layout_clusters_and_near_misses_rank_by_volume():
    rows = [
        _row(relative_path=f"Unknown/{i}.pdf", folder_label="Unknown",
             dispatch_outcome="unclaimed", near_miss=["bmo:0.167"],
             outcome_class="failed", outcome_reason="no_parser_matched")
        for i in range(3)
    ]
    rows.append(_row(folder_label="Rare", dispatch_outcome="unclaimed",
                     outcome_class="failed", outcome_reason="no_parser_matched"))
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert list(summary["unknown_layout_clusters"]) == ["Unknown", "Rare"]
    assert summary["near_miss_parsers"] == {"bmo": 3}


def test_ambiguity_clusters_group_by_candidate_set():
    rows = [
        _row(dispatch_outcome="ambiguous", candidates=["b:0.5", "a:0.5"],
             outcome_class="failed", outcome_reason="parser_ambiguous")
        for _ in range(2)
    ]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["ambiguity_clusters"] == {"a + b": 2}


def test_the_report_is_ascii_only():
    """It is printed by a CLI; a legacy console code page must not be able to
    turn a measurement into a UnicodeEncodeError."""
    rows = [_row(dispatch_outcome="claimed", parser_id="chase",
                 outcome_class="validated", outcome_reason="approved")]
    assert render_report(summarize(rows, mode=MODE_DIGITAL, run_id="r")).isascii()


# --- the two artifacts, two audiences ---------------------------------------


def test_telemetry_carries_no_path_while_the_report_does(tree: Path, tmp_path: Path):
    """H-3's invariant holds for telemetry; the report is a different artifact
    with a different audience and deliberately carries paths for adjudication."""
    from telemetry import JsonlSink, read_jsonl

    sink = JsonlSink(tmp_path / "telemetry.jsonl")
    runner = DiscoveryRunner(tree, mode=MODE_DIGITAL, run_id="t", sink=sink,
                             cache=None, dedup=DedupIndex())
    row = runner.process("BankX/statement.pdf", "BankX")

    records = read_jsonl(tmp_path / "telemetry.jsonl")
    assert len(records) == 1
    blob = json.dumps(records[0])
    assert "BankX" not in blob
    assert "statement.pdf" not in blob
    assert row.content_sha256 in blob

    write_rows(tmp_path / "rows.csv", [row])
    written = list(csv.DictReader((tmp_path / "rows.csv").open(encoding="utf-8")))
    assert written[0]["relative_path"] == "BankX/statement.pdf"
    assert written[0]["folder_label"] == "BankX"
    assert set(written[0]) == set(ROW_FIELDS)


def test_masking_keeps_only_the_last_four_characters():
    from discovery.runner import _mask_last4

    assert _mask_last4("009167365168") == "5168"
    assert _mask_last4("SJ 815-30355-9") == "3559"
    assert _mask_last4("XXXXXX4166") == "4166"
    assert _mask_last4("12") == "12"
    assert _mask_last4(None) is None
    assert _mask_last4("") is None


def test_a_real_account_number_never_reaches_the_row():
    """Columbia's statement carries an account number; only its last 4 survive."""
    row = _runner(CORPUS, MODE_DRY_RUN).process(SCANNED, "Misc")
    from analysis.pipeline import analyze_markdown
    from corpus_artifacts import cached_markdown

    markdown = cached_markdown((CORPUS / SCANNED).read_bytes(),
                               ROOT / "tests" / "corpus_cache")
    full = analyze_markdown(markdown, parse_mode="deterministic").statement.account_number
    assert full and len(full) > 4
    assert row.account_last4 == full[-4:]
    assert full not in json.dumps(row.as_dict())


def test_the_hash_map_is_its_own_file(tmp_path: Path):
    """H-3 ruling 4: telemetry has no paths, so the join lives here and only here."""
    rows = [_row(content_sha256="B" * 64, relative_path="F/a.pdf")]
    write_hash_map(tmp_path / "hash_map.csv", rows)
    written = list(csv.reader((tmp_path / "hash_map.csv").open(encoding="utf-8")))
    assert written[0] == ["content_sha256", "relative_path"]
    assert written[1] == ["B" * 64, "F/a.pdf"]


# --- the dry-run acceptance gate --------------------------------------------


@pytest.mark.corpus
def test_dry_run_reproduces_known_truth():
    """DSC-1's acceptance: the runner must reproduce what we already know
    before it is ever pointed at 3,506 unknown documents.

    Every number here is independently established elsewhere — the manifest by
    the corpus gate, the parsers by R-3's recorded expectations, the outcome
    split by H-3's telemetry anchor — and this asserts the runner agrees with
    all three at once.
    """
    from discovery.cli import run

    summary = run(CORPUS, MODE_DRY_RUN, Path("discovery_reports"), use_cache=False)
    rows = {row.relative_path: row for row in summary.pop("_rows")}

    assert summary["documents"] == 109
    assert summary["processed"] == 109
    assert summary["deferred"] == 0
    assert summary["dispatched"] == 109
    assert summary["deterministic_coverage"] == 1.0
    assert summary["dispatch"] == {"claimed": 109}
    assert summary["outcome"] == {"validated": 100, "review": 6, "withheld": 3}
    # Nothing can defer on the pinned set: the six image-only statements are
    # served from their committed OCR artifacts.
    assert "deferred" not in summary["outcome"]
    assert summary["deferred"] == 0
    assert summary["dedup"] == {"unique": 109}
    assert summary["ambiguity_clusters"] == {}
    assert summary["unknown_layout_clusters"] == {}

    withheld = {
        Path(path).name for path, row in rows.items() if row.outcome_class == "withheld"
    }
    assert withheld == corpus_gate.WITHHELD_STATEMENTS

    expectations = json.loads(
        (ROOT / "tests" / "data" / "parser_expectations.json").read_text(encoding="utf-8")
    )["documents"]
    assert len(expectations) == 109
    for entry in expectations:
        expected = entry["variant_id"] or entry["parser_id"]
        assert rows[entry["path"]].parser_id == expected, entry["path"]
        assert rows[entry["path"]].content_sha256 == entry["sha256"]
