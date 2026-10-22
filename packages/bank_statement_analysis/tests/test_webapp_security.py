"""Wave 0 / D-2a — development-server safety and webapp-boundary hardening.

Covers RISK R-19 (Werkzeug debugger / dev server), R-23 (unvalidated upload),
R-24 (Content-Disposition + spreadsheet formula injection) and R-25 (full
account numbers in webapp-served payloads).

Masking is asserted at the *webapp boundary* only: `analysis/serialization.py`
still emits the account number as printed, because the CLI and the forensic
oracles depend on it. See docs WAVE0_BRIEF §1.
"""
from __future__ import annotations

import io
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

from webapp.app import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_FILES,
    MAX_UPLOAD_PAGES,
    _safe_download_name,
    _server_config,
    app,
    main,
    store,
)
from webapp.export_view import _mask_account, masked
from webapp.spreadsheet import _escape_formula


ACCOUNT = "XXXXXX987654321"
MASKED = "****4321"


class _FakeThread:
    """Runs the target synchronously so job completion is deterministic."""

    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


def _pdf(size: int = 32) -> bytes:
    return b"%PDF-1.7\n" + b"0" * max(0, size - 9)


def _analysis_payload() -> dict:
    return {
        "statement": {
            "bank": "Test Bank",
            "account_number": ACCOUNT,
            "period_start": "2054-01-01",
            "period_end": "2054-01-31",
            "transactions": [
                {
                    "date": "2054-01-04",
                    "description": "ACH DEPOSIT",
                    "amount": 1000.0,
                    "classification": {
                        "account": ACCOUNT,
                        "bank": "Test Bank",
                        "source_location": "page-1-row-1",
                        "revenue_classification": "unverified_deposit",
                        "revenue_initial_classification": "unverified_deposit",
                    },
                }
            ],
        },
        "classifications": [{"account": ACCOUNT, "classification": "revenue"}],
        "metrics": {"effective_total_deposits": 1000.0},
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {"known_funders": []},
    }


def _completed_job(filename: str = "statement.pdf"):
    job = store.create(filename)
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=_analysis_payload())
    return job


