"""Owner ruling 2026-10-02 (the underwriter's Q8, "2 Count it as true revenue, flag it just so i am notified"; spec
§2.1, §5.3, §6.3 narrowing 12, §8.9, §8.10, §19.1, §20; audit I17): when a lease-to-own or patient financier (Snap
Finance, Koalafi, Cherry, Acima, Progressive Leasing, Katapult, Terrace Finance, Wisetack: CUSTOMER_FINANCING_PAYERS,
each a ledger entity) pays the merchant for a customer's financed purchase, the payout is the merchant's own sale:
counted and flagged as customer_financing_payout, never verified (an earlier verification is overruled) and never a Q5
or Q6 repeat. A large one-off lump sum is held as customer_financing_lump_sum until sourced: $10,000 or more and an
incoming wire, a whole multiple of $1,000 or half the statement's posted credits, and not one of three or more payouts
from that financier of at least half its amount. The financiers' consumer-side credits (refunds, withdrawals, rewards,
card credits, a class-action payout, a loan to the holder, a consumer entry to a person) and every debit keep their
readings. Snap's 'SNAP LOAN FUNDING F<digits> <merchant>' leaves the strong LOAN rule; Cherry Technologies joins
PAYOUT_CREDIT_ENTITIES under OQ2's consumer-side veto.

Fabricated rows only: the holder NORTHWIND FURNITURE LLC (dental rows print NORTHWIND DENTAL, a plumbing row NORTHWIND
PLUMBING), customers CONTOSO, FABRIKAM and SAMPLE, 2054 dates, whole-dollar amounts except where the round-sum arm
needs odd cents (a run of sequential digits). The providers' wording follows the census shapes with every digit,
amount, bank and reference changed (audit round 3, R3-B14: R3-07).

Audit round 3, R3-B14 (R3-06; Q8's "consumer-side credits (refunds, loans to the holder) stay as today" and the MCA
principle): a financier's credit printing an advance, capital, interest, dividend or rebate word is no merchant payout:
it takes the reading the same row from any other payer takes, and a Cherry loan or advance keeps D1. (R3-54): a cut
name of Katapult Engineering (KATAPULT ENG...) is the namesake, never the lessor."""
from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from analysis.transaction_classifier import credit_decision
from analysis.descriptor import credit_words
from analysis.descriptor import lexical
from analysis.descriptor import words
from analysis import payee_matcher
from analysis.true_revenue import guards
from analysis.true_revenue import pass7
from analysis.true_revenue import claimed
from analysis.true_revenue import words as true_revenue_words
from analysis.revenue import REVENUE_TIER_REASONS
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from tests.zelle_reading import rules_reading

HOLDER = "NORTHWIND FURNITURE LLC"
CFP = ("counted_flagged", "customer_financing_payout")
LUMP = ("excluded_pending_review", "customer_financing_lump_sum")
VERIFIED = ("verified", None)

