"""Audit 2026-10-13, INTAKE-3 / PERF-01 (a): the ladder builds MuPDF's sorted page text once per document.

`page.get_text("text", sort=True)` is PyMuPDF's pure-Python sort and the largest single cost of the native read.
Before this change the first rung sorted every page of every native document to test its markers, sorted them again
to read its rows on a document it went on to read, and the fifth rung sorted every page a third time for every
document no earlier rung claimed. The value is the same each time: same bytes, same page, same call.

What is pinned here, on fabricated PDFs and page doubles only (SAMPLE / CONTOSO / FABRIKAM text):

* one sorted read per page per document, on a generic document, on a document the first rung claims, and on one it
  reads rows from and then declines;
* a second ladder run over the same bytes sorts nothing and answers the same;
* a refusal (an unreadable text layer) is remembered as an outcome: both rungs refuse, and the failing read is not
  repeated;
* an unexpected exception is never remembered: it escapes, and the next call reads again;
* callers get a fresh list each time, and the handle the read opened is closed.
"""
from __future__ import annotations

import re

import fitz
import pytest

from ocr import native_text
from tests.test_declines_c_variants import _navy_layout_text


def _render(pages_lines: list[list[str]]) -> bytes:
    """A real PDF, one visual row per line, so the sorted text reproduces the lines."""
    document = fitz.open()
    for lines in pages_lines:
        page = document.new_page(width=612, height=792)
        y = 40
        for line in lines:
            page.insert_text((36, y), line, fontsize=9)
            y += 13
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture(autouse=True)
def _cold_caches():
    native_text.clear_page_caches()
    yield
    native_text.clear_page_caches()


@pytest.fixture
def sorted_reads(monkeypatch):
    """Counts MuPDF's sorted-text builds (every `get_text(..., sort=True)` on a real page)."""
    calls = {"sorted": 0}
    real = fitz.Page.get_text

    def counting(self, *args, **kwargs):
        if kwargs.get("sort"):
            calls["sorted"] += 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_text", counting)
    return calls


def _generic_pdf(pages: int = 3) -> bytes:
    return _render([
        [f"SAMPLE LEDGER LINE {page}-{line} CONTOSO PAYMENT 12.34" for line in range(30)]
        for page in range(pages)
    ])


def _claimed_pdf() -> bytes:
    lines = _navy_layout_text().splitlines()
    half = len(lines) // 2
    return _render([lines[:half], lines[half:]])


def _rows_then_declined_pdf() -> bytes:
    """The first rung's markers and a confirmed checking heading, but no dated row under it: the rung reads its rows
    and declines, so the document falls through the ladder."""
    lines = [line for line in _navy_layout_text().splitlines() if not re.match(r"\d{2}-\d{2}\s", line)]
    half = len(lines) // 2
    return _render([lines[:half], lines[half:]])


def _page_count(raw: bytes) -> int:
    with fitz.open(stream=raw, filetype="pdf") as opened:
        return opened.page_count


def test_a_generic_document_is_sorted_once_per_page(sorted_reads):
    raw = _generic_pdf(3)

    document = native_text.native_statement(raw, source_file="x.pdf")

    assert document is not None and document.model == "native-pdf-text"
    assert sorted_reads["sorted"] == _page_count(raw) == 3


def test_a_document_the_first_rung_claims_is_sorted_once_per_page(sorted_reads):
    raw = _claimed_pdf()

    document = native_text.native_statement(raw, source_file="x.pdf")

    assert document is not None and document.model == "native-pdf-text+navy-federal-layout"
    assert "NFCU_TX|7000000001|01-02|300.00|1,300.00|Transfer From Shares" in document.to_markdown()
    assert sorted_reads["sorted"] == _page_count(raw) == 2


def test_a_document_the_first_rung_reads_and_declines_is_sorted_once_per_page(sorted_reads):
    raw = _rows_then_declined_pdf()

    assert native_text.parse_native_navy_federal(raw, source_file="x.pdf") is None
    native_text.native_statement(raw, source_file="x.pdf")

    assert sorted_reads["sorted"] == _page_count(raw) == 2


def test_a_second_ladder_run_over_the_same_bytes_sorts_nothing(sorted_reads):
    raw = _claimed_pdf()
    first = native_text.native_statement(raw, source_file="x.pdf")
    built = sorted_reads["sorted"]

    second = native_text.native_statement(raw, source_file="x.pdf")

    assert sorted_reads["sorted"] == built
    assert second.model == first.model and second.pages == first.pages


# --------------------------------------------------------------------------- page doubles


