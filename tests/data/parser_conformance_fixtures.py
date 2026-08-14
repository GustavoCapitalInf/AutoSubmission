"""Minimal synthetic statement headers, one per registration (R-4).

Each fixture carries exactly the evidence its parser declares and nothing else:
the issuer identification a real statement of that bank prints at the top. They
are deliberately *headers*, with no ledger — which makes them do double duty:

* detection-positive — the parser must recognise its own bank;
* detection-negative — run as a cross product, every fixture must be claimed by
  its own registration and by **no other**. This is the property that matters
  for discovery (WAVE2_BRIEF R-4): it proves parser X does not claim bank Y's
  statement;
* self-invalidation — a header with no transactions is not a parseable
  statement, so `parse` must return None rather than invent one.

The marker strings are written out literally rather than read back from the
registrations. That is the point: if someone edits a marker, these fixtures
stop matching and the test fails, which is what makes this a contract rather
than a tautology.

Where a parser's evidence is a disjunction, the fixture uses one branch and
`ALTERNATE_FIXTURES` covers the others.

No customer names, account numbers, dates or amounts appear here. Two parsers
declare such evidence in production (`farmers_merchants` matches a customer
name, `altana` and `texas_bank` embed digit runs); those are pre-existing R-1
residuals, reported in R3_DETECTION_FINDING.md §7 and deliberately not
exercised by these fixtures.
"""
from __future__ import annotations

