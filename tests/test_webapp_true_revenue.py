"""True revenue spec §9.2, §10.4, §10.7, §10.8, §11, §12 (S5): the package's True revenue, the N/A rules, the served
copy of an older payload, the gate, the True-revenue withholding mode, the exports, the review routes and the replay.
Fabricated statements only, analysed by the real analysis path."""
from __future__ import annotations

import copy
import json

import pytest

from tests.test_webapp_studio_views import _report

ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
        (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
        (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]
#: ROWS, plus a registered lender's debit, an insurer's premium, an unnamed loan debit and a weekly financing debit,
#: so every detection section that copies a classification record is populated: the known funders, the insurers,
#: the potential lenders and the recurring debits.
DETECTED_ROWS = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
                 (3, "FABRIKAM CAPITAL DES:ACH DEBIT ID:1", -300.0),
                 (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
                 (6, "ONDECK CAPITAL DES:PAYMENT ID:1", -250.0), (7, "PROGRESSIVE INS DES:INS PREM ID:1", -150.0),
                 (8, "Direct Debit Loans", -125.0), (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0),
                 (10, "FABRIKAM CAPITAL DES:ACH DEBIT ID:1", -300.0),
                 (17, "FABRIKAM CAPITAL DES:ACH DEBIT ID:1", -300.0),
                 (24, "FABRIKAM CAPITAL DES:ACH DEBIT ID:1", -300.0)]
#: What a record analysed before 5.6 cannot carry, and what an account analysed before 5.6 cannot carry.
_TIER_RECORD_KEYS = ("revenue_tier", "revenue_initial_tier", "revenue_tier_reason", "contributes_to_counted_flagged",
                     "contributes_to_excluded_pending_review")
_TIER_ACCOUNT_KEYS = ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                      "excluded_pending_review_total", "excluded_pending_review_count", "counted_flagged_by_reason",
                      "excluded_pending_review_by_reason", "revenue_review_items", "counted_flagged_evidence",
                      "excluded_pending_review_evidence")
#: A package document row's True, Counted and Held figures (§9.2).
_TIER_ROW_KEYS = ("true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
                  "excluded_pending_review_total", "excluded_pending_review_count", "counted_flagged_by_reason",
                  "excluded_pending_review_by_reason")
_OLD_FLAG = "contributes_to_true_revenue"


def _payload(rows=ROWS, month=3):
    from analysis.serialization import document_report_to_dict
    return document_report_to_dict(_report("CONTOSO BAKERY LLC", "000000001010", 1500.0, rows, month))


def _records(node):
    """Every classification record under `node`: the statement rows' and `classifications`, and each copy of one in
    an evidence list, `manual_review` and the funder, insurer, potential-lender and recurring-debit matches."""
    if isinstance(node, dict):
        if "revenue_classification" in node:
            yield node
        for value in node.values():
            yield from _records(value)
    elif isinstance(node, list):
        for value in node:
            yield from _records(value)


def _untiered(payload):
    """The payload as a release before 5.6 stored it: no tier on any copy of a record, and the OLD meaning of the
    names 5.6 repointed wherever they were stored (T9): `contributes_to_true_revenue` marks a verified credit on every
    copy of a record, and `true_revenue` and `true_revenue_evidence` are the verified figure and evidence."""
    old = copy.deepcopy(payload)
    for record in _records(old):
        for key in _TIER_RECORD_KEYS:
            record.pop(key, None)
        record[_OLD_FLAG] = record.get("revenue_classification") == "verified_revenue"
        record["classification_version"] = "5.4"
    metrics, detection = old["metrics"], old["detection"]
    for key in _TIER_ACCOUNT_KEYS:
        metrics.pop(key, None)
        detection.pop(key, None)
    metrics["true_revenue"] = metrics["verified_revenue_total"]
    metrics["true_revenue_evidence"] = copy.deepcopy(metrics["verified_revenue_evidence"])
    detection["true_revenue_evidence"] = copy.deepcopy(detection["verified_revenue_evidence"])
    return old


