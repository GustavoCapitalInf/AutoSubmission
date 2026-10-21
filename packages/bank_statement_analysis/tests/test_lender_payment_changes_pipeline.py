"""The owner's request of 2026-10-06 (lender payment changes; true revenue spec §9.1; R2-OW18, parts C, D, E, I): the
statement-level items through analysis.pipeline.analyze_statement and analysis.serialization.document_report_to_dict,
the record field `potential_payee_key`, the CLI and batch rows, R2-OW17's readings and a review decision.

Information only: with `analysis.lender_payment_changes.statement_payment_changes` patched to return [] (the
detector-off template of tests/test_returned_funder_payments.py), every metric, lender list and record is the same.

Fabricated rows only (CONTOSO PLUMBING LLC; FABRIKAM, NORTHWIND and SAMPLE payees; KAPITUS, a public funder of the
registry; 2054 dates; neutral whole amounts)."""
from __future__ import annotations

import json
from dataclasses import asdict, fields
from datetime import date, timedelta
from pathlib import Path

import pytest

from analysis import lender_payment_changes as lpc
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import TransactionClassification
from tests.helpers import bdays, every

HOLDER = "CONTOSO PLUMBING LLC"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000001 CCD"
KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD"
FUNDING = "KAPITUS DES:FUNDING ID:000000003 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD"
NAMED = "NORTHWIND FUNDING DES:DEBIT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000003 PPD"
UNNAMED_PAYEE = "NORTHWIND TRADERS DES:DEBIT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000003 PPD"
BOUNCE = "ZELLE PAYMENT FROM PAT SAMPLE NOT PAID CONF 7"
BOFA = "Bank of America"
UNNAMED = "Unidentified lender obligation"


def M(day):  # noqa: N802
    return date(2054, 3, day)


def A(day):  # noqa: N802
    return date(2054, 4, day)


def _statement(rows, *, start=M(1), end=M(31), bank=BOFA, currency="USD", account="000000001010") -> Statement:
    """(day, description, amount) rows in date order (a sale first), printed balances, reconciled."""
    transactions, balance = [], 50000.0
    for day, text, amount in sorted(rows, key=lambda row: row[0]):
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=day.isoformat(), description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    return Statement(account_name=HOLDER, bank=bank, account_number=account, period_start=start.isoformat(),
                     period_end=end.isoformat(), beginning_balance=50000.0, ending_balance=balance, currency=currency,
                     currency_source="printed", transactions=transactions)


def _analysed(rows, **kwargs):
    from analysis.pipeline import analyze_statement

    statement = _statement(rows, **kwargs)
    return analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                             model_used="fabricated-test")


def _payload(rows, **kwargs):
    from analysis.serialization import document_report_to_dict

    return json.loads(json.dumps(document_report_to_dict(_analysed(rows, **kwargs))))


def _account(payload):
    from analysis.payload_shape import payload_accounts

    [account] = payload_accounts(payload, surface="tests/test_lender_payment_changes_pipeline.py")
    return account


def _debits(days, text, amount):
    return [(day, text, -float(amount)) for day in days]


L1 = [(M(1), SALE, 10000.0), *_debits(bdays(M(2), M(13)), KAPITUS, 850), *_debits(bdays(M(16), M(25)), KAPITUS, 600)]


# ------------------------------------------------------------------------------------------------------------ P-L1
def test_p_l1_the_detection_carries_one_decrease_item():
    account = _account(_payload(L1))
    [item] = account["detection"]["lender_payment_changes"]
    assert (item["kind"], item["lender"], item["lender_label"], item["lender_state"], item["change_percent"]) == (
        "decrease", "KAPITUS", "KAPITUS", "confirmed", -29)
    assert (item["payments_before"], item["payments_after"], item["first_after_date"], item["scope"]) == (
        10, 8, "2054-03-16", "statement")
    assert item["locations"] == {"last_before": "transaction:11", "first_after": "transaction:12"}
    assert list(account["detection"]).index("lender_payment_changes") == list(account["detection"]).index(
        "returned_funder_payments") + 1


