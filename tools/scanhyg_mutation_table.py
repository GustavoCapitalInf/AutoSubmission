"""One mutant per gate this branch adds, applied on disk and scored by name.

W3 §SCANHYG's mutation harness. A test named after a gate is not a test OF that
gate: the only way to know a gate is pinned is to break it and watch a named
test fail. Every mutant here is a change to ONE decision, documented in the
table below as the sentence it makes the reader say, and every run records the
tests that killed it — never `-x`, so a mutant that several tests catch names
them all and a mutant that nothing catches is disclosed rather than lost.

    python -m tools.scanhyg_mutation_table [--out <private>/mutants.json]
                                           [--only U1 G3 ...]

REFUSES A DIRTY TREE, first thing. This harness restores with `git checkout --`,
which discards uncommitted work in the files it touches; batch 7 lost an
uncommitted edit to exactly that. A clean tree is checked before the first
mutant and again after the last one.

WHAT IS RUN: the five test files this branch adds to or changes, and nothing
else. The suite, the corpus gate and the archive sweep are the train's.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

TEST_FILES = (
    "tests/test_southside_scanned.py",
    "tests/test_citizens_scanned.py",
    "tests/test_eq_bank_scanned.py",
    "tests/test_shared_parser_utils.py",
    "tests/test_no_parser_helper_clones.py",
)

#: The `_tf_one` paraphrase this branch removed, restored verbatim from the
#: base commit. The clone guard's whole claim is that this cannot come back.
_REMOVED_PARAPHRASE = '''def _tf_one(pattern: re.Pattern[str], source: str):
    """The document's single reading of a summary term, or None."""
    matches = pattern.findall(source)
    if not matches or len(set(matches)) > 1:
        return None
    return pattern.search(source)


