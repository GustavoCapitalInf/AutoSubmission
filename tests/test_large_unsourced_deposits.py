"""Audit round 3, R3-B24 (R3-16; true revenue spec §9.1, §9.2, §10.1, §10.6, §10.7, §10.8, §13, §17.1, §20; standard
G7, "Large one-off or unexplained deposits: COUNT+FLAG, and source them when large", and P22, "count + flag + source"):
a counted credit whose source the statement does not prove (a bare, cash or branch deposit, a check deposit, a named
sender's wire, a one-off or unlabelled payer, a numbered company, P2P, payer text not read) is counted in True and never
Verified, as the owner's Q2-Q6 and OQ3 of 2026-09-28 rule. Nothing measured its size or its share of True, so one such
deposit could carry most of the True an advance is sized on with no signal on any surface. A new served flag, for
information only: a counted credit of $10,000 or more that is more than 25% of its statement's True, on those eight
reasons (the owner-decision default D1, §17.1), is listed (`large_unsourced_deposits`, with its count and total) on the
served copy of a statement whose revenue is established, on the package (each member's own share), in the statement
and package downloads and in both CLIs. No tier, reason, True or Verified figure, review gate, badge or decision reads it.

Fabricated statements only (CONTOSO CAFE LLC at Sample Bank, 2033; SQUARE payouts, NORTHWIND and SAMPLE payers, the
own-account fixture of tests/test_package_matching; neutral round amounts), analysed by the real per-account path."""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path

import pytest

HOLDER = "CONTOSO CAFE LLC"
#: A card processor's payout to the holder: Verified revenue (a repeat payout with its id).
SQUARE = "SQUARE INC DES:SQ0000000 ID:000000000000000 INDN:CONTOSO CAFE LLC CO ID:0000000000 CCD"
#: Counted, never Verified: a bare deposit (`no_payer_printed`), a check deposit, a named sender's wire.
DEPOSIT = "DEPOSIT"
CHECK = "REMOTE ONLINE DEPOSIT 1"
WIRE = "INCOMING WIRE TRANSFER ORIGINATOR NAME: NORTHWIND HOLDINGS LLC"
#: Held (`wire_no_sender`), and counted for a reason outside the flag (`construction_progress_draw`).
WIRE_NO_SENDER = "WIRE TRANSFER IN REF 000000000"
DRAW = "NORTHWIND BUILDERS DES:PROGRESS DRAW ID:0001 INDN:CONTOSO CAFE LLC"
ZELLE = "ZELLE FROM SAMPLE CONTOSO"
SQUARE_DAYS = (1, 3, 5, 8, 10, 12, 15, 17, 19, 22)
ACCOUNT = "000000003030"
FLAG_KEYS = ("large_unsourced_deposit_count", "large_unsourced_deposit_total", "large_unsourced_deposits")


