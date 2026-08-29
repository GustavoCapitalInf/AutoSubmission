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
from datetime import date, timedelta

import pytest

from tools.privacy_scan_branch import (
    EXCLUSIONS,
    NAMED_RESIDUE,
    PROGRAM_ERA,
    TEXT_SUFFIXES,
    _EXCLUSION_SAMPLES,
    added_lines_from_diff,
    excluded_by,
    residue_class,
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

@pytest.mark.parametrize("token", ["100.00", "0.00", "1,250.00", "777777.00"])
def test_round_money_excludes_whole_dollar_figures(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) == "round_money"


@pytest.mark.parametrize("token", ["8909,090.91", "1,250.05", "0.10", "777777.99"])
def test_round_money_reaches_no_figure_with_cents(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) != "round_money"


@pytest.mark.parametrize("token", ["0.01", "0.99", "0.05"])
def test_subunit_money_excludes_a_bare_zero_integer_part(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) == "subunit_money"


@pytest.mark.parametrize("token", ["818,181.81", "777,777.99", "0,000.01", "909,090.91"])
def test_subunit_money_reaches_nothing_above_a_unit(token: str) -> None:
    assert excluded_by("MONEY", "analysis/x.py", token, token) != "subunit_money"


def test_the_money_rules_do_not_between_them_cover_every_figure() -> None:
    """A statement figure with cents and dollars is still a finding."""
    assert excluded_by("MONEY", "tests/test_x.py", "777,777.77", "777,777.77") is None


# --------------------------------------------------------------------------
# hex_sha_substring — inside a sha, not merely on a line that has one.
# --------------------------------------------------------------------------

def test_hex_sha_substring_excludes_a_run_inside_a_sha() -> None:
    line = "SHA 1B41B7B514AE699247E7CF668D7AB023"
    assert excluded_by("DIGITS", "tools/x.py", "69924", line) == "hex_sha_substring"


def test_hex_sha_substring_does_not_excuse_a_number_beside_a_sha() -> None:
    """The token must lie INSIDE the hex run, not merely share its line."""
    line = "1B41B7B514AE699247E7CF668D7AB023 ACCOUNT 7000000001"
    assert excluded_by("DIGITS", "tools/x.py", "7000000001", line) != "hex_sha_substring"


def test_hex_sha_substring_needs_a_run_long_enough_to_be_a_sha() -> None:
    """`ACCT 70030303` is 8 hex-shaped characters; a sha is at least 16."""
    assert excluded_by("DIGITS", "tools/x.py", "70030303", "ACCT 70030303") is None


@pytest.mark.parametrize(
    "line",
    [
        "EVAL_UNKNOWN_BANKS.PY (F7000004E, 392 LINES)",
        "TIP `7000005B`, BASE `10CC722`",
        "TWO Q7 MUTANT FIXES `7000006A`/`579F0BB`",
    ],
)
def test_an_abbreviated_git_object_name_is_a_name_not_a_token(line: str) -> None:
    """The record calls a commit `f14282e`; that is not a number anything printed.

    The token is read OUT of the fixture with the scanner's own pattern (the R2
    lesson) rather than quoted beside it: a quoted literal would stand outside
    every hex run on this very source line, which is exactly the case the rule
    below refuses to excuse.
    """
    token = re.search(r"\d{5,}", line).group(0)
    assert excluded_by("DIGITS", "docs/x.md", token, line) == "hex_sha_substring"


@pytest.mark.parametrize(
    ("token", "line"),
    [
        ("7000004", "ACCOUNT 7000004 AT COMMIT F7000004E"),
        ("98989", "SHA AB98989CDEF AND ACCOUNT 98989"),
        ("7000004", "F7000004E F7000004E 7000004"),
    ],
)
def test_a_digit_run_beside_the_sha_it_is_a_substring_of_is_still_a_finding(
    token: str, line: str
) -> None:
    """Position, not line. The rule asks where the token STANDS: a run that is
    a substring of a sha on its line is excused only where it sits inside one,
    and one occurrence standing on its own is enough to report it."""
    assert excluded_by("DIGITS", "tools/x.py", token, line) is None


@pytest.mark.parametrize(
    ("token", "line"),
    [
        ("70000000011", "RUN 70000000011 (R-3 MERGE)"),   # all digits: no letter
        ("97979", "HYGIENE8 PART 2 = LINES 97979-96969"),
        ("7000000001", "ACCOUNT NUMBER 7000000001"),
        ("9898967", "ACCT 9898967 CLOSED"),               # seven digits, no letter
        ("700303039070030303907003030390700303039012", "X 700303039070030303907003030390700303039012"),
    ],
)
def test_the_git_object_shape_cannot_reach_an_all_digit_run(token: str, line: str) -> None:
    """The required hex LETTER is the whole safety of the second half."""
    assert excluded_by("DIGITS", "docs/x.md", token, line) is None


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
        ("docs/x.md", "2019-11-21"),   # before the era, same century
        ("docs/x.md", "2001-02-03"),   # far before it, still 20xx
        ("docs/x.md", "2011-09-13"),   # a statement period could be any of these
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


@pytest.mark.parametrize("offset", [-2, -1, 0, 1, 30])
def test_the_era_bound_is_pinned_on_both_sides(offset: int) -> None:
    """The counter-samples this rule shipped with stopped at 2019 and never
    probed the days around the bound, so nothing pinned where the bound IS.

    The dates are DERIVED from `PROGRAM_ERA` rather than written down, for two
    reasons. The bound cannot drift away from the constant it is testing. And
    the days either side of the era are real dates in the archive's own last
    months: writing them into a fixture puts printed document dates into
    tracked source, which the whole-tree scan reports -- this file did exactly
    that on its first attempt at this test, and the scan is what said so.
    """
    token = (date.fromisoformat(PROGRAM_ERA) + timedelta(days=offset)).isoformat()
    got = excluded_by("DATES", "docs/x.md", token, f"PERIOD ENDS {token}")
    assert (got == "docs_session_date") is (offset >= 0)


def test_the_day_the_archive_was_frozen_is_inside_the_era() -> None:
    """The rule's residual exposure, pinned rather than hoped away.

    The archive was frozen on 2026-08-06, which is after the era begins, so
    that day is simultaneously a date the program writes about itself and the
    last date a document can print. This rule excuses it: a census entry
    inside `docs/` that quotes a statement period ending in ISO form between
    the era and the freeze IS silenced. One site, measured at this tip. The
    alternative -- dropping the era -- turns every session date the records
    write into residue, and the `mm/dd/yyyy` form a statement actually prints
    is untouched either way.
    """
    frozen = "2026-08-06"
    assert frozen >= PROGRAM_ERA
    assert excluded_by("DATES", "docs/x.md", frozen, f"ENDS {frozen}") == "docs_session_date"


def test_the_era_bound_is_a_date_comparison_not_a_year_comparison() -> None:
    """`token >= PROGRAM_ERA` on ISO strings is a date comparison, and the ISO
    shape is what makes it one. A date in the era's own YEAR but before its
    month is not the program's."""
    era = date.fromisoformat(PROGRAM_ERA)
    token = era.replace(month=1, day=31).isoformat()
    assert excluded_by("DATES", "docs/x.md", token, f"ON {token}") is None


# --------------------------------------------------------------------------
# institution_zip — a postal ADDRESS, and nothing an account can be.
#
# The abbreviation is necessary and never sufficient. Roughly half the list is
# an ordinary English word once the scanner upper-cases the line (`IN`, `OR`,
# `OK`, `ID`, `CO`, `ME`, ...), so the rule asks for the address furniture too:
# a city and its comma, or a post-office box with a CITY between it and the
# state, in the same clause. A ZIP+4 tail is not furniture (the first
# re-review), and neither is the absence of punctuation (the second).
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("token", "line"),
    [
        ("99999", "OZARK, AR 99999"),                          # city, comma, state
        ("99999", r'r"P\.?O\.? BOX 196\s+OZARK,\s*AR\s*99999"'),  # the same, as regex source
        ("99999", "PO BOX 1962 COLUMBUS OH 99999-1558"),       # a box, +4 as well
        ("99999", "PO BOX 1962 ST LOUIS MO 99999"),            # a box in the clause
        ("95959", "P. O. BOX 1962, SEATTLE WA 95959-9750"),
        ("95959", "1 GUARDIAN WAY, PRATTVILLE, AL 95959  334-244-9999"),
        # The six address shapes a box line is actually printed in, so the
        # narrowing below is measured against what it must keep, not only
        # against what it must lose.
        ("99999", "PO BOX 609 PITTSBURGH PA 99999"),           # a one-word city
        ("99999", "P.O. BOX 7889 THE WOODLANDS, TX 99999"),    # a two-word city
        ("99999", "P.O. BOX 1962 SYNTHETIC CITY OH 99999-0000"),
        ("99999", "P.O BOX 1558 EA1W37 COLUMBUS OH 99999-1558"),  # a routing code between
        ("99999", "P.O BOX 179, MOOREFIELD, WV 99999"),
        # A CITY MAY BE TWO WORDS AND THE SECOND MAY BE SHORT. This one is a
        # real institution address in the census, and it is why the rule asks
        # for a city SOMEWHERE between the box and the state rather than for
        # furniture immediately in front of the state.
        ("99999", "EXAMPLE BANK N.A. PO BOX 1962 GREEN BAY WI 99999-9097"),
    ],
)
def test_institution_zip_excludes_a_postal_address(token: str, line: str) -> None:
    assert re.search(rf"{token}(?!\d)", line), "the fixture must print the token"
    assert excluded_by("DIGITS", "analysis/x.py", token, line) == "institution_zip"


