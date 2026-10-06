"""Owner ruling 2026-10-02 (the underwriter's Q10; audit I39 with I24, I38; true revenue spec §2.1, §8.10, §9.1,
§10.1, §14.3, §19.1, §20; audit round 2, R2-OW11): "Lets go with 2. Hold every deposit into an account titled "premium
trust". Count only commissions that reach the agency's operating account."

An insurance agency's premium trust account holds its insureds' premiums, which the agency passes on to the carriers:
not the agency's revenue. On a statement whose printed title reads PREMIUM TRUST (`premium_trust_title` over the
statement's account title, account name and holder name, in that order, read only in the title forms: never the words
anywhere, never a row's payer), pass 7's step after the $1 floor holds every posted credit a rule verified or counted
as `premium_trust_account`. A held credit keeps its first hold and a non-revenue credit stays non-revenue (the default
the owner may change). The operating, producer-payable, wire and Lloyd's-titled accounts read as before; on the
operating account the insurer-worded commissions count through the underwriter's Q2 (R2-OW08), which T6 pins beside
the trust side.

Fabricated rows only (CONTOSO, FABRIKAM, NORTHWIND, ADATUM, SAMPLE, neutral amounts, 2054 dates). The 78 rule cases are
the card's (q10-rev2 n01: r02's 58, the "designation" cases passed as the account title, and 20 new)."""
from __future__ import annotations

import pytest

from analysis import holder_name as hn
from analysis import transaction_classifier as tc
from analysis import true_revenue as tr
from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction
from tests.zelle_reading import rules_reading

PT = ("excluded_pending_review", "premium_trust_account")
T, A, H = "account_title", "account_name", "holder_name"

# --- premium_trust_title: the card's 78 cases ---------------------------------------------------------------------

