"""Audit fix batch B8 (true revenue spec §6.3, §7.0, §8.1, §8.2, §15, §20): non-operating money and statement
boilerplate. Gambling and prediction-market payouts and a crypto exchange's or a retail brokerage's withdrawal are no
money the business earned from its operations (the MCA principle of 2026-09-30, the standing owner-money rule): held
(I28); an HSA distribution and a life insurer's annuity are personal income (I28); a lawsuit's, a class action's or a
claims administrator's settlement, and a law firm's settlement proceeds, are held, while a bare SETTLEMENT stays
counted (I44); a settlement or closing agent's payment is a title firm's (I44); equipment-auction and car-buyer seller
payouts are §15's deferred sources, counted and never verified (I45, OQ4); statement furniture a parser glued onto a
row is cut before classification (I46), and the plural TRANSFERS is transfer wording (I46, Q2); a glued Canada Carbon
Rebate is held (I56, GOV); and the GOV follow-ups: the IRS's interest on a refund is non_revenue, RBC's cut provincial
payment code is a personal benefit (class B). Fabricated rows only, in the banks' printed formats; public names only
where a bank prints its own or a registry lists them (sportsbooks, prediction markets, crypto exchanges, brokerages,
claims administrators, auctioneers and car buyers, each public)."""
from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from analysis import true_revenue as tr
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions, normalize_transaction_description, revenue_text

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
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
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


# I45 (OQ4): equipment-auction and car-buyer seller payouts are §15's deferred sources: counted, never verified.

def test_a_repeated_equipment_auction_seller_payout_is_counted_never_verified():
    rows = [(_bofa("RITCHIE BROS", "SELLER PMT", "1234567"), 15000.0),
            (_bofa("RITCHIE BROS", "SELLER PMT", "7654321"), 12000.0)]
    assert _tiers(rows, bank="Bank of America") == [REFUSED, REFUSED]


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


# I56 (GOV class D): a glued Canada Carbon Rebate is held, as its spaced spelling is; WSIB to a clinic is counted.

@pytest.mark.parametrize("text", ["CDACARBONREBATE CCR", "CDA CARBON REBATE CCR", "CANADA CARBON REBATE",
                                  "DIRECT DEPOSIT CDACARBONREBATE"])
def test_a_canada_carbon_rebate_is_held(text):
    assert _one(text, 120.0, bank="TD Canada Trust") == NON_SALE


@pytest.mark.parametrize("text", [
    "CONTOSO CARBON WORKS LLC DES:PAYMENT ID:1234567 INDN:NORTHWIND BAKERY LLC CO ID:1234567890 CCD",
    "WORK COMP BOARD WSIB EME",
])
def test_a_carbon_surname_or_a_wsib_payment_keeps_its_reading(text):
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
