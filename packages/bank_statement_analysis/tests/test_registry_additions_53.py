"""5.3 (owner ruling 2026-09-27): the registry entries the false-positive hunt added, in their printed forms.
Fabricated descriptors in each bank's layout; the payee names are the registry's business names."""
from __future__ import annotations

import pytest

from analysis.classification_registry import (
    DEBT_RELIEF_ALIASES,
    LENDER_ALIASES,
    OWNER_NAMED_PAYEES,
    POTENTIAL_LENDER_ALIASES,
    REVIEW_FLAG_ENTITIES,
)
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction
from tests.flag_group_fixtures import txn

WEEKLY = (2, 9, 16, 23)


def _weekly_states(description: str) -> set[tuple[str, str]]:
    statement = Statement(bank="Fabricated Bank", transactions=[
        txn(f"2054-01-{day:02d}", description, -300.0) for day in WEEKLY])
    return {(record.classification, record.match_method) for record in classify_statement_transactions(statement)}


@pytest.mark.parametrize(
    ("printed", "entity"),
    [
        ("Paid To - Flexibility Capi Flexibilit Chk 0001", "Flexibility Capital, Inc."),
        ("MERIT BUSINESS FUNDING DES:ACH DEBIT ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", "Merit Business Funding"),
        ("Online Domestic Wire Transfer Via: Fab CU/123456789 A/C: Essentia Funding Sampletown NY 00001 US "
         "Imad: 0001 Trn: 0001", "Essentia Funding"),
    ],
)
def test_the_missing_funders_are_counted_lenders(printed, entity):
    record = classify_transaction(printed, -900.0)
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", entity)
    assert record.contributes_to_withholding_rate


MERIT_REVIEW = "Merit Business (probably Merit Business Funding)"


def test_merit_business_alone_is_a_review_alias_and_never_counted():
    # Owner decision 2026-09-28 (delegated; open question 11): MERIT BUSINESS, the Truist rows' printed originator, is
    # never an alias of the counted Merit Business Funding. It is the alias of a review entity of its own, so its rows
    # are named on the Potential Lenders tab and never enter lender math.
    assert "MERIT BUSINESS" not in LENDER_ALIASES["Merit Business Funding"]
    assert POTENTIAL_LENDER_ALIASES[MERIT_REVIEW] == ("MERIT BUSINESS",)
    assert MERIT_REVIEW not in REVIEW_FLAG_ENTITIES
    record = classify_transaction("ACH CORP DEBIT 0012345678 Merit Business Fab Widgets LLC CUSTOMER ID 0001", -900.0)
    assert (record.classification, record.canonical_entity, record.match_method) == (
        "potential_lender", MERIT_REVIEW, "candidate_lender_alias")
    assert record.review_required
    assert not record.contributes_to_withholding_rate and not record.contributes_to_lender_totals


def test_the_owner_named_funders_are_listed():
    labels = [label for label, _spelling in OWNER_NAMED_PAYEES["confirmed_lender"]]
    # Idea Financial (owner ruling 2026-09-28, tests/test_idea_financial.py) follows them, then Amerifi Capital (owner
    # ruling 2026-10-11, tests/test_amerifi_capital.py).
    assert labels[-5:-2] == ["Flexibility Capital", "Merit Business Funding", "Essentia Funding"]


def test_national_fundings_collection_vehicle_spelling_is_national_funding():
    # The alias is read from the registry: this file never writes the vehicle's digit.
    [alias] = [alias for alias in LENDER_ALIASES["NATIONAL FUNDING"] if alias.startswith("NFSPV")]
    record = classify_transaction(f"{alias.replace(' ', '')} EDI PYMNTS 0001 FAB HOLDER", -900.0)
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", "NATIONAL FUNDING")


