"""Shared descriptor vocabulary: field labels, company forms, rails, category patterns."""
from __future__ import annotations

import re

from analysis.description_text import (
    RECEIVER_FIELD_LABELS,
    RECEIVER_NAME_LABELS,
    _AMEX_LABEL_ORIGINATOR,
    _AMEX_TEMPLATE_ID,
    _AMEX_TEMPLATE_PAYER,
    _AMEX_TEMPLATE_RECEIVER,
)


#: A factor's payout is the business's own sales, paid by the factor that bought
#: its invoices. A credit from a payee of these states is not financing proceeds:
#: it takes the operating-revenue path, as a PAYOUT_CREDIT_ENTITIES credit does,
#: and it still carries its group's flag.
_FLAGGED_REVENUE_CREDIT_STATES: frozenset[str] = frozenset({"factoring"})


#: Premium-finance wording on a row no premium-finance alias claimed is premium
#: financing too. Read by the insurance rule of `classify_transaction` only; credit
#: revenue reads the registries.
_PREMIUM_FINANCE_WORDING_PATTERNS = (
    re.compile(r"\bPREM(?:IUM)? ?FIN(?:ANCE|ANCING)?\b"),
    re.compile(r"\bINSPREMFIN\b"),
)
_REFUND_REVERSAL_PATTERNS = (
    re.compile(r"\bREFUND(?:ED)?\b"),
    re.compile(r"\bREVERS(?:AL|ED|E)\b"),
    re.compile(r"\bVOID(?:ED)?\b"),
    re.compile(r"\bCANCEL(?:LED|ED|LATION)?\b"),
    re.compile(r"\bRETURNED PAYMENT\b"),
    re.compile(r"\bPAYMENT RETURN(?:ED)?\b"),
    re.compile(r"\b(?:TRANSFER|E TRANSFER|ETRANSFER) RETURNED\b"),
    re.compile(r"\bRETURNED (?:TRANSFER|DEPOSIT)\b"),
    re.compile(r"\bPURCHASE RETURN(?:ED)?\b"),
    re.compile(r"\bMERCHANT RETURN\b"),
    re.compile(r"\bDEBIT CARD (?:CREDIT|RETURN)\b"),
    re.compile(r"\b(?:ACH|CARD|MERCHANT) RETURN(?:ED)?(?: CREDIT)?\b"),
    re.compile(r"\bRETURN CREDIT\b"),
    re.compile(r"\bRETURN OF POSTED (?:CHECK|CHEQUE|ITEM)\b"),
    re.compile(r"\bCHARGEBACK\b"),
    re.compile(r"\bPOS CREDIT\b"),
    re.compile(r"\bCREDIT ADJUSTMENT\b"),
    re.compile(r"\bREJECTED\b"),
    re.compile(r"\bRETURNED ACH\b"),
    re.compile(r"\bDEPOSITED ITEM RETURNED\b"),
)
_POS_PATTERNS = (
    re.compile(r"\bPOS\b"),
    re.compile(r"\bPOINT OF SALE\b"),
    re.compile(r"\bCARD PURCHASE\b"),
    re.compile(r"\bDEBIT CARD PURCHASE\b"),
    re.compile(r"\bDEBIT CARD CREDIT\b"),
    re.compile(r"\bDEBIT PURCHASE\b"),
    re.compile(r"\bBUSINESS DEBIT MERCH(?:ANT)?\b"),
    re.compile(r"\bINTERAC PURCHASE\b"),
    re.compile(r"\bCONTACTLESS PURCHASE\b"),
    re.compile(r"\bTAP PURCHASE\b"),
    re.compile(r"\bVISA DEBIT PURCHASE\b"),
    re.compile(r"\bMASTER ?CARD DEBIT PURCHASE\b"),
    re.compile(r"\bCHECK ?CARD\b"),
    re.compile(r"\bPURCHASE AUTHORI[ZS]ED\b"),
    # Bank card-purchase labels of the same kind (BofA MOBILE PURCHASE, CIBC RETAIL PURCHASE, Regions PIN
    # PURCHASE) and the French card-purchase forms the corpus prints (C/ACHAT, CIBC ACHAT AU DETAIL, RBC ACHAT
    # INTERAC, BMO ACHAT PAR CARTE and ACHAT EN LIGNE). A bare ACHAT is never read: 'ACHAT DE CREANCES' is a
    # factor's wording.
    re.compile(r"\b(?:RETAIL|MOBILE|PIN) PURCHASE\b"),
    re.compile(r"\bC ACHAT\b|\bACHAT (?:AU DETAIL|INTERAC|PAR CARTE|EN LIGNE)\b"),
)
_PAYROLL_PATTERNS = (
    re.compile(r"\bPAYROLL\b"),
    re.compile(r"\bPAYCHEX\b"),
    re.compile(r"\bADP\b"),
    re.compile(r"\bGUSTO\b"),
    re.compile(r"\bCERIDIAN\b"),
    re.compile(r"\bWAGES?\b"),
)
_CHECK_PATTERNS = (
    re.compile(r"\bCHECKS?\b"),
    re.compile(r"\bCHEQUES?\b"),
    # The Canadian, credit-union and short cheque spellings, anchored at the start and with the instrument's
    # number, so a label ('BUS CHQ', '... SHARE DRAFT', Navy Federal's 'Paid To - <payee> Chk nnn') never makes a
    # row a cheque. Bare DRAFT is lender collection wording (AUTO DRAFT, WEB DRAFT).
    re.compile(r"^CHQ ?[0-9]"),
    re.compile(r"^SHARE DRAFTS? ?[0-9]"),
    re.compile(r"^DRAFT WITHDRAWAL DRAFT ?[0-9]"),
    re.compile(r"^(?:IMAGE |PAID )?CHK ?[0-9]"),
    re.compile(r"^CK ?[0-9]"),
)
_DIRECT_DEBIT_LOAN_PATTERNS = (
    re.compile(r"\b(?:DIRECT DEB(?:IT)?|ACH DEBIT|BUSINESS PAD)\b.*\bLOANS?\b"),
    re.compile(r"\bLOANS?\b.*\b(?:DIRECT DEB(?:IT)?|ACH DEBIT|BUSINESS PAD)\b"),
)
#: ... on a row whose D11 payee words are only a bank's template words, or none:
#: the payment names no lender, so it is the statement bank's own loan.
_BANK_TEMPLATE_WORDS = frozenset({"NO", "BR", "AUTOMATED", "COMPTE", "DIVERS", "INTEREST", "CHARGE", "CHARGED"})
_EXPLICIT_REPAYMENT_PATTERNS = (
    re.compile(r"\bLOAN (?:PAYMENT|PMT|PYMT|REPAYMENT)\b"),
    re.compile(r"\b(?:PAYMENT|PMT|PYMT|REPAYMENT) (?:ON |FOR )?(?:A )?LOAN\b"),
    re.compile(r"\b(?:ADVANCE|FINANCING|FUNDING) (?:PAYMENT|PMT|PYMT|REPAYMENT)\b"),
    re.compile(r"\b(?:PAYMENT|PMT|PYMT|REPAYMENT) (?:FOR )?(?:ADVANCE|FINANCING|FUNDING)\b"),
    re.compile(r"\bMCA (?:PAYMENT|PMT|PYMT|REMITTANCE)\b"),
    *_DIRECT_DEBIT_LOAN_PATTERNS,
)

