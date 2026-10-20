"""Phase 2.0 composition pins (Ocean, the train10 composition of the five cells).

The one item the cells could not own jointly: P20-SURFACES raises
`Q3ProvenanceRefused` when the Q3 sibling-omission class is asked to admit a
section on non-native provenance; `_guarded` records the CLASS NAME as a parser
failure; and `discovery/runner.py::_failure_reason` (cell A's file) must give
that refusal its own reason token so `rows.csv` can tell a policy refusal from
a crash (P20-SURFACES review MAJOR-2, deferred to composition).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from discovery.runner import _failure_reason


def _dispatch(outcome: str, *exception_names: str, attempted=()):
    exceptions = [
        SimpleNamespace(parser_id="member_statement_rollup", stage="parse", exception=name)
        for name in exception_names
    ]
    return SimpleNamespace(outcome=outcome, exceptions=exceptions, attempted=list(attempted))


def test_a_q3_provenance_refusal_has_its_own_reason_token():
    dispatch = _dispatch("parser_exception", "Q3ProvenanceRefused")
    assert _failure_reason("ParserCrashError", dispatch) == "q3_provenance_refused"


def test_an_ordinary_parser_crash_keeps_the_crash_token():
    dispatch = _dispatch("parser_exception", "ValueError")
    assert _failure_reason("ParserCrashError", dispatch) == "parser_exception"


def test_the_refusal_token_is_decided_by_class_name_only():
    # A refusal recorded beside an unrelated crash still names the refusal —
    # the reader's question is "was this document refused on provenance", and
    # the answer is yes.
    dispatch = _dispatch("parser_exception", "ValueError", "Q3ProvenanceRefused")
    assert _failure_reason("ParserCrashError", dispatch) == "q3_provenance_refused"


def test_the_other_branches_are_untouched():
    assert _failure_reason(None, None) is None
    assert _failure_reason("AmbiguousParserError", None) == "parser_ambiguous"
    assert _failure_reason("RuntimeError", _dispatch("unclaimed")) == "no_parser_matched"
    assert _failure_reason("RuntimeError", _dispatch("unclaimed", attempted=["x"])) == "parser_declined"
    assert _failure_reason("RuntimeError", None) == "exception"


def test_the_token_is_reachable_end_to_end_through_the_real_pipeline():
    """The real seam: a Q3-class document whose header names a non-native
    extractor is refused, and the runner's reason mapping names the refusal."""
    from analysis.parser_registry import ParserCrashError
    from analysis.pipeline import analyze_document
    from telemetry.collect import DispatchCollector

    q3 = pytest.importorskip("tests.test_q3_native_only")
    collector = DispatchCollector()
    with pytest.raises(ParserCrashError):
        analyze_document(
            q3._q3_document("local-tesseract-ocr"),
            parse_mode="deterministic",
            on_dispatch=collector,
        )
    assert collector.dispatch.outcome == "parser_exception"
    assert _failure_reason("ParserCrashError", collector.dispatch) == "q3_provenance_refused"
