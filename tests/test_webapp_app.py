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
    monkeypatch.delenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", raising=False)

    def fake_pair(job_id, store, cache, pdf_bytes, filename, profile, **kwargs):
        seen["pair"] = True
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker._read_visual_pair", fake_pair)
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *args, **kwargs: pytest.fail("legacy reader ran"))
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
    assert seen["pair"] is True


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
    # 5.6 (true revenue spec §9.2): a member with no ledger rows and no verified key has no established verified
    # revenue (the `true_revenue` fallback is gone), so the package's verified total is N/A and it needs review.
    assert totals["verified_revenue_total"] is None
    assert totals["revenue_unestablished_documents"] == sorted([job1.id, job2.id])
    assert totals["decision"] == "review_required"
    # Owner ruling 2026-10-02 (the underwriter's Q5), R2-OW13: every funder rollup sums its returned funder payments
    # (none here, and none in members stored before the ruling).
    assert body["funders"] == [{"funder": "ONDECK", "documents": 2, "total_debited": 1500.0,
                                "returned_payment_count": 0, "returned_payment_total": 0.0}]

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


# ---------------------------------------------------------------------------
# Audit B11 (I06): a repeated statement is left out of every figure, listed, and sends the package to review.
# Fabricated statements (tests/test_webapp_true_revenue.py `_payload`: 1,000 True, 700 Verified, March 2031).
# ---------------------------------------------------------------------------


def _analysed(filename, analysis, pdf_bytes=None):
    job = store.create(filename, pdf_bytes=pdf_bytes)
    store.set_result(job.id, f"# {filename}", f"<h1>{filename}</h1>", analysis=analysis)
    return job


def _package_json(*job_ids):
    return app.test_client().get(f"/package_analysis?ids={','.join(job_ids)}").get_json()


def _figures(totals):
    keys = ("true_revenue_total", "verified_revenue_total", "counted_flagged_total", "excluded_pending_review_total",
            "non_revenue_total", "total_credits", "months", "avg_monthly_true_revenue")
    return {key: totals[key] for key in keys}


#: Fabricated rows whose statement is approved alone (no held credit), so a repeat is what sends it to review.
_APPROVED_ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 7000.0), (3, "MOBILE DEPOSIT", 3000.0)]


def test_the_same_pdf_twice_counts_once_and_needs_review():
    from tests.test_webapp_true_revenue import _payload

    content = b"%PDF-" + _uuid.uuid4().hex.encode()
    first = _analysed("mar.pdf", _payload(_APPROVED_ROWS), content)
    copy = _analysed("mar-again.pdf", _payload(_APPROVED_ROWS), content)
    single = _package_json(first.id)["totals"]
    assert single["decision"] == "approved"
    body = _package_json(first.id, copy.id)
    totals = body["totals"]
    assert _figures(totals) == _figures(single)
    assert (totals["true_revenue_total"], totals["months"], totals["avg_monthly_true_revenue"]) == (
        10000.0, 1, 10000.0)
    assert (totals["documents"], totals["duplicate_documents"], totals["distinct_documents"]) == (2, 1, 1)
    assert totals["has_duplicate_documents"] is True and totals["completed"] == 1
    assert totals["decision"] == "review_required"
    rows = {doc["id"]: doc for doc in body["documents"]}
    assert rows[first.id]["is_duplicate"] is False
    assert (rows[copy.id]["is_duplicate"], rows[copy.id]["duplicate_of"], rows[copy.id]["duplicate_reason"]) == (
        True, first.id, "same_content")
    # The left-out repeat carries no figure, and is never a month of the Monthly Statements.
    assert "true_revenue_total" not in rows[copy.id] and "credits" not in rows[copy.id]
    assert [doc["id"] for doc in body["monthly"]] == [first.id]


def test_a_re_download_with_other_bytes_is_the_same_statement():
    from tests.test_webapp_true_revenue import _payload

    first = _analysed("mar.pdf", _payload(), b"%PDF-" + _uuid.uuid4().hex.encode())
    again = _analysed("mar-download.pdf", _payload(), b"%PDF-" + _uuid.uuid4().hex.encode())
    assert first.content_sha256 != again.content_sha256
    body = _package_json(first.id, again.id)
    totals = body["totals"]
    assert (totals["true_revenue_total"], totals["verified_revenue_total"], totals["months"]) == (1000.0, 700.0, 1)
    assert totals["duplicate_documents"] == 1 and totals["decision"] == "review_required"
    repeat = next(doc for doc in body["documents"] if doc["is_duplicate"])
    assert (repeat["id"], repeat["duplicate_of"], repeat["duplicate_reason"]) == (again.id, first.id, "same_statement")
    assert body["duplicates"][0]["job_ids"] == [first.id, again.id]


def test_a_statement_printing_the_same_key_is_the_same_statement_whatever_its_reading():
    """The statement key (bank, account's last four, period, opening and closing balance) matches two readings of one
    statement whose content differs, an analyst's review on one of them for instance."""
    from tests.test_webapp_true_revenue import _payload

    reviewed = _payload()
    reviewed["statement"]["transactions"][1]["classification"]["revenue_review_status"] = "confirmed"
    first = _analysed("mar.pdf", _payload(), b"%PDF-" + _uuid.uuid4().hex.encode())
    other = _analysed("mar-reviewed.pdf", reviewed, b"%PDF-" + _uuid.uuid4().hex.encode())
    totals = _package_json(first.id, other.id)["totals"]
    assert totals["duplicate_documents"] == 1 and totals["true_revenue_total"] == 1000.0


def test_a_job_listed_twice_is_one_job():
    from tests.test_webapp_true_revenue import _payload

    job = _analysed("mar.pdf", _payload(), b"%PDF-" + _uuid.uuid4().hex.encode())
    single = _package_json(job.id)
    twice = _package_json(job.id, job.id)
    assert _figures(twice["totals"]) == _figures(single["totals"])
    assert [doc["id"] for doc in twice["documents"]] == [job.id]
    assert twice["totals"]["documents"] == 1 and twice["totals"]["has_duplicate_documents"] is False
    # A durable package never lists one job twice, and a package id beside one of its own members adds nothing.
    minted = app.test_client().post("/package", json={"ids": [job.id, job.id]}).get_json()
    assert minted["ids"] == [job.id]
    beside = app.test_client().get(f"/package_analysis?ids={minted['package_id']},{job.id}").get_json()
    assert _figures(beside["totals"]) == _figures(single["totals"])


def test_the_package_code_drops_a_repeated_job_even_when_called_directly():
    from tests.test_webapp_true_revenue import _payload
    from webapp.app import _package_analysis
    from webapp.jobs import Job

    job = Job(id="mar", filename="mar.pdf", status="done", analysis=_payload(), content_sha256="mar")
    package = _package_analysis([job, job])
    assert package["totals"]["true_revenue_total"] == 1000.0 and package["totals"]["months"] == 1
    assert package["totals"]["duplicate_documents"] == 1 and package["totals"]["decision"] == "review_required"
    assert [doc["id"] for doc in package["documents"]] == ["mar"]
    assert package["duplicates"][0]["job_ids"] == ["mar", "mar"]


def test_the_sibling_accounts_of_one_document_are_never_duplicates():
    """Every account of a multi-account document carries the job's hash; none is left out on it."""
    from tests.test_webapp_studio_views import _document
    from webapp.app import _package_analysis
    from webapp.jobs import Job

    package = _package_analysis([Job(id="doc", filename="doc.pdf", status="done", analysis=_document("published"),
                                     content_sha256="doc")])
    assert [doc["id"] for doc in package["documents"]] == ["doc#account_1", "doc#account_2"]
    assert package["totals"]["has_duplicate_documents"] is False
    assert all(doc["is_duplicate"] is False for doc in package["documents"])
    assert package["totals"]["months"] == 1


def test_a_document_repeating_one_statement_keeps_its_other_account():
    """A checking statement uploaded alone, then the document that prints it beside savings: the document's checking
    account is left out as a duplicate, its savings account counts."""
    from tests.test_webapp_studio_views import CHECKING_ROWS, _document, _report
    from analysis.serialization import document_report_to_dict
    from webapp.app import _package_analysis
    from webapp.jobs import Job

    checking = document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, CHECKING_ROWS))
    jobs = [Job(id="chk", filename="chk.pdf", status="done", analysis=checking, content_sha256="chk"),
            Job(id="doc", filename="doc.pdf", status="done", analysis=_document("published"), content_sha256="doc")]
    package = _package_analysis(jobs)
    assert [doc["id"] for doc in package["documents"]] == ["chk", "doc#account_2"]
    excluded = package["excluded_accounts"]
    assert [(entry["job_id"], entry["account_index"], entry["reason"], entry["duplicate_of"]) for entry in excluded] == [
        ("doc", 1, "duplicate_statement", "chk")]
    assert package["totals"]["duplicate_accounts"] == 1 and package["totals"]["decision"] == "review_required"
    alone = _package_analysis([Job(id="doc", filename="doc.pdf", status="done", analysis=_document("published"),
                                   content_sha256="doc")])
    assert package["totals"]["total_credits"] == alone["totals"]["total_credits"]


# ---------------------------------------------------------------------------
# Audit round 2, R2-B14 (R16): of the copies of one repeated statement the package keeps the copy with a completed
# analysis, then the one analysed under the current rules, then the one carrying the analyst's review decisions, and
# only then the one listed first. Fabricated `_payload` statements (1,000 True, 700 Verified, 900 held, March 2031).
# ---------------------------------------------------------------------------

import copy as _copy_module  # noqa: E402
import zipfile  # noqa: E402

import pytest  # noqa: E402


