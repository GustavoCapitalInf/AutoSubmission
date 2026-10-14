from __future__ import annotations
from evidence.native import native_evidence_from_pdf
from .document import StatementMarkdown, native_evidence_describes
from .inspect import DocumentProfile, inspect_pdf
from .local_tesseract import parse_local_tesseract
from .truncation import assess_pages
# The native-text rung ladder, defined ONCE in `ocr/native_text.py` (see
# `native_statement` there for the rung order and the two drifts that paid for
# consolidating it). It is bound here under `_native_statement` — the name
# `parse_statement` has always called and the suite monkeypatches — so the only
# thing that changed is where the ladder lives.
from .native_text import native_statement as _native_statement

#: The fixed refusal for a call that still asks for the visual OCR rung. The
#: rung (the Unlimited-OCR client on a GPU server) was removed by the owner's
#: ruling of 2026-10-13: the product uses no model.
VISUAL_OCR_REMOVED = (
    "parse_statement: the visual OCR rung was removed (the product uses no model); "
    "allow_visual_ocr must be False"
)

#: The fixed refusal for `force_ocr=True` outside the Paddle branch. Forcing
#: used to mean "skip the offline rungs and go straight to the visual rung";
#: with that rung gone, a forced call that names no Paddle read has no rung to
#: run, and it refuses instead of silently answering None.
FORCED_OCR_NEEDS_PADDLE = (
    "parse_statement: force_ocr=True reads only through the Paddle rung "
    "(allow_paddle_ocr=True); the visual OCR rung it used to force was removed"
)


def _notify_stage(on_stage, rung: str) -> None:
    if on_stage is not None:
        on_stage(rung)


