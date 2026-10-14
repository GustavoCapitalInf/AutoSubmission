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
import hashlib
import re
from pathlib import Path

import pytest

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"
#: OQ2 = YES (docs/moneythumb-replacement/PHASE2_RULINGS.md): the
#: no-statement-hardcodes / value-meaning-hardcodes protection extends into
#: `ocr/`. See the `# --- OQ2 extension ---` section at the end of this file.
OCR_DIR = Path(__file__).resolve().parent.parent / "ocr"

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
    "2054-06-18",             # item 1 - memorized date
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

#: Removed statement literals whose TEXT must not be written into tracked source at all, this file included: the
#: ratchet above works by writing the offending string into the repository, and a name that may belong to a real
#: party is what the standing privacy rule keeps out of it (see
#: `test_no_worked_example_in_the_llm_prompt_carries_a_figure`). Each entry is (word count, sha256 of the literal's
#: words): the literal upper-cased, its [A-Z0-9] runs joined by one space. `_literal_digest` computes it.
REMOVED_LITERAL_DIGESTS = (
    # Audit 2026-10-13, REC-8: the holder line the Banco Popular reader compared page lines against (a customer name).
    (5, "58d453a0ac18f02010a7fe1e12d144e2802a57197645f70cdb597037c581a3b2"),
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
#: **`extract.py` is no longer here, and that is the whole of the EXTRACT-PROMPT
#: card (#HYGIENE8).** G7.3 (W3 §PRIVACY3) added it as a DISCLOSURE rather than
#: a shrug: closing `_code_lines`'s triple-quote hole made the LLM prompt
#: visible to this scan for the first time, and the prompt's worked example
#: carried nine matches on four lines — a label/value alignment example and a
#: description example whose payee was a real-looking insurer name, which is
#: exactly the class R-1 purged. §PRIVACY3 could not own the file and carded it.
#:
#: The prompt now teaches the same three things — align BY POSITION, a count is
#: not an amount, a trailing "-" is a sign — with PLACEHOLDERS (`<V1>`…`<V6>`,
#: `<N>`) in place of the literals. Placeholders are not a way of ducking the
#: threshold: they carry no figure at all, which is the property the rule is
#: about, and they make the example impossible to mistake for a statement.
#: The exemption is therefore deleted rather than re-justified, and
#: `test_the_amount_scan_now_sees_the_llm_prompt` is what fails if a literal
#: comes back.
PATTERN_SCAN_EXEMPT = {"metrics.py", "pipeline.py", "reconcile.py"}

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


_DIGEST_WORD_RE = re.compile(r"[A-Z0-9]+")


def _literal_digest(literal: str) -> tuple[int, str]:
    """The (word count, digest) `REMOVED_LITERAL_DIGESTS` holds for `literal`."""
    words = _DIGEST_WORD_RE.findall(literal.upper())
    return len(words), hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest()


def _digest_hits(paths, digests=REMOVED_LITERAL_DIGESTS) -> list[str]:
    """Every file whose text holds a run of words matching a removed literal's digest, in any casing and with any
    spacing or punctuation between the words: code, string constants, comments and docstrings alike."""
    wanted: dict[int, set[str]] = {}
    for count, digest in digests:
        wanted.setdefault(count, set()).add(digest)
    hits = []
    for path in paths:
        words = _DIGEST_WORD_RE.findall(path.read_text(encoding="utf-8").upper())
        for count, digests_of_count in wanted.items():
            for start in range(len(words) - count + 1):
                window = " ".join(words[start:start + count])
                if hashlib.sha256(window.encode("utf-8")).hexdigest() in digests_of_count:
                    hits.append(f"{path.name}: word {start}")
    return hits


def test_removed_literal_digests_stay_removed_anywhere_in_analysis_and_ocr():
    """Audit 2026-10-13, REC-8: `analysis/banco_popular.py` skipped any line equal to one customer's business name.
    The reader now skips the page-header holder line by position, and this guard keeps the name out of the parser and
    OCR layers without writing it here (`REMOVED_LITERAL_DIGESTS`)."""
    paths = sorted(ANALYSIS_DIR.rglob("*.py")) + sorted(OCR_DIR.rglob("*.py"))
    assert len(paths) > 100, "the scan found almost no modules; it would pass vacuously"
    hits = _digest_hits(paths)
    assert not hits, f"a removed statement literal is back (by digest): {hits}"


def test_the_digest_scan_can_see_a_planted_literal(tmp_path):
    """The guard above is not vacuous: a fabricated name planted the way the original was (a `line ==` comparison),
    and again in other casing and spacing, is found by its digest alone."""
    planted = "NORTHWIND PLANTED SAMPLE HOLDINGS LLC"
    module = tmp_path / "planted.py"
    module.write_text(
        "def skip(line):\n"
        f"    return line == {planted!r}\n"
        "# northwind  planted-sample holdings, llc\n",
        encoding="utf-8",
    )
    clean = tmp_path / "clean.py"
    clean.write_text("NORTHWIND PLANTED SAMPLE\nHOLDINGS = 1\n# NORTHWIND SAMPLE PLANTED HOLDINGS LLC\n", encoding="utf-8")
    digest = _literal_digest(planted)
    assert digest[0] == 5
    hits = _digest_hits([module], digests=(digest,))
    assert len(hits) == 2 and all(hit.startswith("planted.py: ") for hit in hits)
    assert _digest_hits([module], digests=((5, "0" * 64),)) == []
    # The same words in another order, or cut short, are not the literal.
    assert _digest_hits([clean], digests=(digest,)) == []


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
    "this module is not a parser": `metrics`, `pipeline` and `reconcile` are the
    deterministic math layer, and none of the three holds a regex, a reader, a
    parse gate or a registration. (`extract.py`, the LLM branch, was a fourth
    entry until #HYGIENE8's EXTRACT-PROMPT removed the constants that needed
    excusing.) So the
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
    # and the three real entries are still not parsers, which is why they pass
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


def test_the_amount_scan_now_sees_the_llm_prompt():
    """The EXTRACT-PROMPT closure, as the inverse of the ratchet it replaces
    (#HYGIENE8).

    G7.3 exempted `analysis/extract.py` because closing the triple-quote hole
    made its prompt visible with nine matches on four lines, and
    `test_the_extract_exemption_still_describes_a_real_offender` asserted those
    matches still existed so the exemption could not outlive them. They are
    gone: the module is back inside the scan, and this asserts the scan really
    reaches it rather than passing because the file is skipped.
    """
    assert "extract.py" not in PATTERN_SCAN_EXEMPT
    assert (ANALYSIS_DIR / "extract.py") in _parser_modules()
    hits = [
        f"{number}: {match.group(0)}"
        for number, line in _code_lines(ANALYSIS_DIR / "extract.py")
        for match in AMOUNT_RE.finditer(line)
        if float(match.group(0)) >= 1.0
    ]
    assert hits == [], f"the LLM prompt carries exact-cent constants again: {hits}"
    # ...and the scan is not vacuous over this file: it still READS it, which is
    # the half a skipped path would also satisfy.
    assert any("SUMMARY ALIGNMENT" in line
               for _, line in _code_lines(ANALYSIS_DIR / "extract.py"))


def test_no_worked_example_in_the_llm_prompt_carries_a_figure():
    """The half `AMOUNT_RE` cannot see, and the half that actually found the
    defect: a worked example.

    The offender G7.3 named (W3 §PRIVACY3 P10 item 5, where it is quoted) was an
    insurer-shaped payee welded to an exact-cent amount, standing in for a real
    posting. The amount scan above catches the number; nothing catches "a quoted
    example that looks like a row off somebody's statement". The rule here is
    the one property those examples must have to be safe: **a quoted example in
    the prompt teaches a SHAPE, so it carries no digits.** `<V1>`, `<N>` and
    `"<description as printed> <money token>"` satisfy it; a payee with a figure
    welded to it cannot.

    Deliberately NOT closed by adding the insurer token to `REMOVED_LITERALS`:
    that ratchet works by writing the offending string into tracked source, and
    a name that may belong to a real party is exactly what the standing privacy
    rule keeps out of this repository. A structural rule needs no specimen —
    which is why this docstring no longer carries one either (#HYGIENE8 H9.1).
    The shared privacy scan run with the ROOT commit as `--base`, so that its
    exclusion set is empty and inherited tokens are visible, found the specimen
    still standing here: the branch deleted it from `analysis/extract.py` and
    re-wrote it into this docstring, which is the same string in tracked source
    that the paragraph above says must stay out.
    """
    source = (ANALYSIS_DIR / "extract.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    prompt = next(
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "_INSTRUCTIONS" for t in node.targets)
        and isinstance(node.value, ast.Constant)
    )
    quoted = re.findall(r'"([^"\n]*)"', prompt)
    assert quoted, "the prompt has no quoted examples left; this rule is vacuous"
    offenders = [text for text in quoted if any(ch.isdigit() for ch in text)]
    assert offenders == [], (
        f"a worked example in the LLM prompt carries a figure: {offenders}"
    )
    # The teaching the placeholders replaced must still be there, or the fix
    # was a deletion wearing a rewrite's clothes. Naming the tokens is not
    # enough and a mutant proved it: deleting the two-column example outright
    # left every placeholder standing in the PROSE around it. So the example's
    # own shape is asserted — a label row and a value row, on their own lines.
    for token in ("<V1>", "<V3>", "<V6>", "<N>", "BY POSITION"):
        assert token in prompt, f"the alignment example lost {token!r}"
    lines = prompt.splitlines()
    assert any(
        "Previous Balance" in line and "<N>" in line for line in lines
    ), "the alignment example lost its LABEL row"
    assert any(
        re.search(r"<V1>.*<V2>.*<V3>", line) for line in lines
    ), "the alignment example lost its VALUE row"
    # ...and its CONTINUATION, which the token loop above only appears to
    # cover. A HYGIENE-8a mutant (E3) deleted `<V4> / <V5> / <V6>` outright and
    # survived: `"<V6>" in prompt` was still true, satisfied by the prose that
    # introduces the placeholders. A membership test over a string that also
    # contains the legend proves the legend, not the example — the same
    # mistake, one level down, that made mutant E5 necessary.
    assert any(
        re.search(r"<V4>.*<V5>.*<V6>", line) for line in lines
    ), "the alignment example lost the CONTINUATION of its value row"


