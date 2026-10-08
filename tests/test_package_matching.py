"""Owner ruling 2026-10-02 (the underwriter's Q6, "2"; audit I42; true revenue spec §6.2's package passes, §9.1, §9.2,
§11; R2-OW15): a deposited item returned in the next statement of the same account leaves the package's True revenue,
a redeposit counts once, and the returns no statement or package pairs and the processor chargebacks and adjustments
are flagged, never deducted. The passes are package-only: a statement viewed alone keeps its own figures.

Owner ruling 2026-10-02 (the underwriter's Q4, "Let's go with option 2 and I'll review it anyways"; audit I30; R2-OW16):
within a package, a counted deposit that prints no payer, matched to an exact-cents transfer out of another of the
business's accounts 0 to 2 days before it, is held (`own_account_transfer_matched`) and listed; Confirm Revenue
releases it into True and marks it Verified. An already-held deposit that pairs the same way is annotated only.

Fabricated statements only (CONTOSO BAKERY LLC, account A 000000001010 and account B 000000002020 at Sample Bank,
NORTHWIND and FABRIKAM payers, SAMPLE PERSON the person-to-person sender, neutral amounts), analysed by the real
analysis path (as tests/test_webapp_studio_views._report does, with a bank, an account number and a currency) and
packaged by webapp.app._package_analysis(jobs, settings={})."""
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


def _report(rows, *, month, opening, number=ACCOUNT_A, currency="USD", name=HOLDER):
    """One month of account `number` (the 1st to the 28th of 2031) analysed, every row with its running balance. A row
    `(day, description, amount, "repeat")` prints the row before it a second time, its running balance included (a
    proven duplicate, which the bank's figures do not count: the statement reconciles without it). A row whose day is
    None prints no date (R2-OW16's T16)."""
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    txns, printed, balance = [], [], opening
    for row in rows:
        day, description, amount = row[:3]
        if len(row) < 4:
            balance = round(balance + amount, 2)
        transaction = Transaction(date="" if day is None else f"2031-{month:02d}-{day:02d}", description=description,
                                  amount=amount, direction="credit" if amount > 0 else "debit", running_balance=balance)
        txns.append(transaction)
        if len(row) < 4:
            printed.append(transaction)
    fields = dict(bank=BANK, account_name=name, account_number=number, period_start=f"2031-{month:02d}-01",
                  period_end=f"2031-{month:02d}-28", beginning_balance=opening, ending_balance=balance,
                  currency=currency, currency_source="printed")
    statement = Statement(**fields, transactions=txns)
    return analyze_statement(statement, reconciliation=reconcile(Statement(**fields, transactions=printed)),
                             markdown="", sheets=[], model_used="fabricated-test")


def _payload(rows, *, month, opening, number=ACCOUNT_A, currency="USD", name=HOLDER):
    """One month of account `number`, as a statement's stored payload (`_report`)."""
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(_report(rows, month=month, opening=opening, number=number, currency=currency,
                                            name=name))


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


#: The owner's request of 2026-10-06 (lender payment changes; R2-OW18, part N): the keys that batch adds to every record
#: (`potential_payee_key`), every account's detection (`lender_payment_changes`) and a package
#: (`lender_payment_changes`, `lender_payment_changes_unchecked`).
R2_OW18_KEYS = frozenset({"potential_payee_key", "lender_payment_changes", "lender_payment_changes_unchecked"})
#: Audit round 3, R3-B02 (the owner's answer of 2026-10-07 to R3-73): the record field every record gains
#: (`represented_by`, null on every row of these fixtures).
R3_B02_KEYS = frozenset({"represented_by"})
#: Audit round 3, R3-B03: the metrics flag of R3-20's floor (`withholding_basis_below_floor`, false on these fixtures)
#: and the owner's answer of 2026-10-07 to R3-79's keys (the record field `lump_sum_payoff`, null on every row; the
#: metrics `lump_sum_payoff_total` and `_count`, 0; the detection list `lump_sum_payoffs`, empty).
R3_B03_KEYS = frozenset({"withholding_basis_below_floor", "lump_sum_payoff", "lump_sum_payoff_total",
                         "lump_sum_payoff_count", "lump_sum_payoffs"})


def _without_r2_ow18(node):
    """R2-OW18 (part N): the payload without the keys the owner's request of 2026-10-06 adds (and, audit round 3,
    R3-B02, the record field `represented_by`, and R3-B03's keys). `_canonical` applies it, and the golden comparisons
    read both sides through `_canonical`, as they read every classification_version as one placeholder. The pinned
    fixtures are never rewritten."""
    if isinstance(node, dict):
        return {key: _without_r2_ow18(value) for key, value in node.items()
                if key not in R2_OW18_KEYS and key not in R3_B02_KEYS and key not in R3_B03_KEYS}
    if isinstance(node, list):
        return [_without_r2_ow18(value) for value in node]
    return node


