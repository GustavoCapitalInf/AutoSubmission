"""tools/train8_compare.py — the accounting quarantine: excluded from the
historical headline, positive movement reported separately, regressions never
excused, a full per-sha table for the quarantined set."""
from __future__ import annotations

import json
from pathlib import Path

from discovery.evidence import load_run
from tools import train8_compare as tc

SHA = {name: (name * 64)[:64].upper() for name in "ABCDEFGH"}


def _run(tmp_path: Path, name: str, docs: dict[str, tuple[str, str]]) -> Path:
    """docs: sha -> (outcome_class, parser_id)."""
    run = tmp_path / name
    run.mkdir()
    with (run / "telemetry.jsonl").open("w", encoding="utf-8") as handle:
        for sha, (cls, parser) in docs.items():
            handle.write(json.dumps({"run_id": name, "document": {"content_sha256": sha},
                                     "outcome": {"class": cls, "reason": "r"},
                                     "dispatch": {"parser_id": parser, "source": "live"},
                                     "source": {"path": "native"}}) + "\n")
    return run


def _quarantine(tmp_path: Path, shas) -> Path:
    path = tmp_path / "q.shas"
    path.write_text("# quarantine\n" + "\n".join(shas) + "\n", encoding="utf-8")
    return path


def test_partition_five_way_accounting_and_headline_exclusion(tmp_path):
    base = _run(tmp_path, "A", {
        SHA["A"]: ("failed", ""), SHA["B"]: ("validated", "x"),      # comparable: A improves, B regresses
        SHA["C"]: ("failed", ""), SHA["D"]: ("validated", "y"),      # quarantined: C improves, D regresses
        SHA["E"]: ("validated", "z"), SHA["F"]: ("deferred", ""),    # unchanged / unranked (quarantined)
    })
    cand = _run(tmp_path, "B", {
        SHA["A"]: ("validated", "x"), SHA["B"]: ("withheld", "x"),
        SHA["C"]: ("validated", "y"), SHA["D"]: ("review", "y"),
        SHA["E"]: ("validated", "z"), SHA["F"]: ("failed", ""),
    })
    q = tc.read_quarantine(_quarantine(tmp_path, [SHA["C"], SHA["D"], SHA["F"], SHA["G"]]))
    p = tc.partitioned(load_run(base), load_run(cand), q)
    assert (p["shared"], p["comparable_shas"], p["quarantined_shas"]) == (6, 3, 3)
    assert p["quarantine_absent"] == [SHA["G"]]
    assert dict(p["counts"]["comparable"]) == {"improved": 1, "regressed": 1, "unchanged": 1}
    assert dict(p["counts"]["quarantined"]) == {"improved": 1, "regressed": 1, "unranked": 1}
    # the historical-comparable validated delta removes the quarantine from BOTH sides
    assert p["validated"]["comparable"] == {"base": 2, "candidate": 2}
    assert p["validated"]["quarantined"] == {"base": 1, "candidate": 1}
    assert p["candidate_totals"]["validated"] == 3 and p["any_regression"]
    text = tc.render_partition(p, base_id="A", candidate_id="B")
    assert "2 → 2 = +0" in text                       # comparable headline, quarantined gain excluded
    assert "2,469" in text and "NOT the base" in text  # the historical figure is named only to be disclaimed
    assert SHA["C"][:16] in text and SHA["D"][:16] in text and SHA["F"][:16] in text   # full quarantined table
    assert ".pdf" not in text and SHA["C"] not in text                                   # sha16 only


def test_quarantined_regression_still_fails_the_run(tmp_path):
    base = _run(tmp_path, "A", {SHA["A"]: ("validated", "x"), SHA["D"]: ("validated", "y")})
    cand = _run(tmp_path, "B", {SHA["A"]: ("validated", "x"), SHA["D"]: ("failed", "")})
    q = _quarantine(tmp_path, [SHA["D"]])
    assert tc.main(["--base", str(base), "--candidate", str(cand), "--quarantine", str(q),
                    "--fail-on-regression"]) == 2
    assert tc.main(["--base", str(base), "--candidate", str(cand), "--quarantine", str(q)]) == 0


def test_no_regression_anywhere_exits_zero_and_quarantined_gain_is_separate(tmp_path, capsys):
    base = _run(tmp_path, "A", {SHA["A"]: ("failed", ""), SHA["D"]: ("failed", "")})
    cand = _run(tmp_path, "B", {SHA["A"]: ("validated", "x"), SHA["D"]: ("validated", "y")})
    q = _quarantine(tmp_path, [SHA["D"]])
    assert tc.main(["--base", str(base), "--candidate", str(cand), "--quarantine", str(q),
                    "--fail-on-regression"]) == 0
    out = capsys.readouterr().out
    assert "| (a)/(b) improved | **1** | 1 (reported separately, not counted) |" in out
    assert "0 → 1 = +1" in out
