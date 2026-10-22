"""Owner ruling 2026-10-02 (the underwriter's Q1, audit I12; true revenue spec §5.4, §6.2, §8.5, §10.7, §19.1, §20;
audit round 2, R2-OW12): "Held for review (look at the day $ amount got deposited and see if there is a frequent
payment following the deposit)", option 1.

Every incoming wire with no sender printed stays held (`excluded_pending_review` / `wire_no_sender`). Pass 7's last
step (`funding_series_after`, after the $1 floor and the premium-trust hold) records on each such held wire every
Lenders or Potential Lenders series that starts after it (`revenue_funding_series`, a tuple of `FundingSeries`): one
tab name (the potential payee label or the canonical entity) and one amount to the cent; posted, not a duplicate,
counting toward the lender or potential-lender count; every row dated strictly after the deposit, the first at most
FUNDING_SERIES_WINDOW_DAYS (10) days after it; two or more dates that `_promotion_cadence` reads daily or weekly. Its
start is observed when the statement shows one full gap of the series (at least 3 days) before the deposit. It is a
review aid only: no tier, reason, state, flag, figure, gate, debit or lender reading moves.

Fabricated rows only (CONTOSO GRILL LLC at Fifth Third Bank, March 2054; FABRIKAM, NORTHWIND and SAMPLE payees;
KAPITUS, a public funder of the registry, as the lender tests use it; neutral whole amounts)."""
from __future__ import annotations

import json
from dataclasses import asdict, fields, replace

import pytest

from analysis import transaction_classifier as tc
from analysis import true_revenue as tr
from analysis.detect import detect
from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction
from analysis.true_revenue import FundingSeries

HOLDER = "CONTOSO GRILL LLC"
BANK = "Fifth Third Bank"
START = "2054-03-01"
HELD_WIRE = ("excluded_pending_review", "wire_no_sender")
WIRE = "INCOMING WIRE TRANS 123456 TRN 1234567890"
#: A registry funder (confirmed_lender), a keyword recurrence (potential_lender, recurring_financing_counterparty), a
#: D6 payee named by its legal form and a D6 payee whose descriptor names no organisation (both recurring_fixed_debit).
KAPITUS = "KAPITUS DES:PAYMENT ID:1234567 INDN:CONTOSO GRILL LLC CO ID:1234567890 CCD"
FABRIKAM = "ACH DEBIT FABRIKAM FUNDING LLC 1234567"
SAMPLE_SERVICES = "SAMPLE MERCHANT SERVICES LLC WEB PMT 1234567"
UNNAMED = "NORTHWIND SAMPLE WEB PMT 1234567"
#: Bank of America's incoming wire, its originator printed after ORIG.
BOFA_WIRE = ("WIRE TYPE WIRE IN DATE 540309 TIME 1200 ET TRN 2054030900012345 SEQ 123456/000001 ORIG {sender} ID 1234 "
             "SND BK SAMPLE BANK ID 123456789")


def _day(day: int) -> str:
    return f"2054-03-{day:02d}"


def _series(text: str, amount: float, *days: int) -> list[tuple[int, str, float]]:
    return [(day, text, amount) for day in days]


def _statement(rows, *, bank=BANK, start=START, balances=False, account_title=None, holder=HOLDER) -> Statement:
    """The rows (day, description, amount) in their order; `balances` prints a running balance on each row, and a row
    given as (day, description, amount, balance) prints that balance (a proven duplicate repeats its original's)."""
    transactions, balance = [], 100000.0
    for row in rows:
        day, text, amount = row[:3]
        balance = row[3] if len(row) > 3 else round(balance + amount, 2)
        transactions.append(Transaction(date=_day(day), description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit",
                                        running_balance=balance if balances or len(row) > 3 else None))
    return Statement(account_name=holder, bank=bank, period_start=start, period_end="2054-03-31",
                     account_title=account_title, transactions=transactions)


def _run(rows, **kwargs):
    return tc.classify_statement_transactions(_statement(rows, **kwargs))


def _aid(records):
    """{location: series} of every record that carries the aid."""
    return {record.source_location: record.revenue_funding_series for record in records
            if record.revenue_funding_series}