RULE_CASES = [
    # r02: must read (the title at the field's end, after an account word, or before a separator).
    (T, "PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"), (A, "Premium Trust", "PREMIUM TRUST"),
    (A, "NORTHWIND Premium Trust", "PREMIUM TRUST"), (A, "PREM TRUST ACCT", "PREM TRUST ACCT"),
    (A, "Premium Trust Checking", "PREMIUM TRUST CHECKING"), (H, "NORTHWIND AGENCY PREMIUM TRUST", "PREMIUM TRUST"),
    (T, "INSURANCE PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"),
    (A, "PREMIUM TRUST ACCT 2", "PREMIUM TRUST ACCT"), (A, "PREMIUM TRUST ACCOUNT #1234", "PREMIUM TRUST ACCOUNT"),
    (A, "PREMIUM TRUST ACCOUNT II", "PREMIUM TRUST ACCOUNT"), (A, "PREMIUM TRUST ACCOUNT (SC)", "PREMIUM TRUST ACCOUNT"),
    (A, "PREMIUM TRUST ACCOUNT - NORTHWIND INSURANCE AGENCY", "PREMIUM TRUST ACCOUNT"),
    (T, "PREMIUM TRUST ACCOUNT - NORTHWIND INSURANCE AGENCY", "PREMIUM TRUST ACCOUNT"),
    (A, "PREMIUMS TRUST ACCOUNT", "PREMIUMS TRUST ACCOUNT"), (A, "Premium Trust - 1234", "PREMIUM TRUST"),
    (A, "NORTHWIND Premium Trust (Account #xxxxxx1234)", "PREMIUM TRUST"),
    (A, "PREMIUM TRUST ACCOUNT 1234", "PREMIUM TRUST ACCOUNT"), (A, "PREMIUM TRUST ACCT #2", "PREMIUM TRUST ACCT"),
    (A, "PREMIUM TRUST ACCOUNT.", "PREMIUM TRUST ACCOUNT"), (A, "PREMIUM TRUST SAVINGS", "PREMIUM TRUST SAVINGS"),
    (A, "PREMIUM TRUST MONEY MARKET", "PREMIUM TRUST MONEY MARKET"), (A, "PREMIUM TRUST A/C", "PREMIUM TRUST A/C"),
    (A, "PREMIUMTRUST", "PREMIUMTRUST"), (A, "PREM TRST", "PREM TRST"), (A, "PREM. TRUST ACCT.", "PREM TRUST ACCT"),
    (H, "NORTHWIND AGENCY PREMIUM TRUST ACCT 2", "PREMIUM TRUST ACCT"),
    (T, "PREMIUM TRUST ACCOUNT - OPERATING", "PREMIUM TRUST ACCOUNT"),
    (T, "PREMIUM TRUST", "PREMIUM TRUST"),
    # r02: must not read (other designations, products, trusts and company names).
    (T, "OPERATING ACCOUNT", None), (T, "PRODUCER PAYABLE ACCOUNT", None), (T, "WIRE ACCOUNT", None),
    (T, "SAMPLE SYNDICATE", None), (T, "TRUST ACCOUNT", None), (T, "CLIENT TRUST ACCOUNT", None),
    (T, "ESCROW ACCOUNT", None), (T, "IOLTA TRUST ACCOUNT", None),
    (A, "SAMPLE PREMIUM BUSINESS CHECKING", None), (A, "Premium Business Chequing", None),
    (A, "Platinum Premium Savings", None), (A, "Premium Finance Checking", None),
    (H, "PREMIUM TRUST ROOFING LLC", None), (A, "PREMIUM TRUST ROOFING LLC", None),
    (H, "PREMIUM TRUST ACCOUNT LLC", None), (A, "PREMIUM TRUST ACCOUNT LLC", None),
    (H, "FABRIKAM FAMILY TRUST", None), (A, "Business Checking", None), (H, "CONTOSO TRUST COMPANY", None),
    (H, "PREMIUM TRUST COMPANY", None), (H, "NORTHWIND PREMIUM TRUST CO", None), (H, "NORTHWIND PREMIUM TRUST CO.", None),
    (A, "PREMIUM TRUSTEE ACCOUNT", None), (A, "SUPREMIUM TRUST", None), (A, "CONTOSO BANK & TRUST ACCOUNT:", None),
    (A, "IOLTA TRUST ACCOUNT", None), (A, "ESCROW ACCOUNT", None), (H, "PREMIUM TRUST HOLDINGS INC", None),
    (H, "PREMIUM TRUSTWORTHY ROOFING", None), (A, "PREMIUM TRUST ROOFING", None),
    # New: a second trade name the holder reader dropped after the legal form is no title.
    (T, "PREMIUM TRUST ROOFING", None), (T, "PREMIUM TRUST ROOFING SUPPLY", None),
    # New: a nickname naming the agency with its legal form after the title and an account word, then a separator.
    (A, "PREMIUM TRUST ACCOUNT - NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"),
    (A, "PREMIUM TRUST CHECKING - 1234 CONTOSO AGENCY INC", "PREMIUM TRUST CHECKING"),
    (A, "Premium Trust Account – Northwind Agency, LLC", "PREMIUM TRUST ACCOUNT"),
    (A, "PREMIUM TRUST ACCT: NORTHWIND AGENCY LLC", "PREMIUM TRUST ACCT"),
    (A, "PREMIUM TRUST CHECKING (NORTHWIND AGENCY LLC)", "PREMIUM TRUST CHECKING"),
    (H, "PREMIUM TRUST ACCOUNT - NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"),
    # New: still not read (FUND is no account word for the separator form; a bare title before a separator; a
    # company named after the words; TRUSTEE and ACCOUNTING are other words; a syndicate's market).
    (A, "PREMIUM TRUST FUNDS - INVESTOR CLASS LLC", None), (H, "PREMIUM TRUST ROOFING - CONTOSO LLC", None),
    (H, "PREMIUM TRUST - CONTOSO LLC", None), (H, "PREMIUM TRUST ACCOUNT LLC", None),
    (H, "PREMIUM TRUST ACCOUNTING LLC", None), (H, "PREMIUM TRUST ACCOUNTING - CONTOSO LLC", None),
    (A, "PREMIUM TRUSTEE ACCOUNT - CONTOSO LLC", None), (T, "PREMIUM TRUSTEE ACCOUNT", None),
    (T, "LLOYDS OF LONDON", None),
    # New: the question's own example as the account name (T5), and the corpus's designation.
    (A, "NORTHWIND INSURANCE AGENCY – PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"),
    (T, "INSURANCE PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"),
    # New, recorded as not read (an abbreviation the words do not read: the safe direction).
    (A, "PREM. TR. ACCT.", None),
]


def test_the_rule_cases_are_the_cards_seventy_eight():
    assert len(RULE_CASES) == 78


