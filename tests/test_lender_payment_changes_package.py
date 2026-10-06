"""The owner's request of 2026-10-06 (lender payment changes; true revenue spec §9.2, §10.8; R2-OW18, parts F and H):
each lender payment series read across a package's consecutive statements of ONE account, through
webapp.app._package_analysis(jobs, settings={}), and the downloads.

Fabricated statements only (CONTOSO PLUMBING LLC; FABRIKAM sales; KAPITUS, ONDECK and CanaCap, public funders of the
registry; Sample Bank; accounts ending 1010 and 2020; 2054 dates; neutral whole amounts), analysed by the real
pipeline and published by analysis/serialization.py, as tests/test_webapp_studio_views.py builds them."""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta

import pytest

from analysis import lender_payment_changes as lpc
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction

HOLDER = "CONTOSO PLUMBING LLC"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000001 CCD"
KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD"
ONDECK = "ONDECK CAPITAL DES:PAYMENT ID:000000003 INDN:CONTOSO PLUMBING LLC CO ID:0000000004 CCD"
CANACAP = "CANACAP BUS"
BANK = "Sample Bank"
ACCOUNT_A = "000000001010"
ACCOUNT_B = "000000002020"
PERIODS = {3: (date(2054, 3, 1), date(2054, 3, 31)), 4: (date(2054, 4, 1), date(2054, 4, 30)),
           5: (date(2054, 5, 1), date(2054, 5, 29))}


def M(day):  # noqa: N802
    return date(2054, 3, day)


def A(day):  # noqa: N802
    return date(2054, 4, day)


def Y(day):  # noqa: N802
    return date(2054, 5, day)


def bdays(first, last):
    days, day = [], first
    while day <= last:
        if day.weekday() < 5 and day not in lpc._holidays("US", day.year):
            days.append(day)
        day += timedelta(days=1)
    return days


def every(first, last, step=7):
    days, day = [], first
    while day <= last:
        days.append(day)
        day += timedelta(days=step)
    return days


def debits(days, amount, text=KAPITUS):
    return [(day, text, -float(amount)) for day in days]


def statement_payload(rows, *, month=None, start=None, end=None, account=ACCOUNT_A, bank=BANK, currency="USD",
                      opening=50000.0):
    """The stored payload of one fabricated statement (a sale on its first day, then `rows`), printed balances."""
    from analysis.pipeline import analyze_statement
    from analysis.serialization import document_report_to_dict

    start, end = (start, end) if start else PERIODS[month]
    transactions, balance = [], opening
    for day, text, amount in sorted([(start, SALE, 20000.0), *rows], key=lambda row: row[0]):
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=day.isoformat(), description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(account_name=HOLDER, bank=bank, account_number=account, period_start=start.isoformat(),
                          period_end=end.isoformat(), beginning_balance=opening, ending_balance=balance,
                          currency=currency, currency_source="printed", transactions=transactions)
    report = analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                               model_used="fabricated-test")
    return json.loads(json.dumps(document_report_to_dict(report)))


def closing(payload):
    return _account(payload)["statement"]["ending_balance"]


def _account(payload):
    from analysis.payload_shape import payload_accounts

    [account] = payload_accounts(payload, surface="tests/test_lender_payment_changes_package.py")
    return account


def job(name, payload, status="done"):
    from webapp.jobs import Job

    return Job(id=name, filename=f"{name}.pdf", status=status, analysis=payload, content_sha256=name)


def package(*jobs):
    from webapp.app import _package_analysis

    return _package_analysis(list(jobs), settings={})


def items_of(payload):
    return _account(payload)["detection"]["lender_payment_changes"]


def line(item, currency="USD"):
    from tests.test_lender_payment_changes_ui import warning_text

    return warning_text(item, currency)


# --------------------------------------------------------------------------------- P1, P2: cross-statement changes
def p1():
    march = statement_payload(debits(every(M(4), M(25)), 1000), month=3)
    april = statement_payload(debits(every(A(1), A(22)), 700), month=4, opening=closing(march))
    return march, april


def test_p1_a_decrease_seen_only_across_two_statements():
    march, april = p1()
    assert items_of(march) == [] and items_of(april) == []
    built = package(job("march", march), job("april", april))
    [item] = built["lender_payment_changes"]
    assert (item["kind"], item["scope"], item["change_percent"], item["payments_before"], item["payments_after"]) == (
        "decrease", "package", -30, 4, 4)
    assert (item["cross_statement"], item["from_document"], item["to_document"], item["source_document"]) == (
        True, "march.pdf", "april.pdf", "april.pdf")
    assert (item["from_job"], item["to_job"], item["source_job"], item["source_currency"],
            item["source_period_end"]) == ("march", "april", "april", "USD", "2054-04-30")
    assert "source_account" not in item and "from_account" not in item
    assert not any(key.startswith("_") or key in ("account", "account_number") for key in item)
    assert "lender_payment_changes_unchecked" not in built


