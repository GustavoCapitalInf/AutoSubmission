"""`layout/signals.py` — the closed signal vocabulary, the three-language
lexicons and the minimal token-shape grammars (Phase 2.2 cell C,
`P22-CLASSIFY.md` §4; umbrella case 24 for the no-hardcode scans).

Every lexicon entry is exercised here with a positive sample AND a boundary
negative (the entry glued to a letter must not match), which is what
"closed, fixtured" means. Mutant M9 (an issuer string added to a lexicon)
dies twice: the issuer-marker scan the OQ2 guard already owns is run over
`layout/` with an empty register, and a synthetic mutant module proves the
scan can see such an addition.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from layout import signals
from layout.signals import (
    DATE_RE,
    LEXICONS,
    MONEY_RE,
    SIGNALS,
    ZERO_ACTIVITY_PATTERNS,
    find_dates,
    find_lexicon,
    find_money,
    find_page_marker,
    find_zero_activity,
    is_micr_shaped,
    money_cents,
)
from tests.test_no_statement_hardcodes import _issuer_string_hits, _paddle_phase21_modules, _unregistered_issuer_markers

ROOT = Path(__file__).resolve().parents[1]
LAYOUT_DIR = ROOT / "layout"


# ---------------------------------------------------------------------------
# the vocabulary is closed
# ---------------------------------------------------------------------------

def test_signal_names_are_a_closed_sorted_unique_vocabulary():
    assert isinstance(SIGNALS, tuple) and len(SIGNALS) == len(set(SIGNALS))
    assert all(re.fullmatch(r"[a-z_]+", name) for name in SIGNALS)
    for required in ("file_invalid_fact", "period_expression", "opening_balance_label", "closing_balance_label",
                     "zero_activity_declaration", "table_run", "table_alignment", "running_balance", "page_marker",
                     "page_gap", "page_missing", "first_page_missing", "balance_discontinuity", "micr_shape",
                     "micr_band", "cheque_aspect", "cheque_lexicon", "void_lexicon", "deposit_slip_lexicon",
                     "letter_lexicon", "card_lexicon", "loan_lexicon", "brokerage_lexicon", "deposit_lexicon",
                     "screenshot_frame", "reverse_chronology", "pending_row", "illegible_floor"):
        assert required in SIGNALS, required


def test_lexicons_cover_the_three_languages_and_are_lowercase_phrases():
    assert set(LEXICONS) >= {"period_phrase", "opening_balance", "closing_balance", "cheque", "void", "deposit_slip",
                             "letter", "card", "loan", "brokerage", "deposit_account", "pending"}
    for name, by_language in LEXICONS.items():
        assert set(by_language) == {"en", "fr", "es"}, name
        for language, entries in by_language.items():
            assert isinstance(entries, tuple), (name, language)
            assert entries, f"{name}/{language} is empty — every lexicon speaks all three languages"
            for entry in entries:
                assert entry == entry.lower().strip(), (name, language, entry)
                assert entry, (name, language)


@pytest.mark.parametrize("name", sorted(["period_phrase", "opening_balance", "closing_balance", "cheque", "void",
                                         "deposit_slip", "letter", "card", "loan", "brokerage", "deposit_account",
                                         "pending"]))
def test_every_lexicon_entry_is_fixtured_with_a_positive_and_a_boundary_negative(name):
    for language, entries in LEXICONS[name].items():
        for entry in entries:
            hits = find_lexicon(f"xx {entry} yy", name)
            assert any(h.phrase == entry and h.language == language for h in hits), (name, language, entry)
            if entry[-1].isalpha():
                glued = find_lexicon(f"xx {entry}z yy", name)
                assert not any(h.phrase == entry for h in glued), f"{name}/{language}: {entry!r} matched inside a longer word"
            if entry[0].isalpha():
                glued = find_lexicon(f"xxz{entry} yy", name)
                assert not any(h.phrase == entry for h in glued), f"{name}/{language}: {entry!r} matched after a letter"


def test_lexicon_matching_folds_case_accents_and_typographic_apostrophes():
    assert find_lexicon("SOLDE D’OUVERTURE", "opening_balance")
    assert find_lexicon("solde de cloture", "closing_balance")
    assert find_lexicon("SALDO INICIAL", "opening_balance")
    assert find_lexicon("Pagina 1 de 2", "period_phrase") == []


def test_the_zero_activity_vocabulary_is_the_sibling_omission_vocabulary_verbatim():
    """The literal strings were copied by hand from
    `analysis/sibling_omission.py::DORMANCY_DECLARATIONS` (the card's rule:
    never import). This is the drift tripwire: the two must stay equal."""
    from analysis.sibling_omission import DORMANCY_DECLARATIONS  # a TEST-side import; layout/ never imports analysis

    assert [p.pattern for p in ZERO_ACTIVITY_PATTERNS] == [p.pattern for p in DORMANCY_DECLARATIONS]
    assert [p.flags for p in ZERO_ACTIVITY_PATTERNS] == [p.flags for p in DORMANCY_DECLARATIONS]
    assert find_zero_activity("No Transactions This Period") is not None
    assert find_zero_activity("there were no transactions this period.") is not None
    assert find_zero_activity("no transactions") is None


# ---------------------------------------------------------------------------
# no issuer string, ever (mutant M9)
# ---------------------------------------------------------------------------

def test_no_issuer_string_anywhere_in_layout():
    offenders = []
    for path in sorted(LAYOUT_DIR.glob("*.py")):
        offenders.extend(_unregistered_issuer_markers(path, registered=set()))
    assert offenders == [], offenders


def test_the_issuer_scan_would_see_an_issuer_string_added_to_a_lexicon(tmp_path):
    """M9 reproduced against the scanner: a lexicon tuple that grows an
    issuer name is caught by the same function the guard uses."""
    mutant = tmp_path / "signals.py"
    mutant.write_text(
        'LEXICONS = {"opening_balance": {"en": ("beginning balance", "wells fargo", "opening balance")}}\n',
        encoding="utf-8",
    )
    hits = _issuer_string_hits(mutant)
    assert hits and hits[0][2] == "wells fargo"
    assert _unregistered_issuer_markers(mutant, registered=set())


def test_the_oq2_pattern_scans_reach_layout():
    """Case 24: the roots append. The OQ2 scope builder must list every
    `layout/*.py` module, so the year / account-number / amount / calendar /
    mojibake scans in `tests/test_no_statement_hardcodes.py` run over it."""
    scoped = {path.resolve() for path in _paddle_phase21_modules()}
    for name in ("__init__.py", "signals.py", "document_class.py", "refusals.py"):
        assert (LAYOUT_DIR / name).resolve() in scoped, f"layout/{name} is outside the OQ2 scan scope"


# ---------------------------------------------------------------------------
# token shapes: money
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_cents", [
    ("1,234.56", 123456),
    ("$1,234.56", 123456),
    ("1234.56", 123456),
    ("0.99", 99),
    ("-25.00", -2500),
    ("(25.00)", -2500),
    ("25.00-", -2500),
    ("25.00 CR", 2500),
    ("1 234,56", 123456),
    ("1 234,56", 123456),
    ("1.234,56", 123456),
    ("12,50", 1250),
    ("US$ 3.00", 300),
    ("€ 1.234,56", 123456),
    ("12 345 678,90", 1234567890),
])
def test_money_shapes_parse_to_cents(text, expected_cents):
    tokens = find_money(f"label {text} tail")
    assert len(tokens) == 1, (text, tokens)
    assert tokens[0].cents == expected_cents
    assert money_cents(text) == expected_cents


@pytest.mark.parametrize("text", [
    "1,234", "3.5", "12.345", "12.345.67", "1.2.3", "2031-03-01", "555-0100", "34.9999", "1,234.5", "0.000668",
    "page 12", "12/31", "1234567890", "#1001",
])
def test_non_money_shapes_do_not_parse(text):
    assert find_money(f"label {text} tail") == [], text
    assert money_cents(text) is None


def test_money_tokens_carry_their_spans():
    text = "Beginning Balance 1,234.56 and 78.90"
    tokens = find_money(text)
    assert [text[t.start:t.end] for t in tokens] == ["1,234.56", "78.90"]


def test_money_regex_has_no_literal_calendar_or_amount_constant():
    # The shape regexes are written with quantifier braces, never digit pairs
    # welded into the pattern (the OQ2 calendar scan's class of defect).
    assert not re.search(r"(?<![\d\\{,])\d{2}(?![\d}])", MONEY_RE.pattern)
    assert not re.search(r"(?<![\d\\{,])\d{2}(?![\d}])", DATE_RE.pattern)


# ---------------------------------------------------------------------------
# token shapes: dates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,ymd", [
    ("2031-03-05", (2031, 3, 5)),
    ("03/05/2031", (2031, 3, 5)),
    ("03/05/31", (2031, 3, 5)),
    ("3/5/2031", (2031, 3, 5)),
    ("03-05-2031", (2031, 3, 5)),
    ("05.03.2031", (2031, 3, 5)),
    ("March 5, 2031", (2031, 3, 5)),
    ("Mar 5 2031", (2031, 3, 5)),
    ("5 mars 2031", (2031, 3, 5)),
    ("5 de marzo de 2031", (2031, 3, 5)),
    ("1er avril 2031", (2031, 4, 1)),
    ("31 déc. 2031", (2031, 12, 31)),
    ("Aug 09, 2032", (2032, 8, 9)),
])
def test_date_shapes_resolve(text, ymd):
    tokens = find_dates(f"on {text} we")
    assert len(tokens) == 1, (text, tokens)
    assert tokens[0].ymd() == ymd, (text, tokens[0])


@pytest.mark.parametrize("text,expected", [
    ("03/05", (None, 3, 5)),
    ("12/31", (None, 12, 31)),
])
def test_short_dates_are_dates_without_a_year(text, expected):
    tokens = find_dates(f"row {text} desc")
    assert len(tokens) == 1
    assert tokens[0].ymd() == expected


def test_a_hyphen_joined_date_range_yields_both_dates():
    """Review MINOR-11: a date touching the hyphen of a compact range is
    still a date when what follows the hyphen is itself a full date."""
    for text in ("03/01/31-03/31/31", "03/01/2031-03/31/2031", "01.03.2031-31.03.2031"):
        tokens = find_dates(text)
        assert len(tokens) == 2, (text, tokens)
    assert find_dates("12-345-6789") == []


def test_day_first_convention_resolves_ambiguous_numeric_dates():
    tokens = find_dates("05/03/2031", day_first=True)
    assert tokens[0].ymd() == (2031, 3, 5)
    tokens = find_dates("05/03/2031", day_first=False)
    assert tokens[0].ymd() == (2031, 5, 3)
    tokens = find_dates("25/03/2031", day_first=False)   # 25 cannot be a month: the shape forces day-first
    assert tokens[0].ymd() == (2031, 3, 25)


@pytest.mark.parametrize("text", ["1.25", "12-345", "13/45", "0/0", "1/2/3/4", "2031", "800-555-0100", "12/2031", "1-2"])
def test_non_dates_do_not_parse(text):
    assert find_dates(f"x {text} y") == [], text


# ---------------------------------------------------------------------------
# MICR, page markers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "⑆111111111⑆ 2222222222⑈ 1001",
    "|111111111| 2222222222; 1001",
    ":111111111: 2222222222: 1001",
    "c111111111c 22222222222c",
    "a111111111a 2222222222c 1001",
])
def test_micr_shaped_lines(text):
    assert is_micr_shaped(text)


@pytest.mark.parametrize("text", [
    "Account 111111111 2222222222",
    "03/05/2031 2222222222 1001",
    "555 0100 800 1234",
    "1111 2222 3333 4444",
    "111111111 2222222222 1001",    # bare numbers with no MICR symbol: a statement's own reference numbers
    "2031-03-05 1234567890 123456",  # review MINOR-5: a date beside an account number is not a MICR line
    "03-05-2031 1234567890 123456",
    "1234567890 123456 2031-03-05",
    "12.345.678 1234567890",
    "123456789-1234567890",
    "2222222222",
    "",
    "Page 1 of 2",
])
def test_non_micr_lines(text):
    assert not is_micr_shaped(text)


@pytest.mark.parametrize("text,expected", [
    ("Page 1 of 3", (1, 3, "en")),
    ("page 2/3", (2, 3, "en")),
    ("Page: 3 of 3", (3, 3, "en")),
    ("Page 1 de 3", (1, 3, "fr")),
    ("Page 2 sur 3", (2, 3, "fr")),
    ("Página 1 de 3", (1, 3, "es")),
    ("Pagina 2 de 3", (2, 3, "es")),
])
def test_page_markers_in_three_languages(text, expected):
    marker = find_page_marker(f"footer {text} end")
    assert marker is not None
    assert (marker.number, marker.total, marker.language) == expected


@pytest.mark.parametrize("text", ["Page 1", "Pages 1-3", "page of", "1 of 3", "Page 0 of 3", "Page 4 of 3"])
def test_non_markers(text):
    assert find_page_marker(text) is None


# ---------------------------------------------------------------------------
# determinism of the primitives
# ---------------------------------------------------------------------------

def test_primitives_are_deterministic_and_ordered_by_position():
    text = "Ending Balance 10.00 Beginning Balance 20.00 03/05/2031 03/06/2031"
    assert find_money(text) == find_money(text)
    assert [t.start for t in find_money(text)] == sorted(t.start for t in find_money(text))
    assert [t.start for t in find_dates(text)] == sorted(t.start for t in find_dates(text))
    hits = find_lexicon(text, "closing_balance") + find_lexicon(text, "opening_balance")
    assert hits == find_lexicon(text, "closing_balance") + find_lexicon(text, "opening_balance")


def test_signals_module_declares_its_own_grammars_and_says_why():
    doc = signals.__doc__ or ""
    assert "analysis/money.py" in doc and "analysis/date_tokens.py" in doc
    assert "LayoutModel" in doc
