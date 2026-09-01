"""CASE 9 (P20-ARTIFACTS, Phase 2.0) — multi-partition artifact-selection
determinism, proven against BOTH readers that adopt `telemetry/run_of_record.py`:
`tools.cohort_replay.ColdCache` and `telemetry.stated_counts._ArtifactJoin`.

Scenario: ONE input (one PDF, one `content_sha256`) with THREE cached OCR
artifacts (offline-local, offline-nolocal, visual) and, off the offline-nolocal
text, TWO cached analysis artifacts (two different analysis settings keys —
the shape of a data directory spanning two parser-registry fingerprints). A
synthetic RECORDED run of record declares its ACTUAL partitions: the
offline-nolocal OCR key and one specific analysis key, no visual key at all
(a "digital" mode run — the visual and offline-local artifacts are DECOYS
some other run or tranche wrote into the same shared cache). Two rows name
the SAME content_sha256 with DIFFERENT provenance (`source_path` /
`visual_rung`), proving resolution is a property of each ROW, not something
memoized per document.

Both readers must, deterministically and identically:
* resolve the row naming the offline partition to the OFFLINE-NOLOCAL text
  and the run's declared analysis payload — never the offline-local or
  visual decoys, never the other analysis partition;
* resolve the row naming the visual outcome (`visual_rung="recovered"`) to
  `None` — the run's partitions carry no visual key, so that is an absent
  partition, never a silent fallback to the offline text;
* reproduce this identically regardless of the ORDER the five artifacts were
  written to the cache in (20 shuffled-insertion runs) — proving no
  dependency on SQLite's row order, which is unspecified without `ORDER BY`
  (the `rows[0]` bug this module replaces).

And the three named mutants must be shown to disagree with this population:
`rows[0]` (no settings-key filter at all), the `_ocr_keys` ordered-preference
walk (offline-local, then offline-nolocal, then visual), and a visual-first
preference.
"""
from __future__ import annotations

import itertools
import json
import random
from pathlib import Path

import pytest

from ocr.document import StatementMarkdown
from ocr.inspect import content_sha256
from webapp.artifact_cache import (
    ArtifactCache,
    analysis_settings_key,
    cached_analysis,
    ocr_settings_key,
)
from webapp.storage import Storage

PDF_X = b"%PDF-1.7\ncase9 multi-partition fixture"
SHA_X = content_sha256(PDF_X)

KEY_OFFLINE_LOCAL = ocr_settings_key(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False)
KEY_OFFLINE_NOLOCAL = ocr_settings_key(force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False)
KEY_VISUAL = ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True)

_DOC_LOCAL = StatementMarkdown(source_file="case9.pdf", model="local-tesseract-ocr", pages=["OFFLINE-LOCAL PAGE"])
_DOC_NOLOCAL = StatementMarkdown(source_file="case9.pdf", model="native-pdf-text", pages=["OFFLINE-NOLOCAL PAGE"])
_DOC_VISUAL = StatementMarkdown(source_file="case9.pdf", model="visual-ocr", pages=["VISUAL PAGE"])

ANALYSIS_KEY_OLD = analysis_settings_key(parse_mode="deterministic")
ANALYSIS_PAYLOAD_OLD = {"marker": "OLD", "statement": {"bank": "Old Fingerprint Bank"}}
ANALYSIS_PAYLOAD_NEW = {"marker": "NEW", "statement": {"bank": "New Fingerprint Bank"}}

# A second, genuinely distinct analysis settings key (the shape of a second
# parser-registry fingerprint / a later wave's tree) — `model` is real key
# material (`analysis_settings_key`'s docstring), so this is a real key, not
# a fabricated string.
_ANALYSIS_KEY_NEW_SOURCE_MODEL = "gemini-a-different-fingerprint-stand-in"


class _AnalysisSettings:
    def __init__(self, model: str = "gemini-3.5-flash-lite") -> None:
        self.model = model
        self.escalation_model = "gemini-3.5-flash"
        self.withholding_denominator_mode = "legacy_eligible_deposits"


