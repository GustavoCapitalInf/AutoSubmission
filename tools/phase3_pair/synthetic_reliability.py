"""Measure the visual pair on fabricated statements with known truth (tools/phase3_pair/synthetic_statements.py).

    python -m tools.phase3_pair.synthetic_reliability --synthetic-root <folder> --output-dir <private folder>
        [--replay-from <an earlier output folder>]

Every statement is read with data_scope="synthetic" (no customer data, no customer fence), analysed when the
gate admits it, and compared with its truth: transactions matched on (date, amount, direction), descriptions,
beginning and ending balance, totals. The one number that matters most is ``admitted_wrong``: statements the
pipeline admitted whose reading does not equal the truth. A statement held with reasons is a lost admission,
not an error. The report also records every confidence score, so the score can be checked against the truth.

With --replay-from, the models' recorded answers from that earlier run are reused and the current merge, gate
and analysis code judges them, with zero model calls (tools/phase3_pair/replay_judgment.py): a statement the
current code would have sent a model anything new is recorded as failed with ReplayMiss, never read live.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _key(date, amount, direction):
    return (str(date), abs(Decimal(str(amount))).quantize(Decimal("0.01")), direction)


def compare(truth: dict, statement: dict | None) -> dict:
    """Truth against an admitted statement (vlm Statement dump): counts and flags."""
    if statement is None:
        return {}
    truth_rows = truth["transactions"]
    rows = statement.get("transactions") or []
    direction = lambda row: row.get("direction") or ("credit" if Decimal(str(row["amount"])) > 0 else "debit")
    wanted = Counter(_key(t["date"], t["amount"], t["direction"]) for t in truth_rows)
    got = Counter(_key(r["date"], r["amount"], direction(r)) for r in rows)
    buckets = {}
    for t in truth_rows:
        buckets.setdefault(_key(t["date"], t["amount"], t["direction"]), []).append(t["description"])
    exact = spaced = 0
    for r in rows:
        pool = buckets.get(_key(r["date"], r["amount"], direction(r)))
        if pool:
            theirs = pool.pop(0)
            exact += r.get("description") == theirs
            spaced += " ".join(str(r.get("description")).split()) == " ".join(theirs.split())
    same = lambda field: (statement.get(field) is not None and truth.get(field) is not None
                          and Decimal(str(statement[field])) == Decimal(str(truth[field])))
    result = {"rows_truth": len(truth_rows), "rows_read": len(rows), "rows_matched": sum((wanted & got).values()),
              "rows_only_read": sum((got - wanted).values()), "rows_only_truth": sum((wanted - got).values()),
              "descriptions_exact": exact, "descriptions_whitespace_equal": spaced,
              "beginning_ok": same("beginning_balance"), "ending_ok": same("ending_balance"),
              "totals_ok": same("stated_total_credits") and same("stated_total_debits"),
              "period_ok": statement.get("period_start") == truth["period_start"]
              and statement.get("period_end") == truth["period_end"]}
    result["ledger_exact"] = (result["rows_matched"] == len(truth_rows) == len(rows)
                              and result["beginning_ok"] and result["ending_ok"])
    return result


def recorded_manifests(evidence: Path) -> dict[str, dict]:
    """PDF sha256 -> the pipeline manifest an earlier run read that document under (from its receipt)."""
    from tools.phase3_pair.replay_judgment import _blob

    manifests = {}
    for index in evidence.glob("*.json"):
        audit = json.loads(index.read_text(encoding="utf-8"))["document"]["visual_pair"]
        receipt = json.loads(_blob(evidence, audit["receipt_sha256"]))
        manifests[receipt["pdf_sha256"]] = receipt["manifest"]
    return manifests


def run(args) -> dict:
    from ocr.visual_pair_config import load_visual_pair_settings
    from vlm.pair import extract_visual_pair
    from vlm.pair_adapter import VisualPairAdmissionError, analyze_visual_pair

    root = args.synthetic_root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    settings = load_visual_pair_settings()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    holder = replay = None
    if getattr(args, "replay_from", None) is not None:
        import shutil
        from tools.phase3_pair.replay_judgment import install

        if (output / "evidence").exists():
            raise SystemExit("replay_output_already_has_evidence: use a fresh --output-dir")
        shutil.copytree(args.replay_from / "evidence", output / "evidence")
        recorded = recorded_manifests(output / "evidence")
        replay = {"replayed_from": str(args.replay_from.name), "model_calls": 0, "hits": 0, "misses": 0}
        holder = install(None, replay)
    results = []
    for item in manifest["files"]:
        pdf = root / item["path"]
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != item["sha256"]:
            raise SystemExit(f"fixture changed: {item['path']}")
        if holder is not None:
            holder["manifest"] = recorded.get(item["sha256"])
        truth = json.loads(pdf.with_suffix(".truth.json").read_text(encoding="utf-8"))
        entry = {"id": truth["id"], "layout": truth["layout"], "expect_admitted": truth["expect_admitted"]}
        try:
            doc = extract_visual_pair(pdf, settings=settings, evidence_dir=output / "evidence", data_scope="synthetic")
        except Exception as exc:  # a failed read is recorded, never retried silently
            entry.update(status="extraction_failed", error_type=type(exc).__name__)
            results.append(entry)
            print(json.dumps(entry), flush=True)
            continue
        pair = doc.visual_pair
        confidence = pair["confidence"]
        entry.update(pages=len(doc.pages), admitted=pair["gate"]["admitted"], reasons=pair["gate"]["reasons"],
                     score=confidence.get("score"), band=confidence.get("band"),
                     components=confidence.get("components"), row_states=confidence.get("counts"),
                     echo_pages=pair.get("ledger_echo_pages"), summary_box=pair.get("summary_box"))
        entry["status"] = "gate_refused"
        if pair["gate"]["admitted"]:
            try:
                report = analyze_visual_pair(doc, review_policy="admit_gated")
                statement = report.accounts[0].statement.model_dump()
                entry["status"] = "analysis_completed"
                entry["comparison"] = compare(truth, statement)
            except VisualPairAdmissionError as exc:
                entry.update(status="analysis_refused", refusal=str(exc))
                entry["comparison"] = compare(truth, pair.get("statement"))
        (output / f"{truth['id']}.result.json").write_text(json.dumps(entry, indent=1, default=str), encoding="utf-8")
        results.append(entry)
        print(json.dumps({key: entry.get(key) for key in ("id", "status", "admitted", "reasons", "score", "band")}),
              flush=True)
    admitted = [r for r in results if r.get("status") == "analysis_completed"]
    summary = {
        "statements": len(results),
        "admitted": len(admitted),
        "admitted_exact": sum(bool(r.get("comparison", {}).get("ledger_exact")) for r in admitted),
        "admitted_wrong": [r["id"] for r in admitted if not r.get("comparison", {}).get("ledger_exact")],
        "held": [r["id"] for r in results if r.get("status") in ("gate_refused", "analysis_refused")],
        "negative_controls_held": all(r.get("status") != "analysis_completed"
                                      for r in results if not r["expect_admitted"]),
        "failed": [r["id"] for r in results if r.get("status") == "extraction_failed"],
        "results": results,
    }
    if replay is not None:
        summary["replay"] = replay
    (output / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--synthetic-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replay-from", type=Path, default=None)
    summary = run(parser.parse_args(argv))
    print(json.dumps({key: summary[key] for key in ("statements", "admitted", "admitted_exact", "admitted_wrong",
                                                    "held", "negative_controls_held", "failed", "replay")
                      if key in summary}))
    return 0 if not summary.get("replay", {}).get("misses") else 3


if __name__ == "__main__":
    raise SystemExit(main())