def test_p2_held_one_and_one_across_the_boundary():
    march = statement_payload(debits([M(4), M(11), M(18)], 1000) + debits([M(25)], 700), month=3)
    april = statement_payload(debits(every(A(1), A(29)), 700), month=4, opening=closing(march))
    assert items_of(march) == [] and items_of(april) == []
    [item] = package(job("march", march), job("april", april))["lender_payment_changes"]
    assert (item["kind"], item["cross_statement"], item["from_document"], item["to_document"],
            item["source_document"], item["first_after_date"]) == (
        "decrease", True, "march.pdf", "april.pdf", "march.pdf", "2054-03-25")


# ---------------------------------------------------------------------------------------- P3, P4, P4b: pauses, stops
def test_p3_a_statement_s_possible_stop_that_resumes_is_a_package_pause():
    march = statement_payload(debits(bdays(M(2), M(20)), 850), month=3)
    april = statement_payload(debits(bdays(A(1), A(30)), 850), month=4, opening=closing(march))
    [stop] = items_of(march)
    assert (stop["kind"], stop["quiet_business_days"], stop["stop_confirmed"]) == ("stop", 7, False)
    [item] = package(job("march", march), job("april", april))["lender_payment_changes"]
    assert (item["kind"], item["last_before_date"], item["first_after_date"], item["pause_business_days"],
            item["grace_business_days"], item["source_document"]) == (
        "pause", "2054-03-20", "2054-04-01", 8, 5, "april.pdf")


def p4(*, ondeck_may=False):
    march = statement_payload(debits(every(M(4), M(25)), 1000), month=3)
    april = statement_payload(debits(every(A(1), A(29)), 1000), month=4, opening=closing(march))
    may = statement_payload([], month=5, opening=closing(april))
    return march, april, may


def test_p4_a_stop_confirmed_by_a_later_statement():
    march, april, may = p4()
    assert items_of(may) == []
    [item] = package(job("march", march), job("april", april), job("may", may))["lender_payment_changes"]
    assert (item["kind"], item["stop_confirmed"], item["quiet_business_days"], item["coverage_end"],
            item["source_document"], item["last_presence_date"]) == (
        "stop", True, 21, "2054-05-29", "april.pdf", "2054-04-29")


def test_p4b_a_short_interim_printout_never_confirms_a_stop():
    march = statement_payload(debits([M(4), M(11), M(18)], 1000), month=3)
    interim = statement_payload([], start=A(1), end=A(3), opening=closing(march))
    [item] = package(job("march", march), job("interim", interim))["lender_payment_changes"]
    assert (item["kind"], item["quiet_business_days"], item["stop_confirmed"], item["coverage_end"]) == (
        "stop", 12, False, "2054-04-03")
    april = statement_payload([], month=4, opening=closing(march))
    [item] = package(job("march", march), job("april", april))["lender_payment_changes"]
    assert (item["kind"], item["stop_confirmed"]) == ("stop", True)


# ------------------------------------------------------------------------------------------- P5, P6, P6b: chains
def test_p5_a_coverage_gap_breaks_the_chain():
    march = statement_payload(debits(bdays(M(2), M(13)), 850) + debits(bdays(M(16), M(25)), 600), month=3)
    may = statement_payload(debits(every(Y(6), Y(27)), 700), month=5, opening=closing(march))
    built = package(job("march", march), job("may", may))
    assert [(item["kind"], item["source_document"]) for item in built["lender_payment_changes"]] == [
        ("decrease", "march.pdf")]
    [item] = built["lender_payment_changes"]
    published = {key: value for key, value in item.items() if key not in SOURCE_KEYS}
    assert published == {**items_of(march)[0], "scope": "package"}


SOURCE_KEYS = ("source_job", "source_document", "source_account", "source_currency", "source_period_end",
               "from_job", "from_document", "from_account", "to_job", "to_document", "to_account", "cross_statement",
               "continues_in_other_account")


def test_p6_two_accounts_are_never_chained():
    a_march = statement_payload(debits(every(M(4), M(25)), 1000), month=3)
    a_april = statement_payload(debits(every(A(1), A(29)), 1000), month=4, opening=closing(a_march))
    b_march = statement_payload(debits(every(M(4), M(25)), 700), month=3, account=ACCOUNT_B)
    b_april = statement_payload(debits(every(A(1), A(29)), 700), month=4, account=ACCOUNT_B,
                                opening=closing(b_march))
    built = package(job("a-march", a_march), job("a-april", a_april), job("b-march", b_march),
                    job("b-april", b_april))
    assert built["lender_payment_changes"] == []


