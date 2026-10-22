"""Credit-side vocabulary and floors: payouts, public payers, returns, customer financing."""
from __future__ import annotations

import re

from analysis.classification_registry import OPERATING_SOURCE_PAYOUT_FORMS


# ---------------------------------------------------------------------------------------------------------------------
# Classification 5.5: the credit revenue rules (§6.1 steps 3 to 14, §7.1 to §7.11).
# ---------------------------------------------------------------------------------------------------------------------

#: §7.11: the unambiguous return codes, read on credits only (the debit rules keep _REFUND_REVERSAL_PATTERNS). The
#: reversal-pair pass reads them too.
_RETURN_CODE_CREDIT_PATTERNS = (
    re.compile(
        r"\b(?:RTN|RETN|RFND|REFND|RFD|RVSL|RVRSL|REVSL|RECALL(?:ED)?|UNPAID|REJT|CHBK|CHGBK)\b"
    ),
)
#: The card-shaped refund labels step 3 adds (Citibank's cut DEBIT CARD CREDI, Bank of America's credit-side
#: CHECKCARD <mmdd>, a point-of-sale deposit naming its merchant), released as a card credit is
#: (_card_credit_released).
_CARD_REFUND_LABELS = (
    re.compile(r"\bDEBIT CARD CREDI\b"),
    re.compile(r"^(?:\d{1,2} \d{1,2} )?CHECKCARD \d{4}\b"),
    re.compile(r"\bPOINT OF SALE DEPOSIT [A-Z]"),
)
_REMBOURSEMENT_WORD = re.compile(r"(?<![A-Z])REMBOURSEMENT\b")
#: No legal-form word later on the row. A marker word that starts a company's name (REV MOBILE LLC, RETOUR CONTOSO
#: INC, UNAUTHORIZED CONTOSO LLC) is no reversal. Copied in true_revenue._POSSIBLE_RETURN and in
#: tools/revenue_census.py.
_NO_LEGAL_FORM_LATER = (
    r"(?!.*\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LTEE|LIMITED|LLP|LLLP|PLLC|ULC|PLC|GMBH)\b)"
)
#: §6.1, §7.11, §20: the reversal, correction and refund spellings
#: step 3 also reads on a credit, beside its 5.4 patterns and the return codes:
#: - a bounced outgoing payment credited back (Zions' ITEM RET NOT PAID; never ITEM RETURNED before a fee, the bank's
#:   charge), and a returned deposited item (PNC's RET DEP ITEM). NOT PAID is read only after an item or return word,
#:  or as the whole row with its references (never inside a memo or a wire's remittance field);
#: - a bank's error or transaction correction, and a correction printed first, glued to its reference too (never a
#:   name that only starts with it: CORRECTIONAL ...; never DEPT OF CORRECTION, which prints it last);
#: - card-purchase refunds: U.S. Bank's DEBIT PURCHASE RET, a reversed card or mobile purchase printed first (REV
#:  MOBILE, POS, DEBIT, PURCHASE, ACH or CARD) and the card-shaped labels (_CARD_REFUND_LABELS). The
#:   leading REV form needs a transaction word, a reference or the row's end after the rail word, or no legal-form word
#:   later on the row (never REV MOBILE LLC ...);
#: - a provisional credit cut to CR, an unauthorized-ACH settlement (never a company's name: no legal-form word
#:   later), and an e-Transfer the holder reclaimed (RECLAIM with its reference glued after it, or last on the row:
#:  CIBC's E TRANSFER RECLAIM<digits>; never a payer's word, RECLAIM CONTOSO LLC or RECLAIMED ...);
#: - the French reversal, return and refund words RENV, RENVERSEMENT, RETOUR and REMBOURSEMENT (REMBOURSEMENT with
#:  §7.11's provider carve-out, _remboursement_from_a_provider). RETOUR needs a reference, MDSE or
#:   MARCHANDISE, or the row's end after it, or no legal-form word later (never RETOUR CONTOSO INC);
#: - a fee waiver (FEE WAIVE, WAIVED, WAIVER) and a courtesy refund (TD's WIRE OUT COURTESY REF).
#: Read on credits only, by step 3 and, on the credit row, by pass 4's revenue side (_CREDIT_PAIR_MARKER_PATTERNS); the
#: lender side of pass 4 never reads them.
#:
#: And these arms, each copied verbatim in
#: true_revenue._POSSIBLE_RETURN and in tools/revenue_census.py (_REVERSAL_MARKERS_56, on the masked text), where a test
#: keeps the three copies in step:
#: - a Quebec returned item (EFFET RETOURNE, EFFETS RETOURNES, the bank's cut EFFET RET);
#: - CIBC's reversal of the holder's cheque or pre-authorized debit (CONTRE-PASSATION DE CHEQUE|DEBIT ..., its hyphen
#:   normalized to a space or dropped);
#: - RBC's French refused item, the bank crediting back a payment refused for no funds (EFFET|CHEQUE REFUSE SANS
#:   PROVISION; a lost accent leaves REFUS);
#: - the English check-word form of NOT PAID (CHECK|CHEQUE|CHK|CHQ [<n>] NOT PAID). At the row's head
#:   only (a spaced or glued leading date before it, spaces the backstop's label removal leaves), as the whole-row NOT
#:   PAID is read: never inside a wire's remittance field, a person-to-person memo or an ACH entry description;
#: - an e-Transfer the holder reclaimed with a spaced or colon-separated reference, the rail word (INTERAC, E TRANSFER,
#:   E TFR) printed right before RECLAIM and a reference holding a digit right after it, or TD's RECLAIM E-TFR. Never
#:   RECLAIM as a payer's word, nor after a reference (a sender's name follows it there);
#: - the fee waiver, now with no legal-form word later on the row (never a company named <word> FEE WAIVER ... INC), as
#:   RETOUR, REV and UNAUTHORIZED read.
#: The lost accent (a replacement character the French text layer can
#: leave, normalized to a space) is tolerated inside CHEQUE ('CH QUE REFUS SANS PROVISION') and after RETOURN ('EFFET
#: RETOURN', 'EFFETS RETOURN S'), as after REFUS; the REFUS ... SANS PROV tail stays mandatory after CH QUE, so a name
#: or a town ('RANCH QUEEN CREEK') never matches.
_RECLAIM_RAIL = r"(?:INTERAC|E ?TRANSFER|E ?TFR)"
_RETURN_REFUND_R2_B08_ARMS = (
    r"(?<![A-Z])EFFETS? (?:RET|RETOUR|RETOURNEE?S?|RETOURN(?: E?E?S)?)\b",
    r"(?<![A-Z])CONTRE ?PASSATIONS?\b",
    r"(?<![A-Z])(?:EFFETS?|CHEQUES?|CH QUES?|CHQ) REFUS\w* SANS PROV(?:ISION)?\b",
    r"^\s*(?:\d{1,2} \d{1,2} ?)?(?:CHECK|CHEQUE|CHK|CHQ)(?: \d+)? NOT PAID\b",
    r"(?<![A-Z])" + _RECLAIM_RAIL + r" ?:? ?RECLAIM ?:? ?(?=[A-Z]{0,4}\d)",
    r"(?<![A-Z])RECLAIM " + _RECLAIM_RAIL + r"(?![A-Z])",
    r"\bFEES? WAIVE[DR]?\b" + _NO_LEGAL_FORM_LATER,
)
_RETURN_REFUND_CREDIT_PATTERNS = (
    re.compile(r"(?<![A-Z])ITEMS? RET(?:URNED)?\b(?! FEES?\b)"),
    re.compile(
        r"(?<![A-Z])(?:ITEMS?|RET|RETN|RTN|RETURN(?:ED)?) NOT PAID\b|^(?:\d{1,2} \d{1,2} )?NOT PAID(?: \S*\d\S*)*$"
    ),
    re.compile(r"\bRET(?:URN(?:ED)?)? DEP(?:OSIT(?:ED)?)? ITEMS?\b"),
    re.compile(r"\b(?:ERROR|TRANSACTION) CORRECTION\b"),
    re.compile(r"^(?:\d{1,2} \d{1,2} )?CORRECTION(?![A-Z])"),
    re.compile(r"\bPURCHASE RET\b"),
    *_CARD_REFUND_LABELS,
    re.compile(r"\b(?:PROVISIONAL|TEMPORARY|CONDITIONAL) CR\b"),
    re.compile(r"\bUNAUTHORI[SZ]ED\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])RECLAIM(?=\d|\s*$)"),
    re.compile(
        r"^(?:\d{1,2} \d{1,2} )?REV (?:MOBILE|POS|DEBIT|PURCHASE|ACH|CARD)\b(?:(?= (?:MOBILE|POS|DEBIT|PURCHASE|ACH|CARD"
        r"|CREDIT|PMT|PAYMENT|TRANSACTION|TXN|WITHDRAWAL)\b| ?\d|\s*$)|" + _NO_LEGAL_FORM_LATER + ")"
    ),
    re.compile(r"(?<![A-Z])(?:RENV|RENVERSEMENT)\b"),
    re.compile(r"(?<![A-Z])RETOUR\b(?:(?= ?\d| MDSE\b| MARCHANDISE\b|\s*$)|" + _NO_LEGAL_FORM_LATER + ")"),
    _REMBOURSEMENT_WORD,
    re.compile(r"\bCOURTESY REF(?:UND)?\b"),
    *(re.compile(arm) for arm in _RETURN_REFUND_R2_B08_ARMS),
)
_CARD_CREDIT_PUSH_WORD = re.compile(
    r"\b(?:VISA DIRECT|MC SEND|VISA MONEY TRANSFER|FASTPAY|INSTANT PAY|INSTANT PAYOUT)\b"
)
#: §7.11 (T5): account verification, Square Capital's SQ CAP, SBA and EIDL disbursements (the tax-refund forms sit
#: in _NON_REVENUE_CREDIT_PATTERNS).
_ACCOUNT_VERIFICATION_CREDIT = re.compile(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b")
#: §7.11 (T19 and this spec): a book or funds transfer is own-account only when no third-party originator is printed.
_BOOK_OR_FUNDS_TRANSFER = re.compile(r"\b(?:BOOK|FUNDS?) TRANSFER\b")
#: §7.11: the Electronic Funds Transfer channel, never a book or funds transfer between accounts.
_EFT_FUNDS_TRANSFER = re.compile(r"\bELECTRONIC FUNDS TRANSFER DEPOSIT\b")

#: In the 5.5 veto patterns below (the recurrence, card, operating, employer, transport, auction, property,
#: payer-remittance, public-payer and wire vetoes) a veto spelling of four letters or more (all its words counted)
#: takes a (?<![A-Z]) left boundary, the owner's card-form convention, so digits glued on its left ('0102CHBK',
#: '1234PAYROLL') never hide it; a spelling of three letters or fewer keeps \b, since a digit glued to it is usually an
#: ID's suffix ('ID 1234CB'). Each spelling counts on its own: FEES reads through a glued digit, FEE does not. Measured
#: exceptions (the cached corpus): the card veto's BOOK and its DUP spellings keep \b, since a digit glued to them
#: there was a company name or an ID fragment, never the word. \b stays on the right of every word. §7.0: the
#: recurrence pass's veto: pay, financing and verification words and the card-credit labels, read on the row before its
#: receiver fields.
_RECURRENCE_VETO = re.compile(
    r"(?<![A-Z])(?:LOANS?|CAPITAL|CAPI|CAPIT|CAPITA|CAPSEC|ADVANCE|FINANC\w*|LEND\w*|CASH ADV\w*"
    r"|PAYROLL\w*|PAYRLL|PAYROL|PAYRL|DIR ?DEP|DIRDEP|DIRECT DEP|SALARY|SALARIES|REG SAL|WAGES?|NET ?PAY|BONUS"
    r"|REIMB\w*|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY|VERIFICATION|INSUR\w*|DEBIT CARD CREDIT|POS CREDIT)\b"
    r"|\b(?:CAP\d*(?:SEC)?|FIN|ADV|MCA)\b"
)
#: §7.0: FUNDING vetoes recurrence too, except on the settlements of the platforms that print it there.
_FUNDING_WORD = re.compile(r"(?<![A-Z])(?:FUNDING|FUNDED)\b")
_FUNDING_SETTLEMENT_ENTITIES = frozenset({"TapGoods Payments", "Braintree", "Buildium"})
#: §7.0, §5.2: the operating sources whose payout rows print the merchant's store name, which is the holder's, in the
#: entry field: the food-delivery and ordering platforms of the registry ('DOORDASH INC DES:<store> CAPITA ...
#: INDN:<store> CAPITAL GROUP'; BMO's 'DIRECT DEPOSIT DOORDASH <store> MSP/DIV'). Only on their rows does the
#: recurrence veto spare a veto word that is one of the holder's own words. On every other source (Square, Stripe,
#: PayPal, Shopify, the marketplaces and processors) the entry field is the platform's own wording, and a holder named
#: like a veto word ('CAPITAL CITY BAKERY LLC', 'SAMPLE LENDING LLC') would otherwise let that source's financing
#: credits verify ('SQUARE INC DES:CAPITAL'), so a veto word always vetoes there. The registry's Uber (driver payouts)
#: and Instacart (shopper payouts) pay no store and stay out.
_STORE_NAME_PAYOUT_ENTITIES = frozenset({
    "DoorDash", "Uber Eats", "Grubhub", "SkipTheDishes", "ezCater", "Menufy", "Snackpass",
})
#: §7.0, §7.8, §7.10: the absolute micro-deposit floor, in whole dollars.
_MICRO_DEPOSIT_FLOOR = 1
#: §8.9, §8.10: a lease-to-own or patient financier's payout (customer_financing_payout) is a large one-off lump sum,
#: held until sourced (customer_financing_lump_sum), when it is this many whole dollars or more and is an incoming
#: wire, a whole multiple of CUSTOMER_FINANCING_LUMP_ROUND dollars or at least CUSTOMER_FINANCING_LUMP_SHARE percent of
#: the statement's posted credits; and the financier makes fewer than CUSTOMER_FINANCING_SERIES_MIN payouts in the
#: statement (the row included) of at least CUSTOMER_FINANCING_SERIES_SHARE percent of its amount (three or more
#: similar-size payouts are an ordinary series).
CUSTOMER_FINANCING_LUMP_FLOOR = 10_000
CUSTOMER_FINANCING_LUMP_ROUND = 1_000
CUSTOMER_FINANCING_LUMP_SHARE = 50
CUSTOMER_FINANCING_SERIES_MIN = 3
CUSTOMER_FINANCING_SERIES_SHARE = 50
_PROCESSOR_CONTEXT_TYPES = frozenset({"merchant_processor", "invoice_and_receivables"})

#: §7.7: the NACHA claim-payment entry. The unbounded branch takes only the full token (never THECLAIMPMT).
_HCCLAIMPMT = re.compile(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b")
#: §8.1 (T14): an insurer's customer-payment wording (a DRP payment, a vendor payment, a commission).
_INSURER_CUSTOMER_PAYMENT = re.compile(
    r"\b(?:DRP|VENDOR ?(?:PMT|PAY|PAYMENT)|COMM?ISS?IONS?|AGT ?COMM|AGENT COMP|AGTEFT|REPAIR)\b"
)

#: §7.5: the payer's accounts-payable remittance (credits only), read on the revenue text and the joined text.
_PAYER_REMITTANCE_CREDIT_PATTERNS = (
    re.compile(r"\bACC(?:OUN)?TS? PAYABLE\b"),
    re.compile(r"^DIRECT DEPOSIT\b(?=.* AP CC$)"),
    re.compile(r"\bA ?P (?:PMTS?|PAYMENTS?|PYMTS?)\b"),
    re.compile(r"\bCO ENTRY DESCR A ?P\b"),
    re.compile(r"\b(?:CCD)?ACC PAY\b"),
    re.compile(r"\bVENDOR ?(?:PMTS?|PAYMENTS?|PAY|PYMTS?)(?:SEC)?\b"),
    re.compile(r"\bTRADE PAY(?:MENTS?)?(?:SEC)?\b"),
    # PAYABLES is Bill.com's payer-side debit wording: never read on a row that prints BILL COM (_payer_remittance).
    re.compile(r"\bPAYABLES\b"),
    re.compile(r"\bPO REMIT(?:TANCE)?\b"),
    re.compile(r"\bAVID ?PAY\b|\bAVIDXCHANGE\b|\bCOUPA PAY\b|\bPAYMODE\b"),
    re.compile(r"\bPAYING BILLS? (?:\d|INV)|\bFOR \d+ BILLS\b"),
    re.compile(r"\bBI ?LL COM (?:INV|MULTIPLE INVOICES|RECEIVABLE)\b|\b(?:DESCR|DES) BI ?LL COM\b"
               r"|\bRECEIVABLE\b(?=.*\bBI ?LL COM\b)"),
    re.compile(r"\bINV(?:OICE)? (?:PMT|PYMT)\b|\b(?:OF|FOR) INVOI ?CES?\b"),
    re.compile(r"\bRMR IV\b"),
    re.compile(r"\bPAIEMENT (?:DE )?FACTURE\b"),
)
_BILL_COM = re.compile(r"\bBI ?LL COM\b")
#: §7.5: the invoice number counts only with a payment-channel word, and never after CREATED FROM or TRANSFER FROM.
_INVOICE_NUMBER = re.compile(r"(?<!\bCREATED FROM )(?<!\bTRANSFER FROM )\bINV(?:OICE)?S?(?: (?:NO|NUM|NUMBER|N))? ?\d")
_PAYMENT_CHANNEL_WORD = re.compile(
    r"\b(?:ACH|PMT|PAYMENTS?|ZELLE|WIRE|FEDWIRE|CHIPS|CCD|CTX|PPD|EFT|RTP|REMIT)\b"
)
#: §7.6 arm B: a public payer anchored on the payer name. A Texas county mutual is a private carrier, never a county:
#: `<WORD> COUNTY` (or PARISH, TOWNSHIP, BOROUGH) followed by an insurer word (MUTUAL and its cuts MUTUA and MUT, INS,
#: INSUR..., CASUALT..., INDEMN..., ASSUR..., LLOYDS) is no public payer ('PROG COUNTY MUT', 'STATE FARM COUNTY MUTUAL
#: INS CO'). Never FIRE (a county fire department) or SELF ('<NAME> COUNTY SELF INSURANCE FUND' stays a government
#: payer, a public insurance programme), and INS only as a whole word (never INSPECTIONS). Credit-side only:
#: government_payer, _public_named, _public_payer_remittance and the payer-remittance veto read this pattern; no debit
#: or lender reading does. Never MUTUAL AID ('<NAME> COUNTY MUTUAL AID' is a public mutual-aid compact, no carrier).
_PUBLIC_PAYER_NAME = re.compile(
    r"^((?:\S+ ){0,3})(?:TREAS \d{3}"
    r"|(?:STATE|COUNTY|CITY|TOWN|VILLAGE|TOWNSHIP|BOROUGH|PARISH|DISTRICT|PROVINCE|COMMONWEALTH|GOVERNMENT|GOVT"
    r"|MUNICIPALITY) OF [A-Z]"
    r"|(?<!\bFROM )(?<!\bTO )(?<!\bTHE )(?<!\bOF )(?<!\bAND )(?<!\bINTO )\b[A-Z]{3,} (?:COUNTY|PARISH|TOWNSHIP|BOROUGH)\b"
    r"(?! (?:MUTUAL(?! AID\b)|MUTUA|MUT|INS|INSUR\w*|CASUALT\w*|INDEMN\w*|ASSUR\w*|LLOYDS)\b)"
    r"|(?:DEPT|DEPARTMENT|MINISTRY) OF\b|(?:DHS|DHHS|DSHS|DCF|DCFS|DSS)\b|SCHOOL DIST(?:RICT)?\b|DFAS\b)"
)
_PUBLIC_PAYER_TEMPLATE = re.compile(
    r"^(?:ELECTRONIC (?:CREDIT|DEPOSIT)(?: FROM)?|ACH (?:CORP )?CREDIT|ACH DEPOSIT|CCD DEPOSIT|DEPOSIT FROM"
    r"|PREAUTHORIZED CREDIT|EFT CREDIT)\b ?"
)
_PUBLIC_PAYER_NAME_VETO = re.compile(
    r"(?<![A-Z])(?:DEPT OF REVENUE|DEPARTMENT OF REVENUE|TAXATION|COMPTROLLER|TREASURER|DEPT OF LABOR|UNEMPLOYMENT"
    r"|WORKFORCE)\b|FUNDING|FUNDER|FINANC|CAPITAL|LENDING|LENDER"
)
_TREASURY_BOILERPLATE = re.compile(
    r"\bADDITIONAL INFORMATION IS AVAILABLE FOR THIS PMT CONTACT A TREASURY SALES OFFICER FOR ASSISTANCE\b"
)
#: §7.6: the whole-row veto, by group; §8.1 holds a public payer's non-sale credit on the first groups.
_PUBLIC_PAYER_NON_SALE_WORDS = re.compile(
    r"(?<![A-Z])(?:TAXES|TAXRFD|TAX ?REF(?:UND)?S?|REFUNDS?|STUREFUND|R(?:E)?F(?:U)?ND|(?:XX)?SOC SEC|SUPP SEC"
    r"|(?:XX)?VA BEN\w*|BENEF\w*)\b|\b(?:TAX|RFD|EIC|SSI|BEN)\b|[A-Z]*REFUNDS?\b|[A-Z]*RFND\b"
    r"|(?<![A-Z])(?:FED SAL|SALARY|PAYROLL|WAGES?|STIPENDS?|PER DIEM|RETIRE\w*|PENSION|ANNUIT\w*)\b"
    r"|(?<![A-Z])(?:UNEMPLOY\w*|STIMULUS|GRANTS?|RELIEF|DISASTER|CARES|SBAD|EIDL|EIDG|LOANS?|ADVANCES?|FORGIV\w*)\b"
    r"|\b(?:UI|PPP|SBA|ADV)\b"
    r"|(?<![A-Z])(?:CHI?LD ?SUPP\w*|CHILD ?CTC|JURY|RESTITUTION|FOSTER|ADOPT\w*|KINSHIP|WORK(?:ERS)? ?COMP)\b|\bCTC\b"
    r"|(?<![A-Z])(?:CLAIMS?|AWARDS?|SUBSID\w*|DISB\w*|PROCEEDS|UNCLAIMED|OVERPA\w*|OVERP(?:Y)?MT|REBATES?|REIMB\w*"
    r"|BONDS?|ESCROW|RETURN(?:ED)?|STABILI[SZ]\w*|OFFSET|RECOVERY|ARPA|RESCUE|ERTC|INCENTIVES?|TUITION)\b|\bERC\b"
    r"|(?<![A-Z])ASSISTANCE\b"
)
_PAYOUT_FORMS = tuple(
    (entity, label, re.compile(pattern))
    for entity, forms in OPERATING_SOURCE_PAYOUT_FORMS.items()
    for label, pattern in forms
)
