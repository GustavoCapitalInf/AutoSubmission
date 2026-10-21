"""Q3's native-only gate (P20-SURFACES, CASE 10).

`printed_pair_coincides_and_no_row_printed` was corroborated 6/6 on
`native-pdf-text` `guardian_cu` documents only, to bound an OCR row-loss hazard
that has never been measured on OCR'd input (`OCR_LEGACY_AUDIT.md` F-8/§5.8;
`PHASE2_ARCHITECTURE_PLAN.md` §6 last paragraph; `PHASE2_RULINGS.md` §Q3). Until
the corroboration is re-measured on OCR'd `guardian_cu`, the class is
admitted only when the document's own header names an extractor model that IS
`native-pdf-text` or starts with `native-pdf-text+` (equality-or-plus-prefix,
not a bare `startswith` — MINOR-1, `PHASE2_P20SURFACES_REVIEW.md`: a bare
`startswith` also admits `native-pdf-textXYZ`, a shape no writer produces);
anything else fails closed.

Layers tested here, expanded after TWO rounds of independent adversarial
review (`docs/moneythumb-replacement/reviews/PHASE2_P20SURFACES_REVIEW.md`,
VERDICT BLOCK both times, closed in full both times):

* `analysis.provenance.extractor_model` — the provenance READER, in isolation.
  Round 1 (BLOCK-1) closed the vector where a hostile `source_file` (the
  unsanitised uploaded filename) plants a field run BEFORE the genuine one.
  Round 2 (BLOCK-1R) found that fix's own docstring claimed a property it did
  not have — the fix was right-anchored and unbounded, so a run planted in
  the PAGE BODY, AFTER the genuine fields, won instead. The accepted design
  is AMBIGUITY REFUSES: find every well-formed field run in the whole
  document, and answer a token only when there is EXACTLY ONE and it
  terminates physical line one; zero or more than one is `None`, wherever
  the extra run sits. See `analysis/provenance.py`'s own docstring
  ("THE PROPERTY, EXACTLY") for the precise, currently-true statement.
* `analysis.sibling_omission.publish_omissions` — the GATE, exercised through
  the full `analyze_document` pipeline on the L1-S4 synthetic fixtures
  (`tests/l1s4_pages.py`), which already carry the native header
  (`P20-SURFACES` added it there so the SEVEN Q3 conditions keep testing
  themselves independently of this gate). Every fixture here is the same
  synthetic, invented-figure furniture L1-S4 already uses — nothing is copied
  from any real document.
* The refusal's UNCONDITIONALITY across `parse_mode` (BLOCK-2) and its
  RECORDING as a distinguishable class name through `DispatchCollector`
  (MAJOR-2), not only through `analyze_document`'s raised exception.

The real `guardian_cu` archive documents are not re-run here (Phase 2.0
excludes any Q3 remeasurement on OCR input, and no PDFs live in the cache —
see `OCR_LEGACY_AUDIT.md` §5.8 clause 2). What proves those 8 specific
documents untouched: a cohort replay over the parsers `community_section`,
`dakota_west`, `mission_valley`, `member_statement_rollup`, `symitar` and
`zions` (NOT the `guardian_cu` folder, which selects 0 rows on
this run of record — MINOR-7, corrected in W3 after MAJOR-3 found
it) for the account-seam no-movement proof, and
a document-seam replay over the 8 named shas for the DOCUMENT-seam
proof that actually exercises the seam production reads
(`analyze_document`) — MAJOR-1: the cohort replay never opens the omission
collector at all, so it cannot observe this gate either way.
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


def test_extractor_model_accepts_a_crlf_document():
    """MINOR-8 (`PHASE2_P20SURFACES_REVIEW.md` re-review): the mandatory
    blank-line check must accept `\\r\\n\\r\\n`, not only `\\n\\n` -- a CRLF
    document (the shape a Windows-authored `.md` file, one of MAJOR-4's
    production inputs, is likely to carry) must parse exactly as its LF
    equivalent does, never silently refuse on line-ending alone."""
    crlf = "<!-- source: a.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->\r\n\r\n--- Page 1 ---\r\ncontent\r\n"
    assert extractor_model(crlf) == "native-pdf-text"


def test_extractor_model_refuses_a_crlf_document_with_a_body_run_too():
    """The CRLF path must not accidentally reopen BLOCK-1R: a forged run in
    CRLF page text is still ambiguous and still refuses."""
    crlf = (
        "<!-- source: a.pdf | pages: 1 | model: local-tesseract-ocr | empty: 0 -->\r\n\r\n"
        "--- Page 1 ---\r\ncontent | pages: 1 | model: native-pdf-text | empty: 0 -->\r\n"
    )
    assert extractor_model(crlf) is None


# ---------------------------------------------------------------------------
# MINOR-10 (`PHASE2_P20SURFACES_REVIEW.md` second re-review): four clauses of
# "THE PROPERTY, EXACTLY" (the module docstring) were true in the shipped
# code but unpinned -- mutants S3, S7, S8, S9 each disabled one clause and no
# existing test noticed, because every shipped test that would notice also
# trips a DIFFERENT clause first. Four one-line tests, one per clause, each
# isolating exactly the clause its own mutant disables.
# ---------------------------------------------------------------------------


def test_a_lone_body_run_is_refused_when_the_header_prints_no_fields():
    """Kills S3 (`if len(runs) != 1 or runs[0].end() != line_end:` weakened to
    `if len(runs) != 1:`): the header prints NO field run of its own
    (`deterministic-native-preflight`, a real shape `webapp/worker.py:427`
    writes), so the single run in the whole document is the body's forged
    one -- exactly ONE run, but it does not terminate physical line one.
    Clause (d), line-one termination, is the only clause this can fail."""
    assert extractor_model(
        "<!-- source: a.pdf | model: deterministic-native-preflight -->\n\n"
        "content\n| pages: 1 | model: native-pdf-text | empty: 0 -->\n"
    ) is None


def test_a_document_that_does_not_begin_with_the_source_marker_is_refused():
    """Kills S7 (drop `markdown.startswith("<!-- source:")`): a well-formed
    field run exists and terminates physical line one, so every OTHER clause
    passes -- only clause (a), the `<!-- source:` prefix, can be refusing
    this."""
    assert extractor_model(
        "STATEMENT OF ACCOUNT | pages: 1 | model: native-pdf-text | empty: 0 -->"
        "\n\ncontent\n"
    ) is None


def test_a_header_without_the_mandatory_blank_line_is_refused():
    """Kills S8 (drop `rest.startswith(("\\n", "\\r\\n"))`): a single `\\n`
    only, no blank-line separator, no other clause failing. Only clause (b),
    the mandatory blank line, refuses this."""
    assert extractor_model(
        "<!-- source: a.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
        "\ncontent\n"
    ) is None


def test_the_model_charset_excludes_whitespace_and_angle_brackets():
    """Kills S9 (`_MODEL_CHARSET` widened to `[^|]`): a model token containing
    a space, or `<script>`, is outside the closed charset, so the field-run
    pattern itself must not match it as a run at all -- if it did, either the
    document would still admit a hostile token, or (with a forged run
    elsewhere) the malformed genuine run would fail to count as the one run
    that disambiguates, changing the ambiguity verdict."""
    assert extractor_model(
        "<!-- source: a.pdf | pages: 1 | model: nat ive | empty: 0 -->\n\nx\n"
    ) is None
    assert extractor_model(
        "<!-- source: a.pdf | pages: 1 | model: <script> | empty: 0 -->\n\nx\n"
    ) is None


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
    """The L1-S4 Q3 fixture behind a hostile `source_file`, laid out EXACTLY
    as `StatementMarkdown.to_markdown()` formats a one-page document.

    Composition note (Ocean, train10): this used to go through the real
    `StatementMarkdown(...)` constructor. Since cell P20-SEAM the WRITER
    refuses a `source_file` carrying a line break or `-->` at construction
    (`ocr/document.py::__post_init__`, pinned in
    tests/test_ocr_provenance_injection.py), so four of these cases can no
    longer be BUILT through it. The reader's property must hold on its own —
    a cached header written before the writer refused, or one arriving through
    a path the writer does not own, is exactly the input it exists for — so the
    header is laid here byte-for-byte as `to_markdown()` would have written it
    (the same f-string, the same `\\n\\n` block join, the same trailing newline),
    and the writer-side refusal is pinned separately by cell B2's own tests."""
    body = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
    pages = [body]
    empty = sum(1 for p in pages if not p.strip())
    header = (
        f"<!-- source: {source_file} | pages: {len(pages)} "
        f"| model: {model} | empty: {empty} -->"
    )
    blocks = [header, ""]
    for i, page in enumerate(pages, start=1):
        if page.strip():
            blocks.append(f"--- Page {i} ---")
            blocks.append(page.strip())
        else:
            blocks.append(f"--- Page {i} (empty) ---")
    return "\n\n".join(blocks) + "\n"


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