def _listed(job_id, analysis=None, *, status="done", content="h1", filename=None):
    """A job as a package lists it: `status` "error" has no analysis and an error, like a failed upload."""
    from webapp.jobs import Job

    return Job(id=job_id, filename=filename or f"{job_id}.pdf", status=status, analysis=analysis,
               content_sha256=content, error="fabricated failure" if status == "error" else None)


def _decided(payload):
    """The same statement after the analyst confirmed its held 900 credit (transaction 3) as revenue: True 1,900."""
    from analysis.revenue import apply_serialized_revenue_review

    return apply_serialized_revenue_review(_copy_module.deepcopy(payload), source_location="transaction:3",
                                           decision="confirm")


def _r16(package):
    totals = package["totals"]
    return {key: totals[key] for key in ("true_revenue_total", "verified_revenue_total", "excluded_pending_review_total",
                                          "completed", "failed", "months", "duplicate_documents", "decision")}


def _left_out(package):
    """The left-out jobs' rows: (id, the job kept in its place, why it is a repeat, why that copy was kept)."""
    return [(doc["id"], doc["duplicate_of"], doc["duplicate_reason"], doc.get("duplicate_kept_because"))
            for doc in package["documents"] if doc["is_duplicate"]]


_ONE_MARCH = {"true_revenue_total": 1000.0, "verified_revenue_total": 700.0, "excluded_pending_review_total": 900.0,
              "completed": 1, "failed": 0, "months": 1, "duplicate_documents": 1, "decision": "review_required"}


def test_a_failed_copy_listed_first_leaves_the_completed_copy_in_the_package():
    """B11's regression: a failed upload of the same bytes listed first claimed the hash, so the completed copy was left
    out (True 0, completed 0). The completed copy is kept, and the failed one is left out and never counted failed."""
    from tests.test_webapp_true_revenue import _payload
    from webapp.app import _package_analysis

    jobs = [_listed("f", status="error"), _listed("a", _payload())]
    package = _package_analysis(jobs)
    assert _r16(package) == _ONE_MARCH
    assert [doc["id"] for doc in package["documents"]] == ["a", "f"]
    assert _left_out(package) == [("f", "a", "same_content", "has_analysis")]
    # A group lists the kept job first, its hash the group's.
    assert package["duplicates"] == [{"content_sha256": "h1", "job_ids": ["a", "f"], "filenames": ["a.pdf", "f.pdf"],
                                      "count": 2}]
    reverse = _package_analysis(list(reversed(jobs)))
    assert _r16(reverse) == _ONE_MARCH and _left_out(reverse) == [("f", "a", "same_content", "has_analysis")]


def test_a_failed_copy_listed_first_through_the_package_route():
    from tests.test_webapp_true_revenue import _payload

    content = b"%PDF-" + _uuid.uuid4().hex.encode()
    failed = store.create("mar.pdf", pdf_bytes=content)
    store.set_error(failed.id, "fabricated failure")
    done = _analysed("mar-again.pdf", _payload(), content)
    for ids in ((failed.id, done.id), (done.id, failed.id)):
        body = _package_json(*ids)
        assert _r16(body) == _ONE_MARCH
        assert _left_out(body) == [(failed.id, done.id, "same_content", "has_analysis")]
    minted = app.test_client().post("/package", json={"ids": [failed.id, done.id]}).get_json()
    durable = app.test_client().get(f"/package_analysis?package_id={minted['package_id']}").get_json()
    assert _r16(durable) == _ONE_MARCH


@pytest.mark.parametrize("status", ["queued", "processing", "interrupted"])
def test_a_copy_still_in_flight_listed_first_leaves_the_completed_copy_in_the_package(status):
    from tests.test_webapp_true_revenue import _payload

    content = b"%PDF-" + _uuid.uuid4().hex.encode()
    pending = store.create("mar.pdf", pdf_bytes=content)
    if status != "queued":
        store.set_status(pending.id, status)
    done = _analysed("mar-again.pdf", _payload(), content)
    body = _package_json(pending.id, done.id)
    assert _r16(body) == _ONE_MARCH
    assert _left_out(body) == [(pending.id, done.id, "same_content", "has_analysis")]


@pytest.mark.parametrize("same_bytes", [True, False])
def test_a_copy_analysed_under_older_rules_listed_first_never_blanks_the_package(same_bytes):
    """A pre-5.6 copy listed first made the whole package's True N/A; the copy analysed under the current rules is kept,
    by its bytes (`same_content`) or by its statement key (`same_statement`)."""
    from tests.test_webapp_true_revenue import _payload, _untiered
    from webapp.app import _package_analysis

    reason = "same_content" if same_bytes else "same_statement"
    jobs = [_listed("old", _untiered(_payload())), _listed("new", _payload(), content="h1" if same_bytes else "h2")]
    for listed in (jobs, list(reversed(jobs))):
        package = _package_analysis(listed)
        assert _r16(package) == _ONE_MARCH
        assert package["totals"]["revenue_unestablished_documents"] == []
        assert package["analysis_rules_outdated"] is False
        assert _left_out(package) == [("old", "new", reason, "current_rules")]


def test_the_copy_carrying_the_review_decisions_is_the_one_kept():
    """Decisions recorded on the later copy were lost (True 1,000, held 900); the decided copy is kept."""
    from tests.test_webapp_true_revenue import _payload
    from webapp.app import _package_analysis

    jobs = [_listed("plain", _payload()), _listed("decided", _decided(_payload()))]
    for listed in (jobs, list(reversed(jobs))):
        package = _package_analysis(listed)
        assert _r16(package) == {**_ONE_MARCH, "true_revenue_total": 1900.0, "verified_revenue_total": 1600.0,
                                 "excluded_pending_review_total": 0.0}
        assert _left_out(package) == [("plain", "decided", "same_content", "has_review_decisions")]


def test_a_failed_month_beside_its_completed_re_upload_keeps_every_month():
    from tests.test_webapp_true_revenue import _payload
    from webapp.app import _package_analysis

    jobs = [_listed("jan", _payload(month=1), content="hj"), _listed("feb-failed", status="error", content="hf"),
            _listed("feb", _payload(month=2), content="hf"), _listed("mar", _payload(month=3), content="hm")]
    for listed in (jobs, list(reversed(jobs))):
        totals = _package_analysis(listed)["totals"]
        assert (totals["true_revenue_total"], totals["verified_revenue_total"], totals["months"]) == (3000.0, 2100.0, 3)
        assert (totals["completed"], totals["failed"], totals["duplicate_documents"]) == (3, 0, 1)
    assert [doc["id"] for doc in _package_analysis(jobs)["documents"]] == ["jan", "feb", "mar", "feb-failed"]


def test_two_current_copies_keep_the_one_listed_first():
    from tests.test_webapp_true_revenue import _payload
    from webapp.app import _package_analysis

    package = _package_analysis([_listed("first", _payload()), _listed("second", _payload())])
    assert _r16(package) == _ONE_MARCH
    assert _left_out(package) == [("second", "first", "same_content", "listed_first")]
    reverse = _package_analysis([_listed("second", _payload()), _listed("first", _payload())])
    assert _left_out(reverse) == [("first", "second", "same_content", "listed_first")]


def test_a_failed_copy_alone_or_beside_another_statement_is_still_a_failed_member():
    from tests.test_webapp_true_revenue import _payload
    from webapp.app import _package_analysis

    alone = _package_analysis([_listed("f", status="error")])["totals"]
    # Audit round 2, R2-B15 (R54): with no statement analysed True is N/A (None), no longer 0.0.
    assert (alone["true_revenue_total"], alone["completed"], alone["failed"], alone["duplicate_documents"]) == (
        None, 0, 1, 0)
    for jobs in ([_listed("f", status="error"), _listed("a", _payload(), content="h2")],
                 [_listed("a", _payload(), content="h2"), _listed("f", status="error")]):
        package = _package_analysis(jobs)
        totals = package["totals"]
        assert (totals["true_revenue_total"], totals["completed"], totals["failed"], totals["duplicate_documents"]) == (
            1000.0, 1, 1, 0)
        assert _left_out(package) == [] and package["duplicates"] == []


def test_the_package_duplicates_return_kept_and_left_out_jobs_in_listed_order():
    from tests.test_webapp_true_revenue import _payload
    from webapp.app import _package_duplicates

    jobs = [_listed("f1", status="error"), _listed("x", _payload(month=2), content="h2"), _listed("a", _payload()),
            _listed("f2", status="error")]
    kept, dropped, repeated, groups = _package_duplicates(jobs)
    assert [job.id for job in kept] == ["x", "a"]
    assert [(entry["job"].id, entry["duplicate_of"], entry["reason"], entry["kept_because"]) for entry in dropped] == [
        ("f1", "a", "same_content", "has_analysis"), ("f2", "a", "same_content", "has_analysis")]
    assert repeated == {}
    assert groups == [{"content_sha256": "h1", "job_ids": ["a", "f1", "f2"], "filenames": ["a.pdf", "f1.pdf", "f2.pdf"],
                       "count": 3}]


def test_why_a_copy_was_kept_reaches_the_package_exports():
    from tests.test_webapp_true_revenue import _payload

    content = b"%PDF-" + _uuid.uuid4().hex.encode()
    failed = store.create("mar.pdf", pdf_bytes=content)
    store.set_error(failed.id, "fabricated failure")
    done = _analysed("mar-again.pdf", _payload(), content)
    csv_body = app.test_client().get(f"/package_download/csv?ids={failed.id},{done.id}").get_data(as_text=True)
    assert "document_2,duplicate_kept_because,has_analysis" in csv_body


# ---------------------------------------------------------------------------
# Audit round 2, R2-B14 (R46): two accounts whose printed full numbers differ are never one statement, however much of
# the statement key they share. Fabricated CONTOSO BANK statements, March 2031, balances 0 -> 0.
# ---------------------------------------------------------------------------

