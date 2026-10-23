"""The v1 API under test: an isolated store, a fake worker, and a client that validates every API response against
the contract models (`webapp.api.contract`). Fabricated statements and PDF bytes only."""
from __future__ import annotations

import io
import json
import uuid
from collections.abc import Callable

from pydantic import TypeAdapter

from webapp.api.contract import ERRORS, ErrorResponse, Package
from webapp.jobs import JobStore
from webapp.storage import Storage

TOKEN = "fabricated-api-token-" + "a1b2c3d4" * 4
PACKAGE = TypeAdapter(Package)

#: What the fake worker does with a file of a given name: `outcome(store, job_id)`. A name it does not know stays
#: queued.
Outcome = Callable[[JobStore, str], None]


def analysed(analysis: dict) -> Outcome:
    return lambda store, job_id: store.set_result(job_id, "# Fabricated", "<p>Fabricated</p>", analysis=analysis)


def refused(analysis_error: str) -> Outcome:
    return lambda store, job_id: store.set_result(job_id, "# Fabricated", "<p>Fabricated</p>", analysis=None,
                                                  analysis_error=analysis_error)


def crashed(store: JobStore, job_id: str) -> None:
    store.set_error(job_id, "analysis stage failed: ValueError (message withheld)")


def pdf() -> bytes:
    return b"%PDF-SAMPLE-" + uuid.uuid4().hex.encode()


def _refuse_constant(name: str) -> None:
    raise ValueError(f"a JSON body carries {name}")


def validated(response):
    """`response` once it is checked: JSON without NaN or Infinity, never cached, and a Package (2xx) or an
    ErrorResponse whose code's catalog status is the response's."""
    assert response.mimetype == "application/json"
    assert response.headers["Cache-Control"] == "no-store"
    text = response.get_data(as_text=True)
    json.loads(text, parse_constant=_refuse_constant)
    if response.status_code < 300:
        PACKAGE.validate_json(text, strict=True)
    else:
        error = ErrorResponse.model_validate_json(text, strict=True).error
        assert ERRORS[error.code].status == response.status_code
    return response


class Api:
    """The test client, its bearer token and the store behind it. Every call returns a validated response."""

    def __init__(self, client, store: JobStore, outcomes: dict[str, Outcome]) -> None:
        self.client, self.store, self.outcomes = client, store, outcomes

    def get(self, path: str, *, token: str | None = TOKEN, **kwargs):
        return validated(self.client.get(path, headers=_auth(token), **kwargs))

    def put(self, path: str, files: list[tuple[str, bytes]], *, token: str | None = TOKEN, **kwargs):
        data = {"files": [(io.BytesIO(content), name) for name, content in files]} if files else {}
        return validated(self.client.put(path, data=data, content_type="multipart/form-data", headers=_auth(token),
                                         **kwargs))

    def call(self, method: str, path: str, *, token: str | None = TOKEN, **kwargs):
        return validated(self.client.open(path, method=method, headers=_auth(token), **kwargs))


def _auth(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token is not None else {}


def package_path() -> str:
    return f"/api/v1/packages/{uuid.uuid4()}"


def make_api(tmp_path, monkeypatch) -> Api:
    """The API on its own store, with the token set, no browser password and a fake worker that finishes each job
    synchronously from `Api.outcomes`."""
    from webapp import app as webapp_app

    store = JobStore(Storage(tmp_path / "data"))
    outcomes: dict[str, Outcome] = {}
    monkeypatch.setenv("WEBAPP_API_TOKEN", TOKEN)
    monkeypatch.delenv("WEBAPP_AUTH_PASSWORD", raising=False)
    monkeypatch.setattr(webapp_app, "store", store)
    monkeypatch.setattr("webapp.intake.pdf_page_count", lambda pdf_bytes: 1)

    def enqueue(job_id: str, pdf_bytes: bytes, filename: str, force_ocr: bool) -> None:
        outcome = outcomes.get(filename)
        if outcome is not None:
            outcome(store, job_id)

    monkeypatch.setattr(webapp_app, "_enqueue_job", enqueue)
    return Api(webapp_app.app.test_client(), store, outcomes)
