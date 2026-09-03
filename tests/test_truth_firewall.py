"""P22-HOLDOUT case 19: the leakage firewall.

The sealed truth store (D9, R3, R4) is invisible to every implementation and
tuning path. Checked by AST at ANY depth (a lazy import inside a function, a
string literal in a docstring, a `getenv` call in a helper all count) over
every module under the production roots; the store package itself imports
nothing from those roots; the store refuses a path inside the checkout; and
the repository digest carries no verdict, figure, kind, date or name — every
one of its lines must match a closed grammar.

The scanner lives here, in the test, in the `test_evidence_boundary.py`
idiom, and is pointed at a SCRATCH copy of a production module to prove it
can actually catch a leak (M8).
"""
from __future__ import annotations

import ast
import hashlib
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PRODUCTION_ROOTS = ("analysis", "layout", "ocr", "evidence", "discovery", "webapp", "telemetry")
#: Roots that must exist for the scan to be non-vacuous (`layout/` lands with cell C).
REQUIRED_ROOTS = ("analysis", "ocr", "evidence", "discovery", "webapp", "telemetry")

FORBIDDEN_LITERAL_FRAGMENTS = ("SEALED_TRUTH_DIR", "HOLDOUT_STORE_DIR", "tools.holdout",
                               "tools/holdout", "tools.adjudicate", "tools/adjudicate")
FORBIDDEN_IMPORT_PREFIXES = ("tools.holdout", "tools.adjudicate")
FORBIDDEN_NAMES = ("SEALED_TRUTH_DIR", "HOLDOUT_STORE_DIR")

#: What `tools/holdout` and `tools/adjudicate.py` may never import.
STORE_FORBIDDEN_PREFIXES = ("analysis", "ocr", "discovery", "webapp", "telemetry", "layout",
                            "evidence", "tests", "corpus_gate", "benchmark")

DIGEST_PATH = ROOT / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt"
KIND_WORDS = ("STATEMENT_COMPLETE", "STATEMENT_PARTIAL", "STATEMENT_ILLEGIBLE", "ACTIVITY_EXPORT",
              "NOT_A_STATEMENT", "FILE_INVALID", "KIND_UNCERTAIN")
MONEY_RE = re.compile(r"(?<![0-9A-Fa-f])\d{1,3}(?:,\d{3})*\.\d{2}(?![0-9A-Fa-f])")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")


