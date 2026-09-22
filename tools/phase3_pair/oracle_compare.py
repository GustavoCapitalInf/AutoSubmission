"""Compare a visual-pair analysis against the production deterministic analysis of the SAME statement.

For statements the deterministic reader already validates, its payload is an exact, reconciled answer key:
every transaction, every anchor, every metric. That is a stronger reference than any model-written or
hand-counted one, and it measures the whole path end to end (reading, merge, gate, analysis).

    python -m tools.phase3_pair.oracle_compare --visual <J01-analysis.private.json> \
        --deterministic <J01.json> [--detail-out <private path>]
    python -m tools.phase3_pair.oracle_compare --pdf <statement.pdf> --visual <...> [--detail-out ...]

--pdf runs the deterministic reader in-process instead of reading a saved payload.

Standard output carries field names, counts and match flags only, never values, so it is safe to show in a
hosted session. --detail-out writes the value-level diff and must point outside the repository checkout.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

STATEMENT_FIELDS = ("period_start", "period_end", "beginning_balance", "ending_balance", "currency",
                    "currency_source", "stated_total_credits", "stated_total_debits",
                    "stated_credit_count", "stated_debit_count")
TOLERANCE = 0.005


def deterministic_payload(pdf: Path) -> dict:
    """The production path, exactly as the web app's deterministic mode reads a text-layer statement."""
    from analysis.pipeline import analyze_document
    from analysis.serialization import document_report_to_dict
    from ocr.pipeline import parse_statement

    doc = parse_statement(pdf.read_bytes(), source_file=pdf.name, force_ocr=False,
                          allow_local_ocr=False, allow_visual_ocr=False)
    if doc is None:
        raise SystemExit("deterministic_text_intake_refused")
    report = analyze_document(doc.to_markdown(), parse_mode="deterministic", sheets=doc.pages)
    return document_report_to_dict(report)


def accounts(payload: dict) -> list[dict]:
    return payload["accounts"] if isinstance(payload, dict) and "accounts" in payload else [payload]


def _equal(left, right) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if isinstance(left, float) and math.isnan(left):
            return isinstance(right, float) and math.isnan(right)
        return abs(float(left) - float(right)) <= TOLERANCE
    return left == right


def _scalar(value) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _signed(txn: dict) -> float:
    return round(float(txn["amount"]), 2)


def _row_key(txn: dict) -> tuple:
    return (txn.get("date"), _signed(txn), txn.get("direction"))


def compare_accounts(visual: dict, oracle: dict) -> tuple[dict, dict]:
    """(counts-only summary, value-level detail)."""
    summary: dict = {"statement": {}, "transactions": {}, "metrics": {}, "reconciliation": {}}
    detail: dict = {"statement": {}, "metrics": {}, "rows_only_in_visual": [], "rows_only_in_oracle": []}
    v_st, o_st = visual.get("statement", {}) or {}, oracle.get("statement", {}) or {}

    for field in STATEMENT_FIELDS:
        same = _equal(v_st.get(field), o_st.get(field))
        summary["statement"][field] = "match" if same else "differs"
        if not same:
            detail["statement"][field] = {"visual": v_st.get(field), "oracle": o_st.get(field)}

    v_rows, o_rows = v_st.get("transactions", []) or [], o_st.get("transactions", []) or []
    v_keys, o_keys = Counter(map(_row_key, v_rows)), Counter(map(_row_key, o_rows))
    matched = sum((v_keys & o_keys).values())
    summary["transactions"] = {"visual": len(v_rows), "oracle": len(o_rows),
                               "matched_on_date_amount_direction": matched,
                               "only_in_visual": sum((v_keys - o_keys).values()),
                               "only_in_oracle": sum((o_keys - v_keys).values())}
    detail["rows_only_in_visual"] = [list(key) for key in (v_keys - o_keys).elements()]
    detail["rows_only_in_oracle"] = [list(key) for key in (o_keys - v_keys).elements()]

    # Descriptions, paired within each (date, amount, direction) bucket in printed order.
    buckets: dict[tuple, list[str]] = {}
    for txn in o_rows:
        buckets.setdefault(_row_key(txn), []).append(txn.get("description") or "")
    exact = spaced = paired = 0
    for txn in v_rows:
        pool = buckets.get(_row_key(txn))
        if not pool:
            continue
        mine = txn.get("description") or ""
        theirs = pool.pop(0)
        paired += 1
        exact += mine == theirs
        spaced += " ".join(mine.split()) == " ".join(theirs.split())
    summary["transactions"]["descriptions_paired"] = paired
    summary["transactions"]["descriptions_byte_equal"] = exact
    summary["transactions"]["descriptions_whitespace_equal"] = spaced

    v_m, o_m = visual.get("metrics", {}) or {}, oracle.get("metrics", {}) or {}
    for name in sorted(set(v_m) | set(o_m)):
        left, right = v_m.get(name), o_m.get(name)
        if not (_scalar(left) and _scalar(right)):
            continue
        same = _equal(left, right)
        summary["metrics"][name] = "match" if same else "differs"
        if not same:
            detail["metrics"][name] = {"visual": left, "oracle": right}

    v_r, o_r = visual.get("reconciliation", {}) or {}, oracle.get("reconciliation", {}) or {}
    for name in ("ok", "summary_ok"):
        summary["reconciliation"][name] = {"visual": v_r.get(name), "oracle": o_r.get(name)}
    return summary, detail


def compare(visual_payload: dict, oracle_payload: dict) -> tuple[dict, dict]:
    v_accounts, o_accounts = accounts(visual_payload), accounts(oracle_payload)
    report = {"accounts": {"visual": len(v_accounts), "oracle": len(o_accounts)}, "per_account": []}
    details = []
    for v_acct, o_acct in zip(v_accounts, o_accounts):
        summary, detail = compare_accounts(v_acct, o_acct)
        report["per_account"].append(summary)
        details.append(detail)
    metrics = [s["metrics"] for s in report["per_account"]]
    report["metrics_compared"] = sum(len(m) for m in metrics)
    report["metrics_differing"] = sorted({name for m in metrics for name, flag in m.items() if flag == "differs"})
    report["statement_fields_differing"] = sorted({name for s in report["per_account"]
                                                   for name, flag in s["statement"].items() if flag == "differs"})
    return report, {"per_account": details}


def _outside_checkout(path: Path) -> Path:
    from ocr.private_artifacts import CHECKOUT_ROOT
    resolved = path.resolve()
    if resolved == CHECKOUT_ROOT or CHECKOUT_ROOT in resolved.parents:
        raise SystemExit("detail_out_inside_checkout")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--visual", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--deterministic", type=Path)
    source.add_argument("--pdf", type=Path)
    parser.add_argument("--detail-out", type=Path)
    args = parser.parse_args(argv)

    visual = json.loads(args.visual.read_text(encoding="utf-8"))
    oracle = (json.loads(args.deterministic.read_text(encoding="utf-8")) if args.deterministic
              else deterministic_payload(args.pdf))
    report, detail = compare(visual, oracle)
    if args.detail_out:
        target = _outside_checkout(args.detail_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(detail, indent=1, default=str), encoding="utf-8")
    json.dump(report, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
