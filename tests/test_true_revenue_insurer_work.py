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
    # (b) A government payer: never by the widened spellings or the brands; by the spelled-out words or CLAIM (the
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
    # (c) A listed insurer's credit: the registry's entity; a premium financier none.
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
])
def test_the_insurer_spellings_read(text):
    assert true_revenue._INSURER_SPELLINGS.search(text)


@pytest.mark.parametrize("text", [
    "ASSURED STAFFING LLC", "P AND C FOODS", "SAMPLE ASSURE", "SAMPLE INSTALLATIONS", "SAMPLE CLM", "SAMPLE CLMS",
    "SAMPLE CLMEFT", "SAMPLE MUTUAL", "SAMPLE ASSURANCE", "SAMPLE LOSS PREVENTION",
    # R2-OW07 review round 1: the given name SUBROTO is no subrogation, nor INSTALLATIONS an insurer word after P & C.
    "SUBROTO SAMPLE", "SAMPLE SUBROTO", "NORTHWIND P & C INSTALLATIONS", "NORTHWIND P AND C INSPECTIONS",
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


def _dated(rows, *, holder: str = BAKERY, bank: str | None = None):
    """A statement of (text, amount, 'MM-DD') rows in 2054, every credit's record."""
    return [record for record in classify_statement_transactions(Statement(account_name=holder, bank=bank,
            transactions=[Transaction(date=f"2054-{day}", description=text, amount=amount,
                                      direction="credit" if amount > 0 else "debit")
                          for text, amount, day in rows])) if record.amount > 0]


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
    # T32: a wire's REF field ('REF COMM BANK NYC', the sending bank) is never a service form.
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
        else:
            assert record.revenue_tier_reason not in {"insurer_named_payer", "insurer_payer"}
            assert record.revenue_review_required is True


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