def _report(rows, *, month=5, number=ACCOUNT, currency="USD", dropped=None, opening=1000.0):
    """One month of CONTOSO CAFE LLC at Sample Bank (2033), each row `(day, description, amount)` with its running
    balance and the bank's summary printing the credits and debits, so the revenue is established. With `dropped` (a
    day), the capture loses that day's row (its balance still printed): the captured credits are not the bank's Total
    and the revenue is not established."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    balance, transactions = opening, []
    for day, text, amount in sorted(rows, key=lambda row: row[0]):
        balance = round(balance + amount, 2)
        if day == dropped:
            continue
        transactions.append(Transaction(date=f"2033-{month:02d}-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(
        bank="Sample Bank", account_name=HOLDER, account_number=number, period_start=f"2033-{month:02d}-01",
        period_end=f"2033-{month:02d}-28", beginning_balance=opening, ending_balance=balance, currency=currency,
        currency_source="printed", stated_total_credits=round(sum(row[2] for row in rows if row[2] > 0), 2),
        stated_total_debits=round(-sum(row[2] for row in rows if row[2] < 0), 2), transactions=transactions,
    )
    return pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )


def _payload(rows, **kwargs):
    from analysis.pipeline import DocumentReport
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(DocumentReport(accounts=[_report(rows, **kwargs)]))


def _served(payload, zelle=True):
    from webapp.app import _displayed
    return _displayed(payload, settings={"zelle_true_revenue": zelle})


def _job(job_id, payload):
    from webapp.jobs import Job
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def _package(*members, zelle=True):
    from webapp.app import _package_analysis
    return _package_analysis([_job(job_id, payload) for job_id, payload in members],
                             settings={"zelle_true_revenue": zelle})


def _squares(days=SQUARE_DAYS, amount=2500.0):
    return [(day, SQUARE, amount) for day in days]


#: L1: ten Square payouts of 2,500.00 (Verified), a bare DEPOSIT of 150,000.00, a check deposit of 90,000.00 and a named
#: sender's wire of 120,000.00 (each counted). True 385,000.00.
L1 = [*_squares(), (6, DEPOSIT, 150000.0), (13, CHECK, 90000.0), (20, WIRE, 120000.0)]
L1_FLAGS = [
    {"source_location": "transaction:4", "date": "2033-05-06", "description": DEPOSIT, "amount": 150000.0,
     "revenue_tier_reason": "no_payer_printed", "share_of_true_percent": 39.0},
    {"source_location": "transaction:12", "date": "2033-05-20", "description": WIRE, "amount": 120000.0,
     "revenue_tier_reason": "wire_named_sender", "share_of_true_percent": 31.2},
]


def _without_flag(node):
    """A copy of a served payload or package with the flag's keys removed wherever they sit."""
    if isinstance(node, dict):
        return {key: _without_flag(value) for key, value in node.items() if key not in FLAG_KEYS}
    if isinstance(node, list):
        return [_without_flag(value) for value in node]
    return node


def _reader_finds_nothing(monkeypatch):
    """The flag's reader finding nothing, from here on in the test: what every surface computed before the batch."""
    from analysis import revenue_view
    from webapp import app as appmod

    monkeypatch.setattr(revenue_view, "large_unsourced_deposits", lambda transactions, true_total: [])
    monkeypatch.setattr(appmod, "large_unsourced_deposits", lambda transactions, true_total: [])


# ---------------------------------------------------------------- the reader and its constants

def test_the_flag_s_constants_are_the_owner_decision_default():
    from analysis import revenue_view

    assert revenue_view.LARGE_UNSOURCED_DEPOSIT_FLOOR == 10_000
    assert revenue_view.LARGE_UNSOURCED_DEPOSIT_SHARE == 25
    assert revenue_view.LARGE_UNSOURCED_DEPOSIT_REASONS == frozenset({
        "no_payer_printed", "check_deposit", "wire_named_sender", "named_payer_one_off", "numbered_company_payer",
        "p2p", "named_payer_unlabelled", "payer_text_not_read"})
    assert revenue_view.LARGE_UNSOURCED_DEPOSIT_FIELDS == (
        "source_location", "date", "description", "amount", "revenue_tier_reason", "share_of_true_percent")
    # Every reason is one of the counted tier's codes.
    from analysis.revenue import REVENUE_TIER_REASONS
    assert all(REVENUE_TIER_REASONS[reason][0] == "counted_flagged"
               for reason in revenue_view.LARGE_UNSOURCED_DEPOSIT_REASONS)


def _row(location, amount, *, tier="counted_flagged", reason="no_payer_printed", **record):
    return {"date": "2033-05-06", "description": "DEPOSIT", "amount": amount,
            "classification": {"source_location": location, "revenue_tier": tier, "revenue_tier_reason": reason,
                               "is_posted": True, "duplicate_of": None, **record}}


