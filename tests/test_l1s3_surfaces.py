"""The exports, the package, the gate's verdict and the discovery row (L1-S3).

The second half of the per-reader proof; `tests/test_l1s3_readers.py` holds the
first. Every payload is CONSTRUCTED, and every branch exercised here is
unreachable in production at this tree.
"""
from __future__ import annotations

import copy

import pytest

from analysis.payload_shape import PayloadShapeError
from tests.l1s3_payloads import account_payload, document_payload


# --- webapp/app.py: the exports ---------------------------------------------


def test_the_export_sheet_renders_every_account():
    from webapp.app import _analysis_rows

    payload = document_payload()
    rows = _analysis_rows(payload)
    sections = {section for section, _field, _value in rows}
    assert "document" in sections
    assert {"account_1.statement", "account_2.statement"} <= sections
    # The collision the section prefix exists to stop: a flat sheet keyed on
    # `(section, field)` would let the second account overwrite the first.
    endings = [
        (section, value) for section, field, value in rows
        if field == "ending_balance" and section.endswith("statement")
    ]
    assert len(endings) == 2
    assert endings[0][1] != endings[1][1]


def test_the_export_sheet_carries_the_account_count_and_no_chosen_account():
    from webapp.app import _analysis_rows

    rows = _analysis_rows(document_payload(outcomes=("validated",) * 3))
    document_rows = {field: value for section, field, value in rows
                     if section == "document"}
    assert document_rows["account_count"] == 3
    assert "statement" not in {section for section, _f, _v in rows}


def test_the_export_sheet_is_unchanged_for_one_account():
    from webapp.app import _analysis_rows

    payload = account_payload()
    assert _analysis_rows(payload) == _analysis_rows(copy.deepcopy(payload))
    assert {section for section, _f, _v in _analysis_rows(payload)} == {
        "statement", "metrics", "quality", "integrity", "reconciliation",
        "detection", "adb", "adb_validation", "adb_daily_balance",
    }


def test_the_csv_export_of_a_document_is_not_empty():
    """Measured before the teaching: zero rows, for a document that reconciled."""
    from webapp.app import _analysis_csv

    text = _analysis_csv(document_payload())
    assert "account_1.statement" in text
    assert "account_2.statement" in text


def test_the_masked_route_is_account_count_agnostic():
    """No branch needed and none added: it is keyed on KEY NAMES."""
    from webapp.app import _masked

    masked = _masked(document_payload())
    assert set(masked) == {"document", "accounts"}
    assert len(masked["accounts"]) == 2
    for index, account in enumerate(masked["accounts"]):
        assert account["statement"]["account_number"] == f"****{index:04d}"


# --- webapp/app.py: the package ---------------------------------------------


class _Job:
    """A package member, with only the attributes `_package_analysis` reads."""

    def __init__(self, ident, analysis, filename="synthetic.pdf"):
        self.id = ident
        self.filename = filename
        self.status = "done"
        self.analysis = analysis
        self.analysis_error = None
        self.error = None
        self.content_sha256 = None


def test_package_membership_requires_each_accounts_own_validation():
    from webapp.app import _package_members

    job = _Job("job-1", document_payload(outcomes=("validated", "withheld")))
    members, excluded = _package_members([job])
    assert [index for _job, _analysis, index, _count in members] == [1]
    assert excluded == [{
        "job_id": "job-1", "account_index": 2, "account_count": 2,
        "outcome": "withheld", "reason": "withheld_adb",
    }]


def test_an_excluded_account_is_published_not_dropped():
    from webapp.app import _package_analysis

    job = _Job("job-1", document_payload(outcomes=("validated", "review")))
    package = _package_analysis([job])
    assert package["excluded_accounts"][0]["account_index"] == 2
    assert len(package["documents"]) == 1
    assert package["documents"][0]["id"] == "job-1#account_1"
    assert package["documents"][0]["account_count"] == 2


def test_a_single_account_package_carries_neither_new_key():
    from webapp.app import _package_analysis

    package = _package_analysis([_Job("job-1", account_payload())])
    assert "excluded_accounts" not in package
    assert package["documents"][0]["id"] == "job-1"
    assert "account_index" not in package["documents"][0]
    assert "account_count" not in package["documents"][0]


def test_the_package_refuses_two_accounts_of_one_document_with_one_digest():
    """The no-average-over-one-content-digest property, standing where the
    cross-account arithmetic happens."""
    from webapp.app import _package_members

    payload = document_payload()
    payload["accounts"][1] = copy.deepcopy(payload["accounts"][0])
    with pytest.raises(ValueError, match="document_publishes_duplicate_account"):
        _package_members([_Job("job-1", payload)])


def test_two_accounts_of_one_document_are_not_package_duplicates():
    """`_package_duplicates` keys on the PDF's content hash, and two accounts
    of one document are one job — so they can never be counted as two."""
    from webapp.app import _package_analysis

    package = _package_analysis([_Job("job-1", document_payload())])
    assert package["totals"]["duplicate_documents"] == 0
    assert package["duplicates"] == []


def test_every_member_is_its_own_row_in_the_package_export():
    from webapp.app import _package_analysis, _package_rows

    package = _package_analysis([_Job("job-1", document_payload())])
    rows = _package_rows(package)
    sections = {section for section, _field, _value in rows}
    assert {"document_1", "document_2"} <= sections
    ids = {value for section, field, value in rows
           if section.startswith("document_") and field == "id"}
    assert ids == {"job-1#account_1", "job-1#account_2"}