def _findings(path: Path) -> list[str]:
    """Every way a module could reach the store, at any AST depth."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for fragment in FORBIDDEN_LITERAL_FRAGMENTS:
                if fragment in node.value:
                    found.append(f"literal {fragment!r} at line {node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    found.append(f"import {alias.name} at line {node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                found.append(f"from {module} import ... at line {node.lineno}")
            if module == "tools" and any(a.name in ("holdout", "adjudicate") for a in node.names):
                found.append(f"from tools import holdout/adjudicate at line {node.lineno}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            found.append(f"name {node.id} at line {node.lineno}")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            found.append(f"attribute .{node.attr} at line {node.lineno}")
    return found


def _modules(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                names.add(node.module)
    return names


# --- the production roots never reach the store -----------------------------


def test_the_scan_is_not_vacuous():
    for root in REQUIRED_ROOTS:
        assert (ROOT / root).is_dir(), root
        assert _modules(ROOT / root), f"{root}/ has no modules to scan"


def test_no_production_module_references_the_store():
    offenders: dict[str, list[str]] = {}
    for root in PRODUCTION_ROOTS:
        directory = ROOT / root
        if not directory.is_dir():
            continue
        for path in _modules(directory):
            found = _findings(path)
            if found:
                offenders[path.relative_to(ROOT).as_posix()] = found
    assert not offenders, f"the sealed truth store leaked into a production path: {offenders}"


@pytest.mark.parametrize(
    "injection",
    [
        'import os\n_LEAK = os.environ.get("SEALED_TRUTH_DIR")\n',
        'import os\n_LEAK = os.getenv("SEALED_TRUTH_DIR")\n',
        'def _late():\n    from tools.holdout import store\n    return store\n',
        'def _late():\n    import tools.holdout.store\n',
        'def _late():\n    from tools import adjudicate\n',
        'import importlib\n_M = importlib.import_module("tools.holdout.store")\n',
        'from os import environ\n\ndef _deep():\n    class _K:\n        def m(self):\n            return environ["SEALED_TRUTH_DIR"]\n',
        '"""A docstring that names HOLDOUT_STORE_DIR."""\n',
    ],
)
def test_a_mutant_production_module_is_caught_at_any_depth(tmp_path, injection):
    """M8: a scratch copy of `discovery/runner.py` with one injected leak."""
    source = ROOT / "discovery" / "runner.py"
    assert not _findings(source), "the real module must be clean for the mutant to be the only finding"
    scratch = tmp_path / "discovery" / "runner.py"
    scratch.parent.mkdir(parents=True)
    shutil.copy(source, scratch)
    scratch.write_text(scratch.read_text(encoding="utf-8") + "\n" + injection, encoding="utf-8")
    assert _findings(scratch), f"the firewall missed: {injection!r}"


def test_a_clean_scratch_copy_produces_no_finding(tmp_path):
    source = ROOT / "discovery" / "runner.py"
    scratch = tmp_path / "runner.py"
    shutil.copy(source, scratch)
    assert _findings(scratch) == []


# --- the store side imports nothing from production --------------------------


def test_tools_holdout_and_adjudicate_import_only_the_standard_library_and_themselves():
    offenders: dict[str, set[str]] = {}
    paths = _modules(ROOT / "tools" / "holdout") + [ROOT / "tools" / "adjudicate.py"]
    assert len(paths) >= 6
    for path in paths:
        bad = set()
        for name in _imports(path):
            top = name.split(".")[0]
            if top in sys.stdlib_module_names or top in sys.builtin_module_names:
                continue
            if name.startswith("tools.holdout"):
                continue
            if name == "fitz" and path.name == "adjudicate.py":
                continue  # PyMuPDF, lazily, for local page rendering only
            bad.add(name)
        if bad:
            offenders[path.relative_to(ROOT).as_posix()] = bad
    assert not offenders, f"tools/holdout reached outside stdlib: {offenders}"


def test_tools_holdout_never_names_a_production_root():
    offenders: dict[str, set[str]] = {}
    paths = _modules(ROOT / "tools" / "holdout") + [ROOT / "tools" / "adjudicate.py"]
    for path in paths:
        bad = {n for n in _imports(path) if n.split(".")[0] in STORE_FORBIDDEN_PREFIXES}
        if bad:
            offenders[path.relative_to(ROOT).as_posix()] = bad
    assert not offenders, offenders


def test_fitz_is_imported_lazily_inside_the_renderer_only():
    tree = ast.parse((ROOT / "tools" / "adjudicate.py").read_text(encoding="utf-8"))
    module_level = {
        alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names
    } | {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    assert "fitz" not in module_level
    sites = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Import) and any(a.name == "fitz" for a in node.names)
    ]
    assert len(sites) == 1


def test_importing_the_store_drags_no_production_module_into_the_process():
    before = {m for m in sys.modules if m.split(".")[0] in STORE_FORBIDDEN_PREFIXES}
    import tools.holdout  # noqa: F401
    import tools.holdout.store  # noqa: F401
    import tools.holdout.manifest  # noqa: F401
    import tools.holdout.digest  # noqa: F401
    import tools.holdout.evaluate  # noqa: F401
    import tools.adjudicate  # noqa: F401

    after = {m for m in sys.modules if m.split(".")[0] in STORE_FORBIDDEN_PREFIXES}
    assert after == before


# --- the store refuses the checkout -----------------------------------------


def test_the_store_refuses_a_path_inside_the_checkout(monkeypatch):
    from tools.holdout.store import StoreLocationError, TruthStore

    monkeypatch.setenv("SEALED_TRUTH_DIR", str(ROOT / "sealed_truth"))
    with pytest.raises(StoreLocationError):
        TruthStore.open()


# --- the digest carries no truth ---------------------------------------------


def _assert_digest_is_non_sensitive(text: str) -> None:
    from tools.holdout.digest import DIGEST_LINE_GRAMMAR

    lines = text.splitlines()
    assert lines, "an empty digest is not a digest"
    for line in lines:
        assert any(pattern.fullmatch(line) for pattern in DIGEST_LINE_GRAMMAR), f"unexpected line: {line!r}"
    upper = text.upper()
    for word in KIND_WORDS:
        assert word not in upper, word
    for token in ("validated", "review", "withheld", "failed", "refused", "legible"):
        assert token not in text.lower(), token
    assert not MONEY_RE.search(text), "a money shape in the digest"
    assert not DATE_RE.search(text), "a date shape in the digest"
    for sha_line in re.findall(r"^- ([0-9A-F]+)", text, flags=re.MULTILINE):
        assert len(sha_line) == 16, "only sha16 prefixes leave the store"


def test_the_committed_digest_is_non_sensitive():
    _assert_digest_is_non_sensitive(DIGEST_PATH.read_text(encoding="utf-8"))


def test_a_digest_rendered_from_a_populated_store_is_non_sensitive(tmp_path, monkeypatch):
    """M9's killer: a digest that included a kind, a figure or a date would
    fail the grammar. The committed digest is an EMPTY store's, so this test
    renders one from a populated synthetic store."""
    from tools.holdout.digest import parse_digest, render_digest
    from tools.holdout.manifest import HoldoutManifest, build_strata
    from tools.holdout.store import TruthStore

    monkeypatch.setenv("SEALED_TRUTH_DIR", str(tmp_path / "sealed"))
    store = TruthStore.open()
    manifest = HoldoutManifest.open()
    sha_a = hashlib.sha256(b"synthetic:firewall-a").hexdigest().upper()
    sha_b = hashlib.sha256(b"synthetic:firewall-b").hexdigest().upper()
    store.append_record(
        content_sha256=sha_a, kind="STATEMENT_COMPLETE", sub_kind=None, account_kind="deposit",
        modality="digital", completeness_findings=[], legible=True, account_count=1,
        printed_period_start="2031-01-01", printed_period_end="2031-01-31",
        opening_balance="100.00", closing_balance="150.25", printed_transaction_count=3,
        sampled_rows=[{"date": "2031-01-05", "description": "SYNTHETIC ROW", "amount": "-12.34"}],
        adjudicator="principal_adjudicator", packet_digest="ab" * 32, notes="a synthetic note",
    )
    manifest.add(content_sha256=sha_b, source_batch="unseen-2031-01",
                 strata=build_strata(modality="scanned", bank_familiarity="unknown_bank",
                                     account_shape="single", table_shape="summary_only",
                                     currency="CAD", page_count=2, layout_family_code="fam_b"),
                 dev_corpus_shas={sha_a})
    text = render_digest(store, manifest)
    _assert_digest_is_non_sensitive(text)
    parsed = parse_digest(text)
    assert parsed["record_count"] == 1
    assert parsed["adjudicated_sha16"] == [sha_a[:16]]
    assert parsed["holdout_sha16_status"] == [(sha_b[:16], "unseen")]
    assert parsed["chain_head"] == store.verify_chain()
    for forbidden in ("150.25", "100.00", "2031-01", "SYNTHETIC", "principal", sha_a[16:], sha_b[16:]):
        assert forbidden not in text, forbidden


def test_the_digest_grammar_rejects_a_verdict_line():
    from tools.holdout.digest import DIGEST_LINE_GRAMMAR

    for bad in ("kind: STATEMENT_COMPLETE", "- 0123456789ABCDEF STATEMENT_COMPLETE",
                "closing_balance: 150.25", "- 0123456789ABCDEF0123456789ABCDEF",
                "adjudicator: someone"):
        assert not any(p.fullmatch(bad) for p in DIGEST_LINE_GRAMMAR), bad
