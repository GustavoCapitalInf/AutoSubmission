"""cpdecl_mutation_table.py — every gate this card added or touched, killed.

    python -m tools.cpdecl_mutation_table [--only M3] [--json <private>.json]

Each row below breaks ONE decision in the production source, runs the tests
that exist for it WITHOUT `-x`, and requires that a NAMED test fails. A test
named after a gate is not a test of that gate; the mutant is.

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
from dataclasses import dataclass
from pathlib import Path

ENCLOSURES = "analysis/core_processor_enclosures.py"
PARTITION = "analysis/category_partition.py"
T_ENCLOSURES = "tests/test_core_processor_enclosures.py"
T_PARTITION = "tests/test_category_partition.py"


@dataclass(frozen=True)
class Mutant:
    id: str
    gate: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    #: The test that MUST fail. A row whose killer survives is a gate this
    #: branch added without a test, and the run fails.
    killer: str


MUTANTS: tuple[Mutant, ...] = (
    # --- core_processor_enclosures._without_non_opening_dates --------------
    Mutant(
        "M1", "the rule itself: a date that opens no row is read as one",
        ENCLOSURES,
        "    dates = list(_DATE_RE.finditer(run))\n"
        "    blanked: list[str] = []",
        "    dates = []\n"
        "    blanked: list[str] = []",
        (T_ENCLOSURES,),
        "test_a_date_with_another_date_before_the_next_amount_opens_no_row",
    ),
    Mutant(
        "M2", "the bound: a run that STOPS mid-row must still be refused",
        ENCLOSURES,
        "    for index, found in enumerate(dates[:-1]):\n"
        "        stop = dates[index + 1].start()",
        "    for index, found in enumerate(dates):\n"
        "        stop = (dates[index + 1].start() if index + 1 < len(dates)\n"
        "                else len(run))",
        (T_ENCLOSURES,),
        "test_a_run_that_ends_on_a_date_closing_no_cell_is_still_declined",
    ),
    Mutant(
        "M3", "WHICH token is blanked: the one that closes no cell, never the "
              "one that opens the row",
        ENCLOSURES,
        "        blanked.append(run[cursor:found.start(1)])\n"
        "        blanked.append(\" \" * len(found.group(1)))\n"
        "        cursor = found.end(1)",
        "        opener = dates[index + 1]\n"
        "        blanked.append(run[cursor:opener.start(1)])\n"
        "        blanked.append(\" \" * len(opener.group(1)))\n"
        "        cursor = opener.end(1)",
        (T_ENCLOSURES,),
        "test_the_blanked_token_can_never_move_a_row_onto_the_wrong_day",
    ),
    Mutant(
        "M4", "the test itself: a date that DOES close a cell must be left alone",
        ENCLOSURES,
        "        if _LEDGER_FIGURE_RE.search(run[found.end():stop]) is not None:\n"
        "            continue",
        "        if _LEDGER_FIGURE_RE.search(run[found.end():stop]) is None:\n"
        "            continue",
        (T_ENCLOSURES,),
        "test_a_complete_statement_publishes_every_printed_figure",
    ),
    Mutant(
        "M5", "blanked, not removed: the run keeps every other character",
        ENCLOSURES,
        "        blanked.append(run[cursor:found.start(1)])\n"
        "        blanked.append(\" \" * len(found.group(1)))\n"
        "        cursor = found.end(1)",
        "        blanked.append(run[cursor:found.start(1)])\n"
        "        cursor = stop",
        (T_ENCLOSURES,),
        "test_a_date_with_another_date_before_the_next_amount_opens_no_row",
    ),
    # --- category_partition: the per-day evidence rule ---------------------
    Mutant(
        "M6", "the ADB doctrine's decision is not the reader's: a document "
              "printing no per-day evidence must still publish",
        PARTITION,
        "    if unified and not _walks_to_the_printed_ending(rows, summary):\n"
        "        return None\n",
        "    if unified and not _walks_to_the_printed_ending(rows, summary):\n"
        "        return None\n"
        "    if grid is None and not unified:\n"
        "        return None\n",
        (T_PARTITION,),
        "test_a_collected_grids_cells_are_never_published_on_the_sectioned_issue",
    ),
    Mutant(
        "M7", "the collected grid's CELLS are still never read",
        PARTITION,
        "    if _LEDGER_GRID_HEADING in sections:\n"
        "        grid = _grid(sections[_LEDGER_GRID_HEADING], summary=summary)",
        "    if _LEDGER_GRID_HEADING in sections or _COLLECTED_GRID_HEADING in sections:\n"
        "        grid = _grid(sections.get(_LEDGER_GRID_HEADING)\n"
        "                     or sections[_COLLECTED_GRID_HEADING], summary=summary)",
        (T_PARTITION,),
        "test_a_collected_grid_cell_is_never_published_as_a_daily_balance",
    ),
)


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
    print(f"| mutant | gate | killer | other failures | result |")
    print(f"|---|---|---|---:|---|")
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
