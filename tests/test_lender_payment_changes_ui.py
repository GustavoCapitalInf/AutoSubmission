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
    assert lines[11] == ("Payment decreased: KAPITUS weekly $1,000.00 → $880.00 (-12%) from 2054-04-27; 4 payments at "
                         "the new amount, after 4 at the old; in steps of under 10% each, via weekly $950.00.")
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


@needs_node
def test_u11_u12_the_tones():
    texts = warning_texts([L32, L10B, POTENTIAL, POTENTIAL_STOP, L1])
    assert texts[0][1] == chip_html("‖", "Paused", "amber") and texts[1][1] == chip_html("+", "New stream", "blue")
    assert texts[2][1] == chip_html("↓", "Decreased", "neutral")
    assert texts[3][1] == chip_html("■", "Possible stop", "neutral")
    assert texts[3][0].startswith("Possible stop: no payment to potential lender Unidentified lender obligation "
                                  "(daily, 300.00) in the last 6 business days of the statement (daily;")
    assert texts[4][1] == chip_html("↓", "Decreased", "amber")


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
