"""Replay every archive document the run of record dispatches to a reader
#HYGIENE8 touched, BASE against BRANCH, in one process.

    python -m tools.hygiene8_family_replay \
        --rows <main>/discovery_reports/<run-id>/rows.csv \
        --data-dir <main>/webapp_data \
        --base 10cc722 --scratch <private> --out replay.json

THE CLAIM UNDER TEST. All three sub-cards on this branch are declared
NON-OUTCOME: QUEUE-SUPERVISOR is a worker-thread lifecycle change in
`webapp/app.py` that the analysis stack cannot see at all, EXTRACT-PROMPT edits
a prompt string the deterministic branch never reaches, and RAISE-PRIVACY-3
changes what four modules put in an exception MESSAGE and widens seven `except`
clauses. A declared non-outcome change earns its "0" by measurement, so this
replays the whole dispatched population and compares the published payload leaf
for leaf — outcome class, outcome reason, the integrity block, and every
transaction field.

THE POPULATION IS DERIVED, NOT TYPED. The card named five registrations; the
call graph names seven. `--print-population` shows the derivation:

* the registry gives every registration whose `parse` lives in a module this
  branch changed (`analysis/chase.py`, `analysis/columbia_bank.py`,
  `analysis/scotia.py`, `analysis/scanned_small_bank.py`);
* an AST call graph over each of those modules then asks which of those
  registrations' entry points actually REACH a changed function, so a
  registration that merely shares a file with one is not carried along;
* and the archive population is every document the run *dispatched* to one of
  the survivors — `parser_id` OR `attempted` OR `candidates` — because `parse`
  runs on a document it goes on to DECLINE exactly as it runs on one it claims,
  and a declining reader is where a raising conversion guard lives.

`analysis/date_tokens.py`'s widened handlers are tree-wide rather than
family-shaped and are NOT provable by this population; `tools.hygiene8_overflow_reach`
is their instrument.

READ-ONLY, $0. No artifact is written, the `webapp_data` sqlite index is never
opened, OCR text is reached by DIRECT file path over every capability partition
of `ocr_settings_key` (the resolution is `tools/regfp_zero_movement_sweep.py`'s,
whose docstring explains why the partition is proved rather than guessed), and
`parse_mode="deterministic"` cannot reach the extraction branch.

NOTHING THIS TOOL PRINTS QUOTES A DOCUMENT. A movement is reported as its
`content_sha256` plus the PATHS at which the payloads differ
(`transactions[7].amount`), which are source symbols. An exception is reported
as its class NAME and never its message — which is not a nicety here but the
point of the card: at base, three of these readers put the printed token INTO
the message, so printing messages would be the leak the branch closes.
"""
from __future__ import annotations

import argparse
import ast
import csv
import itertools
import json
import sys
import time
from pathlib import Path

#: Files this branch changed that hold, or are reached by, a parser entry point.
#: `analysis/date_tokens.py` is deliberately absent — see the module docstring.
CHANGED_PARSER_MODULES = {
    "analysis/chase.py": ["_money_required"],
    "analysis/columbia_bank.py": ["parsed_datetime"],
    "analysis/scotia.py": ["parsed_datetime"],
    "analysis/scanned_small_bank.py": ["_money", "_iso"],
}


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            function = sub.func
            if isinstance(function, ast.Name):
                names.add(function.id)
            elif isinstance(function, ast.Attribute):
                names.add(function.attr)
    return names


