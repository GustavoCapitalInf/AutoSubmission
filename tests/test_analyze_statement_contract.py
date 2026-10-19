"""The `analyze_statement` / account-roster contract the text-first reader is planned to produce into.

Fabricated statements only; no model, no PDF. A reader that builds its own `Statement` (one account, or a document
judged account by account) hands each one to `analysis.pipeline.analyze_statement`, the ordinary account-report
path every bank reader shares, and assembles a `DocumentReport` with its `account_roster` and the document's
`identify_internal_transfers`. `analysis/serialization.py` publishes the roster, and the web app's package view
excludes an unverified or idle main account by it.

Split from `tests/test_visual_pair_adapter.py` and `tests/test_visual_pair_accounts_adapter.py` when the visual
pair was removed (model-code removal, slice S4): its adapter (`vlm/pair_adapter.py`) was the only production
caller, and its source gate, bank-reader bridge and refusals left with it. What stays is every assertion on the
analysis these statements get, on the roster and on the internal transfers, now built from `Statement` objects
directly.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from analysis.pipeline import (AccountRosterEntry, DocumentReport, InternalTransfer, analyze_statement,
                               identify_internal_transfers)
from analysis.reconcile import reconcile
from analysis.schema import Statement
from analysis.serialization import document_report_to_dict


# --- one account (from tests/test_visual_pair_adapter.py) ----------------------------------------------------------

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


PAGES = [
    "SYNTHETIC UNKNOWN ISSUER\nPeriod: 2031-01-01 through 2031-01-03\n"
    "Beginning balance 100.00 CAD\nEnding balance 30.00 CAD\n"
    "2031-01-02 POS PURCHASE  CARD#0042  A&B / REF: 19  -120.00 -20.00\n"
    "2031-01-03 CUSTOMER DEPOSIT  REF/0088  50.00 30.00\n"
]
MARKDOWN = "<!-- source: synthetic.pdf | model: synthetic-reader -->\n\n" + PAGES[0]


def _statement(raw=None, *, currency_source="model_extracted") -> Statement:
    return Statement.model_validate({**(raw or _source()), "currency_source": currency_source})


def _analyze(statement: Statement, *, model_used="synthetic-reader-generic", markdown=MARKDOWN, sheets=PAGES):
    return analyze_statement(statement, reconciliation=reconcile(statement), markdown=markdown, sheets=sheets,
                             model_used=model_used)


def test_one_account_gets_the_ordinary_metrics_and_keeps_its_source_fields():
    statement = _statement()
    result = _analyze(statement)
    payload = document_report_to_dict(result)
    assert isinstance(result, DocumentReport) and len(result.accounts) == 1
    assert result.account_roster == [] and result.internal_transfers == [] and result.document_period is None
    assert result.accounts[0].model_used == "synthetic-reader-generic"
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
    assert result.accounts[0].metrics.adb_ok is True
    # The statement goes through unchanged: the boundary never repairs or normalises it.
    assert result.accounts[0].statement.model_dump() == statement.model_dump()


def test_the_provenance_label_the_producer_assigns_is_published_as_given():
    for label in ("model_extracted", "schema_default", "printed"):
        payload = document_report_to_dict(_analyze(_statement(currency_source=label)))
        assert payload["statement"]["currency_source"] == label


def test_a_printed_column_does_not_override_signed_money():
    raw = deepcopy(_source())
    # A reversal can be printed in the debit column while money enters the account; both facts reach the
    # analysis independently.
    raw["transactions"][1]["direction"] = "debit"
    raw["stated_credit_count"] = 0
    raw["stated_debit_count"] = 2
    statement = _statement(raw)
    analysed = _analyze(statement).accounts[0].statement
    assert analysed.transactions[1].amount == 50.0
    assert analysed.transactions[1].direction == "debit"


def test_a_printed_daily_balance_contradicting_the_ledger_fails_the_adb_validation():
    # The transaction sum still reconciles; only the ADB validation sees that a printed daily snapshot contradicts
    # the running ledger, so a producer cannot publish that account as validated.
    raw = deepcopy(_source())
    raw["stated_daily_balances"][1]["balance"] = 900.0
    statement = _statement(raw)
    assert reconcile(statement).ok
    assert _analyze(statement).accounts[0].metrics.adb_ok is not True


def test_a_statement_that_does_not_reconcile_is_refused_before_any_analysis():
    raw = deepcopy(_source())
    raw["ending_balance"] = 31.0
    statement = _statement(raw)
    with pytest.raises(RuntimeError, match="did not reconcile"):
        _analyze(statement)


# --- a document judged account by account (from tests/test_visual_pair_accounts_adapter.py) ------------------------

def _account(name, number, opening, rows):
    closing = round(opening + sum(amount for _, _, amount in rows), 2)
    balance, transactions = opening, []
    for day, description, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append({"date": day, "description": description, "amount": amount,
                             "direction": "credit" if amount > 0 else "debit", "running_balance": balance})
    return Statement.model_validate({
        "bank": "SYNTHETIC MEMBER UNION", "account_name": name, "account_number": number,
        "period_start": "2031-01-01", "period_end": "2031-01-31", "beginning_balance": opening,
        "ending_balance": closing, "currency": "USD", "currency_source": "model_extracted",
        "transactions": transactions})


CHECKING = _account("FABRICATED BUSINESS CHECKING", "0010", 1000.0, [
    ("2031-01-05", "CUSTOMER DEPOSIT REF 0001", 400.0), ("2031-01-09", "CARD PURCHASE FABRICATED STORE", -100.0),
    ("2031-01-20", "TRANSFER TO SHARE 0001", -50.0)])
SAVINGS = _account("FABRICATED SAVINGS", "0001", 200.0, [("2031-01-20", "TRANSFER FROM SHARE 0010", 50.0)])
MEMBER_PAGES = ["SYNTHETIC MEMBER UNION\nFABRICATED SAVINGS 0001\nFABRICATED BUSINESS CHECKING 0010\n"]

#: (title, kind, number_last4, status, statement, idle balance, held reasons), in printed order.
PRINTED = [
    ("FABRICATED SAVINGS", "savings", "0001", "verified", SAVINGS, None, ()),
    ("FABRICATED BUSINESS CHECKING", "checking", "0010", "verified", CHECKING, None, ()),
    ("FABRICATED CLUB", "savings", "0020", "idle", None, 25.0, ()),
    ("FABRICATED MONEY MARKET", "money_market", "0030", "held", None, None, ("page_unresolved",)),
]


def _member_document(printed=PRINTED) -> DocumentReport:
    """A producer's assembly, as the adapter did it: each verified account analysed on its own by the ordinary
    report path (nothing combined across accounts), every printed account on the roster, the document's internal
    transfers computed over the published reports, and the document period only when every published account
    shares it."""
    reports, roster = [], []
    for title, kind, key, status, statement, balance, reasons in printed:
        if status == "verified":
            report = analyze_statement(statement, reconciliation=reconcile(statement), markdown="",
                                       sheets=MEMBER_PAGES, model_used="synthetic-reader-generic").accounts[0]
            roster.append(AccountRosterEntry(title, kind, key, "published", published_index=len(reports)))
            reports.append(report)
            continue
        roster.append(AccountRosterEntry(title, kind, key, status, balance=balance, reasons=reasons))
    transfers, notes = identify_internal_transfers(reports)
    periods = {(report.statement.period_start, report.statement.period_end) for report in reports}
    return DocumentReport(accounts=reports, document_period=periods.pop() if len(periods) == 1 else None,
                          internal_transfers=transfers, integrity_notes=notes, account_roster=roster)


def test_each_verified_account_is_its_own_report_and_every_account_is_on_the_roster():
    result = _member_document()
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
    assert payload["document"]["account_roster"][2]["balance"] == 25.0
    assert payload["document"]["account_roster"][3]["reasons"] == ["page_unresolved"]
    # Each account's own figures: nothing summed across accounts.
    assert [account["statement"]["ending_balance"] for account in payload["accounts"]] == [250.0, 1250.0]
    assert [account["metrics"]["average_daily_balance"] is not None for account in payload["accounts"]] == [True, True]


def test_the_transfer_between_two_published_accounts_is_found_by_index():
    result = _member_document()
    assert result.internal_transfers == [
        InternalTransfer(a=(0, 0), b=(1, 2), basis="printed_internal_transfer_designation_on_the_credit_leg")]
    assert result.integrity_notes == []
    assert document_report_to_dict(result)["document"]["internal_transfers"] == [
        {"a": [0, 0], "b": [1, 2], "basis": "printed_internal_transfer_designation_on_the_credit_leg"}]
    # Both legs stay in their own ledgers.
    assert [len(report.statement.transactions) for report in result.accounts] == [1, 3]


def test_one_published_account_publishes_todays_payload_beside_its_roster():
    printed = [("FABRICATED SAVINGS", "savings", "0001", "held", None, None, ("sum_mismatch",))] + PRINTED[1:]
    result = _member_document(printed)
    assert result.internal_transfers == []  # one ledger: no sibling for a movement to have a counterpart in
    payload = document_report_to_dict(result)
    assert payload["statement"]["account_name"] == "FABRICATED BUSINESS CHECKING"
    assert [(entry["status"], entry["published_index"]) for entry in payload["document"]["account_roster"]] == [
        ("held", None), ("published", 0), ("idle", None), ("held", None)]


def test_a_roster_entry_names_its_published_account_if_and_only_if_it_is_published():
    with pytest.raises(ValueError):
        AccountRosterEntry("FABRICATED SAVINGS", "savings", "0001", "published")
    with pytest.raises(ValueError):
        AccountRosterEntry("FABRICATED CLUB", "savings", "0020", "idle", published_index=0)
    with pytest.raises(ValueError):
        AccountRosterEntry("FABRICATED CLUB", "savings", "0020", "verified")


def test_a_document_without_a_roster_publishes_no_roster_key():
    payload = document_report_to_dict(_analyze(_statement()))
    assert "account_roster" not in (payload.get("document") or {})
