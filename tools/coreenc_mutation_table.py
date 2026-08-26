"""W3 §COREENC C12.1: the mutation table for the enclosures / average-ledger reader.

The card's proof floor asks for "a MUTATION TABLE for every gate you add or
touch, run WITHOUT `-x` so every killer is named". This is the harness that
produces it, committed so the table is re-derivable rather than asserted:

    python -m tools.coreenc_mutation_table            # every mutant
    python -m tools.coreenc_mutation_table --only M38,M39
    python -m tools.coreenc_mutation_table --table    # markdown, for the log

Each mutant below is ONE exact string replacement that must match the target
**exactly once**. A mutant whose anchor is missing, or matches twice, is
reported `NOT-APPLIED` and fails the run rather than being scored: a mutant
that did not apply as documented pins nothing, which is the batch-7 lesson
(`a "reorder" mutant that actually deleted the reading pinned nothing`).

For every mutant the harness

* refuses to start at all unless the worktree's TRACKED files are clean, so a
  restore cannot silently revert an uncommitted edit (batch 7 again);
* writes the mutant as BYTES, preserving the file's own line endings, because
  a text round-trip on a CRLF checkout is itself a modification;
* runs the branch's own test files with no `-x`, so every killer is named and
  not merely the first;
* restores the file from the bytes it read, then `git checkout --` and a byte
  comparison, and reports the restore — a run that dies mid-way is visible as
  one that did not restore.

**A survivor is disclosed, never dropped.** A mutant carrying `survivor` is one
this cell states as unpinned by design, with the reason in the same row; the
run's exit code is 0 when every mutant applied and every mutant WITHOUT a
`survivor` reason was killed, and 1 otherwise. An undisclosed survivor is
therefore a red run.

No archive content is read or printed: the harness touches source files and
pytest, and nothing else.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

TARGET = "analysis/core_processor_enclosures.py"

#: The branch's own test files — the whole set, so a mutant is scored against
#: every test that could see it rather than against its own module alone.
TESTS = (
    "tests/test_core_processor_enclosures.py",
    "tests/test_count_semantics.py",
    "tests/test_stated_counts.py",
    "tests/test_parser_registry_entries.py",
    "tests/test_parser_conformance.py",
)


class Mutant:
    """One documented change, and the gate it is aimed at."""

    def __init__(self, mid: str, gate: str, changes: str, anchor: str,
                 replacement: str, survivor: str | None = None) -> None:
        self.id = mid
        self.gate = gate
        self.changes = changes
        self.anchor = anchor
        self.replacement = replacement
        self.survivor = survivor


def _m(mid: str, gate: str, changes: str, anchor: str, replacement: str,
       survivor: str | None = None) -> Mutant:
    return Mutant(mid, gate, changes, anchor, replacement, survivor)


# ---------------------------------------------------------------------------
# Detection and registration
# ---------------------------------------------------------------------------

MUTANTS: list[Mutant] = [
    _m("M01", "the second required marker",
       "the ledger-average cell demoted from required to corroborating",
       '    required("platform_ledger_average_cell",',
       '    corroborating("platform_ledger_average_cell",'),
    _m("M02", "the pairing, not the phrase",
       "the registration keyed on `AVERAGE LEDGER` alone instead of on the "
       "credit-count row welded to it",
       '_LEDGER_STATISTIC_RE = re.compile(\n'
       '    r"(?<![0-9])(?:[0-9]{1,4}\\s+)?" + _CREDIT_WORDS + r"\\s+\\$?" + _MONEY\n'
       '    + r"[\\s|]*AVERAGE LEDGER")',
       '_LEDGER_STATISTIC_RE = re.compile(r"AVERAGE LEDGER")'),
    _m("M03", "the registration's own normalization",
       "the upper-casing dropped, so a title-case printing no longer detects",
       "    return markdown.upper()",
       "    return markdown"),

    # -----------------------------------------------------------------------
    # The printed summary strip
    # -----------------------------------------------------------------------
    _m("M04", "the strip cut at the closing balance",
       "the strip runs to the end of the line, so the year-to-date interest "
       "printed after the closing balance is read as the period's own",
       "    return line[: closing.end()] if closing else None",
       "    return line"),
    _m("M05", "a figure printed twice has no rule that says which to believe",
       "`unique_match` relaxed to first-match on the previous balance",
       "    previous = unique_match(strip, _PREVIOUS_RE)",
       "    previous = _PREVIOUS_RE.search(strip)"),
    _m("M06", "the strip is read all-or-nothing",
       "a strip with a hole in it is admitted: only the period is required",
       "    if None in (period, account, previous, days, credits_, debits,\n"
       "                service, interest, closing):\n"
       "        return None",
       "    if period is None:\n"
       "        return None"),
    _m("M07", "the strip's right-aligned sign column",
       "the sign column ignored, so an overdrawn figure publishes positive",
       "    return -amount if match.group(group + 1) else amount",
       "    return amount"),
    _m("M08", "a repeated product name is no name",
       "the repetition check removed, so the layer's four-times-over painting "
       "publishes as the account name",
       "    if any(len(words) % size == 0 and words == words[:size] * (len(words) // size)\n"
       "           for size in range(1, len(words) // 2 + 1)):\n"
       "        return None",
       "    if False:\n"
       "        return None"),
    _m("M09", "the product-name bound",
       "`_PRODUCT_NAME_LIMIT` raised a hundredfold, so a page of welded "
       "furniture can land in the product slot",
       "_PRODUCT_NAME_LIMIT = 60",
       "_PRODUCT_NAME_LIMIT = 6000"),

    # -----------------------------------------------------------------------
    # The printed period
    # -----------------------------------------------------------------------
    _m("M10", "the reversed-period guard",
       "`end < start` no longer refuses a period printed backwards",
       "    if end < start:\n        return None",
       "    if False:\n        return None",
       survivor="defence-in-depth: a reversed period refuses again one step "
                "later, because `iso_within_period` places no row inside it, "
                "so no input distinguishes the two trees"),

    # -----------------------------------------------------------------------
    # The ledger's blocks
    # -----------------------------------------------------------------------
    _m("M11", "the fee-detail block publishes no rows",
       "the `charge` role given a reading, so the itemized fees post a second "
       "time beside the ledger's own `Total Service Charge`",
       '_ROLE_READING = {\n    "credit": ("credit", False, False, "Deposit"),',
       '_ROLE_READING = {\n    "charge": ("debit", False, False, "Debit"),\n'
       '    "credit": ("credit", False, False, "Deposit"),'),
    _m("M12", "the image appendix is a boundary, never a block",
       "the appendix banner removed from the split, so the grid's run swallows "
       "the restated `Date:` / `Amount:` pairs",
       '    ("appendix", r"DATE:\\s*[0-9]{1,2}/[0-9]{1,2}(?:/[0-9]{2,4})?\\s+AMOUNT:", r""),\n',
       ""),
    _m("M13", "a SUMMARY block restates the ledger when the ledger prints a balance",
       "the running-balance test dropped, so the summary blocks are ALWAYS "
       "read and the eight restating members double their ledger",
       "        if running and restated:\n            continue",
       "        if False:\n            continue"),
    _m("M14", "the SUMMARY-block rule, the other direction",
       "the running-balance test dropped the other way, so the summary blocks "
       "are NEVER read and the four cheque-only members lose their debit side",
       "        if running and restated:\n            continue",
       "        if restated:\n            continue"),
    _m("M15", "a cheque grid's leading cell is a serial, not a description",
       "the serial branch removed, so the collapsed grid publishes the "
       "attributed span instead of the cheque's own number",
       "            if serialled:\n"
       "                serial = _SERIAL_RE.fullmatch(cell.described.strip(\" |*\"))\n"
       "                description = f\"{default} {serial.group(1)}\" if serial else default\n"
       "            else:\n"
       "                description = texts[index] or default",
       "            description = texts[index] or default"),

    # -----------------------------------------------------------------------
    # The rows
    # -----------------------------------------------------------------------
    _m("M16", "a row date is a CALENDAR RANGE, not a digit run",
       "`_ROW_DATE` widened to two digit runs, so a reference-number tail "
       "opens a cell no figure closes",
       '_ROW_DATE = r"(?:1[0-2]|0?[1-9])/(?:3[01]|[12][0-9]|0?[1-9])"',
       '_ROW_DATE = r"[0-9]{1,2}/[0-9]{1,2}"'),
    _m("M17", "the ledger figure carries its sign on EITHER side",
       "the leading-minus half of the ledger token dropped, so the issue that "
       "prints `date -amount description` loses every row",
       '_LEDGER_FIGURE = (_TOKEN_START + r"(" + MINUS_CLASS + r"?\\$?" + _MONEY\n'
       '                  + MINUS_CLASS + r"?)" + _FIGURE_END)',
       '_LEDGER_FIGURE = (_TOKEN_START + r"(\\$?" + _MONEY\n'
       '                  + MINUS_CLASS + r"?)" + _FIGURE_END)'),
    _m("M18", "the direction is the block, never the sign",
       "the direction read from the sign of the amount on every block",
       '                credit=(amount > 0) if direction is None else direction == "credit",',
       "                credit=(amount > 0),"),
    _m("M19", "the cross-reference row is a pointer, not a posting",
       "`-See above-` rows left in the run, so the cheque either posts twice "
       "or opens a cell nothing closes",
       "    if not _CROSS_REFERENCE_RE.search(run):\n        return run",
       "    if True:\n        return run"),
    _m("M20", "the description bound",
       "`_DESCRIPTION_LIMIT` raised a hundredfold, so an unbounded span "
       "publishes as one row's description",
       "_DESCRIPTION_LIMIT = 200",
       "_DESCRIPTION_LIMIT = 20000"),

    # -----------------------------------------------------------------------
    # Fail-closed: decline rather than drop
    # -----------------------------------------------------------------------
    _m("M21", "an unreadable RUN declines the document",
       "the run dropped instead, which is how a ledger comes to disagree with "
       "a printed total while still looking complete (C8's M31)",
       "        cells = dated_cells(_without_cross_references(run),\n"
       "                            date_pattern=_DATE_RE, value_pattern=_LEDGER_FIGURE_RE)\n"
       "        if cells is None:\n            return None",
       "        cells = dated_cells(_without_cross_references(run),\n"
       "                            date_pattern=_DATE_RE, value_pattern=_LEDGER_FIGURE_RE)\n"
       "        if cells is None:\n            continue"),
    _m("M22", "an unreadable AMOUNT declines the document",
       "the row dropped instead",
       "            amount = _ledger_amount(cell.value)\n"
       "            if amount is None:\n"
       "                return None",
       "            amount = _ledger_amount(cell.value)\n"
       "            if amount is None:\n"
       "                continue",
       survivor="equivalent in practice: every token `_LEDGER_FIGURE_RE` "
                "captures parses, on both sign placements and the bare-cents "
                "form, so no input reaches the branch. Kept as a fail-closed "
                "statement rather than removed"),
    _m("M23", "a row outside the printed period declines the document",
       "the row dropped instead, even where dropping it would reconcile "
       "(C8's M32)",
       "        iso = iso_within_period(posting.day, start, end)\n"
       "        if iso is None:\n"
       "            return None",
       "        iso = iso_within_period(posting.day, start, end)\n"
       "        if iso is None:\n"
       "            continue"),
    _m("M24", "an empty ledger publishes nothing",
       "`if not postings` weakened to `if postings is None`, so an empty "
       "ledger reaches the gates",
       "    if not postings:\n        return None",
       "    if postings is None:\n        return None",
       survivor="defence-in-depth: the count gates refuse the empty ledger "
                "one step later, so no input distinguishes the two trees"),

    # -----------------------------------------------------------------------
    # The printed summary gates
    # -----------------------------------------------------------------------
    _m("M25", "the summary's own identity",
       "the identity check removed",
       "    if abs(identity - summary.closing) > _TOLERANCE:\n        return False",
       "    if False:\n        return False"),
    _m("M26", "the charge standing OUTSIDE both direction totals",
       "the service charge dropped out of the identity",
       "    identity = (summary.previous + summary.credits - summary.debits\n"
       "                - summary.service_charge + summary.interest)",
       "    identity = (summary.previous + summary.credits - summary.debits\n"
       "                + summary.interest)"),
    _m("M27", "the printed CREDIT COUNT",
       "the count dropped from the credit gate, leaving the total alone",
       "        (len(credits_) == summary.credit_count\n"
       "         and abs(credited - summary.credits) <= _TOLERANCE)",
       "        (abs(credited - summary.credits) <= _TOLERANCE)"),
    _m("M28", "the printed CREDIT TOTAL",
       "the total dropped from the credit gate, leaving the count alone",
       "        (len(credits_) == summary.credit_count\n"
       "         and abs(credited - summary.credits) <= _TOLERANCE)",
       "        (len(credits_) == summary.credit_count)"),
    _m("M29", "the printed DEBIT COUNT",
       "the count dropped from the debit gate, leaving the total alone",
       "        (len(debits) == summary.debit_count\n"
       "         and abs(debited - summary.debits) <= _TOLERANCE)",
       "        (abs(debited - summary.debits) <= _TOLERANCE)"),
    _m("M30", "the printed DEBIT TOTAL",
       "the total dropped from the debit gate, leaving the count alone",
       "        (len(debits) == summary.debit_count\n"
       "         and abs(debited - summary.debits) <= _TOLERANCE)",
       "        (len(debits) == summary.debit_count)"),
    _m("M31", "the interest allowance is bounded to the printed figure",
       "the money bound removed, so ANY single extra credit row is admitted "
       "whenever the bank credited any interest at all",
       "        or (summary.interest > 0 and len(credits_) == summary.credit_count + 1\n"
       "            and abs(credited - summary.credits - summary.interest) <= _TOLERANCE)",
       "        or (summary.interest > 0 and len(credits_) == summary.credit_count + 1)"),
    _m("M32", "the interest allowance bounded to exactly ONE extra row",
       "the count bound removed from the credit allowance, so a ledger with "
       "FEWER credit rows than the bank printed is admitted",
       "        or (summary.interest > 0 and len(credits_) == summary.credit_count + 1\n"
       "            and abs(credited - summary.credits - summary.interest) <= _TOLERANCE)",
       "        or (summary.interest > 0\n"
       "            and abs(credited - summary.credits - summary.interest) <= _TOLERANCE)"),
    _m("M33", "the fee allowance admits only MORE rows, never fewer",
       "the count bound removed from the debit allowance",
       "        or (summary.service_charge > 0 and len(debits) > summary.debit_count\n"
       "            and abs(debited - summary.debits - summary.service_charge) <= _TOLERANCE)",
       "        or (summary.service_charge > 0\n"
       "            and abs(debited - summary.debits - summary.service_charge) <= _TOLERANCE)"),
    _m("M34", "the fee allowance bounded to the printed charge",
       "the money bound removed from the debit allowance, so any number of "
       "extra debit rows is admitted whenever a charge was billed",
       "        or (summary.service_charge > 0 and len(debits) > summary.debit_count\n"
       "            and abs(debited - summary.debits - summary.service_charge) <= _TOLERANCE)",
       "        or (summary.service_charge > 0 and len(debits) > summary.debit_count)"),

    # -----------------------------------------------------------------------
    # The daily-balance grid
    # -----------------------------------------------------------------------
    _m("M35", "the grid walked against the ledger",
       "the whole grid comparison removed",
       "    if printed_grid and not _matches_the_printed_grid(rows, printed_grid, summary):\n"
       "        return None",
       "    if False:\n        return None"),
    _m("M36", "every day the ledger posts on appears in the grid",
       "the missing-day check removed",
       "    if set(walked) - set(printed):\n        return False",
       "    if False:\n        return False"),
    _m("M37", "a grid day the ledger never posts on fails the document",
       "the surplus-day check removed, along with the opening-balance "
       "exception it bounds",
       "    surplus = set(printed) - set(walked)\n"
       "    if surplus and (surplus != {summary.start}\n"
       "                    or abs(printed[summary.start] - summary.previous) > _TOLERANCE):\n"
       "        return False",
       "    surplus = set(printed) - set(walked)\n"
       "    if False:\n        return False"),
    _m("M38", "a day printed twice INSIDE one grid block with two balances",
       "`_grid`'s intra-block duplicate-day check removed, so the LAST "
       "reading silently wins",
       "            if iso in printed and abs(printed[iso] - balance) > 0.005:\n"
       "                return None",
       "            if False:\n                return None"),
    _m("M39", "two grid blocks disagreeing on a shared day",
       "`parse`'s cross-block merge check removed, so the LAST block's "
       "reading silently wins",
       "            if day in printed_grid and abs(printed_grid[day] - balance) > _TOLERANCE:\n"
       "                return None",
       "            if False:\n                return None"),

    # -----------------------------------------------------------------------
    # The tolerance every gate is measured at
    # -----------------------------------------------------------------------
    _m("M40", "the cent tolerance",
       "`_TOLERANCE` widened a thousandfold, so every printed gate admits a "
       "ledger that is dollars out",
       "_TOLERANCE = 0.005",
       "_TOLERANCE = 5.0"),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."),
                        help="the worktree to mutate (default: the cwd)")
    parser.add_argument("--only", default=None,
                        help="comma-separated mutant ids to run")
    parser.add_argument("--table", action="store_true",
                        help="also print the markdown table for the log")
    return parser.parse_args(argv)


def _tracked_changes(root: pathlib.Path) -> str:
    proc = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                          cwd=root, capture_output=True, text=True)
    return proc.stdout.strip()


def _run_tests(root: pathlib.Path) -> tuple[int, list[str], str]:
    """pytest over the branch's own files, without `-x`. Killers, then tally."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", *TESTS],
        cwd=root, capture_output=True, text=True,
    )
    killers: list[str] = []
    tally = ""
    for line in proc.stdout.splitlines():
        if line.startswith(("FAILED", "ERROR")) and "::" in line:
            killers.append(line.split()[1])
        if " passed" in line or " failed" in line or " error" in line:
            tally = line.strip()
    return proc.returncode, killers, tally


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    target = root / TARGET

    dirty = _tracked_changes(root)
    if dirty:
        print("REFUSING TO RUN: the worktree has uncommitted changes to tracked\n"
              "files, and a mutation harness that restores would revert them.\n"
              f"{dirty}")
        return 2

    selected = [m for m in MUTANTS
                if args.only is None or m.id in args.only.replace(" ", "").split(",")]
    if not selected:
        print(f"no mutant matched --only {args.only!r}")
        return 2

    original = target.read_bytes()
    text = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    flat = text.replace("\r\n", "\n")

    results: list[tuple[Mutant, str, list[str]]] = []
    try:
        for mutant in selected:
            occurrences = flat.count(mutant.anchor)
            if occurrences != 1:
                print(f"=== {mutant.id}: NOT-APPLIED — the anchor matched "
                      f"{occurrences} times, not once")
                results.append((mutant, "NOT-APPLIED", []))
                continue
            mutated = flat.replace(mutant.anchor, mutant.replacement, 1)
            target.write_bytes(mutated.replace("\n", newline).encode("utf-8"))
            code, killers, tally = _run_tests(root)
            verdict = "KILLED" if code != 0 else "SURVIVED"
            print(f"=== {mutant.id} [{verdict}] pytest exit {code} - {tally}")
            for killer in killers:
                print(f"      killed by {killer}")
            results.append((mutant, verdict, killers))
            target.write_bytes(original)
    finally:
        target.write_bytes(original)
        subprocess.run(["git", "checkout", "--", TARGET], cwd=root,
                       capture_output=True, text=True)
        restored = target.read_bytes() == original
        print(f"\nrestored {TARGET}: {'byte-identical' if restored else 'DIFFERENT'}")
        left = _tracked_changes(root)
        print(f"tracked changes after the run: {left or '(none)'}")

    applied = [row for row in results if row[1] != "NOT-APPLIED"]
    killed = [row for row in applied if row[1] == "KILLED"]
    survived = [row for row in applied if row[1] == "SURVIVED"]
    disclosed = [row for row in survived if row[0].survivor]
    undisclosed = [row for row in survived if not row[0].survivor]
    unexpected = [row for row in killed if row[0].survivor]
    print(f"\n{len(selected)} mutants selected, {len(applied)} applied, "
          f"{len(killed)} KILLED, {len(survived)} survived "
          f"({len(disclosed)} disclosed, {len(undisclosed)} UNDISCLOSED)")
    if unexpected:
        print("mutants marked as survivors that were in fact killed: "
              + ", ".join(row[0].id for row in unexpected))

    if args.table:
        print("\n| id | line | what the mutant changes | the gate it targets | killed by |")
        print("|---|---|---|---|---|")
        for mutant, verdict, killers in results:
            at = (flat[: flat.index(mutant.anchor)].count("\n") + 1
                  if mutant.anchor in flat else 0)
            if verdict == "KILLED":
                shown = ", ".join(f"`{name.split('::')[-1]}`" for name in killers[:3])
                if len(killers) > 3:
                    shown += f" (+{len(killers) - 3} more)"
                cell = shown
            elif verdict == "SURVIVED":
                cell = (f"**SURVIVES** - disclosed: {mutant.survivor}"
                        if mutant.survivor else "**SURVIVES - UNDISCLOSED**")
            else:
                cell = "**NOT APPLIED**"
            print(f"| {mutant.id} | `{TARGET}:{at}` | {mutant.changes} "
                  f"| {mutant.gate} | {cell} |")

    return 0 if not undisclosed and len(applied) == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
