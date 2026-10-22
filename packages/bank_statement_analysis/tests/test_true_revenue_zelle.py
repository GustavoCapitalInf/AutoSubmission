"""The owner's ruling of 2026-10-02 (the underwriter's Q3; true revenue spec §5.3, §8.4, §8.10 step 26, §19.1; R2-OW02):
every posted Zelle deposit is non_revenue (`zelle_excluded`), whoever sent it, a lender or a processor paying through
Zelle included. Pass 7 excludes it after every tier and before the $1 floor, keeping the rules' own reading on the
record (`zelle_prior_reading`); a row a non-revenue rule already decided keeps that rule and no reason, and a direction
conflict keeps its hold. Only the revenue fields and the contribution flags move: the legacy classification, the
entity, the flag group, the lender-credit exclusion and the debits stay. Other person-to-person rails are unchanged.
R2-OW03 (spec §9.1, §10.7): the metrics and the served payload publish the excluded total and count by reason
(`non_revenue_by_reason`), and the underwriter may confirm a Zelle deposit (confirm and reset only); every other
non-revenue row keeps the review refusal. Fabricated rows only, in the banks' printed formats (CONTOSO, FABRIKAM,
NORTHWIND, SAMPLE; 2054)."""
from __future__ import annotations

import copy
from dataclasses import asdict, fields

import pytest

from analysis import true_revenue
from analysis.metrics import compute_metrics
from analysis.revenue import (
    NON_REVENUE_REASONS,
    REVENUE_TIER_REASONS,
    REVIEWABLE_NON_REVENUE_REASONS,
    apply_serialized_revenue_review,
    non_revenue_reason,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
)
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import TransactionClassification, classify_statement_transactions, revenue_text
from analysis.description_text import normalize_transaction_description

HOLDER = "CONTOSO BAKERY LLC"
HELD = "excluded_pending_review"
COUNTED = "counted_flagged"
EXCLUDED = ("non_revenue", "zelle_excluded")
#: The record fields the Zelle policy may change: the revenue fields and the revenue contribution flags.
REVENUE_FIELDS = frozenset(
    field.name for field in fields(TransactionClassification)
    if field.name.startswith("revenue_") or field.name in {
        "contributes_to_verified_revenue", "contributes_to_unverified_deposit", "contributes_to_non_revenue",
        "contributes_to_counted_flagged", "contributes_to_excluded_pending_review", "contributes_to_true_revenue",
        "contributes_to_potential_revenue",
    }
)


def _transactions(rows, days=None):
    return [
        Transaction(date=f"2054-03-{(days[index] if days else index + 2):02d}", description=text, amount=amount,
                    direction=rest[0] if rest else ("credit" if amount > 0 else "debit"))
        for index, (text, amount, *rest) in enumerate(rows)
    ]


def _run(rows, bank, *, holder=HOLDER, days=None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank,
                                                     transactions=_transactions(rows, days)))


def _both(monkeypatch, rows, bank, **kwargs):
    """The rows read with the Zelle policy, then without it (zelle_deposit reading no row)."""
    on = _run(rows, bank, **kwargs)
    monkeypatch.setattr(true_revenue, "zelle_deposit", lambda text: False)
    off = _run(rows, bank, **kwargs)
    monkeypatch.undo()
    return on, off


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


def _others(record):
    return {name: value for name, value in asdict(record).items() if name not in REVENUE_FIELDS}


