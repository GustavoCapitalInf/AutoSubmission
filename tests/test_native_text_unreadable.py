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
class is reproduced here with a page double built on PyMuPDF's real exception
base. That is deliberate: the contract under test is OURS, and the raising class
differs between extraction modes on the very same page — `get_text("text")` and
`("dict")` raise a builtin `RuntimeError` while `("blocks")` and `("words")`
raise `FzErrorFormat`, which descends from `FzErrorBase` and NOT from
RuntimeError — so both families have to be named, and a guard written against
either alone would miss half its call sites.

Three things are pinned here beyond "it does not crash":

* the catch is NARROW — a mistake in how a rung CALLS `get_text` (`TypeError`
  for a misspelled keyword, `AssertionError` for an unknown mode) still
  escapes, so a broken reader can never silently demote itself to the generic
  rung;
* the catch has not silently narrowed FURTHER — `_mupdf_text_errors` resolves
  `FzErrorBase` lazily, and the resolution is asserted rather than trusted;
* the REASON survives — `text_layer_refusal` and the coverage oracle's row keep
  a structurally corrupt PDF distinguishable from an ordinary scan, which is
  what the escaping exception used to do.

The archive-wide census behind those numbers is in W3 §RUNGSEAM.
"""
from __future__ import annotations

import pytest

from ocr import native_text
from ocr.native_text import (
    _mupdf_text_errors,
    _page_text,
    _UnreadableTextLayer,
    native_statement,
    parse_native_desjardins,
    parse_native_first_citizens,
    parse_native_navy_federal,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
    parse_native_woodforest,
    text_layer_refusal,
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
    """A page double. `blank` is an ordinary image-only scan: readable text
    layer, nothing in it — the case the refusal must NOT be confused with."""

    def __init__(self, *, readable: bool, blank: bool = False) -> None:
        self.readable = readable
        self.blank = blank

    def get_text(self, mode="text", **_options):
        if self.blank:
            return {"blocks": []} if mode == "dict" else ([] if mode in ("blocks", "words") else "")
        if not self.readable:
            # The two shapes MuPDF actually raises for this defect, measured on
            # the four documents: `blocks`/`words` raise FzErrorFormat and
            # `text`/`dict` raise a builtin RuntimeError, on the SAME page.
            if mode in ("blocks", "words"):
                raise _FzErrorFormat("cycle in resources")
            raise RuntimeError("code=7: cycle in resources")
        if mode == "blocks":
            return [(0.0, 0.0, 10.0, 10.0, _READABLE, 0, 0)]
        if mode == "words":
            return [(0.0, 0.0, 10.0, 10.0, word, 0, 0, 0) for word in _READABLE.split()]
        if mode == "dict":
            return {"blocks": []}
        return _READABLE


def _fz_error_base():
    """PyMuPDF's own MuPDF exception base, wherever this build keeps it."""
    for module_name in ("pymupdf.mupdf", "fitz.mupdf"):
        try:
            module = __import__(module_name, fromlist=["FzErrorBase"])
        except Exception:  # noqa: BLE001
            continue
        base = getattr(module, "FzErrorBase", None)
        if isinstance(base, type) and issubclass(base, BaseException):
            return base
    return None


_FZ_ERROR_BASE = _fz_error_base()

if _FZ_ERROR_BASE is not None:

    class _FzErrorFormat(_FZ_ERROR_BASE):
        """Stands in for `FzErrorFormat`, which this build does not re-export.

        Derived from the REAL `FzErrorBase` on purpose: `_page_text` no longer
        catches `Exception`, so a stand-in that merely subclassed RuntimeError
        would be caught for the wrong reason and would prove nothing about the
        half of the catch tuple that exists for this family.
        """

        def __init__(self, text: str) -> None:
            super().__init__(7, text)

else:  # pragma: no cover - only if PyMuPDF stops exposing the class

    class _FzErrorFormat(RuntimeError):
        pass


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