#: The large customer beside a lump sum (verified by its company form), so the lump is under half the posted credits.
BIG = ("CONTOSO SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 90000.0)
SNAP = "SNAP FINANCE FUNDING F12345 NORTHWIND FURNITURE"
ACIMA = "ACIMA DIGITAL DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD"
ACIMA_AP = "ACIMA DIGITAL AP PAYMENT 1234 NTE 1234 FR AB12CD"
WISETACK = "ACH DEPOSIT WISETACK USBANK PAYOUT 1234 NORTHWIND PLUMBING WT12EED34"
HATCH_WISETACK = "ACH DEPOSIT HATCH WISETACK ACH PAYMEN 1234 NORTHWIND PLUMBING 123XXXXX4"
CHASE_CHERRY = ("ORIG CO NAME:CHERRY ORIG ID:1234567890 DESC DATE: CO ENTRY DESCR:{entry} SEC:{sec} "
                "TRACE#:123456789 EED:540301 IND ID:123 IND NAME:{name}")
BOFA_WIRE = ("WIRE TYPE:WIRE IN DATE: 540301 TIME:1234 ET TRN:2054030100123 SEQ:123/123 ORIG:{payer} ID:123 "
             "SND BK:FABRIKAM BANK ID:123")
SNAP_WIRE = BOFA_WIRE.format(payer="SNAP FINANCE LLC")
KOALAFI_WIRE = "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA KOALAFI INC"
CHERRY_TECH = "CHERRY TECHNOLOGIES DES:FUNDING ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD"


def _records(rows, *, bank=None, holder=HOLDER):
    """One statement of `rows` ((text, amount): a positive amount a credit, a negative one a debit)."""
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _credits(rows, **kwargs):
    return [record for record in _records(rows, **kwargs) if record.amount > 0]


def _reading(record):
    return record.revenue_tier, record.revenue_tier_reason


# --- the payouts that are now counted and flagged (cfp) -------------------------------------------------------------

#: (label, bank, rows): every credit is counted_flagged / customer_financing_payout, never verified, no lender credit.
#: Today's reading in the comment.
NOW_COUNTED = (
    ("1 snap funding", "Wells Fargo", [(SNAP, 1500.0)]),                                   # held financing_named_payer
    ("2 snap funding x4, never a Q6 repeat", "Wells Fargo", [(SNAP, 1500.0 + i) for i in range(4)]),
    ("3 snap loan merchant funding", "Wells Fargo",
     [("SNAP LOAN FUNDING F12345 NORTHWIND FURNITURE", 1700.0)]),                          # non_revenue strong rule
    ("4 koalafi lease fund", "Wells Fargo", [("KOALAFI LEASE FUND 1234567 1 CONTOSO SAMPLE", 1800.0)]),   # held
    ("5 koalafi payment", None, [("KOALAFI PAYMENT 1234567", 1800.0)]),                    # named_payer_unlabelled
    ("6 cherry chase", "Chase",
     [(CHASE_CHERRY.format(entry="FUNDING", sec="CCD", name="NORTHWIND DENTAL"), 1234.56)]),            # held
    ("7 cherry chase to the holder (the claim skips the holder hold)", "Chase",
     [(CHASE_CHERRY.format(entry="FUNDING", sec="CCD", name=HOLDER), 1234.56)]),
    ("8 cherry funding", "First Citizens Bank", [("CHERRY FUNDING 123456", 1500.0)]),     # held
    ("9 cherry payment ccd", None, [("CHERRY PAYMENT CCD 1234", 1450.0)]),                 # named_payer_one_off
    ("10 cherry technologies (leaves D1)", "Bank of America", [(CHERRY_TECH, 1300.0)]),    # non_revenue D1
    ("11 cherrypay payout (leaves D1)", "Bank of America",
     [("CHERRYPAY DES:PAYOUT ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD", 980.0)]),          # non_revenue D1
    ("12 acima ap payment", "Wells Fargo", [(ACIMA_AP, 1100.0)]),                          # named_payer_unlabelled
    ("13 acima des funding", "Bank of America", [(ACIMA, 1100.0)]),                        # held
    ("14 terrace finance", None, [("TERRACE FINANCE TERRACE", 2400.0)]),                  # held
    ("15 wisetack repeats", "Capital One", [(HATCH_WISETACK, 4400.0), (HATCH_WISETACK, 4450.0)]),  # verified repeats
    ("16 wisetack company form", None, [("ACH CREDIT HATCH WISETACK ACH PAYMEN LLC", 6100.0)]),    # verified form
    ("17 katapult des funding", "Bank of America",
     [("KATAPULT DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD", 900.0)]),       # held
    ("18 progressive des funding", "Bank of America",
     [("PROGRESSIVE LEASING DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD", 1200.0)]),  # held
    ("20 koalafi small wire", None, [("INCOMING WIRE TRANSFER ORG KOALAFI INC", 2500.0)]),  # purpose_refused
    ("22 snap wire under the floor", "Bank of America", [(SNAP_WIRE, 2345.67)]),            # held
    ("25 acima 9,000 alone (under the floor)", "Bank of America", [(ACIMA, 9000.0)]),       # held
    ("46 snap funding beside a snap debit", "Wells Fargo",
     [(SNAP, 1500.0), ("SNAP FINANCE PAYMENT 1234", -150.0)]),                              # held
    ("46 acima ap beside an acima debit", "Wells Fargo",
     [(ACIMA_AP, 1100.0), ("ACIMA DIGITAL PAYMENT 1234", -120.0)]),                          # held payer_also_debited
    ("56 snap ppd to the holder", "Bank of America",
     [("SNAP FINANCE DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE LLC CO ID:123 PPD", 1500.0)]),
    ("56 snap ccd to a person-named receiver", "Bank of America",
     [("SNAP FINANCE DES:FUNDING ID:123 INDN:JOHN SAMPLE CO ID:123 CCD", 1500.0)]),
    ("57 cherry funding beside a cherry debit", "First Citizens Bank",
     [("CHERRY FUNDING 123456", 1500.0), ("CHERRY TECHNOLOGIES PAYMENT 1234", -200.0)]),   # held
    ("57 cherry technologies beside a cherry debit", "Bank of America",
     [(CHERRY_TECH, 1300.0), ("CHERRY TECHNOLOGIES PAYMENT 1234", -200.0)]),                # non_revenue D1
)


@pytest.mark.parametrize(("label", "bank", "rows"), NOW_COUNTED, ids=[case[0] for case in NOW_COUNTED])
def test_a_financier_s_merchant_payout_is_counted_and_flagged_never_verified(label, bank, rows):
    credits = _credits(rows, bank=bank)
    assert credits
    for record in credits:
        assert _reading(record) == CFP, (label, record.amount)
        assert record.revenue_classification == "unverified_deposit"
        assert record.contributes_to_true_revenue and not record.contributes_to_verified_revenue
        assert not record.revenue_review_required
        assert not record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize(("rows", "method", "overruled"), [
    # 19: an operating-income descriptor verified Cherry's payout: overruled, the method names the financier.
    ([("CHERRY MERCHANT PAYOUT 1234", 2200.0)], "customer_financing_payer", "operating_income_descriptor"),
])
def test_an_earlier_verification_of_a_financier_s_payout_is_overruled(rows, method, overruled):
    (record,) = _credits(rows)
    assert _reading(record) == CFP
    assert record.revenue_match_method == method
    assert record.revenue_matched_rule == "customer_financing_never_verified"
    assert overruled in record.revenue_reason
    assert "customer_financing_payout" in record.revenue_context_signals


def test_a_financier_s_repeat_never_verifies_and_never_counts_toward_another_s_repeat():
    # 15 and 53: Q6 never reads a financier's payouts as a repeat; a third payer's two rows still verify as repeats.
    records = _credits([(HATCH_WISETACK, 4400.0), (HATCH_WISETACK, 4450.0),
                        ("FABRIKAM TRADING LLC DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 3000.0),
                        ("FABRIKAM TRADING LLC DES:PAYMENT ID:2 INDN:NORTHWIND CO ID:1 CCD", 3100.0)],
                       bank="Bank of America")
    assert [_reading(record) for record in records] == [CFP, CFP, VERIFIED, VERIFIED]
    assert [record.revenue_match_method for record in records[2:]] == ["named_payer_repeats"] * 2


# --- the lump sums: large and one-off ------------------------------------------------------------------------------

#: (label, bank, rows, readings of the credits in order).
LUMPS = (
    ("21 snap wire 40,000", "Bank of America", [(SNAP_WIRE, 40000.0), BIG], [LUMP, VERIFIED]),
    ("23 koalafi fedwire, odd cents (the wire arm)", "Chase",
     [("FEDWIRE CREDIT VIA: FABRIKAM BANK B/O: KOALAFI INC RICHMOND VA REF: CHASE NYC/CTR/BNF=NORTHWIND FURNITURE",
       15432.10), BIG], [LUMP, VERIFIED]),
    ("24 acima 25,000 alone (the round arm)", "Bank of America", [(ACIMA, 25000.0), BIG], [LUMP, VERIFIED]),
    ("24 acima exactly 10,000 alone", "Bank of America", [(ACIMA, 10000.0), BIG], [LUMP, VERIFIED]),
    ("26 terrace wire 12,000", "Bank of America", [(BOFA_WIRE.format(payer="TERRACE FINANCE LLC"), 12000.0), BIG],
     [LUMP, VERIFIED]),
    ("27 cherry odd cents, ACH, 12% of posted", "First Citizens Bank", [("CHERRY FUNDING 123456", 12345.67), BIG],
     [CFP, VERIFIED]),
    ("28 wisetack round 12,000 beside 40,000", "Capital One", [(WISETACK, 12000.0), (BIG[0], 40000.0)],
     [LUMP, VERIFIED]),
    ("28 wisetack odd cents beside 40,000", "Capital One", [(WISETACK, 12345.67), (BIG[0], 40000.0)],
     [CFP, VERIFIED]),
    ("28 wisetack odd cents beside 4,000 (the half-of-posted arm)", "Capital One",
     [(WISETACK, 12345.67), (BIG[0], 4000.0)], [LUMP, VERIFIED]),
    # The one-off test: a large payout among small ones is held, the small ones counted.
    ("47 acima 10,000 beside 1,100 and 1,150", "Bank of America",
     [(ACIMA, 10000.0), (ACIMA, 1100.0), (ACIMA, 1150.0), BIG], [LUMP, CFP, CFP, VERIFIED]),
    ("48 a pair is not a series", "Bank of America", [(ACIMA, 10000.0), (ACIMA, 12000.0), BIG],
     [LUMP, LUMP, VERIFIED]),
    ("49 three of a size are a series", "Bank of America",
     [(ACIMA, 10000.0), (ACIMA, 12000.0), (ACIMA, 11000.0), BIG], [CFP, CFP, CFP, VERIFIED]),
    ("49 five round payouts are a series", "Bank of America",
     [(ACIMA, 10000.0 + 1000.0 * i) for i in range(5)] + [BIG], [CFP] * 5 + [VERIFIED]),
    ("50 a snap wire among ten small payouts", "Bank of America",
     [(SNAP_WIRE, 25000.0)] + [(SNAP, 1000.0 + 37.5 * i) for i in range(10)] + [BIG], [LUMP] + [CFP] * 10 + [VERIFIED]),
    ("51 two snap wires of 40,000", "Bank of America", [(SNAP_WIRE, 40000.0), (SNAP_WIRE, 40000.0), BIG],
     [LUMP, LUMP, VERIFIED]),
    ("52 koalafi's two round wires (Instacred's shape)", None,
     [(KOALAFI_WIRE, 51000.0), (KOALAFI_WIRE, 33000.0), (BIG[0], 15000.0)], [LUMP, LUMP, VERIFIED]),
    ("53 wisetack odd-cents series", "Capital One",
     [(WISETACK, 15123.45), (WISETACK, 16234.56), (WISETACK, 17345.67), BIG], [CFP, CFP, CFP, VERIFIED]),
    ("53 wisetack 15,000 beside 7,000 and 7,400", "Capital One",
     [(WISETACK, 15000.0), (WISETACK, 7000.0), (WISETACK, 7400.0), BIG], [LUMP, CFP, CFP, VERIFIED]),
)


@pytest.mark.parametrize(("label", "bank", "rows", "readings"), LUMPS, ids=[case[0] for case in LUMPS])
def test_a_large_one_off_lump_sum_is_held_until_sourced(label, bank, rows, readings):
    records = _credits(rows, bank=bank)
    assert [_reading(record) for record in records] == readings, label
    for record, reading in zip(records, readings):
        if reading == LUMP:
            assert record.revenue_review_required and not record.contributes_to_true_revenue
            assert record.revenue_classification == "unverified_deposit"


def test_the_lump_sum_hold_never_depends_on_the_rows_order():
    forward = _credits([(ACIMA, 10000.0), (ACIMA, 1100.0), (ACIMA, 1150.0), BIG], bank="Bank of America")
    backward = _credits([BIG, (ACIMA, 1150.0), (ACIMA, 1100.0), (ACIMA, 10000.0)], bank="Bank of America")
    assert {(record.amount, _reading(record)) for record in forward} == {
        (record.amount, _reading(record)) for record in backward} == {
        (10000.0, LUMP), (1100.0, CFP), (1150.0, CFP), (90000.0, VERIFIED)}


def test_a_verified_financier_payout_held_as_a_lump_names_the_overruled_rule():
    # 53: a Wisetack repeat verified today, held as a one-off lump sum: never verified, its reason the lump's.
    (record, *_rest) = _credits([(WISETACK, 15000.0), (WISETACK, 7000.0), (WISETACK, 7400.0), BIG],
                                bank="Capital One")
    assert _reading(record) == LUMP
    assert record.revenue_classification == "unverified_deposit"
    # Audit round 3, R3-B15 (R3-53; §5.3): a payout a single-row rule verified (Cherry's operating-income descriptor),
    # overruled and then held as a lump, names the overruled rule and never says it is counted; its sentence names the
    # lump hold by its own label. The same payout at a small amount is counted and keeps the counted sentence.
    (lump, _big) = _credits([("CHERRY MERCHANT PAYOUT 1234", 15000.0), BIG])
    assert _reading(lump) == LUMP
    assert lump.revenue_match_method == "customer_financing_payer"
    assert "operating_income_descriptor" in lump.revenue_reason
    assert "counted and flagged" not in lump.revenue_reason
    assert (f"never verified, and held for review ({REVENUE_TIER_REASONS['customer_financing_lump_sum'][1]})"
            in lump.revenue_reason)
    (counted,) = _credits([("CHERRY MERCHANT PAYOUT 1234", 2200.0)])
    assert _reading(counted) == CFP
    assert "counted and flagged, never verified" in counted.revenue_reason


def test_the_thresholds_are_whole_unit_integers():
    assert (credit_words.CUSTOMER_FINANCING_LUMP_FLOOR, credit_words.CUSTOMER_FINANCING_LUMP_ROUND,
            credit_words.CUSTOMER_FINANCING_LUMP_SHARE, credit_words.CUSTOMER_FINANCING_SERIES_MIN,
            credit_words.CUSTOMER_FINANCING_SERIES_SHARE) == (10_000, 1_000, 50, 3, 50)


# --- the controls: unchanged ---------------------------------------------------------------------------------------

#: (label, bank, rows, (tier, reason or method) of the first credit).
CONTROLS = (
    ("29 affirm's settlement", "Bank of America",
     [("AFFIRM INC DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD", 1100.0)],
     ("counted_flagged", "payout_credit_entity")),
    ("29 american first finance's settlement", "Bank of America",
     [("AMERICAN FIRST FINANCE DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD", 1100.0)],
     ("counted_flagged", "payout_credit_entity")),
    ("30 an affirm return", None, [("RETURN FOR AFFIRM COM PAYME AFFIRM COM ST ABC", 150.0)],
     ("non_revenue", "financing_proceeds_credit")),
    ("31 synchrony's card settlement", "Bank of America",
     [("SYNCHRONY BANK DES:MTOT DEP ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD", 1866.0)],
     ("verified", "operating_income_descriptor")),
    ("32 goodleap", None, [("ELECTRONIC CREDIT GOODLEAP LLC PAYOUT W1S2J3 AUG 12", 28800.0)],
     ("counted_flagged", "named_payer_purpose_refused")),
    ("33 instacred's wire", None, [("INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA INSTACRED INC", 51000.0)],
     ("excluded_pending_review", "financing_named_payer")),
    ("34 a funder's funding", "Bank of America",
     [("CONTOSO PARTNERS LLC DES:FUNDING ID:1 INDN:NORTHWIND CO ID:1 CCD", 1500.0)],
     ("excluded_pending_review", "financing_named_payer")),
    ("34 a loan funding", None, [("FABRIKAM LOAN FUNDING", 5000.0)], ("non_revenue", "strong_non_revenue_rule")),
    ("35 snap loan funding with no merchant form", None, [("SNAP LOAN FUNDING", 1500.0)],
     ("non_revenue", "strong_non_revenue_rule")),
    ("35 a snap loan to a person", "Bank of America",
     [("SNAP LOAN FUNDING DES:LOAN ID:123 INDN:A SAMPLE CO ID:123 PPD", 1500.0)],
     ("non_revenue", "strong_non_revenue_rule")),
    ("36 snap ebt settlement", None, [("SNAP EBT SETTLEMENT 1234 NORTHWIND GROCERY", 800.0)],
     ("counted_flagged", "named_payer_purpose_refused")),
    ("37 cherry hill plumbing, a customer", "Bank of America",
     [("CHERRY HILL PLUMBING LLC DES:PAYMENT ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD", 900.0)],
     ("verified", "named_payer_company_form")),
    ("39 katapult engineering's refund", "Bank of America",
     [("KATAPULT ENGINEERING DES:REFUND ID:1 INDN:NORTHWIND CO ID:1 CCD", 300.0)],
     ("non_revenue", "reversal_cancellation_exclusion")),
    ("40 katapult's micro pair", None, [("ABCDEF KATAPULT ACH IN", 0.01), ("ABCDEF-KATAPULT ACH PULL", -0.01)],
     ("excluded_pending_review", "payer_also_debited")),
    ("41 progressive's breach settlement", "Bank of America",
     [("PROGRESSIVE LEASING BREACH LITIGATI DES:SETTLEMENT ID:1 INDN:A SAMPLE CO ID:1 PPD", 125.0)],
     ("excluded_pending_review", "financing_named_payer")),
    ("42 progressive card credit", None,
     [("DEBIT CARD CREDIT AUT 123 VISA DDA REF PROGRESSIVE LEASING DRAPER UT 1234", 64.0)],
     ("non_revenue", "reversal_cancellation_exclusion")),
    ("43 snap refund", None, [("SNAP FINANCE REFUND 1234", 150.0)], ("non_revenue", "reversal_cancellation_exclusion")),
    ("43 koalafi withdrawal", None, [("KOALAFI WITHDRAWAL 1234567", 300.0)],
     ("counted_flagged", "named_payer_unlabelled")),
    ("43 acima return", None, [("ACIMA DIGITAL RETURN 1234", 210.0)], ("excluded_pending_review", "possible_return")),
    ("43 cherry technologies refund", "Bank of America",
     [("CHERRY TECHNOLOGIES DES:REFUND ID:123 INDN:A SAMPLE CO ID:123 PPD", 120.0)],
     ("non_revenue", "reversal_cancellation_exclusion")),
    ("43 snap card reward", None, [("SNAP FINANCE CARD REWARD 1234", 25.0)], ("non_revenue", "strong_non_revenue_rule")),
    ("44 snap funding under $1", "Wells Fargo", [(SNAP, 0.50)], ("excluded_pending_review", "financing_named_payer")),
    ("54 katapult engineering, twice", "Bank of America",
     [("KATAPULT ENGINEERING DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 800.0),
      ("KATAPULT ENGINEERING DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 850.0)],
     ("counted_flagged", "named_payer_purpose_refused")),
    ("54 katapult pro, twice", "Bank of America",
     [("KATAPULT PRO DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 800.0),
      ("KATAPULT PRO DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 850.0)],
     ("counted_flagged", "named_payer_purpose_refused")),
    ("55 snap ppd to a person", "Bank of America",
     [("SNAP FINANCE DES:PAYMENT ID:123 INDN:JOHN SAMPLE CO ID:123 PPD", 150.0)],
     ("excluded_pending_review", "financing_named_payer")),
    ("55 koalafi web to a person", "Bank of America",
     [("KOALAFI DES:PAYMENT ID:123 INDN:JANE SAMPLE CO ID:123 WEB", 300.0)],
     ("counted_flagged", "named_payer_purpose_refused")),
    ("55 cherry ppd reimbursement to a person", "Chase",
     [(CHASE_CHERRY.format(entry="REIMB", sec="PPD", name="JOHN SAMPLE"), 220.0)],
     ("excluded_pending_review", "non_sale_purpose")),
)


@pytest.mark.parametrize(("label", "bank", "rows", "reading"), CONTROLS, ids=[case[0] for case in CONTROLS])
def test_the_controls_keep_their_readings(label, bank, rows, reading):
    credits = _credits(rows, bank=bank)
    for record in credits:
        assert (record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method) == reading, label
        assert record.revenue_tier_reason not in {"customer_financing_payout", "customer_financing_lump_sum"}


def test_a_zelle_payment_from_a_person_named_cherry_is_never_claimed():
    # 38 (CR7): never claimed; the rules read it as person-to-person, and the Zelle policy excludes it.
    (record,) = _credits([("ZELLE PAYMENT FROM CHERRY SAMPLE CONF ABC123", 230.0)])
    assert rules_reading(record) == ("counted_flagged", "p2p")
    text = lexical.revenue_text(record.normalized_description)
    assert claimed._customer_financier(record, text) is None


def test_the_cherry_consumer_side_credit_keeps_d1_and_its_lender_credit():
    # OQ2's consumer-side veto, which Cherry now joins: a CHERRY TECHNOLOGIES card credit stays financing proceeds.
    (record,) = _credits([("CHERRY TECHNOLOGIES CARD CREDIT 1234", 120.0)], bank="Bank of America")
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion


# --- audit round 3, R3-B14 (R3-06): a financier's non-sale or financing credit is no merchant payout ------------------


def _bofa(payer, entry, indn="NORTHWIND FURNITURE"):
    return f"{payer} DES:{entry} ID:123 INDN:{indn} CO ID:123 CCD"


def _chase(payer, entry):
    return (f"ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE: CO ENTRY DESCR:{entry} SEC:CCD TRACE#:123456789 "
            "EED:540301 IND ID:123 IND NAME:NORTHWIND FURNITURE")


#: (label, bank, row template ({payer}), the financier's payer, the base payer, the held reason). The base swaps the
#: financier for a payer no claim reads: SAMPLE TECHNOLOGIES, or SAMPLE FINANCE where the financier's own name prints a
#: financing root (SNAP FINANCE, TERRACE FINANCE), so the row reads as the same row from any other payer. Every
#: statement also carries BIG, so no row is a lump sum. Today each is counted_flagged / customer_financing_payout.
NON_SALE = (
    ("koalafi advance, odd cents", "Bank of America", _bofa("{payer}", "ADVANCE"), "KOALAFI", "SAMPLE TECHNOLOGIES",
     "financing_named_payer"),
    ("snap finance advance", "Bank of America", _bofa("{payer}", "ADVANCE"), "SNAP FINANCE", "SAMPLE FINANCE",
     "financing_named_payer"),
    ("chase koalafi advance", "Chase", _chase("{payer}", "ADVANCE"), "KOALAFI", "SAMPLE TECHNOLOGIES",
     "financing_named_payer"),
    ("progressive cash adv", "Wells Fargo", "{payer} CASH ADV 123456 NORTHWIND FURNITURE", "PROGRESSIVE LEASING",
     "SAMPLE TECHNOLOGIES", "financing_named_payer"),
    ("acima capital", "Bank of America", _bofa("{payer}", "CAPITAL"), "ACIMA DIGITAL", "SAMPLE TECHNOLOGIES",
     "financing_named_payer"),
    ("acima rebate", "Bank of America", _bofa("{payer}", "REBATE"), "ACIMA DIGITAL", "SAMPLE TECHNOLOGIES",
     "non_sale_purpose"),
    ("acima dividend", "Bank of America", _bofa("{payer}", "DIVIDEND"), "ACIMA DIGITAL", "SAMPLE TECHNOLOGIES",
     "non_sale_purpose"),
    ("terrace interest", "Bank of America", _bofa("{payer}", "INTEREST"), "TERRACE FINANCE", "SAMPLE FINANCE",
     "financing_named_payer"),
    ("wisetack rebate", "Wells Fargo", "{payer} REBATE 1234 NORTHWIND PLUMBING", "WISETACK", "SAMPLE TECHNOLOGIES",
     "non_sale_purpose"),
)


@pytest.mark.parametrize(("label", "bank", "template", "payer", "base", "reason"), NON_SALE,
                         ids=[case[0] for case in NON_SALE])
@pytest.mark.parametrize("amount", [4870.55, 12345.67])
def test_r3_06_a_financier_s_non_sale_or_financing_credit_is_never_a_payout(label, bank, template, payer, base,
                                                                            reason, amount):
    (record, big) = _credits([(template.format(payer=payer), amount), BIG], bank=bank)
    (twin, _big) = _credits([(template.format(payer=base), amount), BIG], bank=bank)
    assert _reading(record) == _reading(twin) == ("excluded_pending_review", reason), label
    assert record.revenue_review_required and not record.contributes_to_true_revenue
    assert _reading(big) == VERIFIED
    text = lexical.revenue_text(record.normalized_description)
    assert claimed._customer_financier(record, text) is None
    assert not claimed._claimed(record, text)


@pytest.mark.parametrize(("payer", "entry", "reason"), [
    # OQ2's payout entities read the same veto (today counted_flagged / payout_credit_entity).
    ("AFFIRM INC", "ADVANCE", "financing_named_payer"),
    ("KLARNA INC", "REBATE", "non_sale_purpose"),
])
def test_r3_06_an_oq2_payout_entity_s_non_sale_or_financing_credit_is_never_claimed(payer, entry, reason):
    (record, big) = _credits([(_bofa(payer, entry), 4870.55), BIG], bank="Bank of America")
    assert _reading(record) == ("excluded_pending_review", reason)
    assert _reading(big) == VERIFIED
    assert not claimed._claimed(record, lexical.revenue_text(record.normalized_description))


@pytest.mark.parametrize("entry", ["ADVNC", "ADVN", "ADVC"])
def test_r3_06_an_unclaimed_payout_entity_s_credit_is_never_verified_by_q6(entry):
    # A payout entity's credit is counted, never verified: where the veto lifts its claim and no hold reads the word (an
    # abbreviated advance), Q6 never verifies it on its company form; the payout_credit_entity arm counts it.
    *rows, big = _credits([(_bofa("AFFIRM INC", entry), 4870.55), (_bofa("AFFIRM INC", entry), 4990.55), BIG],
                          bank="Bank of America")
    for record in rows:
        assert _reading(record) == ("counted_flagged", "payout_credit_entity")
        assert record.revenue_classification == "unverified_deposit" and not record.contributes_to_verified_revenue
    assert _reading(big) == VERIFIED


@pytest.mark.parametrize("entry", ["ADVNC", "ADVN", "ADVC"])
def test_r3_06_an_unclaimed_financier_s_credit_is_never_verified_by_q6(entry):
    # The same for a financier spelled outside CUSTOMER_FINANCING_NAMES (a bare CHERRY region with a company form):
    # its credit is never a Q6 repeat or company-form verification once the veto lifts its claim.
    *rows, big = _credits([(_bofa("CHERRY INC", entry, "NORTHWIND DENTAL"), 4870.55),
                           (_bofa("CHERRY INC", entry, "NORTHWIND DENTAL"), 4990.55), BIG], bank="Bank of America")
    for record in rows:
        assert record.revenue_tier == "counted_flagged" and not record.contributes_to_verified_revenue
        assert record.revenue_tier_reason != "customer_financing_payout"
    assert _reading(big) == VERIFIED


def test_r3_06_the_hidden_loan_shape_is_held_and_its_debits_keep_their_reading():
    # An advance followed by four weekly debits of the same financier: held, never a payout; the debits unchanged.
    debit = (_bofa("KOALAFI", "PAYMENT"), -437.50)
    records = _records([(_bofa("KOALAFI", "ADVANCE"), 8750.0), BIG] + [debit] * 4, bank="Bank of America")
    credit = records[0]
    assert _reading(credit) == ("excluded_pending_review", "financing_named_payer")
    (alone,) = _records([debit], bank="Bank of America")
    for record in records[2:]:
        assert _debit_view(record) == _debit_view(alone)
        assert (record.classification, record.flagged_group, record.canonical_entity) == (
            "lease_or_rental", "leases_rentals", "Koalafi")


@pytest.mark.parametrize("text", [
    "CHERRY TECHNOLOGIES DES:LOAN ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD",
    "CHERRYPAY DES:LOAN DISB ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD",
    "CHERRY TECHNOLOGIES DES:ADVANCE ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD",
])
def test_r3_06_a_cherry_loan_or_advance_keeps_d1_and_its_lender_credit(text):
    from analysis.metrics import compute_metrics

    customer = ("FABRIKAM SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 15000.0)
    statement = Statement(account_name=HOLDER, bank="Bank of America", transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=row, amount=amount, direction="credit")
        for index, (row, amount) in enumerate([(text, 20000.0), customer])
    ])
    records = classify_statement_transactions(statement)
    loan = records[0]
    # Its reading before the Q8 ruling (today: the strong rule's or a lump sum's, entity None, no lender credit).
    assert (loan.revenue_classification, loan.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert loan.revenue_canonical_entity == "Cherry Technologies, Inc."
    assert loan.contributes_to_lender_credit_exclusion
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lender_credits, metrics.legacy_eligible_deposits) == (20000.0, 15000.0)


@pytest.mark.parametrize(("label", "bank", "rows", "holder"), [
    # The veto never reads the holder's own name: a holder named CAPITAL, in its receiver field or Snap's merchant form.
    ("cherry funding to a capital-named holder", "Bank of America",
     [(_bofa("CHERRY TECHNOLOGIES", "FUNDING", "NORTHWIND CAPITAL DENTAL"), 1300.0)], "NORTHWIND CAPITAL DENTAL LLC"),
    ("snap's merchant form naming a capital-named holder", "Wells Fargo",
     [("SNAP LOAN FUNDING F12345 NORTHWIND CAPITAL DENTAL", 1700.0)], "NORTHWIND CAPITAL DENTAL LLC"),
    # A bare ADV is a payment advice, never an advance.
    ("acima's payment advice", "Bank of America", [(_bofa("ACIMA DIGITAL", "PAYMT ADV"), 1100.0)], HOLDER),
])
def test_r3_06_the_veto_spares_the_holder_s_name_and_a_payment_advice(label, bank, rows, holder):
    for record in _credits(rows, bank=bank, holder=holder):
        assert _reading(record) == CFP, label


def test_r3_06_a_lessor_s_loan_proceeds_keep_the_strong_rule():
    (record,) = _credits([(_bofa("KATAPULT", "LOAN PROC"), 1700.0)], bank="Bank of America")
    assert (record.revenue_tier, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")


@pytest.mark.parametrize(("text", "read"), [
    ("ADVANCE", True), ("ADVANCES", True), ("ADVNC", True), ("ADVN", True), ("ADVC", True), ("CASH ADV", True),
    ("CASH ADVANCE", True), ("CAPITAL", True), ("CAPTL", True), ("INTEREST", True), ("DIVIDEND", True),
    ("DIVIDENDS", True), ("REBATE", True), ("REBATES", True),
    ("FUNDING", False), ("FUNDED", False), ("PAYOUT", False), ("PAYMENT", False), ("LEASE FUND", False),
    ("PAYMT ADV", False), ("ADV", False), ("PROCEEDS", False), ("LOAN", False), ("ADVANCED", False),
    ("NORTHWINDCAPITAL", False),
])
def test_r3_06_the_non_sale_and_financing_words(text, read):
    assert bool(words._PAYOUT_NON_SALE_CREDIT.search(text)) is read


# --- audit round 3, R3-B14 (R3-54): a cut Katapult Engineering name is the namesake ---------------------------------


@pytest.mark.parametrize("name", ["KATAPULT ENGINEE", "KATAPULT ENG", "KATAPULT ENGIN", "KATAPULT ENGINEERIN"])
def test_r3_54_a_cut_katapult_engineering_name_is_the_namesake(name):
    def readings(payer, rows):
        return [_reading(record) for record in _credits([(row.format(payer=payer), amount) for row, amount in rows],
                                                        bank="Bank of America")]

    pair = [("{payer} DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 800.0),
            ("{payer} DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 850.0)]
    assert readings(name, pair) == readings("KATAPULT ENGINEERING", pair) == [
        ("counted_flagged", "named_payer_purpose_refused")] * 2
    # A one-off of 15,000 is counted as the full name's is, never a lump sum.
    one_off = [("{payer} DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 15000.0),
               ("FABRIKAM SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 9000.0),
               ("FABRIKAM SUPPLY LLC DES:PAYMENT ID:2 INDN:NORTHWIND CO ID:1 CCD", 9000.0)]
    assert readings(name, one_off) == readings("KATAPULT ENGINEERING", one_off)
    assert readings(name, one_off)[0] == ("counted_flagged", "named_payer_purpose_refused")
    # A remittance-worded series reads as the full name's.
    series = [("{payer} DES:VENDOR PMT ID:%d INDN:NORTHWIND CO ID:1 CCD" % index, 800.0 + index) for index in range(3)]
    assert readings(name, series) == readings("KATAPULT ENGINEERING", series)
    assert _financier(f"{name} DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", bank="Bank of America") is None


@pytest.mark.parametrize("text", [
    "KATAPULT DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD",
    "KATAPULT GROUP INC DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD",
])
def test_r3_54_the_lessor_s_own_name_is_still_katapult(text):
    (record,) = _credits([(text, 900.0)], bank="Bank of America")
    assert _reading(record) == CFP
    assert _financier(text, amount=900.0, bank="Bank of America") == "Katapult"


# --- audit round 3, R3-B14 review round 1 (findings 1 and 2) ---------------------------------------------------------

#: Finding 1: Cherry's layouts that print the holder's name with no label (Wells Fargo's trailing receiver, TD's ACH
#: DEPOSIT, a generic ACH CREDIT), as (bank, row template with {entry} and {name}).
_R1_CHERRY_LABELLESS = (
    ("Wells Fargo", "CHERRY TECHNOLOG {entry} 540301 123456 {name}"),
    ("TD Bank", "ACH DEPOSIT CHERRYPAY {entry} {name}"),
    (None, "ACH CREDIT CHERRY TECHNOLOGIES {entry} {name}"),
)
#: Fabricated practices whose own names print a veto word, leading or inside the name.
_R1_VETO_HOLDERS = ("CAPITAL CONTOSO DENTAL LLC", "NORTHWIND ADVANCE DENTAL LLC", "INTEREST FREE NORTHWIND SMILES LLC")
_R1_CUSTOMER = ("FABRIKAM SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", 15000.0)


def _r1_cherry(bank, template, entry, holder, amount=1300.0):
    from analysis.metrics import compute_metrics

    statement = Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=row, amount=value, direction="credit")
        for index, (row, value) in enumerate([
            (template.format(entry=entry, name=holder.removesuffix(" LLC")), amount), _R1_CUSTOMER])
    ])
    records = classify_statement_transactions(statement)
    return records[0], compute_metrics(statement, classifications=records)


@pytest.mark.parametrize(("bank", "template"), _R1_CHERRY_LABELLESS, ids=["wells", "td", "generic"])
@pytest.mark.parametrize("holder", _R1_VETO_HOLDERS)
@pytest.mark.parametrize("entry", ["FUNDING", "PAYOUT"])
def test_r3_b14_r1_cherry_s_d1_veto_never_reads_the_holder_s_unlabelled_name(bank, template, holder, entry):
    # Finding 1: the classifier's Cherry veto reads the row without the holder's names, as the pass's veto does, so a
    # practice whose own name prints CAPITAL, ADVANCE or INTEREST keeps its Cherry payouts (counted and flagged, no
    # lender credit; at 3939f5c each was financing proceeds, entity Cherry, the lender-credit exclusion on).
    record, metrics = _r1_cherry(bank, template, entry, holder)
    assert _reading(record) == CFP
    assert record.revenue_match_method != "financing_proceeds_credit"
    assert not record.contributes_to_lender_credit_exclusion and record.canonical_entity is None
    assert (metrics.lender_credits, metrics.legacy_eligible_deposits) == (0.0, 16300.0)


@pytest.mark.parametrize(("bank", "template"), _R1_CHERRY_LABELLESS, ids=["wells", "td", "generic"])
@pytest.mark.parametrize("entry", ["ADVANCE", "LOAN", "REBATE"])
def test_r3_b14_r1_cherry_s_own_loan_or_advance_word_still_keeps_d1_on_those_layouts(bank, template, entry):
    # The control: the same layouts and holder, the veto word printed outside the holder's name: D1, as R3-06 ruled.
    record, metrics = _r1_cherry(bank, template, entry, _R1_VETO_HOLDERS[0])
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert record.revenue_canonical_entity == "Cherry Technologies, Inc."
    assert record.contributes_to_lender_credit_exclusion
    assert (metrics.lender_credits, metrics.legacy_eligible_deposits) == (1300.0, 15000.0)


def test_r3_b14_r1_the_classifier_s_cherry_veto_reads_the_holder_s_names_out():
    match = payee_matcher.match_known_payee("CHERRY TECHNOLOG FUNDING 540301 123456 CAPITAL CONTOSO DENTAL", credit=True)
    assert match is not None and match.entity == "Cherry Technologies, Inc."
    row = "CHERRY TECHNOLOG FUNDING 540301 123456 CAPITAL CONTOSO DENTAL"
    assert credit_decision._is_payout_credit(row, match, account_name="CAPITAL CONTOSO DENTAL LLC")
    # Without the holder's name the word is read, as R3-06 reads any Cherry row printing it.
    assert not credit_decision._is_payout_credit(row, match)
    assert not credit_decision._is_payout_credit(row.replace("FUNDING", "ADVANCE"), match,
                                            account_name="CAPITAL CONTOSO DENTAL LLC")


#: Finding 2: a financier's large one-off abbreviated advance (ADVNC, ADVN, ADVC: words no hold reads) whose claim the
#: veto lifted, as (label, bank, row, holder, the customer beside it).
_R1_LUMPS = (
    ("koalafi advnc, whole thousands", "Bank of America", (_bofa("KOALAFI", "ADVNC"), 20000.0), HOLDER, BIG),
    ("acima advn, whole thousands", "Bank of America", (_bofa("ACIMA DIGITAL", "ADVN"), 25000.0), HOLDER, BIG),
    ("katapult advc, whole thousands", "Bank of America", (_bofa("KATAPULT", "ADVC"), 12000.0), HOLDER, BIG),
    ("a bare cherry advnc, whole thousands", "Bank of America",
     (_bofa("CHERRY INC", "ADVNC", "NORTHWIND DENTAL"), 20000.0), "NORTHWIND DENTAL LLC", BIG),
    ("acima advnc, half the statement's credits", "Bank of America", (_bofa("ACIMA DIGITAL", "ADVNC"), 12345.67),
     HOLDER, (BIG[0], 9000.0)),
    ("wisetack's incoming wire, odd cents", "Bank of America",
     (BOFA_WIRE.format(payer="WISETACK LLC") + " OBI:ADVNC", 15432.10), HOLDER, BIG),
)


@pytest.mark.parametrize(("label", "bank", "row", "holder", "customer"), _R1_LUMPS, ids=[case[0] for case in _R1_LUMPS])
def test_r3_b14_r1_a_large_one_off_abbreviated_advance_stays_held_until_sourced(label, bank, row, holder, customer):
    # Finding 2: the veto lifts the claim, but the lump-sum test still reads the row as the financier's (at 3939f5c it
    # was counted: a named payer's or a wire sender's reading); the base's reading, held, returns.
    (record, other) = _credits([row, customer], bank=bank, holder=holder)
    assert _reading(record) == LUMP, label
    assert record.revenue_classification == "unverified_deposit"
    assert record.revenue_review_required and not record.contributes_to_true_revenue
    assert not claimed._claimed(record, lexical.revenue_text(record.normalized_description))
    assert _reading(other) == VERIFIED


def test_r3_b14_r1_a_small_or_serial_abbreviated_advance_is_counted_never_verified():
    # The controls: a small odd-cents advance is no lump sum, and three of a size from one financier are a series, as
    # the payouts were before the veto: counted, never verified; a payout entity's lump sum keeps its payout reading.
    (small, _big) = _credits([(_bofa("KOALAFI", "ADVNC"), 4870.55), BIG], bank="Bank of America")
    assert _reading(small) == ("counted_flagged", "named_payer_purpose_refused")
    *series, _big = _credits([(_bofa("ACIMA DIGITAL", "ADVNC"), amount) for amount in (10000.0, 12000.0, 11000.0)]
                             + [BIG], bank="Bank of America")
    for record in series:
        assert record.revenue_tier == "counted_flagged" and not record.contributes_to_verified_revenue
    (affirm, _big) = _credits([(_bofa("AFFIRM INC", "ADVNC"), 20000.0), BIG], bank="Bank of America")
    assert _reading(affirm) == ("counted_flagged", "payout_credit_entity")
    # A real payout beside it keeps the lump-sum test's reading.
    (payout, _big) = _credits([(_bofa("KOALAFI", "FUNDING"), 20000.0), BIG], bank="Bank of America")
    assert _reading(payout) == LUMP


# --- the debits: unchanged ------------------------------------------------------------------------------------------

#: 45: (debit text, classification, flagged group, canonical entity).
DEBITS = (
    ("SNAP FINANCE PAYMENT 1234", "lease_or_rental", "leases_rentals", "SNAP Finance"),
    ("KOALAFI PAYMENT 1234", "lease_or_rental", "leases_rentals", "Koalafi"),
    ("ACIMA DIGITAL PAYMENT 1234", "lease_or_rental", "leases_rentals", "Acima"),
    ("PROGRESSIVE LEASING PAYMENT 1234", "lease_or_rental", "leases_rentals", "Progressive Leasing"),
    ("KATAPULT PAYMENT 1234", "lease_or_rental", "leases_rentals", "Katapult"),
    ("CHERRY TECHNOLOGIES PAYMENT 1234", "alternative_position", "alternative_positions", "Cherry Technologies, Inc."),
    ("CHERRYPAY*NORTHWIND DENTAL 800-123-4567 CA CARD 1234", "alternative_position", "alternative_positions",
     "Cherry Technologies, Inc."),
    ("CHERRY PAYMENT 1234", "other", None, None),
    ("WISETACK PAYMENT 1234", "other", None, None),
    ("TERRACE FINANCE PAYMENT 1234", "other", None, "Terrace Finance"),
)


def _debit_view(record):
    """A debit's lender-side reading: its class, flag group and entity, and every lender, potential-lender, withholding
    and reversal field."""
    return (record.classification, record.flagged_group, record.canonical_entity, record.reversed_by,
            record.contributes_to_lender_count, record.contributes_to_potential_lender_count,
            record.contributes_to_lender_totals, record.contributes_to_withholding_rate,
            record.contributes_to_potential_lender_totals, record.contributes_to_potential_withholding_exposure,
            record.contributes_to_flagged_totals)


@pytest.mark.parametrize(("text", "classification", "group", "entity"), DEBITS, ids=[case[0] for case in DEBITS])
def test_a_financier_s_debit_keeps_its_reading_alone_and_beside_its_payout(text, classification, group, entity):
    (alone,) = _records([(text, -150.0)])
    assert (alone.classification, alone.flagged_group, alone.canonical_entity) == (classification, group, entity)
    beside = [record for record in _records([(SNAP, 1500.0), ("CHERRY FUNDING 123456", 1500.0), (text, -150.0)])
              if record.amount < 0]
    assert [_debit_view(record) for record in beside] == [_debit_view(alone)]


# --- the reader --------------------------------------------------------------------------------------------------


def _financier(text, amount=1500.0, bank=None, holder=HOLDER):
    (record,) = _credits([(text, amount)], bank=bank, holder=holder)
    return claimed._customer_financier(record, lexical.revenue_text(record.normalized_description))


@pytest.mark.parametrize(("text", "bank", "entity"), [
    (SNAP, "Wells Fargo", "SNAP Finance"),
    ("SNAP LOAN FUNDING F12345 NORTHWIND FURNITURE", "Wells Fargo", "SNAP Finance"),
    ("KOALAFI LEASE FUND 1234567 1 CONTOSO SAMPLE", "Wells Fargo", "Koalafi"),
    (CHASE_CHERRY.format(entry="FUNDING", sec="CCD", name="NORTHWIND DENTAL"), "Chase", "Cherry Technologies, Inc."),
    ("CHERRY FUNDING 123456", None, "Cherry Technologies, Inc."),
    ("CHERRY INC DES:PAYMENT ID:1 INDN:NORTHWIND DENTAL CO ID:1 CCD", "Bank of America", "Cherry Technologies, Inc."),
    (CHERRY_TECH, "Bank of America", "Cherry Technologies, Inc."),
    (ACIMA_AP, "Wells Fargo", "Acima"),
    ("TERRACE FINANCE TERRACE", None, "Terrace Finance"),
    (HATCH_WISETACK, "Capital One", "Wisetack"),
    ("KATAPULT DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD", "Bank of America", "Katapult"),
    ("PROG LEASING DES:FUNDING ID:123 INDN:NORTHWIND FURNITURE CO ID:123 CCD", "Bank of America", "Progressive Leasing"),
    (SNAP_WIRE, "Bank of America", "SNAP Finance"),
    # Never: a bare CHERRY in a longer name, the KatapultPro namesake, Snap's loan with no merchant form, a refund, a
    # class-action payout, a consumer entry to a person, a check, a person-to-person rail, a sub-$1 credit.
    ("CHERRY HILL PLUMBING LLC DES:PAYMENT ID:123 INDN:NORTHWIND DENTAL CO ID:123 CCD", "Bank of America", None),
    ("KATAPULT ENGINEERING DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", "Bank of America", None),
    ("KATAPULT PRO DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", "Bank of America", None),
    # Audit round 3, R3-B14 (R3-54): Katapult Engineering's cut company field is the namesake too.
    ("KATAPULT ENGINEE DES:PAYMENT ID:1 INDN:NORTHWIND CO ID:1 CCD", "Bank of America", None),
    ("SNAP LOAN FUNDING", None, None),
    ("SNAP FINANCE REFUND 1234", None, None),
    ("PROGRESSIVE LEASING BREACH LITIGATI DES:SETTLEMENT ID:1 INDN:A SAMPLE CO ID:1 PPD", "Bank of America", None),
    ("SNAP FINANCE DES:PAYMENT ID:123 INDN:JOHN SAMPLE CO ID:123 PPD", "Bank of America", None),
    ("MOBILE DEPOSIT SNAP FINANCE CHECK 1234", None, None),
    ("ZELLE PAYMENT FROM CHERRY SAMPLE CONF ABC123", None, None),
])
def test_the_reader_names_the_financier_on_the_payer_region(text, bank, entity):
    assert _financier(text, bank=bank) == entity


def test_the_reader_refuses_a_credit_under_the_floor():
    assert _financier(SNAP, amount=0.50, bank="Wells Fargo") is None


def test_the_census_fact_is_the_reader_s():
    (record,) = _credits([(SNAP, 1500.0)], bank="Wells Fargo")
    text = lexical.revenue_text(record.normalized_description)
    assert guards.guard_facts(record, text)["customer_financing_payer"] == "SNAP Finance"
    assert guards.guard_facts(record, text)["claimed"]


def test_a_row_naming_a_financier_never_counts_toward_a_q6_repeat():
    # CUSTOMER_FINANCING_NAMES: a row that names a financier outside its payer region (here in another payer's entry
    # field, which the claim never reads) is no Q6 repeat either: counted, never verified (it was a verified repeat).
    records = _credits([("CONTOSO HOME SERVICES LLC DES:WISETACK ID:1 INDN:NORTHWIND CO ID:1 CCD", 900.0),
                        ("CONTOSO HOME SERVICES LLC DES:WISETACK ID:2 INDN:NORTHWIND CO ID:1 CCD", 950.0)],
                       bank="Bank of America")
    assert [_reading(record) for record in records] == [("counted_flagged", "named_payer_one_off")] * 2
    assert all(claimed._customer_financier(record, lexical.revenue_text(record.normalized_description)) is None
               for record in records)


# --- the registry and the reason table -------------------------------------------------------------------------------


def test_the_registry_names_the_eight_financiers_and_cherry_joins_the_payout_entities():
    assert list(registry.CUSTOMER_FINANCING_PAYERS) == [
        "SNAP Finance", "Koalafi", "Cherry Technologies, Inc.", "Acima", "Terrace Finance", "Wisetack", "Katapult",
        "Progressive Leasing",
    ]
    assert "Cherry Technologies, Inc." in registry.PAYOUT_CREDIT_ENTITIES
    assert "Cherry Technologies, Inc." in credit_decision._OQ2_BNPL_ENTITIES
    # Audit round 3, R3-B14 (R3-54): the names miss every cut form of Katapult Engineering, and read the lessor's own.
    import re

    names = re.compile(registry.CUSTOMER_FINANCING_NAMES)
    for namesake in ("KATAPULT ENG", "KATAPULT ENGIN", "KATAPULT ENGINEE", "KATAPULT ENGINEERIN",
                     "KATAPULT ENGINEERING", "KATAPULT PRO"):
        assert names.search(f"{namesake} DES PAYMENT") is None, namesake
        assert re.search(registry.CUSTOMER_FINANCING_PAYERS["Katapult"], namesake) is None, namesake
    for lessor in ("KATAPULT", "KATAPULT DES FUNDING", "KATAPULT GROUP INC", "123456 KATAPULT ACH IN"):
        assert names.search(lessor) and re.search(registry.CUSTOMER_FINANCING_PAYERS["Katapult"], lessor), lessor
    # §15's deferred payers keep their lease-to-own line (left as it is; it overlaps CUSTOMER_FINANCING_NAMES).
    assert r"|(?<![A-Z])(?:APPLIED SYSTEMS|ACIMA|KATAPULT|KOALAFI|PROGRESS BILLING|ECOMMISSION)\b" in (
        registry.SECTION_15_DEFERRED_PAYERS)


def test_the_two_reasons_sit_at_their_places_in_the_reason_table():
    codes = list(REVENUE_TIER_REASONS)
    assert codes[codes.index("financing_named_payer") + 1] == "customer_financing_lump_sum"
    assert codes[codes.index("payout_credit_entity") + 1] == "customer_financing_payout"
    assert REVENUE_TIER_REASONS["customer_financing_lump_sum"] == (
        "excluded_pending_review", "One-off lump sum from a lease-to-own or patient financier")
    assert REVENUE_TIER_REASONS["customer_financing_payout"] == (
        "counted_flagged", "Lease-to-own or patient-financing payout")
    assert (true_revenue_words.CUSTOMER_FINANCING_PAYOUT, pass7.CUSTOMER_FINANCING_LUMP_SUM) == (
        "customer_financing_payout", "customer_financing_lump_sum")
