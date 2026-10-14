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
from datetime import date

import pytest

from analysis import columbia_bank as cb, parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401 — populates the registry

#: Printed periods for the tests that call the grid reader directly.
MARCH_2054 = (date(2054, 3, 1), date(2054, 3, 31))
APRIL_2054 = (date(2054, 4, 1), date(2054, 4, 30))


# ---------------------------------------------------------------------------
# One statement of the template, in the pieces a test can vary
# ---------------------------------------------------------------------------

MASTHEAD = (
    "April 30, 2054 Page: 1 of 4\n"
    "Customer Service:\n"
    "HOLDER NAME PLLC\n"
    "1 EXAMPLE ST\n"
    "EXAMPLETOWN XX 00000-0000\n"
    "Last statement: March 31, 2054\n"
    "This statement: April 30, 2054\n"
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
    assert (statement.period_start, statement.period_end) == ("2054-04-01", "2054-04-30")
    assert statement.days_in_period == 30
    assert (statement.beginning_balance, statement.ending_balance) == (100.00, 150.00)
    assert (statement.stated_total_credits, statement.stated_total_debits) == (500.00, 450.00)
    assert statement.bank_reported_average_balance == 80.00
    assert statement.bank_reported_average_label == "Average balance"
    assert [(t.date, t.amount) for t in statement.transactions] == [
        ("2054-04-02", 200.00),
        ("2054-04-03", -400.00),
        ("2054-04-05", 300.00),
        ("2054-04-06", -30.00),
        ("2054-04-07", -20.00),
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
        ("2054-04-03", -400.00),
        ("2054-04-05", 300.00),
        ("2054-04-06", -30.00),
        ("2054-04-07", -20.00),
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


@pytest.mark.parametrize("printed", [
    "Beginning balance $100.00", "Low balance $60.00",
    "Average balance $80.00", "Ending balance $150.00",
])
def test_an_em_dash_in_a_sign_position_declines_rather_than_flipping_a_figure(printed):
    #: W3 §MGD3: the em dash is punctuation, never a sign. `parse_decimal`
    #: cannot convert it and this pattern will not match past it, so the
    #: summary is simply not read. Asserted on EVERY balance slot: the debris
    #: tolerance runs between the cells of this strip, and a tolerance that
    #: crept in front of any one figure would absorb the dash there and publish
    #: the magnitude.
    label, figure = printed.rsplit(" ", 1)
    assert parse(document(summary=SUMMARY.replace(
        printed, f"{label} —{figure}"))) is None


def test_the_balance_pattern_and_the_balance_reader_admit_the_same_tokens():
    #: A finder that admits a token its parser refuses hands the parser
    #: something it can only decline by RAISING, which surfaces as
    #: `parser_exception` ("our code broke") rather than as a refusal ("we
    #: could not read this"). `money.SIGNED_MONEY_TOKEN`'s docstring names that
    #: hazard; this is the same pairing for this module's own slot pattern.
    #: `_BALANCE` admits one space between the sign and the figure, which is
    #: the whole of what `_signed` adds over `_money` — `_money` raises on it.
    from analysis.money import MINUS_GLYPHS

    for token in [f"{g}{s}$150.00" for g in MINUS_GLYPHS for s in ("", " ")]:
        assert re.fullmatch(cb._BALANCE, token), token
        assert cb._signed(token) == -150, token
    statement = parse(document(
        summary=SUMMARY.replace("Ending balance $150.00", "Ending balance - $150.00")
                       .replace("Average balance $80.00", "Average balance - $80.00")
                       .replace("Withdrawals/Subtractions $450.00",
                                "Withdrawals/Subtractions $750.00"),
        ach_debits=ACH_DEBITS.replace("400.00", "700.00"),
        grid=GRID.replace("04-03 -100.00", "04-03 -400.00").replace(
            "04-05 200.00", "04-05 -100.00").replace(
            "04-06 170.00", "04-06 -130.00").replace("04-07 150.00", "04-07 -150.00"),
    ))
    assert statement is not None and statement.ending_balance == -150.00
    #: and the evidence lane carries the sign too — a bank-reported average
    #: published as +80.00 on an overdrawn account is the wrong number in the
    #: one field an underwriter reads first.
    assert statement.bank_reported_average_balance == -80.00


def test_a_balance_slot_without_the_sign_class_would_lose_the_whole_summary():
    #: the shape of the loss, so the tolerance cannot be quietly narrowed:
    #: June's statement would be declined by a sign on `Low balance`, a figure
    #: this reader does not even publish.
    assert re.fullmatch(cb._BALANCE, "-$60.00")
    assert not re.fullmatch(cb._BALANCE.replace(f"{cb._SIGN}?", "", 1), "-$60.00")


@pytest.mark.parametrize("printed", [
    "Deposits/Additions $500.00", "Withdrawals/Subtractions $450.00",
    "Interest earned $0.00",
])
def test_a_signed_flow_figure_declines_rather_than_being_read_as_a_magnitude(printed):
    #: The template prints the two flow figures and the interest unsigned and
    #: gives their direction by the label; a signed printing is a template this
    #: reader has not been shown.
    #:
    #: Be exact about WHICH refusal this pins, because it is not the one the
    #: name suggests. In shipped code the unsigned slot cannot match a signed
    #: figure, so the summary regex as a WHOLE becomes unmatchable and the
    #: document is refused for having no readable summary at all — the account
    #: number and every balance are lost with it, not just the flow figure.
    #: Under the mutant that widens the slot to `_BALANCE` the summary reads,
    #: the flow figure comes out negative, and the document is then refused by
    #: the credit identity instead. Two different gates, same verdict: which is
    #: why that mutant survives by design (C8.1). What this test therefore
    #: guarantees is the VERDICT on every flow slot, and the widening it would
    #: take to lose it is pinned separately by
    #: `test_the_balance_pattern_and_the_balance_reader_admit_the_same_tokens`.
    label, figure = printed.rsplit(" ", 1)
    assert parse(document(summary=SUMMARY.replace(
        printed, f"{label} -{figure}"))) is None


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
    assert ("2054-04-02", 50.00) in [(t.date, t.amount) for t in statement.transactions]


def test_an_other_deposits_section_without_its_printed_total_declines():
    assert parse(document(other_credits=OTHER_CREDITS.replace(
        "Total Other Deposits/ Additions $50.00", ""))) is None


def test_a_deposit_section_without_its_printed_total_declines():
    #: The same pairing for the other optional section. It is NOT the dangerous
    #: direction, and saying so is the point: this section's rows are always
    #: inside the summary's `Deposits/Additions` figure, so a reader that
    #: treated the unclosed section as an absent one drops 200.00 of credits
    #: and then FAILS the credit identity — it refuses too, for a different
    #: reason. (The mutation harness confirms it: reverting this check to the
    #: empty-block test survives, and C8.1 names it as surviving by design.)
    #: The check is kept and pinned for symmetry with `Other Deposits/
    #: Additions`, where the same revert does NOT refuse — see the test above,
    #: which is the dangerous direction.
    assert parse(document(deposits=DEPOSITS.replace(
        "Total Additions $200.00", ""))) is None


def test_a_printed_other_deposits_total_with_no_section_declines():
    assert parse(document(
        other_credits="Total Other Deposits/ Additions $50.00\n")) is None


def test_a_printed_total_additions_with_no_deposit_section_declines():
    assert parse(document(deposits="Total Additions $200.00\n")) is None


@pytest.mark.parametrize("section,printed,damaged", [
    ("other_debits", "Automatic Loan Pay 30.00", "Automatic Loan Pay 31.00"),
    ("deposits", "04-02 Deposit 200.00", "04-02 Deposit 201.00"),
    ("ach_credits", "20260405 300.00", "20260405 301.00"),
    ("ach_debits", "20260403 400.00", "20260403 401.00"),
])
def test_a_section_whose_rows_miss_its_own_printed_total_declines(section, printed, damaged):
    #: EVERY section against its own printed total, not just the ones a
    #: fixture happens to exercise. This is the oracle the whole read rests on:
    #: a section that quietly published rows disagreeing with the figure
    #: beneath them would put the disagreement into the transaction list and
    #: leave the summary looking right.
    #:
    #: The ACH DEBIT section is in this list since W3 §REPAIRDOC. It used to be
    #: the one section with a repair path, and the repair is what kept it out.
    base = {"other_debits": OTHER_DEBITS, "deposits": DEPOSITS,
            "ach_credits": ACH_CREDITS, "ach_debits": ACH_DEBITS}[section]
    assert parse(document(**{section: base.replace(printed, damaged)})) is None


# ---------------------------------------------------------------------------
# W3 §REPAIRDOC — a row is published at the figure the text prints, or it is
# not published
# ---------------------------------------------------------------------------
#
# Two repairs used to sit between the row reader and the section gates. One
# snapped a row to its counterparty group's modal amount whenever that moved
# the section nearer its printed total; the other rewrote ONE row BY the
# section's whole residual and kept the candidate whose reconstruction best
# matched the daily grid. Both ran BEFORE the gates, so each gate tested its
# own repair's objective function rather than the document. Gustavo's ruling of
# 2054-08-21 removed them: "Parsers must never rewrite transaction amounts just
# to force reconciliation."
#
# Each shape below is pinned TWICE: the damaged document refuses, and the same
# rows publish at the figures they print once the printed total agrees with
# them. The second half is what says the reader is fail-closed rather than
# merely broken — a reader that had lost the ability to publish these rows at
# all would pass the refusal half and fail this one.

#: Three rows of one counterparty at one amount and a fourth a dollar off it.
#: The removed `_counterparty_key` grouped on the leading non-numeric
#: description tokens, so all four were one group with a mode of 100.00.
_REPEATED_ROWS = (
    "04-03 ACH Debit Example Vendor 20260403 100.00\n"
    "04-03 ACH Debit Example Vendor 20260403 100.00\n"
    "04-03 ACH Debit Example Vendor 20260403 100.00\n"
    "04-03 ACH Debit Example Vendor 20260403 101.00\n"
)


def _repeated_debits(total: str) -> str:
    return (
        "ACH and Electronic Payments/Subtractions\n"
        "Date Description Subtractions\n"
        + _REPEATED_ROWS
        + f"Total ACH and Electronic Payments/Subtractions ${total}\n"
    )


def _summary_and_grid_for_401_of_debits(**parts):
    """`document(...)` with the summary and the grid moved to 401.00 of ACH
    debits, so a section total of 401.00 is the CONSISTENT printing."""
    return document(
        summary=SUMMARY.replace("Withdrawals/Subtractions $450.00",
                                "Withdrawals/Subtractions $451.00")
                       .replace("Ending balance $150.00", "Ending balance $149.00"),
        grid=GRID.replace("04-03 -100.00", "04-03 -101.00")
                 .replace("04-05 200.00", "04-05 199.00")
                 .replace("04-06 170.00", "04-06 169.00")
                 .replace("04-07 150.00", "04-07 149.00"),
        **parts,
    )


def test_a_row_a_dollar_off_its_counterparty_mode_is_not_snapped_to_it():
    #: MUTATION: restore `_repair_repeated_amounts` and its call site and this
    #: document publishes four rows of 100.00 — three read and one WRITTEN,
    #: against a named counterparty, with every printed total agreeing.
    assert parse(document(ach_debits=_repeated_debits("400.00"))) is None


def test_the_same_four_rows_publish_as_printed_when_the_total_agrees():
    statement = _summary_and_grid_for_401_of_debits(
        ach_debits=_repeated_debits("401.00"))
    statement = parse(statement)
    assert statement is not None
    assert sorted(
        t.amount for t in statement.transactions if t.date == "2054-04-03"
    ) == [-101.00, -100.00, -100.00, -100.00]


def test_a_single_row_carrying_the_sections_whole_residual_is_not_rewritten():
    #: MUTATION: restore `_repair_single_section_delta` and its call site and
    #: this document publishes 400.00 for a row the bank printed at 401.00 —
    #: the daily grid confirms the candidate, which is exactly the confirmation
    #: the ruling refuses to accept as a licence to write an amount.
    assert parse(document(ach_debits=ACH_DEBITS.replace(
        "20260403 400.00", "20260403 401.00"))) is None


def test_the_same_row_publishes_as_printed_when_the_total_agrees():
    statement = parse(_summary_and_grid_for_401_of_debits(
        ach_debits=ACH_DEBITS.replace("20260403 400.00", "20260403 401.00")
                             .replace("Subtractions $400.00", "Subtractions $401.00"),
    ))
    assert statement is not None
    assert [t.amount for t in statement.transactions if t.date == "2054-04-03"] == [-401.00]


def test_two_candidate_rows_refuse_rather_than_one_being_chosen():
    #: `88AAC06119FC`'s shape: the section misses its printed total and the
    #: grid puts the whole difference on a day that prints more than one row,
    #: so no candidate is distinguishable. The repair refused here by scoring;
    #: the reader now refuses because the section does not add up, which is the
    #: same answer reached without an objective function.
    two_rows = (
        "ACH and Electronic Payments/Subtractions\n"
        "Date Description Subtractions\n"
        "04-03 ACH Debit Example Vendor 20260403 251.00\n"
        "04-03 ACH Debit Other Vendor 20260403 150.00\n"
        "Total ACH and Electronic Payments/Subtractions $400.00\n"
    )
    assert parse(document(ach_debits=two_rows)) is None


def test_every_published_amount_is_a_figure_the_document_prints():
    #: The doctrine as a property rather than as a list of shapes: whatever the
    #: reader publishes, each magnitude is a token the text carries. Holds over
    #: the template and over both consistent variants above.
    for markdown in (
        document(),
        document(other_credits=OTHER_CREDITS,
                 summary=SUMMARY.replace("Deposits/Additions $500.00",
                                         "Deposits/Additions $550.00")
                                .replace("Ending balance $150.00", "Ending balance $200.00"),
                 grid=GRID.replace("04-02 300.00", "04-02 350.00").replace(
                     "04-03 -100.00", "04-03 -50.00").replace(
                     "04-05 200.00", "04-05 250.00").replace(
                     "04-06 170.00", "04-06 220.00").replace(
                     "04-07 150.00", "04-07 200.00")),
        _summary_and_grid_for_401_of_debits(ach_debits=_repeated_debits("401.00")),
    ):
        statement = parse(markdown)
        assert statement is not None
        for txn in statement.transactions:
            assert f"{abs(txn.amount):,.2f}" in markdown, txn


#: The dangerous shape for a per-section gate: a document whose SUMMARY
#: identity and whose balance CHAIN both hold, and whose only contradiction is
#: one section against its own printed total. Every other oracle is satisfied,
#: so the section gate is the only thing standing between the reader and a
#: published amount the bank did not print. Both optional sections are pinned
#: in it, because both were introduced by this cell.

def test_a_deposit_section_that_contradicts_only_its_own_total_still_declines():
    #: rows 201.00, printed total 200.00, summary and ending both consistent
    #: with the 201.00 the rows add to.
    assert parse(document(
        deposits=DEPOSITS.replace("04-02 Deposit 200.00", "04-02 Deposit 201.00"),
        summary=SUMMARY.replace("Ending balance $150.00", "Ending balance $151.00"),
    )) is None


def test_an_other_deposits_section_that_contradicts_only_its_own_total_declines():
    #: rows 51.00, printed total 50.00, summary and ending both consistent with
    #: the 51.00.
    assert parse(document(
        other_credits=OTHER_CREDITS.replace("20260402 50.00", "20260402 51.00"),
        summary=SUMMARY.replace("Deposits/Additions $500.00", "Deposits/Additions $550.00")
                       .replace("Ending balance $150.00", "Ending balance $201.00"),
    )) is None


def test_an_ach_debit_section_that_contradicts_only_its_own_total_declines():
    #: W3 §REPAIRDOC. The same dangerous shape for the section that used to
    #: have a repair path, and the mutation proof for its gate: rows 401.00 and
    #: a printed section total of 400.00, with BOTH remaining oracles satisfied
    #: — the summary's `Withdrawals/Subtractions` is the sum of the printed
    #: SECTION totals (400 + 30 + 20), and the ledger the ROWS reconstruct
    #: reaches the printed ending balance of 149.00.
    #:
    #: The parametrized decline above does not prove this gate: on its fixture
    #: the ledger chain refuses first, so deleting the section gate leaves it
    #: green. Here the section gate is the only thing standing between the
    #: reader and a transaction list that disagrees with the figure printed
    #: under it.
    #:
    #: MUTATION: delete the `ach_debits` section gate and this document
    #: publishes.
    assert parse(document(
        ach_debits=ACH_DEBITS.replace("20260403 400.00", "20260403 401.00"),
        summary=SUMMARY.replace("Ending balance $150.00", "Ending balance $149.00"),
        grid=GRID.replace("04-03 -100.00", "04-03 -101.00")
                 .replace("04-05 200.00", "04-05 199.00")
                 .replace("04-06 170.00", "04-06 169.00")
                 .replace("04-07 150.00", "04-07 149.00"),
    )) is None


def test_an_ach_credit_section_that_contradicts_only_its_own_total_declines():
    #: The other half of the pair. Rows 301.00 against a printed section total
    #: of 300.00; the printed `Deposits/Additions` still equals 200 + 300 and
    #: the ledger the rows reconstruct still reaches the printed 151.00.
    #:
    #: MUTATION: delete the `ach_credits` section gate and this document
    #: publishes.
    assert parse(document(
        ach_credits=ACH_CREDITS.replace("20260405 300.00", "20260405 301.00"),
        summary=SUMMARY.replace("Ending balance $150.00", "Ending balance $151.00"),
        grid=GRID.replace("04-05 200.00", "04-05 201.00")
                 .replace("04-06 170.00", "04-06 171.00")
                 .replace("04-07 150.00", "04-07 151.00"),
    )) is None


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
    # the grid reader dates its cells by the printed period (audit 2026-10-13
    # PARSERS-2) and also reports a cell from outside it
    snapshots, foreign = cb._daily_snapshots(block, start=MARCH_2054[0], end=MARCH_2054[1])
    assert not foreign
    assert [(d.isoformat(), str(v)) for d, v in sorted(snapshots.items())] == [
        ("2054-03-04", "56767.53"),
        ("2054-03-26", "34167.30"),
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
    assert "2054-04-03" not in [b.date for b in statement.stated_daily_balances]


def test_a_grid_cell_the_bank_printed_negative_is_read_with_its_sign():
    #: an overdrawn day is exactly the day an underwriter needs to see, and
    #: reading it unsigned would publish it three times its distance from zero.
    statement = parse(document())
    assert ("2054-04-03", -100.00) in [
        (b.date, b.balance) for b in statement.stated_daily_balances
    ]


def test_the_sign_class_in_the_grid_is_the_shared_one():
    #: derived from `money.MINUS_GLYPHS`, never re-spelled — so the em dash is
    #: out of it here for the same reason it is out of it everywhere.
    from analysis.money import MINUS_GLYPHS

    for glyph in MINUS_GLYPHS:
        cell = f"04-03 {glyph}100.00\n"
        assert cb._daily_snapshots(cell, start=APRIL_2054[0], end=APRIL_2054[1])[0], glyph
    assert not cb._daily_snapshots("04-03 —100.00\n", start=APRIL_2054[0], end=APRIL_2054[1])[0]


def test_an_out_of_period_grid_cell_is_evidence_but_not_published():
    #: the grid opens on the prior period's closing day. It is used as a gate
    #: and it is not an in-period snapshot.
    statement = parse(document())
    assert "2054-03-31" not in [b.date for b in statement.stated_daily_balances]


# ---------------------------------------------------------------------------
# W3 §REPAIRDOC — the printed cell is published, and a disagreement with the
# ledger under it is a finding rather than something to resolve
# ---------------------------------------------------------------------------
#
# `stated_daily_balances` is BANK evidence: `analysis/adb.py` lets a snapshot
# OVERRIDE the reconstructed carry for its day. This reader used to publish
# `reconstructed.get(day, snapshots[day])` — its own arithmetic wherever it had
# any — so the ADB was computed over a series that was part parser and part
# bank, with nothing saying which day was which.

#: One printed cell the ledger under it does not reconstruct, and everything
#: else about the document consistent: every section adds to its own printed
#: total, the section totals add to the summary, and the ledger reaches the
#: printed ending balance. The disagreement is the ONLY finding, which is what
#: makes it the shape a substitution could hide.
CONTRADICTED_GRID = GRID.replace("04-05 200.00", "04-05 210.00")


def test_the_daily_grid_publishes_the_printed_cell_not_the_reconstruction():
    #: MUTATION: restore `reconstructed.get(snapshot_date, snapshots[...])` and
    #: 200.00 is published for 04-05 — the parser's own arithmetic handed to
    #: `analysis/adb.py` under the name of a bank-printed balance.
    statement = parse(document(grid=CONTRADICTED_GRID))
    assert statement is not None
    assert ("2054-04-05", 210.00) in [
        (b.date, b.balance) for b in statement.stated_daily_balances
    ]


def test_a_grid_cell_the_ledger_does_not_reconstruct_is_published_as_a_contradiction():
    #: MUTATION: drop the reconstruction half of `daily_grid_contradictions`
    #: and the disagreement is published as evidence with nothing naming it.
    markdown = document(grid=CONTRADICTED_GRID)
    notes = cb.daily_grid_contradictions(markdown, parse(markdown))
    assert len(notes) == 1
    assert "2054-04-05" in notes[0]


def test_a_published_snapshot_that_is_not_the_printed_cell_is_a_contradiction():
    #: The never-substitute rule made a measured fact rather than a property of
    #: the code as it stands. The check re-reads the grid from the DOCUMENT, so
    #: a reader that resumed substituting is caught by it.
    #:
    #: MUTATION: drop the published-snapshot half of the check and this
    #: statement — carrying the reconstruction where the grid prints something
    #: else — reports only the ledger disagreement.
    markdown = document(grid=CONTRADICTED_GRID)
    statement = parse(markdown)
    substituted = statement.model_copy(update={"stated_daily_balances": [
        snapshot.model_copy(update={"balance": 200.00})
        if snapshot.date == "2054-04-05" else snapshot
        for snapshot in statement.stated_daily_balances
    ]})
    notes = cb.daily_grid_contradictions(markdown, substituted)
    assert any("is not the figure the Daily Balances grid prints" in note for note in notes)


def test_a_grid_the_ledger_reconstructs_exactly_reports_nothing():
    #: The check is not a standing accusation: the template agrees with itself
    #: on every printed cell and reports nothing.
    markdown = document()
    assert cb.daily_grid_contradictions(markdown, parse(markdown)) == []


def test_the_registration_declares_the_daily_grid_check():
    #: MUTATION: drop `integrity_checks` from the columbia_bank override and
    #: the check never runs, so no disagreement reaches a published flag.
    registration = next(r for r in pr.registrations() if r.id == "columbia_bank")
    assert cb.daily_grid_contradictions in registration.integrity_checks


def test_the_disagreement_reaches_the_published_integrity_block():
    #: End to end: the note the parser's check writes becomes a published flag
    #: on the document, which is what "flag the disagreement" has to mean.
    from analysis.pipeline import analyze_markdown

    report = analyze_markdown(document(grid=CONTRADICTED_GRID), parse_mode="deterministic")
    assert "conflicting_statement_summaries" in report.integrity.flags
    assert any("2054-04-05" in note for note in report.integrity.notes)


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
