"""Structurer mechanism: tokens, rows, columns, summary, geometry.

The safety properties live in `tests/test_structurer_safety.py`; this module
tests the parts, so that a failure says which part broke. Every document here
is synthetic — invented institutions, invented amounts.
"""
from __future__ import annotations

import pytest

from analysis.date_tokens import PERIOD_DASH
from analysis.money import MINUS_GLYPHS, parse_money
from analysis.structurer import geometry_from_pdf, structure_document
from analysis.structurer.geometry import DocumentGeometry, GeoLine, PageGeometry, Word
from analysis.structurer.rows import (
    MIN_CHAIN_AGREEMENT,
    build_rows,
    source_lines_from_geometry,
    source_lines_from_text,
)
from analysis.structurer.summary import read_period, read_summary
from analysis.structurer.tokens import document_year, money_tokens, money_value, read_date


# ===========================================================================
# Tokens
# ===========================================================================

@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("2026-03-05", "2026-03-05"),
        ("03/05/2026", "2026-03-05"),
        ("3/5/26", "2026-03-05"),
        ("03-05-2026", "2026-03-05"),
        ("Mar 5, 2026", "2026-03-05"),
        ("MAR 5 2026", "2026-03-05"),
        ("5 Mar 2026", "2026-03-05"),
        ("March 5, 2026", "2026-03-05"),
        ("mars 5, 2026", "2026-03-05"),
    ],
)
def test_every_supported_date_shape_reads_to_the_same_day(token, expected):
    """A structurer cannot ask which shape a bank uses; it reads them all."""
    assert read_date(token, default_year=None) == expected


@pytest.mark.parametrize("token", ["13/45/24", "42/13", "00/00/00", "02/30/2026", "Foo 5, 2026"])
def test_a_shaped_but_impossible_date_is_not_a_date(token):
    assert read_date(token, default_year=2026) is None


def test_a_year_less_token_needs_a_year_from_the_document():
    assert read_date("03/05", default_year=None) is None
    assert read_date("03/05", default_year=2026) == "2026-03-05"


def test_the_document_year_is_the_majority_year_the_document_prints():
    lines = ["opened 01/02/2019", "period 03/01/2026 to 03/31/2026", "Mar 5, 2026 payment"]
    assert document_year(lines) == 2026


def test_the_document_year_is_never_the_current_year():
    """A statement is a historical record. Dating its rows to today produces a
    document that reconciles against nothing."""
    assert document_year(["no dates here at all"]) is None


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1,234.56", 1234.56),
        ("$1,234.56", 1234.56),
        ("(1,234.56)", -1234.56),
        ("1,234.56-", -1234.56),
        ("-1,234.56", -1234.56),
        # The two non-ASCII glyphs the archive attests in a sign position. Both
        # read POSITIVE before W3 §SIGNREADER: the tokenizer admitted ASCII
        # only, so the sign fell outside the token, and `money_value` then
        # `abs()`-ed away the sign `parse_money` had recovered.
        ("−1,234.56", -1234.56),   # U+2212 MINUS SIGN
        ("–1,234.56", -1234.56),   # U+2013 EN DASH
        ("1,234.56−", -1234.56),
        ("1,234.56–", -1234.56),
        ("−$1,234.56", -1234.56),
        ("(−1,234.56)", -1234.56),
        # U+2014 EM DASH is punctuation, not a sign (W3 §MGD MGD3): the one
        # archive document that prints one before a bare figure prints a
        # POSITIVE running balance behind an empty-column placeholder.
        ("—1,234.56", 1234.56),
    ],
)
def test_money_is_read_with_its_printed_sign(text, value):
    tokens = money_tokens(f"ROW DESCRIPTION {text} END")
    assert [token.value for token in tokens] == [value]


def test_a_bare_integer_is_not_money():
    """Check numbers, item counts and reference ids are not amounts."""
    assert money_tokens("CHECK 4021 REF 99887766") == []


