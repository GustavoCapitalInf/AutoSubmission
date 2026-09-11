"""tools/agree_mutation_table.py — the P23-AGREE mutation table (M1-M10),
applied as real textual edits and run for real.

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
        "M3", "a pixel frame is not scaled by 72 / dpi",
        AGREEMENT,
        "        return POINTS_PER_INCH / float(frame.dpi)",
        "        return 1.0",
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
        "        if native is None or extractor is None:\n            return\n",
        "        if native is None or extractor is None:\n"
        "            native = extractor = native or extractor\n"
        "            if native is None:\n                return\n",
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
        "        if kind == \"xref\":\n            return _resolved_rotate_int(document, value)\n",
        "        if kind == \"xref\":\n            return None\n",
        [T_NATIVE],
        ["test_an_indirect_invalid_rotate_is_resolved_and_refused_by_name",
         "test_an_indirect_rotate_written_as_a_real_is_coerced_by_the_writer_and_refused"],
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
        [sys.executable, "-m", "pytest", *suites, "-q", "--no-header", "-p", "no:cacheprovider"],
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
            code, failures = _run(mutant.suites)
            named = [k for k in mutant.killers if any(k in failure for failure in failures)]
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
        f"# P23-AGREE mutation table (M1-M10) — tree {tree}, {stamp}", "",
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
