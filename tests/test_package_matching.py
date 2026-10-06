"""Owner ruling 2026-10-02 (the underwriter's Q6, "2"; audit I42; true revenue spec §6.2's package passes, §9.1, §9.2,
§11; R2-OW15): a deposited item returned in the next statement of the same account leaves the package's True revenue,
a redeposit counts once, and the returns no statement or package pairs and the processor chargebacks and adjustments
are flagged, never deducted. The passes are package-only: a statement viewed alone keeps its own figures.

Fabricated statements only (CONTOSO BAKERY LLC, account A 000000001010 and account B 000000002020 at Sample Bank,
NORTHWIND and FABRIKAM payers, whole-dollar amounts), analysed by the real analysis path (as
tests/test_webapp_studio_views._report does, with a bank, an account number and a currency) and packaged by
webapp.app._package_analysis(jobs, settings={})."""
from __future__ import annotations

import copy
import csv
import io
import json
import re
from pathlib import Path

import pytest

BANK = "Sample Bank"
HOLDER = "CONTOSO BAKERY LLC"
ACCOUNT_A, ACCOUNT_B = "000000001010", "000000002020"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "package_matching" / "no_pair_package.json"
NW_MARCH = "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1"
NW_APRIL = "NORTHWIND SUPPLY LLC DES:PAYMENT ID:2"
RETURNED = "DEPOSITED ITEM RETURNED"


def _closing(rows, opening):
    return round(opening + sum(row[2] for row in rows if len(row) < 4), 2)


def _payload(rows, *, month, opening, number=ACCOUNT_A, currency="USD", name=HOLDER):
    """One month of account `number` (the 1st to the 28th of 2031), every row with its running balance. A row
    `(day, description, amount, "repeat")` prints the row before it a second time, its running balance included (a
    proven duplicate, which the bank's figures do not count: the statement reconciles without it)."""
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction
    from analysis.serialization import document_report_to_dict

    txns, printed, balance = [], [], opening
    for row in rows:
        day, description, amount = row[:3]
        if len(row) < 4:
            balance = round(balance + amount, 2)
        transaction = Transaction(date=f"2031-{month:02d}-{day:02d}", description=description, amount=amount,
                                  direction="credit" if amount > 0 else "debit", running_balance=balance)
        txns.append(transaction)
        if len(row) < 4:
            printed.append(transaction)
    fields = dict(bank=BANK, account_name=name, account_number=number, period_start=f"2031-{month:02d}-01",
                  period_end=f"2031-{month:02d}-28", beginning_balance=opening, ending_balance=balance,
                  currency=currency, currency_source="printed")
    statement = Statement(**fields, transactions=txns)
    report = analyze_statement(statement, reconciliation=reconcile(Statement(**fields, transactions=printed)),
                               markdown="", sheets=[], model_used="fabricated-test")
    return document_report_to_dict(report)


def _job(job_id, payload):
    from webapp.jobs import Job
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def _package(*members):
    from webapp.app import _package_analysis
    return _package_analysis([_job(job_id, payload) for job_id, payload in members], settings={})


def _served(payload):
    from webapp.app import _displayed
    return _displayed(payload, settings={})


def _ledger_row(package, job_id, location):
    return next(row for row in package["transactions"]
                if row["source_job"] == job_id and row["classification"]["source_location"] == location)


def _doc(package, job_id):
    return next(row for row in package["documents"] if row["id"] == job_id)


#: The owner's example (S1): a March deposit returned on the 1st of April.
MARCH = [(5, NW_MARCH, 50000.0), (26, "DEPOSIT", 100000.0)]
APRIL = [(1, RETURNED, -100000.0), (5, NW_APRIL, 50000.0)]


def _owners_example(april=APRIL, *, april_number=ACCOUNT_A, april_opening=None):
    march = _payload(MARCH, month=3, opening=1500.0)
    opening = _closing(MARCH, 1500.0) if april_opening is None else april_opening
    return march, _payload(april, month=4, opening=opening, number=april_number)


# ---------------------------------------------------------------- the reader