# Q3 MOVES: (bank, rows, days, the rules' reading of each credit). Every credit ends non_revenue / zelle_excluded.
MOVES = [
    ("Chase", [("ZELLE PAYMENT FROM PAT SAMPLE 12345678901", 1234.56)], None, [(COUNTED, "p2p")]),
    ("Bank of America", [("ZELLE PAYMENT FROM FABRIKAM LANDSCAPING LLC CONF# A1B2C3D4E", 2000.0),
                         ("ZELLE PAYMENT FROM FABRIKAM LANDSCAPING LLC CONF# B1B2C3D4E", 2000.0)], None,
     [(HELD, "p2p_round_repeat")] * 2),
    # PNC prints the rail as ZEL, which the classifier's rail does not read. Audit round 3, R3-12 (R3-B12): pass 7 reads
    # it as its ZELLE twin (true_revenue.pass_text), a person-to-person credit (it was named_payer_unlabelled).
    ("PNC Bank", [("Zel From Pat Sample WFCT0ABCDE12", 500.0)], None, [(COUNTED, "p2p")]),
    ("Wells Fargo", [("ZELLE FROM NORTHWIND SUPPLY LLC ON 03/02 REF # BAC0A1B2C3D4", 750.0)], None, [(COUNTED, "p2p")]),
    ("U.S. Bank", [("ZELLE INSTANT PMT FROM PAT SAMPLE", 300.0)], None, [(COUNTED, "p2p")]),
    ("Truist", [("ZELLE BUSINESS PAYMENT FROM SAMPLE CATERING PAYMENT ID BAC1X2Y3Z", 410.25)], None, [(COUNTED, "p2p")]),
    ("BMO", [("TRANSFER IN ZELLE FROM PAT SAMPLE", 220.0)], None, [(COUNTED, "p2p")]),
    ("TD Bank", [("TD ZELLE RECEIVED 1A2B3C ZELLE PAT SAMPLE", 95.0)], None, [(COUNTED, "p2p")]),
    ("American Express", [("ZELLE PAYMENT FROM A1B2C3 PAT SAMPLE WELLS FARGO ID 123", 180.0)], None,
     [(COUNTED, "p2p")]),
    ("Citizens Bank", [("NOW NETWORK CREDIT ZELLE CREDIT NOW NET ID 1A2B ZELLE PAT SAMPLE 5678", 640.0)], None,
     [(COUNTED, "p2p")]),
    ("Navy Federal Credit Union", [("ZELLE CR NORTHWIND SUPPLY LLC", 1027.11)], None, [(COUNTED, "p2p")]),
    ("Regions Bank", [("ZELLE CREDIT FROM PAT SAMPLE REF A1B2", 880.0)], None, [(COUNTED, "p2p")]),
    ("Woodforest National Bank", [("ZELLE MONEY RECEIVED FROM PAT SAMPLE", 3390.0)], None, [(COUNTED, "p2p")]),
    # A reference or a date glued on either side of the rail.
    ("Chase", [("ZELLE1234567 PAYMENT FROM PAT SAMPLE", 615.0)], None, [(COUNTED, "p2p")]),
    ("Chase", [("0302ZELLE PAYMENT FROM PAT SAMPLE", 615.0)], None, [(COUNTED, "p2p")]),
    # Every hold is excluded too: the policy already answered whether the credit counts.
    ("Bank of America", [("ZELLE PAYMENT FROM CONTOSO BAKERY LLC CONF 99", 2500.0)], None, [(HELD, "holder_name")]),
    ("Bank of America", [("ZELLE PAYMENT FROM FABRIKAM FUNDING LLC CONF 1", 5000.0)], None,
     [(HELD, "financing_named_payer")]),
    ("Bank of America", [("ZELLE PAYMENT FROM EXPRESS NORTHWIND CONF 1", 9000.0),
                         *[("EXPRESS NORTHWIND DES:DEBIT ID:2", -300.0)] * 4], [2, 9, 16, 23, 30],
     [(HELD, "payer_debited_as_lender")]),
    ("Wells Fargo", [("ZELLE FROM PAT SAMPLE ON 03/02 REF # BAC0A1B2C3D4", 3200.0),
                     ("ZELLE TO PAT SAMPLE ON 03/05 REF # BAC0A1B2C3D5", -800.0)], None,
     [(HELD, "payer_also_debited")]),
    # The $1 floor's hold (non_sale_purpose): the floor runs after the policy and skips the excluded row.
    ("Bank of America", [("ZELLE PAYMENT FROM PAT SAMPLE CONF 1", 0.50)], None, [(HELD, "non_sale_purpose")]),
    # Purpose words do not rescue a Zelle row.
    ("Bank of America", [("ZELLE PAYMENT FROM PAT SAMPLE FOR INVOICE 1001 CONF 1", 1450.0)], None, [(COUNTED, "p2p")]),
]