'''

#: (id, gate, file, old, new, what the mutant makes the code say)
MUTANTS: tuple[tuple[str, str, str, str, str, str], ...] = (
    # --- SS-UNIQUE-MATCH (efc5ced) ---------------------------------------
    (
        "U1", "the one-distinct-reading rule (southside summary)",
        "analysis/scanned_small_bank.py",
        "from .tables import compact_whitespace, unique_match\nfrom .td_can import normalize_mojibake\n",
        "from .tables import compact_whitespace\nfrom .td_can import normalize_mojibake\n\n\n"
        "def unique_match(text, pattern):\n    return pattern.search(text)\n",
        "a summary row printed twice with two values is read as its FIRST printing",
    ),
    (
        "U2", "the row patterns match horizontal whitespace only",
        "analysis/scanned_small_bank.py",
        '_SS_H = r"[^\\S\\n]"',
        '_SS_H = r"\\s"',
        "a figure on the line BELOW a label may answer that label",
    ),
    (
        "U3", "`isdecimal`, not `isdigit`, on the summary count cell",
        "analysis/scanned_small_bank.py",
        'found[key + "_count"] = int(count) if count and count.isdecimal() else None',
        'found[key + "_count"] = int(count) if count and count.isdigit() else None',
        "a count digit the scan resolved as a SUPERSCRIPT is converted rather than refused",
    ),
    # --- SS-GRID-AMOUNTS (24b77a8) ---------------------------------------
    (
        "G1", "the printed daily grid as an AMOUNT oracle",
        "analysis/scanned_small_bank.py",
        "        if abs(step - moved) > 0.01:",
        "        if False and abs(step - moved) > 0.01:",
        "a span whose printed step and whose ledger disagree is not a finding",
    ),
    (
        "G2", "the walk is seeded at the summary's own beginning balance",
        "analysis/scanned_small_bank.py",
        "previous_day, previous_balance = start - timedelta(days=1), stmt.beginning_balance",
        "previous_day, previous_balance = start - timedelta(days=1), 0.0",
        "the first printed cell is compared against a walk that started from nothing",
    ),
    (
        "G3", "a span covers every day since the previous printed cell",
        "analysis/scanned_small_bank.py",
        "moved, probe = 0.0, previous_day + timedelta(days=1)",
        "moved, probe = 0.0, day",
        "only the printed day itself counts, and rows on the days between two cells are ignored",
    ),
    (
        "G4", "a day the grid prints twice with two balances is not an oracle",
        "analysis/scanned_small_bank.py",
        "        if len(values) > 1:",
        "        if len(values) > 2:",
        "a day printed twice with two balances is believed; three printings are needed to doubt it",
    ),
    (
        "G5", "the grid's last cell against the printed ending balance",
        "analysis/scanned_small_bank.py",
        "        if abs(last - stmt.ending_balance) > 0.01:",
        "        if False and abs(last - stmt.ending_balance) > 0.01:",
        "the grid's own last word and the summary's may disagree in silence",
    ),
    (
        "G6", "the southside registration declares the grid-amount check",
        "analysis/parser_registry_entries.py",
        '"integrity_checks": (scanned_small_bank.daily_grid_amount_contradictions,)',
        '"integrity_checks": ()',
        "the check exists and no document ever runs it",
    ),
    # --- SCAN-DAY-GLYPH (1407286) ----------------------------------------
    (
        "D1", "a non-decimal glyph is enumerated, not deleted",
        "analysis/date_tokens.py",
        '            for suffix in ("", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")',
        '            for suffix in ("",)',
        "a stray glyph can only be ink — the delete-and-take rule this card replaced",
    ),
    (
        "D2", "the day cell's width bound",
        "analysis/date_tokens.py",
        "MAX_DAY_CELL_GLYPHS = 3",
        "MAX_DAY_CELL_GLYPHS = 5",
        "a five-glyph capture that ran into the next column is enumerated as a day cell",
    ),
    (
        "D3", "one reading is accepted only where ONE is possible",
        "analysis/date_tokens.py",
        "    return next(iter(days)) if len(days) == 1 else None",
        "    return next(iter(days)) if days else None",
        "a cell the document leaves ambiguous is dated by preference",
    ),
    (
        "D4", "`isdecimal`, not `isdigit`, inside the enumeration",
        "analysis/date_tokens.py",
        "        if glyph.isdecimal():",
        "        if glyph.isdigit():",
        "a superscript is a digit, and `int()` raises out of the parser",
    ),
    (
        "D5", "a day cell holds one or two glyphs",
        "analysis/date_tokens.py",
        "        if not 1 <= len(reading) <= 2:",
        "        if not 1 <= len(reading) <= 3:",
        "a three-digit reading is offered as a day of the month",
    ),
    # --- citizens printed section totals (d66f743) ------------------------
    (
        "C1", "a section the page contradicts is named",
        "analysis/citizens.py",
        "        if abs(read - printed) <= 0.01:",
        "        if abs(read - printed) <= 1_000_000.0:",
        "no section total ever disagrees with the rows read from it",
    ),
    (
        "C2", "the direction of the disagreement",
        "analysis/citizens.py",
        '        direction = "more" if read > printed else "less"',
        '        direction = "less"',
        "an over-read is reported as an under-read",
    ),
    (
        "C3", "each printed section is held SEPARATELY",
        "analysis/citizens.py",
        "    notes: list[str] = []\n    for label, printed, rows in sections:",
        "    sections = sections[:1]\n    notes: list[str] = []\n    for label, printed, rows in sections:",
        "only the first printed section is held against its total",
    ),
    (
        "C4", "the citizens registration declares the section-total check",
        "analysis/parser_registry_entries.py",
        '"integrity_checks": (citizens.printed_section_total_contradictions,)',
        '"integrity_checks": ()',
        "the check exists and no document ever runs it",
    ),
    # --- EQ Bank closing edge + accrual (e4dcf9c) -------------------------
    (
        "E1", "the closing edge: a trailing row must be a CREDIT",
        "analysis/eq_bank_scanned.py",
        '            if posting.direction != "credit" or posting.amount <= 0:',
        "            if posting.amount <= 0:",
        "a DEBIT dated after the printed period end is admitted as the accrual",
    ),
    (
        "E2", "the closing edge: a trailing row must be POSITIVE",
        "analysis/eq_bank_scanned.py",
        '            if posting.direction != "credit" or posting.amount <= 0:',
        '            if posting.direction != "credit":',
        "a zero or negative credit dated after the period end is admitted",
    ),
    (
        "E3", "the closing edge: the trailing rows are the LAST rows",
        "analysis/eq_bank_scanned.py",
        "        if out_of_period != list(range(len(dates) - len(out_of_period), len(dates))):",
        "        if False:",
        "an out-of-period row may sit anywhere in the printed grid",
    ),
    (
        "E4", "the accrual is corroborated by the printed interest term",
        "analysis/eq_bank_scanned.py",
        "    elif term != accrued:",
        "    elif False:",
        "trailing rows that do not sum to the printed interest term say nothing",
    ),
    (
        "E5", "a page with no legible interest term is itself the finding",
        "analysis/eq_bank_scanned.py",
        "    term = _cents(printed.group(1)) if printed is not None else None\n    if term is None:",
        "    term = _cents(printed.group(1)) if printed is not None else None\n    if False:",
        "rows admitted past the period end with nothing on the page to corroborate them say nothing",
    ),
    (
        "E6", "the in-period ledger against the printed closing balance",
        "analysis/eq_bank_scanned.py",
        "    if int(round(stmt.ending_balance * 100)) - accrued != in_period_closing:",
        "    if False:",
        "the third printing of the accrual is not consulted",
    ),
    (
        "E7", "the EQ Bank registration declares the closing-accrual check",
        "analysis/parser_registry_entries.py",
        '"integrity_checks": (eq_bank_scanned.closing_accrual_contradictions,)',
        '"integrity_checks": ()',
        "the check exists and no document ever runs it",
    ),
    (
        "E8", "EQ Bank reads each term through the shared helper",
        "analysis/eq_bank_scanned.py",
        "from .tables import unique_match\n",
        "from .tables import unique_match as _shared_unique_match  # noqa: F401\n\n\n"
        "def unique_match(text, pattern):\n    return pattern.search(text)\n",
        "a header or summary term printed twice with two values is read as its FIRST printing",
    ),
    # --- the clone guard's own recognition (e4dcf9c) ----------------------
    (
        "K1", "the removed paraphrase may not come back",
        "analysis/scanned_small_bank.py",
        "def _tf_iso(mmdd: str, *, start: date, end: date) -> str | None:",
        _REMOVED_PARAPHRASE + "def _tf_iso(mmdd: str, *, start: date, end: date) -> str | None:",
        "`_tf_one`, the near-clone of `tables.unique_match`, is back in the tree",
    ),
    (
        "K2", "the detector recognises the paraphrase it was written for",
        "tests/test_no_parser_helper_clones.py",
        '_ENUMERATES = {"findall", "finditer"}',
        '_ENUMERATES = {"finditer"}',
        "the guard no longer sees a `findall` paraphrase — and would pass vacuously",
    ),
    (
        "K3", "the helper-length bound",
        "tests/test_no_parser_helper_clones.py",
        "NEAR_CLONE_MAX_STATEMENTS = 6",
        "NEAR_CLONE_MAX_STATEMENTS = 2",
        "a paraphrase of three statements or more is not a helper and is not looked at",
    ),
    # --- the monotonicity residual, pinned (e4dcf9c) ----------------------
    (
        "P1", "the pinned monotonicity residual",
        "analysis/eq_bank_scanned.py",
        "    if any(later < earlier for earlier, later in zip(dates, dates[1:])):",
        "    if any(later != earlier for earlier, later in zip(dates, dates[1:])):",
        "the printed order gate refuses every statement whose rows are not all on one day — "
        "the pin must fail, because it asserts what TODAY's reader publishes",
    ),
)

_FAILED_RE = re.compile(r"^(FAILED|ERROR) (\S+?::\S+)", re.MULTILINE)
_COUNT_RE = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def tree_is_clean() -> tuple[bool, str]:
    status = git("status", "--porcelain")
    dirty = [
        line for line in status.stdout.splitlines()
        # Untracked files outside the tree the harness restores are not a risk
        # to it; a MODIFIED tracked file is.
        if not line.startswith("??")
    ]
    return not dirty, "\n".join(dirty)


def read_source(path: Path) -> tuple[str, bool]:
    """The file as `
`-terminated text, plus whether it is CRLF on disk.

    This checkout is `core.autocrlf=true`, so every tracked file is CRLF on
    disk while every anchor in the table above is written with `
`. Reading
    without normalising would match nothing across a line break; writing
    without restoring would rewrite every line of the file and turn one mutant
    into a whole-file diff.
    """
    raw = path.read_bytes()
    crlf = b"
" in raw
    text = raw.decode("utf-8")
    return (text.replace("
", "
") if crlf else text), crlf


def write_retrying(path: Path, text: str, crlf: bool, attempts: int = 5) -> None:
    """OneDrive holds file handles; a transient PermissionError is not a score."""
    payload = (text.replace("
", "
") if crlf else text).encode("utf-8")
    for attempt in range(attempts):
        try:
            path.write_bytes(payload)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def run_tests() -> tuple[int, list[str], dict[str, int], str]:
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", *TEST_FILES, "-rf"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    output = finished.stdout + finished.stderr
    killers = sorted({match.group(2) for match in _FAILED_RE.finditer(output)})
    counts = {name: int(number) for number, name in _COUNT_RE.findall(output)}
    return finished.returncode, killers, counts, output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--only", nargs="+", default=None)
    args = parser.parse_args(argv)

    clean, dirty = tree_is_clean()
    if not clean:
        print("REFUSING: the tree is dirty and this harness restores with "
              f"`git checkout --`:\n{dirty}", file=sys.stderr)
        return 2

    baseline_code, baseline_killers, baseline_counts, _ = run_tests()
    if baseline_code != 0:
        print(f"REFUSING: the unmutated tree does not pass ({baseline_code}): "
              f"{baseline_killers}", file=sys.stderr)
        return 2

    selected = [m for m in MUTANTS if args.only is None or m[0] in args.only]
    results: list[dict[str, object]] = []
    started = time.perf_counter()
    for identifier, gate, relative, old, new, says in selected:
        path = REPO / relative
        source, crlf = read_source(path)
        occurrences = source.count(old)
        if occurrences != 1:
            results.append({
                "id": identifier, "gate": gate, "file": relative, "says": says,
                "verdict": "UNAPPLIED",
                "detail": f"the anchor appears {occurrences} times, not once",
            })
            print(f"{identifier}: UNAPPLIED ({occurrences} matches)")
            continue
        write_retrying(path, source.replace(old, new), crlf)
        try:
            code, killers, counts, _ = run_tests()
        finally:
            restore = git("checkout", "--", relative)
            if restore.returncode != 0:
                print(f"{identifier}: RESTORE FAILED: {restore.stderr}", file=sys.stderr)
                return 3
        results.append({
            "id": identifier, "gate": gate, "file": relative, "says": says,
            "verdict": "KILLED" if code != 0 else "SURVIVED",
            "exit": code, "counts": counts, "killers": killers,
        })
        print(f"{identifier}: {'KILLED' if code else 'SURVIVED'} by {killers or '-'}")

    clean, dirty = tree_is_clean()
    report = {
        "mutants": len(results),
        "killed": sum(1 for r in results if r["verdict"] == "KILLED"),
        "survived": sum(1 for r in results if r["verdict"] == "SURVIVED"),
        "unapplied": sum(1 for r in results if r["verdict"] == "UNAPPLIED"),
        "baseline": {"exit": baseline_code, "counts": baseline_counts},
        "tree_clean_after": clean,
        "seconds": round(time.perf_counter() - started, 1),
        "results": results,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"},
                     sort_keys=True, separators=(",", ":")))
    return 0 if clean and report["unapplied"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
