"""The owner's request of 2026-10-06 (lender payment changes; true revenue spec §10.1; R2-OW18, part G): the lender
table's warning lines, the not-checked lines, the statement modal and the copied summaries, driven in node through
the whole webapp/static/app.js (tests/webapp_js_harness.py). The items are the module's and the package's own, built
from fabricated rows (tests/test_lender_payment_changes.py, tests/test_lender_payment_changes_package.py)."""
from __future__ import annotations

import json

import pytest

from tests.webapp_js_harness import NODE, run_dashboard
from tests import test_lender_payment_changes as pure
from tests import test_lender_payment_changes_package as pkg

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

M, A, Y, F, J = pure.M, pure.A, pure.Y, pure.F, pure.J


def warning_texts(items, currency="USD"):
    """lenderPaymentChangeWarning and lenderPaymentChangeChip of each item, in node."""
    return run_dashboard(f"""
const items = {json.dumps(items)};
console.log(JSON.stringify(items.map((item) => [lenderPaymentChangeWarning(item, {json.dumps(currency)}),
                                                lenderPaymentChangeChip(item)])));
""")


def warning_text(item, currency="USD"):
    return warning_texts([item], currency)[0][0]


def _chip(glyph, text, tone):
    tones = {"amber": "chip-amber", "blue": "chip-blue", "neutral": "chip-neutral", "violet": "chip-violet",
             "green": "chip-green"}
    return (f'<span class="glass-chip {tones[tone]}"><span class="chip-glyph" aria-hidden="true">{glyph}</span>'
            f'<span class="chip-text">{text}</span></span>')


def chip_html(glyph, text, tone):
    return run_dashboard(f"console.log(JSON.stringify(glassChip({json.dumps(glyph)}, {json.dumps(text)}, "
                         f"{json.dumps(tone)})));")


L1 = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._rows(pure.bdays(M(16), M(25)), 600))
L8 = pure.only(pure._rows(pure.bdays(M(2), M(20)), 500) + pure._rows(pure.every(M(23), A(13)), 2500), end=A(17))
L9 = pure.only(pure._rows(pure.bdays(M(2), M(20)), 500) + pure._rows(pure.every(M(23), A(13)), 1500), end=A(17))
L10B = pure.only(pure._rows(pure.every(M(2), A(27)), 1000) + pure._rows(pure.every(M(18), A(29)), 2100), end=A(30))
L16 = pure.only(pure._rows(pure.every(A(1), Y(13)), 1000), start=A(1), end=Y(29))
L20 = pure.only(pure._rows([F(2), M(2), A(2)], 2000) + pure._rows([A(20)], 5000), start=F(1), end=J(30))
L21 = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._rows(pure.bdays(M(17), M(31)), 860, entity="ONDECK"))
L21_NEW = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850)
                    + pure._rows(pure.bdays(M(17), M(31)), 1000, entity="ONDECK"))
L21_RELIEF = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + [pure._relief(M(18)), pure._relief(M(25))])
L23 = pure.only(pure._rows(pure.every(M(2), M(30)), 1000) + pure._rows(pure.every(M(18), A(29)), 1200), end=A(30))
L31 = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._rows([M(16)], 400) + pure._rows([M(17)], 300)
                + pure._rows([M(19)], 500))
L32 = pure.only(pure._rows(pure.bdays(M(2), M(6)) + pure.bdays(M(16), M(31)), 850))
ATTEMPT = pure.only(pure._rows(pure.every(M(4), A(1)), 1000)
                    + pure._rows([A(8)], 1000, returned_funder_payment_by="transaction:99"), end=Y(1))
POTENTIAL = pure.only(pure._potential(pure.bdays(M(2), M(13)), 300, label=f"{pure.UNNAMED} (daily, 300.00)")
                      + pure._potential(pure.bdays(M(16), M(25)), 250, label=f"{pure.UNNAMED} (daily, 250.00)"))
POTENTIAL_STOP = pure.only(pure._potential(pure.bdays(Y(1), Y(20)), 300, label=f"{pure.UNNAMED} (daily, 300.00)"),
                           start=Y(1), end=Y(29))
POSSIBLE = pure.only(pure._rows(pure.bdays(M(2), M(20)), 500) + pure._rows([M(23), M(30)], 1600))
STEPS = pure.only(pure._rows(pure.every(M(2), M(23)), 1000) + pure._rows(pure.every(M(30), A(20)), 950)
                  + pure._rows(pure.every(A(27), Y(18)), 880), end=Y(20))


