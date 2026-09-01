"""Q3's native-only gate (P20-SURFACES, CASE 10).

`printed_pair_coincides_and_no_row_printed` was corroborated 6/6 on
`native-pdf-text` `guardian_cu` documents only, to bound an OCR row-loss hazard
that has never been measured on OCR'd input (`OCR_LEGACY_AUDIT.md` F-8/§5.8;
`PHASE2_ARCHITECTURE_PLAN.md` §6 last paragraph; `PHASE2_RULINGS.md` §Q3). Until
`tools/q3_corroboration_probe.py` is re-run on OCR'd `guardian_cu`, the class is
admitted only when the document's own first-line provenance header names an
extractor model starting with `native-pdf-text`; anything else fails closed.

Two layers are tested here:

* `analysis.provenance.extractor_model` — the provenance READER, in isolation,
  proven to read the first line and only the first line.
* `analysis.sibling_omission.publish_omissions` — the GATE, exercised through
  the full `analyze_document` pipeline on the L1-S4 synthetic fixtures
  (`tests/l1s4_pages.py`), which already carry the native header
  (`P20-SURFACES` added it there so the SEVEN Q3 conditions keep testing
  themselves independently of this gate). Every fixture here is the same
  synthetic, invented-figure furniture L1-S4 already uses — nothing is copied
  from any real document.

The real `guardian_cu` archive documents are not re-run here (Phase 2.0
excludes any Q3 remeasurement on OCR input, and no PDFs live in the cache —
see `OCR_LEGACY_AUDIT.md` §5.8 clause 2); `tools/cohort_replay.py --folder
guardian_cu` at base and at closure is what proves those specific documents are
untouched.
"""
from __future__ import annotations

import pytest

from analysis.parser_registry import ParserCrashError
from analysis.pipeline import analyze_document
from analysis.provenance import extractor_model
from analysis.serialization import document_report_to_dict
from analysis.sibling_omission import (
    PRINTED_DORMANCY_DECLARATION,
    PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED,
    Q3_CLASS_REQUIRES_NATIVE_PROVENANCE,
    SiblingOmission,
    collecting,
    publish_omissions,
)
from telemetry.record import classify_outcome
from tests.l1s4_pages import document, idle_account, posting_account
from tests.test_symitar import ACTIVE as SYM_ACTIVE
from tests.test_symitar import DORMANT as SYM_DORMANT
from tests.test_symitar import HEAD as SYM_HEAD

# ---------------------------------------------------------------------------
# `extractor_model` in isolation: reads line 1, and only line 1
# ---------------------------------------------------------------------------


def test_extractor_model_reads_the_first_line_header():
    markdown = (
        "<!-- source: a.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->\n"
        "\n--- Page 1 ---\nStatement Dates: 04/01/55 - 04/30/55\n"
    )
    assert extractor_model(markdown) == "native-pdf-text"


def test_extractor_model_admits_a_layout_suffix_as_the_whole_token():
    """The ruling reads `native-pdf-text*`; the reader hands back the FULL
    token and leaves the prefix decision to its caller."""
    markdown = "<!-- source: a.pdf | pages: 1 | model: native-pdf-text+guardian | empty: 0 -->\n"
    assert extractor_model(markdown) == "native-pdf-text+guardian"


def test_extractor_model_returns_none_without_a_header():
    """No header at all -- the no-header mutant's positive control."""
    assert extractor_model("Statement Dates: 04/01/55 - 04/30/55\n") is None


def test_extractor_model_returns_none_for_an_empty_document():
    assert extractor_model("") is None
    assert extractor_model(None) is None


def test_extractor_model_never_reads_past_the_first_line():
    """The line-2 mutant's kill: a header on line two must NOT be found. A
    reader that scanned the whole document (or used MULTILINE `^`) would find
    this header and return its token; this one must return `None`."""
    markdown = (
        "some other first line, not a header\n"
        "<!-- source: a.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->\n"
    )
    assert extractor_model(markdown) is None


def test_extractor_model_returns_none_for_an_empty_model_field():
    """The `\"\"` mutant's positive control on the reader itself."""
    assert extractor_model("<!-- source: a.pdf | pages: 1 | model:  | empty: 0 -->\n") is None


# ---------------------------------------------------------------------------
# the gate, through the full pipeline
# ---------------------------------------------------------------------------


def _q3_document(model: str | None = "native-pdf-text") -> str:
    """The L1-S4 Q3 fixture (idle + posting sibling), with its header's model
    token set to `model`, or removed entirely when `model` is `None`."""
    text = document([idle_account(), posting_account()])
    assert "model: native-pdf-text |" in text.split("\n", 1)[0]
    if model is None:
        # Drop the header line and the blank line under it, leaving exactly
        # the body `tests/l1s4_pages.py` printed before this gate existed.
        return text.split("\n\n", 1)[1]
    return text.replace("model: native-pdf-text |", f"model: {model} |", 1)


def _analyze(text: str):
    return analyze_document(text, parse_mode="deterministic")


