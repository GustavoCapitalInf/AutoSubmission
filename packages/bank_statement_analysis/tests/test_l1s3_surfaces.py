"""The exports, the package, the gate's verdict and the discovery row (L1-S3).

The second half of the per-reader proof; `tests/test_l1s3_readers.py` holds the
first. Every payload is CONSTRUCTED, and every branch exercised here is
unreachable in production at this tree.
"""
from __future__ import annotations

import copy
import pathlib

import pytest

from analysis.payload_shape import PayloadShapeError
from tests.l1s3_payloads import account_payload, document_payload, omission


# --- webapp/statement_export.py and export_view.py: the exports ------------


def test_the_export_sheet_renders_every_account():
    from webapp.statement_export import _analysis_rows

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
    from webapp.statement_export import _analysis_rows

    rows = _analysis_rows(document_payload(outcomes=("validated",) * 3))
    document_rows = {field: value for section, field, value in rows
                     if section == "document"}
    assert document_rows["account_count"] == 3
    assert "statement" not in {section for section, _f, _v in rows}


def test_the_export_sheet_is_unchanged_for_one_account():
    from webapp.statement_export import _analysis_rows

    payload = account_payload()
    assert _analysis_rows(payload) == _analysis_rows(copy.deepcopy(payload))
    assert {section for section, _f, _v in _analysis_rows(payload)} == {
        "statement", "metrics", "quality", "integrity", "reconciliation",
        "detection", "adb", "adb_validation", "adb_daily_balance",
    }


def test_the_csv_export_of_a_document_is_not_empty():
    """Measured before the teaching: zero rows, for a document that reconciled."""
    from webapp.statement_export import analysis_csv

    text = analysis_csv(document_payload())
    assert "account_1.statement" in text
    assert "account_2.statement" in text


def test_the_masked_route_is_account_count_agnostic():
    """No branch needed and none added: it is keyed on KEY NAMES."""
    from webapp.export_view import masked

    served = masked(document_payload())
    assert set(served) == {"document", "accounts"}
    assert len(served["accounts"]) == 2
    for index, account in enumerate(served["accounts"]):
        assert account["statement"]["account_number"] == f"****{index:04d}"


# --- webapp/app.py: the package ---------------------------------------------


class _Job:
    """A package member, with only the attributes `package_analysis` reads."""

    def __init__(self, ident, analysis, filename="synthetic.pdf"):
        self.id = ident
        self.filename = filename
        self.status = "done"
        self.analysis = analysis
        self.analysis_error = None
        self.error = None
        # An obviously synthetic content identity, distinct per job, so the
        # member-set check has something real to key on and two separate jobs
        # are never mistaken for one document.
        self.content_sha256 = f"SYNTHETIC-{ident.upper()}"


def test_package_membership_requires_each_accounts_own_validation():
    from analysis.package.members import package_members

    job = _Job("job-1", document_payload(outcomes=("validated", "withheld")))
    members, excluded = package_members([job])
    assert [index for _job, _analysis, index, _count in members] == [1]
    # Audit round 2, R2-B15 (R15): each excluded account names its statement's file, for the package's notice.
    assert excluded == [{
        "job_id": "job-1", "filename": "synthetic.pdf", "account_index": 2, "account_count": 2,
        "outcome": "withheld", "reason": "withheld_adb",
    }]


def test_an_excluded_account_is_published_not_dropped():
    from analysis.package import package_analysis

    job = _Job("job-1", document_payload(outcomes=("validated", "review")))
    package = package_analysis([job])
    assert package["excluded_accounts"][0]["account_index"] == 2
    assert len(package["documents"]) == 1
    assert package["documents"][0]["id"] == "job-1#account_1"
    assert package["documents"][0]["account_count"] == 2


def test_a_single_account_package_carries_neither_new_key():
    from analysis.package import package_analysis

    package = package_analysis([_Job("job-1", account_payload())])
    assert "excluded_accounts" not in package
    assert package["documents"][0]["id"] == "job-1"
    assert "account_index" not in package["documents"][0]
    assert "account_count" not in package["documents"][0]