# ------------------------------------------------------------------------------------------------ U1-U4, U11, U12
@needs_node
def test_u1_to_u4_the_lines():
    march, april = pkg.p1()
    p1 = pkg.package(pkg.job("march", march), pkg.job("april", april))["lender_payment_changes"][0]
    p4 = pkg.package(*(pkg.job(name, payload) for name, payload in zip(("march", "april", "may"), pkg.p4())))
    p4 = p4["lender_payment_changes"][0]
    texts = warning_texts([L1, p1, L8, L9, L16, p4, L31, L32, L10B, POTENTIAL, POSSIBLE, STEPS])
    lines = [text for text, _chip_html in texts]
    assert lines[0] == ("Payment decreased: KAPITUS daily $850.00 → $600.00 (-29%) from 2054-03-16; 8 payments at the "
                        "new amount, after 10 at the old.")
    assert lines[1] == ("Payment decreased: KAPITUS weekly $1,000.00 → $700.00 (-30%) from 2054-04-01; 4 payments at "
                        "the new amount, after 4 at the old (march.pdf → april.pdf).")
    assert lines[2] == ("Payment schedule changed: KAPITUS daily $500.00 → weekly $2,500.00 from 2054-03-23 (weekly "
                        "equivalent $2,500.00 → $2,500.00, 0%: no decrease); 4 payments on the new schedule, after 15 "
                        "on the old.")
    assert lines[3] == ("Payment decreased: KAPITUS daily $500.00 → weekly $1,500.00 (weekly equivalent $2,500.00 → "
                        "$1,500.00, -40%) from 2054-03-23; 4 payments at the new amount, after 15 at the old.")
    assert lines[4] == ("Possible stop: no payment to KAPITUS in the last 11 business days of the statement (weekly; "
                        "last payment $1,000.00 on 2054-05-13; more than 10 business days without a payment, two "
                        "missed weekly payments).")
    assert lines[5] == ("No payment to KAPITUS since 2054-04-29 (weekly; last payment $1,000.00; 21 business days "
                        "through 2054-05-29) (april.pdf).")
    assert lines[6] == ("Possible stop: no regular $850.00 payment to KAPITUS since 2054-03-13; 3 later debits at "
                        "other amounts, the last on 2054-03-19 (daily; last payment $850.00 on 2054-03-13; more than "
                        "5 business days without a payment).")
    assert lines[7] == ("Payments paused: no payment to KAPITUS between 2054-03-06 and 2054-03-16 (6 business days; "
                        "daily, grace 5), then resumed at the same daily $850.00.")
    assert lines[8] == ("New payment stream: KAPITUS weekly $2,100.00 from 2054-03-18, alongside weekly $1,000.00 "
                        "(weekly total $1,000.00 → $3,100.00, +210%; payment stream 2 of 2).")
    assert lines[9] == ("Payment decreased (potential lender): Unidentified lender obligation (daily, 300.00) daily "
                        "$300.00 → $250.00 (-17%) from 2054-03-16; 8 payments at the new amount, after 10 at the old.")
    # § Still open 18's alternative and § Still open 23's alternative (the orchestrator's choices of 2026-10-06).
    assert lines[10] == ("Possible payment decrease: KAPITUS daily $500.00 → weekly $1,600.00 (weekly equivalent "
                         "$2,500.00 → $1,600.00, -36%) from 2054-03-23; 2 payments at the new amount, after 15 at the "
                         "old; new schedule not yet confirmed.")
    # R2-OW18 review round 1: the unreported levels with the step into each, then the last step.
    assert lines[11] == ("Payment decreased: KAPITUS weekly $1,000.00 → $880.00 (-12%) from 2054-04-27; 4 payments at "
                         "the new amount, after 4 at the old; via weekly $950.00 (-5%), then weekly $880.00 (-7%).")
    chips = [chip for _text, chip in texts]
    assert chips[0] == chips[1] == chip_html("↓", "Decreased", "amber")
    assert chips[2] == chip_html("↻", "Schedule", "blue")
    assert chips[4] == chips[6] == chip_html("■", "Possible stop", "amber")
    assert chips[5] == chip_html("■", "No payments", "amber")
    assert chips[7] == chip_html("‖", "Paused", "amber")
    assert chips[8] == chip_html("+", "New stream", "blue")
    assert chips[10] == chip_html("↓", "Possible decrease", "amber")


