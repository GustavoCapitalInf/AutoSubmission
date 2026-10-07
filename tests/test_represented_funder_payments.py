"""The owner's answer of 2026-10-07 to audit round 3's R3-73: "Count it once (Recommended)" (true revenue spec §6.2 pass
7c and the package passes, §10.1, §11, §14.3 G7, §17.1, §19.1, §20; audit round 3, R3-B02).

A confirmed funder's payment the bank returned unpaid stays in the withholding numerator (the owner's ruling of
2026-10-02 on the underwriter's Q5, R2-OW13: "the obligation standing") until the same funder re-debits it: the same
cents off its cycle within one cadence gap after the return (a re-presentment), or an exact 2x debit within that gap (a
catch-up, covering the bounced payment once). Then the returned attempt LEAVES the numerator (its
`contributes_to_withholding_rate` cleared, `represented_by` naming the re-debit) and the warning says "re-presented on
<date>" (or "caught up on <date>, 2x"). Paid to lenders, the lender count and revenue do not move. The package applies the
same rule across a member boundary; G7 declares the move row by row (`returned_funder_represented`).

Fabricated rows only (CONTOSO PLUMBING LLC and CONTOSO BAKERY LLC; FABRIKAM and NORTHWIND payees; KAPITUS and ONDECK,
public funders of the registry, as the lender tests use them; March 2054 and March and April 2031; neutral whole
amounts)."""
from __future__ import annotations

import json
from dataclasses import fields, replace

import pytest

from analysis import transaction_classifier as tc
from analysis.detect import detect
from analysis.metrics import compute_metrics
from tests.test_returned_funder_payments import BOFA_RETURN, KAPITUS, NAMED_RETURN, ONDECK, SALE, _pairs, _statement
from tests.webapp_js_harness import NODE, run_dashboard

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

#: KAPITUS's weekly 1,000.00 on the Fridays of March 2054 (the 6th, 13th, 20th and 27th); a return of the 13th's on the
#: 15th; the 24,000.00 sale keeps True revenue established.
SALE_ROW = (1, SALE, 24000.0)


def _weekly(*extra, days=(6, 13, 20, 27), amount=-1000.0):
    rows = [SALE_ROW, *[(day, KAPITUS, amount) for day in days], (15, BOFA_RETURN, 1000.0), *extra]
    return sorted(rows, key=lambda row: row[0])


#: name -> (rows, {returned debit's day: (re-debit's day, kind)}, withholding numerator, paid to lenders).
CASES = {
    # A re-presented weekly payment: the 13th's, returned on the 15th, re-debited on Monday the 16th (off its Friday
    # cycle): counted once.
    "re_presented": (_weekly((16, KAPITUS, -1000.0)), {"13": ("16", "re_presented")}, 4000.0, 4000.0),
    # The named pair's route (5.4's lender side, R2-OW13's restore) reads the same.
    "named_pair": ([SALE_ROW, (6, KAPITUS, -1000.0), (13, KAPITUS, -1000.0), (15, NAMED_RETURN, 1000.0),
                    (16, KAPITUS, -1000.0), (20, KAPITUS, -1000.0), (27, KAPITUS, -1000.0)],
                   {"13": ("16", "re_presented")}, 4000.0, 4000.0),
    # The re-presentment bounces too (returned on the 18th): the first attempt leaves, the second stands (one
    # obligation, counted once, never paid).
    "bounced_again": (_weekly((16, KAPITUS, -1000.0), (18, BOFA_RETURN, 1000.0)), {"13": ("16", "re_presented")},
                      4000.0, 3000.0),
    # Controls: the next regular payment is on its cycle (the ruling's own case: the obligation stands).
    "on_cycle": (_weekly(), {}, 4000.0, 3000.0),
    # A same-cents re-debit outside one cycle after the return (the 23rd, 8 days after it): stays.
    "outside_the_gap": (_weekly((23, KAPITUS, -1000.0)), {}, 5000.0, 4000.0),
    # A 2x debit 12 days after the return: stays.
    "catch_up_too_late": (_weekly(days=(6, 13, 20)) + [(27, KAPITUS, -2000.0)], {}, 5000.0, 4000.0),
    # A re-debit by another funder: stays.
    "other_funder": (_weekly((16, ONDECK, -1000.0)), {}, 5000.0, 4000.0),
    # A weekly 2x catch-up on the next cycle (the 20th), 5 days after the return.
    "weekly_catch_up": (_weekly(days=(6, 13, 27)) + [(20, KAPITUS, -2000.0)], {"13": ("20", "caught_up")},
                        4000.0, 4000.0),
}
#: A daily 250.00 series on the business days of March 2054 (Monday the 2nd to Friday the 13th): the 5th's payment
#: returned on the 6th, and 500.00 taken on the 6th: a 2x catch-up.
DAILY = sorted([SALE_ROW, *[(day, KAPITUS, -250.0) for day in (2, 3, 4, 5, 9, 10, 11, 12, 13)],
                (6, KAPITUS, -500.0), (6, BOFA_RETURN, 250.0)], key=lambda row: row[0])
CASES["daily_catch_up"] = (DAILY, {"05": ("06", "caught_up")}, 2500.0, 2500.0)


