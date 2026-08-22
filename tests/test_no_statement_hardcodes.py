"""R-1 guard: statement-specific constants must never return to the parsers.

Scans the parser layer for (a) the exact literals removed by R-1 and (b)
forbidden pattern classes: literal 4-digit years outside date-parsing context,
long literal account-number digit runs, exact-cent amount constants, literal
calendar fields pinned into a pattern, and raw mojibake byte sequences. Test
fixtures may contain such strings (they represent documents); production
parser code may not.

Why some scans are layer-wide and some are not
----------------------------------------------
R-4b established that scoping a scan to a remembered list of files is itself
the defect: a customer name was found in `farmers_merchants.py` precisely
because that file was never on the list, and the literal scan was widened to
the whole layer in response. That lesson was never carried across to the
pattern-class scans, which stayed bound to :data:`GUARDED_FILES` — and
`analysis/first_citizens.py` then carried four memorized section totals
(`55049.85`, `44862.06`, `9800.18`, `74263.31`) and two memorized section
terminators for as long as it existed. `AMOUNT_RE` matches every one of them.
The scan simply never looked at that file.

The year, amount and calendar scans are therefore layer-wide as of this
change; their blast radius was measured first and is recorded in
:data:`PATTERN_SCAN_EXEMPT` and :data:`CALENDAR_BASELINE`. The account-number
and mojibake scans remain list-scoped for now: widening them lights up six
modules owned by other cells (`consumers.py`, `ibc.py`, `cibc.py`,
`columbia_bank.py`, `navigant.py`, `truist.py`), and turning another cell's
work red mid-wave is not this guard's call to make. That backlog is named
here so it is visible rather than forgotten.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"

GUARDED_FILES = (
    "scanned_small_bank.py",
    "community_section.py",
    "bank_repairs.py",
    "rbc.py",
    "td_can.py",
    "wells.py",
    "wilson_muir.py",
)

#: The exact statement-specific literals R-1 removed. Reintroducing any of
#: them (any casing) fails this test. Maintain this list when new hardcodes
#: are purged.
REMOVED_LITERALS = (
    "GRANITE GIRLS",          # item 2 - customer name
    "KLR ENTERPRISES",        # item 2 - customer name
    "GREEN CONVERGENCE",      # item 4 - customer name
    "FIELD TRUCKING",         # item 4 - customer name
    "35127380",               # item 5 - account number
    "2026-06-18",             # item 1 - memorized date
    "Check 1944",             # item 1 - memorized check
    "4500.00",                # item 1 - memorized amount
    "FUNDIFI CANADA",         # item 7 - counterparty in sign heuristic
    "2313833 ONTARIO",        # item 7 - counterparty in sign heuristic
    "DANNY",                  # item 8 - merchant sign list
    "PIZZ",                   # item 8 - merchant sign list
    "PHO ",                   # item 8 - merchant sign list
    "FRESHCO",                # item 8 - merchant sign list
    "CASH 4 YOU",             # item 8 - merchant sign list
    "CANACAP CLN",            # item 8 - merchant sign list
    "LIGHTSPEED",             # item 8 - merchant sign list
    "PRODIGY",                # item 8 - merchant sign list
    "ACE AUTO GLASS",         # R-4b - customer name used as detection evidence
    "BUILDER ACCOUNT",        # R-4b - customer's ACCOUNT TITLE as detection evidence
)

#: Literal years (2010-2039) appearing as code constants. Century pivots
#: ("year += 2000" / "2000 +") are date-parsing arithmetic, not memorized
#: years; unicode escape literals ("u20ac"-style) are not years; and
#: comments/docstrings may describe history.
#: `classification_registry.py` names counterparties on purpose - that is what
#: a counterparty registry is. Every other module in the layer is scanned.
LITERAL_SCAN_EXEMPT = {"classification_registry.py"}

YEAR_RE = re.compile(r"(?<![\d.])(?<!u)20[123]\d(?![\d.])")
#: Long literal digit runs (account-number shaped) as code constants.
ACCOUNT_RE = re.compile(r"(?<![\d.])\d{6,}(?![\d.])")
#: Exact-cent amount constants of one dollar or more (tolerances like 0.01
#: stay allowed).
AMOUNT_RE = re.compile(r"(?<![\d.])\d+\.\d{2}(?![\d.])")
#: Raw mojibake byte sequences; only escape literals are acceptable.
MOJIBAKE_RE = re.compile("[ÃÂ]|â€")

#: A literal calendar field welded into a pattern: two digits, optionally
#: parenthesised as a capture group, sitting immediately before a regex
#: whitespace or date separator. This is the class no other rule could see —
#: a bare `03` is too short for `ACCOUNT_RE`, carries no decimal for
#: `AMOUNT_RE`, and is not a year — and it is what let
#: `analysis/first_citizens.py` pin the statement MONTH into two row regexes
#: (`r"03\s+([\d,]+\.\d{2})([+-])"` and `r"\b(03)\s+(\d[\d,]*\.\d{2})"`), so
#: the parser could only ever read a March statement. A quantifier such as
#: `\d{2}` is a single digit between braces and does not match; a two-digit
#: run inside a longer number does not match either.
CALENDAR_RE = re.compile(r"(?<![\d\\])\(?(\d{2})\)?(?=\\s|\\-|-|/)")

#: Modules the amount scan does not apply to: the deterministic math layer,
#: where an exact-cent constant is a TOLERANCE (`1.00`, `0.98`, `1.02`) rather
#: than a figure copied off a statement. Verified by reading every match in
#: each file at the time this exemption was written. No parser is exempt.
#:
#: `extract.py` joins them at G7.3 (W3 §PRIVACY3) and the entry is a DISCLOSURE,
#: not a shrug. Closing `_code_lines`'s triple-quote hole made exactly one
#: module newly visible to this scan — measured across the whole parser layer,
#: no other module gains an offender — and its four hits are all inside
#: `_INSTRUCTIONS`, the LLM prompt: a worked example teaching the model to align
#: a label column against a value column (`78.68- / 7,329.22 / 3,945.12 / …`,
#: lines 70-74) plus a description example at line 79.
#:
#: Exempt rather than fixed, for three measured reasons. `extract.py` is the
#: LLM branch, not a parser: it holds no regex, no reader, no parse gate and no
#: registration, so a constant in it cannot make anything read one statement —
#: the same property that puts `metrics`/`pipeline`/`reconcile` on this list.
#: The two distinctive values (`7,329.22`, `3,945.12`) appear in no committed
#: expectation and in neither audit CSV, so the example is illustrative rather
#: than copied off a pinned document. And editing a prompt changes what a model
#: does, which is a measurement this card does not carry.
#:
#: CARRIED, and the sharper half: line 79's example is
#: `"PREM PMT BCBS OF AL 32.00"` — a real-looking insurer name in the parser
#: layer, which is the class R-1 purged. Named for whoever owns
#: `analysis/extract.py` next; not this cell's file and not a scan this list
#: covers.
PATTERN_SCAN_EXEMPT = {"metrics.py", "pipeline.py", "reconcile.py", "extract.py"}

#: Modules already flagged by this scan when it was written. A ratchet, not a
#: pardon: nothing new may be added, and the entry shrinks as its owner clears.
#:
#: `first_community.py` produces exactly two hits, and only ONE of them is a
#: calendar literal — stated precisely because a baseline that misdescribes
#: what it excuses is worse than no baseline:
#:
#:   1. `10/31 Ending Balance` (line 37) — a memorized POSTING DATE used as a
#:      section boundary. Genuine, and the class this rule exists for.
#:   2. `(\d+-70)` (line 28) — the `70` is a PRODUCT-CODE SUFFIX, not a date.
#:      A false positive of this rule. It is arguably a statement-specific
#:      literal of a different class, but it is not what CALENDAR_RE claims to
#:      find, and it is the reason the rule cannot yet be tightened to
#:      zero-false-positive.
#:
#: Note what the scan does NOT see in that same string: the `--- Page 12 ---`
#: page marker beside hit 2 is invisible to it, because the `12` is followed by
#: a space rather than a regex date separator. The rule finds pinned calendar
#: FIELDS inside patterns, not every memorized number.
CALENDAR_BASELINE = {"first_community.py"}


def _code_lines(path: Path):
    """Source lines with comments and docstrings stripped.

    Docstrings are blanked IN PLACE, character for character, so the numbers
    reported to a failing developer are the numbers in the file. (An earlier
    revision collapsed each one to `""`, which shifted every subsequent line
    number by the length of the docstring above it and made offender reports
    point at the wrong code.)

    G7.3, the second half. The previous implementation matched a triple-quote
    delimiter with a regex; this one is an AST walk over the four positions the
    language calls a docstring. The regex was wrong in the direction that HIDES:
    it
    blanked every triple-quoted string, docstring or not, so a module constant
    written with triple quotes was invisible to the year, amount and
    account-number scans below. Measured on the tree that carried the fix: two
    such strings exist in the parser layer, and one of them
    (`analysis/extract.py`'s LLM prompt) carries exact-cent amounts the amount
    scan is built to find — see `PATTERN_SCAN_EXEMPT`.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    for node in _docstring_nodes(tree):
        for row in range(node.lineno - 1, node.end_lineno):
            line = lines[row]
            start = node.col_offset if row == node.lineno - 1 else 0
            stop = node.end_col_offset if row == node.end_lineno - 1 else len(line)
            lines[row] = line[:start] + " " * (stop - start) + line[stop:]
    for number, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0]
        if line.strip():
            yield number, line


