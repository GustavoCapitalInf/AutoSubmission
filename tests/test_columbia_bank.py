"""W3 §COLUMBIA5 — the Columbia Marketplace Checking cohort, read across a year.

Every document here is synthetic. The four archive statements that motivated
the extension are named by content sha in the branch log and in the commit
message; none of them is reproduced. The one exception is the daily-grid cell
`03-16 —  39,692.35`, which is quoted verbatim in two tests because it is the
archive's whole attestation for the em dash's exclusion from the sign class
(W3 §MGD3, whose own record quotes it, as does `tests/test_money.py`) and the
handoff asks for the refusal to be proven on that exact printing.

The template is a summary strip over five ledger sections, a daily grid and a
cheque grid, and each section closes with its own printed total. Those totals
are the reader's oracles: nothing is published until every section adds up to
the figure the bank printed under it and the section totals add up to the two
summary figures. Most tests here damage one thing and assert a REFUSAL,
because refusing is what this reader does with a scan it cannot vouch for.
"""
from __future__ import annotations

import re

import pytest

from analysis import columbia_bank as cb, parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401 — populates the registry


# ---------------------------------------------------------------------------
# One statement of the template, in the pieces a test can vary
# ---------------------------------------------------------------------------

MASTHEAD = (
    "April 30, 2026 Page: 1 of 4\n"
    "Customer Service:\n"
    "HOLDER NAME PLLC\n"
    "1 EXAMPLE ST\n"
    "EXAMPLETOWN XX 00000-0000\n"
    "Last statement: March 31, 2026\n"
    "This statement: April 30, 2026\n"
    "MARKETPLACE CHECKING\n"
)
SUMMARY = (
    "Account number XXXXXX0000 Beginning balance $100.00\n"
    "Low balance $60.00 Deposits/Additions $500.00\n"
    "Average balance $80.00 Withdrawals/Subtractions $450.00\n"
    "Interest earned $0.00 Ending balance $150.00\n"
)
DEPOSITS = (
    "Deposits/Additions\n"
    "Date Description Additions\n"
    "04-02 Deposit 200.00\n"
    "Total Additions $200.00\n"
)
ACH_DEBITS = (
    "ACH and Electronic Payments/Subtractions\n"
    "Date Description Subtractions\n"
    "04-03 ACH Debit Example Vendor 20260403 400.00\n"
    "Total ACH and Electronic Payments/Subtractions $400.00\n"
)
ACH_CREDITS = (
    "ACH and Electronic Deposits/Additions\n"
    "Date Description Additions\n"
    "04-05 ACH Credit Example Payer 20260405 300.00\n"
    "Total ACH and Electronic Deposits/Additions $300.00\n"
)
OTHER_DEBITS = (
    "Other Withdrawals/Subtractions\n"
    "Date Description Subtractions\n"
    "04-06 Automatic Ln Paymt Automatic Loan Pay 30.00\n"
    "Total Other Withdrawals/Subtractions $30.00\n"
)
GRID = (
    "Daily Balances\n"
    "Date Amount Date Amount Date Amount\n"
    "03-31 100.00 04-05 200.00 04-07 150.00\n"
    "04-02 300.00 04-06 170.00\n"
    "04-03 -100.00\n"
)
FEES = (
    "Overdraft Fee Summary\n"
    "Total For Total\n"
    "This Period Year-to-Date\n"
    "Total Overdraft Fees $0.00 $0.00\n"
)
CHEQUES = (
    "Checks\n"
    "Check # Amount Date\n"
    "1001 $20.00 04-07\n"
    "(* Skip in check sequence, R-Check has been returned, + Electronified check) )\n"
    "Total Checks paid: 1 for -$20.00\n"
)
#: The month that prints an `Other Deposits/Additions` section: +$50.00 of
#: credits, which the summary strip and the daily grid both carry.
OTHER_CREDITS = (
    "Other Deposits/ Additions\n"
    "Date Description Additions\n"
    "04-02 Return Item Example Payer 20260402 50.00\n"
    "Total Other Deposits/ Additions $50.00\n"
)