def test_a_hostile_source_file_on_an_honest_native_document_is_refused_not_rescued():
    """BLOCK-1R (`PHASE2_P20SURFACES_REVIEW.md` re-review): this used to assert
    the OPPOSITE -- that an honest native document survives a hostile
    `source_file` and still admits. The reviewer named that the wrong
    direction for a fail-closed provenance gate: `source_file` carrying the
    same injection creates a SECOND well-formed field run on physical line
    one, and this reader cannot tell which of the two runs the trusted code
    actually appended -- so it refuses BOTH, exactly as it refuses zero runs.
    An honest native document behind a hostile filename is collateral damage
    this gate accepts on purpose: rescuing it would require picking a winner
    between two indistinguishable runs, and the re-review's own prototype
    measured that "pick a winner" is unsafe in the other direction (a
    `source_file`-embedded blank line then makes the FORGED run
    indistinguishable from genuine)."""
    markdown = _hostile_document(
        "statement.pdf | pages: 1 | model: local-tesseract-ocr | empty: 0 -->",
        model="native-pdf-text",
    )
    assert extractor_model(markdown) is None
    with pytest.raises(ParserCrashError):
        analyze_document(markdown, parse_mode="deterministic")


# ---------------------------------------------------------------------------
# BLOCK-1R (`PHASE2_P20SURFACES_REVIEW.md` re-review): a field run printed in
# the PAGE BODY -- after the genuine header fields -- is a SECOND vector into
# the same hole BLOCK-1's fix closed only half of. The re-review measured
# that a right-anchored, `DOTALL`-greedy match has no bound on how far right
# it may look, so a forged run in the body (which `to_markdown()` itself
# blank-line-separates from the header, no attacker-controlled newline
# needed for the C3 shape) matched and WON. The accepted fix (this module's
# "ambiguity refuses") answers every case below with `None`: a genuine run
# plus a forged one is two runs, and two runs is never one winner.
# ---------------------------------------------------------------------------