ANALYSIS_KEY_NEW = analysis_settings_key(
    parse_mode="deterministic", analysis_settings=_AnalysisSettings(model=_ANALYSIS_KEY_NEW_SOURCE_MODEL)
)

assert ANALYSIS_KEY_OLD != ANALYSIS_KEY_NEW, "fixture bug: the two analysis keys must be distinct"

ROW_OFFLINE = {"content_sha256": SHA_X, "source_path": "native", "visual_rung": "not_attempted"}
ROW_VISUAL_ABSENT = {"content_sha256": SHA_X, "source_path": "native", "visual_rung": "recovered"}


def _write_artifacts(data_dir: Path, order: list[str]) -> None:
    """Write all five artifacts (3 OCR + 2 analysis) to `data_dir` in `order`
    (a permutation of the five names below) — the insertion order under test."""
    cache = ArtifactCache(Storage(data_dir))
    writers = {
        "ocr_local": lambda: cache.put_ocr(SHA_X, KEY_OFFLINE_LOCAL, _DOC_LOCAL),
        "ocr_nolocal": lambda: cache.put_ocr(SHA_X, KEY_OFFLINE_NOLOCAL, _DOC_NOLOCAL),
        "ocr_visual": lambda: cache.put_ocr(SHA_X, KEY_VISUAL, _DOC_VISUAL),
        "analysis_old": lambda: cached_analysis(
            _DOC_NOLOCAL.to_markdown(), compute=lambda: ANALYSIS_PAYLOAD_OLD, cache=cache,
            parse_mode="deterministic", sheets=_DOC_NOLOCAL.pages,
        ),
        "analysis_new": lambda: cached_analysis(
            _DOC_NOLOCAL.to_markdown(), compute=lambda: ANALYSIS_PAYLOAD_NEW, cache=cache,
            parse_mode="deterministic", analysis_settings=_AnalysisSettings(model=_ANALYSIS_KEY_NEW_SOURCE_MODEL),
            sheets=_DOC_NOLOCAL.pages,
        ),
    }
    for name in order:
        writers[name]()


def _write_run_dir(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "provenance.json").write_text(
        json.dumps(
            {
                "tree": {},
                "run_of_record": {
                    "partitions": {
                        "offline_ocr_key": KEY_OFFLINE_NOLOCAL,
                        "analysis_key": ANALYSIS_KEY_NEW,
                        "mode": "digital",
                        # deliberately NO visual_ocr_key: this run never ran
                        # the visual rung, though the shared cache holds a
                        # visual artifact for this input from elsewhere.
                    }
                },
            }
        ),
        encoding="utf-8",
    )


_ALL_ARTIFACT_NAMES = ["ocr_local", "ocr_nolocal", "ocr_visual", "analysis_old", "analysis_new"]
_ALL_PERMUTATIONS = list(itertools.permutations(_ALL_ARTIFACT_NAMES))
_TWENTY_ORDERS = random.Random(20260901).sample(_ALL_PERMUTATIONS, 20)


@pytest.mark.parametrize("order", _TWENTY_ORDERS, ids=[f"order{i}" for i in range(20)])
def test_case9_both_readers_resolve_deterministically_regardless_of_insertion_order(tmp_path, order):
    from telemetry.stated_counts import _ArtifactJoin
    from tools.cohort_replay import ColdCache

    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run"
    _write_artifacts(data_dir, list(order))
    _write_run_dir(run_dir)

    # --- reader 1: tools.cohort_replay.ColdCache ---------------------------
    cold = ColdCache(data_dir, run_dir)
    markdown, pages = cold.text(SHA_X, ROW_OFFLINE)
    assert markdown is not None and "OFFLINE-NOLOCAL PAGE" in markdown
    assert "OFFLINE-LOCAL PAGE" not in markdown and "VISUAL PAGE" not in markdown
    baseline = cold.baseline_payload(markdown, pages)
    assert baseline == ANALYSIS_PAYLOAD_NEW

    # The visual-outcome row: no visual partition in this run -> None, never
    # a fallback to the offline text.
    markdown_absent, _ = cold.text(SHA_X, ROW_VISUAL_ABSENT)
    assert markdown_absent is None

    # --- reader 2: telemetry.stated_counts._ArtifactJoin -------------------
    join = _ArtifactJoin(data_dir, run_dir)
    resolved = join.payload_for(SHA_X, "case9.pdf", ROW_OFFLINE)
    assert resolved == ANALYSIS_PAYLOAD_NEW
    assert join.payload_for(SHA_X, "case9.pdf", ROW_VISUAL_ABSENT) is None


