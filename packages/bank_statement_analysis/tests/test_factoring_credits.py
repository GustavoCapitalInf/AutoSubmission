"""Owner ruling 2026-09-26: a factoring payee's credit is the business's own sales, paid by the factor that bought
its invoices. It is revenue, not financing proceeds, so it stays in eligible deposits, and it still carries the
Factoring flag: the payload counts it in `count_credited` and `total_credited` (contract C4, C5).

Every descriptor, payee and amount is fabricated, and every amount is whole dollars."""
from __future__ import annotations

import pytest

from analysis.transaction_classifier import credit_decision
from analysis.transaction_classifier import row as transaction_classifier_row
from analysis.transaction_classifier import funder_returns
from analysis.classification import credit_predicates
from analysis.metrics import compute_metrics
from analysis.payee_matcher import PayeeMatch
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction
from tests.flag_group_fixtures import FAKE_PAYEES, fake_payees, flagged_statement, txn  # noqa: F401  (fixture)

#: One factor paid twice by credit and once by debit, one lender debit and one customer deposit.
FACTORED_ROWS: tuple[tuple[str, str, float], ...] = (
    ("2054-01-05", "FABRICATED FACTOR INVOICE PAYMENT 0001", 4000.0),
    ("2054-01-12", "ACH DEBIT FABRICATED FACTOR 0001", -200.0),
    ("2054-01-19", "FABRICATED FACTOR INVOICE PAYMENT 0002", 3000.0),
    ("2054-01-20", "CUSTOMER DEPOSIT FABRICATED", 1000.0),
    ("2054-01-21", "ACH DEBIT FABRICATED LENDER 0001", -800.0),
)


def test_a_factoring_credit_is_revenue_and_carries_the_factoring_flag(fake_payees):
    record = classify_transaction("FABRICATED FACTOR INVOICE PAYMENT 0001", 4000.0)
    assert (record.classification, record.canonical_entity, record.matched_alias) == (
        "factoring", "Fabricated Factor", "FABRICATED FACTOR")
    assert (record.match_method, record.matched_rule) == ("known_payee_alias", "factoring_revenue_credit")
    assert (record.flagged_group, record.contributes_to_flagged_totals) == ("factoring", True)
    # Not financing proceeds: the operating-revenue path decides its revenue, and it is never excluded.
    assert not record.contributes_to_lender_credit_exclusion
    assert record.revenue_match_method != "financing_proceeds_credit"
    assert record.revenue_classification == "verified_revenue"
    assert not (record.contributes_to_lender_totals or record.contributes_to_potential_lender_totals)


def test_a_factoring_debit_keeps_its_flagged_group(fake_payees):
    record = classify_transaction("ACH DEBIT FABRICATED FACTOR 0001", -200.0)
    assert (record.classification, record.matched_rule, record.flagged_group) == (
        "factoring", "factoring_registry", "factoring")
    assert record.contributes_to_flagged_totals and not record.contributes_to_lender_totals


def test_the_owner_named_factor_pays_revenue_and_is_flagged():
    """RTS Financial is an owner-named factoring payee (spec §2), read from the rendered registry."""
    record = classify_transaction("RTS FINANCIAL PAYMENT", 100.0)
    assert (record.classification, record.matched_rule) == ("factoring", "factoring_revenue_credit")
    assert (record.flagged_group, record.contributes_to_flagged_totals) == ("factoring", True)
    assert not record.contributes_to_lender_credit_exclusion
    assert record.revenue_classification == "unverified_deposit"


def test_a_factoring_credit_an_earlier_rule_claims_stays_in_eligible_deposits_unflagged(fake_payees):
    """A transfer-worded credit is a transfer (step 6 comes before the known payee), as for a payout-credit entity."""
    record = classify_transaction("ONLINE TRANSFER FROM FABRICATED FACTOR 0001", 900.0)
    assert record.classification == "transfer"
    assert record.flagged_group is None and not record.contributes_to_flagged_totals
    assert record.revenue_match_method != "financing_proceeds_credit"
    assert not record.contributes_to_lender_credit_exclusion


def test_factoring_credits_stay_in_eligible_deposits_and_count_as_credited(fake_payees):
    metrics = compute_metrics(flagged_statement(FACTORED_ROWS))
    assert metrics.lender_credits == 0.0
    assert metrics.legacy_eligible_deposits == 8000.0
    assert metrics.withholding_rate == pytest.approx(10.0)
    assert metrics.flagged_groups == {
        "factoring": {"count": 1, "total": 200.0, "count_credited": 2, "total_credited": 7000.0, "payees": 1}
    }


def test_a_group_whose_rows_are_only_credits_is_published_with_no_debits(fake_payees):
    credits_only = tuple(row for row in FACTORED_ROWS if "INVOICE" in row[1])
    assert compute_metrics(flagged_statement(credits_only)).flagged_groups == {
        "factoring": {"count": 0, "total": 0.0, "count_credited": 2, "total_credited": 7000.0, "payees": 1}
    }