def _canonical(payload):
    """The payload as JSON, every record's classification_version read as one placeholder (R2-B16 moves it), without
    R2-OW18's keys (part N)."""
    payload = _without_r2_ow18(payload)
    return re.sub(r'"classification_version": "[^"]*"', '"classification_version": "<version>"',
                  json.dumps(payload, sort_keys=True, indent=1))


def test_a_package_without_a_qualifying_pair_is_byte_identical_to_the_pinned_payload():
    """The pinned payload is the package the base of R2-OW15 (5ee6e0b) built from these fabricated statements."""
    pinned = FIXTURE.read_text(encoding="utf-8")
    assert _canonical(json.loads(pinned)) == pinned
    assert _canonical(_no_pair_package()) == _canonical(json.loads(pinned))


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


# ---------------------------------------------------------------- Q4: own-account transfers (R2-OW16)

#: The owner's example: account A sends 12,340.17 to account B (its debit prints no internal designation, like the
#: owner's 'TRANSFER TO CHK 4821'), and B prints a bare DEPOSIT of the same cents.
TRANSFER_OUT = "ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521"
NW_A = "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1"
FABRIKAM_B = "FABRIKAM STORES INC DES:PAYMENT ID:2"
SENT = 12340.17


def _rows_a(debit=TRANSFER_OUT, amount=-SENT, day=3, extra=()):
    return [(2, NW_A, 20000.0), (day, debit, amount), *extra]


def _rows_b(credit="DEPOSIT", amount=SENT, day=3, extra=()):
    return [(day, credit, amount), *extra, (9, FABRIKAM_B, 2000.0)]


def _account_a(debit=TRANSFER_OUT, amount=-SENT, day=3, *, extra=(), currency="USD"):
    return _payload(_rows_a(debit, amount, day, extra), month=3, opening=50000.0, currency=currency)


def _account_b(credit="DEPOSIT", amount=SENT, day=3, *, extra=(), number=ACCOUNT_B, currency="USD", name=HOLDER):
    return _payload(_rows_b(credit, amount, day, extra), month=3, opening=1500.0, number=number, currency=currency,
                    name=name)


def _owners_transfer(**b):
    return _package(("a", _account_a()), ("b", _account_b(**b)))


