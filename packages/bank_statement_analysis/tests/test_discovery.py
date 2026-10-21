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
from collections import Counter
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
    PARSER_ID_LIVE_DETECT,
    PARSER_ID_LIVE_DISPATCH,
    PARSER_ID_UNAVAILABLE,
    DiscoveryRunner,
    DocumentRow,
)
from tests.statements import statements_dir
from tests.helpers import _row

ROOT = Path(__file__).resolve().parents[1]
DIGITAL = "Chase/Chase Mar.pdf"
#: An image-only corpus statement whose committed OCR artifact a registration
#: both claims AND publishes — the two properties every use below needs.
#:
#: It was `Misc/Columbia May 26 complete.pdf` until W3 §REPAIRDOC removed the
#: two amount-rewriting repairs from `analysis/columbia_bank.py`; that document
#: is now a pinned REFUSAL (`corpus_gate.PINNED_REFUSALS`) and publishes
#: nothing, so it can no longer stand for "a scanned statement the dry run
#: resolves". First Farmers is the same class of fixture: zero native text, an
#: artifact committed in `tests/corpus_cache`, and a printed account number
#: longer than four characters, which is what the redaction test needs.
SCANNED = "Misc/First Farmers 2026 01-document.pdf"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A synthetic corpus root: one digital, one duplicate, one broken, one non-PDF."""
    (tmp_path / "BankX").mkdir()
    (tmp_path / "BankY").mkdir()
    digital = (statements_dir() / DIGITAL).read_bytes()
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
    target.write_bytes((statements_dir() / manifest[0]).read_bytes())

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
    on_disk.write_bytes((statements_dir() / wanted).read_bytes())

    inventory = enumerate_root(tree)
    # The MANIFEST spelling is the document's identity from here on; the
    # on-disk spelling is an observation, recorded and not propagated.
    assert inventory.pinned == (wanted,)
    # Neither spelling leaks into the discovery set: the partition subtracts
    # what rglob produced, while the identity reported is the manifest's.
    assert "scotiabank/scotiabank -2.pdf" not in inventory.discovery
    assert wanted not in inventory.discovery
    assert inventory.case_mismatches == ((wanted, "scotiabank/scotiabank -2.pdf"),)
    assert wanted not in inventory.missing_pinned


def test_a_case_folded_pinned_document_is_unique_not_a_duplicate_of_itself(tree: Path):
    """The main-checkout dry-run failure, as a regression test.

    On a case-insensitive filesystem the archive created `Scotiabank/` before
    git checked out the tracked `ScotiaBank/`, and Windows kept the first
    spelling. The runner derived the document's identity from the DISK
    spelling while `DedupIndex.pinned` is keyed by the MANIFEST spelling, so
    the two string-compared unequal and a pinned statement reported as a
    `pinned_corpus_duplicate` **of itself** — `dedup {'unique': 108,
    'pinned_corpus_duplicate': 1}`. Every clean worktree passed, because git
    casing and no archive means disk == manifest, which is why it only ever
    reproduced in the main checkout.

    Fixed by canonicalising identity at the one boundary that decides it
    (`enumerate_root`), not by making `classify` case-insensitive: on Linux
    two case-different paths are genuinely different files, and that must stay
    a reported deviation rather than become a silent match. The complement
    (found on Linux, where the manifest spelling does not open the case-folded
    file at all): identity is the manifest spelling, but the READ goes through
    `Inventory.disk_spelling`, exactly as the CLI drives the runner.
    """
    wanted = "ScotiaBank/Scotiabank -2.pdf"
    on_disk = tree / "scotiabank" / "scotiabank -2.pdf"
    on_disk.parent.mkdir(parents=True, exist_ok=True)
    on_disk.write_bytes((statements_dir() / wanted).read_bytes())

    inventory = enumerate_root(tree)
    assert inventory.pinned == (wanted,)
    assert inventory.case_mismatches == ((wanted, "scotiabank/scotiabank -2.pdf"),)
    assert inventory.disk_spelling(wanted) == "scotiabank/scotiabank -2.pdf"

    runner = _runner(tree, dedup=DedupIndex.with_pinned_corpus())
    row = runner.process(
        wanted, inventory.folder_label(wanted),
        disk_relative_path=inventory.disk_spelling(wanted),
    )

    assert row.dedup_status == "unique"
    assert row.duplicate_of is None
    assert row.relative_path == wanted
    assert row.folder_label == "ScotiaBank"
    assert row.content_sha256 == pinned_hashes()[wanted]


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
        runner_module, "analyze_document",
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
    scanned.write_bytes((statements_dir() / SCANNED).read_bytes())

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


# --- P20-ROUTER: evidence quality / failure class / escalation budget ------


def test_a_claimed_digital_document_carries_no_failure_class(tree: Path):
    """P20-ROUTER item 2e (post BLOCK-1). A native-text document that claims
    and analyses without an integrity flag is `validated`, so `failure_class`
    folds to `""` (`ocr.escalation.NO_FAILURE`). `evidence_quality` is
    `"none"` for a NATIVE read — the gate assesses only OCR-sourced evidence
    (`local_tesseract`/`visual`); a native document is usable by
    construction and is never handed to `ExtractionQualityGate` at all."""
    row = _runner(tree).process("BankX/statement.pdf", "BankX")
    assert row.parser_id == "chase"
    assert row.source_path == "native"
    assert row.evidence_quality == "none"
    assert row.failure_class in ("", "C")  # "" if validated, "C" if a check withholds it
    if row.outcome_class == "validated":
        assert row.failure_class == ""


def test_profile_only_and_invalid_pdf_rows_carry_no_evidence_verdict(tree: Path):
    """Nothing was ever read for these rows, so there is nothing to assess —
    `evidence_quality` stays at its `"none"` default, never a guess."""
    profile_only = _runner(tree, MODE_PROFILE_ONLY).process("BankX/statement.pdf", "BankX")
    assert profile_only.evidence_quality == "none"
    assert profile_only.failure_class == ""

    invalid = _runner(tree).process("BankY/broken.pdf", "BankY")
    assert invalid.evidence_quality == "none"
    assert invalid.failure_class == ""


# `test_estimate_class_a_population_*` (2) pinned the retired Paddle mode's
# pre-run escalation ceiling; they left with `estimate_class_a_population`,
# its only caller's subject (model-code removal, slice S5).


def test_the_dry_run_reads_scanned_statements_from_committed_artifacts(tmp_path: Path):
    """That is what lets the dry run cover all 109 with zero OCR."""
    row = _runner(statements_dir(), MODE_DRY_RUN).process(SCANNED, "Misc")
    assert row.source_path == "committed_artifact"
    assert row.parser_id == "first_farmers"
    assert row.outcome_class in {"validated", "review"}


# --- the offline guarantee --------------------------------------------------


#: A discovery read of the synthetic tree's digital statement, run in a fresh
#: process by N2's helper (`tests/test_no_model_clients.py`).
_DISCOVERY_READ = """
from pathlib import Path
from discovery.inventory import DedupIndex
from discovery.runner import DiscoveryRunner, MODE_DIGITAL
row = DiscoveryRunner(Path({root!r}), mode=MODE_DIGITAL, run_id="t", sink=None, cache=None,
                      dedup=DedupIndex()).process("BankX/statement.pdf", "BankX")
