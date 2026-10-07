"""Spec sections 2 and 5, and the S1 facts S2's Task 0 checks, on the registry rendered from the committed
ledger (contract C10), with the owner's rulings of 2026-09-25. The descriptors are fabricated around public
company names; none is statement text."""
from __future__ import annotations

import re

import pytest

from analysis import classification_registry as registry
from analysis.description_text import normalize_transaction_description as normalize
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import match_known_payee, registry_match
from tools import build_lender_registry as builder
from tools import lender_ledger

DATA = lender_ledger.read_ledger(lender_ledger.LEDGER_PATH)
ENTITIES, SHAPE_PROBLEMS = lender_ledger.parse_ledger(DATA)
BY_NAME = {entity.entity: entity for entity in ENTITIES}
RULES = lender_ledger.current_rules()
EVIDENCE = builder.EVIDENCE_PATH.read_text(encoding="utf-8")
REGISTRY_TABLES = {table: getattr(registry, table) for _group, table, _heading in lender_ledger.TABLES}

#: The S2 plan's Task 0 Step 3 OWNER_RULED rows, as the owner's rulings of 2026-09-25 amend them (AFC FUNDING
#: CORP is floor plan; BLUEVINE CAPITAL and SMARTPAY LEASING are the owner-named spellings; EBF HOLDINGS is
#: merged into EVEREST BUSINESS FUNDING; CAPITAL INFUSION is an alternative position): (descriptor, entity, state).
S2_TASK_0 = (
    ("NMEF Funding 2025A payment", "NMEF", "confirmed_lender"),
    ("Navitas Credit Corp payment", "Navitas Credit Corp", "confirmed_lender"),
    ("Balboa Capital payment", "Balboa Capital", "confirmed_lender"),
    ("DIRECT DEB DELAGELANDEN LEASE", "De Lage Landen", "confirmed_lender"),
    ("CHECKCARD 0102 NMEF FUNDING", "NMEF", "confirmed_lender"),
    ("CHECK 1234 FORA FINANCIAL", "FORA FINANCIAL", "confirmed_lender"),
    ("CHECKCARD 0102 ONDECK CAPITAL", "ONDECK", "confirmed_lender"),
    ("Canacap payment", "CanaCap", "confirmed_lender"),
    ("CAN Capital loan payment", "CAN Capital", "confirmed_lender"),
    ("Direct Debit Business PAD Forward Funding", "Forward Funding", "confirmed_lender"),
    ("Direct Debit Business PAD Forward Financing", "Forward Financing", "confirmed_lender"),
    ("ACH DEBIT RAPID FINANCE PAYMENT", "RAPID FINANCE", "confirmed_lender"),
    ("Orig CO Name:Kapitus Descr:Payment ACH Debit", "KAPITUS", "confirmed_lender"),
    ("ACH DEBIT THE FUNDWORKS LLC PMT", "FUNDWORKS", "confirmed_lender"),
    ("EBF HOLDINGS DEBIT 0001", "EVEREST BUSINESS FUNDING", "confirmed_lender"),
    ("AFC FUNDING CORP XPRESS PAY", "AFC FUNDING CORP", "floor_plan_financing"),
    ("BDC loan payment", "BDC", "alternative_position"),
    ("CARD PURCHASE AFFIRMCOM 0001", "AFFIRM", "alternative_position"),
    ("ACH DEBIT INTUIT FINANCING 0001", "INTUIT FINANCING", "alternative_position"),
    ("SQUARE CAPITAL", "SQUARE CAPITAL", "alternative_position"),
    ("SHOPIFY CAPITAL PAYOUT", "SHOPIFY CAPITAL", "alternative_position"),
    ("PAYPAL WORKING CAPITAL", "PAYPAL WORKING CAPITAL", "alternative_position"),
    ("CAPITAL INFUSION PAYMENT", "CAPITAL INFUSION", "alternative_position"),
    ("BLUEVINE loan payment", "BLUEVINE", "line_of_credit"),
    ("BLUEVINE CAPITAL", "BLUEVINE", "line_of_credit"),
    ("FUNDBOX payment", "FUNDBOX", "line_of_credit"),
    ("KABBAGE payment", "KABBAGE", "line_of_credit"),
    ("External Withdrawal SNAP FINANCE - PAYMENT", "SNAP Finance", "lease_or_rental"),
    ("Progressive Leasing recurring purchase", "Progressive Leasing", "lease_or_rental"),
    ("SMARTPAY LEASING payment", "SmartPay", "lease_or_rental"),
)


def _known(descriptor):
    return match_known_payee(normalize(descriptor))


