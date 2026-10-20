"""The exception boundary at the dispatch/parse seam (W3-1).

Discovery ran 3,506 real documents through `resolve()` and 53 of them ended
with an exception escaping the seam: the document aborted, no `Dispatch` was
ever produced (so telemetry recorded nothing about who crashed or why), and the
exception message — which routinely quotes a fragment of the statement —
travelled up into whatever caught it.

These tests state the contract that replaces that behaviour, using a synthetic
registry so they exercise the RULE and not any bank's code. The crash shapes
the real parsers exhibited are reproduced separately, synthetically, in
`tests/test_parser_crash_shapes.py`.

The load-bearing test is `test_no_path_from_resolve_through_parse_can_raise`:
everything else describes what the seam does instead of raising.
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


def boom(exception: type[BaseException] = ValueError):
    """A callable that raises with a message quoting its input.

    The message is deliberately document-shaped: several assertions below check
    that no part of it survives into the recorded facts.
    """

    def raise_it(markdown: str):
        raise exception(f"cannot handle: {markdown}")

    return raise_it


def register(
    parser_id: str,
    *markers,
    parse=None,
    detect_raises: type[BaseException] | None = None,
    band: int = 100,
    supersedes: frozenset[str] = frozenset(),
) -> pr.Registration:
    registration = pr.Registration(
        id=parser_id,
        bank=parser_id.replace("_", " ").title(),
        markers=tuple(markers) or (pr.required("any", lambda _md: True),),
        parse=parse if parse is not None else (lambda md, _b=parser_id: Statement(bank=_b)),
        band=band,
        supersedes=supersedes,
    )
    if detect_raises is not None:
        # A marker that raises is the realistic shape of a detection crash: the
        # registry builds `detect` out of markers, so this is where a bad
        # normalization or a malformed regex input surfaces.
        registration = pr.with_overrides(
            registration, markers=(pr.required("explodes", boom(detect_raises)),)
        )
    return pr.register(registration)


def declines(md):
    return None


# ===========================================================================
# The boundary itself
# ===========================================================================

def one_crashing_claimant():
    register("broken", pr.required("m", contains("STATEMENT")), parse=boom(AttributeError))


def every_registration_broken():
    register("detect_boom", detect_raises=RuntimeError)
    register("parse_boom", pr.required("m", contains("STATEMENT")), parse=boom(AttributeError))


def two_broken_claimants():
    register("parse_boom", pr.required("m", contains("STATEMENT")), parse=boom(AttributeError))
    register("parse_boom_2", pr.required("m", contains("STATEMENT")), parse=boom(ValueError))


def crash_beside_a_healthy_parser():
    register("detect_boom", detect_raises=IndexError)
    register("healthy", pr.required("m", contains("STATEMENT")))


def crash_beside_a_decline():
    register("detect_boom", detect_raises=ZeroDivisionError)
    register("declining", pr.required("m", contains("STATEMENT")), parse=declines)


def nothing_registered():
    return None


@pytest.mark.parametrize(
    "build",
    [
        one_crashing_claimant,
        every_registration_broken,
        two_broken_claimants,
        crash_beside_a_healthy_parser,
        crash_beside_a_decline,
        nothing_registered,
    ],
)
def test_no_path_from_resolve_through_parse_can_raise(build):
    """The acceptance criterion, stated once and directly.

    Whatever is broken and however it is broken, `resolve` returns a verdict.
    """
    build()

    dispatch = pr.resolve("STATEMENT")

    assert isinstance(dispatch, pr.Dispatch)
    assert dispatch.outcome in {"claimed", "ambiguous", "unclaimed", "parser_exception"}


def test_a_crashing_parser_does_not_take_the_registry_down_with_it():
    """The crash is confined to its own registration.

    Ambiguity is still decided before any parse runs, so the pruned survivor
    set is what reaches the parse loop; a broken registration inside it neither
    stops the loop nor changes what the healthy ones do. Here the broken
    registration is ruled out at detection, and the healthy one claims exactly
    as it would in a registry containing no broken parser at all.
    """
    crash_beside_a_healthy_parser()

    dispatch = pr.resolve("STATEMENT")

    assert dispatch.outcome == "claimed"
    assert dispatch.parser_id == "healthy"
    assert dispatch.statement is not None
    # The crash is still on the record even though the document was claimed —
    # a parser that breaks on documents another parser then claims is exactly
    # the defect signal this field exists to make countable.
    assert dispatch.exceptions == (pr.ParserFailure("detect_boom", "detect", "IndexError"),)


def test_all_claimants_crashing_is_parser_exception_not_unclaimed():
    """The two states must not be conflated.

    `unclaimed` means "we have no layout knowledge for this document" and ranks
    a bank for future parser work. A crash means "our code broke on a document
    we DO claim to know" and ranks a bug. Discovery's cluster ranking is built
    on that distinction.
    """
    register("only_claimant", pr.required("m", contains("STATEMENT")), parse=boom())

    dispatch = pr.resolve("STATEMENT")

    assert dispatch.outcome == "parser_exception"
    assert dispatch.attempted == (), "a crash is not a decline"
    assert dispatch.candidates == (("only_claimant", 0.5),)


def test_a_crashing_detect_cannot_claim():
    """Fail closed: an unreadable detection is not an optimistic one."""
    register("detect_boom", detect_raises=KeyError)
    register("healthy", pr.required("m", contains("STATEMENT")))

    dispatch = pr.resolve("STATEMENT")

    assert dispatch.outcome == "claimed"
    assert dispatch.parser_id == "healthy"
    assert dispatch.exceptions == (pr.ParserFailure("detect_boom", "detect", "KeyError"),)


def test_a_crashing_detect_alone_is_parser_exception():
    """Nothing claimed, but we cannot say nothing WOULD have claimed."""
    register("detect_boom", detect_raises=TypeError)

    dispatch = pr.resolve("STATEMENT")

    assert dispatch.outcome == "parser_exception"
    assert dispatch.candidates == ()


def test_ambiguity_still_outranks_a_crash():
    """Two claimants is a resolvable registry fact; it stays the verdict."""
    register("detect_boom", detect_raises=ValueError)
    register("a", pr.required("m", contains("STATEMENT")))
    register("b", pr.required("m", contains("STATEMENT")))

    dispatch = pr.resolve("STATEMENT")

    assert dispatch.outcome == "ambiguous"
    assert [name for name, _ in dispatch.candidates] == ["a", "b"]
    assert dispatch.crashed == ("detect_boom",)


def test_declining_and_crashing_are_recorded_apart():
    """`attempted` keeps meaning "detected, then returned None"."""
    register("declining", pr.required("m", contains("STATEMENT")), parse=declines)
    register("detect_boom", detect_raises=ValueError)

    dispatch = pr.resolve("STATEMENT")

    assert dispatch.outcome == "parser_exception"
    assert dispatch.attempted == ("declining",)
    assert dispatch.crashed == ("detect_boom",)


def test_an_unclaimed_document_is_still_plain_unclaimed():
    """No crash, no change: the pre-W3-1 verdict is untouched."""
    register("a", pr.required("m", contains("SOMETHING ELSE")))

    assert pr.resolve("STATEMENT") == pr.Dispatch("unclaimed")


def test_detection_report_survives_a_crashing_registration():
    """Telemetry's near-miss sweep must not be what aborts a run."""
    register("detect_boom", detect_raises=ValueError)
    register("healthy", pr.required("m", contains("STATEMENT")))

    report = dict(pr.detection_report("STATEMENT"))

    assert report["detect_boom"].score == 0.0
    assert report["healthy"].claims