def _represented(records):
    """{returned debit's day: (re-debit's day, kind)} from the records."""
    days = {record.source_location: record.date[-2:] for record in records}
    found = {}
    for record in records:
        if record.represented_by:
            kind = "caught_up" if "caught it up 2x" in record.reason else "re_presented"
            found[record.date[-2:]] = (days[record.represented_by], kind)
    return found


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_returned_payment_leaves_the_numerator_once_its_funder_re_debits_it(name):
    rows, expected, numerator, paid = CASES[name]
    statement = _statement(rows)
    records = tc.classify_statement_transactions(statement)
    assert _represented(records) == expected
    for record in records:
        if record.represented_by:
            # Out of the withholding rate; still returned, out of paid and in the lender count.
            assert record.returned_funder_payment_by and record.classification == "confirmed_lender"
            assert (record.contributes_to_withholding_rate, record.contributes_to_lender_totals,
                    record.contributes_to_lender_count) == (False, False, True)
        elif record.returned_funder_payment_by:
            assert record.contributes_to_withholding_rate is True
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.withholding_numerator, metrics.lender_debits) == (numerator, paid)
    # Paid, the returned total and the lender count never move: only the numerator, by the matched attempts.
    represented = sum(abs(record.amount) for record in records if record.represented_by)
    assert metrics.withholding_numerator == round(metrics.lender_debits + metrics.returned_funder_payment_total
                                                  - represented, 2)
    assert metrics.lenders_detected == len({record.canonical_entity for record in records
                                            if record.contributes_to_lender_count and record.canonical_entity})


def test_the_warning_item_names_the_re_debit():
    rows = CASES["re_presented"][0]
    statement = _statement(rows)
    records = tc.classify_statement_transactions(statement)
    [item] = detect(statement, classifications=records).returned_funder_payments
    assert item == {
        "funder": "KAPITUS", "amount": 1000.0, "debit_date": "2054-03-13", "debit_location": "transaction:3",
        "credit_date": "2054-03-15", "credit_location": "transaction:4", "credit_description": BOFA_RETURN,
        "represented_date": "2054-03-16", "represented_location": "transaction:5", "represented_kind": "re_presented"}
    debit = records[2]
    assert debit.represented_by == "transaction:5"
    assert debit.reason.endswith(
        "The funder re-presented it by transaction:5: out of the withholding rate, which counts the obligation once "
        "(the owner's answer on re-presented payments, \"Count it once\").")
    assert _pairs(records) == {"transaction:3": "transaction:4"}
    metrics = compute_metrics(statement, classifications=records)
    assert ("1 returned funder payment (1,000.00 USD): out of paid to lenders; 1 re-debited by its funder "
            "(1,000.00 USD), counted once by the re-debit") in metrics.notes
    # A returned payment still standing keeps today's item and note.
    on_cycle = _statement(CASES["on_cycle"][0])
    on_cycle_records = tc.classify_statement_transactions(on_cycle)
    [standing] = detect(on_cycle, classifications=on_cycle_records).returned_funder_payments
    assert "represented_date" not in standing
    assert ("1 returned funder payment (1,000.00 USD): out of paid to lenders, kept in the withholding rate"
            in compute_metrics(on_cycle, classifications=on_cycle_records).notes)


def test_the_cli_names_the_re_debited_payment():
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analyze import _render

    statement = _statement(CASES["re_presented"][0], balances=True)
    statement = statement.model_copy(update={"beginning_balance": 50000.0,
                                             "ending_balance": statement.transactions[-1].running_balance})
    report = analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                               model_used="fabricated-test")
    text = _render(report.accounts[0])
    assert ("  Returned funder payments: 1 row(s), $1,000.00 (1 re-debited by the funder, $1,000.00, counted once; "
            "0 kept in withholding)") in text


def test_a_catch_up_is_named_as_one():
    statement = _statement(DAILY)
    records = tc.classify_statement_transactions(statement)
    [item] = detect(statement, classifications=records).returned_funder_payments
    assert (item["debit_date"], item["represented_date"], item["represented_kind"]) == (
        "2054-03-05", "2054-03-06", "caught_up")
    [returned] = [record for record in records if record.represented_by]
    assert "The funder caught it up 2x by" in returned.reason


def test_a_two_x_level_of_its_own_is_no_catch_up():
    # A second weekly position at 2,000.00 on the same Fridays: the 20th's 2,000.00 is its regular payment.
    rows = _weekly(*[(day, KAPITUS, -2000.0) for day in (6, 13, 20, 27)])
    records = tc.classify_statement_transactions(_statement(rows))
    assert _represented(records) == {}
    # Three 2x debits within a week of the candidate on a daily rhythm: a level of its own.
    daily_level = sorted([SALE_ROW, *[(day, KAPITUS, -250.0) for day in (2, 3, 4, 5, 9, 10)], (6, BOFA_RETURN, 250.0),
                          *[(day, KAPITUS, -500.0) for day in (6, 9, 10)]], key=lambda row: row[0])
    assert _represented(tc.classify_statement_transactions(_statement(daily_level))) == {}


def test_two_two_x_debits_after_a_bounce_are_no_level_and_the_first_catches_up():
    # An irregular rhythm: the 3rd's 500.00 returned on the 5th, 1,000.00 taken that day and again on the 9th.
    rows = [SALE_ROW, (3, KAPITUS, -500.0), (5, BOFA_RETURN, 500.0), (5, KAPITUS, -1000.0), (9, KAPITUS, -1000.0),
            (12, KAPITUS, -500.0)]
    assert _represented(tc.classify_statement_transactions(_statement(rows))) == {"03": ("05", "caught_up")}


def test_two_x_debits_off_the_cycle_do_not_hide_a_weekly_schedule():
    # Mondays 1,000.00 (the 2nd to the 30th); the 16th's returned on the 17th and caught up 2x on Wednesday the 18th;
    # another 2,000.00 on Friday the 6th blurs the series read with its 2x dates, so the Monday dates alone read it.
    rows = sorted([SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (2, 9, 16, 23, 30)], (6, KAPITUS, -2000.0),
                   (17, BOFA_RETURN, 1000.0), (18, KAPITUS, -2000.0)], key=lambda row: row[0])
    assert _represented(tc.classify_statement_transactions(_statement(rows))) == {"16": ("18", "caught_up")}


