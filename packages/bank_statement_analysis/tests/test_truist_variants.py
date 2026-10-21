"""Truist Checks-table families (W3 Track A, cell `truist x {detail_coverage,
ledger_identity}`).

Every document below is synthetic and built from the PRINTED GRID: the Account
summary line, the `DATE CHECK # AMOUNT($)` column groups of the Checks table and
its printed total, and the two description sections. No fixture carries a real
customer, account, amount or date, and no rule under test is keyed on one.

The cell's root cause is a single printed-grid fact the reader did not admit:
Truist emits its currency symbol as its own cell, so `Total checks` arrives
either as `= $662.35` or as `= $ 662.35`. The section pattern required the tight
spelling, so on the 20 cell documents the Checks table was never found and every
cheque in it was silently dropped from the ledger — while the stated totals,
which come from the Account summary, still counted them.
"""
from __future__ import annotations

import pytest

from analysis.truist import parse_truist_statement

ACCOUNT_LINE = "TRUIST DYNAMIC BUSINESS CHECKING - CORE TIER 1110023054594"
CHECK_HEADER_1 = "DATE CHECK # AMOUNT($)"
CHECK_HEADER_3 = " ".join([CHECK_HEADER_1] * 3)

OTHER_SECTION = (
    "Other withdrawals, debits and service charges DATE DESCRIPTION AMOUNT($) "
    "02/02 A COUNTERPARTY PAYMENT 200.00 "
    "Total other withdrawals, debits and service charges = $200.00\n"
)
DEPOSIT_SECTION = (
    "Deposits, credits and interest DATE DESCRIPTION AMOUNT($) "
    "02/05 A COUNTERPARTY DEPOSIT 500.00 "
    "Total deposits, credits and interest = $500.00\n"
)


def document(*, checks_section: str, checks_total: str = "300.00",
             new_balance: str = "1,000.00") -> str:
    return (
        "Your account statement\n"
        f"{ACCOUNT_LINE}\n"
        "Account summary Your previous balance as of 01/30/2054 $1,000.00 "
        f"Checks - {checks_total} "
        "Other withdrawals, debits and service charges - 200.00 "
        "Deposits, credits and interest + 500.00 "
        f"Your new balance as of 02/27/2054 = ${new_balance}\n"
        f"{checks_section}"
        f"{OTHER_SECTION}"
        f"{DEPOSIT_SECTION}"
    )


def amounts(stmt) -> list[float]:
    return [t.amount for t in stmt.transactions]


def descriptions(stmt) -> list[str]:
    return [t.description for t in stmt.transactions]


# --------------------------------------------------------------------------
# T-F1  the currency symbol printed as its own cell
# --------------------------------------------------------------------------

SPACED_TOTAL_DOC = document(checks_section=(
    f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 02/23 1002 200.00 "
    "Total checks = $ 662.35\n").replace("662.35", "300.00"))
TIGHT_TOTAL_DOC = document(checks_section=(
    f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 02/23 1002 200.00 "
    "Total checks = $300.00\n"))


@pytest.mark.parametrize("doc", [SPACED_TOTAL_DOC, TIGHT_TOTAL_DOC],
                         ids=["symbol apart from the figure", "symbol against the figure"])
def test_f1_the_checks_table_is_read_whichever_way_the_currency_symbol_is_printed(doc):
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [-100.00, -200.00, -200.00, 500.00]


def test_f1_the_two_spellings_produce_the_identical_statement():
    spaced = parse_truist_statement(SPACED_TOTAL_DOC)
    tight = parse_truist_statement(TIGHT_TOTAL_DOC)
    assert spaced.model_dump() == tight.model_dump()


def test_f1_the_ledger_satisfies_the_banks_own_summary_identity():
    stmt = parse_truist_statement(SPACED_TOTAL_DOC)
    activity = sum(t.amount for t in stmt.transactions)
    assert round(stmt.beginning_balance + activity, 2) == stmt.ending_balance


# --------------------------------------------------------------------------
# T-F2  the skip marker printed apart from the check number
# --------------------------------------------------------------------------

