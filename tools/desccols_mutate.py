"""Mutation harness for the printed-row rung's gates (W3 §DESCCOLS).

Removes each gate, and each weakening of the emission, one at a time, and
names the test that dies for it. Committed so the kill table in the log is
re-derivable rather than asserted:

    python tools/desccols_mutate.py .

A test named after a gate is not a test of that gate — §GRAM4 G7.4's finding,
and §DESCATTRIB's M6 repeated it on its own gate set — so every mutation here
is required to kill a NAMED test and the harness prints the names.

Run WITHOUT `-x`, so a mutation that kills several tests names all of them and
a mutation that kills none is reported as SURVIVED rather than hidden behind
the first failure.

The target file is restored in a `finally` and the restore is printed, so a run
that dies mid-way is visible as one that did not restore. It is only correct on
a CLEAN tree: batch 7 recorded a harness silently reverting an uncommitted edit.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

RUNG = "ocr/native_text.py"

TESTS = [
    "tests/test_printed_row_extraction.py",
    "tests/test_native_rung_parity.py",
    "tests/test_native_text_unreadable.py",
]

#: label -> [(anchor, replacement), ...]. Applied to a pristine copy of RUNG.
MUTATIONS: dict[str, list[tuple[str, str]]] = {
    # G9 — the amount need no longer be the row's last printed cell, so a
    # template that prints the merchant detail BELOW the amount is
    # re-serialised too, for text a reader's span still cannot reach.
    "M1_the_amount_need_not_be_printed_last": [
        ("            if money[0] != row[-1]:\n"
         "                return None                                    # G9\n", ""),
    ],
    # G3 — a row may carry several money cells, so a multi-column balance
    # ladder or cheque list is re-serialised: dates and figures with no
    # description in them, moved for nothing.
    "M2_a_row_may_carry_several_money_cells": [
        ("        if len(money) > 1:\n"
         "            return None                                        # G3\n", ""),
    ],
    # G6 — the region need not actually be welded, so a ledger the flattening
    # already prints one line per row is claimed and every affected document's
    # cache key rotates for an identical reading.
    "M3_the_region_need_not_be_welded": [
        ("        if welded:\n            regions.append(rows)\n",
         "        regions.append(rows)\n"),
    ],
    # G2 — two bands are a grid. A coincidence is now rewritten.
    "M4_two_rows_are_a_grid": [
        ("_ROW_GRID_MINIMUM = 3\n", "_ROW_GRID_MINIMUM = 2\n"),
    ],
    # G4/G5 — the money and description floors dropped, so an indented
    # paragraph with the shape of a row grid and none of its substance is
    # re-serialised.
    "M5_no_money_and_no_description_floor": [
        ("    if len(edges) < _ROW_GRID_MINIMUM or described < _ROW_GRID_MINIMUM:\n"
         "        return None                                            # G4 / G5\n",
         ""),
    ],
    # G7 — a block straddling the region boundary is skipped rather than
    # refused, so half of it is re-serialised and half is left where it was.
    "M6_a_straddling_block_is_skipped_not_refused": [
        ("            if len(inside) != len(positions):\n"
         "                return None                                    # G7\n",
         "            if len(inside) != len(positions):\n"
         "                continue\n"),
    ],
    # G8 — token conservation dropped, so a divergence between the two
    # extraction modes alters the document instead of refusing it.
    "M7_token_conservation_dropped": [
        ("    if sorted(text.split()) != sorted(flattened.split()):\n"
         "        return None                                            # G8\n", ""),
    ],
    # The reading order inside a row: cells come out in MuPDF's order rather
    # than left to right, so a row's amount can precede its own description.
    "M8_a_row_is_not_read_left_to_right": [
        ("    return [sorted(band, key=lambda p: lines[p].left) for band in bands]\n",
         "    return bands\n"),
    ],
    # Placement: the repaired rows are appended rather than left where the
    # page prints them, so the ledger moves down the page.
    "M9_the_repaired_rows_are_not_put_back_where_they_were": [
        ("    units.sort()\n", ""),
    ],
    # G1 — a band starting to the LEFT of the anchor no longer ends the
    # region, so the ledger swallows whatever the page moved on to.
    "M10_a_line_left_of_the_anchor_does_not_end_the_ledger": [
        ("            elif lead[end] < anchor:\n                break\n", ""),
    ],
}


def failures(root: pathlib.Path) -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", *TESTS],
        cwd=root, capture_output=True, text=True,
    )
    return [line.split(" ", 1)[1].split(" - ")[0]
            for line in completed.stdout.splitlines()
            if line.startswith(("FAILED ", "ERROR "))]


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1] if len(argv) > 1 else ".").resolve()
    original = (root / RUNG).read_text(encoding="utf-8")
    survived = []
    try:
        clean = failures(root)
        print(f"BASELINE failures: {clean}")
        if clean:
            print("the gate set is not green; nothing a mutation kills can be trusted")
            return 2
        for label, patches in MUTATIONS.items():
            text = original
            for anchor, replacement in patches:
                if anchor not in text:
                    raise SystemExit(f"{label}: anchor not found in {RUNG}")
                text = text.replace(anchor, replacement, 1)
            if text == original:
                raise SystemExit(f"{label}: the mutation changed nothing")
            (root / RUNG).write_text(text, encoding="utf-8")
            try:
                killed_by = failures(root)
            finally:
                (root / RUNG).write_text(original, encoding="utf-8")
            if killed_by:
                print(f"KILLED   {label}: {', '.join(killed_by[:6])}"
                      f"{' and more' if len(killed_by) > 6 else ''}"
                      f"  ({len(killed_by)} tests)")
            else:
                survived.append(label)
                print(f"SURVIVED {label}")
    finally:
        (root / RUNG).write_text(original, encoding="utf-8")
        print("restored:", RUNG)
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
