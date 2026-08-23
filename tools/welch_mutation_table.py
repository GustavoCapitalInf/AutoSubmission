"""The WELCH mutation table, run — W3 §WELCH.

Every gate `analysis/welch_state_bank.py` adds, disabled one at a time, with
`tests/test_welch_state_bank.py` run in full each time and NO `-x`, so every
test that kills a mutant is named rather than only the first one. A gate no
mutant can break is not a gate; a test named after a gate that survives its
mutant is not a test of it.

Two properties this harness enforces on ITSELF, because batch 7 lost a mutation
round to each of them:

* THE MUTANT IS APPLIED AS DOCUMENTED. Each entry is an exact
  `before` -> `after` string replacement that must occur EXACTLY ONCE, and the
  file is re-read and diffed after writing. A "reorder" mutant that silently
  deleted the thing it claimed to reorder pinned nothing.
* THE TREE IS CLEAN FIRST. Restoration is `git checkout -- <path>`, which
  discards uncommitted work, so this refuses to start on a dirty tree and
  re-checks cleanliness after every restore. OneDrive holds file handles, so a
  write or a restore is retried rather than scored as a result.

    python -m tools.welch_mutation_table [--out table.json]

Exit 0 when every mutant is killed; 1 names the survivors.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = "analysis/welch_state_bank.py"
TESTS = "tests/test_welch_state_bank.py"

#: A mutant is `(id, file, what it disables, [(before, after), ...], implied_by)`.
#:
#: `implied_by` is a DISCLOSURE, not an excuse. Four of this reader's
#: constraints are algebraically dependent and the dependency is exact, so no
#: document can isolate any one of them and the honest thing is to say which,
#: with the proof, rather than to write a test that appears to pin one and
#: actually pins its neighbour. Write the argument here or leave it empty; a
#: survivor with no argument is a defect and this harness says so.
#:
#: THE ALGEBRA, once. Let `B, C, D, E` be the printed beginning balance, credit
#: total, debit total and ending balance, and `c, d` this reader's own sums.
#: The gates are  (i) `B + C - D = E` (the summary closes), (ii) `c = C`,
#: (iii) `d = D`, and (iv) the daily walk, which starts at `B`, adds every
#: posting and must arrive at `E` — that is, `B + c - d = E`. Substituting
#: (ii) and (iii) into (iv) gives (i). ANY THREE IMPLY THE FOURTH, so each of
#: the four survives its own mutant and every PAIR is killable: M26 removes
#: (i) and (iv), M27 removes (ii) and (iii).
MUTANTS: tuple[tuple[str, str, str, tuple[tuple[str, str], ...], str], ...] = (
    (
        'M01',
        MODULE,
        "detection no longer requires the issuer's home-office PO box",
        (
            ('    required("issuer_home_office_po_box", lambda t: _HOME_OFFICE_RE.search(t) is not None),\n', ''),
        ),
        '',
    ),
    (
        'M02',
        MODULE,
        'the branch ladder needs one rung instead of three',
        (
            ('_LADDER_MINIMUM_RUNGS = 3', '_LADDER_MINIMUM_RUNGS = 1'),
        ),
        '',
    ),
    (
        'M03',
        MODULE,
        'detection no longer requires the counted summary grammar',
        (
            ('    required("summary_counts_grammar", lambda t: _SUMMARY_RE.search(t) is not None),\n', ''),
        ),
        '',
    ),
    (
        'M04',
        MODULE,
        'the summary box no longer has to close',
        (
            ('    if figures["beginning"] + figures["credits"] - figures["debits"] != figures["ending"]:\n        return None\n', ''),
        ),
        'constraint (i), implied by (ii)+(iii)+(iv); this check is a FAIL-FAST that rejects a mis-read summary before a row is read, and M26 kills it paired with (iv)',
    ),
    (
        'M05',
        MODULE,
        'the summary is taken from the first printing instead of the sole one',
        (
            ('    match = unique_match(source, _SUMMARY_RE)', '    match = _SUMMARY_RE.search(source)'),
        ),
        '',
    ),
    (
        'M06',
        MODULE,
        "the masthead account no longer has to agree with the summary's",
        (
            ('    if masthead is None or masthead.group(1) != match.group("account"):\n        return None\n', ''),
        ),
        '',
    ),
    (
        'M07',
        MODULE,
        'a period that ends before it starts is accepted',
        (
            ('    if end < start:\n        return None\n', ''),
        ),
        'a reversed period is an EMPTY date range, so `iso_unique_in_period` can place no posting at all and `_read_regions` refuses every row; with no postings `parse` refuses too. Unkillable by construction, and kept as a fail-fast that names the contradiction at the top of the reader',
    ),
    (
        'M08',
        MODULE,
        'the period is taken from the first printing instead of the sole one',
        (
            ('    match = unique_match(source, _PERIOD_RE)', '    match = _PERIOD_RE.search(source)'),
        ),
        '',
    ),
    (
        'M09',
        MODULE,
        'the printed credit count is no longer checked',
        (
            ('    if len(credits) != summary.credit_count or len(debits) != summary.debit_count:', '    if len(debits) != summary.debit_count:'),
        ),
        '',
    ),
    (
        'M10',
        MODULE,
        'the printed debit count is no longer checked',
        (
            ('    if len(credits) != summary.credit_count or len(debits) != summary.debit_count:', '    if len(credits) != summary.credit_count:'),
        ),
        '',
    ),
    (
        'M11',
        MODULE,
        'the printed credit total is no longer checked',
        (
            ('    if sum(p.cents for p in credits) != summary.credits:\n        return None\n', ''),
        ),
        'constraint (ii), implied by (i)+(iii)+(iv); M27 kills it paired with (iii)',
    ),
    (
        'M12',
        MODULE,
        'the printed debit total is no longer checked',
        (
            ('    if sum(p.cents for p in debits) != summary.debits:\n        return None\n', ''),
        ),
        'constraint (iii), implied by (i)+(ii)+(iv); M27 kills it paired with (ii)',
    ),
    (
        'M13',
        MODULE,
        "the `Checks Cleared` table is never read (the census's measured failure)",
        (
            ('        if _CHECKS_BANNER_RE.match(line):\n            region = "checks"\n            continue\n', '        if _CHECKS_BANNER_RE.match(line):\n            region = None\n            continue\n'),
        ),
        '',
    ),
    (
        'M14',
        MODULE,
        'the daily grid no longer has to replay',
        (
            ('    if not _grid_replays(\n        snapshots, postings, summary=summary, period_start=period_start\n    ):\n        return None\n', ''),
        ),
        '',
    ),
    (
        'M15',
        MODULE,
        'a grid that prints one day twice is accepted',
        (
            ('    if len(set(days)) != len(days):\n        return False\n', ''),
        ),
        '',
    ),
    (
        'M16',
        MODULE,
        'the grid no longer has to name exactly the days that moved',
        (
            ('    if set(days) != set(moved) | {opening}:\n        return False\n', ''),
        ),
        '',
    ),
    (
        'M17',
        MODULE,
        'the replay no longer has to land on the printed ending balance',
        (
            ('    return balance == summary.ending', '    return True'),
        ),
        "constraint (iv)'s endpoint, implied by (i)+(ii)+(iii); M26 kills it paired with (i)",
    ),
    (
        'M18',
        MODULE,
        'text left over after the last anchor on a line is ignored',
        (
            ('    if line[cursor:].strip():\n        return None\n', ''),
        ),
        '',
    ),
    (
        'M19',
        MODULE,
        'a ledger anchor no longer needs a description in front of it',
        (
            ('        if described and not before:\n            return None\n', ''),
        ),
        '',
    ),
    (
        'M20',
        MODULE,
        'text between two grid or check pairs is absorbed instead of refused',
        (
            ('        if not described and before:\n            return None\n', ''),
        ),
        '',
    ),
    (
        'M21',
        MODULE,
        'a ledger amount may carry a sign that contradicts its banner',
        (
            ('                cents = _cents(span.group("amount"), signed=False)\n                if iso is None or cents is None:\n                    return None\n                postings.append(\n                    _Posting(iso, description, cents, credit=region == "credit")\n                )', '                cents = _cents(span.group("amount"), signed=True)\n                if iso is None or cents is None:\n                    return None\n                postings.append(\n                    _Posting(iso, description, abs(cents), credit=region == "credit")\n                )'),
        ),
        '',
    ),
    (
        'M22',
        MODULE,
        'the ledger date anchor accepts every Unicode decimal digit again',
        (
            ('rf"(?<![\\d/])(?P<month>[0-9]{{1,2}})/(?P<day>[0-9]{{1,2}})\\s+(?P<amount>{_FIGURE})"', 'rf"(?<![\\d/])(?P<month>\\d{{1,2}})/(?P<day>\\d{{1,2}})\\s+(?P<amount>{_FIGURE})"'),
        ),
        '',
    ),
    (
        'M23',
        MODULE,
        'a posting date is no longer bounded by the printed period',
        (
            ('    return iso_unique_in_period(\n        int(span.group("month")), int(span.group("day")),\n        start=period_start, end=period_end,\n    )', '    return iso_unique_in_period(\n        int(span.group("month")), int(span.group("day")),\n        start=period_start.replace(month=1, day=1),\n        end=period_end.replace(month=12, day=31),\n    )'),
        ),
        '',
    ),
    (
        'M24',
        MODULE,
        'a line carrying a digit is published as the product line',
        (
            ('        if any(character.isdigit() for character in candidate):\n            return None\n', ''),
        ),
        '',
    ),
    (
        'M25',
        MODULE,
        'the currency claims an evidence class the reader did not earn',
        (
            ('        currency_source="institution_default",', '        currency_source="printed",'),
        ),
        '',
    ),
    (
        'M26',
        MODULE,
        "the closing identity AND the replay's arrival at the printed ending balance",
        (
            ('    if figures["beginning"] + figures["credits"] - figures["debits"] != figures["ending"]:\n        return None\n', ''),
            ('    return balance == summary.ending', '    return True'),
        ),
        '',
    ),
    (
        'M27',
        MODULE,
        'BOTH printed per-direction totals',
        (
            ('    if sum(p.cents for p in credits) != summary.credits:\n        return None\n', ''),
            ('    if sum(p.cents for p in debits) != summary.debits:\n        return None\n', ''),
        ),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if _dirty():
        print("refusing to run on a dirty tree:\n" + _dirty(), file=sys.stderr)
        return 2

    baseline = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if baseline.returncode != 0:
        print("the unmutated suite must pass first", file=sys.stderr)
        print(baseline.stdout[-3000:], file=sys.stderr)
        return 2

    rows: list[dict[str, object]] = []
    survivors: list[str] = []
    undisclosed: list[str] = []
    for mutant_id, relative, description, replacements, implied_by in MUTANTS:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        expected = original
        for before, after in replacements:
            occurrences = expected.count(before)
            if occurrences != 1:
                print(f"{mutant_id}: `before` occurs {occurrences} times, not once",
                      file=sys.stderr)
                return 2
            expected = expected.replace(before, after, 1)
        _write(path, expected)
        applied = path.read_text(encoding="utf-8")
        # The mutant is what it says it is, not what it was meant to be.
        if applied == original or applied != expected:
            print(f"{mutant_id}: the mutant did not apply as documented", file=sys.stderr)
            _git("checkout", "--", relative)
            return 2

        run = subprocess.run(
            [sys.executable, "-m", "pytest", TESTS, "-q", "--no-header",
             "-p", "no:cacheprovider", "--tb=no", "-rf"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        killers = sorted(
            line.split("::", 1)[1].split(" ")[0].split("[")[0]
            for line in run.stdout.splitlines()
            if line.startswith("FAILED ")
        )
        killers = sorted(set(killers))
        _git("checkout", "--", relative)
        if _dirty():
            print(f"{mutant_id}: the tree did not restore:\n{_dirty()}", file=sys.stderr)
            return 2

        rows.append({
            "mutant": mutant_id,
            "file": relative,
            "disables": description,
            "killed": bool(killers),
            "killed_by": killers,
            "implied_by": implied_by,
        })
        if not killers:
            survivors.append(mutant_id)
            if not implied_by:
                undisclosed.append(mutant_id)
        state = "KILLED" if killers else ("SURVIVED (disclosed)" if implied_by else "SURVIVED")
        print(f"{mutant_id}  {state}  {description}")
        for killer in killers:
            print(f"        {killer}")
        if not killers and implied_by:
            print(f"        implied by: {implied_by}")

    report = {
        "mutants": len(MUTANTS),
        "killed": len(MUTANTS) - len(survivors),
        "survivors_disclosed_as_implied": [m for m in survivors if m not in undisclosed],
        "survivors_undisclosed": undisclosed,
        "rows": rows,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(
        {k: report[k] for k in
         ("mutants", "killed", "survivors_disclosed_as_implied", "survivors_undisclosed")},
        sort_keys=True,
    ))
    # An UNDISCLOSED survivor is the failure this harness exists to report: a
    # gate nothing tests. A disclosed one carries its own algebraic proof that
    # no document could isolate it, and the pair mutant that does kill it.
    return 1 if undisclosed else 0


if __name__ == "__main__":
    raise SystemExit(main())
