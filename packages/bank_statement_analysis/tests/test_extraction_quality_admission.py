"""P23-EGATE item 3: the extraction-quality metrics are read by nothing but the
report.

Phase 2.3 measures; it admits nothing. The escalation router those metrics
could once have fed is gone, so the claim is enforced by AST: no module of
`ocr/escalation.py` (the extraction-quality gate), the analysis layer or the
webapp imports `ocr.extraction_quality`, names an `eq_*` column, or reads one
off anything. The guard is a pure function over source text, so M6 (an `eq_*`
value read inside the gate) is planted in a SCRATCH COPY and killed without
the working tree ever being touched. A census over every tracked file closes
the list of modules that may name a column at all.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from ocr.extraction_quality import EQ_ROW_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
ESCALATION = ROOT / "ocr" / "escalation.py"

#: Where an extraction-quality figure must never appear. `ocr/escalation.py`
#: holds the extraction-quality gate; `analysis/` is the layer that produces a
#: financial verdict; `webapp/` is the one that serves it.
GUARDED = ("ocr/escalation.py", "analysis", "webapp")

EQ_COLUMNS = tuple(column for column, _, _ in EQ_ROW_COLUMNS)


def offences(source: str, label: str) -> list[str]:
    """Every way a module could read this cell's work, found by AST.

    A pure function of the TEXT so a mutant can be planted in a scratch copy
    (M6) rather than in the tree: a harness that edits the working tree to
    prove a static rule cannot tell its own mutant from a real edit."""
    found: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "extraction_quality" in alias.name:
                    found.append(f"{label}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "extraction_quality" in module:
                found.append(f"{label}: imports from {module}")
            for alias in node.names:
                if alias.name in EQ_COLUMNS or "extraction_quality" in alias.name:
                    found.append(f"{label}: imports the name {alias.name}")
        elif isinstance(node, ast.Attribute) and node.attr in EQ_COLUMNS:
            found.append(f"{label}:{node.lineno}: reads .{node.attr}")
        elif isinstance(node, ast.Name) and node.id in EQ_COLUMNS:
            found.append(f"{label}:{node.lineno}: names {node.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in EQ_COLUMNS:
            found.append(f"{label}:{node.lineno}: spells {node.value!r}")
    return found


def guarded_modules() -> list[Path]:
    modules: list[Path] = []
    for entry in GUARDED:
        path = ROOT / entry
        modules.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    return modules


# ---------------------------------------------------------------------------
# by AST
# ---------------------------------------------------------------------------

def test_no_gate_analysis_or_webapp_module_reads_an_extraction_quality_figure():
    modules = guarded_modules()
    assert len(modules) > 50, "the guard scans a package, not a handful of files"
    assert ESCALATION in modules
    found: list[str] = []
    for path in modules:
        found.extend(offences(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT))))
    assert found == [], found


#: Where a planted mutant is inserted: inside the gate's one assessment, and
#: at the module's import block.
_ASSESS = "    def assess(document, profile) -> EvidenceQuality:\n"
_IMPORTS = "from dataclasses import dataclass\n"


@pytest.mark.parametrize("anchor, mutant, note", [
    (_ASSESS, "        quality = document.eq_class\n", "an eq_ value read off the gate's input"),
    (_IMPORTS, "from ocr.extraction_quality import e_class\n", "the module imported by the gate"),
    (_IMPORTS, "import ocr.extraction_quality\n", "the module imported by name"),
    (_ASSESS, '        name = "eq_money_rate"\n', "a column named as a string"),
])
def test_m6_an_extraction_quality_read_planted_in_a_scratch_gate_is_caught(anchor, mutant, note):
    """M6's killer. The mutant is inserted into a COPY of the gate's source
    held in this process; the tree is never touched, and the guard that would
    catch it in the repository is the same function that catches it here."""
    source = ESCALATION.read_text(encoding="utf-8")
    assert source.count(anchor) == 1
    planted = source.replace(anchor, anchor + mutant, 1)
    assert offences(planted, "scratch"), note
    # and the unmutated source is clean, so the test above is not vacuous
    assert offences(source, "scratch") == []


def tracked_python_files() -> list[str]:
    """Every `.py` file GIT knows about, repository-relative and sorted.

    The tree's own answer to "what is in it", so a net built on it cannot
    drift from the repository as the repository grows — and it excludes the
    untracked scratch and worktree directories for free."""
    listing = subprocess.run(
        ["git", "ls-files", "--", "*.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return sorted(line.strip() for line in listing.splitlines() if line.strip())


#: The only files outside the tests that may name an `eq_*` column, and why.
#: The first four are the column's own life: the module that computes it, the
#: row that carries it, the CSV that lists it, the census that reads it. The
#: last two are this cell's committed PROOF INSTRUMENTS, which name the
#: columns because naming them is their job — the mutation harness mutates
#: the column list by spelling it, and the fake-partition builder prints a
#: row's columns beside the census's figures. Neither is a reader in the
#: sense that matters: the layers that must never read one
#: (`ocr/escalation.py`, `analysis/`, `webapp/`) are scanned BY AST in
#: `test_no_gate_analysis_or_webapp_module_reads_an_extraction_quality_figure`,
#: and this census is the second, coarser net around them.
#:
#: Model-code removal, slice S5: the census and the two proof instruments
#: (`tools/extraction_quality_census.py`, `tools/p23egate_mutation_table.py`,
#: `tools/p23egate_fake_partition.py`) left with the PaddleOCR rung whose
#: research partition they measured, so they left this allowlist too. Narrowing
#: an allowlist is not weakening it, and the rot check at the end of the test
#: below would fail on a named allowance that names nothing.
ALLOWED_NAMERS = {
    "ocr/extraction_quality.py", "discovery/runner.py", "discovery/report.py",
}


def test_the_report_is_the_only_thing_outside_the_module_that_names_the_columns():
    """Nothing reads `eq_*` but the report and this cell's own instruments —
    by MEASUREMENT over the tree, not by assertion. The list is closed here,
    and every guarded layer is separately required to be absent from it."""
    tracked = tracked_python_files()
    # A depth-limited glob is a net with a hole in it: the previous spelling
    # (`*/*.py` and `*/*/*.py`) missed all eleven modules at the repository
    # ROOT — `corpus_gate.py`, `parse.py`, `analyze.py`, `batch.py` and the
    # rest — and any module four directories deep (review MINOR-4). `git
    # ls-files` is the tree's own answer to "what is in it", so the net cannot
    # drift from the repository as it grows.
    assert len(tracked) > 200, "the census scans the tree, not a handful of files"
    assert "corpus_gate.py" in tracked, "the repository root is inside the net"
    readers: set[str] = set()
    for relative in tracked:
        if relative.startswith("tests/") or relative.startswith(".claude/"):
            continue
        text = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
        if any(column in text for column in EQ_COLUMNS):
            readers.add(relative)
    assert readers <= ALLOWED_NAMERS, sorted(readers - ALLOWED_NAMERS)
    # and the direction that matters, stated as its own claim: not one module
    # of the gate's layer, the analysis layer, the webapp, telemetry or the
    # neutral layout package names a column at all.
    guarded = {name for name in readers
               if name.startswith(("analysis/", "webapp/", "telemetry/", "layout/"))
               or (name.startswith("ocr/") and name != "ocr/extraction_quality.py")}
    assert guarded == set(), sorted(guarded)
    # a named allowance that names nothing is an allowlist rotting quietly
    missing = [name for name in ALLOWED_NAMERS if not (ROOT / name).exists()]
    assert missing == [], missing