def test_the_package_refuses_two_accounts_of_one_document_with_one_digest():
    """The no-average-over-one-content-digest property, standing where the
    cross-account arithmetic happens."""
    from analysis.package.members import package_members

    payload = document_payload()
    payload["accounts"][1] = copy.deepcopy(payload["accounts"][0])
    with pytest.raises(ValueError, match="document_publishes_duplicate_account"):
        package_members([_Job("job-1", payload)])


def test_two_accounts_of_one_document_are_not_package_duplicates():
    """`package_duplicates` keys on the PDF's content hash, and two accounts
    of one document are one job — so they can never be counted as two."""
    from analysis.package import package_analysis

    package = package_analysis([_Job("job-1", document_payload())])
    assert package["totals"]["duplicate_documents"] == 0
    assert package["duplicates"] == []


def test_every_member_is_its_own_row_in_the_package_export():
    from webapp.package_export import _package_rows
    from analysis.package import package_analysis

    package = package_analysis([_Job("job-1", document_payload())])
    rows = _package_rows(package)
    sections = {section for section, _field, _value in rows}
    assert {"document_1", "document_2"} <= sections
    ids = {value for section, field, value in rows
           if section.startswith("document_") and field == "id"}
    assert ids == {"job-1#account_1", "job-1#account_2"}


def test_the_package_never_folds_two_accounts_into_one_member():
    from analysis.package import package_analysis

    package = package_analysis([_Job("job-1", document_payload())])
    openings = sorted(row["beginning_balance"] for row in package["documents"])
    assert openings == [1000.0, 1001.0]


# --- MAJOR-3: no published average over two accounts of one document --------


def _two_accounts_one_period():
    """One job publishing two DIFFERENT validated accounts over ONE period."""
    return _Job("job-1", document_payload(outcomes=("validated", "validated")))


def test_a_package_refuses_the_per_period_averages_over_two_accounts_of_one_document():
    """Design §6.5's fourth bullet. The L1-S3 review measured the halving: a
    package holding one job with two accounts over one statement period
    published every per-month average divided by TWO, because `months` counts
    members and each account is a member."""
    from analysis.package import package_analysis

    totals = package_analysis([_two_accounts_one_period()])["totals"]
    assert totals["cross_account_averages_refused"] is True
    assert totals["documents_with_several_members"] == 1
    for key in ("avg_monthly_credits", "avg_monthly_debits",
                "avg_monthly_cash_flow", "average_daily_balance",
                "monthly_lender_debits"):
        assert totals[key] is None, key
    # The SUMS stay: two accounts of one document really did move that money,
    # and adding them counts each posting once.
    assert totals["total_credits"] > 0


def test_the_duplicate_digest_refusal_does_not_catch_this_and_never_could():
    """The card implemented a duplicate-CONTENT-digest refusal, which fires
    only when two accounts publish IDENTICAL content. Two DIFFERENT accounts of
    one document pass it — which is why §6.5 asked for a member-set check
    keyed on the document, and this is that check."""
    from analysis.package.members import package_members

    members, excluded = package_members([_two_accounts_one_period()])
    assert len(members) == 2 and excluded == []
    shas = {member[0].content_sha256 for member in members}
    assert shas == {"SYNTHETIC-JOB-1"}  # one document identity, two members


def test_two_separate_documents_still_publish_their_averages():
    """The refusal is keyed on ONE document with several members, not on member
    count: two separate jobs are two documents and two periods."""
    from analysis.package import package_analysis

    totals = package_analysis([
        _Job("job-1", account_payload(0)),
        _Job("job-2", account_payload(1)),
    ])["totals"]
    assert "cross_account_averages_refused" not in totals
    assert totals["avg_monthly_credits"] is not None