def p6b(other=KAPITUS):
    a_march = statement_payload(debits(every(M(4), M(25)), 1000), month=3)
    a_april = statement_payload(debits(every(A(1), A(8)), 1000), month=4, opening=closing(a_march))
    a_may = statement_payload([], month=5, opening=closing(a_april))
    b_april = statement_payload(debits(every(A(15), A(29)), 1000, other), month=4, account=ACCOUNT_B)
    b_may = statement_payload(debits(every(Y(6), Y(27)), 1000, other), month=5, account=ACCOUNT_B,
                              opening=closing(b_april))
    return package(job("a-march", a_march), job("a-april", a_april), job("a-may", a_may), job("b-april", b_april),
                   job("b-may", b_may))


def test_p6b_a_funder_that_moves_to_another_account_is_never_a_confirmed_stop():
    [item] = p6b()["lender_payment_changes"]
    assert (item["kind"], item["stop_confirmed"], item["source_document"]) == ("stop", False, "a-april.pdf")
    assert item["continues_in_other_account"] == {"source_job": "b-april", "source_document": "b-april.pdf",
                                                  "first_date": "2054-04-15", "amount": 1000.0}
    assert line(item).endswith("; payments to KAPITUS continue from another account (b-april.pdf) from 2054-04-15 at "
                               "$1,000.00 (a-april.pdf).")
    [item] = p6b(ONDECK)["lender_payment_changes"]
    assert (item["kind"], item["stop_confirmed"]) == ("stop", True)
    assert "continues_in_other_account" not in item


# ----------------------------------------------------------------------------------------------- P7: an overlap
def test_p7_a_debit_both_statements_print_is_counted_once():
    march = statement_payload(debits(every(M(2), M(30)), 1000), month=3)
    april = statement_payload(debits([M(30)], 1000) + debits(every(A(6), A(27)), 700), start=M(29), end=A(30),
                              opening=closing(march))
    built = package(job("march", march), job("april", april))
    [item] = built["lender_payment_changes"]
    assert (item["kind"], item["payments_before"], item["payments_after"], item["from_document"],
            item["source_document"]) == ("decrease", 5, 4, "march.pdf", "april.pdf")


# ------------------------------------------------------------------------------------------- P8, P9: not checked
def _strip(payload):
    stripped = copy.deepcopy(payload)
    _account(stripped)["detection"].pop("lender_payment_changes")
    return stripped


def test_p8_a_member_analysed_before_the_check_is_listed_and_breaks_the_chain():
    march, april = p1()
    built = package(job("march", march), job("april", _strip(april)), job("queued", None, status="queued"))
    assert built["lender_payment_changes"] == []
    assert built["lender_payment_changes_unchecked"] == [
        {"source_job": "april", "source_document": "april.pdf", "reason": "analysed_before_check"},
        {"source_job": "queued", "source_document": "queued.pdf", "reason": "not_ready"}]
    alone = package(job("march", _strip(march)), job("april", _strip(april)))
    assert "lender_payment_changes" not in alone
    assert [entry["reason"] for entry in alone["lender_payment_changes_unchecked"]] == ["analysed_before_check"] * 2


def test_p9_fewer_than_four_digits_chain_only_on_the_balance():
    march = statement_payload(debits(every(M(4), M(25)), 1000), month=3, account="XXXXXXXX")
    april = statement_payload(debits(every(A(1), A(22)), 700), month=4, account="XXXXXXXX", opening=closing(march))
    built = package(job("march", march), job("april", april))
    assert [item["kind"] for item in built["lender_payment_changes"]] == ["decrease"]
    assert "lender_payment_changes_unchecked" not in built
    broken = statement_payload(debits(every(A(1), A(22)), 700), month=4, account="XXXXXXXX", opening=1.0)
    built = package(job("march", march), job("april", broken))
    assert built["lender_payment_changes"] == []
    assert built["lender_payment_changes_unchecked"] == [
        {"source_job": "march", "source_document": "march.pdf", "reason": "no_account_number"},
        {"source_job": "april", "source_document": "april.pdf", "reason": "no_account_number"}]
    other = statement_payload(debits(every(A(1), A(22)), 700), month=4, account=ACCOUNT_B)
    built = package(job("march", statement_payload(debits(every(M(4), M(25)), 1000), month=3)), job("april", other))
    assert built["lender_payment_changes"] == [] and "lender_payment_changes_unchecked" not in built


