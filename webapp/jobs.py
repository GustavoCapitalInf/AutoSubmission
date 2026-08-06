"""Job facade over the durable store (Wave 1 / D-1).

``JobStore`` keeps the public surface the routes and worker already use, but
every terminal state and every served artifact now comes from
``webapp.storage.Storage`` (SQLite + on-disk PDF store). Only in-flight
working state stays purely in memory:

* per-page live OCR buffers (``pages_live`` — streaming scratch space), and
* ``pdf_bytes`` while a job is queued/processing (released on completion;
  afterwards the bytes are served from the disk store by content hash).

Single-writer discipline: this facade is used by exactly one worker thread
plus request threads in one process — see ``webapp/storage.py`` for the full
concurrency contract.

D-3: ``JobStore.cache`` hands the worker the content-hash artifact cache
bound to this store's data directory (``webapp/artifact_cache.py``), so
re-processing byte-identical content performs zero OCR and zero LLM calls.
"""
from __future__ import annotations
import json
import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field

from .artifact_cache import ArtifactCache
from .storage import Storage, content_sha256


@dataclass
class Job:
    id: str
    filename: str
    status: str = "queued"  # "queued" | "processing" | "done" | "error" | "interrupted"
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
    content_sha256: str | None = None
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


def _classification_for(analysis: dict | None, source_location: str) -> dict | None:
    """The classification record currently stored for a transaction, located
    by its ``source_location`` — captured as the prior state of a review."""
    if not isinstance(analysis, dict):
        return None
    statement = analysis.get("statement")
    if not isinstance(statement, dict):
        return None
    for transaction in statement.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        classification = transaction.get("classification")
        if (
            isinstance(classification, dict)
            and classification.get("source_location") == source_location
        ):
            return deepcopy(classification)
    return None