#: Shapes the measurement found misread before the schedule needed three dates and a biweekly series its weekday
#: (fabricated): the returned Friday payment's series is only itself and two more.
SHORT_SERIES = {
    # A three-payment weekly series whose middle payment comes after the return: on its Friday cycle, never a
    # re-presentment (without it, the 6th and the 20th read biweekly and the 13th off its fortnight).
    "middle_payment": [SALE_ROW, (6, KAPITUS, -1000.0), (9, BOFA_RETURN, 1000.0), (13, KAPITUS, -1000.0),
                       (20, KAPITUS, -1000.0)],
    # A re-debit 8 days after the return in a series of two other dates a fortnight apart.
    "two_dates": [SALE_ROW, (3, KAPITUS, -1000.0), (4, BOFA_RETURN, 1000.0), (12, KAPITUS, -1000.0),
                  (17, KAPITUS, -1000.0)],
}


@pytest.mark.parametrize("name", sorted(SHORT_SERIES))
def test_a_series_too_short_to_show_its_cycle_reads_nothing(name):
    records = tc.classify_statement_transactions(_statement(SHORT_SERIES[name]))
    assert _pairs(records)  # the payment was returned
    assert _represented(records) == {}


# ------------------------------------------------------------------------- review round 1 of R3-B02 (fabricated)

#: Two weekdays of every week of March 2054 (0 = Monday the 2nd): a twice-weekly schedule at one amount, or two
#: same-cents positions of one funder.
TWICE_WEEKLY_LAYOUTS = {"mon_wed": (0, 2), "tue_thu": (1, 3), "wed_fri": (2, 4), "mon_thu": (0, 3),
                        "tue_fri": (1, 4), "mon_fri": (0, 4)}


def _twice_weekly(first, second, week):
    """KAPITUS's 1,000.00 on weekdays `first` and `second` of every week of March 2054; the `week`th payment on `first`
    is returned the next day."""
    rows = [SALE_ROW, *[(2 + start + weekday, KAPITUS, -1000.0) for start in (0, 7, 14, 21, 28)
                        for weekday in (first, second) if 2 + start + weekday <= 31]]
    rows.append((2 + 7 * week + first + 1, BOFA_RETURN, 1000.0))
    return sorted(rows, key=lambda row: row[0])


@pytest.mark.parametrize("week", [1, 2, 3])
@pytest.mark.parametrize("layout", sorted(TWICE_WEEKLY_LAYOUTS))
def test_a_second_recurring_weekday_is_no_re_presentment(layout, week):
    """Review round 1 of R3-B02 (finding 1): the other weekday's next payment is that schedule's own, never a
    re-debit: a phase two or more other attempts of the series keep is a recurring phase (a twice-weekly schedule or a
    second same-cents position), which cannot be told from a re-presentment, so the returned payment stands, as Q5
    rules until a re-debit exists."""
    statement = _statement(_twice_weekly(*TWICE_WEEKLY_LAYOUTS[layout], week))
    records = tc.classify_statement_transactions(statement)
    assert _pairs(records)  # the payment was returned
    assert _represented(records) == {}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.withholding_numerator == round(metrics.lender_debits + 1000.0, 2)


def test_two_re_presentments_on_one_off_weekday_each_count_once():
    """A control for the recurring-phase guard: KAPITUS's Friday series (the 6th to the 27th of March 2054), the 6th's
    payment returned on Monday the 9th and re-presented on Tuesday the 10th, the 13th's returned on Monday the 16th and
    re-presented on Tuesday the 17th. One other Tuesday is no recurring phase: each returned payment counts once."""
    rows = sorted([SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (6, 13, 20, 27)], (9, BOFA_RETURN, 1000.0),
                   (10, KAPITUS, -1000.0), (16, BOFA_RETURN, 1000.0), (17, KAPITUS, -1000.0)],
                  key=lambda row: row[0])
    assert _represented(tc.classify_statement_transactions(_statement(rows))) == {
        "06": ("10", "re_presented"), "13": ("17", "re_presented")}


def test_a_weekly_step_up_to_2x_right_after_a_bounce_is_a_new_level_not_a_catch_up():
    """Review round 1 of R3-B02 (finding 2): KAPITUS's Monday 1,000.00 (the 2nd and the 9th of March 2054), the 9th's
    returned on Wednesday the 11th, then 2,000.00 every Monday (the 16th, 23rd and 30th): two more 2x payments on the
    cycle within two cycles after the first make 2x a level of its own (a renewal or a modified payment), so the first
    is no catch-up and the returned payment stands. A step-up seen for only one more cycle still reads as a catch-up (the
    limit of one statement; spec §17.1, the R2-OW13 defaults' (9))."""
    rows = sorted([SALE_ROW, (2, KAPITUS, -1000.0), (9, KAPITUS, -1000.0), (11, BOFA_RETURN, 1000.0),
                   *[(day, KAPITUS, -2000.0) for day in (16, 23, 30)]], key=lambda row: row[0])
    statement = _statement(rows)
    records = tc.classify_statement_transactions(statement)
    assert _pairs(records)
    assert _represented(records) == {}
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.withholding_numerator, metrics.lender_debits) == (8000.0, 7000.0)
    short = sorted([SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (2, 9, 16)], (18, BOFA_RETURN, 1000.0),
                    *[(day, KAPITUS, -2000.0) for day in (23, 30)]], key=lambda row: row[0])
    assert _represented(tc.classify_statement_transactions(_statement(short))) == {"16": ("23", "caught_up")}
    # Review round 2 of R3-B02 (finding 1): every 2x debit after it counts, on the series' cycle or not. A Thursday
    # series (the 5th to the 26th), the 5th's returned on Friday the 6th and 2,000.00 on Tuesday the 10th, then 2,000.00
    # on Thursday the 19th and on Tuesday the 24th: two 2x debits within two cycles after the 10th make 2x a level of
    # its own, so the 10th is no catch-up and the 5th stands (the 12th's regular 1,000.00 was paid).
    off_cycle = sorted([SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (5, 12, 19, 26)], (6, BOFA_RETURN, 1000.0),
                        *[(day, KAPITUS, -2000.0) for day in (10, 19, 24)]], key=lambda row: row[0])
    assert _represented(tc.classify_statement_transactions(_statement(off_cycle))) == {}


