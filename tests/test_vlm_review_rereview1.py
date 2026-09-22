"""Re-review 1 counterexamples of CEILING-HARNESS-REVIEW-X, INVERTED after the closures.

Reviewer X's characterisation tests pinned RR-1..RR-7; each is now asserted the fixed way round so a
regression fails the suite. All fixtures synthetic; no statement is read.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from vlm import metadata, runner
from vlm.assemble import CandidateRow
from vlm.gate import gate
from vlm.metadata import AccountMeta
from vlm.report import _is_false_accept


def _row(day: int, amount: str, direction: str, balance: str | None, desc: str = "SYNTHETIC ROW") -> CandidateRow:
    return CandidateRow(date=f"2031-01-{day:02d}", date_text=f"01/{day:02d}", description=f"{desc} {day:02d}",
                        amount=Decimal(amount), direction=direction,
                        balance=None if balance is None else Decimal(balance), page=0, source="stage_b",
                        locator=f"p0r{day}")


def _meta(beginning: str, ending: str, **kw) -> AccountMeta:
    return AccountMeta(Decimal(beginning), Decimal(ending), "2031-01-01", "2031-01-31", "USD", None, None, ("t",), **kw)


# RR-2 — closed: no count amnesty; the report aggregates admitted repeats (must be 0)
def test_unverifiable_repeat_is_refused_even_when_the_printed_count_matches():
    meta = _meta("1000.00", "750.00", stated_total_debits=Decimal("250.00"), stated_debit_count=3, stated_credit_count=0)
    truth = [_row(5, "100.00", "debit", None, "RENT"), _row(6, "100.00", "debit", None, "INSURANCE"), _row(7, "50.00", "debit", None, "FEE")]
    dropped_and_duplicated = [_row(5, "100.00", "debit", None, "RENT"), _row(5, "100.00", "debit", None, "RENT"), _row(7, "50.00", "debit", None, "FEE")]
    assert gate(truth, meta).admitted
    verdict = gate(dropped_and_duplicated, meta)
    assert not verdict.admitted and "duplicate_row" in verdict.reasons and verdict.admitted_rows == ()
    assert verdict.checks["repeats"] == {"distinguished": 0, "unverifiable": 1}
    assert "repeats" in Path("vlm/report.py").read_text(encoding="utf-8")


# RR-1 — closed: a rule/model disagreement on an anchor is recorded and refuses; corroboration is counted
def test_hybrid_records_anchor_corroboration_and_refuses_a_disagreement():
    claimed = AccountMeta(Decimal("490.00"), Decimal("710.00"), "2031-01-01", "2031-01-31", "USD", None, None, ("meta:stage_b",))
    rule_read = AccountMeta(Decimal("500.00"), Decimal("710.00"), "2031-01-01", "2031-01-31", "USD", None, None, ("beginning:rule", "ending:rule"))
    out = runner._corroborate(claimed, rule_read)
    assert out["summary"] == "disagreement" and out["fields"]["beginning_balance"] == "disagree" and out["fields"]["ending_balance"] == "agree"
    agree = runner._corroborate(rule_read, rule_read)
    assert agree["summary"] == "corroborated"
    model_only = runner._corroborate(claimed, AccountMeta(None, None, None, None, None, None, None, ()))
    assert model_only["summary"] == "model_only"
    source = Path("vlm/runner.py").read_text(encoding="utf-8")
    assert "anchor_disagreement" in source and "anchor_corroboration" in source


# RR-3 — closed: a balance mismatch on a matched row is a false accept; a description difference is
# reported apart (admitted_with_description_mismatches): on real pages it is formatting, not a wrong row
def test_false_accept_sees_balance_mismatches_and_reports_descriptions_apart():
    doc = {"sha": "A" * 64, "gate": {"admitted": True},
           "match": {"truth_rows": 2, "candidate_rows": 2, "matched": 2, "exact_balance": 2, "exact_description": 1, "missing": 0, "extra": 0}}
    assert _is_false_accept(doc) is False
    assert _is_false_accept({**doc, "match": {**doc["match"], "balance_mismatch": 1}}) is True
    assert _is_false_accept({**doc, "match": {**doc["match"], "missing": 1}}) is True
    assert "admitted_with_description_mismatches" in Path("vlm/report.py").read_text(encoding="utf-8")


# RR-5 — closed: no digest of the account digits in the public stats
def test_account_last4_is_published_as_a_count_only():
    from vlm.proposals import PageProposal, merge_pages
    from vlm.schema import empty_proposal

    proposal = empty_proposal("statement_page")
    proposal["account"]["account_number_last4"] = "4821"
    _, _, stats = merge_pages([PageProposal(0, proposal, ())])
    assert stats["account_last4_count"] == 1 and "account_last4_set_sha256" not in stats and "4821" not in json.dumps(stats)


# RR-6 — closed: a parenthesised count belongs to its own field only
def test_printed_count_is_bound_to_the_labels_own_field():
    meta = metadata.extract_meta(["Total deposits 3,450.00 Checks paid (14) 1,200.00"])
    assert meta.stated_total_credits == Decimal("3450.00") and meta.stated_credit_count is None
    meta = metadata.extract_meta(["Deposits and other credits (12) 3,450.00"])
    assert meta.stated_credit_count == 12


# RR-7 — closed: a coverage shortfall has its own reason
def test_coverage_shortfall_is_reported_as_coverage_mismatch():
    rows = [_row(3, "100.00", "credit", None, "DEPOSIT")]
    verdict = gate(rows, _meta("500.00", "600.00", stated_total_credits=Decimal("400.00")))
    assert not verdict.admitted and "coverage_mismatch" in verdict.reasons and "sum_mismatch" not in verdict.reasons
    assert any("captured" in issue for issue in verdict.checks["reader_issues"])


# RR-4 — closed: the weights pin is keyed on the served model and never silently empty
def test_weights_pin_is_keyed_on_the_served_model(tmp_path):
    from tools import vlm_ceiling
    from vlm.receipts import Refused

    assert vlm_ceiling._stage_b_key("RedHatAI/Qwen3.5-9B-FP8-dynamic") == "b9" and vlm_ceiling._stage_b_key("Qwen/Qwen3.5-4B") == "b"
    with pytest.raises(Refused):
        vlm_ceiling._stage_b_key("nobody/unknown")
    with pytest.raises(Refused) as exc:
        vlm_ceiling._weights_bindings(tmp_path, ("b9",))
    assert exc.value.code == "weights_receipt_missing"
