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
    assert lines[6] == ("KAPITUS: payments may have stopped. No regular daily payment since Mar 13, 2054; only 3 debits "
                        "at other amounts since (the last on Mar 19, 2054). A daily schedule allows up to 5 business "
                        "days without a payment. Last regular payment: $850.00 on Mar 13, 2054.")
    assert lines[7] == ("KAPITUS: payments paused, then resumed. No payment between Mar 6 and Mar 16, 2054 (6 business "
                        "days, more than the 5 a daily schedule allows). Payments then resumed at the same daily "
                        "$850.00.")
    assert lines[8] == ("KAPITUS: a second payment started. A second weekly payment of $2,100.00 started on Mar 18, "
                        "2054, alongside the existing weekly $1,000.00. The weekly total went from $1,000.00 to "
                        "$3,100.00 (+210%).")
    assert lines[9] == ("Unidentified lender obligation (daily, 300.00) (potential lender): payment went down 17%. The "
                        "daily payment went from $300.00 to $250.00 starting Mar 16, 2054 (8 payments at the new amount, "
                        "after 10 at the old).")
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
    assert texts[3][0].startswith("Unidentified lender obligation (daily, 300.00) (potential lender): payments may "
                                  "have stopped. No payment in the last 6 business days of this statement.")
    assert texts[4][1] == chip_html("↓", "Decreased", "amber")


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
