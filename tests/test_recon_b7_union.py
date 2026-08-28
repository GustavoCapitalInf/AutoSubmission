"""tools/recon_b7_union.py — a full run plus a scoped re-run compose into one
run view; only the re-run's shas change, and every change is named."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import recon_b7_union as ru

SHA = {name: (name * 64)[:64].upper() for name in "ABC"}
FIELDS = ["relative_path", "folder_label", "content_sha256", "source_path", "parser_id",
          "outcome_class", "outcome_reason"]


def _run(tmp_path: Path, name: str, docs: dict[str, tuple[str, str, str, str]], *, summary=None) -> Path:
    """docs: sha -> (outcome_class, outcome_reason, parser_id, source_path)."""
    run = tmp_path / name
    run.mkdir()
    with (run / "telemetry.jsonl").open("w", encoding="utf-8") as handle:
        for sha, (cls, reason, parser, path) in docs.items():
            handle.write(json.dumps({"run_id": name, "document": {"content_sha256": sha},
                                     "outcome": {"class": cls, "reason": reason},
                                     "dispatch": {"parser_id": parser, "registration_count": 75, "source": "live"},
                                     "source": {"path": path}}) + "\n")
    with (run / "rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for sha, (cls, reason, parser, path) in docs.items():
            writer.writerow({"relative_path": f"x/{sha[:4]}.pdf", "folder_label": "x", "content_sha256": sha,
                             "source_path": path, "parser_id": parser, "outcome_class": cls, "outcome_reason": reason})
    (run / "summary.json").write_text(json.dumps(summary or {
        "mode": "scanned", "inventory": {"pdfs": 3}, "dedup": {"duplicate": 0},
        "reasons": {"old": 1}, "deferred_reasons": {}}), encoding="utf-8")
    return run


def test_union_substitutes_only_the_subset_and_names_every_change(tmp_path):
    full = _run(tmp_path, "A", {
        SHA["A"]: ("validated", "approved", "atb", "native"),
        SHA["B"]: ("failed", "no_parser_matched", "", "local_tesseract"),
        SHA["C"]: ("deferred", "deferred_visual_ocr", "", "none"),
    })
    subset = _run(tmp_path, "B", {
        SHA["B"]: ("withheld", "withheld_adb", "td_us", "local_tesseract"),   # moved
        SHA["C"]: ("deferred", "deferred_visual_ocr", "", "none"),           # identical
    })
    out = tmp_path / "U"
    result = ru.compose(full, subset, out, label="t")
    records = {json.loads(l)["document"]["content_sha256"]: json.loads(l)
               for l in (out / "telemetry.jsonl").read_text().splitlines()}
    assert records[SHA["A"]]["run_id"] == "A"          # untouched native record
    assert records[SHA["B"]]["run_id"] == "B"          # replaced by the re-run
    assert records[SHA["C"]]["run_id"] == "B"
    rows = {r["content_sha256"]: r for r in csv.DictReader(open(out / "rows.csv", encoding="utf-8"))}
    assert rows[SHA["B"]]["outcome_class"] == "withheld" and rows[SHA["A"]]["outcome_class"] == "validated"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["inventory"] == {"pdfs": 3} and summary["dedup"] == {"duplicate": 0}   # whole-corpus facts kept
    assert summary["reasons"] == {"approved": 1, "withheld_adb": 1, "deferred_visual_ocr": 1}
    assert summary["deferred_reasons"] == {"deferred_visual_ocr": 1}
    assert summary["union"]["subset_shas"] == 2 and summary["union"]["records_replaced"] == 2
    assert result["changed"] == 1 and result["diffs"][0][0] == SHA["B"]
    diff = (out / "diff_A_B.md").read_text()
    assert SHA["B"][:16] in diff and "failed | withheld" in diff and ".pdf" not in diff
