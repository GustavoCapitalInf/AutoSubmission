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
