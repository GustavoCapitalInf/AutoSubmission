"""Job facade over the durable store (Wave 1 / D-1).

``JobStore`` keeps the public surface the routes and worker already use, but
every terminal state and every served artifact now comes from
``webapp.storage.Storage`` (SQLite + on-disk PDF store). Only ``pdf_bytes``
stays purely in memory, while a job is queued/processing (released on
completion; afterwards the bytes are served from the disk store by content
hash).

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
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass

from analysis import zelle_view
from analysis.payload_shape import is_document_payload, payload_accounts

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
    # The earliest prior job holding the same bytes (`Storage.duplicate_of`), once known: set from the creation
    # transaction for a job created here, read once for a job loaded from storage. Final once known, None included:
    # see `Storage.record_upload`.
    duplicate_of: str | None = None
    duplicate_of_known: bool = False


@dataclass(frozen=True)
class JobSnapshot:
    """`analysis` is shared with the job rather than copied: every JobStore write replaces a job's analysis and none
    edits it in place (test_a_snapshot_outlives_a_review_a_reanalysis_and_a_result)."""

    id: str
    filename: str
    status: str
    analysis: dict | None
    analysis_error: str | None
    error: str | None
    content_sha256: str | None


class UnknownJobs(LookupError):
    def __init__(self, ids: list[str]) -> None:
        super().__init__(ids)
        self.ids = ids


def _classification_for(
    analysis: dict | None, source_location: str, account: int | None = None
) -> dict | None:
    """The classification record currently stored for a transaction, located
    by its ``source_location`` — captured as the prior state of a review.

    Every account is searched, in printed order, unless ``account`` (1-based,
    printed order) names the posting's own. A reviewer acts on a posting, and a
    posting belongs to one account of the document — so reading only the first
    would silently find nothing for every posting in the second, and "nothing"
    here reads as "this transaction was never classified". A location numbers a
    posting within its account, so when the review named the account, only that
    account is read: the first account's posting of the same number is another
    posting (`apply_serialized_revenue_review` refuses the unnamed ambiguous case).
    """
    if not isinstance(analysis, dict):
        return None
    if is_document_payload(analysis):
        accounts = payload_accounts(
            analysis, surface="webapp/jobs.py::_classification_for")
    else:
        accounts = [analysis]
    if account is not None:
        accounts = accounts[account - 1:account] if account >= 1 else []
    for holder in accounts:
        statement = holder.get("statement")
        if not isinstance(statement, dict):
            continue
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


def _shown_reading(analysis: dict | None, zelle_true_revenue: bool | None) -> dict | None:
    """The stored analysis in the Zelle reading a reviewer saw (analysis/zelle_view.py `reading`), or the stored
    analysis itself when no reading is named. Materialised once per call; it never mutates the stored analysis."""
    if zelle_true_revenue is None or not isinstance(analysis, dict):
        return analysis
    return zelle_view.reading(analysis, counted=zelle_true_revenue)


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
        pdf_bytes: bytes | None = None,
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            filename=filename,
            page_count=page_count,
            force_ocr=force_ocr,
        )
        if pdf_bytes is not None:
            job.content_sha256 = content_sha256(pdf_bytes)
            job.pdf_bytes = pdf_bytes  # held in RAM only while queued/processing
            self._storage.save_pdf(job.content_sha256, pdf_bytes)
        # One transaction: the document row, the job row and the upload audit row, and the duplicate answer read
        # inside it.
        job.duplicate_of = self._storage.record_upload(
            job.id,
            filename=filename,
            content_sha256=job.content_sha256,
            byte_size=len(pdf_bytes) if pdf_bytes is not None else 0,
            force_ocr=force_ocr,
            page_count=page_count,
        )
        job.duplicate_of_known = True
        with self._lock:
            self._jobs[job.id] = job
        return job

    def duplicate_of(self, job_id: str) -> str | None:
        """The earliest prior job holding the same bytes as this job, or None: `Storage.duplicate_of`, asked at most
        once per job. The dashboard polls /status every 1.4 s for every job in flight, and each storage call opened
        a connection and ran two queries while the worker held the interpreter, so a poll took tens to hundreds of
        milliseconds. The answer is final once the job exists (`Storage.record_upload` says why), so the first one
        is kept on the job."""
        job = self.get(job_id)
        if job is None or not job.content_sha256:
            return None
        with self._lock:
            if job.duplicate_of_known:
                return job.duplicate_of
        value = self._storage.duplicate_of(job_id)
        with self._lock:
            if not job.duplicate_of_known:
                job.duplicate_of, job.duplicate_of_known = value, True
            return job.duplicate_of

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

    def snapshot(self, job_ids: Sequence[str]) -> list[JobSnapshot]:
        """The jobs at one moment, in `job_ids` order: every field is copied under one hold of `_lock`, which every
        in-memory write takes. Raises UnknownJobs naming every id the store does not hold."""
        missing = [job_id for job_id in job_ids if self.get(job_id) is None]
        if missing:
            raise UnknownJobs(missing)
        with self._lock:
            jobs = [self._jobs[job_id] for job_id in job_ids]
            return [
                JobSnapshot(
                    id=job.id, filename=job.filename, status=job.status, analysis=job.analysis,
                    analysis_error=job.analysis_error, error=job.error, content_sha256=job.content_sha256,
                )
                for job in jobs
            ]

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

    def apply_reanalysis(
        self,
        job_id: str,
        analysis: dict,
        *,
        replayed: tuple[int, ...] = (),
        not_replayed: tuple[int, ...] = (),
        decided_by_rules: tuple[int, ...] = (),
    ) -> dict | None:
        """Replace a job's analysis with a re-analysis of its statement: the same job, so the same id and the same
        place in Recent. The analysis replaced goes to the audit log first, in the same storage transaction
        (`Storage.record_reanalysis`), beside the ids of the review decisions the re-analysis replayed, of those that
        need redoing, and of those a rule now decides (their row no longer awaits review, so there is nothing to
        redo). A re-analysis that produced an analysis has no analysis error."""
        job = self.get(job_id)
        if job is None:
            return None
        written = self._storage.record_reanalysis(
            job_id,
            analysis_json=json.dumps(analysis),
            detail={
                "reviews_replayed": list(replayed),
                "reviews_not_replayed": list(not_replayed),
                "reviews_decided_by_rules": list(decided_by_rules),
            },
        )
        if not written:
            return None
        with self._lock:
            job.analysis = deepcopy(analysis)
            job.analysis_error = None
        return deepcopy(analysis)

    def apply_review(
        self,
        job_id: str,
        analysis: dict,
        *,
        source_location: str,
        decision: str,
        actor: str = "local-analyst",
        account: int | None = None,
        zelle_true_revenue: bool | None = None,
    ) -> dict | None:
        """Replace the stored analysis AND record the append-only review
        decision (actor, timestamp, prior state) in one storage transaction.
        `account` is the 1-based account the reviewer named, if any. With
        `zelle_true_revenue` given, the prior state is read from that Zelle
        reading (analysis/zelle_view.py `reading`), the one the reviewer saw;
        the storage schema is unchanged."""
        job = self.get(job_id)
        if job is None or job.analysis is None:
            return None
        shown = _shown_reading(job.analysis, zelle_true_revenue)
        prior_state = _classification_for(shown, source_location, account)
        self._storage.record_review(
            job_id,
            analysis_json=json.dumps(analysis),
            source_location=source_location,
            decision=decision,
            actor=actor,
            prior_state_json=json.dumps(prior_state) if prior_state is not None else None,
            account=account,
        )
        with self._lock:
            job.analysis = deepcopy(analysis)
        return deepcopy(analysis)

    def apply_reviews(
        self,
        job_id: str,
        analysis: dict,
        *,
        decisions: list[tuple[str, str, int | None]],
        actor: str = "local-analyst",
        zelle_true_revenue: bool | None = None,
    ) -> dict | None:
        """Replace the stored analysis AND record every decision of a batch —
        `(source_location, decision, account)` — each with the prior state it
        changed, in one storage transaction. The caller has already applied every
        decision to `analysis`; a posting appears at most once in a batch, so each
        prior state is that posting's stored record before the batch. With
        `zelle_true_revenue` given, the prior states are read from that Zelle
        reading, materialised once for the whole batch."""
        job = self.get(job_id)
        if job is None or job.analysis is None:
            return None
        shown = _shown_reading(job.analysis, zelle_true_revenue)
        rows = []
        for source_location, decision, account in decisions:
            prior_state = _classification_for(shown, source_location, account)
            rows.append((source_location, decision, json.dumps(prior_state) if prior_state is not None else None,
                         account))
        self._storage.record_reviews(job_id, analysis_json=json.dumps(analysis), decisions=rows, actor=actor)
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
        *,
        persist: bool = True,
    ) -> list[str]:
        """Startup re-hydration: explicitly mark every job that was in flight
        when the process died. Nothing is silently lost — the job row stays
        queryable with status 'interrupted' and this explanatory error.

        ``persist=False``: a read-only start-up cannot write, so this process
        shows those jobs interrupted with the same note while their rows stay as
        they were; the next start that can write marks them durably."""
        if not persist:
            ids = self._storage.in_flight_job_ids()
            for job_id in ids:
                job = self.get(job_id)
                if job is not None:
                    with self._lock:
                        job.status = "interrupted"
                        job.stage = "interrupted"
                        job.error = note
                        job.pdf_bytes = None
            return ids
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