# --- the sign class: one differential against the shared grammar -----------
#
# The structurer is the generic unclaimed-layout reader, so this is the sign
# rule for every document no registration claims. It must be the SHARED rule
# and not a private opinion, and the five tests below are what say so. Each
# parametrizes over `money.MINUS_GLYPHS` rather than over a literal, so the
# ASCII case is deliberately included — a canon that grows a member grows this
# differential on the same day, and the day it does the ASCII row is the
# reference the new one is compared against.

#: Every shape a sign can take on a token this tokenizer produces, written
#: with a placeholder the parametrization fills with each glyph of the canon.
SIGN_SHAPES = ("%s1,234.56", "1,234.56%s", "%s$1,234.56", "%s 1,234.56", "(%s1,234.56)")


@pytest.mark.parametrize("glyph", list(MINUS_GLYPHS))
@pytest.mark.parametrize("shape", SIGN_SHAPES)
def test_the_sign_is_the_shared_grammars_answer(shape, glyph):
    """Every glyph of `money.MINUS_GLYPHS` reads exactly as ASCII does here.

    The differential is against the canon rather than against a literal: the
    class is `analysis.money`'s, and a glyph added there is tested here the day
    it is added. `money_value` of a U+2212 or U+2013 amount was POSITIVE where
    `parse_money` was negative — it called the shared grammar and discarded the
    answer (W3 §MGD MGD10 finding 1).
    """
    assert money_value(shape % glyph) == money_value(shape % "-")


@pytest.mark.parametrize("glyph", list(MINUS_GLYPHS))
def test_the_reader_and_the_shared_parser_agree_on_every_sign_glyph(glyph):
    """Where `parse_money` reads the shape at all, the two must not disagree.

    The three shapes it does not read are the ones this reader owns and are
    excluded deliberately, not overlooked: parentheses (the accounting negative
    — `parse_money` is paren-blind), a sign separated from its digits by a
    space, and a sign before a currency mark. Each is a local rule of the
    TOKEN GRAMMAR above, each behaves identically for ASCII and for every glyph
    of the canon, and none of them is a second opinion about what a minus is.
    """
    for shape in ("%s1,234.56", "1,234.56%s"):
        assert money_value(shape % glyph) == parse_money(shape % glyph) == -1234.56


@pytest.mark.parametrize("glyph", list(MINUS_GLYPHS))
def test_the_tokenizer_carries_the_sign_inside_the_token(glyph):
    """The sign is part of the amount, not of the description beside it.

    Before the fix the glyph fell outside the match: the token was the bare
    digits, `MoneyToken.start` pointed at the first digit rather than at the
    sign, and the leftover glyph stayed in the row's description. Extent is
    load-bearing downstream — `rows._money_columns` clusters money bands by
    `token.start`, and `_collect` scrubs `token.text` out of the description.
    """
    token, = money_tokens(f"03/05 VENDOR CO {glyph}1,234.56 END")
    assert token.text.startswith(glyph)
    assert token.value == -1234.56


@pytest.mark.parametrize("glyph", list(MINUS_GLYPHS))
def test_a_sign_glyph_between_two_amounts_reads_as_ascii_does(glyph):
    """The lookbehind and the token class widen together or the reader breaks.

    `1,000.00-500.00` is a hyphenated pair, and ASCII yields exactly one token
    from it — the trailing-minus branch is refused by the digit lookahead, and
    the right-hand amount is refused by the lookbehind. Widening the token
    without the lookbehind would have manufactured a second token from the
    right-hand half for the non-ASCII glyphs only.
    """
    assert [t.value for t in money_tokens(f"REF 1,000.00{glyph}500.00 END")] == \
           [t.value for t in money_tokens("REF 1,000.00-500.00 END")] == [1000.0]


def test_the_em_dash_stays_punctuation_for_the_generic_reader_too():
    """W3 §MGD MGD3, applied where it matters most.

    The generic reader meets every layout, including the three-column daily
    balance grid whose empty cell is an em dash. That document prints a
    POSITIVE running balance behind the placeholder, and admitting the glyph
    would flip a figure the bank printed positive.
    """
    tokens = money_tokens("03-16 — 39,692.35   03-26 34,167.30")
    assert [token.value for token in tokens] == [39692.35, 34167.30]


