from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from evidence.native import native_evidence_from_pdf
from .rasterize import rasterize_pdf, rasterize_page
from .document import StatementMarkdown, native_evidence_describes
from .config import load_settings
from .inspect import DocumentProfile, inspect_pdf
from .local_tesseract import parse_local_tesseract
from .truncation import assess_pages
# The native-text rung ladder, defined ONCE in `ocr/native_text.py` (see
# `native_statement` there for the rung order and the two drifts that paid for
# consolidating it). It is bound here under `_native_statement` — the name
# `parse_statement` has always called and the suite monkeypatches — so the only
# thing that changed is where the ladder lives.
from .native_text import native_statement as _native_statement


def _notify_stage(on_stage, rung: str) -> None:
    if on_stage is not None:
        on_stage(rung)


def parse_statement(pdf_bytes: bytes, source_file: str = "", dpi: int = 300,
                    model: str | None = None, page_ocr_fn=None,
                    on_page_delta=None, max_workers: int | None = None,
                    fallback_dpi: int | None = 250, on_page_replace=None,
                    force_ocr: bool = False,
                    allow_local_ocr: bool = False,
                    allow_visual_ocr: bool = True,
                    allow_paddle_ocr: bool = False,
                    paddle_data_scope: str | None = None,
                    profile: DocumentProfile | None = None,
                    on_stage=None) -> StatementMarkdown | None:
    """The single intake ladder (O-1): native text -> local Tesseract ->
    visual OCR / PaddleOCR, driven by the preflight DocumentProfile.

    Capability flags preserve each caller's historical behavior exactly:
    `allow_local_ocr` (default False) gates the Tesseract rung, which has only
    ever existed for the webapp — the CLI (`parse.py`) does not silently gain
    an OCR stage it never had. `allow_visual_ocr=False` stops the ladder after
    the offline rungs and returns None (used by the webapp's deterministic
    mode); with the default True the return value is never None. `force_ocr`
    (or an injected `page_ocr_fn`) skips straight to the visual rung, as
    before. `on_stage(rung)` reports "native" / "local_ocr" / "visual_ocr" /
    "paddle_ocr" as each rung starts, so callers can surface progress without
    owning routing.

    `profile` (computed here when not supplied) drives the ladder: a valid PDF
    with zero native text on every page skips the native rung outright — safe
    because every native extractor keys on extracted text markers, so nothing
    that could match is skipped.

    Visual OCR: pages are rasterized and OCR'd concurrently (up to
    `max_workers`; defaults to Settings.max_workers), reassembled in page
    order. `fallback_dpi` (default 250) guards against a DPI-specific table
    mis-segmentation: a page with the tell-tale orphan amount-only table is
    re-OCR'd once at the fallback DPI and the cleaner read kept. If
    `on_page_delta` is given, raw model output streams live as
    `on_page_delta(page_index, chunk)`; `page_ocr_fn` is injectable for tests
    and receives a single page image.

    PaddleOCR (P21-ROUTING, Phase 2.1, cell R; Ruling A): the Paddle rung runs
    ONLY on the forced path — `force_ocr and allow_paddle_ocr` — never as part
    of the non-forced ("auto") ladder above, which is UNCHANGED and does not
    consult `allow_paddle_ocr` at all (CASE 12: the pre-existing auto-mode
    fallthrough to the visual rung stays exactly as it is; it gains no Paddle
    arm). `allow_paddle_ocr` and `allow_visual_ocr` together on the forced
    path is a `ValueError`: the router names exactly one extractor per call,
    and this ladder never chooses between two OCR extractors on its own.
    `paddle_data_scope` (`"synthetic"` | `"customer"`) is REQUIRED whenever
    `force_ocr and allow_paddle_ocr` — the rung's own privacy-boundary
    declaration (D8); `None` there is a `ValueError`. `ocr.paddle_rung` is
    imported LAZILY, inside this branch, so an offline-only or visual-only
    call never even imports it (mirroring the existing lazy `ocr.ocr_client`
    import for the visual rung).

    Native evidence (P22-IDENTITY, Phase 2.2, D5): a read the NATIVE rung
    produced carries `native_evidence` — `evidence.native.native_evidence_from_pdf`
    over the same bytes, once per document — so the OCR record persists the
    native word geometry with its sha beside the page text. The Tesseract,
    visual and Paddle rungs never set it (`None`); `to_markdown()` is
    byte-identical with or without it."""
    if page_ocr_fn is None and not force_ocr:
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
        if native is not None:
            # O-3: assess every rung, not just the visual one. The offline rungs
            # have no token ceiling, so they can only ever raise a structural
            # signal — and their plain text carries no markup to leave open, so
            # in practice they raise none (proven over all 109 corpus documents
            # in tests/test_truncation.py). Assessing them anyway means an empty
            # `page_integrity` unambiguously means "the ladder did not run",
            # never "this rung is exempt".
            native.page_integrity = assess_pages(native.pages)
            # P21-ROUTING closure (MAJOR-3): design item 3 names a
            # per-page provenance token for EVERY rung, not only Paddle's.
            # `native` here is whichever offline rung actually produced the
            # read (the native extractors or local Tesseract), and its own
            # `model` is already the exact per-document token that rung
            # sets — the same one `to_markdown()`'s header already carries —
            # so every page of THIS read shares it.
            native.page_extractor = [native.model] * len(native.pages)
            if on_page_replace is not None:
                for i, page in enumerate(native.pages):
                    on_page_replace(i, page)
            return native

    # P21-ROUTING: the Paddle rung is reachable ONLY when `force_ocr` is True.
    # `force_ocr` is still in scope here whatever happened above (the
    # non-forced block never returns when it falls through), so this is a
    # precise, structural test of "the forced path", not a guess based on
    # what the offline ladder just did. When `force_ocr` is False,
    # `allow_paddle_ocr` is INERT — `ocr.paddle_rung` is never imported and
    # this whole block never runs, whatever `allow_paddle_ocr` says (CASE 12).
    if force_ocr and allow_paddle_ocr:
        if allow_visual_ocr:
            raise ValueError(
                "parse_statement: allow_paddle_ocr and allow_visual_ocr "
                "together is not allowed — one OCR extractor per call; the "
                "router chooses"
            )
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
        )

    if not allow_visual_ocr:
        return None

    _notify_stage(on_stage, "visual_ocr")
    settings = load_settings(model_override=model)
    workers = max_workers if max_workers is not None else settings.max_workers

    if page_ocr_fn is None:
        from .ocr_client import (ocr_page, _build_client, looks_missegmented,
                                 looks_truncated_td, recover_truncated_td_page)
        client = _build_client(settings)

        def use_alt(page_index, alt):
            # A fallback/recovery re-OCR happened off-stream, so the live buffer the
            # web UI renders still holds the original (broken) read — overwrite it.
            if on_page_replace is not None:
                on_page_replace(page_index, alt)
            return alt

        def ocr_call(image, page_index):
            cb = None
            if on_page_delta is not None:
                cb = lambda chunk, p=page_index: on_page_delta(p, chunk)
            out = ocr_page(image, settings=settings, client=client, on_delta=cb)
            # Re-OCR a mis-segmented page once at the fallback DPI (no streaming);
            # keep it only if it actually resolves the split.
            if (fallback_dpi and fallback_dpi != dpi and looks_missegmented(out)):
                alt_img = rasterize_page(pdf_bytes, page_index, dpi=fallback_dpi)
                alt = ocr_page(alt_img, settings=settings, client=client)
                if not looks_missegmented(alt):
                    return use_alt(page_index, alt)
            # A truncated TD page-1 (the QR-code refusal derails generation) reads
            # fully under some render variant — try them and keep a recovered read.
            if page_index == 0 and looks_truncated_td(out):
                alt = recover_truncated_td_page(pdf_bytes, page_index,
                                                settings=settings, client=client)
                if alt is not None:
                    return use_alt(page_index, alt)
            return out
    else:
        def ocr_call(image, page_index):
            return page_ocr_fn(image)

    pages = rasterize_pdf(pdf_bytes, dpi=dpi)
    results: list[str | None] = [None] * len(pages)

    if workers <= 1 or len(pages) <= 1:
        for i, image in enumerate(pages):
            results[i] = ocr_call(image, i)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(ocr_call, image, i): i for i, image in enumerate(pages)}
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result()

    # O-3: assess the reads that were actually KEPT — this runs after the
    # mis-segmentation fallback and the TD page-1 recovery have already chosen
    # between the original and the re-OCR, and the model signals travel on the
    # PageText itself, so a flag can never describe a discarded read. Flag-only:
    # nothing below re-OCRs, drops, or rewrites a page because of a flag.
    integrity = assess_pages(results)
    pages_out = [str(r) if r else "" for r in results]
    return StatementMarkdown(source_file=source_file, model=settings.model,
                             pages=pages_out, page_integrity=integrity,
                             # P21-ROUTING closure (MAJOR-3): design item 3's
                             # visual arm — `settings.model` per page, the
                             # same token this call already stamps as the
                             # document's own `model`.
                             page_extractor=[settings.model] * len(pages_out))
