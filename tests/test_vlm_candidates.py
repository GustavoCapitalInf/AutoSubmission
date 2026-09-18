from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.candidates import gate_candidates, union_rows
from vlm.metadata import AccountMeta


def _rows(n=4, source="stage_b", skip=()):
    rows, balance = [], Decimal("500.00")
    for i in range(1, n + 1):
        amount = Decimal(i * 10)
        balance += amount
        if i in skip:
            continue
        rows.append(CandidateRow(f"2031-01-{i:02d}", f"01/{i:02d}", f"SYNTHETIC ROW {i:02d}", amount, "credit", balance, 0, source, f"{source[-1]}r{i}"))
    return rows


META = AccountMeta(Decimal("500.00"), Decimal("600.00"), "2031-01-01", "2031-01-31", "USD", "0001", "BANK", ("t",))


def test_stage_b_wins_when_it_reconciles():
    verdict, which, summary = gate_candidates(_rows(), _rows(source="stage_a"), META)
    assert verdict.admitted and which == "stage_b" and summary == {"stage_b": []}


def test_stage_a_rescues_a_model_miss():
    verdict, which, summary = gate_candidates(_rows(skip=(3,)), _rows(source="stage_a"), META)
    assert verdict.admitted and which == "stage_a" and summary["stage_b"] and summary["stage_a"] == []
    assert all(r.source == "stage_a" for r in verdict.admitted_rows)


def test_union_rescues_complementary_misses():
    b = _rows(skip=(3,))
    a = _rows(source="stage_a", skip=(1,))
    verdict, which, summary = gate_candidates(b, a, META)
    assert verdict.admitted and which == "union"
    assert sorted(r.date for r in verdict.admitted_rows) == [f"2031-01-{i:02d}" for i in range(1, 5)]
    assert {r.source for r in verdict.admitted_rows} == {"stage_b", "stage_a+union"}


def test_union_never_duplicates_and_first_verdict_is_kept_when_all_fail():
    merged = union_rows(_rows(), _rows(source="stage_a"))
    assert len(merged) == 4
    bad_meta = AccountMeta(Decimal("500.00"), Decimal("999.00"), None, None, "USD", None, None, ())
    verdict, which, summary = gate_candidates(_rows(), _rows(source="stage_a"), bad_meta)
    assert not verdict.admitted and which == "none" and set(summary) == {"stage_b", "stage_a", "union"}
    assert "sum_mismatch" in verdict.reasons


def test_extra_reasons_apply_to_every_candidate():
    verdict, which, summary = gate_candidates(_rows(), _rows(source="stage_a"), META, extra_reasons=("anchor_disagreement",))
    assert not verdict.admitted and which == "none" and all("anchor_disagreement" in v for v in summary.values())
