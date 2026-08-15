"""A PDF whose text layer cannot be extracted refuses; it never crashes intake.

Four archive documents (`Unidentified/c3f27791_3 BUSINESS CHECKING X3774-*.PDF`,
content_sha256 `6f57be08…`, `64a49584…`, `53906d0e…`, `cdb8a6cc…`) carry a
structural defect MuPDF reports as `code=7: cycle in resources`. `fitz.open`
succeeds and reports the page count; every `page.get_text(...)` on every page
then raises. Before RUNG-SEAM that exception escaped the whole intake ladder:
the coverage oracle booked the document as `native_status=error`, and
`build_corpus_cache.py` — which has no exception handling at all — aborted the
run.

The documents themselves are archive material and are not committed, so the
class is reproduced here with a page double. That is deliberate: the contract
under test is OURS ("whatever MuPDF raises out of get_text becomes a refusal"),
not MuPDF's, and the raising class differs between extraction modes on the very
same page — `get_text("text")` raises a bare `RuntimeError` while
`get_text("blocks")` and `get_text("words")` raise `FzErrorFormat` — so a guard
written against an exception CLASS would have missed a third of the call sites.
The archive-wide census behind those numbers is in W3 §RUNGSEAM.
"""
from __future__ import annotations

import pytest

from ocr import native_text
from ocr.native_text import (
    _UnreadableTextLayer,
    _page_text,
    native_statement,
    parse_native_desjardins,
    parse_native_first_citizens,
    parse_native_navy_federal,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
    parse_native_woodforest,
)

RUNGS = (
    parse_native_navy_federal,
    parse_native_td_canada,
    parse_native_wells_fargo,
    parse_native_woodforest,
    parse_native_desjardins,
    parse_native_first_citizens,
    parse_native_pdf_text,
)

#: A readable page, in the shapes the rungs ask for. Enough text to clear
#: `parse_native_pdf_text`'s 500-char / 200-char-per-page gate.
_READABLE = "Ledger line for a perfectly ordinary statement page. " * 12


class _Page:
    def __init__(self, *, readable: bool) -> None:
        self.readable = readable

    def get_text(self, mode="text", **_options):
        if not self.readable:
            # The two shapes MuPDF actually raises for this defect.
            if mode in ("blocks", "words"):
                raise _FzErrorFormat("code=7: cycle in resources")
            raise RuntimeError("code=7: cycle in resources")
        if mode == "blocks":
            return [(0.0, 0.0, 10.0, 10.0, _READABLE, 0, 0)]
        if mode == "words":
            return [(0.0, 0.0, 10.0, 10.0, word, 0, 0, 0) for word in _READABLE.split()]
        if mode == "dict":
            return {"blocks": []}
        return _READABLE


class _FzErrorFormat(RuntimeError):
    """Stands in for PyMuPDF's own class, which this build does not export."""


class _Doc:
    def __init__(self, pages: list[_Page]) -> None:
        self._pages = pages
        self.page_count = len(pages)

    def __iter__(self):
        return iter(self._pages)

    def __getitem__(self, index):
        return self._pages[index]

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _cold_page_cache():
    """`_native_pages_cached` memoises on bytes; every case starts cold."""
    native_text._native_pages_cached.cache_clear()
    yield
    native_text._native_pages_cached.cache_clear()


def _install(monkeypatch, doc: _Doc) -> None:
    import fitz

    monkeypatch.setattr(fitz, "open", lambda *a, **k: doc)


def test_page_text_passes_a_readable_page_through_untouched():
    page = _Page(readable=True)
    assert _page_text(page, "text") == _READABLE
    assert _page_text(page, "blocks") == page.get_text("blocks")


@pytest.mark.parametrize("mode", ["text", "blocks", "words", "dict"])
def test_page_text_converts_every_mupdf_failure_into_one_refusal(mode):
    with pytest.raises(_UnreadableTextLayer) as raised:
        _page_text(_Page(readable=False), mode)
    # The refusal names what MuPDF said, so a triage does not need the PDF.
    assert "cycle in resources" in str(raised.value)


@pytest.mark.parametrize("rung", RUNGS, ids=lambda fn: fn.__name__)
def test_every_rung_refuses_an_unreadable_document(monkeypatch, rung):
    _install(monkeypatch, _Doc([_Page(readable=False) for _ in range(3)]))
    assert rung(b"%PDF-1.4 unreadable", source_file="x.pdf") is None


def test_the_ladder_refuses_instead_of_raising(monkeypatch):
    _install(monkeypatch, _Doc([_Page(readable=False) for _ in range(3)]))
    assert native_statement(b"%PDF-1.4 unreadable", source_file="x.pdf") is None


def test_one_unreadable_page_refuses_the_whole_document(monkeypatch):
    """Fail CLOSED: a partial read is a statement with pages missing.

    `parse_native_pdf_text` only asks that half the pages carry text, so a
    reader that skipped the bad page and kept the rest would publish a ledger
    short of a page and nothing downstream would know.
    """
    pages = [_Page(readable=True), _Page(readable=False), _Page(readable=True)]
    _install(monkeypatch, _Doc(pages))
    assert native_text._native_pages(b"%PDF-1.4 half-readable") is None
    assert native_statement(b"%PDF-1.4 half-readable", source_file="x.pdf") is None


def test_a_readable_document_still_reads(monkeypatch):
    """The guard is invisible to every document whose text layer works."""
    _install(monkeypatch, _Doc([_Page(readable=True) for _ in range(2)]))
    document = native_statement(b"%PDF-1.4 readable", source_file="x.pdf")
    assert document is not None
    assert document.model == "native-pdf-text"
    assert document.pages == [_READABLE.strip(), _READABLE.strip()]


def test_a_rung_defect_is_not_swallowed(monkeypatch):
    """The refusal is narrow: only unreadable TEXT is caught, not our bugs.

    A bare `except Exception` around each rung would have turned a broken row
    reader into a silent fall-through to the generic rung — a bank-specific
    extractor quietly switching itself off is exactly the failure a coverage
    wave cannot see.
    """
    def boom(_page):
        raise ZeroDivisionError("a defect in our own row reader")

    _install(monkeypatch, _Doc([_Page(readable=True)]))
    monkeypatch.setattr(native_text, "_wells_rows", boom)
    monkeypatch.setattr(
        native_text, "_page_text", lambda page, *a, **k: _wells_text(page, *a, **k)
    )
    with pytest.raises(ZeroDivisionError):
        parse_native_wells_fargo(b"%PDF-1.4 wells", source_file="x.pdf")


def _wells_text(page, mode="text", **options):
    """`_page_text` with Wells Fargo's two printed markers in the page text."""
    value = page.get_text(mode, **options)
    if mode == "blocks":
        return [(0.0, 0.0, 10.0, 10.0, "WELLS FARGO TRANSACTION HISTORY", 0, 0)]
    if isinstance(value, str):
        return "WELLS FARGO\nTRANSACTION HISTORY\n" + value
    return value
