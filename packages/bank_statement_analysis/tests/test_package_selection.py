"""Which jobs and accounts a package reads once the shorter printouts are left out: a document whose every account
another statement prints is left out whole, in its listed place; one superseded account of a document is excluded in
its own place and the document stays, even with no member left, its exclusions and omissions published. Fabricated
CONTOSO BANK statements of CONTOSO BAKERY LLC, April 2031: each account's full month, and a document printing a
month-to-date printout of several accounts."""
from __future__ import annotations

import copy

from analysis.package import package_analysis
from analysis.pipeline import DocumentReport, identify_internal_transfers
from analysis.serialization import document_report_to_dict
from tests.test_webapp_app import _APRIL, _MARCH, _listed, _printed, _printed_report, _r15_document

OPENING = {"1010": 21000.0, "2020": 9000.0, "3030": 4000.0, "4040": 7000.0}
RATIFIED = {"label": "CONTOSO SECTION B", "reason": "printed_dormancy_declaration", "posting_count": 0}


def _april(last4):
    """Account `last4`'s April statement, alone in its job."""
    return _listed(f"a{last4}", _printed(f"00000000{last4}", _APRIL, start="2031-04-01", end="2031-04-30",
                                         opening=OPENING[last4]), content=f"a{last4}")


def _printout(last4):
    """Account `last4`'s April 1-20 printout: its first two rows, which its April statement prints."""
    return _printed_report(f"00000000{last4}", _APRIL[:2], start="2031-04-01", end="2031-04-20",
                           opening=OPENING[last4]).accounts[0]


def _document(job_id, accounts, *, unvalidated=(), outdated=False, omitted=None):
    """One job printing `accounts`; the 1-based `unvalidated` ones fail their own quality check."""
    transfers, notes = identify_internal_transfers(accounts)
    payload = document_report_to_dict(DocumentReport(accounts=accounts, internal_transfers=transfers,
                                                     integrity_notes=notes, account_roster=[],
                                                     document_period=("2031-04-01", "2031-04-20")))
    for index in unvalidated:
        payload["accounts"][index - 1]["quality"]["corporate_use"] = "summary_only"
    if outdated:
        for account in payload["accounts"]:
            for row in account["statement"]["transactions"]:
                row["classification"].pop("classification_version")
    if omitted is not None:
        payload["document"]["omitted_sections"] = omitted
    return _listed(job_id, payload, content=job_id)


def _excluded(package):
    return [(entry["job_id"], entry["account_index"], entry["reason"], entry.get("duplicate_of"))
            for entry in package.get("excluded_accounts") or []]


def _selection(package):
    totals = package["totals"]
    return {
        "documents": [(row["id"], row.get("duplicate_of"), row.get("duplicate_reason")) for row in package["documents"]],
        "excluded": _excluded(package),
        "counts": (totals["documents"], totals["duplicate_documents"], totals["distinct_documents"],
                   totals.get("duplicate_accounts")),
    }


def test_a_document_whose_every_account_another_statement_prints_is_left_out_whole():
    whole = _document("doc", [_printout("1010"), _printout("2020")])
    package = package_analysis([_april("1010"), whole, _april("2020")])
    assert _selection(package) == {
        "documents": [("a1010", None, None), ("a2020", None, None), ("doc", "a1010", "superseded_interim")],
        "excluded": [], "counts": (3, 1, 2, None)}
    assert package["totals"]["true_revenue_total"] == 40000.0


def test_left_out_documents_keep_their_listed_order():
    whole = _document("doc", [_printout("1010"), _printout("2020")])
    copy_of_1010 = _listed("again", copy.deepcopy(_april("1010").analysis), content="a1010")
    package = package_analysis([whole, _april("1010"), copy_of_1010, _april("2020")])
    assert _selection(package)["documents"] == [
        ("a1010", None, None), ("a2020", None, None), ("doc", "a1010", "superseded_interim"),
        ("again", "a1010", "same_content")]


def test_a_left_out_document_takes_its_older_rules_flag_with_it():
    whole = _document("doc", [_printout("1010"), _printout("2020")], outdated=True)
    assert package_analysis([_april("1010"), whole, _april("2020")])["analysis_rules_outdated"] is False
    partial = _document("doc", [_printout("1010"), _printout("3030")], outdated=True)
    assert package_analysis([partial, _april("1010")])["analysis_rules_outdated"] is True


def test_one_superseded_account_of_a_document_is_excluded_and_its_sibling_stays():
    partial = _document("doc", [_printout("1010"), _printout("3030")])
    package = package_analysis([_april("1010"), partial])
    assert _selection(package) == {
        "documents": [("a1010", None, None), ("doc#account_2", None, None)],
        "excluded": [("doc", 1, "superseded_interim", "a1010")], "counts": (2, 0, 2, 1)}


def test_a_document_left_with_no_member_keeps_its_exclusions_and_omissions():
    """Its other account did not validate, so every account it admitted is superseded, but not every account it
    prints: the document stays, listing both exclusions and its ratified omission."""
    document = _document("doc", [_printout("1010"), _printout("3030")], unvalidated=(2,), omitted=[RATIFIED])
    package = package_analysis([document, _april("1010")])
    assert _selection(package) == {
        "documents": [("a1010", None, None)],
        "excluded": [("doc", 1, "superseded_interim", "a1010"), ("doc", 2, "quality_needs_review", None)],
        "counts": (2, 0, 2, 1)}
    assert package["omitted_sections"] == [RATIFIED]


def test_a_superseded_account_beside_a_repeated_one_is_excluded_in_its_place():
    march = _listed("m5050", _printed("000000005050", _MARCH, start="2031-03-01", end="2031-03-31", opening=1500.0),
                    content="m5050")
    repeat = _printed_report("000000005050", _MARCH, start="2031-03-01", end="2031-03-31", opening=1500.0).accounts[0]
    package = package_analysis([march, _april("1010"), _document("doc", [_printout("1010"), repeat])])
    assert _selection(package) == {
        "documents": [("m5050", None, None), ("a1010", None, None)],
        "excluded": [("doc", 1, "superseded_interim", "a1010"), ("doc", 2, "duplicate_statement", "m5050")],
        "counts": (3, 0, 3, 2)}


def test_exclusions_follow_the_jobs_and_then_the_accounts():
    document = _document("doc", [_printout("3030"), _printout("1010"), _printout("4040")], unvalidated=(1,))
    held = _r15_document(2, main="held", job_id="held")
    package = package_analysis([_april("1010"), document, held])
    assert _excluded(package) == [("doc", 1, "quality_needs_review", None), ("doc", 2, "superseded_interim", "a1010"),
                                  ("held", None, "main_account_unverified", None)]
    assert [row["id"] for row in package["documents"]] == ["a1010", "doc#account_3"]
