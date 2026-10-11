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
    # Audit round 4, R4-79: the quiet business days 03-23 to 03-31 (7).
    assert (item["kind"], item["last_before_date"], item["first_after_date"], item["pause_business_days"],
            item["grace_business_days"], item["source_document"]) == (
        "pause", "2054-03-20", "2054-04-01", 7, 5, "april.pdf")


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


def test_r3_26_odkraod_weeks_keep_ondeck_s_weekly_beat_so_no_false_pause():
    """Audit round 3, R3-B01 (R3-26): ODKRAOD is an OnDeck spelling. ONDECK pays weekly on Thursdays in January; in
    February two middle weeks print ODKRAOD. Read as OnDeck payments they keep the beat: no pause (before the alias,
    a confirmed weekly pause from 2054-02-05 to 2054-02-26, longer than the 10-business-day grace)."""
    thursdays = [date(2054, 1, day) for day in (1, 8, 15, 22, 29)]
    january = statement_payload(debits(thursdays, 1000, ONDECK), start=date(2054, 1, 1), end=date(2054, 1, 31))
    february_rows = (debits([date(2054, 2, 5), date(2054, 2, 26)], 1000, ONDECK)
                     + debits([date(2054, 2, 12), date(2054, 2, 19)], 1000, "ODKRAOD 00000"))
    february = statement_payload(february_rows, start=date(2054, 2, 1), end=date(2054, 2, 28),
                                 opening=closing(january))
    built = package(job("january", january), job("february", february))
    assert [item for item in built["lender_payment_changes"] if item["lender"] == "ONDECK"] == []
    assert [item for item in items_of(february) if item["lender"] == "ONDECK"] == []


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
               "continues_in_other_account", "reappears_in_other_account")


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
    # The owner's request of 2026-10-07 (dashboard clarity): an "Also:" sentence, then the statement the note is from.
    assert line(item).endswith(" Also: payments to KAPITUS continue from another account (b-april.pdf) from Apr 15, "
                               "2054 at $1,000.00. From: a-april.pdf.")
    [item] = p6b(ONDECK)["lender_payment_changes"]
    assert (item["kind"], item["stop_confirmed"]) == ("stop", True)
    assert "continues_in_other_account" not in item


# ------------------------------------------------- audit round 3, R3-B06 (R3-83; fabricated statements only)
JULY = (date(2054, 7, 1), date(2054, 7, 31))


def r3_83(b_days, b_amount=1700, b_period=JULY, b_name="b-july"):
    """Account A pays KAPITUS weekly 1,000.00 from 03-04 to 04-08, then a May statement prints none; account B's one
    statement prints KAPITUS at `b_amount` on `b_days`."""
    a_march = statement_payload(debits(every(M(4), M(25)), 1000), month=3)
    a_april = statement_payload(debits(every(A(1), A(8)), 1000), month=4, opening=closing(a_march))
    a_may = statement_payload([], month=5, opening=closing(a_april))
    b_other = statement_payload(debits(b_days, b_amount), start=b_period[0], end=b_period[1], account=ACCOUNT_B)
    return package(job("a-march", a_march), job("a-april", a_april), job("a-may", a_may), job(b_name, b_other))


def test_r3_83_a_funder_seen_months_later_in_another_account_reappears():
    # B's first KAPITUS debit comes 38 business days after A's last payment in the statements provided (36 of A's
    # after 04-08 through 05-29, then 07-01 and 07-02 of B; June no statement covers): beyond the weekly grace of 10,
    # so the stop reads as A's own statements confirm it, and the other account is named apart. The base read "Possible
    # stop ...; payments to KAPITUS continue from another account (b-july.pdf) from 2054-07-02 at $1,700.00".
    [item] = r3_83(every(date(2054, 7, 2), date(2054, 7, 30)))["lender_payment_changes"]
    assert (item["kind"], item["stop_confirmed"], item["source_document"], item["last_presence_date"]) == (
        "stop", True, "a-april.pdf", "2054-04-08")
    assert "continues_in_other_account" not in item
    assert item["reappears_in_other_account"] == {"source_job": "b-july", "source_document": "b-july.pdf",
                                                  "first_date": "2054-07-02", "amount": 1700.0,
                                                  "covered_business_days": 38}
    from tests.test_lender_payment_changes_ui import warning_texts

    [[text, chip]] = warning_texts([item])
    # Audit round 3, R3-MERGE: in the plain voice of the owner's request of 2026-10-07; the stop, its last payment and
    # count, and R3-83's reappearance (the other account's statement, its first day and amount, the business days
    # covered) all stay. Without a package page's rows each statement is named by its file.
    assert text == ("KAPITUS: payments stopped. Last weekly payment: $1,000.00 on Apr 8, 2054. No payments in the 36 "
                    "business days after it, through May 29, 2054. Also: payments to KAPITUS reappear in another account "
                    "(b-july.pdf) from Jul 2, 2054 at $1,700.00, after 38 business days without one in the statements "
                    "provided. From: a-april.pdf.")
    from tests.test_lender_payment_changes_ui import chip_html

    assert chip == chip_html("■", "No payments", "amber")