#: The brief's scenarios with the aid (A1 to A6), each (rows, {wire location: series}).
SCENARIOS = {
    # A1: a keyword recurrence's weekly series two days after the wire.
    "A1": ([(9, WIRE, 50000.0)] + _series(FABRIKAM, -1250.0, 11, 18, 25), {
        "transaction:1": (FundingSeries("Fabrikam Funding LLC", "potential_lender", 1250.0, "weekly", 7.0,
                                        "2054-03-11", 2, 3, True,
                                        ("transaction:2", "transaction:3", "transaction:4")),)}),
    # A2: a registry funder's daily series the day after the wire (several gaps of one, one weekend).
    "A2": ([(10, WIRE, 40000.0)] + _series(KAPITUS, -400.0, 11, 12, 13, 16, 17), {
        "transaction:1": (FundingSeries("KAPITUS", "confirmed_lender", 400.0, "daily", 1.5, "2054-03-11", 1, 5, True,
                                        tuple(f"transaction:{n}" for n in range(2, 7))),)}),
    # A3: a wire on the statement's second day: the statement cannot show whether the series ran before it.
    "A3": ([(2, WIRE, 30000.0)] + _series(KAPITUS, -900.0, 4, 11, 18, 25), {
        "transaction:1": (FundingSeries("KAPITUS", "confirmed_lender", 900.0, "weekly", 7.0, "2054-03-04", 2, 4, False,
                                        tuple(f"transaction:{n}" for n in range(2, 6))),)}),
    # A4: a renewal: the old amount ran before the wire (not listed), the new amount starts after it.
    "A4": (_series(KAPITUS, -900.0, 2, 9) + [(12, WIRE, 50000.0)] + _series(KAPITUS, -1400.0, 16, 23, 30), {
        "transaction:3": (FundingSeries("KAPITUS", "confirmed_lender", 1400.0, "weekly", 7.0, "2054-03-16", 4, 3, True,
                                        ("transaction:4", "transaction:5", "transaction:6")),)}),
    # A5: two D6 payees, one named by its legal form, one by its label (D11: never a payee word); the same first date
    # and amount, so the payee orders them.
    "A5": ([(9, WIRE, 50000.0)] + _series(SAMPLE_SERVICES, -725.0, 11, 18, 25) + _series(UNNAMED, -725.0, 11, 18, 25), {
        "transaction:1": (
            FundingSeries("Sample Merchant Services LLC", "potential_lender", 725.0, "weekly", 7.0, "2054-03-11", 2, 3,
                          True, ("transaction:2", "transaction:3", "transaction:4")),
            FundingSeries("Unidentified lender obligation (weekly, 725.00)", "potential_lender", 725.0, "weekly", 7.0,
                          "2054-03-11", 2, 3, True, ("transaction:5", "transaction:6", "transaction:7")),
        )}),
    # A6: one series after two held wires: each carries it with its own days after.
    "A6": ([(8, WIRE, 20000.0), (10, WIRE, 60000.0)] + _series(KAPITUS, -1000.0, 13, 20, 27), {
        "transaction:1": (FundingSeries("KAPITUS", "confirmed_lender", 1000.0, "weekly", 7.0, "2054-03-13", 5, 3, True,
                                        ("transaction:3", "transaction:4", "transaction:5")),),
        "transaction:2": (FundingSeries("KAPITUS", "confirmed_lender", 1000.0, "weekly", 7.0, "2054-03-13", 3, 3, True,
                                        ("transaction:3", "transaction:4", "transaction:5")),)}),
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_a_held_wire_with_no_sender_names_the_lender_series_that_starts_after_it(name):
    rows, expected = SCENARIOS[name]
    records = _run(rows)
    assert _aid(records) == expected
    for record in records:
        if record.amount > 0:
            # The hold stays: the aid never changes the tier or the reason.
            assert (record.revenue_tier, record.revenue_tier_reason) == HELD_WIRE
        else:
            assert record.revenue_funding_series == ()


def test_the_debits_are_the_lender_tabs_rows_the_aid_reads():
    """The fixtures' debits are what the Lenders and Potential Lenders tabs list (read, never written, by the aid)."""
    states = {name: [(r.classification, r.match_method, r.canonical_entity, r.potential_payee_label,
                      r.contributes_to_lender_count, r.contributes_to_potential_lender_count)
                     for r in _run(SCENARIOS[name][0]) if r.amount < 0][0] for name in ("A1", "A2")}
    assert states == {
        "A1": ("potential_lender", "recurring_financing_counterparty", "Fabrikam Funding LLC", None, False, True),
        "A2": ("confirmed_lender", "verified_lender_alias", "KAPITUS", None, True, False),
    }
    a5 = [(r.match_method, r.canonical_entity, r.potential_payee_label) for r in _run(SCENARIOS["A5"][0])
          if r.amount < 0]
    assert a5[0] == ("recurring_fixed_debit", "Sample Merchant Services LLC", None)
    assert a5[3] == ("recurring_fixed_debit", "Unidentified lender obligation",
                     "Unidentified lender obligation (weekly, 725.00)")


def test_the_series_are_ordered_by_first_date_then_the_larger_amount_then_the_payee():
    rows = ([(9, WIRE, 50000.0)] + _series(KAPITUS, -400.0, 11, 12, 13, 16, 17)
            + _series(FABRIKAM, -1250.0, 11, 18, 25) + _series(KAPITUS, -800.0, 10, 17, 24))
    [series] = _aid(_run(rows)).values()
    assert [(item.payee, item.amount, item.first_date) for item in series] == [
        ("KAPITUS", 800.0, "2054-03-10"), ("Fabrikam Funding LLC", 1250.0, "2054-03-11"),
        ("KAPITUS", 400.0, "2054-03-11")]


@pytest.mark.parametrize(("days", "after"), [((19, 26), 10), ((20, 27), None)])
def test_the_first_payment_comes_at_most_ten_days_after_the_deposit(days, after):
    aid = _aid(_run([(9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, *days)))
    assert [item.days_after for item in aid.get("transaction:1", ())] == ([after] if after else [])
    assert tr.FUNDING_SERIES_WINDOW_DAYS == 10 and tr.FUNDING_SERIES_MIN_PAYMENTS == 2
    assert tr.FUNDING_SERIES_MIN_LOOKBACK_DAYS == 3


@pytest.mark.parametrize(("start", "wire_day", "observed"), [
    # A weekly series needs seven days of the statement before the deposit, a daily one three.
    (START, 8, True), (START, 7, False), ("2054-03-02", 9, True), ("2054-03-03", 9, False),
])
def test_the_start_is_observed_when_the_statement_shows_one_full_gap_before_the_deposit(start, wire_day, observed):
    rows = [(wire_day, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 12, 19, 26)
    [[series]] = _aid(_run(rows, start=start)).values()
    assert series.start_observed is observed


@pytest.mark.parametrize(("wire_day", "observed"), [(4, True), (3, False)])
def test_a_daily_series_needs_three_days_before_the_deposit(wire_day, observed):
    rows = [(wire_day, WIRE, 50000.0)] + _series(KAPITUS, -400.0, 6, 7, 8, 9)
    [[series]] = _aid(_run(rows)).values()
    assert (series.cadence, series.average_gap_days, series.start_observed) == ("daily", 1.0, observed)


def test_without_a_printed_period_the_statement_starts_on_its_earliest_dated_row():
    rows = [(1, "MOBILE DEPOSIT", 300.0), (9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 11, 18, 25)
    [[series]] = _aid(_run(rows, start=None)).values()
    assert series.start_observed is True
    [[late]] = _aid(_run(rows[1:], start=None)).values()
    assert late.start_observed is False  # the wire is the earliest dated row


def test_a_premium_trust_account_s_held_wire_keeps_its_reason_and_carries_the_aid():
    """CR6: the aid is pass 7's last step, after the premium-trust hold, so it reads the final tiers: the premium-trust
    hold leaves a held wire's first hold, and the aid follows it."""
    records = _run(SCENARIOS["A1"][0], account_title="PREMIUM TRUST ACCOUNT")
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == HELD_WIRE
    assert _aid(records) == SCENARIOS["A1"][1]


# --- controls: the field stays empty and every tier is unchanged ---------------------------------------------------

CONTROLS = {
    # C1: the series already ran before the deposit, or on the deposit's own day.
    "C1": [(9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 2, 9, 16, 23),
    "C1_same_day": [(9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 9, 16, 23),
    # C2: the first payment twelve days after.
    "C2": [(9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 21, 28),
    # C3: irregular dates.
    "C3": [(9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 11, 14, 29),
    # C4: weekly series that are no lender rows: payroll, an own transfer, a card purchase.
    "C4": ([(9, WIRE, 50000.0)] + _series("INTUIT PAYROLL 1234", -800.0, 11, 18, 25)
           + _series("ONLINE TRANSFER TO CHK 1234", -600.0, 12, 19, 26)
           + _series("POS DEBIT CONTOSO FUEL", -75.0, 13, 20, 27)),
    # A single payment after the deposit is no series.
    "one_payment": [(9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 11),
    # A held wire whose date does not read.
    "undated": [(9, WIRE, 50000.0)] + _series(KAPITUS, -900.0, 11, 18, 25),
}


@pytest.mark.parametrize("name", sorted(CONTROLS))
def test_no_series_starts_after_the_wire(name):
    statement = _statement(CONTROLS[name])
    if name == "undated":
        statement.transactions[0] = statement.transactions[0].model_copy(update={"date": "SOMETIME"})
    records = tc.classify_statement_transactions(statement)
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == HELD_WIRE
    assert _aid(records) == {}


def test_a_wire_that_is_not_held_as_no_sender_carries_no_aid():
    """C5: Bank of America's incoming wire from a named company (counted) and from the holder (held as the holder's
    name), each followed by a new funder series: only a wire with no sender carries the aid."""
    rows = ([(9, BOFA_WIRE.format(sender="NORTHWIND SUPPLY LLC"), 50000.0),
             (9, BOFA_WIRE.format(sender="CONTOSO GRILL LLC"), 40000.0)] + _series(KAPITUS, -900.0, 11, 18, 25))
    records = _run(rows, bank="Bank of America")
    assert [(r.revenue_tier, r.revenue_tier_reason) for r in records[:2]] == [
        ("counted_flagged", "wire_named_sender"), ("excluded_pending_review", "holder_name")]
    assert _aid(records) == {}


def test_a_duplicated_wire_carries_no_aid_and_a_duplicated_payment_counts_once():
    """C6: a proven duplicate (a repeated printed running balance) is neither a target nor a payment."""
    rows = [(9, WIRE, 50000.0, 150000.0), (9, WIRE, 50000.0, 150000.0),
            (11, KAPITUS, -900.0, 149100.0), (11, KAPITUS, -900.0, 149100.0),
            (18, KAPITUS, -900.0, 148200.0), (25, KAPITUS, -900.0, 147300.0)]
    records = _run(rows)
    assert (records[1].duplicate_of, records[3].duplicate_of) == ("transaction:1", "transaction:3")
    assert _aid(records) == {"transaction:1": (FundingSeries(
        "KAPITUS", "confirmed_lender", 900.0, "weekly", 7.0, "2054-03-11", 2, 3, True,
        ("transaction:3", "transaction:5", "transaction:6")),)}
    assert records[1].revenue_funding_series == ()


# --- C7: the aid moves nothing else (and nothing on the lender side, G7 at unit level) -----------------------------

def _without_aid(node):
    """A detection or metrics output as plain data, every record's aid left out."""
    if isinstance(node, dict):
        return {key: _without_aid(value) for key, value in node.items() if key != "revenue_funding_series"}
    if isinstance(node, (list, tuple)):
        return [_without_aid(value) for value in node]
    return node


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_aid_changes_no_other_field_and_no_lender_or_revenue_figure(monkeypatch, name):
    statement = _statement(SCENARIOS[name][0], balances=True)
    on = tc.classify_statement_transactions(statement)
    monkeypatch.setattr(tr, "funding_series_after", lambda records, duplicate_indexes, statement_start: records)
    off = tc.classify_statement_transactions(statement)
    assert _aid(on) and not _aid(off)
    assert [replace(record, revenue_funding_series=()) for record in on] == off
    for mode in ("legacy_eligible_deposits", "true_revenue"):
        metrics_on = asdict(compute_metrics(statement, classifications=on, withholding_denominator_mode=mode))
        metrics_off = asdict(compute_metrics(statement, classifications=off, withholding_denominator_mode=mode))
        # The evidence lists copy the records (the held wire's copy carries the aid); every figure is equal.
        assert _without_aid(metrics_on) == _without_aid(metrics_off)
        assert {key: value for key, value in metrics_on.items() if not key.endswith("_evidence")} == {
            key: value for key, value in metrics_off.items() if not key.endswith("_evidence")}
    found_on, found_off = detect(statement, classifications=on), detect(statement, classifications=off)
    assert _without_aid(asdict(found_on)) == _without_aid(asdict(found_off))
    assert [funder.funder for funder in found_on.known_funders + found_on.potential_lenders] != []


def test_the_aid_is_frozen_and_hashable_and_last_on_the_record():
    [record] = [r for r in _run(SCENARIOS["A1"][0]) if r.revenue_funding_series]
    assert hash(record) == hash(replace(record))
    with pytest.raises(AttributeError):
        record.revenue_funding_series[0].payee = "FABRICATED"  # type: ignore[misc]
    assert [field.name for field in fields(tc.TransactionClassification)][-1] == "revenue_funding_series"
    assert tc.TransactionClassification("X", "X", "other").revenue_funding_series == ()
    assert [field.name for field in fields(FundingSeries)] == [
        "payee", "lender_state", "amount", "cadence", "average_gap_days", "first_date", "days_after", "payments",
        "start_observed", "source_locations"]


def test_the_pass_reads_the_statement_start_by_keyword_only():
    import inspect

    parameters = inspect.signature(tr.apply_true_revenue_pass).parameters
    assert parameters["statement_start"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["statement_start"].default is None
    # A1 is observed only from the printed start: its earliest dated row is the wire itself, so
    # classify_statement_transactions hands the pass the statement's period start.
    records = [replace(record, revenue_funding_series=()) for record in _run(SCENARIOS["A1"][0])]
    [[series]] = _aid(tr.funding_series_after(records, set(), None)).values()
    assert series.start_observed is False
    [[series]] = _aid(tr.funding_series_after(records, set(), START)).values()
    assert series.start_observed is True
    # A duplicate is never a target, and a statement with no held wire is returned as it is.
    assert tr.funding_series_after(records, {0}, START) == records
    assert tr.funding_series_after(records[1:], set(), START) == records[1:]


# --- C8: the payload ---------------------------------------------------------------------------------------------

def funding_aid_payload(rows=None, *, start=START):
    """The analysed payload of a fabricated statement (A1 by default), as `report_to_dict` writes it."""
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analysis.serialization import document_report_to_dict

    statement = _statement(rows if rows is not None else SCENARIOS["A1"][0], balances=True, start=start)
    statement = statement.model_copy(update={
        "beginning_balance": 100000.0, "ending_balance": statement.transactions[-1].running_balance,
        "account_number": "000000001010", "currency": "USD", "currency_source": "printed"})
    return document_report_to_dict(analyze_statement(statement, reconciliation=reconcile(statement), markdown="",
                                                     sheets=[], model_used="fabricated-test"))


def _served_json(payload):
    from analysis.served_view import displayed

    return json.loads(json.dumps(displayed(payload, settings={})))


def test_the_served_payload_carries_the_aid_as_a_list_of_objects():
    payload = _served_json(funding_aid_payload())
    records = [row["classification"] for row in payload["statement"]["transactions"]]
    assert records[0]["revenue_funding_series"] == [{
        "payee": "Fabrikam Funding LLC", "lender_state": "potential_lender", "amount": 1250.0, "cadence": "weekly",
        "average_gap_days": 7.0, "first_date": "2054-03-11", "days_after": 2, "payments": 3, "start_observed": True,
        "source_locations": ["transaction:2", "transaction:3", "transaction:4"]}]
    assert all(record["revenue_funding_series"] == [] for record in records[1:])
    assert payload["classifications"][0]["revenue_funding_series"] == records[0]["revenue_funding_series"]
    # The posted-credit export table gains no column (the field rides in the evidence JSON cells).
    from webapp.statement_export import _POSTED_CREDIT_COLUMNS
    assert "revenue_funding_series" not in _POSTED_CREDIT_COLUMNS


def test_the_rebuild_and_the_review_writer_keep_the_aid():
    from analysis.revenue import rebuild_serialized_revenue_views, record_serialized_revenue_review

    payload = _served_json(funding_aid_payload())
    aid = payload["statement"]["transactions"][0]["classification"]["revenue_funding_series"]
    assert aid
    rebuild_serialized_revenue_views(payload)
    assert payload["statement"]["transactions"][0]["classification"]["revenue_funding_series"] == aid
    for decision in ("confirm", "reset"):
        record = record_serialized_revenue_review(payload, source_location="transaction:1", decision=decision)
        assert record["revenue_funding_series"] == aid
        rebuild_serialized_revenue_views(payload)
    assert payload["statement"]["transactions"][0]["classification"]["revenue_tier"] == "excluded_pending_review"


# --- Audit round 3, R3-B02 (R3-66): an attempt before the deposit means the series was already running -------------
#
# A potential lender's payment that bounced before a held no-sender wire leaves the pool (the reversal pass cleared its
# counts), so "every date after the deposit" passed and the wire read "Recurring payments start after this deposit:
# possible funding" while the statement shows the series attempted before it. A settlement-reversed attempt is no
# payment of the series, but one dated on or before the deposit's day keeps the aid off, as a paid one does. Fabricated
# rows: CONTOSO DELI LLC at Fifth Third Bank; NORTHWIND CAPITAL GROUP, a D6 payee; KAPITUS, a registry funder.

DELI = "CONTOSO DELI LLC"
NORTHWIND_GROUP = "NORTHWIND CAPITAL GROUP"
NO_SENDER_WIRE = "INCOMING WIRE TRANSFER"
KAPITUS_DELI = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO DELI LLC CO ID:0000000002 CCD"


def _bounced_before(return_text, payee=NORTHWIND_GROUP, *, returned=True):
    """A payment on the 4th (returned on the 5th by `return_text` when `returned`), the held wire on the 10th, then the
    payee's weekly payments on the 11th, 18th and 25th."""
    rows = [(4, payee, -2000.0)]
    if returned:
        rows.append((5, return_text, 2000.0))
    return rows + [(10, NO_SENDER_WIRE, 60000.0)] + _series(payee, -2000.0, 11, 18, 25)


def _deli(rows):
    return _run(rows, holder=DELI)


def _wire(records):
    [wire] = [record for record in records if record.original_description == NO_SENDER_WIRE]
    return wire


R3_66_RETURNS = {
    "named_return": "ACH RETURN NORTHWIND CAPITAL GROUP 0000000",
    "bare_return": "ACH RETURN ITEM NSF",
    "reversal": "REVERSAL ACH DEBIT NORTHWIND CAPITAL GROUP",
}


@pytest.mark.parametrize("name", sorted(R3_66_RETURNS))
def test_r3_66_a_bounced_attempt_before_the_wire_keeps_the_aid_off(name):
    records = _deli(_bounced_before(R3_66_RETURNS[name]))
    wire = _wire(records)
    assert (wire.revenue_tier, wire.revenue_tier_reason) == HELD_WIRE
    assert wire.revenue_funding_series == ()
    # The weekly series after the wire is a potential lender's (D6), and the return's pairing is the reversal pass's.
    assert {record.classification for record in records if record.amount < 0} == {"potential_lender"}


def test_r3_66_the_named_return_zeroes_the_attempt_before_the_wire():
    """The case the aid read: the reversal pass zeroes the 4th's attempt (its counts cleared), so the pool holds only
    the payments after the wire."""
    records = _deli(_bounced_before(R3_66_RETURNS["named_return"]))
    attempt = records[0]
    assert attempt.reversed_by == "transaction:2"
    assert not (attempt.contributes_to_lender_count or attempt.contributes_to_potential_lender_count)


def test_r3_66_controls_read_as_before():
    # A paid payment before the wire: no aid, as today.
    assert _wire(_deli(_bounced_before("", returned=False))).revenue_funding_series == ()
    # No payment before the wire: the series is recorded, its start observed.
    fresh = _wire(_deli([(10, NO_SENDER_WIRE, 60000.0)] + _series(NORTHWIND_GROUP, -2000.0, 11, 18, 25)))
    [series] = fresh.revenue_funding_series
    assert (series.lender_state, series.amount, series.cadence, series.first_date, series.start_observed) == (
        "potential_lender", 2000.0, "weekly", "2054-03-11", True)
    # The confirmed twin: KAPITUS's payment returned before the wire (R2-OW13 keeps its count): no aid, as today.
    twin = _deli(_bounced_before("RETURNED ITEM KAPITUS 0001", KAPITUS_DELI))
    assert _wire(twin).revenue_funding_series == ()
    assert twin[0].contributes_to_lender_count is True
    # A return after the wire of a payment after it is no attempt before the deposit: the series is recorded.
    late = _wire(_deli([(10, NO_SENDER_WIRE, 60000.0)] + _series(NORTHWIND_GROUP, -2000.0, 11, 18, 25)
                       + [(26, R3_66_RETURNS["named_return"], 2000.0)]))
    assert [series.first_date for series in late.revenue_funding_series] == ["2054-03-11"]


@pytest.mark.parametrize("name", sorted(R3_66_RETURNS))
def test_r3_66_moves_no_tier_reason_or_lender_reading(monkeypatch, name):
    rows = _bounced_before(R3_66_RETURNS[name])
    on = _deli(rows)
    monkeypatch.setattr(tr, "funding_series_after", lambda records, duplicate_indexes, statement_start: records)
    off = _deli(rows)
    assert [replace(record, revenue_funding_series=()) for record in on] == off