#: Review round 2 of R3-B02 (finding 1), a fabricated rebuild of a corpus shape (relative days only): KAPITUS pays
#: 1,000.00 every Thursday of March 2054 (the 5th to the 26th; the 5th's returned on Friday the 6th) and runs a second
#: position on Tuesdays at about 2x (2,500.00 on the 3rd, returned on the 4th; 2,000.00 on the 10th, returned on the
#: 11th; 2,000.00 on the 24th), with one more 2,000.00 beside the Thursday 19th's 1,000.00. The Thursday position never
#: re-debits the 5th's payment (the 12th's is its regular 1,000.00), so the 10th's 2,000.00 is the second position's
#: own payment, no catch-up: the 5th stands, as Q5 rules until a re-debit exists.
SECOND_POSITION = [SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (5, 12, 19, 26)], (6, BOFA_RETURN, 1000.0),
                   (3, KAPITUS, -2500.0), (4, BOFA_RETURN, 2500.0), (10, KAPITUS, -2000.0), (11, BOFA_RETURN, 2000.0),
                   (19, KAPITUS, -2000.0), (24, KAPITUS, -2000.0)]
#: name -> (rows, withholding numerator, paid to lenders).
SECOND_POSITION_CASES = {
    "as_in_the_corpus": (SECOND_POSITION, 12500.0, 7000.0),
    # Without the Tuesday position's earlier 2,500.00.
    "two_positions_only": ([row for row in SECOND_POSITION if abs(row[2]) != 2500.0], 10000.0, 7000.0),
    # The Tuesday position's 2,000.00 of the 10th paid, not returned.
    "the_tuesday_payment_paid": ([row for row in SECOND_POSITION if row[0] != 11], 12500.0, 9000.0),
}


@pytest.mark.parametrize("name", sorted(SECOND_POSITION_CASES))
def test_a_second_position_s_2x_payment_on_another_weekday_is_no_catch_up(name):
    rows, numerator, paid = SECOND_POSITION_CASES[name]
    statement = _statement(sorted(rows, key=lambda row: row[0]))
    records = tc.classify_statement_transactions(statement)
    assert _represented(records) == {}
    [thursday] = [record for record in records if record.date.endswith("-05")]
    assert thursday.returned_funder_payment_by and thursday.contributes_to_withholding_rate is True
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.withholding_numerator, metrics.lender_debits) == (numerator, paid)


#: Review round 2 of R3-B02 (finding 2): a 2x level that ran BEFORE the candidate (a second position at exactly twice
#: the cents) is no catch-up either, though its next payment falls past the statement's end or never comes. KAPITUS's
#: 1,000.00 on the Mondays of March 2054, the 16th's returned on Tuesday the 17th. name -> (rows, numerator, paid).
LEVEL_BEFORE_CASES = {
    # The 2,000.00 position on the same Mondays (2 to 23), the statement ending before the 30th.
    "level_at_the_statement_s_end": (
        [SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (2, 9, 16, 23)],
         *[(day, KAPITUS, -2000.0) for day in (2, 9, 16, 23)], (17, BOFA_RETURN, 1000.0)], 12000.0, 11000.0),
    # The 2,000.00 position paid off on the 23rd, the 1,000.00 running on to the 30th.
    "level_paid_off": (
        [SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (2, 9, 16, 23, 30)],
         *[(day, KAPITUS, -2000.0) for day in (2, 9, 16, 23)], (17, BOFA_RETURN, 1000.0)], 13000.0, 12000.0),
    # The 2,000.00 position on Wednesdays (the 4th, 11th and 18th), paid off on the 18th.
    "wednesday_level_paid_off": (
        [SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (2, 9, 16, 23, 30)],
         *[(day, KAPITUS, -2000.0) for day in (4, 11, 18)], (17, BOFA_RETURN, 1000.0)], 11000.0, 10000.0),
}


@pytest.mark.parametrize("name", sorted(LEVEL_BEFORE_CASES))
def test_a_2x_level_running_before_the_candidate_is_no_catch_up(name):
    rows, numerator, paid = LEVEL_BEFORE_CASES[name]
    statement = _statement(sorted(rows, key=lambda row: row[0]))
    records = tc.classify_statement_transactions(statement)
    assert _pairs(records)  # the payment was returned
    assert _represented(records) == {}
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.withholding_numerator, metrics.lender_debits) == (numerator, paid)


def test_one_earlier_catch_up_makes_no_level():
    """A control for the level windows: KAPITUS's Monday 1,000.00 (March 2054), the 2nd's returned on the 3rd and caught
    up 2x on the 9th, the 16th's returned on the 17th and caught up 2x on the 23rd. One 2x debit two cycles before the
    23rd (or after the 9th) is no level: each returned payment counts once."""
    rows = [SALE_ROW, (2, KAPITUS, -1000.0), (3, BOFA_RETURN, 1000.0), (9, KAPITUS, -2000.0), (16, KAPITUS, -1000.0),
            (17, BOFA_RETURN, 1000.0), (23, KAPITUS, -2000.0), (30, KAPITUS, -1000.0)]
    assert _represented(tc.classify_statement_transactions(_statement(rows))) == {
        "02": ("09", "caught_up"), "16": ("23", "caught_up")}