def test_r3_83_inside_the_grace_window_the_funder_continues_from_another_account():
    # P6b's shape (B's first debit 5 covered business days after A's last) is unchanged: never confirmed, "continue".
    [item] = p6b()["lender_payment_changes"]
    assert (item["stop_confirmed"], item["continues_in_other_account"]["first_date"]) == (False, "2054-04-15")
    assert "reappears_in_other_account" not in item
    # The window is counted in covered business days. B's July statement with a debit on 07-01: A covers 36 after
    # 04-08 and B one more, 37 > 10: a reappearance. A B statement covering 04-09 to 04-30 with a debit on 04-22: 10
    # business days after 04-08 (04-09 to 04-22), the grace exactly: "continue", never confirmed.
    [item] = r3_83([date(2054, 7, 1)] + every(date(2054, 7, 8), date(2054, 7, 29)))["lender_payment_changes"]
    assert (item["stop_confirmed"], item["reappears_in_other_account"]["covered_business_days"]) == (True, 37)
    [item] = r3_83(every(A(22), A(29)), b_amount=1000, b_period=(A(9), A(30)),
                   b_name="b-april")["lender_payment_changes"]
    assert (item["stop_confirmed"], item["continues_in_other_account"]) == (False, {
        "source_job": "b-april", "source_document": "b-april.pdf", "first_date": "2054-04-22", "amount": 1000.0})
    assert "reappears_in_other_account" not in item
    # One more business day (04-23) is beyond the grace: a reappearance, and the stop confirmed by A's May statement.
    [item] = r3_83(every(A(23), A(30)), b_amount=1000, b_period=(A(9), A(30)),
                   b_name="b-april")["lender_payment_changes"]
    assert (item["stop_confirmed"], item["reappears_in_other_account"]["covered_business_days"]) == (True, 11)
    assert "continues_in_other_account" not in item


def test_r3_83_the_package_download_carries_the_reappearance():
    from webapp.app import _lender_payment_change_rows, _package_rows

    built = r3_83(every(date(2054, 7, 2), date(2054, 7, 30)))
    rows = {(section, name): value for section, name, value in _package_rows(built)}
    assert tuple(rows[("lender_payment_change_1", f"reappears_in_other_account.{name}")] for name in (
        "source_document", "first_date", "amount", "covered_business_days")) == ("b-july.pdf", "2054-07-02", 1700.0, 38)
    assert rows[("lender_payment_change_1", "continues_in_other_account.source_document")] == ""
    names = [name for _section, name, _value in _lender_payment_change_rows(built["lender_payment_changes"],
                                                                            package=True)]
    start = names.index("continues_in_other_account.source_document")
    assert names[start:start + 7] == [
        "continues_in_other_account.source_document", "continues_in_other_account.first_date",
        "continues_in_other_account.amount", "reappears_in_other_account.source_document",
        "reappears_in_other_account.first_date", "reappears_in_other_account.amount",
        "reappears_in_other_account.covered_business_days"]
    # A statement's own download carries no package note.
    assert not any(name.startswith("reappears_in_other_account") for _section, name, _value in
                   _lender_payment_change_rows(built["lender_payment_changes"]))


