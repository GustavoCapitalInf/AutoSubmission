"""Job storage interface.

The web app, the worker and the `/v1` API all talk to a `JobStoreBase`, never to
a concrete backend. Two implementations ship today — an in-process dict for
tests and `SqliteJobStore` for production — and a Postgres/S3 backend can be
dropped in later without touching a route.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .config import DEFAULT_TENANT, Settings, get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from .jobs import Job


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class JobStoreBase(ABC):
    """Durable job state plus the queue operations a resilient worker needs.

    Live per-page OCR buffers are deliberately *not* part of the durable
    contract: they are progress output for the viewer, and a job whose worker
    died is re-run from its stored PDF rather than resumed mid-page.
    """

    # -- lifecycle -----------------------------------------------------------

    @abstractmethod
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
    ) -> "Job": ...

    @abstractmethod
    def get(self, job_id: str, *, tenant_id: str | None = None) -> "Job | None": ...

    @abstractmethod
    def set_status(self, job_id: str, status: str) -> None: ...

    @abstractmethod
    def set_stage(self, job_id: str, stage: str, parse_model: str | None = None) -> None: ...

    @abstractmethod
    def append_page_live(self, job_id: str, page: int, chunk: str) -> None: ...

    @abstractmethod
    def set_page_live(self, job_id: str, page: int, text: str) -> None: ...

    @abstractmethod
    def pages_live_ordered(self, job_id: str) -> list[str]: ...

    @abstractmethod
    def set_result(
        self,
        job_id: str,
        markdown: str,
        html: str,
        analysis: dict | None = None,
        analysis_error: str | None = None,
        parse_model: str | None = None,
    ) -> None: ...

    @abstractmethod
    def replace_analysis(self, job_id: str, analysis: dict) -> dict | None: ...

    @abstractmethod
    def set_error(self, job_id: str, error: str) -> None: ...

    # -- queue ---------------------------------------------------------------

    @abstractmethod
    def claim_next(self, lease_seconds: int = 900) -> "Job | None":
        """Atomically take the oldest queued job that still has its document."""

    @abstractmethod
    def requeue_stale(self, lease_seconds: int = 900, max_attempts: int = 3) -> list[str]:
        """Recover jobs whose worker died holding an expired lease."""

    # -- lookup, tenancy and retention ---------------------------------------

    @abstractmethod
    def find_by_idempotency_key(self, tenant_id: str, key: str) -> "Job | None": ...

    @abstractmethod
    def list_jobs(
        self,
        tenant_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> "list[Job]": ...

    @abstractmethod
    def count_jobs(self, tenant_id: str, *, status: str | None = None) -> int: ...

    @abstractmethod
    def delete(self, job_id: str, *, tenant_id: str | None = None) -> bool: ...

    @abstractmethod
    def purge_expired(self, max_age_seconds: int) -> int: ...

    @abstractmethod
    def drop_document(self, job_id: str) -> None:
        """Delete the stored PDF but keep the audit trail and the result."""

    # -- audit ---------------------------------------------------------------

    @abstractmethod
    def append_audit(self, entry: dict) -> None: ...

    @abstractmethod
    def audit_events(
        self, tenant_id: str | None = None, job_id: str | None = None, limit: int = 100
    ) -> list[dict]: ...


def create_job_store(settings: Settings | None = None) -> JobStoreBase:
    settings = settings or get_settings()
    if settings.job_store == "memory":
        from .jobs import InMemoryJobStore

        return InMemoryJobStore()
    from .sqlite_store import SqliteJobStore

    return SqliteJobStore(settings.database_path)