def _sheet_xml(xlsx: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
        return archive.read("xl/worksheets/sheet1.xml").decode("utf-8")


# --------------------------------------------------------------------------
# 1. Production-safe server behaviour (R-19)
# --------------------------------------------------------------------------


def test_app_debug_mode_is_disabled():
    assert app.debug is False
    assert app.config.get("DEBUG") is False


def test_server_config_defaults_to_loopback_port_5000(monkeypatch):
    monkeypatch.delenv("WEBAPP_HOST", raising=False)
    monkeypatch.delenv("WEBAPP_PORT", raising=False)
    assert _server_config() == ("127.0.0.1", 5000)


def test_server_config_honours_env_override(monkeypatch):
    monkeypatch.setenv("WEBAPP_HOST", "0.0.0.0")
    monkeypatch.setenv("WEBAPP_PORT", "8080")
    assert _server_config() == ("0.0.0.0", 8080)


def test_main_serves_via_waitress_not_the_werkzeug_dev_server(monkeypatch):
    calls = {}

    def fake_serve(wsgi_app, **kwargs):
        calls["app"] = wsgi_app
        calls["kwargs"] = kwargs

    monkeypatch.setitem(sys.modules, "waitress", types.SimpleNamespace(serve=fake_serve))
    monkeypatch.delenv("WEBAPP_HOST", raising=False)
    monkeypatch.delenv("WEBAPP_PORT", raising=False)

    def explode(*_args, **_kwargs):  # pragma: no cover - guard
        raise AssertionError("app.run() must never be used to serve")

    monkeypatch.setattr(app, "run", explode)

    main()

    assert calls["app"] is app
    assert calls["kwargs"]["host"] == "127.0.0.1"
    assert calls["kwargs"]["port"] == 5000


# --------------------------------------------------------------------------
# 2. Upload validation (R-23)
# --------------------------------------------------------------------------


def test_max_content_length_matches_the_advertised_100mb_limit():
    assert MAX_UPLOAD_BYTES == 100 * 1024 * 1024
    assert app.config["MAX_CONTENT_LENGTH"] == MAX_UPLOAD_BYTES


def test_oversize_request_returns_a_json_error_not_an_html_page(monkeypatch):
    monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", 512)
    client = app.test_client()
    resp = client.post(
        "/upload",
        data={"files": (io.BytesIO(_pdf(4096)), "big.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413
    assert resp.mimetype == "application/json"
    assert "error" in resp.get_json()


def test_upload_rejects_a_file_that_is_not_a_pdf(monkeypatch):
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)
    enqueued = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda *a, **k: enqueued.append(a))

    resp = app.test_client().post(
        "/upload",
        data={"files": (io.BytesIO(b"<?php system($_GET[0]); ?>"), "evil.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body
    assert body["filename"] == "evil.pdf"
    assert enqueued == []


def test_upload_rejects_an_oversize_individual_file(monkeypatch):
    monkeypatch.setattr("webapp.app.MAX_UPLOAD_BYTES", 64)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)
    enqueued = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda *a, **k: enqueued.append(a))

    resp = app.test_client().post(
        "/upload",
        data={"files": (io.BytesIO(_pdf(4096)), "big.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["filename"] == "big.pdf"
    assert enqueued == []


def test_upload_rejects_more_files_than_the_batch_cap(monkeypatch):
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)
    enqueued = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda *a, **k: enqueued.append(a))

    files = [(io.BytesIO(_pdf()), f"s{i}.pdf") for i in range(MAX_UPLOAD_FILES + 1)]
    resp = app.test_client().post(
        "/upload",
        data={"files": files},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()
    assert enqueued == []


def test_upload_rejects_a_file_over_the_page_cap(monkeypatch):
    monkeypatch.setattr(
        "webapp.app.pdf_page_count", lambda pdf_bytes: MAX_UPLOAD_PAGES + 1
    )
    enqueued = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda *a, **k: enqueued.append(a))

    resp = app.test_client().post(
        "/upload",
        data={"files": (io.BytesIO(_pdf()), "long.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["filename"] == "long.pdf"
    assert enqueued == []


def test_upload_rejects_an_unreadable_pdf(monkeypatch):
    def boom(pdf_bytes):
        raise ValueError("damaged xref")

    monkeypatch.setattr("webapp.app.pdf_page_count", boom)
    enqueued = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda *a, **k: enqueued.append(a))

    resp = app.test_client().post(
        "/upload",
        data={"files": (io.BytesIO(_pdf()), "broken.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["filename"] == "broken.pdf"
    assert enqueued == []


def test_upload_rejects_the_whole_batch_when_one_file_is_bad(monkeypatch):
    """A partially accepted batch would leave the dashboard aggregating an
    incomplete package without ever saying so."""
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)
    enqueued = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda *a, **k: enqueued.append(a))

    resp = app.test_client().post(
        "/upload",
        data={
            "files": [
                (io.BytesIO(_pdf()), "good.pdf"),
                (io.BytesIO(b"not a pdf at all"), "bad.pdf"),
            ]
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["filename"] == "bad.pdf"
    assert enqueued == []


def test_upload_still_accepts_a_valid_pdf(monkeypatch):
    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 2)
    monkeypatch.setattr("webapp.app._enqueue_job", lambda *a, **k: None)

    resp = app.test_client().post(
        "/upload",
        data={"files": (io.BytesIO(_pdf()), "good.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["jobs"][0]["page_count"] == 2


# --------------------------------------------------------------------------
# 3. Content-Disposition sanitization (R-24)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('bank"; filename="evil', "bank_filename_evil"),
        ("report\r\nX-Injected: 1", "report_X-Injected_1"),
        ("../../etc/passwd", ".._.._etc_passwd"),
        ("Jan 2026 statement.final", "Jan_2026_statement.final"),
        ("", "download"),
        ("....", "download"),
        (" " * 2, "download"),
    ],
)
def test_safe_download_name_whitelists_the_base_name(raw, expected):
    assert _safe_download_name(raw) == expected


def test_download_header_is_safe_for_a_hostile_filename():
    job = store.create('evil"; filename="pwned.exe.pdf')
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=_analysis_payload())

    resp = app.test_client().get(f"/download/{job.id}/md")
    disposition = resp.headers["Content-Disposition"]
    assert disposition == 'attachment; filename="evil_filename_pwned.exe.md"'
    assert disposition.count('"') == 2
    assert "\r" not in disposition and "\n" not in disposition


# --------------------------------------------------------------------------
# 4. CSV / XLSX formula-injection guard (R-24)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dangerous",
    [
        "=1+1",
        '=HYPERLINK("http://evil","click")',
        "+1+1",
        "-2+3+cmd|' /C calc'!A0",
        "@SUM(A1:A9)",
        "\t=1+1",
        "\r=1+1",
    ],
)
def test_escape_formula_neutralises_dangerous_cells(dangerous):
    escaped = _escape_formula(dangerous)
    assert escaped.startswith("'")
    assert escaped[1:] == dangerous


@pytest.mark.parametrize(
    "safe", ["-1234.56", "-0", "-1e5", "+250.00", "1000", "ACH DEPOSIT", "", "2054-01-31"]
)
def test_escape_formula_leaves_numbers_and_plain_text_alone(safe):
    assert _escape_formula(safe) == safe


@pytest.mark.parametrize("sneaky", ["-nan", "+inf", "-infinity", "+NaN"])
def test_escape_formula_does_not_treat_nan_or_inf_as_a_number(sneaky):
    """Python's float() accepts these; a spreadsheet reads the leading sign as
    the start of a formula. The numeric carve-out must be money-shaped only."""
    assert _escape_formula(sneaky) == "'" + sneaky


def test_escape_formula_passes_non_strings_through_unchanged():
    assert _escape_formula(-1234.56) == -1234.56
    assert _escape_formula(None) is None
    assert _escape_formula(True) is True


def test_statement_csv_escapes_a_formula_description():
    job = store.create("formula.pdf")
    analysis = _analysis_payload()
    analysis["statement"]["bank"] = "=cmd|' /C calc'!A0"
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=analysis)

    body = app.test_client().get(f"/download/{job.id}/csv").get_data(as_text=True)
    assert "'=cmd|' /C calc'!A0" in body
    assert "\n=cmd" not in body
    assert ",=cmd" not in body


def test_statement_xlsx_escapes_a_formula_description():
    job = store.create("formula-xlsx.pdf")
    analysis = _analysis_payload()
    analysis["statement"]["bank"] = "=1+1"
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=analysis)

    sheet = _sheet_xml(app.test_client().get(f"/download/{job.id}/xlsx").get_data())
    # Audit B11 (I52): the XLSX types its cells, and text stays an inline string, which a spreadsheet never evaluates.
    # The apostrophe is therefore literal text there, kept on purpose: a Save As CSV writes it out with the cell, so
    # the text stays inert when the sheet is written back out as a CSV.
    assert "t=\"inlineStr\"><is><t>'=1+1</t>" in sheet
    assert "<t>=1+1</t>" not in sheet
    assert "<f>" not in sheet


def test_xlsx_money_cells_are_numbers_and_text_never_a_formula():
    """Audit B11 (I52): a number, negative money included, is a numeric cell; a numeric-looking STRING stays text."""
    job = store.create("numeric-xlsx.pdf")
    analysis = _analysis_payload()
    analysis["metrics"]["effective_total_withdrawals"] = -1234.5
    analysis["statement"]["bank"] = "-1234.56"
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=analysis)
    sheet = _sheet_xml(app.test_client().get(f"/download/{job.id}/xlsx").get_data())
    assert "><v>-1234.5</v></c>" in sheet
    assert 't="inlineStr"><is><t>-1234.56</t>' in sheet
    assert "<f>" not in sheet


def test_package_csv_and_xlsx_escape_a_formula_bank_name():
    job = store.create("pkg-formula.pdf")
    analysis = _analysis_payload()
    analysis["statement"]["bank"] = "=1+1"
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=analysis)
    client = app.test_client()

    csv_body = client.get(f"/package_download/csv?ids={job.id}").get_data(as_text=True)
    assert "'=1+1" in csv_body
    assert ",=1+1" not in csv_body

    sheet = _sheet_xml(client.get(f"/package_download/xlsx?ids={job.id}").get_data())
    # Audit B11 (I52): a literal apostrophe inside an inline string, never a formula (see the statement test above).
    assert "t=\"inlineStr\"><is><t>'=1+1</t>" in sheet
    assert "<t>=1+1</t>" not in sheet
    assert "<f>" not in sheet


def test_csv_export_still_reports_negative_money_as_a_number():
    job = store.create("negative.pdf")
    analysis = _analysis_payload()
    analysis["metrics"]["cash_flow"] = -1234.56
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=analysis)

    body = app.test_client().get(f"/download/{job.id}/csv").get_data(as_text=True)
    assert "metrics,cash_flow,-1234.56" in body


# --------------------------------------------------------------------------
# 4b. XLSX characters XML 1.0 forbids (audit 2026-10-13, EXP-7)
# --------------------------------------------------------------------------
# One control character (or U+FFFE / U+FFFF) in a cell made sheet1.xml ill-formed, so the whole workbook failed to
# open; a lone surrogate made the download raise. The XLSX path now SUBSTITUTES U+FFFD for each such character (never
# deletes it: a deleted leading control would let "=..." start the cell). The CSV and the JSON keep the text as read.

_XML_FORBIDDEN = ["\x00", "\x01", "\x08", "\x0b", "\x0c", "\x0e", "\x1f", "￾", "￿", "\ud800", "\udfff"]


@pytest.mark.parametrize("char", _XML_FORBIDDEN, ids=lambda c: f"U+{ord(c):04X}")
def test_xlsx_sheet_stays_well_formed_with_a_forbidden_character(char):
    from xml.etree import ElementTree

    from webapp.spreadsheet import rows_xlsx

    blob = rows_xlsx([("posted_credit", "description", f"SAMPLE DEPOSIT{char}REF")])
    sheet = _sheet_xml(blob)
    ElementTree.fromstring(sheet)  # raises ParseError when the sheet is ill-formed
    assert "<t>SAMPLE DEPOSIT�REF</t>" in sheet


@pytest.mark.parametrize("char", _XML_FORBIDDEN, ids=lambda c: f"U+{ord(c):04X}")
def test_xlsx_with_a_forbidden_character_opens_in_a_spreadsheet_reader(char):
    openpyxl = pytest.importorskip("openpyxl")
    from webapp.spreadsheet import rows_xlsx

    blob = rows_xlsx([("posted_credit", "description", f"SAMPLE{char}")])
    workbook = openpyxl.load_workbook(io.BytesIO(blob))
    values = [cell.value for row in workbook.active.iter_rows() for cell in row]
    assert "SAMPLE�" in values


@pytest.mark.parametrize("char", ["\t", "\n", "\r", "\x7f", "\x85", "é", "\U0001f600"])
def test_xlsx_keeps_the_characters_xml_allows(char):
    from webapp.spreadsheet import _xml_escape

    assert _xml_escape(f"A{char}B") == f"A{char}B"


def test_xml_escape_still_escapes_markup_exactly_as_before():
    from webapp.spreadsheet import _xml_escape

    assert _xml_escape('CONTOSO & <FABRIKAM> "SAMPLE"') == "CONTOSO &amp; &lt;FABRIKAM&gt; &quot;SAMPLE&quot;"
    assert _xml_escape(-12.5) == "-12.5"


def test_a_leading_control_never_lets_a_formula_lead_start_the_cell():
    """Substitute, never delete: `_escape_formula` does not see a leading U+0001 as a formula lead, so deleting it would
    leave "=HYPERLINK(...)" at the start of the cell with no apostrophe."""
    from webapp.spreadsheet import rows_xlsx

    sheet = _sheet_xml(rows_xlsx([("statement", "bank", '\x01=HYPERLINK("http://example.invalid")')]))
    assert '<t>�=HYPERLINK(&quot;http://example.invalid&quot;)</t>' in sheet
    assert "<t>=" not in sheet
    assert "<f>" not in sheet


def test_package_xlsx_with_a_control_character_in_a_file_name_opens_and_the_csv_keeps_the_name():
    from xml.etree import ElementTree

    job = store.create("SAMPLE\x0bstatement.pdf")
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=_analysis_payload())
    client = app.test_client()

    xlsx = client.get(f"/package_download/xlsx?ids={job.id}")
    assert xlsx.status_code == 200
    sheet = _sheet_xml(xlsx.get_data())
    ElementTree.fromstring(sheet)
    assert "SAMPLE�statement.pdf" in sheet

    csv_body = client.get(f"/package_download/csv?ids={job.id}").get_data(as_text=True)
    assert "SAMPLE\x0bstatement.pdf" in csv_body


# --------------------------------------------------------------------------
# 5. Account-number masking at the webapp boundary (R-25)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("XXXXXX987654321", "****4321"),
        ("XXXXXX-7450", "****7450"),
        ("xxxxx8125", "****8125"),
        ("...1234", "****1234"),
        ("0050", "****0050"),
        ("****1234", "****1234"),  # idempotent
        ("12 34 56 78", "****5678"),
        ("50", "****50"),
        ("no digits here", "****"),
    ],
)
def test_mask_account_keeps_only_the_last_four_digits(raw, expected):
    assert _mask_account(raw) == expected