def document(*, masthead=MASTHEAD, summary=SUMMARY, deposits=DEPOSITS,
             other_credits="", ach_debits=ACH_DEBITS, ach_credits=ACH_CREDITS,
             other_debits=OTHER_DEBITS, grid=GRID, fees=FEES, cheques=CHEQUES):
    return "\n".join(part for part in (
        masthead, summary, deposits, other_credits, ach_debits, ach_credits,
        other_debits, grid, fees, cheques,
    ) if part)


def parse(markdown: str):
    return cb.parse_columbia_bank_statement(markdown)


def test_the_template_parses_and_publishes_what_the_bank_printed():
    statement = parse(document())
    assert statement is not None
    assert statement.bank == "Columbia Bank"
    assert statement.account_number == "XXXXXX0000"
    assert statement.account_name == "Holder Name Pllc - Marketplace Checking"
    assert (statement.period_start, statement.period_end) == ("2026-04-01", "2026-04-30")
    assert statement.days_in_period == 30
    assert (statement.beginning_balance, statement.ending_balance) == (100.00, 150.00)
    assert (statement.stated_total_credits, statement.stated_total_debits) == (500.00, 450.00)
    assert statement.bank_reported_average_balance == 80.00
    assert statement.bank_reported_average_label == "Average balance"
    assert [(t.date, t.amount) for t in statement.transactions] == [
        ("2026-04-02", 200.00),
        ("2026-04-03", -400.00),
        ("2026-04-05", 300.00),
        ("2026-04-06", -30.00),
        ("2026-04-07", -20.00),
    ]


# ---------------------------------------------------------------------------
# Detection — the issuer's NAME is not evidence on a scanned logo
# ---------------------------------------------------------------------------

def test_the_registration_claims_a_statement_that_never_prints_the_issuer_name():
    text = document()
    assert "COLUMBIA" not in text.upper()
    assert cb.detect(text).claims


def test_every_marker_is_required():
    #: dropping any one of the four declines the document, so none of them is
    #: carried by the others.
    fired = cb.detect(document())
    assert set(fired.matched) == {
        "product", "credits_section", "debits_section", "daily_balances"
    }
    for marker, gone in (
        ("product", document(masthead=MASTHEAD.replace("MARKETPLACE CHECKING", "OTHER PRODUCT"))),
        ("credits_section", document(summary=SUMMARY.replace("Deposits/Additions", "Money in"),
                                     deposits="", ach_credits="")),
        ("debits_section", document(ach_debits="")),
        ("daily_balances", document(grid="")),
    ):
        detection = cb.detect(gone)
        assert not detection.claims, marker
        assert marker not in detection.matched


def test_the_claim_score_is_unchanged_by_the_marker_swap():
    #: four required markers before the swap and four after, so a statement
    #: that claimed at 0.5 still claims at 0.5 — the pinned document's dispatch
    #: score does not move.
    assert cb.detect(document()).score == 0.5


# ---------------------------------------------------------------------------
# The scan's debris: column-header rows and section mastheads
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("printed", [
    "Date Description Additions",
    "Date —_ Description Additions",
    "Date  _  Description Additions",
    "Date | Description Additions",
])
def test_a_column_header_row_is_the_same_row_whatever_the_scan_put_between_its_cells(printed):
    assert parse(document(deposits=DEPOSITS.replace(
        "Date Description Additions", printed))) is not None


def test_debris_in_a_column_header_may_not_cross_a_line():
    #: `Date` and `Description` are one printed row. A gap that spanned lines
    #: could bind one section's `Date` to the next section's `Description` and
    #: bound the section from the wrong place.
    assert parse(document(deposits=DEPOSITS.replace(
        "Date Description Additions", "Date\nDescription Additions"))) is None