#: registration id -> a minimal document that registration must claim.
FIXTURES: dict[str, str] = {
    "altana": "altanafcu.org\nFREE BUSINESS CHECKING ID 0050\n",
    "american_express": (
        "americanexpress.com/businesscheckinghome\n"
        "Business Checking Account Statement\n"
    ),
    "apex_scanned": (
        "SUMMIT BUSINESS CHECKING\nBALANCE FORWARD FROM\nENDING BALANCE AS OF\n"
    ),
    "atb": "ATB Financial\nDeposit Account Statement\n",
    "b1": "B1Bank\nDAILY ACTIVITY\n",
    "banco_popular": "Banco Popular\nFLEXICUENTA DE NEGOCIOS\n",
    "bank_of_america": "BANK OF AMERICA\nACCOUNT SUMMARY\nbankofamerica.com\n",
    "bluevine": "Bluevine Inc.\nActivity summary\n",
    "bmo": "BMO Bank of Montreal\nAccount Summary Totals\n",
    "bmo_ca_business": (
        "www.bmo.com\nBusiness Banking statement\nSummary of account\n"
        "Amounts debited from your account ($) Amounts credited to your account ($)\n"
    ),
    "bmo_ca_business_french": (
        "www.bmo.com\nRelevé de services bancaires aux entreprises\n"
        "Sommaire de votre compte\n"
        "Montants déduits de votre compte ($) Montants ajoutés à votre compte ($)\n"
    ),
    "bmo_us_activity": (
        "BMO BANK N.A. MEMBER FDIC\nbmo.com/contact\n"
        "Account Summary\nBEGINNING BALANCE AS OF\nMonthly Activity Details\n"
    ),
    "capital_one": "CAPITAL ONE\nAN IMPORTANT MESSAGE TO OUR CLIENTS\n",
    "chase": "JPMorgan Chase Bank\nStatement of account\n*start*summary\n",
    "chase_export": "Printed from Chase for Business\nTransactions\n",
    # Deliberately carries no bank NAME: this product is recognised by Chase's
    # own text-layer sentinel plus its printed savings furniture, and adding
    # the name would make `chase` claim this fixture in the cross product —
    # which is the real relationship between the two, expressed as a
    # `supersedes` edge rather than as detection overlap.
    "chase_savings": (
        "*start*summary\nSAVINGS SUMMARY\n"
        "Date Description Amount Balance\n"
    ),
    "cibc": (
        "CIBC Account Statement\nTransaction details\n"
        "Date Description Withdrawals ($) Deposits ($) Balance ($)\n"
    ),
    "cibc_french": "CIBC\nDétail de vos opérations\n",
    "citizens": "citizensbank.com\nBusiness Advisor Checking\n",
    "columbia_bank": (
        "COLUMBIA BANK\nMARKETPLACE CHECKING\nDEPOSITS/ADDITIONS\nDAILY BALANCES\n"
    ),
    "consumers": "Consumers Credit Union\nSummary of All Accounts\n",
    "dakota_west": "dakotawestcu.com\nThank you for being a member of Dakota West Credit Union.\n",
    "demo_national": "SAMPLE BUSINESS BANK STATEMENT\nBank: Demo National Bank\n",
    "desjardins": (
        "CAISSE DESJARDINS\nDESJARDINS CORPORATE BUILD-UP ACCOUNT\n"
    ),
    "farmers_merchants": (
        "FARMERS AND MERCHANTS BANK\nDEPOSITS AND CREDITS\n"
    ),
    # The only fixture here that carries no issuer identification, because the
    # registration it covers carries none: `community_section` recognises a
    # CORE PROCESSOR's template and reads the issuer out of each document. Its
    # evidence is the template's own grid header and the period-count row it
    # prints, and that is exactly what this fixture holds.
    "community_section": (
        "Account Summary Date Description Amount\n"
        "1 Credit(s) This Period $10.00\n"
    ),
    "first_citizens": "First Citizens\nfirstcitizens.com\n",
    "first_community": "firstcommunity.com\nBUSINESS PLUS CKG\n",
    "first_farmers": (
        "WWW.FFBT.COM\nBUSINESS BASIC CHECKING ACCOUNT\n"
        "BALANCE LAST STATEMENT\nTOTAL DAYS IN STATEMENT PERIOD\n"
    ),
    "ibc": "IBC\nBiz Rite Account Recap\n",
    "linkbank": "LINKBANK.COM\nActivity in Date Order\n",
    "midflorida": "midflorida.com\nFree Business Checking\n",
    "mission_valley": "Mission Valley Bank\nOnline Banking www.missionvalleybank.com\n",
    "navigant": (
        "NAVIGANTCU.ORG\nQUEST BALANCE CHECKING\nACCOUNT SUMMARY\nSTATEMENT PERIOD\n"
    ),
    "navy_federal": "Navy Federal\nSummary of your deposit accounts\n",
    "pnc": "PNC Bank\nBusiness Checking\nBalance Summary\n",
    "rbc": "ROYAL BANK OF CANADA\nACCOUNT ACTIVITY DETAILS\n",
    "rbc_french": "BANQUE ROYALE\nDate Description Chèques et débits ($)\n",
    "regions": "REGIONS BANK\nSUMMARY\nThank you for banking with Regions!\n",
    "relay": (
        "RELAY FINANCIALS TECHNOLOGY\nACCOUNT STATEMENT\n"
        "OPENING BALANCE\nCLOSING BALANCE\n"
    ),
    "santander": "Santander\nAccount Activity\n",
    "scotiabank": "SCOTIABANK\nThe Bank of Nova Scotia\n",
    "secu": "secumd.org\nFree Business Checking\n",
    "southside_scanned": "SOUTHSIDE\nACCOUNT SUMMARY\nBUILDER ACCOUNT\n",
    "square_checking": (
        "Square Checking Routing number:\nsquareup.com/help\n"
        "Block Inc. Broadway, Suite Oakland, CA\n"
        "Date Details Activity type Balance Amount\n"
    ),
    "td_canada": (
        "Accounts issued by: THE TORONTO-DOMINION BANK\n"
        "<table>\n<tr><td>Branch No.</td><td>Account No.</td></tr>\n</table>\n"
    ),
    "td_canada_native": (
        "THE TORONTO-DOMINION BANK\n"
        "DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE\n"
    ),
    # The Quebec issue of the same grid. Both markers are issuer furniture: the
    # bank's own column legend and the statement's own issuer footer. The bank
    # name alone is not evidence here any more than it is on the English side.
    "td_canada_french": (
        "DESCRIPTION RETRAITS DEPOTS DATE SOLDE\n"
        "Comptes émis par : LA BANQUE TORONTO-DOMINION\n"
    ),
    "td_us": "TD Bank, N.A.\nSTATEMENT OF ACCOUNT\n",
    "texas_bank": "Texas Bank and Trust\nWITHDRAWALS AND OTHER DEBITS (CONTINUED)\n",
    "truist": "TRUIST\nAccount summary Your previous balance\n",
    "us_bank": "U.S. Bank National Association\nAccount Summary\n",
    "wells_fargo": "WELLS FARGO\nWF_NATIVE_TRANSACTIONS\n",
    "wilson_muir": "WILSON & MUIR\nSMALL BUSINESS PACKAGE SUMMARY\n",
}

#: The other branch of each disjunctive marker. Same contract as FIXTURES:
#: claimed by its own registration, by no other.
ALTERNATE_FIXTURES: dict[str, tuple[str, ...]] = {
    "banco_popular": ("TeleBanco Comercial\nFLEXICUENTA DE NEGOCIOS\n",),
    "farmers_merchants": ("BUSINESS/COMMERCIAL\nCHECKS/DEBITS\nDEPOSITS AND CREDITS\n",),
    # RBC prints its French grid under two product names, as it does in English.
    "rbc_french": ("BANQUE ROYALE\nDate Description Retraits ($)\n",),
    "bmo": ("BANK OF MONTREAL\nAccount Summary Totals\n",),
    "chase": ("\nCHASE\nStatement of account\n*start*summary\n",),
    "consumers": ("ConsumersCU.org\nSummary of All Accounts\n",),
    "first_citizens": ("Central Bank Operations\nfirstcitizens.com\n",),
    "td_canada": (
        "<table>\n<tr><td>BUSINESS CHEQUING ACCOUNT - CAD</td></tr>\n</table>\n",
    ),
}