def test_the_reader_keeps_a_counted_unsourced_credit_by_its_size_and_share_and_never_mutates():
    from analysis.revenue_view import large_unsourced_deposit_metrics, large_unsourced_deposits

    rows = [
        _row("transaction:1", 10000.0),                                   # 25.0025% of 39,996.00: kept
        _row("transaction:2", 9999.99),                                   # under the floor
        _row("transaction:3", 10000.0, tier="verified", reason=None),     # Verified
        _row("transaction:4", 10000.0, tier="excluded_pending_review", reason="wire_no_sender"),
        _row("transaction:5", 10000.0, reason="construction_progress_draw"),
        _row("transaction:6", 10000.0, is_posted=False),
        _row("transaction:7", 10000.0, duplicate_of="transaction:1"),
        _row("transaction:8", -10000.0),
        {"date": "2033-05-09", "description": "DEPOSIT", "amount": 10000.0},  # no classification record
        _row("", 12000.0, reason="p2p"),                                  # no location: its place
    ]
    stored = copy.deepcopy(rows)
    flags = large_unsourced_deposits(rows, 39996.0)
    assert rows == stored
    assert flags == [
        {"source_location": "transaction:1", "date": "2033-05-06", "description": "DEPOSIT", "amount": 10000.0,
         "revenue_tier_reason": "no_payer_printed", "share_of_true_percent": 25.0},
        {"source_location": "transaction:10", "date": "2033-05-06", "description": "DEPOSIT", "amount": 12000.0,
         "revenue_tier_reason": "p2p", "share_of_true_percent": 30.0},
    ]
    assert large_unsourced_deposit_metrics(flags) == {
        "large_unsourced_deposit_count": 2, "large_unsourced_deposit_total": 22000.0, "large_unsourced_deposits": flags}
    assert large_unsourced_deposit_metrics([]) == {}
    # No True, or none above zero: nothing is flagged.
    assert large_unsourced_deposits(rows, None) == large_unsourced_deposits(rows, 0.0) == []
    assert large_unsourced_deposits(None, 39996.0) == []


# ---------------------------------------------------------------- L1: the served flag

def test_l1_two_large_unsourced_deposits_are_flagged_and_nothing_else_moves(monkeypatch):
    payload = _payload(L1)
    stored = copy.deepcopy(payload)
    served = _served(payload)
    metrics = served["metrics"]
    assert (metrics["true_revenue_total"], metrics["verified_revenue_total"]) == (385000.0, 25000.0)
    assert metrics["revenue_review_required"] is False and metrics["revenue_established"] is True
    # Never stored: the payload is untouched.
    assert payload == stored and not any(key in payload["metrics"] for key in FLAG_KEYS)
    assert (metrics["large_unsourced_deposit_count"], metrics["large_unsourced_deposit_total"]) == (2, 270000.0)
    assert metrics["large_unsourced_deposits"] == L1_FLAGS
    # The check deposit is 23.4% of True: counted, and not flagged.
    check = next(row for row in served["statement"]["transactions"] if row["description"] == CHECK)
    assert check["classification"]["revenue_tier"] == "counted_flagged"
    # Nothing else reads it: the served copy without the flag is the served copy the reader finding nothing gives.
    _reader_finds_nothing(monkeypatch)
    before = _served(payload)
    assert not any(key in before["metrics"] for key in FLAG_KEYS)
    assert _without_flag(served) == before


def test_l1_the_served_keys_follow_the_debit_flags():
    metrics = list(_served(_payload(L1))["metrics"])
    assert metrics[-3:] == list(FLAG_KEYS)


# ---------------------------------------------------------------- L2: the boundaries

@pytest.mark.parametrize(("rows", "true_total", "flagged"), [
    # 9,999.99 at 90% of True: under the floor.
    ([(2, SQUARE, 1111.11), (6, DEPOSIT, 9999.99)], 11111.10, []),
    # 10,000.00 at exactly 25.00% of 40,000.00: the share is strictly above 25.
    ([*_squares(range(1, 13)), (14, DEPOSIT, 10000.0)], 40000.0, []),
    # 10,000.00 at 25.0025% of 39,996.00.
    ([*_squares(range(1, 12)), (12, SQUARE, 2496.0), (14, DEPOSIT, 10000.0)], 39996.0, [(10000.0, 25.0)]),
])
def test_l2_the_floor_is_inclusive_and_the_share_strict(rows, true_total, flagged):
    metrics = _served(_payload(rows))["metrics"]
    assert metrics["true_revenue_total"] == true_total
    assert [(item["amount"], item["share_of_true_percent"]) for item in metrics.get("large_unsourced_deposits", [])] == (
        flagged)
    assert ("large_unsourced_deposit_count" in metrics) is bool(flagged)


