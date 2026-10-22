"""Audit fix batch B8 (true revenue spec §6.3, §7.0, §8.1, §8.2, §15, §20): non-operating money and statement
boilerplate. Gambling and prediction-market payouts and a crypto exchange's or a retail brokerage's withdrawal are no
money the business earned from its operations (the MCA principle of 2026-09-30, the standing owner-money rule): held
(I28); an HSA distribution and a life insurer's annuity are personal income (I28); a lawsuit's, a class action's or a
claims administrator's settlement, and a law firm's settlement proceeds, are held, while a bare SETTLEMENT stays
counted (I44); a settlement or closing agent's payment is a title firm's (I44); equipment-auction and car-buyer seller
payouts are §15's deferred sources, counted and never verified (I45, OQ4); statement furniture a parser glued onto a
row is cut before classification (I46), and the plural TRANSFERS is transfer wording (I46, Q2); a glued Canada Carbon
Rebate is held (I56, GOV); and the GOV follow-ups: the IRS's interest on a refund is non_revenue, RBC's cut provincial
payment code is a personal benefit (class B). Audit round 2, R2-B10 (R21): Zions' legal-name footer before a page
counter and Navy Federal's page header are furniture too, and the cut's recorded residual is pinned. Audit round 2, R2-B12 (R37, R36): the B8 readers spare a customer's trade
name, an accounts-payable or vendor DISB and a processor's or a carrier's settlement services, and the gambling reader
reads a lottery's prize entry, the unlisted sportsbooks and a betting payer's withdrawal or payout. Fabricated rows
only, in the banks' printed formats; public names only where a bank prints its own or a registry lists them (sportsbooks, prediction markets, crypto exchanges, brokerages,
claims administrators, auctioneers and car buyers, each public)."""
from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from analysis import true_revenue as tr
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions
from analysis.descriptor.lexical import revenue_text
from analysis.description_text import normalize_transaction_description
from tests.zelle_reading import rules_reading

HOLDER = "NORTHWIND BAKERY LLC"

NON_SALE = ("excluded_pending_review", "non_sale_purpose")
PERSONAL = ("excluded_pending_review", "personal_income")
FINANCING = ("excluded_pending_review", "financing_named_payer")
NO_COUNTERPARTY = ("excluded_pending_review", "transfer_no_counterparty")
NON_REVENUE = ("non_revenue", "strong_non_revenue_rule")
P2P = ("counted_flagged", "p2p")
CHECK = ("counted_flagged", "check_deposit")
NO_PAYER = ("counted_flagged", "no_payer_printed")
UNLABELLED = ("counted_flagged", "named_payer_unlabelled")
ONE_OFF = ("counted_flagged", "named_payer_one_off")
REFUSED = ("counted_flagged", "named_payer_purpose_refused")
WIRE = ("counted_flagged", "wire_named_sender")
REPEATS = ("verified", "named_payer_repeats")
COMPANY = ("verified", "named_payer_company_form")
REMITTANCE = ("verified", "payer_remittance_descriptor")

#: Bank of America's incoming-ACH layout, with the holder in the receiver field.
BOFA = "{payer} DES:{entry} ID:{ref} INDN:NORTHWIND BAKERY LLC CO ID:1234567890 {sec}"


def _bofa(payer: str, entry: str, ref: str = "1234567", sec: str = "CCD") -> str:
    return BOFA.format(payer=payer, entry=entry, ref=ref, sec=sec)


def _records(rows, *, holder: str | None = HOLDER, bank: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _tiers(rows, **kwargs):
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): a Zelle deposit is read through the rules' own reading,
    # its final tier (non_revenue, zelle_excluded) asserted (tests/zelle_reading.py, R2-OW02 CR7).
    return [rules_reading(record, method=True)
            for record in _records(rows, **kwargs) if record.amount > 0]


def _one(text: str, amount: float = 1200.0, **kwargs):
    return _tiers([(text, amount)], **kwargs)[0]


def _in_true(tier) -> bool:
    return tier[0] in ("counted_flagged", "verified")


# I28: gambling and prediction-market payouts are held, never counted or verified.

@pytest.mark.parametrize(("text", "bank"), [
    (_bofa("DRAFTKINGS INC", "WITHDRAWAL"), "Bank of America"),
    ("MONEY TRANSFER AUTHORIZED ON 01 02 FROM CROWN GAMING INC CROWN GAMING MA S123456789012345 CARD 1234",
     "Wells Fargo"),
    ("MONEY TRANSFER AUTHORIZED ON 01 02 FROM CROWN NJ GAMING INC S123456789012345 CARD 1234", "Wells Fargo"),
    ("VISA MONEY TRANSFER C DRAFTKINGS 12345678901234567890 VISA DIRECT FL", "PNC Bank"),
    ("INSTANT PMT FROM PRIZEPICKS VIA AEROPAY PRIZEPICKS ON 01 02 REF 20540102ABCDEF", "Wells Fargo"),
    ("VISA TRANSFER AUT 010254 VISA TRANSFER KALSHI KLEAR LLC NEW YORK NY 1234123412341234", "TD Bank"),
    ("PAYMENT RECEIVED 01 02 KALSHI KLEAR LLC NEW YORK NY CARD 1234", "Chase"),
    (_bofa("FANDUEL INC", "WITHDRAWAL"), "Bank of America"),
    (_bofa("BETMGM LLC", "PAYOUT"), "Bank of America"),
    (_bofa("CAESARS SPORTSBOOK", "WITHDRAWAL"), "Bank of America"),
    (_bofa("FANATICS BETTING AND GAMING", "WITHDRAWAL"), "Bank of America"),
    (_bofa("ESPN BET", "WITHDRAWAL"), "Bank of America"),
    (_bofa("BET365", "WITHDRAWAL"), "Bank of America"),
    (_bofa("BETRIVERS", "WITHDRAWAL"), "Bank of America"),
    (_bofa("UNDERDOG SPORTS INC", "WITHDRAWAL"), "Bank of America"),
    (_bofa("POLYMARKET", "WITHDRAWAL"), "Bank of America"),
    (_bofa("CHUMBA CASINO", "REDEMPTION"), "Bank of America"),
    (_bofa("PULSZ", "REDEMPTION"), "Bank of America"),
    (_bofa("SAMPLE CASINO", "JACKPOT"), "Bank of America"),
    (_bofa("SAMPLE RACEWAY", "WINNINGS"), "Bank of America"),
    ("ACH CREDIT STATE LOTTERY PRIZE PAYMENT 12345", "Wells Fargo"),
])
def test_a_gambling_or_prediction_market_payout_is_held(text, bank):
    assert _one(text, 900.0, bank=bank) == NON_SALE


def test_a_repeated_sportsbook_or_prediction_market_withdrawal_is_never_verified():
    # Q6 verified two withdrawals from one payer as a repeat; a payout of winnings is no payer of the business.
    for payer in ("KALSHI", "FANDUEL"):
        rows = [(_bofa(payer, "WITHDRAWAL", "1234567"), 500.0), (_bofa(payer, "WITHDRAWAL", "7654321"), 700.0)]
        assert _tiers(rows, bank="Bank of America") == [NON_SALE, NON_SALE]


@pytest.mark.parametrize(("text", "bank", "expected"), [
    # A sportsbook or casino paying a vendor from its payables is the vendor's revenue (§7.5's accounts-payable
    # wording, or a vendor or invoice word), and a casino company's own name holds nothing.
    (_bofa("DRAFTKINGS", "AP PAYMENT"), "Bank of America", REMITTANCE),
    ("CAESARS ENT EDI ACH IN", "Mercury", ONE_OFF),
    (_bofa("FANDUEL INC", "VENDOR PMT"), "Bank of America", None),
    (_bofa("CONTOSO CASINO", "INVOICE 1234"), "Bank of America", None),
    # A lottery's settlement with its retailer (the store sells tickets and cashes prizes) is no prize, even beside a
    # prize word.
    (_bofa("NY LOTTERY", "SETTLEMENT"), "Bank of America", REFUSED),
    (_bofa("STATE LOTTERY", "RETAILER WINNINGS SETTLEMENT"), "Bank of America", None),
    (_bofa("STATE LOTTERY", "COMMISSION"), "Bank of America", None),
    # A business named with a word a gambling payer also prints is a payer.
    (_bofa("FABRIKAM UNDERDOG BAKERY LLC", "PAYMENT"), "Bank of America", COMPANY),
    (_bofa("FANATICS RETAIL GROUP", "PAYMENT"), "Bank of America", None),
    (_bofa("FABRIKAM JACKPOTS LLC", "PAYMENT"), "Bank of America", COMPANY),
])
def test_a_gambling_name_s_vendor_payment_or_a_lottery_retailer_s_settlement_keeps_its_reading(text, bank, expected):
    tier = _one(text, 900.0, bank=bank)
    assert tier != NON_SALE and _in_true(tier)
    if expected is not None:
        assert tier == expected


def test_a_sportsbook_refund_of_a_wager_stays_non_revenue():
    # The reversal rule runs first: a card purchase returned by a sportsbook never enters True.
    assert _one("PURCHASE RETURN AUTHORIZED ON 01 02 DK DRAFTKINGS 1234567890 MA S123456789012345 CARD 1234",
                75.0, bank="Wells Fargo")[0] == "non_revenue"


# I28: a crypto exchange's or a retail brokerage's withdrawal is the owner's own money (the standing rule).

@pytest.mark.parametrize(("text", "bank"), [
    ("WT FED 01234 SAMPLE BANK ORG SAMPLEBANK FBO PAYWARD INTERACTIVE SRF 2054010200000 TRN 540102000001 RFB AB12",
     "Wells Fargo"),
    ("FUNDS TRANSFER WIRE FROM COINBA SE INC JAN 02", "Citibank"),
    (_bofa("KRAKEN", "WITHDRAWAL"), "Bank of America"),
    (_bofa("PAYWARD INC", "WITHDRAWAL"), "Bank of America"),
    (_bofa("BAM TRADING SERVICES BINANCE US", "WITHDRAWAL", sec="PPD"), "Bank of America"),
    (_bofa("BINANCE US", "WITHDRAWAL"), "Bank of America"),
    (_bofa("BITSTAMP USA INC", "WITHDRAWAL"), "Bank of America"),
    (_bofa("UPHOLD HQ INC", "WITHDRAWAL"), "Bank of America"),
    (_bofa("BLOCKFI", "WITHDRAWAL"), "Bank of America"),
    (_bofa("BAKKT", "WITHDRAWAL"), "Bank of America"),
    (_bofa("PAXOS TRUST CO", "WITHDRAWAL"), "Bank of America"),
    (_bofa("APEX CLEARING", "ACH TRANSFER", sec="PPD"), "Bank of America"),
    ("ACH DEPOSIT FIDELITY 12345 P FIDELITY 12345 XXXXX1234", "TD Bank"),
    # Already held: the whole spelling.
    ("FUNDS TRANSFER WIRE FROM COINBASE INC JAN 02", "Citibank"),
])
def test_a_crypto_exchange_or_retail_brokerage_withdrawal_is_owner_money(text, bank):
    assert _one(text, 4000.0, bank=bank) == NON_SALE


def test_m1_finance_is_held_as_financing_first():
    # M1 FINANCE carries a financing root, which §8.10's order reads before owner money: held either way.
    assert _one(_bofa("M1 FINANCE LLC", "WITHDRAWAL"), 4000.0, bank="Bank of America") == FINANCING


@pytest.mark.parametrize(("text", "bank"), [
    # A custodian's or a private bank's transfer pays out on its client's instruction: a parent paying a school's
    # tuition from a brokerage account is a customer (never added, the brief's ruling).
    ("ORIG CO NAME BNY MELLON NA ORIG ID 1234567890 DESC DATE 010254 CO ENTRY DESCR TRANSFER SEC PPD TRACE"
     " 123456789012345 EED 540102 IND ID 12345", "Chase"),
    ("ORIG CO NAME NORTHERN TRUST ORIG ID 0000000001 DESC DATE 540102 CO ENTRY DESCR TRANSFER SEC CCD TRACE"
     " 123456789012345 EED 540102 IND ID SCAN", "Chase"),
    ("FEDWIRE CREDIT VIA NORTHERN TRUST COMPANY THE 123456789 B O PAT Q SAMPLE SAMPLEVILLE IL 12345 REF CHASE NYC CTR",
     "Chase"),
    # A bare FIDELITY, and a title firm that holds the word, are no brokerage form.
    ("ACH DEPOSIT FIDELITY 12345 XXXXX1234", "TD Bank"),
])
def test_a_custodian_s_or_a_bare_fidelity_credit_is_not_owner_money(text, bank):
    tier = _one(text, 9000.0, bank=bank)
    assert tier != NON_SALE and _in_true(tier)


def test_the_owner_money_platforms_name_the_new_exchanges_and_no_custodian():
    found = tr._OWNER_MONEY_PLATFORMS
    for name in ("KRAKEN", "PAYWARD", "FBO PAYWARD INTERACTIVE", "BINANCE", "BAM TRADING", "BITSTAMP", "UPHOLD",
                 "BLOCKFI", "BAKKT", "PAXOS", "APEX CLEARING", "M1 FINANCE", "COINBA SE", "P FIDELITY"):
        assert found.search(name), name
    for name in ("BNY MELLON", "PERSHING", "NORTHERN TRUST", "FIDELITY", "FIDELITY NATIONAL TITLE", "BITPAY",
                 "SAMPLE KRAKENS LLC", "APEX CLEARANCE SALES", "COINBASED"):
        assert not found.search(name), name
    assert found.pattern == registry.OWNER_MONEY_PLATFORMS