@needs_node
def test_u4_the_stop_suffixes():
    increase = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._rows(pure.bdays(M(16), M(25)), 1050)
                         + [pure._credit(M(13), 25000)])
    p6b = pkg.p6b()["lender_payment_changes"][0]
    texts = [text for text, _chip in warning_texts([L20, L21, L21_NEW, L21_RELIEF, L23, p6b, ATTEMPT, increase])]
    assert texts[0].endswith("; a final debit of $5,000.00 on 2054-04-20 (possible payoff).")
    assert texts[1].endswith("; payments of $860.00 continue as ONDECK from 2054-03-17 (possible buyout or refinance).")
    assert texts[2].endswith("; a new lender series starts: ONDECK daily $1,000.00 from 2054-03-17.")
    assert texts[3].endswith("; a debt relief program's payments start on 2054-03-18 (possible default or settlement).")
    assert texts[4] == ("Possible stop: no payment to KAPITUS (payment stream 1 of 2) in the last 23 business days of "
                        "the statement (weekly; last payment $1,000.00 on 2054-03-30; more than 10 business days "
                        "without a payment, two missed weekly payments); another KAPITUS payment stream continues "
                        "($1,200.00 weekly).")
    assert texts[5].endswith("; payments to KAPITUS continue from another account (b-april.pdf) from 2054-04-15 at "
                             "$1,000.00 (a-april.pdf).")
    assert texts[5].startswith("Possible stop: no payment to KAPITUS in the last ")
    assert "through 2054-05-29" in texts[5]
    assert texts[6].endswith("; the last attempt, on 2054-04-08, was returned unpaid.")
    assert texts[7].endswith("; after a new funding from KAPITUS of $25,000.00 on 2054-03-13 (renewal?).")


@needs_node
def test_u4_the_change_suffixes():
    cut = pure._rows(pure.bdays(M(2), M(11)), 850) + pure._rows(pure.bdays(M(12), M(18)), 600)
    decrease, increase = pure.changes(cut + pure._rows(pure.bdays(M(19), M(26)), 850))
    restart = pure.only(pure._rows(pure.every(M(2), M(23)), 1000) + pure._rows(pure.every(A(20), Y(4)), 700), end=Y(8))
    texts = [text for text, _chip in warning_texts([decrease, increase, restart])]
    assert texts[0].endswith("; temporary: back to $850.00 from 2054-03-19.")
    assert texts[1].endswith("; back to the earlier $850.00 payment.")
    assert texts[2].endswith("; after a pause of 20 business days.")


# ------------------------------------------------------------------- R2-OW18 review round 1 (fabricated rows only)
@needs_node
def test_r1_an_abrupt_cut_after_a_drift_names_its_last_step():
    abrupt = pure.only(pure._rows(pure.every(M(2), M(16)), 1000) + pure._rows(pure.every(M(23), A(6)), 950)
                       + pure._rows(pure.every(A(13), A(27)), 650), end=A(30))
    possible, change = pure.changes(pure._rows(pure.bdays(M(2), M(13)), 500) + pure._rows([M(16), M(23)], 1600)
                                    + pure._rows([M(30), A(6), A(13)], 2300), end=A(17))
    older = {**abrupt, "via": [{"amount": 950.0, "cadence": "weekly"}]}
    older.pop("last_step_percent")
    texts = [text for text, _chip in warning_texts([abrupt, possible, change, older])]
    assert texts[0] == ("Payment decreased: KAPITUS weekly $1,000.00 → $650.00 (-35%) from 2054-04-13; 3 payments at "
                        "the new amount, after 3 at the old; via weekly $950.00 (-5%), then weekly $650.00 (-32%).")
    assert texts[1] == ("Possible payment decrease: KAPITUS daily $500.00 → weekly $1,600.00 (weekly equivalent "
                        "$2,500.00 → $1,600.00, -36%) from 2054-03-16; 2 payments at the new amount, after 10 at the "
                        "old; new schedule not yet confirmed.")
    assert texts[2] == ("Payment schedule changed: KAPITUS daily $500.00 → weekly $2,300.00 from 2054-03-30 (weekly "
                        "equivalent $2,500.00 → $2,300.00, -8%: no decrease); 3 payments on the new schedule, after 10 "
                        "on the old; via weekly $1,600.00 (-36%), then weekly $2,300.00 (+44%).")
    # An item stored without the step fields names its levels alone; no line claims the steps' size.
    assert texts[3].endswith("; via weekly $950.00.")
    assert not any("under 10%" in text for text in texts)