def _claimed_by(descriptor):
    """The rendered tables with an alias in the descriptor, whatever their context."""
    return [table for table, entries in REGISTRY_TABLES.items() if registry_match(normalize(descriptor), entries)]


def test_the_committed_ledger_passes_the_validator():
    assert SHAPE_PROBLEMS == []
    assert lender_ledger.validate(DATA, RULES) == []


def test_every_payee_the_owner_named_is_in_its_ruled_group_in_the_committed_registry():
    assert lender_ledger.owner_named_problems(REGISTRY_TABLES, registry.OWNER_NAMED_PAYEES) == []


@pytest.mark.parametrize("descriptor,entity,state", S2_TASK_0)
def test_the_known_payee_facts_s2_task_0_checks_hold(descriptor, entity, state):
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, state), found


@pytest.mark.parametrize("descriptor", ["SBA LOAN PAYMENT", "SBA EIDL LOAN PAYMENT"])
def test_sba_loan_payments_are_alternative_positions(descriptor):
    found = _known(descriptor)
    assert found is not None and found.state == "alternative_position", found


@pytest.mark.parametrize("descriptor,state", [("NEXTGEAR CAPITAL PAYMENT", "floor_plan_financing"),
                                              ("RTS FINANCIAL PAYMENT", "factoring")])
def test_the_amendment_groups_s2_task_0_checks(descriptor, state):
    found = _known(descriptor)
    assert found is not None and found.state == state, found


@pytest.mark.parametrize("descriptor", ["IPFS CORP PMT", "FIRST INSURANCE FUNDING PMT"])
def test_premium_financiers_are_premium_finance_payees_and_no_known_payee(descriptor):
    assert registry_match(normalize(descriptor), registry.PREMIUM_FINANCE_ALIASES) is not None
    assert _known(descriptor) is None


@pytest.mark.parametrize("descriptor", ["SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "AMAZON",
                                        "CARD PURCHASE INTUIT QUICKBOOKS 0001"])
def test_bare_platform_names_are_no_known_payee(descriptor):
    assert _known(descriptor) is None


@pytest.mark.parametrize("descriptor", ["ACH Capital One TYPE: ONLINE PMT", "ATB Mastercard payment",
                                        "Office rent payment"])
def test_card_payments_and_rent_are_never_claimed_by_a_lender_or_financing_alias(descriptor):
    found = _known(descriptor)
    assert found is None or found.state == "credit_card_payment", found


def test_netcredit_is_a_financing_payee_named_netcredit():
    found = _known("NETCREDIT CCBANK-NTC loan proceeds")
    assert found is not None and found.entity == "NETCREDIT" and found.state in FINANCING_STATES, found


@pytest.mark.parametrize("descriptor,entity", [("VLFC-Econolease finance payment", "Econolease"),
                                               ("CMCA Finance BUS payment", "CMCA Finance"),
                                               ("Lily Advance", "Lily Advance")])
def test_econolease_cmca_finance_and_lily_advance_are_counted_lenders_and_no_potential_alias(descriptor, entity):
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, "confirmed_lender"), found
    assert registry_match(normalize(descriptor), registry.POTENTIAL_LENDER_ALIASES) is None


def test_truist_is_on_the_bank_name_list():
    assert registry_match(normalize("TRUIST LN 0001 PYMT"), registry.BANK_NAME_ALIASES) is not None


@pytest.mark.parametrize("descriptor,entity", [("Clover equipment rent/leases", "Clover Equipment"),
                                               ("INVESTMENT MERCH PAD", "MERCH PAD (probably Merchant Growth)"),
                                               ("REWARDS NETWORK PAYMENT", "Rewards Network")])
def test_review_tier_payees_are_potential_lender_aliases_and_no_known_payee(descriptor, entity):
    assert _known(descriptor) is None
    found = registry_match(normalize(descriptor), registry.POTENTIAL_LENDER_ALIASES)
    assert found is not None and found[0] == entity, found
    assert BY_NAME[entity].status == "review"


@pytest.mark.parametrize("descriptor,entity", [("ACH DEBIT FORWARDFINANCING LLC", "Forward Financing"),
                                               ("ACH DEBIT EXPANSIONCAP", "EXPANSION CAPITAL")])
def test_the_run_together_spellings_spec_section_1_names_match_their_lender(descriptor, entity):
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, "confirmed_lender"), found


@pytest.mark.parametrize("descriptor,wrong", [
    ("JOURNEY CAPITAL ONDECK CANADA BUS ENT", "ONDECK"),
    ("ONLINE BANKING PAYMENT 0102 ENOVA POWER CO", "ONDECK"),
    ("ACH WEB SMARTPAY ATLASFINANCIAL", "SmartPay"),
])
def test_the_collisions_spec_section_5_names_are_gone(descriptor, wrong):
    found = _known(descriptor)
    assert found is None or found.entity != wrong, found