def _two_account_document(a_rows, b_rows):
    """Accounts A and B printed in ONE document (as tests/test_webapp_true_revenue._pair_document builds one), R-d run
    over them (identify_internal_transfers)."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    first = _report(a_rows, month=3, opening=50000.0).accounts[0]
    second = _report(b_rows, month=3, opening=1500.0, number=ACCOUNT_B).accounts[0]
    transfers, notes = identify_internal_transfers([first, second])
    roster = [AccountRosterEntry(HOLDER, "checking", "1010", "published", published_index=0),
              AccountRosterEntry(HOLDER, "checking", "2020", "published", published_index=1)]
    return document_report_to_dict(DocumentReport(accounts=[first, second], internal_transfers=transfers,
                                                  integrity_notes=notes, account_roster=roster,
                                                  document_period=("2031-03-01", "2031-03-28")))


def _tier(package, job_id, location):
    record = _ledger_row(package, job_id, location)["classification"]
    return record["revenue_tier"], record["revenue_tier_reason"]


def _q4_keys(totals):
    return {key for key in totals if key.startswith("own_account_transfer")}


HELD = ("excluded_pending_review", "own_account_transfer_matched")
COUNTED = ("counted_flagged", "no_payer_printed")


@pytest.mark.parametrize(("text", "paper_or_cash"), [
    ("DEPOSIT", False), ("TELLER DEPOSIT", False), ("COUNTER CREDIT", False), ("BRANCH DEPOSIT", False),
    ("NIGHT DROP DEPOSIT", True), ("CASH DEPOSIT", True), ("ATM CASH DEPOSIT", True),
    # A residual the reader keeps: §8.2's cash form reads NIGHT DEP and NIGHT DROP as whole words, never NIGHT DEPOSIT,
    # and the guard needs the form (R2-B13 reads the forms unchanged), so a bare NIGHT DEPOSIT stays eligible.
    ("NIGHT DEPOSIT", False), ("NIGHT DEP", True),
    ("ATM DEPOSIT", True), ("ABM DEPOSIT", True), ("COIN DEPOSIT", True), ("SMART SAFE DEPOSIT", True),
    ("VAULT DEPOSIT", True), ("PRE ENCODED DEPOSIT", True), ("CPS DEVICE DEPOSIT", True), ("MOBILE DEPOSIT", True),
    ("REMOTE DEPOSIT", True), ("OK SAMPLEVILLE 1234 E 51ST USWALGREENS W1234", True),
    ("INVOICES NORTHWIND SUPPLY", False), ("ONLINE TRANSFER", False),
])
def test_the_reader_reads_a_check_or_cash_device_deposit_never_a_teller_counter_or_branch_one(text, paper_or_cash):
    from analysis.transaction_classifier import paper_or_cash_deposit

    assert paper_or_cash_deposit(text) is paper_or_cash


def test_two_members_are_two_accounts_only_on_four_printed_digits_that_differ():
    from webapp.app import _different_accounts

    def member(key, digits, currency="USD"):
        return {"key": key, "digits": digits, "currency": currency}

    assert _different_accounts(member(("a", None), "000000001010"), member(("b", None), "000000002020"))
    assert _different_accounts(member(("d", 1), "000000001010"), member(("d", 2), "000000002020"))
    assert _different_accounts(member(("a", None), "000000001010"), member(("b", None), "000000091010"))  # conflict
    assert not _different_accounts(member(("a", None), "000000001010"), member(("b", None), "1010"))
    assert not _different_accounts(member(("a", None), "000000001010"), member(("a", None), "000000002020"))
    assert not _different_accounts(member(("a", None), "000000001010"), member(("b", None), "020"))
    assert not _different_accounts(member(("a", None), "000000001010"), member(("b", None), "000000002020", "CAD"))
    assert not _different_accounts(member(("a", None), "000000001010", None), member(("b", None), "000000002020", None))


def test_t1_the_owner_s_example_holds_the_deposit_the_other_account_sent():
    """T1: today the package counts the 12,340.17 twice (True 34,340.17, approved); now B's DEPOSIT is held as a
    transfer out of A, listed, and B viewed alone keeps its figures."""
    a, b = _account_a(), _account_b()
    stored = copy.deepcopy((a, b))
    package = _package(("a", a), ("b", b))
    totals = package["totals"]
    assert (totals["true_revenue_total"], totals["verified_revenue_total"], totals["excluded_pending_review_total"]) == (
        22000.0, 22000.0, SENT)
    assert (totals["own_account_transfer_held_count"], totals["own_account_transfer_held_total"]) == (1, SENT)
    assert "own_account_transfer_already_held_count" not in totals
    assert totals["revenue_review_items"] == 1
    assert totals["decision"] == "review_required"  # held is 86% of B's posted credits
    assert totals["excluded_pending_review_by_reason"]["own_account_transfer_matched"] == {"count": 1, "total": SENT}
    deposit = _ledger_row(package, "b", "transaction:1")["classification"]
    assert (deposit["revenue_tier"], deposit["revenue_tier_reason"]) == HELD
    assert (deposit["revenue_classification"], deposit["revenue_review_required"]) == ("unverified_deposit", True)
    assert deposit["contributes_to_true_revenue"] is False
    assert deposit["contributes_to_excluded_pending_review"] is True
    assert deposit["contributes_to_counted_flagged"] is False
    assert (deposit["revenue_initial_classification"], deposit["revenue_review_status"]) == ("unverified_deposit",
                                                                                            "pending")
    debit_leg = {"job": "a", "filename": "a.pdf", "account_index": None, "source_location": "transaction:2",
                 "date": "2031-03-03", "amount": -SENT, "bank": BANK, "last4": "1010"}
    credit_leg = {"job": "b", "filename": "b.pdf", "account_index": None, "source_location": "transaction:1",
                  "date": "2031-03-03", "amount": SENT, "bank": BANK, "last4": "2020"}
    assert deposit["package_match"] == {"kind": "own_account_transfer", "moved": True, "debit": debit_leg, "gap_days": 0,
                                        "tier_before": "counted_flagged", "reason_before": "no_payer_printed"}
    debit = _ledger_row(package, "a", "transaction:2")["classification"]
    assert debit["package_match"] == {"kind": "own_account_transfer", "credit": credit_leg, "moved": True}
    assert package["package_matches"] == [{
        "kind": "own_account_transfer", "moved": True, "gap_days": 0,
        "credit": {**credit_leg, "currency": "USD", "tier_before": "counted_flagged", "reason_before": "no_payer_printed"},
        "debit": {**debit_leg, "currency": "USD"},
    }]
    assert (_doc(package, "a")["package_match_count"], _doc(package, "b")["package_match_count"]) == (1, 1)
    assert _doc(package, "b")["true_revenue_total"] == 2000.0
    assert "debit_flags" not in package and "package_match_unchecked_count" not in totals
    assert (a, b) == stored  # nothing is written back
    # B alone: as today.
    alone = _package(("b", b))
    assert (alone["totals"]["true_revenue_total"], alone["totals"]["decision"]) == (14340.17, "approved")
    assert not _q4_keys(alone["totals"]) and "package_matches" not in alone
    assert _served(b)["metrics"]["true_revenue_total"] == 14340.17


def test_t1_today_the_package_counted_the_transfer_twice(monkeypatch):
    totals = _without_passes(monkeypatch, ("a", _account_a()), ("b", _account_b()))["totals"]
    assert (totals["true_revenue_total"], totals["verified_revenue_total"], totals["decision"]) == (
        34340.17, 22000.0, "approved")


def test_t1b_the_owner_s_example_in_one_two_account_document_is_held_too():
    """T1b: R-d nets only same-day legs printing an internal designation, so in ONE document the owner's example is
    counted twice today (True 34,340.17); now B's DEPOSIT is held the same way, inside the job."""
    document = _two_account_document(_rows_a(), _rows_b())
    assert document["document"]["internal_transfers"] == []
    package = _package(("doc", document))
    totals = package["totals"]
    assert (totals["true_revenue_total"], totals["verified_revenue_total"], totals["excluded_pending_review_total"]) == (
        22000.0, 22000.0, SENT)
    assert (totals["own_account_transfer_held_count"], totals["own_account_transfer_held_total"]) == (1, SENT)
    assert totals["decision"] == "review_required"
    [match] = package["package_matches"]
    assert (match["kind"], match["moved"], match["gap_days"]) == ("own_account_transfer", True, 0)
    assert (match["credit"]["job"], match["credit"]["account_index"], match["credit"]["last4"]) == ("doc", 2, "2020")
    assert (match["debit"]["job"], match["debit"]["account_index"], match["debit"]["last4"]) == ("doc", 1, "1010")
    [deposit] = [row for row in package["transactions"] if row["source_account"] == 2 and row["amount"] == SENT]
    assert (deposit["classification"]["revenue_tier"], deposit["classification"]["revenue_tier_reason"]) == HELD


