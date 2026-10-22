"""The pass vocabulary: hold labels, financing roots, insurer and claim words, methods."""
from __future__ import annotations

import re

from analysis.classification_registry import (
    EARNED_WAGE_ACCESS_PAYERS,
    LENDING_BANK_CREDIT_PAYERS,
    P2P_SENDING_BANK_NAMES,
)
from analysis.description_text import RECEIVER_NAME_LABELS
from analysis.flag_groups import FINANCING_STATES


#: §8.1: the posting labels removed before a hold reads a row: §7.5's credit posting labels, the branch, card and batch
#: CREDIT labels, and the channel phrases. The plural FUNDS TRANSFERS too, transfer wording since B8 (a bank's channel
#: phrase, never a funder's FUNDS).
_HOLD_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE|INSTANT|REAL TIME|COUNTER|POS|ATM|TELLER|BRANCH|CARD|BATCH|MERCHANT|VISA|CHECKCARD|PURCHASE)"
    r"\s+CREDIT\b|^CREDIT\b"
    r"|\bCREDIT FROM\b|\bFUNDS (?:TRANSFERS?|AVAILABLE)\b|\bINSTANT FUNDS\b"
)
#: §8.1, T4: the credit-side financing roots. A whole-word CREDIT counts only inside a payer name, next to another name
#: word; glued, it always counts. The roots have no left boundary; of the whole words, those of four letters or more take
#: (?<![A-Z]) (the veto convention). A special-purpose entity's SPE (a funder's financing vehicle, as SPV is), the whole
#: word. FIN glued to USA is no root: with no left boundary it read any run-together name ending in FIN + USA (a muffin or
#: griffin brand), and Forward's FORWARDFINUSA is its ledger alias.
_FINANCING_ROOT = re.compile(
    r"(?:(?<!RE)FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|LEASING|PORTFOL)"
    r"|CRED(?=ORA|IBLY)|[A-Z]CREDIT|CREDIT(?!S\b)[A-Z]"
    r"|\b(?:CAP|FIN|ADV|MTG|MCA|RTR|SPE|SPV)\b|(?<![A-Z])(?:CAPI|FINA|FINAN|FINL|FNCL|LEASE)\b"
)
_WHOLE_WORD_ROOT = re.compile(r"(?:CAP|FIN|ADV|MTG|MCA|RTR|SPE|SPV|CAPI|FINA|FINAN|FINL|FNCL|LEASE|FUND)")
#: §8.7: the dealer-funding words.
DEALER_FUNDING_WORDS = re.compile(
    r"(?<![A-Z])(?:VHCL PURCH\w*|VEHICLE PURCHASE\b|DEAL ?FUND\w*|FUNDLOAN\b|DEALER (?:FUND\w*|FND|PMT|PAY\w*)\b"
    r"|DLR PMT\b|AUTODLRPMT\b|CONTRACT FUND\w*|VADMIN FEE\b)"
)
#: §8.7: Q7 never fires on a loan, proceeds, advance or refund word. The owner's veto convention: a spelling of four
#: letters or more takes (?<![A-Z]), one of three letters or fewer keeps \b. The refund words also read inflected
#: and glued, as G15 reads them (a glued PREFUND or REFUNDS never verifies).
_DEALER_FUNDING_VETO = re.compile(
    r"(?<![A-Z])(?:LOANS?|PROCEEDS|ADVANCES?|CASH ADV\w*|RETURN\w*|REVERSAL\w*|RVSL|CHARGEBACK\w*|CHBK)\b"
    r"|\b(?:ADV|MCA|RFD|RTN)\b|[A-Z]*REFUND\w*|(?<![A-Z])(?:RFND|REFND)\w*"
)
#: §8.7: the credit-union arm's payer region and entry field. And a credit union's glued acronym, one to three letters
#: before CU or FCU as one word (BECU, SECU, PSECU, GECU, DCU), read with the arm's VHCL PURCH entry and its two-credit
#: count as every credit union is.
_CREDIT_UNION_PAYER = re.compile(r"\bCU\b|\bCREDIT UNION\b|\bFCU\b|\bCU DIRECT\b|\bCUDL\b|\b[A-Z]{1,3}F?CU\b")
_VEHICLE_PURCHASE_ENTRY = re.compile(r"\bVHCL PURCH(?:ASE)?\b")
#: §8.1: an insurer's name on the payer region.
_INSURER_NAME = re.compile(
    r"(?<![A-Z])(?:INSUR\w*|ASSURANCE\b|MUTUAL\b|CASUALTY\b|INDEMNITY\b|UNDERWRIT\w*)"
)
_CLAIM_WORD = re.compile(r"(?<![A-Z])CLAIMS?\b")
#: §8.1 insurer_named_payer: the insurer spellings a payer region prints beside _INSURER_NAME's spelled-out words,
#: which _INSURER_NAME (pinned by the contract's docs test) leaves unread: the INS abbreviation, the cut forms ASSUR,
#: MUTUA, CASUALT and INDEMN, the French ASSURANCES, ASSURANT and ASSUREUR(S), P AND C (or P & C) at a name's end or
#: before INS, CO, COMPANY or CORP, a loss payment's LOSS PMT, PAYMENT, PYMT or DRAFT, and SUBRO (a subrogation
#: recovery). Never ASSURED or ASSURE ('ASSURED STAFFING LLC'), never P AND C FOODS; CLM, CLMS and CLMEFT are not read
#: (every corpus CLM row is a health plan paying a provider). SUBRO and its cut forms only (SUBROG, SUBROGATION), never
#: the given name SUBROTO; P AND C before INS, INSU or INSUR... only, never an installer's or an inspector's word. And
#: a Texas county mutual's 16-character cut, COUNTY MUT ('PROG COUNTY MUT'; MUTUA and MUTUAL already read), a private
#: carrier never read as a county (the classifier's _PUBLIC_PAYER_NAME veto).
_INSURER_SPELLINGS = re.compile(
    r"(?<![A-Z])(?:ASSURANCES|ASSURANT|ASSUREURS?|ASSUR|MUTUA|CASUALT\w*|INDEMN\w*|SUBRO(?:G\w*)?)(?![A-Z])"
    r"|(?<![A-Z])INS(?![A-Z])"
    r"|(?<![A-Z])P (?:AND|&) C(?:(?! ?[A-Z])| (?:INS(?:UR\w*|U)?|CO|COMPANY|CORP)(?![A-Z]))"
    r"|(?<![A-Z])LOSS (?:PMT|PAYMENT|PYMT|DRAFT)(?![A-Z])"
    r"|(?<![A-Z])COUNTY MUT(?![A-Z])"
)
#: The classifier's _NO_LEGAL_FORM_LATER (copied: the classifier imports this module): no legal-form word
#: later on the row.
_NO_LEGAL_FORM_LATER = (
    r"(?!.*\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LTEE|LIMITED|LLP|LLLP|PLLC|ULC|PLC|GMBH)\b)"
)
#: The classifier's _RETURN_REFUND_R2_B08_ARMS, copied verbatim (the classifier imports this module): a Quebec returned
#: item, CIBC's CONTRE-PASSATION, RBC's refused item SANS PROVISION, the check-word NOT PAID at the row's head (never in
#: a memo, a wire's remittance field or an ACH entry description), an e-Transfer reclaim with the rail word right before
#: RECLAIM and a reference after it or TD's RECLAIM E-TFR, and the fee waiver with no legal-form word later. A test keeps
#: the copies in step. A lost accent inside CHEQUE (CH QUE) and after RETOURN is tolerated, as after REFUS.
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
#: From the row's start, text holding no incoming e-Transfer wording (RECEIVED, FROM, AUTODEPOSIT, the French
#: RECEPT and DEPOT), read before the outgoing send and sent labels of _POSSIBLE_RETURN: a send label after one of
#: them is a memo's words on an incoming transfer.
_NO_INCOMING_WORDING_BEFORE = r"^(?:(?!(?<![A-Z])(?:RECEIVED|FROM|AUTO ?DEPOSIT|RECEPT|DEPOT)(?![A-Z])).)*?"
_POSSIBLE_RETURN = re.compile(
    r"(?<![A-Z])RETURN(?:ED|S)?\b|\bADJ\b|(?<![A-Z])ADJ(?:USTMENT|USTED)\b|(?<![A-Z])DISPUTE[DS]?\b"
    r"|(?<![A-Z])CREDIT MEMO\b|(?<![A-Z])OVERPA\w*"
    # §7.8: an auction's guarantee or arbitration refund of a vehicle the dealer bought.
    r"|(?<![A-Z])DEALSHIELD\b|(?<![A-Z])ARB(?:ITRATION)? CREDIT\b"
    # A backstop for step 3's 5.6 return, correction and refund spellings (the classifier's
    # _RETURN_REFUND_CREDIT_PATTERNS, read on the hold text, a correction or a reversed purchase printed first after
    # the posting labels are removed), so such a row that reaches the pass is held, never counted. REMBOURSEMENT is
    # not read (a provider's REMBOURSEMENT left step 3 by §7.11's carve-out), nor the card labels (their own arm). NOT
    # PAID, UNAUTHORIZED, RECLAIM, the leading REV form and RETOUR narrowed as the classifier's (never a company's
    # name or a memo; _NO_LEGAL_FORM_LATER is the classifier's, copied).
    r"|(?<![A-Z])ITEMS? RET(?:URNED)?\b(?! FEES?\b)|(?<![A-Z])RET DEP ITEMS?\b"
    r"|(?<![A-Z])(?:ITEMS?|RET|RETN|RTN|RETURN(?:ED)?) NOT PAID\b|^\s*(?:\d{1,2} \d{1,2} )?NOT PAID(?: \S*\d\S*)*\s*$"
    r"|(?<![A-Z])(?:ERROR|TRANSACTION|DEPOSIT) CORRECTION\b|^\s*(?:\d{1,2} \d{1,2} )?CORRECTION(?![A-Z])"
    r"|(?<![A-Z])PURCHASE RET\b|(?<![A-Z])(?:PROVISIONAL|TEMPORARY|CONDITIONAL) CR\b"
    r"|(?<![A-Z])UNAUTHORI[SZ]ED\b" + _NO_LEGAL_FORM_LATER
    + r"|(?<![A-Z])RECLAIM(?=\d|\s*$)"
    r"|^\s*(?:\d{1,2} \d{1,2} )?REV (?:MOBILE|POS|DEBIT|PURCHASE|ACH|CARD)\b(?:(?= (?:MOBILE|POS|DEBIT|PURCHASE|ACH"
    r"|CARD|CREDIT|PMT|PAYMENT|TRANSACTION|TXN|WITHDRAWAL)\b| ?\d|\s*$)|" + _NO_LEGAL_FORM_LATER + ")"
    r"|(?<![A-Z])(?:RENV|RENVERSEMENT)\b"
    r"|(?<![A-Z])RETOUR\b(?:(?= ?\d| MDSE\b| MARCHANDISE\b|\s*$)|" + _NO_LEGAL_FORM_LATER + ")"
    r"|(?<![A-Z])COURTESY REF(?:UND)?\b"
    # The classifier's new step-3 arms (the fee waiver's guarded arm replaces the bare one).
    + "".join("|" + arm for arm in _RETURN_REFUND_R2_B08_ARMS)
    # The holder's own sent e-Transfer coming back is no customer revenue, whichever leg the parser signed: a credit
    # printing TD Canada Trust's send (SEND E-TFR), a sent transfer (EQ Bank's 'Interac e-Transfer sent to', any
    # bank's; never 'SENT BY', an incoming wording), TD's French send, its reversal or its redeposit ('Envoi-VFC',
    # 'Envoi - FRAIS - VFC', 'Contr. - VFC', 'Redepot - VFC'), or a French fee adjustment (no legal-form word later on
    # the row). Pass 7 only: never a step-3 or pass-4 marker. The send and sent labels only with no incoming wording
    # before them on the row (_NO_INCOMING_WORDING_BEFORE: an incoming e-Transfer whose memo prints the send words
    # stays a counted push), the send label with no legal-form word later, and none of the three inside an ACH
    # originator's name field (after NAME: 'ORIG CO NAME:SEND ETRANSFER LLC' is a payer's name, never the bank's
    # label).
    + r"|" + _NO_INCOMING_WORDING_BEFORE + r"(?<![A-Z])(?<!NAME )SEND E ?(?:TFR|TRANSFER)\b" + _NO_LEGAL_FORM_LATER
    + r"|" + _NO_INCOMING_WORDING_BEFORE + r"(?<![A-Z])(?<!NAME )(?:INTERAC )?E ?(?:TRANSFER|TFR) SENT\b(?! BY\b)"
    r"|(?<![A-Z])(?:ENVOI|CONTR|REDEPOT) (?:FRAIS )?VFC\b"
    r"|(?<![A-Z])(?<!NAME )AJUST(?:EMENT)? (?:DE )?FRAIS\b" + _NO_LEGAL_FORM_LATER
)
#: §8.1, §7.11: a card credit's posting labels (a refund to the card unless a form or the registry verified it). And
#: the card-shaped refund labels step 3 adds (Citibank's cut DEBIT CARD CREDI, Bank of America's credit-side
#: CHECKCARD <mmdd>, a point-of-sale deposit before its merchant's name, as step 3 reads it; a bare one names no
#: merchant and keeps Q2's counted reading), whichever a push word released.
_CARD_CREDIT_LABEL = re.compile(
    r"(?<![A-Z])(?:DEBIT CARD CREDIT?|POS CREDIT|VISA CREDIT|CHECKCARD CREDIT|PURCHASE CREDIT)\b"
    r"|^(?:\d{1,2} \d{1,2} )?CHECKCARD \d{4}\b|(?<![A-Z])POINT OF SALE DEPOSIT [A-Z]"
)
#: §7.11, §6.3, §20: the method of a card credit released as its merchant processor's instant payout
#: (_processor_card_payouts), the card labels it reads, and each processor's names as whole words
#: (CARD_PAYOUT_PROCESSOR_NAMES).
PROCESSOR_CARD_PAYOUT_METHOD = "processor_card_payout"
#: §8.1 (Q8): pay wording, read on the row before its receiver fields.
_PAY_WORDS = re.compile(
    r"(?<![A-Z])(?:PAYROLL\w*|PAYRLL\b|PAYROL\b|PAYRL\b|SALARY\b|SALARIES\b|REG SAL\b|WAGES?\b|NET ?PAY\b"
    r"|BONUS(?:ES)?\b|PAY PAY\b|PAIE\b|SALAIRES?\b|PAYCHECKS?\b|PAYCHK\b|PR PAY\w*|EMPLOYEE PAY\w*|EMP PAY\b"
    r"|EXP(?:ENSE)? REIMB\w*)"
)
#: §8.1, §8.8 (Q8): the direct-deposit words, DIR DEP, DIRDEP and DIRECT DEP anywhere and the whole phrase DIRECT
#: DEPOSIT as an entry description. A direct deposit is a payment channel, not a purpose: a company settles with a
#: business by direct deposit as it pays an employee. They are pay wording only with a sign the credit is a person's
#: pay (_direct_deposit_pay): another pay word or a payroll provider (_pay_wording reads those anyway), a person named
#: in the receiver field or after the deposit's references, a consumer (PPD or WEB) entry, or an account that does not
#: read as a business's (_business_shape). Q7's refusal still reads them alone (_q7_refused_by_a_hold: a listed
#: lender's dealer funding never verifies beside pay wording).
_DIRECT_DEPOSIT_WORDS = re.compile(
    r"(?<![A-Z])(?:DIR ?DEP\b|DIRDEP\b|DIRECT DEP\b(?!OSIT)|(?:DES|CO ENTRY DESCR) DIRECT DEPOSIT\b)"
)
_ENTRY_COMPANY_FORM = re.compile(
    r"\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC)\b"
)
#: §8.1 non_sale_purpose (the precedent of §7.11's street guard): a word followed by a street suffix is a street's name
#: in an address ('<n> GRANT AVE', an ATM's or a branch's location), never a purpose.
_STREET_NAME = re.compile(
    r"(?<![A-Z])[A-Z]+(?= (?:AVE|AVENUE|ST|STREET|RD|ROAD|BLVD|BOULEVARD|DR|DRIVE|LN|LANE|WAY|CT|PL|HWY|PKWY)\b)"
)
#: §8.1 non_sale_purpose (§7.11's street guard as the precedent): the non-sale reading's street name, read only after a
#: street number: the word right before a street suffix when a number token (digits, a letter after them: '12B') stands
#: right before it or one word before it ('<n> GRANT AVE', '<n> N GRANT ST'). The number is kept. A word before a
#: Stripe-style 'ST-<id>' trace or before a suffix with no number ('<NAME> EQUITY DR <zip>') is no street.
#: _STREET_NAME, which needs no number, still reads a deposit's location (_deposit_location_reading) and a
#: payer-less deposit's non-sale reading (_non_sale_reading). The suffixes are _STREET_NAME's (a test keeps
#: them in step).
_STREET_SUFFIXES = "AVE|AVENUE|ST|STREET|RD|ROAD|BLVD|BOULEVARD|DR|DRIVE|LN|LANE|WAY|CT|PL|HWY|PKWY"
#: §8.1 non_sale_purpose: DISBURS... is the payer's own account ('DISBURSEMENT ACCOUNT', an importer's paying
#: account), or an ordinary company's recurring payout entry ('PSP <phone> DISBURSMNT', a processor's payouts), no
#: non-sale purpose. It stays one beside a loan, escrow, title or proceeds word, on a one-off credit, and on a row
#: whose payer reads as a lender, an insurer, a title or escrow firm, a bank, a lawyer or a government
#: (_disbursing_payer).
_DISBURSEMENT_ACCOUNT = re.compile(r"(?<![A-Z])DISBURS\w* (?:ACCOUNT|ACCT|ACCNT)\b")
_DISBURSEMENT_WORD = re.compile(r"(?<![A-Z])DISBURS\w*")
_DISBURSEMENT_KEEP = re.compile(
    r"(?<![A-Z])(?:LOANS?|ESCROW|TITLE|PROCEEDS) DISBURS\w*|(?<![A-Z])DISBURS\w* (?:LOANS?|ESCROW|TITLE|PROCEEDS)\b"
)
#: §8.1, §7.5's investment words BROKERAGE, SECURITIES and WEALT join the owner money group (the standing rule: owner
#: money never becomes revenue), except on a row that prints §7.5's accounts-payable or vendor-payment wording
#: (_accounts_payable_wording; S4.2 fix measurement): a wealth, brokerage or securities firm paying a vendor from its
#: payables. Such a row is counted and flagged, never verified: §7.5's remittance veto reads the same words, and Q5
#: and Q6 refuse them as proof (CreditFacts.refused_word).
_INVESTMENT_PURPOSE = re.compile(r"(?<![A-Z])(?:BROKERAGE\w*|SECURITIES\b|WEALT\w*)")
#: §8.6 Q6c: a premium-coded entry (PREM, PREMIUM, and the Chase layout's glued PREMSEC), a commission or a
#: premium refund the text cannot tell apart, never a claim payment for the provider's services; and the insurer's
#: abbreviation a payer region prints (_INSURER_NAME reads the spelled-out words). A commission word beside it
#: keeps the entry's reading, and the public health programs (the government's own payers and Medicare's
#: administrative contractors) are never read.
_PREMIUM_CODED = re.compile(r"(?<![A-Z])(?:PREM|PREMIUMS?)(?:SEC)?\b")
#: §8.5: a sender that names a bank, a title or an escrow firm never verifies by repetition. BANKING and the
#: non-English bank words BANCA, BANQUE, BANCAIRE and SPARKASSE too, beside BANCO.
_BANK_OR_TITLE_SENDER = re.compile(
    r"\b(?:BANK|BANKING|BANCO|BANCA|BANQUE|BANCAIRE|SPARKASSE|BANCORP|N A|TRUST COMPANY|CREDIT UNION|FCU|SAVINGS"
    r"|TITLE|ESCROW|CLOSING|SETTLEMENT)\b"
)