RESULT["parser_id"] = row.parser_id
"""


def test_no_model_extraction_can_happen(tree: Path, tmp_path_factory):
    """There is no extraction model to call: the hosted extractor was deleted
    in slice S3 of the model-code removal (this test used to stub it to fail),
    and the analysis module discovery runs holds no handle to one. Since slice
    S6 the read runs in a fresh process through N2's helper, which also proves
    no model module, no third-party network client and no outbound connection
    (a check of `sys.modules` for the deleted module alone became vacuous)."""
    from tests.test_no_model_clients import assert_no_model_module_after

    result = assert_no_model_module_after(_DISCOVERY_READ.format(root=str(tree)) + """
import importlib.util
import analysis.pipeline as pipeline
RESULT["extractor"] = hasattr(pipeline, "extract_statement")
RESULT["extract_module"] = importlib.util.find_spec("analysis.extract") is not None
""", tmp_path_factory.mktemp("data"))
    assert result == {"parser_id": "chase", "extractor": False, "extract_module": False}


def test_the_visual_ocr_client_module_is_never_even_imported(tree: Path, tmp_path_factory):
    """The visual OCR client (`ocr.ocr_client`) was deleted in slice S2 of the
    model-code removal and the PaddleOCR rung, client and settings in slice S5:
    none can be found at all, and nothing tries to import them (before S5,
    `discovery.runner` imported `ocr.paddle_config` for a refusal vocabulary;
    it now holds that vocabulary as a literal). Since slice S6 the check is
    N2's helper: no model package and no removed model module is loaded after
    the read (the deleted modules' names alone could no longer be loaded)."""
    from tests.test_no_model_clients import assert_no_model_module_after

    result = assert_no_model_module_after(_DISCOVERY_READ.format(root=str(tree)) + """
import importlib.util
gone = ("ocr.ocr_client", "ocr.paddle_rung", "ocr.paddle_client", "ocr.paddle_config", "ocr.endpoint_policy")
RESULT["found"] = sorted(m for m in gone if importlib.util.find_spec(m) is not None)
""", tmp_path_factory.mktemp("data"))
    assert result == {"parser_id": "chase", "found": []}


# --- report -----------------------------------------------------------------


def test_folder_agreement_buckets():
    assert folder_agreement(
        _row(folder_label="Chase", parser_id="chase", statement_bank="Chase")) == "agree"
    assert folder_agreement(
        _row(folder_label="Others", parser_id="altana")) == "unlabelled_folder"
    assert folder_agreement(_row(parser_id=None)) == "no_claim"
    # An abbreviation is UNMATCHED, not a disagreement: naming it "disagree"
    # would manufacture a detection-accuracy problem out of string matching.
    assert folder_agreement(
        _row(folder_label="BofA", parser_id="bank_of_america",
             statement_bank="Bank of America")) == "label_unmatched"


def test_cached_rows_do_not_count_as_unclaimed():
    """Regression: a re-run served from the D-3 analysis cache re-dispatches
    nothing, and counting those as unclaimed reported ~0% coverage and turned
    every folder into an 'unknown-layout cluster'.

    Since §DISCOBS the cache-served row carries a RECONSTRUCTED verdict, so it
    is inside the denominator and marked `live_detect` — the two facts this
    asserts together, because either alone is a different report.
    """
    rows = [
        _row(dispatch_outcome="claimed", parser_id="chase", statement_bank="Chase",
             parser_id_source=PARSER_ID_LIVE_DISPATCH,
             outcome_class="validated", outcome_reason="approved"),
        _row(dispatch_outcome="claimed", parser_id="chase", statement_bank="Chase",
             parser_id_source=PARSER_ID_LIVE_DETECT,
             outcome_class="validated", outcome_reason="approved",
             cache_analysis="hit"),
    ]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["dispatched"] == 2
    assert summary["dispatch_cached"] == 1
    assert summary["dispatch_unavailable"] == 0
    assert summary["deterministic_coverage"] == 1.0
    assert summary["unknown_layout_clusters"] == {}
    assert summary["parsers"] == {"chase": 2}
    assert summary["parser_id_source"] == {
        PARSER_ID_LIVE_DISPATCH: 1, PARSER_ID_LIVE_DETECT: 1,
    }
    rendered = render_report(summary)
    assert "served from cache" in rendered
    assert "routing verdict provenance (parser_id_source)" in rendered


def test_a_row_that_never_reached_analysis_is_not_reported_as_cache_served():
    """`dispatch_cached` used to be `processed - dispatched`, which swept in
    every document the analysis stage never ran for — 17 invalid PDFs on the
    run of record, printed as "served from cache; --no-cache to re-dispatch".
    They were never in the cache and re-dispatching them changes nothing."""
    rows = [
        _row(dispatch_outcome="claimed", parser_id="chase", statement_bank="Chase",
             parser_id_source=PARSER_ID_LIVE_DISPATCH,
             outcome_class="validated", outcome_reason="approved"),
        _row(outcome_class="failed", outcome_reason="invalid_pdf"),
    ]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["dispatch_cached"] == 0
    assert summary["dispatch_unavailable"] == 1
    assert summary["dispatch_inconclusive"] == 0
    rendered = render_report(summary)
    assert "served from cache" not in rendered
    assert "no dispatch record" in rendered
    assert "identity refused" not in rendered


def test_a_refused_identity_is_not_reported_as_never_analysed():
    """The two verdict-less shapes are different findings and only one of them
    is a document we know nothing about. A projection-refused row WAS analysed
    (its payload is in the cache and its outcome is published); what is missing
    is the parser's name. Folding it under "the analysis stage never ran for
    these" would print a false sentence about it. Zero on every run so far —
    a non-zero here is the REGFP card arriving."""
    rows = [
        _row(outcome_class="failed", outcome_reason="invalid_pdf"),
        _row(outcome_class="validated", outcome_reason="approved",
             cache_analysis="hit", statement_bank="Some Bank",
             parser_id_source=PARSER_ID_UNAVAILABLE),
    ]
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")
    assert summary["dispatch_unavailable"] == 1     # the invalid PDF, alone
    assert summary["dispatch_inconclusive"] == 1    # the refused projection
    assert summary["parser_id_source"] == {PARSER_ID_UNAVAILABLE: 1}
    rendered = render_report(summary)
    assert "no dispatch record" in rendered
    assert "identity refused" in rendered
    # processed = dispatched + never-analysed + refused, with no double count.
    assert (summary["dispatched"] + summary["dispatch_unavailable"]
            + summary["dispatch_inconclusive"]) == summary["processed"]


# ---------------------------------------------------------------------------
# §DISCOBS: the cache-hit identity hole
# ---------------------------------------------------------------------------

def test_a_template_claim_is_not_a_label_disagreement():
    """§U D3. The honest-unknown-issuer registrations claim a document
    TEMPLATE and publish `Statement.bank = None`; comparing a template name to
    a folder's bank name is a category error, not a disagreement. Reported in
    its own class, with the pairs printed — and never "fixed" by renaming the
    parser after the folder."""
    template = _row(folder_label="Desjardins", parser_id="releve_facturation",
                    dispatch_outcome="claimed", statement_bank=None,
                    parser_id_source=PARSER_ID_LIVE_DISPATCH,
                    outcome_class="validated", outcome_reason="approved")
    unmatched = _row(folder_label="BofA", parser_id="bank_of_america",
                     dispatch_outcome="claimed", statement_bank="Bank of America",
                     parser_id_source=PARSER_ID_LIVE_DISPATCH,
                     outcome_class="validated", outcome_reason="approved")
    assert folder_agreement(template) == "template_claim"
    assert folder_agreement(unmatched) == "label_unmatched"

    summary = summarize([template, unmatched], mode=MODE_DIGITAL, run_id="r")
    assert summary["folder_agreement"] == {"template_claim": 1, "label_unmatched": 1}
    assert summary["template_claim_pairs"] == [
        {"folder": "Desjardins", "parser": "releve_facturation", "documents": 1}
    ]
    # The template pair is NOT in the unmatched ranking an adjudicator works.
    assert summary["label_unmatched_pairs"] == [
        {"folder": "BofA", "parser": "bank_of_america", "documents": 1}
    ]
    rendered = render_report(summary)
    assert "template claim (no issuer printed): Desjardins -> releve_facturation" in rendered
    assert "unmatched: BofA -> bank_of_america" in rendered


def test_an_unlabelled_folder_still_wins_over_the_template_class():
    """Order is load-bearing: `unlabelled_folder` is a fact about the
    REFERENCE side and already exempts those documents. 35 of the run of
    record's 41 no-issuer claims sit in `Unidentified/` and stay there."""
    row = _row(folder_label="Unidentified", parser_id="balance_by_date",
               dispatch_outcome="claimed", statement_bank=None)
    assert folder_agreement(row) == "unlabelled_folder"


def test_a_template_name_that_matches_a_folder_is_still_not_agreement():
    """A claim that names no issuer cannot AGREE either. Without the ordering,
    a folder whose name happens to contain the template's id would be counted
    as a detection-accuracy datum, which is the same fiction the docstring
    opens with, running the other way."""
    row = _row(folder_label="Balance By Date", parser_id="balance_by_date",
               dispatch_outcome="claimed", statement_bank=None)
    assert folder_agreement(row) == "template_claim"


def test_the_projection_names_the_parser_resolve_would_have_named():
    """The whole cache-hit projection rests on this equivalence: after
    `supersedes` pruning a detection sweep has exactly one survivor iff
    `resolve` claimed, and that survivor is the parser of record. Proven
    against `resolve` itself over a synthetic registry with a supersedes edge,
    so no bank's real code is involved."""
    from analysis import parser_registry as pr
    from telemetry import score_vector, sole_surviving_claimant as _sole_surviving_claimant

    saved = dict(pr._REGISTRY)
    pr.clear_registry()
    try:
        pr.register(pr.Registration(
            id="broad", bank="Broad Platform",
            markers=(pr.required("any", lambda md: "LEDGER" in md),),
            parse=lambda md: None,
        ))
        pr.register(pr.Registration(
            id="narrow", bank="Narrow Bank", band=10,
            supersedes=frozenset({"broad"}),
            markers=(pr.required("narrow", lambda md: "NARROW" in md),),
            parse=lambda md: None,
        ))
        pr.register(pr.Registration(
            id="rival", bank="Rival Bank",
            markers=(pr.required("rival", lambda md: "RIVAL" in md),),
            parse=lambda md: None,
        ))

        # One claimant.
        scores, _ = score_vector("LEDGER")
        assert _sole_surviving_claimant(scores) == ("broad", 0.5)
        assert pr.resolve("LEDGER").candidates == (("broad", 0.5),)

        # Two claimants, one superseded: the survivor is the narrow one, and
        # `resolve` agrees it is not ambiguous.
        scores, _ = score_vector("LEDGER NARROW")
        assert _sole_surviving_claimant(scores) == ("narrow", 0.5)
        assert pr.resolve("LEDGER NARROW").candidates == (("narrow", 0.5),)

        # Two unrelated claimants: ambiguous, so there is nothing to name and
        # the projection must refuse rather than pick the first.
        scores, _ = score_vector("LEDGER RIVAL")
        assert _sole_surviving_claimant(scores) is None
        assert pr.resolve("LEDGER RIVAL").outcome == "ambiguous"

        # Nothing claims.
        scores, _ = score_vector("nothing here")
        assert _sole_surviving_claimant(scores) is None
    finally:
        pr.clear_registry()
        pr._REGISTRY.update(saved)


def test_a_cache_served_row_recovers_its_identity_and_says_how(
    tree: Path, tmp_path: Path
):
    """End to end, through a real D-3 cache in `tmp_path`.

    The first pass dispatches live; the second is served from the analysis
    cache and used to carry NO parser_id, NO score and NO dispatch outcome —
    the hole that shortened COUNTS-P3's denominators. The projected row now
    reproduces the live one field for field, and is MARKED as reconstructed so
    the instrument can still tell the two apart.
    """
    from webapp.artifact_cache import open_cache

    cache = open_cache(tmp_path / "cache")
    runner = DiscoveryRunner(tree, mode=MODE_DIGITAL, run_id="t", sink=None,
                             cache=cache, dedup=DedupIndex())

    live = runner.process("BankX/statement.pdf", "BankX")
    assert live.cache_analysis == "miss"
    assert live.parser_id_source == PARSER_ID_LIVE_DISPATCH
    assert live.parser_id == "chase"

    warm = runner.process("BankX/again.pdf", "BankX")
    assert warm.cache_analysis == "hit"
    assert warm.parser_id_source == PARSER_ID_LIVE_DETECT
    assert warm.parser_id == live.parser_id
    assert warm.parser_score == live.parser_score
    assert warm.dispatch_outcome == live.dispatch_outcome == "claimed"
    assert warm.candidates == live.candidates
    assert warm.outcome_class == live.outcome_class
    assert warm.statement_bank == live.statement_bank
    # Not reconstructed, and not faked either: a detect-stage crash in some
    # other registration is not recoverable from a score vector.
    assert warm.attempted == [] and warm.parser_exceptions == []

    write_rows(tmp_path / "rows.csv", [live, warm])
    written = list(csv.DictReader((tmp_path / "rows.csv").open(encoding="utf-8")))
    assert set(written[0]) == set(ROW_FIELDS)
    assert [r["parser_id_source"] for r in written] == [
        PARSER_ID_LIVE_DISPATCH, PARSER_ID_LIVE_DETECT
    ]


class _ListSink:
    """A telemetry sink that keeps the records, so a test can read them.

    `DiscoveryRunner._emit` swallows its own failures (H3_SCHEMA I4), so a
    record that is never written is invisible unless something counts them.
    Every test using this asserts the count.
    """

    def __init__(self) -> None:
        self.records: list[dict] = []

    def write(self, record: dict) -> None:
        self.records.append(record)


def test_a_cache_served_record_carries_what_the_cache_served_row_carries(
    tree: Path, tmp_path: Path
):
    """#TELCOV: the H-3 record's half of the hole §DISCOBS closed for the row.

    The row projection landed in batch 5 and the record was left behind, so one
    run published two artifacts that disagreed about the same document: the row
    named the parser and `telemetry.jsonl` said `dispatch.source = unavailable`
    with a null id, which is how the coverage rate the record feeds reached
    0.0% on a fully warm archive run.

    Both halves now come from ONE derivation
    (`telemetry.collect.reconstructed_claim`), so this asserts the two agree
    document by document as well as warm-against-cold.
    """
    from telemetry.report import coverage
    from webapp.artifact_cache import open_cache

    sink = _ListSink()
    runner = DiscoveryRunner(tree, mode=MODE_DIGITAL, run_id="t", sink=sink,
                             cache=open_cache(tmp_path / "cache"), dedup=DedupIndex())
    cold_row = runner.process("BankX/statement.pdf", "BankX")
    warm_row = runner.process("BankX/again.pdf", "BankX")
    assert (cold_row.cache_analysis, warm_row.cache_analysis) == ("miss", "hit")
    assert len(sink.records) == 2, "a swallowed emit is not a passing test"
    cold, warm = (record["dispatch"] for record in sink.records)

    assert cold["source"] == "live" and warm["source"] == "cached"
    for field in ("outcome", "parser_id", "score", "candidates"):
        assert warm[field] == cold[field], field
    assert warm["outcome"] == "claimed" and warm["parser_id"] == "chase"
    # Not reconstructed, on either arm, and for two different reasons.
    assert warm["attempted"] == [] and warm["exceptions"] == []

    # The row and the record, on the same warm document.
    assert (warm_row.parser_id, warm_row.parser_score, warm_row.dispatch_outcome) == (
        warm["parser_id"], warm["score"], warm["outcome"]
    )
    assert warm_row.parser_id_source == PARSER_ID_LIVE_DETECT

    # And the number the whole card is about.
    assert coverage(sink.records[:1])["rate"] == coverage(sink.records[1:])["rate"] == 1.0


def test_a_document_the_analysis_never_saw_emits_a_record_that_claims_nothing(
    tree: Path, tmp_path: Path
):
    """`unavailable` still means what it says: no payload, no verdict, no
    reconstruction. The three-state vocabulary is only worth anything if the
    third state is still reachable, and it is reached by two DIFFERENT early
    returns in `process` — an unreadable document and a deferred one — so both
    are exercised here rather than one being named for the other.
    """
    scanned = tree / "BankZ" / "scan.pdf"
    scanned.parent.mkdir()
    scanned.write_bytes((statements_dir() / SCANNED).read_bytes())

    sink = _ListSink()
    runner = DiscoveryRunner(tree, mode=MODE_DIGITAL, run_id="t", sink=sink,
                             cache=None, dedup=DedupIndex())
    invalid = runner.process("BankY/broken.pdf", "BankY")
    deferred = runner.process("BankZ/scan.pdf", "BankZ")

    assert (invalid.outcome_class, invalid.outcome_reason) == ("failed", "invalid_pdf")
    assert (deferred.outcome_class, deferred.outcome_reason) == (
        "deferred", "deferred_scanned"
    )
    assert len(sink.records) == 2, "a swallowed emit is not a passing test"
    for record, expected_class in zip(sink.records, ("failed", "deferred")):
        dispatch = record["dispatch"]
        assert record["outcome"]["class"] == expected_class
        assert dispatch["source"] == "unavailable", expected_class
        assert dispatch["outcome"] is None and dispatch["parser_id"] is None

    # And the deferred one is outside the coverage denominator by class, which
    # is the other half of what `unavailable` is for.
    from telemetry.report import coverage

    assert coverage(sink.records) == {
        "numerator": 0, "denominator": 0, "deferred": 1, "unattributed": 0,
        "verdicts": {}, "rate": None,
    }


def test_a_cached_payload_whose_detection_is_inconclusive_names_no_parser():
    """Fail-closed. The invariant behind the projection (a deterministic-mode
    payload implies exactly one surviving claimant) can only break if a cached
    artifact outlived a registry change without an ANALYSIS_STAGE_VERSION
    bump. That is a finding, not a licence to pick a parser.

    The payload spells a deterministic `model_used` deliberately: #TELCOV
    added that guard for the `parse_mode="auto"` emitters, and a payload
    without one would now be refused for the wrong reason, leaving the
    two-survivor branch this test is named for unexercised.
    """
    from discovery.runner import _project_identity

    row = _row()
    source = _project_identity(
        row, [("a", 0.9), ("b", 0.9)], {"model_used": "somebank-deterministic"}
    )
    assert source == PARSER_ID_UNAVAILABLE
    assert (row.parser_id, row.parser_score, row.dispatch_outcome) == (None, None, None)


def test_an_llm_extracted_payload_projects_no_parser():
    """The guard that makes one reconstruction safe for three emitters.

    Discovery analyses in `parse_mode="deterministic"`, where a payload is a
    registry parser's or the structurer's. `batch.py` and the webapp worker run
    `parse_mode="auto"`, where a payload can come from LLM extraction with no
    parser behind it at all - and the loudest detection on such a document is
    not its parser, because it did not have one.
    """
    from discovery.runner import _project_identity

    row = _row()
    assert _project_identity(
        row, [("chase", 0.9)], {"model_used": "gemini-2.5-flash"}
    ) == PARSER_ID_UNAVAILABLE
    assert row.parser_id is None


def test_a_structurer_payload_projects_no_parser():
    """W3-3c is the one branch that publishes a payload with no parser behind
    it. Opt-in and off, but the projection must not name the parser whose
    detection happened to be the loudest on a document nothing claimed."""
    from analysis.structurer import STRUCTURER_MODEL
    from discovery.runner import _project_identity

    row = _row()
    source = _project_identity(row, [("chase", 0.9)], {"model_used": STRUCTURER_MODEL})
    assert source == PARSER_ID_UNAVAILABLE
    assert row.parser_id is None


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
    """The scanned statement carries an account number; only its last 4 survive."""
    row = _runner(statements_dir(), MODE_DRY_RUN).process(SCANNED, "Misc")
    from analysis.pipeline import analyze_markdown
    from corpus_artifacts import cached_markdown

    markdown = cached_markdown((statements_dir() / SCANNED).read_bytes(),
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

    summary = run(statements_dir(), MODE_DRY_RUN, Path("discovery_reports"), use_cache=False)
    rows = {row.relative_path: row for row in summary.pop("_rows")}

    assert summary["documents"] == 109
    assert summary["processed"] == 109
    assert summary["deferred"] == 0
    assert summary["dispatched"] == 109
    assert summary["deterministic_coverage"] == 108 / 109
    assert summary["dispatch"] == {"claimed": 108, "unclaimed": 1}
    # 100/6/3 until WIRING-2's approved ceremony moved Texas Bank and Regions
    # review -> validated on withdrawn FALSE page flags. Regions is one of the
    # six image-only statements, and it only became executable offline once the
    # committed artifacts carried their intake page lists — this runner reads
    # them on the committed-artifact rung, so its agreement with the gate is
    # evidence that both halves of that artifact are in play.
    #
    # The one `failed` arrived with W3 §REPAIRDOC: with the two
    # amount-rewriting repairs gone from `analysis/columbia_bank.py` its one
    # publishing statement declines, no registration claims the document, and
    # the analysis raises. It is a pinned REFUSAL, named in
    # `corpus_gate.PINNED_REFUSALS` and asserted by name below — a document
    # that failed for any OTHER reason would move this count and go red.
    assert summary["outcome"] == {
        "validated": 102, "review": 3, "withheld": 3, "failed": 1,
    }
    failed = {
        path for path, row in rows.items() if row.outcome_class == "failed"
    }
    assert failed == set(corpus_gate.PINNED_REFUSALS)
    assert all(rows[path].outcome_reason == "parser_declined" for path in failed)
    assert all(rows[path].parser_id is None for path in failed)
    # Nothing can defer on the pinned set: the six image-only statements are
    # served from their committed OCR artifacts.
    assert "deferred" not in summary["outcome"]
    assert summary["deferred"] == 0
    assert summary["dedup"] == {"unique": 109}
    assert summary["ambiguity_clusters"] == {}
    # An unknown-layout cluster counts documents no registration published, by
    # folder. W3 §REPAIRDOC put one there and it is named rather than
    # tolerated: the cluster must be exactly the pinned refusal's folder.
    assert summary["unknown_layout_clusters"] == dict(
        Counter(Path(rel).parent.as_posix() for rel in corpus_gate.PINNED_REFUSALS)
    )
    # ...and the DECLINED cluster names the registration that detected it and
    # then refused, which is the fact the refusal actually is.
    assert summary["declined_clusters"] == {"columbia_bank": 1}

    withheld = {
        Path(path).name for path, row in rows.items() if row.outcome_class == "withheld"
    }
    assert withheld == corpus_gate.WITHHELD_STATEMENTS

    expectations = json.loads(
        (ROOT / "tests" / "data" / "parser_expectations.json").read_text(encoding="utf-8")
    )["documents"]
    assert len(expectations) == 109
    for entry in expectations:
        # `parser_expectations.json` records what the pre-R-3 or-chain did and
        # is not rewritten by a later doctrine ceremony; for a pinned refusal
        # the runner names no parser at all, which the block above pins.
        expected = None if entry["path"] in corpus_gate.PINNED_REFUSALS else (
            entry["variant_id"] or entry["parser_id"]
        )
        assert rows[entry["path"]].parser_id == expected, entry["path"]
        assert rows[entry["path"]].content_sha256 == entry["sha256"]

    # `use_cache=False`, so every one of the 109 verdicts is OBSERVED. Nothing
    # in this gate may be a reconstruction (§DISCOBS).
    assert summary["parser_id_source"] == {PARSER_ID_LIVE_DISPATCH: 109}
    assert summary["dispatch_cached"] == 0
    assert summary["dispatch_unavailable"] == 0
    assert summary["dispatch_inconclusive"] == 0


@pytest.mark.corpus
def test_a_warm_rerun_reproduces_the_cold_run_with_identity_recovered(tmp_path: Path):
    """§DISCOBS, the acceptance proof, at the scale this repository can run.

    The same 109 documents twice through a private D-3 cache: cold, then warm.
    The warm pass re-dispatches nothing — that is what the cache is for — and
    before this cell every one of its rows lost its parser, its score and its
    dispatch outcome, so the coverage metric read 0/0 and every parser-keyed
    rollup was empty. The warm pass must now reproduce the cold one EXACTLY
    (the outcome split, the coverage rate, the parser ranking, the
    folder-agreement rollup and the per-document identity), differing in
    exactly one place: the provenance mark that says the verdicts were
    reconstructed rather than observed.

    EXTENDED AT #TELCOV to the telemetry layer, which was the other half of
    the same hole and was left behind by batch 5: each pass now writes its
    H-3 records too, and the record arm is asserted the same way — warm
    against cold, and then against the row the same document produced. Two
    passes over 109 documents is the expensive part of this test and it was
    already being paid; the records are free.
    """
    from telemetry.report import coverage
    from webapp.artifact_cache import open_cache

    # A PRIVATE cache in tmp_path: the shared `webapp_data` store is read-only
    # to a proof, and `discovery.cli.run(use_cache=True)` would open it.
    inventory = enumerate_root(statements_dir())
    paths = list(inventory.pinned)
    assert len(paths) == 109

    def pass_(cache):
        sink = _ListSink()
        runner = DiscoveryRunner(statements_dir(), mode=MODE_DRY_RUN, run_id="warm-proof",
                                 sink=sink, cache=cache,
                                 dedup=DedupIndex.with_pinned_corpus())
        rows = [
            runner.process(path, inventory.folder_label(path),
                           disk_relative_path=inventory.disk_spelling(path))
            for path in paths
        ]
        assert len(sink.records) == 109, "an emit that failed is not a proof"
        return rows, summarize(rows, mode=MODE_DRY_RUN, run_id="warm-proof"), sink.records

    cache = open_cache(tmp_path / "cache")
    cold_rows, cold, cold_records = pass_(cache)
    warm_rows, warm, warm_records = pass_(cache)

    assert {r.cache_analysis for r in cold_rows} == {"miss"}
    # W3 §REPAIRDOC: a pinned refusal is a MISS on both passes and keeps its
    # live dispatch, because `webapp/artifact_cache.py` never caches a failure
    # — there is no payload to serve, so there is nothing to reconstruct FROM.
    # That is the correct behaviour and it is pinned by name rather than
    # relaxed away: everything else hits, and the refusal's warm row is
    # identical to its cold one all the same (asserted below with the rest).
    refusals = set(corpus_gate.PINNED_REFUSALS)
    assert {r.relative_path for r in warm_rows if r.cache_analysis == "miss"} == refusals
    assert {r.cache_analysis for r in warm_rows if r.relative_path not in refusals} == {"hit"}
    assert cold["parser_id_source"] == {PARSER_ID_LIVE_DISPATCH: 109}
    assert warm["parser_id_source"] == {
        PARSER_ID_LIVE_DETECT: 109 - len(refusals),
        PARSER_ID_LIVE_DISPATCH: len(refusals),
    }

    for key in ("outcome", "reasons", "dispatch", "dispatched",
                "deterministic_coverage", "parsers", "folder_agreement",
                "label_unmatched_pairs", "template_claim_pairs",
                "unknown_layout_clusters", "declined_clusters",
                "dispatch_unavailable", "dispatch_inconclusive"):
        assert warm[key] == cold[key], key
    # Every one of the 109 was reconstructed; none was refused.
    assert warm["dispatch_inconclusive"] == 0
    assert warm["outcome"] == {
        "validated": 102, "review": 3, "withheld": 3, "failed": 1,
    }
    # 102/4/3, not 100/6/3: the batch-5 train composed this test (written on
    # wave5-discobs) with WIRING-2's executed Option-A ceremony, which moved
    # Texas Bank and Regions review->validated. The canonical split is the
    # gate's PINNED_OUTCOMES; the warm==cold reproduction above is the
    # property this test owns.
    assert warm["deterministic_coverage"] == 108 / 109

    cold_by_path = {r.relative_path: r for r in cold_rows}
    for row in warm_rows:
        reference = cold_by_path[row.relative_path]
        assert row.parser_id == reference.parser_id, row.relative_path
        assert row.parser_score == reference.parser_score, row.relative_path
        assert row.dispatch_outcome == reference.dispatch_outcome
        assert row.candidates == reference.candidates
        assert row.statement_bank == reference.statement_bank
        assert row.outcome_class == reference.outcome_class
        assert row.outcome_reason == reference.outcome_reason

    # --- the telemetry arm (#TELCOV) ---------------------------------------
    # The record's provenance mark is `dispatch.source`, and it is the one
    # field that is SUPPOSED to differ between the two passes.
    assert {r["dispatch"]["source"] for r in cold_records} == {"live"}
    # ...for every record the cache could serve. A pinned refusal's record is
    # `live` on BOTH passes for the same reason its row is a miss on both: the
    # analysis raised, nothing was cached, and there is no stored verdict to
    # mark as reconstructed. Pinned by shape, not excused: the warm records
    # that are still `live` must be exactly as many as there are refusals, and
    # every one of them must be an unclaimed dispatch.
    warm_live = [r for r in warm_records if r["dispatch"]["source"] == "live"]
    assert len(warm_live) == len(refusals)
    assert {r["dispatch"]["outcome"] for r in warm_live} == {"unclaimed"}
    assert {
        r["dispatch"]["source"] for r in warm_records
        if r["dispatch"]["outcome"] == "claimed"
    } == {"cached"}

    cold_by_sha = {r["document"]["content_sha256"]: r for r in cold_records}
    assert len(cold_by_sha) == 109, "109 distinct documents, so a key per record"
    for record in warm_records:
        reference = cold_by_sha[record["document"]["content_sha256"]]
        for field in ("outcome", "parser_id", "score", "candidates",
                      "attempted", "exceptions", "scores", "registration_count"):
            assert record["dispatch"][field] == reference["dispatch"][field], field
        assert record["outcome"] == reference["outcome"]
        assert record["diagnostics"] == reference["diagnostics"]

    # The number the card is about, warm and cold, from the shipped summariser.
    assert coverage(cold_records) == coverage(warm_records)
    assert coverage(warm_records) == {
        "numerator": 108, "denominator": 109, "deferred": 0,
        "unattributed": 0, "verdicts": {"claimed": 108, "unclaimed": 1},
        "rate": 108 / 109,
    }
    # And the two instruments over one run: the telemetry rollup and the
    # discovery rollup are independent code paths reading independent
    # artifacts, and they must not print different coverage for the same
    # documents. Before #TELCOV the warm pass printed 0.0% here and 100% there.
    for rollup, records in ((cold, cold_records), (warm, warm_records)):
        assert coverage(records)["rate"] == rollup["deterministic_coverage"]
        assert coverage(records)["denominator"] == rollup["dispatched"]
        assert coverage(records)["numerator"] == rollup["dispatch"]["claimed"]

    # The `--enrich` bridge is no longer load-bearing for a run emitted now:
    # the records carry their own parser identity, warm or cold. A refusal
    # names no parser because none published it — the registration that
    # detected it and declined is in `attempted`, not in `parser_id`.
    named = [r for r in warm_records if r["dispatch"]["outcome"] == "claimed"]
    assert len(named) == 109 - len(refusals)
    assert all(r["dispatch"]["parser_id"] for r in named)
    unnamed = [r for r in warm_records if r["dispatch"]["outcome"] != "claimed"]
    assert [r["dispatch"]["attempted"] for r in unnamed] == [["columbia_bank"]]


# ---------------------------------------------------------------------------
# Parser crashes (W3-1): a defect of ours, ranked as one
# ---------------------------------------------------------------------------

def test_a_crashed_dispatch_is_reported_as_a_parser_exception():
    """Before W3-1 a crash produced no Dispatch at all, so the run recorded the
    bare class of whatever escaped and the row read "exception". Now the
    dispatch says which parser broke and the reason names the class."""
    from analysis.parser_registry import Dispatch, ParserFailure
    from discovery.runner import _failure_reason

    crashed = Dispatch("parser_exception",
                       exceptions=(ParserFailure("us_bank", "parse", "AttributeError"),))
    assert _failure_reason("RuntimeError", crashed) == "parser_exception"
    assert _failure_reason("RuntimeError", Dispatch("unclaimed")) == "no_parser_matched"
    assert _failure_reason(None, crashed) is None


def test_a_crash_is_not_ranked_as_an_unknown_layout_cluster():
    """The two rankings answer different questions — "which bank needs a
    parser" and "which parser needs a fix". A crash in the first one hides a
    bug at the bottom of a list of banks."""
    crashed = DocumentRow(
        relative_path="BankX/a.pdf", folder_label="BankX", content_sha256="A" * 64,
        byte_size=1, dispatch_outcome="parser_exception", outcome_class="failed",
        outcome_reason="parser_exception", error_type="RuntimeError",
        parser_exceptions=["us_bank:parse:AttributeError"],
    )
    unknown = DocumentRow(
        relative_path="BankY/b.pdf", folder_label="BankY", content_sha256="B" * 64,
        byte_size=1, dispatch_outcome="unclaimed", outcome_class="failed",
        outcome_reason="no_parser_matched",
    )
    summary = summarize([crashed, unknown], mode=MODE_DIGITAL, run_id="t")

    assert summary["crash_clusters"] == {"us_bank:parse:AttributeError": 1}
    assert summary["unknown_layout_clusters"] == {"BankY": 1}
    assert summary["dispatch"]["parser_exception"] == 1
    assert "parser_exception" in render_report(summary)


# ---------------------------------------------------------------------------
# Dispatch.attempted: "claimed it, then declined it" is its own finding
# ---------------------------------------------------------------------------

@pytest.fixture
def declining_registry():
    """A registry of exactly one parser that claims everything and parses
    nothing — the `attempted` shape, with no bank's real code involved."""
    from analysis import parser_registry as pr

    saved = dict(pr._REGISTRY)
    pr.clear_registry()
    pr.register(pr.Registration(
        id="always_declines",
        bank="Always Declines",
        markers=(pr.required("any", lambda _markdown: True),),
        parse=lambda _markdown: None,
    ))
    try:
        yield
    finally:
        pr.clear_registry()
        pr._REGISTRY.update(saved)


def test_a_parser_that_claimed_and_declined_is_not_an_unseen_layout():
    """The split the report ranks by. `no_parser_matched` had been carrying two
    findings that need different work — a bank we have never parsed, and a
    parser that recognises the document and gives up on it."""
    from analysis.parser_registry import Dispatch, ParserFailure
    from discovery.runner import _failure_reason

    tried = Dispatch("unclaimed", attempted=("chase",))
    assert _failure_reason("RuntimeError", tried) == "parser_declined"
    # An EMPTY attempted is the only thing that still earns the old name.
    assert _failure_reason("RuntimeError", Dispatch("unclaimed")) == "no_parser_matched"
    # A crash still outranks both: "detected, then broke" is a defect of ours
    # and must not be filed as "detected, then declined".
    crashed = Dispatch(
        "parser_exception", attempted=("chase",),
        exceptions=(ParserFailure("us_bank", "parse", "AttributeError"),),
    )
    assert _failure_reason("RuntimeError", crashed) == "parser_exception"
    # And no dispatch outcome invents a failure where the document succeeded.
    assert _failure_reason(None, tried) is None


def test_the_row_carries_the_parsers_that_declined(
    tree: Path, tmp_path: Path, declining_registry
):
    """End to end: the runner projects `Dispatch.attempted` onto the row and the
    CSV grows a column for it, so the queue is readable without re-running."""
    row = _runner(tree).process("BankX/statement.pdf", "BankX")

    assert row.dispatch_outcome == "unclaimed"
    assert row.parser_id is None
    assert row.attempted == ["always_declines"]
    assert (row.outcome_class, row.outcome_reason) == ("failed", "parser_declined")

    write_rows(tmp_path / "rows.csv", [row])
    written = list(csv.DictReader((tmp_path / "rows.csv").open(encoding="utf-8")))
    assert set(written[0]) == set(ROW_FIELDS)
    assert written[0]["attempted"] == "always_declines"


def test_a_document_nothing_claimed_still_reports_no_parser_matched(tree: Path):
    """The other branch, through the same live path: with the real registry
    nothing claims a broken PDF's empty read, and the row says so."""
    row = _runner(tree).process("BankY/broken.pdf", "BankY")
    assert row.attempted == []
    assert row.outcome_reason != "parser_declined"


def test_declined_documents_rank_by_the_parser_that_declined():
    """The bucket answers "which parser needs widening", which is a different
    question from the folder-keyed "which bank needs a parser" beside it."""
    rows = [
        _row(relative_path=f"Chase/{i}.pdf", folder_label="Chase",
             dispatch_outcome="unclaimed", attempted=["chase"],
             outcome_class="failed", outcome_reason="parser_declined")
        for i in range(2)
    ]
    rows.append(_row(folder_label="Wells", dispatch_outcome="unclaimed",
                     attempted=["wells", "chase"], outcome_class="failed",
                     outcome_reason="parser_declined"))
    # A document nothing claimed contributes nothing to this ranking.
    rows.append(_row(folder_label="Unknown", dispatch_outcome="unclaimed",
                     outcome_class="failed", outcome_reason="no_parser_matched"))
    summary = summarize(rows, mode=MODE_DIGITAL, run_id="r")

    assert summary["declined_clusters"] == {"chase": 3, "wells": 1}
    assert list(summary["declined_clusters"]) == ["chase", "wells"]   # ranked
    assert summary["reasons"] == {"parser_declined": 3, "no_parser_matched": 1}
    assert "claimed then declined" in render_report(summary)
    # The rename does not move anything out of the coverage arithmetic: these
    # are all still unclaimed, and all still failed.
    assert summary["dispatch"] == {"unclaimed": 4}
    assert summary["outcome"] == {"failed": 4}


def test_the_rename_is_not_movement_between_two_runs(tmp_path: Path):
    """W3-4 compatibility (requirement 4), proven rather than asserted.

    `discovery.compare` keys movement on `outcome_class` and on the W3-2
    `diagnostics.primary_class` — it reads `outcome.reason` into `Document` and
    never ranks by it. So the same document reported `no_parser_matched` by a
    baseline run and `parser_declined` by a candidate run is UNCHANGED, and a
    merge gate cannot read this reporting split as a regression.

    The record builders are imported from the W3-4 suite on purpose: a private
    copy of the telemetry record shape here could drift, and a compatibility
    proof written against a stale shape proves nothing.
    """
    from discovery.compare import compare
    from discovery.evidence import load_run

    from tests.test_adjudication import _record, _write_run

    sha = "D" * 64
    unmatched = _record(sha, run_id="base", parser_id=None,
                        dispatch_outcome="unclaimed", outcome_class="failed",
                        outcome_reason="no_parser_matched")
    declined = _record(sha, run_id="cand", parser_id=None,
                       dispatch_outcome="unclaimed", outcome_class="failed",
                       outcome_reason="parser_declined")
    baseline = load_run(_write_run(tmp_path / "base", [unmatched]))
    candidate = load_run(_write_run(tmp_path / "cand", [declined]))

    # The reason DID change, and it is visible in the evidence...
    assert baseline.documents[sha].outcome_reason == "no_parser_matched"
    assert candidate.documents[sha].outcome_reason == "parser_declined"

    # ...and it is still not movement.
    report = compare(baseline, candidate)
    assert report["identical"] is True
    assert report["movement"] == {"unchanged": 1}
    assert report["transitions"] == {}
    assert report["failure_class_movement"] == {}
    assert report["regressed_sample"] == []


# ---------------------------------------------------------------------------
# P21-ROUTING closure (MAJOR-1, MINOR-2): the two literal mirrors this module
# carries never drift from the values they mirror.
# ---------------------------------------------------------------------------


def test_cache_finding_literal_mirror_matches_the_artifact_cache_constant():
    from discovery.runner import CACHE_FINDING_EVIDENCE_DRIFT
    from webapp.artifact_cache import CACHE_FINDING_EVIDENCE_DRIFT as ARTIFACT_CACHE_FINDING

    assert CACHE_FINDING_EVIDENCE_DRIFT == ARTIFACT_CACHE_FINDING
