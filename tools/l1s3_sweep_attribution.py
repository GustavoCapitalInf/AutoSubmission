"""l1s3_sweep_attribution.py — whose movement is it? The sweep, run twice.

    python -m tools.l1s3_sweep_attribution --base <base logs glob> --tip <tip logs glob>
    python -m tools.l1s3_sweep_attribution --replay-base <glob> --replay-tip <glob>

**NOT A PARSER. NEVER REGISTERED. IT CALLS NO ANALYSIS AND READS NO DOCUMENT.**

`tools/regfp_zero_movement_sweep.py` compares a tree's recomputed payload
against the payload the RUN OF RECORD cached — and the run of record is
batch 8's. train9 has composed movement cells since, so a sweep at ANY train9
tree reports THEIR movement as well as the branch's, and a branch that read
only its own sweep would either claim someone else's movement or explain away
its own inside the same number.

So the sweep is run twice, at the BASE and at the TIP, over the identical
population, and this instrument diffs the two finding sets by content sha:

  * a finding at BOTH — the base tree already had it. It belongs to what train9
    composed before this branch existed, and this branch neither caused nor
    cured it;
  * a finding at the TIP ONLY — this branch caused it. For a card whose claim
    is ZERO MOVEMENT this must be empty;
  * a finding at the BASE ONLY — this branch made a moved document stop moving,
    which is still movement and still has to be explained. Also must be empty.

A finding is `(content_sha256, verdict)`. The changed FIELD NAMES the sweep
reports are compared too, because a document that moved at both trees for
different reasons is not the same finding.

`--replay-base` / `--replay-tip` do the same job for `tools/cohort_replay.py`'s
per-document JSON, which has the same baseline and therefore the same problem.
One field is ignored there and named here rather than dropped quietly: `ms`,
the per-document elapsed TIME, which differs between any two runs of anything
and says nothing about what was published.

PRIVACY. Content sha16s, verdict tokens, field NAMES (the sweep's own, which
are payload keys rather than values) and counts. No amount, date, name or path.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

VERDICT_KEY = "verdict"
SHA_KEY = "content_sha256"


def _findings(paths: list[str]) -> tuple[dict[str, tuple], dict[str, int]]:
    """`({sha: (verdict, fields…)}, {verdict: count})` from a sweep's logs."""
    findings: dict[str, tuple] = {}
    totals: dict[str, int] = {}
    for path in sorted(paths):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if SHA_KEY not in row:
                    for key, value in row.items():
                        if isinstance(value, int):
                            totals[key] = totals.get(key, 0) + value
                    continue
                findings[row[SHA_KEY]] = (
                    row.get(VERDICT_KEY),
                    tuple(row.get("fields") or ()),
                    row.get("exception"),
                )
    return findings, totals


#: The per-document field a replay row carries that is not about the payload.
REPLAY_IGNORED_FIELDS = {"ms"}


def _replay_rows(paths: list[str]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in sorted(paths):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        for row in payload.get("rows") or []:
            rows[row["sha"]] = row
    return rows


def attribute_replay(base_glob: str, tip_glob: str) -> int:
    base = _replay_rows(glob.glob(base_glob))
    tip = _replay_rows(glob.glob(tip_glob))
    if not base or not tip:
        print("REFUSING: one of the two replays produced no rows at all.")
        return 2
    fields: dict[str, int] = {}
    differing: list[str] = []
    for sha in set(base) | set(tip):
        before, after = base.get(sha), tip.get(sha)
        if before is None or after is None:
            differing.append(sha)
            fields["MISSING_AT_ONE_TREE"] = fields.get("MISSING_AT_ONE_TREE", 0) + 1
            continue
        moved = False
        for field in set(before) | set(after):
            if field in REPLAY_IGNORED_FIELDS:
                continue
            if before.get(field) != after.get(field):
                fields[field] = fields.get(field, 0) + 1
                moved = True
        if moved:
            differing.append(sha)
    print("# L1-S3 — replay attribution: the base tree and the tip, same cohort")
    print()
    print("| measure | documents |")
    print("|---|---:|")
    print(f"| documents replayed at both trees | {len(set(base) | set(tip))} |")
    print(f"| whose replay row DIFFERS (ignoring {sorted(REPLAY_IGNORED_FIELDS)}) | {len(differing)} |")
    print()
    if differing:
        print("**THIS BRANCH MOVED DOCUMENTS.** Fields that differ, and on how many:")
        print()
        for field, count in sorted(fields.items()):
            print(f"* `{field}` — {count}")
        for sha in sorted(differing)[:50]:
            print(f"* `{sha[:16]}`")
        return 1
    print("**ZERO MOVEMENT ATTRIBUTABLE TO THIS BRANCH.** Every document's "
          "before and after outcome, reason, registration, payload identity "
          "and changed leaf paths are the same at both trees.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="attribute sweep findings to a tree")
    parser.add_argument("--base", help="glob for the BASE sweep logs")
    parser.add_argument("--tip", help="glob for the TIP sweep logs")
    parser.add_argument("--replay-base", help="glob for the BASE cohort_replay JSON")
    parser.add_argument("--replay-tip", help="glob for the TIP cohort_replay JSON")
    args = parser.parse_args(argv)
    if bool(args.replay_base) != bool(args.replay_tip):
        parser.error("--replay-base and --replay-tip go together")
    if args.replay_base:
        return attribute_replay(args.replay_base, args.replay_tip)
    if not (args.base and args.tip):
        parser.error("--base and --tip are required for the sweep mode")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    base, base_totals = _findings(glob.glob(args.base))
    tip, tip_totals = _findings(glob.glob(args.tip))
    if not base or not tip:
        print("REFUSING: one of the two sweeps produced no findings at all, so "
              "a diff of the two would be a claim about a measurement that did "
              "not happen.")
        return 2

    shared = {sha for sha in base if sha in tip and base[sha] == tip[sha]}
    differing = {sha for sha in base if sha in tip and base[sha] != tip[sha]}
    tip_only = set(tip) - set(base)
    base_only = set(base) - set(tip)

    print("# L1-S3 — sweep attribution: the base tree and the tip, same population")
    print()
    print("| measure | base | tip |")
    print("|---|---:|---:|")
    for key in sorted(set(base_totals) | set(tip_totals)):
        if key in {"seconds"}:
            continue
        print(f"| {key} | {base_totals.get(key, 0)} | {tip_totals.get(key, 0)} |")
    print()
    print("| attribution | documents |")
    print("|---|---:|")
    print(f"| finding at BOTH trees, identical — train9's, not this branch's | {len(shared)} |")
    print(f"| finding at both trees but DIFFERENT — this branch's | {len(differing)} |")
    print(f"| finding at the TIP only — this branch's | {len(tip_only)} |")
    print(f"| finding at the BASE only — this branch's | {len(base_only)} |")
    print()
    mine = sorted(differing | tip_only | base_only)
    if mine:
        print("**THIS BRANCH MOVED DOCUMENTS.** Each one, by content sha16 and verdict:")
        print()
        for sha in mine:
            print(f"* `{sha[:16]}` base={base.get(sha)} tip={tip.get(sha)}")
        return 1
    print("**ZERO MOVEMENT ATTRIBUTABLE TO THIS BRANCH.** Every finding the tip "
          "sweep reports is present at the base tree, identically: same "
          "document, same verdict, same changed field names.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
