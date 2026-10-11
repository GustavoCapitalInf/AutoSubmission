"""Audit I26 (by Q6 of 2026-09-28, "insurers never count", and the last sentence of the underwriter's Q2 (2026-10-02)
option the owner picked, "a one-off claim paid to a business on its own policy stays out"; R2-OW07): the insurer
reading covers every spelling and brand. A one-off insurer credit spelled INS, a cut form (ASSUR, MUTUA, CASUALT,
INDEMN), ASSURANCES, ASSURANT, ASSUREUR, P AND C at a name's end, LOSS PMT, SUBRO or one of INSURER_CREDIT_BRANDS'
carriers is held as insurer_named_payer, exactly as the same credit spelled INSURANCE is held; the reading is read
without the holder's own names. This file is the reader and the hold, and (owner ruling 2026-10-02, the underwriter's
Q2, "True revenue", option 2; R2-OW08) the release that counts an insurer paid for the business's work on the same
reader: counted_flagged / insurer_paid_for_services, never verified and never a Q5 or Q6 repeat, on a holder's trade
(a repair shop, an insurance agency, a clinic or a pharmacy), a service form (DRP, an agent's EFT, a commission, a
repair, a vendor payment) or three or more credits from one insurer within an inclusive 31-day span; the statement arm
is an owner switch, OFF.

Fabricated rows only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE; public carriers by their public names), in Bank of
America's DES layout unless stated, 2054 dates. "Today" is the reading before this batch (c486fd5 and the owner
batches before this one)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis import classification_registry as registry
from analysis import true_revenue
from analysis.revenue import REVENUE_TIER_REASONS
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import (
    classify_statement_transactions,
    entry_fields,
    payer_region,
    revenue_text,
)
from tests.zelle_reading import rules_reading

BAKERY = "CONTOSO BAKERY LLC"
#: A holder whose name shares no word with the government payers' fabricated 'STATE OF CONTOSO' rows.
NORTHWIND_BAKERY = "NORTHWIND BAKERY LLC"
REPAIR_SHOP = "CONTOSO AUTO REPAIR LLC"
CLINIC = "CONTOSO PHYSIOTHERAPY INC"
AGENCY = "FABRIKAM INSURANCE AGENCY LLC"
TRUIST_AGENCY = "FABRIKAM INSURANCE AGENCY INC"
ROOT = Path(__file__).resolve().parents[1]

HELD = ("excluded_pending_review", "insurer_named_payer")
VERIFIED = ("verified", None)
#: Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: an insurer paid for the business's work.
COUNTED = ("counted_flagged", "insurer_paid_for_services")
METHOD = "insurer_paid_for_services"


def _records(rows, *, holder: str = BAKERY, bank: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _readings(rows, **statement):
    return [rules_reading(record) for record in _records(rows, **statement) if record.amount > 0]


def _reader(text: str, *, holder: str = BAKERY, bank: str | None = None, amount: float = 1234.0):
    """The insurer reading of a one-row statement's credit, as (key, kind, for_work), or None."""
    record = _records([(text, amount)], holder=holder, bank=bank)[0]
    row = revenue_text(record.normalized_description)
    reading = true_revenue.insurer_payer_reading(record, row, payer_region(row), entry_fields(row))
    return None if reading is None else (reading.key, reading.kind, reading.for_work)


def _expected(key: str, kind: str, for_work: bool) -> tuple[str, str, bool]:
    return key, kind, for_work


def insurer_credit_brand(text: str) -> str | None:
    return true_revenue.insurer_credit_brand(text)


# ---------------------------------------------------------------------------------------------------------------------
# The hold: rows the widened reading holds (each counted or verified today), and the controls that keep their tier.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # T9: the INS abbreviation, a one-off at a bakery (today counted named_payer_one_off).
    pytest.param([("SAMPLE INS CO DES:PAYMENT ID:1", 1234.0)], {}, [HELD], id="T9"),
    # T9b: the same row twice (today verified named_payer_repeats; the census declares q5_q6_held_insurer).
    pytest.param([("SAMPLE INS CO DES:PAYMENT ID:1", 1234.0), ("SAMPLE INS CO DES:PAYMENT ID:2", 1290.5)], {},
                 [HELD, HELD], id="T9b"),
    # T9c: a carrier brand with the abbreviation (today counted).
    pytest.param([("FARMERS INS DES:PAYMENT ID:1", 1234.0)], {}, [HELD], id="T9c"),
    # A brand that prints no insurer word (today counted named_payer_one_off).
    pytest.param([("SAFECO DES:PAYMENT ID:1", 1234.0)], {}, [HELD], id="brand-safeco"),
    # A subrogation recovery and a property-and-casualty carrier named at a name's end (today counted).
    pytest.param([("FABRIKAM SUBROGATION DES:PAYMENT ID:1", 1234.0)], {}, [HELD], id="subro"),
    pytest.param([("UNIVERSAL P AND C DES:PAYMENT ID:1", 1234.0)], {}, [HELD], id="p-and-c"),
    # A loss payment printed on an unlabelled payer region, and a cut CASUALT (today counted).
    pytest.param([("SAMPLE LOSS PMT 1234", 1234.0)], {}, [HELD], id="loss-pmt"),
    pytest.param([("ACH CREDIT SAMPLE CASUALT 1234", 1234.0)], {}, [HELD], id="cut-casualt"),
    # A carrier's direct deposit printing INS and a cut ASS twice (today verified named_payer_repeats); two credits are
    # no ground of the underwriter's Q2 (R2-OW08).
    pytest.param([("DIRECT DEPOSIT SAMPLE RISK INS ASS", 1234.0), ("DIRECT DEPOSIT SAMPLE RISK INS ASS", 1290.0)],
                 {}, [HELD, HELD], id="ins-direct-deposit-repeat"),
    # T30's Travelers, T3, T3b and T34 (held by R2-OW07 until the release): counted by R2-OW08's release, below.
    # T7: the spelled-out insurer with CLAIM, at a bakery: held as today.
    pytest.param([("FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT ID:1", 1234.0)], {}, [HELD], id="T7"),
    # T15: three title-insurer wires at a repair shop: held insurer_named_payer (the INS one was non_sale_purpose's
    # title hold today; the title insurer's reading is never for work).
    pytest.param([("WIRE TYPE:WIRE IN ORIG:CONTOSO TITLE INSURANCE CO ID:1", 5000.0),
                  ("WIRE TYPE:WIRE IN ORIG:FABRIKAM TITLE INS CO ID:2", 4000.0),
                  ("WIRE TYPE:WIRE IN ORIG:NORTHWIND TITLE INSURANCE AGENCY ID:3", 3000.0)],
                 {"holder": REPAIR_SHOP}, [HELD, HELD, HELD], id="T15"),
    # The insurer hold precedes the pay hold (today payroll_or_salary) on a row no ground of Q2 releases (a bakery).
    # At a repair shop, T16, the release passes the insurer hold and the pay hold names the row (R2-OW08, below).
    pytest.param([("FARMERS INS DES:PAYROLL ID:1", 1234.0)], {}, [HELD], id="insurer-hold-before-the-pay-hold"),
    # T32: an insurer's wire whose REF names the sending bank: held as today.
    pytest.param([("WIRE TYPE:WIRE IN ORIG:SAMPLE MUTUAL INSURANCE CO REF COMM BANK NYC ID:1", 5000.0)], {}, [HELD],
                 id="T32"),
    # T36: a disability insurer paying three times in a month: held as today.
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:DISABILITY ID:1", 812.0),
                  ("SAMPLE MUTUAL INSURANCE DES:DISABILITY ID:2", 812.0),
                  ("SAMPLE MUTUAL INSURANCE DES:DISABILITY ID:3", 812.0)], {}, [HELD, HELD, HELD], id="T36"),
])
def test_an_insurer_however_it_is_spelled_is_held(rows, statement, expected):
    records = [record for record in _records(rows, **statement) if record.amount > 0]
    assert [rules_reading(record) for record in records] == expected
    for record, reading in zip(records, expected):
        if reading == HELD:
            assert record.revenue_classification == "unverified_deposit"
            assert record.revenue_review_required is True


@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # T12: BCBS's HCCLAIMPMT keeps verifying (T18's claim-first rule).
    pytest.param([("BCBS OF CONTOSO DES:HCCLAIMPMT ID:1", 1234.0)], {"holder": "CONTOSO DENTAL PLLC"}, [VERIFIED],
                 id="T12"),
    # An unlisted insurer's HCCLAIMPMT is a claim paid to a provider: verified, never the insurer's reading.
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:HCCLAIMPMT ID:1", 1234.0)], {"holder": "CONTOSO DENTAL PLLC"},
                 [VERIFIED], id="hcclaimpmt-unlisted-insurer"),
    # T13: a healthcare payer verifies by Q6c.
    pytest.param([("UNITED HEALTHCARE DES:PAYMENT ID:1", 1234.0)], {}, [VERIFIED], id="T13"),
    # T13b: a healthcare payer is an insurer only by the spelled words, so its INS keeps Q6c's premium refusal.
    pytest.param([("AETNA LIFE INS DES:AETNA PREM ID:1", 1234.0)], {},
                 [("counted_flagged", "named_payer_purpose_refused")], id="T13b"),
    # T8: a listed insurer once: the insurance rule's non_revenue.
    pytest.param([("GEICO INSURANCE EFT", 1234.0)], {}, [("non_revenue", None)], id="T8"),
    # T11: an insurer's refund: non_revenue.
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:REFUND ID:1", 1234.0)], {"holder": REPAIR_SHOP},
                 [("non_revenue", None)], id="T11"),
    # T20: Progressive Leasing is no insurer (the underwriter's Q8 counts its merchant payout).
    pytest.param([("PROGRESSIVE LEASING DES:MERCH PMT ID:1", 1234.0)], {},
                 [("counted_flagged", "customer_financing_payout")], id="T20"),
    # T25: a §15 deferred carrier's health-plan row with no insurer word keeps its counted tier, at a clinic, on any
    # bank's statement.
    pytest.param([("MISC PAYMENT SUN LIFE SUNLIFE MED ASO", 76.5)], {"holder": CLINIC},
                 [("counted_flagged", "named_payer_purpose_refused")], id="T25"),
    pytest.param([("MISC PAYMENT SUN LIFE SUNLIFE MED ASO", 76.5)], {"holder": CLINIC, "bank": "RBC"},
                 [("counted_flagged", "named_payer_purpose_refused")], id="T25-rbc"),
    # A deferred carrier printing the abbreviation: the widened spellings never read a §15 deferred payer.
    pytest.param([("SUN LIFE INS CO DES:PAYMENT ID:1", 1234.0)], {"holder": CLINIC},
                 [("counted_flagged", "named_payer_purpose_refused")], id="deferred-carrier-ins"),
    # T25c: a Q6-verified glued health-plan row stays verified.
    pytest.param([("MISC PAYMENT SAMPLE ASO SUNLIFE MED ASO", 76.5), ("MISC PAYMENT SAMPLE ASO SUNLIFE MED ASO", 95.2)],
                 {"holder": CLINIC}, [VERIFIED, VERIFIED], id="T25c"),
    # T27: ASSURED is no insurer spelling; T27b: nor P AND C before another word.
    pytest.param([("ASSURED STAFFING LLC DES:PAYMENT ID:1", 1234.0), ("ASSURED STAFFING LLC DES:PAYMENT ID:2", 1290.5)],
                 {}, [VERIFIED, VERIFIED], id="T27"),
    pytest.param([("P AND C FOODS DES:PAYMENT ID:1", 1234.0), ("P AND C FOODS DES:PAYMENT ID:2", 1290.5)], {},
                 [VERIFIED, VERIFIED], id="T27b"),
    # T28, T28b: the brand table never reads the urgent-care chain or a contractor.
    pytest.param([("AMERICAN FAMILY CARE DES:PAYMENT ID:1", 1234.0)], {},
                 [("counted_flagged", "named_payer_one_off")], id="T28"),
    pytest.param([("NATIONAL GENERAL CONTRACTORS DES:PAYMENT ID:1", 1234.0)], {},
                 [("counted_flagged", "named_payer_one_off")], id="T28b"),
    # Lookalikes of the brands: a cash service, a florist, a bank.
    pytest.param([("TRAVELERS CASH DES:PAYMENT ID:1", 1234.0)], {}, [("counted_flagged", "named_payer_one_off")],
                 id="travelers-cash"),
    pytest.param([("FARMERS IN BLOOM LLC DES:PAYMENT ID:1", 1234.0)], {}, [VERIFIED], id="farmers-in-bloom"),
    pytest.param([("SUNLIFE SOLAR LLC DES:PAYMENT ID:1", 1234.0)], {}, [VERIFIED], id="sunlife-solar"),
])
def test_the_controls_keep_their_reading(rows, statement, expected):
    assert _readings(rows, **statement) == expected


def test_t21_the_holder_s_own_insurance_word_never_makes_its_payer_an_insurer():
    """T21 (Truist's unlabelled receiver): the holder's name, cut by the bank's field, prints the INSURANCE word; read
    without the holder's names the payer is no insurer. Today held insurer_named_payer; at this tip the holder test does
    not read the name in the middle of the region, so the row is the named payer's counted credit (R2-B04's reading of
    the holder; the card's simulation, on c486fd5, read it as holder_name)."""
    rows = [("CREF NORTHWIND FABRIKAM INSURANCE AGEN CUSTOMER ID 1234", 812.4)]
    reading = _readings(rows, holder=TRUIST_AGENCY, bank="Truist")
    assert reading != [HELD]
    assert reading == [("counted_flagged", "named_payer_unlabelled")]
    assert _reader(rows[0][0], holder=TRUIST_AGENCY, bank="Truist", amount=812.4) is None


def test_t33_a_listed_insurer_printed_beside_the_holder_s_name_is_released_where_the_holder_test_reads_no_holder():
    """T33 (re-pinned, R2-OW08; the brief allows it where R2-B04's holder reading differs from the card's simulation):
    GEICO's credit printed before the agency's own name is a listed insurer's (the insurance rule's non_revenue
    before the release). The holder test reads the holder's name printed after GEICO as GEICO's unlabelled receiver,
    never the payer (audit B9, I13), so the row is released on the agency's trade and counted; where the holder test
    does read the holder's name as the payer, the row is held holder_name and never counted (the control)."""
    from analysis.transaction_classifier import holder_named

    text = "EFT GEICO INSURANCE FABRIKAM INSURANCE AGEN CUSTOMER ID 1234"
    record = _records([(text, 2400.0)], holder=TRUIST_AGENCY, bank="Truist")[0]
    row = revenue_text(record.normalized_description)
    assert not holder_named(payer_region(row), TRUIST_AGENCY)
    assert rules_reading(record) == COUNTED
    assert record.revenue_canonical_entity == "GEICO"
    # The control: the agency's own name as the payer region is the holder's, never counted.
    assert _readings([("NORTHWIND LLC FABRIKAM INSURANCE AGENCY", 812.0)], holder=AGENCY) == [
        ("excluded_pending_review", "holder_name")
    ]


def test_t6_and_t25b_a_deferred_carrier_named_by_today_s_words_counts_at_a_clinic():
    """T6 and T25b (re-pinned, R2-OW08): RBC's 'INSURANCE MANULIFE' and 'HEALTH DENTAL CLAIM MANULIFE' (the spelled
    word and CLAIM read a §15 deferred payer) at a clinic are counted on the holder's trade, never verified; at a bakery
    the one-off stays held as today."""
    assert _readings([("INSURANCE MANULIFE", 95.2)], holder=CLINIC, bank="RBC") == [COUNTED]
    assert _readings([("HEALTH DENTAL CLAIM MANULIFE", 67.5)], holder=CLINIC, bank="RBC") == [COUNTED]
    assert _readings([("INSURANCE MANULIFE", 95.2)], holder=BAKERY, bank="RBC") == [HELD]


