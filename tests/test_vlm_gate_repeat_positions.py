"""Fabricated rows only. A repeated (date, description, amount, direction) with no printed balance used to be
refused outright. Genuine repeats are common on statements that print balances sparsely (several identical
fees on one day), and the layout model reads each printed line at its own grid position. Two rows read by
ONE layout pass at DIFFERENT grid positions, or on different pages, are two printed lines. Everything that
could be one line read twice stays refused exactly as before.
"""
from dataclasses import replace
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.gate import GATE_VERSION, gate
from vlm.metadata import AccountMeta


def _fee(locator, *, page=1, balance=None, source="stage_a+stage_b"):
    return CandidateRow("2031-01-05", "01/05", "FABRICATED SERVICE FEE", Decimal("1.50"), "debit", balance,
                        page, source, locator)


def _meta(count, begin="100.00"):
    end = Decimal(begin) - Decimal("1.50") * count
    return AccountMeta(Decimal(begin), end, "2031-01-01", "2031-01-31", "USD", "0001", "SYNTHETIC BANK",
                       ("test",))


def _verdict(rows):
    return gate(rows, _meta(len(rows)))


def test_same_read_different_grid_positions_are_separate_printed_lines():
    verdict = _verdict([_fee("b7t0r14"), _fee("b7t0r15"), _fee("b7t0r16")])
    assert verdict.admitted, verdict.reasons
    assert verdict.checks["repeats"] == {"distinguished": 3, "unverifiable": 0}
    assert verdict.checks["repeats_by_position"] == 3


def test_two_lines_of_one_text_block_are_separate_printed_lines():
    # The proposer read the table as a text block, one printed line per transaction (Regions): two identical
    # $1.50 fees on lines 43 and 44 of block 6 are two printed lines (gate v12).
    verdict = _verdict([_fee("b6l43"), _fee("b6l44")])
    assert verdict.admitted, verdict.reasons
    assert GATE_VERSION >= 12
    # A text line and a table row of another read on the same page may be one line read twice.
    assert "duplicate_row" in _verdict([_fee("b6l43"), _fee("g1c0/b3t0r2")]).reasons


def test_same_crop_different_positions_are_separate_printed_lines():
    verdict = _verdict([_fee("g1c0/b3t0r2"), _fee("g1c0/b3t0r3")])
    assert verdict.admitted, verdict.reasons


def test_repeats_on_different_pages_are_separate_printed_lines():
    verdict = _verdict([_fee("b6t0r30", page=2), _fee("b6t0r1", page=3)])
    assert verdict.admitted, verdict.reasons


def test_corrected_rows_keep_their_layout_position():
    # A corrected row is relabelled stage_b but keeps the candidate's layout locator.
    verdict = _verdict([_fee("b7t0r14", source="stage_b"), _fee("b7t0r15", source="stage_b")])
    assert verdict.admitted, verdict.reasons


def test_full_page_read_and_crop_on_the_same_page_may_overlap_and_stay_refused():
    verdict = _verdict([_fee("b7t0r14"), _fee("g1c0/b3t0r2")])
    assert "duplicate_row" in verdict.reasons


def test_recovery_original_and_crop_may_overlap_and_stay_refused():
    verdict = _verdict([_fee("g0/b7t0r14"), _fee("g1c0/b3t0r2")])
    assert "duplicate_row" in verdict.reasons


def test_two_different_crops_may_overlap_and_stay_refused():
    verdict = _verdict([_fee("g1c0/b3t0r2"), _fee("g1c1/b1t0r0")])
    assert "duplicate_row" in verdict.reasons


def test_reviewer_additions_carry_no_position_and_stay_refused():
    verdict = _verdict([_fee("added0", source="stage_b"), _fee("added1", source="stage_b")])
    assert "duplicate_row" in verdict.reasons


def test_an_addition_repeating_a_layout_row_stays_refused():
    verdict = _verdict([_fee("b7t0r14"), _fee("added0", source="stage_b")])
    assert "duplicate_row" in verdict.reasons


def test_identical_locator_is_one_line_proposed_twice():
    verdict = _verdict([_fee("b7t0r14"), _fee("b7t0r14")])
    assert "duplicate_row" in verdict.reasons


def test_a_same_day_closing_balance_printed_on_every_row_is_not_a_duplicate():
    # Some banks print the day's closing balance on every row of that day; the gate collapses the run
    # before comparing. Two genuine fees under such a balance reconcile and are admitted.
    closing = Decimal("97.00")
    verdict = _verdict([_fee("b7t0r14", balance=closing), _fee("b7t0r15", balance=closing)])
    assert verdict.admitted, verdict.reasons


