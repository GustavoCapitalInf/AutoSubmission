"""Replay the SCAN-HYGIENE families base vs branch, leaf for leaf.

W3 §SCANHYG's movement instrument. The question it answers is the one a card
that changes four readers owes an answer to: **for every document the run of
record put in front of one of those readers, does anything the platform
publishes about it differ between the base commit and this branch — and if it
does, exactly which leaves?**

    python -m tools.scanhyg_family_replay \
        --rows <reports>/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> \
        --base 10cc722 [--out <private>/replay.json]

WHY BOTH SIDES RUN HERE rather than in two checkouts. The base modules are read
out of git as BLOBS and installed into `sys.modules` under their own names
before anything imports `analysis.pipeline`, so the base registry binds the base
functions and the base parsers run the base code. Two checkouts of one repo on
this host is two OneDrive trees and a second place for a stale file to hide; a
blob is what the commit actually says. The two sides still run in separate
CHILD processes — a registry loaded once per process is not a thing that can be
reloaded honestly — and this parent only diffs their JSON.

WHICH DOCUMENTS. Detection is untouched on this branch (no detector marker
moved), so the claimed set is the run's own: every `content_sha256` whose
`parser_id` is one of the named readers, plus every one whose `attempted` names
one — a document a reader CLAIMED and then DECLINED runs the changed `parse`
just as far as the refusal, and is exactly where a widening would first show.
`apex_scanned` is carried as a control: it shares
`analysis/scanned_small_bank.py` with southside and texas_first but calls none
of the functions this branch changed (measured: its `parse` reaches
`_extract_holder_name`, `_section`, `_money`, `_iso`, `compact_whitespace`, none
of which the diff touches), so it is the module-level answer to "did importing
the module differently move anything".

WHICH OCR ARTIFACT, and why it is not a guess: the same per-document proof
`tools/regfp_zero_movement_sweep.py` uses. Every capability partition of
`ocr_settings_key` is enumerated and the artifact chosen is the one whose
reconstruction resolves the run's OWN stored analysis payload. That gives this
tool a third comparison for free, and it is the one that makes the other two
trustworthy: BASE vs the run of record. Where base and the run agree byte for
byte, the base side is demonstrably the code that produced the run, and a
branch-side difference is this branch's doing rather than the harness's.

READ-ONLY and $0.00. Nothing is written to the archive or the artifact store,
the `webapp_data` sqlite index is never opened, and `parse_mode="deterministic"`
cannot reach the extraction branch, tests included.

WHAT IT PRINTS. Leaf PATHS, outcome classes, integrity FLAG NAMES (which are
code-defined identifiers, not document content), and for an integrity note the
sentence TEMPLATE with every figure replaced by `<figure>`. Never a value: no
amount, no date, no name, no account number. The full per-document leaf map is
written to `--out`, which belongs in a private scratchpad and is not committed.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import json
import re
import subprocess
import sys
import time
from pathlib import Path

#: The readers this card changes, plus the shared-module control.
TARGET_PARSERS = (
    "southside_scanned",
    "citizens",
    "eq_bank_scanned",
    "texas_first_scanned",
    "apex_scanned",
)

_FIGURE_RE = re.compile(r"\d[\d,./:-]*")


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def template(text: str) -> str:
    """One integrity note with every printed figure replaced.

    The sentence shape is this branch's own source and is safe to record; the
    figures in it are the document's and are not.
    """
    return _FIGURE_RE.sub("<figure>", str(text))


def flatten(value: object, prefix: str, out: dict[str, str]) -> None:
    """Every LEAF of a published payload, as `dotted.path -> canonical value`.

    A leaf diff rather than a field diff because the field names a sweep prints
    cannot say whether a `statement` moved its ending balance or gained a flag.

    A TUPLE is a list here. `report_to_dict` returns some sequences as tuples
    in memory and JSON has no tuple, so a stored payload read back is a list
    where the recompute is a tuple; a flattener that walked one and not the
    other would score every such field as moved. That is a harness artefact and
    it manufactured a false difference on every document of this family before
    it was fixed — recorded because a measurement's first duty is to be a
    measurement of the product.
    """
    if isinstance(value, dict):
        for key in sorted(value):
            flatten(value[key], f"{prefix}.{key}" if prefix else str(key), out)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            flatten(item, f"{prefix}[{index}]", out)
    else:
        out[prefix] = canonical(value)


def install_modules(repo: Path, rev: str, base: str) -> list[str]:
    """Install this branch's changed `analysis/` modules AT `rev` into
    `sys.modules`, before anything imports the analysis stack.

    THE FILE LIST IS ALWAYS THE WHOLE BRANCH's (`base..HEAD`), whatever `rev`
    is. Shadowing only the files one intermediate commit happened to touch
    would leave the working tree's LATER version of every other changed module
    in the process, which is not any commit's tree and not a measurement of
    anything.

    Order matters and is derived rather than typed: a module that another one
    imports must be installed first, so the list is sorted with
    `parser_registry_entries` last (it is the table that binds every parser
    module) and `date_tokens` first (the helper the readers import). Each blob
    is executed with `__package__` set, so its relative imports resolve against
    the real `analysis` package and every UNCHANGED module is the working
    tree's — which is what "base vs branch" means here: only the diff moves.
    """
    import analysis

    changed = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{base}..HEAD", "--", "analysis/"],
        check=True, capture_output=True, text=True,
    ).stdout.split()
    names = [Path(path).stem for path in changed]
    order = {"date_tokens": 0, "parser_registry_entries": 2}
    for name in sorted(names, key=lambda n: (order.get(n, 1), n)):
        source = subprocess.run(
            ["git", "-C", str(repo), "show", f"{rev}:analysis/{name}.py"],
            check=True, capture_output=True,
        ).stdout.decode("utf-8")
        spec = importlib.util.spec_from_loader(f"analysis.{name}", loader=None)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = "analysis"
        module.__file__ = f"<{rev}:analysis/{name}.py>"
        sys.modules[f"analysis.{name}"] = module
        setattr(analysis, name, module)
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    return sorted(names)


def population(rows: Path, parsers: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """`content_sha256 -> {parser, dispatch, outcome_class}` for the families.

    `parser_id` is a document the reader claimed AND parsed; `attempted` is one
    it claimed and DECLINED. Both run the changed code. `near_miss` is neither —
    a detector score below the claim threshold never reaches `parse` — and is
    deliberately excluded, which is why this population is dozens rather than
    hundreds.
    """
    found: dict[str, dict[str, str]] = {}
    with rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if not sha:
                continue
            parser = row["parser_id"].strip()
            if parser in parsers:
                found[sha] = {
                    "parser": parser,
                    "dispatch": "dispatched",
                    "outcome_class": row["outcome_class"],
                }
                continue
            for attempted in (row.get("attempted") or "").split(";"):
                attempted = attempted.strip()
                if attempted in parsers and sha not in found:
                    found[sha] = {
                        "parser": attempted,
                        "dispatch": "declined",
                        "outcome_class": row["outcome_class"],
                    }
    return found


def ocr_partitions():
    """Every capability partition of `ocr_settings_key`.

    Eight keys is the whole space of the three boolean flags, and existence
    checks against the missing ones are free. Enumerating them is what stops a
    document being read from the wrong rung's text.
    """
    from webapp.artifact_cache import ocr_settings_key

    return [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]


def document_text(root, sha: str, ocr_keys, baseline: str):
    """`(markdown, pages, resolution, run_payload)` for one archived document.

    The artifact is not chosen by an ordering: every partition that holds the
    document is reconstructed and the one selected is the one whose analysis
    cache key resolves the run's OWN stored payload, which is per-document
    proof that this is the text the run analysed.
    """
    import json as _json

    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS,
        STAGE_OCR,
        analysis_input_sha,
        cache_key,
    )

    candidates: list[tuple[str, list[str]]] = []
    for key in ocr_keys:
        composed = cache_key(STAGE_OCR, sha, key)
        path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        try:
            payload = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            # A cached NEGATIVE OCR result: a real cached fact, not a miss.
            continue
        pages = [str(page) for page in (document.get("pages") or [])]
        markdown = StatementMarkdown(
            source_file="replay.pdf",
            model=str(document.get("model") or ""),
            pages=pages,
        ).to_markdown()
        candidates.append((markdown, pages))
    if not candidates:
        return None, None, "no_ocr_artifact", None

    markdown, pages = candidates[0]
    run_payload = None
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
            run_payload = _json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
        except (OSError, ValueError, KeyError):
            continue
        markdown, pages = candidate_markdown, candidate_pages
        break
    resolution = "run_payload" if run_payload is not None else "sole_artifact"
    return markdown, pages, resolution, run_payload


def run_side(args: argparse.Namespace) -> int:
    """One side of the replay, in its own process. Writes JSON to `--side-out`."""
    repo = Path(__file__).resolve().parent.parent
    installed: list[str] = []
    # The BRANCH side is the working tree unless `--head` names a commit, which
    # is how one sub-card's movement is separated from the next one's: the same
    # replay, base against each commit in turn.
    if args.side == "base":
        installed = install_modules(repo, args.base, args.base)
    elif args.head:
        installed = install_modules(repo, args.head, args.base)

    from analysis.parser_registry import resolve
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from telemetry.record import classify_outcome

    baseline = args.baseline_settings_key.strip().upper()
    root = args.data_dir / "artifacts"
    ocr_keys = ocr_partitions()
    members = population(args.rows, tuple(args.parsers))

    records: dict[str, dict] = {}
    started = time.perf_counter()
    for sha in sorted(members):
        record: dict[str, object] = dict(members[sha])
        markdown, pages, resolution, run_payload = document_text(
            root, sha, ocr_keys, baseline
        )
        record["resolution"] = resolution
        if markdown is None:
            records[sha] = record
            continue

        try:
            record["claimed_by"] = resolve(markdown).parser_id
        except Exception as exc:  # a detector that raises is itself a finding
            record["claimed_by"] = f"!{type(exc).__name__}"
        try:
            payload = report_to_dict(
                analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
            )
            raised = None
        except Exception as exc:
            payload, raised = None, type(exc).__name__
        if raised is not None:
            record["raised"] = raised
            record["outcome"], record["reason"] = classify_outcome(None, error_type=raised)
            records[sha] = record
            continue
        outcome, reason = classify_outcome(payload)
        integrity = payload.get("integrity") or {}
        leaves: dict[str, str] = {}
        flatten(payload, "", leaves)
        record.update(
            outcome=outcome,
            reason=reason,
            flags=list(integrity.get("flags") or ()),
            note_templates=[template(note) for note in (integrity.get("notes") or ())],
            risk_level=integrity.get("risk_level"),
            possible_document_issue=bool(integrity.get("possible_document_issue")),
            leaves=leaves,
        )
        if run_payload is not None:
            run_leaves: dict[str, str] = {}
            flatten(run_payload, "", run_leaves)
            record["matches_run_of_record"] = run_leaves == leaves
        records[sha] = record

    args.side_out.write_text(
        json.dumps(
            {
                "side": args.side,
                "base": args.base,
                "installed_from_blobs": installed,
                "documents": len(records),
                "seconds": round(time.perf_counter() - started, 1),
                "records": records,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return 0


def compare(base: dict, branch: dict) -> dict:
    """Base vs branch, per document, as classes and leaf PATHS."""
    findings: list[dict[str, object]] = []
    counts = {
        "documents": 0,
        "identical": 0,
        "outcome_moved": 0,
        "payload_moved": 0,
        "raised_either_side": 0,
        "no_ocr_artifact": 0,
        "base_matches_run_of_record": 0,
        "base_differs_from_run_of_record": 0,
    }
    for sha in sorted(set(base) | set(branch)):
        before, after = base.get(sha, {}), branch.get(sha, {})
        counts["documents"] += 1
        if before.get("resolution") == "no_ocr_artifact":
            counts["no_ocr_artifact"] += 1
            continue
        if before.get("matches_run_of_record") is True:
            counts["base_matches_run_of_record"] += 1
        elif "matches_run_of_record" in before:
            counts["base_differs_from_run_of_record"] += 1
            findings.append({
                "content_sha256": sha,
                "verdict": "base_differs_from_run_of_record",
                "parser": before.get("parser"),
            })
        if before.get("raised") or after.get("raised"):
            counts["raised_either_side"] += 1
            if before.get("raised") != after.get("raised"):
                counts["outcome_moved"] += 1
                findings.append({
                    "content_sha256": sha,
                    "verdict": "refusal_moved",
                    "parser": before.get("parser"),
                    "base": before.get("raised") or before.get("outcome"),
                    "branch": after.get("raised") or after.get("outcome"),
                })
            continue
        moved_paths = sorted(
            path
            for path in set(before.get("leaves") or {}) | set(after.get("leaves") or {})
            if (before.get("leaves") or {}).get(path) != (after.get("leaves") or {}).get(path)
        )
        outcome_moved = (before.get("outcome"), before.get("reason")) != (
            after.get("outcome"), after.get("reason")
        )
        if not moved_paths and not outcome_moved:
            counts["identical"] += 1
            continue
        counts["payload_moved"] += 1
        if outcome_moved:
            counts["outcome_moved"] += 1
        findings.append({
            "content_sha256": sha,
            "verdict": "outcome_moved" if outcome_moved else "payload_moved",
            "parser": before.get("parser"),
            "dispatch": before.get("dispatch"),
            "outcome": [
                f"{before.get('outcome')}/{before.get('reason')}",
                f"{after.get('outcome')}/{after.get('reason')}",
            ],
            "flags_gained": sorted(set(after.get("flags") or ()) - set(before.get("flags") or ())),
            "flags_lost": sorted(set(before.get("flags") or ()) - set(after.get("flags") or ())),
            "notes_gained": [
                note for note in (after.get("note_templates") or ())
                if note not in (before.get("note_templates") or ())
            ],
            "notes_lost": [
                note for note in (before.get("note_templates") or ())
                if note not in (after.get("note_templates") or ())
            ],
            "risk_level": [before.get("risk_level"), after.get("risk_level")],
            "leaf_paths": moved_paths,
        })
    return {**counts, "findings": findings}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", required=True)
    parser.add_argument("--base", required=True, help="the base commit-ish")
    parser.add_argument(
        "--head",
        default=None,
        help="replay the branch side at this commit instead of the working tree "
        "(sub-card attribution: base against each commit in turn)",
    )
    parser.add_argument("--parsers", nargs="+", default=list(TARGET_PARSERS))
    parser.add_argument("--out", type=Path, default=None, help="private full report")
    parser.add_argument("--side", choices=("base", "branch"), default=None)
    parser.add_argument("--side-out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.side is not None:
        if args.side_out is None:
            print("--side requires --side-out", file=sys.stderr)
            return 2
        return run_side(args)

    if args.out is None:
        print("--out is required (a private path; both sides are written beside it)", file=sys.stderr)
        return 2
    sides: dict[str, dict] = {}
    for side in ("base", "branch"):
        side_out = args.out.with_name(f"{args.out.stem}.{side}.json")
        command = [
            sys.executable, "-m", "tools.scanhyg_family_replay",
            "--rows", str(args.rows), "--data-dir", str(args.data_dir),
            "--baseline-settings-key", args.baseline_settings_key,
            "--base", args.base, "--parsers", *args.parsers,
            "--side", side, "--side-out", str(side_out),
        ]
        if args.head:
            command += ["--head", args.head]
        finished = subprocess.run(command, cwd=str(Path(__file__).resolve().parent.parent))
        if finished.returncode != 0:
            print(f"{side} side exited {finished.returncode}", file=sys.stderr)
            return finished.returncode
        sides[side] = json.loads(side_out.read_text(encoding="utf-8"))

    report = compare(sides["base"]["records"], sides["branch"]["records"])
    report["base_commit"] = args.base
    report["head_commit"] = args.head or "working tree"
    report["installed_from_blobs"] = sides["base"]["installed_from_blobs"]
    report["seconds"] = [sides["base"]["seconds"], sides["branch"]["seconds"]]
    per_parser: dict[str, int] = {}
    for sha, record in sides["branch"]["records"].items():
        per_parser[record["parser"]] = per_parser.get(record["parser"], 0) + 1
    report["per_parser"] = dict(sorted(per_parser.items()))
    args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(canonical({key: value for key, value in report.items() if key != "findings"}))
    for finding in report["findings"]:
        print(canonical(finding))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
