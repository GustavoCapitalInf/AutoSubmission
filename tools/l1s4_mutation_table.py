"""l1s4_mutation_table.py — every gate this card wrote, removed one at a time.

    python -m tools.l1s4_mutation_table [--only C1 --only Q3C4]

A test named after a gate is not a test of that gate. Each mutant below is ONE
exact edit that removes ONE condition from production, and the table records
which named test failed for it. A mutant nothing fails on is a HOLE in the
proof, reported as one and never as a property of the code.

Three families, and each is a thing this card wrote:

* **the publisher's fail-closed conditions** (design §4's L1-C1 … L1-C13, as
  they became code in `analysis/member_statement.py`): the printed
  reappearance in both directions, the disjointness of the sections, the
  distinctness of the identities, L1-C5's column caption, the section's own
  figures agreeing with the table's, the cross-account total as an oracle, the
  ledger accounting for every printed dated row, the running balance checking
  the printed direction, the stated totals being FED, and absence never being a
  ground;
* **the seven Q3 conditions** in `analysis/sibling_omission.py`, one clause at a
  time. The archive half of this is `tools/l1s4_q3_oracle.py`, which runs the
  class against the probe that measured it and against that probe's own five
  mutants; these are the conditions the probe's mutants do not separate;
* **R-d's four clauses** in `analysis/pipeline.py`, and the package's two rules.

HOST SAFETY (BATCH9-RULES). The harness refuses to start on a dirty tree or
while another python is working in this worktree; it restores by writing the
ORIGINAL BYTES back rather than through git, because the failure the rule is
about is git dying mid-restore under `index.lock` contention; it verifies the
restore by reading the bytes back AND by `git --no-optional-locks status`; and
it STOPS rather than continuing if either check fails, because the one thing
worse than an unproven mutant is a mutant left in a shared tree.

pytest exits 2 to 5 mean the tests never ran. None of them is evidence of a
kill, and each is scored for nothing and reported as `DID NOT RUN`.

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

#: pytest exit codes that mean the tests never ran.
DID_NOT_RUN = frozenset({2, 3, 4, 5})

#: The test files a kill may come from. Narrow on purpose: a mutant killed by
#: some unrelated suite is a mutant whose killer this card cannot name.
TESTS = [
    "tests/test_l1s4_publisher.py",
    "tests/test_l1s4_transfers.py",
    "tests/test_sibling_omission.py",
    "tests/test_document_report.py",
]


def _lines(*parts: str) -> str:
    """A multi-line anchor, joined at runtime.

    Never an escape inside one literal: a shell heredoc turned a newline escape
    into a real newline in a mutant table once already — and once more while
    this very function was being added, which is why the join is written with
    `chr(10)` rather than with the escape a heredoc can eat. An anchor that
    cannot be applied exactly as documented is not a mutant (BATCH9-RULES).
    """
    return chr(10).join(parts)


@dataclass(frozen=True)
class Mutant:
    id: str
    condition: str
    what: str
    file: str
    old: str
    new: str


MUTANTS: list[Mutant] = [
    # --- the publisher's printed partition -------------------------------
    Mutant("C1", "L1-C1", "the printed reappearance is no longer required in "
           "both directions", "analysis/member_statement.py",
           "    if set(identities) != set(row_identities):",
           "    if False:"),
    Mutant("C2", "L1-C2", "a section's own closing no longer has to be the last "
           "dated thing before the next account",
           "analysis/member_statement.py",
           "        if _DATED_LINE_RE.search(region[end_match.end():]):",
           "        if False:"),
    Mutant("C3", "L1-C3", "two sections may resolve to one identity",
           "analysis/member_statement.py",
           "    if len(set(identities)) != len(identities):",
           "    if False:"),
    Mutant("C5", "L1-C5", "an enumerated row narrower than the caption's own "
           "columns is read positionally instead of refused",
           "analysis/member_statement.py",
           "        if len(values) != len(roles):",
           "        if False:"),
    Mutant("C6", "L1-C6", "the section's own OPENING no longer has to agree with "
           "the table's", "analysis/member_statement.py",
           '        if abs(row.figures["open"] - section.opening) > _CENT:',
           "        if False:"),
    Mutant("C6b", "L1-C6/C10", "the section's own CLOSING no longer has to agree "
           "with the table's", "analysis/member_statement.py",
           '        if abs(row.figures["close"] - section.closing) > _CENT:',
           "        if False:"),
    Mutant("C10", "L1-C10", "the cross-account total stops being an oracle",
           "analysis/member_statement.py",
           "        if abs(enumerated - cross_total) > _CENT:",
           "        if False:"),
    Mutant("C7", "L1-C7", "a printed dated row the ledger does not carry no "
           "longer refuses the section", "analysis/member_statement.py",
           "    if len(_DATED_LINE_RE.findall(section.ledger)) != len(rows):",
           "    if False:"),
    Mutant("C7b", "L1-C7", "the printed running balance stops checking the "
           "printed direction", "analysis/member_statement.py",
           "        if abs(round(balance + signed, 2) - printed_balance) > _CENT:",
           "        if False:"),
    Mutant("C7c", "L1-C7", "the printed reversal word is ignored, so a returned "
           "debit is published as a debit", "analysis/member_statement.py",
           '        sign = -column if match.group("reversal") else column',
           "        sign = column"),
    Mutant("C8", "L1-C10 / L1-C8", "the table's own movement totals stop being "
           "an oracle over the ledger", "analysis/member_statement.py",
           _lines('        if (abs(credits - row.figures["credit_total"]) > _CENT',
                  '                or abs(debits - row.figures["debit_total"]) > _CENT):'),
           "        if False:"),
    Mutant("C8b", "L1-C5", "a stated total IS published, so a figure the "
           "section never printed reaches the payload",
           "analysis/member_statement.py",
           "        ending_balance=section.closing,",
           _lines("        ending_balance=section.closing,",
                  "        stated_total_credits=section.closing,")),
    Mutant("C13", "L1-C13 / Q4", "a document naming two denominations is "
           "published instead of refused", "analysis/member_statement.py",
           "    if len(set(_CURRENCY_CODES.findall(markdown))) > 1:",
           "    if False:"),
    Mutant("C17", "R-a / L1-C17", "a section dropped with NO printed evidence "
           "no longer refuses the document", "analysis/member_statement.py",
           "        if not admitted:",
           "        if False:"),

    # --- the seven Q3 conditions ------------------------------------------
    Mutant("Q3C1", "Q3 conditions 1 and 2", "the section need not print its own "
           "opening and closing", "analysis/sibling_omission.py",
           _lines("    if opening is None or closing is None:",
                  "        return False",
                  "    if abs(opening - closing) > CENT:"),
           _lines("    if opening is None or closing is None:",
                  "        return True",
                  "    if abs(opening - closing) > CENT:")),
    Mutant("Q3C3", "Q3 condition 3", "the printed pair need not coincide",
           "analysis/sibling_omission.py",
           "    if abs(opening - closing) > CENT:",
           "    if False:"),
    Mutant("Q3C4", "Q3 condition 4", "a dated row printed in the section no "
           "longer refuses it", "analysis/sibling_omission.py",
           "    if dated_row_count is None or dated_row_count != 0:",
           "    if False:"),
    Mutant("Q3C5", "Q3 condition 5", "printed counts or totals no longer refuse",
           "analysis/sibling_omission.py",
           "    if prints_counts_or_totals is None or prints_counts_or_totals:",
           "    if False:"),
    Mutant("Q3C6", "Q3 condition 6", "a printed daily-balance table no longer "
           "refuses", "analysis/sibling_omission.py",
           "    if prints_daily_balance_table is None or prints_daily_balance_table:",
           "    if False:"),
    Mutant("Q3C7", "Q3 condition 7", "a document printing no roll-up passes the "
           "witness vacuously", "analysis/sibling_omission.py",
           "    if rollup is None or not rollup.printed:",
           "    if False:\n        pass\n    if rollup is None:"),
    Mutant("Q3C7b", "Q3 condition 7", "L1-C5 widened: the witness stands under a "
           "column whose role the paper never named",
           "analysis/sibling_omission.py",
           "    if not rollup.column_roles_printed:",
           "    if False:"),
    Mutant("Q3C7c", "Q3 condition 7", "the two printed handles need not find the "
           "SAME row (the mis-binding the probe cannot see)",
           "analysis/sibling_omission.py",
           "    if not rollup.locators_agree:",
           "    if False:"),
    Mutant("Q3C7d", "Q3 condition 7", "the roll-up's closing need not reproduce "
           "the section's", "analysis/sibling_omission.py",
           "    return abs(rollup.closing - closing) <= CENT",
           "    return True"),

    # --- R-d's four clauses ------------------------------------------------
    Mutant("Rd1", "R-d clause 1", "a counterpart in the SAME account counts",
           "analysis/pipeline.py",
           "            left[0] != right[0]",
           "            True"),
    Mutant("Rd1b", "R-d clause 1", "the two legs need not be opposite in sign",
           "analysis/pipeline.py",
           "            and left[3] * right[3] < 0",
           "            and True"),
    Mutant("Rd2", "R-d clause 2", "an ambiguous pairing is resolved instead of "
           "refused", "analysis/pipeline.py",
           "    ambiguous = any(len(found) > 1 for found in counterparts.values())",
           "    ambiguous = False"),
    Mutant("Rd3", "R-d clause 3", "one posting may be a leg of two transfers "
           "(the gate is where one-to-one is asserted)", "corpus_gate.py",
           "            if key in seen:",
           "            if False:"),
    Mutant("Rd4", "R-d clause 4", "an arithmetic coincidence sets INTERNAL with "
           "nothing printed", "analysis/pipeline.py",
           "        if not any(designations):",
           "        if False:"),
    Mutant("Rd4b", "R-d clause 4", "the peer-to-peer rail vocabulary is admitted "
           "as transfer evidence", "analysis/transaction_classifier.py",
           "        _INTERNAL_TRANSFER_CREDIT_PATTERNS,\n    )",
           "        _INTERNAL_TRANSFER_CREDIT_PATTERNS + _TRANSFER_PATTERNS,\n    )"),

    # --- the package -------------------------------------------------------
    Mutant("PK1", "R-d, package", "the flagged postings are counted after all",
           "webapp/app.py",
           "        excluded_positions = _internal_transfer_positions(job.analysis, account_index)",
           "        excluded_positions = set()"),
    Mutant("PK2", "§3.3, package", "an ambiguous document is aggregated anyway",
           "webapp/app.py",
           "            if ambiguous:",
           "            if False:"),
    Mutant("PK3", "MINOR-10", "two accounts of one document are two statement "
           "periods again", "webapp/app.py",
           "    statement_periods = len(period_keys) or months",
           "    statement_periods = months"),
]


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def clean() -> bool:
    return git("--no-optional-locks", "status", "--porcelain").stdout.strip() == ""


def _host_pythons() -> list[str]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "ForEach-Object { $_.ProcessId.ToString() + ' ' + $_.CommandLine }"],
        capture_output=True, text=True).stdout
    mine = str(os.getpid())
    return [line.strip() for line in out.splitlines()
            if line.strip() and line.split(" ", 1)[0] != mine]


def _busy_here() -> bool:
    here = str(ROOT).replace("\\", "/").lower()
    return any(here in line.replace("\\", "/").lower() for line in _host_pythons())


def _pytest() -> tuple[int, list[str]]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header",
         "-p", "no:randomly"],
        cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, sorted(set(
        re.findall(r"^FAILED (\S+)", proc.stdout, re.MULTILINE)))


def _mutate(mutant: Mutant) -> str:
    path = ROOT / mutant.file
    text = path.read_text(encoding="utf-8")
    found = text.count(mutant.old)
    if found != 1:
        raise SystemExit(
            f"{mutant.id}: its target text occurs {found} times in "
            f"{mutant.file}; a mutant that cannot be applied exactly as "
            f"documented is not a mutant")
    path.write_text(text.replace(mutant.old, mutant.new), encoding="utf-8")
    return text


def _restore(mutant: Mutant, original: str) -> bool:
    path = ROOT / mutant.file
    for _attempt in range(3):
        try:
            path.write_text(original, encoding="utf-8")
        except OSError:  # a OneDrive handle; retry rather than score it
            continue
        if path.read_text(encoding="utf-8") == original:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the L1-S4 mutation table")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--allow-concurrent", action="store_true")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    if not clean():
        print("REFUSING: the working tree is dirty; a byte restore is only "
              "correct on a clean one.")
        return 5
    if _busy_here() and not args.allow_concurrent:
        print("REFUSING: another python is working in this worktree.")
        return 5
    bystanders = len(_host_pythons())

    chosen = [m for m in MUTANTS if not args.only or m.id in args.only]
    baseline_code, baseline_failing = _pytest()
    print("# L1-S4 — the mutation table\n")
    print(f"Tests: `{' '.join(TESTS)}`, run without `-x`. Other pythons on the "
          f"host at start: {bystanders}.\n")
    print(f"Baseline: exit {baseline_code}, {len(baseline_failing)} failing.\n")
    if baseline_code != 0:
        print("REFUSING: the baseline is not green, so no kill can be attributed.")
        return 5

    print("| mutant | condition | what it removes | file | tests | killers |")
    print("|---|---|---|---|---|---|")
    holes: list[str] = []
    stalled: list[str] = []
    for mutant in chosen:
        original = _mutate(mutant)
        try:
            code, failing = _pytest()
        finally:
            restored = _restore(mutant, original)
        if not restored or not clean():
            print(f"\n**STOPPED** at {mutant.id}: the tree may hold a mutant.")
            return 3
        if code in DID_NOT_RUN:
            stalled.append(f"{mutant.id} (pytest exit {code})")
            verdict, killed = f"DID NOT RUN ({code})", False
        else:
            killed = code == 1 and bool(failing)
            verdict = f"{'FAIL' if code else 'pass'} ({len(failing)})"
            if not killed:
                holes.append(f"{mutant.id} ({mutant.condition})")
        names = ", ".join(f"`{name.split('::')[-1]}`" for name in failing[:3])
        if len(failing) > 3:
            names += f", +{len(failing) - 3} more"
        print(f"| {mutant.id} | {mutant.condition} | {mutant.what} | "
              f"`{mutant.file}` | {verdict} | {names or '—'} |")

    print()
    if stalled:
        print(f"**DID NOT RUN**: {', '.join(stalled)}. Not a kill and not a "
              f"hole — nothing is scored for these. Re-run them.")
        return 2
    if holes:
        print(f"**HOLES**: {', '.join(holes)} — no named test failed on these, "
              f"which is a gap in the proof rather than a property of the code.")
        print(f"\nMUTANTS={len(chosen)} KILLED={len(chosen) - len(holes)} "
              f"HOLES={len(holes)}")
        return 1
    print(f"Every mutant killed by a NAMED failing test: "
          f"{len(chosen)} / {len(chosen)}.")
    print(f"\nMUTANTS={len(chosen)} KILLED={len(chosen)} HOLES=0")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
