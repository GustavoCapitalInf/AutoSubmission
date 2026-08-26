"""The card's mutation table, run and ATTRIBUTED — killed, survived, and by what.

W3 §GLANCE, review closure 3. §GL6 published a `killed by` column naming the
gate that rejects each mutant, and nothing committed asserted it: the suite's
`test_every_gate_is_killed_by_its_own_mutant` asserts only that the mutated
document is declined, never by WHICH gate — so a mutant killed by an unrelated
gate would have reported as covered. This instrument produces that column.

WHAT A MUTANT IS HERE. This card's table (`tests/test_category_partition.py`,
`MUTANTS`) mutates the DOCUMENT, not the reader: each row transforms an
invented statement the way its description says and states the outcome the
reader owes — `detect` must not claim it, `parse` must decline it, or (the
control arms) it must publish a statement IDENTICAL to the unmutated one. So
nothing tracked is ever written by this tool, and the batch-7 harness lesson is
met by construction rather than by a `git checkout --`: the tree is verified
CLEAN of tracked modifications before the run and verified clean again after
it, and the run refuses to start otherwise. A table measured against an
uncommitted edit describes a tree nobody will ever see.

THE TWO ARMS, both reported per row.

1. **Attribution**, in process. Every gate function of the reader is wrapped on
   the module object and the FIRST one to return its rejecting value is
   recorded; the wrappers are removed afterwards. A row whose refusal comes
   from no wrapped gate is attributed to `parse` itself, which is the truthful
   answer for the two mutants that trip the per-day-oracle rule — a rule that
   lives in `parse` and is not a function.

2. **The branch's own test**, on disk. Each row's parametrized test node is run
   under `pytest` in its own process and its verdict recorded, so "killed" is
   the committed suite's word and not only this tool's. `--no-pytest` skips
   that arm for a quick attribution-only pass.

A SURVIVOR IS DISCLOSED, never dropped: any row whose document still publishes
when its row says it must not, or whose control arm changed the published
statement, is printed in the summary and named in the exit status.

    python -m tools.glance_mutation_table [--no-pytest] [--out table.json]

Read-only over the archive — it never touches it — and $0: the documents are
the module's own invented fixtures.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

#: Every gate of the reader, with the value that means "this one refused". The
#: order here is documentation; the ORDER OF REJECTION is measured at runtime.
GATES: tuple[tuple[str, str], ...] = (
    ("_entries", "none"),
    ("_period", "none"),
    ("_summary", "none"),
    ("_unified_rows", "none"),
    ("_sectioned_rows", "none"),
    ("_recap_pairs", "none"),
    ("_reprints", "false"),
    ("_matches_the_printed_partition", "false"),
    ("_matches_the_relationship_block", "false"),
    ("_grid_seed", "false"),
    ("_grid", "none"),
    ("_matches_the_printed_grid", "false"),
    ("_walks_to_the_printed_ending", "false"),
)

#: The refusal that is not a function: `parse` publishes nothing when a
#: document offers no per-day oracle at all.
THE_ORACLE_RULE = "parse (the per-day-oracle rule)"

TEST_FILE = "tests/test_category_partition.py"
TEST_NODE = "test_every_gate_is_killed_by_its_own_mutant"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-pytest", action="store_true",
                        help="skip the on-disk arm (attribution only)")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def tracked_modifications() -> str:
    """The tracked files this tree has changed. Untracked files are not in it:
    an unstaged NEW file cannot change what the reader does, and the logs and
    the reports of a proof round are exactly that."""
    return subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        check=True, stdout=subprocess.PIPE, text=True,
    ).stdout.strip()


def attribute(module, document: str) -> tuple[bool, str | None, object]:
    """`(claims, first gate to refuse, statement)` for one document.

    The gates are wrapped on the module object, so this measures the calls the
    reader itself makes — not a second reading of the document written here.
    """
    refusals: list[str] = []
    originals = {name: getattr(module, name) for name, _ in GATES}

    def wrap(name: str, kind: str):
        original = originals[name]

        def wrapper(*args, **kwargs):
            result = original(*args, **kwargs)
            refused = result is None if kind == "none" else result is False
            if refused:
                refusals.append(name)
            return result
        return wrapper

    for name, kind in GATES:
        setattr(module, name, wrap(name, kind))
    try:
        claims = module.detect(document).claims
        statement = module.parse_category_partition_statement(document)
    finally:
        for name, original in originals.items():
            setattr(module, name, original)
    if not claims:
        return False, "detect", None
    if statement is not None:
        return True, None, statement
    return True, (refusals[0] if refusals else THE_ORACLE_RULE), None


def run_the_test(mutant_id: str) -> tuple[str, str]:
    """The committed suite's own verdict on one row, in its own process."""
    node = f"{TEST_FILE}::{TEST_NODE}[{mutant_id}]"
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=no", node],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    return ("passed" if finished.returncode == 0 else "FAILED"), node


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()

    dirty = tracked_modifications()
    if dirty:
        print("REFUSED: the tree carries uncommitted changes to tracked files.\n"
              "A mutation table measured against an edit describes a tree nobody\n"
              "will ever see. Commit or stash first:\n" + dirty, file=sys.stderr)
        return 2

    from analysis import category_partition as cp
    from tests.test_category_partition import MUTANTS

    rows: list[dict[str, object]] = []
    survivors: list[str] = []
    for mutant in MUTANTS:
        base = mutant.base()
        mutated = mutant.mutate(base)
        baseline_claims, baseline_gate, baseline = attribute(cp, base)
        claims, gate, statement = attribute(cp, mutated)

        if mutated == base or baseline is None:
            verdict, killed_by = "TABLE DEFECT", baseline_gate or "the base does not publish"
        elif mutant.expect == "detect":
            verdict = "killed" if not claims else "SURVIVED"
            killed_by = "detect" if not claims else ""
        elif mutant.expect == "same":
            same = statement is not None and (
                statement.model_dump() == baseline.model_dump())
            verdict = "control holds" if same else "CONTROL BROKE"
            killed_by = "publishes, identical" if same else (gate or "changed the payload")
        else:
            verdict = "killed" if statement is None else "SURVIVED"
            killed_by = gate or ""
        if verdict in {"SURVIVED", "CONTROL BROKE", "TABLE DEFECT"}:
            survivors.append(f"{mutant.id} ({mutant.gate}): {verdict}")

        row = {
            "id": mutant.id,
            "gate": mutant.gate,
            "verdict": verdict,
            "killed_by": killed_by,
            "documented_gate": mutant.gate.split(":")[0],
        }
        if not args.no_pytest:
            row["suite"], row["node"] = run_the_test(mutant.id)
            if row["suite"] != "passed":
                survivors.append(f"{mutant.id}: the committed suite reports {row['suite']}")
        rows.append(row)

    still_clean = tracked_modifications()
    report = {
        "mutants": sum(1 for m in MUTANTS if m.expect != "same"),
        "controls": sum(1 for m in MUTANTS if m.expect == "same"),
        "killed": sum(1 for r in rows if r["verdict"] == "killed"),
        "controls_holding": sum(1 for r in rows if r["verdict"] == "control holds"),
        "survivors": survivors,
        "distinct_killers": sorted({str(r["killed_by"]) for r in rows if r["killed_by"]}),
        "suite_arm": "skipped" if args.no_pytest else "run per row",
        "tree_clean_before": True,
        "tree_clean_after": not still_clean,
        "seconds": round(time.perf_counter() - started, 1),
    }

    print(json.dumps(report, indent=1, sort_keys=True))
    print()
    print("| id | gate | killed by | verdict |")
    print("|---|---|---|---|")
    for row in rows:
        print(f"| {row['id']} | {row['gate']} | "
              f"{('`' + str(row['killed_by']) + '`') if row['killed_by'] else ''} | "
              f"{row['verdict']} |")
    if args.out is not None:
        args.out.write_text(json.dumps({"report": report, "rows": rows}, indent=1),
                            encoding="utf-8")
    if still_clean:
        print("\nTREE DIRTIED BY THE RUN: " + still_clean, file=sys.stderr)
        return 3
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main())