def test_a_listed_insurer_s_cut_spelling_stays_the_insurance_rule_s_non_revenue():
    """T23b: State Farm's Symitar cut form is the insurance rule's (non_revenue), never this hold."""
    record = _records([("ACH DEPOSIT STATE FARM MUTUA PAYMENTS CONTOSO AUTO REBODY", 4100.0)])[0]
    assert rules_reading(record) == ("non_revenue", None)
    assert record.revenue_match_method == "insurance_provider_credit_exclusion"


def test_a_customer_payment_from_a_listed_insurer_is_released_on_its_service_form():
    """T2 (re-pinned, R2-OW08): State Farm's DRP payment is the direct-repair program paying for work (the service
    form), counted, never verified. T24: under the $1 floor the release refuses it and arm 1 keeps insurer_payer."""
    assert _readings([("STATE FARM DES:DRP PAYMENT ID:1", 1234.0)]) == [COUNTED]
    assert _readings([("STATE FARM DES:DRP PAYMENT ID:1", 0.5)]) == [("excluded_pending_review", "insurer_payer")]


# ---------------------------------------------------------------------------------------------------------------------
# R2-OW07 review round 1.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("rows", "bank"), [
    # A personal government benefit an insurance programme pays (employment insurance, parental insurance, disability
    # or family-leave insurance): never revenue (the MCA principle), held as before this batch.
    pytest.param([("GOVERNMENT OF CANADA EMPLOYMENT INSURANCE", 812.0)], "RBC", id="ei"),
    pytest.param([("DIRECT DEPOSIT GOVERNMENT OF CANADA EMPLOYMENT INSURANCE", 812.0)], "RBC", id="ei-direct-deposit"),
    pytest.param([("GOVERNMENT OF QUEBEC ASSURANCE PARENTALE", 812.0)], "RBC", id="parental-insurance"),
    pytest.param([("STATE OF CONTOSO DISABILITY INSURANCE DES:PAYMENT ID:1", 812.0)], None, id="state-disability"),
    pytest.param([("STATE OF CONTOSO PAID FAMILY LEAVE INSURANCE DES:PAYMENT ID:1", 812.0)], None,
                 id="state-family-leave"),
    # A public insurer (a provincial insurance corporation, a county's self-insurance, a state's insurance department or
    # fund): an insurer, held as before this batch, its premium and dividend too.
    pytest.param([("PROVINCE OF CONTOSO INSURANCE CORP DES:PAYMENT ID:1", 812.0)], None, id="provincial-insurer"),
    pytest.param([("COUNTY OF CONTOSO SELF INSURANCE DES:PAYMENT ID:1", 812.0)], None, id="county-self-insurance"),
    pytest.param([("DEPT OF INSURANCE DES:PAYMENT ID:1", 1234.0)], None, id="insurance-department"),
    pytest.param([("DEPT OF INSURANCE DES:PREMIUM ID:1", 1234.0)], None, id="insurance-department-premium"),
    pytest.param([("DEPT OF INSURANCE DES:DIVIDEND ID:1", 812.0)], None, id="insurance-department-dividend"),
    pytest.param([("STATE OF CONTOSO INSURANCE DES:PAYMENT ID:1", 812.0),
                  ("STATE OF CONTOSO INSURANCE DES:PAYMENT ID:2", 900.0)], None, id="state-insurer-repeats"),
    # A government payer's CLAIM word, as the hold read it before this batch.
    pytest.param([("STATE OF CONTOSO CLAIMS DES:PAYMENT ID:1", 812.0)], None, id="state-claims"),
])
def test_a_government_payer_named_by_the_spelled_out_insurer_words_stays_held(rows, bank):
    """R2-OW07 review round 1 (important): arm (b) keeps the hold that held these rows before this batch. A government
    payer is an insurer only by the spelled-out words or CLAIM (never the widened spellings or the brands), and never
    for work, so none of them moves into True, let alone Verified."""
    records = [record for record in _records(rows, holder=NORTHWIND_BAKERY, bank=bank) if record.amount > 0]
    assert [rules_reading(record) for record in records] == [HELD] * len(rows)
    for record in records:
        row = revenue_text(record.normalized_description)
        reading = true_revenue.insurer_payer_reading(record, row, payer_region(row), entry_fields(row))
        assert reading is not None and reading.kind == "named" and reading.for_work is False


@pytest.mark.parametrize(("rows", "expected"), [
    # An insurer's printed truck or vehicle sale is held as the insurer, however it is spelled (a total-loss
    # settlement reads so; held is reviewable), as the spelled-out insurer's already was: R2-OW06's precedence, an
    # insurer-name hold other than IAA's keeps an asset sale held, reads every spelling.
    pytest.param([("SAMPLE INS CO DES:TRUCK SALE ID:1", 4000.0)], HELD, id="ins-truck-sale"),
    pytest.param([("SAFECO DES:VEHICLE SALE ID:1", 4000.0)], HELD, id="brand-vehicle-sale"),
    pytest.param([("SAMPLE INSURANCE CO DES:TRUCK SALE ID:1", 4000.0)], HELD, id="spelled-out-truck-sale"),
    # The control: a non-insurer's truck sale is the asset sale's non_revenue.
    pytest.param([("SAMPLE CO DES:TRUCK SALE ID:1", 4000.0)], ("non_revenue", "asset_sale_proceeds"),
                 id="non-insurer-truck-sale"),
])
def test_an_insurer_s_printed_asset_sale_is_held_as_the_insurer(rows, expected):
    """R2-OW07 review round 1 (minor): the widened insurer reading widens R2-OW06's insurer-name precedence over the
    asset-sale reading (§8.1, §20 record it): a non_revenue asset sale becomes held insurer_named_payer when its payer
    reads as an insurer by any spelling. 0 corpus rows."""
    assert _readings(rows) == [expected]


