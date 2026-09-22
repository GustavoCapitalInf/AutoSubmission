"""Owner ruling, 2026-09-22: the NSF count defaults to printed days; carrying a balance over inactive days is
an option. Fabricated figures only."""
from copy import deepcopy

from analysis.adb import DailyBalance
from analysis.metrics import compute_metrics
from analysis.nsf_days import (CARRIED, PRINTED, UNAVAILABLE, apply_nsf_basis, apply_nsf_basis_to_payload,
                               negative_day_count)
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from analysis.serialization import _metrics_dict


def _ledger():
    # The owner's example: the 10th ends -10, nothing posts on the 11th, the 12th ends +20.
    return [DailyBalance("2054-03-10", -10.0, "reconstructed", 1),
            DailyBalance("2054-03-11", -10.0, "carried", 0),
            DailyBalance("2054-03-12", 20.0, "reconstructed", 1)]


def test_the_owners_example_is_one_printed_day_and_two_carried_days():
    assert negative_day_count(_ledger(), carry_over=False) == 1
    assert negative_day_count(_ledger(), carry_over=True) == 2


def test_a_day_the_bank_printed_in_its_daily_balance_table_is_a_printed_day():
    ledger = [DailyBalance("2054-03-11", -10.0, "bank_daily_summary", 0)]
    assert negative_day_count(ledger, carry_over=False) == 1


def test_serialized_ledger_entries_count_the_same_way():
    ledger = [{"date": d.date, "ending_balance": d.ending_balance, "source": d.source} for d in _ledger()]
    assert negative_day_count(ledger, carry_over=False) == 1
    assert negative_day_count(ledger, carry_over=True) == 2


def _statement():
    def txn(day, amount, description, balance):
        return Transaction(date=day, description=description, amount=amount,
                           direction="credit" if amount >= 0 else "debit", running_balance=balance)
    return Statement(
        bank="Test Bank", period_start="2054-01-01", period_end="2054-01-05",
        beginning_balance=100.0, ending_balance=-20.0,
        transactions=[txn("2054-01-02", -150.0, "ITEM RETURNED NSF", -50.0),
                      txn("2054-01-04", 30.0, "DEPOSIT", -20.0)])


def test_metrics_default_to_printed_days_and_keep_the_carry_over_count():
    stmt = _statement()
    assert reconcile(stmt).ok
    m = compute_metrics(stmt)
    assert m.negative_days == 4               # carry-over: 01-02 through 01-05 end below zero
    assert m.negative_printed_days == 2       # printed: only 01-02 and 01-04 have activity
    assert m.effective_nsf_count == 2 and m.nsf_source == PRINTED
    assert m.nsf_count == 1                   # the returned item is still evidence, reported apart


def test_serialized_metrics_switch_basis_both_ways_without_mutating_the_record():
    metrics = _metrics_dict(compute_metrics(_statement()))
    before = deepcopy(metrics)
    carried = apply_nsf_basis(metrics, carry_over=True)
    assert carried["effective_nsf_count"] == 4 and carried["nsf_source"] == CARRIED
    printed = apply_nsf_basis(carried, carry_over=False)
    assert printed["effective_nsf_count"] == 2 and printed["nsf_source"] == PRINTED
    assert metrics == before


def test_an_unavailable_count_is_never_rebased():
    metrics = {"nsf_source": UNAVAILABLE, "effective_nsf_count": 0, "negative_days": 0}
    assert apply_nsf_basis(metrics, carry_over=True) == metrics
    assert apply_nsf_basis(metrics, carry_over=False) == metrics


def test_a_payload_written_before_the_printed_basis_is_derived_from_its_ledger():
    legacy = {"nsf_source": CARRIED, "effective_nsf_count": 2, "negative_days": 2,
              "adb": {"daily_balances": [{"date": d.date, "ending_balance": d.ending_balance, "source": d.source}
                                         for d in _ledger()]}}
    printed = apply_nsf_basis(legacy, carry_over=False)
    assert printed["effective_nsf_count"] == 1 and printed["nsf_source"] == PRINTED


def test_a_legacy_payload_without_a_ledger_keeps_its_own_count_and_label():
    legacy = {"nsf_source": CARRIED, "effective_nsf_count": 2, "negative_days": 2, "adb": {"daily_balances": []}}
    assert apply_nsf_basis(legacy, carry_over=False) == legacy


def test_every_account_of_a_document_payload_is_rebased():
    metrics = _metrics_dict(compute_metrics(_statement()))
    document = {"document": {"id": "x"}, "accounts": [{"statement": {}, "metrics": metrics},
                                                      {"statement": {}, "metrics": metrics}]}
    before = deepcopy(document)
    carried = apply_nsf_basis_to_payload(document, carry_over=True)
    assert [a["metrics"]["effective_nsf_count"] for a in carried["accounts"]] == [4, 4]
    assert document == before
    single = apply_nsf_basis_to_payload({"statement": {}, "metrics": metrics}, carry_over=True)
    assert single["metrics"]["effective_nsf_count"] == 4


def test_presentation_never_refuses_what_it_cannot_rebase():
    # No analysis, or a malformed document: returned as is, for the readers that refuse it to refuse it.
    assert apply_nsf_basis_to_payload(None, carry_over=True) is None
    assert apply_nsf_basis_to_payload({}, carry_over=True) == {}
    malformed = {"accounts": [{"metrics": {"nsf_source": CARRIED, "negative_printed_days": 0}}]}
    assert apply_nsf_basis_to_payload(malformed, carry_over=False) is malformed