# ===========================================================================
# Rows, columns and signs
# ===========================================================================

LEDGER = """--- Page 1 ---
Statement period 03/01/2026 to 03/31/2026
Beginning balance 1,000.00
Ending balance 1,010.00
03/05 COFFEE ROASTERS LLC 25.00 975.00
03/06 ACME REMITTANCE 100.00 1,075.00
03/07 GRINDER SERVICE CO 5.00 1,070.00
03/08 WIDGET CO 30.00 1,040.00
03/09 GLOBEX INVOICE 20.00 1,020.00
03/10 INITECH REFUND 10.00 1,030.00
03/11 UMBRELLA SUPPLY 20.00 1,010.00
"""


def test_signs_come_from_the_balance_chain():
    outcome = structure_document(LEDGER)

    assert outcome.chained is True
    assert outcome.chain_agreement >= MIN_CHAIN_AGREEMENT
    assert outcome.sign_sources == {"balance_chain": 7}
    assert [t.amount for t in outcome.statement.transactions] == [
        -25.0, 100.0, -5.0, -30.0, -20.0, 10.0, -20.0
    ]


#: The same ledger overdrawn, printing its negative balances with the two
#: non-ASCII glyphs the archive attests — U+2212 on three lines and U+2013 on
#: one, which is exactly how one issuer's generator behaves month to month
#: (W3 §MGD). Nothing else about the document is unusual.
OVERDRAWN_LEDGER = """--- Page 1 ---
Statement period 03/01/2026 to 03/31/2026
Beginning balance 1,000.00
Ending balance −331.00
03/05 ALPHA SUPPLY CO 211.00 789.00
03/06 BRAVO LOGISTICS 322.00 467.00
03/07 CHARLIE FOODS 433.00 34.00
03/08 DELTA POWER AND LIGHT 144.00 −110.00
03/09 ECHO WATER WORKS 155.00 –265.00
03/10 FOXTROT GAS SUPPLY 66.00 −331.00
"""


def test_an_overdrawn_ledger_printed_with_true_minus_signs_is_read_whole():
    """The sign defect's document-level shape, end to end.

    Reading `−110.00` as +110.00 does not merely mis-state one figure: the
    balance chain stops explaining the rows, so agreement falls under the
    threshold, no row can be signed and the rung refuses the document —
    `no_signable_rows`, on a statement whose arithmetic is perfectly sound.
    The printed ending balance is inverted in the same breath, so even a
    chained reading would fail the ledger-completeness check.
    """
    outcome = structure_document(OVERDRAWN_LEDGER)

    assert outcome.reason == "structured"
    assert outcome.chained is True
    assert outcome.sign_sources == {"balance_chain": 6}
    assert [t.amount for t in outcome.statement.transactions] == [
        -211.0, -322.0, -433.0, -144.0, -155.0, -66.0
    ]
    assert outcome.statement.ending_balance == -331.0
    assert [t.running_balance for t in outcome.statement.transactions] == [
        789.0, 467.0, 34.0, -110.0, -265.0, -331.0
    ]


def test_signs_come_from_the_section_heading_when_there_is_no_balance_column():
    document = """--- Page 1 ---
Statement period 03/01/2026 to 03/31/2026
Beginning balance 1,000.00
Ending balance 1,100.00
Deposits and other credits
03/05 ACME REMITTANCE 60.00
03/06 GLOBEX REMITTANCE 90.00
Withdrawals and other debits
03/07 GRINDER SERVICE CO 20.00
03/08 UMBRELLA SUPPLY 30.00
"""
    outcome = structure_document(document)

    assert outcome.chained is False
    assert outcome.sign_sources == {"section_heading": 4}
    assert [t.amount for t in outcome.statement.transactions] == [60.0, 90.0, -20.0, -30.0]


