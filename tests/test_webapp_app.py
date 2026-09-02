import io
from PIL import Image
from webapp.app import app, store


class _FakeThread:
    """Runs the target synchronously so job completion is deterministic in tests."""
    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


class _FakeDoc:
    model = "test-model"
    pages = ["# Hello"]

    def to_markdown(self):
        return "# Hello"


def _mock_processing(monkeypatch, page_count=2):
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: page_count)

    # O-1 delta: the worker feeds the unified ladder capability flags and a
    # preflight profile, so worker-level fakes take **kwargs.
    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, **kwargs):
        if on_page_delta:
            on_page_delta(0, "raw stream")
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_document", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {
        "statement": {"bank": "Test Bank"},
        "metrics": {"average_daily_balance": 123.45},
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
    })


# D-3 delta: every upload gets UNIQUE bytes by default. The webapp's store is
# session-scoped, so before the artifact cache existed each test could re-upload
# the same `%PDF-fake` and still re-run its own monkeypatched parse. With the
# content-hash cache in place, byte-identical re-uploads are served from the
# cache and the fakes are never called — which is the feature, not a defect.
# Tests that assert on cache behavior opt IN by passing explicit content.
def _fresh_pdf() -> bytes:
    return b"%PDF-fake-" + _uuid.uuid4().hex.encode()