# ---------------------------------------------------------------- L3: outside the flag

def test_l3_a_verified_held_or_other_counted_credit_and_a_confirmed_deposit_are_never_flagged():
    from analysis.revenue import apply_serialized_revenue_review

    rows = [*_squares(), (24, SQUARE, 150000.0), (6, WIRE_NO_SENDER, 150000.0), (14, DRAW, 150000.0),
            (16, DEPOSIT, 150000.0)]
    payload = _payload(rows)
    served = _served(payload)
    metrics = served["metrics"]
    readings = {row["description"]: (row["amount"], row["classification"]["revenue_tier"],
                                     row["classification"]["revenue_tier_reason"])
                for row in served["statement"]["transactions"] if row["amount"] >= 150000.0}
    assert readings == {SQUARE: (150000.0, "verified", None),
                        WIRE_NO_SENDER: (150000.0, "excluded_pending_review", "wire_no_sender"),
                        DRAW: (150000.0, "counted_flagged", "construction_progress_draw"),
                        DEPOSIT: (150000.0, "counted_flagged", "no_payer_printed")}
    assert metrics["true_revenue_total"] == 475000.0
    # Only the bare deposit (31.6% of True) is flagged; the gate is the held wire's, as before.
    assert [item["description"] for item in metrics["large_unsourced_deposits"]] == [DEPOSIT]
    assert metrics["revenue_review_required"] is True
    location = metrics["large_unsourced_deposits"][0]["source_location"]
    confirmed = apply_serialized_revenue_review(copy.deepcopy(payload), source_location=location, decision="confirm")
    after = _served(confirmed)["metrics"]
    assert after["true_revenue_total"] == 475000.0 and after["verified_revenue_total"] == 325000.0
    assert not any(key in after for key in FLAG_KEYS)


# ---------------------------------------------------------------- L4, L5: no flag key

def test_l4_a_statement_whose_revenue_is_not_established_carries_no_flag():
    served = _served(_payload(L1, dropped=1))
    assert served["metrics"]["revenue_established"] is False
    assert not any(key in served["metrics"] for key in FLAG_KEYS)


def test_l5_a_statement_with_no_flag_is_served_and_downloaded_as_before():
    from webapp.app import _analysis_csv, _displayed, _masked

    payload = _payload([*_squares(), (6, DEPOSIT, 4000.0)])
    served = _served(payload)
    # The served-only keys every statement already carried: the two revenue flags and the NSF days the chip lists.
    assert set(served["metrics"]) - set(payload["metrics"]) == {"verified_revenue_established", "revenue_established",
                                                                "nsf_days"}
    exported = _analysis_csv(_masked(_displayed(payload, settings={}, export=True)))
    assert "large_unsourced" not in exported


# ---------------------------------------------------------------- L6: the reading shown (R2-OW17)

def test_l6_a_counted_zelle_deposit_is_flagged_under_yes_and_not_under_no():
    payload = _payload([*_squares(range(1, 19)), (20, ZELLE, 30000.0)])
    yes = _served(payload, zelle=True)["metrics"]
    assert yes["true_revenue_total"] == 75000.0
    assert yes["large_unsourced_deposits"] == [
        {"source_location": "transaction:19", "date": "2033-05-20", "description": ZELLE, "amount": 30000.0,
         "revenue_tier_reason": "p2p", "share_of_true_percent": 40.0}]
    no = _served(payload, zelle=False)["metrics"]
    assert no["true_revenue_total"] == 45000.0
    assert not any(key in no for key in FLAG_KEYS)


# ---------------------------------------------------------------- L7: the package

MARCH = [*_squares(), (6, DEPOSIT, 150000.0), (20, WIRE, 120000.0)]
APRIL = [*_squares(), (13, CHECK, 30000.0)]


def _months(april_currency="USD"):
    march = _payload(MARCH, month=3)
    april = _payload(APRIL, month=4, currency=april_currency,
                     number=ACCOUNT if april_currency == "USD" else "000000004040")
    return march, april


