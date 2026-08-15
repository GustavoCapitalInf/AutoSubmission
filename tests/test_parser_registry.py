"""Registry mechanics: scoring, ordering, ambiguity, dispatch (R-3.1).

These tests build a synthetic registry so they exercise the rules themselves
rather than any bank's markers. The real registrations are covered by
`tests/test_parser_registry_entries.py` (data shape) and
`tests/test_parser_parity.py` (behaviour over the pinned corpus).

The scoring assertions are the load-bearing ones: R-3's whole parity argument
rests on a registration reaching `CLAIM_THRESHOLD` exactly when its pre-R-3
conjunctive guard would have passed.
"""
from __future__ import annotations

import pytest

from analysis import parser_registry as pr
from analysis.schema import Statement


@pytest.fixture(autouse=True)
def isolated_registry():
    """Every test gets an empty registry and leaves the real one alone."""
    saved = dict(pr._REGISTRY)
    pr.clear_registry()
    try:
        yield
    finally:
        pr.clear_registry()
        pr._REGISTRY.update(saved)


def contains(needle: str):
    return lambda markdown: needle in markdown


def statement(bank: str) -> Statement:
    return Statement(bank=bank)


def make(
    parser_id: str,
    *markers,
    bank: str | None = None,
    parses: bool = True,
    band: int = 100,
    supersedes: frozenset[str] = frozenset(),
    **kwargs,
) -> pr.Registration:
    return pr.register(
        pr.Registration(
            id=parser_id,
            bank=bank or parser_id.replace("_", " ").title(),
            markers=tuple(markers) or (pr.required("any", lambda _md: True),),
            parse=(lambda md, _b=bank or parser_id: statement(_b)) if parses else (lambda md: None),
            band=band,
            supersedes=supersedes,
            **kwargs,
        )
    )


# ===========================================================================
# Scoring
# ===========================================================================

def test_all_required_markers_present_reaches_exactly_the_threshold():
    """The parity-by-construction property, stated as a test.

    A pre-R-3 guard was `all(required)`. Under this formula that condition — and
    only that condition — produces a claim, at exactly CLAIM_THRESHOLD.
    """
    markers = (pr.required("a", contains("A")), pr.required("b", contains("B")))
    detection = pr.score_markers(markers, "A and B")
    assert detection.score == pr.CLAIM_THRESHOLD
    assert detection.claims
    assert detection.matched == ("a", "b")


@pytest.mark.parametrize("document", ["A only", "B only", "neither"])
def test_a_missing_required_marker_never_claims(document):
    markers = (pr.required("a", contains("A")), pr.required("b", contains("B")))
    detection = pr.score_markers(markers, document)
    assert not detection.claims
    assert detection.score < pr.CLAIM_THRESHOLD


def test_partial_matches_rank_above_no_evidence_but_below_the_threshold():
    markers = (
        pr.required("a", contains("A")),
        pr.required("b", contains("B")),
        pr.required("c", contains("C")),
    )
    none = pr.score_markers(markers, "nothing")
    one = pr.score_markers(markers, "A")
    two = pr.score_markers(markers, "A B")
    assert none.score == 0.0
    assert 0.0 < one.score < two.score < pr.CLAIM_THRESHOLD


def test_corroborating_markers_raise_a_claim_without_being_required():
    markers = (
        pr.required("a", contains("A")),
        pr.corroborating("x", contains("X")),
        pr.corroborating("y", contains("Y")),
    )
    bare = pr.score_markers(markers, "A")
    half = pr.score_markers(markers, "A X")
    full = pr.score_markers(markers, "A X Y")
    assert bare.score == pr.CLAIM_THRESHOLD
    assert half.score == 0.75
    assert full.score == 1.0
    assert all(d.claims for d in (bare, half, full))


def test_corroboration_alone_cannot_claim():
    markers = (pr.required("a", contains("A")), pr.corroborating("x", contains("X")))
    detection = pr.score_markers(markers, "X but no first letter")
    assert not detection.claims
    assert detection.matched == ("x",)


