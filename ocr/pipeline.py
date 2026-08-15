from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from .rasterize import rasterize_pdf, rasterize_page
from .document import StatementMarkdown
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
                    profile: DocumentProfile | None = None,
                    on_stage=None) -> StatementMarkdown | None:
    """The single intake ladder (O-1): native text -> local Tesseract ->
    visual OCR, driven by the preflight DocumentProfile.

    Capability flags preserve each caller's historical behavior exactly:
    `allow_local_ocr` (default False) gates the Tesseract rung, which has only
    ever existed for the webapp — the CLI (`parse.py`) does not silently gain
    an OCR stage it never had. `allow_visual_ocr=False` stops the ladder after
    the offline rungs and returns None (used by the webapp's deterministic
    mode); with the default True the return value is never None. `force_ocr`
    (or an injected `page_ocr_fn`) skips straight to the visual rung, as
    before. `on_stage(rung)` reports "native" / "local_ocr" / "visual_ocr" as
    each rung starts, so callers can surface progress without owning routing.

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
    and receives a single page image."""
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
            if on_page_replace is not None:
                for i, page in enumerate(native.pages):
                    on_page_replace(i, page)
            return native

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
    return StatementMarkdown(source_file=source_file, model=settings.model,
                             pages=[str(r) if r else "" for r in results],
                             page_integrity=integrity)