def test_r3_83_covered_business_days():
    periods = [(M(1), Y(29)), (date(2054, 7, 1), date(2054, 7, 31))]
    assert lpc.covered_business_days(A(8), date(2054, 7, 2), periods) == 38
    assert lpc.covered_business_days(A(8), date(2054, 7, 2), periods[:1]) == 36
    # Overlapping periods count a day once; a period with an open bound is skipped; nothing after `second`.
    assert lpc.covered_business_days(A(8), date(2054, 7, 2), periods + [(A(1), A(30)), (None, Y(29))]) == 38
    assert lpc.covered_business_days(A(8), A(8), periods) == 0
    assert lpc.covered_business_days(A(8), A(10), periods) == 2
    # The Canadian calendar on a CAD deal: Victoria Day (05-18) closes.
    assert lpc.covered_business_days(A(8), Y(20), periods[:1]) == 30
    assert lpc.covered_business_days(A(8), Y(20), periods[:1], "CA") == 29
    # ISO strings read as dates (the package passes the item's dates).
    assert lpc.covered_business_days("2054-04-08", "2054-07-02", periods) == 38


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
    # Audit round 3, R3-B06 (R3-83): the reappearance note's cells, empty where the item carries none.
    for name in ("source_document", "first_date", "amount", "covered_business_days"):
        assert package_rows[("lender_payment_change_1", f"reappears_in_other_account.{name}")] == ""
    assert package_rows[("lender_payment_unchecked_1", "source_document")] == "april.pdf"
    assert package_rows[("lender_payment_unchecked_1", "reason")] == "analysed_before_check"
    assert "lender_payment_unchecked_1" in _package_csv(built)
    exported = [field for section, field, _ in _package_rows(built) if section.startswith("lender_payment_")]
    assert "account" not in exported and "account_number" not in exported


def test_r1_the_downloads_carry_each_step_and_what_ended_a_pause():
    """R2-OW18 review round 1: a change's unreported levels with the step into each and the last step, and a pause's
    resuming presence and the date payments resumed, in the download sections (fabricated module items)."""
    from tests import test_lender_payment_changes as pure
    from webapp.app import LENDER_PAYMENT_CHANGE_EXPORT_FIELDS, _lender_payment_change_rows

    steps = pure.only(pure._rows(pure.every(M(2), M(16)), 1000) + pure._rows(pure.every(M(23), A(6)), 950)
                      + pure._rows(pure.every(A(13), A(27)), 650), end=A(30))
    # Audit round 4, R4-79: the attempt on 03-17, 6 quiet business days after 03-06.
    pause = pure.only(pure._rows(pure.bdays(M(2), M(6)) + pure.bdays(M(23), M(31)), 850)
                      + pure._rows([M(17)], 850, returned_funder_payment_by="transaction:99"))
    rows = {(section, name): value for section, name, value in _lender_payment_change_rows([steps, pause])}
    assert rows[("lender_payment_change_1", "via")] == "weekly 950.0 (-5%)"
    assert rows[("lender_payment_change_1", "last_step_percent")] == -32
    assert rows[("lender_payment_change_2", "first_after_kind")] == "attempt"
    assert rows[("lender_payment_change_2", "resumed_date")] == "2054-03-23"
    assert rows[("lender_payment_change_2", "last_step_percent")] == ""
    fields = list(LENDER_PAYMENT_CHANGE_EXPORT_FIELDS)
    assert fields[fields.index("last_after_date") + 1:fields.index("last_after_date") + 3] == [
        "first_after_kind", "resumed_date"]
    assert fields[fields.index("via") + 1] == "last_step_percent"


