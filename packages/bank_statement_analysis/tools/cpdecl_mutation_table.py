"""cpdecl_mutation_table.py — every gate this card added or touched, killed.

    python -m tools.cpdecl_mutation_table [--only M3] [--json <private>.json]

Each row of `tools/cpdecl_mutants.py` breaks ONE decision in the production
source, runs the tests that exist for it WITHOUT `-x`, and requires that a NAMED
test fails. A test named after a gate is not a test of that gate; the mutant is.

The table lives in its own module because every row is an exact excerpt of
production source: it has to be written and read with a file tool, never through
a shell heredoc, and holding it apart makes that rule enforceable by looking.

Host safety, in the shape BATCH9-RULES asks for after a batch-8 harness left a
mutant in a working tree:

* it REFUSES to start on a dirty tree — a restore cannot be verified against a
  baseline that was already dirty;
* it restores in a `finally` whose exit code is ignored, and then VERIFIES
  `git status --porcelain` is clean before moving to the next row. A restore
  that did not take stops the run rather than poisoning the next measurement;
* it edits by EXACT string replacement and refuses unless the old text occurs
  exactly once, so a mutant can never silently apply somewhere else.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.cpdecl_mutants import MUTANTS, Mutant  # noqa: E402  (path set above)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def tree_is_clean() -> bool:
    return not git("status", "--porcelain").stdout.strip()


def failures(tests: tuple[str, ...]) -> set[str]:
    """The names of the tests that FAILED. Run without `-x`: a mutant that
    kills its own row and nothing else is a different finding from one that
    takes the file down with it, and `-x` hides which it was."""
    done = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--no-header", "-p", "no:randomly"],
        capture_output=True, text=True)
    found: set[str] = set()
    for line in done.stdout.splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            name = line.split(" ", 1)[1].split(" ")[0]
            found.add(name.rsplit("::", 1)[-1])
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    if not tree_is_clean():
        print("REFUSING: the working tree is dirty; a restore cannot be verified")
        return 3

    table = []
    exit_code = 0
    for mutant in MUTANTS:
        if args.only and mutant.id not in args.only:
            continue
        path = Path(mutant.path)
        source = path.read_text(encoding="utf-8")
        occurrences = source.count(mutant.old)
        if occurrences != 1:
            print(f"{mutant.id}: REFUSING — the mutated text occurs {occurrences} times")
            table.append({"id": mutant.id, "gate": mutant.gate, "result": "not-applied"})
            exit_code = 4
            continue
        row = {"id": mutant.id, "gate": mutant.gate, "path": mutant.path,
               "killer": mutant.killer}
        try:
            path.write_text(source.replace(mutant.old, mutant.new, 1), encoding="utf-8")
            failed = failures(mutant.tests)
            row["failed_tests"] = sorted(failed)
            row["killed"] = mutant.killer in failed
        finally:
            git("checkout", "--", mutant.path)
        if not tree_is_clean():
            print(f"{mutant.id}: RESTORE FAILED — stopping with a dirty tree")
            row["restore"] = "FAILED"
            table.append(row)
            return 5
        row["restore"] = "clean"
        if not row.get("killed"):
            exit_code = 1
        table.append(row)
        print(f"{mutant.id:4s} {'KILLED' if row.get('killed') else 'SURVIVED':9s} "
              f"by {mutant.killer} (+{len(row['failed_tests']) - 1} other) — {mutant.gate}")

    print()
    print("| mutant | gate | killer | other failures | result |")
    print("|---|---|---|---:|---|")
    for row in table:
        if "failed_tests" not in row:
            print(f"| {row['id']} | {row['gate']} | — | — | NOT APPLIED |")
            continue
        print(f"| {row['id']} | {row['gate']} | `{row['killer']}` | "
              f"{len(row['failed_tests']) - (1 if row['killed'] else 0)} | "
              f"{'KILLED' if row['killed'] else 'SURVIVED'} |")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(table, indent=1), encoding="utf-8")
    print(f"EXIT={exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