def test_mask_account_preserves_absent_values():
    assert _mask_account(None) is None
    assert _mask_account("") is None


def test_masked_rewrites_every_account_field_at_any_depth():
    served = masked(_analysis_payload())
    assert served["statement"]["account_number"] == MASKED
    assert served["statement"]["transactions"][0]["classification"]["account"] == MASKED
    assert served["classifications"][0]["account"] == MASKED
    assert ACCOUNT not in json.dumps(served)


def test_masked_does_not_mutate_the_stored_analysis():
    payload = _analysis_payload()
    masked(payload)
    assert payload["statement"]["account_number"] == ACCOUNT
    assert payload["classifications"][0]["account"] == ACCOUNT


def test_analysis_route_serves_a_masked_account_number():
    job = _completed_job()
    body = app.test_client().get(f"/analysis/{job.id}").get_data(as_text=True)
    assert ACCOUNT not in body
    assert MASKED in body


def test_analysis_masking_does_not_corrupt_the_stored_job():
    job = _completed_job()
    app.test_client().get(f"/analysis/{job.id}")
    assert store.get(job.id).analysis["statement"]["account_number"] == ACCOUNT


@pytest.mark.parametrize("fmt", ["json", "csv", "xlsx"])
def test_statement_downloads_serve_a_masked_account_number(fmt):
    job = _completed_job()
    data = app.test_client().get(f"/download/{job.id}/{fmt}").get_data()
    text = _sheet_xml(data) if fmt == "xlsx" else data.decode("utf-8")
    assert ACCOUNT not in text
    assert MASKED in text


