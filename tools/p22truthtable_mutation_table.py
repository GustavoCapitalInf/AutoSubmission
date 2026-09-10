"""tools/p22truthtable_mutation_table.py — the P22-TRUTHTABLE mutation table
(M1-M17), applied as real textual edits and run for real.

    python tools/p22truthtable_mutation_table.py [--only M3 M11] [--out <private>.md]

A test named after a gate is not a test OF that gate. Every mutant below is
the edit the card words, applied to the working tree, with the suite that
should kill it run WITHOUT `-x` so a mutant that kills nothing is visible as
"0 killers" rather than hidden behind the first unrelated failure.

Host discipline this harness owes (BATCH9-RULES, "Mutation harnesses on a
shared host"):

* it REFUSES to start on a dirty tree — a harness that restores with
  `git checkout --` cannot tell its own mutant from a real edit;
* every restore is in a `finally` that ignores its own exit code, and
  `git status --porcelain` is asserted CLEAN after each mutant, so a git
  failure mid-run (index.lock contention was seen once on this host) is a
  loud stop rather than a mutant left in the tree;
* it never runs two mutants at once and it is never run beside another
  harness.

M2 is deliberately not a tree edit. Its subject is a drift GUARD whose reader
is a pure function over source TEXT, so the mutant is planted in a scratch
copy of the runner's source inside the test itself and the working tree is
never touched at all — which is a stronger proof of the same property, and the
row records that rather than pretending an edit happened.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TAXONOMY = "telemetry/unresolved_taxonomy.py"
COMPARE = "discovery/compare.py"
RUNNER = "discovery/runner.py"
REPORT = "discovery/report.py"
CLI = "discovery/cli.py"

T_TAXONOMY = "tests/test_unresolved_taxonomy.py"
T_REFUSED = "tests/test_refused_outcome.py"
T_DENOM = "tests/test_two_denominators.py"
T_RESEARCH = "tests/test_research_mode.py"
T_TRIPWIRES = "tests/test_escalation_tripwires.py"


@dataclass
class Mutant:
    ident: str
    what: str
    path: str | None
    old: str
    new: str
    suites: list[str]
    killers: list[str]
    #: set when the mutant is proven by a test that plants it in a scratch
    #: copy rather than by editing the tree.
    in_process: bool = False
    observed: list[str] = field(default_factory=list)


MUTANTS: list[Mutant] = [
    Mutant(
        "M1", "the primary reason is the LOWEST-ranked non-empty layer",
        TAXONOMY,
        'primary_layer = next((layer for layer in LAYER_PRECEDENCE if codes[layer]), "")',
        'primary_layer = next((layer for layer in reversed(LAYER_PRECEDENCE) if codes[layer]), "")',
        [T_TAXONOMY],
        ["test_the_primary_reason_is_the_most_upstream_non_empty_layer"],
    ),
    Mutant(
        "M2", "a runner reason the vocabulary does not know is silently mapped",
        None, "", "", [T_TAXONOMY],
        ["test_m2_a_reason_injected_into_a_scratch_copy_of_the_runner_is_reported"],
        in_process=True,
    ),
    Mutant(
        "M3", "`validated -> refused` treated as unranked",
        COMPARE,
        '    if before == "validated":\n        return "regressed"\n',
        "",
        [T_REFUSED],
        ["test_every_exit_from_validated_is_a_regression",
         "test_validated_to_refused_fails_the_build_with_exit_2"],
    ),
    Mutant(
        "M4", "the transition matrix omits a class",
        COMPARE,
        "    matrix = {source: {target: 0 for target in ALL_CLASSES} for source in ALL_CLASSES}",
        '    _shrunk = tuple(c for c in ALL_CLASSES if c != "unknown")\n'
        "    matrix = {source: {target: 0 for target in _shrunk} for source in ALL_CLASSES}",
        [T_REFUSED],
        ["test_the_transition_matrix_names_every_class_pair_with_a_count"],
    ),
    Mutant(
        "M5", "differing raw denominators accepted instead of refused",
        COMPARE,
        "    if len(baseline) != len(candidate):\n"
        "        raise RawDenominatorMismatch(len(baseline), len(candidate))\n",
        "",
        [T_REFUSED],
        ["test_differing_raw_denominators_are_refused_by_name"],
    ),
    Mutant(
        "M6", "the classifier's verdict passed into `analyze_document`",
        RUNNER,
        "                markdown, parse_mode=\"deterministic\", on_dispatch=collector,\n"
        "                sheets=sheets,\n"
        "            ) if geometry is None else analyze_document(",
        "                markdown, parse_mode=\"deterministic\", on_dispatch=collector,\n"
        "                sheets=sheets, document_geometry=(self._doc_facts or {}).get(\"verdict\"),\n"
        "            ) if geometry is None else analyze_document(",
        [T_DENOM],
        ["test_the_classifier_is_never_passed_to_the_analysis_and_changes_no_payload"],
    ),
    Mutant(
        "M7", "two kinds recorded for one row (the disjointness claim)",
        RUNNER,
        '            ("document_class", KINDS), ("class_modality", MODALITIES),',
        '            ("class_modality", MODALITIES),',
        [T_DENOM],
        ["test_a_row_cannot_carry_two_kinds"],
    ),
    Mutant(
        "M8", "the diagnostic-label table summed",
        REPORT,
        "        lines.append(f\"  density surfaced                       {labels['density_surfaced']}\")",
        "        lines.append(f\"  density surfaced                       {labels['density_surfaced']}\")\n"
        "        lines.append(f\"  total                                  {labels['R'] + labels['U']}\")",
        [T_DENOM],
        ["test_diagnostic_labels_overlap_and_are_never_summed_into_the_primary_table"],
    ),
    Mutant(
        "M9", "a cost key in the summary",
        REPORT,
        '        "diagnostic_labels": diagnostic_labels,',
        '        "diagnostic_labels": diagnostic_labels,\n        "estimated_cost_usd": 0.0,',
        [T_DENOM],
        ["test_no_cost_price_rate_usd_or_billing_key_anywhere"],
    ),
    Mutant(
        "M10", "`enabled` computed per document at a router call site",
        RUNNER,
        '                attempted=("local_tesseract",), stop=False, enabled=self.enabled_extractors,\n'
        "            ))",
        '                attempted=("local_tesseract",), stop=False,\n'
        '                enabled=frozenset({"paddle"}) if profile.page_count else self.enabled_extractors,\n'
        "            ))",
        [T_TRIPWIRES],
        ["test_every_enabled_argument_is_a_mode_fact_never_a_per_document_expression"],
    ),
    Mutant(
        "M11", "the research trigger admitted in --scanned-paddle",
        RUNNER,
        "            upgrade_triggers = RESEARCH_TRIGGERS if self.research else (",
        "            upgrade_triggers = RESEARCH_TRIGGERS if (\n"
        "                self.research or self.mode == MODE_SCANNED_PADDLE) else (",
        [T_RESEARCH],
        ["test_no_other_mode_can_supply_the_research_trigger"],
    ),
    Mutant(
        "M12", "the research mode starts without an opt-in literal",
        CLI,
        "        if missing_literals:",
        "        if False and missing_literals:",
        [T_RESEARCH],
        ["test_research_mode_refuses_without_both_literals",
         "test_research_mode_refuses_a_wrong_literal_value"],
    ),
    Mutant(
        "M13", "a production --data-dir accepted",
        RUNNER,
        "    if _PRODUCTION_DATA_DIR_NAMES.fullmatch(resolved.name):",
        "    if False and _PRODUCTION_DATA_DIR_NAMES.fullmatch(resolved.name):",
        [T_RESEARCH],
        ["test_a_production_data_dir_is_refused"],
    ),
    Mutant(
        "M14", "a holdout sha read in research mode",
        RUNNER,
        "            if sha[:16] in self.holdout_sha16:",
        "            if False and sha[:16] in self.holdout_sha16:",
        [T_RESEARCH],
        ["test_the_runner_refuses_a_holdout_sha_before_any_read"],
    ),
    Mutant(
        "M15", 'geometry passed while `reconstruction_mode == "off"`',
        RUNNER,
        '        if getattr(_load_analysis_settings(), "reconstruction_mode", "off") == "off":\n'
        "            return None, None\n",
        "",
        [T_DENOM],
        ["test_the_geometry_seam_passes_nothing_while_the_reconstruction_mode_is_off"],
    ),
    Mutant(
        "M16", "`research_partition` missing from the row",
        REPORT,
        '    "bytes_up", "bytes_down", "inference_ms", "vram_mb", "peak_rss_mb",\n'
        '    "research_partition",',
        '    "bytes_up", "bytes_down", "inference_ms", "vram_mb", "peak_rss_mb",',
        [T_DENOM],
        ["test_the_new_columns_are_appended_at_the_end_of_row_fields_in_the_card_order"],
    ),
    Mutant(
        "M17", "the CCL denominator replacing the raw one in the headline",
        REPORT,
        '        f"raw coverage              {raw[\'validated\']} / {raw[\'denominator\']}"',
        '        f"raw coverage              {proposed.get(\'validated_in_proposed_ccl\', 0)} / '
        "{proposed.get('proposed_ccl', 0)}\"",
        [T_DENOM],
        ["test_raw_coverage_is_validated_over_distinct_shas_and_is_printed_first"],
    ),
]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _porcelain() -> str:
    return _git("status", "--porcelain").stdout.strip()


def _restore(relative: str) -> None:
    """Restore ONE file, retrying: a OneDrive lock on this host is transient
    and must never leave a mutant behind."""
    import time

    for attempt in range(6):
        if _git("checkout", "--", relative).returncode == 0:
            return
        time.sleep(2 * (attempt + 1))
    raise SystemExit(f"FATAL: could not restore {relative}; the tree may hold a mutant")


def _run(suites: list[str]) -> tuple[int, list[str]]:
    """`(exit code, failing node ids)` — WITHOUT `-x`."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *suites, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    failures = re.findall(r"^(?:FAILED|ERROR) (\S+)", completed.stdout, re.MULTILINE)
    return completed.returncode, failures