_R46_ROWS = [("2031-03-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 800.0),
             ("2031-03-09", "FABRIKAM INC DES:PAYMENT ID:1", 1200.0),
             ("2031-03-27", "SWEEP TO CONTOSO OPERATING", -2000.0)]


def _printed_report(number, rows=_R46_ROWS, *, start="2031-03-01", end="2031-03-31", opening=0.0,
                    name="CONTOSO BAKERY LLC", bank="CONTOSO BANK"):
    """A fabricated statement printing `number` as its account number, analysed by the real pipeline."""
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    transactions, balance = [], opening
    for day, description, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=day, description=description, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(bank=bank, account_name=name, account_number=number, period_start=start, period_end=end,
                          beginning_balance=opening, ending_balance=balance, currency="USD", currency_source="printed",
                          transactions=transactions)
    return analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                             model_used="fabricated-test")


def _printed(number, rows=_R46_ROWS, **kwargs):
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(_printed_report(number, rows, **kwargs))


def _document_with(number, rows=_R46_ROWS, *, start="2031-03-01", end="2031-03-31", opening=0.0):
    """A checking account (the main account) beside a second account printing `number`, in one document."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    checking = _printed_report("000000003030", [(start[:8] + "04", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:2", 500.0)],
                               start=start, end=end, opening=1500.0).accounts[0]
    second = _printed_report(number, rows, start=start, end=end, opening=opening, name="CONTOSO BAKERY SWEEP").accounts[0]
    transfers, notes = identify_internal_transfers([checking, second])
    roster = [AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "3030", "published", published_index=0),
              AccountRosterEntry("CONTOSO BAKERY SWEEP", "savings", number[-4:], "published", published_index=1)]
    return document_report_to_dict(DocumentReport(accounts=[checking, second], internal_transfers=transfers,
                                                  integrity_notes=notes, account_roster=roster,
                                                  document_period=(start, end)))


def _credit_tiers(package):
    return sorted((row["source_document"], row["description"], row["classification"].get("revenue_tier"),
                   row["classification"].get("revenue_tier_reason"))
                  for row in package["transactions"] if row["amount"] > 0)


def test_two_accounts_sharing_a_last_four_and_both_balances_are_both_counted():
    from webapp.app import _account_identities, _package_analysis

    one, two = _printed("100000001010"), _printed("200000001010")
    shared = {key for key in _account_identities(one) if key.startswith("statement:")}
    assert shared and shared == {key for key in _account_identities(two) if key.startswith("statement:")}
    alone = [_package_analysis([_listed(job_id, payload, content=job_id)]) for job_id, payload in (("one", one),
                                                                                                   ("two", two))]
    package = _package_analysis([_listed("one", one, content="one"), _listed("two", two, content="two")])
    totals = package["totals"]
    assert (totals["duplicate_documents"], totals["has_duplicate_documents"]) == (0, False)
    assert totals["true_revenue_total"] == sum(part["totals"]["true_revenue_total"] for part in alone) == 4000.0
    assert _left_out(package) == []
    # Each row keeps its standalone tier and reason.
    assert _credit_tiers(package) == sorted(row for part in alone for row in _credit_tiers(part))


def test_a_masked_print_of_the_same_statement_is_still_the_same_statement():
    from webapp.app import _package_analysis

    full = _printed("100000001010")
    full["statement"]["transactions"][0]["classification"]["revenue_review_status"] = "confirmed"
    package = _package_analysis([_listed("masked", _printed("XXXXXXXX1010"), content="m"),
                                 _listed("full", full, content="f")])
    assert _left_out(package) == [("masked", "full", "same_statement", "has_review_decisions")]
    assert package["totals"]["true_revenue_total"] == 2000.0


def test_a_partly_masked_print_of_the_same_statement_is_still_the_same_statement():
    from webapp.app import _package_analysis

    package = _package_analysis([_listed("full", _printed("100000001010"), content="f"),
                                 _listed("partly", _printed("10XXXXXX1010"), content="p")])
    assert _left_out(package) == [("partly", "full", "same_statement", "listed_first")]
    assert package["totals"]["true_revenue_total"] == 2000.0


def test_a_shorter_number_that_differs_from_the_full_one_is_another_account():
    from webapp.app import _package_analysis

    package = _package_analysis([_listed("short", _printed("5551010"), content="s"),
                                 _listed("full", _printed("100000001010"), content="f")])
    assert _left_out(package) == [] and package["totals"]["true_revenue_total"] == 4000.0


def test_a_reading_of_one_account_matches_that_account_and_never_its_last_four_twin():
    from webapp.app import _package_analysis

    a, b = _printed("100000001010"), _printed("200000001010")
    other_reading = _printed("200000001010", name="CONTOSO BAKERY L L C")
    package = _package_analysis([_listed("a", a, content="a"), _listed("b", b, content="b"),
                                 _listed("c", other_reading, content="c")])
    assert [doc["id"] for doc in package["documents"] if not doc["is_duplicate"]] == ["a", "b"]
    assert _left_out(package) == [("c", "b", "same_statement", "listed_first")]
    assert package["totals"]["true_revenue_total"] == 4000.0
    # A decision recorded on the other reading makes it the copy kept (R16), and still never A's.
    decided = _copy_module.deepcopy(other_reading)
    decided["statement"]["transactions"][0]["classification"]["revenue_review_status"] = "confirmed"
    package = _package_analysis([_listed("a", a, content="a"), _listed("b", b, content="b"),
                                 _listed("c", decided, content="c")])
    assert [doc["id"] for doc in package["documents"] if not doc["is_duplicate"]] == ["a", "c"]
    assert _left_out(package) == [("b", "c", "same_statement", "has_review_decisions")]


def test_a_document_account_printing_another_full_number_is_kept():
    from webapp.app import _package_analysis

    alone = _listed("alone", _printed("100000001010"), content="alone")
    other = _package_analysis([alone, _listed("doc", _document_with("200000001010"), content="doc")])
    assert [doc["id"] for doc in other["documents"]] == ["alone", "doc#account_1", "doc#account_2"]
    assert other["totals"]["has_duplicate_documents"] is False
    assert "excluded_accounts" not in other
    assert other["totals"]["true_revenue_total"] == 4500.0
    same = _package_analysis([alone, _listed("doc", _document_with("100000001010"), content="doc")])
    assert [doc["id"] for doc in same["documents"]] == ["alone", "doc#account_1"]
    assert [(entry["job_id"], entry["account_index"], entry["reason"], entry["duplicate_of"])
            for entry in same["excluded_accounts"]] == [("doc", 2, "duplicate_statement", "alone")]
    assert same["totals"]["true_revenue_total"] == 2500.0


def test_the_printed_account_digits_and_the_number_conflict():
    from webapp.app import _numbers_conflict, _printed_account_digits

    def digits(number):
        return _printed_account_digits({"statement": {"account_number": number}})

    assert [digits(number) for number in ("XXXX-1010", "12XXXX3456", "100000001010", "1000 0000 1010", "1000.0000/1010",
                                          "XXXXXXXX1010", "", None, "1010 SAVINGS")] == [
        "1010", "3456", "100000001010", "100000001010", "100000001010", "1010", "", "", ""]
    assert _numbers_conflict("100000001010", "200000001010") and _numbers_conflict("5551010", "100000001010")
    assert not _numbers_conflict("1010", "100000001010") and not _numbers_conflict("", "100000001010")
    assert not _numbers_conflict("0001010", "100000001010") and not _numbers_conflict("12345", "912345")


# ---------------------------------------------------------------------------
# Audit round 2, R2-B14 (R14): a shorter printout of days another statement of the account covers, every posted row of
# it printed there too, is left out; any other overlap that shares credits is named and sent to review, never netted.
# Fabricated CONTOSO BANK statements of one account, NORTHWIND SUPPLY LLC payments, 2031.
# ---------------------------------------------------------------------------

_MARCH = [("2031-03-03", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 20000.0),
          ("2031-03-25", "CARD PURCHASE FABRIKAM SUPPLY", -500.0)]
_APRIL = [("2031-04-03", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 8000.0),
          ("2031-04-12", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 7000.0),
          ("2031-04-24", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 5000.0),
          ("2031-04-25", "CARD PURCHASE FABRIKAM SUPPLY", -500.0)]
_ACCOUNT = "000000001010"


def _period(job_id, rows, start, end, *, number=_ACCOUNT, opening=1500.0):
    return _listed(job_id, _printed(number, rows, start=start, end=end, opening=opening), content=job_id)


def _march():
    return _period("mar", _MARCH, "2031-03-01", "2031-03-31")


def _april(number=_ACCOUNT):
    return _period("apr", _APRIL, "2031-04-01", "2031-04-30", number=number, opening=21000.0)


def _r14(package):
    totals = package["totals"]
    return (totals["true_revenue_total"], totals["avg_monthly_true_revenue"], totals["months"], totals["decision"])


@pytest.mark.parametrize("mtd_first", [False, True])
def test_a_month_to_date_printout_inside_its_full_month_is_left_out(mtd_first):
    from webapp.app import _package_analysis

    mtd = _period("mtd", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0)
    assert _r14(_package_analysis([_march(), _april()])) == (40000.0, 20000.0, 2, "approved")
    package = _package_analysis([mtd, _march(), _april()] if mtd_first else [_march(), _april(), mtd])
    totals = package["totals"]
    assert _r14(package) == (40000.0, 20000.0, 2, "review_required")
    assert "statement_periods" not in totals and "overlapping_statements" not in totals
    assert (totals["duplicate_documents"], totals["has_duplicate_documents"]) == (1, True)
    assert _left_out(package) == [("mtd", "apr", "superseded_interim", None)]
    assert [doc["id"] for doc in package["documents"] if not doc["is_duplicate"]] == ["mar", "apr"]


def test_of_two_month_to_date_printouts_the_shorter_is_left_out():
    from webapp.app import _package_analysis

    package = _package_analysis([_march(), _period("mtd10", _APRIL[:1], "2031-04-01", "2031-04-10", opening=21000.0),
                                 _period("mtd20", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0)])
    assert _left_out(package) == [("mtd10", "mtd20", "superseded_interim", None)]
    assert package["totals"]["true_revenue_total"] == 35000.0


def test_an_export_straddling_two_full_months_is_left_out():
    from webapp.app import _package_analysis

    export = _period("export", [_MARCH[1], *_APRIL[:2]], "2031-03-15", "2031-04-15", opening=19000.0)
    package = _package_analysis([_march(), _april(), export])
    # The covering statement sharing the most days: March holds 17 of the export's days, April 15. The export runs 32
    # days, more than a month, so it is a longer printout (R2-B14 review round 1).
    assert _left_out(package) == [("export", "mar", "superseded_long_printout", None)]
    assert _r14(package) == (40000.0, 20000.0, 2, "review_required")


def test_a_partial_overlap_sharing_credits_is_named_and_never_netted():
    from webapp.app import _package_analysis

    interim = _period("int", [_APRIL[2], ("2031-05-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 6000.0)],
                      "2031-04-15", "2031-05-10", opening=30000.0)
    alone = [_package_analysis([job])["totals"] for job in (_april(), interim)]
    assert [part["decision"] for part in alone] == ["approved", "approved"]
    package = _package_analysis([_april(), interim])
    totals = package["totals"]
    assert totals["overlapping_statements"] == [
        {"job": "int", "other": "apr", "shared_credit_count": 1, "shared_credit_total": 5000.0, "currency": "USD",
         "days_shared": 16}]
    assert totals["true_revenue_total"] == sum(part["true_revenue_total"] for part in alone) == 31000.0
    assert totals["decision"] == "review_required"
    assert _left_out(package) == [] and totals["has_duplicate_documents"] is False


def test_statements_sharing_only_a_boundary_day_and_no_row_stay_approved():
    from webapp.app import _package_analysis

    first = _period("first", [("2031-03-10", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 9000.0)], "2031-03-01",
                    "2031-04-01")
    second = _period("second", [("2031-04-10", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 6000.0)], "2031-04-01",
                     "2031-05-01", opening=10500.0)
    package = _package_analysis([first, second])
    assert package["totals"]["decision"] == "approved" and "overlapping_statements" not in package["totals"]
    assert _left_out(package) == []


def test_a_contained_period_printing_other_rows_under_the_same_last_four_is_kept_and_named():
    """Audit round 3, R3-B18 (R3-04): a printed pair one of whose periods lies inside the other is named even when the
    two share no credit, and the package goes to review; it is never netted."""
    from webapp.app import _package_analysis

    other = _period("other", [("2031-04-06", "FABRIKAM INC DES:PAYMENT ID:1", 3000.0)], "2031-04-01", "2031-04-20",
                    number="XXXX1010")
    package = _package_analysis([_april(), other])
    assert _left_out(package) == []
    assert package["totals"]["overlapping_statements"] == [
        {"job": "other", "other": "apr", "shared_credit_count": 0, "shared_credit_total": 0.0, "currency": "USD",
         "days_shared": 20}]
    assert package["totals"]["true_revenue_total"] == 23000.0 and package["totals"]["decision"] == "review_required"


def test_a_repeated_full_statement_still_drops_as_the_same_statement():
    from webapp.app import _package_analysis

    again = _period("again", _APRIL, "2031-04-01", "2031-04-30", opening=21000.0)
    package = _package_analysis([_april(), again])
    assert _left_out(package) == [("again", "apr", "same_statement", "listed_first")]


def test_a_contained_period_whose_full_number_conflicts_is_kept():
    from webapp.app import _package_analysis

    twin = _period("twin", _APRIL[:2], "2031-04-01", "2031-04-20", number="200000001010", opening=21000.0)
    package = _package_analysis([_april("100000001010"), twin])
    assert _left_out(package) == [] and "overlapping_statements" not in package["totals"]
    assert package["totals"]["true_revenue_total"] == 35000.0


def test_a_document_account_that_is_an_interim_of_another_statement_is_left_out_alone():
    from webapp.app import _package_analysis

    document = _document_with(_ACCOUNT, _APRIL[:2], start="2031-04-01", end="2031-04-20", opening=21000.0)
    package = _package_analysis([_april(), _listed("doc", document, content="doc")])
    assert [doc["id"] for doc in package["documents"]] == ["apr", "doc#account_1"]
    assert [(entry["job_id"], entry["account_index"], entry["reason"], entry["duplicate_of"])
            for entry in package["excluded_accounts"]] == [("doc", 2, "superseded_interim", "apr")]
    totals = package["totals"]
    assert (totals["duplicate_accounts"], totals["has_duplicate_documents"], totals["decision"]) == (
        1, True, "review_required")
    assert totals["true_revenue_total"] == 20500.0


def test_a_left_out_interim_names_the_statement_the_package_keeps():
    """Of two printouts of one open month both inside the full month, each names the full statement, even when the
    shorter one shares as many days with the longer printout, listed first, which is itself left out."""
    from webapp.app import _package_analysis

    package = _package_analysis([_period("mtd20", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0), _april(),
                                 _period("mtd10", _APRIL[:1], "2031-04-01", "2031-04-10", opening=21000.0)])
    assert _left_out(package) == [("mtd20", "apr", "superseded_interim", None),
                                  ("mtd10", "apr", "superseded_interim", None)]
    assert package["totals"]["true_revenue_total"] == 20000.0


def test_a_statement_the_package_does_not_count_never_covers_an_interim():
    """A document withheld because its main account was not verified counts none of its money, so the month-to-date
    printout of the account it prints stays in the package."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport
    from analysis.serialization import document_report_to_dict
    from webapp.app import _package_analysis

    april = _printed_report(_ACCOUNT, _APRIL, start="2031-04-01", end="2031-04-30", opening=21000.0).accounts[0]
    roster = [AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "3030", "held", reasons=("page_unresolved",)),
              AccountRosterEntry("CONTOSO BAKERY SAVINGS", "savings", "1010", "published", published_index=0)]
    withheld = document_report_to_dict(DocumentReport(accounts=[april], account_roster=roster,
                                                      document_period=("2031-04-01", "2031-04-30")))
    mtd = _period("mtd", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0)
    package = _package_analysis([_listed("doc", withheld, content="doc"), mtd])
    assert _left_out(package) == [] and package["totals"]["true_revenue_total"] == 15000.0
    assert [(entry["job_id"], entry["reason"]) for entry in package["excluded_accounts"]] == [
        ("doc", "main_account_unverified")]