def test_package_analysis_serves_a_masked_account_number():
    job = _completed_job("pkg.pdf")
    body = app.test_client().get(f"/package_analysis?ids={job.id}").get_data(as_text=True)
    assert ACCOUNT not in body
    assert MASKED in body
    assert json.loads(body)["documents"][0]["account"] == MASKED


@pytest.mark.parametrize("fmt", ["json", "csv", "xlsx"])
def test_package_downloads_serve_a_masked_account_number(fmt):
    job = _completed_job("pkg-dl.pdf")
    data = app.test_client().get(f"/package_download/{fmt}?ids={job.id}").get_data()
    text = _sheet_xml(data) if fmt == "xlsx" else data.decode("utf-8")
    assert ACCOUNT not in text
    assert MASKED in text


def test_revenue_review_response_serves_a_masked_account_number():
    job = _completed_job("review.pdf")
    resp = app.test_client().post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "page-1-row-1", "decision": "confirm"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert ACCOUNT not in body
    assert MASKED in body
    # The review itself still landed, and the stored record keeps the real number.
    stored = store.get(job.id).analysis
    assert stored["statement"]["transactions"][0]["classification"][
        "revenue_review_status"
    ] == "confirmed"
    assert stored["statement"]["account_number"] == ACCOUNT


# --------------------------------------------------------------------------
# 6. The UI tells the truth about what the server enforces
# --------------------------------------------------------------------------


