"""Audit round 3, R3-B01 (R3-26): ODKRAOD is an OnDeck spelling (the orchestrator's sign-off under the owner's delegation
of lender-ledger conflicts, 2026-09-25, and of G7 gates, 2026-09-29; recorded 2026-10-07).

Research round 4 left the ACH originator ODKRAOD unresolved and the ledger rejected it. Three independent verifiers of
the round-3 audit found every ODKRAOD debit of the cached corpus at the cents of the same account's ONDECK payment, on a
missed week of its weekly beat, at three unrelated banks, with an ACH entry counter in the ONDECK sequence; ODK Capital,
LLC is OnDeck's lending entity. The ledger's ONDECK record gains the alias and the rejected record is removed (contract
C10: one alias, one entity), so an ODKRAOD debit is an OnDeck payment (paid to lenders, the withholding numerator, the
payment series) and an ODKRAOD credit is OnDeck's funding (D1).

Fabricated rows only (CONTOSO TILE LLC; FABRIKAM SUPPLY INC sales; ONDECK CAPITAL, a public funder of the registry; 2054
dates; neutral whole amounts)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis import classification_registry as registry
from analysis import transaction_classifier as tc
from analysis.transaction_classifier import row
from analysis.detect import detect
from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction

ROOT = Path(__file__).resolve().parent.parent
HOLDER = "CONTOSO TILE LLC"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO TILE LLC CO ID:0000000001 CCD"
ONDECK_ROW = "ONDECK CAPITAL 1 DES:00000 ID:0000000001 INDN:CONTOSO TILE LLC CO ID:0000000002 CCD"
ODKRAOD_ROW = "ODKRAOD 00000"


def test_odkraod_is_an_ondeck_alias_and_no_other_entity_s():
    assert "ODKRAOD" in registry.LENDER_ALIASES["ONDECK"]
    holders = [(state, name) for state, entries in registry.PAYEE_GROUP_REGISTRIES.items()
               for name, aliases in entries.items() if "ODKRAOD" in aliases]
    assert holders == [("confirmed_lender", "ONDECK")]
    assert all("ODKRAOD" not in aliases for aliases in registry.POTENTIAL_LENDER_ALIASES.values())
    assert "ODKRAOD" not in registry.CREDIT_ONLY_ALIASES  # a debit-side alias (G7-admitted for exactly this move)


def test_the_ledger_holds_odkraod_once_under_ondeck_with_its_round_3_verdict():
    ledger = json.loads((ROOT / "docs" / "lender-registry-ledger.json").read_text(encoding="utf-8"))
    holders = [entry for entry in ledger["entities"] if "ODKRAOD" in entry["aliases"]]
    assert [(entry["entity"], entry["group"], entry["status"]) for entry in holders] == [
        ("ONDECK", "confirmed_lender", "admitted")]
    assert all(entry["entity"] != "ODKRAOD" for entry in ledger["entities"])
    [ondeck] = holders
    assert {"round": "audit-r3", "verdict": "upheld", "confirmed": True} in ondeck["verdicts"]
    assert "audit round 3, R3-26" in ondeck["notes"]


@pytest.mark.parametrize(
    ("printed", "bank"),
    [
        ("ORIG CO NAME:ODKRAOD ORIG ID:0000000000 DESC DATE: CO ENTRY DESCR:00000 SEC:CCD TRACE#:1 "
         "IND NAME:CONTOSO TILE LLC", "JPMorgan Chase"),
        ("ODKRAOD DES:00000 ID:0000000001 INDN:CONTOSO TILE LLC CO ID:0000000002 CCD", "Bank of America"),
        (ODKRAOD_ROW, "Bank of America"),
    ],
)
def test_an_odkraod_debit_is_a_counted_ondeck_payment(printed, bank):
    record = row.classify_transaction(printed, -550.0, bank=bank)
    assert (record.classification, record.canonical_entity, record.matched_alias) == (
        "confirmed_lender", "ONDECK", "ODKRAOD")
    assert record.contributes_to_lender_totals and record.contributes_to_withholding_rate
    assert record.contributes_to_lender_count
    assert record.flagged_group is None


def _statement(rows) -> Statement:
    transactions = [Transaction(date=day, description=text, amount=amount,
                                direction="credit" if amount > 0 else "debit") for day, text, amount in rows]
    return Statement(account_name=HOLDER, bank="Bank of America", period_start="2054-02-01",
                     period_end="2054-02-28", transactions=transactions)


def test_a_statement_reads_the_odkraod_weeks_as_ondeck_payments():
    # ONDECK's weekly beat on Thursdays: the two middle weeks print ODKRAOD (today out of paid: 2,000.00).
    statement = _statement([
        ("2054-02-02", SALE, 12000.0), ("2054-02-05", ONDECK_ROW, -1000.0), ("2054-02-12", ODKRAOD_ROW, -1000.0),
        ("2054-02-16", SALE, 12000.0), ("2054-02-19", ODKRAOD_ROW, -1000.0), ("2054-02-26", ONDECK_ROW, -1000.0)])
    records = tc.classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lender_debits, metrics.withholding_numerator, metrics.lenders_detected) == (4000.0, 4000.0, 1)
    assert metrics.true_revenue_total == 24000.0
    [funder] = detect(statement, classifications=records).known_funders
    assert (funder.funder, funder.debit_count, funder.total_debited) == ("ONDECK", 4, 4000.0)


def test_an_odkraod_credit_is_ondeck_s_funding():
    record = row.classify_transaction("ODKRAOD FUNDING 00000", 25000.0)
    assert (record.classification, record.canonical_entity) == ("other", "ONDECK")
    assert (record.match_method, record.matched_rule) == ("financing_proceeds_credit", "financing_proceeds_credit")
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("non_revenue", "ONDECK")
    assert record.contributes_to_lender_credit_exclusion


def test_an_odkraod_row_printing_a_stop_or_charge_word_is_a_charge():
    # Audit round 3, R3-80: the bank's charge naming a funder is a charge, for ODKRAOD as for every funder.
    for printed in ("STOP PAYMENT ODKRAOD", "STOP PAYMENT CHARGE ODKRAOD"):
        record = row.classify_transaction(printed, -35.0)
        assert (record.classification, record.canonical_entity) == ("fee", None)
