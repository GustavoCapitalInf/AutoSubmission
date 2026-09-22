"""Fabricated gate rows only: counts and provenance must not change admission."""
from collections import Counter
from dataclasses import replace
from decimal import Decimal
import json

import pytest

from analysis.reconcile import reconcile
from vlm.assemble import CandidateRow
from vlm.gate import GATE_VERSION, REASONS, GateVerdict, gate, statement_from
from vlm.metadata import AccountMeta


def _rows(count=4):
    return [CandidateRow(f"2035-01-{index + 1:02}", "fabricated date", f"FABRICATED ROW {index}",
                         Decimal("10"), "credit", Decimal(110 + index * 10),
                         index + 1, "synthetic", f"synthetic-{index}")
            for index in range(count)]


def _meta(count=4, **changes):
    base = AccountMeta(Decimal("100"), Decimal(100 + count * 10),
                       "2035-01-01", "2035-01-31", "USD", None, "FABRICATED", ())
    return replace(base, **changes)


def _events(verdict, code):
    return [event for event in verdict.occurrences if event["code"] == code]


def test_public_contract_is_compatible_and_clean_on_admission():
    assert {"currency_missing", "page_unresolved"} <= set(REASONS)
    assert GATE_VERSION > 7
    legacy = GateVerdict(False, ("no_rows",), 0, (), None, 0, 0, {})
    assert legacy.occurrences == ()
    verdict = gate(_rows(), _meta())
    assert verdict.admitted and verdict.reasons == () and verdict.occurrences == ()
    assert verdict.computed_ending == Decimal("140.00")


def test_amount_failures_count_each_row_and_failing_field():
    rows = _rows()
    rows[0] = replace(rows[0], amount=Decimal("0"))
    rows[1] = replace(rows[1], amount=Decimal("-5"), printed_amount=Decimal("3"))
    rows[2] = replace(rows[2], printed_amount=Decimal("2"))
    verdict = gate(rows, _meta())
    assert verdict.reasons == ("proposal_invalid",)
    assert Counter((event["page"], event["field"]) for event in verdict.occurrences) == {
        (1, "amount"): 1, (2, "amount"): 1,
        (2, "printed_amount"): 1, (3, "printed_amount"): 1,
    }
    assert not verdict.admitted and verdict.admitted_rows == ()


def test_unknown_directions_and_missing_dates_count_separate_rows():
    rows = [replace(row, direction="unknown", balance=None, date=None) for row in _rows(3)]
    verdict = gate(rows, _meta(3))
    assert verdict.reasons == ("direction_unknown", "date_unparsed")
    assert [event["page"] for event in _events(verdict, "direction_unknown")] == [1, 2, 3]
    assert [event["page"] for event in _events(verdict, "date_unparsed")] == [1, 2, 3]


def test_malformed_nonnull_date_keeps_existing_refusal_behavior():
    with pytest.raises(ValueError):
        gate([replace(_rows(1)[0], date="2035-02-30")], _meta(1))


def test_period_failure_and_date_order_use_triggering_row_pages():
    rows = _rows(6)
    dates = ["2035-01-01", "2035-01-03", "2035-01-02", "2035-01-05", "2035-01-04", "2035-01-06"]
    verdict = gate([replace(row, date=value) for row, value in zip(rows, dates)], _meta(6))
    assert verdict.reasons == ("date_order_chained",)
    assert [event["page"] for event in verdict.occurrences] == [3, 5]
    outside = gate([replace(row, date=f"2035-03-{index + 1:02}")
                    for index, row in enumerate(rows)], _meta(6))
    assert outside.reasons == ("period_mismatch",)
    assert len(outside.occurrences) == outside.checks["dates_outside_period"] == 6
    assert [event["page"] for event in outside.occurrences] == list(range(1, 7))


def test_unanchored_chain_direction_occurrences_match_newly_resolved_rows():
    rows = _rows(4)
    rows[1:] = [replace(row, direction="unknown") for row in rows[1:]]
    verdict = gate(rows, _meta(4, ending_balance=None))
    assert verdict.reasons == ("anchor_derived", "chain_direction_unanchored")
    assert [event["page"] for event in _events(verdict, "chain_direction_unanchored")] == [2, 3, 4]
    assert _events(verdict, "anchor_derived") == [
        {"code": "anchor_derived", "page": None, "source": "gate", "field": "ending_balance"}]


def test_duplicate_occurrences_count_later_rows_not_pair_comparisons():
    row = replace(_rows(1)[0], balance=None)
    rows = [replace(row, page=page, locator=f"synthetic-{page}") for page in [2, 4, 8]]
    verdict = gate(rows, _meta(3))
    assert verdict.reasons == ("duplicate_row",)
    assert verdict.checks["repeats"]["unverifiable"] == 3
    assert [event["page"] for event in verdict.occurrences] == [4, 8]


def test_distinguished_repeated_rows_do_not_get_duplicate_occurrences():
    row = _rows(1)[0]
    rows = [row, replace(row, page=9, balance=Decimal("120"))]
    verdict = gate(rows, _meta(2))
    assert verdict.admitted and verdict.occurrences == ()
    assert verdict.checks["repeats"] == {"distinguished": 1, "unverifiable": 0}


