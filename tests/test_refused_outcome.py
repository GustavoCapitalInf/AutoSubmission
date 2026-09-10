"""P22-TRUTHTABLE item 2 (R11): the terminal class `refused`, its reserved
reasons, the compare semantics and the exact transition matrix.

* `classify_outcome` / `classify_document` gain `refused=` — an explicit
  declaration by the caller, never inferred, exactly like `deferred=`; the
  reasons are the closed six and nothing in 2.2 produces one;
* `DOCUMENT_LADDER` and `LADDER` are unchanged (`failed < withheld < review <
  validated`); `refused` is UNRANKED against failed / withheld / review;
* ANY transition out of `validated` — to `refused`, `deferred`, `unknown`
  included — is `regressed` (exit 2 under `--fail-on-regression`), the M3 pin;
* the transition matrix is printed exactly, every class present (M4);
* a base/candidate pair whose raw denominators (distinct sha counts) differ
  is REFUSED with a named error, never silently re-baselined (M5).
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from discovery.compare import (
    ALL_CLASSES,
    LADDER,
    UNRANKED,
    RawDenominatorMismatch,
    compare,
    direction,
    main as compare_main,
    render,
    transition_matrix,
)
from discovery.evidence import load_run
from telemetry.record import (
    DEFERRED_REASONS,
    DOCUMENT_LADDER,
    OUTCOME_CLASSES,
    REFUSED_REASONS,
    build_record,
    classify_document,
    classify_outcome,
)

APPROVED = {"metrics": {"average_daily_balance": 1.0}, "quality": {"corporate_use": "approved"}}


# ---------------------------------------------------------------------------
# the vocabulary
# ---------------------------------------------------------------------------


def test_refused_is_a_first_class_outcome_with_the_six_reserved_reasons():
    assert "refused" in OUTCOME_CLASSES
    assert REFUSED_REASONS == (
        "not_a_statement", "file_invalid", "insufficient_evidence", "contradictory", "incomplete", "unreadable",
    )
    assert not set(REFUSED_REASONS) & set(DEFERRED_REASONS)


def test_the_ladders_are_unchanged_and_refused_is_not_a_rung():
    assert DOCUMENT_LADDER == ("failed", "withheld", "review", "validated")
    assert LADDER == DOCUMENT_LADDER
    assert "refused" not in LADDER and "refused" in UNRANKED and "deferred" in UNRANKED


def test_refused_is_declared_never_inferred():
    for reason in REFUSED_REASONS:
        assert classify_outcome(None, refused=reason) == ("refused", reason)
        assert classify_outcome(APPROVED, refused=reason) == ("refused", reason)
        assert classify_document(APPROVED, refused=reason) == ("refused", reason)
    assert classify_outcome(None) == ("failed", "no_analysis")
    assert classify_outcome(APPROVED) == ("validated", "approved")


def test_an_unknown_refusal_reason_is_refused():
    with pytest.raises(ValueError, match="unknown refusal reason"):
        classify_outcome(None, refused="because")
    with pytest.raises(ValueError, match="unknown refusal reason"):
        classify_document(APPROVED, refused="because")


def test_a_deferral_outranks_a_refusal_it_is_a_statement_about_the_run():
    assert classify_outcome(None, deferred="deferred_scanned", refused="unreadable") == ("deferred", "deferred_scanned")


def test_build_record_threads_the_refusal():
    record = build_record(
        run_id="r", emitter="t", document={"content_sha256": "A" * 64}, source={"model": None, "path": "none"},
        dispatch={}, stages={}, model_calls=[], payload=None, refused="not_a_statement",
    )
    assert record["outcome"]["class"] == "refused"
    assert record["outcome"]["reason"] == "not_a_statement"


# ---------------------------------------------------------------------------
# direction: unranked among the terminal classes, ANY exit from validated regressed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("after", ["failed", "withheld", "review", "refused", "deferred", "unknown"])
def test_every_exit_from_validated_is_a_regression(after):
    assert direction("validated", after) == "regressed"


@pytest.mark.parametrize("before", ["failed", "withheld", "review"])
def test_refused_is_unranked_against_the_terminal_classes(before):
    assert direction(before, "refused") == "unranked"
    assert direction("refused", before) == "unranked"


def test_refused_to_validated_is_unranked_like_deferred_to_validated():
    assert direction("refused", "validated") == "unranked"
    assert direction("deferred", "validated") == "unranked"
    assert direction("refused", "refused") == "unchanged"


def test_the_ladder_semantics_are_otherwise_unchanged():
    assert direction("failed", "withheld") == "improved"
    assert direction("review", "failed") == "regressed"
    assert direction("withheld", "validated") == "improved"
    assert direction("failed", "deferred") == "unranked"


# ---------------------------------------------------------------------------
# the exact transition matrix, and the raw-denominator refusal
# ---------------------------------------------------------------------------


def _record(sha: str, outcome_class: str, *, run_id: str = "r", parser_id: str | None = "chase") -> dict:
    return {
        "run_id": run_id,
        "document": {"content_sha256": sha, "classification": "digital", "page_count": 1, "byte_size": 1,
                     "valid_pdf": True, "encrypted": False, "malformed_page_count": 0},
        "source": {"path": "native", "truncation": {"truncated_page_count": 0}},
        "dispatch": {"outcome": "claimed" if parser_id else None, "parser_id": parser_id, "source": "live", "scores": []},
        "outcome": {"class": outcome_class, "reason": "r"},
        "diagnostics": {"evaluated": False},
    }


def _write_run(directory: Path, records: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "telemetry.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    return directory


def test_all_classes_is_every_class_the_matrix_must_name():
    assert ALL_CLASSES == LADDER + UNRANKED
    assert set(ALL_CLASSES) == {"failed", "withheld", "review", "validated", "deferred", "unknown", "refused"}


def test_the_transition_matrix_names_every_class_pair_with_a_count(tmp_path):
    """M4's killer: the matrix has a row for every class and a column for
    every class, zeros included — a class omitted from the shape fails here
    before any count is read."""
    shas = [f"{i:064d}" for i in range(4)]
    base = _write_run(tmp_path / "base", [
        _record(shas[0], "validated"), _record(shas[1], "failed"),
        _record(shas[2], "validated"), _record(shas[3], "withheld"),
    ])
    cand = _write_run(tmp_path / "cand", [
        _record(shas[0], "refused"), _record(shas[1], "refused"),
        _record(shas[2], "validated"), _record(shas[3], "validated"),
    ])
    report = compare(load_run(base), load_run(cand))
    matrix = report["transition_matrix"]
    assert list(matrix) == list(ALL_CLASSES)
    for source in ALL_CLASSES:
        assert list(matrix[source]) == list(ALL_CLASSES), source
    assert matrix["validated"]["refused"] == 1
    assert matrix["failed"]["refused"] == 1
    assert matrix["validated"]["validated"] == 1
    assert matrix["withheld"]["validated"] == 1
    assert sum(sum(row.values()) for row in matrix.values()) == report["documents"]["shared"] == 4
    assert report["movement"] == {"regressed": 1, "unranked": 1, "unchanged": 1, "improved": 1}
    text = render(report)
    assert "transition matrix" in text
    for name in ALL_CLASSES:
        assert name in text
    assert text.isascii()


def test_transition_matrix_is_a_pure_function_of_the_pairs():
    pairs = [("validated", "refused"), ("failed", "failed"), ("deferred", "unknown")]
    matrix = transition_matrix(pairs)
    assert matrix["validated"]["refused"] == 1 and matrix["failed"]["failed"] == 1 and matrix["deferred"]["unknown"] == 1
    assert sum(sum(row.values()) for row in matrix.values()) == 3
    with pytest.raises(ValueError, match="not a known outcome class"):
        transition_matrix([("validated", "made_up")])


def test_validated_to_refused_fails_the_build_with_exit_2(tmp_path):
    """M3's killer: `validated -> refused` treated as unranked would exit 0."""
    sha = "A" * 64
    base = _write_run(tmp_path / "base", [_record(sha, "validated")])
    cand = _write_run(tmp_path / "cand", [_record(sha, "refused")])
    assert compare_main([str(base), str(cand), "--fail-on-regression"]) == 2
    report = compare(load_run(base), load_run(cand))
    assert report["movement"] == {"regressed": 1}
    assert report["transitions"] == {"validated -> refused": 1}


