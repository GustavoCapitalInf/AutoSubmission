from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from analysis import transaction_classifier
from analysis.flag_groups import FINANCING_STATES
from analysis.metrics import compute_metrics
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import FAKE_PAYEES, fake_payees, txn  # noqa: F401  (fixture)

PAYEE_ROWS = [(alias, *FAKE_PAYEES[alias]) for alias in FAKE_PAYEES]


@pytest.mark.parametrize(("alias", "entity", "state"), PAYEE_ROWS)
def test_a_known_payee_credit_is_proceeds_only_for_a_financing_group_other_than_factoring(
    fake_payees, alias, entity, state
):
    record = classify_transaction(f"{alias} DEPOSIT 0001", 5000.0)
    if state == "factoring":
        # Owner ruling 2026-09-26: a factor's payout is revenue and keeps the Factoring flag
        # (tests/test_factoring_credits.py).
        assert (record.flagged_group, record.contributes_to_flagged_totals) == ("factoring", True)
    else:
        assert record.flagged_group is None
        assert not record.contributes_to_flagged_totals
    if state in FINANCING_STATES and state != "factoring":
        assert record.classification == "other"
        assert record.canonical_entity == entity
        assert record.match_method == "financing_proceeds_credit"
        assert record.matched_rule == "financing_proceeds_credit"
        assert record.contributes_to_lender_credit_exclusion
        assert record.revenue_classification == "non_revenue"
        assert record.revenue_match_method == "financing_proceeds_credit"
        assert record.revenue_canonical_entity == entity
    else:
        assert record.matched_rule != "financing_proceeds_credit"
        assert not record.contributes_to_lender_credit_exclusion
        assert record.revenue_classification == "unverified_deposit"


def test_the_owner_named_floor_plan_credit_is_financing_proceeds():
    """Spec §2 amendment and §4.2: D1 covers floor-plan credits. Factoring credits are revenue since the owner's
    ruling of 2026-09-26 (tests/test_factoring_credits.py)."""
    record = classify_transaction("NEXTGEAR CAPITAL PAYMENT", 100.0)
    assert record.matched_rule == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion
    assert record.revenue_classification == "non_revenue"


def test_platform_financing_credits_are_proceeds_but_platform_sales_stay_revenue():
    statement = Statement(
        bank="Fabricated Bank",
        account_name="Business Checking",
        transactions=[
            txn("2054-01-02", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-09", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-16", "SQUARE CAPITAL", 5000.0),
            txn("2054-01-17", "SQUARE SETTLEMENT", 800.0),
            txn("2054-01-18", "SHOPIFY CAPITAL PAYOUT", 900.0),
        ],
    )
    records = classify_statement_transactions(statement)
    assert [record.revenue_classification for record in records] == [
        "non_revenue", "non_revenue", "non_revenue", "verified_revenue", "non_revenue",
    ]
    assert {records[index].revenue_match_method for index in (0, 1, 2, 4)} == {"financing_proceeds_credit"}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_credits == 15900.0
    assert metrics.verified_revenue_total == 800.0
    assert metrics.legacy_eligible_deposits == 800.0


@pytest.fixture
def fabricated_payout_entity(monkeypatch):
    """Owner decision 2026-09-25: the credits of a PAYOUT_CREDIT_ENTITIES payee are the
    account holder's own sales, settled by the platform."""
    monkeypatch.setattr(transaction_classifier, "PAYOUT_CREDIT_ENTITIES", ("Fabricated BNPL",))


def test_a_payout_credit_entitys_credit_is_revenue_not_proceeds(fake_payees, fabricated_payout_entity):
    payout = classify_transaction("FABRICATED BNPL MERCHANT PAYOUT 0001", 900.0)
    assert payout.matched_rule != "financing_proceeds_credit"
    assert not payout.contributes_to_lender_credit_exclusion
    assert payout.revenue_classification == "verified_revenue"
    assert payout.revenue_match_method != "financing_proceeds_credit"
    # Another alternative position's credit is still proceeds.
    assert classify_transaction("FABRICATED ALT DEPOSIT 0001", 900.0).matched_rule == "financing_proceeds_credit"