def test_an_exclusive_sentinel_scores_one_immediately():
    markers = (pr.required("a", contains("A")), pr.exclusive("sentinel", contains("ONLY-ME")))
    detection = pr.score_markers(markers, "ONLY-ME")
    assert detection.score == 1.0
    assert detection.matched == ("sentinel",)


def test_an_excluding_marker_beats_every_other_kind():
    markers = (
        pr.exclusive("sentinel", contains("ONLY-ME")),
        pr.required("a", contains("A")),
        pr.excluding("wrong_document", contains("NOT-A-STATEMENT")),
    )
    detection = pr.score_markers(markers, "ONLY-ME A NOT-A-STATEMENT")
    assert detection.score == 0.0
    assert detection.excluded_by == "wrong_document"
    assert not detection.claims


def test_scores_stay_inside_the_documented_scale():
    markers = (pr.required("a", contains("A")), pr.corroborating("x", contains("X")))
    for document in ("", "A", "X", "A X", "A" * 500):
        detection = pr.score_markers(markers, document)
        assert 0.0 <= detection.score <= 1.0


def test_detection_is_pure_and_repeatable():
    registration = make("bank_a", pr.required("a", contains("A")))
    document = "A statement"
    first = registration.detect(document)
    second = registration.detect(document)
    assert first == second
    assert document == "A statement"


# ===========================================================================
# Prepared text (the sweep seam)
# ===========================================================================

def test_a_prepared_document_strips_the_filename_comment_once():
    prepared = pr.prepare("<!-- SOURCE: chase.pdf -->\nSTATEMENT")
    assert "chase.pdf" not in prepared.admissible
    assert prepared.preparations == 1


def test_each_distinct_normalization_runs_once_per_document():
    """The property the budget rests on. Two registrations sharing a
    normalizer share its output; a third with its own pays for its own."""
    calls = {"shared": 0, "own": 0}

    def shared(text: str) -> str:
        calls["shared"] += 1
        return text.upper()

    def own(text: str) -> str:
        calls["own"] += 1
        return text.lower()

    a = make("a", pr.required("m", contains("X")), normalize=shared)
    b = make("b", pr.required("m", contains("X")), normalize=shared)
    c = make("c", pr.required("m", contains("x")), normalize=own)
    d = make("d", pr.required("m", contains("X")))

    prepared = pr.prepare("x")
    detections = [reg.detect_prepared(prepared) for reg in (a, b, c, d)]

    assert calls == {"shared": 1, "own": 1}
    assert prepared.preparations == 3  # admissible + the two normalizations
    assert [det.claims for det in detections] == [True, True, True, False]


def test_a_prepared_sweep_detects_exactly_as_an_unprepared_one():
    registrations = [
        make("upper", pr.required("m", contains("BANK")), normalize=str.upper),
        make("raw", pr.required("m", contains("bank"))),
        make("excluded", pr.required("m", contains("bank")),
             pr.excluding("no", contains("void"))),
    ]
    document = "<!-- SOURCE: x.pdf -->\nbank statement, not void"
    prepared = pr.prepare(document)
    for registration in registrations:
        assert registration.detect_prepared(prepared) == registration.detect(document)


def test_a_marker_two_registrations_share_is_evaluated_once_per_text():
    """The measured case: `glyph_damaged` is an excluding marker on three
    registrations, and costs 13 ms of a 150 ms sweep each time it runs."""
    calls = []

    def expensive(text: str) -> bool:
        calls.append(text)
        return "DAMAGED" in text

    marker = pr.excluding("damage", expensive)
    a = make("a", marker, pr.required("m", contains("X")))
    b = make("b", marker, pr.required("m", contains("X")))

    prepared = pr.prepare("X")
    assert a.detect_prepared(prepared).claims
    assert b.detect_prepared(prepared).claims
    assert len(calls) == 1


