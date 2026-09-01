"""The nine-function postprocess census, made executable (OQ1 = C, MINOR-6).

Every fixture under `tests/fixtures/ocr_postprocess/<function>/<case>/` is run
through its OWN function AND through the full `postprocess()` chain, and the
recorded numeric-token deltas are independently recomputed (never merely
trusted from `case.json`) so a wrong record — e.g. a fixture's
`numeric_tokens_delta` claiming F-1's [a,a,a,b,c] -> [a] case does not delete
a money token — fails here, not just in prose.

This is also the test that proves `docs/moneythumb-replacement/
OCR_POSTPROCESS_CENSUS.md`'s nine-row table describes real, measured
behavior: every classification claim in that doc must trace back to a
fixture asserted here.
"""
from __future__ import annotations

from collections import Counter

import pytest

from tools.ocr_postprocess_census import (
    CHAIN_ORDER,
    CLASSIFICATION,
    FUNCTIONS,
    extract_tokens,
    load_fixture_cases,
)
from ocr.ocr_client import postprocess

ALL_CASES = load_fixture_cases()

assert len(ALL_CASES) >= 17, (
    f"expected at least 17 committed fixture cases across the nine functions, "
    f"found {len(ALL_CASES)} -- a fixture directory failed to load"
)


def _mechanical_delta(before: dict, after: dict) -> dict:
    """Independently recompute disappeared/appeared per category from the
    RAW before/after token lists (never from a case.json claim)."""
    result = {}
    for cat in ("money", "date", "digit_run"):
        cb, ca = Counter(before[cat]), Counter(after[cat])
        disappeared = any(cb[v] > ca.get(v, 0) for v in cb)
        appeared = any(ca[v] > cb.get(v, 0) for v in ca)
        result[cat] = {"disappeared": disappeared, "appeared": appeared}
    return result


@pytest.mark.parametrize(
    "case", ALL_CASES, ids=[f"{c.function}/{c.case}" for c in ALL_CASES]
)
def test_fixture_function_output_matches_expected(case):
    fn = FUNCTIONS[case.function]
    call_kwargs = case.meta.get("call_kwargs", {})
    actual = fn(case.input_text, **call_kwargs)
    assert actual == case.expected_text, (
        f"{case.function}/{case.case}: function output does not match the "
        f"committed expected.md"
    )


@pytest.mark.parametrize(
    "case", ALL_CASES, ids=[f"{c.function}/{c.case}" for c in ALL_CASES]
)
def test_fixture_full_chain_matches_expected_unless_declared_isolated(case):
    """Every fixture also runs through the FULL nine-function `postprocess`
    chain (not just its own function), proving no other chain member
    interacts with it -- unless the fixture explicitly declares itself
    isolated-function-only (documented, with a reason, in case.json)."""
    if case.meta.get("isolated_function_only"):
        pytest.skip(case.meta.get("isolated_function_only_reason", "declared isolated"))
    actual = postprocess(case.input_text)
    assert actual == case.expected_text, (
        f"{case.function}/{case.case}: the full postprocess() chain produces "
        f"a different result than the isolated function -- an undocumented "
        f"cross-function interaction exists"
    )


@pytest.mark.parametrize(
    "case", ALL_CASES, ids=[f"{c.function}/{c.case}" for c in ALL_CASES]
)
def test_recorded_numeric_tokens_match_measured_tokens(case):
    """`case.json`'s numeric_tokens_before/after must be the REAL measured
    tokens, not a transcription -- catches a hand-authored fixture record
    drifting from what the function actually does."""
    measured_before = extract_tokens(case.input_text)
    measured_after = extract_tokens(case.expected_text)
    assert case.meta["numeric_tokens_before"] == measured_before, (
        f"{case.function}/{case.case}: recorded numeric_tokens_before does "
        f"not match the measured tokens in input.md"
    )
    assert case.meta["numeric_tokens_after"] == measured_after, (
        f"{case.function}/{case.case}: recorded numeric_tokens_after does "
        f"not match the measured tokens in expected.md"
    )


