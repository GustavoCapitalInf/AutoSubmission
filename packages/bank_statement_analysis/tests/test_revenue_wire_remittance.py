"""Classification 5.5 (true revenue spec §7.9, T19): incoming wires whose remittance cites an invoice, a PO, an order
or goods; the channel, the purposes, every veto; third-party book transfers read as incoming wires. Fabricated rows
only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.classification import credit_predicates
from analysis.descriptor import payer
from analysis.descriptor import rails
from analysis.descriptor import lexical
from analysis.descriptor import words
from analysis import description_text
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction

BOFA = ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:20540102001234 SEQ:1234/5678 ORIG:{orig} ID:99887766 "
        "SND BK:SAMPLE BANK ID:0123 PMT DET:{purpose}")
CHASE = "FEDWIRE CREDIT VIA: SAMPLE BANK/0123 B/O: {orig} REF: CHASE NYC/CTR/BNF=CONTOSO LLC /OBI={purpose} IMAD: 1"


def _credit(printed: str, *, holder: str | None = "CONTOSO TRADING LLC"):
    return classify_transaction(printed, 25000.0, account_name=holder, direction="credit")


@pytest.mark.parametrize("purpose", [
    "INVOICE 1234", "INV 5678", "INVOIC E 1234", "PO 45210", "PURCHASE ORDER 88", "ORDER NO 1234", "FACTURA 12",
    "PAGO PROVEEDOR", "PAYMENT FOR GOODS", "PRO FORMA 12",
])
def test_an_incoming_wire_citing_a_sale_verifies(purpose):
    for layout in (BOFA, CHASE):
        record = _credit(layout.format(orig="FABRIKAM EXPORTS LLC", purpose=purpose))
        assert record.revenue_classification == "verified_revenue", (layout[:20], purpose)
        assert record.revenue_match_method in ("wire_remittance_purpose", "payer_remittance_descriptor")


@pytest.mark.parametrize(("orig", "purpose"), [
    ("FABRIKAM CAPITAL LLC", "INVOICE 1234"),         # a financing root
    ("FABRIKAM CAPI TAL", "INVOICE 1234"),            # wrapped across a line
    ("FABRIKAM FUN DING", "INVOICE 1234"),
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234 ADJ"),     # an adjustment
    ("FABRIKAM EXPORTS LLC", "INVOICE 1234 INVESTMENT"),
    ("FABRIKAM EXPORTS LLC", "RETURN INVOICE 1234"),
    ("CONTOSO HOLDINGS LLC", "INVOICE 1234"),         # the holder's brand word: an affiliate
    ("FABRIKAM EXPORTS LLC", "MONEY ORDER 1234"),     # not an order number
    ("FABRIKAM EXPORTS LLC PO 4521", "PAYMENT"),       # a PO number in the originator's address is no purpose
])
def test_the_wire_vetoes(orig, purpose):
    assert _credit(BOFA.format(orig=orig, purpose=purpose)).revenue_classification != "verified_revenue"


def test_a_wire_from_a_person_citing_an_invoice_verifies_and_other_channels_do_not():
    assert _credit(BOFA.format(orig="JOHN SMITH", purpose="INVOICE 1234"), holder=None).revenue_classification == (
        "verified_revenue")
    assert _credit("ZELLE PAYMENT FROM JOHN SMITH MEMO WIRE INVOICE 1234 CONF 1").revenue_classification != (
        "verified_revenue")
    assert _credit("UNKNOWN WIRE CREDIT").revenue_classification == "unverified_deposit"


def test_a_returned_wire_is_never_revenue():
    records = classify_statement_transactions(Statement(account_name="CONTOSO TRADING LLC", transactions=[
        Transaction(date="2054-03-02", description="WIRE TRANSFER OUT FABRIKAM EXPORTS LLC INVOICE 1234",
                    amount=-25000.0, direction="debit"),
        Transaction(date="2054-03-04", description=BOFA.format(orig="FABRIKAM EXPORTS LLC", purpose="RTN INVOICE 1234"),
                    amount=25000.0, direction="credit"),
    ]))
    assert records[1].revenue_classification == "non_revenue"


BOOK = "BOOK TRANSFER CREDIT B/O: {orig} SAMPLEVILLE ST 12345 REF: {purpose}"


def test_a_third_party_book_transfer_is_an_incoming_wire_on_the_owner_s_yes(monkeypatch):
    third_party = BOOK.format(orig="FABRIKAM EXPORTS LLC", purpose="INVOICE 1234")
    own = BOOK.format(orig="CONTOSO TRADING LLC", purpose="INVOICE 1234")
    monkeypatch.setattr(credit_predicates, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", True)
    monkeypatch.setattr(rails, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", True)
    monkeypatch.setattr(words, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", True)
    assert _credit(third_party).revenue_classification == "verified_revenue"
    assert _credit(own).revenue_classification == "non_revenue"
    assert _credit("BOOK TRANSFER CREDIT").revenue_classification == "non_revenue"
    monkeypatch.setattr(credit_predicates, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", False)
    monkeypatch.setattr(rails, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", False)
    monkeypatch.setattr(words, "THIRD_PARTY_BOOK_TRANSFER_AS_WIRE", False)
    assert _credit(third_party).revenue_classification == "non_revenue"


def test_an_incoming_funds_transfer_names_its_sender():
    record = _credit("FUNDS TRANSFER CREDIT TT FABRIKAM EXPORTS LLC REF INVOICE 1234")
    assert record.revenue_classification == "verified_revenue"
    assert _credit("FUNDS TRANSFER FROM SAVINGS 1234").revenue_classification == "non_revenue"


# ---------------------------------------------------------------------------------------------------------------------
# §14.1 (§7.9, review I5): the wire verifier's 40 cases, the false-revenue reviewer's hazard groups G1 to G11 and its
# four party-name rows, and the wire verifier's adversarial rows, transcribed (fabricated names, numbers and amounts;
# the banks' layouts kept). Each is one credit in a statement of its own.
# ---------------------------------------------------------------------------------------------------------------------
FEDWIRE = ("Fedwire Credit Via: Sample Bank/123456789 B/O: {orig} Ref: Chase Nyc/Ctr/Bnf={bnf} Tampa FL 33602 "
           "US/Ac-000012345678 Rfb=Notprovided Obi=/Uri/{obi} Imad: 0105Mmqfmp2B000123 Trn: 1234567890Ff")
BOFA_IN = ("WIRE TYPE:WIRE IN DATE: 540105 TIME:1012 ET TRN:2054010500123456 SEQ:2054010500654321/004512 "
           "ORIG:{orig} ID:1234567890 SND BK:{bank} ID:021000021 PMT DET:{det}")
SANTANDER = "USD WIRE IN FROM {bank} ACCT * 1234 {orig} REF {ref}"
WELLS = "WT Fed#01234 {bank} /Org={orig} Srf# 0123456789Mfp0123 Trn#0123456789 Rfb# {ref}"


def _one(bank: str, holder: str, printed: str):
    [record] = classify_statement_transactions(Statement(
        bank=bank, account_name=holder, account_number="XXXX1234", period_start="2054-01-01",
        period_end="2054-01-31", beginning_balance=1000.0, ending_balance=13345.0,
        transactions=[Transaction(date="2054-01-05", description=printed, amount=12345.0, direction="credit",
                                  running_balance=13345.0)]))
    return record


def _outcome(record) -> str:
    return {"verified_revenue": "verified", "non_revenue": "non_revenue"}.get(record.revenue_classification, "stays")


FORTY = [
    ("verified", "Bank of America", "FABRIKAM FOODS LLC",
     BOFA_IN.format(orig="CONTOSO TRADING INTL", bank="SAMPLE NATIONAL BANK, NA", det="BMG OF 01/05/54 INV10421,10422")),
    ("verified", "Bank of America", "FABRIKAM FOODS LLC",
     BOFA_IN.format(orig="NORTHWIND HARBOR SUITES", bank="SAMPLE CREDIT UNION", det="INVOICE: NW204 MAINTEN ANCE")),
    ("verified", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC 12345, US", bnf="Northwind Labs, LLC", obi="Invoice S104")),
    ("verified", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso For Congress Denver CO 80202", bnf="Northwind Media LLC", obi="Invoic E No.: 10421")),
    ("verified", "Chase", "BUSINESS COMPLETE CHECKING",
     "Chips Credit Via: Sample Bank, N.A./0959 B/O: Contoso Marketing Management,Llsampleville CO 80000 Ref: "
     "Nbnf=Northwind Consulting LLC Sampleton FL 33000-1234 US/Ac-000012345678 Org=/000012345678901 Sampleville CO "
     "80000 Ogb=Sample Merchants Bank, N.A. San Francisco CA US Obi=/Uri/Inv Oices 10421 And 10422 Paid "
     "Ssn: 00123456 Trn: 1234567890Fc"),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO DE CREDIT", orig="CONTOSO SRL", ref="/INV/10421/54")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EUROPE", orig="CONTOSO GROUP SP", ref="PO 4521")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE NBD BANK PJ", orig="CONTOSO GENERAL", ref="Payment for goo")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE SAN J", orig="CONTOSO COSTA", ref="BALANCE ORDER 2")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.", orig="CONTOSO TRADING", ref="PAGO PROVEEDOR")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE CONTIN", orig="CONTOSO SRL", ref="/INV/OP.123456789012")),
    # §7.9 drops the bare 'PI <digits>' pro-forma form: the verifier's positive stays unverified.
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE PICHIN", orig="CONTOSO CIA", ref="PI 10421")),
    ("verified", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.A.", orig="CONTOSO ARCHO", ref="COMPRA MERCADE")),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.A.", orig="CONTOSO LENDING SA", ref="/INV/OP.123456789012")),
    ("verified", "Capital One", "FABRIKAM LLC", "Wire transfer deposit CONTOSO GROUP LLC 540105 INV 10421"),
    ("verified", "CIBC", "FABRIKAM LTD", "WIRE TSF 1234567 CONTOSO FROZEN FOODS LTD INV-1042-54"),
    ("stays", "BMO", "FABRIKAM INC", "Incoming Wire Payment, INCOMING WIRE PAYMENT, CA, 1234567 ONTARIO INC"),
    ("stays", "Bluevine", "FABRIKAM LLC", "Incoming Wire from CONTOSO SUPPLY SER"),
    ("stays", "Citizens Bank", "BUSINESS ADVISOR CHECKING",
     "INCOMING WIRE TRANSFER (MTS NO.123456789012) ORIGINATOR NAME : CONTOSO SPE II LLC ORIG TO BNF INFO: "
     "FED ID# : 20540105MMQFMP2N000123"),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE ASIA BANK", orig="CONTOSO OVERSEAS", ref="ADVANCE PAYMEN")),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE THAI BANK", orig="CONTOSO HEALTH", ref="COST OF GOODS")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Real Estate Services Ll", bnf="Northwind Development Group LLC",
                    obi="Ref: 1234 Sample Foun Dat Ion Draw")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Merchant Funding LLC", bnf="Northwind Grocery Corp", obi="Inv 104211")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Capital Partners LLC", bnf="Northwind Freight LLC", obi="Invoice 104211")),
    ("stays", "Wells Fargo", "FABRIKAM LLC",
     "WT Fed#01234 Sample Commercial Bank /Org=1/Contoso Road Capital Management I Srf# 0123456789Mfp0123+ "
     "Trn#0123456789 Rfb# Inv 10421"),
    ("non_revenue", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Bank Loan Dept", bnf="Northwind Trucks LLC", obi="Inv 104211")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Northwind Industries LLC Jersey City NJ", bnf="Northwind Industries LLC",
                    obi="Inv 104211")),
    ("stays", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK NA", orig="NORTHWIND TRADING", ref="INV 10421")),
    ("non_revenue", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC", bnf="Northwind Labs LLC", obi="Refund Inv 104211")),
    ("stays", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC", bnf="Northwind Labs LLC", obi="Return of Overpayment Inv 104211")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO HOLDINGS LP", bank="SAMPLE BANK", det="INV 2054 DISTRIBUTION")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO PROPERTIES LLC", bank="SAMPLE BANK", det="INV 1042 INTEREST")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO PROPERTIES LLC", bank="SAMPLE BANK", det="REPAYMENT INV 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO TENANT LLC", bank="SAMPLE BANK", det="SECURITY DEPOSIT INVOICE 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO SISTER CO LLC", bank="SAMPLE BANK", det="INTERCOMPANY INVOICE 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO LAW PLLC", bank="SAMPLE BANK", det="COURT ORDER 1042")),
    ("stays", "Bank of America", "FABRIKAM LLC",
     BOFA_IN.format(orig="CONTOSO SERVICING LLC", bank="SAMPLE TRUST", det="INV 104211")),
    ("stays", "Santander Bank", "FABRIKAM TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK", orig="CONTOSO FUNDING SPV", ref="ORDER 10421")),
    ("non_revenue", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Kapitus LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    # Not a wire: §7.5 verifies an ACH credit that prints an invoice number with its channel word.
    ("verified", "Sample Bank", "FABRIKAM LLC", "ACH CREDIT CONTOSO FOODS INV 10421"),
]


@pytest.mark.parametrize(("expected", "bank", "holder", "printed"), FORTY)
def test_the_wire_verifier_s_forty_cases(expected, bank, holder, printed):
    assert _outcome(_one(bank, holder, printed)) == expected


HOLDER = "NORTHWIND LABS LLC"
#: The false-revenue reviewer's hazard rows: none is revenue whose verification the rules may give.
HAZARDS = [
    ("G1 returned wire /RETN/", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK NA", det="/RETN/AC04/ INV 10421")),
    ("G1 RTN", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK NA", det="RTN WIRE INV 10421 ACCT CLOSED")),
    ("G1 /REJT/", "Bank of America", HOLDER,
     BOFA_IN.format(orig="SAMPLE BANK ASIA", bank="SAMPLE BANK NA", det="/REJT/AC01/ PO 4521")),
    ("G1 recall", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Components Ltd", bnf="Northwind Labs LLC", obi="Recall Of Payment Invoice 10421")),
    ("G1 RTN on Chase", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Sample Bank", bnf="Northwind Labs LLC", obi="Rtn Inv 104211 Beneficiary Acct Closed")),
    ("G1 RTN on Santander", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EUROPE", orig="CONTOSO GROUP SP", ref="RTN PO 4521")),
    ("G1 unable to apply", "Wells Fargo", HOLDER,
     WELLS.format(bank="Sample Bank", orig="Contoso Components Ltd", ref="Unable To Apply Inv 10421")),
    ("G1 RETURN word", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK NA", det="RETURN INV 10421")),
    ("G2 bank draw", "Bank of America", "NORTHWIND DEVELOPMENT LLC",
     BOFA_IN.format(orig="SAMPLE COMMUNITY BANK", bank="SAMPLE COMMUNITY BANK", det="DRAW 3 INV 10421 PLUMBING")),
    ("G2 draw via title", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Title Agency LLC", bnf="Northwind Development LLC",
                    obi="Draw #4 Invoices 10421 10422")),
    ("G2 drawdown", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK NA", orig="SAMPLE BANK NA", ref="DRAWDOWN PO 4521")),
    ("G3 bank SCF", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CITIBANK NA", bank="CITIBANK NA", det="SCF EARLY PAYMENT INV 10421 10422")),
    ("G3 supply chain", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Sample Bank Na Supply Chain", bnf="Northwind Labs LLC", obi="Invoice 10421 Discounted")),
    ("G3 eCapital", "CIBC", "NORTHWIND LTD", "WIRE TSF 1234567 ECAPITAL CORP INV-1042-54"),
    ("G3 C2FO", "Bank of America", HOLDER, BOFA_IN.format(orig="C2FO", bank="SAMPLE BANK", det="EARLY PAY INV 10421")),
    ("G3 Taulia", "Bank of America", HOLDER,
     BOFA_IN.format(orig="TAULIA INC", bank="SAMPLE BANK", det="INVOICE 10421 EARLY PAYMENT")),
    ("G3 factor named Solutions", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Business Solutions LLC", bnf="Northwind Freight LLC",
                    obi="Inv 10421 10422 10423 Less Fee")),
    ("G4 PI settlement", "Bank of America", "NORTHWIND LAW PLLC IOLTA",
     BOFA_IN.format(orig="CONTOSO MUTUAL CO", bank="SAMPLE BANK", det="PI 104211 J SAMPLE")),
    ("G4 PI claim", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Casualty Co", bnf="Northwind Law Group PLLC", obi="PI 1042119 Sample")),
    ("G5 person goods and services", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK", det="GOODS AND SERVICES")),
    ("G6 sister company", "Bank of America", HOLDER,
     BOFA_IN.format(orig="NORTHWIND HOLDINGS LLC", bank="SAMPLE BANK", det="INV 1042")),
    ("G6 foreign parent", "Chase", "BUSINESS COMPLETE CHECKING",
     "Chips Credit Via: Sample Bank/0959 B/O: Northwind Gmbh Hamburg De Ref: Nbnf=Northwind Labs LLC Tampa FL "
     "33602 US/Ac-000012345678 Org=/DE12345678 Ogb=Sample Bank Ag Obi=/Inv/10421 Ssn: 00123456 Trn: 1234567890Fc"),
    ("G6 Santander one-word holder", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK PANAMA", orig="NORTHWIND LATAM", ref="INVOICE 1042")),
    ("G7 compensation", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EAST", orig="CONTOSO PACKAGING", ref="COMPENSATION PO 4521")),
    ("G7 price adjustment", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK", det="PRICE ADJUSTMENT INV 10421")),
    ("G7 RMA", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO COMPONENTS LTD", bank="SAMPLE BANK", det="RMA 5521 INV 10421")),
    ("G7 deposit back", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK EAST", orig="CONTOSO PACKAGING", ref="DEPOSIT BACK PO 4521")),
    ("G7 shortage", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Foods Inc", bnf="Northwind Grocery Corp", obi="Shortage Inv 10421")),
    ("G8 pay order", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK KARACHI", det="PAY ORDER 104211")),
    ("G8 support order", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK", det="SUPPORT ORDER 104211")),
    ("G8 transfer order", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK", orig="JOHN Q SAMPLE", ref="TRANSFER ORDER 1042")),
    ("G9 payoff surplus", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO BANK", bank="SAMPLE BANK", det="PAYOFF SURPLUS INV 10421")),
    ("G9 bridge note", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO PARTNERS LP", bank="SAMPLE BANK", det="BRIDGE NOTE INV 1")),
    ("G9 SAFE", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO VENTURES LP", bank="SAMPLE BANK", det="SAFE INV 2 OF 3")),
    ("G9 subscription order", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JOHN Q SAMPLE", bank="SAMPLE BANK", det="SUBSCRIPTION ORDER 1042 SERIES A")),
    ("G10 Zelle memo wire", "Chase", "BUSINESS COMPLETE CHECKING",
     "Zelle Payment From John Q Sample 1234567 wire inv 1042"),
    ("G10 ACH from a company named WIRE", "Chase", "BUSINESS COMPLETE CHECKING",
     "ORIG CO NAME:CONTOSO WIRE AND CABLE ORIG ID:1234567890 DESC DATE:540105 CO ENTRY DESCR:PAYMENT SEC:CCD "
     "TRACE#:123456789012345 EED:540105 IND ID:1042 IND NAME:NORTHWIND LABS LLC TRN: 1234567890TC INV 10421"),
    ("G10 wire fee rebate", "Bank of America", HOLDER, "WIRE FEE ADJ INV 10421"),
    ("G11 title sale proceeds", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Title Agency LLC", bnf="Northwind Holdings LLC", obi="Invoice 1042 123 Main St Sale")),
    ("G11 earnest money", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Title Agency LLC", bnf="Northwind Holdings LLC", obi="Earnest Money PO 4521")),
    ("party: holder named INVOICE", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Business Group LLC", bnf="Northwind Invoice Services LLC", obi="Deal 104211")),
    ("party: originator GOODS AND SERVICES", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO GOODS AND SERVICES", bank="SAMPLE BANK", det="104211")),
    ("party: originator Invoice Cloud", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO INVOICE CLOUD INC", bank="SAMPLE BANK", det="104211")),
    ("party: originator Order 66", "Bank of America", HOLDER,
     BOFA_IN.format(orig="ORDER 66 HOLDINGS LLC", bank="SAMPLE BANK", det="104211")),
    ("wrapped CAPI TAL", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Capi Tal Partners LLC", bnf="Northwind Labs LLC", obi="Invoice 104211")),
    ("wrapped FUN DING", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Fun Ding Group LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    ("sister company sharing its first word", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Northwind Holdings Group LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    ("address PO 4521", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Supply LLC PO 4521 Tampa FL", bnf="Northwind Labs LLC", obi="Notprovided")),
    ("INV 1234 ADJ", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO SUPPLY INC", bank="SAMPLE BANK", det="INV 1234 ADJ")),
    ("Zelle memo wire invoice", "Sample Bank", "FABRIKAM LLC",
     "Zelle payment from JOHN Q SAMPLE memo wire for invoice 1042"),
    ("unknown wire credit", "Sample Bank", "FABRIKAM LLC", "Unknown wire credit"),
]


@pytest.mark.parametrize(("label", "bank", "holder", "printed"), HAZARDS)
def test_the_wire_hazards_never_verify(label, bank, holder, printed):
    assert _outcome(_one(bank, holder, printed)) != "verified", label


#: §7.9's recorded residuals: printed words cannot tell these from a sale (the spec states the person's invoice
#: wire; the others are the neutral-name funder, the root-free factor, a template-named holder's own account and
#: the MCA 'purchase price' order). They verify; the precision sample (§14.5) reads their strata, and the ledger
#: round of Task S1.5 carries the receivables financiers (Stenn, eCapital). Stenn's root-free invoice wire left this list
#: when Task S1.5 admitted Stenn to the ledger's factoring group (the test below).
RESIDUALS = [
    ("person citing an invoice (stated)", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="1/John Q Sample 2/US/Tampa", bnf="Northwind Labs LLC", obi="Inv 1042")),
    ("person, payment for goods", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="BANCO SAMPLE S.A.", orig="JOHN Q SAMPLE", ref="PAYMENT FOR GOODS")),
    ("a person's holding company citing an invoice", "Bank of America", HOLDER,
     BOFA_IN.format(orig="JQS FAMILY HOLDINGS LLC", bank="SAMPLE BANK", det="INV 1042")),
    ("funder name cut before its root", "Santander Bank", "NORTHWIND TRADING CORP",
     SANTANDER.format(bank="SAMPLE BANK", orig="CONTOSO BUSINESS", ref="INV 10421")),
    ("MCA purchase price with an order id", "Bank of America", HOLDER,
     BOFA_IN.format(orig="CONTOSO VENTURES LLC", bank="SAMPLE BANK", det="PURCHASE PRICE ORDER 10421")),
    ("root-free unregistered factor", "Chase", "BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Business Solutions LLC", bnf="Northwind Labs LLC", obi="Inv 104211")),
    ("own account, holder name a product template", "Bank of America", "BUSINESS ADVANTAGE FUNDAMENTALS",
     BOFA_IN.format(orig="FABRIKAM LABS LLC", bank="SAMPLE BANK", det="INV 1234")),
]


@pytest.mark.parametrize(("label", "bank", "holder", "printed"), RESIDUALS)
def test_the_recorded_wire_residuals_verify_and_are_sampled(label, bank, holder, printed):
    assert _outcome(_one(bank, holder, printed)) == "verified", label


def test_a_listed_invoice_financier_s_wire_citing_an_invoice_stays_flagged_as_factoring():
    # §7.9: Task S1.5 admitted Stenn to the ledger's factoring group, which closes the recorded residual of its root-free
    # invoice wire: the wire no longer verifies; it stays an unverified deposit, flagged as factoring.
    record = _one("Santander Bank", "NORTHWIND TRADING CORP",
                  SANTANDER.format(bank="SAMPLE BANK UK", orig="STENN ASSETS UK", ref="/INV/10421/54"))
    assert _outcome(record) == "stays"
    assert (record.revenue_classification, record.classification) == ("unverified_deposit", "factoring")


# ---------------------------------------------------------------------------------------------------------------------
# S2.3 review (fixes 2 and 3): the wire vetoes read a wire whose reference is glued to WIRE, and a wire whose purpose
# reads as a customer or invoice descriptor (§6.1 step 11) as they read every other wire (§7.9).
# ---------------------------------------------------------------------------------------------------------------------
GLUED_REFERENCE = "123456W1234567"


@pytest.mark.parametrize(("printed", "anchored_state"), [
    ("WIRE FROM FABRIKAM HOLDINGS LLC PAYMENT INV 1234 DISTRIBUTION", "unverified_deposit"),
    ("WIRE FROM FABRIKAM PROPERTIES LLC PAYMENT INV 1042 INTEREST", "unverified_deposit"),
    ("WIRE FROM FABRIKAM TITLE AGENCY LLC VENDOR PAYMENT", "unverified_deposit"),
    ("WIRE FROM FABRIKAM SUPPLY LLC SECURITY DEPOSIT INV 1042 PAYMENT", "unverified_deposit"),
    # A person's invoice wire: step 12's company-form gate refuses both rows; §7.9 states that the anchored row
    # verifies at step 14, whose channel test (N1) reads an anchored label only, so the glued row stays unverified.
    ("WIRE FROM JOHN SMITH PAYMENT INV 1234", "verified_revenue"),
])
def test_a_reference_glued_to_wire_answers_to_the_wire_vetoes(printed, anchored_state):
    anchored, glued = _credit(printed), _credit(GLUED_REFERENCE + printed)
    assert (anchored.revenue_classification, anchored.revenue_match_method) != (
        "verified_revenue", "payer_remittance_descriptor")
    assert anchored.revenue_classification == anchored_state
    assert glued.revenue_classification == "unverified_deposit", glued.revenue_match_method


@pytest.mark.parametrize(("printed", "holder"), [
    # S2.3 re-review (minor 1, §5.2): WIRE in the receiver's (the holder's) name makes no row a wire.
    ("CONTOSO SUPPLY DES:INVOICE PAYMENT ID:1 INDN:NORTHWIND WIRE & TAX LLC CO ID:1 CCD", "NORTHWIND WIRE & TAX LLC"),
    ("CONTOSO SUPPLY DES:INVOICE PAYMENT ID:1 INDN:NORTHWIND WIRE CAPITAL LLC CO ID:1 CCD",
     "NORTHWIND WIRE CAPITAL LLC"),
])
def test_wire_in_the_holder_s_name_never_applies_the_wire_vetoes(printed, holder):
    assert _credit(printed, holder=holder).revenue_classification == "verified_revenue"


def test_a_genuine_glued_wire_still_verifies_as_its_anchored_twin():
    printed = "WIRE FROM FABRIKAM SUPPLY LLC PAYMENT INV 1234"
    anchored, glued = _credit(printed), _credit(GLUED_REFERENCE + printed)
    assert anchored.revenue_classification == glued.revenue_classification == "verified_revenue"


STEP_11_WIRES = [
    ("BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Capital Partners LLC", bnf="Northwind Labs LLC", obi="Invoice Payment 104211")),
    ("BUSINESS COMPLETE CHECKING",
     FEDWIRE.format(orig="Contoso Merchant Funding LLC", bnf="Northwind Labs LLC", obi="Invoice Paid 104211")),
    (HOLDER, BOFA_IN.format(orig="CONTOSO PROPERTIES LLC", bank="SAMPLE BANK", det="INVOICE PAID 1042 INTEREST")),
    (HOLDER, BOFA_IN.format(orig="CONTOSO TITLE AGENCY LLC", bank="SAMPLE BANK", det="INVOICE PAYMENT 1042")),
    (HOLDER, BOFA_IN.format(orig="CONTOSO SISTER CO LLC", bank="SAMPLE BANK", det="INTERCOMPANY INVOICE PAYMENT 1042")),
    (HOLDER, BOFA_IN.format(orig="CONTOSO SERVICING LLC", bank="SAMPLE BANK", det="ACCOUNTS RECEIVABLE 104211")),
]


@pytest.mark.parametrize(("holder", "printed"), STEP_11_WIRES)
def test_an_invoice_descriptor_on_a_wire_answers_to_the_wire_vetoes(holder, printed):
    assert _credit(printed, holder=holder).revenue_classification == "unverified_deposit"


def test_a_plain_invoice_payment_wire_still_verifies():
    record = _credit("WIRE FROM CONTOSO SUPPLY LLC INVOICE PAYMENT 1234", holder=HOLDER)
    assert record.revenue_classification == "verified_revenue"


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 3, R3-B07 (R3-14; §8.5, §20 A3-G): a relaying bank that prints BANKING ('<X> BANKING CORP') or a
# non-English bank word (BANCO, BANCA, BANQUE, BANCAIRE, SPARKASSE) is a bank by its form, so the customer it relays
# after ORG is the wire's sender (the holder test, the financing roots and Q5 read that customer); a numbered company
# relayed after ORG is read too ('1234567 B C LTD'). Holder NORTHWIND LABS INC on Chase; fabricated banks, customers and
# references.
# ---------------------------------------------------------------------------------------------------------------------
R314_HOLDER = "NORTHWIND LABS INC"
R314_RELAY = "BOOK TRANSFER CREDIT B/O: {bank} ORG:/0000000000000001 {customer} OGB: {ogb} TRN 000{n}"
R314_BANKING = "NORDKAPP BANKING CORPORATION LIMITED SYDNEY"
R314_NAMED = ("counted_flagged", "wire_named_sender")
R314_REPEAT = ("verified", "repeat_wire_sender")
R314_FINANCING = ("excluded_pending_review", "financing_named_payer")
R314_HOLDER_HELD = ("excluded_pending_review", "holder_name")
R314_NON_ENGLISH = [
    "BANCO SOLARIEGO SA", "BANCA ALPINA DI TRENTO SPA", "BANQUE LACUSTRE SA", "UNION BANCAIRE DU LAC SA",
    "SPARKASSE RHEINTAL",
]
R314_BOFA = ("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:20540302001234 ORIG:{orig} ID:0001 SND BK:{bank} ID:0002 "
             "PMT DET:SAMPLE {n}")


def _r314(rows, *, bank="Chase", holder=R314_HOLDER):
    records = classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount, direction="credit")
        for index, (text, amount) in enumerate(rows)
    ]))
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method) for record in records]


def _r314_text(printed: str) -> str:
    return lexical.revenue_text(description_text.normalize_transaction_description(printed))


def _banking_relay(customer: str, n: int = 1) -> str:
    return R314_RELAY.format(bank=R314_BANKING, customer=customer, ogb="NORDKAPP BANKING CORP", n=n)


def test_r3_14_a_banking_corporation_s_relayed_customer_is_the_sender_and_verifies_on_repeat():
    rows = [(_banking_relay("CONTOSO TIMBER LLC", 1), 12345.67), (_banking_relay("CONTOSO TIMBER LLC", 2), 9876.54)]
    assert _r314(rows) == [R314_REPEAT, R314_REPEAT]
    assert payer.wire_relayed_customer(_r314_text(rows[0][0])) == "CONTOSO TIMBER LLC"
    assert payer.payer_region(_r314_text(rows[0][0])) == "CONTOSO TIMBER LLC"


def test_r3_14_the_holder_relayed_by_a_banking_corporation_is_held_as_the_holder_s_name():
    assert _r314([(_banking_relay(R314_HOLDER), 12345.67)]) == [R314_HOLDER_HELD]


def test_r3_14_a_funder_relayed_by_a_banking_corporation_is_held_as_financing():
    assert _r314([(_banking_relay("FABRIKAM CAPITAL FUNDING LLC"), 12345.67)]) == [R314_FINANCING]


def test_r3_14_two_customers_of_one_banking_relay_are_read_each_on_its_own_name():
    rows = [(_banking_relay("SAMPLE CONTOSO", 1), 12345.67), (_banking_relay("FABRIKAM HOLDINGS LLC", 2), 9876.54)]
    # Each is its own sender: the person-shaped one is counted, never verified with the other.
    assert _r314(rows) == [R314_NAMED, R314_NAMED]
    assert [payer.payer_region(_r314_text(text)) for text, _amount in rows] == [
        "SAMPLE CONTOSO", "FABRIKAM HOLDINGS LLC"]


@pytest.mark.parametrize("bank", R314_NON_ENGLISH)
def test_r3_14_a_non_english_bank_s_relayed_customer_is_read(bank):
    from analysis.descriptor.lexical import bank_by_form

    printed = R314_RELAY.format(bank=bank, customer="CONTOSO TIMBER LLC", ogb=bank, n=1)
    assert bank_by_form(bank)
    assert payer.payer_region(_r314_text(printed)) == "CONTOSO TIMBER LLC"
    assert _r314([(printed, 12345.67)]) == [R314_NAMED]
    # The holder relayed by such a bank is the holder's own money, held.
    assert _r314([(R314_RELAY.format(bank=bank, customer=R314_HOLDER, ogb=bank, n=1), 12345.67)]) == [
        R314_HOLDER_HELD]


@pytest.mark.parametrize("bank", [*R314_NON_ENGLISH, "NORDKAPP BANKING CORP", "FIRST HARBOR BANK"])
def test_r3_14_a_bank_that_names_no_customer_is_held_as_a_bank_originated_wire(bank):
    assert _r314([(f"BOOK TRANSFER CREDIT B/O: {bank} REF: 1234 TRN 0001", 12345.67)]) == [R314_FINANCING]


R314_RBC = ("BOOK TRANSFER CREDIT B/O: ROYAL BANK OF CANADA PAYMENT CENTRE TORONTO ON CANADA ORG: 000000000001 "
            "{customer} REF: RFB GOODS AND SERVICES TRN 000{n}")


@pytest.mark.parametrize(("customer", "region"), [("1234567 B.C. LTD.", "1234567 B C LTD"),
                                                  ("1234567 BC LTD", "1234567 BC LTD")])
def test_r3_14_a_numbered_company_relayed_by_a_bank_is_the_sender_counted_never_verified(customer, region):
    rows = [(R314_RBC.format(customer=customer, n=1), 2345.67), (R314_RBC.format(customer=customer, n=2), 3456.78)]
    assert payer.payer_region(_r314_text(rows[0][0])) == region
    assert payer.numbered_company(_r314_text(rows[0][0]))
    assert _r314(rows) == [R314_NAMED, R314_NAMED]


def test_r3_14_banking_after_a_company_name_is_no_bank_and_q5_never_reads_it_as_one_company():
    from analysis.descriptor.lexical import bank_by_form

    assert not bank_by_form("CONTOSO BANKING SOLUTIONS LLC")
    assert bank_by_form("WESTPAC BANKING CORP") and bank_by_form("NORDKAPP BANKING CORPORATION LIMITED")
    rows = [(R314_BOFA.format(orig="CONTOSO BANKING SOLUTIONS LLC", bank="SAMPLE BANK", n=n), amount)
            for n, amount in ((1, 4321.09), (2, 5432.10))]
    assert _r314(rows[:1], bank="Bank of America") == [R314_NAMED]
    # §8.5: a sender that names a bank word (BANKING among them now) never verifies by repetition.
    assert _r314(rows, bank="Bank of America") == [R314_NAMED, R314_NAMED]


@pytest.mark.parametrize(("bank", "printed"), [
    ("Santander Bank", "USD WIRE IN FROM BANCO SAMPLE ACCT 0001 CONTOSO TIMBER LLC REF SAMPLE {n}"),
    ("Bank of America", R314_BOFA.replace("{orig}", "CONTOSO TIMBER LLC").replace("{bank}", "BANCO SAMPLE")),
])
def test_r3_14_controls_a_sending_bank_s_word_is_no_originator(bank, printed):
    # Santander's sending bank after WIRE IN FROM and Bank of America's SND BK: unchanged readings.
    assert _r314([(printed.format(n=1), 4321.09)], bank=bank) == [R314_NAMED]
    assert _r314([(printed.format(n=1), 4321.09), (printed.format(n=2), 5432.10)], bank=bank) == [
        R314_REPEAT, R314_REPEAT]


def test_r3_14_control_a_company_whose_name_holds_bank_keeps_its_reading():
    printed = R314_BOFA.replace("{orig}", "LEFT BANK BAKERY LLC").replace("{bank}", "SAMPLE BANK")
    assert _r314([(printed.format(n=1), 4321.09)], bank="Bank of America") == [R314_NAMED]


def test_r3_14_control_a_broker_dealer_relay_stays_held():
    # Standard G2 and §7.5: a clearing broker's wire is the owner's brokerage money until reviewed (not changed here).
    printed = ("BOOK TRANSFER CREDIT B/O: NATIONAL FINANCIAL SERVICES LLC ORG: Z00000001 SAMPLE CONTOSO OGB: NATIONAL "
               "FINANCIAL SERVICES LLC REF: TUITION TRN 0001")
    assert _r314([(printed, 4321.09)]) == [R314_FINANCING]


def test_r3_14_control_a_q6_payer_named_banking_counts_once_and_verifies_only_by_repetition():
    printed = "CONTOSO BANKING SERVICES INC DES:PAYMENT ID:000{n} INDN:NORTHWIND LABS INC CO ID:0000000001 CCD"
    assert _r314([(printed.format(n=1), 1234.56)], bank="Bank of America") == [
        ("counted_flagged", "named_payer_one_off")]
    assert _r314([(printed.format(n=1), 1234.56), (printed.format(n=2), 2345.67)], bank="Bank of America") == [
        ("verified", "named_payer_repeats")] * 2
