"""Phase 2.1 D1 tripwire: `evidence/` is a NEUTRAL package.

It may import the standard library and itself, nothing else — in particular
never `ocr`, `analysis`, `discovery`, `webapp` or `telemetry`. That is what
lets `ocr/` (the producer) and `analysis/structurer/geometry.py` (the
consumer) share one representation without either Phase 2.0 import boundary
widening: `tests/test_escalation_tripwires.py` keeps the analysis -> ocr
allowlist EMPTY, and the OCR ladder keeps importing nothing from `analysis`.
Checked by AST at any depth (a lazy import inside a function counts).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evidence"

FORBIDDEN_PREFIXES = ("ocr", "analysis", "discovery", "webapp", "telemetry", "tools", "tests")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: inside the package by construction
                continue
            if node.module:
                names.add(node.module)
    return names


def _is_stdlib(name: str) -> bool:
    top = name.split(".")[0]
    return top in sys.stdlib_module_names or top in sys.builtin_module_names


def test_evidence_package_imports_only_the_standard_library():
    offenders: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        bad = {
            name for name in _imports(path)
            if not _is_stdlib(name) and name.split(".")[0] != "evidence"
        }
        if bad:
            offenders[str(path.relative_to(ROOT))] = bad
    assert not offenders, f"evidence/ must stay standard-library only: {offenders}"


def test_evidence_package_never_names_a_platform_layer():
    offenders: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        bad = {
            name for name in _imports(path)
            if name.split(".")[0] in FORBIDDEN_PREFIXES
        }
        if bad:
            offenders[str(path.relative_to(ROOT))] = bad
    assert not offenders, f"evidence/ reached into a platform layer: {offenders}"


def test_evidence_package_exists_at_the_top_level_and_is_importable_alone():
    assert (PACKAGE / "__init__.py").is_file()
    assert (PACKAGE / "canonical.py").is_file()
    # Importing the package must not drag any platform module into the process.
    before = {m for m in sys.modules if m.split(".")[0] in FORBIDDEN_PREFIXES}
    import evidence  # noqa: F401

    after = {m for m in sys.modules if m.split(".")[0] in FORBIDDEN_PREFIXES}
    assert after == before
