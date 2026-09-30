"""CURRENCY DOCTRINE §F — the package layer never mixes currencies.

`webapp/app.py::_package_analysis` used to sum ADB (weighted), credits, debits,
revenue, lender and insurance money across a package's jobs with zero currency
awareness: `30,000 CAD + 20,000 USD` published as `50,000`. These tests pin the
three buckets and the exact shape of the refusal.

Measurement behind the design (read-only census of 26,096 analysis artifacts in
the archive's artifact store, PKG-CURRENCY 2054-08-20): every payload the
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
import re
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
from analysis.flag_groups import FLAG_GROUPS
from webapp.jobs import Job
from tests.flagged_payloads import FLAGGED_DEBIT, flagged_row, with_flagged_rows

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
    "flagged_position_total",
    "flagged_position_total_credited",
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
    # 5.6 (true revenue spec §9.2): True revenue and its counted and held parts.
    "true_revenue_total",
    "counted_flagged_total",
    "excluded_pending_review_total",
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
    "flagged_position_count",
    "flagged_position_count_credited",
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
    # 5.6 (§9.2): the tier counts and the held-row count.
    "true_revenue_count",
    "counted_flagged_count",
    "excluded_pending_review_count",
    "revenue_review_items",
}
#: 5.6 (§9.2, §10.4): the tier counts are unit-free, and None whenever a completed member's revenue is not
#: established, as every metrics-only member of these fixtures is.
REVENUE_TIER_COUNTS = {"true_revenue_count", "counted_flagged_count", "excluded_pending_review_count"}


def statement_payload(currency, *, amount=10_000.0, adb=100.0, days=31, bank="Test Bank"):
    """A minimal but complete package member. `currency` may be a code, None to
    store an explicit null, or the sentinel `DROP` to omit the key entirely."""
    statement = {
        "bank": bank,
        "period_start": "2054-01-01",
        "period_end": "2054-01-31",
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
        # All THREE rollup kinds, so the export sweep below is never vacuous:
        # the alias that escaped the refusal lived on a potential-lender rollup.
        "detection": {
            "known_funders": [
                {"funder": "ONDECK", "total_debited": 250.0, "debit_count": 2}
            ],
            "potential_lenders": [
                {"funder": "RAPID CAPITAL", "total_debited": 500.0, "debit_count": 3}
            ],
            "insurance_providers": [
                {"provider": "ACME INSURANCE", "total_debited": 40.0, "count": 1}
            ],
        },
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
    for key in UNIT_FREE_TOTALS - REVENUE_TIER_COUNTS:
        assert totals[key] is not None, f"{key} is unit-free and must survive"
    # The members print no ledger rows, so their revenue is not established and the tier counts are N/A (§10.4);
    # the currency refusal is not what nulls them.
    for key in REVENUE_TIER_COUNTS:
        assert totals[key] is None
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


def test_the_deprecated_rollup_alias_is_refused_with_its_canonical_key():
    """BLOCK-1 regression. `_package_analysis` assigns
    `potential_lender_debit_total = total_debited` on every potential-lender
    rollup, and the dashboard reads
    `potential_lender_debit_total ?? total_debited` — alias FIRST. Refusing only
    the canonical key left the mixed number in the JSON, the CSV, the XLSX and
    the rendered row, defeating the refusal exactly where it was designed to
    bite."""
    package = _package_analysis(
        [member("a", "CAD", amount=10_000.0), member("b", "USD", amount=20_000.0)]
    )
    assert package["potential_lenders"], "the fixture must produce a rollup"
    for item in package["potential_lenders"]:
        assert item["total_debited"] is None
        assert item["potential_lender_debit_total"] is None
        # The dashboard's own accessor chain must not find a number either.
        assert (item["potential_lender_debit_total"] or item["total_debited"]) is None
        # Counts are unit-free and must survive.
        assert item["documents"] == 2
        assert item["potential_lender_debit_count"] == item["debit_count"]

    text = _package_csv(package)
    assert "potential_lender_1,potential_lender_debit_total," in text
    assert "1500.0" not in text  # 500 CAD + 500 USD, had it been summed


def test_refused_packages_do_not_rank_rollups_by_a_cross_currency_magnitude():
    """MINOR-1 (Ocean's ruling). Ranking by summed money publishes a
    cross-currency comparison; nulling the figures afterwards leaves that
    assertion standing in the ROW ORDER, unauditable because the numbers behind
    it are gone. A refused package ranks by count, then name."""
    small_cad = member("a", "CAD")
    small_cad.analysis["detection"]["known_funders"] = [
        # Biggest magnitude, fewest debits.
        {"funder": "ZZZ BIG MONEY", "total_debited": 900_000.0, "debit_count": 1}
    ]
    big_usd = member("b", "USD")
    big_usd.analysis["detection"]["known_funders"] = [
        {"funder": "AAA MANY DEBITS", "total_debited": 5.0, "debit_count": 40}
    ]

    refused = _package_analysis([small_cad, big_usd])
    assert refused["totals"]["cross_currency_totals_refused"] is True
    # Count descending, so the 40-debit lender leads — NOT the 900,000 one,
    # whose lead would have been a CAD-vs-USD comparison.
    assert [f["funder"] for f in refused["funders"]] == [
        "AAA MANY DEBITS",
        "ZZZ BIG MONEY",
    ]

    # The same two lenders in ONE currency keep today's magnitude order exactly.
    same_a = member("a", "CAD")
    same_a.analysis["detection"]["known_funders"] = [
        {"funder": "ZZZ BIG MONEY", "total_debited": 900_000.0, "debit_count": 1}
    ]
    same_b = member("b", "CAD")
    same_b.analysis["detection"]["known_funders"] = [
        {"funder": "AAA MANY DEBITS", "total_debited": 5.0, "debit_count": 40}
    ]
    single = _package_analysis([same_a, same_b])
    assert single["totals"]["cross_currency_totals_refused"] is False
    assert [f["funder"] for f in single["funders"]] == [
        "ZZZ BIG MONEY",
        "AAA MANY DEBITS",
    ]


def test_potential_lender_order_is_unit_free_in_both_cases():
    """Measured correction to the ruling's premise: `potential_lenders` was
    already sorted by NAME, never by a magnitude, so its order never asserted a
    cross-currency comparison and is deliberately left unchanged."""
    refused = _package_analysis([member("a", "CAD"), member("b", "USD")])
    single = _package_analysis([member("a", "CAD"), member("b", "CAD")])
    names = [item["funder"] for item in refused["potential_lenders"]]
    assert names == sorted(names)
    assert names == [item["funder"] for item in single["potential_lenders"]]


def test_mixed_currency_refusal_covers_the_flag_roll_up():
    """Lender detection §8.3. The flag roll-up sums money across members exactly as the funder roll-up does, so
    a refused package publishes its counts and none of its money."""
    cad, usd = member("a", "CAD"), member("b", "USD")
    with_flagged_rows(cad.analysis, [flagged_row("credit_cards")])
    with_flagged_rows(usd.analysis, [flagged_row("credit_cards")])
    package = _package_analysis([cad, usd])
    assert package["totals"]["flagged_position_total"] is None
    assert package["totals"]["flagged_position_count"] == 2
    [item] = package["flagged_positions"]["credit_cards"]
    assert item["total_debited"] is None
    assert (item["documents"], item["count"]) == (2, 2)


def test_refused_packages_rank_flagged_positions_by_count_then_payee():
    """MINOR-1's rule, applied to the flag roll-up: no row order read off a cross-currency magnitude."""
    def build(first_currency, second_currency):
        big = member("a", first_currency)
        with_flagged_rows(big.analysis, [flagged_row("mortgages", payee="ZZZ FABRICATED BIG",
                                                     amount=-100 * FLAGGED_DEBIT)])
        many = member("b", second_currency)
        with_flagged_rows(many.analysis, [flagged_row("mortgages", payee="AAA FABRICATED MANY") for _ in range(3)])
        return _package_analysis([big, many])

    refused = build("CAD", "USD")
    assert [item["payee"] for item in refused["flagged_positions"]["mortgages"]] == [
        "AAA FABRICATED MANY", "ZZZ FABRICATED BIG"]
    single = build("CAD", "CAD")
    assert [item["payee"] for item in single["flagged_positions"]["mortgages"]] == [
        "ZZZ FABRICATED BIG", "AAA FABRICATED MANY"]
    assert single["totals"]["flagged_position_count"] == 4
    assert single["totals"]["flagged_position_total"] == 103 * FLAGGED_DEBIT


def test_mixed_currency_refusal_covers_the_credited_flag_roll_up():
    """C6 and the owner's ruling of 2026-09-26: a factor's payouts roll up as credited money, refused exactly as
    the debited money is, while both counts survive."""
    cad, usd = member("a", "CAD"), member("b", "USD")
    for job in (cad, usd):
        with_flagged_rows(job.analysis, [flagged_row("factoring"), flagged_row("factoring", amount=3 * FLAGGED_DEBIT)])
    package = _package_analysis([cad, usd])
    totals = package["totals"]
    assert (totals["flagged_position_total"], totals["flagged_position_total_credited"]) == (None, None)
    assert (totals["flagged_position_count"], totals["flagged_position_count_credited"]) == (2, 2)
    [item] = package["flagged_positions"]["factoring"]
    assert (item["total_debited"], item["total_credited"]) == (None, None)
    assert (item["documents"], item["count"], item["count_credited"]) == (2, 2, 2)


def test_refused_packages_rank_flagged_positions_by_debits_plus_credits():
    """A refused package ranks by the unit-free count, debits plus credits, never by money."""
    def build(first_currency, second_currency):
        paid = member("a", first_currency)
        with_flagged_rows(paid.analysis, [flagged_row("factoring", payee="ZZZ FABRICATED PAID",
                                                      amount=-100 * FLAGGED_DEBIT) for _ in range(2)])
        paying = member("b", second_currency)
        with_flagged_rows(paying.analysis, [flagged_row("factoring", payee="AAA FABRICATED PAYING",
                                                        amount=FLAGGED_DEBIT) for _ in range(3)])
        return _package_analysis([paid, paying])

    refused = build("CAD", "USD")
    assert [(item["payee"], item["count"], item["count_credited"])
            for item in refused["flagged_positions"]["factoring"]] == [
        ("AAA FABRICATED PAYING", 0, 3), ("ZZZ FABRICATED PAID", 2, 0)]
    single = build("CAD", "CAD")
    assert [item["payee"] for item in single["flagged_positions"]["factoring"]] == [
        "ZZZ FABRICATED PAID", "AAA FABRICATED PAYING"]


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


def test_the_corpus_gate_package_surface_survives_a_refusal():
    """`corpus_gate.py` -> `balance_forensic_audit.apply_package_results` reads
    FOUR per-document balance fields off `_package_analysis`, plus the same four
    out of the CSV and XLSX at `document_N`. All four are statement-level, so a
    currency refusal must leave every one of them — and the export's key-based
    `(section, field)` addressing — completely intact.

    This consumer was not in the first pass of the census; it is pinned here so
    the omission cannot recur silently."""
    from balance_forensic_audit import csv_rows, surface_value, xlsx_rows

    cad = member("a", "CAD")
    cad.analysis["statement"]["beginning_balance"] = 500.0
    cad.analysis["statement"]["ending_balance"] = 900.0
    cad.analysis["metrics"]["min_balance"] = 250.0
    cad.analysis["metrics"]["max_balance"] = 1200.0
    cad.analysis["reconciliation"] = {"ok": True}
    usd = member("b", "USD")
    usd.analysis["statement"]["beginning_balance"] = 900.0
    usd.analysis["statement"]["ending_balance"] = 1100.0
    usd.analysis["metrics"]["min_balance"] = 700.0
    usd.analysis["metrics"]["max_balance"] = 1500.0
    usd.analysis["reconciliation"] = {"ok": True}

    package = _package_analysis([cad, usd])
    assert package["totals"]["cross_currency_totals_refused"] is True

    first, second = package["documents"]
    assert (first["beginning_balance"], first["ending_balance"]) == (500.0, 900.0)
    assert (first["min_balance"], first["max_balance"]) == (250.0, 1200.0)
    assert (second["beginning_balance"], second["ending_balance"]) == (900.0, 1100.0)
    assert (second["min_balance"], second["max_balance"]) == (700.0, 1500.0)

    # The exports address by (section, field), never by row position, so the
    # added `currency` section and `currency` column cannot shift them.
    from webapp.app import _package_csv as pkg_csv, _package_xlsx as pkg_xlsx

    for reader, blob in ((csv_rows, pkg_csv(package)), (xlsx_rows, pkg_xlsx(package))):
        rows = reader(blob)
        assert surface_value(rows, "document_1", "beginning_balance") == "500.0"
        assert surface_value(rows, "document_1", "max_balance") == "1200.0"
        assert surface_value(rows, "document_2", "ending_balance") == "1100.0"
        assert surface_value(rows, "document_2", "min_balance") == "700.0"


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


#: Sections that aggregate ACROSS documents. Matched exactly so that
#: `potential_lender_evidence_3` — a per-transaction classification record, and
#: therefore statement-level — is not mistaken for the `potential_lender_3`
#: rollup. The flag roll-up (`flagged_<group>_<n>`, lender detection §8.4) is
#: named group by group for the same reason.
CROSS_DOCUMENT_SECTION = re.compile(
    r"^(totals|funder_\d+|potential_lender_\d+|insurance_provider_\d+"
    r"|flagged_(?:" + "|".join(group.key for group in FLAG_GROUPS) + r")_\d+)$"
)

#: Counts that live on the cross-document rollups.
UNIT_FREE_ROLLUP_KEYS = {
    "count",
    "count_credited",
    "debit_count",
    "documents",
    "potential_lender_debit_count",
}


def test_every_money_row_the_export_emits_is_covered_by_a_declared_currency():
    """The structural guarantee, across EVERY export section.

    A refused package has no declared currency, so nothing that aggregates
    across documents may still publish a number — a surviving one is a mixed
    unit by definition. This is deliberately not scoped to `totals`: the
    rollups are just as cross-document, and `potential_lender_debit_total`
    (the deprecated alias of `total_debited`) escaped exactly that way.

    Statement-level sections DO carry money and keep it. Their obligation is
    different: each must DECLARE the unit it is in, so that no consumer can
    assume dollars.
    """
    cad, usd = member("a", "CAD"), member("b", "USD")
    for job in (cad, usd):
        # A flag roll-up in the refused package, so the flagged sections are swept too: a debit, and a factoring
        # credit, whose credited count and total are swept as the debited ones are (C6, owner ruling 2026-09-26).
        with_flagged_rows(job.analysis, [flagged_row("credit_cards"),
                                         flagged_row("factoring", amount=3 * FLAGGED_DEBIT)])
    package = _package_analysis([cad, usd])
    rows = _package_rows(package)
    assert package["totals"]["cross_currency_totals_refused"] is True

    offenders = []
    for section, field, value in rows:
        if not CROSS_DOCUMENT_SECTION.match(section):
            continue
        # A bool is a flag, not a quantity — and `float(False)` succeeds, so it
        # has to be excluded explicitly or every flag reads as money.
        if isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if field in UNIT_FREE_TOTALS or field in UNIT_FREE_ROLLUP_KEYS:
            continue
        offenders.append(f"{section}.{field} = {number!r}")

    assert offenders == [], (
        "a refused package still publishes cross-document number(s) that are "
        f"not counts, i.e. mixed units: {offenders}"
    )

    # Every rollup section really was exercised — otherwise the sweep above
    # would pass vacuously and the alias could regress unnoticed.
    exercised = {
        section for section, _, _ in rows if CROSS_DOCUMENT_SECTION.match(section)
    }
    assert "totals" in exercised
    assert any(s.startswith("funder_") for s in exercised)
    assert any(s.startswith("potential_lender_") for s in exercised)
    assert any(s.startswith("insurance_provider_") for s in exercised)
    assert any(s.startswith("flagged_credit_cards_") for s in exercised)
    assert ("flagged_factoring_1", "total_credited", "") in rows
    assert ("flagged_factoring_1", "count_credited", 2) in rows

    # Statement-level sections keep their money and declare their unit.
    document_sections = {s for s, _, _ in rows if s.startswith("document_")}
    assert document_sections
    for section in document_sections:
        declared = [f for s, f, _ in rows if s == section and f == "currency"]
        assert declared, f"{section} publishes figures without declaring a currency"


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
        {"date": "2054-01-02", "description": "Deposit", "amount": 100.0, "direction": "credit"}
    ]
    usd = member("b", "USD")
    usd.analysis["statement"]["transactions"] = [
        {"date": "2054-01-03", "description": "Deposit", "amount": 200.0, "direction": "credit"}
    ]
    package = _package_analysis([cad, usd])
    assert [tx["source_currency"] for tx in package["transactions"]] == ["CAD", "USD"]


