"""The owner's request of 2026-10-07 (dashboard clarity; display only; true revenue spec §10.1, §10.2, §20): "make this
writing more clear ... these notes on the lenders", "make the big number ... show True revenue instead of total
credits. Total credits can be shown below it like the others" and "take off verified ($) from the monthly statement
chart and add witholding rate instead".

A: every lender note is a short headline, plain sentences under it, an "Also:" sentence per extra note and the
statement it comes from (never a job id or a "<uuid>_<file>" name). B: the hero's big figure is True revenue, Total
credits on the line below. C: the Monthly Statements table drops Verified ($) and shows each statement's confirmed
withholding rate. D, the owner's follow-up the same day: "can we get these zelle labels ... out of the monthly
statement chart" and "for the Monthly deposits there are like 4 different colors while the color key contains only two
color identifiers": no Monthly Statements row carries a Zelle line (the True card's Zelle fact stays), and every chart
bar takes only colours its key shows (no tallest-bar highlight; the Total view's key gains its swatch). Driven in node
through the whole webapp/static/app.js (tests/webapp_js_harness.py).

Fabricated data only: CONTOSO, FABRIKAM, NORTHWIND and SAMPLE names, public funder names (KAPITUS, ONDECK), 2054
dates, round amounts and made-up job ids."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Made-up job ids, in the shape the webapp gives a job (a UUID), and files whose names carry one as a prefix.
JOB_MAR = "11111111-2222-4333-8444-555555555501"
JOB_APR = "11111111-2222-4333-8444-555555555502"
JOB_MAY = "11111111-2222-4333-8444-555555555503"
JOB_B_APR = "11111111-2222-4333-8444-555555555504"
JOB_UNDATED = "11111111-2222-4333-8444-555555555505"
JOBS = (JOB_MAR, JOB_APR, JOB_MAY, JOB_B_APR, JOB_UNDATED)


def _doc(job, month, name, *, start=None, end=None):
    return {"id": job, "filename": f"{job}_{name}", "status": "done",
            "period_start": start or (f"2054-{month:02d}-01" if month else None),
            "period_end": end or (f"2054-{month:02d}-28" if month else None)}


#: A package of SAMPLE BANK statements: March, April and May of account A, April of account B (two April statements,
#: so each April label names its file), and one statement that printed no period.
DOCUMENTS = [_doc(JOB_MAR, 3, "SAMPLE BANK march.pdf"), _doc(JOB_APR, 4, "SAMPLE BANK april.pdf"),
             _doc(JOB_MAY, 5, "SAMPLE BANK may.pdf"), _doc(JOB_B_APR, 4, "SAMPLE b-april.pdf"),
             _doc(JOB_UNDATED, None, "SAMPLE undated.pdf")]
#: The same package without account B's April statement: one April statement, so its label is its month alone.
THREE = DOCUMENTS[:3]


def _source(job, name, prefix="source"):
    return {f"{prefix}_job": job, f"{prefix}_document": f"{job}_{name}"}


def _item(kind, **fields):
    base = {"kind": kind, "lender": "KAPITUS", "lender_label": "KAPITUS", "lender_state": "confirmed", "position": 1,
            "positions": 1, "scope": "statement"}
    return {**base, **fields}


def _change(kind, before, after, percent, **fields):
    return _item(kind, cadence_before=fields.pop("cadence_before", "daily"),
                 cadence_after=fields.pop("cadence_after", "daily"), amount_before=before, amount_after=after,
                 change_percent=percent, cadence_changed=fields.pop("cadence_changed", False),
                 schedule_confirmed=fields.pop("schedule_confirmed", True), **fields)


DECREASE = _change("decrease", 850.0, 600.0, -29, payments_before=10, payments_after=8,
                   first_after_date="2054-03-16")
INCREASE_AFTER_FUNDING = _change(
    "increase", 1000.0, 1500.0, 50, cadence_before="weekly", cadence_after="weekly", payments_before=3,
    payments_after=2, first_after_date="2054-04-06", lender="ONDECK", lender_label="ONDECK",
    after_funding={"date": "2054-04-01", "amount": 25000.0}, scope="package", source_currency="USD",
    cross_statement=True, **_source(JOB_APR, "SAMPLE BANK april.pdf"),
    **_source(JOB_MAR, "SAMPLE BANK march.pdf", "from"), **_source(JOB_APR, "SAMPLE BANK april.pdf", "to"))
POSSIBLE_INCREASE_POTENTIAL = _change(
    "increase", 300.0, 1800.0, 20, cadence_after="weekly", cadence_changed=True, schedule_confirmed=False,
    weekly_equivalent_before=1500.0, weekly_equivalent_after=1800.0, payments_before=15, payments_after=2,
    first_after_date="2054-03-23", lender="Unidentified lender obligation",
    lender_label="Unidentified lender obligation (daily, 300.00)", lender_state="potential")
STEPS = _change("decrease", 1000.0, 880.0, -12, cadence_before="weekly", cadence_after="weekly", payments_before=4,
                payments_after=4, first_after_date="2054-04-27",
                via=[{"amount": 950.0, "cadence": "weekly", "change_percent": -5}], last_step_percent=-7)
SCHEDULE = _change("cadence_change", 500.0, 2500.0, 0, cadence_after="weekly", cadence_changed=True,
                   weekly_equivalent_before=2500.0, weekly_equivalent_after=2500.0, payments_before=15,
                   payments_after=4, first_after_date="2054-03-23")
SCHEDULE_LOWER = {**SCHEDULE, "amount_after": 2300.0, "weekly_equivalent_after": 2300.0, "change_percent": -8}
PAUSE = _item("pause", cadence="daily", last_before_date="2054-03-20", first_after_date="2054-04-01",
              pause_business_days=8, grace_business_days=5, last_payment_amount=850.0, first_after_kind="payment")
PAUSE_ATTEMPT = {**PAUSE, "first_after_kind": "attempt", "resumed_date": "2054-04-03"}
PAUSE_OTHER = {**PAUSE, "first_after_kind": "other_amount", "resumed_date": "2054-04-03"}
PAUSE_ACROSS_YEARS = {**PAUSE, "last_before_date": "2053-12-30", "first_after_date": "2054-01-08"}
NEW_STREAM = _item("new_stream", position=2, positions=2, cadence_after="weekly", amount_after=2100.0,
                   first_after_date="2054-03-18", alongside=[{"position": 1, "cadence": "weekly", "amount": 1000.0}],
                   weekly_total_before=1000.0, weekly_total_after=3100.0, change_percent=210)
POSSIBLE_STOP = _item("stop", cadence="weekly", last_payment_date="2054-05-13", last_payment_amount=1000.0,
                      payments=6, last_presence_date="2054-05-13", quiet_business_days=11, grace_business_days=10,
                      coverage_end="2054-05-29", stop_confirmed=False)
STOP_NEW_LENDER = _item(
    "stop", cadence="weekly", last_payment_date="2054-04-22", last_payment_amount=1000.0, payments=8,
    last_presence_date="2054-04-22", quiet_business_days=26, grace_business_days=10, coverage_end="2054-05-29",
    stop_confirmed=True, scope="package", source_currency="USD", **_source(JOB_APR, "SAMPLE BANK april.pdf"),
    new_lender_after={"lender_label": "ONDECK", "lender_state": "confirmed", "cadence": "weekly", "amount": 1100.0,
                      "first_date": "2054-04-24"})
STOP_OTHER_DEBITS = _item("stop", cadence="daily", last_payment_date="2054-03-13", last_payment_amount=850.0,
                          payments=10, last_presence_date="2054-03-19", quiet_business_days=8,
                          grace_business_days=5, coverage_end="2054-03-31", stop_confirmed=False,
                          other_debits_after={"count": 3, "last_date": "2054-03-19"})
STOP_EVERY_NOTE = _item(
    "stop", cadence="weekly", position=1, positions=2, last_payment_date="2054-04-01", last_payment_amount=1000.0,
    payments=5, last_presence_date="2054-04-08", quiet_business_days=12, grace_business_days=10,
    coverage_end="2054-05-29", stop_confirmed=False, scope="package", source_currency="USD",
    **_source(JOB_APR, "SAMPLE BANK april.pdf"),
    payoff={"date": "2054-04-20", "amount": 5000.0},
    continues_as={"lender_label": "Unidentified lender obligation (weekly, 990.00)", "lender_state": "potential",
                  "amount": 990.0, "first_date": "2054-04-15"},
    debt_relief_after={"date": "2054-04-18"},
    continues_in_other_account={**_source(JOB_B_APR, "SAMPLE b-april.pdf"), "first_date": "2054-04-15",
                                "amount": 1000.0},
    other_stream_continues={"amount": 1200.0, "cadence": "weekly"},
    last_attempt_returned={"date": "2054-04-08"})
RETURNED = {"funder": "KAPITUS", "amount": 850.0, "debit_date": "2054-03-03", "credit_date": "2054-03-05",
            "credit_description": "RETURN OF POSTED CHECK ITEM"}
RETURNED_ACROSS = {**RETURNED, "debit_date": "2054-03-27", "credit_date": "2054-04-02", "cross_statement": True,
                   "source_currency": "USD", **_source(JOB_MAR, "SAMPLE BANK march.pdf"),
                   **_source(JOB_APR, "SAMPLE BANK april.pdf", "credit")}
RETURNED_IN_ONE = {**RETURNED, "source_currency": "USD", **_source(JOB_MAY, "SAMPLE BANK may.pdf")}


def _note(headline, details, also=(), source=""):
    return {"headline": headline, "details": list(details), "also": list(also), "source": source}


def _notes(items, documents=DOCUMENTS, returned=False):
    function = "returnedFunderPaymentNote" if returned else "lenderPaymentChangeNote"
    return run_dashboard(f"""
