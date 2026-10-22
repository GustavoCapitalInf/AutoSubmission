from __future__ import annotations

import pytest

from analysis.flag_groups import FLAG_GROUP_BY_STATE
from analysis.transaction_classifier.row import classify_transaction
from tests.flag_group_fixtures import FAKE_PAYEES, fake_payees  # noqa: F401  (fixture)

PAYEE_ROWS = [(alias, *FAKE_PAYEES[alias]) for alias in FAKE_PAYEES]


def _group_key(state: str) -> str | None:
    group = FLAG_GROUP_BY_STATE.get(state)
    return group.key if group is not None else None


@pytest.mark.parametrize(("alias", "entity", "state"), PAYEE_ROWS)
def test_a_known_payee_debit_takes_its_group(fake_payees, alias, entity, state):
    record = classify_transaction(f"ACH DEBIT {alias} 0001", -500.0)
    assert record.classification == state
    assert record.canonical_entity == entity
    assert record.matched_alias == alias
    assert record.flagged_group == _group_key(state)
    assert record.contributes_to_flagged_totals is (_group_key(state) is not None)
    assert record.contributes_to_withholding_rate is (state == "confirmed_lender")
    assert not record.contributes_to_potential_lender_totals


def test_a_card_paid_known_payee_is_classified_by_who_was_paid(fake_payees):
    paid = classify_transaction("CARD PURCHASE FABRICATED ALT", -80.0)
    store = classify_transaction("CARD PURCHASE FABRICATED STORE", -80.0)
    assert paid.classification == "alternative_position"
    assert not paid.is_pos_purchase
    assert store.classification == "pos"


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("FABRICATED LENDER TRANSFER FEE", "fee"),
        # Owner decision 2026-09-25: the bank's overdraft charge for an item is a fee,
        # even when it prints the item's payee.
        ("OVERDRAFT CHARGE FABRICATED ALT 0001", "fee"),
        ("FABRICATED LINE ONLINE TRANSFER", "transfer"),
        ("FABRICATED LENDER PAYROLL", "payroll"),
        ("CHECK 1001 FABRICATED LENDER", "confirmed_lender"),
        ("FABRICATED LENDER SUBSCRIPTION", "confirmed_lender"),
        ("FABRICATED ALT RENT", "alternative_position"),
    ],
)
def test_fees_and_transfers_keep_precedence_but_checks_no_longer_hide_a_payee(fake_payees, description, state):
    assert classify_transaction(description, -500.0).classification == state


def test_an_overdraft_charge_is_a_fee_and_its_refund_a_reversal():
    assert classify_transaction("OVERDRAFT CHARGE 0001", -35.0).classification == "fee"
    assert classify_transaction("OVERDRAFT CHARGE REVERSAL 0001", 35.0).classification == "refund_or_reversal"


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("FABRICATED BNPL PLUS MEMBERSHIP", "other"),
        ("FABRICATED BNPL BALANCE TOP UP", "other"),
        ("CARD PURCHASE FABRICATED BNPL PLUS", "pos"),
        ("FABRICATED BNPL PAYMENT", "alternative_position"),
        ("FABRICATED PERSONAL PLUS", "personal_loan"),
    ],
)
def test_a_membership_or_balance_top_up_is_not_a_repayment(fake_payees, description, state):
    """Owner decision 2026-09-25 (Klarna Inc): an alternative-position payee's paid membership,
    or a top-up of the customer's own balance with it, matches no known payee, so D8 does not
    apply and it never takes the payee's group. Other groups are not affected."""
    record = classify_transaction(description, -20.0)
    assert record.classification == state
    assert record.flagged_group == _group_key(state)


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("ACH DEBIT FABRICATED LENDER LOC PMT", "line_of_credit"),
        ("ACH DEBIT FABRICATED ALT LINE OF CREDIT", "line_of_credit"),
        ("ACH DEBIT FABRICATED LINE LOC", "line_of_credit"),
        ("ACH DEBIT FABRICATED CARMAKER FINANCIAL LOC", "vehicle_financing"),
        ("ACH DEBIT FABRICATED FLOORPLAN LOC", "floor_plan_financing"),
        ("ACH DEBIT FABRICATED ISSUER LINE OF CREDIT", "credit_card_payment"),
    ],
)
def test_loc_wording_moves_lender_and_alternative_payees_to_lines_of_credit(fake_payees, description, state):
    record = classify_transaction(description, -500.0)
    assert record.classification == state
    assert not record.contributes_to_withholding_rate


