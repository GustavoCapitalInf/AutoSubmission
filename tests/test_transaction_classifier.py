from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from analysis.metrics import compute_metrics
from analysis.pipeline import analyze_markdown
from analysis.schema import Statement, Transaction
from analysis.serialization import report_to_dict
from analysis.transaction_classifier import classify_transaction
from ocr.native_text import parse_native_navy_federal, parse_native_pdf_text
from webapp.app import _package_analysis
from webapp.jobs import Job


def _txn(
    description: str,
    amount: float,
    *,
    day: str = "2054-01-01",
    balance: float | None = None,
) -> Transaction:
    return Transaction(
        date=day,
        description=description,
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=balance,
    )


@pytest.mark.parametrize(
    "description",
    [
        "POS debit merchant 123",
        "POS-purchase merchant 123",
        "Point of sale: merchant 123",
        "Debit card purchase merchant 123",
        "Card purchase merchant 123",
        "Interac purchase merchant 123",
        "Contactless Interac purchase merchant 123",
        "Contactless purchase merchant 123",
        "Tap purchase merchant 123",
        "Visa Debit purchase merchant 123",
        "Mastercard Debit purchase merchant 123",
        "Checkcard merchant 123",
        "Purchase authorized on 01/02 merchant 123",
        "P0S DEB merchant 123",
    ],
)
def test_pos_purchase_inclusions(description: str):
    result = classify_transaction(description, -12.34)
    assert result.is_pos_purchase
    assert not result.is_pos_credit_or_refund
    assert result.original_description == description


@pytest.mark.parametrize(
    ("description", "amount"),
    [
        ("ATM withdrawal terminal 123", -20.0),
        ("ATM deposit terminal 123", 20.0),
        ("ATM withdrawal fee", -3.0),
        ("Cash withdrawal teller", -20.0),
        ("POS cash advance", -20.0),
        ("Online transfer sent", -20.0),
        ("INTERAC e-Transfer Sent-Autodep", -20.0),
        ("ACH debit merchant", -20.0),
        ("Check 1234", -20.0),
        ("Cheque 1234", -20.0),
        ("Bill payment utility", -20.0),
        ("Monthly service fee", -20.0),
        ("POS Debit bank fee", -20.0),
        ("POS credit adjustment", 20.0),
        ("Card purchase refund", 20.0),
        ("POS purchase reversal", -20.0),
        ("Voided debit card purchase", -20.0),
        ("Cancelled card purchase", -20.0),
    ],
)
def test_pos_purchase_exclusions(description: str, amount: float):
    assert not classify_transaction(description, amount).is_pos_purchase


@pytest.mark.parametrize(
    ("description", "amount"),
    [
        ("POS Credit Adjustment", 4.49),
        ("Card purchase refund", 12.00),
        ("POS purchase reversal", -12.00),
        ("Voided debit card purchase", -12.00),
    ],
)
def test_pos_credits_refunds_and_reversals_are_separate(
    description: str,
    amount: float,
):
    result = classify_transaction(description, amount)
    assert result.is_pos_credit_or_refund
    assert not result.is_pos_purchase


@pytest.mark.parametrize(
    "description",
    [
        "NSF",
        "Non-sufficient funds",
        "Insufficient funds",
        "Item returned NSF",
        "Cheque returned NSF",
        "Check returned NSF",
        "NSF item fee",
        "Returned item fee",
        "Returned check fee",
        "Returned cheque fee",
        "Unpaid item fee",
        "N.S.F. return item fee",
        "N5F item fee",
    ],
)
def test_nsf_event_inclusions(description: str):
    assert classify_transaction(description, -35.0).is_nsf_event


@pytest.mark.parametrize(
    "description",
    [
        "Refund from merchant",
        "Merchant return",
        "POS reversal",
        "Cancelled e-Transfer",
        "INTERAC e-Transfer Returned",
        "Deposit correction",
        "Overdraft fee",
        "Returned deposit",
    ],
)
def test_nsf_event_exclusions(description: str):
    assert not classify_transaction(description, -35.0).is_nsf_event


def test_nsf_embedded_quantity_counts_one_posted_row():
    statement = Statement(
        transactions=[
            _txn("NSF item fee 2 @ $45.00", -90.0),
        ]
    )
    metrics = compute_metrics(statement)
    assert metrics.nsf_count == 1
    # R18: the underwriting NSF count is negative-ending days in the validated daily ledger; the fee row is
    # a returned item, counted above. This statement prints no balances, so there is no ledger to count.
    assert metrics.effective_nsf_count == 0
    assert metrics.nsf_source == "negative_ending_days_unavailable"


def test_separate_nsf_rows_are_not_deduplicated():
    statement = Statement(
        transactions=[
            _txn("Returned item fee", -35.0),
            _txn("Returned item fee", -35.0),
            _txn("NSF item fee", -35.0),
        ]
    )
    assert compute_metrics(statement).nsf_count == 3


