"""`experiments/` is measurement code and must stay outside every real path.

A spike earns its keep by producing numbers, and it earns its danger by being
importable. This test is the whole safety argument for committing spike code
rather than gitignoring it: production may not depend on it, in either
direction that matters — no production module imports it, and nothing in it can
be reached from the dispatch or pipeline path.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Everything that ships. `tests/` is excluded because this file names the word
#: itself, and `experiments/` because it may of course import itself.
PRODUCTION_TREES = ("analysis", "ocr", "webapp", "discovery", "telemetry", "benchmark")
PRODUCTION_MODULES = (
    "batch.py", "analyze.py", "parse.py", "corpus_gate.py", "corpus_artifacts.py",
    "conftest.py",
)

_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+experiments\b", re.MULTILINE)


def production_sources() -> list[Path]:
    files = [ROOT / name for name in PRODUCTION_MODULES if (ROOT / name).exists()]
    for tree in PRODUCTION_TREES:
        files.extend(sorted((ROOT / tree).rglob("*.py")))
    return files


def test_no_production_module_imports_experiments():
    offenders = [
        str(path.relative_to(ROOT))
        for path in production_sources()
        if _IMPORT_RE.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"experiments/ is not production code, but it is imported by: {offenders}"


def test_the_experiments_tree_is_labelled_as_such():
    readme = ROOT / "experiments" / "README.md"
    if not readme.exists():
        return  # the tree is gone, which is the other acceptable end state
    text = readme.read_text(encoding="utf-8").lower()
    assert "never production" in text