def test_case9_the_decoy_partitions_are_never_returned_for_any_row(tmp_path):
    """Belt and braces: over EVERY row shape this input could plausibly carry
    in a real run, the two decoys (offline-local text, the old analysis
    payload) never surface."""
    from telemetry.stated_counts import _ArtifactJoin
    from tools.cohort_replay import ColdCache

    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run"
    _write_artifacts(data_dir, _ALL_ARTIFACT_NAMES)
    _write_run_dir(run_dir)

    cold = ColdCache(data_dir, run_dir)
    join = _ArtifactJoin(data_dir, run_dir)
    for row in (
        ROW_OFFLINE,
        {"content_sha256": SHA_X, "source_path": "local_tesseract", "visual_rung": "not_attempted"},
        {"content_sha256": SHA_X, "source_path": "local_tesseract", "visual_rung": "no_upgrade"},
    ):
        markdown, _ = cold.text(SHA_X, row)
        assert markdown is not None and "OFFLINE-LOCAL PAGE" not in markdown and "VISUAL PAGE" not in markdown
        payload = join.payload_for(SHA_X, "case9.pdf", row)
        assert payload != ANALYSIS_PAYLOAD_OLD


# ---------------------------------------------------------------------------
# mutation table: rows[0], the _ocr_keys preference walk, visual-first
# ---------------------------------------------------------------------------


def test_case9_mutant_rows0_disagrees_with_the_correct_resolution(tmp_path):
    """Review MINOR-4: the PRIMARY killer of the `rows[0]` mutant is
    `test_case9_both_readers_resolve_deterministically_regardless_of_insertion_order`
    (20 shuffled insertion orders, both readers, asserted correct every
    time) — this test's job is narrower and additional: show the mutant
    ITSELF actually resolving the WRONG artifact under at least one
    insertion order, not merely that three rows exist for one input (the
    old, vacuous version of this test asserted only `len(rows) == 3`, which
    is true regardless of whether `rows[0]` ever picks correctly — it never
    even applied the mutant's own `SELECT`, let alone compared its result
    against the correct partition's pages)."""
    import sqlite3

    def mutant_rows0(data_dir: Path) -> list[str]:
        conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT artifact_path FROM artifact_cache WHERE stage = 'ocr' AND input_sha256 = ?",
                (SHA_X,),
            ).fetchall()
            assert len(rows) == 3, "fixture bug: expected all three OCR partitions present"
            payload = json.loads((data_dir / "artifacts" / rows[0][0]).read_text(encoding="utf-8"))
            return payload["artifact"]["document"]["pages"]
        finally:
            conn.close()

    disagreed_at_least_once = False
    for order in _TWENTY_ORDERS:
        data_dir = tmp_path / f"data_{'_'.join(order)}"
        _write_artifacts(data_dir, list(order))
        if mutant_rows0(data_dir) != ["OFFLINE-NOLOCAL PAGE"]:
            disagreed_at_least_once = True
    assert disagreed_at_least_once, (
        "the rows[0] mutant agreed with the correct resolution on every one of "
        "20 insertion orders — SQLite's row order is unspecified without ORDER "
        "BY, so this would mean the test host's b-tree happened to always "
        "return the same physical order across writes, not that the mutant is safe"
    )


