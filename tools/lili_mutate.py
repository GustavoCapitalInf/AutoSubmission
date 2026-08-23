"""Mutation harness for every gate `analysis/lili.py` adds (W3 §LILI).

Breaks each gate one at a time and proves a named test dies for it, so the
kill table in the log is re-derivable rather than asserted:

    python tools/lili_mutate.py .

Each mutant is applied to a pristine copy of the target, the suite is run
WITHOUT `-x` so every killer is named rather than only the first, and the
target is restored in a `finally` — the harness prints the restore, so a run
that dies mid-way is visible as one that did not. It is only correct on a
CLEAN tree: it writes the target file, and an uncommitted edit to it would be
lost.

The two suites run together on purpose. `tests/test_lili.py` owns the
reader's behaviour; the conformance and registry modules own the properties a
registration has to keep (three required markers, the cross-product, the
count), and two of the mutants below are registration-level.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

TESTS = ("tests/test_lili.py", "tests/test_parser_conformance.py",
         "tests/test_parser_registry_entries.py")

#: label -> (anchor, replacement). Applied one at a time to a pristine copy.
#: Every anchor is asserted present before the mutant runs, so a mutant that
#: silently applied to nothing cannot be scored as a kill.
MUTATIONS: dict[str, tuple[str, str]] = {
    # ---------------------------------------------------------------- detection
    # M01 — the registration rests on the summary terms alone, so any
    #       core-processor statement printing those two section names is
    #       claimed by this reader.
    "M01_issuer_marker_dropped": (
        '    required("issuer_support_address", lambda t: "support@lili.co" in t),\n',
        "",
    ),
    # M02 — the reader claims only its clean printing, which is what leaves a
    #       tampered document unnamed in the run's `no_parser_matched` bucket.
    "M02_debit_term_marker_dropped": (
        '    required("summary_debit_term", lambda t: "Withdrawals and other debits" in t),\n',
        "",
    ),

    # ---------------------------------------------------------------- §INTEGRITY
    # The gate is TWO readings over one date class. Each is broken alone,
    # and each bound of the period reading is slackened separately, because
    # a bound that is only ever checked on a calendar-month period is not
    # checked at all.
    #
    # M03 — the whole gate removed.
    "M03_integrity_gate_removed": (
        "    if _ledger_dates_are_sound(markdown, start, end) is not None:\n        return None\n",
        "",
    ),
    # M04 — the COVERAGE reading removed: a printed ledger line the row
    #       pattern cannot parse is dropped in silence again.
    "M04_coverage_reading_removed": (
        '    if {match.start() for match in leading} != {match.start() for match in rows}:\n        return "a line that begins with a date is not a posting"\n',
        "",
    ),
    # M05 — coverage weakened from POSITIONS to a count comparison.
    "M05_coverage_counts_not_positions": (
        "    if {match.start() for match in leading} != {match.start() for match in rows}:",
        "    if len(leading) < len(rows):",
    ),
    # M06 — the PERIOD reading removed, coverage left in place.
    "M06_period_reading_removed": (
        '        if not start <= posted <= end:\n            return "a printed date outside the declared period"\n',
        "",
    ),
    # M07 — the lower bound slackened to the first of the period-start month.
    #       Invisible on a calendar-month period, which is why the suite
    #       carries a period that starts mid-month.
    "M07_lower_bound_slackened_to_the_month": (
        "        if not start <= posted <= end:",
        "        if not start.replace(day=1) <= posted <= end:",
    ),
    # M08 — the upper bound slackened the same way, to the month's end.
    "M08_upper_bound_slackened_to_the_month": (
        "        if not start <= posted <= end:",
        "        if not start <= posted or (posted.year, posted.month) > (end.year, end.month):",
    ),
    # M09 — a date the calendar does not have RAISES instead of answering.
    "M09_period_reading_raises_on_a_non_date": (
        '        except ValueError:\n            return "a printed date outside the declared period"\n',
        "        except ValueError:\n            raise\n",
    ),
    # M10 — the gate runs AFTER the shape is read. Recorded as an EQUIVALENT
    #       mutant and expected to SURVIVE: every gate here answers by
    #       declining, so ORDER changes which reason the replay attributes
    #       and nothing a caller can observe. It is in the table so that
    #       "order is not observable" is a measurement, not a promise.
    "M10_gate_after_the_shape_read_EQUIVALENT": (
        "    if _ledger_dates_are_sound(markdown, start, end) is not None:\n        return None\n\n    summary = _summary(markdown)\n    if summary is None:\n        return None\n",
        "    summary = _summary(markdown)\n    if summary is None:\n        return None\n    if _ledger_dates_are_sound(markdown, start, end) is not None:\n        return None\n",
    ),
    # ---------------------------------------------------------------------- §L-1
    # M07 — the second money column is not seen: the checking column is read
    #       and the collateral account is silently dropped.
    "M11_l1_column_gate_removed": (
        "    if len(summary[0]) != 1:\n        return None\n",
        "",
    ),
    # M08 — the census's own framing of the hazard: read a column rather than
    #       refuse. Takes the LAST figure, which is the printed Total.
    "M12_l1_reads_the_total_column": (
        "    if len(summary[0]) != 1:\n        return None\n",
        "",
    ),
    # M09 — the second ledger is not seen.
    "M13_l1_ledger_gate_removed": (
        "    if len(_LEDGER_HEAD_RE.findall(markdown)) != 1:\n        return None\n",
        "",
    ),
    # M10 — the ledger gate weakened to "at least one", the shape a reader
    #       that only wanted to find the table would write.
    "M14_l1_ledger_gate_at_least_one": (
        "    if len(_LEDGER_HEAD_RE.findall(markdown)) != 1:",
        "    if len(_LEDGER_HEAD_RE.findall(markdown)) < 1:",
    ),

    # ------------------------------------------------------------- summary shape
    # M11 — a term may be printed twice and the first reading wins.
    "M11_summary_term_uniqueness_dropped": (
        "        if len(found) != 1 or found[0].start() <= position:\n            return None",
        "        if len(found) < 1:\n            return None",
    ),
    # M12 — the five terms may appear in any order.
    "M12_summary_order_dropped": (
        "        if len(found) != 1 or found[0].start() <= position:\n            return None",
        "        if len(found) != 1:\n            return None",
    ),
    # M13 — a ragged grid is accepted, so a row with three figures sits beside
    #       four with one and the column binding means nothing.
    "M13_ragged_grid_accepted": (
        "    if len({len(row) for row in columns}) != 1:\n        return None\n",
        "",
    ),
    # M14 — the term patterns use `\\s`, which spans a line break: the second
    #       printing's label-then-figure layout starts matching. This is the
    #       defect the first revision of this reader actually had.
    "M14_summary_terms_span_a_line_break": (
        '        r"^Deposits and other credits[ \\t]+(" + _MONEY_RUN + r")$",',
        '        r"^Deposits and other credits\\s+(" + _MONEY_RUN + r")$",',
    ),

    # ------------------------------------------------------------------- signs
    # M15 — the Withdrawals term may be printed as an inflow.
    "M15_withdrawals_sign_unchecked": (
        "    if withdrawals > 0 or fees > 0:\n        return None\n",
        "    if fees > 0:\n        return None\n",
    ),
    # M16 — the Fees term may be printed as an inflow.
    "M16_fees_sign_unchecked": (
        "    if withdrawals > 0 or fees > 0:\n        return None\n",
        "    if withdrawals > 0:\n        return None\n",
    ),

    # ------------------------------------------------------- the three gates
    # M17 — the printed summary need not close on itself.
    "M17_summary_sum_gate_removed": (
        "    if abs(beginning + deposits + withdrawals + fees - ending) > _CENT:\n        return None\n",
        "",
    ),
    # M18 — the chain is not walked at all.
    "M18_chain_gate_removed": (
        "    if not _chain_holds(postings, beginning, ending):\n        return None\n",
        "",
    ),
    # M19 — only the last printed balance is checked, so a break in the middle
    #       of the walk is invisible.
    "M19_chain_checks_only_the_last_balance": (
        "    balance = beginning\n"
        "    for posting in postings:\n"
        "        walked = round(balance + posting.amount, 2)\n"
        "        if posting.running_balance is None or abs(walked - posting.running_balance) > _CENT:\n"
        "            return False\n"
        "        balance = posting.running_balance\n"
        "    return abs(balance - ending) <= _CENT",
        "    balance = beginning\n"
        "    for posting in postings:\n"
        "        if posting.running_balance is None:\n"
        "            return False\n"
        "        balance = posting.running_balance\n"
        "    return abs(balance - ending) <= _CENT",
    ),
    # M20 — the walk is anchored at the first row's own printed balance
    #       instead of at the printed beginning, so the opening bound is lost.
    "M20_chain_anchored_at_the_first_row": (
        "    balance = beginning\n    for posting in postings:",
        "    balance = beginning\n"
        "    if postings and postings[0].running_balance is not None:\n"
        "        balance = round(postings[0].running_balance - postings[0].amount, 2)\n"
        "    for posting in postings:",
    ),
    # M21 — the rows need not total to the two printed debit terms.
    "M21_gross_debit_gate_removed": (
        "    if abs(debited + withdrawals + fees) > _CENT:\n        return None\n",
        "",
    ),
    # M22 — the gate compares against the Withdrawals term alone: the reading
    #       that would have made the Fees-excluded split invisible.
    "M22_gross_debits_ignore_the_fee_term": (
        "    if abs(debited + withdrawals + fees) > _CENT:",
        "    if abs(debited + withdrawals) > _CENT:",
    ),
    # M23 — a dollar of tolerance instead of a cent.
    "M23_tolerance_widened_to_a_dollar": (
        "_CENT = 0.005",
        "_CENT = 1.0",
    ),

    # -------------------------------------------------------------- the rows
    # M24 — the two money columns lose their binding: the end anchor goes and
    #       the description becomes non-greedy together, so the FIRST pair of
    #       money tokens on the line is taken and a figure inside a
    #       description becomes the amount.
    #
    #       Either half ALONE is an equivalent mutant and is recorded here as
    #       one rather than dressed up as a kill: with the end anchor in
    #       place, backtracking pins the last two tokens whether the
    #       description is greedy or not; with the description greedy,
    #       backtracking from the end of the line does the same without the
    #       anchor. It is the PAIR that binds the columns, and this mutant
    #       breaks the pair.
    "M24_row_columns_unbound": (
        'r"(?P<description>\\S.*)[ \\t]+(?P<amount>" + _MONEY + r")[ \\t]+(?P<balance>" + _MONEY + r")[ \\t]*$",',
        'r"(?P<description>\\S.*?)[ \\t]+(?P<amount>" + _MONEY + r")[ \\t]+(?P<balance>" + _MONEY + r")",',
    ),
    # M25 — a row whose date is not a calendar date is skipped rather than
    #       refusing the document.
    "M25_unreadable_posting_skipped": (
        "        if iso is None or amount is None or balance is None:\n            return None",
        "        if iso is None or amount is None or balance is None:\n            continue",
    ),
    # M26 — an empty description is published as an empty string.
    "M26_empty_description_published": (
        "        if not description:\n            return None\n",
        "",
    ),
    # M27 — no postings at all is read as an empty statement rather than as a
    #       ledger this reader could not read.
    "M27_no_postings_is_an_empty_statement": (
        "    return postings or None",
        "    return postings",
    ),

    # ----------------------------------------------------------- the header
    # M28 — two headers that disagree are blended: whichever the set yields.
    "M28_header_contradiction_accepted": (
        "    if len(readings) != 1:\n        return None",
        "    if len(readings) < 1:\n        return None",
    ),
    # M29 — a period bound the calendar does not have raises instead of
    #       declining: an exception where the document deserves an answer.
    "M29_long_date_raises_instead_of_declining": (
        "    try:\n        return date(int(year), month, int(day))\n    except ValueError:\n        return None",
        "    return date(int(year), month, int(day))",
    ),

    # --------------------------------------------------------- what is published
    # M30 — the fee term folded into the debit total, the reading the
    #       platform's own rows contradict.
    "M30_fees_folded_into_the_debit_total": (
        "        stated_total_debits=abs(withdrawals),\n        stated_service_charge=abs(fees),",
        "        stated_total_debits=abs(withdrawals) + abs(fees),\n        stated_service_charge=None,",
    ),
    # M31 — the running balance the document prints on every row is dropped.
    "M31_running_balance_not_published": (
        "                running_balance=balance,",
        "                running_balance=None,",
    ),
    # M32 — a currency claimed where the family prints none. The mutant sets
    #       the CODE rather than any statement about where the code came from:
    #       that second field may only be NAMED by its readers, the schema and
    #       the gate, and this harness is none of the three.
    "M32_currency_claimed": (
        '        stated_total_credits=deposits,',
        '        currency="CAD",\n        stated_total_credits=deposits,',
    ),
}

#: Mutants that need a second edit alongside the first.
PRELUDE: dict[str, tuple[str, str]] = {
    # M08 reads the LAST column rather than refusing a multi-column grid.
    "M12_l1_reads_the_total_column": (
        "    beginning, deposits, withdrawals, fees, ending = (row[0] for row in summary)",
        "    beginning, deposits, withdrawals, fees, ending = (row[-1] for row in summary)",
    ),
}


def run(root: pathlib.Path, target: pathlib.Path, label: str, source: str) -> bool:
    target.write_text(source, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=root, capture_output=True, text=True,
    )
    failures = [ln for ln in proc.stdout.splitlines() if ln.startswith(("FAILED", "ERROR"))]
    tally = [ln for ln in proc.stdout.splitlines() if " passed" in ln or " failed" in ln]
    verdict = "KILLED" if proc.returncode != 0 else "*** SURVIVED ***"
    print(f"=== {label}: pytest exit {proc.returncode} -> {verdict}")
    print(f"    {tally[-1] if tally else proc.stdout.splitlines()[-1:]}")
    for line in failures[:6]:
        print(f"    {line}")
    if len(failures) > 6:
        print(f"    ... and {len(failures) - 6} more")
    return proc.returncode != 0


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    target = root / "analysis" / "lili.py"
    original = target.read_text(encoding="utf-8")
    killed = 0
    survivors: list[str] = []
    try:
        for label, (anchor, replacement) in MUTATIONS.items():
            source = original
            if label in PRELUDE:
                pre_anchor, pre_replacement = PRELUDE[label]
                assert pre_anchor in source, f"{label}: prelude anchor not found"
                source = source.replace(pre_anchor, pre_replacement, 1)
            assert anchor in source, f"{label}: anchor not found"
            mutated = source.replace(anchor, replacement, 1)
            assert mutated != source, f"{label}: mutant changed nothing"
            if run(root, target, label, mutated):
                killed += 1
            else:
                survivors.append(label)
    finally:
        target.write_text(original, encoding="utf-8")
        print("\nrestored analysis/lili.py")
    print(f"{len(MUTATIONS)} mutants, {killed} KILLED, {len(survivors)} survivors")
    for label in survivors:
        print(f"  SURVIVOR {label}")
    return 0 if not survivors else 1


if __name__ == "__main__":
    sys.exit(main())
