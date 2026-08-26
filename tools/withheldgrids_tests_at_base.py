"""Which of this card's new tests already PASS on the base tree?

W3 §WITHHELDGRIDS's fourth committed instrument, for the review's MINOR-10.
A test added beside a change is supposed to fail without the change. One that
passes on the base tree is one of two things, and the difference matters:

* a deliberate NEGATIVE or ABLATION pin — "the rule must not touch this" —
  which is exactly the half that keeps a removal-only rule honest, and which
  passes at base by construction. Good practice, and it should say so in its
  own name or docstring;
* a test that believes it pins the change and does not. That is a coverage
  hole wearing a passing test's clothes, and the only way to find it is to run
  the new tests against the OLD code.

    python -m tools.withheldgrids_tests_at_base [--base-rev 10cc722]
        [--work <dir>] [--keep]

HOW. `git archive` the base revision into a scratch directory, overlay ONLY
the test files this card touches, and run pytest there. The overlay is what
isolates the question: everything else in that tree is `10cc722`, so a test
that passes is passing against the base parser.

$0.00, no archive access, no network: this reads tracked source only.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

TEST_FILES = (
    "tests/test_adb.py",
    "tests/test_analysis.py",
    "tests/test_community_section_layouts.py",
    "tests/test_declines_c_variants.py",
)


def _git(repo: Path, *args: str, binary: bool = False):
    proc = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True,
        text=not binary,
    )
    return proc.stdout


def added_test_names(repo: Path, base_rev: str) -> list[str]:
    """The `def test_...` names this branch ADDS to the four files."""
    diff = _git(repo, "diff", f"{base_rev}..HEAD", "--", *TEST_FILES)
    return sorted({
        match.group(1)
        for match in re.finditer(r"^\+def (test_\w+)", diff, re.M)
    })


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base-rev", default="10cc722")
    ap.add_argument("--work", default="")
    ap.add_argument("--keep", action="store_true")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    names = added_test_names(repo, args.base_rev)
    if not names:
        print("no added tests found in the four owned files")
        return 1

    work = Path(args.work or tempfile.mkdtemp(prefix="wg_base_")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    tree = work / "base_tree"
    if tree.exists():
        shutil.rmtree(tree, ignore_errors=True)
    tree.mkdir(parents=True)
    archive = work / "base.tar"
    archive.write_bytes(_git(repo, "archive", "--format=tar", args.base_rev, binary=True))
    with tarfile.open(archive) as handle:
        handle.extractall(tree, filter="data")
    for relative in TEST_FILES:
        shutil.copy2(repo / relative, tree / relative)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "--tb=no", "-rA",
         *TEST_FILES],
        cwd=tree, capture_output=True, text=True,
    )
    outcome: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        match = re.match(r"^(PASSED|FAILED|ERROR|XFAIL|SKIPPED)\s+(\S+)", line)
        if match:
            outcome[match.group(2).split("::")[-1]] = match.group(1)

    passing = [name for name in names if outcome.get(name) == "PASSED"]
    failing = [name for name in names if outcome.get(name) in ("FAILED", "ERROR")]
    missing = [name for name in names if name not in outcome]

    print(f"base_rev={args.base_rev}  added_tests={len(names)}")
    print(f"FAIL at base (they pin the change): {len(failing)}")
    for name in failing:
        print(f"  fail  {name}")
    print(f"PASS at base (negative/ablation pins, or coverage holes): {len(passing)}")
    for name in passing:
        print(f"  pass  {name}")
    if missing:
        print(f"NOT COLLECTED at base: {len(missing)}")
        for name in missing:
            print(f"  ????  {name}")
    print(f"pytest exit at base = {proc.returncode}")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
