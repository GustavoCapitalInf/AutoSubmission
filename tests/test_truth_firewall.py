"""P22-HOLDOUT case 19: the leakage firewall.

The sealed truth store (D9, R3, R4) is invisible to every implementation and
tuning path. This is a STATIC literal / name / import tripwire, checked by
AST at ANY depth (a lazy import inside a function, a string constant in a
docstring, an env access in a helper three scopes deep all count) over every
module under the production roots.

What it sees: a string or bytes constant containing the variable name, the
store package or the CLI module (including one assembled from adjacent
literals, `+`-concatenation of constants, a constant f-string, `"_".join` of
constant parts, `.upper()`/`.lower()`/`.replace()` of a constant, and a
reversed constant slice); `import` / `from … import` of `tools.holdout*` or
`tools.adjudicate`; a `Name` or `Attribute` called `SEALED_TRUTH_DIR` /
`HOLDOUT_STORE_DIR`; and any `os.environ` / `getenv` access whose (folded)
key names SEALED, TRUTH or HOLDOUT — a second variable carrying the store
path under such a name is caught by that rule.

What it cannot see (named honestly; review MINOR-6): a name built at run
time from parts it cannot fold (a base64 or other encoded literal, a value
read from a file, a variable), a second environment variable whose name says
nothing (`DATA_ROOT`), a pointer file, `__import__` / `importlib` with a
built name, a hard-coded absolute path to the store, a walk over
`os.environ`, or `exec` of a built statement. Those are side channels only
review and the "no reading of the store from production" convention (the
W3's MINOR-4 note) cover; the firewall pins the literal surface.

The store package itself imports nothing from those roots; the store refuses
a path inside the checkout; and the repository digest carries no verdict,
figure, kind, date or name — every one of its lines must match a closed
grammar. The scanner lives here, in the test, in the `test_evidence_boundary.py`
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

PRODUCTION_ROOTS = ("analysis", "layout", "ocr", "evidence", "discovery", "webapp", "telemetry", "vlm")
#: Roots that must exist for the scan to be non-vacuous (`layout/` lands with cell C).
REQUIRED_ROOTS = ("analysis", "ocr", "evidence", "discovery", "webapp", "telemetry", "vlm")

FORBIDDEN_LITERAL_FRAGMENTS = ("SEALED_TRUTH_DIR", "HOLDOUT_STORE_DIR", "tools.holdout",
                               "tools/holdout", "tools.adjudicate", "tools/adjudicate")
FORBIDDEN_IMPORT_PREFIXES = ("tools.holdout", "tools.adjudicate")
FORBIDDEN_NAMES = ("SEALED_TRUTH_DIR", "HOLDOUT_STORE_DIR")
#: An environment key naming any of these is a store reference, whatever the variable is called.
ENV_KEY_TOKENS = ("SEALED", "TRUTH", "HOLDOUT")
_ENV_GETTERS = ("get", "getenv")

#: What `tools/holdout` and `tools/adjudicate.py` may never import.
STORE_FORBIDDEN_PREFIXES = ("analysis", "ocr", "discovery", "webapp", "telemetry", "layout",
                            "evidence", "tests", "corpus_gate", "benchmark")

DIGEST_PATH = ROOT / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt"
KIND_WORDS = ("STATEMENT_COMPLETE", "STATEMENT_PARTIAL", "STATEMENT_ILLEGIBLE", "ACTIVITY_EXPORT",
              "NOT_A_STATEMENT", "FILE_INVALID", "KIND_UNCERTAIN")
MONEY_RE = re.compile(r"(?<![0-9A-Fa-f])\d{1,3}(?:,\d{3})*\.\d{2}(?![0-9A-Fa-f])")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")


def _int_const(node) -> int | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _int_const(node.operand)
        return None if inner is None else -inner
    return None


def _folded(node) -> str | None:
    """The string a node evaluates to when it is built from constants only."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        if isinstance(node.value, bytes):
            return node.value.decode("utf-8", "replace")
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _folded(node.left), _folded(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            inner = _folded(value.value if isinstance(value, ast.FormattedValue) else value)
            if inner is None:
                return None
            parts.append(inner)
        return "".join(parts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        base = _folded(node.func.value)
        if base is None:
            return None
        method = node.func.attr
        if method == "join" and len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple)):
            items = [_folded(element) for element in node.args[0].elts]
            return None if any(item is None for item in items) else base.join(items)
        if method in ("upper", "lower", "strip", "casefold", "swapcase", "title") and not node.args:
            return getattr(base, method)()
        if method == "replace" and len(node.args) == 2:
            old, new = _folded(node.args[0]), _folded(node.args[1])
            return None if old is None or new is None else base.replace(old, new)
        return None
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        base = _folded(node.value)
        if base is None:
            return None
        bounds = [_int_const(part) if part is not None else None
                  for part in (node.slice.lower, node.slice.upper, node.slice.step)]
        if any(part is not None and bound is None
               for part, bound in zip((node.slice.lower, node.slice.upper, node.slice.step), bounds)):
            return None
        return base[bounds[0]:bounds[1]:bounds[2]]
    return None


