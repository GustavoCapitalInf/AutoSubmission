from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.truth import TruthAccount, TruthRow, match_rows, truth_from_payload

PAYLOAD_ACCOUNT_SHAPE = {
    "statement": {"account_number": "0001", "beginning_balance": 500.0, "ending_balance": 530.0,
                  "period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD",
                  "transactions": [
                      {"date": "2031-01-01", "description": "SYNTHETIC ROW 01", "amount": 10.0, "direction": "credit", "running_balance": 510.0},
                      {"date": "2031-01-02", "description": "SYNTHETIC ROW 02", "amount": -20.0, "direction": "debit", "running_balance": 490.0},
                      {"date": "2031-01-03", "description": "SYNTHETIC ROW 03", "amount": 40.0, "direction": "credit", "running_balance": 530.0}]},
    "metrics": {}, "reconciliation": {}, "quality": {}, "integrity": {}, "detection": {}, "classifications": [],
}


def test_truth_from_account_shape_payload():
    accounts = truth_from_payload(PAYLOAD_ACCOUNT_SHAPE)
    assert len(accounts) == 1
    account = accounts[0]
    assert account.account_number == "0001" and account.beginning == Decimal("500.00")
    assert account.rows[1] == TruthRow("2031-01-02", "SYNTHETIC ROW 02", Decimal("20.00"), "debit", Decimal("490.00"))


def test_truth_from_document_shape_payload():
    payload = {"document": {"account_count": 1}, "accounts": [PAYLOAD_ACCOUNT_SHAPE]}
    assert len(truth_from_payload(payload)) == 1


def test_match_rows_exact_and_partial():
    truth = truth_from_payload(PAYLOAD_ACCOUNT_SHAPE)[0]
    candidates = [
        CandidateRow("2031-01-01", "01/01", "Synthetic Row 01", Decimal("10.00"), "credit", Decimal("510.00"), 0, "stage_b", "p0r0"),
        CandidateRow("2031-01-02", "01/02", "SYNTHETIC ROW 02 extra", Decimal("20.00"), "debit", Decimal("491.00"), 0, "stage_b", "p0r1"),
        CandidateRow("2031-01-09", "01/09", "GHOST", Decimal("1.00"), "debit", None, 0, "stage_b", "p0r2"),
    ]
    match = match_rows(candidates, truth)
    assert (match.truth_rows, match.candidate_rows, match.matched, match.missing, match.extra) == (3, 3, 2, 1, 1)
    assert match.exact_balance == 1 and match.exact_description == 1


def test_match_rows_empty():
    truth = TruthAccount(None, None, None, None, None, "USD", ())
    match = match_rows([], truth)
    assert match.matched == 0 and match.truth_rows == 0
