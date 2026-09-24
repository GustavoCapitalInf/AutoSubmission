"""Fabricated rows only. Some banks print every debit with a minus ("-$30.00" in a Debits column). That minus
is the column's print style, not a reversal; a negative among positive values of its column stays a reversal.
Read either way wrongly, the balance and sum checks refuse the statement."""
from dataclasses import replace
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.gate import gate, minus_styled
from vlm.metadata import AccountMeta


def _row(index, amount, direction, printed, balance):
    return CandidateRow(f"2035-01-{index + 1:02}", "fabricated date", f"FABRICATED ROW {index}", Decimal(amount),
                        direction, Decimal(balance), 1, "synthetic", f"synthetic-{index}",
                        printed_amount=None if printed is None else Decimal(printed))


def _meta(beginning, ending):
    return AccountMeta(Decimal(beginning), Decimal(ending), "2035-01-01", "2035-01-31", "USD", None, "FABRICATED", ())


def test_a_debits_column_that_prints_every_value_with_a_minus_is_a_style():
    rows = [_row(0, "30.00", "debit", "-30.00", "70.00"),
            _row(1, "20.00", "debit", "-20.00", "50.00"),
            _row(2, "40.00", "credit", "40.00", "90.00")]
    assert minus_styled(rows) == frozenset({"debit"})
    verdict = gate(rows, _meta("100.00", "90.00"))
    assert verdict.admitted and verdict.computed_ending == Decimal("90.00")


def test_a_negative_among_positive_debits_stays_a_reversal():
    rows = [_row(0, "30.00", "debit", "30.00", "70.00"),
            _row(1, "5.00", "debit", "-5.00", "75.00"),       # a reversal: the money came back
            _row(2, "40.00", "credit", "40.00", "115.00")]
    assert minus_styled(rows) == frozenset()
    verdict = gate(rows, _meta("100.00", "115.00"))
    assert verdict.admitted and verdict.computed_ending == Decimal("115.00")


def test_a_single_negative_debit_is_not_enough_to_call_a_style():
    rows = [_row(0, "5.00", "debit", "-5.00", "105.00"),      # a lone reversal
            _row(1, "40.00", "credit", "40.00", "145.00")]
    assert minus_styled(rows) == frozenset()
    assert gate(rows, _meta("100.00", "145.00")).admitted


def test_a_style_read_where_the_money_really_came_back_is_refused_not_admitted():
    # Two printed negatives in the debit column that really were reversals (the balance rose): taking them
    # for the column's style makes the balance walk and the sum fail, so the statement is held.
    rows = [_row(0, "5.00", "debit", "-5.00", "105.00"),
            _row(1, "7.00", "debit", "-7.00", "112.00")]
    verdict = gate(rows, _meta("100.00", "112.00"))
    assert not verdict.admitted
    assert {"continuity_break", "sum_mismatch"} & set(verdict.reasons)


def test_a_ledger_one_cent_short_is_refused():
    # A missing one-cent credit (printed ".01") left the sum exactly one cent off, which a one-cent tolerance
    # admitted (gate v13).
    rows = [_row(0, "30.00", "debit", None, "70.00"), _row(1, "40.00", "credit", None, "110.00")]
    rows = [CandidateRow(row.date, row.date_text, row.description, row.amount, row.direction, None, row.page,
                         row.source, row.locator) for row in rows]
    assert gate(rows, _meta("100.00", "110.00")).admitted
    verdict = gate(rows, _meta("100.00", "110.01"))
    assert not verdict.admitted and "sum_mismatch" in verdict.reasons


def test_the_style_is_judged_per_direction():
    rows = [_row(0, "30.00", "debit", "-30.00", "70.00"),
            _row(1, "20.00", "debit", "-20.00", "50.00"),
            _row(2, "40.00", "credit", "40.00", "90.00"),
            _row(3, "10.00", "credit", "-10.00", "80.00")]  # a credit reversal among positive credits
    assert minus_styled(rows) == frozenset({"debit"})
    assert gate([replace(row) for row in rows], _meta("100.00", "80.00")).admitted