@pytest.mark.parametrize(
    ("description", "classification", "entity"),
    [
        ("ONLINE TRANSFER FROM FABRICATED LENDER 0001", "transfer", "Fabricated Lender"),
        ("ONLINE TRANSFER FROM FABRICATED ALT 0001", "transfer", "Fabricated Alt Capital"),
        ("FABRICATED LINE POLICY 0001", "insurance", "Fabricated Line"),
    ],
)
def test_a_financing_group_credit_an_earlier_rule_claims_is_still_excluded(
    fake_payees, description, classification, entity
):
    """Contract C4, spec §4.4: a financing group's credit is non_revenue proceeds AND is excluded
    from eligible deposits, even when an earlier rule (a transfer, an insurance term) names the row."""
    statement = Statement(
        bank="Fabricated Bank",
        transactions=[
            txn("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 800.0),
            txn("2054-01-03", description, 5000.0),
        ],
    )
    records = classify_statement_transactions(statement)
    record = records[1]
    assert record.classification == classification
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.revenue_canonical_entity == entity
    assert record.contributes_to_lender_credit_exclusion
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_credits == 5000.0
    assert metrics.legacy_eligible_deposits == 800.0


def test_a_payout_entitys_transfer_worded_credit_stays_in_eligible_deposits(fake_payees, fabricated_payout_entity):
    record = classify_transaction("ONLINE TRANSFER FROM FABRICATED BNPL 0001", 900.0)
    assert record.classification == "transfer"
    assert record.revenue_match_method != "financing_proceeds_credit"
    assert not record.contributes_to_lender_credit_exclusion


#: Owner ruling OQ2 (true revenue spec §19): the five BNPL providers whose settlements to the merchant joined
#: PAYOUT_CREDIT_ENTITIES (S1.4).
OQ2_BNPL_ENTITIES = ("AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit")


@pytest.fixture
def before_oq2(monkeypatch):
    """The 5.4 reading of a row: classified with PAYOUT_CREDIT_ENTITIES as it was before OQ2 added the five."""
    before = tuple(entity for entity in registry.PAYOUT_CREDIT_ENTITIES if entity not in OQ2_BNPL_ENTITIES)
    assert len(before) == len(registry.PAYOUT_CREDIT_ENTITIES) - len(OQ2_BNPL_ENTITIES)

    def classify(description, amount):
        with monkeypatch.context() as patch:
            patch.setattr(transaction_classifier, "PAYOUT_CREDIT_ENTITIES", before)
            return classify_transaction(description, amount)

    return classify


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        # The census's consumer-side shapes (S3.2, 5.4 -> 5.5): a Klarna withdrawal and the purchase returns.
        ("ACH DEPOSIT KLARNA FABRIKAM WITHDRAWAL CONTOSO", "Klarna Inc"),
        ("KLARNA WITHDRAWAL 0001", "Klarna Inc"),
        ("RETURN FOR KLARNA PURCHASE NORTHWIND", "Klarna Inc"),
        ("RETURN FOR KLARNA PURCHASE 0001 NORTHWIND", "Klarna Inc"),
        ("RETURN FOR AFFIRM COM FABRIKAM AFFIRM COM CONTOSO 0001", "AFFIRM"),
        # The earlier probes: a card product, a debt collector's alias, a balance withdrawal.
        ("AFFIRMCARD FABRIKAM", "AFFIRM"),
        ("TRUEACCORD KLARNA FABRIKAM", "Klarna Inc"),
        ("KLARNA BALANCE WITHDRAWAL", "Klarna Inc"),
        # Each other consumer-side word, on each provider.
        ("KLARNA CARD FABRIKAM 0001", "Klarna Inc"),
        ("GREENSKY CARD 0001 SAMPLE", "GreenSky"),
        ("GREENSKY WITHDRAW 0001", "GreenSky"),
        ("AFTERPAY PURCHASE FABRIKAM 0001", "Afterpay"),
        ("AFTERPAY CASH BACK 0001", "Afterpay"),
        ("SUNBIT CASHBACK 0001", "Sunbit"),
        ("SUNBIT REWARD 0001", "Sunbit"),
        ("SUNBIT REWARDS 0001", "Sunbit"),
    ],
)
def test_a_bnpl_providers_consumer_credit_keeps_its_5_4_reading(before_oq2, description, entity):
    """OQ2 covers a BNPL provider's settlement to the merchant, never the account holder's own consumer credits
    (a withdrawal, a purchase return, a card, a balance, a reward or a collector's credit): those stay financing
    proceeds (D1), as 5.4 read them, and out of eligible deposits."""
    record = classify_transaction(description, 25.0)
    assert record == before_oq2(description, 25.0)
    assert (record.match_method, record.matched_rule, record.canonical_entity) == (
        "financing_proceeds_credit", "financing_proceeds_credit", entity,
    )
    assert record.contributes_to_lender_credit_exclusion
    assert (record.revenue_classification, record.revenue_match_method, record.revenue_canonical_entity) == (
        "non_revenue", "financing_proceeds_credit", entity,
    )