def test_a_catch_up_already_taken_is_no_level_payment():
    """Review round 2 of R3-B02 (the level window before the candidate): KAPITUS's Friday 1,000.00 from March 6 to
    April 10, 2054, every other payment returned and caught up 2x the next Friday. The two earlier catch-ups, already
    taken as re-debits, are no level payments, though leaving them out reads the series biweekly (a 29-day window):
    each returned payment counts once (the rule itself, as the package calls it)."""
    from datetime import date

    from analysis.represented_payments import CAUGHT_UP, Attempt, Returned, re_debits

    days = {"p0": (3, 6), "p1": (3, 13), "p2": (3, 20), "p3": (3, 27), "p4": (4, 3), "p5": (4, 10)}
    attempts = {key: Attempt(key, "KAPITUS", date(2054, *day), 200000 if key in ("p1", "p3", "p5") else 100000,
                             (date(2054, *day), index))
                for index, (key, day) in enumerate(days.items())}
    returned = [Returned(attempts["p0"], date(2054, 3, 11)), Returned(attempts["p2"], date(2054, 3, 24)),
                Returned(attempts["p4"], date(2054, 4, 8))]
    assert re_debits(returned, list(attempts.values())) == {
        "p0": ("p1", CAUGHT_UP), "p2": ("p3", CAUGHT_UP), "p4": ("p5", CAUGHT_UP)}


#: Review round 2 of R3-B02 (finding 3): a funder that re-presents every bounced payment on one weekday (KAPITUS's
#: 1,000.00, March 2054). Those re-presentments are no schedule: each follows another return of the series within one
#: cycle, so they make no recurring phase, and each returned payment counts once. name -> (rows, {returned: re-debit}).
#: (Where the re-presentments sit one to four days after the payments, the median gap reads no weekly schedule and
#: every returned payment stands, as before the review rounds: spec §17.1, the R2-OW13 defaults' (9).)
CHRONIC_CASES = {
    # Fridays (6 to 27); the 6th, 13th and 20th returned on the Tuesday after, re-presented on the Wednesday.
    "friday_series_wednesday_re_presentments": (
        [SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (6, 13, 20, 27)],
         *[(day + 4, BOFA_RETURN, 1000.0) for day in (6, 13, 20)], *[(day + 5, KAPITUS, -1000.0) for day in (6, 13, 20)]],
        {"06": "11", "13": "18", "20": "25"}),
    # Thursdays (5 to 26); the 5th, 12th and 19th returned on the Monday after, re-presented on the Tuesday.
    "thursday_series_tuesday_re_presentments": (
        [SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (5, 12, 19, 26)],
         *[(day + 4, BOFA_RETURN, 1000.0) for day in (5, 12, 19)], *[(day + 5, KAPITUS, -1000.0) for day in (5, 12, 19)]],
        {"05": "10", "12": "17", "19": "24"}),
    # Wednesdays (4 to 25); the 4th, 11th and 18th returned on the Friday, re-presented on the Monday after.
    "wednesday_series_monday_re_presentments": (
        [SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (4, 11, 18, 25)],
         *[(day + 2, BOFA_RETURN, 1000.0) for day in (4, 11, 18)], *[(day + 5, KAPITUS, -1000.0) for day in (4, 11, 18)]],
        {"04": "09", "11": "16", "18": "23"}),
}


@pytest.mark.parametrize("name", sorted(CHRONIC_CASES))
def test_chronic_re_presentments_on_one_weekday_each_count_once(name):
    rows, expected = CHRONIC_CASES[name]
    statement = _statement(sorted(rows, key=lambda row: row[0]))
    records = tc.classify_statement_transactions(statement)
    assert _represented(records) == {day: (re_debit, "re_presented") for day, re_debit in expected.items()}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.withholding_numerator == metrics.lender_debits


def test_a_twice_weekly_schedule_whose_first_weekday_bounces_three_times_stays_standing():
    """The control for the chronic reading: a Monday and Thursday schedule (KAPITUS's 1,000.00, March 2054), the
    Mondays 9th, 16th and 23rd returned on the Tuesday after. The Thursday of the 5th follows no return, so Thursday is
    a recurring phase of the schedule: its payments are its own, and the three returned payments stand."""
    rows = sorted([SALE_ROW, *[(day, KAPITUS, -1000.0) for day in (2, 9, 16, 23, 30)],
                   *[(day, KAPITUS, -1000.0) for day in (5, 12, 19, 26)],
                   *[(day + 1, BOFA_RETURN, 1000.0) for day in (9, 16, 23)]], key=lambda row: row[0])
    statement = _statement(rows)
    records = tc.classify_statement_transactions(statement)
    assert len(_pairs(records)) == 3
    assert _represented(records) == {}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.withholding_numerator == round(metrics.lender_debits + 3000.0, 2)


def test_a_re_debited_payment_s_reason_no_longer_says_it_is_kept_in_the_rate():
    """Review round 1 of R3-B02 (finding 3): the Q5 sentence of a re-debited payment drops "kept in the withholding
    rate", which the re-debit sentence after it contradicted; a payment still standing keeps it word for word."""
    records = tc.classify_statement_transactions(_statement(CASES["re_presented"][0]))
    debit = records[2]
    assert debit.represented_by == "transaction:5"
    assert "kept in the withholding rate" not in debit.reason
    assert debit.reason.endswith(
        "Returned unpaid by transaction:4: out of paid to lenders (the owner's ruling on the underwriter's Q5). The "
        "funder re-presented it by transaction:5: out of the withholding rate, which counts the obligation once (the "
        "owner's answer on re-presented payments, \"Count it once\").")
    [standing] = [record for record in tc.classify_statement_transactions(_statement(CASES["on_cycle"][0]))
                  if record.returned_funder_payment_by]
    assert standing.reason.endswith(
        "Returned unpaid by transaction:4: out of paid to lenders, kept in the withholding rate (the owner's ruling on "
        "the underwriter's Q5).")


