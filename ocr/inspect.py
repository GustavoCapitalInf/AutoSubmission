"""Unified document preflight (Wave 1 / O-1): inspection only.

``inspect_pdf(pdf_bytes)`` produces a ``DocumentProfile`` describing a
document BEFORE any parser runs: structural validity, encryption, page count,
content hash, per-page native-text availability, a digital/scanned/mixed
classification, and advisory layout signals. It never extracts statements and
never calls OCR — the intake ladder in ``ocr/pipeline.py`` consumes the
profile; the extractors themselves are called there, not here.

Hash definition (single source of truth)
----------------------------------------
``content_sha256`` — UPPERCASE hex SHA-256 of the raw PDF bytes, exactly the
convention of ``corpus_gate.sha256_upper``. This module is the ONE definition;
``webapp.storage`` imports it from here (relocated in O-1 from
``webapp/storage.py``, where D-1 first shipped it, to keep the dependency
direction ocr-independent-of-webapp).

Threshold provenance
--------------------
``MIN_TOTAL_TEXT_CHARS`` / ``MIN_PAGE_TEXT_CHARS`` are duplicated BY REFERENCE
from the gate inside ``ocr/native_text.py::parse_native_pdf_text`` (protected
file, inline literals ``500`` / ``200`` — they cannot be imported without
editing it). If that gate ever changes, these must change with it; the
109-document parity test in ``tests/test_inspect.py`` is the tripwire.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict

# Duplicated by reference from ocr/native_text.py::parse_native_pdf_text —
# see the module docstring. Do not tune independently.
MIN_TOTAL_TEXT_CHARS = 500
MIN_PAGE_TEXT_CHARS = 200

# Statement-period marker: reused by reference from ocr/native_text.py
# (_NAVY_PERIOD_RE — 'MM/DD/YY - MM/DD/YY'); the phrase alternative covers
# banks that label the block instead of printing the bare range.
from .native_text import _NAVY_PERIOD_RE as _PERIOD_RANGE_RE

_PERIOD_PHRASE_RE = re.compile(r"statement\s+period|statement\s+date", re.IGNORECASE)

# 'Page N of M' footer: the core alternation of ocr/ocr_client.py::_PAGE_DUP_RE
# (which wraps this same pattern in a consecutive-duplicate backreference and
# is therefore not directly reusable for single-occurrence detection).
_PAGE_N_OF_M_RE = re.compile(r"Page:?\s*\d+\s*(?:of|/)\s*\d+", re.IGNORECASE)

# Table markers in native text: bank statements print ledger column headers;
# OCR output instead carries literal <table> markup (ocr/ocr_client.py::_TABLE_RE).
_TABLE_HEADER_RE = re.compile(
    r"(?:date|description|details?)\b.{0,40}\b(?:amount|debit|credit|withdrawals?|deposits?|balance)",
    re.IGNORECASE,
)
_TABLE_HTML_RE = re.compile(r"<table>", re.IGNORECASE)

# 'Account Number/Type' block markers (ADVISORY heuristic only).
_ACCOUNT_MARKER_RE = re.compile(r"account\s+(?:number|type)\b", re.IGNORECASE)
_ACCOUNT_VALUE_RE = re.compile(
    r"account\s+(?:number|no\.?|#)\s*[:#]?\s*([Xx*•]*[\d][\dXx*•\- ]{3,})",
    re.IGNORECASE,
)


def content_sha256(data: bytes) -> str:
    """UPPERCASE hex SHA-256 of the raw PDF bytes.

    The single hash definition shared by the webapp document store (O-1
    handshake) and matching ``corpus_gate.sha256_upper`` exactly:
    ``hashlib.sha256(data).hexdigest().upper()``.
    """
    return hashlib.sha256(data).hexdigest().upper()


@dataclass
class LayoutSignals:
    """ADVISORY — consumed by nothing in production code (stored with the
    profile and read only by tests)."""

    has_table_markers: bool = False
    has_statement_period: bool = False
    has_page_n_of_m: bool = False


@dataclass
class DocumentProfile:
    """What is knowable about a PDF before any parser touches it.

    ``classification``: ``digital`` (the generic native-text gate passes),
    ``scanned`` (no page carries usable native text), ``mixed`` (some native
    text, but below the gate), or ``unknown`` (invalid or encrypted — there is
    no text truth to report).
    """

    content_sha256: str
    valid_pdf: bool = False
    encrypted: bool = False
    page_count: int = 0
    page_text_chars: list[int] = field(default_factory=list)
    text_pages: list[bool] = field(default_factory=list)
    classification: str = "unknown"  # digital | scanned | mixed | unknown
    likely_ocr_required: bool = True
    malformed_pages: list[int] = field(default_factory=list)
    likely_account_count: int = 0  # ADVISORY — consumed by nothing
    layout_signals: LayoutSignals = field(default_factory=LayoutSignals)  # ADVISORY

    @property
    def native_text_total_chars(self) -> int:
        return sum(self.page_text_chars)

    def to_dict(self) -> dict:
        return asdict(self)


def _page_texts(doc) -> tuple[list[str], list[int]]:
    """Per-page text with the same block normalization as
    ``ocr/native_text.py::_native_pages`` (duplicated by reference — that
    helper has no per-page error isolation, which malformed-page reporting
    needs). Returns (page_texts, malformed_page_indices)."""
    pages: list[str] = []
    malformed: list[int] = []
    for index, page in enumerate(doc):
        try:
            lines: list[str] = []
            blocks = sorted(
                page.get_text("blocks"), key=lambda b: (round(b[1], 1), round(b[0], 1))
            )
            for block in blocks:
                text = " ".join(
                    part.strip() for part in str(block[4]).splitlines() if part.strip()
                )
                if text:
                    lines.append(text)
            pages.append("\n".join(lines))
        except Exception:
            pages.append("")
            malformed.append(index)
    return pages, malformed


def _classify(page_text_chars: list[int]) -> str:
    """Digital/scanned/mixed from per-page native-text availability.

    ``digital`` reuses parse_native_pdf_text's gate EXACTLY (total chars and
    text-page quorum) — the same bar the ladder's generic native rung applies,
    which is what makes the 109-document corpus parity hold. ``scanned`` means
    no page reaches the per-page threshold; anything in between is ``mixed``.
    """
    page_count = len(page_text_chars)
    if page_count == 0:
        return "unknown"
    total = sum(page_text_chars)
    text_page_count = sum(1 for chars in page_text_chars if chars >= MIN_PAGE_TEXT_CHARS)
    if total >= MIN_TOTAL_TEXT_CHARS and text_page_count >= max(1, page_count // 2):
        return "digital"
    if text_page_count == 0:
        return "scanned"
    return "mixed"


def _account_count(text: str) -> int:
    """ADVISORY 'Account Number/Type' block counting — distinct account-number
    values when printed, else whether any account block marker appears at all."""
    values = {
        re.sub(r"[\s\-]", "", match.group(1)).upper()
        for match in _ACCOUNT_VALUE_RE.finditer(text)
    }
    if values:
        return len(values)
    return 1 if _ACCOUNT_MARKER_RE.search(text) else 0


def _layout_signals(text: str) -> LayoutSignals:
    return LayoutSignals(
        has_table_markers=bool(
            _TABLE_HEADER_RE.search(text) or _TABLE_HTML_RE.search(text)
        ),
        has_statement_period=bool(
            _PERIOD_RANGE_RE.search(text) or _PERIOD_PHRASE_RE.search(text)
        ),
        has_page_n_of_m=bool(_PAGE_N_OF_M_RE.search(text)),
    )


def inspect_pdf(pdf_bytes: bytes, *, read_native_text: bool = True) -> DocumentProfile:
    """Inspect a PDF without parsing it as a statement. Never raises.

    Forced visual intake uses ``read_native_text=False`` for structural checks
    only. Text-derived fields remain unknown rather than claiming the document
    has no native text, and no page text accessor is called.
    """
    profile = DocumentProfile(content_sha256=content_sha256(pdf_bytes))
    if not pdf_bytes.startswith(b"%PDF-"):
        return profile

    try:
        import fitz
    except Exception:
        return profile
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return profile

    profile.valid_pdf = True
    profile.page_count = int(doc.page_count)
    if doc.needs_pass:
        # Structurally valid but unreadable without a password: no text truth
        # to report, so classification stays "unknown".
        profile.encrypted = True
        return profile

    if not read_native_text:
        doc.close()
        return profile

    pages, malformed = _page_texts(doc)
    profile.page_text_chars = [len(page.strip()) for page in pages]
    profile.text_pages = [
        chars >= MIN_PAGE_TEXT_CHARS for chars in profile.page_text_chars
    ]
    profile.malformed_pages = malformed
    profile.classification = _classify(profile.page_text_chars)
    profile.likely_ocr_required = profile.classification != "digital"

    joined = "\n".join(pages)
    profile.likely_account_count = _account_count(joined)
    profile.layout_signals = _layout_signals(joined)
    return profile