@pytest.mark.parametrize(("bank", "rows", "days", "prior"), MOVES)
def test_q3_every_zelle_deposit_is_excluded_with_the_rules_reading_kept(monkeypatch, bank, rows, days, prior):
    on, off = _both(monkeypatch, rows, bank, days=days)
    credits = [(new, old) for new, old in zip(on, off) if new.amount > 0]
    assert [_tier(old) for _new, old in credits] == prior
    for new, old in credits:
        assert _tier(new) == EXCLUDED
        assert true_revenue.zelle_prior_reading(new) == _tier(old)
        assert (new.revenue_classification, new.revenue_initial_classification, new.revenue_initial_tier) == (
            "non_revenue", "non_revenue", "non_revenue")
        assert (new.revenue_match_method, new.revenue_matched_rule) == ("zelle_deposit_excluded",) * 2
        assert new.revenue_review_status == "not_required" and new.revenue_review_required is False
        assert not new.contributes_to_true_revenue and new.contributes_to_non_revenue
        assert not new.contributes_to_counted_flagged and not new.contributes_to_excluded_pending_review
        assert new.revenue_reason.startswith("A Zelle deposit, excluded from true revenue by the owner's policy")
        label = REVENUE_TIER_REASONS[old.revenue_tier_reason][1]
        assert new.revenue_reason.endswith(f"the rules read it as: {label}.")
        # Only the revenue fields and the contribution flags move.
        assert _others(new) == _others(old)
    # The debits are unchanged, whole.
    assert [new for new in on if new.amount <= 0] == [old for old in off if old.amount <= 0]


@pytest.mark.parametrize(("bank", "rows", "days", "prior"), MOVES)
def test_q3_amended_the_counted_reading_of_every_move_is_its_prior(bank, rows, days, prior):
    """The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17, I-Rules): the counted (Yes) reading of each
    Zelle deposit is the rules' own reading, the zelle_prior the stored reading keeps; nothing else in the statement
    moves (none of these rows prints a sale, a draw or a premium trust title)."""
    statement = Statement(account_name=HOLDER, bank=bank, transactions=_transactions(rows, days))
    stored = classify_statement_transactions(statement)
    counted = classify_statement_transactions(statement, zelle_true_revenue=True)
    credits = [(old, new) for old, new in zip(stored, counted) if old.amount > 0]
    assert [true_revenue.zelle_prior_reading(old) for old, _new in credits] == prior
    assert [_tier(new) for _old, new in credits] == prior
    assert [old for old in stored if old.amount <= 0] == [new for new in counted if new.amount <= 0]


def test_q3_the_classification_stays_the_legacy_reading():
    """Transfer for a rail the classifier reads; other for PNC's ZEL and a glued rail."""
    assert [_run([(text, 500.0)], bank)[0].classification for text, bank in (
        ("ZELLE PAYMENT FROM PAT SAMPLE CONF 1", "Bank of America"), ("Zel From Pat Sample WFCT0ABCDE12", "PNC Bank"),
        ("ZELLE1234567 PAYMENT FROM PAT SAMPLE", "Chase"),
    )] == ["transfer", "other", "other"]


def test_q3_a_financing_held_zelle_credit_keeps_its_reading_in_the_reason():
    [record] = _run([("ZELLE PAYMENT FROM FABRIKAM FUNDING LLC CONF 1", 5000.0)], "Bank of America")
    assert _tier(record) == EXCLUDED
    assert "Payer or entry suggests financing" in record.revenue_reason
    assert record.contributes_to_lender_credit_exclusion is False


def test_q3_a_lender_debited_payer_s_debits_keep_their_lender_reading(monkeypatch):
    rows = [("ZELLE PAYMENT FROM EXPRESS NORTHWIND CONF 1", 9000.0), *[("EXPRESS NORTHWIND DES:DEBIT ID:2", -300.0)] * 4]
    on, off = _both(monkeypatch, rows, "Bank of America", days=[2, 9, 16, 23, 30])
    assert [record.classification for record in on[1:]] == ["potential_lender"] * 4
    assert on[1:] == off[1:]


# Q3 KEPT: a row a non-revenue rule decided keeps that rule and no reason; a direction conflict keeps its hold.
@pytest.mark.parametrize(("bank", "row", "reading"), [
    ("Bank of America", ("ZELLE PAYMENT FROM PAT SAMPLE FOR REFUND CONF 1", 799.5),
     ("non_revenue", None, "reversal_cancellation_exclusion")),
    ("TD Bank", ("TD ZELLE SENT REFUND 1A2B REFUND ZELLE", 150.0),
     ("non_revenue", None, "reversal_cancellation_exclusion")),
    # Printed as a debit with a positive amount.
    ("Bank of America", ("ZELLE PAYMENT TO PAT SAMPLE CONF 1", 400.0, "debit"),
     (HELD, "direction_conflict", "direction_conflict")),
])
def test_q3_a_non_revenue_rule_and_a_direction_conflict_keep_their_reading(bank, row, reading):
    [record] = _run([row], bank)
    assert (record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method) == reading
    assert true_revenue.zelle_prior_reading(record) is None