def test_p_l1_the_cli_and_the_batch_columns():
    import analyze
    import batch

    report = _analysed(L1).accounts[0]
    text = analyze._render(report)
    assert "  Lender payment changes:" in text.splitlines()
    assert "    - decrease: KAPITUS daily $850.00 -> $600.00 (-29%) from 2054-03-16, 8 payments (was 10)" in (
        text.splitlines())
    row = batch._row(Path("fabricated.md"), report)
    assert [row[name] for name in ("lender_payment_decreases", "lender_payment_increases",
                                   "lender_payment_cadence_changes", "lender_payment_new_streams",
                                   "lender_payment_pauses", "lender_payment_possible_stops",
                                   "lender_payment_catch_ups", "lender_payment_changes")] == [
        1, 0, 0, 0, 0, 0, 0, "decrease:KAPITUS"]
    # Audit round 3, R3-B05 (the owner's answer of 2026-10-07 to R3-25): the catch-up count column.
    start = batch.FIELDS.index("recurring_debit_groups") + 1
    assert batch.FIELDS[start:start + 8] == [
        "lender_payment_decreases", "lender_payment_increases", "lender_payment_cadence_changes",
        "lender_payment_new_streams", "lender_payment_pauses", "lender_payment_possible_stops",
        "lender_payment_catch_ups", "lender_payment_changes"]
    quiet = analyze._render(_analysed([(M(1), SALE, 10000.0)]).accounts[0])
    assert "  Lender payment changes: none" in quiet.splitlines()


def test_r1_the_cli_names_an_attempt_and_the_unreported_steps():
    """R2-OW18 review round 1: the CLI line of a pause a bounced attempt ended, of a stop whose last presence is an
    attempt and of a change through unreported levels (fabricated module items)."""
    import analyze
    from tests import test_lender_payment_changes as pure

    regular = pure._rows(pure.bdays(M(2), M(6)) + pure.bdays(M(23), M(31)), 850)
    pause = pure.only(regular + pure._rows([M(16)], 850, returned_funder_payment_by="transaction:99"))
    assert analyze._payment_change_line(pause) == (
        "pause: KAPITUS daily $850.00, no payment or attempt 2054-03-06 to 2054-03-16, 6 business days (grace 5); "
        "a returned attempt on 2054-03-16, payments resumed on 2054-03-23")
    other = pure.only(regular + pure._rows([M(16)], 425))
    assert analyze._payment_change_line(other).endswith(
        "6 business days (grace 5); a payment at another amount on 2054-03-16, payments resumed on 2054-03-23")
    stop = pure.only(pure._rows(pure.every(M(4), A(1)), 1000)
                     + pure._rows([pure.A(8)], 1000, returned_funder_payment_by="transaction:99"), end=pure.Y(1))
    # Audit round 3, R3-B06 (R3-85): the count runs from the returned attempt, and names it as its anchor.
    assert analyze._payment_change_line(stop) == (
        f"possible stop: KAPITUS weekly, last $1,000.00 on 2054-04-01, a returned attempt on 2054-04-08, "
        f"{stop['quiet_business_days']} business days after 2054-04-08 to the period end (grace 10)")
    steps = pure.only(pure._rows(pure.every(M(2), M(16)), 1000) + pure._rows(pure.every(M(23), A(6)), 950)
                      + pure._rows(pure.every(A(13), A(27)), 650), end=A(30))
    assert analyze._payment_change_line(steps) == (
        "decrease: KAPITUS weekly $1,000.00 -> $650.00 (-35%) from 2054-04-13, 3 payments (was 3), "
        "via weekly $950.00 (-5%), then -32%")