def reaches_a_changed_function(source: str, entry: str, targets: list[str]) -> list[str]:
    """The changed functions `entry` can reach in this module, transitively.

    Attribute calls are matched on the ATTRIBUTE name (`parsed_datetime` in
    `date_tokens.parsed_datetime`) so an imported target is seen however it was
    spelled. That over-approximates — a same-named method on some other object
    would count — and over-approximation is the right direction: it can only
    widen the replayed population, never shrink it below the truth.
    """
    tree = ast.parse(source)
    calls = {
        node.name: _called_names(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    found: list[str] = []
    seen: set[str] = set()
    stack = [entry]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for name in calls.get(current, ()):
            if name in targets and name not in found:
                found.append(name)
            if name in calls:
                stack.append(name)
    return sorted(found)


def derive_population(repo: Path) -> dict[str, dict[str, object]]:
    """{parser_id: {module, entry, reaches}} for every registration in reach."""
    from analysis import parser_registry_entries as _entries  # noqa: F401
    from analysis.parser_registry import registrations

    sources = {
        path: (repo / path).read_text(encoding="utf-8") for path in CHANGED_PARSER_MODULES
    }
    derived: dict[str, dict[str, object]] = {}
    for registration in registrations():
        module = getattr(registration.parse, "__module__", "")
        path = module.replace(".", "/") + ".py"
        if path not in CHANGED_PARSER_MODULES:
            continue
        reaches = reaches_a_changed_function(
            sources[path], registration.parse.__name__, CHANGED_PARSER_MODULES[path]
        )
        if not reaches:
            continue
        derived[registration.id] = {
            "module": module,
            "entry": registration.parse.__name__,
            "reaches": reaches,
        }
    return derived


def _dispatch_tokens(row: dict[str, str]) -> set[str]:
    tokens = {row.get("parser_id") or ""}
    for column in ("attempted", "candidates"):
        for token in (row.get(column) or "").replace(";", ",").split(","):
            token = token.strip().split(":")[0]
            if token:
                tokens.add(token)
    tokens.discard("")
    return tokens


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=Path, help="the run of record's rows.csv")
    parser.add_argument("--data-dir", type=Path, help="the webapp_data directory")
    parser.add_argument("--base", default="10cc722", help="the base revision")
    parser.add_argument("--scratch", type=Path, help="private scratch directory")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--print-population",
        action="store_true",
        help="print the derived registration set and the archive counts, then stop",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo))

    population = derive_population(repo)
    if args.print_population:
        print(json.dumps(population, indent=1, sort_keys=True))
        if args.rows is None:
            return 0

    if args.rows is None or args.data_dir is None or args.scratch is None:
        print("--rows, --data-dir and --scratch are required for a replay")
        return 2

    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown
    from telemetry.record import classify_outcome
    from tools.hygiene8_base_tree import leaf_diff, load_base_analysis
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    base = load_base_analysis(args.base, repo=repo, scratch=args.scratch)

    wanted = set(population)
    shas: dict[str, set[str]] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row.get("content_sha256")
            hit = _dispatch_tokens(row) & wanted
            if sha and hit:
                shas.setdefault(sha, set()).update(hit)
    ordered = sorted(shas)[args.start : args.end]

    if args.print_population:
        print(json.dumps({"dispatched_documents": len(shas)}, sort_keys=True))
        return 0

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]

    counts = {
        "documents": len(ordered),
        "replays": 0,
        "identical": 0,
        "moved": 0,
        "outcome_moved": 0,
        "raised_on_both": 0,
        "raise_class_moved": 0,
        "base_raised_branch_publishes": 0,
        "base_published_branch_raises": 0,
        "no_ocr_artifact": 0,
        "multi_artifact_documents": 0,
    }
    findings: list[dict[str, object]] = []
    started = time.perf_counter()

    for sha in ordered:
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
            markdown = StatementMarkdown(
                source_file="replay.pdf",
                model=str(document.get("model") or ""),
                pages=pages,
            ).to_markdown()
            candidates.append((markdown, pages))

        if not candidates:
            counts["no_ocr_artifact"] += 1
            continue
        if len(candidates) > 1:
            counts["multi_artifact_documents"] += 1

        # EVERY partition that holds a document is replayed, not one chosen by
        # a rule. The selection `regfp_zero_movement_sweep` performs exists to
        # match a STORED payload; here both sides are recomputed from the same
        # text, so the honest thing is to leave no partition unexercised.
        for markdown, pages in candidates:
            counts["replays"] += 1
            try:
                before = base.report_to_dict(
                    base.analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
                )
                before_raised = None
            except Exception as exc:  # class only: a base message can carry the token
                before, before_raised = None, type(exc).__name__
            try:
                after = report_to_dict(
                    analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
                )
                after_raised = None
            except Exception as exc:
                after, after_raised = None, type(exc).__name__

            if before_raised and after_raised:
                counts["raised_on_both"] += 1
                if before_raised != after_raised:
                    counts["raise_class_moved"] += 1
                    findings.append(
                        {
                            "content_sha256": sha,
                            "verdict": "raise_class_moved",
                            "base": before_raised,
                            "branch": after_raised,
                            "dispatched_to": sorted(shas[sha]),
                        }
                    )
                continue
            if before_raised and not after_raised:
                counts["base_raised_branch_publishes"] += 1
                findings.append(
                    {
                        "content_sha256": sha,
                        "verdict": "base_raised_branch_publishes",
                        "base": before_raised,
                        "dispatched_to": sorted(shas[sha]),
                    }
                )
                continue
            if after_raised and not before_raised:
                counts["base_published_branch_raises"] += 1
                findings.append(
                    {
                        "content_sha256": sha,
                        "verdict": "base_published_branch_raises",
                        "branch": after_raised,
                        "dispatched_to": sorted(shas[sha]),
                    }
                )
                continue

            base_outcome = classify_outcome(before)
            branch_outcome = classify_outcome(after)
            paths = leaf_diff(before, after)
            if base_outcome != branch_outcome:
                counts["outcome_moved"] += 1
                findings.append(
                    {
                        "content_sha256": sha,
                        "verdict": "outcome_moved",
                        # The CLASS and the REASON are both closed vocabularies
                        # owned by `telemetry/record.py`; neither can carry text
                        # from the document.
                        "base": list(base_outcome),
                        "branch": list(branch_outcome),
                        "dispatched_to": sorted(shas[sha]),
                    }
                )
            if paths:
                counts["moved"] += 1
                findings.append(
                    {
                        "content_sha256": sha,
                        "verdict": "moved",
                        "paths": paths[:40],
                        "path_count": len(paths),
                        "dispatched_to": sorted(shas[sha]),
                    }
                )
            elif base_outcome == branch_outcome:
                counts["identical"] += 1

    report = {
        "base": base.revision,
        "range": [args.start, args.end],
        "registrations": sorted(population),
        "seconds": round(time.perf_counter() - started, 1),
        **counts,
        "findings": findings,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "findings"}, sort_keys=True))
    for finding in findings:
        print(json.dumps(finding, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
