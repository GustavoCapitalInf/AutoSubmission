"""CI installs every third-party package a test imports with `pytest.importorskip`, so no test that exists to run in
CI is skipped there in silence.

The audit of the model-code removal (2026-10) measured 12 such skips on a fresh CI-shaped install: every test that
reads an exported spreadsheet back with `openpyxl`, which no requirement file named. `requirements-dev.txt` (the
CI test install, .github/workflows/corpus-gate.yml) now names it, and this test keeps the next such package from
slipping past: an `importorskip` of a package the CI install set does not hold fails here, and a new name has to be
mapped to its distribution below on purpose.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from tests.test_no_model_clients import _ci_install_files, _normalise, requirement_findings

ROOT = Path(__file__).resolve().parents[1]

#: Import name -> distribution (PEP 503 normalised) for every third-party module a test importorskips.
IMPORTORSKIP_DISTRIBUTIONS = {
    "openpyxl": "openpyxl",  # MIT; reads the exported .xlsx back (tests/test_webapp_security.py, ..._true_revenue.py)
    "fitz": "pymupdf",       # requirements.txt, the runtime install
}


def importorskip_names(source: bytes) -> list[str]:
    """The constant module names a source passes to `importorskip`."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and (getattr(node.func, "attr", None) or getattr(node.func, "id", None)) == "importorskip"):
            names.append(node.args[0].value)
    return names


def _first_party(name: str) -> bool:
    top = name.split(".")[0]
    return (ROOT / top).is_dir() or (ROOT / f"{top}.py").is_file()


def _test_sources() -> dict[str, bytes]:
    listing = subprocess.run(["git", "ls-files", "-z", "--", "tests/*.py"], cwd=ROOT, capture_output=True,
                             check=True).stdout.decode("utf-8")
    files = [path for path in listing.split("\0") if path] or sorted(
        path.relative_to(ROOT).as_posix() for path in (ROOT / "tests").glob("*.py"))
    assert len(files) > 200, "not looking at the test suite"
    return {relative: (ROOT / relative).read_bytes() for relative in files}


def test_the_scan_reads_an_importorskip_in_every_spelling():
    source = (b"import pytest\nfrom pytest import importorskip\n"
              b"a = pytest.importorskip('openpyxl')\nb = importorskip(\"fitz\", minversion='1')\n"
              b"c = pytest.importorskip(name)\n")
    assert importorskip_names(source) == ["openpyxl", "fitz"]


def test_every_third_party_importorskip_is_installed_by_ci():
    third_party = {}
    for relative, source in _test_sources().items():
        for name in importorskip_names(source):
            if not _first_party(name):
                third_party.setdefault(name.split(".")[0], []).append(relative)
    assert "openpyxl" in third_party, third_party  # the scan sees the spreadsheet tests
    unmapped = sorted(set(third_party) - set(IMPORTORSKIP_DISTRIBUTIONS))
    assert unmapped == [], f"map these importorskip names to their distribution: {unmapped}"
    problems, names = requirement_findings(ROOT, _ci_install_files())
    assert problems == [], problems
    installed = set().union(*names.values())
    missing = sorted(_normalise(IMPORTORSKIP_DISTRIBUTIONS[name]) for name in third_party
                     if _normalise(IMPORTORSKIP_DISTRIBUTIONS[name]) not in installed)
    assert missing == [], f"CI would skip the tests that need {missing}: add them to requirements-dev.txt"
