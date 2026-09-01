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
    Q3ProvenanceRefused,
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
    markdown = "<!-- source: a.pdf | pages: 1 | model: native-pdf-text+guardian | empty: 0 -->\n\n"
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
    assert extractor_model("<!-- source: a.pdf | pages: 1 | model:  | empty: 0 -->\n\n") is None


# ---------------------------------------------------------------------------
# BLOCK-1 (`PHASE2_P20SURFACES_REVIEW.md`): `source_file` cannot supply the
# model. `source_file` is the uploaded filename -- attacker-supplied,
# unsanitised (`webapp/app.py` -> `webapp/worker.py` -> `ocr/document.py`) --
# so a header reader that stops at the FIRST `-->` on the line can be handed a
# fake, complete header by the filename alone, before the genuine trailing
# fields the trusted code always appends. Every case here builds the SAME
# real document (real model `local-tesseract-ocr`, non-native) behind a
# hostile `source_file`, and requires BOTH that `extractor_model` never
# reports `native-pdf-text*` for it AND that the Q3 class fails closed
# end-to-end through `analyze_document`.
# ---------------------------------------------------------------------------


def _hostile_document(source_file: str, *, model: str = "local-tesseract-ocr") -> str:
    """The L1-S4 Q3 fixture, wrapped in a REAL `StatementMarkdown.to_markdown()`
    call so `source_file` is interpolated exactly as `ocr/document.py` does
    it -- not a hand-typed approximation of the header."""
    from ocr.document import StatementMarkdown

    body = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
    return StatementMarkdown(source_file=source_file, model=model, pages=[body]).to_markdown()


_BLOCK1_HOSTILE_SOURCE_FILES = (
    ("the exact fake header from the review",
     "statement.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"),
    ("a bare closing marker", "evil--> statement.pdf"),
    ("a literal <", "evil<statement.pdf"),
    ("a literal >", "evil>statement.pdf"),
    ("an embedded newline", "evil\nstatement.pdf"),
    ("a second, nested header",
     "<!-- source: fake | pages: 1 | model: native-pdf-text | empty: 0 -->"),
)
_BLOCK1_IDS = [label for label, _ in _BLOCK1_HOSTILE_SOURCE_FILES]


@pytest.mark.parametrize("_label,source_file", _BLOCK1_HOSTILE_SOURCE_FILES, ids=_BLOCK1_IDS)
def test_a_hostile_source_file_never_yields_a_native_token(_label, source_file):
    markdown = _hostile_document(source_file)
    model = extractor_model(markdown)
    assert model != "native-pdf-text"
    assert not (model or "").startswith("native-pdf-text")


@pytest.mark.parametrize("_label,source_file", _BLOCK1_HOSTILE_SOURCE_FILES, ids=_BLOCK1_IDS)
def test_a_hostile_source_file_fails_closed_end_to_end(_label, source_file):
    markdown = _hostile_document(source_file)
    with pytest.raises(ParserCrashError):
        analyze_document(markdown, parse_mode="deterministic")


def test_a_hostile_source_file_still_reports_the_true_model_when_it_is_native():
    """The corroborating positive control: the fix must not make an honest
    native read collateral damage. A `source_file` carrying the exact same
    injection, on a document whose REAL model is native, still admits."""
    markdown = _hostile_document(
        "statement.pdf | pages: 1 | model: local-tesseract-ocr | empty: 0 -->",
        model="native-pdf-text",
    )
    assert extractor_model(markdown) == "native-pdf-text"
    report = analyze_document(markdown, parse_mode="deterministic")
    assert [o.reason for o in report.omissions] == [PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED]


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


def test_a_bare_concatenation_with_no_plus_is_refused():
    """MINOR-1 (`PHASE2_P20SURFACES_REVIEW.md`): `native-pdf-textXYZ` is a
    shape no writer in this tree produces (`ocr/native_text.py` writes only
    the bare token or a `+suffix` form). A bare `startswith("native-pdf-
    text")` would have admitted this; the equality-or-`+`-prefix check must
    refuse it, fail closed."""
    with pytest.raises(ParserCrashError):
        _analyze(_q3_document("native-pdf-textXYZ"))


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


