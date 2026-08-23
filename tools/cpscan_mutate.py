"""Mutation harness for the two row-date grammars (W3 §CPSCAN CP8).

Every weakening and every over-tightening of the leading-zero class and the
calendar bound, one at a time, with the NAMED tests that die for each:

    python tools/cpscan_mutate.py .

A test named after a gate is not a test of that gate (§GRAM4 G7.4, on this
same complex), so this harness reports test names rather than a count, and
runs the whole file rather than stopping at the first failure.

Both directions are mutated on purpose. A widening harness alone would pass a
grammar that had quietly stopped matching `10-31`; the `..._still_matches`
mutants are what say the tightening did not overshoot.

The target files are restored from memory in a `finally`, and the restore is
printed, so a run that dies mid-way is visible as one that did not.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

SECTIONED = "analysis/core_processor_sectioned.py"
DAILY = "analysis/core_processor_daily.py"

TESTS = [
    "tests/test_core_processor_sectioned.py",
    "tests/test_core_processor_daily.py",
]

#: The three declarations of the sectioned template's row date, verbatim.
_S_ZERO = '_LEADING_ZERO = r"[0oO]"'
_S_MONTH = '_ROW_MONTH = r"(?:" + _LEADING_ZERO + r"[1-9]|1[0-2]|[1-9])"'
_S_DAY = '_ROW_DAY = r"(?:" + _LEADING_ZERO + r"[1-9]|[12][0-9]|3[01]|[1-9])"'
_S_TOKEN = '_DATE_TOKEN = _TOKEN_START + r"(" + _ROW_DATE + r")" + _DATE_END'
_S_START = '_TOKEN_START = r"(?<![0-9A-Za-z.,/|])"'
_S_TABLE = '_ZERO_GLYPHS = str.maketrans({"o": "0", "O": "0"})'
_S_READ = "    return token.translate(_ZERO_GLYPHS)"

#: The daily template's, which is one string.
_D_DATE = '_ROW_DATE = r"(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"'

#: label -> (file, [(anchor, replacement), ...]). Applied to a pristine copy.
MUTATIONS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    # ---- the leading-zero class -------------------------------------------
    # M01 — the shipped behaviour restored: the zero-shaped letters go back
    # outside the class and the 154 archive rows go invisible again.
    "M01_zero_glyph_removed": (SECTIONED, [(_S_ZERO, '_LEADING_ZERO = r"[0]"')]),
    # M02 — the class widened to the ONE-shaped letters. `l2/12` then reads as
    # February and a December row is published ten months early.
    "M02_one_shaped_letters_admitted": (
        SECTIONED, [(_S_ZERO, '_LEADING_ZERO = r"[0oOlI|]"')]),
    # M03 — the glyph allowed in the TRAILING position of the month, where the
    # digit it stands for IS significant: `1o/12` would read as month 1.
    "M03_glyph_in_the_trailing_position": (SECTIONED, [
        (_S_MONTH,
         '_ROW_MONTH = r"(?:" + _LEADING_ZERO + r"[1-9]|1" + _LEADING_ZERO'
         ' + r"|1[0-2]|[1-9])"'),
    ]),
    # ---- the calendar bound, widened --------------------------------------
    "M04_sectioned_month_bound_removed": (
        SECTIONED, [(_S_MONTH, '_ROW_MONTH = r"[0-9]{1,2}"')]),
    "M05_sectioned_day_bound_removed": (
        SECTIONED, [(_S_DAY, '_ROW_DAY = r"[0-9]{1,2}"')]),
    "M06_daily_month_bound_removed": (
        DAILY, [(_D_DATE, '_ROW_DATE = r"[0-9]{2}-(?:0[1-9]|[12][0-9]|3[01])"')]),
    "M07_daily_day_bound_removed": (
        DAILY, [(_D_DATE, '_ROW_DATE = r"(?:0[1-9]|1[0-2])-[0-9]{2}"')]),
    "M08_daily_month_admits_a_thirteenth": (
        DAILY, [(_D_DATE, '_ROW_DATE = r"(?:0[1-9]|1[0-3])-(?:0[1-9]|[12][0-9]|3[01])"')]),
    "M09_daily_day_admits_a_thirty_second": (
        DAILY, [(_D_DATE, '_ROW_DATE = r"(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[012])"')]),
    # ---- the calendar bound, over-tightened -------------------------------
    # The direction a widening harness cannot see: a bound that has quietly
    # stopped matching a date the platform really prints.
    "M10_daily_month_loses_the_teens": (
        DAILY, [(_D_DATE, '_ROW_DATE = r"(?:0[1-9])-(?:0[1-9]|[12][0-9]|3[01])"')]),
    "M11_daily_day_loses_the_thirties": (
        DAILY, [(_D_DATE, '_ROW_DATE = r"(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9])"')]),
    "M12_sectioned_month_loses_the_teens": (
        SECTIONED, [(_S_MONTH, '_ROW_MONTH = r"(?:" + _LEADING_ZERO + r"[1-9]|[1-9])"')]),
    "M13_sectioned_day_loses_the_thirties": (
        SECTIONED, [(_S_DAY, '_ROW_DAY = r"(?:" + _LEADING_ZERO + r"[1-9]|[12][0-9]|[1-9])"')]),
    # ---- the reading -------------------------------------------------------
    # M14 — the glyph matched but never resolved to its digit. `iso_within_
    # period` splits on `/` and requires digits, so the row is lost one layer
    # further down and the class buys nothing.
    "M14_normalization_removed": (SECTIONED, [(_S_READ, "    return token")]),
    # M15 — half the class resolved. The upper-case glyph is admitted by the
    # pattern and then refused by the reading, which is the silent form of the
    # same defect.
    "M15_normalization_forgets_the_capital": (
        SECTIONED, [(_S_TABLE, '_ZERO_GLYPHS = str.maketrans({"o": "0"})')]),
    # ---- the boundary the class sits behind --------------------------------
    # M16 — `_TOKEN_START` dropped from the date token. With the zero glyph in
    # the grammar this is the mutant that proves the boundary still does the
    # job the class does NOT do: a one-shaped letter's date matching one
    # character in.
    "M16_token_start_dropped": (
        SECTIONED, [(_S_TOKEN, '_DATE_TOKEN = r"(" + _ROW_DATE + r")" + _DATE_END')]),
    # M17 — the vertical bar back out of the boundary class, which is where
    # this branch found it. `|2/11` then reads as February.
    "M17_boundary_loses_the_vertical_bar": (
        SECTIONED, [(_S_START, '_TOKEN_START = r"(?<![0-9A-Za-z.,/])"')]),
    # M18 — the asterisk added to it. The platform's own serial-gap marker
    # abuts the date it precedes, so this one costs real cheque rows.
    "M18_boundary_gains_the_asterisk": (
        SECTIONED, [(_S_START, '_TOKEN_START = r"(?<![0-9A-Za-z.,/|*])"')]),
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
                 for name in (SECTIONED, DAILY)}
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
                print(f"KILLED   {label}: {', '.join(killed_by[:5])}"
                      f"{' and more' if len(killed_by) > 5 else ''}"
                      f"  ({len(killed_by)} tests)")
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
