"""Owner ruling, 2026-09-22: the NSF count defaults to printed days; carrying a balance over inactive days is
an option. Fabricated figures only."""
from copy import deepcopy

import pytest

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


# ---------------------------------------------------------------- metrics.nsf_days: the days the count counts
# Owner request, 2026-09-27 ("Two chips"): the dashboard's NSFs chip lists the days the NSF count counts, each shown by
# the posting that ended it, so the chip always agrees with the tile. The server publishes them as metrics.nsf_days.

def _posting(day, amount, location):
    return {"date": day, "description": "FABRICATED POSTING", "amount": amount,
            "classification": {"classification": "other", "source_location": location}}


def _serialized(ledger):
    return [{"date": d.date, "ending_balance": d.ending_balance, "source": d.source,
             "transaction_count": d.transaction_count} for d in ledger]


def _account(ledger, transactions, *, count=None, source=PRINTED):
    printed = negative_day_count(ledger, carry_over=False)
    carried = negative_day_count(ledger, carry_over=True)
    return {"statement": {"transactions": transactions},
            "metrics": {"nsf_source": source, "effective_nsf_count": printed if count is None else count,
                        "negative_days": carried, "negative_printed_days": printed, "nsf_count": 0,
                        "adb": {"ok": True, "daily_balances": _serialized(ledger)}}}


def _owners_example():
    # 03-10 ends -10 with activity, 03-11 has none, 03-12 ends +20.
    return _account(_ledger(), [_posting("2054-03-10", -10.0, "transaction:1"),
                                _posting("2054-03-12", 30.0, "transaction:2")])


def test_the_owners_example_lists_one_printed_day_and_two_carried_days_both_ended_by_the_10th():
    account = _owners_example()
    printed = apply_nsf_basis_to_payload(account, carry_over=False)["metrics"]
    carried = apply_nsf_basis_to_payload(account, carry_over=True)["metrics"]
    assert printed["nsf_days"] == [
        {"date": "2054-03-10", "ending_balance": -10.0, "source": "reconstructed", "source_location": "transaction:1"}]
    assert carried["nsf_days"] == [
        {"date": "2054-03-10", "ending_balance": -10.0, "source": "reconstructed", "source_location": "transaction:1"},
        {"date": "2054-03-11", "ending_balance": -10.0, "source": "carried", "source_location": "transaction:1"}]
    assert len(printed["nsf_days"]) == printed["effective_nsf_count"] == 1
    assert len(carried["nsf_days"]) == carried["effective_nsf_count"] == 2


def test_a_day_negative_intraday_that_ends_positive_is_not_an_nsf_day():
    ledger = [DailyBalance("2054-03-10", 5.0, "reconstructed", 2)]
    account = _account(ledger, [_posting("2054-03-10", -20.0, "transaction:1"),
                                _posting("2054-03-10", 25.0, "transaction:2")])
    for carry_over in (False, True):
        metrics = apply_nsf_basis_to_payload(account, carry_over=carry_over)["metrics"]
        assert metrics["nsf_days"] == [] and metrics["effective_nsf_count"] == 0


def test_a_negative_day_with_two_postings_is_shown_by_its_last_posting_in_statement_order():
    ledger = [DailyBalance("2054-03-09", 50.0, "reconstructed", 1),
              DailyBalance("2054-03-10", -10.0, "reconstructed", 2),
              DailyBalance("2054-03-11", -10.0, "carried", 0)]
    # Printed out of date order: the posting of the 9th comes last, and is still not the one that ended the 10th.
    account = _account(ledger, [_posting("2054-03-10", -30.0, "transaction:1"),
                                _posting("2054-03-10", -30.0, "transaction:2"),
                                _posting("2054-03-09", 50.0, "transaction:3")])
    printed = apply_nsf_basis_to_payload(account, carry_over=False)["metrics"]["nsf_days"]
    carried = apply_nsf_basis_to_payload(account, carry_over=True)["metrics"]["nsf_days"]
    assert [day["source_location"] for day in printed] == ["transaction:2"]
    assert [(day["date"], day["source_location"]) for day in carried] == [("2054-03-10", "transaction:2"),
                                                                          ("2054-03-11", "transaction:2")]


def test_a_day_without_postings_is_shown_by_the_last_posting_before_it_or_by_none():
    # The opening balance is negative: the 1st carries it with no posting on or before it. The bank printed the
    # balance of the 3rd in its daily balance table, with no posting that day.
    ledger = [DailyBalance("2054-03-01", -5.0, "carried", 0),
              DailyBalance("2054-03-02", -8.0, "reconstructed", 1),
              DailyBalance("2054-03-03", -8.0, "bank_daily_summary", 0)]
    account = _account(ledger, [_posting("2054-03-02", -3.0, "transaction:1")])
    printed = apply_nsf_basis_to_payload(account, carry_over=False)["metrics"]["nsf_days"]
    carried = apply_nsf_basis_to_payload(account, carry_over=True)["metrics"]["nsf_days"]
    assert [(day["date"], day["source"], day["source_location"]) for day in printed] == [
        ("2054-03-02", "reconstructed", "transaction:1"), ("2054-03-03", "bank_daily_summary", "transaction:1")]
    assert [(day["date"], day["source_location"]) for day in carried] == [
        ("2054-03-01", None), ("2054-03-02", "transaction:1"), ("2054-03-03", "transaction:1")]


def test_an_unavailable_count_lists_no_day():
    account = {"statement": {"transactions": [_posting("2054-03-10", -10.0, "transaction:1")]},
               "metrics": {"nsf_source": UNAVAILABLE, "effective_nsf_count": 0, "adb": {"daily_balances": []}}}
    for carry_over in (False, True):
        metrics = apply_nsf_basis_to_payload(account, carry_over=carry_over)["metrics"]
        assert metrics["nsf_days"] == [] and metrics["nsf_source"] == UNAVAILABLE


