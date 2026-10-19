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
    # The owner's request of 2026-10-07 (dashboard clarity): each line is a headline, plain sentences and, on a package
    # item, the statements it comes from (here without the page's rows: the files' names).
    # Review round 1 of the 2026-10-07 change: no "so far" in the counts, the weekly total first (and in the headline)
    # where the schedule changes, and the grace window read as a threshold.
    assert lines[0] == ("KAPITUS: payment went down 29%. The daily payment went from $850.00 to $600.00 starting Mar 16, "
                        "2054 (8 payments at the new amount, after 10 at the old).")
    assert lines[1] == ("KAPITUS: payment went down 30%. The weekly payment went from $1,000.00 to $700.00 starting Apr "
                        "1, 2054 (4 payments at the new amount, after 4 at the old). From: march.pdf → april.pdf.")
    assert lines[2] == ("KAPITUS: payment schedule changed. Payments changed from daily $500.00 to weekly $2,500.00 "
                        "starting Mar 23, 2054 (4 payments on the new schedule, after 15 on the old). The weekly total "
                        "stayed about the same ($2,500.00 before, $2,500.00 after).")
    assert lines[3] == ("KAPITUS: weekly payment total went down 40%. The weekly total went from $2,500.00 to "
                        "$1,500.00. Payments changed from daily $500.00 to weekly $1,500.00 starting Mar 23, 2054 (4 "
                        "payments at the new amount, after 15 at the old).")
    assert lines[4] == ("KAPITUS: payments may have stopped. No payment in the last 11 business days of this statement. "
                        "A weekly schedule allows up to 10 business days without a payment. Last payment: $1,000.00 on "
                        "May 13, 2054.")
    assert lines[5] == ("KAPITUS: payments stopped. Last weekly payment: $1,000.00 on Apr 29, 2054. No payments in the "
                        "21 business days after it, through May 29, 2054. From: april.pdf.")
    # Review round 3 of the 2026-10-07 change: the quiet business days after the last debit at another amount.
    assert lines[6] == ("KAPITUS: payments may have stopped. Last regular daily payment: $850.00 on Mar 13, 2054. After "
                        "it came only 3 debits at other amounts, the last on Mar 19, 2054. No payment in the 8 business "
                        "days after Mar 19, 2054, to the end of this statement. A daily schedule allows up to 5 business "
                        "days without a payment.")
    assert lines[7] == ("KAPITUS: payments paused, then resumed. No payment between Mar 6 and Mar 16, 2054 (6 business "
                        "days, more than the 5 a daily schedule allows). Payments then resumed at the same daily "
                        "$850.00.")
    assert lines[8] == ("KAPITUS: a second payment started. A second weekly payment of $2,100.00 started on Mar 18, "
                        "2054, alongside the existing weekly $1,000.00. The weekly total went from $1,000.00 to "
                        "$3,100.00 (+210%).")
    # Review round 2 of the 2026-10-07 change: the new payments' own label, where it differs, is named. Review round 3:
    # a potential lender's headline reads "Potential lender <label>: ...".
    assert lines[9] == ("Potential lender Unidentified lender obligation (daily, 300.00): payment went down 17%. The "
                        "daily payment went from $300.00 to $250.00 starting Mar 16, 2054 (8 payments at the new amount, "
                        "after 10 at the old). The new payments are listed as Unidentified lender obligation (daily, "
                        "250.00).")
    # § Still open 18's alternative and § Still open 23's alternative (the orchestrator's choices of 2026-10-06).
    assert lines[10] == ("KAPITUS: weekly payment total may have gone down 36%. The weekly total went from $2,500.00 to "
                         "$1,600.00. Payments changed from daily $500.00 to weekly $1,600.00 starting Mar 23, 2054 (2 "
                         "payments at the new amount, after 15 at the old). The new schedule isn't confirmed yet.")
    # R2-OW18 review round 1: the unreported levels with the step into each, then the last step.
    assert lines[11] == ("KAPITUS: payment went down 12%. The weekly payment went from $1,000.00 to $880.00 starting Apr "
                         "27, 2054 (4 payments at the new amount, after 4 at the old). It stepped through $950.00 (-5%) "
                         "on the way, then to $880.00 (-7%).")
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
    # The owner's request of 2026-10-07: each extra note is its own "Also:" sentence.
    assert texts[0].endswith(" Also: a final debit of $5,000.00 on Apr 20, 2054 may be a payoff.")
    assert texts[1].endswith(" Also: payments of $860.00 continue under ONDECK from Mar 17, 2054; this may be a buyout "
                             "or refinance.")
    assert texts[2].endswith(" Also: ONDECK started daily payments of $1,000.00 on Mar 17, 2054; it may have taken over "
                             "this advance.")
    assert texts[3].endswith(" Also: a debt-relief program's payments start on Mar 18, 2054; this may mean a default or "
                             "settlement.")
    assert texts[4] == ("KAPITUS: payments may have stopped. No payment in the last 23 business days of this statement. "
                        "A weekly schedule allows up to 10 business days without a payment. Last payment: $1,000.00 on "
                        "Mar 30, 2054. This lender has 2 separate payment streams; this note is about the first. Also: "
                        "another KAPITUS payment of $1,200.00 weekly continues.")
    assert texts[5].endswith(" Also: payments to KAPITUS continue from another account (b-april.pdf) from Apr 15, 2054 "
                             "at $1,000.00. From: a-april.pdf.")
    assert texts[5].startswith("KAPITUS: payments may have stopped. No payment in the last ")
    assert ", through May 29, 2054." in texts[5]
    assert texts[6].endswith(" Also: the last attempt, on Apr 8, 2054, was returned unpaid.")
    assert texts[7].endswith(" Also: KAPITUS deposited $25,000.00 on Mar 13, 2054, just before; this may be a renewal.")


