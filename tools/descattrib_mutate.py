"""Mutation harness for the description-attribution rule (W3 §DESCATTRIB DA7).

Reintroduces the defect, and every weakening of the fix, one at a time, and
names the test that dies for each. Committed so the kill table in the log is
re-derivable rather than asserted:

    python tools/descattrib_mutate.py .

A test named after a gate is not a test of that gate — that is §GRAM4 G7.4's
finding on this same complex, where two gate tests were firing through the
wrong gate. So every mutation here is required to kill a NAMED test, and the
harness prints the names rather than a count.

The target files are restored in a `finally`, and the harness prints the
restore, so a run that dies mid-way is visible as one that did not.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

TABLES = "analysis/tables.py"
DAILY = "analysis/core_processor_daily.py"

TESTS = [
    "tests/test_description_attribution.py",
    "tests/test_core_processor_counted.py",
    "tests/test_core_processor_daily.py",
]

_BRANCH = (
    "        if not lines:\n"
    "            printed = label\n"
    "        else:\n"
    "            printed = cell.described if outstanding == 1 and len(lines) == 1 else label\n"
    "            outstanding = 0\n"
)

#: label -> (file, [(anchor, replacement), ...]). Applied to a pristine copy.
MUTATIONS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    # M1 — the shipped defect, restored verbatim: the whole span is the row's.
    "M1_the_shipped_span_restored": (TABLES, [
        (_BRANCH, "        printed = cell.described\n"),
    ]),
    # M2 — the OTHER candidate fix G7.7 named: attribute the flush to the row
    # BEFORE the span it landed in. It moves the same wrong name one row the
    # other way, because the flush ends with the block of the row it is in.
    "M2_attributed_to_the_row_before": (TABLES, [
        ("    published: list[str] = []\n    outstanding = 0\n    for cell in cells:\n",
         "    published: list[str] = []\n    outstanding = 0\n"
         "    for _index, cell in enumerate(cells):\n"
         "        _next = (cells[_index + 1].described.partition('\\n')[2]\n"
         "                 if _index + 1 < len(cells) else '')\n"),
        (_BRANCH,
         "        printed = (cell.described.partition('\\n')[0] + ' ' + _next\n"
         "                   if _next.strip() else cell.described.partition('\\n')[0])\n"),
    ]),
    # M3 — the indeterminate branch dropped: any single-line flush is taken as
    # the row's own, however many rows are outstanding.
    "M3_the_count_dropped": (TABLES, [
        ("printed = cell.described if outstanding == 1 and len(lines) == 1 else label",
         "printed = cell.described if len(lines) == 1 else label"),
    ]),
    # M4 — the one-line condition dropped: a span holding two flushes, or a
    # page's furniture, is taken as one block.
    "M4_the_one_line_condition_dropped": (TABLES, [
        ("printed = cell.described if outstanding == 1 and len(lines) == 1 else label",
         "printed = cell.described if outstanding == 1 else label"),
    ]),
    # M5 — a flush never clears what is outstanding, so no row is ever
    # attributed after the first: fail-closed become fail-silent.
    "M5_the_flush_never_clears": (TABLES, [
        ("            printed = cell.described if outstanding == 1 and len(lines) == 1 else label\n"
         "            outstanding = 0\n",
         "            printed = cell.described if outstanding == 1 and len(lines) == 1 else label\n"),
    ]),
    # M6 — the cap cuts at the bound again rather than at a token boundary.
    "M6_cut_through_a_token": (TABLES, [
        ("    boundary = text.rfind(\" \", 0, limit + 1)\n"
         "    return text[:boundary].rstrip() if boundary > 0 else \"\"\n",
         "    return text[:limit]\n"),
    ]),
    # M7 — half a token published where there is no boundary to cut at.
    "M7_half_a_token_rather_than_nothing": (TABLES, [
        ("    return text[:boundary].rstrip() if boundary > 0 else \"\"\n",
         "    return text[:boundary].rstrip() if boundary > 0 else text[:limit]\n"),
    ]),
    # M8 — one reader keeps a private normaliser beside the shared call: the
    # two readers of one layer can disagree about it again.
    "M8_a_private_normaliser_returns": (DAILY, [
        ("            else:\n                description = described[index] or default\n",
         "            else:\n"
         "                description = _private_described(cell.described) or default\n"),
        ("def _row_lead(gap: str) -> str:\n",
         "def _private_described(gap: str) -> str:\n"
         "    return re.sub(r\"\\\\s+\", \" \", gap).strip(\" '.-|*\")[:200].strip()\n"
         "\n"
         "\n"
         "def _row_lead(gap: str) -> str:\n"),
    ]),
}


def failures(root: pathlib.Path) -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
         *TESTS],
        cwd=root, capture_output=True, text=True,
    )
    names = []
    for line in completed.stdout.splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            names.append(line.split(" ", 1)[1].split(" - ")[0])
    return names


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1] if len(argv) > 1 else ".").resolve()
    originals = {name: (root / name).read_text(encoding="utf-8")
                 for name in (TABLES, DAILY)}
    survived = []
    try:
        clean = failures(root)
        print(f"BASELINE failures: {clean}")
        if clean:
            print("the gate set is not green; nothing a mutation kills can be trusted")
            return 2
        for label, (target, patches) in MUTATIONS.items():
            text = originals[target]
            for anchor, replacement in patches:
                if anchor not in text:
                    raise SystemExit(f"{label}: anchor not found in {target}")
                text = text.replace(anchor, replacement, 1)
            (root / target).write_text(text, encoding="utf-8")
            try:
                killed_by = failures(root)
            finally:
                (root / target).write_text(originals[target], encoding="utf-8")
            if killed_by:
                print(f"KILLED  {label}: {', '.join(killed_by[:6])}"
                      f"{' …' if len(killed_by) > 6 else ''}  ({len(killed_by)} tests)")
            else:
                survived.append(label)
                print(f"SURVIVED {label}")
    finally:
        for name, text in originals.items():
            (root / name).write_text(text, encoding="utf-8")
        print("restored:", ", ".join(originals))
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