const sources = paymentChangeSources({json.dumps(documents)});
console.log(JSON.stringify({json.dumps(items)}.map((item) => {function}(item, 'USD', sources))));
""")


# ----------------------------------------------------------------------------------------------- A: the notes
@needs_node
def test_a_change_reads_as_a_headline_and_plain_sentences():
    notes = _notes([DECREASE, INCREASE_AFTER_FUNDING, POSSIBLE_INCREASE_POTENTIAL, STEPS, SCHEDULE, SCHEDULE_LOWER])
    # Review round 1: the counts say nothing about the level still running ("so far" read wrong where a later change
    # replaced it).
    assert notes[0] == _note("KAPITUS: payment went down 29%", [
        "The daily payment went from $850.00 to $600.00 starting Mar 16, 2054 (8 payments at the new amount, after 10 "
        "at the old)."])
    # Review round 1: April 2054 is printed by two members (accounts A and B), so the cross-statement line names the
    # April statement by its file as well.
    assert notes[1] == _note("ONDECK: payment went up 50%", [
        "The weekly payment went from $1,000.00 to $1,500.00 starting Apr 6, 2054 (2 payments at the new amount, after "
        "3 at the old)."],
        ["Also: ONDECK deposited $25,000.00 on Apr 1, 2054, just before; this may be a renewal."],
        "From: March 2054 statement → April 2054 statement, SAMPLE BANK april.pdf")
    # Review round 1: where the schedule changes, the headline's percentage is the weekly total's, so the headline says
    # so and the weekly-total sentence comes first. Review round 3: a potential lender's headline names it first.
    assert notes[2] == _note(
        "Potential lender Unidentified lender obligation (daily, 300.00): weekly payment total may have gone up 20%", [
            "The weekly total went from $1,500.00 to $1,800.00.",
            "Payments changed from daily $300.00 to weekly $1,800.00 starting Mar 23, 2054 (2 payments at the new "
            "amount, after 15 at the old).",
            "The new schedule isn't confirmed yet."])
    assert notes[3] == _note("KAPITUS: payment went down 12%", [
        "The weekly payment went from $1,000.00 to $880.00 starting Apr 27, 2054 (4 payments at the new amount, after "
        "4 at the old).",
        "It stepped through $950.00 (-5%) on the way, then to $880.00 (-7%)."])
    assert notes[4] == _note("KAPITUS: payment schedule changed", [
        "Payments changed from daily $500.00 to weekly $2,500.00 starting Mar 23, 2054 (4 payments on the new "
        "schedule, after 15 on the old).",
        "The weekly total stayed about the same ($2,500.00 before, $2,500.00 after)."])
    assert notes[5]["details"][1] == "The weekly total stayed about the same ($2,500.00 before, $2,300.00 after, -8%)."


@needs_node
def test_a_change_s_extra_notes_are_each_an_also_sentence():
    restart = {**STEPS, "via": [], "restart": True, "pause_business_days": 20}
    back = {**DECREASE, "kind": "increase", "amount_before": 600.0, "amount_after": 850.0, "change_percent": 42,
            "back_to_earlier": True}
    temporary = {**DECREASE, "reverted": True, "reverted_date": "2054-03-26"}
    after = {**INCREASE_AFTER_FUNDING, "after_funding": {"date": "2054-04-08", "amount": 25000.0}}
    notes = _notes([restart, back, temporary, after])
    assert notes[0]["also"] == ["Also: the new amount started after a pause of 20 business days with no payment."]
    assert notes[1]["also"] == ["Also: this is back to the earlier $850.00 payment."]
    assert notes[2]["also"] == ["Also: this was temporary; the payment went back to $850.00 on Mar 26, 2054."]
    assert notes[3]["also"] == ["Also: ONDECK deposited $25,000.00 on Apr 8, 2054, just after; this may be a renewal."]


@needs_node
def test_a_pause_and_a_new_stream():
    notes = _notes([PAUSE, PAUSE_ATTEMPT, PAUSE_OTHER, PAUSE_ACROSS_YEARS, NEW_STREAM])
    # Review round 1: the grace window reads as the threshold it is, never as the payments' normal rhythm; an attempt
    # reads "returned unpaid" (a bank's bounce and a business's reversal alike, R2-OW13).
    assert notes[0] == _note("KAPITUS: payments paused, then resumed", [
        "No payment between Mar 20 and Apr 1, 2054 (8 business days, more than the 5 a daily schedule allows).",
        "Payments then resumed at the same daily $850.00."])
    assert notes[1]["details"] == [
        "No payment or payment attempt between Mar 20 and Apr 1, 2054 (8 business days, more than the 5 a daily "
        "schedule allows).",
        "The attempt on Apr 1, 2054 was returned unpaid, and payments resumed at the same daily $850.00 on Apr 3, "
        "2054."]
    assert notes[2]["details"][1] == ("A payment of another amount came on Apr 1, 2054, and payments resumed at the "
                                      "same daily $850.00 on Apr 3, 2054.")
    assert notes[3]["details"][0].startswith("No payment between Dec 30, 2053 and Jan 8, 2054 (")
    assert notes[4] == _note("KAPITUS: a second payment started", [
        "A second weekly payment of $2,100.00 started on Mar 18, 2054, alongside the existing weekly $1,000.00.",
        "The weekly total went from $1,000.00 to $3,100.00 (+210%)."])


@needs_node
def test_a_stop_says_when_the_last_payment_was_and_how_long_it_has_been():
    notes = _notes([POSSIBLE_STOP, STOP_NEW_LENDER, STOP_OTHER_DEBITS, STOP_EVERY_NOTE])
    assert notes[0] == _note("KAPITUS: payments may have stopped", [
        "No payment in the last 11 business days of this statement.",
        "A weekly schedule allows up to 10 business days without a payment.",
        "Last payment: $1,000.00 on May 13, 2054."])
    assert notes[1] == _note("KAPITUS: payments stopped", [
        "Last weekly payment: $1,000.00 on Apr 22, 2054.",
        "No payments in the 26 business days after it, through May 29, 2054."],
        ["Also: ONDECK started weekly payments of $1,100.00 on Apr 24, 2054; it may have taken over this advance."],
        "From: April 2054 statement, SAMPLE BANK april.pdf")
    # Review round 3: a possible stop after debits at other amounts names the quiet business days after the last of
    # them, as every other stop does, and the last regular payment once.
    assert notes[2]["details"] == [
        "Last regular daily payment: $850.00 on Mar 13, 2054.",
        "After it came only 3 debits at other amounts, the last on Mar 19, 2054.",
        "No payment in the 8 business days after Mar 19, 2054, to the end of this statement.",
        "A daily schedule allows up to 5 business days without a payment."]
    # Review round 1: two concurrent streams, not two payments in all, and no amount-bearing label repeated.
    assert notes[3] == _note("KAPITUS: payments may have stopped", [
        "No payment or payment attempt in the last 12 business days, through May 29, 2054.",
        "A weekly schedule allows up to 10 business days without a payment.",
        "Last payment: $1,000.00 on Apr 1, 2054.",
        "This lender has 2 separate payment streams; this note is about the first."], [
        "Also: a final debit of $5,000.00 on Apr 20, 2054 may be a payoff.",
        "Also: payments of $990.00 continue under potential lender Unidentified lender obligation (weekly, 990.00) "
        "from Apr 15, 2054; this may be a buyout or refinance.",
        "Also: a debt-relief program's payments start on Apr 18, 2054; this may mean a default or settlement.",
        "Also: payments to KAPITUS continue from another account (April 2054 statement, SAMPLE b-april.pdf) from "
        "Apr 15, 2054 at $1,000.00.",
        "Also: another KAPITUS payment of $1,200.00 weekly continues.",
        "Also: the last attempt, on Apr 8, 2054, was returned unpaid."],
        "From: April 2054 statement, SAMPLE BANK april.pdf")


@needs_node
def test_a_confirmed_stop_after_a_bounced_attempt_counts_from_the_attempt():
    stop = {**STOP_NEW_LENDER, "new_lender_after": None, "last_presence_date": "2054-04-29",
            "last_attempt_returned": {"date": "2054-04-29"}}
    [note] = _notes([stop], THREE)
    assert note["details"] == ["Last weekly payment: $1,000.00 on Apr 22, 2054.",
                               "No payment or payment attempt in the 26 business days after Apr 29, 2054, through May "
                               "29, 2054."]
    assert note["also"] == ["Also: the last attempt, on Apr 29, 2054, was returned unpaid."]
    # One April statement in the package: its month alone names it.
    assert note["source"] == "From: April 2054 statement"


@needs_node
def test_a_returned_payment_says_it_was_returned_in_plain_words():
    notes = _notes([RETURNED, RETURNED_ACROSS, RETURNED_IN_ONE], THREE, returned=True)
    # Review round 1: "was returned", true of a bank's bounce and of a business's reversal alike; the bank's own words
    # tell them apart (R2-OW13).
    assert notes[0] == _note("KAPITUS: a payment was returned", [
        'The $850.00 payment on Mar 3, 2054 was returned unpaid on Mar 5, 2054 (the bank printed: "RETURN OF POSTED '
        'CHECK ITEM").',
        "It isn't counted as paid, but it still counts in the withholding rate."])
    assert notes[1]["source"] == "From: March 2054 → April 2054 statements"
    assert notes[1]["details"][0].startswith("The $850.00 payment on Mar 27, 2054 was returned unpaid on Apr 2, 2054")
    assert notes[2]["source"] == "From: May 2054 statement"


@needs_node
def test_the_source_line_never_prints_a_job_id():
    undated = {**DECREASE, "scope": "package", **_source(JOB_UNDATED, "SAMPLE undated.pdf")}
    unknown = {**DECREASE, "scope": "package", "source_job": "job-that-left",
               "source_document": f"{JOB_MAY}_SAMPLE gone.pdf"}
    bare = {**DECREASE, "scope": "package", "source_job": "another-job-that-left", "source_document": JOB_MAY}
    one_statement = [_doc(JOB_MAR, 3, "SAMPLE BANK march.pdf")]
    result = run_dashboard(f"""