@needs_node
def test_u4_the_change_suffixes():
    cut = pure._rows(pure.bdays(M(2), M(11)), 850) + pure._rows(pure.bdays(M(12), M(18)), 600)
    decrease, increase = pure.changes(cut + pure._rows(pure.bdays(M(19), M(26)), 850))
    restart = pure.only(pure._rows(pure.every(M(2), M(23)), 1000) + pure._rows(pure.every(A(20), Y(4)), 700), end=Y(8))
    texts = [text for text, _chip in warning_texts([decrease, increase, restart])]
    assert texts[0].endswith(" Also: this was temporary; the payment went back to $850.00 on Mar 19, 2054.")
    assert texts[1].endswith(" Also: this is back to the earlier $850.00 payment.")
    assert texts[2].endswith(" Also: the new amount started after a pause of 20 business days with no payment.")


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
    assert texts[0] == ("KAPITUS: payment went down 35%. The weekly payment went from $1,000.00 to $650.00 starting Apr "
                        "13, 2054 (3 payments at the new amount, after 3 at the old). It stepped through $950.00 (-5%) "
                        "on the way, then to $650.00 (-32%).")
    assert texts[1] == ("KAPITUS: weekly payment total may have gone down 36%. The weekly total went from $2,500.00 to "
                        "$1,600.00. Payments changed from daily $500.00 to weekly $1,600.00 starting Mar 16, 2054 (2 "
                        "payments at the new amount, after 10 at the old). The new schedule isn't confirmed yet.")
    # A level names its schedule where the change crosses schedules.
    assert texts[2] == ("KAPITUS: payment schedule changed. Payments changed from daily $500.00 to weekly $2,300.00 "
                        "starting Mar 30, 2054 (3 payments on the new schedule, after 10 on the old). The weekly total "
                        "stayed about the same ($2,500.00 before, $2,300.00 after, -8%). It stepped through weekly "
                        "$1,600.00 (-36%) on the way, then to weekly $2,300.00 (+44%).")
    # An item stored without the step fields names its levels alone; no line claims the steps' size.
    assert texts[3].endswith(" It stepped through $950.00 on the way.")
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
    assert texts[0] == ("KAPITUS: payments paused, then resumed. No payment or payment attempt between Mar 6 and Mar 16, "
                        "2054 (6 business days, more than the 5 a daily schedule allows). The attempt on Mar 16, 2054 "
                        "was returned unpaid, and payments resumed at the same daily $850.00 on Mar 23, 2054.")
    assert texts[1] == ("KAPITUS: payments paused, then resumed. No payment between Mar 6 and Mar 16, 2054 (6 business "
                        "days, more than the 5 a daily schedule allows). A payment of another amount came on Mar 16, "
                        "2054, and payments resumed at the same daily $850.00 on Mar 23, 2054.")
    assert stop["stop_confirmed"] is True
    assert texts[2] == (f"KAPITUS: payments stopped. Last weekly payment: $1,000.00 on Mar 18, 2054. No payment or "
                        f"payment attempt in the {stop['quiet_business_days']} business days after Mar 25, 2054, "
                        f"through Apr 30, 2054. Also: the last attempt, on Mar 25, 2054, was returned unpaid. From: "
                        f"april.pdf.")
    assert texts[3] == (f"KAPITUS: payments may have stopped. No payment or payment attempt in the last "
                        f"{ATTEMPT['quiet_business_days']} business days of this statement. A weekly schedule allows "
                        f"up to 10 business days without a payment. Last payment: $1,000.00 on Apr 1, 2054. Also: the "
                        f"last attempt, on Apr 8, 2054, was returned unpaid.")
    # The regime's own payment ends L32's pause: the line as before.
    assert texts[4] == ("KAPITUS: payments paused, then resumed. No payment between Mar 6 and Mar 16, 2054 (6 business "
                        "days, more than the 5 a daily schedule allows). Payments then resumed at the same daily "
                        "$850.00.")