def test_r3_b05_the_cli_and_the_batch_name_a_catch_up():
    """Audit round 3, R3-B05 (R3-25 and the owner's answer of 2026-10-07, "Add a 'Caught up' line"): the CLI line of a
    pause a catch-up ended and of a Caught up item, and the batch's count (fabricated module items)."""
    import analyze
    import batch
    from tests import test_lender_payment_changes as pure

    pause = pure.only(pure._rows(pure.bdays(M(2), M(6)) + pure.bdays(M(23), M(31)), 300)
                      + pure._rows([M(16)], 1800))
    assert analyze._payment_change_line(pause) == (
        "pause: KAPITUS daily $300.00, no payment 2054-03-06 to 2054-03-16, 6 business days (grace 5); a catch-up of "
        "6x on 2054-03-16, payments resumed on 2054-03-23")
    two = pure.only(pure._rows(pure.bdays(M(2), M(13)) + pure.bdays(M(19), M(31)), 850)
                    + pure._rows([M(18)], 1700))
    assert analyze._payment_change_line(two) == (
        "catch-up: KAPITUS daily $850.00, no payment on 2 scheduled payments 2054-03-16 to 2054-03-17, then 2x "
        "$1,700.00 on 2054-03-18")
    one = pure.only(pure._rows(pure.bdays(M(2), M(13)) + pure.bdays(M(18), M(31)), 850)
                    + pure._rows([M(17)], 1700))
    assert analyze._payment_change_line(one) == (
        "catch-up: KAPITUS daily $850.00, no payment on 1 scheduled payment 2054-03-16, then 2x $1,700.00 on "
        "2054-03-17")
    # Review round 1 (finding 2): a catch-up after the bounced attempt that ended the pause, before payments resumed.
    attempt = pure._rows([M(16)], 850, returned_funder_payment_by="transaction:99")
    inside = pure.only(pure._rows(pure.bdays(M(2), M(6)) + pure.bdays(M(18), M(31)), 850) + attempt
                       + pure._rows([M(17)], 1700))
    assert analyze._payment_change_line(inside) == (
        "pause: KAPITUS daily $850.00, no payment or attempt 2054-03-06 to 2054-03-16, 6 business days (grace 5); a "
        "returned attempt on 2054-03-16, payments resumed on 2054-03-18; a catch-up of 2x on 2054-03-17 before "
        "payments resumed")
    columns = batch._payment_change_columns([two, pause, {**one, "lender_state": "potential"}])
    assert (columns["lender_payment_catch_ups"], columns["lender_payment_pauses"]) == (2, 1)
    assert columns["lender_payment_changes"] == "catch_up:KAPITUS; pause:KAPITUS; catch_up:KAPITUS (potential)"


def test_r3_85_the_cli_stop_line_names_the_later_debits_and_the_count_s_anchor():
    """Audit round 3, R3-B06 (R3-85): a statement possible stop whose last presence is a later debit at another amount
    names those debits and counts its business days after the last of them; a stop whose last presence is its last
    payment prints as before (fabricated module items)."""
    import analyze
    from tests import test_lender_payment_changes as pure

    later = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._rows([M(16)], 400) + pure._rows([M(19)], 500))
    assert (later["kind"], later["other_debits_after"], later["quiet_business_days"]) == (
        "stop", {"count": 2, "last_date": "2054-03-19"}, 8)
    assert analyze._payment_change_line(later) == (
        "possible stop: KAPITUS daily, last $850.00 on 2054-03-13; 2 later debits at other amounts, the last on "
        "2054-03-19; 8 business days after 2054-03-19 to the period end (grace 5)")
    one = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._rows([M(18)], 400))
    assert analyze._payment_change_line(one) == (
        "possible stop: KAPITUS daily, last $850.00 on 2054-03-13; 1 later debit at other amounts, the last on "
        "2054-03-18; 9 business days after 2054-03-18 to the period end (grace 5)")
    plain = pure.only(pure._rows(pure.every(A(1), pure.Y(13)), 1000), start=A(1), end=pure.Y(29))
    assert analyze._payment_change_line(plain) == (
        "possible stop: KAPITUS weekly, last $1,000.00 on 2054-05-13, 11 business days to the period end (grace 10)")


def test_p_l1_the_detector_moves_nothing_else(monkeypatch):
    import batch

    on = _analysed(L1).accounts[0]
    monkeypatch.setattr(lpc, "statement_payment_changes", lambda *args, **kwargs: [])
    off = _analysed(L1).accounts[0]
    assert len(on.detection.lender_payment_changes) == 1 and off.detection.lender_payment_changes == []
    assert asdict(on.metrics) == asdict(off.metrics)
    for name in ("known_funders", "potential_lenders", "recurring_debits", "flagged_positions",
                 "returned_funder_payments", "lender_evidence", "potential_lender_evidence"):
        assert repr(getattr(on.detection, name)) == repr(getattr(off.detection, name))
    assert [asdict(record) for record in on.classifications] == [asdict(record) for record in off.classifications]
    on_row, off_row = batch._row(Path("fabricated.md"), on), batch._row(Path("fabricated.md"), off)
    assert on_row["needs_review"] == off_row["needs_review"]
    assert {key: value for key, value in on_row.items() if not key.startswith("lender_payment_")} == {
        key: value for key, value in off_row.items() if not key.startswith("lender_payment_")}