def test_the_record_carries_represented_by_after_the_two_returned_fields():
    names = [field.name for field in fields(tc.TransactionClassification)]
    position = names.index("returns_funder_payment")
    assert names[position + 1] == "represented_by"
    assert getattr(tc.classify_transaction(KAPITUS, -850.0), "represented_by") is None


@pytest.mark.parametrize("name", ["re_presented", "daily_catch_up", "bounced_again"])
def test_pass_7c_moves_no_revenue_reading_and_nothing_but_the_returned_debit(monkeypatch, name):
    rows = CASES[name][0]
    after = tc.classify_statement_transactions(_statement(rows))
    monkeypatch.setattr(tc, "_apply_represented_funder_payments", lambda records, duplicates, calendar="US": records)
    before = tc.classify_statement_transactions(_statement(rows))
    for old, new in zip(before, after):
        if new.represented_by:
            assert replace(new, represented_by=None, contributes_to_withholding_rate=True, reason=old.reason) == old
        else:
            assert new == old


# ---------------------------------------------------------------------------------------------- the package boundary

KAPITUS_BAKERY = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO BAKERY LLC CO ID:0000000002 CCD"
BARE_BOUNCE = "ACH RETURN ITEM NSF"
NW_MARCH, NW_APRIL = "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "NORTHWIND SUPPLY LLC DES:PAYMENT ID:2"
#: KAPITUS's 850.00 on the Tuesdays of March 2031 (the 4th, 11th, 18th and 25th).
MARCH = [(3, NW_MARCH, 30000.0)] + [(day, KAPITUS_BAKERY, -850.0) for day in (4, 11, 18, 25)]


def _months(march_rows, april_rows):
    from tests.test_package_matching import _closing, _payload

    march = _payload(sorted(march_rows, key=lambda row: row[0]), month=3, opening=5000.0)
    april = _payload(sorted(april_rows, key=lambda row: row[0]), month=4,
                     opening=_closing(sorted(march_rows, key=lambda row: row[0]), 5000.0))
    return march, april


def _numerators(*payloads):
    return [payload["metrics"]["withholding_numerator"] for payload in payloads]


def test_package_a_statement_s_returned_payment_re_debited_in_the_next_statement_leaves_the_numerator():
    """The return sits in March with its payment (rule D in March, the 28th's bounce of the 25th's payment); the funder
    re-debits it on Thursday April 3 (off its Tuesday cycle). March alone keeps it in its numerator; the package takes
    it out once."""
    from tests.test_package_matching import _package

    march, april = _months([*MARCH, (28, BARE_BOUNCE, 850.0)],
                           [(2, NW_APRIL, 30000.0), (3, KAPITUS_BAKERY, -850.0)]
                           + [(day, KAPITUS_BAKERY, -850.0) for day in (1, 8, 15, 22)])
    assert _numerators(march, april) == [3400.0, 4250.0]
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    assert (totals["withholding_numerator"], totals["lender_debits"]) == (6800.0, 6800.0)
    assert (totals["returned_funder_payment_total"], totals["returned_funder_payment_count"]) == (850.0, 1)
    assert totals["lenders_detected"] == 1
    [item] = package["returned_funder_payments"]
    assert (item["debit_date"], item["represented_date"], item["represented_kind"], item["represented_job"],
            item["represented_document"]) == ("2031-03-25", "2031-04-03", "re_presented", "apr", "apr.pdf")
    debit = next(row for row in package["transactions"] if row["source_job"] == "mar"
                 and row["date"] == "2031-03-25")["classification"]
    assert (debit["contributes_to_withholding_rate"], debit["represented_by"], debit["returned_funder_payment_by"]) == (
        False, item["represented_location"], item["credit_location"])
    # The package's lender evidence and the ledger's lender filter keep the returned row.
    assert any(record.get("represented_by") for record in package["lender_evidence"])
    # Each statement viewed alone keeps its own figures.
    assert _package(("mar", march))["totals"]["withholding_numerator"] == 3400.0


def test_package_a_payment_pass_4_matched_and_re_debited_leaves_the_numerator():
    """Pass 4 matches April 1's bare bounce to March 25's payment; the funder re-debits it on Thursday April 3."""
    from tests.test_package_matching import _package

    april_rows = [(1, BARE_BOUNCE, 850.0), (2, NW_APRIL, 30000.0), (3, KAPITUS_BAKERY, -850.0)] + [
        (day, KAPITUS_BAKERY, -850.0) for day in (8, 15, 22)]
    march, april = _months(MARCH, april_rows)
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    assert (totals["withholding_numerator"], totals["lender_debits"]) == (5950.0, 5950.0)
    [item] = package["returned_funder_payments"]
    assert item["cross_statement"] is True
    assert (item["represented_date"], item["represented_kind"], item["represented_document"]) == (
        "2031-04-03", "re_presented", "apr.pdf")


@needs_node
def test_package_the_ledger_note_of_a_payment_pass_4_matched_and_re_debited_counts_it_once():
    """Review round 1 of R3-B02 (finding 3): the package ledger's note on a payment pass 4 matched said "still in the
    withholding rate" after pass 5 took it out; it now says the rate counts it once, by its re-debit. A matched payment
    still standing reads as before."""
    from tests.test_package_matching import _package

    def debit_note(april_rows):
        march, april = _months(MARCH, april_rows)
        package = _package(("mar", march), ("apr", april))
        debit = next(row for row in package["transactions"] if row["source_job"] == "mar"
                     and row["date"] == "2031-03-25")
        return run_dashboard(f"console.log(JSON.stringify(packageMatchNotes({json.dumps(debit)})));")

    weekly = [(day, KAPITUS_BAKERY, -850.0) for day in (8, 15, 22)]
    assert debit_note([(1, BARE_BOUNCE, 850.0), (2, NW_APRIL, 30000.0), (3, KAPITUS_BAKERY, -850.0)] + weekly) == [
        "Returned unpaid on 2031-04-01 (apr.pdf): out of paid to lenders, counted once in the withholding rate, by its "
        "re-debit."]
    assert debit_note([(1, BARE_BOUNCE, 850.0), (2, NW_APRIL, 30000.0), (10, KAPITUS_BAKERY, -850.0)] + weekly) == [
        "Returned unpaid on 2031-04-01 (apr.pdf): out of paid to lenders, still in the withholding rate."]


