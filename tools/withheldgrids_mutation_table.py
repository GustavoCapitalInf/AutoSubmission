"""The mutation table W3 §WITHHELDGRIDS reports, as a committed instrument.

Standing rule: commit your instruments under `tools/` when they produce
headline numbers. The 13/13 headline in the first draft of §WITHHELDGRIDS was
produced by a harness that lived only in a scratchpad, which is the review's
MAJOR-4; this is that harness, in the shape the sibling cells used
(`tools/descattrib_mutate.py`, and `tools/extractpriv_mutate.py`, deleted in
slice S3 of the model-code removal with the module it mutated).

    python -m tools.withheldgrids_mutation_table            # the whole table
    python -m tools.withheldgrids_mutation_table --only M1 M13
    python -m tools.withheldgrids_mutation_table --list

WHAT A MUTANT IS HERE. A single literal substitution in tracked source that
MUST appear exactly once. If it appears zero times or more than once the
harness reports NOT APPLIED and scores nothing — the batch-7 trap, where a
mutant that silently failed to apply looked like a killed mutant. Each mutant
is written to break exactly the mechanism its row names, and the row names the
mechanism, not the test: a test named after a gate is not a test of that gate.

SAFETY, in the order it matters:

* the harness REFUSES to start on a dirty tree, because it restores with
  `git checkout --` and would otherwise destroy uncommitted work (batch 7:
  one harness did exactly that);
* every mutant is restored in a `finally`, and the tree is re-checked for
  cleanliness after every mutant and once more at the end;
* pytest runs WITHOUT `-x`, so every killer is named rather than just the
  first one.

Survivors are DISCLOSED in the table, never dropped. A rule whose mutant
survives is either untested or unnecessary, and only measurement against the
documents says which (W3 §WITHHELDGRIDS WG5).

$0.00: no hosted model, no archive access, no network.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

TEST_FILES = (
    "tests/test_adb.py",
    "tests/test_analysis.py",
    "tests/test_community_section_layouts.py",
    "tests/test_declines_c_variants.py",
)


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    gate: str
    path: str
    old: str
    new: str
    note: str = ""


DATES = "analysis/dates.py"
COMMUNITY = "analysis/community_section.py"
REGIONS = "analysis/regions.py"
NAVY = "analysis/navy_federal.py"

MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        "M1", "money presence keeps its two-decimal bound", DATES,
        r'_MONEY_RE = re.compile(r"\d[\d, ]*[.,]\d{2}(?!\d)")',
        r'_MONEY_RE = re.compile(r"\d[\d, ]*[.,]\d{2}")',
        "without the right-hand bound `0.0000%` reads as the amount `0.00`",
    ),
    Mutant(
        "M2", "money presence reads a comma decimal", DATES,
        r'_MONEY_RE = re.compile(r"\d[\d, ]*[.,]\d{2}(?!\d)")',
        r'_MONEY_RE = re.compile(r"\d[\d,]*\.\d{2}(?!\d)")',
        "the US-only pattern reports `no money anywhere` on a French statement",
    ),
    # M5 and M6 attacked the page-header position rule, and M9 the
    # column-caption stop. Both rules were withdrawn by measurement (CLOSURE 2
    # and CLOSURE 7), so their mutants are gone with them rather than left
    # here reporting NOT APPLIED for ever. M18 and M19 were written for a
    # deferring page-header rule and for the rate-only remainder; neither is
    # in the tree, and the rate rule's effect is measured as a COUNTERFACTUAL
    # by `tools/withheldgrids_srcdates_audit.py --counterfactuals` instead.
    Mutant(
        "M7", "the bare-date forward label test fires", DATES,
        "                following = next(\n"
        "                    (l.strip() for l in lines[index + 1:] if l.strip()), \"\"\n"
        "                )",
        '                following = ""',
        "the column-per-line layout's `Beginning Balance` label is never read",
    ),
    Mutant(
        "M8", "money proximity is required of EVERY moneyless candidate", DATES,
        "            lookahead = [l for l in lines[index + 1: index + 5] if l.strip()][:3]",
        "            if len(remainder) >= 3:\n"
        "                found.add(parsed)\n"
        "                continue\n"
        "            lookahead = [l for l in lines[index + 1: index + 5] if l.strip()][:3]",
        "the old narrower gate: proximity asked only of a bare date",
    ),
    Mutant(
        "M10", "dot leaders are stripped before the grid caption", DATES,
        '_DOT_LEADERS = re.compile(r"\\.{3,}")',
        '_DOT_LEADERS = re.compile(r"(?!x)x")',
        "`Date.....Balance` never matches the caption without the strip",
    ),
    Mutant(
        "M11", "the `Date Balance` caption opens a section", DATES,
        '_DAILY_BALANCE_GRID_CAPTION = re.compile(r"^\\s*date\\s+balance\\s*$", re.I)',
        '_DAILY_BALANCE_GRID_CAPTION = re.compile(r"^(?!x)x", re.I)',
        "the layout that prints no heading above the grid loses the section",
    ),
    Mutant(
        "M12", "the section HEADING is matched on the printed line, leaders and all",
        DATES,
        "    if _DAILY_BALANCE_SECTION_START.match(line):",
        "    if _DAILY_BALANCE_SECTION_START.match(_without_leaders(line)):",
        "stripping leaders for the heading too opens a section on two more "
        "archive documents and costs each a real posting day",
    ),
    Mutant(
        "M13", "the grid reads its balance column SIGNED", COMMUNITY,
        'for match in re.finditer(r"(" + _DATE + r")\\s+(" + _SIGNED_MONEY + r")", _clean(start.group(1))):',
        'for match in re.finditer(r"(" + _DATE + r")\\s+(" + _MONEY + r")", _clean(start.group(1))):',
        "an overdrawn day prints `-$1,234.56` and the unsigned pair drops the DAY",
    ),
    Mutant(
        "M15", "the page sign-off is cut from a row", REGIONS,
        '    r"\\s+Total\\b|For all your banking needs\\b|" + re.escape(ISSUER_FOOTER),',
        '    r"\\s+Total\\b|For all your banking needs\\b",',
        "the anchored row pattern DELETES a row a welded footer sits on",
    ),
    Mutant(
        "M16", "the compatibility branch is narrowed", NAVY,
        "            if signed > 0 and (txn_date is None or not description):",
        "            if signed > 0:",
        "unnarrowed it shifts the whole ledger by one row",
    ),
    Mutant(
        "M17", "the compatibility branch still fires where it should", NAVY,
        "            if signed > 0 and (txn_date is None or not description):",
        "            if False and signed > 0 and (txn_date is None or not description):",
        "the branch is narrowed, not removed",
    ),
    Mutant(
        "M22", "the grid region is anchored on the grid's own column header",
        COMMUNITY,
        '    r"Daily Balances\\b[\\s\\S]{0,40}?Date\\s+Amount\\b(.*?)"',
        '    r"Daily Balances\\b(.*?)"',
        "unanchored the region opens in the METHOD DISCLOSURE and a check row "
        "is read as a grid cell",
    ),
    Mutant(
        "M20", "a repeated grid date with disagreeing balances refuses", COMMUNITY,
        "        if iso in balances and balances[iso] != amount:",
        "        if False and iso in balances and balances[iso] != amount:",
        "without the refusal the grid resolves a contradiction last-wins",
    ),
    Mutant(
        "M21", "a repeated grid date that AGREES is not a contradiction", COMMUNITY,
        "        if iso in balances and balances[iso] != amount:",
        "        if iso in balances:",
        "the grid prints the same day twice with the same balance on real documents",
    ),
)


@dataclass
class Result:
    mutant: Mutant
    verdict: str
    killers: list[str] = field(default_factory=list)
    seconds: float = 0.0


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _dirty(repo: Path) -> str:
    return _git(repo, "status", "--porcelain").strip()


def _run_tests(repo: Path) -> tuple[int, list[str]]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=no", "-rf",
         *TEST_FILES],
        cwd=repo, capture_output=True, text=True,
    )
    killers = sorted({
        match.group(1)
        for match in re.finditer(r"^FAILED\s+(\S+?)(?:\s|$)", proc.stdout, re.M)
    } | {
        match.group(1)
        for match in re.finditer(r"^ERROR\s+(\S+?)(?:\s|$)", proc.stdout, re.M)
    })
    return proc.returncode, killers


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--list", action="store_true")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()

    selected = [m for m in MUTANTS if not args.only or m.mutant_id in set(args.only)]
    if args.list:
        for mutant in selected:
            print(f"{mutant.mutant_id:4s} {mutant.path:32s} {mutant.gate}")
        return 0

    dirty = _dirty(repo)
    if dirty:
        print("REFUSING: the tree is dirty and this harness restores with "
              "`git checkout --`. Commit or stash first.")
        print(dirty)
        return 1

    baseline_rc, baseline_killers = _run_tests(repo)
    if baseline_rc != 0:
        print(f"REFUSING: the four owned test files do not pass at HEAD "
              f"(exit {baseline_rc}); a mutation table over a red suite means "
              f"nothing.")
        for killer in baseline_killers:
            print(f"  {killer}")
        return 1
    print(f"baseline: the four owned test files pass at HEAD (exit 0)")

    results: list[Result] = []
    for mutant in selected:
        target = repo / mutant.path
        original = target.read_text(encoding="utf-8")
        occurrences = original.count(mutant.old)
        if occurrences != 1:
            results.append(Result(mutant, f"NOT APPLIED ({occurrences} matches)"))
            print(f"{mutant.mutant_id:4s} NOT APPLIED ({occurrences} matches)")
            continue
        started = time.time()
        try:
            target.write_text(original.replace(mutant.old, mutant.new), encoding="utf-8")
            code, killers = _run_tests(repo)
            verdict = "KILLED" if code != 0 else "SURVIVED"
            results.append(Result(mutant, verdict, killers, time.time() - started))
            print(f"{mutant.mutant_id:4s} {verdict:9s} {len(killers):2d} killer(s) "
                  f"{time.time() - started:5.1f}s")
        finally:
            _git(repo, "checkout", "--", mutant.path)
        still_dirty = _dirty(repo)
        if still_dirty:
            print(f"RESTORE FAILED after {mutant.mutant_id}: {still_dirty}")
            return 1

    print()
    print("| mutant | file | gate | verdict | killed by |")
    print("|---|---|---|---|---|")
    for result in results:
        killers = "; ".join(
            killer.split("::")[-1] for killer in result.killers
        ) or "—"
        print(f"| {result.mutant.mutant_id} | `{result.mutant.path}` | "
              f"{result.mutant.gate} | {result.verdict} | {killers} |")

    killed = sum(1 for r in results if r.verdict == "KILLED")
    survived = sum(1 for r in results if r.verdict == "SURVIVED")
    not_applied = sum(1 for r in results if r.verdict.startswith("NOT APPLIED"))
    print()
    print(f"MUTANTS={len(results)} KILLED={killed} SURVIVED={survived} "
          f"NOT_APPLIED={not_applied}")
    if survived:
        print("SURVIVORS, disclosed:")
        for result in results:
            if result.verdict == "SURVIVED":
                print(f"  {result.mutant.mutant_id}  {result.mutant.gate}  "
                      f"— {result.mutant.note}")
    final = _dirty(repo)
    print(f"TREE_CLEAN_AFTER={not final}")
    if final:
        print(final)
        return 1
    return 0 if (survived == 0 and not_applied == 0) else 2


if __name__ == "__main__":
    sys.exit(main())