# ------------------------------------------------------------------------------------------ P-L11, P-L12: bounces
def _return(day, debit_day):
    return (day, f"RETURN OF POSTED CHECK ITEM RECEIVED ON {debit_day:%m/%d} {day:%m/%d}", 850.0)


def test_p_l11_a_bounce_inside_a_series_is_no_item_and_keeps_r2_ow13_s_warning():
    rows = [(M(1), SALE, 30000.0), *_debits(bdays(M(2), M(31)), KAPITUS, 850), _return(M(12), M(11))]
    detection = _account(_payload(rows))["detection"]
    assert detection["lender_payment_changes"] == []
    [returned] = detection["returned_funder_payments"]
    assert (returned["funder"], returned["debit_date"]) == ("KAPITUS", "2054-03-11")


def test_p_l12_a_bounced_tail_is_no_stop():
    rows = [(M(1), SALE, 30000.0), *_debits(every(M(4), A(8)), KAPITUS, 1000)]
    for day in every(A(15), A(29)):
        rows += [(day, KAPITUS, -1000.0),
                 (day + timedelta(days=1), f"RETURN OF POSTED CHECK ITEM RECEIVED ON {day:%m/%d} "
                                           f"{day + timedelta(days=1):%m/%d}", 1000.0)]
    detection = _account(_payload(rows, end=A(30)))["detection"]
    assert len(detection["returned_funder_payments"]) == 3
    assert detection["lender_payment_changes"] == []
    # Without the returns the series stops (L12's control).
    quiet = _account(_payload([(M(1), SALE, 30000.0), *_debits(every(M(4), A(8)), KAPITUS, 1000)], end=A(30)))
    [stop] = quiet["detection"]["lender_payment_changes"]
    assert (stop["kind"], stop["quiet_business_days"], stop["grace_business_days"]) == ("stop", 16, 10)


# ------------------------------------------------------------------------------------------------- P-L13: renewal
def test_p_l13_a_renewal_names_the_funding_credit():
    rows = [(M(1), SALE, 10000.0), *_debits(bdays(M(2), M(13)), KAPITUS, 850), (M(13), FUNDING, 25000.0),
            *_debits(bdays(M(16), M(25)), KAPITUS, 1050)]
    account = _account(_payload(rows))
    [item] = account["detection"]["lender_payment_changes"]
    assert (item["kind"], item["change_percent"], item["after_funding"]) == (
        "increase", 24, {"date": "2054-03-13", "amount": 25000.0})
    credit = next(row["classification"] for row in account["statement"]["transactions"]
                  if row["description"] == FUNDING)
    # The funding credit names its funder on both entity fields (the financing-proceeds rule).
    assert (credit["canonical_entity"], credit["revenue_canonical_entity"]) == ("KAPITUS", "KAPITUS")


# ----------------------------------------------------------------------------------- P-L24, P-L25: potential payees
def _potential_rows(text, after_days=None):
    after_days = bdays(M(16), M(25)) if after_days is None else after_days
    return [(M(1), SALE, 10000.0), *_debits(bdays(M(2), M(13)), text, 300), *_debits(after_days, text, 250)]


def test_p_l24_an_unnamed_potential_payee_keeps_one_key_across_its_labels():
    account = _account(_payload(_potential_rows(UNNAMED_PAYEE)))
    records = [row["classification"] for row in account["statement"]["transactions"]
               if row["description"] == UNNAMED_PAYEE]
    assert {record["classification"] for record in records} == {"potential_lender"}
    keys = {record["potential_payee_key"] for record in records}
    [key] = keys
    assert len(key) == 16 and all(character in "0123456789abcdef" for character in key)
    assert not any(word in key.upper() for word in ("NORTHWIND", "TRADERS"))
    assert {record["potential_payee_label"] for record in records} == {f"{UNNAMED} (daily, 300.00)",
                                                                        f"{UNNAMED} (daily, 250.00)"}
    [item] = account["detection"]["lender_payment_changes"]
    assert (item["kind"], item["lender_state"], item["lender"], item["change_percent"]) == (
        "decrease", "potential", UNNAMED, -17)
    assert (item["lender_label"], item["lender_label_after"]) == (f"{UNNAMED} (daily, 300.00)",
                                                                  f"{UNNAMED} (daily, 250.00)")


