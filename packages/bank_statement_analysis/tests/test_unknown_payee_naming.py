from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction
from tests.flag_group_fixtures import txn

UNIDENTIFIED = "Unidentified lender obligation"


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("WEB PMT NORTHSTAR FINANCE INDN:PAT EXAMPLE CO ID:0000 CCD", "Northstar Finance"),
        (
            "ORIG CO NAME:NORTHSTAR FINANCE ORIG ID:0000 DESC DATE:0101 CO ENTRY DESCR:PAYMENT "
            "SEC:CCD TRACE#:0000 EED:0101 IND ID:0000 IND NAME:PAT EXAMPLE",
            "Northstar Finance",
        ),
        ("NORTHSTAR FINANCE DES:PAYMENT ID:XXXX0000 INDN:PAT EXAMPLE CO ID:0000 CCD", "Northstar Finance"),
        ("NORTHSTAR FINANCE PAYMENT 0101 0000000 PAT EXAMPLE", "Northstar Finance"),
        ("ACH DEBIT FABRICATED FUNDING LLC", "Fabricated Funding LLC"),
        ("ACH PMT PAT EXAMPLE FAMILY LOAN", UNIDENTIFIED),
        ("ADVANCE PAT EXAMPLE PMT", UNIDENTIFIED),
    ],
)
def test_a_financing_keyword_row_is_named_from_organisation_words_only(description, entity):
    record = classify_transaction(description, -90.0)
    assert record.classification == "other"
    assert record.match_method == "financing_keyword_review"
    assert record.canonical_entity == entity


@pytest.mark.parametrize(
    "description",
    [
        "LOAN PAYMENT PAT EXAMPLE",
        "WITHDRAWAL ADVANCE PAYMENT PAT EXAMPLE 0000",
        "DEBIT MEMO FUNDING PMT PAT EXAMPLE",
    ],
)
def test_a_repayment_to_an_unknown_person_is_never_named_after_them(description):
    record = classify_transaction(description, -90.0)
    assert record.classification == "potential_lender"
    assert record.canonical_entity == UNIDENTIFIED


def test_generic_financing_words_alone_name_no_payee():
    record = classify_transaction("ACH Debit Funder 0102", -450.0)
    assert record.match_method == "financing_keyword_review"
    assert record.canonical_entity is None


def test_a_financing_payee_keeps_one_name_across_dated_descriptors():
    statement = Statement(
        transactions=[
            txn(f"2054-01-{day:02d}", f"NORTHSTAR FINANCE PAYMENT JAN {day}", -90.0)
            for day in (5, 6, 7, 8, 9)
        ]
    )
    records = classify_statement_transactions(statement)
    assert {record.canonical_entity for record in records} == {"Northstar Finance"}
    assert {record.classification for record in records} == {"potential_lender"}


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("ACH DEBIT FABRICATED CAPITAL EQUIPMENT FINANCE", "Fabricated Capital"),
        ("ACH DEBIT FABRICATED EQUIPMENT FINANCE", UNIDENTIFIED),
    ],
)
def test_unnamed_equipment_financing_keeps_only_an_organisation_name(description, entity):
    record = classify_transaction(description, -600.0)
    assert record.match_method == "unnamed_equipment_financing"
    assert record.canonical_entity == entity


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("ACH DEBIT FABRICATED LOAN SERVICING", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED SERVICER LLC", "Fabricated Servicer LLC"),
        ("FABRICATED DEBT COLLECTORS INC", "Fabricated Debt Collectors Inc"),
        # Owner decision 2026-09-25: an MCA servicing company whose funder is not named.
        # 5.3 (2026-09-27): its fixed D10 label, because the words print for two unrelated funders.
        ("ACH DEBIT MCA SERVICING 0001", "MCA servicer (funder not identified)"),
    ],
)
def test_an_unknown_servicer_or_collector_is_a_potential_lender(description, entity):
    record = classify_transaction(description, -250.0)
    assert record.classification == "potential_lender"
    assert record.match_method == "unknown_servicer_or_collector"
    assert record.canonical_entity == entity
    assert record.review_required
    assert not record.contributes_to_withholding_rate


@pytest.mark.parametrize("description", ["LOAN PAYMENT", "LOAN PAYMENT BR 0001", "COMPTE DIVERS LOAN PAYMENT 0001"])
def test_a_loan_payment_that_names_no_payee_is_the_statement_banks_loan(description):
    """Owner decision 2026-09-25 (D5): a LOAN PAYMENT with no lender printed is the statement
    bank's own loan, not a potential lender."""
    named = classify_transaction(description, -500.0, bank="Fabricated Bank")
    unnamed = classify_transaction(description, -500.0)
    assert (named.classification, named.canonical_entity, named.matched_rule) == (
        "bank_loan",
        "Fabricated Bank",
        "unnamed_loan_payment",
    )
    assert (unnamed.classification, unnamed.canonical_entity) == ("bank_loan", None)
    assert named.flagged_group == "bank_loans"
    assert not named.review_required
    assert not named.contributes_to_potential_lender_totals


def test_a_loan_payment_that_prints_a_payee_keeps_the_potential_rules():
    # LOAN PAYMENT PAT EXAMPLE (a person) stays potential too: see the repayment test above.
    assert classify_transaction("LOAN PAYMENT NORTHSTAR FINANCE 0001", -500.0).classification == "potential_lender"
