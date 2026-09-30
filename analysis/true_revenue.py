"""Classification 5.6: the true-revenue pass (docs/superpowers/specs/2026-09-28-true-revenue-design.md §5, §8).

Statement pass 7 (§6.2) runs after every verifying rule of `analysis/transaction_classifier.py`. It reads each posted
credit's payer facts (channel family, payer region, payer name and key, entry fields, the holds of §8.1), then runs
Q7's credit-union arm (§8.7) and the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold names, and last
gives every posted credit its tier and reason (§5.3), in the order of §8.10.

It imports the classifier's readers at call time (`_classifier`), never at load: the classifier imports this module
at its own load, so a load-time import back would be circular.

The payer region, payer name, entry fields and wire reading are the 5.5 readers' (S2.1 to S2.4): a holder's name in
the receiver field never names a payer (§5.2), a glued leading date never changes a reading (revenue_text), the
§7.9 wire vetoes are `_wire_vetoed` itself, and a wire is any row the 5.5 wire vetoes read as one
(`_wire_vetoes_apply`). The hold words follow the owner's veto convention (S2.2 review, item A): a spelling of four
letters or more (all its words counted) takes a (?<![A-Z]) left boundary, so a digit glued on its left never hides
it; a spelling of three letters or fewer keeps \\b.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from functools import cache
from typing import TYPE_CHECKING, Sequence

from .classification_registry import (
    CARD_SETTLEMENT_CREDIT_FORMS,
    DEALER_FUNDING_PAYERS,
    HEALTHCARE_PAYER_ALIASES,
    OPERATING_REVENUE_READ_ALIASES,
    OWNER_MONEY_PLATFORMS,
    P2P_SENDING_BANK_NAMES,
    PAYOUT_CREDIT_ENTITIES,
    SECTION_15_DEFERRED_PAYERS,
    STATEMENT_BANK_PRINTED_NAMES,
)
from .flag_groups import FINANCING_STATES
from .payee_matcher import PayeeMatch, match_known_payee, registry_match
from .revenue import revenue_contribution_flags

if TYPE_CHECKING:
    from .transaction_classifier import TransactionClassification

#: §8.1: the posting labels removed before a hold reads a row: §7.5's credit posting labels, the branch, card and
#: batch CREDIT labels, and the channel phrases.
_HOLD_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE|INSTANT|REAL TIME|COUNTER|POS|ATM|TELLER|BRANCH|CARD|BATCH|MERCHANT|VISA|CHECKCARD|PURCHASE)"
    r"\s+CREDIT\b|^CREDIT\b"
    r"|\bCREDIT FROM\b|\bFUNDS (?:TRANSFER|AVAILABLE)\b|\bINSTANT FUNDS\b"
)
#: §8.1, T4: the credit-side financing roots. A whole-word CREDIT counts only inside a payer name, next to another
#: name word; glued, it always counts. The roots have no left boundary; of the whole words, those of four letters or
#: more take (?<![A-Z]) (the veto convention).
_FINANCING_ROOT = re.compile(
    r"(?:(?<!RE)FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|LEASING|PORTFOL)"
    r"|CRED(?=ORA|IBLY)|[A-Z]CREDIT|CREDIT[A-Z]"
    r"|\b(?:CAP|FIN|ADV|MTG|MCA|RTR|SPV)\b|(?<![A-Z])(?:CAPI|FINA|FINAN|FINL|FNCL|LEASE)\b"
)
_WHOLE_CREDIT = re.compile(r"\bCREDITS?\b")
#: §8.1, T4 (A3 review, round 2): §7.9's word-end CRED arm, aligned with a glued letter on its left: a payer-name word
#: that ends in CRED (a credit provider's glued name, 'FABRICRED'), read on the payer's name only, as the whole-word
#: CREDIT is (never an entry field or a row that prints no payer's name field): never the whole word CRED, and never
#: the whole words SACRED and ACCRED (an abbreviation of accredited). Any other glued ...CRED name is held.
_GLUED_CRED_NAME = re.compile(r"(?!(?:SACRED|ACCRED)$)[A-Z]+CRED")
#: §8.1, §7.9 (A3): a wire's sender whose name a line wrap splits ('F INANCIAL', 'SERVICIN G') is read across the split
#: too, as §7.9's veto reads its first six words run together. A3 review, round 3 (_wrap_split_root): a join counts
#: only when its two words together spell one of these financing words (T4's run roots, spelled out, without the
#: glued-CREDIT arm and without the abbreviation CAPTL), or a prefix of one of _WRAP_PREFIX_MIN letters or more; two
#: words that spell none make no root ('SERVICE REPAIR', 'SOLO ANALYTICS', 'ALLEN D', 'CAPT L', 'SERVICE RX').
_WRAP_FINANCING_WORDS = (
    "FINANCIAL", "FINANCE", "FINANCING", "FUNDING", "FUNDS", "FUND", "FUNDED", "CAPITAL", "LOAN", "LOANS", "LENDING",
    "LENDER", "LENDERS", "LEND", "MORTGAGE", "ADVANCE", "ADVANCES", "ACCEPTANCE", "SERVICING", "SERVICER", "LEASING",
    "PORTFOLIO",
)
_WRAP_PREFIX_MIN = 5
#: §8.7: the dealer-funding words.
DEALER_FUNDING_WORDS = re.compile(
    r"(?<![A-Z])(?:VHCL PURCH\w*|VEHICLE PURCHASE\b|DEAL ?FUND\w*|FUNDLOAN\b|DEALER (?:FUND\w*|FND|PMT|PAY\w*)\b"
    r"|DLR PMT\b|AUTODLRPMT\b|CONTRACT FUND\w*|VADMIN FEE\b)"
)
#: §8.7: the dealer-payables words a listed auto lender prints on its dealer funding (Westlake's DES:PAYABLES).
_DEALER_PAYABLES_WORDS = re.compile(r"\bPAYABLES\b|\bTRADE PAY\w*|\bACCT FUND\w*")
#: §8.7: Q7 never fires on a loan, proceeds, advance or refund word. The owner's veto convention (S2.2 review, item
#: A): a spelling of four letters or more takes (?<![A-Z]), one of three letters or fewer keeps \b. The refund words
#: also read inflected and glued, as G15 reads them (a glued PREFUND or REFUNDS never verifies).
_DEALER_FUNDING_VETO = re.compile(
    r"(?<![A-Z])(?:LOANS?|PROCEEDS|ADVANCES?|CASH ADV\w*|RETURN\w*|REVERSAL\w*|RVSL|CHARGEBACK\w*|CHBK)\b"
    r"|\b(?:ADV|MCA|RFD|RTN)\b|[A-Z]*REFUND\w*|(?<![A-Z])(?:RFND|REFND)\w*"
)
#: §8.7: the credit-union arm's payer region and entry field.
_CREDIT_UNION_PAYER = re.compile(r"\bCU\b|\bCREDIT UNION\b|\bFCU\b|\bCU DIRECT\b|\bCUDL\b")
_VEHICLE_PURCHASE_ENTRY = re.compile(r"\bVHCL PURCH(?:ASE)?\b")
#: §8.7: a statement's credit-union dealer funding needs this many credits.
CREDIT_UNION_DEALER_MIN_CREDITS = 2
#: §8.7 (S4.3 review): a lender's floor-plan (wholesale) financing of the dealer's inventory is never dealer funding.
_DEALER_FLOOR_PLAN_WORDS = re.compile(r"(?<![A-Z])(?:FLOOR\w*|WHOLESALE\w*)")
#: §8.1: an insurer's name on the payer region.
_INSURER_NAME = re.compile(
    r"(?<![A-Z])(?:INSUR\w*|ASSURANCE\b|MUTUAL\b|CASUALTY\b|INDEMNITY\b|UNDERWRIT\w*)"
)
_CLAIM_WORD = re.compile(r"(?<![A-Z])CLAIMS?\b")
_POSSIBLE_RETURN = re.compile(
    r"(?<![A-Z])RETURN(?:ED|S)?\b|\bADJ\b|(?<![A-Z])ADJ(?:USTMENT|USTED)\b|(?<![A-Z])DISPUTE[DS]?\b"
    r"|(?<![A-Z])CREDIT MEMO\b|(?<![A-Z])OVERPA\w*"
    # §7.8: an auction's guarantee or arbitration refund of a vehicle the dealer bought.
    r"|(?<![A-Z])DEALSHIELD\b|(?<![A-Z])ARB(?:ITRATION)? CREDIT\b"
)
#: §8.1, §7.11: a card credit's posting labels (a refund to the card unless a form or the registry verified it).
_CARD_CREDIT_LABEL = re.compile(
    r"(?<![A-Z])(?:DEBIT CARD CREDIT|POS CREDIT|VISA CREDIT|CHECKCARD CREDIT|PURCHASE CREDIT)\b"
)
#: §8.1 (Q8): pay wording, read on the row before its receiver fields.
_PAY_WORDS = re.compile(
    r"(?<![A-Z])(?:PAYROLL\w*|PAYRLL\b|PAYROL\b|PAYRL\b|SALARY\b|SALARIES\b|REG SAL\b|WAGES?\b|NET ?PAY\b"
    r"|BONUS(?:ES)?\b|PAY PAY\b|PAIE\b|SALAIRES?\b|PAYCHECKS?\b|PAYCHK\b|PR PAY\w*|EMPLOYEE PAY\w*|EMP PAY\b"
    r"|DIR ?DEP\b|DIRDEP\b|DIRECT DEP\b(?!OSIT)|(?:DES|CO ENTRY DESCR) DIRECT DEPOSIT\b"
    r"|EXP(?:ENSE)? REIMB\w*)"
)
#: §8.1: benefit and pension credits.
_PERSONAL_INCOME = re.compile(
    r"(?<![A-Z])(?:XX)?SOC SEC\b|\bSSA\b|\bSSI\b|(?<![A-Z])SUPP SEC\b|(?<![A-Z])(?:XX)?VA BEN\w*"
    r"|(?<![A-Z])UNEMPLOY\w*|(?<![A-Z])UI BEN\w*"
    r"|(?<![A-Z])CHI?LD ?SUPP\w*\b|(?<![A-Z])CHILD ?CTC\b|(?<![A-Z])PENSION\b|(?<![A-Z])ANNUIT\w*"
    r"|(?<![A-Z])RETIRE\w*"
)
#: §8.1: a non-sale purpose.
_NON_SALE_PURPOSE = re.compile(
    r"(?<![A-Z])(?:INVEST\w*|DISTRIB(?!UTORS?\b|UTING\b)\w*|DIVIDENDS?\b|EQUITY\b|CONTRIB\w*|SHAREHOLDER\w*"
    r"|OWNERS?\b(?! OP\b| OPERATORS?\b)|STOCK\b|INTERCO\w*|INTER COMPANY\b|DUE FROM\b|SWEEP\b|ZERO BAL\w*"
    r"|REPAY\w*|PRINCIPAL\b|PAYOFF\b|PROMISSORY\b|CONVERTIBLE\b|TRANCHE\b|DRAWS?\b|DRAWDOWNS?\b"
    r"|DISBURS\w*"
    r"|ESCROW\b|EARNEST\b|SECURITY DEPOSIT\b|DEPOSIT BACK\b|SURPLUS\b"
    r"|GRANTS?\b|DONATION\w*|GIFT\b(?! CARD\b)|COURT\b|JUDGMENT\b"
    r"|REBATES?\b|REIMB\w*|INTEREST\b|REWARDS?\b|CASH ?BACK\b"
    r"|RFND\w*|REFND\w*)"
    r"|\bZBA\b|[A-Z]*REFUND\w*"
)
#: §8.1, S4.2 review (I6b): §7.5's investment words BROKERAGE, SECURITIES and WEALT join the owner money group (the
#: standing rule: owner money never becomes revenue), except on a row that prints §7.5's accounts-payable or
#: vendor-payment wording (_accounts_payable_wording; S4.2 fix measurement): a wealth, brokerage or securities firm
#: paying a vendor from its payables. Such a row is counted and flagged, never verified: §7.5's remittance veto reads
#: the same words, and Q5 and Q6 refuse them as proof (CreditFacts.refused_word).
_INVESTMENT_PURPOSE = re.compile(r"(?<![A-Z])(?:BROKERAGE\w*|SECURITIES\b|WEALT\w*)")
#: §8.1: a healthcare payer's member or premium credit.
_HEALTHCARE_MEMBER_WORDS = re.compile(
    r"(?<![A-Z])(?:REIMB\w*|MEMBER\b|SUBSCRIBER\b|PREMIUM\b)|\bMBR\b"
)
#: §8.4, T13: an account designation printed by a named transfer.
_ACCOUNT_DESIGNATION = re.compile(
    r"(?<![A-Z])(?:CHECKING|CHKG|SAVINGS|SAVING|SVGS|MONEY MARKET|ACCOUNT|ACCT|EVERYDAY)\b|\b(?:CHK|SAV|MMA|DDA)\b"
    r"|\bX{2,}\d{2,}\b|(?<![A-Z])ENDING (?:IN )?\d{3,}\b"
)
_ACCOUNT_WORDS = frozenset({
    "CHECKING", "CHK", "CHKG", "SAVINGS", "SAVING", "SAV", "SVGS", "MONEY", "MARKET", "MMA", "DDA", "ACCOUNT", "ACCT",
    "EVERYDAY",
})
#: §8.5: the loose wire words, for tiering only (a row the 5.5 wire vetoes read as a wire is one too: _channel).
_LOOSE_WIRE = re.compile(
    r"(?<![A-Z])(?:WIRE|FEDWIRE|FED WIRE|CHIPS CREDIT|SWIFT|FOREIGN REMITTANCE|WT FED|FED REF)\b|\bIWT\b"
)
#: §8.5 (A3): on a row that prints transfer wording, the loose wire words and a bare CHIPS ('INCOMING CHIPS TRANSFER')
#: name the wire channel (_channel). A bare CHIPS elsewhere may be a payer's own word, so _LOOSE_WIRE keeps CHIPS CREDIT.
_TRANSFER_WIRE_WORDS = re.compile(_LOOSE_WIRE.pattern + r"|(?<![A-Z])CHIPS\b")
#: §8.5: a sender that names a bank, a title or an escrow firm never verifies by repetition.
_BANK_OR_TITLE_SENDER = re.compile(
    r"\b(?:BANK|BANCO|BANCORP|N A|TRUST COMPANY|CREDIT UNION|FCU|SAVINGS|TITLE|ESCROW|CLOSING|SETTLEMENT)\b"
)
#: §8.6: the verification-only words: sales wording often enough to count, never proof.
_VERIFICATION_ONLY = re.compile(
    r"(?<![A-Z])(?:SETTLEMENT\b|TAXES\b|FEES\b|SUBSCRIPTIONS?\b|DISCOUNT\w*|COMM?ISS?IONS?\b"
    r"|COMPENSATION\b|EXPENSES?\b|AFFILIATE\b|PERSONAL\b|CLOSING\b|SUPPLY CHAIN\b"
    r"|EARLY PAY(?:MENT)?\b|ALLOWANCES?\b|SHORTAGES?\b)"
    r"|\b(?:TAX|IRS|CRA|FEE|SCF|RMA)\b"
)
_ENTRY_VERIFICATION_ONLY = re.compile(r"(?<![A-Z])(?:FLOOR ?PLAN\b|FLOORPLAN\b|EQUIP\w*)|\bVIN\b")
_CONSUMER_ENTRY = re.compile(r"\b(?:PPD|WEB)\b")
#: §8.6 method names.
_Q6_METHODS = ("named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer")
#: §8.1 (review C2): the financing words on a registry row: the recurrence veto's financing words (§7.0), the
#: new-read financing veto (§7.2) and the auction's financing words (§7.8). A platform's or processor's capital,
#: advance or loan credit and an auction's floor-plan or NextGear credit are never claimed by the registry.
_REGISTRY_FINANCING_WORDS = re.compile(
    r"(?<![A-Z])(?:LOANS?|CAPITAL|CAPI|CAPIT|CAPITA|CAPTL|FINANC\w*|LEND\w*|ADVANCE[SD]?|ADVNC|ADVN|ADVC"
    r"|CASH ADV\w*|FUNDING|FUNDNG|FUNDED|PROCEEDS|DRAW|FLOOR ?PLAN|FLOORPLAN)\b"
    r"|\b(?:CAP\d*(?:SEC)?|FIN|ADV|MCA|NGC)\b"
)
#: G2 (review I1): a financing root glued inside a word of a registry row (STRIPECAPITAL, SHOPIFYCAPITAL).
_GLUED_FINANCING_ROOT = re.compile(r"CAPITAL|CAPTL|FINANC|FUNDING|FUNDNG|LENDING|LENDER|LOAN")
#: The registry-family methods: a platform, processor or payout the operating registry named (§8.9).
_REGISTRY_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "wholesale_auction_payout_form",
})
#: §5.3: tiers by revenue state; the two middle tiers are unverified.
_TIER_OF_STATE = {"verified_revenue": "verified", "non_revenue": "non_revenue"}
#: §8.10: the lender and financing debit states payer_debited_as_lender reads.
_LENDER_DEBIT_STATES = frozenset({"confirmed_lender", "potential_lender"}) | FINANCING_STATES
#: §7.5, the standing rule (S4.2 review I6b): brokerage, investing and crypto-exchange platforms (the registry's
#: OWNER_MONEY_PLATFORMS, §7.0: a table that names companies lives there). A credit from one is the owner's own money
#: coming back (owner money never becomes revenue): held as non_sale_purpose. The classifier's consumer savings and
#: investing originators (_SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS) are read too.
_OWNER_MONEY_PLATFORMS = re.compile(OWNER_MONEY_PLATFORMS)
#: §15, §19 OQ4 (S4.2 review I6a): the payers of the deferred family items (the registry's
#: SECTION_15_DEFERRED_PAYERS), which stay counted and flagged until the owner rules on each: Q5 and Q6 never verify
#: them, they never count toward a Q5 or Q6 repeat, and on a wire or an ACH or EFT row their reason is
#: named_payer_purpose_refused (S4.2 re-review: a payer Q5 and Q6 refuse as proof, §8.9; never "One-off payer", as a
#: deferred source often repeats). The registry's own deferred sources are left to the registry by _left_to_its_family.
_SECTION_15_DEFERRED_PAYERS = re.compile(SECTION_15_DEFERRED_PAYERS)
#: §7.7: a bare X12 TRN*1* with no entry description, from a healthcare payer, is deferred too.
_BARE_X12_TRACE = re.compile(r"\bTRN 1\b")
#: §7.1 (S4.2 review I5): the NET SETTLE card form, read whether or not its refusal or the card veto matches: such a
#: row is decided by §7.1's own rule alone (its refusal and its three-credit count), never by Q5 or Q6.
_NET_SETTLE_FORM = re.compile(next(form.pattern for form in CARD_SETTLEMENT_CREDIT_FORMS if form.label == "net_settle"))
#: §8.2 (S4.2 review I2): the field labels, originator-name labels, SEC codes and reference labels a transfer prints
#: (the classifier's _ACH_FIELD_SEGMENT, _ENTITY_NAME_LABELS and _GLUED_SEC_CODE vocabulary). None names its
#: counterparty.
_TRANSFER_FIELD_LABEL_WORDS = frozenset({
    "DES", "DESC", "DESCR", "ORIG", "ORIGINATOR", "CO", "NAME", "COMPANY", "ENTRY", "DATE", "ID", "IND", "INDN",
    "TRACE", "SEC", "EED", "TRN", "CONF", "CONFIRMATION", "REF", "REFERENCE", "MEMO", "CUST", "TYPE", "INSTR", "SRF",
    "RFB", "IMAD", "OMAD", "SEQ", "NO", "NUMBER", "NBR", "NUM", "TRANSACTION",
    "CCD", "CTX", "PPD", "WEB", "IAT", "TEL", "POP", "BOC", "ARC", "RCK", "CIE", "COR",
})
#: §8.2 (S4.2 review I2): a reference label and the value after it, letters only or not ('REF IBEABCD').
_TRANSFER_REFERENCE_VALUE = re.compile(
    r"\b(?:REF|REFERENCE|CONF|CONFIRMATION|TRN|TRACE|ID|SEQ|TRANSACTION)\b(?: (?:NO|NUM|NUMBER|NBR))? \S+"
)
#: Q4 (S4.2 review I7): the rail, posting and layout words a person-to-person row prints around a sender printed
#: without FROM ('INTERAC E TRANSFER RECEIVED <sender>', 'ZELLE CREDIT <sender>', 'VIREMENT INTERAC RECU'), besides
#: the generic words, the field labels and the reference tokens; none is ever a sender's name. A Venmo or Cash App
#: cash-out prints no sender at all.
_P2P_NOT_SENDER_WORDS = frozenset({
    "ZELLE", "INTERAC", "ETRANSFER", "TFR", "VIREMENT", "VFC", "AUTODEPOSIT", "AUTODEP", "VENMO", "CASHAPP", "APP",
    "POPMONEY", "RTP", "AUTO", "CASHOUT", "CASH", "OUT", "TRANSFERS", "XFER", "BANK", "DEBIT", "EPAY", "INST", "INS",
    "PURCHASE", "CARD", "NOW", "NET", "NETWORK", "USA",
    # French posting words (Desjardins, National Bank, TD's French layouts).
    "RECU", "RECUE", "PAR", "BANQUE", "EN", "LE", "LA", "DE", "DU", "ES",
})
#: Q4 (S4.2 review I7): after these the named party is a recipient, or the row is a reversal: no sender is read.
_P2P_NO_SENDER_WORDS = frozenset({
    "TO", "CANCEL", "CANCELLED", "CANCELED", "ANNULE", "REFUND", "REFUNDED", "RTN", "RETURN", "RETURNED", "REVERSAL",
})
#: Q4 (S4.2 review I7): a sender printed without FROM ends at these (§5.2's sender ends, and the field labels).
_P2P_SENDER_END_WORDS = frozenset({"ON", "REF", "CONF", "MEMO", "TRN", "ID", "FOR", "NOTE", "INFO"})
#: Q4, §5.2 (S4.2 re-review fix 1b): more layout words, never a sender's name: the posting words a rail prints where
#: a sender would stand ('ZELLE BUSINESS PAYMENT', 'ZELLE RECURRING PAYMENT', 'INTERAC E TRANSFER REQUEST FULFILLED',
#: 'RTP CREDIT REMITTANCE INFO'), the French ones ('VIREMENT INTERAC DEPOT AUTOMATIQUE', 'VIREMENT INTERAC ENTRANT',
#: 'VIREMENT EN LIGNE TF'), Apple Cash's own name printed again after PMNT RCVD, and its card code CKCD.
_P2P_LAYOUT_WORDS = frozenset({
    "BUSINESS", "RECURRING", "REQUEST", "FULFILLED", "REMITTANCE",
    "DEPOT", "AUTOMATIQUE", "ENTRANT", "ENTRANTE", "LIGNE", "TF",
    "APPLE", "CKCD",
})
#: Q4, §5.2 (S4.2 re-review fix 1b): phrases removed before the sender is read: a sending bank's name (the registry's
#: P2P_SENDING_BANK_NAMES, 'ZELLE CREDIT BANK OF AMERICA') and Zelle's PAY ID label.
_P2P_LAYOUT_PHRASES = re.compile(
    r"(?<![A-Z])(?:" + "|".join(re.escape(name) for name in sorted(P2P_SENDING_BANK_NAMES, key=len, reverse=True))
    + r"|PAY ID)\b"
)
#: Q4, §5.2 (S4.2 re-review fix 1b): a wallet's city, printed after its sender ('CASH APP*<sender>*OAKLAND CA', Apple
#: Cash's CUPERTINO CA, Venmo's NEW YORK CITY NY and SAN JOSE CA, Square's SAN FRANCISCO CA): the sender ends there.
#: S4.2 final review (fix 3): only as the sender's tail (_without_city_tail): a sender whose name starts with the city
#: ('ZELLE CREDIT NEW YORK FABRIKAM LLC') keeps it.
_P2P_WALLET_CITY = re.compile(r"(?<![A-Z])(?:CUPERTINO|OAKLAND|(?:SOUTH )?SAN FRANCISCO|SAN JOSE|NEW YORK(?: CITY)?)\b")
#: Q4, §5.2 (S4.2 re-review fix 1b): the US state codes a wallet prints as a trailing tail ('VENMO <sender> VISA
#: DIRECT NY'), removed from the sender's end (_without_state_tail).
_US_STATE_TAIL = frozenset("""
AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC
SD TN TX UT VT VA WA WV WI WY DC PR US CAUS
""".split())
#: §5.2 (S4.2 re-review fix 1b): a Venmo or Cash App cash-out prints no sender ('CASH APP*CASH OUT*OAKLAND CA',
#: 'VENMO CASHOUT <reference> <name>': the name is the wallet's owner). S4.2 final review (fix 3): only on a Cash App or
#: Venmo row: CASH OUT on any other rail is a sender's own words ('ZELLE CREDIT CASH OUT AUTO LLC').
_P2P_CASH_OUT = re.compile(
    r"(?<![A-Z])(?:CASH ?APP|SQUARE CASH|VENMO)\b.*?(?<![A-Z])CASH ?OUT\b"
    r"|(?<![A-Z])CASH ?OUT\b.*?(?<![A-Z])(?:CASH ?APP|SQUARE CASH|VENMO)\b"
)
#: Q4 (S4.2 re-review fix 1b): a legal form or an article alone names nobody ('RTP CREDIT 1ABC INC SAN FRANCISCO CA',
#: whose name the reference reading drops).
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
_INTERAC_FORM = re.compile(r"(?<![A-Z])(?:INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|AUTODEPOSIT)\b")
#: §8.2 (S4.2 follow-up 2): the French transfer and posting words, never a transfer's counterparty ('VIREMENT EN LIGNE
#: TF <reference>', 'VIREMENT ENTRE COMPTES', 'VIREMENT DE FONDS', 'VIREMENT RECU', 'VIREMENT PAR BANQUE EN DIRECT').
_VIREMENT_TRANSFER_WORDS = frozenset({
    "VIREMENT", "LIGNE", "TF", "ENTRE", "COMPTE", "COMPTES", "FONDS", "RECU", "RECUE", "ENTRANT", "ENTRANTE", "PAR",
})
#: §8.2 (S4.2 final review, fix 5): the French month names and abbreviations a date prints ('02 JUIN VIREMENT EN
#: LIGNE TF <reference>'), never a transfer's counterparty (the English ones are reference tokens already).
#: S4.2 fix round 4: only where a date prints them (_without_date_months): MARS and MAI are also names.
_FRENCH_MONTHS = frozenset({
    "JANV", "JANVIER", "FEVR", "FEVRIER", "MARS", "AVR", "AVRIL", "MAI", "JUIN", "JUIL", "JUILLET", "AOUT", "SEPT",
    "SEPTEMBRE", "OCT", "OCTOBRE", "NOV", "NOVEMBRE", "DEC", "DECEMBRE",
})
#: §8.2 (S4.2 fix round 4): a day of the month printed as its own word beside a month ('02 JUIN', 'JUIN 2').
_DAY_NUMBER = re.compile(r"0?[1-9]|[12]\d|3[01]")
#: Q4, §5.2 (S4.2 fix round 4): the four-digit group Quebec's numbered companies print twice (NNNN-NNNN). The Quebec
#: words after it are the classifier's _QUEBEC (S4.2 fix round 5: one set for the key and the numbered-company guard).
_FOUR_DIGITS = re.compile(r"\d{4}")
#: §8.2 (S4.2 final review, fix 5): a bank branch a transfer prints ('AVIS VIREMENT <n> CTR BANCAIRE <branch>'), never
#: its counterparty.
_BANK_BRANCH_WORDS = re.compile(r"(?<![A-Z])(?:CTR BANCAIRE|CENTRE BANCAIRE|SUCCURSALE|BRANCH)\b")
#: §8.2, §8.5 (A3, the precision sample of the largest counted rows, 2026-09-30): a wire's channel and layout words,
#: never a transfer's counterparty ('INCOMING FEDWIRE TRANSFER' names nobody). Some are generic words already; the
#: set names them all, so the rule reads in one place.
_WIRE_LAYOUT_WORDS = frozenset({
    "INCOMING", "INBOUND", "INBD", "FEDWIRE", "FED", "WIRE", "WIRES", "WT", "IWT", "TRANSFER", "CREDIT", "CHIPS",
    "SWIFT", "BOOK", "DOMESTIC", "INTL", "INTERNATIONAL",
})
#: §8.1 (A3): the holder's own currency conversion: foreign-exchange and currency-conversion wording, English and
#: French. It never names a counterparty (_without_currency_conversion); a credit that prints it and names no payer
#: besides it is the holder's own money converted from one currency to another (_currency_conversion). The corpus
#: prints ONLINE BANKING FOREIGN EXCHANGE; the other spellings are the banks' common forms, no corpus row yet.
_CURRENCY_CONVERSION = re.compile(
    r"(?<![A-Z])(?:FOREIGN (?:EXCHANGE|EXCH|CURRENCY (?:EXCHANGE|CONVERSION))|FX (?:CONVERSION|CONV|EXCHANGE|EXCH|TRADE"
    r"|DEAL|SPOT|CONTRACT)|CURRENCY (?:EXCHANGE|EXCH|CONVERSION|CONV)|(?:CONVERSION|CHANGE|ACHAT|VENTE) DE DEVISES"
    r"|CONV(?:ERSION)? DEVISES?)\b"
)
#: §8.1 (A3): a title firm named on the payer region, whose payment is property-closing proceeds (an asset sale), never
#: the business's operating revenue: the whole word TITLE beside a title-firm word or a legal form (either order, AND
#: between them allowed), or a national title insurer. TITLEIST and TITLE BOXING CLUB are no title firm.
_TITLE_FIRM = re.compile(
    r"\bTITLE (?:AND )?(?:AGENCY|AGENCIES|AGCY|CO|COMPANY|COMPANIES|CORP|CORPORATION|INC|LLC|LTD|TRUST|INS|INSURANCE"
    r"|GUARANTY|GUARANTEE|GTY|SERVICES|SERVICE|SVCS|ESCROW|CLOSING|CLOSINGS|SETTLEMENT|SETTLEMENTS|PARTNERS|GROUP)\b"
    r"|\b(?:AGENCY|TRUST|INSURANCE|GUARANTY|SERVICES|ESCROW|CLOSING|CLOSINGS|SETTLEMENT|ABSTRACT)(?: AND)? TITLE\b"
    r"|\b(?:CHICAGO|FIRST AMERICAN|FIDELITY NATIONAL|OLD REPUBLIC|STEWART|TICOR|COMMONWEALTH LAND|LAWYERS|WESTCOR"
    r"|WESTCOR LAND|NORTH AMERICAN|ATTORNEYS|WFG NATIONAL|DOMA) TITLE\b(?! BOXING\b| CLUB\b)"
)
#: §8.1 (A3, orchestrator ruling): a title firm also pays the holder's own fee at closing: a commission, an origination
#: or broker fee, an invoice, consulting or services rendered, cited in the payment's purpose (_title_purpose_text: a
#: wire's OBI, RMR, PMT DET, RFB or URI purpose, an ACH entry, a transfer's memo). Such a credit is not held by the
#: title hold and takes its normal reading.
_TITLE_FEE_WORDING = re.compile(
    r"(?<![A-Z])(?:COMMISSIONS?|COMM|ORIGINATION|ORIG FEE|BROKER\w*|INVOICES?|CONSULT\w*|FEES? FOR SERVICES?"
    r"|SERVICES RENDERED)\b|\bINV\b|(?<![A-Z])INV ?\d"
)
#: §8.1 (A3 review): a wire's purpose fields, each up to the next wire field: OBI, RMR, PMT DET, RFB, and a URI label
#: wherever it prints (Chase prints its URI inside OBI, a book transfer inside REF, a line wrap may split it: 'U RI').
#: A REF field is never read: on the Fedwire layout it is the sender's bank reference ('REF COMM BANK NYC'), and Bank
#: of America's SERVICE REF is its own reference; Santander's REF is its purpose (_title_purpose_text). A3 review round
#: 2: ORIG FEE is purpose wording, never the start of an originator field.
_WIRE_PURPOSE_FIELD = re.compile(
    r"\b(?:OBI|RMR|PMT DET|RFB|U ?R ?I)\b (.*?)"
    r"(?=\b(?:BNF|NBNF|BBI|OBI|SRF|TRN|IMAD|ACCT|SND BK|RFB|RMR|PMT DET|REF|ORIG(?! FEE\b)|B O|ORG)\b|$)"
)
#: §8.1, T4 (A3-G): a wire's originator that reads as a bank by its own form (the classifier's BANK_FORM_ORIGINATOR),
#: never a bank's settlement form (BANK_SETTLEMENT_ORIGINATOR). Money a bank sends on its own behalf is more often loan
#: proceeds or the bank's own funds than a customer's payment: held as financing_named_payer. A3-G refinement: a bank
#: that names the ultimate originator only relays, and the payer region reads that customer (relayed_customer_text).
#: A3-G refinement: a sender the payer region reads as bare channel words names nobody (credit_facts).
_BARE_CHANNEL_WORDS = frozenset({"WIRE", "WIRES", "TRANSFER", "BOOK", "CREDIT"})
#: §8.1 (A3-G refinement): a holder's name read from the statement's own incoming receiver fields (INDN, IND NAME,
#: RECEIVER NAME) needs this many credits, words and letters; a run-together match needs this many letters.
_RECEIVER_HOLDER_MIN_CREDITS = 2
_RECEIVER_HOLDER_MIN_WORDS = 2
_RECEIVER_HOLDER_MIN_LETTERS = 8
_RECEIVER_HOLDER_RUN_LETTERS = 12
#: §8.1 (A3-G refinement): the receiver field's label, before its value.
_RECEIVER_LABEL = re.compile(r"^\s*(?:INDN|IND NAME|RECEIVER NAME|RECV NAME)\b\s*")
#: §8.1 (A3-G refinement): a receiver value that names a bank is never the holder's name.
_RECEIVER_BANK_WORDS = re.compile(r"(?<![A-Z])(?:BANK|BANCORP|CREDIT UNION|SAVINGS|FCU)\b|\bCU\b")
#: A3-G: Bank of America's sending-bank field, up to its next field.
_SENDING_BANK_FIELD = re.compile(r"\bSND BK\b (.*?)(?=\b(?:ID|PMT DET|OBI|RMR|BNF|TRN|IMAD|SRF|RFB)\b|$)")
#: A3-G: an originator equal to the sending bank keeps at least this many letters on its shorter side (A3-G review: 8).
_SENDING_BANK_MIN_LETTERS = 8
#: §8.1 (A3-G): a personal trust's words: the trust word, the trustee's TTEE, and the adjectives a personal trust
#: prints before its trust word.
_PERSONAL_TRUST_WORDS = frozenset({"TRUST", "TRST", "TR", "TTEE"})
_PERSONAL_TRUST_ADJECTIVES = frozenset({"REVOCABLE", "REV", "LIVING", "FAMILY", "FAM", "IRREVOCABLE", "IRREV"})
_PERSONAL_TRUST_FILLERS = frozenset({"THE", "AND", "OF"})
_PERSONAL_TRUST_MAX_NAME_WORDS = 5
#: §8.1 (A3-G review, a): the words a trust form may print after it: its agreement and date words (DTD, DATED, U A,
#: UA, UAD, UTA), a date or a number, a PO box and the country; on a wire's originator field, which prints the
#: sender's address after the name, an address that ends in a US state code.
_TRUST_TAIL_WORDS = frozenset({"DTD", "DATED", "U", "A", "UA", "UAD", "UTA", "PO", "BOX", "US", "USA"})
#: §8.1 (A3-G re-review): the words a trust's address never prints before its state: account, service, department and
#: office words, and the trades a business names itself by ('... TRUST ROOFING <city> <state>' is a company).
_TRUST_NOT_PLACE_WORDS = frozenset({
    "ACCOUNT", "ACCT", "ACCOUNTS", "SERVICES", "SERVICE", "SVCS", "SVC", "DEPT", "DEPARTMENT", "DIV", "DIVISION",
    "OFFICE", "OPERATING", "OPERATIONS", "ADMIN", "ADMINISTRATION",
    # A3-G re-review 2: a trust company's custody and administration words.
    "CUSTODY", "CUSTODIAN", "CUSTODIANS", "ADMINISTRATOR", "ADMINISTRATORS",
    "ROOFING", "LANDSCAPE", "CONSTRUCTION", "CONTRACTING", "CONTRACTORS", "PLUMBING", "ELECTRIC", "ELECTRICAL", "HVAC",
    "LANDSCAPING", "TRUCKING", "TRANSPORT", "LOGISTICS", "CLEANING", "SUPPLY", "SALES", "MARKETING", "CONSULTING",
    "DESIGN", "AUTO", "MOTORS", "RESTAURANT", "BAKERY", "CAFE", "GRILL", "PIZZA", "DENTAL", "MEDICAL", "CLINIC",
    "PHARMACY", "SALON", "SPA", "FITNESS", "STUDIO", "MEDIA", "PRODUCTIONS", "TECHNOLOGIES", "TECH", "SYSTEMS",
    "ENTERPRISES", "INDUSTRIES", "MANUFACTURING", "FARMS", "RANCH", "TRAVEL", "HOMES", "BUILDERS", "REMODELING",
    "PAINTING", "FLOORING", "STORE", "SHOP", "MARKET", "WHOLESALE", "DISTRIBUTION", "IMPORTS", "EXPORTS", "TRADING",
})
#: §8.1 (A3-G re-review 2): a trust's address prints at most this many words before its state (a city's name: 'LAS
#: VEGAS', 'SAMPLE LAKE CITY'); a longer tail names something else, whatever its words.
_TRUST_ADDRESS_MAX_WORDS = 3
#: A street type right after the trust word makes it a street's name ('12 TRUST RD'), never a trust form.
_STREET_WORDS = frozenset({
    "RD", "ROAD", "ST", "STREET", "AVE", "AVENUE", "DR", "DRIVE", "LN", "LANE", "BLVD", "WAY", "CT", "COURT", "PL",
    "PLACE", "HWY", "PKWY", "CIR", "TER", "TRL",
})
#: §8.1 (A3-G review, b): the business, institutional and benefit words that make the words before the trust form no
#: person's name (with the classifier's company form and its holder-noise business and product words).
_TRUST_BUSINESS_WORDS = re.compile(
    r"(?<![A-Z])(?:BANK|BANCORP|SAVINGS|NATIONAL|FEDERAL|TITLE|ESCROW|CORPORATE|WEALTH|CAPITAL|INVEST\w*|SECURITIES"
    r"|FUNDS?|FINANCIAL|ASSET|MANAGEMENT|ADVISORS?|PARTNERS|HOLDINGS|GROUP|SERVICES|CANADA|COMPANY|ACCOUNT|ACCT"
    r"|CLIENTS?|REALTY|PROPERTIES|PROPERTY|HEALTH|WELFARE|PENSION|BENEFITS?|UNION|LOCAL|PLAN|CARPENTERS|ANNUITY"
    r"|ACADEMY|SCHOOL|CHURCH|FOUNDATION|UNIVERSITY|COLLEGE|HOSPITAL|ASSOCIATION|SOCIETY|COUNTY|CITY|STATE)\b"
)
#: §8.1 (A3-G review, c): a bank's or a trust company's form right after the trust word, and a lawyer's or a client
#: trust account anywhere in the sender.
_TRUST_COMPANY_SUFFIX = re.compile(r"^(?:TRUST|TRST|TR) (?:N A|NA|FSB|BANK|COMPANY|CO)\b")
_TRUST_LAWYER_WORDS = re.compile(r"(?<![A-Z])(?:ESQ|ATTORNEYS?|LAW|LEGAL|IOLTA|IOTA|IOLA)\b")
#: §8.1 (A3 review, round 2): the company forms that name a currency-exchange company on an originator field beside
#: currency wording ('CURRENCY EXCHANGE INTERNATIONAL DES:PAYMENT', 'FOREIGN EXCHANGE CO DES:PAYMENT'). INTERNATIONAL
#: and INTL are organisation words the generic and wire-layout words drop, and CO a field label the transfer reader
#: drops, so the counterparty reading alone never names such a company.
_CURRENCY_COMPANY_WORDS = frozenset({"LLC", "INC", "CORP", "CO", "LTD", "INTERNATIONAL", "INTL"})


@dataclass(frozen=True)
class CreditFacts:
    """§8: one posted credit's payer facts."""

    channel: str
    region: str
    name: str
    key: tuple[str, ...]
    entry: str
    hold: str | None
    claimed: bool
    wire_n1: bool
    company_form: bool
    public_or_healthcare: bool
    healthcare: bool
    numbered: bool
    electronic: bool
    refused_word: bool
    round_sum: bool
    consumer_entry: bool
    transfer_no_counterparty: bool
    account_designation: bool


