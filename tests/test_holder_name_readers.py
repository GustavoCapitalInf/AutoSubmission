"""Audit round 2, batch R2-B05 (R04 parts 2 and 4; true revenue spec §5.2, §20): the holder's name read from page 1 on
the banks that published none. Fourteen more parsers read `Statement.holder_name` from the mailing address their bank
prints on page 1 (analysis/holder_name.py's readers, each bank with its own anchor; RBC's two issues count as one, and
Desjardins' reader is held for the owner), TD Canada Trust's French issue reads the English issue's mail-routing
anchor, and Chase, Navy Federal, TD Bank and PNC gain a page-1 block fallback where their anchor reads none. A reader
reads the address line or the mailing block, never a second line that is no DBA (an owner's or a co-holder's name),
drops a contact (ATTN), and returns None rather than guess (a page that prints only a product). `account_name` is
unchanged, and only the holder's name moves in the extraction.

Owner ruling 2026-10-02 (the underwriter's Q10), audit round 2, R2-OW10 (spec §9.1, §20): every reader returns a
`HolderReading` (the name and the account title it drops after the name), and its parser publishes the title as
`Statement.account_title` wherever it publishes that reading's name, from the same anchor and never from any other
text; the holder's names are unchanged.

Fabricated pages only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE, SAMPLEVILLE; 555 phone numbers, zero-filled codes and
account numbers, X0X 0X0 postal codes, 2054 dates), in the shapes the banks print; public names only where a bank prints
its own (its name, its contact line, its mail-routing code's letters)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis import (
    bluevine, bmo_us_activity, bofa, capital_one, chase, cibc, citibusiness, community_section, first_citizens,
    huntington, navy_federal, pnc, rbc, santander, scotia, square_checking, td_can, td_canada_french, td_us, truist,
    us_bank, wells,
)
from analysis.holder_name import (
    HolderReading, first_page, holder_from_address_line, mailing_line_after, page_lines, read_address_block,
    read_address_line, read_mailing_line_after, read_name,
)
from ocr.document import StatementMarkdown

#: A reading that names nobody (and so prints no title).
NONE = HolderReading(None, None)


def _document(*pages: str) -> str:
    """The pages as the statement reading hands them to a parser (its page markers included)."""
    return StatementMarkdown(source_file="sample.pdf", model="sample", pages=list(pages)).to_markdown()


# --- the shared page-1 readers ------------------------------------------------------------------------------------

def test_first_page_is_the_text_before_the_second_page_marker():
    markdown = _document("PAGE ONE LINE\nSECOND LINE", "PAGE TWO LINE")
    assert page_lines(first_page(markdown)) == ["PAGE ONE LINE", "SECOND LINE"]
    # A parser handed one page's text with no marker reads all of it.
    assert first_page("ONLY TEXT\n") == "ONLY TEXT\n"


def test_page_lines_collapse_whitespace_and_drop_blank_lines():
    assert page_lines("  CONTOSO   TRADING LLC  \n\n   \n100  SAMPLE ST ") == ["CONTOSO TRADING LLC", "100 SAMPLE ST"]


@pytest.mark.parametrize(("line", "holder"), [
    # A unit printed before the street ends the name, as a house number does.
    ("JORDAN SAMPLE SUITE 200 100 SAMPLE RD SAMPLEVILLE ON X0X 0X0", "JORDAN SAMPLE"),
    ("CONTOSO TRADING LLC STE 5 100 SAMPLE RD SAMPLEVILLE TX 75000-0001", "CONTOSO TRADING LLC"),
    # A unit word with a number that a legal form follows is a name's (a numbered company).
    ("NORTHWIND UNIT 7 LLC 100 SAMPLE RD SAMPLEVILLE TX 75000-0001", "NORTHWIND UNIT 7 LLC"),
])
def test_a_unit_before_the_street_starts_the_address(line, holder):
    assert holder_from_address_line(line) == holder


def test_the_mailing_line_after_an_anchor_closes_on_a_state_and_zip():
    import re

    anchor = re.compile(r"^SAMPLE BANK RETURN ADDRESS\b")
    page = "SAMPLE BANK RETURN ADDRESS PO BOX 100\nCONTOSO TRADING LLC 100 SAMPLE ST SAMPLEVILLE MI 48000-0001\n"
    assert mailing_line_after(_document(page), anchor) == "CONTOSO TRADING LLC"
    assert mailing_line_after(_document(page.replace(" MI 48000-0001", "")), anchor) is None
    assert mailing_line_after(_document("FILLER", page), anchor) is None
    # R2-OW10: the reading carries the title the line prints after the name, and nothing where no name is read.
    titled = page.replace("CONTOSO TRADING LLC 100", "CONTOSO TRADING LLC OPERATING ACCOUNT 100")
    assert read_mailing_line_after(_document(titled), anchor) == ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")
    assert read_mailing_line_after(_document(titled.replace(" MI 48000-0001", "")), anchor) == NONE


# --- Bank of America ----------------------------------------------------------------------------------------------

BOFA_PAGE = (
    "P.O. Box 0000 Sampleville, DE 19000\n"
    "Customer service information\n"
    "1.888.555.0100\n"
    "CONTOSO TRADING LLC 100 SAMPLE LN SAMPLEVILLE, TX 75000-0001\n"
    "Bank of America, N.A. P.O. Box 0000 Sampleville, FL 33000-0000\n"
    "Your Business Advantage Fundamentals Banking\n"
    "for May 1, 2054 to May 31, 2054 Account number: 0000 0000 0000\n"
    "{name}"
    "Account summary\n"
)


@pytest.mark.parametrize(("name", "holder"), [
    ("CONTOSO TRADING LLC\n", "CONTOSO TRADING LLC"),
    ("CONTOSO TRADING LLC DBA NORTHWIND GOODS\n", "CONTOSO TRADING LLC DBA NORTHWIND GOODS"),
    ("JORDAN SAMPLE\n", "JORDAN SAMPLE"),
    # A page that prints only the product: the summary heading follows the period line.
    ("", None),
])
def test_bank_of_america_reads_the_line_after_the_period_line(name, holder):
    assert bofa._holder_reading(_document(BOFA_PAGE.format(name=name))).name == holder


def test_bank_of_america_reads_page_one_only():
    assert bofa._holder_reading(_document("Your statement", BOFA_PAGE.format(name="CONTOSO TRADING LLC\n"))) == NONE


# --- Wells Fargo --------------------------------------------------------------------------------------------------

WELLS_PAGE = (
    "Initiate Business Checking SM\n"
    "May 31, 2054 Page 1 of 5\n"
    "Questions?\n"
    "Available by phone 24 hours a day, 7 days a week\n"
    "{mailing}"
    "1-800-555-0100\n"
    "Write: Wells Fargo Bank, N.A. (000)\n"
    "P.O. Box 0000 Sampleville, OR 97000-0000\n"
)


@pytest.mark.parametrize(("mailing", "holder"), [
    ("CONTOSO TRADING LLC 100 SAMPLE PKWY STE 100-200 SAMPLEVILLE TX 75000-0001\n", "CONTOSO TRADING LLC"),
    ("JORDAN SAMPLE DBA NORTHWIND GOODS 100 SAMPLE DR SAMPLEVILLE GA 30000-0001\n",
     "JORDAN SAMPLE DBA NORTHWIND GOODS"),
    # No mailing line before the bank's own address: nothing is read (the bank's P.O. box never is).
    ("", None),
])
def test_wells_fargo_reads_the_mailing_line_after_its_questions_panel(mailing, holder):
    assert wells._holder_reading(_document(WELLS_PAGE.format(mailing=mailing))).name == holder


# --- U.S. Bank ----------------------------------------------------------------------------------------------------

def _us_bank_page(mailing: str) -> str:
    return (
        "Business Statement\nAccount Number:\nP.O. Box 0000 Sampleville, Minnesota 55000-0000\nPage 1 of 5\n"
        f"{mailing}%\nTo Contact U.S. Bank\n24-Hour Business Solutions:\n800-555-0100\n"
    )


@pytest.mark.parametrize(("mailing", "holder"), [
    ("CONTOSO TRADING LLC 100 SAMPLE BLVD NW STE C SAMPLEVILLE MN 55000\n", "CONTOSO TRADING LLC"),
    # An attention contact after the name is dropped, with or without a name after it.
    ("CONTOSO TRADING LLC ATTN: 100 SAMPLE BLVD NW SAMPLEVILLE MN 55000\n", "CONTOSO TRADING LLC"),
    ("CONTOSO TRADING LLC ATTN JORDAN SAMPLE 100 SAMPLE BLVD SAMPLEVILLE MN 55000\n", "CONTOSO TRADING LLC"),
    ("JORDAN SAMPLE DBA NORTHWIND GOODS 100 SAMPLE CT SAMPLEVILLE CA 91000-0001\n", "JORDAN SAMPLE DBA NORTHWIND GOODS"),
    # A line that opens on the contact names no holder this reader can place.
    ("ATTN: JORDAN SAMPLE 100 SAMPLE BLVD SAMPLEVILLE MN 55000\n", None),
    ("", None),
])
def test_us_bank_reads_the_mailing_line_before_its_contact_panel_and_drops_attn(mailing, holder):
    reading = us_bank._holder_reading(_document(_us_bank_page(mailing)))
    assert reading.name == holder
    # R2-OW10: a contact is never a title.
    assert reading.title is None


@pytest.mark.parametrize(("mailing", "holder", "title"), [
    # Audit round 3, R3-B11 (R3-61): a contact glued to its marker is dropped as a spaced one is, never published as
    # a title; a contact whose words are the premium-trust designation itself is the account's title (the
    # underwriter's Q10 of 2026-10-02), in any spacing.
    ("CONTOSO TRADING LLC ATTN:JORDAN SAMPLE 100 SAMPLE BLVD SAMPLEVILLE MN 55000\n", "CONTOSO TRADING LLC", None),
    ("CONTOSO INSURANCE AGENCY INC ATTN: PREMIUM TRUST ACCOUNT 100 SAMPLE BLVD SAMPLEVILLE MN 55000\n",
     "CONTOSO INSURANCE AGENCY INC", "PREMIUM TRUST ACCOUNT"),
    ("CONTOSO INSURANCE AGENCY INC ATTN:PREMIUM TRUST ACCOUNT 100 SAMPLE BLVD SAMPLEVILLE MN 55000\n",
     "CONTOSO INSURANCE AGENCY INC", "PREMIUM TRUST ACCOUNT"),
])
def test_us_bank_reads_a_contact_by_its_words_not_its_spacing(mailing, holder, title):
    assert us_bank._holder_reading(_document(_us_bank_page(mailing))) == HolderReading(holder, title)


# --- RBC and Banque Royale ----------------------------------------------------------------------------------------

@pytest.mark.parametrize(("line", "holder"), [
    ("RBBDA00000_0000000 E D 00000 00000 CONTOSO TRADING INC. 100 SAMPLE DR SAMPLEVILLE ON X0X 0X0",
     "CONTOSO TRADING INC."),
    ("RBBDA00000_0000000 F D 00000 00000 1234-5678 QUEBEC INC. 100 RUE SAMPLE SAMPLEVILLE QC X0X 0X0",
     "1234-5678 QUEBEC INC."),
    # A numbered company keeps its number; the account designation after its legal form is dropped.
    ("RBBDA00000_0000000 E D 00000 00000 1234567 ONTARIO INC. CAD CHEQUING ACCOUNT 100 SAMPLE WAY SAMPLEVILLE ON "
     "X0X 0X0", "1234567 ONTARIO INC."),
    # The personal code prints a sequence and one more field.
    ("RBPDA00000_0000000_000 E I 000 00000 00000 JORDAN SAMPLE 100 SAMPLE ST SAMPLEVILLE BC X0X 0X0", "JORDAN SAMPLE"),
    ("RBBDA00000_0000000 E D 00000 00000 JORDAN SAMPLE SUITE 200 100 SAMPLE RD SAMPLEVILLE ON X0X 0X0",
     "JORDAN SAMPLE"),
    # No address after the name: nothing is read.
    ("RBBDA00000_0000000 E I 00000 00000 CONTOSO TRADING LTD. GET NEW ADDRESS", None),
    ("Account number: 00000 000-000-0", None),
])
def test_rbc_reads_the_holder_after_its_mail_routing_code(line, holder):
    page = f"ROYAL BANK OF CANADA P.O. BOX 0000 SAMPLEVILLE ON X0X 0X0\nBusiness Account Statement\n{line}\n"
    assert rbc._holder_reading(_document(page)).name == holder


# --- Scotiabank ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("page", "holder"), [
    ("100 SAMPLE STREET 00000 SAMPLEVILLE ON X0X 0X0 555-0100\n"
     "CONTOSO TRADING INC. 100 SAMPLE RD SAMPLEVILLE ON X0X0X0 Statement Of: Account Number: From: To: Business "
     "Account 00000 00000 00\n", "CONTOSO TRADING INC."),
    # The summary header on its own line: the mailing line is the one before it.
    ("100 SAMPLE STREET 00000 SAMPLEVILLE ON X0X 0X0 555-0100\nCONTOSO TRADING INC. 100 SAMPLE GATE SE SAMPLEVILLE "
     "AB X0X0X0\nStatement Of: Account Number: From: To: Business Account 00000 00000 00\n", "CONTOSO TRADING INC."),
    ("Statement Of: Account Number: From: To: Business Account 00000 00000 00\n", None),
])
def test_scotiabank_reads_the_mailing_line_before_its_summary_header(page, holder):
    assert scotia._holder_reading(_document(page)).name == holder


# --- Bluevine -----------------------------------------------------------------------------------------------------

def test_bluevine_reads_the_name_after_its_phone_line_and_never_the_owner_line_under_it():
    page = (
        "Bluevine Inc.\n100 Sample St, Suite 100\nSampleville, NJ 07000\nwww.bluevine.com\n"
        "+1 (555) 555-0100 CONTOSO TRADING LLC\njordan sample\n100 Sample Terrace\nSampleville, FL 33000\n"
        "Account statement\n"
    )
    assert bluevine._holder_reading(_document(page)) == ("CONTOSO TRADING LLC", None)
    assert bluevine._holder_reading(_document(page.replace("+1 (555) 555-0100 CONTOSO TRADING LLC\n", ""))) == NONE


# --- Huntington ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("mailing", "holder"), [
    ("CONTOSO TRADING LLC DBA NORTHWIND GOODS 100 SAMPLE ST SAMPLEVILLE MI 48000-0001\n",
     "CONTOSO TRADING LLC DBA NORTHWIND GOODS"),
    ("CONTOSO, INC. 100 SAMPLE SAMPLEVILLE MI 48000-0001\n", "CONTOSO, INC."),
    ("", None),
])
def test_huntington_reads_the_mailing_line_after_the_bank_s_own_address(mailing, holder):
    page = (
        "THE HUNTINGTON NATIONAL BANK PO BOX 0000 A0A0A0 SAMPLEVILLE OH 43000-0000\n"
        f"{mailing}Have a Question or Concern?\n1-800-555-0100\n"
    )
    assert huntington._holder_reading(_document(page)).name == holder


# --- Capital One --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("page", "holder"), [
    ("Speak to a dedicated business solutions expert at 1-888-555-0100 - a one-stop number.\n"
     "CONTOSO TRADING AND SUPPLY LLC 100 SAMPLE CIR SAMPLEVILLE LA 71000\nACCOUNT SUMMARY FOR PERIOD\n",
     "CONTOSO TRADING AND SUPPLY LLC"),
    # The designation in brackets after the legal form is no part of the name.
    ("CONTOSO TRADING LLC (RECEIVABLES) 100 SAMPLE ST NW SUITE 5 SAMPLEVILLE DC 20000\n"
     "Speak to a dedicated business solutions expert at 1-888-555-0100 - a one-stop number.\n"
     "ACCOUNT SUMMARY FOR PERIOD\n", "CONTOSO TRADING LLC"),
    # Nothing closes on a state and ZIP before the summary.
    ("Speak to a dedicated business solutions expert at 1-888-555-0100.\nACCOUNT SUMMARY FOR PERIOD\n"
     "100 SAMPLE CIR SAMPLEVILLE LA 71000\n", None),
])
def test_capital_one_reads_the_mailing_line_before_its_account_summary(page, holder):
    assert capital_one._holder_reading(_document(page)).name == holder


# --- CIBC ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("page", "holder"), [
    ("CIBC Account Statement\nCONTOSO TRADING LTD.\nFor Apr 1 to Apr 30, 2054\n", "CONTOSO TRADING LTD."),
    ("Relevé de compte CIBC\nJORDAN SAMPLE\nDu 1 nov au 30 nov 2054\n", "JORDAN SAMPLE"),
    # The period line right after the title: no name printed.
    ("CIBC Account Statement\nFor Apr 1 to Apr 30, 2054\n", None),
])
def test_cibc_reads_the_line_after_its_statement_title(page, holder):
    assert cibc._holder_reading(_document(page)).name == holder


# --- Square -------------------------------------------------------------------------------------------------------

SQUARE_HEAD = "Square Checking Routing number: 000000000\nAccount number: 0000\nChecking statement May 1 - May 31, 2054\n"


@pytest.mark.parametrize(("block", "holder"), [
    ("Contoso Trading LLC\n100 Sample Ave NE Sampleville, MI 49000-0001\n", "Contoso Trading LLC"),
    # A DBA line is the holder's trade name; any other second line (an owner's) is never read.
    ("Contoso Trading LLC\nDBA Northwind Goods\n100 Sample Ave NE Sampleville, MI 49000-0001\n",
     "Contoso Trading LLC DBA Northwind Goods"),
    ("Contoso Trading LLC\nJordan Sample\n100 Sample Ave NE Sampleville, MI 49000-0001\n", "Contoso Trading LLC"),
    # The block run onto one line.
    ("Contoso Trading LLC 100 Sample Rd Sampleville, MO 63000\n", "Contoso Trading LLC"),
    # A page that prints no mailing block under the period line.
    ("Location Starting balance Activities Ending balance $0.00 6 $0.00\n$0.00 Starting balance\n", None),
])
def test_square_reads_the_mailing_block_under_its_period_line(block, holder):
    reading = square_checking._holder_reading(_document(SQUARE_HEAD + block + "Starting balance\n"))
    assert reading.name == holder
    # R2-OW10: an owner's line is never a title.
    assert reading.title is None


# --- Mission Valley -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("line", "holder"), [
    ("CONTOSO TRADING INC Page 1 of 6", "CONTOSO TRADING INC"),
    ("Page 1 of 6", None),
])
def test_mission_valley_reads_the_name_before_its_page_counter(line, holder):
    page = (
        f"Statement Ending 02/27/2054\n{line}\nAccount Number:XXXXXXXX0000\n"
        "CONTOSO TRADING INC SAMPLE LOCATION 100 N SAMPLE AVE SAMPLEVILLE CA 91000-0001\n"
    )
    assert community_section._mission_valley_holder_reading(_document(page)).name == holder


# --- BMO (US activity layout) -------------------------------------------------------------------------------------

@pytest.mark.parametrize(("mailing", "holder"), [
    ("CONTOSO TRADING L.L.C. 100 S SAMPLE AVE SAMPLEVILLE IL 60000\n", "CONTOSO TRADING L.L.C."),
    ("Date January 01, 2054 through January 31, 2054 Primary Account Number\n", None),
])
def test_bmo_us_reads_the_mailing_line_after_its_contact_line(mailing, holder):
    page = (
        "How to reach us\nP.O. BOX 0000, SAMPLEVILLE, IL 60000-0000 Return Service Requested\n"
        f"bmo.com/contact 888-555-0100\n{mailing}"
    )
    assert bmo_us_activity._holder_reading(_document(page)).name == holder


# --- Santander ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("line", "holder"), [
    ("CONTOSO TRADING INC Account # 00000000000", "CONTOSO TRADING INC"),
    # The header's primary account number prints a colon and names nobody.
    ("BUSINESS BANKING ANALYZED CHECKING Statement Period 02/01/54 - 02/28/54", None),
])
def test_santander_reads_the_name_before_its_account_number(line, holder):
    page = (
        "Statement Period 02/01/54 TO 02/28/54 Primary Account #: 00000000000\n"
        "CONTOSO TRADING INC 100 SAMPLE RD SAMPLEVILLE CT 06000\n"
        f"{line}\nBalances\n"
    )
    assert santander._holder_reading(_document(page)).name == holder


# --- Citibank -----------------------------------------------------------------------------------------------------

CITI_HEADER = "000 CITIBANK, N. A. Account 00000000 Statement Period {between} Relationship Manager Citibusiness Service " \
              "Center (877) 555-0100 Page 1 of 3"


@pytest.mark.parametrize(("page", "holder"), [
    # The mailing line under the header.
    (CITI_HEADER.format(between="Mar 1 - Mar 31, 2054") + "\nCONTOSO TRADING LLC 100 SAMPLE DRIVE SAMPLEVILLE MD "
     "20900-0001\n", "CONTOSO TRADING LLC"),
    # The block run onto the header line, before the relationship manager's label.
    (CITI_HEADER.format(between="May 1 - May 31, 2054 CONTOSO TRADING, LLC 100 SAMPLE AVE # 200") + "\n",
     "CONTOSO TRADING, LLC"),
    # The name split around the period's dates, its DBA after them.
    (CITI_HEADER.format(between="CONTOSO TRADING LLC Jun 1 - Jun 30, 2054 DBA NORTHWIND 100 SAMPLE PLAZA") + "\n",
     "CONTOSO TRADING LLC DBA NORTHWIND"),
    (CITI_HEADER.format(between="Mar 1 - Mar 31, 2054") + "\nCitiBusiness ACCOUNT AS OF MARCH 31, 2054\n", None),
])
def test_citibank_reads_the_mailing_address_of_its_header(page, holder):
    assert citibusiness._holder_reading(_document(page)).name == holder


# --- TD Canada Trust (French issue) -------------------------------------------------------------------------------

@pytest.mark.parametrize(("line", "holder"), [
    ("CONTOSO S.E.N.C. 100 RUE SAMPLE O SUITE 3 SAMPLEVILLE PQ X0X 0X0", "CONTOSO S.E.N.C."),
    ("1234-5678 QUEBEC INC. 100 BOUL SAMPLE SAMPLEVILLE PQ X0X 0X0", "1234-5678 QUEBEC INC."),
    ("CONTOSO S.E.N.C.", None),
])
def test_td_canada_trust_s_french_issue_reads_the_holder_after_its_mail_routing_code(line, holder):
    page = f"SAMPLEVILLE-OUEST\nTel: 1-800-555-0100\nTDCDA00000_0000000_000 F R 00000 00000\n{line}\nReleve de compte\n"
    assert td_canada_french._holder_reading(_document(page)).name == holder


# --- the page-1 block fallbacks of the B9 readers ------------------------------------------------------------------

CHASE_DDA_PAGE = (
    "January 01, 2054 through January 31, 2054\n"
    "JPMorgan Chase Bank, N.A. P O Box 0000 Sampleville, IN 46000 - 0000\n"
    "Account Number:\nCUSTOMER SERVICE INFORMATION\n"
    "00000000 DDA 000 000 00000 NNNNNNNNNNN 1 000000000 00 0000\n"
    "CONTOSO HOLDINGS OF SAMPLEVILLE,\n100 SAMPLE HWY\nSAMPLEVILLE FL 33000\n00000000000000000000\n"
    "*start*summary\n"
)


def test_chase_reads_page_one_s_block_after_the_account_type_code_line():
    assert chase._holder_reading(_document(CHASE_DDA_PAGE)).name == "CONTOSO HOLDINGS OF SAMPLEVILLE"
    # The fallback reads page 1 only.
    assert chase._holder_reading(_document("Statement", CHASE_DDA_PAGE)) == NONE
    # The plant code's own line still reads first.
    plant = CHASE_DDA_PAGE.replace(
        "January 01, 2054 through January 31, 2054\n",
        "00000000 DRE 000 000 00000 NNNNNNNNNNN 1 000000000 00 0000\nFABRIKAM GOODS LLC\n100 SAMPLE ST\n"
        "SAMPLEVILLE TX 75000-0001\n00000000000000000000\n",
    )
    assert chase._holder_reading(_document(plant)).name == "FABRIKAM GOODS LLC"


@pytest.mark.parametrize("page", [
    # The name and address run on after the mail-routing code.
    "Statement of Account\nRouting Number: 0000-0000-0\n#AAAAAAA #000000A0A0AAA0A0#000AAA00A CONTOSO TRADING LLC 100 "
    "SAMPLE RD UNIT 10 SAMPLEVILLE TX 76000-0001\nQuestions about this Statement? Toll-free in the U.S. 1-888-555-0100\n",
    # The block after the code, the panel's lines between its lines.
    "Statement of Account\n#AAAAAAA #000000A0A0AAA0A0#000AAA00A\nRouting Number: 0000-0000-0\nCONTOSO TRADING LLC\n"
    "Questions about this Statement?\n8 SAMPLE GREEN\nToll-free in the U.S. 1-888-555-0100\nSTE A\n"
    "For toll-free numbers when overseas,\nSAMPLEVILLE DE 19000\n",
])
def test_navy_federal_reads_page_one_s_block_after_its_mail_routing_code(page):
    assert navy_federal._holder_reading(_document(page)) == ("CONTOSO TRADING LLC", None)
    assert navy_federal._holder_reading(_document(page.replace("CONTOSO TRADING LLC", "100 SAMPLE PLACE"))) == NONE


TD_BANK_PAGE = (
    "STATEMENT OF ACCOUNT\nPage: 1 of 7 Statement Period: Mar 01 2054-Mar 31 2054 Primary Account #: 000-0000000\n"
    "CONTOSO TRADING LLC NORTHWIND GOODS PO BOX 100 SAMPLEVILLE SC 29000\n"
    "TD Business Simple Checking\n{name}Account # 000-0000000\nACCOUNT SUMMARY Beginning Balance 0.00\n"
)


@pytest.mark.parametrize(("name", "holder"), [
    ("CONTOSO TRADING LLC NORTHWIND GOODS\n", "CONTOSO TRADING LLC"),
    # The product line above the number: page 1's mailing line never opens on it.
    ("", None),
])
def test_td_bank_reads_the_name_above_an_account_number_on_its_own_line(name, holder):
    assert td_us._holder_reading(_document(TD_BANK_PAGE.format(name=name))).name == holder


def test_td_bank_s_fallback_needs_the_mailing_line_to_open_on_the_name():
    page = TD_BANK_PAGE.format(name="CONTOSO TRADING LLC NORTHWIND GOODS\n").replace(
        "CONTOSO TRADING LLC NORTHWIND GOODS PO BOX", "FABRIKAM GOODS LLC PO BOX"
    )
    assert td_us._holder_reading(_document(page)) == NONE


@pytest.mark.parametrize(("street", "holder"), [
    ("100 SAMPLE AVE convenient way to manage your cash flow 24\n", "CONTOSO MARINE LLC"),
    ("convenient way to manage your cash flow 24\n", None),
])
def test_pnc_reads_page_one_s_block_after_its_enclosure_count(street, holder):
    page = (
        "PO Box 000 Sampleville, PA 15000-0000 Business Checking\nPNC Bank\nPage 1 of 12\nNumber of enclosures: 0\n"
        f"CONTOSO MARINE LLC PNC Online Banking is an easy and\n{street}SAMPLEVILLE FL 33000-0001 hours a day.\n"
    )
    assert pnc._holder_reading(_document(page)).name == holder


# --- a page that prints only a product names nobody ---------------------------------------------------------------

PRODUCT_ONLY_PAGE = "Business Advantage Fundamentals Banking\nBusiness Checking\nAccount summary\nPage 1 of 3\n"


@pytest.mark.parametrize("reader", [
    bofa._holder_reading, wells._holder_reading, us_bank._holder_reading, rbc._holder_reading,
    scotia._holder_reading, bluevine._holder_reading, huntington._holder_reading, capital_one._holder_reading,
    cibc._holder_reading, square_checking._holder_reading, community_section._mission_valley_holder_reading,
    bmo_us_activity._holder_reading, santander._holder_reading, citibusiness._holder_reading,
    td_canada_french._holder_reading, chase._holder_reading, navy_federal._holder_reading, td_us._holder_reading,
    pnc._holder_reading,
])
def test_a_page_that_prints_only_a_product_reads_no_holder(reader):
    assert reader(_document(PRODUCT_ONLY_PAGE, "CONTOSO TRADING LLC 100 SAMPLE ST SAMPLEVILLE TX 75000-0001")) == NONE


# --- R2-OW10: each reader publishes the title its own anchor prints after the name ----------------------------------

_TITLED_PAGES = [
    (bofa._holder_reading, BOFA_PAGE.format(name="CONTOSO TRADING LLC OPERATING ACCOUNT\n"),
     ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")),
    (wells._holder_reading,
     WELLS_PAGE.format(mailing="CONTOSO TRADING LLC PREMIUM TRUST ACCOUNT 100 SAMPLE PKWY SAMPLEVILLE TX 75000-0001\n"),
     ("CONTOSO TRADING LLC", "PREMIUM TRUST ACCOUNT")),
    (us_bank._holder_reading,
     _us_bank_page("CONTOSO TRADING LLC OPERATING ACCOUNT 100 SAMPLE BLVD SAMPLEVILLE MN 55000\n"),
     ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")),
    (rbc._holder_reading,
     "ROYAL BANK OF CANADA P.O. BOX 0000 SAMPLEVILLE ON X0X 0X0\nBusiness Account Statement\nRBBDA00000_0000000 E D "
     "00000 00000 1234567 ONTARIO INC. CAD CHEQUING ACCOUNT 100 SAMPLE WAY SAMPLEVILLE ON X0X 0X0\n",
     ("1234567 ONTARIO INC.", "CAD CHEQUING ACCOUNT")),
    (scotia._holder_reading,
     "CONTOSO TRADING INC. TRUST ACCOUNT 100 SAMPLE RD SAMPLEVILLE ON X0X0X0 Statement Of: Account Number: From: To: "
     "Business Account 00000 00000 00\n", ("CONTOSO TRADING INC.", "TRUST ACCOUNT")),
    (bluevine._holder_reading,
     "Bluevine Inc.\n+1 (555) 555-0100 CONTOSO TRADING LLC OPERATING ACCOUNT\njordan sample\n100 Sample Terrace\n",
     ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")),
    (huntington._holder_reading,
     "THE HUNTINGTON NATIONAL BANK PO BOX 0000 A0A0A0 SAMPLEVILLE OH 43000-0000\n"
     "CONTOSO TRADING LLC PAYROLL ACCOUNT 100 SAMPLE ST SAMPLEVILLE MI 48000-0001\nHave a Question or Concern?\n",
     ("CONTOSO TRADING LLC", "PAYROLL ACCOUNT")),
    (capital_one._holder_reading,
     "CONTOSO TRADING LLC (RECEIVABLES) 100 SAMPLE ST NW SUITE 5 SAMPLEVILLE DC 20000\nACCOUNT SUMMARY FOR PERIOD\n",
     ("CONTOSO TRADING LLC", "(RECEIVABLES)")),
    (cibc._holder_reading, "CIBC Account Statement\nCONTOSO TRADING LTD. TRUST ACCOUNT\nFor Apr 1 to Apr 30, 2054\n",
     ("CONTOSO TRADING LTD.", "TRUST ACCOUNT")),
    (square_checking._holder_reading,
     SQUARE_HEAD + "Contoso Trading LLC\nOperating Account\n100 Sample Ave NE Sampleville, MI 49000-0001\n",
     ("Contoso Trading LLC", "Operating Account")),
    (community_section._mission_valley_holder_reading,
     "Statement Ending 02/27/2054\nCONTOSO TRADING INC OPERATING ACCOUNT Page 1 of 6\n",
     ("CONTOSO TRADING INC", "OPERATING ACCOUNT")),
    (bmo_us_activity._holder_reading,
     "How to reach us\nbmo.com/contact 888-555-0100\nCONTOSO TRADING L.L.C. OPERATING ACCOUNT 100 S SAMPLE AVE "
     "SAMPLEVILLE IL 60000\n", ("CONTOSO TRADING L.L.C.", "OPERATING ACCOUNT")),
    (santander._holder_reading,
     "Statement Period 02/01/54 TO 02/28/54 Primary Account #: 00000000000\n"
     "CONTOSO TRADING INC OPERATING ACCOUNT Account # 00000000000\nBalances\n",
     ("CONTOSO TRADING INC", "OPERATING ACCOUNT")),
    (citibusiness._holder_reading,
     CITI_HEADER.format(between="May 1 - May 31, 2054 CONTOSO TRADING, LLC ESCROW ACCOUNT 100 SAMPLE AVE # 200") + "\n",
     ("CONTOSO TRADING, LLC", "ESCROW ACCOUNT")),
    (td_canada_french._holder_reading,
     "Tel: 1-800-555-0100\nTDCDA00000_0000000_000 F R 00000 00000\n1234-5678 QUEBEC INC. COMPTE EN FIDUCIE 100 BOUL "
     "SAMPLE SAMPLEVILLE PQ X0X 0X0\nReleve de compte\n", ("1234-5678 QUEBEC INC.", "COMPTE EN FIDUCIE")),
    (chase._holder_reading,
     CHASE_DDA_PAGE.replace("CONTOSO HOLDINGS OF SAMPLEVILLE,\n", "CONTOSO HOLDINGS LLC\nPREMIUM TRUST ACCOUNT\n"),
     ("CONTOSO HOLDINGS LLC", "PREMIUM TRUST ACCOUNT")),
    (navy_federal._holder_reading,
     "Statement of Account\n#AAAAAAA #000000A0A0AAA0A0#000AAA00A CONTOSO TRADING LLC OPERATING ACCOUNT 100 SAMPLE RD "
     "UNIT 10 SAMPLEVILLE TX 76000-0001\n", ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")),
    (td_us._holder_reading,
     "STATEMENT OF ACCOUNT\nCONTOSO TRADING LLC OPERATING ACCOUNT Account # 000-0000000\nACCOUNT SUMMARY\n",
     ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")),
    (pnc._holder_reading,
     "PNC Bank\nCONTOSO TRADING LLC OPERATING ACCOUNT Business Checking Summary Account number: XX-XXXX-0000\n",
     ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")),
    (td_can._holder_reading,
     "Tel: 1-800-555-0100\nTDCDA12345_1234567_123 E R 12345 12345\nCONTOSO CONSTRUCTION LTD. TRUST ACCOUNT 1000 SAMPLE "
     "DR SAMPLEVILLE BC V1E 2C3\nStatement of Account\n", ("CONTOSO CONSTRUCTION LTD.", "TRUST ACCOUNT")),
    (truist._holder_reading,
     "Page 1 of 2 01/01/54 FL 1234567890123\n123-45-67-89  12345   1  C  123  45  S    67  890 CONTOSO TRADING LLC "
     "OPERATING ACCOUNT 1000 SAMPLE CIR SAMPLEVILLE FL  34000-0001\nContact us\n",
     ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")),
    (first_citizens._holder_reading,
     "CONTOSO LLC DBA NORTHWIND AGENCY, LLC PREMIUM TRUST ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001 1,234.56\n"
     "Your Account(s) At A Glance\n", ("CONTOSO LLC DBA NORTHWIND AGENCY, LLC", "PREMIUM TRUST ACCOUNT")),
]


@pytest.mark.parametrize(("reader", "page", "reading"), _TITLED_PAGES, ids=lambda value: getattr(value, "__module__", ""))
def test_each_reader_publishes_the_title_its_own_anchor_prints_after_the_name(reader, page, reading):
    assert reader(_document(page)) == reading


def test_every_holder_reader_has_a_titled_page():
    """The 22 readers this batch wires (the seven of audit B9, First Citizens included, and R2-B05's fifteen with
    TD Canada Trust's French issue in Desjardins' place), each tested above."""
    assert len({reader for reader, _page, _reading in _TITLED_PAGES}) == 22


def test_a_title_is_read_only_from_the_reading_s_own_anchor():
    """The title words printed anywhere else on the page (a product line, a summary heading) are never a title."""
    page = BOFA_PAGE.replace("Your Business Advantage Fundamentals Banking", "Your Premium Trust Account").format(
        name="CONTOSO TRADING LLC\n"
    )
    assert bofa._holder_reading(_document(page)) == ("CONTOSO TRADING LLC", None)
    assert bofa._holder_reading(_document(BOFA_PAGE.replace("{name}", "") + "PREMIUM TRUST ACCOUNT\n")) == NONE


# --- the extraction does not move: only the holder's name is new ---------------------------------------------------

def _without_holder(statement):
    return statement.model_dump(exclude={"holder_name", "account_title"})


def test_bank_of_america_s_holder_line_moves_nothing_else():
    from tests.test_parser_crash_shapes import bofa_document

    plain = bofa_document()
    named = "for January 1, 2054 to January 31, 2054 Account number: 9999 9999 9999\nCONTOSO TRADING LLC\n" + plain
    before, after = bofa.parse_bofa_statement(plain), bofa.parse_bofa_statement(named)
    assert before is not None and after is not None
    assert before.holder_name is None and after.holder_name == "CONTOSO TRADING LLC"
    assert before.account_title is None and after.account_title is None
    assert _without_holder(after) == _without_holder(before)
    # R2-OW10: a designation after the name is the statement's title, and moves nothing else either.
    titled = bofa.parse_bofa_statement(named.replace("CONTOSO TRADING LLC\n", "CONTOSO TRADING LLC OPERATING ACCOUNT\n"))
    assert titled is not None
    assert (titled.holder_name, titled.account_title) == ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")
    assert _without_holder(titled) == _without_holder(before)
    assert titled.model_dump()["account_title"] == "OPERATING ACCOUNT"
    assert "account_title" not in after.model_dump()


def test_us_bank_s_mailing_line_moves_nothing_else():
    from tests.test_parser_crash_shapes import us_bank_document

    plain = us_bank_document()
    named = "CONTOSO TRADING LLC 100 SAMPLE BLVD SAMPLEVILLE MN 55000\n%\nTo Contact U.S. Bank\n" + plain
    before, after = us_bank.parse_us_bank_statement(plain), us_bank.parse_us_bank_statement(named)
    assert before is not None and after is not None
    assert before.holder_name is None and after.holder_name == "CONTOSO TRADING LLC"
    assert _without_holder(after) == _without_holder(before)
    titled = us_bank.parse_us_bank_statement(named.replace("LLC 100", "LLC PREMIUM TRUST ACCOUNT 100"))
    assert titled is not None
    assert (titled.holder_name, titled.account_title) == ("CONTOSO TRADING LLC", "PREMIUM TRUST ACCOUNT")
    assert _without_holder(titled) == _without_holder(before)


def test_td_bank_s_fallback_line_moves_nothing_else():
    from tests.test_parser_crash_shapes import td_us_document

    plain = td_us_document()
    named = plain.replace(
        "Primary Account #: 9999999999\n",
        "Primary Account #: 9999999999\nCONTOSO TRADING LLC PO BOX 100 SAMPLEVILLE SC 29000\nCONTOSO TRADING LLC\n"
        "Account # 9999999999\n",
    )
    before, after = td_us.parse_td_us_statement(plain), td_us.parse_td_us_statement(named)
    assert before is not None and after is not None
    assert before.holder_name is None and after.holder_name == "CONTOSO TRADING LLC"
    assert _without_holder(after) == _without_holder(before)
    titled = td_us.parse_td_us_statement(plain.replace(
        "Primary Account #: 9999999999\n",
        "Primary Account #: 9999999999\nCONTOSO TRADING LLC OPERATING ACCOUNT Account # 9999999999\n",
    ))
    assert titled is not None
    assert (titled.holder_name, titled.account_title) == ("CONTOSO TRADING LLC", "OPERATING ACCOUNT")
    assert _without_holder(titled) == _without_holder(before)


# --- R2-OW10: every parser publishes the title wherever it publishes the reading's name ------------------------------

_ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"


def _sets(node: ast.AST) -> tuple[bool, bool]:
    """Whether a Statement(...) call or an assignment sets holder_name, and whether it sets account_title."""
    if isinstance(node, ast.Call):
        names = {keyword.arg for keyword in node.keywords}
    else:
        targets = [element for target in node.targets
                   for element in (target.elts if isinstance(target, ast.Tuple) else [target])]
        names = {target.attr for target in targets if isinstance(target, ast.Attribute)}
    return "holder_name" in names, "account_title" in names


def test_every_parser_that_publishes_a_holder_name_publishes_its_title_beside_it():
    """Every Statement(...) call that passes holder_name passes account_title, and every assignment of a statement's
    holder_name assigns its account_title in the same statement (from the same reading): a holder reader's title can
    never be dropped by a parser that publishes its name."""
    sites, unpaired = 0, []
    for path in sorted(_ANALYSIS.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            statement_call = isinstance(node, ast.Call) and (
                getattr(node.func, "id", None) == "Statement" or getattr(node.func, "attr", None) == "Statement"
            )
            if not (statement_call or isinstance(node, ast.Assign)):
                continue
            holder, title = _sets(node)
            if holder:
                sites += 1
                if not title:
                    unpaired.append(f"{path.name}:{node.lineno}")
    assert not unpaired
    # The 22 readers' parsers: their constructors and assignments (RBC's two issues, CIBC's and TD Canada Trust's two
    # entry points each count twice). Audit round 4, R4-68: and Symitar's Primary Owner(s) reader, one assignment.
    assert sites == 26


# --- Audit round 4, batch R4-B08 ---
# Audit round 4, R4-29 (the underwriter's Q10 of 2026-10-02, "Hold every deposit into an account titled "premium
# trust""; R3-B11's rule that a contact is read by its words and that the contact's name is never the holder's or the
# title): CARE OF is a contact after the premium-trust designation (the title rule's words, kind words and reference),
# whatever prints before it, and on a block's own designation line after either designation. Every reader cuts it alike;
# a name with no designation and no legal form keeps its CARE OF, and an account designation after a form-less name
# reads as before. Fabricated lines only.

R4_29_ADDRESS = "100 SAMPLE ST SAMPLEVILLE SC 29000-0001"
R4_29_DESIGNATIONS = [
    "PREMIUM TRUST", "PREMIUM TRUST CHECKING", "PREMIUM TRUST BUSINESS CHECKING", "PREMIUM TRUST MONEY MARKET",
    "PREMIUM TRUST SAVINGS", "PREMIUM TRUST DDA", "PREMIUM TRUST ACCOUNT (0000)", "PREMIUM FUND TRUST ACCOUNT",
]


@pytest.mark.parametrize("care_of", ["CARE OF", "care of"])
@pytest.mark.parametrize("designation", R4_29_DESIGNATIONS)
def test_r4_29_care_of_after_the_premium_trust_designation_is_a_contact(designation, care_of):
    line = f"NORTHWIND AGENCY INC {designation} {care_of} SAMPLE PERSON {R4_29_ADDRESS}"
    assert read_address_line(line) == HolderReading("NORTHWIND AGENCY INC", designation)
    assert read_name(f"NORTHWIND AGENCY INC {designation} {care_of} SAMPLE PERSON") == HolderReading(
        "NORTHWIND AGENCY INC", designation)


@pytest.mark.parametrize(("line", "title"), [
    ("PREMIUM TRUST CHECKING CARE OF SAMPLE PERSON", "PREMIUM TRUST CHECKING"),
    ("PREMIUM TRUST ACCOUNT CARE OF SAMPLE PERSON", "PREMIUM TRUST ACCOUNT"),
    ("PREMIUM TRUST CARE OF SAMPLE PERSON", "PREMIUM TRUST"),
    ("OPERATING ACCOUNT CARE OF SAMPLE PERSON", "OPERATING ACCOUNT"),
])
def test_r4_29_a_block_s_own_designation_line_cuts_its_care_of(line, title):
    lines = ["NORTHWIND AGENCY INC", line, "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"]
    assert read_address_block(lines) == HolderReading("NORTHWIND AGENCY INC", title)


def test_r4_29_a_title_line_s_care_of_never_drops_a_premium_trust_designation():
    # The cut keeps a CARE OF contact that names the trust account itself, so the title rule still reads it.
    from analysis.true_revenue import premium_trust_title

    lines = ["NORTHWIND AGENCY INC", "OPERATING ACCOUNT CARE OF PREMIUM TRUST ACCOUNT", "100 SAMPLE ST",
             "SAMPLEVILLE SC 29000-0001"]
    reading = read_address_block(lines)
    assert reading == HolderReading("NORTHWIND AGENCY INC", "OPERATING ACCOUNT PREMIUM TRUST ACCOUNT")
    assert premium_trust_title(reading.title, None, reading.name) == "PREMIUM TRUST ACCOUNT"


def test_r4_29_a_form_less_name_loses_the_person_after_the_premium_trust_designation():
    line = f"NORTHWIND AGENCY PREMIUM TRUST CHECKING CARE OF SAMPLE PERSON {R4_29_ADDRESS}"
    assert read_address_line(line) == HolderReading("NORTHWIND AGENCY PREMIUM TRUST CHECKING", None)
    assert read_name("NORTHWIND AGENCY PREMIUM TRUST CHECKING CARE OF SAMPLE PERSON") == HolderReading(
        "NORTHWIND AGENCY PREMIUM TRUST CHECKING", None)


@pytest.mark.parametrize(("name", "reading"), [
    # CARE OF after a name with no designation and no form is part of the name (R3-B11 review round 1, finding 1).
    ("CONTOSO HOLDINGS LLC DBA NORTHWIND HOME CARE OF SAMPLEVILLE",
     HolderReading("CONTOSO HOLDINGS LLC DBA NORTHWIND HOME CARE OF SAMPLEVILLE", None)),
    ("SAMPLE AND CO HOME CARE OF SAMPLEVILLE LLC", HolderReading("SAMPLE AND CO HOME CARE OF SAMPLEVILLE LLC", None)),
    ("SAMPLE & CO HOME CARE OF SAMPLEVILLE LLC", HolderReading("SAMPLE & CO HOME CARE OF SAMPLEVILLE LLC", None)),
    ("CONTOSO HOME CARE OF SAMPLEVILLE LLC", HolderReading("CONTOSO HOME CARE OF SAMPLEVILLE LLC", None)),
    # Recorded residual: an account designation after a form-less name keeps the contact in the name, so the contact
    # person's own Zelles stay held by the holder test.
    ("NORTHWIND AGENCY OPERATING ACCOUNT CARE OF SAMPLE PERSON",
     HolderReading("NORTHWIND AGENCY OPERATING ACCOUNT CARE OF SAMPLE PERSON", None)),
    # ATTN keeps its reading.
    ("NORTHWIND AGENCY INC OPERATING ACCOUNT ATTN SAMPLE PERSON", HolderReading("NORTHWIND AGENCY INC",
                                                                                "OPERATING ACCOUNT")),
    ("NORTHWIND AGENCY INC ATTN:PREMIUM TRUST ACCOUNT", HolderReading("NORTHWIND AGENCY INC", "PREMIUM TRUST ACCOUNT")),
])
def test_r4_29_the_controls_read_as_before(name, reading):
    assert read_address_line(f"{name} {R4_29_ADDRESS}") == reading
    assert read_name(name) == reading