# ---------------------------------------------------------------------------------- P10, P11, P12: the package
def test_p10_the_listing_order_changes_nothing():
    march, april = p1()
    forward = package(job("march", march), job("april", april))
    backward = package(job("april", april), job("march", march))
    assert forward["lender_payment_changes"] == backward["lender_payment_changes"]


def test_p11_a_mixed_currency_package_publishes_each_item_in_its_unit():
    usd_march, usd_april = p1()
    cad_march = statement_payload(debits(every(M(4), M(25)), 1000, CANACAP), month=3, account=ACCOUNT_B,
                                  bank="TD Canada Trust", currency="CAD")
    cad_april = statement_payload(debits(every(A(1), A(22)), 700, CANACAP), month=4, account=ACCOUNT_B,
                                  bank="TD Canada Trust", currency="CAD", opening=closing(cad_march))
    built = package(job("march", usd_march), job("april", usd_april), job("cad-march", cad_march),
                    job("cad-april", cad_april))
    assert built["totals"]["cross_currency_totals_refused"] is True
    assert sorted((item["lender"], item["source_currency"], item["amount_after"])
                  for item in built["lender_payment_changes"]) == [("CanaCap", "CAD", 700.0), ("KAPITUS", "USD", 700.0)]


def test_p12_information_only(monkeypatch):
    march, april = p1()
    on = package(job("march", march), job("april", april))
    monkeypatch.setattr(lpc, "payment_changes", lambda *args, **kwargs: [])
    monkeypatch.setattr(lpc, "statement_payment_changes", lambda *args, **kwargs: [])
    off_march, off_april = p1()
    off = package(job("march", off_march), job("april", off_april))
    assert off["lender_payment_changes"] == [] and len(on["lender_payment_changes"]) == 1
    keys = ("lender_payment_changes", "lender_payment_changes_unchecked")
    assert {key: value for key, value in on.items() if key not in keys} == {
        key: value for key, value in off.items() if key not in keys}
    for name in ("totals", "funders", "potential_lenders", "returned_funder_payments", "documents", "monthly"):
        assert on[name] == off[name]


def test_p14_a_one_member_chain_equals_its_statement_but_for_its_scope_and_source():
    march = statement_payload(debits(bdays(M(2), M(13)), 850) + debits(bdays(M(16), M(25)), 600), month=3)
    [item] = package(job("march", march))["lender_payment_changes"]
    assert {key: value for key, value in item.items() if key not in SOURCE_KEYS} == {
        **items_of(march)[0], "scope": "package"}
    assert (item["source_document"], item["cross_statement"]) == ("march.pdf", False)


# ------------------------------------------------------------------------------------------------- P13: exports
def test_p13_the_statement_and_package_downloads():
    from webapp.app import _analysis_csv, _analysis_rows, _package_csv, _package_rows

    march, april = p1()
    two_months = statement_payload(debits(bdays(M(2), M(13)), 850) + debits(bdays(M(16), M(25)), 600), month=3)
    rows = _analysis_rows(two_months)
    sections = {(section, field): value for section, field, value in rows}
    assert sections[("lender_payment_change_1", "kind")] == "decrease"
    assert sections[("lender_payment_change_1", "change_percent")] == -29
    assert sections[("lender_payment_change_1", "after_funding.date")] == ""
    assert not any(section == "detection" and field == "lender_payment_changes" for section, field, _ in rows)
    assert "lender_payment_change_1" in _analysis_csv(two_months)
    built = package(job("march", march), job("april", _strip(april)))
    built["lender_payment_changes"] = package(job("march", march), job("april", april))["lender_payment_changes"]
    package_rows = {(section, field): value for section, field, value in _package_rows(built)}
    assert package_rows[("lender_payment_change_1", "source_currency")] == "USD"
    assert package_rows[("lender_payment_change_1", "cross_statement")] is True
    assert package_rows[("lender_payment_change_1", "from_document")] == "march.pdf"
    assert package_rows[("lender_payment_change_1", "continues_in_other_account.source_document")] == ""
    assert package_rows[("lender_payment_unchecked_1", "source_document")] == "april.pdf"
    assert package_rows[("lender_payment_unchecked_1", "reason")] == "analysed_before_check"
    assert "lender_payment_unchecked_1" in _package_csv(built)
    exported = [field for section, field, _ in _package_rows(built) if section.startswith("lender_payment_")]
    assert "account" not in exported and "account_number" not in exported


def test_p13_the_package_json_download_carries_both_keys():
    from webapp.app import _package_for_export

    march, april = p1()
    built = package(job("march", march), job("april", _strip(april)))
    exported = _package_for_export(built)
    assert "lender_payment_changes" in exported and "lender_payment_changes_unchecked" in exported
