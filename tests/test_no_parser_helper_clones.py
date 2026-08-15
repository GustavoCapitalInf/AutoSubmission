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

#: Cross-module private imports that survive, and why. R-3 removed the
#: pipeline -> td_can `_parse_money` entry along with the dispatch seam.
ALLOWED_PRIVATE_IMPORTS = {
    # rbc.py reads TD Canada's month-abbreviation table. Canadian statements
    # from both banks print the same three-letter month tokens; the table is
    # data, not behaviour, and moving it is a separate cleanup.
    ("rbc.py", "td_can", "_MONTHS"),
    # Both consume TD Canada's mojibake repair. It stays in td_can.py on
    # purpose: tests/test_no_statement_hardcodes.py guards that file for raw
    # mojibake byte sequences (R-1 item 11), and moving the function would
    # move it out from under that guard.
    #
    # td_canada_french.py reads the same printed grid as td_can's native path,
    # localized (W3 §TD-FRENCH). Both recover the direction of a row from the
    # balance the bank prints at the end of each date group, and that is one
    # piece of arithmetic over one layout, not two: copying it would fail
    # `test_no_two_functions_in_analysis_share_a_body` above, and re-deriving
    # it differently would put two answers to the same question in the tree.
    # The import is deliberately the narrow one — the solver and its
    # equal-amount tie-break, nothing else. Promoting the pair into a shared
    # module is the right end state and is a separate cleanup: td_can.py is
    # owned by another cell this cycle.
    ("td_canada_french.py", "td_can", "_credit_counts_from_balances"),
    ("td_canada_french.py", "td_can", "_directions_from_credit_counts"),
}

#: Money cleaning belongs in analysis/money.py. This is the signature of the
#: clone family R-2 removed.
MONEY_CLEAN_RE = re.compile(r'\.replace\("\$", ""\)\s*\.replace\(",", ""\)')

#: U+2212 MINUS SIGN — the sentinel of a privately-spelled SIGN class.
#:
#: This one codepoint is the right detector and the en/em dashes are not,
#: because U+2212 has no punctuation reading at all: it is not a range dash,
#: not a hyphen and not a bullet, and Unicode names it MINUS SIGN. A module
#: that carries it is claiming to know what a minus is, which is a claim only
#: `analysis/money.py` may make — the sign class decides the DIRECTION of
#: money, and a second copy of it drifts silently and inverts amounts when it
#: does. `analysis/wealthsimple.py` carried exactly such a copy, and it had
#: drifted to admit U+2014 EM DASH, which the canon rules out on the archive's
#: own evidence (W3 §MGD).
#:
#: A dash class for a DATE RANGE is a different thing with the opposite risk
#: profile and is deliberately wider; it lives at `date_tokens.PERIOD_DASH`
#: and is exempt here because it is a shared utility.
MINUS_SIGN_CODEPOINT = "−"

#: How long a string may be before it stops being a sign class. Every real one
#: has been a handful of glyphs (`"–−—-"`) or a short pattern that interpolates
#: them (`"[-−–+]?\\s?\\$[\\d,]+\\.\\d{2}"`, 26 characters); nothing above this
#: is a class, and the module that keeps paragraph-length provenance notes as
#: string DATA needs the room.
SIGN_CLASS_MAX_CHARS = 60


def _rel(path: Path) -> str:
    """`structurer/tokens.py`, not `tokens.py` — the scan is recursive now, so
    a bare filename would name the wrong file for six of the 89 modules."""
    return path.relative_to(ANALYSIS_DIR).as_posix()


def _modules():
    """Every module under `analysis/`, RECURSIVELY.

    It was `glob` until W3 §MGD, which is to say it silently stopped at the
    directory's own level and never saw `analysis/structurer/`'s six modules —
    including `structurer/tokens.py`, a GENERIC money reader on the
    unclaimed-layout path. Four guards in this file were reading a scope
    narrower than the one their names claim.

    Widening it costs nothing measurable: 83 modules become 89, there are no
    basename collisions (so the allowlist's `ANALYSIS_DIR / filename` lookups
    are unaffected), and all four guards pass over the wider set with no new
    exemptions.
    """
    return sorted(p for p in ANALYSIS_DIR.rglob("*.py") if p.name != "__init__.py")


