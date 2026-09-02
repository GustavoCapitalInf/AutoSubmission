"""P20-REPLAY-SHAPE (Phase 2.0 addendum cell E) — the cohort replay replays
through the runner's EXACT document call.

Diagnosed at `PHASE2_P20ARTIFACTS_REVIEW.md` MAJOR-3, corroborated by
`PHASE2_P20SURFACES_REVIEW.md` MAJOR-1: `tools/cohort_replay.py::replay_one`
used to call `report_to_dict(analyze_markdown(...))` — the SINGLE-ACCOUNT
projection — while the runner of record (`discovery/runner.py::_analyse` +
`process()`) calls `document_report_to_dict(analyze_document(...))` and the
cached analysis artifacts hold THAT shape. On a document that publishes a
`document` block (23 of 2,656 on the train9 cold cache, 2 of them genuinely
multi-account) the mismatch made `--expect-identical` structurally unable to
reproduce the baseline, and made the replay unable to observe anything at the
omission-publish seam (`analysis/sibling_omission.py`'s Q3 native-only gate) —
`analyze_markdown` never opens the omission collector `analyze_document` opens.

Four properties proven here, matching the card's four requirements:

1. a synthetic MULTI-ACCOUNT document whose cached analysis payload is
   document-shaped reproduces `identical` through `tools.cohort_replay.main`
   with `--expect-identical` (the DEFAULT, document-shaped, path);
2. the reversion mutant — `--account-shape`, which is exactly
   `report_to_dict(analyze_markdown(...))` restored as the DEFAULT would be —
   is KILLED: the same cache, the same cohort, `--account-shape` in place of
   the default, exits 3 (drift) rather than 0;
3. the Q3 gate (P20-SURFACES) is OBSERVABLE through `replay_one` at its new
   default: a `local-tesseract-ocr` header on a Q3-class fixture yields the
   fail-closed outcome (`failed` / `q3_provenance_refused`) through the
   document-shaped replay, and is NOT observed at all through `--account-shape`
   — the exact MAJOR-1 asymmetry, reproduced directly against `replay_one`;
4. the `replayed < population` refusal (the P20-ARTIFACTS re-review's
   MINOR-8): `--expect-identical` now exits 3 whenever fewer shas replayed
   than the named cohort's population, unless `--allow-unresolved` is passed.

Read-only over a synthetic, throwaway cache built in `tmp_path`; no archive
data, no OCR, no model, $0. Every fixture here is invented furniture from
`tests/l1s4_pages.py`, nothing copied from any real document.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ocr.document import StatementMarkdown
from ocr.inspect import content_sha256
from tests.l1s4_pages import document as l1s4_document, idle_account, posting_account
from webapp.artifact_cache import (
    ArtifactCache,
    analysis_settings_key,
    cached_analysis,
    ocr_settings_key,
)
from webapp.storage import Storage

REPO_ROOT = Path(__file__).resolve().parents[1]

OFFLINE_KEY = ocr_settings_key(force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False)
ANALYSIS_KEY = analysis_settings_key(parse_mode="deterministic")

ROWS_HEADER = "content_sha256,folder_label,outcome_class,outcome_reason,parser_id,source_path,visual_rung"


# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------


def _multi_account_markdown() -> tuple[str, list[str]]:
    """Two DISTINCT posting accounts (different labels, suffixes, opening
    balances) — a genuine multi-account document: neither is idle, so no
    omission is raised, and `document_report_to_dict` publishes the
    `{"document": ..., "accounts": [...]}` shape with NO top-level `statement`
    (verified empirically: 2 accounts, `set(payload) == {"document",
    "accounts"}`, `classify_document(payload) == ("validated", "approved")`)."""
    full_text = l1s4_document([
        posting_account(),
        posting_account(label="SAMPLE SAVINGS", suffix="72", opening=500.00),
    ])
    body = full_text.split("\n\n", 1)[1]
    doc = StatementMarkdown(source_file="synthetic.pdf", model="native-pdf-text", pages=[body])
    return doc.to_markdown(), doc.pages


def _write_run_dir(run_dir: Path, *, rows: list[str], mode: str = "digital") -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("provenance.json").write_text(
        json.dumps({
            "tree": {},
            "run_of_record": {
                "partitions": {
                    "offline_ocr_key": OFFLINE_KEY,
                    "analysis_key": ANALYSIS_KEY,
                    "mode": mode,
                }
            },
        }),
        encoding="utf-8",
    )
    run_dir.joinpath("rows.csv").write_text("\n".join([ROWS_HEADER, *rows]) + "\n", encoding="utf-8")


def _run_cohort_replay(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tools.cohort_replay", *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )


def _seed_multi_account_cache(tmp_path: Path) -> tuple[Path, Path, str, dict]:
    """One cached document -> the genuine multi-account payload, at
    `OFFLINE_KEY` / `ANALYSIS_KEY`, with a `rows.csv` row naming it
    `validated`/`approved` exactly as the runner's own fold would have
    recorded it (`classify_document` on this payload, verified below)."""
    from analysis.pipeline import analyze_document
    from analysis.serialization import document_report_to_dict
    from telemetry.record import classify_document

    markdown, pages = _multi_account_markdown()
    payload = document_report_to_dict(analyze_document(
        markdown, parse_mode="deterministic", sheets=pages))
    assert set(payload) == {"document", "accounts"}, "fixture bug: expected a genuine multi-account payload"
    assert classify_document(payload) == ("validated", "approved")

    pdf_bytes = b"%PDF-1.7\nP20-REPLAY-SHAPE synthetic multi-account fixture"
    sha = content_sha256(pdf_bytes)

    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run"
    cache = ArtifactCache(Storage(data_dir))
    ocr_doc = StatementMarkdown(source_file="synthetic.pdf", model="native-pdf-text", pages=pages)
    cache.put_ocr(sha, OFFLINE_KEY, ocr_doc)
    result = cached_analysis(
        markdown, compute=lambda: payload, cache=cache,
        parse_mode="deterministic", sheets=pages,
    )
    assert not result.cached, "fixture bug: expected a fresh write, not a cache hit"

    _write_run_dir(run_dir, rows=[f"{sha},Synthetic,validated,approved,member_statement_rollup,native,not_attempted"])
    return data_dir, run_dir, sha, payload


# ---------------------------------------------------------------------------
# 1. the document-shaped baseline reproduces identical through the default path
# ---------------------------------------------------------------------------


def test_a_document_shaped_multi_account_baseline_reproduces_identical(tmp_path):
    data_dir, run_dir, sha, _payload = _seed_multi_account_cache(tmp_path)
    shas_file = tmp_path / "shas.txt"
    shas_file.write_text(sha + "\n", encoding="utf-8")

    result = _run_cohort_replay(
        "--run", str(run_dir), "--data-dir", str(data_dir),
        "--shas", str(shas_file), "--expect-identical",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "BASELINE FIDELITY FAILED" not in result.stdout


# ---------------------------------------------------------------------------
# 2. the reversion mutant (--account-shape standing in for the historical
#    default) is killed: same cache, same cohort, exit 3 instead of 0
# ---------------------------------------------------------------------------


def test_the_account_shape_reversion_mutant_is_killed(tmp_path):
    data_dir, run_dir, sha, _payload = _seed_multi_account_cache(tmp_path)
    shas_file = tmp_path / "shas.txt"
    shas_file.write_text(sha + "\n", encoding="utf-8")

    result = _run_cohort_replay(
        "--run", str(run_dir), "--data-dir", str(data_dir),
        "--shas", str(shas_file), "--expect-identical", "--account-shape",
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "BASELINE FIDELITY FAILED" in result.stdout
    assert sha[:16] in result.stdout


def test_replay_one_default_and_account_shape_disagree_on_the_multi_account_fixture():
    """The same disagreement, isolated at the function level rather than
    through a subprocess and a cache: `replay_one`'s DEFAULT (document-shaped)
    payload carries `document` + `accounts`; `account_shape=True` carries the
    single-account `statement`/`metrics`/... shape with no `accounts` key at
    all — the two are never comparable, which is exactly why the mutant in
    test 2 above cannot reproduce the cached baseline."""
    from tools.cohort_replay import replay_one

    markdown, pages = _multi_account_markdown()

    doc_payload, doc_klass, doc_reason, _ = replay_one(markdown, pages)
    assert doc_payload is not None
    assert set(doc_payload) == {"document", "accounts"}
    assert (doc_klass, doc_reason) == ("validated", "approved")

    acct_payload, acct_klass, acct_reason, _ = replay_one(markdown, pages, account_shape=True)
    assert acct_payload is not None
    assert "accounts" not in acct_payload
    assert "statement" in acct_payload
    assert (acct_klass, acct_reason) == ("validated", "approved")

    assert doc_payload != acct_payload


# ---------------------------------------------------------------------------
# 3. the Q3 gate is observable through the replay at its new default, and NOT
#    observable through --account-shape (the exact MAJOR-1 asymmetry)
# ---------------------------------------------------------------------------


def _q3_ocr_fed_fixture() -> tuple[str, list[str]]:
    """The L1-S4 Q3 fixture (idle share + posting checking), header
    attributed to `local-tesseract-ocr` instead of `native-pdf-text` — the
    same substitution `tests/test_q3_native_only.py::test_local_tesseract_
    ocr_refuses_and_fails_closed` uses, restated here at the replay seam."""
    text = l1s4_document([idle_account(), posting_account()])
    ocr_fed = text.replace("model: native-pdf-text |", "model: local-tesseract-ocr |", 1)
    pages = [ocr_fed.split("\n\n", 1)[1]]
    return ocr_fed, pages


def test_the_q3_gate_is_observable_through_the_default_document_shaped_replay():
    from tools.cohort_replay import replay_one

    markdown, pages = _q3_ocr_fed_fixture()
    payload, klass, reason, _claimed = replay_one(markdown, pages)
    assert payload is None
    assert klass == "failed"
    assert reason == "q3_provenance_refused"


def test_the_q3_gate_is_not_observable_through_the_account_shape_path():
    """MAJOR-1's own finding, reproduced directly against `replay_one`:
    `analyze_markdown` never opens the omission collector `analyze_document`
    opens, so the SAME OCR-attributed Q3 fixture that fails closed above
    quietly validates instead when replayed through `--account-shape`."""
    from tools.cohort_replay import replay_one

    markdown, pages = _q3_ocr_fed_fixture()
    payload, klass, reason, _claimed = replay_one(markdown, pages, account_shape=True)
    assert payload is not None
    assert (klass, reason) == ("validated", "approved")


# ---------------------------------------------------------------------------
# 4. --expect-identical refuses replayed < population unless --allow-unresolved
#    (P20-ARTIFACTS re-review MINOR-8)
# ---------------------------------------------------------------------------


def _seed_correspondence_padding(cache: ArtifactCache, count: int) -> list[str]:
    """`count` trivial, always-resolving OCR artifacts under `OFFLINE_KEY`,
    as `rows.csv` lines. `telemetry.run_of_record.verify_reconstruction`
    samples the FIRST `_CORRESPONDENCE_SAMPLE_SIZE` `native`/`local_tesseract`
    rows of `rows.csv` and refuses the whole run below a 90% resolution rate
    (P20-ARTIFACTS review MINOR-7) — placing exactly this many always-resolving
    rows FIRST fills that sample window completely, so the cohort actually
    under test (placed AFTER these in `rows.csv`) falls entirely outside the
    sample and this test's correspondence result is independent of whatever
    that cohort resolves."""
    rows = []
    for i in range(count):
        sha = content_sha256(f"%PDF-1.7\ncorrespondence padding {i}".encode())
        doc = StatementMarkdown(source_file="pad.pdf", model="native-pdf-text", pages=[f"PAD PAGE {i}"])
        cache.put_ocr(sha, OFFLINE_KEY, doc)
        rows.append(f"{sha},Padding,validated,approved,some_parser,native,not_attempted")
    return rows


def _build_scaffold(tmp_path: Path) -> tuple[Path, Path, str, list[str], str]:
    """A cache + run dir that clears `telemetry.run_of_record.
    verify_reconstruction` (the OCR and analysis keys both exist; the
    correspondence sample is 100% padding, always resolving) with one
    genuinely-resolving multi-account sha on top — so a caller's OWN --shas
    selection can freely name additional never-cached shas without tripping
    `ColdCache`'s CONSTRUCTOR-level refusal (exit 5) instead of `main()`'s
    own population/drift checks (exit 0/3), exactly as the pre-existing
    `tests/test_cohort_replay_selection.py::test_expect_identical_refuses_
    a_vacuous_zero_resolution_on_the_selected_cohort` isolates the same two
    failure modes."""
    from telemetry.run_of_record import _CORRESPONDENCE_SAMPLE_SIZE

    data_dir, run_dir, sha, _payload = _seed_multi_account_cache(tmp_path)
    padding_rows = _seed_correspondence_padding(
        ArtifactCache(Storage(data_dir)), _CORRESPONDENCE_SAMPLE_SIZE)
    target_row = f"{sha},Synthetic,validated,approved,member_statement_rollup,native,not_attempted"
    return data_dir, run_dir, sha, padding_rows, target_row


def test_expect_identical_refuses_a_partial_resolution_without_allow_unresolved(tmp_path):
    """Reproduces the re-review's own example shape: some shas of the named
    cohort resolve (and are identical), the rest never resolve at all
    (`no_text`) — under the OLD semantics this was a silent exit 0 ("replayed
    2 / population 10"); it must now refuse."""
    data_dir, run_dir, sha, padding_rows, target_row = _build_scaffold(tmp_path)

    # A sha the run of record NAMES (source_path=native, so it is eligible
    # for the correspondence sample -- excluded from it only because the
    # padding above already fills the sample window) but for which no OCR
    # artifact was ever cached: it lands in `no_text`, exactly the shape the
    # re-review reproduced.
    absent_sha = content_sha256(b"%PDF-1.7\nnever cached, the sha the cohort names but no artifact answers")
    absent_row = f"{absent_sha},Synthetic,validated,approved,member_statement_rollup,native,not_attempted"
    _write_run_dir(run_dir, rows=[*padding_rows, target_row, absent_row])

    shas_file = tmp_path / "shas.txt"
    shas_file.write_text(f"{sha}\n{absent_sha}\n", encoding="utf-8")

    refused = _run_cohort_replay(
        "--run", str(run_dir), "--data-dir", str(data_dir),
        "--shas", str(shas_file), "--expect-identical",
    )
    assert refused.returncode == 3, refused.stdout + refused.stderr
    assert "replayed 1 of population 2" in refused.stdout
    assert "--allow-unresolved" in refused.stdout

    permitted = _run_cohort_replay(
        "--run", str(run_dir), "--data-dir", str(data_dir),
        "--shas", str(shas_file), "--expect-identical", "--allow-unresolved",
    )
    assert permitted.returncode == 0, permitted.stdout + permitted.stderr
    assert "BASELINE FIDELITY FAILED" not in permitted.stdout


def test_expect_identical_still_refuses_the_exactly_zero_case_with_its_own_message(tmp_path):
    """The pre-existing exactly-zero refusal (`tests/test_cohort_replay_
    selection.py::test_expect_identical_refuses_a_vacuous_zero_resolution_
    on_the_selected_cohort`) keeps its OWN message and fires BEFORE the new
    partial-resolution guard — pinned here so the two checks are proven not
    to collide: the SAME scaffold as the partial-resolution test above, but
    the caller's --shas selection names ONLY the never-cached sha, so 100%
    (not merely a majority) of the SELECTED cohort is unresolved."""
    data_dir, run_dir, _sha, padding_rows, target_row = _build_scaffold(tmp_path)

    never_cached = content_sha256(b"%PDF-1.7\nnever cached at all")
    never_cached_row = f"{never_cached},Synthetic,failed,no_parser_matched,,native,not_attempted"
    _write_run_dir(run_dir, rows=[*padding_rows, target_row, never_cached_row])

    shas_file = tmp_path / "shas.txt"
    shas_file.write_text(never_cached + "\n", encoding="utf-8")

    result = _run_cohort_replay(
        "--run", str(run_dir), "--data-dir", str(data_dir),
        "--shas", str(shas_file), "--expect-identical",
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "0 of 1 shas resolved any cached text" in result.stdout