@needs_node
def test_u11_u12_the_tones():
    texts = warning_texts([L32, L10B, POTENTIAL, POTENTIAL_STOP, L1])
    assert texts[0][1] == chip_html("‖", "Paused", "amber") and texts[1][1] == chip_html("+", "New stream", "blue")
    assert texts[2][1] == chip_html("↓", "Decreased", "neutral")
    assert texts[3][1] == chip_html("■", "Possible stop", "neutral")
    assert texts[3][0].startswith("Potential lender Unidentified lender obligation (daily, 300.00): payments may have "
                                  "stopped. No payment in the last 6 business days of this statement.")
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
    # Audit round 3, R3-MERGE: each line in the plain voice of the owner's request of 2026-10-07 (the hosting line's
    # lender notes); every fact the round-3 line carried stays (the levels, the weekly equivalents and the percentage,
    # the first day, the counts, the unconfirmed schedule, the temporary cut and the return to the earlier amount).
    assert texts[0] == [
        "KAPITUS: weekly payment total may have gone down 40%. The weekly total went from $2,500.00 to $1,500.00. "
        "Payments changed from daily $500.00 to weekly $1,500.00 starting Mar 23, 2054 (2 payments at the new amount, "
        "after 15 at the old). The new schedule isn't confirmed yet.", chip_html("↓", "Possible decrease", "amber")]
    assert texts[1][0] == ("KAPITUS: payment went down 60%. The daily payment went from $850.00 to $340.00 starting Mar "
                           "30, 2054 (10 payments at the new amount, after 20 at the old). Also: this was temporary; the "
                           "payment went back to $850.00 on Apr 15, 2054.")
    assert texts[2][0] == ("KAPITUS: payment went up 150%. The daily payment went from $340.00 to $850.00 starting Apr "
                           "15, 2054 (4 payments at the new amount, after 10 at the old). Also: this is back to the "
                           "earlier $850.00 payment.")


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
    # Audit round 3, R3-MERGE: in the plain voice of the owner's request of 2026-10-07; every R3-25 fact stays (the
    # catch-up's amount, multiple and day, the larger debit inside the gap, the later exact multiples, the payoff's
    # earlier debits of twice the payment or more).
    assert texts[0] == [
        "KAPITUS: payments paused, then resumed. No payment between Mar 6 and Mar 16, 2054 (6 business days, more than "
        "the 5 a daily schedule allows). A debit of $1,800.00 on Mar 16, 2054, 6 times the payment, may be a catch-up, "
        "and payments resumed at the same daily $300.00 on Mar 23, 2054.", chip_html("‖", "Paused", "amber")]
    assert texts[1][0] == (
        "KAPITUS: payments paused, then resumed. No payment between Mar 6 and Mar 23, 2054 (11 business days, more than "
        "the 5 a daily schedule allows). Payments then resumed at the same daily $300.00. Also: a debit of $1,300.00 on "
        "Mar 16, 2054, inside the gap, was more than twice the payment.")
    assert ("After it came only 2 debits at other amounts, the last on Jun 12, 2054; 2 of them are exact multiples of "
            "the payment, which may be a catch-up.") in texts[2][0]
    assert "payoff" not in texts[2][0]
    assert texts[3][0].endswith("Also: a final debit of $5,000.00 on Apr 20, 2054 may be a payoff, after 1 earlier debit "
                                "of twice the payment or more.")
    assert ("After it came only 1 debit at another amount, on Mar 17, 2054; it is an exact multiple of the payment, "
            "which may be a catch-up.") in texts[4][0]
    assert texts[5][0].endswith("may be a payoff, after 2 earlier debits of twice the payment or more.")
    # A payoff with no earlier one reads as before (L20).
    assert warning_text(L20).endswith("Also: a final debit of $5,000.00 on Apr 20, 2054 may be a payoff.")


