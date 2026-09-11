"""tools/p23egate_mutation_table.py — the P23-EGATE mutation table (M1-M10),
applied as real textual edits and run for real.

    python tools/p23egate_mutation_table.py [--only M3 M7] [--out <private>.md]

A test named after a gate is not a test OF that gate. Every mutant below is
the edit the card words, applied to the working tree, with the suite that
should kill it run WITHOUT `-x` so a mutant that kills nothing is visible as
"0 killers" rather than hidden behind the first unrelated failure.

Host discipline this harness owes (BATCH9-RULES, "Mutation harnesses on a
shared host"), in the idiom `tools/p22truthtable_mutation_table.py` set:

* it REFUSES to start on a dirty tree — a harness that restores with
  `git checkout --` cannot tell its own mutant from a real edit;
* every restore is in a `finally` that ignores its own exit code, and
  `git status --porcelain` is asserted CLEAN after each mutant, so a git
  failure mid-run is a loud stop rather than a mutant left in the tree;
* it never runs two mutants at once and it is never run beside another
  harness;
* `--out` appends rather than overwrites (P22-FENCE re-review Q1): a table
  log that a second run truncates is a table log that cannot be checked.

M6 is deliberately not a tree edit. Its subject is a STATIC guard whose
reader is a pure function over source text, so the mutant is planted in a
scratch copy of the router's source inside the test itself and the working
tree is never touched at all — a stronger proof of the same property, and the
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

QUALITY = "ocr/extraction_quality.py"
RUNNER = "discovery/runner.py"
REPORT = "discovery/report.py"
CENSUS = "tools/extraction_quality_census.py"

T_QUALITY = "tests/test_extraction_quality.py"
T_ADMISSION = "tests/test_extraction_quality_admission.py"
T_CENSUS = "tests/test_extraction_quality_census.py"
T_DENOM = "tests/test_two_denominators.py"


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
        "M1", "a threshold changed without the version",
        QUALITY,
        '    "money_rate_floor": 0.02,',
        '    "money_rate_floor": 0.2,',
        [T_QUALITY],
        ["test_the_threshold_table_and_the_version_are_pinned_together"],
    ),
    Mutant(
        "M2", "the money-shape rate computed over ALL tokens, not the numeric ones",
        QUALITY,
        "else sum(1 for text in numeric if money_cents(text) is not None) / len(numeric)",
        "else sum(1 for text in numeric if money_cents(text) is not None) / max(1, word_count)",
        [T_QUALITY],
        ["test_the_money_rate_denominator_is_the_numeric_tokens_not_every_token"],
    ),
    Mutant(
        "M3", "the garbage rate ignoring repeated letters",
        QUALITY,
        '    return len(text) > int(_t("garbage_token_max_chars")) or bool(_REPEATED_LETTER_RE.search(text))',
        '    return len(text) > int(_t("garbage_token_max_chars"))',
        [T_QUALITY],
        ["test_a_repeated_letter_page_is_E2_although_every_token_is_short"],
    ),
    Mutant(
        "M4", "ink-versus-box coverage computed INSIDE the boxes",
        QUALITY,
        "return share, (None if not total else (total - inside) / total)",
        "return share, (None if not total else inside / total)",
        [T_QUALITY],
        ["test_a_partly_covered_page_is_E1_and_the_ink_it_measures_is_the_ink_OUTSIDE",
         "test_ink_far_from_every_word_box_is_a_coverage_gap"],
    ),
    Mutant(
        "M5", "the E-class set from the rec-score alone",
        QUALITY,
        "        or quality.garbage_rate > float(_t(\"garbage_rate_ceiling\"))\n    )",
        "        or quality.garbage_rate > float(_t(\"garbage_rate_ceiling\"))\n"
        "        or (quality.rec_p10 is not None and quality.rec_p10 < 0.5)\n    )",
        [T_QUALITY],
        ["test_the_rec_score_is_a_proxy_and_never_sets_a_class_on_its_own"],
    ),
    Mutant(
        "M6", "an eq_ value read in ocr/escalation.py or by the router",
        None, "", "", [T_ADMISSION],
        ["test_m6_an_extraction_quality_read_planted_in_a_scratch_router_is_caught"],
        in_process=True,
    ),
    Mutant(
        "M7", "ROW_FIELDS reordered",
        REPORT,
        '    "eq_version", "eq_word_count", "eq_density", "eq_rec_mean", "eq_rec_p10",',
        '    "eq_word_count", "eq_version", "eq_density", "eq_rec_mean", "eq_rec_p10",',
        [T_DENOM],
        ["test_the_new_columns_are_appended_at_the_end_of_row_fields_in_the_card_order",
         "test_the_extraction_quality_columns_are_the_modules_own_table_in_its_own_order"],
    ),
    Mutant(
        "M8", "the projection reading native-only rows",
        RUNNER,
        '        evidence = getattr(document, "evidence", None) if document is not None else None\n'
        '        if evidence is None or getattr(evidence, "extractor_id", "") == NATIVE_EXTRACTOR_ID:\n'
        "            return\n",
        '        evidence = (getattr(document, "evidence", None)\n'
        '                    or getattr(document, "native_evidence", None)) if document is not None else None\n'
        "        if evidence is None:\n"
        "            return\n",
        [T_QUALITY],
        ["test_the_projection_is_empty_on_a_native_only_read"],
    ),
    Mutant(
        "M8b", "only the extractor-id half of that guard removed (an extra: each half alone)",
        RUNNER,
        '        if evidence is None or getattr(evidence, "extractor_id", "") == NATIVE_EXTRACTOR_ID:',
        "        if evidence is None:",
        [T_QUALITY],
        ["test_the_projection_is_empty_on_a_native_only_read"],
    ),
    Mutant(
        "M9", "the census printing a per-document identifier",
        CENSUS,
        "        censuses.setdefault(configuration_of(evidence), Census()).add(quality)",
        '        censuses.setdefault(configuration_of(evidence) + f" sha={evidence.document_sha256}",\n'
        "                            Census()).add(quality)",
        [T_CENSUS],
        ["test_the_output_carries_counts_and_percentiles_and_no_document_content"],
    ),
    Mutant(
        # The planted import must SUCCEED. An import of a name that does not
        # exist is killed by an ImportError that collects the whole test file
        # as one ERROR — the guard never runs, and the row honestly reads "not
        # killed by the named killer", which is not the proof the card asks
        # for. `normalize_sign_glyphs` is a real name in `analysis/money.py`,
        # so the module still imports and the AST guard is what fails.
        "M10", "the metrics module importing `analysis` (an import that SUCCEEDS)",
        QUALITY,
        "from layout.signals import LEXICONS, fold, money_cents",
        "from analysis.money import normalize_sign_glyphs  # noqa: F401\nfrom layout.signals import LEXICONS, fold, money_cents",
        [T_QUALITY],
        ["test_the_module_imports_only_the_standard_library_evidence_and_layout_signals"],
    ),
    Mutant(
        "M10b", "the metrics module importing `ocr.paddle_client` (an extra: the other named import)",
        QUALITY,
        "from layout.signals import LEXICONS, fold, money_cents",
        "import ocr.paddle_client  # noqa: F401\nfrom layout.signals import LEXICONS, fold, money_cents",
        [T_QUALITY],
        ["test_the_module_imports_only_the_standard_library_evidence_and_layout_signals"],
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

    selected = [m for m in MUTANTS if args.only is None or m.ident in args.only]
    rows: list[str] = []
    unkilled: list[str] = []
    for mutant in selected:
        if mutant.in_process:
            code, failures = _run(mutant.suites)
            status = "KILLED (in-process, tree untouched)" if code == 0 and not failures else "NOT KILLED"
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

    table = "\n".join([
        "# P23-EGATE mutation table (M1-M10, plus the named extras)", "",
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
    return 0 if not unkilled else 2


if __name__ == "__main__":
    raise SystemExit(main())