def test_package_the_recurring_phase_guard_reads_every_return_of_the_members():
    """Review round 2 of R3-B02 (finding 3), across a member boundary: March 25's payment, returned on Friday the 28th,
    is re-presented on Friday April 4; in April the funder re-presents its two bounced Tuesday payments (the 8th and
    15th, returned on the Thursday after) on the Fridays the 11th and 18th. Those two Fridays follow April's returns,
    so they are no recurring phase: the package counts March 25's payment once. Each statement viewed alone keeps its
    own reading (April alone cannot see March's return, so its Friday the 4th reads as a schedule and its two returned
    payments stand)."""
    from tests.test_package_matching import _package

    march, april = _months([*MARCH, (28, BARE_BOUNCE, 850.0)],
                           [(2, NW_APRIL, 30000.0), (10, BARE_BOUNCE, 850.0), (17, BARE_BOUNCE, 850.0)]
                           + [(day, KAPITUS_BAKERY, -850.0) for day in (1, 4, 8, 11, 15, 18, 22)])
    assert _numerators(march, april) == [3400.0, 5950.0]
    package = _package(("mar", march), ("apr", april))
    assert (package["totals"]["withholding_numerator"], package["totals"]["lender_debits"]) == (8500.0, 6800.0)
    items = {item["debit_date"]: item for item in package["returned_funder_payments"]}
    assert sorted(items) == ["2031-03-25", "2031-04-08", "2031-04-15"]
    assert (items["2031-03-25"].get("represented_date"), items["2031-03-25"].get("represented_kind")) == (
        "2031-04-04", "re_presented")
    assert "represented_date" not in items["2031-04-08"] and "represented_date" not in items["2031-04-15"]


def test_package_a_re_debit_outside_the_gap_leaves_the_returned_payment_standing():
    from tests.test_package_matching import _package

    april_rows = [(1, BARE_BOUNCE, 850.0), (2, NW_APRIL, 30000.0), (10, KAPITUS_BAKERY, -850.0)] + [
        (day, KAPITUS_BAKERY, -850.0) for day in (8, 15, 22)]
    march, april = _months(MARCH, april_rows)
    package = _package(("mar", march), ("apr", april))
    assert package["totals"]["withholding_numerator"] == 6800.0
    [item] = package["returned_funder_payments"]
    assert "represented_date" not in item


# ---------------------------------------------------------------------------------------------- the dashboard

@needs_node
def test_the_dashboard_warns_re_presented_and_caught_up_payments_and_counts_them_once():
    items = [
        {"funder": "KAPITUS", "amount": 1000.0, "debit_date": "2054-03-13", "credit_date": "2054-03-15",
         "credit_description": BOFA_RETURN, "represented_date": "2054-03-16", "represented_kind": "re_presented"},
        {"funder": "KAPITUS", "amount": 250.0, "debit_date": "2054-03-05", "credit_date": "2054-03-06",
         "credit_description": BOFA_RETURN, "represented_date": "2054-03-06", "represented_kind": "caught_up"},
        {"funder": "KAPITUS", "amount": 850.0, "debit_date": "2031-03-25", "credit_date": "2031-03-28",
         "credit_description": BARE_BOUNCE, "represented_date": "2031-04-03", "represented_kind": "re_presented",
         "represented_document": "apr.pdf", "represented_job": "apr", "source_job": "mar", "source_document": "mar.pdf",
         "source_currency": "USD"},
        {"funder": "KAPITUS", "amount": 850.0, "debit_date": "2054-03-13", "credit_date": "2054-03-15",
         "credit_description": BOFA_RETURN},
    ]
    metrics = {"lender_debits": 4000, "withholding_numerator": 4850, "withholding_denominator": 24000,
               "withholding_denominator_label": "True revenue", "returned_funder_payment_total": 1850,
               "returned_funder_payment_count": 2}
    rows = [{"amount": -1000, "classification": {"returned_funder_payment_by": "transaction:4",
                                                 "contributes_to_withholding_rate": False}},
            {"amount": -1000, "classification": {"contributes_to_withholding_rate": True}},
            {"amount": -1000, "classification": {"contributes_to_withholding_rate": False}}]
    result = run_dashboard(f"""
const items = {json.dumps(items)};
const rows = {json.dumps(rows)};
console.log(JSON.stringify({{warnings: items.map((item) => returnedFunderPaymentWarning(item, 'USD')),
  audit: withholdingAuditNote({json.dumps(metrics)}, 'USD'),
  lender: filterTransactions(rows, 'lender').map((tx) => rows.indexOf(tx))}}));
""")
    assert result["warnings"] == [
        'Returned funder payment: KAPITUS $1,000.00 debited 2054-03-13, returned 2054-03-15 ("RETURN OF POSTED CHECK '
        'ITEM"), re-presented on 2054-03-16. Not counted as paid; counted once in the withholding rate, by the '
        're-presented payment.',
        'Returned funder payment: KAPITUS $250.00 debited 2054-03-05, returned 2054-03-06 ("RETURN OF POSTED CHECK '
        'ITEM"), caught up on 2054-03-06, 2x. Not counted as paid; counted once in the withholding rate, by the '
        'catch-up.',
        'Returned funder payment: KAPITUS $850.00 debited 2031-03-25, returned 2031-03-28 ("ACH RETURN ITEM NSF"), '
        're-presented on 2031-04-03 (apr.pdf). Not counted as paid; counted once in the withholding rate, by the '
        're-presented payment.',
        'Returned funder payment: KAPITUS $850.00 debited 2054-03-13, returned 2054-03-15 ("RETURN OF POSTED CHECK '
        'ITEM"). Not counted as paid; still in the withholding rate.',
    ]
    assert result["audit"] == ("$4,850.00 confirmed lender debits (incl. $850.00 returned unpaid; $1,000.00 returned "
                               "and re-debited, counted once) divided by $24,000.00 true revenue")
    # The lender filter keeps a returned row whose re-debit took it out of the rate.
    assert result["lender"] == [0, 1]