@pytest.mark.parametrize(
    ("printed", "entity"),
    [
        ("RAM PMT 482913 0001", "RAM Payment LLC (Reliant)"),
        ("Electronic Withdrawal To RAM PAYMENTS", "RAM Payment LLC (Reliant)"),
        ("RAM PAYMENTS DES:RELIANT ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "RAM Payment LLC (Reliant)"),
        ("RAMPAYMENTS DES:PMT ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "RAM Payment LLC (Reliant)"),
        # a cheque payable to the processor: step 7b reads it before the cheque rule (the verifier's 'check'
        # expectation, updated for the flag design)
        ("Paid To - Ram Pmt Chk 1234", "RAM Payment LLC (Reliant)"),
        ("GLOBAL GHLLC.COM DES:FABPROGRAM ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "Global Holdings LLC"),
        ("Tayne Law Group", "Tayne Law Group"),
        ("FORTHPAY DES:DEPOSIT ID:0001 INDN:PAT EXAMPLE CO ID:0002 PPD", "Set Forth LLC (Forth Pay)"),
    ],
)
def test_the_debt_relief_payees_are_flagged_debt_relief(printed, entity):
    record = classify_transaction(printed, -300.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "debt_relief", entity, "debt_relief")


@pytest.mark.parametrize(
    ("printed", "state"),
    [
        # the debt-settlement verifier's negative controls: settlement words beside a funder or a law office, and
        # RAM Capital, never the RAM Payment processor
        ("FABRICATED FUNDING LLC DEBT SETTLEMENT", ("potential_lender", "recurring_fixed_debit")),
        ("FAB LAW GROUP DEBT SETTLEMENT", ("potential_lender", "recurring_fixed_debit")),
        ("LAW OFFICES OF PAT EXAMPLE", ("potential_lender", "recurring_fixed_debit")),
        ("ACH DEBIT RAM CAPITAL FUNDING", ("potential_lender", "recurring_financing_counterparty")),
        ("RAM CAPITAL", ("potential_lender", "recurring_fixed_debit")),
    ],
)
def test_settlement_words_and_ram_capital_are_never_debt_relief(printed, state):
    assert _weekly_states(printed) == {state}


def test_a_chase_ram_capital_originator_is_not_the_ram_payment_processor():
    record = classify_transaction(
        "Orig CO Name:Ram Capital Fundi Orig ID:0001 Desc Date: CO Entry Descr:Payment Sec:CCD Ind Name:Fab Holder",
        -300.0)
    assert record.classification == "potential_lender"


def test_resolve_capital_is_debt_relief_marked_unconfirmed():
    [entity] = [name for name in POTENTIAL_LENDER_ALIASES if name.startswith("Resolve Capital")]
    assert REVIEW_FLAG_ENTITIES[entity] == "debt_relief"
    record = classify_transaction(
        "Orig CO Name:Resolve Capital Orig ID:0001 Desc Date: CO Entry Descr:0001 Sec:CCD", -9000.0)
    assert (record.classification, record.review_required) == ("debt_relief", True)


def test_the_owner_named_debt_relief_payees_are_listed():
    assert [label for label, _spelling in OWNER_NAMED_PAYEES["debt_relief"]] == [
        "RAM Payments / Reliant", "Global Holdings", "Tayne Law Group"]


# --- Owner decisions 2026-09-28 (delegated; open question 14) ------------------------------------------------------


def test_delancey_street_is_read_by_its_full_name_only():
    # No card form DELANCEY STREET NEW YORK: a card purchase printing the merchant and the city keeps today's rules.
    assert DEBT_RELIEF_ALIASES["Delancey Street Debt Relief Inc"] == ("DELANCEY STREET DEBT RELIEF",)
    named = classify_transaction("DELANCEY STREET DEBT RELIEF DES:PAYMENT ID:0001 INDN:FAB HOLDER CO ID:0002 CCD",
                                 -300.0)
    assert (named.classification, named.canonical_entity) == ("debt_relief", "Delancey Street Debt Relief Inc")
    card = classify_transaction("Debit Card Purchase: 0105 PURCHASE 12 Delancey Street New York NY", -300.0)
    assert card.classification != "debt_relief" and card.flagged_group is None


def test_bare_forth_is_no_debt_relief_alias():
    assert all(alias != "FORTH" for aliases in DEBT_RELIEF_ALIASES.values() for alias in aliases)
    record = classify_transaction("Forth 0001 PPD ID: 0002", -300.0)
    assert record.classification != "debt_relief"


def test_an_escrow_refund_credit_keeps_todays_path():
    refund = classify_transaction("RAM PMT 482913 0001", 300.0)
    assert refund.classification != "debt_relief" and refund.flagged_group is None


def test_samson_servicing_is_named_on_the_potential_tab_only():
    record = classify_transaction("SAMSONSERVICING DES:ACHPAYMENT ID:0001 INDN:FAB HOLDER CO ID:0002 CCD", -900.0)
    assert record.classification == "potential_lender" and record.canonical_entity.startswith("Samson Servicing")
    assert not record.contributes_to_withholding_rate