@needs_node
def test_r3_b05_the_caught_up_line():
    march = pure._rows(pure.bdays(M(2), M(27)), 850)
    april = pure._rows([A(2)], 1700) + pure._rows(pure.bdays(A(3), A(30)), 850)
    [chained] = pure._chain((march, M(1), M(31)), (april, A(1), A(30)))
    chained = {**pure.lpc.public_item(chained), "source_document": "april.pdf"}
    items = _r3_b05_items()
    caught_up, weekly, potential = items["caught_up"], items["caught_up_weekly"], items["caught_up_potential"]
    texts = warning_texts([caught_up, weekly, potential, chained])
    # Audit round 3, R3-MERGE: the owner's amber "Caught up" note (R3-25) in the plain voice of the owner's request of
    # 2026-10-07: the missed scheduled payments and their days, the catch-up's amount, day and multiple of the payment,
    # the potential lender named first, the statement it comes from; the chips unchanged.
    assert texts[0] == [
        "KAPITUS: missed payments caught up. 2 scheduled daily payments were missed (Mar 16 to Mar 17, 2054). Then one "
        "debit of $1,700.00 on Mar 18, 2054 came to 2 times the daily $850.00 payment.",
        chip_html("↺", "Caught up", "amber")]
    assert texts[1][0] == ("KAPITUS: missed payments caught up. 1 scheduled weekly payment was missed (Mar 24, 2054). "
                           "Then one debit of $3,000.00 on Mar 27, 2054 came to 3 times the weekly $1,000.00 payment.")
    assert texts[2] == [
        "Potential lender Unidentified lender obligation (daily, 300.00): missed payments caught up. 1 scheduled daily "
        "payment was missed (Mar 16, 2054). Then one debit of $600.00 on Mar 17, 2054 came to 2 times the daily $300.00 "
        "payment.", chip_html("↺", "Caught up", "neutral")]
    assert texts[3][0] == ("KAPITUS: missed payments caught up. 3 scheduled daily payments were missed (Mar 30 to Apr 1, "
                           "2054). Then one debit of $1,700.00 on Apr 2, 2054 came to 2 times the daily $850.00 payment. "
                           "From: april.pdf.")
    # A weekly triple after two missed weeks: its pause line carries the catch-up, the one line for the gap.
    [pause] = pure.changes(pure._rows(pure.every(M(3), M(17)) + pure.every(A(14), Y(26)), 1000)
                           + pure._rows([A(7)], 3000), end=Y(29))
    assert warning_text(pause) == (
        "KAPITUS: payments paused, then resumed. No payment between Mar 17 and Apr 7, 2054 (15 business days, more than "
        "the 10 a weekly schedule allows). A debit of $3,000.00 on Apr 7, 2054, 3 times the payment, may be a "
        "catch-up, and payments resumed at the same weekly $1,000.00 on Apr 14, 2054.")
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
    # Audit round 3, R3-MERGE: in the plain voice of the owner's request of 2026-10-07, the catch-up an "Also:" sentence.
    assert texts[0] == [
        "KAPITUS: payments paused, then resumed. No payment or payment attempt between Mar 6 and Mar 16, 2054 (6 "
        "business days, more than the 5 a daily schedule allows). The attempt on Mar 16, 2054 was returned unpaid, and "
        "payments resumed at the same daily $850.00 on Mar 18, 2054. Also: a debit of $1,700.00 on Mar 17, 2054, 2 "
        "times the payment, came before payments resumed; this may be a catch-up.", chip_html("‖", "Paused", "amber")]
    assert texts[1][0] == (
        "KAPITUS: payments paused, then resumed. No payment between Mar 6 and Mar 16, 2054 (6 business days, more than "
        "the 5 a daily schedule allows). A payment of another amount came on Mar 16, 2054, and payments resumed at the "
        "same daily $850.00 on Mar 18, 2054. Also: a debit of $2,550.00 on Mar 17, 2054, 3 times the payment, came "
        "before payments resumed; this may be a catch-up.")