@pytest.mark.parametrize(
    ("token", "line"),
    [
        ("9898967", "OZARK, AR 9898967"),     # seven digits is not a postal code
        ("99999", "ACCOUNT 99999"),           # no state abbreviation
        ("99999", "AR " + "x" * 9 + "99999"), # the gap is longer than the rule
        ("99999", "AR 111 99999"),            # a digit run intervenes
        ("98989", "PAID 98989"),
    ],
)
def test_institution_zip_reaches_nothing_wider(token: str, line: str) -> None:
    assert excluded_by("DIGITS", "analysis/x.py", token, line) != "institution_zip"


@pytest.mark.parametrize(
    ("token", "line"),
    [
        # A ZIP+4 TAIL IS NOT EVIDENCE. `NNNNN-NNNN` after an abbreviation-shaped
        # word is a shape the archive prints on identifiers, and the rule used to
        # read it as an address on its own.
        ("84213", "MEMBER ID 84213-6789"),
        ("84213", "CARD ENDING IN 84213-6789"),
        ("84213", "LOAN NO. OR 84213-1234"),
        ("84213", "PAID CO 84213-1234"),
        # THE VOCABULARY, not the geometry: every abbreviation below is also an
        # ordinary word, and every line below is a shape this archive prints.
        ("84213", "MEMBER ID 84213"),                       # a member number
        ("84213", "THE ACCOUNT ENDING IN 84213"),           # an account tail
        ("45678", "07/03 BETA INBOUND CCD CO# 45678 TRACE"),  # an ACH originator id
        ("84213", "09/17 TRANSFER IN 84213 CREDIT"),        # a posting reference
        ("84213", "AUTH OK 84213"),                         # an authorisation code
        ("84213", "CHECK NO OR 84213"),                     # a cheque number
        ("84213", "PAYMENT TO ME 84213"),
        ("84213", "BALANCE DELAWARE 84213"),                # not the abbreviation
    ],
)
def test_a_state_abbreviation_that_is_an_english_word_is_not_an_address(
    token: str, line: str
) -> None:
    assert excluded_by("DIGITS", "analysis/x.py", token, line) is None


