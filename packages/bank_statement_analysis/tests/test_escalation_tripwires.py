"""Structural tripwires for the reading ladder: the ABSENCE of every forbidden
edge, proved by inspecting source (AST / import graph), not by trusting a
comment.

1. `ocr/escalation.py` and `ocr/pipeline.py` import nothing from `analysis`,
   `discovery`, `webapp` or `telemetry`: the ladder cannot see a validator.
2. No module under `analysis/` imports `ocr.escalation`, `ocr.pipeline`,
   `ocr.ocr_client` or `discovery`: the validator cannot reach an extractor.
   The measured, pinned allowlist of `analysis/` -> `ocr` imports is EMPTY
   (measured 2026-09-01: `grep -rn "^from ocr\\|^import ocr" analysis/` finds
   nothing but comments).
3. `discovery/runner.py::RESEARCH_TRIGGERS` is read only by the report's
   historical research table.

The escalation router these tripwires also guarded (`EscalationRouter.decide`,
`RouterInputs`) had no call site left after the model rungs were removed, and
was deleted with its pins.
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_FOR_OCR_LADDER = ("analysis", "discovery", "webapp", "telemetry")

#: Measured 2026-09-01: no module under `analysis/` imports anything from
#: `ocr` at all (the handful of `ocr/...` mentions in that tree's source are
#: prose inside docstrings/comments, never an `import`). A future, deliberate
#: widening of this allowlist is a reviewed decision, not a silent drift.
ANALYSIS_TO_OCR_ALLOWLIST: frozenset[str] = frozenset()

#: The ocr modules a validator must never reach (checked alongside the
#: allowlist above and independently of it, per the card's explicit list).
FORBIDDEN_OCR_IMPORTS_FOR_ANALYSIS = ("ocr.escalation", "ocr.pipeline", "ocr.ocr_client")


def _imported_top_level_names(path: Path) -> set[str]:
    """Every `X` from `import X...` / `from X import ...` at any depth in the
    module (not just module level) — a lazy import inside a function is
    exactly the shape `ocr/pipeline.py` itself uses for `ocr.ocr_client`, so
    a guard that only looked at module-level imports would miss it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_ocr_document_imports_only_evidence_config_and_truncation():
    """P21-ROUTING design item 3: `ocr/document.py` gains an `evidence`
    import (the ONE cross-package import this module needs — `evidence/` is
    neutral and stdlib-only, so this widens no pinned boundary; see D1) but
    nothing else new: it may import `evidence` (canonical), its own
    `.config` and `.truncation`, `dataclasses`, and `__future__` — never
    `analysis`, `discovery`, `webapp`, `telemetry`, or any other `ocr.*`
    module."""
    imported = _imported_top_level_names(ROOT / "ocr" / "document.py")
    allowed = {"evidence", "evidence.canonical", "config", "truncation", "dataclasses", "__future__"}
    offenders = {name for name in imported if name not in allowed}
    assert not offenders, f"ocr/document.py imports beyond its pinned set: {sorted(offenders)}"


def test_escalation_and_pipeline_import_nothing_forbidden():
    for relative in ("ocr/escalation.py", "ocr/pipeline.py"):
        imported = _imported_top_level_names(ROOT / relative)
        offenders = {
            name for name in imported
            if any(name == pkg or name.startswith(pkg + ".") for pkg in FORBIDDEN_FOR_OCR_LADDER)
        }
        assert not offenders, f"{relative} imports forbidden package(s): {sorted(offenders)}"


def _analysis_files() -> list[Path]:
    return sorted((ROOT / "analysis").rglob("*.py"))


def test_analysis_ocr_imports_match_the_pinned_allowlist_exactly():
    found: set[str] = set()
    for path in _analysis_files():
        for name in _imported_top_level_names(path):
            if name == "ocr" or name.startswith("ocr."):
                found.add(name)
    assert found == ANALYSIS_TO_OCR_ALLOWLIST, (
        f"analysis/ -> ocr imports drifted from the pinned allowlist "
        f"{sorted(ANALYSIS_TO_OCR_ALLOWLIST)}: found {sorted(found)}. A "
        f"deliberate widening is a reviewed decision — update the pin "
        f"in the same commit that adds the import, with the justification."
    )