def apply_mutant(mutant: Mutant) -> None:
    path = ROOT / mutant.path
    source = path.read_text(encoding="utf-8")
    occurrences = source.count(mutant.old)
    if occurrences != 1:
        raise SystemExit(
            f"{mutant.ident}: the mutation target appears {occurrences} times in "
            f"{mutant.path}; the harness refuses to guess which one"
        )
    path.write_text(source.replace(mutant.old, mutant.new, 1), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", default=None, help="mutant ids to run")
    parser.add_argument("--out", type=Path, default=None, help="write the table here too")
    args = parser.parse_args(argv)

    dirty = _porcelain()
    if dirty:
        raise SystemExit(
            "refusing to start on a dirty tree: a harness that restores with "
            f"`git checkout --` cannot tell its own mutant from a real edit.\n{dirty}"
        )

    selected = [m for m in MUTANTS if args.only is None or m.ident in args.only]
    rows: list[str] = []
    unkilled: list[str] = []
    for mutant in selected:
        if mutant.in_process:
            code, failures = _run(mutant.suites)
            named = [k for k in mutant.killers
                     if any(k in failure for failure in failures)]
            # the in-process mutant's own test must PASS (it plants and asserts)
            status = "KILLED (in-process, tree untouched)" if code == 0 and not named else "NOT KILLED"
            rows.append(f"| {mutant.ident} | {mutant.what} | (scratch copy, no tree edit) | "
                        f"{mutant.killers[0]} | {status} |")
            if status == "NOT KILLED":
                unkilled.append(mutant.ident)
            print(f"{mutant.ident}: {status}", flush=True)
            continue
        try:
            apply_mutant(mutant)
            code, failures = _run(mutant.suites)
        finally:
            _restore(mutant.path)
        clean = _porcelain()
        if clean:
            raise SystemExit(
                f"FATAL after {mutant.ident}: the tree is not clean after the restore.\n{clean}"
            )
        mutant.observed = failures
        named = sorted({k for k in mutant.killers
                        if any(k in failure for failure in failures)})
        status = "KILLED" if named else "NOT KILLED"
        if not named:
            unkilled.append(mutant.ident)
        rows.append(
            f"| {mutant.ident} | {mutant.what} | `{mutant.path}` | "
            f"{', '.join(named) or '(none)'} | {status} ({len(failures)} failing) |"
        )
        print(f"{mutant.ident}: {status} — killers {named or '(none)'} "
              f"({len(failures)} failing tests, exit {code})", flush=True)

    table = "\n".join([
        "# P22-TRUTHTABLE mutation table (M1-M17)", "",
        "| # | mutant | file | killer | result |", "|---|---|---|---|---|",
        *rows, "",
        f"unkilled: {', '.join(unkilled) if unkilled else 'none'}",
        f"tree clean after every mutant: {'yes' if not _porcelain() else 'NO'}",
        "",
    ])
    print("\n" + table)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(table, encoding="utf-8")
    return 0 if not unkilled else 2


if __name__ == "__main__":
    raise SystemExit(main())
