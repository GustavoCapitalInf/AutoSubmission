"""l1s3_mutation_table.py — the mutation table for the taught surfaces.

    python -m tools.l1s3_mutation_table [--only M1 --only M3]

Six mutants, each ONE exact edit to one production file, each run against the
L1-S3 tests WITHOUT `-x` (so every failure is seen rather than the first) and
against `tools/l1s3_surface_census.py`, because for two of them the census is
the killer and a table that only ran the tests would report them as holes.

The four the card names are M1 to M4:

    M1  a reader that silently DROPS the accounts
    M2  a reader that AVERAGES two accounts
    M3  a reader that takes the FIRST account as the document — L1-C18's killer
    M4  a reader that reads the top-level `statement` on a document payload

M5 and M6 are the package's two rules, which are the ones a cross-account total
depends on:

    M5  membership stops requiring the account's OWN validation
    M6  the duplicate-content refusal removed

A mutant no test and no census fails on is a HOLE in the proof, and it is
reported as one.

HOST SAFETY (BATCH9-RULES), the same discipline `tools/l1s1_mutation_table.py`
established and for the same reasons:

* it refuses to start on a dirty tree — `git checkout --` is only correct on
  one, and so is any restore;
* the restore does NOT go through git. The failure the rule is about is git
  dying mid-restore under `index.lock` contention, so the original BYTES are
  read before the mutation and written back afterwards in a `finally` — no
  lock, nothing to contend for — and the restore is then VERIFIED by comparing
  the bytes back, with `git --no-optional-locks status --porcelain` as a second
  check that takes no lock either;
* it STOPS rather than going on to the next mutant if either check fails,
  because the one thing worse than an unproven mutant is a mutant left in a
  shared tree;
* it records how many other pythons were on the host while it ran, and refuses
  outright when one is working IN THIS WORKTREE.

PRIVACY. Nothing here reads a document. The table prints mutant ids, file
paths, test names and counts.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutant:
    id: str
    what: str
    file: str
    old: str
    new: str


MUTANTS: list[Mutant] = [
    Mutant(
        "M1", "the export renders the document block and DROPS every account",
        "webapp/app.py",
        "        for key, item in payload_document_block(analysis, surface=surface).items():",
        "        return []\n"
        "        for key, item in payload_document_block(analysis, surface=surface).items():",
    ),
    Mutant(
        "M2", "the document diagnosis AVERAGES its accounts' counts instead of "
              "summing them",
        "telemetry/diagnostics.py",
        "        counts[key] = sum(measured) if measured else None",
        "        counts[key] = sum(measured) // len(measured) if measured else None",
    ),
    Mutant(
        "M3", "the discovery row fills the account column from the FIRST "
              "account (L1-C18's killer)",
        "discovery/runner.py",
        "    row.account_last4 = None",
        "    row.account_last4 = _mask_last4("
        "(accounts[0].get(\"statement\") or {}).get(\"account_number\"))",
    ),
    Mutant(
        "M4", "the outcome function's refusal removed, so it reads the "
              "top-level `statement` of a document payload again",
        "telemetry/record.py",
        '    refuse_document_payload(payload, surface="telemetry/record.py::classify_outcome")\n',
        "",
    ),
    Mutant(
        "M5", "package membership stops requiring the account's OWN validation",
        "webapp/app.py",
        '            if outcome != "validated":',
        "            if False:",
    ),
    Mutant(
        "M6", "the package's duplicate-content refusal removed",
        "webapp/app.py",
        "        if len(set(digests)) != len(digests):",
        "        if False and len(set(digests)) != len(digests):",
    ),
]

TESTS = [
    "tests/test_payload_shape.py",
    "tests/test_document_outcome.py",
    "tests/test_l1s3_readers.py",
    "tests/test_l1s3_surfaces.py",
]


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def tree_is_clean() -> bool:
    return git("--no-optional-locks", "status", "--porcelain").stdout.strip() == ""


def other_pythons() -> list[str]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "ForEach-Object { $_.ProcessId.ToString() + ' ' + $_.CommandLine }"],
        capture_output=True, text=True).stdout
    mine = str(os.getpid())
    return [line.strip() for line in out.splitlines()
            if line.strip() and line.split(" ", 1)[0] != mine]


def a_python_is_working_in_this_tree() -> bool:
    here = str(ROOT).replace("\\", "/").lower()
    return any(here in line.replace("\\", "/").lower() for line in other_pythons())


def run_tests() -> tuple[int, list[str]]:
    """(exit code, failing test names). No `-x`: every failure is wanted."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header",
         "-p", "no:randomly"],
        cwd=ROOT, capture_output=True, text=True)
    failing = sorted(set(re.findall(r"^FAILED (\S+)", proc.stdout, re.MULTILINE)))
    return proc.returncode, failing