def test_l7_a_package_lists_each_member_s_flags_with_its_statement_and_sums_them():
    march, april = _months()
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    assert (totals["large_unsourced_deposit_count"], totals["large_unsourced_deposit_total"]) == (3, 300000.0)
    assert package["large_unsourced_deposits"] == [
        {"source_location": "transaction:4", "date": "2033-03-06", "description": DEPOSIT, "amount": 150000.0,
         "revenue_tier_reason": "no_payer_printed", "share_of_true_percent": 50.8, "source_job": "mar",
         "source_document": "mar.pdf", "source_currency": "USD"},
        {"source_location": "transaction:11", "date": "2033-03-20", "description": WIRE, "amount": 120000.0,
         "revenue_tier_reason": "wire_named_sender", "share_of_true_percent": 40.7, "source_job": "mar",
         "source_document": "mar.pdf", "source_currency": "USD"},
        {"source_location": "transaction:7", "date": "2033-04-13", "description": CHECK, "amount": 30000.0,
         "revenue_tier_reason": "check_deposit", "share_of_true_percent": 54.5, "source_job": "apr",
         "source_document": "apr.pdf", "source_currency": "USD"},
    ]
    # Each share is its own statement's: each statement served alone flags the same credits at the same shares.
    for job_id, payload in (("mar", march), ("apr", april)):
        alone = _served(payload)["metrics"]["large_unsourced_deposits"]
        assert alone == [{key: value for key, value in item.items() if not key.startswith("source_") or
                          key == "source_location"} for item in package["large_unsourced_deposits"]
                         if item["source_job"] == job_id]


def test_l7_a_package_of_two_currencies_keeps_the_count_and_refuses_the_money():
    march, april = _months("CAD")
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    assert totals["cross_currency_totals_refused"] is True
    assert (totals["large_unsourced_deposit_count"], totals["large_unsourced_deposit_total"]) == (3, None)
    assert [(item["source_currency"], item["amount"]) for item in package["large_unsourced_deposits"]] == [
        ("USD", 150000.0), ("USD", 120000.0), ("CAD", 30000.0)]


def test_l7_a_deposit_the_own_account_pass_holds_is_flagged_on_its_statement_alone_not_in_the_package():
    from tests.test_package_matching import SENT, _account_a, _account_b

    a, b = _account_a(), _account_b()
    alone = _served(b)["metrics"]
    assert alone["large_unsourced_deposits"] == [
        {"source_location": "transaction:1", "date": "2031-03-03", "description": DEPOSIT, "amount": SENT,
         "revenue_tier_reason": "no_payer_printed", "share_of_true_percent": 86.1}]
    package = _package(("a", a), ("b", b))
    assert package["totals"]["own_account_transfer_held_count"] == 1
    assert not any(key in package["totals"] for key in FLAG_KEYS) and "large_unsourced_deposits" not in package


def test_l7_a_package_without_a_flag_carries_no_key():
    package = _package(("mar", _payload([*_squares(), (6, DEPOSIT, 4000.0)], month=3)))
    assert not any(key in package["totals"] for key in FLAG_KEYS) and "large_unsourced_deposits" not in package


def test_l7_a_document_s_account_names_its_account():
    from tests.test_package_matching import _rows_a, _rows_b, _two_account_document

    package = _package(("doc", _two_account_document(_rows_a(), _rows_b(amount=12000.0))))
    # The two accounts' transfer pairs only where the amounts are equal; this deposit stays counted and is flagged.
    assert [(item["source_job"], item["source_account"], item["amount"]) for item in
            package["large_unsourced_deposits"]] == [("doc", 2, 12000.0)]


# ---------------------------------------------------------------- L8: the downloads and the CLIs

def _statement_downloads(payload):
    from tests.test_webapp_true_revenue import _sheet_rows
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed, _masked

    exported = _masked(_displayed(payload, settings={}, export=True))
    return list(csv.reader(io.StringIO(_analysis_csv(exported)))), _sheet_rows(_analysis_xlsx(exported)), exported


def _section_rows(rows, prefix=""):
    return [row[:3] for row in rows if str(row[0]).startswith(f"{prefix}large_unsourced_deposit_")]