@pytest.mark.parametrize(
    "case", ALL_CASES, ids=[f"{c.function}/{c.case}" for c in ALL_CASES]
)
def test_recorded_token_delta_matches_mechanical_diff(case):
    """Mutation table: 'a census fixture's numeric_tokens_disappeared
    recorded as 0 for F-1's [a,a,a,b,c] is the census test.' The
    disappeared/appeared flags in case.json are cross-checked against an
    INDEPENDENTLY recomputed Counter-diff of the measured tokens -- a wrong
    record (in either direction) fails here."""
    mechanical = _mechanical_delta(
        extract_tokens(case.input_text), extract_tokens(case.expected_text)
    )
    assert case.meta["numeric_tokens_delta"] == mechanical, (
        f"{case.function}/{case.case}: recorded numeric_tokens_delta "
        f"{case.meta['numeric_tokens_delta']} does not match the mechanically "
        f"measured delta {mechanical}"
    )


def test_f1_distinct_adjacent_amounts_are_recorded_as_disappeared():
    """The mutation table's named killer, pinned directly (not just via the
    parametrized sweep above): F-1's worst case must show money tokens
    disappearing. A mutant that records `disappeared: false` here is caught
    by BOTH this test and the mechanical cross-check above."""
    case = next(
        c for c in ALL_CASES
        if c.function == "collapse_repeated_amounts" and c.case == "distinct_adjacent_deleted"
    )
    assert case.meta["numeric_tokens_delta"]["money"]["disappeared"] is True
    # And the actual deleted values are the DISTINCT ones, not merely dupes.
    before = Counter(extract_tokens(case.input_text)["money"])
    after = Counter(extract_tokens(case.expected_text)["money"])
    destroyed = before - after
    assert destroyed.get("$75.00", 0) == 1
    assert destroyed.get("$60.00", 0) == 1


def test_repair_fused_amount_table_fold_is_settled_by_construction():
    """The census's central finding: OCR_LEGACY_AUDIT.md F-11 item 3 called
    the debit/credit/balance fold 'explicitly UNPROVEN'. This fixture proves
    it IS constructible: a genuine secondary money column (a debit AND a
    credit) is folded into free-text description, and the table's true final
    column (a running balance) is relabeled as the transaction amount."""
    case = next(
        c for c in ALL_CASES
        if c.function == "repair_fused_amount_table" and c.case == "debit_credit_balance_folded"
    )
    out = FUNCTIONS["repair_fused_amount_table"](case.input_text)
    assert out == case.expected_text
    # The debit and credit values are now inside the description cell...
    assert "<td>Northstar Vendor Inc 10.00 25.00</td>" in out
    # ...and the running balance is now in the position a parser reads as
    # "the amount" for this row.
    assert out.endswith("<td>105.00</td></tr></table>")
    assert case.meta["semantics_can_change"] is True


def test_every_chain_member_has_a_classification_and_at_least_one_fixture():
    """MINOR-6: the chain is nine functions, not six. Every one of the nine
    is classified and has committed fixture coverage -- a function silently
    dropped from either would pass every other test in this file vacuously."""
    assert len(CHAIN_ORDER) == 9
    by_function: dict[str, int] = {}
    for case in ALL_CASES:
        by_function[case.function] = by_function.get(case.function, 0) + 1
    for name in CHAIN_ORDER:
        assert name in CLASSIFICATION, f"{name} has no recorded classification"
        assert by_function.get(name, 0) >= 1, f"{name} has no committed fixture"


def test_classification_never_uses_a_bare_misleading_label():
    """The card: 'never forced into a label the evidence contradicts.' A
    function whose worst input destroys a value may not be classified as
    merely 'restructures'; a function that never touches a financial value
    may not be classified as 'writes'. Spot-check the two ends."""
    assert "deletes" in CLASSIFICATION["collapse_repeated_amounts"]
    assert "writes" in CLASSIFICATION["collapse_repeated_amounts"]
    assert "reads/removes metadata-only" in CLASSIFICATION["strip_det_tags"]
    assert "reads/removes metadata-only" in CLASSIFICATION["strip_refusal_commentary"]
    assert "reads/removes metadata-only" in CLASSIFICATION["strip_placeholder_markers"]
    assert "reads/removes metadata-only" in CLASSIFICATION["strip_oversized_embedded_images"]
    assert "CONDITIONALLY" in CLASSIFICATION["repair_fused_amount_table"]
