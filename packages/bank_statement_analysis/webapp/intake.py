"""How statements enter the store, for the dashboard's upload and the API's packages: a batch is checked whole,
stored whole, and queued only when the caller's block completes."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Literal, NamedTuple

from ocr.inspect import DocumentProfile, inspect_pdf
from ocr.rasterize import pdf_page_count

from .jobs import Job, JobStore

# Upload ceilings. Every value here is enforced server-side and mirrored in the
# dropzone caption, so what the operator is told is what the server does.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_UPLOAD_FILES = 25
MAX_UPLOAD_PAGES = 500

#: The free-space floor's refusal (507): fixed text, never a measured figure or a path.
STORAGE_NEARLY_FULL = "the server's storage is nearly full; no statement was accepted"

#: The answer when the batch could not be stored: every job it created is marked failed with this text and none is
#: queued. Fixed text, never an exception's.
UPLOAD_NOT_STORED = "the statements could not be stored; none was accepted. Upload them again"

IntakeRefusalCode = Literal[
    "no_statements", "too_many_statements", "invalid_filename", "statement_too_large", "not_a_pdf", "pdf_encrypted",
    "pdf_unreadable", "too_many_pages", "storage_full", "not_stored",
]


class Upload(NamedTuple):
    filename: str
    pdf_bytes: bytes


class CheckedUpload(NamedTuple):
    filename: str
    pdf_bytes: bytes
    page_count: int
    profile: DocumentProfile


class IntakeRefused(Exception):
    """A refused batch. Nothing was stored or queued, or (`not_stored`) every job the batch created is marked failed
    and none is queued. `message` is the dashboard's text; `filename` names the refused file, when one was."""

    def __init__(self, status: int, code: IntakeRefusalCode, message: str, filename: str | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.filename = status, code, message, filename

    def browser_body(self) -> dict:
        return {"error": self.message, **({"filename": self.filename} if self.filename is not None else {})}


def check_batch_size(count: int) -> None:
    """Refuses (400) a batch of no file or of more than MAX_UPLOAD_FILES."""
    if not count:
        raise IntakeRefused(400, "no_statements", "no files uploaded")
    if count > MAX_UPLOAD_FILES:
        raise IntakeRefused(400, "too_many_statements", f"{count} files uploaded (limit {MAX_UPLOAD_FILES} per batch)")


def checked_upload(upload: Upload) -> CheckedUpload:
    """One file, checked in this order: its name, its size, the `%PDF-` header, encryption, then its page count.
    Raises IntakeRefused (400).

    A name carrying CR, LF or `-->` is refused first, with the class name `ocr.document.StatementMarkdown` would
    refuse it with (ProvenanceTokenError) and without the name: CR/LF is the multipart delimiter, so such a name is
    never echoed. Every other refusal names the file, which is safe to echo."""
    filename, pdf_bytes = upload
    if "\r" in filename or "\n" in filename or "-->" in filename:
        raise IntakeRefused(400, "invalid_filename", "ProvenanceTokenError")
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        limit = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise IntakeRefused(400, "statement_too_large", f"file exceeds the {limit} MB limit", filename)
    if not pdf_bytes.startswith(b"%PDF-"):
        raise IntakeRefused(400, "not_a_pdf", "file is not a PDF", filename)
    profile = inspect_pdf(pdf_bytes)
    if profile.encrypted:
        raise IntakeRefused(400, "pdf_encrypted", "PDF is password-protected; upload a decrypted copy", filename)
    try:
        page_count = pdf_page_count(pdf_bytes)
    except Exception:
        raise IntakeRefused(400, "pdf_unreadable", "PDF could not be read", filename) from None
    if page_count > MAX_UPLOAD_PAGES:
        raise IntakeRefused(400, "too_many_pages", f"PDF has {page_count} pages (limit {MAX_UPLOAD_PAGES})", filename)
    return CheckedUpload(filename, pdf_bytes, page_count, profile)


@contextmanager
def accepted_statements(
    store: JobStore,
    uploads: Sequence[Upload],
    *,
    enqueue: Callable[[str, bytes, str, bool], None],
    volume_nearly_full: Callable[[int], bool],
) -> Iterator[list[Job]]:
    """The batch's jobs, stored, one per upload in order. Entering checks the batch size, then every file
    (`checked_upload`), then the free-space floor, then stores every job; any refusal raises IntakeRefused and
    nothing is queued. When the block completes the jobs are queued; when it raises, every job is marked failed with
    UPLOAD_NOT_STORED, none is queued, and the exception propagates."""
    check_batch_size(len(uploads))
    checked = [checked_upload(upload) for upload in uploads]
    if volume_nearly_full(sum(len(upload.pdf_bytes) for upload in checked)):
        raise IntakeRefused(507, "storage_full", STORAGE_NEARLY_FULL)
    jobs = _stored(store, checked)
    try:
        yield jobs
    except BaseException:
        _mark_not_stored(store, jobs)
        raise
    for job, upload in zip(jobs, checked):
        enqueue(job.id, upload.pdf_bytes, upload.filename, False)


def _stored(store: JobStore, checked: list[CheckedUpload]) -> list[Job]:
    """Every job of the batch, with its document row, PDF and preflight profile, before any is queued: a storage
    failure on file k never leaves files 1..k-1 processed under ids the caller never received."""
    created: list[Job] = []
    try:
        for upload in checked:
            job = store.create(upload.filename, page_count=upload.page_count, force_ocr=False,
                               pdf_bytes=upload.pdf_bytes)
            created.append(job)
            store.storage.set_document_profile(job.id, json.dumps(upload.profile.to_dict()))
    except Exception:
        _mark_not_stored(store, created)
        raise IntakeRefused(503, "not_stored", UPLOAD_NOT_STORED) from None
    return created


def _mark_not_stored(store: JobStore, jobs: list[Job]) -> None:
    for job in jobs:
        try:
            store.set_error(job.id, UPLOAD_NOT_STORED)
        except Exception:
            pass  # best effort: a job still `queued` in storage is marked interrupted at the next start