@pytest.mark.parametrize(
    "description",
    [
        "ATM withdrawal terminal 123",
        "ATM cash withdrawal terminal 123",
        "ATM W/D terminal 123",
        "A7M cash-withdrawal terminal 123",
        "Cash withdrawal at ATM terminal 123",
    ],
)
def test_atm_withdrawal_inclusions(description: str):
    assert classify_transaction(description, -20.0).is_atm_withdrawal


@pytest.mark.parametrize(
    ("description", "amount"),
    [
        ("ATM deposit terminal 123", 20.0),
        ("ATM deposit fee", -3.0),
        ("ATM cash-deposit fee", -3.0),
        ("ATM balance inquiry", -1.0),
        ("ATM withdrawal fee", -3.0),
        ("ATM transfer to savings", -20.0),
        ("Cash withdrawal at teller", -20.0),
        ("ATM withdrawal terminal 123", 20.0),
    ],
)
def test_atm_withdrawal_exclusions(description: str, amount: float):
    assert not classify_transaction(description, amount).is_atm_withdrawal


def test_identical_rows_without_balance_evidence_remain_distinct():
    statement = Statement(
        transactions=[
            _txn("POS debit coffee", -5.0),
            _txn("POS debit coffee", -5.0),
            _txn("POS debit coffee", -5.0, balance=95.0),
            _txn("POS debit coffee", -5.0, balance=90.0),
        ]
    )
    assert compute_metrics(statement).pos_count == 4


def test_classification_preserves_transaction_description():
    description = "Contactless-Interac purchase: Cafe #42"
    statement = Statement(transactions=[_txn(description, -12.34)])
    compute_metrics(statement)
    assert statement.transactions[0].description == description
    assert classify_transaction(
        statement.transactions[0].description,
        statement.transactions[0].amount,
    ).normalized_description == "CONTACTLESS INTERAC PURCHASE CAFE 42"


def _real_statement_report(relative_path: str):
    path = Path("Bank Statements", relative_path)
    pdf_bytes = path.read_bytes()
    document = (
        parse_native_navy_federal(pdf_bytes, source_file=path.name)
        or parse_native_pdf_text(pdf_bytes, source_file=path.name)
    )
    assert document is not None
    return analyze_markdown(document.to_markdown(), parse_mode="deterministic")


def _classified_rows(report, category: str):
    rows = []
    for transaction in report.statement.transactions:
        classification = classify_transaction(
            transaction.description,
            transaction.amount,
        )
        if category in classification.categories:
            rows.append((transaction, classification))
    return rows


def test_rbc_january_february_classification_regression():
    report = _real_statement_report("RBC/Chequing Statement-JAN+.pdf")
    assert report.statement.period_start == "2026-01-02"
    assert report.statement.period_end == "2026-02-02"
    assert report.reconciliation.ok
    assert report.metrics.pos_count == 10
    assert report.metrics.nsf_count == 3
    assert report.metrics.atm_withdrawal_count == 3

    pos_rows = _classified_rows(report, "pos_purchase")
    assert len(pos_rows) == 10
    assert sum(
        "CONTACTLESS INTERAC PURCHASE" in classification.normalized_description
        for _, classification in pos_rows
    ) == 5
    assert sum(
        classification.normalized_description.startswith("INTERAC PURCHASE")
        for _, classification in pos_rows
    ) == 5
    assert {
        transaction.description
        for transaction, _ in _classified_rows(report, "nsf_event")
    } == {
        "Item returned NSF",
        "Cheque returned NSF",
        "NSF item fee 2 @ $45.00",
    }


def test_navy_federal_june_classification_regression():
    report = _real_statement_report("Navy Fed/JUNE 2026.pdf")
    assert report.reconciliation.ok
    assert report.metrics.pos_count == 14
    assert report.metrics.pos_credit_count == 1
    assert report.metrics.nsf_count == 2
    assert report.metrics.atm_withdrawal_count == 3

    credit_rows = _classified_rows(report, "pos_credit_or_refund")
    assert len(credit_rows) == 1
    transaction, classification = credit_rows[0]
    assert transaction.description.startswith("POS Credit Adjustment")
    assert not classification.is_pos_purchase


def test_atb_august_classification_regression():
    report = _real_statement_report("ATB/ATB August 2023.pdf")
    assert report.reconciliation.ok
    assert report.metrics.pos_count == 0
    assert report.metrics.pos_credit_count == 0
    assert report.metrics.nsf_count == 0
    assert report.metrics.atm_withdrawal_count == 0
    returned_transfer = next(
        transaction
        for transaction in report.statement.transactions
        if transaction.description == "INTERAC e-Transfer Returned"
    )
    assert classify_transaction(
        returned_transfer.description,
        returned_transfer.amount,
    ).classification == "refund_or_reversal"