def test_p_l24_a_named_potential_payee():
    account = _account(_payload(_potential_rows(NAMED)))
    records = [row["classification"] for row in account["statement"]["transactions"] if row["description"] == NAMED]
    assert {(record["classification"], record["canonical_entity"], record["match_method"],
             record["potential_payee_label"]) for record in records} == {
        ("potential_lender", "Northwind Funding", "recurring_fixed_debit", None)}
    assert len({record["potential_payee_key"] for record in records}) == 1
    [item] = account["detection"]["lender_payment_changes"]
    assert (item["kind"], item["lender_state"], item["lender"], item["lender_label"]) == (
        "decrease", "potential", "Northwind Funding", "Northwind Funding")


def test_p_l25_a_new_amount_joins_only_once_promoted():
    account = _account(_payload(_potential_rows(UNNAMED_PAYEE, [M(16), M(17)])))
    later = [row["classification"] for row in account["statement"]["transactions"]
             if row["description"] == UNNAMED_PAYEE and row["amount"] == -250.0]
    assert {(record["classification"], record["potential_payee_key"]) for record in later} == {("other", None)}
    assert [item["kind"] for item in account["detection"]["lender_payment_changes"]] == ["stop"]


# ----------------------------------------------------------------------------------------- P-L30: the record field
def test_p_l30_the_record_field():
    names = [item.name for item in fields(TransactionClassification)]
    assert names.index("potential_payee_key") == names.index("potential_payee_label") + 1
    assert names[-1] == "revenue_funding_series"
    account = _account(_payload(L1 + _potential_rows(UNNAMED_PAYEE)[1:]))
    for row in account["statement"]["transactions"]:
        record = row["classification"]
        assert (record["potential_payee_key"] is not None) == (record["classification"] == "potential_lender")


# ------------------------------------------------------------------------------------- P-R1: R2-OW17's readings
def test_p_r1_each_reading_s_items_follow_its_records():
    from analysis import zelle_view

    rows = [(M(1), SALE, 10000.0), *_debits(every(M(2), M(23)), KAPITUS, 1000), (M(30), KAPITUS, -700.0),
            (M(31), BOUNCE, 700.0), (A(6), KAPITUS, -700.0)]
    report = _analysed(rows, end=A(10)).accounts[0]
    counted = report.zelle_counted
    assert counted is not None
    bounced = next(index for index, record in enumerate(report.classifications)
                   if record.date == "2054-03-30" and record.amount < 0)
    # No: rule D pairs the Zelle bounce form, so the 700 debit is an attempt and the 700 level a one-off.
    assert report.classifications[bounced].returned_funder_payment_by is not None
    assert counted.classifications[bounced].returned_funder_payment_by is None
    assert report.detection.lender_payment_changes == []
    [item] = counted.detection.lender_payment_changes
    assert (item["kind"], item["change_percent"], item["payments_after"]) == ("decrease", -30, 2)
    for reading in (report, counted):
        assert reading.detection.lender_payment_changes == lpc.statement_payment_changes(
            reading.classifications, period_start="2054-03-01", period_end="2054-04-10", currency="USD")
    from analysis.serialization import document_report_to_dict

    payload = json.loads(json.dumps(document_report_to_dict(_analysed(rows, end=A(10)))))
    assert _account(zelle_view.apply_zelle_view(payload, counted=False))["detection"]["lender_payment_changes"] == []
    served = _account(zelle_view.apply_zelle_view(payload, counted=True))["detection"]["lender_payment_changes"]
    assert [entry["kind"] for entry in served] == ["decrease"]


# ------------------------------------------------------------------------------------------ P-R2: a review decision
@pytest.mark.parametrize("decision", ["confirm", "reject"])
def test_p_r2_a_review_decision_leaves_the_items_as_they_are(decision):
    from analysis.revenue import rebuild_serialized_revenue_views, record_serialized_revenue_review

    payload = _payload([*L1, (M(1), "DEPOSIT", 2345.0)])
    before = _account(payload)["detection"]["lender_payment_changes"]
    assert [item["kind"] for item in before] == ["decrease"]
    deposit = next(row["classification"] for row in _account(payload)["statement"]["transactions"]
                   if row["description"] == "DEPOSIT")
    assert deposit["revenue_tier"] == "counted_flagged"
    record_serialized_revenue_review(payload, source_location=deposit["source_location"], decision=decision)
    rebuild_serialized_revenue_views(payload)
    assert _account(payload)["detection"]["lender_payment_changes"] == before