# I28: a health savings account's distribution and a life insurer's annuity payment are personal income.

@pytest.mark.parametrize(("text", "bank"), [
    ("EXTERNAL DEPOSIT SAMPLE PAT HSADISTRIB TRACER 12345678901234", "Sample Credit Union"),
    ("EXTERNAL DEPOSIT SAMPLE PAT HSA DISTRIB TRACER 12345678901234", "Sample Credit Union"),
    (_bofa("SAMPLE HSA BANK", "HSA DISTRIBUTION", sec="PPD"), "Bank of America"),
    ("FABRIKAM LIFE AN DISBPYMT12 PPD ID 1234567890", "Chase"),
])
def test_an_hsa_distribution_or_a_cut_annuity_payment_is_personal_income(text, bank):
    assert _one(text, 300.0, bank=bank) == PERSONAL


@pytest.mark.parametrize("text", [
    _bofa("FABRIKAM LIFE AN", "PAYMENT"),
    _bofa("CONTOSO HSA SERVICES LLC", "INVOICE 1234"),
])
def test_a_name_that_holds_the_annuity_or_hsa_letters_is_no_personal_income(text):
    tier = _one(text, 300.0, bank="Bank of America")
    assert tier != PERSONAL and _in_true(tier)


# I44: a lawsuit's, a class action's or a claims administrator's settlement is held; a bare SETTLEMENT is not.

