"""5.3 (owner ruling 2026-09-27): the registry entries the false-positive hunt added, in their printed forms.
Fabricated descriptors in each bank's layout; the payee names are the registry's business names."""
from __future__ import annotations

import pytest

from analysis.classification_registry import (
    LENDER_ALIASES,
    OWNER_NAMED_PAYEES,
    POTENTIAL_LENDER_ALIASES,
    REVIEW_FLAG_ENTITIES,
)
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
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
    assert labels[-3:] == ["Flexibility Capital", "Merit Business Funding", "Essentia Funding"]


def test_national_fundings_collection_vehicle_spelling_is_national_funding():
    # The alias is read from the registry: this file never writes the vehicle's digit.
    [alias] = [alias for alias in LENDER_ALIASES["NATIONAL FUNDING"] if alias.startswith("NFSPV")]
    record = classify_transaction(f"{alias.replace(' ', '')} EDI PYMNTS 0001 FAB HOLDER", -900.0)
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", "NATIONAL FUNDING")