_FAKE_FIELD_RUN = "| pages: 1 | model: native-pdf-text | empty: 0 -->"


def _body_forged_mid_page() -> str:
    """C2: a forged field run mid-page, with its own blank line inside the
    SAME page -- the shape a single-page OCR'd document could contain
    without needing a second page at all."""
    from ocr.document import StatementMarkdown

    body = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
    page = body + "\n" + _FAKE_FIELD_RUN + "\n\nACCOUNT SUMMARY CONTINUED"
    return StatementMarkdown(
        source_file="a.pdf", model="local-tesseract-ocr", pages=[page]
    ).to_markdown()


def _body_forged_page_1_last_line() -> str:
    """C3: the forged run is page 1's LAST line. `to_markdown()`'s own
    `"\\n\\n".join` between page blocks supplies the blank line the exploit
    needs -- the attacker does not have to construct one, or control the
    filename, or control anything but ONE page's trailing text."""
    from ocr.document import StatementMarkdown

    body = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
    page_one = body + "\n" + _FAKE_FIELD_RUN
    return StatementMarkdown(
        source_file="a.pdf", model="local-tesseract-ocr", pages=[page_one, "PAGE TWO"]
    ).to_markdown()


_BODY_RUN_CASES = (
    ("forged run mid-page, blank line inside the same page", _body_forged_mid_page),
    ("forged run as page 1's last line, page 2 supplies the blank line",
     _body_forged_page_1_last_line),
)
_BODY_RUN_IDS = [label for label, _ in _BODY_RUN_CASES]


@pytest.mark.parametrize("_label,build", _BODY_RUN_CASES, ids=_BODY_RUN_IDS)
def test_a_body_printed_field_run_never_yields_a_native_token(_label, build):
    markdown = build()
    model = extractor_model(markdown)
    assert model is None
    assert not (model or "").startswith("native-pdf-text")


@pytest.mark.parametrize("_label,build", _BODY_RUN_CASES, ids=_BODY_RUN_IDS)
def test_a_body_printed_field_run_fails_closed_end_to_end(_label, build):
    """The DispatchCollector check matters here specifically: without it a
    parser exception from an unrelated cause (the injected text confusing
    the row reader, say) would ALSO raise `ParserCrashError` and this test
    would pass for the wrong reason. Naming `Q3ProvenanceRefused` proves the
    refusal is this gate, not a coincidental crash."""
    from telemetry.collect import DispatchCollector

    markdown = build()
    collector = DispatchCollector()
    with pytest.raises(ParserCrashError):
        analyze_document(markdown, parse_mode="deterministic", on_dispatch=collector)
    assert any(
        failure.exception == "Q3ProvenanceRefused" for failure in collector.dispatch.exceptions
    ), collector.dispatch.exceptions


