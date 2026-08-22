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

    Docstrings are blanked line for line rather than collapsed, so the numbers
    reported to a failing developer are the numbers in the file. Collapsing
    them to `""` shifted every subsequent line number by the length of the
    docstring above it, which made offender reports point at the wrong code.
    """
    text = path.read_text(encoding="utf-8")

    def blank(match: re.Match[str]) -> str:
        return '""' + "\n" * match.group(0).count("\n")

    text = re.sub(r'"""(?:[^"]|"(?!""))*"""', blank, text, flags=re.DOTALL)
    for number, raw in enumerate(text.splitlines(), 1):
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


def _pattern_strings(path: Path):
    """Every string constant in a module, with its real line number."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
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