def parse_statement(pdf_bytes: bytes, source_file: str = "", *, dpi: int = 300,
                    on_page_replace=None,
                    force_ocr: bool = False,
                    allow_local_ocr: bool = False,
                    allow_visual_ocr: bool = False,
                    allow_paddle_ocr: bool = False,
                    paddle_data_scope: str | None = None,
                    profile: DocumentProfile | None = None,
                    on_stage=None) -> StatementMarkdown | None:
    """The single intake ladder (O-1): native text -> local Tesseract, driven by
    the preflight DocumentProfile. Every parameter after `source_file` is
    keyword-only.

    Capability flags preserve each caller's historical behavior exactly:
    `allow_local_ocr` (default False) gates the Tesseract rung, which has only
    ever existed for the webapp — the CLI (`parse.py`) does not silently gain
    an OCR stage it never had. When the offline rungs read nothing the return
    value is None. `on_stage(rung)` reports "native" / "local_ocr" /
    "paddle_ocr" as each rung starts, so callers can surface progress without
    owning routing. `on_page_replace(page_index, text)` receives every page of
    the offline read the ladder returns.

    The visual OCR rung is gone (owner ruling, 2026-10-13: the product uses no
    model). `allow_visual_ocr` stays a parameter because callers and the cache
    key still name it, defaults to False, and True is a `ValueError`
    (`VISUAL_OCR_REMOVED`). `force_ocr=True` used to skip straight to that
    rung; it now reads only through the Paddle branch below, and
    `force_ocr=True` without `allow_paddle_ocr` is a `ValueError`
    (`FORCED_OCR_NEEDS_PADDLE`). Both refusals happen before anything is read.

    `profile` (computed here when not supplied) drives the ladder: a valid PDF
    with zero native text on every page skips the native rung outright — safe
    because every native extractor keys on extracted text markers, so nothing
    that could match is skipped.

    PaddleOCR (P21-ROUTING, Phase 2.1, cell R; Ruling A): the Paddle rung runs
    ONLY on the forced path — `force_ocr and allow_paddle_ocr` — never as part
    of the non-forced ("auto") ladder below, which does not consult
    `allow_paddle_ocr` at all (CASE 12). `paddle_data_scope` (`"synthetic"` |
    `"customer"`) is REQUIRED whenever `force_ocr and allow_paddle_ocr` — the
    rung's own privacy-boundary declaration (D8); `None` there is a
    `ValueError`. `ocr.paddle_rung` is imported LAZILY, inside this branch, so
    an offline-only call never even imports it. `dpi` is read only by that
    branch.

    Native evidence (P22-IDENTITY, Phase 2.2, D5): a read the NATIVE rung
    produced carries `native_evidence` — `evidence.native.native_evidence_from_pdf`
    over the same bytes, once per document — so the OCR record persists the
    native word geometry with its sha beside the page text. The Tesseract and
    Paddle rungs never set it (`None`); `to_markdown()` is byte-identical with
    or without it."""
    if allow_visual_ocr:
        raise ValueError(VISUAL_OCR_REMOVED)

    # P21-ROUTING: the Paddle rung is reachable ONLY when `force_ocr` is True.
    # When `force_ocr` is False, `allow_paddle_ocr` is INERT — `ocr.paddle_rung`
    # is never imported and this whole block never runs, whatever
    # `allow_paddle_ocr` says (CASE 12).
    if force_ocr and allow_paddle_ocr:
        if paddle_data_scope is None:
            raise ValueError(
                "parse_statement: paddle_data_scope is required when "
                "allow_paddle_ocr=True"
            )
        _notify_stage(on_stage, "paddle_ocr")
        from .paddle_config import PADDLE_MODEL_TOKEN
        from .paddle_rung import read_document as _paddle_read_document

        document_sha256 = (
            profile.content_sha256 if profile is not None
            else inspect_pdf(pdf_bytes).content_sha256
        )
        read = _paddle_read_document(
            pdf_bytes, document_sha256=document_sha256,
            data_scope=paddle_data_scope, dpi=dpi,
        )
        return StatementMarkdown(
            source_file=source_file,
            model=PADDLE_MODEL_TOKEN,
            pages=list(read.pages),
            page_integrity=assess_pages(read.pages),
            page_extractor=list(read.page_extractor),
            evidence=read.evidence,
            # P23-WAVE (Phase 2.3): the rung's per-request technical figures,
            # carried on the read that measured them and nowhere else. TRANSIENT
            # by ruling — never persisted into the OCR artifact, so a cache hit
            # for this same document carries none and the row's four telemetry
            # columns stay empty. See `ocr/document.py`'s field comment.
            extraction_telemetry=dict(read.telemetry),
        )

    if force_ocr:
        raise ValueError(FORCED_OCR_NEEDS_PADDLE)

    if profile is None:
        profile = inspect_pdf(pdf_bytes)
    native = None
    # Profile-driven skip: no native text anywhere means no native
    # extractor can match (they all gate on extracted text markers).
    no_native_text = (
        profile.valid_pdf
        and profile.page_count > 0
        and profile.native_text_total_chars == 0
    )
    if not no_native_text:
        _notify_stage(on_stage, "native")
        native = _native_statement(pdf_bytes, source_file=source_file)
        if native is not None:
            # P22-IDENTITY (Phase 2.2, D5): the native rung — and ONLY the
            # native rung, never Tesseract's read below — attaches the ONE
            # native reader's evidence (PyMuPDF word boxes in the display
            # frame) to the document it returns, once per document. `None`
            # when the reader answers `None` (no placeable word). Attached
            # only when `native_evidence_describes` admits it (page counts
            # agree — the same rule `StatementMarkdown.__post_init__`
            # refuses on); a read whose page list a reader reshaped past
            # that rule carries no lineage rather than a wrong one, and the
            # row's empty `evidence_sha256` is the visible signal. Set by
            # attribute like `page_integrity` / `page_extractor` below,
            # because a read is whatever object the rung produced.
            native_words = native_evidence_from_pdf(pdf_bytes)
            if native_words is not None and native_evidence_describes(native.pages, native_words):
                native.native_evidence = native_words
    if native is None and allow_local_ocr:
        _notify_stage(on_stage, "local_ocr")
        native = parse_local_tesseract(pdf_bytes, source_file=source_file)
    if native is None:
        # The offline rungs read nothing, and there is no further rung.
        return None
    # O-3: assess every rung. The offline rungs have no token ceiling, so
    # they can only ever raise a structural signal — and their plain text
    # carries no markup to leave open, so in practice they raise none
    # (proven over all 109 corpus documents in tests/test_truncation.py).
    # Assessing them anyway means an empty `page_integrity` unambiguously
    # means "the ladder did not run", never "this rung is exempt".
    native.page_integrity = assess_pages(native.pages)
    # P21-ROUTING closure (MAJOR-3): design item 3 names a per-page
    # provenance token for EVERY rung, not only Paddle's. `native` here is
    # whichever offline rung actually produced the read (the native
    # extractors or local Tesseract), and its own `model` is already the
    # exact per-document token that rung sets — the same one
    # `to_markdown()`'s header already carries — so every page of THIS read
    # shares it.
    native.page_extractor = [native.model] * len(native.pages)
    if on_page_replace is not None:
        for i, page in enumerate(native.pages):
            on_page_replace(i, page)
    return native