const many = paymentChangeSources({json.dumps(DOCUMENTS)});
const one = paymentChangeSources({json.dumps(one_statement)});
const items = {json.dumps([undated, unknown, bare])};
console.log(JSON.stringify({{many: items.map((item) => lenderPaymentChangeNote(item, 'USD', many).source),
  none: items.map((item) => lenderPaymentChangeNote(item, 'USD', null).source),
  across: lenderPaymentChangeNote({json.dumps(INCREASE_AFTER_FUNDING)}, 'USD', null).source,
  one: lenderPaymentChangeNote({json.dumps({**DECREASE, "scope": "package", **_source(JOB_MAR, "x.pdf")})},
                               'USD', one).source,
  statement: lenderPaymentChangeNote({json.dumps(DECREASE)}, 'USD', many).source}}));
""")
    # No period: the file, its job-id prefix removed; a member the page does not list: its file the same way; a file
    # that is only an id: no name at all.
    assert result["many"] == ["From: SAMPLE undated.pdf", "From: SAMPLE gone.pdf", "From: a statement"]
    assert result["none"] == result["many"]
    assert result["across"] == "From: SAMPLE BANK march.pdf → SAMPLE BANK april.pdf"
    # A package of one statement, and a statement's own page, need no source line.
    assert result["one"] == "" and result["statement"] == ""
    assert not any(job in json.dumps(result) for job in JOBS)


# ----------------------------------------------------------------------------------- A: review round 1's wordings
#: Two accounts of CONTOSO, operating and payroll, each printing March and April 2054.
TWO_ACCOUNTS = [_doc(JOB_MAR, 3, "CONTOSO operating march.pdf"), _doc(JOB_APR, 4, "CONTOSO operating april.pdf"),
                _doc(JOB_MAY, 3, "CONTOSO payroll march.pdf"), _doc(JOB_B_APR, 4, "CONTOSO payroll april.pdf")]


@needs_node
def test_a_cross_statement_line_names_the_files_where_a_month_is_shared():
    payroll = {**_change("decrease", 1000.0, 700.0, -30, cadence_before="weekly", cadence_after="weekly",
                         payments_before=4, payments_after=4, first_after_date="2054-04-01"),
               "scope": "package", "source_currency": "USD", "cross_statement": True,
               **_source(JOB_B_APR, "CONTOSO payroll april.pdf"),
               **_source(JOB_MAY, "CONTOSO payroll march.pdf", "from"),
               **_source(JOB_B_APR, "CONTOSO payroll april.pdf", "to")}
    returned = {**RETURNED_ACROSS, **_source(JOB_MAY, "CONTOSO payroll march.pdf"),
                **_source(JOB_B_APR, "CONTOSO payroll april.pdf", "credit")}
    [change] = _notes([payroll], TWO_ACCOUNTS)
    [bounce] = _notes([returned], TWO_ACCOUNTS, returned=True)
    both = ("From: March 2054 statement, CONTOSO payroll march.pdf → April 2054 statement, CONTOSO payroll "
            "april.pdf")
    assert change["source"] == both and bounce["source"] == both
    # The same item where each month has one statement keeps the bare months.
    [alone] = _notes([payroll], [TWO_ACCOUNTS[2], TWO_ACCOUNTS[3]])
    assert alone["source"] == "From: March 2054 → April 2054 statements"
    assert not any(job in json.dumps([change, bounce, alone]) for job in JOBS)


@needs_node
def test_a_change_across_schedules_leads_with_the_weekly_total():
    lower = _change("decrease", 500.0, 1800.0, -28, cadence_after="weekly", cadence_changed=True,
                    weekly_equivalent_before=2500.0, weekly_equivalent_after=1800.0, payments_before=15,
                    payments_after=4, first_after_date="2054-03-23")
    [note] = _notes([lower])
    assert note == _note("KAPITUS: weekly payment total went down 28%", [
        "The weekly total went from $2,500.00 to $1,800.00.",
        "Payments changed from daily $500.00 to weekly $1,800.00 starting Mar 23, 2054 (4 payments at the new amount, "
        "after 15 at the old)."])


@needs_node
def test_the_grace_window_reads_as_a_threshold_for_every_schedule():
    irregular = {**POSSIBLE_STOP, "cadence": "daily_irregular", "grace_business_days": 6, "quiet_business_days": 7}
    monthly = {**POSSIBLE_STOP, "cadence": "monthly", "grace_business_days": 25, "quiet_business_days": 26}
    pause = {**PAUSE, "cadence": "semimonthly", "grace_business_days": 15, "pause_business_days": 17}
    notes = _notes([irregular, monthly, pause])
    assert notes[0]["details"][1] == "An irregular daily schedule allows up to 6 business days without a payment."
    assert notes[1]["details"][1] == "A monthly schedule allows up to 25 business days without a payment."
    assert notes[2]["details"][0] == ("No payment between Mar 20 and Apr 1, 2054 (17 business days, more than the 15 "
                                      "a semi-monthly schedule allows).")
    assert "normally" not in json.dumps(_notes([POSSIBLE_STOP, STOP_OTHER_DEBITS, PAUSE, PAUSE_ATTEMPT]))


@needs_node
def test_one_debit_at_another_amount_reads_in_the_singular():
    one = {"count": 1, "last_date": "2054-03-19"}
    possible = {**STOP_OTHER_DEBITS, "other_debits_after": one}
    confirmed = {**STOP_OTHER_DEBITS, "other_debits_after": one, "stop_confirmed": True}
    notes = _notes([possible, confirmed])
    assert notes[0]["details"][:3] == ["Last regular daily payment: $850.00 on Mar 13, 2054.",
                                       "After it came only 1 debit at another amount, on Mar 19, 2054.",
                                       "No payment in the 8 business days after Mar 19, 2054, to the end of this "
                                       "statement."]
    assert notes[1]["details"][:2] == ["Last regular daily payment: $850.00 on Mar 13, 2054.",
                                       "After it came only 1 debit at another amount, on Mar 19, 2054."]


@needs_node
def test_a_possible_stop_after_other_debits_says_how_many_quiet_business_days_passed():
    # Review round 3: the quiet business days that raised the note (quiet_business_days), counted from the last debit
    # (last_presence_date), in the voice of every other stop; "since" no longer twice, the last payment's date once.
    package = {**STOP_OTHER_DEBITS, "scope": "package", "source_currency": "USD",
               **_source(JOB_MAR, "SAMPLE BANK march.pdf")}
    later_attempt = {**STOP_OTHER_DEBITS, "last_presence_date": "2054-03-20", "quiet_business_days": 7}
    notes = _notes([STOP_OTHER_DEBITS, package, later_attempt])
    assert notes[0]["details"][2] == "No payment in the 8 business days after Mar 19, 2054, to the end of this statement."
    assert notes[1] == _note("KAPITUS: payments may have stopped", [
        "Last regular daily payment: $850.00 on Mar 13, 2054.",
        "After it came only 3 debits at other amounts, the last on Mar 19, 2054.",
        "No payment in the 8 business days after Mar 19, 2054, through Mar 31, 2054.",
        "A daily schedule allows up to 5 business days without a payment."], [], "From: March 2054 statement")
    # The quiet days run from the last presence, which can be later than the last debit at another amount.
    assert notes[2]["details"][2] == "No payment in the 7 business days after Mar 20, 2054, to the end of this statement."
    for note in notes:
        text = " ".join(note["details"])
        assert text.count("since") == 0 and text.count("Mar 13, 2054") == 1


@needs_node
def test_a_potential_lender_s_streams_sentence_repeats_no_label():
    stop = {**POSSIBLE_STOP, "lender": "Unidentified lender obligation", "position": 2, "positions": 2,
            "lender_label": "Unidentified lender obligation (weekly, 1000.00)", "lender_state": "potential"}
    [note] = _notes([stop])
    assert note["headline"] == ("Potential lender Unidentified lender obligation (weekly, 1000.00): payments may have "
                                "stopped")
    assert note["details"][-1] == "This lender has 2 separate payment streams; this note is about the second."
    assert sum("1000.00" in part for part in [note["headline"], *note["details"]]) == 1


@needs_node
def test_a_funding_on_the_day_the_new_amount_starts_reads_the_same_day():
    # Review round 2: B3's window holds the new amount's first day itself; a funding on that day is neither "just
    # before" nor "just after".
    same_day = {**INCREASE_AFTER_FUNDING, "after_funding": {"date": "2054-04-06", "amount": 25000.0}}
    before = {**INCREASE_AFTER_FUNDING, "after_funding": {"date": "2054-04-05", "amount": 25000.0}}
    after = {**INCREASE_AFTER_FUNDING, "after_funding": {"date": "2054-04-07", "amount": 25000.0}}
    notes = _notes([same_day, before, after])
    assert notes[0]["also"] == ["Also: ONDECK deposited $25,000.00 on Apr 6, 2054, the same day the new amount "
                                "started; this may be a renewal."]
    assert notes[1]["also"] == ["Also: ONDECK deposited $25,000.00 on Apr 5, 2054, just before; this may be a renewal."]
    assert notes[2]["also"] == ["Also: ONDECK deposited $25,000.00 on Apr 7, 2054, just after; this may be a renewal."]


@needs_node
def test_a_potential_lender_s_new_payments_name_the_label_they_are_listed_under():
    # Review round 2: a potential lender's label carries its schedule and amount, so the new payments are listed in the
    # lender table under another label; the note names it. A label that does not change adds nothing.
    relabelled = {**POSSIBLE_INCREASE_POTENTIAL,
                  "lender_label_after": "Unidentified lender obligation (weekly, 1800.00)"}
    cut = _change("decrease", 300.0, 250.0, -17, payments_before=12, payments_after=9, first_after_date="2054-03-17",
                  lender="Unidentified lender obligation", lender_label="Unidentified lender obligation (daily, 300.00)",
                  lender_label_after="Unidentified lender obligation (daily, 250.00)", lender_state="potential")
    unchanged = {**DECREASE, "lender_label_after": "KAPITUS"}
    notes = _notes([relabelled, cut, unchanged])
    assert notes[0]["details"] == [
        "The weekly total went from $1,500.00 to $1,800.00.",
        "Payments changed from daily $300.00 to weekly $1,800.00 starting Mar 23, 2054 (2 payments at the new amount, "
        "after 15 at the old).",
        "The new schedule isn't confirmed yet.",
        "The new payments are listed as Unidentified lender obligation (weekly, 1800.00)."]
    assert notes[1] == _note(
        "Potential lender Unidentified lender obligation (daily, 300.00): payment went down 17%", [
            "The daily payment went from $300.00 to $250.00 starting Mar 17, 2054 (9 payments at the new amount, after "
            "12 at the old).",
            "The new payments are listed as Unidentified lender obligation (daily, 250.00)."])
    assert notes[2] == _notes([DECREASE])[0]


@needs_node
def test_a_potential_lender_s_headline_reads_potential_lender_first_on_every_kind():
    # Review round 3 (the orchestrator's ruling): "Potential lender <label>: <what happened>" on every kind, never the
    # stacked "<label> (potential lender)"; the chip stays neutral. An "Also:" sentence names another potential lender
    # the same way.
    label = "Unidentified lender obligation (weekly, 1000.00)"
    potential = {"lender": "Unidentified lender obligation", "lender_label": label, "lender_state": "potential"}
    kinds = [DECREASE, INCREASE_AFTER_FUNDING, STEPS, SCHEDULE, PAUSE, NEW_STREAM, POSSIBLE_STOP, STOP_NEW_LENDER,
             STOP_OTHER_DEBITS]
    handed = {**STOP_NEW_LENDER, "new_lender_after": {
        "lender_label": "Unidentified lender obligation (weekly, 1100.00)", "lender_state": "potential",
        "cadence": "weekly", "amount": 1100.0, "first_date": "2054-04-24"}}
    items = [{**item, **potential} for item in kinds] + [handed]
    result = run_dashboard(f"""
