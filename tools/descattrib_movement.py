"""Leaf-diff one population's published analyses: descriptions apart, everything else together.

W3 §DESCATTRIB's movement instrument. The archive sweep
(`tools.regfp_zero_movement_sweep`) reports which top-level FIELDS moved and
nothing more, which is the right contract for a sweep of 3,380 documents and
not enough for the card that moves a field on purpose. This tool answers the
two questions that card owes:

1. **with every `description` leaf masked, is the published payload byte-
   identical to what the run stored?** Amounts, dates, directions, counts,
   totals, the grid, the ADB, the verdict, the flags, the classifier's own
   output — all of it is in that comparison, and any of it moving is a
   finding, not a footnote;
2. **which description leaves moved, and how?** Reported as PATHS and as row
   CLASSES — `shortened`, `lengthened`, `replaced` — with the before/after
   LENGTHS. Never the text: a description is the statement's own printing and
   a report is not the place for it.

    python -m tools.descattrib_movement \
        --rows <reports>/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> \
        --sha <content_sha256> [--sha ...] [--out movement.json]

READ-ONLY and $0, by the same construction as the sweep: the sqlite index is
never opened, artifacts are reached by direct path, the OCR artifact is the one
whose reconstruction resolves the run's own stored payload, and
`parse_mode="deterministic"` cannot reach the extraction branch.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import time
from pathlib import Path

#: The leaf whose movement this card is FOR. Masked for the first comparison
#: and compared alone in the second, so neither hides the other.
DESCRIPTION_LEAF = "description"
MASK = "\x00masked\x00"
#: "this path is not in that payload at all", distinct from every leaf value.
ABSENT = "\x00absent\x00"


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def leaves(node: object, path: str = "") -> dict[str, object]:
    """Every scalar of a payload, by its path. Sequences are indexed.

    A tuple is a list here, deliberately: the stored artifact is JSON and a
    recompute is the in-memory object, so the same field arrives as `[...]`
    from one side and `(...)` from the other. Treating them apart would report
    every sequence in every payload as a mover and drown the finding this tool
    exists to make.
    """
    if isinstance(node, dict):
        out: dict[str, object] = {}
        for key, value in node.items():
            out.update(leaves(value, f"{path}.{key}" if path else str(key)))
        return out
    if isinstance(node, (list, tuple)):
        out = {}
        for index, value in enumerate(node):
            out.update(leaves(value, f"{path}[{index}]"))
        return out
    return {path: node}


def masked(payload: object) -> object:
    if isinstance(payload, dict):
        return {key: (MASK if key == DESCRIPTION_LEAF else masked(value))
                for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [masked(value) for value in payload]
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", required=True)
    parser.add_argument("--sha", action="append", default=[],
                        help="a content_sha256 of the named population; repeatable")
    parser.add_argument("--sha-file", type=Path, default=None,
                        help="a file of content_sha256, one per line")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )

    wanted = [sha.strip().upper() for sha in args.sha if sha.strip()]
    if args.sha_file is not None:
        wanted += [line.strip().upper()
                   for line in args.sha_file.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    if not wanted:
        raise SystemExit("no population named")

    baseline = args.baseline_settings_key.strip().upper()
    root = args.data_dir / "artifacts"
    ocr_keys = [ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
                for f, l, v in itertools.product((False, True), repeat=3)]

    outcome_by_sha: dict[str, str] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["content_sha256"]:
                outcome_by_sha.setdefault(row["content_sha256"], row["outcome_class"])

    documents = []
    totals = {"documents": 0, "rows": 0, "moved_descriptions": 0,
              "shortened": 0, "lengthened": 0, "replaced": 0,
              "other_movement": 0, "no_payload": 0}
    started = time.perf_counter()

    for sha in sorted(set(wanted)):
        candidates = []
        for key in ocr_keys:
            composed = cache_key(STAGE_OCR, sha, key)
            path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            document = (payload.get("artifact") or {}).get("document")
            if not isinstance(document, dict):
                continue
            pages = [str(page) for page in (document.get("pages") or [])]
            candidates.append((StatementMarkdown(
                source_file="movement.pdf", model=str(document.get("model") or ""),
                pages=pages).to_markdown(), pages))
        before = None
        markdown, pages = (candidates[0] if candidates else ("", []))
        for candidate_markdown, candidate_pages in candidates:
            composed = cache_key(STAGE_ANALYSIS,
                                 analysis_input_sha(candidate_markdown, candidate_pages),
                                 baseline)
            stored = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
            if not stored.exists():
                continue
            before = json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
            markdown, pages = candidate_markdown, candidate_pages
            break
        if before is None:
            totals["no_payload"] += 1
            documents.append({"content_sha256": sha, "verdict": "no_payload"})
            continue

        after = report_to_dict(
            analyze_markdown(markdown, parse_mode="deterministic", sheets=pages))
        totals["documents"] += 1

        before_masked = leaves(masked(before))
        after_masked = leaves(masked(after))
        elsewhere = sorted(
            path for path in set(before_masked) | set(after_masked)
            if canonical(before_masked.get(path, ABSENT))
            != canonical(after_masked.get(path, ABSENT))
        )
        before_leaves = {p: v for p, v in leaves(before).items()
                         if p.endswith("." + DESCRIPTION_LEAF) or p == DESCRIPTION_LEAF}
        after_leaves = {p: v for p, v in leaves(after).items()
                        if p.endswith("." + DESCRIPTION_LEAF) or p == DESCRIPTION_LEAF}
        moved = []
        for path in sorted(set(before_leaves) | set(after_leaves)):
            old, new = before_leaves.get(path), after_leaves.get(path)
            if old == new:
                continue
            if isinstance(old, str) and isinstance(new, str) and old.startswith(new):
                kind = "shortened"
            elif isinstance(old, str) and isinstance(new, str) and new.startswith(old):
                kind = "lengthened"
            else:
                kind = "replaced"
            totals[kind] += 1
            moved.append({"path": path, "class": kind,
                          "before_len": len(old) if isinstance(old, str) else None,
                          "after_len": len(new) if isinstance(new, str) else None})
        totals["rows"] += len(before_leaves)
        totals["moved_descriptions"] += len(moved)
        totals["other_movement"] += len(elsewhere)
        documents.append({
            "content_sha256": sha,
            "outcome_class": outcome_by_sha.get(sha),
            "description_leaves": len(before_leaves),
            "moved_descriptions": len(moved),
            "movement_elsewhere": elsewhere,
            "moved": moved,
        })

    report = {"seconds": round(time.perf_counter() - started, 1), **totals,
              "documents_detail": documents}
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(canonical({key: value for key, value in report.items()
                     if key != "documents_detail"}))
    for document in documents:
        print(canonical({key: value for key, value in document.items() if key != "moved"}))
    return 1 if totals["other_movement"] or totals["no_payload"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
