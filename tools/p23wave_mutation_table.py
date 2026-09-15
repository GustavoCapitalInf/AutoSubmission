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
        "M25", "raw source path is added to the ordinary row allowlist", WAVE,
        '    "source_path", "cache_paddle", "wave_refusal_reason", "bytes_up", "bytes_down",\n',
        '    "source_path", "cache_paddle", "wave_refusal_reason", "bytes_up", "bytes_down", "relative_path",\n',
        [T_WAVE + "::test_export_positive_allowlist_preserves_aliases_missing_values_and_originals"],
        ["test_export_positive_allowlist_preserves_aliases_missing_values_and_originals"],
    ),
    Mutant(
        "M26", "raw generic report is copied into the ordinary export", WAVE,
        '    return target\n\n\ndef read_wave_technical_export(',
        '    (target / "report.json").write_bytes((source / "report.json").read_bytes())\n'
        '    return target\n\n\ndef read_wave_technical_export(',
        [T_WAVE + "::test_export_positive_allowlist_preserves_aliases_missing_values_and_originals"],
        ["test_export_positive_allowlist_preserves_aliases_missing_values_and_originals"],
    ),
    Mutant(
        "M27", "allowed status fields accept arbitrary source values", WAVE,
        '        _export_require(row[name] in choices, "wave_export_status_unknown")',
        '        _export_require(True, "wave_export_status_unknown")',
        [T_WAVE + "::test_export_rejects_unsafe_values_before_publication"],
        ["test_export_rejects_unsafe_values_before_publication"],
    ),
    Mutant(
        "M28", "the writer ignores the trusted original provenance digest", WAVE,
        '    _export_require(hashlib.sha256(provenance_raw).hexdigest() == expected_source_provenance_sha256,\n'
        '                    "wave_source_provenance_binding_mismatch")',
        '    _export_require(True, "wave_source_provenance_binding_mismatch")',
        [T_WAVE + "::test_export_requires_independent_rows_provenance_and_session_bindings"],
        ["test_export_requires_independent_rows_provenance_and_session_bindings"],
    ),
    Mutant(
        "M29", "a self-consistent export marker replaces trusted provenance", WAVE,
        '                       ("source_provenance_sha256", expected_source_provenance_sha256),\n',
        '',
        [T_WAVE + "::test_export_reader_refuses_forged_or_corrupt_marker"],
        ["test_export_reader_refuses_forged_or_corrupt_marker"],
    ),
    Mutant(
        "M30", "a legacy state loader accepts a new or unknown storage marker", WAVE,
        '        _validate_storage_chunks(payload.get("chunks", []), payload["version"])\n',
        '',
        [T_WAVE + "::test_state_rejects_new_storage_in_old_format_and_unknown_markers"],
        ["test_state_rejects_new_storage_in_old_format_and_unknown_markers"],
    ),
    Mutant(
        "M31", "ordinary and private output roots may overlap", WAVE,
        '    _export_require(left != right and not left.is_relative_to(right)\n'
        '                    and not right.is_relative_to(left), "wave_storage_roots_overlap")',
        '    _export_require(True, "wave_storage_roots_overlap")',
        [T_WAVE + "::test_wave_refuses_overlapping_storage_before_discovery"],
        ["test_wave_refuses_overlapping_storage_before_discovery"],
    ),
    Mutant(
        "M32", "multiple new custody children silently select the first", WAVE,
        '    _export_require(len(fresh) <= 1, "wave_child_run_ambiguous")',
        '    _export_require(True, "wave_child_run_ambiguous")',
        [T_WAVE + "::test_wave_refuses_multiple_new_custody_children_before_recording"],
        ["test_wave_refuses_multiple_new_custody_children_before_recording"],
    ),
    Mutant(
        "M33", "completed extraction is not persisted until after export", WAVE,
        '    state.save(state_path)\n    log("chunk.end",',
        '    log("chunk.end",',
        [T_WAVE + "::test_completed_private_chunk_survives_export_failure_with_truthful_session"],
        ["test_completed_private_chunk_survives_export_failure_with_truthful_session"],
    ),
    Mutant(
        "M34", "an export failure reports zero completed work in the session", WAVE,
        '                session["chunks"] += 1\n                session["documents"] += exc.processed\n',
        '',
        [T_WAVE + "::test_completed_private_chunk_survives_export_failure_with_truthful_session"],
        ["test_completed_private_chunk_survives_export_failure_with_truthful_session"],
    ),
    Mutant(
        "M35", "an offline export enters the pending-document loop", WAVE,
        '    supplied_source, supplied_output = Path(custody_run), Path(out_dir)\n',
        '    WaveState().pending([])\n    supplied_source, supplied_output = Path(custody_run), Path(out_dir)\n',
        [T_WAVE + "::test_offline_export_never_resumes_refused_documents_or_mutates_state"],
        ["test_offline_export_never_resumes_refused_documents_or_mutates_state"],
    ),
    Mutant(
        "M36", "lexical source and output paths may retarget during publication", WAVE,
        '    _export_require(valid, "wave_path_binding_changed")',
        '    _export_require(True, "wave_path_binding_changed")',
        [T_WAVE + "::test_export_rechecks_lexical_bindings_before_completion_marker"],
        ["test_export_rechecks_lexical_bindings_before_completion_marker"],
    ),
    Mutant(
        "M37", "arbitrary derived refusal strings become ordinary report keys", WAVE,
        '    _export_require(isinstance(reason, str) and (reason in WAVE_REFUSAL_REASONS or (empty and reason == "")),\n'
        '                    "wave_refusal_code_unknown")',
        '    _export_require(True, "wave_refusal_code_unknown")',
        [T_WAVE + "::test_export_and_report_refuse_unknown_derived_refusal_keys"],
        ["test_export_and_report_refuse_unknown_derived_refusal_keys"],
    ),
    Mutant(
        "M38", "software-defined failed-inspection sentinels are lost", WAVE,
        '    failed_inspection = (\n', '    failed_inspection = False and (\n',
        [T_WAVE + "::test_failed_attestation_preserves_only_the_defined_unavailable_sentinels"],
        ["test_failed_attestation_preserves_only_the_defined_unavailable_sentinels"],
    ),
    Mutant(
        "M39", "an existing export is silently reused instead of a fresh publication", WAVE,
        '    _export_require(not target.exists(), "wave_export_destination_exists")\n',
        '    if target.exists():\n        return target\n',
        [T_WAVE + "::test_export_positive_allowlist_preserves_aliases_missing_values_and_originals"],
        ["test_export_positive_allowlist_preserves_aliases_missing_values_and_originals"],
    ),
    Mutant(
        "M40", "a no-work legacy resume rewrites the storage format version", WAVE,
        '    if pending:\n        state.version = STATE_VERSION\n',
        '    state.version = STATE_VERSION\n',
        [T_WAVE + "::test_completed_population_resume_has_no_remote_lifecycle"],
        ["test_completed_population_resume_has_no_remote_lifecycle"],
    ),
    Mutant(
        "M41", "missing private custody becomes a missing measurement", WAVE,
        '        resolved_directory = _inside(directory, parent, exists=True)\n',
        '        if not (directory / "rows.csv").exists():\n            return None\n'
        '        resolved_directory = _inside(directory, parent, exists=True)\n',
        [T_WAVE + "::test_private_and_legacy_report_equivalence_and_mixed_authority"],
        ["test_private_and_legacy_report_equivalence_and_mixed_authority"],
    ),
    Mutant(
        "M24", "the requested tunnel compression is silently omitted",
        "tools/paddle_vast.py",
        "        *options,\n",
        "",
        ["tests/test_paddle_vast_tool.py"],
        ["test_tunnel_compression_is_read_at_launch_without_changing_the_endpoint"],
    ),
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
        " -newermt '@{since}' ",
        " ",
        [T_WAVE],
        ["test_the_temp_image_count_is_scoped_to_this_session"],
    ),
    Mutant(
        "M15", "process inspection counts its shell command as a worker",
        WAVE,
        "    '$1 ~ /^python([0-9]+([.][0-9]+)*)?$/ && $3 == \"{worker}\" '\n"
        "    '{{n++}} END {{print n+0}}'",
        "    '/paddle_worker[.]py/ {{n++}} END {{print n+0}}'",
        [T_WAVE],
        ["test_retention_process_count_distinguishes_the_inspector_from_the_worker"],
    ),
    Mutant(
        "M19", "a failed process listing is reported as no worker",
        WAVE,
        "PROCESSES=$(ps -eo comm=,args= 2>/dev/null) || exit 1; ",
        "PROCESSES=$(ps -eo comm=,args= 2>/dev/null); ",
        [T_WAVE],
        ["test_retention_executes_the_shell_and_refuses_incomplete_inspection"],
    ),
    Mutant(
        "M20", "retention ignores unexpected nested files",
        WAVE,
        'OTHER=$(find "$D" -mindepth 1 ! -type d ',
        'OTHER=$(find "$D" -mindepth 1 -maxdepth 1 ! -type d ',
        [T_WAVE],
        ["test_retention_executes_the_shell_and_refuses_incomplete_inspection"],
    ),
    Mutant(
        "M21", "a recovered report trusts stale state refusal vocabulary",
        WAVE,
        '    if out_dir is None and not any("storage" in chunk for chunk in state.chunks):\n'
        '        historical = state.refusals_by_reason()',
        '    if True:\n        historical = state.refusals_by_reason()',
        [T_WAVE + "::test_report_rederives_refusals_from_the_recorded_chunk_without_rewriting_state"],
        ["test_report_rederives_refusals_from_the_recorded_chunk_without_rewriting_state"],
    ),
    Mutant(
        "M22", "a recovered report reads the first chunk instead of the recorded attempt",
        WAVE,
        '            source_rows = _recorded_chunk_rows(state, by_chunk.get(outcome.chunk, {}),',
        '            source_rows = _recorded_chunk_rows(state, by_chunk.get(0, {}),',
        [T_WAVE + "::test_report_rederives_refusals_from_the_recorded_chunk_without_rewriting_state",
         T_WAVE + "::test_mixed_chunks_bind_latest_refusal_and_exact_technical_denominators"],
        ["test_report_rederives_refusals_from_the_recorded_chunk_without_rewriting_state"],
    ),
    Mutant(
        "M23", "a no-work resume performs an unstarted remote teardown",
        WAVE,
        "        if lifecycle is not None and pending:\n            attestation = lifecycle.down(",
        "        if lifecycle is not None:\n            attestation = lifecycle.down(",
        [T_WAVE],
        ["test_completed_population_resume_has_no_remote_lifecycle"],
    ),
    Mutant(
        "M17", "telemetry searches only the flat directory and omits population runs",
        WAVE,
        '    supplied = (root / state.population_name / name, root / name)',
        '    supplied = (root / name,)',
        [T_WAVE + "::test_report_reads_each_populations_nested_run_directory"],
        ["test_report_reads_each_populations_nested_run_directory"],
    ),
    Mutant(
        "M18", "telemetry silently chooses one of two matching run directories",
        WAVE,
        "    if len(candidates) > 1:\n"
        "        raise WaveRefused(\"ambiguous population run directory for technical measurements\")\n",
        "",
        [T_WAVE],
        ["test_report_reads_each_populations_nested_run_directory"],
    ),
    Mutant(
        "M16", "process inspection ignores a real live worker",
        WAVE,
        "    '{{n++}} END {{print n+0}}'",
        "    '{{n++}} END {{print 0}}'",
        [T_WAVE],
        ["test_retention_process_count_distinguishes_the_inspector_from_the_worker"],
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
