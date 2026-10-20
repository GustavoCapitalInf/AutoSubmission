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
import os
import resource
import signal
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


# ---------------------------------------------------------------------------
# Execution guards (2026-08-28, Gustavo's blocker). Mutant O21 raises the
# per-day row cap to 10**9 and the row-cap test builds its fixture from the
# mutated constant: `[100] * (10**9 + 1)`, a second list of that size and ~10**9
# int objects — 30+ GB, and Linux overcommit let it reach the whole host. None
# of this changes what is mutated or how a verdict is scored: the same MUTANTS,
# the same two suites, one mutant at a time, a kill is still and only a named
# failing test. What changes is that the child cannot take the host with it.
# ---------------------------------------------------------------------------

#: Address-space cap for the pytest child (RLIMIT_AS). The unmutated suites
#: peak at 85 MB RSS; an allocation the mutant makes impossible to honour
#: raises MemoryError inside the test instead of growing the process.
DEFAULT_MEM_CAP_GB = 4
#: Hard wall-clock limit per mutant; the child's whole process group is killed
#: and reaped, and the mutant is reported TIMEOUT — never scored as a kill.
DEFAULT_TIMEOUT_S = 600
#: Refuse to start a mutant, and abort a running one, when the host's
#: MemAvailable falls under this.
DEFAULT_MIN_AVAILABLE_GB = 8


def _mem_available_gb() -> float:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1048576
    except OSError:
        pass
    return float("nan")


def _child_peak_rss_mb(pid: int) -> float | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


class _Run:
    """What `_run_suites` returns: the CompletedProcess shape the verdict logic
    reads (`returncode`, `stdout`) plus the execution telemetry."""

    def __init__(self, returncode, stdout, *, timed_out=False, aborted_memory=False,
                 peak_rss_mb=None, seconds=0.0, mem_before_gb=None, mem_after_gb=None):
        self.returncode = returncode
        self.stdout = stdout
        self.timed_out = timed_out
        self.aborted_memory = aborted_memory
        self.peak_rss_mb = peak_rss_mb
        self.seconds = seconds
        self.mem_before_gb = mem_before_gb
        self.mem_after_gb = mem_after_gb

    def telemetry(self) -> dict:
        return {"peak_rss_mb": self.peak_rss_mb, "seconds": round(self.seconds, 1),
                "mem_available_before_gb": self.mem_before_gb,
                "mem_available_after_gb": self.mem_after_gb,
                "timed_out": self.timed_out, "aborted_memory": self.aborted_memory}


def _run_suites(*, mem_cap_gb: float = DEFAULT_MEM_CAP_GB, timeout_s: float = DEFAULT_TIMEOUT_S,
                min_available_gb: float = DEFAULT_MIN_AVAILABLE_GB) -> _Run:
    """The two gate suites, in ONE child, sequentially, under a hard address-space
    cap and a hard timeout, with the child's peak RSS and the host's available
    memory recorded. No workers: `-p no:xdist` is passed even though xdist is
    not installed, so a future install cannot parallelise this silently."""
    cap = int(mem_cap_gb * (1 << 30))

    def limit() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))

    before = _mem_available_gb()
    if before < min_available_gb:
        return _Run(None, "", aborted_memory=True, mem_before_gb=round(before, 1),
                    mem_after_gb=round(before, 1))
    started = time.monotonic()
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header",
         "-p", "no:cacheprovider", "-p", "no:xdist", "--tb=no", "-rf"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True, preexec_fn=limit,
    )
    peak = 0.0
    timed_out = aborted = False
    import threading
    chunks: list[str] = []
    reader = threading.Thread(target=lambda: chunks.append(proc.stdout.read()), daemon=True)
    reader.start()
    while proc.poll() is None:
        rss = _child_peak_rss_mb(proc.pid)
        if rss is not None:
            peak = max(peak, rss)
        if time.monotonic() - started > timeout_s:
            timed_out = True
        elif _mem_available_gb() < min_available_gb:
            aborted = True
        if timed_out or aborted:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            break
        time.sleep(0.2)
    proc.wait()                      # reap the child (and, via the session, its group)
    reader.join(timeout=5)
    after = _mem_available_gb()
    return _Run(proc.returncode, "".join(chunks), timed_out=timed_out, aborted_memory=aborted,
                peak_rss_mb=round(peak, 1), seconds=time.monotonic() - started,
                mem_before_gb=round(before, 1), mem_after_gb=round(after, 1))