@needs_node
def test_r3_b05_the_same_amount_note_and_a_stop_it_never_confirms():
    march = pure._rows(pure.bdays(M(2), M(13)), 850) + pure._other(pure.bdays(M(16), M(31)), 850)
    [stop] = pure._chain((march, M(1), M(31)), (pure._other(pure.bdays(A(1), A(30)), 850), A(1), A(30)))
    stop = {**pure.lpc.public_item(stop), "source_document": "march.pdf"}
    [pause] = pure._chain((march, M(1), M(31)), (pure._rows(pure.bdays(A(1), A(30)), 850), A(1), A(30)))
    pause = {**pure.lpc.public_item(pause), "source_document": "april.pdf"}
    texts = warning_texts([_r3_b05_items()["same_amount_stop"], stop, pause])
    # Audit round 3, R3-MERGE: R3-84's note an "Also:" sentence in the plain voice of the owner's request of 2026-10-07:
    # the count, the exact amount, the schedule, the other description, the days and the possible collection.
    assert texts[0][0].endswith("Also: 12 debits of exactly $850.00 came on the same daily schedule under another "
                                "description, from Mar 16 to Mar 31, 2054; this may be the lender collecting under "
                                "another name.")
    assert texts[0][0].startswith("KAPITUS: payments may have stopped. No payment in the last 12 business days of this "
                                  "statement.")
    assert texts[0][1] == chip_html("■", "Possible stop", "amber")
    assert stop["stop_confirmed"] is False
    assert texts[1][0].startswith("KAPITUS: payments may have stopped. No payment in the last ")
    assert texts[1][0].endswith("Also: 34 debits of exactly $850.00 came on the same daily schedule under another "
                                "description, from Mar 16 to Apr 30, 2054; this may be the lender collecting under "
                                "another name. From: march.pdf.")
    assert texts[1][1] == chip_html("■", "Possible stop", "amber")
    assert texts[2][0] == (
        "KAPITUS: payments paused, then resumed. No payment between Mar 13 and Apr 1, 2054 (13 business days, more than "
        "the 5 a daily schedule allows). Payments then resumed at the same daily $850.00. Also: 12 debits of exactly "
        "$850.00 came on the same daily schedule under another description, from Mar 16 to Mar 31, 2054; this may be "
        "the lender collecting under another name. From: april.pdf.")