def _upload_one(client, content: bytes | None = None):
    data = {"files": (io.BytesIO(content if content is not None else _fresh_pdf()), "s.pdf")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    return resp.get_json()


def test_upload_creates_and_completes_job(monkeypatch):
    _mock_processing(monkeypatch, page_count=3)
    client = app.test_client()

    upload_json = _upload_one(client)
    job = upload_json["jobs"][0]
    assert job["page_count"] == 3
    job_id = job["id"]

    status_resp = client.get(f"/status/{job_id}")
    assert status_resp.status_code == 200
    body = status_resp.get_json()
    assert body["status"] == "done"
    assert body["page_count"] == 3
    assert body["parse_model"] == "test-model"
    assert body["force_ocr"] is False

    result_resp = client.get(f"/result/{job_id}")
    assert "<h1>Hello</h1>" in result_resp.get_data(as_text=True)

    md_resp = client.get(f"/download/{job_id}/md")
    assert md_resp.get_data(as_text=True) == "# Hello"
    assert "attachment" in md_resp.headers["Content-Disposition"]


def test_markdown_source_route(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/markdown/{job_id}")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "# Hello"


def test_analysis_route_returns_report(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/analysis/{job_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["analysis"]["statement"]["bank"] == "Test Bank"
    assert body["analysis_error"] is None


def test_json_download_returns_analysis(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/download/{job_id}/json")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert '"Test Bank"' in resp.get_data(as_text=True)


def test_csv_download_returns_flat_analysis(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/download/{job_id}/csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    body = resp.get_data(as_text=True)
    assert "section,field,value" in body
    assert "statement,bank,Test Bank" in body


def test_xlsx_download_returns_workbook(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/download/{job_id}/xlsx")
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert resp.get_data()[:2] == b"PK"


def test_markdown_before_done_returns_404():
    client = app.test_client()
    job = store.create("pending.pdf")
    resp = client.get(f"/markdown/{job.id}")
    assert resp.status_code == 404


def test_live_route_returns_streamed_text(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/live/{job_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert "raw stream" in body["live_text"]


def test_live_unknown_job_returns_404():
    client = app.test_client()
    assert app.test_client().get("/live/nope").status_code == 404


def test_render_route_returns_live_fragment(monkeypatch):
    _mock_processing(monkeypatch)
    monkeypatch.setattr("webapp.app.rasterize_page",
                        lambda pdf_bytes, n, dpi=200: Image.new("RGB", (8, 8)))
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/render/{job_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    # A body fragment (no full-page wrapper), rendered from the live buffer.
    assert "raw stream" in body["fragment"]
    assert "<!DOCTYPE html>" not in body["fragment"]


def test_render_unknown_job_returns_404():
    assert app.test_client().get("/render/nope").status_code == 404


def test_rendered_skeleton_has_live_root():
    resp = app.test_client().get("/rendered_skeleton")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="live-root"' in html
    assert "<style>" in html


def test_page_route_returns_png(monkeypatch):
    _mock_processing(monkeypatch, page_count=2)
    monkeypatch.setattr("webapp.app.rasterize_page",
                        lambda pdf_bytes, n, dpi=100: Image.new("RGB", (4, 4), (255, 255, 255)))
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]

    ok = client.get(f"/page/{job_id}/0")
    assert ok.status_code == 200
    assert ok.mimetype == "image/png"
    assert ok.get_data()[:8] == b"\x89PNG\r\n\x1a\n"

    oob = client.get(f"/page/{job_id}/5")  # page_count is 2
    assert oob.status_code == 404


def test_upload_with_no_files_returns_400():
    client = app.test_client()
    resp = client.post("/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_checked_upload_refuses_a_filename_with_a_line_break():
    """MINOR-8 (PHASE2_P20SEAM_REVIEW.md): a multipart filename carrying a
    raw CR/LF is refused at `_checked_upload`, with a class-name-only
    message — never the raw filename echoed back (unlike every other
    `_checked_upload` error branch, which safely echoes an ordinary
    filename). Tested at the function level, not through the werkzeug test
    client's multipart encoder: a raw `\\r\\n` inside a `Content-Disposition`
    filename corrupts the multipart framing itself (the same two bytes are
    the section delimiter), so the HTTP transport cannot reliably carry this
    shape at all — `_checked_upload` is exercised directly so the refusal is
    proven regardless of what any given multipart parser does with it."""
    from webapp.app import _checked_upload

    for hostile in ("evil\r\nname.pdf", "evil\nname.pdf", "evil\rname.pdf"):
        page_count, profile, error = _checked_upload(hostile, b"%PDF-fake")
        assert page_count is None
        assert profile is None
        assert error == {"error": "ProvenanceTokenError"}
        assert "filename" not in error


def test_checked_upload_refuses_a_filename_with_a_comment_close():
    """NEW-4 (re-review, closure 1cc759e): `StatementMarkdown.__post_init__`
    also refuses `-->` in `source_file` (the writer-side belt), but a raw
    `-->` does not corrupt multipart framing the way CR/LF does, so a
    filename like `a-->b.pdf` reached the view and then died as the same
    opaque per-job failure MINOR-8 fixed for CR/LF. Refused at
    `_checked_upload` too now, with the identical class-name-only shape."""
    from webapp.app import _checked_upload

    page_count, profile, error = _checked_upload("evil-->name.pdf", b"%PDF-fake")
    assert page_count is None
    assert profile is None
    assert error == {"error": "ProvenanceTokenError"}
    assert "filename" not in error


def test_checked_upload_still_echoes_an_ordinary_filename():
    """The refusal above is scoped to the line-break shape — every other
    `_checked_upload` error keeps echoing the (safe) filename it always did."""
    from webapp.app import _checked_upload

    page_count, profile, error = _checked_upload("not-a-pdf.pdf", b"not a pdf")
    assert error == {"error": "file is not a PDF", "filename": "not-a-pdf.pdf"}


def test_upload_can_force_visual_ocr(monkeypatch):
    seen = {}
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)

    def fake_parse(pdf_bytes, source_file="", force_ocr=False, **kwargs):
        seen["force_ocr"] = force_ocr
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_document", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})

    client = app.test_client()
    resp = client.post(
        "/upload",
        data={"force_ocr": "1", "files": (io.BytesIO(_fresh_pdf()), "s.pdf")},
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert body["jobs"][0]["force_ocr"] is True
    assert seen["force_ocr"] is True


def test_upload_can_request_deterministic_parse_mode(monkeypatch):
    seen = {}
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)
    # O-1 delta: the native rung is patched at its one home in ocr.pipeline
    # (the worker no longer owns a private ladder to patch).
    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda pdf_bytes, source_file="": _FakeDoc())

    def fake_analyze(markdown, parse_mode="auto", **kwargs):
        seen["parse_mode"] = parse_mode
        return object()

    monkeypatch.setattr("webapp.worker.analyze_document", fake_analyze)
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})

    client = app.test_client()
    resp = client.post(
        "/upload",
        data={"parse_mode": "deterministic", "files": (io.BytesIO(_fresh_pdf()), "s.pdf")},
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    job_id = body["jobs"][0]["id"]
    assert body["jobs"][0]["parse_mode"] == "deterministic"
    assert seen["parse_mode"] == "deterministic"

    status = client.get(f"/status/{job_id}").get_json()
    assert status["parse_mode"] == "deterministic"


def test_upload_rejects_invalid_parse_mode():
    client = app.test_client()
    resp = client.post(
        "/upload",
        data={"parse_mode": "llm-only", "files": (io.BytesIO(b"%PDF-fake"), "s.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_package_analysis_aggregates_completed_jobs():
    client = app.test_client()
    job1 = store.create("jan.pdf")
    job2 = store.create("feb.pdf")
    store.set_result(job1.id, "# Jan", "<h1>Jan</h1>", analysis={
        "statement": {
            "bank": "TD Bank",
            # A package aggregates only across a proven single currency
            # (CURRENCY DOCTRINE §F); a real payload always declares one.
            "currency": "USD",
            "period_start": "2054-01-01",
            "period_end": "2054-01-31",
            "beginning_balance": 500,
            "ending_balance": 900,
        },
        "metrics": {
            "effective_total_deposits": 10000,
            "effective_total_withdrawals": 7000,
            "cash_flow": 3000,
            "effective_nsf_count": 1,
            "average_daily_balance": 100,
            "adb_ok": True,
            "calendar_day_count": 31,
            "min_balance": 250,
            "max_balance": 1200,
            "lender_debits": 1000,
            "monthly_lender_debits": 1000,
            "withholding_rate": 10,
        },
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {"known_funders": [{"funder": "ONDECK", "total_debited": 1000}]},
    })
    store.set_result(job2.id, "# Feb", "<h1>Feb</h1>", analysis={
        "statement": {
            "bank": "TD Bank",
            "currency": "USD",
            "period_start": "2054-02-01",
            "period_end": "2054-02-28",
            "beginning_balance": 900,
            "ending_balance": 1100,
        },
        "metrics": {
            "effective_total_deposits": 12000,
            "effective_total_withdrawals": 8000,
            "cash_flow": 4000,
            "effective_nsf_count": 0,
            "average_daily_balance": 200,
            "adb_ok": True,
            "calendar_day_count": 28,
            "min_balance": 700,
            "max_balance": 1500,
            "lender_debits": 500,
            "monthly_lender_debits": 500,
            "withholding_rate": 4.17,
        },
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {"known_funders": [{"funder": "ONDECK", "total_debited": 500}]},
    })

    resp = client.get(f"/package_analysis?ids={job1.id},{job2.id}")
    assert resp.status_code == 200
    body = resp.get_json()
    totals = body["totals"]
    assert totals["documents"] == 2
    assert totals["completed"] == 2
    assert totals["approved"] == 2
    assert totals["total_credits"] == 22000
    assert totals["total_debits"] == 15000
    assert totals["cash_flow"] == 7000
    assert totals["avg_monthly_credits"] == 11000
    assert totals["average_daily_balance"] == 147.46
    assert [doc["average_daily_balance"] for doc in body["documents"]] == [100, 200]
    assert [doc["beginning_balance"] for doc in body["documents"]] == [500, 900]
    assert [doc["ending_balance"] for doc in body["documents"]] == [900, 1100]
    assert [doc["min_balance"] for doc in body["documents"]] == [250, 700]
    assert [doc["max_balance"] for doc in body["documents"]] == [1200, 1500]
    assert all(doc["daily_balance_extrema_validated"] for doc in body["documents"])
    assert totals["package_withholding_rate"] == 6.82
    assert totals["decision"] == "approved"
    assert body["funders"] == [{"funder": "ONDECK", "documents": 2, "total_debited": 1500.0}]

    json_resp = client.get(f"/package_download/json?ids={job1.id},{job2.id}")
    assert json_resp.status_code == 200
    assert json_resp.mimetype == "application/json"
    assert '"package_withholding_rate": 6.82' in json_resp.get_data(as_text=True)

    csv_resp = client.get(f"/package_download/csv?ids={job1.id},{job2.id}")
    assert csv_resp.status_code == 200
    assert csv_resp.mimetype == "text/csv"
    assert "totals,total_credits,22000.0" in csv_resp.get_data(as_text=True)
    assert "document_1,min_balance,250" in csv_resp.get_data(as_text=True)
    assert "document_2,max_balance,1500" in csv_resp.get_data(as_text=True)

    xlsx_resp = client.get(f"/package_download/xlsx?ids={job1.id},{job2.id}")
    assert xlsx_resp.status_code == 200
    assert xlsx_resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert xlsx_resp.get_data()[:2] == b"PK"


def test_package_adb_ignores_rejected_or_unvalidated_cached_values():
    rejected = store.create("rejected-adb.pdf")
    missing_status = store.create("legacy-adb.pdf")
    missing_days = store.create("missing-adb-days.pdf")
    for job, adb_ok, days in (
        (rejected, False, 31),
        (missing_status, None, 31),
        (missing_days, True, None),
    ):
        metrics = {
            "average_daily_balance": 999999.0,
        }
        if days is not None:
            metrics["calendar_day_count"] = days
        if adb_ok is not None:
            metrics["adb_ok"] = adb_ok
        store.set_result(job.id, "# Statement", "<h1>Statement</h1>", analysis={
            "statement": {
                "bank": "Audit Bank",
                "period_start": "2054-01-01",
                "period_end": "2054-01-31",
                "transactions": [],
            },
            "metrics": metrics,
            "quality": {"level": "needs_review", "corporate_use": "manual_review_required"},
            "integrity": {"risk_level": "review"},
            "detection": {"known_funders": []},
        })

    body = app.test_client().get(
        f"/package_analysis?ids={rejected.id},{missing_status.id},{missing_days.id}"
    ).get_json()
    assert body["totals"]["average_daily_balance"] is None
    assert [doc["average_daily_balance"] for doc in body["documents"]] == [None, None, None]
    assert [doc["adb_validated"] for doc in body["documents"]] == [False, False, False]
    assert [doc["min_balance"] for doc in body["documents"]] == [None, None, None]
    assert [doc["max_balance"] for doc in body["documents"]] == [None, None, None]
    assert [doc["daily_balance_extrema_validated"] for doc in body["documents"]] == [
        False,
        False,
        False,
    ]


def test_package_withholding_is_zero_with_deposits_and_no_lender_debits():
    client = app.test_client()
    job = store.create("no-lenders.pdf")
    store.set_result(job.id, "# No lenders", "<h1>No lenders</h1>", analysis={
        "statement": {"bank": "Audit Bank", "currency": "USD", "transactions": []},
        "metrics": {
            "effective_total_deposits": 5000,
            "effective_total_withdrawals": 1000,
            "withholding_numerator": 0,
            "withholding_denominator": 5000,
            "lender_debits": 0,
        },
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {"known_funders": []},
    })

    totals = client.get(f"/package_analysis?ids={job.id}").get_json()["totals"]
    assert totals["withholding_numerator"] == 0
    assert totals["withholding_denominator"] == 5000
    assert totals["package_withholding_rate"] == 0.0
    assert totals["withholding_review_required"] is False


def test_status_unknown_job_returns_404():
    client = app.test_client()
    resp = client.get("/status/does-not-exist")
    assert resp.status_code == 404


def test_download_invalid_format_returns_400(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]
    resp = client.get(f"/download/{job_id}/txt")
    assert resp.status_code == 400


def test_download_before_done_returns_404():
    client = app.test_client()
    job = store.create("pending.pdf")  # no thread started; status stays "queued"
    resp = client.get(f"/download/{job.id}/md")
    assert resp.status_code == 404


def test_index_page_renders():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Unlimited" in resp.data


# ---------------------------------------------------------------------------
# D-1 additions: durable persistence wiring at the endpoint level.
# (Everything above is unchanged from the in-memory era.)
# ---------------------------------------------------------------------------

import hashlib
import json


def test_upload_records_content_hash_and_upload_audit(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    content = _fresh_pdf()
    job_id = _upload_one(client, content)["jobs"][0]["id"]

    job = store.get(job_id)
    expected_sha = hashlib.sha256(content).hexdigest().upper()
    assert job.content_sha256 == expected_sha

    uploads = store.storage.audit_events("upload", job_id=job_id)
    assert len(uploads) == 1


def test_completed_job_releases_pdf_bytes_and_page_serves_from_disk(monkeypatch):
    from PIL import Image as _Image

    _mock_processing(monkeypatch, page_count=2)
    monkeypatch.setattr("webapp.app.rasterize_page",
                        lambda pdf_bytes, n, dpi=100: _Image.new("RGB", (4, 4)))
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]

    # RAM release on completion — the acceptance criterion itself.
    assert store.get(job_id).status == "done"
    assert store.get(job_id).pdf_bytes is None

    # /page still works, now disk-backed via the content-hash store.
    resp = client.get(f"/page/{job_id}/0")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_durable_package_id_reproduces_the_comma_ids_payload(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job1_id = _upload_one(client)["jobs"][0]["id"]
    job2_id = _upload_one(client)["jobs"][0]["id"]

    minted = client.post("/package", json={"ids": [job1_id, job2_id]})
    assert minted.status_code == 200
    package_id = minted.get_json()["package_id"]

    by_ids = client.get(f"/package_analysis?ids={job1_id},{job2_id}").get_json()
    by_package = client.get(f"/package_analysis?package_id={package_id}").get_json()
    assert by_package == by_ids
    # The durable id is also accepted in the ids slot.
    by_ids_slot = client.get(f"/package_analysis?ids={package_id}").get_json()
    assert by_ids_slot == by_ids


def test_package_mint_rejects_unknown_job_ids():
    resp = app.test_client().post("/package", json={"ids": ["nope"]})
    assert resp.status_code == 404
    assert resp.get_json()["missing"] == ["nope"]


def test_unknown_package_id_returns_404():
    resp = app.test_client().get("/package_analysis?package_id=not-a-package")
    assert resp.status_code == 404


def test_revenue_review_endpoint_writes_a_durable_decision_row():
    job = store.create("review-durable.pdf")
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis={
        "statement": {
            "bank": "Test Bank",
            "transactions": [
                {
                    "date": "2054-01-04",
                    "description": "ACH DEPOSIT",
                    "amount": 1000.0,
                    "classification": {
                        "source_location": "page-1-row-1",
                        "revenue_classification": "unverified_deposit",
                        "revenue_initial_classification": "unverified_deposit",
                    },
                }
            ],
        },
        "metrics": {"effective_total_deposits": 1000.0},
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {"known_funders": []},
    })

    resp = app.test_client().post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "page-1-row-1", "decision": "confirm",
              "actor": "underwriter-jane"},
    )
    assert resp.status_code == 200

    history = store.review_history(job.id)
    assert len(history) == 1
    assert history[0]["decision"] == "confirm"
    assert history[0]["actor"] == "underwriter-jane"
    assert history[0]["decided_at"]
    prior = json.loads(history[0]["prior_state"])
    assert prior["revenue_classification"] == "unverified_deposit"


def test_download_writes_an_export_audit_row(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    job_id = _upload_one(client)["jobs"][0]["id"]

    assert client.get(f"/download/{job_id}/json").status_code == 200
    exports = store.storage.audit_events("export", job_id=job_id)
    assert len(exports) == 1
    assert json.loads(exports[0]["detail"])["format"] == "json"


# ---------------------------------------------------------------------------
# O-1 additions: preflight surfacing at the upload boundary.
# ---------------------------------------------------------------------------

import uuid as _uuid


def _upload_bytes(client, data_bytes, name="s.pdf"):
    resp = client.post(
        "/upload",
        data={"files": (io.BytesIO(data_bytes), name)},
        content_type="multipart/form-data",
    )
    return resp.status_code, resp.get_json()


def test_duplicate_upload_of_identical_bytes_is_flagged(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    unique = b"%PDF-" + _uuid.uuid4().hex.encode()

    _, first = _upload_bytes(client, unique, "jan.pdf")
    first_job = first["jobs"][0]
    assert first_job["duplicate_of"] is None
    assert first_job["content_sha256"] == hashlib.sha256(unique).hexdigest().upper()

    _, again = _upload_bytes(client, unique, "jan-copy.pdf")
    again_job = again["jobs"][0]
    assert again_job["duplicate_of"] == first_job["id"]
    assert again_job["content_sha256"] == first_job["content_sha256"]

    # The durable indication also serves from /status after upload.
    status = client.get(f"/status/{again_job['id']}").get_json()
    assert status["content_sha256"] == first_job["content_sha256"]
    assert status["duplicate_of"] == first_job["id"]
    assert client.get(f"/status/{first_job['id']}").get_json()["duplicate_of"] is None


def test_distinct_bytes_are_not_flagged_as_duplicates(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    _, one = _upload_bytes(client, b"%PDF-" + _uuid.uuid4().hex.encode(), "a.pdf")
    _, two = _upload_bytes(client, b"%PDF-" + _uuid.uuid4().hex.encode(), "b.pdf")
    assert one["jobs"][0]["duplicate_of"] is None
    assert two["jobs"][0]["duplicate_of"] is None
    assert one["jobs"][0]["content_sha256"] != two["jobs"][0]["content_sha256"]


def test_encrypted_pdf_is_rejected_with_the_d2a_error_shape():
    # Encrypted fixture generated with PyMuPDF (pypdf is not installed here —
    # the spec's sanctioned fallback). Rejection happens at preflight, before
    # any page counting, so no processing mocks are needed.
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret")
    encrypted = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw"
    )

    status_code, body = _upload_bytes(app.test_client(), encrypted, "locked.pdf")
    assert status_code == 400
    assert body["filename"] == "locked.pdf"
    assert "password" in body["error"]


# ---------------------------------------------------------------------------
# D-3 additions: duplicate content surfaced in the package payload.
# ---------------------------------------------------------------------------


def _completed(filename, pdf_bytes=None, deposits=1000.0):
    job = store.create(filename, pdf_bytes=pdf_bytes)
    store.set_result(job.id, f"# {filename}", f"<h1>{filename}</h1>", analysis={
        "statement": {"bank": "Test Bank", "transactions": []},
        "metrics": {"effective_total_deposits": deposits},
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {"known_funders": []},
    })
    return job


def test_package_flags_documents_that_repeat_the_same_content():
    content = b"%PDF-" + _uuid.uuid4().hex.encode()
    first = _completed("jan.pdf", content)
    duplicate = _completed("jan-again.pdf", content)  # same bytes, new name
    other = _completed("feb.pdf", b"%PDF-" + _uuid.uuid4().hex.encode())

    body = app.test_client().get(
        f"/package_analysis?ids={first.id},{duplicate.id},{other.id}"
    ).get_json()

    totals = body["totals"]
    assert totals["documents"] == 3
    assert totals["duplicate_documents"] == 1
    assert totals["distinct_documents"] == 2
    assert totals["has_duplicate_documents"] is True

    rows = {doc["id"]: doc for doc in body["documents"]}
    assert rows[first.id]["is_duplicate"] is False
    assert rows[first.id]["duplicate_of"] is None
    # The re-listed member points at the earlier one it repeats.
    assert rows[duplicate.id]["is_duplicate"] is True
    assert rows[duplicate.id]["duplicate_of"] == first.id
    assert rows[other.id]["is_duplicate"] is False
    assert rows[first.id]["content_sha256"] == rows[duplicate.id]["content_sha256"]

    assert body["duplicates"] == [{
        "content_sha256": first.content_sha256,
        "job_ids": [first.id, duplicate.id],
        "filenames": ["jan.pdf", "jan-again.pdf"],
        "count": 2,
    }]


def test_package_without_repeated_content_reports_no_duplicates():
    one = _completed("a.pdf", b"%PDF-" + _uuid.uuid4().hex.encode())
    two = _completed("b.pdf", b"%PDF-" + _uuid.uuid4().hex.encode())

    body = app.test_client().get(f"/package_analysis?ids={one.id},{two.id}").get_json()
    assert body["duplicates"] == []
    assert body["totals"]["duplicate_documents"] == 0
    assert body["totals"]["has_duplicate_documents"] is False
    assert all(doc["is_duplicate"] is False for doc in body["documents"])


def test_jobs_without_content_bytes_are_never_guessed_to_be_duplicates():
    # Two jobs with no PDF bytes have no content hash at all; identical
    # nothing is not identical content.
    one = _completed("no-bytes-1.pdf")
    two = _completed("no-bytes-2.pdf")

    body = app.test_client().get(f"/package_analysis?ids={one.id},{two.id}").get_json()
    assert body["duplicates"] == []
    assert body["totals"]["has_duplicate_documents"] is False
    assert [doc["content_sha256"] for doc in body["documents"]] == [None, None]


def test_duplicate_flag_reaches_the_package_exports():
    content = b"%PDF-" + _uuid.uuid4().hex.encode()
    first = _completed("mar.pdf", content)
    duplicate = _completed("mar-copy.pdf", content)

    csv_body = app.test_client().get(
        f"/package_download/csv?ids={first.id},{duplicate.id}"
    ).get_data(as_text=True)
    assert "totals,duplicate_documents,1" in csv_body
    assert "duplicate_1,count,2" in csv_body
    assert "document_2,is_duplicate,True" in csv_body


def test_upload_persists_the_preflight_profile_with_the_document(monkeypatch):
    _mock_processing(monkeypatch)
    client = app.test_client()
    content = _fresh_pdf()
    job_id = _upload_one(client, content)["jobs"][0]["id"]

    profile = store.storage.document_profile(job_id)
    assert profile is not None
    assert profile["content_sha256"] == hashlib.sha256(content).hexdigest().upper()
    assert profile["classification"] in {"digital", "scanned", "mixed", "unknown"}
    # Advisory fields ride along in storage; nothing in production reads them.
    assert "likely_account_count" in profile
    assert "layout_signals" in profile
