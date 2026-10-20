"""l1s1_seam_probe.py — RULE S at the PIPELINE SEAM, proved ACROSS TREES.

    # at the BASE tree (the document entry point does not exist there yet)
    PYTHONHASHSEED=0 python -m tools.l1s1_seam_probe --run <run> --data-dir <cold cache> \
        --capture <private>/base.json
    # at the S1 tree
    PYTHONHASHSEED=0 python -m tools.l1s1_seam_probe --run <run> --data-dir <cold cache> \
        --capture <private>/s1.json --baseline <private>/base.json

WHY THIS EXISTS AND WHAT IT ANSWERS THAT THE DESIGN'S PROBE DOES NOT
--------------------------------------------------------------------
The design measured RULE S by serialising ONE in-memory `Report` two ways
inside ONE process: `report_to_dict(report)` against a wrapper that returns
`report_to_dict(doc.accounts[0])` where `doc.accounts[0] is report`. That
equality is by construction — it says the serialiser is deterministic over one
object, which is worth knowing and is not the claim S1 has to make.

The claim S1 has to make is about the PIPELINE: text in at one tree, text in at
another, and the published bytes the same. So this instrument captures, at a
tree, one digest per document, and compares two captures taken at DIFFERENT
trees:

    base capture   `report_to_dict(analyze_markdown(text))`
    S1 capture     `document_report_to_dict(analyze_document(text))`
                   and `report_to_dict(analyze_markdown(text))` alongside

Three properties are reported separately, because they fail separately:

    RULE S at the seam   base payload == S1 DOCUMENT-seam payload, as BYTES
    the account seam     base payload == S1 legacy payload, as BYTES
    the integrity block  the published flag LIST, in published order, equal —
                         reported on its own because the two ways an
                         implementer assembles the document/account scope split
                         fail here and nowhere else: dropping the document-scope
                         flags from the account block, and concatenating the two
                         scopes instead of preserving published order

DETERMINISM. `analysis/serialization.py` publishes two serialised SETS whose
list order follows the process's string hash seed, so a byte comparison across
processes is only meaningful with the seed pinned. The probe REFUSES to capture
without `PYTHONHASHSEED` set (`--allow-unpinned-hash-seed` overrides it and is
never used for a reported number), and it records a second, seed-independent
digest with all-scalar lists sorted so a reader can tell a real byte movement
from a set-order one.

PRIVACY. Nothing this instrument writes or prints comes from a document's
content: content sha16s, registration ids, counts, top-level KEY NAMES,
integrity FLAG NAMES (a closed vocabulary of the platform's own), outcome
classes, and sha256 digests. No value, name, number, amount or date.

READ-ONLY over the run of record and the cold cache. No OCR, no model, $0.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
from pathlib import Path


def _tree_on_path(tree: Path) -> None:
    sys.path.insert(0, str(tree))


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sorted_scalar_lists(value):
    """The payload with every all-scalar list sorted.

    The seed-independent view: `tools/cohort_replay.py::flatten` compares those
    lists as a multiset for the same reason, so a digest over this view moves
    only when something other than a serialised set's order moved.
    """
    if isinstance(value, dict):
        return {key: _sorted_scalar_lists(item) for key, item in value.items()}
    if isinstance(value, list):
        if value and all(not isinstance(item, (dict, list)) for item in value):
            return sorted(value, key=lambda item: (type(item).__name__, str(item)))
        return [_sorted_scalar_lists(item) for item in value]
    return value


def record_for(payload: dict) -> dict:
    """The comparable projection of one published payload."""
    return {
        "sha256": digest(canonical(payload)),
        "stable_sha256": digest(canonical(_sorted_scalar_lists(payload))),
        "keys": sorted(payload),
        "key_digests": {key: digest(canonical({key: value}))
                        for key, value in payload.items()},
    }


def probe_one(sha: str, parser_id: str, cache) -> dict:
    """One document, analysed ONCE, through whichever seams this tree has."""
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from telemetry.record import classify_outcome

    try:
        from analysis.pipeline import analyze_document, split_integrity_flags
        from analysis.serialization import document_report_to_dict
    except ImportError:  # the BASE tree: the document entry point is this card
        analyze_document = None
        split_integrity_flags = None
        document_report_to_dict = None

    out: dict = {"sha16": sha[:16], "parser_id": parser_id, "analysed": False}
    markdown, pages = cache.text(sha)
    if markdown is None:
        out["error"] = "no-cached-text"
        return out
    try:
        if analyze_document is not None:
            document = analyze_document(markdown, parse_mode="deterministic", sheets=pages)
            report = document.accounts[0]
            out["seam"] = "document"
            out["account_count"] = len(document.accounts)
            out["document"] = record_for(document_report_to_dict(document))
            out["document_scope_flags"] = document.document_scope_flags()
        else:
            report = analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
            out["seam"] = "legacy"
            out["account_count"] = 1
    except Exception as exc:  # the runner's own boundary: a refusal is data
        out["error"] = type(exc).__name__
        return out

    legacy = report_to_dict(report)
    out["analysed"] = True
    out["legacy"] = record_for(legacy)
    out["integrity_flags"] = list((legacy.get("integrity") or {}).get("flags") or [])
    out["outcome"] = list(classify_outcome(legacy))
    if split_integrity_flags is not None:
        scopes = split_integrity_flags(out["integrity_flags"])
        out["scope_split"] = {"document": scopes[0], "account": scopes[1]}
    return out


def compare(base: dict, s1: dict) -> dict:
    """Every count this instrument reports, computed in one place."""
    base_rows = {row["sha16"]: row for row in base["rows"]}
    s1_rows = {row["sha16"]: row for row in s1["rows"]}
    shared = sorted(set(base_rows) & set(s1_rows))
    result = collections.Counter()
    changed_keys: collections.Counter = collections.Counter()
    movers: list[dict] = []
    for sha16 in shared:
        before, after = base_rows[sha16], s1_rows[sha16]
        if not (before.get("analysed") and after.get("analysed")):
            result["not_analysed_at_one_tree"] += 1
            continue
        result["compared"] += 1
        document_seam = after.get("document") or after.get("legacy")
        if before["legacy"]["sha256"] == document_seam["sha256"]:
            result["rule_s_byte_identical"] += 1
        else:
            result["rule_s_moved"] += 1
            for key in set(before["legacy"]["key_digests"]) | set(document_seam["key_digests"]):
                if (before["legacy"]["key_digests"].get(key)
                        != document_seam["key_digests"].get(key)):
                    changed_keys[key] += 1
            movers.append({"sha16": sha16, "parser_id": after.get("parser_id", ""),
                           "seam": "document"})
        if before["legacy"]["stable_sha256"] == document_seam["stable_sha256"]:
            result["rule_s_stable_identical"] += 1
        if before["legacy"]["sha256"] == after["legacy"]["sha256"]:
            result["account_seam_byte_identical"] += 1
        else:
            result["account_seam_moved"] += 1
            movers.append({"sha16": sha16, "parser_id": after.get("parser_id", ""),
                           "seam": "legacy"})
        if before.get("integrity_flags") == after.get("integrity_flags"):
            result["integrity_flags_identical"] += 1
        else:
            result["integrity_flags_moved"] += 1
        if before.get("outcome") == after.get("outcome"):
            result["outcome_unchanged"] += 1
        else:
            result["outcome_moved"] += 1
        if after.get("account_count") == 1:
            result["one_account"] += 1
        if (after.get("document_scope_flags") or []):
            result["carries_document_scope_flags"] += 1
        if after.get("integrity_flags"):
            result["carries_any_flag"] += 1
    return {"shared": len(shared), "counts": dict(result),
            "changed_keys": dict(changed_keys), "movers": movers}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RULE S at the pipeline seam")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--tree", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="the tree to import production from (default: this file's)")
    parser.add_argument("--per-parser", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--baseline", type=Path,
                        help="a capture from another tree; compare against it")
    parser.add_argument("--label", default="")
    parser.add_argument("--allow-unpinned-hash-seed", action="store_true")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    seed = os.environ.get("PYTHONHASHSEED")
    if seed is None and not args.allow_unpinned_hash_seed:
        print("REFUSED: PYTHONHASHSEED is not set. Two payloads serialised in "
              "two processes differ in the order of the payload's serialised "
              "SETS, so a byte comparison across trees is not meaningful "
              "without it.")
        return 4

    _tree_on_path(args.tree)
    from tools.cohort_replay import ColdCache, load_baseline_rows
    from tools.l1_design_payload_probe import select_cohort

    rows = load_baseline_rows(args.run)
    cohort = select_cohort(rows, args.per_parser, None, args.limit,
                           include_unvalidated=True)
    cache = ColdCache(args.data_dir)
    probes = [probe_one(sha, (rows.get(sha, {}).get("parser_id") or ""), cache)
              for sha in cohort]
    analysed = [p for p in probes if p.get("analysed")]
    registrations = sorted({p["parser_id"] for p in analysed if p["parser_id"]})
    capture = {
        "label": args.label,
        "tree": str(args.tree),
        "hash_seed": seed,
        "per_parser": args.per_parser,
        "documents": len(cohort),
        "analysed": len(analysed),
        "registrations": len(registrations),
        "seam": (analysed[0].get("seam") if analysed else None),
        "rows": probes,
    }
    args.capture.write_text(json.dumps(capture, indent=1), encoding="utf-8")

    print(f"# L1-S1 — RULE S at the pipeline seam ({args.label or 'capture'})")
    print()
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents in the cohort | {len(cohort)} |")
    print(f"| ... analysed | {len(analysed)} |")
    print(f"| distinct registrations covered | {len(registrations)} |")
    print(f"| seam exercised at this tree | `{capture['seam']}` |")
    print(f"| PYTHONHASHSEED | `{seed}` |")
    print()

    if args.baseline is None:
        return 0

    base = json.loads(args.baseline.read_text(encoding="utf-8"))
    verdict = compare(base, capture)
    counts = verdict["counts"]
    print(f"## Against the baseline capture (`{base.get('label') or base.get('tree')}`, "
          f"seam `{base.get('seam')}`)")
    print()
    print("| property | documents |")
    print("|---|---:|")
    print(f"| shared cohort | {verdict['shared']} |")
    print(f"| compared (analysed at both trees) | {counts.get('compared', 0)} |")
    print(f"| **RULE S at the seam — payload byte-identical** | "
          f"**{counts.get('rule_s_byte_identical', 0)}** |")
    print(f"| ... payload moved | {counts.get('rule_s_moved', 0)} |")
    print(f"| ... identical ignoring serialised-set order | "
          f"{counts.get('rule_s_stable_identical', 0)} |")
    print(f"| the account seam — payload byte-identical | "
          f"{counts.get('account_seam_byte_identical', 0)} |")
    print(f"| ... payload moved | {counts.get('account_seam_moved', 0)} |")
    print(f"| **integrity flags, published list and ORDER, identical** | "
          f"**{counts.get('integrity_flags_identical', 0)}** |")
    print(f"| ... moved | {counts.get('integrity_flags_moved', 0)} |")
    print(f"| ladder outcome unchanged | {counts.get('outcome_unchanged', 0)} |")
    print(f"| ... moved | {counts.get('outcome_moved', 0)} |")
    print(f"| documents publishing exactly one account | {counts.get('one_account', 0)} |")
    print(f"| documents carrying any integrity flag | {counts.get('carries_any_flag', 0)} |")
    print(f"| ... of them carrying a DOCUMENT-scope flag | "
          f"{counts.get('carries_document_scope_flags', 0)} |")
    print()
    if verdict["changed_keys"]:
        print("## Top-level keys that moved (names only, never values)")
        print()
        for key, count in sorted(verdict["changed_keys"].items()):
            print(f"* `{key}` — {count} document(s)")
        print()
    if verdict["movers"]:
        print("## Movers (by content sha16 and seam)")
        print()
        for mover in verdict["movers"][:40]:
            print(f"* `{mover['sha16']}` `{mover['parser_id']}` — {mover['seam']}")
        print()
    moved = (counts.get("rule_s_moved", 0) + counts.get("account_seam_moved", 0)
             + counts.get("integrity_flags_moved", 0) + counts.get("outcome_moved", 0))
    print(f"MOVED_TOTAL={moved}")
    return 0 if moved == 0 else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