@pytest.mark.parametrize("text", [
    # A listed funder paying through Zelle: D1's financing proceeds, the lender-credit exclusion kept.
    "ZELLE PAYMENT FROM FORWARD FINANCING CONF 1",
    "ZELLE FROM ONDECK ON 03/02 REF # BAC0A1B2C3D4",
])
def test_q3_a_listed_funder_s_zelle_credit_stays_financing_proceeds(text):
    [record] = _run([(text, 5000.0)], "Bank of America")
    assert (record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method) == (
        "non_revenue", None, "financing_proceeds_credit")
    assert record.contributes_to_lender_credit_exclusion is True
    assert true_revenue.zelle_prior_reading(record) is None


# Q3 CONTROLS: a name holding the rail's letters, and the other person-to-person rails.
@pytest.mark.parametrize("text", [
    "HAZEL SUPPLY LLC DES:PAYMENT ID:1", "NORTHWIND ROSZELL LLC DES:PAYMENT ID:1",
    "MAZZELLA FABRIKAM INC DES:PAYMENT ID:1", "ZELLER CONTOSO INC DES:PAYMENT ID:1",
])
def test_q3_a_payer_whose_name_holds_the_letters_is_no_zelle_deposit(text):
    [record] = _run([(text, 800.0)], "Bank of America")
    assert (record.revenue_tier, record.revenue_match_method) == ("verified", "named_payer_company_form")
    assert not true_revenue.zelle_deposit(revenue_text(normalize_transaction_description(text)))


@pytest.mark.parametrize("text", [
    "VENMO FROM PAT SAMPLE", "CASH APP*PAT SAMPLE", "INTERAC E-TRANSFER RECEIVED PAT SAMPLE",
])
def test_q3_the_other_person_to_person_rails_stay_counted(text):
    [record] = _run([(text, 1234.0)], "Royal Bank of Canada")
    assert _tier(record) == (COUNTED, "p2p")


def test_q3_a_sender_s_zelle_round_sum_still_completes_its_named_group():
    zelle, venmo = _run([("ZELLE PAYMENT FROM PAT SAMPLE CONF 1", 500.0), ("VENMO FROM PAT SAMPLE", 500.0)], "Chase")
    assert _tier(zelle) == EXCLUDED
    assert true_revenue.zelle_prior_reading(zelle) == (HELD, "p2p_round_repeat")
    assert _tier(venmo) == (HELD, "p2p_round_repeat")


@pytest.mark.parametrize(("text", "zelle"), [
    ("ZELLE PAYMENT FROM PAT SAMPLE CONF 1", True),
    ("ZEL FROM PAT SAMPLE WFCT0ABCDE12", True),
    ("ZEL TO PAT SAMPLE 1234", True),
    ("ZELLE1234567 PAYMENT FROM PAT SAMPLE", True),
    ("0302ZELLE PAYMENT FROM PAT SAMPLE", True),
    ("NAVY ZELLE CR NORTHWIND SUPPLY LLC", True),
    ("HAZEL SUPPLY LLC", False),
    ("NORTHWIND ROSZELL LLC", False),
    ("MAZZELLA FABRIKAM INC", False),
    ("ZELLER CONTOSO INC", False),
    ("EZELL SAMPLE LLC", False),
    ("ZELDA SAMPLE", False),
    # The rail read only before the receiver fields.
    ("NORTHWIND SUPPLY DES:PAYMENT ID:1 INDN:ZELLE SAMPLE CO ID:1234567890 CCD", False),
    # Audit round 3, R3-56 (R3-B12): a wire is never a Zelle deposit, whatever its memo prints.
    ("WIRE TYPE:WIRE IN DATE: 540302 TIME:1200 ET TRN:2054030200001 ORIG:NORTHWIND TRADING INC ID:0001 "
     "PMT DET:INVOICE 1234 PAID BY WIRE INSTEAD OF ZELLE", False),
    ("DEPOSIT WIRE IN 000123 ORG NORTHWIND TRADING INC OBI INVOICE 1234 NOT VIA ZELLE", False),
    # The ACH entry-description form is kept (an entry its sender wrote as ZELLE).
    ("NORTHWIND TRADING INC DES:ZELLE PMT ID:0001 INDN:CONTOSO BAKERY LLC", True),
])
def test_q3_the_zelle_reader(text, zelle):
    assert true_revenue.zelle_deposit(revenue_text(normalize_transaction_description(text))) is zelle


