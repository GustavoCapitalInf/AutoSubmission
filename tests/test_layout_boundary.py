"""Phase 2.2 D1 tripwire: `layout/` is a NEUTRAL package.

It may import the standard library, `evidence` and itself — nothing else. In
particular never `ocr`, `analysis`, `discovery`, `webapp`, `telemetry`,
`tools` or `tests`, and never a third-party package (`fitz`, `numpy`, `PIL`,
`paddleocr` ...). The classifier reads evidence from any extractor and its
verdict is consumed by the intake ladder AND by analysis; the analysis -> ocr
allowlist is pinned EMPTY and ocr -> analysis is forbidden, so neither side
may own it (umbrella D1). Checked by AST at any depth (a lazy import inside a
function counts), in the exact idiom of `tests/test_evidence_boundary.py`.
Mutant M12 (a third-party import anywhere under `layout/`) dies here.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "layout"

FORBIDDEN_PREFIXES = ("ocr", "analysis", "discovery", "webapp", "telemetry", "tools", "tests")
ALLOWED_REPOSITORY_PACKAGES = ("evidence", "layout")
#: Modules a pure classifier has no business touching: clocks, randomness,
#: the process, the filesystem, the network. Their absence is what makes
#: `classify_document` replayable from its inputs alone (umbrella case 5).
FORBIDDEN_STDLIB = ("random", "secrets", "uuid", "time", "datetime", "os", "sys", "io", "pathlib",
                    "subprocess", "socket", "urllib", "http", "threading", "multiprocessing", "tempfile")


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


def _modules() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


def test_layout_package_exists_with_its_four_modules():
    for name in ("__init__.py", "signals.py", "document_class.py", "refusals.py"):
        assert (PACKAGE / name).is_file(), f"layout/{name} is missing"


def test_layout_package_imports_only_the_standard_library_and_evidence():
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        bad = {
            name for name in _imports(path)
            if not _is_stdlib(name) and name.split(".")[0] not in ALLOWED_REPOSITORY_PACKAGES
        }
        if bad:
            offenders[str(path.relative_to(ROOT))] = bad
    assert not offenders, f"layout/ must stay stdlib + evidence only: {offenders}"


def test_layout_package_never_names_a_platform_layer():
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        bad = {name for name in _imports(path) if name.split(".")[0] in FORBIDDEN_PREFIXES}
        if bad:
            offenders[str(path.relative_to(ROOT))] = bad
    assert not offenders, f"layout/ reached into a platform layer: {offenders}"


def test_layout_package_never_imports_a_clock_random_source_or_io_module():
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        bad = {name for name in _imports(path) if name.split(".")[0] in FORBIDDEN_STDLIB}
        if bad:
            offenders[str(path.relative_to(ROOT))] = bad
    assert not offenders, f"layout/ imported an impure module: {offenders}"


def test_layout_package_is_importable_alone_and_drags_no_platform_or_third_party_module():
    watched = FORBIDDEN_PREFIXES + ("fitz", "pymupdf", "numpy", "PIL", "paddleocr", "paddle", "cv2")
    before = {m for m in sys.modules if m.split(".")[0] in watched}
    import layout  # noqa: F401
    import layout.document_class  # noqa: F401
    import layout.refusals  # noqa: F401
    import layout.signals  # noqa: F401

    after = {m for m in sys.modules if m.split(".")[0] in watched}
    assert after == before


def test_the_tripwire_sees_a_third_party_import_at_any_depth(tmp_path):
    """Mutant M12 reproduced against the scanner itself: a lazy `import numpy`
    inside a function, and a `from PIL import Image` inside a class body,
    are both found — the walk is AST-deep, not top-level."""
    mutant = tmp_path / "signals.py"
    mutant.write_text(
        "def _widths(boxes):\n"
        "    import numpy as np\n"
        "    return np.median(boxes)\n"
        "class _Raster:\n"
        "    from PIL import Image\n",
        encoding="utf-8",
    )
    names = _imports(mutant)
    bad = {name for name in names if not _is_stdlib(name) and name.split(".")[0] not in ALLOWED_REPOSITORY_PACKAGES}
    assert bad == {"numpy", "PIL"}
