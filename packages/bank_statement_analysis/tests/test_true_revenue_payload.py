"""Classification 5.6 (true revenue spec §5.1, §5.4, §9.1, §10.7 server rules, §11, §12, T6 to T10): the contribution
flags, the metrics, the detection lists, the serialized views and their rebuild, the review writer, the gate and the
True-revenue withholding mode. Fabricated rows only."""
from __future__ import annotations

import copy
from dataclasses import asdict, replace

import pytest

from analysis.metrics import compute_metrics
from analysis.revenue import (
    NON_REVENUE_REASONS,
    REVENUE_REVIEW_HELD_SHARE,
    REVENUE_TIER_REASONS,
    TIER_METRIC_KEYS,
    apply_serialized_revenue_review,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
    revenue_contribution_flags,
    revenue_review_gate,
    tier_of_state,
)
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction

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
    return _rebuilt(statement, classify_statement_transactions(statement))


def _rebuilt(statement, records) -> dict:
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
    # The owner's rulings of 2026-10-02: the non_revenue codes end the table, the underwriter's Q3's zelle_excluded
    # (R2-OW02), then the display reason of Q12's rows, government_no_purpose (R2-OW03), then Q11's non-dealer asset
    # sales, asset_sale_proceeds (R2-OW06).
    assert {tier for tier, _label in REVENUE_TIER_REASONS.values()} == {
        "counted_flagged", "excluded_pending_review", "non_revenue"}
    assert [code for code, (tier, _label) in REVENUE_TIER_REASONS.items() if tier == "non_revenue"] == [
        "zelle_excluded", "government_no_purpose", "asset_sale_proceeds"]
    assert list(REVENUE_TIER_REASONS)[-3:] == ["zelle_excluded", "government_no_purpose", "asset_sale_proceeds"]
    assert NON_REVENUE_REASONS == frozenset({"zelle_excluded", "government_no_purpose", "asset_sale_proceeds"})
    # Owner ruling 2026-10-02 (the underwriter's Q11 (a)), R2-OW06: construction_progress_draw right after
    # lender_paid_for_services (CR5).
    # Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: insurer_paid_for_services right after
    # construction_progress_draw (CR5).
    # Owner ruling 2026-10-02 (the underwriter's Q9 (a), (b)), R2-OW09: finance_named_customer, then lessor_rent, right
    # after insurer_paid_for_services (CR5).
    codes = list(REVENUE_TIER_REASONS)
    assert codes[codes.index("factoring_payout") + 1: codes.index("factoring_payout") + 6] == [
        "lender_paid_for_services", "construction_progress_draw", "insurer_paid_for_services",
        "finance_named_customer", "lessor_rent"]
    assert REVENUE_TIER_REASONS["construction_progress_draw"] == ("counted_flagged", "Builder's progress draw")
    assert REVENUE_TIER_REASONS["insurer_paid_for_services"] == (
        "counted_flagged", "Insurer paid for the business's work")
    assert REVENUE_TIER_REASONS["finance_named_customer"] == (
        "counted_flagged", "Customer with a finance word in its name, paying an invoice")
    assert REVENUE_TIER_REASONS["lessor_rent"] == ("counted_flagged", "Rent received by a leasing or property business")
    assert "insurer_payer" in REVENUE_TIER_REASONS and "insurer_named_payer" in REVENUE_TIER_REASONS
    assert REVENUE_TIER_REASONS["asset_sale_proceeds"] == ("non_revenue", "Sale of equipment or vehicles (not a dealer)")
    # Audit B10 (I05, I60): payer_text_not_read is the 27th. Audit round 2, R2-B07 (R07): unread_run_names_financing
    # the 28th. The owner's ruling of 2026-10-02 (the underwriter's Q3): zelle_excluded, the 29th; R2-OW03:
    # government_no_purpose, the 30th. Owner ruling 2026-10-02 (Q8), R2-OW04: customer_financing_lump_sum after
    # financing_named_payer and customer_financing_payout after payout_credit_entity, the 31st and 32nd. Owner ruling
    # 2026-10-02 (the underwriter's Q9, part (c')), R2-OW05: lender_paid_for_services right after factoring_payout, the
    # 33rd. Owner ruling 2026-10-02 (the underwriter's Q11), R2-OW06: construction_progress_draw and
    # asset_sale_proceeds, the 34th and 35th. Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08:
    # insurer_paid_for_services, the 36th. Owner ruling 2026-10-02 (the underwriter's Q9), R2-OW09:
    # finance_named_customer and lessor_rent, the 37th and 38th. Q10 (owner 2026-10-02): premium_trust_account, the 39th
    # (R2-OW11). Q4 (owner 2026-10-02): own_account_transfer_matched, the 40th, the end of the held group (R2-OW16).
    assert len(REVENUE_TIER_REASONS) == 40
    assert REVENUE_TIER_REASONS["premium_trust_account"] == (
        "excluded_pending_review", "Deposit into a premium trust account")
    assert REVENUE_TIER_REASONS["own_account_transfer_matched"] == (
        "excluded_pending_review", "Matches a transfer out of another account in this package")
    codes = list(REVENUE_TIER_REASONS)
    assert codes[codes.index("premium_trust_account") + 1] == "own_account_transfer_matched"
    assert codes[codes.index("own_account_transfer_matched") + 1] == "wire_named_sender"
    assert codes[codes.index("premium_trust_account") - 1] == "p2p_round_repeat"
    assert "non_revenue_by_reason" in TIER_METRIC_KEYS


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
    # R2-OW03: the own-account transfer a non-revenue rule decided carries no reason, so the breakdown is empty.
    assert metrics.non_revenue_by_reason == {}
    assert metrics.revenue_review_items == 1
    assert metrics.revenue_reconciles
    assert [record.revenue_tier for record in metrics.true_revenue_evidence] == ["verified", "counted_flagged"]