def test_the_headerless_case_above_is_a_live_production_path_not_only_a_fixture_shape():
    """MAJOR-4 (`PHASE2_P20SURFACES_REVIEW.md`): `analyze.py:186-188`
    (`open(args.markdown).read() -> analyze_document(markdown)`, the CLI's own
    help calling its argument "Path to the OCR markdown file") and
    `batch.py:59-75,245-262` (`_read_source` returns `path.read_text()`
    verbatim for a non-`.pdf` input; the call site's own comment: "this CLI ...
    is a production caller (W3 §WIRING W4)") both hand `analyze_document` text
    that may carry NO header at all -- a hand-saved or post-stripped `.md`
    file, or any text file a user points either CLI at. On both, a Q3-class
    document that previously validated NOW fails closed, exactly as the
    `_q3_document(None)` fixture above does; this is that same shape, restated
    without a card fixture in between, so it stands as the disclosure the
    review asked for rather than only a positive-control shape. Both CLIs
    default `parse_mode="auto"` (neither passes `parse_mode` explicitly), so
    this also proves the direction is unchanged there."""
    headerless_markdown = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
    assert not headerless_markdown.startswith("<!--")
    with pytest.raises(ParserCrashError):
        analyze_document(headerless_markdown, parse_mode="auto")


def test_empty_model_token_refuses_and_fails_closed():
    """Mutation-table entry: 'Q3 admitted on model \"\"' is killed here."""
    with pytest.raises(ParserCrashError):
        _analyze(_q3_document(""))


# ---------------------------------------------------------------------------
# BLOCK-2 (`PHASE2_P20SURFACES_REVIEW.md`): the refusal must be unconditional
# in EVERY `parse_mode`, not only `"deterministic"`. `extract_statement` is
# replaced by a sentinel that FAILS THE TEST if it is ever called -- the
# webapp's default `parse_mode="auto"` must never reach a hosted-model
# extraction call for a document Q3's gate has already refused.
# ---------------------------------------------------------------------------


@pytest.fixture
def _extract_statement_must_not_be_called(monkeypatch):
    def _sentinel(markdown, *, settings=None, model=None):
        raise AssertionError(
            "extract_statement reached: a Q3 provenance refusal fell through "
            "to hosted extraction in a non-deterministic parse_mode (BLOCK-2)"
        )
    monkeypatch.setattr("analysis.pipeline.extract_statement", _sentinel)


@pytest.mark.parametrize("model", ["local-tesseract-ocr", "", None], ids=[
    "local-tesseract-ocr", "empty", "headerless",
])
def test_q3_refusal_is_fail_closed_in_auto_mode_too(
    model, _extract_statement_must_not_be_called
):
    """The three CASE-10 refusal shapes, replayed in `parse_mode="auto"` --
    the webapp's default (`webapp/app.py`) -- with `extract_statement` wired
    to fail the test if the refusal ever falls through to it. Each must raise
    `ParserCrashError` (fail closed) exactly as `parse_mode="deterministic"`
    already does, and never construct a Statement with the sibling silently
    dropped."""
    with pytest.raises(ParserCrashError):
        analyze_document(_q3_document(model), parse_mode="auto")


def test_the_preexisting_unclaimed_to_auto_fallthrough_is_unchanged():
    """BLOCK-2's own finding, pinned so this closure does not silently widen
    its own fix: a document NOTHING claims (`dispatch.outcome == "unclaimed"`,
    unrelated to Q3) still falls through to `extract_statement` in
    `parse_mode="auto"` exactly as it did before this card -- a separate,
    pre-existing edge Ocean is reporting to Gustavo, which this fix must not
    touch. `extract_statement` is stubbed to return a value rather than to
    fail the test, because reaching it here is the CORRECT, unchanged
    behaviour being pinned, not a defect."""
    import analysis.pipeline as pipeline
    from analysis.schema import Statement

    reached = []

    def _stub(markdown, *, settings=None, model=None):
        reached.append(True)
        return Statement()

    unclaimed_markdown = (
        "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
        "\n\n--- Page 1 ---\ncompletely unrecognisable text, no template furniture\n"
    )
    original = pipeline.extract_statement
    pipeline.extract_statement = _stub
    try:
        pipeline.analyze_document(unclaimed_markdown, parse_mode="auto")
    finally:
        pipeline.extract_statement = original
    assert reached, "the pre-existing unclaimed->auto fallthrough moved -- report, do not fix here"