class _Page:
    def __init__(self, text: str = "", *, unreadable: bool = False, typo: bool = False) -> None:
        self.text = text
        self.unreadable = unreadable
        self.typo = typo
        self.sorted_reads = 0

    def get_text(self, mode: str = "text", **options):
        if options.get("sort"):
            self.sorted_reads += 1
            if self.typo:
                raise TypeError("unexpected keyword argument")
        if self.unreadable:
            raise RuntimeError("code=7: cycle in resources")
        if mode == "blocks":
            return [(0.0, 0.0, 10.0, 10.0, self.text, 0, 0)]
        if mode == "words":
            return [(0.0, 0.0, 10.0, 10.0, word, 0, 0, 0) for word in self.text.split()]
        if mode == "dict":
            return {"blocks": []}
        return self.text


class _Doc:
    def __init__(self, pages: list[_Page]) -> None:
        self.pages = pages
        self.page_count = len(pages)
        self.closed = 0

    def __iter__(self):
        return iter(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def close(self) -> None:
        self.closed += 1


def _install(monkeypatch, doc: _Doc) -> list[_Doc]:
    opened: list[_Doc] = []

    def open_(*_args, **_kwargs):
        opened.append(doc)
        return doc

    monkeypatch.setattr(fitz, "open", open_)
    return opened


_DESJARDINS_PAGE = (
    "CAISSE DESJARDINS SAMPLE BRANCH\nSTATEMENT OF ACCOUNT\nDESJARDINS CORPORATE BUILD-UP ACCOUNT\n"
    + "SAMPLE LEDGER ROW CONTOSO 12.34 100.00\n" * 20
)


def test_a_refusal_is_remembered_as_an_outcome(monkeypatch):
    """Both sorted-text rungs refuse an unreadable document, and the failing read is not repeated."""
    pages = [_Page("SAMPLE readable page " * 20), _Page(unreadable=True), _Page("SAMPLE " * 50)]
    _install(monkeypatch, _Doc(pages))
    raw = b"%PDF-1.4 sample refusal"

    assert native_text.parse_native_navy_federal(raw, source_file="x.pdf") is None
    assert native_text.parse_native_desjardins(raw, source_file="x.pdf") is None
    assert native_text.native_statement(raw, source_file="x.pdf") is None

    # The read stopped at the unreadable page, once: page 3 was never asked.
    assert [page.sorted_reads for page in pages] == [1, 1, 0]
    assert native_text._sorted_pages_cached.cache_info().currsize == 1


def test_an_unexpected_exception_is_never_remembered(monkeypatch):
    """A mistake in how a rung calls get_text stays loud, on every call, and leaves no entry behind."""
    page = _Page("SAMPLE " * 100, typo=True)
    _install(monkeypatch, _Doc([page]))
    raw = b"%PDF-1.4 sample typo"

    with pytest.raises(TypeError):
        native_text.native_statement(raw, source_file="x.pdf")
    assert native_text._sorted_pages_cached.cache_info().currsize == 0

    page.typo = False
    assert native_text.native_statement(raw, source_file="x.pdf") is not None
    assert page.sorted_reads == 2


def test_each_caller_gets_its_own_list(monkeypatch):
    """The memo holds a tuple; a reader that edits the pages it was handed edits nobody else's."""
    _install(monkeypatch, _Doc([_Page(_DESJARDINS_PAGE)]))
    raw = b"%PDF-1.4 sample layout"

    first = native_text.parse_native_desjardins(raw, source_file="x.pdf")
    assert first is not None and first.model == "native-pdf-text+desjardins-layout"
    first.pages[0] = "edited"

    second = native_text.parse_native_desjardins(raw, source_file="x.pdf")
    assert second.pages == [_DESJARDINS_PAGE]
    assert isinstance(native_text._sorted_pages_cached(raw), tuple)


def test_the_sorted_read_opens_one_handle_and_closes_it(monkeypatch):
    doc = _Doc([_Page("SAMPLE " * 100)])
    opened = _install(monkeypatch, doc)
    raw = b"%PDF-1.4 sample handle"

    native_text.parse_native_navy_federal(raw, source_file="x.pdf")
    native_text.parse_native_desjardins(raw, source_file="x.pdf")

    assert len(opened) == 1
    assert doc.closed == 1


def test_clear_page_caches_empties_both_memos(monkeypatch):
    _install(monkeypatch, _Doc([_Page("SAMPLE " * 100)]))
    raw = b"%PDF-1.4 sample clear"
    native_text.native_statement(raw, source_file="x.pdf")
    assert native_text._native_pages_cached.cache_info().currsize == 1
    assert native_text._sorted_pages_cached.cache_info().currsize == 1

    native_text.clear_page_caches()

    assert native_text._native_pages_cached.cache_info().currsize == 0
    assert native_text._sorted_pages_cached.cache_info().currsize == 0
