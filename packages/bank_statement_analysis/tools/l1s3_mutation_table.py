"""l1s3_mutation_table.py — the mutation table for the taught surfaces.

    python -m tools.l1s3_mutation_table [--only M1 --only M3]

Twelve mutants, each ONE exact edit to one production file, each run against the
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


def _lines(*parts: str) -> str:
    """A multi-line mutant anchor, joined at runtime.

    Never an escape inside a literal: a shell heredoc turned `\\n` into a real
    newline here once already, and a mutant anchor that cannot be applied
    exactly as documented is not a mutant (BATCH9-RULES).
    """
    return "\n".join(parts)


#: pytest exit codes that mean the tests never ran. None of them is evidence
#: that a mutant was killed (L1-S3 review, MINOR-7).
DID_NOT_RUN_EXITS = frozenset({2, 3, 4, 5})


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
    Mutant(
        "M7", "the package's member-set check removed, so a per-period average "
              "is published over two accounts of ONE document",
        "webapp/app.py",
        "    refuse_cross_account_averages = bool(documents_with_several_members)",
        "    refuse_cross_account_averages = False",
    ),
    # M8-M10 are the L1-S3 review's own mutant, at the three refusal sites it
    # found untested: the refusal LEFT IN PLACE but moved into a dead branch.
    # The review proved all three passed the whole 7,578-test suite and both
    # censuses. They are killed twice now — by a test, and by the census, whose
    # forward check no longer walks into a constant-false branch.
    Mutant(
        "M8", "the balance audit's refusal moved into a dead branch (the LEGACY "
              "INDEXING path)",
        "balance_forensic_audit.py",
        _lines(
            '    refuse_document_payload(',
            '        payload, surface="balance_forensic_audit.py::audit_source")',
        ),
        _lines(
            '    if False:',
            '        refuse_document_payload(',
            '            payload, surface="balance_forensic_audit.py::audit_source")',
        ),
    ),
    Mutant(
        "M9", "the ADB audit's refusal moved into a dead branch",
        "adb_forensic_audit.py",
        '    refuse_document_payload(payload, surface="adb_forensic_audit.py::audit_one")',
        _lines(
            '    if False:',
            '        refuse_document_payload(payload, surface="adb_forensic_audit.py::audit_one")',
        ),
    ),
    # M11 and M12 are the two directions of RULE S's clause, which the
    # L1-S3 / L1-S2 composition corrected to the account count alone. M11 is
    # the exact regression that broke the composed tree.
    Mutant(
        "M11", "RULE S regains the omission clause, so a SINGLE-account document "
               "carrying one flips to the document shape (the composition defect)",
        "analysis/serialization.py",
        "    return len(document.accounts) == 1",
        "    return len(document.accounts) == 1 and not document.omissions",
    ),
    Mutant(
        "M12", "RULE S loses its account-count condition, so a TWO-account "
               "document publishes its first account as the whole document",
        "analysis/serialization.py",
        "    return len(document.accounts) == 1",
        "    return True",
    ),
    Mutant(
        "M10", "the gate's currency-provenance refusal moved into a dead branch",
        "corpus_gate.py",
        _lines(
            '        refuse_document_payload(',
            '            payload, surface="corpus_gate.py::check_currency_source")',
        ),
        _lines(
            '        if False:',
            '            refuse_document_payload(',
            '                payload, surface="corpus_gate.py::check_currency_source")',
        ),
    ),
]

TESTS = [
    "tests/test_payload_shape.py",
    "tests/test_document_outcome.py",
    "tests/test_l1s3_readers.py",
    "tests/test_l1s3_surfaces.py",
    # S1's wrapper pins. RULE S's clause is serialized shape, so its mutants are
    # killed here rather than by a reader test.
    "tests/test_document_report.py",
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
    did_not_run: list[str] = []
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
        # L1-S3 review, MINOR-7. `code != 0` counted a NON-RUN as a kill:
        # pytest exits 2 (interrupted), 3 (internal error), 4 (usage) and 5 (no
        # tests collected) are all non-zero and none of them is evidence that
        # anything failed. A kill is exit 1 WITH at least one named failing
        # test, or a census that went red. Anything else is DID_NOT_RUN and is
        # excluded from the score rather than counted for it.
        if code in DID_NOT_RUN_EXITS:
            did_not_run.append(f"{mutant.id} (pytest exit {code})")
            outcome = f"DID NOT RUN ({code})"
            killed = False
        else:
            killed = (code == 1 and bool(failing)) or census != 0
            outcome = f"{'FAIL' if code else 'pass'} ({len(failing)})"
            if not killed:
                holes.append(mutant.id)
        names = ", ".join(f"`{name.split('::')[-1]}`" for name in failing[:4])
        if len(failing) > 4:
            names += f", +{len(failing) - 4} more"
        print(f"| {mutant.id} | {mutant.what} | `{mutant.file}` | "
              f"{outcome} | {census} | {names or '—'} |")
    print()
    if did_not_run:
        print(f"**DID NOT RUN**: {', '.join(did_not_run)} — pytest exited "
              f"without running the tests. That is not a kill, and it is not a "
              f"hole either: nothing is scored for these. Re-run them.")
        return 2
    if holes:
        print(f"**HOLES**: {', '.join(holes)} — no test and no census failed on "
              f"these, which is a gap in the proof, not a property of the code.")
        return 1
    print(f"Every mutant killed: {len(chosen)} / {len(chosen)}, each by a NAMED "
          f"failing test or a red census.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