def test_a_continuation_line_extends_the_previous_description():
    document = LEDGER.replace(
        "03/06 ACME REMITTANCE 100.00 1,075.00",
        "03/06 ACME REMITTANCE 100.00 1,075.00\nINVOICE 4471 SETTLEMENT",
    )
    outcome = structure_document(document)

    described = [t.description for t in outcome.statement.transactions if "ACME" in t.description]
    assert described and "INVOICE 4471 SETTLEMENT" in described[0]


def test_a_line_carrying_money_is_never_swallowed_as_a_continuation():
    """Swallowing it would hide a row we failed to recognise — the difference
    between an incomplete ledger and a visible refusal."""
    document = LEDGER.replace(
        "03/06 ACME REMITTANCE 100.00 1,075.00",
        "03/06 ACME REMITTANCE 100.00 1,075.00\nUNRECOGNISED ROW 44.00",
    )
    outcome = structure_document(document)

    assert all("44.00" not in t.description for t in outcome.statement.transactions)


def test_rows_are_not_found_without_a_year_anywhere_in_the_document():
    document = LEDGER.replace("Statement period 03/01/2026 to 03/31/2026", "Statement period")
    outcome = structure_document(document)

    assert outcome.statement is None
    assert outcome.reason in {"no_dated_rows", "no_printed_period"}


# ===========================================================================
# Summary and period
# ===========================================================================

def test_summary_values_are_read_with_their_labels_and_provenance():
    lines = source_lines_from_text(LEDGER)
    summary = read_summary(lines)

    assert summary["beginning_balance"].value == 1000.0
    assert summary["ending_balance"].value == 1010.0
    assert summary["beginning_balance"].label == "BEGINNING BALANCE"
    assert summary["beginning_balance"].page == 1


def test_a_value_far_from_its_label_is_not_that_label_s_value():
    """A wide page pairs a left-hand label with an unrelated right-hand figure
    unless distance is part of the rule. Distance is counted in characters of
    the flattened line — the only proxy available once a page is linearised,
    since runs of spaces are collapsed long before this code sees them.
    """
    lines = source_lines_from_text(
        "Ending balance" + " INTEREST RATE DISCLOSURE" * 6 + " 9,999.99\n"
        "Ending balance 1,010.00"
    )
    summary = read_summary(lines)

    assert summary["ending_balance"].value == 1010.00


def test_the_period_is_read_from_an_explicit_range():
    lines = source_lines_from_text(LEDGER)
    period = read_period(lines, read_summary(lines))

    assert (period.start, period.end, period.source) == ("2026-03-01", "2026-03-31", "range")


@pytest.mark.parametrize("separator", [*PERIOD_DASH.strip("[]"), "to", "through", "thru", "au", "until"])
def test_the_period_range_reads_every_separator_the_canon_admits(separator):
    """The dash half of this alternation is `date_tokens.PERIOD_DASH`, consumed
    rather than re-spelled.

    It was a fourth private range class (`-|–|—`) that had drifted from the
    canon by exactly U+2212 (W3 §MGD MGD10 finding 2). The words stay local
    because no shared constant claims them and a dash class that admitted
    "to" would be wrong for every consumer that embeds it between two amounts.

    Widening a RANGE class is the safe direction and the asymmetry with the
    SIGN class is deliberate: a glyph admitted here can only make a period line
    match, and the period is required, so an unrecognised range dash costs the
    whole document.
    """
    lines = source_lines_from_text(f"Statement period March 1, 2026 {separator} March 31, 2026")
    period = read_period(lines, {})

    assert (period.start, period.end) == ("2026-03-01", "2026-03-31")


def test_the_period_can_be_reconstructed_from_balance_anchors():
    """A large family of layouts never prints a range: it prints the two dates
    beside its opening and closing balances."""
    lines = source_lines_from_text(
        "Your balance forward on Jul 31, 2023 34,313.58\n"
        "Your closing balance on Aug 31, 2023 14,742.49\n"
    )
    period = read_period(lines, read_summary(lines))

    assert (period.start, period.end, period.source) == ("2023-08-01", "2023-08-31", "balance_anchors")


