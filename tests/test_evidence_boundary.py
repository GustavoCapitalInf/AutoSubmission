"""The `evidence/` boundary tripwire, amended precisely for the ONE native
reader (Phase 2.2 cell K, `docs/agent-handoffs/P22-IDENTITY.md` item 4; D3;
case 16).

`evidence/` is a NEUTRAL package: it imports nothing from any repository
package — never `ocr`, `analysis`, `discovery`, `webapp`, `telemetry`,
`layout`, `tools` or `tests` — so `ocr/` (a producer) and
`analysis/structurer/geometry.py` (a consumer) can share one representation
without either Phase 2.0 import boundary widening. Since Phase 2.2 it also
holds the one native PDF reader, so the third-party rule is no longer "none":
it is EXACTLY one — `fitz` (PyMuPDF), imported LAZILY inside
`evidence/native.py::native_evidence_from_pdf`, and nowhere else, at no other
site, under no other name. Checked by AST at any depth: every import node's
enclosing function and module are asserted, so a module-level `import fitz`
anywhere in the package (mutants M2/M3) fails here, and `import evidence`
must succeed in a subprocess where `fitz` is made unimportable.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evidence"

FORBIDDEN_PREFIXES = ("ocr", "analysis", "discovery", "webapp", "telemetry", "layout", "tools", "tests")

#: The ONE admitted third-party import in the whole package: (relative file,
#: enclosing function name, imported module).
ADMITTED_THIRD_PARTY = {("evidence/native.py", "native_evidence_from_pdf", "fitz")}


def _import_sites(source: str, filename: str) -> list[tuple[str | None, str]]:
    """Every `(enclosing_function_or_None, module)` import site in `source`,
    at any depth. A relative import (`from .canonical import ...`) is inside
    the package by construction and is not reported."""
    tree = ast.parse(source, filename=filename)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    sites: list[tuple[str | None, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            names = [node.module] if node.module else []
        else:
            continue
        enclosing: str | None = None
        cursor: ast.AST | None = parents.get(node)
        while cursor is not None:
            if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                enclosing = cursor.name
                break
            cursor = parents.get(cursor)
        for name in names:
            sites.append((enclosing, name))
    return sites


def _is_stdlib(name: str) -> bool:
    top = name.split(".")[0]
    return top in sys.stdlib_module_names or top in sys.builtin_module_names


def _package_files() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


def _third_party_sites(files: list[Path]) -> set[tuple[str, str | None, str]]:
    found: set[tuple[str, str | None, str]] = set()
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        for enclosing, name in _import_sites(path.read_text(encoding="utf-8"), str(path)):
            if _is_stdlib(name) or name.split(".")[0] == "evidence":
                continue
            found.add((relative, enclosing, name))
    return found


def test_evidence_package_imports_nothing_from_any_repository_package():
    offenders: dict[str, set[str]] = {}
    for path in _package_files():
        bad = {
            name for _, name in _import_sites(path.read_text(encoding="utf-8"), str(path))
            if name.split(".")[0] in FORBIDDEN_PREFIXES
        }
        if bad:
            offenders[path.relative_to(ROOT).as_posix()] = bad
    assert not offenders, f"evidence/ reached into a repository package: {offenders}"


def test_the_only_third_party_import_is_fitz_lazily_inside_the_native_reader():
    """The precise amendment: the set of (file, enclosing function, module)
    third-party import sites over the WHOLE package equals exactly the one
    admitted site. A second `import fitz` anywhere (M3), a module-level one
    (M2 — enclosing function `None`), or any other third-party module fails
    this by set inequality, naming the site."""
    found = _third_party_sites(_package_files())
    assert found == ADMITTED_THIRD_PARTY, (
        f"evidence/ third-party import sites drifted from the ONE admitted lazy "
        f"`fitz` inside native_evidence_from_pdf: {sorted(found)}"
    )
    assert (PACKAGE / "native.py").is_file()


def test_fitz_is_the_first_statement_of_the_reader_body():
    """Item 1's letter: `import fitz` at the first line of the function body
    (after the docstring), wrapped only by the try that turns an unimportable
    PyMuPDF into the reader's honest `None`."""
    tree = ast.parse((PACKAGE / "native.py").read_text(encoding="utf-8"))
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "native_evidence_from_pdf"]
    assert len(functions) == 1
    body = functions[0].body
    first = body[1] if (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)) else body[0]
    assert isinstance(first, ast.Try), "the reader's first statement must be the guarded `import fitz`"
    assert len(first.body) == 1 and isinstance(first.body[0], ast.Import)
    assert [alias.name for alias in first.body[0].names] == ["fitz"]


def test_the_tripwire_is_not_vacuous_on_a_module_level_fitz_import():
    """The checker itself, exercised on synthetic sources: a module-level
    `import fitz` reports enclosing function `None`; a lazy one inside a
    function reports that function's name; a lazy `import numpy` inside the
    reader is still a foreign site. If any of these stopped being detected,
    the in-vivo mutants M2/M3 would survive while this file stayed green."""
    module_level = "import fitz\n\ndef native_evidence_from_pdf(b):\n    return None\n"
    assert (None, "fitz") in _import_sites(module_level, "synthetic")
    lazy = "def native_evidence_from_pdf(b):\n    try:\n        import fitz\n    except Exception:\n        return None\n"
    assert ("native_evidence_from_pdf", "fitz") in _import_sites(lazy, "synthetic")
    foreign = "def native_evidence_from_pdf(b):\n    import numpy\n    return None\n"
    assert ("native_evidence_from_pdf", "numpy") in _import_sites(foreign, "synthetic")
    nested = "def outer():\n    def inner():\n        import fitz\n"
    assert ("inner", "fitz") in _import_sites(nested, "synthetic")


def test_import_evidence_succeeds_with_fitz_unimportable():
    """`import evidence` in a subprocess where `fitz` cannot be imported
    (`sys.modules["fitz"] = None` makes any `import fitz` raise ImportError):
    the package imports, every name resolves, and the reader answers `None`
    rather than raising — the lazy import is what keeps the neutral package
    importable without PyMuPDF (D3's named risk, disproven)."""
    program = (
        "import sys\n"
        "sys.modules['fitz'] = None\n"
        "import evidence\n"
        "from evidence import native_evidence_from_pdf, ExtractionEvidence, PageFrame\n"
        "assert native_evidence_from_pdf(b'%PDF-1.4 not really') is None\n"
        "assert 'fitz' not in {m for m in sys.modules if sys.modules[m] is not None}\n"
        "print('OK')\n"
    )
    done = subprocess.run([sys.executable, "-c", program], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith("OK")


def test_evidence_package_exists_at_the_top_level_and_is_importable_alone():
    assert (PACKAGE / "__init__.py").is_file()
    assert (PACKAGE / "canonical.py").is_file()
    assert (PACKAGE / "native.py").is_file()
    # Importing the package must not drag any platform module into the process.
    before = {m for m in sys.modules if m.split(".")[0] in FORBIDDEN_PREFIXES}
    import evidence  # noqa: F401

    after = {m for m in sys.modules if m.split(".")[0] in FORBIDDEN_PREFIXES}
    assert after == before
