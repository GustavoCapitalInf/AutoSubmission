"""Audit 2026-10-13, PERF-02 (and F1's cache): one classification answers each matcher question once.

AliasIndex.match is a pure function of an immutable index and the text, and one statement asks the same index about
the same text again and again (the row rules, the record, the revenue rules, the true-revenue pass, and both Zelle
readings). The skeptics' binding amendment: no memo that outlives the classification, because a memo hanging off the
module-level indexes would keep normalized transaction descriptions in the worker's memory across jobs (the residency
the privacy work closes elsewhere), and would let the spec 4.6 speed gate time memo hits instead of the matcher.

So the memo is scoped: `payee_matcher.match_memo()` opens it, the statement-level classifications open it on entry
and drop it on exit (both Zelle readings share one), and a call outside a scope is not memoised at all. Fabricated
statements only (tests/zelle_setting_fixtures.py, tools/bench_classifier.py).
"""
from __future__ import annotations

import sys
import threading
from contextlib import nullcontext
from dataclasses import asdict

import pytest

from analysis import payee_matcher, transaction_classifier
from analysis.payee_matcher import AliasIndex, match_memo
from tests import zelle_setting_fixtures as fx
from tools.bench_classifier import fabricated_statement

FABRICATED = {"confirmed_lender": {"Contoso Funding": ("CONTOSO FUNDING",), "Fabrikam Capital": ("FABRIKAM CAPITAL",)}}


@pytest.fixture
def evaluations(monkeypatch):
    """Counts the matcher's real evaluations (AliasIndex._match) and its answers (AliasIndex.match)."""
    counts = {"evaluated": 0}
    real = AliasIndex._match

    def counting(self, text):
        counts["evaluated"] += 1
        return real(self, text)

    monkeypatch.setattr(AliasIndex, "_match", counting)
    return counts


def test_outside_a_scope_nothing_is_remembered(evaluations):
    index = AliasIndex(FABRICATED)

    assert index.match("ACH CONTOSO FUNDING 01") is index.match("ACH CONTOSO FUNDING 01")
    assert evaluations["evaluated"] == 2
    assert payee_matcher._MATCH_MEMO.get() is None


def test_inside_a_scope_a_repeated_question_is_answered_once(evaluations):
    index, other = AliasIndex(FABRICATED), AliasIndex(FABRICATED)

    with match_memo():
        first = index.match("ACH CONTOSO FUNDING 01")
        assert index.match("ACH CONTOSO FUNDING 01") is first
        assert index.match("FABRIKAM CAPITAL PMT").entity == "Fabrikam Capital"
        assert index.match("NORTHWIND") is None and index.match("NORTHWIND") is None
        # Another index is another question, even with the same aliases and text.
        assert other.match("ACH CONTOSO FUNDING 01") == first

    assert first.entity == "Contoso Funding"
    assert evaluations["evaluated"] == 4
    assert payee_matcher._MATCH_MEMO.get() is None


def test_a_nested_scope_shares_the_outer_memo(evaluations):
    index = AliasIndex(FABRICATED)
    with match_memo():
        index.match("CONTOSO FUNDING")
        with match_memo():
            index.match("CONTOSO FUNDING")
            assert payee_matcher._MATCH_MEMO.get() is not None
        assert payee_matcher._MATCH_MEMO.get() is not None
        index.match("CONTOSO FUNDING")
    assert evaluations["evaluated"] == 1
    assert payee_matcher._MATCH_MEMO.get() is None


def test_the_memo_is_dropped_when_the_scope_fails(evaluations):
    index = AliasIndex(FABRICATED)
    with pytest.raises(RuntimeError):
        with match_memo():
            index.match("CONTOSO FUNDING")
            raise RuntimeError("SAMPLE failure")
    assert payee_matcher._MATCH_MEMO.get() is None


