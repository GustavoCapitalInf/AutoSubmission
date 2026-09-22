"""telemetry/run_of_record.py — the ONE artifact-selection policy (P20-ARTIFACTS,
Phase 2.0; OQ8/OQ10; F-9/MAJOR-3/MINOR-4).

Proves, independently of either reader that adopts it
(``tools/cohort_replay.py``, ``telemetry/stated_counts.py::_ArtifactJoin``):

* a run's partitions are RECORDED when its ``provenance.json`` says so, and a
  malformed recorded block RAISES rather than silently falling back to
  reconstruction;
* a run predating recording is deterministically RECONSTRUCTED from what it
  DID record, and the reconstruction is VERIFIED against the cache it was
  built to describe — a mismatch is a raised error, never a guess;
* ``ocr_partition_for_row`` reads a row's own provenance, never a preference
  order, and a row naming an absent partition resolves to ``None``;
* ``select_artifact`` returns the one row a triple names and RAISES on a
  corrupt index that somehow holds two.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
from pathlib import Path

import pytest

from telemetry.run_of_record import (
    ORIGIN_RECONSTRUCTED,
    ORIGIN_RECORDED,
    RunOfRecordError,
    RunPartitions,
    analysis_partition,
    ocr_partition_for_row,
    partitions_for_run,
    select_artifact,
    verify_reconstruction,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# fixtures: a minimal cache index and minimal run directories
# ---------------------------------------------------------------------------


def _make_cache_db(tmp_path: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    """``rows``: ``(stage, input_sha256, settings_key, artifact_path)``."""
    db_path = tmp_path / "webapp.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE artifact_cache ("
        " stage TEXT, cache_key TEXT, input_sha256 TEXT, settings_key TEXT,"
        " artifact_path TEXT, byte_size INTEGER, format_version INTEGER,"
        " created_at TEXT, hit_count INTEGER, last_hit_at TEXT,"
        " PRIMARY KEY (stage, cache_key))"
    )
    for index, (stage, input_sha, settings_key, path) in enumerate(rows):
        conn.execute(
            "INSERT INTO artifact_cache (stage, cache_key, input_sha256, settings_key,"
            " artifact_path, byte_size, format_version, hit_count)"
            " VALUES (?, ?, ?, ?, ?, 0, 1, 0)",
            (stage, f"KEY{index}", input_sha, settings_key, path),
        )
    conn.commit()
    return db_path


def _conn(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def _write_recorded_run(
    run_dir: Path, *, offline_key: str, visual_key: str | None, analysis_key: str, mode: str,
    paddle_key: str | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    partitions = {"offline_ocr_key": offline_key, "analysis_key": analysis_key, "mode": mode}
    if visual_key is not None:
        partitions["visual_ocr_key"] = visual_key
    if paddle_key is not None:
        partitions["paddle_ocr_key"] = paddle_key
    (run_dir / "provenance.json").write_text(
        json.dumps(
            {
                "tree": {"OCR_STAGE_VERSION": 5, "ANALYSIS_STAGE_VERSION": 17},
                "run_of_record": {"partitions": partitions},
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# RECORDED partitions
# ---------------------------------------------------------------------------


def test_a_recorded_run_uses_its_own_partitions_verbatim(tmp_path):
    run_dir = tmp_path / "run"
    _write_recorded_run(
        run_dir, offline_key="OFFLINE1", visual_key="VISUAL1", analysis_key="ANALYSIS1", mode="scanned"
    )
    partitions = partitions_for_run(run_dir)
    assert partitions.origin == ORIGIN_RECORDED
    assert partitions.ocr_keys_by_source == {
        "native": "OFFLINE1",
        "local_tesseract": "OFFLINE1",
        "visual": "VISUAL1",
    }
    assert partitions.analysis_key == "ANALYSIS1"
    assert partitions.mode == "scanned"


def test_a_recorded_run_with_a_paddle_key_carries_it(tmp_path):
    run_dir = tmp_path / "run"
    _write_recorded_run(
        run_dir, offline_key="OFFLINE1", visual_key=None, analysis_key="ANALYSIS1",
        mode="scanned-paddle", paddle_key="PADDLE1",
    )
    partitions = partitions_for_run(run_dir)
    assert partitions.ocr_keys_by_source == {
        "native": "OFFLINE1", "local_tesseract": "OFFLINE1", "paddle": "PADDLE1",
    }


def test_a_recorded_run_with_no_paddle_key_has_no_paddle_partition(tmp_path):
    """Every provenance.json recorded before this cell, and every run whose
    Paddle settings did not load at record time — the common case."""
    run_dir = tmp_path / "run"
    _write_recorded_run(
        run_dir, offline_key="OFFLINE1", visual_key="VISUAL1", analysis_key="ANALYSIS1",
        mode="scanned-visual",
    )
    partitions = partitions_for_run(run_dir)
    assert "paddle" not in partitions.ocr_keys_by_source


def test_a_recorded_run_with_no_visual_key_has_no_visual_partition(tmp_path):
    run_dir = tmp_path / "run"
    _write_recorded_run(
        run_dir, offline_key="OFFLINE1", visual_key=None, analysis_key="ANALYSIS1", mode="digital"
    )
    partitions = partitions_for_run(run_dir)
    assert "visual" not in partitions.ocr_keys_by_source


def test_a_recorded_mode_disagreeing_with_summary_json_is_refused(tmp_path):
    """Review MAJOR-1/MAJOR-4 hardening: `--mode` is an operator-supplied
    argument to `tools/train/provenance.py`, not derived from the run
    itself — a typo (`--mode digital` on a `scanned` run) must not silently
    stand as the recorded truth when the run's own `summary.json` disagrees."""
    run_dir = tmp_path / "run"
    _write_recorded_run(
        run_dir, offline_key="OFFLINE1", visual_key=None, analysis_key="ANALYSIS1", mode="digital"
    )
    (run_dir / "summary.json").write_text(json.dumps({"mode": "scanned"}), encoding="utf-8")
    with pytest.raises(RunOfRecordError):
        partitions_for_run(run_dir)