def test_bluevine_is_bluevine_capital_and_bluevine_loan_without_the_bare_alias():
    # Owner ruling 2026-09-25: bare BLUEVINE takes Bluevine Bill Pay and Bluevine checking rows.
    assert registry.LINE_OF_CREDIT_ALIASES["BLUEVINE"] == ("BLUEVINE CAPITAL", "BLUEVINE LOAN")
    assert not [name for entries in REGISTRY_TABLES.values() for name, aliases in entries.items()
                if any(normalize(alias) == "BLUEVINE" for alias in aliases)]
    for descriptor in ("BLUEVINE", "BLUEVINE BILL PAY QUILLON BAKERY", "BLUEVINE ONLINE TRANSFER"):
        assert _known(descriptor) is None and _claimed_by(descriptor) == [], descriptor


def test_smartpay_is_smartpay_leasing_and_smartpay_sol_is_claimed_by_no_table():
    # Owner ruling 2026-09-25: SMARTPAY SOL is SmartPay Solutions' premium billing, not the lease-to-own SmartPay.
    assert registry.LEASE_RENTAL_ALIASES["SmartPay"] == ("SMARTPAY LEASING",)
    assert registry.REATTRIBUTED_REGISTRY_ALIASES == {"SMARTPAY SOL": "SmartPay Solutions, LLC"}
    solutions = BY_NAME["SmartPay Solutions, LLC"]
    assert solutions.status == "rejected" and "SMARTPAY SOL" in solutions.aliases
    for descriptor in ("SmartPay Sol debitpmt", "SMARTPAY SOL"):
        assert _known(descriptor) is None and _claimed_by(descriptor) == [], descriptor


def test_first_insurance_is_premium_financing_of_first_insurance_funding_on_the_owners_ruling():
    premium = registry.PREMIUM_FINANCE_ALIASES
    assert registry.PREMIUM_FINANCE_INSURER_ALIASES == ("FIRST INSURANCE",)
    for descriptor in ("FIRST INSURANCE FUNDING PMT", "FIRST INSURANCE PMT"):
        found = registry_match(normalize(descriptor), premium)
        assert found is not None and found[0] == "FIRST Insurance Funding", (descriptor, found)
        assert _known(descriptor) is None, descriptor
    found = registry_match(normalize("PAD FIRST INSURANCE LOAN"), premium)
    assert found is not None and found[0] == "FIRST Insurance Funding of Canada", found
    assert registry.INSURANCE_PROVIDER_ALIASES["First Insurance"] == ("FIRST INSURANCE",)
    insurer_aliases = {normalize(a) for aliases in registry.INSURANCE_PROVIDER_ALIASES.values() for a in aliases}
    premium_aliases = {normalize(a) for aliases in premium.values() for a in aliases}
    assert insurer_aliases & premium_aliases == {normalize(a) for a in registry.PREMIUM_FINANCE_INSURER_ALIASES}
    assert not set(premium) & set(registry.INSURANCE_PROVIDER_ALIASES)
    assert "only on the owner's ruling (`PREMIUM_FINANCE_INSURER_ALIASES`)" in EVIDENCE
    assert "has an alias that contains an alias of the hand-kept insurer" not in EVIDENCE


def test_ebf_holdings_is_merged_into_everest_business_funding_and_counts_once():
    assert registry.MERGED_REGISTRY_ENTITIES == {"EBF HOLDINGS": "EVEREST BUSINESS FUNDING"}
    assert "EBF HOLDINGS" not in BY_NAME
    assert not [table for table, entries in REGISTRY_TABLES.items() if "EBF HOLDINGS" in entries]
    assert {"EBF HOLDINGS", "EBF DEBIT", "HOLDINGS EBF"} <= set(registry.LENDER_ALIASES["EVEREST BUSINESS FUNDING"])
    found = _known("HOLDINGS EBF DEBIT")
    assert found is not None and (found.entity, found.state) == ("EVEREST BUSINESS FUNDING", "confirmed_lender")
    assert "| EBF HOLDINGS | confirmed_lender | confirmed_lender (merged into EVEREST BUSINESS FUNDING) |" in EVIDENCE


