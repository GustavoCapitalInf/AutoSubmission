"""The four newest corpus statements, asserted end to end.

Source-of-truth policy for the two image-only fixtures (columbia,
first_farmers): their OCR markdown comes from the **committed artifacts** in
`tests/corpus_cache/`, keyed by the SHA-256 of the source PDF, exactly as
`corpus_gate.py` resolves scanned statements. Live Tesseract output varies with
version, language data, and platform, and these tests assert exact financial
values — on the GitHub runner (tesseract 5.3.x) columbia OCR'd differently
enough that no deterministic parser matched, while it passes on a 5.5.0 dev box.
Committed artifacts make the asserted values identical on every machine.

The real local-Tesseract path is preserved, not deleted:
`test_live_tesseract_reproduces_the_committed_artifact_reports` re-OCRs both
fixtures with the local binary and compares the resulting report to the
artifact-served one. It carries the `live` marker, so it is deselected from the
default run (`pytest.ini` addopts) and runs with `pytest -m live`. That marker
is documented as "hits the real OCR endpoint"; this widens it to "runs real OCR
rather than a committed fixture", which is the property that matters here — a
dedicated marker would need a `pytest.ini` registration plus an addopts change
to stay out of the default run, and that file is outside this task's allowlist.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pytest

from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from corpus_artifacts import cached_markdown, manifest_entries, sha256_hex
from ocr.local_tesseract import parse_local_tesseract
from ocr.native_text import parse_native_pdf_text
from ocr.rasterize import pdf_page_count
from webapp.app import (
    _analysis_csv,
    _analysis_xlsx,
    _package_analysis,
    _package_csv,
    _package_xlsx,
    app,
    store,
)
from webapp.jobs import Job


ROOT = Path(__file__).resolve().parents[1]

SOURCES = {
    "columbia": {
        "path": "Bank Statements/Misc/Columbia May 26 complete.pdf",
        "sha256": "0CBD2AD897B90137878F81EF608778735CA0DFEAB23D25793F2C6F1DF6C6127D",
        "pages": 4,
        "ocr": True,
    },
    "first_farmers": {
        "path": "Bank Statements/Misc/First Farmers 2026 01-document.pdf",
        "sha256": "58CB0DCC7460A445541C6181F461432BBF948BC31AB7F1C64459FF6ADC8F0243",
        "pages": 3,
        "ocr": True,
    },
    "navigant": {
        "path": "Bank Statements/Others/Navigant Credit Union 2026-06-30.pdf",
        "sha256": "B1DECFC9A6C43C3D28F49F7D70D490CB970079324E7D5BFE49575C71A56F24EF",
        "pages": 8,
        "ocr": False,
    },
    "relay": {
        "path": "Bank Statements/Others/Relay Operations-June-2026.pdf",
        "sha256": "6FBA5B1AC5707B4C4758791C4F780EB6351AF1A228A15301F2301B858CC7DB9D",
        "pages": 12,
        "ocr": False,
    },
}

EXPECTED = {
    "columbia": {
        "bank": "Columbia Bank",
        "parser": "columbia-bank-deterministic",
        "account": "XXXXXX4166",
        "period": ("2026-05-01", "2026-05-31"),
        "opening": 6291.76,
        "ending": 13904.87,
        "transactions": 108,
        "credits": 147052.51,
        "debits": 139439.40,
        "daily_sum": 411545.17,
        "adb": 13275.65,
        "minimum": 4831.08,
        "maximum": 37211.56,
        "printed_average": 13275.65,
        "revenue": (98103.31, 5002.00, 43947.20, 103105.31),
        "revenue_counts": (48, 1, 5),
        "channels": (52, 49, 0, 0, 2, 0),
        "lenders": (26, 79378.55, 3, 19412.49),
        "insurance": (0, 0.00),
        "reversal_pairs": 1,
        "daily": [
            9072.74, 9072.74, 9072.74, 14908.58, 9369.15, 14479.21,
            15322.85, 10705.49, 10705.49, 10705.49, 18768.22, 13726.42,
            16712.17, 37211.56, 19110.95, 19110.95, 19110.95, 9772.30,
            4831.08, 7525.18, 13011.28, 9619.35, 9619.35, 9619.35,
            9619.35, 9677.65, 17084.73, 12285.24, 13904.87, 13904.87,
            13904.87,
        ],
    },
    "first_farmers": {
        "bank": "First Farmers Bank & Trust",
        "parser": "first-farmers-bank-&-trust-deterministic",
        "account": "XXXXXXXXXXX0947",
        "period": ("2026-01-01", "2026-01-30"),
        "opening": 1552.27,
        "ending": 2028.08,
        "transactions": 16,
        "credits": 6705.81,
        "debits": 6230.00,
        "daily_sum": 89389.16,
        "adb": 2979.64,
        "minimum": 1372.27,
        "maximum": 4878.08,
        "printed_average": 2979.63,
        "revenue": (0.00, 6705.81, 0.00, 6705.81),
        "revenue_counts": (0, 5, 0),
        "channels": (0, 0, 5, 0, 1, 0),
        "lenders": (1, 100.00, 0, 0.00),
        "insurance": (0, 0.00),
        "reversal_pairs": 0,
        "daily": [
            1552.27, 1372.27, 1372.27, 1372.27, 4778.08, 4838.08,
            2338.08, 2338.08, 2338.08, 2338.08, 2338.08, 2138.08,
            4738.08, 4738.08, 4878.08, 4878.08, 4878.08, 4878.08,
            4878.08, 2278.08, 2278.08, 2128.08, 2528.08, 2528.08,
            2528.08, 2528.08, 2528.08, 2528.08, 2528.08, 2028.08,
        ],
    },
    "navigant": {
        "bank": "Navigant Credit Union",
        "parser": "navigant-credit-union-deterministic",
        "account": "xxxxx8125",
        "period": ("2026-06-01", "2026-06-30"),
        "opening": 19207.58,
        "ending": -989.63,
        "transactions": 138,
        "credits": 150484.24,
        "effective_credits": 108982.74,
        "debits": 170681.45,
        "effective_debits": 129179.95,
        "daily_sum": 83100.46,
        "adb": 2770.02,
        "minimum": -989.63,
        "maximum": 15604.26,
        "printed_average": None,
        "revenue": (1543.85, 107438.89, 41501.50, 108982.74),
        "revenue_counts": (1, 19, 11),
        "channels": (1, 37, 30, 0, 20, 5),
        "lenders": (0, 0.00, 1, 1191.00),
        "insurance": (2, 1251.74),
        "reversal_pairs": 11,
        "daily": [
            3546.64, -112.55, -123.81, -971.28, -763.11, 7178.20,
            7178.20, 2442.61, 1466.96, 161.46, 28.98, -931.86,
            -931.86, -931.86, 895.37, -728.52, 63.22, 5955.29,
            5955.29, 3931.50, 3931.50, 353.41, 10353.41, 290.41,
            15604.26, 6498.26, 5914.99, 5914.99, 1919.99, -989.63,
        ],
    },
    "relay": {
        "bank": "Thread Bank (Relay)",
        "parser": "thread-bank-(relay)-deterministic",
        "account": "XXXXXX-7450",
        "period": ("2026-06-01", "2026-06-30"),
        "opening": 175.71,
        "ending": 0.70,
        "transactions": 176,
        "credits": 14799.79,
        "debits": 14974.80,
        "daily_sum": 3678.57,
        "adb": 122.62,
        "minimum": 0.00,
        "maximum": 1175.34,
        "printed_average": None,
        "revenue": (2020.00, 0.00, 12779.79, 2020.00),
        "revenue_counts": (2, 0, 49),
        "channels": (2, 8, 66, 9, 0, 0),
        "lenders": (0, 0.00, 0, 0.00),
        "insurance": (0, 0.00),
        "reversal_pairs": 9,
        "daily": [
            112.75, 0.75, 21.50, 1.50, 54.08, 0.08, 0.08, 0.08,
            0.08, 0.08, 485.41, 207.39, 302.53, 280.59, 74.25,
            56.24, 9.06, 278.05, 62.08, 0.00, 153.63, 2.00, 0.00,
            1175.34, 310.30, 57.28, 2.58, 2.58, 27.58, 0.70,
        ],
    },
}


CACHE = ROOT / "tests" / "corpus_cache"


def _source_markdown(name: str, *, live_ocr: bool = False) -> str:
    """Markdown for a fixture: native text, or its committed OCR artifact.

    `live_ocr=True` re-OCRs with the local Tesseract binary instead of reading
    the artifact. Only the `live`-marked parity test passes it; everything else
    reads the artifact so the asserted values cannot move with a tesseract
    upgrade. `cached_markdown` verifies the artifact against its manifest pin,
    so a tampered or mismatched artifact raises rather than quietly changing an
    assertion.
    """
    source = SOURCES[name]
    path = ROOT / source["path"]
    pdf_bytes = path.read_bytes()
    native = parse_native_pdf_text(pdf_bytes, source_file=path.name)
    if not source["ocr"]:
        assert native is not None
        return native.to_markdown()

    assert native is None
    if live_ocr:
        document = parse_local_tesseract(pdf_bytes, source_file=path.name)
        assert document is not None, f"local Tesseract produced nothing for {path.name}"
        return document.to_markdown()

    markdown = cached_markdown(pdf_bytes, CACHE)
    assert markdown is not None, f"no committed OCR artifact for {path.name}"
    return markdown


@lru_cache(maxsize=None)
def _source_report(name: str):
    return analyze_markdown(_source_markdown(name), parse_mode="deterministic")


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@pytest.mark.parametrize("name", SOURCES)
def test_new_source_inventory_is_exact(name: str):
    source = SOURCES[name]
    path = ROOT / source["path"]
    pdf_bytes = path.read_bytes()
    assert hashlib.sha256(pdf_bytes).hexdigest().upper() == source["sha256"]
    assert pdf_page_count(pdf_bytes) == source["pages"]


@pytest.mark.parametrize("name", [name for name, source in SOURCES.items() if source["ocr"]])
def test_scanned_fixtures_are_served_from_their_pinned_committed_artifact(name: str):
    """The OCR markdown these tests assert on is the pinned artifact, byte for byte."""
    source = SOURCES[name]
    pdf_bytes = (ROOT / source["path"]).read_bytes()
    entry = manifest_entries(CACHE)[source["sha256"]]

    assert entry["path"] == source["path"].split("Bank Statements/", 1)[1]
    assert entry["pdf_sha256"] == sha256_hex(pdf_bytes) == source["sha256"]

    markdown = _source_markdown(name)
    assert sha256_hex(markdown.encode("utf-8")) == entry["artifact_sha256"]
    assert markdown == (CACHE / entry["artifact"]).read_text(encoding="utf-8")


@pytest.mark.live
@pytest.mark.skipif(shutil.which("tesseract") is None, reason="local Tesseract not installed")
@pytest.mark.parametrize("name", [name for name, source in SOURCES.items() if source["ocr"]])
def test_live_tesseract_reproduces_the_committed_artifact_reports(name: str):
    """Opt-in: the real local-OCR path still produces the artifact's analysis.

    Deselected by default (`live` marker). A failure here is not necessarily a
    product regression — it means this machine's Tesseract has drifted from the
    build that produced the committed artifact, which is exactly the drift that
    took the GitHub runner red. Diagnose before re-baselining anything.
    """
    live = analyze_markdown(_source_markdown(name, live_ocr=True), parse_mode="deterministic")
    assert report_to_dict(live) == report_to_dict(_source_report(name))


@pytest.mark.parametrize("name", EXPECTED)
def test_new_statement_ledger_and_independent_daily_balances(name: str):
    expected = EXPECTED[name]
    report = _source_report(name)
    statement = report.statement
    metrics = report.metrics

    assert statement.bank == expected["bank"]
    assert report.model_used == expected["parser"]
    assert statement.account_number == expected["account"]
    assert (statement.period_start, statement.period_end) == expected["period"]
    assert statement.days_in_period == len(expected["daily"])
    assert len(statement.transactions) == expected["transactions"]
    assert statement.beginning_balance == expected["opening"]
    assert statement.ending_balance == expected["ending"]

    gross_credits = sum(
        (_money(transaction.amount) for transaction in statement.transactions if transaction.amount > 0),
        Decimal("0.00"),
    )
    gross_debits = -sum(
        (_money(transaction.amount) for transaction in statement.transactions if transaction.amount < 0),
        Decimal("0.00"),
    )
    assert gross_credits == _money(expected["credits"])
    assert gross_debits == _money(expected["debits"])
    assert _money(expected["opening"]) + gross_credits - gross_debits == _money(expected["ending"])
    assert report.reconciliation.ok
    assert report.reconciliation.continuity_breaks == 0

    independent_daily = [_money(value) for value in expected["daily"]]
    independent_sum = sum(independent_daily, Decimal("0.00"))
    independent_adb = (independent_sum / Decimal(len(independent_daily))).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    assert independent_sum == _money(expected["daily_sum"])
    assert independent_adb == _money(expected["adb"])
    assert [_money(day.ending_balance) for day in metrics.adb.daily_balances] == independent_daily
    assert metrics.daily_balance_sum == expected["daily_sum"]
    assert metrics.average_daily_balance == expected["adb"]
    assert metrics.min_balance == expected["minimum"]
    assert metrics.max_balance == expected["maximum"]
    assert metrics.adb_ok is True


@pytest.mark.parametrize("name", EXPECTED)
def test_new_statement_revenue_lender_and_transaction_metrics(name: str):
    expected = EXPECTED[name]
    report = _source_report(name)
    metrics = report.metrics

    verified, unverified, non_revenue, upper = expected["revenue"]
    verified_count, unverified_count, non_revenue_count = expected["revenue_counts"]
    assert (
        metrics.verified_revenue_total,
        metrics.unverified_deposit_total,
        metrics.non_revenue_total,
        metrics.maximum_revenue,
    ) == (verified, unverified, non_revenue, upper)
    assert (
        metrics.verified_revenue_count,
        metrics.unverified_deposit_count,
        metrics.non_revenue_count,
    ) == (verified_count, unverified_count, non_revenue_count)
    assert metrics.revenue_reconciles
    assert metrics.revenue_classified_total == metrics.total_posted_credits
    assert metrics.maximum_revenue == round(verified + unverified, 2)

    for transaction, classification in zip(report.statement.transactions, report.classifications):
        if transaction.amount <= 0 or not classification.is_posted:
            continue
        assert sum((
            classification.contributes_to_verified_revenue,
            classification.contributes_to_unverified_deposit,
            classification.contributes_to_non_revenue,
        )) == 1

    ach_credits, ach_debits, pos, atm, checks, nsf = expected["channels"]
    assert (
        metrics.ach_credit_count,
        metrics.ach_debit_count,
        metrics.pos_count,
        metrics.atm_withdrawal_count,
        metrics.check_count,
        metrics.nsf_count,
    ) == (ach_credits, ach_debits, pos, atm, checks, nsf)
    assert sum(
        classification.settlement_reversal
        for classification in report.classifications
    ) == expected["reversal_pairs"]

    lender_count, lender_total, potential_count, potential_total = expected["lenders"]
    assert (
        metrics.lender_debit_count,
        metrics.lender_debits,
        metrics.potential_lender_debit_count,
        metrics.potential_lender_debit_total,
    ) == (lender_count, lender_total, potential_count, potential_total)
    assert (metrics.insurance_count, metrics.insurance_total) == expected["insurance"]


def test_new_statement_printed_average_terminology_and_integrity():
    columbia = _source_report("columbia")
    first_farmers = _source_report("first_farmers")
    navigant = _source_report("navigant")
    relay = _source_report("relay")

    assert columbia.statement.stated_average_balance == 13275.65
    assert columbia.metrics.adb.validations["agrees_with_bank_stated_average"] is True
    assert first_farmers.statement.stated_average_balance == 2979.63
    assert first_farmers.metrics.average_daily_balance == 2979.64
    assert first_farmers.metrics.adb.validations["agrees_with_bank_stated_average"] is False
    assert navigant.statement.stated_average_balance is None
    assert relay.statement.stated_average_balance is None

    assert columbia.integrity.risk_level == "review"
    assert columbia.integrity.flags == ["missing_declared_statement_page"]
    assert not columbia.integrity.possible_document_issue
    for report in (first_farmers, navigant, relay):
        assert report.integrity.risk_level == "clear"
        assert not report.integrity.flags


def test_navigant_rejected_activity_reconciles_gross_ledger_and_settled_summary():
    report = _source_report("navigant")
    reconciliation = report.reconciliation
    metrics = report.metrics
    assert reconciliation.coverage_adjusted_for_reversals
    assert reconciliation.gross_credit_total == 150484.24
    assert reconciliation.gross_debit_total == 170681.45
    assert reconciliation.settled_credit_detail == 108982.74
    assert reconciliation.settled_debit_detail == 129179.95
    assert metrics.effective_total_deposits == 108982.74
    assert metrics.effective_total_withdrawals == 129179.95
    assert sum(record.settlement_reversal for record in report.classifications) == 11
    assert not any(
        record.contributes_to_potential_lender_totals and record.reversed_by
        for record in report.classifications
    )


def test_new_statement_api_and_exports_preserve_authoritative_values():
    payloads = {
        name: report_to_dict(_source_report(name))
        for name in EXPECTED
    }
    for name, payload in payloads.items():
        expected_adb = EXPECTED[name]["adb"]
        assert payload["metrics"]["average_daily_balance"] == expected_adb
        assert "average_daily_balance" not in payload["metrics"]["adb"]
        assert payload["metrics"]["revenue_reconciles"] is True

        csv_text = _analysis_csv(payload)
        assert f"metrics,average_daily_balance,{expected_adb}" in csv_text
        assert f"adb,daily_balance_sum,{EXPECTED[name]['daily_sum']}" in csv_text

        xlsx = _analysis_xlsx(payload)
        assert xlsx[:2] == b"PK"
        with zipfile.ZipFile(BytesIO(xlsx)) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "average_daily_balance" in sheet
        assert str(expected_adb) in sheet

    relay_payload = payloads["relay"]
    job = store.create("Relay Operations-June-2026.pdf")
    store.set_result(job.id, "source", "<p>source</p>", analysis=relay_payload)
    response = app.test_client().get(f"/analysis/{job.id}")
    assert response.status_code == 200
    assert response.get_json()["analysis"]["metrics"]["average_daily_balance"] == 122.62

    jobs = [
        Job(
            id=f"new-corpus-{name}",
            filename=Path(SOURCES[name]["path"]).name,
            status="done",
            analysis=payload,
        )
        for name, payload in payloads.items()
    ]
    package = _package_analysis(jobs)
    assert package["totals"]["average_daily_balance"] == 4857.14
    assert package["totals"]["verified_revenue_total"] == 101667.16
    assert package["totals"]["unverified_deposit_total"] == 119146.70
    assert package["totals"]["non_revenue_total"] == 98228.49
    assert package["totals"]["maximum_revenue"] == 220813.86
    assert [document["average_daily_balance"] for document in package["documents"]] == [
        13275.65,
        2979.64,
        2770.02,
        122.62,
    ]
    assert "totals,average_daily_balance,4857.14" in _package_csv(package)
    assert _package_xlsx(package)[:2] == b"PK"


def test_dashboard_uses_backend_adb_without_frontend_recalculation():
    javascript = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert "formatMoney(metrics.average_daily_balance" in javascript
    assert "metrics.average_daily_balance === null" in javascript
    assert "daily_balance_sum /" not in javascript
    assert "daily_balances.reduce" not in javascript
    assert "computeAverageDailyBalance" not in javascript