@pytest.mark.parametrize(
    ("token", "line"),
    [
        # The box marker belongs to ITS clause. A box in one sentence may not
        # excuse a number in the next.
        ("84213", "PO BOX 196 OZARK, AR 99999; MEMBER ID 84213"),
        ("84213", "PO BOX 196 OZARK, AR 99999 | AUTH OK 84213"),
        ("84213", "PO BOX 196 " + "x" * 75 + " MEMBER ID 84213"),
        # A clause ends at a FULL STOP and at a DASH, not only at `;` and `|`.
        # Both of these were silenced while the class was `[^;|]`.
        ("84213", "PO BOX 609 - ACCOUNT ENDING IN 84213"),
        ("84213", "REMIT TO P.O. BOX 609. AUTH OK 84213"),
        ("84213", "PO BOX 609 \u2014 MEMBER ID 84213"),
        ("84213", "PO BOX 609 (SEE OVER) AUTH OK 84213"),
        # And the clause characters have to do that work THEMSELVES. Every case
        # above also carries an identifier word, which the tempered run refuses
        # on its own, so none of them can tell whether the clause bound still
        # holds. These four carry no identifier word at all: what stands after
        # the punctuation is an ordinary city, state and five digits \u2014 a shape
        # that is reported when no box vouches for it \u2014 so they fail if and
        # only if the box marker reaches across the full stop, the hyphen, the
        # dash or the bracket.
        ("84213", "REMIT TO P.O. BOX 609. PITTSBURGH PA 84213"),
        ("84213", "PO BOX 609 - GREENVILLE SC 84213"),
        ("84213", "PO BOX 609 \u2014 DENVER CO 84213"),
        ("84213", "PO BOX 609 (SEE OVER) BOSTON MA 84213"),
    ],
)
def test_the_box_marker_does_not_reach_out_of_its_clause(token: str, line: str) -> None:
    assert excluded_by("DIGITS", "analysis/x.py", token, line) is None