class JobStore:
    def __init__(self, storage: Storage | None = None) -> None:
        self._storage = storage if storage is not None else Storage()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._cache: ArtifactCache | None = None

    @property
    def storage(self) -> Storage:
        return self._storage

    @property
    def cache(self) -> ArtifactCache:
        """The D-3 artifact cache bound to this store's data directory.

        Built lazily and reused: one cache per store means a JobStore pointed
        at a tmp dir (every test) is automatically cache-isolated too."""
        if self._cache is None:
            self._cache = ArtifactCache(self._storage)
        return self._cache

    def record_cache_hit(self, job_id: str, stage: str, cache_key: str | None) -> None:
        """Audit-log a served-from-cache stage. Write-only bookkeeping: it
        records what was NOT recomputed, which is what makes a re-run's zero
        OCR/LLM cost visible after the fact (and is H-3's hook)."""
        self._storage.append_audit(
            "cache_hit", job_id=job_id, detail={"stage": stage, "cache_key": cache_key}
        )

    # ------------------------------------------------------------------
    # creation / retrieval
    # ------------------------------------------------------------------

    def create(
        self,
        filename: str,
        *,
        page_count: int = 0,
        force_ocr: bool = False,
        parse_mode: str = "auto",
        pdf_bytes: bytes | None = None,
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            filename=filename,
            page_count=page_count,
            force_ocr=force_ocr,
            parse_mode=parse_mode,
        )
        document_id = None
        if pdf_bytes is not None:
            job.content_sha256 = content_sha256(pdf_bytes)
            job.pdf_bytes = pdf_bytes  # held in RAM only while queued/processing
            self._storage.save_pdf(job.content_sha256, pdf_bytes)
            document_id = self._storage.record_document(
                job.content_sha256, filename, len(pdf_bytes), page_count
            )
        self._storage.create_job(
            job.id,
            filename=filename,
            document_id=document_id,
            force_ocr=force_ocr,
            parse_mode=parse_mode,
            page_count=page_count,
        )
        self._storage.append_audit(
            "upload",
            job_id=job.id,
            detail={"filename": filename, "content_sha256": job.content_sha256},
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return job
        row = self._storage.load_job(job_id)
        if row is None:
            return None
        job = self._job_from_row(row)
        with self._lock:
            # setdefault: another thread may have hydrated it meanwhile.
            return self._jobs.setdefault(job_id, job)

    @staticmethod
    def _job_from_row(row: dict) -> Job:
        analysis = None
        if row.get("analysis_json"):
            analysis = json.loads(row["analysis_json"])
        return Job(
            id=row["id"],
            filename=row["filename"],
            status=row["status"],
            markdown=row.get("markdown"),
            html=row.get("html"),
            analysis=analysis,
            analysis_error=row.get("analysis_error"),
            parse_model=row.get("parse_model"),
            force_ocr=bool(row.get("force_ocr")),
            parse_mode=row.get("parse_mode") or "auto",
            error=row.get("error"),
            pdf_bytes=None,  # never re-loaded into RAM; served from disk on demand
            page_count=int(row.get("page_count") or 0),
            stage=row.get("stage") or row["status"],
            content_sha256=row.get("content_sha256"),
        )

    # ------------------------------------------------------------------
    # status / stage transitions (persisted)
    # ------------------------------------------------------------------

    def set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = status
                job.stage = status
        self._storage.set_job_status(job_id, status)

    def set_stage(self, job_id: str, stage: str, parse_model: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.stage = stage
                if parse_model is not None:
                    job.parse_model = parse_model
        self._storage.set_job_stage(job_id, stage, parse_model)

    # ------------------------------------------------------------------
    # live OCR buffers (in-flight working state — memory only by design)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # results / errors (persisted; terminal states release pdf_bytes)
    # ------------------------------------------------------------------

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
                job.pdf_bytes = None  # RAM release: disk store serves from here on
        self._storage.set_job_result(
            job_id,
            markdown=markdown,
            html=html,
            analysis_json=json.dumps(analysis) if analysis is not None else None,
            analysis_error=analysis_error,
            parse_model=parse_model,
        )

    def set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.error = error
                job.status = "error"
                job.pdf_bytes = None  # RAM release on the terminal state
        self._storage.set_job_error(job_id, error)

    # ------------------------------------------------------------------
    # analysis mutation / analyst review
    # ------------------------------------------------------------------

    def replace_analysis(self, job_id: str, analysis: dict) -> dict | None:
        job = self.get(job_id)
        if job is None or job.analysis is None:
            return None
        with self._lock:
            job.analysis = deepcopy(analysis)
        self._storage.set_job_analysis(job_id, json.dumps(analysis))
        return deepcopy(analysis)

    def apply_review(
        self,
        job_id: str,
        analysis: dict,
        *,
        source_location: str,
        decision: str,
        actor: str = "local-analyst",
    ) -> dict | None:
        """Replace the stored analysis AND record the append-only review
        decision (actor, timestamp, prior state) in one storage transaction."""
        job = self.get(job_id)
        if job is None or job.analysis is None:
            return None
        prior_state = _classification_for(job.analysis, source_location)
        self._storage.record_review(
            job_id,
            analysis_json=json.dumps(analysis),
            source_location=source_location,
            decision=decision,
            actor=actor,
            prior_state_json=json.dumps(prior_state) if prior_state is not None else None,
        )
        with self._lock:
            job.analysis = deepcopy(analysis)
        return deepcopy(analysis)

    def review_history(self, job_id: str) -> list[dict]:
        return self._storage.review_history(job_id)

    # ------------------------------------------------------------------
    # PDF bytes (RAM while in flight, disk afterwards)
    # ------------------------------------------------------------------

    def pdf_bytes(self, job_id: str) -> bytes | None:
        job = self.get(job_id)
        if job is None:
            return None
        if job.pdf_bytes is not None:
            return job.pdf_bytes
        if job.content_sha256:
            return self._storage.load_pdf(job.content_sha256)
        return None

    # ------------------------------------------------------------------
    # packages / audit / startup re-hydration
    # ------------------------------------------------------------------

    def create_package(self, job_ids: list[str], reference: str | None = None) -> str:
        return self._storage.create_package(job_ids, reference)

    def package_member_ids(self, package_id: str) -> list[str] | None:
        return self._storage.package_member_ids(package_id)

    def record_export(
        self,
        *,
        job_id: str | None = None,
        package_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        self._storage.append_audit("export", job_id=job_id, package_id=package_id, detail=detail)

    def mark_interrupted(
        self,
        note: str = (
            "interrupted: the server stopped while this job was queued or "
            "processing; re-upload the statement to reprocess it"
        ),
    ) -> list[str]:
        """Startup re-hydration: explicitly mark every job that was in flight
        when the process died. Nothing is silently lost — the job row stays
        queryable with status 'interrupted' and this explanatory error."""
        ids = self._storage.mark_interrupted_jobs(note)
        with self._lock:
            for job_id in ids:
                job = self._jobs.get(job_id)
                if job is not None:
                    job.status = "interrupted"
                    job.stage = "interrupted"
                    job.error = note
                    job.pdf_bytes = None
        return ids