def test_one_line_read_twice_with_its_running_balance_is_refused_by_the_arithmetic():
    # A running-balance bank printed ONE fee leaving 98.50; reading that line twice cannot reconcile.
    verdict = _verdict([_fee("b7t0r14", balance=Decimal("98.50")), _fee("b7t0r15", balance=Decimal("98.50"))])
    assert not verdict.admitted


def test_unlabelled_locators_keep_the_strict_rule():
    verdict = _verdict([_fee("synthetic-1"), _fee("synthetic-2")])
    assert "duplicate_row" in verdict.reasons


def test_a_positional_repeat_is_still_refused_when_the_arithmetic_fails():
    # Positions only lift the duplicate reason. A row read that is not on the page still breaks the sum.
    rows = [_fee("b7t0r14"), _fee("b7t0r15")]
    verdict = gate(rows, _meta(1))
    assert not verdict.admitted and "duplicate_row" not in verdict.reasons


def test_gate_version_moved_for_the_new_evidence():
    assert GATE_VERSION >= 10


def test_additions_are_separate_when_their_page_prints_the_line_as_often_as_rows_claim_it():
    # Gate v15: two reviewer additions repeating one fee (the proposer read that table as a text block it could not
    # split, "description date amount") are two printed lines when the page prints the date and the amount on two
    # lines: its text layer, else the proposer's reading, one line per table row or text line.
    from vlm.pair import printed_repeat_groups

    rows = [_fee("added0", source="stage_b"), _fee("added1", source="stage_b")]
    twice = [["FABRICATED SERVICE FEE 01/05 1.50", "FABRICATED SERVICE FEE 01/05 1.50", "01/05 98.50"]]
    groups = printed_repeat_groups(rows, twice)
    assert groups == {(1, "2031-01-05", Decimal("1.50"))} and GATE_VERSION >= 15
    verdict = gate(rows, _meta(2), printed_repeats=groups)
    assert verdict.admitted, verdict.reasons
    # Printed once (the daily-balance line prints a date and a figure, no words): the repeat stays refused.
    once = [["FABRICATED SERVICE FEE 01/05 1.50", "01/05 1.50"]]
    assert printed_repeat_groups(rows, once) == frozenset()
    assert "duplicate_row" in gate(rows, _meta(2), printed_repeats=printed_repeat_groups(rows, once)).reasons
    # A line printing the fee under another date, or on another page, proves nothing for this one.
    elsewhere = [["FABRICATED SERVICE FEE 01/05 1.50", "FABRICATED SERVICE FEE 01/06 1.50"]]
    assert printed_repeat_groups(rows, elsewhere) == frozenset()
    assert printed_repeat_groups([replace(rows[1], page=2), rows[0]], twice) == frozenset()
    # A k-up line prints each of its date and amount pairs.
    kup = [["FABRICATED DEPOSIT 01/05 1.50 FABRICATED DEPOSIT 01/05 1.50"]]
    assert printed_repeat_groups(rows, kup) == {(1, "2031-01-05", Decimal("1.50"))}
    # Review 6, finding 2: the whole printed date is matched. "Jan 5" is not every line of January.
    named = [replace(row, date_text="Jan 5") for row in rows]
    month = [["Jan 5 FABRICATED SERVICE FEE 1.50", "Jan 12 FABRICATED SERVICE FEE 1.50", "Jan 51 FABRICATED 1.50"]]
    assert printed_repeat_groups(named, month) == frozenset()
    assert "duplicate_row" in gate(named, _meta(2), printed_repeats=printed_repeat_groups(named, month)).reasons
    twice_named = [["Jan 5 FABRICATED SERVICE FEE 1.50", "JAN  5 FABRICATED SERVICE FEE 1.50"]]
    assert printed_repeat_groups(named, twice_named) == {(1, "2031-01-05", Decimal("1.50"))}
    # A printed date text without a digit never counts, nor a bare day number (any "5" on a line).
    assert printed_repeat_groups([replace(row, date_text="Jan") for row in rows], month) == frozenset()
    bare = [["12 FABRICATED CHECK 5 1.50", "12 FABRICATED STORE 5 1.50"]]
    assert printed_repeat_groups([replace(row, date_text="5") for row in rows], bare) == frozenset()