def test_no_analysis_module_imports_the_forbidden_ocr_or_discovery_modules():
    offenders: dict[str, set[str]] = {}
    for path in _analysis_files():
        imported = _imported_top_level_names(path)
        hit = {
            name for name in imported
            if name in FORBIDDEN_OCR_IMPORTS_FOR_ANALYSIS
            or name == "discovery" or name.startswith("discovery.")
        }
        if hit:
            offenders[str(path.relative_to(ROOT))] = hit
    assert not offenders, f"the validator must not reach an extractor: {offenders}"


#: The repo-wide scan reads every `.py` file under ROOT except `tests/`
#: (fixtures). It walks the filesystem rather than `git ls-files`, so an
#: untracked file that still runs is seen. It never descends into tool caches
#: or into `.claude`, where the main checkout keeps nested worktree checkouts
#: with their own copies of these modules.
EXCLUDED_TREES_FROM_REPO_SCAN = ("tests/",)
EXCLUDED_DIR_NAMES = {
    ".git", ".github", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache",
    "node_modules", ".venv", "venv", ".claude",
}


def _is_nested_checkout(directory: Path) -> bool:
    """A directory below ROOT that carries its own `.git` entry is a separate
    checkout, whatever its name."""
    return (directory / ".git").exists()


def _tracked_python_files() -> list[Path]:
    import os

    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [
            name for name in dirnames
            if name not in EXCLUDED_DIR_NAMES and not _is_nested_checkout(current / name)
        ]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = current / filename
            posix = str(path.relative_to(ROOT)).replace("\\", "/")
            if any(posix.startswith(tree) for tree in EXCLUDED_TREES_FROM_REPO_SCAN):
                continue
            paths.append(path)
    return paths


#: A program can live inside a string constant that is later run in a
#: subprocess (`tools/train/provenance.py::_TREE_PROBE` is one), where
#: `ast.parse(path.read_text())` alone cannot see it. Any multi-line string or
#: f-string of 40 characters or more that parses on its own, after
#: `textwrap.dedent` and with each f-string hole replaced by a placeholder
#: name, is scanned like the file's own tree.
_FSTRING_HOLE = "_FSTRING_HOLE_"


def _fstring_text(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append(_FSTRING_HOLE)
    return "".join(parts)


def _embedded_program_asts(source: str) -> list[ast.AST]:
    embedded: list[ast.AST] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = _fstring_text(node)
        else:
            continue
        if len(text) < 40 or "\n" not in text:
            continue
        try:
            embedded.append(ast.parse(textwrap.dedent(text)))
        except (SyntaxError, ValueError):
            continue
    return embedded


def _all_asts_for_source(source: str) -> list[ast.AST]:
    return [ast.parse(source), *_embedded_program_asts(source)]


def _tree_sources() -> list[tuple[str, str]]:
    return [
        (str(path.relative_to(ROOT)).replace("\\", "/"), path.read_text(encoding="utf-8"))
        for path in _tracked_python_files()
    ]


def test_the_tree_probe_is_detected_as_an_embedded_program_string():
    path = ROOT / "tools" / "train" / "provenance.py"
    count = len(_embedded_program_asts(path.read_text(encoding="utf-8")))
    assert count >= 1, "the _TREE_PROBE string was not detected as an embedded program"


def test_the_historical_research_trigger_constant_is_read_only_by_the_report():
    """`RESEARCH_TRIGGERS` stays for one reader: `discovery/report.py`'s research table, which counts historical
    research rows whose `escalation_trigger` is in it. No other module may reach for it."""
    readers = {}
    for relative, source in _tree_sources():
        if relative == "discovery/runner.py":
            continue
        lines = [node.lineno for tree in _all_asts_for_source(source) for node in ast.walk(tree)
                 if (isinstance(node, ast.Name) and node.id == "RESEARCH_TRIGGERS")
                 or (isinstance(node, ast.alias) and node.name == "RESEARCH_TRIGGERS")]
        if lines:
            readers[relative] = lines
    assert set(readers) == {"discovery/report.py"}, readers