def test_the_package_never_folds_two_accounts_into_one_member():
    from webapp.app import _package_analysis

    package = _package_analysis([_Job("job-1", document_payload())])
    openings = sorted(row["beginning_balance"] for row in package["documents"])
    assert openings == [1000.0, 1001.0]


# --- webapp/jobs.py and the reviewer's decision -----------------------------


def test_a_reviewers_posting_is_found_in_any_account():
    from webapp.jobs import _classification_for

    payload = document_payload()
    payload["accounts"][1]["statement"]["transactions"][0]["classification"][
        "source_location"] = "transaction:99"
    found = _classification_for(payload, "transaction:99")
    assert found is not None and found["source_location"] == "transaction:99"
    assert _classification_for(payload, "transaction:not-there") is None


def test_a_reviewers_decision_reaches_a_posting_in_the_second_account():
    from analysis.revenue import apply_serialized_revenue_review

    payload = document_payload()
    second = payload["accounts"][1]["statement"]["transactions"][0]["classification"]
    second["source_location"] = "transaction:99"
    second["revenue_initial_classification"] = "unverified_deposit"
    second["revenue_classification"] = "unverified_deposit"
    apply_serialized_revenue_review(
        payload, source_location="transaction:99", decision="reject")
    assert second["revenue_classification"] == "non_revenue"


# --- benchmark and the two forensic audits ----------------------------------


def test_the_benchmark_refuses_a_document_it_cannot_declare_a_second_value_for():
    from benchmark.ourside import OurFileResult

    result = OurFileResult(relative_path="synthetic.pdf", source_type="digital/native",
                           markdown="", payload=document_payload())
    for view in ("statement", "metrics", "reconciliation", "detection"):
        with pytest.raises(PayloadShapeError, match="reader_is_account_scope"):
            getattr(result, view)


def test_the_benchmark_still_answers_todays_payload():
    from benchmark.ourside import OurFileResult

    payload = account_payload()
    result = OurFileResult(relative_path="synthetic.pdf", source_type="digital/native",
                           markdown="", payload=payload)
    assert result.statement == payload["statement"]
    assert result.metrics == payload["metrics"]


def test_the_forensic_reader_refuses_where_it_used_to_raise_a_bare_key_error():
    """The one loud reader was loud by accident of punctuation, not by a guard.
    The `KeyError` is what the tree used to produce; the named refusal is what
    the taught reader produces instead."""
    from analysis.payload_shape import refuse_document_payload

    payload = document_payload()
    with pytest.raises(KeyError):
        _ = payload["statement"]
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope"):
        refuse_document_payload(
            payload, surface="balance_forensic_audit.py::audit_source")


# --- corpus_gate -------------------------------------------------------------


def test_the_gate_verdict_is_unchanged_for_one_account():
    import corpus_gate

    payload = account_payload()
    document, accounts = corpus_gate.document_verdicts(payload)
    assert accounts == (document,)
    assert document == corpus_gate._Verdict("validated", (), (), "clear", False)
    assert document.account_index is None


def test_the_gate_returns_one_verdict_per_account_plus_the_documents():
    import corpus_gate

    payload = document_payload(outcomes=("validated", "review"))
    document, accounts = corpus_gate.document_verdicts(payload)
    assert [verdict.account_index for verdict in accounts] == [1, 2]
    assert [verdict.outcome for verdict in accounts] == ["validated", "review"]
    assert document.outcome == "review"
    assert document.risk_level == "review"


def test_the_document_verdict_carries_no_account_scope_flag():
    """An account-scope flag is a fact about THAT account; reading it at the
    document would say the whole document carries it."""
    import corpus_gate

    payload = document_payload(outcomes=("review", "validated"))
    document, accounts = corpus_gate.document_verdicts(payload)
    assert accounts[0].flags == ("running_balance_breaks",)
    assert document.flags == ()


def test_the_pinned_published_outcome_still_compares_equal():
    import corpus_gate

    document, _accounts = corpus_gate.document_verdicts(account_payload())
    assert document == corpus_gate.PUBLISHED_OUTCOME


def test_the_gate_refuses_to_pin_a_denomination_it_cannot_key():
    import corpus_gate

    result = corpus_gate.Result()
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope"):
        corpus_gate.check_currency(
            result, ["synthetic.pdf"], {"synthetic.pdf": document_payload()})


# --- discovery ---------------------------------------------------------------


def _row():
    from discovery.runner import DocumentRow

    return DocumentRow(relative_path="a.pdf", folder_label="F",
                       content_sha256="0" * 64, byte_size=1)


def test_the_discovery_row_carries_the_document_and_no_account():
    from discovery.runner import _project_accounts

    row = _row()
    _project_accounts(row, document_payload(outcomes=("validated",) * 3))
    assert row.account_last4 is None
    assert row.account_count == 3
    assert row.statement_bank == "SYNTHETIC TEST BANK"


def test_the_discovery_row_is_unchanged_for_one_account():
    from discovery.runner import _project_accounts

    row = _row()
    _project_accounts(row, account_payload())
    assert row.account_last4 == "0000"
    assert row.account_count == 1


def test_a_document_whose_accounts_disagree_on_the_issuer_refuses():
    from discovery.runner import _project_accounts

    payload = document_payload()
    payload["accounts"][1]["statement"]["bank"] = "ANOTHER SYNTHETIC BANK"
    with pytest.raises(ValueError, match="document_accounts_disagree_on_issuer"):
        _project_accounts(_row(), payload)


def test_the_row_field_list_carries_the_new_column():
    from discovery.report import ROW_FIELDS

    assert "account_count" in ROW_FIELDS
    assert set(ROW_FIELDS) <= set(_row().as_dict())