@pytest.mark.parametrize(("text", "bank"), [
    (_bofa("EPIQ CLASS ACTION", "SETTLEMENT", sec="PPD"), "Bank of America"),
    (_bofa("EPIQ SYSTEMS INC", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("JND LEGAL ADMINISTRATION LLC", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("KCC CLASS ACTION SERVICES", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("KCC LLC", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("ANGEION GROUP LLC", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("SIMPLURIS INC", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("RUST CONSULTING INC", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("KROLL SETTLEMENT ADMIN", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("A B DATA LTD", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("VERITA GLOBAL", "PAYMENT", sec="PPD"), "Bank of America"),
    (_bofa("FABRIKAM INC", "LAWSUIT SETTLEMENT"), "Bank of America"),
    (_bofa("FABRIKAM INC", "LITIGATION"), "Bank of America"),
    (_bofa("CONTOSO ADMINISTRATORS", "CLASS ACTION"), "Bank of America"),
    (_bofa("CONTOSO ADMIN SERVICES LLC", "SETTLEMENT ADMIN"), "Bank of America"),
    ("ZELLE PAYMENT FROM FABRIKAM DATA BREACH SETTLEMENT FOR YOUR FABRIKAM DATA BREACH SETTLEMENT PAYMENT CONF AB123",
     "Bank of America"),
    ("WT FED 01234 SAMPLE BANK ORG CONTOSO LAW GROUP IOLTA SRF 2054010200000 TRN 540102000001 RFB AB12 OBI SETTLEMENT"
     " PROCEEDS", "Wells Fargo"),
    (_bofa("CONTOSO LAW FIRM PLLC", "SETTLEMENT PROCEEDS"), "Bank of America"),
    (_bofa("PAT SAMPLE ESQ", "SETTLEMENT PROCEEDS", sec="PPD"), "Bank of America"),
])
def test_a_legal_settlement_or_a_claims_administrator_s_payout_is_held(text, bank):
    assert _one(text, 4000.0, bank=bank) == NON_SALE


def test_a_law_firm_s_settlement_funds_are_held():
    # FUNDS is a financing root too (§8.1, T4), whose hold §8.10's order reads first: held either way.
    assert _one(_bofa("CONTOSO LAW FIRM PLLC", "SETTLEMENT FUNDS"), 4000.0,
                bank="Bank of America")[0] == "excluded_pending_review"


@pytest.mark.parametrize(("text", "bank", "expected"), [
    # A bare SETTLEMENT is a processor's, a carrier's or an operating settlement (§8.6: counted, never verified).
    ("CONTRACTOR MGMT SETTLEMENT 1", "Wells Fargo", REFUSED),
    (_bofa("FABRIKAM MERCHANT SVCS", "SETTLEMENT"), "Bank of America", None),
    (_bofa("CONTOSO FREIGHT LLC", "SETTLEMENT"), "Bank of America", REFUSED),
    # A claims administrator or a law firm paying a vendor's invoice pays its vendor.
    (_bofa("EPIQ SYSTEMS INC", "VENDOR PMT"), "Bank of America", None),
    (_bofa("JND LEGAL ADMINISTRATION LLC", "INVOICE 1234"), "Bank of America", None),
    (_bofa("CONTOSO LAW GROUP", "PAYMENT"), "Bank of America", None),
])
def test_a_bare_settlement_or_an_administrator_s_vendor_payment_keeps_its_reading(text, bank, expected):
    tier = _one(text, 2500.0, bank=bank)
    assert tier != NON_SALE and _in_true(tier)
    if expected is not None:
        assert tier == expected


@pytest.mark.parametrize("text", [
    # A settlement or closing agent named without the word TITLE pays property-closing proceeds (A3's title firm).
    "WT FED 01234 SAMPLE BANK ORG FABRIKAM SETTLEMENT SERVICES INC SRF 2054010200000 TRN 540102000001 RFB AB12",
    "WT FED 01234 SAMPLE BANK ORG CONTOSO CLOSING SERVICES LLC SRF 2054010200000 TRN 540102000001 RFB AB12",
    _bofa("CONTOSO CLOSING SERVICES LLC", "PAYMENT"),
])
def test_a_settlement_or_closing_agent_is_a_title_firm(text):
    assert _one(text, 4000.0, bank="Wells Fargo") == NON_SALE


def test_a_settlement_agent_s_payment_of_the_holder_s_fee_keeps_its_reading():
    # A3's orchestrator ruling: a title firm's payment of the holder's own fee (a commission, an invoice) is counted.
    text = ("WT FED 01234 SAMPLE BANK ORG FABRIKAM SETTLEMENT SERVICES INC SRF 2054010200000 TRN 540102000001 RFB AB12"
            " OBI COMMISSION 1234")
    tier = _one(text, 4000.0, bank="Wells Fargo")
    assert tier != NON_SALE and _in_true(tier)


# I45 (OQ4) and the owner's ruling of 2026-10-02 (the underwriter's Q11 (b), "Don't count as true revenue and go straight
# to non-revenue"): on a statement that shows no dealer evidence, a non-dealer's sale of equipment or vehicles (an
# equipment auction's or a car buyer's seller payout, a printed TRUCK SALE, SALE OF or SOLD purpose, a vehicle's sale even
# when it cites an invoice) is non_revenue, method and reason asset_sale_proceeds, not held; a dealer's sales stay
# revenue. Before the ruling a seller payout was a §15 deferred source, counted and never verified.

ASSET_SALE = ("non_revenue", "asset_sale_proceeds")
SOLAR = "NORTHWIND SOLAR LLC"
FUEL_STOP = "NORTHWIND FUEL STOP LLC"
BROKERS = "NORTHWIND BROKERS LLC"


def test_a_repeated_equipment_auction_seller_payout_is_asset_sale_proceeds():
    rows = [(_bofa("RITCHIE BROS", "SELLER PMT", "1234567"), 15000.0),
            (_bofa("RITCHIE BROS", "SELLER PMT", "7654321"), 12000.0)]
    assert _tiers(rows, bank="Bank of America") == [ASSET_SALE, ASSET_SALE]


def _q11_bofa(payer: str, entry: str, holder: str = SOLAR, ref: str = "1234567") -> str:
    return f"{payer} DES:{entry} ID:{ref} INDN:{holder} CO ID:1234567890 CCD"


def _q11_chase(payer: str, entry: str, holder: str = SOLAR) -> str:
    return (f"ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:{entry} SEC:CCD "
            f"TRACE#:123456789012345 EED:540102 IND ID:1234 IND NAME:{holder} TRN: 1234567890TC")


def _q11_wire(orig: str, purpose: str) -> str:
    return ("WIRE TYPE:WIRE IN DATE: 540302 TIME:1200 ET TRN:2054030200012345 SEQ:123456/000001 ORIG:"
            f"{orig} ID:1234 SND BK:SAMPLE BANK ID:123456789 PMT DET:{purpose}")


def _q11_records(rows, holder: str = SOLAR):
    """One Bank of America month: a mobile deposit, then `rows`; the records of the credits after the deposit."""
    records = classify_statement_transactions(Statement(account_name=holder, bank="Bank of America", transactions=[
        Transaction(date="2054-03-01", description="MOBILE DEPOSIT", amount=500.0, direction="credit"),
        *(Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                      direction="credit" if amount > 0 else "debit")
          for index, (text, amount) in enumerate(rows)),
    ]))
    return [record for record in records[1:] if record.amount > 0]


def _q11(rows, holder: str = SOLAR):
    return [rules_reading(record, method=True) for record in _q11_records(rows, holder)]


@pytest.mark.parametrize(("rows", "holder", "arm"), [
    # B1: an equipment auction's seller payment, twice.
    ([(_q11_bofa("RITCHIE BROS", "SELLER PMT"), 15000.0),
      (_q11_bofa("RITCHIE BROS", "SELLER PMT", ref="7654321"), 12000.0)], SOLAR, "payer"),
    # B2: a car buyer's payout (was counted named_payer_purpose_refused).
    ([(_q11_bofa("CARVANA PAYOUT", "CVNA 12345"), 1850.0)], SOLAR, "payer"),
    # B3: a car buyer's company-form payment on Chase's layout (was Q6's verification: the declared demotion).
    ([(_q11_chase("CARVANA LLC", "PAYMENT"), 14000.0)], SOLAR, "payer"),
    # B4, B5, B6: a printed equipment or vehicle sale (B5 was Q6's company-form verification).
    ([(_q11_wire("FABRIKAM PAVING LLC", "USED EQUIPMENT SALE"), 27000.0)], SOLAR, "purpose"),
    ([(_q11_bofa("FABRIKAM FREIGHT LLC", "TRUCK SALE"), 18000.0)], SOLAR, "purpose"),
    ([(_q11_wire("FABRIKAM FREIGHT LLC", "SALE OF 2019 TRAILER"), 8000.0)], SOLAR, "purpose"),
    # B7: Copart's seller payment (its seller word).
    ([(_q11_bofa("COPART INC", "SELLER PMT"), 3000.0)], SOLAR, "payer"),
    # B8: IAA's seller payment, held before by the insurer-name hold (its INSURANCE is the auction's name).
    ([(_q11_bofa("INSURANCE AUTO AUCTIONS", "SELLER PMT"), 3000.0)], SOLAR, "payer"),
    # B9: a person's e-Transfer for a truck (no Zelle).
    ([("INTERAC E-TRANSFER FROM PAT SAMPLE TRUCK SALE", 6500.0)], SOLAR, "purpose"),
    # B10: a trucking holder's auction seller payout (a seller word, whatever the holder's trade).
    ([(_q11_bofa("RITCHIE BROS AUCTIONEERS", "SELLER PAYOUT", holder="NORTHWIND TRUCKING LLC"), 60000.0)],
     "NORTHWIND TRUCKING LLC", "payer"),
    # B11: the ruling's own example, a bare row.
    ([("CARVANA PAYMENT", 9000.0)], SOLAR, "payer"),
    # D13, I1: a vehicle's sale citing an invoice, which an invoice descriptor verified (D13: the declared demotion).
    ([(_q11_wire("FABRIKAM FARMS LLC", "TRACTOR SALE INV 1234"), 9000.0)], SOLAR, "purpose"),
    ([(_q11_wire("CONTOSO LANDSCAPING LLC", "TRUCK SALE INV 4521"), 9000.0)], SOLAR, "purpose"),
    # Q2: SOLD before a model year and a make.
    ([(_q11_wire("PAT SAMPLE", "SOLD 2019 FORD TRUCK"), 9000.0)], SOLAR, "purpose"),
    # S2, L2, T1: a bare SUPPLY, RENTALS or FLEET in the holder's name is no trade name (S2 was Q6's verification).
    ([(_q11_bofa("FABRIKAM FREIGHT LLC", "TRUCK SALE", holder="NORTHWIND OFFICE SUPPLY LLC"), 9000.0)],
     "NORTHWIND OFFICE SUPPLY LLC", "purpose"),
    ([(_q11_bofa("FABRIKAM FREIGHT LLC", "TRUCK SALE", holder="NORTHWIND PARTY RENTALS LLC"), 9000.0)],
     "NORTHWIND PARTY RENTALS LLC", "purpose"),
    ([(_q11_bofa("FABRIKAM FREIGHT LLC", "TRUCK SALE", holder="NORTHWIND FLEET SERVICES LLC"), 9000.0)],
     "NORTHWIND FLEET SERVICES LLC", "purpose"),
    # W3: a towing holder's Copart seller payment (a towing service is a platform's vendor, no dealer).
    ([(_q11_bofa("COPART INC", "SELLER PMT", holder="NORTHWIND TOWING LLC"), 3000.0)], "NORTHWIND TOWING LLC", "payer"),
    # T2, T5: a bare SALES or SUPPLY in the holder's name.
    ([(_q11_bofa("CARVANA", "PAYMENT", holder="NORTHWIND SALES & MARKETING LLC"), 9000.0)],
     "NORTHWIND SALES & MARKETING LLC", "payer"),
    ([(_q11_bofa("RITCHIE BROS", "SELLER PAYOUT", holder="NORTHWIND OFFICE SUPPLY LLC"), 9000.0)],
     "NORTHWIND OFFICE SUPPLY LLC", "payer"),
    # A vehicle-trade holder name that prints a recovery word is no dealer (R2-OW05's _DEALER_HOLDER_VETO).
    ([(_q11_bofa("COPART INC", "SELLER PMT", holder="SAMPLE AUTOMOTIVE RECOVERY LLC"), 3000.0)],
     "SAMPLE AUTOMOTIVE RECOVERY LLC", "payer"),
    # Review round 1: FLEET alone is no asset noun, but a fleet's vehicles or trucks still are.
    ([(_q11_wire("CONTOSO LLC", "SALE OF FLEET VEHICLES"), 9000.0)], SOLAR, "purpose"),
    ([(_q11_wire("CONTOSO LLC", "FLEET TRUCK SALE"), 9000.0)], SOLAR, "purpose"),
    # Review round 1: a fee printed apart from the sale leaves the row a sale's proceeds.
    ([(_q11_wire("FABRIKAM FREIGHT LLC", "TRUCK SALE NET OF FEES"), 9000.0)], SOLAR, "purpose"),
])
def test_a_non_dealer_s_asset_sale_is_non_revenue(rows, holder, arm):
    records = _q11_records(rows, holder)
    assert [rules_reading(record, method=True) for record in records] == [ASSET_SALE] * len(records)
    for record in records:
        assert record.revenue_classification == "non_revenue"
        assert record.revenue_match_method == tr.ASSET_SALE_METHOD == "asset_sale_proceeds"
        assert record.revenue_matched_rule == f"asset_sale_{arm}"
        assert record.revenue_tier_reason == "asset_sale_proceeds" and record.revenue_confidence_score == 0.90
        assert not record.revenue_review_required and not record.contributes_to_true_revenue
        assert record.contributes_to_non_revenue and "asset_sale_proceeds" in record.revenue_context_signals
        assert "Q11" in record.revenue_reason


def test_an_invoice_verified_vehicle_sale_names_the_rule_it_overrules():
    # D13: an invoice descriptor verified it; pass 7 overrules that verification.
    record, = _q11_records([(_q11_wire("FABRIKAM FARMS LLC", "TRACTOR SALE INV 1234"), 9000.0)])
    assert (record.revenue_tier, record.revenue_tier_reason) == ASSET_SALE
    assert "payer_remittance_descriptor" in record.revenue_reason


def test_a_payables_only_lender_credit_is_no_dealer_evidence_for_an_asset_sale():
    # R2-OW05: a listed auto lender's payables-only credit is no dealer evidence, so a car buyer's payout beside it
    # is still asset-sale proceeds.
    records = _q11_records([(_q11_bofa("WESTLAKE FINANCI", "PAYABLES"), 4000.0),
                            (_q11_bofa("CARVANA PAYOUT", "CVNA 12345"), 1850.0)])
    assert rules_reading(records[1], method=True) == ASSET_SALE


@pytest.mark.parametrize(("rows", "holder", "expected"), [
    # D1: a dealer by its name.
    ([(_q11_chase("CARVANA LLC", "PAYMENT", holder="NORTHWIND AUTO SALES LLC"), 14000.0)], "NORTHWIND AUTO SALES LLC",
     [COMPANY]),
    # D2: Q7 dealer funding beside an auction seller payment.
    ([(_q11_bofa("WESTLAKE FINANCIAL", "DEALER PMT"), 20000.0), (_q11_bofa("RITCHIE BROS", "SELLER PMT"), 15000.0)],
     SOLAR, [("verified", "auto_lender_dealer_funding"), REFUSED]),
    # D3: a floor-plan financier's debit.
    ([("NEXTGEAR CAPITAL DES:PAYOFF ID:1 CO ID:1 CCD", -5000.0), (_q11_bofa("FABRIKAM FREIGHT LLC", "TRUCK SALE"), 18000.0)],
     SOLAR, [COMPANY]),
    # D4: a dealer-only wholesale auction's payout credit (§7.8).
    ([("ACV AUCTIONS INC PAYMENTS 123456 12 123456789012", 4000.0), (_q11_bofa("CARVANA PAYOUT", "CVNA 12345"), 1850.0)],
     SOLAR, [("verified", "wholesale_auction_payout_form"), REFUSED]),
    # D5: a platform's vendor payment; D6, D7, D8: a transporter's or a hauler's fee.
    ([(_q11_bofa("CARVANA LLC", "VENDOR PAY"), 9000.0)], SOLAR, [REMITTANCE]),
    ([(_q11_chase("CARVANA LLC", "PAYMENT", holder="NORTHWIND AUTO TRANSPORT LLC"), 9000.0)],
     "NORTHWIND AUTO TRANSPORT LLC", [COMPANY]),
    ([(_q11_bofa("RITCHIE BROS AUCTIONEERS", "TRANSPORT PMT"), 9000.0)], SOLAR, [REFUSED]),
    ([(_q11_bofa("RITCHIE BROS AUCTIONEERS", "PAYMENT", holder="NORTHWIND TRUCKING LLC"), 9000.0)],
     "NORTHWIND TRUCKING LLC", [REFUSED]),
    # D9, D22: lookalike names (a longer name is another payer).
    ([(_q11_bofa("VROOM DELIVERY LLC", "PAYMENT"), 9000.0)], SOLAR, [REFUSED]),
    ([(_q11_bofa("CARMAX BUSINESS SERVICES LLC", "PAYMENT"), 9000.0)], SOLAR, [REFUSED]),
    # D10: CarMax Auto Finance's dealer funding.
    ([(_q11_bofa("CARMAX AUTO FINANCE", "DEALER PMT", holder="NORTHWIND MOTORS LLC"), 20000.0)],
     "NORTHWIND MOTORS LLC", [("verified", "auto_lender_dealer_funding")]),
    # D11: a payer whose own name holds the words; D12: SALES (plural).
    ([(_q11_bofa("CONTOSO TRUCK SALE AND SERVICE INC", "PAYMENT"), 9000.0)], SOLAR, [COMPANY]),
    ([(_q11_bofa("FABRIKAM HAULING LLC", "TRUCK SALES"), 9000.0)], SOLAR, [COMPANY]),
    # D15: a return; D16: Copart with no seller word; D17: a wire with no sender (Q1's hold wins).
    ([("RETURN FOR CARVANA LLC PURCHASE C ST A1B2C3D4E5F6", 4500.0)], SOLAR,
     [("excluded_pending_review", "possible_return")]),
    ([(_q11_bofa("COPART INC", "PAYMENT"), 3000.0)], SOLAR, [COMPANY]),
    ([("WIRE TYPE:WIRE IN DATE: 540302 TIME:1200 ET TRN:2054030200012345 SEQ:123456/000001 PMT DET:TRUCK SALE",
       20000.0)], SOLAR, [("excluded_pending_review", "wire_no_sender")]),
    # D18: the strong non-revenue rule's EQUIPMENT SALE PROCEEDS keeps its rule; D19: COST OF GOODS SOLD.
    ([(_q11_bofa("FABRIKAM PAVING LLC", "EQUIPMENT SALE PROCEEDS"), 20000.0)], SOLAR,
     [("non_revenue", "strong_non_revenue_rule")]),
    ([(_q11_wire("FABRIKAM RETAIL LLC", "COST OF GOODS SOLD"), 9000.0)], SOLAR, [WIRE]),
    # D20: a supplier's customer buying generic equipment.
    ([(_q11_bofa("FABRIKAM DINER LLC", "EQUIPMENT SALE", holder="NORTHWIND RESTAURANT SUPPLY LLC"), 9000.0)],
     "NORTHWIND RESTAURANT SUPPLY LLC", [REFUSED]),
    # D21: a person's repeated round sums (Q4's hold wins).
    ([("INTERAC E-TRANSFER FROM PAT SAMPLE TRUCK SALE", 5000.0),
      ("INTERAC E-TRANSFER FROM PAT SAMPLE TRUCK SALE", 5000.0)], SOLAR,
     [("excluded_pending_review", "p2p_round_repeat")] * 2),
    # R1, R3, R4: a purchase at a dealer-only wholesale auction (a posted debit) is dealer evidence.
    ([("MANHEIM US DES:ACH PAYMNT ID:1 CO ID:1 CCD", -4000.0), (_q11_bofa("CARVANA PAYOUT", "CVNA 12345"), 1850.0)],
     SOLAR, [REFUSED]),
    ([("ACV AUCTIONS INC DES:PAYMENTS ID:1 CO ID:1 CCD", -3000.0), (_q11_bofa("FABRIKAM FREIGHT LLC", "TRUCK SALE"), 18000.0)],
     SOLAR, [COMPANY]),
    ([("OPENLANE INC DES:OPENLANE ID:1 CO ID:1 CCD", -3500.0), (_q11_bofa("RITCHIE BROS", "SELLER PMT"), 15000.0)],
     SOLAR, [REFUSED]),
    # I2: generic equipment keeps the invoice veto; I3, I4: vendor and accounts-payable wording spare a vehicle's sale.
    ([(_q11_wire("CONTOSO LLC", "EQUIPMENT SALE PMT INV 88"), 9000.0)], SOLAR, [REFUSED]),
    ([(_q11_bofa("FABRIKAM FREIGHT LLC", "VENDOR PAY TRUCK SALE"), 9000.0)], SOLAR, [REMITTANCE]),
    ([(_q11_bofa("FABRIKAM FREIGHT LLC", "A P PMT TRUCK SALE"), 9000.0)], SOLAR, [REMITTANCE]),
    # L1, L3, M1, T4: a lessor's, a truck-rental fleet's, a marina's and an equipment-rental fleet's sales are its trade.
    ([(_q11_wire("PAT SAMPLE", "VEHICLE SALE"), 9000.0)], "NORTHWIND LEASING LLC", [WIRE]),
    ([(_q11_bofa("FABRIKAM FREIGHT LLC", "TRUCK SALE", holder="NORTHWIND TRUCK RENTAL LLC"), 9000.0)],
     "NORTHWIND TRUCK RENTAL LLC", [COMPANY]),
    ([(_q11_wire("PAT SAMPLE", "BOAT SALE"), 9000.0)], "NORTHWIND MARINA LLC", [WIRE]),
    ([(_q11_wire("CONTOSO LLC", "SALE OF EXCAVATOR"), 9000.0)], "NORTHWIND EQUIPMENT RENTAL LLC", [WIRE]),
    # W1, W2: a towing holder's platform payment with no seller word is its fee.
    ([(_q11_bofa("COPART INC", "PAYMENT", holder="NORTHWIND TOWING LLC"), 3000.0)], "NORTHWIND TOWING LLC",
     [COMPANY]),
    ([(_q11_chase("CARVANA LLC", "PAYMENT", holder="NORTHWIND TOWING LLC"), 3000.0)], "NORTHWIND TOWING LLC",
     [COMPANY]),
    # P3: Proxibid remits the buyers' money to the auction house (§15 deferred, unchanged).
    ([(_q11_bofa("PROXIBID", "PAYOUT", holder="NORTHWIND LIQUIDATORS LLC"), 9000.0)], "NORTHWIND LIQUIDATORS LLC",
     [REFUSED]),
    # Q1: a parts seller's 'SALE OF PARTS FOR TRUCK'.
    ([(_q11_wire("FABRIKAM FLEET LLC", "SALE OF PARTS FOR TRUCK"), 9000.0)], SOLAR, [WIRE]),
    # Review round 1: a fleet card's settlement wording is no asset sale (FLEET alone is no asset noun).
    ([(_q11_bofa("FABRIKAM FUEL CARDS INC", "FLEET SALE", holder=FUEL_STOP), 9000.0)], FUEL_STOP, [COMPANY]),
    ([(_q11_wire("CONTOSO LLC", "FLEET SALE"), 9000.0)], SOLAR, [WIRE]),
    ([(_q11_wire("CONTOSO LLC", "FLEET SOLD"), 9000.0)], SOLAR, [WIRE]),
    ([("FLEET SALE SETTLEMENT 123456 NORTHWIND FUEL", 9000.0)], FUEL_STOP, [REFUSED]),
    # Review round 1: a commission or a fee printed next to a sale is a broker's or an agent's earned revenue.
    ([(_q11_bofa("FABRIKAM MOTORS INC", "CAR SALE COMMISSION", holder=BROKERS), 3000.0)], BROKERS, [REFUSED]),
    ([(_q11_wire("FABRIKAM AUTO GROUP LLC", "VEHICLE SALE COMMISSION"), 3000.0)], BROKERS, [REFUSED]),
    ([(_q11_wire("FABRIKAM AUTO GROUP LLC", "COMMISSION ON TRUCK SALE"), 3000.0)], BROKERS, [REFUSED]),
    ([(_q11_wire("FABRIKAM AUTO GROUP LLC", "TRUCK SALE FEE"), 3000.0)], BROKERS, [REFUSED]),
    ([(_q11_wire("FABRIKAM AUTO GROUP LLC", "EQUIPMENT SALE COMMISSIONS"), 3000.0)], BROKERS, [REFUSED]),
])
def test_a_dealer_s_sale_or_no_asset_sale_keeps_its_reading(rows, holder, expected):
    assert _q11(rows, holder) == expected


def test_an_iaa_seller_payout_a_later_hold_names_stays_held():
    # Review round 1: IAA's insurer-name hold yields to Q11 only when no later hold names the row; beside an IAA
    # purchase debit (a buyer and seller) the row stays held and reviewable, as Copart's stays held payer_also_debited.
    assert _q11([(_q11_bofa("INSURANCE AUTO AUCTIONS", "SELLER PMT"), 3000.0),
                 ("INSURANCE AUTO AUCTIONS DES:PURCHASE ID:1 CO ID:1 CCD", -2000.0)]) == [
        ("excluded_pending_review", "insurer_named_payer")]
    assert _q11([(_q11_bofa("COPART INC", "SELLER PMT"), 3000.0),
                 ("COPART INC DES:PURCHASE ID:1 CO ID:1 CCD", -2000.0)]) == [
        ("excluded_pending_review", "payer_also_debited")]
    # IAA's seller payments with no later hold are still asset-sale proceeds.
    assert _q11([(_q11_bofa("INSURANCE AUTO AUCTIONS", "SELLER PMT"), 3000.0),
                 (_q11_bofa("INSURANCE AUTO AUCTIONS", "SELLER PMT", ref="7654321"), 2500.0)]) == [ASSET_SALE] * 2


def test_a_zelle_truck_sale_is_q3_s_never_an_asset_sale():
    # D14 (CR7): the rules count it as a person-to-person payment; Q3's policy excludes it, never Q11.
    record, = _q11_records([("ZELLE PAYMENT FROM PAT SAMPLE FOR TRUCK SALE CONF ABC123", 9000.0)])
    assert rules_reading(record, method=True) == P2P
    assert record.revenue_match_method == tr.ZELLE_POLICY_METHOD


@pytest.mark.parametrize(("region", "entity"), [
    ("CARVANA PAYOUT", "Carvana"), ("CARVANA LLC", "Carvana"), ("RITCHIE BROS AUCTIONEERS INC", "Ritchie Bros. (RB Global)"),
    ("CARMAX AUTO SUPERSTORES INC", "CarMax"), ("VROOM INC", "Vroom"), ("PEDDLE LLC", "Peddle"),
    ("BIG IRON AUCTION CO", "BigIron Auctions"), ("BIGIRON AUCTIONS LLC", "BigIron Auctions"),
    ("IAA INC", "Insurance Auto Auctions (IAA)"), ("RB GLOBAL INC", "Ritchie Bros. (RB Global)"),
    ("CARMAX BUSINESS SERVICES LLC", None), ("VROOM DELIVERY LLC", None), ("FABRIKAM PEDDLERS LLC", None),
    ("BIG IRON TRUCKING LLC", None), ("CARVANA FOR PETS LLC", None), ("PROXIBID LLC", None),
])
def test_the_asset_sale_platform_reader(region, entity):
    assert tr.asset_sale_platform(region) == entity
    assert "Proxibid" not in " ".join(registry.ASSET_SALE_PAYERS)
    assert registry.ASSET_SALE_SELLER_WORD_ONLY == {"Copart", "Insurance Auto Auctions (IAA)"}


@pytest.mark.parametrize("payer", [
    "IRONPLANET INC", "IRON PLANET INC", "RB GLOBAL INC", "RITCHIE BROS AUCTIONEERS", "PURPLE WAVE INC",
    "BIGIRON AUCTIONS LLC", "BIG IRON AUCTION CO", "GOVDEALS INC", "PROXIBID INC", "COPART INC", "IAA INC",
    "INSURANCE AUTO AUCTIONS", "CARVANA PAYOUT", "CARMAX", "CARMAX BUSINESS SERVICES LLC", "PEDDLE LLC", "VROOM INC",
])
def test_an_auction_or_car_buyer_seller_payout_is_never_verified(payer):
    text = _bofa(payer, "SELLER PMT")
    tier = _one(text, 15000.0, bank="Bank of America")
    assert tier[0] != "verified"
    deferred = tr._SECTION_15_DEFERRED_PAYERS
    assert deferred.search(normalize_transaction_description(text))
    assert deferred.pattern == registry.SECTION_15_DEFERRED_PAYERS


@pytest.mark.parametrize("text", [
    # CarMax Auto Finance is a listed auto lender paying dealers (§8.7, DEALER_FUNDING_PAYERS), not a car buyer.
    "CARMAX AUTO FINANCE",
    "ORIG CO NAME CARMAX AUTO ORIG ID 1 CO ENTRY DESCR FINANCE",
    # Copart and IAA also pay their towing and transport vendors: only their seller payments are deferred.
    "COPART INC DES VENDOR PAY ID 1",
    "IAA INC DES PAYMENT ID 1",
    # A car buyer's other payments, and a name that only starts like one.
    "CARVANA LLC DES VENDOR PAY ID 1",
    "FABRIKAM PEDDLERS LLC DES PAYMENT ID 1",
])
def test_a_lender_or_a_vendor_payment_is_no_deferred_seller_payout(text):
    assert not tr._SECTION_15_DEFERRED_PAYERS.search(text)


# I46: statement furniture a parser glued onto a row is cut before classification.

TD_PANEL = (
    " CALL 1 800 555 0100 FOR 24 HOUR BANK BY PHONE SERVICES OR CONNECT TO WWW TDBANK COM BANK DEPOSITS FDIC INSURED"
    " TD BANK N A EQUAL HOUSING LENDER PAGE 2 HOW TO BALANCE YOUR ACCOUNT PAGE 2 OF 8 ADD ANY INTEREST EARNED IF YOU"
    " HAVE AN INTEREST BEARING ACCOUNT IN CASE OF ERRORS OR QUESTIONS ABOUT YOUR ELECTRONIC FUNDS TRANSFERS FOR"
    " CONSUMER LOAN ACCOUNTS ONLY BILLING RIGHTS SUMMARY RETURNED ITEM PAGE 3 STATEMENT OF ACCOUNT NORTHWIND BAKERY"
    " LLC PAGE 3 OF 8 STATEMENT PERIOD JAN 01 2054 JAN 31 2054"
)
TD_FOOTER = " BANK DEPOSITS FDIC INSURED TD BANK N A EQUAL HOUSING LENDER CALL 1 888 555 0100 FOR 24 HOUR BANK BY PHONE"
CITIZENS_HEADER = (
    " PLEASE SEE ADDITIONAL INFORMATION ON NEXT PAGE PAGE 6 PAGE 6 OF 9 BUSINESS ADVISOR CHECKING FOR XXXXXX 123 4"
    " CONTINUED DEPOSITS AND CREDITS CONTINUED DATE AMOUNT DESCRIPTION"
)
CITIZENS_FDIC = (
    " MEMBER FDIC 2 EQUAL HOUSING LENDER PAGE 6 PAGE 6 OF 10 BUSINESS GREEN CHECKING FOR XXXXXX 123 4 CONTINUED"
    " DEPOSITS AND CREDITS CONTINUED DATE AMOUNT DESCRIPTION"
)
SYMITAR_RECAP = (
    " 01 31 54 1 234 56 ENDING BALANCE CLEARED CHECK RECAP CHECK DATE AMOUNT 1001 01 05 500 00 INDICATES CHECKS OUT OF"
    " SEQUENCE THIS PERIOD YEAR TO DATE TOTAL OVERDRAFT FEES 0 00 0 00 TOTAL RETURNED ITEM FEES 0 00 0 00"
)
SYMITAR_HEADER = (
    " 3 STATEMENT OF ACCOUNT ACCOUNT NUMBER STATEMENT PERIOD PAGE 01 01 54 01 31 54 1234 3 OF 5 POSTING DATE"
    " DEPOSIT WITHDRAWAL BALANCE DESCRIPTION"
)
CITIBANK_HEADER = " 000 R1 01F001 PAGE 3 OF 5 NORTHWIND BAKERY LLC ACCOUNT 1234567890 STATEMENT PERIOD JAN 1 JAN 31 2054"
FIFTH_THIRD_PAGE = " PAGE 9 OF 10 DATE AMOUNT DESCRIPTION"
FIFTH_THIRD_DISCLOSURE = " FOR ADDITIONAL INFORMATION AND ACCOUNT DISCLOSURES PLEASE VISIT WWW 53 COM COMMERCIALBANKING"


@pytest.mark.parametrize(("row", "furniture", "bank"), [
    ("SBB MDEPOSIT", TD_PANEL, "TD Bank"),
    ("SBB MDEPOSIT", TD_FOOTER + TD_PANEL, "TD Bank"),
    ("DEPOSIT", TD_FOOTER + TD_PANEL, "TD Bank"),
    ("ACH DEPOSIT VENMO CASHOUT 1234567890123", TD_PANEL, "TD Bank"),
    ("RTP RCVD STRIPE PAYMENTS COMPANY ST ABCDEFGHIJ123 CONTOSO", TD_PANEL, "TD Bank"),
    ("CCD DEPOSIT INTUIT 12345678 DEPOSIT 123456789012345", TD_PANEL, "TD Bank"),
    ("CHECK DEPOSIT", SYMITAR_RECAP, "Symitar Credit Union"),
    ("CHECK DEPOSIT", SYMITAR_HEADER, "Symitar Credit Union"),
    ("1234 ATM DEPOSIT AB1234 SAMPLE OFFICE 1 SAMPLEVILLE", CITIZENS_HEADER, "Citizens Bank"),
    ("MOBILE DEPOSIT", CITIZENS_FDIC, "Citizens Bank"),
    ("STRIPE TRANSFER 540102 ST AB1CD2EF3GH4", CITIZENS_FDIC, "Citizens Bank"),
    ("NOW NETWORK CREDIT ZELLE CREDIT NOW NET ID 123456ABCDEF EPP ID US12345678901234 ZELLE PAT SAMPLE 1234567890",
     CITIZENS_HEADER, "Citizens Bank"),
    ("DEPOSIT", CITIBANK_HEADER, "Citibank"),
    ("CPS DEVICE DEPOSIT B12345678901234 01022054", FIFTH_THIRD_DISCLOSURE, "Fifth Third Bank"),
    ("SHIFT4 PYMT PROC 123456789012345 CONTOSO GRILL 010254", FIFTH_THIRD_PAGE, "Fifth Third Bank"),
])
def test_a_deposit_with_statement_furniture_glued_on_reads_as_the_deposit_alone(row, furniture, bank):
    glued = _one(row + furniture, 800.0, bank=bank)
    assert glued == _one(row, 800.0, bank=bank)
    assert _in_true(glued)
    assert revenue_text(normalize_transaction_description(row + furniture)) == revenue_text(
        normalize_transaction_description(row))


@pytest.mark.parametrize(("row", "bank", "expected"), [
    ("SBB MDEPOSIT" + TD_PANEL, "TD Bank", UNLABELLED),
    ("CHECK DEPOSIT" + SYMITAR_RECAP, "Symitar Credit Union", CHECK),
    ("1234 ATM DEPOSIT AB1234 SAMPLE OFFICE 1 SAMPLEVILLE" + CITIZENS_HEADER, "Citizens Bank", NO_PAYER),
])
def test_the_brief_s_furniture_rows_are_counted(row, bank, expected):
    assert _one(row, 800.0, bank=bank) == expected


@pytest.mark.parametrize(("row", "bank", "expected"), [
    # The furniture's cut never brings in money that should stay out: a prediction market's payout is held by the
    # gambling reader, and a bare transfer is held under Q2 once the header's account number is gone.
    ("VISA TRANSFER AUT 010254 VISA TRANSFER KALSHI KLEAR LLC NEW YORK NY 1234123412341234" + TD_PANEL, "TD Bank",
     NON_SALE),
    ("CBUSOL TRANSFER CREDIT ONLINE REFERENCE 1" + CITIBANK_HEADER, "Citibank", NO_COUNTERPARTY),
    ("CBUSOL TRANSFER CREDIT ONLINE REFERENCE 1", "Citibank", NO_COUNTERPARTY),
    # An own-account transfer and a loan stay non_revenue.
    ("ONLINE TRANSFER FROM CHECKING 1234567890" + CITIZENS_HEADER, "Citizens Bank", ("non_revenue", None)),
    ("ACH DEPOSIT FABRIKAM LOAN PROCEEDS" + TD_PANEL, "TD Bank", ("non_revenue", None)),
])
def test_the_furniture_cut_keeps_what_should_stay_out_of_true(row, bank, expected):
    tier = _one(row, 400.0, bank=bank)
    if expected[1] is None:
        assert tier[0] == expected[0]
    else:
        assert tier == expected


@pytest.mark.parametrize("text", [
    # Text a payer prints that only resembles furniture is never cut.
    "FABRIKAM INC DES:PAYMENT ID:1 INDN:NORTHWIND BAKERY LLC CO ID:1234567890 CCD PMT INFO STATEMENT OF ACCOUNT 1234",
    "WT FED 01234 SAMPLE BANK ORG FABRIKAM INC SRF 1 TRN 2 RFB 3 OBI INVOICE 1234 PAGE ONE",
    "PAGE 1 OF 2 FABRIKAM INC",
])
def test_text_that_only_resembles_furniture_is_kept(text):
    normalized = normalize_transaction_description(text)
    assert revenue_text(normalized) == normalized


@pytest.mark.parametrize(("text", "kept"), [
    ("SBB MDEPOSIT" + TD_PANEL, "SBB MDEPOSIT"),
    # The ending balance's date and amount are the recap's, as a page number is the header's.
    ("CHECK DEPOSIT" + SYMITAR_RECAP, "CHECK DEPOSIT"),
    ("CHECK DEPOSIT" + SYMITAR_HEADER, "CHECK DEPOSIT"),
    ("CBUSOL TRANSFER CREDIT ONLINE REFERENCE 1" + CITIBANK_HEADER, "CBUSOL TRANSFER CREDIT ONLINE REFERENCE 1"),
    ("01/02SBB MDEPOSIT" + TD_FOOTER, "SBB MDEPOSIT"),
])
def test_the_cut_reads_the_earliest_furniture_and_keeps_the_row_before_it(text, kept):
    assert revenue_text(normalize_transaction_description(text)) == kept


# Audit round 2, R2-B10 (R21 part A): Zions' legal-name footer, glued before a page break's counters, is furniture; the
# same words a wire prints after its sending bank (no page counter after them) are not.

ZIONS = "Zions Bancorporation"
ZIONS_HOLDER = HOLDER
ZIONS_FOOTER = " A DIVISION OF ZIONS BANCORPORATION N A 1234567 PAGE 2 PAGE 2 OF 4 MARCH 31 2054 NORTHWIND BAKERY LLC"


def test_r21_a_bare_zions_deposit_with_the_footer_glued_names_no_payer():
    assert _one("DEPOSIT" + ZIONS_FOOTER, 5000.0, holder=ZIONS_HOLDER, bank=ZIONS) == NO_PAYER
    assert revenue_text(normalize_transaction_description("DEPOSIT" + ZIONS_FOOTER)) == "DEPOSIT"


def test_r21_control_a_zions_bankcard_settlement_with_the_footer_stays_verified():
    text = "BANKCARD 1234 MTOT DEP REF 12345 1234567890 BANKCARD 1234" + ZIONS_FOOTER
    assert _one(text, 300.0, holder=ZIONS_HOLDER, bank=ZIONS)[0] == "verified"


def test_r21_control_a_wire_relayed_by_a_zions_division_keeps_its_sender():
    text = "WIRE TRANSFER FROM FABRIKAM INC VIA SAMPLE BANK A DIVISION OF ZIONS BANCORPORATION N A REF 1"
    assert revenue_text(normalize_transaction_description(text)) == text
    assert _one(text, 5000.0, holder=ZIONS_HOLDER, bank=ZIONS) == WIRE


def test_r21_control_the_zions_footer_alone_keeps_its_text():
    text = "A DIVISION OF ZIONS BANCORPORATION N A 1234567 PAGE 2 PAGE 2 OF 4"
    assert revenue_text(text) == text


# Audit round 2, R2-B10 (R21 part B, the classifier's guard): Navy Federal's page header ('STATEMENT OF ACCOUNT',
# 'JOINT OWNER(S): <names|NONE>') glued onto a row is furniture, so its OWNER never holds a deposit.

NAVY_FEDERAL = "Navy Federal Credit Union"


@pytest.mark.parametrize("header", [" STATEMENT OF ACCOUNT JOINT OWNER S NONE", " JOINT OWNER S NONE"])
def test_r21_a_navy_federal_mobile_deposit_with_the_header_glued_is_a_counted_check_deposit(header):
    assert _one("MOBILE DEPOSIT" + header, 500.0, bank=NAVY_FEDERAL) == CHECK


def test_r21_a_navy_federal_ach_payer_with_the_header_glued_verifies_beside_its_clean_twin():
    rows = [("ACH TRANSACTION CONTOSO SUPPLY LLC PAYMENT 1234 STATEMENT OF ACCOUNT JOINT OWNER S NONE", 500.0),
            ("ACH TRANSACTION CONTOSO SUPPLY LLC PAYMENT 1234", 600.0)]
    assert [tier for tier, _reason in _tiers(rows, bank=NAVY_FEDERAL)] == ["verified", "verified"]


def test_r21_control_an_own_account_transfer_with_the_header_glued_stays_non_revenue():
    assert _one("TRANSFER FROM SHARES JOINT OWNER S NONE", 500.0, bank=NAVY_FEDERAL)[0] == "non_revenue"


# Audit round 2, R2-B10 (R21 part D): the cut drops every word after the first form, so a loan's proceeds printed
# after a page counter are read as a bare deposit (§6.3 narrowing 11's recorded residual; the census counts such rows,
# which the corpus does not print).

def test_r21_the_recorded_residual_a_loan_after_a_page_counter_is_a_counted_bare_deposit():
    assert _one("DEPOSIT PAGE 2 OF 8 LOAN PROCEEDS", 5000.0) == NO_PAYER


# I46 (Q2): the plural TRANSFERS is transfer wording.

def test_a_bare_transfers_row_is_held_however_often_it_repeats():
    rows = [(f"EXTERNAL DEPOSIT ACH TRANSFERS PAYMENT {n}", 7000.0 + n) for n in (1, 2, 3, 4)]
    assert _tiers(rows, bank="Sample Credit Union") == [NO_COUNTERPARTY] * 4


@pytest.mark.parametrize(("text", "bank"), [
    ("12345678901 PAY BY PHONE XXXXXX1234 FUNDS TRANSFERS", "Banco Popular"),
    ("ONLINE TRANSFERS CREDIT 1234", "Sample Bank"),
])
def test_bare_transfers_wording_is_held(text, bank):
    assert _one(text, 4000.0, bank=bank)[0] == "excluded_pending_review"


def test_a_named_transfers_counterparty_is_a_named_transfer():
    # T13: a transfer that names its counterparty takes the named-transfer reading (counted under Q4).
    assert _one("TRANSFERS FROM FABRIKAM SUPPLY LLC", 4000.0, bank="Sample Bank") == P2P


def test_square_s_loan_transfers_stay_non_revenue():
    assert _one("SQUARE LOAN TRANSFERS", 4000.0, bank="Square")[0] == "non_revenue"


# I56 (GOV class D): a glued Canada Carbon Rebate is held, as its spaced spelling is; a payer whose name holds CARBON
# keeps its reading. (WSIB's no-purpose payment is non_revenue since the owner's ruling of 2026-10-02, the underwriter's
# Q12: tests/test_true_revenue_government_no_purpose.py.)

@pytest.mark.parametrize("text", ["CDACARBONREBATE CCR", "CDA CARBON REBATE CCR", "CANADA CARBON REBATE",
                                  "DIRECT DEPOSIT CDACARBONREBATE"])
def test_a_canada_carbon_rebate_is_held(text):
    assert _one(text, 120.0, bank="TD Canada Trust") == NON_SALE


@pytest.mark.parametrize("text", [
    "CONTOSO CARBON WORKS LLC DES:PAYMENT ID:1234567 INDN:NORTHWIND BAKERY LLC CO ID:1234567890 CCD",
])
def test_a_carbon_surname_keeps_its_reading(text):
    tier = _one(text, 120.0, bank="Royal Bank of Canada")
    assert tier != NON_SALE and _in_true(tier)


# GOV follow-ups (the orchestrator's): the IRS's interest on a refund is non_revenue; RBC's cut provincial payment
# code with the CRA's originator is a personal benefit (class B).

@pytest.mark.parametrize(("text", "bank"), [
    ("IRS TREAS 310 DES:INT ID:1234567 INDN:NORTHWIND BAKERY LLC CO ID:1234567890 PPD", "Bank of America"),
    ("IRS TREAS 310 DES:INTEREST ID:1234567 INDN:NORTHWIND BAKERY LLC CO ID:1234567890 PPD", "Bank of America"),
    ("ORIG CO NAME IRS TREAS 310 ORIG ID 1234567890 DESC DATE 010254 CO ENTRY DESCR INT SEC PPD TRACE 123456789012345"
     " EED 540102 IND ID 12345", "Chase"),
    ("IRS TREAS 310 INT 1234567890", "Wells Fargo"),
])
def test_the_irs_interest_on_a_refund_is_non_revenue(text, bank):
    assert _one(text, 45.0, bank=bank) == NON_REVENUE


@pytest.mark.parametrize(("text", "expected"), [
    # The IRS's vendor payments keep their readings (GOV review I1).
    ("IRS TREAS 310 DES:MISC PAY ID:1", REFUSED),
    ("IRS TREAS 310 DES:VENDOR PAY ID:1", ("verified", "public_payer_remittance")),
    ("IRS TREAS 310 DES:INTL VENDOR ID:1", None),
])
def test_an_irs_vendor_payment_is_no_interest(text, expected):
    tier = _one(text, 45.0, bank="Bank of America")
    assert tier[0] != "non_revenue"
    if expected is not None:
        assert tier == expected


@pytest.mark.parametrize("text", [
    "Prov./Loc.G.Paym Canada",
    "Prov./Loc.G.Paym Canada PRO",
    "PROV LOC G PAYM CANADA 12345",
    "DIRECT DEPOSIT PROV LOC G PAYM CANADA",
])
def test_rbc_s_cut_provincial_payment_code_with_the_cra_s_name_is_a_personal_benefit(text):
    assert _one(text, 300.0, bank="Royal Bank of Canada") == PERSONAL


@pytest.mark.parametrize("text", [
    # A provincial payment from a province names no CRA benefit (class E, the owner's): its reading is kept.
    "Prov./Loc.G.Paym ONTARIO",
    "PROV LOC G PAYM CANADA GOOSE SUPPLY",
])
def test_rbc_s_cut_provincial_payment_code_without_the_cra_keeps_its_reading(text):
    tier = _one(text, 300.0, bank="Royal Bank of Canada")
    assert tier != PERSONAL and _in_true(tier)


# B7 review round 2 (routed to B8, §20): an owner-shaped payer's DISB entry is owner money, as its DISBURSEMENT is.

def test_an_owner_shaped_payer_s_disb_entry_is_held_however_often_it_repeats():
    rows = [(_bofa("FABRIKAM PARTNERS LP", "PARTNER DISB", "1234567"), 5000.0),
            (_bofa("FABRIKAM PARTNERS LP", "PARTNER DISB", "7654321"), 5000.0)]
    assert _tiers(rows, bank="Bank of America") == [NON_SALE, NON_SALE]
    assert _one(_bofa("CONTOSO HOLDINGS LLC", "DISB"), 5000.0, bank="Bank of America") == NON_SALE


@pytest.mark.parametrize(("rows", "expected"), [
    # An ordinary payer's cash disbursement is its payment to a vendor; a factor's DISB stays its factoring payout.
    ([(_bofa("CONTOSO SUPPLY INC", "CASH DISB", "1234567"), 5000.0),
      (_bofa("CONTOSO SUPPLY INC", "CASH DISB", "7654321"), 4000.0)], [REPEATS, REPEATS]),
    ([("ORIG CO NAME FABRIKAM TRADING ORIG ID 1234567890 DESC DATE CO ENTRY DESCR CASH DISB SEC CCD TRACE"
       " 123456789012345", 5000.0)], [ONE_OFF]),
])
def test_an_ordinary_payer_s_disb_entry_keeps_its_reading(rows, expected):
    assert _tiers(rows, bank="Chase") == expected


# The census's facts name the rule that holds each.

@pytest.mark.parametrize(("text", "rule"), [
    (_bofa("KALSHI", "WITHDRAWAL"), "gambling_payout"),
    ("MONEY TRANSFER AUTHORIZED ON 01 02 FROM CROWN GAMING INC CROWN GAMING MA S123456789012345 CARD 1234",
     "gambling_payout"),
    (_bofa("EPIQ CLASS ACTION", "SETTLEMENT", sec="PPD"), "legal_settlement"),
    ("WT FED 01234 SAMPLE BANK ORG CONTOSO LAW GROUP IOLTA SRF 2054010200000 TRN 540102000001 RFB AB12 OBI SETTLEMENT"
     " PROCEEDS", "legal_settlement"),
    ("WT FED 01234 SAMPLE BANK ORG FABRIKAM SETTLEMENT SERVICES INC SRF 2054010200000 TRN 540102000001 RFB AB12",
     "title_firm"),
    (_bofa("KRAKEN", "WITHDRAWAL"), "owner_money"),
    ("CDACARBONREBATE CCR", "government_grant"),
    ("Prov./Loc.G.Paym Canada", "government_benefit"),
    (_bofa("FABRIKAM PARTNERS LP", "PARTNER DISB"), "owner_disbursement"),
    (_bofa("DRAFTKINGS", "AP PAYMENT"), None),
    ("CONTRACTOR MGMT SETTLEMENT 1", None),
])
def test_the_hold_rule_fact_names_the_new_readings(text, rule):
    from analysis.transaction_classifier import entry_fields, payer_region

    record = next(record for record in _records([(text, 900.0)]) if record.amount > 0)
    revenue = revenue_text(record.normalized_description)
    assert tr.hold_rule(record, revenue, payer_region(revenue), entry_fields(revenue)) == rule


# Audit round 2, R2-B12 (R37): B8's readers read a legal, gambling or owner-money word as the payer's or the purpose's,
# never inside a customer's trade name (a company form and a name word of its own in the payer region, or a name word
# right after it on the purpose); a processor's or a carrier's '<word> SETTLEMENT SERVICES' is no title firm; an
# accounts-payable or vendor DISB is no owner money; BigIron's deferral reads its own spellings only.

#: Chase's incoming-ACH layout, with the holder in the receiver field.
CHASE = ("ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:{entry}SEC:CCD "
         "TRACE#:123456789012345 EED:540102 IND ID:12345 IND NAME:NORTHWIND BAKERY LLC TRN: 1234567890TC")


def _chase(payer: str, entry: str) -> str:
    return CHASE.format(payer=payer, entry=entry)


def _twice(payer: str, entry: str, amount: float = 900.0):
    return [(_bofa(payer, entry, "1234567"), amount), (_bofa(payer, entry, "7654321"), amount + 1)]


@pytest.mark.parametrize(("payer", "entry"), [
    ("CONTOSO LITIGATION SUPPORT LLC", "PAYMENT"),
    ("FABRIKAM DATA BREACH RESPONSE LLC", "PAYMENT"),
    ("VERITA HEALTH LLC", "PAYMENT"),
    ("EPIQ PLUMBING INC", "PAYMENT"),
    ("JACKPOT DIGITAL INC", "PAYMENT"),
    ("FABRIKAM WINNINGS LLC", "PAYMENT"),
    ("KRAKEN ROBOTICS INC", "INV 1234"),
    ("PAXOS CLEANING LLC", "PAYMENT"),
    ("CONTOSO UPHOLD SERVICES LLC", "PAYMENT"),
    ("FABRIKAM FAMILY DENTAL", "AP DISB"),
    ("CONTOSO HOLDINGS INC", "VENDOR DISB"),
    ("BIG IRON TRUCKING LLC", "PAYMENT"),
])
def test_r37_a_customer_s_trade_name_or_vendor_disb_holds_nothing(payer, entry):
    assert _tiers(_twice(payer, entry), bank="Bank of America") == [REPEATS, REPEATS]


@pytest.mark.parametrize("payer", ["CONTOSO CARD SETTLEMENT SERVICES", "FABRIKAM FREIGHT SETTLEMENT SERVICES LLC"])
def test_r37_a_processor_s_or_a_carrier_s_settlement_services_is_no_title_firm(payer):
    entry = "DEPOSIT" if "CARD" in payer else "PAYMENT"
    assert _tiers(_twice(payer, entry), bank="Bank of America") == [REFUSED, REFUSED]


def test_r37_a_product_named_on_a_person_to_person_memo_holds_nothing():
    assert _one("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT CANDLES CONF 1234", 180.0, bank="Bank of America") == P2P


@pytest.mark.parametrize(("rows", "bank"), [
    (_twice("SAMPLE CASINO", "JACKPOT"), "Bank of America"),
    (_twice("FABRIKAM JACKPOT CASINO", "PAYOUT"), "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR YOUR WINNINGS CONF 1234", 900.0)], "Bank of America"),
    (_twice("EPIQ SYSTEMS INC", "PAYMENT"), "Bank of America"),
    (_twice("VERITA GLOBAL", "PAYMENT"), "Bank of America"),
    (_twice("FABRIKAM INC", "LITIGATION"), "Bank of America"),
    (_twice("KRAKEN", "WITHDRAWAL"), "Bank of America"),
    (_twice("UPHOLD HQ INC", "WITHDRAWAL"), "Bank of America"),
    (_twice("PAXOS TRUST CO", "WITHDRAWAL"), "Bank of America"),
    ([("WT FED 01234 SAMPLE BANK ORG FABRIKAM SETTLEMENT SERVICES INC SRF 2054010200000 TRN 540102000001 RFB AB12",
       4000.0)], "Wells Fargo"),
    (_twice("CONTOSO CLOSING SERVICES LLC", "PAYMENT"), "Bank of America"),
    (_twice("CONTOSO HOLDINGS LLC", "DISB"), "Bank of America"),
    (_twice("CONTOSO HOLDINGS INC", "CASH DISB"), "Bank of America"),
    (_twice("FABRIKAM FAMILY DENTAL", "DISBURSEMENT"), "Bank of America"),
])
def test_r37_controls_keep_their_holds(rows, bank):
    assert _tiers(rows, bank=bank) == [NON_SALE] * len(rows)


def test_r37_an_equipment_auction_s_seller_payout_is_still_never_verified():
    # The owner's ruling of 2026-10-02 (the underwriter's Q11 (b)): on a statement that shows no dealer (a bakery's),
    # BigIron's payout is asset-sale proceeds, non_revenue (it was counted as a refused deferred source); still never
    # verified. R2-B12's spelling reading (glued, or spaced before AUCTION) is the asset-sale reader's too.
    for payer in ("BIG IRON AUCTION CO", "BIG IRON AUCTIONS LLC", "BIGIRON AUCTIONS LLC"):
        assert _tiers(_twice(payer, "PAYMENT", 15000.0), bank="Bank of America") == [ASSET_SALE, ASSET_SALE], payer
    assert _tiers(_twice("BIG IRON TRUCKING LLC", "PAYMENT", 15000.0), bank="Bank of America") == [REPEATS, REPEATS]
    deferred = tr._SECTION_15_DEFERRED_PAYERS
    assert deferred.pattern == registry.SECTION_15_DEFERRED_PAYERS
    for text in ("BIG IRON AUCTION CO", "BIG IRON AUCTIONS", "BIGIRON", "BIGIRON AUCTIONS LLC"):
        assert deferred.search(text), text
    for text in ("BIG IRON TRUCKING LLC", "BIG IRON FABRIKAM LLC", "FABRIKAM BIG IRONSAMPLE"):
        assert not deferred.search(text), text


@pytest.mark.parametrize(("text", "words", "keep", "trade"), [
    # (a) in a payer region that prints a company form and a name word of its own.
    (_bofa("CONTOSO LITIGATION SUPPORT LLC", "PAYMENT"), "LEGAL", "LEGAL", True),
    (_bofa("EPIQ SYSTEMS INC", "PAYMENT"), "LEGAL", "LEGAL", False),
    (_bofa("VERITA GLOBAL", "PAYMENT"), "LEGAL", "LEGAL", False),
    (_bofa("UPHOLD HQ INC", "WITHDRAWAL"), "PLATFORM", "PLATFORM", False),
    (_bofa("PAXOS TRUST CO", "WITHDRAWAL"), "PLATFORM", "PLATFORM", False),
    (_bofa("THE KRAKEN USA LLC", "WITHDRAWAL"), "PLATFORM", "PLATFORM", False),
    (_bofa("KRAKEN 123 LLC", "WITHDRAWAL"), "PLATFORM", "PLATFORM", False),
    (_bofa("PAXOS CLEANING LLC", "PAYMENT"), "PLATFORM", "PLATFORM", True),
    # (b) on the purpose, with a name word right after it.
    ("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT CANDLES CONF 1234", "GAMBLING", "GAMBLING", True),
    ("ZELLE PAYMENT FROM A SAMPLE FOR YOUR WINNINGS CONF 1234", "GAMBLING", "GAMBLING", False),
    ("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT PAYOUT CONF 1234", "GAMBLING", "GAMBLING", False),
    ("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT 1234", "GAMBLING", "GAMBLING", False),
    (_bofa("FABRIKAM INC", "LITIGATION"), "LEGAL", "LEGAL", False),
    (_bofa("FABRIKAM INC", "LITIGATION SUPPORT"), "LEGAL", "LEGAL", True),
    (_bofa("FABRIKAM INC", "LITIGATION FUNDS"), "LEGAL", "LEGAL", False),
    # Anywhere else it holds: a payer region with no company form, or a second occurrence outside the name.
    (_bofa("CONTOSO LITIGATION SUPPORT", "PAYMENT"), "LEGAL", "LEGAL", False),
    (_bofa("CONTOSO LITIGATION SUPPORT LLC", "LITIGATION"), "LEGAL", "LEGAL", False),
])
def test_r37_the_trade_name_reader(text, words, keep, trade):
    from analysis.transaction_classifier import payer_region

    tables = {
        "LEGAL": (tr._LEGAL_NAME_WORDS, tr._LEGAL_NAME_KEEP),
        "GAMBLING": (tr._GAMBLING_NAME_WORDS, tr._GAMBLING_CONTEXT),
        "PLATFORM": (tr._PLATFORM_NAME_WORDS, tr._PLATFORM_NAME_KEEP),
    }
    revenue = revenue_text(normalize_transaction_description(text))
    row = tr._hold_text(revenue)
    assert tr._trade_name(revenue, row, payer_region(revenue), tables[words][0], tables[keep][1]) is trade


def test_r37_the_title_firm_s_settlement_services_arm_spares_a_processor_s_and_a_carrier_s_word():
    title = tr._TITLE_FIRM
    for name in ("FABRIKAM SETTLEMENT SERVICES INC", "CONTOSO CLOSING SERVICES LLC", "CONTOSO CLOSING SERVICE",
                 "SAMPLE TITLE AND ESCROW", "FABRIKAM SETTLEMENT SERVICE"):
        assert title.search(name), name
    for name in ("CONTOSO CARD SETTLEMENT SERVICES", "FABRIKAM FREIGHT SETTLEMENT SERVICES LLC",
                 "CONTOSO MERCHANT SETTLEMENT SERVICES", "CONTOSO PAYMENT SETTLEMENT SERVICES",
                 "CONTOSO TRANSPORTATION SETTLEMENT SERVICES", "CONTOSO DEBT SETTLEMENT SERVICES",
                 "CONTOSO CLAIMS SETTLEMENT SERVICES"):
        assert not title.search(name), name


@pytest.mark.parametrize(("text", "rule"), [
    (_bofa("KRAKEN", "WITHDRAWAL"), "owner_money"),
    (_bofa("PAXOS CLEANING LLC", "PAYMENT"), None),
    # Review round 1: a platform the registry names by its own name is spared by §7.5's accounts-payable wording only
    # (S4.2's exception), never by a bare invoice word; KRAKEN, UPHOLD or PAXOS alone takes the legal and gambling
    # readers' vendor spare.
    (_bofa("BITSTAMP USA INC", "INV 1234"), "owner_money"),
    (_bofa("KRAKEN", "INV 1234"), None),
    # The classifier's savings and investing originators are read as before, an invoice word or not.
    (_bofa("COINBASE INC", "INV 1234"), "owner_money"),
    (_bofa("JACKPOT DIGITAL INC", "PAYMENT"), None),
    (_bofa("SAMPLE CASINO", "JACKPOT"), "gambling_payout"),
    (_bofa("VERITA HEALTH LLC", "PAYMENT"), None),
    (_bofa("VERITA GLOBAL", "PAYMENT"), "legal_settlement"),
    (_bofa("CONTOSO HOLDINGS INC", "VENDOR DISB"), None),
    (_bofa("CONTOSO HOLDINGS INC", "CASH DISB"), "owner_disbursement"),
    (_bofa("CONTOSO CARD SETTLEMENT SERVICES", "DEPOSIT"), None),
])
def test_r37_the_hold_rule_fact_reads_the_guarded_readers(text, rule):
    from analysis.transaction_classifier import entry_fields, payer_region

    record = next(record for record in _records([(text, 900.0)], bank="Bank of America") if record.amount > 0)
    revenue = revenue_text(record.normalized_description)
    assert tr.hold_rule(record, revenue, payer_region(revenue), entry_fields(revenue)) == rule


def test_r37_the_owner_money_platforms_table_is_unchanged():
    assert tr._OWNER_MONEY_PLATFORMS.pattern == registry.OWNER_MONEY_PLATFORMS
    for name in ("KRAKEN", "UPHOLD", "PAXOS"):
        assert tr._PLATFORM_NAME_WORDS.fullmatch(name) and tr._OWNER_MONEY_PLATFORMS.fullmatch(name), name


# Audit round 2, R2-B12 review round 1 (R37): a purpose noun, a function word or a word a hold reads, right after the
# hold word on the purpose, is the purpose's, never a trade name's (_TRADE_NAME_PURPOSE_WORD), so a legal windfall, a
# gambling win or an owner's crypto withdrawal named on an entry, a wire's OBI, a person-to-person or a transfer memo
# keeps its hold; a claims administrator's form words (SERVICES, SOLUTIONS, RESTRUCTURING, GROUP) are the legal
# reader's keep words; a platform the registry names by its own name is spared by §7.5's accounts-payable wording only.

#: Wells Fargo's incoming Fedwire layout, with the originator's free text after OBI.
WF_WIRE = "WT FED 01234 SAMPLE BANK ORG {org} SRF 2054010200000 TRN 540102000001 RFB AB12 OBI {obi}"
#: Chase's incoming-ACH layout, with its SEC code.
CHASE_SEC = ("ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:540102 CO ENTRY DESCR:{entry}SEC:{sec} "
             "TRACE#:123456789012345 EED:540102 IND ID:12345 IND NAME:NORTHWIND BAKERY LLC TRN: 1234567890TC")


@pytest.mark.parametrize(("rows", "bank"), [
    # An ACH entry (Bank of America's DES, Chase's CO ENTRY DESCR), a company's or a person's.
    (_twice("FABRIKAM INC", "LAWSUIT PROCEEDS"), "Bank of America"),
    (_twice("FABRIKAM INC", "LITIGATION PROCEEDS"), "Bank of America"),
    ([(_chase("FABRIKAM INC", "LAWSUIT PROCEEDS"), 9000.0)], "Chase"),
    ([(CHASE_SEC.format(payer="PAT SAMPLE", entry="JACKPOT WIN", sec="PPD"), 900.0)], "Chase"),
    ([(_bofa("PAT SAMPLE", "JACKPOT WIN", sec="PPD"), 900.0)], "Bank of America"),
    ([(_bofa("PAT SAMPLE", "KRAKEN WITHDRAWAL", sec="PPD"), 9000.0)], "Bank of America"),
    # A wire's originator text.
    ([(WF_WIRE.format(org="SAMPLE LAW LLP", obi="LAWSUIT PROCEEDS"), 25000.0)], "Wells Fargo"),
    ([(WF_WIRE.format(org="SAMPLE LAW LLP", obi="LITIGATION PROCEEDS"), 25000.0)], "Wells Fargo"),
    ([(WF_WIRE.format(org="SAMPLE HOLDINGS INC", obi="CLASS ACTION RECOVERY"), 25000.0)], "Wells Fargo"),
    ([(WF_WIRE.format(org="PAT SAMPLE", obi="KRAKEN WITHDRAWAL"), 9000.0)], "Wells Fargo"),
    ([(WF_WIRE.format(org="PAT SAMPLE", obi="UPHOLD CASHOUT"), 9000.0)], "Wells Fargo"),
    # A person-to-person memo and a transfer's memo.
    ([("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT WIN CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR WINNINGS FROM BET CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR WINNINGS LAST NIGHT CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR LAWSUIT MONEY CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR KRAKEN WITHDRAWAL CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR UPHOLD TRANSFER CONF 1234", 900.0)], "Bank of America"),
    ([("ONLINE TRANSFER FROM PAT SAMPLE MEMO LAWSUIT PROCEEDS CONF 1234", 9000.0)], "Bank of America"),
    ([("ONLINE TRANSFER FROM PAT SAMPLE MEMO KRAKEN CASHOUT CONF 1234", 9000.0)], "Bank of America"),
])
def test_r37_review_a_purpose_noun_after_the_hold_word_keeps_the_hold(rows, bank):
    assert _tiers(rows, bank=bank) == [NON_SALE] * len(rows)


@pytest.mark.parametrize(("rows", "bank", "expected"), [
    # A name word after the hold word on the purpose is still a trade name's (the brief's own controls). Review round 2:
    # a row only the purpose arm spares counts and never proves (named_payer_purpose_refused).
    ([("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT CANDLES CONF 1234", 180.0)], "Bank of America", [P2P]),
    ([(_bofa("FABRIKAM INC", "LITIGATION SUPPORT"), 900.0)], "Bank of America", [REFUSED]),
    (_twice("FABRIKAM INC", "LITIGATION SUPPORT"), "Bank of America", [REFUSED, REFUSED]),
])
def test_r37_review_a_name_word_after_the_hold_word_is_still_a_trade_name(rows, bank, expected):
    assert _tiers(rows, bank=bank) == expected


@pytest.mark.parametrize("word", [
    "WIN", "WINS", "WON", "WINNER", "WINNINGS", "PRIZE", "PRIZES", "BONUS", "WITHDRAWAL", "WITHDRAWALS", "WITHDRAW",
    "WDRL", "WD", "CASH", "CASHOUT", "TRANSFER", "TRANSFERS", "XFER", "TFR", "PROCEEDS", "RECOVERY", "RECOVERIES",
    "MONEY", "FUNDS", "FUNDING", "CHECK", "CHEQUE", "DISTRIBUTION", "DISBURSEMENT", "DISB", "DEPOSIT", "REFUND",
    "REIMBURSEMENT", "PAYMENTS", "PAYOUTS", "PAY", "PAID", "SETTLEMENT", "CLAIM", "AWARD", "SHARE", "SALE", "BALANCE",
    "ACCOUNT", "ACCT", "BTC", "BITCOIN", "FROM", "TO", "ON", "MY", "LAST", "TONIGHT",
])
def test_r37_review_the_purpose_words_are_no_name_words(word):
    assert tr._TRADE_NAME_PURPOSE_WORD.fullmatch(word), word


@pytest.mark.parametrize("word", ["CANDLES", "SUPPORT", "RESPONSE", "HEALTH", "PLUMBING", "ROBOTICS", "CLEANING"])
def test_r37_review_a_name_word_is_no_purpose_word(word):
    assert tr._TRADE_NAME_PURPOSE_WORD.fullmatch(word) is None, word


@pytest.mark.parametrize(("text", "words", "trade"), [
    ("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT WIN CONF 1234", "GAMBLING", False),
    ("ZELLE PAYMENT FROM A SAMPLE FOR WINNINGS FROM BET CONF 1234", "GAMBLING", False),
    (WF_WIRE.format(org="SAMPLE LAW LLP", obi="LAWSUIT PROCEEDS"), "LEGAL", False),
    (_bofa("FABRIKAM INC", "LITIGATION SERVICES"), "LEGAL", False),
    ("ZELLE PAYMENT FROM A SAMPLE FOR KRAKEN WITHDRAWAL CONF 1234", "PLATFORM", False),
    (_bofa("EPIQ CORPORATE RESTRUCTURING LLC", "PAYMENT"), "LEGAL", False),
    # Controls: a name word right after the hold word, or a name word of the region's own.
    ("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT CANDLES CONF 1234", "GAMBLING", True),
    (_bofa("FABRIKAM INC", "LITIGATION SUPPORT"), "LEGAL", True),
    (_bofa("CONTOSO LITIGATION SUPPORT LLC", "PAYMENT"), "LEGAL", True),
])
def test_r37_review_the_trade_name_reader_reads_a_purpose_word_as_the_purpose_s(text, words, trade):
    from analysis.transaction_classifier import payer_region

    tables = {
        "LEGAL": (tr._LEGAL_NAME_WORDS, tr._LEGAL_NAME_KEEP),
        "GAMBLING": (tr._GAMBLING_NAME_WORDS, tr._GAMBLING_CONTEXT),
        "PLATFORM": (tr._PLATFORM_NAME_WORDS, tr._PLATFORM_NAME_KEEP),
    }
    revenue = revenue_text(normalize_transaction_description(text))
    row = tr._hold_text(revenue)
    assert tr._trade_name(revenue, row, payer_region(revenue), *tables[words]) is trade


@pytest.mark.parametrize(("rows", "expected"), [
    # A claims administrator's or a restructuring unit's form words are the legal reader's keep words.
    (_twice("EPIQ CORPORATE RESTRUCTURING LLC", "PAYMENT"), [NON_SALE, NON_SALE]),
    (_twice("EPIQ GROUP INC", "PAYMENT"), [NON_SALE, NON_SALE]),
    (_twice("CLASS ACTION SERVICES LLC", "PAYMENT"), [NON_SALE, NON_SALE]),
    (_twice("LITIGATION SOLUTIONS GROUP LLC", "PAYMENT"), [NON_SALE, NON_SALE]),
    ([(_bofa("FABRIKAM INC", "LITIGATION SERVICES"), 900.0)], [NON_SALE]),
    # Recorded residual (§20): a name word of the payer's own beside the legal word and the form words still reads as a
    # customer's trade name, a claims administrator's ('<NAME> CLASS ACTION SERVICES LLC') as a litigation-support
    # vendor's ('<NAME> LITIGATION SERVICES LLC').
    (_twice("CONTOSO CLASS ACTION SERVICES LLC", "PAYMENT"), [REPEATS, REPEATS]),
    (_twice("FABRIKAM LITIGATION SERVICES LLC", "PAYMENT"), [REPEATS, REPEATS]),
])
def test_r37_review_a_claims_administrator_s_form_words_are_keep_words(rows, expected):
    assert _tiers(rows, bank="Bank of America") == expected


@pytest.mark.parametrize(("rows", "expected"), [
    # A platform the registry names by its own name: a bare invoice or vendor word spares nothing (S4.2's platform hold),
    # §7.5's accounts-payable wording does (S4.2's exception: counted by the investment word or verified by §7.5).
    (_twice("BITSTAMP USA INC", "INV 1234"), [NON_SALE, NON_SALE]),
    (_twice("BITSTAMP USA INC", "INVOICE"), [NON_SALE, NON_SALE]),
    (_twice("BITSTAMP USA INC", "VENDOR"), [NON_SALE, NON_SALE]),
    (_twice("BITSTAMP USA INC", "ACCOUNTS PAYABLE"), [REMITTANCE, REMITTANCE]),
    ([("E*TRADE SECURITIES LLC DES:ACCOUNTS PAYABLE ID:1", 3000.0)], [REFUSED]),
    # KRAKEN, UPHOLD or PAXOS alone, whose names are other businesses' too, takes the vendor spare (the brief's).
    (_twice("KRAKEN", "INV 1234"), [REPEATS, REPEATS]),
    (_twice("KRAKEN ROBOTICS INC", "INV 1234"), [REPEATS, REPEATS]),
])
def test_r37_review_a_registry_platform_is_spared_by_accounts_payable_wording_only(rows, expected):
    assert _tiers(rows, bank="Bank of America") == expected


# Audit round 2, R2-B12 review round 2 (R37): the legal reader's settlement words are the classifier's own settlement
# spellings (_SETTLEMENT_CREDIT's, and SETL), so a legal word beside an abbreviated settlement holds by context; the
# purpose words read those spellings, the payment cuts the statements print and a handpay, a distribution, proceeds, a
# judgment, a redemption, a compensation, a bet or a rail word as the purpose's; and a row only the purpose arm spares
# counts and never proves (CreditFacts.refused_word), so a purpose noun no list names is at worst counted and flagged.

@pytest.mark.parametrize(("rows", "bank"), [
    # One credit from a formed payer (Bank of America's DES, Chase's CO ENTRY DESCR).
    ([(_bofa("SAMPLE ADMINISTRATION LLC", "CLASS ACTION STLMT"), 900.0)], "Bank of America"),
    ([(_bofa("SAMPLE ADMINISTRATION LLC", "DATA BREACH STLMT"), 900.0)], "Bank of America"),
    ([(_bofa("SAMPLE ADMINISTRATION LLC", "CLASS ACTION SETTLE"), 900.0)], "Bank of America"),
    ([(_bofa("SAMPLE ADMINISTRATION LLC", "CLASS ACTION SETLMT"), 900.0)], "Bank of America"),
    ([(_bofa("SAMPLE ADMINISTRATION LLC", "LAWSUIT PYMNT"), 900.0)], "Bank of America"),
    ([(_chase("SAMPLE ADMINISTRATION INC", "CLASS ACTION STLMNT"), 900.0)], "Chase"),
    ([(_bofa("SAMPLE RESORTS INC", "JACKPOT HANDPAY"), 3000.0)], "Bank of America"),
    ([(_bofa("SAMPLE RESORTS INC", "WINNINGS PYMNT"), 3000.0)], "Bank of America"),
    # A repeat.
    (_twice("FABRIKAM INC", "LAWSUIT STLMT"), "Bank of America"),
    (_twice("SAMPLE QSF", "CLASS ACTION STLMT"), "Bank of America"),
    (_twice("FABRIKAM INC", "CLASS ACTION SETL"), "Bank of America"),
    (_twice("FABRIKAM INC", "LITIGATION STLMNT"), "Bank of America"),
    (_twice("FABRIKAM INC", "CLASS ACTION PMNT"), "Bank of America"),
    (_twice("FABRIKAM INC", "CLASS ACTION PYMNTS"), "Bank of America"),
    (_twice("FABRIKAM INC", "LITIGATION DIST"), "Bank of America"),
    (_twice("FABRIKAM INC", "CLASS ACTION DISTR"), "Bank of America"),
    (_twice("FABRIKAM INC", "LAWSUIT PROC"), "Bank of America"),
    (_twice("FABRIKAM INC", "LAWSUIT JUDGMENT"), "Bank of America"),
    (_twice("FABRIKAM INC", "DATA BREACH COMP"), "Bank of America"),
    (_twice("FABRIKAM INC", "WINNINGS PYMNT"), "Bank of America"),
    (_twice("FABRIKAM INC", "JACKPOT HANDPAY"), "Bank of America"),
    # A wire's originator text, a person-to-person memo and a person's PPD entry.
    ([(WF_WIRE.format(org="SAMPLE LAW LLP", obi="LAWSUIT STLMT"), 25000.0)], "Wells Fargo"),
    ([(WF_WIRE.format(org="SAMPLE LAW LLP", obi="CLASS ACTION PYMNT"), 25000.0)], "Wells Fargo"),
    ([(WF_WIRE.format(org="PAT SAMPLE", obi="KRAKEN REDEMPTION"), 9000.0)], "Wells Fargo"),
    ([(WF_WIRE.format(org="PAT SAMPLE", obi="KRAKEN USD"), 9000.0)], "Wells Fargo"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR LAWSUIT STLMT CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT HANDPAY CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR WINNINGS FANTASY FOOTBALL CONF 1234", 900.0)], "Bank of America"),
    ([("ZELLE PAYMENT FROM A SAMPLE FOR WINNINGS POOL CONF 1234", 900.0)], "Bank of America"),
    ([(_bofa("PAT SAMPLE", "CLASS ACTION STLMT", sec="PPD"), 900.0)], "Bank of America"),
    ([(_bofa("PAT SAMPLE", "JACKPOT PYMNT", sec="PPD"), 900.0)], "Bank of America"),
    ([(_bofa("PAT SAMPLE", "KRAKEN ACH", sec="PPD"), 900.0)], "Bank of America"),
])
def test_r37_review_2_an_abbreviated_purpose_after_the_hold_word_keeps_the_hold(rows, bank):
    assert _tiers(rows, bank=bank) == [NON_SALE] * len(rows)


@pytest.mark.parametrize(("rows", "bank", "expected"), [
    # A purpose noun no list names: the purpose arm alone spares the row, which counts and never proves.
    (_twice("FABRIKAM INC", "LAWSUIT WINDFALL"), "Bank of America", [REFUSED, REFUSED]),
    ([(_bofa("SAMPLE ADMINISTRATION LLC", "CLASS ACTION WINDFALL"), 900.0)], "Bank of America", [REFUSED]),
    ([(_chase("SAMPLE RESORTS INC", "JACKPOT WINDFALL"), 3000.0)], "Chase", [REFUSED]),
    ([(WF_WIRE.format(org="FABRIKAM INC", obi="LAWSUIT WINDFALL"), 25000.0),
      (WF_WIRE.format(org="FABRIKAM INC", obi="LAWSUIT WINDFALL").replace("AB12", "CD34"), 25001.0)],
     "Wells Fargo", [REFUSED, REFUSED]),
    ([(_bofa("PAT SAMPLE", "KRAKEN WINDFALL", sec="PPD"), 900.0)], "Bank of America", [REFUSED]),
    # A person-to-person memo is counted whatever it prints: no Q5 or Q6 reads it.
    ([("ZELLE PAYMENT FROM A SAMPLE FOR LAWSUIT WINDFALL CONF 1234", 900.0)], "Bank of America", [P2P]),
    # Controls: the payer region's own trade name (arm (a)) and the vendor spare are no purpose-arm spare.
    (_twice("CONTOSO LITIGATION SUPPORT LLC", "PAYMENT"), "Bank of America", [REPEATS, REPEATS]),
    (_twice("JACKPOT DIGITAL INC", "PAYMENT"), "Bank of America", [REPEATS, REPEATS]),
    (_twice("FABRIKAM INC", "KRAKEN ROBOTICS INV 1234"), "Bank of America", [REPEATS, REPEATS]),
    (_twice("FABRIKAM INC", "SUPPORT SERVICES"), "Bank of America", [REPEATS, REPEATS]),
])
def test_r37_review_2_a_row_only_the_purpose_arm_spares_counts_never_proves(rows, bank, expected):
    assert _tiers(rows, bank=bank) == expected


@pytest.mark.parametrize("word", [
    "SETTLE", "SETTLED", "SETTLEMENT", "SETTLEMENTS", "SETTLMT", "SETLMT", "STLMT", "STLMNT", "SETL",
    "PYMNT", "PYMNTS", "PMNT", "PMNTS", "PAYMNT", "PAYMNTS", "PAYMT", "PAYMTS",
    "HANDPAY", "DIST", "DISTR", "PROC", "PRCDS", "JUDGMENT", "JUDGEMENT", "REDEMPTION", "REDEEM", "COMP",
    "COMPENSATION", "BET", "BETS", "WAGER", "PARLAY", "FANTASY", "POOL", "SUPERBOWL", "LOTTO", "RAFFLE", "ACH", "EFT",
    "WIRE", "USD", "REWARDS", "STAKING",
])
def test_r37_review_2_the_abbreviated_purpose_words_are_no_name_words(word):
    assert tr._TRADE_NAME_PURPOSE_WORD.fullmatch(word), word


@pytest.mark.parametrize("word", ["SETTLE", "SETTLEMENT", "SETTLMT", "SETLMT", "STLMT", "STLMNT", "SETL", "CLAIM", "AWARDS"])
def test_r37_review_2_the_legal_context_reads_every_settlement_spelling(word):
    assert tr._LEGAL_CONTEXT.fullmatch(word), word
    assert tr._LEGAL_NAME_KEEP.fullmatch(word), word


def test_r37_review_2_the_legal_reader_reads_the_classifier_s_settlement_spellings():
    """The legal context and the purpose words read every settlement spelling a processor's settlement credit reads
    (_SETTLEMENT_CREDIT), so the two lists stay in step."""
    for word in ("SETTLE", "SETTLED", "SETTLEMENT", "SETTLEMENTS", "SETTLMT", "SETLMT", "STLMT", "STLMNT"):
        assert tr._SETTLEMENT_CREDIT.fullmatch(word), word
        assert tr._LEGAL_CONTEXT.fullmatch(word), word
        assert tr._TRADE_NAME_PURPOSE_WORD.fullmatch(word), word


@pytest.mark.parametrize(("text", "spared"), [
    # The purpose arm alone spares the row.
    (_bofa("FABRIKAM INC", "LITIGATION SUPPORT"), True),
    (_bofa("FABRIKAM INC", "LAWSUIT WINDFALL"), True),
    (_bofa("SAMPLE RESORTS INC", "JACKPOT WINDFALL"), True),
    (_bofa("PAT SAMPLE", "KRAKEN WINDFALL", sec="PPD"), True),
    ("ZELLE PAYMENT FROM A SAMPLE FOR JACKPOT CANDLES CONF 1234", True),
    # A hold (a purpose word, a context word), the payer region's trade name, a vendor spare or no hold word.
    (_bofa("FABRIKAM INC", "LAWSUIT STLMT"), False),
    (_bofa("FABRIKAM INC", "LITIGATION SUPPORT SETTLEMENT"), False),
    (_bofa("CONTOSO LITIGATION SUPPORT LLC", "PAYMENT"), False),
    (_bofa("JACKPOT DIGITAL INC", "PAYMENT"), False),
    (_bofa("FABRIKAM INC", "KRAKEN ROBOTICS INV 1234"), False),
    (_bofa("FABRIKAM INC", "PAYMENT"), False),
])
def test_r37_review_2_the_purpose_trade_name_reader(text, spared):
    from analysis.transaction_classifier import payer_region

    revenue = revenue_text(normalize_transaction_description(text))
    row = tr._hold_text(revenue)
    assert tr.purpose_trade_name(revenue, row, payer_region(revenue)) is spared


@pytest.mark.parametrize(("text", "fact"), [
    (_bofa("FABRIKAM INC", "LITIGATION SUPPORT"), True),
    (_bofa("FABRIKAM INC", "LAWSUIT STLMT"), False),
    (_bofa("CONTOSO LITIGATION SUPPORT LLC", "PAYMENT"), False),
])
def test_r37_review_2_the_census_reads_the_purpose_trade_name_fact(text, fact):
    record = next(record for record in _records([(text, 900.0)], bank="Bank of America") if record.amount > 0)
    facts = tr.guard_facts(record, revenue_text(record.normalized_description))
    assert facts["purpose_trade_name"] is fact


# Audit round 2, R2-B12 (R36): the gambling reader reads a lottery's prize entry, the unlisted sportsbooks and a
# sportsbook's, a casino's or an online gaming payer's withdrawal or payout; the lottery's retailer spare reads the
# entry, never the agency's name.

@pytest.mark.parametrize(("rows", "bank"), [
    ([(_bofa("CONTOSO STATE LOTTERY", "PRIZE PMT"), 5000.0)], "Bank of America"),
    (_twice("CONTOSO STATE LOTTERY", "PRIZE PMT", 5000.0), "Bank of America"),
    ([(_chase("CONTOSO STATE LOTTERY", "PRIZE PMT"), 5000.0)], "Chase"),
    (_twice("CONTOSO LOTTERY CORPORATION", "PRIZE", 5000.0), "Bank of America"),
    (_twice("CONTOSO LOTTERY COMMISSION", "PRIZE PMT", 5000.0), "Bank of America"),
    ([(_bofa("CONTOSO LOTTERY COMMISSION", "WINNINGS"), 5000.0)], "Bank of America"),
    ([(_bofa("HARD ROCK DIGITAL INC", "WITHDRAWAL"), 900.0)], "Bank of America"),
    (_twice("HARD ROCK DIGITAL INC", "WITHDRAWAL"), "Bank of America"),
    (_twice("BETPARX", "WITHDRAWAL"), "Bank of America"),
    (_twice("BALLY BET", "WITHDRAWAL"), "Bank of America"),
    (_twice("POINTSBET", "WITHDRAWAL"), "Bank of America"),
    ([("VISA MONEY TRANSFER C HARDROCKBET 12345678901234567890 VISA DIRECT FL", 900.0)], "PNC Bank"),
    ([("VISA MONEY TRANSFER C BETPARX 12345678901234567890 VISA DIRECT PA", 900.0)], "PNC Bank"),
    (_twice("FABRIKAM SPORTSBOOK LLC", "WITHDRAWAL"), "Bank of America"),
    (_twice("FABRIKAM CASINO LLC", "PAYOUT"), "Bank of America"),
    (_twice("FABRIKAM ONLINE GAMING", "CASHOUT"), "Bank of America"),
])
def test_r36_a_lottery_prize_or_a_betting_payer_s_withdrawal_is_held(rows, bank):
    assert _tiers(rows, bank=bank) == [NON_SALE] * len(rows)


@pytest.mark.parametrize(("rows", "expected"), [
    # A lottery or a comptroller paying with no prize word, and a retailer's settlement or commission entry.
    (_twice("CONTOSO STATE LOTTERY", "PAYMENT", 5000.0), [REPEATS, REPEATS]),
    (_twice("CONTOSO STATE COMPTROLLER", "LOTTERY", 5000.0), [REPEATS, REPEATS]),
    ([(_bofa("CONTOSO LOTTERY", "RETAILER SETTLEMENT"), 5000.0)], [REFUSED]),
    ([(_bofa("CONTOSO LOTTERY COMMISSION", "COMMISSION"), 5000.0)], [REFUSED]),
    ([(_bofa("CONTOSO STATE LOTTERY", "PRIZE REIMB"), 5000.0)], [NON_SALE]),
    # A casino company's own payments and a casino's payables.
    (_twice("FABRIKAM CASINO RESORT LLC", "PAYMENT"), [REPEATS, REPEATS]),
    ([(_bofa("FABRIKAM CASINO RESORT LLC", "AP PAYMENT"), 900.0)], [REMITTANCE]),
    ([(_bofa("FABRIKAM CASINO", "VENDOR PAY"), 900.0)], [REMITTANCE]),
    (_twice("DRAFTKINGS INC", "WITHDRAWAL"), [NON_SALE, NON_SALE]),
    (_twice("SAMPLE GAMING AND LIQUOR", "ACCOUNTS PAYABLE"), [REMITTANCE, REMITTANCE]),
    # A name that only holds a gambling or a prize word.
    (_twice("FABRIKAM SPORTS BAR", "PAYMENT"), [REPEATS, REPEATS]),
    (_twice("FABRIKAM PRIZE FOODS INC", "PAYMENT"), [REPEATS, REPEATS]),
    (_twice("SAMPLE BETTING SUPPLY INC", "PAYMENT"), [REPEATS, REPEATS]),
])
def test_r36_controls_keep_their_readings(rows, expected):
    assert _tiers(rows, bank="Bank of America") == expected


@pytest.mark.parametrize(("text", "held"), [
    (_bofa("CONTOSO STATE LOTTERY", "PRIZE PMT"), True),
    (_chase("CONTOSO STATE LOTTERY", "PRIZE PMT"), True),
    (_bofa("CONTOSO LOTTERY COMMISSION", "WINNINGS"), True),
    (_bofa("CONTOSO LOTTERY COMMISSION", "COMMISSION"), False),
    (_bofa("STATE LOTTERY", "RETAILER WINNINGS SETTLEMENT"), False),
    (_chase("CONTOSO LOTTERY", "SWEEP"), False),
    # With no entry field the whole row is the retailer spare's scope.
    ("ACH CREDIT STATE LOTTERY PRIZE PAYMENT 12345", True),
    ("ACH CREDIT STATE LOTTERY COMMISSION 12345", False),
    # Review round 1: but never the agency's name (LOTTERY COMMISSION), so a prize it pays holds; a retailer word after
    # the name, or a commission after the prize word, keeps the retailer's reading.
    ("ACH CREDIT STATE LOTTERY COMMISSION PRIZE PAYMENT 12345", True),
    ("ACH CREDIT CONTOSO LOTTERY COMMISSION WINNINGS 12345", True),
    ("ACH CREDIT STATE LOTTERY COMMISSION RETAILER SETTLEMENT 12345", False),
    ("ACH CREDIT STATE LOTTERY COMMISSION COMMISSION 12345", False),
    ("ACH CREDIT STATE LOTTERY PRIZE COMMISSION 12345", False),
    (_bofa("GOLDEN NUGGET ONLINE GAMING", "WITHDRAWAL"), True),
    (_bofa("FLIFF INC", "REDEMPTION"), True),
    (_bofa("FABRIKAM CASINO RESORT LLC", "PAYMENT"), False),
    (_bofa("FABRIKAM CASINO", "WITHDRAWAL"), True),
    (_bofa("FABRIKAM SPORTS BOOK", "WDRL"), True),
    (_bofa("FABRIKAM ONLINE GAMING", "CASH OUT"), True),
    (_bofa("FABRIKAM SUPPLY INC", "CASINO PAYOUT"), False),
    (_bofa("FABRIKAM CASINO", "VENDOR PAYOUT"), False),
])
def test_r36_the_gambling_reader(text, held):
    revenue = revenue_text(normalize_transaction_description(text))
    assert tr.gambling_payout(revenue, tr._hold_text(revenue)) is held


@pytest.mark.parametrize(("text", "expected"), [
    # Audit round 2, R2-B12 review round 1 (R36): on a layout that prints no entry field, the agency's name supplies no
    # retailer word, so its prize is held as on Bank of America's and Chase's layouts; its bare row keeps its reading.
    ("ACH CREDIT STATE LOTTERY COMMISSION PRIZE PAYMENT 12345", NON_SALE),
    ("ACH CREDIT STATE LOTTERY COMMISSION 12345", REFUSED),
])
def test_r36_review_an_agency_s_name_on_a_row_with_no_entry_spares_no_prize(text, expected):
    assert _one(text, 5000.0, bank="PNC Bank") == expected


def test_r36_the_entry_field_reader_is_the_premium_reader_s():
    text = revenue_text(normalize_transaction_description(_bofa("CONTOSO STATE LOTTERY", "PRIZE PMT")))
    assert tr._layout_entry(text).strip() == "PRIZE PMT"
    text = revenue_text(normalize_transaction_description(_chase("CONTOSO STATE LOTTERY", "PRIZE PMT")))
    assert tr._layout_entry(text).strip() == "PRIZE PMT"
    assert tr._layout_entry("ACH CREDIT STATE LOTTERY PRIZE PAYMENT 12345") == ""