def _parser_modules() -> list[Path]:
    """Every module in the parser layer the pattern scans apply to."""
    return [
        path
        for path in sorted(ANALYSIS_DIR.glob("*.py"))
        if path.name not in LITERAL_SCAN_EXEMPT
    ]


def _docstring_nodes(tree: ast.AST):
    """Every DOCSTRING constant node in `tree`, in no particular order.

    A docstring is the first statement of a Module, ClassDef, FunctionDef or
    AsyncFunctionDef and nothing else. Recognised by POSITION rather than by
    delimiter, which is the whole point of G7.3: a triple-quoted string
    assigned to a name, passed to a call, or sitting in a list is a value the
    module can compile, compare or embed, and it stays scanned.
    """
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            yield body[0].value


def _docstring_ids(tree: ast.AST) -> set[int]:
    """`_docstring_nodes` by identity, for the callers that only need a
    membership test. One walk, not two (review MINOR-4).

    `tests/test_no_parser_helper_clones.py::_code_strings` has excluded
    docstrings this way since R-2; this file did not, and G7.3 is that gap.
    """
    return {id(node) for node in _docstring_nodes(tree)}


def _pattern_strings(path: Path):
    """Every string constant a module can COMPILE, with its real line number.

    Docstrings are excluded and comments never reach the AST at all (G7.3, W3
    §GRAM4 G7.3 / §LCPERIOD L5.1). The scans below hunt for pinned calendar
    fields inside PATTERNS; a docstring that quotes a real printed row beside a
    regex escape — which is what evidence for a boundary rule looks like — is
    not a pattern, and two cells in a row had to reword prose to get past a
    guard that could not tell the difference. Both directions matter and the
    second is the dangerous one: a scan that reads docstrings can also be
    SATISFIED by one, so a module whose only calendar literal moved into a
    docstring would keep its `CALENDAR_BASELINE` entry alive on evidence that
    no longer describes any code.

    Narrow on purpose. The regex-based blanking in `_code_lines` removes every
    triple-quoted string, docstring or not; this walk removes only the four
    positions the language calls a docstring, so a `re.VERBOSE` pattern written
    with triple quotes is still scanned here.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_ids(tree)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            yield node.lineno, node.value


def test_removed_literals_stay_removed_anywhere_in_analysis():
    """The literal scan covers EVERY analysis module, not just the seven R-1
    touched.

    R-4b found a customer name (`ACE AUTO GLASS`) sitting in
    `analysis/farmers_merchants.py`'s detection guard — a violation of R-1's
    zero-customer-names rule that its file-scoped scan could not see, because
    that file was never on the list. A customer name has no business anywhere
    in the parser layer, so the scan is now scoped to the layer rather than to
    a list someone has to remember to extend.

    W3 §SCANFINISH added the second entry of that class, `BUILDER ACCOUNT` —
    which is not a product line but the TITLE one Southside customer gave one
    of its accounts, and which `analysis/scanned_small_bank.py` required before
    it would recognise the issuer. The class is wider than "a company name":
    anything the CUSTOMER wrote, an account title included, is the customer's
    words and cannot be the issuer's evidence. It claimed three of that
    issuer's nine archive statements and hid the other six.
    """
    offenders = []
    for path in sorted(ANALYSIS_DIR.glob("*.py")):
        if path.name in LITERAL_SCAN_EXEMPT:
            continue
        source = path.read_text(encoding="utf-8").upper()
        for literal in REMOVED_LITERALS:
            if literal.upper() in source:
                offenders.append(f"{path.name}: {literal}")
    assert not offenders, f"statement-specific literals in analysis/: {offenders}"


@pytest.mark.parametrize("filename", GUARDED_FILES)
def test_removed_literals_stay_removed(filename):
    source = (ANALYSIS_DIR / filename).read_text(encoding="utf-8").upper()
    hits = [literal for literal in REMOVED_LITERALS if literal.upper() in source]
    assert not hits, f"{filename} reintroduces statement-specific literals: {hits}"


def test_no_literal_years_outside_date_parsing():
    """Layer-wide. Measured blast radius when this was widened: zero."""
    offenders = []
    for path in _parser_modules():
        for number, line in _code_lines(path):
            if not YEAR_RE.search(line):
                continue
            if "2000 +" in line or "+= 2000" in line or "+ 2000" in line:
                continue
            offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, f"literal year constants: {offenders}"


def test_no_exact_amount_constants_anywhere_in_analysis():
    """Layer-wide, and the scan that would have caught `first_citizens.py`.

    That module pinned four section totals off one statement and gated its
    whole parse on them. Every one matches `AMOUNT_RE`; nothing was looking.
    """
    offenders = []
    for path in _parser_modules():
        if path.name in PATTERN_SCAN_EXEMPT:
            continue
        for number, line in _code_lines(path):
            for match in AMOUNT_RE.finditer(line):
                if float(match.group(0)) >= 1.0:
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
                    break
    assert not offenders, f"exact-cent amount constants: {offenders}"


def test_no_literal_calendar_fields_in_patterns():
    """Layer-wide. A pinned month or day makes a parser read one statement.

    `CALENDAR_BASELINE` holds the modules that already carried such a literal
    when this scan was written; a module outside it may carry none.
    """
    offenders = []
    for path in _parser_modules():
        if path.name in CALENDAR_BASELINE:
            continue
        for number, text in _pattern_strings(path):
            if "\\d" not in text and "\\s" not in text:
                continue
            for match in CALENDAR_RE.finditer(text):
                offenders.append(
                    f"{path.name}:{number}: literal {match.group(1)!r} in {text[:70]!r}"
                )
    assert not offenders, f"literal calendar fields pinned into patterns: {offenders}"


#: The two row regexes `analysis/first_citizens.py` carried before the
#: rebuild, and the four section totals its parse was gated on. Kept verbatim
#: as the thing these scans exist to catch: a guard nobody has watched fail is
#: a guard nobody has tested.
FIRST_CITIZENS_MONTH_PATTERNS = (
    r"03\s+([\d,]+\.\d{2})([+-])",
    r"\b(03)\s+(\d[\d,]*\.\d{2})",
)
FIRST_CITIZENS_MEMORIZED_TOTALS = ("55049.85", "44862.06", "9800.18", "74263.31")


@pytest.mark.parametrize("pattern", FIRST_CITIZENS_MONTH_PATTERNS)
def test_calendar_scan_catches_the_literal_that_escaped(pattern):
    assert CALENDAR_RE.search(pattern), (
        "CALENDAR_RE must flag a pinned statement month; this pattern is the "
        "one that shipped and made the parser March-only"
    )


@pytest.mark.parametrize("total", FIRST_CITIZENS_MEMORIZED_TOTALS)
def test_amount_scan_catches_the_totals_that_escaped(total):
    match = AMOUNT_RE.search(f'"deposits": (10, {total}, len(deposits), total),')
    assert match and float(match.group(0)) >= 1.0, (
        "AMOUNT_RE must flag a memorized section total; these four gated the "
        "whole parse and were never scanned because the file was not listed"
    )


def test_pattern_scans_cover_every_parser_module():
    """No parser may be outside the layer-wide scans.

    The defect this file now guards against was a scope defect, so the scope
    itself is asserted rather than assumed.
    """
    scanned = {path.name for path in _parser_modules()}
    every = {path.name for path in ANALYSIS_DIR.glob("*.py")}
    assert every - scanned == LITERAL_SCAN_EXEMPT
    assert "first_citizens.py" in scanned
    assert "citizens.py" in scanned
    assert not (PATTERN_SCAN_EXEMPT & {"first_citizens.py", "citizens.py"})


def test_calendar_baseline_still_describes_real_offenders():
    """The ratchet may not outlive what it excuses.

    An entry that no longer carries a calendar literal must be deleted, so the
    baseline can only ever shrink.
    """
    stale = []
    for name in sorted(CALENDAR_BASELINE):
        path = ANALYSIS_DIR / name
        if not path.exists():
            stale.append(f"{name}: no longer exists")
            continue
        hits = [
            match.group(1)
            for _, text in _pattern_strings(path)
            if "\\d" in text or "\\s" in text
            for match in CALENDAR_RE.finditer(text)
        ]
        if not hits:
            stale.append(f"{name}: clean now, remove it from CALENDAR_BASELINE")
    assert not stale, f"stale calendar baseline entries: {stale}"


@pytest.mark.parametrize("filename", GUARDED_FILES)
def test_no_literal_account_numbers(filename):
    offenders = [
        f"{filename}:{number}: {line.strip()}"
        for number, line in _code_lines(ANALYSIS_DIR / filename)
        if ACCOUNT_RE.search(line)
    ]
    assert not offenders, f"literal account-number digit runs: {offenders}"


@pytest.mark.parametrize("filename", GUARDED_FILES)
def test_no_exact_amount_constants(filename):
    offenders = []
    for number, line in _code_lines(ANALYSIS_DIR / filename):
        for match in AMOUNT_RE.finditer(line):
            if float(match.group(0)) >= 1.0:
                offenders.append(f"{filename}:{number}: {line.strip()}")
                break
    assert not offenders, f"exact-cent amount constants: {offenders}"


@pytest.mark.parametrize("filename", GUARDED_FILES)
def test_no_raw_mojibake_sequences(filename):
    offenders = [
        f"{filename}:{number}"
        for number, line in enumerate(
            (ANALYSIS_DIR / filename).read_text(encoding="utf-8").splitlines(), 1
        )
        if MOJIBAKE_RE.search(line)
    ]
    assert not offenders, f"raw mojibake byte sequences: {offenders}"


def _registered_parser_modules() -> set[str]:
    """The file name of every module the REGISTRY dispatches to.

    Imported here rather than at module scope so the registry load is paid only
    by the tests that need it. `parser_registry_entries` is the module whose
    import performs the registrations.
    """
    from analysis import parser_registry_entries          # noqa: F401
    from analysis.parser_registry import registrations

    return {
        registration.parse.__module__.rsplit(".", 1)[-1] + ".py"
        for registration in registrations()
    }


def test_no_registered_parser_module_is_exempt_from_the_amount_scan():
    """The exemption list may never cover a module the registry DISPATCHES to
    (review MINOR-3).

    `PATTERN_SCAN_EXEMPT` was pinned against two names — `first_citizens.py` and
    `citizens.py`, the two the scan was written for. That is a pin against the
    last accident, not against the class. The rule the list actually encodes is
    "this module is not a parser": `metrics`, `pipeline`, `reconcile` are the
    deterministic math layer and `extract` is the LLM branch, and none of the
    four holds a regex, a reader, a parse gate or a registration. So the
    assertion is the registry's own answer to that question, and it scales with
    the registry instead of with somebody's memory.
    """
    registered = _registered_parser_modules()
    assert len(registered) >= 60, (
        f"the registry did not load ({len(registered)} modules); this test "
        "would pass vacuously"
    )
    leaked = sorted(registered & PATTERN_SCAN_EXEMPT)
    assert leaked == [], (
        "a REGISTERED parser module is exempt from the exact-amount scan; a "
        f"memorized section total in it would never be seen: {leaked}"
    )


def test_the_registered_parser_guard_can_actually_see_a_leak():
    """The mutant, because a guard nobody has watched fail is not a guard: put
    a real registered parser into a copy of the exempt set and the predicate
    must catch it."""
    registered = _registered_parser_modules()
    assert "bmo.py" in registered, "fixture drifted: bmo is no longer registered"
    mutated = PATTERN_SCAN_EXEMPT | {"bmo.py"}
    assert sorted(registered & mutated) == ["bmo.py"]
    # and the four real entries are still not parsers, which is why they pass
    assert registered & PATTERN_SCAN_EXEMPT == set()


# ---------------------------------------------------------------------------
# G7.3 — what the scans read, asserted (W3 §PRIVACY3)
#
# Two cells in a row (§LCPERIOD L5.1, §GRAM4 G7.2/G7.3) hit the same wall: a
# docstring that quotes a real printed row beside a regex escape — which is
# exactly what evidence for a boundary rule looks like — tripped a scan aimed
# at PATTERNS, and both worked around it by rewording prose. G7.3 asked for the
# scan to exclude docstrings and comments explicitly, or for a proof that it
# already does, "so a documented example can never trip or hide a finding".
# Both directions are below, on SYNTHETIC modules: a guard nobody has watched
# fail is not a guard, and these are the shapes that would make it fail.
# ---------------------------------------------------------------------------

#: One literal, three positions. `04-01` is a pinned calendar field the moment
#: it sits inside a pattern, and prose the moment it sits inside a docstring.
_G73_CALENDAR_EXAMPLE = r"(04-01)\s+"


def _g73_module(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


def _calendar_hits(path: Path) -> list[str]:
    return [
        match.group(1)
        for _, text in _pattern_strings(path)
        if r"\d" in text or r"\s" in text
        for match in CALENDAR_RE.finditer(text)
    ]


def test_the_calendar_scan_ignores_the_same_literal_in_a_docstring(tmp_path):
    """Direction 1 — a documented example may not TRIP the scan."""
    source = (
        'r"""A module docstring quoting the class as evidence: ' + _G73_CALENDAR_EXAMPLE + '"""\n'
        "\n"
        "def reader():\n"
        '    r"""A function docstring quoting it too: ' + _G73_CALENDAR_EXAMPLE + '"""\n'
        "    return None\n"
        "\n"
        "class Reader:\n"
        '    r"""And a class docstring: ' + _G73_CALENDAR_EXAMPLE + '"""\n'
    )
    assert _calendar_hits(_g73_module(tmp_path, "documented.py", source)) == []


def test_the_calendar_scan_still_sees_the_literal_in_real_code(tmp_path):
    """Direction 2 — the exclusion may not HIDE one. Same literal, four
    positions the language does NOT call a docstring: a module constant, a
    call argument, a list member, and a string that is merely the second
    statement of a function."""
    source = (
        '"""Real docstring."""\n'
        "import re\n"
        "\n"
        "PATTERN = " + repr(_G73_CALENDAR_EXAMPLE) + "\n"
        "COMPILED = re.compile(" + repr(_G73_CALENDAR_EXAMPLE) + ")\n"
        "ALTERNATES = [" + repr(_G73_CALENDAR_EXAMPLE) + "]\n"
        "\n"
        "def reader():\n"
        '    """Doc."""\n'
        "    " + repr(_G73_CALENDAR_EXAMPLE) + "\n"
        "    return None\n"
    )
    hits = _calendar_hits(_g73_module(tmp_path, "coded.py", source))
    # Two hits per occurrence: `(04-` and `01)\s` each satisfy the rule. That is
    # the rule working, not double counting. Four code positions, so four each.
    assert hits.count("04") == 4 and hits.count("01") == 4


def test_the_code_line_scan_ignores_docstrings_and_comments(tmp_path):
    """`_code_lines`, the other extractor. An amount in a docstring or behind
    a `#` is not a constant the module can read."""
    source = (
        '"""An example the module documents: 1,234.56 and 9876543210."""\n'
        "\n"
        "def reader():\n"
        '    """Another: 3,945.12 in 2026."""\n'
        "    return None  # and a comment: 7,329.22 in 2025\n"
    )
    path = _g73_module(tmp_path, "documented_lines.py", source)
    text = " ".join(line for _, line in _code_lines(path))
    assert AMOUNT_RE.search(text) is None
    assert YEAR_RE.search(text) is None
    assert ACCOUNT_RE.search(text) is None


def test_the_code_line_scan_still_sees_a_triple_quoted_module_constant(tmp_path):
    """The hole G7.3's second half closed, replayed.

    The previous implementation blanked every triple-quoted string. A module
    constant written with triple quotes — a prompt, a word list, a
    `re.VERBOSE` pattern — was therefore invisible to the year, amount and
    account-number scans. It is not a docstring: nothing about its POSITION
    makes it one."""
    source = (
        '"""Real docstring, correctly ignored: 1,111.11."""\n'
        "\n"
        "PROMPT = " + '"""' + "\\n"
        "A worked example: 3,945.12 posted in 2026 to account 9876543210\n"
        + '"""' + "\n"
    )
    path = _g73_module(tmp_path, "constant.py", source)
    text = " ".join(line for _, line in _code_lines(path))
    assert AMOUNT_RE.search(text) is not None
    assert YEAR_RE.search(text) is not None
    assert ACCOUNT_RE.search(text) is not None
    assert "1,111.11" not in text


