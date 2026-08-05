from __future__ import annotations
import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .config import DEFAULT_TENANT
from .storage import JobStoreBase, utc_now


@dataclass
class Job:
    id: str
    filename: str
    status: str = "queued"  # "queued" | "processing" | "done" | "error"
    markdown: str | None = None
    html: str | None = None
    analysis: dict | None = None
    analysis_error: str | None = None
    parse_model: str | None = None
    force_ocr: bool = False
    parse_mode: str = "auto"
    error: str | None = None
    pdf_bytes: bytes | None = None
    page_count: int = 0
    stage: str = "queued"
    # Tenant separation: every read path filters on this, so one customer's job
    # id is never a handle on another customer's statement.
    tenant_id: str = DEFAULT_TENANT
    submitted_by: str | None = None
    # Set only when the submitter supplied an Idempotency-Key, so a retried
    # upload returns the original job instead of paying for a second OCR pass.
    idempotency_key: str | None = None
    content_sha256: str | None = None
    size_bytes: int = 0
    attempts: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    # Per-page live OCR buffers, keyed by 0-based page index. Pages are OCR'd
    # concurrently, so buffers fill out of order; `live_text` renders them back
    # in page order with the "--- Page N ---" markers the viewer keys boxes on.
    pages_live: dict[int, str] = field(default_factory=dict)

    @property
    def live_text(self) -> str:
        return "".join(
            f"\n\n--- Page {p + 1} ---\n\n{self.pages_live[p]}"
            for p in sorted(self.pages_live)
        )


class InMemoryJobStore(JobStoreBase):
    """Process-local store. Kept for tests and single-shot local runs; production
    uses `SqliteJobStore`, which survives a restart."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._audit: list[dict] = []
        self._lock = threading.Lock()

    def create(
        self,
        filename: str,
        *,
        tenant_id: str = DEFAULT_TENANT,
        pdf_bytes: bytes | None = None,
        force_ocr: bool = False,
        parse_mode: str = "auto",
        page_count: int = 0,
        idempotency_key: str | None = None,
        submitted_by: str | None = None,
        content_sha256: str | None = None,
        size_bytes: int = 0,
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            filename=filename,
            tenant_id=tenant_id,
            pdf_bytes=pdf_bytes,
            force_ocr=force_ocr,
            parse_mode=parse_mode,
            page_count=page_count,
            idempotency_key=idempotency_key,
            submitted_by=submitted_by,
            content_sha256=content_sha256,
            size_bytes=size_bytes,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str, *, tenant_id: str | None = None) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None or (tenant_id is not None and job.tenant_id != tenant_id):
            return None
        return job

    def set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = status
                job.stage = status
                job.updated_at = utc_now()

    def set_stage(self, job_id: str, stage: str, parse_model: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.stage = stage
                job.updated_at = utc_now()
                if parse_model is not None:
                    job.parse_model = parse_model

    def append_page_live(self, job_id: str, page: int, chunk: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.pages_live[page] = job.pages_live.get(page, "") + chunk

    def set_page_live(self, job_id: str, page: int, text: str) -> None:
        """Replace a page's live buffer wholesale — used when a fallback/recovery
        re-OCR (off-stream) supersedes the originally streamed read."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.pages_live[page] = text

    def pages_live_ordered(self, job_id: str) -> list[str]:
        """Snapshot the per-page live buffers in page order (thread-safe)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return []
            return [job.pages_live[p] for p in sorted(job.pages_live)]

    def set_result(
        self,
        job_id: str,
        markdown: str,
        html: str,
        analysis: dict | None = None,
        analysis_error: str | None = None,
        parse_model: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.markdown = markdown
                job.html = html
                job.analysis = analysis
                job.analysis_error = analysis_error
                job.parse_model = parse_model
                job.status = "done"
                job.stage = "done"
                job.updated_at = utc_now()

    def replace_analysis(self, job_id: str, analysis: dict) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.analysis is None:
                return None
            job.analysis = deepcopy(analysis)
            job.updated_at = utc_now()
            return deepcopy(job.analysis)

    def set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.error = error
                job.status = "error"
                job.stage = "error"
                job.updated_at = utc_now()

    # -- durable-queue surface ------------------------------------------------

    def claim_next(self, lease_seconds: int = 900) -> Job | None:
        with self._lock:
            for job in self._jobs.values():
                if job.status == "queued" and job.pdf_bytes is not None:
                    job.status = "processing"
                    job.stage = "processing"
                    job.attempts += 1
                    job.updated_at = utc_now()
                    return job
        return None

    def requeue_stale(self, lease_seconds: int = 900, max_attempts: int = 3) -> list[str]:
        return []

    def find_by_idempotency_key(self, tenant_id: str, key: str) -> Job | None:
        with self._lock:
            for job in self._jobs.values():
                if job.tenant_id == tenant_id and job.idempotency_key == key:
                    return job
        return None

    def list_jobs(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.tenant_id == tenant_id]
        if status:
            jobs = [job for job in jobs if job.status == status]
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return jobs[offset: offset + limit]

    def count_jobs(self, tenant_id: str, *, status: str | None = None) -> int:
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.tenant_id == tenant_id]
        if status:
            jobs = [job for job in jobs if job.status == status]
        return len(jobs)

    def delete(self, job_id: str, *, tenant_id: str | None = None) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or (tenant_id is not None and job.tenant_id != tenant_id):
                return False
            del self._jobs[job_id]
            return True

    def purge_expired(self, max_age_seconds: int) -> int:
        cutoff = datetime.now(UTC).timestamp() - max_age_seconds
        removed = 0
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                try:
                    created = datetime.fromisoformat(job.created_at).timestamp()
                except ValueError:
                    continue
                if created < cutoff:
                    del self._jobs[job_id]
                    removed += 1
        return removed

    def drop_document(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.pdf_bytes = None

    def append_audit(self, entry: dict) -> None:
        with self._lock:
            self._audit.append(dict(entry))

    def audit_events(
        self, tenant_id: str | None = None, job_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        with self._lock:
            events = list(self._audit)
        if tenant_id:
            events = [event for event in events if event.get("tenant_id") == tenant_id]
        if job_id:
            events = [event for event in events if event.get("job_id") == job_id]
        return events[-limit:][::-1]


# Historical name. New code should depend on `JobStoreBase` (the interface) or
# ask `webapp.storage.create_job_store()` for the configured implementation.
JobStore = InMemoryJobStore