@pytest.mark.parametrize(
    ("description", "state", "entity"),
    [
        # The NMEF, Navitas, Balboa, Econolease and Progressive Leasing descriptors move here unchanged
        # from the order table of tests/test_lender_insurance_classification.py; the others are fabricated.
        ("NMEF Funding 2025A payment", "confirmed_lender", "NMEF"),
        ("Navitas Credit Corp payment", "confirmed_lender", "Navitas Credit Corp"),
        ("Balboa Capital payment", "confirmed_lender", "Balboa Capital"),
        ("CHECKCARD 0102 NMEF FUNDING", "confirmed_lender", "NMEF"),
        ("CHECK 1234 FORA FINANCIAL", "confirmed_lender", "FORA FINANCIAL"),
        # Owner decisions 2026-09-25: Econolease is equipment finance, a lender; EBF Holdings
        # is Everest Business Funding, one funder counted once.
        ("VLFC-Econolease finance payment", "confirmed_lender", "Econolease"),
        ("EBF HOLDINGS DEBIT 0001", "confirmed_lender", "EVEREST BUSINESS FUNDING"),
        ("BDC loan payment", "alternative_position", "BDC"),
        ("ACH DEBIT INTUIT FINANCING 0001", "alternative_position", "INTUIT FINANCING"),
        ("CARD PURCHASE AFFIRMCOM 0001", "alternative_position", "AFFIRM"),
        # Owner ruling 2026-09-25: Capital Infusion (the house) is flagged, never counted.
        ("CAPITAL INFUSION PAYMENT", "alternative_position", "CAPITAL INFUSION"),
        ("BLUEVINE loan payment", "line_of_credit", "BLUEVINE"),
        ("BLUEVINE CAPITAL", "line_of_credit", "BLUEVINE"),
        ("FUNDBOX payment", "line_of_credit", "FUNDBOX"),
        ("KABBAGE payment", "line_of_credit", "KABBAGE"),
        ("Progressive Leasing recurring purchase", "lease_or_rental", "Progressive Leasing"),
        ("SMARTPAY LEASING payment", "lease_or_rental", "SmartPay"),
    ],
)
def test_owner_ruled_payees_take_their_groups(description, state, entity):
    record = classify_transaction(description, -100.0)
    assert (record.classification, record.canonical_entity) == (state, entity)
    assert record.contributes_to_withholding_rate is (state == "confirmed_lender")
    assert record.flagged_group == _group_key(state)


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("NEXTGEAR CAPITAL PAYMENT", "floor_plan_financing"),
        ("RTS FINANCIAL PAYMENT", "factoring"),
    ],
)
def test_owner_named_floor_plan_and_factoring_payees_take_their_groups(description, state):
    """Spec §2 amendment: floor plan and factoring are flagged like alternative positions."""
    record = classify_transaction(description, -100.0)
    assert record.classification == state
    assert record.flagged_group == _group_key(state)
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_withholding_rate


def test_smartpay_solutions_premium_billing_is_not_the_lease_to_own_smartpay():
    """Owner decision 2026-09-25: SMARTPAY SOL rows are SmartPay Solutions' premium billing,
    not the lease-to-own SmartPay Leasing, so they stay unflagged."""
    # Moves here unchanged from the order table of tests/test_lender_insurance_classification.py.
    record = classify_transaction("SmartPay Sol debitpmt", -100.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == ("other", None, None)


@pytest.mark.parametrize(
    ("debit", "credit", "state", "entity"),
    [
        ("SEZZLE PAYMENT 0001", "SEZZLE MERCHANT PAYOUT 0001", "alternative_position", "Sezzle Inc"),
        ("PAYABILITY PAYMENT 0001", "PAYABILITY MARKETPLACE PAYOUT 0001", "confirmed_lender", "PAYABILITY"),
    ],
)
def test_a_payout_credit_entity_keeps_its_group_on_debits_and_its_payouts_are_revenue(debit, credit, state, entity):
    """Owner decision 2026-09-25 (PAYOUT_CREDIT_ENTITIES): the platform settles the account
    holder's own sales, so its credits are revenue, not financing proceeds."""
    paid = classify_transaction(debit, -100.0)
    assert (paid.classification, paid.canonical_entity) == (state, entity)
    assert paid.contributes_to_withholding_rate is (state == "confirmed_lender")
    payout = classify_transaction(credit, 900.0)
    assert payout.matched_rule != "financing_proceeds_credit"
    assert not payout.contributes_to_lender_credit_exclusion
    assert payout.revenue_classification == "verified_revenue"
    assert payout.revenue_match_method != "financing_proceeds_credit"


@pytest.mark.parametrize(
    "description",
    # The ATB Mastercard and Capital One descriptors move here unchanged from the order table of
    # tests/test_lender_insurance_classification.py; the third is fabricated.
    ["ATB Mastercard payment", "ACH Capital One TYPE: ONLINE PMT", "CREDIT CARD PAYMENT FABRICATED"],
)
def test_card_payments_are_flagged_credit_cards_never_lenders(description):
    record = classify_transaction(description, -100.0)
    assert record.classification == "credit_card_payment"
    assert record.flagged_group == "credit_cards"
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_withholding_rate
    assert not record.contributes_to_potential_lender_totals


@pytest.mark.parametrize(("description", "state"), [("ONDECK TRANSFER FEE", "fee"), ("BLUEVINE ONLINE TRANSFER", "transfer")])
def test_fee_and_transfer_precedence_survives_the_real_matcher(description, state):
    assert classify_transaction(description, -100.0).classification == state


@pytest.mark.parametrize(
    "description",
    # A fabricated card purchase of Intuit software: a bare platform name with no financing wording.
    ["SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "CARD PURCHASE INTUIT QUICKBOOKS 0001"],
)
def test_bare_platform_names_are_never_a_flagged_payee(description):
    record = classify_transaction(description, -100.0)
    assert record.flagged_group is None
    assert record.classification not in ("confirmed_lender", "alternative_position")


@pytest.mark.parametrize(
    "name",
    ["LEASE_PROVIDER_ALIASES", "LEGACY_CONFIRMED_LENDER_ALIASES", "LEGACY_POTENTIAL_LENDER_ALIASES"],
)
def test_the_retired_classifier_inputs_are_gone(name):
    from analysis import classification_registry

    assert not hasattr(classification_registry, name)