const sources = paymentChangeSources({json.dumps(DOCUMENTS)});
const tone = (chip) => chip === glassChip(chip.match(/aria-hidden="true">([^<]*)</)[1],
  chip.match(/chip-text">([^<]*)</)[1], "neutral") ? "neutral" : "toned";
console.log(JSON.stringify({json.dumps(items)}.map((item) => [lenderPaymentChangeNote(item, 'USD', sources),
  tone(lenderPaymentChangeChip(item)), lenderPaymentChangeWarning(item, 'USD', sources)])));
""")
    happened = ["payment went down 29%", "payment went up 50%", "payment went down 12%", "payment schedule changed",
                "payments paused, then resumed", "a second payment started", "payments may have stopped",
                "payments stopped", "payments may have stopped"]
    assert [note["headline"] for note, _chip, _text in result[:-1]] == [
        f"Potential lender {label}: {what}" for what in happened]
    assert [tone for _note, tone, _text in result] == ["neutral"] * len(kinds) + ["toned"]
    # A confirmed lender's headline is as before.
    assert result[-1][0]["headline"] == "KAPITUS: payments stopped"
    assert result[-1][0]["also"] == [
        "Also: potential lender Unidentified lender obligation (weekly, 1100.00) started weekly payments of $1,100.00 "
        "on Apr 24, 2054; it may have taken over this advance."]
    texts = [text for _note, _chip, text in result]
    assert not any("(potential lender)" in text or ") (" in text for text in texts)


# ------------------------------------------------------------------------------------- A: the table and the memo
LENDER_ROWS = r"""
const rows = (html) => [...html.matchAll(/<tr([^>]*)>([\s\S]*?)<\/tr>/g)].map((m) => m[2]);
"""
FUNDER = {"funder": "KAPITUS", "debit_count": 8, "total_debited": 8000.0, "transactions": [], "evidence": []}


@needs_node
def test_the_lender_table_shows_each_part_on_its_own_line():
    escaped = {**DECREASE, "lender_label": "<b>NORTHWIND</b> & CO", "lender": "NORTHWIND"}
    unchecked = [{"source_job": JOB_UNDATED, "source_document": f"{JOB_UNDATED}_SAMPLE undated.pdf",
                  "reason": "no_period"},
                 {"source_job": JOB_B_APR, "source_document": f"{JOB_B_APR}_SAMPLE b-april.pdf",
                  "reason": "analysed_before_check"}]
    html = run_dashboard(LENDER_ROWS + f"""
renderLenders({json.dumps([FUNDER])}, [], 'USD', {json.dumps([RETURNED_ACROSS])},
  {json.dumps([INCREASE_AFTER_FUNDING, STOP_NEW_LENDER, escaped])}, {json.dumps(unchecked)}, true,
  {json.dumps(DOCUMENTS)});
console.log(JSON.stringify(els.lenderTable.innerHTML));
""")
    assert '<strong class="lender-note-headline">KAPITUS: a payment was returned</strong>' in html
    assert '<strong class="lender-note-headline">ONDECK: payment went up 50%</strong>' in html
    assert ('<div class="lender-note-detail">The weekly payment went from $1,000.00 to $1,500.00 starting Apr 6, 2054 '
            '(2 payments at the new amount, after 3 at the old).</div>') in html
    assert ('<div class="lender-note-also">Also: ONDECK deposited $25,000.00 on Apr 1, 2054, just before; this may be '
            'a renewal.</div>') in html
    # Two members print April 2054: the April end of each cross-statement line names its file.
    assert ('<div class="lender-note-source">From: March 2054 statement → April 2054 statement, SAMPLE BANK '
            'april.pdf</div>') in html
    # The chips and their tones stay; each note is a warning row above the lender rows.
    assert html.index("chip-text\">Returned<") < html.index("chip-text\">Increased<") < html.index(
        "chip-text\">No payments<") < html.index("chip-text\">Not checked<") < html.index(">KAPITUS</")
    # Every value is escaped.
    assert "&lt;b&gt;NORTHWIND&lt;/b&gt; &amp; CO: payment went down 29%" in html and "<b>" not in html
    # The members not compared, by name and in plain words.
    assert '<strong class="lender-note-headline">Payment changes not checked across statements</strong>' in html
    assert ('These 2 statements were not compared with the others: SAMPLE undated.pdf (no statement period printed, '
            'so it was checked on its own); April 2054 statement, SAMPLE b-april.pdf (analysed before the check; '
            're-analyze it to include it).') in html
    assert not any(job in html for job in JOBS)


@needs_node
def test_the_not_checked_lines_read_plainly():
    result = run_dashboard(LENDER_ROWS + f"""
const strip = (html) => html.replace(/<[^>]+>/g, " ").replace(/\\s+/g, " ").trim();
renderLenders({json.dumps([FUNDER])}, [], 'USD', [], undefined);
const statement = strip(els.lenderTable.innerHTML);
renderLenders({json.dumps([FUNDER])}, [], 'USD', [], undefined, [], true);
console.log(JSON.stringify({{statement, package: strip(els.lenderTable.innerHTML)}}));
""")
    assert result["statement"].startswith("· Not checked Payment changes not checked This statement was analysed before "
                                          "the check. Re-analyze it to see payment changes.")
    assert result["package"].startswith("· Not checked Payment changes not checked No statement in this package has "
                                        "been checked yet.")


@needs_node
def test_a_statement_page_note_has_no_source_line():
    html = run_dashboard(f"""
renderLenders({json.dumps([FUNDER])}, [], 'USD', {json.dumps([RETURNED])}, {json.dumps([DECREASE, POSSIBLE_STOP])});
console.log(JSON.stringify(els.lenderTable.innerHTML));
""")
    assert "lender-note-source" not in html and "From:" not in html
    assert '<strong class="lender-note-headline">KAPITUS: payments may have stopped</strong>' in html


@needs_node
def test_the_copied_memo_carries_the_same_words():
    text = run_dashboard(f"""
const sources = paymentChangeSources({json.dumps(DOCUMENTS)});
console.log(JSON.stringify([lenderPaymentChangeWarning({json.dumps(INCREASE_AFTER_FUNDING)}, 'USD', sources),
  lenderPaymentChangeWarning({json.dumps(DECREASE)}, 'USD', null),
  returnedFunderPaymentWarning({json.dumps(RETURNED_ACROSS)}, 'USD', sources)]));
""")
    assert text == [
        "ONDECK: payment went up 50%. The weekly payment went from $1,000.00 to $1,500.00 starting Apr 6, 2054 (2 "
        "payments at the new amount, after 3 at the old). Also: ONDECK deposited $25,000.00 on Apr 1, 2054, just "
        "before; this may be a renewal. From: March 2054 statement → April 2054 statement, SAMPLE BANK april.pdf.",
        "KAPITUS: payment went down 29%. The daily payment went from $850.00 to $600.00 starting Mar 16, 2054 (8 "
        "payments at the new amount, after 10 at the old).",
        "KAPITUS: a payment was returned. The $850.00 payment on Mar 27, 2054 was returned unpaid on Apr 2, 2054 (the "
        "bank printed: \"RETURN OF POSTED CHECK ITEM\"). It isn't counted as paid, but it still counts in the "
        "withholding rate. From: March 2054 statement → April 2054 statement, SAMPLE BANK april.pdf."]


@needs_node
def test_the_package_memo_and_page_name_the_months(tmp_path):
    from tests import test_lender_payment_changes_package as pkg

    march, april = pkg.p1()
    built = pkg.package(pkg.job("march", march), pkg.job("april", april))
    result = run_dashboard(f"""
currentJobIds = ['march', 'april']; renderPackageAnalysis({json.dumps(built)}); generateSummary();
console.log(JSON.stringify({{memo: els.summaryBox.textContent, table: els.lenderTable.innerHTML}}));
""")
    assert result["memo"].endswith(
        "\n- KAPITUS: payment went down 30%. The weekly payment went from $1,000.00 to $700.00 starting Apr 1, 2054 "
        "(4 payments at the new amount, after 4 at the old). From: March 2054 → April 2054 statements.")
    assert '<div class="lender-note-source">From: March 2054 → April 2054 statements</div>' in result["table"]


# ------------------------------------------------------------------------------------------------ B: the hero
HERO = r"""
const strip = (html) => String(html).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const hero = () => ({label: els.creditsLabel.textContent, value: els.creditsValue.textContent,
  lines: [...els.creditsMeta.innerHTML.matchAll(/<span class="credits-meta-line">([\s\S]*?)<\/span>(?=<span class="credits-meta-line">|$)/g)]
    .map((m) => strip(m[1])), meta: strip(els.creditsMeta.innerHTML)});
"""


def _money(value):
    return f"${value:,.2f}"


@needs_node
def test_the_statement_hero_shows_true_revenue_with_total_credits_below():
    from tests.test_webapp_true_revenue import _payload, _summary_only
    from tests.test_webapp_true_revenue_ui import _open, _served

    established = _served(_payload())
    short = _served(_summary_only(3))
    out = {}
    for name, payload in (("established", established), ("short", short)):
        out[name] = run_dashboard(HERO + _open(name, payload) + "console.log(JSON.stringify(hero()));")
    metrics = established["metrics"]
    assert out["established"]["label"] == "True revenue"
    assert out["established"]["value"] == _money(metrics["true_revenue_total"]) == "$1,000.00"
    assert out["established"]["lines"] == [
        f"Total credits {_money(metrics['effective_total_deposits'])} · {metrics['total_posted_credit_count']} credit "
        "transactions"]
    short_metrics = short["metrics"]
    assert out["short"]["value"] == "N/A"
    assert out["short"]["lines"] == [
        "True revenue is not established for this statement",
        f"Total credits {_money(short_metrics['effective_total_deposits'])} · "
        f"{short_metrics['total_posted_credit_count']} credit transactions"]


@needs_node
def test_the_package_hero_shows_true_revenue_with_total_credits_below(tmp_path, monkeypatch):
    from tests.test_webapp_studio_views import _package
    from tests.test_webapp_true_revenue import _SECOND_ACCOUNT_ROWS, _account_payload, _payload, _summary_only

    package = _package({"chk": _payload(), "sav": _account_payload("000000002020", _SECOND_ACCOUNT_ROWS)},
                       tmp_path, monkeypatch)
    partial = _package({"mar": _payload(), "apr": _summary_only(4)}, tmp_path, monkeypatch)
    result = run_dashboard(HERO + f"""
currentJobIds = ['chk', 'sav']; renderPackageAnalysis({json.dumps(package)});
const whole = hero();
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(partial)});
console.log(JSON.stringify({{whole, partial: hero()}}));
""")
    assert result["whole"] == {
        "label": "True revenue · 2 statements · 1 month", "value": "$3,500.00",
        "lines": ["Total credits $4,500.00 · Avg monthly gross credits $4,500.00 · True per month $3,500.00"],
        "meta": "Total credits $4,500.00 · Avg monthly gross credits $4,500.00 · True per month $3,500.00"}
    totals = partial["totals"]
    assert totals["true_revenue_total"] is None
    assert result["partial"]["label"] == "True revenue · 2 statements · 2 months"
    assert result["partial"]["value"] == "N/A"
    assert result["partial"]["lines"] == [
        "1 of 2 statements has no established revenue",
        f"Total credits {_money(totals['total_credits'])} · Avg monthly gross credits "
        f"{_money(totals['avg_monthly_credits'])} · True per month N/A"]


def test_the_page_s_default_hero_label_and_table_header():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert '<span class="credits-label" id="creditsLabel">True revenue</span>' in html
    head = html[html.index('<thead id="monthlyHead">'):html.index("</thead>", html.index('<thead id="monthlyHead">'))]
    assert re.findall(r"<th>([^<]*)</th>", head) == [
        "Month", "Year", "Total Deposits ($)", "Total Deposits Per Month", "True Deposits ($)",
        "True Deposits Per Month", "Active Positions", "Withholding Rate", "Ledger ($)", "NSF", "Action"]
    # Audit round 3, R3-MERGE: the merged app.js asks for the next free value above both lines (-8 the hosting line's).
    # The owner's request of 2026-10-10 (active positions by month): "Active Positions" right before "Withholding
    # Rate", and app.js asked for as true-revenue-12. The owner's own design (2026-10-11, display only): -13. His
    # request of 2026-10-11 to hide Verified revenue and "Counted, not verified": -14. The code audit of 2026-10-13
    # (its dashboard fixes): -15. The model-code removal (no Force visual OCR control, the advice texts rewritten): -16.
    assert '<script src="/static/app.js?v=true-revenue-16"></script>' in html


# ---------------------------------------------------------------------------------- C: the Monthly Statements
MONTHLY = r"""
const cells = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)]
  .map((row) => [...row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((cell) => cell[1].replace(/<[^>]+>/g, "").trim()));
const views = (pkg) => Object.fromEntries(["both", "total", "true"].map((view) => {
  setMonthlyDepositsView(view); renderMonthlyStatements(pkg);
  return [view, {head: cells(els.monthlyHead.innerHTML)[0], rows: cells(els.monthlyTable.innerHTML)}];
}));
"""


def _row(job, month, **fields):
    return {"id": job, "filename": f"{job}.pdf", "status": "done", "period_start": f"2054-{month:02d}-01",
            "period_end": f"2054-{month:02d}-28", "credits": 100000.0, "deposit_count": 4,
            "true_revenue_total": 60000.0, "true_revenue_count": 2, "verified_revenue_total": 20000.0,
            "revenue_established": True, "verified_revenue_established": True, "average_daily_balance": 5000.0,
            "nsf_count": 1, "currency": "USD", **fields}


@needs_node
def test_the_monthly_table_shows_each_statement_s_withholding_rate_and_no_verified_column():
    # Review round 3 (the orchestrator's ruling): the cell is the row's own figures, its served withholding_numerator
    # over its withholding_denominator (x 100, two decimals), never the statement-alone withholding_rate beside them.
    # Audit round 3, R3-MERGE: the server now serves that figure as the row's withholding_rate (round 3's R3-72 and the
    # final review's F2), so the cell reads it, guarded by the row's own figures; the cells expected are unchanged.
    rows = [_row("contoso", 1, withholding_rate=76.4912, withholding_numerator=45894.72,
                 withholding_denominator=60000.0),
            _row("fabrikam", 2, withholding_rate=None, withholding_numerator=500.0, withholding_denominator=0.0,
                 withholding_review_required=True),
            _row("northwind", 3, withholding_rate=None, withholding_numerator=1000.0, withholding_denominator=60000.0,
                 withholding_basis_unestablished=True, revenue_established=False),
            # The package passes took 20,000 out of this member's True: its row reads 6,000 over 40,000, not the 10%
            # its statement alone published over 60,000. Audit round 3, R3-MERGE: the merged server serves this row's
            # own rate, 15.0 (the hosting line's served the statement-alone 10.0 here).
            _row("sample", 4, true_revenue_total=40000.0, withholding_rate=15.0, withholding_numerator=6000.0,
                 withholding_denominator=40000.0),
            _row("stale", 5, withholding_rate=12.5, withholding_numerator=7500.0, withholding_denominator=60000.0,
                 withholding_basis_unestablished=True),
            _row("failed", 6, status="failed", withholding_rate=10.0, withholding_numerator=6000.0,
                 withholding_denominator=60000.0),
            # The package publishes no rate for this member (none served), whatever its figures say.
            _row("unrated", 7, withholding_rate=None, withholding_numerator=600.0, withholding_denominator=60000.0),
            # A row that serves only one of the two figures has no rate of its own.
            _row("unserved", 8, withholding_rate=5.0, withholding_denominator=60000.0),
            _row("negative", 9, withholding_rate=5.0, withholding_numerator=600.0, withholding_denominator=-1.0)]
    package = {"documents": rows, "totals": {}, "currency": {"currencies": ["USD"]}}
    result = run_dashboard(MONTHLY + f"console.log(JSON.stringify(views({json.dumps(package)})));")
    # The owner's request of 2026-10-10 (active positions by month): "Active Positions" sits right before it.
    assert result["both"]["head"] == ["Month", "Year", "Total Deposits ($)", "Total Deposits Per Month",
                                      "True Deposits ($)", "True Deposits Per Month", "Active Positions",
                                      "Withholding Rate", "Ledger ($)", "NSF", "Action"]
    for view in ("total", "true"):
        assert result[view]["head"] == ["Month", "Year", "Monthly Deposits ($)", "Deposits Per Month",
                                        "Active Positions", "Withholding Rate", "Ledger ($)", "NSF", "Action"], view
    expected = ["76.49%", "N/A", "N/A", "15.00%", "N/A", "N/A", "N/A", "N/A", "N/A"]
    assert [row[7] for row in result["both"]["rows"]] == expected
    assert [row[5] for row in result["total"]["rows"]] == expected
    assert [row[5] for row in result["true"]["rows"]] == expected
    assert result["both"]["rows"][0] == ["January", "2054", "100,000", "4", "60,000", "2", "N/A", "76.49%", "5,000",
                                         "1", "Open"]
    assert result["both"]["rows"][3][4:8] == ["40,000", "2", "N/A", "15.00%"]
    assert not any("Verified" in header for shown in result.values() for header in shown["head"])


#: Review round 3's probes, fabricated (tests/test_package_matching.py's CONTOSO BAKERY LLC, 2031): S1 (R2-OW15), a
#: March deposit returned on April 1, each month paying ONDECK 2,500; and R2-OW16's owner's example, account A's
#: 12,340.17 transfer held in account B, which pays ONDECK 700.
ONDECK_1 = "ONDECK CAPITAL DES:PAYMENT ID:1"
ONDECK_2 = "ONDECK CAPITAL DES:PAYMENT ID:2"


def _moved_packages():
    from tests import test_package_matching as pm

    march_rows = [(5, pm.NW_MARCH, 50000.0), (10, ONDECK_1, -2500.0), (26, "DEPOSIT", 100000.0)]
    april_rows = [(1, pm.RETURNED, -100000.0), (5, pm.NW_APRIL, 50000.0), (10, ONDECK_2, -2500.0)]
    march = pm._payload(march_rows, month=3, opening=1500.0)
    april = pm._payload(april_rows, month=4, opening=pm._closing(march_rows, 1500.0))
    returned = pm._package(("mar", march), ("apr", april))
    transfer = pm._package(("a", pm._account_a()), ("b", pm._account_b(extra=[(6, ONDECK_1, -700.0)])))
    return returned, transfer


@needs_node
def test_a_member_whose_true_the_package_reduced_shows_the_package_s_rate(monkeypatch):
    # Review round 3 (important): the Withholding Rate read the statement alone (S1's March 1.67% over 150,000, B's
    # 4.88% over 14,340.17) beside True Deposits the package passes had reduced (50,000; 2,000). The row now divides its
    # own served numerator by its own served basis: 5.00% and 35.00%, the figures the package's totals add up.
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "true_revenue")
    returned, transfer = _moved_packages()
    docs = {doc["id"]: doc for package in (returned, transfer) for doc in package["documents"]}
    assert docs["mar"]["withholding_denominator_mode"] == docs["b"]["withholding_denominator_mode"] == "true_revenue"
    # Audit round 3, R3-MERGE: round 3's R3-72 (and the final review's F2) has the server serve each member row's own
    # numerator over its own basis wherever the package moved either, so the rows serve 5.0 and 35.0 (on the hosting
    # line they served the statement-alone 1.67 and 4.88, which the cell no longer read); the cells below are unchanged.
    assert round(docs["mar"]["withholding_rate"], 2) == 5.0 and round(docs["b"]["withholding_rate"], 2) == 35.0
    assert (docs["mar"]["withholding_numerator"], docs["mar"]["withholding_denominator"]) == (2500.0, 50000.0)
    assert (docs["b"]["withholding_numerator"], docs["b"]["withholding_denominator"]) == (700.0, 2000.0)
    assert docs["mar"]["true_revenue_total"] == 50000.0 and docs["b"]["true_revenue_total"] == 2000.0
    result = run_dashboard(MONTHLY + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(returned)});
const returned = views({json.dumps(returned)});
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(transfer)});
console.log(JSON.stringify({{returned, transfer: views({json.dumps(transfer)})}}));
""")
    # True Deposits ($), its count and the Withholding Rate, row by row, in the Both view; the other views agree.
    # (The owner's request of 2026-10-10: the Active Positions cell, row[6], sits between them.)
    assert [[row[4], row[5], row[7]] for row in result["returned"]["both"]["rows"]] == [["50,000", "1", "5.00%"],
                                                                                     ["50,000", "1", "5.00%"]]
    assert [[row[4], row[5], row[7]] for row in result["transfer"]["both"]["rows"]] == [["20,000", "1", "0.00%"],
                                                                                     ["2,000", "1", "35.00%"]]
    for name in ("returned", "transfer"):
        both = [row[7] for row in result[name]["both"]["rows"]]
        assert [row[5] for row in result[name]["true"]["rows"]] == both
        assert [row[5] for row in result[name]["total"]["rows"]] == both
    # The rows add up to the package's own rate: 5,000 over 100,000 and 700 over 22,000.
    assert returned["totals"]["package_withholding_rate"] == 5.0
    assert transfer["totals"]["package_withholding_rate"] == 3.18