#: CANCELLED's French words ('VIREMENT ANNULE', 'VIREMENT INTERAC ANNULE', 'ANNUL VFC'), whole words with the
#: veto convention's (?<![A-Z]) left boundary, so a digit glued on the left never hides one. S4.2 fix round 5:
#: and their plurals, ANNULES and ANNULEES.
_FRENCH_CANCEL_CREDIT_PATTERN = re.compile(r"(?<![A-Z])(?:ANNUL|ANNULE|ANNULEE|ANNULES|ANNULEES|ANNULATION)\b")
_REVERSAL_CANCELLATION_CREDIT_PATTERNS = (
    *_REFUND_REVERSAL_PATTERNS,
    re.compile(r"\b(?:E TRANSFER|ETRANSFER|TRANSFER) (?:RETURNED|CANCEL(?:LED|ED)?|CNCL)\b"),
    re.compile(r"\b(?:RETURNED|CANCEL(?:LED|ED)?|CNCL) (?:E TRANSFER|ETRANSFER|TRANSFER)\b"),
    re.compile(r"\bCNCL\b"),
    _FRENCH_CANCEL_CREDIT_PATTERN,
    re.compile(r"\bREIMBURSEMENT\b"),
    re.compile(r"\bNSF\b"),
    re.compile(r"\bRETURNED (?:PAYMENT|ITEM|CHECK|CHEQUE|DEPOSIT)\b"),
    re.compile(r"\b(?:CHECK|CHEQUE) (?:RETURNED|REVERSED)\b"),
    re.compile(r"\bBANK (?:CORRECTION|ADJUSTMENT|ERROR)\b"),
    re.compile(r"\bCREDIT (?:CORRECTION|ADJUSTMENT)\b"),
    re.compile(r"\b(?:PROVISIONAL|TEMPORARY|CONDITIONAL) CREDIT\b"),
    re.compile(r"\bCREDIT PENDING (?:REVIEW|FINAL|VERIFICATION)\b"),
)

_SETTLEMENT_REVERSAL_PATTERNS = (
    re.compile(r"\bRETURN(?:ED)?\b"),
    re.compile(r"\bREJECTED\b"),
    re.compile(r"\bREVERS(?:AL|ED|E)\b"),
    re.compile(r"\bVOID(?:ED)?\b"),
    re.compile(r"\bCANCEL(?:LED|ED|LATION)?\b"),
    re.compile(r"\bCNCL\b"),
    re.compile(r"\bNSF\b"),
    re.compile(r"\bCHARGEBACK\b"),
)

#: The own-account sources a transfer names after FROM also include DDA, a cut CHECKG, TD's credit-line CL, a loan
#: account LN, and the holder's card or credit line (CRD, CREDIT CARD, CREDIT LINE, LINE OF CREDIT, LOC): a draw on
#: the holder's own card or line is no sale.
_INTERNAL_ACCOUNT_SOURCE = (
    r"(?:ACCOUNTS?|CHK|CHECKING|CHECKG|CK|SAV|SAVINGS|SV|SHARES?|MMA|DDA|"
    r"MONEY MARKET|PCA|(?:SUB )?RESERVE ACCOUNTS?|CL|LOC|LN|CRD|CREDIT CARD|CREDIT LINE|LINE OF CREDIT)"
)
#: FRM is FROM in the own-account forms ('TFR FRM CHECKING', 'INTERNET XFR FRM CHECKG').
_FROM_WORD = r"(?:FROM|FRM)"
#: §8.2, §8.4: _INTERNAL_ACCOUNT_SOURCE's spellings in two lists (a test keeps them equal to it): the short tokens,
#: which can be a company's first letters ('CL FABRIKAM INC', 'LOC CONTOSO LLC'), and the long spellings, read as
#: before. The source list itself is unchanged: its account words, _counterparty_tokens' and the 'FROM <n> <source>'
#: form read it whole.
_SHORT_ACCOUNT_SOURCES = r"CHK|CHECKG|CK|SAV|SV|MMA|DDA|PCA|CL|LOC|LN|CRD"
_LONG_ACCOUNT_SOURCES = (
    r"ACCOUNTS?|CHECKING|SAVINGS|SHARES?|MONEY MARKET|(?:SUB )?RESERVE ACCOUNTS?|CREDIT CARD|CREDIT LINE|LINE OF CREDIT"
)
#: An own-account source a transfer designates after FROM: a long spelling as a whole word (Navy Federal's 'FROM SHARES
#: <name>' stays the holder's own transfer), or a short token only before an account number, a masked account, ACCOUNT
#: or ACCT, or at the row's end ('FROM CL 1234567', 'FROM LOC XXXXXX1234', 'FROM CK ACCT 1234', 'FROM CL'). A short
#: token before a name ('FROM CL FABRIKAM INC') is that company's name: the row falls to the named-transfer readings
#: (T13, Q4, Q5), never the strong rule.
_DESIGNATED_ACCOUNT_SOURCE = (
    rf"(?:(?:{_LONG_ACCOUNT_SOURCES})\b|(?:{_SHORT_ACCOUNT_SOURCES})(?= (?:\d|X+\d*\b|ACCOUNTS?\b|ACCT\b)|$))"
)
#: The own-account forms whose sender a bank may print after the designation (Bank of America's 'ONLINE TRANSFER
#: FROM CHK <n> CONFIRMATION <reference> <sender>', a credit union's 'TFR FROM X...<n> TRANSFER DEPOSIT <sender>'):
#: named, so the strong rule refuses them when that sender is not the holder (_named_sender_after_designation). The
#: source is a designated one (_DESIGNATED_ACCOUNT_SOURCE).
_TRANSFER_FROM_ACCOUNT = re.compile(rf"\b(?:TRANSFER|XFER|XFR|TFR) {_FROM_WORD} {_DESIGNATED_ACCOUNT_SOURCE}")
_CHANNEL_TRANSFER_FROM_ACCOUNT = re.compile(
    # Truist's own-account layout repeats its channel word between TRANSFER and FROM ('ONLINE TRANSFER ONLINE FROM
    # <n>', the layout analysis/bank_repairs.py names). A MOBILE there is not read (no corpus layout confirms it as
    # own-account): such a row names no counterparty and is held under Q2. The source is a designated one
    # (_DESIGNATED_ACCOUNT_SOURCE).
    rf"\b(?:BRANCH|ONLINE|MOBILE|INTERNET|HOME|BUSINESS ONLINE|TELEPHONE)"
    rf"(?: BANKING)?(?: ACCOUNT)? (?:TRANSFER|XFER)(?: TRANSFER| ONLINE)? {_FROM_WORD} "
    rf"(?:{_DESIGNATED_ACCOUNT_SOURCE}|(?:X+\d*|\d{{3,}})\b)"
)
_TFR_TRANSFER_DEPOSIT = re.compile(r"\bTFR FROM (?:X+\d*|\d{3,})\b.*\bTRANSFER DEPOSIT\b")
_INTERNAL_TRANSFER_CREDIT_PATTERNS = (
    # §7.11: BOOK TRANSFER and FUNDS TRANSFER are own-account only without a third-party originator
    # (_own_book_or_funds_transfer).
    re.compile(r"\b(?:INTERNAL|ACCOUNT) TRANSFER\b"),
    re.compile(r"\bTRANSFER (?:FROM|BETWEEN) (?:OWN|MY|INTERNAL) ACCOUNTS?\b"),
    _TRANSFER_FROM_ACCOUNT,
    _CHANNEL_TRANSFER_FROM_ACCOUNT,
    re.compile(r"\bTRANSFER DEPOSIT FROM (?:ACCOUNT )?(?:X+\d*|\d{3,})\b"),
    _TFR_TRANSFER_DEPOSIT,
    re.compile(r"\bDEPOSIT TRANSFER FROM (?:X+\d*|\d{3,})\b"),
    re.compile(r"\b(?:ATM )?(?:SH TO SH|SHARE TO SHARE|ACCOUNT TO ACCOUNT) TRANSFER\b"),
    re.compile(r"\bTRANSFER FROM X+\d* TO X+\d*\b"),
    re.compile(
        r"\bTRANSFER FROM (?:X+\d*|\d{3,})(?: \d+){0,4}\b.*"
        r"\b(?:MB|MOBILE) TRANSFER\b"
    ),
    re.compile(r"\b(?:INTER CURRENCY|INTERCURRENCY) TRANSFER\b"),
    re.compile(
        rf"\bTRANSFER\b.*\b(?:ONLINE|MOBILE|INTERNET|HOME)\b.*"
        rf"\bFROM (?:X+\d*|\d{{3,}}) {_INTERNAL_ACCOUNT_SOURCE}\b"
    ),
    re.compile(r"\bTRANSFER (?:INCOMING|CREDIT)\b.*\b(?:SUB )?RESERVE ACCOUNT\b"),
)
#: The holder's own-account sweeps that print no transfer source the patterns above read: an overdraft-protection
#: sweep from the holder's own account, card or line ('OVERDRAFT PROTECTION FROM <n>', 'OD PROTECTION TRANSFER
#: FROM CREDIT CARD', 'OVERDRAFT XFER FROM CREDIT CARD OR LINE', Chase's 'ODP TRANSFER'), and Regions' electronic
#: banking from the holder's checking or savings ('EB FROM CHECKING <n>'). Read by the strong non-revenue rule
#: only (R-d's package pairing keeps _INTERNAL_TRANSFER_CREDIT_PATTERNS).
_OWN_ACCOUNT_SWEEP_CREDIT_PATTERNS = (
    re.compile(r"\bOVERDRAFT PROTECTION(?: (?:TRANSFER|XFER))? FROM\b"),
    re.compile(r"\bOD PROTECTION (?:TRANSFER|XFER)\b"),
    re.compile(r"\bOVERDRAFT (?:XFER|TRANSFER) FROM\b"),
    re.compile(r"\bODP (?:TRANSFER|XFER)\b"),
    re.compile(r"^(?:\d{1,2} \d{1,2} )?EB FROM (?:CHECKING|SAVINGS)\b"),
)