def test_closing_the_docstring_hole_flags_no_module():
    """The blast radius, as an assertion rather than as a claim in a log.

    Closing `_code_lines`'s triple-quote hole (G7.3) made the amount scan see
    two strings it had been blanking, and exactly one of them carried a finding:
    the LLM prompt. EXTRACT-PROMPT removed the finding rather than the
    exemption's excuse, so the measured cost of G7.3 is now ZERO modules outside
    the math layer — and a later module that grows a triple-quoted constant with
    money in it fails here."""
    offenders = set()
    for path in _parser_modules():
        for _, line in _code_lines(path):
            for match in AMOUNT_RE.finditer(line):
                if float(match.group(0)) >= 1.0:
                    offenders.add(path.name)
                    break
    assert offenders <= PATTERN_SCAN_EXEMPT
    assert "extract.py" not in offenders


# ---------------------------------------------------------------------------
# OQ2 extension (docs/moneythumb-replacement/PHASE2_RULINGS.md, ruled
# 2026-09-01): the no-statement-hardcodes / value-meaning-hardcodes
# protection extends into `ocr/`. F-3 (OCR_LEGACY_AUDIT.md) found issuer-
# specific behaviour (TD page-1 recovery) inside the intake layer, where this
# guard's scans never reached. Everything below reuses the SAME pattern
# classes and helper functions already defined above, parameterized over
# `ocr/*.py` instead of `analysis/*.py` -- no new detection logic, only a new
# scope. Blast radius measured before any test was written (P20-POSTPROCESS,
# 2026-09-01): REMOVED_LITERALS / YEAR_RE / ACCOUNT_RE / MOJIBAKE_RE /
# CALENDAR_RE are all clean (0 hits) across every file in `ocr/`; AMOUNT_RE
# hits exactly two files, both non-statement furniture (see
# OCR_AMOUNT_BASELINE below).
# ---------------------------------------------------------------------------

