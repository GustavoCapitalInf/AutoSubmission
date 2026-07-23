from __future__ import annotations
import threading
import uuid
from dataclasses import dataclass, field


@dataclass
class Job:
    id: str
    filename: str
    status: str = "queued"  # "queued" | "processing" | "done" | "error"
    markdown: str | None = None
    html: str | None = None
    error: str | None = None
    pdf_bytes: bytes | None = None
    page_count: int = 0
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


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, filename: str) -> Job:
        job = Job(id=str(uuid.uuid4()), filename=filename)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = status

    def append_page_live(self, job_id: str, page: int, chunk: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.pages_live[page] = job.pages_live.get(page, "") + chunk

    def set_result(self, job_id: str, markdown: str, html: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.markdown = markdown
                job.html = html
                job.status = "done"

    def set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.error = error
                job.status = "error"
