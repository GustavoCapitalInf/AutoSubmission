"""R-2 guard: the helper clones must not come back.

R-2 consolidated 28 money-parsing implementations, 14 date-token
implementations and 22 table/text helpers into `analysis/money.py`,
`analysis/date_tokens.py` and `analysis/tables.py`. The value of that
consolidation decays the moment someone adds parser #44 by copying its
neighbour, which is exactly how the 28 clones accumulated in the first place.

These tests fail on the copy, not on the drift it later causes:

1. no two functions anywhere in `analysis/` share a body;
2. no module outside the shared utilities re-implements money cleaning;
3. no module imports a private helper from another parser (the dependency
   inversion that made a Canadian bank parser the de-facto money library).

If a genuinely new shape appears, the fix is to extend the shared module and
its differential tests — not to add an entry here.
"""
from __future__ import annotations

import ast
import hashlib
import re
from collections import defaultdict
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"
SHARED_UTILITIES = {"money.py", "date_tokens.py", "tables.py"}

#: Trivially-short bodies (a single statement) are excluded: two parsers both
#: writing `return None` is not a clone worth reporting.
MIN_BODY_STATEMENTS = 2

#: The one remaining cross-module private import, and why it is still here.
#: `analysis/pipeline.py` imports `_parse_money` from `analysis/td_can.py`,
#: where R-2 left a one-line alias to `analysis.money.parse_money`. Removing it
#: requires editing pipeline.py, which belongs to R-3 (the dispatch seam).
#: R-3 deletes both the import and the alias; this entry goes with them.
ALLOWED_PRIVATE_IMPORTS = {
    ("pipeline.py", "td_can", "_parse_money"),
    # rbc.py reads TD Canada's month-abbreviation table. Canadian statements
    # from both banks print the same three-letter month tokens; the table is
    # data, not behaviour, and moving it is a separate cleanup.
    ("rbc.py", "td_can", "_MONTHS"),
    # Both consume TD Canada's mojibake repair. It stays in td_can.py on
    # purpose: tests/test_no_statement_hardcodes.py guards that file for raw
    # mojibake byte sequences (R-1 item 11), and moving the function would
    # move it out from under that guard.
}

#: Money cleaning belongs in analysis/money.py. This is the signature of the
#: clone family R-2 removed.
MONEY_CLEAN_RE = re.compile(r'\.replace\("\$", ""\)\s*\.replace\(",", ""\)')


def _modules():
    return sorted(p for p in ANALYSIS_DIR.glob("*.py") if p.name != "__init__.py")


def _functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_no_two_functions_in_analysis_share_a_body():
    bodies = defaultdict(list)
    for path in _modules():
        for node in _functions(path):
            statements = [s for s in node.body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)]
            if len(statements) < MIN_BODY_STATEMENTS:
                continue
            source = ast.unparse(ast.Module(body=statements, type_ignores=[]))
            bodies[hashlib.sha1(source.encode()).hexdigest()].append(f"{path.name}:{node.name}")

    clones = {digest: names for digest, names in bodies.items() if len(names) > 1}
    assert not clones, "duplicated function bodies in analysis/: " + str(list(clones.values()))


def test_money_cleaning_lives_only_in_the_shared_money_module():
    offenders = []
    for path in _modules():
        if path.name in SHARED_UTILITIES:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if MONEY_CLEAN_RE.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, (
        "money cleaning outside analysis/money.py — use parse_amount/parse_money "
        f"or add the new format there: {offenders}"
    )


def test_no_parser_imports_a_private_helper_from_another_parser():
    offenders = []
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?m)^from \.(\w+) import (.+)$", source):
            module = match.group(1)
            for name in (n.strip() for n in match.group(2).split(",")):
                if not name.startswith("_"):
                    continue
                if (path.name, module, name) in ALLOWED_PRIVATE_IMPORTS:
                    continue
                offenders.append(f"{path.name} imports {name} from .{module}")
    assert not offenders, (
        "private cross-module imports — promote the helper into a shared "
        f"module under analysis/ instead: {offenders}"
    )


def test_every_allowed_private_import_still_exists():
    """The allowlist is a debt register, not decoration: an entry that no
    longer describes the code must be deleted, or it will silently permit a
    future inversion."""
    stale = []
    for filename, module, name in ALLOWED_PRIVATE_IMPORTS:
        source = (ANALYSIS_DIR / filename).read_text(encoding="utf-8")
        if not re.search(rf"(?m)^from \.{module} import .*\b{re.escape(name)}\b", source):
            stale.append(f"{filename} no longer imports {name} from .{module}")
    assert not stale, f"remove these allowlist entries: {stale}"


def test_shared_utility_modules_do_not_import_any_parser():
    """The shared utilities are leaves. A cycle here would recreate the
    inversion in the other direction."""
    offenders = []
    for name in sorted(SHARED_UTILITIES):
        source = (ANALYSIS_DIR / name).read_text(encoding="utf-8")
        for match in re.finditer(r"(?m)^\s*from \.(\w+) import|^\s*from analysis\.(\w+) import", source):
            offenders.append(f"{name} imports .{match.group(1) or match.group(2)}")
    assert not offenders, f"shared utilities must not import other analysis modules: {offenders}"
