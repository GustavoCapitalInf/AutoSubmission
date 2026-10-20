"""The mutation table for RAISE-PRIVACY-5's three `_MONTHS[...]` lookups.

    python -m tools.raisepriv5_mutation_table                # the whole table
    python -m tools.raisepriv5_mutation_table --only M1 M2   # a subset
    python -m tools.raisepriv5_mutation_table --list         # the roster, no runs

ONE MUTANT PER SITE reverting that site — and only that site — to the raw
`_MONTHS[...]` subscript the base tree held, plus the four ways the fix can be
written WRONG while still looking right, plus two that blind the census this
card added. Each is applied ON DISK, the gate set runs against it WITHOUT `-x`
so every killer is named rather than only the first, and the file is restored
afterwards whatever happens.

WHY A LOOKUP NEEDS ITS OWN TABLE. RAISE-PRIVACY-4's table reverted CALLS, and
a reverted call is visible to a conversion census. A subscript is not: neither
census in this tree walked `Subscript` nodes, so `_MONTHS[sm]` had no `raise`
to grep for and no call to enumerate. The first three mutants are therefore
the ones that say out loud whether §4c's lookup census is doing work, and M4-M6
are the ones that say whether the DRIVES are checking the printed word's
absence rather than the message's shape.

THE RESTORE CANNOT DEPEND ON GIT, and this host is why (FIXTURE-PRIVACY-2, and
before it a re-review closure that watched `git checkout --` die with exit 255
on `index.lock` contention from another cell INSIDE a `finally`, leaving the
mutant in the working tree). So: refuse to start on a tree git will not prove
clean; restore in two stages, git first and then a byte restore from the text
this harness read before it mutated anything, neither of which may raise;
verify every mutated file against that text before printing a table; and prove
`git status --porcelain` clean again at the end, with reads retried because the
same contention can silence `status` too.

Exit 0 only if EVERY mutant was killed; 1 if one survived or was not applied
(the only red that is about the code); 3 if the tree was not clean, or git
would not say, BEFORE the run; 4 if a file was not restored to its original
bytes; 5 if the tree is not verifiably clean AFTER it.

Reads no archive document, makes no model call, costs $0.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from tools.hygiene8_mutation_table import Mutant, _nth_index, enclosing_function

ROOT = Path(__file__).resolve().parent.parent

#: The three files that hold this card's gates. Nothing wider: a mutant killed
#: by an unrelated suite is a kill, but it is not evidence that the gate this
#: card added works, and evidence is the point.
GATE_SET = (
    "tests/test_raise_privacy4.py",
    "tests/test_privacy3_boundaries.py",
    "tests/test_raise_privacy3.py",
)

TD = "analysis/td_can.py"
BOUNDARIES = "tests/test_privacy3_boundaries.py"

#: The refusal as it stands at both ends of `_parse_period`, byte for byte. It
#: occurs TWICE and that is the property, not an accident: a caller must not be
#: able to tell which end of the printed period was unreadable.
_PERIOD_RAISE = (
    "        raise KeyError(\n"
    '            "month lookup refused a printed word "\n'
    '            "(not a month word; reader=td_can._parse_period)"\n'
    "        )"
)

_START_FUNNEL = (
    "    start_month = _MONTHS.get(sm)\n"
    "    if start_month is None:\n"
    + _PERIOD_RAISE
)

_END_FUNNEL = (
    "    end_month = _MONTHS.get(em)\n"
    "    if end_month is None:\n"
    + _PERIOD_RAISE
)

_NATIVE_FUNNEL = (
    "    month = _MONTHS.get(m.group(1).upper())\n"
    "    if month is None:\n"
    "        raise KeyError(\n"
    '            "month lookup refused a printed word "\n'
    '            "(not a month word; reader=td_can._native_date_to_iso)"\n'
    "        )"
)

MUTANTS = (
    Mutant(
        "M1", "td_can._parse_period, the period's START month word", TD,
        _START_FUNNEL,
        "    start_month = _MONTHS[sm]",
        "the first of the three lookups reverted to the raw subscript the "
        "base tree held: `_PERIOD_RE`'s `([A-Z]{3})` proves three capital "
        "letters, so a word that is not a month reaches the table and the "
        "`KeyError` IS the printed word",
    ),
    Mutant(
        "M2", "td_can._parse_period, the period's END month word", TD,
        _END_FUNNEL,
        "    end_month = _MONTHS[em]",
        "the same shape on the period's end word. Reverted separately from M1 "
        "because a mutant per FUNCTION would leave one of the two ends "
        "unpinned, and the two ends are read sequentially",
    ),
    Mutant(
        "M3", "td_can._native_date_to_iso, the row token's month word", TD,
        _NATIVE_FUNNEL,
        "    month = _MONTHS[m.group(1).upper()]",
        "the CALLER-GUARDED lookup reverted. No production caller reaches it "
        "— `_native_date_token` tests membership first — so this is the "
        "mutant that says whether the lookup census does the work the "
        "production drive cannot",
    ),
    Mutant(
        "M4", "the refusal is a FIXED message", TD,
        _PERIOD_RAISE,
        "        raise KeyError(\n"
        '            f"month lookup refused the printed word {sm} "\n'
        '            "(not a month word; reader=td_can._parse_period)"\n'
        "        )",
        "the funnel is kept and the MESSAGE is made to quote the word — a "
        "refusal that looks exactly right, names its reader, and leaks. The "
        "shape §MONEYPRIV MP0 named, one construction over",
        occurrences=2, nth=1,
    ),
    Mutant(
        "M5", "the refusal stands OUTSIDE any handler", TD,
        _START_FUNNEL,
        "    try:\n"
        "        start_month = _MONTHS[sm]\n"
        "    except KeyError:\n"
        "        raise KeyError(\n"
        '            "month lookup refused a printed word "\n'
        '            "(not a month word; reader=td_can._parse_period)"\n'
        "        )",
        "the message is fixed, the class is right, and the raise sits inside "
        "the handler — so `__context__` still holds `KeyError('<the word>')` "
        "and the word rides out on the first rendered traceback. The failure "
        "`from None` does not fix either",
    ),
    Mutant(
        "M6", "the raised CLASS does not move", TD,
        _PERIOD_RAISE,
        "        raise ValueError(\n"
        '            "month lookup refused a printed word "\n'
        '            "(not a month word; reader=td_can._parse_period)"\n'
        "        )",
        "the message is private and the CLASS moves. `_guarded` reduces a "
        "parser crash to `type(exc).__name__`, so this is a moved outcome "
        "with no figure moving — the one thing a hygiene card may not do",
        occurrences=2, nth=1,
    ),
    Mutant(
        "M7", "the fourth subscript really is guarded", TD,
        "        if mon not in _MONTHS:\n            continue",
        "        if mon not in _MONTHS and False:\n            continue",
        "`_date_tokens`'s `_MONTHS[mon]` is the one subscript this card left "
        "standing, on the ground that the membership test above it is a "
        "guard. This neuters that guard: if the allowlist's reason is true, "
        "the drive that exercises it must go red",
    ),
    Mutant(
        "M8", "the lookup census reports a non-literal key", BOUNDARIES,
        "        if isinstance(key, (ast.Constant, ast.Slice)):\n            continue",
        "        if True:\n            continue",
        "the census is blinded so it reports nothing at all. A census that "
        "reports nothing agrees with every allowlist, so the `stale` clause "
        "is what has to catch it — and its own mutant roster with it",
    ),
    Mutant(
        "M9", "both censuses walk the whole module", BOUNDARIES,
        '    visit(tree, "<module>")\n    return found',
        "    for top in ast.iter_child_nodes(tree):\n"
        "        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):\n"
        '            found.append(("<module>", top))\n'
        "            visit(top, top.name)\n"
        "    return found",
        "the scope walker reverted to the FunctionDef-only walk review "
        "MINOR-5 measured: module scope and module-level lambdas disappear "
        "from both censuses while both claims stay written over everything",
    ),
)

#: How many times a git call that only READS is retried, and how long the
#: harness waits between tries. `index.lock` contention from another cell in
#: another worktree of this repository is transient by construction.
_GIT_TRIES = 3
_GIT_BACKOFF = 0.5


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "-c", "gc.auto=0", *args],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, args, proc.stdout, proc.stderr)
    return proc.stdout


def _porcelain() -> str | None:
    """The working tree's status, or None if git would not answer at all.

    None and "" are different facts and the caller must not confuse them: ""
    is a tree proved clean, None is a tree whose state is unknown. Both refuse
    the run, at either end, but only one of them is a claim.
    """
    for attempt in range(_GIT_TRIES):
        try:
            return _git("status", "--porcelain").strip()
        except (subprocess.CalledProcessError, OSError):
            if attempt + 1 < _GIT_TRIES:
                time.sleep(_GIT_BACKOFF * (attempt + 1))
    return None


def _restore(relative: str, original: str) -> None:
    """Put the file back to `original`. NEVER raises, whatever git does.

    Stage one is `git checkout --`, the right tool when it works, and its exit
    code is IGNORED. Stage two is the one that cannot fail for a reason
    outside this process: compare against the text read before anything was
    mutated and write it back. OneDrive holds files open transiently, so the
    write is retried; if every try fails the function still returns, and the
    caller's verification is what turns that into a refusal to report.
    """
    try:
        _git("checkout", "--", relative)
    except Exception:  # noqa: BLE001 — the restore may not have an opinion
        pass
    target = ROOT / relative
    for attempt in range(_GIT_TRIES):
        try:
            if target.read_text(encoding="utf-8") == original:
                return
            target.write_text(original, encoding="utf-8")
        except OSError:
            time.sleep(_GIT_BACKOFF * (attempt + 1))


def run_gate_set(timeout: int) -> tuple[int, list[str], str]:
    """(exit code, the failing test ids, the tail of the output)."""
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", *GATE_SET],
        cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=timeout,
    )
    output = (process.stdout or "") + (process.stderr or "")
    killers = sorted({
        line.split(" ", 1)[1].split(" ")[0]
        for line in output.splitlines()
        if line.startswith(("FAILED ", "ERROR ")) and " " in line
    })
    return process.returncode, killers, output[-1200:]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", default=None, help="mutant ids to run")
    parser.add_argument("--list", action="store_true", help="print the roster and stop")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    selected = [m for m in MUTANTS if args.only is None or m.id in set(args.only)]
    if args.list:
        for mutant in selected:
            print(f"{mutant.id:4s} {mutant.path:32s} {mutant.gate}")
        print(f"{len(selected)} mutants")
        return 0

    dirty = _porcelain()
    if dirty is None:
        print(f"git status would not answer after {_GIT_TRIES} tries, so the tree "
              "cannot be proved clean; refusing to start — this harness mutates "
              "tracked source and will not do that against a tree it cannot see",
              file=sys.stderr)
        return 3
    if dirty:
        print("the tree is not clean; the harness restores tracked source and would "
              f"discard real work:\n{dirty}", file=sys.stderr)
        return 3

    # Every file this table touches, read ONCE, before anything is mutated.
    # This text is the authority the restore and the verification both use.
    originals = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in sorted({mutant.path for mutant in selected})
    }

    print("=== baseline: the gate set on the unmutated branch ===")
    baseline_code, baseline_killers, baseline_tail = run_gate_set(args.timeout)
    print(f"baseline exit={baseline_code} failures={baseline_killers}")
    if baseline_code != 0:
        print(baseline_tail)
        print("REFUSING: the gate set is not green before mutation; every kill "
              "below would be unattributable.")
        return 3

    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for mutant in selected:
        original = originals[mutant.path]
        count = original.count(mutant.old)
        if count != mutant.occurrences:
            rows.append({
                "id": mutant.id, "gate": mutant.gate, "path": mutant.path,
                "verdict": "NOT APPLIED",
                "detail": f"target text occurs {count}x, documented {mutant.occurrences}x",
            })
            print(f"{mutant.id:4s} NOT APPLIED  (occurs {count}x, documented "
                  f"{mutant.occurrences}x)")
            continue
        offset = _nth_index(original, mutant.old, mutant.nth)
        mutated = original[:offset] + mutant.new + original[offset + len(mutant.old):]
        landed_in = enclosing_function(mutated, offset)
        code, killers, tail, failure = None, [], "", ""
        try:
            (ROOT / mutant.path).write_text(mutated, encoding="utf-8")
            try:
                compile(mutated, mutant.path, "exec")
            except SyntaxError as exc:
                failure = f"does not compile ({type(exc).__name__}: {exc.msg})"
            else:
                code, killers, tail = run_gate_set(args.timeout)
        except Exception as error:  # noqa: BLE001
            # Applying or launching failed — not a verdict about the mutant,
            # and crucially not allowed to escape: the restore below and the
            # two verifications after the loop have to be reached.
            failure = f"{type(error).__name__}: {error}"
        finally:
            _restore(mutant.path, original)
        if code is None:
            rows.append({
                "id": mutant.id, "gate": mutant.gate, "path": mutant.path,
                "verdict": "NOT APPLIED", "detail": failure,
            })
            print(f"{mutant.id:4s} NOT APPLIED  ({failure})")
            continue
        verdict = "killed" if code != 0 else "SURVIVED"
        rows.append({
            "id": mutant.id, "gate": mutant.gate, "path": mutant.path,
            "landed_in": landed_in, "describes": mutant.describes,
            "verdict": verdict, "exit": code, "killers": killers,
            "tail": "" if code != 0 else tail,
        })
        print(f"{mutant.id:4s} {'killed  ' if code != 0 else 'SURVIVED'} "
              f"exit={code} in={landed_in} "
              f"killers={killers[:4]}{'...' if len(killers) > 4 else ''}")

    # Two verifications, in this order, and no table is printed unless both
    # pass. The first is about the files this harness knowingly mutated and is
    # byte-exact against text held in memory since before the first mutant.
    # The second is about everything else.
    for relative, original in originals.items():
        try:
            current = (ROOT / relative).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{relative} could not be read back ({exc}); refusing to report",
                  file=sys.stderr)
            return 4
        if current != original:
            print(f"{relative} was not restored; refusing to report", file=sys.stderr)
            return 4
    left = _porcelain()
    if left is None:
        print(f"git status would not answer after {_GIT_TRIES} tries; the mutated "
              "files ARE verified restored byte-for-byte, but this harness does not "
              "report a table it cannot stand behind", file=sys.stderr)
        return 5
    if left:
        print(f"the tree is not clean after the run; refusing to report:\n{left}",
              file=sys.stderr)
        return 5

    killed = sum(1 for row in rows if row["verdict"] == "killed")
    survived = [row for row in rows if row["verdict"] == "SURVIVED"]
    not_applied = [row for row in rows if row["verdict"] == "NOT APPLIED"]
    report = {
        "mutants": len(rows), "killed": killed, "survived": len(survived),
        "not_applied": len(not_applied),
        "seconds": round(time.perf_counter() - started, 1),
        "gate_set": list(GATE_SET), "rows": rows,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    lines = ["| mutant | gate | file | landed in | verdict | killed by |",
             "|---|---|---|---|---|---|"]
    for row in rows:
        killers = row.get("killers") or []
        head = "; ".join(k.split("::", 1)[-1] for k in killers[:3])
        if len(killers) > 3:
            head += f"; +{len(killers) - 3} more"
        lines.append(
            f"| {row['id']} | {row['gate']} | `{row['path']}` | "
            f"`{row.get('landed_in', '-')}` | {row['verdict']} "
            f"({len(killers)}) | {head or row.get('detail', '')} |"
        )
    print("\n".join(lines))
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, sort_keys=True))
    for row in survived:
        print(f"SURVIVOR {row['id']}: {row['describes']}")
    for row in not_applied:
        print(f"NOT APPLIED {row['id']}: {row['detail']}")
    return 1 if survived or not_applied else 0


if __name__ == "__main__":
    raise SystemExit(main())