@needs_node
def test_r1_a_pause_or_a_stop_whose_presence_is_an_attempt_says_so():
    regular = pure._rows(pure.bdays(M(2), M(6)) + pure.bdays(M(23), M(31)), 850)
    attempt = pure.only(regular + pure._rows([M(16)], 850, returned_funder_payment_by="transaction:99"))
    other = pure.only(regular + pure._rows([M(16)], 425))
    march = pure._rows(pure.every(M(4), M(18)), 1000) + pure._rows([M(25)], 1000,
                                                                    returned_funder_payment_by="transaction:99")
    [stop] = pure._chain((march, M(1), M(31)), ([], A(1), A(30)))
    stop = {**pure.lpc.public_item(stop), "source_document": "april.pdf"}
    texts = [text for text, _chip in warning_texts([attempt, other, stop, ATTEMPT, L32])]
    assert texts[0] == ("Payments paused: no payment or payment attempt to KAPITUS between 2054-03-06 and 2054-03-16 "
                        "(6 business days; daily, grace 5); the attempt on 2054-03-16 was returned unpaid, and payments "
                        "resumed at the same daily $850.00 on 2054-03-23.")
    assert texts[1] == ("Payments paused: no payment to KAPITUS between 2054-03-06 and 2054-03-16 (6 business days; "
                        "daily, grace 5); a payment at another amount on 2054-03-16, and payments resumed at the same "
                        "daily $850.00 on 2054-03-23.")
    assert stop["stop_confirmed"] is True
    assert texts[2] == (f"No payment or payment attempt to KAPITUS since 2054-03-25 (weekly; last payment $1,000.00 on "
                        f"2054-03-18; {stop['quiet_business_days']} business days through 2054-04-30); the last "
                        f"attempt, on 2054-03-25, was returned unpaid (april.pdf).")
    assert texts[3] == (f"Possible stop: no payment or payment attempt to KAPITUS in the last "
                        f"{ATTEMPT['quiet_business_days']} business days of the statement (weekly; last payment "
                        f"$1,000.00 on 2054-04-01; more than 10 business days without a payment, two missed weekly "
                        f"payments); the last attempt, on 2054-04-08, was returned unpaid.")
    # The regime's own payment ends L32's pause: the line as before.
    assert texts[4] == ("Payments paused: no payment to KAPITUS between 2054-03-06 and 2054-03-16 (6 business days; "
                        "daily, grace 5), then resumed at the same daily $850.00.")


@needs_node
def test_u11_u12_the_tones():
    texts = warning_texts([L32, L10B, POTENTIAL, POTENTIAL_STOP, L1])
    assert texts[0][1] == chip_html("‖", "Paused", "amber") and texts[1][1] == chip_html("+", "New stream", "blue")
    assert texts[2][1] == chip_html("↓", "Decreased", "neutral")
    assert texts[3][1] == chip_html("■", "Possible stop", "neutral")
    assert texts[3][0].startswith("Possible stop: no payment to potential lender Unidentified lender obligation "
                                  "(daily, 300.00) in the last 6 business days of the statement (daily;")
    assert texts[4][1] == chip_html("↓", "Decreased", "amber")


