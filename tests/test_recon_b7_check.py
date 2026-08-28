"""tools/recon_b7_check.py — the frozen acceptance logic for the regenerated
batch-7 baseline, exercised on synthetic runs and synthetic records."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools import recon_b7_check as rc

SHA = {name: (name * 64)[:64].upper() for name in "ABCDEF"}


def _run_dir(tmp_path: Path, docs: dict[str, tuple[str, str]], *, registration_count=75,
             dedup=(0, 0), inventory=None, mode="scanned") -> Path:
    """docs: sha -> (outcome_class, source_path)."""
    run = tmp_path / "run"
    run.mkdir()
    with (run / "telemetry.jsonl").open("w", encoding="utf-8") as handle:
        for sha, (outcome, path) in docs.items():
            handle.write(json.dumps({
                "run_id": "t", "document": {"content_sha256": sha},
                "outcome": {"class": outcome, "reason": "x"},
                "dispatch": {"registration_count": registration_count, "source": "live"},
                "source": {"path": path},
            }) + "\n")
    with (run / "rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "relative_path", "folder_label", "content_sha256", "dedup_status",
            "source_path", "parser_id", "outcome_class", "statement_bank"])
        writer.writeheader()
        for sha, (outcome, path) in docs.items():
            writer.writerow({"relative_path": f"x/{sha[:4]}.pdf", "folder_label": "x",
                             "content_sha256": sha, "dedup_status": "unique",
                             "source_path": path, "parser_id": "p", "outcome_class": outcome,
                             "statement_bank": ""})
    (run / "summary.json").write_text(json.dumps({
        "mode": mode, "dedup": {"unique": len(docs), "duplicate": dedup[0], "pinned_corpus_duplicate": dedup[1]},
        "inventory": inventory or {}, "reasons": {"invalid_pdf": 0}, "deferred_reasons": {},
    }), encoding="utf-8")
    return run


@pytest.fixture
def small_record(monkeypatch):
    """Shrink the frozen record so a three-document run can be exact."""
    monkeypatch.setattr(rc, "RECORD", {
        "distinct_shas": 3,
        "outcome": {"validated": 1, "review": 0, "withheld": 1, "failed": 1, "deferred": 0},
        "rows": 3, "dedup": {"duplicate": 0, "pinned_corpus_duplicate": 0},
        "inventory": {}, "mode": "scanned", "registration_count": 75,
        "explained_improvements_cap": 24,
    })


def _check(run, **oracles):
    defaults = dict(pinned={}, census_failed=[], census_withheld=[], welch=[], rbc={}, batch7_named=set())
    defaults.update(oracles)
    return rc.check(rc.load_run_view(run), **defaults)


# ---- oracle extraction ----------------------------------------------------

def test_census_fenced_lists_only_and_withheld_table():
    text = "\n".join([
        "## Family records", "### 1. fam", "- **VERIFY:** misfiled 8CCAE7DD830DF214 in prose",
        "- **shas:**", "```", SHA["A"], f"{SHA['B'][:30]}[long digit run redacted]{SHA['B'][-20:]}", "```",
        "## not_statements", "```", "{", ' "shas": [', f'  "{SHA["C"]}"', " ]", "}", "```",
        "## The withheld 61 (run `7a317445`)", "# Withheld-cohort census", "## Group table",
        "| parser_id | cause | n |", "|---|---|---|", "| `bmo` | A | 3 |",
        "## Per-document list", "| sha16 | parser |", "|---|---|", f"| {SHA['D'][:16]} | bmo |",
        "```", SHA["E"], "```",
    ])
    failed = rc.census_failed_tokens(text)
    assert [s for s, _ in failed] == ["Family records", "Family records", "not_statements"]
    assert failed[0][1] == SHA["A"] and "[" in failed[1][1] and failed[2][1] == SHA["C"]
    assert rc.census_withheld_tokens(text) == [SHA["D"][:16]]   # found under the report's own sub-header


def test_rbc_table_and_welch_and_pinned():
    rbc = "\n".join([
        "**Pinned (4)** — x", "", "**Discovery (147)**, by `content_sha256`, with the run-of-record outcome class:", "",
        "| # | `content_sha256` | Old | New | Outcome |", "|---|---|---|---|---|",
        f"| 1 | `{SHA['A']}` | USD | CAD | validated |", f"| 2 | `{SHA['B']}` | USD | CAD | withheld |",
        "", "**Next**", f"| 3 | `{SHA['C']}` | USD | CAD | validated |",
    ])
    assert rc.rbc_expectations(rbc) == {SHA["A"]: "validated", SHA["B"]: "withheld"}
    assert rc.welch_population(f"# c\n{SHA['A']}\n{SHA['B'].lower()}\n") == [SHA["A"]]
    rows = [{"path": "P/a.pdf", "sha256": SHA["A"].lower()}, {"path": "P/b.pdf", "sha256": SHA["B"]},
            {"path": "P/c.pdf", "sha256": SHA["C"]}]
    expected = rc.pinned_expectations(rows, {"P/b.pdf": "review"}, {"P/c.pdf": "refused"})
    assert expected == {SHA["A"]: "validated", SHA["B"]: "review", SHA["C"]: "failed"}


def test_batch7_namespace_is_the_ten_sections_only():
    w3 = "\n".join([
        "# §DECLINESD — batch 6", f"| `{SHA['A'][:8]}` | validated |",
        "# §DECLINESE — batch 7", f"moved `{SHA['B'][:8]}` and {SHA['C']}",
        "# §COREISS2 — batch 8", f"`{SHA['D'][:8]}`",
    ])
    assert rc.batch7_named_shas(w3) == {SHA["B"][:8], SHA["C"][:8]}


def test_resolve_exact_prefix_redacted_ambiguous():
    shas = [SHA["A"], SHA["B"], "AB" + SHA["C"][2:], "AB" + SHA["D"][2:]]
    assert rc.resolve(SHA["A"], shas).status == "exact"
    assert rc.resolve(SHA["B"][:16], shas).sha == SHA["B"]
    red = f"{SHA['A'][:24]}[9-digit reference redacted]{SHA['A'][-24:]}"
    assert rc.resolve(red, shas) == rc.Resolution(SHA["A"], "redacted")
    assert rc.resolve("AB", shas).status == "ambiguous"
    assert rc.resolve(SHA["E"], shas).status == "unmatched"


# ---- gates ------------------------------------------------------------------

def test_exact_reproduction_is_accepted(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "native")})
    report = _check(run, pinned={SHA["A"]: "validated"}, census_failed=[("f", SHA["C"])],
                    census_withheld=[SHA["B"][:16]])
    assert report.g3_ok and not report.discrepancies
    assert report.verdict()[:2] == ("ACCEPT", 0)
    assert report.matched == {"O1-pinned-copy": 1, "O2-census-failed": 1, "O3-census-withheld": 1}


def test_native_discrepancy_is_a_stop(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "native")})
    report = _check(run, rbc={SHA["C"]: "validated"})   # record says validated, run says failed
    assert [d.kind for d in report.discrepancies] == ["STOP"]
    verdict, code, why = report.verdict()
    assert (verdict, code) == ("REJECT", 1) and "STOP" in why


def test_non_native_discrepancy_is_drift_candidate(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "local_tesseract")})
    report = _check(run, rbc={SHA["C"]: "validated"})
    assert [d.kind for d in report.discrepancies] == ["DRIFT"]
    assert report.non_native_total == 1 and report.non_native_in_oracle == 1
    assert report.verdict()[:2] == ("REJECT-DRIFT-CANDIDATE", 2)


def test_aggregate_delta_unbounded_by_non_native_population_is_a_plain_reject(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("validated", "native"),
                              SHA["C"]: ("failed", "native")})   # withheld 0 / validated 2
    report = _check(run)
    assert report.aggregate_deltas() == {"outcome.validated": 1, "outcome.withheld": -1}
    assert report.verdict()[:2] == ("REJECT", 1)


def test_named_batch7_improvement_is_explained_but_movement_down_is_not(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "native")})
    report = _check(run, census_failed=[("f", SHA["A"])], census_withheld=[SHA["C"][:16]],
                    batch7_named={SHA["A"][:8], SHA["C"][:8]})
    assert [s for s, *_ in report.explained] == [SHA["A"]]          # failed -> validated, named: explained
    assert [(d.sha, d.kind) for d in report.discrepancies] == [(SHA["C"], "STOP")]  # withheld -> failed: never


def test_explained_cap_is_enforced(tmp_path, small_record, monkeypatch):
    monkeypatch.setitem(rc.RECORD, "explained_improvements_cap", 0)
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "native")})
    report = _check(run, census_failed=[("f", SHA["A"])], batch7_named={SHA["A"][:8]})
    assert not report.explained and report.stops


def test_oracle_document_absent_from_the_run_rejects(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "native")})
    report = _check(run, welch=[SHA["D"]])
    assert [d.kind for d in report.discrepancies] == ["ABSENT"]
    assert report.verdict()[:2] == ("REJECT", 1)


def test_registration_count_and_mode_are_gated(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "native")}, registration_count=81, mode="digital")
    report = _check(run)
    failed = {name for name, _, _, ok in report.g3 if not ok}
    assert failed == {"registration_count", "mode"}
    assert report.verdict()[:2] == ("REJECT", 1)


def test_render_names_documents_by_sha16_only(tmp_path, small_record):
    run = _run_dir(tmp_path, {SHA["A"]: ("validated", "native"), SHA["B"]: ("withheld", "native"),
                              SHA["C"]: ("failed", "local_tesseract")})
    report = _check(run, rbc={SHA["C"]: "validated"})
    text = rc.render(report, run_dir="r")
    assert SHA["C"][:16] in text and SHA["C"] not in text and ".pdf" not in text
    assert "REJECT-DRIFT-CANDIDATE" in text