def test_the_refusal_is_the_same_shape_l1_c17_uses_for_an_unratified_reason():
    """Cites the exact mechanism: `analysis.parser_registry.ParserCrashError`,
    raised because `_guarded` (`analysis/parser_registry.py:839-855`) caught an
    exception from the claiming registration's `parse` and no other claimant
    published -- the identical fail-closed path
    `SiblingOmission.__post_init__`'s `ValueError` for a reason outside
    `EVIDENCE_CLASSES` takes today. `ParserCrashError` subclasses
    `RuntimeError` (`analysis/parser_registry.py:127`), the same base class
    `tests/test_l1s2_omission_ruling.py::test_the_document_is_refused_rather_
    than_published_short` asserts for the sibling-boundary refusal.

    MAJOR-2 (`PHASE2_P20SURFACES_REVIEW.md`): the CLASS that crosses
    `_guarded`'s boundary (`ParserFailure` stores no message, by the same
    privacy discipline the sibling omission machinery already applies
    elsewhere) is now `Q3ProvenanceRefused`, not the generic `ValueError` a
    genuine crash would also produce -- so a reader of `dispatch.exceptions`
    (or `rows.csv`'s `parser_exceptions` column, which formats this tuple
    verbatim) can tell a POLICY refusal apart from our own code breaking,
    which a bare `ValueError` could never do."""
    from analysis.parser_registry import ParserFailure

    with pytest.raises(ParserCrashError) as excinfo:
        _analyze(_q3_document("local-tesseract-ocr"))
    assert all(isinstance(f, ParserFailure) for f in excinfo.value.failures)
    assert all(f.exception == "Q3ProvenanceRefused" for f in excinfo.value.failures)


def test_dispatch_records_the_refusal_class_name_not_a_generic_parser_crash():
    """MAJOR-2's own required proof, through `DispatchCollector` -- the same
    seam `discovery/runner.py` observes a live dispatch through -- rather than
    below `_guarded`'s boundary. `dispatch.exceptions` carries
    `ParserFailure(parser_id, stage, exception)` and `discovery/runner.py`
    formats each one as `f"{parser_id}:{stage}:{exception}"` into the
    `parser_exceptions` row column (cited, not touched -- `discovery/runner.py`
    belongs to cell A; the `_failure_reason` -> `rows.csv` reason-token mapping
    that would let a report DISTINGUISH this from an ordinary crash is Ocean's
    to add at composition, not this card's)."""
    from telemetry.collect import DispatchCollector

    collector = DispatchCollector()
    with pytest.raises(ParserCrashError):
        analyze_document(
            _q3_document("local-tesseract-ocr"),
            parse_mode="deterministic",
            on_dispatch=collector,
        )
    assert collector.dispatch.outcome == "parser_exception"
    formatted = [
        f"{failure.parser_id}:{failure.stage}:{failure.exception}"
        for failure in collector.dispatch.exceptions
    ]
    assert any(entry.endswith(":parse:Q3ProvenanceRefused") for entry in formatted), formatted


def test_the_refusal_token_is_named_in_the_raised_message():
    """`publish_omissions`, exercised directly (below `_guarded`'s message-
    swallowing boundary): the refusal names
    `q3_class_requires_native_provenance` in its message, satisfying the
    card's original requirement to record the token somewhere on the refusal.
    MAJOR-2 is what a PRODUCTION reader can actually observe (the class name,
    proven above) -- this message is real but reaches no consumer beyond a
    test or a debugger attached at the raise site, and the docstring says so
    rather than calling this proof of anything a reader downstream can see."""
    omission = SiblingOmission("SAMPLE SHARE", PRINTED_PAIR_COINCIDES_AND_NO_ROW_PRINTED, 0)
    header = "<!-- source: a.pdf | pages: 1 | model: local-tesseract-ocr | empty: 0 -->\n\n"
    with collecting(header):
        with pytest.raises(Q3ProvenanceRefused, match=Q3_CLASS_REQUIRES_NATIVE_PROVENANCE):
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
