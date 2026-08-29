"""The mutation table for RAISE-PRIVACY-4's eight rerouted `date()` sites.

    python -m tools.raisepriv4_mutation_table                # the whole table
    python -m tools.raisepriv4_mutation_table --only N1 N2   # a subset
    python -m tools.raisepriv4_mutation_table --list         # the roster, no runs

ONE MUTANT PER SITE, each reverting that site — and only that site — to the raw
`date(...)` call the base tree held, plus two that break the refusal in the two
ways an AST guard exists to catch. Each is applied ON DISK, the gate set runs
against it WITHOUT `-x` so every killer is named rather than only the first, and
the file is restored with `git checkout --`.

WHY EIGHT REVERTS AND NOT FIVE. The card's population is eight SITES standing
in five code locations: `bmo._statement_period` builds two dates, and so do
`farmers_merchants._parse_summary` and `td_can._parse_period`. A mutant per
LOCATION would leave four sites unpinned, and one of them —`bmo`'s
`monthrange` date — cannot be reached by any document once the start date is
readable. That site is pinned by the structural census and by nothing else,
which is precisely the case W3 §H14 warned about: the next raw `date()` will
arrive somewhere no input reaches.

The harness itself is `tools.hygiene8_mutation_table`'s, imported rather than
copied: the dirty-tree refusal, the documented occurrence count, the
`enclosing_function` anti-lie check and the compile check are batch-7 findings
and a second copy of them is a second thing to keep in step.

Restoring is `git checkout --`, so this tool writes only to files it has just
mutated and only inside the working tree. It reads no archive document, makes
no model call, and costs $0.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from tools.hygiene8_mutation_table import Mutant, _nth_index, enclosing_function

#: The three files that hold this card's gates. Nothing wider: a mutant killed
#: by an unrelated suite is a kill, but it is not evidence that the gate this
#: card added works, and evidence is the point.
GATE_SET = (
    "tests/test_raise_privacy4.py",
    "tests/test_privacy3_boundaries.py",
    "tests/test_raise_privacy3.py",
)

BMO_FUNNEL = (
    "    start_iso = iso_or_none(year, month, 1)\n"
    "    end_iso = iso_or_none(year, month, calendar.monthrange(year, month)[1])\n"
    "    if start_iso is None or end_iso is None:\n"
    "        raise date_refusal(\n"
    '            "bmo._statement_period", f"{match.group(1)} {match.group(2)}"\n'
    "        )\n"
    "    return date.fromisoformat(start_iso), date.fromisoformat(end_iso)"
)

#: `analysis/farmers_merchants.py` and `analysis/td_can.py` no longer import
#: `date` — the import went with the sites, as `scotia`'s did at `548e518` — so
#: their reverts reach the constructor through `__import__`. That is not a
#: dodge around the census: the guard matches on the CALL's attribute name, so
#: `__import__("datetime").date(...)` is reported exactly as `date(...)` is.
_DT = '__import__("datetime")'

MUTANTS = (
    Mutant(
        "N1", "bmo._statement_period, the period START date",
        "analysis/bmo.py",
        BMO_FUNNEL,
        "    start = date(year, month, 1)\n"
        "    end_iso = iso_or_none(year, month, calendar.monthrange(year, month)[1])\n"
        "    if end_iso is None:\n"
        "        raise date_refusal(\n"
        '            "bmo._statement_period", f"{match.group(1)} {match.group(2)}"\n'
        "        )\n"
        "    return start, date.fromisoformat(end_iso)",
        "the first of §H14.3's two bmo rows reverted: `(\\d{4})` admits `0000` "
        "and `date()` echoes the printed year back out of the parser",
    ),
    Mutant(
        "N2", "bmo._statement_period, the period END date",
        "analysis/bmo.py",
        BMO_FUNNEL,
        "    start_iso = iso_or_none(year, month, 1)\n"
        "    if start_iso is None:\n"
        "        raise date_refusal(\n"
        '            "bmo._statement_period", f"{match.group(1)} {match.group(2)}"\n'
        "        )\n"
        "    return date.fromisoformat(start_iso), date(\n"
        "        year, month, calendar.monthrange(year, month)[1])",
        "the second bmo row reverted. NO DRIVE CAN REACH IT — once the start "
        "date is readable the month's last day always is — so this mutant is "
        "the one that says out loud whether the structural census is doing the "
        "work the dynamic proof cannot",
    ),
    Mutant(
        "N3", "farmers_merchants._parse_summary, the period START cell",
        "analysis/farmers_merchants.py",
        "    period_start = iso_or_none(year, start_m, start_d)\n"
        "    if period_start is None:\n"
        '        raise date_refusal("farmers_merchants._parse_summary", m.group("start"))\n'
        "    stmt.period_start = period_start",
        f"    stmt.period_start = {_DT}.date(year, start_m, start_d).isoformat()",
        "§H14.3's `date(year, start_m, start_d)` reverted: three digit pairs "
        "prove a shape and not a date, and `date()` echoes the printed month",
    ),
    Mutant(
        "N4", "farmers_merchants._parse_summary, the period END cell",
        "analysis/farmers_merchants.py",
        "    period_end = iso_or_none(year, end_m, end_d)\n"
        "    if period_end is None:\n"
        '        raise date_refusal("farmers_merchants._parse_summary", m.group("end"))\n'
        "    stmt.period_end = period_end",
        f"    stmt.period_end = {_DT}.date(year, end_m, end_d).isoformat()",
        "the same shape on the period's end cell",
    ),
    Mutant(
        "N5", "td_can._parse_period, the period START token",
        "analysis/td_can.py",
        "    start = iso_or_none(2000 + int(sy), _MONTHS[sm], int(sd))\n"
        "    if start is None:\n"
        '        raise date_refusal("td_can._parse_period", m.group(0))',
        f"    start = {_DT}.date(2000 + int(sy), _MONTHS[sm], int(sd)).isoformat()",
        "§H14.3's `date(2000 + int(sy), _MONTHS[sm], int(sd))` reverted: "
        "`_PERIOD_RE`'s `(\\d{1,2})/(\\d{2})` proves two digit runs",
    ),
    Mutant(
        "N6", "td_can._parse_period, the period END token",
        "analysis/td_can.py",
        "    end = iso_or_none(2000 + int(ey), _MONTHS[em], int(ed))\n"
        "    if end is None:\n"
        '        raise date_refusal("td_can._parse_period", m.group(0))',
        f"    end = {_DT}.date(2000 + int(ey), _MONTHS[em], int(ed)).isoformat()",
        "the same shape on the period's end token",
    ),
    Mutant(
        "N7", "td_can._date_tokens, the row date",
        "analysis/td_can.py",
        "        iso = iso_or_none(year, _MONTHS[mon], int(day))\n"
        "        if iso is None:\n"
        "            raise date_refusal(\n"
        '                "td_can._date_tokens", f"{mon}{day}/{yy}" if yy else f"{mon}{day}"\n'
        "            )\n"
        "        out.append(iso)",
        f"        out.append({_DT}.date(year, _MONTHS[mon], int(day)).isoformat())",
        "§H14.3's `date(year, _MONTHS[mon], int(day))` reverted: a month WORD "
        "and a day SHAPE, and `date()` echoes the printed day",
    ),
    Mutant(
        "N8", "td_can._native_date_to_iso, the native row date",
        "analysis/td_can.py",
        "    iso = iso_or_none(default_year, _MONTHS[m.group(1).upper()], int(m.group(2)))\n"
        "    if iso is None:\n"
        '        raise date_refusal("td_can._native_date_to_iso", value)\n'
        "    return iso",
        f"    return {_DT}.date(\n"
        "        default_year, _MONTHS[m.group(1).upper()], int(m.group(2))).isoformat()",
        "the eighth site reverted. The reader keeps its FIRST refusal (the "
        "shape one), so this mutant also asks whether a drive can tell the two "
        "refusals of one reader apart — it can, because only one of the two "
        "shapes reaches the calendar",
    ),
    Mutant(
        "N9", "the refusal is the declared constructor",
        "analysis/farmers_merchants.py",
        '        raise date_refusal("farmers_merchants._parse_summary", m.group("start"))',
        '        raise ValueError(m.group("start"))',
        "the funnel is kept and the REFUSAL is replaced by a naked ValueError "
        "carrying the cell — the shape §MONEYPRIV MP0 named, and the reason "
        "`CHAIN_GUARDED` reads raise statements rather than trusting the fix",
    ),
    Mutant(
        "N10", "the refusal is unchained",
        "analysis/td_can.py",
        '        raise date_refusal("td_can._parse_period", m.group(0))',
        '        raise date_refusal("td_can._parse_period", m.group(0)) from ValueError(m.group(0))',
        "the refusal is correct and CHAINED: `str(exc)` is clean and the "
        "printed token rides out on `__cause__` and on the first rendered "
        "traceback. §MONEYPRIV MP2's failure, and the reason the drives assert "
        "on five surfaces rather than on the message",
        occurrences=2,
        nth=1,
    ),
)


def run_gate_set(repo: Path, timeout: int) -> tuple[int, list[str], str]:
    """(exit code, the failing test ids, the tail of the output)."""
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", *GATE_SET],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout,
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
    repo = Path(__file__).resolve().parent.parent

    selected = [m for m in MUTANTS if args.only is None or m.id in set(args.only)]
    if args.list:
        for mutant in selected:
            print(f"{mutant.id:5s} {mutant.path:32s} {mutant.gate}")
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
            rows.append({
                "id": mutant.id, "gate": mutant.gate, "verdict": "NOT APPLIED",
                "detail": f"target text occurs {count}x, documented {mutant.occurrences}x",
            })
            print(f"{mutant.id:5s} NOT APPLIED  (occurs {count}x, documented "
                  f"{mutant.occurrences}x)")
            continue
        offset = _nth_index(original, mutant.old, mutant.nth)
        mutated = original[:offset] + mutant.new + original[offset + len(mutant.old):]
        landed_in = enclosing_function(mutated, offset)
        try:
            path.write_text(mutated, encoding="utf-8")
            try:
                compile(mutated, str(path), "exec")
            except SyntaxError as exc:
                syntax = f"{type(exc).__name__}: {exc.msg}"
                rows.append({
                    "id": mutant.id, "gate": mutant.gate, "verdict": "NOT APPLIED",
                    "detail": f"the mutant does not compile ({syntax})",
                })
                print(f"{mutant.id:5s} NOT APPLIED  (does not compile: {syntax})")
                continue
            code, killers, tail = run_gate_set(repo, args.timeout)
        finally:
            subprocess.run(
                ["git", "-C", str(repo), "checkout", "--", mutant.path],
                check=True, capture_output=True,
            )
        verdict = "killed" if code != 0 else "SURVIVED"
        rows.append({
            "id": mutant.id,
            "gate": mutant.gate,
            "path": mutant.path,
            "landed_in": landed_in,
            "describes": mutant.describes,
            "verdict": verdict,
            "exit": code,
            "killers": killers,
            "tail": "" if code != 0 else tail,
        })
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
