"""CURRENCY DOCTRINE §F — the package layer never mixes currencies.

`webapp/app.py::_package_analysis` used to sum ADB (weighted), credits, debits,
revenue, lender and insurance money across a package's jobs with zero currency
awareness: `30,000 CAD + 20,000 USD` published as `50,000`. These tests pin the
three buckets and the exact shape of the refusal.

Measurement behind the design (read-only census of 26,096 analysis artifacts in
the archive's artifact store, PKG-CURRENCY 2026-08-20): every payload the
current pipeline produces declares a currency — 0 missing sections, 0 missing
keys, 0 nulls, 0 non-strings — across exactly two codes, USD 22,613 and CAD
3,483. `analysis/schema.py` gives `Statement.currency` a non-null "USD"
default, which is why the undetermined bucket is unreachable from a fresh
pipeline payload and reachable only from a legacy stored analysis (the D-1
SQLite store survives restarts and schema changes) or a hand-built payload.
The mixed bucket, by contrast, is reachable in production today: a package
combining a U.S. statement with a Canadian one is exactly the CAD/USD split the
census found.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from webapp.app import (
    _CROSS_CURRENCY_TOTAL_KEYS,
    _package_analysis,
    _package_csv,
    _package_rows,
    _package_xlsx,
    _statement_currency,
)
from webapp.jobs import Job

ROOT = Path(__file__).resolve().parents[1]

#: Every total the refusal must null. Spelled out here rather than imported so
#: that widening `_CROSS_CURRENCY_TOTAL_KEYS` without thinking fails a test.
EXPECTED_REFUSED_TOTALS = {
    "average_daily_balance",
    "avg_monthly_cash_flow",
    "avg_monthly_credits",
    "avg_monthly_debits",
    "cash_flow",
    "confirmed_true_revenue",
    "confirmed_true_revenue_total",
    "eligible_deposits",
    "insurance_total",
    "lender_debits",
    "maximum_revenue",
    "monthly_lender_debits",
    "non_revenue_total",
    "package_withholding_rate",
    "package_withholding_rate_raw",
    "potential_lender_debit_total",
    "potential_lender_debits",
    "potential_revenue_total",
    "potential_withholding_denominator",
    "potential_withholding_exposure",
    "potential_withholding_exposure_raw",
    "potential_withholding_numerator",
    "revenue_classified_total",
    "revenue_reconciliation_delta",
    "total_credits",
    "total_debits",
    "total_posted_credits",
    "true_revenue",
    "unverified_deposit_total",
    "verified_revenue_total",
    "withholding_denominator",
    "withholding_numerator",
}

#: Totals that count things rather than measure money. A count is unit-free, so
#: a currency refusal must leave every one of them intact — an underwriter still
#: needs to know how many statements failed and how many NSFs there were.
UNIT_FREE_TOTALS = {
    "approved",
    "completed",
    # The 3.0 deprecated count aliases are counts too.
    "confirmed_true_revenue_count",
    "potential_revenue_count",
    "distinct_documents",
    "documents",
    "duplicate_documents",
    "failed",
    "insurance_count",
    "integrity_high",
    "integrity_review",
    "lender_debit_count",
    "lenders_detected",
    "manual_review",
    "months",
    "non_revenue_count",
    "nsf_count",
    "potential_lender_debit_count",
    "potential_lenders_detected",
    "revenue_classified_count",
    "summary_only",
    "total_posted_credit_count",
    "unverified_deposit_count",
    "verified_revenue_count",
}


def statement_payload(currency, *, amount=10_000.0, adb=100.0, days=31, bank="Test Bank"):
    """A minimal but complete package member. `currency` may be a code, None to
    store an explicit null, or the sentinel `DROP` to omit the key entirely."""
    statement = {
        "bank": bank,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "transactions": [],
    }
    if currency is not DROP:
        statement["currency"] = currency
    return {
        "statement": statement,
        "metrics": {
            "effective_total_deposits": amount,
            "effective_total_withdrawals": amount / 2,
            "cash_flow": amount / 2,
            "average_daily_balance": adb,
            "adb_ok": True,
            "calendar_day_count": days,
            "withholding_denominator": amount,
            "lender_debits": 250.0,
            "withholding_numerator": 250.0,
            "insurance_total": 40.0,
            "insurance_count": 1,
        },
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {"known_funders": [{"funder": "ONDECK", "total_debited": 250.0}]},
    }


class _Drop:
    def __repr__(self):  # pragma: no cover - debugging aid only
        return "DROP"


DROP = _Drop()


def member(job_id, currency, **kwargs):
    return Job(
        id=job_id,
        filename=f"{job_id}.pdf",
        status="done",
        analysis=statement_payload(currency, **kwargs),
        content_sha256=job_id,
    )


# ---------------------------------------------------------------------------
# The currency reader
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("USD", "USD"),
        ("CAD", "CAD"),
        # ISO 4217 codes are uppercase, so case is a spelling of the same unit.
        # Refusing a package over a spelling would be a FALSE refusal.
        ("usd", "USD"),
        ("  cad  ", "CAD"),
        # No unit was declared at all.
        ("", None),
        ("   ", None),
        (None, None),
        (7, None),
    ],
)
def test_statement_currency_reads_or_refuses(raw, expected):
    assert _statement_currency({"statement": {"currency": raw}}) == expected


def test_statement_currency_of_a_payload_with_no_statement_is_unknown():
    assert _statement_currency({}) is None
    assert _statement_currency({"statement": None}) is None
    assert _statement_currency({"statement": {}}) is None


# ---------------------------------------------------------------------------
# Bucket 1 — same currency aggregates exactly as before
# ---------------------------------------------------------------------------


def test_same_currency_package_aggregates_and_is_denominated_once():
    package = _package_analysis([member("a", "CAD"), member("b", "CAD")])
    totals = package["totals"]

    assert totals["total_credits"] == 20_000.0
    assert totals["average_daily_balance"] == 100.0
    assert totals["cross_currency_totals_refused"] is False
    assert totals["currency_refusal_reason"] is None
    # Doctrine D: ONE denominated figure, the code surfaced once.
    assert totals["currency"] == "CAD"
    assert totals["currency_resolution"] == "single"
    assert package["currency"] == {
        "resolution": "single",
        "currency": "CAD",
        "currencies": ["CAD"],
        "documents_by_currency": {"CAD": 2},
        "undeclared_currency_documents": 0,
        "cross_currency_totals_refused": False,
        "refusal_reason": None,
        "refused_total_fields": [],
    }


def test_currency_case_does_not_split_a_single_currency_package():
    lower = _package_analysis([member("a", "usd"), member("b", "USD")])
    upper = _package_analysis([member("a", "USD"), member("b", "USD")])
    assert lower["totals"] == upper["totals"]
    assert lower["totals"]["currency"] == "USD"


def test_a_member_that_never_analyzed_carries_no_currency_and_no_money():
    """A failed member contributes zero to every money total, so it carries no
    unit and must not be able to refuse an otherwise single-currency package."""
    failed = Job(id="x", filename="x.pdf", status="error", analysis=None, content_sha256="x")
    package = _package_analysis([member("a", "USD"), failed])
    totals = package["totals"]

    assert totals["currency"] == "USD"
    assert totals["cross_currency_totals_refused"] is False
    assert totals["total_credits"] == 10_000.0
    assert totals["failed"] == 1
    assert package["documents"][1]["currency"] is None


def test_a_package_with_no_analyzed_member_refuses_nothing():
    failed = [
        Job(id="x", filename="x.pdf", status="error", analysis=None, content_sha256="x"),
        Job(id="y", filename="y.pdf", status="error", analysis=None, content_sha256="y"),
    ]
    package = _package_analysis(failed)
    totals = package["totals"]

    # Every total is a structural zero over an empty set: there is no unit to
    # protect, so refusing here would invent a problem rather than report one.
    assert totals["currency_resolution"] == "no_analyzed_documents"
    assert totals["cross_currency_totals_refused"] is False
    assert totals["total_credits"] == 0.0


# ---------------------------------------------------------------------------
# Bucket 2 — mixed currencies refuse every cross-currency figure
# ---------------------------------------------------------------------------


def test_mixed_currency_package_refuses_every_cross_currency_total():
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    totals = package["totals"]

    assert totals["currency"] is None
    assert totals["currency_resolution"] == "mixed"
    assert totals["cross_currency_totals_refused"] is True
    assert totals["currency_refusal_reason"] == "multiple_currencies"
    assert package["currency"]["currencies"] == ["CAD", "USD"]
    assert package["currency"]["documents_by_currency"] == {"CAD": 1, "USD": 1}

    for key in EXPECTED_REFUSED_TOTALS:
        assert totals[key] is None, f"{key} was published for a mixed package"

    # 30,000 CAD + 20,000 USD != 50,000. Nothing may be silently summed...
    assert totals["total_credits"] is None
    # ...and nothing may be silently zeroed either.
    assert totals["total_credits"] != 0
    assert totals["total_credits"] != 0.0


def test_mixed_currency_refusal_leaves_every_count_intact():
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    totals = package["totals"]
    for key in UNIT_FREE_TOTALS:
        assert totals[key] is not None, f"{key} is unit-free and must survive"
    assert totals["documents"] == 2
    assert totals["completed"] == 2
    assert totals["insurance_count"] == 2


def test_mixed_currency_refusal_fails_derived_judgements_closed():
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    totals = package["totals"]
    # A judgement read off a refused figure must never read as a pass.
    assert totals["revenue_reconciles"] is False
    assert totals["withholding_review_required"] is True
    assert totals["decision"] == "review_required"


def test_mixed_currency_refusal_covers_the_cross_document_rollups():
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    assert package["funders"], "the fixture must produce a funder rollup"
    for funder in package["funders"]:
        assert funder["total_debited"] is None
        # The count of documents the funder appears in is unit-free.
        assert funder["documents"] == 2


def test_statement_level_results_survive_a_mixed_currency_refusal():
    """Doctrine F preserves statement-level results and presents them per
    currency; only the cross-currency combination is refused."""
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    documents = package["documents"]

    assert [doc["currency"] for doc in documents] == ["CAD", "USD"]
    assert [doc["credits"] for doc in documents] == [10_000.0, 10_000.0]
    assert [doc["average_daily_balance"] for doc in documents] == [100.0, 100.0]
    assert [doc["cash_flow"] for doc in documents] == [5_000.0, 5_000.0]
    assert [row["currency"] for row in package["monthly"]] == ["CAD", "USD"]


def test_no_conversion_is_ever_fabricated():
    """A converted number would be evidence nobody produced. The refusal path
    must not contain a rate, a converted figure, or a normalized total."""
    package = _package_analysis([member("a", "CAD", amount=30_000.0), member("b", "USD", amount=20_000.0)])
    blob = json.dumps(package)
    assert "50000" not in blob and "50,000" not in blob
    assert "exchange_rate" not in blob
    assert "converted" not in blob
    # The doctrine's own counter-example must not appear at any precision.
    assert package["totals"]["total_credits"] is None


def test_three_currencies_refuse_and_enumerate_all_three():
    package = _package_analysis(
        [member("a", "CAD"), member("b", "USD"), member("c", "EUR")]
    )
    assert package["currency"]["currencies"] == ["CAD", "EUR", "USD"]
    assert package["totals"]["cross_currency_totals_refused"] is True


# ---------------------------------------------------------------------------
# Bucket 3 — an undeclared currency fails the package closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("undeclared", [DROP, None, "", "   "])
def test_a_member_without_a_declared_currency_fails_the_package_closed(undeclared):
    """Doctrine B: genuinely uncertain evidence fails closed rather than being
    forced into a currency. An unknown must not join a same-currency pool as if
    proven — it could be the CAD that breaks the USD total."""
    package = _package_analysis([member("a", "USD"), member("b", undeclared)])
    totals = package["totals"]

    assert totals["currency"] is None
    assert totals["currency_resolution"] == "undetermined"
    assert totals["cross_currency_totals_refused"] is True
    assert totals["currency_refusal_reason"] == "undetermined_statement_currency"
    assert package["currency"]["undeclared_currency_documents"] == 1
    # The one code that WAS declared is still reported as evidence.
    assert package["currency"]["currencies"] == ["USD"]
    assert totals["total_credits"] is None
    assert totals["decision"] == "review_required"


def test_an_undeclared_member_alone_still_fails_closed():
    package = _package_analysis([member("only", DROP)])
    assert package["totals"]["currency_resolution"] == "undetermined"
    assert package["totals"]["average_daily_balance"] is None


def test_the_undetermined_bucket_is_not_reachable_from_a_pipeline_payload():
    """The schema default is why: `Statement.currency` is non-null, so a fresh
    payload always declares a code. This pins the reason the bucket exists (a
    legacy stored analysis) rather than letting it look like dead code."""
    from analysis.schema import Statement

    field = Statement.model_fields["currency"]
    assert field.default == "USD"
    assert _statement_currency({"statement": Statement().model_dump()}) == "USD"


# ---------------------------------------------------------------------------
# Consumers: no consumer may receive a mixed-unit number
# ---------------------------------------------------------------------------


def test_refused_field_list_matches_the_constant_and_the_payload():
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    assert set(_CROSS_CURRENCY_TOTAL_KEYS) == EXPECTED_REFUSED_TOTALS
    assert package["currency"]["refused_total_fields"] == sorted(EXPECTED_REFUSED_TOTALS)


def test_csv_export_carries_the_refusal_and_never_a_mixed_number():
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    text = _package_csv(package)
    rows = list(csv.reader(io.StringIO(text)))
    cells = {(row[0], row[1]): row[2] for row in rows[1:] if len(row) == 3}

    assert cells[("currency", "resolution")] == "mixed"
    assert cells[("currency", "cross_currency_totals_refused")] == "True"
    assert cells[("currency", "refusal_reason")] == "multiple_currencies"
    # A refused total is an empty cell, never a number an analyst could add up.
    for key in EXPECTED_REFUSED_TOTALS:
        assert cells[("totals", key)] == "", f"totals.{key} leaked into the CSV"
    # Statement-level rows keep their own denomination.
    assert cells[("document_1", "currency")] == "CAD"
    assert cells[("document_2", "currency")] == "USD"


def test_csv_export_of_a_single_currency_package_states_the_denomination():
    package = _package_analysis([member("a", "CAD"), member("b", "CAD")])
    text = _package_csv(package)
    assert "totals,currency,CAD" in text
    assert "currency,resolution,single" in text
    assert "totals,total_credits,20000.0" in text


def test_xlsx_export_carries_the_same_refusal():
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    blob = _package_xlsx(package)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "multiple_currencies" in sheet
    assert "cross_currency_totals_refused" in sheet


def test_every_money_row_the_export_emits_is_covered_by_a_declared_currency():
    """The structural guarantee: for a refused package, no `totals` row in the
    export holds a number. Anything numeric there would be a mixed unit."""
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    numeric = []
    for section, field, value in _package_rows(package):
        if section != "totals":
            continue
        # A bool is a flag, not a quantity — and `float(False)` succeeds, so it
        # has to be excluded explicitly or every flag reads as money.
        if isinstance(value, bool):
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            continue
        numeric.append((field, value))
    for field, value in numeric:
        assert field in UNIT_FREE_TOTALS, (
            f"totals.{field} = {value!r} is a number in a refused package but is "
            "not on the unit-free list"
        )


def test_version_3_deprecated_aliases_degrade_with_their_canonical_names():
    """The 3.0 aliases carry the identical number, so they must carry the
    identical refusal — an old consumer must not be the one that still gets a
    mixed total."""
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    totals = package["totals"]
    for alias, canonical in (
        ("true_revenue", "verified_revenue_total"),
        ("confirmed_true_revenue", "verified_revenue_total"),
        ("confirmed_true_revenue_total", "verified_revenue_total"),
        ("potential_revenue_total", "unverified_deposit_total"),
        ("potential_lender_debits", "potential_lender_debit_total"),
        ("monthly_lender_debits", "lender_debits"),
    ):
        assert totals[alias] == totals[canonical] is None


def test_package_ledger_rows_carry_their_own_source_currency():
    """The combined ledger interleaves rows from every member, so a package-wide
    label would mislabel every row of a mixed package."""
    cad = member("a", "CAD")
    cad.analysis["statement"]["transactions"] = [
        {"date": "2026-01-02", "description": "Deposit", "amount": 100.0, "direction": "credit"}
    ]
    usd = member("b", "USD")
    usd.analysis["statement"]["transactions"] = [
        {"date": "2026-01-03", "description": "Deposit", "amount": 200.0, "direction": "credit"}
    ]
    package = _package_analysis([cad, usd])
    assert [tx["source_currency"] for tx in package["transactions"]] == ["CAD", "USD"]


# ---------------------------------------------------------------------------
# The dashboard
# ---------------------------------------------------------------------------


def test_dashboard_no_longer_hardcodes_usd_for_the_package_view():
    javascript = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    # The three package render call sites used to pass a literal "USD".
    assert 'renderLenders(funders, potentialLenders, "USD")' not in javascript
    assert 'renderInsurance(insuranceProviders, "USD")' not in javascript
    assert 'renderRevenueEvidence(pkg.totals || {}, "USD")' not in javascript
    # ...and the combined ledger hardcoded it too.
    assert 'currency: "USD",\n      multi: true,' not in javascript
    assert "packageCurrencyInfo(pkg).currency" in javascript
    # The refusal has to reach the analyst, not just the JSON.
    assert "CURRENCY_REFUSAL_COPY" in javascript
    assert "multiple_currencies" in javascript
    assert "undetermined_statement_currency" in javascript
    # An undeclared currency must not be printed as dollars.
    assert "if (!currency) return amount;" in javascript
