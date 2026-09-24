from dataclasses import replace
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.gate import gate, statement_from
from vlm.metadata import AccountMeta


def test_separate_printed_service_charge_reaches_gate_reconciliation():
    meta = AccountMeta(
        Decimal("100"), Decimal("125"), "2031-01-01", "2031-01-31",
        "CAD", "0001", "SYNTHETIC", (), stated_total_credits=Decimal("50"),
        stated_total_debits=Decimal("20"), stated_credit_count=1, stated_debit_count=2,
        stated_service_charge=Decimal("5"), account_name="FABRICATED BUSINESS",
        account_number="0000-0001", days_in_period=31, stated_nsf_count=0,
        bank_reported_average_balance=Decimal("111.11"),
        bank_reported_average_label="Average Collected Balance",
        stated_daily_balances=(("2031-01-02", Decimal("125")),),
    )
    rows = [
        CandidateRow("2031-01-02", "01/02", "SYNTHETIC DEPOSIT", Decimal("50"), "credit",
                     Decimal("150"), 1, "stage_b", "row-1"),
        CandidateRow("2031-01-02", "01/02", "SYNTHETIC PURCHASE", Decimal("20"), "debit",
                     Decimal("130"), 1, "stage_b", "row-2"),
        CandidateRow("2031-01-02", "01/02", "SERVICE CHARGE", Decimal("5"), "debit",
                     Decimal("125"), 1, "stage_b", "row-3"),
    ]
    assert gate(rows, meta).admitted
    assert "summary_mismatch" in gate(rows, replace(meta, stated_service_charge=None)).reasons
    statement = statement_from(rows, meta)
    assert statement.account_name == "FABRICATED BUSINESS"
    assert statement.account_number == "0000-0001"
    assert statement.days_in_period == 31
    assert statement.stated_service_charge == 5.0
    assert statement.bank_reported_average_label == "Average Collected Balance"
    assert statement.stated_daily_balances[0].balance == 125.0