@pytest.mark.parametrize("description", ["AFFIRM REFUND 0001", "AFTERPAY RFND 0001", "KLARNA REFUND FABRIKAM"])
def test_a_bnpl_providers_refund_keeps_its_5_4_reading(before_oq2, description):
    record = classify_transaction(description, 25.0)
    assert record == before_oq2(description, 25.0)
    assert (record.revenue_classification, record.revenue_match_method) == (
        "non_revenue", "reversal_cancellation_exclusion",
    )


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("AFFIRM INC DES:SETTLEMENT ID:0001 INDN:FABRIKAM LLC CO ID:0001 CCD", "AFFIRM"),
        ("AFFIRM COM FABRIKAM DES:TRANSFER ID:0001 INDN:CONTOSO CO ID:0001 PPD", "AFFIRM"),
        ("KLARNA INC DES:PAYOUT ID:0001", "Klarna Inc"),
        ("AFTERPAY US INC MERCHANT PAYMENT 0001", "Afterpay"),
        ("GREENSKY SETTLEMENT 0001", "GreenSky"),
        ("SUNBIT MERCHANT PAYOUT 0001", "Sunbit"),
    ],
)
def test_a_bnpl_providers_settlement_still_leaves_d1(before_oq2, description, entity):
    """Owner ruling OQ2: the settlement is the merchant's own sale, so it is revenue, not financing proceeds."""
    before = before_oq2(description, 900.0)
    assert (before.revenue_match_method, before.revenue_canonical_entity) == ("financing_proceeds_credit", entity)
    record = classify_transaction(description, 900.0)
    assert record.matched_rule != "financing_proceeds_credit"
    assert not record.contributes_to_lender_credit_exclusion
    assert record.revenue_classification in {"verified_revenue", "unverified_deposit"}
    assert record.revenue_match_method != "financing_proceeds_credit"


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("AFFIRM PAYMENT 0001", "AFFIRM"),
        ("AFTERPAY PAYMENT 0001", "Afterpay"),
        ("GREENSKY PAYMENT 0001", "GreenSky"),
        ("KLARNA PAYMENT 0001", "Klarna Inc"),
        ("SUNBIT PAYMENT 0001", "Sunbit"),
        ("AFFIRMCARD FABRIKAM", "AFFIRM"),
        ("KLARNA CARD PURCHASE FABRIKAM", "Klarna Inc"),
    ],
)
def test_a_bnpl_providers_debit_keeps_alternative_position(before_oq2, description, entity):
    record = classify_transaction(description, -100.0)
    assert record == before_oq2(description, -100.0)
    assert (record.classification, record.canonical_entity) == ("alternative_position", entity)


@pytest.mark.parametrize(
    "description",
    # Sezzle prints WITHDRAWAL on its merchant payouts, and PAYABILITY a CARD on its transfers: their credits keep
    # the entity-wide exception of 2026-09-25.
    ["SEZZLE MERCHANT WITHDRAWAL FABRIKAM 0001", "SEZZLE CARD FABRIKAM 0001", "PAYABILITY FABRIKAM CARD 0001",
     "AMERICAN FIRST FINANCE BALANCE 0001"],
)
def test_the_consumer_words_narrow_only_the_oq2_bnpl_providers(description):
    record = classify_transaction(description, 900.0)
    assert record.matched_rule != "financing_proceeds_credit"
    assert not record.contributes_to_lender_credit_exclusion
    assert record.revenue_match_method != "financing_proceeds_credit"


@pytest.mark.parametrize(
    ("description", "rule", "entity"),
    [
        ("LOAN CREDIT", "bank_line_advance_credit", "Fabricated Bank"),
        ("LOC ADVANCE 0001", "loc_draw_credit", "Fabricated Bank"),
        ("ADVANCE FROM LINE OF CREDIT 0001", "loc_draw_credit", "Fabricated Bank"),
        ("ADVANCE 2054 FABRICATED MODEL VIN 0001", "floor_plan_advance_credit", None),
    ],
)
def test_a_credit_whose_words_say_financing_proceeds_is_proceeds(description, rule, entity):
    """Owner decisions 2026-09-25: the bank's own line advance, a line-of-credit draw and a
    per-vehicle floor-plan advance are financing proceeds (D1), with no flag."""
    record = classify_transaction(description, 900.0, bank="Fabricated Bank")
    assert record.classification == "other"
    assert (record.match_method, record.matched_rule, record.canonical_entity) == (
        "financing_proceeds_credit",
        rule,
        entity,
    )
    assert record.contributes_to_lender_credit_exclusion
    assert record.flagged_group is None
    assert record.revenue_classification == "non_revenue"
    assert (record.revenue_match_method, record.revenue_matched_rule) == ("financing_proceeds_credit", rule)
    assert record.revenue_canonical_entity == entity


def test_only_the_exact_bank_line_posting_is_proceeds_by_its_words():
    record = classify_transaction("LOAN CREDIT MEMO 0001", 900.0, bank="Fabricated Bank")
    assert record.revenue_match_method == "strong_non_revenue_rule"
    assert not record.contributes_to_lender_credit_exclusion