def test_atb_november_lender_and_potential_obligation_regression():
    report = _real_statement_report("ATB/ATB Nov 2023.pdf")
    metrics = report.metrics

    assert report.statement.period_start == "2023-11-01"
    assert report.statement.period_end == "2023-11-30"
    assert report.reconciliation.ok
    # Owner rulings 2026-09-24/25: BDC is an alternative position, and Econolease
    # (equipment finance) is a lender. Derived totals only.
    assert metrics.lenders_detected == 3
    assert metrics.lender_debit_count == 45
    assert metrics.lender_debits == 9757.26
    # The C10 ledger's review tier (spec section 4.3 step 11): MERCH PAD's fixed
    # daily debits and the LOANS FC direct debit.
    assert metrics.potential_lenders_detected == 2
    assert metrics.potential_lender_debit_count == 22
    assert metrics.potential_lender_debit_total == 3178.19
    assert metrics.eligible_deposits == 59310.74
    assert metrics.potential_withholding_numerator == 3178.19
    assert metrics.potential_withholding_denominator == 59310.74
    assert metrics.potential_withholding_exposure == pytest.approx(
        3178.19 / 59310.74 * 100
    )
    assert round(metrics.potential_withholding_exposure, 2) == 5.36

    known_funders = {match.funder: match for match in report.detection.known_funders}
    assert set(known_funders) == {"CanaCap", "Econolease", "Forward Funding"}
    assert known_funders["Forward Funding"].debit_count == 21
    assert known_funders["Forward Funding"].total_debited == 4305.0
    assert known_funders["Econolease"].debit_count == 3
    # Owner ruling 2026-09-24: BDC is an alternative position, not a lender.
    assert sum(record.classification == "alternative_position" for record in report.classifications) == 1

    assert [match.funder for match in report.detection.potential_lenders] == [
        "MERCH PAD (probably Merchant Growth)",
        "LOANS FC",
    ]
    merch_pad, loans_fc = report.detection.potential_lenders
    assert (merch_pad.debit_count, merch_pad.total_debited) == (21, 2606.31)
    assert (loans_fc.debit_count, loans_fc.total_debited) == (1, 571.88)
    for potential in (merch_pad, loans_fc):
        assert potential.eligible_deposit_denominator == 59310.74
        assert potential.potential_withholding_exposure == pytest.approx(
            potential.total_debited / 59310.74 * 100
        )
        assert potential.review_required
    assert [transaction.description for transaction in loans_fc.transactions] == [
        "Direct Debit Loans FC"
    ]
    assert [transaction.amount for transaction in loans_fc.transactions] == [-571.88]
    assert len(report.detection.lender_evidence) == 45
    assert round(sum(abs(record.amount) for record in report.detection.lender_evidence), 2) == 9757.26
    assert len(report.detection.potential_lender_evidence) == 22
    assert Counter(record.match_method for record in report.detection.potential_lender_evidence) == {
        "candidate_lender_alias": 22,
    }
    assert not any(record.contributes_to_lender_totals for record in report.detection.potential_lender_evidence)

    payload = report_to_dict(report)
    serialized = {item["funder"]: item for item in payload["detection"]["potential_lenders"]}
    assert serialized["LOANS FC"]["debit_count"] == 1
    assert serialized["LOANS FC"]["total_debited"] == 571.88
    assert serialized["LOANS FC"]["eligible_deposit_denominator"] == 59310.74
    assert serialized["LOANS FC"]["potential_withholding_exposure"] == pytest.approx(
        571.88 / 59310.74 * 100
    )
    assert serialized["LOANS FC"]["status"] == "review_required"
    assert serialized["MERCH PAD (probably Merchant Growth)"]["debit_count"] == 21
    assert serialized["MERCH PAD (probably Merchant Growth)"]["total_debited"] == 2606.31

    package = _package_analysis(
        [Job(id="atb-nov", filename="ATB Nov 2023.pdf", status="done", analysis=payload)]
    )
    totals = package["totals"]
    assert totals["lenders_detected"] == 3
    assert totals["lender_debit_count"] == 45
    assert totals["lender_debits"] == 9757.26
    assert totals["potential_lenders_detected"] == 2
    assert totals["potential_lender_debit_count"] == 22
    assert totals["potential_lender_debit_total"] == 3178.19
    assert totals["eligible_deposits"] == 59310.74
    assert totals["potential_withholding_exposure"] == 5.36
    assert totals["decision"] == "review_required"

    package_candidates = {item["funder"]: item for item in package["potential_lenders"]}
    assert list(package_candidates) == ["LOANS FC", "MERCH PAD (probably Merchant Growth)"]
    package_candidate = package_candidates["LOANS FC"]
    assert package_candidate["debit_count"] == 1
    assert package_candidate["total_debited"] == 571.88
    assert package_candidate["eligible_deposit_denominator"] == 59310.74
    assert package_candidate["status"] == "review_required"
    assert package_candidates["MERCH PAD (probably Merchant Growth)"]["debit_count"] == 21
    assert Counter(row["match_method"] for row in package["potential_lender_evidence"]) == {
        "candidate_lender_alias": 22,
    }