def test_a_marker_that_raises_is_not_memoized_and_still_reaches_the_guard():
    def explodes(_text: str) -> bool:
        raise ValueError("cannot handle this document")

    registration = make("boom", pr.required("m", explodes))
    prepared = pr.prepare("anything")
    failures: list[pr.ParserFailure] = []

    assert pr.safe_detect(registration, prepared, failures).score == 0.0
    assert pr.safe_detect(registration, prepared, failures).score == 0.0
    assert [f.exception for f in failures] == ["ValueError", "ValueError"]


def test_an_unhashable_normalization_result_takes_the_base_path_not_a_crash():
    """Interning trusts the normalizer's return value, so it is guarded.

    Before the guard this raised inside `text_for` and surfaced as a
    `ParserFailure` — fail-closed, but a failure mode the or-chain did not
    have, on a registration that used to score normally.
    """
    class Unhashable(str):
        __hash__ = None  # type: ignore[assignment]

    registration = make("a", pr.required("m", contains("X")),
                        normalize=lambda text: Unhashable(text.upper()))
    prepared = pr.prepare("x")

    assert registration.detect_prepared(prepared).claims
    assert registration.detect_prepared(prepared) == registration.detect("x")


def test_a_str_subclass_result_is_never_swapped_for_another_registrations_text():
    """The silent half of the same hazard.

    `Sticky` compares equal to everything, so interning it would hand the
    second registration the FIRST one's text to run its markers over. The
    guard keeps each registration on the text its own normalizer produced.
    """
    class Sticky(str):
        def __eq__(self, other):
            return True

        def __hash__(self):
            return 0

    first = make("first", pr.required("m", contains("AAA")),
                 normalize=lambda text: Sticky("AAA"))
    second = make("second", pr.required("m", contains("BBB")),
                  normalize=lambda text: Sticky("BBB"))
    prepared = pr.prepare("anything")

    assert first.detect_prepared(prepared).claims
    assert second.detect_prepared(prepared).claims, (
        "second registration was handed the first one's interned text"
    )


def test_preparing_a_document_never_mutates_it():
    document = "<!-- SOURCE: x.pdf -->\nBank Statement"
    prepared = pr.prepare(document)
    make("a", pr.required("m", contains("BANK")), normalize=str.upper).detect_prepared(prepared)
    assert document == "<!-- SOURCE: x.pdf -->\nBank Statement"


# ===========================================================================
# Registry data
# ===========================================================================

def test_registry_order_is_band_then_id():
    make("zulu", band=10)
    make("alpha", band=100)
    make("bravo", band=10)
    make("yankee", band=900)
    assert [r.id for r in pr.registrations()] == ["bravo", "zulu", "alpha", "yankee"]


def test_duplicate_ids_are_rejected():
    make("bank_a")
    with pytest.raises(ValueError, match="duplicate parser id"):
        make("bank_a")


def test_a_registration_without_markers_is_rejected():
    with pytest.raises(ValueError, match="registers no markers"):
        pr.register(pr.Registration(id="empty", bank="Empty", markers=(), parse=lambda md: None))


def test_supersedes_targets_must_exist():
    make("narrow", supersedes=frozenset({"missing"}))
    with pytest.raises(ValueError, match="supersedes unknown parser"):
        pr.validate_registry()


def test_supersedes_cycles_are_rejected():
    make("one", supersedes=frozenset({"two"}))
    make("two", supersedes=frozenset({"one"}))
    with pytest.raises(ValueError, match="supersedes cycle"):
        pr.validate_registry()


def test_lookup_by_bank_label_is_case_insensitive_and_deterministic():
    make("bank_a", bank="Bank Of Example")
    assert pr.by_bank_label("bank of example").id == "bank_a"
    assert pr.by_bank_label("  BANK OF EXAMPLE  ").id == "bank_a"
    assert pr.by_bank_label("Someone Else") is None
    assert pr.by_bank_label(None) is None
    assert pr.by_bank_label("") is None


# ===========================================================================
# Dispatch
# ===========================================================================

def test_a_single_claimant_is_claimed():
    make("bank_a", pr.required("a", contains("AAA")), bank="Bank A")
    make("bank_b", pr.required("b", contains("BBB")), bank="Bank B")
    dispatch = pr.resolve("document mentioning AAA")
    assert dispatch.outcome == "claimed"
    assert dispatch.parser_id == "bank_a"
    assert dispatch.statement.bank == "Bank A"
    assert dispatch.candidates == (("bank_a", 0.5),)
    assert dispatch.attempted == ()