def test_a_masthead_may_be_preceded_by_debris_on_its_own_line():
    assert parse(document(other_debits="——. " + OTHER_DEBITS)) is not None


def test_a_masthead_may_not_be_preceded_by_words():
    #: the tolerance admits no letter, so no word of a longer heading can hide
    #: in it — which is what keeps `Deposits/Additions` from being bounded from
    #: `ACH and Electronic Deposits/Additions`.
    assert parse(document(deposits="Continued Deposits/Additions\n"
                                   + DEPOSITS.split("\n", 1)[1])) is None


def test_the_plain_deposit_section_is_not_bounded_from_the_ach_credit_section():
    #: April prints no plain deposit section. Without the line anchor the
    #: reader would bound `Deposits/Additions` from the tail of `ACH and
    #: Electronic Deposits/Additions` and read that section's rows under the
    #: wrong printed total.
    statement = parse(document(
        deposits="",
        summary=SUMMARY.replace("Deposits/Additions $500.00", "Deposits/Additions $300.00")
                       .replace("Ending balance $150.00", "Ending balance -$50.00"),
        grid=GRID.replace("04-02 300.00", "04-02 100.00").replace(
            "04-03 -100.00", "04-03 -300.00").replace(
            "04-05 200.00", "04-05 0.00").replace("04-06 170.00", "04-06 -30.00").replace(
            "04-07 150.00", "04-07 -50.00"),
    ))
    assert statement is not None
    assert [(t.date, t.amount) for t in statement.transactions] == [
        ("2026-04-03", -400.00),
        ("2026-04-05", 300.00),
        ("2026-04-06", -30.00),
        ("2026-04-07", -20.00),
    ]


def test_the_period_labels_may_print_without_their_colon():
    assert parse(document(masthead=MASTHEAD.replace(
        "Last statement:", "Last statement"))) is not None


# ---------------------------------------------------------------------------
# The summary strip: signed balances, unsigned flows
# ---------------------------------------------------------------------------

def test_debris_between_two_summary_cells_is_not_a_missing_summary():
    for debris in ("— ", "| ", "  "):
        text = SUMMARY.replace("XXXXXX0000 Beginning", f"XXXXXX0000 {debris}Beginning")
        assert parse(document(summary=text)) is not None, debris


def test_a_negative_low_balance_is_read_rather_than_declining_the_statement():
    #: an overdrawn month prints one, and the low balance is not a figure this
    #: reader publishes — so the whole statement used to be lost to a sign on a
    #: cell nobody reads.
    assert parse(document(summary=SUMMARY.replace(
        "Low balance $60.00", "Low balance -$60.00"))) is not None


def test_a_negative_ending_balance_is_published_with_its_sign():
    statement = parse(document(
        summary=SUMMARY.replace("Ending balance $150.00", "Ending balance -$150.00")
                       .replace("Withdrawals/Subtractions $450.00",
                                "Withdrawals/Subtractions $750.00"),
        ach_debits=ACH_DEBITS.replace("400.00", "700.00"),
        grid=GRID.replace("04-03 -100.00", "04-03 -400.00").replace(
            "04-05 200.00", "04-05 -100.00").replace(
            "04-06 170.00", "04-06 -130.00").replace("04-07 150.00", "04-07 -150.00"),
    ))
    assert statement is not None
    assert statement.ending_balance == -150.00


def test_an_em_dash_in_a_sign_position_declines_rather_than_flipping_a_figure():
    #: W3 §MGD3: the em dash is punctuation, never a sign. `parse_decimal`
    #: cannot convert it and this pattern will not match past it, so the
    #: summary is simply not read.
    assert parse(document(summary=SUMMARY.replace(
        "Beginning balance $100.00", "Beginning balance —$100.00"))) is None