# ------------------------------------------- audit round 3, R3-B06 (R3-81, R3-85; fabricated rows only): the lines
@needs_node
def test_r3_81_the_new_stream_line_names_the_level_paying_when_it_began():
    _decrease, stream = pure.changes(pure._rows(pure.bdays(M(2), A(30)), 250) + pure._rows(pure.bdays(Y(1), J(30)), 112)
                                     + pure._rows(pure.bdays(M(16), J(30)), 170), start=M(1), end=J(30))
    # Audit round 3, R3-MERGE: in the plain voice of the owner's request of 2026-10-07; R3-81's fact stays: the other
    # stream named at the level it paid when the new one began (daily $250.00, not the later $112.00).
    assert warning_text(stream) == (
        "KAPITUS: a second payment started. A second daily payment of $170.00 started on Mar 16, 2054, alongside the "
        "existing daily $250.00. The weekly total went from $1,250.00 to $2,100.00 (+68%).")


@needs_node
def test_r3_85_a_confirmed_stop_s_count_names_its_anchor():
    # Weekly 1,000.00 to 03-30, then debits of 700.00 on 04-06 and 650.00 on 04-20 (payment-sized, presence), and a May
    # statement with none: the count runs from the last presence (04-20), not from the "since" date (03-30).
    march = pure._rows(pure.every(M(2), M(30)), 1000)
    april = pure._rows([A(6)], 700) + pure._rows([A(20)], 650)
    [stop] = pure._chain((march, M(1), M(31)), (april, A(1), A(30)), ([], Y(1), Y(29)))
    stop = {**pure.lpc.public_item(stop), "source_document": "april.pdf"}
    assert (stop["stop_confirmed"], stop["last_payment_date"], stop["last_presence_date"],
            stop["quiet_business_days"]) == (True, "2054-03-30", "2054-04-20", 28)
    # Audit round 3, R3-MERGE: in the plain voice of the owner's request of 2026-10-07, which names every count's anchor
    # ("after <the last presence>", or "after it" where that is the last payment): R3-85's fact stays, the 28 business
    # days counted after the last presence (Apr 20), not after the last regular payment (Mar 30).
    assert warning_text(stop) == (
        "KAPITUS: payments stopped. Last regular weekly payment: $1,000.00 on Mar 30, 2054. After it came only 2 debits "
        "at other amounts, the last on Apr 20, 2054. No payment in the 28 business days after Apr 20, 2054, through May "
        "29, 2054. From: april.pdf.")
    # Controls: the plain confirmed line (U1-U4) counts from its last payment ("after it"), and the returned-attempt
    # line from the attempt, its last presence (the hosting line's review round 1 names that day).
    p4 = pkg.package(*(pkg.job(name, payload) for name, payload in zip(("march", "april", "may"), pkg.p4())))
    attempt_march = pure._rows(pure.every(M(4), M(18)), 1000) + pure._rows(
        [M(25)], 1000, returned_funder_payment_by="transaction:99")
    [attempt] = pure._chain((attempt_march, M(1), M(31)), ([], A(1), A(30)))
    attempt = {**pure.lpc.public_item(attempt), "source_document": "april.pdf"}
    texts = [text for text, _chip in warning_texts([p4["lender_payment_changes"][0], attempt])]
    assert texts[0] == ("KAPITUS: payments stopped. Last weekly payment: $1,000.00 on Apr 29, 2054. No payments in the "
                        "21 business days after it, through May 29, 2054. From: april.pdf.")
    assert texts[1] == (f"KAPITUS: payments stopped. Last weekly payment: $1,000.00 on Mar 18, 2054. No payment or "
                        f"payment attempt in the {attempt['quiet_business_days']} business days after Mar 25, 2054, "
                        f"through Apr 30, 2054. Also: the last attempt, on Mar 25, 2054, was returned unpaid. From: "
                        f"april.pdf.")


