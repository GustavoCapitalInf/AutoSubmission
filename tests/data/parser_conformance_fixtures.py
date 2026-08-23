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
    # A platform template with no issuer in it at all, which is the point:
    # `balance_by_date` recognises a CORE PROCESSOR's four-way summary
    # partition — a grid whose terms carry printed COUNTS beside terms that
    # carry none — plus the daily grid that walks the period. Both markers are
    # the template's own furniture, so this fixture carries no bank name, no
    # domain and nothing an issuer could change between statements.
    "balance_by_date": (
        "Checking Account Summary\n"
        "PREVIOUS BALANCE .00\n"
        "+ 0 CREDITS .00\n"
        "- 0 DEBITS .00\n"
        "- SERVICE CHARGES .00\n"
        "+ INTEREST PAID .00\n"
        "ENDING BALANCE .00\n"
        "e Balance By Date\n"
    ),
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
    "brex": (
        "support@brex.com Account Statement\n"
        "Account Summary\nThis Period Year-to-Date\n"
        "Beginning Account Balance\nEnding Account Balance\n"
        "Date From Method Amount\n"
    ),
    "bmo_us_activity": (
        "BMO BANK N.A. MEMBER FDIC\nbmo.com/contact\n"
        "Account Summary\nBEGINNING BALANCE AS OF\nMonthly Activity Details\n"
    ),
    # The issuer's own name appears in its OWN ledger, as the location of the
    # ATM a card row was made at. Detection needs the domain, the platform's
    # activity banner and its summary grid together.
    "burke_herbert": (
        "Burke & Herbert Bank\n"
        "burkeandherbertbank.com\n"
        "ACTIVITY IN DATE ORDER\n"
        "PREVIOUS BALANCE 927.81- DAYS THIS STATEMENT PERIOD 28\n"
    ),
    "capital_one": "CAPITAL ONE\nAN IMPORTANT MESSAGE TO OUR CLIENTS\n",
    # W3 §GLANCE. Two required markers: the summary's own control line with its
    # column header, and the partition's two DATED balances. Every name, date
    # and figure here is INVENTED, under the standing batch-8 privacy rule, and
    # the fixture deliberately prints no `This Statement Cycle Reflects` line,
    # so `parse` declines it at the period gate — a header is not a statement.
    "category_partition": (
        "Invented Alpha Account SUMMARY Type :     **REG    Status :    Active\n"
        "Category Number Amount Balance Forward From 08/29/25 41,003.77 "
        "Alpha Credits 1 62,005.11+ Ending Balance On 09/30/25 103,008.88\n"
    ),
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
    # Issuer furniture only: the legal entity, the product masthead, the
    # ledger section and its own column header.
    "citibusiness": (
        "CITIBANK, N. A. Account Statement Period\n"
        "CitiBusiness  ACCOUNT AS OF\n"
        "CHECKING ACTIVITY\n"
        "Date Description Debits Credits Balance\n"
    ),
    "citizens": "citizensbank.com\nBalance Calculation\n",
    # No issuer NAME, and that is the registration's own conclusion rather
    # than this file's convenience (W3 §COLUMBIA5). The masthead of this
    # printing is a logo: across four consecutive statements of one account the
    # scan renders the name twice and renders it as `sbedet eye ffgeef tLe` and
    # `Aun | rou ae nn nro) cell Mazo LOTT` the other two times. What the
    # registration recognises instead is the issuer's product masthead and the
    # three pieces of ledger furniture its reader cannot proceed without.
    "columbia_bank": (
        "MARKETPLACE CHECKING\nDEPOSITS/ADDITIONS\n"
        "ACH AND ELECTRONIC PAYMENTS/SUBTRACTIONS\nDAILY BALANCES\n"
    ),
    "consumers": "Consumers Credit Union\nSummary of All Accounts\n",
    # The second fixture here that carries no issuer identification, for the
    # same reason as `community_section` below: the registration it covers
    # recognises a CORE PROCESSOR's template and reads the issuer out of each
    # document. Its evidence is the template's own period line and the labels
    # of the two summary balance rows, and that is exactly what this holds.
    # The THIRD core-processor template (W3 §LCPERIOD). No issuer in it at
    # all, which is the point twice over: the registration reads the template's
    # own period sentence, and the template prints no institution FIELD, so
    # `Statement.bank` is None on every document it publishes. Sentence case is
    # load-bearing — upper-cased, this fixture is not this template.
    # The day count is on its own line, which is one of the two arrangements
    # the archive prints (the other puts all three fields on one line). It
    # matters here for the same reason it matters in the other platform
    # fixtures: `_mention_of` demotes a fixture's FIRST LINE into another
    # bank's ledger, and a registration must not claim a document that merely
    # quotes it — so no single line of a fixture may carry every required
    # marker.
    "core_processor_daily": (
        "Last statement: March 31, 2026 This statement: April 30, 2026\n"
        "Total days in statement period: 30\n"
        "Direct inquiries to: 000-000-0000\n"
    ),
    # The fourth summary grammar of the same processor (W3 §GRAM4). It shares
    # the line above's period SENTENCE, so the first line is deliberately not
    # enough on its own: the second required marker is the pair of DATED
    # summary balances, which is exactly what separates the two registrations
    # on the archive. No `Total days` line here, and none in the sibling's
    # fixture's summary — that asymmetry is the cross-product's job to prove.
    "core_processor_counted": (
        "This statement: February 27, 2026 Last statement: January 30, 2026\n"
        "Beginning balance (1/30/2026)\n"
        "Ending balance (2/27/2026)\n"
        "Contact us:\n"
    ),
    "core_processor_sectioned": (
        "No Minimum Business Checking ACCOUNT XXXXXXXXXX1234\n"
        "LAST STATEMENT 07/31/25 0.00 AVG AVAILABLE BALANCE 0.00 "
        "THIS STATEMENT 08/29/25 0.00\n"
        "TOTAL DAYS IN STATEMENT PERIOD 08/01/25 THROUGH 08/29/25: 29\n"
    ),
    "dakota_west": "dakotawestcu.com\nThank you for being a member of Dakota West Credit Union.\n",
    "demo_national": "SAMPLE BUSINESS BANK STATEMENT\nBank: Demo National Bank\n",
    "desjardins": (
        "CAISSE DESJARDINS\nDESJARDINS CORPORATE BUILD-UP ACCOUNT\n"
    ),
    # The issuer's own contact domain out of the summary block, this
    # template's summary head, and the ledger column head — the last one is a
    # DETECTION marker and not merely a parse requirement, because the running
    # balance it names is what solves every row's direction and a printing
    # without it is one this reader cannot direct (W3 §TANGERINE).
    "eq_bank_scanned": (
        "eqbank.ca/contact-us\n"
        "Your activity summary\n"
        "Date Description Withdrawals Deposits Balance\n"
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
    "fifth_third": (
        "FTCSTMT000 000 00000000 UDSPDFSTMT 0000000000000000000 DDA\n"
        "Account Summary\nwww.53.com/businessbanking\n"
    ),
    # A platform template, so the fixture carries the template's furniture
    # rather than an issuer: the heading, the opening-balance clause that keeps
    # it off Wells Fargo, and the parenthesised counts.
    "fiserv_premier": (
        "Statement of Account\n"
        "Previous Balance $0.00 Deposits/Credits (0) $0.00 "
        "Checks/Debits (0) $0.00 Ending Balance $0.00\n"
    ),
    "first_citizens": "First Citizens\nYour Account(s) At A Glance\n",
    "first_community": "firstcommunity.com\nBUSINESS PLUS CKG\n",
    "first_farmers": (
        "WWW.FFBT.COM\nBUSINESS BASIC CHECKING ACCOUNT\n"
        "BALANCE LAST STATEMENT\nTOTAL DAYS IN STATEMENT PERIOD\n"
    ),
    "found_lead": (
        "February 2026 Account Statement\n"
        "Found is a financial technology company, not a bank.\n"
        "Banking services are provided by Lead Bank, Member FDIC.\n"
        "Account summary\n"
        "Deposits & other credits\nPurchases & other debits\n"
        "Date Description Amount Balance\n"
    ),
    # The same document class, plus the one sentence in which the issuer
    # refuses the word "statement". That line is the whole difference between
    # the two registrations, and the cross-product below is what proves it is
    # enough to keep them apart.
    "found_lead_activity": (
        "February 2026 Activity (Month to Date)\n"
        "Found is a financial technology company, not a bank.\n"
        "Banking services are provided by Lead Bank, Member FDIC.\n"
        "Account summary\n"
        "Deposits & other credits\nPurchases & other debits\n"
        "Date Description Amount Balance\n"
        "The information in this document is not a bank statement and therefore should not be relied upon as a bank statement.\n"
    ),
    # The issuer name alone is not the claim — a statement of another bank that
    # records an ATM withdrawal at a Huntington branch prints it too. The claim
    # needs this issuer's own summary grid and its service-mark footer.
    "huntington": (
        "THE HUNTINGTON NATIONAL BANK\n"
        "Beginning Balance $1,000.00 Credits (+) 0.00 Debits (-) 0.00 "
        "Ending Balance $1,000.00\n"
        "Huntington Bancshares Incorporated\n"
    ),
    "ibc": "IBC\nBiz Rite Account Recap\n",
    "linkbank": "LINKBANK.COM\nActivity in Date Order\n",
    "mercury": (
        "Mercury | help@mercury.com\n"
        "Account details\nAccount activity\n"
        "Statement balance\n"
        "Banking services provided by Member FDIC\n"
        "Date (UTC) Description Type Amount End of Day Balance\n"
    ),
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
    # The second fixture here carrying no issuer identification, and for a
    # stronger reason than `community_section`'s: that template's documents
    # print an issuer this platform reads out of them, and these print none at
    # all (W3 §UNKISSUER). So the fixture is the template's furniture and
    # nothing else - the ledger's column header, the fee table that terminates
    # it, and the fee table's printed transaction totals. The figures are
    # zeroes: they make the oracle marker fire without putting a ledger in a
    # file whose whole purpose is to hold none.
    "releve_facturation": (
        "MM JJ DESCRIPTION DÉBIT ($) CRÉDIT ($) SOLDE ($)\n"
        "FACTURATION DÉTAILLÉE TRANSACTIONS/VOLUME(S) TARIF UNIT./TAUX FRAIS\n"
        "NOMBRE MONTANT TOTAL NOMBRE MONTANT TOTAL\n"
        "TRANSACTIONS DÉBIT 0 0,00 CRÉDIT 0 0,00\n"
    ),
    "santander": "Santander\nAccount Activity\n",
    "scotiabank": "SCOTIABANK\nThe Bank of Nova Scotia\n",
    "secu": "secumd.org\nFree Business Checking\n",
    # Every marker is the layout's own printed furniture. The partner banks
    # named in the statement's disclosure (and in the archive's folder label)
    # are deliberately absent: they are not what identifies this document.
    "shopify_balance": (
        "Shopify Balance\nStatement summary\nTransaction history\n"
        "Posted Date Transaction Date Description Amount Account balance\n"
    ),
    # The masthead plus three ROW LABELS of the ACCOUNT SUMMARY grid. What was
    # here — `BUILDER ACCOUNT` — is one customer's name for one of its
    # accounts, and the fixture said so out loud for as long as the detector
    # gated on it (W3 §SCANFINISH SF3).
    "southside_scanned": (
        "SOUTHSIDE\nDays in Statement Period\nDeposits/Credits\nChecks/Debits\n"
    ),
    "square_checking": (
        "Square Checking Routing number:\nsquareup.com/help\n"
        "Block Inc. Broadway, Suite Oakland, CA\n"
        "Date Details Activity type Balance Amount\n"
    ),
    # A member statement: the ACCOUNT SUMMARY, a per-account section heading
    # and the deposit grid. The loan grid is deliberately absent - a section
    # printing it is a credit facility, not a deposit ledger.
    "symitar": (
        "Statement of Account\nACCOUNT SUMMARY\n"
        "Free Business Checking ( ID 0210 )\n"
        "Posting Date Deposit Withdrawal Balance Description\n"
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
    # The scanned Texas First template. Its evidence is the issuer's own
    # tele-banking domain out of the page furniture, this template's summary
    # head, and the daily grid the ATM/POS directions are solved on — the grid
    # is a DETECTION marker and not merely a parse requirement, because a
    # printing without it is one this reader cannot direct and claiming it
    # would strand it (W3 §SCANNEXT).
    "texas_first_scanned": (
        "Texas First Bank\nwww.texasfirst.bank\n"
        "Summary of Activity Since Your Last Statement\n"
        "Daily Balance Summary\n"
    ),
    "truist": "TRUIST\nAccount summary Your previous balance\n",
    "us_bank": "U.S. Bank National Association\nAccount Summary\n",
    # The issuer name alone is NOT this parser's evidence: three CIBC
    # statements in the archive name Wealthsimple in a payee line. The
    # product line and the activity grid's column header are what make the
    # document Wealthsimple's own statement.
    "wealthsimple": (
        "Chequing monthly statement\nWealthsimple\n"
        "DATE POSTED DATE DESCRIPTION AMOUNT (CAD) BALANCE (CAD)\n"
    ),
    "wells_fargo": "WELLS FARGO\nWF_NATIVE_TRANSACTIONS\n",
    # The issuer, not the trade name: Zions Bancorporation prints this same
    # layout as Nevada State Bank and as Amegy Bank, and registering on
    # either brand would leave the other unclaimed.
    "wilson_muir": "WILSON & MUIR\nSMALL BUSINESS PACKAGE SUMMARY\n",
    # The institution alone is NOT this parser's evidence: other issuers'
    # statements name Woodforest in a payee line. The two printed column
    # headers are what make the document Woodforest's own statement.
    "woodforest": (
        "www.woodforest.com\nSummary of Accounts\n"
        "ACCOUNT TYPE AND NUMBER BALANCE FORWARD TOTAL DEBITS TOTAL CREDITS CLOSING BALANCE\n"
        "Transactions\nDate Credits Debits Balance Description\n"
    ),
    # The issuer, not the trade name. Zions Bancorporation prints this same
    # layout as Nevada State Bank and as Amegy Bank; registering on either
    # brand would leave the other unclaimed, so the evidence is the corporate
    # footer every issue carries plus the layout's own column legend.
    "zions": (
        "Statement of Accounts\n"
        "SUMMARY OF ACCOUNT BALANCE\n"
        "Previous Balance Deposits/Credits Withdrawals/Debits Checks Processed Ending Balance\n"
        "A division of Zions Bancorporation, N.A.\n"
    ),
}

#: The other branch of each disjunctive marker. Same contract as FIXTURES:
#: claimed by its own registration, by no other.
ALTERNATE_FIXTURES: dict[str, tuple[str, ...]] = {
    "banco_popular": ("TeleBanco Comercial\nFLEXICUENTA DE NEGOCIOS\n",),
    "farmers_merchants": ("BUSINESS/COMMERCIAL\nCHECKS/DEBITS\nDEPOSITS AND CREDITS\n",),
    # The scanned issue of the Fifth Third statement. The print stream belongs
    # to the electronic PDF and a photograph of the page cannot carry it; what
    # the page itself prints is the product named in its `Account Type:` field.
    "fifth_third": (
        "Account Type: 5/3 BUSINESS CKG\n"
        "Account Summary\nwww.53.com/businessbanking\n",
    ),
    # RBC prints its French grid under two product names, as it does in English.
    "rbc_french": ("BANQUE ROYALE\nDate Description Retraits ($)\n",),
    "bmo": ("BANK OF MONTREAL\nAccount Summary Totals\n",),
    "chase": ("\nCHASE\nStatement of account\n*start*summary\n",),
    "consumers": ("ConsumersCU.org\nSummary of All Accounts\n",),
    "first_citizens": ("Central Bank Operations\nYour Account(s) At A Glance\n",),
    "td_canada": (
        "<table>\n<tr><td>BUSINESS CHEQUING ACCOUNT - CAD</td></tr>\n</table>\n",
    ),
}
