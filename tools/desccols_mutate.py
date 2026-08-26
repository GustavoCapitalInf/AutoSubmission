"""Mutation harness for the printed-row rung's gates (W3 §DESCCOLS).

Removes each gate, and each weakening of the emission, one at a time, and
names the test that dies for it. Committed so the kill table in the log is
re-derivable rather than asserted:

    python tools/desccols_mutate.py .

A test named after a gate is not a test of that gate — §GRAM4 G7.4's finding,
and §DESCATTRIB's M6 repeated it on its own gate set — so every mutation here
is required to kill a NAMED test and the harness prints the names. The first
run of this harness found four survivors and every one of them was a fixture
declined by a DIFFERENT gate than the one it was named after; three fixtures
were rebuilt and one gate was deleted as redundant.

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

_AMOUNT_LAST = (
    "            if money[0] != row[-1]:\n"
    "                return None                                    # G8\n"
)
_STRADDLE = (
    "            if len(inside) != len(positions):\n"
    "                return None                                    # G6\n"
)
_STRADDLE_SKIPPED = (
    "            if len(inside) != len(positions):\n"
    "                continue\n"
)
_CONSERVATION = (
    "    if sorted(text.split()) != sorted(flattened.split()):\n"
    "        return None                                            # G7\n"
)
_FLOORS = (
    "    if len(edges) < _ROW_GRID_MINIMUM or described < _ROW_GRID_MINIMUM:\n"
    "        return None                                            # G3 / G4\n"
)
_BOX_GUARD = (
    "            box = _line_box(line)\n"
    "            if box is None:\n"
    "                return None\n"
)
_BOX_UNGUARDED = "            box = line[\"bbox\"]\n"
_UNCONVERTED = (
    "    except Exception:  # noqa: BLE001 — a refusal is an answer, an exception is not\n"
    "        # `_page_text` converts the exception classes MuPDF raises TODAY; this\n"
    "        # rung reads `get_text(\"dict\")` on every native-text document in the\n"
    "        # archive, so a future binding that raises a class outside that family\n"
    "        # would crash the OCR stage for the document instead of falling\n"
    "        # through to the generic rung. Refusing is always available and always\n"
    "        # correct here: the caller's next rung reproduces today's answer.\n"
    "        return None\n"
)

#: label -> [(anchor, replacement), ...]. Applied to a pristine copy of RUNG.
MUTATIONS: dict[str, list[tuple[str, str]]] = {
    # G8 — the amount need no longer be the row's last printed cell, so a
    # template printing the merchant detail BELOW the amount is re-serialised
    # for text a reader's span still cannot reach; and a multi-column balance
    # ladder, whose first money is never its last cell, loses the only gate
    # that excluded it.
    "M1_the_amount_need_not_be_printed_last": [(_AMOUNT_LAST, "")],
    # G5 — the region need not actually be welded, so a ledger the flattening
    # already prints one line per row is claimed and every affected document's
    # cache key rotates for an identical reading.
    "M2_the_region_need_not_be_welded": [
        ("        if welded:\n            regions.append(rows)\n",
         "        regions.append(rows)\n"),
    ],
    # G2 — two bands are a grid. A coincidence is now rewritten.
    "M3_two_rows_are_a_grid": [
        ("_ROW_GRID_MINIMUM = 3\n", "_ROW_GRID_MINIMUM = 2\n"),
    ],
    # G3/G4 — the money and description floors dropped, so an indented
    # paragraph with the shape of a row grid and none of its substance is
    # re-serialised.
    "M4_no_money_and_no_description_floor": [(_FLOORS, "")],
    # G6 alone — a block straddling the region boundary is skipped rather than
    # refused. EXPECTED TO SURVIVE, and kept for that reason: G6 is redundant
    # with G7, because a half-serialised block either duplicates or drops
    # tokens and conservation then refuses the page. Recording it as a
    # measured redundancy is the honest alternative to deleting a gate that
    # still makes the refusal fast and legible.
    "M5_a_straddling_block_is_skipped_not_refused_EXPECTED_TO_SURVIVE": [
        (_STRADDLE, _STRADDLE_SKIPPED),
    ],
    # G6 AND G7 — the straddle refusal and the backstop that makes it
    # redundant. With both gone the straddling block is half re-serialised and
    # half left where it was, and the page is published corrupted.
    "M6_the_straddle_refusal_and_its_backstop_both_removed": [
        (_STRADDLE, _STRADDLE_SKIPPED), (_CONSERVATION, ""),
    ],
    # G7 — token conservation dropped, so a divergence between the two
    # extraction modes alters the document instead of refusing it.
    "M7_token_conservation_dropped": [(_CONSERVATION, "")],
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
    # The line-box guard removed, i.e. `line["bbox"]` read unguarded — the
    # shape the review's exception probe found escaping the rung as a
    # `KeyError`, a `ValueError` and a `TypeError` on three of six malformed
    # dicts. A crash there takes the OCR stage down for the document instead of
    # falling through to the generic rung.
    "M11_a_malformed_line_box_is_read_rather_than_refused": [
        (_BOX_GUARD, _BOX_UNGUARDED),
    ],
    # The catch-all around the page loop removed, so an exception class
    # `_page_text` does not convert escapes the rung. `_page_text` converts
    # what MuPDF raises TODAY; this rung reads `get_text("dict")` on every
    # native-text document in the archive.
    "M12_an_unconverted_exception_escapes_the_rung": [(_UNCONVERTED, "")],
}

#: The one mutant this harness expects to survive, and why: see its comment
#: above. Named here so its SURVIVED line is a measurement rather than a hole,
#: and so any OTHER survivor — or this one being killed — still fails the run.
EXPECTED_SURVIVORS = {
    "M5_a_straddling_block_is_skipped_not_refused_EXPECTED_TO_SURVIVE",
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
    survived: list[str] = []
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
    unexpected = sorted(set(survived) - EXPECTED_SURVIVORS)
    resurrected = sorted(EXPECTED_SURVIVORS - set(survived))
    if unexpected:
        print("SURVIVED and should not have:", ", ".join(unexpected))
    if resurrected:
        print("EXPECTED TO SURVIVE but was killed:", ", ".join(resurrected))
    return 1 if unexpected or resurrected else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