@pytest.mark.parametrize(("text", "wording"), [
    ("HRTLAND PMT SYS CHARGEBACK 123456", "chargeback"),
    ("FABRIKAM MERCHANT SVCS MERCH CHBK", "chargeback"),
    ("FABRIKAM MERCHANT SVCS CHGBK", "chargeback"),
    ("FABRIKAM MERCHANT SVCS CHG BACK", "chargeback"),
    ("FABRIKAM MERCHANT SVCS CHARGE BACKS", "chargeback"),
    ("FABRIKAM MERCHANT SVCS MERCH ADJ", "adjustment"),
    ("FABRIKAM MERCHANT SVCS MERCHANT ADJUSTMENT", "adjustment"),
    ("FABRIKAM BANKCARD FINCL ADJ", "adjustment"),
    ("FABRIKAM BANKCD ADJ", "adjustment"),
    ("CHARGEBACK FEE", None),
    ("CHBK CHRG", None),
    ("FABRIKAM MERCHANT SVCS CHG", None),
    ("CHARGEBACK SVC CHG", None),
    ("CHARGEBACK SERVICE CHARGE", None),
    ("DEP RETURN CHARGEBACK", None),
    ("CHARGE BACK ITEM CHECK 1041", None),
    ("DEP RETURN FEE", None),
    ("FABRIKAM MERCHANT SVCS DISCOUNT", None),
    ("CHARGEBACKS FRAIS", None),
])
def test_the_reader_reads_a_processor_s_chargeback_or_adjustment_never_a_fee_or_a_returned_deposit(text, wording):
    from analysis.transaction_classifier import processor_chargeback_debit

    assert processor_chargeback_debit(text) == wording


# ---------------------------------------------------------------- Q6: returned deposits across statements

def test_s1_a_deposit_returned_in_the_next_statement_leaves_the_package_s_true_revenue():
    """S1, the owner's example: today the package counts the returned $100,000 deposit (True 200,000.00); now March's
    DEPOSIT is non-revenue in the package, matched to April's return 6 days after it."""
    march, april = _owners_example()
    stored = copy.deepcopy((march, april))
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    assert totals["true_revenue_total"] == 100000.0
    assert totals["verified_revenue_total"] == 100000.0
    assert totals["non_revenue_total"] == 100000.0
    assert (totals["returned_deposit_cross_statement_count"], totals["returned_deposit_cross_statement_total"]) == (
        1, 100000.0)
    assert "unmatched_deposit_return_count" not in totals and "processor_chargeback_count" not in totals
    assert "package_match_unchecked_count" not in totals
    deposit = _ledger_row(package, "mar", "transaction:2")["classification"]
    assert (deposit["revenue_classification"], deposit["revenue_tier"], deposit["revenue_tier_reason"]) == (
        "non_revenue", "non_revenue", None)
    assert (deposit["revenue_match_method"], deposit["revenue_matched_rule"]) == (
        "matched_reversal_pair", "returned_deposit_cross_statement")
    assert deposit["revenue_review_required"] is False
    assert deposit["contributes_to_true_revenue"] is False and deposit["contributes_to_non_revenue"] is True
    assert deposit["contributes_to_counted_flagged"] is False
    # Kept, so Confirm Revenue still shows on the row and overrides the match.
    assert (deposit["revenue_initial_classification"], deposit["revenue_review_status"]) == ("unverified_deposit",
                                                                                            "pending")
    assert deposit["revenue_related_transaction"] is None
    assert deposit["package_match"] == {
        "kind": "returned_deposit", "moved": True, "gap_days": 6, "tier_before": "counted_flagged",
        "reason_before": "no_payer_printed",
        "debit": {"job": "apr", "filename": "apr.pdf", "account_index": None, "source_location": "transaction:1",
                  "date": "2031-04-01", "amount": -100000.0, "bank": BANK, "last4": "1010"},
    }
    debit = _ledger_row(package, "apr", "transaction:1")["classification"]
    assert debit["package_match"] == {
        "kind": "returned_deposit",
        "credit": {"job": "mar", "filename": "mar.pdf", "account_index": None, "source_location": "transaction:2",
                   "date": "2031-03-26", "amount": 100000.0, "bank": BANK, "last4": "1010"},
    }
    assert package["package_matches"] == [{
        "kind": "returned_deposit", "moved": True, "gap_days": 6,
        "credit": {**deposit["package_match"]["debit"], "job": "mar", "filename": "mar.pdf",
                   "source_location": "transaction:2", "date": "2031-03-26", "amount": 100000.0, "currency": "USD",
                   "tier_before": "counted_flagged", "reason_before": "no_payer_printed"},
        "debit": {**debit["package_match"]["credit"], "job": "apr", "filename": "apr.pdf",
                  "source_location": "transaction:1", "date": "2031-04-01", "amount": -100000.0, "currency": "USD"},
    }]
    assert "debit_flags" not in package
    assert (_doc(package, "mar")["package_match_count"], _doc(package, "apr")["package_match_count"]) == (1, 1)
    assert _doc(package, "mar")["true_revenue_total"] == 50000.0
    assert "package_match_unchecked" not in _doc(package, "mar")
    # Nothing is written back.
    assert (march, april) == stored