#: Modules in `ocr/` that carry an AMOUNT_RE-shaped literal that is NOT a
#: statement value -- a ratchet baseline in the same spirit as
#: CALENDAR_BASELINE, ONLY for the exact lines measured when this scan was
#: written. Both are read-only/render furniture, never data read off a
#: statement:
#:   * `column_grid.py:207` -- `reach = pitch * 1.25`, a geometry ratio
#:     constant used to size a column-detection search window.
#:   * `render.py:83,85,87,89,114` -- CSS `line-height`/`font-size` values
#:     (1.55em, 1.25em, 1.05rem twice, 1.05rem) inside the page-rendering
#:     stylesheet constant.
#: A module outside this set may carry no AMOUNT_RE-shaped literal >= 1.0.
OCR_AMOUNT_BASELINE = {"column_grid.py", "render.py"}


def _ocr_modules() -> list[Path]:
    """Every module the OQ2 scans apply to: all of `ocr/*.py`."""
    return sorted(OCR_DIR.glob("*.py"))


def test_no_removed_literals_in_ocr():
    offenders = []
    for path in _ocr_modules():
        source = path.read_text(encoding="utf-8").upper()
        for literal in REMOVED_LITERALS:
            if literal.upper() in source:
                offenders.append(f"{path.name}: {literal}")
    assert not offenders, f"statement-specific literals in ocr/: {offenders}"


def test_no_literal_years_in_ocr():
    offenders = []
    for path in _ocr_modules():
        for number, line in _code_lines(path):
            if not YEAR_RE.search(line):
                continue
            if "2000 +" in line or "+= 2000" in line or "+ 2000" in line:
                continue
            offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, f"literal year constants in ocr/: {offenders}"


def _verified_calibration_value_spans(path: Path) -> dict[int, tuple[int, int]]:
    """Only the active, recomputed calibration record is cryptographic data.

    This is a value-span classification, never a hex, line or file exemption.
    A copied, forged, misplaced or inactive record remains ordinary scanned code.
    """
    if path.resolve() != (OCR_DIR / "extraction_quality.py").resolve():
        return {}
    from ocr.extraction_quality import EXTRACTION_QUALITY_VERSION, calibration_digest

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = [node for node in tree.body if
        (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
         and node.target.id == "CALIBRATION_DIGESTS") or
        (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
         and target.id == "CALIBRATION_DIGESTS" for target in node.targets))]
    if len(assignments) != 1 or not isinstance(assignments[0], ast.AnnAssign):
        return {}
    call = assignments[0].value
    if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name)
            or call.func.id != "MappingProxyType" or len(call.args) != 1
            or call.keywords or not isinstance(call.args[0], ast.Dict)):
        return {}
    values = [value for key, value in zip(call.args[0].keys, call.args[0].values)
              if isinstance(key, ast.Constant) and type(key.value) is int
              and key.value == EXTRACTION_QUALITY_VERSION]
    if len(values) != 1:
        return {}
    value = values[0]
    expected = calibration_digest()
    if (not isinstance(value, ast.Constant) or not isinstance(value.value, str)
            or value.value != expected):
        return {}
    lines = source.splitlines()
    spans = {}
    for number in range(value.lineno, value.end_lineno + 1):
        raw = lines[number - 1].encode("utf-8")
        start = value.col_offset if number == value.lineno else 0
        stop = value.end_col_offset if number == value.end_lineno else len(raw)
        # AST columns are UTF-8 byte offsets; _code_lines preserves characters.
        spans[number] = (len(raw[:start].decode("utf-8")), len(raw[:stop].decode("utf-8")))
    return spans


def _ocr_account_code_lines(path: Path):
    spans = _verified_calibration_value_spans(path)
    for number, line in _code_lines(path):
        if number in spans:
            start, stop = spans[number]
            line = line[:start] + " " * (stop - start) + line[stop:]
        yield number, line