def test_native_pdf_text_admits_the_q3_omission():
    """The existing pin, restated as CASE 10's positive control: a native
    header admits the class, and the account beside it stays validated."""
    document_report = _analyze(_q3_document("native-pdf-text"))
    assert [o.reason for o in document_report.omissions] == [
        PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED
    ]
    payload = document_report_to_dict(document_report)
    assert classify_outcome(payload)[0] == "validated"


def test_a_native_layout_suffix_is_still_admitted():
    """`native-pdf-text+guardian` -- a native read carrying its own layout
    suffix -- is admitted exactly as plain `native-pdf-text` is."""
    document_report = _analyze(_q3_document("native-pdf-text+guardian"))
    assert [o.reason for o in document_report.omissions] == [
        PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED
    ]


def test_local_tesseract_ocr_refuses_and_fails_closed():
    """CASE 10: the SAME text, OCR-attributed, is refused -- fail closed, not
    a silent admission and not a partial document."""
    with pytest.raises(ParserCrashError):
        _analyze(_q3_document("local-tesseract-ocr"))


def test_header_removed_refuses_and_fails_closed():
    """CASE 10: no provenance header at all -- absence refuses, the direction
    L1-C17 already reads every other omission class fail-closed in."""
    with pytest.raises(ParserCrashError):
        _analyze(_q3_document(None))


def test_empty_model_token_refuses_and_fails_closed():
    """Mutation-table entry: 'Q3 admitted on model \"\"' is killed here."""
    with pytest.raises(ParserCrashError):
        _analyze(_q3_document(""))


def test_the_refusal_is_the_same_shape_l1_c17_uses_for_an_unratified_reason():
    """Cites the exact mechanism: `analysis.parser_registry.ParserCrashError`,
    raised because `_guarded` (`analysis/parser_registry.py:839-855`) caught an
    exception from the claiming registration's `parse` and no other claimant
    published -- the identical fail-closed path
    `SiblingOmission.__post_init__`'s `ValueError` for a reason outside
    `EVIDENCE_CLASSES` takes today. `ParserCrashError` subclasses
    `RuntimeError` (`analysis/parser_registry.py:127`), the same base class
    `tests/test_l1s2_omission_ruling.py::test_the_document_is_refused_rather_
    than_published_short` asserts for the sibling-boundary refusal. Only the
    exception CLASS crosses `_guarded`'s boundary (`ParserFailure` stores no
    message, by the same privacy discipline the sibling omission machinery
    already applies elsewhere), so this asserts the shape rather than the
    withheld text."""
    from analysis.parser_registry import ParserFailure

    with pytest.raises(ParserCrashError) as excinfo:
        _analyze(_q3_document("local-tesseract-ocr"))
    assert all(isinstance(f, ParserFailure) for f in excinfo.value.failures)
    assert all(f.exception == "ValueError" for f in excinfo.value.failures)


def test_the_refusal_token_is_named_in_the_raised_message():
    """`publish_omissions`, exercised directly (below `_guarded`'s message-
    swallowing boundary): the refusal names
    `q3_class_requires_native_provenance`, satisfying the card's requirement
    to record the token somewhere on the refusal -- here, as the message
    `SiblingOmission`'s own construction-time refusal (`__post_init__`) uses
    the same way, since this closed vocabulary has no separate refusal-reason
    enum of its own to extend."""
    omission = SiblingOmission("SAMPLE SHARE", PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED, 0)
    header = "<!-- source: a.pdf | pages: 1 | model: local-tesseract-ocr | empty: 0 -->\n"
    with collecting(header):
        with pytest.raises(ValueError, match=Q3_CLASS_REQUIRES_NATIVE_PROVENANCE):
            publish_omissions([omission])


# ---------------------------------------------------------------------------
# the other three ratified classes are NOT gated
# ---------------------------------------------------------------------------


def test_the_dormancy_class_is_admitted_with_no_header_at_all():
    """Mutation-table entry: 'gate applied to printed_dormancy_declaration' is
    killed here. No header, and the class still admits -- this is the
    UNGATED behaviour every reader written before Q3 already relies on
    (`tests/test_l1s2_omission_ruling.py`), reasserted here as a direct
    contrast with the gated class above."""
    text = SYM_HEAD + SYM_ACTIVE + SYM_DORMANT
    assert not text.startswith("<!--")
    document_report = _analyze(text)
    assert [o.reason for o in document_report.omissions] == [
        PRINTED_DORMANCY_DECLARATION
    ]
    payload = document_report_to_dict(document_report)
    assert classify_outcome(payload)[0] == "validated"


def test_the_dormancy_class_is_admitted_under_a_non_native_header_too():
    """Stronger than the no-header case: even a header that would refuse Q3
    outright is irrelevant to this class, because this class is never asked."""
    text = (
        "<!-- source: a.pdf | pages: 1 | model: local-tesseract-ocr | empty: 0 -->\n\n"
        + SYM_HEAD + SYM_ACTIVE + SYM_DORMANT
    )
    document_report = _analyze(text)
    assert [o.reason for o in document_report.omissions] == [
        PRINTED_DORMANCY_DECLARATION
    ]
