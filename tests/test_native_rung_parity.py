"""Every copy of the native-text rung ladder is the same ladder.

Six modules hold a `_native_statement` (the production `ocr/pipeline.py` plus
five oracle/cache consumers). Batch 4 caught them drifting: GEOM-1 wired
`parse_native_woodforest` into the production ladder while the five oracle
copies still lacked it — which would have made the forensic oracles read
Woodforest documents with the generic rung while production used geometry.
An oracle that reads different bytes than production is not an oracle.

This guard extracts each copy's ordered rung-call list by AST and asserts
they are all identical to the production ladder, so the seventh copy — or
the next new rung — cannot drift silently. (The genuinely right fix is one
shared ladder; that is the RUNG-SEAM card. Until it lands, this pin holds.)
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: module -> the function holding its copy of the ladder. Production first.
LADDER_MODULES = {
    "ocr/pipeline.py": "_native_statement",
    "adb_debug.py": "_native_statement",
    "adb_forensic_audit.py": "native_statement",
    "balance_forensic_audit.py": "native_document",
    "build_corpus_cache.py": "native_document",
    "deterministic_coverage_audit.py": "native_statement",
}


def _ladder(path: Path, func: str) -> list[str]:
    """The ordered parse_native_* call names inside the ladder function."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            return [
                n.func.id
                for n in ast.walk(node)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id.startswith("parse_native_")
            ]
    raise AssertionError(f"{path} has no {func}")


def test_every_native_rung_copy_is_the_production_ladder():
    ladders = {m: _ladder(REPO / m, f) for m, f in LADDER_MODULES.items()}
    production = ladders["ocr/pipeline.py"]
    assert production, "production ladder is empty?"
    drifted = {m: l for m, l in ladders.items() if l != production}
    assert not drifted, (
        f"native rung copies drifted from ocr/pipeline.py {production}: {drifted}"
    )


def test_the_ladder_module_list_is_itself_complete():
    """A NEW module composing the rung ladder must be added to LADDER_MODULES.

    Keyed on the ladder's tail call (every copy ends in the generic rung), so
    a copy under any function name is found."""
    holders = []
    for path in REPO.rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith((".claude/", "tests/")) or "site-packages" in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if ("or parse_native_pdf_text(" in text and "def parse_native_pdf_text" not in text):
            holders.append(rel)
    assert sorted(holders) == sorted(LADDER_MODULES), (
        "modules holding a _native_statement copy changed; update LADDER_MODULES "
        f"and wire the ladder: {sorted(holders)}"
    )
