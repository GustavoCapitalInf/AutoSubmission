"""W3 §COREISS2's mutation harness, committed because its table is a headline.

    python -m tools.coreiss2_mutation --data-dir <checkout>/webapp_data

Each mutant is ONE documented textual substitution applied to a CLEAN tree.
The two unit-test files are then run WITHOUT `-x`, so every test that dies is
named rather than only the first, and `tools.coreiss2_probe replay` is run as
a SECOND, independent killer over the archive's own text — a mutant that no
unit test catches but that changes what the archive publishes is caught there,
and vice versa.

Three properties make the table trustworthy rather than decorative, and all
three are enforced rather than intended:

* the harness REFUSES to start on a dirty tree, because `git checkout --` as a
  restore is only correct on one (batch 7: a harness silently reverted an
  uncommitted edit);
* every substitution must match its anchor EXACTLY ONCE or the mutant is
  reported as an anchor error instead of being silently skipped — which is how
  a mutant comes to be "applied" without being applied (§FISERV3 F13.1);
* the restore is asserted after every mutant, so a harness that leaves the
  tree mutated stops rather than scoring the rest of the table against it.

The mutants are written as (anchor, replacement) source pairs, so they go
STALE loudly: an edit that moves an anchor turns the mutant into an anchor
error at the next run rather than into a silent pass.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIGNED = "analysis/core_processor_signed_counts.py"
ACTIVITY = "analysis/core_processor_activity_summary.py"
SIGNED_TEST = "tests/test_core_processor_signed_counts.py"
ACTIVITY_TEST = "tests/test_core_processor_activity_summary.py"

MUTANTS: tuple[tuple[str, str, str, str, str], ...] = (
    ("M01", SIGNED, "the counts marker no longer requires the printed SIGN",
     r'_MARK_CREDITS_RE = re.compile(r"(?<![/A-Z])CREDITS\s*\([0-9]+\)\s*\+\$")',
     r'_MARK_CREDITS_RE = re.compile(r"(?<![/A-Z])CREDITS\s*\([0-9]+\)")'),
    ("M02", SIGNED, "the CREDIT label loses its bare-label lookbehind",
     r'_MARK_CREDITS_RE = re.compile(r"(?<![/A-Z])CREDITS\s*\([0-9]+\)\s*\+\$")',
     r'_MARK_CREDITS_RE = re.compile(r"CREDITS\s*\([0-9]+\)\s*\+\$")'),
    ("M02b", SIGNED, "the DEBIT label loses its bare-label lookbehind",
     r'_MARK_DEBITS_RE = re.compile(r"(?<![/A-Z])DEBITS\s*\([0-9]+\)\s*" + MINUS_CLASS + r"\$")',
     r'_MARK_DEBITS_RE = re.compile(r"DEBITS\s*\([0-9]+\)\s*" + MINUS_CLASS + r"\$")'),
    ("M03", SIGNED, "the balance marker no longer requires the balances to be DATED",
     r'_MARK_BEGIN_RE = re.compile(r"BEGINNING BALANCE\s+[0-9]{1,2}/[0-9]{1,2}/[0-9]{2}\b")',
     r'_MARK_BEGIN_RE = re.compile(r"BEGINNING BALANCE")'),
    ("M04", SIGNED, "the printed length need not equal the dated span",
     "    if last_day < start or (last_day - start).days + 1 != days:",
     "    if last_day < start:"),
    ("M05", SIGNED, "the period END is read from `Statement Date:` instead",
     "    days = int(stats.group(3))\n    if last_day < start",
     '    stated = re.search(r"Statement Date:\\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2})", markdown)\n'
     "    if stated is not None:\n"
     "        last_day = date.fromisoformat(iso_from_month_day_year(stated.group(1)))\n"
     "    days = int(stats.group(3))\n    if last_day < start"),
    ("M06", SIGNED, "the summary identity is not checked",
     "    if abs(walked - closing) > _TOLERANCE:\n        return None",
     "    if False:\n        return None"),
    ("M07", SIGNED, "the `Checks in Number Order` section is dropped from the debits",
     "    debit_rows = debit_rows + check_rows",
     "    debit_rows = list(debit_rows)"),
    ("M08", SIGNED, "the debit amount is the FIRST money token and the minus is optional",
     '_DEBIT_ROW_RE = re.compile(\n    _DAY + r" ((?:\\$" + _FIG + r"(?!" + MINUS_CLASS + r")|[^$])+?) "\n'
     '    r"\\$(" + _FIG + MINUS_CLASS + r")(?![0-9,.])"\n)',
     '_DEBIT_ROW_RE = re.compile(\n    _DAY + r" ([^$]+?) "\n'
     '    r"\\$(" + _FIG + r")" + MINUS_CLASS + r"?(?![0-9,.])"\n)'),
    ("M09", SIGNED, "the credit description may cross a `$`",
     '    _DAY + r" ([^$]+?) \\$(" + _FIG + r")(?![0-9,.]|" + MINUS_CLASS + r")"',
     '    _DAY + r" (.+?) \\$(" + _FIG + r")(?![0-9,.]|" + MINUS_CLASS + r")"'),
    ("M10", SIGNED, "the ledger is never terminated by the statistics summary",
     r'_LEDGER_END_RE = re.compile(r"^Summary\s+Average Ledger Bal\b")',
     r'_LEDGER_END_RE = re.compile(r"^(?!x)x")'),
    ("M11", SIGNED, "the printed daily grid is not walked against the ledger",
     "    if printed is None or not _grid_agrees(printed, transactions, opening, closing):",
     "    if printed is None:"),
    ("M12", SIGNED, "a row on a day the grid never prints is allowed",
     "    return not moved and abs(running - closing) <= _TOLERANCE",
     "    return abs(running - closing) <= _TOLERANCE"),
    ("M13", SIGNED, "the grid need not be printed in date order",
     "    if [day for day, _ in printed] != sorted(day for day, _ in printed):\n        return False",
     "    if False:\n        return False"),
    ("M14", SIGNED, "a page break carries the section blindly instead of suspending it",
     "        if _PAGE_RE.match(line) or _FOOTER_RE.match(line):\n"
     "            if current is not None and current != \"daily\":\n"
     "                suspended = current\n"
     "            current = None\n"
     "            continue",
     "        if _PAGE_RE.match(line) or _FOOTER_RE.match(line):\n"
     "            continue"),
    ("M15", SIGNED, "a cheque row's amount cell need not be money",
     '    _DAY + r" ([0-9]{1,7}\\*?) \\$(" + _FIG + r")(?![0-9,.])"',
     '    _DAY + r" ([0-9]{1,7}\\*?) (\\S+)(?![0-9,.])"'),
    ("M16", SIGNED, "the FIRST labelled mask is published instead of requiring exactly one",
     "    return (product or holder or None), (masks.pop() if len(masks) == 1 else None)",
     "    return (product or holder or None), (sorted(masks)[0] if masks else None)"),
    ("M17", SIGNED, "the printed CREDIT count is not checked",
     "    if len(credit_rows) != credit_count or len(debit_rows) != debit_count:",
     "    if len(debit_rows) != debit_count:"),
    ("M18", SIGNED, "neither printed TOTAL is checked",
     "    if abs(sum(t.amount for t in credit_rows) - abs(credits)) > _TOLERANCE:\n"
     "        return None\n"
     "    if abs(sum(-t.amount for t in debit_rows) - abs(debits)) > _TOLERANCE:\n"
     "        return None",
     "    if False:\n        return None"),
    ("N01", ACTIVITY, "the cycle-length anti-collision clause is loosened to `DAYS IN`",
     r'_MARK_CYCLE_RE = re.compile(r"DAYS IN CYCLE\s+[0-9]+")',
     r'_MARK_CYCLE_RE = re.compile(r"DAYS IN")'),
    ("N02", ACTIVITY, "the closing-balance label is dropped from the marker",
     "        and bool(_MARK_CLOSING_RE.search(t)),",
     "        and True,"),
    ("N03", ACTIVITY, "the box heading may appear anywhere rather than on its own line",
     r'_MARK_BOX_RE = re.compile(r"^ACTIVITY SUMMARY\s*$", re.MULTILINE)',
     r'_MARK_BOX_RE = re.compile(r"ACTIVITY SUMMARY")'),
    ("N04", ACTIVITY, "`Days in Cycle` is not required to equal the printed span",
     "    if end < start or (end - start).days + 1 != days:",
     "    if end < start:"),
    ("N05", ACTIVITY, "more than one Activity Summary box is allowed",
     "    if printed is None or len(box) != 1:",
     "    if printed is None or not box:"),
    ("N06", ACTIVITY, "the restated trio is not required to agree with the box",
     "        if second is None or abs(abs(second) - abs(printed)) > _TOLERANCE:\n            return None",
     "        if False:\n            return None"),
    ("N07", ACTIVITY, "the summary identity is not checked",
     "    if abs(walked - closing) > _TOLERANCE:\n        return None",
     "    if False:\n        return None"),
    ("N08", ACTIVITY, "the running-balance chain is not walked",
     "        if abs(round(running + amount, 2) - balance) > _TOLERANCE:\n            return None",
     "        if False:\n            return None"),
    ("N09", ACTIVITY, "a zero-amount row is filed instead of refusing",
     "        if amount == 0:\n            return None",
     "        if False:\n            return None"),
    ("N10", ACTIVITY, "a non-posting line inside the region refuses instead of being skipped",
     "        if match is None:\n            continue",
     "        if match is None:\n            return None"),
    ("N11", ACTIVITY, "a page break does not close the ledger region",
     "        if _PAGE_RE.match(line):\n            inside = False\n            continue",
     "        if _PAGE_RE.match(line):\n            continue"),
    ("N12", ACTIVITY, "the ledger is not cut at the cheque recap banner",
     r'_LEDGER_END_RE = re.compile(r"^Checks in Number Order\s*$")',
     r'_LEDGER_END_RE = re.compile(r"^(?!x)x")'),
    ("N13", ACTIVITY, "the money token loses its LEADING minus",
     '_CASH = MINUS_CLASS + r"?\\$(?:[0-9][0-9,]*)?\\.[0-9]{2}"',
     '_CASH = r"\\$(?:[0-9][0-9,]*)?\\.[0-9]{2}"'),
    ("N14", ACTIVITY, "the row description is read non-greedily (a PROVEN NO-OP: the "
     "end-of-line anchor already forces the last two money tokens)",
     '    r"^([0-9]{1,2}/[0-9]{1,2})\\s+(.*)\\s+(" + _CASH + r")\\s+(" + _CASH + r")\\s*$"',
     '    r"^([0-9]{1,2}/[0-9]{1,2})\\s+(.*?)\\s+(" + _CASH + r")\\s+(" + _CASH + r")\\s*$"'),
    ("N15", ACTIVITY, "the last row need not land on the printed closing balance",
     "    if abs(transactions[-1].running_balance - closing) > _TOLERANCE:\n        return None",
     "    if False:\n        return None"),
    ("N16", ACTIVITY, "neither printed count is checked",
     "    if len(credit_rows) != credit_count or len(debit_rows) != debit_count:\n        return None",
     "    if False:\n        return None"),
    ("N17", ACTIVITY, "neither printed total is checked",
     "    if abs(sum(txn.amount for txn in credit_rows) - abs(credits)) > _TOLERANCE:\n"
     "        return None\n"
     "    if abs(sum(-txn.amount for txn in debit_rows) - abs(debits)) > _TOLERANCE:\n"
     "        return None",
     "    if False:\n        return None"),
)

#: N14 cannot change any reading — see its description. It is kept in the table
#: and reported as a survivor rather than deleted, so the next reader can
#: re-measure the claim instead of trusting this one.
KNOWN_NO_OPS = frozenset({"N14"})


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _dirty() -> str:
    return _run(["git", "status", "--porcelain"]).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if _dirty():
        print("REFUSING: the tree is not clean, so `git checkout --` is not a restore")
        return 2

    results = []
    for identifier, path, description, anchor, replacement in MUTANTS:
        target = ROOT / path
        source = target.read_text(encoding="utf-8")
        if source.count(anchor) != 1:
            print(f"{identifier} ANCHOR-ERROR: matched {source.count(anchor)} times, not 1")
            results.append({"id": identifier, "status": "anchor-error"})
            continue
        target.write_text(source.replace(anchor, replacement, 1), encoding="utf-8")
        try:
            tests = _run([sys.executable, "-m", "pytest", SIGNED_TEST, ACTIVITY_TEST,
                          "-q", "--no-header"])
            killers = sorted(set(re.findall(
                r"^FAILED ([^\s:]+::[^\s]+)", tests.stdout + tests.stderr, re.MULTILINE)))
            replay = _run([sys.executable, "-m", "tools.coreiss2_probe", "replay",
                           "--data-dir", str(args.data_dir)])
            counts = re.findall(r"=(\d+)/(\d+)", replay.stdout)
        finally:
            _run(["git", "checkout", "--", path])
        if _dirty():
            print(f"{identifier} ABORT: the tree did not restore")
            return 3
        moved = any(int(got) != int(want) for got, want in counts) if counts else None
        results.append({"id": identifier, "file": path, "mutant": description,
                        "killers": killers, "replay": replay.stdout.strip()})
        print(f"{identifier} killers={len(killers)} replay_moved={moved} :: {description}")
        for killer in killers:
            print(f"      {killer}")

    survived = [
        entry for entry in results
        if not entry.get("killers") and "REPLAY" in entry.get("replay", "")
        and not re.search(r"=(\d+)/(?!\1\b)", entry["replay"])
    ]
    unexpected = [entry["id"] for entry in survived if entry["id"] not in KNOWN_NO_OPS]
    print(f"\nMUTANTS {len(results)}  SURVIVED {[e['id'] for e in survived]}  "
          f"UNEXPECTED {unexpected}")
    if args.out:
        args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 1 if unexpected else 0


if __name__ == "__main__":
    raise SystemExit(main())