def test_the_non_revenue_breakdown_names_a_non_dealer_s_asset_sales():
    # The owner's ruling of 2026-10-02 (the underwriter's Q11 (b)): a car buyer's payout and an equipment auction's
    # seller payment on a statement with no dealer are non_revenue / asset_sale_proceeds, shown in the non-revenue
    # breakdown beside the Zelle policy's code, by compute_metrics and by the rebuild alike.
    rows = [
        ("2054-03-01", "MOBILE DEPOSIT", 500.0),
        ("2054-03-02", "CARVANA PAYOUT DES:CVNA 12345 ID:1234567 INDN:NORTHWIND SOLAR LLC CO ID:1234567890 CCD", 1850.0),
        ("2054-03-03", "RITCHIE BROS DES:SELLER PMT ID:1234567 INDN:NORTHWIND SOLAR LLC CO ID:1234567890 CCD", 15000.0),
        ("2054-03-04", "ZELLE PAYMENT FROM PAT SAMPLE CONF 1", 300.0),
    ]
    statement = Statement(account_name="NORTHWIND SOLAR LLC", bank="Bank of America", currency="USD", transactions=[
        Transaction(date=day, description=text, amount=amount, direction="credit") for day, text, amount in rows
    ])
    records = classify_statement_transactions(statement)
    expected = {"asset_sale_proceeds": {"count": 2, "total": 16850.0}, "zelle_excluded": {"count": 1, "total": 300.0}}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.non_revenue_by_reason == expected
    assert (metrics.non_revenue_total, metrics.true_revenue_total) == (17150.0, 500.0)
    assert metrics.revenue_reconciles
    rebuilt = rebuild_serialized_revenue_views({
        "statement": {"currency": "USD", "transactions": [
            {**transaction.model_dump(), "classification": asdict(record)}
            for transaction, record in zip(statement.transactions, records)
        ]},
        "metrics": {}, "detection": {},
    })["metrics"]
    assert rebuilt["non_revenue_by_reason"] == expected
    assert rebuilt["non_revenue_total"] == 17150.0 and rebuilt["revenue_reconciles"]


def test_a_record_whose_tier_disagrees_with_its_state_is_refused():
    statement = _statement()
    records = classify_statement_transactions(statement)
    records[1] = replace(records[1], revenue_tier="verified")
    with pytest.raises(ValueError, match="agree with its tier"):
        compute_metrics(statement, classifications=records)


