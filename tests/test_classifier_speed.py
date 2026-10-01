"""Spec section 4.6: the compiled matcher classifies a fabricated 300-row statement at least 10x faster,
and changes no classification."""
from __future__ import annotations

from dataclasses import asdict

from analysis import transaction_classifier
from tools.bench_classifier import REQUIRED_SPEEDUP, fabricated_statement, legacy_matchers, measure


def test_the_classifier_matches_through_the_compiled_registry_index(monkeypatch):
    calls = []
    compiled = transaction_classifier.registry_match

    def spy(text, registry, **options):
        calls.append(text)
        return compiled(text, registry, **options)

    monkeypatch.setattr(transaction_classifier, "registry_match", spy)
    transaction_classifier.classify_statement_transactions(fabricated_statement(3))
    assert calls


def test_the_compiled_matcher_changes_no_record_of_the_fabricated_statement():
    statement = fabricated_statement(60)
    compiled = [asdict(record) for record in transaction_classifier.classify_statement_transactions(statement)]
    with legacy_matchers():
        legacy = [asdict(record) for record in transaction_classifier.classify_statement_transactions(statement)]
    assert compiled == legacy


def test_three_hundred_fabricated_rows_classify_at_least_ten_times_faster():
    result = measure(300)
    assert result["speedup"] >= REQUIRED_SPEEDUP, result
