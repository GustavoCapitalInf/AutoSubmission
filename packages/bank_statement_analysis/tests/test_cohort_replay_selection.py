"""CASE 9 (P20-ARTIFACTS, Phase 2.0) — multi-partition artifact-selection
determinism, proven against the reader that adopts `telemetry/run_of_record.py`:
`telemetry.stated_counts._ArtifactJoin`.

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

The reader must, deterministically:
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
def test_case9_the_reader_resolves_deterministically_regardless_of_insertion_order(tmp_path, order):
    from telemetry.stated_counts import _ArtifactJoin

    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run"
    _write_artifacts(data_dir, list(order))
    _write_run_dir(run_dir)

    join = _ArtifactJoin(data_dir, run_dir)
    resolved = join.payload_for(SHA_X, "case9.pdf", ROW_OFFLINE)
    assert resolved == ANALYSIS_PAYLOAD_NEW
    assert join.payload_for(SHA_X, "case9.pdf", ROW_VISUAL_ABSENT) is None


def test_case9_the_decoy_partitions_are_never_returned_for_any_row(tmp_path):
    """Belt and braces: over EVERY row shape this input could plausibly carry
    in a real run, the two decoys (offline-local text, the old analysis
    payload) never surface."""
    from telemetry.stated_counts import _ArtifactJoin

    data_dir = tmp_path / "data"
    run_dir = tmp_path / "run"
    _write_artifacts(data_dir, _ALL_ARTIFACT_NAMES)
    _write_run_dir(run_dir)

    join = _ArtifactJoin(data_dir, run_dir)
    for row in (
        ROW_OFFLINE,
        {"content_sha256": SHA_X, "source_path": "local_tesseract", "visual_rung": "not_attempted"},
        {"content_sha256": SHA_X, "source_path": "local_tesseract", "visual_rung": "no_upgrade"},
    ):
        payload = join.payload_for(SHA_X, "case9.pdf", row)
        assert payload != ANALYSIS_PAYLOAD_OLD