def test_s1_each_statement_viewed_alone_keeps_its_own_figures_and_flags_the_return():
    march, april = _owners_example()
    alone = _served(march)["metrics"]
    assert alone["true_revenue_total"] == 150000.0
    assert not any(key.startswith(("unmatched_deposit_return", "processor_chargeback")) for key in alone)
    flagged = _served(april)["metrics"]
    assert flagged["true_revenue_total"] == 50000.0
    assert (flagged["unmatched_deposit_return_count"], flagged["unmatched_deposit_return_total"],
            flagged["unmatched_deposit_return_locations"]) == (1, 100000.0, ["transaction:1"])
    assert "processor_chargeback_count" not in flagged
    # A package of April alone has no preceding statement: the return is flagged there too, nothing moves.
    package = _package(("apr", april))
    assert package["totals"]["true_revenue_total"] == 50000.0
    assert (package["totals"]["unmatched_deposit_return_count"],
            package["totals"]["unmatched_deposit_return_total"]) == (1, 100000.0)
    assert package["debit_flags"] == [{
        "kind": "unmatched_deposit_return", "source_job": "apr", "source_document": "apr.pdf", "source_account": None,
        "source_currency": "USD", "source_location": "transaction:1", "date": "2031-04-01", "amount": -100000.0,
        "description": RETURNED,
    }]
    assert "package_matches" not in package


def test_s2_a_redeposit_after_the_return_counts_once():
    """S2: the bounced check deposited again on 04-08 stays counted, so the money counts once (today 300,000.00)."""
    march, april = _owners_example([*APRIL, (8, "DEPOSIT", 100000.0)])
    package = _package(("mar", march), ("apr", april))
    assert package["totals"]["true_revenue_total"] == 200000.0
    redeposit = _ledger_row(package, "apr", "transaction:3")["classification"]
    assert (redeposit["revenue_tier"], redeposit["revenue_tier_reason"]) == ("counted_flagged", "no_payer_printed")
    assert "package_match" not in redeposit
    assert _ledger_row(package, "mar", "transaction:2")["classification"]["revenue_tier"] == "non_revenue"


def test_s3a_there_is_no_day_cap_inside_the_preceding_statement():
    """S3 (a): a deposit of 03-05 returned on 04-04, 30 days later, is matched ("across consecutive months")."""
    march_rows = [(5, "DEPOSIT", 7000.0), (9, NW_MARCH, 2000.0)]
    march = _payload(march_rows, month=3, opening=1500.0)
    april = _payload([(4, RETURNED, -7000.0), (6, NW_APRIL, 3000.0)], month=4, opening=_closing(march_rows, 1500.0))
    package = _package(("mar", march), ("apr", april))
    assert package["package_matches"][0]["gap_days"] == 30
    assert package["totals"]["true_revenue_total"] == 5000.0