def test_r3_b05_the_downloads_carry_catch_ups_larger_debits_and_same_amount_debits():
    """Audit round 3, R3-B05 (R3-25, R3-84 and the owner's answer of 2026-10-07): a pause's catch-up and larger debits,
    a stop's catch-up count and earlier large debits, a Caught up item and the same-amount note, as cells, empty where
    an item carries none (fabricated module items)."""
    from tests import test_lender_payment_changes as pure
    from webapp.app import LENDER_PAYMENT_CHANGE_EXPORT_FIELDS, _lender_payment_change_rows

    pause_rows = pure.bdays(M(2), M(6)) + pure.bdays(M(23), M(31))
    # Audit round 4, R4-79: the catch-up's pause from 03-05 (6 quiet business days before the 6x on 03-16).
    catch_up = pure.only(pure._rows(pure.bdays(M(2), M(5)) + pure.bdays(M(23), M(31)), 300) + pure._rows([M(16)], 1800))
    larger = pure.only(pure._rows(pause_rows, 300) + pure._rows([M(16)], 1300))
    stop = pure.only(pure._rows([pure.F(13), M(13), A(13)], 1000) + pure._rows([Y(13)], 2000)
                     + pure._rows([pure.J(12)], 3000), start=pure.F(1), end=date(2054, 8, 31))
    payoff = pure.only(pure._rows([pure.F(2), M(2), A(2)], 2000) + pure._rows([A(10)], 4500)
                       + pure._rows([A(20)], 5000), start=pure.F(1), end=pure.J(30))
    caught = pure.only(pure._rows(pure.bdays(M(2), M(13)) + pure.bdays(M(19), M(31)), 850) + pure._rows([M(18)], 1700))
    noted = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._other(pure.bdays(M(16), M(31)), 850))
    rows = {(section, name): value for section, name, value in _lender_payment_change_rows(
        [catch_up, larger, stop, payoff, caught, noted])}

    def cells(number, *names):
        return tuple(rows[(f"lender_payment_change_{number}", name)] for name in names)

    assert cells(1, "first_after_kind", "first_after_amount", "first_after_multiple", "larger_debits_inside") == (
        "catch_up", 1800.0, 6, "")
    assert cells(2, "first_after_kind", "first_after_amount", "first_after_multiple", "larger_debits_inside") == (
        "payment", "", "", "2054-03-16 1300.0")
    assert cells(3, "other_debits_after.count", "other_debits_after.catch_ups", "payoff.date", "payoff.earlier") == (
        2, 2, "", "")
    assert cells(4, "other_debits_after.catch_ups", "payoff.date", "payoff.earlier") == ("", "2054-04-20", 1)
    assert cells(5, "kind", "cadence", "last_payment_amount", "missed_payments", "missed_first_date",
                 "missed_last_date", "multiple", "catch_up_date", "catch_up_amount") == (
        "catch_up", "daily", 850.0, 2, "2054-03-16", "2054-03-17", 2, "2054-03-18", 1700.0)
    assert cells(6, "same_amount_debits.count", "same_amount_debits.first_date", "same_amount_debits.last_date") == (
        12, "2054-03-16", "2054-03-31")
    assert cells(1, "same_amount_debits.count", "missed_payments", "catch_up_date", "catch_ups_inside") == (
        "", "", "", "")
    # Review round 1 (finding 2): a catch-up after the presence that ended a pause, before payments resumed (audit
    # round 4: the attempt on 03-17, R4-79; the 2x the next business day, nothing missed between them, R4-08).
    attempt = pure._rows([M(17)], 850, returned_funder_payment_by="transaction:99")
    inside = pure.only(pure._rows(pure.bdays(M(2), M(6)) + pure.bdays(M(19), M(31)), 850) + attempt
                       + pure._rows([M(18)], 1700))
    [cell] = [value for _section, name, value in _lender_payment_change_rows([inside]) if name == "catch_ups_inside"]
    assert cell == "2054-03-18 1700.0 2x"
    fields = list(LENDER_PAYMENT_CHANGE_EXPORT_FIELDS)
    assert fields[fields.index("resumed_date") + 1:fields.index("resumed_date") + 5] == [
        "first_after_amount", "first_after_multiple", "larger_debits_inside", "catch_ups_inside"]
    assert fields[-6:] == ["missed_payments", "missed_first_date", "missed_last_date", "multiple", "catch_up_date",
                           "catch_up_amount"]


SAMPLEPAY_REF = "MISC PAYMENT REF-0000AA00BB SAMPLEPAY"
SAMPLEPAY_PREAUTHORIZED = "PREAUTHORIZED DEBIT SAMPLEPAY"


def _states(payload, text):
    return {row["classification"]["classification"] for row in _account(payload)["statement"]["transactions"]
            if row["description"] == text}


def test_r3_84_a_package_pause_names_same_cents_debits_under_another_description():
    """Audit round 3, R3-B05 (R3-84): the funder's daily 850.00 stops for the second half of March while a processor
    descriptor no rule claims takes exactly 850.00 every business day; April resumes. The package's pause, and the
    March statement's possible stop, name them; a descriptor D6 promotes to a potential lender is its own series and
    gives no note (fabricated: SAMPLEPAY)."""
    march = statement_payload(debits(bdays(M(2), M(13)), 850) + debits(bdays(M(16), M(31)), 850, SAMPLEPAY_REF),
                              month=3)
    assert _states(march, SAMPLEPAY_REF) == {"other"}
    april = statement_payload(debits(bdays(A(1), A(30)), 850), month=4, opening=closing(march))
    [item] = package(job("march", march), job("april", april))["lender_payment_changes"]
    assert (item["kind"], item["lender"], item["last_before_date"], item["first_after_date"]) == (
        "pause", "KAPITUS", "2054-03-13", "2054-04-01")
    assert item["same_amount_debits"] == {"count": 12, "first_date": "2054-03-16", "last_date": "2054-03-31"}
    [alone] = items_of(march)
    assert (alone["kind"], alone["stop_confirmed"], alone["same_amount_debits"]["count"]) == ("stop", False, 12)
    control = statement_payload(debits(bdays(M(2), M(13)), 850)
                                + debits(bdays(M(16), M(31)), 850, SAMPLEPAY_PREAUTHORIZED), month=3)
    assert _states(control, SAMPLEPAY_PREAUTHORIZED) == {"potential_lender"}
    april = statement_payload(debits(bdays(A(1), A(30)), 850), month=4, opening=closing(control))
    built = package(job("march", control), job("april", april))
    kapitus = [item for item in built["lender_payment_changes"] if item["lender"] == "KAPITUS"]
    assert [item["kind"] for item in kapitus] == ["pause"]
    assert "same_amount_debits" not in kapitus[0]