def test_a_proven_duplicate_factoring_credit_is_counted_once(fake_payees):
    statement = Statement(transactions=[
        txn("2054-01-05", "FABRICATED FACTOR INVOICE PAYMENT 0001", 4000.0, balance=5000.0),
        txn("2054-01-05", "FABRICATED FACTOR INVOICE PAYMENT 0001", 4000.0, balance=5000.0),
    ])
    first, duplicate = classify_statement_transactions(statement)
    assert first.contributes_to_flagged_totals and not duplicate.contributes_to_flagged_totals
    assert compute_metrics(statement).flagged_groups["factoring"]["count_credited"] == 1


def test_a_factoring_credit_the_reversal_pass_pairs_leaves_the_flagged_totals(fake_payees):
    statement = Statement(transactions=[
        txn("2054-01-05", "FABRICATED FACTOR INVOICE PAYMENT 0001", 4000.0),
        txn("2054-01-07", "REVERSAL FABRICATED FACTOR INVOICE PAYMENT 0001", -4000.0),
    ])
    credit, debit = classify_statement_transactions(statement)
    assert credit.flagged_group == "factoring"
    assert credit.revenue_match_method == "matched_reversal_pair"
    assert not credit.contributes_to_flagged_totals
    assert "factoring" not in compute_metrics(statement).flagged_groups


def test_a_factoring_position_counts_its_debits_and_its_credits_apart(fake_payees):
    from analysis.detect import find_flagged_positions

    statement = flagged_statement(FACTORED_ROWS)
    [position] = find_flagged_positions(statement, classify_statement_transactions(statement))
    assert (position.group, position.payee, position.matched_alias) == (
        "factoring", "Fabricated Factor", "FABRICATED FACTOR")
    assert (position.count, position.total_debited) == (1, 200.0)
    assert (position.count_credited, position.total_credited) == (2, 7000.0)
    # The cadence and the dates read every counted row, debit or credit.
    assert (position.cadence, position.avg_gap_days) == ("weekly", 7.0)
    assert (position.first_date, position.last_date) == ("2054-01-05", "2054-01-19")
    assert position.source_locations == ["transaction:1", "transaction:2", "transaction:3"]


@pytest.fixture
def two_factors(monkeypatch):
    """FAKE_PAYEES plus a second fabricated factor, so one group holds two payees."""
    payees = {**FAKE_PAYEES, "FABRICATED SECOND FACTOR": ("Fabricated Second Factor", "factoring")}

    def match(normalized_text: str, *, credit: bool = False) -> PayeeMatch | None:
        for alias in sorted(payees, key=len, reverse=True):
            if alias in normalized_text:
                entity, state = payees[alias]
                return PayeeMatch(entity=entity, state=state, alias=alias)
        return None

    monkeypatch.setattr(credit_predicates, "match_known_payee", match)
    monkeypatch.setattr(credit_decision, "match_known_payee", match)
    monkeypatch.setattr(funder_returns, "match_known_payee", match)
    monkeypatch.setattr(transaction_classifier_row, "match_known_payee", match)


def test_positions_rank_by_debited_plus_credited_within_a_group(two_factors):
    from analysis.detect import find_flagged_positions

    statement = flagged_statement((
        ("2054-01-05", "ACH DEBIT FABRICATED FACTOR 0001", -500.0),
        ("2054-01-06", "ACH DEBIT FABRICATED SECOND FACTOR 0001", -100.0),
        ("2054-01-07", "FABRICATED SECOND FACTOR INVOICE PAYMENT 0001", 900.0),
    ))
    positions = find_flagged_positions(statement, classify_statement_transactions(statement))
    # 100 debited plus 900 received outranks 500 debited: the order reads both directions.
    assert [position.payee for position in positions] == ["Fabricated Second Factor", "Fabricated Factor"]


def test_the_payload_publishes_the_credited_fields(fake_payees):
    from analysis.serialization import report_to_dict
    from tests.flag_group_fixtures import flagged_report

    payload = report_to_dict(flagged_report(FACTORED_ROWS))
    [position] = payload["detection"]["flagged_positions"]
    assert list(position) == [
        "group", "payee", "matched_alias", "count", "total_debited", "count_credited", "total_credited",
        "cadence", "avg_gap_days", "first_date", "last_date", "source_locations", "review_required",
    ]
    assert (position["count_credited"], position["total_credited"]) == (2, 7000.0)
    assert payload["metrics"]["flagged_groups"]["factoring"]["total_credited"] == 7000.0


def test_the_text_report_prints_what_a_flagged_payee_paid_in(fake_payees):
    from analyze import _render
    from tests.flag_group_fixtures import flagged_report

    assert (
        "  - Factoring: Fabricated Factor: 1 debit(s), $200.00; 2 credit(s) received, $7,000.00 (weekly)"
        in _render(flagged_report(FACTORED_ROWS))
    )