#: The IRS's Treasury form, and the entries that make one of its credits a tax refund or a benefit. The child tax
#: credit and the stimulus (TAX EIP) are personal benefits the true-revenue pass holds (class B). The refund wording
#: is the tax-refund forms' (5.5's TAXEIC spaced or not, a refund word glued or not). The layout words are Chase's and
#: Bank of America's field labels, which name no entry.
IRS_TREASURY_FORM = re.compile(r"(?<![A-Z])IRS TREAS ?\d{3}\b")


#: The French interest credit (TD Canada Trust's CREDIT D'INTERET, the apostrophe dropped or glued, and INTERET
#: CREDITE), as INTEREST CREDIT and CREDIT INTEREST read. And INTERETS GAGNES, CREDITEURS, PAYES and VERSES (interest
#: earned, credited, paid), read on credits only: a debit's INTERETS SUR PRET or INTERETS DECOUVERT is the holder's
#: borrowing cost, never read here. Copied in tools/revenue_census.py.
_FRENCH_INTEREST_CREDIT = re.compile(
    r"(?<![A-Z])CREDIT D ?INTERETS?\b|(?<![A-Z])INTERETS? CREDITES?\b"
    r"|(?<![A-Z])INTERETS? (?:GAGNES?|CREDITEURS?|PAYES?|VERSES?)\b"
)
#: §6.1, §7.11: the customer and invoice descriptors. CUSTOMER is never read in CUSTOMER ID (Truist prints it on
#: every ACH line) and never with CHECK or CHEQUE (Q3). A payer the holder test or the numbered-company guard
#: matches never verifies through them (§5.2).
_CUSTOMER_INVOICE_DESCRIPTORS = (
    re.compile(r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\bCUSTOMER\b(?! ID\b).*\b(?:ACH|PAYMENT|DEPOSIT)\b"),
    re.compile(r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\b(?:ACH|PAYMENT|DEPOSIT)\b.*\bCUSTOMER\b(?! ID\b)"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
)
_BUSINESS_ACCOUNT_PATTERNS = (
    re.compile(r"\bBUSINESS\b"),
    re.compile(r"\bCOMMERCIAL\b"),
    re.compile(r"\bOPERATING\b"),
    re.compile(r"\bMERCHANT\b"),
)
#: T19 (OQ6): Chase's BOOK TRANSFER CREDIT B/O <originator> from someone other than the holder, and Bank of America's
#: WIRE TYPE BOOK IN, are incoming wires, not own-account transfers.
THIRD_PARTY_BOOK_TRANSFER_AS_WIRE = True

#: §7.0: Chase glues the SEC code to the entry description ('CO ENTRY DESCR HCCLAIMPMTSEC CCD'). Bounded to the
#: entry-description field, so a word elsewhere that ends in SEC is untouched.
_GLUED_SEC_CODE = re.compile(
    r"(\bCO (?:ENTRY )?DESCR (?:\S+ ){0,2}?\S{2,}?)SEC (CCD|CTX|PPD|WEB|IAT|COR|TEL|POP|BOC|ARC|RCK|CIE)\b"
)
#: §5.2: the receiver fields, where the bank prints the account holder (PNC labels its RECEIVER NAME). Every
#: receiver vocabulary is built from description_text's one tuple, RECV NAME included.
_RECEIVER_FIELD_LABELS = "|".join(RECEIVER_FIELD_LABELS)
_RECEIVER_NAME_LABELS = "|".join(RECEIVER_NAME_LABELS)
_CREDIT_RECEIVER_FIELD = re.compile(rf"\b(?:{_RECEIVER_FIELD_LABELS})\b")
#: A receiver field's value ends at the next ACH field: CO ID, TRN, TRACE or the SEC code (5.3, shared with
#: _RECEIVER_FIELD_VALUE).
_RECEIVER_VALUE_END = r".*?(?=\b(?:CO ID|TRN|TRACE|PPD|CCD|WEB|CTX|TEL|ARC|BOC)\b|$)"
#: §5.2: an incoming wire's beneficiary field (BNF, NBNF, BENEFICIARY, BNF NAME, as the wire readers name them) with
#: its value, up to the next wire field. ORIG TO BNF is the originator's remittance text, not a beneficiary. The
#: value also ends at every originator label the wire readers read (_WIRE_ORIGINATOR_LABEL: WIRE IN FROM, WIRE FROM,
#: FUNDS TRANSFER CREDIT TT, INBD FUNDS TRANSFER RECEIVED) and at FROM, so 'INCOMING WIRE BNF <holder> FROM STRIPE
#: INC' still names its originator.
_CREDIT_WIRE_BENEFICIARY_VALUE = re.compile(
    r"(?<!\bTO )\b(?:N?BNF|BENEFICIARY)(?: NAME)?\b.*?"
    r"(?=\b(?:REF|OBI|RFB|IMAD|OMAD|TRN|SRF|BBI|SND BK|PMT DET|RMR|ORIG|ORIGINATOR|ORG|B O|WIRE IN FROM|WIRE FROM"
    r"|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER RECEIVED|FROM)\b|$)"
)
#: §5.2: the bank's words printed before the payer, removed before the payer is read (with _PAYEE_TEMPLATE_PREFIX). And
#: American Express's incoming-ACH label (_AMEX_ACH_CREDIT); only when an originator word follows it
#: (_AMEX_LABEL_ORIGINATOR). And the layouts' posting or channel labels that print CREDIT, first and longest first: BMO's
#: 'EDI EFT CCD CREDIT [CCD]', 'INTERNET CREDIT', CIBC's 'PREAUTH CREDIT', Huntington's 'HIP CREDIT RCVD FROM' and 'HIP
#: CREDIT', the French '[I] AVIS DE CREDIT' and 'AUTOMATED CREDIT', so the payer region starts after the label (a bare
#: label names no payer) and the label's CREDIT is never a lender's name word (true_revenue.financing_named).
_REVENUE_TEMPLATE_PREFIX = re.compile(
    r"^(?:EDI EFT CCD CREDIT(?: CCD)?|INTERNET CREDIT|PREAUTH CREDIT|HIP CREDIT RCVD FROM|HIP CREDIT"
    r"|(?:I )?AVIS DE CREDIT|AUTOMATED CREDIT"
    r"|BUSINESS TO BUSINESS ACH CREDIT|CCD DEPOSIT|CTX DEPOSIT|ELECTRONIC DEPOSIT FROM|ELECTRONIC DEPOSIT"
    r"|ELECTRONIC CREDIT|ACH CORP CREDIT|ACH DEPOSIT|ACH CREDIT|DEPOSIT FROM|PREAUTHORIZED CREDIT|EFT CREDIT"
    r"|DIRECT DEPOSIT|MISC PAYMENT|BILL PAYMENT|ONLINE TRANSFER PAYMENT CREDIT(?=" + _AMEX_LABEL_ORIGINATOR + r"))\b ?"
)
#: American Express Business Checking prints every incoming ACH credit as 'ONLINE TRANSFER PAYMENT CREDIT <originator>
#: <entry> <id> [<receiver account>] <receiver name> EXTERNAL <originating bank> ID <trace>' (the NACHA company name,
#: entry description, a four-digit id it prints masked as '*****NNNN', the receiver's own account and name, the sending
#: bank). It is an ACH template, never a transfer: the label's TRANSFER names no counterparty. The originator and its
#: entry are the text before the id (the payer region); the receiver block, up to EXTERNAL, is a receiver field
#: (_before_receiver, _without_receiver_value), so the receiver's masked account and the holder's own name never read
#: as the payer. The id is the last four-digit token before the receiver block. Built from the template's pieces
#: (_AMEX_TEMPLATE_TAIL's).
_AMEX_ACH_CREDIT = re.compile(
    r"^ONLINE TRANSFER PAYMENT CREDIT (?P<payer>" + _AMEX_TEMPLATE_PAYER + r") (?P<id>" + _AMEX_TEMPLATE_ID + r")"
    r"(?P<receiver>" + _AMEX_TEMPLATE_RECEIVER + r") EXTERNAL\b"
)
#: §5.2: a wire's originator starts after one of these labels (never ORIG CO NAME, ORIG ID or ORIG TO BNF).
#: ORIGINATOR and ORG take the same guards: ORIGINATOR TO BENEFICIARY (ORG TO BNF) is a purpose field's label, never
#: an originator label.
_WIRE_ORIGINATOR_LABEL = re.compile(
    r"\b(?:B O|ORIGINATOR(?: NAME)?(?! TO BNF\b| TO BENEFICIARY\b)|ORIG(?! CO NAME\b)(?! ID\b)(?! TO BNF\b)"
    r"|ORG(?! TO BNF\b| TO BENEFICIARY\b)|WIRE IN FROM|WIRE FROM"
    r"|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER RECEIVED)\b ?"
)
#: §5.2: ... and ends at the next wire field. ID is read as a field too: Bank of America prints 'ORIG:<name> ID:<n>'.
#: So does the originator-to-beneficiary phrase, which opens a purpose field.
_WIRE_FIELD_END = re.compile(
    r"\b(?:BNF|NBNF|BENEFICIARY|BBI|OBI|REF|SRF|TRN|RFB|IMAD|ACCT|SND BK|ID"
    r"|(?:ORG|ORIGINATOR) TO (?:BNF|BENEFICIARY))\b"
)
#: §5.2, §7.9 (Santander's layout): 'USD WIRE IN FROM <sending bank> ACCT <n> <originator> REF <purpose>'. The words
#: after WIRE IN FROM name the sending bank; the originator follows the account number (the field §7.9 cuts at 16).
_SANTANDER_WIRE = re.compile(r"^(?:[A-Z]{3} )?WIRE IN FROM\b(?P<bank>.*?)\bACCT \d+ (?P<originator>.*?)(?=\bREF\b|$)")
#: §5.2: a person-to-person or transfer sender follows FROM and ends at one of these words. And at Truist's 'PAYMENT ID'
#: label ('ZELLE BUSINESS PAYMENT FROM <sender> PAYMENT ID <reference>'): the leftmost match ends the sender at PAYMENT,
#: so the label's PAYMENT never joins a person's name (B7's surname reading).
_SENDER_END = re.compile(r"\b(?:ON|REF|CONF|MEMO|TRN|ID|FOR|NOTE|PMT INFO|PAYMENT INFO|PAYMENT ID)\b")
#: §5.2: the entry fields: Bank of America's DES, Chase's CO ENTRY DESCR, a wire's purpose fields, a transfer's memo.
_BOFA_ENTRY_FIELD = re.compile(
    r"\bDES (.*?)(?=\b(?:ID|INDN|CO ID|IND NAME|IND ID|CCD|CTX|PPD|WEB|IAT|TEL|POP|BOC|ARC|RCK|CIE)\b|$)"
)
_CHASE_ENTRY_FIELD = re.compile(
    r"\bCO (?:ENTRY )?DESCR (.*?)(?=\b(?:SEC|TRACE|EED|IND ID|IND NAME|TRN|CCD|CTX|PPD|WEB|IAT)\b|$)"
)
_MEMO_ENTRY_FIELD = re.compile(r"\b(?:MEMO|NOTE|FOR|PMT INFO|PAYMENT INFO)\b (.*?)(?=\b(?:CONF|REF|TRN|ID)\b|$)")

#: §5.2: the generic words of the definition memo's categorize.py, inlined (that file is private).
REVENUE_GENERIC_WORDS: frozenset[str] = frozenset("""
DEPOSIT DEPOSITS CREDIT CREDITS TRNSFR TRANSFER OTHER REAL TIME INCOMING RECEIVED ACH ELECTRONIC DIRECT MEMO MISC BILL
FILE INTERNET BANKING EXTERNAL RECD CR DEP ONLINE MOBILE INSTANT FUNDS ADJUSTMENT ADJ MONEY VISA CORPORATE PREAUTHORIZED
SEQ IN NEW ITEM ITEMS MSP DIV DP FD BR BRANCH RECEIPT RECEIVE PAYMENT DOMESTIC TRANS CUSTOMER DDA SAV SAVINGS CHECKING
CHK ACCOUNT ACCT FR FROM WIRE REF TRN TYPE DATE ET USD TRF WT FED NUMBER NO NOTPROVIDED INTERNATIONAL FX CAD SWIFT IMAD
OMAD SRF RFB OBI PM AM ON AT VIA CARD ID CONF CONFIRMATION TRACE SENT RCVD PMNT PMT AUTHORIZED SEQUENCE
""".split())
#: §5.2: the holder-name noise of the same file, plus the bank-template and product words, the remaining province and
#: territory names and every generic word.
HOLDER_NOISE: frozenset[str] = frozenset("""
BUSINESS CHECKING ACCOUNT LLC INC CORP COMPANY THE OF AND SAVINGS PLATINUM COMPLETE ANALYZED COMMERCIAL ADVANTAGE
FUNDAMENTALS SIMPLE BASIC PREFERRED INTEREST OPERATING PERFORMANCE SELECT ESSENTIALS CHECK TOTAL PREMIUM SMALL STANDARD
FREE DBA USD CAD ACCT PLUS ELITE EVERYDAY BANKING DEPOSIT MONEY MARKET ONTARIO CANADA ALBERTA QUEBEC BRITISH COLUMBIA
SASKATCHEWAN MANITOBA NOVA SCOTIA LTD LIMITED CORPORATION INCORPORATED LLP PLLC GROUP HOLDINGS SERVICES ENTERPRISES USA
AMERICA AMERICAN NATIONAL INTERNATIONAL TRUST SOLUTIONS MANAGEMENT CO LP
COMPTE DIVERS BANK BANQUE CAISSE ENTREPRISE AFFAIRES OPERATIONS CU FCU
BRUNSWICK NEWFOUNDLAND LABRADOR PRINCE EDWARD ISLAND YUKON NORTHWEST TERRITORIES NUNAVUT
""".split()) | REVENUE_GENERIC_WORDS
#: §5.2: common name-starters that are never a holder's or a payer's first distinctive word.
_NAME_STARTERS = frozenset({
    "FIRST", "NORTH", "SOUTH", "EAST", "WEST", "CENTRAL", "UNITED", "GLOBAL", "PREMIER", "ROYAL", "GOLDEN", "GREAT",
    "CITY", "STATE", "COUNTY",
})
#: The holder test's noise: HOLDER_NOISE, the bank and product abbreviations that lead account names (BMO, ADV for
#: Advantage, BUS for Business, CKG for Checking) and GENERAL (a product or nickname's word), read on both the
#: holder's and the payer's side of the holder test (holder_words, holder_named). The payer, debit and lender readers
#: keep HOLDER_NOISE, so no payer key, debit reading or lender name moves.
_HOLDER_TEST_NOISE: frozenset[str] = HOLDER_NOISE | frozenset({"BMO", "ADV", "BUS", "CKG", "GENERAL"})
#: A trade-name marker inside a holder's name ('CONTOSO LLC DBA NORTHWIND AGENCY'); each side is a name of the
#: holder's.
_HOLDER_TRADE_NAME = re.compile(r" (?:DBA|D B A|AKA) ")
#: §5.2: a legal-form word after the payer name's first word, or an institution word. CO is never one (Colorado's
#: state code, D11) and TRUST is never one (a family trust is owner money).
_COMPANY_FORM = re.compile(
    r"^\S+ (?:.* )?(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LIMITED|LP|LLP|LLLP|PLLC|ULC|PLC|GMBH|AG"
    r"|SA|SAS|SRL|BV|NV|PTY|DOO|DMCC|SA DE CV)\b"
    r"|\b(?:FOUNDATION|CHURCH|MINISTRIES|UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|HOSPITAL|ASSOCIATION|SOCIETY|COOPERATIVE"
    r"|CO OP)\b"
)
#: §5.2: an ACH or EFT mark: the row is an electronic payment.
_ELECTRONIC_PAYMENT_FORM = re.compile(
    r"\b(?:ORIG CO NAME|CO ENTRY DESCR|DES|CCD|CTX|PPD|IAT|ACH|EFT|ELECTRONIC DEPOSIT|ELECTRONIC CREDIT|ELECTRONIC PMT"
    r"|ELECTRONIC PAYMENT|DIRECT DEPOSIT|MISC PAYMENT|CORPORATE ACH|BILL PAYMENT|EDI|INDN|PREAUTHORIZED CREDIT"
    r"|DEPOSIT FROM|PAID FROM|PAYMENT FROM|CREDIT FROM|MSP DIV|AP CC"
    # American Express's incoming-ACH label (_AMEX_ACH_CREDIT); only when an originator word follows it
    # (_AMEX_LABEL_ORIGINATOR).
    r"|ONLINE TRANSFER PAYMENT CREDIT(?=" + _AMEX_LABEL_ORIGINATOR + r"))\b"
)
#: §5.2, T11: the provinces and territories and CANADA, whole or cut to three or more leading letters, and their
#: postal and common abbreviations.
_PROVINCE_NAMES = (
    "ONTARIO", "QUEBEC", "NOVA SCOTIA", "NEW BRUNSWICK", "MANITOBA", "BRITISH COLUMBIA", "PRINCE EDWARD ISLAND",
    "SASKATCHEWAN", "ALBERTA", "NEWFOUNDLAND AND LABRADOR", "YUKON", "NORTHWEST TERRITORIES", "NUNAVUT", "CANADA",
)
_PROVINCE_ABBREVIATIONS = (
    "ON", "ONT", "QC", "QUE", "NS", "NB", "MB", "MAN", "BC", "B C", "PE", "PEI", "SK", "SASK", "AB", "ALB", "ALTA",
    "NL", "NFLD", "YT", "NT", "NWT", "NU", "CAN",
)
_PROVINCE = "(?:" + "|".join(sorted(
    {name[:length].rstrip() for name in _PROVINCE_NAMES for length in range(3, len(name) + 1)}
    | set(_PROVINCE_ABBREVIATIONS),
    key=lambda value: (-len(value), value),
)) + ")"
#: §5.2, T11 (S4.2 fix round 5): QUEBEC, its cuts and QC: the only province that prints a numbered company as
#: NNNN-NNNN. The P2P sender key reads the same set (true_revenue._numbered_province_sender).
_QUEBEC = "(?:QUEBEC|QUEBE|QUEB|QUE|QC)"
#: The CPA transaction codes BMO prints after a cut numbered company's number ('DIRECT DEPOSIT <n> ONTA AP CC', '...
#: MSP DIV', '... EDI EED'): no name word. And BMO's two-word CPA code pairs (English, French: BPY FAC, CLN PEE, GST
#: TPS, LNS PRE, BUS ENT, RLS LOY, TFS CLI, RIT RIF, CAP CDE, INS ASS, INV PLA), longest first, so a numbered company
#: before one keeps its number. BUS, CAP and INS are read only in their pairs (alone they could start a name word).
_BMO_CODE_PAIRS = (
    "BPY FAC", "CLN PEE", "GST TPS", "LNS PRE", "BUS ENT", "RLS LOY", "TFS CLI", "RIT RIF", "CAP CDE", "INS ASS",
    "INV PLA",
)
_BMO_CODE_TAIL = "(?:" + "|".join(_BMO_CODE_PAIRS) + r"|AP|CC|MSP|DIV|APY|EDI|EED)"
#: §5.2, T11: a numbered company. The template form is read on the row before the receiver fields (BMO cuts the name to
#: the field, so the digits alone decide); the payer-region form keeps the region's leading digit token. Scotiabank,
#: RBC and CIBC print a payment reference in the template's digit slot and then the payer's name ('BILL PAYMENT
#: <reference> <payer> INC', 'MISC PAYMENT <reference> TOWN OF <town>'): the template form fires only when nothing, a
#: province or territory (or a cut of one) or BMO's code tail follows the digits, and both forms read a number of six
#: to ten digits (a Canadian corporation number has at most ten; a longer run is a reference). The province, its cut or
#: the code counts only when it is no name's first word (_PROVINCE_NOT_A_NAME_START). §5.2: the tokens after a numbered
#: company's province (or its cut, or BMO's code) that still name no payer: every leading cut of three letters or more
#: of INCORPORATED, LIMITED, LIMITEE, CORPORATION, COMPANY and UNLIMITED, the other legal forms, BMO's code tail, a
#: trade-name marker and the remittance words. And BMO's code pairs (_BMO_CODE_PAIRS) and Scotiabank's single codes BPY
#: and PAY ('MISC PAYMENT|BILL PAYMENT <n> ONTARIO BPY|PAY').
_NUMBERED_TAIL_WORDS = "(?:" + "|".join(sorted(
    {form[:length] for form in ("INCORPORATED", "LIMITED", "LIMITEE", "CORPORATION", "COMPANY", "UNLIMITED")
     for length in range(3, len(form) + 1)}
    | {"LTD", "LTEE", "ULC", "LLC", "LLP", "MSP", "DIV", "APY", "EDI", "EED", "DBA", "AKA", "INV", "INVOICE", "PMT",
       "PAYMENT", "REF", "BPY", "PAY"}
    | set(_BMO_CODE_PAIRS),
    key=lambda value: (-len(value), value),
)) + ")"
#: A province or territory (or a cut of one), Quebec's form or BMO's code tail after the number that is no payer's
#: first name word: the next token is not a letters-only word of three letters or more outside _NUMBERED_TAIL_WORDS.
#: A token holding digits (RBC's 'ALBERTA RMOD<n>', a reference), a one- or two-letter token (BMO's 'ONTA AP CC'), a
#: legal form or its cut, BMO's code, a trade-name marker, a remittance word or the field's end keep the number; a
#: name word ('NORTH MOUNTAIN PAVING', 'NEW HORIZON PAVING INC', 'NOVA SCOTIA POWER') drops it, so the payer is read.
#: The group is atomic, so the longest spelling decides (NOVA SCOTIA, NEW BRUNSWICK, never NOVA or NEW alone).
#: Residual: a name whose second word has one or two letters ('CAN DO PLUMBING LTD') still reads numbered.
_PROVINCE_NOT_A_NAME_START = (
    rf"(?>(?:{_PROVINCE}|{_QUEBEC}|{_BMO_CODE_TAIL})\b)"
    rf"(?! (?!{_NUMBERED_TAIL_WORDS}(?: |$))[A-Z]{{3,}}(?: |$))"
)
#: A3: a numbered company's number before its province or territory, or Quebec's NNNN NNNN before QUEBEC (the
#: province arm of _NUMBERED_COMPANY_REGION), kept when a wire's sender is read after its label.
_NUMBERED_PROVINCE_START = re.compile(rf"^\d{{6,}} {_PROVINCE}\b|^\d{{4}} \d{{4}} {_QUEBEC}\b")
_NUMBERED_COMPANY_REGION = re.compile(
    rf"^\d{{6,10}}\b(?: {_PROVINCE}\b| (?:[A-Z]+ ){{0,4}}(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|ULC|LLC|LP|CO"
    rf"|COMPANY)\b)"
    # Quebec prints its numbered companies as NNNN-NNNN (normalized NNNN NNNN), always before the province. S4.2 fix
    # round 5: Quebec's words only, so another province's word or code starting a name ('NORTH STAR', 'AB') is none.
    rf"|^\d{{4}} \d{{4}} {_QUEBEC}\b"
)
#: §6.1 step 9b: consumer person-to-person rails (never verified by any step), and real-time or push rails (verified
#: by the operating registry only). In these four gate families every left boundary is (?<![A-Z]), never \b (the
#: owner's card-form convention), so digits glued to a rail or a form ('01/02/2054Zelle', '0102Zelle') no longer hide
#: it; a right boundary stays \b. A form anchored at the row's start accepts a leading MM DD pair, glued or spaced
#: ('01/02 Remote'). Residual (0 corpus rows): a longer prefix before the bare anchored REMOTE or GC form
#: ('0102Remote', '01/02/2054 Remote', '2054 GC 1234 Deposit') still reads no gate. Against the older \b patterns the
#: gate reading only moves toward closed or push; the shared patterns also move the payer region and entry fields of
#: those same rows. The consumer rails' words, one list the rail and the glued-reference split read.
_CONSUMER_P2P_RAIL_WORDS = (
    r"ZELLE|INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|VIREMENT|VFC|AUTODEPOSIT|VENMO|CASH ?APP|SQUARE CASH"
    r"|APPLE CASH|POPMONEY"
)
_CONSUMER_P2P_RAIL = re.compile(r"(?<![A-Z])(?:" + _CONSUMER_P2P_RAIL_WORDS + r")\b")
_PUSH_RAIL = re.compile(
    r"(?<![A-Z])(?:RTP|FEDNOW|REAL TIME (?:TRANSFER|PAYMENT)|INSTANT (?:PMT|PAYMENT|TRANSFER)|VISA DIRECT"
    r"|VISA MONEY TRANSFER|MC SEND|MONEY TRANSFER|PMNT RCVD|PAYMENT RECEIVED)\b"
)
#: §8.3: check deposits (Q3: counted, never verified).
_CHECK_DEPOSIT_FORM = re.compile(
    r"(?<![A-Z])MOBILE (?:CHECK |CHEQUE )?(?:DEPOSIT|DEP)\b|(?<![A-Z])MOBILE CHE(?:CK|QUE)\b|(?<![A-Z])MB DEP\b"
    r"|(?<![A-Z])BKOFAMERICA MOBILE\b"
    r"|(?<![A-Z])REMOTE (?:ONLINE )?(?:DEPOSIT|CAPTURE)\b|(?<![A-Z])DEPOSIT CAPTURE\b|(?<![A-Z])MERCHANT CAPTURE\b"
    r"|(?<![A-Z])DESKTOP (?:REMOTE )?DEPOSIT\b|(?<![A-Z])EDEPOSIT SCAN\b|(?<![A-Z])E ?CHEQUE DEPOSIT\b"
    r"|(?<![A-Z])(?:ATM )?CHE(?:CK|QUE)S? (?:DEPOSIT|DEP|RECEIVED)\b|(?<![A-Z])MAIL DEPOSIT\b"
    r"|^(?:\d{1,2} \d{1,2} ?)?REMOTE$|(?<![A-Z])IMAGED DEPOSIT\b"
    r"|(?<![A-Z])DEPOSITED (?:CHECK|ITEM)\b|(?<![A-Z])RDC\b|(?<![A-Z])SCAN(?:NED)? DEPOSIT\b|(?<![A-Z])LOCKBOX\b"
    r"|(?<![A-Z])LBX DEP\b"
)
#: §8.2, arm R: a retail cash load, printed '<ST> <town> <street> US<RETAILER> W<n>' at the row's end (Bluevine's
#: deposits at a retail cash network; inferred from the shape, no statement opened; the statements that carry it print
#: the bank's CASH DEPOSIT FEE debits beside the loads).
_RETAIL_CASH_LOAD = (
    r"(?<![A-Z])US ?(?:WALGREENS|CVS|7 ?ELEVEN|WAL ?MART|DOLLAR GENERAL|RITE ?AID|FAMILY DOLLAR|CIRCLE K) W ?\d+$"
)
#: §8.2, arm S: a branch deposit printed 'DEPOSIT <place, one to four words> <5-digit transit> <3-digit sequence>' as
#: the whole row (Scotiabank's), with no legal form on the row (a named depositor keeps its reading).
_BRANCH_DEPOSIT_TRANSIT = (
    r"^(?:\d{1,2} \d{1,2} )?DEPOSIT (?!.*\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LTEE|LIMITED|LLP"
    r"|PLLC|ULC|PLC)\b)(?:[A-Z]+ ){1,4}\d{5} \d{3}$"
)
#: §8.2: cash, branch and teller, and ATM deposits (Q2: counted, never verified), read only on a row that prints no
#: electronic-payment form and no person-to-person rail. And the retail cash load (arm R) and the branch deposit
#: printed with its transit (arm S), the two cash shapes the corpus check found the reader missed; each is its own
#: last alternative.
_CASH_BRANCH_ATM_FORM = re.compile(
    r"(?<![A-Z])CASH DEP(?:OSIT)?\b|(?<![A-Z])ATM CASH\b|(?<![A-Z])CPS DEVICE\b|(?<![A-Z])CURRENCY PROCESSING\b"
    r"|(?<![A-Z])SMART ?SAFE\b|(?<![A-Z])COIN\b|(?<![A-Z])CASH IN\b"
    r"|(?<![A-Z])COUNTER (?:CREDIT|DEPOSIT)\b|(?<![A-Z])TELLER\b|(?<![A-Z])IN BRANCH\b|(?<![A-Z])BRANCH\b"
    r"|(?<![A-Z])BRCH\b|(?<![A-Z])DEPOSIT AT BR\b"
    r"|(?<![A-Z])DEPOSIT THANK YOU\b|(?<![A-Z])MAIN OFFICE\b|(?<![A-Z])PRE ?ENCODED\b|(?<![A-Z])NIGHT (?:DEP|DROP)\b"
    r"|(?<![A-Z])BANKING CENTRE\b"
    # DEPOT MARCHAND (a card settlement, §7.1) and DEPOT DIRECT (a direct deposit) are electronic, never a branch.
    r"|^(?:\d{1,2} \d{1,2} ?)?GC\b.*(?<![A-Z])DEPOSIT\b|(?<![A-Z])G DEPOT\b|(?<![A-Z])DEPOT\b(?! MARCHAND\b| DIRECT\b)"
    r"|(?<![A-Z])DEPOSIT IBB\b|(?<![A-Z])VAULT DEP\w*|(?<![A-Z])STORE DEPOSIT\b"
    r"|(?<![A-Z])DEPOSIT MADE IN\b"
    r"|(?<![A-Z])ATM\b.*(?<![A-Z])DEP(?:OSIT)?\b|(?<![A-Z])DEP(?:OSIT)?\b.*(?<![A-Z])ATM\b|(?<![A-Z])ABM\b"
    "|" + _RETAIL_CASH_LOAD + "|" + _BRANCH_DEPOSIT_TRANSIT
)
#: §5.2: the ACH originator and entry fields (Bank of America's DES, Chase's ORIG CO NAME and CO ENTRY DESCR).
_ACH_ORIGINATOR_FIELD = re.compile(r"\b(?:DES|CO ENTRY DESCR|ORIG CO NAME)\b")


#: WIRE printed anywhere on the row, a reference glued on its left included ('123456W1234567WIRE
#: FROM ...', which _INCOMING_WIRE_LABEL, anchored at the row's start, never reads).
_WIRE_WORD = re.compile(r"(?<![A-Z])WIRE\b")
BANK_SETTLEMENT_ORIGINATOR = re.compile(
    r"(?<![A-Z])(?:MERCHANT\w*|MERCH SVCS|BANKCARD\w*|CARD (?:SERVICES|SVCS)|PAYMENTECH|PROCESSING|SETTLEMENT\w*)\b"
    r"|\b(?:MERCH|MRCH|BNKCD|BKCD|STLMT)\b"
)
#: A company form; a company whose name holds BANK is no bank ('LEFT BANK BAKERY LLC', 'BANK STREET PARTNERS LLC'),
#: unless the form is the bank's own, right after its bank word ('<X> BANK LTD', '<X> BANK CO LTD', '<X> BANK
#: PUBLIC CO LTD', 'BANK OF <place> LIMITED').
_BANK_COMPANY_FORM = re.compile(
    r"\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC|PARTNERS|PARTNERSHIP"
    r"|GMBH|AG|SA|BV|NV|PTY)\b"
)


#: The labels after which a relaying (correspondent) bank prints the ultimate originator ('B O <bank> ... ORG
#: <account> <customer> OGB <bank>'), and the fields the customer's name ends at: a wire field, the originating bank
#: (OGB) and the relay's charge and amount fields. Never the purpose's own label, ORIGINATOR TO BENEFICIARY or ORG
#: TO BNF (the guards _WIRE_ORIGINATOR_LABEL has).
_RELAY_ORIGINATOR_LABEL = re.compile(
    r"\b(?:ORG(?! TO BNF\b| TO BENEFICIARY\b)|B O|ORIGINATOR(?: NAME)?(?! TO BNF\b| TO BENEFICIARY\b)"
    r"|ORIG CUST(?:OMER)?|BY ORDER OF)\b ?"
)


#: A3: the incoming-wire layouts that print the sender right after their label, with
#: no originator label: BMO's label printed twice, then the sender's country code ('INCOMING WIRE PAYMENT INCOMING
#: WIRE PAYMENT CA <sender>'); a reference, then the sender ('INCOMING WIRE <reference> <sender> NOTPROVIDED'); TD
#: Bank's 'WIRE TRANSFER INCOMING <sender>'; Wilson & Muir's 'WIRE TRANSFER FROM <sender>'; Capital One's 'WIRE
#: TRANSFER DEPOSIT <sender> <reference> USD<...>'; Scotiabank's 'INCOMING WIRE TRANSFER <sender> WIRE PAYMENT'; and
#: SECU's 'DOMESTIC WIRE DEPOSIT WIRE IN <sender>'. Anchored at the row's start, so a sending bank after VIA or a
#: reference-only row ('DOMESTIC INCOMING WIRE <reference>') is never read as a sender. Falcon International Bank
#: prints an incoming wire as '<label> <amount> Falcon Internati Wires <sender>' (its own name cut to sixteen
#: characters and its wire field, then the sender, cut too): the bank's field is a label, never the sender.
_FALCON_WIRE_FIELD = r"(?:INTERNATIONAL IWT|INCOMING WIRE(?: TRF)?) FALCON INTERNATI WIRES"
#: The plural 'WIRE TRANSFERS <INCOMING|FROM|DEPOSIT|IN>' too, and 'WIRE TRANSFER[S] IN <sender>', whose sender was
#: never read (a reference alone after IN is still no sender). And the sender printed straight after R32's labels and
#: the plural CREDIT label: 'INBOUND WIRE|FEDWIRE [TRANSFER FROM] <sender>', 'INCOMING FEDWIRE [TRANSFER FROM]
#: <sender>', 'INCOMING WIRE TRANSFER FROM <sender>', 'INCOMING CHIPS <sender>' and 'WIRE TRANSFER[S] CREDIT <sender>'
#: (the longer form first, so Huntington's bare 'INCOMING FEDWIRE TRANSFER' reads only its label word and no sender).
#: The other labels with no FROM (FEDWIRE CREDIT, CHIPS CREDIT, WIRE IN, DOMESTIC WIRE, a bare INCOMING WIRE <name>,
#: U.S. Bank's WIRE CREDIT REF<n>) stay the recorded residual (§20).
_WIRE_SENDER_AFTER_LABEL = re.compile(
    r"^(?:INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT [A-Z]{2}|INCOMING WIRE(?= \d+ [A-Z])"
    r"|WIRE TRANSFERS? (?:INCOMING|FROM|DEPOSIT|IN|CREDIT)|INCOMING WIRE TRANSFER(?= .*\bWIRE PAYMENT$)"
    r"|(?:DOMESTIC )?WIRE DEPOSIT WIRE IN|" + _FALCON_WIRE_FIELD
    + r"|INBOUND (?:FED)?WIRE(?: TRANSFER FROM)?|INCOMING FEDWIRE(?: TRANSFER FROM)?|INCOMING WIRE TRANSFER FROM"
    r"|INCOMING CHIPS)\b ?"
)
#: A3: the sender printed after the label ends at a wire field, at NOTPROVIDED, or at Scotiabank's WIRE PAYMENT.
_WIRE_SENDER_AFTER_LABEL_END = re.compile(_WIRE_FIELD_END.pattern + r"|\b(?:NOTPROVIDED|WIRE PAYMENT)\b")


#: Chase's real-time layout prints the contra bank's label and routing number before the sender ('REAL TIME TRANSFER
#: RECD FROM ABA/CONTR BNK-<routing> FROM: <sender> REF ...'): never a sender.
_CONTRA_BANK_FIELD = re.compile(r"\bFROM ABA CONTR BNK\b(?: \d+\b)?")


#: §7.11: the account-type and product words a transfer prints after FROM about one of the holder's own accounts.
#: _INTERNAL_ACCOUNT_SOURCE's words and HOLDER_NOISE (BUSINESS, CHECKING, SAVINGS, ACCOUNT, OPERATING, MONEY
#: MARKET, TRUST, the generic words) are read too, so neither is repeated here.
_OWN_ACCOUNT_PRODUCT_WORDS = frozenset({
    "SAVS", "SVG", "SVGS", "CHKG", "CHKING", "MMDA", "OPER", "RESERVE", "RESERVES", "TAX", "TAXES", "PAYROLL",
    "PERSONAL", "BUS", "BUSN", "ACCTS", "LOC", "LINE", "HELOC", "SWEEP", "ESCROW", "INVESTMENT", "INVESTMENTS",
    "BROKERAGE", "IRA", "SUB",
    # The adjectives an own account prints before its product word, and a loan account.
    "PRIMARY", "SECONDARY", "MAIN", "JOINT", "HIGH", "YIELD", "SPENDING", "SHARE", "DRAFT", "LOAN",
})
_INTERNAL_ACCOUNT_SOURCE_WORDS = re.compile(rf"\b{_INTERNAL_ACCOUNT_SOURCE}\b")


#: Channel and payment words that never name a payee (D11).
_ENTITY_NOISE = {
    "ACH", "EFT", "DEBIT", "DIRECT", "DEB", "EXTERNAL", "WITHDRAWAL", "ELECTRONIC",
    "PREAUTHORIZED", "PREAUTH", "AUTOMATIC", "AUTO", "ORIG", "ORIGINATOR", "NAME",
    "DESCR", "DESCRIPTION", "ENTRY", "DETAIL", "PAYMENT", "PAYMENTS", "PAY", "PMT",
    "PYMT", "REPAYMENT", "REMITTANCE", "PAD", "BUSINESS", "ONLINE", "WEB", "CCD", "PPD",
    "LOAN", "MCA", "TO", "FROM", "FOR", "TFR", "XFER", "TRANSFER", "MISC",
    # The paid-to label a bank prints before the payee (Navy Federal "Paid To -").
    "PAID",
}
#: D11: a name is published only when one of these organisation cues survives. The last eight are the
#: registry-style company tokens (legal-form suffixes). CO is no cue (it is also Colorado's state code:
#: 'NAME, CITY, CO'); COMPANY stays one.
_ORGANISATION_CUES = {
    "LLC", "INC", "CORP", "FUNDING", "CAPITAL", "FINANCIAL", "FINANCE", "BANK",
    "CREDIT", "LENDING", "ADVANCE", "GROUP", "HOLDINGS", "SERVICES",
    "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
}
#: Labels that introduce the originator's name: the label goes, the name stays.
_ENTITY_NAME_LABELS = re.compile(r"\b(?:ORIG CO NAME|ORIGINATOR NAME|COMPANY NAME|CO NAME)\b")
#: D11: ACH field segments. Everything from the first one on is dropped, so a
#: name is never built from ID, INDN, IND NAME, CO ID, TRACE or similar fields.
_ACH_FIELD_SEGMENT = re.compile(
    r"\b(?:DES|DESC|DESCR|ORIG ID|CO ID|IND ID|IND NAME|INDN|IND|ID|TRACE|SEC|EED|TRN|"
    # Truist's receiver field label, Huntington's instruction field and the wire fields.
    r"CONF|REF|MEMO|CUST|TYPE|CUSTOMER ID|INSTR|SRF|RFB|IMAD)\b"
)
#: Bank template words printed before the payee: removed before the payee words start, so two recipients paid
#: through one template are never one payee (D11) and a template is never a name. Read at the start of the
#: normalized row. 'ACH CORP DEBIT' is Truist's; its name then passes _truist_name_is_published.
_PAYEE_TEMPLATE_PREFIX = re.compile(
    r"^(?:(?:PMNT|PAYMENT) SENT|CORPORATE ACH|DOMESTIC ASSIST WIRE|HIP CREDIT SENT(?: TO)?|RETAIL PURCHASE"
    r"|DBCRD PUR AP(?: AUT)?(?: [0-9]+)?(?: VISA DDA PUR(?: AP)?)?|ACH CORP (?:DEBIT|CREDIT))\b"
)
#: A receiver-name field with its value, up to the next ACH field, removed before the debt-relief table is read: the
#: account holder's own name never makes a row debt relief. The one tuple's name labels.
_RECEIVER_FIELD_VALUE = re.compile(rf"\b(?:{_RECEIVER_NAME_LABELS})\b" + _RECEIVER_VALUE_END)


#: D9: LOC wording. Also the first step-8 descriptor rule (Task 8).
_LINE_OF_CREDIT_PATTERNS = (
    re.compile(r"\bLOC\b"),
    re.compile(r"\bLINE OF CREDIT\b"),
)
_BNPL_CONSUMER_CREDIT = re.compile(
    r"\bRETURN\w*|\bWITHDRAW\w*|REFUND\w*|\bRFND\w*|\bREFND\w*|\bRFD\b|\bBALANCE\b|\bCASH ?BACK\b|\bREWARDS?\b"
    r"|\bAFFIRMCARD\b|\bCARD\b|\bPURCHASES?\b|\bTRUE ?ACCORD\b"
)
#: A payout entity's or a lease-to-own or patient financier's credit printing an advance, capital, interest, a dividend
#: or a rebate is no merchant payout. Q8: "Their consumer-side credits (refunds, loans to the holder) stay as today";
#: the MCA principle: an advance, interest, a dividend or a rebate is no money the business earns from its operations.
#: Never FUNDING, FUNDED, PAYOUT, PAYMENT, LEASE FUND or a bare ADV, which is a payment advice; never PROCEEDS, which a
#: settlement may print; LOAN is the strong rule's. Read by the true-revenue pass's claim (_customer_financier,
#: _claimed) and, for Cherry alone, by _is_payout_credit.
_PAYOUT_NON_SALE_CREDIT = re.compile(
    r"(?<![A-Z])(?:ADVANCES?|ADVNC|ADVN|ADVC|CASH ADV\w*|CAPITAL|CAPTL|INTEREST|DIVIDENDS?|REBATES?)\b"
)
#: §6.3: Snap's merchant funding as Wells Fargo prints it, 'SNAP LOAN FUNDING F<digits> <merchant>': the strong
#: non-revenue rule reads the row without it (_classify_credit_revenue), and the true-revenue pass reads a SNAP LOAN
#: FUNDING payer as Snap's payout only in this form (_customer_financier). A SNAP LOAN FUNDING with no merchant form is a
#: loan, as before.
_SNAP_MERCHANT_FUNDING = re.compile(r"(?<![A-Z])SNAP LOAN FUNDING(?= F\d)")
#: And the CHARGE (never CHARGE BACK, the chargeback) and CHRG wordings of the fee.
_DEPOSIT_UNDO_FEE = re.compile(r"\b(?:FEES?|FRAIS|SVC|CHG|CHRG|SERVICE CHARGE)\b|\bCHARGES?\b(?! ?BACK)")


#: §7.5: a card purchase's leading card-form words and the MMDD date after them. D11 stops at that date, so
#: 'CHECKCARD 0302 NORTHWIND GRILL' reads CHECKCARD alone; pass 6 reads the debit after them.
_CARD_FORM_DEBIT_PREFIX = re.compile(
    r"^(?:RECURRING )?(?:CHECKCARD|(?:MOBILE |CARD )?PURCHASE(?: AUTHORIZED ON)?) (?:\d{4}|\d{2} \d{2}) (?=\S)"
)
#: The financing veto every 5.3 D6 skip reads. Funders ARE paid by card, Zelle, Interac, bill pay and wire, so no skip
#: fires on a row that names financing. The roots have no left word boundary, so a run-together or cut name hits
#: (KOVOCREDIT, CONSTRULOANS, BYZFUNDER, FUNDIN, CAPITA, FINANC, CLICKLEASE), and so does a collector of MCA debt
#: (RECOVERY, RECEIVABLES, COLLECTIONS). The card verifier's roots: SETTLE (an unregistered debt-settlement payee
#: stays reviewed; the registry alone names it debt relief), CRED before IT, ORA, IBLY or a word end (CREDIBLY,
#: CREDORA, a cut CRED; never INCREDIBLE) and ACCEPT (ACCEPTANCE). A skip's own matched words are removed before the
#: veto reads the row (_skips), so A4's 'BUS ONLINE ACH SETTLEMENT' template still skips. The short abbreviations are
#: whole words. Known over-reach, in the safe direction (the row stays in review): CALENDAR, RELEASE, REFUNDABLE,
#: FUNDRAISER, a processor's SETTLEMENT wording, ACCEPTED.
_FINANCING_ROOT_PATTERN = re.compile(
    r"(?:FUND|CAPITA|CAPTL|CRED(?=IT|ORA|IBLY|\b)|LOAN|LEND|FINANC|ADVANC|MERCH|RECOVER|RECEIVAB|COLLECT"
    r"|SERVICING|SERVICER|FACTOR|LEASE|LEASING|EQUIP|MORTG|ACCEPT|REMIT|SETTLE)"
    r"|\b(?:CAP|FIN|FINL|FNCL|ADV|MTG|MCA|RTR|SPV|DLY|DAILY|WKLY|WEEKLY)\b"
)
#: D11 and 5.3: the legal-form suffixes. A legal form names an organisation only after the name's first word.
_LEGAL_FORM_SUFFIXES = frozenset({
    "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
})


#: Bank channel vocabulary. A D6 group whose payee words are all channel words names no payee: a card, cash, cheque
#: or bill-pay posting printed without its merchant or recipient. OTHER, BANK and the bare withdrawal abbreviations
#: (WD, WDL, WDRL) are left out on purpose: 'Other Debit', 'Bank Debit' and 'Preauthorized Wd' rows stay in review,
#: because their text does not tell what they pay.
_CHANNEL_VOCABULARY = frozenset({
    # card postings
    "CARD", "CARDS", "CRD", "DBT", "DBCRD", "PIN", "PURCH", "PURCHASE", "PUR", "POS", "DDA", "VISA", "MASTERCARD",
    "MC", "TRANSACTION", "SPEND", "RETAIL", "ACHAT", "AUTHORIZED", "AUTHORISED", "ON", "ENDING",
    # cash
    "ATM", "ABM", "CASH", "TELLER", "COUNTER", "BRANCH", "STORE", "MADE", "IN", "NETWORK", "WITHDRWL", "RETRAIT",
    # cheques and items
    "CHK", "CK", "CHQ", "DRAFT", "SHARE", "ITEM",
    # bill pay, push and banking channels
    "BILL", "BILLS", "BILLPAY", "RECURRING", "RECUR", "AUTOPAY", "MISCELLANEOUS", "INTERNET", "MOBILE", "PHONE",
    "TELEPHONE", "SENT", "PMNT", "VIREMENT", "ENVOYE", "PAID",
})
#: Named consumer savings and investing originators: a closed list of verified non-funder ACH names, never a
#: category by resemblance. A name joins only after collision_check.py (registry tables, the whole ledger,
#: all_keys.json) prints no hit. Bare VANGUARD, INVEST, SAVINGS, FIDELITY and MONEYLINE stay out.
_SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS = (
    re.compile(r"\bSTASH (?:CAPITAL|INVEST(?:MENTS?)?)\b"),
    re.compile(r"\bALINEA\b"),
    re.compile(r"\bFID BKG SVC\b"),                                   # Fidelity Brokerage Services MoneyLine
    re.compile(r"\bALBERT (?:SAVINGS )?(?:DES )?EDI PYMNTS\b"),         # Albert's money movement, not its advances
    re.compile(r"\b(?:ACORNS|ROBINHOOD|COINBASE|BETTERMENT|WEALTHFRONT)\b"),
)