def test_case9_mutant_ocr_keys_preference_picks_the_wrong_partition(tmp_path):
    """The `_ocr_keys` ordered-preference mutant this module replaces
    (`telemetry/stated_counts.py`'s old `_ocr_keys` list, offline-local FIRST):
    walking `[KEY_OFFLINE_LOCAL, KEY_OFFLINE_NOLOCAL, KEY_VISUAL]` in order and
    taking the first hit returns the OFFLINE-LOCAL decoy for this input, not
    the run's own offline-nolocal partition."""
    import sqlite3

    data_dir = tmp_path / "data"
    _write_artifacts(data_dir, _ALL_ARTIFACT_NAMES)
    conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)

    def mutant_ocr_keys_preference(input_sha: str) -> str | None:
        for key in (KEY_OFFLINE_LOCAL, KEY_OFFLINE_NOLOCAL, KEY_VISUAL):
            row = conn.execute(
                "SELECT artifact_path FROM artifact_cache WHERE stage = 'ocr' "
                "AND input_sha256 = ? AND settings_key = ?",
                (input_sha, key),
            ).fetchone()
            if row:
                return str(row[0])
        return None

    try:
        mutant_path = mutant_ocr_keys_preference(SHA_X)
    finally:
        conn.close()
    assert mutant_path is not None
    payload = json.loads((data_dir / "artifacts" / mutant_path).read_text(encoding="utf-8"))
    mutant_pages = payload["artifact"]["document"]["pages"]
    # The mutant resolves the offline-LOCAL decoy...
    assert mutant_pages == ["OFFLINE-LOCAL PAGE"]

    # ...while the real, run-of-record-driven resolution correctly picks the
    # offline-NOLOCAL partition this run actually declared.
    from telemetry.run_of_record import ocr_partition_for_row, select_artifact
    from telemetry.run_of_record import partitions_for_run

    run_dir = tmp_path / "run"
    _write_run_dir(run_dir)
    conn2 = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
    try:
        partitions = partitions_for_run(run_dir, conn=conn2)
        real_key = ocr_partition_for_row(ROW_OFFLINE, partitions)
        real_path = select_artifact(conn2, "ocr", SHA_X, real_key)
    finally:
        conn2.close()
    real_payload = json.loads((data_dir / "artifacts" / real_path).read_text(encoding="utf-8"))
    assert real_payload["artifact"]["document"]["pages"] == ["OFFLINE-NOLOCAL PAGE"]
    assert real_path != mutant_path


def test_case9_mutant_visual_first_picks_the_visual_decoy(tmp_path):
    """A visual-FIRST preference mutant (Risk 7's exact disposition — never
    ratified, F-9): walking `[KEY_VISUAL, KEY_OFFLINE_NOLOCAL, KEY_OFFLINE_LOCAL]`
    resolves the visual decoy for a row this run never escalated."""
    import sqlite3

    data_dir = tmp_path / "data"
    _write_artifacts(data_dir, _ALL_ARTIFACT_NAMES)
    conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)

    def mutant_visual_first(input_sha: str) -> str | None:
        for key in (KEY_VISUAL, KEY_OFFLINE_NOLOCAL, KEY_OFFLINE_LOCAL):
            row = conn.execute(
                "SELECT artifact_path FROM artifact_cache WHERE stage = 'ocr' "
                "AND input_sha256 = ? AND settings_key = ?",
                (input_sha, key),
            ).fetchone()
            if row:
                return str(row[0])
        return None

    try:
        mutant_path = mutant_visual_first(SHA_X)
    finally:
        conn.close()
    payload = json.loads((data_dir / "artifacts" / mutant_path).read_text(encoding="utf-8"))
    assert payload["artifact"]["document"]["pages"] == ["VISUAL PAGE"]

    # The real resolution for the SAME offline row never touches the visual
    # partition at all (proven above); this test documents the contrast.
    from telemetry.run_of_record import ocr_partition_for_row, partitions_for_run

    run_dir = tmp_path / "run"
    _write_run_dir(run_dir)
    conn2 = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
    try:
        partitions = partitions_for_run(run_dir, conn=conn2)
    finally:
        conn2.close()
    assert ocr_partition_for_row(ROW_OFFLINE, partitions) == KEY_OFFLINE_NOLOCAL


