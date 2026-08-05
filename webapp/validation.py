"""Upload validation shared by the browser upload route and the `/v1` API.

An underwriter-facing platform accepts files from the outside world, so the
first gate is boring and strict: a real PDF header, a bounded size, a sanitized
filename, and a page count the OCR tier can actually finish.
"""
from __future__ import annotations
import hashlib
import os
import re
from dataclasses import dataclass

from .config import Settings, get_settings

PDF_MAGIC = b"%PDF-"
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ ()\-]")
MAX_FILENAME_LENGTH = 180


class UploadRejected(ValueError):
    """A submitted file failed validation. `code` is the stable API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    data: bytes
    size_bytes: int
    content_sha256: str


def safe_filename(filename: str | None) -> str:
    """Strip directories and shell-hostile characters. An empty result becomes a
    generic name rather than an error, so a nameless browser upload still runs."""
    candidate = os.path.basename((filename or "").strip().replace("\\", "/"))
    candidate = _UNSAFE_FILENAME.sub("_", candidate).strip(" .")
    if not candidate:
        candidate = "statement.pdf"
    if len(candidate) > MAX_FILENAME_LENGTH:
        root, ext = os.path.splitext(candidate)
        candidate = root[: MAX_FILENAME_LENGTH - len(ext)] + ext
    return candidate


def validate_pdf_upload(
    filename: str | None,
    data: bytes,
    settings: Settings | None = None,
) -> ValidatedUpload:
    settings = settings or get_settings()
    name = safe_filename(filename)
    if not data:
        raise UploadRejected("empty_file", f"{name}: uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise UploadRejected(
            "file_too_large", f"{name}: exceeds the {limit_mb} MB upload limit"
        )
    if not data.startswith(PDF_MAGIC):
        raise UploadRejected("not_a_pdf", f"{name}: does not start with a PDF header")
    if not name.lower().endswith(".pdf"):
        raise UploadRejected("not_a_pdf", f"{name}: only .pdf uploads are accepted")
    return ValidatedUpload(
        filename=name,
        data=data,
        size_bytes=len(data),
        content_sha256=hashlib.sha256(data).hexdigest(),
    )


def validate_page_count(
    filename: str, page_count: int, settings: Settings | None = None
) -> None:
    settings = settings or get_settings()
    if page_count > settings.max_pages:
        raise UploadRejected(
            "too_many_pages",
            f"{filename}: {page_count} pages exceeds the {settings.max_pages} page limit",
        )