def test_s3b_a_return_fifteen_days_after_its_deposit_in_one_statement_stays_counted_and_is_flagged():
    """S3 (b), R22's in-statement control: pass 4 keeps its 14 days, so a return 15 days after an equal deposit of its
    own statement leaves the deposit counted; with no equal deposit in March it is flagged on the statement and the
    package."""
    march_rows = [(9, NW_MARCH, 2000.0)]
    march = _payload(march_rows, month=3, opening=1500.0)
    april = _payload([(2, "DEPOSIT", 2500.0), (17, RETURNED, -2500.0)], month=4, opening=_closing(march_rows, 1500.0))
    package = _package(("mar", march), ("apr", april))
    assert _ledger_row(package, "apr", "transaction:1")["classification"]["revenue_tier"] == "counted_flagged"
    assert package["totals"]["true_revenue_total"] == 4500.0
    assert (package["totals"]["unmatched_deposit_return_count"],
            package["totals"]["unmatched_deposit_return_total"]) == (1, 2500.0)
    assert _served(april)["metrics"]["unmatched_deposit_return_locations"] == ["transaction:2"]
    assert "package_matches" not in package


def test_s3c_a_deposit_two_statements_back_is_never_matched():
    """S3 (c): only the immediately preceding statement is read: a February deposit returned in April stays counted,
    whether or not March sits between them."""
    february_rows = [(5, "DEPOSIT", 3000.0)]
    february = _payload(february_rows, month=2, opening=1500.0)
    march_rows = [(9, NW_MARCH, 2000.0)]
    march = _payload(march_rows, month=3, opening=_closing(february_rows, 1500.0))
    april = _payload([(2, RETURNED, -3000.0)], month=4,
                     opening=_closing(march_rows, _closing(february_rows, 1500.0)))
    for members in ((("feb", february), ("apr", april)), (("feb", february), ("mar", march), ("apr", april))):
        package = _package(*members)
        assert "package_matches" not in package
        assert _ledger_row(package, "feb", "transaction:1")["classification"]["revenue_tier"] == "counted_flagged"
        assert package["totals"]["unmatched_deposit_return_count"] == 1


def test_s4_a_return_in_another_account_is_flagged():
    march, april = _owners_example(april_number=ACCOUNT_B, april_opening=151500.0)
    package = _package(("mar", march), ("apr", april))
    assert "package_matches" not in package
    assert package["totals"]["true_revenue_total"] == 200000.0
    assert package["totals"]["unmatched_deposit_return_count"] == 1


def test_s5_a_partial_return_is_flagged_and_true_revenue_is_unchanged():
    march_rows = [(20, "DEPOSIT", 5000.0)]
    march = _payload(march_rows, month=3, opening=1500.0)
    april = _payload([(2, RETURNED, -1200.0), (6, NW_APRIL, 800.0)], month=4, opening=_closing(march_rows, 1500.0))
    package = _package(("mar", march), ("apr", april))
    assert "package_matches" not in package
    assert package["totals"]["true_revenue_total"] == 5800.0
    assert (package["totals"]["unmatched_deposit_return_count"],
            package["totals"]["unmatched_deposit_return_total"]) == (1, 1200.0)


def test_s6_statements_printing_no_account_digits_match_on_the_balance_chain():
    """S6: both statements print 'XXXXXXXX': April opening on March's closing balance is the same account; opening one
    dollar higher, it is not, and the return is flagged."""
    march = _payload(MARCH, month=3, opening=1500.0, number="XXXXXXXX")
    chained = _payload(APRIL, month=4, opening=_closing(MARCH, 1500.0), number="XXXXXXXX")
    package = _package(("mar", march), ("apr", chained))
    assert package["totals"]["true_revenue_total"] == 100000.0
    assert package["package_matches"][0]["credit"]["last4"] is None
    broken = _payload(APRIL, month=4, opening=_closing(MARCH, 1500.0) + 1.0, number="XXXXXXXX")
    package = _package(("mar", march), ("apr", broken))
    assert "package_matches" not in package
    assert package["totals"]["true_revenue_total"] == 200000.0
    assert package["totals"]["unmatched_deposit_return_count"] == 1