def test_f2_a_detached_skip_marker_still_belongs_to_its_check_number():
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 02/23 * 1003 200.00 "
        "Total checks = $ 300.00 "
        "* indicates a skip in sequential check numbers above this item\n"))
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [-100.00, -200.00, -200.00, 500.00]
    assert descriptions(stmt)[:2] == ["Check 1001", "Check *1003"]


def test_f2_an_attached_skip_marker_is_unchanged():
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 02/23 *1003 200.00 "
        "Total checks = $300.00\n"))
    stmt = parse_truist_statement(doc)
    assert descriptions(stmt)[:2] == ["Check 1001", "Check *1003"]


def test_f2_negative_the_skip_footnote_is_never_a_row():
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 300.00 "
        "Total checks = $ 300.00 "
        "* indicates a skip in sequential check numbers above this item\n"))
    stmt = parse_truist_statement(doc)
    assert amounts(stmt) == [-300.00, -200.00, 500.00]


# --------------------------------------------------------------------------
# T-F3  a cheque the bank printed no number for
# --------------------------------------------------------------------------

def test_f3_a_cheque_with_no_printed_number_is_still_a_cheque():
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 100.00 02/23 * 9253259 200.00 "
        "Total checks = $ 300.00 "
        "* indicates a skip in sequential check numbers above this item\n"))
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [-100.00, -200.00, -200.00, 500.00]
    assert descriptions(stmt)[:2] == ["Check", "Check *9253259"]


def test_f3_a_skip_marker_with_no_number_beside_it():
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 100.00 02/23 * 200.00 "
        "Total checks = $ 300.00\n"))
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [-100.00, -200.00, -200.00, 500.00]
    assert descriptions(stmt)[:2] == ["Check", "Check *"]


# --------------------------------------------------------------------------
# T-F4  one column group instead of three
# --------------------------------------------------------------------------

def test_f4_a_three_column_checks_header_is_read():
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_3} 02/24 1001 100.00 02/23 1002 150.00 02/22 1004~ 50.00 "
        "Total checks = $300.00\n"))
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [-100.00, -150.00, -50.00, -200.00, 500.00]
    assert descriptions(stmt)[2] == "Check 1004~"


def test_f4_a_single_column_checks_header_is_read():
    stmt = parse_truist_statement(SPACED_TOTAL_DOC)
    assert stmt is not None
    assert len([t for t in stmt.transactions if t.description.startswith("Check")]) == 2


# --------------------------------------------------------------------------
# T-F5  the printed total is the gate
# --------------------------------------------------------------------------

def test_f5_negative_checks_that_do_not_reproduce_the_printed_total_fail_closed():
    """The Checks table prints its own total, so the cheques are checkable
    against the bank rather than against the residue of two other figures. A
    reading that does not reproduce it publishes nothing."""
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 "
        "Total checks = $ 300.00\n"))
    assert parse_truist_statement(doc) is None


def test_f5_negative_a_statement_with_no_checks_table_is_unaffected():
    doc = document(checks_section="", checks_total="0.00", new_balance="1,300.00")
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert amounts(stmt) == [-200.00, 500.00]


# --------------------------------------------------------------------------
# MONEYFIX-1 card T — the Account summary's activity rows admit the symbol
#
# `_DOLLAR` exists because Truist prints its currency symbol as its own cell,
# and its docstring says every money pattern in the module admits it. Three
# did not: the summary's `Checks`, `Other withdrawals...` and `Deposits...`
# rows. The summary is the parser's entry gate — `_summary()` returning None
# returns None for the whole statement — so unlike T-F1, which lost a section,
# this lost the DOCUMENT. (F-MONEYFMT finding 4.)
# --------------------------------------------------------------------------

#: The grammar those three rows carried BEFORE the fix, quoted verbatim.
PRE_FIX_ACTIVITY_ROWS_RE = (
    r"Checks\s+-\s+([\d,]+\.\d{2})\s+"
    r"Other withdrawals, debits and service charges\s+-\s+([\d,]+\.\d{2})\s+"
    r"Deposits, credits and interest\s+\+\s+([\d,]+\.\d{2})"
)