def test_t2_a_deposit_two_days_after_is_held_three_days_after_counted():
    assert _tier(_owners_transfer(day=5), "b", "transaction:1") == HELD
    assert _owners_transfer(day=5)["package_matches"][0]["gap_days"] == 2
    late = _owners_transfer(day=6)
    assert _tier(late, "b", "transaction:1") == COUNTED
    assert "package_matches" not in late and not _q4_keys(late["totals"])


def test_t3_a_deposit_before_the_transfer_out_is_counted():
    package = _package(("a", _account_a(day=5)), ("b", _account_b(day=3)))
    assert _tier(package, "b", "transaction:1") == COUNTED
    assert package["totals"]["true_revenue_total"] == 34340.17


def test_t4_a_round_sum_is_never_matched():
    package = _package(("a", _account_a(amount=-12300.0)), ("b", _account_b(amount=12300.0)))
    assert _tier(package, "b", "transaction:1") == COUNTED
    assert "package_matches" not in package


def test_t5_a_person_to_person_leg_is_never_matched():
    zelle = _package(("a", _account_a("ZELLE PAYMENT TO CONTOSO BAKERY")), ("b", _account_b()))
    assert _tier(zelle, "b", "transaction:1") == COUNTED
    assert "package_matches" not in zelle
    venmo = _owners_transfer(credit="VENMO CASHOUT SAMPLE PERSON")
    assert _tier(venmo, "b", "transaction:1") == ("counted_flagged", "p2p")
    assert "package_matches" not in venmo


@pytest.mark.parametrize(("debit", "expected"), [
    ("ONLINE BANKING TRANSFER TO CHK 9999 CONF 5521", COUNTED),
    ("ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521", HELD),
    ("ONLINE TRANSFER TO *9999", COUNTED),
    ("ONLINE TRANSFER TO XXXX 9999", COUNTED),
    ("ONLINE TRANSFER TO XXXXXX2020", HELD),
    ("ONLINE BANKING TRANSFER CONF 5521", HELD),
])
def test_t6_a_transfer_out_printing_another_account_never_pairs(debit, expected):
    assert _tier(_package(("a", _account_a(debit)), ("b", _account_b())), "b", "transaction:1") == expected


def test_t7_a_transfer_out_and_a_deposit_in_one_account_s_two_statements_are_counted():
    march_rows = [(2, NW_A, 20000.0), (28, "ONLINE BANKING TRANSFER CONF 5521", -777.31)]
    march = _payload(march_rows, month=3, opening=50000.0)
    april = _payload([(1, "DEPOSIT", 777.31), (6, NW_APRIL, 900.0)], month=4, opening=_closing(march_rows, 50000.0))
    package = _package(("mar", march), ("apr", april))
    assert _tier(package, "apr", "transaction:1") == COUNTED
    assert "package_matches" not in package


def test_t8_r_d_s_designated_pair_in_one_document_stays_r_d_s():
    document = _two_account_document(_rows_a("ONLINE TRANSFER TO CHK 2020"),
                                     _rows_b("ONLINE TRANSFER FROM CHK 1010"))
    assert len(document["document"]["internal_transfers"]) == 1
    package = _package(("doc", document))
    assert package["totals"]["true_revenue_total"] == 22000.0
    assert "package_matches" not in package and not _q4_keys(package["totals"])


@pytest.mark.parametrize(("credit", "tier"), [
    (NW_A, ("verified", None)),
    ("INVOICES NORTHWIND SUPPLY", ("counted_flagged", "named_payer_unlabelled")),
    ("ONLINE TRANSFER FROM CHK 1010", ("non_revenue", None)),
    ("MOBILE DEPOSIT", ("counted_flagged", "check_deposit")),
])
def test_t9_a_deposit_naming_a_payer_or_already_out_of_true_is_never_moved(credit, tier):
    package = _owners_transfer(credit=credit)
    assert _tier(package, "b", "transaction:1") == tier
    assert "package_match" not in _ledger_row(package, "b", "transaction:1")["classification"]
    assert "package_matches" not in package and not _q4_keys(package["totals"])