def test_s7_a_pair_inside_one_statement_is_pass_4_s_and_publishes_no_package_key():
    march_rows = [(9, NW_MARCH, 2000.0)]
    march = _payload(march_rows, month=3, opening=1500.0)
    april = _payload([(2, "DEPOSIT", 900.0), (9, RETURNED, -900.0)], month=4, opening=_closing(march_rows, 1500.0))
    package = _package(("mar", march), ("apr", april))
    deposit = _ledger_row(package, "apr", "transaction:1")["classification"]
    assert (deposit["revenue_match_method"], deposit["revenue_matched_rule"]) == (
        "matched_reversal_pair", "returned_deposit_amount_date_match")
    assert "package_match" not in deposit
    for key in ("package_matches", "debit_flags"):
        assert key not in package
    assert not any(key.startswith(("returned_deposit_cross_statement", "unmatched_deposit_return",
                                   "processor_chargeback", "package_match")) for key in package["totals"])
    assert "unmatched_deposit_return_count" not in _served(april)["metrics"]


#: S8: three processor chargebacks and adjustments, and the controls that are none: R22's returned mobile deposit (pass 4
#: pairs it), a chargeback fee, a deposit return's fee and a chargeback charge.
CHARGEBACK_ROWS = [(2, NW_APRIL, 5000.0), (3, "HRTLAND PMT SYS CHARGEBACK 123456", -350.0),
                   (4, "FABRIKAM MERCHANT SVCS MERCH CHBK", -400.0), (5, "FABRIKAM MERCHANT SVCS MERCH ADJ", -125.0),
                   (6, "SBB MDEPOSIT", 600.0), (8, "DEP RETURN CHARGEBACK", -600.0), (9, "CHARGEBACK FEE", -15.0),
                   (10, "DEP RETURN FEE", -20.0), (11, "CHBK CHRG", -10.0)]


def test_s8_processor_chargebacks_and_adjustments_are_flagged_never_deducted():
    march_rows = [(9, NW_MARCH, 2000.0)]
    march = _payload(march_rows, month=3, opening=1500.0)
    april = _payload(CHARGEBACK_ROWS, month=4, opening=_closing(march_rows, 1500.0))
    metrics = _served(april)["metrics"]
    assert (metrics["processor_chargeback_count"], metrics["processor_chargeback_total"],
            metrics["processor_chargeback_locations"]) == (3, 875.0, ["transaction:2", "transaction:3", "transaction:4"])
    assert "unmatched_deposit_return_count" not in metrics
    # Never deducted: the statement's figures are its own.
    assert metrics["true_revenue_total"] == april["metrics"]["true_revenue_total"] == 5000.0
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    assert (totals["processor_chargeback_count"], totals["processor_chargeback_total"]) == (3, 875.0)
    assert totals["true_revenue_total"] == 7000.0
    assert [(flag["kind"], flag.get("wording"), flag["source_location"]) for flag in package["debit_flags"]] == [
        ("processor_chargeback", "chargeback", "transaction:2"), ("processor_chargeback", "chargeback", "transaction:3"),
        ("processor_chargeback", "adjustment", "transaction:4")]
    assert "unmatched_deposit_return_count" not in totals


def test_s9_an_analyst_s_confirm_beats_the_match_and_the_flag_names_the_confirmed_deposit():
    from analysis.revenue import apply_serialized_revenue_review

    march, april = _owners_example()
    confirmed = apply_serialized_revenue_review(march, source_location="transaction:2", decision="confirm")
    package = _package(("mar", confirmed), ("apr", april))
    assert "package_matches" not in package
    assert package["totals"]["true_revenue_total"] == 200000.0
    deposit = _ledger_row(package, "mar", "transaction:2")["classification"]
    assert (deposit["revenue_tier"], deposit["revenue_review_status"]) == ("verified", "confirmed")
    assert "package_match" not in deposit
    assert package["debit_flags"] == [{
        "kind": "unmatched_deposit_return",
        "candidate_decided": {"job": "mar", "filename": "mar.pdf", "account_index": None, "source_location": "transaction:2",
                              "date": "2031-03-26", "decision": "confirmed"},
        "source_job": "apr", "source_document": "apr.pdf", "source_account": None, "source_currency": "USD",
        "source_location": "transaction:1", "date": "2031-04-01", "amount": -100000.0, "description": RETURNED,
    }]
    # Mark Non-Revenue agrees the money is not revenue: no match and no named candidate.
    rejected = apply_serialized_revenue_review(_owners_example()[0], source_location="transaction:2",
                                               decision="reject")
    package = _package(("mar", rejected), ("apr", april))
    assert "package_matches" not in package and "candidate_decided" not in package["debit_flags"][0]
    assert package["totals"]["true_revenue_total"] == 100000.0