def test_the_route_serves_the_refusal_through_masking_and_json():
    """`/package_analysis` runs the payload through `_masked` and `jsonify`.
    Neither may turn a refusal back into a number, and neither may drop the
    block that explains it."""
    from webapp.app import app, store

    ids = []
    for name, code in (("cad.pdf", "CAD"), ("usd.pdf", "USD")):
        job = store.create(name)
        store.set_result(job.id, f"# {name}", f"<h1>{name}</h1>", analysis=statement_payload(code))
        ids.append(job.id)

    response = app.test_client().get(f"/package_analysis?ids={','.join(ids)}")
    assert response.status_code == 200
    body = response.get_json()

    assert body["currency"]["resolution"] == "mixed"
    assert body["currency"]["documents_by_currency"] == {"CAD": 1, "USD": 1}
    assert body["totals"]["cross_currency_totals_refused"] is True
    assert body["totals"]["total_credits"] is None
    assert body["totals"]["average_daily_balance"] is None
    assert body["totals"]["decision"] == "review_required"
    # Statement-level results still served, still denominated.
    assert sorted(doc["currency"] for doc in body["documents"]) == ["CAD", "USD"]


def test_the_route_serves_the_undetermined_bucket_end_to_end():
    """MINOR-3. The fail-closed bucket was only ever exercised in-process; this
    pins it through the real route, masking and JSON serialization."""
    from webapp.app import app, store

    ids = []
    for name, code in (("proven.pdf", "USD"), ("legacy.pdf", DROP)):
        job = store.create(name)
        store.set_result(job.id, f"# {name}", f"<h1>{name}</h1>", analysis=statement_payload(code))
        ids.append(job.id)

    response = app.test_client().get(f"/package_analysis?ids={','.join(ids)}")
    assert response.status_code == 200
    body = response.get_json()

    assert body["currency"]["resolution"] == "undetermined"
    assert body["currency"]["refusal_reason"] == "undetermined_statement_currency"
    assert body["currency"]["undeclared_currency_documents"] == 1
    # The code that WAS declared is still reported as evidence.
    assert body["currency"]["currencies"] == ["USD"]
    assert len(body["currency"]["refused_total_fields"]) == 37
    assert body["totals"]["cross_currency_totals_refused"] is True
    assert body["totals"]["currency"] is None
    assert body["totals"]["total_credits"] is None
    assert body["totals"]["average_daily_balance"] is None
    assert body["totals"]["decision"] == "review_required"
    # The undeclared member is served honestly, not backfilled to USD.
    assert sorted(
        (doc["currency"] is None) for doc in body["documents"]
    ) == [False, True]
    for item in body["potential_lenders"]:
        assert item["total_debited"] is None
        assert item["potential_lender_debit_total"] is None


