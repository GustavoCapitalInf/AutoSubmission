"""True revenue spec §9.2, §10.4, §10.7, §10.8, §11, §12 (S5): the package's True revenue, the N/A rules, the served
copy of an older payload, the gate, the True-revenue withholding mode, the exports, the review routes and the replay.
Fabricated statements only, analysed by the real analysis path."""
from __future__ import annotations

import copy

from tests.test_webapp_studio_views import _report

ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
        (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
        (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]


def _payload(rows=ROWS, month=3):
    from analysis.serialization import document_report_to_dict
    return document_report_to_dict(_report("CONTOSO BAKERY LLC", "000000001010", 1500.0, rows, month))


def _untiered(payload):
    old = copy.deepcopy(payload)
    for transaction in old["statement"]["transactions"]:
        record = transaction.get("classification") or {}
        for key in ("revenue_tier", "revenue_initial_tier", "revenue_tier_reason"):
            record.pop(key, None)
        record["classification_version"] = "5.4"
    return old


def _package(*payloads):
    from webapp.app import _package_analysis
    from webapp.jobs import Job
    return _package_analysis([Job(id=f"job-{index}", filename=f"statement-{index}.pdf", status="done", analysis=payload)
                              for index, payload in enumerate(payloads, start=1)])


def test_a_package_member_carries_its_true_revenue_and_parts():
    package = _package(_payload())
    document, totals = package["documents"][0], package["totals"]
    assert document["revenue_established"] and document["verified_revenue_established"]
    assert (document["true_revenue_total"], document["counted_flagged_total"],
            document["excluded_pending_review_total"]) == (1000.0, 300.0, 900.0)
    assert document["excluded_pending_review_by_reason"] == {"financing_named_payer": {"count": 1, "total": 900.0}}
    assert (totals["true_revenue_total"], totals["true_revenue"], totals["verified_revenue_total"]) == (
        1000.0, 1000.0, 700.0)
    assert totals["revenue_review_items"] == 1 and totals["revenue_review_required"]
    assert totals["revenue_unestablished_documents"] == []
    assert len(package["true_revenue_evidence"]) == 2
    assert package["detection"]["true_revenue_evidence"] == package["true_revenue_evidence"]
    assert len(package["counted_flagged_evidence"]) == len(package["excluded_pending_review_evidence"]) == 1


def test_counted_credits_never_gate_the_package():
    rows = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 7000.0), (3, "MOBILE DEPOSIT", 3000.0),
            (4, "ZELLE PAYMENT FROM JOHN SMITH CONF 1", 123.0)]
    totals = _package(_payload(rows))["totals"]
    assert not totals["revenue_review_required"]
    assert totals["decision"] == "approved"


def test_an_older_member_leaves_the_package_true_revenue_not_established():
    package = _package(_payload(), _untiered(_payload(month=4)))
    totals = package["totals"]
    assert totals["true_revenue_total"] is None and totals["counted_flagged_total"] is None
    assert totals["verified_revenue_total"] == 1400.0
    assert totals["revenue_unestablished_documents"] == ["job-2"]
    assert package["true_revenue_evidence"] is None
    older = package["documents"][1]
    assert not older["revenue_established"] and older["true_revenue_total"] is None
    # Its gate is the rule it was analysed under: a pending unverified deposit needs review.
    assert older["revenue_review_required"]


def test_the_verified_aliases_are_n_a_with_the_verified_total():
    # Review M4 (T9): confirmed_true_revenue_total and confirmed_true_revenue alias the verified total, so a member
    # whose verified revenue is not established leaves all three N/A.
    partial = _payload()
    partial["statement"]["transactions"][0]["classification"]["revenue_classification"] = None
    totals = _package(_payload(month=4), partial)["totals"]
    assert totals["verified_revenue_total"] is None
    assert totals["confirmed_true_revenue_total"] is None and totals["confirmed_true_revenue"] is None
    assert totals["revenue_unestablished_documents"] == ["job-2"]


def test_the_served_copy_of_an_older_payload_nulls_true_revenue():
    from webapp.app import _displayed
    served = _displayed(_untiered(_payload()), settings={})
    assert served["metrics"]["revenue_established"] is False
    assert served["metrics"]["verified_revenue_established"] is True
    assert served["metrics"]["true_revenue"] is None and served["metrics"]["true_revenue_total"] is None
    assert served["detection"]["true_revenue_evidence"] is None
    assert all("contributes_to_true_revenue" not in transaction["classification"]
               for transaction in served["statement"]["transactions"] if transaction["amount"] > 0)
    assert served["metrics"]["verified_revenue_total"] == 700.0
    fresh = _displayed(_payload(), settings={})
    assert fresh["metrics"]["revenue_established"] is True


def test_the_true_revenue_mode_deducts_only_counted_internal_transfer_credits():
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    checking = _report("CONTOSO BAKERY LLC", "000000001010", 1500.0,
                       [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 4000.0),
                        (4, "ONLINE TRANSFER FROM CHK 2020", 500.0)]).accounts[0]
    savings = _report("CONTOSO BAKERY SAVINGS", "000000002020", 9000.0,
                      [(4, "ONLINE TRANSFER TO CHK 1010", -500.0)]).accounts[0]
    transfers, notes = identify_internal_transfers([checking, savings])
    roster = [AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "1010", "published", published_index=0),
              AccountRosterEntry("CONTOSO BAKERY SAVINGS", "savings", "2020", "published", published_index=1)]
    payload = document_report_to_dict(DocumentReport(accounts=[checking, savings], internal_transfers=transfers,
                                                     integrity_notes=notes, account_roster=roster,
                                                     document_period=("2031-03-01", "2031-03-28")))
    from analysis.revenue import rebuild_serialized_revenue_views
    for account in payload["accounts"]:
        account["metrics"]["withholding_denominator_mode"] = "true_revenue"
    rebuild_serialized_revenue_views(payload)
    assert [account["metrics"]["withholding_denominator"] for account in payload["accounts"]] == [4000.0, 0.0]
    package = _package(payload)
    totals = package["totals"]
    assert (totals["withholding_denominator_mode"], totals["withholding_denominator_label"]) == (
        "true_revenue", "True revenue")
    # The pair's credit is an own-account transfer, non-revenue, so True revenue never held it: nothing comes off.
    assert totals["withholding_denominator"] == 4000.0
    assert totals["true_revenue_total"] == 4000.0
