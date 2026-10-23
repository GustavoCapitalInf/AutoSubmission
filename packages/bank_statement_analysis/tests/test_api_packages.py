import io
import json
import sqlite3
import uuid
from contextlib import closing

import pytest

from tests import zelle_setting_fixtures as zelle
from tests.api_client import analysed, crashed, make_api, package_path, pdf, refused
from tests.test_webapp_revenue_batch import _two_accounts
from tests.test_webapp_studio_views import CHECKING_ROWS, _document, _single
from webapp.intake import UPLOAD_NOT_STORED
from webapp.worker import NO_PARSER_MATCHED, NO_USABLE_TEXT

CREDITS_CENTS = round(sum(amount for _day, _text, amount in CHECKING_ROWS if amount > 0) * 100)


@pytest.fixture
def api(tmp_path, monkeypatch):
    return make_api(tmp_path, monkeypatch)


def _ready(api, analyses: dict[str, dict]):
    for name, analysis in analyses.items():
        api.outcomes[name] = analysed(analysis)
    path = package_path()
    response = api.put(path, [(name, pdf()) for name in analyses])
    assert response.status_code == 201
    return path, response.get_json()


def test_a_new_package_is_created_and_reads_ready_once_its_statements_are_analysed(api):
    api.outcomes.update({"march.pdf": analysed(_single(month=3)), "april.pdf": analysed(_single(month=4))})
    path = package_path()
    created = api.put(path, [("march.pdf", pdf()), ("april.pdf", pdf())])
    assert created.status_code == 201
    assert created.headers["Location"] == path
    body = created.get_json()
    assert (body["status"], body["api_version"], body["package_id"]) == ("ready", "1.0", path.rsplit("/", 1)[1])
    assert [document["filename"] for document in body["documents"]] == ["march.pdf", "april.pdf"]
    assert {document["status"] for document in body["documents"]} == {"analysed"}
    assert body["figures"]["months"] == 2
    assert body["figures"]["deposits_cents"] == 2 * CREDITS_CENTS
    assert api.get(path).get_data() == created.get_data()


def test_a_package_still_processing_says_when_to_ask_again(api):
    path = package_path()
    created = api.put(path, [("march.pdf", pdf())])
    assert (created.status_code, created.headers["Retry-After"]) == (201, "10")
    read = api.get(path)
    assert (read.status_code, read.headers["Retry-After"]) == (200, "10")
    body = read.get_json()
    assert body["status"] == "processing"
    assert [document["status"] for document in body["documents"]] == ["queued"]
    assert "figures" not in body and "review" not in body


def test_an_identical_request_is_answered_again_without_a_new_job(api):
    api.outcomes["march.pdf"] = analysed(_single())
    path, files = package_path(), [("march.pdf", pdf()), ("april.pdf", pdf())]
    first = api.put(path, files)
    jobs_before = _job_count(api)
    again = api.put(path, files)
    assert (first.status_code, again.status_code) == (201, 200)
    assert "Location" not in again.headers
    assert again.get_data() == first.get_data()
    assert _job_count(api) == jobs_before


@pytest.mark.parametrize("change", ["other bytes", "other name", "other order", "one fewer"])
def test_other_statements_under_a_known_id_are_a_conflict(api, change):
    path, files = package_path(), [("march.pdf", pdf()), ("april.pdf", pdf())]
    api.put(path, files)
    changed = {
        "other bytes": [files[0], ("april.pdf", pdf())],
        "other name": [files[0], ("may.pdf", files[1][1])],
        "other order": [files[1], files[0]],
        "one fewer": files[:1],
    }[change]
    jobs_before = _job_count(api)
    response = api.put(path, changed)
    assert (response.status_code, response.get_json()["error"]["code"]) == (409, "package_conflict")
    assert _job_count(api) == jobs_before


@pytest.mark.parametrize("package_id", ["not-a-uuid", str(uuid.uuid4()).upper(), uuid.uuid4().hex])
def test_a_package_id_must_be_a_lowercase_canonical_uuid(api, package_id):
    response = api.put(f"/api/v1/packages/{package_id}", [("march.pdf", pdf())])
    assert (response.status_code, response.get_json()["error"]["code"]) == (400, "invalid_package_id")
    assert _job_count(api) == 0


