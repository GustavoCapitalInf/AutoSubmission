"""The v1 routes. Authentication is not here: `webapp.auth.gate` runs before every request."""
from __future__ import annotations

import sqlite3
import threading
import uuid
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import datetime

from flask import Blueprint, Response, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed, NotFound, RequestEntityTooLarge

from ..intake import IntakeRefused, Upload
from ..jobs import Job, JobStore, UnknownJobs
from ..storage import content_sha256
from .contract import ProcessingPackage
from .projection import package_resource
from .wire import API_PREFIX, error_response, is_api_path, json_response

BLUEPRINT_NAME = "api_v1"
#: The endpoints a read-only start-up still serves; webapp/app.py adds them to its `_READ_ONLY_ENDPOINTS`.
READ_ONLY_ENDPOINTS = frozenset({f"{BLUEPRINT_NAME}.get_package"})
RETRY_AFTER_SECONDS = 10

Accept = Callable[[Sequence[Upload]], AbstractContextManager[list[Job]]]


def api_blueprint(*, store: Callable[[], JobStore], accept: Accept) -> Blueprint:
    """The v1 API under API_PREFIX. `store` and `accept` (the statement intake, `webapp.intake.accepted_statements`
    bound to the process's queue) are read at each request. The one state held here is the submission lock: one
    process serves the app."""
    api = Blueprint(BLUEPRINT_NAME, __name__, url_prefix=API_PREFIX)
    submitting = threading.Lock()

    @api.put("/packages/<package_id>", provide_automatic_options=False)
    def put_package(package_id: str) -> Response:
        """Create the package `package_id` from the request's PDFs (201), or answer an identical earlier request again
        (200: the same filenames and contents in the same order); other statements under a known id are a conflict."""
        if not _canonical_uuid(package_id):
            return error_response("invalid_package_id")
        uploads = [Upload(part.filename, part.read()) for part in request.files.getlist("files")]
        submitted = [(upload.filename, content_sha256(upload.pdf_bytes)) for upload in uploads]
        jobs = store()
        with submitting:
            members = jobs.storage.package_member_ids(package_id)
            if members is not None:
                held = [(document.filename, document.content_sha256) for document in jobs.snapshot(members)]
                if held != submitted:
                    return error_response("package_conflict")
                return _package_response(jobs, package_id, 200)
            try:
                with accept(uploads) as accepted:
                    jobs.storage.create_package([job.id for job in accepted], package_id=package_id)
            except (sqlite3.Error, OSError):
                return error_response("not_stored")
        return _package_response(jobs, package_id, 201)

    @api.get("/packages/<package_id>", provide_automatic_options=False)
    def get_package(package_id: str) -> Response:
        return _package_response(store(), package_id, 200)

    @api.errorhandler(IntakeRefused)
    def _refused(refusal: IntakeRefused) -> Response:
        return error_response(refusal.code, filename=refusal.filename)

    @api.errorhandler(UnknownJobs)
    def _members_missing(_exc: UnknownJobs) -> Response:
        return error_response("internal_error")

    @api.errorhandler(RequestEntityTooLarge)
    def _too_large(_exc: RequestEntityTooLarge) -> Response:
        return error_response("request_too_large")

    @api.errorhandler(HTTPException)
    def _http_error(exc: HTTPException) -> Response:
        """A malformed request is invalid_request; anything else, an unhandled exception included, is internal_error."""
        return error_response("invalid_request" if exc.code is not None and exc.code < 500 else "internal_error")

    @api.app_errorhandler(NotFound)
    def _no_route(exc: NotFound) -> Response | NotFound:
        return error_response("route_not_found") if is_api_path(request.path) else exc

    @api.app_errorhandler(MethodNotAllowed)
    def _no_method(exc: MethodNotAllowed) -> Response | MethodNotAllowed:
        if not is_api_path(request.path):
            return exc
        return error_response("method_not_allowed", headers={"Allow": ", ".join(sorted(exc.valid_methods or ()))})

    return api


def _canonical_uuid(text: str) -> bool:
    try:
        return str(uuid.UUID(text)) == text
    except ValueError:
        return False


def _package_response(jobs: JobStore, package_id: str, status: int) -> Response:
    stored = jobs.storage.package(package_id)
    if stored is None:
        return error_response("package_not_found")
    # A package the dashboard stored can list one job twice; it is one document.
    documents = jobs.snapshot(list(dict.fromkeys(stored["job_ids"])))
    body = package_resource(package_id, datetime.fromisoformat(stored["created_at"]), documents)
    headers = {}
    if isinstance(body, ProcessingPackage):
        headers["Retry-After"] = str(RETRY_AFTER_SECONDS)
    if status == 201:
        headers["Location"] = f"{API_PREFIX}/packages/{package_id}"
    return json_response(body, status, headers)
