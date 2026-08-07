"""W3-4 — coverage movement between two discovery runs, in one command.

    python -m discovery.compare <baseline_run_dir> <candidate_run_dir>

This is how every Track A / W3-3c improvement gets measured against the frozen
baseline from now on: not "the summary went from 30.2% to 34.1%", but **which
documents moved, out of which failure class, for which parser family** - so a
change that fixes 200 chase detail-coverage withholds and breaks 30 wells
validations reports both, instead of netting out to a number that looks fine.

Two design commitments:

**Keyed on content hashes, never on ordering.** A document is its
`content_sha256`. Run ids, timings, record ids, row order, tranche mode and
the wall-clock all differ between any two runs and none of them is a
difference in what the platform did. Two runs over the same bytes with the
same code must compare as zero movement, and a test asserts exactly that by
comparing a run to itself.

**Asymmetry is reported, never averaged.** Regressions and improvements are
separate lines. A comparison that only printed a net delta would let a real
regression hide inside a bigger win, which is the one thing a merge gate must
not do.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .evidence import Document, Run, load_run

#: Outcome classes ranked worst to best. Movement UP this ladder is an
#: improvement; movement DOWN is a regression. `deferred` sits outside the
#: ladder deliberately - it means "this tranche chose not to try", which is a
#: statement about the run, so moving in or out of it is neither.
LADDER = ("failed", "withheld", "review", "validated")
UNRANKED = ("deferred", "unknown")


def _rank(outcome_class: str) -> int | None:
    return LADDER.index(outcome_class) if outcome_class in LADDER else None


def direction(before: str, after: str) -> str:
    """improved | regressed | unchanged | unranked."""
    if before == after:
        return "unchanged"
    left, right = _rank(before), _rank(after)
    if left is None or right is None:
        return "unranked"
    return "improved" if right > left else "regressed"


def _family(document: Document | None) -> str:
    """The parser family a document belongs to, for grouping.

    Falls back to the folder label, then to `(unclaimed)`: a document that no
    parser claimed still belongs to a family for reporting purposes, and that
    family is what a human called it.
    """
    if document is None:
        return "(absent)"
    if document.parser_id:
        return document.parser_id
    if document.folder_label:
        return f"folder:{document.folder_label}"
    return "(unclaimed)"


def compare(baseline: Run, candidate: Run) -> dict:
    """Every difference between two runs, keyed on document identity."""
    shared = sorted(set(baseline.documents) & set(candidate.documents))
    only_baseline = sorted(set(baseline.documents) - set(candidate.documents))
    only_candidate = sorted(set(candidate.documents) - set(baseline.documents))

    directions: Counter = Counter()
    transitions: Counter = Counter()
    by_family: dict[str, Counter] = defaultdict(Counter)
    class_movement: Counter = Counter()
    family_movement: dict[str, Counter] = defaultdict(Counter)
    regressed_samples: list[dict] = []
    improved_samples: list[dict] = []

    for sha in shared:
        before, after = baseline.documents[sha], candidate.documents[sha]
        move = direction(before.outcome_class, after.outcome_class)
        directions[move] += 1
        family = _family(before) if before.parser_id or not after.parser_id else _family(after)
        by_family[family][move] += 1
        if move == "unchanged":
            continue
        transitions[f"{before.outcome_class} -> {after.outcome_class}"] += 1
        family_movement[family][move] += 1
        # Failure class is the W3-2 diagnosis the document LEFT (or entered).
        left, entered = before.primary_class, after.primary_class
        if left and not entered:
            class_movement[f"left {left}"] += 1
        elif entered and not left:
            class_movement[f"entered {entered}"] += 1
        elif left and entered and left != entered:
            class_movement[f"{left} -> {entered}"] += 1
        sample = {
            "content_sha256": sha,
            "from": before.outcome_class,
            "to": after.outcome_class,
            "family": family,
            "failure_class_before": left,
            "failure_class_after": entered,
        }
        (regressed_samples if move == "regressed" else improved_samples).append(sample)

    def coverage(run: Run) -> tuple[int, int]:
        dispatched = [d for d in run.values() if d.dispatch_outcome]
        return sum(1 for d in dispatched if d.dispatch_outcome == "claimed"), len(dispatched)

    base_claimed, base_dispatched = coverage(baseline)
    cand_claimed, cand_dispatched = coverage(candidate)

    return {
        "baseline_run": baseline.run_id,
        "candidate_run": candidate.run_id,
        "documents": {
            "baseline": len(baseline),
            "candidate": len(candidate),
            "shared": len(shared),
            "only_baseline": len(only_baseline),
            "only_candidate": len(only_candidate),
        },
        "identical": (
            not only_baseline and not only_candidate
            and directions.get("unchanged", 0) == len(shared)
        ),
        "movement": dict(directions),
        "transitions": dict(transitions.most_common()),
        "failure_class_movement": dict(class_movement.most_common()),
        "by_family": {
            family: dict(counts.most_common())
            for family, counts in sorted(
                family_movement.items(),
                key=lambda item: (
                    -(item[1].get("improved", 0) + item[1].get("regressed", 0)
                      + item[1].get("unranked", 0)),
                    item[0],
                ),
            )
        },
        "outcome": {
            "baseline": dict(Counter(d.outcome_class for d in baseline.values()).most_common()),
            "candidate": dict(Counter(d.outcome_class for d in candidate.values()).most_common()),
        },
        "deterministic_coverage": {
            "baseline": (base_claimed / base_dispatched) if base_dispatched else 0.0,
            "candidate": (cand_claimed / cand_dispatched) if cand_dispatched else 0.0,
            "baseline_dispatched": base_dispatched,
            "candidate_dispatched": cand_dispatched,
        },
        "regressed_sample": regressed_samples[:20],
        "improved_sample": improved_samples[:20],
    }


def render(report: dict, *, top: int = 20) -> str:
    """ASCII only."""
    documents = report["documents"]
    lines = [
        f"coverage movement  {report['baseline_run']}  ->  {report['candidate_run']}",
        f"documents  baseline {documents['baseline']} | candidate {documents['candidate']} "
        f"| shared {documents['shared']}",
    ]
    if documents["only_baseline"] or documents["only_candidate"]:
        lines.append(
            f"  NOT COMPARABLE for {documents['only_baseline']} baseline-only and "
            f"{documents['only_candidate']} candidate-only documents "
            "(different document sets, reported not averaged)"
        )
    if report["identical"]:
        lines.append("")
        lines.append("  NO MOVEMENT: every shared document reached the same outcome.")

    lines.extend(["", "movement (shared documents)"])
    shared = documents["shared"]
    for key in ("improved", "regressed", "unchanged", "unranked"):
        if key in report["movement"]:
            count = report["movement"][key]
            share = f"{count / shared:6.1%}" if shared else "     -"
            lines.append(f"  {key:<24}{count:>7}   {share}")

    coverage = report["deterministic_coverage"]
    delta = coverage["candidate"] - coverage["baseline"]
    lines.extend([
        "",
        f"deterministic coverage    {coverage['baseline']:.1%} -> "
        f"{coverage['candidate']:.1%}   ({delta:+.1%})",
    ])

    lines.extend(["", "outcome"])
    classes = sorted(set(report["outcome"]["baseline"]) | set(report["outcome"]["candidate"]))
    for name in classes:
        before = report["outcome"]["baseline"].get(name, 0)
        after = report["outcome"]["candidate"].get(name, 0)
        lines.append(f"  {name:<24}{before:>7} -> {after:>7}   ({after - before:+})")

    if report["transitions"]:
        lines.extend(["", "transitions"])
        for key, count in list(report["transitions"].items())[:top]:
            lines.append(f"  {key:<40}{count:>7}")

    if report["failure_class_movement"]:
        lines.extend(["", "failure class movement (W3-2 diagnosis)"])
        for key, count in list(report["failure_class_movement"].items())[:top]:
            lines.append(f"  {key:<40}{count:>7}")

    moved = {
        family: counts for family, counts in report["by_family"].items()
        if any(counts.get(key) for key in ("improved", "regressed", "unranked"))
    }
    if moved:
        lines.extend([
            "",
            "movement by parser family (families with no movement are omitted)",
            f"  {'family':<30}{'improved':>10}{'regressed':>11}{'unranked':>10}",
        ])
        for family, counts in list(moved.items())[:top]:
            lines.append(
                f"  {family:<30}{counts.get('improved', 0):>10}"
                f"{counts.get('regressed', 0):>11}{counts.get('unranked', 0):>10}"
            )
        if len(moved) > top:
            lines.append(f"  ... {len(moved) - top} more families")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="W3-4 coverage movement between two discovery runs.")
    parser.add_argument("baseline", help="Baseline discovery run directory.")
    parser.add_argument("candidate", help="Candidate discovery run directory.")
    parser.add_argument(
        "--enrich", action="append", default=[], metavar="RUN_DIR",
        help="Recover parser identity by content hash from another run, for "
             "BOTH sides (a cache-served run carries no parser_id).")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument(
        "--fail-on-regression", action="store_true",
        help="Exit non-zero if any shared document moved down the ladder.")
    args = parser.parse_args(argv)

    baseline = load_run(args.baseline, enrich_parsers_from=args.enrich)
    candidate = load_run(args.candidate, enrich_parsers_from=args.enrich)
    report = compare(baseline, candidate)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json
          else render(report, top=args.top))
    if args.fail_on_regression and report["movement"].get("regressed"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
