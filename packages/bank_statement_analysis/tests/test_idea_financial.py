"""Owner ruling 2026-09-28: Idea Financial (Idea 247, Inc.) is a counted lender, no longer a line of credit.

A row whose own words say LOC or LINE OF CREDIT still goes to Lines of credit (D9), and its credits are financing
proceeds (D1). Fabricated descriptors in each bank's layout; the payee names are the registry's business names.
"""
from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from analysis.schema import Statement
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction
from tests.flag_group_fixtures import txn

IDEA = "IDEA FINANCIAL"
#: The entity's spellings since the owner's ruling, fixed here so the controls stay behavioural at any registry state.
IDEA_SPELLINGS = frozenset({"IDEA FINANCIAL", "IDEAFINANCIAL", "IDEALOAN", "IDEA 247 INC"})
WEEKLY = (2, 9, 16, 23)

#: The tryout host's Wells Fargo business-to-business layout: '<company name> <entry description> <date>
#: <individual ID> <receiver>'. The company name is the legal name Idea 247 Inc and the entry description IDEALOAN.
WF_B2B = "< Business to Business ACH Debit - Idea 247 Inc Idealoan 540105 L-00000001 Fab Holder Co"


def _weekly(description: str, amount: float = -300.0):
    statement = Statement(bank="Fabricated Bank", transactions=[
        txn(f"2054-01-{day:02d}", description, amount) for day in WEEKLY])
    return classify_statement_transactions(statement)


def test_idea_financial_is_a_counted_lender_with_its_printed_spellings():
    assert set(registry.LENDER_ALIASES[IDEA]) == IDEA_SPELLINGS
    assert IDEA not in registry.LINE_OF_CREDIT_ALIASES
    assert IDEA not in registry.POTENTIAL_LENDER_ALIASES
    # Bare IDEA is an English word: it would read receivers and other companies' names, so it is never an alias.
    for table in registry.PAYEE_GROUP_REGISTRIES.values():
        for aliases in table.values():
            assert "IDEA" not in aliases


def test_idea_financial_is_owner_named_in_the_lender_group():
    assert ("Idea Financial", IDEA) in registry.OWNER_NAMED_PAYEES["confirmed_lender"]
    assert all(spelling != IDEA for _label, spelling in registry.OWNER_NAMED_PAYEES["line_of_credit"])


def test_the_wells_fargo_weekly_debit_is_a_counted_idea_financial_row():
    records = _weekly(WF_B2B)
    assert {(record.classification, record.canonical_entity, record.match_method) for record in records} == {
        ("confirmed_lender", IDEA, "verified_lender_alias")}
    assert all(record.contributes_to_withholding_rate for record in records)
    assert all(record.contributes_to_lender_totals for record in records)
    # The legal name is the longest alias the row prints.
    assert {record.matched_alias for record in records} == {"IDEA 247 INC"}