# ===========================================================================
# Sensitivity
# ===========================================================================

def test_only_the_exception_class_name_is_kept():
    """H3_SCHEMA I1: messages quote the document, class names cannot."""
    register("leaky", pr.required("m", contains("ACME")), parse=boom())

    dispatch = pr.resolve("ACME PLUMBING LLC ACCOUNT 12345")

    assert dispatch.exceptions == (pr.ParserFailure("leaky", "parse", "ValueError"),)
    assert "ACME" not in repr(dispatch.exceptions)
    assert "cannot handle" not in repr(dispatch.exceptions)


def test_process_level_exceptions_still_propagate():
    """KeyboardInterrupt/SystemExit are about the process, not the parser."""
    register("interrupted", pr.required("m", contains("STATEMENT")), parse=boom(KeyboardInterrupt))

    with pytest.raises(KeyboardInterrupt):
        pr.resolve("STATEMENT")


# ===========================================================================
# Failure-mode coverage of the real crash classes
# ===========================================================================

@pytest.mark.parametrize("exception", [AttributeError, ValueError, TypeError, IndexError, KeyError, ZeroDivisionError])
def test_every_discovery_crash_class_fails_closed(exception):
    """The two clusters discovery found (AttributeError x36, ValueError x17)
    plus the neighbouring shapes a parser can reach. None of them escapes, and
    none of them produces a statement."""
    register("broken", pr.required("m", contains("STATEMENT")), parse=boom(exception))

    dispatch = pr.resolve("STATEMENT")

    assert dispatch.outcome == "parser_exception"
    assert dispatch.statement is None
    assert dispatch.exceptions[0].exception == exception.__name__