def test_l8_the_statement_downloads_write_the_metric_rows_and_one_section_per_flag():
    csv_rows, xlsx_rows, exported = _statement_downloads(_payload(L1))
    expected = [[f"large_unsourced_deposit_{number}", field, item[field]]
                for number, item in enumerate(L1_FLAGS, start=1) for field in item]
    as_text = [[section, field, str(value)] for section, field, value in expected]
    assert _section_rows(csv_rows) == as_text
    assert _section_rows(xlsx_rows) == [[section, field, float(value) if isinstance(value, float) else value]
                                        for section, field, value in expected]
    flat = {(row[0], row[1]): row[2] for row in csv_rows if len(row) == 3}
    assert (flat[("metrics", "large_unsourced_deposit_count")], flat[("metrics", "large_unsourced_deposit_total")]) == (
        "2", "270000.0")
    assert ("metrics", "large_unsourced_deposits") not in flat
    # After the Zelle rows (the revenue_tier section), before the detection rows.
    sections = [row[0] for row in csv_rows]
    first = sections.index("large_unsourced_deposit_1")
    assert all(section != "detection" for section in sections[:first])
    assert all(not section.startswith("revenue_tier") for section in sections[first:])
    # The JSON download follows the served payload.
    assert exported["metrics"]["large_unsourced_deposits"] == L1_FLAGS


def test_l8_a_document_s_accounts_write_under_their_prefix():
    from tests.test_package_matching import _rows_a, _rows_b, _two_account_document

    csv_rows, _xlsx, _exported = _statement_downloads(_two_account_document(_rows_a(), _rows_b(amount=12000.0)))
    assert [row[:2] for row in csv_rows if "large_unsourced_deposit_" in row[0]][:2] == [
        ["account_2.large_unsourced_deposit_1", "source_location"], ["account_2.large_unsourced_deposit_1", "date"]]
    assert ["account_2.metrics", "large_unsourced_deposit_count", "1"] in csv_rows
    assert not [row for row in csv_rows if row[0].startswith("account_1.") and "large_unsourced" in ",".join(row)]


def test_l8_the_package_downloads_write_one_section_per_flag_after_the_debit_flags():
    from tests.test_webapp_true_revenue import _sheet_rows
    from webapp.app import _masked, _package_csv, _package_for_export, _package_xlsx

    march, _april = _months()
    # April adds a processor's chargeback (R2-OW15's debit flag) after its rows, so the package has a debit_flag_1.
    april = _payload([*APRIL, (24, "HRTLAND PMT SYS CHARGEBACK 123456", -350.0)], month=4)
    exported = _masked(_package_for_export(_package(("mar", march), ("apr", april))))
    assert exported["debit_flags"]
    rows = list(csv.reader(io.StringIO(_package_csv(exported))))
    fields = ("source_location", "date", "description", "amount", "revenue_tier_reason", "share_of_true_percent",
              "source_job", "source_document", "source_account", "source_currency")
    assert [row[1] for row in rows if row[0] == "large_unsourced_deposit_1"] == list(fields)
    assert [row[2] for row in rows if row[0] == "large_unsourced_deposit_3"] == [
        "transaction:7", "2033-04-13", CHECK, "30000.0", "check_deposit", "54.5", "apr", "apr.pdf", "", "USD"]
    sections = [row[0] for row in rows]
    assert max(index for index, section in enumerate(sections) if section.startswith("debit_flag_")) < sections.index(
        "large_unsourced_deposit_1")
    totals = {row[1]: row[2] for row in rows if row[0] == "totals"}
    assert (totals["large_unsourced_deposit_count"], totals["large_unsourced_deposit_total"]) == ("3", "300000.0")
    assert "large_unsourced_deposits" not in totals
    xlsx = [row[:3] for row in _sheet_rows(_package_xlsx(exported)) if row[0] == "large_unsourced_deposit_2"]
    assert xlsx[2] == ["large_unsourced_deposit_2", "description", WIRE]


