"""Wave 1 / O-1 — unified document preflight (ocr/inspect.py).

Profile unit tests use synthetic PDFs generated with PyMuPDF (pypdf is not
installed in this environment, so the encrypted fixture is produced with
fitz AES-256 encryption — the spec's sanctioned fallback). The 109-document
corpus parity test is native-text detection only (no OCR, no network) so it
runs in the default suite.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import fitz
import pytest

from ocr.inspect import (
    MIN_PAGE_TEXT_CHARS,
    MIN_TOTAL_TEXT_CHARS,
    DocumentProfile,
    content_sha256,
    inspect_pdf,
    _page_texts,
)
from tests.statements import statements_dir

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LONG_TEXT = ("Deposit 1,204.56 balance forward statement line item detail " * 12).strip()
# Between the per-page (200) and total (500) thresholds: a usable text page
# that still cannot satisfy the document-level gate on its own.
MID_TEXT = ("ledger row detail 12.34 " * 11).strip()
SHORT_TEXT = "Only a short caption"


def _pdf_with_pages(page_texts: list[str | None]) -> bytes:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_textbox(fitz.Rect(36, 36, 560, 800), text, fontsize=10)
    return doc.tobytes()


def _encrypted_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret statement text")
    return doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="hunter2", owner_pw="hunter2"
    )


# ---------------------------------------------------------------------------
# hash — the single definition (O-1 handshake)
# ---------------------------------------------------------------------------


def test_content_sha256_is_uppercase_sha256_of_raw_bytes():
    data = b"%PDF-1.7 raw bytes"
    assert content_sha256(data) == hashlib.sha256(data).hexdigest().upper()


def test_webapp_storage_reexports_the_same_hash_function():
    from webapp.storage import content_sha256 as storage_hash

    assert storage_hash is content_sha256  # one definition, relocated not duplicated


# ---------------------------------------------------------------------------
# validity / encryption / structure signals
# ---------------------------------------------------------------------------


def test_non_pdf_bytes_profile():
    profile = inspect_pdf(b"<?php system($_GET[0]); ?>")
    assert profile.valid_pdf is False
    assert profile.encrypted is False
    assert profile.page_count == 0
    assert profile.classification == "unknown"
    assert profile.likely_ocr_required is True
    assert profile.content_sha256 == content_sha256(b"<?php system($_GET[0]); ?>")


def test_pdf_header_with_garbage_body_is_not_valid():
    profile = inspect_pdf(b"%PDF-1.7\n0000 not really a pdf")
    assert profile.valid_pdf is False
    assert profile.classification == "unknown"


def test_encrypted_pdf_is_flagged_and_never_raises():
    profile = inspect_pdf(_encrypted_pdf())
    assert profile.valid_pdf is True
    assert profile.encrypted is True
    assert profile.page_count == 1
    assert profile.classification == "unknown"  # no text truth without the password
    assert profile.likely_ocr_required is True


def test_valid_pdf_reports_pages_and_hash():
    pdf = _pdf_with_pages([LONG_TEXT, LONG_TEXT, None])
    profile = inspect_pdf(pdf)
    assert profile.valid_pdf is True
    assert profile.encrypted is False
    assert profile.page_count == 3
    assert profile.content_sha256 == content_sha256(pdf)
    assert len(profile.page_text_chars) == 3
    assert profile.malformed_pages == []


# ---------------------------------------------------------------------------
# classification: digital | scanned | mixed
# ---------------------------------------------------------------------------


def test_digital_classification_reuses_the_native_gate():
    profile = inspect_pdf(_pdf_with_pages([LONG_TEXT, LONG_TEXT]))
    assert profile.classification == "digital"
    assert profile.likely_ocr_required is False
    assert profile.text_pages == [True, True]
    assert profile.native_text_total_chars >= MIN_TOTAL_TEXT_CHARS
    assert all(chars >= MIN_PAGE_TEXT_CHARS for chars in profile.page_text_chars)


def test_scanned_classification_for_textless_pages():
    profile = inspect_pdf(_pdf_with_pages([None, None]))
    assert profile.classification == "scanned"
    assert profile.likely_ocr_required is True
    assert profile.text_pages == [False, False]
    assert profile.native_text_total_chars == 0


def test_mixed_classification_when_text_misses_the_gate_quorum():
    # One rich text page out of four: below the max(1, n//2) quorum the
    # generic native gate demands, but clearly not a pure scan either.
    profile = inspect_pdf(_pdf_with_pages([LONG_TEXT, None, None, None]))
    assert profile.classification == "mixed"
    assert profile.likely_ocr_required is True
    assert profile.text_pages == [True, False, False, False]


def test_mixed_classification_when_total_misses_the_gate():
    # One usable text page (>= per-page threshold) whose document total still
    # misses the gate: not digital, but visibly not a pure scan either.
    profile = inspect_pdf(_pdf_with_pages([MID_TEXT, None]))
    assert MIN_PAGE_TEXT_CHARS <= profile.page_text_chars[0]
    assert profile.native_text_total_chars < MIN_TOTAL_TEXT_CHARS
    assert profile.classification == "mixed"


def test_scanned_classification_for_sub_threshold_scanner_footer_text():
    # A scan whose text layer is only a stray caption stays "scanned": no page
    # reaches the usable-text threshold the ladder's native gate applies.
    profile = inspect_pdf(_pdf_with_pages([SHORT_TEXT, None]))
    assert 0 < profile.native_text_total_chars < MIN_PAGE_TEXT_CHARS
    assert profile.classification == "scanned"


# ---------------------------------------------------------------------------
# malformed pages (per-page isolation)
# ---------------------------------------------------------------------------


def test_page_texts_isolates_a_malformed_page():
    class _BadPage:
        def get_text(self, kind):
            raise RuntimeError("damaged content stream")

    class _GoodPage:
        def get_text(self, kind):
            return [(0, 0, 1, 1, "recovered text", 0, 0)]

    pages, malformed = _page_texts([_GoodPage(), _BadPage(), _GoodPage()])
    assert malformed == [1]
    assert pages[1] == ""
    assert pages[0] == "recovered text"


# ---------------------------------------------------------------------------
# advisory signals (consumed by nothing in production)
# ---------------------------------------------------------------------------


def test_likely_account_count_counts_distinct_account_numbers():
    text = (
        "Account Number: 1234567890\nsome ledger rows\n"
        "Account Number: 9876543210\n" + LONG_TEXT
    )
    profile = inspect_pdf(_pdf_with_pages([text]))
    assert profile.likely_account_count == 2


def test_likely_account_count_marker_only_counts_one():
    profile = inspect_pdf(_pdf_with_pages(["Account Type\nBusiness Checking\n" + LONG_TEXT]))
    assert profile.likely_account_count == 1


def test_likely_account_count_zero_without_markers():
    profile = inspect_pdf(_pdf_with_pages([LONG_TEXT]))
    assert profile.likely_account_count == 0


def test_layout_signals_detect_period_pages_and_tables():
    text = (
        "Statement Period 01/01/54 - 01/31/54\n"
        "Page 1 of 4\n"
        "Date Description Amount Balance\n" + LONG_TEXT
    )
    profile = inspect_pdf(_pdf_with_pages([text]))
    assert profile.layout_signals.has_statement_period is True
    assert profile.layout_signals.has_page_n_of_m is True
    assert profile.layout_signals.has_table_markers is True


def test_layout_signals_absent_on_plain_text():
    profile = inspect_pdf(_pdf_with_pages(["plain prose with no statement furniture " * 20]))
    assert profile.layout_signals.has_statement_period is False
    assert profile.layout_signals.has_page_n_of_m is False
    assert profile.layout_signals.has_table_markers is False


def test_profile_serializes_to_a_plain_dict():
    profile = inspect_pdf(_pdf_with_pages([LONG_TEXT]))
    payload = profile.to_dict()
    assert payload["classification"] == "digital"
    assert payload["layout_signals"]["has_table_markers"] in (True, False)
    assert isinstance(payload["page_text_chars"], list)


# ---------------------------------------------------------------------------
# 109-document corpus parity — the profile must describe reality
# ---------------------------------------------------------------------------


def test_corpus_parity_with_the_balance_audit_source_type():
    """For every corpus statement, the profile's digital/scanned classification
    must match the committed audit's source_type column exactly:
    digital/native <-> digital, scanned/local_ocr <-> scanned. Native-text
    detection only — no OCR, no network — so it stays in the default suite."""
    corpus = statements_dir()
    audit_csv = PROJECT_ROOT / "docs" / "balance-metrics-audit-results.csv"
    if not corpus.is_dir() or not audit_csv.exists():
        pytest.skip("statement corpus or audit CSV not present")

    with open(audit_csv, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 109

    expected_by_source_type = {"digital/native": "digital", "scanned/local_ocr": "scanned"}
    mismatches = []
    for row in rows:
        pdf_path = corpus / row["path"]
        profile = inspect_pdf(pdf_path.read_bytes())
        expected = expected_by_source_type[row["source_type"]]
        if profile.classification != expected:
            mismatches.append(
                f"{row['path']}: source_type={row['source_type']} "
                f"but profile={profile.classification}"
            )
        # The stored audit hash uses the same convention — cross-check it.
        assert profile.content_sha256 == row["sha256"]

    assert not mismatches, "\n".join(mismatches)