# ------------------------------------------------------- audit round 3, R3-B04 (fabricated rows only): the lines
@needs_node
def test_r3_b04_the_lines_of_a_slower_triple_and_of_a_restoration_read_through_bounced_attempts():
    # R3-70: daily 500 -> weekly 1,500 held 2 is § Still open 18's possible change, no longer a catch-up.
    slower = pure.only(pure._rows(pure.bdays(M(2), M(20)), 500) + pure._rows([M(23), M(30)], 1500))
    # R3-23: a cut and a restoration paid only on Wednesdays, the other days returned unpaid.
    decrease, increase = pure.changes(
        pure._rows(pure.bdays(M(2), M(27)), 850) + pure._rows(pure.bdays(M(30), A(10)), 340)
        + pure._split(pure.bdays(A(13), Y(8)), 850, pure._wednesdays), end=Y(8))
    texts = warning_texts([slower, decrease, increase])
    assert texts[0] == [
        "Possible payment decrease: KAPITUS daily $500.00 → weekly $1,500.00 (weekly equivalent $2,500.00 → "
        "$1,500.00, -40%) from 2054-03-23; 2 payments at the new amount, after 15 at the old; new schedule not yet "
        "confirmed.", chip_html("↓", "Possible decrease", "amber")]
    assert texts[1][0] == ("Payment decreased: KAPITUS daily $850.00 → $340.00 (-60%) from 2054-03-30; 10 payments at "
                           "the new amount, after 20 at the old; temporary: back to $850.00 from 2054-04-15.")
    assert texts[2][0] == ("Payment increased: KAPITUS daily $340.00 → $850.00 (+150%) from 2054-04-15; 4 payments at "
                           "the new amount, after 10 at the old; back to the earlier $850.00 payment.")


# ------------------------- audit round 3, R3-B05 (R3-25, R3-84; the owner's answer of 2026-10-07; fabricated rows only)
def _r3_b05_items():
    """The batch's fabricated items, built when a test runs."""
    gap = pure.bdays(M(2), M(6)) + pure.bdays(M(23), M(31))
    label = f"{pure.UNNAMED} (daily, 300.00)"
    return {
        "catch_up_pause": pure.only(pure._rows(gap, 300) + pure._rows([M(16)], 1800)),
        "larger_pause": pure.only(pure._rows(gap, 300) + pure._rows([M(16)], 1300)),
        "catch_up_stop": pure.only(pure._rows([F(13), M(13), A(13)], 1000) + pure._rows([Y(13)], 2000)
                                   + pure._rows([J(12)], 3000), start=F(1), end=pure.date(2054, 8, 31)),
        "earlier_payoff": pure.only(pure._rows([F(2), M(2), A(2)], 2000) + pure._rows([A(10)], 4500)
                                    + pure._rows([A(20)], 5000), start=F(1), end=J(30)),
        "caught_up": pure.only(pure._rows(pure.bdays(M(2), M(13)) + pure.bdays(M(19), M(31)), 850)
                               + pure._rows([M(18)], 1700)),
        "caught_up_weekly": pure.only(pure._rows(pure.every(M(3), M(17)) + pure.every(M(31), Y(26)), 1000)
                                      + pure._rows([M(27)], 3000), end=Y(29)),
        "caught_up_potential": pure.only(pure._potential(pure.bdays(M(2), M(13)) + pure.bdays(M(18), M(31)), 300,
                                                         label=label) + pure._potential([M(17)], 600, label=label)),
        "same_amount_stop": pure.only(pure._rows(pure.bdays(M(2), M(13)), 850)
                                      + pure._other(pure.bdays(M(16), M(31)), 850)),
    }


@needs_node
def test_r3_b05_the_pause_and_stop_lines_name_catch_ups_and_larger_debits():
    items = _r3_b05_items()
    after = pure.only(pure._rows(pure.bdays(M(2), M(13)), 850) + pure._rows([M(17)], 1700))
    two_earlier = {**items["earlier_payoff"], "payoff": {**items["earlier_payoff"]["payoff"], "earlier": 2}}
    texts = warning_texts([items["catch_up_pause"], items["larger_pause"], items["catch_up_stop"],
                           items["earlier_payoff"], after, two_earlier])
    assert texts[0] == [
        "Payments paused: no payment to KAPITUS between 2054-03-06 and 2054-03-16 (6 business days; daily, grace 5); a "
        "debit of $1,800.00 (6 times the payment) on 2054-03-16 (possible catch-up), and payments resumed at the same "
        "daily $300.00 on 2054-03-23.", chip_html("‖", "Paused", "amber")]
    assert texts[1][0] == (
        "Payments paused: no payment to KAPITUS between 2054-03-06 and 2054-03-23 (11 business days; daily, grace 5), "
        "then resumed at the same daily $300.00; a debit of $1,300.00 on 2054-03-16 inside the gap, more than twice "
        "the payment.")
    assert ("; 2 later debits at other amounts, the last on 2054-06-12 (2 of them exact multiples of the payment: "
            "possible catch-up)") in texts[2][0]
    assert "possible payoff" not in texts[2][0]
    assert texts[3][0].endswith("; a final debit of $5,000.00 on 2054-04-20 (possible payoff; 1 earlier debit of twice "
                                "the payment or more).")
    assert ("; 1 later debit at other amounts, the last on 2054-03-17 (1 of them an exact multiple of the payment: "
            "possible catch-up)") in texts[4][0]
    assert texts[5][0].endswith("(possible payoff; 2 earlier debits of twice the payment or more).")
    # A payoff with no earlier one reads as before (L20).
    assert warning_text(L20).endswith("; a final debit of $5,000.00 on 2054-04-20 (possible payoff).")


