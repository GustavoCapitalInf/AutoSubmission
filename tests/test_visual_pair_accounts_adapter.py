"""Synthetic Stage E for a statement the visual pair judged account by account (vlm/pair_accounts.py): each verified
account becomes its own report, the roster keeps every account the statement prints, and nothing is combined.
No customer pages or model calls."""
from copy import deepcopy

import pytest

from analysis.serialization import document_report_to_dict
from ocr.document import StatementMarkdown
from ocr.truncation import assess_pages
from vlm import pair_adapter


def _statement(name, number, opening, rows):
    closing = round(opening + sum(amount for _, _, amount in rows), 2)
    balance, transactions = opening, []
    for day, description, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append({"date": day, "description": description, "amount": amount,
                             "direction": "credit" if amount > 0 else "debit", "running_balance": balance})
    return {"bank": "SYNTHETIC MEMBER UNION", "account_name": name, "account_number": number,
            "period_start": "2031-01-01", "period_end": "2031-01-31", "beginning_balance": opening,
            "ending_balance": closing, "currency": "USD", "transactions": transactions}


CHECKING = _statement("FABRICATED BUSINESS CHECKING", "0010", 1000.0, [
    ("2031-01-05", "CUSTOMER DEPOSIT REF 0001", 400.0), ("2031-01-09", "CARD PURCHASE FABRICATED STORE", -100.0),
    ("2031-01-20", "TRANSFER TO SHARE 0001", -50.0)])
SAVINGS = _statement("FABRICATED SAVINGS", "0001", 200.0, [("2031-01-20", "TRANSFER FROM SHARE 0010", 50.0)])


def _entry(index, title, kind, key, status, statement=None, **extra):
    entry = {"index": index, "title": title, "kind": kind, "number_key": key, "status": status,
             "reasons": [] if status != "held" else ["page_unresolved"],
             "confidence": {"score": 0.9876, "band": "very_high"}}
    if statement is not None:
        entry.update(statement=statement, markdown="", gate={"admitted": True, "reasons": [], "checks": {}})
    entry.update(extra)
    return entry


def _doc(entries):
    pages = ["SYNTHETIC MEMBER UNION\nFABRICATED SAVINGS 0001\nFABRICATED BUSINESS CHECKING 0010\n"]
    doc = StatementMarkdown(source_file="synthetic.pdf", model="visual-pair-v1", pages=pages,
                            page_integrity=assess_pages(pages), page_extractor=["visual-pair-v1"])
    doc.visual_pair = {"version": 1, "account_count": len(entries), "accounts": entries, "statement": None,
                       "gate": {"admitted": False, "reasons": ["anchor_disagreement"]},
                       "confidence": {"gate_admitted": False, "counts": {"unresolved": 0}},
                       "row_evidence": [], "receipt_sha256": "0" * 64}
    return doc


ENTRIES = [
    _entry(0, "FABRICATED SAVINGS", "savings", "0001", "verified", deepcopy(SAVINGS)),
    _entry(1, "FABRICATED BUSINESS CHECKING", "checking", "0010", "verified", deepcopy(CHECKING)),
    _entry(2, "FABRICATED CLUB", "savings", "0020", "idle", balance=25.0),
    _entry(3, "FABRICATED MONEY MARKET", "money_market", "0030", "held"),
]


def test_each_verified_account_is_its_own_report_and_every_account_is_on_the_roster():
    result = pair_adapter.analyze_visual_pair(_doc(deepcopy(ENTRIES)), review_policy="admit_gated")
    assert [report.statement.account_name for report in result.accounts] == [
        "FABRICATED SAVINGS", "FABRICATED BUSINESS CHECKING"]
    assert [(entry.status, entry.published_index, entry.balance, entry.reasons) for entry in result.account_roster] == [
        ("published", 0, None, ()), ("published", 1, None, ()), ("idle", None, 25.0, ()),
        ("held", None, None, ("page_unresolved",))]
    assert result.document_period == ("2031-01-01", "2031-01-31")
    payload = document_report_to_dict(result)
    assert "statement" not in payload and len(payload["accounts"]) == 2
    assert [entry["status"] for entry in payload["document"]["account_roster"]] == [
        "published", "published", "idle", "held"]
    # Each account's own figures: nothing summed across accounts.
    assert [account["statement"]["ending_balance"] for account in payload["accounts"]] == [250.0, 1250.0]
    assert [account["metrics"]["average_daily_balance"] is not None for account in payload["accounts"]] == [True, True]


def test_one_verified_account_publishes_todays_payload_beside_its_roster():
    entries = deepcopy(ENTRIES)
    entries[0].update(status="held", reasons=["sum_mismatch"])
    payload = document_report_to_dict(pair_adapter.analyze_visual_pair(_doc(entries), review_policy="admit_gated"))
    assert payload["statement"]["account_name"] == "FABRICATED BUSINESS CHECKING"
    assert [(entry["status"], entry["published_index"]) for entry in payload["document"]["account_roster"]] == [
        ("held", None), ("published", 0), ("idle", None), ("held", None)]


def test_no_verified_account_or_a_hold_policy_publishes_nothing():
    held = [dict(entry, status="held", reasons=["page_unresolved"]) for entry in deepcopy(ENTRIES)]
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="verified no account"):
        pair_adapter.analyze_visual_pair(_doc(held), review_policy="admit_gated")
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="requires human review"):
        pair_adapter.analyze_visual_pair(_doc(deepcopy(ENTRIES)), review_policy="hold")


def test_a_verified_account_whose_evidence_disagrees_is_refused():
    entries = deepcopy(ENTRIES)
    entries[1]["gate"]["reasons"] = ["sum_mismatch"]
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="account evidence is invalid"):
        pair_adapter.analyze_visual_pair(_doc(entries), review_policy="admit_gated")
    entries = deepcopy(ENTRIES)
    entries[1]["index"] = 5
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="account evidence is invalid"):
        pair_adapter.analyze_visual_pair(_doc(entries), review_policy="admit_gated")


def test_an_account_whose_reading_does_not_reconcile_is_held_not_published():
    entries = deepcopy(ENTRIES)
    entries[0]["statement"]["ending_balance"] = 999.0
    result = pair_adapter.analyze_visual_pair(_doc(entries), review_policy="admit_gated")
    assert [report.statement.account_name for report in result.accounts] == ["FABRICATED BUSINESS CHECKING"]
    assert (result.account_roster[0].status, result.account_roster[0].reasons) == (
        "held", ("source_statement_invalid",))