def _killers(stdout: str) -> list[str]:
    return sorted({
        line.split("::", 1)[1].split(" ")[0].split("[")[0]
        for line in stdout.splitlines()
        if line.startswith("FAILED ") and "::" in line
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="JSON written after EVERY mutant; --resume continues from it")
    parser.add_argument("--resume", action="store_true",
                        help="skip mutants already recorded in --checkpoint")
    parser.add_argument("--only", nargs="*", default=None,
                        help="run only these mutant ids (execution subset; the table is still the whole MUTANTS)")
    parser.add_argument("--dry-run", action="store_true",
                        help="check every anchor occurs exactly once and exit; runs no pytest")
    parser.add_argument("--mem-cap-gb", type=float, default=DEFAULT_MEM_CAP_GB)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--min-available-gb", type=float, default=DEFAULT_MIN_AVAILABLE_GB)
    args = parser.parse_args(argv)
    guards = dict(mem_cap_gb=args.mem_cap_gb, timeout_s=args.timeout_seconds,
                  min_available_gb=args.min_available_gb)

    if args.dry_run:
        bad = 0
        for mutant_id, relative, description, replacements, implied_by in MUTANTS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            misses = [before for before, _after in replacements if text.count(before) != 1]
            print(f"{mutant_id:4} {relative:28} {'anchors ok' if not misses else 'ANCHOR MISSING'}  {description}")
            bad += bool(misses)
        print(f"dry run: {len(MUTANTS)} mutants, {bad} with a missing anchor; no pytest was run")
        return 1 if bad else 0

    if _dirty():
        print("refusing to run on a dirty tree:\n" + _dirty(), file=sys.stderr)
        return 2

    done: dict[str, dict] = {}
    if args.resume and args.checkpoint is not None and args.checkpoint.is_file():
        done = {row["mutant"]: row for row in json.loads(args.checkpoint.read_text(encoding="utf-8")).get("rows", [])}
        print(f"RESUME: {len(done)} mutants already recorded in {args.checkpoint}")

    baseline = _run_suites(**guards)
    if baseline.returncode != 0:
        print("the two gate suites must pass unmutated first", file=sys.stderr)
        print(json.dumps(baseline.telemetry()), file=sys.stderr)
        print(baseline.stdout[-3000:], file=sys.stderr)
        return 2
    print("BASELINE green:", baseline.stdout.strip().splitlines()[-1], json.dumps(baseline.telemetry()))

    rows: list[dict[str, object]] = [done[m] for m, *_ in MUTANTS if m in done]
    survivors: list[str] = [r["mutant"] for r in rows if str(r["verdict"]).startswith("SURVIVED")]
    undisclosed: list[str] = [r["mutant"] for r in rows if r["verdict"] == "SURVIVED" and not r.get("implied_by")]
    not_applied: list[str] = [r["mutant"] for r in rows if r["verdict"] == "NOT-APPLIED"]
    invalid: list[str] = [r["mutant"] for r in rows if r["verdict"] == "INVALID"]
    unscored: list[str] = [r["mutant"] for r in rows if r["verdict"] in ("TIMEOUT", "ABORTED-MEMORY")]

    def checkpoint() -> None:
        if args.checkpoint is not None:
            args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
            args.checkpoint.write_text(json.dumps({"rows": rows}, indent=1), encoding="utf-8")

    for mutant_id, relative, description, replacements, implied_by in MUTANTS:
        if mutant_id in done or (args.only and mutant_id not in args.only):
            continue
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

        run = _run_suites(**guards)
        killers = _killers(run.stdout)
        collection_error = "error" in (run.stdout.strip().splitlines() or [""])[-1].lower()
        _git("checkout", "--", relative)
        if _dirty():
            print(f"{mutant_id}: the tree did not restore:\n{_dirty()}", file=sys.stderr)
            checkpoint()
            return 2

        if run.timed_out or run.aborted_memory:
            # An execution limit fired. This is NOT evidence about the gate —
            # not a kill, not a survival — so it is reported on its own and
            # the run exits non-zero until every mutant has a real verdict.
            verdict = "TIMEOUT" if run.timed_out else "ABORTED-MEMORY"
            unscored.append(mutant_id)
            rows.append({"mutant": mutant_id, "file": relative, "disables": description,
                         "verdict": verdict, "killed_by": [], "implied_by": implied_by,
                         "telemetry": run.telemetry()})
            print(f"{mutant_id}  {verdict}  {description}  {json.dumps(run.telemetry())}")
            checkpoint()
            if run.aborted_memory:
                print("aborting: host available memory is under the safe threshold", file=sys.stderr)
                return 3
            continue

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
                     "implied_by": implied_by, "telemetry": run.telemetry()})
        print(f"{mutant_id}  {verdict}  {description}  {json.dumps(run.telemetry())}")
        for killer in killers:
            print(f"        {killer}")
        if not killers and implied_by:
            print(f"        implied by: {implied_by}")
        checkpoint()

    report = {
        "mutants": len(MUTANTS),
        "killed": sum(1 for row in rows if row["verdict"] == "KILLED"),
        "survivors_disclosed_as_implied": [m for m in survivors if m not in undisclosed],
        "survivors_undisclosed": undisclosed,
        "not_applied": not_applied,
        "invalid": invalid,
        "unscored_execution_limits": unscored,
        "rows": rows,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(
        {key: report[key] for key in
         ("mutants", "killed", "survivors_disclosed_as_implied",
          "survivors_undisclosed", "not_applied", "invalid", "unscored_execution_limits")},
        sort_keys=True,
    ))
    return 1 if (undisclosed or not_applied or invalid or unscored) else 0


if __name__ == "__main__":
    raise SystemExit(main())