@pytest.mark.parametrize(("field", "text", "expected"), RULE_CASES)
def test_premium_trust_title_reads_only_the_title_forms(field, text, expected):
    fields = {T: None, A: None, H: None}
    fields[field] = text
    assert tr.premium_trust_title(**fields) == expected


def test_the_rule_reads_the_title_then_the_account_name_then_the_holder_name():
    # The first field that reads wins; a field that does not read passes to the next.
    assert tr.premium_trust_title("OPERATING ACCOUNT", "Premium Trust", None) == "PREMIUM TRUST"
    assert tr.premium_trust_title(None, "Business Checking", "NORTHWIND AGENCY PREMIUM TRUST") == "PREMIUM TRUST"
    assert tr.premium_trust_title("PREMIUM TRUST ACCT", "Premium Trust Checking", None) == "PREMIUM TRUST ACCT"
    assert tr.premium_trust_title(None, None, None) is None
    assert tr.premium_trust_title("", "  ", "") is None
    # L.L.C. reads as LLC, so the account-word form is refused on a field that ends in it.
    assert tr.premium_trust_title(None, None, "PREMIUM TRUST ACCOUNT L.L.C.") is None


@pytest.mark.parametrize(("line", "holder", "title", "rule"), [
    ("CONTOSO LLC DBA NORTHWIND AGENCY, LLC PREMIUM TRUST ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001 1,234.56",
     "CONTOSO LLC DBA NORTHWIND AGENCY, LLC", "PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"),
    ("NORTHWIND INSURANCE AGENCY – PREMIUM TRUST ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "NORTHWIND INSURANCE AGENCY –", "PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"),
    ("NORTHWIND INSURANCE AGENCY - PREMIUM TRUST ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "NORTHWIND INSURANCE AGENCY -", "PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"),
    ("NORTHWIND INSURANCE AGENCY LLC – PREMIUM TRUST ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT", "PREMIUM TRUST ACCOUNT"),
    # T2: no legal form and no account word: the title stays in the holder's name, which the rule reads at its end.
    ("NORTHWIND INSURANCE AGENCY PREMIUM TRUST PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "NORTHWIND INSURANCE AGENCY PREMIUM TRUST", None, "PREMIUM TRUST"),
    # C1, C2, C3: the agency's other accounts.
    ("CONTOSO LLC DBA NORTHWIND AGENCY LLC OPERATING ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "CONTOSO LLC DBA NORTHWIND AGENCY LLC", "OPERATING ACCOUNT", None),
    ("CONTOSO LLC DBA NORTHWIND AGENCY, LLC PRODUCER PAYABLE ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "CONTOSO LLC DBA NORTHWIND AGENCY, LLC", "PRODUCER PAYABLE ACCOUNT", None),
    ("CONTOSO LLC DBA NORTHWIND AGENCY LLC SAMPLE SYNDICATE PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "CONTOSO LLC DBA NORTHWIND AGENCY LLC", "SAMPLE SYNDICATE", None),
    # C10: a second trade name the reader drops after the legal form is published as a title, and never read.
    ("CONTOSO HOLDINGS LLC PREMIUM TRUST ROOFING 100 MAIN ST SAMPLEVILLE SC 29000-0001",
     "CONTOSO HOLDINGS LLC", "PREMIUM TRUST ROOFING", None),
])
def test_the_rule_on_the_holder_line_readings(line, holder, title, rule):
    reading = hn.read_address_line(line)
    assert reading == (holder, title)
    assert tr.premium_trust_title(reading.title, None, reading.name) == rule


# --- the statements -------------------------------------------------------------------------------------------------

ADDR = "PO BOX 100 SAMPLEVILLE SC 29000-0001 1,234.56"
TRUST_LINE = f"CONTOSO LLC DBA NORTHWIND AGENCY, LLC PREMIUM TRUST ACCOUNT {ADDR}"
OPERATING_LINE = f"CONTOSO LLC DBA NORTHWIND AGENCY LLC OPERATING ACCOUNT {ADDR}"

#: T1's rows: (description, amount, today's (tier, reason or method), the tier and reason after Q10).
T1_ROWS = [
    ("DEPOSIT", 2345.67, ("counted_flagged", "no_payer_printed"), PT),
    ("APPLIED SYSTEMS PAYOUT 1ABC2DEF3GH4IJ", 4321.00, ("counted_flagged", "named_payer_unlabelled"), PT),
    ("WIRE TRANSFER IN REF 123456 ORG: FABRIKAM MARINE LLC", 9000.00, ("verified", "repeat_wire_sender"), PT),
    ("WIRE TRANSFER IN REF 123457 ORG: FABRIKAM MARINE LLC", 9100.00, ("verified", "repeat_wire_sender"), PT),
    ("BANKCARD 8030 BTOT DEP 1234567", 5120.44, ("verified", "operating_income_descriptor"), PT),
    ("BANKCARD 8030 BTOT DEP 1234567", 4870.10, ("verified", "operating_income_descriptor"), PT),
    ("MOBILE CHECK DEPOSIT", 980.00, ("counted_flagged", "check_deposit"), PT),
    # The underwriter's Q2 (R2-OW08) counts an insurer's agent commission; on a trust account Q10 holds it.
    ("SAMPLE MUTUAL INS CO AGT COMM 1234", 640.00, ("counted_flagged", "insurer_paid_for_services"), PT),
    # Unchanged: the first holds, and the non-revenue rows.
    ("NORTHWIND AGENCY PY03/02/54 *****1234", 150000.00, ("excluded_pending_review", "holder_name"),
     ("excluded_pending_review", "holder_name")),
    ("IPFS123 456 7890 IPFSFNDFLP P 1234", 8800.00, ("non_revenue", "insurance_provider_credit_exclusion"),
     ("non_revenue", "insurance_provider_credit_exclusion")),
    ("TRANSFER INTERNET 03 05 SEQ 12345 1234567890", 20000.00, ("excluded_pending_review", "transfer_no_counterparty"),
     ("excluded_pending_review", "transfer_no_counterparty")),
    ("DEPOSIT", 0.50, ("excluded_pending_review", "non_sale_purpose"), ("excluded_pending_review", "non_sale_purpose")),
    ("KAPITUS LLC FUNDING 1234", 25000.00, ("non_revenue", "financing_proceeds_credit"),
     ("non_revenue", "financing_proceeds_credit")),
    ("WIRE TRANSFER IN REF 123458 ORG: SAMPLE FAMILY TRUST", 7000.00, ("excluded_pending_review", "non_sale_purpose"),
     ("excluded_pending_review", "non_sale_purpose")),
]
T1_DEBITS = [
    ("KAPITUS LLC PAYMENT 1234", -900.00),
    ("KAPITUS LLC PAYMENT 1234", -900.00),
    # A debit that shares no first word with a payer (a SAMPLE debit would hold the SAMPLE MUTUAL row as
    # payer_also_debited, a first hold Q10 keeps: test_a_first_hold_is_kept_on_a_trust_account).
    ("ONLINE TRANSFER TO ADATUM VENDOR", -50.00),
]
T1 = [(text, amount) for text, amount, _today, _after in T1_ROWS] + T1_DEBITS
#: T2 to T5's rows: the bare deposit, two wires and two card settlements.
SHORT = [T1[0], T1[2], T1[3], T1[4], T1[5]]


def _statement(rows, line=None, *, bank="First Citizens Bank", **fields):
    """A statement whose holder name and title come from the holder reader's own line, as the First Citizens parser
    publishes them (its holder line read, R2-OW10)."""
    if line is not None:
        reading = hn.read_address_line(line)
        fields.update(holder_name=reading.name, account_title=reading.title)
    return Statement(bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ], **fields)


def _today(statement, monkeypatch):
    """The statement's records with the premium-trust rule reading no title (every other rule as today)."""
    with monkeypatch.context() as patch:
        patch.setattr(tc, "premium_trust_title", lambda *fields: None)
        return tc.classify_statement_transactions(statement)


def _reading(records):
    return [rules_reading(record, method=True) for record in records if record.amount > 0]


def _money(value):
    return round(value, 2)


def test_t1_a_trust_account_holds_every_credit_a_rule_verified_or_counted(monkeypatch):
    statement = _statement(T1, TRUST_LINE, account_name="Business Banking")
    assert statement.holder_name == "CONTOSO LLC DBA NORTHWIND AGENCY, LLC"
    assert statement.account_title == "PREMIUM TRUST ACCOUNT"
    before = _today(statement, monkeypatch)
    after = tc.classify_statement_transactions(statement)
    assert _reading(before) == [today for _text, _amount, today, _after in T1_ROWS]
    assert _reading(after) == [held for _text, _amount, _today, held in T1_ROWS]
    for old, new in zip(before, after):
        if new.revenue_tier_reason != "premium_trust_account":
            assert new == old
            continue
        assert new.revenue_review_required is True and new.revenue_initial_tier == "excluded_pending_review"
        assert not new.contributes_to_true_revenue and new.contributes_to_excluded_pending_review
        if old.revenue_classification == "verified_revenue":
            # A verified credit leaves verification as a new first state, the rule it overruled named.
            assert new.revenue_classification == new.revenue_initial_classification == "unverified_deposit"
            assert (new.revenue_match_method, new.revenue_matched_rule, new.revenue_confidence_score) == (
                "premium_trust_account", "premium_trust_account_title", 0.40)
            assert new.revenue_context_signals == (*old.revenue_context_signals, "premium_trust_account")
            assert new.revenue_related_transaction == old.revenue_related_transaction
            assert new.revenue_reason.startswith("A deposit into an account titled PREMIUM TRUST ACCOUNT: an insurance "
                                                 "agency's premium trust account holds its insureds' premiums")
            assert f"The rule that read it ({old.revenue_match_method}) is overruled" in new.revenue_reason
            assert not new.contributes_to_verified_revenue
        else:
            # A counted credit keeps its state, method, rule and reason sentence: only its tier and reason change.
            for field in ("revenue_classification", "revenue_match_method", "revenue_matched_rule",
                          "revenue_confidence_score", "revenue_reason", "revenue_context_signals"):
                assert getattr(new, field) == getattr(old, field), field
        # Nothing but the revenue reading moves: the classification and its lender flags are the same.
        for field in ("classification", "match_method", "canonical_entity", "contributes_to_lender_count",
                      "contributes_to_lender_totals", "contributes_to_withholding_rate",
                      "contributes_to_lender_credit_exclusion"):
            assert getattr(new, field) == getattr(old, field), field

    # Owner ruling 2026-10-02 (the underwriter's Q7), R2-OW14: True revenue is the default basis, so the legacy rate
    # this test pins (it does not move) is read on the legacy basis, selected.
    legacy = "legacy_eligible_deposits"
    was = compute_metrics(statement, classifications=before, withholding_denominator_mode=legacy)
    now = compute_metrics(statement, classifications=after, withholding_denominator_mode=legacy)
    assert (_money(was.true_revenue_total), _money(was.excluded_pending_review_total)) == (36377.21, 177000.50)
    assert (_money(now.true_revenue_total), _money(now.excluded_pending_review_total)) == (0.0, 213377.71)
    assert _money(now.verified_revenue_total) == 0.0
    for metrics in (was, now):
        assert _money(metrics.non_revenue_total) == 33800.0
        assert _money(metrics.legacy_eligible_deposits) == 222177.71
        assert (_money(metrics.lender_debits), _money(metrics.lender_credits), metrics.lenders_detected) == (
            1800.0, 25000.0, 1)
        assert round(metrics.withholding_rate, 2) == 0.81
    assert now.premium_trust_account is True and was.premium_trust_account is True
    assert compute_metrics(statement, withholding_denominator_mode=legacy) == now
    # On the True basis, the default (R2-OW14), the denominator is $0: the rate is unavailable (the withholding
    # numerator does not move).
    true_basis = compute_metrics(statement, classifications=after, withholding_denominator_mode="true_revenue")
    assert compute_metrics(statement) == true_basis
    assert true_basis.withholding_rate is None and true_basis.withholding_review_required is True
    assert _money(true_basis.lender_debits) == 1800.0


def test_t2_a_holder_name_that_ends_in_the_title(monkeypatch):
    statement = _statement(SHORT, f"NORTHWIND INSURANCE AGENCY PREMIUM TRUST {ADDR}")
    assert (statement.holder_name, statement.account_title) == ("NORTHWIND INSURANCE AGENCY PREMIUM TRUST", None)
    before = compute_metrics(statement, classifications=_today(statement, monkeypatch))
    after = tc.classify_statement_transactions(statement)
    assert _reading(after) == [PT] * 5
    metrics = compute_metrics(statement, classifications=after)
    assert (_money(before.true_revenue_total), _money(metrics.true_revenue_total)) == (30436.21, 0.0)
    assert (before.revenue_review_required, metrics.revenue_review_required) == (False, True)
    assert metrics.premium_trust_account is True


@pytest.mark.parametrize(("bank", "account_name"), [
    # T3: a credit union's share named for the title.
    ("Northwind Credit Union", "Premium Trust"),
    # T4: a nickname with its masked number.
    ("Chase", "NORTHWIND Premium Trust (Account #xxxxxx1234)"),
    # T5: the question's own example.
    ("First Citizens Bank", "NORTHWIND INSURANCE AGENCY – PREMIUM TRUST ACCOUNT"),
])
def test_t3_to_t5_an_account_name_that_reads_the_title(bank, account_name, monkeypatch):
    statement = _statement(SHORT, bank=bank, account_name=account_name)
    assert _reading(_today(statement, monkeypatch)) == [
        ("counted_flagged", "no_payer_printed"), ("verified", "repeat_wire_sender"), ("verified", "repeat_wire_sender"),
        ("verified", "operating_income_descriptor"), ("verified", "operating_income_descriptor")]
    assert _reading(tc.classify_statement_transactions(statement)) == [PT] * 5
    assert compute_metrics(statement).premium_trust_account is True


#: T6: the owner's two halves. Carrier commissions and a bare deposit, on the operating and on the trust statement.
T6 = [
    ("SAMPLE MUTUAL INS CO AGT COMM 1234", 640.00),
    ("FABRIKAM INSURANCE CO AGT EFT 1234", 1500.00),
    ("FABRIKAM INSURANCE CO AGT EFT 1234", 1450.00),
    ("ADATUM CASUALTY COMMISSION 1234", 820.00),
    ("SAMPLE CARRIER COMM PMT 1234", 375.00),
    ("DEPOSIT", 2345.67),
]
INSURER_FOR_WORK = ("counted_flagged", "insurer_paid_for_services")


def test_t6_commissions_count_on_the_operating_account_and_are_held_on_the_trust_account(monkeypatch):
    operating = _statement(T6, OPERATING_LINE, account_name="Business Banking")
    trust = _statement(T6, TRUST_LINE, account_name="Business Banking")
    # (a) The operating account: the underwriter's Q2 counts the four insurer-worded commissions; Q10 moves nothing.
    records = tc.classify_statement_transactions(operating)
    assert records == _today(operating, monkeypatch)
    assert _reading(records) == [INSURER_FOR_WORK] * 4 + [
        ("counted_flagged", "named_payer_unlabelled"), ("counted_flagged", "no_payer_printed")]
    metrics = compute_metrics(operating, classifications=records)
    assert (_money(metrics.true_revenue_total), _money(metrics.excluded_pending_review_total)) == (7130.67, 0.0)
    assert metrics.premium_trust_account is False
    # (b) The trust account: the same six credits are held for the title, the released commissions included (their
    # method stays the release's).
    records = tc.classify_statement_transactions(trust)
    assert _reading(records) == [PT] * 6
    assert [record.revenue_match_method for record in records[:4]] == [tr.INSURER_FOR_WORK_METHOD] * 4
    metrics = compute_metrics(trust, classifications=records)
    assert (_money(metrics.true_revenue_total), _money(metrics.excluded_pending_review_total)) == (0.0, 7130.67)
    assert metrics.premium_trust_account is True


def test_a_zelle_deposit_into_a_trust_account_stays_excluded(monkeypatch):
    """R2-OW02's Zelle step runs before the hold, and every step after it skips a non-revenue row (CR7: the rules'
    reading is asserted through zelle_prior_reading)."""
    rows = [("ZELLE PAYMENT FROM SAMPLE PERSON CONF 1234567890", 900.00), ("DEPOSIT", 2345.67)]
    statement = _statement(rows, TRUST_LINE)
    records = tc.classify_statement_transactions(statement)
    assert (records[0].revenue_tier, records[0].revenue_tier_reason) == ("non_revenue", "zelle_excluded")
    assert rules_reading(records[0]) == ("counted_flagged", "p2p")
    assert (records[1].revenue_tier, records[1].revenue_tier_reason) == PT
    assert records[0] == _today(statement, monkeypatch)[0]


def test_a_first_hold_is_kept_on_a_trust_account(monkeypatch):
    """A debit sharing the commission payer's first word holds the released commission as payer_also_debited (the
    counter-debit hold, after the release); on a trust account that first hold keeps its reason."""
    rows = [("SAMPLE MUTUAL INS CO AGT COMM 1234", 640.00), ("DEPOSIT", 2345.67),
            ("ONLINE TRANSFER TO SAMPLE VENDOR", -50.00)]
    statement = _statement(rows, TRUST_LINE)
    before = _today(statement, monkeypatch)
    after = tc.classify_statement_transactions(statement)
    assert _reading(before) == [("excluded_pending_review", "payer_also_debited"), ("counted_flagged", "no_payer_printed")]
    assert _reading(after) == [("excluded_pending_review", "payer_also_debited"), PT]
    assert after[0] == before[0]


# --- the controls: Q10 moves nothing -------------------------------------------------------------------------------

CONTROLS = [
    # C1: the agency's operating account (title OPERATING ACCOUNT): the commission counts through Q2.
    pytest.param(dict(rows=T1, line=OPERATING_LINE, account_name="Business Banking"), 36377.21, id="C1-operating"),
    # C2: its producer-payable account, and C3: a Lloyd's syndicate's designation.
    pytest.param(dict(rows=T1, line=f"CONTOSO LLC DBA NORTHWIND AGENCY, LLC PRODUCER PAYABLE ACCOUNT {ADDR}"), None,
                 id="C2-producer-payable"),
    pytest.param(dict(rows=T1, line=f"CONTOSO LLC DBA NORTHWIND AGENCY LLC SAMPLE SYNDICATE {ADDR}"), None,
                 id="C3-syndicate"),
    # C4: the T3 member's Business Checking beside an empty Premium Trust share.
    pytest.param(dict(rows=SHORT, bank="Northwind Credit Union", account_name="Business Checking"), 30436.21,
                 id="C4-member-checking"),
    # C5: a bank's Premium Business product.
    pytest.param(dict(rows=SHORT, bank="BMO", account_name="BMO PREMIUM BUSINESS CHEQUING"), None,
                 id="C5-premium-business"),
    # C6: a company named after the words.
    pytest.param(dict(rows=SHORT, holder_name="PREMIUM TRUST ROOFING LLC"), None, id="C6-company-name"),
    # C7: a law firm's client trust account.
    pytest.param(dict(rows=SHORT, account_name="IOLTA TRUST ACCOUNT", holder_name="CONTOSO LAW PLLC"), None,
                 id="C7-iolta"),
    # C8: a family trust as the holder.
    pytest.param(dict(rows=SHORT, holder_name="SAMPLE FAMILY TRUST"), None, id="C8-family-trust"),
    # C10: a second trade name the holder reader dropped after the legal form.
    pytest.param(dict(rows=SHORT, line="CONTOSO HOLDINGS LLC PREMIUM TRUST ROOFING 100 MAIN ST SAMPLEVILLE SC "
                                        "29000-0001"), 30436.21, id="C10-trade-name-title"),
]


@pytest.mark.parametrize(("spec", "true_total"), CONTROLS)
def test_a_control_account_reads_as_today(spec, true_total, monkeypatch):
    spec = dict(spec)
    statement = _statement(spec.pop("rows"), spec.pop("line", None), **spec)
    assert tr.premium_trust_title(statement.account_title, statement.account_name, statement.holder_name) is None
    records = tc.classify_statement_transactions(statement)
    assert records == _today(statement, monkeypatch)
    assert all(record.revenue_tier_reason != "premium_trust_account" for record in records)
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.premium_trust_account is False
    if true_total is not None:
        assert _money(metrics.true_revenue_total) == true_total


def test_c9_a_payer_that_prints_the_words_never_makes_a_title(monkeypatch):
    rows = [
        ("ACH CREDIT NORTHWIND PREMIUM TRUST ACCT PAYMENT 1234", 3100.00),
        ("ORIG CO NAME:NORTHWIND PREMIUM TRUST ORIG ID:1234567890 CO ENTRY DESCR:PAYMENT SEC:CCD", 2200.00),
        ("WIRE TRANSFER IN REF 123456 ORG: FABRIKAM MARINE LLC", 9000.00),
        ("WIRE TRANSFER IN REF 123457 ORG: FABRIKAM MARINE LLC", 9100.00),
        ("DEPOSIT", 2345.67),
    ]
    statement = _statement(rows, holder_name="CONTOSO TRADING LLC", account_name="Business Checking")
    records = tc.classify_statement_transactions(statement)
    assert records == _today(statement, monkeypatch)
    assert _reading(records)[:2] == [("verified", "named_payer_repeats")] * 2
    assert compute_metrics(statement, classifications=records).premium_trust_account is False


# --- the pass's mechanics ------------------------------------------------------------------------------------------

def _pass_arguments(statement, monkeypatch):
    """The arguments classify_statement_transactions hands pass 7 (the records before it, the duplicates...)."""
    seen = {}
    original = tc.apply_true_revenue_pass

    def capture(*args, **kwargs):
        seen["args"], seen["kwargs"] = args, kwargs
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(tc, "apply_true_revenue_pass", capture)
        tc.classify_statement_transactions(statement)
    return seen["args"], seen["kwargs"]


def test_the_pass_reads_the_title_only_through_its_keyword(monkeypatch):
    statement = _statement(T1, TRUST_LINE, account_name="Business Banking")
    args, kwargs = _pass_arguments(statement, monkeypatch)
    # Owner ruling 2026-10-02 (the underwriter's Q1), R2-OW12: the pass also reads the printed period start (the
    # funding aid's), none here. The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): and the Zelle
    # reading, the stored one by default.
    assert kwargs == {"premium_trust": "PREMIUM TRUST ACCOUNT", "statement_start": None, "zelle_true_revenue": False}
    # premium_trust=None, or no keyword, returns today's records exactly.
    assert tr.apply_true_revenue_pass(*args) == tr.apply_true_revenue_pass(*args, premium_trust=None)
    today = tr.apply_true_revenue_pass(*args)
    held = tr.apply_true_revenue_pass(*args, premium_trust="PREMIUM TRUST ACCOUNT")
    moved = [index for index, (old, new) in enumerate(zip(today, held)) if old != new]
    assert moved == [index for index, record in enumerate(today)
                     if record.amount > 0 and record.revenue_tier in {"verified", "counted_flagged"}]
    assert all(held[index].revenue_tier_reason == "premium_trust_account" for index in moved)
    # Debits are never read.
    assert all(old == new for old, new in zip(today, held) if old.amount < 0)


def test_a_duplicate_a_direction_conflict_and_a_credit_under_one_dollar_keep_their_reading(monkeypatch):
    rows = [
        Transaction(date="2054-03-02", description="DEPOSIT", amount=500.0, direction="credit", running_balance=1500.0),
        # A repeated printed running balance proves the same ledger row was duplicated: non_revenue as a duplicate.
        Transaction(date="2054-03-02", description="DEPOSIT", amount=500.0, direction="credit", running_balance=1500.0),
        # The printed direction disagrees with the amount: held as a direction conflict.
        Transaction(date="2054-03-03", description="DEPOSIT", amount=700.0, direction="debit"),
        # A card settlement under $1 a descriptor verifies: the floor holds it first (non_sale_purpose).
        Transaction(date="2054-03-04", description="BANKCARD 8030 BTOT DEP 1234567", amount=0.75, direction="credit"),
        Transaction(date="2054-03-05", description="BANKCARD 8030 BTOT DEP 1234567", amount=812.40,
                    direction="credit"),
    ]
    reading = hn.read_address_line(TRUST_LINE)
    statement = Statement(bank="First Citizens Bank", holder_name=reading.name, account_title=reading.title,
                          transactions=rows)
    before = _today(statement, monkeypatch)
    after = tc.classify_statement_transactions(statement)
    assert [(r.revenue_tier, r.revenue_tier_reason or r.revenue_match_method) for r in after] == [
        PT, ("non_revenue", "duplicate_credit_exclusion"), ("excluded_pending_review", "direction_conflict"),
        ("excluded_pending_review", "non_sale_purpose"), PT]
    assert after[1:4] == before[1:4]
    assert after[3].revenue_match_method == "micro_deposit_floor"


def test_a_statement_with_no_rows_still_carries_the_fact():
    assert compute_metrics(Statement(account_title="PREMIUM TRUST ACCOUNT")).premium_trust_account is True
    assert compute_metrics(Statement(account_title="OPERATING ACCOUNT")).premium_trust_account is False
    assert compute_metrics(Statement()).premium_trust_account is False
