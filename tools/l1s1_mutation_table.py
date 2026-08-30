"""l1s1_mutation_table.py — the mutation table for the document wrapper.

    python -m tools.l1s1_mutation_table [--only M1 --only M3] \
        [--seam-probe --run <run> --data-dir <cold cache> --baseline <base capture>] \
        [--scratch <private dir>]

Ten mutants, each a single exact edit to one production file, each run against
the wrapper's own tests WITHOUT `-x` so every failure is seen rather than the
first one. A mutant that no test fails on is a hole in the tests, and it is
reported as one.

Four of the ten are also run through `tools/l1s1_seam_probe.py` over the whole
232-document / 80-registration cohort, because for those four the interesting
question is not whether a unit test fails but whether the ARCHIVE-SCALE BYTE
COMPARISON sees them:

    M1  an added key            — expected to move every document
    M2  a reordered flag tuple  — expected to move NONE, and that is the point:
                                  the cohort cannot kill it, the constructed
                                  fixture must, and the order is pinned by the
                                  corpus gate rather than by this cohort
    M3  the document-scope flags dropped from the account block — expected to
                                  move the few documents that carry one
    M4  an account's value in a document field — expected to move NONE, because
                                  RULE S does not publish the document block at
                                  all; again the fixture is the killer

HOST SAFETY (BATCH9-RULES). It refuses to start on a dirty tree; it restores in
a `finally` that ignores the restore's exit code and then VERIFIES the tree is
clean before returning, because a harness that restores with `git checkout --`
can leave a mutant behind when git dies mid-run; and it refuses to run while
another python process is on the host.

PRIVACY. Nothing here reads a document. The table prints mutant ids, file
paths, test names and counts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RULE_S_RETURN = "        return report_to_dict(document.accounts[0])"

NAIVE_ASSEMBLY = (
    "        published = report_to_dict(document.accounts[0])\n"
    "        from .pipeline import split_integrity_flags\n"
    "        scopes = split_integrity_flags(published[\"integrity\"][\"flags\"])\n"
    "        published[\"integrity\"][\"flags\"] = scopes[0] + scopes[1]\n"
    "        return published"
)

DROPPED_ASSEMBLY = (
    "        published = report_to_dict(document.accounts[0])\n"
    "        from .pipeline import split_integrity_flags\n"
    "        scopes = split_integrity_flags(published[\"integrity\"][\"flags\"])\n"
    "        published[\"integrity\"][\"flags\"] = scopes[1]\n"
    "        return published"
)

ADDED_KEY = (
    "        published = report_to_dict(document.accounts[0])\n"
    "        published[\"document\"] = {\"account_count\": len(document.accounts)}\n"
    "        return published"
)

FOUR_CLAUSES = (
    "    return (\n"
    "        len(document.accounts) == 1\n"
    "        and not document.omissions\n"
    "        and document.rollup is None\n"
    "        and document.boundary_mechanism is None\n"
    "    )"
)

ONE_CLAUSE = "    return len(document.accounts) == 1"

NO_ACCOUNT_REFUSAL = (
    "    if not document.accounts:\n"
    "        raise ValueError(\n"
    "            \"a document object with no account may not be published \"\n"
    "            \"(document_publishes_no_account)\"\n"
    "        )\n"
)

DUPLICATE_REFUSAL = (
    "    digests = [_account_content_digest(account) for account in accounts]\n"
    "    if len(set(digests)) != len(digests):\n"
    "        raise ValueError(\n"
    "            \"two accounts of one document publish identical content; a \"\n"
    "            \"duplicate section would be double-counted by every cross-account \"\n"
    "            \"total (document_publishes_duplicate_account)\"\n"
    "        )\n"
)

ACCOUNTS_LINE = "    accounts = [report_to_dict(account) for account in document.accounts]"

SORTED_ACCOUNTS = (
    "    accounts = [report_to_dict(account) for account in document.accounts]\n"
    "    accounts.sort(key=lambda account: json.dumps(account, sort_keys=True, default=str))"
)

DOCUMENT_KEY = '        "document": {'
DOCUMENT_KEY_WITH_STATEMENT = '        "statement": accounts[0],\n        "document": {'

SCOPE_SET = (
    "DOCUMENT_SCOPE_FLAGS: frozenset[str] = frozenset({\n"
    "    \"parser_ambiguous\",\n"
    "    \"parser_exception\",\n"
    "    \"repair_exception\",\n"
    "    \"integrity_check_exception\",\n"
    "    \"missing_declared_statement_page\",\n"
    "})"
)

EMPTY_SCOPE_SET = "DOCUMENT_SCOPE_FLAGS: frozenset[str] = frozenset()"

SEAM_RETURN = "    return DocumentReport(accounts=[report])"

SEAM_RETURN_LEAKING = (
    "    return DocumentReport(accounts=[report], document_period=(\n"
    "        report.statement.period_start, report.statement.period_end))"
)


@dataclass
class Mutant:
    id: str
    what: str
    file: str
    old: str
    new: str
    #: the cohort-scale byte comparison is run for this mutant, and this is what
    #: it is expected to see — `None` means the probe is not run for it
    expect_cohort_movers: str | None = None
    killers: list[str] = field(default_factory=list)


MUTANTS: list[Mutant] = [
    Mutant("M1", "RULE S adds a key to the single-account payload",
           "analysis/serialization.py", RULE_S_RETURN, ADDED_KEY,
           expect_cohort_movers="every document"),
    Mutant("M2", "the account's flag list is assembled as document-scope then "
                 "account-scope instead of preserving published order",
           "analysis/serialization.py", RULE_S_RETURN, NAIVE_ASSEMBLY,
           expect_cohort_movers="none — the fixture is the killer"),
    Mutant("M3", "the document-scope flags LEAVE the account block (the design's "
                 "prose read literally)",
           "analysis/serialization.py", RULE_S_RETURN, DROPPED_ASSEMBLY,
           expect_cohort_movers="the documents carrying one"),
    Mutant("M4", "an account's period is written into the document's period field",
           "analysis/pipeline.py", SEAM_RETURN, SEAM_RETURN_LEAKING,
           expect_cohort_movers="none — RULE S publishes no document block"),
    Mutant("M5", "RULE S weakened from four clauses to 'one account'",
           "analysis/serialization.py", FOUR_CLAUSES, ONE_CLAUSE),
    Mutant("M6", "the no-account refusal removed",
           "analysis/serialization.py", NO_ACCOUNT_REFUSAL, ""),
    Mutant("M7", "the duplicate-account refusal removed",
           "analysis/serialization.py", DUPLICATE_REFUSAL, ""),
    Mutant("M8", "the published accounts are sorted instead of printed order",
           "analysis/serialization.py", ACCOUNTS_LINE, SORTED_ACCOUNTS),
    Mutant("M9", "the document shape also publishes a top-level `statement`",
           "analysis/serialization.py", DOCUMENT_KEY, DOCUMENT_KEY_WITH_STATEMENT),
    Mutant("M10", "the document-scope flag set is emptied",
           "analysis/pipeline.py", SCOPE_SET, EMPTY_SCOPE_SET),
]

TESTS = ["tests/test_document_report.py"]


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def tree_is_clean() -> bool:
    return git("status", "--porcelain").stdout.strip() == ""


def another_python_is_running() -> bool:
    """A mutation harness may not share the host with another python process."""
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe"],
                         capture_output=True, text=True).stdout
    return len(re.findall(r"^python\.exe", out, re.MULTILINE)) > 1


def wait_for_a_free_host(minutes: int) -> bool:
    """Poll, bounded, for the host to be free. Refusing is the fallback.

    This machine is shared with another cell, so "no other python" is a state
    to WAIT for rather than a precondition to assume — and a bounded poll is
    the only honest way to wait: an unbounded one would hang a proof on another
    cell's schedule with nothing in the log to say so.
    """
    deadline = time.monotonic() + minutes * 60
    while another_python_is_running():
        if time.monotonic() >= deadline:
            return False
        time.sleep(20)
    return True


def run_tests() -> tuple[int, list[str]]:
    """(exit code, failing test names). No `-x`: every failure is wanted."""
    proc = subprocess.run([sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header",
                           "-p", "no:randomly"],
                          cwd=ROOT, capture_output=True, text=True)
    failing = sorted(set(re.findall(r"^FAILED (\S+)", proc.stdout, re.MULTILINE)))
    return proc.returncode, failing


def run_seam_probe(args, mutant_id: str) -> tuple[int, str]:
    scratch = Path(args.scratch)
    capture = scratch / f"seam_mutant_{mutant_id}.json"
    log = scratch / f"seam_mutant_{mutant_id}.log"
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-m", "tools.l1s1_seam_probe",
         "--run", str(args.run), "--data-dir", str(args.data_dir),
         "--per-parser", "3", "--capture", str(capture),
         "--baseline", str(args.baseline), "--label", f"mutant {mutant_id}"],
        cwd=ROOT, capture_output=True, text=True, env=env)
    log.write_text(proc.stdout + "\n" + proc.stderr + f"\nEXIT={proc.returncode}\n",
                   encoding="utf-8")
    moved = re.search(r"^MOVED_TOTAL=(\d+)", proc.stdout, re.MULTILINE)
    detail = re.search(r"payload moved \| (\d+) \|", proc.stdout)
    return (int(moved.group(1)) if moved else -1), (detail.group(1) if detail else "?")


def apply_mutant(mutant: Mutant) -> None:
    path = ROOT / mutant.file
    text = path.read_text(encoding="utf-8")
    occurrences = text.count(mutant.old)
    if occurrences != 1:
        raise SystemExit(
            f"{mutant.id}: its target text occurs {occurrences} times in "
            f"{mutant.file}; a mutant that cannot be applied exactly as "
            f"documented is not a mutant")
    path.write_text(text.replace(mutant.old, mutant.new), encoding="utf-8")


def restore(mutant: Mutant) -> None:
    git("checkout", "--", mutant.file)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the L1-S1 wrapper mutation table")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--seam-probe", action="store_true")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--wait-minutes", type=int, default=0,
                        help="poll, bounded, for a host with no other python on it")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    if not tree_is_clean():
        print("REFUSED: the working tree is dirty. This harness restores with "
              "`git checkout --`, which is only correct on a clean tree.")
        return 3
    if another_python_is_running() and not wait_for_a_free_host(args.wait_minutes):
        print("REFUSED: another python process is on this host. Two harnesses "
              "at once is how a mutant survives a restore.")
        return 3
    if args.seam_probe and not (args.run and args.data_dir and args.baseline and args.scratch):
        print("REFUSED: --seam-probe needs --run, --data-dir, --baseline and --scratch.")
        return 3

    chosen = [m for m in MUTANTS if not args.only or m.id in args.only]
    results = []
    for mutant in chosen:
        applied = False
        try:
            apply_mutant(mutant)
            applied = True
            code, failing = run_tests()
            probe: tuple[int, str] | None = None
            if args.seam_probe and mutant.expect_cohort_movers is not None:
                probe = run_seam_probe(args, mutant.id)
        finally:
            if applied:
                restore(mutant)
        if not tree_is_clean():
            print(f"STOPPED after {mutant.id}: the tree did not come back clean. "
                  f"Restore by hand before anything else runs here.")
            return 4
        results.append({"id": mutant.id, "what": mutant.what, "file": mutant.file,
                        "killed": code != 0, "killers": failing,
                        "probe_moved": (probe[0] if probe else None),
                        "probe_rule_s_moved": (probe[1] if probe else None),
                        "expected_cohort": mutant.expect_cohort_movers})

    print("# L1-S1 — mutation table over the document wrapper")
    print()
    print(f"Tests run per mutant, without `-x`: `{' '.join(TESTS)}`")
    print()
    print("| mutant | what it does | file | killed | killed by |")
    print("|---|---|---|:---:|---|")
    for row in results:
        killers = ", ".join(f"`{name.split('::')[-1]}`" for name in row["killers"][:4])
        if len(row["killers"]) > 4:
            killers += f" (+{len(row['killers']) - 4} more)"
        print(f"| **{row['id']}** | {row['what']} | `{row['file']}` | "
              f"{'YES' if row['killed'] else '**NO**'} | {killers or '—'} |")
    print()
    if any(row["probe_moved"] is not None for row in results):
        print("## What the cohort-scale BYTE comparison sees (232 documents / 80 registrations)")
        print()
        print("| mutant | documents moved | of them, RULE S payload moved | expected |")
        print("|---|---:|---:|---|")
        for row in results:
            if row["probe_moved"] is None:
                continue
            print(f"| **{row['id']}** | {row['probe_moved']} | "
                  f"{row['probe_rule_s_moved']} | {row['expected_cohort']} |")
        print()
    survivors = [row["id"] for row in results if not row["killed"]]
    print(f"MUTANTS={len(results)} KILLED={len(results) - len(survivors)} "
          f"SURVIVED={len(survivors)}")
    if survivors:
        print(f"SURVIVORS={','.join(survivors)}")
    if args.scratch:
        (Path(args.scratch) / "mutation_table.json").write_text(
            json.dumps(results, indent=1), encoding="utf-8")
    return 0 if not survivors else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