@needs_node
def test_a_package_that_moved_nothing_keeps_each_statement_s_own_rate(tmp_path, monkeypatch):
    from tests.test_webapp_studio_views import _package
    from tests.test_webapp_true_revenue import DETECTED_ROWS, _payload

    package = _package({"mar": _payload(DETECTED_ROWS), "apr": _payload(month=4)}, tmp_path, monkeypatch)
    docs = {doc["id"]: doc for doc in package["documents"]}
    assert docs["mar"]["withholding_rate"] is not None and docs["mar"]["withholding_rate"] > 0
    for doc in docs.values():
        # No package pass moved a credit: the row's figures are the statement's own, so its rate is too.
        if doc["withholding_rate"] is not None:
            assert doc["withholding_rate"] == pytest.approx(
                abs(doc["withholding_numerator"]) / doc["withholding_denominator"] * 100)
    result = run_dashboard(MONTHLY + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify(views({json.dumps(package)})));
""")
    shown = [row[7] for row in result["both"]["rows"]]
    rates = [docs[key]["withholding_rate"] for key in ("mar", "apr")]
    assert shown == ["N/A" if rate is None else f"{rate:.2f}%" for rate in rates]


# ---------------------------- Audit round 3, R3-MERGE: the Withholding Rate column reads the rate the server serves
@needs_node
def test_r3_merge_the_cell_prints_the_served_rate_where_it_and_the_row_s_figures_disagree():
    """Audit round 3, R3-MERGE: the cell is the row's served `withholding_rate`, the rule the server owns (R3-72 and the
    final review's F2: a member row's own numerator over its own basis wherever the package moved either; R3-20's basis
    floor; F1's unestablished basis; R3-73's and R3-79's numerator), never a division the page makes itself. Fabricated
    rows where the served rate and the row's two figures disagree, which the merged server never serves (the hosting
    line's row did, beside figures the passes had moved): the cell prints the served 9.50%, not the 10.00% the two figures
    give; a basis under R3-20's floor publishes no rate whatever its figures; a served rate keeps its own digits."""
    rows = [_row("contoso", 1, withholding_rate=9.5, withholding_numerator=6000.0, withholding_denominator=60000.0),
            _row("fabrikam", 2, withholding_rate=None, withholding_numerator=40.0, withholding_denominator=400.0,
                 withholding_basis_below_floor=True),
            _row("northwind", 3, withholding_rate=28.0, withholding_numerator=8400.0, withholding_denominator=30000.0)]
    package = {"documents": rows, "totals": {}, "currency": {"currencies": ["USD"]}}
    result = run_dashboard(MONTHLY + f"console.log(JSON.stringify(views({json.dumps(package)})));")
    assert [row[7] for row in result["both"]["rows"]] == ["9.50%", "N/A", "28.00%"]
    assert [row[5] for row in result["true"]["rows"]] == [row[5] for row in result["total"]["rows"]] == [
        "9.50%", "N/A", "28.00%"]


