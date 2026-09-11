"""P23-EGATE item 3: the extraction-quality metrics are ADMITTED AS NOTHING.

Ruling B's discipline is labelled evidence FIRST, review SECOND, admission
THIRD. Phase 2.3 measures; it admits nothing. That claim is worth exactly as
much as its enforcement, so it is enforced three ways:

* **by blob** — `ocr/escalation.py` is byte-identical to its content at this
  branch's base. Not "`ADMITTED_TRIGGERS` is unchanged" (a set can be
  rebuilt from the same names while the router around it moves), but the
  whole module, every line of it;
* **by vocabulary** — the admitted trigger set, the extractor order and the
  router's field set restated here independently of that module's own tests,
  so a change has to defeat two files;
* **by AST** — no module of the router, the analysis layer or the webapp
  imports `ocr.extraction_quality`, names an `eq_*` column, or reads one off
  anything. The guard is a pure function over source text, so M6 (an `eq_*`
  value read inside the router) is planted in a SCRATCH COPY and killed
  without the working tree ever being touched.

The fourth way is structural and lives elsewhere: `RouterInputs` has six
fields and none of them can hold a metric, `ocr/extraction_quality.py`
imports nothing but the standard library, `evidence` and `layout.signals`,
and `discovery/runner.py` writes the columns to the ROW at the row's single
exit, after the analysis has already finished.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from ocr.escalation import (
    ADMITTED_TRIGGERS,
    ALL_TRIGGERS,
    EXTRACTOR_ORDER,
    TRUNCATION_FLAGGED,
    RouterInputs,
)
from ocr.extraction_quality import EQ_ROW_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
ESCALATION = ROOT / "ocr" / "escalation.py"

#: The branch this cell was cut from (`train13`, the Phase 2.3 opening
#: commit) and the SHA-256 of `ocr/escalation.py` there, over the file's bytes
#: with line endings normalised to LF — this repository checks out CRLF on
#: Windows and LF on the Linux CI runner, and a pin that fired on a line
#: ending would be a pin on the platform, not on the router.
BASE_COMMIT = "26f94f5"
ESCALATION_SHA256_AT_BASE = "E8367533D6D394CA7F34A131E21DBC8AC122DE120E358CE03A1598FD374384EC"

#: Where an extraction-quality figure must never appear. `ocr/escalation.py`
#: is the router itself; `analysis/` is the layer that produces a financial
#: verdict; `webapp/` is the one that serves it.
GUARDED = ("ocr/escalation.py", "analysis", "webapp")

EQ_COLUMNS = tuple(column for column, _, _ in EQ_ROW_COLUMNS)


def normalised(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


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
# by blob
# ---------------------------------------------------------------------------

def test_the_router_module_is_byte_identical_to_its_content_at_the_base():
    digest = hashlib.sha256(normalised(ESCALATION)).hexdigest().upper()
    assert digest == ESCALATION_SHA256_AT_BASE, (
        f"ocr/escalation.py changed since {BASE_COMMIT}. Phase 2.3 measures extraction "
        "quality and admits none of it; a change here is a Phase 2.5 decision with its "
        "own ruling, not a side effect of a measurement card."
    )


# ---------------------------------------------------------------------------
# by vocabulary
# ---------------------------------------------------------------------------

def test_the_admitted_trigger_set_is_unchanged():
    assert ADMITTED_TRIGGERS == frozenset(ALL_TRIGGERS) - {TRUNCATION_FLAGGED}
    assert sorted(ADMITTED_TRIGGERS) == [
        "extractor_failed",
        "extractor_output_unusable",
        "image_only_document",
        "mixed_document_pages_without_native_text",
        "offline_rungs_produced_no_text",
        "operator_forced_paddle",
        "operator_forced_visual",
    ]
    assert TRUNCATION_FLAGGED not in ADMITTED_TRIGGERS
    # no E-class, no metric name, nothing this cell produced is a trigger
    assert not [name for name in ALL_TRIGGERS if name.startswith("eq_") or name in EQ_COLUMNS]


def test_the_extractor_order_and_the_router_field_set_are_unchanged():
    assert EXTRACTOR_ORDER == ("local_tesseract", "paddle", "visual")
    assert tuple(RouterInputs.__dataclass_fields__) == (
        "profile", "evidence", "triggers", "attempted", "stop", "enabled",
    )
    assert RouterInputs.__subclasses__() == []


# ---------------------------------------------------------------------------
# by AST
# ---------------------------------------------------------------------------

def test_no_router_analysis_or_webapp_module_reads_an_extraction_quality_figure():
    modules = guarded_modules()
    assert len(modules) > 50, "the guard scans a package, not a handful of files"
    assert ESCALATION in modules
    found: list[str] = []
    for path in modules:
        found.extend(offences(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT))))
    assert found == [], found


#: Where a planted mutant is inserted: inside the router's one decision, and
#: at the module's import block.
_DECIDE = "    def decide(inputs: RouterInputs) -> Escalation:\n"
_IMPORTS = "from dataclasses import dataclass\n"


@pytest.mark.parametrize("anchor, mutant, note", [
    (_DECIDE, "        quality = inputs.evidence.eq_class\n", "an eq_ value read off the router's inputs"),
    (_IMPORTS, "from ocr.extraction_quality import e_class\n", "the module imported by the router"),
    (_IMPORTS, "import ocr.extraction_quality\n", "the module imported by name"),
    (_DECIDE, '        name = "eq_money_rate"\n', "a column named as a string"),
])
def test_m6_an_extraction_quality_read_planted_in_a_scratch_router_is_caught(anchor, mutant, note):
    """M6's killer. The mutant is inserted into a COPY of the router's source
    held in this process; the tree is never touched, and the guard that would
    catch it in the repository is the same function that catches it here."""
    source = ESCALATION.read_text(encoding="utf-8")
    assert source.count(anchor) == 1
    planted = source.replace(anchor, anchor + mutant, 1)
    assert offences(planted, "scratch"), note
    # and the unmutated source is clean, so the test above is not vacuous
    assert offences(source, "scratch") == []


#: The only files outside the tests that may name an `eq_*` column, and why.
#: The first four are the column's own life: the module that computes it, the
#: row that carries it, the CSV that lists it, the census that reads it. The
#: last two are this cell's committed PROOF INSTRUMENTS, which name the
#: columns because naming them is their job — the mutation harness mutates
#: the column list by spelling it, and the fake-partition builder prints a
#: row's columns beside the census's figures. Neither is a reader in the
#: sense that matters: the layers that must never read one
#: (`ocr/escalation.py`, `analysis/`, `webapp/`) are scanned BY AST in
#: `test_no_router_analysis_or_webapp_module_reads_an_extraction_quality_figure`,
#: and this census is the second, coarser net around them.
ALLOWED_NAMERS = {
    "ocr/extraction_quality.py", "discovery/runner.py", "discovery/report.py",
    "tools/extraction_quality_census.py",
    "tools/p23egate_mutation_table.py", "tools/p23egate_fake_partition.py",
}


def test_the_report_is_the_only_thing_outside_the_module_that_names_the_columns():
    """Nothing reads `eq_*` but the report and this cell's own instruments —
    by MEASUREMENT over the tree, not by assertion. The list is closed here,
    and every guarded layer is separately required to be absent from it."""
    readers: set[str] = set()
    for path in sorted(ROOT.glob("*/*.py")) + sorted(ROOT.glob("*/*/*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("tests/") or relative.startswith(".claude/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(column in text for column in EQ_COLUMNS):
            readers.add(relative)
    assert readers <= ALLOWED_NAMERS, sorted(readers - ALLOWED_NAMERS)
    # and the direction that matters, stated as its own claim: not one module
    # of the router's layer, the analysis layer, the webapp, telemetry or the
    # neutral layout package names a column at all.
    guarded = {name for name in readers
               if name.startswith(("analysis/", "webapp/", "telemetry/", "layout/"))
               or (name.startswith("ocr/") and name != "ocr/extraction_quality.py")}
    assert guarded == set(), sorted(guarded)
    # a named allowance that names nothing is an allowlist rotting quietly
    missing = [name for name in ALLOWED_NAMERS if not (ROOT / name).exists()]
    assert missing == [], missing