def test_l8_the_batch_columns_follow_the_non_revenue_count():
    import batch

    start = batch.FIELDS.index("non_revenue_count") + 1
    assert batch.FIELDS[start:start + 2] == ["large_unsourced_deposit_count", "large_unsourced_deposit_total"]
    row = batch._row(Path("fabricated.md"), _report(L1))
    assert (row["large_unsourced_deposit_count"], row["large_unsourced_deposit_total"]) == (2, "270000.00")
    none = batch._row(Path("fabricated.md"), _report([*_squares(), (6, DEPOSIT, 4000.0)]))
    assert (none["large_unsourced_deposit_count"], none["large_unsourced_deposit_total"]) == (0, "0.00")
    unestablished = batch._row(Path("fabricated.md"), _report(L1, dropped=1))
    assert unestablished["revenue_established"] == "NO"
    assert (unestablished["large_unsourced_deposit_count"], unestablished["large_unsourced_deposit_total"]) == ("", "")
    # needs_review does not read them.
    assert row["needs_review"] == none["needs_review"] == ""


def test_l8_the_batch_row_reads_the_zelle_reading_asked_for():
    import batch

    report = _report([*_squares(range(1, 19)), (20, ZELLE, 30000.0)])
    yes = batch._row(Path("fabricated.md"), report, zelle_true_revenue=True)
    no = batch._row(Path("fabricated.md"), report, zelle_true_revenue=False)
    assert (yes["large_unsourced_deposit_count"], yes["large_unsourced_deposit_total"]) == (1, "30000.00")
    assert (no["large_unsourced_deposit_count"], no["large_unsourced_deposit_total"]) == (0, "0.00")


def test_l8_analyze_prints_one_line_after_held_for_review_and_its_json_carries_the_keys():
    import analyze
    from analysis.pipeline import DocumentReport

    report = _report(L1)
    lines = analyze._render(report).splitlines()
    held = next(index for index, line in enumerate(lines) if line.startswith("  Held for review"))
    assert lines[held + 1] == ("  Large deposits to source: 2, $270,000.00 (each $10,000 or more and over 25% of True; "
                               "information only)")
    assert not [line for line in analyze._render(_report([*_squares(), (6, DEPOSIT, 4000.0)])).splitlines()
                if "Large deposits" in line]
    assert not [line for line in analyze._render(_report(L1, dropped=1)).splitlines() if "Large deposits" in line]
    payload = analyze._json_safe(DocumentReport(accounts=[report]))
    assert payload["metrics"]["large_unsourced_deposits"] == L1_FLAGS
    assert json.loads(json.dumps(payload))["metrics"]["large_unsourced_deposit_total"] == 270000.0


# ---------------------------------------------------------------- L9: nothing reads the flag

def _fixtures():
    from tests.test_package_matching import _account_a, _account_b

    march, april = _months()
    cad_march, cad_april = _months("CAD")
    return {
        "statements": [_payload(L1), _payload(L1, dropped=1), _payload([*_squares(), (6, DEPOSIT, 4000.0)]),
                       _payload([*_squares(range(1, 19)), (20, ZELLE, 30000.0)]), march, april, _account_b()],
        "packages": [(("mar", march), ("apr", april)), (("mar", cad_march), ("apr", cad_april)),
                     (("a", _account_a()), ("b", _account_b()))],
    }


@pytest.mark.parametrize("zelle", [True, False])
def test_l9_every_payload_and_package_is_the_one_the_reader_finding_nothing_gives(zelle, monkeypatch):
    fixtures = _fixtures()
    served = [_served(payload, zelle) for payload in fixtures["statements"]]
    packages = [_package(*members, zelle=zelle) for members in fixtures["packages"]]
    assert any("large_unsourced_deposits" in item["metrics"] for item in served)
    assert any("large_unsourced_deposits" in package for package in packages)
    _reader_finds_nothing(monkeypatch)
    assert [_without_flag(item) for item in served] == [_served(payload, zelle) for payload in fixtures["statements"]]
    assert [_without_flag(package) for package in packages] == [
        _package(*members, zelle=zelle) for members in fixtures["packages"]]
    # The package decision and each statement's gate, as the reader finding nothing gives them.
    assert [package["totals"]["decision"] for package in packages] == [
        _package(*members, zelle=zelle)["totals"]["decision"] for members in fixtures["packages"]]