def test_s10_the_listing_order_changes_nothing():
    march, april = _owners_example([*APRIL, (8, "DEPOSIT", 100000.0), *CHARGEBACK_ROWS[1:4]])
    forward = _package(("mar", march), ("apr", april))
    backward = _package(("apr", april), ("mar", march))
    assert forward["package_matches"] == backward["package_matches"]
    assert forward["debit_flags"] == backward["debit_flags"]
    assert forward["totals"] == backward["totals"]
    by_row = lambda package: {(row["source_job"], row["classification"]["source_location"]): row  # noqa: E731
                              for row in package["transactions"]}
    assert by_row(forward) == by_row(backward)


def _without_passes(monkeypatch, *members):
    """The package with its passes switched off: what it published before R2-OW15."""
    from webapp import app

    with monkeypatch.context() as patched:
        patched.setattr(app, "_package_matches", lambda members, rd_positions: {
            "overlays": {}, "matches": [], "debit_flags": [], "unchecked": {}, "moved": {}})
        return _package(*members)


def test_s11_no_debit_and_no_lender_reading_moves(monkeypatch):
    """S11, G7: April's NSF count, lender debits, withholding numerator, every debit's classification and contributions
    and its reversed_by are the same with and without March (the return's debit gains only its display note), and the
    package's gross figures, deposit counts, months and lender figures are the ones it published without its passes."""
    rows = [*APRIL, (10, "ONDECK CAPITAL DES:PAYMENT ID:1", -250.0), (12, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]
    march, april = _owners_example(rows)
    alone, together = _package(("apr", april)), _package(("mar", march), ("apr", april))
    for key in ("nsf_count", "lender_debits", "lender_debit_count", "withholding_numerator",
                "potential_lender_debit_total", "insurance_total", "debits", "credits", "deposit_count"):
        assert _doc(alone, "apr")[key] == _doc(together, "apr")[key], key
    assert (alone["totals"]["lender_debits"], alone["totals"]["withholding_numerator"]) == (
        together["totals"]["lender_debits"], together["totals"]["withholding_numerator"]) == (250.0, 250.0)
    assert alone["funders"] == together["funders"]
    for location in ("transaction:1", "transaction:3", "transaction:4"):
        before = _ledger_row(alone, "apr", location)["classification"]
        after = {key: value for key, value in _ledger_row(together, "apr", location)["classification"].items()
                 if key != "package_match"}
        assert after == before, location
    assert _ledger_row(together, "apr", "transaction:1")["classification"].get("reversed_by") is None
    before = _without_passes(monkeypatch, ("mar", march), ("apr", april))
    for key in ("total_credits", "total_posted_credits", "total_posted_credit_count", "total_debits", "cash_flow",
                "average_daily_balance", "months", "lender_debits", "lender_debit_count", "withholding_numerator",
                "nsf_count", "lenders_detected", "potential_lender_debit_total", "insurance_total",
                "flagged_position_total", "avg_monthly_credits"):
        assert together["totals"][key] == before["totals"][key], key
    assert [row["deposit_count"] for row in together["documents"]] == [row["deposit_count"] for row in before["documents"]]
    # What moves: the True, the non-revenue and the True-revenue basis, by the returned deposit.
    assert before["totals"]["true_revenue_total"] - together["totals"]["true_revenue_total"] == 100000.0
    assert together["totals"]["non_revenue_total"] - before["totals"]["non_revenue_total"] == 100000.0
    assert before["totals"]["withholding_denominator"] - together["totals"]["withholding_denominator"] == 100000.0


def test_s12_a_return_printed_twice_nets_one_deposit_and_adds_no_flag():
    march, april = _owners_example([(1, RETURNED, -100000.0), (1, RETURNED, -100000.0, "repeat"),
                                    (5, NW_APRIL, 50000.0)])
    assert april["statement"]["transactions"][1]["classification"]["duplicate_of"] == "transaction:1"
    package = _package(("mar", march), ("apr", april))
    assert len(package["package_matches"]) == 1
    assert package["totals"]["true_revenue_total"] == 100000.0
    assert "debit_flags" not in package
    # Viewed alone, April flags its return once, never its printed duplicate.
    assert _served(april)["metrics"]["unmatched_deposit_return_locations"] == ["transaction:1"]


def test_s13_a_correction_naming_a_credit_of_its_own_statement_is_never_netted_across():
    """S13: pass 4 pairs April's first DEPOSIT CORRECTION NORTHWIND with the equal NORTHWIND credit; the second one
    names that credit too (pass 4's guard, _undo_debit_names_a_credit), so the package never nets it against March's
    equal DEPOSIT: it stays flagged."""
    march_rows = [(20, "DEPOSIT", 700.0)]
    march = _payload(march_rows, month=3, opening=1500.0)
    april = _payload([(2, NW_APRIL, 700.0), (3, "DEPOSIT CORRECTION NORTHWIND", -700.0),
                      (6, "DEPOSIT CORRECTION NORTHWIND", -700.0)], month=4, opening=_closing(march_rows, 1500.0))
    package = _package(("mar", march), ("apr", april))
    assert "package_matches" not in package
    assert _ledger_row(package, "mar", "transaction:1")["classification"]["revenue_tier"] == "counted_flagged"
    assert [(flag["kind"], flag["source_location"]) for flag in package["debit_flags"]] == [
        ("unmatched_deposit_return", "transaction:3")]
    assert _served(april)["metrics"]["unmatched_deposit_return_locations"] == ["transaction:3"]


# ---------------------------------------------------------------- the scaffold

#: A package of two statements of account A with no return and no chargeback.
NO_PAIR_MARCH = [(5, NW_MARCH, 900.0), (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0), (12, "DEPOSIT", 400.0)]
NO_PAIR_APRIL = [(3, NW_APRIL, 800.0), (6, "ONDECK CAPITAL DES:PAYMENT ID:1", -250.0)]


def _no_pair_package():
    march = _payload(NO_PAIR_MARCH, month=3, opening=1500.0)
    april = _payload(NO_PAIR_APRIL, month=4, opening=_closing(NO_PAIR_MARCH, 1500.0))
    return _package(("mar", march), ("apr", april))


def _canonical(payload):
    """The payload as JSON, every record's classification_version read as one placeholder (R2-B16 moves it)."""
    return re.sub(r'"classification_version": "[^"]*"', '"classification_version": "<version>"',
                  json.dumps(payload, sort_keys=True, indent=1))


def test_a_package_without_a_qualifying_pair_is_byte_identical_to_the_pinned_payload():
    """The pinned payload is the package the base of R2-OW15 (5ee6e0b) built from these fabricated statements."""
    assert _canonical(_no_pair_package()) == FIXTURE.read_text(encoding="utf-8")


def test_a_member_analysed_with_older_rules_or_with_no_currency_is_marked_and_never_matched():
    from tests.test_webapp_true_revenue import _untiered

    march, april = _owners_example()
    older = _package(("mar", _untiered(march)), ("apr", april))
    assert "package_matches" not in older
    assert _doc(older, "mar")["package_match_unchecked"] == "older_rules"
    assert "package_match_unchecked" not in _doc(older, "apr")
    assert older["totals"]["package_match_unchecked_count"] == 1
    assert older["totals"]["unmatched_deposit_return_count"] == 1
    no_currency = copy.deepcopy(march)
    no_currency["statement"]["currency"] = None
    unknown = _package(("mar", no_currency), ("apr", april))
    assert "package_matches" not in unknown
    assert _doc(unknown, "mar")["package_match_unchecked"] == "no_currency"
    assert unknown["totals"]["package_match_unchecked_count"] == 1
    # A package of one statement names nothing as unchecked, nor does a statement that prints no row.
    single = _package(("mar", _untiered(march)))
    assert "package_match_unchecked" not in _doc(single, "mar")
    assert "package_match_unchecked_count" not in single["totals"]
    empty = _payload([], month=2, opening=1500.0)
    quiet = _package(("feb", empty), ("mar", march), ("apr", april))
    assert "package_match_unchecked" not in _doc(quiet, "feb")
    assert "package_match_unchecked_count" not in quiet["totals"]
    assert len(quiet["package_matches"]) == 1


@pytest.mark.parametrize("mode", ["true_revenue", "verified_revenue", "legacy_eligible_deposits"])
def test_the_withholding_basis_loses_the_moved_deposit_in_the_true_revenue_mode_only(mode, monkeypatch):
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    march, april = _owners_example([*APRIL, (10, "ONDECK CAPITAL DES:PAYMENT ID:1", -250.0)])
    assert {march["metrics"]["withholding_denominator_mode"], april["metrics"]["withholding_denominator_mode"]} == {
        mode}
    stored = march["metrics"]["withholding_denominator"] + april["metrics"]["withholding_denominator"]
    totals = _package(("mar", march), ("apr", april))["totals"]
    assert totals["withholding_denominator"] == (stored - 100000.0 if mode == "true_revenue" else stored)
    assert totals["withholding_denominator"] == {"true_revenue": 100000.0, "verified_revenue": 100000.0,
                                                 "legacy_eligible_deposits": 200000.0}[mode]
    assert totals["withholding_numerator"] == 250.0


def test_the_package_downloads_list_each_match_and_each_flag():
    from webapp.app import _package_csv

    march, april = _owners_example([*APRIL, *CHARGEBACK_ROWS[1:2]])
    rows = list(csv.reader(io.StringIO(_package_csv(_package(("mar", march), ("apr", april))))))
    cells = {(row[0], row[1]): row[2] for row in rows[1:] if len(row) == 3}
    assert cells[("package_match_1", "kind")] == "returned_deposit"
    assert json.loads(cells[("package_match_1", "credit")])["source_location"] == "transaction:2"
    assert cells[("package_match_1", "gap_days")] == "6"
    assert cells[("debit_flag_1", "kind")] == "processor_chargeback"
    assert cells[("debit_flag_1", "wording")] == "chargeback"
    assert cells[("debit_flag_1", "description")] == "HRTLAND PMT SYS CHARGEBACK 123456"
    assert cells[("totals", "returned_deposit_cross_statement_total")] == "100000.0"
    assert cells[("totals", "processor_chargeback_total")] == "350.0"


def test_the_member_loop_reads_the_passes_one_tiering_helper():
    """The passes and the member loop decide 'tiered' by one helper (`_member_tiered`), so a member the passes read is
    never one the loop publishes without its tier figures."""
    import inspect

    from webapp import app

    loop = inspect.getsource(app._package_analysis)
    assert "tiered = _member_tiered(statement_transactions)" in loop
    assert "_member_tiered(" in inspect.getsource(app._package_matches)


def test_the_route_serves_each_match_s_legs_with_their_account_index_never_masked():
    """The served package masks every key named `account` as a printed account number (`_masked`), so a match's leg
    names its account `account_index`, and the route serves the match, the flags and the overlay end to end."""
    from webapp.app import app, store

    march, april = _owners_example([*APRIL, *CHARGEBACK_ROWS[1:2]])
    ids = []
    for name, payload in (("mar.pdf", march), ("apr.pdf", april)):
        job = store.create(name)
        store.set_result(job.id, f"# {name}", f"<h1>{name}</h1>", analysis=payload)
        ids.append(job.id)
    response = app.test_client().get(f"/package_analysis?ids={','.join(ids)}")
    assert response.status_code == 200
    body = response.get_json()
    [match] = body["package_matches"]
    for leg in (match["credit"], match["debit"]):
        assert "account" not in leg and leg["account_index"] is None and leg["last4"] == "1010"
    assert (match["credit"]["job"], match["debit"]["job"]) == tuple(ids)
    assert body["totals"]["true_revenue_total"] == 100000.0
    assert [flag["kind"] for flag in body["debit_flags"]] == ["processor_chargeback"]
    overlaid = [row for row in body["transactions"] if row["classification"].get("package_match")]
    assert len(overlaid) == 2