#: §8.6 method names.
_Q6_METHODS = ("named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer")
#: The registry-family methods: a platform, processor or payout the operating registry named (§8.9).
_REGISTRY_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "wholesale_auction_payout_form",
})
#: §8.10: the lender and financing debit states payer_debited_as_lender reads.
LENDER_DEBIT_STATES = frozenset({"confirmed_lender", "potential_lender"}) | FINANCING_STATES
#: §8.1, T4 (Q6 "lenders never count"): a bank that lends to small businesses on its own account or as a fintech's
#: lender of record (the registry's LENDING_BANK_CREDIT_PAYERS) named as the payer: held as financing_named_payer
#: (lending_bank_payer).
_LENDING_BANK_PAYER = re.compile(LENDING_BANK_CREDIT_PAYERS)
#: §8.1, Q8: an earned-wage access provider's push (the registry's EARNED_WAGE_ACCESS_PAYERS) is a worker's wages
#: from another company: pay wording (_pay_wording), held as payroll_or_salary.
_EARNED_WAGE_ACCESS = re.compile(EARNED_WAGE_ACCESS_PAYERS)
#: §8.1, §8.10: the reason of a builder's progress draw, counted and flagged, never verified
#: (construction_progress_draw).
CONSTRUCTION_PROGRESS_DRAW_REASON = "construction_progress_draw"
#: §5.3: the reasons of a financier's payout and of its one-off lump sum.
CUSTOMER_FINANCING_PAYOUT = "customer_financing_payout"
#: §5.3, §8.7: the reason, and the revenue method, of a lender paying the business for its services (a repair, a
#: recovery, a commission): counted and flagged, never verified. This batch gives it to a listed auto lender's
#: payables-only credit on a statement with no dealer evidence (_lender_service_never_verified).
LENDER_PAID_FOR_SERVICES = "lender_paid_for_services"
_DEALER_HOLDER_VETO = re.compile(r"(?<![A-Z])(?:RECOVER\w*|REPO|REPOS|REPOSSESS\w*|TOWING|TOW|COLLATERAL)\b")
#: §8.1, §8.10: the method, and the non_revenue reason code, of a non-dealer's asset-sale proceeds.
ASSET_SALE_METHOD = "asset_sale_proceeds"
#: Q11 (b): the platform whose INSURANCE is its own name (IAA), which an insurer-name hold never keeps from Q11.
_IAA = "Insurance Auto Auctions (IAA)"
#: §8.2: the field labels, originator-name labels, SEC codes and reference labels a transfer prints (the
#: classifier's _ACH_FIELD_SEGMENT, _ENTITY_NAME_LABELS and _GLUED_SEC_CODE vocabulary). None names its
#: counterparty.
_TRANSFER_FIELD_LABEL_WORDS = frozenset({
    "DES", "DESC", "DESCR", "ORIG", "ORIGINATOR", "CO", "NAME", "COMPANY", "ENTRY", "DATE", "ID", "IND", "INDN",
    "TRACE", "SEC", "EED", "TRN", "CONF", "CONFIRMATION", "REF", "REFERENCE", "MEMO", "CUST", "TYPE", "INSTR", "SRF",
    "RFB", "IMAD", "OMAD", "SEQ", "NO", "NUMBER", "NBR", "NUM", "TRANSACTION",
    "CCD", "CTX", "PPD", "WEB", "IAT", "TEL", "POP", "BOC", "ARC", "RCK", "CIE", "COR",
})
#: Q4, §5.2: phrases removed before the sender is read: a sending bank's name (the registry's P2P_SENDING_BANK_NAMES,
#: 'ZELLE CREDIT BANK OF AMERICA') and Zelle's PAY ID label.
_P2P_LAYOUT_PHRASES = re.compile(
    r"(?<![A-Z])(?:" + "|".join(re.escape(name) for name in sorted(P2P_SENDING_BANK_NAMES, key=len, reverse=True))
    + r"|PAY ID)\b"
)
#: Q4, §5.2: the US state codes a wallet prints as a trailing tail ('VENMO <sender> VISA DIRECT NY'), removed
#: from the sender's end (_without_state_tail).
_US_STATE_TAIL = frozenset("""
AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC
SD TN TX UT VT VA WA WV WI WY DC PR US CAUS
""".split())
#: Q4: a legal form or an article alone names nobody ('RTP CREDIT 1ABC INC SAN FRANCISCO CA', whose name the
#: reference reading drops).
_NOT_A_NAME_ALONE = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "COMPANY", "CO", "LTD", "LIMITED", "LP", "LLP", "PLLC", "ULC",
    "PLC", "THE", "OF", "AND",
})
#: §8.4, §8.2 (S4.2 follow-up 2, the owner's delegation): in pass 7 VIREMENT is a person-to-person rail only in its
#: Interac forms (Interac prints VIREMENT INTERAC, or the e-transfer and autodeposit words). Printed without one
#: ('VIREMENT EN LIGNE', 'VIREMENT ENTRE COMPTES', 'VIREMENT DE COMPTE', 'VIREMENT DE FONDS', a bare VIREMENT) it is
#: a French transfer, typically between the holder's own accounts: transfer wording (_p2p_rail, _transfer_wording).
#: The 5.5 channel gate (the classifier's _CONSUMER_P2P_RAIL) is unchanged.
_VIREMENT = re.compile(r"(?<![A-Z])VIREMENT\b")
#: §8.2, §8.4: Interac's French name, "virement par courriel", singular or plural. Banque Royale's autodeposit prints
#: 'DEPOT AUTO VIREMENTS PAR COURRIEL <sender> <reference>', which the classifier's VIREMENT\b never reads (the
#: plural): pass 7 reads it as the e-Transfer rail (_p2p_rail, _p2p_sender_rail, _E_TRANSFER_RAIL), before the cash
#: or branch DEPOT. DEPOT AUTO(MATIQUE) alone is no form (beside VIREMENT it can be the holder's own scheduled
#: transfer).
_INTERAC_COURRIEL = re.compile(r"(?<![A-Z])VIREMENTS? PAR COURRIEL\b")
#: §8.2, §8.5 (A3, the precision sample of the largest counted rows): a wire's channel and layout words, never a
#: transfer's counterparty ('INCOMING FEDWIRE TRANSFER' names nobody). Some are generic words already; the set names
#: them all, so the rule reads in one place.
_WIRE_LAYOUT_WORDS = frozenset({
    "INCOMING", "INBOUND", "INBD", "FEDWIRE", "FED", "WIRE", "WIRES", "WT", "IWT", "TRANSFER", "CREDIT", "CHIPS",
    "SWIFT", "BOOK", "DOMESTIC", "INTL", "INTERNATIONAL",
})
#: §8.1: the holder's own currency conversion: foreign-exchange and currency-conversion wording, English and
#: French. It never names a counterparty (_without_currency_conversion); a credit that prints it and names no payer
#: besides it is the holder's own money converted from one currency to another (_currency_conversion). The corpus
#: prints ONLINE BANKING FOREIGN EXCHANGE; the other spellings are the banks' common forms, no corpus row yet.
_CURRENCY_CONVERSION = re.compile(
    r"(?<![A-Z])(?:FOREIGN (?:EXCHANGE|EXCH|CURRENCY (?:EXCHANGE|CONVERSION))|FX (?:CONVERSION|CONV|EXCHANGE|EXCH|TRADE"
    r"|DEAL|SPOT|CONTRACT)|CURRENCY (?:EXCHANGE|EXCH|CONVERSION|CONV)|(?:CONVERSION|CHANGE|ACHAT|VENTE) DE DEVISES"
    r"|CONV(?:ERSION)? DEVISES?)\b"
)
#: §8.1: a title firm named on the payer region, whose payment is property-closing proceeds (an asset sale), never the
#: business's operating revenue: the whole word TITLE beside a title-firm word or a legal form (either order, AND
#: between them allowed), or a national title insurer. TITLEIST and TITLE BOXING CLUB are no title firm. And a
#: settlement or closing agent named without the word TITLE ('<NAME> SETTLEMENT SERVICES', '<NAME> CLOSING SERVICES'); a
#: bare '<NAME> SETTLEMENT' (a carrier's contractor settlement) is none. Never a processor's, a card's, a clearing
#: house's, a carrier's or a freight, fuel, trucking, logistics or transport firm's settlement services (its operating
#: settlement, §8.6), a claims firm's or a debt settler's ('<NAME> CARD SETTLEMENT SERVICES', '<NAME> FREIGHT SETTLEMENT
#: SERVICES LLC').
_TITLE_FIRM = re.compile(
    r"\bTITLE (?:AND )?(?:AGENCY|AGENCIES|AGCY|CO|COMPANY|COMPANIES|CORP|CORPORATION|INC|LLC|LTD|TRUST|INS|INSURANCE"
    r"|GUARANTY|GUARANTEE|GTY|SERVICES|SERVICE|SVCS|ESCROW|CLOSING|CLOSINGS|SETTLEMENT|SETTLEMENTS|PARTNERS|GROUP)\b"
    r"|\b(?:AGENCY|TRUST|INSURANCE|GUARANTY|SERVICES|ESCROW|CLOSING|CLOSINGS|SETTLEMENT|ABSTRACT)(?: AND)? TITLE\b"
    r"|\b(?:CHICAGO|FIRST AMERICAN|FIDELITY NATIONAL|OLD REPUBLIC|STEWART|TICOR|COMMONWEALTH LAND|LAWYERS|WESTCOR"
    r"|WESTCOR LAND|NORTH AMERICAN|ATTORNEYS|WFG NATIONAL|DOMA) TITLE\b(?! BOXING\b| CLUB\b)"
    r"|\b(?!(?:CARD|MERCHANT|PAYMENTS?|BANKCARD|CLEARING|TRANSACTION|ACH|FREIGHT|CARRIER|FUEL|CLAIMS?|TRUCKING"
    r"|LOGISTICS|TRANSPORT\w*|DEBT)\b)[A-Z]+ SETTLEMENT SERVICES?\b|\b[A-Z]+ CLOSING SERVICES?\b"
)
#: §8.1: a title firm also pays the holder's own fee at closing: a commission, an origination or broker fee, an
#: invoice, consulting or services rendered, cited in the payment's purpose (_title_purpose_text: a wire's OBI, RMR,
#: PMT DET, RFB or URI purpose, an ACH entry, a transfer's memo). Such a credit is not held by the title hold and takes
#: its normal reading.
_TITLE_FEE_WORDING = re.compile(
    r"(?<![A-Z])(?:COMMISSIONS?|COMM|ORIGINATION|ORIG FEE|BROKER\w*|INVOICES?|CONSULT\w*|FEES? FOR SERVICES?"
    r"|SERVICES RENDERED)\b|\bINV\b|(?<![A-Z])INV ?\d"
)
_CPA_PAYMENT_CODE = re.compile(r"(?<= )(?:AP|MSP|BPY|APY)$")
#: §8.1 (A3-G refinement): the receiver field's label, before its value.
_RECEIVER_LABEL = re.compile(rf"^\s*(?:{'|'.join(RECEIVER_NAME_LABELS)})\b\s*")
#: §8.1 (A3-G refinement): a receiver value that names a bank is never the holder's name.
_RECEIVER_BANK_WORDS = re.compile(r"(?<![A-Z])(?:BANK|BANCORP|CREDIT UNION|SAVINGS|FCU)\b|\bCU\b")
#: §8.1: a trust's address prints at most this many words before its state (a city's name: 'LAS VEGAS', 'SAMPLE
#: LAKE CITY'); a longer tail names something else, whatever its words.
_TRUST_ADDRESS_MAX_WORDS = 3
#: §8.1: the business, institutional and benefit words that make the words before the trust form no person's name
#: (with the classifier's company form and its holder-noise business and product words).
_TRUST_BUSINESS_WORDS = re.compile(
    r"(?<![A-Z])(?:BANK|BANCORP|SAVINGS|NATIONAL|FEDERAL|TITLE|ESCROW|CORPORATE|WEALTH|CAPITAL|INVEST\w*|SECURITIES"
    r"|FUNDS?|FINANCIAL|ASSET|MANAGEMENT|ADVISORS?|PARTNERS|HOLDINGS|GROUP|SERVICES|CANADA|COMPANY|ACCOUNT|ACCT"
    r"|CLIENTS?|REALTY|PROPERTIES|PROPERTY|HEALTH|WELFARE|PENSION|BENEFITS?|UNION|LOCAL|PLAN|CARPENTERS|ANNUITY"
    r"|ACADEMY|SCHOOL|CHURCH|FOUNDATION|UNIVERSITY|COLLEGE|HOSPITAL|ASSOCIATION|SOCIETY|COUNTY|CITY|STATE)\b"
)
_TRUST_LAWYER_WORDS = re.compile(r"(?<![A-Z])(?:ESQ|ATTORNEYS?|LAW|LEGAL|IOLTA|IOTA|IOLA)\b")