@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # A person-to-person sender's surname, given name or the rail's own word is no cut insurer, and a brand never reads
    # a person's transfer: the reading on a person-to-person rail is the spelled-out words and CLAIM alone.
    pytest.param([("INTERAC E-TRANSFER FROM SAMPLE MUTUA", 400.0)], {"bank": "RBC"}, ("counted_flagged", "p2p"),
                 id="e-transfer-surname-mutua"),
    pytest.param([("INTERAC E-TRANSFER FROM SAMPLE INS", 400.0)], {"bank": "RBC"}, ("counted_flagged", "p2p"),
                 id="e-transfer-ins"),
    pytest.param([("INTERAC E-TRANSFER FROM SAFECO", 400.0)], {"bank": "RBC"}, ("counted_flagged", "p2p"),
                 id="e-transfer-brand"),
    pytest.param([("VENMO CASHOUT FROM SUBROTO SAMPLE", 350.0)], {}, ("counted_flagged", "p2p"),
                 id="venmo-given-name-subroto"),
    # The spelled-out word still reads on the rail, as before this batch.
    pytest.param([("INTERAC E-TRANSFER FROM SAMPLE INSURANCE", 400.0)], {"bank": "RBC"}, HELD,
                 id="e-transfer-spelled-out-insurer"),
    # SUBRO is a subrogation's word and its cut forms, never the given name SUBROTO.
    pytest.param([("SUBROTO SAMPLE DES:PAYMENT ID:1", 1234.0)], {}, ("counted_flagged", "named_payer_one_off"),
                 id="ach-given-name-subroto"),
    pytest.param([("FABRIKAM SUBROGATION DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="subrogation"),
    pytest.param([("FABRIKAM SUBROG DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="subrogation-cut"),
    # A brand's INS is an insurer word or its cut, never another word's first letters.
    pytest.param([("FARMERS INSTITUTE DES:PAYMENT ID:1", 1234.0)], {}, ("counted_flagged", "named_payer_one_off"),
                 id="farmers-institute"),
    pytest.param([("FARMERS INSTANT CO DES:PAYMENT ID:1", 1234.0)], {}, ("counted_flagged", "named_payer_one_off"),
                 id="farmers-instant"),
    pytest.param([("NATIONAL GENERAL INSTRUMENTS DES:PAYMENT ID:1", 1234.0)], {},
                 ("counted_flagged", "named_payer_one_off"), id="national-general-instruments"),
    pytest.param([("AMERICAN FAMILY INSTITUTE DES:PAYMENT ID:1", 1234.0)], {},
                 ("counted_flagged", "named_payer_one_off"), id="american-family-institute"),
    pytest.param([("FARMERS INSU DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="farmers-insurance-cut"),
    pytest.param([("NATIONAL GENERAL INS DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="national-general-ins"),
    pytest.param([("AMERICAN FAMILY INS DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="american-family-ins"),
    # Travelers' property line only before an insurer word or at the name's end, never a property manager.
    pytest.param([("TRAVELERS PROPERTY MANAGEMENT DES:PAYMENT ID:1", 1234.0)], {},
                 ("counted_flagged", "named_payer_one_off"), id="travelers-property-manager"),
    pytest.param([("TRAVELERS PROP CAS DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="travelers-prop-cas"),
    pytest.param([("TRAVELERS PROPERTY DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="travelers-property-end"),
    # P AND C before an installer's or an inspector's word is no insurer.
    pytest.param([("NORTHWIND P & C INSTALLATIONS DES:PAYMENT ID:1", 1234.0)], {"holder": "FABRIKAM BAKERY LLC"},
                 ("counted_flagged", "named_payer_one_off"), id="p-and-c-installations"),
    # Accepted over-holds (§8.1, held and reviewable): an ACH payer whose name ends in MUTUA (a 16-letter field's cut of
    # an insurer's MUTUAL reads the same), National General's 16-letter cut, P AND C at a name's end or before CO, and
    # the INS token before another word.
    pytest.param([("SAMPLE MUTUA DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="over-hold-ach-mutua"),
    pytest.param([("NATIONAL GENERAL DES:PAYMENT ID:1", 1234.0)], {}, HELD, id="over-hold-national-general-cut"),
    pytest.param([("NORTHWIND P & C DES:PAYMENT ID:1", 1234.0)], {"holder": "FABRIKAM BAKERY LLC"}, HELD,
                 id="over-hold-p-and-c-end"),
    pytest.param([("P & C CO DES:PAYMENT ID:1", 1234.0)], {"holder": "FABRIKAM BAKERY LLC"}, HELD,
                 id="over-hold-p-and-c-co"),
    pytest.param([("NORTHWIND HOME INS INSPECTIONS DES:PAYMENT ID:1", 1234.0)], {"holder": "FABRIKAM BAKERY LLC"},
                 HELD, id="over-hold-ins-token"),
])
def test_the_insurer_spellings_and_brands_never_read_their_namesakes(rows, statement, expected):
    """R2-OW07 review round 1 (minor): the namesakes the brief's patterns read keep their reading before this batch;
    the over-holds the patterns cannot tell from an insurer stay held, as §8.1 lists them."""
    assert _readings(rows, **statement) == [expected]


@pytest.mark.parametrize(("text", "expected"), [
    # T21: a payer that prints no insurer word of its own beside the agency holder's cut name.
    pytest.param("CREF NORTHWIND FABRIKAM INSURANCE AGEN CUSTOMER ID 1234", ("counted_flagged", "named_payer_unlabelled"),
                 id="no-insurer-word"),
    # An insurer word glued to the payer's name, which no insurer reading reads.
    pytest.param("CREF SAMPLEINSURANCE FABRIKAM INSURANCE AGEN CUSTOMER ID 1234",
                 ("counted_flagged", "named_payer_unlabelled"), id="glued-insurer-word"),
])
def test_a_row_the_holder_strip_un_reads_is_counted_where_no_later_hold_names_it(text, expected):
    """R2-OW07 review round 1 (minor): the holder strip never lets the holder's own INSURANCE word make its payer an
    insurer, so a row whose only insurer reading was the holder's name is counted where no later hold of §8.10 names
    it (the holder test does not read the name in the middle of Truist's region; §20 records it). Held before this
    batch; R2-OW08's re-measure reads them."""
    assert _readings([(text, 812.0)], holder=TRUIST_AGENCY, bank="Truist") == [expected]


def test_a_row_the_holder_strip_un_reads_takes_the_later_hold_that_names_it():
    """The control: where the holder test reads the holder's name (at the region's end), the row is held holder_name,
    never counted."""
    assert _readings([("NORTHWIND LLC FABRIKAM INSURANCE AGENCY", 812.0)], holder=AGENCY) == [
        ("excluded_pending_review", "holder_name")
    ]


# ---------------------------------------------------------------------------------------------------------------------
# The reader, arm by arm.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("text", "statement", "expected"), [
    # (a) An HCCLAIMPMT entry: never an insurer's reading.
    ("SAMPLE MUTUAL INSURANCE DES:HCCLAIMPMT ID:1", {}, None),
    # (b) A listed insurer's credit (audit round 3, R3-B13: R3-11, read before the government arm): the registry's
    # entity, whatever government-shaped name it prints; a premium financier none. (c) below.
    ("ALLSTATE COUNTY DES:CLAIM PMT ID:1", {}, _expected("Allstate", "registry", True)),
    # (c) A government payer: never by the widened spellings or the brands; by the spelled-out words or CLAIM (the
    # reading before this batch), never for work (R2-OW07 review round 1).
    ("STATE OF OHIO INS FUND DES:PAYMENT ID:1", {}, None),
    ("STATE OF CONTOSO INS DES:PAYMENT ID:1", {"holder": NORTHWIND_BAKERY}, None),
    ("STATE OF CONTOSO FARMERS INS DES:PAYMENT ID:1", {"holder": NORTHWIND_BAKERY}, None),
    ("GOVERNMENT OF CANADA EMPLOYMENT INSURANCE", {"holder": NORTHWIND_BAKERY, "bank": "RBC"},
     _expected("GOVERNMENT OF CANADA EMPLOYMENT", "named", False)),
    ("STATE OF CONTOSO DISABILITY INSURANCE DES:PAYMENT ID:1", {"holder": NORTHWIND_BAKERY},
     _expected("STATE OF CONTOSO DISABILITY", "named", False)),
    ("DEPT OF INSURANCE DES:PREMIUM ID:1", {"holder": NORTHWIND_BAKERY}, _expected("DEPT OF INSURANCE", "named", False)),
    ("STATE OF CONTOSO CLAIMS DES:PAYMENT ID:1", {"holder": NORTHWIND_BAKERY},
     _expected("STATE OF CONTOSO CLAIMS", "named", False)),
    # (b) A listed insurer's credit: the registry's entity; a premium financier none.
    ("GEICO INSURANCE EFT", {}, _expected("GEICO", "registry", True)),
    ("STATE FARM DES:DRP PAYMENT ID:1", {}, _expected("State Farm", "registry", True)),
    ("IPFS 888 DES:FUNDING ID:1", {}, None),
    ("FIRST INSURANCE FUNDING DES:PAYMENT ID:1", {}, None),
    # (d) The holder's own insurance word, read away.
    ("CREF NORTHWIND FABRIKAM INSURANCE AGEN CUSTOMER ID 1234", {"holder": TRUIST_AGENCY, "bank": "Truist"}, None),
    # (e) A title insurer (never for work); a title firm with no insurer word is none.
    ("WIRE TYPE:WIRE IN ORIG:CONTOSO TITLE INSURANCE CO ID:1", {},
     _expected("CONTOSO TITLE INSURANCE CO", "title", False)),
    ("WIRE TYPE:WIRE IN ORIG:FABRIKAM TITLE INS CO ID:1", {}, _expected("FABRIKAM TITLE INS CO", "title", False)),
    ("WIRE TYPE:WIRE IN ORIG:CONTOSO TITLE AGENCY LLC ID:1", {}, None),
    # (f) A premium-finance wording.
    ("SAMPLE INSURANCE PREMIUM FINANCE DES:PAYMENT ID:1", {}, None),
    # (g) A healthcare payer: only by the spelled words.
    ("AETNA LIFE INS DES:AETNA PREM ID:1", {}, None),
    ("AETNA LIFE INSURANCE CO DES:PAYMENT ID:1", {}, _expected("AETNA LIFE INSURANCE CO", "named", True)),
    # (g2) A §15 deferred payer: only by the spelled words or CLAIM.
    ("MISC PAYMENT SUN LIFE SUNLIFE MED ASO", {}, None),
    ("SUN LIFE INS CO DES:PAYMENT ID:1", {}, None),
    ("SUN LIFE ASSURANCE DES:PAYMENT ID:1", {}, _expected("SUN LIFE ASSURANCE", "named", True)),
    ("HEALTH DENTAL CLAIM MANULIFE", {}, _expected("HEALTH DENTAL CLAIM MANULIFE", "named", True)),
    # (h) A brand, keyed by its entity.
    ("SAFECO DES:PAYMENT ID:1", {}, _expected("Safeco", "brand", True)),
    ("TRAVELERS INDEMN DES:PAYMENT ID:1", {}, _expected("Travelers", "brand", True)),
    ("FARMERS INS DES:PAYMENT ID:1", {}, _expected("Farmers", "brand", True)),
    # (i) An insurer word, a spelling or CLAIM, keyed by the payer key.
    ("SAMPLE INS CO DES:PAYMENT ID:1", {}, _expected("SAMPLE INS CO", "named", True)),
    ("FABRIKAM CLAIMS SERVICES DES:PAYMENT ID:1", {}, _expected("FABRIKAM CLAIMS SERVICES", "named", True)),
    ("NORTHWIND SUBRO RECOVERY DES:PAYMENT ID:1", {}, _expected("NORTHWIND SUBRO RECOVERY", "named", True)),
    # On a person-to-person rail only the spelled-out words and CLAIM read (R2-OW07 review round 1): a sender's
    # surname or the rail's own word is no cut insurer, and a brand never reads a person's transfer.
    ("INTERAC E-TRANSFER FROM SAMPLE INSURANCE", {"bank": "RBC"}, _expected("SAMPLE INSURANCE", "named", True)),
    ("INTERAC E-TRANSFER FROM SAMPLE MUTUA", {"bank": "RBC"}, None),
    ("INTERAC E-TRANSFER FROM SAMPLE INS", {"bank": "RBC"}, None),
    ("INTERAC E-TRANSFER FROM SAFECO", {"bank": "RBC"}, None),
    ("VENMO CASHOUT FROM SUBROTO SAMPLE", {}, None),
    # No reading.
    ("NORTHWIND SUPPLY DES:PAYMENT ID:1", {}, None),
    ("ASSURED STAFFING LLC DES:PAYMENT ID:1", {}, None),
])
def test_the_insurer_reading_arm_by_arm(text, statement, expected):
    assert _reader(text, **statement) == expected


def test_a_registry_reading_is_never_the_insurer_name_hold():
    """Arm 2 holds every reading but the registry's: a listed insurer's credit is the insurance rule's."""
    assert _reader("GEICO INSURANCE EFT")[1] == "registry"
    assert _readings([("GEICO INSURANCE EFT", 1234.0)]) == [("non_revenue", None)]


def test_a_claimed_row_is_never_the_insurer_name_hold(monkeypatch):
    """The insurer-name hold skips a row the registry, a payout entity or a factoring payee claimed (§8.1)."""
    monkeypatch.setattr(true_revenue, "_claimed", lambda record, text: True)
    assert _readings([("SAMPLE INS CO DES:PAYMENT ID:1", 1234.0)]) != [HELD]


def test_the_insurer_reading_is_frozen():
    reading = true_revenue.InsurerReading("Safeco", "brand", True)
    with pytest.raises(AttributeError):
        reading.key = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------------------------------------------------
# The spellings and the brand table.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "UNIVERSAL P AND C", "STATE FARM MUTUA", "SAMPLE RISK INS ASS", "SAMPLE INS CO", "SAMPLE P & C INS",
    "NORTHWIND P AND C COMPANY", "SAMPLE ASSURANCES", "SAMPLE ASSURANT", "SAMPLE ASSUREURS", "SAMPLE ASSUR",
    "SAMPLE CASUALT", "SAMPLE INDEMN", "SAMPLE LOSS PMT", "SAMPLE LOSS DRAFT", "SAMPLE SUBRO",
    # R2-OW07 review round 1: a subrogation's cut forms, and P AND C before an insurer word or its cut.
    "SAMPLE SUBROGATION", "SAMPLE SUBROG", "SAMPLE P & C INSURANCE", "SAMPLE P AND C INSU",
    # Audit round 3, R3-B13 (R3-11): a Texas county mutual's 16-character cut.
    "SAMPLE COUNTY MUT",
])
def test_the_insurer_spellings_read(text):
    assert true_revenue._INSURER_SPELLINGS.search(text)


@pytest.mark.parametrize("text", [
    "ASSURED STAFFING LLC", "P AND C FOODS", "SAMPLE ASSURE", "SAMPLE INSTALLATIONS", "SAMPLE CLM", "SAMPLE CLMS",
    "SAMPLE CLMEFT", "SAMPLE MUTUAL", "SAMPLE ASSURANCE", "SAMPLE LOSS PREVENTION",
    # R2-OW07 review round 1: the given name SUBROTO is no subrogation, nor INSTALLATIONS an insurer word after P & C.
    "SUBROTO SAMPLE", "SAMPLE SUBROTO", "NORTHWIND P & C INSTALLATIONS", "NORTHWIND P AND C INSPECTIONS",
    # Audit round 3, R3-B13 (R3-11): MUT reads only after COUNTY, as a whole word.
    "SAMPLE MUTTON FARM",
])
def test_the_insurer_spellings_never_read(text):
    assert true_revenue._INSURER_SPELLINGS.search(text) is None


def test_the_spelled_out_insurer_words_are_unchanged():
    """_INSURER_NAME stays byte-identical (the contract's docs test pins its words); the spellings are read beside it."""
    assert true_revenue._INSURER_NAME.pattern == (
        r"(?<![A-Z])(?:INSUR\w*|ASSURANCE\b|MUTUAL\b|CASUALTY\b|INDEMNITY\b|UNDERWRIT\w*)"
    )


@pytest.mark.parametrize(("text", "entity"), [
    ("FARMERS INSURANCE", "Farmers"), ("FARMERS FARMERS IN", "Farmers"), ("FARMERS NEW WORLD LIFE", "Farmers"),
    ("AMERICAN FAMILY", "American Family"), ("AMERICAN FAMILY MUTUAL", "American Family"), ("AMFAM", "American Family"),
    ("SAFECO", "Safeco"), ("HISCOX", "Hiscox"), ("AFLAC", "Aflac"), ("GAINSCO", "Gainsco"), ("AMTRUST", "AmTrust"),
    ("NATIONAL GENERAL", "National General"), ("NATIONAL GENERAL INS", "National General"),
    ("TRAVELERS INDEMN", "Travelers"), ("TRAVELERSPICOMM", "Travelers"), ("TRAVELERS CASUALTY", "Travelers"),
    ("TRAVELERS COMML", "Travelers"),
    # R2-OW07 review round 1: the insurer word's cut forms, and Travelers' property line before an insurer word or at
    # the name's end.
    ("FARMERS INSU", "Farmers"), ("FARMERS INSURAN", "Farmers"), ("AMERICAN FAMILY INSUR", "American Family"),
    ("NATIONAL GENERAL INSURANCE", "National General"), ("TRAVELERS PROPERTY CASUALTY", "Travelers"),
    ("TRAVELERS PROP CAS", "Travelers"), ("TRAVELERS PROP INS", "Travelers"), ("TRAVELERS PROPERTY", "Travelers"),
    ("TRAVELERS PROP 1234", "Travelers"),
    # Audit round 3, R3-B16 (R3-03): American Income Life, as its agents' commission credits print it.
    ("AM INCOME LIFE", "American Income Life"), ("AMERICAN INCOME LIFE", "American Income Life"),
    ("AMERICAN INCOME LIFE INS CO", "American Income Life"),
])
def test_the_brand_table_reads_its_carriers(text, entity):
    assert insurer_credit_brand(text) == entity


@pytest.mark.parametrize("text", [
    "AMERICAN FAMILY CARE", "AMERICAN FAMILY DENTAL", "FARMERS IN BLOOM LLC", "FARMERS EXCHANGE BANK",
    "NATIONAL GENERAL CONTRACTORS", "TRAVELERS CASH", "TRAVELERS PROPANE", "TRAVELERS COMMUNITY", "AMTRUST BANK",
    "AMTRUST TITLE", "SUNLIFE SOLAR LLC", "PROGRESSIVE LEASING", "NATIONWIDE SECUR", "BENEVA BLVD",
    # R2-OW07 review round 1: INS only as an insurer word or its cut, never another word's first letters; Travelers'
    # property line never a property manager.
    "FARMERS INSTITUTE", "FARMERS INSTANT CO", "AMERICAN FAMILY INSTITUTE", "NATIONAL GENERAL INSTRUMENTS",
    "TRAVELERS PROPERTY MANAGEMENT", "TRAVELERS PROPERTY MGMT", "TRAVELERS PROP SERVICES",
    # Audit round 3, R3-B16 (R3-03): American Income Life's namesakes, and its entry spelling (the brand reads the payer
    # region only).
    "AMERICAN INCOME FUND", "AM INCOME LIFESTYLE LLC", "INCOME LIFE COACHING", "AIL INS",
])
def test_no_brand_pattern_reads_another_business(text):
    assert insurer_credit_brand(text) is None


def test_a_brand_the_insurance_registry_names_is_keyed_by_the_registry_s_entity():
    """A carrier is one key however it prints: a brand that reads one of INSURANCE_PROVIDER_ALIASES' aliases carries
    that entity's name, spelled identically ('Travelers')."""
    for entity, aliases in registry.INSURANCE_PROVIDER_ALIASES.items():
        for alias in aliases:
            brand = insurer_credit_brand(alias)
            assert brand is None or brand == entity, (alias, brand, entity)
    assert "Travelers" in registry.INSURANCE_PROVIDER_ALIASES and "Travelers" in registry.INSURER_CREDIT_BRANDS
    assert insurer_credit_brand("TRAVELERS INDEMNITY") == "Travelers"


@pytest.mark.parametrize("carrier", [
    "SUN LIFE", "SUNLIFE", "MANULIFE", "CANADA LIFE", "GREAT WEST LIFE", "EQUITABLE LIFE", "DESJARDINS INSURANCE",
    "GREEN SHIELD", "BENEVA", "SSQ", "LA CAPITALE", "BERKSHIRE HATHAWAY", "PROGRESSIVE", "NATIONWIDE",
])
def test_no_brand_is_a_section_15_deferred_or_left_out_carrier(carrier):
    assert insurer_credit_brand(carrier) is None
    for entity in registry.INSURER_CREDIT_BRANDS:
        assert true_revenue._SECTION_15_DEFERRED_PAYERS.search(entity.upper()) is None, entity


def test_the_brand_table_is_credit_only():
    """No module but the true-revenue pass reads INSURER_CREDIT_BRANDS: classify_transaction's insurance rule, the
    debit readers, the lender and flag tables and the records never carry it."""
    readers = sorted(
        path.relative_to(ROOT).as_posix()
        for folder in ("analysis", "webapp", "tools", "ocr")
        if (ROOT / folder).is_dir()
        for path in (ROOT / folder).rglob("*.py")
        if "INSURER_CREDIT_BRANDS" in path.read_text(encoding="utf-8", errors="ignore")
    )
    assert readers == ["analysis/classification_registry.py", "analysis/true_revenue.py"]
    assert not set(registry.INSURER_CREDIT_BRANDS) & {
        name for name in registry.INSURANCE_PROVIDER_ALIASES if name != "Travelers"
    }


def test_each_brand_pattern_compiles_as_a_whole_name():
    for entity, patterns in registry.INSURER_CREDIT_BRANDS.items():
        assert patterns, entity
        for pattern in patterns:
            re.compile(pattern)
    assert [entity for entity, _ in true_revenue._INSURER_CREDIT_BRANDS] == list(registry.INSURER_CREDIT_BRANDS)
    for _, patterns in true_revenue._INSURER_CREDIT_BRANDS:
        for pattern in patterns:
            assert pattern.pattern.startswith("(?<![A-Z])(?:") and pattern.pattern.endswith(")(?![A-Z])")


# ---------------------------------------------------------------------------------------------------------------------
# Owner ruling 2026-10-02 (the underwriter's Q2, "True revenue", option 2), R2-OW08: insurers paid for the business's
# work are counted and flagged (insurer_paid_for_services), never verified and never a Q5 or Q6 repeat.
# ---------------------------------------------------------------------------------------------------------------------

REPAIR_COLLISION = "CONTOSO COLLISION LLC"
STAFFING_AGENCY = "CONTOSO STAFFING AGENCY LLC"
INS_AGENCY = "FABRIKAM INS AGENCY LLC"
GROUND_WORDS = {
    "holder_trade:repair shop": "the holder's name reads a repair shop",
    "holder_trade:insurance agency": "the holder's name reads an insurance agency",
    "holder_trade:clinic": "the holder's name reads a clinic",
    "holder_trade:pharmacy": "the holder's name reads a pharmacy",
    "service_form": "the row prints the form an insurer pays a repair shop, an agency or a provider with",
    "same_insurer_3_in_31_days": "the same insurer pays the business three or more times within 31 days",
    "insurer_service_statement": "another insurer pays the business three or more times within 31 days in the statement",
}


def _dated(rows, *, holder: str = BAKERY, bank: str | None = None, zelle_true_revenue: bool = False):
    """A statement of (text, amount, 'MM-DD') rows in 2054, every credit's record (audit round 3, R3-B13: under the
    Zelle setting `zelle_true_revenue`, No by default)."""
    return [record for record in classify_statement_transactions(Statement(account_name=holder, bank=bank,
            transactions=[Transaction(date=f"2054-{day}", description=text, amount=amount,
                                      direction="credit" if amount > 0 else "debit")
                          for text, amount, day in rows]), zelle_true_revenue=zelle_true_revenue)
            if record.amount > 0]


def _t4(days=("03-02", "03-12", "03-24"), amounts=(812.0, 1290.5, 640.25)):
    return [(f"NORTHWIND MUTUAL INSURANCE CO DES:PAYMENT ID:{n}", amount, day)
            for n, (amount, day) in enumerate(zip(amounts, days), start=1)]


#: The brief's COUNTED cases: (rows, statement, the ground of each released row).
COUNTED_CASES = [
    # T1: a repair holder (today held insurer_named_payer); its CLAIM is the claim paid for the repair.
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:CLAIM PMT ID:1 INDN:CONTOSO COLLISION LLC CO ID:1 CCD", 4250.0,
                   "03-02")], {"holder": REPAIR_COLLISION}, ["holder_trade:repair shop"], id="T1"),
    # T2: a registry insurer's DRP at a bakery (today held insurer_payer): the service form.
    pytest.param([("STATE FARM DES:DRP PAYMENT ID:1", 1234.0, "03-02")], {}, ["service_form"], id="T2"),
    # T3: an agency's agent EFT from a brand (today counted named_payer_one_off; R2-OW07 held it).
    pytest.param([("AFLAC DES:AGENTS EFT ID:A1 INDN:FABRIKAM INSURANCE AGENCY CO ID:1 PPD", 2210.55, "03-02")],
                 {"holder": AGENCY}, ["holder_trade:insurance agency"], id="T3"),
    # T3b: a carrier's PI COMM at the same agency (today counted named_payer_unlabelled).
    pytest.param([("TRAVELERSPICOMM 1234 NORTHWIND", 812.4, "03-02")], {"holder": AGENCY},
                 ["holder_trade:insurance agency"], id="T3b"),
    # T4: the same insurer three times within 31 days, no trade (today all held; without _never_q5_or_q6 they would
    # verify as repeats).
    pytest.param(_t4(), {}, ["same_insurer_3_in_31_days"] * 3, id="T4"),
    # T6: a §15 deferred carrier today's INSURANCE word reads, at a clinic (today held insurer_named_payer).
    pytest.param([("INSURANCE MANULIFE", 95.2, "03-02")], {"holder": CLINIC, "bank": "RBC"}, ["holder_trade:clinic"],
                 id="T6"),
    # T10b: a premium with a commission, at an agency (today held): the commission form overrides the premium word.
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:PREM COMM ID:1", 640.0, "03-02")], {"holder": AGENCY},
                 ["holder_trade:insurance agency"], id="T10b"),
    # T18: a bill to the carrier (a one-off premium at another amount) does not hold a for-work credit (the bill
    # clause's insurer is no insurer here; today held insurer_payer).
    pytest.param([("STATE FARM DES:DRP PAYMENT ID:1", 3000.0, "03-02"), ("STATE FARM DES:AUTOPAY ID:9", -412.18, "03-03")],
                 {"holder": REPAIR_SHOP}, ["holder_trade:repair shop"], id="T18"),
    # T23: Symitar's cut State Farm form three times, no holder trade (today non_revenue).
    pytest.param([("ACH DEPOSIT STATE FARM MUTUA PAYMENTS CONTOSO AUTO REBODY", 4100.0, "03-02"),
                  ("ACH DEPOSIT STATE FARM MUTUA PAYMENTS CONTOSO AUTO REBODY", 3800.0, "03-09"),
                  ("ACH DEPOSIT STATE FARM MUTUA PAYMENTS CONTOSO AUTO REBODY", 5120.0, "03-16")], {},
                 ["same_insurer_3_in_31_days"] * 3, id="T23"),
    # T25b: a deferred carrier's CLAIM three times at a clinic (today all held insurer_named_payer).
    pytest.param([("HEALTH DENTAL CLAIM MANULIFE", 67.5, "03-02"), ("HEALTH DENTAL CLAIM MANULIFE", 135.0, "03-09"),
                  ("HEALTH DENTAL CLAIM MANULIFE", 95.2, "03-16")], {"holder": CLINIC, "bank": "RBC"},
                 ["holder_trade:clinic"] * 3, id="T25b"),
    # T26c: a loose AGENCY word corroborated by a second eligible insurer credit (today both held).
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:CLAIM PMT ID:1", 1234.0, "03-02"),
                  ("NORTHWIND CASUALTY CO DES:PAYMENT ID:2", 640.0, "03-03")], {"holder": STAFFING_AGENCY},
                 ["holder_trade:insurance agency"] * 2, id="T26c"),
    # T29: the window's edge inside, 03-01 to 03-31 (a 30-day span).
    pytest.param(_t4(days=("03-01", "03-15", "03-31")), {}, ["same_insurer_3_in_31_days"] * 3, id="T29"),
    # The sliding span reaches across a calendar month's edge (03-20 to 04-15).
    pytest.param(_t4(days=("03-20", "04-01", "04-15")), {}, ["same_insurer_3_in_31_days"] * 3,
                 id="span-across-a-month-edge"),
    # T30: one carrier spelled two ways is one key (Travelers): the registry's spelling (today non_revenue) and the
    # brand's cut INDEMN (today verified named_payer_repeats; R2-OW07 held them).
    pytest.param([("TRAVELERS INSURANCE DES:PAYMENT ID:1", 812.0, "03-02"),
                  ("TRAVELERS INDEMN DES:PAYMENT ID:2", 1290.5, "03-12"),
                  ("TRAVELERS INDEMN DES:PAYMENT ID:3", 640.25, "03-24")], {}, ["same_insurer_3_in_31_days"] * 3,
                 id="T30"),
    # T34: a brand's agent EFT at an agency whose name prints INS (today counted named_payer_one_off).
    pytest.param([("AMERICAN FAMILY DES:AGENTS EFT ID:A1 INDN:FABRIKAM INS AGENCY CO ID:1 PPD", 3100.0, "03-02")],
                 {"holder": INS_AGENCY}, ["holder_trade:insurance agency"], id="T34"),
    # The service forms one by one at a bakery (a commission, a contingency, a vendor payment, a repair).
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:COMMISSION ID:1", 640.0, "03-02")], {}, ["service_form"],
                 id="form-commission"),
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:CONTINGENCY ID:1", 640.0, "03-02")], {}, ["service_form"],
                 id="form-contingency"),
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:VENDOR PMT ID:1", 640.0, "03-02")], {}, ["service_form"],
                 id="form-vendor-pmt"),
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:REPAIR ID:1", 640.0, "03-02")], {}, ["service_form"],
                 id="form-repair"),
    # The classifier's own customer-payment form printed before the payer ('MTH AGTEFT <carrier>').
    pytest.param([("MTH AGTEFT SAMPLE INS", 640.0, "03-02")], {}, ["service_form"], id="form-before-the-payer"),
    # A pharmacy's trade.
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:CLAIM PMT ID:1", 640.0, "03-02")],
                 {"holder": "CONTOSO PHARMACY LLC"}, ["holder_trade:pharmacy"], id="pharmacy"),
]


@pytest.mark.parametrize(("rows", "statement", "grounds"), COUNTED_CASES)
def test_an_insurer_paid_for_the_business_s_work_is_counted_never_verified(rows, statement, grounds):
    records = _dated(rows, **statement)
    assert [rules_reading(record) for record in records] == [COUNTED] * len(grounds)
    for record, ground in zip(records, grounds):
        assert record.revenue_classification == "unverified_deposit"
        assert record.revenue_match_method == METHOD
        assert record.revenue_matched_rule == "insurer_paid_for_services"
        assert record.revenue_confidence_score == 0.60
        assert METHOD in record.revenue_context_signals
        assert record.revenue_review_required is False and record.contributes_to_true_revenue
        assert not record.contributes_to_verified_revenue
        assert f"({GROUND_WORDS[ground]})" in record.revenue_reason
        assert ("counted and flagged, never verified (the owner's ruling on the underwriter's Q2)"
                in record.revenue_reason)


def test_the_statement_arm_switch_on_counts_another_insurer_s_one_off(monkeypatch):
    """T5-ON: with the owner's switch on, T4's frequent insurer makes a fourth insurer's one-off claim count
    ('insurer_service_statement'); T5: off (the default, the literal reading), the one-off stays held."""
    rows = [*_t4(), ("FABRIKAM CASUALTY CO DES:CLAIM PMT ID:9", 455.0, "03-25")]
    assert true_revenue.INSURER_FOR_WORK_STATEMENT_ARM is False
    assert [rules_reading(record) for record in _dated(rows)] == [COUNTED, COUNTED, COUNTED, HELD]
    monkeypatch.setattr(true_revenue, "INSURER_FOR_WORK_STATEMENT_ARM", True)
    records = _dated(rows)
    assert [rules_reading(record) for record in records] == [COUNTED] * 4
    assert f"({GROUND_WORDS['insurer_service_statement']})" in records[3].revenue_reason
    assert f"({GROUND_WORDS['same_insurer_3_in_31_days']})" in records[0].revenue_reason


@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # T4b: two only; T4c: 03-01, 03-20, 04-15 (no three within 31 days); T29b: 03-01, 03-15, 04-01 (a 32-day span:
    # the inclusive 31-day span ends 03-31).
    pytest.param(_t4()[:2], {}, [HELD, HELD], id="T4b"),
    pytest.param(_t4(days=("03-01", "03-20", "04-15")), {}, [HELD] * 3, id="T4c"),
    pytest.param(_t4(days=("03-01", "03-15", "04-01")), {}, [HELD] * 3, id="T29b"),
    # T7: a one-off claim at a bakery stays held ('a one-off claim paid to a business on its own policy stays out').
    pytest.param([("FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT ID:1", 1234.0, "03-02")], {}, [HELD], id="T7"),
    # T8: a listed insurer once at a bakery stays the insurance rule's non_revenue.
    pytest.param([("GEICO INSURANCE EFT", 1234.0, "03-02")], {}, [("non_revenue", None)], id="T8"),
    # T9, T9b, T9c: R2-OW07's holds (one or two credits, no trade, no form).
    pytest.param([("SAMPLE INS CO DES:PAYMENT ID:1", 1234.0, "03-02")], {}, [HELD], id="T9"),
    pytest.param([("SAMPLE INS CO DES:PAYMENT ID:1", 1234.0, "03-02"), ("SAMPLE INS CO DES:PAYMENT ID:2", 1290.5, "03-03")],
                 {}, [HELD, HELD], id="T9b"),
    pytest.param([("FARMERS INS DES:PAYMENT ID:1", 1234.0, "03-02")], {}, [HELD], id="T9c"),
    # T10: a premium at an agency: the premium word refuses every ground.
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:INS PREM ID:1", 640.0, "03-02")], {"holder": AGENCY}, [HELD],
                 id="T10"),
    # T11: an insurer's refund at a repair shop: non_revenue (the reversal rule).
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:REFUND ID:1", 1234.0, "03-02")], {"holder": REPAIR_SHOP},
                 [("non_revenue", None)], id="T11"),
    # T12: BCBS's HCCLAIMPMT keeps verifying; T13: a healthcare payer keeps Q6c; T13b: its premium stays refused.
    pytest.param([("BCBS OF CONTOSO DES:HCCLAIMPMT ID:1", 1234.0, "03-02")], {"holder": "CONTOSO DENTAL PLLC"},
                 [VERIFIED], id="T12"),
    pytest.param([("UNITED HEALTHCARE DES:PAYMENT ID:1", 1234.0, "03-02")], {}, [VERIFIED], id="T13"),
    pytest.param([("AETNA LIFE INS DES:AETNA PREM ID:1", 1234.0, "03-02")], {},
                 [("counted_flagged", "named_payer_purpose_refused")], id="T13b"),
    # T14: premium finance at an agency stays non_revenue.
    pytest.param([("IPFS 888 DES:FUNDING ID:1", 1234.0, "03-02")], {"holder": AGENCY}, [("non_revenue", None)],
                 id="T14"),
    # T15: title-insurer wires at a repair shop: a title insurer is never for work.
    pytest.param([("WIRE TYPE:WIRE IN ORIG:CONTOSO TITLE INSURANCE CO ID:1", 5000.0, "03-02"),
                  ("WIRE TYPE:WIRE IN ORIG:FABRIKAM TITLE INS CO ID:2", 4000.0, "03-03"),
                  ("WIRE TYPE:WIRE IN ORIG:NORTHWIND TITLE INSURANCE AGENCY ID:3", 3000.0, "03-04")],
                 {"holder": REPAIR_SHOP}, [HELD] * 3, id="T15"),
    # T16: released at a repair shop, then the pay hold names it (the release passes only the insurer-name hold).
    pytest.param([("FARMERS INS DES:PAYROLL ID:1", 1234.0, "03-02")], {"holder": REPAIR_SHOP},
                 [("excluded_pending_review", "payroll_or_salary")], id="T16"),
    # T18b: a debit for the credit's own amount holds it: a released row is unclaimed (the counter-debit hold reads it).
    pytest.param([("STATE FARM DES:DRP PAYMENT ID:1", 3000.0, "03-02"), ("STATE FARM DES:AUTOPAY ID:9", -3000.0, "03-03")],
                 {"holder": REPAIR_SHOP}, [("excluded_pending_review", "payer_also_debited")], id="T18b"),
    # T19: a government insurance programme's credits are Q12's non_revenue before pass 7 (R2-OW01), never for work.
    pytest.param([("WORKFORCE SAFETY AND INSURANCE DES:PAYMENT ID:1", 812.0, "03-02"),
                  ("WORKFORCE SAFETY AND INSURANCE DES:PAYMENT ID:2", 900.0, "03-09"),
                  ("WORKFORCE SAFETY AND INSURANCE DES:PAYMENT ID:3", 700.0, "03-16")], {},
                 [("non_revenue", "government_no_purpose")] * 3, id="T19"),
    # T20: Progressive Leasing is a lease-to-own financier (Q8), never an insurer.
    pytest.param([("PROGRESSIVE LEASING DES:MERCH PMT ID:1", 1234.0, "03-02")], {},
                 [("counted_flagged", "customer_financing_payout")], id="T20"),
    # T23b: the cut State Farm form once: non_revenue.
    pytest.param([("ACH DEPOSIT STATE FARM MUTUA PAYMENTS CONTOSO AUTO REBODY", 4100.0, "03-02")], {},
                 [("non_revenue", None)], id="T23b"),
    # T24: the DRP row under the $1 floor keeps insurer_payer.
    pytest.param([("STATE FARM DES:DRP PAYMENT ID:1", 0.5, "03-02")], {}, [("excluded_pending_review", "insurer_payer")],
                 id="T24"),
    # T25, T25c: a §15 deferred carrier's health-plan rows with no insurer word keep their tier.
    pytest.param([("MISC PAYMENT SUN LIFE SUNLIFE MED ASO", 76.5, "03-02")], {"holder": CLINIC, "bank": "RBC"},
                 [("counted_flagged", "named_payer_purpose_refused")], id="T25"),
    pytest.param([("MISC PAYMENT SAMPLE ASO SUNLIFE MED ASO", 76.5, "03-02"),
                  ("MISC PAYMENT SAMPLE ASO SUNLIFE MED ASO", 95.2, "03-03")], {"holder": CLINIC},
                 [VERIFIED, VERIFIED], id="T25c"),
    # T26: one claim at a staffing agency (the loose AGENCY word needs a second eligible credit); T26b: VISION, a loose
    # clinic word, in a graphics firm's name, once.
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:CLAIM PMT ID:1", 1234.0, "03-02")], {"holder": STAFFING_AGENCY},
                 [HELD], id="T26"),
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:CLAIM PMT ID:1", 1234.0, "03-02")],
                 {"holder": "CONTOSO VISION GRAPHICS LLC"}, [HELD], id="T26b"),
    # T27, T27b: ASSURED and P AND C FOODS are no insurers (verified repeats as today).
    pytest.param([("ASSURED STAFFING LLC DES:PAYMENT ID:1", 1234.0, "03-02"),
                  ("ASSURED STAFFING LLC DES:PAYMENT ID:2", 1290.5, "03-03")], {}, [VERIFIED, VERIFIED], id="T27"),
    pytest.param([("P AND C FOODS DES:PAYMENT ID:1", 1234.0, "03-02"), ("P AND C FOODS DES:PAYMENT ID:2", 1290.5, "03-03")],
                 {}, [VERIFIED, VERIFIED], id="T27b"),
    # T28, T28b: the brands' namesakes stay one-off payers.
    pytest.param([("AMERICAN FAMILY CARE DES:PAYMENT ID:1", 1234.0, "03-02")], {},
                 [("counted_flagged", "named_payer_one_off")], id="T28"),
    pytest.param([("NATIONAL GENERAL CONTRACTORS DES:PAYMENT ID:1", 1234.0, "03-02")], {},
                 [("counted_flagged", "named_payer_one_off")], id="T28b"),
    # T32: a wire's REF field ('REF COMM BANK NYC', the sending bank) is no service form: the service form reads the
    # payer and the purpose words, never a wire's REF, and the classifier's customer-payment wording, which does read
    # REF (Chase's book transfer prints its purpose there, R3-58), never reads a bare COMM.
    pytest.param([("WIRE TYPE:WIRE IN ORIG:SAMPLE MUTUAL INSURANCE CO REF COMM BANK NYC ID:1", 5000.0, "03-02")], {},
                 [HELD], id="T32"),
    # T36: a disability insurer three times within a month: a personal benefit's word refuses every ground.
    pytest.param([("SAMPLE MUTUAL INSURANCE DES:DISABILITY ID:1", 812.0, "03-02"),
                  ("SAMPLE MUTUAL INSURANCE DES:DISABILITY ID:2", 812.0, "03-09"),
                  ("SAMPLE MUTUAL INSURANCE DES:DISABILITY ID:3", 812.0, "03-16")], {}, [HELD] * 3, id="T36"),
    # The other not-for-work words refuse every ground too, at an agency (a dividend, a cancellation, a pension).
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:DIVIDEND ID:1", 640.0, "03-02")], {"holder": AGENCY}, [HELD],
                 id="dividend-at-an-agency"),
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:UNEARNED ID:1", 640.0, "03-02")], {"holder": AGENCY},
                 [HELD], id="unearned-at-an-agency"),
    # A cancellation is the reversal rule's non_revenue first (non-revenue rules run first), never released.
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:CANCELLATION ID:1", 640.0, "03-02")], {"holder": AGENCY},
                 [("non_revenue", None)], id="cancellation-at-an-agency"),
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:PENSION ID:1", 640.0, "03-02")], {"holder": AGENCY}, [HELD],
                 id="pension-at-an-agency"),
    # A released row keeps every later hold but the insurer-name hold: a non-sale word other than CLAIM still holds.
    pytest.param([("SAMPLE MUTUAL INSURANCE CO DES:INVESTMENT ID:1", 640.0, "03-02")], {"holder": AGENCY},
                 [("excluded_pending_review", "non_sale_purpose")], id="released-non-sale-word"),
    # A government payer is never for work, at an agency too.
    pytest.param([("STATE OF CONTOSO INSURANCE DES:PAYMENT ID:1", 812.0, "03-02")], {"holder": AGENCY}, [HELD],
                 id="government-at-an-agency"),
])
def test_the_insurers_no_ground_or_rule_releases_keep_their_reading(rows, statement, expected):
    records = _dated(rows, **statement)
    assert [rules_reading(record) for record in records] == expected
    for record in records:
        if record.revenue_match_method == METHOD:
            assert record.revenue_tier != "verified"