@pytest.mark.parametrize(
    ("token", "line"),
    [
        # THE ABSENCE OF PUNCTUATION IS NOT FURNITURE. Every line here is one
        # unbroken clause — no full stop, no dash, no separator — so the clause
        # bound cannot help, and every one of them is an identifier the archive
        # prints. The first is the second re-review's residual verbatim: the ACH
        # company-id shape out of `core_processor_signed_counts.py`'s grammar.
        ("45678", "PO BOX 1558 CCD CO# 45678 TRACE"),
        ("45678", "REMIT PO BOX 1558 CCD CO# 45678"),
        # THREE LETTERS ARE NOT A CITY, on its own and with no `#` to help.
        ("45678", "PO BOX 1558 CCD CO 45678"),
        ("84213", "PO BOX 1558 XYZ ID 84213"),
        ("84213", "PO BOX 196 MEMBER ID 84213"),
        ("84213", "PO BOX 196 THE MEMBER ID 84213"),
        ("84213", "PO BOX 196 SOUTH MEMBER ID 84213"),
        ("84213", "PO BOX 609 ACCOUNT NO OR 84213"),
        ("84213", "PO BOX 609 PITTSBURGH ACCOUNT NO OR 84213"),
        ("84213", "PO BOX 196 AUTH OK 84213"),
        ("84213", "PO BOX 196 CHECK NO OR 84213"),
        ("84213", "PO BOX 1962 CARD ENDING IN 84213"),
    ],
)
def test_a_box_needs_a_city_between_it_and_the_state(token: str, line: str) -> None:
    """A box marker plus an unbroken run of ordinary characters is not an address.

    Three letters are not a city (`CCD`), and the words this archive prints to
    introduce an identity — `MEMBER`, `ACCOUNT`, `AUTH`, `CHECK`, `CARD`, `NO`
    — are not cities either, whatever their length. The run from the box to the
    state is tempered against all of them, in both halves, so a city standing
    legitimately in front of one (`PITTSBURGH ACCOUNT NO OR 84213`) does not
    rescue it.
    """
    assert excluded_by("DIGITS", "analysis/x.py", token, line) is None


@pytest.mark.parametrize(
    ("token", "line"),
    [
        ("45678", "PO BOX 1558 ACME CORP CO# 45678 TRACE"),
        ("45678", "ACME INC, CO# 45678 TRACE"),
        ("45678", "OZARK, AR# 45678"),
        ("45678", "PO BOX 196 OZARK AR# 45678"),
    ],
)
def test_a_number_sign_is_not_postal_furniture(token: str, line: str) -> None:
    """`#` between the state and the digits is evidence AGAINST an address.

    It is the mark this archive puts in front of an identity — `CO# 45678` —
    and a postal code never carries one. Both address shapes share the gap, so
    saying it once covers both, and it closes the case a city-shaped word
    cannot: a COMPANY name standing where a city would.
    """
    assert excluded_by("DIGITS", "analysis/x.py", token, line) is None