@pytest.mark.parametrize(("credit", "reason"), [
    ("TRANSFER CREDIT", "transfer_no_counterparty"),
    ("CONTOSO BAKERY LLC", "holder_name"),
    ("INCOMING WIRE", "wire_no_sender"),
])
def test_t9_an_already_held_deposit_that_pairs_is_annotated_only(credit, reason, monkeypatch):
    before = _without_passes(monkeypatch, ("a", _account_a()), ("b", _account_b(credit)))
    package = _owners_transfer(credit=credit)
    record = _ledger_row(package, "b", "transaction:1")["classification"]
    assert (record["revenue_tier"], record["revenue_tier_reason"]) == ("excluded_pending_review", reason)
    assert record["package_match"] == {
        "kind": "own_account_transfer", "moved": False, "gap_days": 0, "tier_before": "excluded_pending_review",
        "reason_before": reason,
        "debit": {"job": "a", "filename": "a.pdf", "account_index": None, "source_location": "transaction:2",
                  "date": "2031-03-03", "amount": -SENT, "bank": BANK, "last4": "1010"}}
    unannotated = {key: value for key, value in record.items() if key != "package_match"}
    assert unannotated == _ledger_row(before, "b", "transaction:1")["classification"]
    assert _ledger_row(package, "a", "transaction:2")["classification"]["package_match"]["moved"] is False
    totals = package["totals"]
    assert (totals["own_account_transfer_already_held_count"], totals["own_account_transfer_already_held_total"]) == (
        1, SENT)
    assert "own_account_transfer_held_count" not in totals
    for key in ("true_revenue_total", "verified_revenue_total", "excluded_pending_review_total", "revenue_review_items",
                "decision", "withholding_denominator"):
        assert totals[key] == before["totals"][key], key
    assert [match["moved"] for match in package["package_matches"]] == [False]


@pytest.mark.parametrize("amount", [4200.00, 4213.57])
def test_t9_a_zelle_deposit_held_as_the_holder_s_name_is_never_annotated(amount):
    """The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): under Yes (this file's settings={}) a
    Zelle deposit from the holder's own name is held as holder_name, and PNC's 'ZEL FROM' escapes the consumer rail;
    pass 2 still never matches it (Q4 (2026-10-02): never P2P; true_revenue.zelle_deposit). 4,200.00 is the brief's
    case (a round sum, refused anyway); 4,213.57 is refused by the Zelle test alone."""
    package = _package(("a", _account_a("ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521", amount=-amount, day=2)),
                       ("b", _account_b("ZEL FROM CONTOSO BAKERY LLC", amount=amount)))
    record = _ledger_row(package, "b", "transaction:1")["classification"]
    assert (record["revenue_tier"], record["revenue_tier_reason"]) == ("excluded_pending_review", "holder_name")
    assert "package_match" not in record
    assert "package_matches" not in package and not _q4_keys(package["totals"])
    # The same held deposit printed without the rail is annotated (T9's arm), so the rail is what keeps it out.
    plain = _package(("a", _account_a("ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521", amount=-4213.57, day=2)),
                     ("b", _account_b("CONTOSO BAKERY LLC", amount=4213.57)))
    assert _ledger_row(plain, "b", "transaction:1")["classification"]["package_match"]["moved"] is False


def test_t9_a_counted_deposit_takes_the_transfer_before_a_held_one():
    package = _owners_transfer(extra=[(4, "TRANSFER CREDIT", SENT)])
    assert _tier(package, "b", "transaction:1") == HELD
    assert "package_match" not in _ledger_row(package, "b", "transaction:2")["classification"]
    assert "own_account_transfer_already_held_count" not in package["totals"]


def test_t9_a_premium_trust_deposit_is_never_annotated():
    package = _owners_transfer(name="CONTOSO BAKERY PREMIUM TRUST ACCOUNT")
    assert _tier(package, "b", "transaction:1") == ("excluded_pending_review", "premium_trust_account")
    assert "package_matches" not in package and not _q4_keys(package["totals"])


@pytest.mark.parametrize(("credit", "expected"), [
    ("MOBILE DEPOSIT", ("counted_flagged", "check_deposit")),
    ("ATM CASH DEPOSIT", COUNTED),
    ("CASH DEPOSIT", COUNTED),
    ("NIGHT DROP DEPOSIT", COUNTED),
    ("OK SAMPLEVILLE 1234 E 51ST USWALGREENS W1234", COUNTED),  # R2-OW14's retail cash load is cash
    ("TELLER DEPOSIT", HELD),
    ("COUNTER CREDIT", HELD),
    ("BRANCH DEPOSIT", HELD),
])
def test_t10_a_check_or_cash_device_deposit_is_never_matched(credit, expected):
    assert _tier(_owners_transfer(credit=credit), "b", "transaction:1") == expected