#: §8.1: a holder run's last word of this many letters or more may print cut by the bank's field, keeping this many
#: letters or more, at the row's end.
_HOLDER_RUN_CUT_FROM = 5
_HOLDER_RUN_CUT_KEEPS = 4
#: §8.1 (standard A1, A2): a bare settlement word under the merchant's own name, a processor's, a carrier's or an
#: operating settlement, read by merchant_settlement beside _MERCHANT_SETTLEMENT_ENTRY on a row that is no transfer and
#: no person-to-person row. A row this word alone releases is counted, never verified and never a repeat, in each
#: spelling, slot and boundary (CreditFacts.settlement_released).
_HOLDER_NAMED_SETTLEMENT_ENTRY = re.compile(r"(?<![A-Z])(?:SETTLEMENT|SETTLMT|STLMT)(?![A-Z])")


#: §8.1: the legal forms a wire's sender or beneficiary name ends with, before its address.
_WIRE_PARTY_LEGAL_FORMS = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "PLLC", "PLC",
})
#: A card purchase printed in a form the card-form prefix (classifier._CARD_FORM_DEBIT_PREFIX: CHECKCARD or PURCHASE
#: <mmdd>) misses: Truist's DEBIT CARD PURCHASE, DBCRD PUR, Woodforest's POS DB, POS DEBIT or POS PURCHASE, POINT OF
#: SALE, CIBC's glued PURCHASE<digits>, or a charge ending in a state or province code and its country (Found's and
#: Bluevine's '<merchant> <city> <ST> USA|CAN').
_CARD_FORM_DEBIT = re.compile(
    r"^(?:DEBIT CARD PURCHASE|DBCRD PUR|POS (?:DB|DEBIT|PUR)|POINT OF SALE|PURCHASE\d{4,})"
    r"|(?<![A-Z])[A-Z]{2} (?:USA|CAN)$"
)
_DEPOSIT_CHANNELS = frozenset({"check", "cash_branch_atm"})


#: §8.1, §8.10: the method, matched rule and tier reason of an insurer's credit pass 7 releases as payment for the
#: business's work: counted and flagged, never verified and never toward a Q5 or Q6 repeat. It never joins
#: _REGISTRY_METHODS or any claimed set: a released row is unclaimed, so §8.10's holds 4 to 11 still read it (the
#: insurer-name hold, item 3, passes over it).
INSURER_FOR_WORK_METHOD = "insurer_paid_for_services"


#: §7.0, §8.10: the reason a credit under the $1 floor is held with. An account-verification entry is not a sale (T5),
#: so it is non_sale_purpose: §5.3's table has no micro-deposit code (a code of its own would be a change to the
#: table).
_MICRO_DEPOSIT_REASON = "non_sale_purpose"
