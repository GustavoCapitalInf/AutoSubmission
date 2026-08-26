"""The FROST-OZK mutation table, as a committed harness — W3 §FROSTOZK §FZ12.

W3 §FZ6 records a 41-row mutation table, 39 killed and 2 provably redundant,
but the harness that produced it was never committed: the table was evidence
nobody else could re-run. This file is that harness, reconstructed row by row
from §FZ6 by Ocean's 2026-08-26 verification session, so the table's numbers
are reproducible rather than described.

    python -m tools.frostozk_mutation_table [--out table.json]

WHAT IT DOES. Each of the 41 rows is one mutant: an exact `before` -> `after`
replacement in `analysis/frost.py`, `analysis/bank_ozk.py` or
`analysis/count_semantics.py` that disables exactly the gate the §FZ6 row
names. The mutant is applied ON DISK, `tests/test_frost.py` and
`tests/test_bank_ozk.py` are run in full and WITHOUT `-x` so every killer is
named rather than only the first, and the file is restored with
`git checkout --`.

THREE PROPERTIES IT ENFORCES ON ITSELF, each of which a batch-7 or batch-8
mutation round lost to its absence:

* THE TREE IS CLEAN FIRST. Restoration discards uncommitted work, so this
  refuses to start on a dirty tree and re-checks cleanliness after every
  restore. A harness that silently reverts someone's edit is worse than no
  harness.
* THE MUTANT IS APPLIED AS DOCUMENTED. Every `before` must occur EXACTLY ONCE
  in the file; anything else is reported `NOT-APPLIED` and scored as nothing,
  never as a kill. The file is re-read after writing and compared against what
  was intended.
* A COLLECTION ERROR IS NOT A KILL. Each mutated file is compiled before the
  suite runs; a mutant that does not parse is reported `INVALID` and scored as
  nothing, because "the suite went red" and "the gate is tested" are different
  facts.

Exit 0 when every mutant is either KILLED or carries a disclosed algebraic
reason no document could isolate it; 1 names any UNDISCLOSED survivor, which
is a gate nothing tests.

READ-ONLY with respect to the archive: nothing here reads a document, opens
the sqlite index or makes a model call. It runs the two gate suites, whose
fixtures are invented.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FROST = "analysis/frost.py"
OZK = "analysis/bank_ozk.py"
SEMANTICS = "analysis/count_semantics.py"
TESTS = ("tests/test_frost.py", "tests/test_bank_ozk.py")

#: A mutant is `(id, file, what it disables, [(before, after), ...], implied_by)`.
#:
#: `implied_by` is a DISCLOSURE and not an excuse: a survivor with no argument
#: is a defect and this harness exits 1 on it.
#:
#: THE ALGEBRA BEHIND THE TWO DISCLOSED SURVIVORS, once. Over the OZK reader,
#: let `P, C, D, N` be the printed previous balance, credit total, debit total
#: and current balance, and let `grid[last]` be the last cell of the daily
#: grid. Every day's step is checked against the grid, so the walk telescopes:
#: `grid[last] = P + sum(signed rows)`. The totals gate gives
#: `sum(signed rows) = C - D`. So `P + C - D == N` (mutant O1's gate) and
#: `grid[last] == N` (mutant O7's gate) each imply the other, and removing
#: EITHER ALONE cannot change any outcome. Removing BOTH is the real hole, and
#: that is mutant `O1+O7`, which is killed.
MUTANTS: tuple[tuple[str, str, str, tuple[tuple[str, str], ...], str], ...] = (
    # -----------------------------------------------------------------
    # Frost — the summary strip
    # -----------------------------------------------------------------
    (
        'F1',
        FROST,
        "the box line's side order is ignored; DEPOSITS assumed first",
        ((
            '    first, second = (side.strip() for side in sides.groups())',
            '    first, second = "DEPOSITS", "WITHDRAWALS"',
        ),),
        '',
    ),
    (
        'F2',
        FROST,
        'the label line is no longer checked against its six known cells',
        ((
            '    if (head, no_a, no_b) != ("BALANCE LAST STATEMENT", "NO.", "NO."):\n'
            '        return None\n'
            '    if (amount_a, amount_b) != ("AMOUNT", "AMOUNT"):\n'
            '        return None\n'
            '    if tail != "BALANCE THIS STATEMENT":\n'
            '        return None\n',
            '    _ = (head, no_a, no_b, amount_a, amount_b, tail)\n',
        ),),
        '',
    ),
    (
        'F3',
        FROST,
        'the count slot\'s type check is dropped and the token coerced',
        ((
            '            if role.endswith("_count"):\n'
            '                if _COUNT_ONLY_RE.match(token) is None:\n'
            '                    return None\n'
            '                summary[role] = int(token)\n'
            '                continue\n',
            '            if role.endswith("_count"):\n'
            '                summary[role] = int(float(token.replace(",", "").rstrip("-")))\n'
            '                continue\n',
        ),),
        '',
    ),
    (
        'F4',
        FROST,
        "the strip's own arithmetic need not close",
        ((
            '    if (\n'
            '        summary["opening"] + summary["credit_total"] - summary["debit_total"]\n'
            '        != summary["closing"]\n'
            '    ):\n'
            '        return None\n',
            '    _ = summary["opening"]\n',
        ),),
        '',
    ),
    (
        'F5',
        FROST,
        'an unknown column head falls back to a layout',
        ((
            '    return _LAYOUTS.get(tuple(cell.split()))',
            '    return _LAYOUTS.get(tuple(cell.split()), "date_transaction_amount")',
        ),),
        '',
    ),
    (
        'F6',
        FROST,
        'an unparsable line inside a section is skipped',
        ((
            '            row = _row_from(layout, cell)\n'
            '            if row is None:\n'
            '                return None\n',
            '            row = _row_from(layout, cell)\n'
            '            if row is None:\n'
            '                continue\n',
        ),),
        '',
    ),
    (
        'F7',
        FROST,
        'the two printed totals need not reproduce',
        ((
            '    if credit_total != summary["credit_total"] '
            'or debit_total != summary["debit_total"]:\n'
            '        return None\n',
            '    _ = (credit_total, debit_total)\n',
        ),),
        '',
    ),
    (
        'F8',
        FROST,
        "the grid's two ends are not checked against the strip",
        ((
            '    if dated[0][1] != summary["opening"] or dated[-1][1] != summary["closing"]:\n'
            '        return None\n',
            '    _ = dated\n',
        ),),
        '',
    ),
    (
        'F9',
        FROST,
        'the issued date takes the first match, not the sole reading',
        ((
            '    issued_match = unique_match(markdown, _ISSUED_RE)',
            '    issued_match = _ISSUED_RE.search(markdown)',
        ),),
        '',
    ),
    (
        'F10',
        FROST,
        'the banner takes the first match, not the sole reading',
        ((
            '    banner = unique_match(markdown, _BANNER_RE)',
            '    banner = _BANNER_RE.search(markdown)',
        ),),
        '',
    ),
    (
        'F11',
        FROST,
        'the money format loses sub-dollar padding and trailing minus',
        ((
            '_AMOUNT = r"(?:\\d[\\d,]{0,15})?\\.\\d{2}-?"',
            '_AMOUNT = r"\\d[\\d,]{0,15}\\.\\d{2}"',
        ),),
        '',
    ),
    (
        'F12',
        FROST,
        'the money format loses ONLY the trailing minus',
        ((
            '_AMOUNT = r"(?:\\d[\\d,]{0,15})?\\.\\d{2}-?"',
            '_AMOUNT = r"(?:\\d[\\d,]{0,15})?\\.\\d{2}"',
        ),),
        '',
    ),
    (
        'F13',
        FROST,
        'the year always comes from the cycle date',
        ((
            '    year = issued.year - 1 if row.month > issued.month else issued.year',
            '    year = issued.year',
        ),),
        '',
    ),
    (
        'F14',
        FROST,
        'the product banner stops being required evidence',
        ((
            '    required("frost_business_checking_banner", _has_banner),',
            '    corroborating("frost_business_checking_banner", _has_banner),',
        ),),
        '',
    ),
    (
        'F15',
        FROST,
        'multi-up packing ignored; one physical line is one row',
        ((
            '        for cell in line.split("|"):',
            '        for cell in [line]:',
        ),),
        '',
    ),
    (
        'F16',
        FROST,
        "a period is derived from the grid's ends and published",
        ((
            '        currency="USD",\n'
            '        currency_source="institution_default",\n'
            '    )\n'
            '    # The bank\'s own end-of-day balances, exactly as printed.',
            '        currency="USD",\n'
            '        currency_source="institution_default",\n'
            '        period_start=dated[0][0],\n'
            '        period_end=dated[-1][0],\n'
            '    )\n'
            '    # The bank\'s own end-of-day balances, exactly as printed.',
        ),),
        '',
    ),
    (
        'F17',
        FROST,
        'a grid day printed twice takes the last reading',
        ((
            '        if printed_by_day.setdefault(iso, row.cents) != row.cents:\n'
            '            return None\n',
            '        printed_by_day[iso] = row.cents\n',
        ),),
        '',
    ),
    # -----------------------------------------------------------------
    # Bank OZK — the direction solve
    # -----------------------------------------------------------------
    (
        'O1',
        OZK,
        'the summary fail-fast is removed',
        ((
            '    if figures["previous"] + figures["credits"] '
            '- figures["debits"] != figures["current"]:\n'
            '        return None\n',
            '    _ = figures["previous"]\n',
        ),),
        'O7 — the grid-close check. The walk telescopes to '
        '`grid[last] = P + sum(signed rows)` and the totals gate fixes '
        '`sum(signed rows) = C - D`, so `P + C - D == N` and `grid[last] == N` '
        'imply each other and neither can be isolated. The PAIR is mutant '
        'O1+O7, and it is killed.',
    ),
    (
        'O2',
        OZK,
        'the printed day count is not checked against the as-of dates',
        ((
            '    if (end - start).days + 1 != int(printed_days):\n'
            '        return None\n',
            '    _ = printed_days\n',
        ),),
        '',
    ),
    (
        'O3',
        OZK,
        'the captured row count need not equal the two printed counts',
        ((
            '    if len(cheques) + len(others) != credits_expected + debits_expected:\n'
            '        return None\n',
            '    _ = (cheques, others)\n',
        ),),
        '',
    ),
    (
        'O4',
        OZK,
        'an off-grid row is dropped instead of refusing',
        ((
            '    if any(row.day not in grid for row in cheques + others):\n'
            '        return None\n',
            '    cheques = [row for row in cheques if row.day in grid]\n'
            '    others = [row for row in others if row.day in grid]\n',
        ),),
        '',
    ),
    (
        'O5',
        OZK,
        'the global solve takes the first solution',
        ((
            '    return found[0] if len(found) == 1 else None',
            '    return found[0] if found else None',
        ),),
        '',
    ),
    (
        'O6',
        OZK,
        'the printed credit count does not choose between day solutions',
        ((
            '    chosen = _unique_global(per_day, counts, credits_expected)',
            '    chosen = [day[0] for day in per_day]',
        ),),
        '',
    ),
    (
        'O7',
        OZK,
        'the grid need not close on the printed current balance',
        ((
            '    if walk[-1][1] != figures["current"]:\n'
            '        return None\n',
            '    _ = walk\n',
        ),),
        'O1 — the summary fail-fast, by the same algebra. Removing either '
        'alone cannot change an outcome; the pair is mutant O1+O7.',
    ),
    (
        'O8',
        OZK,
        'a grid date printed twice with two values is accepted',
        ((
            '            if value is None or (iso in grid and grid[iso] != value):\n'
            '                return None\n',
            '            if value is None:\n'
            '                return None\n',
        ),),
        '',
    ),
    (
        'O9',
        OZK,
        'a grid day carrying no rows is accepted',
        ((
            '        if not known and not unknown:\n'
            '            return None\n',
            '        if not known and not unknown:\n'
            '            per_day.append([frozenset()])\n'
            '            counts.append([0])\n'
            '            balance = printed_balance\n'
            '            continue\n',
        ),),
        '',
    ),
    (
        'O10',
        OZK,
        'a quoted amount inside a description is not masked',
        ((
            '            masked = _QUOTED_RE.sub(lambda hit: " " * len(hit.group(0)), segment)',
            '            masked = segment',
        ),),
        '',
    ),
    (
        'O11',
        OZK,
        "the row's amount is the FIRST money token",
        ((
            '            cents = _cents(amounts[-1].group(0))',
            '            cents = _cents(amounts[0].group(0))',
        ),),
        '',
    ),
    (
        'O12',
        OZK,
        'the row-date token loses its left-hand boundary',
        ((
            '_ROW_DATE_RE = re.compile(r"(?<![\\d/])(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])(?!\\d)")',
            '_ROW_DATE_RE = re.compile(r"(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])(?!\\d)")',
        ),),
        '',
    ),
    (
        'O13',
        OZK,
        'the row-date token loses its right-hand boundary',
        ((
            '_ROW_DATE_RE = re.compile(r"(?<![\\d/])(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])(?!\\d)")',
            '_ROW_DATE_RE = re.compile(r"(?<![\\d/])(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])")',
        ),),
        '',
    ),
    (
        'O14',
        OZK,
        'the row-date token stops bounding the month to 01-12',
        ((
            '_ROW_DATE_RE = re.compile(r"(?<![\\d/])(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])(?!\\d)")',
            '_ROW_DATE_RE = re.compile(r"(?<![\\d/])(\\d{2})/(0[1-9]|[12]\\d|3[01])(?!\\d)")',
        ),),
        '',
    ),
    (
        'O15',
        OZK,
        'a date the period cannot place is skipped',
        ((
            '            if iso is None:\n'
            '                # A date-shaped token the printed period cannot place is not a\n'
            '                # row this reader may guess at, and it is not description text\n'
            '                # either: it may be a row whose date was mangled. Fail closed.\n'
            '                return None\n',
            '            if iso is None:\n'
            '                continue\n',
        ),),
        '',
    ),
    (
        'O16',
        OZK,
        'a second printed account number is accepted',
        ((
            '    if labelled != {banner.group(2)}:\n'
            '        return None\n',
            '    if banner.group(2) not in labelled:\n'
            '        return None\n',
        ),),
        '',
    ),
    (
        'O17',
        OZK,
        'the service-centre block stops being required evidence',
        ((
            '    required("ozk_service_centre", _has_service_centre),',
            '    corroborating("ozk_service_centre", _has_service_centre),',
        ),),
        '',
    ),
    (
        'O18',
        OZK,
        'a grid balance is read unsigned',
        ((
            '            value = _cents(balance.group(0), signed=True)',
            '            value = _cents(balance.group(0), signed=False)',
        ),),
        '',
    ),
    (
        'O19',
        OZK,
        'cheques stop seeding their day as known debits',
        ((
            '        residual = printed_balance - balance + sum(row.cents for row in known)',
            '        residual = printed_balance - balance',
        ),),
        '',
    ),
    (
        'O21',
        OZK,
        'the per-day row cap is removed',
        (('_MAX_DAY_ROWS = 64', '_MAX_DAY_ROWS = 10 ** 9'),),
        '',
    ),
    (
        'O22',
        OZK,
        'the per-day node budget is removed',
        (('_MAX_DAY_NODES = 200_000', '_MAX_DAY_NODES = 10 ** 12'),),
        '',
    ),
    (
        'O23',
        OZK,
        'the per-day solution cap is removed',
        (('_MAX_DAY_SOLUTIONS = 64', '_MAX_DAY_SOLUTIONS = 10 ** 9'),),
        '',
    ),
    (
        'O1+O7',
        OZK,
        'BOTH the summary fail-fast and the grid-close check removed together',
        (
            (
                '    if figures["previous"] + figures["credits"] '
                '- figures["debits"] != figures["current"]:\n'
                '        return None\n',
                '    _ = figures["previous"]\n',
            ),
            (
                '    if walk[-1][1] != figures["current"]:\n'
                '        return None\n',
                '    _ = walk\n',
            ),
        ),
        '',
    ),
    # -----------------------------------------------------------------
    # The count-semantics entry the Frost card owns
    # -----------------------------------------------------------------
    (
        'C1',
        SEMANTICS,
        '`frost:debit` declared comparable',
        ((
            '        "debit": CountSemantics(\n'
            '            comparable=False,\n'
            '            scope="named_row_classes_excluded",',
            '        "debit": CountSemantics(\n'
            '            comparable=True,\n'
            '            scope="named_row_classes_excluded",',
        ),),
        '',
    ),
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def _dirty() -> str:
    return _git("status", "--porcelain").stdout.strip()


def _write(path: Path, text: str) -> None:
    """OneDrive holds file handles; a transient PermissionError is retried."""
    for attempt in range(8):
        try:
            path.write_text(text, encoding="utf-8", newline="\n")
            return
        except PermissionError:
            time.sleep(0.25 * (attempt + 1))
    path.write_text(text, encoding="utf-8", newline="\n")


def _run_suites() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header",
         "-p", "no:cacheprovider", "--tb=no", "-rf"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def _killers(stdout: str) -> list[str]:
    return sorted({
        line.split("::", 1)[1].split(" ")[0].split("[")[0]
        for line in stdout.splitlines()
        if line.startswith("FAILED ") and "::" in line
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if _dirty():
        print("refusing to run on a dirty tree:\n" + _dirty(), file=sys.stderr)
        return 2

    baseline = _run_suites()
    if baseline.returncode != 0:
        print("the two gate suites must pass unmutated first", file=sys.stderr)
        print(baseline.stdout[-3000:], file=sys.stderr)
        return 2
    print("BASELINE green:", baseline.stdout.strip().splitlines()[-1])

    rows: list[dict[str, object]] = []
    survivors: list[str] = []
    undisclosed: list[str] = []
    not_applied: list[str] = []
    invalid: list[str] = []

    for mutant_id, relative, description, replacements, implied_by in MUTANTS:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        expected = original
        misses = [
            before for before, _after in replacements if expected.count(before) != 1
        ]
        if misses:
            not_applied.append(mutant_id)
            print(f"{mutant_id}  NOT-APPLIED  (an anchor did not occur exactly once)")
            rows.append({"mutant": mutant_id, "file": relative,
                         "disables": description, "verdict": "NOT-APPLIED",
                         "killed_by": [], "implied_by": implied_by})
            continue
        for before, after in replacements:
            expected = expected.replace(before, after, 1)

        _write(path, expected)
        applied = path.read_text(encoding="utf-8")
        if applied == original or applied != expected:
            _git("checkout", "--", relative)
            not_applied.append(mutant_id)
            print(f"{mutant_id}  NOT-APPLIED  (the file on disk is not the mutant)")
            rows.append({"mutant": mutant_id, "file": relative,
                         "disables": description, "verdict": "NOT-APPLIED",
                         "killed_by": [], "implied_by": implied_by})
            continue

        # A mutant that does not parse cannot be scored: a collection error is
        # not evidence that any gate is tested.
        try:
            compile(applied, str(path), "exec")
        except SyntaxError:
            _git("checkout", "--", relative)
            invalid.append(mutant_id)
            print(f"{mutant_id}  INVALID  (the mutated module does not parse)")
            rows.append({"mutant": mutant_id, "file": relative,
                         "disables": description, "verdict": "INVALID",
                         "killed_by": [], "implied_by": implied_by})
            continue

        run = _run_suites()
        killers = _killers(run.stdout)
        collection_error = "error" in (run.stdout.strip().splitlines() or [""])[-1].lower()
        _git("checkout", "--", relative)
        if _dirty():
            print(f"{mutant_id}: the tree did not restore:\n{_dirty()}", file=sys.stderr)
            return 2

        if collection_error and not killers:
            invalid.append(mutant_id)
            verdict = "INVALID"
        elif killers:
            verdict = "KILLED"
        else:
            verdict = "SURVIVED (disclosed)" if implied_by else "SURVIVED"
            survivors.append(mutant_id)
            if not implied_by:
                undisclosed.append(mutant_id)

        rows.append({"mutant": mutant_id, "file": relative, "disables": description,
                     "verdict": verdict.split(" ")[0], "killed_by": killers,
                     "implied_by": implied_by})
        print(f"{mutant_id}  {verdict}  {description}")
        for killer in killers:
            print(f"        {killer}")
        if not killers and implied_by:
            print(f"        implied by: {implied_by}")

    report = {
        "mutants": len(MUTANTS),
        "killed": sum(1 for row in rows if row["verdict"] == "KILLED"),
        "survivors_disclosed_as_implied": [m for m in survivors if m not in undisclosed],
        "survivors_undisclosed": undisclosed,
        "not_applied": not_applied,
        "invalid": invalid,
        "rows": rows,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(
        {key: report[key] for key in
         ("mutants", "killed", "survivors_disclosed_as_implied",
          "survivors_undisclosed", "not_applied", "invalid")},
        sort_keys=True,
    ))
    return 1 if (undisclosed or not_applied or invalid) else 0


if __name__ == "__main__":
    raise SystemExit(main())