def test_a_package_of_todays_payloads_carries_no_refusal_key():
    from analysis.package import package_analysis

    totals = package_analysis([_Job("job-1", account_payload())])["totals"]
    assert "cross_account_averages_refused" not in totals
    assert "documents_with_several_members" not in totals
    assert totals["avg_monthly_credits"] is not None


# --- Q10: surface the omission, do not demote -------------------------------


def test_a_ratified_omission_is_surfaced_by_the_package():
    """Q10. The document stays `validated` and the
    package says a section was established and not published."""
    from analysis.package import package_analysis

    payload = document_payload(outcomes=("validated",),
                               omitted_sections=(omission(),))
    package = package_analysis([_Job("job-1", payload)])
    assert package["totals"]["sibling_account_omission_detected"] is True
    assert package["totals"]["completeness"] == "partial"
    assert package["totals"]["omitted_section_count"] == 1
    assert package["omitted_sections"][0]["reason"] == "printed_dormancy_declaration"
    # ... and the account is still a member: surfacing never demotes.
    assert len(package["documents"]) == 1
    assert "excluded_accounts" not in package


def test_a_package_of_todays_payloads_carries_none_of_the_q10_keys():
    """The darkness property for Q10: absence IS today's package."""
    from analysis.package import package_analysis

    package = package_analysis([_Job("job-1", account_payload())])
    assert "sibling_account_omission_detected" not in package["totals"]
    assert "completeness" not in package["totals"]
    assert "omitted_section_count" not in package["totals"]
    assert "omitted_sections" not in package


def test_the_q10_surface_reaches_the_export_an_underwriter_reads():
    """A refusal that lives only in the JSON is invisible to the person the
    package is for."""
    from webapp.package_export import package_csv
    from analysis.package import package_analysis

    payload = document_payload(outcomes=("validated",),
                               omitted_sections=(omission(),))
    text = package_csv(package_analysis([_Job("job-1", payload)]))
    assert "sibling_account_omission_detected" in text
    assert "completeness" in text


def test_an_unratified_omission_is_not_surfaced_as_partial():
    """A defect dressed as a policy is worse than a defect. L1-C17 fails the
    document; the package excludes its accounts rather than calling it partial."""
    from analysis.package import package_analysis

    payload = document_payload(outcomes=("validated",),
                               omitted_sections=(omission("absence_of_parsed_rows"),))
    package = package_analysis([_Job("job-1", payload)])
    assert "sibling_account_omission_detected" not in package["totals"]
    assert package["excluded_accounts"][0]["reason"] == "document_omission_unratified"
    assert package["documents"] == []


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


def test_the_balance_audit_refuses_the_document_shape(monkeypatch, tmp_path):
    """The LEGACY INDEXING PATH — the one reader of the design's ten that raised
    at all, and the one this card's Proof section promised to pin.

    Its guard is the only thing standing between a document payload and the
    bare `KeyError` at the `payload["statement"]` two lines below it, and until
    the L1-S3 review (MAJOR-4) nothing exercised it: the whole 7,578-test suite
    and both censuses stayed green with the refusal moved into a dead branch.
    """
    import balance_forensic_audit as audit

    monkeypatch.setattr(audit, "source_markdown",
                        lambda path, **kwargs: ("markdown", "digital/native", b""))
    monkeypatch.setattr(audit, "analyze_document", lambda *a, **k: object())
    monkeypatch.setattr(audit, "document_report_to_dict",
                        lambda document: document_payload())
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope") as raised:
        audit.audit_source(tmp_path / "synthetic.pdf", tmp_path)
    assert "balance_forensic_audit.py::audit_source" in str(raised.value)


def test_the_adb_audit_refuses_the_document_shape(monkeypatch, tmp_path):
    """One ADB per row against a path-keyed truth set with no account column —
    and the ADB doctrine forbids a document-level combined figure outright, so
    there is no fold that could stand in for the missing column."""
    import adb_forensic_audit as audit

    monkeypatch.setattr(audit, "analyze_document", lambda *a, **k: object())
    monkeypatch.setattr(audit, "document_report_to_dict",
                        lambda document: document_payload())
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope") as raised:
        audit.audit_one(tmp_path / "synthetic.pdf", tmp_path, "markdown")
    assert "adb_forensic_audit.py::audit_one" in str(raised.value)