def test_a_recorded_mode_agreeing_with_summary_json_is_accepted(tmp_path):
    run_dir = tmp_path / "run"
    _write_recorded_run(
        run_dir, offline_key="OFFLINE1", visual_key=None, analysis_key="ANALYSIS1", mode="scanned"
    )
    (run_dir / "summary.json").write_text(json.dumps({"mode": "scanned"}), encoding="utf-8")
    partitions = partitions_for_run(run_dir)
    assert partitions.mode == "scanned"


def test_a_recorded_run_with_no_summary_json_is_not_cross_checked(tmp_path):
    """No `summary.json` at all (a synthetic RECORDED run directory, or a
    pre-run provenance call) means nothing to cross-check against — the
    recorded mode stands as given."""
    run_dir = tmp_path / "run"
    _write_recorded_run(
        run_dir, offline_key="OFFLINE1", visual_key=None, analysis_key="ANALYSIS1", mode="digital"
    )
    partitions = partitions_for_run(run_dir)
    assert partitions.mode == "digital"


@pytest.mark.parametrize(
    "partitions_block",
    [
        {},
        {"offline_ocr_key": "OFFLINE1"},  # missing analysis_key / mode
        {"offline_ocr_key": "", "analysis_key": "A", "mode": "scanned"},  # empty string
        {"offline_ocr_key": "OFFLINE1", "analysis_key": "A"},  # missing mode
    ],
)
def test_a_malformed_recorded_block_raises_rather_than_falling_back(tmp_path, partitions_block):
    """A half-written run_of_record.partitions block is a defect to surface,
    never a silent invitation to reconstruct instead."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "provenance.json").write_text(
        json.dumps({"tree": {}, "run_of_record": {"partitions": partitions_block}}),
        encoding="utf-8",
    )
    with pytest.raises(RunOfRecordError):
        partitions_for_run(run_dir)


def test_no_run_of_record_block_means_reconstruction_not_an_error(tmp_path):
    """A run with no `run_of_record` key at all (every batch-8/9 run) is not
    malformed — it predates recording, so reconstruction applies."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "provenance.json").write_text(
        json.dumps(
            {
                "tree": {
                    "OCR_STAGE_VERSION": 4,
                    "ANALYSIS_STAGE_VERSION": 17,
                    "analysis_settings_key_deterministic": "ANALYSISKEY",
                },
                "env": {},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(json.dumps({"mode": "digital"}), encoding="utf-8")
    partitions = partitions_for_run(run_dir)
    assert partitions.origin == ORIGIN_RECONSTRUCTED


# ---------------------------------------------------------------------------
# RECONSTRUCTED partitions — against the real batch-9 run of record
# ---------------------------------------------------------------------------


#: A git worktree carries neither the gitignored recovery cache nor the
#: discovery reports; the checkout it was created from does. Walking upwards
#: is the same idiom `tests/test_rbc_variants.py` and
#: `tests/test_l1s2_protected_carriers.py` use for the OCR store — run from
#: the repo tree or a worktree beneath `.claude/worktrees/`.
def _checkout_ancestor(*relative: str) -> Path | None:
    for base in (ROOT, *ROOT.parents):
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


_BATCH9_RUN_RELATIVE = ("discovery_reports", "TRAIN9-7b25d70", "2026-08-31T185527.271012-0000-91f5179a")
_BATCH9_COLD_CACHE_RELATIVE = (".claude", "recovery", "webapp_data_train9_cold")

BATCH9_RUN = _checkout_ancestor(*_BATCH9_RUN_RELATIVE)
BATCH9_COLD_CACHE = _checkout_ancestor(*_BATCH9_COLD_CACHE_RELATIVE)

_batch9_available = (
    BATCH9_RUN is not None and BATCH9_COLD_CACHE is not None
    and (BATCH9_COLD_CACHE / "webapp.db").is_file()
)


@pytest.mark.skipif(not _batch9_available, reason="batch-9 run of record / cold cache not present on this host")
def test_the_batch9_run_reconstructs_and_verifies_against_its_own_cold_cache():
    """The measured fact this whole cell is built on: the batch-9 cold cache
    holds exactly one OCR key and one analysis key, and the reconstruction
    reproduces BOTH exactly (measured 2026-09-01: offline
    0F25500A3CADF72305575A198086A30A0C348656976954489591A58C9E303BE7,
    analysis 7799FEE4EC8BCAAA2A36A27FDDCCC0BECACD50DE5C908600DA2B88A6237C996E)."""
    conn = _conn(BATCH9_COLD_CACHE / "webapp.db")
    try:
        partitions = partitions_for_run(BATCH9_RUN, conn=conn)
    finally:
        conn.close()
    assert partitions.origin == ORIGIN_RECONSTRUCTED
    assert partitions.mode == "scanned"
    offline_key = partitions.ocr_keys_by_source["native"]
    assert partitions.ocr_keys_by_source["local_tesseract"] == offline_key
    assert offline_key == "0F25500A3CADF72305575A198086A30A0C348656976954489591A58C9E303BE7"
    assert partitions.analysis_key == "7799FEE4EC8BCAAA2A36A27FDDCCC0BECACD50DE5C908600DA2B88A6237C996E"

    conn = _conn(BATCH9_COLD_CACHE / "webapp.db")
    try:
        distinct_ocr = {r[0] for r in conn.execute(
            "SELECT DISTINCT settings_key FROM artifact_cache WHERE stage = 'ocr'")}
        distinct_analysis = {r[0] for r in conn.execute(
            "SELECT DISTINCT settings_key FROM artifact_cache WHERE stage = 'analysis'")}
    finally:
        conn.close()
    assert distinct_ocr == {offline_key}
    assert distinct_analysis == {partitions.analysis_key}


def test_reconstruction_requires_the_tree_block(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "provenance.json").write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(RunOfRecordError):
        partitions_for_run(run_dir)


def test_reconstruction_requires_the_mode_from_summary_json(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "provenance.json").write_text(
        json.dumps(
            {
                "tree": {
                    "OCR_STAGE_VERSION": 4,
                    "ANALYSIS_STAGE_VERSION": 17,
                    "analysis_settings_key_deterministic": "A",
                },
                "env": {},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(RunOfRecordError):
        partitions_for_run(run_dir)


# ---------------------------------------------------------------------------
# verify_reconstruction — the fail-closed mismatch (mutation: "reconstruction
# guesses a key absent from the cache" -> exit 5, never a guess)
# ---------------------------------------------------------------------------


def _write_rows_csv(run_dir, rows: list[dict[str, str]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with (run_dir / "rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_verify_reconstruction_raises_when_the_offline_key_is_absent(tmp_path):
    db_path = _make_cache_db(tmp_path, [
        ("ocr", "SHA1", "REAL-OFFLINE-KEY", "artifacts/ocr/aa/REAL-OFFLINE-KEY.json"),
        ("analysis", "SHA1", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/x.json"),
    ])
    bad = RunPartitions(
        ocr_keys_by_source={"native": "WRONG-KEY", "local_tesseract": "WRONG-KEY"},
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=4, analysis_stage_version=17, mode="digital",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        with pytest.raises(RunOfRecordError):
            verify_reconstruction(bad, conn, tmp_path)
    finally:
        conn.close()


def test_verify_reconstruction_raises_when_the_analysis_key_is_absent(tmp_path):
    db_path = _make_cache_db(tmp_path, [
        ("ocr", "SHA1", "REAL-OFFLINE-KEY", "artifacts/ocr/aa/REAL-OFFLINE-KEY.json"),
        ("analysis", "SHA1", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/x.json"),
    ])
    bad = RunPartitions(
        ocr_keys_by_source={"native": "REAL-OFFLINE-KEY", "local_tesseract": "REAL-OFFLINE-KEY"},
        analysis_key="WRONG-ANALYSIS-KEY",
        ocr_stage_version=4, analysis_stage_version=17, mode="digital",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        with pytest.raises(RunOfRecordError):
            verify_reconstruction(bad, conn, tmp_path)
    finally:
        conn.close()


def test_verify_reconstruction_does_not_require_the_visual_key_to_exist(tmp_path):
    """A run whose visual rung never fired legitimately has zero visual-
    partition rows — that absence must not fail verification."""
    db_path = _make_cache_db(tmp_path, [
        ("ocr", "SHA1", "REAL-OFFLINE-KEY", "artifacts/ocr/aa/REAL-OFFLINE-KEY.json"),
        ("analysis", "SHA1", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/x.json"),
    ])
    partitions = RunPartitions(
        ocr_keys_by_source={
            "native": "REAL-OFFLINE-KEY", "local_tesseract": "REAL-OFFLINE-KEY",
            "visual": "NEVER-WRITTEN-VISUAL-KEY",
        },
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=4, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        verify_reconstruction(partitions, conn, tmp_path)  # must not raise
    finally:
        conn.close()


def test_a_recorded_run_whose_keys_are_absent_from_its_cache_is_refused(tmp_path):
    """Review MAJOR-1(a): retargets the old
    `test_verify_reconstruction_is_a_noop_for_a_recorded_run`, whose premise
    ("a RECORDED run's own keys are, by construction, exactly what it wrote")
    is false the moment an operator's `--mode` disagrees with what the run
    actually consumed, or the recorded key is simply wrong.
    `verify_reconstruction` now checks BOTH origins: a RECORDED run whose
    declared keys the cache does not hold is refused exactly like a bad
    reconstruction, never served as a silent 100% miss."""
    db_path = _make_cache_db(tmp_path, [])  # empty cache: nothing this run could have written
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "ANYTHING", "local_tesseract": "ANYTHING"},
        analysis_key="ANYTHING-ELSE",
        ocr_stage_version=5, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECORDED,
    )
    conn = _conn(db_path)
    try:
        with pytest.raises(RunOfRecordError):
            verify_reconstruction(partitions, conn, tmp_path)
    finally:
        conn.close()


def test_a_recorded_run_whose_keys_exist_verifies_clean(tmp_path):
    """The positive case beside the refusal above: a RECORDED run whose
    declared keys the cache DOES hold verifies without raising."""
    db_path = _make_cache_db(tmp_path, [
        ("ocr", "SHA1", "REAL-OFFLINE-KEY", "artifacts/ocr/aa/x.json"),
        ("analysis", "SHA1", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/y.json"),
    ])
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "REAL-OFFLINE-KEY", "local_tesseract": "REAL-OFFLINE-KEY"},
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=5, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECORDED,
    )
    conn = _conn(db_path)
    try:
        verify_reconstruction(partitions, conn, tmp_path)  # must not raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# verify_reconstruction — CORRESPONDENCE, not just existence (review MAJOR-1(b))
# ---------------------------------------------------------------------------


def test_correspondence_raises_when_the_offline_key_resolves_none_of_the_runs_own_rows(tmp_path):
    """The exact vacuous-green reproduction from the review: the offline key
    exists in the cache's index (for a DIFFERENT input) but resolves NONE of
    THIS run's own native/local_tesseract rows — a wrong-partition record
    that existence-only verification let through with `--expect-identical`
    silently reporting a 100% miss as a pass."""
    db_path = _make_cache_db(tmp_path, [
        # The key exists in the index, but only for a sha this run never read.
        ("ocr", "SOME-OTHER-SHA-NOT-IN-THIS-RUN", "REAL-OFFLINE-KEY", "artifacts/ocr/aa/x.json"),
        ("analysis", "SOME-OTHER-SHA-NOT-IN-THIS-RUN", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/y.json"),
    ])
    _write_rows_csv(tmp_path, [
        {"content_sha256": "ROW-SHA-1", "source_path": "native"},
        {"content_sha256": "ROW-SHA-2", "source_path": "local_tesseract"},
        {"content_sha256": "ROW-SHA-3", "source_path": "none"},  # excluded from the sample
    ])
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "REAL-OFFLINE-KEY", "local_tesseract": "REAL-OFFLINE-KEY"},
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=5, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        with pytest.raises(RunOfRecordError):
            verify_reconstruction(partitions, conn, tmp_path)
    finally:
        conn.close()


def test_correspondence_passes_when_a_supermajority_of_the_sample_resolves(tmp_path):
    """Review MINOR-7: the bound is a SUPERMAJORITY (90%), not "at least
    one" -- nine of ten sampled rows resolve, one is a genuine gap (the
    shape F-9 measured on the real archive: individual documents can
    legitimately miss from a partial cold cache without the key being
    wrong)."""
    cache_rows = [
        ("analysis", "ANY-SHA", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/y.json"),
    ]
    row_specs = []
    for i in range(10):
        sha = f"ROW-SHA-{i}"
        row_specs.append({"content_sha256": sha, "source_path": "native"})
        if i != 9:  # nine of ten cached; the tenth is a genuine, honest gap
            cache_rows.append(("ocr", sha, "REAL-OFFLINE-KEY", f"artifacts/ocr/aa/{sha}.json"))
    db_path = _make_cache_db(tmp_path, cache_rows)
    _write_rows_csv(tmp_path, row_specs)
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "REAL-OFFLINE-KEY", "local_tesseract": "REAL-OFFLINE-KEY"},
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=5, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        verify_reconstruction(partitions, conn, tmp_path)  # 90% resolves: must not raise
    finally:
        conn.close()


def test_correspondence_refuses_a_one_accidental_hit_sample(tmp_path):
    """Review MINOR-7's named scenario: one lucky/accidental resolution in
    a ten-row sample (10%) is NOT the supermajority the bound requires --
    the OLD "at least one resolves" bound would have accepted this; the new
    90% bound must not."""
    cache_rows = [
        ("ocr", "ROW-SHA-0", "REAL-OFFLINE-KEY", "artifacts/ocr/aa/ROW-SHA-0.json"),
        ("analysis", "ANY-SHA", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/y.json"),
    ]
    row_specs = [{"content_sha256": f"ROW-SHA-{i}", "source_path": "native"} for i in range(10)]
    db_path = _make_cache_db(tmp_path, cache_rows)
    _write_rows_csv(tmp_path, row_specs)
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "REAL-OFFLINE-KEY", "local_tesseract": "REAL-OFFLINE-KEY"},
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=5, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        with pytest.raises(RunOfRecordError):
            verify_reconstruction(partitions, conn, tmp_path)
    finally:
        conn.close()


def test_correspondence_cannot_tell_two_full_tranches_apart(tmp_path):
    """Review MINOR-7's honestly-documented residual, PROVEN rather than
    merely asserted: a resolution-RATE check cannot distinguish two
    tranches that each fully cover the sampled documents. Here the WRONG
    tranche holds an artifact for every one of the sample's three
    documents (not just the ones the correct tranche holds) -- 3/3
    resolve, 100% >= 90%, and this check is genuinely unable to tell it
    apart from the correct tranche. This is the documented, out-of-scope
    residual, not a bug: closing it needs an instrument that can tell two
    ARTIFACTS apart (content or provenance), not one that asks "does
    something exist here"."""
    db_path = _make_cache_db(tmp_path, [
        ("ocr", "ROW-SHA-0", "WRONG-TRANCHE-KEY", "artifacts/ocr/aa/wrong0.json"),
        ("ocr", "ROW-SHA-1", "WRONG-TRANCHE-KEY", "artifacts/ocr/aa/wrong1.json"),
        ("ocr", "ROW-SHA-2", "WRONG-TRANCHE-KEY", "artifacts/ocr/aa/wrong2.json"),
        ("ocr", "ROW-SHA-0", "CORRECT-TRANCHE-KEY", "artifacts/ocr/aa/right0.json"),
        ("ocr", "ROW-SHA-1", "CORRECT-TRANCHE-KEY", "artifacts/ocr/aa/right1.json"),
        ("ocr", "ROW-SHA-2", "CORRECT-TRANCHE-KEY", "artifacts/ocr/aa/right2.json"),
        ("analysis", "ANY-SHA", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/y.json"),
    ])
    _write_rows_csv(tmp_path, [
        {"content_sha256": "ROW-SHA-0", "source_path": "native"},
        {"content_sha256": "ROW-SHA-1", "source_path": "native"},
        {"content_sha256": "ROW-SHA-2", "source_path": "native"},
    ])
    # The run's reconstruction is WRONG (declares the wrong tranche as its
    # offline key), but that tranche happens to fully cover the sample too.
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "WRONG-TRANCHE-KEY", "local_tesseract": "WRONG-TRANCHE-KEY"},
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=5, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        verify_reconstruction(partitions, conn, tmp_path)  # cannot be told apart: does not raise
    finally:
        conn.close()


def test_correspondence_is_a_noop_when_the_run_has_no_rows_csv(tmp_path):
    """No rows.csv (a synthetic run directory, or a call site that has not
    written one yet) means nothing to sample against — the existence checks
    are still the operative ones, and correspondence must not manufacture a
    failure out of an absent file."""
    db_path = _make_cache_db(tmp_path, [
        ("ocr", "SHA1", "REAL-OFFLINE-KEY", "artifacts/ocr/aa/x.json"),
        ("analysis", "SHA1", "REAL-ANALYSIS-KEY", "artifacts/analysis/aa/y.json"),
    ])
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "REAL-OFFLINE-KEY", "local_tesseract": "REAL-OFFLINE-KEY"},
        analysis_key="REAL-ANALYSIS-KEY",
        ocr_stage_version=5, analysis_stage_version=17, mode="scanned",
        origin=ORIGIN_RECONSTRUCTED,
    )
    conn = _conn(db_path)
    try:
        verify_reconstruction(partitions, conn, tmp_path)  # no rows.csv: must not raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ocr_partition_for_row — row-driven, never a preference order
# ---------------------------------------------------------------------------


_PARTITIONS = RunPartitions(
    ocr_keys_by_source={"native": "OFFLINE", "local_tesseract": "OFFLINE", "visual": "VISUAL"},
    analysis_key="ANALYSIS",
    ocr_stage_version=5, analysis_stage_version=17, mode="scanned-visual",
    origin=ORIGIN_RECORDED,
)


@pytest.mark.parametrize(
    "row,expected",
    [
        ({"source_path": "native", "visual_rung": "not_attempted"}, "OFFLINE"),
        ({"source_path": "local_tesseract", "visual_rung": "not_attempted"}, "OFFLINE"),
        ({"source_path": "local_tesseract", "visual_rung": "no_upgrade"}, "OFFLINE"),
        ({"source_path": "native", "visual_rung": "recovered"}, "VISUAL"),
        ({"source_path": "local_tesseract", "visual_rung": "upgraded"}, "VISUAL"),
        ({"source_path": "none", "visual_rung": "not_attempted"}, None),
        ({"source_path": "none", "visual_rung": "failed"}, None),
        ({}, None),
    ],
)
def test_ocr_partition_for_row(row, expected):
    assert ocr_partition_for_row(row, _PARTITIONS) == expected


def test_ocr_partition_for_row_resolves_to_none_never_another_partition_when_visual_is_missing():
    """A run with no visual partition (visual never ran) whose row somehow
    claims 'recovered' must resolve to None, never fall back to the offline
    key — that fallback IS the visual-first-or-fallback bug this module
    replaces."""
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "OFFLINE", "local_tesseract": "OFFLINE"},
        analysis_key="ANALYSIS", ocr_stage_version=4, analysis_stage_version=17,
        mode="scanned", origin=ORIGIN_RECONSTRUCTED,
    )
    assert ocr_partition_for_row({"source_path": "native", "visual_rung": "recovered"}, partitions) is None


def test_analysis_partition_returns_the_runs_one_analysis_key():
    assert analysis_partition(_PARTITIONS) == "ANALYSIS"


# ---------------------------------------------------------------------------
# P21-ROUTING: the Paddle partition — optional, row-driven, never confused
# with the visual one (M11: "ocr_partition_for_row returns the visual key
# for a paddle row" is the mutant this section exists to kill).
# ---------------------------------------------------------------------------

_PADDLE_PARTITIONS = RunPartitions(
    ocr_keys_by_source={
        "native": "OFFLINE", "local_tesseract": "OFFLINE",
        "visual": "VISUAL", "paddle": "PADDLE",
    },
    analysis_key="ANALYSIS",
    ocr_stage_version=5, analysis_stage_version=17, mode="scanned-paddle",
    origin=ORIGIN_RECORDED,
)


@pytest.mark.parametrize(
    "row,expected",
    [
        ({"source_path": "local_tesseract", "paddle_rung": "recovered"}, "PADDLE"),
        ({"source_path": "local_tesseract", "paddle_rung": "upgraded"}, "PADDLE"),
        ({"source_path": "local_tesseract", "paddle_rung": "not_attempted"}, "OFFLINE"),
        ({"source_path": "none", "paddle_rung": "refused_customer_data"}, None),
        ({"source_path": "none", "paddle_rung": "failed"}, None),
    ],
)
def test_ocr_partition_for_row_paddle(row, expected):
    assert ocr_partition_for_row(row, _PADDLE_PARTITIONS) == expected


def test_a_paddle_row_never_resolves_to_the_visual_key():
    """M11: even when a run carries BOTH a visual and a paddle key, a row
    whose OWN provenance names paddle must resolve to the PADDLE key, never
    the visual one — and vice versa. A row is never both in practice (D4),
    but the function's own logic must not depend on that being true to
    answer correctly for the one column a row actually set."""
    paddle_row = {"source_path": "local_tesseract", "paddle_rung": "upgraded", "visual_rung": "not_attempted"}
    visual_row = {"source_path": "local_tesseract", "visual_rung": "upgraded", "paddle_rung": "not_attempted"}
    assert ocr_partition_for_row(paddle_row, _PADDLE_PARTITIONS) == "PADDLE"
    assert ocr_partition_for_row(visual_row, _PADDLE_PARTITIONS) == "VISUAL"


def test_ocr_partition_for_row_resolves_to_none_never_another_partition_when_paddle_is_missing():
    """The paddle counterpart of the equivalent visual test above: a run with
    no paddle partition recorded (batch-8/9-era runs; any run predating this
    cell) whose row somehow claims a paddle outcome resolves to None, never
    falls back to the offline or visual key."""
    partitions = RunPartitions(
        ocr_keys_by_source={"native": "OFFLINE", "local_tesseract": "OFFLINE"},
        analysis_key="ANALYSIS", ocr_stage_version=4, analysis_stage_version=17,
        mode="scanned", origin=ORIGIN_RECONSTRUCTED,
    )
    assert ocr_partition_for_row(
        {"source_path": "local_tesseract", "paddle_rung": "upgraded"}, partitions
    ) is None


# ---------------------------------------------------------------------------
# select_artifact — the shared primitive both readers now call
# ---------------------------------------------------------------------------


def test_select_artifact_returns_the_one_matching_row(tmp_path):
    db_path = _make_cache_db(tmp_path, [
        ("ocr", "SHA1", "KEYA", "path/a.json"),
        ("ocr", "SHA1", "KEYB", "path/b.json"),
        ("ocr", "SHA2", "KEYA", "path/c.json"),
    ])
    conn = _conn(db_path)
    try:
        assert select_artifact(conn, "ocr", "SHA1", "KEYA") == "path/a.json"
        assert select_artifact(conn, "ocr", "SHA1", "KEYB") == "path/b.json"
        assert select_artifact(conn, "ocr", "SHA2", "KEYA") == "path/c.json"
    finally:
        conn.close()


def test_select_artifact_returns_none_on_a_miss(tmp_path):
    db_path = _make_cache_db(tmp_path, [("ocr", "SHA1", "KEYA", "path/a.json")])
    conn = _conn(db_path)
    try:
        assert select_artifact(conn, "ocr", "SHA1", "KEYB") is None
        assert select_artifact(conn, "ocr", "SHA-ABSENT", "KEYA") is None
        assert select_artifact(conn, "analysis", "SHA1", "KEYA") is None
    finally:
        conn.close()


def test_select_artifact_returns_none_for_an_empty_settings_key():
    """A row that resolves to no partition at all (`ocr_partition_for_row`
    returning None) must short-circuit to a miss, never query with an empty
    string that could incidentally match something."""
    class _ExplodingConn:
        def execute(self, *a, **k):
            raise AssertionError("must not query the database for an empty settings key")

    assert select_artifact(_ExplodingConn(), "ocr", "SHA1", None) is None
    assert select_artifact(_ExplodingConn(), "ocr", "SHA1", "") is None


def test_select_artifact_raises_on_a_corrupt_index_with_two_rows_for_one_triple(tmp_path):
    """The mutation this proves absent: `select_artifact` (and therefore
    neither reader) may ever tolerate two rows for one (stage, input,
    settings) triple — a corrupt index is a finding, never a choice."""
    db_path = tmp_path / "webapp.db"
    conn = sqlite3.connect(db_path)
    # No primary key here on purpose: this fixture deliberately builds the
    # corrupt state a real index's (stage, cache_key) primary key rules out,
    # to prove the SELECTOR itself refuses to pick one rather than relying
    # solely on a constraint it does not enforce.
    conn.execute(
        "CREATE TABLE artifact_cache (stage TEXT, input_sha256 TEXT, settings_key TEXT, artifact_path TEXT)"
    )
    conn.executemany(
        "INSERT INTO artifact_cache VALUES (?, ?, ?, ?)",
        [
            ("ocr", "SHA1", "KEYA", "path/first.json"),
            ("ocr", "SHA1", "KEYA", "path/second.json"),
        ],
    )
    conn.commit()
    conn.close()
    ro = _conn(db_path)
    try:
        with pytest.raises(RunOfRecordError):
            select_artifact(ro, "ocr", "SHA1", "KEYA")
    finally:
        ro.close()


def test_select_artifact_mutant_rows0_would_have_silently_picked_one():
    """Documents the mutant this test class kills: restoring `rows[0]` on the
    corrupt-index fixture above would return "path/first.json" instead of
    raising. Exercised directly against the mutant function (not the
    production one) so the contrast is explicit."""
    def _mutant_rows0(conn, stage, input_sha256, settings_key):
        rows = conn.execute(
            "SELECT artifact_path FROM artifact_cache WHERE stage = ? AND input_sha256 = ? AND settings_key = ?",
            (stage, input_sha256, settings_key),
        ).fetchall()
        return None if not rows else rows[0][0]

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE artifact_cache (stage TEXT, input_sha256 TEXT, settings_key TEXT, artifact_path TEXT)")
    conn.executemany(
        "INSERT INTO artifact_cache VALUES (?, ?, ?, ?)",
        [("ocr", "SHA1", "KEYA", "path/first.json"), ("ocr", "SHA1", "KEYA", "path/second.json")],
    )
    conn.commit()
    # The mutant silently picks one — SQLite's row order without ORDER BY is
    # unspecified, so which one is not even the point; that it picks ANY one
    # instead of raising is the bug.
    assert _mutant_rows0(conn, "ocr", "SHA1", "KEYA") in ("path/first.json", "path/second.json")
    with pytest.raises(RunOfRecordError):
        select_artifact(conn, "ocr", "SHA1", "KEYA")


# ---------------------------------------------------------------------------
# P21-ROUTING closure (MINOR-5): tools/train/provenance.py's `_TREE_PROBE`
# never writes a raw exception message into the durable run record.
# ---------------------------------------------------------------------------


#: Every Paddle configuration variable the probe's `load_paddle_settings`
#: can read. Hermeticity (P22-IDENTITY closure, Gustavo's direction): the
#: probe runs in a SUBPROCESS whose `ocr.config` import calls `load_dotenv()`
#: (override=False), and `find_dotenv` walks up from the worktree to the
#: checkout's gitignored `.env` — which, on this host, carries the REAL Vast
#: connection variables. Merely DELETING them from `os.environ` therefore
#: lets the probe re-inject them; a variable that is PRESENT (even empty) is
#: left alone by dotenv, and `load_paddle_settings` treats an empty value as
#: unset. So a hermetic test sets every one of these to a value of its own —
#: the empty string to be unconfigured, `local`/`local_free` to be configured
#: — and never depends on what the host's `.env` says. The real configuration
#: stays on this host untouched.
_PADDLE_ENV_NAMES = (
    "PADDLE_PROVIDER", "PADDLE_EXECUTION_CLASS", "PADDLE_VAST_HOST", "PADDLE_VAST_SSH_PORT",
    "PADDLE_VAST_SSH_USER", "PADDLE_REMOTE_OPT_IN", "PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN",
    "PADDLE_WORKER_URL", "PADDLE_WORKER_PORT", "PADDLE_TUNNEL_LOCAL_PORT", "PADDLE_RUNTIME_DIR",
)


def _unconfigure_paddle(monkeypatch) -> None:
    """Every `PADDLE_*` variable present-but-empty: unconfigured, hermetically."""
    for name in list(os.environ):
        if name.startswith("PADDLE_"):
            monkeypatch.setenv(name, "")
    for name in _PADDLE_ENV_NAMES:
        monkeypatch.setenv(name, "")


def _configure_local_paddle(monkeypatch) -> None:
    """A configured, LOCAL, opt-in-free Paddle environment (no host, no
    network): `load_paddle_settings` succeeds, so the probe records a key."""
    _unconfigure_paddle(monkeypatch)
    monkeypatch.setenv("PADDLE_PROVIDER", "local")
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", "local_free")


def test_provenance_paddle_key_note_never_leaks_a_raw_exception_message(tmp_path, monkeypatch):
    """A missing Paddle configuration raises `PaddleConfigError` — recorded
    as `paddle_ocr_key_note` inside `run_of_record.partitions`. Before this
    fix the clause wrote `f"...: {exc}"` verbatim and unbounded for ANY
    exception; now only the class name (plus a closed-vocabulary `.reason`,
    when the exception is a `PaddleRefused`) ever reaches the record.

    Hermetic (P22-IDENTITY closure): the test CONTROLS the probe's Paddle
    environment (`_unconfigure_paddle`) instead of deleting variables the
    host's `.env` would silently put back — see `_PADDLE_ENV_NAMES`."""
    import tools.train.provenance as provenance

    _unconfigure_paddle(monkeypatch)

    root = tmp_path / "root"
    root.mkdir()
    data_dir = tmp_path / "data"
    record = provenance.collect(
        Path(__file__).resolve().parents[1], root, data_dir,
        label="test", hash_corpus=False, mode="digital",
    )
    # The probe runs in a subprocess; when it fails, `collect` records the
    # failure under `tree` and writes no `run_of_record` block at all. Surface
    # that record in the assertion so a host-specific probe failure (seen once
    # on the CI runner at the Phase 2.1 composed tree) reads as its cause,
    # never as a bare KeyError.
    assert "run_of_record" in record, {"tree": record.get("tree")}
    partitions = record["run_of_record"]["partitions"]
    assert "paddle_ocr_key" not in partitions
    note = partitions["paddle_ocr_key_note"]
    assert note == "not recorded: PaddleConfigError"
    assert "PADDLE_PROVIDER" not in note  # the variable NAME never crosses either
    assert "not set" not in note  # PaddleConfigError's own message text, absent


def test_provenance_records_the_paddle_key_and_a_note_when_paddle_is_configured(tmp_path, monkeypatch):
    """The inverse case (P22-IDENTITY closure, hermeticity): with a configured
    LOCAL Paddle environment the probe records `paddle_ocr_key` AND the note
    `recorded` — the note key is present on BOTH paths, so a reader never
    infers "configured" from an absence. No host, no port, no token is ever
    in the record (a local provider has none), and the key is a 64-hex
    settings fingerprint that differs from the production offline key."""
    import tools.train.provenance as provenance

    _configure_local_paddle(monkeypatch)

    root = tmp_path / "root"
    root.mkdir()
    record = provenance.collect(
        Path(__file__).resolve().parents[1], root, tmp_path / "data",
        label="test", hash_corpus=False, mode="digital",
    )
    assert "run_of_record" in record, {"tree": record.get("tree")}
    partitions = record["run_of_record"]["partitions"]
    assert partitions["paddle_ocr_key_note"] == "recorded"
    key = partitions["paddle_ocr_key"]
    assert isinstance(key, str) and len(key) == 64 and all(c in "0123456789ABCDEF" for c in key)
    assert key != partitions["offline_ocr_key"] and key != partitions["visual_ocr_key"]
    # the recorded run still selects as a production run (no research partition)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "provenance.json").write_text(json.dumps(record, default=str), encoding="utf-8")
    partitions_read = partitions_for_run(run_dir)
    assert partitions_read.ocr_keys_by_source["paddle"] == key
    assert partitions_read.research_partition == ""


def test_provenance_probe_tolerates_stdout_noise_before_its_json(tmp_path, monkeypatch):
    """Composed-tree finding (Phase 2.1, Ocean, 2026-09-02): on the CI runner
    a newer PyMuPDF printed a `fitz` deprecation notice to STDOUT on import,
    the probe's output was no longer pure JSON, and `collect` silently
    recorded the whole tree block as an error — so `run_of_record` vanished.
    The probe now delimits its JSON with a marker line; whatever precedes it
    is recorded as bounded `stdout_noise`, never a parse failure."""
    import tools.train.provenance as provenance

    _unconfigure_paddle(monkeypatch)
    noisy = "print('warning: some library printed this on import')\n" + provenance._TREE_PROBE
    monkeypatch.setattr(provenance, "_TREE_PROBE", noisy)

    root = tmp_path / "root"
    root.mkdir()
    record = provenance.collect(
        Path(__file__).resolve().parents[1], root, tmp_path / "data",
        label="test", hash_corpus=False, mode="digital",
    )
    assert "run_of_record" in record, {"tree": record.get("tree")}
    assert "offline_ocr_key" in record["run_of_record"]["partitions"]
    assert "error" not in record["tree"]


def test_provenance_probe_without_its_marker_is_an_error_not_a_guess(tmp_path, monkeypatch):
    """The other direction: output that never carries the marker (a probe
    that crashed before printing, or an older probe) is still recorded as an
    error — the parent never parses a guess out of arbitrary stdout."""
    import tools.train.provenance as provenance

    monkeypatch.setattr(provenance, "_TREE_PROBE", "print('{\"looks\": \"like json\"}')\n")
    root = tmp_path / "root"
    root.mkdir()
    record = provenance.collect(
        Path(__file__).resolve().parents[1], root, tmp_path / "data",
        label="test", hash_corpus=False, mode="digital",
    )
    assert "error" in record["tree"]
    assert "run_of_record" not in record


# ---------------------------------------------------------------------------
# P22-IDENTITY (Phase 2.2, cell K; D7; case 17): research partitions are
# never a run of record — refused by name before any key is read; the
# production key is unchanged when the field is empty; cohort_replay and
# provenance honour it.
# ---------------------------------------------------------------------------


def _write_recorded_run_with_partition(run_dir: Path, research_partition, **keys) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    partitions = {"offline_ocr_key": keys.get("offline_key", "OFFLINE1"),
                  "analysis_key": keys.get("analysis_key", "ANALYSIS1"), "mode": keys.get("mode", "digital")}
    if research_partition is not None:
        partitions["research_partition"] = research_partition
    (run_dir / "provenance.json").write_text(
        json.dumps({"tree": {"OCR_STAGE_VERSION": 5, "ANALYSIS_STAGE_VERSION": 18},
                    "run_of_record": {"partitions": partitions}}),
        encoding="utf-8",
    )


def test_a_recorded_run_carrying_a_research_partition_is_refused_by_name(tmp_path):
    """M11: the refusal names the partition, subclasses RunOfRecordError (so
    every exit-5 boundary honours it), and fires BEFORE any key is served."""
    from telemetry.run_of_record import ResearchPartitionRefused

    run_dir = tmp_path / "run"
    _write_recorded_run_with_partition(run_dir, "p23-wave-a")
    with pytest.raises(ResearchPartitionRefused) as caught:
        partitions_for_run(run_dir)
    assert caught.value.partition == "p23-wave-a"
    assert "p23-wave-a" in str(caught.value)
    assert isinstance(caught.value, RunOfRecordError)


@pytest.mark.parametrize("value", ["", None])
def test_an_empty_or_absent_research_partition_is_a_production_run(tmp_path, value):
    """The production selection is unchanged when the field is empty or
    (every run recorded before this cell) absent."""
    run_dir = tmp_path / "run"
    _write_recorded_run_with_partition(run_dir, value)
    partitions = partitions_for_run(run_dir)
    assert partitions.origin == ORIGIN_RECORDED
    assert partitions.research_partition == ""
    assert partitions.ocr_keys_by_source["native"] == "OFFLINE1"
    assert partitions.analysis_key == "ANALYSIS1"


def test_a_non_string_research_partition_is_malformed(tmp_path):
    run_dir = tmp_path / "run"
    _write_recorded_run_with_partition(run_dir, ["not", "a", "string"])
    with pytest.raises(RunOfRecordError):
        partitions_for_run(run_dir)


def test_a_research_run_is_refused_even_when_its_keys_exist_in_the_cache(tmp_path):
    """The refusal is not a verification failure: even a cache that DOES hold
    the research run's keys is refused, because a research artifact can never
    become historical truth (D7)."""
    from telemetry.run_of_record import ResearchPartitionRefused

    db_path = _make_cache_db(tmp_path, [
        ("ocr", "SHA1", "RESEARCH-OFFLINE", "artifacts/ocr/aa/x.json"),
        ("analysis", "SHA1", "RESEARCH-ANALYSIS", "artifacts/analysis/aa/y.json"),
    ])
    run_dir = tmp_path / "run"
    _write_recorded_run_with_partition(run_dir, "p23-wave-a", offline_key="RESEARCH-OFFLINE",
                                       analysis_key="RESEARCH-ANALYSIS")
    conn = _conn(db_path)
    try:
        with pytest.raises(ResearchPartitionRefused):
            partitions_for_run(run_dir, conn=conn)
    finally:
        conn.close()


def test_cohort_replay_exits_5_on_a_research_run_without_any_change_of_its_own(tmp_path, monkeypatch):
    """CASE 17: `tools/cohort_replay.py` needs no change — its existing
    `RunOfRecordError` boundary turns the refusal into exit 5 and never
    selects an artifact of the research run."""
    import tools.cohort_replay as cohort_replay

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _make_cache_db(data_dir, [
        ("ocr", "A" * 64, "RESEARCH-OFFLINE", "artifacts/ocr/aa/x.json"),
        ("analysis", "A" * 64, "RESEARCH-ANALYSIS", "artifacts/analysis/aa/y.json"),
    ])
    run_dir = tmp_path / "run"
    _write_recorded_run_with_partition(run_dir, "p23-wave-a", offline_key="RESEARCH-OFFLINE",
                                       analysis_key="RESEARCH-ANALYSIS")
    _write_rows_csv(run_dir, [{"content_sha256": "A" * 64, "source_path": "native",
                               "outcome_class": "validated", "outcome_reason": "", "parser_id": "x",
                               "folder_label": "f", "visual_rung": "not_attempted"}])
    shas = tmp_path / "shas.txt"
    shas.write_text("A" * 64 + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    exit_code = cohort_replay.main([
        "--run", str(run_dir), "--data-dir", str(data_dir), "--shas", str(shas),
        "--census", str(tmp_path / "absent-census.csv"), "--expect-identical",
    ])
    assert exit_code == 5


def test_provenance_validates_the_research_partition_before_any_probe(tmp_path, monkeypatch):
    """Review F-3 (closure-2): a malformed `--research-partition` used to be
    caught inside the probe by `attempt`, dropping the whole `run_of_record`
    block — after which `partitions_for_run` RECONSTRUCTED the run as a
    production-shaped record. The caller now validates the id up front with
    the SAME closed shape the cache module enforces and refuses before any
    subprocess starts; `main` exits 2 and writes nothing."""
    import tools.train.provenance as provenance
    import webapp.artifact_cache as cache_module

    assert provenance.RESEARCH_PARTITION_PATTERN == cache_module._RESEARCH_PARTITION_RE.pattern
    assert provenance.validate_research_partition("") == ""
    assert provenance.validate_research_partition(None) == ""
    assert provenance.validate_research_partition("p23-wave.a_1") == "p23-wave.a_1"
    for bad in ("bad id", "a/b", "-leading", "x" * 65, "nl\n", "tab\t"):
        with pytest.raises(ValueError):
            provenance.validate_research_partition(bad)

    def no_subprocess(*args, **kwargs):
        raise AssertionError("no probe or tool may run for a refused partition")

    monkeypatch.setattr(provenance.subprocess, "run", no_subprocess)
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError):
        provenance.collect(Path(__file__).resolve().parents[1], root, tmp_path / "data",
                           label="t", hash_corpus=False, mode="digital", research_partition="bad id")
    out = tmp_path / "out" / "provenance.json"
    exit_code = provenance.main([
        "--checkout", str(Path(__file__).resolve().parents[1]), "--root", str(root),
        "--data-dir", str(tmp_path / "data"), "--out", str(out), "--mode", "digital",
        "--research-partition", "bad id",
    ])
    assert exit_code == 2
    assert not out.exists() and not out.with_suffix(".md").exists()


def test_provenance_records_the_research_partition_and_folds_it_into_the_keys(tmp_path, monkeypatch):
    """`tools/train/provenance.py --research-partition <id>` records the id in
    `run_of_record.partitions` and computes the OCR keys WITH it, so the
    recorded run is refused as a run of record; a production call records
    the empty string and the production keys."""
    import tools.train.provenance as provenance
    from telemetry.run_of_record import ResearchPartitionRefused

    _unconfigure_paddle(monkeypatch)
    root = tmp_path / "root"
    root.mkdir()
    checkout = Path(__file__).resolve().parents[1]
    production = provenance.collect(checkout, root, tmp_path / "data", label="t", hash_corpus=False, mode="digital")
    research = provenance.collect(checkout, root, tmp_path / "data", label="t", hash_corpus=False, mode="digital",
                                  research_partition="p23-wave-a")
    assert "run_of_record" in production, {"tree": production.get("tree")}
    assert "run_of_record" in research, {"tree": research.get("tree")}
    prod_parts = production["run_of_record"]["partitions"]
    research_parts = research["run_of_record"]["partitions"]
    assert prod_parts["research_partition"] == ""
    assert research_parts["research_partition"] == "p23-wave-a"
    assert prod_parts["offline_ocr_key"] != research_parts["offline_ocr_key"]
    assert prod_parts["visual_ocr_key"] != research_parts["visual_ocr_key"]
    assert prod_parts["analysis_key"] == research_parts["analysis_key"]
    assert production["tree"]["EXTRACTION_SCHEMA_VERSION"] == 3
    assert production["tree"]["EVIDENCE_SCHEMA_VERSION"] == 1
    assert "RECONSTRUCTION_MODE" in production["env"]

    run_dir = tmp_path / "research-run"
    run_dir.mkdir()
    (run_dir / "provenance.json").write_text(json.dumps(research, default=str), encoding="utf-8")
    with pytest.raises(ResearchPartitionRefused):
        partitions_for_run(run_dir)
    production_dir = tmp_path / "production-run"
    production_dir.mkdir()
    (production_dir / "provenance.json").write_text(json.dumps(production, default=str), encoding="utf-8")
    assert partitions_for_run(production_dir).research_partition == ""
