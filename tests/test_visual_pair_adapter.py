"""Synthetic Stage E contract checks; no customer pages or model calls."""
from copy import deepcopy

import pytest

from analysis.pipeline import analyze_statement
from analysis.reconcile import reconcile
from analysis.serialization import document_report_to_dict
from ocr.document import StatementMarkdown
from ocr.truncation import assess_pages
from vlm import pair_adapter


def _source():
    return {
        "bank": "SYNTHETIC UNKNOWN ISSUER", "account_name": "FABRICATED BUSINESS",
        "account_number": "0000-1234", "period_start": "2031-01-01",
        "period_end": "2031-01-03", "beginning_balance": 100.0,
        "ending_balance": 30.0, "currency": "CAD", "days_in_period": 3,
        "stated_total_credits": 50.0, "stated_total_debits": 120.0,
        "stated_credit_count": 1, "stated_debit_count": 1,
        "stated_service_charge": 0.0, "stated_interest_paid": 0.0,
        "stated_nsf_count": 5, "bank_reported_average_balance": 77.01,
        "bank_reported_average_label": "Average Collected Balance",
        "stated_daily_balances": [
            {"date": "2031-01-01", "balance": 100.0},
            {"date": "2031-01-02", "balance": -20.0},
            {"date": "2031-01-03", "balance": 30.0},
        ],
        "transactions": [
            {"date": "2031-01-02", "description": "POS PURCHASE  CARD#0042  A&B / REF: 19",
             "amount": -120.0, "direction": "debit", "running_balance": -20.0},
            {"date": "2031-01-03", "description": "CUSTOMER DEPOSIT  REF/0088",
             "amount": 50.0, "direction": "credit", "running_balance": 30.0},
        ],
    }


def _doc():
    pages = [
        "SYNTHETIC UNKNOWN ISSUER\nPeriod: 2031-01-01 through 2031-01-03\n"
        "Beginning balance 100.00 CAD\nEnding balance 30.00 CAD\n"
        "2031-01-02 POS PURCHASE  CARD#0042  A&B / REF: 19  -120.00 -20.00\n"
        "2031-01-03 CUSTOMER DEPOSIT  REF/0088  50.00 30.00\n"
    ]
    doc = StatementMarkdown(
        source_file="synthetic.pdf", model="visual-pair-v1", pages=pages,
        page_integrity=assess_pages(pages), page_extractor=["visual-pair-v1"],
    )
    doc.visual_pair = {
        "version": 1, "account_count": 1, "statement": _source(),
        "gate": {"admitted": True, "reasons": []},
        "confidence": {"provisional": True, "gate_admitted": True,
                       "counts": {"agreed": 2, "corrected": 0, "added": 0,
                                  "rejected": 0, "unresolved": 0}},
        "row_evidence": [], "receipt_sha256": "0" * 64,
    }
    return doc


def test_generic_unmatched_layout_uses_existing_metrics_and_source_contract():
    doc = _doc()
    result = pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")
    payload = document_report_to_dict(result)
    assert result.accounts[0].model_used == "visual-pair-v1-generic"
    assert payload["statement"]["currency"] == "CAD"
    assert payload["statement"]["currency_source"] == "model_extracted"
    assert payload["statement"]["account_number"] == "0000-1234"
    assert payload["statement"]["bank_reported_average_label"] == "Average Collected Balance"
    assert payload["statement"]["stated_daily_balances"] == _source()["stated_daily_balances"]
    assert result.accounts[0].statement.transactions[0].description == _source()["transactions"][0]["description"]
    assert payload["metrics"]["average_daily_balance"] == pytest.approx(36.67, abs=0.01)
    assert payload["metrics"]["effective_nsf_count"] == 1
    assert payload["metrics"]["stated_nsf_count"] == 5
    assert payload["metrics"]["pos_count"] == 1
    assert payload["metrics"]["effective_total_deposits"] == 50.0
    assert payload["metrics"]["effective_total_withdrawals"] == 120.0
    assert payload["escalated"] is False


def test_faithful_bank_bridge_uses_full_statement_identity(monkeypatch):
    doc = _doc()
    statement = pair_adapter._source_statement(_source())
    ordinary = analyze_statement(
        statement, reconciliation=reconcile(statement), markdown=doc.to_markdown(),
        sheets=doc.pages, model_used="synthetic-reader",
    )
    calls = []

    def bridge(markdown, **kwargs):
        calls.append(kwargs)
        return ordinary

    monkeypatch.setattr(pair_adapter, "analyze_document", bridge)
    monkeypatch.setattr(pair_adapter, "analyze_statement", lambda *a, **k: pytest.fail("generic used"))
    result = pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")
    assert result.accounts[0].model_used == "visual-pair-v1-bank-bridge"
    assert calls[0]["parse_mode"] == "deterministic"
    assert result.accounts[0].statement.model_dump() == statement.model_dump()