def _classifier():
    from . import transaction_classifier

    return transaction_classifier


def healthcare_payer(region: str) -> bool:
    """§5.2: a payer region that matches HEALTHCARE_PAYER_ALIASES."""
    return bool(region) and registry_match(region, HEALTHCARE_PAYER_ALIASES) is not None


def government_payer(region: str) -> bool:
    """§5.2: a payer region the public-payer patterns of §7.6 match at its start, and the payer-name veto does not."""
    classifier = _classifier()
    if not region:
        return False
    name = classifier._PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    found = classifier._PUBLIC_PAYER_NAME.match(name)
    return (
        found is not None
        and not any(ch.isdigit() for ch in found.group(1))
        and classifier._PUBLIC_PAYER_NAME_VETO.search(name) is None
    )


def public_region(text: str) -> str:
    """§5.2: the region a government payer is read on: the payee region of the row before its receiver fields, with
    the template prefixes removed, before the digit cut, so 'TREAS 310' keeps its digits. On an incoming wire it is
    the originator (S4.2 review M2: the payee region of a wire reads its label, 'WIRE')."""
    classifier = _classifier()
    if classifier._is_wire_row(text):
        return _wire_originator_text(text)
    return classifier._payee_region(classifier._strip_revenue_template(classifier._before_receiver(text))).strip()