@pytest.mark.parametrize("ledger", [
    "not a ledger", {"2054-03-10": -10.0}, [None], ["2054-03-10 -10.00"],
    [{"date": "not a date", "ending_balance": -10.0, "source": "reconstructed"}],
    [{"date": None, "ending_balance": -10.0, "source": "reconstructed"}],
], ids=["string", "mapping", "none-entry", "string-entry", "bad-date", "no-date"])
def test_a_malformed_ledger_lists_no_day_and_never_raises(ledger):
    account = {"statement": {"transactions": [_posting("2054-03-10", -10.0, "transaction:1")]},
               "metrics": {"nsf_source": PRINTED, "effective_nsf_count": 1, "negative_days": 1,
                           "negative_printed_days": 1, "adb": {"daily_balances": ledger}}}
    for carry_over in (False, True):
        assert apply_nsf_basis_to_payload(account, carry_over=carry_over)["metrics"]["nsf_days"] == []


@pytest.mark.parametrize("transactions", [None, "rows", [None, 7], [{"date": "garbage", "amount": -1.0}]],
                         ids=["none", "string", "junk-rows", "undated-row"])
def test_malformed_postings_leave_the_days_listed_without_a_posting(transactions):
    account = _owners_example()
    account["statement"]["transactions"] = transactions
    days = apply_nsf_basis_to_payload(account, carry_over=True)["metrics"]["nsf_days"]
    assert [(day["date"], day["source_location"]) for day in days] == [("2054-03-10", None), ("2054-03-11", None)]


def test_a_posting_without_a_recorded_location_is_named_by_its_position():
    account = _owners_example()
    del account["statement"]["transactions"][0]["classification"]
    [day] = apply_nsf_basis_to_payload(account, carry_over=False)["metrics"]["nsf_days"]
    assert day["source_location"] == "transaction:1"


def test_a_ledger_that_does_not_support_the_count_lists_no_day():
    # The payload's own count says 3 printed days; its ledger shows one. No list of the wrong length is published.
    account = _owners_example()
    account["metrics"]["negative_printed_days"] = 3
    metrics = apply_nsf_basis_to_payload(account, carry_over=False)["metrics"]
    assert metrics["effective_nsf_count"] == 3 and metrics["nsf_days"] == []


def test_listing_the_days_never_mutates_the_payload():
    account = _owners_example()
    document = {"document": {"id": "x"}, "accounts": [deepcopy(account), deepcopy(account)]}
    before_account, before_document = deepcopy(account), deepcopy(document)
    apply_nsf_basis_to_payload(account, carry_over=True)
    apply_nsf_basis_to_payload(document, carry_over=False)
    assert account == before_account and document == before_document
    assert "nsf_days" not in account["metrics"]


def test_the_exports_rebase_without_listing_the_days():
    account = _owners_example()
    document = {"document": {"id": "x"}, "accounts": [deepcopy(account)]}
    single = apply_nsf_basis_to_payload(account, carry_over=True, list_days=False)["metrics"]
    [inner] = apply_nsf_basis_to_payload(document, carry_over=True, list_days=False)["accounts"]
    for metrics in (single, inner["metrics"]):
        assert "nsf_days" not in metrics
        assert metrics["effective_nsf_count"] == 2 and metrics["nsf_source"] == CARRIED


def test_every_account_of_a_document_lists_its_own_days():
    negative = _owners_example()
    positive = _account([DailyBalance("2054-03-10", 40.0, "reconstructed", 1)],
                        [_posting("2054-03-10", 40.0, "transaction:1")])
    document = {"document": {"id": "x"}, "accounts": [negative, positive]}
    accounts = apply_nsf_basis_to_payload(document, carry_over=True)["accounts"]
    assert [len(a["metrics"]["nsf_days"]) for a in accounts] == [2, 0]
    assert [a["metrics"]["effective_nsf_count"] for a in accounts] == [2, 0]


def _pipeline_payload():
    """The real analysis path over a fabricated statement: analyze, then publish."""
    from analysis.pipeline import analyze_statement
    from analysis.serialization import document_report_to_dict
    statement = _statement()
    report = analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                               model_used="fabricated-test")
    return document_report_to_dict(report)


@pytest.mark.parametrize("carry_over", [False, True], ids=["printed", "carry-over"])
def test_the_published_analysis_lists_exactly_the_days_its_count_counts(carry_over):
    from analysis.payload_shape import payload_accounts
    served = apply_nsf_basis_to_payload(_pipeline_payload(), carry_over=carry_over)
    accounts = payload_accounts(served, surface="tests/test_nsf_days.py") if "accounts" in served else [served]
    [account] = accounts
    metrics = account["metrics"]
    assert metrics["nsf_source"] == (CARRIED if carry_over else PRINTED)
    assert len(metrics["nsf_days"]) == metrics["effective_nsf_count"] == (4 if carry_over else 2)
    # The 2nd is ended by the returned item, the 4th by the deposit; a carried day by the posting before it.
    expected = ([("2054-01-02", "transaction:1"), ("2054-01-03", "transaction:1"), ("2054-01-04", "transaction:2"),
                 ("2054-01-05", "transaction:2")] if carry_over
                else [("2054-01-02", "transaction:1"), ("2054-01-04", "transaction:2")])
    assert [(day["date"], day["source_location"]) for day in metrics["nsf_days"]] == expected
    # The returned item stays evidence of its own: one nsf_or_return row, whatever the days.
    rows = account["statement"]["transactions"]
    assert [row["classification"]["classification"] for row in rows].count("nsf_or_return") == 1
