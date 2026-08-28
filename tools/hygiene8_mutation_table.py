"""The mutation table for every gate #HYGIENE8's six commits added or touched.

    python -m tools.hygiene8_mutation_table                 # the whole table
    python -m tools.hygiene8_mutation_table --only Q1 R11   # a subset
    python -m tools.hygiene8_mutation_table --list          # the roster, no runs

Each mutant is applied ON DISK, the branch's gate set is run against it WITHOUT
`-x` so every killer is named rather than only the first, and the file is
restored with `git checkout --`. A survivor is DISCLOSED with a reason; a
survivor that is quietly dropped is how a mutation table becomes decoration.

THREE RULES THIS HARNESS ENFORCES ON ITSELF, each of them a batch-7 finding:

1. **A dirty tree is refused.** The restore is `git checkout -- <path>`, which
   would silently destroy an uncommitted edit. Batch 7 lost one that way, so
   this exits 2 before touching anything if `git status --porcelain` is not
   empty.
2. **A mutant is verified to be what it says it is.** The edit declares how
   many times its target text occurs and which occurrence to take; a count that
   does not match is an ERROR, not a skip. After applying, the harness re-parses
   the file and records the ENCLOSING FUNCTION of the mutated line, so the table
   states where the mutation actually landed rather than where it was meant to.
   §DECLINESF F13.1 found a row of a mutation table that was a lie — a "reorder"
   mutant that in fact deleted the reading, pinning nothing.
3. **Syntax is checked before the tests run.** A mutant that does not compile is
   killed by every test for the wrong reason, which looks like coverage.

THE GATE SET is the four test files this branch changed. Nothing wider: a
mutant killed by an unrelated suite is a kill, but it is not evidence that the
gate this branch added works, and evidence is the point.

Restoring is `git checkout --`, so this tool writes only to files it has just
mutated and only inside the working tree. It reads no archive document, makes
no model call, and costs $0.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

GATE_SET = (
    "tests/test_queue_supervisor.py",
    "tests/test_raise_privacy3.py",
    "tests/test_privacy3_boundaries.py",
    "tests/test_no_statement_hardcodes.py",
)


@dataclass(frozen=True)
class Mutant:
    """One documented edit, and the gate it is supposed to wake."""

    id: str
    gate: str
    path: str
    old: str
    new: str
    describes: str
    occurrences: int = 1
    nth: int = 1
    #: Set where the mutant is expected to survive, with the reason. A survivor
    #: with a reason is a disclosure; a survivor without one is a hole.
    expected_survivor: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


#: --------------------------------------------------------------------------
#: QUEUE-SUPERVISOR — `webapp/app.py`
#: --------------------------------------------------------------------------
QUEUE_MUTANTS = (
    Mutant(
        "Q1", "the slot is released when the worker dies", "webapp/app.py",
        "            _release_worker_slot()\n            raise",
        "            raise",
        "the handler stays but releases nothing: the base tree's defect, "
        "reintroduced behind a `try` that looks like a fix",
    ),
    Mutant(
        "Q2", "the escaping exception is re-raised bare", "webapp/app.py",
        "            _release_worker_slot()\n            raise",
        "            _release_worker_slot()",
        "the arm swallows instead of re-raising - the fix §PRIVACY3 P8.1 "
        "deliberately did NOT take, because it hides the death",
    ),
    Mutant(
        "Q3", "the handler is BaseException, not Exception", "webapp/app.py",
        "        except BaseException:",
        "        except Exception:",
        "a `SystemExit` or `KeyboardInterrupt` raised inside run_job walks past "
        "the handler and strands the queue again - the exact class the arm "
        "exists for",
    ),
    Mutant(
        "Q4", "the slot always comes back", "webapp/app.py",
        "        _job_worker_active = rearm\n",
        "",
        "the release stops releasing: the flag is left exactly as the dead "
        "worker claimed it, so a process with an empty queue at the moment of "
        "death never accepts an upload again",
    ),
    Mutant(
        "Q5", "the re-arm needs queued work", "webapp/app.py",
        "        rearm = bool(_job_queue)\n",
        "        rearm = True\n",
        "a replacement worker is started on an EMPTY queue - the first draft's "
        "mutant Q8, which walked through the thread-count assertion the branch "
        "replaced",
    ),
    Mutant(
        "Q6", "no exception class is exempt from the re-arm", "webapp/app.py",
        "            _release_worker_slot()\n            raise",
        '            if isinstance(__import__("sys").exc_info()[1],\n'
        "                          (SystemExit, KeyboardInterrupt)):\n"
        "                with _job_queue_lock:\n"
        "                    _job_worker_active = False\n"
        "            else:\n"
        "                _release_worker_slot()\n"
        "            raise",
        "REVIEW MINOR-3, the shipped premise reintroduced: a thread-raised "
        "signal releases the slot and starts nothing, so the work already "
        "queued waits for the next upload on a process that is not stopping",
    ),
    Mutant(
        "Q7", "a claimed slot has a worker behind it", "webapp/app.py",
        "        threading.Thread(target=_process_job_queue, daemon=True).start()\n",
        "        pass\n",
        "the flag is claimed for a replacement that is never started: the "
        "queued work AND every future upload are stranded behind a claim nobody "
        "holds - the worst state, and the one the claim-before-spawn order "
        "makes possible. The same spawn line stands in `_enqueue_job` too, at "
        "the same indent: this is the FIRST occurrence, the release's, and "
        "`landed_in` says so",
        occurrences=2,
        nth=1,
    ),
    Mutant(
        "Q8", "the replacement claims the slot before it is started", "webapp/app.py",
        "        _job_worker_active = rearm\n",
        "        _job_worker_active = False\n",
        "REVIEW MAJOR-1, the shipped defect: the slot is released and the "
        "replacement is spawned with the flag left False, so for the life of "
        "the replacement the module says no worker exists and the next upload "
        "starts a second one - two threads draining one queue",
    ),
)

#: --------------------------------------------------------------------------
#: EXTRACT-PROMPT — `analysis/extract.py` and the guard that reaches it
#: --------------------------------------------------------------------------
EXTRACT_MUTANTS = (
    Mutant(
        "E1", "the prompt carries no exact-cent constant", "analysis/extract.py",
        "      Previous Balance / <N> Deposits/Credits / <N> Checks/Debits / Service Charge /",
        "      Previous Balance / 7 Deposits/Credits / 7 Checks/Debits / 1,234.56 /",
        "an amount-shaped constant comes back into the prompt. THE PAYLOAD IS "
        "INVENTED and is not the constant that was removed: a mutant that "
        "restored the real one would be the leak, written into tracked source "
        "by the tool that proves there is none",
    ),
    Mutant(
        "E2", "a quoted example carries no digits", "analysis/extract.py",
        '  Amount cell left blank ("<description as printed> <money token>"); use that',
        '  Amount cell left blank ("SOME DESCRIPTION 1,234.56"); use that',
        "a worked example goes back to carrying a figure welded to a payee - "
        "the class R-1 purged, in the half `AMOUNT_RE` cannot see. Payee and "
        "figure both INVENTED: the removed example's own tokens are what the "
        "standing privacy rule keeps out of this repository, and a structural "
        "gate needs no specimen",
    ),
    Mutant(
        "E3", "the alignment example keeps its VALUE row", "analysis/extract.py",
        "      <V4> / <V5> / <V6>",
        "      the values, in the same order",
        "the value row loses its `<V1>..<V3>` ordering - the shape pin, not "
        "the token pin",
    ),
    Mutant(
        "E4", "the alignment example keeps its LABEL row", "analysis/extract.py",
        "      Previous Balance / <N> Deposits/Credits / <N> Checks/Debits / Service Charge /\n"
        "      Interest Paid / Ending Balance   ...then...   <V1>- / <V2> / <V3> /\n"
        "      <V4> / <V5> / <V6>",
        "      the labels first, then the values",
        "MUTANT E5 FROM THE COMMIT: the two-column worked example is deleted "
        "outright, and every placeholder it named still stands in the prose "
        "around it. This is the mutant that survived the token pin",
    ),
    Mutant(
        "E5", "`extract.py` is out of PATTERN_SCAN_EXEMPT",
        "tests/test_no_statement_hardcodes.py",
        'PATTERN_SCAN_EXEMPT = {"metrics.py", "pipeline.py", "reconcile.py"}',
        'PATTERN_SCAN_EXEMPT = {"metrics.py", "pipeline.py", "reconcile.py", "extract.py"}',
        "the exemption comes back, so the amount scan stops seeing the prompt "
        "at all - the debt EXTRACT-PROMPT paid off",
    ),
)

#: --------------------------------------------------------------------------
#: RAISE-PRIVACY-3 — the six rerouted sites and the reader-name rule
#: --------------------------------------------------------------------------
RAISE_MUTANTS = (
    Mutant(
        "R1", "chase._money_required refuses privately", "analysis/chase.py",
        '        raise money_refusal("chase._money_required", value)',
        "        raise ValueError(value)",
        "site 1 reverted to the base tree's leak",
    ),
    Mutant(
        "R2", "scanned_small_bank._money refuses privately",
        "analysis/scanned_small_bank.py",
        '        raise money_refusal("scanned_small_bank._money", value)',
        "        raise ValueError(value)",
        "site 2 reverted",
    ),
    Mutant(
        "R3", "scanned_small_bank._iso refuses privately",
        "analysis/scanned_small_bank.py",
        '        raise date_refusal("scanned_small_bank._iso", value)',
        "        raise ValueError(value)",
        "site 3 reverted (the SHAPE half: `_MONTH_RE` did not match). The same "
        "line stands twice in this function - this is the FIRST, and R4 owns "
        "the second",
        occurrences=2,
        nth=1,
    ),
    Mutant(
        "R4", "scanned_small_bank._iso funnels through iso_or_none",
        "analysis/scanned_small_bank.py",
        "    iso = iso_or_none(year, int(month), int(day))\n"
        "    if iso is None:\n"
        '        raise date_refusal("scanned_small_bank._iso", value)\n'
        "    return iso",
        "    return date(year, int(month), int(day)).isoformat()",
        "THE SIXTH LEAK, reverted: `date()` echoes the offending month or day "
        "for a token whose SHAPE the regex proved and whose VALUE it did not",
    ),
    Mutant(
        "R5", "columbia_bank's period reader calls no strptime",
        "analysis/columbia_bank.py",
        "    previous_end = parsed_datetime(\n"
        '        dates.group(1), "%B %d, %Y", reader="columbia_bank.period").date()',
        '    previous_end = __import__("datetime").datetime.strptime(\n'
        '        dates.group(1), "%B %d, %Y").date()',
        "site 4 reverted to an escaping `strptime`, whose ValueError quotes "
        "the printed period",
    ),
    Mutant(
        "R6", "scotia's period reader calls no strptime", "analysis/scotia.py",
        "            parsed = parsed_datetime(\n"
        '                raw, "%b %d %Y", reader="scotia.period").date()',
        '            parsed = __import__("datetime").datetime.strptime(\n'
        '                raw, "%b %d %Y").date()',
        "site 5 reverted",
    ),
    Mutant(
        "R7", "the reader name is a source symbol, never the token",
        "analysis/scotia.py",
        '                raw, "%b %d %Y", reader="scotia.period").date()',
        '                raw, "%b %d %Y", reader=f"scotia.period {raw}").date()',
        "MUTANT R11 FROM THE COMMIT: the document travels in the READER "
        "argument, which every proof about `token` says nothing about",
    ),
    Mutant(
        "R8", "the reader name rule holds at the columbia site",
        "analysis/columbia_bank.py",
        '        dates.group(1), "%B %d, %Y", reader="columbia_bank.period").date()',
        '        dates.group(1), "%B %d, %Y", reader=f"columbia_bank.period {dates.group(1)}").date()',
        "R11's shape at the other repointed site",
    ),
    Mutant(
        "R9", "the refusal class stays ValueError", "analysis/scanned_small_bank.py",
        "from .date_tokens import date_refusal, iso_or_none",
        "from .date_tokens import iso_or_none\n"
        "def date_refusal(reader, token):\n"
        "    return TypeError(f'{reader} refused')",
        "the date refusal stops being a `ValueError`, so the four "
        "`except ValueError` handlers in this module stop catching it",
    ),
    Mutant(
        "R10", "the modules are chain-guarded", "tests/test_privacy3_boundaries.py",
        '    "analysis/chase.py": frozenset({"money_refusal"}),',
        "",
        "one of the four CHAIN_GUARDED registrations is removed, so a naked "
        "raise arriving in that module later would go unseen",
    ),
)

#: --------------------------------------------------------------------------
#: The OverflowError contract — one mutant per widened handler
#: --------------------------------------------------------------------------
OVERFLOW_MUTANTS = tuple(
    Mutant(
        f"O{index}",
        "every conversion guard in date_tokens catches OverflowError",
        "analysis/date_tokens.py",
        "except (ValueError, OverflowError):",
        "except ValueError:",
        "handler #%d of 8 narrowed back to the base tree's shape" % index,
        occurrences=8,
        nth=index,
    )
    for index in range(1, 9)
)

MUTANTS = QUEUE_MUTANTS + EXTRACT_MUTANTS + RAISE_MUTANTS + OVERFLOW_MUTANTS


def _nth_index(haystack: str, needle: str, nth: int) -> int:
    position = -1
    for _ in range(nth):
        position = haystack.find(needle, position + 1)
        if position < 0:
            return -1
    return position


def enclosing_function(source: str, offset: int) -> str:
    """The function the mutated text now sits inside, read off the AST.

    This is the anti-lie check: the table states where the mutation LANDED.
    """
    line = source[:offset].count("\n") + 1
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "<does not parse>"
    best = "<module level>"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= line <= end:
                best = node.name
    return best


def run_gate_set(repo: Path, timeout: int) -> tuple[int, list[str], str]:
    """(exit code, the failing test ids, the tail of the output)."""
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
         *GATE_SET],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (process.stdout or "") + (process.stderr or "")
    # Every FAILED/ERROR line, so the table names each killer rather than only
    # the first — which is why the run has no `-x`.
    killers = sorted(
        {
            line.split(" ", 1)[1].split(" ")[0]
            for line in output.splitlines()
            if line.startswith(("FAILED ", "ERROR ")) and " " in line
        }
    )
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
    repo = Path(__file__).resolve().parent.parent

    selected = [m for m in MUTANTS if args.only is None or m.id in set(args.only)]
    if args.list:
        for mutant in selected:
            print(f"{mutant.id:5s} {mutant.path:36s} {mutant.gate}")
        print(f"{len(selected)} mutants")
        return 0

    dirty = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if dirty:
        print("REFUSING: the tree is dirty; `git checkout --` would destroy an edit.")
        print(dirty)
        return 2

    print("=== baseline: the gate set on the unmutated branch ===")
    baseline_code, baseline_killers, baseline_tail = run_gate_set(repo, args.timeout)
    print(f"baseline exit={baseline_code} failures={baseline_killers}")
    if baseline_code != 0:
        print(baseline_tail)
        print("REFUSING: the gate set is not green before mutation; every kill "
              "below would be unattributable.")
        return 3

    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for mutant in selected:
        path = repo / mutant.path
        original = path.read_text(encoding="utf-8")
        count = original.count(mutant.old)
        if count != mutant.occurrences:
            rows.append(
                {
                    "id": mutant.id, "gate": mutant.gate, "verdict": "NOT APPLIED",
                    "detail": f"target text occurs {count}x, documented {mutant.occurrences}x",
                }
            )
            print(f"{mutant.id:5s} NOT APPLIED  (occurs {count}x, documented "
                  f"{mutant.occurrences}x)")
            continue
        offset = _nth_index(original, mutant.old, mutant.nth)
        mutated = original[:offset] + mutant.new + original[offset + len(mutant.old):]
        landed_in = enclosing_function(mutated, offset)
        try:
            path.write_text(mutated, encoding="utf-8")
            compiles = True
            try:
                compile(mutated, str(path), "exec")
            except SyntaxError as exc:
                compiles = False
                syntax = f"{type(exc).__name__}: {exc.msg}"
            if not compiles:
                rows.append(
                    {
                        "id": mutant.id, "gate": mutant.gate, "verdict": "NOT APPLIED",
                        "detail": f"the mutant does not compile ({syntax})",
                    }
                )
                print(f"{mutant.id:5s} NOT APPLIED  (does not compile: {syntax})")
                continue
            code, killers, tail = run_gate_set(repo, args.timeout)
        finally:
            subprocess.run(
                ["git", "-C", str(repo), "checkout", "--", mutant.path],
                check=True, capture_output=True,
            )
        verdict = "killed" if code != 0 else "SURVIVED"
        rows.append(
            {
                "id": mutant.id,
                "gate": mutant.gate,
                "path": mutant.path,
                "landed_in": landed_in,
                "describes": mutant.describes,
                "verdict": verdict,
                "exit": code,
                "killers": killers,
                "expected_survivor": mutant.expected_survivor,
                "tail": "" if code != 0 else tail,
            }
        )
        marker = "killed  " if code != 0 else "SURVIVED"
        print(f"{mutant.id:5s} {marker} exit={code} in={landed_in} "
              f"killers={killers[:4]}{'...' if len(killers) > 4 else ''}")

    killed = sum(1 for row in rows if row["verdict"] == "killed")
    survived = [row for row in rows if row["verdict"] == "SURVIVED"]
    not_applied = [row for row in rows if row["verdict"] == "NOT APPLIED"]
    report = {
        "mutants": len(rows),
        "killed": killed,
        "survived": len(survived),
        "not_applied": len(not_applied),
        "seconds": round(time.perf_counter() - started, 1),
        "gate_set": list(GATE_SET),
        "rows": rows,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, sort_keys=True))
    for row in survived:
        print(f"SURVIVOR {row['id']}: {row['describes']}")
    for row in not_applied:
        print(f"NOT APPLIED {row['id']}: {row['detail']}")

    final = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if final:
        print("WARNING: the tree did not restore clean:")
        print(final)
        return 4
    return 1 if survived or not_applied else 0


if __name__ == "__main__":
    raise SystemExit(main())