def test_t11_one_transfer_out_holds_one_deposit():
    package = _package(("a", _account_a(amount=-500.25)),
                       ("b", _account_b(amount=500.25, extra=[(4, "DEPOSIT", 500.25)])))
    assert _tier(package, "b", "transaction:1") == HELD
    assert _tier(package, "b", "transaction:2") == COUNTED
    assert package["totals"]["own_account_transfer_held_count"] == 1


def test_t12_confirm_revenue_releases_the_held_deposit_into_true_and_marks_it_verified():
    """T12 through the routes: Confirm Revenue on B's held DEPOSIT is B's own decision (§10.7): the row turns Verified
    on B and is never matched again; Reset restores the rule and the match; Mark Non-Revenue keeps it out."""
    from webapp.app import app, store

    ids = {}
    for name, payload in (("a", _account_a()), ("b", _account_b())):
        job = store.create(f"{name}.pdf")
        store.set_result(job.id, f"# {name}", f"<h1>{name}</h1>", analysis=payload)
        ids[name] = job.id
    client = app.test_client()
    url = f"/package_analysis?ids={ids['a']},{ids['b']}"

    def decide(decision):
        response = client.post(f"/analysis/{ids['b']}/revenue-review",
                               json={"source_location": "transaction:1", "decision": decision})
        assert response.status_code == 200
        return response.get_json()["analysis"]

    def package():
        body = client.get(url).get_json()
        deposit = next(row for row in body["transactions"] if row["source_job"] == ids["b"]
                       and row["classification"]["source_location"] == "transaction:1")["classification"]
        return body["totals"], deposit

    totals, deposit = package()
    assert (deposit["revenue_tier"], deposit["revenue_tier_reason"]) == HELD
    assert totals["own_account_transfer_held_total"] == SENT
    alone = decide("confirm")
    record = alone["statement"]["transactions"][0]["classification"]
    assert (record["revenue_tier"], record["revenue_review_status"]) == ("verified", "confirmed")
    assert alone["metrics"]["verified_revenue_total"] == 14340.17
    totals, deposit = package()
    assert (deposit["revenue_tier"], deposit["revenue_review_status"]) == ("verified", "confirmed")
    assert "package_match" not in deposit
    assert (totals["true_revenue_total"], totals["verified_revenue_total"], totals["excluded_pending_review_total"]) == (
        34340.17, 34340.17, 0.0)
    assert not _q4_keys(totals)
    decide("reset")
    totals, deposit = package()
    assert (deposit["revenue_tier"], deposit["revenue_tier_reason"]) == HELD
    assert (totals["verified_revenue_total"], totals["own_account_transfer_held_total"]) == (22000.0, SENT)
    decide("reject")
    totals, deposit = package()
    assert deposit["revenue_tier"] == "non_revenue" and "package_match" not in deposit
    assert totals["true_revenue_total"] == 22000.0 and not _q4_keys(totals)


def test_t13_the_listing_order_changes_nothing():
    a, b = _account_a(extra=[(4, "ONLINE TRANSFER TO CHK 2020", -640.33)]), _account_b(
        extra=[(5, "TRANSFER CREDIT", 640.33)])
    forward, backward = _package(("a", a), ("b", b)), _package(("b", b), ("a", a))
    assert [match["moved"] for match in forward["package_matches"]] == [True, False]
    assert forward["package_matches"] == backward["package_matches"]
    assert forward["totals"] == backward["totals"]
    by_row = lambda package: {(row["source_job"], row["classification"]["source_location"]): row  # noqa: E731
                              for row in package["transactions"]}
    assert by_row(forward) == by_row(backward)


def test_t14_two_currencies_are_never_two_of_the_business_s_accounts():
    package = _package(("a", _account_a(currency="CAD")), ("b", _account_b()))
    assert _tier(package, "b", "transaction:1") == COUNTED
    assert "package_matches" not in package


@pytest.mark.parametrize("mode", ["true_revenue", "verified_revenue", "legacy_eligible_deposits"])
def test_t15_the_true_revenue_basis_loses_the_held_deposit(mode, monkeypatch):
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    a = _account_a(extra=[(10, "ONDECK CAPITAL DES:PAYMENT ID:1", -250.0)])
    b = _account_b()
    stored = a["metrics"]["withholding_denominator"] + b["metrics"]["withholding_denominator"]
    totals = _package(("a", a), ("b", b))["totals"]
    assert totals["withholding_denominator"] == (round(stored - SENT, 2) if mode == "true_revenue" else stored)
    assert totals["withholding_denominator"] == {"true_revenue": 22000.0, "verified_revenue": 22000.0,
                                                 "legacy_eligible_deposits": 34340.17}[mode]
    assert totals["withholding_numerator"] == 250.0


def test_t16_an_undated_transfer_out_is_never_matched():
    package = _package(("a", _account_a(day=None)), ("b", _account_b()))
    assert _tier(package, "b", "transaction:1") == COUNTED
    assert "package_matches" not in package


