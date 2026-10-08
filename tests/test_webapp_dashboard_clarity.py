"""The owner's request of 2026-10-07 (dashboard clarity; display only; true revenue spec §10.1, §10.2, §20): "make this
writing more clear ... these notes on the lenders", "make the big number ... show True revenue instead of total
credits. Total credits can be shown below it like the others" and "take off verified ($) from the monthly statement
chart and add witholding rate instead".

A: every lender note is a short headline, plain sentences under it, an "Also:" sentence per extra note and the
statement it comes from (never a job id or a "<uuid>_<file>" name). B: the hero's big figure is True revenue, Total
credits on the line below. C: the Monthly Statements table drops Verified ($) and shows each statement's confirmed
withholding rate. Driven in node through the whole webapp/static/app.js (tests/webapp_js_harness.py).

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
    assert notes[0] == _note("KAPITUS: payment went down 29%", [
        "The daily payment went from $850.00 to $600.00 starting Mar 16, 2054 (8 payments at the new amount so far, "
        "after 10 at the old)."])
    assert notes[1] == _note("ONDECK: payment went up 50%", [
        "The weekly payment went from $1,000.00 to $1,500.00 starting Apr 6, 2054 (2 payments at the new amount so "
        "far, after 3 at the old)."],
        ["Also: ONDECK deposited $25,000.00 on Apr 1, 2054, just before; this may be a renewal."],
        "From: March 2054 → April 2054 statements")
    assert notes[2] == _note(
        "Unidentified lender obligation (daily, 300.00) (potential lender): payment may have gone up 20%", [
            "Payments changed from daily $300.00 to weekly $1,800.00 starting Mar 23, 2054 (2 payments at the new "
            "amount so far, after 15 at the old).",
            "The weekly total went from $1,500.00 to $1,800.00.",
            "The new schedule isn't confirmed yet."])
    assert notes[3] == _note("KAPITUS: payment went down 12%", [
        "The weekly payment went from $1,000.00 to $880.00 starting Apr 27, 2054 (4 payments at the new amount so "
        "far, after 4 at the old).",
        "It stepped through $950.00 (-5%) on the way, then to $880.00 (-7%)."])
    assert notes[4] == _note("KAPITUS: payment schedule changed", [
        "Payments changed from daily $500.00 to weekly $2,500.00 starting Mar 23, 2054 (4 payments on the new "
        "schedule so far, after 15 on the old).",
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
    assert notes[0] == _note("KAPITUS: payments paused, then resumed", [
        "No payment between Mar 20 and Apr 1, 2054 (8 business days; daily payments normally allow 5).",
        "Payments then resumed at the same daily $850.00."])
    assert notes[1]["details"] == [
        "No payment or payment attempt between Mar 20 and Apr 1, 2054 (8 business days; daily payments normally "
        "allow 5).",
        "The attempt on Apr 1, 2054 bounced, and payments resumed at the same daily $850.00 on Apr 3, 2054."]
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
        "Weekly payments normally arrive within 10 business days.",
        "Last payment: $1,000.00 on May 13, 2054."])
    assert notes[1] == _note("KAPITUS: payments stopped", [
        "Last weekly payment: $1,000.00 on Apr 22, 2054.",
        "No payments in the 26 business days after it, through May 29, 2054."],
        ["Also: ONDECK started weekly payments of $1,100.00 on Apr 24, 2054; it may have taken over this advance."],
        "From: April 2054 statement, SAMPLE BANK april.pdf")
    assert notes[2]["details"] == [
        "No regular daily payment since Mar 13, 2054; only 3 debits at other amounts since (the last on Mar 19, 2054).",
        "Daily payments normally arrive within 5 business days.",
        "Last regular payment: $850.00 on Mar 13, 2054."]
    assert notes[3] == _note("KAPITUS: payments may have stopped", [
        "No payment or payment attempt in the last 12 business days, through May 29, 2054.",
        "Weekly payments normally arrive within 10 business days.",
        "Last payment: $1,000.00 on Apr 1, 2054.",
        "KAPITUS takes 2 separate payments; this note is about the first."], [
        "Also: a final debit of $5,000.00 on Apr 20, 2054 may be a payoff.",
        "Also: payments of $990.00 continue under Unidentified lender obligation (weekly, 990.00) (potential lender) "
        "from Apr 15, 2054; this may be a buyout or refinance.",
        "Also: a debt-relief program's payments start on Apr 18, 2054; this may mean a default or settlement.",
        "Also: payments to KAPITUS continue from another account (April 2054 statement, SAMPLE b-april.pdf) from "
        "Apr 15, 2054 at $1,000.00.",
        "Also: another KAPITUS payment of $1,200.00 weekly continues.",
        "Also: the last attempt, on Apr 8, 2054, bounced."],
        "From: April 2054 statement, SAMPLE BANK april.pdf")


@needs_node
def test_a_confirmed_stop_after_a_bounced_attempt_counts_from_the_attempt():
    stop = {**STOP_NEW_LENDER, "new_lender_after": None, "last_presence_date": "2054-04-29",
            "last_attempt_returned": {"date": "2054-04-29"}}
    [note] = _notes([stop], THREE)
    assert note["details"] == ["Last weekly payment: $1,000.00 on Apr 22, 2054.",
                               "No payment or payment attempt in the 26 business days after Apr 29, 2054, through May "
                               "29, 2054."]
    assert note["also"] == ["Also: the last attempt, on Apr 29, 2054, bounced."]
    # One April statement in the package: its month alone names it.
    assert note["source"] == "From: April 2054 statement"


@needs_node
def test_a_returned_payment_says_it_bounced_in_plain_words():
    notes = _notes([RETURNED, RETURNED_ACROSS, RETURNED_IN_ONE], THREE, returned=True)
    assert notes[0] == _note("KAPITUS: a payment bounced", [
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
    assert '<strong class="lender-note-headline">KAPITUS: a payment bounced</strong>' in html
    assert '<strong class="lender-note-headline">ONDECK: payment went up 50%</strong>' in html
    assert ('<div class="lender-note-detail">The weekly payment went from $1,000.00 to $1,500.00 starting Apr 6, 2054 '
            '(2 payments at the new amount so far, after 3 at the old).</div>') in html
    assert ('<div class="lender-note-also">Also: ONDECK deposited $25,000.00 on Apr 1, 2054, just before; this may be '
            'a renewal.</div>') in html
    assert '<div class="lender-note-source">From: March 2054 → April 2054 statements</div>' in html
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
        "payments at the new amount so far, after 3 at the old). Also: ONDECK deposited $25,000.00 on Apr 1, 2054, "
        "just before; this may be a renewal. From: March 2054 → April 2054 statements.",
        "KAPITUS: payment went down 29%. The daily payment went from $850.00 to $600.00 starting Mar 16, 2054 (8 "
        "payments at the new amount so far, after 10 at the old).",
        "KAPITUS: a payment bounced. The $850.00 payment on Mar 27, 2054 was returned unpaid on Apr 2, 2054 (the bank "
        "printed: \"RETURN OF POSTED CHECK ITEM\"). It isn't counted as paid, but it still counts in the withholding "
        "rate. From: March 2054 → April 2054 statements."]


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
        "(4 payments at the new amount so far, after 4 at the old). From: March 2054 → April 2054 statements.")
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
        "True Deposits Per Month", "Withholding Rate", "Ledger ($)", "NSF", "Action"]
    assert '<script src="/static/app.js?v=true-revenue-7"></script>' in html


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
    rows = [_row("contoso", 1, withholding_rate=76.4912, withholding_denominator=60000.0),
            _row("fabrikam", 2, withholding_rate=None, withholding_denominator=0.0, withholding_review_required=True),
            _row("northwind", 3, withholding_rate=None, withholding_basis_unestablished=True,
                 revenue_established=False),
            _row("sample", 4, withholding_rate=50, withholding_denominator=60000.0),
            _row("stale", 5, withholding_rate=12.5, withholding_basis_unestablished=True),
            _row("failed", 6, status="failed", withholding_rate=10.0)]
    package = {"documents": rows, "totals": {}, "currency": {"currencies": ["USD"]}}
    result = run_dashboard(MONTHLY + f"console.log(JSON.stringify(views({json.dumps(package)})));")
    assert result["both"]["head"] == ["Month", "Year", "Total Deposits ($)", "Total Deposits Per Month",
                                      "True Deposits ($)", "True Deposits Per Month", "Withholding Rate", "Ledger ($)",
                                      "NSF", "Action"]
    for view in ("total", "true"):
        assert result[view]["head"] == ["Month", "Year", "Monthly Deposits ($)", "Deposits Per Month",
                                        "Withholding Rate", "Ledger ($)", "NSF", "Action"], view
    expected = ["76.49%", "N/A", "N/A", "50.00%", "N/A", "N/A"]
    assert [row[6] for row in result["both"]["rows"]] == expected
    assert [row[4] for row in result["total"]["rows"]] == expected
    assert [row[4] for row in result["true"]["rows"]] == expected
    assert result["both"]["rows"][0] == ["January", "2054", "100,000", "4", "60,000", "2", "76.49%", "5,000", "1",
                                         "Open"]
    assert not any("Verified" in header for shown in result.values() for header in shown["head"])


@needs_node
def test_a_real_package_s_rows_carry_the_served_rate(tmp_path, monkeypatch):
    from tests.test_webapp_studio_views import _package
    from tests.test_webapp_true_revenue import DETECTED_ROWS, _payload

    package = _package({"mar": _payload(DETECTED_ROWS), "apr": _payload(month=4)}, tmp_path, monkeypatch)
    rates = {doc["id"]: doc["withholding_rate"] for doc in package["documents"]}
    assert rates["mar"] is not None and rates["mar"] > 0
    result = run_dashboard(MONTHLY + f"""
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify(views({json.dumps(package)})));
""")
    shown = [row[6] for row in result["both"]["rows"]]
    assert shown == [f"{rates['mar']:.2f}%", "N/A" if rates["apr"] is None else f"{rates['apr']:.2f}%"]
