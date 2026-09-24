"""Forced visual upload checks structural safety without reading native text."""
import importlib
import io

import pytest

from ocr.inspect import content_sha256


webapp = importlib.import_module("webapp.app")


def _pdf(*, encrypted=False):
    import fitz

    with fitz.open() as document:
        document.new_page().insert_text((72, 72), "FABRICATED NATIVE TEXT MUST NOT BE READ")
        return document.tobytes(**({"encryption": fitz.PDF_ENCRYPT_AES_256,
                                    "user_pw": "synthetic", "owner_pw": "synthetic"} if encrypted else {}))


def _post(raw):
    return webapp.app.test_client().post(
        "/upload", data={"force_ocr": "1", "files": (io.BytesIO(raw), "synthetic.pdf")},
        content_type="multipart/form-data")


def test_forced_upload_persists_only_structural_profile(monkeypatch):
    monkeypatch.delenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", raising=False)
    monkeypatch.setattr("ocr.inspect._page_texts", lambda *a: pytest.fail("native text was read"))
    queued = []
    monkeypatch.setattr(webapp, "_enqueue_job", lambda *args: queued.append(args))
    raw = _pdf()
    response = _post(raw)
    assert response.status_code == 200
    job = response.get_json()["jobs"][0]
    assert len(queued) == 1 and queued[0][3] is True
    profile = webapp.store.storage.document_profile(job["id"])
    assert profile["valid_pdf"] and not profile["encrypted"] and profile["page_count"] == 1
    assert profile["content_sha256"] == content_sha256(raw)
    assert profile["classification"] == "unknown"
    assert profile["page_text_chars"] == profile["text_pages"] == []
    assert profile["likely_account_count"] == 0


@pytest.mark.parametrize("case", ["encrypted", "too_many_pages", "malformed"])
def test_forced_upload_preserves_encryption_and_page_safety_checks(monkeypatch, case):
    monkeypatch.delenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", raising=False)
    monkeypatch.setattr("ocr.inspect._page_texts", lambda *a: pytest.fail("native text was read"))
    monkeypatch.setattr(webapp, "_enqueue_job", lambda *a: pytest.fail("invalid document queued"))
    if case == "too_many_pages":
        monkeypatch.setattr(webapp, "pdf_page_count", lambda *a: webapp.MAX_UPLOAD_PAGES + 1)
    raw = b"%PDF-invalid synthetic" if case == "malformed" else _pdf(encrypted=case == "encrypted")
    response = _post(raw)
    assert response.status_code == 400
    expected = {"encrypted": "password-protected", "too_many_pages": "pages (limit",
                "malformed": "could not be read"}[case]
    assert expected in response.get_json()["error"]


def test_explicit_legacy_comparison_retains_native_preflight(monkeypatch):
    monkeypatch.setenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", "1")
    reads = []
    monkeypatch.setattr("ocr.inspect._page_texts", lambda *a: (reads.append(True) or (["SYNTHETIC"], [])))
    monkeypatch.setattr(webapp, "_enqueue_job", lambda *a: None)
    response = _post(_pdf())
    assert response.status_code == 200 and reads == [True]
    profile = webapp.store.storage.document_profile(response.get_json()["jobs"][0]["id"])
    assert profile["page_text_chars"] == [len("SYNTHETIC")]