def _wire_originator_text(text: str) -> str:
    """§5.2 (S4.2 review M2): a wire's originator after its label, up to the next wire field, before the digit cut
    (the payer region's reading, _wire_payer_region, cuts it at the first reference token)."""
    classifier = _classifier()
    santander = classifier._SANTANDER_WIRE.match(text)
    if santander is not None:
        return santander.group("originator").strip()
    found = classifier._WIRE_ORIGINATOR_LABEL.search(text)
    if found is None:
        return ""
    # A3-G: a SWIFT 50F line number is never part of the originator (the normalizer drops it with its slash).
    rest = text[found.end():]
    end = classifier._WIRE_FIELD_END.search(rest)
    originator = (rest[: end.start()] if end is not None else rest).strip()
    # A3-G refinement: a relaying bank's customer is the originator (the payer region reads it the same way, with the
    # region's address context, A3-G re-review 2).
    region = classifier._leading_name_words(originator)
    after, city_state_end = classifier.originator_address(text, region)
    customer = classifier.relayed_customer_text(region, rest, after=after, city_state_end=city_state_end)
    return customer.strip() if customer else originator


@cache
def _p2p_sender_rail() -> re.Pattern[str]:
    """Q4 (S4.2 review I7): the rails a sender printed without FROM follows: §8.4's consumer rails and RTP. A push
    rail a platform's payout prints after the payer's name ('<payer> ... VISA DIRECT <city> <state>') is not read."""
    return re.compile(_classifier()._CONSUMER_P2P_RAIL.pattern + r"|(?<![A-Z])RTP\b")


def _p2p_sender_region(text: str) -> str:
    """Q4, §5.2 (S4.2 review I7): the sender a person-to-person rail prints without FROM ('E TRANSFER AUTODEPOSIT
    <sender>', 'INTERAC E TRANSFER RECEIVED <sender>', 'ZELLE TRANSFER <sender>', 'ZELLE CREDIT <sender>'), as its key
    reads it (_p2p_sender_readings)."""
    return _p2p_sender_readings(text)[0]