def test_a_registry_insurer_s_credit_that_fails_the_test_stays_non_revenue():
    """Open point 2 of the Q2 card (default): a listed insurer paying a bakery twice a month (no trade, no form, two
    credits) stays the insurance rule's non_revenue, never held."""
    records = _dated([("GEICO INSURANCE EFT", 1234.0, "03-02"), ("GEICO INSURANCE EFT", 1290.5, "03-16")])
    assert [rules_reading(record) for record in records] == [("non_revenue", None)] * 2
    assert {record.revenue_match_method for record in records} == {"insurance_provider_credit_exclusion"}


def test_the_asset_sale_reading_wins_over_the_release():
    """Owner ruling 2026-10-02 (Q11 (b), R2-OW06): IAA's seller payouts three times within a month at a non-dealer are
    released by the insurer reading (INSURANCE is the auction's name) and then made non_revenue / asset_sale_proceeds
    by the tier loop: the asset-sale override wins."""
    rows = [(f"INSURANCE AUTO AUCTIONS DES:SELLER PMT ID:{n}", amount, day)
            for n, (amount, day) in enumerate(((3000.0, "03-02"), (3100.0, "03-09"), (3200.0, "03-16")), start=1)]
    records = _dated(rows)
    assert [rules_reading(record) for record in records] == [("non_revenue", "asset_sale_proceeds")] * 3