def test_no_literal_account_numbers_in_ocr():
    offenders = []
    for path in _ocr_modules():
        for number, line in _ocr_account_code_lines(path):
            if ACCOUNT_RE.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, f"literal account-number digit runs in ocr/: {offenders}"


def _synthetic_calibration_source(tmp_path, monkeypatch, value, *, version=None,
                                  filename="extraction_quality.py", assignment="CALIBRATION_DIGESTS",
                                  extra="", suffix="", prefix=""):
    from ocr.extraction_quality import EXTRACTION_QUALITY_VERSION

    monkeypatch.setitem(globals(), "OCR_DIR", tmp_path)
    active = EXTRACTION_QUALITY_VERSION if version is None else version
    source = (prefix + f"{assignment}: Mapping[int, str] = MappingProxyType({{{active}: {value!r}"
              + extra + "})" + suffix + "\n")
    path = tmp_path / filename
    path.write_text(source, encoding="utf-8")
    return path


def test_ocr_account_guard_accepts_only_the_recomputed_active_digest(tmp_path, monkeypatch):
    from ocr.extraction_quality import calibration_digest

    digest = calibration_digest()
    path = _synthetic_calibration_source(tmp_path, monkeypatch, digest)
    assert any(ACCOUNT_RE.search(line) for _, line in _code_lines(path))
    assert not any(ACCOUNT_RE.search(line) for _, line in _ocr_account_code_lines(path))


@pytest.mark.parametrize("width", [7, 64])
def test_ocr_account_guard_rejects_forged_or_malformed_digest_values(tmp_path, monkeypatch, width):
    path = _synthetic_calibration_source(tmp_path, monkeypatch, "7" * width)
    assert any(ACCOUNT_RE.search(line) for _, line in _ocr_account_code_lines(path))


@pytest.mark.parametrize("extra_active", [False, True])
def test_ocr_account_guard_keeps_inactive_version_values_scanned(tmp_path, monkeypatch, extra_active):
    from ocr.extraction_quality import EXTRACTION_QUALITY_VERSION, calibration_digest

    digest = calibration_digest()
    extra = f", {EXTRACTION_QUALITY_VERSION}: {digest!r}" if extra_active else ""
    path = _synthetic_calibration_source(tmp_path, monkeypatch, digest,
        version=EXTRACTION_QUALITY_VERSION + 1, extra=extra)
    assert any(ACCOUNT_RE.search(line) for _, line in _ocr_account_code_lines(path))


@pytest.mark.parametrize("wrong", ["module", "assignment"])
def test_ocr_account_guard_keeps_wrong_location_values_scanned(tmp_path, monkeypatch, wrong):
    from ocr.extraction_quality import calibration_digest

    path = _synthetic_calibration_source(tmp_path, monkeypatch, calibration_digest(),
        filename="unrelated.py" if wrong == "module" else "extraction_quality.py",
        assignment="UNRELATED_DIGESTS" if wrong == "assignment" else "CALIBRATION_DIGESTS")
    assert any(ACCOUNT_RE.search(line) for _, line in _ocr_account_code_lines(path))


@pytest.mark.parametrize("prefix", ["", "label = 'é'; "])
def test_ocr_account_guard_preserves_neighboring_literals_on_the_same_line(tmp_path, monkeypatch, prefix):
    from ocr.extraction_quality import calibration_digest

    marker = "8" * 9
    path = _synthetic_calibration_source(tmp_path, monkeypatch, calibration_digest(),
        prefix=prefix, suffix=f"; account = {marker!r}")
    lines = list(_ocr_account_code_lines(path))
    assert any(marker in line and ACCOUNT_RE.search(line) for _, line in lines)
    assert not any(calibration_digest() in line for _, line in lines)


def test_no_exact_amount_constants_in_ocr():
    offenders = []
    for path in _ocr_modules():
        if path.name in OCR_AMOUNT_BASELINE:
            continue
        for number, line in _code_lines(path):
            for match in AMOUNT_RE.finditer(line):
                if float(match.group(0)) >= 1.0:
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
                    break
    assert not offenders, f"exact-cent amount constants in ocr/: {offenders}"


def test_ocr_amount_baseline_still_describes_real_offenders():
    """The ratchet may only ever shrink (same property as
    `test_calendar_baseline_still_describes_real_offenders`)."""
    stale = []
    for name in sorted(OCR_AMOUNT_BASELINE):
        path = OCR_DIR / name
        if not path.exists():
            stale.append(f"{name}: no longer exists")
            continue
        hits = [
            match.group(0)
            for _, line in _code_lines(path)
            for match in AMOUNT_RE.finditer(line)
            if float(match.group(0)) >= 1.0
        ]
        if not hits:
            stale.append(f"{name}: clean now, remove it from OCR_AMOUNT_BASELINE")
    assert not stale, f"stale OCR_AMOUNT_BASELINE entries: {stale}"


def test_no_literal_calendar_fields_in_ocr_patterns():
    offenders = []
    for path in _ocr_modules():
        for number, text in _pattern_strings(path):
            if "\\d" not in text and "\\s" not in text:
                continue
            for match in CALENDAR_RE.finditer(text):
                offenders.append(
                    f"{path.name}:{number}: literal {match.group(1)!r} in {text[:70]!r}"
                )
    assert not offenders, f"literal calendar fields pinned into ocr/ patterns: {offenders}"


