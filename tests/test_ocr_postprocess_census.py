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
    METADATA_ONLY_LABEL,
    FUNCTIONS,
    extract_tokens,
    load_fixture_cases,
)
from ocr.ocr_client import postprocess

ALL_CASES = load_fixture_cases()

#: Review MINOR-R3: a floor of `>= 17` stayed satisfied at 31 fixtures, so
#: deleting any of the 14 fixtures added after the first review re-opened
#: MAJOR-5's exact regression (the reviewer's Y+N compound: delete
#: `collapse_repeated_amounts/two_repeats_untouched`, then widen F-1's
#: `count >= 3` to `>= 2` -- SURVIVED under the old floor) with the suite
#: green. A per-function EXACT count means any single deletion, from any
#: function, names itself immediately by function and by how many are
#: missing, rather than staying silent until the collected total crosses a
#: threshold nobody is watching.
EXPECTED_FIXTURE_COUNT = {
    "strip_det_tags": 5,
    "strip_refusal_commentary": 2,
    "strip_placeholder_markers": 3,
    "strip_oversized_embedded_images": 2,
    "collapse_repeated_amounts": 4,
    "collapse_repeated_page_numbers": 3,
    "split_fused_header_row": 4,
    "repair_fused_amount_table": 4,
    "fix_amount_column_bleed": 4,
}
assert sum(EXPECTED_FIXTURE_COUNT.values()) == 31, "EXPECTED_FIXTURE_COUNT total drifted from 31"


def test_every_function_has_exactly_its_expected_fixture_count():
    by_function: dict[str, int] = {}
    for case in ALL_CASES:
        by_function[case.function] = by_function.get(case.function, 0) + 1
    mismatches = {
        name: (by_function.get(name, 0), expected)
        for name, expected in EXPECTED_FIXTURE_COUNT.items()
        if by_function.get(name, 0) != expected
    }
    assert not mismatches, (
        f"fixture count drifted from EXPECTED_FIXTURE_COUNT (actual, expected): {mismatches}"
    )
    assert len(ALL_CASES) == 31, f"expected 31 total committed fixture cases, found {len(ALL_CASES)}"


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
    may not be classified as 'writes'. Spot-check several ends.

    Review MAJOR-1: `strip_det_tags` and `strip_oversized_embedded_images`
    were falsified by construction and no longer carry the unconditional
    metadata-only label (see `orphan_bracket_contains_money`,
    `pair_spans_to_next_close`, `alt_attribute_money_dropped`); they now use
    the honest 'markup span whose content is UNCONSTRAINED' wording instead.
    `strip_refusal_commentary` and `strip_placeholder_markers` keep the
    label — every one of their fixtures proves it (the invariant below)."""
    assert "deletes" in CLASSIFICATION["collapse_repeated_amounts"]
    assert "writes" in CLASSIFICATION["collapse_repeated_amounts"]
    assert "UNCONSTRAINED" in CLASSIFICATION["strip_det_tags"]
    assert not CLASSIFICATION["strip_det_tags"].startswith(METADATA_ONLY_LABEL)
    assert CLASSIFICATION["strip_refusal_commentary"].startswith(METADATA_ONLY_LABEL)
    assert CLASSIFICATION["strip_placeholder_markers"].startswith(METADATA_ONLY_LABEL)
    assert "UNCONSTRAINED" in CLASSIFICATION["strip_oversized_embedded_images"]
    assert not CLASSIFICATION["strip_oversized_embedded_images"].startswith(METADATA_ONLY_LABEL)
    assert "CONDITIONALLY" in CLASSIFICATION["repair_fused_amount_table"]


def test_metadata_only_classification_never_deletes_a_financial_token():
    """Review MAJOR-1's fix #3: the enforceable invariant that makes the
    METADATA_ONLY_LABEL label mean something, instead of a claim in prose. A
    function may use it ONLY if `money.disappeared is False` and
    `date.disappeared is False` hold on EVERY one of its committed fixtures.

    This is what a mutant that relabels or weakens a value-deleter into this
    bucket would have to defeat: `strip_det_tags` and
    `strip_oversized_embedded_images` are correctly EXCLUDED (their own
    worst-case fixtures show money.disappeared is True); the two functions
    still carrying the label (`strip_refusal_commentary`,
    `strip_placeholder_markers`) are checked against every one of their
    fixtures, including any added later."""
    covered = set()
    for case in ALL_CASES:
        classification = CLASSIFICATION[case.function]
        if not classification.startswith(METADATA_ONLY_LABEL):
            continue
        covered.add(case.function)
        delta = case.meta["numeric_tokens_delta"]
        assert delta["money"]["disappeared"] is False, (
            f"{case.function}/{case.case}: classified {METADATA_ONLY_LABEL!r} "
            f"but a fixture shows a money token disappearing"
        )
        assert delta["date"]["disappeared"] is False, (
            f"{case.function}/{case.case}: classified {METADATA_ONLY_LABEL!r} "
            f"but a fixture shows a date token disappearing"
        )
    # The invariant must not be vacuous: at least one function actually
    # carries the label and was checked.
    assert covered == {"strip_refusal_commentary", "strip_placeholder_markers"}


def test_metadata_only_invariant_actually_catches_a_mislabeled_deleter():
    """The mutant this invariant exists to kill, applied directly (not to a
    live file): if `strip_det_tags` were (wrongly) relabeled back to
    METADATA_ONLY_LABEL while keeping its own `orphan_bracket_contains_money`
    fixture (money.disappeared = True), the invariant must fail."""
    fake_classification = {**CLASSIFICATION, "strip_det_tags": METADATA_ONLY_LABEL}
    offenders = []
    for case in ALL_CASES:
        if not fake_classification[case.function].startswith(METADATA_ONLY_LABEL):
            continue
        if case.meta["numeric_tokens_delta"]["money"]["disappeared"] is True:
            offenders.append(f"{case.function}/{case.case}")
    assert "strip_det_tags/orphan_bracket_contains_money" in offenders