def test_a_forward_balance_anchor_starts_the_period_the_next_day():
    """"Balance forward on Jul 31" is the 31st's CLOSING balance. Reading it as
    the period start makes August 32 days long and every average built on it
    3% low."""
    lines = source_lines_from_text(
        "Balance forward on 07/31/2023 100.00\nClosing balance on 08/31/2023 200.00"
    )
    assert read_period(lines, read_summary(lines)).start == "2023-08-01"

    lines = source_lines_from_text(
        "Beginning balance on 08/01/2023 100.00\nEnding balance on 08/31/2023 200.00"
    )
    assert read_period(lines, read_summary(lines)).start == "2023-08-01"


@pytest.mark.parametrize("span", ["01/01/2026 to 01/02/2026", "01/01/2026 to 12/31/2026"])
def test_a_date_range_that_is_not_a_billing_cycle_is_not_a_period(span):
    lines = source_lines_from_text(f"Rate table {span}")
    assert read_period(lines, {}) is None


def test_period_detection_does_not_stall_on_a_pathological_line():
    """Regression: an unbounded month-name pattern backtracked quadratically,
    and one 20,000-character line took nine seconds to reject."""
    import time

    lines = source_lines_from_text("a" * 60_000)
    started = time.perf_counter()
    read_period(lines, {})
    assert time.perf_counter() - started < 1.0


# ===========================================================================
# Geometry
# ===========================================================================

def _line(page: int, index: int, cells: list[tuple[str, float]]) -> GeoLine:
    words = []
    text_parts: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = 0
    for position, (word, x) in enumerate(cells):
        if position:
            text_parts.append(" ")
            offset += 1
        words.append(Word(word, x, index * 10.0, x + 20.0, index * 10.0 + 8.0))
        spans.append((offset, offset + len(word)))
        text_parts.append(word)
        offset += len(word)
    return GeoLine(page, tuple(words), "".join(text_parts), tuple(spans))


def test_geometry_finds_rows_whose_date_is_not_at_the_start_of_the_line():
    """The 3a finding, as a test: a check number to the left of the date is
    fatal to flat text and irrelevant to geometry."""
    header = [
        _line(1, 0, [("Statement", 40.0), ("period", 90.0), ("03/01/2026", 140.0),
                     ("to", 200.0), ("03/31/2026", 220.0)]),
        _line(1, 1, [("Beginning", 40.0), ("balance", 90.0), ("1,000.00", 300.0)]),
        _line(1, 2, [("Ending", 40.0), ("balance", 90.0), ("1,010.00", 300.0)]),
    ]
    rows = []
    balances = [975.00, 1075.00, 1070.00, 1040.00, 1020.00, 1030.00, 1010.00]
    amounts = [25.00, 100.00, 5.00, 30.00, 20.00, 10.00, 20.00]
    for index, (amount, balance) in enumerate(zip(amounts, balances), start=3):
        rows.append(_line(1, index, [
            (f"40{index}", 40.0),                       # a check number, to the LEFT
            (f"03/{index + 2:02d}", 120.0),             # the date column
            (f"VENDOR{index}", 180.0),
            (f"{amount:,.2f}", 320.0),
            (f"{balance:,.2f}", 400.0),
        ]))
    geometry = DocumentGeometry((PageGeometry(1, 612.0, 792.0, tuple(header + rows)),))

    lines = source_lines_from_geometry(geometry)
    built = build_rows(lines, default_year=2026, opening_balance=1000.0)

    assert len(built.rows) == 7
    assert built.chained is True

    flat = build_rows(
        source_lines_from_text("\n".join(line.text for line in geometry.lines)),
        default_year=2026, opening_balance=1000.0,
    )
    assert not flat.rows, "flat text must fail here, or this test proves nothing"


def test_geometry_from_a_pdf_without_native_text_is_none():
    """A scanned page has pixels, not words. Inventing boxes from an image is
    the visual rung's job, not this one."""
    assert geometry_from_pdf(b"not a pdf at all") is None


def test_geometry_never_raises_on_a_malformed_pdf():
    assert geometry_from_pdf(b"%PDF-1.4\n garbage \n%%EOF") is None