def test_no_raw_mojibake_sequences_in_ocr():
    offenders = []
    for path in _ocr_modules():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if MOJIBAKE_RE.search(line):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, f"raw mojibake byte sequences in ocr/: {offenders}"


# ---------------------------------------------------------------------------
# The issuer-named-string register guard. F-3 / OQ2 (P20-POSTPROCESS item
# 4-5): the TD markers were admitted ONLY through `ocr.ocr_client.
# INTAKE_FURNITURE`, which left with the visual OCR client (slice S2); the
# register is now `REGISTERED_ISSUER_MARKER_OWNERS`, empty. Layer-wide over every file in `ocr/` (review MAJOR-2:
# the original scope was 3 files "because ocr/native_text.py carries
# pre-existing constants" -- measured to cost 0 offenders today when widened,
# so the narrowing bought nothing while leaving 10 of 13 files unguarded).
# `native_text.py` and `column_grid.py` keep their pre-existing per-issuer
# structural PDF-parsing constants under a NAMED, COUNTED, shrink-only
# ratchet (`OCR_ISSUER_STRING_BASELINE`) rather than a blanket file skip --
# a per-file skip would leave a FUTURE addition to those two files
# uncaught (review's mutant J), which the count-based ratchet below does not.
# ---------------------------------------------------------------------------

#: A representative set of real institution names/marketing phrases (public
#: information, the same class already used openly in
#: `tests/test_parser_detection_markers.py`). Broad enough to catch a
#: realistic future addition; narrow enough that, outside the two ratcheted
#: files, it currently matches nothing in `ocr/` except the declared TD
#: markers.
ISSUER_NAME_LEXICON = (
    "td bank", "td business", "most convenient bank", "td canada trust",
    "wells fargo", "bank of america", "jpmorgan chase", "chase bank",
    "citibank", "pnc bank", "truist", "huntington bank", "regions bank",
    "capital one", "u.s. bank", "us bank", "fifth third", "bank of montreal",
    "cibc", "royal bank of canada", "scotiabank", "desjardins", "woodforest",
    "navy federal", "first citizens", "zions bank", "santander", "bmo harris",
    "wilson muir", "farmers and merchants", "columbia bank", "first community",
    "guardian credit union", "linkbank",
)

#: (`ISSUER_MARKERS_BY_ISSUER`, the TD markers grouped for
#: `tests/test_ocr_intake_furniture.py`, was deleted with that test file and
#: the visual OCR client it tested, slice S2.)

#: Pre-existing per-issuer structural PDF-parsing constants outside this
#: card's ownership -- a NAMED ratchet, not a scope exclusion (review
#: MAJOR-2). Measured by summing, over every `str` `ast.Constant` in the
#: module, the count of each `ISSUER_NAME_LEXICON` marker found in it
#: (`_issuer_string_hit_count`, below) -- module/function docstrings included
#: (they are `ast.Constant` nodes), bare identifiers (function/variable
#: NAMES, e.g. `parse_native_woodforest`) excluded (a name is not a string
#: value this scan reads). The count may only shrink: a module growing a NEW
#: occurrence -- an issuer string added to an already-ratcheted file, exactly
#: the shape review mutant J tests -- fails
#: `test_ocr_issuer_string_baseline_is_not_exceeded`.
#:   * `native_text.py`: 5 issuers (woodforest, navy federal, first citizens,
#:     desjardins, wells fargo), 25 occurrences -- `ocr/native_text.py`'s own
#:     per-issuer native-PDF-text column/layout readers (`parse_native_
#:     woodforest`, `parse_native_navy_federal`, `parse_native_desjardins`,
#:     the First Citizens description-column reader, the Wells Fargo summary
#:     reader), structurally analogous to `analysis/`'s per-bank parsers --
#:     not owned by this card, not the postprocess/intake-furniture surface
#:     OQ1/OQ2 govern.
#:   * `column_grid.py`: 1 issuer (woodforest), 3 occurrences -- geometry
#:     helpers reused by the Woodforest column reader above.
OCR_ISSUER_STRING_BASELINE = {
    "native_text.py": 25,
    "column_grid.py": 3,
}


def _issuer_owning_name(node: ast.AST, parents: dict) -> str:
    """The nearest enclosing assignment target, function, or class name for
    `node` -- so an issuer marker written as a bare `re.search(...)` literal
    argument (review mutant I) is attributed to its containing function, not
    only a `NAME = re.compile(...)` assignment."""
    cur = node
    while cur in parents:
        cur = parents[cur]
        if (isinstance(cur, ast.Assign) and len(cur.targets) == 1
                and isinstance(cur.targets[0], ast.Name)):
            return cur.targets[0].id
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return cur.name
    return f"<module line {node.lineno}>"