def test_the_package_rows_name_an_interim_and_an_overlap_in_words():
    from webapp.app import _package_analysis, _package_rows

    mtd = _period("mtd", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0)
    rows = _package_rows(_package_analysis([_march(), _april(), mtd]))
    assert ("document_3", "duplicate_reason", "superseded_interim") in rows
    assert ("document_3", "duplicate_reason_words", "a shorter printout of days another statement covers") in rows
    interim = _period("int", [_APRIL[2], ("2031-05-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 6000.0)],
                      "2031-04-15", "2031-05-10", opening=30000.0)
    rows = _package_rows(_package_analysis([_april(), interim]))
    assert ("overlapping_statement_1", "shared_credit_count", 1) in rows
    assert ("overlapping_statement_1", "currency", "USD") in rows
    assert ("overlapping_statement_1", "words",
            "int.pdf and apr.pdf share 1 credit (5,000.00 USD) in the days both cover, counted in both") in rows
    # Nothing new on a package without an overlap.
    rows = _package_rows(_package_analysis([_march(), _april()]))
    assert not [row for row in rows if row[1] == "duplicate_reason_words" or row[0].startswith("overlapping")]


def test_the_interim_and_overlap_words_reach_the_package_downloads():
    from webapp.app import _package_for_export, _package_analysis, _package_csv, _package_xlsx

    interim = _period("int", [_APRIL[2], ("2031-05-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 6000.0)],
                      "2031-04-15", "2031-05-10", opening=30000.0)
    package = _package_for_export(_package_analysis([_april(), interim]))
    words = "int.pdf and apr.pdf share 1 credit (5,000.00 USD) in the days both cover, counted in both"
    assert f'overlapping_statement_1,words,"{words}"' in _package_csv(package)
    with zipfile.ZipFile(io.BytesIO(_package_xlsx(package))) as book:
        assert words in "".join(book.read(name).decode("utf-8") for name in book.namelist() if name.endswith(".xml"))


# ---------------------------------------------------------------------------
# Audit round 2, R2-B14 review round 1: a printout of more than a month (31 days) is tested first, the longest first,
# before the statements it could cover, so the monthly statements it repeats stay in the package (each its own
# calendar month) and the longer printout is left out (`superseded_long_printout`); the statements of a month or less
# keep the shortest-first order, so a full month is never left out in favour of two partial printouts of it.
# Fabricated CONTOSO BANK statements of one account, NORTHWIND SUPPLY LLC payments, 2031.
# ---------------------------------------------------------------------------

_JAN = [("2031-01-06", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 10000.0),
        ("2031-01-20", "CARD PURCHASE FABRIKAM SUPPLY", -100.0)]
_FEB = [("2031-02-06", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 10000.0),
        ("2031-02-20", "CARD PURCHASE FABRIKAM SUPPLY", -100.0)]
_MAR_Q1 = [("2031-03-06", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 10000.0),
           ("2031-03-20", "CARD PURCHASE FABRIKAM SUPPLY", -100.0)]
_LONG_PRINTOUT_WORDS = "a printout of more than a month whose every row other statements of the account print"


def _first_quarter():
    """January, February and March 2031, each a monthly statement of the account, $10,000 of True each."""
    return (_period("jan", _JAN, "2031-01-01", "2031-01-31", opening=1500.0),
            _period("feb", _FEB, "2031-02-01", "2031-02-28", opening=11400.0),
            _period("mar", _MAR_Q1, "2031-03-01", "2031-03-31", opening=21300.0))


@pytest.mark.parametrize("long_first", [False, True])
def test_the_monthly_statements_stay_and_a_quarterly_printout_of_their_rows_is_left_out(long_first):
    from webapp.app import _package_analysis

    monthly = _first_quarter()
    quarter = _period("q1", _JAN + _FEB + _MAR_Q1, "2031-01-01", "2031-03-31")
    assert _r14(_package_analysis(list(monthly))) == (30000.0, 10000.0, 3, "approved")
    package = _package_analysis([quarter, *monthly] if long_first else [*monthly, quarter])
    assert _r14(package) == (30000.0, 10000.0, 3, "review_required")
    # It repeats the monthly statement sharing the most of its days: January's 31, March's 31, January listed first.
    assert _left_out(package) == [("q1", "jan", "superseded_long_printout", None)]
    assert [doc["id"] for doc in package["documents"] if not doc["is_duplicate"]] == ["jan", "feb", "mar"]
    assert "overlapping_statements" not in package["totals"]


@pytest.mark.parametrize("long_first", [False, True])
def test_the_monthly_statements_stay_and_a_two_month_export_of_their_rows_is_left_out(long_first):
    from webapp.app import _package_analysis

    monthly = _first_quarter()
    export = _period("janfeb", _JAN + _FEB, "2031-01-01", "2031-02-28")
    package = _package_analysis([export, *monthly] if long_first else [*monthly, export])
    assert _r14(package) == (30000.0, 10000.0, 3, "review_required")
    assert _left_out(package) == [("janfeb", "jan", "superseded_long_printout", None)]


def test_an_export_of_more_than_a_month_is_left_out_before_the_month_it_covers():
    """A 45-day export (March 1 to April 14) printing March's rows and April's first two: taken first, it is left out,
    so March stays and the April days the export shares with April are never counted twice."""
    from webapp.app import _package_analysis

    export = _period("export", [*_MARCH, *_APRIL[:2]], "2031-03-01", "2031-04-14")
    package = _package_analysis([_march(), _april(), export])
    assert _left_out(package) == [("export", "mar", "superseded_long_printout", None)]
    assert _r14(package) == (40000.0, 20000.0, 2, "review_required")
    assert "overlapping_statements" not in package["totals"]


def test_a_full_month_stays_over_two_partial_printouts_that_print_its_days_between_them():
    """Two printouts of one month that overlap each other and print every row of the full month between them are each
    left out, the shorter first; the full month is never left out in their favour, which would count the days the
    two share twice."""
    from webapp.app import _package_analysis

    early = _period("early", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0)
    late = _period("late", _APRIL[1:], "2031-04-12", "2031-04-30", opening=29000.0)
    package = _package_analysis([early, late, _april()])
    assert _left_out(package) == [("early", "apr", "superseded_interim", None),
                                  ("late", "apr", "superseded_interim", None)]
    assert package["totals"]["true_revenue_total"] == 20000.0
    assert "overlapping_statements" not in package["totals"]


def test_a_document_account_printing_more_than_a_month_of_kept_statements_is_left_out_alone():
    from webapp.app import _package_analysis

    january, february, _march_q1 = _first_quarter()
    document = _document_with(_ACCOUNT, _JAN + _FEB, start="2031-01-01", end="2031-02-28", opening=1500.0)
    package = _package_analysis([january, february, _listed("doc", document, content="doc")])
    assert [doc["id"] for doc in package["documents"]] == ["jan", "feb", "doc#account_1"]
    assert [(entry["job_id"], entry["account_index"], entry["reason"], entry["duplicate_of"])
            for entry in package["excluded_accounts"]] == [("doc", 2, "superseded_long_printout", "jan")]
    assert package["totals"]["true_revenue_total"] == 20500.0


def test_the_package_rows_name_a_longer_printout_in_words():
    from webapp.app import _package_analysis, _package_rows

    quarter = _period("q1", _JAN + _FEB + _MAR_Q1, "2031-01-01", "2031-03-31")
    rows = _package_rows(_package_analysis([*_first_quarter(), quarter]))
    assert ("document_4", "duplicate_reason", "superseded_long_printout") in rows
    assert ("document_4", "duplicate_reason_words", _LONG_PRINTOUT_WORDS) in rows


# ---------------------------------------------------------------------------
# Audit round 3, R3-B18 (R3-02, R3-04, R3-05; MCA standard §4.6(3)): one account's statements in a package. A statement
# that prints no bank or fewer than four account digits is still one statement with another reading of it when its
# period, its balances and its ledger rows on the day and the signed cents are the same (the `ledger:` key); it is
# compared with the account's other statements (a "possible pair": banks, names and currencies not differing); an
# overlap of one account's statements a day off or in other wording is named, never netted; and a monthly statement of
# 32 to 35 days is never left out in favour of partial printouts that overlap each other. Fabricated CONTOSO BANK
# statements of CONTOSO BAKERY LLC, NORTHWIND SUPPLY LLC and FABRIKAM rows, 2031.
# ---------------------------------------------------------------------------

#: The (number, bank) variants of a statement whose account is not printed in full: no number read, a number masked to
#: three digits, a full number printed with no bank read.
_UNKEYED_VARIANTS = [(None, "CONTOSO BANK"), ("XXXXXXXX010", "CONTOSO BANK"), ("000000001010", "")]


def _unkeyed(job_id, rows, start, end, *, number=None, bank="CONTOSO BANK", opening=1500.0,
             name="CONTOSO BAKERY LLC"):
    return _listed(job_id, _printed(number, rows, start=start, end=end, opening=opening, bank=bank, name=name),
                   content=job_id)


def _pairs(package):
    return package["totals"].get("overlapping_statements")


@pytest.mark.parametrize(("number", "bank"), _UNKEYED_VARIANTS)
def test_a_re_read_statement_whose_number_is_not_read_is_left_out_by_its_ledger(number, bank):
    from webapp.app import _package_analysis

    march = _unkeyed("mar", _MARCH, "2031-03-01", "2031-03-31", number=number, bank=bank)
    april = _unkeyed("apr", _APRIL, "2031-04-01", "2031-04-30", number=number, bank=bank, opening=21000.0)
    again_payload = _copy_module.deepcopy(march.analysis)
    again_payload["model_used"] = "fabricated-other-reader"
    package = _package_analysis([march, april, _listed("again", again_payload, content="again")])
    assert _left_out(package) == [("again", "mar", "same_statement", "listed_first")]
    assert _r14(package) == (40000.0, 20000.0, 2, "review_required")


@pytest.mark.parametrize(("number", "bank"), _UNKEYED_VARIANTS)
def test_a_re_read_statement_carrying_a_decision_keeps_the_decided_copy(number, bank):
    from webapp.app import _package_analysis

    march = _unkeyed("mar", _MARCH, "2031-03-01", "2031-03-31", number=number, bank=bank)
    april = _unkeyed("apr", _APRIL, "2031-04-01", "2031-04-30", number=number, bank=bank, opening=21000.0)
    again_payload = _copy_module.deepcopy(march.analysis)
    again_payload["model_used"] = "fabricated-other-reader"
    again_payload["statement"]["transactions"][0]["classification"]["revenue_review_status"] = "confirmed"
    package = _package_analysis([march, april, _listed("again", again_payload, content="again")])
    assert _left_out(package) == [("mar", "again", "same_statement", "has_review_decisions")]
    assert package["totals"]["true_revenue_total"] == 40000.0


def test_two_readings_with_one_number_read_are_one_statement():
    from webapp.app import _account_identities, _package_analysis

    march = _period("mar", _MARCH, "2031-03-01", "2031-03-31")
    again = _unkeyed("again", _MARCH, "2031-03-01", "2031-03-31")
    ledger = {key for key in _account_identities(march.analysis) if key.startswith("ledger:")}
    assert ledger and ledger == {key for key in _account_identities(again.analysis) if key.startswith("ledger:")}
    assert not any(key.startswith("statement:") for key in _account_identities(again.analysis))
    package = _package_analysis([march, again])
    assert _left_out(package) == [("again", "mar", "same_statement", "listed_first")]
    assert package["totals"]["true_revenue_total"] == 20000.0


def test_the_ledger_key_reads_the_period_the_balances_and_every_row_on_its_day_and_cents():
    from webapp.app import _account_identities

    def ledger(payload):
        return {key for key in _account_identities(payload) if key.startswith("ledger:")}

    march = _printed(None, _MARCH, start="2031-03-01", end="2031-03-31", opening=1500.0)
    (key,) = ledger(march)
    assert key.startswith("ledger:2031-03-01|2031-03-31|1500.00|21000.00|")
    # Other wording, another classification or a review decision never change it; another day or cents does.
    worded = _copy_module.deepcopy(march)
    worded["statement"]["transactions"][0]["description"] = "ONLINE DEPOSIT NORTHWIND SUPPLY REF 0001"
    worded["statement"]["transactions"][0]["classification"]["revenue_review_status"] = "rejected"
    assert ledger(worded) == {key}
    moved = _copy_module.deepcopy(march)
    moved["statement"]["transactions"][0]["date"] = "2031-03-04"
    assert ledger(moved) and ledger(moved) != {key}
    # A statement that prints no balance, no period day or no row has none.
    for field, value in (("beginning_balance", None), ("period_end", None), ("transactions", [])):
        bare = _copy_module.deepcopy(march)
        bare["statement"][field] = value
        assert ledger(bare) == set()


@pytest.mark.parametrize("mtd_first", [False, True])
@pytest.mark.parametrize(("number", "bank"), _UNKEYED_VARIANTS)
def test_an_interim_of_a_statement_whose_number_is_not_read_is_left_out(number, bank, mtd_first):
    from webapp.app import _package_analysis

    march = _unkeyed("mar", _MARCH, "2031-03-01", "2031-03-31", number=number, bank=bank)
    april = _unkeyed("apr", _APRIL, "2031-04-01", "2031-04-30", number=number, bank=bank, opening=21000.0)
    mtd = _unkeyed("mtd", _APRIL[:2], "2031-04-01", "2031-04-20", number=number, bank=bank, opening=21000.0)
    package = _package_analysis([mtd, march, april] if mtd_first else [march, april, mtd])
    assert _left_out(package) == [("mtd", "apr", "superseded_interim", None)]
    assert _r14(package) == (40000.0, 20000.0, 2, "review_required")
    assert _pairs(package) is None


def test_an_unkeyed_overlap_sharing_its_credits_is_named_and_never_netted():
    from webapp.app import _package_analysis

    interim = _unkeyed("int", [_APRIL[2], ("2031-05-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 6000.0)],
                       "2031-04-15", "2031-05-10", opening=30000.0)
    package = _package_analysis([_unkeyed("apr", _APRIL, "2031-04-01", "2031-04-30", opening=21000.0), interim])
    assert _pairs(package) == [{"job": "int", "other": "apr", "shared_credit_count": 1, "shared_credit_total": 5000.0,
                                "currency": "USD", "days_shared": 16}]
    assert package["totals"]["true_revenue_total"] == 31000.0
    assert package["totals"]["decision"] == "review_required" and _left_out(package) == []


_SAVINGS = [("2031-04-05", "ONLINE TRANSFER FROM CHK", 3000.0),
            ("2031-04-18", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:9", 2500.0),
            ("2031-04-30", "INTEREST PAYMENT", 1.25)]


@pytest.mark.parametrize("savings_rows", [
    _SAVINGS,
    # One of its three credits a checking credit's cents a day off: under half of them, so no pair.
    [_SAVINGS[0], ("2031-04-13", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:9", 7000.0), _SAVINGS[2]],
])
def test_two_unkeyed_accounts_of_one_bank_sharing_no_credit_are_never_named(savings_rows):
    from webapp.app import _package_analysis

    checking = _unkeyed("chk", _APRIL, "2031-04-01", "2031-04-30", opening=21000.0)
    savings = _unkeyed("sav", savings_rows, "2031-04-01", "2031-04-30", opening=9000.0)
    alone = [_package_analysis([job])["totals"]["true_revenue_total"] for job in (checking, savings)]
    package = _package_analysis([checking, savings])
    assert _pairs(package) is None and _left_out(package) == []
    assert package["totals"]["true_revenue_total"] == sum(alone)


def test_a_lone_matching_credit_names_a_possible_pair():
    """The recorded residual: an unkeyed savings account whose only credit is a checking credit's cents a day off is
    named with the checking account (review only, never netted)."""
    from webapp.app import _package_analysis

    checking = _unkeyed("chk", _APRIL, "2031-04-01", "2031-04-30", opening=21000.0)
    savings = _unkeyed("sav", [("2031-04-13", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:9", 7000.0)], "2031-04-01",
                       "2031-04-30", opening=9000.0)
    package = _package_analysis([checking, savings])
    assert _pairs(package) == [{"job": "sav", "other": "chk", "shared_credit_count": 1, "shared_credit_total": 7000.0,
                                "currency": "USD", "days_shared": 30}]
    assert package["totals"]["decision"] == "review_required" and _left_out(package) == []


def test_a_possible_pair_printing_one_period_and_both_balances_is_named():
    """Another reading of the April statement that misread every credit's cents: no credit is shared and the ledgers
    differ, but the two print one period and both balances, so they are one account's and the pair is named."""
    from webapp.app import _package_analysis

    april = _unkeyed("apr", _APRIL, "2031-04-01", "2031-04-30", opening=21000.0)
    misread = _copy_module.deepcopy(april.analysis)
    for row in misread["statement"]["transactions"]:
        if row["amount"] > 0:
            row["amount"] = round(row["amount"] + 0.08, 2)
    package = _package_analysis([april, _listed("misread", misread, content="misread")])
    assert _pairs(package) == [{"job": "misread", "other": "apr", "shared_credit_count": 0, "shared_credit_total": 0.0,
                                "currency": "USD", "days_shared": 30}]
    assert _left_out(package) == [] and package["totals"]["decision"] == "review_required"


@pytest.mark.parametrize("differs", ["name", "currency"])
def test_statements_whose_names_or_currencies_differ_are_never_one_account(differs):
    from webapp.app import _package_analysis

    april = _unkeyed("apr", _APRIL, "2031-04-01", "2031-04-30", opening=21000.0)
    if differs == "name":
        mtd = _unkeyed("mtd", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0, name="FABRIKAM TOOLS LLC")
    else:
        mtd = _unkeyed("mtd", _APRIL[:2], "2031-04-01", "2031-04-20", opening=21000.0)
        mtd.analysis["statement"]["currency"] = "CAD"
    package = _package_analysis([april, mtd])
    assert _left_out(package) == [] and _pairs(package) is None


def test_the_package_bank_reads_the_informal_export_label_as_its_bank():
    from webapp.app import _bank_key, _package_bank

    assert _package_bank({"bank": "Chase  Transaction Export"}) == "chase"
    assert _package_bank({"bank": "Chase"}) == "chase" and _package_bank({"bank": "CONTOSO BANK"}) == "contoso bank"
    assert _package_bank({"bank": None}) == "" and _package_bank(None) == ""
    # R2-OW15's and R2-OW16's passes keep reading the label as printed.
    assert _bank_key({"bank": "Chase Transaction Export"}) == "chase transaction export"


def test_a_chase_transaction_export_is_compared_with_its_chase_statements():
    """The informal export's label is read as its bank: an export printing the account's last four beside the
    account's Chase statement is left out when the statement prints its rows, and named when they are a day off. (The
    export is an informal printout, so its package goes to review either way.)"""
    from webapp.app import _package_analysis

    april = _listed("apr", _printed(_ACCOUNT, _APRIL, start="2031-04-01", end="2031-04-30", opening=21000.0,
                                    bank="Chase"), content="apr")

    def export(rows):
        return _listed("export", _printed("...1010", rows, start="2031-04-01", end="2031-04-20", opening=21000.0,
                                          bank="Chase Transaction Export"), content="export")

    package = _package_analysis([april, export(_APRIL[:2])])
    assert _left_out(package) == [("export", "apr", "superseded_interim", None)]
    assert package["totals"]["true_revenue_total"] == 20000.0 and package["totals"]["decision"] == "review_required"
    shifted = [("2031-04-04", _APRIL[0][1], _APRIL[0][2]), ("2031-04-13", _APRIL[1][1], _APRIL[1][2])]
    package = _package_analysis([april, export(shifted)])
    assert _left_out(package) == []
    assert _pairs(package) == [{"job": "export", "other": "apr", "shared_credit_count": 2,
                                "shared_credit_total": 15000.0, "currency": "USD", "days_shared": 20}]
    assert package["totals"]["decision"] == "review_required"


def test_a_month_to_date_printout_a_day_off_is_named_and_sent_to_review():
    from webapp.app import _package_analysis

    mtd = _period("mtd", [("2031-04-04", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 8000.0),
                          ("2031-04-13", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 7000.0)],
                  "2031-04-01", "2031-04-20", opening=21000.0)
    package = _package_analysis([_march(), _april(), mtd])
    assert _left_out(package) == []
    assert _r14(package) == (55000.0, 27500.0, 2, "review_required")
    assert _pairs(package) == [{"job": "mtd", "other": "apr", "shared_credit_count": 2, "shared_credit_total": 15000.0,
                                "currency": "USD", "days_shared": 20}]


def test_a_printout_in_other_wording_with_a_moved_debit_is_named():
    from webapp.app import _package_analysis

    mtd = _period("mtd", [("2031-04-03", "ONLINE DEPOSIT NORTHWIND SUPPLY REF 0001", 8000.0),
                          ("2031-04-12", "ONLINE DEPOSIT NORTHWIND SUPPLY REF 0002", 7000.0),
                          ("2031-04-15", "CARD PURCHASE FABRIKAM SUPPLY", -75.0)],
                  "2031-04-01", "2031-04-20", opening=21000.0)
    package = _package_analysis([_march(), _april(), mtd])
    assert _left_out(package) == []
    assert [(pair["job"], pair["other"], pair["shared_credit_count"], pair["shared_credit_total"])
            for pair in _pairs(package)] == [("mtd", "apr", 2, 15000.0)]


def test_a_partial_shift_names_the_whole_double_count():
    from webapp.app import _package_analysis

    mtd = _period("mtd", [("2031-04-03", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 8000.0),
                          ("2031-04-13", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 7000.0)],
                  "2031-04-01", "2031-04-20", opening=21000.0)
    package = _package_analysis([_march(), _april(), mtd])
    assert [(pair["job"], pair["other"], pair["shared_credit_count"], pair["shared_credit_total"])
            for pair in _pairs(package)] == [("mtd", "apr", 2, 15000.0)]


def test_a_quarterly_export_a_day_off_names_each_monthly_statement():
    from datetime import date, timedelta

    from webapp.app import _package_analysis

    later = [((date.fromisoformat(day) + timedelta(days=1)).isoformat(), text, amount)
             for day, text, amount in _JAN + _FEB + _MAR_Q1]
    package = _package_analysis([*_first_quarter(), _period("q1", later, "2031-01-01", "2031-03-31")])
    assert _left_out(package) == []
    assert [(pair["job"], pair["other"], pair["shared_credit_count"], pair["shared_credit_total"], pair["days_shared"])
            for pair in _pairs(package)] == [("q1", "jan", 1, 10000.0, 31), ("q1", "feb", 1, 10000.0, 28),
                                             ("q1", "mar", 1, 10000.0, 31)]
    assert (package["totals"]["true_revenue_total"], package["totals"]["decision"]) == (60000.0, "review_required")


def test_a_recurring_credit_beside_a_boundary_day_is_never_named():
    """The shape of the cached boundary pairs: one recurring amount just before the shared day on one statement and
    just after it on the next lies outside the days both cover, so it is never a shared credit."""
    from webapp.app import _package_analysis

    first = _period("first", [("2031-03-30", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 4000.0)], "2031-03-01",
                    "2031-04-01")
    second = _period("second", [("2031-04-02", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 4000.0)], "2031-04-01",
                     "2031-05-01", opening=5500.0)
    package = _package_analysis([first, second])
    assert _pairs(package) is None and package["totals"]["decision"] == "approved"
    assert _left_out(package) == []


def test_a_credit_both_statements_print_on_their_shared_boundary_day_is_named_whatever_its_wording():
    from webapp.app import _package_analysis

    first = _period("first", [("2031-04-01", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:7", 4000.0)], "2031-03-01",
                    "2031-04-01")
    second = _period("second", [("2031-04-01", "NORTHWIND SUPPLY PAYMENT REF 7", 4000.0)], "2031-04-01",
                     "2031-05-01")
    package = _package_analysis([first, second])
    assert [(pair["job"], pair["other"], pair["shared_credit_count"], pair["days_shared"])
            for pair in _pairs(package)] == [("second", "first", 1, 1)]
    assert package["totals"]["decision"] == "review_required" and _left_out(package) == []


def test_the_shared_credits_are_matched_one_to_one_inside_the_days_both_cover():
    from datetime import date

    from webapp.app import _shared_credits

    def entry(*credits):
        return {"credits": [{"date": day, "amount": amount, "description": "FABRIKAM"} for day, amount in credits]}

    earlier = entry(("2031-04-03", 8000.0), ("2031-04-05", 8000.0), ("2031-04-10", 500.0), ("2031-03-30", 4000.0))
    later = entry(("2031-04-04", 8000.0), ("2031-04-04", 8000.0), ("2031-04-04", 8000.0), ("2031-04-09", 500.25),
                  ("2031-04-02", 4000.0))
    first, last = date(2031, 4, 1), date(2031, 4, 30)
    # Two of the later statement's three 8,000.00 credits each take one earlier credit; 500.25 is other cents; the
    # earlier 4,000.00 lies outside the common days.
    assert _shared_credits(earlier, later, first, last) == (2, 1600000)
    assert _shared_credits(entry(("2031-04-01", 10.0)), entry(("2031-04-05", 10.0)), first, last) == (0, 0)
    assert _shared_credits(entry(("2031-04-01", 10.0)), entry(("2031-04-04", 10.0)), first, last) == (1, 1000)


@pytest.mark.parametrize("full_first", [True, False])
@pytest.mark.parametrize("end", ["2031-07-04", "2031-07-05", "2031-07-07"])
def test_a_monthly_statement_of_32_to_35_days_stays_over_two_overlapping_partial_printouts(end, full_first):
    from webapp.app import _package_analysis

    rows = [("2031-06-05", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 6000.0),
            ("2031-06-16", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 9000.0),
            ("2031-06-28", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 4000.0),
            ("2031-06-30", "CARD PURCHASE FABRIKAM SUPPLY", -200.0)]
    full = _period("full", rows, "2031-06-03", end)
    early = _period("early", rows[:2], "2031-06-03", "2031-06-20")
    late = _period("late", rows[1:], "2031-06-14", end, opening=7500.0)
    package = _package_analysis([full, early, late] if full_first else [early, late, full])
    assert _left_out(package) == [("early", "full", "superseded_interim", None),
                                  ("late", "full", "superseded_interim", None)]
    assert package["totals"]["true_revenue_total"] == 19000.0 and _pairs(package) is None


def test_a_monthly_statement_of_33_days_stays_over_partial_printouts_that_tile_it():
    """Kept whole, the statement keeps its recurring payer's three credits together, so its Verified stands (left out in
    favour of the two partials, one of them printed the payer's credit alone and Verified fell)."""
    from webapp.app import _package_analysis

    payer = "FABRIKAM WHOLESALE DES:ACH CREDIT ID:7"
    rows = [("2031-06-05", payer, 6000.0), ("2031-06-16", payer, 9000.0), ("2031-06-28", payer, 4000.0),
            ("2031-06-30", "CARD PURCHASE SAMPLE OFFICE SUPPLY", -200.0)]
    full = _period("full", rows, "2031-06-03", "2031-07-05")
    alone = _package_analysis([full])["totals"]
    early = _period("early", rows[:2], "2031-06-03", "2031-06-20")
    late = _period("late", rows[2:], "2031-06-21", "2031-07-05", opening=16500.0)
    package = _package_analysis([early, late, full])
    assert _left_out(package) == [("early", "full", "superseded_interim", None),
                                  ("late", "full", "superseded_interim", None)]
    totals = package["totals"]
    assert (totals["true_revenue_total"], totals["verified_revenue_total"]) == (
        alone["true_revenue_total"], alone["verified_revenue_total"])


def test_a_35_day_export_straddling_three_monthly_statements_is_left_out():
    """Control: a pure day threshold would leave February (28 days) out in favour of the export."""
    from webapp.app import _package_analysis

    export = _period("export", _FEB, "2031-01-29", "2031-03-04", opening=11400.0)
    package = _package_analysis([*_first_quarter(), export])
    assert _left_out(package) == [("export", "feb", "superseded_long_printout", None)]
    assert [doc["id"] for doc in package["documents"] if not doc["is_duplicate"]] == ["jan", "feb", "mar"]
    assert (package["totals"]["true_revenue_total"], package["totals"]["months"]) == (30000.0, 3)


# ---------------------------------------------------------------------------
# Audit round 2, R2-B15 (R15): an account the package leaves out of its figures for any reason but a repeat (a statement
# whose main account is held or idle, an account that did not validate, every account of a document whose transfers
# could not be paired or that left a section out without proof) sends the package to review and is named: completeness
# partial, excluded_account_count, the exclusion's filename and an excluded_account_<n> download section. Membership
# and every figure are as before. Fabricated CONTOSO BANK statements of 2031, FABRIKAM INC paying $10,000.00 a month.
# ---------------------------------------------------------------------------

_R15_PAYMENT = "FABRIKAM INC DES:ACH PAYMENT ID:1"


def _r15_bounds(month):
    return f"2031-{month:02d}-01", f"2031-{month:02d}-28"


def _r15_checking(month):
    start, end = _r15_bounds(month)
    return _printed_report("000000001010", [(f"2031-{month:02d}-05", _R15_PAYMENT, 10000.0)], start=start, end=end,
                           opening=1500.0)


def _r15_savings(month):
    start, end = _r15_bounds(month)
    return _printed_report("000000002020", [(f"2031-{month:02d}-04", "INTEREST PAID", 2.0)], start=start, end=end,
                           opening=9000.0, name="CONTOSO BAKERY SAVINGS")


def _r15_month(month):
    """A clean single-account statement: CONTOSO BAKERY LLC's checking, FABRIKAM INC paying $10,000.00."""
    from analysis.serialization import document_report_to_dict

    return _listed(f"m{month}", document_report_to_dict(_r15_checking(month)), content=f"m{month}",
                   filename=f"m{month}.pdf")


def _r15_document(month, *, main="published", notes=(), omitted=None, job_id=None):
    """The business checking account (the main account) beside savings, in one document of `month`: `main` published,
    held (only savings published) or idle; `notes` the document's integrity notes; `omitted` its omitted sections."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    savings = _r15_savings(month).accounts[0]
    savings_entry = AccountRosterEntry("CONTOSO BAKERY SAVINGS", "savings", "2020", "published",
                                       published_index=1 if main == "published" else 0)
    if main == "published":
        accounts = [_r15_checking(month).accounts[0], savings]
        main_entry = AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "1010", "published", published_index=0)
    else:
        accounts = [savings]
        main_entry = (AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "1010", "held", reasons=("page_unresolved",))
                      if main == "held" else AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "1010", "idle",
                                                                balance=25.0))
    transfers, found = identify_internal_transfers(accounts)
    payload = document_report_to_dict(DocumentReport(accounts=accounts, internal_transfers=transfers,
                                                     integrity_notes=[*found, *notes],
                                                     account_roster=[main_entry, savings_entry],
                                                     document_period=_r15_bounds(month)))
    if omitted is not None:
        payload["document"]["omitted_sections"] = omitted
    job_id = job_id or f"doc{month}"
    return _listed(job_id, payload, content=job_id, filename=f"{job_id}.pdf")


def _r15(package):
    totals = package["totals"]
    return {"decision": totals["decision"], "completeness": totals.get("completeness"),
            "excluded_account_count": totals.get("excluded_account_count"),
            "excluded": [(entry["job_id"], entry["filename"], entry["account_index"], entry["reason"])
                         for entry in package.get("excluded_accounts") or []]}


@pytest.mark.parametrize(("main", "reason"), [("held", "main_account_unverified"), ("idle", "main_account_idle")])
def test_a_statement_withheld_for_its_main_account_sends_the_package_to_review(main, reason):
    """R15 T1, T2: January, a February whose main account is held (or idle), March. February stays out of every figure
    (the 2026-09-23 ruling); the package says so and needs review."""
    from webapp.app import _package_analysis, _package_rows

    package = _package_analysis([_r15_month(1), _r15_document(2, main=main), _r15_month(3)])
    assert _r15(package) == {"decision": "review_required", "completeness": "partial", "excluded_account_count": 1,
                             "excluded": [("doc2", "doc2.pdf", None, reason)]}
    totals = package["totals"]
    assert (totals["true_revenue_total"], totals["months"], totals["completed"], totals["failed"]) == (20000.0, 2, 2, 0)
    assert "sibling_account_omission_detected" not in totals  # Q10's key only
    rows = [(field, value) for section, field, value in _package_rows(package) if section == "excluded_account_1"]
    assert rows == [("job_id", "doc2"), ("filename", "doc2.pdf"), ("account_index", ""), ("account_count", 2),
                    ("outcome", "withheld"), ("reason", reason)]


def test_an_account_of_a_document_that_did_not_validate_gates_as_it_does_alone():
    """R15 T3: a document's savings account whose own outcome is review (corporate_use manual_review) was left out under
    Approved; the same two accounts uploaded as two statements need review (Q1: the weaker account)."""
    from analysis.serialization import document_report_to_dict
    from webapp.app import _package_analysis

    document = _r15_document(3)
    document.analysis["accounts"][1]["quality"]["corporate_use"] = "manual_review"
    package = _package_analysis([document])
    assert _r15(package) == {"decision": "review_required", "completeness": "partial", "excluded_account_count": 1,
                             "excluded": [("doc3", "doc3.pdf", 2, "quality_needs_review")]}
    assert package["totals"]["true_revenue_total"] == 10000.0 and package["totals"]["completed"] == 1
    savings = document_report_to_dict(_r15_savings(3))
    savings["quality"]["corporate_use"] = "manual_review"
    apart = _package_analysis([_listed("chk", document_report_to_dict(_r15_checking(3)), content="chk"),
                               _listed("sav", savings, content="sav")])
    assert apart["totals"]["decision"] == "review_required" and apart["totals"]["manual_review"] == 1


def test_a_document_whose_transfers_could_not_be_paired_names_both_accounts():
    """R15 T4: the aggregation is refused (Q2) and stays refused; the package needs review and names each account."""
    from webapp.app import _package_analysis, _package_rows

    package = _package_analysis([_r15_month(1), _r15_document(2, notes=("ambiguous_internal_transfer",))])
    assert _r15(package) == {"decision": "review_required", "completeness": "partial", "excluded_account_count": 2,
                             "excluded": [("doc2", "doc2.pdf", 1, "document_transfer_pairing_ambiguous"),
                                          ("doc2", "doc2.pdf", 2, "document_transfer_pairing_ambiguous")]}
    assert package["totals"]["true_revenue_total"] == 10000.0
    sections = {section for section, _field, _value in _package_rows(package)}
    assert {"excluded_account_1", "excluded_account_2"} <= sections and "excluded_account_3" not in sections


def test_a_document_that_left_a_section_out_without_proof_sends_the_package_to_review():
    """R15 T5 (L1-C17): every account of the document is left out; the package needs review."""
    from webapp.app import _package_analysis

    unratified = [{"label": "CONTOSO SECTION B", "reason": "absence_of_parsed_rows", "posting_count": 0}]
    package = _package_analysis([_r15_month(1), _r15_document(2, omitted=unratified)])
    assert _r15(package)["decision"] == "review_required"
    assert [entry[3] for entry in _r15(package)["excluded"]] == ["document_omission_unratified"] * 2


def test_a_package_none_of_whose_accounts_counted_needs_review_and_reads_no_figure():
    """R15 T6 with R54: one document whose main account is held counts nothing; True is N/A, never $0.00."""
    from webapp.app import _package_analysis

    package = _package_analysis([_r15_document(3, main="held")])
    totals = package["totals"]
    assert _r15(package)["decision"] == "review_required" and totals["completeness"] == "partial"
    assert (totals["completed"], totals["failed"], totals["true_revenue_total"], totals["verified_revenue_total"],
            totals["avg_monthly_true_revenue"]) == (0, 0, None, None, None)
    assert package["documents"] == []


def test_a_package_with_no_exclusion_carries_no_new_key():
    """R15 C1, C2, C4: three clean months, a repeated statement (B11's path) and a document of two validated accounts
    publish no completeness, no excluded_account_count and no excluded_account section; their decisions stand."""
    from webapp.app import _package_analysis, _package_rows

    clean = _package_analysis([_r15_month(1), _r15_month(2), _r15_month(3)])
    repeated = _package_analysis([_r15_month(1), _r15_month(1)])
    document = _package_analysis([_r15_document(3)])
    for package in (clean, repeated, document):
        assert "completeness" not in package["totals"] and "excluded_account_count" not in package["totals"]
        assert not any(section.startswith("excluded_account") for section, _f, _v in _package_rows(package))
    assert clean["totals"]["decision"] == "approved" and "excluded_accounts" not in clean
    assert repeated["totals"]["decision"] == "review_required" and repeated["totals"]["duplicate_documents"] == 1
    assert document["totals"]["decision"] == "approved" and document["totals"]["completed"] == 2


def test_a_ratified_omission_stays_partial_and_approved():
    """R15 C3 (Q10): surfaced, never demoted; no account is left out, so nothing new is said."""
    from webapp.app import _package_analysis

    ratified = [{"label": "CONTOSO SECTION B", "reason": "printed_dormancy_declaration", "posting_count": 0}]
    totals = _package_analysis([_r15_document(3, omitted=ratified)])["totals"]
    assert (totals["completeness"], totals["sibling_account_omission_detected"], totals["decision"]) == (
        "partial", True, "approved")
    assert "excluded_account_count" not in totals


def test_a_document_account_repeating_another_statement_keeps_the_duplicate_path():
    """R15 C2: a repeat is no exclusion: its entry is `is_duplicate`, and the package needs review for the repeat only."""
    from analysis.serialization import document_report_to_dict
    from webapp.app import _package_analysis

    alone = _listed("chk", document_report_to_dict(_r15_checking(3)), content="chk")
    package = _package_analysis([alone, _r15_document(3)])
    assert [(entry["job_id"], entry["account_index"], entry["reason"], entry["is_duplicate"])
            for entry in package["excluded_accounts"]] == [("doc3", 1, "duplicate_statement", True)]
    assert "completeness" not in package["totals"] and "excluded_account_count" not in package["totals"]
    assert package["totals"]["decision"] == "review_required" and package["totals"]["duplicate_accounts"] == 1


# ---------------------------------------------------------------------------
# Audit round 2, R2-B15 (R54): a package with no statement analysed publishes no True, Verified, Counted or Held figure
# (None, never a $0.00 an underwriter would read as a decline), and a job still queued or processing is pending, never
# failed. Fabricated SAMPLE jobs and CONTOSO BAKERY LLC's January 2031.
# ---------------------------------------------------------------------------

_R54_NULLED = ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
               "excluded_pending_review_total", "excluded_pending_review_count", "true_revenue",
               "counted_flagged_by_reason", "excluded_pending_review_by_reason", "verified_revenue_total",
               "confirmed_true_revenue_total", "confirmed_true_revenue", "avg_monthly_true_revenue",
               "avg_monthly_verified_revenue")


@pytest.mark.parametrize(("status", "failed", "pending"), [
    ("error", 1, None), ("interrupted", 1, None), ("queued", 0, 1), ("processing", 0, 1)])
def test_a_package_with_no_analysed_statement_reads_no_revenue_figure(status, failed, pending):
    import csv

    from webapp.app import _package_analysis, _package_csv

    package = _package_analysis([_listed("sample", status=status, filename="sample.pdf")])
    totals = package["totals"]
    assert {key: totals[key] for key in _R54_NULLED} == dict.fromkeys(_R54_NULLED)
    assert totals["revenue_tiers_sum_to_posted"] is False and totals["revenue_reconciles"] is False
    assert package["true_revenue_evidence"] is None and package["detection"]["true_revenue_evidence"] is None
    assert (totals["completed"], totals["failed"], totals.get("pending")) == (0, failed, pending)
    assert totals["decision"] == "review_required"
    # Unchanged: the structural zeros of the currency layer (test_package_currency) and the non-revenue figure.
    assert (totals["total_credits"], totals["avg_monthly_credits"], totals["non_revenue_total"]) == (0.0, 0.0, 0.0)
    assert totals["currency_resolution"] == "no_analyzed_documents"
    cells = {(row[0], row[1]): row[2] for row in csv.reader(io.StringIO(_package_csv(package))) if len(row) == 3}
    assert cells[("totals", "true_revenue_total")] == "" and cells[("totals", "avg_monthly_true_revenue")] == ""


def test_an_analysed_statement_beside_a_failed_or_pending_one_keeps_its_figures():
    """R54 C1 (spec §10.4): a failed member's credits are in no total; the analysed one's stand, and both gate."""
    from webapp.app import _package_analysis

    for status, failed, pending in (("error", 1, None), ("queued", 0, 1)):
        package = _package_analysis([_r15_month(1), _listed("sample", status=status, content="s", filename="s.pdf")])
        totals = package["totals"]
        assert (totals["true_revenue_total"], totals["avg_monthly_true_revenue"], totals["months"]) == (
            10000.0, 10000.0, 1)
        assert (totals["completed"], totals["failed"], totals.get("pending"), totals["decision"]) == (
            1, failed, pending, "review_required")
        assert totals["revenue_tiers_sum_to_posted"] is True
    alone = _package_analysis([_r15_month(1)])
    assert "pending" not in alone["totals"] and alone["totals"]["decision"] == "approved"


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