def test_the_route_denominates_a_single_currency_package():
    from webapp.app import app, store

    ids = []
    for name in ("jan.pdf", "feb.pdf"):
        job = store.create(name)
        store.set_result(job.id, f"# {name}", f"<h1>{name}</h1>", analysis=statement_payload("CAD"))
        ids.append(job.id)

    body = app.test_client().get(f"/package_analysis?ids={','.join(ids)}").get_json()
    assert body["totals"]["currency"] == "CAD"
    assert body["totals"]["total_credits"] == 20_000.0
    assert body["totals"]["cross_currency_totals_refused"] is False


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
    # MAJOR-1: the lender summary box and the copied package summary denominate
    # too — the summary is what an analyst pastes into a credit memo.
    assert "formatMoney(funder.total_debited, currency)" in javascript
    assert "formatMoney(totals.avg_monthly_credits, currency)" in javascript
    assert "formatMoney(totals.avg_monthly_cash_flow, currency)" in javascript


def test_no_package_money_is_rendered_with_the_usd_default():
    """Exhaustive, not a spot-check: every `formatMoney` call site in the file
    passes an explicit currency, so no money anywhere can silently inherit the
    USD default parameter."""
    javascript = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    single_argument = []
    for match in re.finditer(r"\bformatMoney\(", javascript):
        index, depth, arguments = match.end(), 1, 1
        while index < len(javascript) and depth:
            char = javascript[index]
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == "," and depth == 1:
                arguments += 1
            index += 1
        if arguments == 1:
            line = javascript.count("\n", 0, match.start()) + 1
            single_argument.append(line)
    assert javascript.count("formatMoney(") > 50, "sanity: the scan found the call sites"
    assert single_argument == [], (
        f"formatMoney call sites relying on the USD default at lines {single_argument}"
    )