def test_r3_b05_r1_a_package_stop_whose_last_presence_is_a_catch_up_in_an_earlier_statement():
    """Audit round 3, R3-B05, review round 1 (finding 1): KAPITUS weekly 1,000.00 on 03-03, 03-10 and 03-17, then
    2,000.00 on 03-27 (the 03-24 payment missed), and an April statement with no KAPITUS debit. The package view and
    its downloads build: the stop confirms on April, names the catch-up, and no Caught up line repeats it."""
    from webapp.app import _package_rows

    march = statement_payload(debits([M(3), M(10), M(17)], 1000) + debits([M(27)], 2000), month=3)
    april = statement_payload([], month=4, opening=closing(march))
    built = package(job("march", march), job("april", april))
    [item] = built["lender_payment_changes"]
    assert (item["kind"], item["lender"], item["stop_confirmed"], item["last_presence_date"],
            item["source_document"]) == ("stop", "KAPITUS", True, "2054-03-27", "march.pdf")
    assert item["other_debits_after"] == {"count": 1, "last_date": "2054-03-27", "catch_ups": 1}
    assert "payoff" not in item
    rows = {(section, name): value for section, name, value in _package_rows(built)}
    assert rows[("lender_payment_change_1", "other_debits_after.catch_ups")] == 1


def test_r4_75_a_package_caught_up_line_names_the_payments_pass_5_re_debited():
    """Audit round 4, R4-B03 (R4-75): KAPITUS weekly 1,000.00 on the Fridays of a statement printed March 1 to 27, the
    20th's returned on the 24th and the 27th's the same day; the next statement, printed March 28 to April 30, takes
    2,000.00 on Monday March 30 (off the Friday cycle: it covers both), then the Fridays again. The package's pass 5
    counts both bounces once, each naming the 30th; its Caught up line names both (before: only the 20th, the 27th
    being one business day before the catch-up, on time), the same payments the returned notes call caught up."""
    bounce = "ACH RETURN ITEM NSF"
    march = statement_payload(debits(every(M(6), M(27)), 1000) + [(M(24), bounce, 1000.0), (M(27), bounce, 1000.0)],
                              start=M(1), end=M(27))
    later = statement_payload(debits([M(30)], 2000) + debits(every(A(3), A(24)), 1000), start=M(28), end=A(30),
                              opening=closing(march))
    built = package(job("march", march), job("later", later))
    returned = {item["debit_date"]: item for item in built["returned_funder_payments"]}
    assert sorted(returned) == ["2054-03-20", "2054-03-27"]
    for item in returned.values():
        assert (item["represented_date"], item["represented_kind"], item["represented_multiple"],
                item["represented_job"]) == ("2054-03-30", "caught_up", 2, "later")
    [item] = [entry for entry in built["lender_payment_changes"] if entry["kind"] == "catch_up"]
    assert (item["scope"], item["missed_payments"], item["missed_first_date"], item["missed_last_date"],
            item["multiple"], item["catch_up_date"], item["source_job"]) == (
        "package", 2, "2054-03-20", "2054-03-27", 2, "2054-03-30", "later")
    assert not any(key.startswith("_") for entry in built["lender_payment_changes"] for key in entry)
    # Each statement alone: no Caught up line (the catch-up and its regime's first payment are in the later one).
    assert [entry["kind"] for entry in items_of(march) + items_of(later)] == []


def test_p13_the_package_json_download_carries_both_keys():
    from webapp.app import _package_for_export

    march, april = p1()
    built = package(job("march", march), job("april", _strip(april)))
    exported = _package_for_export(built)
    assert "lender_payment_changes" in exported and "lender_payment_changes_unchecked" in exported