# ---------------------------------------------------------------------------
# review MAJOR-1(c) — --expect-identical refuses a vacuous zero-resolution
# on the CALLER's selected cohort, distinct from verify_reconstruction's own
# bounded correspondence sample (which only ever samples the run's FIRST
# rows, never a caller's --shas/--folder/--group selection)
# ---------------------------------------------------------------------------


def test_expect_identical_refuses_a_vacuous_zero_resolution_on_the_selected_cohort(tmp_path, capsys):
    """The run's declared offline key can pass BOTH verify_reconstruction's
    existence check and its bounded-sample correspondence check (an early
    row in rows.csv resolves) while the SPECIFIC cohort a caller selects via
    --shas resolves NONE of it. That is a distinct failure mode from the
    review's original MAJOR-1(a) reproduction (a run whose partitions
    describe NOTHING in the data directory) and from MAJOR-1(b)
    (correspondence) — this is the guard `tools/cohort_replay.py::main`
    itself must carry, because no bounded sample inside
    `telemetry/run_of_record.py` can see a caller's selection in advance."""
    import subprocess
    import sys

    from webapp.artifact_cache import ArtifactCache, cached_analysis
    from webapp.storage import Storage

    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run"

    offline_key = KEY_OFFLINE_NOLOCAL
    cache = ArtifactCache(Storage(data_dir))

    # The correspondence-sample document: cached under the offline key, and
    # named FIRST in rows.csv so verify_reconstruction's bounded sample sees
    # it and the run's declared offline key passes existence+correspondence.
    corr_pdf = b"%PDF-1.7\ncorrespondence-sample document, never selected for replay"
    corr_sha = content_sha256(corr_pdf)
    corr_doc = StatementMarkdown(source_file="corr.pdf", model="native-pdf-text", pages=["CORR PAGE"])
    cache.put_ocr(corr_sha, offline_key, corr_doc)
    result = cached_analysis(
        corr_doc.to_markdown(), compute=lambda: {"marker": "CORR"}, cache=cache,
        parse_mode="deterministic", sheets=corr_doc.pages,
    )
    assert not result.cached

    # The document the caller actually asks to replay: never cached at all.
    target_pdf = b"%PDF-1.7\nthe replay target, no cached artifact anywhere"
    target_sha = content_sha256(target_pdf)

    from webapp.artifact_cache import analysis_settings_key

    _write_run_dir_with_partitions(
        run_dir, offline_key=offline_key, analysis_key=analysis_settings_key(parse_mode="deterministic"),
        mode="digital",
    )
    (run_dir / "rows.csv").write_text(
        "content_sha256,folder_label,outcome_class,outcome_reason,parser_id,source_path,visual_rung\n"
        f"{corr_sha},Correspondence,validated,,some_parser,native,not_attempted\n"
        f"{target_sha},Target,failed,no_parser_matched,,native,not_attempted\n",
        encoding="utf-8",
    )
    shas_file = tmp_path / "shas.txt"
    shas_file.write_text(target_sha + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "-m", "tools.cohort_replay",
            "--run", str(run_dir), "--data-dir", str(data_dir),
            "--shas", str(shas_file), "--expect-identical",
        ],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "0 of 1 shas resolved any cached text" in result.stdout


def _write_run_dir_with_partitions(run_dir: Path, *, offline_key: str, analysis_key: str, mode: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("provenance.json").write_text(
        json.dumps(
            {
                "tree": {},
                "run_of_record": {
                    "partitions": {
                        "offline_ocr_key": offline_key,
                        "analysis_key": analysis_key,
                        "mode": mode,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
