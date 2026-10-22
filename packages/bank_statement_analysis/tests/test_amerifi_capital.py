"""Owner ruling 2026-10-11: Amerifi Capital is a counted lender ("amerifi is a lender we count").

Amerifi Capital, LLC (a Connecticut LLC, Hartford CT, with its office in Aventura FL) is a direct merchant cash advance
funder that funds through ISO brokers; Virginia listed it among its sales-based financing providers in 2023 and 2024.
The owner's statement printed its daily debits as 'Electronic Withdrawal To AMERIFI CAPITAL', which read as a potential
lender (D6) before the ruling. The ledger admits it as a confirmed lender with the one alias AMERIFI CAPITAL (its r9
verify round upheld the alias and rejected bare AMERIFI, a broker's name, and the cut AMERIFI CAP, another registered
company's name). Its debits are paid to lenders, in the withholding rate and in the lender count; a row whose own words
say LOC or LINE OF CREDIT goes to Lines of credit (D9); its credits are financing proceeds (D1). Names that start the
same but are other businesses (AMERIFIRST, AMERIFIELD, AMERIFINANCIAL, AMERIFIX, AMERIFY, AMERIFACTORS) never read as
it: aliases are whole words, never a bare prefix.

Fabricated rows only (FABRIKAM LLC the holder; CONTOSO and NORTHWIND the merchants; the funder's public name; 2054
dates; neutral whole amounts).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from analysis import classification_registry as registry
from analysis.detect import detect
from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction

ROOT = Path(__file__).resolve().parent.parent
AMERIFI = "Amerifi Capital"
#: The entity's spellings since the owner's ruling, fixed here so the controls stay behavioural at any registry state.
AMERIFI_SPELLINGS = frozenset({"AMERIFI CAPITAL"})
#: The owner's statement's printed form (the bank's 'Electronic Withdrawal To <payee>' layout).
OWNER_FORM = "Electronic Withdrawal To AMERIFI CAPITAL"
HOLDER = "FABRIKAM LLC"
SALE = "CONTOSO MERCHANT SERVICES DEPOSIT FABRIKAM LLC"
PAYMENT = 500.0


def _business_days(count: int) -> list[str]:
    days, day = [], date(2054, 3, 2)
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day += timedelta(days=1)
    return days


def _statement(description: str, amount: float = -PAYMENT, count: int = 20) -> Statement:
    """A month of the owner's shape: one payee's row on each of `count` business days, and four weekly sales."""
    rows = [(day, description, amount) for day in _business_days(count)]
    rows += [(day, SALE, 12000.0) for day in ("2054-03-04", "2054-03-11", "2054-03-18", "2054-03-25")]
    transactions = [Transaction(date=day, description=text, amount=value,
                                direction="credit" if value > 0 else "debit") for day, text, value in sorted(rows)]
    return Statement(account_name=HOLDER, bank="Fabricated Bank", period_start="2054-03-01",
                     period_end="2054-03-31", transactions=transactions)


def test_amerifi_capital_is_a_counted_lender_with_its_one_alias():
    assert set(registry.LENDER_ALIASES[AMERIFI]) == AMERIFI_SPELLINGS
    holders = [(state, name) for state, entries in registry.PAYEE_GROUP_REGISTRIES.items()
               for name, aliases in entries.items() if "AMERIFI CAPITAL" in aliases]
    assert holders == [("confirmed_lender", AMERIFI)]
    assert AMERIFI not in registry.POTENTIAL_LENDER_ALIASES
    assert AMERIFI not in registry.LINE_OF_CREDIT_ALIASES
    assert "AMERIFI CAPITAL" not in registry.CREDIT_ONLY_ALIASES  # a debit-side alias, as every counted lender's
    # Bare AMERIFI is a funding broker's name (Amerifi, Broomall PA) and would read receivers; AMERIFI CAP is another
    # registered company's full name (AMERIFI CAP LLC); a cut form is added only when this funder's own rows print it.
    for table in (*registry.PAYEE_GROUP_REGISTRIES.values(), registry.POTENTIAL_LENDER_ALIASES):
        for aliases in table.values():
            assert not {"AMERIFI", "AMERIFI CAP", "AMERIFI CAPITA", "AMERIFICAP"} & set(aliases)


def test_amerifi_capital_is_owner_named_in_the_lender_group():
    assert ("Amerifi Capital", "AMERIFI CAPITAL") in registry.OWNER_NAMED_PAYEES["confirmed_lender"]


def test_the_ledger_records_the_verify_round_and_the_owner_ruling():
    ledger = json.loads((ROOT / "docs" / "lender-registry-ledger.json").read_text(encoding="utf-8"))
    [entry] = [entry for entry in ledger["entities"] if entry["entity"] == AMERIFI]
    assert (entry["group"], entry["status"], entry["business_type"], entry["aliases"]) == (
        "confirmed_lender", "admitted", "mca_or_revenue_based_funder", ["AMERIFI CAPITAL"])
    assert [verdict["round"] for verdict in entry["verdicts"]] == ["r1", "r9", "owner"]
    assert {"round": "owner", "verdict": "upheld", "confirmed": True} in entry["verdicts"]
    assert entry["notes"].startswith("Owner ruling 2026-10-11: Amerifi Capital is a counted lender")
    assert all(other["entity"] == AMERIFI for other in ledger["entities"] if "AMERIFI CAPITAL" in other["aliases"])


def test_the_owner_s_daily_debits_are_counted_amerifi_capital_payments():
    statement = _statement(OWNER_FORM)
    records = classify_statement_transactions(statement)
    debits = [record for record in records if record.amount < 0]
    assert len(debits) == 20
    assert {(record.classification, record.canonical_entity, record.match_method, record.matched_alias)
            for record in debits} == {("confirmed_lender", AMERIFI, "verified_lender_alias", "AMERIFI CAPITAL")}
    assert all(record.contributes_to_lender_totals and record.contributes_to_withholding_rate for record in debits)
    assert all(record.contributes_to_lender_count for record in debits)
    assert not any(record.contributes_to_potential_lender_totals or record.contributes_to_potential_lender_count
                   for record in debits)
    assert all(record.flagged_group is None for record in debits)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lenders_detected, metrics.potential_lenders_detected) == (1, 0)
    assert (metrics.lender_debits, metrics.withholding_numerator) == (20 * PAYMENT, 20 * PAYMENT)
    [funder] = detect(statement, classifications=records).known_funders
    assert (funder.funder, funder.debit_count, funder.total_debited) == (AMERIFI, 20, 20 * PAYMENT)


@pytest.mark.parametrize(
    "printed",
    [
        OWNER_FORM,
        # another bank's company-name field, and a receiver after it
        "AMERIFI CAPITAL DES:PAYMENT ID:0001 INDN:FABRIKAM LLC CO ID:0002 CCD",
        "ORIG CO NAME:AMERIFI CAPITAL ORIG ID:0001 DESC DATE: CO ENTRY DESCR:PAYMENT SEC:CCD IND NAME:FABRIKAM LLC",
        # the legal form after the name, and the name run together
        "ACH DEBIT AMERIFI CAPITAL LLC FABRIKAM LLC",
        "ACH DEBIT AMERIFICAPITAL FABRIKAM LLC",
        # an originator id glued to the name's last word
        "AMERIFI CAPITAL0001 DES:PAYMENT ID:0002 INDN:FABRIKAM LLC CO ID:0003 CCD",
    ],
)
def test_every_printed_form_is_a_counted_amerifi_capital_debit(printed):
    record = classify_transaction(printed, -PAYMENT)
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", AMERIFI)
    assert record.matched_alias in AMERIFI_SPELLINGS
    assert record.contributes_to_lender_totals and record.contributes_to_withholding_rate
    assert record.contributes_to_lender_count
    assert record.flagged_group is None


@pytest.mark.parametrize(
    "printed",
    [
        "AMERIFI CAPITAL LOC PAYMENT FABRIKAM LLC",
        "Electronic Withdrawal To AMERIFI CAPITAL LINE OF CREDIT",
    ],
)
def test_a_row_that_says_loc_or_line_of_credit_stays_a_line_of_credit(printed):
    # D9: a descriptor that says LOC or LINE OF CREDIT puts the row in Lines of credit, even when the payee is a lender.
    records = [record for record in classify_statement_transactions(_statement(printed)) if record.amount < 0]
    assert {(record.classification, record.canonical_entity, record.matched_rule) for record in records} == {
        ("line_of_credit", AMERIFI, "line_of_credit_descriptor_override")}
    assert not any(record.contributes_to_withholding_rate for record in records)
    assert not any(record.contributes_to_lender_totals for record in records)


@pytest.mark.parametrize(
    "printed",
    [
        "Electronic Deposit From AMERIFI CAPITAL",
        "WIRE TRANSFER CREDIT FROM AMERIFI CAPITAL LLC REF 0001",
        "ORIG CO NAME:AMERIFI CAPITAL ORIG ID:0001 DESC DATE: CO ENTRY DESCR:FUNDING SEC:CCD IND NAME:FABRIKAM LLC",
        "ACH CREDIT AMERIFICAPITAL0001 FABRIKAM LLC",
    ],
)
def test_an_amerifi_capital_credit_is_financing_proceeds(printed):
    # D1: a counted lender's credit (the advance's funding) is financing proceeds, never an eligible deposit.
    record = classify_transaction(printed, 25000.0)
    assert (record.classification, record.canonical_entity) == ("other", AMERIFI)
    assert (record.match_method, record.matched_rule) == ("financing_proceeds_credit", "financing_proceeds_credit")
    assert record.contributes_to_lender_credit_exclusion
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("non_revenue", AMERIFI)
    assert record.flagged_group is None


@pytest.mark.parametrize(
    ("printed", "amount"),
    [
        # other companies whose names start the same (other tokens: aliases are whole words)
        ("Electronic Withdrawal To AMERIFIRST BANK", -PAYMENT),
        ("ACH DEBIT AMERIFIRST FINANCIAL FABRIKAM LLC", -PAYMENT),
        ("ACH DEBIT AMERI FIRST FINANCIAL FABRIKAM LLC", -PAYMENT),
        ("ACH DEBIT AMERIFIRST CAPITAL CORP FABRIKAM LLC", -PAYMENT),
        ("ACH CREDIT AMERIFIRST FINANCIAL FABRIKAM LLC", 2500.0),
        ("Electronic Withdrawal To AMERIFY CAPITAL", -PAYMENT),
        ("ACH CREDIT AMERIFY CAPITAL FABRIKAM LLC", 2500.0),
        ("ACH DEBIT AMERIFINANCIAL SOLUTIONS FABRIKAM LLC", -PAYMENT),
        ("ACH CREDIT AMERIFINANCIAL SOLUTIONS FABRIKAM LLC", 2500.0),
        ("AMERIFIELD JV LLC PAYMENT NORTHWIND", -PAYMENT),
        ("AMERIFIX LLC PURCHASE CONTOSO", -PAYMENT),
        # names that share the word AMERIFI but are not this funder's (a broker, other registered companies)
        ("Electronic Withdrawal To AMERIFI LLC", -PAYMENT),
        ("ACH CREDIT AMERIFI LLC COMMISSION FABRIKAM LLC", 2500.0),
        ("Electronic Withdrawal To AMERIFI CAP LLC", -PAYMENT),
        ("Electronic Withdrawal To AMERIFI FUNDING LLC", -PAYMENT),
        # a split name, a longer word than CAPITAL, and a glued prefix
        ("ACH DEBIT AMERI FI CAPITAL FABRIKAM LLC", -PAYMENT),
        ("ACH DEBIT AMERIFI CAPITALIZATION FABRIKAM LLC", -PAYMENT),
        ("ACH DEBIT TOAMERIFI CAPITAL FABRIKAM LLC", -PAYMENT),
    ],
)
def test_other_ameri_names_are_never_amerifi_capital(printed, amount):
    records = classify_statement_transactions(_statement(printed, amount))
    assert all(record.canonical_entity != AMERIFI for record in records)
    assert all(record.revenue_canonical_entity != AMERIFI for record in records)
    assert all(record.matched_alias not in AMERIFI_SPELLINGS for record in records)
    assert not any(record.classification == "confirmed_lender" for record in records)


def test_an_amerifactors_credit_stays_factoring():
    # AmeriFactors is the only corpus word that starts AMERIF: a factor's credit, its own entity, never Amerifi Capital.
    record = classify_transaction(
        "ORIG CO NAME:AMERIFACTORS FIN ORIG ID:0001 DESC DATE: CO ENTRY DESCR:CASH DISB SEC:CCD IND NAME:FABRIKAM LLC",
        2500.0)
    assert record.classification == "factoring"
    assert record.canonical_entity != AMERIFI and record.matched_alias not in AMERIFI_SPELLINGS