T_CHECKS_SECTION = (
    f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 02/23 1002 200.00 "
    "Total checks = $300.00\n"
)


def summary_document(checks_cell: str, other_cell: str, deposits_cell: str) -> str:
    """The same document as `document()`, with the three activity cells free."""
    return (
        "Your account statement\n"
        f"{ACCOUNT_LINE}\n"
        "Account summary Your previous balance as of 01/30/2054 $1,000.00 "
        f"Checks - {checks_cell} "
        f"Other withdrawals, debits and service charges - {other_cell} "
        f"Deposits, credits and interest + {deposits_cell} "
        "Your new balance as of 02/27/2054 = $1,000.00\n"
        f"{T_CHECKS_SECTION}{OTHER_SECTION}{DEPOSIT_SECTION}"
    )


def test_t_pre_fix_the_activity_rows_refused_the_symbol_cell_beside_them():
    """The defect, in process: one printed grid, two different readings."""
    import re

    from analysis.truist import _DOLLAR

    spelled = ("Checks - $ 300.00 "
               "Other withdrawals, debits and service charges - $ 200.00 "
               "Deposits, credits and interest + $ 500.00")

    # Before the fix: no match, so `_summary` returned None for the document.
    assert re.search(PRE_FIX_ACTIVITY_ROWS_RE, spelled, re.IGNORECASE) is None
    # After: the module's own gap-tolerant pattern, applied as documented.
    fixed = (
        r"Checks\s+-\s+" + _DOLLAR + r"([\d,]+\.\d{2})\s+"
        r"Other withdrawals, debits and service charges\s+-\s+" + _DOLLAR
        + r"([\d,]+\.\d{2})\s+"
        r"Deposits, credits and interest\s+\+\s+" + _DOLLAR + r"([\d,]+\.\d{2})"
    )
    assert re.search(fixed, spelled, re.IGNORECASE).groups() == ("300.00", "200.00", "500.00")


@pytest.mark.parametrize("spelling", ["300.00", "$300.00", "$ 300.00"],
                         ids=["no symbol", "symbol against the figure",
                              "symbol as its own cell"])
def test_t_the_summary_is_read_whichever_way_the_symbol_is_printed(spelling):
    other = spelling.replace("300.00", "200.00")
    deposits = spelling.replace("300.00", "500.00")
    stmt = parse_truist_statement(summary_document(spelling, other, deposits))
    assert stmt is not None
    assert stmt.stated_total_debits == 500.00
    assert stmt.stated_total_credits == 500.00
    assert amounts(stmt) == [-100.00, -200.00, -200.00, 500.00]


def test_t_the_symbol_bearing_document_is_the_symbol_less_one():
    """Cosmetic means cosmetic: not one published field may differ."""
    plain = parse_truist_statement(summary_document("300.00", "200.00", "500.00"))
    spaced = parse_truist_statement(summary_document("$ 300.00", "$ 200.00", "$ 500.00"))
    assert plain is not None and spaced is not None
    assert spaced.model_dump() == plain.model_dump()


def test_t_negative_a_row_carrying_no_figure_still_withholds_the_document():
    """`_DOLLAR` admits the symbol, not the absence of the amount."""
    assert parse_truist_statement(summary_document("$", "200.00", "500.00")) is None


# --------------------------------------------------------------------------
# MONEYFIX-1 card T2 — a note ABOUT the Checks table is not a row of it
#
# The Checks table has three columns and prints no words in any of them. The
# sequence-gap note prints a date, a cheque number and an amount in that
# order — `Gap in check sequence 02/28 1099 0.00` — so the row pattern matched
# it wherever it appeared and it WOULD have been published as `Check 1099` for -0.00 (latent for truist), at
# approved/clear. Truist has no count oracle (`count_semantics` UNSURVEYED,
# correctly), so nothing downstream saw the phantom row. (F-STRUCTURE #4.)
#
# The discriminator is the printed grid, not the words: a row may follow only
# cells, or a page break, which the bank closes by REPRINTING the column
# header. Measured over the whole truist population (33 documents printing a
# Checks table, 532 rows), the only text ever standing between two rows is a
# numbers-only `~` cross-reference cell or that reprinted header — and no
# genuine cheque is printed for 0.00.
# --------------------------------------------------------------------------

