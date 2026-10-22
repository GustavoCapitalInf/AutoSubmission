"""5.3 (2026-09-27): the D11 naming fixes: organisation cues by position, the legal-form cut, trailing connectors,
bank template prefixes, Truist's company field, wire beneficiaries and the printed 'NAME, CITY, ST' line.
Fabricated descriptors only, in each bank's printed format."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.schema import Statement
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.classification.payees import _canonical_unknown_entity, _unknown_payee_tokens
from analysis.classification.record import UNIDENTIFIED_LENDER_OBLIGATION as UNIDENTIFIED
from tests.flag_group_fixtures import txn

WEEKLY = ("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26")


def _name(printed: str) -> str | None:
    return _canonical_unknown_entity(normalize(printed))


# --- C5: cues by position, the legal-form cut, connectors, PAID and a leading AND --------------------------------

@pytest.mark.parametrize(
    ("printed", "name"),
    [
        # a legal form printed first is no cue; a name made only of cue words names no one
        ("ACH DEBIT CORP FABRIKAM CONSULT 0001", UNIDENTIFIED),
        ("BANK DEBIT", UNIDENTIFIED),
        # CO is Colorado's state code, never a cue (COMPANY stays one)
        ("Electronic Withdrawal To CO FAM SUPP REG", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED TRADING CO 0001", UNIDENTIFIED),
        ("ACH DEBIT FABRICATED TRADING COMPANY 0001", "Fabricated Trading Company"),
        # the name ends at its first legal form after the first word
        ("FAB REVIEW INC PURCHASE", "Fab Review Inc"),
        ("ACH DEBIT FABRIKAM WIDGETS LLC INVOICES 0001", "Fabrikam Widgets LLC"),
        # a connector left by the four-word cap is dropped
        ("ACH DEBIT FABRIKAM NATIONAL A BANK OF OKLAHOMA 0001", "Fabrikam National Bank"),
        ("ACH DEBIT AND FAB FUNDING LLC", "Fab Funding LLC"),
        # multi-cue names keep every word up to the legal form
        ("ACH DEBIT FABRIKAM CAPITAL FUNDING LLC 0001", "Fabrikam Capital Funding LLC"),
    ],
)
def test_the_cue_rules_and_the_legal_form_cut(printed, name):
    assert _name(printed) == name


def test_paid_is_a_channel_word_not_part_of_the_payee():
    assert _unknown_payee_tokens(normalize("PAID TO - FAB CAPITAL GROUP 0001")) == ("FAB", "CAPITAL", "GROUP")


# --- C6: bank template prefixes and Truist's company field ----------------------------------------------------------

@pytest.mark.parametrize(
    ("printed", "payee"),
    [
        ("PMNT SENT 0105 FAB RECIPIENT ONE", ("FAB", "RECIPIENT", "ONE")),
        ("Payment Sent 01/05 Fab Funding LLC Card 1234", ("FAB", "FUNDING", "LLC")),
        ("Corporate ACH Payment Fab Capital LLC", ("FAB", "CAPITAL", "LLC")),
        ("HIP Credit SENT to Fab Advance LLC", ("FAB", "ADVANCE", "LLC")),
        ("DOMESTIC ASSIST WIRE FAB HOLDINGS LLC", ("FAB", "HOLDINGS", "LLC")),
        ("DBCRD PUR AP, AUT 010554 VISA DDA PUR AP 123456 FAB MART MIAMI FL", ("FAB", "MART", "MIAMI", "FL")),
    ],
)
def test_a_bank_template_prefix_never_names_the_payee(printed, payee):
    assert _unknown_payee_tokens(normalize(printed)) == payee


def test_two_recipients_of_one_template_are_two_payees():
    # FUNDING keeps both off the p2p rail (A2's veto), so only the payee key decides.
    statement = Statement(bank="Fabricated Bank", transactions=[
        *(txn(day, "PMNT SENT 0105 FAB FUNDING ONE", -300.0) for day in WEEKLY[:2]),
        *(txn(day, "PMNT SENT 0105 FAB FUNDING TWO", -300.0) for day in WEEKLY[2:]),
    ])
    records = classify_statement_transactions(statement)
    assert {record.classification for record in records} == {"other"}


@pytest.mark.parametrize(
    ("printed", "name"),
    [
        ("ACH CORP DEBIT SQ540512 SQUARE INC FAB YOGA STUDIO LL CUSTOMER ID 0001", "Square Inc"),
        ("ACH CORP DEBIT KAPIFAB LLC FAB HOLDER CUSTOMER ID 0001", "Kapifab LLC"),
        # a short originator lets the receiver's words into the 16-character field: no name is published
        ("ACH CORP DEBIT DEBIT FABPAY CAPITAL GROWTH LLC CUSTOMER ID 0001", UNIDENTIFIED),
        ("ACH CORP DEBIT 0012345678 FAB BUSINESS FABCO WIDGETS LLC CUSTOMER ID 0001", UNIDENTIFIED),
        ("ACH CORP DEBIT LOAN PMT FABRIKAM EXPRESS FAB HOLDER CUSTOMER ID 0001", UNIDENTIFIED),
    ],
)
def test_a_truist_name_is_published_only_through_its_company_field(printed, name):
    assert _name(printed) == name


# --- C7: wire beneficiaries ---------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("printed", "name"),
    [
        ("WT Fed#01R23 Fab Bank /Ftr/Bnf=Fab Advance Group LLC Srf# 0001 Trn#0001 Rfb# 0001", "Fab Advance"),
        ("WIRE TYPE:WIRE OUT DATE:540105 TIME:1200 ET TRN:0001 SERVICE REF:0001 BNF:FAB FUNDING LLC ID:0001",
         "Fab Funding"),
        ("Online Domestic Wire Transfer Via: Fab CU/123456789 A/C: Fab Funding Sampletown NY 00001 US Ref: Loan "
         "Imad: 0001 Trn: 0001", "Fab Funding"),
        # a person beneficiary, anywhere, is never published
        ("WT Fed#01R23 Fab Bank /Ftr/Bnf=Pat Example Srf# 0001", UNIDENTIFIED),
        ("Online Domestic Wire Transfer Via: Fab CU/123456789 A/C: Pat Example Denver CO 00002 US Ref: Rent "
         "Imad: 0001 Trn: 0001", UNIDENTIFIED),
    ],
)
def test_a_wire_is_named_by_its_beneficiary(printed, name):
    assert _name(printed) == name


def test_two_beneficiaries_of_one_wire_format_are_two_payees():
    statement = Statement(bank="Wells Fargo", transactions=[
        *(txn(day, "WT Fed#01R23 Fab Bank /Ftr/Bnf=Fab One LLC Srf# 0001", -900.0) for day in WEEKLY[:2]),
        *(txn(day, "WT Fed#01R23 Fab Bank /Ftr/Bnf=Fab Two LLC Srf# 0001", -900.0) for day in WEEKLY[2:]),
    ])
    assert {record.classification for record in classify_statement_transactions(statement)} == {"other"}


# --- C8: the printed 'NAME, CITY, ST' line ----------------------------------------------------------------------------

def test_a_card_networks_city_never_joins_the_d6_name():
    statement = Statement(bank="Bluevine", transactions=[
        txn(day, "FAB CARRIER SERVICES, OVERLAND PARK, KS", -700.0) for day in WEEKLY
    ])
    records = classify_statement_transactions(statement)
    assert {(record.classification, record.canonical_entity) for record in records} == {
        ("potential_lender", "Fab Carrier Services")}
