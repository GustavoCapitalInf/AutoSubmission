"""pnc_mutation_table.py — every decision this card added to `analysis/pnc.py`,
killed by a named test.

    python -m tools.pnc_mutation_table [--only M5] [--out <private>.md]

Each row of `tools/pnc_mutants.py` breaks ONE decision in the production source
by exact string replacement, runs the tests that exist for it WITHOUT `-x`, and
requires that a NAMED test fails. A test named after a gate is not a test of
that gate; the mutant is.

Host safety is the shape BATCH9-RULES asks for after a batch-8 harness left a
mutant in a working tree, and it is borrowed rather than rewritten: the
restore, the git wrapper that neither starts nor scores the stale-worktree
prune, and the retried `status --porcelain` all come from
`tools/fixpriv_mutation_table.py`, which is where they were hardened. A second
copy of that logic is a second thing to get wrong.

    * refuses to start on a dirty tree — a restore cannot be verified against a
      baseline that was already dirty, and `git checkout --` would discard work;
    * restores in a `finally` whose exit code is ignored, then verifies the
      file byte-for-byte against text held in memory since before the first
      mutant, then verifies the whole tree is clean again;
    * no table is printed unless both verifications pass.

Exit 0 only if every mutant was killed; 1 if one survived; 3 if the tree was
not clean (or git would not say) BEFORE the run; 4 if the file was not restored
to its original bytes; 5 if the tree is not verifiably clean AFTER it.
$0: no archive, no cache, no network.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.fixpriv_mutation_table import (  # noqa: E402  (path set above)
    _GIT_TRIES,
    _porcelain,
    _restore,
)
from tools.pnc_mutants import MUTANTS  # noqa: E402

_FAIL_LINE = re.compile(r"^FAILED (\S+)")


def run(only: str | None, out: Path | None) -> int:
    dirty = _porcelain()
    if dirty is None:
        print(f"git status would not answer after {_GIT_TRIES} tries, so the tree "
              "cannot be proved clean; refusing to start — this harness mutates "
              "tracked source and restores it", file=sys.stderr)
        return 3
    if dirty:
        print("the tree is not clean; the harness restores with `git checkout --` "
              f"and would discard real work:\n{dirty}", file=sys.stderr)
        return 3

    mutants = [m for m in MUTANTS if only is None or m.ident == only]
    originals = {m.target: (ROOT / m.target).read_text(encoding="utf-8") for m in mutants}
    rows: list[tuple[str, str, str, str, str]] = []
    survivors = 0
    for mutant in mutants:
        target = ROOT / mutant.target
        original = originals[mutant.target]
        if original.count(mutant.old) != 1:
            rows.append((mutant.ident, mutant.rule, mutant.what, "NOT APPLIED",
                         f"the mutated text occurs {original.count(mutant.old)} "
                         "times in the file, not once"))
            survivors += 1
            continue
        target.write_text(original.replace(mutant.old, mutant.new, 1), encoding="utf-8")
        proc = None
        failure = ""
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", *mutant.suite, "-q", "--no-header",
                 "-p", "no:cacheprovider"],
                cwd=ROOT, capture_output=True, text=True, errors="replace")
        except Exception as error:  # noqa: BLE001 — never escapes; the restore must run
            failure = f"{type(error).__name__}: {error}"
        finally:
            _restore(target, original)
        if proc is None:
            rows.append((mutant.ident, mutant.rule, mutant.what, "NOT RUN", failure))
            survivors += 1
            continue
        killers = sorted({m.group(1) for m in
                          (_FAIL_LINE.match(line) for line in proc.stdout.splitlines()) if m})
        if proc.returncode == 0 and not killers:
            rows.append((mutant.ident, mutant.rule, mutant.what, "SURVIVED", "no test failed"))
            survivors += 1
            continue
        named = "; ".join(k.split("::", 1)[-1] for k in killers[:3])
        if len(killers) > 3:
            named += f"; +{len(killers) - 3} more"
        rows.append((mutant.ident, mutant.rule, mutant.what,
                     f"KILLED ({len(killers)})", named or f"exit {proc.returncode}"))

    for path, original in originals.items():
        if (ROOT / path).read_text(encoding="utf-8") != original:
            print(f"{path} was not restored; refusing to report", file=sys.stderr)
            return 4
    left = _porcelain()
    if left is None:
        print(f"git status would not answer after {_GIT_TRIES} tries; the mutated "
              "file IS verified restored byte-for-byte, but this harness does not "
              "report a table it cannot stand behind", file=sys.stderr)
        return 5
    if left:
        print(f"the tree is not clean after the run; refusing to report:\n{left}",
              file=sys.stderr)
        return 5

    lines = ["| mutant | rule | what the mutant does | verdict | killed by |",
             "|---|---|---|---|---|"]
    lines += [f"| {i} | {r} | {w} | {v} | {k} |" for i, r, w, v, k in rows]
    table = "\n".join(lines)
    tail = (f"\nmutants {len(mutants)} · killed {len(mutants) - survivors} "
            f"· survived {survivors}")
    print(table)
    print(tail)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(table + "\n" + tail + "\n", encoding="utf-8")
    return 0 if survivors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default=None, help="run one mutant by its ident")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    return run(args.only, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