def test_dropzone_caption_matches_the_enforced_limits():
    html = app.test_client().get("/").get_data(as_text=True)
    assert f"{MAX_UPLOAD_BYTES // (1024 * 1024)}MB" in html
    assert f"up to {MAX_UPLOAD_FILES} PDFs" in html
    assert f"{MAX_UPLOAD_PAGES} pages each" in html


def test_upload_failures_surface_the_server_message_not_just_a_status_code():
    """A rejected upload must name the file and the reason. Rendering only
    `Upload failed (400)` would leave an operator with no idea which of a
    twelve-statement batch the server refused."""
    javascript = (
        Path(__file__).resolve().parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")
    upload_handler = javascript.split("function uploadFiles(")[1].split("\nfunction ")[0]
    assert "body.error" in upload_handler
    assert "body.filename" in upload_handler


def test_raw_ocr_surfaces_are_documented_residual_exposure():
    """`/markdown`, `/result` and the md/html downloads intentionally still
    carry the printed account number: they are the analyst's source view and
    masking them would corrupt the evidence trail. The fix is authentication
    (D-2b), not redaction. This test pins that decision so a future reader
    sees it was deliberate rather than missed."""
    job = store.create("raw.pdf")
    store.set_result(job.id, f"Account {ACCOUNT}", f"<p>Account {ACCOUNT}</p>",
                     analysis=_analysis_payload())
    client = app.test_client()
    assert ACCOUNT in client.get(f"/markdown/{job.id}").get_data(as_text=True)
    assert ACCOUNT in client.get(f"/result/{job.id}").get_data(as_text=True)
    assert ACCOUNT in client.get(f"/download/{job.id}/md").get_data(as_text=True)


# --------------------------------------------------------------------------
# 6. Statement text served as a page (audit 2026-10-13, EXP-1)
# --------------------------------------------------------------------------
# A PDF's text layer is untrusted (an applicant's, possibly forged, statement). The report pages that carry it
# (/result, the html and md downloads, /markdown) are served with a sandboxing Content-Security-Policy and nosniff, so
# markup in a statement can never run a script in the app's origin; a saved html download carries the same policy
# (without `sandbox`, which a meta tag cannot carry) inside its head, so it is inert when opened from disk.

_INJECTED = "<img src=x onerror=\"document.title='INJECTED'\">"


def _report_job(html: str, markdown: str = "# md"):
    job = store.create("report.pdf")
    store.set_result(job.id, markdown, html, analysis=_analysis_payload())
    return job


@pytest.mark.parametrize("route", ["/result/{id}", "/download/{id}/html", "/download/{id}/md", "/markdown/{id}"])
def test_report_routes_serve_a_sandboxing_csp_and_nosniff(route):
    job = _report_job(f"<p>{_INJECTED}</p>", markdown=_INJECTED)
    resp = app.test_client().get(route.format(id=job.id))
    assert resp.status_code == 200
    policy = resp.headers.get("Content-Security-Policy", "")
    directives = [d.strip() for d in policy.split(";")]
    assert directives[0] == "sandbox"
    for needed in ("default-src 'none'", "style-src 'unsafe-inline'", "img-src data:", "form-action 'none'",
                   "base-uri 'none'"):
        assert needed in directives, (needed, policy)
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_the_report_routes_keep_their_content_types():
    """/result stays a utf-8 html page and /markdown a utf-8 text page (its charset was written twice before)."""
    job = _report_job("<p>md</p>")
    client = app.test_client()
    assert client.get(f"/result/{job.id}").headers["Content-Type"] == "text/html; charset=utf-8"
    assert client.get(f"/markdown/{job.id}").headers["Content-Type"] == "text/plain; charset=utf-8"
    assert client.get(f"/result/{job.id}").get_data(as_text=True) == "<p>md</p>"


def test_the_html_download_of_a_stored_report_carries_the_policy_in_its_head():
    """A report stored before the renderer carried the meta tag gets it at serve time, inside its head; the rest of
    the stored bytes are served unchanged."""
    from ocr.render import REPORT_CSP

    stored = "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<title>x</title>\n</head>\n<body>\n" \
        f"<p>{_INJECTED}</p>\n</body>\n</html>\n"
    job = _report_job(stored)
    body = app.test_client().get(f"/download/{job.id}/html").get_data(as_text=True)
    meta = f'<meta http-equiv="Content-Security-Policy" content="{REPORT_CSP}">'
    head = body.split("</head>", 1)[0]
    assert head.count(meta) == 1
    assert body.replace(meta + "\n", "", 1) == stored


def test_the_html_download_does_not_repeat_a_policy_the_report_already_carries():
    from ocr.render import REPORT_CSP, markdown_to_html

    rendered = markdown_to_html("SAMPLE STATEMENT", title="report.pdf")
    job = _report_job(rendered)
    body = app.test_client().get(f"/download/{job.id}/html").get_data(as_text=True)
    assert body == rendered
    assert body.count(f'content="{REPORT_CSP}"') == 1


def test_a_crafted_text_layer_reaches_the_review_page_as_text_end_to_end(monkeypatch):
    """The finding's path, end to end: a fabricated PDF whose text layer prints an <img onerror> and a <script>
    element, through the real upload and the real worker (deterministic parse). The refused statement's "Review
    extraction" page and its html download show the markup as text, under the sandboxing policy."""
    fitz = pytest.importorskip("fitz")
    import webapp.app as webapp_app

    image_tag = "<img src=x onerror=\"document.title='INJECTED'\">"
    script_tag = "<script>document.title='INJECTED2'</script>"
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page()
        lines = ["SAMPLE BANK STATEMENT (fabricated)", "01/04 ACH DEPOSIT CONTOSO 100.00", image_tag, script_tag]
        lines += [f"filler line {i} with ordinary words for the native text gate" for i in range(25)]
        for n, line in enumerate(lines):
            page.insert_text((72, 72 + 13 * n), line, fontsize=9)
    pdf = doc.tobytes()
    doc.close()

    monkeypatch.setattr(webapp_app, "_enqueue_job", lambda job_id, pdf_bytes, filename, force_ocr:
                        webapp_app.run_job(job_id, pdf_bytes, filename, webapp_app.store, force_ocr))
    client = app.test_client()
    resp = client.post("/upload", data={"files": (io.BytesIO(pdf), "crafted.pdf")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200, resp.get_json()
    job_id = resp.get_json()["jobs"][0]["id"]
    assert client.get(f"/status/{job_id}").get_json()["status"] == "done"
    assert image_tag in client.get(f"/markdown/{job_id}").get_data(as_text=True)  # the evidence keeps the text

    for route in (f"/result/{job_id}", f"/download/{job_id}/html"):
        served = client.get(route)
        body = served.get_data(as_text=True)
        assert image_tag not in body and script_tag not in body
        assert "<img" not in body and "<script" not in body
        assert "&lt;img src=x onerror=" in body and "&lt;script&gt;" in body
        assert served.headers["Content-Security-Policy"].startswith("sandbox; default-src 'none'")


def test_a_policy_printed_in_the_statement_body_does_not_stand_in_for_the_head_one():
    from ocr.render import REPORT_CSP

    fake = f'<meta http-equiv="Content-Security-Policy" content="{REPORT_CSP}">'
    stored = f"<html><head><title>x</title></head><body><p>{fake}</p>{_INJECTED}</body></html>"
    job = _report_job(stored)
    body = app.test_client().get(f"/download/{job.id}/html").get_data(as_text=True)
    assert fake in body.split("</head>", 1)[0]


def test_the_other_downloads_are_unchanged_by_the_report_policy():
    job = _report_job("<p>md</p>")
    client = app.test_client()
    for fmt in ("json", "csv", "xlsx"):
        assert "Content-Security-Policy" not in client.get(f"/download/{job.id}/{fmt}").headers