def test_a_zelle_credit_from_an_insurer_at_an_agency_is_excluded_with_the_release_as_its_prior_reading():
    """The underwriter's Q3 (R2-OW02, CR7): the Zelle step overrides the release after the tiers; the rules' reading
    (counted, insurer_paid_for_services) is kept on the record."""
    record = _dated([("ZELLE PAYMENT FROM SAMPLE INSURANCE CO CONF 99", 400.0, "03-02")], holder=AGENCY)[0]
    assert (record.revenue_tier, record.revenue_tier_reason) == ("non_revenue", "zelle_excluded")
    assert true_revenue.zelle_prior_reading(record) == COUNTED
    assert rules_reading(record) == COUNTED


def test_the_release_s_method_is_never_a_registry_or_claimed_method():
    """A released row is unclaimed, so §8.10's holds 4 to 11 still read it (T18b, T16 pin it on the tiers)."""
    assert true_revenue.INSURER_FOR_WORK_METHOD == "insurer_paid_for_services"
    assert true_revenue.INSURER_FOR_WORK_METHOD not in true_revenue._REGISTRY_METHODS
    record = _dated([("STATE FARM DES:DRP PAYMENT ID:1", 1234.0, "03-02")])[0]
    assert record.revenue_match_method == METHOD
    assert not true_revenue._claimed(record, revenue_text(record.normalized_description))


def test_a_claimed_row_is_never_released(monkeypatch):
    """The release skips a row the registry, a payout entity, a factoring payee or a financier claimed (the
    insurer-name hold's convention)."""
    monkeypatch.setattr(true_revenue, "_claimed", lambda record, text: True)
    records = _dated(_t4())
    assert all(record.revenue_match_method != METHOD for record in records)
    assert all(record.revenue_tier_reason != "insurer_paid_for_services" for record in records)


@pytest.mark.parametrize(("rows", "statement"), [
    *((case.values[0], case.values[1]) for case in COUNTED_CASES),
    # The released rows a later hold names.
    ([("FARMERS INS DES:PAYROLL ID:1", 1234.0, "03-02")], {"holder": REPAIR_SHOP}),
    ([("STATE FARM DES:DRP PAYMENT ID:1", 3000.0, "03-02"), ("STATE FARM DES:AUTOPAY ID:9", -3000.0, "03-03")],
     {"holder": REPAIR_SHOP}),
    ([("SAMPLE MUTUAL INSURANCE CO DES:INVESTMENT ID:1", 640.0, "03-02")], {"holder": AGENCY}),
])
def test_every_released_row_is_counted_or_held_by_a_later_hold_never_verified(rows, statement):
    released = [record for record in _dated(rows, **statement)
                if record.revenue_match_method == METHOD]
    assert released
    for record in released:
        assert record.revenue_classification == "unverified_deposit"
        assert record.revenue_tier in {"counted_flagged", "excluded_pending_review"}
        if record.revenue_tier == "counted_flagged":
            assert record.revenue_tier_reason == "insurer_paid_for_services"
            assert record.revenue_review_required is False
            assert "counted and flagged, never verified" in record.revenue_reason
        else:
            assert record.revenue_tier_reason not in {"insurer_named_payer", "insurer_payer"}
            assert record.revenue_review_required is True
            # Audit round 3, R3-B15 (R3-53): a held row's sentence never says it is counted.
            assert "counted and flagged" not in record.revenue_reason
            assert (f"never verified, and held for review "
                    f"({REVENUE_TIER_REASONS[record.revenue_tier_reason][1]})") in record.revenue_reason


def test_a_released_row_never_counts_toward_a_q5_or_q6_repeat():
    """Q2: never Verified and never toward a repeat. T4's three credits from one insurer would be Q6's verified repeats
    without the release; released, each is one of the rows Q5 and Q6 never read (_never_q5_or_q6)."""
    records = _dated(_t4())
    assert all(record.revenue_classification != "verified_revenue" for record in records)
    texts = [revenue_text(record.normalized_description) for record in records]
    facts = true_revenue.credit_facts(records[0], texts[0], debits=true_revenue.counter_debits(records, set()))
    assert true_revenue._never_q5_or_q6(records[0], texts[0], facts)


def test_the_bill_clause_reads_a_released_credit_as_no_insurer():
    """On R2-B02's CounterCredit: a released row's insurer fact is False, a held insurer's True."""
    released = _dated([("STATE FARM DES:DRP PAYMENT ID:1", 3000.0, "03-02")], holder=REPAIR_SHOP)[0]
    held = _dated([("FABRIKAM MUTUAL INSURANCE COMPANY DES:CLAIM PAYMT ID:1", 1234.0, "03-02")])[0]
    for record, insurer in ((released, False), (held, True)):
        text = revenue_text(record.normalized_description)
        assert true_revenue.counter_credit(record, text, payer_region(text)).insurer is insurer


@pytest.mark.parametrize(("days", "frequent"), [
    (["2054-03-01", "2054-03-15", "2054-03-31"], True),
    (["2054-03-01", "2054-03-15", "2054-04-01"], False),
    (["2054-03-20", "2054-04-01", "2054-04-15"], True),
    (["2054-03-01", "2054-03-20", "2054-04-15"], False),
    (["2054-01-01", "2054-03-01", "2054-03-10", "2054-03-30"], True),
    (["2054-03-01", "2054-03-02"], False),
    # An undated credit counts as inside any span: two dated credits within one span and one undated are three.
    (["2054-03-01", "2054-03-25", None], True),
    (["2054-03-01", "2054-04-30", None], False),
    (["2054-03-01", None, None], True),
    ([None, None, None], True),
    (["2054-03-01", None], False),
])
def test_the_frequency_reads_an_inclusive_31_day_span(days, frequent):
    from datetime import date

    found = [None if day is None else date.fromisoformat(day) for day in days]
    assert true_revenue._insurer_key_frequent(found) is frequent
    assert (true_revenue.INSURER_FOR_WORK_MIN_CREDITS, true_revenue.INSURER_FOR_WORK_WINDOW_DAYS) == (3, 31)


@pytest.mark.parametrize(("holder", "count", "expected"), [
    ("CONTOSO AUTO BODY LLC", 1, ("repair shop", "AUTO BODY")),
    ("CONTOSO COLLISION LLC", 1, ("repair shop", "COLLISION")),
    ("CONTOSO CARROSSERIE INC", 1, ("repair shop", "CARROSSERIE")),
    ("FABRIKAM INSURANCE AGENCY LLC", 1, ("insurance agency", "INSURANCE")),
    ("FABRIKAM INS AGENCY LLC", 1, ("insurance agency", "INS")),
    ("CONTOSO DENTAL PLLC", 1, ("clinic", "DENTAL")),
    ("CONTOSO PHYSIOTHERAPY INC", 1, ("clinic", "PHYSIOTHERAPY")),
    ("CONTOSO PHARMACY LLC", 1, ("pharmacy", "PHARMACY")),
    # The loose words need two eligible insurer credits.
    ("CONTOSO STAFFING AGENCY LLC", 1, None),
    ("CONTOSO STAFFING AGENCY LLC", 2, ("insurance agency", "AGENCY")),
    ("NORTHWIND VISION GRAPHICS LLC", 2, ("clinic", "VISION")),
    ("NORTHWIND TOWING LLC", 2, ("repair shop", "TOWING")),
    ("NORTHWIND ROOFING LLC", 1, None),
    # No trade word: HEALTHY, SURGE, a bare GLASS, a bakery.
    ("CONTOSO HEALTHY FOODS LLC", 2, None),
    ("CONTOSO SURGE LLC", 2, None),
    ("CONTOSO GLASS LLC", 2, None),
    ("CONTOSO BAKERY LLC", 2, None),
])
def test_the_holder_s_trade(holder, count, expected):
    record = _dated([("NORTHWIND SUPPLY DES:PAYMENT ID:1", 100.0, "03-02")], holder=holder)[0]
    assert true_revenue._holder_service_trade(record, (), count) == expected
    assert true_revenue.INSURER_FOR_WORK_LOOSE_MIN_CREDITS == 2


@pytest.mark.parametrize(("words", "form", "commission", "not_for_work"), [
    ("DRP PAYMENT", True, False, False),
    ("AGENTS EFT", True, True, False),
    ("AGENT EFT", True, True, False),
    ("AGTEFT", True, True, False),
    ("AGT COMM", True, True, False),
    ("AGENT COMP", True, True, False),
    ("COMMISSIONS", True, True, False),
    ("CONTINGENCY", True, True, False),
    ("TRAVELERSPICOMM", True, True, False),
    ("REPAIRS", True, False, False),
    ("VENDOR PMT", True, False, False),
    ("PAYMENT", False, False, False),
    ("COMMUNITY", False, False, False),
    ("PREM COMM", True, True, True),
    ("INS PREM", False, False, True),
    ("REFUND", False, False, True),
    ("DIVIDEND", False, False, True),
    ("UNEARNED", False, False, True),
    ("MEMBER", False, False, True),
    ("DISABILITY", False, False, True),
    ("ANNUITY", False, False, True),
    ("PENSION", False, False, True),
    ("INVALIDITE", False, False, True),
    ("CLAIM PMT", False, False, False),
])
def test_the_service_and_not_for_work_forms(words, form, commission, not_for_work):
    assert (true_revenue._INSURER_SERVICE_FORM.search(words) is not None) is form
    assert (true_revenue._INSURER_COMMISSION_FORM.search(words) is not None) is commission
    assert (true_revenue._INSURER_NOT_FOR_WORK.search(words) is not None) is not_for_work


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 3, R3-B13: the underwriter's Q2 and I26 insurer readings. "Today" below is the reading at R3-B12's tip
# (2c0ced6).
# ---------------------------------------------------------------------------------------------------------------------

def _settings(rows, **statement):
    """CR7: each credit's reading under both Zelle settings: (the No setting's rules reading, a Zelle deposit's final
    tier asserted `zelle_excluded` and its prior returned; the Yes setting's tier and reason)."""
    no = [rules_reading(record) for record in _dated(rows, **statement)]
    yes = [(record.revenue_tier, record.revenue_tier_reason)
           for record in _dated(rows, zelle_true_revenue=True, **statement)]
    return no, yes


def _same_in_both(rows, **statement):
    """A row no Zelle setting reads: its one reading, asserted equal under both settings."""
    no, yes = _settings(rows, **statement)
    assert no == yes
    return no


GEICO_COUNTY = [(f"GEICO COUNTY MUT DES:CLAIM PMT ID:000{n} INDN:CONTOSO BAKERY LLC CO ID:0000000001 CCD", amount, day)
                for n, (amount, day) in enumerate(((812.0, "03-02"), (1290.5, "03-09"), (640.25, "03-17")), start=1)]
ALLSTATE_COUNTY = [(text.replace("GEICO COUNTY MUT", "ALLSTATE COUNTY"), amount, day)
                   for text, amount, day in GEICO_COUNTY]


@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # Progressive's Texas county mutual paying a repair shop's DRP (today Verified as a public payer).
    pytest.param([("PROG COUNTY MUT DES:DRP PAYMENT ID:0001 INDN:CONTOSO AUTO REPAIR LLC CO ID:0000000001 CCD", 2450.0,
                   "03-02")], {"holder": REPAIR_SHOP}, [COUNTED], id="prog-county-mut-drp"),
    # A listed carrier's county mutual three times within 16 days at a bakery (today non_revenue: the government arm
    # read it first and found no insurer word, so no release).
    pytest.param(GEICO_COUNTY, {}, [COUNTED] * 3, id="geico-county-mut-3-in-31"),
    # A county mutual cut before its insurer word, which the veto cannot reach: the registry arm reads first.
    pytest.param(ALLSTATE_COUNTY, {}, [COUNTED] * 3, id="allstate-county-arm-order"),
    # Its released CLAIM is no public payer's claim to the non-sale hold either; the public arm's other words (an
    # award) still hold it.
    pytest.param([(text.replace("CLAIM PMT", "CLAIM AWARD"), amount, day) for text, amount, day in ALLSTATE_COUNTY],
                 {}, [("excluded_pending_review", "non_sale_purpose")] * 3, id="allstate-county-award"),
    # Unlisted county mutuals at a bakery, one-off: held as an insurer (today Verified as a public payer).
    pytest.param([("SAMPLE TEXAS COUNTY MUTUA DES:PAYMENT ID:0001", 1234.0, "03-02")], {}, [HELD],
                 id="county-mutua-one-off"),
    pytest.param([("SAMPLE COUNTY MUT INS DES:PAYMENT ID:0001", 1234.0, "03-02")], {}, [HELD], id="county-mut-ins"),
    # State Farm's full county-mutual name on a wire paying a repair invoice at a repair shop (today held
    # insurer_payer).
    pytest.param([("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:0000000001 ORIG:STATE FARM COUNTY MUTUAL INS CO "
                   "ID:0001 PMT DET:REPAIR INV 0001", 5000.0, "03-02")], {"holder": REPAIR_SHOP}, [COUNTED],
                 id="state-farm-county-mutual-wire"),
    # Controls: counties paying the business (a vendor payment) and a county's fire department stay public payers,
    # verified; a county's self-insurance fund keeps the government arm's reading (held, never for work); a county
    # mutual's premium refund stays the reversal rule's non_revenue.
    pytest.param([("HARRIS COUNTY DES:VENDOR PMT ID:0001", 1234.0, "03-02")], {}, [VERIFIED], id="harris-county"),
    pytest.param([("SAMPLE COUNTY DES:VENDOR PMT ID:0001", 1234.0, "03-02")], {}, [VERIFIED], id="sample-county"),
    pytest.param([("SAMPLE COUNTY FIRE DEPT DES:VENDOR PMT ID:0001", 1234.0, "03-02")], {}, [VERIFIED],
                 id="county-fire-dept"),
    pytest.param([("SAMPLE COUNTY SELF INSURANCE FUND DES:PAYMENT ID:0001", 812.0, "03-02")],
                 {"holder": NORTHWIND_BAKERY}, [HELD], id="county-self-insurance-fund"),
    pytest.param([("ACH DEPOSIT PROG COUNTY MUT REFUND 0000000001", 640.0, "03-02")], {}, [("non_revenue", None)],
                 id="county-mut-refund"),
    # R3-B13 review round 1 (finding 3): a county's mutual-aid body is a public compact, never a county mutual: it
    # stays a public payer, verified (be75450: counted insurer_paid_for_services).
    pytest.param([("HARRIS COUNTY MUTUAL AID DES:VENDOR PMT ID:0001", 1234.0, "03-02")], {}, [VERIFIED],
                 id="county-mutual-aid"),
])
def test_r3_11_a_texas_county_mutual_is_an_insurer_never_a_county(rows, statement, expected):
    """Audit round 3, R3-B13 (R3-11; I26 by Q6 of 2026-09-28, "insurers never count", and the underwriter's Q2 of
    2026-10-02): a Texas county mutual is a private carrier, never a county government. `<WORD> COUNTY` followed by an
    insurer word is no public payer (_PUBLIC_PAYER_NAME's veto), COUNTY MUT is an insurer spelling, and a listed
    insurer's credit reads as the registry's carrier before the government arm."""
    records = _dated(rows, **statement)
    assert [rules_reading(record) for record in records] == expected
    if expected == [("non_revenue", None)]:
        assert records[0].revenue_match_method == "reversal_cancellation_exclusion"