@pytest.mark.parametrize("descriptor,entity,state", [
    ("SEZZLE PAYMENT", "Sezzle Inc", "alternative_position"),
    ("AMERICAN FIRST FINANCE PAYMENT", "American First Finance, LLC", "alternative_position"),
    ("PAYABILITY PAYMENT", "PAYABILITY", "confirmed_lender"),
    # Owner ruling 2026-09-28 (true revenue spec OQ2): the BNPL providers' settlements to the merchant are revenue.
    ("AFFIRM PAYMENT", "AFFIRM", "alternative_position"),
    ("AFTERPAY PAYMENT", "Afterpay", "alternative_position"),
    ("GREENSKY PAYMENT", "GreenSky", "alternative_position"),
    ("KLARNA PAYMENT", "Klarna Inc", "alternative_position"),
    ("SUNBIT PAYMENT", "Sunbit", "alternative_position"),
    # Owner ruling 2026-10-02 (Q8): Cherry's payout to a practice for a patient-financed treatment is the practice's
    # own sale; its debits stay an alternative position.
    ("CHERRY TECHNOLOGIES PAYMENT", "Cherry Technologies, Inc.", "alternative_position"),
])
def test_the_payout_credit_entities_are_admitted_financing_payees_whose_debits_keep_their_group(
        descriptor, entity, state):
    # Owner ruling 2026-09-25: their credits are the holder's own sales settled by the platform, which S2 reads
    # as revenue (PAYOUT_CREDIT_ENTITIES, a D1 exception); the matcher still gives every row the entity's group.
    assert registry.PAYOUT_CREDIT_ENTITIES == (
        "Sezzle Inc", "American First Finance, LLC", "PAYABILITY", "AFFIRM", "Afterpay", "GreenSky", "Klarna Inc",
        "Sunbit", "Cherry Technologies, Inc.",
    )
    assert BY_NAME[entity].status == "admitted" and BY_NAME[entity].group in FINANCING_STATES
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, state), found


@pytest.mark.parametrize("entity,group,status", [
    ("CAPITAL INFUSION", "alternative_position", "admitted"),
    ("MERCH PAD (probably Merchant Growth)", "confirmed_lender", "review"),
    ("Rewards Network", "confirmed_lender", "review"),
    ("MR BIZ CAPITAL", "confirmed_lender", "rejected"),
    ("Keep Technologies Corp", "credit_card_payment", "rejected"),
    ("LADCO Leasing", "lease_or_rental", "admitted"),
])
def test_the_owner_delegated_rulings_of_2026_09_25_file_each_payee_in_its_place(entity, group, status):
    assert (BY_NAME[entity].group, BY_NAME[entity].status) == (group, status)
    counted = entity in registry.LENDER_ALIASES
    assert counted == (group == "confirmed_lender" and status == "admitted"), entity


def test_the_numbered_ontario_company_waits_for_the_owner_unsearched_and_without_its_number():
    numbered = [entity for entity in ENTITIES if entity.status == "owner_ruling"
                and "numbered ontario company" in f"{entity.entity} {entity.notes}".lower()]
    assert numbered
    for entity in numbered:
        # Spec section 5: it is not searched anywhere, by rule. A URL is where the digit rule does not look.
        assert entity.evidence == () and entity.where_looked == (), entity.index
        assert not any(re.search(r"\d", alias) for alias in entity.aliases), entity.index


def test_no_digit_run_of_five_or_more_reaches_the_ledgers_outside_urls_and_todays_aliases():
    held = {run for table in RULES.baseline.values() for aliases in table.values() for alias in aliases
            for run in re.findall(r"\d{5,}", alias)}
    for text in (EVIDENCE, lender_ledger.LEDGER_PATH.read_text(encoding="utf-8")):
        stripped = re.sub(r"sha256:[0-9a-f]{64}", "", re.sub(r"https?://[^\s\"|,]+", "", text))
        assert set(re.findall(r"\d{5,}", stripped)) <= held


@pytest.mark.parametrize(
    ("descriptor", "entity"),
    [
        ("MERIDIAN RLS LOY 0001", "Meridian (RLS rent/lease PAD; probably Meridian OneCap Credit Corp)"),
        ("FUTURE FUNDING DES:PAYMENT ID:0001", "FUTURE FUNDING (legal entity not identified)"),
        ("NATIONWIDECREDIT TELECHK 0001", "Nationwide Credit (debt collector; creditor not printed)"),
        ("ORIG CO NAME ACCOUNT SERVICIN ORIG ID 0001", "Unidentified account servicer (ACCOUNT SERVICIN[G])"),
    ],
)
def test_review_payees_are_published_under_names_that_say_what_the_ledger_knows(descriptor, entity):
    found = registry_match(normalize(descriptor), registry.POTENTIAL_LENDER_ALIASES)
    assert found is not None and found[0] == entity, found