def test_the_memo_is_bounded(monkeypatch, evaluations):
    monkeypatch.setattr(payee_matcher, "MATCH_MEMO_LIMIT", 3)
    index = AliasIndex(FABRICATED)
    with match_memo():
        for number in range(10):
            index.match(f"SAMPLE {number}")
        assert len(payee_matcher._MATCH_MEMO.get()) <= 3
        # A cleared memo only re-asks; the answer is the same.
        assert index.match("CONTOSO FUNDING").entity == "Contoso Funding"


def test_another_thread_does_not_see_this_thread_s_scope():
    """The web app runs each job in a thread of one process: a job's memo is that job's alone. (A free-threaded build
    hands a new thread a copy of the caller's context, so the check applies where threads start empty, the GIL build
    this product runs.)"""
    seen: list[object] = []
    with match_memo():
        worker = threading.Thread(target=lambda: seen.append(payee_matcher._MATCH_MEMO.get()), daemon=True)
        worker.start()
        worker.join()
    if not getattr(sys.flags, "thread_inherit_context", 0):
        assert seen == [None]
    assert payee_matcher._MATCH_MEMO.get() is None


def test_a_statement_classification_answers_each_question_once(evaluations, monkeypatch):
    answers = {"asked": 0}
    real = AliasIndex.match

    def asking(self, text):
        answers["asked"] += 1
        return real(self, text)

    monkeypatch.setattr(AliasIndex, "match", asking)

    transaction_classifier.classify_statement_readings(fabricated_statement(120))

    assert answers["asked"] > 0
    assert evaluations["evaluated"] < answers["asked"]
    assert payee_matcher._MATCH_MEMO.get() is None


def test_each_classification_starts_cold(evaluations):
    """What the spec 4.6 speed gate times: a classification with an empty memo, every time."""
    statement = fabricated_statement(60)
    transaction_classifier.classify_statement_transactions(statement)
    first = evaluations["evaluated"]
    transaction_classifier.classify_statement_transactions(statement)
    assert evaluations["evaluated"] == 2 * first


def test_no_description_stays_behind_after_a_classification():
    """Residency: after the classification returns, no memo exists and no index holds anything new."""
    indexes = [payee_matcher._DEFAULT_INDEX, payee_matcher._CREDIT_INDEX, payee_matcher._DEBT_RELIEF_INDEX]
    before = [dict(vars(index)) for index in indexes]

    transaction_classifier.classify_statement_readings(fx.statement(fx.Z1))

    assert payee_matcher._MATCH_MEMO.get() is None
    for index, attributes in zip(indexes, before):
        assert set(vars(index)) == set(attributes)
        assert all(vars(index)[name] is value for name, value in attributes.items())
    for _registry, index in payee_matcher._REGISTRY_INDEXES.values():
        assert set(vars(index)) == {"_table", "_glued", "_single", "_letter_tail", "_longest", "_prefixes"}


@pytest.mark.parametrize("name", sorted(fx.CASES))
def test_the_memo_changes_no_record_of_either_reading(monkeypatch, name):
    rows, holder, title = fx.CASES[name]
    statement = fx.statement(rows, holder=holder, title=title)

    remembered = transaction_classifier.classify_statement_readings(statement)
    monkeypatch.setattr(transaction_classifier, "match_memo", nullcontext)
    asked = transaction_classifier.classify_statement_readings(statement)

    for left, right in zip(remembered, asked):
        assert (left is None) == (right is None)
        if left is not None:
            assert [asdict(record) for record in left] == [asdict(record) for record in right]


def test_the_memo_changes_no_record_of_the_fabricated_ledger(monkeypatch):
    statement = fabricated_statement(150)
    remembered = transaction_classifier.classify_statement_transactions(statement)
    monkeypatch.setattr(transaction_classifier, "match_memo", nullcontext)
    asked = transaction_classifier.classify_statement_transactions(statement)
    assert [asdict(record) for record in remembered] == [asdict(record) for record in asked]