def test_r3_11_a_released_insurer_s_claim_is_no_public_payer_s_claim():
    """The non-sale hold's public-payer arm reads no CLAIM on a released row (as its CLAIM arm already did)."""
    text, region = "ALLSTATE COUNTY DES:CLAIM PMT ID:1", "ALLSTATE COUNTY"
    assert true_revenue.non_sale_purpose(text, region) is True
    assert true_revenue.non_sale_purpose(text, region, insurer_work=True) is False
    assert true_revenue.non_sale_purpose("ALLSTATE COUNTY DES:AWARD ID:1", region, insurer_work=True) is True


def test_r3_11_the_reader_keys_a_county_mutual_by_its_carrier():
    for rows, key in ((GEICO_COUNTY, "GEICO"), (ALLSTATE_COUNTY, "Allstate")):
        for record in _dated(rows):
            row = revenue_text(record.normalized_description)
            reading = true_revenue.insurer_payer_reading(record, row, payer_region(row), entry_fields(row))
            assert (reading.key, reading.kind, reading.for_work) == (key, "registry", True)
    # The self-insurance fund keeps the government arm's reading.
    assert _reader("SAMPLE COUNTY SELF INSURANCE FUND DES:PAYMENT ID:0001", holder=NORTHWIND_BAKERY) == _expected(
        "SAMPLE COUNTY SELF INSURANCE", "named", False)


@pytest.mark.parametrize(("name", "public"), [
    ("PROG COUNTY MUT", False), ("STATE FARM COUNTY MUTUAL", False), ("SAMPLE COUNTY MUTUA", False),
    ("SAMPLE COUNTY INS", False), ("SAMPLE COUNTY CASUALTY", False), ("SAMPLE COUNTY INSURANCE CO", False),
    ("SAMPLE COUNTY INDEMNITY", False), ("SAMPLE COUNTY ASSURANCE", False), ("SAMPLE COUNTY LLOYDS", False),
    ("HARRIS COUNTY", True), ("SAMPLE COUNTY SCHOOL", True), ("SAMPLE COUNTY INSPECTIONS", True),
    ("SAMPLE COUNTY SELF INSURANCE", True), ("SAMPLE COUNTY FIRE DEPT", True), ("SAMPLE PARISH MUTUAL", False),
    # R3-B13 review round 1 (finding 3): MUTUAL AID is a public compact.
    ("HARRIS COUNTY MUTUAL AID", True), ("SAMPLE PARISH MUTUAL AID", True), ("SAMPLE COUNTY MUTUAL INS", False),
    ("SAMPLE COUNTY MUTUAL AIDE INS", False),
])
def test_r3_11_the_public_payer_name_vetoes_an_insurer_word_after_county(name, public):
    from analysis import transaction_classifier as classifier

    assert (classifier._PUBLIC_PAYER_NAME.match(name) is not None) is public


ONE_OFF = 1875.0


@pytest.mark.parametrize(("rows", "statement"), [
    # Push and instant rails (today counted p2p: the widened spellings and the brands were off the whole channel).
    pytest.param([("REAL TIME PAYMENT FROM SAMPLE INS CO", ONE_OFF, "03-02")], {}, id="rtp-ins"),
    pytest.param([("INSTANT PAYMENT FROM SAFECO", ONE_OFF, "03-02")], {}, id="instant-brand"),
    pytest.param([("FEDNOW CREDIT FROM HISCOX", ONE_OFF, "03-02")], {}, id="fednow-brand"),
    # Named transfers.
    pytest.param([("ONLINE TRANSFER FROM SAMPLE INS CO", ONE_OFF, "03-02")], {}, id="online-transfer-ins"),
    pytest.param([("TRANSFER FROM SAMPLE CASUALT", ONE_OFF, "03-02")], {}, id="transfer-casualt"),
    # A carrier's ordinary ACH entry whose description is TRANSFER (Bank of America's and Chase's layouts).
    pytest.param([("SAMPLE INS CO DES:TRANSFER ID:0001 INDN:CONTOSO BAKERY LLC CO ID:0000000001 CCD", ONE_OFF,
                   "03-02")], {"bank": "Bank of America"}, id="bofa-des-transfer"),
    pytest.param([("ORIG CO NAME:SAFECO ORIG ID:0000000001 DESC DATE: CO ENTRY DESCR:TRANSFER SEC:CCD "
                   "TRACE#:000000000000001 EED:540302 IND ID:0001 IND NAME:CONTOSO BAKERY LLC TRN: 0000000001TC",
                   ONE_OFF, "03-02")], {"bank": "Chase"}, id="chase-entry-transfer"),
    # MUTUA reads off a consumer rail beside a company form.
    pytest.param([("REAL TIME PAYMENT FROM CONTOSO MUTUA INS CO", ONE_OFF, "03-02")], {"holder": NORTHWIND_BAKERY},
                 id="rtp-mutua-company"),
])
def test_r3_57_widened_spellings_read_off_the_consumer_rails(rows, statement):
    """Audit round 3, R3-B13 (R3-57; §17.1's I26 default: an insurer however spelled is held as one spelled
    INSURANCE): off a consumer rail (Zelle, Interac, e-Transfer, Venmo, Cash App, Apple Cash, Popmoney), every insurer
    spelling and brand is read on the person-to-person channel too, so a one-off insurer credit on a push rail, a
    named transfer or an ACH entry worded TRANSFER is held as insurer_named_payer under both Zelle settings."""
    assert _same_in_both(rows, **statement) == [HELD]


@pytest.mark.parametrize(("rows", "statement", "yes", "no"), [
    # Zelle: under Yes the rail's own reading (counted p2p); under No excluded, the prior the same.
    pytest.param([("ZELLE PAYMENT FROM SAMPLE INS CO", ONE_OFF, "03-02")], {}, ("counted_flagged", "p2p"),
                 ("counted_flagged", "p2p"), id="zelle-ins"),
    # The other consumer rails: a sender's surname or given name, or the rail's own word, is no cut insurer.
    pytest.param([("INTERAC E-TRANSFER FROM PAT MUTUA", ONE_OFF, "03-02")], {"bank": "RBC"},
                 ("counted_flagged", "p2p"), ("counted_flagged", "p2p"), id="interac-surname"),
    pytest.param([("VENMO FROM PAT SUBROTO", ONE_OFF, "03-02")], {}, ("counted_flagged", "p2p"),
                 ("counted_flagged", "p2p"), id="venmo-given-name"),
    pytest.param([("APPLE CASH INS 0000 PMNT RCVD", ONE_OFF, "03-02")], {}, ("counted_flagged", "p2p"),
                 ("counted_flagged", "p2p"), id="apple-cash-ins"),
    # A push rail's person-shaped MUTUA (no company form) is a surname.
    pytest.param([("REAL TIME PAYMENT FROM CONTOSO MUTUA", ONE_OFF, "03-02")], {"holder": NORTHWIND_BAKERY},
                 ("counted_flagged", "p2p"), ("counted_flagged", "p2p"), id="rtp-mutua-person"),
])
def test_r3_57_the_consumer_rails_keep_the_spelled_out_words_alone(rows, statement, yes, no):
    no_reading, yes_reading = _settings(rows, **statement)
    assert (yes_reading, no_reading) == ([yes], [no])
    if "ZELLE" in rows[0][0]:
        record = _dated(rows, **statement)[0]
        assert (record.revenue_tier, record.revenue_tier_reason) == ("non_revenue", "zelle_excluded")


def test_r3_57_the_reader_on_a_push_rail():
    assert _reader("REAL TIME PAYMENT FROM SAMPLE INS CO") == _expected("SAMPLE INS CO", "named", True)
    assert _reader("INSTANT PAYMENT FROM SAFECO") == _expected("Safeco", "brand", True)
    assert _reader("REAL TIME PAYMENT FROM CONTOSO MUTUA", holder=NORTHWIND_BAKERY) is None
    # A company form (classifier.company_form: a legal-form word, never a bare CO) beside the cut MUTUA.
    assert _reader("REAL TIME PAYMENT FROM CONTOSO MUTUA CO", holder=NORTHWIND_BAKERY) is None
    assert _reader("REAL TIME PAYMENT FROM CONTOSO MUTUA LLC", holder=NORTHWIND_BAKERY)[1:] == ("named", True)
    assert _reader("ONLINE TRANSFER FROM CONTOSO MUTUA INC", holder=NORTHWIND_BAKERY)[1:] == ("named", True)
    # A consumer rail keeps the spelled-out words and CLAIM alone.
    assert _reader("ZELLE PAYMENT FROM SAMPLE INS CO") is None
    assert _reader("INTERAC E-TRANSFER FROM SAMPLE MUTUA CO", bank="RBC") is None


def _weekly(entry: str, payer: str = "SAMPLE MUTUAL INS", holder: str = "NORTHWIND BAKERY LLC", amount: float = 812.0):
    return [(f"{payer} DES:{entry} ID:0001 INDN:{holder} CO ID:0000000001 PPD", amount, day)
            for day in ("03-02", "03-09", "03-16")]


PERSONAL_BENEFIT_ENTRIES = ("STD BENEFIT", "STD PMT", "WEEKLY BEN", "INCOME BNFT", "WC BENEFIT", "WORKERS COMP",
                            "BENEFITS")
LIFE_POLICY_ENTRIES = ("DEATH BENEFIT", "DEATH CLAIM", "SURVIVOR BEN", "CSV SURR", "SURRENDER", "CASH VALUE",
                       "MATURITY")


@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # A disability benefit by another name, workers' compensation and a plain BENEFIT(S) wording, three weekly at a
    # bakery (today counted on the 3-in-31 ground).
    *(pytest.param(_weekly(entry), {"holder": NORTHWIND_BAKERY}, [HELD] * 3, id=f"weekly-{entry}")
      for entry in PERSONAL_BENEFIT_ENTRIES),
    # Life-policy money, one-off at a repair shop and at an agency (today counted on the holder's trade).
    *(pytest.param([(f"SAMPLE LIFE INSURANCE CO DES:{entry} ID:0001", 25000.0, "03-02")], {"holder": holder}, [HELD],
                   id=f"{label}-{entry}")
      for entry in LIFE_POLICY_ENTRIES for label, holder in (("repair", REPAIR_SHOP), ("agency", AGENCY))),
    # A long-term disability claim in Chase's entry field.
    pytest.param([("ORIG CO NAME:SAMPLE LIFE INSURANCE ORIG ID:0000000001 DESC DATE: CO ENTRY DESCR:LTD CLAIM SEC:PPD "
                   "TRACE#:000000000000001 EED:540302 IND ID:0001 IND NAME:CONTOSO AUTO REPAIR LLC TRN: 0000000001TC",
                   2500.0, "03-02")], {"holder": REPAIR_SHOP, "bank": "Chase"}, [HELD], id="chase-ltd-claim"),
    # Controls. LTD on the payer is a legal form, never a disability benefit.
    pytest.param([("SAMPLE INSURANCE COMPANY LTD DES:DRP PAYMENT ID:0001", 2450.0, "03-02")], {"holder": REPAIR_SHOP},
                 [COUNTED], id="payer-ltd-drp"),
    pytest.param([("SAMPLE INSURANCE CO LTD DES:CLAIM PMT ID:0001", 2450.0, "03-02")], {"holder": REPAIR_SHOP},
                 [COUNTED], id="payer-ltd-claim-pmt"),
    # Workers' compensation and a plain BENEFITS wording paid to a provider are its service revenue (Q2: "Medical
    # claim payments to providers keep counting as today").
    pytest.param(_weekly("WC CLAIM PMT", holder=CLINIC), {"holder": CLINIC}, [COUNTED] * 3, id="wc-at-a-clinic"),
    pytest.param(_weekly("BENEFITS", holder="CONTOSO PHARMACY LLC"), {"holder": "CONTOSO PHARMACY LLC"},
                 [COUNTED] * 3, id="benefits-at-a-pharmacy"),
    # The commission override.
    pytest.param([("SAMPLE LIFE INS DES:DEATH CLAIM COMM ID:0001", 640.0, "03-02")], {"holder": AGENCY}, [COUNTED],
                 id="death-claim-commission"),
    # Unchanged: a disability benefit stays held; a policy loan stays the strong rule's non_revenue.
    pytest.param([("SAMPLE LIFE INSURANCE CO DES:DISABILITY ID:0001", 812.0, "03-02")], {"holder": AGENCY}, [HELD],
                 id="disability"),
    pytest.param([("SAMPLE LIFE INS DES:POLICY LOAN ID:0001", 812.0, "03-02")], {"holder": AGENCY},
                 [("non_revenue", None)], id="policy-loan"),
])
def test_r3_10_a_personal_benefit_is_never_paid_for_work(rows, statement, expected):
    """Audit round 3, R3-B13 (R3-10; the underwriter's Q2 of 2026-10-02, "A one-off claim paid to a business on its own
    policy stays out ... Medical claim payments to providers keep counting as today"; the MCA principle: personal
    benefits are never revenue): a disability benefit by any name, a death, survivor, surrender, cash-value or maturity
    payment refuses every ground; workers' compensation and a plain BENEFIT(S) wording refuse it except at a clinic or
    a pharmacy; a commission form printed in the same words still releases."""
    records = _dated(rows, **statement)
    assert [rules_reading(record) for record in records] == expected
    if expected == [("non_revenue", None)]:
        assert records[0].revenue_match_method == "strong_non_revenue_rule"
    for record, reading in zip(records, expected):
        assert (record.revenue_match_method == METHOD) is (reading == COUNTED)


@pytest.mark.parametrize(("holder", "provider"), [
    (CLINIC, True), ("CONTOSO PHARMACY LLC", True), ("CONTOSO DENTAL PLLC", True),
    # A loose clinic word names a provider here (the brief reads the trade with the loose table).
    ("CONTOSO HEALTH SERVICES LLC", True),
    # R3-B13 review round 1 (finding 1): the provider is the holder's first trade (_holder_service_trade's label),
    # so a name whose first trade is a repair shop or an insurance agency is no provider, whatever clinic or pharmacy
    # word it also prints.
    ("FABRIKAM INSURANCE MEDICAL BILLING LLC", False), ("CONTOSO HEALTH INSURANCE AGENCY LLC", False),
    ("CONTOSO MED INSURANCE AGENCY LLC", False), ("CONTOSO COLLISION DOCTORS LLC", False),
    ("CONTOSO AUTO REPAIR AND RX LLC", False),
    (BAKERY, False), (REPAIR_SHOP, False), (AGENCY, False), ("CONTOSO STAFFING AGENCY LLC", False),
])
def test_r3_10_the_holder_is_a_provider(holder, provider):
    record = _dated([("NORTHWIND SUPPLY DES:PAYMENT ID:1", 100.0, "03-02")], holder=holder)[0]
    assert true_revenue._holder_provider(record) is provider
    trade = true_revenue._holder_service_trade(record, (), true_revenue.INSURER_FOR_WORK_LOOSE_MIN_CREDITS)
    assert (trade is not None and trade[0] in {"clinic", "pharmacy"}) is provider


