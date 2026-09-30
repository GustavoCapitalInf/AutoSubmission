"""Classification 5.6 (true revenue spec §5.1, §5.4, §9.1, §10.7 server rules, §11, §12, T6 to T10): the contribution
flags, the metrics, the detection lists, the serialized views and their rebuild, the review writer, the gate and the
True-revenue withholding mode. Fabricated rows only."""
from __future__ import annotations

import copy
from dataclasses import asdict

import pytest

from analysis.metrics import compute_metrics
from analysis.revenue import (
    REVENUE_REVIEW_HELD_SHARE,
    REVENUE_TIER_REASONS,
    apply_serialized_revenue_review,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
    revenue_contribution_flags,
    revenue_review_gate,
    tier_of_state,
)
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction

ROWS = [
    ("2054-03-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0),     # verified (Q6 company form)
    ("2054-03-03", "MOBILE DEPOSIT", 300.0),                            # counted: check deposit
    ("2054-03-04", "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0),     # held: financing-named payer
    ("2054-03-05", "INTERNAL TRANSFER FROM SAVINGS", 100.0),            # non-revenue
    ("2054-03-06", "FABRIKAM SUPPLY DES:DEBIT ID:1", -50.0),
]


def _statement(rows=ROWS):
    return Statement(account_name="CONTOSO BAKERY LLC", currency="USD", transactions=[
        Transaction(date=day, description=text, amount=amount, direction="credit" if amount > 0 else "debit")
        for day, text, amount in rows
    ])


def _payload(rows=ROWS) -> dict:
    statement = _statement(rows)
    records = classify_statement_transactions(statement)
    return rebuild_serialized_revenue_views({
        "statement": {"currency": "USD", "transactions": [
            {**transaction.model_dump(), "classification": asdict(record)}
            for transaction, record in zip(statement.transactions, records)
        ]},
        "metrics": {}, "detection": {},
    })


def test_the_flags_follow_the_state_and_the_tier():
    assert revenue_contribution_flags("verified_revenue", "verified")["contributes_to_true_revenue"]
    counted = revenue_contribution_flags("unverified_deposit", "counted_flagged")
    assert counted["contributes_to_true_revenue"] and counted["contributes_to_counted_flagged"]
    assert counted["contributes_to_unverified_deposit"] and counted["contributes_to_potential_revenue"]
    held = revenue_contribution_flags("unverified_deposit", "excluded_pending_review")
    assert not held["contributes_to_true_revenue"] and held["contributes_to_excluded_pending_review"]
    assert not revenue_contribution_flags("non_revenue", "non_revenue")["contributes_to_true_revenue"]
    assert not revenue_contribution_flags("verified_revenue", None)["contributes_to_true_revenue"]


def test_every_reason_code_names_a_middle_tier():
    assert {tier for tier, _label in REVENUE_TIER_REASONS.values()} == {"counted_flagged", "excluded_pending_review"}
    assert len(REVENUE_TIER_REASONS) == 26


def test_a_record_carries_the_tier_its_state_fixes():
    assert (tier_of_state("verified_revenue"), tier_of_state("non_revenue"), tier_of_state("unverified_deposit")) == (
        "verified", "non_revenue", None)
    verified = classify_transaction("FABRIKAM MERCH DEP 1234567", 250.0, direction="credit")
    assert (verified.revenue_tier, verified.revenue_initial_tier, verified.revenue_tier_reason) == (
        "verified", "verified", None)
    assert verified.contributes_to_true_revenue
    transfer = classify_transaction("INTERNAL TRANSFER FROM SAVINGS", 100.0, direction="credit")
    assert transfer.revenue_tier == "non_revenue" and not transfer.contributes_to_true_revenue
    assert classify_transaction("CARD PURCHASE FABRIKAM SUPPLY", -120.0, direction="debit").revenue_tier is None


def test_a_proven_duplicate_credit_is_tiered_non_revenue():
    records = classify_statement_transactions(Statement(account_name="CONTOSO BAKERY LLC", transactions=[
        Transaction(date="2054-03-02", description="FABRIKAM MERCH DEP 1234567", amount=250.0, direction="credit",
                    running_balance=1250.0),
        Transaction(date="2054-03-02", description="FABRIKAM MERCH DEP 1234567", amount=250.0, direction="credit",
                    running_balance=1250.0),
    ]))
    assert [record.revenue_tier for record in records] == ["verified", "non_revenue"]
    assert not records[1].contributes_to_true_revenue

def test_the_metrics_carry_the_four_tiers_and_true_revenue():
    statement = _statement()
    metrics = compute_metrics(statement, classifications=classify_statement_transactions(statement))
    assert (metrics.verified_revenue_total, metrics.counted_flagged_total, metrics.excluded_pending_review_total,
            metrics.non_revenue_total) == (700.0, 300.0, 900.0, 100.0)
    assert metrics.true_revenue_total == metrics.true_revenue == 1000.0
    assert metrics.true_revenue_count == 2
    assert metrics.maximum_revenue == 1900.0
    assert metrics.counted_flagged_by_reason == {"check_deposit": {"count": 1, "total": 300.0}}
    assert metrics.excluded_pending_review_by_reason == {"financing_named_payer": {"count": 1, "total": 900.0}}
    assert metrics.revenue_review_items == 1
    assert metrics.revenue_reconciles
    assert [record.revenue_tier for record in metrics.true_revenue_evidence] == ["verified", "counted_flagged"]


def test_a_record_whose_tier_disagrees_with_its_state_is_refused():
    statement = _statement()
    records = classify_statement_transactions(statement)
    from dataclasses import replace
    records[1] = replace(records[1], revenue_tier="verified")
    with pytest.raises(ValueError, match="agree with its tier"):
        compute_metrics(statement, classifications=records)


@pytest.mark.parametrize(("held", "posted", "gated"), [
    (99.99, 1000.0, False),      # just under ten percent, in cents
    (100.0, 1000.0, True),       # exactly ten percent
    (0.0, 0.0, False),           # nothing posted, nothing held
])
def test_the_gate_compares_the_held_share_in_integer_cents(held, posted, gated):
    assert REVENUE_REVIEW_HELD_SHARE == 10
    assert revenue_review_gate(direction_conflict=False, held_total=held, posted_total=posted, reconciles=True) is gated
    assert revenue_review_gate(direction_conflict=True, held_total=0.0, posted_total=posted, reconciles=True)
    assert revenue_review_gate(direction_conflict=False, held_total=0.0, posted_total=posted, reconciles=False)


def test_the_serialized_views_carry_the_tiers_and_repoint_true_revenue():
    payload = _payload()
    metrics, detection = payload["metrics"], payload["detection"]
    assert (metrics["true_revenue_total"], metrics["counted_flagged_total"], metrics["excluded_pending_review_total"]) == (
        1000.0, 300.0, 900.0)
    assert metrics["true_revenue"] == 1000.0 and metrics["confirmed_true_revenue_total"] == 700.0
    assert metrics["revenue_review_required"]            # 900 of 2000 posted is held
    assert metrics["revenue_review_items"] == 1
    assert len(detection["true_revenue_evidence"]) == 2
    assert len(detection["counted_flagged_evidence"]) == len(detection["excluded_pending_review_evidence"]) == 1
    assert [record["source_location"] for record in detection["manual_review"]
            if record.get("revenue_review_required")] == ["transaction:3"]


def test_confirm_reject_and_reset_move_the_tier():
    payload = _payload()
    confirmed = apply_serialized_revenue_review(copy.deepcopy(payload), source_location="transaction:3",
                                                decision="confirm")
    record = confirmed["statement"]["transactions"][2]["classification"]
    assert (record["revenue_classification"], record["revenue_tier"], record["revenue_tier_reason"]) == (
        "verified_revenue", "verified", "financing_named_payer")
    assert confirmed["metrics"]["true_revenue_total"] == 1900.0
    rejected = apply_serialized_revenue_review(copy.deepcopy(payload), source_location="transaction:2",
                                               decision="reject")
    assert rejected["statement"]["transactions"][1]["classification"]["revenue_tier"] == "non_revenue"
    reset = apply_serialized_revenue_review(rejected, source_location="transaction:2", decision="reset")
    reset_record = reset["statement"]["transactions"][1]["classification"]
    assert (reset_record["revenue_tier"], reset_record["revenue_review_status"]) == ("counted_flagged", "pending")
    assert not reset_record["revenue_review_required"]


def test_a_rule_verified_credit_can_be_rejected_but_not_confirmed():
    payload = _payload()
    with pytest.raises(ValueError, match="a credit a rule verified can only be marked non-revenue"):
        record_serialized_revenue_review(copy.deepcopy(payload), source_location="transaction:1", decision="confirm")
    rejected = apply_serialized_revenue_review(payload, source_location="transaction:1", decision="reject")
    record = rejected["statement"]["transactions"][0]["classification"]
    assert (record["revenue_classification"], record["revenue_tier"]) == ("non_revenue", "non_revenue")
    reset = apply_serialized_revenue_review(rejected, source_location="transaction:1", decision="reset")
    record = reset["statement"]["transactions"][0]["classification"]
    assert (record["revenue_tier"], record["revenue_review_status"]) == ("verified", "not_required")
    with pytest.raises(ValueError, match="only automatically unverified deposits"):
        record_serialized_revenue_review(reset, source_location="transaction:4", decision="reject")


def _untiered(payload: dict) -> dict:
    old = copy.deepcopy(payload)
    for transaction in old["statement"]["transactions"]:
        record = transaction["classification"]
        for key in ("revenue_tier", "revenue_initial_tier", "revenue_tier_reason"):
            record.pop(key, None)
    return old


def test_a_payload_analysed_before_5_6_takes_the_tier_less_path():
    old = rebuild_serialized_revenue_views(_untiered(_payload()))
    metrics = old["metrics"]
    assert metrics["true_revenue"] is None and metrics["true_revenue_evidence"] is None
    assert metrics["true_revenue_total"] is None and metrics["counted_flagged_by_reason"] is None
    assert metrics["verified_revenue_total"] == 700.0
    assert metrics["revenue_review_required"]                # a pending unverified deposit, today's rule
    assert all("contributes_to_true_revenue" not in transaction["classification"]
               for transaction in old["statement"]["transactions"] if transaction["amount"] > 0)
    # Its review follows today's rules: only an unverified deposit is reviewable, and no tier is written.
    confirmed = apply_serialized_revenue_review(old, source_location="transaction:2", decision="confirm")
    assert "revenue_tier" not in confirmed["statement"]["transactions"][1]["classification"]
    with pytest.raises(ValueError, match="only automatically unverified deposits"):
        record_serialized_revenue_review(old, source_location="transaction:1", decision="reject")


def _conflict_payload() -> dict:
    statement = Statement(account_name="CONTOSO BAKERY LLC", currency="USD", transactions=[
        Transaction(date="2054-03-02", description="NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", amount=5000.0,
                    direction="credit"),
        # A positive amount printed as a debit: a direction conflict (40 of 5,040 is under the held share).
        Transaction(date="2054-03-03", description="FABRIKAM SUPPLY LLC DES:PAYMENT ID:1", amount=40.0,
                    direction="debit"),
    ])
    records = classify_statement_transactions(statement)
    assert compute_metrics(statement, classifications=records).revenue_review_required
    return rebuild_serialized_revenue_views({
        "statement": {"currency": "USD", "transactions": [
            {**transaction.model_dump(), "classification": asdict(record)}
            for transaction, record in zip(statement.transactions, records)
        ]},
        "metrics": {}, "detection": {},
    })


@pytest.mark.parametrize("tiered", [True, False])
def test_a_direction_conflict_gates_only_while_it_is_undecided(tiered):
    # S4.4/S4.5 review, fix round 1 (§10.7, T7, §12): what needs review now is the undecided rows, so once the analyst
    # confirms or rejects the only conflicting credit the statement no longer waits on it; a reset makes it wait again.
    payload = _conflict_payload() if tiered else rebuild_serialized_revenue_views(_untiered(_conflict_payload()))
    record = payload["statement"]["transactions"][1]["classification"]
    assert (record["revenue_match_method"], record["revenue_review_status"]) == ("direction_conflict", "pending")
    assert payload["metrics"]["revenue_review_required"]
    for decision in ("confirm", "reject"):
        decided = apply_serialized_revenue_review(copy.deepcopy(payload), source_location="transaction:2",
                                                  decision=decision)
        assert decided["metrics"]["revenue_reconciles"]
        assert not decided["metrics"]["revenue_review_required"]
        reset = apply_serialized_revenue_review(decided, source_location="transaction:2", decision="reset")
        assert reset["metrics"]["revenue_review_required"]


def test_a_payload_tiered_only_in_part_is_refused():
    mixed = _payload()
    mixed["statement"]["transactions"][1]["classification"].pop("revenue_tier")
    with pytest.raises(ValueError, match="carries a revenue tier, or none does"):
        rebuild_serialized_revenue_views(mixed)


def test_true_revenue_is_a_selectable_withholding_denominator_never_the_default():
    statement = _statement()
    records = classify_statement_transactions(statement)
    legacy = compute_metrics(statement, classifications=records)
    assert legacy.withholding_denominator_mode == "legacy_eligible_deposits"
    true = compute_metrics(statement, classifications=records, withholding_denominator_mode="true_revenue")
    assert (true.eligible_deposits, true.withholding_denominator_label) == (1000.0, "True revenue")


# ---------------------------------------------------------------------------------------------------------------- S4.5
def _document_report(rows=None):
    from tests.test_webapp_studio_views import _report
    return _report("CONTOSO BAKERY LLC", "000000001010", 1500.0, rows or [
        (2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
        (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
        (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)])


def test_the_batch_csv_carries_true_revenue_and_its_counted_and_held_parts():
    from pathlib import Path

    import batch

    row = batch._row(Path("fabricated.pdf"), _document_report().accounts[0])
    assert batch.FIELDS.index("true_revenue_total") < batch.FIELDS.index("verified_revenue_total")
    assert (row["true_revenue_total"], row["counted_flagged_total"], row["excluded_pending_review_total"],
            row["verified_revenue_total"]) == ("1000.00", "300.00", "900.00", "700.00")
    assert row["needs_review"] == "REVIEW"   # the held credit is 45% of the posted credits (T7)


def test_the_cli_report_prints_true_verified_counted_and_held():
    import analyze

    text = analyze._render(_document_report().accounts[0])
    lines = [line.strip() for line in text.splitlines()]
    true_line = next(line for line in lines if line.startswith("True revenue"))
    assert "$1,000.00" in true_line
    assert lines.index(true_line) < lines.index(next(line for line in lines if line.startswith("Verified revenue")))
    assert any(line.startswith("Counted, not verified") and "$300.00" in line for line in lines)
    assert any(line.startswith("Held for review") and "$900.00" in line for line in lines)


def test_the_benchmark_compares_true_revenue_with_moneythumb_s_true_credits():
    from benchmark.compare import true_revenue_row
    from benchmark.normalize import MTStatementRow

    row = true_revenue_row("fabricated_set", "s1.true_revenue",
                           {"true_revenue_total": 1000.0, "verified_revenue_total": 700.0},
                           MTStatementRow(raw={}, true_credits=1000.0))
    assert (row.field, row.ours, row.mt) == ("s1.true_revenue", 1000.0, 1000.0)
    assert "Verified revenue beside it: 700.0" in row.rationale
    missing = true_revenue_row("fabricated_set", "s1.true_revenue", {"true_revenue_total": None}, None)
    assert (missing.ours, missing.mt) == (None, None)
