"""l1s2_mutation_table.py — every gate this card added, removed and re-run.

    python -m tools.l1s2_mutation_table --run <run dir> --data-dir <cold cache> \
        [--only <id>[,<id>]] [--list]

A test named after a gate is not a test of that gate. Each mutant below removes
ONE decision this card makes, exactly as documented, and the harness runs the
killers WITHOUT `-x` so that every killer that fires is recorded rather than
the first one. A mutant that survives its killers is a hole in the proof, and
it is printed as SURVIVED rather than explained away.

Two of the mutants are killed only by CONSTRUCTED fixtures and that is the
finding rather than a shortfall. `restore_the_absence_skip` is invisible to the
archive by construction: every section the readers omit today prints evidence,
so a tree that admitted an omission WITHOUT evidence would move nothing in the
run of record — which is precisely why the absence-only fixtures exist and why
the card required them. `drop_the_yield_only_class` has a measured archive
population of three sections, and its own unit fixture is the one that isolates
it from the declaration class beside it.

SAFETY (the batch-9 lesson, stated because a harness that leaves a mutant in a
shared tree is worse than no harness). It refuses to start on a dirty tree; it
restores in a `finally` that ignores the restore's own exit code; it verifies
`git status --porcelain` is clean before it returns; and it refuses to start
while another python process is already working on this host — the one-heavy-
harness-per-host rule, enforced rather than described. `--allow-concurrent`
overrides that last one and is a deliberate act: two harnesses mutating and
restoring one shared checkout is how a mutant gets left behind.

PRIVACY. Mutant ids, killer command lines, exit codes and counts. Nothing this
instrument writes or prints comes from a document.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Patch:
    path: str
    before: str
    after: str


@dataclass(frozen=True)
class Mutant:
    id: str
    what_it_removes: str
    patches: tuple[Patch, ...]
    #: (label, argv) — run in order, all of them, none allowed to stop the rest.
    killers: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    #: killers that need the run of record; `--run` / `--data-dir` are appended.
    archive_killers: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    note: str = ""


SIBLING = "analysis/sibling_omission.py"
SYMITAR = "analysis/symitar.py"
SCHEMA = "analysis/schema.py"
RECORD = "telemetry/record.py"

UNIT = ("the constructed fixtures",
        ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_sibling_omission.py"))
SYMITAR_SUITE = ("the symitar layout suite",
                 ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                  "tests/test_symitar.py"))
ZIONS_SUITE = ("the zions layout suite",
               ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "tests/test_zions_layouts.py"))
PLATFORM_SUITE = ("the core-processor layout suite",
                  ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "tests/test_community_section_layouts.py"))
DOCUMENT_SUITE = ("the document-object suite (RULE S)",
                  ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "tests/test_document_report.py"))
#: Gustavo's Q10 pins. The ruling file and the tripwire run in the default
#: selection; the protected-carrier replay is `corpus`-marked, which `pytest.ini`
#: deselects, so its killer names the marker explicitly.
Q10_PINS = ("the Q10 ruling pins + the document-outcome tripwire",
            ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "tests/test_l1s2_omission_ruling.py",
             "tests/test_l1s2_document_outcome.py"))
Q10_CARRIERS = ("the 15 protected carriers, replayed",
                ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 "-m", "corpus", "tests/test_l1s2_protected_carriers.py"))


def _admission(registrations: str) -> tuple[str, tuple[str, ...]]:
    return (f"the archive, through the omission probe ({registrations})",
            ("python", "-m", "tools.l1s2_admission_probe",
             "--registrations", registrations))


def _replay(parser_id: str) -> tuple[str, tuple[str, ...]]:
    return (f"RULE S's byte comparison against the run of record (--parser {parser_id})",
            ("python", "-m", "tools.cohort_replay", "--parser", parser_id,
             "--expect-identical"))


MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        id="drop_the_dormancy_declaration_class",
        what_it_removes=(
            "L1-C17's `printed_dormancy_declaration`: the class stops admitting "
            "a section, so a sibling whose only evidence is the printed "
            "declaration is refused and its document with it"),
        patches=(Patch(SIBLING,
                       "    if prints_dormancy_declaration(text):\n",
                       "    if False and prints_dormancy_declaration(text):\n"),),
        killers=(UNIT, SYMITAR_SUITE, ZIONS_SUITE),
        archive_killers=(_admission("symitar,zions"),),
        note="archive population: 8 sections (7 symitar, 1 zions)",
    ),
    Mutant(
        id="drop_the_zero_activity_summary_class",
        what_it_removes=(
            "L1-C17's `printed_zero_activity_summary`: a block stating its own "
            "opening, a coinciding closing, zero totals and zero counts no "
            "longer admits an omission"),
        patches=(Patch(SIBLING,
                       "    if prints_zero_activity_summary(\n",
                       "    if False and prints_zero_activity_summary(\n"),),
        killers=(UNIT, PLATFORM_SUITE),
        archive_killers=(_admission("community_section,dakota_west"),),
        note="archive population: 8 sections (6 community_section, 2 dakota_west)",
    ),
    Mutant(
        id="drop_the_yield_only_class",
        what_it_removes=(
            "L1-C17's `yield_only_arithmetic_with_summary_equality`: the "
            "sibling whose only postings are the yield the account itself "
            "earned is no longer admitted, and refuses instead"),
        patches=(Patch(SYMITAR,
                       "            omitted.omit(section.name, YIELD_ONLY_ARITHMETIC, len(rows))\n"
                       "            continue\n",
                       "            return None\n"),),
        killers=(UNIT, SYMITAR_SUITE),
        archive_killers=(_admission("symitar"),),
        note="archive population: 3 sections on 3 symitar documents",
    ),
    Mutant(
        id="restore_the_absence_skip",
        what_it_removes=(
            "the refusal itself: a section with NO printed evidence is admitted "
            "anyway, wearing a ratified label — which is the absence-based skip "
            "these three readers performed before this card"),
        patches=(Patch(SIBLING,
                       "        if reason is None:\n"
                       "            self.refuse()\n"
                       "            return False\n",
                       "        if reason is None:\n"
                       "            reason = PRINTED_ZERO_ACTIVITY_SUMMARY\n"),),
        killers=(UNIT,),
        archive_killers=(_admission("symitar,community_section,dakota_west,zions"),),
        note=("archive population: ZERO by construction — every section the "
              "readers omit today prints evidence, so only the constructed "
              "absence-only fixtures can kill this one"),
    ),
    Mutant(
        id="open_the_closed_vocabulary",
        what_it_removes=(
            "L1-C17's membership check at the point the record is BUILT, so a "
            "reason naming absence rather than printed evidence could reach a "
            "payload"),
        patches=(Patch(SIBLING,
                       "        if self.reason not in EVIDENCE_CLASSES:\n",
                       "        if False and self.reason not in EVIDENCE_CLASSES:\n"),),
        killers=(UNIT,),
        note="a constructed fixture by nature: no reader passes an unratified reason",
    ),
    Mutant(
        id="write_the_omission_onto_the_statement",
        what_it_removes=(
            "RULE S's boundary: the record is written onto `Statement` — ONE "
            "ACCOUNT's object — instead of onto the document, so every "
            "single-account payload in the archive gains a key"),
        patches=(
            Patch(SCHEMA,
                  "    currency: str = Field(default=\"USD\", description=\"ISO currency code.\")\n",
                  "    currency: str = Field(default=\"USD\", description=\"ISO currency code.\")\n"
                  "    unpublished_sibling_sections: list[dict] = []\n"),
            Patch(SYMITAR,
                  "    publish_omissions(omitted.omissions)\n",
                  "    stmt.unpublished_sibling_sections = [\n"
                  "        {\"label\": record.label, \"reason\": record.reason,\n"
                  "         \"posting_count\": record.posting_count}\n"
                  "        for record in omitted.omissions\n"
                  "    ]\n"),
        ),
        killers=(UNIT, DOCUMENT_SUITE),
        archive_killers=(_replay("symitar"),),
        note=("the archive killer IS the byte comparison: `--expect-identical` "
              "exits 3 when any replayed payload differs from the run of "
              "record's stored one"),
    ),
    # ---------------------------------------------------------------------
    # The two the independent re-review built. Q-1 was already killed; Q-3 was
    # NOT, and it is why the document-outcome resolver and its tripwire exist.
    # Both are carried here so the kill is reproducible rather than asserted.
    # ---------------------------------------------------------------------
    Mutant(
        id="Q1_the_omission_is_admitted_but_never_surfaced",
        what_it_removes=(
            "the SURFACE half of Gustavo's Q10 ruling: the section is still "
            "admitted on printed evidence, but the record never reaches the "
            "document — a silent drop wearing an evidence-based skip's clothes"),
        patches=(Patch(SIBLING,
                       "    sink = _COLLECTING.get()\n",
                       "    return  # MUTANT Q-1: the record never reaches the document\n"
                       "    sink = _COLLECTING.get()\n"),),
        # `Q10_CARRIERS` is a plain killer and NOT an archive one: archive
        # killers have `--run` / `--data-dir` appended, and pytest answers an
        # unknown option with exit 4 — which would have counted as a kill while
        # the test never ran. It reaches the archive through the test's own
        # ancestor walk instead.
        killers=(UNIT, Q10_PINS, Q10_CARRIERS),
        note="the re-review's Q-1; it was already killed before this closure",
    ),
    Mutant(
        id="Q3_a_document_fold_demotes_on_any_omission",
        what_it_removes=(
            "the DO-NOT-DEMOTE half: design §1.5's original fold, written "
            "exactly as it stood before Q10 superseded it — a document-level "
            "classifier returning `review` / `sibling_section_omitted` whenever "
            "the document carries an omission, which demotes all 15 protected "
            "carriers"),
        patches=(Patch(RECORD,
                       "TELEMETRY_VERSION = 1\n",
                       "TELEMETRY_VERSION = 1\n\n\n"
                       "def classify_document(document):  # MUTANT Q-3\n"
                       "    if getattr(document, \"omissions\", None):\n"
                       "        return (\"review\", \"sibling_section_omitted\")\n"
                       "    return (\"validated\", \"approved\")\n"),),
        killers=(Q10_PINS, Q10_CARRIERS),
        note=("the re-review's Q-3, which passed EVERY pin before this closure. "
              "It is killed on three legs now: the document-outcome assertions "
              "read the fold through the resolver, the tripwire's "
              "`no document fold yet` pin fires, and the superseded-reason scan "
              "fires on the reason string itself"),
    ),
)


#: Exit codes that mean THE KILLER DID NOT RUN, not that it fired. `pytest`
#: answers a usage error with 4 and "no tests collected" with 5, and
#: `cohort_replay` answers an empty cohort with 4. Counting those as kills is
#: the exact vacuity this harness exists to prevent — it was found the ordinary
#: way, by a killer that was handed an option pytest does not take and reported
#: a confident 4 while the test never executed.
DID_NOT_RUN = (4, 5)


def _run(argv: tuple[str, ...]) -> int:
    completed = subprocess.run(list(argv), cwd=REPO, capture_output=True, text=True)
    return completed.returncode


def _fired(code: int) -> bool:
    """Did this killer actually detect the mutant?"""
    return code > 0 and code not in DID_NOT_RUN


def _other_python_processes() -> list[str]:
    """Other python processes on this host, as `name:pid`, excluding this one.

    The rule the batch-9 records state is "check `tasklist` for another python
    first"; this is that check, made mechanical. `tasklist` is the Windows host's
    own tool and `ps` covers a POSIX one; if neither answers, the list is empty
    and the harness proceeds — a probe that cannot see is not evidence that the
    host is busy, and refusing on a failed probe would make the tool unrunnable
    wherever it cannot look.
    """
    mine = str(os.getpid())
    found: list[str] = []
    try:
        listing = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                                 capture_output=True, text=True, timeout=30)
        rows = [line for line in listing.stdout.splitlines() if line.startswith('"python')]
        for row in rows:
            cells = [cell.strip('"') for cell in row.split('","')]
            if len(cells) >= 2 and cells[1] != mine:
                found.append(f"{cells[0]}:{cells[1]}")
        if rows:
            return found
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        listing = subprocess.run(["ps", "-eo", "pid,comm"], capture_output=True,
                                 text=True, timeout=30)
        for line in listing.stdout.splitlines()[1:]:
            parts = line.split(None, 1)
            if len(parts) == 2 and "python" in parts[1] and parts[0] != mine:
                found.append(f"{parts[1].strip()}:{parts[0]}")
    except (OSError, subprocess.SubprocessError):
        pass
    return found


def _dirty() -> str:
    return subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _apply(mutant: Mutant) -> None:
    for patch in mutant.patches:
        path = REPO / patch.path
        source = path.read_text(encoding="utf-8")
        if source.count(patch.before) != 1:
            raise RuntimeError(
                f"{mutant.id}: the anchor for {patch.path} matches "
                f"{source.count(patch.before)} times, not once")
        path.write_text(source.replace(patch.before, patch.after), encoding="utf-8")


def _restore(mutant: Mutant) -> None:
    for patch in mutant.patches:
        subprocess.run(["git", "checkout", "--", patch.path], cwd=REPO,
                       capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--only", default="")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--allow-concurrent", action="store_true",
                        help="run even though another python process is working on this host")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    chosen = [m for m in MUTANTS
              if not args.only or m.id in {p.strip() for p in args.only.split(",")}]
    if args.list:
        for mutant in chosen:
            print(f"{mutant.id}: {mutant.what_it_removes}")
        return 0

    others = [] if args.allow_concurrent else _other_python_processes()
    if others:
        print("REFUSING: another python process is working on this host, and two "
              "harnesses mutating and restoring one shared checkout is how a "
              "mutant gets left behind.")
        for other in others:
            print(f"  * {other}")
        print("Wait for it, or pass --allow-concurrent deliberately.")
        return 5

    dirty = _dirty()
    if dirty:
        print("REFUSING: the working tree is dirty. A mutation harness is only "
              "correct on a clean tree — a restore here would discard work.")
        print(dirty)
        return 3

    archive = bool(args.run and args.data_dir)
    if not archive:
        print("NOTE: --run/--data-dir not given; the archive killers are skipped "
              "and reported as `not run`.")

    rows: list[tuple[Mutant, list[tuple[str, int]]]] = []
    survived: list[str] = []
    for mutant in chosen:
        print(f"\n## {mutant.id}", flush=True)
        results: list[tuple[str, int]] = []
        try:
            _apply(mutant)
            for label, killer in mutant.killers:
                code = _run(killer)
                print(f"   {label}: exit {code}", flush=True)
                results.append((label, code))
            for label, killer in mutant.archive_killers:
                if not archive:
                    results.append((label, -1))
                    continue
                code = _run(killer + ("--run", str(args.run),
                                      "--data-dir", str(args.data_dir)))
                print(f"   {label}: exit {code}", flush=True)
                results.append((label, code))
        finally:
            _restore(mutant)
        left = _dirty()
        if left:
            print("STOP: the tree did not come back clean after this mutant.")
            print(left)
            return 4
        if not any(_fired(code) for _label, code in results):
            survived.append(mutant.id)
        rows.append((mutant, results))

    print()
    print("# L1-S2 — the mutation table")
    print()
    print("| mutant | what it removes | killers that FIRED | killers that did not |")
    print("|---|---|---|---|")
    for mutant, results in rows:
        fired = [f"{label} (exit {code})" for label, code in results if _fired(code)]
        quiet = [f"{label} (not run)" if code == -1
                 else f"{label} (DID NOT RUN — exit {code})" if code in DID_NOT_RUN
                 else label
                 for label, code in results if not _fired(code)]
        print(f"| `{mutant.id}` | {mutant.what_it_removes} | "
              f"{'; '.join(fired) or '**NONE — SURVIVED**'} | {'; '.join(quiet) or '-'} |")
    print()
    for mutant, _results in rows:
        if mutant.note:
            print(f"* `{mutant.id}` — {mutant.note}")
    print()
    print(f"MUTANTS={len(rows)} SURVIVED={len(survived)}"
          + (" (" + ", ".join(survived) + ")" if survived else ""))
    return 2 if survived else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
