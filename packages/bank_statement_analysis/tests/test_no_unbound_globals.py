"""Audit 2026-10-13, EXP-2: no function in the CLIs or the webapp reads a module-level name that nothing binds.

batch.py's `_emit` read `report` after a parameter rename had left it unbound; its blanket `except` swallowed the
NameError, so every batch telemetry record was dropped for weeks and no test noticed. No linter with an
undefined-name check runs on this tree, so this test is that check for these modules: for every function scope, each
name the compiler resolves as a global must be bound at module level (an assignment, an import, a def or a class, or a
`global` declaration that assigns it) or be a builtin. It reads the sources with `symtable` and imports nothing.
"""
from __future__ import annotations

import builtins
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / name for name in ("batch.py", "analyze.py", "parse.py", "corpus_gate.py")]
TARGETS += sorted((ROOT / "webapp").glob("*.py"))

_IMPLICIT = {"__file__", "__name__", "__doc__", "__spec__", "__builtins__", "__package__", "__loader__", "__path__",
             "__annotations__", "__dict__", "__module__", "__qualname__"}


def _bound_at_module_level(top: symtable.SymbolTable) -> set[str]:
    bound = {symbol.get_name() for symbol in top.get_symbols()
             if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()}

    def declared(table: symtable.SymbolTable) -> None:
        for symbol in table.get_symbols():
            if symbol.is_declared_global() and symbol.is_assigned():
                bound.add(symbol.get_name())
        for child in table.get_children():
            declared(child)

    declared(top)
    return bound


def unbound_global_reads(path: Path) -> list[tuple[str, int, str]]:
    top = symtable.symtable(path.read_text(encoding="utf-8"), str(path), "exec")
    known = _bound_at_module_level(top) | set(dir(builtins)) | _IMPLICIT
    found: list[tuple[str, int, str]] = []

    def walk(table: symtable.SymbolTable) -> None:
        if table.get_type() != "module":  # a str, or a StrEnum member since Python 3.13
            for symbol in table.get_symbols():
                if symbol.is_global() and symbol.is_referenced() and symbol.get_name() not in known:
                    found.append((table.get_name(), table.get_lineno(), symbol.get_name()))
        for child in table.get_children():
            walk(child)

    walk(top)
    return found


def test_the_cli_and_webapp_modules_read_no_unbound_global():
    assert len(TARGETS) > 4
    hits = {path.relative_to(ROOT).as_posix(): unbound_global_reads(path) for path in TARGETS}
    assert {name: found for name, found in hits.items() if found} == {}


def test_the_check_sees_an_unbound_read(tmp_path):
    """The check itself: a function reading a name nothing binds is reported; a bound one, a builtin and a local are
    not."""
    source = tmp_path / "sample.py"
    source.write_text(
        "import os\n"
        "LIMIT = 3\n"
        "def emit(document=None):\n"
        "    local = len(os.sep) + LIMIT\n"
        "    return bool(report.escalated) if report is not None else local\n",
        encoding="utf-8",
    )
    assert unbound_global_reads(source) == [("emit", 3, "report")]