#: T17: accounts A and B with no qualifying pair (a transfer out five days before an equal deposit, a card purchase).
NO_TRANSFER_A = [(2, NW_A, 900.0), (3, "ONLINE BANKING TRANSFER TO CHK 2020 CONF 5521", -456.78),
                 (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]
NO_TRANSFER_B = [(8, "DEPOSIT", 456.78), (12, FABRIKAM_B, 800.0)]
NO_TRANSFER_FIXTURE = FIXTURE.parent / "no_transfer_pair_package.json"


def _no_transfer_package():
    return _package(("a", _payload(NO_TRANSFER_A, month=3, opening=1500.0)),
                    ("b", _payload(NO_TRANSFER_B, month=3, opening=500.0, number=ACCOUNT_B)))


def test_t17_a_package_of_two_accounts_without_a_qualifying_pair_is_byte_identical_to_the_pinned_payload():
    """The pinned payload is the package the base of R2-OW16 (fabb8ae) built from these fabricated statements."""
    pinned = NO_TRANSFER_FIXTURE.read_text(encoding="utf-8")
    assert _canonical(json.loads(pinned)) == pinned
    assert _canonical(_no_transfer_package()) == _canonical(json.loads(pinned))


def test_t18_a_statement_printing_no_account_number_is_never_matched_and_is_named():
    package = _owners_transfer(number="XXXX")
    assert _tier(package, "b", "transaction:1") == COUNTED
    assert "package_matches" not in package
    assert _doc(package, "b")["package_match_unchecked"] == "no_account_number"
    assert "package_match_unchecked" not in _doc(package, "a")
    assert package["totals"]["package_match_unchecked_count"] == 1
    # A package of that statement alone names nothing.
    assert "package_match_unchecked" not in _doc(_package(("b", _account_b(number="XXXX"))), "b")


def test_t19_a_transfer_out_printed_twice_holds_one_deposit():
    a = _account_a(extra=[(3, TRANSFER_OUT, -SENT, "repeat")])
    assert a["statement"]["transactions"][2]["classification"]["duplicate_of"] == "transaction:2"
    package = _package(("a", a), ("b", _account_b(extra=[(4, "DEPOSIT", SENT)])))
    assert _tier(package, "b", "transaction:1") == HELD
    assert _tier(package, "b", "transaction:2") == COUNTED
    assert package["totals"]["own_account_transfer_held_count"] == 1
    assert "package_match" not in _ledger_row(package, "a", "transaction:3")["classification"]


def test_q4_never_moves_a_debit_or_a_gross_figure(monkeypatch):
    """Pass 2 holds a tier only: every debit's classification and contributions, the gross figures, the deposit
    counts, the lender figures and the numerator are the ones the package published without its passes."""
    a = _account_a(extra=[(10, "ONDECK CAPITAL DES:PAYMENT ID:1", -250.0)])
    b = _account_b()
    together, before = _package(("a", a), ("b", b)), _without_passes(monkeypatch, ("a", a), ("b", b))
    for location in ("transaction:2", "transaction:3"):
        after = {key: value for key, value in _ledger_row(together, "a", location)["classification"].items()
                 if key != "package_match"}
        assert after == _ledger_row(before, "a", location)["classification"], location
    for key in ("total_credits", "total_posted_credits", "total_posted_credit_count", "total_debits", "cash_flow",
                "average_daily_balance", "months", "lender_debits", "lender_debit_count", "withholding_numerator",
                "nsf_count", "lenders_detected", "potential_lender_debit_total", "insurance_total",
                "flagged_position_total", "avg_monthly_credits"):
        assert together["totals"][key] == before["totals"][key], key
    assert [row["deposit_count"] for row in together["documents"]] == [row["deposit_count"] for row in before["documents"]]
    assert before["totals"]["true_revenue_total"] - together["totals"]["true_revenue_total"] == pytest.approx(SENT)


def test_q4_s_matches_download_with_the_package():
    from webapp.app import _package_csv

    rows = list(csv.reader(io.StringIO(_package_csv(_owners_transfer()))))
    cells = {(row[0], row[1]): row[2] for row in rows[1:] if len(row) == 3}
    assert cells[("package_match_1", "kind")] == "own_account_transfer"
    assert cells[("package_match_1", "moved")] == "True"
    assert json.loads(cells[("package_match_1", "credit")])["reason_before"] == "no_payer_printed"
    assert cells[("totals", "own_account_transfer_held_total")] == str(SENT)


# ---------------------------------------------------------------- audit round 3, R3-B03 (R3-72): member rows
# A member's document row printed the package-adjusted basis (`withholding_denominator`, after R-d's internal-transfer
# deduction, the 5.6 counted-pair deduction and R2-OW15/16's moved credits) beside the statement's own rate and
# potential exposure, so the CSV and XLSX row contradicted itself and the package's own per-match exposure. A member row
# now divides by the basis it prints: where the package moved the basis, its rate and exposure are its own numerators
# over that basis (none under R3-20's floor or where F1 refuses the basis); elsewhere the stored figures, as before.

R3_72_KAPITUS = "KAPITUS DES:PAYMENT ID:000000003 INDN:CONTOSO BAKERY LLC CO ID:0000000004 CCD"
R3_72_POTENTIAL = "NORTHWIND FUNDING WEB PMT"


def _r3_72_pass_1():
    feb = [(4, "FABRIKAM STORES INC DES:PAYMENT ID:7", 30000.0), (20, "DEPOSIT", 60000.0)]
    feb += [(day, R3_72_KAPITUS, -1500.0) for day in (6, 13, 20, 27)]
    feb += [(day, R3_72_POTENTIAL, -750.0) for day in (7, 14, 21, 28)]
    mar = [(2, "DEPOSITED ITEM RETURNED", -60000.0), (6, "FABRIKAM STORES INC DES:PAYMENT ID:8", 30000.0)]
    mar += [(day, R3_72_KAPITUS, -1500.0) for day in (6, 13, 20, 27)]
    february = _payload(feb, month=2, opening=2500.0)
    march = _payload(mar, month=3, opening=_closing(feb, 2500.0))
    return february, march


def test_r3_72_pass_1_a_member_row_divides_by_the_basis_it_prints():
    february, march = _r3_72_pass_1()
    assert february["metrics"]["withholding_rate"] == pytest.approx(6000.0 / 90000.0 * 100)
    package = _package(("feb", february), ("mar", march))
    row = _doc(package, "feb")
    assert (row["withholding_numerator"], row["withholding_denominator"]) == (6000.0, 30000.0)
    assert row["withholding_rate"] == pytest.approx(20.0)  # was 6.6667
    assert row["potential_withholding_exposure"] == pytest.approx(10.0)  # was 3.3333
    (match,) = [item for item in package["detection"]["potential_lenders"] if item["source_job"] == "feb"]
    assert match["potential_withholding_exposure"] == pytest.approx(row["potential_withholding_exposure"])
    assert match["eligible_deposit_denominator"] == row["potential_withholding_denominator"] == 30000.0


def test_r3_72_pass_2_a_member_row_divides_by_the_basis_it_prints():
    a_rows = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:5", 15000.0),
              (3, "ONLINE BANKING TRANSFER TO CHK 2020 CONF 7788", -9876.54)]
    b_rows = [(3, "DEPOSIT", 9876.54), (9, "FABRIKAM STORES INC DES:PAYMENT ID:6", 3000.0)]
    b_rows += [(day, R3_72_KAPITUS, -400.0) for day in (6, 13, 20, 27)]
    b_rows += [(day, R3_72_POTENTIAL, -200.0) for day in (7, 14, 21, 28)]
    a = _payload(a_rows, month=3, opening=40000.0)
    b = _payload(b_rows, month=3, opening=1500.0, number=ACCOUNT_B)
    assert b["metrics"]["withholding_rate"] == pytest.approx(1600.0 / 12876.54 * 100)
    package = _package(("a", a), ("b", b))
    row = _doc(package, "b")
    assert row["withholding_denominator"] == 3000.0
    assert row["withholding_rate"] == pytest.approx(1600.0 / 3000.0 * 100)  # was 12.4257
    assert row["potential_withholding_exposure"] == pytest.approx(800.0 / 3000.0 * 100)  # was 6.2128
    # A member the passes did not move keeps its stored figures, byte for byte.
    before = _package(("a", a))
    assert _doc(package, "a") == {**_doc(before, "a"), **{key: _doc(package, "a")[key] for key in (
        "package_match_count",) if key in _doc(package, "a")}}


