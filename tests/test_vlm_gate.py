from dataclasses import replace
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.gate import GATE_VERSION, gate, resolve_directions
from vlm.metadata import EMPTY_META, AccountMeta


def _rows(n=4, start=Decimal("500.00"), direction="credit"):
    rows, balance = [], start
    for i in range(1, n + 1):
        amount = Decimal(i * 10)
        balance = balance + amount if direction == "credit" else balance - amount
        rows.append(CandidateRow(f"2031-01-{i:02d}", f"01/{i:02d}", f"SYNTHETIC ROW {i:02d}", amount, direction,
                                 balance, 0, "stage_a", f"t0r{i}"))
    return rows


def _meta(begin="500.00", end="600.00", **extra):
    return AccountMeta(Decimal(begin) if begin else None, Decimal(end) if end else None, "2031-01-01", "2031-01-31",
                       "USD", "0001", "SYNTHETIC BANK", ("test",), **extra)


def test_reconciled_ledger_is_admitted_strictly():
    verdict = gate(_rows(), _meta())
    assert verdict.admitted and verdict.reasons == () and verdict.row_count == 4 and verdict.anchored == "both"
    assert verdict.computed_ending == Decimal("600.00") and verdict.continuity_breaks == 0
    assert verdict.checks["gate_version"] == GATE_VERSION and verdict.checks["derived"] == []


def test_tampered_amount_is_refused_with_codes():
    rows = _rows()
    rows[2] = CandidateRow(rows[2].date, rows[2].date_text, rows[2].description, Decimal("31.00"), "credit",
                           rows[2].balance, 0, "stage_a", rows[2].locator)
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "sum_mismatch" in verdict.reasons and "continuity_break" in verdict.reasons
    assert verdict.admitted_rows == ()


def test_missing_row_is_refused():
    rows = _rows()
    del rows[1]
    assert "sum_mismatch" in gate(rows, _meta()).reasons


def test_both_anchors_derived_is_refused_and_truncation_cannot_pass():
    full, short = _rows(6), _rows(6)[:3]
    for rows in (full, short):
        verdict = gate(rows, EMPTY_META)
        assert not verdict.admitted and verdict.reasons == ("anchors_underdetermined",) and verdict.anchored == "none"


def test_one_printed_anchor_is_recorded_but_never_admitted():
    verdict = gate(_rows(), _meta(begin=None, end="600.00"))
    assert not verdict.admitted and verdict.reasons == ("anchor_derived",)
    assert verdict.anchored == "one" and verdict.checks["derived"] == ["beginning_balance"]
    verdict = gate(_rows(), _meta(begin="500.00", end=None))
    assert not verdict.admitted and verdict.reasons == ("anchor_derived",) and verdict.checks["derived"] == ["ending_balance"]
    # a truncated read with the ending derived from the last row reconciles trivially: that is WHY it is not admitted
    truncated = gate(_rows(6)[:3], _meta(begin="500.00", end=None))
    assert not truncated.admitted and "anchor_derived" in truncated.reasons


def test_chain_directions_need_both_printed_anchors():
    rows = [CandidateRow(r.date, r.date_text, r.description, r.amount, "unknown", r.balance, 0, "stage_a", r.locator)
            for r in _rows()]
    resolved, flagged = resolve_directions(rows, Decimal("500.00"))
    assert flagged == 4 and all(r.direction == "credit" and r.direction_source == "chain" for r in resolved)
    verdict = gate(rows, _meta())
    assert verdict.admitted and verdict.chain_derived_directions == 4
    unanchored = gate(rows, _meta(begin=None, end="600.00"))
    assert not unanchored.admitted and "chain_direction_unanchored" in unanchored.reasons


def test_misread_balance_with_chain_direction_is_refused_when_unanchored():
    rows = [CandidateRow("2031-01-01", "01/01", "A", Decimal("100.00"), "credit", Decimal("600.00"), 0, "stage_b", "p0r1"),
            CandidateRow("2031-01-02", "01/02", "B", Decimal("50.00"), "unknown", Decimal("650.00"), 0, "stage_b", "p0r2")]
    assert not gate(rows, EMPTY_META).admitted
    verdict = gate(rows, _meta(begin="500.00", end=None))
    assert not verdict.admitted and "chain_direction_unanchored" in verdict.reasons


def test_unknown_direction_without_balance_is_refused():
    rows = [CandidateRow(r.date, r.date_text, r.description, r.amount, "unknown", None, 0, "stage_a", r.locator)
            for r in _rows()]
    assert "direction_unknown" in gate(rows, _meta()).reasons


def test_date_checks():
    rows = _rows()
    rows[1] = CandidateRow(None, "??", rows[1].description, rows[1].amount, "credit", rows[1].balance, 0, "stage_a", "x")
    assert "date_unparsed" in gate(rows, _meta()).reasons
    rows = _rows()
    rows[1] = CandidateRow("2031-03-05", "03/05", rows[1].description, rows[1].amount, "credit", rows[1].balance, 0, "stage_a", "x")
    verdict = gate(rows, _meta())
    # gate v5: a row outside the printed period refuses; the order break is recorded, never refused
    assert not verdict.admitted and set(verdict.reasons) == {"period_mismatch", "date_order_chained"}
    assert verdict.checks["dates_outside_period"] == 1 and verdict.checks["date_order_breaks"] == 1
    rows = _rows()
    rows[1], rows[2] = rows[2], rows[1]   # same ledger, two rows swapped: an order break only
    verdict = gate(rows, _meta())
    assert verdict.checks["date_order_breaks"] == 1 and "period_mismatch" not in verdict.reasons