@needs_node
def test_r3_b05_the_caught_up_line():
    march = pure._rows(pure.bdays(M(2), M(27)), 850)
    april = pure._rows([A(2)], 1700) + pure._rows(pure.bdays(A(3), A(30)), 850)
    [chained] = pure._chain((march, M(1), M(31)), (april, A(1), A(30)))
    chained = {**pure.lpc.public_item(chained), "source_document": "april.pdf"}
    items = _r3_b05_items()
    caught_up, weekly, potential = items["caught_up"], items["caught_up_weekly"], items["caught_up_potential"]
    texts = warning_texts([caught_up, weekly, potential, chained])
    assert texts[0] == [
        "Caught up: no payment to KAPITUS on 2 scheduled daily payments (2054-03-16 to 2054-03-17), then $1,700.00 on "
        "2054-03-18 (2x the daily $850.00).", chip_html("↺", "Caught up", "amber")]
    assert texts[1][0] == ("Caught up: no payment to KAPITUS on 1 scheduled weekly payment (2054-03-24), then "
                           "$3,000.00 on 2054-03-27 (3x the weekly $1,000.00).")
    assert texts[2] == [
        "Caught up (potential lender): no payment to Unidentified lender obligation (daily, 300.00) on 1 scheduled "
        "daily payment (2054-03-16), then $600.00 on 2054-03-17 (2x the daily $300.00).",
        chip_html("↺", "Caught up", "neutral")]
    assert texts[3][0] == ("Caught up: no payment to KAPITUS on 3 scheduled daily payments (2054-03-30 to 2054-04-01), "
                           "then $1,700.00 on 2054-04-02 (2x the daily $850.00) (april.pdf).")
    # A weekly triple after two missed weeks: its pause line carries the catch-up, the one line for the gap.
    [pause] = pure.changes(pure._rows(pure.every(M(3), M(17)) + pure.every(A(14), Y(26)), 1000)
                           + pure._rows([A(7)], 3000), end=Y(29))
    assert warning_text(pause) == (
        "Payments paused: no payment to KAPITUS between 2054-03-17 and 2054-04-07 (15 business days; weekly, grace "
        "10); a debit of $3,000.00 (3 times the payment) on 2054-04-07 (possible catch-up), and payments resumed at "
        "the same weekly $1,000.00 on 2054-04-14.")
    sentence = run_dashboard(f"""
console.log(JSON.stringify([lenderPaymentChangesSummary({json.dumps([caught_up, items["catch_up_pause"]])}),
                            lenderPaymentChangesSummary({json.dumps([caught_up, weekly, potential])})]));
""")
    assert sentence == ["Lender payment changes: 1 pause, 1 catch-up.",
                        "Lender payment changes: 3 catch-ups (1 potential)."]


@needs_node
def test_r3_b05_r1_a_pause_names_a_catch_up_before_payments_resumed():
    """Audit round 3, R3-B05, review round 1 (finding 2): a bounced attempt or a payment at another amount ends the
    pause and a catch-up follows before payments resume: the pause line names it (one line per event)."""
    gap = pure.bdays(M(2), M(6)) + pure.bdays(M(18), M(31))
    attempt = pure._rows([M(16)], 850, returned_funder_payment_by="transaction:99")
    [after_attempt] = pure.changes(pure._rows(gap, 850) + attempt + pure._rows([M(17)], 1700))
    [after_one_off] = pure.changes(pure._rows(gap, 850) + pure._rows([M(16)], 500) + pure._rows([M(17)], 2550))
    texts = warning_texts([after_attempt, after_one_off])
    assert texts[0] == [
        "Payments paused: no payment or payment attempt to KAPITUS between 2054-03-06 and 2054-03-16 (6 business days; "
        "daily, grace 5); the attempt on 2054-03-16 was returned unpaid, and payments resumed at the same daily "
        "$850.00 on 2054-03-18; a debit of $1,700.00 (2 times the payment) on 2054-03-17 before payments resumed "
        "(possible catch-up).", chip_html("‖", "Paused", "amber")]
    assert texts[1][0] == (
        "Payments paused: no payment to KAPITUS between 2054-03-06 and 2054-03-16 (6 business days; daily, grace 5); "
        "a payment at another amount on 2054-03-16, and payments resumed at the same daily $850.00 on 2054-03-18; a "
        "debit of $2,550.00 (3 times the payment) on 2054-03-17 before payments resumed (possible catch-up).")


