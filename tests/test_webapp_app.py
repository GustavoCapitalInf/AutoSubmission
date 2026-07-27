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

    def to_markdown(self):
        return "# Hello"


def _mock_processing(monkeypatch, page_count=2):
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: page_count)

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        if on_page_delta:
            on_page_delta(0, "raw stream")
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown: object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {
        "statement": {"bank": "Test Bank"},
        "metrics": {"average_balance": 123.45},
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
    })


def _upload_one(client):
    data = {"files": (io.BytesIO(b"%PDF-fake"), "s.pdf")}
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


def test_upload_can_force_visual_ocr(monkeypatch):
    seen = {}
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        seen["force_ocr"] = force_ocr
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown: object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    client = app.test_client()
    resp = client.post(
        "/upload",
        data={"force_ocr": "1", "files": (io.BytesIO(b"%PDF-fake"), "s.pdf")},
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert body["jobs"][0]["force_ocr"] is True
    assert seen["force_ocr"] is True


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