def _r3_merge_packages():
    """The final review's F2 probes (tests/test_represented_funder_payments.py and tests/test_lump_sum_payoffs.py; their
    fabricated CONTOSO BAKERY LLC months of 2031, KAPITUS paid weekly): `redebit`, March 25's payment returned and
    re-debited on April 3 (R3-73: the package's pass 5 takes it out of March's numerator, 2,550.00 over 30,000.00);
    `payoff`, a 5,000.00 payoff paid in March and returned on April 1 (R3-79 with Q5: it rejoins March's numerator,
    8,400.00 over 30,000.00); `floor`, a March basis of 400.00, under R3-20's floor."""
    from tests import test_represented_funder_payments as rp
    from tests.test_package_matching import _closing, _package, _payload

    april = ([(2, rp.NW_APRIL, 30000.0), (3, rp.KAPITUS_BAKERY, -850.0)]
             + [(day, rp.KAPITUS_BAKERY, -850.0) for day in (1, 8, 15, 22)])
    redebit = _package(*zip(("mar", "apr"), rp._months([*rp.MARCH, (28, rp.BARE_BOUNCE, 850.0)], april)))
    floor_march = [(3, rp.NW_MARCH, 400.0)] + [(day, rp.KAPITUS_BAKERY, -850.0) for day in (4, 11, 18, 25)]
    floor = _package(*zip(("mar", "apr"), rp._months([*floor_march, (28, rp.BARE_BOUNCE, 850.0)], april)))
    march_rows = sorted([(3, rp.NW_MARCH, 30000.0)] + [(day, rp.KAPITUS_BAKERY, -850.0) for day in (4, 11, 18, 25)]
                        + [(27, rp.KAPITUS_BAKERY_PAYOFF, -5000.0)], key=lambda row: row[0])
    april_rows = sorted([(1, rp.BARE_BOUNCE, 5000.0), (2, rp.NW_APRIL, 30000.0)]
                        + [(day, rp.KAPITUS_BAKERY, -850.0) for day in (1, 8, 15, 22)], key=lambda row: row[0])
    payoff = _package(("mar", _payload(march_rows, month=3, opening=5000.0)),
                      ("apr", _payload(april_rows, month=4, opening=_closing(march_rows, 5000.0))))
    return {"redebit": redebit, "payoff": payoff, "floor": floor}