def test_a_signed_flow_figure_declines_rather_than_being_read_as_a_magnitude():
    #: the template prints the two flow figures unsigned and gives their
    #: direction by the label; a signed printing is a template this reader has
    #: not been shown.
    assert parse(document(summary=SUMMARY.replace(
        "Withdrawals/Subtractions $450.00", "Withdrawals/Subtractions -$450.00"))) is None


# ---------------------------------------------------------------------------
# The sections a month may or may not print
# ---------------------------------------------------------------------------

def test_an_other_deposits_section_is_read_and_folded_into_the_printed_credits():
    statement = parse(document(
        other_credits=OTHER_CREDITS,
        summary=SUMMARY.replace("Deposits/Additions $500.00", "Deposits/Additions $550.00")
                       .replace("Ending balance $150.00", "Ending balance $200.00"),
        grid=GRID.replace("04-02 300.00", "04-02 350.00").replace(
            "04-03 -100.00", "04-03 -50.00").replace(
            "04-05 200.00", "04-05 250.00").replace(
            "04-06 170.00", "04-06 220.00").replace("04-07 150.00", "04-07 200.00"),
    ))
    assert statement is not None
    assert statement.stated_total_credits == 550.00
    assert ("2026-04-02", 50.00) in [(t.date, t.amount) for t in statement.transactions]


def test_an_other_deposits_section_without_its_printed_total_declines():
    assert parse(document(other_credits=OTHER_CREDITS.replace(
        "Total Other Deposits/ Additions $50.00", ""))) is None


def test_a_printed_other_deposits_total_with_no_section_declines():
    assert parse(document(
        other_credits="Total Other Deposits/ Additions $50.00\n")) is None


def test_a_printed_total_additions_with_no_deposit_section_declines():
    assert parse(document(deposits="Total Additions $200.00\n")) is None


def test_a_section_whose_rows_miss_its_own_printed_total_declines():
    assert parse(document(other_debits=OTHER_DEBITS.replace(
        "Automatic Loan Pay 30.00", "Automatic Loan Pay 31.00"))) is None


# ---------------------------------------------------------------------------
# The cheque grid
# ---------------------------------------------------------------------------

def test_a_clean_cheque_serial_is_published():
    statement = parse(document())
    assert statement.transactions[-1].description == "Check 1001"


def test_a_damaged_cheque_serial_publishes_no_serial_rather_than_a_wrong_one():
    #: the scan reads `1001` as `A001`. Taking any trailing digit run would
    #: publish `Check 001`, a serial the bank did not print; requiring a clean
    #: one would lose the row and with it the section's agreement with the
    #: printed debit total, so the whole statement would decline over a damaged
    #: label. The amount and the date are printed and readable, and they are
    #: what the ledger needs.
    statement = parse(document(cheques=CHEQUES.replace("1001 $20.00", "A001 $20.00")))
    assert statement is not None
    assert statement.transactions[-1].description == "Check"
    assert statement.transactions[-1].amount == -20.00


def test_a_cheque_amount_without_its_currency_symbol_loses_the_row_and_declines():
    #: the symbol is what separates a serial from an amount once the serial is
    #: optional. Losing the row fails the printed debit total, which is the
    #: fail-closed direction.
    assert parse(document(cheques=CHEQUES.replace("1001 $20.00", "1001 20.00"))) is None


# ---------------------------------------------------------------------------
# The daily grid: the placeholder refusal, and the sign it must not refuse
# ---------------------------------------------------------------------------

def test_a_grid_cell_whose_figure_the_scan_preceded_with_a_placeholder_is_refused():
    #: The attested printing, verbatim (W3 §MGD3, §COUNTSP3): `88AAC06119FC`
    #: prints `03-16 —  39,692.35` in its Daily Balances grid, where the dash
    #: is the empty-column placeholder and the figure is a POSITIVE running
    #: balance between 56,767.53 and 34,167.30.
    block = "03-04 56,767.53   03-16 —  39,692.35   03-26 34,167.30\n"
    snapshots = cb._daily_snapshots(block, year=2026)
    assert [(d.isoformat(), str(v)) for d, v in sorted(snapshots.items())] == [
        ("2026-03-04", "56767.53"),
        ("2026-03-26", "34167.30"),
    ]


