"""R-1 guard: statement-specific constants must never return to the parsers.

Scans the seven R-1 parser/repair modules for (a) the exact literals removed
by R-1 and (b) forbidden pattern classes: literal 4-digit years outside
date-parsing context, long literal account-number digit runs, exact-cent
amount constants, and raw mojibake byte sequences. Test fixtures may contain
such strings (they represent documents); production parser code may not.
"""
from __future__ import annotations

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
)

#: Literal years (2010-2039) appearing as code constants. Century pivots
#: ("year += 2000" / "2000 +") are date-parsing arithmetic, not memorized
#: years; unicode escape literals ("u20ac"-style) are not years; and
#: comments/docstrings may describe history.
YEAR_RE = re.compile(r"(?<![\d.])(?<!u)20[123]\d(?![\d.])")
#: Long literal digit runs (account-number shaped) as code constants.
ACCOUNT_RE = re.compile(r"(?<![\d.])\d{6,}(?![\d.])")
#: Exact-cent amount constants of one dollar or more (tolerances like 0.01
#: stay allowed).
AMOUNT_RE = re.compile(r"(?<![\d.])\d+\.\d{2}(?![\d.])")
#: Raw mojibake byte sequences; only escape literals are acceptable.
MOJIBAKE_RE = re.compile("[ÃÂ]|â€")


def _code_lines(path: Path):
    """Source lines with comments and docstrings stripped."""
    text = path.read_text(encoding="utf-8")
    # Remove triple-quoted strings (docstrings/comments in this codebase).
    text = re.sub(r'"""(?:[^"]|"(?!""))*"""', '""', text, flags=re.DOTALL)
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0]
        if line.strip():
            yield number, line


@pytest.mark.parametrize("filename", GUARDED_FILES)
def test_removed_literals_stay_removed(filename):
    source = (ANALYSIS_DIR / filename).read_text(encoding="utf-8").upper()
    hits = [literal for literal in REMOVED_LITERALS if literal.upper() in source]
    assert not hits, f"{filename} reintroduces statement-specific literals: {hits}"


@pytest.mark.parametrize("filename", GUARDED_FILES)
def test_no_literal_years_outside_date_parsing(filename):
    offenders = []
    for number, line in _code_lines(ANALYSIS_DIR / filename):
        if not YEAR_RE.search(line):
            continue
        if "2000 +" in line or "+= 2000" in line or "+ 2000" in line:
            continue
        offenders.append(f"{filename}:{number}: {line.strip()}")
    assert not offenders, f"literal year constants: {offenders}"


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