@needs_node
def test_r3_merge_each_member_s_cell_follows_round_3_s_withholding_rules():
    """Audit round 3, R3-MERGE, the real path: each package's March row prints the rate its own figures publish under
    round 3's rules, R3-73's re-debit counted once (8.50%, not March's stored 11.33%), R3-79's returned payoff back in
    the rate (28.00%) and R3-20's floor (N/A); every cell, in every view, is the row's served rate."""
    packages = _r3_merge_packages()
    served = {name: {doc["id"]: doc["withholding_rate"] for doc in pkg["documents"]} for name, pkg in packages.items()}
    assert round(served["redebit"]["mar"], 2) == 8.5 and round(served["payoff"]["mar"], 2) == 28.0
    assert served["floor"]["mar"] is None
    script = MONTHLY + "const out = {};\n" + "".join(
        f"currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(pkg)}); "
        f"out[{json.dumps(name)}] = views({json.dumps(pkg)});\n" for name, pkg in packages.items())
    result = run_dashboard(script + "console.log(JSON.stringify(out));")
    for name in packages:
        expected = ["N/A" if served[name][key] is None else f"{served[name][key]:.2f}%" for key in ("mar", "apr")]
        both = [row[7] for row in result[name]["both"]["rows"]]
        assert both == expected, name
        assert [row[5] for row in result[name]["true"]["rows"]] == both, name
        assert [row[5] for row in result[name]["total"]["rows"]] == both, name
    assert [result[name]["both"]["rows"][0][7] for name in ("redebit", "payoff", "floor")] == ["8.50%", "28.00%", "N/A"]


# ------------------------------------------------------------- D: the follow-up (the Monthly Statements and its chart)
#: Each view's Monthly Statements rows (cells) and raw markup, read after a run that defines `cells`.
MONTHLY_CARD = r"""
const monthlyCard = (pkg) => Object.fromEntries(["both", "total", "true"].map((view) => {
  setMonthlyDepositsView(view); renderMonthlyStatements(pkg);
  return [view, {rows: cells(els.monthlyTable.innerHTML), table: els.monthlyTable.innerHTML}];
}));
"""