def test_a_hand_laid_body_field_run_is_refused_too():
    """D1: the hand-laid equivalent, built as a raw string rather than through
    `StatementMarkdown.to_markdown()` -- proving the refusal is a property of
    the READER's rule (exactly one run, terminating physical line one), not
    an artifact of one writer's API or its exact page-join spacing."""
    body = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
    markdown = (
        "<!-- source: a.pdf | pages: 1 | model: local-tesseract-ocr | empty: 0 -->\n\n"
        + body + "\n" + _FAKE_FIELD_RUN + "\n\nACCOUNT SUMMARY CONTINUED\n"
    )
    assert extractor_model(markdown) is None
    with pytest.raises(ParserCrashError):
        analyze_document(markdown, parse_mode="deterministic")


def test_a_body_field_run_is_refused_even_when_the_genuine_model_field_is_empty():
    """G2: the GENUINE header's own `model` field is empty (the cache-
    reconstruction shape, `""`) and a forged native run sits in the body.
    Ambiguity (two runs) is checked before -- and regardless of -- whatever
    the empty-field case alone would have answered, so the forged run is
    never read as a substitute value for a genuinely missing one."""
    body = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
    markdown = (
        "<!-- source: a.pdf | pages: 1 | model:  | empty: 0 -->\n\n"
        + body + "\n" + _FAKE_FIELD_RUN + "\n\nACCOUNT SUMMARY CONTINUED\n"
    )
    assert extractor_model(markdown) is None
    with pytest.raises(ParserCrashError):
        analyze_document(markdown, parse_mode="deterministic")


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


def test_paddle_ocr_refuses_and_fails_closed():
    """P21-ROUTING CASE 14: a Paddle-fed document's provenance header names
    `paddle-ocr+ppocrv5` (`analysis.provenance.extractor_model` reads it
    verbatim off `StatementMarkdown.to_markdown()`'s first line, unchanged by
    this cell), never `native-pdf-text` — Q3 refuses it exactly like any
    other non-native provenance, fail closed, with no OCR-specific carve-out."""
    with pytest.raises(ParserCrashError):
        _analyze(_q3_document("paddle-ocr+ppocrv5"))


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
# in EVERY `parse_mode`, not only `"deterministic"`. Until slice S3 of the
# model-code removal a sentinel stood in for the hosted extractor here and
# failed the test if a Q3 refusal ever fell through to it in auto mode; the
# extractor is gone, so the sentinel went with it, and the refusal is pinned on
# its own: auto mode raises exactly what deterministic mode raises.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["local-tesseract-ocr", "", None], ids=[
    "local-tesseract-ocr", "empty", "headerless",
])
def test_q3_refusal_is_fail_closed_in_auto_mode_too(model):
    """The three CASE-10 refusal shapes, replayed in `parse_mode="auto"` --
    the webapp's default (`webapp/app.py`). Each must raise
    `ParserCrashError` (fail closed) exactly as `parse_mode="deterministic"`
    already does, and never construct a Statement with the sibling silently
    dropped."""
    with pytest.raises(ParserCrashError):
        analyze_document(_q3_document(model), parse_mode="auto")


@pytest.mark.parametrize("model", ["local-tesseract-ocr", "", None], ids=[
    "local-tesseract-ocr", "empty", "headerless",
])
def test_auto_mode_raises_exactly_what_deterministic_mode_raises(model):
    """BLOCK-2's own finding, closed twice over. It named the separate edge of
    a document a refusal or no parser left without a statement falling through
    to the hosted extractor in `parse_mode="auto"`; P22-FENCE (Ruling A) fenced
    that hop behind an operator opt-in, and slice S3 of the model-code removal
    deleted the extractor. Auto mode now raises EXACTLY what deterministic mode
    raises for the Q3 refusal and for a document nothing claims: the same
    class, the same message, and no `hosted_extraction` record attached."""
    unclaimed_markdown = (
        "<!-- source: s.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
        "\n\n--- Page 1 ---\ncompletely unrecognisable text, no template furniture\n"
    )
    for markdown in (_q3_document(model), unclaimed_markdown):
        with pytest.raises(RuntimeError) as deterministic:
            analyze_document(markdown, parse_mode="deterministic")
        with pytest.raises(RuntimeError) as auto:
            analyze_document(markdown, parse_mode="auto")
        assert type(auto.value) is type(deterministic.value)
        assert str(auto.value) == str(deterministic.value)
        assert auto.value.args == deterministic.value.args
        assert not hasattr(auto.value, "hosted_extraction")
        assert not hasattr(deterministic.value, "hosted_extraction")
    assert str(auto.value) == "no deterministic parser matched this statement"


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