def test_an_unknown_package_is_not_found(api):
    response = api.get(package_path())
    assert (response.status_code, response.get_json()["error"]["code"]) == (404, "package_not_found")


def test_a_request_over_the_size_limit_is_refused(api, monkeypatch):
    from webapp.app import app

    monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", 64)
    response = api.put(package_path(), [("march.pdf", pdf() + b"x" * 128)])
    assert (response.status_code, response.get_json()["error"]["code"]) == (413, "request_too_large")


def _job_count(api) -> int:
    with closing(sqlite3.connect(api.store.storage.db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def _package_count(api) -> int:
    with closing(sqlite3.connect(api.store.storage.db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0]


def _encrypted() -> bytes:
    import fitz

    with fitz.open() as document:
        document.new_page().insert_text((72, 72), "FABRICATED")
        return document.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="fabricated", user_pw="fabricated")


def _storage_fails_on_the_second_file(api, monkeypatch):
    real, calls = api.store.create, []

    def create(*args, **kwargs):
        calls.append(args)
        if len(calls) % 2 == 0:
            raise OSError("SAMPLE-SECRET fabricated failure")
        return real(*args, **kwargs)

    monkeypatch.setattr(api.store, "create", create)


REFUSALS = {
    "no_statements": ([], None, (400, {"error": "no files uploaded"})),
    "too_many_statements": ([(f"s{n}.pdf", None) for n in range(26)], None,
                            (400, {"error": "26 files uploaded (limit 25 per batch)"})),
    "invalid_filename": ([("a-->b.pdf", None)], None, (400, {"error": "ProvenanceTokenError"})),
    "statement_too_large": ([("a.pdf", None)], lambda api, mp: mp.setattr("webapp.intake.MAX_UPLOAD_BYTES", 8),
                            (400, {"error": "file exceeds the 0 MB limit", "filename": "a.pdf"})),
    "not_a_pdf": ([("a.pdf", b"plain fabricated text")], None,
                  (400, {"error": "file is not a PDF", "filename": "a.pdf"})),
    "pdf_encrypted": ([("a.pdf", "encrypted")], None,
                      (400, {"error": "PDF is password-protected; upload a decrypted copy", "filename": "a.pdf"})),
    "pdf_unreadable": ([("a.pdf", None)], lambda api, mp: mp.setattr("webapp.intake.pdf_page_count", _unreadable),
                       (400, {"error": "PDF could not be read", "filename": "a.pdf"})),
    "too_many_pages": ([("a.pdf", None)], lambda api, mp: mp.setattr("webapp.intake.pdf_page_count", lambda b: 501),
                       (400, {"error": "PDF has 501 pages (limit 500)", "filename": "a.pdf"})),
    "storage_full": ([("a.pdf", None)], lambda api, mp: mp.setattr("webapp.app._data_volume_nearly_full",
                                                                   lambda incoming=0: True),
                     (507, {"error": "the server's storage is nearly full; no statement was accepted"})),
    "not_stored": ([("a.pdf", None), ("b.pdf", None)], _storage_fails_on_the_second_file,
                   (503, {"error": UPLOAD_NOT_STORED})),
}


def _unreadable(pdf_bytes):
    raise ValueError("fabricated damaged xref")


@pytest.mark.parametrize("code", sorted(REFUSALS))
def test_every_intake_refusal_is_the_browsers_refusal_under_its_code(api, monkeypatch, code):
    files, provoke, browser = REFUSALS[code]
    if provoke is not None:
        provoke(api, monkeypatch)

    def request_files():
        return [(name, _encrypted() if content == "encrypted" else content or pdf()) for name, content in files]

    upload = api.client.post("/upload", data={"files": [(io.BytesIO(c), n) for n, c in request_files()]},
                             content_type="multipart/form-data")
    assert (upload.status_code, upload.get_json()) == browser
    jobs_before = _job_count(api)
    response = api.put(package_path(), request_files())
    error = response.get_json()["error"]
    assert (response.status_code, error["code"]) == (browser[0], code)
    assert error["filename"] == browser[1].get("filename")
    assert "SAMPLE-SECRET" not in response.get_data(as_text=True)
    created = _job_count(api) - jobs_before
    assert created == (1 if code == "not_stored" else 0)
    assert _package_count(api) == 0


def test_a_package_row_that_cannot_be_written_leaves_every_job_failed_and_none_queued(api, monkeypatch):
    queued = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda job_id, *args: queued.append(job_id))

    def refuse(*args, **kwargs):
        raise sqlite3.OperationalError("fabricated: database is locked")

    monkeypatch.setattr(api.store.storage, "create_package", refuse)
    response = api.put(package_path(), [("march.pdf", pdf()), ("april.pdf", pdf())])
    assert (response.status_code, response.get_json()["error"]["code"]) == (503, "not_stored")
    assert queued == []
    with closing(sqlite3.connect(api.store.storage.db_path)) as conn:
        rows = conn.execute("SELECT status, error FROM jobs").fetchall()
    assert rows == [("error", UPLOAD_NOT_STORED)] * 2


def test_each_failed_statement_names_why_and_the_rest_still_yields_figures(api):
    api.outcomes.update({
        "march.pdf": analysed(_single(month=3)), "scan.pdf": refused(NO_USABLE_TEXT),
        "layout.pdf": refused(NO_PARSER_MATCHED), "analysis.pdf": refused("analysis stage failed: KeyError"),
        "crash.pdf": crashed,
    })
    path = package_path()
    api.put(path, [(name, pdf()) for name in ("march.pdf", "scan.pdf", "layout.pdf", "analysis.pdf", "crash.pdf",
                                              "restart.pdf")])
    api.store.mark_interrupted()
    body = api.get(path).get_json()
    assert body["status"] == "ready"
    assert [(document["filename"], document["status"], (document.get("failure") or {}).get("code"))
            for document in body["documents"]] == [
        ("march.pdf", "analysed", None), ("scan.pdf", "failed", "unreadable"),
        ("layout.pdf", "failed", "unsupported_statement"), ("analysis.pdf", "failed", "analysis_failed"),
        ("crash.pdf", "failed", "processing_failed"), ("restart.pdf", "failed", "interrupted"),
    ]
    assert (body["complete"], body["review"]["required"], body["review"]["decision"]) == (
        False, True, "review_required")
    assert body["figures"]["deposits_cents"] == CREDITS_CENTS
    text = json.dumps(body)
    assert "KeyError" not in text and NO_USABLE_TEXT not in text


def test_a_statement_sent_twice_is_one_document_and_a_duplicate(api):
    content = pdf()
    api.outcomes.update({"march.pdf": analysed(_single()), "march-copy.pdf": analysed(_single())})
    path = package_path()
    api.put(path, [("march.pdf", content), ("march-copy.pdf", content)])
    first, second = api.get(path).get_json()["documents"]
    assert (first["status"], second["status"]) == ("analysed", "duplicate")
    assert (second["duplicate_of"], second["reason"]) == (first["document_id"], "same_content")
    assert first["sha256"] == second["sha256"]


def test_a_statement_of_two_accounts_lists_both_and_they_add_up_to_the_package(api):
    path, body = _ready(api, {"two-accounts.pdf": _two_accounts()})
    (document,) = body["documents"]
    accounts = document["accounts"]
    assert [(account["status"], account["account_index"]) for account in accounts] == [("included", 1),
                                                                                        ("included", 2)]
    assert sum(account["deposits_cents"] for account in accounts) == body["figures"]["deposits_cents"]
    assert body["figures"]["monthly_deposits_cents"] is None


def test_a_statement_whose_main_account_is_held_is_excluded_and_counts_nothing(api):
    path, body = _ready(api, {"held.pdf": _document("held"), "april.pdf": _single(month=4)})
    held, april = body["documents"]
    assert held["accounts"] == [{"status": "excluded", "account_index": None, "reason": "main_account_unverified"}]
    assert april["accounts"][0]["status"] == "included"
    assert (body["complete"], body["review"]["required"]) == (False, True)
    assert body["figures"]["deposits_cents"] == CREDITS_CENTS


def test_a_package_that_admits_no_account_has_no_figures(api):
    path, body = _ready(api, {"held.pdf": _document("held")})
    assert body["documents"][0]["status"] == "analysed"
    assert (body["figures"], body["complete"], body["review"]["required"]) == (None, False, True)


def test_statements_in_two_currencies_publish_counts_and_no_money(api):
    canadian = _single(month=4)
    canadian["statement"]["currency"] = "CAD"
    path, body = _ready(api, {"march.pdf": _single(month=3), "april.pdf": canadian})
    figures = body["figures"]
    assert (figures["currency"], figures["currency_refusal"]) == (None, "multiple_currencies")
    money = [name for name in figures if name.endswith("_cents")]
    assert money and all(figures[name] is None for name in money)
    assert figures["months"] == 2 and isinstance(figures["lender_payment_count"], int)
    assert [document["accounts"][0]["currency"] for document in body["documents"]] == ["USD", "CAD"]
    assert body["review"]["decision"] == "review_required"


def test_a_statement_whose_zelle_reading_cannot_be_applied_is_failed_and_left_out(api):
    without_edits = zelle.case("Z1")
    without_edits.pop("zelle_counted_reading")
    path, body = _ready(api, {"march.pdf": _single(month=3), "zelle.pdf": without_edits})
    march, zelle_document = body["documents"]
    assert zelle_document["failure"]["code"] == "reading_unavailable"
    assert (march["status"], body["complete"]) == ("analysed", False)
    assert body["figures"]["deposits_cents"] == CREDITS_CENTS


def test_the_browsers_saved_settings_never_move_the_api_body(api):
    path, _body = _ready(api, {"zelle.pdf": zelle.case("Z1"), "march.pdf": _single(month=3)})
    before = api.get(path).get_data()
    job_ids = ",".join(document["document_id"] for document in json.loads(before)["documents"])
    browser_before = api.client.get(f"/package_analysis?ids={job_ids}").get_json()
    saved = api.client.post("/api/settings", json={"zelle_true_revenue": False, "nsf_carry_over": True,
                                                   "flag_alternative_positions": False})
    assert saved.status_code == 200
    assert api.client.get(f"/package_analysis?ids={job_ids}").get_json() != browser_before
    assert api.get(path).get_data() == before


def test_the_account_number_is_masked_and_never_sent_whole(api):
    path, body = _ready(api, {"march.pdf": _single()})
    assert body["documents"][0]["accounts"][0]["account_masked"] == "****1010"
    assert "000000001010" not in api.get(path).get_data(as_text=True)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_stored_figure_that_is_not_finite_is_published_as_null(api, value):
    analysis = _single()
    analysis["statement"]["beginning_balance"] = value
    path, body = _ready(api, {"march.pdf": analysis})
    assert body["documents"][0]["accounts"][0]["opening_balance_cents"] is None


def test_a_review_in_the_dashboard_changes_the_revision(api):
    path, body = _ready(api, {"march.pdf": _single()})
    document_id = body["documents"][0]["document_id"]
    assert api.get(path).get_json()["revision"] == body["revision"]
    reviewed = api.client.post(f"/analysis/{document_id}/revenue-review",
                               json={"source_location": "transaction:6", "decision": "confirm"})
    assert reviewed.status_code == 200
    assert api.get(path).get_json()["revision"] != body["revision"]


def test_a_package_that_cannot_be_published_answers_internal_error_without_its_text(api, monkeypatch):
    path, _body = _ready(api, {"march.pdf": _single()})

    def fail(*args, **kwargs):
        raise RuntimeError("SAMPLE-SECRET fabricated failure")

    monkeypatch.setattr("webapp.api.routes.package_resource", fail)
    response = api.get(path)
    assert (response.status_code, response.get_json()["error"]["code"]) == (500, "internal_error")
    assert "SAMPLE-SECRET" not in response.get_data(as_text=True)


def test_a_package_whose_statement_the_store_lost_answers_internal_error(api, monkeypatch):
    path, body = _ready(api, {"march.pdf": _single()})
    monkeypatch.setattr(api.store.storage, "package",
                        lambda package_id: {"created_at": body["created_at"], "job_ids": ["missing-job"]})
    response = api.get(path)
    assert (response.status_code, response.get_json()["error"]["code"]) == (500, "internal_error")
