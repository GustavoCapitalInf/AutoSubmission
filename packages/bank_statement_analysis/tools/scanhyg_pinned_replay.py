"""The pinned truth set, replayed base vs branch, verdict block leaf for leaf.

W3 §SCANHYG's HARD STOP. Three of this branch's five commits register a new
`integrity_checks` entry, and an integrity check is the one kind of addition
that can move a document the two forensic audits are structurally blind to: the
published integrity block (flags, notes, `risk_level`,
`possible_document_issue`) can gain an entry with every financial field
byte-identical, and a gained flag can carry a class with it. `corpus_gate.py`
is where that is enforced, and running the gate is the TRAIN's job at merge —
this instrument is the cell's own answer, before the train, and it is narrower
and stricter in one respect: it does not compare against pins written by hand,
it compares the branch against the BASE COMMIT's own output, so a pin that was
wrong could not hide a movement.

    python -m tools.scanhyg_pinned_replay --base 10cc722 \
        [--corpus "<checkout>/Bank Statements"] [--out <private>/pinned.json]

WHAT IS REPLAYED: all 109 pinned corpus-relative paths, enumerated from the
committed balance audit exactly as `corpus_gate.manifest_paths` does — every
one of them, not only the ones expected to reach these readers, because "whose
parser is one of the four" is itself a thing this branch could move. Each
document is resolved through the PRODUCTION intake ladder with both OCR rungs
disabled (`corpus_gate.production_verdict`'s resolution, offline: the six
image-only statements fall through to their committed OCR artifact), and the
parser that claims it is recorded so the report can say which of the 109 the
four readers actually own.

WHAT COUNTS AS MOVEMENT: any difference at all between the two sides — outcome
class, any leaf of the published payload, or any element of the integrity
block. A difference is NOT repaired here and is not a defect report; it is a
ceremony decision, and the instrument's whole job is to name it exactly.

Both sides run in separate child processes; the base side's changed modules are
read out of git as blobs (see `tools.scanhyg_family_replay.install_modules`).
Read-only, offline, $0.00: no OCR binary, no endpoint, no model call.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from bank_statements import bank_statements_dir_or_exit
from tools.scanhyg_family_replay import canonical, flatten, install_modules, template


def manifest(repo: Path) -> list[str]:
    """The 109 pinned corpus-relative paths, from the committed balance audit."""
    path = repo / "docs" / "balance-metrics-audit-results.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sorted({row["path"] for row in csv.DictReader(handle)})


def run_side(args: argparse.Namespace) -> int:
    repo = Path(__file__).resolve().parent.parent
    installed: list[str] = []
    if args.side == "base":
        installed = install_modules(repo, args.base, args.base)

    # Imported after the blobs are installed, so the base side's registry binds
    # the base functions.
    from analysis.parser_registry import resolve
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from corpus_artifacts import cached_markdown, cached_pages
    from corpus_gate import PRODUCTION_SUPPLIES_SHEETS
    from ocr.inspect import inspect_pdf
    from ocr.pipeline import parse_statement
    from telemetry.record import classify_outcome

    corpus = args.corpus or bank_statements_dir_or_exit()
    cache = args.ocr_cache or (repo / "tests" / "corpus_cache")
    records: dict[str, dict] = {}
    started = time.perf_counter()
    for rel in manifest(repo):
        path = corpus / Path(rel)
        record: dict[str, object] = {}
        if not path.is_file():
            record["resolution"] = "missing"
            records[rel] = record
            continue
        raw = path.read_bytes()
        # Named by CONTENT HASH in everything this prints. The pinned manifest
        # is a list of file paths, and a corpus path carries an institution and
        # a customer's filename; an 8-hex prefix names the same document and
        # carries neither.
        record["sha"] = hashlib.sha256(raw).hexdigest().upper()[:12]
        document = parse_statement(
            raw,
            source_file=path.name,
            profile=inspect_pdf(raw),
            force_ocr=False,
            allow_local_ocr=False,
            allow_visual_ocr=False,
        )
        if document is not None:
            markdown = document.to_markdown()
            sheets = list(document.pages) if PRODUCTION_SUPPLIES_SHEETS else None
            record["resolution"] = "native"
        else:
            markdown = cached_markdown(raw, cache)
            sheets = cached_pages(raw, cache) if PRODUCTION_SUPPLIES_SHEETS else None
            record["resolution"] = "committed_ocr_artifact"
            if markdown is None:
                record["resolution"] = "no_text_and_no_artifact"
                records[rel] = record
                continue
        try:
            record["claimed_by"] = resolve(markdown).parser_id
        except Exception as exc:
            record["claimed_by"] = f"!{type(exc).__name__}"
        try:
            payload = report_to_dict(
                analyze_markdown(markdown, parse_mode="deterministic", sheets=sheets)
            )
            raised = None
        except Exception as exc:
            payload, raised = None, f"{type(exc).__name__}: {exc}"
        if raised is not None:
            # A pinned REFUSAL is a pinned fact: the message is part of it, and
            # it is this platform's own text, never the document's.
            record["raised"] = raised
            record["outcome"] = "refused"
            records[rel] = record
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
        records[rel] = record

    args.side_out.write_text(
        json.dumps(
            {
                "side": args.side,
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


def compare(base: dict, branch: dict, parsers: tuple[str, ...]) -> dict:
    findings: list[dict[str, object]] = []
    counts = {
        "pinned": 0,
        "identical": 0,
        "moved": 0,
        "refused_both_sides": 0,
        "claimed_by_target_reader": 0,
    }
    owned: dict[str, list[str]] = {}
    for rel in sorted(set(base) | set(branch)):
        before, after = base.get(rel, {}), branch.get(rel, {})
        counts["pinned"] += 1
        claimed = before.get("claimed_by")
        if claimed in parsers:
            counts["claimed_by_target_reader"] += 1
            owned.setdefault(str(claimed), []).append(str(before.get("sha")))
        if before.get("raised") or after.get("raised"):
            if before.get("raised") == after.get("raised"):
                counts["refused_both_sides"] += 1
                continue
            counts["moved"] += 1
            findings.append({
                "sha": before.get("sha") or after.get("sha"),
                "verdict": "refusal_moved",
                "claimed_by": [claimed, after.get("claimed_by")],
                "base": before.get("raised") or before.get("outcome"),
                "branch": after.get("raised") or after.get("outcome"),
            })
            continue
        moved_paths = sorted(
            path
            for path in set(before.get("leaves") or {}) | set(after.get("leaves") or {})
            if (before.get("leaves") or {}).get(path) != (after.get("leaves") or {}).get(path)
        )
        block_moved = any(
            before.get(field) != after.get(field)
            for field in ("outcome", "reason", "flags", "note_templates",
                          "risk_level", "possible_document_issue", "claimed_by")
        )
        if not moved_paths and not block_moved:
            counts["identical"] += 1
            continue
        counts["moved"] += 1
        findings.append({
            "sha": before.get("sha") or after.get("sha"),
            "verdict": "moved",
            "claimed_by": [claimed, after.get("claimed_by")],
            "outcome": [
                f"{before.get('outcome')}/{before.get('reason')}",
                f"{after.get('outcome')}/{after.get('reason')}",
            ],
            "flags_gained": sorted(set(after.get("flags") or ()) - set(before.get("flags") or ())),
            "flags_lost": sorted(set(before.get("flags") or ()) - set(after.get("flags") or ())),
            "risk_level": [before.get("risk_level"), after.get("risk_level")],
            "leaf_paths": moved_paths,
        })
    return {**counts, "owned_by_target_reader": {k: sorted(v) for k, v in sorted(owned.items())},
            "findings": findings}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--ocr-cache", type=Path, default=None)
    parser.add_argument(
        "--parsers",
        nargs="+",
        default=["southside_scanned", "citizens", "eq_bank_scanned",
                 "texas_first_scanned", "apex_scanned"],
    )
    parser.add_argument("--out", type=Path, default=None)
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
            sys.executable, "-m", "tools.scanhyg_pinned_replay",
            "--base", args.base, "--side", side, "--side-out", str(side_out),
            "--parsers", *args.parsers,
        ]
        if args.corpus:
            command += ["--corpus", str(args.corpus)]
        if args.ocr_cache:
            command += ["--ocr-cache", str(args.ocr_cache)]
        finished = subprocess.run(command, cwd=str(Path(__file__).resolve().parent.parent))
        if finished.returncode != 0:
            print(f"{side} side exited {finished.returncode}", file=sys.stderr)
            return finished.returncode
        sides[side] = json.loads(side_out.read_text(encoding="utf-8"))

    report = compare(sides["base"]["records"], sides["branch"]["records"], tuple(args.parsers))
    report["base_commit"] = args.base
    report["installed_from_blobs"] = sides["base"]["installed_from_blobs"]
    report["seconds"] = [sides["base"]["seconds"], sides["branch"]["seconds"]]
    args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(canonical({k: v for k, v in report.items()
                     if k not in ("findings", "owned_by_target_reader")}))
    print(canonical(report["owned_by_target_reader"]))
    for finding in report["findings"]:
        print(canonical(finding))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