# ------------------------------------------------------------------------------------- U5, U6, U7, U10: the table
def _table(call):
    return run_dashboard(f"""
{call}
console.log(JSON.stringify(els.lenderTable.innerHTML));
""")


FUNDER = {"funder": "KAPITUS", "debit_count": 18, "total_debited": 13300.0, "transactions": [], "evidence": []}
# The owner's request of 2026-10-07: the not-checked notes in the same plain voice (headline, then the sentence).
STATEMENT_TEXT = "This statement was analysed before the check. Re-analyze it to see payment changes."
PACKAGE_TEXT = "No statement in this package has been checked yet."


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
    assert html.index("KAPITUS: a payment was returned") < html.index("KAPITUS: payments may have stopped") < (
        html.index("No lenders detected"))


@needs_node
def test_u7_a_cad_item_prints_cad_money():
    item = {**L1, "scope": "package", "source_currency": "CAD", "source_document": "td.pdf", "cross_statement": False}
    assert warning_text(item, None).startswith("KAPITUS: payment went down 29%. The daily payment went from CA$850.00 "
                                               "to CA$600.00 starting")


@needs_node
def test_u10_the_package_s_unchecked_line():
    unchecked = [{"source_job": "a", "source_document": "a.pdf", "reason": "analysed_before_check"},
                 {"source_job": "q", "source_document": "q.pdf", "reason": "not_ready"},
                 {"source_job": "c", "source_document": "c.pdf", "reason": "no_currency"},
                 {"source_job": "p", "source_document": "p.pdf", "reason": "no_period"},
                 {"source_job": "x", "source_document": "x.pdf", "reason": "no_account_number"}]
    html = _table(f"renderLenders({json.dumps([FUNDER])}, [], 'USD', [], [], {json.dumps(unchecked)}, true);")
    assert '<strong class="lender-note-headline">Payment changes not checked across statements</strong>' in html
    assert ("These 5 statements were not compared with the others: a.pdf (analysed before the check; re-analyze it to "
            "include it); q.pdf (not analysed yet); c.pdf (no currency declared, so it was checked on its own); p.pdf "
            "(no statement period printed, so it was checked on its own); x.pdf (fewer than 4 account digits and no "
            "balance chain, so it was checked on its own).") in html


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
    # The owner's request of 2026-10-07: the memo's line is the lender table's note, its statements named by month.
    assert text.endswith("\n- KAPITUS: payment went down 30%. The weekly payment went from $1,000.00 to $700.00 starting "
                         "Apr 1, 2054 (4 payments at the new amount, after 4 at the old). From: March 2054 → April "
                         "2054 statements.")


@needs_node
def test_u9_the_statement_modal_shows_its_statement_s_lines():
    two = pkg.statement_payload(pkg.debits(pure.bdays(M(2), M(13)), 850) + pkg.debits(pure.bdays(M(16), M(25)), 600),
                                month=3)
    html = run_dashboard(f"""
openStatementModal('s');
renderStatementModal('s', {json.dumps(pkg._account(two))}, '');
console.log(JSON.stringify(els.statementModalLenders.innerHTML));
""")
    assert '<strong class="lender-note-headline">KAPITUS: payment went down 29%</strong>' in html
    assert ("The daily payment went from $850.00 to $600.00 starting Mar 16, 2054 (8 payments at the new amount, after "
            "10 at the old).") in html
    assert "lender-note-source" not in html  # a statement's own window names no statement
    assert html.index("payment went down") < html.index("Confirmed lender")


@needs_node
def test_the_package_page_renders_its_lines():
    march, april = pkg.p1()
    built = pkg.package(pkg.job("march", march), pkg.job("april", april))
    html = run_dashboard(f"""
currentJobIds = ['march', 'april']; renderPackageAnalysis({json.dumps(built)});
console.log(JSON.stringify(els.lenderTable.innerHTML));
""")
    assert '<div class="lender-note-source">From: March 2054 → April 2054 statements</div>' in html
    assert "Decreased" in html