def test_continuity_occurrences_are_uncapped_and_use_actual_pages():
    rows = [replace(row, balance=Decimal(111 + index * 11), page=index // 2 + 1)
            for index, row in enumerate(_rows(8))]
    verdict = gate(rows, _meta(8))
    result = reconcile(statement_from(rows, _meta(8)))
    occurrences = _events(verdict, "continuity_break")
    assert len(occurrences) == verdict.continuity_breaks == result.continuity_breaks == 8
    assert Counter(event["page"] for event in occurrences) == {1: 2, 2: 2, 3: 2, 4: 2}
    assert verdict.reasons == ("continuity_break", "coverage_mismatch")
    assert _events(verdict, "coverage_mismatch")[0]["page"] is None


@pytest.mark.parametrize("balance,breaks", [("115", 0), ("116", 1)])
def test_continuity_replay_keeps_fee_signed_and_collapsed_daily_balance_semantics(balance, breaks):
    rows = _rows(3)
    rows[0] = replace(rows[0], amount=Decimal("20"), balance=Decimal(balance))
    rows[1] = replace(rows[1], date=rows[0].date, amount=Decimal("5"), direction="debit",
                      description="FABRICATED FEE", balance=Decimal(balance), page=7)
    rows[2] = replace(rows[2], amount=Decimal("3"), direction="credit",
                      printed_amount=Decimal("-3"), balance=Decimal(balance) - 3)
    meta = _meta(3, ending_balance=Decimal("112"), stated_service_charge=Decimal("5"))
    from vlm.gate import collapse_daily_balances
    normalized, _ = collapse_daily_balances(rows)
    result = reconcile(statement_from(normalized, meta))
    verdict = gate(rows, meta)
    events = _events(verdict, "continuity_break")
    assert len(events) == verdict.continuity_breaks == result.continuity_breaks == breaks
    assert [event["page"] for event in events] == ([7] if breaks else [])
    assert verdict.checks["collapsed_daily_balances"] == 1
    assert verdict.computed_ending == Decimal("112.00")


def test_aggregate_field_failures_are_counted_without_page_attribution():
    rows = [replace(_rows(1)[0], amount=Decimal("10"), balance=None),
            replace(_rows(2)[1], amount=Decimal("10"), direction="debit", balance=None)]
    meta = _meta(2, ending_balance=Decimal("100"),
                 stated_total_credits=Decimal("20"), stated_total_debits=Decimal("20"),
                 stated_credit_count=3, stated_debit_count=4)
    verdict = gate(rows, meta)
    assert verdict.reasons == ("count_mismatch", "coverage_mismatch")
    assert Counter(event["code"] for event in verdict.occurrences) == {
        "count_mismatch": 2, "coverage_mismatch": 2}
    assert {event["field"] for event in verdict.occurrences} == {
        "stated_credit_count", "stated_debit_count", "stated_total_credits", "stated_total_debits"}
    assert all(event["page"] is None for event in verdict.occurrences)


def test_document_failures_have_no_fabricated_page_and_occurrences_have_no_source_values():
    verdict = gate(_rows(), _meta(4, ending_balance=Decimal("170"),
                                stated_total_credits=Decimal("80"), stated_total_debits=Decimal("0")))
    assert verdict.reasons == ("sum_mismatch", "summary_mismatch")
    assert all(event == {"code": event["code"], "page": None, "source": "gate"}
               for event in verdict.occurrences)
    for event in verdict.occurrences:
        assert set(event) <= {"code", "page", "source", "field"}
    assert "FABRICATED" not in json.dumps(verdict.occurrences)
    empty = gate([], _meta())
    assert empty.occurrences == ({"code": "no_rows", "page": None, "source": "gate"},)


def test_incomplete_document_keeps_source_failures_without_ledger_cascades(monkeypatch):
    rows = _rows(4)
    rows[0] = replace(rows[0], amount=Decimal("0"), page=2)
    rows[1] = replace(rows[1], direction="unknown", date=None, page=2)
    rows[2] = replace(rows[2], date="2035-04-01", page=5)
    rows[3] = replace(rows[2], locator="synthetic-repeat", balance=None, page=5)
    monkeypatch.setattr("vlm.gate.reconcile", lambda *a, **k: pytest.fail("partial ledger reconciled"))
    meta = _meta(4, beginning_balance=None, ending_balance=None,
                 stated_total_credits=Decimal("999"), stated_credit_count=999)
    verdict = gate(rows, meta, complete_document=False)
    assert not verdict.admitted and verdict.admitted_rows == () and verdict.computed_ending is None
    assert verdict.checks["document_checks_deferred"] is True
    assert verdict.reasons == ("proposal_invalid", "direction_unknown", "date_unparsed", "period_mismatch", "duplicate_row")
    assert Counter((event["code"], event["page"]) for event in verdict.occurrences) == {
        ("proposal_invalid", 2): 1, ("direction_unknown", 2): 1,
        ("date_unparsed", 2): 1, ("period_mismatch", 5): 2, ("duplicate_row", 5): 1,
    }
    assert verdict.continuity_breaks == verdict.chain_derived_directions == 0


def test_incomplete_subset_does_not_infer_directions_or_reorder_rows(monkeypatch):
    rows = [replace(row, direction="unknown") for row in reversed(_rows(3))]
    for helper in ("orient", "collapse_daily_balances", "resolve_directions", "reconcile"):
        monkeypatch.setattr("vlm.gate." + helper,
                            lambda *a, **k: pytest.fail("whole-ledger helper reached"))
    verdict = gate(rows, _meta(3), complete_document=False)
    assert verdict.reasons == ("direction_unknown",)
    assert [event["page"] for event in verdict.occurrences] == [3, 2, 1]
    assert "date_order_breaks" not in verdict.checks
    assert verdict.checks["derived"] == []
    assert verdict.chain_derived_directions == 0


@pytest.mark.parametrize("rows", [[], _rows(2)])
def test_valid_or_empty_incomplete_subset_is_held_without_invented_failures(rows):
    verdict = gate(rows, _meta(2), complete_document=False)
    assert not verdict.admitted and verdict.reasons == () and verdict.occurrences == ()
    assert verdict.row_count == len(rows)
    assert verdict.computed_ending is None and verdict.admitted_rows == ()
    assert verdict.checks["document_checks_deferred"] is True