def test_r3_72_the_legacy_r_d_deduction_recomputes_the_row(monkeypatch):
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "legacy_eligible_deposits")
    a_rows = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:5", 15000.0), (3, "ONLINE TRANSFER TO CHK 2020", -9876.54)]
    b_rows = [(3, "ONLINE TRANSFER FROM CHK 1010", 9876.54), (9, "FABRIKAM STORES INC DES:PAYMENT ID:6", 3000.0),
              (10, R3_72_KAPITUS, -600.0)]
    document = _two_account_document(a_rows, b_rows)
    assert document["document"]["internal_transfers"]
    package = _package(("d", document))
    (row,) = [item for item in package["documents"] if item.get("account_index") == 2]
    assert row["withholding_denominator"] == 3000.0
    assert row["withholding_rate"] == pytest.approx(20.0)  # was 4.6596


def test_r3_72_the_downloads_carry_the_recomputed_rate():
    import zipfile

    from webapp.app import _package_csv, _package_xlsx

    february, march = _r3_72_pass_1()
    package = _package(("feb", february), ("mar", march))
    rows = list(csv.reader(io.StringIO(_package_csv(package))))
    cells = {(row[0], row[1]): row[2] for row in rows[1:] if len(row) == 3}
    assert float(cells[("document_1", "withholding_rate")]) == pytest.approx(20.0)
    assert float(cells[("document_1", "potential_withholding_exposure")]) == pytest.approx(10.0)
    with zipfile.ZipFile(io.BytesIO(_package_xlsx(package))) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "<v>20.0</v>" in sheet and "<v>10.0</v>" in sheet