def test_the_code_line_scan_reports_the_line_numbers_in_the_file(tmp_path):
    """Blanking is in place, character for character, so an offender report
    points at the offending line. The regression this replaces shifted every
    number by the length of the docstring above it."""
    source = (
        '"""Line one\n'
        "line two\n"
        'line three."""\n'
        "AMOUNT = 3945.12\n"
    )
    path = _g73_module(tmp_path, "numbered.py", source)
    assert [number for number, _ in _code_lines(path)] == [4]


def test_a_docstring_sharing_its_line_with_code_blanks_only_the_docstring(tmp_path):
    """Character-level blanking, not line-level: `def f(): '''doc'''` must keep
    its `def`."""
    path = _g73_module(tmp_path, "inline.py", 'def f(): """doc 1,234.56"""\n')
    lines = list(_code_lines(path))
    assert len(lines) == 1
    assert lines[0][0] == 1
    assert lines[0][1].strip().startswith("def f():")
    assert "1,234.56" not in lines[0][1]


def test_the_extract_exemption_still_describes_a_real_offender():
    """A ratchet, like `CALENDAR_BASELINE`: the entry that G7.3 added may not
    outlive what it excuses. If `analysis/extract.py`'s prompt stops carrying
    exact-cent amounts, the exemption comes out."""
    hits = [
        match.group(0)
        for _, line in _code_lines(ANALYSIS_DIR / "extract.py")
        for match in AMOUNT_RE.finditer(line)
        if float(match.group(0)) >= 1.0
    ]
    assert hits, (
        "analysis/extract.py no longer carries exact-cent amounts; remove it "
        "from PATTERN_SCAN_EXEMPT"
    )


def test_closing_the_docstring_hole_flags_exactly_one_module():
    """The blast radius, as an assertion rather than as a claim in a log.

    Closing `_code_lines`'s triple-quote hole made the amount scan see two
    strings it had been blanking. Only one of them carries a finding, and the
    exemption above covers it — so this is the whole measured cost of G7.3, and
    a later module that grows a triple-quoted constant with money in it fails
    here instead of hiding behind the exemption."""
    offenders = set()
    for path in _parser_modules():
        for _, line in _code_lines(path):
            for match in AMOUNT_RE.finditer(line):
                if float(match.group(0)) >= 1.0:
                    offenders.add(path.name)
                    break
    assert offenders <= PATTERN_SCAN_EXEMPT
    assert "extract.py" in offenders