GAP_NOTE = "Gap in check sequence 02/28 1099 0.00 "


def gap_document(note: str = GAP_NOTE) -> str:
    return document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 02/23 1002 200.00 "
        f"{note}Total checks = $300.00\n"))


def test_t2_pre_fix_the_row_pattern_matched_the_note_and_booked_it():
    """The defect, in process: the pattern alone cannot tell the two apart."""
    from analysis.truist import _CHECK_ROW_RE

    found = _CHECK_ROW_RE.findall(
        "02/24 1001 100.00 02/23 1002 200.00 " + GAP_NOTE)
    assert [(m[0], m[2].strip(), m[3]) for m in found] == [
        ("02/24", "1001", "100.00"),
        ("02/23", "1002", "200.00"),
        ("02/28", "1099", "0.00"),   # <- the phantom cheque, pre-fix
    ]


def test_t2_the_sequence_gap_note_is_not_published_as_a_cheque():
    stmt = parse_truist_statement(gap_document())
    assert stmt is not None
    assert descriptions(stmt) == [
        "Check 1001", "Check 1002", "A COUNTERPARTY PAYMENT", "A COUNTERPARTY DEPOSIT",
    ]
    assert 0.0 not in amounts(stmt)


def test_t2_the_note_changes_nothing_else_about_the_document():
    with_note = parse_truist_statement(gap_document())
    without = parse_truist_statement(gap_document(note=""))
    assert with_note is not None and without is not None
    assert with_note.model_dump() == without.model_dump()


@pytest.mark.parametrize("note", [
    "Gap in check sequence 02/28 1099 0.00 ",
    "Missing check numbers 02/28 1099 25.00 ",
    "See reverse for check images 02/28 1099 25.00 ",
], ids=["zero-amount gap note", "note carrying a real-looking figure",
        "an unrelated printed note"])
def test_t2_any_note_carrying_a_row_shaped_figure_is_refused(note):
    """The rule is the grid, not the wording: no blocklist of phrases.

    The second and third notes carry 25.00, so booking them would ALSO break
    the printed total and withhold the document — which is the fail-closed
    half of the same rule.
    """
    stmt = parse_truist_statement(gap_document(note=note))
    if stmt is None:
        return
    assert "Check 1099" not in descriptions(stmt)


def test_t2_negative_rows_resuming_after_a_page_break_are_still_rows():
    """The one interruption the table really prints. The bank closes a page
    break by reprinting the column header, and the cheques after it are
    cheques — dropping them would break the printed total and withhold two
    archive documents that validate today."""
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 "
        "continued\nPAGE  1  OF  8 0185530\n\n--- Page 2 ---\n\n"
        f"{ACCOUNT_LINE} (continued) {CHECK_HEADER_3} "
        "02/23 1002 200.00 "
        "Total checks = $300.00\n"))
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert descriptions(stmt)[:2] == ["Check 1001", "Check 1002"]
    assert amounts(stmt) == [-100.00, -200.00, -200.00, 500.00]


def test_t2_negative_the_numbers_only_cross_reference_cell_is_unaffected():
    """`05/26 1645~` prints no amount: it is a pointer into the other section.
    It carries no words, so the rule never looks at it, and the cheque printed
    after it is still read."""
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 02/26 1645~ 02/23 1002 200.00 "
        "Total checks = $300.00\n"))
    stmt = parse_truist_statement(doc)
    assert stmt is not None
    assert descriptions(stmt)[:2] == ["Check 1001", "Check 1002"]


def test_t2_negative_a_note_that_swallows_a_real_cheque_withholds_the_document():
    """The safety argument for skipping rather than fabricating: the table's
    own printed total is the oracle. A note that swallowed a genuine cheque
    cannot reproduce it, so the document is withheld, never shipped short."""
    doc = document(checks_section=(
        f"Checks {CHECK_HEADER_1} 02/24 1001 100.00 "
        "Gap in check sequence 02/23 1002 200.00 "
        "Total checks = $300.00\n"))
    assert parse_truist_statement(doc) is None