@pytest.mark.parametrize(("words", "personal", "ltd", "non_provider"), [
    ("STD BENEFIT", True, False, True), ("STD PMT", True, False, False), ("STD CLM", True, False, False),
    ("WEEKLY BEN", True, False, False), ("INCOME BNFT", True, False, True), ("DEATH CLAIM", True, False, False),
    ("SURVIVOR BEN", True, False, False), ("CSV SURR", True, False, False), ("SURRENDER", True, False, False),
    ("CASH VALUE", True, False, False), ("CASHVALUE", True, False, False), ("MATURITY", True, False, False),
    ("MATURED", True, False, False), ("BENEFICIARY", True, False, False),
    ("LTD BENEFIT", False, True, True), ("LTD CLAIM", False, True, False), ("LTD PMT", False, True, False),
    ("WC BENEFIT", False, False, True), ("WORKERS COMP", False, False, True), ("WORKCOMP", False, False, True),
    ("BENEFITS", False, False, True), ("BNFT", False, False, True),
    # Never read: a bare LTD (a legal form), a bare COMP (Truist's INS COMP commission), LIFE, CLAIM PMT.
    ("LTD", False, False, False), ("SAMPLE INSURANCE CO LTD", False, False, False), ("INS COMP", False, False, False),
    ("LIFE", False, False, False), ("CLAIM PMT", False, False, False), ("STANDARD", False, False, False),
])
def test_r3_10_the_personal_benefit_forms(words, personal, ltd, non_provider):
    assert (true_revenue._INSURER_PERSONAL_BENEFIT.search(words) is not None) is personal
    assert (true_revenue._INSURER_LTD_BENEFIT.search(words) is not None) is ltd
    assert (true_revenue._INSURER_NON_PROVIDER_BENEFIT.search(words) is not None) is non_provider


def _one_off(entry: str, holder: str, payer: str = "SAMPLE MUTUAL INS"):
    return [(f"{payer} DES:{entry} ID:0001 INDN:{holder} CO ID:0000000001 PPD", 812.0, "03-02")]


def _three(text: str, amount: float = 812.0):
    return [(text.replace("000N", f"000{n}"), amount, day) for n, day in ((1, "03-02"), (2, "03-09"), (3, "03-16"))]


@pytest.mark.parametrize(("rows", "holder", "expected"), [
    # Workers' compensation or a plain BENEFIT(S) wording at a holder whose first trade is an insurance agency or a
    # repair shop, though its name also prints a clinic or a pharmacy word (be75450: counted on the holder's trade).
    pytest.param(_one_off("WC BENEFIT", "CONTOSO HEALTH INSURANCE AGENCY LLC"), "CONTOSO HEALTH INSURANCE AGENCY LLC",
                 [HELD], id="health-insurance-agency-wc"),
    pytest.param(_one_off("BENEFITS", "CONTOSO HEALTH INSURANCE AGENCY LLC", payer="AFLAC"),
                 "CONTOSO HEALTH INSURANCE AGENCY LLC", [HELD], id="health-insurance-agency-aflac-benefits"),
    pytest.param(_one_off("WC BENEFIT", "CONTOSO MED INSURANCE AGENCY LLC"), "CONTOSO MED INSURANCE AGENCY LLC",
                 [HELD], id="med-insurance-agency-wc"),
    pytest.param(_one_off("WC BENEFIT", "CONTOSO COLLISION DOCTORS LLC"), "CONTOSO COLLISION DOCTORS LLC", [HELD],
                 id="collision-doctors-wc"),
    pytest.param(_one_off("WORKERS COMP", "CONTOSO AUTO REPAIR AND RX LLC"), "CONTOSO AUTO REPAIR AND RX LLC", [HELD],
                 id="auto-repair-and-rx-workers-comp"),
    pytest.param(_one_off("WC BENEFIT", "FABRIKAM INSURANCE MEDICAL BILLING LLC"),
                 "FABRIKAM INSURANCE MEDICAL BILLING LLC", [HELD], id="insurance-medical-billing-wc"),
    # Controls: a holder whose first trade is a clinic or a pharmacy is paid for treatment (counted, as before).
    pytest.param(_one_off("WC BENEFIT", CLINIC), CLINIC, [COUNTED], id="clinic-wc"),
    pytest.param(_one_off("BENEFITS", "CONTOSO PHARMACY LLC"), "CONTOSO PHARMACY LLC", [COUNTED],
                 id="pharmacy-benefits"),
    pytest.param(_three("SAMPLE MUTUAL INS DES:WC BENEFIT ID:000N INDN:CONTOSO HEALTH SERVICES LLC CO ID:0000000001 "
                        "PPD"), "CONTOSO HEALTH SERVICES LLC", [COUNTED] * 3, id="loose-clinic-wc-x3"),
])
def test_r3_b13_r1_the_provider_is_the_holder_s_first_trade(rows, holder, expected):
    """Audit round 3, R3-B13, review round 1 (finding 1; R3-10's brief: the holder is a provider when
    _holder_service_trade(record, receiver_holders, INSURER_FOR_WORK_LOOSE_MIN_CREDITS) labels a clinic or a
    pharmacy): workers' compensation and a plain BENEFIT(S) wording refuse the release wherever the holder's first trade
    is no clinic or pharmacy, so a health-insurance agency or a collision shop printing a clinic word keeps the insurer
    hold."""
    records = _dated(rows, holder=holder)
    assert [rules_reading(record) for record in records] == expected
    for record, reading in zip(records, expected):
        assert (record.revenue_match_method == METHOD) is (reading == COUNTED)


@pytest.mark.parametrize(("rows", "holder", "expected"), [
    # A BENEFIT word inside the carrier's name, followed by its insurer word or legal form, names the payer, never the
    # payment (be75450: held insurer_named_payer; counted at R3-B13's base).
    pytest.param([("MUTUAL BENEFIT INS CO DES:DRP PAYMENT ID:0001", 2450.0, "03-02")], REPAIR_SHOP, [COUNTED],
                 id="mutual-benefit-carrier-drp"),
    pytest.param([("MUTUAL BENEFIT GROUP DES:DRP PAYMENT ID:0001", 2450.0, "03-02")], REPAIR_SHOP, [COUNTED],
                 id="mutual-benefit-group-drp"),
    pytest.param(_three("SAMPLE BENEFIT LIFE INS CO DES:CLAIM PMT ID:000N"), "CONTOSO PT LLC", [COUNTED] * 3,
                 id="benefit-life-carrier-claims-x3"),
    pytest.param([("SAMPLE BENEFITS INS CO DES:VENDOR PMT ID:0001", 1234.0, "03-02")], NORTHWIND_BAKERY, [COUNTED],
                 id="benefits-carrier-vendor-pmt"),
    # Controls (held): the same carrier paying a benefit on its entry; a BENEFIT wording printed after the carrier's
    # name on a layout with no entry field; a payer region printing only a brand and the wording; workers'
    # compensation on the payer, which names a workers' compensation carrier however it prints.
    pytest.param(_three("MUTUAL BENEFIT INS CO DES:BENEFITS ID:000N"), NORTHWIND_BAKERY, [HELD] * 3,
                 id="mutual-benefit-carrier-benefits-x3"),
    pytest.param(_three("SAMPLE MUTUAL INS BENEFIT PMT 000N"), NORTHWIND_BAKERY, [HELD] * 3,
                 id="no-entry-benefit-after-the-name-x3"),
    pytest.param(_three("SAMPLE WC INS FUND DES:PAYMENT ID:000N"), NORTHWIND_BAKERY, [HELD] * 3,
                 id="wc-carrier-x3"),
    pytest.param(_three("SAMPLE WORKERS COMP INS FUND DES:PAYMENT ID:000N"), NORTHWIND_BAKERY, [HELD] * 3,
                 id="workers-comp-carrier-x3"),
    pytest.param(_three("SAMPLE MUTUAL INS WC PMT 000N"), NORTHWIND_BAKERY, [HELD] * 3, id="no-entry-wc-x3"),
])
def test_r3_b13_r1_a_benefit_word_in_the_carrier_s_name_is_no_benefit(rows, holder, expected):
    """Audit round 3, R3-B13, review round 1 (finding 2): a plain BENEFIT(S) or BNFT wording is read on the purpose and,
    on the payer region, only where no insurer word, spelling or legal form follows it (there it is the carrier's name:
    'MUTUAL BENEFIT INS CO'); workers' compensation (WC, WORKERS COMP, WORK COMP) is read on both, as R3-10 ruled."""
    records = _dated(rows, holder=holder)
    assert [rules_reading(record) for record in records] == expected


@pytest.mark.parametrize(("own", "purpose", "read"), [
    ("MUTUAL BENEFIT INS CO", "DRP PAYMENT", False), ("SAMPLE BENEFIT LIFE INS CO", "CLAIM PMT", False),
    ("SAMPLE BENEFITS INS CO", "", False), ("MUTUAL BENEFIT GROUP", "", False), ("SAMPLE BNFT ASSURANCE", "", False),
    ("MUTUAL BENEFIT INS CO", "BENEFITS", True), ("SAMPLE MUTUAL INS BENEFIT PMT", "", True),
    ("AFLAC BENEFITS", "", True), ("SAMPLE INS CO", "BNFT", True), ("SAMPLE WC INS FUND", "PAYMENT", True),
    ("SAMPLE WORKERS COMP INS FUND", "", True), ("SAMPLE INS CO", "WC CLAIM", True),
    ("SAMPLE INS CO", "PAYMENT", False),
])
def test_r3_b13_r1_the_non_provider_benefit_reading(own, purpose, read):
    assert true_revenue._non_provider_benefit(own, purpose) is read


ROUND_ZELLE = [(f"Zelle payment from SAMPLE INSURANCE CO Conf# 000000000{n}", 1000.0, day)
               for n, day in ((1, "03-02"), (2, "03-09"), (3, "03-16"))]
ROUND_ZEL = [(f"ZEL FROM SAMPLE INSURANCE CO WFCT0ABCDE1{n}", 1000.0, day)
             for n, day in ((1, "03-02"), (2, "03-09"), (3, "03-16"))]
REPEAT = ("excluded_pending_review", "p2p_round_repeat")
ROUND_P2P = {
    "chase-rtp": ([(f"REAL TIME PAYMENT CREDIT RECD FROM ABA/CONTR BNK-000000001 FROM: SAMPLE MUTUAL INSURANCE CO "
                    f"REF: 000{n}", 500.0, day) for n, day in ((1, "03-02"), (2, "03-09"))],
                  {"holder": REPAIR_SHOP, "bank": "Chase"}),
    "wells-instant": ([(f"INSTANT PMT FROM SAMPLE INSURANCE CO ON 03/0{n} REF # RTP000000000{n}", 500.0, day)
                       for n, day in ((2, "03-02"), (9, "03-09"))], {"holder": REPAIR_SHOP, "bank": "Wells Fargo"}),
    "wealthsimple-interac": ([("INTERAC E-TRANSFER FROM SAMPLE ASSURANCE CO", 800.0, day)
                              for day in ("03-02", "03-09")], {"holder": CLINIC, "bank": "Wealthsimple"}),
    "online-transfer": ([("ONLINE TRANSFER FROM SAMPLE INSURANCE CO", 2500.0, day) for day in ("03-02", "03-09")],
                        {"holder": CLINIC}),
}


@pytest.mark.parametrize(("rows", "statement"), [
    pytest.param(ROUND_ZELLE, {"bank": "Bank of America"}, id="bofa-zelle"),
    # R3-B12's reconciliation: PNC's ZEL is read as its ZELLE twin in pass 7.
    pytest.param(ROUND_ZEL, {"bank": "PNC Bank"}, id="pnc-zel"),
])
def test_r3_09_one_insurer_s_repeated_round_sums_on_zelle_are_held(rows, statement):
    """Audit round 3, R3-B13 (R3-09; the underwriter's Q3 of 2026-10-02, "repeated round sums from one sender held",
    and the 2026-10-06 amendment, "the same round amount repeated by one sender are held for review (releasable)"):
    the Q2 release never skips §8.4's round-sum repeat on a person-to-person row. Yes: held p2p_round_repeat, its
    method still the release's (today counted insurer_paid_for_services); No: zelle_excluded with that prior."""
    no, yes = _settings(rows, **statement)
    assert yes == [REPEAT] * 3
    assert no == [REPEAT] * 3
    yes_records = _dated(rows, zelle_true_revenue=True, **statement)
    assert [record.revenue_match_method for record in yes_records] == [METHOD] * 3
    assert [(record.revenue_tier, record.revenue_tier_reason) for record in _dated(rows, **statement)] == [
        ("non_revenue", "zelle_excluded")] * 3


@pytest.mark.parametrize("case", sorted(ROUND_P2P))
def test_r3_09_one_insurer_s_repeated_round_sums_on_a_push_rail_or_a_named_transfer_are_held(case):
    rows, statement = ROUND_P2P[case]
    assert _same_in_both(rows, **statement) == [REPEAT] * len(rows)
    assert [record.revenue_match_method for record in _dated(rows, **statement)] == [METHOD] * len(rows)


@pytest.mark.parametrize(("rows", "statement", "reason"), [
    pytest.param([("STATE FARM DES:DRP PAYMENT ID:1", 3000.0, "03-02"),
                  ("STATE FARM DES:AUTOPAY ID:9", -3000.0, "03-03")],
                 {"holder": REPAIR_SHOP}, "payer_also_debited", id="T18b"),
    pytest.param([("FARMERS INS DES:PAYROLL ID:1", 1234.0, "03-02")], {"holder": REPAIR_SHOP}, "payroll_or_salary",
                 id="T16"),
    # R3-B13's R3-09, Zelle Yes: one insurer's repeated round sums on Zelle are held p2p_round_repeat.
    pytest.param(ROUND_ZELLE, {"bank": "Bank of America", "zelle_true_revenue": True}, "p2p_round_repeat",
                 id="r3-09-zelle-yes"),
])
def test_r3_53_a_released_insurer_a_later_hold_names_says_it_is_held(rows, statement, reason):
    """Audit round 3, R3-B15 (R3-53; §5.3, §8.10): the Q2 release re-states an insurer's credit with "counted and
    flagged, never verified"; when a later hold names the row, its sentence names the hold by the hold's own label
    (REVENUE_TIER_REASONS) instead, and nothing else of the record changes (today the held row kept the counted
    sentence, which the JSON download and the package's evidence sections write beside excluded_pending_review)."""
    records = [record for record in _dated(rows, **statement) if record.revenue_match_method == METHOD]
    assert records
    label = REVENUE_TIER_REASONS[reason][1]
    for record in records:
        assert (record.revenue_tier, record.revenue_tier_reason) == ("excluded_pending_review", reason)
        assert "counted and flagged" not in record.revenue_reason
        assert f"never verified, and held for review ({label}) (the owner's ruling on the underwriter's Q2)" in (
            record.revenue_reason)
        assert record.revenue_reason.startswith("An insurer pays the business for its work (")


ODD = (1234.56, 987.65, 1050.25)


