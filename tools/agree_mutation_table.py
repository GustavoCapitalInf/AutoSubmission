"""tools/agree_mutation_table.py — the P23-AGREE mutation table (M1-M25 plus
the review's own FR1 / FR3 / FR4), applied as real textual edits and run for
real.

    python tools/agree_mutation_table.py [--only M3 M8] [--out <private>.md]

A test named after a gate is not a test OF that gate. Every mutant below is
the edit the card words, applied to the working tree, with the suites that
should kill it run WITHOUT `-x`, so a mutant that kills nothing reads as
"0 killers" rather than hiding behind the first unrelated failure.

Host discipline (BATCH9-RULES, "Mutation harnesses on a shared host"):

* it REFUSES to start on a dirty tree — a harness that restores with
  `git checkout --` cannot tell its own mutant from a real edit;
* every restore is in a `finally` that ignores its own exit code, and
  `git status --porcelain` is asserted CLEAN after each mutant, so a git
  failure mid-run is a loud stop rather than a mutant left behind;
* it never runs two mutants at once and is never run beside another harness;
* `--out` is APPENDED to, never overwritten (P22-FENCE re-review-3 Q1): a
  second run of one mutant must not erase the table the first run produced.

M6 is deliberately not a tree edit. Its subject is a static guard whose
reader is a pure function over source TEXT, so the mutants are planted in an
in-memory copy of the router's and the structurer's real sources inside the
test itself; the row records that rather than pretending an edit happened.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AGREEMENT = "layout/agreement.py"
NATIVE = "evidence/native.py"
RUNNER = "discovery/runner.py"
CENSUS = "tools/agreement_census.py"

T_AGREE = "tests/test_agreement.py"
T_NATIVE = "tests/test_native_evidence.py"


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
        "M1", "the IoU threshold 0.5 -> 0.1 without a version bump",
        AGREEMENT,
        "IOU_THRESHOLD = 0.5",
        "IOU_THRESHOLD = 0.1",
        [T_AGREE],
        ["test_the_versions_and_thresholds_are_pinned",
         "test_a_known_shift_drops_the_matched_ratio_exactly_as_the_box_arithmetic_says"],
    ),
    Mutant(
        "M2", "a box may be matched twice (the extractor side is never spent)",
        AGREEMENT,
        "        taken_left.add(i)\n        taken_right.add(j)\n",
        "        taken_left.add(i)\n",
        [T_AGREE],
        ["test_alignment_is_greedy_and_uses_every_box_once"],
    ),
    Mutant(
        "M3", "a pixel frame is not scaled into points at all",
        AGREEMENT,
        "    if frame.space != PIXEL:\n        return 1.0, 1.0\n",
        "    if True:\n        return 1.0, 1.0\n",
        [T_AGREE],
        ["test_identical_words_at_300_dpi_agree_completely",
         "test_the_real_native_reader_agrees_with_the_fake_workers_evidence"],
    ),
    Mutant(
        "M4", "the character agreement skips the normaliser",
        AGREEMENT,
        "        left = normalise_text(native_display[i].text)\n"
        "        right = normalise_text(extractor_display[j].text)\n",
        "        left = native_display[i].text\n"
        "        right = extractor_display[j].text\n",
        [T_AGREE],
        ["test_the_case_and_whitespace_normaliser_is_applied"],
    ),
    Mutant(
        "M5", "the money and date agreement is taken over UNMATCHED pairs",
        AGREEMENT,
        "    for i, j, _ in pairs:\n",
        "    for i, j in zip(range(len(native_display)), range(len(extractor_display))):\n",
        [T_AGREE],
        ["test_a_known_shift_drops_the_matched_ratio_exactly_as_the_box_arithmetic_says"],
    ),
    Mutant(
        "M6", "a decision package reads an agreement statistic",
        None, "", "", [T_AGREE],
        ["test_m6_the_guard_fires_on_a_scratch_copy_of_the_router_and_the_structurer"],
        in_process=True,
    ),
    Mutant(
        "M7", "the projection falls back to the ONE reading a document has",
        RUNNER,
        "            if native is None or extractor is None:\n                return\n",
        "            if native is None or extractor is None:\n"
        "                native = extractor = native or extractor\n"
        "                if native is None:\n                    return\n",
        [T_AGREE],
        ["test_the_runner_projects_the_columns_only_when_both_evidences_exist"],
    ),
    Mutant(
        "M8", "N-1: the display transform is PyMuPDF's matrix regardless of the rect",
        NATIVE,
        "            if _matrices_agree(matrix, derived):",
        "            if True:",
        [T_NATIVE],
        ["test_an_overhanging_cropbox_on_a_rotated_page_lands_on_the_rasters_ink"],
    ),
    Mutant(
        "M9", "N-2: an indirect /Rotate is treated as absent",
        NATIVE,
        "        if kind == \"xref\":\n            return _indirect_rotate(document, page, value)\n",
        "        if kind == \"xref\":\n            return None\n",
        [T_NATIVE],
        ["test_an_indirect_invalid_rotate_is_resolved_and_refused_by_name",
         "test_an_indirect_rotate_written_as_a_real_is_coerced_by_the_writer_and_refused",
         "test_an_inherited_indirect_invalid_rotate_through_the_pages_node_is_refused_by_name"],
    ),
    Mutant(
        "M10", "the census prints a word off the page",
        CENSUS,
        "            result = page_agreement(page, other)\n",
        "            result = page_agreement(page, other)\n"
        "            print('  sample:', ' '.join(w.text for w in page.words[:3]))\n",
        [T_AGREE],
        ["test_the_census_prints_counts_and_percentiles_and_never_a_word"],
    ),
    # ---- the review's closure: the reviewer's three surviving fresh mutants,
    # a real-PDF mutant for the MAJOR, and one for each remaining MINOR fix.
    Mutant(
        "FR1", "the IoU threshold applied as `>` instead of `>=`",
        AGREEMENT,
        "            if score >= threshold:\n",
        "            if score > threshold:\n",
        [T_AGREE],
        ["test_the_iou_threshold_is_inclusive_at_exactly_one_half"],
    ),
    Mutant(
        "FR3", "the money comparison drops the SIGN (a debit agrees with a credit)",
        AGREEMENT,
        "    return tuple(token.cents for token in find_money(text))",
        "    return tuple(abs(token.cents) for token in find_money(text))",
        [T_AGREE],
        ["test_a_negative_amount_never_agrees_with_its_positive_twin"],
    ),
    Mutant(
        "FR4", "the skew statistic is the MEAN of the line slopes, not the median",
        AGREEMENT,
        "    slopes.sort()\n"
        "    middle = len(slopes) // 2\n"
        "    if len(slopes) % 2:\n"
        "        return slopes[middle]\n"
        "    return (slopes[middle - 1] + slopes[middle]) / 2\n",
        "    return sum(slopes) / len(slopes)\n",
        [T_AGREE],
        ["test_the_skew_statistic_is_the_MEDIAN_over_lines_not_the_mean"],
    ),
    Mutant(
        "M11", "MAJOR-1: an indirect /Rotate is acted on WITHOUT the page corroborating it",
        NATIVE,
        "    if resolved % 90 == 0:\n"
        "        return resolved if rotation == resolved % 360 else None\n"
        "    return resolved if _rect_is_transposed(page) else None\n",
        "    return resolved\n",
        [T_NATIVE],
        ["test_an_indirect_rotate_resolving_to_an_xref_number_is_the_page_every_renderer_shows",
         "test_an_indirect_rotate_resolving_to_an_xref_number_is_read_through_the_parent_walk_too",
         "test_the_resolver_makes_one_call_so_no_reference_shape_can_spin",
         "test_a_genuine_reference_chain_is_resolved_by_the_library_in_the_readers_one_call",
         "test_an_indirect_rotate_the_page_does_not_corroborate_is_no_value"],
    ),
    Mutant(
        "M12", "MINOR-2: both axes scaled by one nominal 72 / dpi",
        AGREEMENT,
        "    scale_x = 1.0 / float(frame.scale_x) if frame.scale_x else nominal\n"
        "    scale_y = 1.0 / float(frame.scale_y) if frame.scale_y else nominal\n",
        "    scale_x = nominal\n    scale_y = nominal\n",
        [T_AGREE],
        ["test_a_legal_non_uniform_pixel_frame_normalises_to_the_true_points"],
    ),
    Mutant(
        "M13", "MINOR-3: `frames_agree` stops comparing the rotation",
        AGREEMENT,
        "    if int(left.rotation_deg) != int(right.rotation_deg):\n        return False\n",
        "",
        [T_AGREE],
        ["test_two_frames_that_disagree_about_the_rotation_are_a_frame_mismatch"],
    ),
    Mutant(
        "M14", "MINOR-6: the two evidence reads move back outside the guard",
        RUNNER,
        "        try:\n"
        "            # The two attribute READS are inside the guard too (review\n",
        "        document = facts.get(\"document\")\n"
        "        native = getattr(document, \"native_evidence\", None) if document is not None else None\n"
        "        extractor = getattr(document, \"evidence\", None) if document is not None else None\n"
        "        try:\n"
        "            # The two attribute READS are inside the guard too (review\n",
        [T_AGREE],
        ["test_a_document_whose_evidence_attribute_raises_is_a_finding_not_an_exception"],
    ),
    Mutant(
        "M15", "the census ignores the selected population in a shared partition",
        CENSUS,
        "    documents = _population(args.shas) if args.shas else partition_documents\n",
        "    documents = partition_documents\n",
        [T_AGREE],
        ["test_the_census_separates_populations_in_one_shared_partition"],
    ),
    Mutant(
        "M16", "the sha census compares the current reader against itself",
        "tools/agree_native_census.py",
        "            if _evidence_sha(pdf_bytes) != _evidence_sha(pdf_bytes, baseline_reader):\n",
        "            if _evidence_sha(pdf_bytes) != _evidence_sha(pdf_bytes):\n",
        [T_NATIVE],
        ["test_the_native_census_exits_nonzero_on_movement_or_an_absent_population"],
    ),
    Mutant(
        "M17", "research provenance silently substitutes the offline OCR key",
        CENSUS,
        '    key = block.get("paddle_ocr_key")\n',
        '    key = block.get("paddle_ocr_key") or block.get("offline_ocr_key")\n',
        [T_AGREE],
        ["test_the_census_never_substitutes_an_offline_key_for_an_unrecorded_paddle_key"],
    ),
    Mutant(
        "M18", "the census permits a selected population with no canonical evidence pages",
        CENSUS,
        "    if not any(geometry_by_source.values()):\n",
        "    if False:\n",
        [T_AGREE],
        ["test_the_census_refuses_an_empty_measurement_under_the_selected_key",
         "test_the_census_refuses_empty_or_misidentified_evidence"],
    ),
    Mutant(
        "M19", "the census combines conflicting extractor identities under one settings key",
        CENSUS,
        "            if len(identities) > 1:\n",
        "            if False:\n",
        [T_AGREE],
        ["test_the_census_refuses_conflicting_extractor_identities_under_one_key"],
    ),
    Mutant(
        "M20", "the census trusts an envelope that conflicts with its cache record",
        CENSUS,
        '    if (payload.get("input_sha256") != sha or payload.get("settings_key") != key\n'
        '            or payload.get("stage") != "ocr"):\n',
        "    if False:\n",
        [T_AGREE],
        ["test_the_census_refuses_empty_or_misidentified_evidence"],
    ),
    Mutant(
        "M21", "the native census slot can contain extractor geometry",
        CENSUS,
        "        if native is not None and native.extractor_id != NATIVE_EXTRACTOR_ID:\n",
        "        if False:\n",
        [T_AGREE],
        ["test_the_census_refuses_empty_or_misidentified_evidence"],
    ),
    Mutant(
        "M22", "the extractor census slot can contain native geometry",
        CENSUS,
        "            if extractor.extractor_id == NATIVE_EXTRACTOR_ID:\n",
        "            if False:\n",
        [T_AGREE],
        ["test_the_census_refuses_empty_or_misidentified_evidence"],
    ),
    Mutant(
        "M23", "the census accepts evidence for a different document",
        CENSUS,
        "                if source.document_sha256.upper() != sha:\n",
        "                if False:\n",
        [T_AGREE],
        ["test_the_census_refuses_empty_or_misidentified_evidence"],
    ),
    Mutant(
        "M24", "the census searches only the first twenty-five records of another key",
        CENSUS,
        '                "SELECT input_sha256,artifact_path FROM artifact_cache WHERE stage=\'ocr\' AND settings_key=? ORDER BY input_sha256",\n',
        '                "SELECT input_sha256,artifact_path FROM artifact_cache WHERE stage=\'ocr\' AND settings_key=? ORDER BY input_sha256 LIMIT 25",\n',
        [T_AGREE],
        ["test_the_census_checks_for_another_evidence_key_beyond_the_first_twenty_five_records"],
    ),
    Mutant(
        "M25", "the census chooses the first of two indexed artifacts for one exact tuple",
        CENSUS,
        '            artifact_path = select_artifact(self.conn, "ocr", sha, self.key)\n',
        '            row = self.conn.execute("SELECT artifact_path FROM artifact_cache WHERE stage=\'ocr\' AND input_sha256=? AND settings_key=?", (sha, self.key)).fetchone()\n'
        '            artifact_path = str(row[0]) if row is not None else None\n',
        [T_AGREE],
        ["test_the_census_refuses_duplicate_index_rows_in_either_order"],
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


def _run(suites: list[str], *, select: str | None = None) -> tuple[int, list[str], int]:
    """`(exit code, failing node ids, tests that PASSED)` — WITHOUT `-x`.

    `select` adds a `-k` expression, which is how the in-process row proves
    that its killer was COLLECTED (a `-k` that matches nothing reports zero
    passed, and pytest exits 5).
    """
    command = [sys.executable, "-m", "pytest", *suites, "-q", "--no-header", "-p", "no:cacheprovider"]
    if select is not None:
        command += ["-k", select]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    failures = re.findall(r"^(?:FAILED|ERROR) (\S+)", completed.stdout, re.MULTILINE)
    match = re.search(r"(\d+) passed", completed.stdout)
    return completed.returncode, failures, int(match.group(1)) if match else 0


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
    parser.add_argument("--out", type=Path, default=None, help="APPEND the table here too")
    args = parser.parse_args(argv)

    dirty = _porcelain()
    if dirty:
        raise SystemExit(
            "refusing to start on a dirty tree: a harness that restores with "
            f"`git checkout --` cannot tell its own mutant from a real edit.\n{dirty}"
        )
    tree = _git("rev-parse", "HEAD").stdout.strip()[:12]

    selected = [m for m in MUTANTS if args.only is None or m.ident in args.only]
    rows: list[str] = []
    unkilled: list[str] = []
    for mutant in selected:
        if mutant.in_process:
            # Review closure, MINOR-5: the row must score THE KILLER, not
            # "the suite is green". The killer is run BY NAME and must be
            # collected and pass; a renamed, deleted or never-collected killer
            # reports zero passed and the row reads NOT KILLED — which is what
            # the old scorer (exit 0 and no named failure) could not tell from
            # a real kill.
            code, failures, _ = _run(mutant.suites)
            killer_code, killer_failures, killer_passed = _run(mutant.suites, select=mutant.killers[0])
            collected = killer_passed >= 1 and killer_code == 0 and not killer_failures
            status = ("KILLED (in-process, tree untouched)"
                      if code == 0 and not failures and collected else "NOT KILLED")
            rows.append(f"| {mutant.ident} | {mutant.what} | (scratch copy, no tree edit) | "
                        f"{mutant.killers[0]} ({killer_passed} collected and passed) | {status} |")
            if status == "NOT KILLED":
                unkilled.append(mutant.ident)
            print(f"{mutant.ident}: {status} — killer collected and passed: {killer_passed}", flush=True)
            continue
        try:
            apply_mutant(mutant)
            code, failures, _ = _run(mutant.suites)
        finally:
            _restore(mutant.path)
        clean = _porcelain()
        if clean:
            raise SystemExit(f"FATAL after {mutant.ident}: the tree is not clean after the restore.\n{clean}")
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

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = "\n".join([
        f"# P23-AGREE mutation table (M1-M25, FR1, FR3, FR4) — tree {tree}, {stamp}", "",
        "| # | mutant | file | killer | result |", "|---|---|---|---|---|",
        *rows, "",
        f"unkilled: {', '.join(unkilled) if unkilled else 'none'}",
        f"tree clean after every mutant: {'yes' if not _porcelain() else 'NO'}",
        "",
    ])
    print("\n" + table)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("a", encoding="utf-8") as handle:  # APPEND, never overwrite
            handle.write(table + "\n")
    return 0 if not unkilled else 2


if __name__ == "__main__":
    raise SystemExit(main())