# ---------------------------------------------------------------------------------------------- G7

def _g7_account(*, withholding, represented=(), numerator, dates=True, state_of_redebit="confirmed_lender",
                entity_of_redebit="Quillon Funding"):
    """A five-row account: Quillon Funding paid rows 1 and 4, row 2 returned by the credit at row 3 (transaction:4)."""
    states = ["other", "confirmed_lender", "confirmed_lender", "other", state_of_redebit]
    account = {
        "rows": 5, "states": states, "flagged": {}, "lender_debits": 200.0, "eligible_deposits": 1000.0,
        "withholding_rate": 10.0,
        "lenders": [[1, "Quillon Funding", "QUILLON FUNDING"]]
        + ([[4, entity_of_redebit, entity_of_redebit.upper()]] if state_of_redebit == "confirmed_lender" else []),
        "withholding_rows": list(withholding), "withholding_numerator": numerator,
        "lender_count_entities": ["Quillon Funding"], "returned_funder_rows": [[2, "transaction:4"]],
        "represented_rows": [list(row) for row in represented],
        "potential_lender_rows": [], "potential_withholding_rows": [], "reversed_by": [],
        "row_entities": {"1": "Quillon Funding", "2": "Quillon Funding", "4": entity_of_redebit},
        "zelle_policy_rows": [],
    }
    if dates:
        account["row_dates"] = ["2054-03-01", "2054-03-06", "2054-03-13", "2054-03-15", "2054-03-16"]
    return account


def _g7(before, after):
    return ({"classification_version": "5.7", "accounts": {"s1:0": before}},
            {"classification_version": "5.7", "accounts": {"s1:0": after}})


def _g7_exit(tmp_path, before, after):
    from tests.test_lender_census import _compare_argv, _files, _ledger
    from tools import lender_census as census

    return census.main(_compare_argv(_files(tmp_path, before, after, _ledger()), tmp_path))


def test_g7_declares_a_re_debited_returned_row_leaving_the_numerator(tmp_path):
    from tools import lender_census as census

    before, after = _g7(_g7_account(withholding=(1, 2, 4), numerator=300.0),
                        _g7_account(withholding=(1, 4), represented=[(2, "transaction:5")], numerator=200.0))
    report = census.compare(before, after, admitted=frozenset())
    assert report["returned_funder_represented"] == {"analyses": 1, "rows": 1}
    assert report["returned_rows_leaving_withholding"] == {"analyses": 0, "rows": 0}
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert report["withholding_numerator"] == {"down": 1}
    assert _g7_exit(tmp_path, before, after) == 0


@pytest.mark.parametrize("change", ["no_entry", "another_entity", "not_a_lender_row", "dated_before_the_return",
                                    "no_dates", "the_return_itself"])
def test_g7_fails_any_other_returned_row_leaving_the_numerator(tmp_path, change):
    from tools import lender_census as census

    kwargs = {"withholding": (1, 4), "represented": [(2, "transaction:5")], "numerator": 200.0}
    if change == "no_entry":
        kwargs["represented"] = []
    elif change == "another_entity":
        kwargs["entity_of_redebit"] = "Brambleway Capital"
    elif change == "not_a_lender_row":
        kwargs["state_of_redebit"] = "other"
    elif change == "no_dates":
        kwargs["dates"] = False
    elif change == "the_return_itself":
        kwargs["represented"] = [(2, "transaction:4")]
    after_account = _g7_account(**kwargs)
    if change == "dated_before_the_return":
        after_account["row_dates"] = ["2054-03-01", "2054-03-06", "2054-03-13", "2054-03-15", "2054-03-14"]
    before_account = _g7_account(withholding=(1, 2, 4), numerator=300.0, dates=change != "no_dates")
    before, after = _g7(before_account, after_account)
    report = census.compare(before, after, admitted=frozenset(), allowlisted=frozenset({"Quillon Funding"}))
    assert report["returned_funder_represented"] == {"analyses": 0, "rows": 0}
    assert report["returned_rows_leaving_withholding"] == {"analyses": 1, "rows": 1}
    assert _g7_exit(tmp_path, before, after) == 1


def test_g7_the_snapshot_records_the_represented_rows(tmp_path, fake_payees):  # noqa: F811
    from tools import lender_census as census
    from webapp.artifact_cache import ArtifactCache
    from tests.test_lender_census import _row

    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("f" * 64, "settings", {"statement": {"bank": "Bank of America", "transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        *[_row(f"2054-01-{day:02d}", "ACH DEBIT FABRICATED LENDER 0001", -1000.0) for day in (5, 12)],
        _row("2054-01-14", "RETURN OF POSTED CHECK ITEM", 1000.0),
        *[_row(f"2054-01-{day:02d}", "ACH DEBIT FABRICATED LENDER 0001", -1000.0) for day in (15, 19, 26)],
    ]}})
    account = census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"]["f" * 64 + ":0"]
    assert account["returned_funder_rows"] == [[2, "transaction:4"]]
    assert account["represented_rows"] == [[2, "transaction:5"]]
    assert 2 not in account["withholding_rows"]
    assert account["withholding_numerator"] == account["lender_debits"] == 4000.0


from tests.flag_group_fixtures import fake_payees  # noqa: E402,F401  (fixture)