def _issuer_string_hits(path: Path):
    """(owning_name, lineno, marker) for every occurrence of an
    `ISSUER_NAME_LEXICON` marker inside any `str` `ast.Constant` in `path` --
    a `re.compile(...)` pattern, a bare `re.search(...)` literal, a tuple of
    marker strings, or any other string value the language can compile.
    Widened past `re.compile` assignments alone (review MAJOR-2 fix #2)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            low = node.value.lower()
            for marker in ISSUER_NAME_LEXICON:
                count = low.count(marker)
                if count:
                    owner = _issuer_owning_name(node, parents)
                    hits.extend([(owner, node.lineno, marker)] * count)
    return hits


def _issuer_string_hit_count(path: Path) -> int:
    return len(_issuer_string_hits(path))


def _unregistered_issuer_markers(path: Path, registered: set[str]) -> list[str]:
    """Every issuer-string hit in `path` whose owning name is not in
    `registered` (`REGISTERED_ISSUER_MARKER_OWNERS`)."""
    return [
        f"{path.name}:{lineno}: {owner!r} matches issuer marker {marker!r}"
        for owner, lineno, marker in _issuer_string_hits(path)
        if owner not in registered
    ]


#: The register of names allowed to own an issuer-named string in `ocr/`
#: outside `OCR_ISSUER_STRING_BASELINE`. It was the retired visual OCR client's
#: `INTAKE_FURNITURE` (the TD page-furniture markers); the client was deleted in
#: slice S2 of the model-code removal, so the register is EMPTY and any
#: issuer-named string outside the two ratcheted files now fails.
REGISTERED_ISSUER_MARKER_OWNERS: frozenset[str] = frozenset()


def test_every_issuer_named_regex_in_ocr_is_registered():
    """Layer-wide (review MAJOR-2 fix #1). Every file OUTSIDE
    `OCR_ISSUER_STRING_BASELINE` must carry zero issuer-string hits whose
    owning name is not in the (now empty) register."""
    registered = set(REGISTERED_ISSUER_MARKER_OWNERS)
    offenders = []
    scanned = []
    for path in _ocr_modules():
        if path.name in OCR_ISSUER_STRING_BASELINE:
            continue
        scanned.append(path.name)
        offenders.extend(_unregistered_issuer_markers(path, registered))
    assert not offenders, (
        f"issuer-named string(s) outside the register: {offenders}"
    )
    # The scan is not vacuous: it walked the real ocr/ modules (the TD marker
    # that used to prove it, in the deleted client, is gone), and the planted
    # mutant in `test_the_issuer_marker_guard_can_actually_see_an_unregistered_marker`
    # below proves the same scanning function catches an unregistered marker.
    assert {"pipeline.py", "local_tesseract.py", "render.py"} <= set(scanned), scanned
    assert not (OCR_DIR / "ocr_client.py").exists()


def test_ocr_issuer_string_baseline_is_not_exceeded():
    """The ratchet may only ever shrink (same property as
    `test_calendar_baseline_still_describes_real_offenders` /
    `test_ocr_amount_baseline_still_describes_real_offenders`), and growth
    must be caught even inside an already-ratcheted file -- review mutant J:
    a NEW issuer regex added to `native_text.py` must not hide behind the
    baseline's existing count."""
    grown = []
    for name, ceiling in OCR_ISSUER_STRING_BASELINE.items():
        actual = _issuer_string_hit_count(OCR_DIR / name)
        if actual > ceiling:
            grown.append(f"{name}: {actual} > baselined {ceiling}")
        elif actual < ceiling:
            grown.append(f"{name}: {actual} < baselined {ceiling} (baseline is stale, tighten it)")
    assert not grown, f"OCR_ISSUER_STRING_BASELINE no longer matches measurement: {grown}"


def test_the_issuer_marker_guard_can_actually_see_an_unregistered_marker(tmp_path):
    """The mutant, named in the P20-POSTPROCESS mutation table: 'an issuer
    marker added outside INTAKE_FURNITURE' must be killed. A synthetic module
    mimicking `ocr/pipeline.py` with a brand-new, unregistered issuer marker
    must be caught by the same scanning function the real guard uses --
    review mutant I: as an inline `re.search(...)` literal, not only a
    `NAME = re.compile(...)` assignment."""
    mutant = tmp_path / "pipeline.py"
    mutant.write_text(
        "import re\n"
        "def _is_wf_statement(text):\n"
        '    return bool(re.search(r"wells fargo", text, re.IGNORECASE))\n',
        encoding="utf-8",
    )
    offenders = _unregistered_issuer_markers(mutant, registered=set())
    assert offenders, "the guard did not catch an unregistered inline issuer marker"
    assert "_is_wf_statement" in offenders[0]

    # And registering the containing function's name clears it -- proving
    # the guard checks the register, not just the presence of a marker.
    cleared = _unregistered_issuer_markers(mutant, registered={"_is_wf_statement"})
    assert cleared == []


def test_the_issuer_marker_guard_catches_a_new_compile_assignment_too(tmp_path):
    """The card's own mutant (F) restated over the widened detector: a
    `NAME = re.compile(...)` assignment is still caught."""
    mutant = tmp_path / "pipeline.py"
    mutant.write_text(
        "import re\n"
        '_WF_STATEMENT_RE = re.compile(r"wells fargo", re.IGNORECASE)\n',
        encoding="utf-8",
    )
    offenders = _unregistered_issuer_markers(mutant, registered=set())
    assert offenders and "_WF_STATEMENT_RE" in offenders[0]
    assert _unregistered_issuer_markers(mutant, registered={"_WF_STATEMENT_RE"}) == []


def test_the_issuer_marker_guard_catches_growth_inside_a_ratcheted_file(tmp_path):
    """Review mutant J, reproduced directly against the ratchet mechanism (not
    only against the real `native_text.py`, which the mutation campaign also
    exercises): a synthetic module shaped like a baselined file, with one
    more issuer occurrence than its ceiling, must be flagged as grown."""
    mutant = tmp_path / "native_text.py"
    mutant.write_text(
        "import re\n"
        '_EXISTING = "woodforest"\n'
        '_NEW_ISSUER_RE = re.compile(r"wells fargo", re.IGNORECASE)\n',
        encoding="utf-8",
    )
    baseline = {"native_text.py": 1}  # only _EXISTING's one "woodforest" hit allowed
    actual = _issuer_string_hit_count(mutant)
    assert actual > baseline["native_text.py"], (
        "the ratchet mechanism did not see the added issuer marker as growth"
    )


# ---------------------------------------------------------------------------
# P21-ROUTING CASE 15: the OQ2 protection extends to `evidence/` and
# `tools/paddle_vast.py`, reusing the SAME pattern classes and helper
# functions defined above — no new detection logic, only a new scope, exactly
# the OCR extension's own precedent (see its header comment). Blast radius
# measured before this test was written: every scan below is clean (0 hits)
# over both `evidence/*.py` and `tools/paddle_vast.py`.
# ---------------------------------------------------------------------------

EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "evidence"
PADDLE_VAST_TOOL = Path(__file__).resolve().parent.parent / "tools" / "paddle_vast.py"
#: P22-CLASSIFY (Phase 2.2 case 24): the neutral `layout/` package joins the
#: same scans — a roots APPEND only, no new detection logic.
LAYOUT_DIR = Path(__file__).resolve().parent.parent / "layout"

#: P22-TRUTHTABLE (Phase 2.2 case 24, card item 10): the two NEW modules this
#: card adds — the layered unresolved-reason vocabulary and the sealed-store
#: join — join the same scans. A roots APPEND only, no new detection logic,
#: in cell C's style one line above.
#:
#: `discovery/` and `telemetry/` as WHOLES are deliberately NOT added here,
#: and that is reported rather than done quietly: both are large pre-existing
#: packages that these scans have never covered, so adding them is a ratchet
#: decision with its own baseline to establish (the scans are not "does this
#: file look clean", they are "no statement-specific literal, no literal year,
#: no account-shaped digit run, no exact amount"), and a card whose job is
#: reporting plumbing is the wrong place to take it. The two files this card
#: AUTHORS are covered from birth, which is the part that is genuinely a clean
#: append.
P22_TRUTHTABLE_MODULES = [
    Path(__file__).resolve().parent.parent / "telemetry" / "unresolved_taxonomy.py",
    Path(__file__).resolve().parent.parent / "tools" / "truth_report.py",
]

#: P23-WAVE (Phase 2.3, card item 9): the wave runner joins the same scans, in
#: cell T's style one line above — a roots APPEND only, no new detection logic.
#: It is covered from birth, which is the part that is genuinely a clean append;
#: `discovery/` and `telemetry/` as WHOLES stay out for the reason T recorded.
P23_WAVE_MODULES = [
    Path(__file__).resolve().parent.parent / "tools" / "paddle_wave.py",
]

#: P23-EGATE (Phase 2.3 cell E, card item 6): the census instrument joins the
#: same scans — a roots APPEND only, in the two lines of precedent above. Its
#: module, `ocr/extraction_quality.py`, needs no append at all: `_ocr_modules`
#: already covers every file in `ocr/`, and
#: `test_the_p23_egate_scan_roots_cover_the_module_and_the_tool` asserts that
#: rather than assuming it — an allowlist whose members are covered by
#: accident is one rename away from covering nothing.
P23_EGATE_MODULES = [
    Path(__file__).resolve().parent.parent / "tools" / "extraction_quality_census.py",
]

#: P23-AGREE (Phase 2.3 cell X, card item 6): this card's two instruments
#: join the same scans. A roots APPEND only, no new detection logic, in the
#: style of the two blocks above. `layout/agreement.py` needs no entry — the
#: whole of `layout/*.py` is already globbed below, so it is covered from
#: birth.
P23_AGREE_MODULES = [
    Path(__file__).resolve().parent.parent / "tools" / "agreement_census.py",
    Path(__file__).resolve().parent.parent / "tools" / "agree_native_census.py",
    Path(__file__).resolve().parent.parent / "tools" / "agree_mutation_table.py",
]


def _paddle_phase21_modules() -> list[Path]:
    """`evidence/*.py` plus `tools/paddle_vast.py` — CASE 15's exact scope —
    plus `layout/*.py` (Phase 2.2 case 24), cell T's two new modules, and cell
    W's wave runner (Phase 2.3)."""
    modules = sorted(EVIDENCE_DIR.glob("*.py"))
    if PADDLE_VAST_TOOL.exists():
        modules.append(PADDLE_VAST_TOOL)
    modules.extend(sorted(LAYOUT_DIR.glob("*.py")))
    modules.extend(path for path in P22_TRUTHTABLE_MODULES if path.exists())
    modules.extend(path for path in P23_WAVE_MODULES if path.exists())
    modules.extend(path for path in P23_EGATE_MODULES if path.exists())
    modules.extend(path for path in P23_AGREE_MODULES if path.exists())
    return modules


def test_the_p23_agree_modules_and_the_agreement_module_are_actually_scanned():
    """The same guard cell T wrote for its own roots: a named file that does
    not exist scans nothing and passes. `layout/agreement.py` is asserted
    here too, because it is covered by a GLOB rather than by name and a glob
    that stopped matching would be just as silent."""
    missing = [path.name for path in P23_AGREE_MODULES if not path.exists()]
    assert not missing, f"named in the scan roots but absent: {missing}"
    scanned = {path.name for path in _paddle_phase21_modules()}
    assert {path.name for path in P23_AGREE_MODULES} <= scanned
    assert "agreement.py" in scanned


def test_the_p22_truthtable_modules_are_actually_scanned():
    """A roots append that names a file which does not exist scans nothing and
    passes, which is the failure mode of every allowlist. Both must be here."""
    missing = [path.name for path in P22_TRUTHTABLE_MODULES if not path.exists()]
    assert not missing, f"named in the scan roots but absent: {missing}"
    scanned = {path.name for path in _paddle_phase21_modules()}
    assert {path.name for path in P22_TRUTHTABLE_MODULES} <= scanned


def test_the_p23_wave_module_is_actually_scanned():
    """The same guard for this card's append, for the same reason."""
    missing = [path.name for path in P23_WAVE_MODULES if not path.exists()]
    assert not missing, f"named in the scan roots but absent: {missing}"
    scanned = {path.name for path in _paddle_phase21_modules()}
    assert {path.name for path in P23_WAVE_MODULES} <= scanned


def test_the_p23_egate_scan_roots_cover_the_module_and_the_tool():
    """Card item 6: the metrics module AND the census instrument are in the
    OQ2 scan roots. The module is covered by the `ocr/` layer scan and the
    tool by this card's append; both are asserted, because a named root that
    does not exist scans nothing and passes."""
    missing = [path.name for path in P23_EGATE_MODULES if not path.exists()]
    assert not missing, f"named in the scan roots but absent: {missing}"
    assert {path.name for path in P23_EGATE_MODULES} <= {p.name for p in _paddle_phase21_modules()}
    assert "extraction_quality.py" in {path.name for path in _ocr_modules()}


def test_no_removed_literals_in_evidence_and_paddle_vast():
    offenders = []
    for path in _paddle_phase21_modules():
        source = path.read_text(encoding="utf-8").upper()
        for literal in REMOVED_LITERALS:
            if literal.upper() in source:
                offenders.append(f"{path.name}: {literal}")
    assert not offenders, f"statement-specific literals: {offenders}"


def test_no_literal_years_in_evidence_and_paddle_vast():
    offenders = []
    for path in _paddle_phase21_modules():
        for number, line in _code_lines(path):
            if not YEAR_RE.search(line):
                continue
            if "2000 +" in line or "+= 2000" in line or "+ 2000" in line:
                continue
            offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, f"literal year constants: {offenders}"


#: `canonical.py:615` -- `"0123456789ABCDEFabcdef"`, the hex-digit CHARSET
#: `_is_sha256_hex` validates against, not an account number. A ratchet
#: baseline in the same spirit as `OCR_AMOUNT_BASELINE`.
EVIDENCE_ACCOUNT_BASELINE = {"canonical.py"}


def test_no_literal_account_numbers_in_evidence_and_paddle_vast():
    offenders = []
    for path in _paddle_phase21_modules():
        if path.name in EVIDENCE_ACCOUNT_BASELINE:
            continue
        for number, line in _code_lines(path):
            if ACCOUNT_RE.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, f"literal account-number digit runs: {offenders}"


def test_evidence_account_baseline_still_describes_a_real_offender():
    """The ratchet may only ever shrink."""
    stale = []
    for name in sorted(EVIDENCE_ACCOUNT_BASELINE):
        path = EVIDENCE_DIR / name
        if not path.exists():
            stale.append(f"{name}: no longer exists")
            continue
        hits = [line for _, line in _code_lines(path) if ACCOUNT_RE.search(line)]
        if not hits:
            stale.append(f"{name}: clean now, remove it from EVIDENCE_ACCOUNT_BASELINE")
    assert not stale, f"stale EVIDENCE_ACCOUNT_BASELINE entries: {stale}"


def test_no_exact_amount_constants_in_evidence_and_paddle_vast():
    offenders = []
    for path in _paddle_phase21_modules():
        for number, line in _code_lines(path):
            for match in AMOUNT_RE.finditer(line):
                if float(match.group(0)) >= 1.0:
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
                    break
    assert not offenders, f"exact-cent amount constants: {offenders}"


def test_no_literal_calendar_fields_in_evidence_and_paddle_vast_patterns():
    offenders = []
    for path in _paddle_phase21_modules():
        for number, text in _pattern_strings(path):
            if "\\d" not in text and "\\s" not in text:
                continue
            for match in CALENDAR_RE.finditer(text):
                offenders.append(
                    f"{path.name}:{number}: literal {match.group(1)!r} in {text[:70]!r}"
                )
    assert not offenders, f"literal calendar fields pinned into a pattern: {offenders}"


def test_no_raw_mojibake_sequences_in_evidence_and_paddle_vast():
    offenders = []
    for path in _paddle_phase21_modules():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if MOJIBAKE_RE.search(line):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, f"raw mojibake byte sequences: {offenders}"


def test_evidence_and_paddle_vast_scope_is_not_accidentally_empty():
    """A scan over an empty file list passes vacuously and proves nothing —
    the same lesson `test_the_calendar_scan_still_sees_the_literal_in_real_
    code` exists to teach elsewhere in this file. `evidence/canonical.py`
    always exists (cell 0's contract); `tools/paddle_vast.py` may not exist
    yet on a base tree ahead of cell P's composition, so it is checked
    separately and never REQUIRED for this pin to be meaningful."""
    modules = _paddle_phase21_modules()
    names = {path.name for path in modules}
    assert "canonical.py" in names, "evidence/canonical.py was not found by the scan"
