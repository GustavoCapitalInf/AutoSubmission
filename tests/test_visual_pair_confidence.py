"""Fabricated rows only. The statement confidence score (evidence_v2): how much of a reading was independently
verified. An admitted statement passed every arithmetic check (0.5); the other half is the mean of the
independent evidence that applies to it. A held statement is capped below 0.5. It is verification coverage,
not a calibrated probability."""
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.confidence import CONFIDENCE_METHOD, statement_confidence
from vlm.native_text import PrintedEvidence

TEXT = """01/02 FABRICATED PAYROLL 2,500.00 3,500.00
01/05 FABRICATED HARDWARE STORE 224.50 3,275.50
"""


def _row(description, amount, *, locator, balance=None, date="2031-01-02", label=None):
    return CandidateRow(date, date[5:], description, Decimal(amount), "credit", None if balance is None else Decimal(balance),
                        1, "stage_a+stage_b", locator, description_label=label)


def _score(rows, states, *, admitted=True, checks=None, account=None, printed=(PrintedEvidence(native=TEXT),),
           reasons=()):
    checks = {"summary_ok": True, "credit_count_matches": True, "debit_count_matches": True,
              "balance_chained": False, **(checks or {})}
    account = {"stated_total_credits": 2500.0, "stated_total_debits": 224.5, **(account or {})}
    return statement_confidence(admitted=admitted, checks=checks, account=account, rows=rows,
                                row_states=states, printed_pages=list(printed), reasons=list(reasons))


def test_a_fully_corroborated_statement_scores_one():
    rows = [_row("FABRICATED PAYROLL", "2500.00", locator="t0r1"), _row("FABRICATED HARDWARE STORE", "224.50", locator="t0r2")]
    result = _score(rows, {(1, "t0r1"): ("agreed", None), (1, "t0r2"): ("agreed", None)})
    assert result["methodology"] == CONFIDENCE_METHOD and result["provisional"] is False
    assert result["score"] == 1.0 and result["band"] == "very_high"
    assert result["components"] == {"stated_totals": 1.0, "stated_counts": 1.0, "amounts_printed": 1.0,
                                    "two_readers": 1.0, "descriptions_in_text_layer": 1.0, "running_balances": None}


def test_missing_checks_and_single_reader_rows_lower_the_score():
    rows = [_row("FABRICATED PAYROLL", "2500.00", locator="t0r1"), _row("NOT PRINTED ANYWHERE", "9.99", locator="added0")]
    result = _score(rows, {(1, "t0r1"): ("agreed", None), (1, "added0"): ("added", None)},
                    checks={"summary_ok": None, "credit_count_matches": None, "debit_count_matches": None},
                    account={"stated_total_credits": None, "stated_total_debits": None})
    components = result["components"]
    assert components["stated_totals"] == 0.0 and components["stated_counts"] == 0.0
    assert components["amounts_printed"] == 0.5 and components["two_readers"] == 0.5
    assert components["descriptions_in_text_layer"] == 0.5
    assert result["score"] == pytest.approx(0.5 + 0.5 * (0 + 0 + 0.5 + 0.5 + 0.5) / 5)
    assert result["band"] == "low"
    assert result["evidence"]["reviewer_only_rows"] == 1


def test_a_correction_counts_as_both_readers_only_when_the_page_prints_it():
    rows = [_row("FABRICATED PAYROLL", "2500.00", locator="t0r1"), _row("FABRICATED HARDWAR STORE", "224.50", locator="t0r2")]
    result = _score(rows, {(1, "t0r1"): ("agreed", None), (1, "t0r2"): ("corrected", None)})
    assert result["components"]["two_readers"] == 0.75           # the corrected description is not printed
    settled = _score(rows[:1], {(1, "t0r1"): ("agreed", "text_layer")})
    assert settled["components"]["two_readers"] == 1.0 and settled["evidence"]["settled_by_text_layer"] == 1


def test_running_balances_apply_only_when_printed_and_count_when_they_continue_unbroken():
    # End-of-day balances (printed on some rows only) are verified by the continuity check as much as a
    # balance on every row; a continuity break means they were not.
    rows = [_row("FABRICATED PAYROLL", "2500.00", locator="t0r1", balance="3500.00"),
            _row("FABRICATED HARDWARE STORE", "224.50", locator="t0r2")]
    states = {(1, "t0r1"): ("agreed", None), (1, "t0r2"): ("agreed", None)}
    assert _score(rows, states)["components"]["running_balances"] == 1.0
    broken = _score(rows, states, admitted=False, reasons=["continuity_break"])
    assert broken["components"]["running_balances"] == 0.0
    assert _score(rows[1:], states)["components"]["running_balances"] is None


def test_a_description_printed_over_two_lines_or_in_another_order_counts_as_printed():
    # A second printed line (a reference) sits after the amount column, or before the first, in the text layer.
    printed = (PrintedEvidence(native="REF=FAB123 PAYMENT\n01/02 FABRICATED TRANSFER 2,500.00\n"),)
    rows = [_row("FABRICATED TRANSFER REF=FAB123 PAYMENT", "2500.00", locator="t0r1")]
    result = _score(rows, {(1, "t0r1"): ("corrected", None)}, printed=printed,
                    account={"stated_total_credits": 2500.0, "stated_total_debits": 0.0})
    assert result["components"]["descriptions_in_text_layer"] == 1.0 and result["components"]["two_readers"] == 1.0


def test_a_scanned_page_has_no_description_evidence_and_is_not_penalised_for_it():
    rows = [_row("FABRICATED PAYROLL", "2500.00", locator="t0r1")]
    result = _score(rows, {(1, "t0r1"): ("agreed", None)}, printed=(PrintedEvidence(native=None, proposer=TEXT),))
    assert result["components"]["descriptions_in_text_layer"] is None and result["score"] == 1.0


def test_a_cheque_label_is_not_held_against_its_description():
    rows = [_row("Check 1234", "45.10", locator="t0r1", label="Check")]
    printed = (PrintedEvidence(native="Check Nbr Date Amount\n1234 01/05 45.10\n"),)
    result = _score(rows, {(1, "t0r1"): ("agreed", None)}, printed=printed,
                    account={"stated_total_credits": 45.1, "stated_total_debits": 0.0})
    assert result["components"]["descriptions_in_text_layer"] == 1.0


def test_a_held_statement_stays_below_half():
    rows = [_row("FABRICATED PAYROLL", "2500.00", locator="t0r1")]
    result = _score(rows, {(1, "t0r1"): ("agreed", None)}, admitted=False)
    assert result["score"] == pytest.approx(0.49) and result["band"] == "held"
    assert _score([], {}, admitted=False)["score"] == 0.0