@pytest.mark.parametrize(
    ("token", "line"),
    [
        # The gap between the abbreviation and the code is SHORT and DIGIT-FREE,
        # and it has to stay both even when the address furniture is present:
        # an address prints its code next to its state, and anything reached
        # across a phrase or across another number is not that code.
        ("84213", "OZARK, AR ACCOUNT NO 84213"),
        ("84213", "OZARK, AR 1 84213"),
        ("84213", "PO BOX 1962 OZARK AR ACCOUNT NO 84213"),
        ("84213", "P. O. BOX 1962, SEATTLE WA 95959-9750 MEMBER ID 84213"),
    ],
)
def test_the_gap_stays_short_and_digit_free_inside_the_address_shapes(
    token: str, line: str
) -> None:
    assert excluded_by("DIGITS", "analysis/x.py", token, line) is None


@pytest.mark.parametrize(
    ("token", "line", "excused"),
    [
        # THE NARROWING'S COST, AND IT IS ONE SHAPE. A genuine box address whose
        # city is shorter than four letters and which carries no comma is
        # reported now. The same line with the city's comma is excused, which is
        # what bounds the cost to this one shape. Live cost in this tree: zero.
        ("99999", "PO BOX 1 ADA OK 99999", False),
        ("99999", "PO BOX 1 ADA, OK 99999", True),
        # THE RESIDUAL, AS WIDE AS IT ACTUALLY IS: the substitute city need not
        # be identity-flavoured at all, and ordinary English will do. The
        # identifier list is a floor on what the rule catches, never a ceiling.
        ("99999", "PO BOX 196 SERIAL OR 99999", True),
        ("99999", "PO BOX 196 VOUCHER OR 99999", True),
        ("99999", "PO BOX 196 FOLIO ID 99999", True),
    ],
)
def test_the_city_rule_costs_one_shape_and_leaves_a_residual_this_wide(
    token: str, line: str, excused: bool
) -> None:
    """Both halves of the rule's honest description, pinned so they stay true."""
    rule = excluded_by("DIGITS", "analysis/x.py", token, line)
    assert (rule == "institution_zip") is excused, rule


def test_a_bare_city_state_code_with_no_furniture_is_reported_not_hidden() -> None:
    """The narrowing's own cost, pinned. `CITY ST 99999` with no comma, no box
    and no ZIP+4 is indistinguishable from `AUTH OK 84213` by shape alone, so
    the rule declines it and the scan REPORTS it — the safe direction."""
    assert excluded_by("DIGITS", "analysis/x.py", "99999", "ST LOUIS MO 99999") is None