def _functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _code_strings(path: Path):
    """(value, lineno) for every string CONSTANT that is not a docstring.

    Comments never reach the AST at all, and docstrings are excluded by
    identity, so what remains is the strings the module can compile, compare
    or embed — the only place a constant can affect a reading.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            yield node.value, node.lineno


def test_no_two_functions_in_analysis_share_a_body():
    bodies = defaultdict(list)
    for path in _modules():
        for node in _functions(path):
            statements = [s for s in node.body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)]
            if len(statements) < MIN_BODY_STATEMENTS:
                continue
            source = ast.unparse(ast.Module(body=statements, type_ignores=[]))
            bodies[hashlib.sha1(source.encode()).hexdigest()].append(f"{_rel(path)}:{node.name}")

    clones = {digest: names for digest, names in bodies.items() if len(names) > 1}
    assert not clones, "duplicated function bodies in analysis/: " + str(list(clones.values()))


def test_money_cleaning_lives_only_in_the_shared_money_module():
    offenders = []
    for path in _modules():
        if path.name in SHARED_UTILITIES:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if MONEY_CLEAN_RE.search(line):
                offenders.append(f"{_rel(path)}:{number}: {line.strip()}")
    assert not offenders, (
        "money cleaning outside analysis/money.py — use parse_amount/parse_money "
        f"or add the new format there: {offenders}"
    )


def test_the_minus_sign_class_lives_only_in_the_shared_money_module():
    """No parser spells its own sign class.

    The clone guards above catch a copied FUNCTION; this catches a copied
    CONSTANT, which is the shape money drift actually takes — a four-character
    string in a parser, agreeing with the shared class on the day it is written
    and diverging the first time the shared one is narrowed. Two such copies
    existed: a second `MINUS_GLYPHS` inside `money.py` itself, and
    `wealthsimple._SIGN_GLYPHS`. Both had drifted the same way, and neither was
    visible to any test until a document printed the glyph they disagreed on.

    The allowlist is empty on purpose, and stays empty over the RECURSIVE
    scan — `analysis/structurer/`'s six modules carry no U+2212 either. If a
    layout genuinely prints a sign glyph the canon lacks, the fix is to attest
    it and add it there — once.

    WHAT THIS GUARD CANNOT DO, stated because the gap is not obvious and two
    real defects live in it: it detects the PRESENCE of a private sign class,
    so it is structurally blind to a reader whose bug is the ABSENCE of one.
    `structurer/tokens.py::money_value` and `regions.py:40` each handle ASCII
    and U+2013 and miss U+2212 — `tokens.py` goes further and `abs()`-es away
    the sign the shared grammar had already recovered, so `money_value` of a
    U+2212 or U+2013 amount is POSITIVE where `parse_money` is negative. No
    presence-guard can see that; only a differential against the shared
    grammar can, and that is a reader-by-reader job. Both are carried at
    W3 §MGD MGD10, `tokens.py` first.

    Prose is not code, and the test says so twice. The glyph is read out of the
    AST's string CONSTANTS with docstrings excluded, so a comment or a
    docstring that sets a minus typographically (`charges − waivers`, four of
    which exist today) is not an offence; and a constant longer than
    `SIGN_CLASS_MAX_CHARS` is not a class either — `count_semantics.py` stores
    paragraph-length provenance notes as DATA rather than as docstrings, and
    two of them describe a count disagreement as `credit −n, debit +n`. What
    is left is a short literal a parser can compile, embed or compare, which
    is the only shape a privately-spelled sign class has ever taken.
    """
    offenders = []
    for path in _modules():
        if path.name in SHARED_UTILITIES:
            continue
        for node, line in _code_strings(path):
            if MINUS_SIGN_CODEPOINT in node and len(node) <= SIGN_CLASS_MAX_CHARS:
                offenders.append(f"{_rel(path)}:{line}: {node!r}")
    assert not offenders, (
        "U+2212 MINUS SIGN outside the shared money grammar — import "
        f"money.MINUS_GLYPHS / money.MINUS_CLASS instead: {offenders}"
    )


def test_the_minus_sign_guard_fires_on_the_copy_it_was_written_for(tmp_path):
    """A guard that has never been seen to fail is a guard nobody has tested.
    Both real offender shapes are replayed here — the private glyph string
    `wealthsimple` carried, and the inline interpolated pattern a parser would
    write instead — alongside the three shapes that must NOT trip it: a
    docstring, a comment, and a paragraph of provenance prose held as data.

    Scope note: `_modules()` is now `analysis/**/*.py`. `ocr/column_grid.py`
    carries another private opinion about dash glyphs and is outside this scan
    by the same boundary every other guard in this file uses (W3 §MGD MGD10)."""
    module = tmp_path / "fake_parser.py"
    module.write_text(
        '"""A docstring may say charges − waivers freely."""\n'
        '# and so may a comment: −12.00\n'
        'PROSE = "a provenance note long enough to be prose, disagreeing by '
        'credit −n and debit +n, which is data and not a class"\n'
        'SIGN_GLYPHS = "–−—-"\n'
        'PATTERN = r"[-−–+]?\\s?\\$[\\d,]+\\.\\d{2}"\n',
        encoding="utf-8",
    )
    caught = [
        value for value, _ in _code_strings(module)
        if MINUS_SIGN_CODEPOINT in value and len(value) <= SIGN_CLASS_MAX_CHARS
    ]
    assert caught == ["–−—-", r"[-−–+]?\s?\$[\d,]+\.\d{2}"]


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
                offenders.append(f"{_rel(path)} imports {name} from .{module}")
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