@needs_node
def test_r3_b05_the_same_amount_note_and_a_stop_it_never_confirms():
    march = pure._rows(pure.bdays(M(2), M(13)), 850) + pure._other(pure.bdays(M(16), M(31)), 850)
    [stop] = pure._chain((march, M(1), M(31)), (pure._other(pure.bdays(A(1), A(30)), 850), A(1), A(30)))
    stop = {**pure.lpc.public_item(stop), "source_document": "march.pdf"}
    [pause] = pure._chain((march, M(1), M(31)), (pure._rows(pure.bdays(A(1), A(30)), 850), A(1), A(30)))
    pause = {**pure.lpc.public_item(pause), "source_document": "april.pdf"}
    texts = warning_texts([_r3_b05_items()["same_amount_stop"], stop, pause])
    assert texts[0][0].endswith("; 12 debits of exactly $850.00 on the same daily schedule under another description, "
                                "from 2054-03-16 to 2054-03-31 (possible collection under another name).")
    assert texts[0][0].startswith("Possible stop: no payment to KAPITUS in the last 12 business days of the statement")
    assert texts[0][1] == chip_html("■", "Possible stop", "amber")
    assert stop["stop_confirmed"] is False
    assert texts[1][0].startswith("Possible stop: no payment to KAPITUS in the last ")
    assert texts[1][0].endswith("; 34 debits of exactly $850.00 on the same daily schedule under another description, "
                                "from 2054-03-16 to 2054-04-30 (possible collection under another name) (march.pdf).")
    assert texts[1][1] == chip_html("■", "Possible stop", "amber")
    assert texts[2][0] == (
        "Payments paused: no payment to KAPITUS between 2054-03-13 and 2054-04-01 (13 business days; daily, grace 5), "
        "then resumed at the same daily $850.00; 12 debits of exactly $850.00 on the same daily schedule under another "
        "description, from 2054-03-16 to 2054-03-31 (possible collection under another name) (april.pdf).")


# ------------------------------------------------------------------------------------- U5, U6, U7, U10: the table
def _table(call):
    return run_dashboard(f"""
{call}
console.log(JSON.stringify(els.lenderTable.innerHTML));
""")


FUNDER = {"funder": "KAPITUS", "debit_count": 18, "total_debited": 13300.0, "transactions": [], "evidence": []}
STATEMENT_TEXT = "Payment changes not checked: this statement was analysed before the check. Re-analyze to see them."
PACKAGE_TEXT = "Payment changes not checked: no statement of this package has been checked yet."


@needs_node
def test_u5_not_computed_is_never_no_change():
    funders = json.dumps([FUNDER])
    html = _table(f"renderLenders({funders}, [], 'USD', [], undefined);")
    assert STATEMENT_TEXT in html and "Not checked" in html
    assert "Payment changes" not in _table(f"renderLenders({funders}, [], 'USD', [], []);")
    assert "Payment changes" not in _table("renderLenders([], [], 'USD', [], undefined);")
    html = _table(f"renderLenders({funders}, [], 'USD', [], undefined, [], true);")
    assert PACKAGE_TEXT in html and STATEMENT_TEXT not in html


@needs_node
def test_u6_lines_render_above_no_lenders_detected():
    returned = {"funder": "KAPITUS", "amount": 850.0, "debit_date": "2054-03-03", "credit_date": "2054-03-05",
                "credit_description": "RETURN OF POSTED CHECK ITEM"}
    html = _table(f"renderLenders([], [], 'USD', {json.dumps([returned])}, {json.dumps([L16])});")
    assert html.index("Returned funder payment: KAPITUS") < html.index("Possible stop: no payment to KAPITUS") < (
        html.index("No lenders detected"))