# --------------------------------------------------------------------------
# The block: no rule, in any combination, may silence an identifier.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("cls", "token", "line"),
    [
        ("DIGITS", "7001010102", 'FLAT.FIND("BUSINESSPLUS CHECKING (S70) - 7001010102")'),
        ("DIGITS", "7002020203", '"EMINENT FUNDING": ("EMINENT", "7002020203")'),
        ("DIGITS", "44556677", "ACCOUNT NUMBER 44556677"),
        ("DIGITS", "98989", "CHECK 98989"),
        ("DIGITS", "70030303", "MERCHANT PURCHASE TERMINAL 70030303"),
        ("DIGITS", "84213", "MEMBER ID 84213"),
        ("DIGITS", "84213", "THE ACCOUNT ENDING IN 84213"),
        ("DIGITS", "45678", "07/03 BETA INBOUND CCD CO# 45678 TRACE"),
        ("DIGITS", "45678", "PO BOX 1558 CCD CO# 45678 TRACE"),
        ("DIGITS", "84213", "PO BOX 196 MEMBER ID 84213"),
        ("DIGITS", "84213", "AUTH OK 84213"),
        ("DIGITS", "84213", "CHECK NO OR 84213"),
        ("MONEY", "777,777.77", "BEGINNING BALANCE 777,777.77"),
        ("MONEY", "818,181.81", "CREDITS (3) +$818,181.81"),
        ("DATES", "02/16/31", "ATM W/D 1339 02/16/31"),
        ("DATES", "2019-11-21", "PERIOD ENDS 2019-11-21"),
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


@pytest.mark.parametrize(
    ("token", "line"),
    [
        ("98989", "REF 98989A CLEARED"),      # six characters: shorter than any
        ("23456", "ITEM B23456 POSTED"),      # abbreviation this record writes
    ],
)
def test_a_run_shorter_than_an_abbreviation_is_not_an_object_name(token: str, line: str) -> None:
    """Seven is the shortest object name these records use; six is a reference."""
    assert excluded_by("DIGITS", "docs/x.md", token, line) is None


# --------------------------------------------------------------------------
# The diff reader. An exclusion that reaches too wide hides a token; a diff
# reader that drops a line never sees one. Both are ways for the instrument to
# report a zero it did not earn.
# --------------------------------------------------------------------------

_DIFF_WITH_A_QUOTED_HEADER = (
    "diff --git a/docs/r.md b/docs/r.md\n"
    "--- a/docs/r.md\n"
    "+++ b/docs/r.md\n"
    "@@ -0,0 +1,4 @@\n"
    "+the closure quotes a diff:\n"
    "+--- a/analysis/x.py\n"
    "+++ b/analysis/x.py\n"
    "+ACCOUNT 44556677\n"
)


def test_the_diff_reader_reads_a_line_that_begins_like_a_file_header() -> None:
    """A quoted `+++ b/...` inside the FILE arrives as `++++ b/...` in the body.

    Reading it as a header drops the line from the scan — an added line the
    instrument never looks at — and shifts every line after it by one.
    """
    read = added_lines_from_diff(_DIFF_WITH_A_QUOTED_HEADER)
    assert [(path, number) for path, number, _text in read] == [
        ("docs/r.md", 1), ("docs/r.md", 2), ("docs/r.md", 3), ("docs/r.md", 4),
    ]
    assert read[2][2] == "++ B/ANALYSIS/X.PY"
    assert read[3][2] == "ACCOUNT 44556677"


def test_the_diff_reader_numbers_every_hunk_from_its_own_header() -> None:
    diff = (
        "--- a/tests/t.py\n"
        "+++ b/tests/t.py\n"
        "@@ -10,0 +11,2 @@\n"
        "+first\n"
        "+second\n"
        "@@ -40,1 +42,1 @@\n"
        "-gone\n"
        "+here\n"
    )
    assert added_lines_from_diff(diff) == [
        ("tests/t.py", 11, "FIRST"),
        ("tests/t.py", 12, "SECOND"),
        ("tests/t.py", 42, "HERE"),
    ]


def test_the_diff_reader_counts_no_removed_line_and_no_newline_marker() -> None:
    diff = (
        "--- a/tests/t.py\n"
        "+++ b/tests/t.py\n"
        "@@ -3,2 +3,1 @@\n"
        "---- a quoted removal\n"
        "-plain removal\n"
        "+kept\n"
        "\\ No newline at end of file\n"
    )
    assert added_lines_from_diff(diff) == [("tests/t.py", 3, "KEPT")]


# --------------------------------------------------------------------------
# What the scanner reads at all, and what it counts apart.
#
# A suffix list is a claim about what is worth reading, and a file the list
# forgets is audited by nothing. A NAMED residue class is the opposite of an
# exclusion: it is residue that is counted apart so a ruling can be written
# about it, and it must never be silenced by a rule.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("suffix", ["log", "shas", "ps1"])
def test_the_tracked_text_the_scanner_had_never_read_is_read_now(suffix: str) -> None:
    """`.log`, `.shas` and `.ps1` are tracked TEXT and were outside the list.

    One of them is a run log written by a tool that printed document text, and
    nothing had ever looked at it. This is the first review's item 6.
    """
    assert suffix in TEXT_SUFFIXES


def test_the_suffix_list_still_declines_the_corpus_documents() -> None:
    """The list is about TEXT. A PDF is evidence, not source."""
    assert "pdf" not in TEXT_SUFFIXES


@pytest.mark.parametrize(
    "path",
    [path for _name, paths in NAMED_RESIDUE for path in paths],
)
def test_a_named_residue_class_is_counted_and_never_excused(path: str) -> None:
    """Named is not excluded: every rule must still decline these paths.

    The three files are per-statement audited expectations read as DATA by the
    benchmark, so their contents ARE archive identity — real balances, real
    account masks, real periods, one of them holding the last copy of the
    account number the P0 card removed everywhere else. That needs a ruling,
    and a ruling needs a number, so the sites stay residue and are counted
    apart rather than silenced.
    """
    assert residue_class(path) is not None
    # A statement figure, an account tail, a document date: all still reported.
    assert excluded_by("MONEY", path, "818,181.81", "SHA,818,181.81,X") is None
    assert excluded_by("DIGITS", path, "44556677", "SHA,44556677,X") is None
    assert excluded_by("DATES", path, "2019-11-21", "SHA,2019-11-21,X") is None


@pytest.mark.parametrize(
    "path",
    [path for _name, paths in NAMED_RESIDUE for path in paths],
)
def test_the_session_date_rule_does_not_reach_into_a_named_class(path: str) -> None:
    """A date in a truth CSV is a statement period, not the day a cell ran.

    Both are ISO and both are inside `docs/`, so the era rule would have taken
    it — and it is the one boundary the re-review measured a live site on.
    """
    assert excluded_by("DATES", path, "2026-08-06", f"SHA,{path},2026-08-06") is None
    # The same token in an ordinary record IS a session date.
    assert excluded_by("DATES", "docs/x.md", "2026-08-06", "ON 2026-08-06") == "docs_session_date"


@pytest.mark.parametrize(
    "path",
    [path for _name, paths in NAMED_RESIDUE for path in paths],
)
@pytest.mark.parametrize(
    ("cls", "token", "line"),
    [
        # One case per rule of the table, each chosen to be exactly the shape
        # that rule claims. Inside a named path NONE of them may claim it.
        ("MONEY", "100.00", "SHA,100.00,X"),               # round_money
        ("MONEY", "70300.00", "SHA,70300.00,X"),           # round_money, five figures
        ("MONEY", "0.01", "SHA,0.01,X"),                   # subunit_money
        ("DIGITS", "98989", "SHA,AB98989CDEF09898967,X"),  # hex_sha_substring
        ("DIGITS", "99999", "SHA,OZARK, AR 99999,X"),      # institution_zip
        ("DATES", "2026-08-29", "SHA,2026-08-29,X"),       # docs_session_date
        ("MONEY", "818,181.81", "SHA,818,181.81,X"),       # nothing claims it anyway
    ],
)
def test_no_rule_of_the_table_silences_anything_inside_a_named_class(
    path: str, cls: str, token: str, line: str
) -> None:
    """The class is counted WHOLE, and the count is the ruling's input.

    The first version of this carve-out lived inside `docs_session_date` alone,
    so three other rules went on silencing a quarter of the class while the
    record called it never-excused. A `.00` figure in a per-statement audited
    expectations file is a real printed balance; `round_money` excuses that
    class by choice, and inside these files the choice is not the scanner's to
    make.
    """
    assert excluded_by(cls, path, token, line) is None


@pytest.mark.parametrize(
    "path",
    [path for _name, paths in NAMED_RESIDUE for path in paths],
)
def test_the_named_carve_out_stops_at_WORDS(path: str) -> None:
    """The one class still excused inside a named path, and why.

    `words_class` discards every WORDS hit everywhere — the tree is unaudited
    for customer names by construction — so counting names here and nowhere
    else would put a number on the ruling that means something different from
    the number in every other file. A scope statement, not an exception.
    """
    assert excluded_by("WORDS", path, "SMITH JONES", "SHA,SMITH JONES,X") == "words_class"


@pytest.mark.parametrize(
    ("cls", "token", "line", "rule"),
    [
        ("MONEY", "100.00", "TOTAL 100.00", "round_money"),
        ("MONEY", "0.01", "TOLERANCE 0.01", "subunit_money"),
        ("DATES", "2026-08-29", "ON 2026-08-29", "docs_session_date"),
    ],
)
def test_the_same_shapes_are_still_excused_outside_a_named_class(
    cls: str, token: str, line: str, rule: str
) -> None:
    """The carve-out is about the PATH, and it reaches nothing wider."""
    assert excluded_by(cls, "docs/moneythumb-replacement/x.md", token, line) == rule


def test_a_named_class_names_a_file_the_scanner_would_read() -> None:
    for _name, paths in NAMED_RESIDUE:
        for path in paths:
            assert path.rsplit(".", 1)[-1].lower() in TEXT_SUFFIXES


def test_residue_class_declines_an_ordinary_path() -> None:
    assert residue_class("docs/moneythumb-replacement/census_batch9/per_sha.csv") is None
    assert residue_class("tests/test_x.py") is None
    assert residue_class("docs/adb-audit-results.csv.bak") is None