def _p2p_sender_readings(text: str) -> tuple[str, str]:
    """Q4, §5.2 (S4.2 review I7): the sender a person-to-person rail prints without FROM, read two ways: (its key
    reading, its holder-test reading). The key reading is the name words after a consumer rail or RTP, skipping the
    rail, posting, layout and generic words and single letters, up to a field label, one of §5.2's sender ends or a
    reference token after a name word. When a rail is followed by no name word the next rail is read ('NOW NETWORK
    CREDIT ZELLE CREDIT NOW NET ID <n> ZELLE <sender>'). ('', '') when the row prints FROM (payer_region reads it),
    names a recipient or a reversal, or prints no sender (a Venmo or Cash App cash-out).

    S4.2 re-review (fix 1): a reference printed before the sender is no part of it, so a per-row reference never
    splits one sender ('E TRANSFER <reference> <sender>'). A sending bank's name and Zelle's PAY ID are removed first,
    the sender ends at a wallet's city, a trailing US state code is dropped, and a legal form or an article alone is
    no sender.

    S4.2 final review (fixes 1 and 3): the number is kept only on §5.2's province arm, the numbered company proper
    ('1234567 ONTARIO INC': its identity, and the holder test's digit run), so '<reference> FABRIKAM SUPPLY LTD' is one
    sender. A city ends the sender only as its tail, and a state code only after two words (_without_state_tail). A
    legal form left alone by the skipped words reads them back ('ZELLE CREDIT CASH OUT AUTO LLC'). The holder test
    also reads a layout word inside the name ('ZELLE CREDIT REQUEST FABRIKAM LLC'), which the key skips so that one
    sender's rows printed with and without it stay one sender."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    if re.search(r"\bFROM\b", row) or _P2P_CASH_OUT.search(row):
        return "", ""
    for rail in _p2p_sender_rail().finditer(row):
        read = _sender_tokens(_without_city_tail(_P2P_LAYOUT_PHRASES.sub(" ", row[rail.end():])))
        if read is None:
            return "", ""
        tokens, number = read
        words = _without_state_tail([token for token, name in tokens if name])
        if number and _numbered_province_sender().match(" ".join([number, *words])):
            return " ".join([number, *words]), " ".join([number, *words])
        if words and not all(word in _NOT_A_NAME_ALONE for word in words):
            return " ".join(words), _holder_reading(tokens)
        formed = _read_back_legal_form(tokens)
        if formed:
            return formed, formed
    return "", ""


@cache
def _numbered_province_sender() -> re.Pattern[str]:
    """Q4, §5.2 (S4.2 final review, fix 1): the province arm of §5.2's numbered payer region: six or more digits and
    a province, territory, CANADA or a cut of one. S4.2 fix round 4: or Quebec's own form, four digits, a hyphen and
    four digits before QUEBEC, a cut of it or QC ('1234-5678 QUEBEC INC', normalized to '1234 5678 QUEBEC INC'), both
    digit groups kept. S4.2 fix round 5: the Quebec words are the classifier's _QUEBEC, which the numbered-company
    guard reads too."""
    classifier = _classifier()
    return re.compile(rf"^(?:\d{{6,}} {classifier._PROVINCE}|\d{{4}} \d{{4}} {classifier._QUEBEC})\b")


def _sender_tokens(rest: str) -> tuple[list[tuple[str, bool]], str] | None:
    """Q4: the words of a sender printed after a rail, up to a field label, one of §5.2's sender ends or a reference
    token after a name word, generic words and single letters skipped: each word with whether it is a name word (not
    a rail, posting or layout word), and the reference printed before the name (six or more digits, or ''). None when
    the row names a recipient or a reversal.

    S4.2 fix round 4: two four-digit groups printed one after the other ('1234 5678', Quebec's hyphenated number once
    normalized) are read as one reference, both groups kept."""
    classifier = _classifier()
    tokens: list[tuple[str, bool]] = []
    number = ""
    previous = ""
    for token in rest.split():
        if token in _P2P_SENDER_END_WORDS or token in _TRANSFER_FIELD_LABEL_WORDS:
            break
        if token in _P2P_NO_SENDER_WORDS:
            return None
        if classifier._is_reference_token(token):
            if any(name for _, name in tokens):
                break
            if _FOUR_DIGITS.fullmatch(token) and _FOUR_DIGITS.fullmatch(previous):
                number = f"{previous} {token}"
            else:
                number = token if token.isdigit() and len(token) >= 6 else ""
            previous = token
            continue
        previous = ""
        if token in classifier.REVENUE_GENERIC_WORDS or len(token) < 2:
            continue
        tokens.append((token, token not in _P2P_NOT_SENDER_WORDS and token not in _P2P_LAYOUT_WORDS))
    return tokens, number


def _without_city_tail(rest: str) -> str:
    """Q4, §5.2 (S4.2 final review, fix 3): the words after a rail, cut at a wallet's city printed as the sender's
    tail: after a name word ('CASH APP*<sender>*OAKLAND CA'), or with no name word after it but a state code ('APPLE
    CASH INST XFER CUPERTINO CA'). A city followed by name words starts the sender's name and is kept ('ZELLE CREDIT
    NEW YORK FABRIKAM LLC', 'CASH APP*NEW YORK FABRIKAM LLC*OAKLAND CA', which ends at OAKLAND)."""
    for city in _P2P_WALLET_CITY.finditer(rest):
        before = _sender_tokens(rest[: city.start()])
        after = _sender_tokens(rest[city.end():])
        named_before = before is not None and any(name for _, name in before[0])
        named_after = after is not None and any(name and token not in _US_STATE_TAIL for token, name in after[0])
        if named_before or not named_after:
            return rest[: city.start()]
    return rest


def _without_state_tail(words: list[str]) -> list[str]:
    """Q4, §5.2 (S4.2 final review, M7): the sender's words without a trailing US state code printed after two words
    or more ('JOHN SMITH NY', 'FABRIKAM LLC NY'), or with no name word before it (a code alone names nobody). After a
    single name word it is the name's own ('KIM PA' and 'KIM MA' are two senders)."""
    words = list(words)
    while words and words[-1] in _US_STATE_TAIL and (
        len(words) >= 3 or all(word in _US_STATE_TAIL or word in _NOT_A_NAME_ALONE for word in words[:-1])
    ):
        words.pop()
    return words


def _holder_reading(tokens: list[tuple[str, bool]]) -> str:
    """Q4, §5.2 (S4.2 final review, M7): the sender as the holder test reads it: the name words, and each layout word
    next to one, so a layout word never defeats the holder test ('REQUEST FABRIKAM LLC' paying Request Fabrikam). A
    rail or posting word ('AUTO' of AUTO DEPOSIT, 'CASH') is never read back: a holder named with it would be held on
    every such row."""
    kept = []
    for index, (token, name) in enumerate(tokens):
        beside = [tokens[at][1] for at in (index - 1, index + 1) if 0 <= at < len(tokens)]
        if name or (token in _P2P_LAYOUT_WORDS and any(beside)):
            kept.append(token)
    return " ".join(_without_state_tail(kept))


def _read_back_legal_form(tokens: list[tuple[str, bool]]) -> str:
    """Q4, §5.2 (S4.2 final review, fix 3): a sender whose only name words are a legal form or an article, and whose
    skipped words stand right before them: those words and the form, when they read as a company form ('CASH OUT AUTO
    LLC'); '' otherwise ('RTP CREDIT 1ABC INC', 'ZELLE BUSINESS PAYMENT')."""
    names = [index for index, (_, name) in enumerate(tokens) if name]
    if not names or not all(tokens[index][0] in _NOT_A_NAME_ALONE for index in names):
        return ""
    start = names[0]
    while start > 0 and not tokens[start - 1][1]:
        start -= 1
    if start == names[0]:
        return ""
    sender = " ".join(_without_state_tail([token for token, _ in tokens[start:]]))
    return sender if _classifier().company_form(sender) else ""


def _sender_key(sender: str) -> tuple[str, ...]:
    """Q4 (S4.2 review I7): the key of a sender printed without FROM: its words (a numbered company's number kept, so
    two numbered companies are never one sender), at most the first four; the payer key of the same name printed
    after FROM (_payer_key) when it prints no number."""
    return tuple(sender.split())[:4]


def _public_named(region: str) -> bool:
    """§8.1: the payer region matches a §7.6 payer pattern or the payer-name veto (a public payer of any kind)."""
    classifier = _classifier()
    if not region:
        return False
    name = classifier._PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    return classifier._PUBLIC_PAYER_NAME.match(name) is not None or bool(
        re.search(r"(?<![A-Z])(?:DEPT OF REVENUE|DEPARTMENT OF REVENUE|TAXATION|COMPTROLLER|TREASURER|DEPT OF LABOR"
                  r"|UNEMPLOYMENT|WORKFORCE)\b", name)
    )


def _hold_text(text: str) -> str:
    """§8.1: the row before its receiver fields with the posting labels removed."""
    classifier = _classifier()
    return _HOLD_POSTING_LABELS.sub(" ", classifier._before_receiver(text))


def financing_named(text: str, region: str, entry: str, account_name: str | None) -> bool:
    """§8.1, T4: a financing root in the payer region or the entry fields (posting labels removed, and a run equal to
    the holder's whole account name removed first), or, on a row with no payer region, in the row before its
    receiver fields. A whole-word CREDIT counts only inside a payer name, next to another name word."""
    classifier = _classifier()
    holder = classifier.account_name_text(account_name)
    parts = []
    if region:
        payer = _HOLD_POSTING_LABELS.sub(" ", region)
        if len(holder.split()) >= 2:
            payer = payer.replace(holder, " ")
        parts.append(payer)
        name_words = classifier.payer_name(payer).split()
        if len(name_words) >= 2 and _WHOLE_CREDIT.search(" ".join(name_words)):
            return True
        # A3 review, rounds 2 and 3: a glued ...CRED word, on a payer's name field or a company-formed payer region.
        if (
            _prints_payer_name_field(text) or classifier.company_form(" ".join(name_words))
        ) and any(_GLUED_CRED_NAME.fullmatch(word) for word in name_words):
            return True
        # A3: a wire's sender split by a line wrap, read across the split (§7.9's wrap-tolerant reading); A3 review,
        # rounds 2 and 3: on every wire sender, labelled or not, where the two words spell a financing word.
        if classifier._is_wire_row(text) and _wrap_split_root(text, payer):
            return True
        if entry:
            parts.append(_HOLD_POSTING_LABELS.sub(" ", entry))
    else:
        row = _hold_text(text)
        if len(holder.split()) >= 2:
            row = row.replace(holder, " ")
        parts.append(row)
    return any(_FINANCING_ROOT.search(part) for part in parts)


def _prints_payer_name_field(text: str) -> bool:
    """§8.1, T4 (A3 review, round 2): the payer region is a payer's name field: a wire's sender, an ACH originator (the
    row prints DES, CO ENTRY DESCR or ORIG CO NAME) or a transfer's sender after FROM. An unlabelled row's words
    ('ACHCRED 12345678') are no name field."""
    classifier = _classifier()
    if classifier._is_wire_row(text):
        return True
    row = classifier._before_receiver(text)
    if classifier._ACH_ORIGINATOR_FIELD.search(row) is not None:
        return True
    return classifier._is_transfer_or_p2p_row(text) and bool(classifier._sender_payer_region(text))


def _wrap_split_root(text: str, payer: str) -> bool:
    """§8.1, §7.9 (A3 review, rounds 2 and 3): a financing word that a line wrap split across two of the wire sender's
    first six words (those with no digit): the two words together spell a financing word (_WRAP_FINANCING_WORDS) or a
    prefix of one of _WRAP_PREFIX_MIN letters or more, so the join falls inside it ('F INANCIAL', 'SERVICIN G', 'LO AN',
    'MORT G'). Two words that spell none never make one ('SERVICE REPAIR', 'ALLEN D', 'HELEN DE', 'CAPT L', and a
    Fedwire sender's city and state, 'GLEN DE', 'LAMORT GA'). A3-G review: no city and state skip (a company form CO is
    no state code: 'NORTHWIND F INANCIAL CO' is held)."""
    words = [token for token in payer.split() if not any(ch.isdigit() for ch in token)][:6]
    for left, right in zip(words, words[1:]):
        joined = left + right
        if joined in _WRAP_FINANCING_WORDS or (
            len(joined) >= _WRAP_PREFIX_MIN and any(word.startswith(joined) for word in _WRAP_FINANCING_WORDS)
        ):
            return True
    return False


def _accounts_payable_wording(text: str) -> bool:
    """§7.5 (S4.2 fix measurement): the payer's accounts-payable or vendor-payment wording, as _payer_remittance
    matches it before its veto: an AP pattern on the row before its receiver fields or on its joined text (PAYABLES
    never on a row that prints BILL COM), or an invoice number on a row that also prints a payment-channel word."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    joined = classifier._joined_text(row)
    for pattern in classifier._PAYER_REMITTANCE_CREDIT_PATTERNS:
        found = pattern.search(row) or pattern.search(joined)
        if found is not None and not (found.group(0) == "PAYABLES" and classifier._BILL_COM.search(row)):
            return True
    found = classifier._INVOICE_NUMBER.search(row)
    return found is not None and classifier._PAYMENT_CHANNEL_WORD.search(
        row[: found.start()] + " " + row[found.end():]
    ) is not None


def non_sale_purpose(text: str, region: str, *, bank: str | None = None) -> bool:
    """§8.1: a non-sale purpose, a public payer's refund or benefit, or a healthcare payer's member or premium credit.
    The investment words hold a row unless it prints accounts-payable wording (S4.2 fix measurement). A3 (precision
    sample): a title firm named on the payer region (_TITLE_FIRM: property-closing proceeds, an asset sale), on a
    wire or an ACH row alike, unless its purpose cites the holder's fee (_TITLE_FEE_WORDING, the orchestrator's
    ruling; A3 review: read on the purpose only, _title_purpose_text); and the holder's own currency conversion
    (_currency_conversion; `bank` is the statement's bank, whose own name names no payer)."""
    classifier = _classifier()
    row = _hold_text(text)
    claim_entry = classifier._HCCLAIMPMT.search(text) is not None
    healthcare = healthcare_payer(region)
    if _NON_SALE_PURPOSE.search(row) is not None:
        return True
    if (
        region and _TITLE_FIRM.search(region) is not None
        and _TITLE_FEE_WORDING.search(_title_purpose_text(text)) is None
    ):
        return True
    if _currency_conversion(text, bank=bank):
        return True
    if _personal_trust(text, region):
        return True
    if _INVESTMENT_PURPOSE.search(row) is not None and not _accounts_payable_wording(text):
        return True
    if _CLAIM_WORD.search(row) and not claim_entry and not (healthcare and re.search(r"(?<![A-Z])CLAIM PMT\b", row)):
        return True
    if _public_named(public_region(text)) and classifier._PUBLIC_PAYER_NON_SALE_WORDS.search(
        classifier._TREASURY_BOILERPLATE.sub(" ", text)
    ):
        return True
    # S4.2 review (I6b): a brokerage, investing or crypto-exchange platform returns the owner's own money.
    if _OWNER_MONEY_PLATFORMS.search(row) or classifier._matches_any(
        row, classifier._SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS
    ):
        return True
    return healthcare and _HEALTHCARE_MEMBER_WORDS.search(row) is not None


def _personal_trust(text: str, region: str) -> bool:
    """§8.1 (A3-G, A3-G review): the named sender is a personal trust, held as non_sale_purpose (owner money: a family's
    money, an investment or a loan far more often than a customer's purchase). Read on a wire's originator field before
    its digit cut (_wire_originator_text: 'JANE Q SAMPLE 1234 TRUST <city> <state> ...', or the sender printed right
    after the label), and on any other row's payer region. The sender prints a trust form (_PERSONAL_TRUST_WORDS) after
    one to _PERSONAL_TRUST_MAX_NAME_WORDS name words (digits, fillers and the trust adjectives aside); a plain TRUST or
    TRST with no adjective needs two name words and never reads a person-to-person row (whose sender field also prints
    the sending bank), and a bare TR needs an adjective. And all of these hold:
    (a) the trust form ends the sender's name (_trust_form_ends_the_name: 'IN GOD WE TRUST ROOFING' is no trust);
    (b) the words before it read as a person's name: no business, institutional or benefit word (_TRUST_BUSINESS_WORDS,
        the classifier's holder-noise words) and no company form;
    (c) no bank's or trust company's form after the trust word (_TRUST_COMPANY_SUFFIX: TRUST NA, FSB, BANK, COMPANY,
        CO) and no lawyer's or client trust account (_TRUST_LAWYER_WORDS: ESQ, ATTORNEY, LAW, LEGAL, IOLTA, IOTA, IOLA)."""
    classifier = _classifier()
    wire = classifier._is_wire_row(text)
    sender = (_wire_originator_text(text) or _wire_sender_after_label_text(text)) if wire else region
    tokens = sender.split()
    index = next((at for at, token in enumerate(tokens) if token in _PERSONAL_TRUST_WORDS), None)
    if index is None:
        return False
    before = [token for token in tokens[:index] if not any(ch.isdigit() for ch in token)]
    adjectives = [token for token in before if token in _PERSONAL_TRUST_ADJECTIVES]
    names = [token for token in before if token not in _PERSONAL_TRUST_ADJECTIVES and token not in _PERSONAL_TRUST_FILLERS]
    if not 1 <= len(names) <= _PERSONAL_TRUST_MAX_NAME_WORDS:
        return False
    if tokens[index] != "TTEE" and not adjectives:
        if tokens[index] == "TR" or len(names) < 2 or _channel(text) == "person_to_person":
            return False
    # (c) a trust company's or a bank's form after the trust word; a lawyer's or a client trust account.
    # A3-G re-review: the lawyer and client-trust words read across the whole sender.
    if _TRUST_COMPANY_SUFFIX.search(" ".join(tokens[index:])) or _TRUST_LAWYER_WORDS.search(" ".join(tokens)):
        return False
    # (a) the trust form ends the sender's name.
    if not _trust_form_ends_the_name(tokens[index + 1:], address=wire):
        return False
    # (b) the words before the form read as a person's name.
    return not (
        classifier.company_form(" ".join([*before, tokens[index]]))
        or any(_TRUST_BUSINESS_WORDS.search(name) or name in classifier.HOLDER_NOISE for name in names)
    )


def _trust_form_ends_the_name(tail: Sequence[str], *, address: bool) -> bool:
    """§8.1 (A3-G review, a): the words after a trust form add nothing to the sender's name: only its agreement and
    date words, dates, numbers, a PO box and the country (_TRUST_TAIL_WORDS), or, on a wire's originator field (which
    prints the sender's address after its name), an address that ends in a US state code ('... TRUST SAMPLEVILLE WA
    12345 US')."""
    classifier = _classifier()
    words = list(tail)
    if words and words[0] in _STREET_WORDS:
        # A street named TRUST ('12 TRUST RD'): the trust word is the address's, not a trust form.
        return False
    if "FBO" in words:
        # The trust's beneficiary ('... FAMILY TRUST FBO <name>') names no other sender.
        words = words[: words.index("FBO")]
    while words and (classifier._is_reference_token(words[-1]) or words[-1] in {"US", "USA"}):
        words.pop()
    if all(word in _TRUST_TAIL_WORDS or classifier._is_reference_token(word) for word in words):
        return True
    if not address or words[-1] not in _US_STATE_TAIL:
        return False
    # A3-G re-review: the address holds only place words before its state: city words (and a street or PO box), never
    # a business, lawyer, company-form, account, service, department or institution word. A3-G re-review 2: the list
    # is finite, so the address is also at most _TRUST_ADDRESS_MAX_WORDS words (_address_words). A3-G re-review 3: a
    # dotted company form ('L.L.C.', 'P.A.') prints as single letters, which the cap skips: joined, they are a form.
    if len(_address_words(words[:-1])) > _TRUST_ADDRESS_MAX_WORDS or _joined_letters_company_form(words[:-1]):
        return False
    return not any(_not_a_place_word(word) for word in words[:-1])


#: §8.1 (A3-G re-review 3): the company forms a dotted spelling joins into besides the classifier's (_BANK_COMPANY_FORM
#: has LLC, LP, INC, CO ...): a professional association and a professional corporation. Read on joined letters only:
#: a lone PA is Pennsylvania.
_DOTTED_COMPANY_FORMS = frozenset({"LP", "PA", "PC"})


def _joined_letters_company_form(words: Sequence[str]) -> bool:
    """§8.1 (A3-G re-review 3): two or more single letters in a row that join into a company form (a dotted 'L.L.C.',
    'L.P.', 'P.A.' or 'P.C.', which the normalizer prints 'L L C'). Initials that join into none keep their skip (the
    agreement's 'U A', a middle initial)."""
    classifier = _classifier()
    run: list[str] = []
    for word in [*words, ""]:
        if len(word) == 1 and word.isalpha():
            run.append(word)
            continue
        joined = "".join(run)
        if len(run) >= 2 and (joined in _DOTTED_COMPANY_FORMS or classifier._BANK_COMPANY_FORM.fullmatch(joined)):
            return True
        run = []
    return False


def _address_words(words: Sequence[str]) -> list[str]:
    """§8.1 (A3-G re-review 2): the address's own words before its state, the words the cap counts: never the
    agreement, date, PO box and country words (_TRUST_TAIL_WORDS: '... TRUST U A DTD PO BOX <n> <city>'), a number or
    a reference token (a street number, a name glued to it), a street type (_STREET_WORDS) or an initial."""
    classifier = _classifier()
    return [
        word for word in words
        if not (
            classifier._is_reference_token(word) or word in _TRUST_TAIL_WORDS or word in _STREET_WORDS
            or len(word) == 1
        )
    ]


def _not_a_place_word(word: str) -> bool:
    """§8.1 (A3-G re-review): a word no address prints before its state: a business, trade, lawyer, company-form,
    account, service, department or institution word (_TRUST_NOT_PLACE_WORDS, _TRUST_BUSINESS_WORDS,
    _TRUST_LAWYER_WORDS, the classifier's company forms). Numbers (a street or a PO box) and the agreement words
    (_TRUST_TAIL_WORDS) are place words here; the generic words are not read (a city prints NEW, as NEW YORK)."""
    classifier = _classifier()
    if (
        classifier._is_reference_token(word) or word in _TRUST_TAIL_WORDS or word in _US_STATE_TAIL
        or word in {"CITY", "COUNTY", "STATE"}
    ):
        return False
    return (
        word in _TRUST_NOT_PLACE_WORDS
        or _TRUST_BUSINESS_WORDS.search(word) is not None or _TRUST_LAWYER_WORDS.search(word) is not None
        or classifier._BANK_COMPANY_FORM.fullmatch(word) is not None
    )


def _wire_sender_after_label_text(text: str) -> str:
    """§5.2 (A3-G): the sender a wire prints right after its label (the classifier's _WIRE_SENDER_AFTER_LABEL layouts),
    up to its end (a wire field, NOTPROVIDED or WIRE PAYMENT), before the digit cut the payer region makes; '' on any
    other layout."""
    classifier = _classifier()
    found = classifier._WIRE_SENDER_AFTER_LABEL.match(text)
    if found is None:
        return ""
    rest = text[found.end():]
    end = classifier._WIRE_SENDER_AFTER_LABEL_END.search(rest)
    return (rest[: end.start()] if end is not None else rest).strip()


def _bank_originated_wire(text: str, region: str) -> bool:
    """§8.1, T4 (A3-G): a wire whose originator reads as a bank: by its own form (the classifier's
    BANK_FORM_ORIGINATOR: BANK, BANCORP, BANK N A, CREDIT UNION, SAVINGS BANK, FEDERAL SAVINGS), or equal to Bank of
    America's sending bank (SND BK) with the field's line-wrap splits read run together (the originator's letters
    start the sending bank's, or the reverse). Only the originator field (the payer region) is read, never the sending
    or receiving bank field or the text after it, and never a bank's merchant-services, bankcard or processor form
    (BANK_SETTLEMENT_ORIGINATOR), a settlement. A3-G refinement: a bank that names its customer after a relay label
    only relays; the payer region then reads the customer (relayed_customer_text), so the bank's form is held only when
    no customer prints. A3-G review: the form arm is the classifier's bank_by_form (never a food or blood bank, never a
    company whose name holds the bank word); the sending-bank arm compares the letters with spaces removed, needs
    _SENDING_BANK_MIN_LETTERS letters on the shorter side and an originator that prints no company form. A3-G
    re-review 2: both arms read CO or NV as the address's state only in its address context (the classifier's
    originator_address: a ZIP or the country code after it, or the end of a Fedwire or CHIPS B/O city and state)."""
    classifier = _classifier()
    if not region or not classifier._is_wire_row(text) or classifier.BANK_SETTLEMENT_ORIGINATOR.search(region):
        return False
    after, city_state_end = classifier.originator_address(text, region)
    if classifier.bank_by_form(region, after, city_state_end=city_state_end):
        return True
    sending = _SENDING_BANK_FIELD.search(text)
    if sending is None or classifier.company_form_outside_address(region, after, city_state_end=city_state_end):
        return False
    originator = "".join(ch for ch in classifier.payer_name(region) if ch.isalpha())
    bank = "".join(ch for ch in sending.group(1) if ch.isalpha())
    shorter = min(len(originator), len(bank))
    return shorter >= _SENDING_BANK_MIN_LETTERS and (bank.startswith(originator) or originator.startswith(bank))


def _usable_holder_name(account_name: str | None) -> bool:
    """§5.2 (A3-G refinement): the statement's account-name field names its holder: a company form, or a person's
    name (two to four words of letters, none a product, noise or generic word). A product name ('BUSINESS ADVANTAGE
    CHECKING') or an empty field names nobody."""
    classifier = _classifier()
    name = classifier.account_name_text(account_name)
    if not name:
        return False
    if classifier.company_form(name):
        return True
    words = name.split()
    return 2 <= len(words) <= 4 and all(
        word.isalpha() and word not in classifier.HOLDER_NOISE and word not in classifier.REVENUE_GENERIC_WORDS
        for word in words
    )


def _receiver_holder_names(records: Sequence[TransactionClassification], credits: Sequence[int]) -> tuple[str, ...]:
    """§5.2, §8.1 (A3-G refinement): when the statement's account-name field names nobody (_usable_holder_name), the
    holder's names its own incoming receiver fields print (INDN, IND NAME, RECEIVER NAME: an ACH credit's receiver is
    the holder), each on _RECEIVER_HOLDER_MIN_CREDITS credits or more, with _RECEIVER_HOLDER_MIN_WORDS words and
    _RECEIVER_HOLDER_MIN_LETTERS letters or more, naming no bank, and holding a word that is no product, noise or
    generic word. Read by the holder hold only (the holder's name is never a payer), never to verify anything. A3-G
    review: the credits must come from _RECEIVER_HOLDER_MIN_CREDITS distinct originators or more: a receiver constant
    across payers is the holder, while a name one platform prints (a rent platform's tenant) is its customer. A3-G
    re-review: originators are compared by the payer's first distinctive word, the word the classifier groups a payer
    by (_payer_first_distinctive_word; the payer key where it holds none), so one platform's two spellings are one
    originator ('SAMPLE RENT PAY', 'SAMPLE RENT PAYMENTS')."""
    classifier = _classifier()
    if not credits or _usable_holder_name(records[credits[0]].account_name):
        return ()
    originators: dict[str, set[str]] = {}
    for index in credits:
        text = classifier.revenue_text(records[index].normalized_description)
        region = classifier.payer_region(text)
        payer = (
            classifier._payer_first_distinctive_word(region) or " ".join(classifier._payer_key(region))
            or classifier._before_receiver(text)
        )
        for found in classifier._RECEIVER_FIELD_VALUE.finditer(records[index].normalized_description):
            value = _RECEIVER_LABEL.sub("", found.group(0), count=1)
            words = [token for token in value.split() if token.isalpha() and len(token) > 1]
            if words:
                originators.setdefault(" ".join(words), set()).add(payer)
    return tuple(
        name for name, payers in originators.items()
        if len(payers) >= _RECEIVER_HOLDER_MIN_CREDITS and len(name.split()) >= _RECEIVER_HOLDER_MIN_WORDS
        and sum(len(word) for word in name.split()) >= _RECEIVER_HOLDER_MIN_LETTERS
        and _RECEIVER_BANK_WORDS.search(name) is None
        and any(word not in classifier.HOLDER_NOISE and word not in classifier.REVENUE_GENERIC_WORDS
                for word in name.split())
    )


def _receiver_alias_reads(record: TransactionClassification, text: str) -> bool:
    """§5.2 (A3-G refinement, final): the rows a receiver-field holder name is read on: a wire (a book transfer
    included) or a transfer or person-to-person row (Zelle, Venmo, an online, mobile, book or internal transfer), where
    the holder moves its own money. Never an ACH, card, processor or marketplace settlement row (a platform prints the
    store's own name as its payer), and never a row an earlier rule verified on sale evidence (a card settlement, a
    platform payout, an accounts-payable remittance, a public payer). A3-G review: the wire is the classified wire
    layout (an incoming-wire label or a third-party book transfer, _is_wire_row), never the word WIRE printed anywhere
    ('<payer> DES:WIRE PMT' is an ACH row)."""
    classifier = _classifier()
    if record.revenue_classification == "verified_revenue":
        return False
    if classifier._is_wire_row(text):
        return True
    # A real-time or push rail also carries a platform's payout (Visa Direct, RTP): never read there.
    return _channel(text) == "person_to_person" and not classifier._PUSH_RAIL.search(classifier._before_receiver(text))


def _receiver_holder_named(payer: str, holder: str) -> bool:
    """§5.2 (A3-G refinement, narrowed variant): the payer is the holder that a receiver field names: the two names run
    together where one starts the other and the shorter keeps _RECEIVER_HOLDER_RUN_LETTERS letters (a receiver field
    and an originator field cut the same name at different widths). The broad holder test (a shared first word) is not
    read against a receiver name."""
    classifier = _classifier()
    if not payer:
        return False
    ours = "".join(ch for ch in classifier.payer_name(payer) if ch.isalpha())
    theirs = "".join(ch for ch in holder if ch.isalpha())
    shorter = min(len(ours), len(theirs))
    return shorter >= _RECEIVER_HOLDER_RUN_LETTERS and (ours.startswith(theirs) or theirs.startswith(ours))


def _title_purpose_text(text: str) -> str:
    """§8.1 (A3 review): the words a payment prints about its purpose, which the title fee exemption reads: Bank of
    America's DES field, Chase's CO ENTRY DESCR field, a wire's purpose fields (_WIRE_PURPOSE_FIELD: OBI, RMR, PMT
    DET, RFB and a URI label, never a REF field), a transfer's memo. entry_fields reads a wire's REF field too, which
    on the Fedwire layout is the sender's bank reference, never the purpose. A3 review round 2: on Santander's layout
    ('ACCT <n> <originator> REF <purpose>', _SANTANDER_WIRE) the REF field is the purpose, and is read."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    fields = [
        found.group(1) for found in (
            pattern.search(row) for pattern in (classifier._BOFA_ENTRY_FIELD, classifier._CHASE_ENTRY_FIELD)
        ) if found is not None
    ]
    santander = classifier._SANTANDER_WIRE.match(text)
    if santander is not None:
        purpose = re.match(r"\s*\bREF\b(.*)$", text[santander.end():])
        if purpose is not None:
            fields.append(purpose.group(1))
    if classifier._is_wire_row(text):
        fields.extend(found.group(1) for found in _WIRE_PURPOSE_FIELD.finditer(text))
    elif classifier._is_transfer_or_p2p_row(text):
        fields.extend(found.group(1) for found in classifier._MEMO_ENTRY_FIELD.finditer(row))
    return " ".join(field.strip() for field in fields if field.strip())


def _listed_auto_lender(text: str) -> tuple[str, str] | None:
    """§8.7: the listed auto lender the originator segment names, and the alias that named it: a vehicle_financing
    registry entity or a DEALER_FUNDING_PAYERS entry; or None."""
    classifier = _classifier()
    segment = classifier._originator_segment(text)
    known = match_known_payee(segment)
    if known is not None and known.state == "vehicle_financing":
        return known.entity, known.alias
    return registry_match(segment, DEALER_FUNDING_PAYERS)


def _dealer_funding_payer(text: str) -> str | None:
    """§8.7: the listed auto lender the originator segment names (_listed_auto_lender), or None."""
    found = _listed_auto_lender(text)
    return found[0] if found is not None else None


@dataclass(frozen=True)
class DealerFunding:
    """§6.1 step 4 (Q7): a dealer-funding credit's reading. `arm` is 'listed' or 'credit_union'; `entity` and `alias`
    are the listed lender and the alias that named it, or the credit union as its payer region prints it (both the
    same); `word` is the dealer-funding word (or the VHCL PURCH entry) the row prints (S4.3 review: a Q7 record keeps
    its lender's name, as the financing-proceeds record it replaces did)."""

    arm: str
    entity: str
    alias: str
    word: str


def _q7_refused_by_a_hold(text: str, words: str, region: str) -> bool:
    """S4.3 review (§8.1, G11): Q7 decides at step 4, before any hold of §8.1 reads the row, so it refuses a row whose
    wording one of those holds names, fail closed: the pay and personal-income words and the payroll providers (Q8,
    G11), a non-sale purpose, a possible return (an overpaid payoff refunded, an adjustment, a credit memo, a dispute),
    an insurer or claim word, and a floor-plan word (FLOOR..., WHOLESALE). Each reads as §8.1 reads it, on the row
    before its receiver fields, and again on the whole row without the receiver field's value, as the Q7 veto words
    do (a BofA PMT INFO addenda after the receiver prints the lender's own words; the holder's name never refuses).
    Such a row keeps the reading it has without Q7: a ledger lender's financing proceeds, or a held row."""
    classifier = _classifier()
    if _CARD_CREDIT_LABEL.search(text) or non_sale_purpose(text, region) or non_sale_purpose(words, region):
        return True
    for row in (classifier._before_receiver(text), words):
        hold = _HOLD_POSTING_LABELS.sub(" ", row)
        if (
            _PAY_WORDS.search(row) or classifier._is_payroll_provider_row(row) or _PERSONAL_INCOME.search(row)
            or _POSSIBLE_RETURN.search(hold)
            or _INSURER_NAME.search(hold) or _CLAIM_WORD.search(hold)
            or _DEALER_FLOOR_PLAN_WORDS.search(row)
        ):
            return True
    return False


def dealer_funding(text: str) -> str | None:
    """§6.1 step 4 (Q7): the arm of dealer_funding_reading ('listed' or 'credit_union'), or None."""
    reading = dealer_funding_reading(text)
    return reading.arm if reading is not None else None


def dealer_funding_reading(text: str) -> DealerFunding | None:
    """§6.1 step 4 (Q7), read on a credit's revenue text: arm 'listed' when a listed auto lender pays dealer-funding
    words, 'credit_union' when a credit union prints the VHCL PURCH entry (the statement pass decides it), each with
    the lender it names; or None. Never on a row that names a lender outside vehicle financing, a potential lender or
    an insurer, that prints a loan, proceeds, advance or refund word, or that the channel gate closes; nor on a row
    whose wording a hold of §8.1 names (S4.3 review: _q7_refused_by_a_hold).

    The lender is read on the originator segment without the receiver field's value, and the veto words on the whole
    row without it (S4.3, §5.2: the holder's name never names a payer, and never vetoes one; a BofA PMT INFO addenda
    after the receiver still prints the row's own words). §6 precedence (S4.3): the non-revenue rules stay first, so
    Q7 also never fires on a row the strong non-revenue rule or D1's descriptors decide, or that prints transfer
    wording (Q4: a named transfer is never Verified), and a push rail is the registry's alone (§6.1 step 9b). The
    caller keeps steps 2 and 3 ahead of it (a direction conflict and a reversal marker win) and the $1 floor (§7.0)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    # Both arms need their word (a wire's entry fields may run past the row, so the VHCL PURCH entry is looked for on
    # the whole text): a row that prints neither is refused before the slower readers run.
    if not (
        DEALER_FUNDING_WORDS.search(row) or _DEALER_PAYABLES_WORDS.search(row) or _VEHICLE_PURCHASE_ENTRY.search(text)
    ):
        return None
    words = classifier._without_receiver_value(text)
    if (
        _DEALER_FUNDING_VETO.search(words)
        or classifier.channel_gate(text) is not None
        or classifier._matches_any(words, classifier._NON_REVENUE_CREDIT_PATTERNS)
        or classifier._descriptor_proceeds(text) is not None
        or _transfer_wording(row)
    ):
        return None
    region = classifier.payer_region(text)
    if _q7_refused_by_a_hold(text, words, region):
        return None
    known = match_known_payee(text)
    if known is not None and known.state in FINANCING_STATES and known.state != "vehicle_financing":
        return None
    if registry_match(text, classifier.POTENTIAL_LENDER_ALIASES) is not None:
        return None
    if classifier._insurance_registry_match(text) is not None:
        return None
    lender = _listed_auto_lender(words)
    word = DEALER_FUNDING_WORDS.search(row) or _DEALER_PAYABLES_WORDS.search(row)
    if lender is not None and word is not None:
        return DealerFunding("listed", lender[0], lender[1], word.group(0))
    entry = _VEHICLE_PURCHASE_ENTRY.search(classifier.entry_fields(text) or row)
    if _CREDIT_UNION_PAYER.search(region) and entry is not None:
        # The credit union as its payer region prints it (§5.2: never a receiver field): no registry names it.
        return DealerFunding("credit_union", classifier.payer_name(region) or region, region, entry.group(0))
    return None


def _first_word(region: str) -> str | None:
    return _classifier()._payer_first_distinctive_word(region)


def _debit_words(records: Sequence[TransactionClassification], duplicates: set[int]) -> tuple[set[str], set[str]]:
    """The first distinctive words of the statement's posted debits (pass 6's reading, _debit_word_reading): (lender
    and financing debits, the others). The others leave out a card purchase (A1 census): buying at a merchant that
    shares the payer's word is spending, never the circular money payer_also_debited holds. A card-form debit the
    classifier names as a lender or financing payee (D8) still counts as a lender debit (§8.1)."""
    classifier = _classifier()
    lender: set[str] = set()
    other: set[str] = set()
    for index, record in enumerate(records):
        if index in duplicates or record.amount >= 0 or not record.is_posted:
            continue
        word, card_purchase = classifier._debit_word_reading(record)
        if word is None:
            continue
        if record.classification in _LENDER_DEBIT_STATES:
            lender.add(word)
        elif not card_purchase:
            other.add(word)
    return lender, other


def _channel(text: str) -> str:
    """§5.2: the channel family: wire, ach_eft, person_to_person, check, cash_branch_atm or other. A row the 5.5 wire
    vetoes read as a wire (_wire_vetoes_apply: an incoming-wire label, a third-party book transfer, or WIRE printed
    outside the receiver's value, a glued reference included) is a wire, so Q6 never reads it as an ACH payer.

    A3 (precision sample): a transfer that prints the loose wire words (§8.5: FEDWIRE, WIRE, CHIPS, SWIFT ...) and
    names no counterparty ('INCOMING FEDWIRE TRANSFER') is a wire with no sender (Q5: held as wire_no_sender); one that
    names its counterparty keeps the named-transfer reading (T13)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    if classifier._is_wire_row(text):
        return "wire"
    if _p2p_rail(row) or classifier._PUSH_RAIL.search(row):
        return "person_to_person"
    if classifier._CHECK_DEPOSIT_FORM.search(row):
        return "check"
    if (not classifier._ELECTRONIC_PAYMENT_FORM.search(row) and classifier._CASH_BRANCH_ATM_FORM.search(row)):
        return "cash_branch_atm"
    if _transfer_wording(row):
        if _TRANSFER_WIRE_WORDS.search(row) and not _transfer_counterparty_words(text):
            return "wire"
        return "person_to_person"
    if _LOOSE_WIRE.search(row) or classifier._wire_vetoes_apply(text):
        return "wire"
    if classifier._ELECTRONIC_PAYMENT_FORM.search(row):
        return "ach_eft"
    return "other"


def _p2p_rail(row: str) -> bool:
    """§8.4 in pass 7 (S4.2 follow-up 2): the row prints one of the classifier's consumer person-to-person rails
    (_CONSUMER_P2P_RAIL), a VIREMENT counting only in its Interac forms (_INTERAC_FORM)."""
    return any(
        found.group(0) != "VIREMENT" or _INTERAC_FORM.search(row) is not None
        for found in _classifier()._CONSUMER_P2P_RAIL.finditer(row)
    )


def _transfer_wording(row: str) -> bool:
    """§8.2 in pass 7 (S4.2 follow-up 2): the classifier's transfer wording, or a VIREMENT printed without an Interac
    form ('VIREMENT EN LIGNE', 'VIREMENT ENTRE COMPTES')."""
    return _classifier()._TRANSFER_WORDING.search(row) is not None or (
        _VIREMENT.search(row) is not None and _INTERAC_FORM.search(row) is None
    )


def _transfer_row(row: str) -> bool:
    """§8.2: transfer wording on a row that prints no person-to-person or push rail, which the transfer rules read (a
    counterparty, or none: transfer_no_counterparty)."""
    return _transfer_wording(row) and not _p2p_rail(row) and _classifier()._PUSH_RAIL.search(row) is None


def _own_words(record: TransactionClassification, text: str) -> set[str]:
    """§7.0: the holder's own words, as the recurrence veto reads them on a store-name platform: the account name's
    distinctive words and the name the bank prints in the receiver field (a delivery platform prints the merchant's
    store there). On every other source there are none (S2.4 review: a veto word always vetoes there)."""
    classifier = _classifier()
    if record.revenue_canonical_entity not in classifier._STORE_NAME_PAYOUT_ENTITIES:
        return set()
    own = set(classifier.holder_words(record.account_name))
    for found in classifier._RECEIVER_FIELD_VALUE.finditer(text):
        own.update(classifier._distinctive_words(found.group(0).split()[1:]))
    return own


def _own_word(word: str, own: set[str]) -> bool:
    """§7.0: a word of four letters or more that is one of the holder's own words or the start of one."""
    return len(word) >= 4 and any(mine == word or mine.startswith(word) for mine in own)


def registry_financing(record: TransactionClassification, text: str) -> bool:
    """§8.1 (review C2): a registry row whose row before its receiver fields prints a financing word, the holder's own
    words aside on a store-name platform (§7.0, S2.4 review) and FUNDING aside on the settlements of the three
    platforms §7.0 names. Such a row is not claimed by the registry: it is held as financing_named_payer."""
    if record.revenue_match_method not in _REGISTRY_METHODS:
        return False
    classifier = _classifier()
    own = _own_words(record, text)
    for found in _REGISTRY_FINANCING_WORDS.finditer(classifier._before_receiver(text)):
        word = found.group(0)
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in classifier._FUNDING_SETTLEMENT_ENTITIES:
            continue
        return True
    return False


def _payout_entity(text: str) -> PayeeMatch | None:
    """§8.9: the payout-credit entity (PAYOUT_CREDIT_ENTITIES) the row names, read without the receiver field's value
    (§5.2: the holder's name never names a payer, as the 5.5 readers read the operating alias); or None."""
    known = match_known_payee(_classifier()._without_receiver_value(text))
    return known if known is not None and known.entity in PAYOUT_CREDIT_ENTITIES else None


def _claimed(record: TransactionClassification, text: str) -> bool:
    """§8.1, §8.9: the operating registry, a payout-credit entity or a factoring payee claimed the row. A registry row
    that prints a financing word is not claimed (review C2)."""
    if record.revenue_match_method in _REGISTRY_METHODS:
        return not registry_financing(record, text)
    if record.classification == "factoring":
        return True
    return _payout_entity(text) is not None


def _transfer_counterparty_words(text: str) -> list[str]:
    """§8.2: the payer words a transfer prints once template prefixes, generic words, account words and reference
    tokens are removed. S4.2 review (I2): the ACH field labels, SEC codes and reference labels are removed with the
    reference printed after them, letters only or not ('REF IBEABCD'), and what is left is read as S2.3 reads a
    transfer's originator (_originator_payer_words), so an account description ('FROM HELOC', 'FROM TAX RESERVE',
    'FROM OPERATING') is never a counterparty. S4.2 re-review (fix 4): failing that, a short or company-formed name
    after FROM is one (_short_or_formed_counterparty). S4.2 follow-up 2: the French transfer and posting words
    (_VIREMENT_TRANSFER_WORDS) are removed too. S4.2 final review (fix 5): so are a French month and a bank branch.
    S4.2 fix round 4: a French month only where a date prints it (_without_date_months), on the row's start too.
    A3 (precision sample): a wire's channel and layout words (_WIRE_LAYOUT_WORDS: 'INCOMING FEDWIRE TRANSFER') and
    currency-conversion wording (_CURRENCY_CONVERSION: 'ONLINE BANKING FOREIGN EXCHANGE') are never a counterparty."""
    classifier = _classifier()
    row = _TRANSFER_REFERENCE_VALUE.sub(" ", _BANK_BRANCH_WORDS.sub(" ", _without_date_months(
        _without_currency_conversion(classifier._strip_revenue_template(classifier._before_receiver(text))), row=True
    )))
    words = [
        token for token in row.split()
        if classifier._is_payer_word(token) and not classifier._is_reference_token(token)
        and token not in _ACCOUNT_WORDS and token not in _TRANSFER_FIELD_LABEL_WORDS
        and not classifier._TRANSFER_WORDING.fullmatch(token) and token not in _VIREMENT_TRANSFER_WORDS
        and token not in {"TRANSFER", "TRNSFR", "XFER", "TFR", "BR", "TO", "BANKING", "INTERNET"}
        and token not in _WIRE_LAYOUT_WORDS
    ]
    return classifier._originator_payer_words(" ".join(words)) or _short_or_formed_counterparty(text)


#: §8.2 (S4.2 re-review fix 4): the HOLDER_NOISE words that describe one of the holder's own accounts or a bank
#: product, never a counterparty's name (a company's name words such as AMERICAN, NATIONAL, HOLDINGS are kept).
_ACCOUNT_DESCRIPTION_WORDS = frozenset({
    "BUSINESS", "PLATINUM", "COMPLETE", "ANALYZED", "COMMERCIAL", "ADVANTAGE", "FUNDAMENTALS", "SIMPLE", "BASIC",
    "PREFERRED", "INTEREST", "OPERATING", "PERFORMANCE", "SELECT", "ESSENTIALS", "CHECK", "TOTAL", "PREMIUM", "SMALL",
    "STANDARD", "FREE", "PLUS", "ELITE", "COMPTE", "DIVERS", "ENTREPRISE", "AFFAIRES", "OPERATIONS", "BANK", "BANQUE",
    "CAISSE", "CU", "FCU", "DBA",
})


def _short_or_formed_counterparty(text: str) -> list[str]:
    """§8.2, T13 (S4.2 re-review fix 4): a counterparty printed after FROM that the distinctive-word reading drops: two
    name words of any length ('LI WU', 'LE VU'), or a company form ('JD LLC', 'AMERICAN NATIONAL INC', 'USA HOLDINGS
    LLC'). Read on the sender after FROM (the payer region, cut at §5.2's sender ends), without field labels, reference
    labels and their values, reference tokens, generic words, transfer words, account and product words and single
    letters (payer_name drops those too); the name words also leave out HOLDER_NOISE. An account description or a
    field label after FROM ('FROM OPERATING LLC', 'FROM NAME COMPANY LLC') is still no counterparty. [] otherwise.

    S4.2 final review (fix 2): on a row that prints no FROM, the company form is read on the words after the transfer
    wording (_after_transfer_wording), so a company, a numbered one included, is a counterparty with or without FROM
    ('VIREMENT RECU 1234567 QUEBEC INC', 'ONLINE TRANSFER 1234567 ONTARIO INC'): counted and flagged, never verified
    (§19 OQ3), under T13's two holds (S4.2 fix round 5, _named_transfer_sender)."""
    classifier = _classifier()
    if re.search(r"\bFROM\b", classifier._before_receiver(text)) is None:
        tokens = _counterparty_tokens(_after_transfer_wording(text))
        return tokens if tokens and classifier.company_form(" ".join(tokens)) else []
    tokens = _counterparty_tokens(classifier._sender_payer_region(text))
    names = [token for token in tokens if token not in classifier.HOLDER_NOISE]
    if len(names) >= 2 or (tokens and classifier.company_form(" ".join(tokens))):
        return tokens
    return []


def _counterparty_tokens(words: str) -> list[str]:
    """§8.2 (S4.2 re-review fix 4): a transfer sender's words without bank branches, reference labels and their
    values, reference tokens, field labels, generic words, account and product words, transfer words, French months
    printed as a date (S4.2 fix round 4, _without_date_months) and single letters. A3: nor a wire's channel and layout
    words, nor currency-conversion wording."""
    classifier = _classifier()
    sender = _TRANSFER_REFERENCE_VALUE.sub(" ", _BANK_BRANCH_WORDS.sub(" ", _without_date_months(
        _without_currency_conversion(words)
    )))
    return [
        token for token in classifier._INTERNAL_ACCOUNT_SOURCE_WORDS.sub(" ", sender).split()
        if len(token) > 1 and not classifier._is_reference_token(token)
        and token not in _TRANSFER_FIELD_LABEL_WORDS and token not in classifier.REVENUE_GENERIC_WORDS
        and token not in _ACCOUNT_WORDS and token not in classifier._OWN_ACCOUNT_PRODUCT_WORDS
        and token not in _ACCOUNT_DESCRIPTION_WORDS and not classifier._TRANSFER_WORDING.fullmatch(token)
        and token not in _VIREMENT_TRANSFER_WORDS and token not in _WIRE_LAYOUT_WORDS
    ]


def _without_currency_conversion(words: str) -> str:
    """§8.1, §8.2 (A3): the words without currency-conversion wording, which never names a counterparty."""
    return _CURRENCY_CONVERSION.sub(" ", words)


def _currency_conversion(text: str, *, bank: str | None = None) -> bool:
    """§8.1 (A3, precision sample): the holder's own currency conversion: currency-conversion wording on the row
    before its receiver fields (posting labels removed), on a row that names no payer once that wording is removed:
    no name word in its payer region (_counterparty_tokens), no transfer counterparty and no person-to-person sender.
    A named payer that prints the wording (a customer's wire converted on arrival, 'ORIG FABRIKAM GMBH ... FOREIGN
    EXCHANGE') keeps its reading. The standing rule (owner money never becomes revenue) holds it as non_sale_purpose:
    §5.3's own-money reason, as a SWEEP or a ZBA is held; it names no counterparty and designates no account, so it
    is no named transfer of T13 (transfer_account_designation).

    A3 review: the statement's bank (`bank`) printing its own name right before the wording names no payer
    (_statement_bank_before_conversion: 'ROYAL FOREIGN EXCHANGE DEPOSIT' on a Royal Bank of Canada statement); a named
    currency-exchange company does (_named_currency_company: 'CURRENCY EXCHANGE INTERNATIONAL DES:PAYMENT'). A3 review
    round 3: a legal form or an article alone beside the wording names nobody (_NOT_A_NAME_ALONE, the person-to-person
    reader's rule), so a legal form names a currency company only on an originator field ('FX CONVERSION LLC <n>' and
    BMO's 'INCOMING WIRE PAYMENT ... CA FOREIGN EXCHANGE LTD' stay held)."""
    classifier = _classifier()
    if _CURRENCY_CONVERSION.search(_hold_text(text)) is None:
        return False
    own_bank = _statement_bank_before_conversion(bank) if bank else None
    if own_bank is not None:
        text = own_bank.sub(" ", text)
    if _named_currency_company(text):
        return False
    stripped = _without_currency_conversion(text)
    tokens = _counterparty_tokens(classifier.payer_region(stripped))
    if any(token not in _NOT_A_NAME_ALONE for token in tokens):
        return False
    if _transfer_row(classifier._before_receiver(stripped)) and _transfer_counterparty_words(stripped):
        return False
    return not _p2p_sender_region(stripped)


@cache
def _statement_bank_before_conversion(bank: str) -> re.Pattern[str] | None:
    """§8.1 (A3 review): the statement's bank's own name printed right before currency-conversion wording: its whole
    normalized name, and the short forms it prints (the registry's STATEMENT_BANK_PRINTED_NAMES, read when the bank
    field contains one of the entry's bank words). None when the bank field normalizes to nothing."""
    classifier = _classifier()
    field = classifier.normalize_transaction_description(bank).strip().upper()
    forms = {field}
    for markers, printed in STATEMENT_BANK_PRINTED_NAMES:
        # A3 review round 2: the bank field names the bank by containment (whole words, any case), not exact spelling.
        if any(re.search(r"(?<![A-Z])" + re.escape(marker) + r"(?![A-Z])", field) for marker in markers):
            forms.update(printed)
    forms.discard("")
    if not forms:
        return None
    names = "|".join(re.escape(form) for form in sorted(forms, key=len, reverse=True))
    return re.compile(r"(?<![A-Z])(?:" + names + r") (?=" + _CURRENCY_CONVERSION.pattern + ")")


def _named_currency_company(text: str) -> bool:
    """§8.1 (A3 review, round 2): a named currency-exchange company: an originator field names it (an ACH originator,
    the name before DES or CO ENTRY DESCR, or after ORIG CO NAME; or a wire's labelled sender, _wire_originator_run),
    and that name prints the wording with a company form beside it (_CURRENCY_COMPANY_WORDS: LLC, INC, CORP, CO, LTD,
    INTERNATIONAL or INTL). A row with no originator field names no company this way ('INTL FOREIGN EXCHANGE DEPOSIT'
    stays the holder's own conversion). Any other name word beside the wording already names the payer, on any row
    (_counterparty_tokens)."""
    classifier = _classifier()
    if classifier._is_wire_row(text):
        if classifier._wire_originator_run(text) is None:
            return False
    elif classifier._ACH_ORIGINATOR_FIELD.search(classifier._before_receiver(text)) is None:
        return False
    region = classifier.payer_region(text)
    if not region or _CURRENCY_CONVERSION.search(region) is None:
        return False
    return any(token in _CURRENCY_COMPANY_WORDS for token in _without_currency_conversion(region).split())


def _without_date_months(words: str, *, row: bool = False) -> str:
    """§8.2 (S4.2 fix round 4): the words without a French month printed as a date: beside a day number ('02 JUIN',
    'JUIN 02'; glued, '02JUIN' is a reference token already) or, read on the row itself (`row`), at its start (after
    a leading date's digits only) before the transfer wording ('JANV VIREMENT PAR BANQUE EN DIRECT <n>'). A month word
    anywhere else is a name's ('TRANSFER FROM MARS INC', 'ONLINE TRANSFER FROM MAI LE')."""
    classifier = _classifier()
    tokens = words.split()
    kept = []
    for index, token in enumerate(tokens):
        if token in _FRENCH_MONTHS:
            beside_day = any(
                _DAY_NUMBER.fullmatch(tokens[at]) for at in (index - 1, index + 1) if 0 <= at < len(tokens)
            )
            rest = " ".join(tokens[index + 1:])
            leading = row and all(classifier._is_reference_token(before) for before in tokens[:index]) and (
                classifier._TRANSFER_WORDING.search(rest) is not None or _VIREMENT.search(rest) is not None
            )
            if beside_day or leading:
                continue
        kept.append(token)
    return " ".join(kept)


def _after_transfer_wording(text: str) -> str:
    """§8.2 (S4.2 final review, fix 2): the words a transfer printed without FROM prints after its first transfer
    wording (the classifier's, or a VIREMENT), before its receiver fields and up to TO (a recipient)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    found = [match for match in (classifier._TRANSFER_WORDING.search(row), _VIREMENT.search(row)) if match is not None]
    if not found:
        return ""
    rest = row[min(found, key=lambda match: match.start()).end():]
    return re.split(r"\bTO\b", rest, maxsplit=1)[0]


#: T13 (S4.2 fix round 5): a numbered company's number printed right before its name: six or more digits, or Quebec's
#: two four-digit groups.
_NUMBER_BEFORE_NAME = re.compile(r"(?:^|\s)(\d{6,}|\d{4} \d{4})\s*$")


def _named_transfer_sender(text: str) -> str:
    """T13, §8.2 (S4.2 fix round 5): the counterparty of a named transfer printed without FROM, read for the two holds
    a counted named transfer stays under (the holder test and the round-sum repeat's key), as the FROM form's payer
    region is read: the words after the transfer wording, up to TO (_after_transfer_wording), from the first word the
    company-form arm keeps (_counterparty_tokens) up to a reference token or one of §5.2's sender ends, read as that
    arm reads them. A numbered company's number printed right before the name is kept on §5.2's province arm
    (_numbered_province_sender), so the holder test reads its digit run and two numbered companies are two senders
    ('ONLINE TRANSFER 1234567 ONTARIO INC', 'ONLINE BANKING TRANSFER 1234-5678 QUEBEC INC'). '' when no word is kept."""
    classifier = _classifier()
    words = _after_transfer_wording(text)
    tokens = _counterparty_tokens(words)
    if not tokens:
        return ""
    first = re.search(rf"(?<!\S){re.escape(tokens[0])}(?!\S)", words)
    if first is None:
        return ""
    rest = classifier._leading_name_words(words[first.start():])
    end = classifier._SENDER_END.search(rest)
    names = _counterparty_tokens(rest[: end.start()] if end is not None else rest)
    number = _NUMBER_BEFORE_NAME.search(words[: first.start()])
    if names and number is not None and _numbered_province_sender().match(" ".join([number.group(1), *names])):
        return " ".join([number.group(1), *names])
    return " ".join(names)


def credit_facts(
    record: TransactionClassification,
    text: str,
    *,
    lender_words: set[str],
    debit_words: set[str],
    receiver_holders: tuple[str, ...] = (),
) -> CreditFacts:
    """§8.1 to §8.9: one posted credit's payer facts, including the first hold of §8.10's order 2 to 11. The payer
    region, name, key and entry fields are the 5.5 readers' (payer_region, payer_name, _payer_key, entry_fields). A
    person-to-person sender printed without FROM (S4.2 review I7) is read after its rail for Q4's two holds only: the
    holder test and the round-sum repeat (its key). So is the counterparty of a named transfer printed without FROM
    (T13, S4.2 fix round 5: _named_transfer_sender), which the FROM form's payer region reads. Every other hold reads
    the payer region, so such a row's financing root is still read on the whole row. A3-G refinement: on the wire
    channel a region of bare channel words (_BARE_CHANNEL_WORDS: 'WIRE') names no sender; `receiver_holders` are the
    holder's names the statement's own receiver fields print (_receiver_holder_names), read by the holder hold only."""
    classifier = _classifier()
    channel = _channel(text)
    region = classifier.payer_region(text)
    if channel == "wire" and region and all(token in _BARE_CHANNEL_WORDS for token in region.split()):
        region = ""
    sender, holder_sender = (
        _p2p_sender_readings(text) if not region and channel == "person_to_person" else ("", "")
    )
    name = classifier.payer_name(region)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    claimed = _claimed(record, text)
    wire_n1 = classifier._is_wire_row(text)
    # §8.5 (S4.2 review M2): Q5 reads a healthcare payer on an incoming wire too; Q6 on an electronic-payment form.
    healthcare = healthcare_payer(region) and (wire_n1 or bool(classifier._ELECTRONIC_PAYMENT_FORM.search(row)))
    public = government_payer(public_region(text))
    transfer_words = _transfer_counterparty_words(text) if channel == "person_to_person" else []
    transfer_row = _transfer_row(row)
    if not region and not sender and transfer_row and transfer_words and re.search(r"\bFROM\b", row) is None:
        # T13 (S4.2 fix round 5): a named transfer printed without FROM takes the same two holds.
        sender = holder_sender = _named_transfer_sender(text)
    hold = _first_hold(
        record, text, region=region, entry=entry, claimed=claimed, lender_words=lender_words,
        debit_words=debit_words, sender=sender, holder_sender=holder_sender, receiver_holders=receiver_holders,
    )
    return CreditFacts(
        channel=channel,
        region=region,
        name=name,
        key=classifier._payer_key(region) if region else _sender_key(sender),
        entry=entry,
        hold=hold,
        claimed=claimed,
        wire_n1=wire_n1,
        company_form=classifier.company_form(name),
        public_or_healthcare=public or healthcare,
        healthcare=healthcare,
        numbered=classifier.numbered_company(text, region),
        electronic=classifier._ELECTRONIC_PAYMENT_FORM.search(row) is not None,
        # An investment word an accounts-payable row spared from the holds (S4.2 fix measurement) is no proof either:
        # §7.5's remittance veto reads it, so Q5 and Q6 never verify the row.
        refused_word=bool(
            _VERIFICATION_ONLY.search(entry) or _VERIFICATION_ONLY.search(region)
            or _ENTRY_VERIFICATION_ONLY.search(entry) or _INVESTMENT_PURPOSE.search(row)
        ),
        round_sum=classifier.is_round_sum(record.amount),
        consumer_entry=_CONSUMER_ENTRY.search(text) is not None,
        transfer_no_counterparty=transfer_row and not transfer_words,
        account_designation=transfer_row and bool(transfer_words) and _ACCOUNT_DESIGNATION.search(row) is not None,
    )


def _first_hold(
    record: TransactionClassification,
    text: str,
    *,
    region: str,
    entry: str,
    claimed: bool,
    lender_words: set[str],
    debit_words: set[str],
    sender: str = "",
    holder_sender: str = "",
    receiver_holders: tuple[str, ...] = (),
) -> str | None:
    """§8.1 in §8.10's order (2 to 11): the first hold that names the row, or None. A row the registry, a payout
    entity or a factoring payee claimed takes only the insurer, possible-return, pay and benefit holds; a registry row
    that prints a financing word is held as financing_named_payer (review C2). The holder test also reads a
    person-to-person sender printed without FROM (`sender`, Q4; S4.2 review I7), and its holder-test reading, which
    keeps a layout word inside the name (`holder_sender`, S4.2 final review M7); or a named transfer's counterparty
    printed without FROM (T13, S4.2 fix round 5), both readings one."""
    classifier = _classifier()
    row = _hold_text(text)
    if record.revenue_match_method == "insurer_customer_payment":
        return "insurer_payer"
    claim_entry = classifier._HCCLAIMPMT.search(text) is not None
    if not claimed and region and (
        _INSURER_NAME.search(region)
        or (_CLAIM_WORD.search(region) and not claim_entry and not healthcare_payer(region))
    ):
        return "insurer_named_payer"
    if record.revenue_match_method != "reversal_cancellation_exclusion" and (
        _POSSIBLE_RETURN.search(row)
        or (_CARD_CREDIT_LABEL.search(text) and record.revenue_classification != "verified_revenue")
    ):
        return "possible_return"
    if not claimed and (
        financing_named(text, region, entry, record.account_name)
        or registry_financing(record, text)
        # §8.7: a listed lender's or a dealer-funding word's row that Q7 did not verify, and a lone credit union's.
        or (_dealer_funding_payer(text) is not None and record.revenue_match_method != "auto_lender_dealer_funding")
        or (DEALER_FUNDING_WORDS.search(row) and record.revenue_match_method != "auto_lender_dealer_funding")
        or record.revenue_match_method == "credit_union_vehicle_purchase"
        # A3-G: a wire a bank originates on its own behalf.
        or _bank_originated_wire(text, region)
    ):
        return "financing_named_payer"
    word = _first_word(region) if region else None
    if not claimed and word is not None and word in lender_words:
        return "payer_debited_as_lender"
    if not claimed and (region or sender) and (
        classifier.holder_named(region or sender, record.account_name)
        or (not region and holder_sender != sender and classifier.holder_named(holder_sender, record.account_name))
        # A3-G refinement: the holder's names the statement's own receiver fields print (the hold only), on a wire, a
        # book transfer or a transfer or person-to-person row that no earlier rule verified (_receiver_alias_reads).
        or (
            receiver_holders and _receiver_alias_reads(record, text)
            and any(_receiver_holder_named(region or sender, holder) for holder in receiver_holders)
        )
    ):
        return "holder_name"
    if _PAY_WORDS.search(classifier._before_receiver(text)) or classifier._is_payroll_provider_row(
        classifier._before_receiver(text)
    ):
        return "payroll_or_salary"
    if _PERSONAL_INCOME.search(classifier._before_receiver(text)):
        return "personal_income"
    if not claimed and non_sale_purpose(text, region, bank=record.bank):
        return "non_sale_purpose"
    if not claimed and (
        record.revenue_match_method == "payer_remittance_with_counter_debit"
        or (word is not None and word in debit_words)
    ):
        return "payer_also_debited"
    # §7.0, §7.8, §8.10 (S4.2 review I3; S4.4/S4.5 review): the $1 floor is absolute. A posted credit under $1 is never
    # verified and never counted, whichever rule read it, claimed or not: an unverified one that no earlier hold names
    # is held here, and one a rule verified is held by the pass's last step (_held_by_the_floor).
    if _under_micro_floor(record):
        return _MICRO_DEPOSIT_REASON
    return None


#: §7.0, §8.10 (S4.2 review I3): the reason a credit under the $1 floor is held with. An account-verification entry is
#: not a sale (T5), so it is non_sale_purpose: §5.3's table has no micro-deposit code (S4.2 re-review: the nearest
#: reason; a code of its own would be a change to the table).
_MICRO_DEPOSIT_REASON = "non_sale_purpose"


def _under_micro_floor(record: TransactionClassification) -> bool:
    """§7.0 (S4.2 review I3): a credit under the absolute micro-deposit floor ($1, _MICRO_DEPOSIT_FLOOR)."""
    return record.amount < _classifier()._MICRO_DEPOSIT_FLOOR


def _held_by_the_floor(record: TransactionClassification) -> TransactionClassification:
    """§7.0, §7.8, §8.10 (S4.4/S4.5 review): a tiered credit under the $1 floor that a rule verified or counted, held
    for review with the floor's reason (_MICRO_DEPOSIT_REASON). A verified one leaves verification as a new first
    state (unverified_deposit, method micro_deposit_floor, pending review, so the analyst may confirm it); its reason
    names the rule the floor overruled, for the audit."""
    if record.revenue_classification == "verified_revenue":
        record = _classifier()._replace_revenue_state(
            record,
            "unverified_deposit",
            match_method="micro_deposit_floor",
            matched_rule="credit_under_micro_deposit_floor",
            confidence_score=0.40,
            reason=(
                "A credit under $1 is never verified and never counted (the absolute micro-deposit floor): the rule "
                f"that read it ({record.revenue_match_method}) is overruled, and it is held for review."
            ),
            context_signals=(*record.revenue_context_signals, "micro_deposit_floor"),
            related_transaction=record.revenue_related_transaction,
        )
    return _with_tier(record, "excluded_pending_review", _MICRO_DEPOSIT_REASON)


def _left_to_its_family(text: str) -> bool:
    """§7.1 to §7.3, §7.8 (S4.2 review I5): a row a family rule decides alone, which Q5 and Q6 never verify: the
    operating registry names an entity on it (an alias or its cut, read with the receiver field's value removed, or a
    payout form; whether or not the registry's read was vetoed or named a source, so an auction wire, a transport
    marketplace's wallet or wire credit and a TikTok row that is not ACH-shaped stay with their own rules), or it
    prints the NET SETTLE card form (§7.1: its refusal on law, trust, escrow, title and claims firms, and its
    three-credit count). A waiting processor's bare word (BRAINTREE, SMARTTAB) is no operating-registry alias, so it
    never takes a row from Q5 or Q6 (S4.2 re-review fix 2: 'BRAINTREE PLUMBING LLC' is a payer like any other)."""
    classifier = _classifier()
    alias_text = classifier._without_receiver_value(text)
    if registry_match(alias_text, OPERATING_REVENUE_READ_ALIASES) is not None:
        return True
    row = classifier._before_receiver(text)
    joined = classifier._joined_text(row)
    if any(pattern.search(row) or pattern.search(joined) for _, _, pattern in classifier._PAYOUT_FORMS):
        return True
    return _NET_SETTLE_FORM.search(row) is not None or _NET_SETTLE_FORM.search(joined) is not None


def _deferred_source(text: str, facts: CreditFacts) -> bool:
    """§15, §19 OQ4 (S4.2 review I6a): a payer of the deferred family items, counted and flagged until the owner
    rules: read with the receiver field's value removed, and a healthcare payer's bare X12 trace with no entry (an
    ACH or EFT shape: a wire's own TRN field is no X12 trace)."""
    classifier = _classifier()
    if _SECTION_15_DEFERRED_PAYERS.search(classifier._without_receiver_value(text)):
        return True
    return (
        facts.channel != "wire" and healthcare_payer(facts.region) and not facts.entry
        and _BARE_X12_TRACE.search(text) is not None
    )


def _never_q5_or_q6(record: TransactionClassification, text: str, facts: CreditFacts) -> bool:
    """The rows Q5 and Q6 never verify and never count toward a repeat, whatever their holds: a direction conflict
    (§6.1 step 2, §7.0: never lifted by any pass; S4.2 review C1), a credit under $1 (§7.0, review I3), a row a family
    rule decides alone (review I5) and a deferred source (review I6a)."""
    return (
        record.revenue_match_method == "direction_conflict"
        or not record.direction_consistent
        or _under_micro_floor(record)
        or _left_to_its_family(text)
        or _deferred_source(text, facts)
    )


def _wire_verifies(record: TransactionClassification, text: str, facts: CreditFacts, repeats: int) -> bool:
    """§8.5 (Q5): the same company wires twice or more, and the row passes every veto of §7.9 (the 5.5 reader,
    _wire_vetoed: a non-sale purpose, a financing root, any known payee, the own account, a brand-word affiliate, a cut
    financing originator, a title or escrow firm). The holder test is read here too, so a row the holds skip (one the
    registry claimed) never verifies from the holder's name (§6 precedence: Q5 never verifies a row the holder test
    or the numbered-company guard matches)."""
    classifier = _classifier()
    if not facts.wire_n1 or facts.hold is not None or not facts.region or facts.numbered:
        return False
    if classifier.holder_named(facts.region, record.account_name):
        return False
    if classifier.channel_gate(text) is not None:
        return False
    if not (facts.company_form or facts.public_or_healthcare) or repeats < 2:
        return False
    if _BANK_OR_TITLE_SENDER.search(facts.name) or facts.refused_word:
        return False
    return not classifier._wire_vetoed(text, facts.region, record.account_name)


def _q6_method(facts: CreditFacts, repeats: int, all_consumer: bool) -> str | None:
    """§8.6 (Q6): the verifying method of an eligible named ACH or EFT payer, or None. A PPD or WEB entry never
    verifies by repetition alone (a) or by its company form (b, review I6), and neither does a bank or a title or
    escrow firm's company form (§8.5's senders)."""
    if repeats >= 2 and not all_consumer:
        return "named_payer_repeats"
    if facts.company_form and not facts.consumer_entry and not _BANK_OR_TITLE_SENDER.search(facts.name):
        return "named_payer_company_form"
    if facts.public_or_healthcare:
        return "public_or_healthcare_payer"
    return None


def _q6_eligible(record: TransactionClassification, text: str, facts: CreditFacts) -> bool:
    """§8.6: an unverified posted credit with an electronic-payment form and a payer region, which the channel gate
    leaves open, no transfer wording in its entry fields, no wire, no registry, payout or factoring claim, no hold,
    and no numbered company."""
    classifier = _classifier()
    return (
        facts.electronic and bool(facts.region) and facts.channel == "ach_eft"
        and classifier.channel_gate(text) is None
        and not classifier._TRANSFER_WORDING.search(facts.entry)
        and not facts.wire_n1 and not facts.claimed and facts.hold is None and not facts.numbered
    )


def _tier_reason(
    record: TransactionClassification, text: str, facts: CreditFacts, round_repeat: bool, deferred: bool = False,
) -> tuple[str, str]:
    """§8.10: the tier and reason of an unverified posted credit, in order. A deferred source (§15, `deferred`) on a
    wire or an ACH or EFT row is a named payer Q5 and Q6 refuse as proof, as a verification-only word refuses one:
    named_payer_purpose_refused (S4.2 re-review), never "One-off payer" (a deferred source often repeats). On a row
    with no electronic-payment form it keeps named_payer_unlabelled: Q6 never reads such a row, deferred or not."""
    classifier = _classifier()
    if record.revenue_match_method == "direction_conflict":
        return "excluded_pending_review", "direction_conflict"
    if facts.hold is not None:
        return "excluded_pending_review", facts.hold
    if facts.channel == "wire" and not facts.claimed:
        if not facts.region:
            return "excluded_pending_review", "wire_no_sender"
        if facts.refused_word or deferred:
            return "counted_flagged", "named_payer_purpose_refused"
        return "counted_flagged", "wire_named_sender"
    if facts.transfer_no_counterparty and not facts.claimed:
        return "excluded_pending_review", "transfer_no_counterparty"
    if facts.account_designation and not facts.claimed:
        return "excluded_pending_review", "transfer_account_designation"
    if facts.channel == "check":
        return "counted_flagged", "check_deposit"
    if facts.channel == "cash_branch_atm":
        return "counted_flagged", "no_payer_printed"
    if facts.channel == "person_to_person" and not facts.claimed:
        return ("excluded_pending_review", "p2p_round_repeat") if round_repeat else ("counted_flagged", "p2p")
    if record.revenue_match_method in _REGISTRY_METHODS:
        return "counted_flagged", "platform_unconfirmed"
    if record.classification == "factoring":
        return "counted_flagged", "factoring_payout"
    if _payout_entity(text) is not None:
        return "counted_flagged", "payout_credit_entity"
    if facts.numbered:
        return "counted_flagged", "numbered_company_payer"
    if facts.region and (facts.refused_word or (deferred and facts.electronic)):
        return "counted_flagged", "named_payer_purpose_refused"
    if facts.region and facts.electronic:
        return "counted_flagged", "named_payer_one_off"
    if facts.region and not classifier._is_bare_row(text):
        return "counted_flagged", "named_payer_unlabelled"
    return "counted_flagged", "no_payer_printed"


def _with_tier(record: TransactionClassification, tier: str, reason: str | None) -> TransactionClassification:
    """A record with its 5.6 tier, initial tier, reason and contribution flags. The review flag is set for a held
    row only; a counted row is reviewable, not required."""
    return replace(
        record,
        revenue_tier=tier,
        revenue_initial_tier=tier,
        revenue_tier_reason=reason,
        revenue_review_required=tier == "excluded_pending_review",
        **revenue_contribution_flags(record.revenue_classification, tier),
    )


def _verify(record: TransactionClassification, method: str, reason: str, confidence: float) -> TransactionClassification:
    classifier = _classifier()
    return classifier._replace_revenue_state(
        record,
        "verified_revenue",
        match_method=method,
        matched_rule=f"verified_{method}",
        confidence_score=confidence,
        reason=reason,
        context_signals=(*record.revenue_context_signals, method),
    )


def apply_true_revenue_pass(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 7 (§6.2): payer facts, Q7's credit-union arm, the Q5 and Q6 verifications, then the tiers."""
    classifier = _classifier()
    updated = list(records)
    credits = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount > 0 and record.is_posted
        and record.revenue_classification is not None
    ]
    # §8.7: the credit-union arm needs two or more such credits in the statement. Step 4 gives the method only to a
    # credit of $1 or more whose direction agrees; the pass reads both again (§7.0: never lifted, never counted).
    union_rows = [
        index for index in credits
        if records[index].revenue_match_method == "credit_union_vehicle_purchase"
        and records[index].revenue_classification == "unverified_deposit"
        and records[index].direction_consistent and not _under_micro_floor(records[index])
    ]
    if len(union_rows) >= CREDIT_UNION_DEALER_MIN_CREDITS:
        for index in union_rows:
            record = updated[index]
            # S4.3 review: the reason names the credit union step 4 read (its revenue entity and alias stay); the
            # count is the statement's, across credit unions (§8.7).
            updated[index] = replace(
                _verify(record, "auto_lender_dealer_funding",
                        f"Credit union '{record.revenue_canonical_entity}' funds the dealer's indirect auto loans: its "
                        f"VHCL PURCH entry, one of {len(union_rows)} such credit-union credits in the statement (two "
                        "or more are dealer funding).", 0.90),
                revenue_source_type="auto_dealer_funding",
            )
    lender_words, debit_words = _debit_words(records, duplicate_indexes)
    # A3-G refinement: the holder's names the statement's own receiver fields print, when its account name names nobody.
    receiver_holders = _receiver_holder_names(records, credits)
    texts = {index: classifier.revenue_text(updated[index].normalized_description) for index in credits}
    facts = {
        index: credit_facts(
            updated[index], texts[index], lender_words=lender_words, debit_words=debit_words,
            receiver_holders=receiver_holders,
        )
        for index in credits
    }
    # §5.2: repeats count a verified credit, or an unverified one no hold names; never a held or conflicting one, a
    # credit under $1, a row a family rule decides alone or a deferred source (_never_q5_or_q6), and on the wire
    # channel only an incoming wire (§8.5: the loose wire words are for tiering only; S4.2 review I4). Never a Q7 row
    # either (S4.3 review): a lender's dealer funding verifies by §8.7 alone, and Q6's lenders never count.
    never = {index: _never_q5_or_q6(updated[index], texts[index], facts[index]) for index in credits}
    counting = Counter()
    consumer_only: dict[tuple[str, tuple[str, ...]], bool] = {}
    for index in credits:
        record, fact = updated[index], facts[index]
        if not fact.key or record.revenue_classification == "non_revenue" or never[index]:
            continue
        if record.revenue_match_method == "auto_lender_dealer_funding":
            continue
        if record.revenue_classification == "unverified_deposit" and fact.hold is not None:
            continue
        if fact.channel == "wire" and not fact.wire_n1:
            continue
        group = (fact.channel, fact.key)
        counting[group] += 1
        consumer_only[group] = consumer_only.get(group, True) and fact.consumer_entry
    # §8.4: a sender with two or more round sums on the rails or through named transfers. A direction conflict never
    # counts toward it (§5.2, §7.0; S4.2 review C1).
    round_sums = Counter(
        facts[index].key for index in credits
        if facts[index].channel == "person_to_person" and facts[index].round_sum and facts[index].key
        and updated[index].revenue_match_method != "direction_conflict" and updated[index].direction_consistent
    )
    for index in credits:
        record, fact, text = updated[index], facts[index], texts[index]
        if record.revenue_classification != "unverified_deposit" or never[index]:
            continue
        group = (fact.channel, fact.key)
        repeats = counting[group] if fact.key else 0
        if fact.channel == "wire" and _wire_verifies(record, text, fact, repeats):
            updated[index] = _verify(record, "repeat_wire_sender",
                                     "The same company wires the business twice or more in the statement.", 0.85)
            continue
        if _q6_eligible(record, text, fact) and not fact.refused_word:
            method = _q6_method(fact, repeats, consumer_only.get(group, True))
            if method is not None:
                updated[index] = _verify(record, method, _Q6_REASONS[method], 0.85)
    for index in credits:
        record, fact = updated[index], facts[index]
        tier = _TIER_OF_STATE.get(record.revenue_classification)
        if tier is not None:
            updated[index] = _with_tier(record, tier, None)
            continue
        round_repeat = fact.round_sum and bool(fact.key) and round_sums[fact.key] >= 2
        tier, reason = _tier_reason(record, texts[index], fact, round_repeat, _deferred_source(texts[index], fact))
        updated[index] = _with_tier(record, tier, reason)
    # §7.0, §7.8, §8.10 (S4.4/S4.5 review): the $1 floor is absolute, so it runs after every verification. A posted
    # credit under $1 that any rule verified or counted (a single-row rule, the registry's own context, a descriptor or
    # a remittance, reads no floor of its own) is held as _MICRO_DEPOSIT_REASON; a held one keeps its first hold
    # (§8.10's order) and a non-revenue one stays non-revenue. None counted toward a repeat above (_never_q5_or_q6).
    for index in credits:
        record = updated[index]
        if _under_micro_floor(record) and record.revenue_tier in {"verified", "counted_flagged"}:
            updated[index] = _held_by_the_floor(record)
    return updated


_Q6_REASONS = {
    "named_payer_repeats": "The same named payer pays the business twice or more in the statement.",
    "named_payer_company_form": "A named company pays the business by ACH or EFT.",
    "public_or_healthcare_payer": "A government or healthcare payer pays the business.",
}


def registry_financing_root(record: TransactionClassification, text: str) -> bool:
    """G2 (§14.3, review I1) on a registry row: a registry financing word (registry_financing), or a financing root
    glued inside a word of the row before its receiver fields, the holder's own words (on a store-name platform) and
    §7.0's FUNDING settlements aside. A root inside a place name (a city whose name holds LEND) is not one: the
    registry's reads are whole words."""
    classifier = _classifier()
    if registry_financing(record, text):
        return True
    own = _own_words(record, text)
    for word in classifier._before_receiver(text).split():
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in classifier._FUNDING_SETTLEMENT_ENTITIES:
            continue
        if _GLUED_FINANCING_ROOT.search(word):
            return True
    return False


def guard_facts(record: TransactionClassification, text: str) -> dict:
    """The census's §14.3 facts of one posted credit (tools/revenue_census.py), read with these readers. The customer
    descriptor is step 11's reading (the text without the receiver field's value, or the joined originator and entry
    before the receiver fields), so a descriptor in the holder's name never marks a row. The known payee is read the
    same way, as the record's claim reads it (S4.2 review M3). `claimed` is the pass's own claim (§8.1: the holds,
    the holder's included, skip a row the registry, a payout entity or a factoring payee claimed), which the census's
    holder guards read (review M1)."""
    classifier = _classifier()
    region = classifier.payer_region(text)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    words = classifier._without_receiver_value(text)
    known = match_known_payee(words)
    # G12 (§8.7): Q7's payer and veto words, read as dealer_funding reads them (the holder's name never names a lender).
    listed = _dealer_funding_payer(words) is not None
    union = bool(_CREDIT_UNION_PAYER.search(region))
    return {
        "claimed": _claimed(record, text),
        "financing_root": financing_named(text, region, entry, record.account_name),
        "registry_root": registry_financing_root(record, text),
        "registry_financing": registry_financing(record, text),
        "pay_or_personal": bool(_PAY_WORDS.search(row) or _PERSONAL_INCOME.search(row)),
        "transfer_no_counterparty": _transfer_row(row) and not _transfer_counterparty_words(text),
        "known_financing": known is not None and known.state in FINANCING_STATES,
        "payout_or_factoring": known is not None and (known.entity in PAYOUT_CREDIT_ENTITIES or known.state == "factoring"),
        "numbered_region": classifier._NUMBERED_COMPANY_REGION.search(
            classifier._skip_numbered_leading_date(region)
        ) is not None,
        "customer_descriptor": (
            classifier._matches_any(classifier._without_receiver_value(text), classifier._CUSTOMER_INVOICE_DESCRIPTORS)
            or classifier._matches_any(classifier._joined_text(row), classifier._CUSTOMER_INVOICE_DESCRIPTORS)
        ),
        "q7_payer_ok": listed or union,
        "q7_listed": listed,
        "q7_credit_union": union and bool(_VEHICLE_PURCHASE_ENTRY.search(entry or row)),
        "q7_veto_word": bool(_DEALER_FUNDING_VETO.search(words)),
        "pooled_while_vetoed": (
            record.revenue_match_method in {"recurring_operating_source", "operating_source_related_activity"}
            and classifier._recurrence_vetoed(record, text)
        ),
        # §14.2: a named payer whose channel is not printed, and whose name alone Q6 (b) or (c) would verify.
        "q6_shape": (
            classifier.company_form(classifier.payer_name(region))
            or government_payer(public_region(text)) or healthcare_payer(region)
        ),
    }