@pytest.mark.parametrize(
    ("printed", "alias"),
    [
        # The dump the rows were seen in masks the originator's digits: the entry description reaches them anyway.
        ("< Business to Business ACH Debit - Idea 000 Inc Idealoan 540112 L-00000001 Fab Holder Co", "IDEALOAN"),
        ("Business to Business ACH Debit - Idea 247 Inc Idealoan 540112 L-00000001 Fab Holder Co", "IDEA 247 INC"),
        # a layout that prints the entry description first, or alone
        ("ACH CORP DEBIT IDEALOAN FAB HOLDER CO CUSTOMER ID L00000001", "IDEALOAN"),
        # another bank's company-name field
        ("IDEA 247 INC DES:PAYMENT ID:L-00000001 INDN:FAB HOLDER CO CO ID:0001 CCD", "IDEA 247 INC"),
        ("Orig CO Name:Idea 247 Inc Orig ID:0001 Desc Date:540105 CO Entry Descr:Idealoan Sec:CCD", "IDEA 247 INC"),
        # the two spellings the registry held before the ruling
        ("IDEA FINANCIAL PAYMENT 0001", "IDEA FINANCIAL"),
        ("IDEAFINANCIAL ACH DEBIT 0001", "IDEAFINANCIAL"),
    ],
)
def test_every_printed_form_is_a_counted_idea_financial_debit(printed, alias):
    record = classify_transaction(printed, -900.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == ("confirmed_lender", IDEA, alias)
    assert record.contributes_to_withholding_rate
    assert record.flagged_group is None


@pytest.mark.parametrize(
    "printed",
    [
        "IDEA 247 INC DES:LOC PMT ID:L-00000001 INDN:FAB HOLDER CO CO ID:0001 CCD",
        "IDEA FINANCIAL LINE OF CREDIT PAYMENT 0001",
        "< Business to Business ACH Debit - Idea 247 Inc Loc Pmt 540105 L-00000001 Fab Holder Co",
    ],
)
def test_a_row_that_says_loc_or_line_of_credit_stays_a_line_of_credit(printed):
    # D9: a descriptor that says LOC or LINE OF CREDIT puts the row in Lines of credit, even when the payee is a lender.
    records = _weekly(printed)
    assert {(record.classification, record.canonical_entity, record.matched_rule) for record in records} == {
        ("line_of_credit", IDEA, "line_of_credit_descriptor_override")}
    assert not any(record.contributes_to_withholding_rate for record in records)
    assert not any(record.contributes_to_lender_totals for record in records)


def test_the_loan_number_is_no_loc_wording():
    # 'L-' before the loan number never reads as LOC.
    record = classify_transaction("IDEA 247 INC DES:PAYMENT ID:L-00000001 INDN:FAB HOLDER CO CO ID:0001 CCD", -900.0)
    assert record.matched_rule != "line_of_credit_descriptor_override"
    assert record.classification == "confirmed_lender"


@pytest.mark.parametrize(
    "printed",
    [
        "Business to Business ACH Credit - Idea 247 Inc Loan Fund 540105 L-00000001 Fab Holder Co",
        "IDEA FINANCIAL DEPOSIT 0001",
        "IDEALOAN FUNDING 0001",
    ],
)
def test_an_idea_financial_credit_is_financing_proceeds(printed):
    # D1: a counted lender's credit (the loan's funding, a draw) is financing proceeds, never an eligible deposit.
    record = classify_transaction(printed, 5000.0)
    assert (record.classification, record.canonical_entity) == ("other", IDEA)
    assert (record.match_method, record.matched_rule) == ("financing_proceeds_credit", "financing_proceeds_credit")
    assert record.contributes_to_lender_credit_exclusion
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_canonical_entity == IDEA
    assert record.flagged_group is None


@pytest.mark.parametrize(
    ("printed", "amount"),
    [
        ("Orig CO Name:Ideal Fab Supply Orig ID:0001 Desc Date: CO Entry Descr:Payment Sec:CCD", -300.0),
        ("Purchase authorized on 01/02 Ideal Fab Tire Shop Sampletown ST S0001 Card 0001", -300.0),
        ("BRIGHT IDEAS FAB LLC PAYMENT 0001", -300.0),
        ("FINANCIAL IDEA LOAN FAB PAYMENT 0001", -300.0),
        ("IDEAL LOAN FAB PAYMENT 0001", -300.0),
        # a receiver (the account holder) named Idea ... on another originator's debit
        ("Orig CO Name:Fab Widget Co Orig ID:0001 Desc Date: CO Entry Descr:Payment Sec:CCD Ind ID:0001 "
         "Ind Name:Idea Fab Studio LLC", -300.0),
        ("IDEA FAB STUDIO LLC DEPOSIT 0001", 900.0),
        ("Orig CO Name:The Ideal Fab Co Orig ID:0001 Desc Date: CO Entry Descr:ACH Pmt Sec:CCD", 900.0),
    ],
)
def test_other_idea_words_are_not_idea_financial(printed, amount):
    records = _weekly(printed, amount)
    assert all(record.canonical_entity != IDEA for record in records)
    assert all(record.matched_alias not in IDEA_SPELLINGS for record in records)
    assert not any(record.match_method == "financing_proceeds_credit" for record in records)