def test_q3_the_consumer_rail_is_unchanged():
    """The classifier's rail, shared with the legacy classes and the debits, does not read PNC's ZEL."""
    from analysis import transaction_classifier

    assert "ZEL " not in transaction_classifier._CONSUMER_P2P_RAIL.pattern
    assert transaction_classifier._CONSUMER_P2P_RAIL.search("ZEL FROM PAT SAMPLE") is None


def test_q3_an_unregistered_reason_code_names_itself():
    """A reason another batch adds without a table row never raises: the code is its own label."""
    [record] = _run([("MOBILE DEPOSIT", 300.0)], "Chase")
    excluded = true_revenue._zelle_excluded(
        TransactionClassification(**{**asdict(record), "revenue_tier_reason": "fabricated_new_reason"})
    )
    assert _tier(excluded) == EXCLUDED
    assert excluded.revenue_reason.endswith("the rules read it as: fabricated_new_reason.")
    assert true_revenue.zelle_prior_reading(excluded) == (COUNTED, "fabricated_new_reason")


def test_q3_a_verified_row_reads_as_verified_revenue():
    [record] = _run([("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0)], "Bank of America")
    assert _tier(record) == ("verified", None)
    excluded = true_revenue._zelle_excluded(record)
    assert _tier(excluded) == EXCLUDED
    assert excluded.revenue_reason.endswith("the rules read it as: Verified revenue.")
    assert true_revenue.zelle_prior_reading(excluded) == ("verified", None)


def test_q3_the_prior_reading_of_any_other_row_is_none():
    assert [true_revenue.zelle_prior_reading(record) for record in _run(
        [("MOBILE DEPOSIT", 300.0), ("VENMO FROM PAT SAMPLE", 230.0)], "Chase")] == [None, None]


def test_q3_the_reason_table_ends_with_its_non_revenue_codes():
    """The non_revenue codes end the table (R2-OW02's Zelle code, then R2-OW03's display code for Q12's rows, then
    R2-OW06's asset_sale_proceeds for Q11's non-dealer asset sales), and NON_REVENUE_REASONS is exactly them; only the
    Zelle code may be reviewed (owner ruling 2026-10-02, R2-OW03; Q11's has no review path, its card's open point 4)."""
    non_revenue = [code for code, (tier, _label) in REVENUE_TIER_REASONS.items() if tier == "non_revenue"]
    assert non_revenue == ["zelle_excluded", "government_no_purpose", "asset_sale_proceeds"]
    assert list(REVENUE_TIER_REASONS)[-len(non_revenue):] == non_revenue
    assert REVENUE_TIER_REASONS["zelle_excluded"] == ("non_revenue", "Zelle deposit (excluded by policy)")
    assert NON_REVENUE_REASONS == frozenset(non_revenue)
    assert [non_revenue_reason(code) for code in ("zelle_excluded", "government_no_purpose", "check_deposit",
                                                  "p2p_round_repeat", None, "")] == [
        True, True, False, False, False, False]
    assert REVIEWABLE_NON_REVENUE_REASONS == frozenset({"zelle_excluded"}) <= NON_REVENUE_REASONS
    assert true_revenue.ZELLE_EXCLUDED == "zelle_excluded"
    assert true_revenue.ZELLE_POLICY_METHOD == "zelle_deposit_excluded"


# Owner ruling 2026-10-02, R2-OW03 (the underwriter's Q3; spec §9.1, §9.2, §10.1, §10.7): the figures state the
# exclusion (`non_revenue_by_reason`, beside `non_revenue_total`), and the underwriter may confirm a single Zelle deposit
# back into revenue ("I can review"). Every other non-revenue row keeps the review refusal.
ROWS = [
    ("ZELLE PAYMENT FROM PAT SAMPLE CONF 1", 1000.0),
    ("ZELLE PAYMENT FROM SAMPLE CATERING CONF 2", 400.0),
    ("ZELLE PAYMENT FROM FABRIKAM SUPPLY CONF 3", 100.0),
    ("MOBILE DEPOSIT", 300.0),
]
ZELLE_BY_REASON = {"zelle_excluded": {"count": 3, "total": 1500.0}}


def _statement(rows=ROWS, bank="Bank of America"):
    return Statement(account_name=HOLDER, bank=bank, currency="USD", transactions=_transactions(rows))


def test_q3_the_metrics_read_the_excluded_rows_as_non_revenue():
    statement = _statement()
    metrics = compute_metrics(statement, classifications=classify_statement_transactions(statement))
    assert (metrics.non_revenue_total, metrics.non_revenue_count) == (1500.0, 3)
    assert (metrics.counted_flagged_total, metrics.excluded_pending_review_total) == (300.0, 0.0)
    assert metrics.true_revenue_total == 300.0
    # The breakdown: its own dict, never a slot of the counted or held maps; the four tiers still sum to posted.
    assert metrics.non_revenue_by_reason == ZELLE_BY_REASON
    assert metrics.counted_flagged_by_reason == {"check_deposit": {"count": 1, "total": 300.0}}
    assert metrics.excluded_pending_review_by_reason == {}
    assert metrics.revenue_tiers_sum_to_posted is True
    assert metrics.revenue_classified_total == metrics.total_posted_credits == 1800.0


def _payload(rows=ROWS, bank="Bank of America"):
    statement = _statement(rows, bank)
    records = classify_statement_transactions(statement)
    return rebuild_serialized_revenue_views({
        "statement": {"currency": "USD", "transactions": [
            {**transaction.model_dump(), "classification": asdict(record)}
            for transaction, record in zip(statement.transactions, records)
        ]},
        "metrics": {}, "detection": {},
    })


def _row(payload, text):
    return next(transaction["classification"] for transaction in payload["statement"]["transactions"]
                if transaction["description"] == text)


def _figures(payload):
    metrics = payload["metrics"]
    return {key: metrics[key] for key in ("true_revenue_total", "verified_revenue_total", "counted_flagged_total",
                                          "excluded_pending_review_total", "non_revenue_total", "non_revenue_count",
                                          "non_revenue_by_reason", "revenue_review_required")}


def test_q3_the_served_payload_rebuilds_the_breakdown():
    payload = _payload()
    metrics = payload["metrics"]
    assert (metrics["non_revenue_total"], metrics["non_revenue_count"]) == (1500.0, 3)
    assert metrics["true_revenue_total"] == 300.0 and metrics["revenue_tiers_sum_to_posted"] is True
    assert metrics["non_revenue_by_reason"] == ZELLE_BY_REASON
    assert "zelle_excluded" not in metrics["counted_flagged_by_reason"]
    assert "zelle_excluded" not in metrics["excluded_pending_review_by_reason"]


def test_q3_a_reviewer_rejected_counted_deposit_is_not_in_the_breakdown():
    """A rejected counted row keeps its counted reason (check_deposit), which is no non-revenue code: it joins the
    non-revenue total, never the breakdown."""
    payload = _payload()
    apply_serialized_revenue_review(payload, source_location=_row(payload, "MOBILE DEPOSIT")["source_location"],
                                    decision="reject")
    rejected = _row(payload, "MOBILE DEPOSIT")
    assert (rejected["revenue_tier"], rejected["revenue_tier_reason"]) == ("non_revenue", "check_deposit")
    assert (payload["metrics"]["non_revenue_total"], payload["metrics"]["non_revenue_count"]) == (1800.0, 4)
    assert payload["metrics"]["non_revenue_by_reason"] == ZELLE_BY_REASON


def test_q3_a_payload_analysed_before_5_6_has_no_breakdown():
    """§12: a payload with no tier has no breakdown, in its rebuild and in its served copy (TIER_METRIC_KEYS)."""
    from analysis.revenue_view import apply_revenue_view

    old = _payload()
    for transaction in old["statement"]["transactions"]:
        for key in ("revenue_tier", "revenue_initial_tier", "revenue_tier_reason"):
            transaction["classification"].pop(key, None)
    served = apply_revenue_view(copy.deepcopy(old))  # the stored breakdown, served from an untiered ledger
    assert served["metrics"]["non_revenue_by_reason"] is None
    assert rebuild_serialized_revenue_views(old)["metrics"]["non_revenue_by_reason"] is None


def test_q3_the_underwriter_may_confirm_a_zelle_deposit_and_reset_it():
    payload = _payload()
    before = _figures(payload)
    location = _row(payload, "ZELLE PAYMENT FROM PAT SAMPLE CONF 1")["source_location"]
    apply_serialized_revenue_review(payload, source_location=location, decision="confirm")
    record = _row(payload, "ZELLE PAYMENT FROM PAT SAMPLE CONF 1")
    # The 'deposits you confirmed' contract: Verified, the reason kept for the audit.
    assert (record["revenue_classification"], record["revenue_tier"], record["revenue_tier_reason"],
            record["revenue_review_status"], record["revenue_initial_classification"],
            record["revenue_initial_tier"]) == (
        "verified_revenue", "verified", "zelle_excluded", "confirmed", "non_revenue", "non_revenue")
    assert record["contributes_to_true_revenue"] is True and record["revenue_review_required"] is False
    metrics = payload["metrics"]
    assert metrics["non_revenue_by_reason"] == {"zelle_excluded": {"count": 2, "total": 500.0}}
    assert metrics["true_revenue_total"] == before["true_revenue_total"] + 1000.0
    assert metrics["verified_revenue_total"] == before["verified_revenue_total"] + 1000.0
    assert (metrics["non_revenue_total"], metrics["non_revenue_count"]) == (500.0, 2)
    assert metrics["revenue_tiers_sum_to_posted"] is True
    apply_serialized_revenue_review(payload, source_location=location, decision="reset")
    record = _row(payload, "ZELLE PAYMENT FROM PAT SAMPLE CONF 1")
    assert (record["revenue_classification"], record["revenue_tier"], record["revenue_tier_reason"],
            record["revenue_review_status"], record["revenue_reviewed_at"]) == (
        "non_revenue", "non_revenue", "zelle_excluded", "not_required", None)
    assert _figures(payload) == before


def test_q3_a_reject_on_a_zelle_deposit_is_refused_and_writes_nothing():
    """The row is already non-revenue, and the replay reads a confirm only: the writer refuses a reject, with
    today's message, before and after a confirm."""
    payload = _payload()
    location = _row(payload, "ZELLE PAYMENT FROM SAMPLE CATERING CONF 2")["source_location"]
    unchanged = copy.deepcopy(payload)
    with pytest.raises(ValueError, match="only automatically unverified deposits can be reviewed"):
        record_serialized_revenue_review(payload, source_location=location, decision="reject")
    assert payload == unchanged
    apply_serialized_revenue_review(payload, source_location=location, decision="confirm")
    confirmed = copy.deepcopy(payload)
    with pytest.raises(ValueError, match="only automatically unverified deposits can be reviewed"):
        record_serialized_revenue_review(payload, source_location=location, decision="reject")
    assert payload == confirmed


@pytest.mark.parametrize("decision", ["confirm", "reject", "reset"])
def test_q3_every_other_non_revenue_row_keeps_the_refusal(decision):
    """A Zelle refund a non-revenue rule decided carries no reason, and a government payment that prints no purpose
    carries its display reason only: neither may be reviewed."""
    refund = _payload([("ZELLE PAYMENT FROM PAT SAMPLE FOR REFUND CONF 1", 800.0), ("MOBILE DEPOSIT", 300.0)])
    government = _payload([("ELECTRONIC DEPOSIT FROM MN STATE-MMB", 4000.0), ("MOBILE DEPOSIT", 300.0)], "U.S. Bank")
    for payload, text, reason in (
        (refund, "ZELLE PAYMENT FROM PAT SAMPLE FOR REFUND CONF 1", None),
        (government, "ELECTRONIC DEPOSIT FROM MN STATE-MMB", "government_no_purpose"),
    ):
        record = _row(payload, text)
        assert (record["revenue_tier"], record["revenue_tier_reason"]) == ("non_revenue", reason)
        unchanged = copy.deepcopy(payload)
        with pytest.raises(ValueError, match="only automatically unverified deposits can be reviewed"):
            record_serialized_revenue_review(payload, source_location=record["source_location"], decision=decision)
        assert payload == unchanged