@needs_node
def test_u7_a_cad_item_prints_cad_money():
    item = {**L1, "scope": "package", "source_currency": "CAD", "source_document": "td.pdf", "cross_statement": False}
    assert warning_text(item, None).startswith("Payment decreased: KAPITUS daily CA$850.00 → CA$600.00 (-29%)")


@needs_node
def test_u10_the_package_s_unchecked_line():
    unchecked = [{"source_job": "a", "source_document": "a.pdf", "reason": "analysed_before_check"},
                 {"source_job": "q", "source_document": "q.pdf", "reason": "not_ready"},
                 {"source_job": "c", "source_document": "c.pdf", "reason": "no_currency"},
                 {"source_job": "p", "source_document": "p.pdf", "reason": "no_period"},
                 {"source_job": "x", "source_document": "x.pdf", "reason": "no_account_number"}]
    html = _table(f"renderLenders({json.dumps([FUNDER])}, [], 'USD', [], [], {json.dumps(unchecked)}, true);")
    assert ("Payment changes not checked across statements for 5 statement(s): a.pdf (analysed before the check: "
            "re-analyze), q.pdf (not analysed yet), c.pdf (no currency declared: checked alone), p.pdf (no statement "
            "period: checked alone), x.pdf (fewer than 4 account digits and no balance chain: checked alone)") in html


# --------------------------------------------------------------------------------------- U8, U9: summary and modal
@needs_node
def test_u8_the_copied_summaries():
    sentence = run_dashboard(f"""
console.log(JSON.stringify([lenderPaymentChangesSummary({json.dumps([L1, POTENTIAL_STOP])}),
                            lenderPaymentChangesSummary([]), lenderPaymentChangesSummary(undefined)]));
""")
    assert sentence == ["Lender payment changes: 1 decrease, 1 possible stop (1 potential).", "", ""]
    from tests.test_webapp_studio_views import _serve

    march, april = pkg.p1()
    served = run_dashboard(_serve(s=pkg._account(march)) + """
currentJobId = 's'; currentJobIds = ['s']; loadResults('s'); await settle();
generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert "Lender payment changes:" not in served
    two = pkg.statement_payload(pkg.debits(pure.bdays(M(2), M(13)), 850) + pkg.debits(pure.bdays(M(16), M(25)), 600),
                                month=3)
    served = run_dashboard(_serve(s=pkg._account(two)) + """
currentJobId = 's'; currentJobIds = ['s']; loadResults('s'); await settle();
generateSummary(); console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert "Lender payment changes: 1 decrease. Status:" in served
    built = pkg.package(pkg.job("march", march), pkg.job("april", april))
    text = run_dashboard(f"""
currentJobIds = ['march', 'april']; renderPackageAnalysis({json.dumps(built)}); generateSummary();
console.log(JSON.stringify(els.summaryBox.textContent));
""")
    assert text.endswith("\n- Payment decreased: KAPITUS weekly $1,000.00 → $700.00 (-30%) from 2054-04-01; 4 payments "
                         "at the new amount, after 4 at the old (march.pdf → april.pdf).")


@needs_node
def test_u9_the_statement_modal_shows_its_statement_s_lines():
    two = pkg.statement_payload(pkg.debits(pure.bdays(M(2), M(13)), 850) + pkg.debits(pure.bdays(M(16), M(25)), 600),
                                month=3)
    html = run_dashboard(f"""
openStatementModal('s');
renderStatementModal('s', {json.dumps(pkg._account(two))}, '');
console.log(JSON.stringify(els.statementModalLenders.innerHTML));
""")
    assert "Payment decreased: KAPITUS daily $850.00 → $600.00 (-29%) from 2054-03-16" in html
    assert html.index("Payment decreased") < html.index("Confirmed lender")


@needs_node
def test_the_package_page_renders_its_lines():
    march, april = pkg.p1()
    built = pkg.package(pkg.job("march", march), pkg.job("april", april))
    html = run_dashboard(f"""
currentJobIds = ['march', 'april']; renderPackageAnalysis({json.dumps(built)});
console.log(JSON.stringify(els.lenderTable.innerHTML));
""")
    assert "(march.pdf → april.pdf)." in html and "Decreased" in html