def test_the_mupdf_error_family_is_actually_resolved_here():
    """The narrowed catch must not narrow itself further by accident.

    `_mupdf_text_errors` resolves `FzErrorBase` lazily and falls back to
    `RuntimeError` alone if the attribute moves. That fallback would let
    `FzErrorFormat` escape the ladder again — silently, and only on the
    documents nobody has. Assert the resolution succeeded instead.
    """
    errors = _mupdf_text_errors()
    assert RuntimeError in errors
    assert _FZ_ERROR_BASE is not None, "PyMuPDF no longer exposes FzErrorBase"
    assert _FZ_ERROR_BASE in errors, (
        f"the FzErrorBase family is not in the catch tuple {errors} — the guard "
        "has silently narrowed to RuntimeError"
    )
    # The whole reason both have to be named: they are siblings, not kin.
    assert not issubclass(_FZ_ERROR_BASE, RuntimeError)


@pytest.mark.parametrize(
    "boom, expected",
    [
        (lambda: (_ for _ in ()).throw(TypeError("unexpected keyword argument 'srot'")), TypeError),
        (lambda: (_ for _ in ()).throw(AssertionError()), AssertionError),
        (lambda: (_ for _ in ()).throw(KeyError("blocks")), KeyError),
    ],
)
def test_a_mistake_in_how_we_call_get_text_is_not_a_refusal(boom, expected):
    """A misspelled `sort=`/mode is OUR bug and must stay loud.

    PyMuPDF answers a bad keyword with `TypeError` and an unknown mode with
    `AssertionError`. Under the old `except Exception` both became a silent
    whole-document refusal — the ladder would fall through to the generic rung
    and the archive would quietly lose a bank-specific reader.
    """

    class _Boom:
        def get_text(self, *_a, **_k):
            boom()

    with pytest.raises(expected):
        _page_text(_Boom(), "text")


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


def test_the_refusal_reason_survives_the_ladder(monkeypatch):
    """WHY there is no text, not just that there is none.

    The ladder answers None for a document with nothing to read and for one
    whose text layer MuPDF cannot read, which is correct but makes a
    structurally corrupt PDF indistinguishable from an ordinary scan. Before
    the guard, the escaping exception carried that distinction; this is where
    it went.
    """
    _install(monkeypatch, _Doc([_Page(readable=True), _Page(readable=False)]))
    raw = b"%PDF-1.4 corrupt"
    assert native_statement(raw, source_file="x.pdf") is None
    refusal = text_layer_refusal(raw)
    assert refusal is not None
    assert "page 2" in refusal, refusal
    assert "cycle in resources" in refusal, refusal


def test_a_readable_document_has_no_refusal_reason(monkeypatch):
    _install(monkeypatch, _Doc([_Page(readable=True)]))
    raw = b"%PDF-1.4 readable"
    assert native_statement(raw, source_file="x.pdf") is not None
    assert text_layer_refusal(raw) is None


def test_the_coverage_oracle_publishes_the_reason(monkeypatch, tmp_path):
    """The row a triage actually reads. RS6.2 / Ocean closure 2.

    Without this the oracle books `error=native PDF text unavailable or too
    sparse` for a document MuPDF refused outright — the same row an image-only
    scan gets.
    """
    import deterministic_coverage_audit as audit

    pdf = tmp_path / "corrupt.pdf"
    pdf.write_bytes(b"%PDF-1.4 corrupt")
    _install(monkeypatch, _Doc([_Page(readable=False) for _ in range(2)]))

    row = audit.audit_file(pdf, tmp_path)
    assert row["native_status"] == "no_native_text"
    assert row["deterministic_status"] == "not_attempted"
    assert row["integrity_flags"] == "text_unavailable"
    assert "cycle in resources" in row["error"], row["error"]
    assert "text layer unreadable" in row["integrity_notes"], row["integrity_notes"]


def test_the_coverage_oracle_row_is_unchanged_for_an_ordinary_scan(monkeypatch, tmp_path):
    """Nothing else moves: a document with no text layer reads as it always did."""
    import deterministic_coverage_audit as audit

    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 scan")
    _install(monkeypatch, _Doc([_Page(readable=True, blank=True) for _ in range(2)]))

    row = audit.audit_file(pdf, tmp_path)
    assert row["native_status"] == "no_native_text"
    assert row["error"] == "native PDF text unavailable or too sparse"
    assert row["integrity_notes"] == (
        "native text unavailable and local OCR did not produce usable statement text"
    )


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
