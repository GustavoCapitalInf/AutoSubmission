"""Mutation harness for the TD grid readers (W3 §WITHHELDTD).

Weakens each gate this card adds or touches, one at a time, and names the test
that dies for it. Committed so the kill table in the log is re-derivable rather
than asserted:

    python tools/withheldtd_mutate.py .

Three properties the batch-7 review asked every harness for, and this one has:

* a mutant must be applied AS DOCUMENTED — the harness fails loudly when an
  anchor is missing, and fails just as loudly when the "mutated" text is
  identical to the original, which is how a reorder that deleted nothing got
  counted as a kill;
* two mutants that produce the SAME tree pin the same thing once — every
  mutated tree is hashed and duplicates are reported by name;
* the suite runs WITHOUT `-x`, so every killer is named rather than the first.

Mutants that are semantically INERT are listed here too, under `INERT`, with
what they prove. `M-INERT-1` is the "codes already reach the target" shortcut
in `_resolve_directions_from_balances`: removing it changes no output, because
the ranking that then runs scores the code reading at `(0 contradictions, 0
rows moved)`, which is strictly minimal. That is not a hole — it is the
byte-identity argument, and it is worth being able to re-run.

M13 was briefly deleted rather than tested: the ACCOUNT SUMMARY discriminator
changes no heading mark on any of the 40 archive documents, and the first
attempt at a killing fixture failed, so the gate was removed as untestable. The
adversarial review produced the fixture — a summary line whose last heading
falls inside the next section's legend window — and the gate and its mutant are
both back. "No fixture can distinguish them" is a claim about the fixtures
tried, and it was wrong.

The target files are restored in a `finally`, and the harness prints the
restore, so a run that dies mid-way is visible as one that did not.
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

CAN = "analysis/td_can.py"
FRENCH = "analysis/td_canada_french.py"
US = "analysis/td_us.py"

TESTS = [
    "tests/test_td_can_native_variants.py",
    "tests/test_td_french_layouts.py",
    "tests/test_td_us_variants.py",
    "tests/test_row_grouping.py",
    "tests/test_r1_hardcodes.py",
]

#: label -> (file, [(anchor, replacement), ...]). Applied to a pristine copy.
MUTATIONS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    # ---------------------------------------------------------------- td_can
    # M1 — the printed change may be an odd number of cents. It cannot: every
    # split of integer-cent amounts moves the balance by an even `delta + S`,
    # so an odd one means a row is missing or misread.
    "M1_target_accepts_odd_parity": (CAN, [
        ("    doubled = delta + total\n    if doubled % 2:\n        return None\n",
         "    doubled = delta + total\n"),
        ("    target = doubled // 2\n", "    target = doubled // 2\n    doubled = doubled\n"),
    ]),
    # M2 — a target outside the group's own total is a reading.
    "M2_target_accepts_an_unreachable_range": (CAN, [
        ("    if target < 0 or target > total:\n        return None\n", ""),
    ]),
    # M3 — the group-size bound comes off.
    "M3_target_has_no_group_bound": (CAN, [
        ("    if not amounts or len(amounts) > _MAX_GROUP_ROWS:\n        return None\n",
         "    if not amounts:\n        return None\n"),
    ]),
    # M4 — a `$0.00` row becomes a dimension of the search again. It is one
    # the arithmetic cannot answer, and — on any future edit to the prune that
    # keeps it reachable — a division by zero inside a parser.
    "M4_zero_amount_rows_enter_the_search": (CAN, [
        ("    values = sorted((value for value in multiplicity if value), reverse=True)\n",
         "    values = sorted(multiplicity, reverse=True)\n"),
    ]),
    # M5 — the ranking stops reading the bank's printed codes and keeps only
    # "change as little as possible", so a printed withdrawal can be handed
    # the deposit label.
    "M5_ranking_ignores_the_printed_codes": (CAN, [
        ("        key = (contradictions, moved)\n", "        key = (0, moved)\n"),
    ]),
    # M6 — the ranking keeps only the codes and drops minimal change, so an
    # uncoded group is settled by the enumeration's order.
    "M6_ranking_ignores_minimal_change": (CAN, [
        ("        key = (contradictions, moved)\n", "        key = (contradictions, 0)\n"),
    ]),
    # M7 — the code reading goes back to two-valued: "TD says withdrawal" and
    # "TD says nothing" become the same answer again.
    "M7_direction_code_is_two_valued": (CAN, [
        ("    tokens = text.split()\n"
         "    if tokens:\n"
         "        if tokens[-1] in _NATIVE_DEBIT_CODES:\n"
         "            return False\n"
         "        if tokens[-1] in _NATIVE_CREDIT_CODES:\n"
         "            return True\n"
         "    return None\n",
         "    tokens = text.split()\n"
         "    if tokens:\n"
         "        if tokens[-1] in _NATIVE_CREDIT_CODES:\n"
         "            return True\n"
         "    return False\n"),
    ]),
    # M8 — the machine channel's withdrawal half goes unread again.
    "M8_atm_withdrawal_code_unread": (CAN, [
        ('    if text.startswith("TD ATM W/D"):\n        return False\n', ""),
    ]),
    # M9 — the deposit channel's withdrawal half goes unread again.
    "M9_deposit_channel_withdrawal_code_unread": (CAN, [
        ("    if _GC_CASH_WITHDRAWAL_RE.match(text):\n        return False\n", ""),
    ]),
    # M18 — a group tied past every oracle is resolved by the walk's own order
    # instead of refused (review MAJOR-2).
    "M18_an_unbreakable_tie_is_guessed": (CAN, [
        ("    if _tied_beyond_the_printed_counts(tied):\n        return None\n", ""),
    ]),
    # M19 — the certificate the refusal rests on: two readings that rank alike
    # but count DIFFERENTLY are separable by the printed counts, and refusing
    # them too would withhold documents the platform can check.
    "M19_every_tie_refuses_even_a_separable_one": (CAN, [
        ("    counts = [sum(resolved) for resolved in tied]\n"
         "    return len(set(counts)) < len(counts)\n",
         "    return True\n"),
    ]),
    # ------------------------------------------------------------- td_french
    # M10 — the French issue scores its rows with the ENGLISH code table
    # again, which is what the shared tie-break did before this card.
    "M10_french_tie_break_uses_the_english_codes": (FRENCH, [
        ("        credit_like=_french_credit_like,\n", ""),
    ]),
    # ----------------------------------------------------------------- td_us
    # M11 — a section ends at the next heading of ANY name, so the bank's own
    # `(continued)` reprint truncates it.
    "M11_a_continued_reprint_ends_the_section": (US, [
        ("        if name != heading:                     # the next section starts here\n"
         "            return _closed(markdown[opened:start])\n",
         "        return _closed(markdown[opened:start])\n"),
    ]),
    # M12 — the subtotal search leaves the slice, which is the shipped defect:
    # a section with no readable subtotal takes the next section's.
    "M12_the_subtotal_search_leaves_the_slice": (US, [
        ("        if name != heading:                     # the next section starts here\n"
         "            return _closed(markdown[opened:start])\n",
         "        if name != heading:                     # the next section starts here\n"
         "            return _closed(markdown[opened:])\n"),
    ]),
    # M13 — the ACCOUNT SUMMARY line is admitted as a section heading. It is
    # excluded by the legend window on every archive document, and NOT on the
    # shape where the summary's last line runs into the first detail legend.
    "M13_summary_line_opens_a_section": (US, [
        ('                   + _MONEY_ON_THE_SAME_LINE + _LEGEND_WITHIN)',
         '                   + _LEGEND_WITHIN)'),
    ]),
    # M14 — the legend stops being required, so the page footer's `Bank
    # Deposits FDIC insured...` opens a Deposits section.
    "M14_no_legend_required": (US, [
        ('_LEGEND_WITHIN = r"(?=.{0,40}?(?:POSTING|No\\. ?Checks|DATE SERIAL NO))"',
         '_LEGEND_WITHIN = r""'),
    ]),
    # M15 — a heading may sit inside a sentence, so the cheque legend's own
    # footnote opens an Electronic Payments section.
    "M15_a_heading_may_sit_mid_sentence": (US, [
        ('_NOT_MID_SENTENCE = r"(?-i:(?<![a-z])(?<![a-z] ))"', '_NOT_MID_SENTENCE = r""'),
    ]),
    # M16 — the legend must follow the heading immediately, which is the
    # shipped behaviour: OCR noise between the two discards the section.
    "M16_the_legend_must_be_immediate": (US, [
        ("(?=.{0,40}?(?:POSTING", "(?=.{0,1}?(?:POSTING"),
    ]),
    # M20 — the subtotal line stops being read case-insensitively on a family
    # that arrives through Tesseract (review MINOR-3).
    "M20_subtotal_is_case_sensitive": (US, [
        (r'r"Subtotal:\s*(?P<total>[\d,]+\.\d{2})", re.IGNORECASE',
         r'r"Subtotal:\s*(?P<total>[\d,]+\.\d{2})"'),
    ]),
    # M17 — the case-sensitivity scope comes off the sentence guard, so
    # `DAILY ACCOUNT ACTIVITY Electronic Deposits` reads as prose.
    "M17_sentence_guard_folds_case": (US, [
        ('_NOT_MID_SENTENCE = r"(?-i:(?<![a-z])(?<![a-z] ))"',
         '_NOT_MID_SENTENCE = r"(?<![a-z])(?<![a-z] )"'),
    ]),
}

#: Mutants that change no behaviour, kept because being able to re-run them is
#: the evidence for what they prove.
INERT: dict[str, tuple[str, list[tuple[str, str]]]] = {
    # The byte-identity argument: the shortcut only avoids enumerating, and
    # the ranking reaches the same reading when it does enumerate.
    "M-INERT-1_no_shortcut_for_codes_that_already_agree": (CAN, [
        ("        if sum(row.amount for row in group if credit_like(row.description)) == target:\n"
         "            continue                       # the codes already say what the page says\n",
         ""),
    ]),
}


def failures(root: pathlib.Path) -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", *TESTS],
        cwd=root, capture_output=True, text=True,
    )
    names = []
    for line in completed.stdout.splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            names.append(line.split(" ", 1)[1].split(" - ")[0])
    return names


def apply(root: pathlib.Path, originals: dict[str, str], label: str,
          target: str, patches: list[tuple[str, str]]) -> str:
    text = originals[target]
    for anchor, replacement in patches:
        if anchor not in text:
            raise SystemExit(f"{label}: anchor not found in {target}")
        text = text.replace(anchor, replacement, 1)
    if text == originals[target]:
        raise SystemExit(f"{label}: the mutation changed nothing in {target}")
    (root / target).write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1] if len(argv) > 1 else ".").resolve()
    originals = {name: (root / name).read_text(encoding="utf-8")
                 for name in (CAN, FRENCH, US)}
    survived: list[str] = []
    trees: dict[str, str] = {}
    try:
        clean = failures(root)
        print(f"BASELINE failures: {clean}")
        if clean:
            print("the gate set is not green; nothing a mutation kills can be trusted")
            return 2
        for label, (target, patches) in MUTATIONS.items():
            digest = apply(root, originals, label, target, patches)
            try:
                killed_by = failures(root)
            finally:
                (root / target).write_text(originals[target], encoding="utf-8")
            if digest in trees:
                print(f"DUPLICATE {label}: the same tree as {trees[digest]}")
            trees.setdefault(digest, label)
            if killed_by:
                print(f"KILLED   {label}: {', '.join(killed_by[:5])}"
                      f"{' and more' if len(killed_by) > 5 else ''}"
                      f"  ({len(killed_by)} tests)")
            else:
                survived.append(label)
                print(f"SURVIVED {label}")
        for label, (target, patches) in INERT.items():
            apply(root, originals, label, target, patches)
            try:
                moved = failures(root)
            finally:
                (root / target).write_text(originals[target], encoding="utf-8")
            print(f"INERT    {label}: {'CHANGED ' + str(moved) if moved else 'no test moves'}")
    finally:
        for name, text in originals.items():
            (root / name).write_text(text, encoding="utf-8")
        print("restored:", ", ".join(originals))
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