@pytest.mark.parametrize("mutation", ["description", "rejected_row", "summary", "daily_balance"])
def test_bank_bridge_cannot_revive_or_change_reviewed_sources(monkeypatch, mutation):
    doc = _doc()
    original = pair_adapter._source_statement(_source())
    ordinary = analyze_statement(
        original, reconciliation=reconcile(original), markdown=doc.to_markdown(),
        sheets=doc.pages, model_used="synthetic-reader",
    )
    stale = original.model_copy(deep=True)
    if mutation == "description":
        stale.transactions[0].description = "STAGE A WRONG DESCRIPTION"
    elif mutation == "rejected_row":
        stale.transactions.append(stale.transactions[0].model_copy())
    elif mutation == "summary":
        stale.stated_nsf_count = 99
    else:
        stale.stated_daily_balances[0].balance = 99.0
    ordinary.accounts[0].statement = stale
    monkeypatch.setattr(pair_adapter, "analyze_document", lambda *a, **k: ordinary)
    result = pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")
    assert result.accounts[0].model_used.endswith("-generic")
    assert result.accounts[0].statement.model_dump() == original.model_dump()


def test_policy_defaults_to_hold_even_when_gate_passes(monkeypatch):
    monkeypatch.setattr(pair_adapter, "analyze_document", lambda *a, **k: pytest.fail("parser called"))
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="requires human review"):
        pair_adapter.analyze_visual_pair(_doc())


@pytest.mark.parametrize("mutation,reason", [
    (lambda d: d.visual_pair["gate"].update(admitted=False, reasons=["sum_mismatch"]), "gate refused"),
    (lambda d: d.visual_pair["confidence"]["counts"].update(unresolved=1), "review is incomplete"),
    (lambda d: d.visual_pair.update(account_count=2), "multiple accounts"),
    (lambda d: d.visual_pair["statement"].update(beginning_balance=None), "required printed fields"),
    (lambda d: d.visual_pair["statement"].update(ending_balance=31.0), "did not reconcile"),
    (lambda d: d.visual_pair["statement"].update(average_daily_balance=999.0), "unsupported fields"),
    (lambda d: d.visual_pair["statement"]["transactions"][0].update(lender=True), "unsupported fields"),
    (lambda d: d.visual_pair["statement"].update(currency=None), "required printed fields"),
    (lambda d: d.visual_pair["statement"]["transactions"][0].update(amount=float("nan")), "numbers are invalid"),
    (lambda d: d.visual_pair["statement"]["transactions"][0].update(date="2032-01-02"), "outside its printed period"),
])
def test_invalid_or_incomplete_evidence_never_reaches_analysis(monkeypatch, mutation, reason):
    doc = _doc()
    mutation(doc)
    monkeypatch.setattr(pair_adapter, "analyze_document", lambda *a, **k: pytest.fail("parser called"))
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match=reason):
        pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")


def _with_cut_off_terms_page(doc):
    from ocr.truncation import PageIntegrity
    doc.pages.append("FABRICATED TERMS AND CONDITIONS\nIn case of errors or questions about your")
    doc.page_integrity.append(PageIntegrity(page_index=1, truncated=True, signals=["model_finish_reason_length"],
                                            finish_reason="length"))
    return doc


def test_a_cut_off_page_without_amounts_named_by_the_evidence_does_not_refuse_the_analysis(monkeypatch):
    # The page's own text layer prints no amount (vlm/pair.py lists it in cut_off_pages_without_transactions): no
    # transaction can be missing, and the gate admitted the statement with it.
    doc = _with_cut_off_terms_page(_doc())
    doc.visual_pair["cut_off_pages_without_transactions"] = [2]
    monkeypatch.setattr(pair_adapter, "analyze_document", lambda *a, **k: None)
    result = pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")
    assert result.accounts[0].model_used.endswith("-generic")


@pytest.mark.parametrize("named", [None, [], [3]])
def test_any_other_cut_off_page_leaves_the_page_evidence_incomplete(monkeypatch, named):
    doc = _with_cut_off_terms_page(_doc())
    if named is not None:
        doc.visual_pair["cut_off_pages_without_transactions"] = named
    monkeypatch.setattr(pair_adapter, "analyze_document", lambda *a, **k: pytest.fail("parser called"))
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="page evidence is incomplete"):
        pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")


def test_printed_column_does_not_override_signed_money():
    raw = deepcopy(_source())
    # A reversal can be printed in the debit column while money enters the
    # account. The adapter must preserve both facts independently.
    raw["transactions"][1]["direction"] = "debit"
    raw["stated_credit_count"] = 0
    raw["stated_debit_count"] = 2
    statement = pair_adapter._source_statement(raw)
    assert statement.transactions[1].amount == 50.0
    assert statement.transactions[1].direction == "debit"


def test_currency_source_cannot_be_certified_by_model():
    raw = _source()
    raw["currency_source"] = "printed"
    assert pair_adapter._source_statement(raw).currency_source == "model_extracted"


def test_conflicting_printed_daily_ledger_cannot_be_partially_admitted():
    doc = _doc()
    # The transaction sum still reconciles; only the existing ADB validation
    # discovers that a printed daily snapshot contradicts its running ledger.
    doc.visual_pair["statement"]["stated_daily_balances"][1]["balance"] = 900.0
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="daily ledger did not validate"):
        pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")
