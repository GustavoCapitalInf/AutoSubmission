"""The privacy scanner's exclusion table: each rule, exactly its shape.

An exclusion is the only way a candidate leaves the scan without being fixed,
so an exclusion that reaches one character wider than the shape it names is a
silent leak with a committed excuse in front of it. Every test below is written
the same way: the shape the rule NAMES is excluded, and the nearest thing that
is NOT that shape survives. The last test is the one that matters most — no
rule in the table, in any combination, may swallow a bare account number.

Nothing here reads the archive; the fixtures are invented shapes.
"""
from __future__ import annotations

import re

import pytest

from tools.privacy_scan_branch import (
    EXCLUSIONS,
    _EXCLUSION_SAMPLES,
    excluded_by,
    self_check,
)

RULE_NAMES = tuple(name for name, _ in EXCLUSIONS)


def test_the_table_self_checks_on_import() -> None:
    """`self_check` refuses an inert table; it must pass on the committed one."""
    self_check()


def test_every_rule_carries_a_sample_and_a_counter_sample() -> None:
    for name in RULE_NAMES:
        rows = [s for s in _EXCLUSION_SAMPLES if s[0] == name]
        assert any(s[5] for s in rows), f"{name} has no positive sample"
        assert any(not s[5] for s in rows), f"{name} has no counter-sample"


def test_no_rule_is_named_twice() -> None:
    assert len(set(RULE_NAMES)) == len(RULE_NAMES)


# --------------------------------------------------------------------------
# words_class — alphabetic template vocabulary, and nothing with a digit in it.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("token", ["BALANCE", "DEPOSIT", "OZARK", "SAMPLE MERCHANT"])
def test_words_class_excludes_alphabetic_tokens(token: str) -> None:
    assert excluded_by("WORDS", "analysis/x.py", token, token) == "words_class"


@pytest.mark.parametrize("cls", ["MONEY", "DIGITS", "DATES"])
def test_words_class_reaches_no_other_class(cls: str) -> None:
    assert excluded_by(cls, "analysis/x.py", "44556677", "ACCOUNT 44556677") != "words_class"


# --------------------------------------------------------------------------
# corpus_cache — that directory, not the tests around it.
# --------------------------------------------------------------------------

def test_corpus_cache_excludes_the_committed_cache() -> None:
    path = "tests/corpus_cache/pages/AAAA.json"
    assert excluded_by("MONEY", path, "1,234.56", "1,234.56") == "corpus_cache"


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_analysis.py",
        "tests/corpus_cache_notes.md",      # a NEIGHBOUR, not the directory
        "docs/tests/corpus_cache/x.md",     # not at the top of the path
        "analysis/corpus_cache.py",
    ],
)
def test_corpus_cache_reaches_no_other_path(path: str) -> None:
    assert excluded_by("MONEY", path, "1,234.56", "1,234.56") != "corpus_cache"


# --------------------------------------------------------------------------
# round_money / subunit_money — magnitudes, not identities.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("token", ["100.00", "0.00", "1,250.00", "999999.00"])
def test_round_money_excludes_whole_dollar_figures(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) == "round_money"


@pytest.mark.parametrize("token", ["100.01", "1,250.05", "0.10", "999999.99"])
def test_round_money_reaches_no_figure_with_cents(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) != "round_money"


@pytest.mark.parametrize("token", ["0.01", "0.99", "0.05"])
def test_subunit_money_excludes_a_bare_zero_integer_part(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) == "subunit_money"


@pytest.mark.parametrize("token", ["10.01", "1,000.99", "0,000.01", "20.05"])
def test_subunit_money_reaches_nothing_above_a_unit(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) != "subunit_money"


def test_the_money_rules_do_not_between_them_cover_every_figure() -> None:
    """A statement figure with cents and dollars is still a finding."""
    assert excluded_by("MONEY", "tests/test_x.py", "26,245.24", "26,245.24") is None


# --------------------------------------------------------------------------
# hex_sha_substring — inside a sha, not merely on a line that has one.
# --------------------------------------------------------------------------

def test_hex_sha_substring_excludes_a_run_inside_a_sha() -> None:
    line = "SHA 1B41B7B514AE699247E7CF668D7AB023"
    assert excluded_by("DIGITS", "tools/x.py", "69924", line) == "hex_sha_substring"


def test_hex_sha_substring_does_not_excuse_a_number_beside_a_sha() -> None:
    """The token must lie INSIDE the hex run, not merely share its line."""
    line = "1B41B7B514AE699247E7CF668D7AB023 ACCOUNT 8877665544"
    assert excluded_by("DIGITS", "tools/x.py", "8877665544", line) != "hex_sha_substring"