def test_the_metrics_file_a_credit_by_its_flag_and_the_rebuild_by_its_state():
    # The counted check deposit carries the verified flag while its state stays unverified_deposit.
    statement = _statement()
    records = classify_statement_transactions(statement)
    records[1] = replace(records[1], contributes_to_verified_revenue=True, contributes_to_unverified_deposit=False)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.verified_revenue_total, metrics.unverified_deposit_total, metrics.counted_flagged_total) == (
        1000.0, 900.0, 300.0)
    assert (metrics.true_revenue_total, metrics.revenue_classified_total, metrics.revenue_reconciles) == (
        1300.0, 2300.0, False)
    rebuilt = _rebuilt(statement, records)["metrics"]
    assert (rebuilt["verified_revenue_total"], rebuilt["unverified_deposit_total"], rebuilt["true_revenue_total"]) == (
        700.0, 1200.0, 1000.0)
    assert rebuilt["revenue_reconciles"]


def test_the_metrics_file_a_credit_with_no_state_and_an_unknown_tier_in_no_tier():
    statement = _statement()
    records = classify_statement_transactions(statement)
    records[1] = replace(records[1], revenue_classification=None, revenue_tier="unknown")
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.unverified_deposit_total, metrics.counted_flagged_total, metrics.counted_flagged_by_reason) == (
        1200.0, 0.0, {})
    assert (metrics.true_revenue_total, metrics.revenue_classified_total, metrics.revenue_reconciles) == (
        700.0, 1700.0, False)


def test_true_revenue_evidence_reads_every_record_and_state_evidence_only_posted_credits():
    # The verified credit is unposted but keeps its verified and True flags.
    statement = _statement()
    records = classify_statement_transactions(statement)
    records[0] = replace(records[0], is_posted=False)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.verified_revenue_total, metrics.true_revenue_total, metrics.verified_revenue_evidence) == (
        0.0, 300.0, [])
    assert [record.source_location for record in metrics.true_revenue_evidence] == ["transaction:1", "transaction:2"]
    rebuilt = _rebuilt(statement, records)
    assert (rebuilt["metrics"]["true_revenue_total"], rebuilt["metrics"]["verified_revenue_evidence"]) == (300.0, [])
    assert [record["source_location"] for record in rebuilt["detection"]["true_revenue_evidence"]] == [
        "transaction:1", "transaction:2"]


def test_the_revenue_figures_add_the_credits_one_by_one_in_ledger_order():
    # Builtin sum() compensates float error and gives 100000000000002.02 for these three amounts.
    rows = [("2054-03-02", "MOBILE DEPOSIT", 1e14), ("2054-03-03", "MOBILE DEPOSIT", 1.01),
            ("2054-03-04", "MOBILE DEPOSIT", 1.01)]
    statement = _statement(rows)
    metrics = compute_metrics(statement, classifications=classify_statement_transactions(statement))
    rebuilt = _payload(rows)["metrics"]
    assert (metrics.total_posted_credits, metrics.unverified_deposit_total, metrics.counted_flagged_total,
            metrics.counted_flagged_by_reason["check_deposit"]["total"]) == (100000000000002.03,) * 4
    assert (rebuilt["total_posted_credits"], rebuilt["unverified_deposit_total"], rebuilt["counted_flagged_total"],
            rebuilt["counted_flagged_by_reason"]["check_deposit"]["total"]) == (100000000000002.03,) * 4


@pytest.mark.parametrize(("held", "posted", "gated"), [
    (99.99, 1000.0, False),      # just under ten percent, in cents
    (100.0, 1000.0, True),       # exactly ten percent
    (0.0, 0.0, False),           # nothing posted, nothing held
])
def test_the_gate_compares_the_held_share_in_integer_cents(held, posted, gated):
    # Audit B11 (I31): the identity term is named for what it is, the four tiers summing to the posted credits.
    assert REVENUE_REVIEW_HELD_SHARE == 10
    assert revenue_review_gate(direction_conflict=False, held_total=held, posted_total=posted,
                               tiers_sum_to_posted=True) is gated
    assert revenue_review_gate(direction_conflict=True, held_total=0.0, posted_total=posted, tiers_sum_to_posted=True)
    assert revenue_review_gate(direction_conflict=False, held_total=0.0, posted_total=posted,
                               tiers_sum_to_posted=False)