def _flag_sections(node, path=""):
    """Each place `contributes_to_true_revenue` sits under `node`, as a path without list indices."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == _OLD_FLAG:
                yield path
            yield from _flag_sections(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for value in node:
            yield from _flag_sections(value, path)


def _pair_document(verified_amount, pair_amount, *, pair_tier=None, mode=None):
    """A checking account (a verified customer credit, and a credit R-d pairs with its savings account's debit) and
    that savings account, in one document. `pair_tier` restates the pair credit's tier as a decided analysis would
    hold it; `mode` is the withholding basis."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.revenue import rebuild_serialized_revenue_views
    from analysis.serialization import document_report_to_dict

    checking = _report("CONTOSO BAKERY LLC", "000000001010", 1500.0,
                       [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", verified_amount),
                        (4, "ONLINE TRANSFER FROM CHK 2020", pair_amount)]).accounts[0]
    savings = _report("CONTOSO BAKERY SAVINGS", "000000002020", 90000.0,
                      [(4, "ONLINE TRANSFER TO CHK 1010", -pair_amount)]).accounts[0]
    transfers, notes = identify_internal_transfers([checking, savings])
    roster = [AccountRosterEntry("CONTOSO BAKERY LLC", "checking", "1010", "published", published_index=0),
              AccountRosterEntry("CONTOSO BAKERY SAVINGS", "savings", "2020", "published", published_index=1)]
    payload = document_report_to_dict(DocumentReport(accounts=[checking, savings], internal_transfers=transfers,
                                                     integrity_notes=notes, account_roster=roster,
                                                     document_period=("2031-03-01", "2031-03-28")))
    record = payload["accounts"][0]["statement"]["transactions"][1]["classification"]
    if pair_tier == "verified":
        record.update(revenue_classification="verified_revenue", revenue_initial_classification="verified_revenue",
                      revenue_tier="verified", revenue_initial_tier="verified", revenue_tier_reason=None)
    elif pair_tier == "counted_flagged":
        record.update(revenue_classification="unverified_deposit", revenue_initial_classification="unverified_deposit",
                      revenue_tier="counted_flagged", revenue_initial_tier="counted_flagged",
                      revenue_tier_reason="p2p", revenue_review_status="pending")
    elif pair_tier == "excluded_pending_review":
        record.update(revenue_classification="unverified_deposit", revenue_initial_classification="unverified_deposit",
                      revenue_tier="excluded_pending_review", revenue_initial_tier="excluded_pending_review",
                      revenue_tier_reason="transfer_account_designation", revenue_review_status="pending")
    for account in payload["accounts"]:
        if mode is not None:
            account["metrics"]["withholding_denominator_mode"] = mode
    return rebuild_serialized_revenue_views(payload)


def _package(*payloads, zelle: bool = True):
    """The package of `payloads`, built on an explicit settings snapshot (every default; `zelle` the owner's "Mark Zelle
    Payments as True Revenue", R2-OW17), never the data directory's settings.json."""
    from webapp.app import _package_analysis
    from webapp.jobs import Job
    from webapp.settings import DEFAULTS
    return _package_analysis([Job(id=f"job-{index}", filename=f"statement-{index}.pdf", status="done", analysis=payload)
                              for index, payload in enumerate(payloads, start=1)],
                             settings={**DEFAULTS, "zelle_true_revenue": zelle})


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


def _summary_only(month):
    """A 5.6 member whose captured credits fall short of the bank's summary total: not established, not outdated."""
    partial = _payload(month=month)
    partial["metrics"]["deposits_source"] = "summary"
    partial["metrics"]["effective_total_deposits"] = 99999.0
    return partial


def test_a_package_names_each_member_analysed_with_older_rules():
    # §12: the package note names an outdated member ("Re-analyze to compute true revenue"). Each document row carries
    # its statement's analysis_rules_outdated, read off the copy the package reads (_displayed), and the package
    # carries it when any member does. A summary-only member is not established, and not outdated.
    package = _package(_payload(), _untiered(_payload(month=4)), _summary_only(5))
    assert [row["analysis_rules_outdated"] for row in package["documents"]] == [False, True, False]
    assert package["analysis_rules_outdated"] is True
    assert package["totals"]["revenue_unestablished_documents"] == ["job-2", "job-3"]
    current = _package(_payload(), _summary_only(4))
    assert [row["analysis_rules_outdated"] for row in current["documents"]] == [False, False]
    assert current["analysis_rules_outdated"] is False
    # A statement of several accounts is marked at its top level, never on an account: each account row carries it.
    document = _pair_document(700.0, 300.0)
    document["accounts"] = [_untiered(account) for account in document["accounts"]]
    older = _package(document)
    assert [row["id"] for row in older["documents"]] == ["job-1#account_1", "job-1#account_2"]
    assert [row["analysis_rules_outdated"] for row in older["documents"]] == [True, True]
    assert older["analysis_rules_outdated"] is True


def test_the_re_analyze_flag_is_left_out_of_the_package_downloads():
    # S6 review: the flag feeds the dashboard's note alone; the package downloads keep their shape.
    from webapp.app import _package_for_export

    exported = _package_for_export(_package(_payload(), _untiered(_payload(month=4))))
    assert "analysis_rules_outdated" not in exported
    assert all("analysis_rules_outdated" not in row for section in ("documents", "monthly")
               for row in exported.get(section) or [])


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
    payload = _pair_document(4000.0, 500.0, mode="true_revenue")
    assert [account["metrics"]["withholding_denominator"] for account in payload["accounts"]] == [4000.0, 0.0]
    package = _package(payload)
    totals = package["totals"]
    assert (totals["withholding_denominator_mode"], totals["withholding_denominator_label"]) == (
        "true_revenue", "True revenue")
    # The pair's credit is an own-account transfer, non-revenue, so True revenue never held it: nothing comes off.
    assert totals["withholding_denominator"] == 4000.0
    assert totals["true_revenue_total"] == 4000.0


def test_the_exports_write_the_by_reason_figures_as_readable_rows():
    from webapp.app import _analysis_rows, _package_rows
    rows = _analysis_rows(_payload())
    assert ("revenue_tier", "excluded_pending_review.financing_named_payer.total", 900.0) in rows
    assert ("revenue_tier", "counted_flagged.check_deposit.count", 1) in rows
    assert not any(field == "counted_flagged_by_reason" for _section, field, _value in rows)
    package_rows = _package_rows(_package(_payload()))
    assert ("revenue_tier", "excluded_pending_review.financing_named_payer.total", 900.0) in package_rows
    assert ("document_1.revenue_tier", "counted_flagged.check_deposit.total", 300.0) in package_rows


def test_the_review_routes_reject_a_rule_verified_credit_and_refuse_its_confirm():
    from webapp.app import app, store
    job = store.create("true-revenue.pdf")
    store.set_result(job.id, "# Fabricated", "<p>Fabricated</p>", analysis=_payload())
    client = app.test_client()
    refused = client.post(f"/analysis/{job.id}/revenue-review",
                          json={"source_location": "transaction:1", "decision": "confirm"})
    assert refused.status_code == 400
    assert refused.get_json()["error"] == "a credit a rule verified can only be marked non-revenue"
    rejected = client.post(f"/analysis/{job.id}/revenue-review",
                           json={"source_location": "transaction:1", "decision": "reject"})
    record = rejected.get_json()["analysis"]["statement"]["transactions"][0]["classification"]
    assert (record["revenue_classification"], record["revenue_tier"]) == ("non_revenue", "non_revenue")
    confirmed = client.post(f"/analysis/{job.id}/revenue-reviews",
                            json={"decisions": [{"source_location": "transaction:3", "decision": "confirm"}]})
    metrics = confirmed.get_json()["analysis"]["metrics"]
    assert (metrics["verified_revenue_total"], metrics["excluded_pending_review_total"]) == (900.0, 0.0)


def test_a_rule_verified_row_awaits_only_a_reject_on_replay():
    import json
    from webapp.reanalysis import _awaits_review, replay_reviews

    payload = _payload()
    verified = payload["statement"]["transactions"][0]["classification"]
    assert _awaits_review(verified, "reject") and not _awaits_review(verified, "confirm")
    counted = payload["statement"]["transactions"][1]["classification"]
    assert _awaits_review(counted, "confirm") and _awaits_review(counted, "reject")
    prior = json.dumps(verified)
    history = [{"id": 7, "source_location": "transaction:1", "decision": "reject", "prior_state": prior,
                "decided_at": "2031-04-01T00:00:00+00:00"},
               {"id": 8, "source_location": "transaction:1", "decision": "confirm", "prior_state": prior,
                "decided_at": "2031-03-31T00:00:00+00:00"}]
    replay = replay_reviews(_payload(), history[:1])
    assert replay.replayed == (7,)
    assert replay.analysis["statement"]["transactions"][0]["classification"]["revenue_tier"] == "non_revenue"
    ruled = replay_reviews(_payload(), history[1:])
    assert (ruled.replayed, ruled.not_replayed, ruled.decided_by_rules) == ((), (), (8,))


# --- The S5 service review (fix round 1) ---


def test_an_older_payload_carries_no_true_revenue_flag_anywhere_it_is_served():
    # T10, §12: an older payload stores contributes_to_true_revenue, with its OLD verified meaning, on every copy of a
    # record, not only on the statement rows. None of them may reach a reader: not the served copy, not the package
    # built from it, not the API or the downloads. The stored job stays byte-identical.
    from webapp.app import _displayed, app, store

    old = _untiered(_payload(DETECTED_ROWS))
    stored = json.dumps(old, sort_keys=True)
    # The fixture is realistic: every copy of a record carries the old flag, and the verified ones carry True.
    assert {"statement.transactions.classification", "classifications", "metrics.verified_revenue_evidence",
            "metrics.true_revenue_evidence", "metrics.unverified_deposit_evidence", "metrics.non_revenue_evidence",
            "metrics.potential_revenue_evidence", "metrics.lender_evidence", "metrics.insurance_evidence",
            "metrics.potential_lender_evidence", "detection.verified_revenue_evidence",
            "detection.true_revenue_evidence", "detection.unverified_deposit_evidence",
            "detection.potential_revenue_evidence", "detection.non_revenue_evidence", "detection.manual_review",
            "detection.lender_evidence", "detection.insurance_evidence", "detection.potential_lender_evidence",
            "detection.known_funders.evidence", "detection.known_funders.transactions.classification",
            "detection.insurance_providers.evidence", "detection.insurance_providers.transactions.classification",
            "detection.potential_lenders.evidence", "detection.potential_lenders.transactions.classification",
            "detection.recurring_debits.evidence", "detection.recurring_debits.transactions.classification",
            } <= set(_flag_sections(old))
    assert old["metrics"]["verified_revenue_evidence"][0][_OLD_FLAG] is True
    assert old["detection"]["verified_revenue_evidence"][0][_OLD_FLAG] is True
    assert old["classifications"][0][_OLD_FLAG] is True

    assert set(_flag_sections(_displayed(old, settings={}))) == set()
    package = _package(old)
    assert set(_flag_sections(package)) == set()
    assert package["funders"] and package["insurance_providers"] and package["potential_lenders"]
    assert json.dumps(old, sort_keys=True) == stored

    job = store.create("older.pdf")
    store.set_result(job.id, "# Fabricated", "<p>Fabricated</p>", analysis=old)
    stored_job = json.dumps(store.get(job.id).analysis, sort_keys=True)
    client = app.test_client()
    for url in (f"/analysis/{job.id}", f"/download/{job.id}/json", f"/download/{job.id}/csv",
                f"/package_analysis?ids={job.id}", f"/package_download/json?ids={job.id}",
                f"/package_download/csv?ids={job.id}"):
        response = client.get(url)
        assert response.status_code == 200, url
        assert _OLD_FLAG not in response.get_data(as_text=True), url
    assert json.dumps(store.get(job.id).analysis, sort_keys=True) == stored_job


def test_a_5_6_payload_keeps_the_repointed_flag_on_every_copy():
    # T9: from 5.6 on the flag means True revenue, and the served copy keeps it wherever the payload stored it.
    from webapp.app import _displayed
    served = _displayed(_payload(DETECTED_ROWS), settings={})
    assert {"statement.transactions.classification", "classifications", "metrics.true_revenue_evidence",
            "detection.counted_flagged_evidence", "detection.known_funders.evidence"} <= set(_flag_sections(served))
    counted = served["statement"]["transactions"][1]["classification"]
    assert (counted["revenue_tier"], counted[_OLD_FLAG]) == ("counted_flagged", True)


def test_a_document_row_shows_no_tier_figure_when_its_revenue_is_not_established():
    # §9.2, §10.4: a member whose credits carry tiers but whose captured credits are not the money its Total counts
    # (the bank's summary total, which the line items fall short of) has no established revenue: its row's True,
    # Counted and Held figures are N/A, and the package export writes them empty.
    from webapp.app import _package_rows
    partial = _payload(month=4)
    partial["metrics"]["deposits_source"] = "summary"
    partial["metrics"]["effective_total_deposits"] = 99999.0
    package = _package(_payload(), partial)
    established, unestablished = package["documents"]
    assert established["revenue_established"] and established["true_revenue_total"] == 1000.0
    assert not unestablished["revenue_established"]
    assert {key: unestablished[key] for key in _TIER_ROW_KEYS} == dict.fromkeys(_TIER_ROW_KEYS)
    rows = _package_rows(package)
    assert ("document_2", "true_revenue_total", "") in rows
    assert ("document_2", "excluded_pending_review_count", "") in rows
    assert not any(section == "document_2.revenue_tier" for section, _field, _value in rows)
    assert any(section == "document_1.revenue_tier" for section, _field, _value in rows)


def test_a_member_with_no_rows_and_no_stored_verified_figure_has_none():
    # §9.2: without authoritative rows, a member's verified figure falls back to verified_revenue_total, then
    # confirmed_true_revenue_total, then None (not established), never 0.0; the document row shows N/A.
    from webapp.app import _package_rows
    bare = _payload(month=4)
    bare["statement"]["transactions"] = []
    del bare["classifications"]
    for key in ("verified_revenue_total", "confirmed_true_revenue_total"):
        del bare["metrics"][key]
    package = _package(_payload(), bare)
    row = package["documents"][1]
    assert not row["verified_revenue_established"]
    assert row["verified_revenue_total"] is None and row["confirmed_true_revenue_total"] is None
    assert ("document_2", "verified_revenue_total", "") in _package_rows(package)
    assert package["totals"]["verified_revenue_total"] is None
    # A stored figure is kept as stored (T10), under the not-established flag.
    stored = copy.deepcopy(bare)
    stored["metrics"]["confirmed_true_revenue_total"] = 700.0
    kept = _package(stored)["documents"][0]
    assert (kept["verified_revenue_total"], kept["verified_revenue_established"]) == (700.0, False)


def test_the_package_gate_reads_the_member_without_its_internal_transfer_pair():
    # T7 in the package reads the member's rows without R-d's internal-transfer pairs. The pairing proves the money is
    # the holder's own, moving between two of its accounts, so a held pair credit awaits no revenue review there:
    # 500 held against 4,500 posted gates the statement (11%, it cannot see the sibling), not the package.
    payload = _pair_document(4000.0, 500.0, pair_tier="excluded_pending_review")
    checking = payload["accounts"][0]["metrics"]
    assert (checking["excluded_pending_review_total"], checking["revenue_review_required"]) == (500.0, True)
    package = _package(payload)
    assert package["documents"][0]["revenue_review_required"] is False
    assert package["totals"]["revenue_review_required"] is False
    assert package["totals"]["decision"] == "approved"


@pytest.mark.parametrize(("pair_tier", "member_denominator"), [
    ("counted_flagged", 4500.0), ("verified", 4500.0), ("excluded_pending_review", 4000.0)])
def test_the_true_revenue_mode_deducts_a_pair_credit_true_revenue_holds(pair_tier, member_denominator):
    # §11: the True-revenue denominator loses the R-d pair credits it holds, verified or counted, and only those.
    payload = _pair_document(4000.0, 500.0, pair_tier=pair_tier, mode="true_revenue")
    assert payload["accounts"][0]["metrics"]["withholding_denominator"] == member_denominator
    totals = _package(payload)["totals"]
    assert totals["withholding_denominator_mode"] == "true_revenue"
    assert totals["withholding_denominator"] == 4000.0


def test_a_mixed_currency_package_refuses_the_by_reason_money_and_keeps_the_counts():
    # §9.2 (currency): a refused package sets every total inside the by-reason dicts to None; the counts stay, and
    # each document row keeps its own denominated figures.
    from webapp.app import _package_rows
    cad = _payload(month=4)
    cad["statement"]["currency"] = "CAD"
    package = _package(_payload(), cad)
    totals = package["totals"]
    assert totals["cross_currency_totals_refused"] is True
    assert totals["counted_flagged_by_reason"] == {"check_deposit": {"count": 2, "total": None}}
    assert totals["excluded_pending_review_by_reason"] == {"financing_named_payer": {"count": 2, "total": None}}
    assert (totals["true_revenue_count"], totals["counted_flagged_count"], totals["excluded_pending_review_count"],
            totals["revenue_review_items"]) == (4, 2, 2, 2)
    assert totals["true_revenue_total"] is None
    rows = _package_rows(package)
    assert ("revenue_tier", "counted_flagged.check_deposit.total", "") in rows
    assert ("revenue_tier", "counted_flagged.check_deposit.count", 2) in rows
    assert ("document_2.revenue_tier", "counted_flagged.check_deposit.total", 300.0) in rows


@pytest.mark.parametrize(("held", "gated"), [(1000.0, True), (999.0, False)])
def test_the_package_gate_holds_at_ten_percent_of_posted_credits(held, gated):
    # T7: held credits of 10% or more of the posted credits gate, compared in integer cents; 9.99% does not.
    package = _package(_payload([(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 10000.0 - held),
                                 (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", held)]))
    document, totals = package["documents"][0], package["totals"]
    assert (document["excluded_pending_review_total"], document["total_posted_credits"]) == (held, 10000.0)
    assert document["revenue_review_required"] is gated
    assert totals["revenue_review_required"] is gated
    assert totals["decision"] == ("review_required" if gated else "approved")


def _verified_unestablished(month):
    partial = _payload(month=month)
    partial["statement"]["transactions"][0]["classification"]["revenue_classification"] = None
    return partial


@pytest.mark.parametrize(("mode", "member"), [
    ("true_revenue", lambda: _untiered(_payload(month=4))),
    ("true_revenue", lambda: _summary_only(4)),
    ("verified_revenue", lambda: _verified_unestablished(4)),
])
def test_a_revenue_withholding_rate_is_never_published_on_a_partial_denominator(mode, member):
    # Final review M10 (§11): in the True- and Verified-revenue modes a member whose figure is not established adds a
    # partial figure to the denominator, so the package publishes no rate and asks for review.
    members = [_payload(), member()]
    for payload in members:
        payload["metrics"]["withholding_denominator_mode"] = mode
    totals = _package(*members)["totals"]
    assert totals["withholding_denominator_mode"] == mode
    assert totals["package_withholding_rate"] is None and totals["package_withholding_rate_raw"] is None
    assert totals["potential_withholding_exposure"] is None
    assert totals["withholding_review_required"] is True
    established = [_payload(), _payload(month=4)]
    for payload in established:
        payload["metrics"]["withholding_denominator_mode"] = mode
    assert _package(*established)["totals"]["package_withholding_rate"] is not None


def test_the_legacy_withholding_mode_keeps_its_rate_beside_an_unestablished_member(monkeypatch):
    # Owner ruling 2026-10-02 (the underwriter's Q7), R2-OW14: True revenue is the default basis, so the legacy mode is
    # selected for the members' analyses.
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "legacy_eligible_deposits")
    totals = _package(_payload(), _untiered(_payload(month=4)))["totals"]
    assert totals["withholding_denominator_mode"] == "legacy_eligible_deposits"
    assert totals["package_withholding_rate"] is not None and totals["withholding_review_required"] is False


def test_the_default_basis_is_true_revenue_and_a_stored_payload_without_a_mode_keeps_its_legacy_basis(monkeypatch):
    """Owner ruling 2026-10-02 (the underwriter's Q7, audit I34), R2-OW14: an analysis made today divides by True
    revenue (U1); a payload stored before the default moved carries no mode and keeps the legacy basis it was analysed
    under, in the served copy (revenue.py) and in the package (app.py) (U3)."""
    from webapp.app import _displayed

    monkeypatch.delenv("WITHHOLDING_DENOMINATOR_MODE", raising=False)
    today = _payload()
    assert (today["metrics"]["withholding_denominator_mode"], today["metrics"]["withholding_denominator"]) == (
        "true_revenue", 1000.0)
    assert today["metrics"]["legacy_eligible_deposits"] == 2000.0
    totals = _package(_payload())["totals"]
    assert (totals["withholding_denominator_mode"], totals["withholding_denominator_label"],
            totals["withholding_denominator"]) == ("true_revenue", "True revenue", 1000.0)

    stored = _payload()
    metrics = stored["metrics"]
    for key in ("withholding_denominator_mode", "withholding_denominator_label", "eligible_deposit_definition"):
        metrics.pop(key)
    for key in ("eligible_deposits", "withholding_denominator", "potential_withholding_denominator"):
        metrics[key] = 2000.0
    # The served copy keeps the stored basis (the dashboard reads a missing mode as legacy: activeDenominatorNote), and
    # the revenue rebuild (a review decision) reads it as legacy and keeps the stored denominator.
    from analysis.revenue import rebuild_serialized_revenue_views

    served = _displayed(copy.deepcopy(stored), settings={})
    assert "withholding_denominator_mode" not in served["metrics"]
    assert served["metrics"]["withholding_denominator"] == served["metrics"]["eligible_deposits"] == 2000.0
    rebuilt = rebuild_serialized_revenue_views(copy.deepcopy(stored))
    assert rebuilt["metrics"]["withholding_denominator_mode"] == "legacy_eligible_deposits"
    assert rebuilt["metrics"]["withholding_denominator"] == rebuilt["metrics"]["eligible_deposits"] == 2000.0
    totals = _package(stored)["totals"]
    assert (totals["withholding_denominator_mode"], totals["withholding_denominator_label"],
            totals["withholding_denominator"]) == ("legacy_eligible_deposits", "Legacy eligible deposits", 2000.0)


# ---------------------------------------------------------------- Audit B11: months, averages, the gate and the exports

def _account_payload(number, rows, month=3):
    """A fabricated statement of another account of the same business (its own number), month `month` of 2031."""
    from analysis.serialization import document_report_to_dict
    from tests.test_webapp_studio_views import _report
    return document_report_to_dict(_report("CONTOSO BAKERY LLC", number, 1500.0, rows, month))


_SECOND_ACCOUNT_ROWS = [(5, "FABRIKAM STORES INC DES:PAYMENT ID:2", 2000.0), (6, "MOBILE DEPOSIT", 500.0)]


def test_two_accounts_uploaded_separately_for_one_month_are_one_month():
    """I33: months counted members, so two accounts of one business for March read "2 months" and halved every
    monthly average. They are one calendar month; the per-month True is the two accounts' March summed."""
    package = _package(_payload(), _account_payload("000000002020", _SECOND_ACCOUNT_ROWS))
    totals = package["totals"]
    assert totals["months"] == 1 and totals["statement_periods"] == 2
    assert totals["true_revenue_total"] == 1000.0 + 2500.0
    assert totals["avg_monthly_true_revenue"] == 3500.0
    assert totals["avg_monthly_verified_revenue"] == 700.0 + 2000.0
    assert totals["avg_monthly_credits"] == totals["total_credits"]
    assert totals["avg_monthly_non_revenue"] == totals["non_revenue_total"] == 100.0
    assert totals["has_duplicate_documents"] is False


def test_a_duplicated_middle_month_leaves_the_averages_unchanged():
    months = {month: _payload(month=month) for month in (1, 2, 3)}
    clean = _package(months[1], months[2], months[3])["totals"]
    repeated = _package(months[1], months[2], copy.deepcopy(months[2]), months[3])["totals"]
    keys = ("months", "true_revenue_total", "verified_revenue_total", "avg_monthly_true_revenue",
            "avg_monthly_verified_revenue", "avg_monthly_credits", "avg_monthly_debits", "avg_monthly_cash_flow",
            "avg_monthly_non_revenue", "total_credits")
    assert {key: repeated[key] for key in keys} == {key: clean[key] for key in keys}
    assert clean["months"] == 3 and clean["avg_monthly_true_revenue"] == 1000.0
    assert repeated["duplicate_documents"] == 1 and repeated["decision"] == "review_required"


def test_a_statement_period_spanning_two_months_counts_in_the_month_holding_most_of_its_days():
    from webapp.app import _statement_month

    assert _statement_month("2031-03-02", "2031-04-01") == 2031 * 12 + 2
    assert _statement_month("2030-12-01", "2031-01-02") == 2030 * 12 + 11
    assert _statement_month("2031-02-15", "2031-03-14") == 2031 * 12 + 1  # 14 days each: the earlier month
    assert _statement_month(None, "2031-05-31") == 2031 * 12 + 4
    assert _statement_month("2031-02-30", None) is None and _statement_month(None, None) is None


def test_the_per_month_true_revenue_is_n_a_where_true_revenue_is():
    totals = _package(_payload(), _summary_only(4))["totals"]
    assert totals["true_revenue_total"] is None
    assert totals["avg_monthly_true_revenue"] is None and totals["avg_monthly_verified_revenue"] is None
    assert totals["avg_monthly_non_revenue"] is not None


def test_the_per_month_figures_are_refused_with_the_other_averages():
    from tests.test_webapp_studio_views import _document
    cad = _payload(month=4)
    cad["statement"]["currency"] = "CAD"
    mixed = _package(_payload(), cad)["totals"]
    one_document = _package(_document("published"))["totals"]
    for totals in (mixed, one_document):
        assert totals["avg_monthly_true_revenue"] is None and totals["avg_monthly_verified_revenue"] is None
        assert totals["avg_monthly_non_revenue"] is None


def test_the_package_gate_reads_held_against_true_plus_held():
    """I50: $9,000 held beside $31,000 True and $60,000 of financing is 9% of the posted credits, 22.5% of True plus
    held: the member and the package need review."""
    package = _package(_payload([(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 31000.0),
                                 (3, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 9000.0),
                                 (4, "ONDECK CAPITAL DES:LOAN PROCEEDS ID:1", 60000.0)]))
    document, totals = package["documents"][0], package["totals"]
    assert (document["true_revenue_total"], document["excluded_pending_review_total"],
            document["non_revenue_total"]) == (31000.0, 9000.0, 60000.0)
    assert document["revenue_review_required"] is True and totals["revenue_review_required"] is True
    assert totals["decision"] == "review_required"


def test_the_tier_identity_has_its_own_name_and_the_package_lists_its_unreconciled_members():
    """I31: the four-tier identity is published as revenue_tiers_sum_to_posted (revenue_reconciles its alias), and the
    members whose own rows do not reconcile to their bank's figures are listed for the Revenue chip."""
    unreconciled = _payload(month=4)
    unreconciled["reconciliation"]["ok"] = False
    package = _package(_payload(), unreconciled)
    totals = package["totals"]
    assert totals["revenue_tiers_sum_to_posted"] is True and totals["revenue_reconciles"] is True
    assert totals["unreconciled_documents"] == ["job-2"]
    assert [row["revenue_tiers_sum_to_posted"] for row in package["documents"]] == [True, True]
    assert _payload()["metrics"]["revenue_tiers_sum_to_posted"] is True


def test_the_package_lists_the_members_whose_holder_or_payer_text_was_not_read():
    unscreened = _payload(month=4)
    unscreened["metrics"]["holder_unscreened"] = True
    unread = _payload(month=5)
    unread["metrics"]["payer_text_unread"] = True
    package = _package(_payload(), unscreened, unread)
    assert package["totals"]["holder_unscreened_documents"] == ["job-2"]
    assert package["totals"]["payer_text_unread_documents"] == ["job-3"]
    assert [(row["holder_unscreened"], row["payer_text_unread"]) for row in package["documents"]] == [
        (False, False), (True, False), (False, True)]


def test_the_package_lists_its_premium_trust_accounts():
    """Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: a statement whose name reads a premium trust title,
    analysed by the real path, holds every credit that would count; its metrics carry the fact, its document row
    carries it, and the totals list the members (sorted), beside the integrity facts' lists."""
    from analysis.serialization import document_report_to_dict

    trust = document_report_to_dict(_report("SAMPLE AGENCY PREMIUM TRUST", "000000003030", 1500.0, ROWS, 4))
    assert trust["metrics"]["premium_trust_account"] is True
    assert trust["metrics"]["true_revenue_total"] == 0.0
    assert _payload()["metrics"]["premium_trust_account"] is False
    second = document_report_to_dict(_report("SAMPLE AGENCY PREMIUM TRUST", "000000003030", 1500.0, ROWS, 6))
    package = _package(trust, _payload(month=5), second)
    assert package["totals"]["premium_trust_documents"] == ["job-1", "job-3"]
    assert [row["premium_trust_account"] for row in package["documents"]] == [True, False, True]
    assert package["documents"][0]["true_revenue_total"] == 0.0
    assert package["totals"]["true_revenue_total"] == _payload(month=5)["metrics"]["true_revenue_total"]
    assert _package(_payload())["totals"]["premium_trust_documents"] == []


def _csv_cells(text):
    import csv
    import io
    csv.field_size_limit(10_000_000)
    return list(csv.reader(io.StringIO(text)))


def test_a_statement_download_leaves_unestablished_revenue_empty():
    """I51: a short capture's True, Counted and Held, and every alias, are empty in the downloads (the dashboard reads
    them as N/A); Non-revenue stays, captured rows only; its Verified figure, not established either, is empty too."""
    from webapp.app import _analysis_csv, _displayed

    short = _summary_only(3)
    served = _displayed(short, settings={})
    exported = _displayed(short, settings={}, export=True)
    assert served["metrics"]["revenue_established"] is False and served["metrics"]["true_revenue_total"] == 1000.0
    cells = {(row[0], row[1]): row[2] for row in _csv_cells(_analysis_csv(exported)) if len(row) == 3}
    for key in ("true_revenue", "true_revenue_total", "true_revenue_count", "counted_flagged_total",
                "counted_flagged_count", "excluded_pending_review_total", "excluded_pending_review_count",
                "revenue_review_items", "unverified_deposit_total", "potential_revenue_total", "maximum_revenue",
                "verified_revenue_total", "confirmed_true_revenue", "confirmed_true_revenue_total"):
        assert cells[("metrics", key)] == "", key
    assert cells[("metrics", "non_revenue_total")] == "100.0"
    assert cells[("metrics", "revenue_established")] == "False"
    assert not any(row[0] == "revenue_tier" for row in _csv_cells(_analysis_csv(exported)))
    # An established statement's download keeps every figure.
    fresh = {(row[0], row[1]): row[2] for row in _csv_cells(_analysis_csv(_displayed(_payload(), settings={},
                                                                                     export=True)))
             if len(row) == 3}
    assert (fresh[("metrics", "true_revenue_total")], fresh[("metrics", "maximum_revenue")]) == ("1000.0", "1900.0")


def test_a_package_download_leaves_the_partial_figures_empty():
    from webapp.app import _package_for_export

    package = _package(_payload(month=4), _summary_only(3))
    exported = _package_for_export(package)
    totals = exported["totals"]
    for key in ("maximum_revenue", "potential_revenue_total", "unverified_deposit_total", "revenue_review_items",
                "true_revenue_total", "verified_revenue_total"):
        assert totals[key] is None, key
    assert package["totals"]["maximum_revenue"] is not None  # the served package keeps it; the dashboard reads flags
    rows = {row["id"]: row for row in exported["documents"]}
    short = rows["job-2"]
    for key in ("verified_revenue_total", "confirmed_true_revenue_total", "unverified_deposit_total",
                "potential_revenue_total", "maximum_revenue", "true_revenue_total"):
        assert short[key] is None, key
    assert rows["job-1"]["verified_revenue_total"] == 700.0 and rows["job-1"]["maximum_revenue"] == 1900.0


def test_the_xlsx_writes_money_as_numbers_and_flags_as_booleans():
    """I52: SUM and a pivot add the money; NaN, inf and every numeric-looking string stay text."""
    openpyxl = pytest.importorskip("openpyxl")
    import io
    from webapp.app import _analysis_xlsx, _displayed, _package_xlsx, _xlsx_cell

    def sheet(blob):
        workbook = openpyxl.load_workbook(io.BytesIO(blob))
        return {(row[0].value, row[1].value): row[2] for row in workbook.active.iter_rows(min_row=2)
                if len(row) >= 3}

    cells = sheet(_analysis_xlsx(_displayed(_payload(), settings={}, export=True)))
    true_cell = cells[("metrics", "true_revenue_total")]
    assert (true_cell.data_type, true_cell.value) == ("n", 1000)
    assert cells[("metrics", "true_revenue_count")].data_type == "n"
    flag = cells[("metrics", "revenue_established")]
    assert (flag.data_type, flag.value) == ("b", True)
    assert cells[("statement", "bank")].data_type == "s"
    package_cells = sheet(_package_xlsx(_package(_payload())))
    assert package_cells[("document_1", "true_revenue_total")].data_type == "n"
    assert package_cells[("totals", "true_revenue_total")].value == 1000
    assert 't="inlineStr"' in _xlsx_cell("C2", float("nan")) and 't="inlineStr"' in _xlsx_cell("C2", float("inf"))
    assert 't="inlineStr"' in _xlsx_cell("C2", "-1234.56") and 't="inlineStr"' in _xlsx_cell("C2", "0012")
    assert _xlsx_cell("C2", True) == '<c r="C2" t="b"><v>1</v></c>'
    assert _xlsx_cell("C2", -1234.5) == '<c r="C2"><v>-1234.5</v></c>'


def test_the_statement_downloads_list_every_posted_credit_on_its_own_row():
    """I32: one row per posted credit with its date, description, amount, currency, tier, reason, state and review
    status, so True can be checked deposit by deposit."""
    from webapp.app import _analysis_csv, _displayed

    rows = [row for row in _csv_cells(_analysis_csv(_displayed(_payload(), settings={}, export=True)))
            if row[0] == "posted_credit"]
    assert rows[0] == ["posted_credit", "columns", "date", "description", "amount", "currency", "tier", "reason",
                       "state", "review_status"]
    credits = rows[1:]
    assert [(row[3], row[4], row[5], row[6], row[7]) for row in credits] == [
        ("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "700.0", "USD", "verified", ""),
        ("MOBILE DEPOSIT", "300.0", "USD", "counted_flagged", "check_deposit"),
        ("FABRIKAM FUNDING LLC DES:PAYMENT ID:1", "900.0", "USD", "excluded_pending_review", "financing_named_payer"),
        ("INTERNAL TRANSFER FROM SAVINGS", "100.0", "USD", "non_revenue", ""),
    ]
    assert sum(float(row[4]) for row in credits if row[6] in ("verified", "counted_flagged")) == 1000.0
    # A document of several accounts writes one block per account, each under its section prefix.
    document_rows = _csv_cells(_analysis_csv(_pair_document(4000.0, 500.0)))
    assert {row[0] for row in document_rows if row[0].endswith("posted_credit")} == {"account_1.posted_credit"}


# ---------------------------------------------------------------- Audit round 2, R2-B16 (R53): the posted debits and
# the spreadsheet's cell limit. A fabricated 40-row statement: 35 CONTOSO LLC credits, a FABRIKAM CAPITAL debit (a
# confirmed lender), a NORTHWIND NSF fee, a SAMPLE purchase still pending (unposted), a SAMPLE purchase whose text
# starts with "=" and a card payment of a flag group (Credit cards).

_FORTY_ROWS = ([(1 + index % 28, f"CONTOSO LLC DES:PAYMENT ID:{index + 1}", 100.0) for index in range(35)]
               + [(10, "FABRIKAM CAPITAL DES:ACH DEBIT ID:1", -250.0), (11, "NORTHWIND NSF FEE", -35.0),
                  (12, "PENDING SAMPLE STORE PURCHASE", -60.0), (13, "=SAMPLE STORE PURCHASE", -20.0),
                  (14, "AMERICAN EXPRESS ACH PMT", -90.0)])
_XLSX_CELL_LIMIT = 32767
_POINTER = "Not shown: {:,} characters, over the spreadsheet cell limit; see the JSON download."


def _forty_payload():
    """The 40-row statement, analysed by the real path; the FABRIKAM CAPITAL debit's record restated as a confirmed
    lender's (lender detection names it), as _pair_document restates a decided record."""
    payload = _payload(_FORTY_ROWS)
    assert len(payload["statement"]["transactions"]) == 40
    for row in payload["statement"]["transactions"]:
        if row["description"].startswith("FABRIKAM CAPITAL"):
            row["classification"].update(classification="confirmed_lender", canonical_entity="FABRIKAM CAPITAL",
                                         review_required=False)
    return payload


def _sheet_rows(blob):
    """The statement XLSX's rows as Excel reads them: an inline string's unescaped text, a number as a float, a
    boolean as a bool."""
    import io
    import zipfile
    from xml.etree import ElementTree

    main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    root = ElementTree.fromstring(zipfile.ZipFile(io.BytesIO(blob)).read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.iter(f"{main}row"):
        cells = []
        for cell in row.iter(f"{main}c"):
            kind = cell.get("t")
            if kind == "inlineStr":
                cells.append("".join(text.text or "" for text in cell.iter(f"{main}t")))
            elif kind == "b":
                cells.append(cell.find(f"{main}v").text == "1")
            else:
                cells.append(float(cell.find(f"{main}v").text))
        rows.append(cells)
    return rows


def _utf16(text):
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _two_accounts_with_debits():
    """A document of two accounts, each with a posted debit: CONTOSO LLC's checking and its savings."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    checking = _report("CONTOSO LLC", "000000001010", 1500.0,
                       [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (5, "NORTHWIND NSF FEE", -35.0)]).accounts[0]
    savings = _report("CONTOSO LLC SAVINGS", "000000002020", 9000.0,
                      [(6, "AMERICAN EXPRESS ACH PMT", -90.0)]).accounts[0]
    transfers, notes = identify_internal_transfers([checking, savings])
    roster = [AccountRosterEntry("CONTOSO LLC", "checking", "1010", "published", published_index=0),
              AccountRosterEntry("CONTOSO LLC SAVINGS", "savings", "2020", "published", published_index=1)]
    return document_report_to_dict(DocumentReport(accounts=[checking, savings], internal_transfers=transfers,
                                                  integrity_notes=notes, account_roster=roster,
                                                  document_period=("2031-03-01", "2031-03-28")))


def test_the_statement_xlsx_keeps_every_cell_under_the_limit_and_the_csv_keeps_the_ledger_whole():
    """R53: no XLSX cell holds more than Excel's 32,767 characters; the ledger cell, over it, says what it held and
    points to the JSON download (never a cut JSON). The CSV, which has no such limit, keeps the whole ledger."""
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed

    served = _displayed(_forty_payload(), settings={}, export=True)
    ledger = json.dumps(served["statement"]["transactions"])
    assert _utf16(ledger) > _XLSX_CELL_LIMIT
    rows = _sheet_rows(_analysis_xlsx(served))
    assert all(_utf16(value) <= _XLSX_CELL_LIMIT for row in rows for value in row if isinstance(value, str))
    cells = {(row[0], row[1]): row[2] for row in rows if len(row) == 3}
    assert cells[("statement", "transactions")] == _POINTER.format(_utf16(ledger))
    csv_cells = {(row[0], row[1]): row[2] for row in _csv_cells(_analysis_csv(served)) if len(row) == 3}
    assert json.loads(csv_cells[("statement", "transactions")]) == json.loads(ledger)


def test_the_statement_downloads_list_every_posted_debit_on_its_own_row():
    """R53: one row per posted debit after the credit table, with its date, description, signed amount (a number in the
    XLSX), currency, classification, flag group (only where Settings shows the group), entity and review flag; no
    unposted row and no credit; statement text formula-escaped."""
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed

    served = _displayed(_forty_payload(), settings={}, export=True)
    csv_rows = _csv_cells(_analysis_csv(served))
    sections = [row[0] for row in csv_rows]
    assert sections.index("posted_debit") > max(index for index, section in enumerate(sections)
                                                if section == "posted_credit")
    debits = [row for row in csv_rows if row[0] == "posted_debit"]
    assert debits[0] == ["posted_debit", "columns", "date", "description", "amount", "currency", "classification",
                         "flagged_group", "canonical_entity", "review_required", "returned_funder_payment"]
    assert debits[1:] == [
        ["posted_debit", "1", "2031-03-10", "FABRIKAM CAPITAL DES:ACH DEBIT ID:1", "-250.0", "USD", "confirmed_lender",
         "", "FABRIKAM CAPITAL", "False", ""],
        ["posted_debit", "2", "2031-03-11", "NORTHWIND NSF FEE", "-35.0", "USD", "nsf_or_return", "", "", "False", ""],
        ["posted_debit", "3", "2031-03-13", "'=SAMPLE STORE PURCHASE", "-20.0", "USD", "other", "", "", "False", ""],
        ["posted_debit", "4", "2031-03-14", "AMERICAN EXPRESS ACH PMT", "-90.0", "USD", "credit_card_payment",
         "credit_cards", "American Express [credit card payment]", "False", ""],
    ]
    # The XLSX writes the same block, the amount a number and the flag a boolean.
    sheet = [row for row in _sheet_rows(_analysis_xlsx(served)) if row[0] == "posted_debit"]
    assert sheet[1] == ["posted_debit", 1.0, "2031-03-10", "FABRIKAM CAPITAL DES:ACH DEBIT ID:1", -250.0, "USD",
                        "confirmed_lender", "", "FABRIKAM CAPITAL", False, ""]
    assert sheet[3][3] == "'=SAMPLE STORE PURCHASE"
    # An unticked group leaves the flag column blank (its rows lose their flag on the served copy).
    unticked = _displayed(_forty_payload(), settings={"flag_credit_cards": False}, export=True)
    amex = [row for row in _csv_cells(_analysis_csv(unticked)) if row[0] == "posted_debit"][4]
    assert (amex[3], amex[6], amex[7]) == ("AMERICAN EXPRESS ACH PMT", "credit_card_payment", "")
    # A document of two accounts writes a block for each, under its section prefix.
    document_rows = _csv_cells(_analysis_csv(_displayed(_two_accounts_with_debits(), settings={}, export=True)))
    blocks = [row for row in document_rows if row[0].endswith("posted_debit")]
    assert [(row[0], row[3]) for row in blocks if row[1] != "columns"] == [
        ("account_1.posted_debit", "NORTHWIND NSF FEE"), ("account_2.posted_debit", "AMERICAN EXPRESS ACH PMT")]


def test_a_funder_payment_returned_unpaid_names_the_credit_that_returned_it():
    """R53 with R2-OW13's column (the underwriter's Q5): a confirmed funder's payment the bank returned unpaid names the
    returning credit's location; the funder's other payment, and the returning credit (no debit), do not."""
    from webapp.app import _analysis_csv, _displayed

    payload = _payload([(1, "FABRIKAM SUPPLY INC DES:PAYMENT ID:1", 10000.0), (2, "KAPITUS DES:PAYMENT ID:1", -850.0),
                        (3, "KAPITUS RETURNED ACH ITEM 0001", 850.0), (5, "KAPITUS DES:PAYMENT ID:2", -850.0)])
    debits = [row for row in _csv_cells(_analysis_csv(_displayed(payload, settings={}, export=True)))
              if row[0] == "posted_debit" and row[1] != "columns"]
    assert [(row[2], row[6], row[10]) for row in debits] == [("2031-03-02", "confirmed_lender", "transaction:3"),
                                                              ("2031-03-05", "confirmed_lender", "")]


def test_the_xlsx_cell_limit_counts_utf16_units_and_never_cuts():
    """R53: 32,767 UTF-16 units are kept; one more is replaced whole by the pointer; a character outside the Basic
    Multilingual Plane counts two, as Excel counts it. Numbers and flags are untouched."""
    from webapp.app import _xlsx_cell

    def text(markup):
        return markup.split("<t>", 1)[1].rsplit("</t>", 1)[0]

    assert text(_xlsx_cell("C2", "x" * _XLSX_CELL_LIMIT)) == "x" * _XLSX_CELL_LIMIT
    assert text(_xlsx_cell("C2", "x" * (_XLSX_CELL_LIMIT + 1))) == _POINTER.format(_XLSX_CELL_LIMIT + 1)
    face = "\N{GRINNING FACE}"
    kept = face * 16383 + "x"
    assert _utf16(kept) == _XLSX_CELL_LIMIT and text(_xlsx_cell("C2", kept)) == kept
    assert text(_xlsx_cell("C2", face * 16384)) == _POINTER.format(_XLSX_CELL_LIMIT + 1)
    assert _xlsx_cell("C2", -250.0) == '<c r="C2"><v>-250.0</v></c>'
    assert _xlsx_cell("C2", False) == '<c r="C2" t="b"><v>0</v></c>'


def test_a_short_statement_xlsx_changes_only_by_the_debit_block_and_a_package_xlsx_not_at_all():
    """R53 controls: below the limit every cell is written as before, so a short statement's XLSX is the flat rows and
    the credit table, unchanged, then the debit table; a package's XLSX is its rows, unchanged."""
    from webapp.app import (_analysis_rows, _analysis_xlsx, _displayed, _escaped_rows, _package_rows,
                            _package_transaction_table, _package_xlsx, _posted_credit_table, _posted_debit_table)

    def as_read(rows):
        # A cell as the sheet holds it: a bool, a number or a string (any other value is written as its text).
        return [[value if isinstance(value, (bool, int, float, str)) else str(value) for value in row]
                for row in _escaped_rows(rows)]

    served = _displayed(_payload(), settings={}, export=True)
    before = as_read(_analysis_rows(served) + _posted_credit_table(served))
    block = as_read(_posted_debit_table(served))
    assert [row[3] for row in block] == ["description", "CARD PURCHASE FABRIKAM SUPPLY"]
    rows = _sheet_rows(_analysis_xlsx(served))
    assert rows[0] == ["section", "field", "value"]
    assert rows[1:len(before) + 1] == before
    assert rows[len(before) + 1:] == block
    assert [row for row in rows if row[0] == "posted_credit"] == as_read(_posted_credit_table(served))
    package = _package(_payload())
    package_rows = _sheet_rows(_package_xlsx(package))
    assert package_rows[1:] == as_read(_package_rows(package) + _package_transaction_table(package))
    assert not any(isinstance(value, str) and value.startswith("Not shown:") for row in package_rows for value in row)


def test_the_package_downloads_split_the_evidence_by_tier_and_name_its_unit_and_account():
    """I32: counted (in True) and held (out of it) credits get their own sections, each record naming its currency
    and account; the combined ledger is written one posting a row."""
    from webapp.app import _package_csv, _package_rows

    package = _package(_payload(), _untiered(_payload(month=4)))
    rows = _package_rows(package)
    sections = {section.rsplit("_", 1)[0] for section, _field, _value in rows if section.endswith(tuple("0123456789"))}
    assert {"verified_revenue_evidence", "counted_flagged_evidence", "excluded_pending_review_evidence",
            "non_revenue_evidence", "unverified_deposit_evidence"} <= sections
    counted = {field: value for section, field, value in rows if section == "counted_flagged_evidence_1"}
    assert (counted["revenue_tier"], counted["source_currency"], counted["source_account"]) == (
        "counted_flagged", "USD", "")
    held = {field: value for section, field, value in rows if section == "excluded_pending_review_evidence_1"}
    assert held["revenue_tier"] == "excluded_pending_review"
    # The older member's unverified credits carry no tier and stay in the state's section.
    older = {field: value for section, field, value in rows if section == "unverified_deposit_evidence_1"}
    assert "revenue_tier" not in older and older["source_job"] == "job-2"
    ledger = [row for row in _csv_cells(_package_csv(package)) if row[0] == "package_transaction"]
    assert ledger[0][2:] == ["source_document", "source_account", "source_currency", "date", "description", "amount",
                             "classification", "tier", "reason", "state", "review_status"]
    assert len(ledger) - 1 == len(package["transactions"])
    first = ledger[1]
    assert first[1] == "1" and first[2:8] == ["statement-1.pdf", "", "USD", "2031-03-02",
                                              "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "700.0"]
    assert first[9:] == ["verified", "", "verified_revenue", package["transactions"][0]["classification"][
        "revenue_review_status"]]
    two_accounts = _package(_pair_document(4000.0, 500.0))
    assert {record["source_account"] for record in two_accounts["verified_revenue_evidence"]} == {1}


# ---------------------------------------------------------------- Audit round 2, R2-B15 (R13): months by days covered

#: The two fabricated accounts the R13 tests read: CONTOSO BAKERY LLC's checking and its FABRIKAM-paid operating account.
_CONTOSO_NUMBER = "000000001010"
_FABRIKAM_NUMBER = "000000002020"


def _period_payload(start, end, total=10000.0, *, number=_CONTOSO_NUMBER, bank="CONTOSO BANK"):
    """A fabricated statement of `number` printing `start`..`end`, whose one credit, a FABRIKAM INC ACH payment of
    `total` on its first day, is its True revenue."""
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction
    from analysis.serialization import document_report_to_dict

    balance = round(1500.0 + total, 2)
    statement = Statement(bank=bank, account_name="CONTOSO BAKERY LLC", account_number=number, period_start=start,
                          period_end=end, beginning_balance=1500.0, ending_balance=balance, currency="USD",
                          currency_source="printed",
                          transactions=[Transaction(date=start, description="FABRIKAM INC DES:ACH PAYMENT ID:1",
                                                    amount=total, direction="credit", running_balance=balance)])
    return document_report_to_dict(analyze_statement(statement, reconciliation=reconcile(statement), markdown="",
                                                     sheets=[], model_used="fabricated-test"))


def _periods_package(periods, **kwargs):
    """A package of one statement per `(start, end)` (or `(start, end, total)`), in that order."""
    return _package(*(_period_payload(*period, **kwargs) for period in periods))


#: A fixed cycle starting on the 16th across February: B11's month rule read 02-16..03-15 (13 February days, 15 March
#: days) and 03-16..04-15 (16 March days) as March both, so three statements read two months.
_SIXTEENTH_CYCLE = [("2031-01-16", "2031-02-15"), ("2031-02-16", "2031-03-15"), ("2031-03-16", "2031-04-15")]


def _months(totals):
    return (totals["months"], totals["true_revenue_total"], totals["avg_monthly_true_revenue"])


def test_three_statements_of_a_mid_month_cycle_across_february_read_three_months():
    """R13: the days the account's statements cover (90 here, 2.96 months of 30.4375 days) floor the month count, so a
    16th-to-15th cycle across February reads 3 months, never the 2 calendar months its labels fall in."""
    package = _periods_package(_SIXTEENTH_CYCLE)
    totals = package["totals"]
    assert _months(totals) == (3, 30000.0, 10000.0)
    assert "statement_periods" not in totals  # three statements, three months
    assert totals["avg_monthly_verified_revenue"] == round(totals["verified_revenue_total"] / 3, 2)
    assert totals["avg_monthly_credits"] == 10000.0 and totals["decision"] == "approved"


def test_a_cycle_whose_statements_share_their_closing_day_reads_its_months():
    """R13: the shape the Canadian parsers read, each period starting on the day the last one closed (January and the
    two Marches by B11's rule): 91 days covered, 3 months."""
    shared = [("2031-01-16", "2031-02-16"), ("2031-02-16", "2031-03-16"), ("2031-03-16", "2031-04-16")]
    assert _months(_periods_package(shared)["totals"]) == (3, 30000.0, 10000.0)


def test_a_business_day_cycle_slipping_around_the_fifteenth_reads_its_months():
    variable = [("2031-01-15", "2031-02-14"), ("2031-02-15", "2031-03-16"), ("2031-03-17", "2031-04-15")]
    assert _months(_periods_package(variable)["totals"]) == (3, 30000.0, 10000.0)


def test_a_statement_of_fifty_nine_days_reads_two_months():
    """R13 (older than B11): a statement longer than a month counted one month, so its True per month was its total."""
    totals = _periods_package([("2031-01-01", "2031-02-28", 20000.0)])["totals"]
    assert _months(totals) == (2, 20000.0, 10000.0)
    assert totals["statement_periods"] == 1  # one statement, two months: the dashboard prints both


def test_two_accounts_on_the_sixteenth_cycle_read_three_months_and_sum_by_month():
    """Each account's days floor the months on its own (the largest account wins); the accounts' True sums."""
    contoso = [_period_payload(start, end, number=_CONTOSO_NUMBER) for start, end in _SIXTEENTH_CYCLE]
    fabrikam = [_period_payload(start, end, 5000.0, number=_FABRIKAM_NUMBER) for start, end in _SIXTEENTH_CYCLE]
    totals = _package(*contoso, *fabrikam)["totals"]
    assert _months(totals) == (3, 45000.0, 15000.0)
    assert totals["statement_periods"] == 6


@pytest.mark.parametrize(("periods", "months"), [
    # B11's calendar months, which the floor never lowers: January to March; a gap (January, March); two half-month
    # January statements; one 20-day statement.
    ([("2031-01-01", "2031-01-31"), ("2031-02-01", "2031-02-28"), ("2031-03-01", "2031-03-31")], 3),
    ([("2031-01-01", "2031-01-31"), ("2031-03-01", "2031-03-31")], 2),
    ([("2031-01-01", "2031-01-15"), ("2031-01-16", "2031-01-31")], 1),
    ([("2031-01-05", "2031-01-24")], 1),
])
def test_calendar_month_statements_keep_their_month_count(periods, months):
    assert _periods_package(periods)["totals"]["months"] == months


def test_twelve_calendar_months_read_twelve():
    from datetime import date, timedelta

    periods = [(f"2031-{month:02d}-01", (date(2031 + month // 12, month % 12 + 1, 1) - timedelta(days=1)).isoformat())
               for month in range(1, 13)]
    totals = _periods_package(periods)["totals"]
    assert totals["months"] == 12 and totals["avg_monthly_true_revenue"] == 10000.0


def test_the_month_labels_and_the_tiers_are_unchanged():
    """R13 changes the divisor only: each statement keeps the month holding most of its days (January, March, March:
    the Monthly Statements' Month/Year labels, owner request 7ea2559), and each credit its tier."""
    from webapp.app import _statement_month

    package = _periods_package(_SIXTEENTH_CYCLE)
    assert [_statement_month(row["period_start"], row["period_end"]) % 12 for row in package["monthly"]] == [0, 2, 2]
    alone = [_periods_package([period]) for period in _SIXTEENTH_CYCLE]
    assert [row["true_revenue_total"] for row in package["documents"]] == [
        single["documents"][0]["true_revenue_total"] for single in alone]
    assert sorted((row["classification"]["revenue_tier"], row["classification"].get("revenue_tier_reason"))
                  for row in package["transactions"] if row["amount"] > 0) == sorted(
        (row["classification"]["revenue_tier"], row["classification"].get("revenue_tier_reason"))
        for single in alone for row in single["transactions"] if row["amount"] > 0)


def test_the_covered_days_of_a_period():
    from datetime import date

    from webapp.app import _covered_days

    assert len(_covered_days("2031-01-16", "2031-02-15")) == 31
    assert _covered_days("2031-03-01", "2031-03-01") == {date(2031, 3, 1)}
    assert _covered_days("2031-03-02", "2031-03-01") == set()  # an end before the start reads no day
    assert _covered_days(None, "2031-03-01") == set() and _covered_days("2031-03-01", "2031-02-30") == set()
    assert len(_covered_days("2030-01-01", "2032-12-31")) == 400  # capped as _statement_month is


# ---------------------------------------------------------------- Owner ruling 2026-10-02, R2-OW03: the non-revenue
# breakdown of the package (the underwriter's Q3; spec §9.2, §10.8). Fabricated CONTOSO statements: March prints two
# Zelle deposits (600 and 400), April one (500).

_ZELLE_MARCH = ROWS + [(10, "ZELLE PAYMENT FROM PAT SAMPLE CONF 1", 600.0),
                       (11, "ZELLE PAYMENT FROM SAMPLE CATERING CONF 2", 400.0)]
_ZELLE_APRIL = ROWS + [(10, "ZELLE PAYMENT FROM FABRIKAM SUPPLY CONF 3", 500.0)]
_ZELLE_TOTAL = {"zelle_excluded": {"count": 3, "total": 1500.0}}


def test_the_package_sums_the_non_revenue_breakdown_over_its_members():
    from webapp.app import _analysis_rows, _package_rows
    package = _package(_payload(_ZELLE_MARCH), _payload(_ZELLE_APRIL, month=4), zelle=False)
    totals = package["totals"]
    assert [document["non_revenue_by_reason"] for document in package["documents"]] == [
        {"zelle_excluded": {"count": 2, "total": 1000.0}}, {"zelle_excluded": {"count": 1, "total": 500.0}}]
    assert totals["non_revenue_by_reason"] == _ZELLE_TOTAL
    assert (totals["non_revenue_total"], totals["non_revenue_count"]) == (1700.0, 5)
    assert totals["true_revenue_total"] == 2000.0  # no tier or figure moves: the breakdown only names what is there
    rows = _package_rows(package)
    assert ("revenue_tier", "non_revenue.zelle_excluded.count", 3) in rows
    assert ("revenue_tier", "non_revenue.zelle_excluded.total", 1500.0) in rows
    assert ("document_1.revenue_tier", "non_revenue.zelle_excluded.total", 1000.0) in rows
    assert ("document_2.revenue_tier", "non_revenue.zelle_excluded.count", 1) in rows
    assert not any(field == "non_revenue_by_reason" for _section, field, _value in rows)
    statement_rows = _analysis_rows(_payload(_ZELLE_MARCH))
    assert ("revenue_tier", "non_revenue.zelle_excluded.count", 2) in statement_rows
    assert ("revenue_tier", "non_revenue.zelle_excluded.total", 1000.0) in statement_rows


def test_a_repeated_statement_adds_nothing_to_the_breakdown():
    march, april = _payload(_ZELLE_MARCH), _payload(_ZELLE_APRIL, month=4)
    totals = _package(march, copy.deepcopy(march), april, zelle=False)["totals"]
    assert totals["duplicate_documents"] == 1
    assert totals["non_revenue_by_reason"] == _ZELLE_TOTAL


def test_a_member_whose_revenue_is_not_established_still_shows_its_non_revenue():
    """§10.4: Non-revenue stays where True is N/A (its rows are known non-revenue), so the breakdown does too."""
    partial = _payload(_ZELLE_APRIL, month=4)
    partial["metrics"]["deposits_source"] = "summary"
    partial["metrics"]["effective_total_deposits"] = 99999.0
    package = _package(_payload(_ZELLE_MARCH), partial, zelle=False)
    totals = package["totals"]
    assert totals["true_revenue_total"] is None and totals["revenue_unestablished_documents"] == ["job-2"]
    assert totals["non_revenue_by_reason"] == _ZELLE_TOTAL
    unestablished = package["documents"][1]
    assert not unestablished["revenue_established"]
    assert unestablished["non_revenue_by_reason"] == {"zelle_excluded": {"count": 1, "total": 500.0}}


def test_a_package_with_no_statement_analysed_keeps_an_empty_breakdown():
    """Audit round 2, R2-B15 (R54): with no completed member True, Verified, Counted and Held are None; the
    non-revenue breakdown is not nulled with them (it is empty: no member counted a row)."""
    from webapp.app import _package_analysis
    from webapp.jobs import Job
    totals = _package_analysis([Job(id="sample", filename="sample.pdf", status="error", analysis=None,
                                    error="fabricated failure")])["totals"]
    assert totals["completed"] == 0 and totals["true_revenue_total"] is None
    assert totals["non_revenue_by_reason"] == {}


def test_a_mixed_currency_package_refuses_the_breakdown_s_money_and_keeps_its_counts():
    from webapp.app import _package_rows
    cad = _payload(_ZELLE_APRIL, month=4)
    cad["statement"]["currency"] = "CAD"
    package = _package(_payload(_ZELLE_MARCH), cad, zelle=False)
    totals = package["totals"]
    assert totals["cross_currency_totals_refused"] is True
    assert totals["non_revenue_by_reason"] == {"zelle_excluded": {"count": 3, "total": None}}
    # Each document row keeps its own denominated figures.
    assert [document["non_revenue_by_reason"] for document in package["documents"]] == [
        {"zelle_excluded": {"count": 2, "total": 1000.0}}, {"zelle_excluded": {"count": 1, "total": 500.0}}]
    rows = _package_rows(package)
    assert ("revenue_tier", "non_revenue.zelle_excluded.total", "") in rows
    assert ("revenue_tier", "non_revenue.zelle_excluded.count", 3) in rows
    assert ("document_2.revenue_tier", "non_revenue.zelle_excluded.total", 500.0) in rows


# ---------------------------------------------------------------- The owner's amendment of 2026-10-06 to the
# underwriter's Q3 (R2-OW17; spec §9.2, §10.8, §11): "Mark Zelle Payments as True Revenue", Yes by default. The four
# breakdown tests above run under No; these are their Yes twins.

def test_yes_the_package_counts_its_members_zelle_deposits():
    package = _package(_payload(_ZELLE_MARCH), _payload(_ZELLE_APRIL, month=4))
    totals = package["totals"]
    assert totals["non_revenue_by_reason"] == {}
    assert totals["true_revenue_total"] == 3000.0  # 2,000.00 under No, plus March's two counted Zelle deposits
    # April's Zelle sender is also debited by the statement: held, out of True.
    assert totals["zelle_deposits"] == {
        "counted_as_true_revenue": True, "setting_applied": True, "count": 3, "total": 1500.0,
        "by_tier": {"counted_flagged": {"count": 2, "total": 1000.0}, "excluded_pending_review": {"count": 1,
                                                                                                  "total": 500.0}}}
    assert [document["zelle_deposits"]["count"] for document in package["documents"]] == [2, 1]
    # The member withholding denominator is the counted reading's (True revenue, R2-OW14's default basis).
    assert [document["withholding_denominator"] for document in package["documents"]] == [2000.0, 1000.0]


def test_yes_a_repeated_statement_adds_nothing_to_the_zelle_figures():
    march, april = _payload(_ZELLE_MARCH), _payload(_ZELLE_APRIL, month=4)
    totals = _package(march, copy.deepcopy(march), april)["totals"]
    assert totals["duplicate_documents"] == 1
    assert (totals["zelle_deposits"]["count"], totals["zelle_deposits"]["total"]) == (3, 1500.0)


def test_yes_a_member_whose_revenue_is_not_established_still_shows_its_zelle_figures():
    partial = _payload(_ZELLE_APRIL, month=4)
    partial["metrics"]["deposits_source"] = "summary"
    partial["metrics"]["effective_total_deposits"] = 99999.0
    package = _package(_payload(_ZELLE_MARCH), partial)
    assert package["totals"]["true_revenue_total"] is None
    assert package["totals"]["zelle_deposits"]["count"] == 3
    assert package["documents"][1]["zelle_deposits"]["count"] == 1


def test_yes_a_mixed_currency_package_refuses_the_zelle_money_and_keeps_its_counts():
    from webapp.app import _package_rows
    cad = _payload(_ZELLE_APRIL, month=4)
    cad["statement"]["currency"] = "CAD"
    package = _package(_payload(_ZELLE_MARCH), cad)
    figures = package["totals"]["zelle_deposits"]
    assert (figures["count"], figures["total"]) == (3, None)
    assert figures["by_tier"] == {"counted_flagged": {"count": 2, "total": None},
                                  "excluded_pending_review": {"count": 1, "total": None}}
    assert package["documents"][1]["zelle_deposits"]["total"] == 500.0
    rows = _package_rows(package)
    assert ("revenue_tier", "zelle_deposits.total", "") in rows
    assert ("revenue_tier", "zelle_deposits.count", 3) in rows


def test_yes_z1_turns_the_package_gate_on():
    from tests import zelle_setting_fixtures as fx
    assert _package(fx.case("Z1"))["totals"]["revenue_review_required"] is True
    assert _package(fx.case("Z1"), zelle=False)["totals"]["revenue_review_required"] is False


def test_yes_a_member_analysed_before_the_setting_is_named_beside_the_others():
    """One member with the counted reading's edits, one analysed between the Zelle policy and the setting (its edits
    absent): the package prints both members' parts and says the setting is not applied everywhere."""
    from tests import zelle_setting_fixtures as fx
    older = fx.case("Z2")
    older.pop("zelle_counted_reading")
    package = _package(fx.case("Z1"), older)
    figures = package["totals"]["zelle_deposits"]
    assert figures["setting_applied"] is False and figures["counted_as_true_revenue"] is True
    assert figures["by_tier"] == {"counted_flagged": {"count": 1, "total": 1234.56},
                                  "excluded_pending_review": {"count": 3, "total": 6500.0},
                                  "non_revenue": {"count": 1, "total": 1500.0}}
    assert [document["zelle_deposits"]["setting_applied"] for document in package["documents"]] == [True, False]


def test_no_a_member_without_the_figures_contributes_its_excluded_zelle():
    """Under No a fresh member carries no figures; beside one that does (a confirmed Zelle deposit), its excluded Zelle
    deposits are its non-revenue part, so the package figure covers every member."""
    from tests import zelle_setting_fixtures as fx
    from analysis.revenue import apply_serialized_revenue_review
    confirmed = apply_serialized_revenue_review(fx.case("Z1"), source_location="transaction:2", decision="confirm")
    package = _package(confirmed, fx.case("Z2"), zelle=False)
    figures = package["totals"]["zelle_deposits"]
    assert figures["counted_as_true_revenue"] is False and figures["setting_applied"] is True
    assert figures["by_tier"] == {"verified": {"count": 1, "total": 1234.56},
                                  "non_revenue": {"count": 4, "total": 8000.0}}
    assert "zelle_deposits" not in package["documents"][1]


# Exports (spec §10.8): the readable rows, the row tag and the `zelle` column.

def _download(job_payload, fmt, *, zelle):
    from webapp.app import _analysis_csv, _displayed
    from webapp.settings import DEFAULTS
    served = _displayed(job_payload, settings={**DEFAULTS, "zelle_true_revenue": zelle}, export=True)
    return served if fmt == "json" else _analysis_csv(served)


def test_a_yes_download_of_z1_prints_the_readable_rows_and_the_zelle_column():
    from tests import zelle_setting_fixtures as fx
    from webapp.app import _analysis_rows, _displayed, _posted_credit_table
    from webapp.settings import DEFAULTS
    served = _displayed(fx.case("Z1"), settings={**DEFAULTS, "zelle_true_revenue": True}, export=True)
    rows = _analysis_rows(served)
    assert ("revenue_tier", "zelle_deposits.setting", "Yes") in rows
    assert ("revenue_tier", "zelle_deposits.count", 4) in rows and ("revenue_tier", "zelle_deposits.total", 7734.56) in rows
    assert ("revenue_tier", "zelle_deposits.counted_flagged.count", 1) in rows
    assert ("revenue_tier", "zelle_deposits.excluded_pending_review.total", 6500.0) in rows
    assert ("revenue_tier", "zelle_deposits.setting_applied", True) in rows
    assert not any(section == "metrics" and field == "zelle_deposits" for section, field, _value in rows)
    table = _posted_credit_table(served)
    assert table[0][-1] == "zelle"
    assert [row[3] for row in table[1:] if row[-1] == "Zelle"] == [fx.PAT, fx.FABRIKAM_1, fx.FABRIKAM_2, fx.OWN]
    assert sum(1 for transaction in served["statement"]["transactions"] if transaction.get("zelle_deposit")) == 4


def test_a_package_json_keeps_the_row_tag_and_its_ledger_table_the_zelle_column():
    from tests import zelle_setting_fixtures as fx
    from webapp.app import _package_rows, _package_transaction_table
    package = _package(fx.case("Z1"))
    assert sum(1 for row in package["transactions"] if row.get("zelle_deposit") is True) == 4
    table = _package_transaction_table(package)
    assert table[0][-1] == "zelle" and sum(1 for row in table[1:] if row[-1] == "Zelle") == 4
    rows = _package_rows(package)
    assert ("revenue_tier", "zelle_deposits.setting", "Yes") in rows
    assert ("document_1.revenue_tier", "zelle_deposits.count", 4) in rows
    assert not any(field == "zelle_deposits" for _section, field, _value in rows)
    no_table = _package_transaction_table(_package(fx.case("Z1"), zelle=False))
    assert no_table[0][-1] == "review_status"


def test_a_no_download_of_a_fresh_z1_and_every_zelle_free_download_are_today_s():
    """Today's download is the stored payload served without the counted reading's edits (R2-OW16's payload, which
    tests/fixtures/zelle_setting_no_view.json pins): the No download of a fresh analysis equals it byte for byte, and a
    Zelle-free statement's downloads are the same in both modes."""
    from tests import zelle_setting_fixtures as fx
    fresh = fx.case("Z1")
    today = copy.deepcopy(fresh)
    today.pop("zelle_counted_reading")
    for fmt in ("csv", "json"):
        produced = _download(fresh, fmt, zelle=False)
        expected = _download(today, fmt, zelle=False)
        assert (produced if fmt == "csv" else json.dumps(produced)) == (
            expected if fmt == "csv" else json.dumps(expected))
        free = fx.payload(fx.FREE)
        assert _download(free, fmt, zelle=True) == _download(free, fmt, zelle=False)
    assert "zelle" not in _download(fresh, "csv", zelle=False).splitlines()[0]
    assert ",zelle\r" not in _download(fresh, "csv", zelle=False)