@pytest.mark.parametrize(("rows", "statement", "zelle"), [
    # The same rows at amounts that are no round sum stay counted.
    pytest.param([(text, amount, day) for (text, _amount, day), amount in zip(ROUND_ZELLE, ODD)],
                 {"bank": "Bank of America"}, True, id="bofa-zelle-odd"),
    *(pytest.param([(text, amount, day) for (text, _amount, day), amount in zip(ROUND_P2P[case][0], ODD)],
                   ROUND_P2P[case][1], False, id=f"{case}-odd") for case in sorted(ROUND_P2P)),
    # One round Zelle credit is no repeat.
    pytest.param(ROUND_ZELLE[:1], {"bank": "Bank of America", "holder": AGENCY}, True, id="single-round-zelle"),
    # The round-sum repeat is the person-to-person channel's: an insurer's round ACH payments stay counted.
    pytest.param([(f"SAMPLE INSURANCE CO DES:PAYMENT ID:000{n}", 1000.0, day)
                  for n, day in ((1, "03-02"), (2, "03-09"), (3, "03-16"))], {}, False, id="ach-round"),
])
def test_r3_09_the_controls_stay_counted(rows, statement, zelle):
    no, yes = _settings(rows, **statement)
    assert yes == [COUNTED] * len(rows)
    assert no == [COUNTED] * len(rows)
    if zelle:
        assert all((record.revenue_tier, record.revenue_tier_reason) == ("non_revenue", "zelle_excluded")
                   for record in _dated(rows, **statement))


CHASE_BOOK = ("BOOK TRANSFER CREDIT B/O: SAMPLE MUTUAL INSURANCE CO CONTOSOVILLE ST 00000-0000 REF: {ref} "
              "TRN: 0000000000ES")


def test_r3_58_a_chase_book_transfer_s_ref_is_its_purpose():
    """Audit round 3, R3-B13 (R3-58; no code change): on Chase's BOOK TRANSFER CREDIT the REF field is the purpose,
    which _title_purpose_text does not read; the classifier's customer-payment wording, read on the row before its
    receiver fields, releases an insurer's commission there (the service form), and a number in REF holds."""
    [released] = _dated([(CHASE_BOOK.format(ref="AGENT COMMISSIONS"), 2000.0, "03-02")], bank="Chase")
    assert rules_reading(released) == COUNTED
    assert f"({GROUND_WORDS['service_form']})" in released.revenue_reason
    assert [rules_reading(record) for record in _dated([(CHASE_BOOK.format(ref="000000"), 2000.0, "03-02")],
                                                         bank="Chase")] == [HELD]


TRUCK_SALE = ("SAMPLE INSURANCE CO DES:TRUCK SALE ID:0001", 18000.0, "03-02")
ASSET_SALE = ("non_revenue", "asset_sale_proceeds")


@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # A released insurer's printed truck sale at an agency, a clinic and on the 3-in-31 ground: Q11 (b)'s non_revenue.
    pytest.param([TRUCK_SALE], {"holder": AGENCY}, [ASSET_SALE], id="agency"),
    pytest.param([TRUCK_SALE], {"holder": CLINIC}, [ASSET_SALE], id="clinic"),
    pytest.param([TRUCK_SALE, ("SAMPLE INSURANCE CO DES:PAYMENT ID:0002", 1234.0, "03-09"),
                  ("SAMPLE INSURANCE CO DES:PAYMENT ID:0003", 1290.5, "03-16")], {"holder": "NORTHWIND FLORIST LLC"},
                 [ASSET_SALE, COUNTED, COUNTED], id="three-in-31"),
    # A holder whose trade name is also dealer evidence (§17.1 asset-sale follow-up (1)) keeps its release.
    pytest.param([TRUCK_SALE], {"holder": REPAIR_COLLISION}, [COUNTED], id="collision-shop"),
    # Not released at a bakery: the insurer-name hold keeps it held.
    pytest.param([TRUCK_SALE], {}, [HELD], id="bakery"),
])
def test_r3_64_a_released_insurer_s_printed_asset_sale_is_read_by_q11_b(rows, statement, expected):
    """Audit round 3, R3-B13 (R3-64; no code change; Q11 (b) of 2026-10-02: "Don't count as true revenue and go
    straight to non-revenue"): an insurer-name hold keeps an insurer's printed asset sale held; a row the Q2 release
    re-states is read by Q11 (b), non_revenue at a non-dealer, and where the holder's trade name is dealer evidence it
    keeps its release."""
    assert [rules_reading(record) for record in _dated(rows, **statement)] == expected


# --- Audit round 3, R3-B16 --------------------------------------------------------------------------------------------
# R3-03 (owner ruling 2026-10-02, the underwriter's Q2; the MCA principle; standard A11, B6): a credit the Q2 release
# counted (an insurer paying for the business's work) is held by a debit naming its carrier only when that debit is
# circular money, is for the credit's own amount, or recurs at one amount printing no premium or retry word; a premium
# the business pays the carrier that pays it is an ordinary expense, never money going round. American Income Life
# joins INSURER_CREDIT_BRANDS (its agents' commissions print AM INCOME LIFE as the originator, no insurer word), so
# the release reads it. Fabricated holders, the public carriers by their names, 2054 dates, zeroed ids, and fabricated
# amounts (audit round 4, R4-42: no amount is a corpus amount).

AIL = ("ORIG CO NAME:AM INCOME LIFE ORIG ID:0000000001 DESC DATE:5403{dd} CO ENTRY DESCR:{entry} TRACE#:0000001 "
       "EED:5403{dd} IND ID:0000001 IND NAME:NORTHWIND PARTNERS")
AIL_HOLDER = {"holder": "NORTHWIND PARTNERS LLC", "bank": "Chase"}


def _ail(entry: str, amount: float, day: str):
    return AIL.format(dd=day[-2:], entry=entry), amount, day


AIL_CREDITS = [_ail("AIL INS SEC:PPD", amount, day)
               for amount, day in ((3120.45, "03-02"), (2980.10, "03-09"), (3410.00, "03-16"), (2875.30, "03-23"))]
AIL_PREMIUM = _ail("INS PREMSEC PPD", -171.09, "03-05")
NAVY_FEDERAL_AGENCY = {"holder": "NORTHWIND INSURANCE AGENCY LLC", "bank": "Navy Federal Credit Union"}
FARMERS_CREDITS = [("DEPOSIT ACH PAID FROM 0000 FARMERS INS 0000000", 12500.0, "03-02"),
                   ("DEPOSIT ACH PAID FROM 0000 FARMERS INS 0000000", 9800.0, "03-16")]
FARMERS_PREMIUM = ("PAID TO - FARMERS INS EFT PYMT CHK 0000000", -287.61, "03-10")
MANULIFE_CREDITS = [("INSURANCE MANULIFE", amount, day)
                    for amount, day in ((187.29, "03-02"), (120.40, "03-09"), (88.10, "03-16"))]
RBC_CLINIC = {"holder": CLINIC, "bank": "Royal Bank of Canada"}
HELD_ALSO = ("excluded_pending_review", "payer_also_debited")


@pytest.mark.parametrize(("rows", "statement", "ground"), [
    # A1: an agency's weekly commissions beside its own small premium to the carrier (today all held).
    pytest.param([*AIL_CREDITS, AIL_PREMIUM], AIL_HOLDER, "same_insurer_3_in_31_days", id="A1"),
    # A2: A1 without the premium (today counted named_payer_one_off: the brand was unread).
    pytest.param(AIL_CREDITS, AIL_HOLDER, "same_insurer_3_in_31_days", id="A2"),
    # A3: the premium recurring at one amount, the bank's retry of a returned premium and the premium re-presented.
    pytest.param([*AIL_CREDITS, AIL_PREMIUM, _ail("INS PREMSEC PPD", -171.09, "03-12"),
                  _ail("RETRY PYMT", -233.71, "03-13"), _ail("INS PREM", -233.71, "03-14")], AIL_HOLDER,
                 "same_insurer_3_in_31_days", id="A3"),
    # A4: a Farmers agency's credits beside one premium to Farmers (today both held).
    pytest.param([*FARMERS_CREDITS, FARMERS_PREMIUM], NAVY_FEDERAL_AGENCY, "holder_trade:insurance agency", id="A4"),
    # A5: a clinic's insurer payments beside one debit to another insurer the label key names (today held).
    pytest.param([*MANULIFE_CREDITS, ("INSURANCE SAMPLE MUTUAL", -318.47, "03-05")], RBC_CLINIC, "holder_trade:clinic",
                 id="A5"),
])
def test_r3_03_a_released_insurer_s_credits_are_counted_beside_its_premium(rows, statement, ground):
    records = _dated(rows, **statement)
    assert [rules_reading(record) for record in records] == [COUNTED] * len(records)
    for record in records:
        assert record.revenue_match_method == METHOD and not record.contributes_to_verified_revenue
        assert f"({GROUND_WORDS[ground]})" in record.revenue_reason
        assert "counted and flagged, never verified" in record.revenue_reason
    if statement is AIL_HOLDER:
        assert round(sum(record.amount for record in records if record.contributes_to_true_revenue), 2) == 12385.85


@pytest.mark.parametrize(("rows", "statement", "expected"), [
    # A debit naming the carrier that recurs at one amount and prints no premium or retry word still holds.
    pytest.param([*AIL_CREDITS, AIL_PREMIUM, _ail("AGENT DEBIT", -250.0, "03-10"),
                  _ail("AGENT DEBIT", -250.0, "03-24")], AIL_HOLDER, [HELD_ALSO] * 4, id="recurring-agent-debit"),
    # Circular money to the carrier still holds.
    pytest.param([*AIL_CREDITS, AIL_PREMIUM, ("ONLINE TRANSFER TO AM INCOME LIFE REF 0001", -500.0, "03-10")],
                 AIL_HOLDER, [HELD_ALSO] * 4, id="transfer"),
    # A premium for a credit's own amount holds that credit only.
    pytest.param([*AIL_CREDITS, AIL_PREMIUM, _ail("INS PREM", -2980.10, "03-10")], AIL_HOLDER,
                 [COUNTED, HELD_ALSO, COUNTED, COUNTED], id="own-amount"),
    # The Farmers debit printed twice at one amount, with no premium or retry word.
    pytest.param([*FARMERS_CREDITS, FARMERS_PREMIUM, (FARMERS_PREMIUM[0], FARMERS_PREMIUM[1], "03-24")],
                 NAVY_FEDERAL_AGENCY, [HELD_ALSO] * 2, id="recurring-eft"),
    # Two American Income Life credits at a holder with no trade word, no debit: R2-OW07's I26 default (held as an
    # insurer's, with the owner) now reaches the brand.
    pytest.param([AIL_CREDITS[0], _ail("AIL INS SEC:PPD", 2980.10, "03-20")], AIL_HOLDER,
                 [("excluded_pending_review", "insurer_named_payer")] * 2, id="two-ail-credits"),
])
def test_r3_03_the_holds_that_stay(rows, statement, expected):
    assert [rules_reading(record) for record in _dated(rows, **statement)] == expected


def test_r3_03_the_unreleased_insurer_beside_its_premium_and_the_kind_pins_are_unchanged():
    """§20 B4 (c): an insurer's credit the release does not count stays held beside its premium or bill (insurers never
    count); the premium is a flag, never a debit kind."""
    for debit in ("FABRIKAM LIFE DES:INS PREM ID:2 INDN:CONTOSO BAKERY LLC CO ID:1 PPD",
                  "FABRIKAM LIFE DES:AUTOPAY ID:2 INDN:CONTOSO BAKERY LLC CO ID:1 PPD", "BILL PAY FABRIKAM LIFE"):
        rows = [("FABRIKAM LIFE DES:FL INS ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 PPD", 1500.0, "03-02"),
                (debit, -105.0, "03-03")]
        assert [rules_reading(record) for record in _dated(rows)] == [HELD_ALSO]
    assert true_revenue._counter_debit_kind("FABRIKAM LIFE DES:INS PREM ID:2") == "other"
    # T18 and T18b: a one-off AUTOPAY to the carrier is counted; a debit for the credit's own amount holds it.
    drp = ("STATE FARM DES:DRP PAYMENT ID:1", 3000.0, "03-02")
    assert [rules_reading(record) for record in _dated([drp, ("STATE FARM DES:AUTOPAY ID:9", -412.18, "03-03")],
                                                        holder=REPAIR_SHOP)] == [COUNTED]
    assert [rules_reading(record) for record in _dated([drp, ("STATE FARM DES:AUTOPAY ID:9", -3000.0, "03-03")],
                                                        holder=REPAIR_SHOP)] == [HELD_ALSO]


def test_r3_03_american_income_life_is_a_credit_only_brand():
    """The brand reads the payer region only (never the entry's AIL INS), is no insurance-registry carrier and no §15
    deferred payer."""
    assert registry.INSURER_CREDIT_BRANDS["American Income Life"] == (r"AM(?:ERICAN)? INCOME LIFE",)
    assert "American Income Life" not in registry.INSURANCE_PROVIDER_ALIASES
    assert true_revenue._SECTION_15_DEFERRED_PAYERS.search("AMERICAN INCOME LIFE") is None
    record = _dated([AIL_CREDITS[0]], **AIL_HOLDER)[0]
    row = revenue_text(record.normalized_description)
    assert insurer_credit_brand(payer_region(row)) == "American Income Life"
    assert insurer_credit_brand(entry_fields(row)) is None


# --- Audit round 3, R3-B17 --------------------------------------------------------------------------------------------
# R3-77 (owner ruling 2026-10-02, the underwriter's Q2: insurer payments for the business's work count; standard A9;
# the hold's purpose, B6): RBC prints its posting-type label INSURANCE before the party on credits and debits alike, and
# the bank's own label names no party, so a clinic's insurer payments are compared with its debits by the insurer's own
# name: a debit to another insurer the label alone named no longer holds them, and a premium to the same insurer
# still names it. Fabricated holder (the file's CLINIC), public carriers by their names, 2054 dates, and fabricated
# amounts (audit round 4, R4-42: no amount is a corpus amount).

SAMPLE_MUTUAL = "INSURANCE SAMPLE MUTUAL"


@pytest.mark.parametrize(("debits", "expected"), [
    # Another insurer's debit for the second credit's own amount (today that credit is held: legacy INSURANCE).
    pytest.param([(SAMPLE_MUTUAL, -120.40, "03-10")], [COUNTED] * 3, id="own-amount-another-insurer"),
    # Another insurer's debit recurring at one amount, no premium word (today all three are held).
    pytest.param([(SAMPLE_MUTUAL, -318.47, "03-04"), (SAMPLE_MUTUAL, -318.47, "03-11")], [COUNTED] * 3,
                 id="recurring-another-insurer"),
    # Controls: the same insurer's debits still name it (key MANULIFE), as today.
    pytest.param([("INSURANCE MANULIFE GRP", -120.40, "03-10")], [COUNTED, HELD_ALSO, COUNTED],
                 id="own-amount-same-insurer"),
    pytest.param([("INSURANCE MANULIFE GRP", -318.47, "03-04"), ("INSURANCE MANULIFE GRP", -318.47, "03-11")],
                 [HELD_ALSO] * 3, id="recurring-same-insurer"),
])
def test_r3_77_rbc_s_insurance_label_never_names_the_insurer(debits, expected):
    records = _dated([*MANULIFE_CREDITS, *debits], **RBC_CLINIC)
    assert [rules_reading(record) for record in records] == expected
    assert {record.revenue_match_method for record in records} == {METHOD}


@pytest.mark.parametrize("bank", ["RBC", "Banque Royale du Canada"])
def test_r3_77_every_rbc_bank_field_reads_the_label(bank):
    rows = [*MANULIFE_CREDITS, (SAMPLE_MUTUAL, -318.47, "03-04"), (SAMPLE_MUTUAL, -318.47, "03-11")]
    assert [rules_reading(record) for record in _dated(rows, holder=CLINIC, bank=bank)] == [COUNTED] * 3


def test_r3_77_another_rbc_label_names_no_payer_either():
    # RBC's EQUIPMENT RENT label on a customer's credit and on another company's debits (today held by the key
    # EQUIPMENT): the credit reads as without the debits.
    credit = [("EQUIPMENT RENT FABRIKAM", 1500.0, "03-02")]
    debits = [("EQUIPMENT RENT CONTOSO LEASING", -50.0, "03-04"), ("EQUIPMENT RENT CONTOSO LEASING", -50.0, "03-11")]
    with_debits = [rules_reading(record) for record in _dated([*credit, *debits], **RBC_CLINIC)]
    assert with_debits == [rules_reading(record) for record in _dated(credit, **RBC_CLINIC)]
    assert with_debits[0][0] == "counted_flagged" and with_debits[0] != HELD_ALSO