@pytest.mark.parametrize(("held", "true", "posted", "gated"), [
    # The brief's case: $9,000 held beside $31,000 True and $60,000 of financing is 9% of the posted credits but 22.5%
    # of True plus held.
    (9000.0, 31000.0, 100000.0, True),
    # True $0 with four cents held never gates: the share is 100%, the floor is not reached.
    (0.04, 0.0, 1000.04, False),
    # At the floor, exactly ten percent of True plus held, in cents, gates; a cent under either does not.
    (500.0, 4500.0, 50000.0, True),
    (499.99, 4499.91, 50000.0, False),
    (500.0, 4500.01, 50000.0, False),
    # The posted-credit share still gates on its own (no floor there).
    (100.0, 900.0, 1000.0, True),
])
def test_the_gate_also_reads_held_against_true_plus_held_above_a_floor(held, true, posted, gated):
    """Audit B11 (I50, T7 amended): an MCA advance is sized on True, so held credits of 10% or more of True plus held
    gate too, when they are $500 or more."""
    from analysis.revenue import REVENUE_REVIEW_HELD_FLOOR

    assert REVENUE_REVIEW_HELD_FLOOR == 500
    assert revenue_review_gate(direction_conflict=False, held_total=held, posted_total=posted,
                               tiers_sum_to_posted=True, true_total=true) is gated