def test_hex_sha_substring_needs_a_run_long_enough_to_be_a_sha() -> None:
    """`ACCT 12345678` is 8 hex-shaped characters; a sha is at least 16."""
    assert excluded_by("DIGITS", "tools/x.py", "12345678", "ACCT 12345678") is None


@pytest.mark.parametrize("cls", ["MONEY", "DATES", "WORDS"])
def test_hex_sha_substring_is_a_digits_rule_only(cls: str) -> None:
    line = "1B41B7B514AE699247E7CF668D7AB023"
    assert excluded_by(cls, "tools/x.py", "69924", line) != "hex_sha_substring"


# --------------------------------------------------------------------------
# docs_session_date — the program's own dates, bounded by directory AND era.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("token", ["2026-07-01", "2026-08-29", "2027-01-05"])
def test_docs_session_date_excludes_the_programs_own_era(token: str) -> None:
    assert excluded_by("DATES", "docs/x.md", token, f"ON {token}") == "docs_session_date"


@pytest.mark.parametrize(
    ("path", "token"),
    [
        ("docs/x.md", "2026-06-30"),   # one day before the era
        ("docs/x.md", "2025-04-30"),   # a statement period
        ("tests/test_x.py", "2026-08-29"),  # right era, wrong tree
        ("analysis/x.py", "2026-08-29"),
    ],
)
def test_docs_session_date_is_bounded_both_ways(path: str, token: str) -> None:
    assert excluded_by("DATES", path, token, f"ON {token}") != "docs_session_date"


@pytest.mark.parametrize("token", ["08/29/2026", "AUGUST 29, 2026"])
def test_docs_session_date_covers_the_iso_notation_only(token: str) -> None:
    """A slashed or spelled date in `docs/` is how a DOCUMENT prints one."""
    assert excluded_by("DATES", "docs/x.md", token, f"ON {token}") != "docs_session_date"


# --------------------------------------------------------------------------
# institution_zip — a branch's postal code, and nothing an account can be.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "line",
    [
        "OZARK, AR 72949",
        r'r"P\.?O\.? BOX 196\s+OZARK,\s*AR\s*72949"',
        "ST LOUIS MO 63166",
    ],
)
def test_institution_zip_excludes_a_state_and_its_code(line: str) -> None:
    token = re.search(r"(\d{5})(?!\d)", line).group(1)
    assert excluded_by("DIGITS", "analysis/x.py", token, line) == "institution_zip"


@pytest.mark.parametrize(
    ("token", "line"),
    [
        ("1234567", "OZARK, AR 1234567"),     # seven digits is not a postal code
        ("72949", "ACCOUNT 72949"),           # no state abbreviation
        ("72949", "AR " + "x" * 9 + "72949"), # the gap is longer than the rule
        ("72949", "AR 111 72949"),            # a digit run intervenes
        ("55555", "PAID 55555"),
    ],
)
def test_institution_zip_reaches_nothing_wider(token: str, line: str) -> None:
    assert excluded_by("DIGITS", "analysis/x.py", token, line) != "institution_zip"


# --------------------------------------------------------------------------
# The block: no rule, in any combination, may silence an identifier.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("cls", "token", "line"),
    [
        ("DIGITS", "0836327000", 'FLAT.FIND("BUSINESSPLUS CHECKING (S70) - 0836327000")'),
        ("DIGITS", "3329001101", '"EMINENT FUNDING": ("EMINENT", "3329001101")'),
        ("DIGITS", "44556677", "ACCOUNT NUMBER 44556677"),
        ("DIGITS", "12345", "CHECK 12345"),
        ("DIGITS", "07615556", "MERCHANT PURCHASE TERMINAL 07615556"),
        ("MONEY", "26,245.24", "BEGINNING BALANCE 26,245.24"),
        ("MONEY", "1,326.43", "CREDITS (3) +$1,326.43"),
        ("DATES", "02/16/26", "ATM W/D 1339 02/16/26"),
        ("DATES", "2026-04-30", "PERIOD ENDS 2026-04-30"),
    ],
)
@pytest.mark.parametrize(
    "path", ["analysis/x.py", "tests/test_x.py", "tools/x.py", "docs/x.md", "webapp/x.py"]
)
def test_no_exclusion_silences_an_identifier_or_a_statement_figure(
    cls: str, token: str, line: str, path: str
) -> None:
    rule = excluded_by(cls, path, token, line)
    assert rule is None, f"{path}: {cls} {token!r} was excluded by {rule!r}"