def test_no_claimant_is_unclaimed():
    make("bank_a", pr.required("a", contains("AAA")))
    dispatch = pr.resolve("a document from somewhere else entirely")
    assert dispatch.outcome == "unclaimed"
    assert dispatch.registration is None
    assert dispatch.statement is None
    assert dispatch.candidates == ()


def test_two_claimants_are_ambiguous_and_no_parse_runs():
    parsed: list[str] = []

    def spy(parser_id):
        def parse(markdown):
            parsed.append(parser_id)
            return statement(parser_id)

        return parse

    pr.register(pr.Registration("bank_a", "Bank A", (pr.required("a", contains("SHARED")),), spy("bank_a")))
    pr.register(pr.Registration("bank_b", "Bank B", (pr.required("b", contains("SHARED")),), spy("bank_b")))

    dispatch = pr.resolve("a SHARED phrase both banks print")
    assert dispatch.outcome == "ambiguous"
    assert dispatch.registration is None
    assert dispatch.statement is None
    assert [name for name, _score in dispatch.candidates] == ["bank_a", "bank_b"]
    assert parsed == [], "an ambiguous document must never be parsed"


def test_ambiguity_is_decided_before_parsing_even_when_scores_differ():
    """A higher score does not break a tie — only `supersedes` does."""
    make("weak", pr.required("a", contains("SHARED")))
    make("strong", pr.required("a", contains("SHARED")), pr.corroborating("x", contains("SHARED")))
    dispatch = pr.resolve("SHARED")
    assert dispatch.outcome == "ambiguous"
    assert dispatch.candidates == (("strong", 1.0), ("weak", 0.5))


def test_supersedes_resolves_a_would_be_ambiguity():
    make("broad", pr.required("a", contains("SHARED")), bank="Broad")
    make("narrow", pr.required("a", contains("SHARED")), bank="Narrow", supersedes=frozenset({"broad"}))
    dispatch = pr.resolve("SHARED")
    assert dispatch.outcome == "claimed"
    assert dispatch.parser_id == "narrow"


def test_superseding_parser_that_does_not_claim_leaves_the_broad_one_alone():
    make("broad", pr.required("a", contains("BROAD")), bank="Broad")
    make("narrow", pr.required("n", contains("NARROW")), bank="Narrow", supersedes=frozenset({"broad"}))
    dispatch = pr.resolve("only BROAD here")
    assert dispatch.outcome == "claimed"
    assert dispatch.parser_id == "broad"


def test_a_claimant_that_declines_to_parse_yields_unclaimed_and_is_recorded():
    """The fallthrough case the or-chain made invisible (R3_RFC §4.3)."""
    make("bank_a", pr.required("a", contains("AAA")), parses=False)
    dispatch = pr.resolve("AAA")
    assert dispatch.outcome == "unclaimed"
    assert dispatch.attempted == ("bank_a",)
    assert dispatch.candidates == (("bank_a", 0.5),)


def test_ambiguous_error_lists_its_candidates():
    error = pr.AmbiguousParserError((("bank_a", 0.5), ("bank_b", 0.75)))
    assert "bank_a (0.50)" in str(error)
    assert "bank_b (0.75)" in str(error)
    assert error.candidates == (("bank_a", 0.5), ("bank_b", 0.75))


def test_detection_report_ranks_every_registration():
    make("bank_a", pr.required("a", contains("AAA")))
    make("bank_b", pr.required("b", contains("BBB")))
    report = dict(pr.detection_report("AAA"))
    assert report["bank_a"].claims
    assert not report["bank_b"].claims
    assert [name for name, _ in pr.detection_report("AAA")] == ["bank_a", "bank_b"]


def test_registrations_are_immutable():
    registration = make("bank_a")
    with pytest.raises(Exception):
        registration.id = "renamed"