@needs_node
@pytest.mark.parametrize("counted", [True, False], ids=["zelle-yes", "zelle-no"])
def test_no_monthly_statements_row_carries_a_zelle_line(counted, tmp_path, monkeypatch):
    # The owner's follow-up of 2026-10-07: "can we get these zelle labels ... out of the monthly statement chart". Under
    # either Zelle choice, in every view, no row carries a Zelle line (R2-OW03's "Zelle excluded", R2-OW17's "Zelle in
    # True ... · held ..." and "counted after review"); each True cell is its figure alone. The True card's Zelle fact
    # stays. CONTOSO's fabricated March (a Zelle deposit confirmed after review) and April
    # (tests/zelle_setting_fixtures.py).
    from tests import zelle_setting_fixtures as fx
    from tests.test_webapp_studio_views import _package
    from tests.test_webapp_true_revenue_ui import METRIC_ROWS
    from tests.test_zelle_setting_ui import _decided
    from webapp.settings import save_settings

    save_settings(tmp_path, {"zelle_true_revenue": counted})
    package = _package({"mar": _decided(("transaction:2", "confirm", True)), "apr": fx.case("Z2", month=4)},
                       tmp_path, monkeypatch)
    docs = {doc["id"]: doc for doc in package["documents"]}
    result = run_dashboard(METRIC_ROWS + MONTHLY_CARD + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const notes = Object.fromEntries(metricRows(els.metricsGrid.innerHTML).map((row) => [row.label, row.note]));
console.log(JSON.stringify({{card: monthlyCard({json.dumps(package)}), trueNote: notes["True Revenue"],
  helper: typeof monthlyZelleDetail}}));
""")
    whole = lambda value: f"{round(value):,}"  # noqa: E731  the table's whole-number format
    true_cells = [whole(docs[key]["true_revenue_total"]) for key in ("mar", "apr")]
    total_cells = [whole(docs[key]["credits"]) for key in ("mar", "apr")]
    for view, shown in result["card"].items():
        assert "Zelle" not in shown["table"], view
        assert "table-cell-detail" not in shown["table"], view  # two months, one NSF basis: no other detail line
    assert [row[4] for row in result["card"]["both"]["rows"]] == true_cells
    assert [row[2] for row in result["card"]["both"]["rows"]] == total_cells
    assert [row[2] for row in result["card"]["true"]["rows"]] == true_cells
    assert [row[2] for row in result["card"]["total"]["rows"]] == total_cells
    # The True card still names the Zelle deposits, in the words of the choice.
    if counted:
        assert "Zelle deposits in True revenue: " in result["trueNote"]
    else:
        # The owner's request of 2026-10-11: the part a review counted is "counted in True revenue".
        assert "Zelle deposits excluded: " in result["trueNote"] and " · counted in True revenue: " in result["trueNote"]
    assert result["helper"] == "undefined"
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert "monthlyZelleDetail" not in source


#: Each view's chart: per bar, its class and its parts' classes and heights; the key's entries, each its swatch's class
#: (null for plain text) and its words.
CHART_KEY = r"""
const charts = (pkg) => Object.fromEntries(["both", "total", "true"].map((view) => {
  setMonthlyDepositsView(view); renderMonthlyStatements(pkg);
  const html = els.monthlyChart.innerHTML;
  const legend = html.match(/<span class="chart-legend">([\s\S]*?)<\/span>\s*<\/div>/)[1];
  const columns = html.split('<div class="bar-col">').slice(1);
  return [view, {html,
    bars: columns.map((column) => ({
      bar: (column.match(/<div class="(bar(?: [^"]*)?)" style="height: [0-9.]+px">/) || [])[1] || null,
      parts: [...column.matchAll(/<div class="(bar-part[^"]*)" style="height: ([0-9.]+)%">/g)].map((m) => [m[1], m[2]])})),
    key: [...legend.matchAll(/<span>(?:<i class="([^"]*)" aria-hidden="true"><\/i>)?([^<]*)<\/span>/g)]
      .map((m) => [m[1] || null, m[2]])}];
}));
"""
#: The swatch that names each colour a bar can draw (webapp/templates/index.html gives each pair one background).
#: The owner's request of 2026-10-11 (true revenue spec §2.2, §10.3): no verified part, so no verified shade or swatch.
SWATCH_OF = {"bar-total": "legend-swatch", "bar-true": "legend-swatch-true", "bar-part": "legend-swatch-true"}
TOTAL_KEY = ["legend-swatch", "Total deposits"]
TRUE_KEY = ["legend-swatch legend-swatch-true", "True revenue"]
LEDGER_KEY = [None, "and ledger (average daily balance) per statement"]


@needs_node
def test_every_bar_takes_only_the_colours_its_key_shows_in_every_view():
    # The owner's follow-up of 2026-10-07: "for the Monthly deposits there are like 4 different colors while the color
    # key contains only two color identifiers" (the True view drew pale bars, the tallest in the accent, and the
    # verified part darker). Now no bar is highlighted ('peak' is gone); the True view's bars are all the True revenue
    # colour; the Total view's bars are all the neutral Total colour and its key gains the Total swatch. The owner's
    # request of 2026-10-11: no verified part, shade or key entry in any view.
    rows = [_row("contoso", 1),
            _row("fabrikam", 2, credits=150000.0, true_revenue_total=90000.0, verified_revenue_total=30000.0),
            _row("northwind", 3, credits=80000.0, true_revenue_total=50000.0, verified_revenue_total=0.0)]
    package = {"documents": rows, "totals": {}, "currency": {"currencies": ["USD"]}}
    result = run_dashboard(CHART_KEY + f"console.log(JSON.stringify(charts({json.dumps(package)})));")
    for view, chart in result.items():
        assert "peak" not in chart["html"], view
        drawn = {name.split()[-1] for bar in chart["bars"] for name in [bar["bar"], *(p[0] for p in bar["parts"])]}
        swatches = {key[0].split()[-1] for key in chart["key"] if key[0]}
        # No colour on a bar that the key does not show (a bare "bar" class draws no colour of its own).
        assert {SWATCH_OF[name] for name in drawn - {"bar"}} <= swatches, view
    both, true_only, total = result["both"], result["true"], result["total"]
    # Both: the Total bar neutral, its True part in the accent.
    assert [bar["bar"] for bar in both["bars"]] == ["bar bar-total"] * 3
    assert [bar["parts"] for bar in both["bars"]] == [
        [["bar-part", "60.0"]], [["bar-part", "60.0"]], [["bar-part", "62.5"]]]
    assert both["key"] == [TOTAL_KEY, TRUE_KEY]
    # True: every bar, the tallest included, in the True revenue colour, with no part inside it.
    assert [bar["bar"] for bar in true_only["bars"]] == ["bar bar-true"] * 3
    assert [bar["parts"] for bar in true_only["bars"]] == [[], [], []]
    assert true_only["key"] == [TRUE_KEY, LEDGER_KEY]
    assert all("verified" not in chart["html"] for chart in result.values())
    # Total: every bar the Both view's neutral Total colour, and its key names it.
    assert [bar["bar"] for bar in total["bars"]] == ["bar bar-total"] * 3
    assert all(bar["parts"] == [] for bar in total["bars"])
    assert total["key"] == [TOTAL_KEY, LEDGER_KEY]


def _css_rules(html):
    """The page's style rules as (selector, declarations) pairs, comments removed (an @media rule's inner rules
    included)."""
    style = re.sub(r"/\*.*?\*/", "", html[html.index("<style>") + len("<style>"):html.index("</style>")], flags=re.S)
    return [(" ".join(selector.split()), body) for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style)]


def _declared(rules, selector, prop):
    found = [m[1].strip() for sel, body in rules if sel == selector
             for m in re.finditer(rf"(?<![\w-]){prop}:\s*([^;]+);", body)]
    assert len(found) <= 1, (selector, prop, found)
    return found[0] if found else None


def _tokens(rules, selector):
    [body] = [body for sel, body in rules if sel == selector]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", body))


def test_the_bar_colours_are_the_key_colours_in_both_themes_and_no_bar_is_highlighted():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    rules = _css_rules(html)
    assert ".peak" not in html and not any("peak" in selector for selector, _body in rules)
    # A bar has no colour of its own: each view's class gives it its key's colour.
    assert _declared(rules, ".bar", "background") is None
    assert not any("accent-muted" in body for selector, body in rules if re.search(r"\.bar\b", selector))
    pairs = {".bar.bar-total": ".legend-swatch", ".bar.bar-true": ".legend-swatch-true",
             ".bar-part": ".legend-swatch-true"}
    for bar, swatch in pairs.items():
        assert _declared(rules, bar, "background") == _declared(rules, swatch, "background") is not None, bar
    assert _declared(rules, ".legend-swatch", "background") == "var(--border-2)"
    assert _declared(rules, ".legend-swatch-true", "background") == "var(--accent)"
    # The owner's request of 2026-10-11 (true revenue spec §2.2, §10.3): no verified shade, swatch or figure.
    assert not any("verified" in selector for selector, _body in rules)
    # The figures above the bars keep their colours.
    assert _declared(rules, ".bar-value", "color") == "var(--text-2)"
    assert _declared(rules, ".bar-value-true", "color") == "var(--accent-text)"
    # Both themes resolve the same tokens: each theme sets the neutral and the accent (the verified shade is gone). The
    # owner's own design (2026-10-11): light is the root (the default) and dark the data-theme rule, each with its own
    # accent.
    light, dark = _tokens(rules, ':root, :root[data-theme="light"]'), _tokens(rules, ':root[data-theme="dark"]')
    assert {"--border-2", "--accent"} <= set(light) and "--verified" not in light
    assert {"--border-2", "--accent"} <= set(dark) and "--verified" not in dark