def test_differing_raw_denominators_are_refused_by_name(tmp_path, capsys):
    """M5's killer: a base with 3 distinct shas against a candidate with 2 is
    not compared over the intersection — it is refused."""
    shas = [f"{i:064d}" for i in range(3)]
    base = _write_run(tmp_path / "base", [_record(s, "validated") for s in shas])
    cand = _write_run(tmp_path / "cand", [_record(s, "validated") for s in shas[:2]])
    with pytest.raises(RawDenominatorMismatch, match="3 != 2"):
        compare(load_run(base), load_run(cand))
    assert compare_main([str(base), str(cand)]) == 3
    assert "raw denominators differ" in capsys.readouterr().err


def test_equal_denominators_with_different_membership_are_still_reported_not_refused(tmp_path):
    """The pre-existing `NOT COMPARABLE` reporting stays for equal counts
    with different document sets (`tests/test_adjudication.py` pins it)."""
    base = _write_run(tmp_path / "base", [_record("A" * 64, "validated"), _record("B" * 64, "failed")])
    cand = _write_run(tmp_path / "cand", [_record("A" * 64, "validated"), _record("C" * 64, "failed")])
    report = compare(load_run(base), load_run(cand))
    assert report["documents"]["only_baseline"] == 1
    assert report["raw_denominator"] == {"baseline": 2, "candidate": 2}


def test_the_report_prints_the_raw_denominators_first(tmp_path):
    base = _write_run(tmp_path / "base", [_record("A" * 64, "validated"), _record("B" * 64, "failed")])
    cand = _write_run(tmp_path / "cand", [_record("A" * 64, "validated"), _record("B" * 64, "validated")])
    report = compare(load_run(base), load_run(cand))
    text = render(report)
    assert report["raw_denominator"] == {"baseline": 2, "candidate": 2}
    assert report["raw_coverage"] == {"baseline": {"validated": 1, "denominator": 2},
                                      "candidate": {"validated": 2, "denominator": 2}}
    raw_line = next(line for line in text.splitlines() if "raw denominator" in line)
    ccl_line = next(line for line in text.splitlines() if "ccl_adjudicated" in line)
    assert text.index(raw_line) < text.index(ccl_line)
    assert "not available in this tool" in ccl_line


def test_every_class_pair_has_a_direction():
    for before, after in itertools.product(ALL_CLASSES, repeat=2):
        assert direction(before, after) in ("improved", "regressed", "unchanged", "unranked")
        if before == "validated" and after != "validated":
            assert direction(before, after) == "regressed"
