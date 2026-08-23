"""Which LEAVES moved inside a document's analysis payload, and nothing else.

W3 §WITHHELDGRIDS's own instrument, committed because it produces a headline
number. `tools/regfp_zero_movement_sweep.py` answers *did this document move*
and names the TOP-LEVEL fields that differ; a card that moves a field on
purpose owes the next question — *what inside it moved* — and owes it without
printing a single figure out of a document.

    python -m tools.withheldgrids_leaf_diff --shas <file> \
        --data-dir <checkout>/webapp_data --baseline-settings-key <64 hex>

READ-ONLY, by the same rules as the sweep it complements: the `webapp_data`
sqlite index is never opened, OCR and analysis payloads are reached by DIRECT
file path, every capability partition is enumerated and the artifact chosen is
the one whose reconstruction resolves the run's own stored analysis payload.
`parse_mode="deterministic"` cannot reach the extraction branch, so it makes no
model call and costs $0.00.

WHAT IT PRINTS, and what it deliberately does not. For each document, the dotted
path of every differing leaf and a CHANGE CLASS for it:

* ``added`` / ``removed`` — the leaf exists on one side only;
* ``type`` — the leaf changed JSON type;
* ``value`` — both sides have a value of the same type and they differ.

No value, on either side, ever reaches the output — not the old one, not the
new one, not a delta between them. A leaf PATH is our own schema; a leaf VALUE
is the customer's money (PRIVACY, batch-7 standing rule). List elements are
addressed by index, so `statement.transactions.7.running_balance` is a path and
tells a reviewer exactly which reading moved without telling them what it read.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter
from pathlib import Path


def _normalised(payload: object) -> object:
    """Both sides through JSON before anything is compared.

    The stored baseline has already been through `json.dumps`/`json.loads`; a
    freshly computed payload has not, so a field the schema builds as a TUPLE
    is a tuple on one side and a list on the other. Comparing them raw reports
    every such field as moved on every document — which is exactly the false
    positive this instrument exists to rule out, and it was caught by
    disagreeing with `regfp_zero_movement_sweep`, whose own comparison is
    `canonical(before) == canonical(after)` and is therefore immune.
    """
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def _leaves(node: object, prefix: str = "") -> dict[str, object]:
    """Flatten a JSON payload to {dotted path: scalar}."""
    out: dict[str, object] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            out.update(_leaves(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            out.update(_leaves(value, f"{prefix}.{index}"))
        if not node:
            out[prefix] = "[]"
    else:
        out[prefix] = node
    return out


def _classify(before: dict[str, object], after: dict[str, object]) -> list[tuple[str, str]]:
    changes: list[tuple[str, str]] = []
    for path in sorted(set(before) | set(after)):
        if path not in after:
            changes.append((path, "removed"))
        elif path not in before:
            changes.append((path, "added"))
        elif type(before[path]) is not type(after[path]):
            changes.append((path, "type"))
        elif before[path] != after[path]:
            changes.append((path, "value"))
    return changes


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shas", required=True, help="file of content_sha256, one per line")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--baseline-settings-key", required=True)
    ap.add_argument("--paths-only", action="store_true",
                    help="print the union of differing paths and their counts")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS,
        STAGE_OCR,
        analysis_input_sha,
        cache_key,
        ocr_settings_key,
    )

    root = Path(args.data_dir) / "artifacts"
    baseline = args.baseline_settings_key
    ocr_keys = [
        ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
        for f, l, v in itertools.product((False, True), repeat=3)
    ]
    shas = [
        line.strip().upper()
        for line in Path(args.shas).read_text(encoding="utf-8").split()
        if line.strip()
    ]

    union: Counter[str] = Counter()
    compared = identical = 0
    for sha in shas:
        candidates: list[tuple[str, list[str]]] = []
        for key in ocr_keys:
            composed = cache_key(STAGE_OCR, sha, key)
            path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            document = (payload.get("artifact") or {}).get("document")
            if not isinstance(document, dict):
                continue
            pages = [str(page) for page in (document.get("pages") or [])]
            candidates.append((
                StatementMarkdown(
                    source_file="leafdiff.pdf",
                    model=str(document.get("model") or ""),
                    pages=pages,
                ).to_markdown(),
                pages,
            ))
        if not candidates:
            print(f"{sha[:16]} no_ocr_artifact")
            continue

        before = None
        markdown, pages = candidates[0]
        for candidate_markdown, candidate_pages in candidates:
            composed = cache_key(
                STAGE_ANALYSIS,
                analysis_input_sha(candidate_markdown, candidate_pages),
                baseline,
            )
            stored = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
            if not stored.exists():
                continue
            try:
                before = json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
            except (OSError, ValueError, KeyError):
                continue
            markdown, pages = candidate_markdown, candidate_pages
            break
        if before is None:
            print(f"{sha[:16]} no_baseline_payload")
            continue

        try:
            after = report_to_dict(
                analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
            )
        except Exception as exc:  # noqa: BLE001 - a refusal is an answer
            print(f"{sha[:16]} payload_now_raises {type(exc).__name__}")
            continue

        compared += 1
        changes = _classify(
            _leaves(_normalised(before)), _leaves(_normalised(after))
        )
        if not changes:
            identical += 1
            print(f"{sha[:16]} identical")
            continue
        union.update(path for path, _ in changes)
        print(f"{sha[:16]} moved leaves={len(changes)}")
        if not args.paths_only:
            for path, kind in changes:
                print(f"    {kind:8s} {path}")

    print(f"\ncompared={compared} identical={identical} moved={compared - identical}")
    print("union of differing leaf paths:")
    for path, count in union.most_common():
        print(f"  {count:4d}  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
