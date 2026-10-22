"""Spec section 4.6: the compiled matcher classifies a fabricated statement at least 10x faster than the
matcher as it stood before S1, and changes no classification.

The spec's acceptance run is the 300-row statement of `python -m tools.bench_classifier`, which stays the
measurement of record. The suite holds the same 10x line on the 60-row statement it already classifies for
the no-change check, and one legacy pass serves both checks (audit 2026-10-13, HYG-08). The legacy reference
is the slow side by design, and its cost grows with every alias the registries gain (about 0.14 s a row,
measured 2026-10-14), while the ratio barely depends on the row count (measured 283x at 30 rows, 285x and
290x at 60, 225x and 285x at 300). So the separate 300-row pass bought 40 to 110 s of suite time and no assurance
the 60-row pass lacks; with the compiled matchers swapped for the legacy ones, the 60-row check fails at 1.0x.
"""
from __future__ import annotations

from dataclasses import asdict

import pytest

from analysis import transaction_classifier
from analysis.classification import operating_sources
from analysis.classification import payees
from analysis.classification import tax_forms
from analysis.descriptor import financing
from analysis import payee_matcher
from tools.bench_classifier import REQUIRED_SPEEDUP, fabricated_statement, measure


@pytest.fixture(scope="module")
def sixty_rows() -> dict:
    """The 60-row fabricated statement classified with the compiled matchers (a warm-up, then the best of
    three timed runs) and once with the legacy matchers, both sides' records kept."""
    return measure(60, keep_records=True)


def test_the_classifier_matches_through_the_compiled_registry_index(monkeypatch):
    calls = []
    compiled = payee_matcher.registry_match

    def spy(text, registry, **options):
        calls.append(text)
        return compiled(text, registry, **options)

    monkeypatch.setattr(transaction_classifier, "registry_match", spy)
    monkeypatch.setattr(operating_sources, "registry_match", spy)
    monkeypatch.setattr(payees, "registry_match", spy)
    monkeypatch.setattr(tax_forms, "registry_match", spy)
    monkeypatch.setattr(financing, "registry_match", spy)
    transaction_classifier.classify_statement_transactions(fabricated_statement(3))
    assert calls


def test_the_compiled_matcher_changes_no_record_of_the_fabricated_statement(sixty_rows):
    compiled = [asdict(record) for record in sixty_rows["current_records"]]
    legacy = [asdict(record) for record in sixty_rows["legacy_records"]]
    assert len(compiled) == 60
    assert compiled == legacy


def test_sixty_fabricated_rows_classify_at_least_ten_times_faster(sixty_rows):
    result = {key: value for key, value in sixty_rows.items() if not key.endswith("_records")}
    assert result["rows"] == 60
    assert result["speedup"] >= REQUIRED_SPEEDUP, result