def test_a_statement_heavy_with_financing_is_gated_on_its_true_revenue():
    """The analysis pass and the rebuild apply the amended gate: a fabricated statement whose $60,000 financing credit
    dilutes the posted base still needs review when its held credit is a fifth of True plus held."""
    rows = [
        ("2031-03-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 31000.0),
        ("2031-03-03", "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 9000.0),
        ("2031-03-04", "ONDECK CAPITAL DES:LOAN PROCEEDS ID:1", 60000.0),
    ]
    statement = _statement(rows)
    metrics = compute_metrics(statement, classifications=classify_statement_transactions(statement))
    assert metrics.excluded_pending_review_total == 9000.0
    assert metrics.true_revenue_total == 31000.0
    assert metrics.non_revenue_total == 60000.0
    assert metrics.revenue_review_required is True
    assert metrics.revenue_tiers_sum_to_posted is True and metrics.revenue_reconciles is True
    rebuilt = _payload(rows)["metrics"]
    assert rebuilt["revenue_review_required"] is True
    assert rebuilt["revenue_tiers_sum_to_posted"] is True and rebuilt["revenue_reconciles"] is True
    # Below the floor the same shares do not gate: $400 held beside $1,600 True and $60,000 of financing.
    small = _payload([("2031-03-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 1600.0),
                      ("2031-03-03", "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 400.0),
                      ("2031-03-04", "ONDECK CAPITAL DES:LOAN PROCEEDS ID:1", 60000.0)])["metrics"]
    assert small["excluded_pending_review_total"] == 400.0 and small["revenue_review_required"] is False


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
    assert metrics["non_revenue_by_reason"] is None  # R2-OW03: a tier figure (TIER_METRIC_KEYS)
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


def test_true_revenue_is_the_default_withholding_denominator_and_legacy_stays_selectable():
    """Owner ruling 2026-10-02 (the underwriter's Q7, audit I34), R2-OW14: True revenue is the default withholding
    basis (U1); the legacy and verified bases stay selectable, and the legacy figure is published on every statement."""
    statement = _statement()
    records = classify_statement_transactions(statement)
    default = compute_metrics(statement, classifications=records)
    assert (default.withholding_denominator_mode, default.withholding_denominator_label) == (
        "true_revenue", "True revenue")
    assert default.eligible_deposits == default.withholding_denominator == default.true_revenue_total == 1000.0
    assert default.eligible_deposit_definition == "true revenue: verified plus counted credits"
    assert default.legacy_eligible_deposits == 2000.0
    legacy = compute_metrics(statement, classifications=records, withholding_denominator_mode="legacy_eligible_deposits")
    assert (legacy.eligible_deposits, legacy.withholding_denominator_label) == (2000.0, "Legacy eligible deposits")
    assert legacy.eligible_deposit_definition == "effective total deposits minus recognized lender funding credits"
    verified = compute_metrics(statement, classifications=records, withholding_denominator_mode="verified_revenue")
    assert (verified.eligible_deposits, verified.withholding_denominator_label) == (700.0, "Verified revenue")


def test_the_default_withholding_mode_is_one_constant():
    """R2-OW14 (Q7): the settings, compute_metrics' keyword and the Metrics dataclass all take the one constant."""
    import inspect

    from analysis.config import Settings
    from analysis.metrics import Metrics
    from analysis.revenue import DEFAULT_WITHHOLDING_DENOMINATOR_MODE

    assert DEFAULT_WITHHOLDING_DENOMINATOR_MODE == "true_revenue"
    assert Metrics().withholding_denominator_mode == DEFAULT_WITHHOLDING_DENOMINATOR_MODE
    assert Metrics().withholding_denominator_label == "True revenue"
    assert inspect.signature(compute_metrics).parameters["withholding_denominator_mode"].default == (
        DEFAULT_WITHHOLDING_DENOMINATOR_MODE)
    # (The inert model fields this call used to fill left `Settings` in slice S4 of the model-code removal.)
    assert Settings().withholding_denominator_mode == DEFAULT_WITHHOLDING_DENOMINATOR_MODE


def test_a_stored_mode_missing_reads_as_legacy_and_an_invalid_one_reads_as_the_default_given():
    """R2-OW14 (Q7, U3): a stored payload whose metrics carry no mode keeps its legacy basis; the settings read a
    missing or invalid environment value as the new default."""
    from analysis.revenue import normalize_withholding_denominator_mode as normalize

    assert normalize(None) == normalize("") == normalize("invalid") == "legacy_eligible_deposits"
    assert normalize("confirmed_true_revenue") == "verified_revenue"
    assert normalize(None, default="true_revenue") == normalize("invalid", default="true_revenue") == "true_revenue"
    assert normalize("legacy_eligible_deposits", default="true_revenue") == "legacy_eligible_deposits"
    payload = _payload()
    payload["metrics"].pop("withholding_denominator_mode", None)
    payload["metrics"]["eligible_deposits"] = payload["metrics"]["withholding_denominator"] = 2000.0
    rebuilt = rebuild_serialized_revenue_views(payload)
    assert rebuilt["metrics"]["withholding_denominator_mode"] == "legacy_eligible_deposits"
    assert rebuilt["metrics"]["eligible_deposits"] == 2000.0


#: U4's rows: a customer's payment, an own-account transfer (legacy only) and a registered funder's debit.
U4_ROWS = [
    ("2054-03-02", "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000001 CCD", 10000.0),
    ("2054-03-03", "INTERNAL TRANSFER FROM SAVINGS", 5000.0),
    ("2054-03-04", "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD", -850.0),
]


def test_the_default_rate_divides_by_true_revenue_and_the_legacy_mode_by_eligible_deposits():
    """R2-OW14 (Q7, U4): $850 to a funder over $10,000 True (8.50%) by default; over $15,000 legacy (5.67%)."""
    statement = _statement(U4_ROWS)
    records = classify_statement_transactions(statement)
    default = compute_metrics(statement, classifications=records)
    assert (default.withholding_denominator, default.withholding_numerator) == (10000.0, 850.0)
    assert round(default.withholding_rate, 2) == 8.50
    assert default.potential_withholding_denominator == 10000.0
    legacy = compute_metrics(statement, classifications=records, withholding_denominator_mode="legacy_eligible_deposits")
    assert (legacy.withholding_denominator, legacy.withholding_numerator) == (15000.0, 850.0)
    assert round(legacy.withholding_rate, 2) == 5.67
    # The numerator, the legacy figure and every revenue reading are the same under either basis.
    assert legacy.legacy_eligible_deposits == default.legacy_eligible_deposits == 15000.0
    assert legacy.true_revenue_total == default.true_revenue_total


def test_a_statement_whose_every_credit_is_held_has_no_default_rate_and_needs_review():
    """R2-OW14 (Q7, U5): True $0.00: no rate, the withholding review flag, and the note names True revenue."""
    statement = _statement([ROWS[2], U4_ROWS[2]])
    records = classify_statement_transactions(statement)
    assert [record.revenue_tier for record in records if record.amount > 0] == ["excluded_pending_review"]
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.true_revenue_total == 0.0
    assert metrics.withholding_rate is None and metrics.withholding_review_required
    assert "withholding rate is unavailable because True revenue is zero or missing" in metrics.notes
    legacy = compute_metrics(statement, classifications=records, withholding_denominator_mode="legacy_eligible_deposits")
    assert legacy.withholding_rate == pytest.approx(850.0 / 900.0 * 100) and not legacy.withholding_review_required


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
    # Owner ruling 2026-10-02 (the underwriter's Q7), R2-OW14: the working lines name the basis, True revenue by default.
    assert "Withholding working   : $0.00 / $1,000.00 True revenue" in lines
    assert "Potential working     : $0.00 / $1,000.00 True revenue" in lines


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