def test_the_placeholder_row_never_reaches_the_ledger_or_flips_a_balance():
    #: the three ways the cell can be read wrongly, all asserted absent: as a
    #: transaction (W3 §COUNTSP3, the failure this family actually suffered),
    #: as a negative balance (the shadowed sign class's answer), and as the
    #: next column's figure bound to 03-16.
    statement = parse(document(grid=GRID.replace(
        "04-03 -100.00", "04-03 —  39,692.35")))
    assert statement is not None
    assert all(abs(t.amount) != 39692.35 for t in statement.transactions)
    assert all(b.balance != -39692.35 for b in statement.stated_daily_balances)
    assert "2026-04-03" not in [b.date for b in statement.stated_daily_balances]


def test_a_grid_cell_the_bank_printed_negative_is_read_with_its_sign():
    #: an overdrawn day is exactly the day an underwriter needs to see, and
    #: reading it unsigned would publish it three times its distance from zero.
    statement = parse(document())
    assert ("2026-04-03", -100.00) in [
        (b.date, b.balance) for b in statement.stated_daily_balances
    ]


def test_the_sign_class_in_the_grid_is_the_shared_one():
    #: derived from `money.MINUS_GLYPHS`, never re-spelled — so the em dash is
    #: out of it here for the same reason it is out of it everywhere.
    from analysis.money import MINUS_GLYPHS

    for glyph in MINUS_GLYPHS:
        cell = f"04-03 {glyph}100.00\n"
        assert cb._daily_snapshots(cell, year=2026), glyph
    assert not cb._daily_snapshots("04-03 —100.00\n", year=2026)


def test_an_out_of_period_grid_cell_is_evidence_but_not_published():
    #: the grid opens on the prior period's closing day. It is used as a gate
    #: and it is not an in-period snapshot.
    statement = parse(document())
    assert "2026-03-31" not in [b.date for b in statement.stated_daily_balances]


# ---------------------------------------------------------------------------
# The oracles hold the whole read together
# ---------------------------------------------------------------------------

def test_the_section_totals_must_add_up_to_the_printed_summary_figures():
    assert parse(document(summary=SUMMARY.replace(
        "Deposits/Additions $500.00", "Deposits/Additions $501.00"))) is None


def test_a_ledger_that_does_not_reach_the_printed_ending_balance_declines():
    assert parse(document(
        summary=SUMMARY.replace("Ending balance $150.00", "Ending balance $151.00"))) is None


def test_the_reader_refuses_a_document_it_did_not_claim():
    assert parse(document(grid="")) is None


def test_the_module_declares_no_second_sign_class():
    #: `_SIGN` and `_BALANCE` are DERIVED from `money.MINUS_GLYPHS` rather than
    #: re-spelled; a private copy is the fifth definition W3 §MGD6 went to the
    #: trouble of deleting. Proven by membership over the class rather than by
    #: string equality, so a reordering of the shared class still passes and a
    #: widening of it still fails.
    from analysis.money import MINUS_GLYPHS

    assert set(re.findall(r"\[(.*)\]", cb._SIGN)[0].replace("\\", "")) == set(MINUS_GLYPHS)
    for glyph in MINUS_GLYPHS:
        assert re.fullmatch(cb._BALANCE, f"{glyph}$1.00"), glyph
    assert not re.fullmatch(cb._BALANCE, "—$1.00")
    #: and the debris class excludes every one of them, so debris can never
    #: absorb a sign.
    for glyph in MINUS_GLYPHS:
        assert not re.fullmatch(cb._DEBRIS, glyph), glyph