def _env_key(node) -> str | None:
    """The folded key of an `os.environ[...]` / `os.environ.get(...)` / `os.getenv(...)` access."""
    if isinstance(node, ast.Subscript):
        target = node.value
        if (isinstance(target, ast.Attribute) and target.attr == "environ") or \
                (isinstance(target, ast.Name) and target.id == "environ"):
            return _folded(node.slice)
        return None
    if isinstance(node, ast.Call):
        func = node.func
        is_getter = (
            (isinstance(func, ast.Attribute) and func.attr in _ENV_GETTERS and (
                (isinstance(func.value, ast.Attribute) and func.value.attr == "environ")
                or (isinstance(func.value, ast.Name) and func.value.id in ("environ", "os"))))
            or (isinstance(func, ast.Name) and func.id == "getenv")
        )
        if is_getter and node.args:
            return _folded(node.args[0])
    return None


def _findings(path: Path) -> list[str]:
    """Every literal, name, import or env-key reference to the store at any depth."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    seen: set[tuple] = set()

    def record(kind: str, what: str, line: int) -> None:
        key = (kind, what, line)
        if key not in seen:
            seen.add(key)
            found.append(f"{kind} {what!r} at line {line}")

    for node in ast.walk(tree):
        text = _folded(node)
        if text is not None:
            lowered = text.lower()
            for fragment in FORBIDDEN_LITERAL_FRAGMENTS:
                if fragment.lower() in lowered:
                    record("literal", fragment, getattr(node, "lineno", 0))
        key = _env_key(node)
        if key is not None and any(token in key.upper() for token in ENV_KEY_TOKENS):
            record("environment key", key, getattr(node, "lineno", 0))
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    record("import", alias.name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                record("from-import", module, node.lineno)
            if module == "tools" and any(a.name in ("holdout", "adjudicate") for a in node.names):
                record("from-import", "tools.holdout/adjudicate", node.lineno)
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            record("name", node.id, node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            record("attribute", node.attr, node.lineno)
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


INJECTIONS = [
    'import os\n_LEAK = os.environ.get("SEALED_TRUTH_DIR")\n',
    'import os\n_LEAK = os.getenv("SEALED_TRUTH_DIR")\n',
    'def _late():\n    from tools.holdout import store\n    return store\n',
    'def _late():\n    import tools.holdout.store\n',
    'def _late():\n    from tools import adjudicate\n',
    'import importlib\n_M = importlib.import_module("tools.holdout.store")\n',
    'from os import environ\n\ndef _deep():\n    class _K:\n        def m(self):\n            return environ["SEALED_TRUTH_DIR"]\n',
    '"""A docstring that names HOLDOUT_STORE_DIR."""\n',
    # MINOR-6: the shapes the folding pass sees
    'import os\n_LEAK = os.environ.get("SEALED_" + "TRUTH_DIR")\n',
    'import os\n_LEAK = os.environ.get("_".join(["SEALED", "TRUTH", "DIR"]))\n',
    'import os\n_LEAK = os.environ.get(f"SEALED_TRUTH_{\'DIR\'}")\n',
    'import os\n_LEAK = os.environ.get("sealed_truth_dir".upper())\n',
    'import os\n_LEAK = os.environ.get("RID_HTURT_DELAES"[::-1])\n',
    'import os\n_LEAK = os.environ.get("MY_TRUTH_STORE_PATH")\n',
    'import os\n_LEAK = os.environ["HOLDOUT_ROOT"]\n',
    '_NAME = b"SEALED_TRUTH_DIR"\n',
    '_MOD = "tools" "." "holdout"\n',
]


@pytest.mark.parametrize("injection", INJECTIONS)
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


NOT_SEEN = [
    'import base64, os\n_LEAK = os.environ.get(base64.b64decode("U0VBTEVEX1RSVVRIX0RJUg==").decode())\n',
    'import os\n_LEAK = os.environ.get("DATA_ROOT")\n',
    '_P = "C:/somewhere/truth.jsonl"\n',
]


@pytest.mark.parametrize("injection", NOT_SEEN)
def test_the_firewall_names_its_limits_truthfully(tmp_path, injection):
    """The docstring's 'cannot see' list must stay true: these shapes are NOT
    findings, so nobody mistakes the tripwire for a dynamic analysis."""
    scratch = tmp_path / "runner.py"
    scratch.write_text("x = 1\n" + injection, encoding="utf-8")
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


def _dev_corpus(tmp_path, *shas):
    import csv

    from tools.holdout.manifest import dev_corpus_from_rows

    path = tmp_path / "dev_rows.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "content_sha256", "outcome_class"])
        writer.writeheader()
        for sha in shas:
            writer.writerow({"relative_path": f"synthetic/{sha[:8]}.pdf", "content_sha256": sha,
                             "outcome_class": "validated"})
    return dev_corpus_from_rows(path)


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
                 dev_corpus=_dev_corpus(tmp_path, sha_a))
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
