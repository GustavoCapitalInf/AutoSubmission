"""tools/p23wave_mutation_table.py — the P23-WAVE mutation table (M1-M12),
applied as real textual edits and run for real.

    python tools/p23wave_mutation_table.py [--only M3 M7] [--out <private>.md]

A test named after a gate is not a test OF that gate. Every mutant below is
the edit the card words, applied to the working tree, with the suite that
should kill it run WITHOUT `-x` so a mutant that kills nothing is visible as
"0 killers" rather than hidden behind the first unrelated failure.

Host discipline this harness owes (BATCH9-RULES, "Mutation harnesses on a
shared host"), unchanged from cell T's:

* it REFUSES to start on a dirty tree — a harness that restores with
  `git checkout --` cannot tell its own mutant from a real edit;
* every restore is in a `finally` that ignores its own exit code, and
  `git status --porcelain` is asserted CLEAN after each mutant, so a git
  failure mid-run (index.lock contention was seen once on this host) is a
  loud stop rather than a mutant left in the tree;
* it never runs two mutants at once and it is never run beside another
  harness;
* `--out` APPENDS (the P22-FENCE re-review's Q1 residue): a second invocation
  of a subset must not erase the table the first one wrote.

Two mutants deliberately edit a file this card does not OWN
(`webapp/artifact_cache.py` for M4, `discovery/runner.py` for M2 and M6): a
mutant is a temporary edit that is restored and never committed, and the
property each of those proves — that the telemetry cannot reach the artifact,
that the partition cannot fall out of the key, that the cache cannot be
bypassed — lives in the file the mutant has to touch to be honest.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WAVE = "tools/paddle_wave.py"
RUNNER = "discovery/runner.py"
CACHE = "webapp/artifact_cache.py"

T_WAVE = "tests/test_paddle_wave.py"
T_RESEARCH = "tests/test_research_mode.py"
T_RUNG = "tests/test_paddle_rung.py"


@dataclass
class Mutant:
    ident: str
    what: str
    path: str
    old: str
    new: str
    suites: list[str]
    killers: list[str]
    observed: list[str] = field(default_factory=list)


MUTANTS: list[Mutant] = [
    Mutant(
        "M1", "a document that produced no evidence is SKIPPED instead of recorded as refused",
        WAVE,
        "        else:\n"
        "            state.record(sha, DocumentOutcome(outcome=OUTCOME_REFUSED, reason=_refusal_reason(row),\n"
        "                                              pages=pages, chunk=chunk_index, at=_now()))\n"
        "        processed += 1",
        "        else:\n"
        "            pass\n"
        "        processed += 1",
        [T_WAVE],
        ["test_d4_every_document_is_attempted_or_refused_when_the_worker_fails"],
    ),
    Mutant(
        "M2", "the research partition dropped from the runner's cached_ocr call",
        RUNNER,
        "                    research_partition=self.research_partition,\n"
        "                )\n"
        "                document, cached = result.value, result.cached\n"
        "                self._last_paddle_finding = result.finding",
        '                    research_partition="",\n'
        "                )\n"
        "                document, cached = result.value, result.cached\n"
        "                self._last_paddle_finding = result.finding",
        [T_RESEARCH],
        ["test_research_reads_are_keyed_under_the_partition_in_their_own_cache",
         "test_cli_end_to_end_writes_a_research_run_that_run_of_record_refuses"],
    ),
    Mutant(
        "M3", "the preflight accepts one literal (only the remote opt-in is checked)",
        WAVE,
        "            (PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL),\n"
        "            (PADDLE_CUSTOMER_DATA_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL),\n"
        "        )",
        "            (PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL),\n"
        "        )",
        [T_WAVE],
        ["test_m3_each_literal_alone_refuses_and_names_the_other"],
    ),
    Mutant(
        "M4", "the technical telemetry persisted into the OCR artifact",
        CACHE,
        '                    "page_extractor": list(getattr(document, "page_extractor", None) or []),',
        '                    "page_extractor": list(getattr(document, "page_extractor", None) or []),\n'
        '                    "extraction_telemetry": getattr(document, "extraction_telemetry", None),',
        [T_WAVE, T_RESEARCH],
        ["test_m4_the_telemetry_never_enters_the_artifact_or_a_cache_key"],
    ),
    Mutant(
        "M5", "raster retention accepts an empty (production) partition",
        WAVE,
        '    if not partition:\n'
        '        raise WaveRefused("retain_rasters_for refuses an empty research partition")',
        "    if not partition:\n        partition = partition",
        [T_WAVE],
        ["test_m5_the_production_path_writes_no_raster_file"],
    ),
    Mutant(
        "M6", "the Paddle read bypasses the cache, so a population sha is read twice",
        RUNNER,
        "        self._last_paddle_finding = None\n"
        '        self._last_paddle_refusal_reason = ""\n'
        "        try:\n"
        "            if self.cache is None:",
        "        self._last_paddle_finding = None\n"
        '        self._last_paddle_refusal_reason = ""\n'
        "        try:\n"
        "            if True:",
        [T_WAVE, T_RESEARCH],
        ["test_the_synthetic_wave_reads_every_page_once_resumes_and_then_hits_the_cache",
         "test_research_reads_are_keyed_under_the_partition_in_their_own_cache"],
    ),
    Mutant(
        "M7", "the unresolved corpus may start while the control sample is incomplete",
        WAVE,
        "        outstanding = state.unattempted(earlier_population)",
        "        outstanding = []",
        [T_WAVE],
        ["test_m7_u755_refuses_to_start_while_the_control_sample_has_an_unattempted_document",
         "test_the_slice_waits_for_both_earlier_populations",
         "test_a_predecessor_run_under_a_different_partition_does_not_satisfy_the_order"],
    ),
    Mutant(
        "M8", "the attestation passes on the worker's declaration without inspecting",
        WAVE,
        "        return (\n"
        "            self.retention_declared\n"
        "            and self.inspected\n"
        "            and not self.worker_process_alive\n"
        "            and not self.pidfile_present\n"
        "            and self.request_artefacts == 0\n"
        "            and self.page_byte_files == 0\n"
        "            and self.unexpected_files == 0\n"
        "        )",
        "        return self.retention_declared",
        [T_WAVE],
        ["test_m8_a_fake_ssh_runner_that_lists_a_leftover_fails_the_attestation",
         "test_m8_an_inspection_that_could_not_run_fails_closed",
         "test_a_worker_that_does_not_declare_retention_fails_even_on_a_clean_instance"],
    ),
    Mutant(
        "M9", "a cost key in the report",
        WAVE,
        '            "documents_measured": len(document_ms),',
        '            "documents_measured": len(document_ms),\n'
        '            "usd_estimate": 0,',
        [T_WAVE],
        ["test_the_report_states_the_count_identity_and_carries_no_cost_key",
         "test_m9_no_cost_rate_price_or_billing_token_anywhere_in_the_tool"],
    ),
    Mutant(
        "M10", "the wave runner imports the Paddle rung",
        WAVE,
        "ROOT = Path(__file__).resolve().parents[1]",
        "from ocr.paddle_rung import read_document  # noqa: F401\n\n"
        "ROOT = Path(__file__).resolve().parents[1]",
        [T_WAVE],
        ["test_m10_the_wave_runner_never_imports_the_rung_or_calls_read_document"],
    ),
    Mutant(
        "M11", "the wave accepts a --data-dir inside a cold cache",
        WAVE,
        "    try:\n"
        "        refuse_production_data_dir(data_dir)\n"
        "    except ValueError as exc:\n"
        "        raise WaveRefused(str(exc)) from exc",
        "    return",
        [T_WAVE],
        ["test_m11_a_production_or_cold_cache_data_dir_is_refused_through_the_wave"],
    ),
    Mutant(
        "M12", "the state resumes PAST a sha whose row was refused",
        WAVE,
        "        done = {\n"
        "            sha for sha, outcome in self.documents.items() if outcome.outcome == OUTCOME_EVIDENCE\n"
        "        }",
        "        done = set(self.documents)",
        [T_WAVE],
        ["test_m12_a_refused_sha_stays_pending_so_a_resume_never_reads_past_it",
         "test_a_refused_document_counts_as_attempted_for_the_order_rule"],
    ),
    # M13 and M14 are the CTRL run's two findings about the attestation itself,
    # mutated back in: the gate this cell touched after the live evidence
    # arrived gets a mutant of its own, like every other gate here.
    Mutant(
        "M13", "the exit grace believes a process that is still alive (breaks on the first look)",
        WAVE,
        "        if values[\"PROC\"] <= 0 or probes >= budget:\n"
        "            break",
        "        break",
        [T_WAVE],
        ["test_m8_a_fake_ssh_runner_that_lists_a_leftover_fails_the_attestation",
         "test_a_worker_still_exiting_is_given_a_bounded_grace_and_then_believed"],
    ),
    Mutant(
        "M14", "the temp-image count drops its session scope and counts the whole /tmp again",
        WAVE,
        "    \"\\\\( -name '*.png' -o -name '*.pdf' \\\\) -newermt '@{since}' 2>/dev/null | wc -l)\"",
        "    \"\\\\( -name '*.png' -o -name '*.pdf' \\\\) 2>/dev/null | wc -l)\"",
        [T_WAVE],
        ["test_the_temp_image_count_is_scoped_to_this_session"],
    ),
]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def _porcelain() -> str:
    return _git("status", "--porcelain").stdout.strip()


def _restore(relative: str) -> None:
    """Restore ONE file, retrying: a OneDrive lock on this host is transient
    and must never leave a mutant behind."""
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
    parser.add_argument("--out", type=Path, default=None, help="append the table here too")
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
        named = sorted({k for k in mutant.killers if any(k in failure for failure in failures)})
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
        "", f"# P23-WAVE mutation table (run {time.strftime('%Y-%m-%dT%H:%M:%S')})", "",
        "| # | mutant | file | killer | result |", "|---|---|---|---|---|",
        *rows, "",
        f"unkilled: {', '.join(unkilled) if unkilled else 'none'}",
        f"tree clean after every mutant: {'yes' if not _porcelain() else 'NO'}",
        "",
    ])
    print("\n" + table)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("a", encoding="utf-8") as handle:
            handle.write(table)
    return 1 if unkilled else 0


if __name__ == "__main__":
    raise SystemExit(main())