def test_the_gate_refuses_to_pin_a_provenance_it_cannot_key():
    """`PINNED_CURRENCY_SOURCE` is path-keyed for the same reason
    `PINNED_CURRENCY` is: two accounts may rest their denomination on two
    different classes of evidence."""
    import corpus_gate

    result = corpus_gate.Result()
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope") as raised:
        corpus_gate.check_currency_source(
            result, ["synthetic.pdf"], {"synthetic.pdf": document_payload()})
    assert "corpus_gate.py::check_currency_source" in str(raised.value)


def test_every_refusal_names_its_own_surface():
    """MINOR-4. The refusal message is what a person reads when a document
    publisher first breaks, and two of them named a different function — one of
    them a function that exists in the OTHER audit."""
    import re

    for module, expected in (
        ("balance_forensic_audit.py", {"balance_forensic_audit.py::audit_source"}),
        ("adb_forensic_audit.py", {"adb_forensic_audit.py::audit_one"}),
        ("benchmark/ourside.py", {"benchmark/ourside.py::_account"}),
        ("corpus_gate.py", {"corpus_gate.py::check_currency",
                            "corpus_gate.py::check_currency_source",
                            "corpus_gate.py::document_verdicts"}),
    ):
        text = pathlib.Path(module).read_text(encoding="utf-8")
        # Both spellings: the keyword argument, and the local named once and
        # passed several times.
        found = set(re.findall(r'surface\s*=\s*"([^"]+)"', text))
        assert found == expected, (module, found)


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

def _verdict(outcome, flags=(), risk="clear", index=None):
    import corpus_gate

    return corpus_gate._Verdict(outcome, tuple(flags), (), risk, False, index)


def test_a_document_outcome_no_account_holds_is_refused():
    """MINOR-1 / design §6.5's first bullet.

    The per-account verdicts were returned and DISCARDED at the only call site,
    which made "one verdict per account plus a document verdict" a shape rather
    than a claim. Each clause is doctored, because a self-check nothing can
    break is not a check.
    """
    import corpus_gate

    with pytest.raises(ValueError, match="document_verdict_does_not_follow"):
        corpus_gate._assert_document_verdict_follows(
            _verdict("withheld"),
            (_verdict("review", index=1), _verdict("validated", index=2)),
        )


def test_a_document_flag_no_account_raised_is_refused():
    import corpus_gate

    with pytest.raises(ValueError, match="document_verdict_invents_a_flag"):
        corpus_gate._assert_document_verdict_follows(
            _verdict("review", flags=("a_flag_no_account_raised",)),
            (_verdict("review", index=1), _verdict("validated", index=2)),
        )


def test_a_document_risk_milder_than_an_accounts_is_refused():
    import corpus_gate

    with pytest.raises(ValueError, match="document_verdict_softens_an_account"):
        corpus_gate._assert_document_verdict_follows(
            _verdict("review", risk="clear"),
            (_verdict("review", risk="high", index=1),
             _verdict("validated", index=2)),
        )


def test_a_document_level_refusal_is_allowed_to_hold_no_accounts_outcome():
    """`failed` is the one outcome the fold may reach on its own — a document
    that publishes no account, or one whose omission is unratified."""
    import corpus_gate

    corpus_gate._assert_document_verdict_follows(
        _verdict("failed"),
        (_verdict("validated", index=1),),
    )


def test_the_self_check_is_silent_on_a_verdict_that_does_follow():
    import corpus_gate

    document, per = corpus_gate.document_verdicts(
        document_payload(outcomes=("review", "validated")))
    assert document.outcome == "review"
    assert [verdict.outcome for verdict in per] == ["review", "validated"]
    assert document.risk_level == "review"