def run_census() -> int:
    proc = subprocess.run(
        [sys.executable, "tools/l1s3_surface_census.py"],
        cwd=ROOT, capture_output=True, text=True)
    return proc.returncode


def apply_mutant(mutant: Mutant) -> str:
    """Apply it, and return the ORIGINAL text so the restore needs no git."""
    path = ROOT / mutant.file
    text = path.read_text(encoding="utf-8")
    occurrences = text.count(mutant.old)
    if occurrences != 1:
        raise SystemExit(
            f"{mutant.id}: its target text occurs {occurrences} times in "
            f"{mutant.file}; a mutant that cannot be applied exactly as "
            f"documented is not a mutant")
    path.write_text(text.replace(mutant.old, mutant.new), encoding="utf-8")
    return text


def restore(mutant: Mutant, original: str) -> bool:
    """Write the original bytes back. No git, no lock, and verified."""
    path = ROOT / mutant.file
    for _ in range(3):
        try:
            path.write_text(original, encoding="utf-8")
        except OSError:  # OneDrive holds a handle now and then; retry
            continue
        if path.read_text(encoding="utf-8") == original:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the L1-S3 surface mutation table")
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    if not tree_is_clean():
        print("REFUSING: the working tree is dirty. This harness restores by "
              "writing bytes back and verifies against a clean tree.")
        return 2
    if a_python_is_working_in_this_tree():
        print("REFUSING: another python is working in this worktree.")
        return 2
    bystanders = len(other_pythons())

    chosen = [m for m in MUTANTS if not args.only or m.id in args.only]
    print("# L1-S3 — the mutation table")
    print()
    print(f"Tests: `{' '.join(TESTS)}` plus `tools/l1s3_surface_census.py`, "
          f"run without `-x`. Other pythons on the host at start: {bystanders}.")
    print()

    baseline_code, baseline_failing = run_tests()
    baseline_census = run_census()
    print(f"Baseline: tests exit {baseline_code} "
          f"({len(baseline_failing)} failing), census exit {baseline_census}.")
    print()
    if baseline_code != 0 or baseline_census != 0:
        print("REFUSING: the baseline is not green, so no kill can be attributed.")
        return 2

    print("| mutant | what it does | file | tests | census | killers |")
    print("|---|---|---|---|---:|---|")
    holes: list[str] = []
    for mutant in chosen:
        original = apply_mutant(mutant)
        try:
            code, failing = run_tests()
            census = run_census()
        finally:
            # No `return` in the `finally` — that would swallow whatever went
            # wrong inside the `try`, and what went wrong is the thing a
            # mutation harness most needs to say out loud.
            restored = restore(mutant, original)
        if not restored:
            print()
            print(f"**STOPPED**: {mutant.id} could not be restored in "
                  f"{mutant.file}. The tree may hold a mutant.")
            return 3
        if not tree_is_clean():
            print()
            print(f"**STOPPED**: the tree is dirty after {mutant.id}.")
            return 3
        killed = code != 0 or census != 0
        if not killed:
            holes.append(mutant.id)
        names = ", ".join(f"`{name.split('::')[-1]}`" for name in failing[:4])
        if len(failing) > 4:
            names += f", +{len(failing) - 4} more"
        print(f"| {mutant.id} | {mutant.what} | `{mutant.file}` | "
              f"{'FAIL' if code else 'pass'} ({len(failing)}) | {census} | "
              f"{names or '—'} |")
    print()
    if holes:
        print(f"**HOLES**: {', '.join(holes)} — no test and no census failed on "
              f"these, which is a gap in the proof, not a property of the code.")
        return 1
    print(f"Every mutant killed: {len(chosen)} / {len(chosen)}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
