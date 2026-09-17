from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.gate import GATE_VERSION, gate, resolve_directions
from vlm.metadata import AccountMeta


def _rows(n=4, start=Decimal("500.00"), direction="credit"):
    rows, balance = [], start
    for i in range(1, n + 1):
        amount = Decimal(i * 10)
        balance = balance + amount if direction == "credit" else balance - amount
        rows.append(CandidateRow(f"2031-01-{i:02d}", f"01/{i:02d}", f"SYNTHETIC ROW {i:02d}", amount, direction,
                                 balance, 0, "stage_a", f"t0r{i}"))
    return rows


def _meta(begin="500.00", end="600.00"):
    return AccountMeta(Decimal(begin) if begin else None, Decimal(end) if end else None, "2031-01-01", "2031-01-31",
                       "USD", "0001", "SYNTHETIC BANK", ("test",))


def test_reconciled_ledger_is_admitted():
    verdict = gate(_rows(), _meta())
    assert verdict.admitted and verdict.reasons == () and verdict.row_count == 4
    assert verdict.computed_ending == Decimal("600.00") and verdict.continuity_breaks == 0
    assert verdict.checks["gate_version"] == GATE_VERSION


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
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "sum_mismatch" in verdict.reasons


def test_unknown_direction_resolved_by_chain_and_flagged():
    rows = [CandidateRow(r.date, r.date_text, r.description, r.amount, "unknown", r.balance, 0, "stage_a", r.locator)
            for r in _rows()]
    resolved, flagged = resolve_directions(rows, Decimal("500.00"))
    assert flagged == 4 and all(r.direction == "credit" and r.direction_source == "chain" for r in resolved)
    verdict = gate(rows, _meta())
    assert verdict.admitted and verdict.chain_derived_directions == 4


def test_unknown_direction_without_balance_is_refused():
    rows = [CandidateRow(r.date, r.date_text, r.description, r.amount, "unknown", None, 0, "stage_a", r.locator)
            for r in _rows()]
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "direction_unknown" in verdict.reasons


def test_missing_balances_are_derived_from_chain():
    verdict = gate(_rows(), AccountMeta(None, None, None, None, None, None, None, ()))
    assert verdict.admitted and verdict.checks["derived"] == ["beginning_balance", "ending_balance"]


def test_date_checks():
    rows = _rows()
    rows[1] = CandidateRow(None, "??", rows[1].description, rows[1].amount, "credit", rows[1].balance, 0, "stage_a", "x")
    assert "date_unparsed" in gate(rows, _meta()).reasons
    rows = _rows()
    rows[1] = CandidateRow("2031-03-05", "03/05", rows[1].description, rows[1].amount, "credit", rows[1].balance, 0, "stage_a", "x")
    reasons = gate(rows, _meta()).reasons
    assert "date_out_of_period" in reasons and "date_not_monotonic" in reasons


def test_duplicate_row_refused_and_no_rows():
    rows = _rows()
    rows.append(rows[-1])
    assert "duplicate_row" in gate(rows, _meta()).reasons
    verdict = gate([], _meta())
    assert not verdict.admitted and verdict.reasons == ("no_rows",)