def test_duplicate_rows_with_balances_and_without():
    rows = _rows()
    rows.append(rows[-1])
    assert "duplicate_row" in gate(rows, _meta()).reasons
    # a genuine repeat distinguished by balances is not a duplicate
    repeat = [CandidateRow("2031-01-05", "01/05", "ATM FEE", Decimal("3.00"), "debit", Decimal("497.00"), 0, "stage_a", "a"),
              CandidateRow("2031-01-05", "01/05", "ATM FEE", Decimal("3.00"), "debit", Decimal("494.00"), 0, "stage_a", "b")]
    assert gate(repeat, _meta(begin="500.00", end="494.00")).admitted
    # without balances a repeat is unverifiable → refused, and a matching printed count never amnesties it (RR-2)
    meta = _meta(begin="1000.00", end="800.00")
    dup = [CandidateRow("2031-01-05", "01/05", "RENT", Decimal("100.00"), "debit", None, 0, "stage_b", "a"),
           CandidateRow("2031-01-05", "01/05", "RENT", Decimal("100.00"), "debit", None, 0, "stage_b", "b")]
    assert "duplicate_row" in gate(dup, meta).reasons
    counted = gate(dup, _meta(begin="1000.00", end="800.00", stated_credit_count=0, stated_debit_count=2))
    assert not counted.admitted and "duplicate_row" in counted.reasons and counted.checks["debit_count_matches"] is True


def test_coverage_shortfall_has_its_own_reason():
    rows = [CandidateRow("2031-01-03", "01/03", "DEPOSIT", Decimal("100.00"), "credit", None, 0, "stage_b", "a")]
    verdict = gate(rows, _meta(begin="500.00", end="600.00", stated_total_credits=Decimal("400.00")))
    assert not verdict.admitted and "coverage_mismatch" in verdict.reasons and "sum_mismatch" not in verdict.reasons


def test_printed_totals_and_counts_decide():
    meta = _meta(stated_total_credits=Decimal("100.00"), stated_total_debits=Decimal("0.00"), stated_credit_count=4, stated_debit_count=0)
    verdict = gate(_rows(), meta)
    assert verdict.admitted and verdict.checks["summary_ok"] is True and verdict.checks["credit_count_matches"] is True
    wrong_total = _meta(stated_total_credits=Decimal("150.00"), stated_total_debits=Decimal("0.00"))
    assert "summary_mismatch" in gate(_rows(), wrong_total).reasons
    wrong_count = _meta(stated_credit_count=5, stated_debit_count=0)
    assert "count_mismatch" in gate(_rows(), wrong_count).reasons


def test_no_rows():
    verdict = gate([], _meta())
    assert not verdict.admitted and verdict.reasons == ("no_rows",)


def test_reverse_chronological_statements_are_oriented():
    from vlm.gate import orient
    rows = list(reversed(_rows()))
    oriented, reversed_order = orient(rows)
    assert reversed_order and [r.date for r in oriented] == [r.date for r in _rows()]
    verdict = gate(rows, _meta())
    assert verdict.admitted and verdict.checks["reversed_order"] is True and verdict.continuity_breaks == 0


def test_repeated_daily_balances_collapse_to_the_last_row_of_the_day():
    from vlm.gate import collapse_daily_balances
    same_day = [CandidateRow("2031-01-05", "01/05", "A", Decimal("10.00"), "credit", Decimal("530.00"), 0, "stage_b", "a"),
                CandidateRow("2031-01-05", "01/05", "B", Decimal("20.00"), "credit", Decimal("530.00"), 0, "stage_b", "b"),
                CandidateRow("2031-01-06", "01/06", "C", Decimal("5.00"), "debit", Decimal("525.00"), 0, "stage_b", "c")]
    collapsed, n = collapse_daily_balances(same_day)
    assert n == 1 and collapsed[0].balance is None and collapsed[1].balance == Decimal("530.00") and collapsed[2].balance == Decimal("525.00")
    verdict = gate(same_day, _meta(begin="500.00", end="525.00"))
    assert verdict.admitted and verdict.checks["collapsed_daily_balances"] == 1 and verdict.continuity_breaks == 0


def test_rows_dated_outside_the_printed_period_refuse():
    rows = _rows()
    rows[1] = replace(rows[1], date="2029-01-02")
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "period_mismatch" in verdict.reasons and verdict.checks["dates_outside_period"] == 1
    assert gate(_rows(), _meta()).checks["dates_outside_period"] == 0


def test_balance_chained_statement_refuses_a_date_order_break_but_an_unchained_one_records_it():
    rows = _rows()
    rows[2] = replace(rows[2], date="2031-01-01")   # printed before its predecessor (01-02), balance intact
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "date_order_chained" in verdict.reasons
    assert verdict.checks["balance_chained"] is True and verdict.checks["date_order_breaks"] == 1
    unchained = [replace(r, balance=None) for r in rows]
    verdict = gate(unchained, _meta())
    assert verdict.checks["balance_chained"] is False and "date_order_chained" not in verdict.reasons
