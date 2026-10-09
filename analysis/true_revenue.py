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

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date as _date
from functools import cache
from typing import TYPE_CHECKING, Sequence

from .classification_registry import (
    ASSET_SALE_PAYERS,
    ASSET_SALE_SELLER_WORD_ONLY,
    BARE_PLATFORM_NAMES,
    CARD_PAYOUT_PROCESSOR_NAMES,
    CARD_SETTLEMENT_CREDIT_FORMS,
    CUSTOMER_FINANCING_NAMES,
    CUSTOMER_FINANCING_PAYERS,
    DEALER_FUNDING_PAYERS,
    EARNED_WAGE_ACCESS_PAYERS,
    FACTORING_PAYOUT_PAYERS,
    FLOOR_PLAN_ALIASES,
    HEALTHCARE_PAYER_ALIASES,
    INSURER_CREDIT_BRANDS,
    LENDING_BANK_CREDIT_PAYERS,
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    OWN_BANK_SENDING_SPELLINGS,
    OWNER_MONEY_PLATFORMS,
    P2P_SENDING_BANK_NAMES,
    PAYOUT_CREDIT_ENTITIES,
    SECTION_15_DEFERRED_PAYERS,
    STATEMENT_BANK_PRINTED_NAMES,
    WHOLESALE_AUCTION_PAYOUT_FORMS,
    WHOLESALE_AUCTION_REFUND_NAMES,
)
from .dates import parse_date
from .description_text import RECEIVER_FIELD_LABELS, RECEIVER_NAME_LABELS, normalize_transaction_description
from .flag_groups import FINANCING_STATES
# Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the premium-trust words and the legal forms the holder
# readers read (holder_name imports nothing of the analysis package, so this import is never circular). Audit round 3,
# R3-B11 review round 1 (finding 2): the title grammar's adjective, kind words and reference live there too, so a
# holder line's contact designation reads exactly the title the rule reads.
from .holder_name import (
    LEGAL_FORMS as _HOLDER_LEGAL_FORMS,
    PREMIUM_TRUST_ADJECTIVE as _PREMIUM_TRUST_ADJECTIVE,
    PREMIUM_TRUST_KIND as _PREMIUM_TRUST_KIND,
    PREMIUM_TRUST_REFERENCE as _PREMIUM_TRUST_REFERENCE,
    PREMIUM_TRUST_WORDS,
)
from .payee_matcher import PayeeMatch, match_known_payee, registry_match
from .revenue import REVENUE_TIER_REASONS, revenue_contribution_flags

if TYPE_CHECKING:
    from .transaction_classifier import CounterDebitReading, TransactionClassification

#: §8.1: the posting labels removed before a hold reads a row: §7.5's credit posting labels, the branch, card and
#: batch CREDIT labels, and the channel phrases. Audit B8 (I46): the plural FUNDS TRANSFERS too, transfer wording since
#: B8 (a bank's channel phrase, never a funder's FUNDS).
_HOLD_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE|INSTANT|REAL TIME|COUNTER|POS|ATM|TELLER|BRANCH|CARD|BATCH|MERCHANT|VISA|CHECKCARD|PURCHASE)"
    r"\s+CREDIT\b|^CREDIT\b"
    r"|\bCREDIT FROM\b|\bFUNDS (?:TRANSFERS?|AVAILABLE)\b|\bINSTANT FUNDS\b"
)
#: §8.1, T4: the credit-side financing roots. A whole-word CREDIT counts only inside a payer name, next to another
#: name word; glued, it always counts. The roots have no left boundary; of the whole words, those of four letters or
#: more take (?<![A-Z]) (the veto convention). Audit B6 (I08): a special-purpose entity's SPE (a funder's financing
#: vehicle, as SPV is), the whole word. B6 review round 1: FIN glued to USA is no root: with no left boundary it read
#: any run-together name ending in FIN + USA (a muffin or griffin brand), and Forward's FORWARDFINUSA is its ledger alias.
_FINANCING_ROOT = re.compile(
    r"(?:(?<!RE)FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|LEASING|PORTFOL)"
    r"|CRED(?=ORA|IBLY)|[A-Z]CREDIT|CREDIT(?!S\b)[A-Z]"
    r"|\b(?:CAP|FIN|ADV|MTG|MCA|RTR|SPE|SPV)\b|(?<![A-Z])(?:CAPI|FINA|FINAN|FINL|FNCL|LEASE)\b"
)
#: §8.1, T4: the whole-word CREDIT a payer name may print. Audit B7 (I16): the plural CREDITS is a statement's section
#: word ('DEPOSITS AND CREDITS', 'OTHER CREDITS', printed after a deposit when a page header or footer is glued on, or
#: as a layout's posting word), never a lender's name word: it is no root, glued or whole (the glued arm above spares
#: it too). B7 review round 1: except before a company form, after another name word, in a payer region
#: ('<NAME> CREDITS LLC'), where it is a lender's name word as the whole-word CREDIT is (_FORMED_CREDITS).
_WHOLE_CREDIT = re.compile(r"\bCREDIT\b")
_FORMED_CREDITS = re.compile(
    r"(?<=[A-Z] )CREDITS (?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC)\b"
)
#: §8.1, T4 (audit B7: I16): text the roots are never read on, because it never names the payer. A bank's branch label
#: after a bank's name ('BOFA FIN CTR', a Bank of America financial center); the banks' page furniture ('MEMBER FDIC',
#: 'EQUAL HOUSING LENDER'); a fundraising purpose; and Wave Payments' payout entry, the forms its payouts print ('WAVE
#: <code> FUNDIN WAVE', 'WAVE FUNDING INSTRU...'; Wave Payments is the operating registry's invoice-and-receivables
#: processor). On a wire's purpose text a buyer's advance payment or prepayment for goods is no financing either
#: (_WIRE_TRADE_PURPOSE).
_BRANCH_LABEL_WORDS = r"(?:FIN CTR|FIN CENTER|FINANCIAL CENTER|FINANCIAL CTR)"
_ROOT_FURNITURE = re.compile(r"(?<![A-Z])(?:MEMBER FDIC|EQUAL HOUSING LENDER)\b")
_FUNDRAISING = re.compile(r"(?<![A-Z])FUNDRAIS\w*")
_WAVE_PAYOUT_ENTRY = re.compile(r"(?<![A-Z])WAVE (?:[A-Z0-9]{2,6} )?FUNDIN WAVE\b|(?<![A-Z])WAVE FUNDING INSTRU\w*")
#: Audit round 3, R3-B07 (R3-18): and the abbreviated forms a wire's purpose field prints or cuts (ADV PAYM, ADV
#: PAYMENT, ADV PMT, ADV PYMT, ADVANCE PYMT), never after MERCHANT, CASH or MCA (a merchant cash advance's own words,
#: the full forms included). One pattern, shared by a wire's purpose text (_financing_root_places, wire-only: an ACH
#: entry's 'DES:ADV PMT' keeps its root) and a payer-less deposit's reading (_deposit_location_reading).
_WIRE_TRADE_PURPOSE = re.compile(
    r"(?<![A-Z])(?<!MERCHANT )(?<!CASH )(?<!MCA )(?:(?:ADVANCE|ADV) (?:PAYM\w*|PMTS?|PYMTS?)|PRE ?PAYMENTS?)(?![A-Z])"
)
#: §8.1, T4 (audit B7: I16): a whole-word CREDIT after a single letter that ends the payer region is the entry word a
#: layout prints after an originator name its field cut ('<NAME> P CREDIT', a sixteen-character name and its entry).
#: Audit round 2, R2-B09 (R06): so is the ACH entry 'CREDIT NONE' ending the region after a cut name ('<NAME> CREDIT
#: NONE'), and a credit union's DIVIDEND CREDIT is a dividend (its CREDIT no root).
_CUT_NAME_ENTRY_CREDIT = re.compile(r"(?<=\b[A-Z]) CREDIT$| CREDIT NONE$|(?<=\bDIVIDEND) CREDIT\b")
#: §8.1, T4 (B7 review round 1, I16): a check, cash, branch or ATM row that prints no payer region is read once its
#: location is removed (_deposit_location_reading): a branch's label ('<NAME> FIN CTR', '... FINANCIAL CENTER') and a
#: credit union's name ('<NAME> FIN CU', '... CREDIT UNION', '... FCU'), the ATM's or branch's owner, and a street's
#: name (_STREET_NAME: '<n> CAPITAL BLVD'). What is left is read for a financing word only: a word that starts with one
#: (_FINANCING_NAME_STARTS, CREDIT aside: a posting word there) or a whole-word root, never a root inside a word (a
#: town's name, 'GLENDALE'). So a funder's name printed on a deposit ('MOBILE DEPOSIT <NAME> FUNDING LLC') still holds.
#: B7 review round 2 widens the location (below) and the words never kept.
_DEPOSIT_BRANCH_LABEL = re.compile(r"(?:(?<![A-Z])[A-Z]+ )?" + _BRANCH_LABEL_WORDS + r"\b")
_DEPOSIT_CREDIT_UNION = re.compile(r"(?:(?<![A-Z])[A-Z]+ )?(?:FIN(?:ANCIAL)? )?(?:CREDIT UNION|F?CU)\b")
#: §8.1, T4 (B7 review round 2, I16): more of a deposit's location: a place a suffix names ('<n> CAPITAL CIR', '1
#: FINANCIAL PLAZA', '... FINANCIAL DISTRICT', '... CAPITAL HEIGHTS'), up to two words before BRANCH (a branch's
#: name, 'CAPITAL CITY BRANCH'), and a town printed with its state (_DEPOSIT_TOWN_TAIL). The ATM's or branch's bank
#: (the statement's own, a listed sending bank) is removed too (_root_reading's person-to-person removal: a bank's name
#: is never the payer). Audit round 2, R2-B13 (R35): a place, branch name or town that holds a kept financing word is
#: removed only after the row's start, a number, the deposit's own words or a numbered address
#: (_deposit_location_removal).
_DEPOSIT_PLACE = re.compile(
    r"(?<![A-Z])[A-Z]+(?= (?:PLAZA|MALL|CIR|CIRCLE|CTR|CENTER|CENTRE|SQ|SQUARE|DISTRICT|HEIGHTS|PARK)\b)"
)
_DEPOSIT_BRANCH_NAME = re.compile(r"(?<![A-Z])(?:[A-Z]+ ){1,2}(?=BRANCH\b)")
#: §8.1, T4 (audit round 2, R2-B13: R35; B7 review round 3, minor 1): the deposit's own words, after which a location
#: whose first word alone is a financing word is still a place ('ATM CASH DEPOSIT CAPITAL HEIGHTS MD', 'DEPOSIT CAPITAL
#: CITY BRANCH'); after a name word it is a funder's name ('MOBILE DEPOSIT <NAME> CAPITAL PLAZA',
#: _deposit_location_removal).
_DEPOSIT_LEAD_WORDS = frozenset({
    "DEPOSIT", "DEP", "DEPOSITS", "DEPOSITED", "EDEPOSIT", "ATM", "ABM", "BRANCH", "BRCH", "BR", "COUNTER", "CREDIT",
    "TELLER", "CASH", "CHECK", "CHECKS", "CHEQUE", "MOBILE", "REMOTE", "ONLINE", "IN", "AT",
})
#: §8.1, T4 (audit round 2, R2-B13 review round 1: R35): Wells Fargo's own deposit furniture, 'DEPOSIT MADE IN A
#: BRANCH/STORE' (normalized 'BRANCH STORE'), whose last word leads a place as the deposit's own words do; STORE alone
#: never does ('<NAME> STORE CAPITAL PLAZA' holds).
_DEPOSIT_LEAD_PAIRS = frozenset({("BRANCH", "STORE")})
#: §8.1, T4 (B7 review round 2, I16): a buyer's advance purchase printed on a deposit ('ADVANCE TICKET SALES') and,
#: as on a wire's purpose (_WIRE_TRADE_PURPOSE), an advance payment or prepayment for goods: no financing.
_DEPOSIT_TRADE_PURPOSE = re.compile(
    r"(?<![A-Z])ADVANCE (?:TICKETS?|SALES?|ORDERS?|BOOKINGS?|RESERVATIONS?|REGISTRATIONS?|PURCHASES?)\b"
)
#: §8.1, T4 (B7 review round 2, I16): the financing words a deposit's reading keeps: _FINANCING_NAME_STARTS without
#: CREDIT (a posting word there) and without FUNDS and FUNDED (a hold notice's words: 'FUNDS ON HOLD', 'FUNDS AVAIL
#: NEXT DAY'), which are kept only before a company form ('<NAME> FUNDS LLC').
_DEPOSIT_FINANCING_STARTS = (
    "FUNDING", "CAPITAL", "CAPTL", "FINANC", "LENDING", "LENDER", "LOAN", "ADVANCE", "MORTGAGE", "LEASING",
    "ACCEPTANCE", "SERVICING", "PORTFOLIO",
)
_DEPOSIT_NOTICE_FUNDS = frozenset({"FUNDS", "FUNDED"})
#: §8.1, T4 (audit B7: I16): on a person-to-person row the sender's bank: a credit union's name printed beside the
#: sender ('<sender> <NAME> CREDIT UNION ID ...'), one name word with its form; the listed sending banks are read with
#: _P2P_LAYOUT_PHRASES.
_P2P_CREDIT_UNION = re.compile(r"(?:(?<![A-Z])[A-Z]+ )?(?:CREDIT UNION|FCU)\b")
#: §8.1, T4 (audit B7: I16): the financing words a person's name never starts with; a person-to-person sender whose
#: name holds one (or a whole-word root) is read as a name that may be a lender's ('TRUE FINANCE', 'FAST FUNDING').
_FINANCING_NAME_STARTS = (
    "FUNDING", "FUNDS", "FUNDED", "CAPITAL", "CAPTL", "FINANC", "LENDING", "LENDER", "LOAN", "ADVANCE", "MORTGAGE",
    "LEASING", "CREDIT", "ACCEPTANCE", "SERVICING", "PORTFOLIO",
)
_WHOLE_WORD_ROOT = re.compile(r"(?:CAP|FIN|ADV|MTG|MCA|RTR|SPE|SPV|CAPI|FINA|FINAN|FINL|FNCL|LEASE|FUND)")
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
#: §8.7: the credit-union arm's payer region and entry field. Audit B7 (I36): and a credit union's glued acronym, one to
#: three letters before CU or FCU as one word (BECU, SECU, PSECU, GECU, DCU), read with the arm's VHCL PURCH entry and
#: its two-credit count as every credit union is.
_CREDIT_UNION_PAYER = re.compile(r"\bCU\b|\bCREDIT UNION\b|\bFCU\b|\bCU DIRECT\b|\bCUDL\b|\b[A-Z]{1,3}F?CU\b")
#: §8.7 (audit B7: I36): a deal's ID on Chase's credit-union layout ('IND ID:<deal>'), which a credit union prints on
#: the vehicle purchase and on the same deal's admin fee.
_DEAL_ID = re.compile(r"\bIND ID (\S+)")
_VEHICLE_PURCHASE_ENTRY = re.compile(r"\bVHCL PURCH(?:ASE)?\b")
#: §8.7: a statement's credit-union dealer funding needs this many credits.
CREDIT_UNION_DEALER_MIN_CREDITS = 2
#: §8.7 (S4.3 review): a lender's floor-plan (wholesale) financing of the dealer's inventory is never dealer funding.
_DEALER_FLOOR_PLAN_WORDS = re.compile(r"(?<![A-Z])(?:FLOOR\w*|WHOLESALE\w*)")
#: §8.1, §8.7 (B7 review round 2, I36): a floor-plan lender's name on a wire's sender (_dealer_word_lender): a
#: floor-plan form, or WHOLESALE beside a lender's or a vehicle trade's whole word ('<NAME> WHOLESALE AUTO LLC'; audit
#: round 2, R2-B13: R39, B7 review round 3 minor 3: whole words, never a customer's FINE, CAPE, FINCH, CAPTAIN,
#: AUTOMATION, MOTORSPORTS or DEALERSHIP); never a flooring contractor's or a wholesale grocer's name ('<NAME> FLOORING
#: LLC', '<NAME> WHOLESALE GROCERS INC'). R2-B13 review round 1: and a finance company's glued spellings that the
#: financing root does not read (FINCO, FINCORP, CAPCO, CAPCORP, AUTOFIN).
_FLOOR_PLAN_LENDER_WORDS = (
    r"(?:FUND|FUNDS|FUNDING|FIN|FINANCE|FINANCIAL|FINANCING|LEND|LENDER|LENDERS|LENDING|CAP|CAPITAL|CREDIT|AUTO|AUTOS"
    r"|AUTOMOTIVE|MOTOR|MOTORS|DEALER|DEALERS|FINCO|FINCORP|CAPCO|CAPCORP|AUTOFIN)"
)
_FLOOR_PLAN_LENDER_NAME = re.compile(
    r"(?<![A-Z])FLOOR ?PLAN\w*"
    rf"|(?<![A-Z])WHOLESALE\w* {_FLOOR_PLAN_LENDER_WORDS}(?![A-Z])"
    rf"|(?<![A-Z]){_FLOOR_PLAN_LENDER_WORDS} WHOLESALE\w*"
)
#: §8.1: an insurer's name on the payer region.
_INSURER_NAME = re.compile(
    r"(?<![A-Z])(?:INSUR\w*|ASSURANCE\b|MUTUAL\b|CASUALTY\b|INDEMNITY\b|UNDERWRIT\w*)"
)
_CLAIM_WORD = re.compile(r"(?<![A-Z])CLAIMS?\b")
#: §8.1 insurer_named_payer (audit I26, by Q6 of 2026-09-28 and the underwriter's Q2 (2026-10-02) option's "a one-off
#: claim paid to a business on its own policy stays out"; R2-OW07): the insurer spellings a payer region prints beside
#: _INSURER_NAME's spelled-out words, which _INSURER_NAME (pinned by the contract's docs test) leaves unread: the INS
#: abbreviation, the cut forms ASSUR, MUTUA, CASUALT and INDEMN, the French ASSURANCES, ASSURANT and ASSUREUR(S), P AND
#: C (or P & C) at a name's end or before INS, CO, COMPANY or CORP, a loss payment's LOSS PMT, PAYMENT, PYMT or DRAFT,
#: and SUBRO (a subrogation recovery). Never ASSURED or ASSURE ('ASSURED STAFFING LLC'), never P AND C FOODS; CLM, CLMS
#: and CLMEFT are not read (every corpus CLM row is a health plan paying a provider). R2-OW07 review round 1: SUBRO and
#: its cut forms only (SUBROG, SUBROGATION), never the given name SUBROTO; P AND C before INS, INSU or INSUR... only,
#: never an installer's or an inspector's word. Audit round 3, R3-B13 (R3-11): and a Texas county mutual's
#: 16-character cut, COUNTY MUT ('PROG COUNTY MUT'; MUTUA and MUTUAL already read), a private carrier never read as a
#: county (the classifier's _PUBLIC_PAYER_NAME veto).
_INSURER_SPELLINGS = re.compile(
    r"(?<![A-Z])(?:ASSURANCES|ASSURANT|ASSUREURS?|ASSUR|MUTUA|CASUALT\w*|INDEMN\w*|SUBRO(?:G\w*)?)(?![A-Z])"
    r"|(?<![A-Z])INS(?![A-Z])"
    r"|(?<![A-Z])P (?:AND|&) C(?:(?! ?[A-Z])| (?:INS(?:UR\w*|U)?|CO|COMPANY|CORP)(?![A-Z]))"
    r"|(?<![A-Z])LOSS (?:PMT|PAYMENT|PYMT|DRAFT)(?![A-Z])"
    r"|(?<![A-Z])COUNTY MUT(?![A-Z])"
)
#: B3 review round 1: the classifier's _NO_LEGAL_FORM_LATER (copied: the classifier imports this module): no
#: legal-form word later on the row.
_NO_LEGAL_FORM_LATER = (
    r"(?!.*\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LTEE|LIMITED|LLP|LLLP|PLLC|ULC|PLC|GMBH)\b)"
)
#: Audit round 2, R2-B08 (R08, R47 (a), R48 part 2): the classifier's _RETURN_REFUND_R2_B08_ARMS, copied verbatim (the
#: classifier imports this module): a Quebec returned item, CIBC's CONTRE-PASSATION, RBC's refused item SANS
#: PROVISION, the check-word NOT PAID at the row's head (review round 1: never in a memo, a wire's remittance field or an
#: ACH entry description), an e-Transfer reclaim with the rail word right before RECLAIM and a reference after it or
#: TD's RECLAIM E-TFR, and the fee waiver with no legal-form word later. A test keeps the copies in step. Audit round 3,
#: R3-B08 (R3-44): a lost accent inside CHEQUE (CH QUE) and after RETOURN is tolerated, as after REFUS.
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
#: Audit round 3, R3-B09 review round 1 (R3-75): from the row's start, text holding no incoming e-Transfer wording
#: (RECEIVED, FROM, AUTODEPOSIT, the French RECEPT and DEPOT), read before the outgoing send and sent labels of
#: _POSSIBLE_RETURN: a send label after one of them is a memo's words on an incoming transfer.
_NO_INCOMING_WORDING_BEFORE = r"^(?:(?!(?<![A-Z])(?:RECEIVED|FROM|AUTO ?DEPOSIT|RECEPT|DEPOT)(?![A-Z])).)*?"
_POSSIBLE_RETURN = re.compile(
    r"(?<![A-Z])RETURN(?:ED|S)?\b|\bADJ\b|(?<![A-Z])ADJ(?:USTMENT|USTED)\b|(?<![A-Z])DISPUTE[DS]?\b"
    r"|(?<![A-Z])CREDIT MEMO\b|(?<![A-Z])OVERPA\w*"
    # §7.8: an auction's guarantee or arbitration refund of a vehicle the dealer bought.
    r"|(?<![A-Z])DEALSHIELD\b|(?<![A-Z])ARB(?:ITRATION)? CREDIT\b"
    # 5.6 (audit B3: I04): a backstop for step 3's 5.6 return, correction and refund spellings (the classifier's
    # _RETURN_REFUND_CREDIT_PATTERNS, read on the hold text, a correction or a reversed purchase printed first after
    # the posting labels are removed), so such a row that reaches the pass is held, never counted. REMBOURSEMENT is
    # not read (a provider's REMBOURSEMENT left step 3 by §7.11's carve-out), nor the card labels (their own arm).
    # B3 review round 1: NOT PAID, UNAUTHORIZED, RECLAIM, the leading REV form and RETOUR narrowed as the classifier's
    # (never a company's name or a memo; _NO_LEGAL_FORM_LATER is the classifier's, copied).
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
    # Audit round 2, R2-B08: the classifier's new step-3 arms (the fee waiver's guarded arm replaces the bare one).
    + "".join("|" + arm for arm in _RETURN_REFUND_R2_B08_ARMS)
    # Audit round 3, R3-B09 (R3-75; standard D1, D3, A8): the holder's own sent e-Transfer coming back is no customer
    # revenue, whichever leg the parser signed: a credit printing TD Canada Trust's send (SEND E-TFR), a sent transfer
    # (EQ Bank's 'Interac e-Transfer sent to', any bank's; never 'SENT BY', an incoming wording), TD's French send, its
    # reversal or its redeposit ('Envoi-VFC', 'Envoi - FRAIS - VFC', 'Contr. - VFC', 'Redepot - VFC'), or a French fee
    # adjustment (no legal-form word later on the row). Pass 7 only: never a step-3 or pass-4 marker.
    # R3-B09 review round 1: the send and sent labels only with no incoming wording before them on the row
    # (_NO_INCOMING_WORDING_BEFORE: an incoming e-Transfer whose memo prints the send words stays a counted push), the
    # send label with no legal-form word later, and none of the three inside an ACH originator's name field (after
    # NAME: 'ORIG CO NAME:SEND ETRANSFER LLC' is a payer's name, never the bank's label).
    + r"|" + _NO_INCOMING_WORDING_BEFORE + r"(?<![A-Z])(?<!NAME )SEND E ?(?:TFR|TRANSFER)\b" + _NO_LEGAL_FORM_LATER
    + r"|" + _NO_INCOMING_WORDING_BEFORE + r"(?<![A-Z])(?<!NAME )(?:INTERAC )?E ?(?:TRANSFER|TFR) SENT\b(?! BY\b)"
    r"|(?<![A-Z])(?:ENVOI|CONTR|REDEPOT) (?:FRAIS )?VFC\b"
    r"|(?<![A-Z])(?<!NAME )AJUST(?:EMENT)? (?:DE )?FRAIS\b" + _NO_LEGAL_FORM_LATER
)
#: §8.1, §7.11: a card credit's posting labels (a refund to the card unless a form or the registry verified it). 5.6
#: (audit B3: I04): and the card-shaped refund labels step 3 adds (Citibank's cut DEBIT CARD CREDI, Bank of America's
#: credit-side CHECKCARD <mmdd>, a point-of-sale deposit before its merchant's name, as step 3 reads it; B3 review
#: round 1: a bare one names no merchant and keeps Q2's counted reading), whichever a push word released.
_CARD_CREDIT_LABEL = re.compile(
    r"(?<![A-Z])(?:DEBIT CARD CREDIT?|POS CREDIT|VISA CREDIT|CHECKCARD CREDIT|PURCHASE CREDIT)\b"
    r"|^(?:\d{1,2} \d{1,2} )?CHECKCARD \d{4}\b|(?<![A-Z])POINT OF SALE DEPOSIT [A-Z]"
)
#: §8.1 (audit B3: I04): a card credit printed first, BMO's and Regions' 'CARD CREDIT ...': a refund to the card, or a
#: push the parser cut from its payer (BMO prints the merchant on a line the parser drops), held as a possible return
#: unless a push or person-to-person rail is printed (Regions' 'CARD CREDIT CASH APP ...' and '... APPLE CASH ...' stay
#: Q4's counted pushes).
_LEADING_CARD_CREDIT = re.compile(r"^(?:\d{1,2} \d{1,2} )?CARD CREDIT\b")
#: 5.6 (audit B3: I11, §7.11, §6.3 narrowing 9, §20): the method of a card credit released as its merchant processor's
#: instant payout (_processor_card_payouts), the card labels it reads, and each processor's names as whole words
#: (CARD_PAYOUT_PROCESSOR_NAMES).
PROCESSOR_CARD_PAYOUT_METHOD = "processor_card_payout"
#: Audit B3 (I11): the release stays off by the owner's ruling of 2026-10-02 (the underwriter's Q13, "keep them
#: excluded"; spec §19.1): a processor's payout printed as a bare card credit stays a card refund. The code stays as
#: the declined option's record; turning it on needs the owner's word again (at c486fd5 it would count 119 rows,
#: $199,280.67, in 9 Relay statements, census narrowing 10, and re-pin the Relay fixture of
#: tests/test_new_statement_corpus.py).
PROCESSOR_CARD_PAYOUT_RELEASE = False
_PROCESSOR_CARD_PAYOUT_RULE = "processor_card_credit_beside_its_ach_activity"
_CARD_PAYOUT_LABEL = re.compile(r"(?<![A-Z])(?:DEBIT CARD CREDIT?|POS CREDIT)\b")
_CARD_PAYOUT_NAMES = {
    entity: re.compile(
        r"(?<![A-Z])(?:" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)) + r")(?![A-Z])"
    )
    for entity, names in CARD_PAYOUT_PROCESSOR_NAMES.items()
}
#: §8.1 (Q8): pay wording, read on the row before its receiver fields.
_PAY_WORDS = re.compile(
    r"(?<![A-Z])(?:PAYROLL\w*|PAYRLL\b|PAYROL\b|PAYRL\b|SALARY\b|SALARIES\b|REG SAL\b|WAGES?\b|NET ?PAY\b"
    r"|BONUS(?:ES)?\b|PAY PAY\b|PAIE\b|SALAIRES?\b|PAYCHECKS?\b|PAYCHK\b|PR PAY\w*|EMPLOYEE PAY\w*|EMP PAY\b"
    r"|EXP(?:ENSE)? REIMB\w*)"
)
#: §8.1, §8.8 (Q8; audit B7: I09, amends review I4's reading): the direct-deposit words, DIR DEP, DIRDEP and DIRECT
#: DEP anywhere and the whole phrase DIRECT DEPOSIT as an entry description. A direct deposit is a payment channel, not
#: a purpose: a company settles with a business by direct deposit as it pays an employee. They are pay wording only
#: with a sign the credit is a person's pay (_direct_deposit_pay): another pay word or a payroll provider (_pay_wording
#: reads those anyway), a person named in the receiver field or after the deposit's references, a consumer (PPD or WEB)
#: entry, or an account that does not read as a business's (_business_shape). Q7's refusal still reads them alone
#: (_q7_refused_by_a_hold: a listed lender's dealer funding never verifies beside pay wording).
_DIRECT_DEPOSIT_WORDS = re.compile(
    r"(?<![A-Z])(?:DIR ?DEP\b|DIRDEP\b|DIRECT DEP\b(?!OSIT)|(?:DES|CO ENTRY DESCR) DIRECT DEPOSIT\b)"
)
#: §8.1, §20 (GOV, the owner's ruling of 2026-09-30, class B: government money paid to a person is no revenue of the
#: business; GOV review I2, M4): the government's personal-benefit descriptors, read as the whole payer
#: (government_benefit) after the posting words and template prefixes (classifier.government_form_payer), with the
#: CRA's originator name (CANADA) before or after them and a posting code or a reference after them. The Canadian
#: Payments Association's federal benefit descriptors: the child, essentials (the GST/HST credit's name since 2026, in
#: full 'CANADA GROCERIES AND ESSENTIALS BENEFIT'), workers and disability benefits, and Old Age Security. A provincial
#: benefit the CRA pays on a province's behalf ("Canada PRO"): the provincial payment code with the CRA's originator
#: ('PROV LOCAL GVT PAYMENT CANADA', '... CANADA PRO'), its PRO label ('PROV LOCAL GVT PRO ONTARIO') and 'CANADA PRO
#: DEPOSIT'. So 'CANADA CHILD CARE CENTRE INC', 'CANADA DISABILITY BENEFITS CONSULTING INC', 'OLD AGE SECURITY SYSTEMS
#: LTD' and 'PROVINCIAL PAYMENT CANADA GOOSE SUPPLY' are payers, and a provincial payment from a province names no
#: benefit (its purpose is not printed).
_PROVINCES = (
    r"(?:ONTARIO|QUEBEC|NOVA SCOTIA|NEW BRUNSWICK|MANITOBA|BRITISH COLUMBIA|BC|PRINCE EDWARD ISLAND|PEI|SASKATCHEWAN"
    r"|ALBERTA|NEWFOUNDLAND(?: AND LABRADOR)?|YUKON|NORTHWEST TERRITORIES|NUNAVUT)"
)
#: Audit B8 (the GOV follow-up, the orchestrator's): RBC's cut label of the same provincial payment code,
#: 'Prov./Loc.G.Paym' ('PROV LOC G PAYM CANADA'), read as its spelled-out form is.
_GOVERNMENT_BENEFIT_PAYER = re.compile(
    r"(?:(?:CANADA )?(?:CANADA (?:CHILD|(?:GROCERIES (?:AND )?)?ESSENTIALS|WORKERS|DISABILITY) BENEFITS?"
    r"|OLD AGE SECURITY)(?: CANADA)?"
    rf"|(?:PROV LOCAL GVT(?: PAYMENT)?|PROV LOC G(?:VT)? PAYM(?:ENT)?|PROVINCIAL PAYMENT)"
    rf" (?:CANADA(?: PRO)?|PRO(?: {_PROVINCES})?)"
    r"|CANADA PRO(?: DEPOSIT)?)"
    r"(?: (?:MSP|DIV|\d+))*"
)
#: GOV (B; GOV review I2): the benefit entries read inside a row: a state's unemployment-insurance direct deposit ('NYS
#: DOL UI DD') and the IRS's economic impact payment ('TAX EIP3'), this one on an IRS Treasury row only. A company form
#: after the entry, before the row's next field, vetoes it ('NORTHWIND UI DD LLC'); 'FABRIKAM TAX EIP SERVICES' prints
#: no IRS form.
_GOVERNMENT_BENEFIT_ENTRY = re.compile(r"\bUI DD\b|(?<![A-Z])(?P<eip>TAX ?EIP ?\d?)\b")
_ENTRY_FIELD_LABEL = re.compile(r"\b(?:CO ID|DES|ID|INDN|IND ID|IND NAME|ORIG ID|SEC|TRACE|EED|TRN|CCD|PPD|CTX|WEB)\b")
_ENTRY_COMPANY_FORM = re.compile(
    r"\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC)\b"
)
#: §8.1: benefit and pension credits. GOV: the government's personal-benefit forms are read by government_benefit.
#: Audit B8 (I28): and a health savings account's distribution ('HSADISTRIB', 'HSA DISTRIB...': a person's own medical
#: savings) and a life insurer's annuity payment cut by a sixteen-character originator field ('<insurer> LIFE AN
#: DISBPYMT', the whole ANNUIT... word cut away).
_PERSONAL_INCOME = re.compile(
    r"(?<![A-Z])(?:XX)?SOC SEC\b|\bSSA\b|\bSSI\b|(?<![A-Z])SUPP SEC\b|(?<![A-Z])(?:XX)?VA BEN\w*"
    r"|(?<![A-Z])UNEMPLOY\w*|(?<![A-Z])UI BEN\w*"
    r"|(?<![A-Z])CHI?LD ?SUPP\w*\b|(?<![A-Z])CHILD ?CTC\b|(?<![A-Z])PENSION\b|(?<![A-Z])ANNUIT\w*"
    r"|(?<![A-Z])RETIRE\w*"
    r"|(?<![A-Z])HSA ?DISTRIB\w*|(?<![A-Z])LIFE AN DISB\w*"
)
#: §8.1, §20 (GOV, the owner's ruling of 2026-09-30, class D: a grant or subsidy is no sale): HHS's CARES Act Provider
#: Relief Fund ('US HHS STIMULUS', its glued entry 'HHSPAYMENT') and the USDA's farm programs, the Farm Service
#: Agency's and (GOV review M4) the Commodity Credit Corporation's Treasury forms ('FSA TREAS 310', 'CCC TREAS 310';
#: USDA's own 'USDA TREAS 310' also pays vendors and keeps its reading); and (the coordinator's ruling on the class-E
#: form) ESDC's federal payment code, its grants and contributions ('GOVERNMENT ESDC ... FEDERAL PMT'). §8.1's GRANT
#: word already holds a row that prints it. Never a name that holds the letters: 'HHS SUPPLY CO', 'NORTHWIND FSA
#: SERVICES LLC'.
#: Audit B8 (I56; GOV class D, the owner's ruling of 2026-09-30): the CRA's Canada Carbon Rebate, glued as TD Canada
#: Trust prints it ('CDACARBONREBATE CCR') or spaced, read with no left word boundary (its spaced spelling's REBATE
#: word holds it too); a name that only holds CARBON ('<NAME> CARBON WORKS LLC') is no rebate.
_GOVERNMENT_GRANT = re.compile(
    r"(?<![A-Z])HHS ?STIMULUS\b|(?<![A-Z])HHSPAYMENT(?:SEC)?\b|(?<![A-Z])(?:FSA|CCC) TREAS ?\d{3}\b"
    r"|(?<![A-Z])GOVERNMENT ESDC\b(?=.*(?<![A-Z])(?:FEDERAL PMT|PAIEMENT FEDERAL)\b)"
    r"|(?:CANADA ?|CDA ?)CARBON ?REBATE\b"
)
#: GOV review (M4): the CRA's Canada Emergency Wage Subsidy, read as the whole payer (government_form_payer) with the
#: CRA's name before or after it, so 'CANADA CEWS CONSULTING INC' is a payer.
_WAGE_SUBSIDY_PAYER = re.compile(r"(?:CANADA )?CEWS(?: CANADA)?(?: (?:MSP|DIV|\d+))*")
#: §8.1: a non-sale purpose. Audit B7 (I18): OWNER is no owner money in the ordering platform's name OWNER COM, and
#: neither OWNER nor OWNERS in an owners' or homeowners' association's name ('<NAME> OWNERS ASSOC', cut to 'OWNERS A'
#: by a sixteen-character originator field); the other words read only as a purpose (_non_sale_reading).
_NON_SALE_PURPOSE = re.compile(
    r"(?<![A-Z])(?:INVEST\w*|DISTRIB(?!UTORS?\b|UTING\b)\w*|DIVIDENDS?\b|EQUITY\b|CONTRIB\w*|SHAREHOLDER\w*"
    r"|OWNER\b(?! OP\b| OPERATORS?\b| COM\b| ASS(?:OC|N)\w*)"
    r"|OWNERS\b(?! OP\b| OPERATORS?\b| ASS(?:OC|N)\w*| AS\b| A\b)"
    r"|STOCK\b|INTERCO\w*|INTER COMPANY\b|DUE FROM\b|SWEEP\b|ZERO BAL\w*"
    r"|REPAY\w*|PRINCIPAL\b|PAYOFF\b|PROMISSORY\b|CONVERTIBLE\b|TRANCHE\b|DRAWS?\b|DRAWDOWNS?\b"
    r"|DISBURS\w*"
    r"|ESCROW\b|EARNEST\b|SECURITY DEPOSIT\b|DEPOSIT BACK\b|SURPLUS\b"
    r"|GRANTS?\b|DONATION\w*|GIFT\b(?! CARD\b)|COURT\b|JUDGMENT\b"
    r"|REBATES?\b|REIMB\w*|INTEREST\b|REWARDS?\b|CASH ?BACK\b"
    r"|RFND\w*|REFND\w*)"
    r"|\bZBA\b|[A-Z]*REFUND\w*"
)
#: §8.1 non_sale_purpose (audit B7: I18, the precedent of §7.11's street guard): a word followed by a street suffix is a
#: street's name in an address ('<n> GRANT AVE', an ATM's or a branch's location), never a purpose.
_STREET_NAME = re.compile(
    r"(?<![A-Z])[A-Z]+(?= (?:AVE|AVENUE|ST|STREET|RD|ROAD|BLVD|BOULEVARD|DR|DRIVE|LN|LANE|WAY|CT|PL|HWY|PKWY)\b)"
)
#: §8.1 non_sale_purpose (audit round 2, R2-B13: R34, §7.11's street guard as the precedent): the non-sale reading's
#: street name, read only after a street number: the word right before a street suffix when a number token (digits, a
#: letter after them: '12B') stands right before it or one word before it ('<n> GRANT AVE', '<n> N GRANT ST'). The
#: number is kept. A word before a Stripe-style 'ST-<id>' trace or before a suffix with no number ('<NAME> EQUITY DR
#: <zip>') is no street. _STREET_NAME, which needs no number, still reads a deposit's location
#: (_deposit_location_reading) and, R2-B13 review round 1, a payer-less deposit's non-sale reading (_non_sale_reading).
#: The suffixes are _STREET_NAME's (a test keeps them in step).
_STREET_SUFFIXES = "AVE|AVENUE|ST|STREET|RD|ROAD|BLVD|BOULEVARD|DR|DRIVE|LN|LANE|WAY|CT|PL|HWY|PKWY"
_STREET_SUFFIX_WORDS = frozenset(_STREET_SUFFIXES.split("|"))
_NUMBERED_STREET_NAME = re.compile(
    rf"(?<![A-Z0-9])(?P<number>\d+[A-Z]?(?: [A-Z]+)?) [A-Z]+(?= (?:{_STREET_SUFFIXES})\b)"
)
#: §8.1 non_sale_purpose (audit B7: I18): DISTRIB... and STOCK are a business's name words (a distributor, a goods
#: stock) more often than owner money. They are not read inside the payer's name field (an ACH originator, a wire's
#: sender, a transfer's sender after FROM), inside a name that a company form ends ('<NAME> DISTRIBUTION INC', after a
#: name word, with at most one more name word and no connector word before the form: never 'DISTRIBUTION FROM <NAME>
#: LLC'), in
#: a joint-stock company's or bank's legal form ('JOINT STOCK COMPANY', 'JOINT STOCK COMMERCIAL BANK'), or, STOCK, on a
#: row that cites an invoice ('INV <n> STOCK AND FREIGHT': goods). A purpose or entry field still holds them
#: ('DES:DISTRIB', 'QUARTERLY PARTNER DISTRIBUTION').
_NAME_NON_SALE_WORDS = re.compile(r"(?<![A-Z])(?:DISTRIB(?!UTORS?\b|UTING\b)\w*|STOCK\b)")
_JOINT_STOCK = re.compile(r"(?<![A-Z])JOINT STOCK\b")
#: B7 review round 1: the word before DISTRIB... or STOCK must be a name word (letters only, none of
#: _NOT_A_NAME_WORD_BEFORE: a period, a member's or owner's word, a memo's or a field's label, a connector, a company
#: form), so a purpose before a formed name ('QUARTERLY DISTRIBUTION <NAME> LLC', 'MEMO DISTRIBUTION <NAME> LLC', 'PMT
#: DET <n> MEMBER DISTRIBUTION <NAME> INC') still holds.
_FORMED_NAME_NON_SALE = re.compile(
    r"(?<![A-Z0-9])(?P<before>[A-Z0-9]+) (?:DISTRIB(?!UTORS?\b|UTING\b)\w*|STOCK)"
    r"(?= (?:(?!(?:FROM|TO|OF|FOR|BY|PER|AND|THE)\b)[A-Z]+ )?(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO"
    r"|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC|GMBH)\b)"
)
_NOT_A_NAME_WORD_BEFORE = frozenset({
    "QUARTERLY", "MONTHLY", "ANNUAL", "ANNUALLY", "YEARLY", "WEEKLY", "FINAL", "INTERIM", "SPECIAL", "MEMBER", "MEMBERS",
    "PARTNER", "PARTNERS", "OWNER", "OWNERS", "SHAREHOLDER", "SHAREHOLDERS", "PROFIT", "PROFITS", "CAPITAL", "EQUITY",
    "CASH", "INCOME", "DIVIDEND", "TRUST", "ESTATE", "MEMO", "OBI", "DET", "REF", "RE", "INFO", "NOTE", "DESC", "DES",
    "RMK", "FOR", "OF", "TO", "FROM", "BY", "PER", "AND", "THE", "LLC", "INC", "CORP", "LP", "LLP", "LTD",
    # B7 review round 2: a tax, year-end, partnership, half-year, preferred, estimated or retained distribution, and
    # the months (the classifier's _ENTITY_MONTHS, copied: the classifier imports this module).
    "TAX", "TAXES", "PARTNERSHIP", "YEAR", "END", "YEAREND", "YE", "SEMIANNUAL", "BIANNUAL", "PREFERRED", "ESTIMATED",
    "RETAINED",
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "SEPT", "OCT", "NOV", "DEC", "JANUARY", "FEBRUARY",
    "MARCH", "APRIL", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
    # Audit round 2, R2-B13 (R34; B7 review round 3, minor 2): an earnings, liquidating or pro-rata distribution.
    "EARNINGS", "EARNING", "LIQUIDATING", "LIQUIDATION", "PRORATA",
})
#: B7 review round 2: a period's code before DISTRIB... or STOCK is no name word ('Q4 DISTRIBUTION', 'K1', 'FY2054',
#: '2054Q4', '4TH'), nor a reference (a word of three digits or more, 'AB1234'), while a name word that holds a letter
#: and one or two digits is one ('A1 DISTRIBUTION LLC', 'H2O DISTRIBUTION INC'). Audit round 2, R2-B13 (R34; B7 review
#: round 3, minor 2): nor a month and year, or a day and month, glued ('JAN54', 'SEPT54', '15JAN', '1JAN54').
_PERIOD_MONTHS = r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEPT?|OCT|NOV|DEC)"
_PERIOD_CODE = re.compile(
    r"Q[1-4]|[1-4]Q|H[12]|K1|FY\d*|\d{2,4}Q[1-4]|Q[1-4]\d{2,4}|\d+(?:ST|ND|RD|TH)"
    rf"|{_PERIOD_MONTHS}\d{{2,4}}|\d{{1,4}}{_PERIOD_MONTHS}(?:\d{{2,4}})?"
)
_NAME_WORD_MAX_DIGITS = 2
_STOCK_WORD = re.compile(r"(?<![A-Z])STOCK\b")
_INVOICE_WORD = re.compile(r"(?<![A-Z])(?:INVOICES?|INV)\b|(?<![A-Z])INV ?\d")
#: §8.1 non_sale_purpose (audit B7: I18): DISBURS... is the payer's own account ('DISBURSEMENT ACCOUNT', an importer's
#: paying account), or an ordinary company's recurring payout entry ('PSP <phone> DISBURSMNT', a processor's
#: payouts), no non-sale purpose. It stays one beside a loan, escrow, title or proceeds word, on a one-off credit, and
#: on a row whose payer reads as a lender, an insurer, a title or escrow firm, a bank, a lawyer or a government
#: (_disbursing_payer).
_DISBURSEMENT_ACCOUNT = re.compile(r"(?<![A-Z])DISBURS\w* (?:ACCOUNT|ACCT|ACCNT)\b")
_DISBURSEMENT_WORD = re.compile(r"(?<![A-Z])DISBURS\w*")
_DISBURSEMENT_KEEP = re.compile(
    r"(?<![A-Z])(?:LOANS?|ESCROW|TITLE|PROCEEDS) DISBURS\w*|(?<![A-Z])DISBURS\w* (?:LOANS?|ESCROW|TITLE|PROCEEDS)\b"
)
#: Audit round 2, R2-B12 (R17; standard E3, G2): a retirement account's or plan's disbursement (an IRA, a Roth, a
#: 401(k) or 403(b) plan, a pension, a retirement or annuity payer) is the owner's own money or personal income, never
#: an ordinary payer's payout: read on the row's hold text (the payer region stops at a digit, 'SAMPLE 401K PLAN'
#: reading 'SAMPLE'), it keeps the disbursement's hold however often it repeats (_disbursing_payer).
_RETIREMENT_ACCOUNT = re.compile(r"(?<![A-Z])(?:IRA|ROTH|401 ?K|403 ?B|PENSION\w*|RETIRE\w*|ANNUIT\w*)\b")
#: §8.1 non_sale_purpose (B7 review round 1, I18): an owner-shaped payer, whose disbursement is owner money and never a
#: payout: a holding company, a partnership (PARTNERS, PARTNERSHIP, LP, LLP, LLLP), a venture, a family office, a
#: trust or an estate (never REAL ESTATE, a broker's name).
_OWNER_SHAPED_PAYER = re.compile(
    r"(?<![A-Z])(?:HOLDINGS?|PARTNERS|PARTNERSHIP|VENTURES?|FAMILY|TRUST)\b|(?<![A-Z])(?<!REAL )ESTATES?\b"
    r"|\b(?:LP|LLP|LLLP)\b"
)
#: §8.1 (A3-G, audit B7: the orchestrator's delegated ruling on audit I57): a personal trust's payment whose purpose
#: cites the holder's service, a school's tuition or a student's ID, is a customer's payment, not owner money; it is
#: read on the payment's purpose (_title_purpose_text) with a line wrap's split joined ('TUITIO N'). A trust's invoice
#: or PO payment is already verified by §7.9 before the holds read it. Audit round 2, R2-B08 (R47 (c)): the ruling names
#: TUITION and STUDENT ID only: TUITION is read on the space-stripped purpose (a wrap's split joined, glued after a word
#: as in FORTUITION) but never after IN (INTUITION, a cross-word join INTUIT ION...), and STUDENT ID on the printed
#: purpose as whole words (STUDENT ID 12345, STUDENTID12345; never STUDENT IDEAS). IN TUITION is held, the safe side.
#: Review round 1: a line wrap's split inside STUDENT or ID is joined, as TUITION's reader joins one (STUDEN T ID,
#: STUDENT I D), the two ends staying whole words (never STUDENT I DEAS, STUDENT IDENTIFICATION or STUDENTS ID).
_TRUST_SERVICE_PURPOSE = re.compile(r"(?<!IN)TUITION")
_TRUST_STUDENT_ID_PURPOSE = re.compile(r"(?<![A-Z])S ?T ?U ?D ?E ?N ?T ?I ?D(?![A-Z])")
#: §8.1 non_sale_purpose (audit B8: I28; the MCA principle of 2026-09-30, standard G3): a gambling or prediction-market
#: payout is no money the business earned from its operations, held for review (the owner may make it non_revenue).
#: Read on the row before its receiver fields: the sportsbooks', casinos' and prediction markets' names, each public
#: (DraftKings and its Massachusetts entity Crown <state> Gaming, FanDuel, BetMGM, Caesars Sportsbook, Fanatics'
#: betting forms, ESPN BET, bet365, BetRivers, PrizePicks, Underdog's fantasy and sports forms, Kalshi, Polymarket,
#: the Chumba and Pulsz social casinos), and a LOTTERY PRIZE. A bare FANATICS or UNDERDOG is a retailer's or any
#: business's name, and CAESARS alone the casino company paying its vendors. Audit round 2, R2-B12 (R36; standard G3):
#: and the licensed sportsbooks the list missed, each public: Hard Rock Digital (Hard Rock Bet, glued or spaced), Greenwood
#: Racing's BetParx, Bally's Corporation's Bally Bet, PointsBet, Golden Nugget Online Gaming and the Fliff social
#: sportsbook. JACKPOT and WINNINGS left the list (R37): they hold beside a gambling word or outside a trade name
#: (_GAMBLING_NAME_WORDS).
_GAMBLING_PAYOUT = re.compile(
    r"(?<![A-Z])(?:DRAFT ?KINGS|CROWN (?:[A-Z]{2} )?GAMING|FAN ?DUEL|BET ?MGM|CAESARS SPORTSBOOK"
    r"|FANATICS (?:SPORTSBOOK|BETTING|BET|GAMING|CASINO)|ESPN ?BET|BET ?365|BET ?RIVERS|PRIZE ?PICKS"
    r"|UNDERDOG (?:FANTASY|SPORTS)|KALSHI|POLYMARKET|CHUMBA|PULSZ|LOTTERY PRIZES?"
    r"|HARD ?ROCK ?(?:BET|DIGITAL)|BET ?PARX|BALLY ?BET|POINTS ?BET|GOLDEN NUGGET ONLINE|FLIFF)\b"
)
#: Audit round 2, R2-B12 (R37): a casino's JACKPOT and WINNINGS, which hold beside a gambling word on the row
#: (_GAMBLING_CONTEXT) or anywhere but a customer's trade name (_trade_name: 'JACKPOT DIGITAL INC', a memo's 'JACKPOT
#: CANDLES').
_GAMBLING_NAME_WORDS = re.compile(r"(?<![A-Z])(?:JACKPOT|WINNINGS)\b")
_GAMBLING_CONTEXT = re.compile(
    r"(?<![A-Z])(?:CASINOS?|GAMING|SLOTS?|LOTTERY|POKER|BINGO|RACEWAY|RACETRACK|RACING|SPORTSBOOK|BETTING)\b"
)
#: Audit round 2, R2-B12 (R36; standard G3, G4): a lottery's prize (LOTTERY and a prize word anywhere on the row: '<STATE>
#: LOTTERY DES:PRIZE PMT'), unless the entry is the lottery's settlement with its retailer (a retailer word read on the
#: entry, never on the agency's name: 'LOTTERY COMMISSION' is many states' agency); and a sportsbook's, a casino's or an
#: online gaming payer's withdrawal or payout (the payer before the entry label, the word in the entry), which a brand
#: list can never complete (sportsbooks' payouts also come through processors).
_LOTTERY_WORD = re.compile(r"(?<![A-Z])LOTTERY\b")
_LOTTERY_PRIZE_WORD = re.compile(r"(?<![A-Z])(?:PRIZES?|WINNINGS?|JACKPOTS?)\b")
_LOTTERY_RETAILER_WORDING = re.compile(r"(?<![A-Z])(?:SETTLEMENT|SETTLMT|SWEEP|COMMISSIONS?|RETAILER)\b")
#: Review round 1 (R36): many states' lottery agency is a LOTTERY COMMISSION; on a row that prints no entry field its
#: name supplies no retailer word, so the agency's prize ('<STATE> LOTTERY COMMISSION PRIZE PAYMENT') holds as it does on
#: Bank of America's and Chase's layouts.
_LOTTERY_AGENCY_NAME = re.compile(r"(?<![A-Z])LOTTERY COMMISSION\b")
_BETTING_PAYER = re.compile(r"(?<![A-Z])(?:SPORTS ?BOOK|CASINO|BETTING|ONLINE GAMING)\b")
_BETTING_WITHDRAWAL = re.compile(r"(?<![A-Z])(?:WITHDRAWALS?|WITHDRAW|WDRL|PAYOUTS?|CASH ?OUT)\b")
#: The entry labels the payer before them is read up to (Bank of America's DES, Chase's CO ENTRY DESCR).
_ENTRY_LABEL = re.compile(r"\bDES\b|\bCO (?:ENTRY )?DESCR\b")
#: Audit B8 (I28, I44): a gambling payer, a claims administrator or a law firm paying a vendor's invoice from its
#: payables pays its vendor (§7.5's accounts-payable wording, _accounts_payable_wording, or these words), and a
#: lottery's settlement with its retailer (standard G4: the store sells tickets and cashes prizes) is no prize.
_VENDOR_PAYMENT_WORDING = re.compile(r"(?<![A-Z])(?:VENDORS?|INVOICES?|PAYABLES?)\b|\bINV\b|(?<![A-Z])INV ?\d")
#: §8.1 non_sale_purpose (audit B8: I44; the MCA principle: a legal windfall is no operating earning, standard G):
#: a lawsuit's, a class action's or a claims administrator's settlement, held for review (a law firm or a contractor
#: may earn such money). Read on the row before its receiver fields: SETTLEMENT ADMIN..., and the claims
#: administrators' names, each public (JND Legal Administration, KCC (only with LLC, CLASS or SETTLEMENT after it: three
#: letters are many companies' initials), Angeion, Simpluris, Rust Consulting, Kroll Settlement Administration, A.B.
#: Data). A bare SETTLEMENT is a processor's, a carrier's or an operating settlement and stays counted, never verified
#: (§8.6). A lawyer's or a client trust account's payer (IOLTA, ESQ, LAW, ATTORNEY: _TRUST_LAWYER_WORDS on the payer
#: region) paying SETTLEMENT PROCEEDS or FUNDS is held too. Audit round 2, R2-B12 (R37): LAWSUIT, LITIGAT..., CLASS
#: ACTION, DATA BREACH and the administrators Epiq and Verita (whose names are other businesses' too) hold beside a
#: settlement, claim or award word on the row (_LEGAL_CONTEXT) or anywhere but a customer's trade name (_trade_name:
#: '<NAME> LITIGATION SUPPORT LLC', 'VERITA HEALTH LLC'; never 'EPIQ SYSTEMS INC' or 'VERITA GLOBAL', whose other words
#: are _LEGAL_NAME_KEEP's). Review round 1: a claims administrator's or a restructuring unit's form words (SERVICES,
#: SOLUTIONS, RESTRUCTURING, GROUP) are keep words too ('EPIQ CORPORATE RESTRUCTURING LLC', 'CLASS ACTION SERVICES
#: LLC'); a name word of the payer's own beside them still reads as a trade name (a recorded residual, §20). Review
#: round 2: the settlement words are the classifier's own settlement spellings (_SETTLEMENT_CREDIT's SETTLE...,
#: SETTLMT, SETLMT, STLMT and STLMNT, kept in step by a test) and SETL, so 'DES:CLASS ACTION STLMT' holds by context
#: as 'DES:CLASS ACTION SETTLEMENT' does.
_LEGAL_SETTLEMENT = re.compile(
    r"(?<![A-Z])(?:SETTLEMENT ADMIN\w*|JND LEGAL|ANGEION|SIMPLURIS|RUST CONSULTING|KROLL SETTLEMENT|A B DATA)\b"
    r"|\bKCC(?= (?:LLC|CLASS|SETTLEMENT)\b)"
)
_LEGAL_SETTLEMENT_SPELLINGS = r"SETTLE\w*|SETTLMT|SETLMT|STLMT|STLMNT|SETL"
_LEGAL_NAME_WORDS = re.compile(r"(?<![A-Z])(?:LAWSUITS?|LITIGAT\w*|CLASS ACTION|DATA BREACH|EPIQ|VERITA)\b")
_LEGAL_CONTEXT = re.compile(rf"(?<![A-Z])(?:{_LEGAL_SETTLEMENT_SPELLINGS}|CLAIMS?|AWARDS?)\b")
_LEGAL_NAME_KEEP = re.compile(
    rf"(?<![A-Z])(?:{_LEGAL_SETTLEMENT_SPELLINGS}|CLAIMS?|AWARDS?|FUNDS?|ADMIN\w*|SYSTEMS|GLOBAL|CORPORATE"
    r"|SERVICES|SOLUTIONS|RESTRUCTURING|GROUP)\b"
)
_LAWYER_SETTLEMENT_PROCEEDS = re.compile(r"(?<![A-Z])SETTLEMENT (?:PROCEEDS|FUNDS?)\b")
#: §8.1 non_sale_purpose (audit B8, routed by the B7 review round 2, §20): DISB, the abbreviation of a disbursement,
#: on an owner-shaped payer (_OWNER_SHAPED_PAYER: '<NAME> PARTNERS LP DES:PARTNER DISB') is owner money, as its
#: DISBURSEMENT is. An ordinary payer's 'CASH DISB' is its payment to a vendor and keeps its reading. Audit round 2,
#: R2-B12 (R37): so is an owner-shaped payer's accounts-payable or vendor disbursement (_VENDOR_DISB, or §7.5's
#: accounts-payable or a vendor or invoice word: _vendor_payment), its payment of a vendor's invoice.
_DISB_ABBREVIATION = re.compile(r"(?<![A-Z])DISB(?![A-Z])")
_VENDOR_DISB = re.compile(r"(?<![A-Z])(?:AP|A P|ACCTS? PAY\w*|VENDOR|VNDR) DISB(?![A-Z])")
#: Audit round 2, R2-B12 (R37): a word a hold reads is a customer's trade name, never the payer's or the purpose's,
#: when it sits in a payer region that prints a company form (_TRADE_NAME_FORM) and a name word of its own besides the
#: reader's words, the forms, the fillers (_TRADE_NAME_NOT_A_NAME) and the reader's keep words, or on the payment's
#: purpose (_title_purpose_text) with a name word right after it (never a form, a keep word or a field's word,
#: _TRADE_NAME_NOT_AFTER). A name word is two letters or more, no digit. Read by _trade_name.
_TRADE_NAME_FORM = re.compile(r"\b(?:LLC|INC|CORP|CO|COMPANY|LTD|PLLC|LLP|LP|PLC)\b")
_TRADE_NAME_NOT_A_NAME = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLLC", "LLP", "LP", "PLC",
    "THE", "OF", "AND", "FOR", "YOUR", "US", "USA", "NA", "DBA", "FBO", "HQ",
})
_TRADE_NAME_NOT_AFTER = frozenset({"CONF", "REF", "ID", "TRN", "PMT", "PAYMENT", "PAYOUT"})
_TRADE_NAME_WORD = re.compile(r"[A-Z]{2,}")
#: Audit round 2, R2-B12 review round 1 (R37): a word right after a hold word on the purpose that names the purpose,
#: never a trade name: a win, a prize or a bonus; a withdrawal, a cash-out, a transfer, proceeds, a recovery, money,
#: funds, a check, a distribution, a disbursement, a deposit, a refund or a reimbursement; a payment or a payout; the
#: legal reader's settlement, claim and award words; a share, a sale, a balance or an account; a coin; a preposition,
#: a possessive or a time word ('FOR JACKPOT WIN', 'OBI LAWSUIT PROCEEDS', 'DES:KRAKEN WITHDRAWAL', 'FOR WINNINGS FROM
#: BET', 'FOR WINNINGS LAST NIGHT'), so the occurrence before it holds. Read whole (fullmatch) by _trade_name's
#: purpose arm only; a name word ('FOR JACKPOT CANDLES', 'DES:LITIGATION SUPPORT') keeps the trade-name reading.
#: Review round 2: and the legal reader's settlement spellings (_LEGAL_SETTLEMENT_SPELLINGS), the payment cuts the
#: statements print (PYMNT, PMNT, PAYMNT, PAYMT, PYMMT and their plurals, PAYMEN, PAYME, PAYM, PYM), a handpay, a
#: distribution's, proceeds' or a compensation's cut (DIST, DISTR, PROC, PRCDS, COMP), a judgment, a redemption, a bet
#: or a wager, a fantasy contest, a pool, a lotto or a raffle, and a rail, a currency or a staking reward ('OBI KRAKEN
#: USD', 'DES:KRAKEN ACH'). The list stays closed: a row only this arm spares counts and never proves
#: (purpose_trade_name).
_TRADE_NAME_PURPOSE_WORD = re.compile(
    r"WINS?|WON|WINNERS?|WINNINGS?|PRIZES?|BONUS\w*|JACKPOTS?"
    r"|WITHDRAW\w*|WDRLS?|WD|CASH\w*|TRANSF\w*|TRNSFR|XFE?RS?|TFR|PROCEEDS?|RECOVER\w*|MONEY|MONIES|FUNDS?|FUNDING"
    r"|CHECKS?|CHEQUES?|CHK|DISTRIB\w*|DISBURS\w*|DISB|DEPOSITS?|DEP|REFUNDS?|REIMB\w*|REBATES?"
    r"|PAYMENTS?|PAYOUTS?|PAY|PAID|PMTS?|PYMTS?|CLAIMS?|AWARDS?"
    rf"|{_LEGAL_SETTLEMENT_SPELLINGS}"
    r"|PYMNTS?|PMNTS?|PAYMNTS?|PAYMTS?|PYMMTS?|PAYMENS?|PAYME|PAYM|PYM"
    r"|HANDPAYS?|DISTR?|DISTRO|PROC|PRCDS|COMP|COMPENSAT\w*|JUDG\w*|REDEMPT\w*|REDEEM\w*"
    r"|BETS?|WAGER\w*|PARLAYS?|FANTASY|ODDS|GAMBL\w*|POOLS?|SUPERBOWL|LOTTO|RAFFLES?"
    r"|ACH|EFT|WIRE|USD|CAD|REWARDS?|STAK\w*"
    r"|SHARES?|SPLIT|SALES?|SOLD|BALANCE|ACCOUNTS?|ACCT|BTC|ETH|BITCOIN|USDC|USDT"
    r"|FROM|TO|IN|ON|AT|BY|WITH|MY|OUR|HIS|HER|THEIR|THIS|THAT|LAST|NEXT|TODAY|TONIGHT|YESTERDAY"
)
#: Audit round 2, R2-B12 (R37): the owner-money platforms whose names are other businesses' too (a robotics maker, a
#: cleaner, a services firm): KRAKEN, UPHOLD and PAXOS hold, when no other platform is named, only outside a customer's
#: trade name (_trade_name; never 'UPHOLD HQ INC' or 'PAXOS TRUST CO', whose other words are _PLATFORM_NAME_KEEP's).
_PLATFORM_NAME_WORDS = re.compile(r"(?<![A-Z])(?:KRAKEN|UPHOLD|PAXOS)\b")
_PLATFORM_NAME_KEEP = re.compile(
    r"(?<![A-Z])(?:TRUST|TECHNOLOGY|GLOBAL|DIGITAL|EXCHANGE|PAYWARD|INTERACTIVE|CRYPTO)\b"
)
#: §8.1, S4.2 review (I6b): §7.5's investment words BROKERAGE, SECURITIES and WEALT join the owner money group (the
#: standing rule: owner money never becomes revenue), except on a row that prints §7.5's accounts-payable or
#: vendor-payment wording (_accounts_payable_wording; S4.2 fix measurement): a wealth, brokerage or securities firm
#: paying a vendor from its payables. Such a row is counted and flagged, never verified: §7.5's remittance veto reads
#: the same words, and Q5 and Q6 refuse them as proof (CreditFacts.refused_word).
_INVESTMENT_PURPOSE = re.compile(r"(?<![A-Z])(?:BROKERAGE\w*|SECURITIES\b|WEALT\w*)")
#: §8.1: a healthcare payer's member or premium credit. A3-H review: a premium word the entry field prints on a row
#: _premium_coded reads is no hold here; that row is counted and flagged as a named payer Q5 and Q6 refuse.
_HEALTHCARE_MEMBER_WORDS = re.compile(
    r"(?<![A-Z])(?:REIMB\w*|MEMBER\b|SUBSCRIBER\b|PREMIUM\b)|\bMBR\b"
)
#: §8.6 Q6c (A3-H): a premium-coded entry (PREM, PREMIUM, and the Chase layout's glued PREMSEC), a commission or a
#: premium refund the text cannot tell apart, never a claim payment for the provider's services; and the insurer's
#: abbreviation a payer region prints (_INSURER_NAME reads the spelled-out words). A3-H review: a commission word
#: beside it keeps the entry's reading, and the public health programs (the government's own payers and Medicare's
#: administrative contractors) are never read.
_PREMIUM_CODED = re.compile(r"(?<![A-Z])(?:PREM|PREMIUMS?)(?:SEC)?\b")
_INSURER_ABBREVIATION = re.compile(r"\bINS\b")
_COMMISSION_WORD = re.compile(r"(?<![A-Z])(?:COMMS?|COMMISSIONS?)\b")
_PUBLIC_HEALTH_PAYERS = frozenset({
    "Medicare", "State Medicaid program", "TRICARE", "VA Community Care", "Noridian", "Palmetto GBA",
    "Novitas Solutions", "WPS Health Solutions", "National Government Services", "CGS Administrators",
    "First Coast Service Options",
})
#: §8.4, T13: an account designation printed by a named transfer. Audit round 2, R2-B09 (R45): and the checking
#: abbreviations CHCKING, CHKING and CKG ('COMM ONLINETRANSFER FROM COMM BUS CHCKING ...'), which are never a transfer's
#: counterparty words either (_ACCOUNT_WORDS).
_ACCOUNT_DESIGNATION = re.compile(
    r"(?<![A-Z])(?:CHECKING|CHKG|SAVINGS|SAVING|SVGS|MONEY MARKET|ACCOUNT|ACCT|EVERYDAY)\b|\b(?:CHK|SAV|MMA|DDA)\b"
    r"|\bX{2,}\d{2,}\b|(?<![A-Z])ENDING (?:IN )?\d{3,}\b"
    r"|(?<![A-Z])(?:CHCKING|CHKING)\b|\bCKG\b"
)
_ACCOUNT_WORDS = frozenset({
    "CHECKING", "CHK", "CHKG", "SAVINGS", "SAVING", "SAV", "SVGS", "MONEY", "MARKET", "MMA", "DDA", "ACCOUNT", "ACCT",
    "EVERYDAY", "CHCKING", "CHKING", "CKG",
})
#: T13 (audit B2: I01): a bare 'FROM <3+ digits>' designates an account too ('ONLINE TRANSFER FROM 1234 <name>'),
#: unless the digits start a numbered company's name (§5.2, T11: 'TRANSFER FROM 1234567 ONTARIO INC').
_FROM_ACCOUNT_DIGITS = re.compile(r"(?<![A-Z])FROM (?=\d{3,}\b)")
#: §8.4, T13 (audit B2: I21): Square prints a move from one of the holder's savings folders as 'TRANSFER IN <folder>'
#: ('TRANSFER IN GENERAL SAVINGS', 'TRANSFER IN TAX', 'TRANSFER IN RAINY DAY', 'TRANSFER IN RENT'): on a Square
#: statement, a folder name with no company form designates the holder's own account. Never read on another bank
#: (Wealthsimple prints its memo there: 'TRANSFER IN <memo>'). Audit round 2, R2-B11 (R29, no behaviour change): the
#: B02 brief's person test is not applied. Square prints an outside sender in Details before its activity type
#: ('<sender> TRANSFER IN', which is read like any named transfer), so only a folder move prints TRANSFER IN first, and
#: a folder named for a person is still the holder's own money.
_SQUARE_BANK = re.compile(r"(?<![A-Z])SQUARE\b")
_SQUARE_FOLDER_TRANSFER = re.compile(r"^TRANSFER IN (?!FROM\b)(?P<folder>[A-Z]+(?: [A-Z]+)*)$")


def _account_designation(row: str, bank: str | None = None) -> bool:
    """§8.4, T13: the row prints an account designation (_ACCOUNT_DESIGNATION); audit B2: or a bare 'FROM <3+ digits>'
    that starts no numbered company (_FROM_ACCOUNT_DIGITS), or Square's savings-folder transfer (_square_folder)."""
    if _ACCOUNT_DESIGNATION.search(row) is not None or _square_folder(row, bank):
        return True
    classifier = _classifier()
    return any(
        classifier._NUMBERED_COMPANY_REGION.match(row[found.end():]) is None
        for found in _FROM_ACCOUNT_DIGITS.finditer(row)
    )


def _square_folder(row: str, bank: str | None) -> bool:
    """§8.4, T13 (audit B2: I21): on a Square statement, 'TRANSFER IN <folder>' whose folder prints no company form."""
    if not bank or _SQUARE_BANK.search(bank.upper()) is None:
        return False
    found = _SQUARE_FOLDER_TRANSFER.match(row)
    return found is not None and not _classifier().company_form(found.group("folder"))


#: §8.5: the loose wire words, for tiering only (a row the 5.5 wire vetoes read as a wire is one too: _channel).
_LOOSE_WIRE = re.compile(
    r"(?<![A-Z])(?:WIRE|FEDWIRE|FED WIRE|CHIPS CREDIT|SWIFT|FOREIGN REMITTANCE|WT FED|FED REF)\b|\bIWT\b"
)
#: §8.5 (A3): on a row that prints transfer wording, the loose wire words and a bare CHIPS ('INCOMING CHIPS TRANSFER')
#: name the wire channel (_channel). A bare CHIPS elsewhere may be a payer's own word, so _LOOSE_WIRE keeps CHIPS CREDIT.
_TRANSFER_WIRE_WORDS = re.compile(_LOOSE_WIRE.pattern + r"|(?<![A-Z])CHIPS\b")
#: §8.5: a sender that names a bank, a title or an escrow firm never verifies by repetition. Audit round 3, R3-B07
#: (R3-14): BANKING and the non-English bank words BANCA, BANQUE, BANCAIRE and SPARKASSE too, beside BANCO.
_BANK_OR_TITLE_SENDER = re.compile(
    r"\b(?:BANK|BANKING|BANCO|BANCA|BANQUE|BANCAIRE|SPARKASSE|BANCORP|N A|TRUST COMPANY|CREDIT UNION|FCU|SAVINGS"
    r"|TITLE|ESCROW|CLOSING|SETTLEMENT)\b"
)
#: §8.6: the verification-only words: sales wording often enough to count, never proof. Audit round 3, R3-B10 review
#: round 2 (findings 1 and 2): SETTLEMENT alone again, as before the batch (review round 1's short spellings SETTLMT and
#: STLMT are taken out): a row the settlement exemption releases is refused as proof by its own flag
#: (CreditFacts.settlement_released), whatever slot or boundary its word sits in, and a third party's short spelling
#: keeps the reading it had.
_VERIFICATION_ONLY = re.compile(
    r"(?<![A-Z])(?:SETTLEMENT\b|TAXES\b|FEES\b|SUBSCRIPTIONS?\b|DISCOUNT\w*|COMM?ISS?IONS?\b"
    r"|COMPENSATION\b|EXPENSES?\b|AFFILIATE\b|PERSONAL\b|CLOSING\b|SUPPLY CHAIN\b"
    r"|EARLY PAY(?:MENT)?\b|ALLOWANCES?\b|SHORTAGES?\b)"
    r"|\b(?:TAX|IRS|CRA|FEE|SCF|RMA)\b"
)
_ENTRY_VERIFICATION_ONLY = re.compile(r"(?<![A-Z])(?:FLOOR ?PLAN\b|FLOORPLAN\b|EQUIP\w*)|\bVIN\b")
#: §8.6 (final review I1): a PPD or WEB entry is read only in the SEC code's own slot: Chase's 'SEC <code>' (its glued
#: 'HCCLAIMPMTSEC CCD' split by revenue_text), the code printed right before its TRACE or ID field when a line wrap
#: drops the label ('... PAYMENT PPD TRACE', '... 540302 WEB ID <id>'), the code Bank of America prints after the
#: company id or at the row's end ('CO ID <id> PPD', 'ID <id> PPD'), and a layout's 'ACH <code>'. Never a name or a
#: receiver field: each receiver field's value is removed first, up to the next CO ID, TRN, TRACE or SEC field (not
#: at a code word, so 'INDN:CONTOSO WEB STUDIO LLC CO ID <id> CCD' is a CCD entry).
_CONSUMER_ENTRY = re.compile(
    r"\bSEC (?:PPD|WEB)\b|\b(?:PPD|WEB) (?:TRACE|ID)\b|\bID \S+ (?:PPD|WEB)\b|\bACH (?:PPD|WEB)\b"
)
_RECEIVER_THROUGH_NEXT_FIELD = re.compile(
    rf"\b(?:{'|'.join(RECEIVER_FIELD_LABELS)})\b.*?(?=\b(?:CO ID|TRN|TRACE|SEC)\b|$)"
)


#: §8.6 (re-review N1): the code a layout prints as the row's last word, after a receiver value that no later field
#: ends ('... INDN:CONTOSO BAKERY LLC PPD').
_TRAILING_CONSUMER_CODE = re.compile(r" (PPD|WEB)$")
#: §8.6 (re-review N1): the code printed right before Bank of America's DES label, after a company form or a
#: reference token ('NORTHWIND SUPPLY LLC PPD DES:...'); after a name word it is the payer's name ('NORTHWIND WEB').
#: FW wave 3: PPD is never a name word, so it is the code after any word ('NORTHWIND SUPPLY PPD DES:...').
_CODE_BEFORE_DES = re.compile(r"(\S+) (PPD|WEB) DES\b")
_CODE_AFTER_TEMPLATE = re.compile(r"(?:PPD|WEB)\b")


def consumer_entry(text: str, account_name: str | None = None) -> bool:
    """§8.6 (final review I1): the row prints a PPD or WEB entry in its SEC code's slot (_CONSUMER_ENTRY), read on
    the row with every receiver field's value removed (_RECEIVER_THROUGH_NEXT_FIELD). Re-review N1: and in three more
    slots, still never inside a name or a receiver field: the row's last word after a receiver value that no later field
    ends, unless it is the last word of the holder's own name (`account_name`: 'INDN:CONTOSO WEB' is the holder); the
    code before DES after a company form or a reference token (_CODE_BEFORE_DES); and the code right after the
    posting label a row starts with ('ACH CREDIT PPD <payer>', the classifier's revenue template prefixes)."""
    classifier = _classifier()
    if _CONSUMER_ENTRY.search(_RECEIVER_THROUGH_NEXT_FIELD.sub(" ", text)) is not None:
        return True
    trailing = _TRAILING_CONSUMER_CODE.search(text)
    if trailing is not None:
        receiver = None
        for found in _RECEIVER_THROUGH_NEXT_FIELD.finditer(text):
            receiver = found
        holder = classifier.account_name_text(account_name).split() if account_name else []
        if (
            receiver is not None and receiver.end() == len(text)
            and len(receiver.group(0).split()) > 2
            and not (holder and holder[-1] == trailing.group(1))
        ):
            return True
    before_des = _CODE_BEFORE_DES.search(classifier._before_receiver(text))
    if before_des is not None and (
        before_des.group(2) == "PPD"
        or classifier._BANK_COMPANY_FORM.fullmatch(before_des.group(1)) or classifier._is_reference_token(before_des.group(1))
    ):
        return True
    template = classifier._REVENUE_TEMPLATE_PREFIX.match(text)
    return template is not None and template.end() > 0 and _CODE_AFTER_TEMPLATE.match(text, template.end()) is not None


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
#: §8.10: the lender and financing debit states payer_debited_as_lender reads (and, final review I5, the states
#: whose card purchase passes 6 and 7 still read: counter_debits, which pass 6 calls since audit B4).
LENDER_DEBIT_STATES = frozenset({"confirmed_lender", "potential_lender"}) | FINANCING_STATES
#: §7.5, the standing rule (S4.2 review I6b): brokerage, investing and crypto-exchange platforms (the registry's
#: OWNER_MONEY_PLATFORMS, §7.0: a table that names companies lives there). A credit from one is the owner's own money
#: coming back (owner money never becomes revenue): held as non_sale_purpose. The classifier's consumer savings and
#: investing originators (_SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS) are read too.
_OWNER_MONEY_PLATFORMS = re.compile(OWNER_MONEY_PLATFORMS)
#: §8.1, T4 (audit B6: I23; Q6 "lenders never count"): a bank that lends to small businesses on its own account or as
#: a fintech's lender of record (the registry's LENDING_BANK_CREDIT_PAYERS) named as the payer: held as
#: financing_named_payer (lending_bank_payer).
_LENDING_BANK_PAYER = re.compile(LENDING_BANK_CREDIT_PAYERS)
#: §8.1, Q8 (audit B6: I49): an earned-wage access provider's push (the registry's EARNED_WAGE_ACCESS_PAYERS) is a
#: worker's wages from another company: pay wording (_pay_wording), held as payroll_or_salary.
_EARNED_WAGE_ACCESS = re.compile(EARNED_WAGE_ACCESS_PAYERS)
#: §8.1 (audit B6: I49): the instant-payment rail labels a layout prints before the payer's name, never the payer:
#: PNC's INSTPMNTIN at the start of the payer region, and the RTP network's RTP CREDIT at the start of a row whose
#: payer region is empty (not RTP CREDIT FROM, whose sender the person-to-person readers read). The counter-debit holds
#: read the name after them (_counter_region), so an app's advance no alias lists is read against the app's debits.
_INSTANT_PAYMENT_LABEL = re.compile(r"^INSTPMNTIN\s+")
_RTP_CREDIT_NAME = re.compile(r"^RTP CREDIT\s+(?!FROM\b)(\S.*)$")
#: §15, §19 OQ4 (S4.2 review I6a): the payers of the deferred family items (the registry's
#: SECTION_15_DEFERRED_PAYERS), which stay counted and flagged until the owner rules on each: Q5 and Q6 never verify
#: them, they never count toward a Q5 or Q6 repeat, and on a wire or an ACH or EFT row their reason is
#: named_payer_purpose_refused (S4.2 re-review: a payer Q5 and Q6 refuse as proof, §8.9; never "One-off payer", as a
#: deferred source often repeats). The registry's own deferred sources are left to the registry by _left_to_its_family.
_SECTION_15_DEFERRED_PAYERS = re.compile(SECTION_15_DEFERRED_PAYERS)
#: Owner ruling 2026-10-02 (the underwriter's Q11 (a), "Count as true revenue and flag it"; audit I18's construction
#: DRAW; §8.1, §8.10): the reason of a builder's progress draw, counted and flagged, never verified
#: (construction_progress_draw).
CONSTRUCTION_PROGRESS_DRAW_REASON = "construction_progress_draw"
#: Q11 (a): DRAW or DRAWS as _NON_SALE_PURPOSE reads it (DRAWDOWN keeps its financing reading).
_DRAW_WORD = re.compile(r"(?<![A-Z])DRAWS?\b")
#: Q11 (a): a builder named as the payer: a builder, a homebuilder, a construction firm or a contractor (BUILD alone is
#: a builder's name word, '<NAME> BUILD GROUP INC'; CONST and CONSTR are the cut spellings a sixteen-character
#: originator field prints). Never a builders' supplier, exchange, association or insurer ('BUILDERS FIRSTSOURCE',
#: 'CONTRACTORS INSURANCE'). A homebuilder named HOMES too, never a nursing, funeral, care, group, foster, senior or
#: retirement home, a mobile or manufactured home seller, nor HOMES FOR SALE or FOR RENT. BUILDING is no builder (a
#: building's owner, a building-supply or building-maintenance firm, a building-and-loan association); DEVELOPMENT,
#: DEVELOPERS and PROPERTIES are deliberately not builder words (§17.1, the owner's follow-up on a developer's draw).
_BUILDER_PAYER = re.compile(
    r"(?<![A-Z])(?:BUILDERS?|BUILD|HOMEBUILDERS?|HOMEBUILDING|CONSTRUCTION|CONSTRUCTORS?|CONSTR|CONST|CONTRACTORS?"
    r"|CONTRACTING)\b"
    r"(?! (?:SUPPLY|SUPPLIES|FIRSTSOURCE|FIRST SOURCE|HARDWARE|EXCHANGE|ASSOCIATION|ASSN|MUTUAL|INSURANCE|RISK)\b)"
    r"|(?<![A-Z])(?<!NURSING )(?<!FUNERAL )(?<!MOBILE )(?<!MANUFACTURED )(?<!CARE )(?<!GROUP )(?<!FOSTER )"
    r"(?<!SENIOR )(?<!RETIREMENT )HOMES\b(?! FOR (?:SALE|RENT)\b)"
)
#: Audit round 3, R3-B15 (R3-08; Q11 (a): "when the payer is a builder"): a draw's purpose phrase, CONSTRUCTION,
#: CONSTR or CONST directly followed by DRAW or DRAWS. On a row that prints no payer-name field the payer region holds
#: the entry words ('<NAME> CONST DRAW', TD's whole 'CONSTRUCTION DRAW'), so the phrase is the entry's purpose, never
#: the payer's builder word (_label_less_builder_word). R3-B15 review round 1 (finding 4): BUILD too ('<NAME> BUILD
#: DRAW'), so a root-less lender's entry BUILD DRAW names no builder either.
_DRAW_PURPOSE_PHRASE = re.compile(r"(?<![A-Z])(?:CONSTRUCTION|CONSTR|CONST|BUILD) DRAWS?\b")
#: Q11 (a): a loan's, a credit line's, a mortgage's, an escrow's or a title's draw, an owner's, member's, partner's or
#: shareholder's draw, a personal, line, credit, advance, capital, equity or cash draw, and a draw on a line, a LOC, a
#: credit facility or an account: the business's own loan or money, never a builder's progress draw. R2-OW06 review
#: round 1: nor a commission draw (COMM, COMMISSION or COMMISSIONS DRAW), a salesperson's advance against its
#: commissions.
_OWN_LOAN_DRAW = re.compile(
    r"(?<![A-Z])(?:LOANS?|LOC|HELOC|LINE OF CREDIT|CREDIT LINE|MORTGAGE|MTG|ESCROW|TITLE)\b"
    r"|(?<![A-Z])(?:OWNERS?|MEMBERS?|PARTNERS?|SHAREHOLDERS?|PERSONAL|LINE|CREDIT|ADVANCE|CAPITAL|EQUITY|CASH|COMM"
    r"|COMMISSIONS?) DRAWS?\b"
    r"|(?<![A-Z])DRAWS? ON (?:THE |A )?(?:LINE|LOC|CREDIT|FACILITY|ACCOUNT)\b"
)
#: Q11 (a), R2-OW06 review round 1: a realty firm's words on the payer region (REALTY, REALTOR(S), REAL ESTATE): a
#: realty firm named '<NAME> HOMES REALTY' or '<NAME> BUILDERS REALTY' is no builder (the brief's non-builders), so its
#: DRAW keeps today's non-sale hold.
_REALTY_PAYER = re.compile(r"(?<![A-Z])(?:REALTY|REALTORS?|REAL ESTATE)\b")
#: Owner ruling 2026-10-02 (Q8; §8.9): the lease-to-own and patient financiers whose merchant payouts are the merchant's
#: sales (the registry's CUSTOMER_FINANCING_PAYERS: ledger entity -> its spelling on the payer region), read by
#: _customer_financier; and their names anywhere on the row without the receiver field's value
#: (CUSTOMER_FINANCING_NAMES), which keep a row from Q5 and Q6 (_never_q5_or_q6).
_CUSTOMER_FINANCING_PAYERS = {entity: re.compile(pattern) for entity, pattern in CUSTOMER_FINANCING_PAYERS.items()}
_CUSTOMER_FINANCING_NAMES = re.compile(CUSTOMER_FINANCING_NAMES)
#: Owner ruling 2026-10-02 (Q8): the class-action words that make a financier's credit consumer-side (Progressive
#: Leasing's data-breach settlement paid to its customers): Q8's own claim veto, read whatever R2-B12's
#: legal_settlement reads.
_LEGAL_SETTLEMENT_WORDS = re.compile(r"(?<![A-Z])(?:BREACH|LITIGAT\w*|CLASS ACTION)\b")
#: Owner ruling 2026-10-02 (Q8): the channels a financier's merchant payout comes on (never a check, a cash or branch
#: deposit or a person-to-person rail).
_CUSTOMER_FINANCING_CHANNELS = frozenset({"wire", "ach_eft", "other"})
#: Owner ruling 2026-10-02 (Q8; §5.3): the reasons of a financier's payout and of its one-off lump sum.
CUSTOMER_FINANCING_PAYOUT = "customer_financing_payout"
CUSTOMER_FINANCING_LUMP_SUM = "customer_financing_lump_sum"
#: Owner ruling 2026-10-02 (the underwriter's Q9, part (c); §5.3, §8.7): the reason, and the revenue method, of a lender
#: paying the business for its services (a repair, a recovery, a commission): counted and flagged, never verified. This
#: batch (R2-OW05) gives it to a listed auto lender's payables-only credit on a statement with no dealer evidence
#: (_lender_service_never_verified).
LENDER_PAID_FOR_SERVICES = "lender_paid_for_services"
#: Owner ruling 2026-10-02 (the underwriter's Q9, "Keep them as true revenue", option 2; §5.3, §8.1; R2-OW09): the
#: reasons of T4's financing-root hold lifted (finance_named_release): (a) a customer whose own name carries a finance
#: word, paying on a line that prints invoice, accounts-payable or vendor-payment wording, and (b) a rent LEASE received
#: by a business in leasing or property; (c) is LENDER_PAID_FOR_SERVICES. Each counted and flagged, never verified,
#: never toward a Q5 or Q6 repeat.
FINANCE_NAMED_CUSTOMER = "finance_named_customer"
LESSOR_RENT = "lessor_rent"
#: Q9 (a), (c): a commission is service wording too (the orchestrator's extension under the underwriter's Q10,
#: "commissions that reach the agency's operating account"; not Q9's own words), read on the row before its receiver
#: fields, the holder's names removed.
_SERVICE_COMMISSION = re.compile(r"(?<![A-Z])COMMISSIONS?\b")
#: Q9: a line printing loan proceeds or a disbursement is never released, whatever its wording.
_Q9_REFUSAL = re.compile(r"(?<![A-Z])(?:PROCEEDS|DISBURS\w*)\b")
#: Q9 (b): the rent sense of LEASE: never before a fund, a financing, a loan, an advance, proceeds, a buyout, a purchase
#: or TO OWN (a lease-to-own or lease financing, Q8's or T4's).
_RENT_LEASE = re.compile(
    r"(?<![A-Z])LEASE\b(?! ?(?:FUND\w*|FINANC\w*|LOANS?|ADVANCES?|PROCEEDS|BUY ?OUT\w*|PURCH\w*|TO OWN))"
)
#: Q9 (c): the payer's name reads as a lender's: the label lender_paid_for_services, never a tier (a label only).
#: FINANCIAL and ADVANCED are left out (they read as a customer's); a customer whose name starts with a whole-word
#: ADVANCE, CAP, ADV or CREDIT (ADVANCE AUTO PARTS) takes this label, its tier the same (a documented label limit).
_LENDER_NAME_WORD = re.compile(
    r"(?<![A-Z])(?:FUND(?:ING|S|ED|ER|ERS)?|LEND(?:ING|ERS?)?|LOANS?|CAPITAL|CAPIT|CAPTL|CAP|CASH ADV\w*|ADVANCES?|ADV"
    r"|MCA|RTR|ACCEPTANCE|SERVICING|SERVICER|FINANCE|FINANCING|MORTGAGE|MTG|CREDIT|LEASING|PORTFOL\w*)(?![A-Z])"
    r"|[A-Z]CREDIT|CREDIT[A-Z]"
)
#: Q9 (b), the lessor's third arm: rent wording on a posted credit (never a car rental's RENT A CAR).
_RENT_RECEIVED = re.compile(r"(?<![A-Z])(?:RENT|RENTS|RENTAL|RENTALS)\b(?! ?A ?CAR\b)")
#: Q9 (b), the lessor's first arm: a leasing or property trade word on one of the holder's names.
_PROPERTY_TRADE = re.compile(
    r"(?<![A-Z])(?:REALTY|REAL ESTATE|PROPERTY|PROPERTIES|PROPS|LEASING|RENTALS?|LANDLORD|APARTMENTS?|APTS|LOFTS"
    r"|TOWNHOMES|STORAGE|PARKING|PLAZA|MALL|ESTATES|PROPERTY MANAGEMENT|PROP MGMT)\b"
)
#: Q9: a payer's company form; finance_named_release reads its FIRST match on the payer reading (a root after it, on a
#: layout with no entry label, is a purpose, never the name; (b)'s rent memo stands after it).
_Q9_FORM_WORD = re.compile(r"\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC)\b")
#: Q9: the counted reasons a released row keeps (the relabel never renames them): the owner batches' specific counted
#: reasons and the platform, payout, numbered-company and unread-payer readings.
_Q9_KEEPS = frozenset({
    "numbered_company_payer", "factoring_payout", "payout_credit_entity", "platform_unconfirmed", "payer_text_not_read",
    "customer_financing_payout", "construction_progress_draw", "insurer_paid_for_services", LENDER_PAID_FOR_SERVICES,
})
#: Owner ruling 2026-10-02 (Q9 (c'); §8.7): dealer evidence on a statement's rows: a floor-plan form printed anywhere
#: (FLOORPLAN, FLOOR PLAN), beside the registry's floor-plan financiers (FLOOR_PLAN_ALIASES). Audit round 3, R3-B14
#: (R3-52): the form's own words only, FLOORPLAN(S) and FLOOR PLANNING, never FLOORPLANNER (a planning tool's
#: subscription) or FLOOR PLANKS (flooring). Review round 1 (finding 6): and the glued words a narrow field prints,
#: FLOORPLANINT, FLOORPLANPAYOFF, FLOORPLANADV and FLOORPLANXPRESS.
_FLOOR_PLAN_FORM = re.compile(r"(?<![A-Z])FLOOR ?PLAN(?:S|NING|INT|PAYOFF|ADV|XPRESS)?\b")
#: Audit round 3, R3-B14 (R3-52; the underwriter's Q9 (c), "a lender paying a business for services counts as 'lender
#: paid for services', never verified"): a floor-plan financier's credit printing service wording (a vendor payment, a
#: repossession, a recovery, a tow, a transport, an inspection, a commission) pays the business for its services and is
#: no dealer evidence; every corpus floor-plan credit is a VIN-bearing dealer advance, which still is.
_FLOOR_PLAN_SERVICE_CREDIT = re.compile(
    r"(?<![A-Z])(?:VENDOR ?(?:PMT|PAY|PAYMENT)|REPO|REPOS|REPOSSESS\w*|RECOVER\w*|TOW(?:ING|S)?|TRANSPORT\w*|INSPECT\w*"
    r"|COMMISSIONS?)\b"
)
#: Owner ruling 2026-10-02 (Q9 (c'); §8.7): a dealer's name on the holder's name (the Q11 card's holder reading, shared
#: with R2-OW06): a vehicle or equipment noun before a dealer's trade word, or a dealership's own word. Never read where
#: the same name prints a recovery, repossession, towing or collateral word (_DEALER_HOLDER_VETO): a repossession or
#: towing agency named '<NAME> AUTOMOTIVE RECOVERY' is no dealer.
_DEALER_HOLDER_NAME = re.compile(
    r"(?<![A-Z])(?:AUTOS?|CARS?|TRUCKS?|TRAILERS?|EQUIPMENT|TRACTORS?|MOTOR|RVS?|BOATS?|MARINE|MACHINERY|POWERSPORTS"
    r"|MOTORSPORTS) (?:SALES|DEALERS?|DEALERSHIP|MART|OUTLET|EXCHANGE|SUPERSTORES?)\b"
    r"|(?<![A-Z])(?:MOTORS|AUTOMOTIVE|AUTO GROUP|AUTO PLAZA|AUTO MALL|DEALERSHIP|CAR LOT)\b"
)
_DEALER_HOLDER_VETO = re.compile(r"(?<![A-Z])(?:RECOVER\w*|REPO|REPOS|REPOSSESS\w*|TOWING|TOW|COLLATERAL)\b")
#: Owner ruling 2026-10-02 (Q9 (c'); §7.8, §8.7): the dealer-only wholesale auctions' names on a posted debit (the
#: registry's WHOLESALE_AUCTION_REFUND_NAMES: MANHEIM, ACV AUCTIONS, OPENLANE or BACKLOT CARS), a purchase there being
#: dealer evidence.
_WHOLESALE_AUCTION_DEBIT_NAMES = tuple(re.compile(pattern) for pattern in WHOLESALE_AUCTION_REFUND_NAMES.values())
#: Owner ruling 2026-10-02 (the underwriter's Q11 (b), "Don't count as true revenue and go straight to non-revenue";
#: audit I45; §8.1, §8.10): the method, and the non_revenue reason code, of a non-dealer's asset-sale proceeds.
ASSET_SALE_METHOD = "asset_sale_proceeds"
#: Q11 (b): a seller's word on a platform's payout.
_SELLER_WORD = re.compile(r"(?<![A-Z])(?:SELLERS?|CONSIGN\w*|PAYOUTS?|PROCEEDS)\b")
#: Q11 (b): the seller's words a platform's region may print after its name ('CARVANA PAYOUT', 'RITCHIE BROS SELLER
#: PAYOUT'), which asset_sale_platform reads past.
_ASSET_SALE_TAIL_WORDS = frozenset({"PAYOUT", "PAYOUTS", "SELLER", "SELLERS", "PROCEEDS", "CONSIGNOR", "CONSIGNMENT"})
#: Q11 (b): a platform paying for a service (a haul, a repair, a commission, a rent), never a seller's payout.
_PLATFORM_SERVICE_WORDS = re.compile(
    r"(?<![A-Z])(?:TRANSPORT\w*|HAUL\w*|TOW(?:ING|S)?|DELIVER\w*|FREIGHT|SHIPPING|LOGISTIC\w*|LABOR|REPAIR\w*"
    r"|RECON\w*|DETAIL\w*|INSPECT\w*|COMMISSIONS?|FEES?|REIMB\w*|REBATES?|SERVICES?|STORAGE|MARKETING|ADVERTIS\w*"
    r"|RENT\w*|LEASE)\b"
)
#: Q11 (b): a holder whose trade serves the platforms (a hauler, a transporter, a repair, reconditioning or glass shop,
#: a staffing firm, a towing or wrecker service): a platform's payment with no seller word is its fee, never a sale.
_PLATFORM_VENDOR_HOLDER = re.compile(
    r"(?<![A-Z])(?:TRANSPORT\w*|TRUCKING|HAUL\w*|LOGISTIC\w*|CARRIERS?|FREIGHT|DELIVER\w*|EXPEDIT\w*|COURIER\w*"
    r"|DETAIL\w*|RECON\w*|INSPECT\w*|GLASS|TIRES?|REPAIR\w*|MECHANIC\w*|DRIVERS?|STAFFING|TOW|TOWING|WRECKERS?)\b"
)
#: Q11 (b): the vehicle and heavy-equipment nouns, whose sale reads through an invoice reference, and the generic ones
#: (EQUIPMENT, EQUIP, MACHINERY) that many trades sell and invoice. R2-OW06 review round 1: FLEET alone is no asset
#: noun of a sale ('FLEET SALE' is a fleet card's settlement wording, a fuel merchant's revenue); a fleet's vehicles or
#: trucks still read through their noun ('SALE OF FLEET VEHICLES', 'FLEET TRUCK SALE').
_VEHICLE_NOUN = (
    r"(?:TRUCKS?|TRAILERS?|VEHICLES?|VEH|CARS?|AUTOS?|TRACTORS?|BOATS?|RVS?|CAMPERS?|MOTORCYCLES?"
    r"|EXCAVATORS?|LOADERS?|SKID ?STEERS?|FORKLIFTS?|BACKHOES?|BULLDOZERS?|DOZERS?|CRANES?|SEMIS?)"
)
_ASSET_NOUN = r"(?:" + _VEHICLE_NOUN + r"|EQUIPMENT|EQUIP|MACHINERY)"
_VEHICLE_NOUN_WORD = re.compile(r"(?<![A-Z])" + _VEHICLE_NOUN + r"\b")
#: Q11 (b): a holder whose name reads as a vehicle or equipment trade (a dealer's or a dealership's words, a salvage,
#: wrecking or auction business, a marina or a boatyard, a collision or body shop, a lessor, an asset noun's sales,
#: rentals, leasing, supply or recycling): its sales of vehicles or equipment are its trade, dealer evidence beyond the
#: owner's words (§17.1). Never a bare SALES, SUPPLY, SUPPLIES, FLEET, RENTAL(S), RECYCLING or TOWING, which plain
#: non-dealers print ('SALES & MARKETING', 'OFFICE SUPPLY', 'FLEET SERVICES', 'PARTY RENTALS'); MOTOR, TRUCKING and
#: TRUCKS stay out; a towing or wrecker service is a platform's vendor (_PLATFORM_VENDOR_HOLDER). A bare LEASING stays:
#: a lessor's sale of a returned vehicle or machine is its trade.
_ASSET_TRADE_HOLDER = re.compile(
    r"(?<![A-Z])(?:AUTOS?|AUTOMOTIVE|AUTOMOBILES?|CARS|MOTORS|MOTORCARS|TRAILERS|EQUIPMENT|EQUIP|MACHINERY|TRACTORS?"
    r"|IMPLEMENTS?|MARINE|MARINAS?|BOATS|BOATYARDS?|YACHTS?|RVS?|POWERSPORTS|MOTORSPORTS|CYCLES|DEALERS?|DEALERSHIP"
    r"|SALVAGE|WRECKING|AUCTION\w*|COLLISION|BODY SHOP|LEASING"
    # R2-OW06 review round 1: FLEET left the asset nouns of a sale, never this arm ('<NAME> FLEET SALES' still trades).
    r"|(?:" + _ASSET_NOUN + r"|FLEET) (?:SALES|RENTALS?|LEASING|SUPPLY|SUPPLIES|RECYCL\w*))\b"
)
#: Q11 (b): a supplier's holder name, whose sale of generic equipment or machinery is its trade.
_SUPPLIER_HOLDER = re.compile(r"(?<![A-Z])(?:SUPPLY|SUPPLIES|SUPPLIERS?)\b")
#: Q11 (b): up to two words between SALE OF or SOLD and the asset, never a connector or a goods or service word ('SALE
#: OF PARTS FOR TRUCK', 'SOLD TIRES FOR TRUCK' are a parts or tire seller's own sales).
_ASSET_SALE_FILLER = (
    r"(?:(?!(?:TO|FOR|ON|AT|BY|FROM|OF|AND|OR|WITH|PER|IN|PARTS?|TIRES?|SERVICES?|REPAIRS?|LABOR|ACCESSOR\w*"
    r"|SUPPL\w*|GOODS|LOADS?|CARGO|FUEL|WARRANT\w*|INSURANCE)\b)\S+ ){0,2}"
)
#: Q11 (b): the sale of a truck, trailer, vehicle or equipment, read as a purpose: '<asset> SALE' (never SALES, a
#: dealer's word), 'SALE OF <asset>' and 'SOLD <asset>' (up to two filler words between), '<asset> SOLD'; never inside
#: a name a company form ends within three more words that hold no connector ('<NAME> TRUCK SALE AND SERVICE INC').
_ASSET_SALE_PURPOSE = re.compile(
    r"(?<![A-Z])(?:" + _ASSET_NOUN + r" SALE|SALE OF " + _ASSET_SALE_FILLER + _ASSET_NOUN + r"|SOLD "
    + _ASSET_SALE_FILLER + _ASSET_NOUN + r"|" + _ASSET_NOUN + r" SOLD)\b"
    r"(?!(?: (?!(?:TO|FROM|FOR|BY|PER|ON|AT)\b)[A-Z&]+){0,3} (?:LLC|L L C|INC|CORP|CORPORATION|CO|COMPANY|LTD)\b)"
)
#: Q11 (b), R2-OW06 review round 1: a commission or a fee printed next to the sale, right after it ('CAR SALE
#: COMMISSION', 'TRUCK SALE FEE') or right before it with at most a connector ('COMMISSION ON TRUCK SALE'): a broker's or
#: an agent's earned revenue, never the proceeds of its own asset. A fee printed apart ('TRUCK SALE NET OF FEES') leaves
#: the sale.
_ASSET_SALE_COMMISSION_AFTER = re.compile(r"^\s*(?:COMMISSIONS?|COMMS?|FEES?)\b")
_ASSET_SALE_COMMISSION_BEFORE = re.compile(r"(?<![A-Z])(?:COMMISSIONS?|FEES?)(?:\s+(?:ON|FOR|FROM|OF))?\s*$")
#: Audit round 3, R3-B15 (R3-59; Q11 (b), "Don't count as true revenue and go straight to non-revenue"; standard G6 and
#: §4.2: deposits arrive net of fees): a netting word beside that commission or fee, after it ('TRUCK SALE FEES
#: WITHHELD', 'TRUCK SALE COMM DEDUCTED') or before it ('LESS FEES TRUCK SALE', 'NET OF COMMISSION TRUCK SALE'): what
#: the seller's proceeds are net of, never a broker's earned fee, so the sale is read (_asset_sale_commission).
#: R3-B15 review round 1 (finding 1; R2-OW06 review round 1's broker carve-out, standard A11): a bare NET reads only
#: before FEES ('NET FEES TRUCK SALE'); a broker's or an agent's NET COMMISSION is its own earned commission after
#: splits, and NET FEE its own fee, so both stay a broker's revenue.
_ASSET_SALE_NETTING_AFTER = re.compile(r"^\s*(?:COMMISSIONS?|COMMS?|FEES?)\s+(?:WITHHELD|DEDUCTED|DEDUCT\w*|NETTED)\b")
_ASSET_SALE_NETTING_BEFORE = re.compile(
    r"(?<![A-Z])(?:(?:NET OF|LESS|AFTER|MINUS)\s+(?:COMMISSIONS?|COMMS?|FEES?)|NET\s+FEES)"
    r"(?:\s+(?:ON|FOR|FROM|OF))?\s*$"
)
#: R3-B15 review round 2 (finding 1; R2-OW06 review round 1's broker carve-out, standard A11): a seller's proceeds never
#: lead with or come out of a commission. A commission word printed directly before that netting phrase ('COMMISSION
#: LESS FEES ON TRUCK SALE', 'NET COMMISSION LESS FEES TRUCK SALE': a broker's or an agent's commission less its fees)
#: or fees a netting word takes from or off a commission after the sale ('TRUCK SALE FEES WITHHELD FROM COMMISSION') is
#: the broker's own earned commission, so the veto stays, as for its mirror 'TRUCK SALE COMMISSION LESS FEES'; never a
#: commission a netting word itself stands before ('NET OF COMMISSION LESS FEES TRUCK SALE', _ASSET_SALE_NETTED_WORD:
#: what a seller's proceeds are net of; a bare NET is a broker's NET COMMISSION).
_ASSET_SALE_COMMISSION_NETTED_BEFORE = re.compile(
    r"(?<![A-Z])(?:COMMISSIONS?|COMMS?)\s+(?:(?:NET OF|LESS|AFTER|MINUS)\s+(?:COMMISSIONS?|COMMS?|FEES?)|NET\s+FEES)"
    r"(?:\s+(?:ON|FOR|FROM|OF))?\s*$"
)
_ASSET_SALE_NETTED_WORD = re.compile(r"(?<![A-Z])(?:NET OF|LESS|AFTER|MINUS)\s*$")
_ASSET_SALE_FEES_FROM_COMMISSION = re.compile(
    r"^\s*FEES?\s+(?:WITHHELD|DEDUCTED|DEDUCT\w*|NETTED)\s+(?:FROM|OFF)\s+(?:[A-Z]+\s+)?(?:COMMISSIONS?|COMMS?)\b"
)
#: Q11 (b): an invoice reference, which a vehicle's or heavy equipment's sale reads through (the owner made no invoice
#: carve-out); accounts-payable, vendor or payables wording still spares the row.
_INVOICE_REFERENCE = re.compile(
    r"(?<![A-Z])INV(?:OICE)?S?(?: (?:NO|NUM|NUMBER|N))? ?#? ?\d\S*|(?<![A-Z])INV(?:OICE)?S?\b(?: (?:PMT|PYMT))?"
    r"|(?<![A-Z])(?:OF|FOR) INVOI ?CES?\b"
)
#: Q11 (b): the single-row verifications that rest on an invoice or customer-payment reference; a non-dealer's printed
#: vehicle sale is read on them too (pass 7 overrules them: a verified asset sale).
ASSET_SALE_INVOICE_METHODS = frozenset(
    {"operating_income_descriptor", "payer_remittance_descriptor", "wire_remittance_purpose"}
)
#: Q11 (b): a refund word, which no asset sale prints (a buyer's refund, a platform's refund of a purchase).
_ASSET_SALE_REFUND = re.compile(r"[A-Z]*REFUND\w*|(?<![A-Z])(?:RFND|REFND)\w*")
#: Q11 (b): the dealer-only wholesale auctions of §7.8, whose payout credit is dealer evidence for Q11 (never for Q9's
#: payables, _dealer_activity).
_WHOLESALE_AUCTION_ENTITIES = frozenset(WHOLESALE_AUCTION_PAYOUT_FORMS)
#: Q11 (b): the platform whose INSURANCE is its own name (IAA), which an insurer-name hold never keeps from Q11.
_IAA = "Insurance Auto Auctions (IAA)"
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
#: §8.1, T4 (B7 review round 2, I16): a deposit's town, one or two words before a state's code (_US_STATE_TAIL without
#: US and CAUS, and without CO, a company form there, never Colorado's code) that ends the row or comes before a ZIP, a
#: reference, a country or 'ON <date>' ('<n> ADVANCE NC', '... CAPITAL HEIGHTS MD 1234567 ATM ID ...'). A company form
#: is no town's word ('<NAME> FUNDING LLC NY' keeps its name).
_DEPOSIT_TOWN_TAIL = re.compile(
    r"(?<![A-Z])(?:(?!(?:LLC|INC|INCORPORATED|CORP|CORPORATION|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC)\b)[A-Z]+ ){1,2}(?:"
    + "|".join(sorted(_US_STATE_TAIL - {"US", "CAUS", "CO"}))
    + r")(?=\s*$| \d| US\b| USA\b| ON \d)"
)
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
#: Audit round 3, R3-29 (§8.2, §8.4; Q3 of 2026-10-02: "Other P2P rails (Interac e-Transfer, ...) are unchanged"):
#: Interac's French name, "virement par courriel", singular or plural. Banque Royale's autodeposit prints 'DEPOT AUTO
#: VIREMENTS PAR COURRIEL <sender> <reference>', which the classifier's VIREMENT\b never reads (the plural): pass 7
#: reads it as the e-Transfer rail (_p2p_rail, _p2p_sender_rail, _E_TRANSFER_RAIL), before the cash or branch DEPOT.
#: DEPOT AUTO(MATIQUE) alone is no form (beside VIREMENT it can be the holder's own scheduled transfer).
_INTERAC_COURRIEL = re.compile(r"(?<![A-Z])VIREMENTS? PAR COURRIEL\b")
#: Audit round 3, R3-29: PAR COURRIEL is an Interac form, so the singular 'VIREMENT PAR COURRIEL' is the rail in
#: _p2p_rail and no transfer wording in _transfer_wording.
_INTERAC_FORM = re.compile(r"(?<![A-Z])(?:INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|AUTODEPOSIT|PAR COURRIEL)\b")
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
#: between them allowed), or a national title insurer. TITLEIST and TITLE BOXING CLUB are no title firm. Audit B8
#: (I44): and a settlement or closing agent named without the word TITLE ('<NAME> SETTLEMENT SERVICES', '<NAME>
#: CLOSING SERVICES'); a bare '<NAME> SETTLEMENT' (a carrier's contractor settlement) is none.
#: Audit round 2, R2-B12 (R37; standard A1): never a processor's, a card's, a clearing house's, a carrier's or a
#: freight, fuel, trucking, logistics or transport firm's settlement services (its operating settlement, §8.6), a claims
#: firm's or a debt settler's ('<NAME> CARD SETTLEMENT SERVICES', '<NAME> FREIGHT SETTLEMENT SERVICES LLC').
_TITLE_FIRM = re.compile(
    r"\bTITLE (?:AND )?(?:AGENCY|AGENCIES|AGCY|CO|COMPANY|COMPANIES|CORP|CORPORATION|INC|LLC|LTD|TRUST|INS|INSURANCE"
    r"|GUARANTY|GUARANTEE|GTY|SERVICES|SERVICE|SVCS|ESCROW|CLOSING|CLOSINGS|SETTLEMENT|SETTLEMENTS|PARTNERS|GROUP)\b"
    r"|\b(?:AGENCY|TRUST|INSURANCE|GUARANTY|SERVICES|ESCROW|CLOSING|CLOSINGS|SETTLEMENT|ABSTRACT)(?: AND)? TITLE\b"
    r"|\b(?:CHICAGO|FIRST AMERICAN|FIDELITY NATIONAL|OLD REPUBLIC|STEWART|TICOR|COMMONWEALTH LAND|LAWYERS|WESTCOR"
    r"|WESTCOR LAND|NORTH AMERICAN|ATTORNEYS|WFG NATIONAL|DOMA) TITLE\b(?! BOXING\b| CLUB\b)"
    r"|\b(?!(?:CARD|MERCHANT|PAYMENTS?|BANKCARD|CLEARING|TRANSACTION|ACH|FREIGHT|CARRIER|FUEL|CLAIMS?|TRUCKING"
    r"|LOGISTICS|TRANSPORT\w*|DEBT)\b)[A-Z]+ SETTLEMENT SERVICES?\b|\b[A-Z]+ CLOSING SERVICES?\b"
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
#: §8.5, Q5 (audit B5: I14): on the wire channel, a sender the payer region reads only as a bank's or a layout's labels
#: names nobody (Navy Federal's 'BANK WIRE DEPOSIT', 'INCOMING BANK WIRE'), and neither does a region with no name
#: word (TD's glued '<reference>S<reference>WIRE'): wire_no_sender. Audit B10 (I14): Falcon Bank's 'INTERNATIONAL IWT'
#: is an incoming-wire label whose sender the classifier reads after the bank's own wire field, now that the reader
#: keeps the text Falcon prints after the amount; a row that prints none names nobody. Audit round 2, R2-B10 (R32):
#: the label words are the bare channel words, every wire layout word (_WIRE_LAYOUT_WORDS: FEDWIRE, FED, INBOUND,
#: INBD, CHIPS, SWIFT, WT, IWT, DOMESTIC, INTL, INTERNATIONAL, INCOMING ...) and BANK, DEPOSIT, DEP, IN, RECEIVED and
#: CR, so the label rule reads in one place: 'INCOMING FEDWIRE', 'FEDWIRE CR', 'INBOUND WIRE' name no sender.
_WIRE_LABEL_ONLY_WORDS = _BARE_CHANNEL_WORDS | _WIRE_LAYOUT_WORDS | frozenset({
    "BANK", "DEPOSIT", "DEP", "IN", "RECEIVED", "CR",
})
#: §8.5, Q5 (audit B5: I61): the Fedwire and CHIPS originator field's width. A legal form the field cuts to LL and
#: glues to the address after it ('<name> MANAGEMENT LL<city>') ends within two to four characters of the width (the
#: normalizer drops the name's punctuation); a word that starts with LL earlier in the name is a name word ('LLOYD').
_WIRE_ORIGINATOR_WIDTH = 35
_WIRE_CUT_FORM_SLACK = 4
_CUT_LLC = re.compile(r"LL[A-Z]{2,}")
#: §8.6, Q6, Q8 (audit B5: I37; Payments Canada Standard 007): TD Canada Trust prints the CPA transaction code as the
#: row's last word, with no ACH word: AP (460, accounts payable), MSP (450, miscellaneous payment), BPY (430, bill
#: payment) and APY (439) are an electronic-payment form; PAY (the 200 family, payroll deposit) is pay wording. DIV
#: (250, a dividend) is neither. Read on TD Canada Trust's statements only: a US row's last word is its own.
_CPA_CODE_BANK = re.compile(r"(?<![A-Z])(?:TD )?CANADA TRUST\b", re.IGNORECASE)
_CPA_PAYMENT_CODE = re.compile(r"(?<= )(?:AP|MSP|BPY|APY)$")
_CPA_PAYROLL_CODE = re.compile(r"(?<= )PAY$")
#: §8.1 personal_income (audit round 2, R2-B12: R42; standard A4, A16, E3): RETIRE... is a payer's own name word, never
#: a person's retirement income, inside the payer region in two places: before an operator's word (a retirement
#: residence, community, village or home paying its vendor: _RETIRE_OPERATOR_NAME), and on TD Canada Trust, ending the
#: payer field TD cuts to fifteen characters (_TD_PAYER_WIDTH) before an electronic-payment CPA code ('<NAME> RETIREM
#: MSP', '<NAME> RETIREME AP': the company form is cut away). PENSION, ANNUIT..., an entry or purpose word, a recordkeeper's
#: or advisor's name (RETIREMENT SERVICES, PLAN, SYS, ADVISORS), an uncut TD name, the PAY code and every other bank keep
#: the hold.
_TD_PAYER_WIDTH = 15
_RETIRE_OPERATOR_NAME = re.compile(
    r"(?<![A-Z])RETIRE\w* (?=(?:RESIDENCES?|COMMUNIT\w*|LIVING|HOMES?|VILLAGES?|CENTRES?|CENTERS?|LODGE|MANOR|SUITES)\b)"
)
_RETIRE_CUT_WORD = re.compile(r"RETIRE[A-Z]*")
#: Audit round 2, R2-B11 (R09 part A; §5.2, §8.4, Q4): TD Canada Trust prints an incoming e-Transfer with a per-transfer
#: code of two to four letters or digits after masked asterisks, where a sender would stand ('E-TRANSFER ***<code>',
#: 'E-TFR ***<code> EPAY'), read on the row's original description: never a sender, a payer word or a CPA code.
_TD_TRANSFER_CODE = re.compile(r"^E[- ]?(?:TRANSFER|TFR)\s+\*{2,}(?P<code>[A-Za-z0-9]{2,4})\b")
#: §8.1 (A3-G refinement): a holder's name read from the statement's own incoming receiver fields (INDN, IND NAME,
#: RECEIVER NAME) needs this many credits, words and letters; a run-together match needs this many letters.
_RECEIVER_HOLDER_MIN_CREDITS = 2
_RECEIVER_HOLDER_MIN_WORDS = 2
_RECEIVER_HOLDER_MIN_LETTERS = 8
_RECEIVER_HOLDER_RUN_LETTERS = 12
#: §8.1 (A3-G refinement): the receiver field's label, before its value (final review I2: the one tuple's name labels,
#: description_text.RECEIVER_NAME_LABELS).
_RECEIVER_LABEL = re.compile(rf"^\s*(?:{'|'.join(RECEIVER_NAME_LABELS)})\b\s*")
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
    "DESIGN", "AUTO", "MOTORS", "RESTAURANT", "BAKERY", "CAFE", "GRILL", "DELI", "DENTAL", "MEDICAL", "CLINIC",
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
    #: §8.9 (A3-H review 2): the payer is a factor FACTORING_PAYOUT_PAYERS names (_factoring_payout_payer).
    factor: bool = False
    #: §8.2, §8.6 (audit round 2, R2-B03: R05): the payer region names only a bank (_bank_only_payer): 'sending',
    #: 'own', 'form', or None.
    bank_only: str | None = None
    #: §8.1 (audit round 2, R2-B04: R41): the row moves the holder's own money in on its face (self_originated) and
    #: nothing claimed it, the guard _first_hold reads: never verified, never a repeat.
    self_own: bool = False
    #: §8.9 (owner ruling 2026-10-02, Q8): the lease-to-own or patient financier whose merchant payout the row is
    #: (_customer_financier: the ledger entity CUSTOMER_FINANCING_PAYERS names), or None.
    financier: str | None = None
    #: §8.1, §8.10 (owner ruling 2026-10-02, the underwriter's Q11 (a)): a builder's progress draw
    #: (construction_progress_draw) on a row nothing claimed: counted and flagged, never verified, never a repeat.
    progress_draw: bool = False
    #: §8.1 (owner ruling 2026-10-02, Q11 (b); R2-OW06 review round 1): on IAA's row the insurer-name hold names (its
    #: INSURANCE is the auction's name), the hold of §8.10's order that would name it after that hold, or None: Q11
    #: reads the row only when none would, so every other hold keeps an IAA seller payout held.
    hold_past_insurer_name: str | None = None
    #: §8.1, §8.10 (owner ruling 2026-10-02, the underwriter's Q9; R2-OW09): the reason T4's financing-root hold was
    #: lifted with (finance_named_customer, lessor_rent or lender_paid_for_services: finance_named_release), set only
    #: where no hold names the row then; never verified, never a repeat, its counted reason relabelled last.
    q9: str | None = None
    #: §8.1, §8.6 (audit round 3, R3-B10 review round 2: finding 1): the bare settlement word alone
    #: (merchant_settlement's _HOLDER_NAMED_SETTLEMENT_ENTRY arm) lifted from the row the pass-7 holder hold (an
    #: unverified credit) or the row-alone own-push guard (self_originated): whatever slot or boundary the word sits in,
    #: refused as proof (refused_word), never a repeat (_never_q5_or_q6), and, where an earlier rule verified the row
    #: under the own-push guard, overruled (_settlement_never_verified).
    settlement_released: bool = False


def _classifier():
    from . import transaction_classifier

    return transaction_classifier


#: §5.2, §8.6 (final review I3): a healthcare alias of this many letters or fewer (WPS, UHC, VPAY, AETNA, CIGNA,
#: OPTUM, ZELIS, VA CCN), and ANTHEM, a common word in business names, is read only as the whole payer name: the
#: region is the alias, before it only reference tokens, generic words and health-plan words, and after it nothing, a
#: reference token, a company form, a health-plan word (_HEALTH_PLAN_WORDS, a Blue-plan form) or another healthcare
#: alias, which may then run on ('UHC PLAN OF THE <place>'). 'ANTHEM ROOFING' and 'WPS INDUSTRIES' are other
#: companies. A longer alias keeps the registry's token read.
_SHORT_HEALTHCARE_ALIAS_LETTERS = 5
_WHOLE_NAME_HEALTHCARE_ALIASES = frozenset({"ANTHEM"})
_HEALTH_PLAN_WORDS = frozenset({
    "HEALTH", "HEALTHCARE", "HLTH", "HLTHCARE", "HC", "PLAN", "PLANS", "INS", "INSURANCE", "INSUR", "CLAIM", "CLAIMS",
    "CLMS", "HCCLAIMPMT", "BLUE", "BC", "BCBS", "LIFE", "BENEFIT", "BENEFITS", "COMMUNITY", "MEDICARE", "MEDICAID",
    "DENTAL", "VISION", "RX", "PHARMACY", "PROVIDER", "NETWORK",
})
_BLUE_PLAN_WORD = re.compile(r"BCBS[A-Z]*")


def _short_healthcare_alias(alias: str) -> bool:
    return len(alias.replace(" ", "")) <= _SHORT_HEALTHCARE_ALIAS_LETTERS or alias in _WHOLE_NAME_HEALTHCARE_ALIASES


@cache
def _short_healthcare_aliases() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """(entity, alias words) of every short healthcare alias, the longest first."""
    found = [
        (entity, tuple(alias.split()))
        for entity, aliases in HEALTHCARE_PAYER_ALIASES.items()
        for alias in aliases
        if _short_healthcare_alias(alias)
    ]
    return tuple(sorted(found, key=lambda item: -len(" ".join(item[1]))))


def _health_plan_word(word: str) -> bool:
    return word in _HEALTH_PLAN_WORDS or _BLUE_PLAN_WORD.fullmatch(word) is not None


def healthcare_payer_match(region: str) -> tuple[str, str] | None:
    """§5.2 (final review I3): the (entity, alias) HEALTHCARE_PAYER_ALIASES names on a payer region, a short alias
    only as the whole payer name (_short_healthcare_alias); or None."""
    if not region:
        return None
    found = registry_match(region, HEALTHCARE_PAYER_ALIASES)
    if found is None or not _short_healthcare_alias(found[1]):
        return found
    classifier = _classifier()
    words = region.split()
    start = 0
    while start < len(words) and (
        classifier._is_reference_token(words[start]) or _health_plan_word(words[start])
        or words[start] in classifier.REVENUE_GENERIC_WORDS
    ):
        start += 1
    for entity, alias in _short_healthcare_aliases():
        if tuple(words[start:start + len(alias)]) != alias:
            continue
        rest = words[start + len(alias):]
        while rest and classifier._is_reference_token(rest[0]):
            rest = rest[1:]
        if not rest or _health_plan_word(rest[0]) or classifier._BANK_COMPANY_FORM.fullmatch(rest[0]) is not None:
            return entity, " ".join(alias)
        # Another healthcare alias right after it ('OPTUM VA CCN').
        other = registry_match(" ".join(rest), HEALTHCARE_PAYER_ALIASES)
        if other is not None and tuple(rest[:len(other[1].split())]) == tuple(other[1].split()):
            return entity, " ".join(alias)
    return None


def healthcare_payer(region: str) -> bool:
    """§5.2: a payer region that matches HEALTHCARE_PAYER_ALIASES (final review I3: a short alias only as the whole
    payer name, healthcare_payer_match)."""
    return healthcare_payer_match(region) is not None


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
    rail a platform's payout prints after the payer's name ('<payer> ... VISA DIRECT <city> <state>') is not read.
    Audit round 3, R3-29: Interac's French form (_INTERAC_COURRIEL) first, so the sender is read after COURRIEL (the
    singular's VIREMENT would otherwise read 'PAR COURRIEL' as the sender's words)."""
    return re.compile(
        _INTERAC_COURRIEL.pattern + "|" + _classifier()._CONSUMER_P2P_RAIL.pattern + r"|(?<![A-Z])RTP\b"
    )


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


#: §8.1 (audit B7: I47): the legal forms a holder's name run may print after it, or leave off.
_HOLDER_RUN_FORM = r"(?: (?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC))?"


@cache
def _holder_runs(account_name: str | None, whole_name: bool) -> re.Pattern[str] | None:
    """§8.1 (audit B7: I47): the holder's own name as a row prints it when the bank prints the receiver with no label:
    the account name's whole run (`whole_name`: any name of two or more words, as T4's root test always removed it),
    and, when the account name names the holder (_usable_holder_name: a company form or a person's name, never a
    product name such as 'BUSINESS REWARDS CHECKING'), each run of its first two words or more, with the legal form
    printed or left off ('NORTHWIND DISTRIBUTION' for 'NORTHWIND DISTRIBUTION LLC'). Longest first; None when there is
    none. Audit round 2, R2-B04 (R19): the runs of each side of a name that joins two (_HOLDER_NAME_MARKER: DBA, AKA,
    'Operating as') that names a holder too, and a run whose last word has _HOLDER_RUN_CUT_FROM letters or more cut by
    the bank's field to _HOLDER_RUN_CUT_KEEPS letters or more at the row's end ('NORTHWIND DISTRIBUTIO'). Audit round 3,
    R3-B10 (R3-37): the row-end cuts are tried before the whole-word runs at each word, so a name of three words or more
    cut in its third word or later ('FABRIKAM COASTAL DISTRIBUT') is removed whole, never its first two words alone; and
    a leading THE is no word of a run: a side that leads with it builds its runs from its words after THE (two words or
    more), each read bare and with THE before it, so no 'THE <one word>' run or cut removes a third party's words (the
    whole-name run stays as printed)."""
    holder = _classifier().account_name_text(account_name)
    words = holder.split()
    runs = set()
    if whole_name and len(words) >= 2:
        runs.add(holder)
    sides = _HOLDER_NAME_MARKER.split(holder)
    for side in (holder, *sides) if len(sides) > 1 else (holder,):
        side = side.strip()
        if _usable_holder_text(side):
            side_words = side.split()
            lead = ""
            if side_words[:1] == ["THE"]:
                side_words, lead = side_words[1:], "THE "
            for count in range(2, len(side_words) + 1):
                run = " ".join(side_words[:count])
                runs.update((run, lead + run) if lead else (run,))
    if not runs:
        return None
    names = "|".join(re.escape(run) for run in sorted(runs, key=len, reverse=True))
    pattern = r"(?<![A-Z0-9])(?:" + names + r")" + _HOLDER_RUN_FORM + r"(?![A-Z0-9])"
    cuts = sorted({
        cut for run in runs
        if not (run.startswith("THE ") and len(run.split()) < 3) and (cut := _holder_run_cut(run)) is not None
    }, key=len, reverse=True)
    if cuts:
        pattern = r"(?<![A-Z0-9])(?:" + "|".join(cuts) + r")\s*$|" + pattern
    return re.compile(pattern)


#: §8.1 (audit round 2, R2-B04: R19): a holder run's last word of this many letters or more may print cut by the bank's
#: field, keeping this many letters or more, at the row's end.
_HOLDER_RUN_CUT_FROM = 5
_HOLDER_RUN_CUT_KEEPS = 4


def _holder_run_cut(run: str) -> str | None:
    """§8.1 (audit round 2, R2-B04: R19): the pattern of a holder run whose last word the bank cut: its other words whole
    and its last word's first _HOLDER_RUN_CUT_KEEPS letters or more ('NORTHWIND DIST', 'NORTHWIND DISTRIBUTIO' for
    'NORTHWIND DISTRIBUTION'); None when its last word is shorter than _HOLDER_RUN_CUT_FROM letters or holds a
    non-letter."""
    words = run.split()
    last = words[-1]
    if len(words) < 2 or len(last) < _HOLDER_RUN_CUT_FROM or not last.isalpha():
        return None
    tail = ""
    for letter in reversed(last[_HOLDER_RUN_CUT_KEEPS:]):
        tail = f"(?:{re.escape(letter)}{tail})?"
    return re.escape(" ".join(words[:-1])) + " " + re.escape(last[:_HOLDER_RUN_CUT_KEEPS]) + tail


def _without_holder_name(
    row: str, account_name: str | None, *, whole_name: bool = False, also: Sequence[str] = (),
) -> str:
    """§8.1 (audit B7: I47): `row` with the holder's own name runs removed (_holder_runs), so a hold word inside the
    holder's name (DISTRIBUTION, CAPITAL, PAYROLL, RETIREMENT, RETURNS) never holds a third party's payment printed with
    an unlabelled receiver. Read before the possible-return, financing-root, pay, personal-income and non-sale tests.
    Audit round 2, R2-B04 (R40): and then each of `also`'s names (the holder's other business names,
    _holder_strip_names), whole and by its runs."""
    runs = _holder_runs(account_name, whole_name) if account_name else None
    row = runs.sub(" ", row) if runs is not None else row
    for name in also:
        extra = _holder_runs(name, True)
        if extra is not None:
            row = extra.sub(" ", row)
    return row


def _holder_strip_names(record: TransactionClassification) -> tuple[str, ...]:
    """§8.1 (audit round 2, R2-B04: R40; I47): the holder's business names the I47 strip removes beside the holder's own
    name (_holder): of the holder's name, and of the account-name field when the holder hold reads it as a second name
    (_holder_names), the trade side of a DBA name always and its legal side when it prints a company form; and an
    account-name field with no DBA that reads as no person's name (_p2p_person_name). Names of two words or more only.
    Never a person's name: stripping the owner's name would count the owner's pay from another company (Q8)."""
    return _holder_strip_names_of(record.account_name, record.holder_name)


def _holder_strip_names_of(account_name: str | None, holder_name: str | None) -> tuple[str, ...]:
    """_holder_strip_names on a statement's account-name field and holder name (audit round 3, R3-B14 review round 1:
    finding 1, so the classifier's Cherry veto reads the names before a record exists)."""
    classifier = _classifier()
    names = _holder_names_of(account_name, holder_name)
    stripped: list[str] = []
    for index, name in enumerate(names):
        printed = classifier.account_name_text(name)
        sides = classifier._HOLDER_TRADE_NAME.split(printed, maxsplit=1)
        if len(sides) == 2:
            legal, trade = (side.strip() for side in sides)
            stripped.append(trade)
            if classifier.company_form(legal):
                stripped.append(legal)
        elif index > 0 and not _p2p_person_name(printed):
            stripped.append(printed)
    return tuple(dict.fromkeys(name for name in stripped if len(name.split()) >= 2))


def government_benefit(text: str) -> bool:
    """§8.1 personal_income, §20 (GOV, class B; GOV review I2): a government's personal-benefit form names the row: a
    benefit descriptor as the whole payer of the row before its receiver fields (_GOVERNMENT_BENEFIT_PAYER, read on
    classifier.government_form_payer), or a benefit entry (_GOVERNMENT_BENEFIT_ENTRY) that no company form follows
    before the row's next field, the IRS's TAX EIP on an IRS Treasury row only."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    if _GOVERNMENT_BENEFIT_PAYER.fullmatch(classifier.government_form_payer(row)) is not None:
        return True
    for found in _GOVERNMENT_BENEFIT_ENTRY.finditer(row):
        if found.group("eip") and classifier.IRS_TREASURY_FORM.search(row) is None:
            continue
        rest = row[found.end():]
        label = _ENTRY_FIELD_LABEL.search(rest)
        if _ENTRY_COMPANY_FORM.search(rest[: label.start()] if label is not None else rest) is None:
            return True
    return False


def _personal_income(text: str, row: str, bank: str | None = None) -> bool:
    """§8.1 personal_income: a benefit or pension word on `row` (_PERSONAL_INCOME), or (GOV) a government's
    personal-benefit form on the credit's text (government_benefit). Audit round 2, R2-B12 (R42): RETIRE... inside the
    payer's own name is read as no benefit word (_spare_retire_name; `bank` is the statement's, which TD Canada Trust's
    cut reads: with none, as Q7's refusal reads it, the cut never spares a word)."""
    row = _spare_retire_name(text, row, bank)
    return _PERSONAL_INCOME.search(row) is not None or government_benefit(text)


def _spare_retire_name(text: str, row: str, bank: str | None = None) -> str:
    """Audit round 2, R2-B12 (R42): `row` without the RETIRE... words the payer region (classifier.payer_region)
    prints as its own name: before an operator's word (_RETIRE_OPERATOR_NAME), or, on TD Canada Trust's row that ends
    with an electronic-payment CPA code (cpa_payment_code, read on the row before its receiver fields and before the
    holder's name is stripped), as the last word of the payer field TD cut to exactly _TD_PAYER_WIDTH characters
    (_RETIRE_CUT_WORD). Every other word, and a region the row no longer prints as read, is left as printed (the
    hold stays)."""
    classifier = _classifier()
    region = classifier.payer_region(text)
    if not region:
        return row
    named = _RETIRE_OPERATOR_NAME.sub("", region)
    printed = classifier._before_receiver(text).strip()
    if cpa_payment_code(printed, bank):
        payer = printed.rsplit(" ", 1)[0]
        last = payer.rsplit(" ", 1)[-1]
        if len(payer) == _TD_PAYER_WIDTH and _RETIRE_CUT_WORD.fullmatch(last):
            words = named.split()
            if len(words) >= 2 and _CPA_PAYMENT_CODE.search(" " + words[-1]) and words[-2] == last:
                del words[-2]
            elif words and words[-1] == last:
                del words[-1]
            named = " ".join(words)
    return row.replace(region, named) if named != region else row


def government_grant(text: str) -> bool:
    """§8.1 non_sale_purpose, §20 (GOV, class D; GOV review M4): a government grant or subsidy names the row: a grant
    form on the row before its receiver fields (_GOVERNMENT_GRANT), or the CRA's wage subsidy as the whole payer
    (_WAGE_SUBSIDY_PAYER)."""
    classifier = _classifier()
    row = _hold_text(text)
    return _GOVERNMENT_GRANT.search(row) is not None or _WAGE_SUBSIDY_PAYER.fullmatch(
        classifier.government_form_payer(classifier._before_receiver(text))
    ) is not None


def financing_named(
    text: str, region: str, entry: str, account_name: str | None, *, bank: str | None = None,
    also: Sequence[str] = (),
) -> bool:
    """§8.1, T4: a financing root in the payer region or the entry fields (posting labels removed, and the holder's
    own name runs removed first: its whole account name, and audit B7 (I47) a run of its first two words or more,
    _without_holder_name), or, on a row with no payer region, in the row before its receiver fields. A whole-word
    CREDIT counts only inside a payer name, next to another name word.

    Audit B7 (I16): the roots are never read on text that names no payer. A cash, branch, ATM or check deposit with no
    payer region prints its location ('<n> GLENDALE <state>', '<n> CAPITAL BLVD', '<NAME> FIN CU <street>'), so it is
    never read. On every row a bank's branch label after a bank's name ('BOFA FIN CTR'), the banks' page furniture
    (MEMBER FDIC, EQUAL HOUSING LENDER), a fundraising purpose and Wave Payments' payout entry are removed
    (_root_reading). On a person-to-person row the sender's bank (a listed sending bank, the statement's bank, a credit
    union's name) is removed, and a sender that reads as a person's name is not read (_p2p_person_name: a surname that
    holds LEND or FUND). On a wire's purpose text a buyer's advance payment or prepayment for goods is removed
    (_WIRE_TRADE_PURPOSE). A whole-word CREDIT ending the payer region after a single letter is the entry word a cut
    originator name prints ('<NAME> P CREDIT'), and the plural CREDITS is no root (_WHOLE_CREDIT) unless a company form
    follows it in the payer region (B7 review round 1, _FORMED_CREDITS: '<NAME> CREDITS LLC'). B7 review round 1: a
    payer-less deposit row is read once its location is removed (_deposit_location_reading), for whole financing words
    only, so a funder's name printed on it still holds; B7 review round 2: its bank, a place, a branch's name, a town
    printed with its state, a buyer's advance purchase and a hold notice's FUNDS are removed or never kept too.

    Owner ruling 2026-10-02 (the underwriter's Q9; R2-OW09): the reading is _financing_root_places', place by place;
    this is whether any place fired (bool of the places), unchanged."""
    return bool(_financing_root_places(text, region, entry, account_name, bank=bank, also=also))


@dataclass(frozen=True)
class _RootPlaces:
    """Owner ruling 2026-10-02 (the underwriter's Q9; §8.1, T4; R2-OW09): where financing_named's roots fire, place by
    place. `payer` is the payer reading when a root, or one of the special payer arms, fires there (`payer_arm`: the
    whole-word or formed CREDIT arm, a glued ...CRED name or a wire's wrap-split root); `entry` the entry reading when a
    root fires there; `row` the payer-less reading (a check, cash, branch or ATM deposit's reading, or the row's reading
    on a row with no payer region) when a root fires there. None where none fires. True when any place fired."""

    payer: str | None = None
    payer_arm: bool = False
    entry: str | None = None
    row: str | None = None

    def __bool__(self) -> bool:
        return self.payer is not None or self.entry is not None or self.row is not None


def _financing_root_places(
    text: str, region: str, entry: str, account_name: str | None, *, bank: str | None = None,
    also: Sequence[str] = (),
) -> _RootPlaces:
    """§8.1, T4 (financing_named's reading, moved here whole by R2-OW09, no behaviour change): the places a financing
    root fires on, each read as financing_named always read it. Every place is computed: a special payer arm (the
    whole-word or formed CREDIT, a glued ...CRED name, a wire's wrap-split root) no longer ends the reading, so the
    underwriter's Q9 release (finance_named_release) sees an entry root printed beside it. bool() of the result is
    financing_named's answer on every input."""
    classifier = _classifier()
    channel = _channel(text, bank)
    if not region and channel in _DEPOSIT_CHANNELS:
        reading = _deposit_location_reading(text, account_name, bank, also=also)
        return _RootPlaces(row=reading) if _FINANCING_ROOT.search(reading) is not None else _RootPlaces()
    row = classifier._before_receiver(text)
    p2p = channel == "person_to_person" and _p2p_rail(row)
    wire = classifier._is_wire_row(text)
    if region:
        payer = _root_reading(_HOLD_POSTING_LABELS.sub(" ", region), account_name, bank, p2p=p2p, also=also)
        if p2p and _p2p_person_name(payer):
            payer = ""
        payer = _CUT_NAME_ENTRY_CREDIT.sub("", payer.strip())
        name_words = classifier.payer_name(payer).split()
        payer_arm = bool(
            (len(name_words) >= 2 and (_WHOLE_CREDIT.search(" ".join(name_words)) or _FORMED_CREDITS.search(payer)))
            # A3 review, rounds 2 and 3: a glued ...CRED word, on a payer's name field or a company-formed payer region.
            or (
                (_prints_payer_name_field(text) or classifier.company_form(" ".join(name_words)))
                and any(_GLUED_CRED_NAME.fullmatch(word) for word in name_words)
            )
            # A3: a wire's sender split by a line wrap, read across the split (§7.9's wrap-tolerant reading); A3
            # review, rounds 2 and 3: on every wire sender, labelled or not, where the two words spell a financing word.
            or (wire and _wrap_split_root(text, payer))
        )
        entry_place = None
        if entry:
            purpose = _HOLD_POSTING_LABELS.sub(" ", entry)
            if wire:
                purpose = _WIRE_TRADE_PURPOSE.sub(" ", purpose)
            reading = _root_reading(purpose, account_name, bank, p2p=False, also=also)
            if _FINANCING_ROOT.search(reading):
                entry_place = reading
        return _RootPlaces(
            payer=payer if payer_arm or _FINANCING_ROOT.search(payer) else None,
            payer_arm=payer_arm,
            entry=entry_place,
        )
    reading = _root_reading(_hold_text(text), account_name, bank, p2p=p2p, also=also)
    if p2p:
        # A sender printed without FROM (its rail's reading, _p2p_sender_region): a person's name words are removed one
        # by one (the reading skips single letters and generic words between them).
        sender = _p2p_sender_region(text)
        if sender and _p2p_person_name(sender):
            for word in sender.split():
                reading = re.sub(r"(?<![A-Z0-9])" + re.escape(word) + r"(?![A-Z0-9])", " ", reading)
    return _RootPlaces(row=reading) if _FINANCING_ROOT.search(reading) else _RootPlaces()


def _root_reading(
    words: str, account_name: str | None, bank: str | None, *, p2p: bool, also: Sequence[str] = (),
) -> str:
    """§8.1, T4 (audit B7: I16, I47): the words the financing roots are read on: without the holder's own name runs
    (_without_holder_name, its whole account name always), a bank's branch label after a bank's name, the banks' page
    furniture, a fundraising purpose and Wave Payments' payout entry; on a person-to-person row (`p2p`) without the
    sender's bank too: a listed sending bank (_P2P_LAYOUT_PHRASES), the statement's own bank and a credit union's
    name (_P2P_CREDIT_UNION)."""
    words = _without_holder_name(words, account_name, whole_name=True, also=also)
    words = _branch_label(bank).sub(" ", words)
    words = _ROOT_FURNITURE.sub(" ", words)
    words = _FUNDRAISING.sub(" ", words)
    words = _WAVE_PAYOUT_ENTRY.sub(" ", words)
    if p2p:
        words = _P2P_LAYOUT_PHRASES.sub(" ", words)
        own = _statement_bank_names(bank) if bank else None
        if own is not None:
            words = own.sub(" ", words)
        words = _P2P_CREDIT_UNION.sub(" ", words)
    return words


def _deposit_location_reading(
    text: str, account_name: str | None, bank: str | None, *, also: Sequence[str] = (),
) -> str:
    """§8.1, T4 (B7 review round 1, I16): the words a payer-less check, cash, branch or ATM row's roots are read on: the
    row's root reading (_root_reading) without its location (a branch's label, a credit union's name, a street's name),
    keeping only the words that start with a financing word (CREDIT aside) or are a whole-word root. A town's name
    holding a root ('GLENDALE') is never read. B7 review round 2: nor the ATM's or branch's bank (the statement's own, a
    listed sending bank: the person-to-person removal), a place a suffix names (_DEPOSIT_PLACE), a branch's name
    (_DEPOSIT_BRANCH_NAME), a town printed with its state (_DEPOSIT_TOWN_TAIL), a buyer's advance purchase or payment
    (_DEPOSIT_TRADE_PURPOSE, _WIRE_TRADE_PURPOSE), or a hold notice's FUNDS or FUNDED (kept only before a company
    form: _DEPOSIT_FINANCING_STARTS)."""
    words = _root_reading(_hold_text(text), account_name, bank, p2p=True, also=also)
    words = _DEPOSIT_BRANCH_LABEL.sub(" ", words)
    words = _DEPOSIT_CREDIT_UNION.sub(" ", words)
    words = _STREET_NAME.sub(" ", words)
    # Audit round 2, R2-B13 (R35): B7 review round 2's place, branch name and town are removed only where no name word
    # stands before their financing word (_deposit_location_removal). Audit round 3, R3-B07 (R3-45): read with the
    # statement's bank, so arm S's whole-row match lifts R35's guard on Scotiabank's statements only.
    for location in (_DEPOSIT_PLACE, _DEPOSIT_BRANCH_NAME, _DEPOSIT_TOWN_TAIL):
        words = location.sub(lambda found: _deposit_location_removal(found, bank=bank), words)
    words = _DEPOSIT_TRADE_PURPOSE.sub(" ", words)
    words = _WIRE_TRADE_PURPOSE.sub(" ", words)
    split = words.split()
    return " ".join(
        word for index, word in enumerate(split)
        if word.startswith(_DEPOSIT_FINANCING_STARTS)
        or _WHOLE_WORD_ROOT.fullmatch(word) is not None
        or (word in _DEPOSIT_NOTICE_FUNDS and _ENTRY_COMPANY_FORM.match(" ".join(split[index + 1:])) is not None)
    )


def _deposit_location_removal(found: re.Match[str], *, bank: str | None = None) -> str:
    """§8.1, T4 (audit round 2, R2-B13: R35; B7 review round 3, minor 1): a place, a branch's name or a town (B7 review
    round 2's _DEPOSIT_PLACE, _DEPOSIT_BRANCH_NAME, _DEPOSIT_TOWN_TAIL) is removed from a deposit's reading as before
    when it holds no financing word the reading keeps (_deposit_kept_word). One that holds one is removed only when that
    word is the match's first word and its only kept word, and the token just before the match is the row's start, a
    token with a digit or a mask ('1 ADVANCE NC'), one of the deposit's own words (_DEPOSIT_LEAD_WORDS: 'DEPOSIT
    CAPITAL CITY BRANCH', 'ATM CASH DEPOSIT CAPITAL HEIGHTS MD'; R2-B13 review round 1: and Wells Fargo's
    'BRANCH/STORE', _DEPOSIT_LEAD_PAIRS), a word inside the classifier's check or cash, branch or ATM form
    (_inside_a_deposit_form: 'NIGHT DROP CAPITAL PLAZA'), or the street suffix that ends a numbered address ('<n> MAIN
    ST CAPITAL HEIGHTS MD', B7 review round 2's own pin). Otherwise the match stays, so a funder's name before a
    location keeps its financing word ('MOBILE DEPOSIT <NAME> FUNDING <town> <ST>', '<NAME> CAPITAL PLAZA', '<NAME>
    CAPITAL CITY BRANCH') and holds. Audit round 3, R3-B07 (R3-45): the deposit form is read with the statement's
    `bank` (_inside_a_deposit_form: arm S's whole-row match counts on Scotiabank's statements only)."""
    location = found.group(0).split()
    kept = [word for word in location if _deposit_kept_word(word)]
    if not kept:
        return " "
    if len(kept) > 1 or not _deposit_kept_word(location[0]):
        return found.group(0)
    before = found.string[: found.start()].split()
    if (
        not before or _numbered_token(before[-1]) or before[-1] in _DEPOSIT_LEAD_WORDS
        # R2-B13 review round 1: Wells Fargo's 'DEPOSIT MADE IN A BRANCH/STORE <place>' (_DEPOSIT_LEAD_PAIRS).
        or tuple(before[-2:]) in _DEPOSIT_LEAD_PAIRS
        # The street suffix that ends a numbered address ('<n> MAIN ST CAPITAL HEIGHTS MD', its name removed by
        # _STREET_NAME): the town follows the ATM's or branch's address.
        or (before[-1] in _STREET_SUFFIX_WORDS and any(_numbered_token(token) for token in before[-3:-1]))
        or _inside_a_deposit_form(found.string, found.start(), bank)
    ):
        return " "
    return found.group(0)


def _numbered_token(token: str) -> bool:
    """§8.1, T4 (audit round 2, R2-B13: R35): a token that holds a digit or a mask ('#')."""
    return "#" in token or any(character.isdigit() for character in token)


def _deposit_kept_word(word: str) -> bool:
    """§8.1, T4 (B7 review round 2, I16; audit round 2, R2-B13: R35): a word a deposit's reading keeps as a financing
    word: it starts with one (_DEPOSIT_FINANCING_STARTS) or is a whole-word root (_WHOLE_WORD_ROOT)."""
    return word.startswith(_DEPOSIT_FINANCING_STARTS) or _WHOLE_WORD_ROOT.fullmatch(word) is not None


def _inside_a_deposit_form(words: str, start: int, bank: str | None = None) -> bool:
    """§8.1, T4 (audit round 2, R2-B13: R35): the token just before a deposit's location (which starts at `start` in
    `words`) is a word inside a match of the classifier's check-deposit form (_CHECK_DEPOSIT_FORM) or its cash, branch or
    ATM form (_CASH_BRANCH_ATM_FORM), read from each word's start so an overlapping match is found: the location
    follows, or sits inside, the deposit's own words (Wells Fargo's 'ATM CHECK DEPOSIT ON <date> <address> <town> <ST>
    <n> ATM ID ...', inside the form's DEPOSIT ... ATM arm; 'NIGHT DROP <place>').

    Audit round 3, R3-B07 (R3-45): on a statement whose bank field (`bank`) is not Scotiabank's (_SCOTIABANK), arm S's
    whole-row match (the classifier's _BRANCH_DEPOSIT_TRANSIT, the form's last alternative) never counts: the form is
    read without it (_cash_form_without_arm_s), so R35's guard holds a financing word after a name word there
    ('DEPOSIT <NAME> CAPITAL PLAZA <transit> <sequence>'), as before arm S. On Scotiabank's statements the words are
    the branch's printed name and arm S counts as before. Arm S's channel reading is unchanged (spec §17.1 (3))."""
    classifier = _classifier()
    before = words[:start].rstrip()
    cash = (
        classifier._CASH_BRANCH_ATM_FORM if _SCOTIABANK.search((bank or "").upper()) is not None
        else _cash_form_without_arm_s()
    )
    return any(
        (found := form.match(words, word.start())) is not None and found.end() >= len(before)
        for form in (classifier._CHECK_DEPOSIT_FORM, cash)
        for word in re.finditer(r"\S+", before)
    )


#: §8.1, T4 (audit round 3, R3-B07: R3-45): the bank field of a Scotiabank statement (upper-cased), whose arm-S branch
#: deposits print the branch's own name.
_SCOTIABANK = re.compile(r"(?<![A-Z])(?:SCOTIABANK|SCOTIA|BANK OF NOVA SCOTIA|BANQUE SCOTIA)\b")


@cache
def _cash_form_without_arm_s() -> re.Pattern[str]:
    """§8.1, T4 (audit round 3, R3-B07: R3-45): the classifier's cash, branch or ATM form without its last alternative,
    arm S (_BRANCH_DEPOSIT_TRANSIT), for _inside_a_deposit_form off Scotiabank's statements. A match the full form makes
    with an earlier alternative is the same match here (the alternation tries arm S last)."""
    classifier = _classifier()
    pattern = classifier._CASH_BRANCH_ATM_FORM.pattern
    arm_s = "|" + classifier._BRANCH_DEPOSIT_TRANSIT
    if not pattern.endswith(arm_s):
        raise RuntimeError("the cash, branch or ATM form no longer ends with arm S")
    return re.compile(pattern[: -len(arm_s)])


@cache
def _branch_label(bank: str | None) -> re.Pattern[str]:
    """§8.1, T4 (audit B7: I16): a bank's branch label printed after a bank's name, a listed sending bank's or the
    statement's own ('BOFA FIN CTR', 'BANK OF AMERICA FINANCIAL CENTER')."""
    names = set(P2P_SENDING_BANK_NAMES) | {"BKOFAMERICA"}
    if bank:
        names.update(_statement_bank_forms(bank))
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(r"(?<![A-Z])(?:" + alternatives + r") " + _BRANCH_LABEL_WORDS + r"\b")


def _p2p_person_name(name: str) -> bool:
    """§8.1, T4 (audit B7: I16): a person-to-person sender that reads as a person's name: two to five name words once
    its reference tokens are skipped, each of letters only, no company form, no holder-noise, generic, business or
    institution word, and no word that is a whole-word root or starts with a financing word
    (_FINANCING_NAME_STARTS: 'TRUE FINANCE', 'FAST FUNDING' and 'NORTHWIND CAPITALCO' are no person). A root inside a
    surname ('LENDSAMPLE', 'FUNDERSON') is never read on it."""
    classifier = _classifier()
    words = [word for word in name.split() if not classifier._is_reference_token(word)]
    if not 2 <= len(words) <= 5 or classifier.company_form(" ".join(words)):
        return False
    return all(
        word.isalpha() and word not in classifier.HOLDER_NOISE and word not in classifier.REVENUE_GENERIC_WORDS
        and _TRUST_BUSINESS_WORDS.search(word) is None and _WHOLE_WORD_ROOT.fullmatch(word) is None
        and not word.startswith(_FINANCING_NAME_STARTS)
        for word in words
    )


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


def _vendor_payment(text: str, row: str) -> bool:
    """Audit B8 (I28, I44): the row is a payer's payment of a vendor's invoice from its payables: §7.5's
    accounts-payable wording (_accounts_payable_wording) or a vendor, invoice or payables word (_VENDOR_PAYMENT_WORDING)."""
    return _accounts_payable_wording(text) or _VENDOR_PAYMENT_WORDING.search(row) is not None


def _trade_name_word(word: str, keep: re.Pattern[str], also: frozenset[str] = frozenset()) -> bool:
    """Audit round 2, R2-B12 (R37): a name word of a customer's trade name: two letters or more and no digit
    (_TRADE_NAME_WORD), never a company form or a filler (_TRADE_NAME_NOT_A_NAME), one of `also`, or a word of the
    reader's `keep`."""
    return (
        _TRADE_NAME_WORD.fullmatch(word) is not None and word not in _TRADE_NAME_NOT_A_NAME and word not in also
        and keep.fullmatch(word) is None
    )


def _trade_name(
    text: str, row: str, region: str, words: re.Pattern[str], keep: re.Pattern[str], *, purpose_arm: bool = True,
) -> bool:
    """Audit round 2, R2-B12 (R37): every occurrence of `words` on `row` (a hold's text) is a customer's trade name,
    never the payer's or the purpose's: (a) it sits in `region`, the payer region, which prints a company form
    (_TRADE_NAME_FORM) and still holds a name word (_trade_name_word) once `words`, the forms, the fillers and `keep`
    are removed; or (b) it sits on the payment's purpose (_title_purpose_text) with a name word right after it (never a
    form, a filler, a `keep` word, another of `words` or a field's word, _TRADE_NAME_NOT_AFTER; review round 1: nor a
    word that names the purpose, _TRADE_NAME_PURPOSE_WORD). An occurrence anywhere else, or one the row no longer prints
    as read, is no trade name, so the hold that reads it holds. Review round 2: `purpose_arm` False reads (a) alone,
    which purpose_trade_name compares with the full reading."""
    rest = row
    if region and _TRADE_NAME_FORM.search(region) and any(
        _trade_name_word(word, keep) for word in words.sub(" ", region).split()
    ):
        rest = rest.replace(region, " ")
    purpose = _title_purpose_text(text) if purpose_arm else ""
    for found in words.finditer(purpose):
        after = re.match(r" (\S+)", purpose[found.end():])
        if after is None or words.fullmatch(after.group(1)) is not None:
            continue
        if (
            _trade_name_word(after.group(1), keep, _TRADE_NAME_NOT_AFTER)
            and _TRADE_NAME_PURPOSE_WORD.fullmatch(after.group(1)) is None
        ):
            rest = rest.replace(f"{found.group(0)} {after.group(1)}", f" {after.group(1)}", 1)
    return words.search(rest) is None


def _layout_entry(text: str) -> str:
    """§8.6 Q6c, §8.1 (A3-H review; audit round 2, R2-B12: R36): the entry field the layout prints, Bank of America's
    DES and Chase's CO ENTRY DESCR, joined; '' on a row that prints none."""
    classifier = _classifier()
    return " ".join(
        found.group(1)
        for field in (classifier._BOFA_ENTRY_FIELD, classifier._CHASE_ENTRY_FIELD)
        for found in field.finditer(text or "")
    )


def gambling_payout(text: str, row: str, *, purpose_arm: bool = True) -> bool:
    """§8.1 non_sale_purpose (audit B8: I28): a sportsbook's, a casino's, a lottery's or a prediction market's payout
    on `row` (the hold text without the holder's name), read in this order (audit round 2, R2-B12: R36, R37): never the
    payer's payment of a vendor (_vendor_payment), nor a lottery's settlement with its retailer (LOTTERY on the row and a
    retailer word, _LOTTERY_RETAILER_WORDING, on the entry the layout prints, _layout_entry, or on the row where it
    prints none: never on the agency's name; review round 1: on a row with no entry, nor its LOTTERY COMMISSION,
    _LOTTERY_AGENCY_NAME); then a listed payer (_GAMBLING_PAYOUT); a lottery's prize (LOTTERY and a prize word anywhere
    on the row); a sportsbook's, a casino's or an online gaming payer (_BETTING_PAYER on the row before its entry
    label) whose entry, or row, prints a withdrawal or payout (_BETTING_WITHDRAWAL); and a JACKPOT or WINNINGS beside a
    gambling word (_GAMBLING_CONTEXT) or outside a customer's trade name (_trade_name, its purpose arm read when
    `purpose_arm`: review round 2, purpose_trade_name)."""
    if _vendor_payment(text, row):
        return False
    entry = _layout_entry(text)
    scope = entry if entry.strip() else row
    lottery = _LOTTERY_WORD.search(row) is not None
    retailer_scope = entry if entry.strip() else _LOTTERY_AGENCY_NAME.sub("LOTTERY", row, count=1)
    if lottery and _LOTTERY_RETAILER_WORDING.search(retailer_scope):
        return False
    if _GAMBLING_PAYOUT.search(row) is not None:
        return True
    if lottery and _LOTTERY_PRIZE_WORD.search(row) is not None:
        return True
    if _BETTING_PAYER.search(_ENTRY_LABEL.split(row, maxsplit=1)[0]) and _BETTING_WITHDRAWAL.search(scope):
        return True
    if _GAMBLING_NAME_WORDS.search(row) is None:
        return False
    return _GAMBLING_CONTEXT.search(row) is not None or not _trade_name(
        text, row, _classifier().payer_region(text), _GAMBLING_NAME_WORDS, _GAMBLING_CONTEXT, purpose_arm=purpose_arm
    )


def legal_settlement(text: str, row: str, region: str, *, purpose_arm: bool = True) -> bool:
    """§8.1 non_sale_purpose (audit B8: I44): a claims administrator's settlement (_LEGAL_SETTLEMENT) on `row`, a
    lawsuit's, a class action's, a data breach's or Epiq's or Verita's (_LEGAL_NAME_WORDS: audit round 2, R2-B12, R37)
    beside a settlement, claim or award word (_LEGAL_CONTEXT) or outside a customer's trade name (_trade_name, keeping
    _LEGAL_NAME_KEEP's words), or a lawyer's or client trust account's payer (_TRUST_LAWYER_WORDS on `region`, the payer
    region) paying settlement proceeds or funds (_LAWYER_SETTLEMENT_PROCEEDS); never a payer's payment of a vendor
    (_vendor_payment). Review round 2: the settlement words are the classifier's settlement spellings
    (_LEGAL_SETTLEMENT_SPELLINGS), and `purpose_arm` is _trade_name's (purpose_trade_name)."""
    named = _LEGAL_SETTLEMENT.search(row) is not None or (
        _LEGAL_NAME_WORDS.search(row) is not None and (
            _LEGAL_CONTEXT.search(row) is not None
            or not _trade_name(text, row, region, _LEGAL_NAME_WORDS, _LEGAL_NAME_KEEP, purpose_arm=purpose_arm)
        )
    )
    if not named and not (
        region and _TRUST_LAWYER_WORDS.search(region) and _LAWYER_SETTLEMENT_PROCEEDS.search(row)
    ):
        return False
    return not _vendor_payment(text, row)


def owner_disbursement(text: str, row: str, region: str) -> bool:
    """§8.1 non_sale_purpose (audit B8, routed by the B7 review round 2): an owner-shaped payer (_OWNER_SHAPED_PAYER on
    the payer region) printing DISB, a disbursement's abbreviation (_DISB_ABBREVIATION), is owner money; audit round 2,
    R2-B12 (R37): never its accounts-payable or vendor disbursement (_VENDOR_DISB, or _vendor_payment)."""
    return (
        bool(region) and _OWNER_SHAPED_PAYER.search(region) is not None and _DISB_ABBREVIATION.search(row) is not None
        and not (_vendor_payment(text, row) or _VENDOR_DISB.search(row))
    )


def owner_money_platform(text: str, row: str, region: str, *, purpose_arm: bool = True) -> bool:
    """§7.5's standing rule, §8.1 non_sale_purpose (S4.2 review I6b; audit B8: I28): a brokerage, investing or
    crypto-exchange platform the registry names (_OWNER_MONEY_PLATFORMS) on `row` returns the owner's own money. Audit
    round 2, R2-B12 (R37): never a payer's payment of a vendor, and when the only platform the row names is KRAKEN,
    UPHOLD or PAXOS (_PLATFORM_NAME_WORDS), only outside a customer's trade name (_trade_name, keeping
    _PLATFORM_NAME_KEEP's words). Review round 1: a platform the row names by a name that is only the platform's is
    spared by §7.5's accounts-payable wording alone (_accounts_payable_wording, S4.2's exception for the investment
    words and its re-review's ruling: accounts-payable wording is the payer's vendor payment), never by a bare vendor,
    invoice or payables word; KRAKEN, UPHOLD or PAXOS alone, whose names are other businesses' too, takes the legal and
    gambling readers' vendor spare (_vendor_payment). The registry's table is unchanged. Review round 2: `purpose_arm`
    is _trade_name's (purpose_trade_name)."""
    if _OWNER_MONEY_PLATFORMS.search(row) is None or _accounts_payable_wording(text):
        return False
    if _OWNER_MONEY_PLATFORMS.search(_PLATFORM_NAME_WORDS.sub(" ", row)) is not None:
        return True
    if _vendor_payment(text, row):
        return False
    return not _trade_name(text, row, region, _PLATFORM_NAME_WORDS, _PLATFORM_NAME_KEEP, purpose_arm=purpose_arm)


def purpose_trade_name(text: str, row: str, region: str) -> bool:
    """Audit round 2, R2-B12 review round 2 (R37; §8.1, §8.6): a legal, gambling or owner-money reader (legal_settlement,
    gambling_payout, owner_money_platform) would hold `row` (the hold text the holds read) but for _trade_name's purpose
    arm, a name word right after the hold word on the purpose ('DES:LITIGATION SUPPORT', 'FOR JACKPOT CANDLES'). The
    purpose words (_TRADE_NAME_PURPOSE_WORD) are a closed list no statement's spelling can complete, so such a row counts
    and never proves (CreditFacts.refused_word): an unlisted purpose noun after a hold word is at worst counted and
    flagged. A row the payer region's trade name (arm (a)) or a vendor spare clears is no such row."""
    if not any(words.search(row) for words in (_GAMBLING_NAME_WORDS, _LEGAL_NAME_WORDS, _PLATFORM_NAME_WORDS)):
        return False
    return (
        (gambling_payout(text, row, purpose_arm=False) and not gambling_payout(text, row))
        or (legal_settlement(text, row, region, purpose_arm=False) and not legal_settlement(text, row, region))
        or (
            owner_money_platform(text, row, region, purpose_arm=False)
            and not owner_money_platform(text, row, region)
        )
    )


def construction_progress_draw(
    text: str, region: str, account_name: str | None = None, *, also: Sequence[str] = (),
    zelle_true_revenue: bool = False,
) -> bool:
    """§8.1, §8.10 (owner ruling 2026-10-02, the underwriter's Q11 (a), "Count as true revenue and flag it"; audit
    I18): a builder's progress draw, counted and flagged, never verified. True only when the payer region names a
    builder (_BUILDER_PAYER), the row prints no Zelle rail (Q3 of 2026-10-02 excludes every Zelle deposit,
    zelle_deposit; the owner's amendment of 2026-10-06 to the underwriter's Q3, R2-OW17: in the counted reading,
    `zelle_true_revenue`, a builder's Zelle draw is read as any other rail's), the row (the hold text without the
    holder's names, as the holds read it: `account_name` and `also`)
    prints DRAW or DRAWS where §8.1 reads the non-sale words (_non_sale_reading) once the payer's own name is removed
    (R2-B13's _payer_name_proper on a row that prints a payer name field, so 'QUICK DRAW CONSTRUCTION LLC DES:PAYMENT'
    prints no draw), nothing reads as the business's own loan or money (_OWN_LOAN_DRAW: a loan's, a line's, an
    escrow's, an owner's, an equity draw, a draw on a line; R2-OW06 review round 1: a commission draw), and the payer is
    no bank, title, escrow, closing or settlement firm, owner-shaped payer or financing root (the earlier financing
    holds read those first). R2-OW06 review round 1: nor a realty firm (_REALTY_PAYER: '<NAME> HOMES REALTY LLC').

    Audit round 3, R3-B15 (R3-08; Q11 (a), "when the payer is a builder"; §2.1's Q11 row, "a DRAW printed only inside
    the payer's own name ... keep(s) today's reading"): the builder word is read on the payer region without the
    holder's names (`account_name` and `also`), so the holder's own builder word is never the payer's (Truist prints the
    receiver inside the region). On a row that prints no payer-name field (_prints_payer_name_field: Wells Fargo's,
    Citizens', TD Bank's, Huntington's and Truist's label-less layouts) the region holds the entry words too: the
    payer's builder word is the first that does not start a draw's purpose phrase (_label_less_builder_word: '<NAME>
    CONST DRAW' names no builder), and DRAW is read only after it or in such a phrase that starts the region
    (_label_less_draw_purpose: any other printed before it, 'QUICK DRAW CONST PAYMENT', is inside the payer's
    name). A row these refuse keeps its reading before the ruling,
    the non-sale hold of its DRAW, as its Bank of America DES twin does; on a row that prints a payer-name field the
    name field is the payer's and today's reading stands. Recorded residual (held, reviewable; 0 corpus rows): a
    builder named '<NAME> CONSTRUCTION', or by the cut spellings a sixteen-character originator field prints, '<NAME>
    CONST' or '<NAME> CONSTR', or '<NAME> BUILD', with no company form before a bare DRAW on a label-less row (the
    phrase cannot be told from the name; R3-B15 review round 1, findings 3 and 4). R3-B15 review round 1 (finding 2):
    a builder's draw on Truist's entry-first layout ('CONST DRAW <NAME> BUILDERS INC ...') counts, the DRAW of the
    entry's purpose phrase read before the builder word (_label_less_draw_purpose); its recorded residual (counted, as
    before R3-08; 0 corpus rows): a receiver the holder's names do not strip that prints a builder word lends it to a
    root-less payer's entry-first CONST DRAW. R3-B15 review round 2 (finding 2): only a phrase that starts the payer
    region is that entry, so a root-less lender's, a county's or a developer's '<NAME> CONST DRAW' followed by a later
    builder word in the region ('SAMPLE COUNTY CONST DRAW BUILDER PMT') names no builder and keeps its hold."""
    if not region or _REALTY_PAYER.search(region) or (not zelle_true_revenue and zelle_deposit(text)):
        return False
    named = _prints_payer_name_field(text)
    payer = _without_holder_name(region, account_name, also=also)
    builder = _BUILDER_PAYER.search(payer) if named else _label_less_builder_word(payer)
    if builder is None:
        return False
    row = _without_holder_name(_hold_text(text), account_name, also=also)
    if named:
        name = _payer_name_proper(text, region)
        purpose = row.replace(name, " ") if name else row
    else:
        purpose = _label_less_draw_purpose(row, payer, builder)
    if _DRAW_WORD.search(_non_sale_reading(text, purpose, region)) is None or _OWN_LOAN_DRAW.search(row):
        return False
    return not (
        _BANK_OR_TITLE_SENDER.search(region) or _TITLE_FIRM.search(region) or _OWNER_SHAPED_PAYER.search(region)
        or _FINANCING_ROOT.search(region)
    )


def _label_less_builder_word(payer: str) -> re.Match[str] | None:
    """Audit round 3, R3-B15 (R3-08): the payer's builder word on a payer region that is no payer-name field (`payer`,
    read without the holder's names): the first _BUILDER_PAYER match that does not start a draw's purpose phrase
    (_DRAW_PURPOSE_PHRASE: CONSTRUCTION, CONSTR or CONST, and since R3-B15 review round 1, finding 4, BUILD, directly
    followed by DRAW or DRAWS, the entry's words); None when there is none ('FABRIKAM AMERICA CONST DRAW', 'SAMPLE
    COUNTY CONSTRUCTION DRAW', 'FABRIKAM AMERICA BUILD DRAW')."""
    for found in _BUILDER_PAYER.finditer(payer):
        if _DRAW_PURPOSE_PHRASE.match(payer, found.start()) is None:
            return found
    return None


def _label_less_draw_purpose(row: str, payer: str, builder: re.Match[str]) -> str:
    """Audit round 3, R3-B15 (R3-08): where a row that prints no payer-name field reads DRAW: the hold row (`row`,
    without the holder's names) from the end of the payer's builder word on (`builder`, a match on `payer`, the payer
    region without the holder's names), so a DRAW printed before the builder word is inside the payer's name. The
    builder word is found in the row through the region's words up to it; where the row does not print them as the
    region does, only the region's words after the builder word are read (a draw the row prints later stays unread,
    the conservative side). R3-B15 review round 1 (finding 2; Q11 (a)): a draw's purpose phrase printed before the
    builder word (_DRAW_PURPOSE_PHRASE, which _label_less_builder_word skipped) is the entry's purpose, never the
    payer's name, so its DRAW is read too: Truist's entry-first 'CONST DRAW <NAME> BUILDERS INC <receiver> CUSTOMER
    ID' is a builder's draw, while 'QUICK DRAW CONST PAYMENT' prints no phrase and stays unread. R3-B15 review round 2
    (finding 2; R3-08's own target payers): only a phrase that starts the payer region, the entry-first entry, is read;
    one printed after the payer's name ('FABRIKAM AMERICA CONST DRAW CONTRACTOR PMT', 'SAMPLE COUNTY CONST DRAW BUILDER
    PMT') is that root-less payer's own entry and lends no DRAW to a later builder word."""
    lead = payer[: builder.end()].strip()
    at = row.find(lead) if lead else -1
    after = row[at + len(lead):] if at >= 0 else payer[builder.end():]
    offset = len(payer) - len(payer.lstrip())
    first = _DRAW_PURPOSE_PHRASE.match(payer, offset)
    if first is not None and first.end() <= builder.start():
        return f"{first.group(0)} {after}"
    return after


def non_sale_purpose(
    text: str, region: str, *, bank: str | None = None, account_name: str | None = None, disbursing: bool = False,
    also: Sequence[str] = (), progress_draw: bool = False, insurer_work: bool = False,
) -> bool:
    """§8.1: a non-sale purpose, a public payer's refund or benefit, or a healthcare payer's member or premium credit.
    The investment words hold a row unless it prints accounts-payable wording (S4.2 fix measurement). A3 (precision
    sample): a title firm named on the payer region (_TITLE_FIRM: property-closing proceeds, an asset sale), on a
    wire or an ACH row alike, unless its purpose cites the holder's fee (_TITLE_FEE_WORDING, the orchestrator's
    ruling; A3 review: read on the purpose only, _title_purpose_text); and the holder's own currency conversion
    (_currency_conversion; `bank` is the statement's bank, whose own name names no payer).

    Audit B7: the row is read without the holder's own name runs (I47, _without_holder_name: `account_name`), and the
    non-sale words only as a purpose (I18, _non_sale_reading): never a street's name, a payer's name word
    (DISTRIB..., STOCK), a joint-stock company's form, the payer's own DISBURSEMENT ACCOUNT, or the recurring
    disbursement entry of an ordinary payer (`disbursing`: the statement pass's _recurring_disbursers). A personal
    trust's payment that cites the holder's service is no owner money (the orchestrator's ruling on audit I57,
    _held_personal_trust).

    Audit B8: a gambling or prediction-market payout (I28, gambling_payout), a legal settlement (I44,
    legal_settlement) and an owner-shaped payer's DISB (owner_disbursement) are no sale either; a settlement or
    closing agent is a title firm (I44, _TITLE_FIRM). Audit round 2, R2-B12 (R37): those readers, and the owner-money
    platforms (owner_money_platform), spare a customer's trade name, a vendor's payment and a processor's or a carrier's
    settlement services, in the same order.

    Owner ruling 2026-10-02 (the underwriter's Q11 (a)): on a builder's progress draw (`progress_draw`, the pass's
    construction_progress_draw), DRAW is no non-sale word, inside the payer's name too; every other non-sale word and
    every later test still holds the row.

    Owner ruling 2026-10-02 (the underwriter's Q2): on an insurer's credit pass 7 released as the business's work
    (`insurer_work`, INSURER_FOR_WORK_METHOD), CLAIM is no non-sale word: the release read the insurer's claim as paid for
    the business's work (a repair shop's, an agency's or a provider's claims); every other non-sale word still holds.
    Audit round 3, R3-B13 (R3-11): nor in the public-payer arm, so a listed carrier the release read before the
    government arm ('ALLSTATE COUNTY DES:CLAIM PMT', a Texas county mutual's cut that _PUBLIC_PAYER_NAME still reads as
    a county) is not held as a public payer's claim; the arm's other words still hold it."""
    classifier = _classifier()
    row = _without_holder_name(_hold_text(text), account_name, also=also)
    claim_entry = classifier._HCCLAIMPMT.search(text) is not None
    healthcare = healthcare_payer(region)
    reading = _non_sale_reading(text, row, region, disbursing=disbursing, bank=bank)
    if progress_draw:
        reading = _DRAW_WORD.sub(" ", reading)
    if _NON_SALE_PURPOSE.search(reading) is not None:
        return True
    # GOV (owner ruling 2026-09-30, class D): a government grant or subsidy.
    if government_grant(text):
        return True
    # Audit B8 (I28, I44; the B7 review round 2's routing): a gambling payout, a legal settlement, an owner's DISB.
    if gambling_payout(text, row) or legal_settlement(text, row, region) or owner_disbursement(text, row, region):
        return True
    if (
        region and _TITLE_FIRM.search(region) is not None
        and _TITLE_FEE_WORDING.search(_title_purpose_text(text)) is None
    ):
        return True
    if _currency_conversion(text, bank=bank):
        return True
    if _held_personal_trust(text, region):
        return True
    if _INVESTMENT_PURPOSE.search(row) is not None and not _accounts_payable_wording(text):
        return True
    if (
        not insurer_work and _CLAIM_WORD.search(row) and not claim_entry
        and not (healthcare and re.search(r"(?<![A-Z])CLAIM PMT\b", row))
    ):
        return True
    public_words = classifier._TREASURY_BOILERPLATE.sub(" ", text)
    if insurer_work:
        # Audit round 3, R3-B13 (R3-11): the released insurer's CLAIM is no public payer's claim either.
        public_words = _CLAIM_WORD.sub(" ", public_words)
    if _public_named(public_region(text)) and classifier._PUBLIC_PAYER_NON_SALE_WORDS.search(public_words):
        return True
    # S4.2 review (I6b): a brokerage, investing or crypto-exchange platform returns the owner's own money (audit round 2,
    # R2-B12: R37, never a vendor's payment or a customer's trade name, owner_money_platform).
    if owner_money_platform(text, row, region) or classifier._matches_any(
        row, classifier._SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS
    ):
        return True
    # A3-H review: on a row whose entry field _premium_coded reads, a premium word holds nothing (the row is counted
    # and flagged as a refused payer); a member, subscriber or reimbursement word still holds it.
    if healthcare and _premium_coded(text, region):
        row = _PREMIUM_CODED.sub(" ", row)
    return healthcare and _HEALTHCARE_MEMBER_WORDS.search(row) is not None


def _non_sale_reading(
    text: str, row: str, region: str, *, disbursing: bool = False, bank: str | None = None,
) -> str:
    """§8.1 non_sale_purpose (audit B7: I18): the words _NON_SALE_PURPOSE reads, the non-sale words only as a purpose:
    without a street's name (audit round 2, R2-B13: R34, after a street number only, _NUMBERED_STREET_NAME: '<n> GRANT
    AVE'; R2-B13 review round 1: on a payer-less check, cash, branch or ATM deposit, whose location is never a purpose,
    B7's _STREET_NAME with no number, as _financing_root reads that row's location; `bank` is the statement's bank,
    for _channel), a joint-stock company's or bank's form (_JOINT_STOCK), DISTRIB... or STOCK inside a name a company
    form ends (_FORMED_NAME_NON_SALE, after a name word: B7 review round 1, _spare_a_formed_name_word) or inside the
    payer's name field (the payer region of a row that prints one, _prints_payer_name_field: 'ORIG CO NAME:<NAME>
    DISTRIBUTIO'; R2-B13: R34, its name proper only, _payer_name_proper), STOCK on a row citing an invoice
    (_INVOICE_WORD), the payer's own DISBURSEMENT ACCOUNT, and (`disbursing`) the disbursement entry of an ordinary
    payer that repeats in the statement (_recurring_disbursers), which no loan, escrow, title or proceeds word stands
    beside (_DISBURSEMENT_KEEP)."""
    if not region and _channel(text, bank) in _DEPOSIT_CHANNELS:
        row = _STREET_NAME.sub(" ", row)
    else:
        row = _NUMBERED_STREET_NAME.sub(r"\g<number> ", row)
    row = _JOINT_STOCK.sub(" ", row)
    row = _FORMED_NAME_NON_SALE.sub(_spare_a_formed_name_word, row)
    if region and _prints_payer_name_field(text):
        name = _payer_name_proper(text, region)
        named = _NAME_NON_SALE_WORDS.sub(" ", name)
        if named != name:
            row = row.replace(name, named)
    if _INVOICE_WORD.search(row):
        row = _STOCK_WORD.sub(" ", row)
    row = _DISBURSEMENT_ACCOUNT.sub(" ", row)
    if disbursing and _DISBURSEMENT_KEEP.search(row) is None:
        row = _DISBURSEMENT_WORD.sub(" ", row)
    return row


def _payer_name_proper(text: str, region: str) -> str:
    """§8.1 non_sale_purpose (audit round 2, R2-B13: R34): the part of a payer's name field (_prints_payer_name_field)
    that is the payer's name, where B7's I18 spare reads DISTRIB... and STOCK as name words: on a wire's sender
    (_is_wire_row) or an ACH originator field (_ACH_ORIGINATOR_FIELD before the receiver fields), the whole region; on a
    transfer's or a person-to-person sender after FROM, the region up to and including its first company form
    (_ENTRY_COMPANY_FORM: 'FROM <NAME> HOLDINGS LLC PROFIT DISTRIBUTION' reads '<NAME> HOLDINGS LLC'), or, with no form,
    the whole region only when the row prints more after it before the receiver fields (a label of _SENDER_END or a
    reference closes the sender: 'FROM <NAME> DISTRIBUTION CONF <n>'). A sender that runs to the row's end with no form
    (Wealthsimple's 'TRANSFER IN FROM <sender> <memo>') may hold the payer's memo, so none of it is spared ('')."""
    classifier = _classifier()
    if classifier._is_wire_row(text):
        return region
    row = classifier._before_receiver(text)
    if classifier._ACH_ORIGINATOR_FIELD.search(row) is not None:
        return region
    form = _ENTRY_COMPANY_FORM.search(region)
    if form is not None:
        return region[: form.end()]
    sender = re.search(r"\bFROM\b", row)
    at = row.find(region, sender.end()) if sender is not None else -1
    return region if at >= 0 and row[at + len(region):].strip() else ""


def _spare_a_formed_name_word(found: re.Match[str]) -> str:
    """§8.1 non_sale_purpose (B7 review round 1, I18): a _FORMED_NAME_NON_SALE match keeps its word before and drops
    DISTRIB... or STOCK only when that word is a name word (not in _NOT_A_NAME_WORD_BEFORE; B7 review round 2: holding
    a letter, at most _NAME_WORD_MAX_DIGITS digits and no period's code, _PERIOD_CODE, so 'A1 DISTRIBUTION LLC' is a
    name and 'Q4 DISTRIBUTION' or 'AB1234 DISTRIBUTION' is not); otherwise the match is left as printed, so a purpose
    before a formed name still holds."""
    before = found.group("before")
    if (
        any(character.isalpha() for character in before)
        and sum(character.isdigit() for character in before) <= _NAME_WORD_MAX_DIGITS
        and _PERIOD_CODE.fullmatch(before) is None and before not in _NOT_A_NAME_WORD_BEFORE
    ):
        return before + " "
    return found.group(0)


def _recurring_disbursers(texts: dict[int, str]) -> frozenset[tuple[str, ...]]:
    """§8.1 non_sale_purpose (audit B7: I18): the payer keys of the statement's ordinary payers (_disbursing_payer) whose
    disbursement entry prints on two or more credits (§5.2's repeats): a processor's or a platform's recurring payout
    ('PSP <phone> DISBURSMNT'). A one-off disbursement keeps its hold."""
    classifier = _classifier()
    counts: Counter = Counter()
    for text in texts.values():
        if _DISBURSEMENT_WORD.search(_hold_text(text)) is None:
            continue
        region = classifier.payer_region(text)
        if region and _disbursing_payer(text, region):
            counts[classifier._payer_key(region)] += 1
    return frozenset(key for key, count in counts.items() if key and count >= 2)


def _disbursing_payer(text: str, region: str) -> bool:
    """§8.1 non_sale_purpose (audit B7: I18): an ACH or EFT payer whose disbursement entry is its ordinary payout (a
    processor's 'PSP <phone> DISBURSMNT', an association's 'DISBURSEMENT'): the row is on the ACH or EFT channel and its
    payer region names a payer that reads as none of a lender (a financing root, a financing payee of the registry), an
    insurer or a claim payer, a bank, a title, escrow, closing or settlement firm, a lawyer's account or a public
    payer. B7 review round 1: nor an owner-shaped payer (_OWNER_SHAPED_PAYER: a holding company, a partnership, a
    venture, a family office, a trust or an estate), whose disbursement is owner money. Audit round 2, R2-B12 (R17): nor
    a retirement account's or plan's (_RETIREMENT_ACCOUNT on the row's hold text), whose disbursement keeps its hold."""
    classifier = _classifier()
    if not region or _channel(text) != "ach_eft":
        return False
    if (
        _FINANCING_ROOT.search(region) or _INSURER_NAME.search(region) or _CLAIM_WORD.search(region)
        or _BANK_OR_TITLE_SENDER.search(region) or _TRUST_LAWYER_WORDS.search(region)
        or _OWNER_SHAPED_PAYER.search(region) or _public_named(public_region(text))
        or _RETIREMENT_ACCOUNT.search(_hold_text(text))
    ):
        return False
    known = match_known_payee(classifier._without_receiver_value(text), credit=True)
    return known is None or known.state not in FINANCING_STATES


def _disbursement_entry(text: str, region: str) -> bool:
    """§8.1, §8.6 (audit round 2, R2-B12: R17): the row's hold text prints a disbursement word (_DISBURSEMENT_WORD)
    outside the payer's own DISBURSEMENT ACCOUNT and beside no loan, escrow, title or proceeds word
    (_DISBURSEMENT_KEEP): the entry B7's I18 spare drops from the non-sale reading. Review round 1: read outside the
    payer's own name field (`region` on a row that prints one, _prints_payer_name_field, as B7 reads DISTRIB... and
    STOCK), so a payer named for disbursement services ('<NAME> DISBURSEMENT SERVICES LLC DES:PAYMENT') prints no
    disbursement entry; a row that prints no name field, or whose hold text no longer prints the region, is read whole
    (fail closed)."""
    row = _hold_text(text)
    if region and _prints_payer_name_field(text):
        row = row.replace(region, " ")
    row = _DISBURSEMENT_ACCOUNT.sub(" ", row)
    return _DISBURSEMENT_WORD.search(row) is not None and _DISBURSEMENT_KEEP.search(row) is None


def _held_personal_trust(text: str, region: str) -> bool:
    """§8.1 (A3-G; the orchestrator's delegated ruling on audit I57): a personal trust that the hold names
    (_personal_trust), unless the payment's purpose (_title_purpose_text, a line wrap's split joined) cites the holder's
    service: a school's tuition or a student's ID (_TRUST_SERVICE_PURPOSE, _TRUST_STUDENT_ID_PURPOSE). A trust's payment
    with no purpose stays held. Audit round 2, R2-B08 (R47 (c)): TUITION never read after IN, STUDENT ID only as whole
    words on the printed purpose (review round 1: a line wrap's split inside it joined)."""
    if not _personal_trust(text, region):
        return False
    purpose = _title_purpose_text(text)
    return (
        _TRUST_SERVICE_PURPOSE.search(purpose.replace(" ", "")) is None
        and _TRUST_STUDENT_ID_PURPOSE.search(purpose) is None
    )


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


def _cpa_code_bank(bank: str | None) -> bool:
    """Audit B5 (I37): the statement is TD Canada Trust's, which prints the CPA transaction code as the row's last
    word (_CPA_CODE_BANK)."""
    return bool(bank) and _CPA_CODE_BANK.search(bank) is not None


def cpa_payment_code(row: str, bank: str | None) -> bool:
    """§8.6 (audit B5: I37): TD Canada Trust's row ends with an electronic-payment CPA code (AP, MSP, BPY, APY)."""
    return _cpa_code_bank(bank) and _CPA_PAYMENT_CODE.search(row) is not None


def cpa_payroll_code(row: str, bank: str | None) -> bool:
    """§8.1, Q8 (audit B5: I37): TD Canada Trust's row ends with the CPA payroll-deposit code (PAY)."""
    return _cpa_code_bank(bank) and _CPA_PAYROLL_CODE.search(row) is not None


def _transfer_code(record: TransactionClassification) -> str | None:
    """Audit round 2, R2-B11 (R09 part A): the per-transfer code a TD Canada Trust e-Transfer credit prints after its
    rail (_TD_TRANSFER_CODE, on the original description), upper-cased as the normalized text prints it; None on any
    other row or bank."""
    if not _cpa_code_bank(record.bank):
        return None
    found = _TD_TRANSFER_CODE.match(record.original_description or "")
    return found.group("code").upper() if found is not None else None


def without_transfer_code(record: TransactionClassification, text: str) -> str:
    """Audit round 2, R2-B11 (R09 part A; §5.2, §8.4, Q4): a credit's revenue text without TD Canada Trust's
    per-transfer code after its e-Transfer rail ('E TRANSFER PAY' reads 'E TRANSFER'), the text pass 7's payer facts,
    holds, CPA-code readers and counter-debit reading read (and the census's facts, guard_facts), so a code that spells
    a word (PAY, CAP, MTG) is never pay wording, a financing root or a payer's name. Every other row's text is
    returned as it is; the reversal and cancel rules, which decided before pass 7, stay first."""
    code = _transfer_code(record)
    if code is None:
        return text
    return re.sub(rf"^(E ?(?:TRANSFER|TFR)) {re.escape(code)}(?= |$)", r"\1", text, count=1)


def _pay_wording(
    row: str, bank: str | None, *, text: str = "", account_name: str | None = None, business: bool = False
) -> bool:
    """§8.1, Q8: pay wording on the row before its receiver fields (_PAY_WORDS), a payroll provider, (audit B5: I37)
    TD Canada Trust's payroll-deposit code, or (audit B6: I49) an earned-wage access provider's push. Audit B7 (I09):
    or the direct-deposit words with a sign of a person's pay (_direct_deposit_pay; `text` is the credit's revenue
    text with its receiver fields, `business` the statement's _business_shape)."""
    if (
        _PAY_WORDS.search(row) or _EARNED_WAGE_ACCESS.search(row) or _classifier()._is_payroll_provider_row(row)
        or cpa_payroll_code(row, bank)
    ):
        return True
    return _direct_deposit_pay(text or row, row, account_name, business=business)


def _direct_deposit_pay(text: str, row: str, account_name: str | None, *, business: bool) -> bool:
    """§8.1, §8.8 (Q8; audit B7: I09): the direct-deposit words (_DIRECT_DEPOSIT_WORDS) on `row` are a person's pay when
    the account does not read as a business's (`business` False, _business_shape), when a payroll provider is named on
    the row, when the receiver is a person (_person_receiver), or on a consumer (PPD or WEB) entry (consumer_entry) to
    a receiver that is not a company (audit round 2, R2-B13: R23, _business_receiver).
    The rest of the pay words (_PAY_WORDS) and the payroll providers of _is_payroll_provider_row are read by
    _pay_wording before these. On a business's account a company's
    direct deposit to the business ('<payer> DIR DEP <date> <id>', a carrier's settlement to its contractor) is no pay
    wording: the credit takes its payer's reading (Q6, or named_payer_unlabelled on a layout with no ACH form)."""
    found = _DIRECT_DEPOSIT_WORDS.search(row)
    if found is None:
        return False
    if not business:
        return True
    classifier = _classifier()
    # A payroll provider named on the row (the classifier's payroll words: ADP, PAYCHEX, GUSTO, CERIDIAN), whose
    # direct deposit is the employer's payroll it runs.
    if classifier._matches_any(row, classifier._PAYROLL_PATTERNS):
        return True
    return _person_receiver(text, row[found.end():], account_name) or (
        consumer_entry(text, account_name) and not _business_receiver(text, account_name)
    )


def _business_receiver(text: str, account_name: str | None) -> bool:
    """§8.1, §8.8 (Q8; audit round 2, R2-B13: R23; I09's ruling, "a PPD entry to a person"): a receiver field's value
    (INDN, IND NAME, RECEIVER NAME, its letters-only words, as _person_receiver reads it) names a business: it prints a
    company form ('INDN:<NAME> ROUTES LLC'), or it is the holder's own company-formed name (_holder_business_name:
    'INDN:<NAME> ROUTES' on the account of '<NAME> ROUTES LLC'). A person, a holder with no company form (a person, a
    DBA name with no form) or a receiver with no form that is not the holder's whole name is no business. R2-B13 review
    round 1: never holder_named's looser reading, which also reads a shorter run of the holder's name, a DBA's person
    side, a middle initial or a reversed order as the holder, so the owner's own pay ('INDN:JOHN SAMPLE' on 'JOHN SAMPLE
    PLUMBING LLC''s account) keeps the entry's pay reading."""
    classifier = _classifier()
    for found in classifier._RECEIVER_FIELD_VALUE.finditer(text):
        value = " ".join(word for word in _RECEIVER_LABEL.sub("", found.group(0), count=1).split() if word.isalpha())
        if value and (classifier.company_form(value) or _holder_business_name(value, account_name)):
            return True
    return False


#: §8.1, §8.8 (audit round 2, R2-B13 review round 1: R23): the legal forms a holder's company-formed name may print
#: after its name words, which a receiver field may leave off or print cut ('<NAME> ROUTES L').
_RECEIVER_HOLDER_FORMS = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "LLLP", "PLLC",
    "PLC", "ULC",
})


def _holder_business_name(value: str, account_name: str | None) -> bool:
    """§8.1, §8.8 (audit round 2, R2-B13 review round 1: R23): a receiver's letters-only words (`value`) are the
    holder's own company-formed name (the holder's name prints a company form and no DBA or AKA): every name word of
    it, in order, its trailing form left off, printed whole or cut ('<NAME> ROUTES', '<NAME> ROUTES L' for '<NAME>
    ROUTES LLC'), or that name with its last word of _HOLDER_RUN_CUT_FROM letters or more cut by the bank's field to
    _HOLDER_RUN_CUT_KEEPS letters or more and nothing after it (R2-B04's end cut: '<NAME> TRANSPORTAT'). A leading THE
    is no name word on either side, and a printed L L C is LLC. A shorter run of the name (the owner's own name leading
    '<person> PLUMBING LLC'), a DBA's side, a middle initial, a reversed order or a word after the name that is no form
    is never the business: a person receiver keeps the entry's reading. Recorded residual, an owner item beside Q8
    (§17.1): a holder whose formed name is a person's name with a form ('<person> LLC') reads as the business when the
    receiver prints that name whole, with its own form cut, or with its last word cut (two name words or more), as
    nothing in the text tells it from '<NAME> ROUTES' on '<NAME> ROUTES LLC'. Audit round 3, R3-B10 (R3-89): a last
    word after the name that is no whole form reads as a cut form only when one of the holder's own forms starts with
    it ('L', 'LL' on '... LLC'; never 'L' on '... CORP'), and a one-word holder's name is never read cut ('NORT' on
    'NORTHWIND LLC'), as _holder_run_cut needs two words."""
    classifier = _classifier()
    printed = classifier.account_name_text(account_name)
    if not printed or not classifier.company_form(printed) or classifier._HOLDER_TRADE_NAME.search(printed):
        return False

    def name_words(name: str) -> list[str]:
        words = [word for word in re.sub(r"(?<![A-Z])L L C(?![A-Z])", "LLC", name).split() if word.isalpha()]
        return words[1:] if words[:1] == ["THE"] else words

    holder = name_words(printed)
    popped: list[str] = []
    while holder and holder[-1] in _RECEIVER_HOLDER_FORMS:
        popped.insert(0, holder.pop())
    words = name_words(value)
    count = len(holder)
    if not holder or len(words) < count or words[: count - 1] != holder[:-1]:
        return False
    last, rest = words[count - 1], words[count:]
    if last != holder[-1]:
        return (
            count >= 2 and not rest and len(holder[-1]) >= _HOLDER_RUN_CUT_FROM and len(last) >= _HOLDER_RUN_CUT_KEEPS
            and holder[-1].startswith(last)
        )
    return all(word in _RECEIVER_HOLDER_FORMS for word in rest[:-1]) and (
        not rest or rest[-1] in _RECEIVER_HOLDER_FORMS or any(form.startswith(rest[-1]) for form in popped)
    )


#: §8.1, §8.8 (B7 review round 1, I09): the trace and reference labels a layout prints after a direct deposit's
#: receiver, never a person's name word.
_TAIL_TRACE_LABELS = frozenset({"TRN", "TRACE", "REF", "ID"})


def _person_receiver(text: str, tail: str, account_name: str | None) -> bool:
    """§8.1, §8.8 (audit B7: I09): the direct deposit's receiver is a person: a receiver field's value (INDN, IND NAME,
    RECEIVER NAME) that reads as a person's name, or, on a layout that prints the receiver after the deposit's
    references with no label (Wells Fargo's '<payer> DIR DEP <date> <id> <receiver>'), the words after those
    references (`tail`), each a letters-only word, reading as one (_p2p_person_name). B7 review round 1: a reference,
    or a trace label (_TAIL_TRACE_LABELS) and its number, printed after the receiver is skipped too ('<receiver>
    123456', '<receiver> TRN 1234'). The holder's own name is never the person (a business's name printed without its
    form)."""
    classifier = _classifier()
    names = [
        " ".join(word for word in _RECEIVER_LABEL.sub("", found.group(0), count=1).split() if word.isalpha())
        for found in classifier._RECEIVER_FIELD_VALUE.finditer(text)
    ]
    words = tail.split()
    while words and classifier._is_reference_token(words[0]):
        words.pop(0)
    while words and (classifier._is_reference_token(words[-1]) or words[-1] in _TAIL_TRACE_LABELS):
        words.pop()
    if words and all(word.isalpha() for word in words):
        names.append(" ".join(words))
    return any(
        name and _p2p_person_name(name) and not classifier.holder_named(name, account_name)
        and _without_holder_name(name, account_name).strip() == name
        for name in names
    )


def _business_shape(records: Sequence[TransactionClassification], duplicates: set[int]) -> bool:
    """§8.1, §8.8 (audit B7: I09): the statement's account reads as a business's: its account name prints a business
    product word or a legal form (the classifier's _business_account) or a company form, or the statement shows the
    holder's own payroll (a posted debit the classifier reads as payroll). Any other account is consumer-shaped, and a
    direct deposit to it is a person's pay (_direct_deposit_pay)."""
    classifier = _classifier()
    account_name = records[0].account_name if records else None
    holder = classifier.account_name_text(account_name)
    if classifier._business_account(account_name) or (holder and classifier.company_form(holder)):
        return True
    return any(
        index not in duplicates and record.amount < 0 and record.is_posted and record.classification == "payroll"
        for index, record in enumerate(records)
    )


def lending_bank_payer(text: str, region: str) -> bool:
    """§8.1, T4 (audit B6: I23): a lending bank (_LENDING_BANK_PAYER) is the payer: read on the payer region, or, on a
    row with no payer region, on the row before its receiver fields with the posting labels removed (_hold_text), as
    financing_named reads it. Celtic Bank's Bluevine line (DES BV LOAN) is the registry's financing proceeds already."""
    return _LENDING_BANK_PAYER.search(region or _hold_text(text)) is not None


def _wire_label_only(region: str) -> bool:
    """§8.5, Q5 (audit B5: I14): a wire's payer region that names nobody: no name word (payer_name is empty), or only
    a bank's or a layout's labels (_WIRE_LABEL_ONLY_WORDS)."""
    words = _classifier().payer_name(region).split()
    return all(word in _WIRE_LABEL_ONLY_WORDS for word in words)


#: §8.5, Q5 (audit round 3, R3-B07: R3-40; the underwriter's Q1 of 2026-10-02, every wire with no sender held): the
#: words a wire's region may print besides its labels that name nobody, beside the classifier's generic words
#: (REVENUE_GENERIC_WORDS, joined at call time: _wire_designation_words): the account-designation and product words,
#: the holder-noise name words, the filler and purpose words and the legal forms. Never a place or nationality word (a
#: numbered company's or a real name's: the provinces, CANADA, USA, AMERICA, AMERICAN, NATIONAL), and never INTEREST
#: or another word a non-sale hold reads ('WIRE TRANSFER IN <ref> INTEREST' keeps its non-sale hold).
_WIRE_DESIGNATION_OWN_WORDS = frozenset({
    # Account designations and products.
    "BUSINESS", "OPERATING", "OPERATIONS", "CHECKING", "SAVINGS", "ACCOUNT", "ACCT", "DDA", "SAV", "CHK", "MONEY",
    "MARKET", "COMMERCIAL", "ANALYZED", "PREMIUM", "PLATINUM", "SELECT", "PREFERRED", "STANDARD", "BASIC", "SIMPLE",
    "ESSENTIALS", "FUNDAMENTALS", "COMPLETE", "ADVANTAGE", "PERFORMANCE", "EVERYDAY", "PLUS", "ELITE", "FREE", "SMALL",
    "TOTAL",
    # Holder-noise name words.
    "TRUST", "GROUP", "HOLDINGS", "SERVICES", "SOLUTIONS", "MANAGEMENT", "ENTERPRISES", "DBA",
    # Filler and purpose words.
    "AMOUNT", "RENT", "THE", "OF", "AND",
    # Legal forms.
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "PLLC", "ULC",
    "PLC",
})


@cache
def _wire_designation_words() -> frozenset[str]:
    """§8.5, Q5 (audit round 3, R3-B07: R3-40): _WIRE_DESIGNATION_OWN_WORDS and the classifier's generic words."""
    return _WIRE_DESIGNATION_OWN_WORDS | _classifier().REVENUE_GENERIC_WORDS


def _wire_names_nobody(region: str) -> bool:
    """§8.5, Q5 (audit round 3, R3-B07: R3-40; the underwriter's Q1 of 2026-10-02): a wire's payer region that names no
    sender: only labels (_wire_label_only), or only label, holder-noise, account-designation, purpose, filler or
    legal-form words (_WIRE_LABEL_ONLY_WORDS, _wire_designation_words: 'BUSINESS', 'OPERATING ACCOUNT', 'BUSINESS LLC',
    'THE AMOUNT OF'), on every wire layout and the labelled path. A numbered company keeps its reading (the
    classifier's _NUMBERED_COMPANY_REGION or _NUMBERED_PROVINCE_START: '1234567 ONTARIO INC', '1234567 B C LTD',
    OQ3)."""
    if _wire_label_only(region):
        return True
    classifier = _classifier()
    if (
        classifier._NUMBERED_COMPANY_REGION.search(region) is not None
        or classifier._NUMBERED_PROVINCE_START.match(region) is not None
    ):
        return False
    nobody = _WIRE_LABEL_ONLY_WORDS | _wire_designation_words()
    return all(word in nobody for word in classifier.payer_name(region).split())


def _sending_bank_after_label(text: str, region: str, bank: str | None) -> bool:
    """§8.5, Q5 (audit round 3, R3-B07: R3-42): on a row the classifier reads its sender after the wire's label
    (_WIRE_SENDER_AFTER_LABEL, no originator label: _WIRE_ORIGINATOR_LABEL), a region that is only a bank's channel name
    (_bank_only_payer: a listed sending bank's name or the statement's own bank's, after reference tokens and a trailing
    ACH or N A) names no sender ('INBOUND WIRE <sending bank>'). A bank by its own form keeps the bank-originated
    hold."""
    classifier = _classifier()
    if classifier._WIRE_SENDER_AFTER_LABEL.match(text) is None or classifier._WIRE_ORIGINATOR_LABEL.search(text):
        return False
    return _bank_only_payer(region, "", bank) in {"sending", "own"}


def _wire_region_names_nobody(text: str, region: str, bank: str | None) -> bool:
    """§8.5, Q5: the wire channel's blank point (_facts_region, _customer_financier): a region that names nobody
    (_wire_names_nobody, audit round 3: R3-40), a bare incoming wire (the classifier's _bare_incoming_wire, R2-B10
    review round 1: R11) or a sending bank's channel name printed after the wire's label (_sending_bank_after_label,
    audit round 3: R3-42)."""
    return bool(region) and (
        _wire_names_nobody(region) or _classifier()._bare_incoming_wire(text)
        or _sending_bank_after_label(text, region, bank)
    )


def _cut_wire_legal_form(region: str) -> bool:
    """§8.5, Q5's repeat arm (audit B5: I61): a wire sender whose LLC the originator field cut to LL and glued to the
    address after it ('<name> MANAGEMENT LL<city>'): a word after the first that is LL and two or more letters, ending
    the field (its LL within _WIRE_CUT_FORM_SLACK characters of _WIRE_ORIGINATOR_WIDTH). Never a two-letter prefix of
    another form (CO, IN, LI), never a name word that starts with LL earlier in the name ('JOHN LLOYD'), and never
    read by Q6's company form (company_form)."""
    words = region.split()
    for index in range(1, len(words)):
        if _CUT_LLC.fullmatch(words[index]):
            width = len(" ".join(words[:index])) + len(" LL")
            return _WIRE_ORIGINATOR_WIDTH - _WIRE_CUT_FORM_SLACK <= width <= _WIRE_ORIGINATOR_WIDTH
    return False


def _bank_originated_wire(text: str, region: str, *, wire: bool = False) -> bool:
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
    originator_address: a ZIP or the country code after it, or the end of a Fedwire or CHIPS B/O city and state).

    Audit B5 (I14, I23; the orchestrator's ruling): read on every row pass 7's wire channel reads (`wire`), not only
    on a row an incoming-wire label starts ('<BANK> N A WIRE', Mercury's '<sender> WIRE' layout); never on a region of
    labels alone ('BANK WIRE DEPOSIT' names no sender: _wire_label_only)."""
    classifier = _classifier()
    if (
        not region or not (wire or classifier._is_wire_row(text)) or classifier.BANK_SETTLEMENT_ORIGINATOR.search(region)
        or _wire_label_only(region)
    ):
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


def _holder(record: TransactionClassification) -> str | None:
    """Audit B9 (I13): the holder's name the holds read: the statement's holder name when its parser read one, else
    its account-name field (classifier.holder_reading)."""
    return _classifier().holder_reading(record.account_name, record.holder_name)


def _holder_names(record: TransactionClassification) -> tuple[str, ...]:
    """§5.2, §8.1 (audit B9 review round 1: I13): the names the holder hold reads: the holder's name (_holder), and,
    beside a parser's holder name, the account-name field when it names a holder too (_usable_holder_name: a person or a
    company, never a product; review round 2: never a product a holder reader publishes, PNC's 'Treasury Enterprise
    Plan' included), as each side of a DBA name is read: a layout that prints the owner there keeps the owner's own
    money held."""
    return _holder_names_of(record.account_name, record.holder_name)


def _holder_names_of(account_name: str | None, holder_name: str | None) -> tuple[str, ...]:
    """_holder_names on a statement's account-name field and holder name (audit round 3, R3-B14 review round 1)."""
    classifier = _classifier()
    holder = classifier.holder_reading(account_name, holder_name)
    names = [holder] if holder else []
    if holder_name and account_name and _usable_holder_name(account_name):
        if classifier.account_name_text(account_name) != classifier.account_name_text(holder):
            names.append(account_name)
    return tuple(names)


def region_names_holder(record: TransactionClassification, text: str, region: str) -> bool:
    """§14.3 G3 (audit B9 review round 1: I13): the census's holder fact, read as pass 7's holder hold reads the payer
    region: any of the holder's names (_holder_names), the row's layout setting where another payer's receiver block
    can print (classifier.holder_receiver_block), a processor's settlement under the merchant's own name aside
    (merchant_settlement), and (audit round 2, R2-B02: R18) a platform's payout known by its payout id
    (processor_payout), and (audit round 2, R2-B04: R04 part 1) a processor's, a platform's or a franchisor's credit
    printing the merchant's own name (platform_credit)."""
    classifier = _classifier()
    names = _holder_names(record)
    if (
        not region or not names or merchant_settlement(text, names) or processor_payout(text)
        or platform_credit(text, region, names)
    ):
        return False
    block = classifier.holder_receiver_block(text, record.bank)
    return any(classifier.holder_named(region, name, receiver_block=block) for name in names)


#: §5.2 (audit round 2, R2-B04: R19): the legal forms a holder's name may end with that the classifier's company form
#: leaves out: a trailing CO after two words or more (holder_name._LEGAL_FORMS counts it; the payer readers never do,
#: since CO is also Colorado's code, D11, while a header or mailing-block name prints no address), and Quebec's
#: partnership S.E.N.C. (normalized 'S E N C') or SENC. A city and state ('SAMPLEVILLE CO') stays no name.
_HOLDER_TRAILING_FORM = re.compile(r"^\S+ \S+ (?:.* )?CO$|^\S+ (?:.* )?(?:S E N C|SENC)$")
#: §5.2 (audit round 2, R2-B04: R19): the markers that join two names of the holder's inside its name: a trade name
#: (the classifier's _HOLDER_TRADE_NAME: DBA, D B A, AKA) and BMO's 'Operating as:'.
_HOLDER_NAME_MARKER = re.compile(r" (?:DBA|D B A|AKA|OPERATING AS) ")
#: §5.2 (audit round 2, R2-B04: R19): the words a partnership's name joins its partners with ('&' normalizes to AND).
_HOLDER_PARTNER_WORDS = frozenset({"AND"})


def _usable_holder_name(account_name: str | None) -> bool:
    """§5.2 (A3-G refinement): the holder's name (`account_name`: holder_reading's name) names its holder: a company
    form, or a person's name (two to four words of letters, none a product, noise or generic word). A product name
    ('BUSINESS ADVANTAGE CHECKING') or an empty field names nobody. Audit B9 (I13): nor does Chase's summary grid header
    ('INSTANCES AMOUNT') or a name of the holder test's bank and product abbreviations (BMO BUS CKG, GENERAL). Review
    round 2: nor a product a holder reader publishes, whose words are no noise (classifier.account_product: PNC's
    'Treasury Enterprise Plan'). Audit round 2, R2-B04 (R19): a holder's own legal forms the company form leaves out
    name it too (_HOLDER_TRAILING_FORM: a trailing CO after two words or more, S.E.N.C.); a name that joins two names
    (_HOLDER_NAME_MARKER: DBA, AKA, BMO's 'Operating as') names its holder when either side does; and a leading THE and
    a partnership's AND between words are read as no word of the name. A name of five words or more with no form still
    names nobody."""
    return _usable_holder_text(_classifier().account_name_text(account_name))


def _usable_holder_text(name: str) -> bool:
    """§5.2 (audit round 2, R2-B04: R19): _usable_holder_name on a normalized name."""
    classifier = _classifier()
    if not name or classifier._summary_grid_header(name):
        return False
    if classifier.company_form(name) or _HOLDER_TRAILING_FORM.search(name):
        return True
    if classifier.account_product(name):
        return False
    sides = _HOLDER_NAME_MARKER.split(name)
    if len(sides) > 1:
        return any(_usable_holder_text(side.strip()) for side in sides)
    words = name.split()
    if words and words[0] == "THE":
        words = words[1:]
    words = [
        word for index, word in enumerate(words)
        if not (word in _HOLDER_PARTNER_WORDS and 0 < index < len(words) - 1)
    ]
    return 2 <= len(words) <= 4 and all(
        word.isalpha() and word not in classifier._HOLDER_TEST_NOISE and word not in classifier.REVENUE_GENERIC_WORDS
        for word in words
    )


def _holder_name_known(name: str | None) -> bool:
    """§5.2, §8.1 (audit B9: I13): the holder's name is known well enough to switch the receiver fields' holder names
    off (_receiver_holder_names): a usable name (_usable_holder_name) with a company form or three words or more. A
    bare two-word fragment needs corroboration, so the receiver fields are still read beside it."""
    if not _usable_holder_name(name):
        return False
    classifier = _classifier()
    text = classifier.account_name_text(name)
    return classifier.company_form(text) or len(text.split()) > 2


#: §8.2, §8.10 (audit B10: I05, I60): the reason of a counted credit whose payer text the parser could not read (the
#: parser's own mark, Transaction.payer_text_unread). Q2's no_payer_printed is for a row whose statement prints no payer;
#: this one is for a row whose statement printed one the parser lost. Counted and flagged, never Verified.
PAYER_TEXT_NOT_READ = "payer_text_not_read"
#: The owner's ruling of 2026-10-02 (the underwriter's Q3; spec §8.4, §8.10 step 26, §19.1): every posted Zelle
#: deposit is non_revenue with this reason, whoever sent it, a lender or a processor paying through Zelle included
#: (_zelle_excluded). A row a non-revenue rule already decided keeps that rule, and a direction conflict keeps its hold.
ZELLE_EXCLUDED = "zelle_excluded"
#: Q3 (2026-10-02): the method and the rule of a Zelle deposit the policy excluded.
ZELLE_POLICY_METHOD = "zelle_deposit_excluded"
#: Q3 (2026-10-02): the context signal that keeps the rules' own reading of an excluded Zelle deposit
#: ('zelle_prior:<tier>:<reason>', read by zelle_prior_reading).
_ZELLE_PRIOR = "zelle_prior:"
#: Q3 (2026-10-02): the Zelle rail, read on the revenue text before the receiver fields (zelle_deposit). The corpus
#: prints it as 'ZELLE PAYMENT FROM <sender> (CONF#)', 'ZELLE FROM <sender> ON ## ## REF', 'ZELLE INSTANT PMT FROM',
#: 'ZELLE BUSINESS PAYMENT FROM <sender> PAYMENT ID', 'ZELLE CREDIT (FROM)', 'ZELLE MONEY RECEIVED FROM', 'TRANSFER IN
#: ZELLE FROM', 'TD ZELLE RECEIVED', Citizens' '... CREDIT ZELLE CREDIT ... ZELLE <name>', Navy Federal's 'ZELLE (CR)
#: <name>' and PNC's 'Zel From <name>', with a date or a reference glued on either side ('ZELLE1234567', '0302ZELLE':
#: the right boundary is a letter, so the glued reference reads with or without the revenue text's rail split). The
#: left boundary is the card forms' (no letter before), so a name holding the letters (HAZEL, ROSZELL, MAZZELLA,
#: ZELLER, EZELL) is never read. The classifier's _CONSUMER_P2P_RAIL, shared with the legacy classes and the debits,
#: does not read PNC's ZEL and is not changed. Audit round 3, R3-12: pass 7 reads PNC's ZEL as its ZELLE twin on its
#: own text (pass_text); the ZEL arm stays here for the readers of the raw text (R2-OW16's own-account pass, the
#: lessor and asset-sale carve-outs).
_ZELLE_RAIL = re.compile(r"(?<![A-Z])ZELLE(?![A-Z])|(?<![A-Z])ZEL (?:FROM|TO)\b")
#: Audit round 3, R3-12 (the owner's amendment of 2026-10-06 to the underwriter's Q3: "holds as for other P2P"): PNC's
#: spelling of the Zelle rail, 'ZEL FROM <sender>' and 'ZEL TO <recipient>', which pass_text spells 'ZELLE '.
_ZEL_SPELLING = re.compile(r"(?<![A-Z])ZEL (?=(?:FROM|TO)\b)")
#: The owner's ruling of 2026-10-02 (the underwriter's Q12), R2-OW03 (spec §5.3; the Q12 card's open point 2, its
#: default): the display reason a government payment that prints no purpose carries (§6.1 step 3a decided it
#: non_revenue, method GOVERNMENT_NO_PURPOSE_METHOD), so the non-revenue breakdown names the excluded government money.
#: Display only: the row's tier, state, method, rule and flags are step 3a's, and it has no review path.
GOVERNMENT_NO_PURPOSE = "government_no_purpose"
GOVERNMENT_NO_PURPOSE_METHOD = "government_no_purpose_exclusion"


def pass_text(record, text: str) -> str:
    """Audit round 3, R3-12 (§8.4; the owner's amendment of 2026-10-06 to the underwriter's Q3, R2-OW17: "holds as for
    other P2P"): the credit text pass 7's payer facts, holds, counter-credit reading and Zelle step read, and the
    census's facts (guard_facts) and the served Zelle view (zelle_view._reads_zelle) read: the revenue text without TD
    Canada Trust's e-Transfer code (without_transfer_code, audit round 2, R2-B11), with PNC's Zelle rail, printed
    'ZEL FROM <sender>' or 'ZEL TO <recipient>' (_ZEL_SPELLING), spelled as its ZELLE twin. So a PNC Zelle credit reads
    as the same sender's 'ZELLE FROM' row: the person-to-person channel (_p2p_rail), the payer region and key (pooled
    with that sender's ZELLE rows), the round-sum repeat, and R2-B02's (R02) person match of the counter-debit hold.
    `record` needs only its bank and printed description. The classifier's _CONSUMER_P2P_RAIL (the 5.5 channel gate,
    the legacy classes, the debits) is unchanged: a 'ZEL TO' debit keeps the classifier's debit reading. Review round 1
    (§8.4's residuals): the classifier's earlier reading of the raw text is not pass 7's, so a ZEL credit whose sender
    looks like an operating platform is still claimed as an operating source (counted, and Verified on a repeat), and
    a 'ZEL TO' debit keeps its legacy class 'other' and no person key (a credit for its own amount, or one with no
    person key, names it by the first word)."""
    return _ZEL_SPELLING.sub("ZELLE ", without_transfer_code(record, text))


def zelle_deposit(text: str) -> bool:
    """Q3 (2026-10-02, spec §8.4): the credit's revenue text prints the Zelle rail before its receiver fields
    (_ZELLE_RAIL). Audit round 3, R3-56: an incoming wire or a loose wire's originator row is never a Zelle deposit,
    whatever its memo prints ('PMT DET:INVOICE <n> PAID BY WIRE INSTEAD OF ZELLE'): an incoming wire (the classifier's
    _is_wire_row) or a loose wire's originator row (_loose_wire_originator, as merchant_settlement reads it; read on
    the row up to its first Zelle word, since the classifier's loose-wire label refuses a row that prints a consumer
    rail, so a word in the originator's name or memo after the label reads as the wire's) is not read. The ACH
    entry-description forms ('DES:ZELLE') and the rail printed mid-row are kept; a company whose name holds the word
    ZELLE paying by ACH still reads (§8.4's residual). Review round 1 (finding 3): a wire layout neither gate reads
    ('<sender> WIRE' with no originator label, 'ONLINE WIRE TRANSFER FROM', 'WIRE TRANS SVC CREDIT', 'WIRE DEPOSIT')
    still reads a memo's ZELLE, and a Zelle row that prints WIRE and an originator label before its rail word is
    refused (§8.4's residuals, 0 corpus rows)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    rail = _ZELLE_RAIL.search(row)
    if rail is None:
        return False
    return not (
        classifier._is_wire_row(text) or classifier._loose_wire_originator(text)
        or classifier._loose_wire_originator(row[: rail.start()])
    )


def _zelle_excluded(record: TransactionClassification) -> TransactionClassification:
    """Q3 (2026-10-02, spec §8.4, §8.10 step 26): a Zelle deposit the rules tiered, excluded by the owner's policy:
    non_revenue, method and rule ZELLE_POLICY_METHOD, reason ZELLE_EXCLUDED. The rules' own reading (its tier and
    reason) stays in the reason sentence and in the zelle_prior signal (zelle_prior_reading); a reason code the table
    does not list names itself. Only the revenue fields and the contribution flags change: the legacy classification,
    the entity, the flag group, the lender-credit exclusion, the withholding flag and the review flag stay."""
    tier, reason = record.revenue_tier, record.revenue_tier_reason
    label = "Verified revenue" if tier == "verified" else REVENUE_TIER_REASONS.get(reason, (None, reason or tier))[1]
    excluded = _classifier()._replace_revenue_state(
        record,
        "non_revenue",
        match_method=ZELLE_POLICY_METHOD,
        matched_rule=ZELLE_POLICY_METHOD,
        confidence_score=1.0,
        reason=(
            "A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec §19.1); the "
            f"rules read it as: {label}."
        ),
        context_signals=(*record.revenue_context_signals, ZELLE_POLICY_METHOD, f"{_ZELLE_PRIOR}{tier}:{reason or ''}"),
        related_transaction=record.revenue_related_transaction,
    )
    return replace(excluded, revenue_tier_reason=ZELLE_EXCLUDED)


def zelle_prior_reading(record: TransactionClassification) -> tuple[str, str | None] | None:
    """Q3 (2026-10-02): the tier and reason the rules gave a Zelle deposit the policy excluded (the zelle_prior
    signal), or None for any other row."""
    for signal in record.revenue_context_signals:
        if signal.startswith(_ZELLE_PRIOR):
            tier, _, reason = signal[len(_ZELLE_PRIOR):].partition(":")
            return tier, reason or None
    return None


def zelle_credits_present(records: Sequence[TransactionClassification], duplicate_indexes: set[int]) -> bool:
    """The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): whether any credit pass 7 reads (posted,
    not a duplicate, carrying a revenue state) prints the Zelle rail on the pass's own text (zelle_deposit, on
    pass_text). Only such a row can read differently in the counted reading: the Zelle step and the two lifted
    carve-outs read nothing else, so a statement without one has a single reading."""
    classifier = _classifier()
    return any(
        index not in duplicate_indexes and record.amount > 0 and record.is_posted
        and record.revenue_classification is not None
        and zelle_deposit(pass_text(record, classifier.revenue_text(record.normalized_description)))
        for index, record in enumerate(records)
    )


#: Audit B10 (I05): the share of a statement's posted credit rows whose payer text was not read above which the
#: statement carries the payer_text_unread fact (metrics.payer_text_unread): its True rests on rows nobody read.
PAYER_TEXT_UNREAD_SHARE = 0.30


def payer_text_unread_indexes(transactions: Sequence) -> frozenset[int]:
    """Audit B10 (I05, I60): the ledger indexes of the credits the parser marked as read only by their label
    (Transaction.payer_text_unread)."""
    return frozenset(
        index for index, transaction in enumerate(transactions)
        if getattr(transaction, "payer_text_unread", False) and transaction.amount > 0
    )


#: Audit round 2, R2-B07 (R07): the reason of a credit the parser marked unread whose unread run of payer blocks prints
#: a lender's or a lending bank's block (unread_run_names_financing): held, never counted, since one row of the run is
#: that lender's money and the text cannot say which.
UNREAD_RUN_NAMES_FINANCING = "unread_run_names_financing"
#: Audit round 2, R2-B07 (R07): the ACH standard entry class code an ACH block closes on (`<originator> <entry> <id>
#: <receiver> CCD`), read on the normalized text: layout grammar, where a run of welded blocks splits into its blocks.
#: Audit round 3, R3-B09 (R3-87): a class-code word followed by a legal form is part of a name, never a block's end
#: (CashArc's ACH company name 'CASH-ARC LLC', normalized 'CASH ARC LLC', the registry's alias), as the counted
#: template's one-block count reads it (core_processor_counted._ACH_CLASS_CODE). R3-B09 review round 1: the LLC family
#: only (LLC, L L C, LLP, PLLC), as that count reads it: INC, CO, COMPANY, CORP, LTD, LP and the rest open real
#: originator names, so a code before them closes its block and the next block opens on them.
_UNREAD_BLOCK_END = re.compile(
    r"\b(?:CCD|CTX|PPD|WEB|IAT|TEL|POP|ARC|BOC|RCK|CIE)\b"
    r"(?! (?:LLC|L L C|LLP|PLLC)\b)"
)
#: Audit round 2, R2-B07 (R07): the registry states whose block in an unread run holds its rows: the lender and
#: financing states (LENDER_DEBIT_STATES) without an alternative position (a platform's own settlement of the
#: merchant's sales) and a factor (whose payout is counted and flagged, never held).
_UNREAD_RUN_LENDER_STATES = LENDER_DEBIT_STATES - {"alternative_position", "factoring"}


def payer_text_unread_texts(transactions: Sequence) -> dict[int, str]:
    """Audit round 2, R2-B07 (R07): the unread payer text (Transaction.unread_payer_text) of each credit the parser
    marked as read only by its label, by ledger index."""
    return {
        index: text for index, transaction in enumerate(transactions)
        if getattr(transaction, "payer_text_unread", False) and transaction.amount > 0
        and (text := getattr(transaction, "unread_payer_text", "") or "")
    }


def unread_run_blocks(text: str) -> list[str]:
    """Audit round 2, R2-B07 (R07): an unread run of welded payer blocks, normalized and split after each ACH class
    code (_UNREAD_BLOCK_END); words after the last code are one more block."""
    normalized = normalize_transaction_description(text)
    blocks: list[str] = []
    start = 0
    for found in _UNREAD_BLOCK_END.finditer(normalized):
        blocks.append(normalized[start:found.end()].strip())
        start = found.end()
    blocks.append(normalized[start:].strip())
    return [block for block in blocks if block]


def unread_run_names_financing(text: str) -> bool:
    """Audit round 2, R2-B07 (R07): one block of an unread run (unread_run_blocks) names a registry lender of
    _UNREAD_RUN_LENDER_STATES (match_known_payee, read as a credit) or a lending bank (_LENDING_BANK_PAYER). The bare
    financing root is never read: a customer named CAPITAL is no lender."""
    for block in unread_run_blocks(text):
        known = match_known_payee(block, credit=True)
        if known is not None and known.state in _UNREAD_RUN_LENDER_STATES:
            return True
        if _LENDING_BANK_PAYER.search(block):
            return True
    return False


def payer_text_unread(
    transactions: Sequence, records: Sequence[TransactionClassification],
) -> tuple[bool, int]:
    """Audit B10 (I05): (the statement's payer text is mostly unread, the count of its unread posted credits): more
    than PAYER_TEXT_UNREAD_SHARE of its posted credit rows (duplicates aside) carry the parser's mark. Published as
    metrics.payer_text_unread and metrics.payer_text_unread_count."""
    unread = payer_text_unread_indexes(transactions)
    posted = [
        index for index, record in enumerate(records)
        if record.amount > 0 and record.is_posted and record.duplicate_of is None
    ]
    count = sum(1 for index in posted if index in unread)
    return (bool(posted) and count / len(posted) > PAYER_TEXT_UNREAD_SHARE), count


def holder_unscreened(
    records: Sequence[TransactionClassification], *, holder_name: str | None = None, account_name: str | None = None,
) -> bool:
    """§8.1 (audit B9: I13): no holder's name is known for the statement, so no holder test can see the holder's own
    money: the holder's name (_holder) names nobody (_usable_holder_name) and the statement's receiver fields name no
    holder (_receiver_holder_names). Published as metrics.holder_unscreened. Audit round 2, R2-B04 (R19): the names are
    the statement's (its first record's, or `holder_name` and `account_name` for a statement with no transaction); a
    holder's name the parser read is known whenever the holder test reads a word of it (classifier.holder_words, which
    the holder hold reads with no usability test), whatever its shape, and an account-name field is known when it names
    a holder (_usable_holder_name on holder_reading's name)."""
    classifier = _classifier()
    if records:
        holder_name, account_name = records[0].holder_name, records[0].account_name
    if holder_name and holder_name.strip() and classifier.holder_words(holder_name):
        return False
    if _usable_holder_name(classifier.holder_reading(account_name, holder_name)):
        return False
    credits = [index for index, record in enumerate(records) if record.amount > 0 and record.is_posted]
    return not _receiver_holder_names(records, credits)


def _receiver_holder_names(records: Sequence[TransactionClassification], credits: Sequence[int]) -> tuple[str, ...]:
    """§5.2, §8.1 (A3-G refinement): when the statement's account-name field names nobody (audit B9:
    _holder_name_known, which lets a bare two-word fragment through to corroboration, and is read beside the parser's
    holder name, never instead of it), the
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
    # Audit B9 (I13): an account name that names the holder beyond a bare two-word fragment (_holder_name_known)
    # switches the receiver fields off. A holder's name the parser read never does: the receiver fields can name the
    # holder's owner (the bank prints the owner as the receiver), whose own money the holder hold keeps.
    if not credits or _holder_name_known(records[credits[0]].account_name):
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


#: §8.1 (audit B9: I13): a processor's or a platform's settlement or payout entry, which prints the merchant's own
#: name as its originator and its receiver (Worldpay's NET SETTLE, Stripe's NETSWEEP, a beverage distributor's
#: FINTECHEFT, the BANKCARD and MERCH deposit forms): never the holder's own push, never held as the holder's name.
_MERCHANT_SETTLEMENT_ENTRY = re.compile(
    r"(?<![A-Z])(?:NET (?:SETTLE|SETLMT|STLMT|SETL)|NETSWEEP|FINTECHEFT|BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD"
    r"|MERCH|MERCHANT|MERCHPAYO\w*|MRCHNTSRVS)(?:SEC)?(?![A-Z])"
)
#: §8.1 (audit round 3, R3-B10: R3-90 part A; standard A1, A2): a bare settlement word under the merchant's own name, a
#: processor's, a carrier's or an operating settlement, read by merchant_settlement beside _MERCHANT_SETTLEMENT_ENTRY on
#: a row that is no transfer and no person-to-person row. R3-B10 review round 2 (finding 1): a row this word alone
#: releases is counted, never verified and never a repeat, in each spelling, slot and boundary
#: (CreditFacts.settlement_released).
_HOLDER_NAMED_SETTLEMENT_ENTRY = re.compile(r"(?<![A-Z])(?:SETTLEMENT|SETTLMT|STLMT)(?![A-Z])")
#: §8.1 (audit round 3, R3-B10 review round 2: finding 1): the method and the matched rule pass 7 gives a settlement
#: under the merchant's own name that an earlier rule verified and that only the bare settlement word lifted from the
#: own-push guard (_settlement_never_verified).
HOLDER_NAMED_SETTLEMENT_METHOD = "holder_named_settlement"
HOLDER_NAMED_SETTLEMENT_RULE = "holder_named_settlement_never_verified"
#: §8.1 (audit B9: I13): Capital One's incoming ACH row, which prints the receiver (the holder) with no label after the
#: originator, its entry and a digit run.
_CAPITAL_ONE_BANK = re.compile(r"(?<![A-Z])CAPITAL ONE\b", re.IGNORECASE)
_CAPITAL_ONE_TRAILING_RECEIVER = re.compile(
    r"^ACH DEPOSIT (?P<originator>[A-Z][A-Z ]*?) \d{4,} (?P<receiver>[A-Z][A-Z ]*?)(?= \S*\d|$)"
)
#: §8.1 (audit round 2, R2-B04: R04 part 3): the tails Mercury's push prints on Capital One's row, its product after
#: the originator ('<holder> MERCURYACH') and its code after the receiver ('<holder> MRCR <ref>'), read off before the
#: self test compares the two names.
_CAPITAL_ONE_ORIGINATOR_TAIL = re.compile(r"\s*\bMERCURYACH$")
_CAPITAL_ONE_RECEIVER_TAIL = re.compile(r"\s*\bMRCR$")
#: §8.1 (audit B9: I13): the legal forms an originator or a receiver field prints after the name or leaves off (a
#: field cut inside L L C leaves a single letter). CO and COMPANY stay: left off, they would make an insurer's 'X INS
#: CO' the start of an agency's 'X INS AGENCY'.
_SELF_TEST_LEGAL_FORMS = frozenset({"LLC", "INC", "CORP", "LTD", "LIMITED", "LP", "LLP", "PLLC", "L", "C"})
#: §8.1 (audit B9: I13): a name one field cut names the other's holder with this many characters or more.
_SELF_TEST_CUT_CHARACTERS = 15


def _self_test_name(name: str) -> str:
    """§8.1 (audit B9: I13): a name as the self test compares it: its words of letters, the legal forms at its end
    left off."""
    words = [word for word in name.split() if word.isalpha()]
    while words and words[-1] in _SELF_TEST_LEGAL_FORMS:
        words.pop()
    return " ".join(words)


def _same_name(originator: str, receiver: str) -> bool:
    """§8.1 (audit B9: I13): two fields print one name: equal, or one starts the other at a word with two words or more,
    or as a cut of _SELF_TEST_CUT_CHARACTERS characters or more (the census's class B reading). One shared first word
    is not one name ('NORTHWIND' and 'NORTHWIND MARINE')."""
    ours, theirs = _self_test_name(originator), _self_test_name(receiver)
    if len(ours.replace(" ", "")) < 3 or len(theirs.replace(" ", "")) < 3:
        return False
    shorter, longer = sorted((ours, theirs), key=len)
    if shorter == longer:
        return True
    return longer.startswith(shorter) and (
        len(shorter) >= _SELF_TEST_CUT_CHARACTERS or (longer[len(shorter)] == " " and len(shorter.split()) >= 2)
    )


def merchant_settlement(text: str, names: Sequence[str] = (), *, bare_settlement: bool = True) -> bool:
    """§8.1 (audit B9: I13): the row prints a processor's or a platform's settlement or payout entry under the
    merchant's own name (_MERCHANT_SETTLEMENT_ENTRY), read before the receiver fields: the holder holds skip it. Audit
    B9 review round 1: the entry is read outside the holder's own name (each of `names`, each side of a DBA name, its
    runs as _without_holder_name removes them), so a holder whose name prints MERCHANT, MERCH or BANKCARD keeps its own
    money held, and never on an incoming wire or a person-to-person or push rail, which print no processor's
    settlement. Audit round 3, R3-B10 (R3-90 part A): a bare SETTLEMENT, SETTLMT or STLMT read there too
    (_HOLDER_NAMED_SETTLEMENT_ENTRY), on a row that is no transfer or person-to-person row (a transfer printing the
    word is the holder's own money): the holds skip it, and it takes its own reading, counted and never verified.
    R3-B10 review round 2 (finding 1): with `bare_settlement` False that arm is not read (B9's words alone), the
    reading credit_facts compares to name a row the bare word alone released (CreditFacts.settlement_released)."""
    classifier = _classifier()
    if classifier._is_wire_row(text) or classifier._loose_wire_originator(text):
        return False
    row = classifier._before_receiver(text)
    if _p2p_rail(row) or classifier._PUSH_RAIL.search(row):
        return False
    outside = _outside_holder_names(row, names)
    if _MERCHANT_SETTLEMENT_ENTRY.search(outside) is not None:
        return True
    return (
        bare_settlement and _HOLDER_NAMED_SETTLEMENT_ENTRY.search(outside) is not None
        and not classifier._is_transfer_or_p2p_row(text)
    )


def _outside_holder_names(row: str, names: Sequence[str]) -> str:
    """§8.1 (audit B9 review round 1: I13): `row` without the holder's own names: each of `names`, whole, each side of a
    DBA name, and its runs as _without_holder_name removes them (merchant_settlement's reading; audit round 2, R2-B04:
    R04, platform_credit's)."""
    classifier = _classifier()
    for name in names:
        printed = classifier.account_name_text(name)
        for side in (printed, *classifier._HOLDER_TRADE_NAME.split(printed)) if printed else ():
            row = _without_holder_name(row, side, whole_name=True)
    return row


#: §8.1 (audit round 2, R2-B04: R04 part 1): the operating registry's source types whose entity is a processor or a
#: platform that pays the merchant its own sales (every type but a known operating counterparty).
_PLATFORM_SOURCE_TYPES = frozenset({
    "merchant_processor", "customer_payment_platform", "ecommerce_platform", "ecommerce_marketplace",
    "delivery_marketplace", "booking_marketplace", "transport_marketplace", "invoice_and_receivables",
    "property_management_payments", "wholesale_auto_auction",
})
#: §8.1 (audit round 2, R2-B04: R04 part 1): a franchisor's or a platform's fee entry, which a franchise system's
#: marketing, technology or royalty fund prints when it credits a location under the location's own name ('FRAN <n>
#: MARKETING FEE', 'TECHNOLOGY FEES').
_PLATFORM_FEE_ENTRY = re.compile(r"(?<![A-Z])(?:FRAN[A-Z]*|ROYALTY|MARKETING|TECHNOLOGY|ADVERTISING) FEES?(?![A-Z])")
#: §8.1 (audit round 2, R2-B04: R04 part 1): a bank's field that cuts a processor's or a platform's one-word name at the
#: originator's end keeps this many letters or more and drops at most _PLATFORM_CUT_DROPS (a ten-letter processor's
#: name printed with its last letter cut), and the cut is no generic or holder-noise word, so a whole word that starts
#: a name ('SHOP', 'PAYMENT' for 'PAYMENTECH', 'BUILDER' for 'BUILDERTREND') is never read as one.
_PLATFORM_CUT_LETTERS = 7
_PLATFORM_CUT_DROPS = 2


@cache
def _platform_names() -> tuple[re.Pattern[str], tuple[str, ...]]:
    """§8.1 (audit round 2, R2-B04: R04 part 1): the processors' and platforms' names as a whole-word pattern (the
    operating registry's aliases and their sixteen-character cuts for the _PLATFORM_SOURCE_TYPES entities, the bare
    platform names and the card-payout processors' names), and their one-word names a bank may cut."""
    classifier = _classifier()
    names = {
        alias for entity, aliases in OPERATING_REVENUE_READ_ALIASES.items()
        if OPERATING_REVENUE_SOURCE_TYPES.get(entity) in _PLATFORM_SOURCE_TYPES for alias in aliases
    }
    names.update(BARE_PLATFORM_NAMES)
    names.update(name for spellings in CARD_PAYOUT_PROCESSOR_NAMES.values() for name in spellings)
    normalized = {classifier.normalize_transaction_description(name).strip() for name in names} - {""}
    pattern = re.compile(
        r"(?<![A-Z0-9])(?:" + "|".join(re.escape(name) for name in sorted(normalized, key=len, reverse=True))
        + r")(?![A-Z0-9])"
    )
    words = tuple(sorted(name for name in normalized if name.isalpha() and len(name) > _PLATFORM_CUT_LETTERS))
    return pattern, words


def platform_credit(text: str, region: str, names: Sequence[str] = ()) -> bool:
    """§8.1 (audit round 2, R2-B04: R04 part 1; standard A1, A2): the row is a processor's, a platform's or a
    franchisor's credit that prints the merchant's own name, never the holder's own money: read outside the holder's
    names (`names`, _outside_holder_names), its originator (the payer region, or the row's hold text when it prints
    none) prints a processor's or a platform's name (_platform_names: the operating registry's processors and
    platforms, the bare platform names such as INTUIT, the card-payout processors), or its last word is one of their
    one-word names cut by the bank's field (_PLATFORM_CUT_LETTERS letters or more, at most _PLATFORM_CUT_DROPS dropped,
    never a generic or holder-noise word: 'LIGHTSPEE'); or the row prints a franchisor's or a
    platform's fee entry (_PLATFORM_FEE_ENTRY). Never on an incoming wire or a person-to-person or push rail
    (merchant_settlement's gate), which keep the holder hold. It lifts the holder holds only (pass 7's and the census's
    holder fact, region_names_holder), never verifies."""
    classifier = _classifier()
    if classifier._is_wire_row(text) or classifier._loose_wire_originator(text):
        return False
    row = classifier._before_receiver(text)
    if _p2p_rail(row) or classifier._PUSH_RAIL.search(row):
        return False
    if _PLATFORM_FEE_ENTRY.search(_outside_holder_names(row, names)) is not None:
        return True
    originator = _outside_holder_names(region or _hold_text(text), names).split()
    if not originator:
        return False
    pattern, words = _platform_names()
    if pattern.search(" ".join(originator)) is not None:
        return True
    last = originator[-1]
    if len(last) < _PLATFORM_CUT_LETTERS or last in classifier.HOLDER_NOISE:
        return False
    return any(
        word != last and word.startswith(last) and len(word) - len(last) <= _PLATFORM_CUT_DROPS for word in words
    )


#: §8.1 (audit round 2, R2-B02: R18): a platform's payout id printed in the ACH id field, normalized: Bank of America's
#: 'ID:ST-<id>' and Chase's 'IND ID:ST-<id>' (Stripe's payout id, ten characters or more), which a platform's payout
#: under the merchant's statement descriptor prints ('<descriptor> DES:<descriptor> ID:ST-<id> INDN:<merchant>').
#: R2-B02 review round 1: the id holds letters and digits, as _PAYOUT_FORMS's ST id does: a town printed after an ID
#: label ('ID:ST <town>') or a number alone is no payout id.
_PROCESSOR_PAYOUT_ID = re.compile(
    r"(?<![A-Z0-9])ID ST (?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{10,}(?![A-Z0-9])"
)


def processor_payout(text: str) -> bool:
    """§8.1 (audit round 2, R2-B02: R18; standard A1): the row is a platform's payout, known by its payout id
    (_PROCESSOR_PAYOUT_ID), whatever originator or entry it prints (a payout under the merchant's own descriptor
    included), never on an incoming wire or a person-to-person or push rail (merchant_settlement's gate). It replaces
    B9's entry-word reading (an entry leading with the originator's first word, which the holder's own push printing its
    name passes too). It lifts holds only (the holder holds, region_names_holder, and the counter-debit hold beside the
    platform's own pull, also_debited), never verifies: a platform also pays claims, treasury and capital forms, which
    the other rules decide."""
    if _PROCESSOR_PAYOUT_ID.search(text) is None:
        return False
    classifier = _classifier()
    if classifier._is_wire_row(text) or classifier._loose_wire_originator(text):
        return False
    row = classifier._before_receiver(text)
    return not (_p2p_rail(row) or classifier._PUSH_RAIL.search(row))


#: §8.1 (audit B9 review round 1: I13): the legal forms a wire's sender or beneficiary name ends with, before its
#: address.
_WIRE_PARTY_LEGAL_FORMS = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "PLLC", "PLC",
})
#: §8.1 (audit B9 review round 1: I13): the label a wire's beneficiary field prints before its value.
_WIRE_BENEFICIARY_LABEL = re.compile(r"^(?:N?BNF|BENEFICIARY)(?: NAME)?\s*")


#: §8.1 (audit B9 review round 2: I13): the state codes a wire party's address prints after its town (_US_STATE_TAIL
#: without the country codes), and the country codes it may print after the state.
_WIRE_PARTY_STATES = _US_STATE_TAIL - {"US", "CAUS"}
_WIRE_PARTY_COUNTRIES = frozenset({"US", "USA"})
#: §8.1 (audit B9 review round 2: I13): the fewest words a party's field prints when a town and a state follow its name
#: (two name words, the town, the state).
_WIRE_PARTY_TOWN_STATE_WORDS = 4


def _wire_party(value: str) -> str:
    """§8.1 (audit B9 review round 1: I13): the name a wire's sender or beneficiary field prints: its words up to its
    first token with a digit (the address's number), cut after its first legal form. Review round 2: a name no legal
    form ends is read without the town and state its address prints after it ('NORTHWIND MARINE SAMPLEVILLE TX', a
    country code after the state included), read as one town word before the state (a two-word town leaves its first
    word, which the class-B prefix reading of _same_name still matches against a one-word town), when two name words
    stay before them."""
    words: list[str] = []
    for word in value.split():
        if any(character.isdigit() for character in word):
            break
        words.append(word)
        if word in _WIRE_PARTY_LEGAL_FORMS:
            return " ".join(words)
    if len(words) >= 2 and words[-1] in _WIRE_PARTY_COUNTRIES and words[-2] in _WIRE_PARTY_STATES:
        words.pop()
    if len(words) >= _WIRE_PARTY_TOWN_STATE_WORDS and words[-1] in _WIRE_PARTY_STATES:
        words = words[:-2]
    return " ".join(words)


def _wire_sent_by_its_beneficiary(text: str, region: str) -> bool:
    """§8.1 (audit B9: I13; review round 1): an incoming wire whose sender is its beneficiary, the holder sending from
    its account at another bank: the originator's first two words are the beneficiary's (classifier.
    wire_sender_is_beneficiary, the reading _wire_vetoed refuses Q5 with) and the two whole names are one (_same_name,
    each read by _wire_party), so two companies sharing two first words ('THE SAMPLE COMPANY INC' and 'THE SAMPLE
    BAKERY LLC') are never one sender."""
    classifier = _classifier()
    if not region or not classifier.wire_sender_is_beneficiary(text, region):
        return False
    beneficiary = classifier._CREDIT_WIRE_BENEFICIARY_VALUE.search(text)
    if beneficiary is None:
        return False
    return _same_name(_wire_party(region), _wire_party(_WIRE_BENEFICIARY_LABEL.sub("", beneficiary.group(0).strip())))


def self_originated(text: str, region: str, bank: str | None = None, *, bare_settlement: bool = True) -> bool:
    """§8.1 (audit B9: I13): the row moves the holder's own money in, read on the row alone: an incoming wire whose
    sender is its beneficiary (_wire_sent_by_its_beneficiary), or an ACH or EFT credit whose originator is the row's own
    receiver field (INDN, IND NAME, RECEIVER NAME; Capital One's unlabelled trailing receiver), one name by _same_name.
    A processor's or a platform's settlement or payout under the merchant's own name (merchant_settlement, read outside
    that name; audit round 2, R2-B02: R18, a platform's payout id, processor_payout) is no own push. Held as
    holder_name. Audit round 2, R2-B04: American Express's unlabelled receiver block is paired too (R41), and Capital
    One's pair is read without Mercury's MERCURYACH and MRCR tails (R04 part 3). Audit round 3, R3-B10 review round 2:
    `bare_settlement` is merchant_settlement's (False: B9's settlement words alone)."""
    classifier = _classifier()
    if classifier._is_wire_row(text):
        return _wire_sent_by_its_beneficiary(text, region)
    if processor_payout(text):
        return False
    pairs: list[tuple[str, str]] = []
    if region:
        originator = classifier.payer_name(region)
        pairs.extend(
            (originator, _RECEIVER_LABEL.sub("", found.group(0), count=1))
            for found in classifier._RECEIVER_FIELD_VALUE.finditer(text)
        )
    # Audit round 2, R2-B04 (R41): American Express's receiver block (B5's _AMEX_ACH_CREDIT, read on the regex, so a
    # TRANSFER entry is paired too, on any statement's bank): the originator, and, when the payer region holds two
    # words or more, the region without its last word, the entry the template prints into it ('CONTOSO LLC PAYMENT').
    amex = classifier._AMEX_ACH_CREDIT.match(text)
    if amex is not None and region:
        pairs.append((classifier.payer_name(region), amex.group("receiver")))
        words = region.split()
        if len(words) >= 2:
            pairs.append((" ".join(words[:-1]), amex.group("receiver")))
    if bank and _CAPITAL_ONE_BANK.search(bank):
        trailing = _CAPITAL_ONE_TRAILING_RECEIVER.match(text)
        if trailing is not None:
            # Audit round 2, R2-B04 (R04 part 3): Mercury's push prints its product after the originator (MERCURYACH)
            # and its code after the receiver (MRCR), which are no words of either name.
            pairs.append((
                _CAPITAL_ONE_ORIGINATOR_TAIL.sub("", trailing.group("originator")),
                _CAPITAL_ONE_RECEIVER_TAIL.sub("", trailing.group("receiver")),
            ))
    return any(
        _same_name(originator, receiver)
        and not merchant_settlement(text, (receiver, originator), bare_settlement=bare_settlement)
        for originator, receiver in pairs
    )


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
    known = match_known_payee(segment, credit=True)
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
            # Audit B7 (I09): the direct-deposit words still refuse Q7 alone (G11, fail closed).
            _PAY_WORDS.search(row) or _DIRECT_DEPOSIT_WORDS.search(row) or classifier._is_payroll_provider_row(row)
            or _personal_income(text, row)
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
    region = _dealer_funding_region(text, row, words)
    if region is None:
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


def _dealer_funding_region(text: str, row: str, words: str) -> str | None:
    """§6.1 step 4 (Q7): the payer region of a credit Q7 may read, or None when one of its refusals names the row (the
    loan, proceeds, advance and refund words, the channel gate, the strong non-revenue rule and D1's descriptors,
    transfer wording, a hold's wording, a lender outside vehicle financing, a potential lender, an insurer)."""
    classifier = _classifier()
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
    known = match_known_payee(text, credit=True)
    if known is not None and known.state in FINANCING_STATES and known.state != "vehicle_financing":
        return None
    if registry_match(text, classifier.POTENTIAL_LENDER_ALIASES) is not None:
        return None
    # Final review M9: the insurer is read as step 5 reads it, on the lookup text (a glued HCCLAIMPMT split from the
    # name before it, _split_glued_claim).
    if classifier._insurance_registry_match(classifier._split_glued_claim(text), glued_digits=True) is not None:
        return None
    return region


def credit_union_dealer_entry(text: str) -> DealerFunding | None:
    """§8.7 (audit B7: I36): a credit union's other dealer-funding entry, read on a credit's revenue text: a credit union
    named on the payer region (_CREDIT_UNION_PAYER, no listed auto lender) prints a dealer-funding word other than the
    VHCL PURCH entry ('VADMIN FEE', the same deal's admin fee), and none of Q7's refusals names the row
    (_dealer_funding_region). Arm 'credit_union_entry', with the credit union as its payer region prints it; or None.
    The statement pass verifies it beside the same credit union's verified VHCL PURCH credits, or one that prints its
    deal ID (_DEAL_ID)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    word = DEALER_FUNDING_WORDS.search(row)
    if word is None or _VEHICLE_PURCHASE_ENTRY.search(classifier.entry_fields(text) or row):
        return None
    words = classifier._without_receiver_value(text)
    region = _dealer_funding_region(text, row, words)
    if region is None or not _CREDIT_UNION_PAYER.search(region) or _listed_auto_lender(words) is not None:
        return None
    return DealerFunding("credit_union_entry", classifier.payer_name(region) or region, region, word.group(0))


def _dealer_word_lender(text: str, region: str) -> bool:
    """§8.1, §8.7 (audit B7: I36): the dealer-word hold reads every row but a wire whose purpose alone prints the word
    and whose sender is a named non-lender ('B/O <person> ... OBI VEHICLE PURCHASE', a customer's own wire to the
    dealer): Q5 reads that wire. A wire is still held when it names no sender, when the sender's own name prints the
    word, or when the sender reads as a lender, a credit union or a bank: a financing root, a floor-plan lender's name
    (B7 review round 1; round 2, _FLOOR_PLAN_LENDER_NAME: a floor-plan form, or WHOLESALE beside a lender's or a
    vehicle trade's whole word, audit round 2, R2-B13: R39, never a flooring contractor, a wholesale grocer or a
    customer's FINE, CAPE or AUTOMATION), a credit union's or a bank's, title or
    escrow firm's form, a financing payee of the registry or a potential lender. An ACH or EFT entry printing the word
    from an unlisted originator stays held ('<NAME> AUTO DES:DEALER PAY': an auto lender the registry does not
    list)."""
    classifier = _classifier()
    if not region or _channel(text) != "wire" or DEALER_FUNDING_WORDS.search(region):
        return True
    if (
        _CREDIT_UNION_PAYER.search(region) or _BANK_OR_TITLE_SENDER.search(region) or _FINANCING_ROOT.search(region)
        or _FLOOR_PLAN_LENDER_NAME.search(region)
    ):
        return True
    known = match_known_payee(classifier._without_receiver_value(text), credit=True)
    if known is not None and known.state in FINANCING_STATES:
        return True
    return registry_match(region, classifier.POTENTIAL_LENDER_ALIASES) is not None


def _payables_only_dealer_funding(text: str) -> bool:
    """Owner ruling 2026-10-02 (the underwriter's Q9, part (c'); §8.7): a listed auto lender's credit Q7 reads on a
    payables word alone (PAYABLES, TRADE PAY..., ACCT FUND...): dealer_funding_reading's listed arm, whose word is no
    dealer-specific funding word (it reads one first), on a credit's revenue text."""
    reading = dealer_funding_reading(text)
    return reading is not None and reading.arm == "listed" and _DEALER_PAYABLES_WORDS.fullmatch(reading.word) is not None


def _dealer_activity(
    records: Sequence[TransactionClassification], duplicate_indexes: set[int], indexes: Sequence[int],
) -> bool:
    """Owner ruling 2026-10-02 (the underwriter's Q9 (c'); §8.7): the statement's dealer activity, the shared core of
    the dealer evidence (R2-OW05; R2-OW06's Q11 reads it too). True when one of the statement's credits (`indexes`,
    the pass's posted, non-duplicate credits) is a credit union's VHCL PURCH (method credit_union_vehicle_purchase) or a
    Q7 credit that is not payables-only (a dealer-specific word, or the credit-union arm); or when a posted,
    non-duplicate row, credit or debit, is a floor-plan financier's (classification floor_plan_financing, the
    registry's FLOOR_PLAN_ALIASES, or a FLOOR PLAN form); or when a posted, non-duplicate debit is a purchase at a
    dealer-only wholesale auction (_WHOLESALE_AUCTION_DEBIT_NAMES). A listed auto lender's payables-only credit is no
    dealer evidence: a repossession agency's own payables would make its statement a dealer's (the Q9 card); nor is a
    §7.8 auction payout credit (R2-OW06 adds it for Q11 only).

    Audit round 3, R3-B14 (R3-52; Q9 (c), "a lender paying a business for services counts as 'lender paid for
    services', never verified. The hidden-loan guard stays"): the auction arm reads a debit that is no card purchase
    (_card_purchase_debit: classification pos, or the card forms classifier._CARD_FORM_DEBIT_PREFIX and
    _CARD_FORM_DEBIT), so a purchase in Manheim, PA is no auction purchase, while an ACH, wire or check debit to the
    auction still is; the floor-plan form reads FLOORPLAN(S) and FLOOR PLANNING only (_FLOOR_PLAN_FORM: never
    FLOORPLANNER or FLOOR PLANKS); and a floor-plan financier's posted credit (any of the three arms) is evidence only
    where it prints no service wording (_FLOOR_PLAN_SERVICE_CREDIT, read without the receiver field's value: a vendor
    payment, a repossession, a recovery, a tow, a transport, an inspection, a commission). Debits are read as before.
    Q11 (b)'s _dealer_statement reads the same arms. Review round 1 (findings 4 to 6): the service wording is read
    without the holder's names too (without_receiver_and_holder), so a dealer advance whose unlabelled receiver is the
    holder's own name printing RECOVERY, TRANSPORT or COMMISSIONS stays evidence; a card form's '<ST> USA|CAN' tail on a
    wire, ACH or check row is no card purchase (_card_purchase_debit); and the floor-plan form reads its glued words
    (FLOORPLANINT, FLOORPLANPAYOFF, FLOORPLANADV, FLOORPLANXPRESS)."""
    classifier = _classifier()
    for index in indexes:
        record = records[index]
        if record.revenue_match_method == "credit_union_vehicle_purchase":
            return True
        if record.revenue_match_method == "auto_lender_dealer_funding" and not _payables_only_dealer_funding(
            classifier.revenue_text(record.normalized_description)
        ):
            return True
    for index, record in enumerate(records):
        if index in duplicate_indexes or not record.is_posted:
            continue
        text = classifier.revenue_text(record.normalized_description)
        if (
            record.classification == "floor_plan_financing" or registry_match(text, FLOOR_PLAN_ALIASES) is not None
            or _FLOOR_PLAN_FORM.search(text)
        ) and (
            record.amount < 0
            or _FLOOR_PLAN_SERVICE_CREDIT.search(
                without_receiver_and_holder(text, record.account_name, record.holder_name)
            ) is None
        ):
            return True
        if (
            record.amount < 0 and not _card_purchase_debit(record, text)
            and any(pattern.search(text) for pattern in _WHOLESALE_AUCTION_DEBIT_NAMES)
        ):
            return True
    return False


def _card_purchase_debit(record: TransactionClassification, text: str) -> bool:
    """Audit round 3, R3-B14 (R3-52): a debit that is a card purchase, as R2-B02 (R01) reads one: the classifier's
    class `pos`, or a card form on its revenue text (classifier._CARD_FORM_DEBIT_PREFIX: CHECKCARD or PURCHASE <mmdd>;
    _CARD_FORM_DEBIT: DEBIT CARD PURCHASE, DBCRD PUR, POS DB|DEBIT|PUR, POINT OF SALE, a glued PURCHASE<digits>, a
    charge ending in a state or province code and its country). Review round 1 (finding 5): that tail, Found's and
    Bluevine's card-charge form, is no card purchase on a row that prints a wire, ACH or check form
    (_NON_CARD_DEBIT_FORM: 'OUTGOING WIRE <auction> ATLANTA GA USA', 'ACH DEBIT <auction> ... GA USA')."""
    classifier = _classifier()
    stripped = text.strip()
    if record.classification == "pos" or classifier._CARD_FORM_DEBIT_PREFIX.search(stripped) is not None:
        return True
    card = _CARD_FORM_DEBIT.search(stripped)
    if card is None:
        return False
    return _CARD_FORM_TAIL.fullmatch(card.group(0)) is None or _NON_CARD_DEBIT_FORM.search(stripped) is None


def _dealer_contract_evidence(
    records: Sequence[TransactionClassification], duplicate_indexes: set[int], indexes: Sequence[int],
) -> bool:
    """Owner ruling 2026-10-02 (the underwriter's Q9 (c'); §8.7): the statement shows dealer evidence, which a listed
    auto lender's payables-only credit needs to stay verified as dealer funding: the statement's dealer activity
    (_dealer_activity), or a dealer's name on one of the holder's names (the first credit's _holder_names, its
    account name and its holder name, each read through account_name_text) that prints no recovery, repossession,
    towing or collateral word (_DEALER_HOLDER_NAME, _DEALER_HOLDER_VETO)."""
    if _dealer_activity(records, duplicate_indexes, indexes):
        return True
    if not indexes:
        return False
    classifier = _classifier()
    first = records[indexes[0]]
    names = (*_holder_names(first), first.account_name, first.holder_name)
    for name in names:
        printed = classifier.account_name_text(name) if name else ""
        if printed and _DEALER_HOLDER_NAME.search(printed) and not _DEALER_HOLDER_VETO.search(printed):
            return True
    return False


#: Audit B4 (I02; standard A5): the bank's own fee for an incoming wire or funds transfer, which reprints the sender's
#: name (RBC's 'FUNDS TRANSFER FEE TT <sender>', 'WIRE TRANSFER FEE [FROM] <sender>', '[DOMESTIC] INCOMING WIRE FEE',
#: 'WIRE FEE'): never circular money, so it never holds the wire (_COUNTER_DEBIT_KINDS).
_RECEIVING_FEE_DEBIT = re.compile(
    r"(?<![A-Z])(?:FUNDS TRANSFER|WIRE(?: TRANSFER| TRANS| TFR| IN)?) (?:FEES?|CHG|CHARGE|SVC CHARGE)\b"
    r"|(?<![A-Z])INCOMING (?:FUNDS TRANSFER |WIRE (?:TRANSFER )?)?(?:FEES?|CHG|CHARGE)\b"
)
#: Audit B4 (I02): the fee for the holder's own outgoing wire names its beneficiary: it still holds the payer (the
#: holder sent that payer money).
_OUTGOING_WIRE_FEE = re.compile(r"(?<![A-Z])(?:OUTGOING|OUT|TO|BNF|BENEFICIARY)\b")
#: Audit round 2, R2-B02 (R48 part 1): the receiving fee prints the sender it reprints after TT or FROM ('FUNDS TRANSFER
#: FEE TT <sender>', 'WIRE TRANSFER FEE FROM <sender>'): the outgoing words are read before it, never inside the
#: sender's name ('CONTOSO TO GO INC'). Review round 1: FROM before the holder's own account (an account word or a
#: masked account number: 'WIRE TRANSFER FEE FROM CHECKING TO <payee>') or before TO is the wire's source, never a
#: sender, so the words after it are the fee's own.
#: Audit round 3, R3-B16 (R3-33): the holder's own account is also an account product's name (up to two product words,
#: BUSINESS, BUS, OPERATING, PAYROLL, PRIMARY, COMMERCIAL, ANALYZED, ANALYSIS or PERSONAL, before an account word:
#: 'FROM BUSINESS CHECKING TO <payee>', 'FROM BUS CHK'), MONEY MARKET, OPERATING alone (the holder's operating
#: account) or a digit run of three or more (the account number a bank prints after '*' or '...'); every other word
#: after FROM still starts a sender ('FROM CONTOSO TO GO INC', 'FROM OPERATING ENGINEERS LOCAL ...'), so the lookahead
#: is widened only, never every FROM ... TO read as the source (which would re-open R48's sender named with TO).
_FEE_SOURCE_ACCOUNT = (
    r"(?:(?:BUSINESS|BUS|OPERATING|PAYROLL|PRIMARY|COMMERCIAL|ANALYZED|ANALYSIS|PERSONAL) ){0,2}"
    r"(?:CHECKING|CHKG|CHK|CKG|SAVINGS|SAV|SVGS|ACCOUNT|ACCT|DDA|MMA)"
    r"|MONEY MARKET"
)
_FEE_SENDER_RUN = re.compile(
    r"(?<![A-Z])(?:TT|FROM)\b"
    rf"(?! (?:TO|OPERATING|{_FEE_SOURCE_ACCOUNT})\b| X{{2,}}\d*\b| \d{{3,}}\b)"
)
#: Review round 1: the outgoing words no sender's name prints, read after the sender too ('... TT <sender> BNF <payee>').
_OUTGOING_WIRE_FEE_AFTER_SENDER = re.compile(r"(?<![A-Z])(?:OUTGOING|BNF|BENEFICIARY)\b")
#: Audit B4 (I02; standard A1, A2, §4.2): a processor's own debit beside its settlements: its fee, discount,
#: chargeback, adjustment or returns. A monthly-discount processor posts one such debit a month.
_PROCESSOR_FEE_DEBIT = re.compile(
    r"(?<![A-Z])(?:FEES?|DISCOUNT|DISC|CHBK|CHGBK|CHRGBACK|CHARGEBACKS?|CHG BACK|ADJ|ADJUSTMENTS?|RETURNS?)\b"
)
#: Audit round 3, R3-B16 (R3-35; standard A1, A2, §4.2; §20 B4 review round 1): a processor's fee word glued after
#: another word at the end of the entry that Chase's SEC code follows, once _counter_debit_kind_text splits the code off
#: ('MONTHLYFEE SEC CCD', 'PAYCORFEES SEC CCD', 'SERVICEFEE SEC WEB'), never COFFEE.
_GLUED_FEE_ENTRY = re.compile(
    r"(?<![A-Z])[A-Z]{3,}?(?<!COF)(?:FEES?|DISCOUNT|DISC|CHARGEBACKS?|CHGBK|CHBK)"
    r"(?= SEC (?:CCD|CTX|PPD|WEB|IAT|COR|TEL|POP|BOC|ARC|RCK|CIE)\b)"
)
#: Audit B4 (I02): a credit printing settlement, payout, MID or merchant-services wording is a processor's
#: settlement, which its own fee debits never hold.
_SETTLEMENT_CREDIT = re.compile(
    r"(?<![A-Z])(?:SETTLE\w*|SETTLMT|SETLMT|STLMT|STLMNT|PAYOUTS?|MERCHANT SERVI\w*)\b|(?<![A-Z])MID(?=\d|\b)"
)
#: Audit round 2, R2-B02 (R01; standard A1, §4.2): a processor's or a platform's payout forms the settlement words miss,
#: read before the receiver fields as they are: a merchant-services deposit glued or cut (RBC's MRCHNTSVCS, MRCH SVCS),
#: a combined deposit (COMB DEP), Payment Brands' originator in its printed cuts (PAYMNTBRAND, PYMNTBRDMIN: a card
#: payment facilitator, a registered ISO of Fifth Third Bank, whose settlement account takes its card sales and pays
#: its refunds, chargebacks and processing fees), QuickBooks Payments in Canada (INTUIT CANADA PAYMENTS and its cut
#: INTUIT CANADA P, never its PAYROLL), a bank's merchant deposit ('DEPOSIT <bank> MERCHANT ...') and a platform's
#: twelve-character payout id of letters and digits after ST (Stripe's 'ST-<id>').
_PAYOUT_FORMS = re.compile(
    r"(?<![A-Z])(?:MRCHNT ?SVCS?|MRCH SVCS?|COMB(?:INED)? DEP(?:OSIT)?|PA?YM?NTBR(?:A?NDS?|D)\w*"
    r"|INTUIT CANADA P(?:AYMENTS)?)\b"
    r"|^DEPOSIT [A-Z]+ MERCHANT\b"
    r"|(?<![A-Z0-9])ST (?=[A-Z0-9]{12}(?![A-Z0-9]))(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{12}(?![A-Z0-9])"
)
#: Audit round 2, R2-B02 (R01): a processor's merchant-ID field, read anywhere on the row: Chase and Truist print it
#: after the receiver ('IND NAME:<merchant> MID:<digits>-<processor>').
_MERCHANT_ID_FIELD = re.compile(r"(?<![A-Z])MID \d{6,}\b")
#: Audit round 2, R2-B02 (R01; standard A1): a card purchase printed in a form the card-form prefix
#: (classifier._CARD_FORM_DEBIT_PREFIX: CHECKCARD or PURCHASE <mmdd>) misses: Truist's DEBIT CARD PURCHASE, DBCRD PUR,
#: Woodforest's POS DB, POS DEBIT or POS PURCHASE, POINT OF SALE, CIBC's glued PURCHASE<digits>, or a charge ending in a
#: state or province code and its country (Found's and Bluevine's '<merchant> <city> <ST> USA|CAN').
_CARD_FORM_DEBIT = re.compile(
    r"^(?:DEBIT CARD PURCHASE|DBCRD PUR|POS (?:DB|DEBIT|PUR)|POINT OF SALE|PURCHASE\d{4,})"
    r"|(?<![A-Z])[A-Z]{2} (?:USA|CAN)$"
)
#: Audit round 3, R3-B14 review round 1 (finding 5): _CARD_FORM_DEBIT's tail arm, the '<ST> USA|CAN' ending, which a
#: wire, ACH or check debit printing its beneficiary's state and country prints too (_NON_CARD_DEBIT_FORM); read by
#: _card_purchase_debit alone (the counter-debit reader keeps _CARD_FORM_DEBIT whole).
_CARD_FORM_TAIL = re.compile(r"(?<![A-Z])[A-Z]{2} (?:USA|CAN)$")
_NON_CARD_DEBIT_FORM = re.compile(r"(?<![A-Z])(?:WIRE|ACH|CHECK|CHK|CHEQUE)\b")
#: Audit round 2, R2-B02 (R02; standard A6): an ATM, ABM or cash withdrawal: the holder taking cash out names a place,
#: never a payer, so it never holds a deposit (a transfer made at an ATM stays circular money).
_CASH_WITHDRAWAL_DEBIT = re.compile(
    r"(?<![A-Z])(?:ATM|ABM)\b|(?<![A-Z])CASH (?:WITHDRAWAL|WITHDRWL|WDL|WD)\b|(?<![A-Z])WITHDRAWAL CASH\b"
)
#: R2-B02 review round 1: a company whose name leads with ATM or ABM (a legal form within its next two words; never
#: CO, a state's code after an ATM's town), or an ACH entry printing one (Bank of America's DES ... ID field, Chase's
#: ORIG CO NAME and CO ENTRY DESCR, a receiver or company id field), is a payee the holder pays, never a cash withdrawal.
#: Audit round 3, R3-B16 (R3-34; standard A6; R2-B02 R02: an ATM withdrawal names a place, never a payer): none of
#: those two words is a cash or posting word (WITHDRAWAL, WITHDRAW, WITHDRWL, WTHDRWL, WDL, WD, DEBIT, CASH, FEE,
#: PURCHASE, TRANSACTION, TXN), so 'ATM WITHDRAWAL <name> INC' and 'ATM DEBIT <name> LLC' stay cash withdrawals.
_ATM_NAMED_COMPANY = re.compile(
    r"(?<![A-Z])(?:ATM|ABM)"
    r"(?: (?!(?:WITHDRAWALS?|WITHDRAW|WITHDRWL|WTHDRWL|WDL|WD|DEBIT|CASH|FEE|PURCHASE|TRANSACTION|TXN)\b)[A-Z&]+){0,2}"
    r" (?:INC|LLC|CORP|CORPORATION|LTD|LIMITED|COMPANY|INDUSTRIES|GROUP)\b"
)
_ACH_ENTRY_LABEL = re.compile(
    r"(?<![A-Z])(?:INDN|IND NAME|ORIG CO NAME|CO ENTRY DESCR|CO ID|DES(?: [A-Z0-9]+){1,4} ID)\b"
)
#: Audit round 2, R2-B02 (R02; §5.2, S23): a wallet's cash-out names no sender (Venmo, Cash App, Square Cash, Apple
#: Cash): a counter-debit reading that leads with the wallet's name reads nothing.
_WALLET_CASH_OUT = re.compile(r"^(?:VENMO|CASH ?APP|SQUARE CASH|APPLE CASH)\b")
#: Audit round 2, R2-B02 (R02): the e-Transfer rails, whose sender RBC and TD print without FROM (e-Transfer received
#: <sender>, AUTODEPOSIT <sender>, VIREMENT RECU <sender>): the counter-debit holds read that sender (_counter_region).
#: Audit round 3, R3-29: and Interac's French form, plural included (Banque Royale's 'DEPOT AUTO VIREMENTS PAR
#: COURRIEL <sender>', _INTERAC_COURRIEL).
_E_TRANSFER_RAIL = re.compile(
    r"(?<![A-Z])(?:INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|AUTODEPOSIT|VIREMENT|VIREMENTS? PAR COURRIEL)\b"
)
#: Audit round 2, R2-B02 (R02; T13): RBC's French 'Paiement divers' label before the holder's own chequing or savings
#: account and its number: the holder's own account, held as transfer_account_designation.
_FRENCH_OWN_ACCOUNT_PAYMENT = re.compile(r"^PAIEMENT DIVERS COMPTE (?:CHEQUE|EPARGNE) \d+")
#: R2-B02 review round 1 (T13): a credit 'FR' (from) an account designation, printed with no transfer word (Bank of
#: America's banking-centre 'BKOFAMERICA BC <date> <ref> FR SAV' or 'FR CHKG'): it names an account, never a payer,
#: and is held as transfer_account_designation whatever debits the statement prints.
_FROM_ACCOUNT_ABBREVIATION = re.compile(
    r"(?<![A-Z])FR (?:SAV|SAVINGS|SVGS|CHKG|CHK|CKG|CHECKING|DDA|MMA)\b"
)
#: Audit B4 (I02): a bill the holder pays: bill pay, an electronic bill (EBPP), autopay, a utility, a telecom, cable or
#: wireless service, a subscription.
_BILL_DEBIT = re.compile(
    r"(?<![A-Z])(?:BILL ?PAY(?:MENTS?|MT|MNT)?|BILL PAID|BILL PMT|EBPP|AUTOPAY\w*|AUTO PAY|UTILIT\w*|UTIL"
    r"|TELECOM\w*|WIRELESS|CABLE|VOIP|SUBSCRIPTIONS?|SUBSCR)\b"
)
#: Audit B4 (I02; Q6): a payer that reads as an insurer keeps the bill exclusion off: an insurer's credit beside the
#: holder's premium or bill to it stays held (insurers never count).
_INSURER_CREDIT = re.compile(r"(?<![A-Z])(?:INS|INSUR\w*|ASSUR\w*)\b")
#: Audit round 3, R3-B16 (R3-03; owner ruling 2026-10-02, the underwriter's Q2; standard A11, B6): a premium, or the
#: bank's retry of a returned premium (a re-presentment of the same obligation, never a second one), read on a
#: non-lender debit's kind text with Chase's glued SEC code split off ('INS PREMSEC PPD' reads 'INS PREM SEC PPD'): the
#: flag that lets a debit naming a credit the Q2 release counted recur at one amount without holding it
#: (also_debited). A flag, never a kind: the debit keeps its kind.
_PREMIUM_DEBIT = re.compile(r"(?<![A-Z])(?:PREM|PREMS|PREMIUMS?|PREMSEC|RETRY)(?![A-Z])")
#: Audit B4 (guard): a transfer, wire or person-to-person debit, or an own-account move ('TO CHKG', 'DDA TO DDA'):
#: it can be circular money, so it also matches a payer as 5.6 read it (CounterDebitReading.legacy).
_OWN_ACCOUNT_DEBIT = re.compile(
    r"(?<![A-Z])(?:FR|FROM|TO) (?:CHKG|CHK|CHECKING|SAV|SAVINGS|SHARES?|DDA)\b|(?<![A-Z])ZEL\b"
)
#: Audit B4 (I22): payer_debited_as_lender compares a cut or glued funder name by prefix, five letters or more ...
_PREFIX_MIN_LETTERS = 5
#: ... when the longer word runs on into a financing root ('CONTOSOFUNDING' after 'CONTOSO') or into the shorter side's
#: next word ('FABRIKAMVENTUREHO' after 'FABRIKAM VENTURE'), never into anything else (a customer named like a funder:
#: 'FABRIK EVENTS' against 'FABRIKAM').
_FINANCING_REMAINDER = re.compile(r"^(?:FUND|FIN|CAP|LEND|LOAN|ADV|CRED|MCA)")
#: Audit B4 (I56): a payroll provider's tax-service credit (ADP TAX, PAYCHEX TPS TAX[ES], GUSTO TAX, INTUIT TAX), read
#: with its tax word on the payer region and the entry fields (B4 review round 1, payroll_tax_credit): the holder's
#: own tax impound coming back, never a sale.
_PAYROLL_PROVIDER_WORD = re.compile(r"(?<![A-Z])(?:ADP|PAYCHEX|GUSTO|INTUIT)\b")
_PAYROLL_TAX_WORD = re.compile(r"(?<![A-Z])TAX(?:ES)?\b")


@dataclass(frozen=True)
class _CounterDebit:
    """Audit B4: one posted debit as the counter-debit holds read it: its reading, its kind (lender, receiving_fee,
    circular, processor_fee, bill or other), its amount in cents, the registry lender it names (a lender debit) and
    whether another debit of the payer's word posts the same amount (recurring). Audit round 2, R2-B02 (R18): `payout`,
    the debit prints a platform's payout id (processor_payout: the platform's own pull under the merchant's
    descriptor); (R02) `person_key`, on a person-to-person or push debit whose recipient prints a name of two words or
    more, that name's first two words glued (the only key a credit matches it by, a debit for the credit's own amount
    aside); (R01, review round 1) `card`, a card purchase in a form the card-form prefix misses, which keeps its own
    kind (a fee, a bill or another debit): the card form only lifts a payout's hold (also_debited). A lender debit's
    reading keeps the place words (classifier._without_not_a_payer). Audit round 3, R3-B16 (R3-03): `premium`, a
    non-lender debit printing a premium or a retry of one (_PREMIUM_DEBIT, on its kind text with Chase's glued SEC code
    split off); a lender debit's is always False."""

    reading: CounterDebitReading
    kind: str
    cents: int
    entity: str | None
    recurring: bool
    payout: bool = False
    person_key: str | None = None
    card: bool = False
    premium: bool = False


@dataclass(frozen=True)
class CounterDebits:
    """Audit B4: the statement's posted debits that may hold a payer: the lender and financing debits, the others."""

    lender: tuple[_CounterDebit, ...]
    other: tuple[_CounterDebit, ...]


@dataclass(frozen=True)
class CounterCredit:
    """Audit B4: one posted credit as the counter-debit holds read it. Audit round 2, R2-B02: `payout`, the credit
    prints a platform's payout id (R18, processor_payout); `person_key`, on a person-to-person or push credit whose
    sender prints a name of two words or more and no company form, that name's first two words glued (R02; review
    round 1: a company's push is compared by the B4 forms as before); `lender_reading`, the reading the lender hold
    compares (the place words kept; None: `reading`). Audit round 3, R3-B16 (R3-03): `released_insurer`, the credit
    the Q2 release counted as an insurer paying for the business's work (INSURER_FOR_WORK_METHOD)."""

    reading: CounterDebitReading
    cents: int
    entity: str | None
    settlement: bool
    insurer: bool
    payout: bool = False
    person_key: str | None = None
    lender_reading: CounterDebitReading | None = None
    released_insurer: bool = False


def _cents(amount: float) -> int:
    return round(abs(amount) * 100)


def _lender_entity(text: str, *, credit: bool = False) -> str | None:
    """Audit B4 (I22): the registry lender or financing entity a text names (its glued digit runs split off). Audit B6
    (I22): a credit's (`credit`) is read with the credit index, as the classifier reads the credit."""
    known = match_known_payee(_classifier()._split_glued_digits(text), credit=credit)
    return known.entity if known is not None and known.state in LENDER_DEBIT_STATES else None


def _counter_debit_kind(text: str) -> str:
    """Audit B4 (I02): a posted non-lender debit's kind. The bank's receiving fee first (it prints transfer or wire
    wording, never circular money), then a transfer, wire, person-to-person or own-account debit (circular), a
    processor's fee, a bill, or another debit (an ACH payment, a purchase...).

    B4 review round 1 (finding 1): read without the receiver fields' values (§5.2: INDN, IND NAME, RECEIVER NAME, RECV
    NAME, IND ID print the holder's own name), as _lender_entity reads a lender debit, every field after them kept (an
    addenda's PMT INFO): a holder named for a bill or fee word ('<NAME> CABLE LLC', '<NAME> RETURNS LLC') never turns
    an affiliate's or a collector's debit into a bill or a processor's fee.

    Audit B8 (I46): read without the statement furniture a parser glued onto the debit
    (classifier.without_statement_furniture), so a footer's words (TD's back panel prints 'ELECTRONIC FUNDS
    TRANSFERS') never make a fee or a bill circular money.

    Audit round 2, R2-B02 (R48 part 1): the receiving fee's outgoing words (_OUTGOING_WIRE_FEE) are read on its label
    and the words after it up to the sender it reprints after TT or FROM (_FEE_SENDER_RUN), never inside that sender's
    name ('FUNDS TRANSFER FEE TT CONTOSO TO G' is the bank's fee for a wire from CONTOSO TO GO INC). A fee whose own
    words name an outgoing wire falls through to the kinds after it, as before. Review round 1: FROM before the
    holder's own account or before TO starts no sender ('WIRE TRANSFER FEE FROM CHECKING TO <payee>' is the fee for
    the holder's own wire), and OUTGOING, BNF and BENEFICIARY, which no sender's name prints, are read after the
    sender too.

    Audit round 3, R3-B16 (R3-35; standard A1, A2, §4.2; §20 B4 review round 1): the processor's fee and the bill are
    read on the kind text with Chase's glued SEC code split off (_counter_debit_kind_text: 'CO ENTRY DESCR FEESSEC
    CCD' reads 'FEES SEC CCD', 'BILL PAYMTSEC' reads 'BILL PAYMT SEC'), and a fee word glued after another word at the
    entry's end is the processor's fee too (_GLUED_FEE_ENTRY: 'MONTHLYFEESEC', never 'COFFEESEC'); the receiving fee
    and circular money keep reading the row as printed (a glued 'TRANSFERSEC' keeps its kind). The kind order is
    unchanged. R3-33: FROM before an account product's name, MONEY MARKET, OPERATING or an account number starts no
    sender either (_FEE_SOURCE_ACCOUNT: 'WIRE TRANSFER FEE FROM BUSINESS CHECKING TO <payee>' is circular)."""
    return _counter_debit_kind_of(*_counter_debit_kind_text(text))


def _counter_debit_kind_text(text: str) -> tuple[str, str]:
    """Audit round 3, R3-B16 (R3-35): a non-lender debit's kind text, read without the receiver fields' values and the
    statement furniture (as _counter_debit_kind has read it since B4 review round 1 and B8), and the same text with
    Chase's glued SEC code split off (classifier._GLUED_SEC_CODE, which classifier.revenue_text applies to credits
    only): (text, split)."""
    classifier = _classifier()
    text = classifier.without_statement_furniture(classifier._without_receiver_value(text))
    return text, classifier._GLUED_SEC_CODE.sub(r"\1 SEC \2", text)


def _counter_debit_kind_of(text: str, split: str) -> str:
    """Audit B4 (I02): the kind of a debit's kind text and its split (_counter_debit_kind_text), in the order
    _counter_debit_kind gives: the receiving fee and circular money on `text`, the processor's fee and the bill on
    `split` (audit round 3, R3-B16: R3-35)."""
    classifier = _classifier()
    fee = _RECEIVING_FEE_DEBIT.search(text)
    if fee is not None:
        tail = text[fee.end():]
        sender = _FEE_SENDER_RUN.search(tail)
        own = tail if sender is None else tail[:sender.start()]
        if not (
            _OUTGOING_WIRE_FEE.search(f"{text[:fee.end()]} {own}")
            or (sender is not None and _OUTGOING_WIRE_FEE_AFTER_SENDER.search(tail[sender.start():]))
        ):
            return "receiving_fee"
    if (
        classifier._TRANSFER_WORDING.search(text) or classifier._WIRE_WORD.search(text)
        or classifier._CONSUMER_P2P_RAIL.search(text) or classifier._PUSH_RAIL.search(text)
        or _OWN_ACCOUNT_DEBIT.search(text)
    ):
        return "circular"
    if _PROCESSOR_FEE_DEBIT.search(split) or _GLUED_FEE_ENTRY.search(split):
        return "processor_fee"
    if _BILL_DEBIT.search(split):
        return "bill"
    return "other"


def counter_debits(records: Sequence[TransactionClassification], duplicates: set[int]) -> CounterDebits:
    """Audit B4 (§8.1, amends the 5.6 reading of pass 6 and pass 7): the statement's posted debits that may hold a
    payer, with their counter-debit readings (CounterDebitReading). A card purchase the classifier names as no lender
    or financing payee is left out (A1 census: buying at a merchant that shares the payer's word is spending, never
    circular money); a card-form debit it names as a lender (D8) is still a lender debit.

    Audit round 2, R2-B02: a card purchase in another bank's form, or one the classifier classes 'pos', that the
    card-form prefix misses keeps its place among the other debits (and counts for recurrence), marked `card` where it
    reads other, processor_fee or bill, never circular or receiving_fee (R01, _CARD_FORM_DEBIT; review round 1: it
    keeps that kind); an ATM, ABM or cash withdrawal that is no lender's and no circular money is left out (R02,
    _cash_withdrawal: never a company named ATM or ABM, nor an ACH entry); each debit records whether it prints a
    platform's payout id (R18, processor_payout); a lender debit is read with the place words kept, and a
    person-to-person or push debit to a named recipient records its person_key (R02). Audit round 3, R3-B16 (R3-03):
    each non-lender debit, a card-marked one included, records whether it prints a premium or a retry of one
    (_PREMIUM_DEBIT, on its kind text with Chase's glued SEC code split off); a lender debit never does."""
    classifier = _classifier()
    lender: list[_CounterDebit] = []
    other: list[tuple[CounterDebitReading, str, int, bool, str | None, bool, bool]] = []
    for index, record in enumerate(records):
        if index in duplicates or record.amount >= 0 or not record.is_posted:
            continue
        lender_debit = record.classification in LENDER_DEBIT_STATES
        reading, card_purchase = classifier.counter_debit_debit_reading(record, keep_places=lender_debit)
        if reading.legacy is None and not reading.keys:
            continue
        text = record.normalized_description
        payout = processor_payout(text)
        if lender_debit:
            entity = _lender_entity(classifier._without_receiver_value(text))
            lender.append(_CounterDebit(reading, "lender", _cents(record.amount), entity, False, payout))
        elif not card_purchase:
            kind_text, split = _counter_debit_kind_text(text)
            kind = _counter_debit_kind_of(kind_text, split)
            if kind != "circular" and _cash_withdrawal(text):
                continue
            card = kind in _CARD_KIND_FROM and bool(
                record.classification == "pos" or _CARD_FORM_DEBIT.search(text.strip())
            )
            person_key = None
            if (
                (classifier._CONSUMER_P2P_RAIL.search(text) or classifier._PUSH_RAIL.search(text))
                and reading.heads and reading.heads[0][1]
            ):
                person_key = reading.heads[0][0] + reading.heads[0][1][0]
            premium = _PREMIUM_DEBIT.search(split) is not None
            other.append((reading, kind, _cents(record.amount), payout, person_key, card, premium))
    # "Recurring same-amount debits keep holding": two or more debits of one payer word at one amount (a bill's; B4
    # review round 1: never a processor's fee beside its settlement, also_debited).
    amounts = Counter((_head_word(reading), cents) for reading, _, cents, _, _, _, _ in other)
    return CounterDebits(
        tuple(lender),
        tuple(
            _CounterDebit(
                reading, kind, cents, None, amounts[(_head_word(reading), cents)] >= 2, payout, person_key, card,
                premium,
            )
            for reading, kind, cents, payout, person_key, card, premium in other
        ),
    )


#: Audit round 2, R2-B02 (R01): the kinds a card purchase in another bank's form is marked a card charge on (never
#: circular money or the bank's receiving fee).
_CARD_KIND_FROM = frozenset({"other", "processor_fee", "bill"})


def _cash_withdrawal(text: str) -> bool:
    """Audit round 2, R2-B02 (R02; review round 1): an ATM, ABM or cash withdrawal (_CASH_WITHDRAWAL_DEBIT) that names
    no company leading with ATM or ABM and prints no ACH entry field (_ATM_NAMED_COMPANY, _ACH_ENTRY_LABEL). Audit
    round 3, R3-B16 (R3-34): the company's name never reads a cash or posting word between ATM or ABM and its legal
    form, so 'ATM WITHDRAWAL <name> INC' is still a cash withdrawal."""
    return (
        _CASH_WITHDRAWAL_DEBIT.search(text) is not None
        and _ATM_NAMED_COMPANY.search(text) is None and _ACH_ENTRY_LABEL.search(text) is None
    )


def _head_word(reading: CounterDebitReading) -> str | None:
    return reading.heads[0][0] if reading.heads else reading.legacy


def _counter_region(text: str, region: str) -> str:
    """Audit B6 (I49): the payer words the counter-debit reading reads: the payer region without PNC's leading
    INSTPMNTIN label, or, where the payer region is empty, the words after a leading RTP CREDIT label
    (_INSTANT_PAYMENT_LABEL, _RTP_CREDIT_NAME).

    Audit round 2, R2-B02 (R02): where neither prints, on an e-Transfer row (_E_TRANSFER_RAIL), the sender the rail
    prints without FROM (RBC's and TD's e-Transfer, _p2p_sender_readings), so the same person's round trip can be
    matched; and a wallet's name leading the words (_WALLET_CASH_OUT: a Venmo, Cash App, Square Cash or Apple Cash
    cash-out, which names no sender, §5.2) reads nothing."""
    if region:
        found = _INSTANT_PAYMENT_LABEL.sub("", region)
    else:
        row = _classifier()._before_receiver(text)
        named = _RTP_CREDIT_NAME.match(row)
        if named is not None:
            found = named.group(1)
        elif _E_TRANSFER_RAIL.search(row):
            found = _p2p_sender_readings(text)[0]
        else:
            found = ""
    return "" if _WALLET_CASH_OUT.match(found) else found


def _sender_name_key(region: str) -> str | None:
    """Audit round 2, R2-B02 (R02): a person-to-person or push credit's sender as the counter-debit holds match it: the
    first head word of its payer name (classifier._counter_debit_head) glued to the word after it, when the name has
    one. The name ends at its legal form, so the town a payout prints after a company's name is no part of it
    ('<company> INC <town> <ST>' is a one-word name, matched as before)."""
    classifier = _classifier()
    name: list[str] = []
    for word in classifier.payer_name(region).split() if region else ():
        if word in _WIRE_PARTY_LEGAL_FORMS:
            break
        name.append(word)
    head = classifier._counter_debit_head(name)
    return head[0] + head[1][0] if head is not None and head[1] else None


def counter_credit(record: TransactionClassification, text: str, region: str) -> CounterCredit:
    """Audit B4: a posted credit's counter-debit reading, on its payer region, and the facts the debit kinds read.
    Audit B6 (I49): the reading reads past an instant-payment rail label (_counter_region).

    Audit round 2, R2-B02: a processor's payout is its settlement wording or a payout form before the receiver fields,
    or a merchant-ID field anywhere on the row (R01: _SETTLEMENT_CREDIT, _PAYOUT_FORMS, _MERCHANT_ID_FIELD); `payout`
    is a platform's payout id (R18, processor_payout); `person_key` is set on a credit printing a person-to-person or
    push rail whose first head word has a next word (R02: the glued first two words of the sender's name), and (review
    round 1) whose sender prints no company form: a company's push is compared by the B4 forms as before. Owner ruling
    2026-10-02 (the underwriter's Q2): `insurer` is False on a credit pass 7 released as an insurer paying for the
    business's work (INSURER_FOR_WORK_METHOD), so a bill to that insurer holds it only as a bill to any payer does.
    Audit round 3, R3-29: Interac's French form (_INTERAC_COURRIEL, whose plural the classifier's rail never reads) is
    such a rail too, so a French autodeposit's sender names a debit as its English twin's does. Audit round 3, R3-B16
    (R3-03): `released_insurer` is True on that released credit, which also_debited holds by a debit naming its carrier
    only when the debit is circular money, is for its own amount, or recurs at one amount printing no premium or retry
    word."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    # Audit round 2, R2-B11 (R09 part A): TD Canada Trust's e-Transfer code is no sender, so never a counter-debit key.
    words = _counter_region(text, region) if _transfer_code(record) is None else region
    reading = classifier.counter_debit_payer_reading(words)
    person_key = None
    if (
        (
            classifier._CONSUMER_P2P_RAIL.search(row) or classifier._PUSH_RAIL.search(row)
            or _INTERAC_COURRIEL.search(row)
        )
        and not classifier.company_form(classifier.payer_name(words))
    ):
        person_key = _sender_name_key(words)
    return CounterCredit(
        reading=reading,
        cents=_cents(record.amount),
        entity=_lender_entity(region, credit=True) if region else None,
        settlement=(
            _SETTLEMENT_CREDIT.search(row) is not None or _PAYOUT_FORMS.search(row) is not None
            or _MERCHANT_ID_FIELD.search(text) is not None
        ),
        # Owner ruling 2026-10-02 (the underwriter's Q2), on R2-B02's CounterCredit: a credit the insurer-for-work
        # release re-stated is the business's work, no insurer to the bill clause of also_debited.
        insurer=_INSURER_CREDIT.search(row) is not None and record.revenue_match_method != INSURER_FOR_WORK_METHOD,
        payout=processor_payout(text),
        person_key=person_key,
        lender_reading=classifier.counter_debit_payer_reading(words, keep_places=True),
        # Audit round 3, R3-B16 (R3-03): the credit the Q2 release counted as the business's work.
        released_insurer=record.revenue_match_method == INSURER_FOR_WORK_METHOD,
    )


def _same_payer(credit: CounterDebitReading, debit: CounterDebitReading, *, legacy: bool) -> bool:
    """Audit B4: the payer and the debit name one payer: by the B4 forms (I38's glued forms included), or, where 5.6's
    reading still governs (`legacy`), by 5.6's first distinctive word."""
    if legacy and credit.legacy is not None and credit.legacy == debit.legacy:
        return True
    return not credit.keys.isdisjoint(debit.keys)


def _prefix_payer(credit: CounterDebitReading, debit: CounterDebitReading) -> bool:
    """Audit B4 (I22): one side's first word, five letters or more, starts the other's, and the longer word runs on
    into a financing root or into the shorter side's next word (_FINANCING_REMAINDER)."""
    for credit_word, credit_next in credit.heads:
        for debit_word, debit_next in debit.heads:
            if credit_word == debit_word:
                continue
            short, long, following = (
                (credit_word, debit_word, credit_next) if len(credit_word) < len(debit_word)
                else (debit_word, credit_word, debit_next)
            )
            if len(short) < _PREFIX_MIN_LETTERS or not long.startswith(short):
                continue
            rest = long[len(short):]
            if _FINANCING_REMAINDER.match(rest) or (
                following and (rest.startswith(following[0]) or (len(rest) >= 3 and following[0].startswith(rest)))
            ):
                return True
    return False


def debited_as_lender(credit: CounterCredit, debits: CounterDebits, *, prefix: bool) -> bool:
    """§8.1 payer_debited_as_lender (audit B4: I22, I38): a lender or financing debit names the payer. When both name a
    registry entity, they match when it is one entity; 5.6's first-word match still holds either way. Otherwise the
    B4 forms match, and with `prefix` (pass 7, an unverified credit) a cut or glued spelling (_prefix_payer). Audit
    round 2, R2-B02 (R02): both sides are read with the place words kept (a funder may carry a state's name), and a
    person-to-person or push credit from a named person (its person_key) also matches a lender debit printing that
    whole name. Review round 1: the whole name is one more arm, never the only one: the first word, the B4 forms and
    the prefix still read such a credit, since this hold never lets a funder's money into True (a funder printing no
    legal form, pushing by a real-time or Zelle rail and pulling under a glued or one-word name)."""
    reading = credit.lender_reading if credit.lender_reading is not None else credit.reading
    for debit in debits.lender:
        if credit.person_key is not None and credit.person_key in debit.reading.keys:
            return True
        if reading.legacy is not None and reading.legacy == debit.reading.legacy:
            return True
        if credit.entity is not None and debit.entity is not None:
            if credit.entity == debit.entity:
                return True
            continue
        if _same_payer(reading, debit.reading, legacy=False):
            return True
        if prefix and _prefix_payer(reading, debit.reading):
            return True
    return False


def also_debited(credit: CounterCredit, debits: CounterDebits) -> bool:
    """§8.1 payer_also_debited (audit B4: I02, I38, I56): a debit that can be circular money names the payer (an own
    account, an affiliate, a funder that collects).
    - The bank's receiving fee never holds the payer.
    - A transfer, wire, person-to-person or own-account debit matches as 5.6 read it too (the guard: no such match is
      ever lost).
    - Any other debit matches by the B4 forms; one for the credit's own amount matches as 5.6 read it too (the credit
      undoes it).
    - A processor's fee beside a settlement never holds unless the debit is for the credit's own amount; a bill to a
      payer that is no insurer never holds unless the debit is for the credit's own amount or recurs at one amount.
      B4 review round 1 (finding 4; standard §4.2): a processor's fixed monthly or per-batch fee posts at one amount,
      so its recurrence is the processor's shape, never a collector's; a bill recurring at one amount can be a
      collector's draw and keeps holding.

    Audit round 2, R2-B02, in this order: a platform's payout and the platform's own pull, each printing a payout id,
    never hold unless the pull is for the payout's own amount (R18); a person-to-person or push credit from a named
    person matches by its person_key, or by its first word on a debit for its own amount (R02, _names_the_payer);
    after the bill rule, a processor's payout (its settlement wording, payout forms or merchant-ID field) is never held
    by a card charge or by a one-off other debit of the processor's own unless the debit is for its own amount (R01;
    standard A1, §4.2: its fee, subscription or card charge is the processor's shape, never circular money). Review
    round 1: a card charge keeps its own kind, so beside a credit with no payout form a card-form bill reads the bill
    rule and any other card charge holds as its kind does.

    Audit round 3, R3-B16 (R3-03; owner ruling 2026-10-02, the underwriter's Q2; the MCA principle; standard A11, B6),
    after the bill rule: a credit the Q2 release counted as an insurer paying for the business's work
    (CounterCredit.released_insurer) is held by a debit naming its carrier only when that debit is circular money, is
    for the credit's own amount, or recurs at one amount printing no premium or retry word (_CounterDebit.premium). A
    premium the business pays the carrier that pays it for its work is an ordinary expense, never money going round,
    and it recurs at one amount by nature, as a processor's fixed fee does (B4 review round 1), so it never holds the
    credit, recurring or not. An insurer the release did not count keeps B4's hold beside its premium or bill."""
    for debit in debits.other:
        same_amount = debit.cents == credit.cents
        if credit.payout and debit.payout and not same_amount:
            continue
        if debit.kind == "receiving_fee":
            continue
        if not _names_the_payer(
            credit, debit, legacy=debit.kind == "circular" or same_amount, same_amount=same_amount,
        ):
            continue
        if debit.kind == "processor_fee" and credit.settlement and not same_amount:
            continue
        if debit.kind == "bill" and not credit.insurer and not same_amount and not debit.recurring:
            continue
        # Audit round 3, R3-B16 (R3-03): a released insurer's carrier debits.
        if (
            credit.released_insurer and not same_amount and debit.kind != "circular"
            and (debit.premium or not debit.recurring)
        ):
            continue
        if credit.settlement and not same_amount and (
            debit.card or (debit.kind == "other" and not debit.recurring)
        ):
            continue
        return True
    return False


def _payer_collects(credit: CounterCredit, debits: CounterDebits) -> bool:
    """Owner ruling 2026-10-02 (the underwriter's Q9: "The hidden-loan guard stays: a payer that also debits the account
    like a lender stays held"; §8.1, §8.7): the payer also collects from the account. True when a lender or financing
    debit names it (debited_as_lender, with the pass-7 prefix), or any other posted debit names it by the B4 forms, 5.6's
    first distinctive word (legacy) or a cut or glued spelling (_prefix_payer), the bank's receiving fee and a card
    charge (audit round 2, R2-B02 R01's card mark) aside; a card purchase the classifier names is never among the debits
    (counter_debits). Deliberately stricter than also_debited: no bill, processor-fee, settlement or payout-pair
    exemption, and no amount or recurrence test (a documented over-hold of the owner's "collecting loan payments")."""
    if debited_as_lender(credit, debits, prefix=True):
        return True
    for debit in debits.other:
        if debit.kind == "receiving_fee" or debit.card:
            continue
        if _same_payer(credit.reading, debit.reading, legacy=True) or _prefix_payer(credit.reading, debit.reading):
            return True
    return False


def finance_named_release(
    record: TransactionClassification,
    text: str,
    *,
    region: str,
    entry: str,
    debits: CounterDebits,
    lessor: bool = False,
) -> str | None:
    """Owner ruling 2026-10-02 (the underwriter's Q9, "Keep them as true revenue", option 2; §8.1, T4; R2-OW09): the
    reason T4's financing-root hold is lifted with on an unverified credit nothing claimed, or None. Only the root arm
    (financing_named, read by place: _financing_root_places) is lifted; every other financing arm still holds, and a
    released row takes every later hold (_first_hold's `released`).

    None when no root fires, or when the row before its receiver fields (the holder's names removed) prints PROCEEDS or
    a disbursement (_Q9_REFUSAL). (a) and (c): the root fires on the payer's name alone (no entry or row place) and the
    line prints accounts-payable, vendor-payment or invoice wording (_accounts_payable_wording, the holder's names
    removed) or a commission (_SERVICE_COMMISSION, the orchestrator's extension under the underwriter's Q10). Never a
    payer region that names only a bank (R2-B03's _bank_only_payer); on a layout with no entry label (empty entry
    fields: the entry words print inside the payer region) never a payer reading with two or more roots or a root at or
    after the end of its first company form (_labelless_root_refusal): a single root such a layout prints cannot tell a
    name from a purpose and is read as the name. The reason is lender_paid_for_services when the payer's name reads as
    a lender's (_LENDER_NAME_WORD, a label only) or a listed auto lender (DEALER_FUNDING_PAYERS) originates the row, else
    finance_named_customer. (b): the statement's business is in leasing or property (`lessor`, _lessor_business), no
    special payer arm fired, and every place that fired is a rent LEASE alone (_rent_only), a payer place only as a memo
    printed after the payer's first company form with no root before the form's end (_rent_memo_payer): lessor_rent.

    Last, the hidden-loan guard: None when the payer also collects from the account (_payer_collects: any lender or
    other posted debit naming it, the bank's receiving fee and a card charge aside; a documented over-hold)."""
    classifier = _classifier()
    holder = _holder(record)
    also = _holder_strip_names(record)
    places = _financing_root_places(text, region, entry, holder, bank=record.bank, also=also)
    if not places:
        return None
    row = _without_holder_name(classifier._before_receiver(text), holder, also=also)
    if _Q9_REFUSAL.search(row):
        return None
    reason = None
    payer_only = places.payer is not None and places.entry is None and places.row is None
    if payer_only and (
        _accounts_payable_wording(_without_holder_name(text, holder, also=also))
        or _SERVICE_COMMISSION.search(row) is not None
    ):
        if _bank_only_payer(region, entry, record.bank) is not None:
            return None
        if not entry and _labelless_root_refusal(places.payer):
            return None
        lender = _LENDER_NAME_WORD.search(places.payer) is not None or registry_match(
            classifier._originator_segment(classifier._without_receiver_value(text)), DEALER_FUNDING_PAYERS
        ) is not None
        reason = LENDER_PAID_FOR_SERVICES if lender else FINANCE_NAMED_CUSTOMER
    elif lessor and not places.payer_arm and _rent_only_places(places):
        reason = LESSOR_RENT
    if reason is None:
        return None
    if _payer_collects(counter_credit(record, text, region), debits):
        return None
    return reason


def _labelless_root_refusal(payer: str) -> bool:
    """Q9 (a), (c) on a layout with no entry label (R2-OW09): the payer reading prints two or more financing roots, or a
    root at or after the end of its first company form (_Q9_FORM_WORD): a funder's purpose printed inside the region
    ('<NAME> CAPITAL ADVANCE VENDOR PMT', '<NAME> LLC FUNDING PAYABLES'), never released."""
    roots = list(_FINANCING_ROOT.finditer(payer))
    if len(roots) >= 2:
        return True
    form = _Q9_FORM_WORD.search(payer)
    return form is not None and any(root.start() >= form.end() for root in roots)


def _rent_only(words: str) -> bool:
    """Q9 (b): `words` print a rent LEASE (_RENT_LEASE) and no other financing root once it is blanked."""
    return _RENT_LEASE.search(words) is not None and _FINANCING_ROOT.search(_RENT_LEASE.sub(" ", words)) is None


def _rent_memo_payer(payer: str) -> bool:
    """Q9 (b): a payer place that is a rent memo the region swallowed: a first company form (_Q9_FORM_WORD), the words
    after it a rent LEASE alone, and no root before the form's end ('<NAME> LLC LEASE PMT'). A payer named 'LEASE
    HOLDINGS LLC' (LEASE before its form) is no memo."""
    form = _Q9_FORM_WORD.search(payer)
    return (
        form is not None and _rent_only(payer[form.end():]) and _FINANCING_ROOT.search(payer[: form.end()]) is None
    )


def _rent_only_places(places: _RootPlaces) -> bool:
    """Q9 (b): every place that fired is a rent LEASE alone; a payer place only as a rent memo (_rent_memo_payer)."""
    if places.payer is not None and not _rent_memo_payer(places.payer):
        return False
    return all(_rent_only(place) for place in (places.entry, places.row) if place is not None)


def _lessor_business(
    records: Sequence[TransactionClassification],
    duplicate_indexes: set[int],
    credits: Sequence[int],
) -> bool:
    """Owner ruling 2026-10-02 (the underwriter's Q9 (b); §8.1; R2-OW09): the statement's business is in leasing or
    property, which a rent LEASE needs to be released (finance_named_release). True when one of the holder's names (the
    first credit's _holder_names, its account name and its holder name, each read through account_name_text) prints a
    leasing or property trade word (_PROPERTY_TRADE); or a posted credit's revenue entity is a property-management
    platform (OPERATING_REVENUE_SOURCE_TYPES 'property_management_payments'); or two or more distinct payers pay rent:
    posted credits that no duplicate, no non_revenue rule, no card credit and no Zelle deposit (the underwriter's Q3:
    excluded later in the pass) is, printing RENT, RENTS, RENTAL(S) or a rent LEASE on the row before its receiver
    fields, the holder's names removed; a row with a payer region counts under its payer key unless the region names
    the holder (region_names_holder), and a payer-less row counts as its own payer only on a check, cash, branch or ATM
    deposit (a payer-less transfer, person-to-person or wire row never does).

    Audit round 3, R3-B14 (R3-60; the underwriter's Q9 (b), "rent received counts when the business is in leasing or
    property"; §8.1's "a payer-less transfer is never a rent payer"): in the third arm, a row whose payer region gives
    an empty payer key (an account designation: 'ONLINE BANKING TRANSFER FROM CHK <n> ... RENT') is no rent payer, and
    the rent words are read on the row with the payer's own name removed (_rent_payer_name), so a payer named '...
    RENTALS' is no rent payer while a DES entry, a memo after the payer's company form and a wire's REF still read."""
    if not credits:
        return False
    classifier = _classifier()
    first = records[credits[0]]
    for name in (*_holder_names(first), first.account_name, first.holder_name):
        if name and _PROPERTY_TRADE.search(classifier.account_name_text(name)):
            return True
    payers: set[tuple] = set()
    for index in credits:
        record = records[index]
        if index in duplicate_indexes:
            continue
        if OPERATING_REVENUE_SOURCE_TYPES.get(record.revenue_canonical_entity or "") == "property_management_payments":
            return True
        if record.revenue_classification == "non_revenue":
            continue
        text = pass_text(record, classifier.revenue_text(record.normalized_description))
        if _CARD_CREDIT_LABEL.search(text) or zelle_deposit(text):
            continue
        holder, also = _holder(record), _holder_strip_names(record)
        row = classifier._before_receiver(text)
        if not _rent_words(_without_holder_name(row, holder, also=also)):
            continue
        channel = _channel(text, record.bank)
        region = _facts_region(text, channel, record.bank)
        if region and classifier._payer_key(region) == ():
            continue
        name = _rent_payer_name(text, region)
        if name and not _rent_words(_without_holder_name(row.replace(name, " ", 1), holder, also=also)):
            continue
        if region:
            if not region_names_holder(record, text, region):
                payers.add(("payer", classifier._payer_key(region)))
        elif channel in _DEPOSIT_CHANNELS:
            payers.add(("row", index))
    return len(payers) >= 2


def _rent_words(row: str) -> bool:
    """Q9 (b), the lessor's third arm: `row` prints RENT, RENTS, RENTAL(S) (never RENT A CAR) or a rent LEASE."""
    return _RENT_RECEIVED.search(row) is not None or _RENT_LEASE.search(row) is not None


def _rent_payer_name(text: str, region: str) -> str:
    """Audit round 3, R3-B14 (R3-60): the payer's own name, which the lessor's third arm reads no rent word in. On a row
    that prints a payer-name field (_prints_payer_name_field: a wire's sender, an ACH originator, a transfer's sender
    after FROM) the name proper (_payer_name_proper: a wire's or an originator's whole region); on a row that prints
    none, the region up to the end of its first company form (_Q9_FORM_WORD, the _rent_memo_payer convention: '<NAME>
    LLC LEASE PMT' keeps its memo). '' for a payer-less row.

    Review round 1 (finding 3): a row that prints no payer-name field prints the entry description inside the region,
    so only the payer's name proper is removed: the region's leading rent words are the entry description a
    label-less layout prints first (Truist's '<entry> <company field> <receiver> CUSTOMER ID': 'RENT <tenant> LLC'),
    never the name; and with no company form, the name is the region up to a trade noun, RENTALS after a name word or
    RENTAL ending the region after one (_rent_trade_noun_name: 'PAYMENT <NAME> RENTALS', '<NAME> AUTO RENTALS ACH
    PAYMNT'), or none at all, so a tenant's memo after a name with no form ('<tenant> RENT 540301 ...', 'ACH DEPOSIT
    <tenant> RENT', '<tenant> RENTAL PAYMENT', 'RENTAL INCOME <tenant>') still reads."""
    if not region:
        return ""
    if _prints_payer_name_field(text):
        return _payer_name_proper(text, region)
    words = region.split()
    while words and _rent_words(words[0]):
        words = words[1:]
    named = " ".join(words)
    form = _Q9_FORM_WORD.search(named)
    return named[: form.end()] if form is not None else _rent_trade_noun_name(words)


def _rent_trade_noun_name(words: Sequence[str]) -> str:
    """Audit round 3, R3-B14 review round 1 (finding 3): a label-less region with no company form, as `words`, whose
    name is a rental trade: the words up to and including RENTALS after a name word (a word of two letters or more, no
    generic word, no rent word), or RENTAL as the last word after one; '' when it prints neither."""
    classifier = _classifier()
    for at, word in enumerate(words):
        if word not in ("RENTAL", "RENTALS") or (word == "RENTAL" and at != len(words) - 1):
            continue
        if any(
            before.isalpha() and len(before) > 1 and before not in classifier.REVENUE_GENERIC_WORDS
            and not _rent_words(before) for before in words[:at]
        ):
            return " ".join(words[: at + 1])
    return ""


def _names_the_payer(credit: CounterCredit, debit: _CounterDebit, *, legacy: bool, same_amount: bool) -> bool:
    """Audit B4 (_same_payer); audit round 2, R2-B02 (R02): a person-to-person or push credit whose sender prints a name
    of two words or more and no company form names the debit's payer by that whole name (its person_key, the glued
    first two words, in the debit's keys); and a person-to-person or push debit to a recipient printing such a name
    (now that the rail's own word no longer reads as the debit's) is named by a credit only by that whole name (its
    person_key in the credit's keys): a given name, a rail's name or a town alone never does. Review round 1: a debit
    for the credit's own amount that is no such person-to-person debit still names the credit's payer by 5.6's first
    word, as B4 read it (the credit undoes it)."""
    if credit.person_key is not None:
        if (
            same_amount and debit.person_key is None and credit.reading.legacy is not None
            and credit.reading.legacy == debit.reading.legacy
        ):
            return True
        return credit.person_key in debit.reading.keys
    if debit.person_key is not None:
        return debit.person_key in credit.reading.keys
    return _same_payer(credit.reading, debit.reading, legacy=legacy)


def payroll_tax_credit(text: str, region: str) -> bool:
    """§8.1 non_sale_purpose (audit B4: I56): a payroll provider's tax-service credit: _PAYROLL_PROVIDER_WORD on the
    row before its receiver fields, with a TAX or TAXES word. B4 review round 1 (finding 2): the tax word is read on
    the payer region (`region`, payer_region) and the entry fields only, never on the rest of the row, where a layout
    with no receiver label prints the holder's own name ('<PROVIDER> DEPOSIT <ref> <NAME> TAX SERVICES LLC' is the
    provider paying a holder named for taxes); a layout that prints its entry first ('ACH TAXES <ref> PAYCHEX TPS')
    reads it as the payer region."""
    if _PAYROLL_PROVIDER_WORD.search(_classifier()._before_receiver(text)) is None:
        return False
    return _PAYROLL_TAX_WORD.search(f"{region} {_classifier().entry_fields(text)}") is not None


#: §8.2, §8.3 (audit B2: I48): an explicit cash, ATM or check deposit form, which Q2 and Q3 count even when the row
#: also prints transfer wording (Square's 'CASH DEPOSIT TRANSFER IN', 'MOBILE CHECK DEPOSIT TRANSFER'). A teller,
#: branch or counter transfer prints none and stays held (M4: 'TELLER TRANSFER').
_EXPLICIT_DEPOSIT_FORM = re.compile(
    r"(?<![A-Z])CASH DEP(?:OSIT)?\b|(?<![A-Z])ATM\b.*(?<![A-Z])DEP(?:OSIT)?\b|(?<![A-Z])DEP(?:OSIT)?\b.*(?<![A-Z])ATM\b"
    r"|(?<![A-Z])(?:MOBILE|REMOTE)(?: ONLINE)? (?:CHECK |CHEQUE )?(?:DEPOSIT|DEP)\b"
    r"|(?<![A-Z])(?:ATM )?CHE(?:CK|QUE)S? (?:DEPOSIT|DEP)\b"
)
_DEPOSIT_CHANNELS = frozenset({"check", "cash_branch_atm"})


def _channel(text: str, bank: str | None = None) -> str:
    """§5.2: the channel family: wire, ach_eft, person_to_person, check, cash_branch_atm or other. A row the 5.5 wire
    vetoes read as a wire (_wire_vetoes_apply: an incoming-wire label, a third-party book transfer, or WIRE printed
    outside the receiver's value, a glued reference included) is a wire, so Q6 never reads it as an ACH payer.

    A3 (precision sample): a transfer that prints the loose wire words (§8.5: FEDWIRE, WIRE, CHIPS, SWIFT ...) and
    names no counterparty ('INCOMING FEDWIRE TRANSFER') is a wire with no sender (Q5: held as wire_no_sender); one that
    names its counterparty keeps the named-transfer reading (T13).

    Audit B2 (I48): a check, cash, branch or ATM row that prints transfer wording, no explicit deposit form
    (_EXPLICIT_DEPOSIT_FORM) and names its counterparty once its deposit-channel words are removed ('BRANCH TRANSFER
    FROM <company>') is a named transfer (T13); the statement's bank (`bank`) names no counterparty. Audit round 2,
    R2-B09 (R25; M4, Q2): 'names its counterparty' is FROM and a sender, or a company form
    (_deposit_transfer_names_counterparty): a reference and a town printed after a branch's transfer ('BRANCH TRANSFER
    <ref> <town>', the booking branch) name nobody, so the row stays held.

    Audit B5: American Express's incoming-ACH label ('ONLINE TRANSFER PAYMENT CREDIT' at the row's start, I19) is no
    transfer wording and is an electronic-payment form, so its template is ACH; the originator's own entry word
    (TRANSFER) still reads as transfer wording, as Bank of America's 'DES:TRANSFER' does. A TD Canada Trust row that
    ends with an electronic-payment CPA code is ACH too (I37, cpa_payment_code)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    if classifier._is_wire_row(text):
        return "wire"
    if _p2p_rail(row) or classifier._PUSH_RAIL.search(row):
        return "person_to_person"
    deposit = None
    if classifier._CHECK_DEPOSIT_FORM.search(row):
        deposit = "check"
    elif (not classifier._ELECTRONIC_PAYMENT_FORM.search(row) and classifier._CASH_BRANCH_ATM_FORM.search(row)):
        deposit = "cash_branch_atm"
    if deposit is not None:
        if (
            _transfer_wording(row) and _EXPLICIT_DEPOSIT_FORM.search(row) is None
            and _deposit_transfer_names_counterparty(text, bank)
        ):
            return "person_to_person"
        return deposit
    if _transfer_wording(row):
        if _TRANSFER_WIRE_WORDS.search(row) and not _transfer_counterparty_words(text, bank):
            return "wire"
        return "person_to_person"
    if _LOOSE_WIRE.search(row) or classifier._wire_vetoes_apply(text):
        return "wire"
    if classifier._ELECTRONIC_PAYMENT_FORM.search(row) or cpa_payment_code(row, bank):
        return "ach_eft"
    return "other"


def _deposit_transfer_names_counterparty(text: str, bank: str | None = None) -> bool:
    """§8.2, T13 (audit round 2, R2-B09: R25; M4, Q2; amends audit B2's I48 release): a check, cash, branch or ATM row's
    transfer names its counterparty once its deposit-channel words are removed (_without_deposit_channel_words): it
    prints a counterparty word (_transfer_counterparty_words) and, after FROM, a sender (_counterparty_tokens of the
    sender region), or, with no FROM, a company form among the words after its transfer wording
    (_after_transfer_wording). A reference and a town, a street or a name with no form printed after a teller's, a
    branch's or a counter's transfer ('BRANCH TRANSFER 00123 <town>', 'BRANCH TRANSFER <two words>') name nobody: the
    bank prints the booking branch there, and the row stays held (transfer_no_counterparty)."""
    classifier = _classifier()
    stripped = _without_deposit_channel_words(text)
    if not _transfer_counterparty_words(stripped, bank):
        return False
    if re.search(r"\bFROM\b", classifier._before_receiver(stripped)) is not None:
        return bool(_counterparty_tokens(classifier._sender_payer_region(stripped)))
    tokens = _counterparty_tokens(_after_transfer_wording(stripped))
    return bool(tokens) and classifier.company_form(" ".join(tokens))


def _without_deposit_channel_words(text: str) -> str:
    """§8.2, §8.3 (audit B2: I48): the text without its check, cash, branch, teller and ATM forms (the classifier's
    _CHECK_DEPOSIT_FORM and _CASH_BRANCH_ATM_FORM), which never name a transfer's counterparty ('TELLER TRANSFER')."""
    classifier = _classifier()
    return classifier._CASH_BRANCH_ATM_FORM.sub(" ", classifier._CHECK_DEPOSIT_FORM.sub(" ", text))


def _explicit_deposit(channel: str, row: str) -> bool:
    """§8.2, §8.3 (audit B2: I48): a check, cash, branch or ATM row that prints an explicit deposit form."""
    return channel in _DEPOSIT_CHANNELS and _EXPLICIT_DEPOSIT_FORM.search(row) is not None


def _transfer_reading(
    record: TransactionClassification, text: str, channel: str, region: str,
) -> tuple[bool, list[str], bool]:
    """§8.2, T13: (transfer row, its counterparty words, transfer_no_counterparty), as the pass and the census's G4
    read them. Audit B2: an explicit check, cash or ATM deposit form is no bare transfer (I48: Q2 and Q3 count it); the
    counterparty is read with the statement's bank (I01); and an ACH or unlabelled payer region that is only a bank's
    name and an account description (_bank_account_payer, I01) names no payer either. A wire is decided by Q5 before
    this hold (§8.10), so a wire row never carries it.

    Audit round 2, R2-B03 (R05; I01, Q2: a bank's name is never the payer's): nor does an ACH or unlabelled payer
    region that is only a sending bank's name or a bank by its own form (_bank_only_payer: 'sending' or 'form'), on a
    row that prints no entry field, which no rule verified and nothing claimed: the holder's pull from another of its
    own bank accounts ('ACH CREDIT <bank>', '<bank> ACH'). The statement's own bank's channel ('own': 'CHASE ONLINE' on
    a Chase statement) is never held: it is a customer's bill payment through the bank (counted, never verified)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    transfer_row = _transfer_row(row) and not _explicit_deposit(channel, row)
    words = _transfer_counterparty_words(text, record.bank) if channel == "person_to_person" else []
    bank_account = channel in {"ach_eft", "other"} and (
        _bank_account_payer(region, record.bank) or _bank_only_pull(record, text, region)
    )
    return transfer_row, words, channel != "wire" and ((transfer_row and not words) or bank_account)


def _bank_only_pull(record: TransactionClassification, text: str, region: str) -> bool:
    """§8.2 (audit round 2, R2-B03: R05): an ACH or unlabelled credit whose payer region is only a sending bank's name
    or a bank by its own form (_bank_only_payer), on a row that prints no entry field, which no rule verified and no
    registry, payout, factoring payee or factor claimed: no payer is printed (held as transfer_no_counterparty, Q2)."""
    if not region or record.revenue_classification == "verified_revenue":
        return False
    classifier = _classifier()
    if classifier.entry_fields(text).strip():
        return False
    if _bank_only_payer(region, "", record.bank, row=classifier._before_receiver(text)) not in {"sending", "form"}:
        return False
    return not (_claimed(record, text) or _factoring_payout_payer(region, text))


#: §8.6 (audit round 2, R2-B03: R05): the entry words of a bank's merchant deposit or card settlement ('<bank>
#: DES:DEPOSIT', Synchrony's 'MTOT DEP', 'BTOT', 'NET SETTLE', 'STLMT', a merchant word): a bank named before such an
#: entry pays the business's own sales, and keeps its reading.
_BANK_SETTLEMENT_ENTRY = re.compile(r"(?<![A-Z])(?:DEPOSIT|DEP|MTOT|BTOT|SETTLE\w*|STLMT|MERCH\w*)\b")
#: §8.6 (R2-B03: R05): the channel words a bank prints after its own name in an ACH payer region ('<bank> ACH',
#: 'CHASE ONLINE', '<bank> N A'), dropped from the end of the name.
_BANK_ONLY_TAIL = frozenset({"ACH", "ONLINE", "N", "A", "NA"})
#: §8.6 (R2-B03: R05): the last word of a bank's own form, and the most words such a name may print.
_BANK_ONLY_FORM_ENDS = frozenset({"BANK", "BANCORP", "FSB"})
_BANK_ONLY_MAX_WORDS = 4
#: §8.6 (R2-B03: R05): the listed sending banks' names alone (the registry's P2P_SENDING_BANK_NAMES; Zelle's PAY ID,
#: which _P2P_LAYOUT_PHRASES also removes, names no bank).
_SENDING_BANK_NAME = re.compile(
    r"(?<![A-Z])(?:" + "|".join(re.escape(name) for name in sorted(P2P_SENDING_BANK_NAMES, key=len, reverse=True))
    + r")\b"
)
#: The marks _bank_only_payer puts where a bank's name stood (lowercase: no upper-case reader ever matches them).
_SENDING_MARK = "sending-bank"
_OWN_MARK = "own-bank"
#: §8.6 (R2-B03: R05): a person-to-person label printed on the row ('<bank> P2P <reference> <sender>', Bank of
#: America's P2P payment received at another bank): the bank is a person's sending bank (Q4), never the payer alone.
#: Audit round 3, R3-B08 (R3-32 (2)): read inside the payer region only, the bank's name followed by the label
#: (_p2p_label_after_bank_name); an entry field's P2P ('CO ENTRY DESCR:P2P') no longer refuses the bank-only reading.
_P2P_LABEL = re.compile(r"(?<![A-Z0-9])P2P(?![A-Z0-9])")


def _p2p_label_after_bank_name(region: str, row: str) -> bool:
    """§8.6 (audit round 3, R3-B08: R3-32 (2)): the payer region prints a person-to-person label (_P2P_LABEL), or the
    row (`row`, before its receiver fields) prints the region's name followed by the label ('BANK OF AMERICA P2P
    <reference> <sender>': the payer region ends at the label, a token holding a digit)."""
    if _P2P_LABEL.search(region):
        return True
    name = region.strip()
    return bool(row and name) and re.search(
        r"(?<![A-Z0-9])" + re.escape(name) + r" P2P(?![A-Z0-9])", row
    ) is not None


def _own_bank_whole_region(region: str, bank: str) -> bool:
    """§8.2, §8.6 (audit round 3, R3-B08: R3-31, R3-32): the payer region, its reference tokens and a trailing channel
    word (_BANK_ONLY_TAIL) dropped, is as a whole one of the statement's own bank's names: its normalized bank field and
    printed short forms (_statement_bank_forms), or a listed sending-bank spelling the bank prints for itself
    (_own_bank_sending_spellings: BOFA on Bank of America, US BANK on U.S. Bank, JPMORGAN CHASE and CHASE BANK on
    Chase). Read on the region's name (payer_name) and, for a spaced initialism ('U S BANK'), on its words with single
    letters kept."""
    classifier = _classifier()
    own = {*_statement_bank_forms(bank), *_own_bank_sending_spellings(bank)}
    if not own:
        return False
    for words in (classifier.payer_name(region).split(), region.split()):
        kept = [word for word in words if not classifier._is_reference_token(word)]
        while kept and kept[-1] in _BANK_ONLY_TAIL:
            kept.pop()
        if kept and " ".join(kept) in own:
            return True
    return False


@cache
def _own_bank_sending_spellings(bank: str) -> tuple[str, ...]:
    """§8.2, §8.6 (audit round 3, R3-B08: R3-31, R3-32): the listed sending-bank spellings the statement's bank prints
    for itself (the registry's OWN_BANK_SENDING_SPELLINGS), read when one of an entry's markers starts the normalized
    bank field as whole words (a leading THE skipped), so a marker never matches inside another bank's name ('FIRST
    CITIZENS BANK' is not Citizens Bank). Empty when none does."""
    classifier = _classifier()
    field = classifier.normalize_transaction_description(bank).strip().upper()
    field = re.sub(r"^THE ", "", field)
    spellings: set[str] = set()
    for markers, printed in OWN_BANK_SENDING_SPELLINGS:
        if any(re.match(re.escape(marker) + r"(?![A-Z0-9])", field) for marker in markers):
            spellings.update(printed)
    return tuple(sorted(spellings, key=len, reverse=True))


def _bank_only_payer(region: str, entry: str, bank: str | None, *, row: str = "") -> str | None:
    """§8.2, §8.6 (audit round 2, R2-B03: R05; I01 and the registry's note: a bank's name is never the payer's name):
    the payer region names only a bank. On its name (payer_name: no token holding a digit, no single letter) the listed
    sending banks' names (P2P_SENDING_BANK_NAMES) are marked, then the statement's own bank's names
    (_statement_bank_names); reference tokens are dropped, and a trailing channel word (_BANK_ONLY_TAIL: ACH, ONLINE,
    N A, NA). 'sending' when only a sending bank's name is left, 'own' when only the statement's own bank's, 'form' when
    one to four words ending BANK, BANCORP, FSB or CREDIT UNION are left (no marked name among them) and the classifier
    reads the region as a bank by its own form (bank_by_form: never a food, blood, sperm, eye, tissue, milk, bone or
    cord-blood bank, never a company whose name holds the bank word, never a bank's settlement form). None otherwise,
    for an empty region, for a bank's settlement or merchant-services originator (BANK_SETTLEMENT_ORIGINATOR), for an
    entry of a merchant deposit or card settlement (_BANK_SETTLEMENT_ENTRY: '<bank> DES:DEPOSIT', 'MTOT DEP'), which pay
    the business's own sales, and for a payer region that prints a person-to-person label after the bank's name
    (_p2p_label_after_bank_name, read on `row`, the row before its receiver fields: the bank is a person's sending
    bank, whose payment Q4 reads, never the holder's pull).

    Audit round 3, R3-B08 (R3-31, R3-32): the statement's own bank is read first, as a whole region
    (_own_bank_whole_region: its normalized bank field, its printed short forms, and the listed sending-bank spellings
    it prints for itself), so a statement whose bank is itself a listed sending bank reads its own name alone as 'own'
    ('WELLS FARGO ACH' on Wells Fargo, 'BOFA' on Bank of America, 'JPMORGAN CHASE' on Chase), never as another bank's
    pull; a longer region keeps the old order (sending, then own, then form), so 'JPMORGAN CHASE' inside a longer name
    is never cut to its other words.

    Q6 never verifies such a payer, which is counted as no_payer_printed (a bank's name names no customer); a sending
    bank or a bank by its form on a row with no entry field is the holder's own pull (_bank_only_pull, held)."""
    classifier = _classifier()
    if not region or classifier.BANK_SETTLEMENT_ORIGINATOR.search(region) or _BANK_SETTLEMENT_ENTRY.search(entry or ""):
        return None
    if _p2p_label_after_bank_name(region, row):
        return None
    if bank and _own_bank_whole_region(region, bank):
        return "own"
    marked = _SENDING_BANK_NAME.sub(f" {_SENDING_MARK} ", classifier.payer_name(region))
    own = _statement_bank_names(bank) if bank else None
    if own is not None:
        marked = own.sub(f" {_OWN_MARK} ", marked)
    words = [word for word in marked.split() if not classifier._is_reference_token(word)]
    while words and words[-1] in _BANK_ONLY_TAIL:
        words.pop()
    if words == [_SENDING_MARK]:
        return "sending"
    if words == [_OWN_MARK]:
        return "own"
    if not words or _SENDING_MARK in words or _OWN_MARK in words or len(words) > _BANK_ONLY_MAX_WORDS:
        return None
    if words[-1] not in _BANK_ONLY_FORM_ENDS and words[-2:] != ["CREDIT", "UNION"]:
        return None
    return "form" if classifier.bank_by_form(region) else None


#: §8.2 (audit B2: I01): the account-description words a bank prints after its own name on a pull from another of
#: the holder's bank accounts ('<bank> SAVINGS <n> ACH', '<bank> BUSINESS BANKING OPERATING ACCOUNT ACH'), and the
#: product words one of them must be; a bank's own form ends its name.
_BANK_ACCOUNT_DESCRIPTION_WORDS = frozenset({
    "SAVINGS", "SAVING", "SVGS", "SAV", "CHECKING", "CHKG", "CHK", "BUSINESS", "BANKING", "OPERATING", "ACCOUNT",
    "ACCT", "MONEY", "MARKET", "ACH",
})
_BANK_PRODUCT_WORDS = frozenset({"SAVINGS", "SAVING", "SVGS", "CHECKING", "CHKG", "BANKING"})
_BANK_FORM_WORDS = frozenset({"BANK", "BANCORP", "FSB", "CU", "FCU"})


def _bank_account_payer(region: str, bank: str | None) -> bool:
    """§8.2 (audit B2: I01; a bank's name is never the payer's name): an ACH or unlabelled payer region that is only a
    bank's name and an account description: a sending bank's or the statement's own bank's name, or one to four words
    ending in a bank's form (BANK, BANCORP, FSB, CU, FCU), or one word before a BANKING product ('<brand> BUSINESS
    BANKING OPERATING ACCOUNT'), followed only by account-description words (_BANK_ACCOUNT_DESCRIPTION_WORDS), one of
    them a product word (SAVINGS, CHECKING, BANKING), references and digits. Such a credit is the holder's pull from
    another of its own bank accounts: no payer is printed (held as transfer_no_counterparty, Q2)."""
    if not region:
        return False
    classifier = _classifier()
    named = _P2P_LAYOUT_PHRASES.sub(" BANK ", region)
    own = _statement_bank_names(bank) if bank else None
    if own is not None:
        named = own.sub(" BANK ", named)
    tokens = [
        token for token in named.split()
        if not classifier._is_reference_token(token) and not any(ch.isdigit() for ch in token)
    ]
    split = next((at for at, token in enumerate(tokens) if token in _BANK_ACCOUNT_DESCRIPTION_WORDS), len(tokens))
    name, description = tokens[:split], tokens[split:]
    if not description or any(token not in _BANK_ACCOUNT_DESCRIPTION_WORDS for token in description):
        return False
    if not any(token in _BANK_PRODUCT_WORDS for token in description):
        return False
    if name and name[-1] in _BANK_FORM_WORDS and len(name) <= 4:
        return True
    return len(name) == 1 and "BANKING" in description


def _p2p_rail(row: str) -> bool:
    """§8.4 in pass 7 (S4.2 follow-up 2): the row prints one of the classifier's consumer person-to-person rails
    (_CONSUMER_P2P_RAIL), a VIREMENT counting only in its Interac forms (_INTERAC_FORM). Audit round 3, R3-29: or
    Interac's French form, singular or plural (_INTERAC_COURRIEL: 'DEPOT AUTO VIREMENTS PAR COURRIEL <sender>'), which
    _channel reads before a cash or branch DEPOT."""
    if _INTERAC_COURRIEL.search(row) is not None:
        return True
    return any(
        found.group(0) != "VIREMENT" or _INTERAC_FORM.search(row) is not None
        for found in _classifier()._CONSUMER_P2P_RAIL.finditer(row)
    )


def _transfer_wording(row: str) -> bool:
    """§8.2 in pass 7 (S4.2 follow-up 2): the classifier's transfer wording, or a VIREMENT printed without an Interac
    form ('VIREMENT EN LIGNE', 'VIREMENT ENTRE COMPTES'). Audit round 2, R2-B09 (R28): the transfer wording outside a
    company-formed ACH originator's own name (classifier.credit_transfer_wording), so a company whose name prints TRF,
    XFR or TRANSFER is an ACH payer Q6 reads (the channel, the transfer row and reading, Q7's refusals)."""
    return _classifier().credit_transfer_wording(row) is not None or (
        _VIREMENT.search(row) is not None and _INTERAC_FORM.search(row) is None
    )


def _transfer_row(row: str) -> bool:
    """§8.2: transfer wording on a row that prints no person-to-person or push rail, which the transfer rules read (a
    counterparty, or none: transfer_no_counterparty)."""
    return _transfer_wording(row) and not _p2p_rail(row) and _classifier()._PUSH_RAIL.search(row) is None


@dataclass(frozen=True)
class _OwnWords:
    """§7.0: the holder's own words on a store-name platform (`words`), and (FW wave 3) the platform entry's words when
    they are a consecutive run of the holder's name (`run`: the store's own name, spared at any length)."""

    words: frozenset[str] = frozenset()
    run: frozenset[str] = frozenset()


def _own_words(record: TransactionClassification, text: str) -> _OwnWords:
    """§7.0: the holder's own words, as the recurrence veto reads them on a store-name platform: the account name's
    distinctive words and the name the bank prints in the receiver field (a delivery platform prints the merchant's
    store there). On every other source there are none (S2.4 review: a veto word always vetoes there)."""
    classifier = _classifier()
    entity = record.revenue_canonical_entity
    if entity not in classifier._STORE_NAME_PAYOUT_ENTITIES:
        return _OwnWords()
    # Final review I4: a veto word that is the whole entry field, or forms it alone with generic words, is the
    # platform's own financing wording: no store name prints, so the holder's words spare nothing.
    if not classifier.store_name_printed(text, entity, _holder(record)):
        return _OwnWords()
    own = set(classifier.holder_words(_holder(record)))
    for found in classifier._RECEIVER_FIELD_VALUE.finditer(text):
        own.update(classifier._distinctive_words(found.group(0).split()[1:]))
    return _OwnWords(frozenset(own), classifier.store_name_run_words(text, entity, _holder(record)))


def _own_word(word: str, own: _OwnWords) -> bool:
    """§7.0: a word of four letters or more that is one of the holder's own words or the start of one; FW wave 3: or a
    word of the store's own name, the entry's run of the holder's name ('FIN AND FORK'), at any length."""
    return word in own.run or (len(word) >= 4 and any(mine == word or mine.startswith(word) for mine in own.words))


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
    known = match_known_payee(_classifier()._without_receiver_value(text), credit=True)
    return known if known is not None and known.entity in PAYOUT_CREDIT_ENTITIES else None


def _customer_financier(record: TransactionClassification, text: str, *, non_sale: bool = True) -> str | None:
    """§8.9 (owner ruling 2026-10-02, Q8; audit I17): the lease-to-own or patient financier (CUSTOMER_FINANCING_PAYERS:
    Snap Finance, Koalafi, Cherry, Acima, Terrace Finance, Wisetack, Katapult, Progressive Leasing) whose payout to the
    merchant for a customer's financed purchase the row is, read on the payer region; or None. None, in this order, on a
    credit under the $1 floor; on a channel other than a wire, an ACH or EFT row or an unlabelled one; on a row with no
    payer region, or a wire's region that names nobody (blanked as credit_facts blanks it); on a consumer-side row (OQ2's
    consumer words, _BNPL_CONSUMER_CREDIT: a refund, a return, a withdrawal, a reward, a card or a purchase) or a
    class-action payout (_LEGAL_SETTLEMENT_WORDS), read without the receiver field's value; on a non-sale or financing
    credit (audit round 3, R3-B14: R3-06, _payout_non_sale: an advance, capital, interest, a dividend or a rebate, read
    without the receiver field's value and the holder's names, so a holder named CAPITAL never vetoes); and on a
    consumer (PPD or WEB) entry to a person who is not the holder. Otherwise the first financier whose spelling the
    region prints; a spelling that holds LOAN (Snap's SNAP LOAN FUNDING) only in Snap's merchant form
    (_SNAP_MERCHANT_FUNDING). `non_sale=False` reads the financier without the R3-06 veto, for _payout_claim_vetoed
    alone."""
    classifier = _classifier()
    if record.amount < classifier._MICRO_DEPOSIT_FLOOR:
        return None
    channel = _channel(text, record.bank)
    if channel not in _CUSTOMER_FINANCING_CHANNELS:
        return None
    region = classifier.payer_region(text)
    if channel == "wire" and _wire_region_names_nobody(text, region, record.bank):
        region = ""
    if not region:
        return None
    words = classifier._without_receiver_value(text)
    if classifier._BNPL_CONSUMER_CREDIT.search(words) or _LEGAL_SETTLEMENT_WORDS.search(words):
        return None
    if non_sale and _payout_non_sale(record, text):
        return None
    holder = _holder(record)
    if consumer_entry(text, holder) and _person_receiver(text, "", holder):
        return None
    for entity, spelling in _CUSTOMER_FINANCING_PAYERS.items():
        found = spelling.search(region)
        if found is None:
            continue
        if "LOAN" in found.group(0) and not classifier._SNAP_MERCHANT_FUNDING.search(classifier._before_receiver(text)):
            continue
        return entity
    return None


def _claimed(record: TransactionClassification, text: str) -> bool:
    """§8.1, §8.9: the operating registry, a payout-credit entity or a factoring payee claimed the row. A registry row
    that prints a financing word is not claimed (review C2). Audit B3 (I11): a card credit released as its processor's
    instant payout is claimed by that processor (its pulls and fees never hold it as the payer also debited). Owner
    ruling 2026-10-02 (Q8): and a lease-to-own or patient financier's merchant payout (_customer_financier), which skips
    the holds a payout entity or a factor skips (the insurer name, the financing, counter-debit, holder and non-sale
    holds); the insurer, possible-return, pay, personal-income and payroll-tax holds and the $1 floor still read it.
    Audit round 3, R3-B14 (R3-06): a payout entity's or a financier's credit printing a non-sale or financing word
    (_payout_non_sale: an advance, capital, interest, a dividend or a rebate) is not claimed, so the holds read it as
    they read the same row from any other payer; the payout_credit_entity tier arm is unchanged."""
    if record.revenue_match_method == PROCESSOR_CARD_PAYOUT_METHOD:
        return True
    if record.revenue_match_method in _REGISTRY_METHODS:
        return not registry_financing(record, text)
    if record.classification == "factoring":
        return True
    if _payout_entity(text) is not None and not _payout_non_sale(record, text):
        return True
    return _customer_financier(record, text) is not None


def _payout_non_sale(record: TransactionClassification, text: str) -> bool:
    """Audit round 3, R3-B14 (R3-06; the underwriter's Q8 of 2026-10-02, "Their consumer-side credits (refunds, loans to
    the holder) stay as today", and the MCA principle): the row, read without the receiver field's value and without
    the holder's names (the I47 strip's, _without_holder_name with _holder_strip_names), prints a non-sale or
    financing word (classifier._PAYOUT_NON_SALE_CREDIT: ADVANCE(S), ADVNC, ADVN, ADVC, CASH ADV..., CAPITAL, CAPTL,
    INTEREST, DIVIDEND(S), REBATE(S); never FUNDING, PAYOUT, PAYMENT, LEASE FUND, PROCEEDS or a bare ADV). Such a credit
    of a payout entity or a lease-to-own or patient financier is never claimed as a merchant payout: a holder named
    'NORTHWIND CAPITAL DENTAL', in its receiver field or in Snap's merchant form, never vetoes."""
    words = without_receiver_and_holder(text, record.account_name, record.holder_name)
    return _classifier()._PAYOUT_NON_SALE_CREDIT.search(words) is not None


def without_receiver_and_holder(text: str, account_name: str | None, holder_name: str | None) -> str:
    """Audit round 3, R3-B14 review round 1 (findings 1 and 4): `text` without the receiver field's value
    (classifier._without_receiver_value) and without the holder's names (the I47 strip's: _without_holder_name with
    _holder_strip_names), so a word inside the holder's own name, printed in a labelled receiver field or as an
    unlabelled one (Wells Fargo's trailing receiver, TD's ACH DEPOSIT, a generic ACH CREDIT), is never read. Read by
    the R3-06 veto on both sides (the pass's _payout_non_sale and the classifier's Cherry D1 veto, _is_payout_credit,
    which passes the statement's account-name field and holder name before a record exists) and by the floor-plan
    service wording (_dealer_activity)."""
    classifier = _classifier()
    return _without_holder_name(
        classifier._without_receiver_value(text), classifier.holder_reading(account_name, holder_name),
        also=_holder_strip_names_of(account_name, holder_name),
    )


def _leading_card_credit(text: str) -> bool:
    """§8.1 (audit B3: I04): a card credit printed first ('CARD CREDIT', BMO's with its merchant line dropped, or
    Regions' 'CARD CREDIT <merchant>'), with no push word (§7.11's) and no person-to-person or push rail (Cash App and
    Apple Cash are person-to-person rails, so Regions' pushes stay counted): held as a possible return."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    return _LEADING_CARD_CREDIT.match(row) is not None and not (
        classifier._CARD_CREDIT_PUSH_WORD.search(row)
        or classifier._CONSUMER_P2P_RAIL.search(row)
        or classifier._PUSH_RAIL.search(row)
    )


def _card_payout_processor(row: str) -> str | None:
    """Audit B3 (I11): the processor (CARD_PAYOUT_PROCESSOR_NAMES) a row names, as a whole word; None for none."""
    for entity, pattern in _CARD_PAYOUT_NAMES.items():
        if pattern.search(row):
            return entity
    return None


def _card_payout_credit_processor(text: str) -> str | None:
    """Audit B3 (I11): the processor a card credit names as its whole payer, when step 3 read the card label alone: the
    row prints DEBIT CARD CREDIT (or Citibank's cut CREDI) or POS CREDIT, after it only the processor's name with
    reference tokens and generic words (never a financing or other word: 'STRIPE CAPITAL' is not the processor's
    payout), and no other reversal marker once the label is removed. None otherwise."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    label = _CARD_PAYOUT_LABEL.search(row)
    if label is None or classifier._reversal_credit(_CARD_PAYOUT_LABEL.sub(" ", text)):
        return None
    rest = row[label.end():]
    for entity, pattern in _CARD_PAYOUT_NAMES.items():
        found = pattern.search(rest)
        if found is None:
            continue
        others = (rest[:found.start()] + " " + rest[found.end():]).split()
        if not any(classifier._is_payer_word(word) for word in others):
            return entity
    return None


def _processor_card_payouts(
    records: Sequence[TransactionClassification], duplicate_indexes: set[int],
) -> dict[int, str]:
    """§7.11, §6.3 narrowing 9 (audit B3: I11; MCA principle and standard A1/A2: a processor's payout is sales): the
    card credits the reversal rule (step 3) took as a card refund, or a push word released and §8.1 would hold, that
    name a merchant processor as their whole payer (_card_payout_credit_processor) on a statement that also prints that
    processor's own ACH activity (its ACH payout, its ACH pull or a returned pull: any posted row naming it with an
    electronic-payment form, never another card credit) and no card purchase at it (a posted debit naming it that is a
    card purchase: a refund of that purchase cannot be told from a payout). {credit index: processor}. Never a row a
    rule verified, a pair pass 4 made, a duplicate or a direction conflict. A marketplace or a retailer (Uber, DoorDash,
    Amazon) names no processor of the table, so its card credits keep the refund reading."""
    classifier = _classifier()
    candidates: dict[int, str] = {}
    activity: set[str] = set()
    purchases: set[str] = set()
    for index, record in enumerate(records):
        if (
            index in duplicate_indexes or not record.is_posted or record.amount == 0
            or _card_payout_processor(record.normalized_description) is None
        ):
            continue
        text = classifier.revenue_text(record.normalized_description)
        row = classifier._before_receiver(text)
        entity = _card_payout_processor(row)
        if entity is None:
            continue
        if record.amount < 0:
            if record.classification == "pos" or classifier._matches_any(row, classifier._POS_PATTERNS):
                purchases.add(entity)
            elif classifier._ELECTRONIC_PAYMENT_FORM.search(row):
                activity.add(entity)
            continue
        if _CARD_PAYOUT_LABEL.search(row) or _CARD_CREDIT_LABEL.search(text) or _LEADING_CARD_CREDIT.match(row):
            if (
                record.direction_consistent
                and record.revenue_classification != "verified_revenue"
                and record.revenue_match_method not in {"matched_reversal_pair", "direction_conflict"}
                and (
                    record.revenue_match_method == "reversal_cancellation_exclusion"
                    or record.revenue_classification == "unverified_deposit"
                )
            ):
                processor = _card_payout_credit_processor(text)
                if processor is not None:
                    candidates[index] = processor
            continue
        if classifier._ELECTRONIC_PAYMENT_FORM.search(row):
            activity.add(entity)
    return {index: entity for index, entity in candidates.items() if entity in activity and entity not in purchases}


#: §8.2, §20 (audit B2: I01, I21): the online-banking channel codes and account descriptions a transfer prints, never
#: its counterparty: Citi Business Online (CBUSOL), online banking (OLB), an external transfer (EXT, EXTERNAL), CIBC's
#: CMO, telephone banking (and TELEPHONE before transfer wording), PHONE, a card (CRD), a federal savings bank (FSB),
#: an overdraft sweep's PROTECTION and OVERDRAFT, Found's name, BUSINESS BANKING and OPERATING ACCOUNT, and FUNDING
#: beside TRANSFER ('FUNDING TRANSFER CREDIT'). A custodian's name is not one (audit I01, I28: unconfirmed).
_TRANSFER_CHANNEL_CODES = re.compile(
    r"(?<![A-Z])(?:CBUSOL|OLB|EXT|EXTERNAL|CMO|TELEPHONE BANKING|PHONE|CRD|FSB|PROTECTION|OVERDRAFT|FOUND"
    r"|BUSINESS BANKING|OPERATING ACCOUNT)\b"
    r"|(?<![A-Z])TELEPHONE(?= (?:TRANSFER|TRNSFR|TRSFR|TRANSF|XFER|XFR|TFR|TRF)\b)"
    r"|(?<![A-Z])FUNDING(?= (?:TRANSFER|XFER)\b)|(?<=\bTRANSFER )FUNDING\b"
)
#: §8.2 (audit B2: I01): a credit union's institution name, the one word before CU or FCU ('ACH TRANSFER FROM <name>
#: CU'): a bank's name, never a sender's. A person's name before it keeps its other words.
_CREDIT_UNION_NAME = re.compile(r"(?<![A-Z])[A-Z]+ F?CU\b")
#: §8.2 (audit B2: I01): a sending bank's name glued to its transfer wording ('USAAFSBTRNSFER').
_GLUED_BANK_TRANSFER = re.compile(
    r"(?<![A-Z])(?:"
    + "|".join(re.escape(name.replace(" ", "")) for name in sorted(P2P_SENDING_BANK_NAMES, key=len, reverse=True))
    + r")(?:FSB)?(?:TRANSFER|TRNSFER|TRNSFR|TRSFR|XFER|XFR|TFR|TRF)\b"
)


def _without_bank_and_channel_words(text: str, bank: str | None = None) -> str:
    """§8.2, §20 (audit B2: I01; the registry's note: a bank's name is never the sender's name): the text without a
    sending bank's name (the registry's P2P_SENDING_BANK_NAMES, _P2P_LAYOUT_PHRASES), the statement's own bank's names
    (`bank`, _statement_bank_names), a bank's name glued to its transfer wording, a credit union's institution name,
    the receiver fields' bank words (_RECEIVER_BANK_WORDS) and the channel codes and account descriptions
    (_TRANSFER_CHANNEL_CODES), so none of them names a transfer's counterparty."""
    stripped = _P2P_LAYOUT_PHRASES.sub(" ", text)
    own = _statement_bank_names(bank) if bank else None
    if own is not None:
        stripped = own.sub(" ", stripped)
    for pattern in (_GLUED_BANK_TRANSFER, _CREDIT_UNION_NAME, _RECEIVER_BANK_WORDS, _TRANSFER_CHANNEL_CODES):
        stripped = pattern.sub(" ", stripped)
    return " ".join(stripped.split())


def _transfer_counterparty_words(text: str, bank: str | None = None) -> list[str]:
    """§8.2: the payer words a transfer prints once template prefixes, generic words, account words and reference
    tokens are removed. S4.2 review (I2): the ACH field labels, SEC codes and reference labels are removed with the
    reference printed after them, letters only or not ('REF IBEABCD'), and what is left is read as S2.3 reads a
    transfer's originator (_originator_payer_words), so an account description ('FROM HELOC', 'FROM TAX RESERVE',
    'FROM OPERATING') is never a counterparty. S4.2 re-review (fix 4): failing that, a short or company-formed name
    after FROM is one (_short_or_formed_counterparty). S4.2 follow-up 2: the French transfer and posting words
    (_VIREMENT_TRANSFER_WORDS) are removed too. S4.2 final review (fix 5): so are a French month and a bank branch.
    S4.2 fix round 4: a French month only where a date prints it (_without_date_months), on the row's start too.
    A3 (precision sample): a wire's channel and layout words (_WIRE_LAYOUT_WORDS: 'INCOMING FEDWIRE TRANSFER') and
    currency-conversion wording (_CURRENCY_CONVERSION: 'ONLINE BANKING FOREIGN EXCHANGE') are never a counterparty.
    Audit B2 (I01): nor is a bank's name, the statement's own bank (`bank`) included, a channel code or an account
    description (_without_bank_and_channel_words)."""
    classifier = _classifier()
    text = _without_bank_and_channel_words(text, bank)
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
    if _transfer_row(classifier._before_receiver(stripped)) and _transfer_counterparty_words(stripped, bank):
        return False
    return not _p2p_sender_region(stripped)


@cache
def _statement_bank_forms(bank: str) -> tuple[str, ...]:
    """§8.1 (A3 review): the names the statement's bank prints for itself: its whole normalized name, and the short
    forms it prints (the registry's STATEMENT_BANK_PRINTED_NAMES, read when the bank field contains one of the entry's
    bank words), longest first. Empty when the bank field normalizes to nothing."""
    classifier = _classifier()
    field = classifier.normalize_transaction_description(bank).strip().upper()
    forms = {field}
    for markers, printed in STATEMENT_BANK_PRINTED_NAMES:
        # A3 review round 2: the bank field names the bank by containment (whole words, any case), not exact spelling.
        if any(re.search(r"(?<![A-Z])" + re.escape(marker) + r"(?![A-Z])", field) for marker in markers):
            forms.update(printed)
    forms.discard("")
    return tuple(sorted(forms, key=len, reverse=True))


@cache
def _statement_bank_before_conversion(bank: str) -> re.Pattern[str] | None:
    """§8.1 (A3 review): the statement's bank's own name (_statement_bank_forms) printed right before
    currency-conversion wording. None when the bank field normalizes to nothing."""
    forms = _statement_bank_forms(bank)
    if not forms:
        return None
    names = "|".join(re.escape(form) for form in forms)
    return re.compile(r"(?<![A-Z])(?:" + names + r") (?=" + _CURRENCY_CONVERSION.pattern + ")")


@cache
def _statement_bank_names(bank: str) -> re.Pattern[str] | None:
    """§8.2 (audit B2: I01): the statement's bank's own names (_statement_bank_forms) as whole words, which never name
    a transfer's counterparty ('TRUIST ONLINE TRANSFER ...' on a Truist statement). None when the bank field normalizes
    to nothing."""
    forms = _statement_bank_forms(bank)
    if not forms:
        return None
    return re.compile(r"(?<![A-Z])(?:" + "|".join(re.escape(form) for form in forms) + r")\b")


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
            # Audit round 2, R2-B09 (R28): the transfer wording outside a company-formed ACH originator's own name.
            leading = row and all(classifier._is_reference_token(before) for before in tokens[:index]) and (
                classifier.credit_transfer_wording(rest) is not None or _VIREMENT.search(rest) is not None
            )
            if beside_day or leading:
                continue
        kept.append(token)
    return " ".join(kept)


def _after_transfer_wording(text: str) -> str:
    """§8.2 (S4.2 final review, fix 2): the words a transfer printed without FROM prints after its first transfer
    wording (the classifier's, or a VIREMENT), before its receiver fields and up to TO (a recipient). Audit round 2,
    R2-B09 (R28): the classifier's wording outside a company-formed ACH originator's own name
    (credit_transfer_wording)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    found = [
        match for match in (classifier.credit_transfer_wording(row), _VIREMENT.search(row)) if match is not None
    ]
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


#: §8.1 insurer_named_payer (audit I26; R2-OW07): the registry's INSURER_CREDIT_BRANDS, each pattern bounded as a whole
#: name, (entity, compiled patterns) in the table's order.
_INSURER_CREDIT_BRANDS = tuple(
    (entity, tuple(re.compile(rf"(?<![A-Z])(?:{pattern})(?![A-Z])") for pattern in patterns))
    for entity, patterns in INSURER_CREDIT_BRANDS.items()
)
#: §8.1 (R2-OW07): the revenue methods a listed insurer's credit carries (§6.1 step 5: the insurance rule's non-revenue
#: exclusion and T14's customer-payment reading), on which the reader names the registry's entity. Owner ruling
#: 2026-10-02 (the underwriter's Q2), R2-OW08: and the release's method, so a listed insurer's released credit reads as
#: it read before the release (the registry lookup still decides; this set is no claimed set).
_INSURER_REGISTRY_METHODS = frozenset({
    "insurance_provider_credit_exclusion", "insurer_customer_payment", "insurer_paid_for_services",
})


def insurer_credit_brand(region: str) -> str | None:
    """§8.1 (audit I26; R2-OW07): the entity of the first INSURER_CREDIT_BRANDS carrier a payer region names, or None.
    Credit-only: no debit and no classifier rule reads it."""
    if not region:
        return None
    for entity, patterns in _INSURER_CREDIT_BRANDS:
        if any(pattern.search(region) for pattern in patterns):
            return entity
    return None


@dataclass(frozen=True)
class InsurerReading:
    """§8.1 (audit I26; R2-OW07): an insurer read on a credit's payer region. `key` is the carrier the frequency of the
    underwriter's Q2 counts by (the registry's or the brand table's entity name, so one carrier is one key however it
    prints; otherwise the payer key of the region without the holder's names); `kind` is 'registry' (a listed insurer,
    §6.1 step 5), 'brand' (INSURER_CREDIT_BRANDS), 'named' (an insurer word, spelling or claim word) or 'title' (a
    title insurer, whose credit is a property closing's proceeds); `for_work` is False only for a title insurer and
    (R2-OW07 review round 1) a government payer, whose insurance programme's credit is a personal benefit or a public
    insurer's, never the business's work."""

    key: str
    kind: str
    for_work: bool


def _insurer_own_region(
    record: TransactionClassification, region: str, receiver_holders: Sequence[str] = (),
) -> str:
    """§8.1 (R2-OW07): the payer region without the holder's names (each of _holder_names by its runs, then R2-B04's
    _holder_strip_names and the statement's receiver-field holder names whole), so the holder's own INSURANCE word
    never makes its payer an insurer."""
    own = region
    for name in _holder_names(record):
        own = _without_holder_name(own, name)
    own = _without_holder_name(own, None, also=(*_holder_strip_names(record), *receiver_holders))
    return " ".join(own.split())


def insurer_payer_reading(
    record: TransactionClassification,
    text: str,
    region: str,
    entry: str,
    receiver_holders: Sequence[str] = (),
) -> InsurerReading | None:
    """§8.1 insurer_named_payer (audit I26, by Q6 of 2026-09-28 and the underwriter's Q2 (2026-10-02) option's "a
    one-off claim paid to a business on its own policy stays out"; R2-OW07): the insurer a credit's payer region names,
    or None; the first arm that reads wins. (a) An HCCLAIMPMT entry is a claim paid to a provider, never an insurer's
    reading (T18's claim-first rule keeps verifying it). (b) A listed insurer's credit (its revenue method one of
    _INSURER_REGISTRY_METHODS and the classifier's insurer lookup naming it): the registry's entity, or None for a
    premium financier. Audit round 3, R3-B13 (R3-11): read before the government arm, so a row the classifier's
    insurance rule read as a listed insurer is that insurer, government-shaped name or not ('ALLSTATE COUNTY', a Texas
    county mutual's cut the classifier's _PUBLIC_PAYER_NAME veto does not reach). (c) A government payer (§7.6) is an
    insurer only by _INSURER_NAME's spelled words or CLAIM (CLAIM never on a healthcare payer), read on the region
    without the holder's names, never for work: the reading the insurer-name hold made before I26 (R2-OW07 review round
    1), so a government insurance programme's credit (employment, parental, disability or family-leave insurance, a
    public insurer) stays held and never counts as the business's work; the widened spellings and brands never read a
    government payer. (d) Then the region is read without the holder's names (_insurer_own_region); empty, None. (e) A
    title firm is a title insurer when an insurer word or spelling prints (never for work), else None. (f) A
    premium-finance wording on the row before its receiver fields is premium financing, None. (g) A healthcare payer is
    an insurer only by _INSURER_NAME's spelled words (Q6c unchanged). (g2) A §15 deferred payer (_deferred_reading: the
    Canadian benefit carriers, HEALTH DENTAL CLAIM, CLMEFT) only by those words or CLAIM: the widened spellings and
    brands never read it, so a medical claim payment to a provider keeps its tier. (h) An INSURER_CREDIT_BRANDS carrier,
    by the brand's entity. (i) _INSURER_NAME, _INSURER_SPELLINGS or _CLAIM_WORD, keyed by the payer key. No channel
    gate, but (R2-OW07 review round 1; audit round 3, R3-B13: R3-57) on a consumer person-to-person rail (_p2p_rail:
    Zelle, Interac and its e-Transfer and VIREMENT forms, Venmo, Cash App, Square Cash, Apple Cash, Popmoney) the
    widened spellings and the brands are not read: a sender's surname or given name (MUTUA, SUBROTO) or the rail's own
    word (APPLE CASH INS) is no cut insurer, so the rail keeps the spelled-out words and CLAIM it read before I26. A
    push or instant rail (RTP, FEDNOW, INSTANT PAYMENT ...), a named transfer and an ACH entry worded TRANSFER, which
    sit on the person-to-person channel too, read every spelling and the brands, except that the cut MUTUA reads there
    only beside a company form on the payer region without the holder's names (classifier.company_form: 'REAL TIME
    PAYMENT FROM <GIVEN NAME> MUTUA' is a person's surname)."""
    classifier = _classifier()
    channel = _channel(text, record.bank)
    if classifier._HCCLAIMPMT.search(text):
        return None
    own = _insurer_own_region(record, region, receiver_holders)
    # Audit round 3, R3-B13 (R3-11): the registry arm reads before the government arm.
    if record.revenue_match_method in _INSURER_REGISTRY_METHODS:
        match = classifier._insurance_registry_match(classifier._split_glued_claim(text), glued_digits=True)
        if match is not None:
            return None if match[2] else InsurerReading(match[0], "registry", True)
    if government_payer(public_region(text)):
        if own and (
            _INSURER_NAME.search(own) or (_CLAIM_WORD.search(own) and not healthcare_payer(own))
        ):
            return InsurerReading(" ".join(classifier._payer_key(own)) or own, "named", False)
        return None
    if not own:
        return None
    row = classifier._before_receiver(text)
    # R2-OW07 review round 1: a consumer person-to-person rail reads the spelled-out words and CLAIM alone. Audit round
    # 3, R3-B13 (R3-57): only a consumer rail; a push rail, a named transfer and a TRANSFER entry read every spelling
    # and the brands, the cut MUTUA only beside a company form.
    widened = channel != "person_to_person" or not _p2p_rail(row)
    named = _INSURER_NAME.search(own) is not None
    spelled = named or (widened and any(
        found.group(0) != "MUTUA" or channel != "person_to_person" or classifier.company_form(own)
        for found in _INSURER_SPELLINGS.finditer(own)
    ))
    if _TITLE_FIRM.search(own):
        return InsurerReading(own, "title", False) if spelled else None
    if any(pattern.search(row) for pattern in classifier._PREMIUM_FINANCE_WORDING_PATTERNS):
        return None
    key = " ".join(classifier._payer_key(own)) or own
    if healthcare_payer(own):
        return InsurerReading(key, "named", True) if named else None
    claim = _CLAIM_WORD.search(own) is not None
    if _deferred_reading(text, channel, region, entry):
        return InsurerReading(key, "named", True) if named or claim else None
    brand = insurer_credit_brand(own) if widened else None
    if brand is not None:
        return InsurerReading(brand, "brand", True)
    if spelled or claim:
        return InsurerReading(key, "named", True)
    return None


def _facts_region(text: str, channel: str, bank: str | None = None) -> str:
    """The payer region the pass's facts read (credit_facts; owner ruling 2026-10-02, Q2: the insurer-for-work release
    reads it too): the classifier's payer_region, '' on the wire channel where it names no sender. Audit B5 (I14): a
    wire's region of labels alone, or with no name word, names no sender (_wire_label_only). Audit round 2, R2-B10
    review round 1 (R11): nor does a row an incoming-wire label starts that prints only a reference (the classifier's
    _bare_incoming_wire), whatever word of it the payer reader keeps (a month, a stray TT or FROM): it left the
    own-account reading only to be held as a wire with no sender, never counted. Audit round 3, R3-B07: nor a region of
    label, holder-noise, account-designation, purpose, filler or legal-form words (R3-40), nor a sending bank's channel
    name printed after the wire's label (R3-42, read with the statement's `bank`): _wire_region_names_nobody."""
    region = _classifier().payer_region(text)
    if channel == "wire" and _wire_region_names_nobody(text, region, bank):
        return ""
    return region


#: Owner ruling 2026-10-02 (the underwriter's Q2, "True revenue", option 2; §8.1, §8.10): the method, matched rule and
#: tier reason of an insurer's credit pass 7 releases as payment for the business's work: counted and flagged, never
#: verified and never toward a Q5 or Q6 repeat. It never joins _REGISTRY_METHODS or any claimed set: a released row is
#: unclaimed, so §8.10's holds 4 to 11 still read it (the insurer-name hold, item 3, passes over it).
INSURER_FOR_WORK_METHOD = "insurer_paid_for_services"
#: §8.10's threshold (Q2: "the same insurer pays three or more times in a month"): one insurer key pays the business
#: this many eligible credits within an inclusive span of INSURER_FOR_WORK_WINDOW_DAYS days (date[i+2] - date[i] <=
#: WINDOW_DAYS - 1). The span slides, so it reaches across a calendar month's edge; an undated credit counts as inside.
INSURER_FOR_WORK_MIN_CREDITS = 3
INSURER_FOR_WORK_WINDOW_DAYS = 31
#: A loose trade word (_SERVICE_TRADES_LOOSE) names the trade only on a statement with this many eligible insurer
#: credits or more, so it never counts a one-off claim on the business's own policy.
INSURER_FOR_WORK_LOOSE_MIN_CREDITS = 2
#: The owner's switch (the Q2 card's open point 1), OFF, the literal reading: on, a statement where one insurer key is
#: frequent would count every other eligible insurer credit too ('insurer_service_statement'), which the owner's words
#: do not say.
INSURER_FOR_WORK_STATEMENT_ARM = False
#: Q2: the forms insurers pay an agency with (an agent's EFT, a commission, a contingency); a not-for-work word yields
#: to one printed in the same words.
_INSURER_COMMISSION_FORM = re.compile(
    r"(?<![A-Z])(?:AGENTS? EFT|AGTEFT|AGT ?COMM|AGENT COMP|COMMS?|COMMISSIONS?|CONTINGEN\w*)(?![A-Z])|PICOMM(?![A-Z])"
)
#: Q2: the forms insurers pay the owner's trades with: the commission forms, a direct-repair program's DRP, a repair and
#: a vendor payment (the question's own example lines), read on the payer and the purpose words, never a wire's REF.
#: Audit round 3, R3-B13 (R3-58): the classifier's customer-payment wording (_INSURER_CUSTOMER_PAYMENT), the
#: service-form ground's other reader, reads the row before its receiver fields, a wire's REF included: Chase's BOOK
#: TRANSFER CREDIT and Santander print the purpose there, which _title_purpose_text does not read (never a bare COMM,
#: so 'REF COMM BANK NYC', the sending bank, stays held).
_INSURER_SERVICE_FORM = re.compile(
    _INSURER_COMMISSION_FORM.pattern + r"|(?<![A-Z])(?:DRP|REPAIRS?|VENDOR ?(?:PMT|PAY|PAYMENT))(?![A-Z])"
)
#: Q2: a premium, refund, return, dividend, cancellation, overpayment, member or subscriber word, or one of the
#: personal-benefit stems DISAB..., INVALIDIT..., ANNUIT... and PENSION... (the MCA principle: personal benefits are
#: never revenue), refuses every ground, unless a commission form prints in the same words. Audit round 3, R3-B13
#: (R3-10): the other personal-benefit words are _INSURER_PERSONAL_BENEFIT, _INSURER_LTD_BENEFIT and
#: _INSURER_NON_PROVIDER_BENEFIT below.
_INSURER_NOT_FOR_WORK = re.compile(
    r"(?<![A-Z])(?:REFUND\w*|RFND|PREM|PREMIUMS?|PREMSEC|RETURN\w*|DIVIDEND\w*|CANCEL\w*|UNEARNED|OVERPA\w*|MEMBER"
    r"|SUBSCRIBER|MBR|DISAB\w*|INVALIDIT\w*|ANNUIT\w*|PENSION\w*)(?![A-Z])"
)
#: Audit round 3, R3-B13 (R3-10; the underwriter's Q2 of 2026-10-02, "A one-off claim paid to a business on its own
#: policy stays out (held as today). Medical claim payments to providers keep counting as today."; the MCA principle:
#: personal benefits are never revenue): a disability benefit under another name (short-term disability's STD, a
#: weekly or income benefit) and life-policy money (a death or survivor benefit, a surrender, a policy's cash value, a
#: maturity, a beneficiary's payment) refuse every ground, read on the payer (without the holder's names) and the
#: purpose, as _INSURER_NOT_FOR_WORK is. A bare LIFE is never read (group health and dental claims print it).
_INSURER_PERSONAL_BENEFIT = re.compile(
    r"(?<![A-Z])(?:STD (?:BENEFITS?|BEN|BNFT|CLAIMS?|CLM|PMT|PAYMENT)|(?:WEEKLY|INCOME) (?:BENEFITS?|BEN|BNFT)|DEATH\w*"
    r"|SURVIVOR\w*|SURRENDER\w*|SURR|CASH ?VALUE|MATURITY|MATURED|BENEFICIAR\w*)(?![A-Z])"
)
#: Audit round 3, R3-B13 (R3-10; Q2's two sentences above): long-term disability's LTD before a benefit, claim or
#: payment word, read on the purpose alone (the entry fields or a wire's purpose fields), never on the payer region,
#: where LTD is a carrier's legal form ('<carrier> CO LTD DES:CLAIM PMT' is no disability benefit).
_INSURER_LTD_BENEFIT = re.compile(r"(?<![A-Z])LTD (?:BENEFITS?|BEN|BNFT|CLAIMS?|CLM|PMT|PAYMENT)(?![A-Z])")
#: Audit round 3, R3-B13 (R3-10; Q2's two sentences above): workers' compensation and a plain BENEFIT(S) wording, read
#: on the payer and the purpose (_non_provider_benefit), refuse every ground only where the holder is no provider
#: (_holder_provider: the holder's first trade is no clinic or pharmacy): a workers' compensation carrier paying a
#: clinic, a therapy practice or a pharmacy for treatment pays for its services; elsewhere it is a wage or an owner's
#: benefit. A bare COMP is never read (Truist's 'INS COMP' commission).
_INSURER_NON_PROVIDER_BENEFIT = re.compile(r"(?<![A-Z])(?:WC|WORKERS? ?COMP\w*|WORK ?COMP|BENEFITS?|BNFT)(?![A-Z])")
#: R3-B13 review round 1 (finding 2): the plain benefit words of _INSURER_NON_PROVIDER_BENEFIT, and the words that,
#: printed after one on the payer region, make it the carrier's name ('MUTUAL BENEFIT INS CO', 'SAMPLE BENEFIT LIFE INS
#: CO', 'MUTUAL BENEFIT GROUP'): an insurer word or spelling (_INSURER_NAME, _INSURER_SPELLINGS) or a legal form.
_INSURER_PLAIN_BENEFIT = re.compile(r"BENEFITS?|BNFT")
_INSURER_NAME_FORM = re.compile(r"(?<![A-Z])(?:CO|COMPANY|CORP|CORPORATION|INC|LLC|LTD|GROUP)(?![A-Z])")
#: Audit round 3, R3-B13 (R3-10): the holder trades whose insurer credits are medical claim payments to a provider.
_PROVIDER_TRADES = frozenset({"clinic", "pharmacy"})
#: Q2's four trades on a holder name, strict words: one names the trade from a single credit. HEALTHY, SURGE and a bare
#: GLASS are no trade word.
_SERVICE_TRADES = tuple(
    (label, re.compile(rf"(?<![A-Z])(?:{words})(?![A-Z])")) for label, words in (
        ("repair shop", r"AUTO ?BODY|BODY ?SHOP|BODY ?WORKS?|COLLISION|RE ?BODY|PAINT (?:AND|&) BODY|AUTO (?:REPAIR|GLASS)"
                        r"|GLASS (?:REPAIR|SHOP|SERVICE)S?|REPAIRS?|CARROSSERIE|DEBOSSELAGE|MECANIQUE"),
        ("insurance agency", r"INSUR\w*|ASSURANCES?|INS|UNDERWRIT\w*"),
        ("clinic", r"CLINIC\w*|CLINIQUE|MEDICAL|MED|HEALTHCARE|SANTE|DENTAL|DENTAIRE|DENTIST\w*|DDS|DMD|ORTHODON\w*"
                   r"|PHYSIO\w*|PHYSICAL THERAP\w*|CHIRO\w*|THERAP\w*|REHAB\w*|OPTOM\w*|OPTICAL|PODIAT\w*|PEDIATRI\w*"
                   r"|PHYSICIANS?|HOSPITAL|MASSAGE|RMT|COUNSELL?ING|PSYCH\w*|AUDIOLOG\w*|HEARING|LABORATOR\w*"
                   r"|RADIOLOG\w*|URGENT CARE|HOME CARE|NURSING|HOSPICE|AMBULANCE|ACUPUNCT\w*|NATUROPATH\w*"
                   r"|DERMATOLOG\w*|SURGERY|SURGICAL|SURGEONS?|ORTHOPED\w*|DIALYSIS|MEDICINE|DOCTORS?"),
        ("pharmacy", r"PHARMAC\w*|DRUGS?|APOTHECARY|RX|CHEMIST|COMPOUNDING"),
    )
)
#: Q2's loose trade words: an agency or a broker with no insurance word, the clinic words other businesses print too, a
#: repair shop's neighbours; read only on a statement with INSURER_FOR_WORK_LOOSE_MIN_CREDITS eligible insurer credits.
_SERVICE_TRADES_LOOSE = tuple(
    (label, re.compile(rf"(?<![A-Z])(?:{words})(?![A-Z])")) for label, words in (
        ("insurance agency", r"AGENCY|AGENCIES|AGCY|BROKERS?|BROKERAGE|COURTIERS?"),
        ("clinic", r"HEALTH|VISION|WELLNESS|SPEECH|OCCUPATIONAL|IMAGING|COUNSEL\w*"),
        ("repair shop", r"TOWING|RESTORATION|ROOFING|MITIGATION"),
    )
)
#: Q2: each ground in words, which the released row's reason names (never the payer's words).
_INSURER_FOR_WORK_GROUND_WORDS = {
    "service_form": "the row prints the form an insurer pays a repair shop, an agency or a provider with",
    "same_insurer_3_in_31_days": "the same insurer pays the business three or more times within 31 days",
    "insurer_service_statement": (
        "another insurer pays the business three or more times within 31 days in the statement"
    ),
}


def _holder_service_trade(
    record: TransactionClassification, receiver_holders: Sequence[str] = (), eligible_count: int = 0,
) -> tuple[str, str] | None:
    """Q2 (owner ruling 2026-10-02): the trade (label, word) a holder name reads: the first strict word
    (_SERVICE_TRADES) on the holder's names (_holder_names), R2-B04's other business names (_holder_strip_names) and
    the statement's receiver-field holder names, in that order; only on a statement with
    INSURER_FOR_WORK_LOOSE_MIN_CREDITS eligible insurer credits or more (`eligible_count`), the first loose word; or
    None."""
    classifier = _classifier()
    names = [
        printed for printed in (
            classifier.account_name_text(name)
            for name in (*_holder_names(record), *_holder_strip_names(record), *receiver_holders) if name
        ) if printed
    ]
    tables = [_SERVICE_TRADES]
    if eligible_count >= INSURER_FOR_WORK_LOOSE_MIN_CREDITS:
        tables.append(_SERVICE_TRADES_LOOSE)
    for table in tables:
        for name in names:
            for label, pattern in table:
                found = pattern.search(name)
                if found is not None:
                    return label, found.group(0)
    return None


def _holder_provider(record: TransactionClassification, receiver_holders: Sequence[str] = ()) -> bool:
    """Audit round 3, R3-B13 (R3-10; the underwriter's Q2 of 2026-10-02, "Medical claim payments to providers keep
    counting as today"): the holder's trade, the first _holder_service_trade reads with its strict and its loose words
    (INSURER_FOR_WORK_LOOSE_MIN_CREDITS), is a clinic or a pharmacy (_PROVIDER_TRADES): a provider's insurer credit that
    prints workers' compensation or a plain BENEFIT(S) wording (_INSURER_NON_PROVIDER_BENEFIT) is paid for treatment.
    R3-B13 review round 1 (finding 1, the brief's reading): a name whose first trade is a repair shop or an insurance
    agency is no provider, whatever clinic or pharmacy word it also prints ('CONTOSO HEALTH INSURANCE AGENCY LLC',
    'CONTOSO COLLISION DOCTORS LLC')."""
    trade = _holder_service_trade(record, receiver_holders, INSURER_FOR_WORK_LOOSE_MIN_CREDITS)
    return trade is not None and trade[0] in _PROVIDER_TRADES


def _non_provider_benefit(own: str, purpose: str) -> bool:
    """Audit round 3, R3-B13 (R3-10): workers' compensation or a plain BENEFIT(S) wording
    (_INSURER_NON_PROVIDER_BENEFIT) on the purpose, or on the payer region read without the holder's names (`own`).
    R3-B13 review round 1 (finding 2): on the payer region a plain BENEFIT(S) or BNFT followed by an insurer word or
    spelling or a legal form is the carrier's name (_INSURER_PLAIN_BENEFIT, _INSURER_NAME_FORM: 'MUTUAL BENEFIT INS CO
    DES:DRP PAYMENT' is no benefit), while one printed after the name (a layout with no entry field: 'SAMPLE MUTUAL INS
    BENEFIT PMT') and workers' compensation anywhere (WC, WORKERS COMP, WORK COMP: a workers' compensation carrier) are
    read."""
    if _INSURER_NON_PROVIDER_BENEFIT.search(purpose):
        return True
    for found in _INSURER_NON_PROVIDER_BENEFIT.finditer(own):
        if not _INSURER_PLAIN_BENEFIT.fullmatch(found.group(0)):
            return True
        tail = own[found.end():]
        if not (_INSURER_NAME.search(tail) or _INSURER_SPELLINGS.search(tail) or _INSURER_NAME_FORM.search(tail)):
            return True
    return False


def _record_day(record: TransactionClassification) -> _date | None:
    """A record's posted day, or None where its date reads as none (an undated credit)."""
    try:
        return _date.fromisoformat(str(record.date or "")[:10])
    except ValueError:
        return None


def _insurer_key_frequent(days: Sequence[_date | None]) -> bool:
    """Q2's threshold (§8.10): some INSURER_FOR_WORK_MIN_CREDITS of one key's eligible credits fall within an inclusive
    span of INSURER_FOR_WORK_WINDOW_DAYS days; an undated credit counts as inside any span."""
    need = INSURER_FOR_WORK_MIN_CREDITS - sum(1 for day in days if day is None)
    if need <= 0:
        return True
    known = sorted(day for day in days if day is not None)
    span = INSURER_FOR_WORK_WINDOW_DAYS - 1
    return any((known[i + need - 1] - known[i]).days <= span for i in range(len(known) - need + 1))


def _insurer_for_work(
    records: Sequence[TransactionClassification],
    credits: Sequence[int],
    texts: dict[int, str],
    receiver_holders: Sequence[str] = (),
) -> dict[int, str]:
    """Owner ruling 2026-10-02 (the underwriter's Q2, "True revenue", option 2; §8.1): the insurer credits pass 7
    releases as the business's work, {index: ground}. A credit is eligible when the insurer reading
    (insurer_payer_reading, on the payer region the facts read) is for work; no registry, payout entity, factoring payee
    or financier claimed it (_claimed, _factoring_payout_payer: the insurer-name hold's convention); no not-for-work word
    prints on the payer (without the holder's names) or the purpose (_INSURER_NOT_FOR_WORK, unless a commission form
    prints there too); it is $1 or more, its direction agrees, and it is an unverified deposit or the insurance rule's
    non_revenue (insurance_provider_credit_exclusion): a row a classifier rule verified is left alone. Audit round 3,
    R3-B13 (R3-10): nor a personal benefit's word, unless a commission form prints in the same words: a disability
    benefit by another name or life-policy money on the payer or the purpose (_INSURER_PERSONAL_BENEFIT), long-term
    disability's LTD benefit on the purpose alone (_INSURER_LTD_BENEFIT: on the payer LTD is a legal form), and
    workers' compensation or a plain BENEFIT(S) wording on the payer or the purpose (_INSURER_NON_PROVIDER_BENEFIT,
    _non_provider_benefit: review round 1, never a benefit word inside the carrier's name) where the holder's first
    trade is no clinic or pharmacy (_holder_provider); a refused credit is no eligible credit, so it never
    counts toward its key's frequency or the loose-trade count. The purpose is a wire's purpose fields
    (_title_purpose_text, never its REF) or the entry fields, read with R2-B12's layout entry (_layout_entry). The
    ground, the first that applies: 'holder_trade:<label>' (_holder_service_trade, with the statement's eligible count),
    'service_form' (_INSURER_SERVICE_FORM on the payer and the purpose, or the classifier's own customer-payment
    wording on the row before its receiver fields, for layouts that print it before the payer or in a wire's REF, which
    Chase's book transfer and Santander print the purpose in: R3-B13, R3-58), 'same_insurer_3_in_31_days' (the
    reading's key frequent, _insurer_key_frequent: the registry's or the
    brand's entity, so one carrier is one key however it prints), and, only with the owner's switch
    INSURER_FOR_WORK_STATEMENT_ARM on, 'insurer_service_statement' (any key of the statement frequent). A credit with no
    ground is not released: a listed insurer's stays non_revenue, any other the insurer holds keep."""
    classifier = _classifier()
    eligible: dict[int, InsurerReading] = {}
    forms: dict[int, bool] = {}
    for index in credits:
        record, text = records[index], texts[index]
        if not (
            record.revenue_classification == "unverified_deposit"
            or (
                record.revenue_classification == "non_revenue"
                and record.revenue_match_method == "insurance_provider_credit_exclusion"
            )
        ):
            continue
        if (
            record.revenue_match_method == "direction_conflict" or not record.direction_consistent
            or _under_micro_floor(record)
        ):
            continue
        region = _facts_region(text, _channel(text, record.bank), record.bank)
        if _claimed(record, text) or _factoring_payout_payer(region, text):
            continue
        entry = classifier.entry_fields(text)
        reading = insurer_payer_reading(record, text, region, entry, receiver_holders)
        if reading is None or not reading.for_work:
            continue
        own = _insurer_own_region(record, region, receiver_holders)
        if classifier._is_wire_row(text):
            purpose = _title_purpose_text(text)
        else:
            # Audit round 2, R2-B12: the layout's entry (Bank of America's DES, Chase's CO ENTRY DESCR) through its
            # helper, beside entry_fields' other fields (PNC's entry, a transfer's memo).
            purpose = " ".join(part for part in (_layout_entry(text), entry) if part)
        words = f"{own} {purpose}"
        # Audit round 3, R3-B13 (R3-10): the personal-benefit words refuse as the not-for-work words do; the commission
        # form printed in the same words still releases.
        if not _INSURER_COMMISSION_FORM.search(words) and (
            _INSURER_NOT_FOR_WORK.search(words)
            or _INSURER_PERSONAL_BENEFIT.search(words)
            or _INSURER_LTD_BENEFIT.search(purpose)
            or (_non_provider_benefit(own, purpose) and not _holder_provider(record, receiver_holders))
        ):
            continue
        eligible[index] = reading
        forms[index] = bool(
            _INSURER_SERVICE_FORM.search(words)
            or classifier._INSURER_CUSTOMER_PAYMENT.search(classifier._before_receiver(text))
        )
    days: dict[str, list[_date | None]] = {}
    for index, reading in eligible.items():
        days.setdefault(reading.key, []).append(_record_day(records[index]))
    frequent = {key for key, found in days.items() if _insurer_key_frequent(found)}
    grounds: dict[int, str] = {}
    for index, reading in eligible.items():
        trade = _holder_service_trade(records[index], receiver_holders, len(eligible))
        if trade is not None:
            grounds[index] = f"holder_trade:{trade[0]}"
        elif forms[index]:
            grounds[index] = "service_form"
        elif reading.key in frequent:
            grounds[index] = "same_insurer_3_in_31_days"
        elif INSURER_FOR_WORK_STATEMENT_ARM and frequent:
            grounds[index] = "insurer_service_statement"
    return grounds


def _insurer_for_work_reason(ground: str) -> str:
    """The released row's reason: the ground in words, never the payer's (privacy)."""
    if ground.startswith("holder_trade:"):
        label = ground.split(":", 1)[1]
        article = "an" if label[:1] in "aeiou" else "a"
        words = f"the holder's name reads {article} {label}"
    else:
        words = _INSURER_FOR_WORK_GROUND_WORDS[ground]
    # The ruling is named without its date: no year literal outside date parsing (test_no_statement_hardcodes).
    return (
        f"An insurer pays the business for its work ({words}): counted and flagged, never verified (the owner's "
        "ruling on the underwriter's Q2)."
    )


def credit_facts(
    record: TransactionClassification,
    text: str,
    *,
    debits: CounterDebits,
    receiver_holders: tuple[str, ...] = (),
    business: bool = False,
    disbursers: frozenset[tuple[str, ...]] = frozenset(),
    lessor: bool = False,
    zelle_true_revenue: bool = False,
) -> CreditFacts:
    """§8.1 to §8.9: one posted credit's payer facts, including the first hold of §8.10's order 2 to 11. The payer
    region, name, key and entry fields are the 5.5 readers' (payer_region, payer_name, _payer_key, entry_fields). A
    person-to-person sender printed without FROM (S4.2 review I7) is read after its rail for Q4's two holds only: the
    holder test and the round-sum repeat (its key). So is the counterparty of a named transfer printed without FROM
    (T13, S4.2 fix round 5: _named_transfer_sender), which the FROM form's payer region reads. Every other hold reads
    the payer region, so such a row's financing root is still read on the whole row. A3-G refinement: on the wire
    channel a region of bare channel words (_BARE_CHANNEL_WORDS: 'WIRE') names no sender; `receiver_holders` are the
    holder's names the statement's own receiver fields print (_receiver_holder_names), read by the holder hold only.
    Audit B7: `business` is the statement's _business_shape, which the direct-deposit words read (I09), and
    `disbursers` the statement's _recurring_disbursers, whose disbursement entry is no non-sale purpose (I18). Owner
    ruling 2026-10-02 (the underwriter's Q9; R2-OW09): on an unverified credit nothing claimed, the release of T4's
    financing-root hold (finance_named_release, `lessor` the statement's _lessor_business) lifts that root arm alone in
    _first_hold (`released`); CreditFacts.q9 carries its reason only where no hold names the row then. The owner's
    amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): `zelle_true_revenue` is the counted reading, in which a
    builder's Zelle draw is a progress draw (construction_progress_draw); nothing else here reads it."""
    classifier = _classifier()
    channel = _channel(text, record.bank)
    region = _facts_region(text, channel, record.bank)
    # Audit round 2, R2-B11 (R09 part A): a TD Canada Trust e-Transfer prints a per-transfer code where a sender would
    # stand, which the pass's text no longer prints (without_transfer_code): the row reads no sender and no key.
    sender, holder_sender = (
        _p2p_sender_readings(text)
        if not region and channel == "person_to_person" and _transfer_code(record) is None else ("", "")
    )
    name = classifier.payer_name(region)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    # A3-H review 2: a factor the registry names claims its row as a factoring payee does (only the insurer,
    # possible-return, pay and benefit holds read it), so its trade name's financing word holds nothing.
    factor = _factoring_payout_payer(region, text)
    # Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's merchant payout, which _claimed claims too.
    financier = _customer_financier(record, text)
    claimed = _claimed(record, text) or factor
    wire_n1 = classifier._is_wire_row(text)
    # Audit B5 (I37): TD Canada Trust's trailing CPA code is an electronic-payment form.
    electronic = bool(classifier._ELECTRONIC_PAYMENT_FORM.search(row)) or cpa_payment_code(row, record.bank)
    # §8.5 (S4.2 review M2): Q5 reads a healthcare payer on an incoming wire too; Q6 on an electronic-payment form.
    healthcare = healthcare_payer(region) and (wire_n1 or electronic)
    public = government_payer(public_region(text))
    transfer_row, transfer_words, no_counterparty = _transfer_reading(record, text, channel, region)
    if not region and not sender and transfer_row and transfer_words and re.search(r"\bFROM\b", row) is None:
        # T13 (S4.2 fix round 5): a named transfer printed without FROM takes the same two holds.
        sender = holder_sender = _named_transfer_sender(text)
    disbursing = bool(region) and classifier._payer_key(region) in disbursers
    # Owner ruling 2026-10-02 (the underwriter's Q11 (a)): a builder's progress draw, read only on a named payer that no
    # registry, payout entity, factor or financier claimed.
    progress_draw = not claimed and construction_progress_draw(
        text, region, _holder(record), also=_holder_strip_names(record), zelle_true_revenue=zelle_true_revenue,
    )
    # Owner ruling 2026-10-02 (the underwriter's Q9, "Keep them as true revenue"; R2-OW09): T4's root arm lifted for a
    # finance-named customer paying an invoice, a lessor's rent or a lender paying for services, on an unverified credit
    # nothing claimed (finance_named_release); every other financing arm and every later hold still read the row.
    release = (
        finance_named_release(record, text, region=region, entry=entry, debits=debits, lessor=lessor)
        if record.revenue_classification == "unverified_deposit" and not claimed else None
    )
    hold_reading = {
        "region": region, "entry": entry, "claimed": claimed, "debits": debits, "sender": sender,
        "holder_sender": holder_sender, "receiver_holders": receiver_holders, "wire": channel == "wire",
        "business": business, "disbursing": disbursing, "progress_draw": progress_draw,
        "released": release is not None,
    }
    hold = _first_hold(record, text, **hold_reading)
    # Owner ruling 2026-10-02 (Q11 (b); R2-OW06 review round 1): IAA's insurer-name hold reads the auction's own name;
    # the hold after it, which keeps an IAA seller payout held where any other hold names it.
    past_insurer_name = (
        _first_hold(record, text, **hold_reading, insurer_name=False)
        if hold == "insurer_named_payer" and asset_sale_platform(region, text) == _IAA else None
    )
    # Audit round 2, R2-B04 (R41): the holder's own push, read on the row alone, as _first_hold reads it.
    self_own = not claimed and self_originated(text, region, record.bank)
    # Audit round 3, R3-B10 review round 2 (finding 1): the bare settlement word alone lifted the row from the own-push
    # guard, or an unverified credit from the pass-7 holder hold: the reading with B9's settlement words alone holds it
    # as holder_name, the row's own reading does not. Read only where the row prints the word somewhere.
    bare = not claimed and _HOLDER_NAMED_SETTLEMENT_ENTRY.search(text) is not None
    settlement_released = bare and (
        (not self_own and self_originated(text, region, record.bank, bare_settlement=False))
        or (
            record.revenue_classification == "unverified_deposit" and hold != "holder_name"
            and _first_hold(record, text, **hold_reading, bare_settlement=False) == "holder_name"
        )
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
        electronic=electronic,
        # An investment word an accounts-payable row spared from the holds (S4.2 fix measurement) is no proof either:
        # §7.5's remittance veto reads it, so Q5 and Q6 never verify the row.
        refused_word=bool(
            _VERIFICATION_ONLY.search(entry) or _VERIFICATION_ONLY.search(region)
            or _ENTRY_VERIFICATION_ONLY.search(entry) or _INVESTMENT_PURPOSE.search(row)
            # A3-H: a healthcare, insurer or health-plan payer's premium-coded entry is no claim payment (Q6c).
            or _premium_coded(text, region)
            # Audit round 2, R2-B12 (R17): a recurring disbursement entry B7's I18 spare dropped from the non-sale
            # reading counts, never proves (§8.6, as an unregistered payer's SETTLEMENT).
            or (disbursing and _disbursement_entry(text, region))
            # Audit round 2, R2-B12 review round 2 (R37): a legal, gambling or owner-money word only the trade-name
            # reader's purpose arm spared counts, never proves (the hold's own text, without the holder's names).
            or purpose_trade_name(
                text, _without_holder_name(_hold_text(text), _holder(record), also=_holder_strip_names(record)),
                region,
            )
            # Audit round 3, R3-B10 review round 2 (finding 1): a settlement the bare word alone released, wherever
            # the word prints (an ID field, an originator's tail, digits glued on), counts, never proves (§8.6).
            or settlement_released
        ),
        round_sum=classifier.is_round_sum(record.amount),
        consumer_entry=consumer_entry(text, _holder(record)),
        transfer_no_counterparty=no_counterparty,
        account_designation=transfer_row and bool(transfer_words) and _account_designation(row, record.bank),
        factor=factor,
        financier=financier,
        # Audit round 2, R2-B03 (R05): a payer region that names only a bank names no customer.
        bank_only=_bank_only_payer(region, entry, record.bank, row=row),
        self_own=self_own,
        progress_draw=progress_draw,
        hold_past_insurer_name=past_insurer_name,
        # Q9 (R2-OW09): the release's reason where it took effect (no hold names the row).
        q9=release if hold is None else None,
        settlement_released=settlement_released,
    )


def _first_hold(
    record: TransactionClassification,
    text: str,
    *,
    region: str,
    entry: str,
    claimed: bool,
    debits: CounterDebits,
    sender: str = "",
    holder_sender: str = "",
    receiver_holders: tuple[str, ...] = (),
    wire: bool = False,
    business: bool = False,
    disbursing: bool = False,
    progress_draw: bool = False,
    insurer_name: bool = True,
    released: bool = False,
    bare_settlement: bool = True,
) -> str | None:
    """§8.1 in §8.10's order (2 to 11): the first hold that names the row, or None. Audit B5: a bank's own wire is
    read on every row pass 7's wire channel reads (`wire`, I14, I23), and TD Canada Trust's payroll-deposit code is pay
    wording (I37). A row the registry, a payout
    entity or a factoring payee claimed takes only the insurer, possible-return, pay and benefit holds; a registry row
    that prints a financing word is held as financing_named_payer (review C2). The holder test also reads a
    person-to-person sender printed without FROM (`sender`, Q4; S4.2 review I7), and its holder-test reading, which
    keeps a layout word inside the name (`holder_sender`, S4.2 final review M7); or a named transfer's counterparty
    printed without FROM (T13, S4.2 fix round 5), both readings one. Audit B4: the counter-debit holds read the
    statement's debits by kind (debited_as_lender, also_debited), and a payroll provider's tax-service credit no
    debit holds is non_sale_purpose (I56), on a claimed row too (the pay holds' convention).

    Audit B7: the possible-return, financing-root, pay, personal-income and non-sale tests read the row without the
    holder's own name runs (I47, _without_holder_name); the direct-deposit words are pay wording only with a sign of a
    person's pay (I09, _direct_deposit_pay, `business` the statement's _business_shape); and the dealer-word hold
    never reads a named non-lender's wire purpose (I36, _dealer_word_lender). Owner ruling 2026-10-02 (the
    underwriter's Q11 (a)): on a builder's progress draw (`progress_draw`) the non-sale test spares DRAW alone. R2-OW06
    review round 1: with `insurer_name` False the insurer-name hold is passed over, so credit_facts reads the hold an IAA
    seller payout would take after it (CreditFacts.hold_past_insurer_name). Audit I26 (R2-OW07): the insurer-name hold
    reads insurer_payer_reading, every insurer spelling and brand without the holder's names. Owner ruling 2026-10-02
    (the underwriter's Q2): a credit the insurer-for-work release re-stated (INSURER_FOR_WORK_METHOD) takes no
    insurer-name hold, and the non-sale test reads no CLAIM on it; every other hold reads it as before. Owner ruling
    2026-10-02 (the underwriter's Q9; R2-OW09): with `released` (finance_named_release lifted the row) the financing
    hold's root arm (financing_named) is passed over; its other arms keep their order and still hold, and every later
    hold reads the row. Audit round 3, R3-B10 review round 2 (finding 1): with `bare_settlement` False the holder hold
    and the own-push guard read B9's settlement words alone (merchant_settlement), the hold credit_facts compares to
    name a row the bare settlement word alone released (CreditFacts.settlement_released)."""
    classifier = _classifier()
    # Audit round 2, R2-B04 (R40): the I47 strip reads the holder's other business names too (_holder_strip_names).
    also = _holder_strip_names(record)
    row = _without_holder_name(_hold_text(text), _holder(record), also=also)
    before = _without_holder_name(classifier._before_receiver(text), _holder(record), also=also)
    if record.revenue_match_method == "insurer_customer_payment":
        return "insurer_payer"
    # Audit I26 (by Q6 of 2026-09-28 and the underwriter's Q2 (2026-10-02) option's "a one-off claim ... stays out";
    # R2-OW07): an insurer however the bank spells it (insurer_payer_reading: the spelled words, the INS abbreviation,
    # the cut forms, LOSS PMT, SUBRO, the brand table, CLAIM), read without the holder's names; a listed insurer's
    # reading is the insurance rule's (non_revenue), never this hold.
    # Owner ruling 2026-10-02 (the underwriter's Q2): a credit the insurer-for-work release re-stated
    # (INSURER_FOR_WORK_METHOD) is no insurer-name hold; every later hold still reads it.
    if insurer_name and not claimed and region and record.revenue_match_method != INSURER_FOR_WORK_METHOD:
        reading = insurer_payer_reading(record, text, region, entry, receiver_holders)
        if reading is not None and reading.kind != "registry":
            return "insurer_named_payer"
    if record.revenue_match_method != "reversal_cancellation_exclusion" and (
        _POSSIBLE_RETURN.search(row)
        or (
            _CARD_CREDIT_LABEL.search(text) and record.revenue_classification != "verified_revenue"
            # Audit B3 (I11): a processor's instant payout, released beside its ACH activity, is counted.
            and record.revenue_match_method != PROCESSOR_CARD_PAYOUT_METHOD
        )
        # Audit B3 (I04): a card credit printed first, with no push or person-to-person rail.
        or (_leading_card_credit(text) and record.revenue_classification != "verified_revenue")
    ):
        return "possible_return"
    if not claimed and (
        # Owner ruling 2026-10-02 (the underwriter's Q9; R2-OW09): the root arm alone is lifted on a released row.
        (financing_named(text, region, entry, _holder(record), bank=record.bank, also=also) and not released)
        or registry_financing(record, text)
        # §8.7: a listed lender's or a dealer-funding word's row that Q7 did not verify, and a lone credit union's.
        # Audit B7 (I36): never on a named non-lender's wire purpose (_dealer_word_lender).
        or (_dealer_funding_payer(text) is not None and record.revenue_match_method != "auto_lender_dealer_funding")
        or (
            DEALER_FUNDING_WORDS.search(row) and record.revenue_match_method != "auto_lender_dealer_funding"
            and _dealer_word_lender(text, region)
        )
        or record.revenue_match_method == "credit_union_vehicle_purchase"
        # A3-G: a wire a bank originates on its own behalf.
        or _bank_originated_wire(text, region, wire=wire)
        # Audit B6 (I23): a bank that lends to small businesses, named as the payer.
        or lending_bank_payer(text, region)
    ):
        return "financing_named_payer"
    # Audit round 2, R2-B02 (R02): RBC's French label before the holder's own chequing or savings account (T13), which
    # the counter-debit holds no longer read by its label word; review round 1: a credit from an account designation
    # printed with no transfer word ('BKOFAMERICA BC <date> <ref> FR SAV'), which only a debit sharing the bank's word
    # held before.
    if not claimed and (
        _FRENCH_OWN_ACCOUNT_PAYMENT.match(classifier._before_receiver(text))
        or _FROM_ACCOUNT_ABBREVIATION.search(classifier._before_receiver(text))
    ):
        return "transfer_account_designation"
    counter = counter_credit(record, text, region)
    if not claimed and debited_as_lender(
        counter, debits, prefix=record.revenue_classification == "unverified_deposit"
    ):
        return "payer_debited_as_lender"
    # Audit B9 (I13): a processor's or a platform's settlement or payout under the merchant's own name is never the
    # holder's own money (merchant_settlement). Review round 1: read outside the holder's own names, never on a wire or
    # a person-to-person rail; the holder's names include an account-name field naming a holder beside the parser's
    # (_holder_names), and the row's layout sets where another payer's receiver block can print
    # (holder_receiver_block). Audit round 2, R2-B02 (R18): nor a platform's payout known by its payout id
    # (processor_payout), whatever descriptor it prints. Audit round 2, R2-B04 (R04 part 1): nor a processor's, a
    # platform's or a franchisor's credit printing the merchant's own name (platform_credit).
    names = _holder_names(record)
    block = classifier.holder_receiver_block(text, record.bank)
    if not claimed and (
        (region or sender)
        and not merchant_settlement(text, (*names, *receiver_holders), bare_settlement=bare_settlement)
        and not processor_payout(text) and not platform_credit(text, region, (*names, *receiver_holders)) and (
            any(classifier.holder_named(region or sender, name, receiver_block=block) for name in names)
            or (
                not region and holder_sender != sender
                and any(classifier.holder_named(holder_sender, name, receiver_block=block) for name in names)
            )
            # A3-G refinement: the holder's names the statement's own receiver fields print (the hold only), on a
            # wire, a book transfer or a transfer or person-to-person row that no earlier rule verified
            # (_receiver_alias_reads).
            or (
                receiver_holders and _receiver_alias_reads(record, text)
                and any(_receiver_holder_named(region or sender, holder) for holder in receiver_holders)
            )
        )
        # Audit B9 (I13): the row's own originator is its receiver field, or a wire's sender its beneficiary.
        or self_originated(text, region, record.bank, bare_settlement=bare_settlement)
    ):
        return "holder_name"
    if _pay_wording(before, record.bank, text=text, account_name=_holder(record), business=business):
        return "payroll_or_salary"
    # Audit round 2, R2-B12 (R42): the statement's bank, so TD Canada Trust's cut payer name is read as a name.
    if _personal_income(text, before, record.bank):
        return "personal_income"
    if not claimed and non_sale_purpose(
        text, region, bank=record.bank, account_name=_holder(record), disbursing=disbursing, also=also,
        progress_draw=progress_draw, insurer_work=record.revenue_match_method == INSURER_FOR_WORK_METHOD,
    ):
        return "non_sale_purpose"
    if not claimed and (
        record.revenue_match_method == "payer_remittance_with_counter_debit" or also_debited(counter, debits)
    ):
        return "payer_also_debited"
    if payroll_tax_credit(text, region):
        return "non_sale_purpose"
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


#: Owner ruling 2026-10-02 (the underwriter's Q10, "Hold every deposit into an account titled "premium trust""; §5.3,
#: §8.10; audit round 2, R2-OW11): the held reason of a credit into an account whose printed title reads PREMIUM TRUST,
#: and the method and rule a verified one leaves verification with.
PREMIUM_TRUST_REASON = "premium_trust_account"
PREMIUM_TRUST_METHOD = "premium_trust_account"
_PREMIUM_TRUST_RULE = "premium_trust_account_title"
#: R2-OW11: the kind words a title may print after the premium-trust words (an account, a fund, a product:
#: holder_name.PREMIUM_TRUST_KIND, imported above as _PREMIUM_TRUST_KIND), and the account and product words alone (no
#: FUND or FUNDS), which the separator form needs. Audit round 3, R3-B11 (R3-65): a product adjective may print before
#: a kind word ('PREMIUM TRUST BUSINESS CHECKING'; holder_name.PREMIUM_TRUST_ADJECTIVE); an adjective alone is never a
#: kind word ('PREMIUM TRUST BUSINESS' is no title). The reference a title may print is
#: holder_name.PREMIUM_TRUST_REFERENCE (imported as _PREMIUM_TRUST_REFERENCE): an account number, masked or not, after
#: #, NO, NUMBER, ACCOUNT, ACCT or A/C, in or out of parentheses; a roman numeral; or a parenthesised code of up to four
#: letters or digits. Since R3-B11 review round 1 (finding 2) the three live in holder_name, so a holder line's contact
#: designation reads the same title.
_PREMIUM_TRUST_ACCOUNT_KIND = (
    rf"{_PREMIUM_TRUST_ADJECTIVE}"
    r"(?:ACCOUNT|ACCT|ACCNT|A/C|CHECKING|CHK|DDA|SAVINGS|SAV|SHARE|MMA|MONEY\s+MARKET)\.?"
)
_PREMIUM_TRUST_TITLE = rf"(?P<title>{PREMIUM_TRUST_WORDS}(?:\s+{_PREMIUM_TRUST_KIND})*)"
#: R2-OW11: the three title forms. The title at the field's end (kind words, a reference and punctuation may follow);
#: the words followed by an account word; the words and one or more account or product words, a reference allowed, then
#: a separator (' - ', an en or em dash, ':' or '(') and anything ('PREMIUM TRUST ACCOUNT - NORTHWIND AGENCY LLC').
_PREMIUM_TRUST_AT_END = re.compile(rf"{_PREMIUM_TRUST_TITLE}(?:[\s\-:#,]*{_PREMIUM_TRUST_REFERENCE})?[\s.,;:\-)]*$")
_PREMIUM_TRUST_WITH_ACCOUNT = re.compile(
    rf"(?P<title>{PREMIUM_TRUST_WORDS}\s+{_PREMIUM_TRUST_ADJECTIVE}(?:ACCOUNT|ACCT|ACCNT|A/C)\.?)(?![A-Z])"
)
#: Audit round 3, R3-B11 (R3-65): the for-benefit form, the words and an account word before FBO, F/B/O, OF or FOR
#: and a name ('PREMIUM TRUST ACCOUNT FBO NORTHWIND AGENCY LLC'), read on an account name or a holder name even when
#: the field ends in a legal form (the form is the beneficiary's). Review round 1 (finding 3): a product adjective may
#: print before the account word, as in the account-word form ('PREMIUM TRUST BUSINESS ACCOUNT FBO NORTHWIND LLC').
_PREMIUM_TRUST_FOR_BENEFIT = re.compile(
    rf"(?P<title>{PREMIUM_TRUST_WORDS}\s+{_PREMIUM_TRUST_ADJECTIVE}(?:ACCOUNT|ACCT|ACCNT|A/C)\.?)"
    r"\s+(?:FBO|F/B/O|F B O|OF|FOR)\s+[A-Z]"
)
_PREMIUM_TRUST_SEPARATED = re.compile(
    rf"(?P<title>{PREMIUM_TRUST_WORDS}(?:\s+{_PREMIUM_TRUST_ACCOUNT_KIND})+)(?:[\s\-:#,]*{_PREMIUM_TRUST_REFERENCE})?"
    r"\s*(?:\s-\s|\s?[–—]\s?|:|\()\s*\S"
)
#: R2-OW11: a field that ends in a legal form (the holder readers' LEGAL_FORMS), which refuses the account-word form
#: on an account name or a holder name ('PREMIUM TRUST ACCOUNT LLC' is a company).
_PREMIUM_TRUST_LEGAL_LAST = re.compile(r"\b(?:" + "|".join(sorted(_HOLDER_LEGAL_FORMS)) + r")\.?\s*$")


def _premium_trust_field(field: str | None) -> str:
    """R2-OW11: a statement field as the premium-trust rule reads it: upper case, its whitespace runs collapsed, L.L.C.
    read as LLC."""
    return " ".join(str(field or "").upper().replace("L.L.C.", "LLC").split())


def _premium_trust_words(match: re.Match[str]) -> str:
    """R2-OW11: the title words a form matched, its dots dropped and its blanks collapsed."""
    return " ".join(match.group("title").replace(".", " ").split())


def premium_trust_title(account_title: str | None, account_name: str | None, holder_name: str | None) -> str | None:
    """Owner ruling 2026-10-02 (the underwriter's Q10, "Hold every deposit into an account titled "premium trust"";
    §8.10, §9.1; audit round 2, R2-OW11): the premium-trust title a statement prints, or None. Read on the statement's
    own fields, never on a row (a payer that prints the words makes no title). The bank's designation
    (`Statement.account_title`, R2-OW10) reads in any of the three title forms: the title at the field's end, the
    words followed by an account word, or the words and an account or product word before a separator; never the
    words anywhere ('PREMIUM TRUST ROOFING', a trade name the holder reader dropped after a legal form, is no title).
    Then the account name, then the holder's name: the title at the end, the account-word form only when the field does
    not end in a legal form ('PREMIUM TRUST ACCOUNT LLC' is a company), the for-benefit form even when it does ('PREMIUM
    TRUST ACCOUNT FBO NORTHWIND AGENCY LLC'; audit round 3, R3-B11: R3-65), and the separator form even when it does
    ('PREMIUM TRUST ACCOUNT - NORTHWIND INSURANCE AGENCY LLC'). Audit round 3, R3-B11 (R3-65): a product adjective
    (BUSINESS, ANALYZED, COMMERCIAL) may print before a kind word or the account word, and FUND or FUNDS between the
    words ('PREMIUM FUND TRUST ACCOUNT'). Returns the matched title words, dots dropped.
    Recorded false negatives (each overstates True: the trust account's deposits stay counted): 'PREM. TR. ACCT.', a
    bare title before a separator ('PREMIUM TRUST - CONTOSO AGENCY LLC'), 'PREMIUM TRUST OPERATING', and a title only a
    statement whose parser reads no holder line prints (R3-30: no account title is published there); a holder line's
    contact that prints a name before the words ('CARE OF NORTHWIND PREMIUM TRUST ACCOUNT') or any other word after the
    designation ('ATTN: PREMIUM TRUST ACCOUNT - NORTHWIND'), which the holder readers publish as no title (audit round
    3, R3-B11 review round 1, finding 2).
    Recorded over-reads (each understates True, held and reviewable): a trade name that prints the words and an account
    word ('PREMIUM TRUST ACCOUNT SERVICES', 'PREMIUM TRUST ACCT MGMT', 'NORTHWIND PREMIUM TRUST ACCOUNT SERVICES' as a
    holder with no legal form, a company named 'PREMIUM TRUST ACCOUNT OF <place> LLC', a product adjective before the
    account word too: 'PREMIUM TRUST BUSINESS ACCOUNT OF <place> LLC', review round 1, finding 3)."""
    text = _premium_trust_field(account_title)
    if text:
        for form in (_PREMIUM_TRUST_AT_END, _PREMIUM_TRUST_WITH_ACCOUNT, _PREMIUM_TRUST_SEPARATED):
            if (found := form.search(text)) is not None:
                return _premium_trust_words(found)
    for field in (account_name, holder_name):
        text = _premium_trust_field(field)
        if not text:
            continue
        if (found := _PREMIUM_TRUST_AT_END.search(text)) is not None:
            return _premium_trust_words(found)
        if not _PREMIUM_TRUST_LEGAL_LAST.search(text) and (found := _PREMIUM_TRUST_WITH_ACCOUNT.search(text)):
            return _premium_trust_words(found)
        if (found := _PREMIUM_TRUST_FOR_BENEFIT.search(text)) is not None:
            return _premium_trust_words(found)
        if (found := _PREMIUM_TRUST_SEPARATED.search(text)) is not None:
            return _premium_trust_words(found)
    return None


def _held_in_premium_trust(record: TransactionClassification, title: str) -> TransactionClassification:
    """Owner ruling 2026-10-02 (the underwriter's Q10; §8.10; R2-OW11), as _held_by_the_floor holds: a credit a rule
    verified or counted, on a statement whose title reads PREMIUM TRUST, held for review as PREMIUM_TRUST_REASON. A
    verified one first leaves verification as a new first state (unverified_deposit, method PREMIUM_TRUST_METHOD,
    pending review, so the analyst may confirm it), its reason naming the rule it overruled; a counted one keeps its
    state, method and rule, and only its tier and reason change."""
    if record.revenue_classification == "verified_revenue":
        # The ruling is named without its date: no year literal outside date parsing (test_no_statement_hardcodes).
        record = _classifier()._replace_revenue_state(
            record,
            "unverified_deposit",
            match_method=PREMIUM_TRUST_METHOD,
            matched_rule=_PREMIUM_TRUST_RULE,
            confidence_score=0.40,
            reason=(
                f"A deposit into an account titled {title}: an insurance agency's premium trust account holds its "
                "insureds' premiums, not the agency's revenue (the owner's ruling on the underwriter's Q10). The rule "
                f"that read it ({record.revenue_match_method}) is overruled, and it is held for review."
            ),
            context_signals=(*record.revenue_context_signals, PREMIUM_TRUST_METHOD),
            related_transaction=record.revenue_related_transaction,
        )
    return _with_tier(record, "excluded_pending_review", PREMIUM_TRUST_REASON)


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
    return _deferred_reading(text, facts.channel, facts.region, facts.entry)


def _deferred_reading(text: str, channel: str, region: str, entry: str) -> bool:
    """§15 (_deferred_source) on the row's channel, payer region and entry fields."""
    classifier = _classifier()
    if _SECTION_15_DEFERRED_PAYERS.search(classifier._without_receiver_value(text)):
        return True
    return (
        channel != "wire" and healthcare_payer(region) and not entry
        and _BARE_X12_TRACE.search(text) is not None
    )


def _never_q5_or_q6(record: TransactionClassification, text: str, facts: CreditFacts) -> bool:
    """The rows Q5 and Q6 never verify and never count toward a repeat, whatever their holds: a direction conflict
    (§6.1 step 2, §7.0: never lifted by any pass; S4.2 review C1), a credit under $1 (§7.0, review I3), a row a family
    rule decides alone (review I5), a deferred source (review I6a) and a factoring payer's payout (A3-H). Audit B3
    (I11): and a processor's instant payout released from a card credit (counted, never verified). Owner ruling
    2026-10-02 (Q8): and a lease-to-own or patient financier's merchant payout, or any row that names one of them
    (CUSTOMER_FINANCING_NAMES, read without the receiver field's value). Owner ruling 2026-10-02 (the underwriter's Q11
    (a)): and a builder's progress draw (counted and flagged, never verified). Owner ruling 2026-10-02 (the
    underwriter's Q2): and an insurer's credit released as the business's work (INSURER_FOR_WORK_METHOD). Owner ruling
    2026-10-02 (the underwriter's Q9; R2-OW09): and a credit the financing-root release lifted (CreditFacts.q9). Audit
    round 3, R3-B10 review round 2 (finding 1): and a settlement the bare settlement word alone released from the holder
    hold or the own-push guard (CreditFacts.settlement_released), which never counted toward a repeat while held. Audit
    round 3, R3-B14 (R3-06): and a payout entity's or a financier's credit whose claim the non-sale or financing veto
    lifted (_payout_claim_vetoed), so the holds read it: such a credit is counted, never verified, and where no hold
    reads its word (an abbreviated advance, ADVNC) a payout entity's is counted as payout_credit_entity, as before."""
    return (
        record.revenue_match_method == "direction_conflict"
        or record.revenue_match_method == PROCESSOR_CARD_PAYOUT_METHOD
        or record.revenue_match_method == INSURER_FOR_WORK_METHOD
        or not record.direction_consistent
        or _under_micro_floor(record)
        or _left_to_its_family(text)
        or _deferred_source(text, facts)
        or facts.factor
        or facts.financier is not None
        or _CUSTOMER_FINANCING_NAMES.search(_classifier()._without_receiver_value(text)) is not None
        or facts.progress_draw
        or facts.q9 is not None
        or facts.settlement_released
        or (not facts.claimed and _payout_claim_vetoed(record, text))
    )


def _payout_claim_vetoed(record: TransactionClassification, text: str) -> bool:
    """Audit round 3, R3-B14 (R3-06): a payout entity (_payout_entity) or a lease-to-own or patient financier
    (_customer_financier, read without the veto) names the row, whose claim the non-sale or financing veto lifted
    (_payout_non_sale). Such a credit is never verified by Q5 or Q6 and never counts toward a repeat: the holds read it
    as any payer's row, and where none reads its word (an abbreviated advance: ADVNC, ADVN, ADVC) it is counted, a
    payout entity's as payout_credit_entity, as before the batch."""
    classifier = _classifier()
    if classifier._PAYOUT_NON_SALE_CREDIT.search(classifier._without_receiver_value(text)) is None:
        return False
    if not _payout_non_sale(record, text):
        return False
    return _payout_entity(text) is not None or _customer_financier(record, text, non_sale=False) is not None


def _vetoed_financier(record: TransactionClassification, text: str) -> str | None:
    """Audit round 3, R3-B14 review round 1 (finding 2; Q8's "Keep large one-off lump sums held until sourced"): the
    lease-to-own or patient financier (_customer_financier, read without the veto) whose claim the non-sale or financing
    veto lifted (_payout_non_sale), or None. The lump-sum test reads such a counted credit as that financier's payout,
    as before the veto, so an abbreviated advance (ADVNC, ADVN, ADVC), which no hold reads, is never a way into True
    for a large one-off sum; a payout entity's credit, which no lump-sum test reads, is not one."""
    classifier = _classifier()
    if classifier._PAYOUT_NON_SALE_CREDIT.search(classifier._without_receiver_value(text)) is None:
        return None
    if not _payout_non_sale(record, text):
        return None
    return _customer_financier(record, text, non_sale=False)


def _factoring_payout_payer(region: str, text: str = "") -> bool:
    """§8.9 (A3-H): a freight-factoring payer the registry names for this pass alone (FACTORING_PAYOUT_PAYERS). Its
    credit is the carrier's own invoices paid by the factor: counted and flagged as factoring_payout, never verified by
    any path (A3-H review: _factor_never_verified overrules an earlier rule's verification). A3-H review: read only as
    the payer region (the ACH originator or the wire sender), which is the alias, followed only by company forms: a
    longer name that starts with it ('<alias> FOR PETS LLC') or another payer's purpose citing it names another payer.
    A3-H review 2: the words after the alias (_factor_tail) may also be a company form glued to its last word
    ('<alias>LLC'), a DBA tail, an entry word, a date or a number that falls into the region, and on a B/O field
    (`text`'s originator label) the sender's address: its city, state, ZIP and country (the trust rule's place
    reading)."""
    words = (region or "").split()
    for aliases in FACTORING_PAYOUT_PAYERS.values():
        for alias in aliases:
            head = alias.split()
            if not words or len(words) < len(head) or words[: len(head) - 1] != head[:-1]:
                continue
            last = words[len(head) - 1]
            if last == head[-1]:
                tail = words[len(head):]
            elif last.startswith(head[-1]) and _classifier()._BANK_COMPANY_FORM.fullmatch(last[len(head[-1]):]):
                # A company form glued to the alias's last word ('SOLUTIONSLLC').
                tail = [last[len(head[-1]):], *words[len(head):]]
            else:
                continue
            if _factor_tail(tail, b_o=_b_o_field(text)):
                return True
    return False


#: §8.9 (A3-H review 2): the entry words a layout with no entry field prints into the payer region after its name.
_FACTOR_ENTRY_WORDS = frozenset({"PAYMENT", "PAYMENTS", "PMT", "PMTS", "PYMT"})


def _b_o_field(text: str) -> bool:
    """A3-H review 2: the wire's originator label is B/O (Fedwire, CHIPS, Chase's book transfer), a field that
    prints the sender's address after its name."""
    found = _classifier()._WIRE_ORIGINATOR_LABEL.search(text or "")
    return found is not None and found.group(0).strip() == "B O"


def _factor_tail(tail: Sequence[str], *, b_o: bool) -> bool:
    """§8.9 (A3-H review, review 2): the words after a factor's alias add nothing to its name: company forms (glued or
    spaced), entry words (_FACTOR_ENTRY_WORDS), dates and numbers (reference tokens), then either nothing, a DBA
    tail (the factor's trade name, any words), or, on a B/O field, an address: place words ending in a US state
    code, at most _TRUST_ADDRESS_MAX_WORDS of the address's own, as the personal-trust rule reads one, and never a
    connector word (_FACTOR_CONNECTOR_WORDS: FOR, OF, AND, THE; [A3H-m1])."""
    classifier = _classifier()
    words = list(tail)
    while words and (
        classifier._BANK_COMPANY_FORM.fullmatch(words[0]) or words[0] in _FACTOR_ENTRY_WORDS
        or classifier._is_reference_token(words[0])
    ):
        words.pop(0)
    if not words or words[0] == "DBA":
        return True
    if not b_o:
        return False
    while words and words[-1] in {"US", "USA"}:
        words.pop()
    return (
        bool(words) and words[-1] in _US_STATE_TAIL
        and len(_address_words(words[:-1])) <= _TRUST_ADDRESS_MAX_WORDS
        and not any(_not_a_place_word(word) or word in _FACTOR_CONNECTOR_WORDS for word in words[:-1])
    )


#: [A3H-m1] (final review): a connector word after a factor's alias joins a longer name ('<alias> FOR PETS
#: <city> <state>'), never the sender's address.
_FACTOR_CONNECTOR_WORDS = frozenset({"FOR", "OF", "AND", "THE"})


def asset_sale_platform(region: str, text: str = "") -> str | None:
    """§8.1 (owner ruling 2026-10-02, the underwriter's Q11 (b); audit I45): the equipment auction or car buyer
    (ASSET_SALE_PAYERS) the payer region names as its whole payer name, or None: the alias's words start the region and
    the words after it, a seller's words aside (_ASSET_SALE_TAIL_WORDS: 'CARVANA PAYOUT', 'RITCHIE BROS SELLER PAYOUT'),
    add nothing to its name, as _factor_tail reads a factor's (company forms, entry words, references, a DBA tail, a
    B/O field's address). A longer name that starts with it ('VROOM DELIVERY LLC', 'CARMAX BUSINESS SERVICES LLC',
    'BIG IRON TRUCKING LLC') names another payer; a glued '<alias>LLC' is not read (fail-safe)."""
    words = (region or "").split()
    for entity, aliases in ASSET_SALE_PAYERS.items():
        for alias in aliases:
            head = alias.split()
            if len(words) < len(head) or words[: len(head)] != head:
                continue
            tail = [word for word in words[len(head):] if word not in _ASSET_SALE_TAIL_WORDS]
            if _factor_tail(tail, b_o=_b_o_field(text)):
                return entity
    return None


def asset_sale_reading(
    record: TransactionClassification, text: str, facts: CreditFacts, *, verified: bool = False,
    zelle_true_revenue: bool = False,
) -> str | None:
    """§8.1 (owner ruling 2026-10-02, the underwriter's Q11 (b), "Don't count as true revenue and go straight to
    non-revenue"; audit I45): 'payer' when an equipment auction or a car buyer pays a seller (asset_sale_platform: with
    a seller's word on the row, or, except Copart and IAA, with no service word on the purpose and a holder whose trade
    does not serve the platforms), 'purpose' when the row prints the sale of a truck, trailer, vehicle or equipment
    (_ASSET_SALE_PURPOSE, read outside the payer's own name, R2-B13's _payer_name_proper); or None. A vehicle's or heavy
    equipment's sale reads through an invoice reference (_INVOICE_REFERENCE), so only accounts-payable, vendor or
    payables wording spares it (_vendor_payment); a generic EQUIPMENT or MACHINERY sale keeps the invoice veto, a
    single-row verification and a supplier's holder name. Never a claimed row, a row an insurer-name hold reads unless
    the payer is IAA (its INSURANCE is the auction's name) and no later hold would name it (R2-OW06 review round 1:
    CreditFacts.hold_past_insurer_name), a Zelle row (Q3 of 2026-10-02), a possible return or a refund; nor a printed
    sale with a commission or a fee next to it (review round 1: _ASSET_SALE_COMMISSION_AFTER and _BEFORE, a broker's or
    an agent's earned revenue; audit round 3, R3-B15: R3-59, unless a netting word stands beside it,
    _asset_sale_commission). `verified` is a row an invoice or customer-payment descriptor verified
    (ASSET_SALE_INVOICE_METHODS): only its printed sale is read, never a platform. The pass reads the statement's dealer
    evidence first (_dealer_statement) and applies the reading where the tier would count the row or a verification it
    overrules; a held tier keeps the row held. The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17):
    in the counted reading (`zelle_true_revenue`) a Zelle row is read as any other rail's, so a Zelle truck or
    equipment sale is asset-sale proceeds, as a Venmo one is."""
    classifier = _classifier()
    region = facts.region
    entity = asset_sale_platform(region, text) if region and not verified else None
    # R2-OW06 review round 1: IAA's insurer-name hold yields only where no later hold would name the row.
    if facts.claimed or (
        facts.hold == "insurer_named_payer" and (entity != _IAA or facts.hold_past_insurer_name is not None)
    ):
        return None
    row = _without_holder_name(_hold_text(text), _holder(record), also=_holder_strip_names(record))
    if (
        (not zelle_true_revenue and zelle_deposit(text)) or _POSSIBLE_RETURN.search(row)
        or _ASSET_SALE_REFUND.search(row)
    ):
        return None
    name = _payer_name_proper(text, region) if region and _prints_payer_name_field(text) else ""
    purpose = row.replace(name, " ") if name else row
    holder = classifier.account_name_text(_holder(record)) or ""
    if entity is not None:
        if _vendor_payment(text, row):
            return None
        if _SELLER_WORD.search(row):
            return "payer"
        if (
            entity not in ASSET_SALE_SELLER_WORD_ONLY and _PLATFORM_SERVICE_WORDS.search(purpose) is None
            and _PLATFORM_VENDOR_HOLDER.search(holder) is None
        ):
            return "payer"
        return None
    found = _ASSET_SALE_PURPOSE.search(purpose)
    if found is None:
        return None
    # R2-OW06 review round 1: a commission or a fee next to the sale is earned revenue (_ASSET_SALE_COMMISSION_*);
    # audit round 3, R3-B15 (R3-59): unless a netting word makes it what the proceeds are net of.
    if _asset_sale_commission(purpose[found.end():], purpose[:found.start()]):
        return None
    if _VEHICLE_NOUN_WORD.search(found.group(0)):
        if _vendor_payment(_INVOICE_REFERENCE.sub(" ", text), _INVOICE_REFERENCE.sub(" ", row)):
            return None
        return "purpose"
    if verified or _vendor_payment(text, row) or _SUPPLIER_HOLDER.search(holder):
        return None
    return "purpose"


def _asset_sale_commission(after: str, before: str) -> bool:
    """§8.1 (Q11 (b); R2-OW06 review round 1): a commission or a fee printed right after a printed sale (`after`, the
    purpose after it: _ASSET_SALE_COMMISSION_AFTER) or right before it with at most a connector (`before`, the purpose
    before it: _ASSET_SALE_COMMISSION_BEFORE), a broker's or an agent's earned revenue, so the purpose arm reads no
    sale. Audit round 3, R3-B15 (R3-59; Q11 (b), standard G6, §4.2): never one a netting word stands beside
    (_ASSET_SALE_NETTING_AFTER: WITHHELD, DEDUCTED, DEDUCT..., NETTED after it; _ASSET_SALE_NETTING_BEFORE: NET OF,
    LESS, AFTER, MINUS before it, and a bare NET before FEES only, R3-B15 review round 1, finding 1), which is what the
    seller's proceeds are net of: 'TRUCK SALE FEES WITHHELD', 'NET FEES TRUCK SALE' and 'LESS COMMISSION TRUCK SALE'
    are the sale, as 'TRUCK SALE NET OF FEES' was; 'TRUCK SALE COMMISSION', 'COMMISSION ON TRUCK SALE', 'TRUCK SALE
    FEE', 'FEE FOR TRUCK SALE' and a broker's or an agent's 'NET COMMISSION ON TRUCK SALE' (its own earned commission
    after splits) stay a broker's revenue. R3-B15 review round 2 (finding 1; R2-OW06 review round 1's broker carve-out,
    standard A11): a seller's proceeds never lead with or come out of a commission, so a commission word printed
    directly before the netting phrase (_ASSET_SALE_COMMISSION_NETTED_BEFORE: 'COMMISSION LESS FEES ON TRUCK SALE',
    'NET COMMISSION LESS FEES TRUCK SALE') or fees taken from or off a commission (_ASSET_SALE_FEES_FROM_COMMISSION:
    'TRUCK SALE FEES WITHHELD FROM COMMISSION') keeps the veto, as its mirror 'TRUCK SALE COMMISSION LESS FEES' does;
    a commission a netting word itself stands before ('NET OF COMMISSION LESS FEES TRUCK SALE') is still the sale."""
    broker = _ASSET_SALE_COMMISSION_NETTED_BEFORE.search(before)
    if _ASSET_SALE_FEES_FROM_COMMISSION.search(after) or (
        broker is not None and _ASSET_SALE_NETTED_WORD.search(before[: broker.start()]) is None
    ):
        return True
    return bool(
        (_ASSET_SALE_COMMISSION_AFTER.search(after) and not _ASSET_SALE_NETTING_AFTER.search(after))
        or (_ASSET_SALE_COMMISSION_BEFORE.search(before) and not _ASSET_SALE_NETTING_BEFORE.search(before))
    )


def _dealer_statement(
    records: Sequence[TransactionClassification], duplicate_indexes: set[int], indexes: Sequence[int],
) -> bool:
    """§8.1 (owner ruling 2026-10-02, the underwriter's Q11 (b)): the statement shows a dealer, whose sales of vehicles
    or equipment stay revenue: R2-OW05's dealer activity (_dealer_activity: Q7 dealer funding that is not payables-only,
    a credit union's VHCL PURCH, a floor-plan financier's row or a FLOOR PLAN form, a posted debit at a dealer-only
    wholesale auction), a §7.8 auction's payout credit (a non-duplicate record of `indexes` whose revenue entity is one
    of WHOLESALE_AUCTION_PAYOUT_FORMS' auctions), or a vehicle or equipment trade name on one of the holder's names (the
    first record's _holder_names, read through account_name_text: _ASSET_TRADE_HOLDER) that prints no recovery,
    repossession, towing or collateral word (_DEALER_HOLDER_VETO). Read once per statement, before the tiers. Audit
    round 3, R3-B14 (R3-52): _dealer_activity's narrowed arms (no card purchase at an auction, no floor-plan financier's
    service credit, no FLOORPLANNER or FLOOR PLANKS), so a non-dealer's asset sale beside such a row is asset-sale
    proceeds."""
    if _dealer_activity(records, duplicate_indexes, indexes):
        return True
    if any(
        records[index].revenue_canonical_entity in _WHOLESALE_AUCTION_ENTITIES
        for index in indexes if index not in duplicate_indexes
    ):
        return True
    if not indexes:
        return False
    classifier = _classifier()
    for name in _holder_names(records[indexes[0]]):
        printed = classifier.account_name_text(name) if name else ""
        if printed and _ASSET_TRADE_HOLDER.search(printed) and not _DEALER_HOLDER_VETO.search(printed):
            return True
    return False


def _asset_sale_record(record: TransactionClassification, arm: str) -> TransactionClassification:
    """§8.1, §8.10 (owner ruling 2026-10-02, the underwriter's Q11 (b)): the record made non_revenue as a non-dealer's
    asset-sale proceeds (method ASSET_SALE_METHOD, rule asset_sale_payer or asset_sale_purpose); its reason names the
    rule it overrules, for the audit. The pass gives it the reason code asset_sale_proceeds; it has no review path."""
    return _classifier()._replace_revenue_state(
        record,
        "non_revenue",
        match_method=ASSET_SALE_METHOD,
        matched_rule=f"asset_sale_{arm}",
        confidence_score=0.90,
        reason=(
            "An equipment auction's or a car buyer's seller payout, or a printed sale of a truck, trailer, vehicle or "
            "equipment, on a statement that shows no dealer evidence: asset-sale proceeds, not revenue, by the owner's "
            f"ruling on the underwriter's Q11 (b); the rule that read it ({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, ASSET_SALE_METHOD),
        related_transaction=record.revenue_related_transaction,
    )


def _progress_draw_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.1, §8.10 (owner ruling 2026-10-02, the underwriter's Q11 (a); R2-OW06 review round 1): a builder's progress
    draw that an earlier rule verified (§7.5's accounts-payable remittance, 'A P PMT DRAW 3') leaves verification as a
    new first state (unverified_deposit, method construction_progress_draw), as _financier_never_verified does; its
    reason names the rule it overruled, for the audit. The pass tiers it counted_flagged / construction_progress_draw."""
    return _classifier()._replace_revenue_state(
        record,
        "unverified_deposit",
        match_method=CONSTRUCTION_PROGRESS_DRAW_REASON,
        matched_rule="construction_progress_draw_never_verified",
        confidence_score=0.50,
        reason=(
            "A builder pays the business a progress draw for its work: counted and flagged, never verified, by the "
            "owner's ruling on the underwriter's Q11 (a); the rule that read it "
            f"({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, CONSTRUCTION_PROGRESS_DRAW_REASON),
        related_transaction=record.revenue_related_transaction,
    )


def _factor_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.9 (A3-H review): a factoring payer's credit that an earlier rule verified (an invoice-purpose wire, an
    accounts-payable remittance descriptor) leaves verification as a new first state (unverified_deposit, method
    factoring_payout_payer); its reason names the rule it overruled, for the audit. The pass tiers it counted_flagged /
    factoring_payout."""
    return _classifier()._replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="factoring_payout_payer",
        matched_rule="factoring_payer_never_verified",
        confidence_score=0.50,
        reason=(
            "A factor pays the business's own invoices: its payout is counted and flagged, never verified; the rule "
            f"that read it ({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, "factoring_payout"),
        related_transaction=record.revenue_related_transaction,
    )


def _financier_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.9 (owner ruling 2026-10-02, Q8): a lease-to-own or patient financier's merchant payout that an earlier rule
    verified (a repeat, a company form, an operating-income descriptor) leaves verification as a new first state
    (unverified_deposit, method customer_financing_payer), as _factor_never_verified does; its reason names the rule it
    overruled, for the audit. The pass tiers it counted_flagged / customer_financing_payout."""
    return _classifier()._replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="customer_financing_payer",
        matched_rule="customer_financing_never_verified",
        confidence_score=0.50,
        reason=(
            "A lease-to-own or patient-financing company pays the merchant for a customer's financed purchase: counted "
            f"and flagged, never verified; the rule that read it ({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, CUSTOMER_FINANCING_PAYOUT),
        related_transaction=record.revenue_related_transaction,
    )


def _lender_service_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.7 (owner ruling 2026-10-02, the underwriter's Q9, part (c')): a listed auto lender's payables-only credit Q7
    verified, on a statement with no dealer evidence, is a lender paying the business for its services (a repossession
    agency's recoveries), never dealer funding: it leaves verification as a new first state (unverified_deposit, method
    lender_paid_for_services, no source type), as _factor_never_verified does; its reason names the lender and its
    alias, says the statement shows no dealer evidence and that the owner's ruling overrules auto_lender_dealer_funding.
    The pass tiers it counted_flagged / lender_paid_for_services, or holds it as financing_named_payer when the lender
    also collects from the account (_payer_collects). The transaction side (classification, match_method,
    canonical_entity and every lender flag) is untouched."""
    lender = record.revenue_canonical_entity or "the lender"
    alias = f" ({record.revenue_matched_alias})" if record.revenue_matched_alias else ""
    return replace(
        _classifier()._replace_revenue_state(
            record,
            "unverified_deposit",
            match_method=LENDER_PAID_FOR_SERVICES,
            matched_rule="q7_payables_without_dealer_evidence",
            confidence_score=0.50,
            reason=(
                f"Listed auto lender '{lender}'{alias} pays the business on a payables word alone, and the statement "
                "shows no dealer evidence (no dealer-funding credit, floor-plan financier, dealer-only auction purchase "
                "or dealer's name): a lender paying the business for its services (a repair, a recovery, a commission), "
                "counted and flagged, never verified. The owner's ruling on the underwriter's Q9 overrules "
                f"{record.revenue_match_method}."
            ),
            context_signals=(*record.revenue_context_signals, LENDER_PAID_FOR_SERVICES),
            related_transaction=record.revenue_related_transaction,
        ),
        revenue_source_type=None,
    )


def _customer_financing_lump(
    index: int,
    payouts: dict[int, str],
    records: Sequence[TransactionClassification],
    channel: str,
    posted_cents: int,
) -> bool:
    """§8.9 (owner ruling 2026-10-02, Q8: "Keep large one-off lump sums held until sourced"): a financier's payout
    (`payouts`: the statement's customer_financing_payout rows, index -> financier) that is large and one-off. Large:
    CUSTOMER_FINANCING_LUMP_FLOOR dollars or more, and an incoming wire, a whole multiple of
    CUSTOMER_FINANCING_LUMP_ROUND dollars or at least CUSTOMER_FINANCING_LUMP_SHARE percent of the statement's posted
    credits (`posted_cents`, non-revenue included, the T7 base). One-off: the same financier makes fewer than
    CUSTOMER_FINANCING_SERIES_MIN payouts in the statement, the row included, of at least
    CUSTOMER_FINANCING_SERIES_SHARE percent of its amount. Read over every payout at once, so the hold never depends on
    the rows' order (a pair of lumps holds both); compared in integer cents."""
    classifier = _classifier()
    cents = _cents(records[index].amount)
    if cents < classifier.CUSTOMER_FINANCING_LUMP_FLOOR * 100:
        return False
    if not (
        channel == "wire" or cents % (classifier.CUSTOMER_FINANCING_LUMP_ROUND * 100) == 0
        or cents * 100 >= classifier.CUSTOMER_FINANCING_LUMP_SHARE * posted_cents
    ):
        return False
    series = sum(
        1 for other, entity in payouts.items()
        if entity == payouts[index] and _cents(records[other].amount) * 100 >= classifier.CUSTOMER_FINANCING_SERIES_SHARE * cents
    )
    return series < classifier.CUSTOMER_FINANCING_SERIES_MIN


def _holder_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.1 (audit round 2, R2-B04: R41): the holder's own push (self_originated) that an earlier rule verified (an
    accounts-payable entry read by step 11, whose holder guard reads only a known holder's name) leaves verification as
    a new first state (unverified_deposit, method self_originated_holder), as _factor_never_verified does; its reason
    names the rule it overruled, for the audit. The pass tiers it excluded_pending_review / holder_name."""
    return _classifier()._replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="self_originated_holder",
        matched_rule="holder_own_push_never_verified",
        confidence_score=0.40,
        reason=(
            "The row's originator is its own receiver: the holder moves its own money in, which is never revenue and "
            f"never verified; the rule that read it ({record.revenue_match_method}) is overruled, and it is held for "
            "review."
        ),
        context_signals=(*record.revenue_context_signals, "self_originated_holder"),
        related_transaction=record.revenue_related_transaction,
    )


def _settlement_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.1 (audit round 3, R3-B10 review round 2: finding 1): a settlement under the merchant's own name that an
    earlier rule verified (an operating-income or a claim-payment descriptor) and that only the bare settlement word
    lifted from the own-push guard (CreditFacts.settlement_released) leaves verification as a new first state
    (unverified_deposit, method HOLDER_NAMED_SETTLEMENT_METHOD), as _holder_never_verified does; its reason names the
    rule it overruled, for the audit. The pass reads it as an unverified credit: a later hold still names it, and where
    none does it is counted and flagged, named_payer_purpose_refused (R3-90 part A: counted, never verified)."""
    return _classifier()._replace_revenue_state(
        record,
        "unverified_deposit",
        match_method=HOLDER_NAMED_SETTLEMENT_METHOD,
        matched_rule=HOLDER_NAMED_SETTLEMENT_RULE,
        confidence_score=0.50,
        reason=(
            "A settlement printed under the merchant's own name (a processor's, a carrier's or an operating "
            "settlement) is no holder's own push: counted and flagged, never verified; the rule that read it "
            f"({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, HOLDER_NAMED_SETTLEMENT_METHOD),
        related_transaction=record.revenue_related_transaction,
    )


def _premium_coded(text: str, region: str) -> bool:
    """§8.6 Q6c (A3-H): a healthcare, insurer or health-plan payer (HEALTHCARE_PAYER_ALIASES, an insurer's name or
    its INS abbreviation) whose entry is premium-coded (_PREMIUM_CODED). A3-H review: read only in the entry field the
    layout prints (Bank of America's DES, Chase's CO ENTRY DESCR); a row that prints none keeps its reading. A
    commission word in the entry keeps its reading too (_COMMISSION_WORD), and a public payer is never read: a
    government payer (the public-payer patterns) or a public health program (_PUBLIC_HEALTH_PAYERS: Medicare and its
    administrative contractors, Medicaid, TRICARE, VA)."""
    entry = _layout_entry(text)
    if not region or _PREMIUM_CODED.search(entry) is None or _COMMISSION_WORD.search(entry) is not None:
        return False
    if government_payer(public_region(text)):
        return False
    health = healthcare_payer_match(region)
    if health is not None:
        return health[0] not in _PUBLIC_HEALTH_PAYERS
    return bool(_INSURER_NAME.search(region) or _INSURER_ABBREVIATION.search(region))


def _wire_verifies(record: TransactionClassification, text: str, facts: CreditFacts, repeats: int) -> bool:
    """§8.5 (Q5): the same company wires twice or more, and the row passes every veto of §7.9 (the 5.5 reader,
    _wire_vetoed: a non-sale purpose, a financing root, any known payee, the own account, a brand-word affiliate, a cut
    financing originator, a title or escrow firm). The holder test is read here too, so a row the holds skip (one the
    registry claimed) never verifies from the holder's name (§6 precedence: Q5 never verifies a row the holder test
    or the numbered-company guard matches)."""
    classifier = _classifier()
    if not facts.wire_n1 or facts.hold is not None or not facts.region or facts.numbered:
        return False
    if classifier.holder_named(facts.region, _holder(record)):
        return False
    if classifier.channel_gate(text) is not None:
        return False
    # Audit B5 (I61): an LLC the originator field cut and glued to the address counts as the company form here only.
    if not (facts.company_form or facts.public_or_healthcare or _cut_wire_legal_form(facts.region)) or repeats < 2:
        return False
    if _BANK_OR_TITLE_SENDER.search(facts.name) or facts.refused_word:
        return False
    return not classifier._wire_vetoed(text, facts.region, _holder(record))


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
    and no numbered company. Audit round 2, R2-B03 (R05): nor a payer region that names only a bank (_bank_only_payer):
    a bank's name, or the statement's own bank's channel ('CHASE ONLINE'), is no customer, so its repetition proves
    nothing (Q6 refused a bank on its company-form arm only before)."""
    classifier = _classifier()
    return (
        facts.electronic and bool(facts.region) and facts.channel == "ach_eft"
        and classifier.channel_gate(text) is None
        and not classifier._TRANSFER_WORDING.search(facts.entry)
        and not facts.wire_n1 and not facts.claimed and facts.hold is None and not facts.numbered
        # Audit B2 (I01): a payer region that is only a bank's name and an account description names no payer.
        and not facts.transfer_no_counterparty
        and not facts.bank_only
    )


def _tier_reason(
    record: TransactionClassification, text: str, facts: CreditFacts, round_repeat: bool, deferred: bool = False,
    unread: bool = False, unread_text: str = "",
) -> tuple[str, str]:
    """§8.10: the tier and reason of an unverified posted credit, in order. A deferred source (§15, `deferred`) on a
    wire or an ACH or EFT row is a named payer Q5 and Q6 refuse as proof, as a verification-only word refuses one:
    named_payer_purpose_refused (S4.2 re-review), never "One-off payer" (a deferred source often repeats). On a row
    with no electronic-payment form it keeps named_payer_unlabelled: Q6 never reads such a row, deferred or not.
    Audit B10 (I05, I60): a row the parser marked as read only by its label (`unread`) that would be counted as Q2's
    no_payer_printed at the bare-row fall-through is counted as payer_text_not_read instead: the statement printed a
    payer the parser did not read. Every hold before it still applies (a bare transfer label stays
    transfer_no_counterparty). B10 review (round 1): a cash, branch, teller or ATM row (the cash_branch_atm channel)
    keeps no_payer_printed, marked or not: its own label says the statement printed no payer (Q2). Audit round 2,
    R2-B07 (R07): such a marked row whose unread run of payer blocks (`unread_text`, Transaction.unread_payer_text)
    prints a lender's or a lending bank's block (unread_run_names_financing) is held as unread_run_names_financing
    instead: one row of the run is that lender's money and the text cannot say which (Q6: lenders never count). It is
    never a lender credit and names no payer.

    Owner ruling 2026-10-02 (the underwriter's Q9; §8.10; R2-OW09): last, after the unread branch, a credit the
    financing-root release lifted (CreditFacts.q9) that the tiers count takes the release's reason, unless its counted
    reason is one a released row keeps (_Q9_KEEPS: payer_text_not_read, the platform, payout, numbered-company and
    factoring readings, and the owner batches' specific counted reasons). A held reason is never overridden."""
    tier, reason = _tier_reason_read(record, text, facts, round_repeat, deferred)
    if unread and reason == "no_payer_printed" and facts.channel != "cash_branch_atm":
        if unread_text and unread_run_names_financing(unread_text):
            return "excluded_pending_review", UNREAD_RUN_NAMES_FINANCING
        reason = PAYER_TEXT_NOT_READ
    if facts.q9 is not None and tier == "counted_flagged" and reason not in _Q9_KEEPS:
        reason = facts.q9
    return tier, reason


def _tier_reason_read(
    record: TransactionClassification, text: str, facts: CreditFacts, round_repeat: bool, deferred: bool,
) -> tuple[str, str]:
    """§8.10's order (_tier_reason), on the row's text alone."""
    classifier = _classifier()
    if record.revenue_match_method == "direction_conflict":
        return "excluded_pending_review", "direction_conflict"
    if facts.hold is not None:
        return "excluded_pending_review", facts.hold
    # Audit B2 (I20, §6.3 narrowing 8): a named sender after an own-account designation left the strong non-revenue
    # rule only to be held (T13), on any channel and whoever the sender is: it never enters True.
    if classifier._named_sender_after_designation(text, _holder(record)):
        return "excluded_pending_review", "transfer_account_designation"
    # Owner ruling 2026-10-02 (the underwriter's Q2; §8.10 item 12): an insurer paying the business for its work, which
    # the release before the facts re-stated (_insurer_for_work); every hold before it still wins. Audit round 3, R3-B13
    # (R3-09; Q3 of 2026-10-02, "repeated round sums from one sender held", and the 2026-10-06 amendment): on a
    # person-to-person row §8.4's round-sum repeat still wins, as for the progress draw: the released row falls through
    # to the person-to-person arm below, held p2p_round_repeat, its method still the release's.
    if record.revenue_match_method == INSURER_FOR_WORK_METHOD and not (
        facts.channel == "person_to_person" and round_repeat
    ):
        return "counted_flagged", INSURER_FOR_WORK_METHOD
    # Audit B3 (I11, §6.3 narrowing 9): a processor's instant payout printed as a card credit, released beside the
    # processor's own ACH activity: a platform payout no form confirms.
    if record.revenue_match_method == PROCESSOR_CARD_PAYOUT_METHOD:
        return "counted_flagged", "platform_unconfirmed"
    # A3-H: a factoring payer's payout, on any channel (FACTORING_PAYOUT_PAYERS).
    if facts.factor:
        return "counted_flagged", "factoring_payout"
    # Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's merchant payout (CUSTOMER_FINANCING_PAYERS),
    # on a wire, an ACH or EFT row or an unlabelled one; a one-off lump sum is held after the tiers.
    if facts.financier:
        return "counted_flagged", CUSTOMER_FINANCING_PAYOUT
    # Owner ruling 2026-10-02 (the underwriter's Q11 (a)): a builder's progress draw, on any channel but Zelle (Q3's); a
    # bare transfer's and an account designation's holds and Q4's round-sum repeat still win (any hold wins above).
    if (
        facts.progress_draw and not facts.transfer_no_counterparty and not facts.account_designation
        and not (facts.channel == "person_to_person" and round_repeat)
    ):
        return "counted_flagged", CONSTRUCTION_PROGRESS_DRAW_REASON
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
    # Audit round 2, R2-B03 (R05): a payer region that names only a bank names no customer (Q2): counted as
    # no_payer_printed, never as a named payer.
    if facts.region and facts.bank_only:
        return "counted_flagged", "no_payer_printed"
    if facts.region and facts.electronic:
        return "counted_flagged", "named_payer_one_off"
    if facts.region and not classifier._is_bare_row(text):
        return "counted_flagged", "named_payer_unlabelled"
    return "counted_flagged", "no_payer_printed"


#: Audit round 3, R3-B15 (R3-53; §5.3): the words a counted re-statement's reason sentence says it is counted with (the
#: insurer-for-work release, the factoring, financier, payables, progress-draw and settlement demotions, the processor
#: card payout), which a hold that re-tiers the row replaces (_held_reason).
_COUNTED_SENTENCE = "counted and flagged, never verified"


def _with_tier(record: TransactionClassification, tier: str, reason: str | None) -> TransactionClassification:
    """A record with its 5.6 tier, initial tier, reason and contribution flags. The review flag is set for a held
    row only; a counted row is reviewable, not required. Audit round 3, R3-B15 (R3-53; §5.3): a held row's reason
    sentence never says it is counted (_held_reason); every other field, and a counted row's sentence, is as before."""
    return replace(
        record,
        revenue_tier=tier,
        revenue_initial_tier=tier,
        revenue_tier_reason=reason,
        revenue_review_required=tier == "excluded_pending_review",
        revenue_reason=_held_reason(record.revenue_reason, reason) if tier == "excluded_pending_review" else (
            record.revenue_reason),
        **revenue_contribution_flags(record.revenue_classification, tier),
    )


def _held_reason(sentence: str | None, reason: str | None) -> str | None:
    """Audit round 3, R3-B15 (R3-53; §5.3): the reason sentence of a row a hold re-tiers (`reason`, the held reason
    code): where an earlier counted re-statement wrote "counted and flagged, never verified" (_COUNTED_SENTENCE), that
    phrase becomes "never verified, and held for review (<label>)", the label the held reason's own
    (REVENUE_TIER_REASONS; the code itself when the table lists none). The wording follows _zelle_excluded, which names
    the rules' reading inside its own sentence. It covers every hold of the owner batches: the Q2 release a later hold
    names, Q8's lump sum, Q9 (c')'s hidden-loan guard, Q10's premium-trust hold and the $1 floor on a counted or
    demoted unverified row (a Verified row the floor or the premium-trust hold re-states gets its own sentence first).
    Any other sentence is returned unchanged."""
    if not sentence or _COUNTED_SENTENCE not in sentence:
        return sentence
    label = REVENUE_TIER_REASONS.get(reason or "", (None, reason or "excluded_pending_review"))[1]
    return sentence.replace(_COUNTED_SENTENCE, f"never verified, and held for review ({label})")


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


#: Owner ruling 2026-10-02 (the underwriter's Q1, "Held for review (look at the day $ amount got deposited and see if
#: there is a frequent payment following the deposit)", option 1; audit I12; §8.5, §10.7; R2-OW12): the funding aid's
#: constants, whole numbers. A series' first payment comes at most FUNDING_SERIES_WINDOW_DAYS after the deposit and
#: falls on FUNDING_SERIES_MIN_PAYMENTS distinct dates or more; its start is observed when the statement shows one full
#: gap of the series, and at least FUNDING_SERIES_MIN_LOOKBACK_DAYS, before the deposit.
FUNDING_SERIES_WINDOW_DAYS = 10
FUNDING_SERIES_MIN_PAYMENTS = 2
FUNDING_SERIES_MIN_LOOKBACK_DAYS = 3
#: The states the Lenders and Potential Lenders tabs list, the only payees the aid reads ("frequent payment" read as a
#: lender-side series: an all-debits pool is card purchases, payroll, own transfers and person-to-person payments).
_FUNDING_SERIES_STATES = ("confirmed_lender", "potential_lender")


@dataclass(frozen=True)
class FundingSeries:
    """Owner ruling 2026-10-02 (the underwriter's Q1; §5.4, §8.5; R2-OW12): one lender's daily or weekly payment series
    that starts after a held wire with no sender printed, the review aid's line ("possible funding").

    `payee` is the name the Lenders or Potential Lenders tab lists (the potential payee label, else the canonical
    entity; never a payee word for an unnamed payee, D11); `lender_state` its tab's state (`confirmed_lender` or
    `potential_lender`); `amount` the payment, positive; `cadence` daily or weekly and `average_gap_days` its mean gap
    (classify_cadence); `first_date` the first payment's date as printed and `days_after` its days after the deposit;
    `payments` its distinct dates; `start_observed` whether the statement shows one full gap of the series before the
    deposit; `source_locations` its rows."""

    payee: str
    lender_state: str
    amount: float
    cadence: str
    average_gap_days: float
    first_date: str
    days_after: int
    payments: int
    start_observed: bool
    source_locations: tuple[str, ...]


def funding_series_after(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
    statement_start: str | None,
) -> list[TransactionClassification]:
    """Owner ruling 2026-10-02 (the underwriter's Q1, option 1; audit I12; §8.5, §10.7; R2-OW12): pass 7's last step.
    Every incoming wire with no sender printed stays held (`wire_no_sender`); this step records on each such held
    credit, as `revenue_funding_series`, every series of the Lenders or Potential Lenders tabs that starts after it, so
    the review can see a funding the wire may be. It reads the records only, and writes that one field and only on
    those credits: no tier, reason, state, flag, figure, gate, debit or lender reading moves.

    1. The pool: posted debits, never a duplicate (`duplicate_indexes`: duplicate_of is written after pass 7), of a
       lender tab's state with a canonical entity, counting toward the lender or potential-lender count (which leaves
       out a settlement-reversed debit, whose counts the reversal pass cleared), grouped by the tab's name (the
       potential payee label, else the canonical entity, as detect._group_funders lists it) and the amount to the cent
       (find_recurring_debits' amount): (state, name, amount).
    2. The statement's start: `statement_start` read as a date, else its earliest dated row.
    3. The targets: posted, non-duplicate credits held as `excluded_pending_review` / `wire_no_sender` whose date reads.
    4. A group is a series of a target when every date of it reads and is after the deposit's day (a payment on or
       before that day means the series was already running), the first at most FUNDING_SERIES_WINDOW_DAYS after it,
       and `_promotion_cadence` (D6's daily or weekly test, several rows on one date one occurrence) reads its dates
       with FUNDING_SERIES_MIN_PAYMENTS. Its start is observed when the deposit comes at least one full gap of the
       series (its mean gap rounded up, and at least FUNDING_SERIES_MIN_LOOKBACK_DAYS) after the statement's start.
       Audit round 3, R3-B02 (R3-66): a settlement-reversed debit is no payment of the series, but an attempt on or
       before the deposit's day means the series was already running: the group's attempts (its pool rows and the
       debits of its key the reversal pass zeroed, `reversed_by`) are keyed as the pool is, and a dated attempt on or
       before the deposit's day keeps the series off that target (an undated attempt is ignored, as an undated pool
       row is). The series itself (its dates, cadence, first date, payments and start) is read from the pool only.
    5. Each target carries its series sorted by first date, then the larger amount, then the payee; a series that
       follows several held wires goes on each, with its own days after. Every other record keeps ()."""
    targets = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount > 0 and record.is_posted
        and record.revenue_tier == "excluded_pending_review" and record.revenue_tier_reason == "wire_no_sender"
        and parse_date(record.date) is not None
    ]
    if not targets:
        return records
    groups: dict[tuple[str, str, float], list[int]] = {}
    # Audit round 3, R3-B02 (R3-66): every attempt of a key, a settlement-reversed one included (its dates only).
    attempts: dict[tuple[str, str, float], list[_date]] = {}
    for index, record in enumerate(records):
        if (
            index in duplicate_indexes or record.amount >= 0 or not record.is_posted
            or record.classification not in _FUNDING_SERIES_STATES or not record.canonical_entity
        ):
            continue
        counted = record.contributes_to_lender_count or record.contributes_to_potential_lender_count
        if not (counted or record.reversed_by):
            continue
        key = (record.classification, record.potential_payee_label or record.canonical_entity,
               round(abs(record.amount), 2))
        if (day := parse_date(record.date)) is not None:
            attempts.setdefault(key, []).append(day)
        if counted:
            groups.setdefault(key, []).append(index)
    classifier = _classifier()
    series: list[tuple[str, str, float, list[int], list[_date], str, float]] = []
    for (state, name, amount), indexes in groups.items():
        days = [parse_date(records[index].date) for index in indexes]
        if any(day is None for day in days):
            continue
        promotion = classifier._promotion_cadence(records, indexes, FUNDING_SERIES_MIN_PAYMENTS)
        if promotion is None:
            continue
        cadence, average_gap = promotion
        series.append((state, name, amount, indexes, days, cadence, float(average_gap)))
    if not series:
        return records
    start = parse_date(statement_start)
    if start is None:
        dated = [day for record in records if (day := parse_date(record.date)) is not None]
        start = min(dated) if dated else None
    updated = list(records)
    for target in targets:
        deposit = parse_date(records[target].date)
        found: list[tuple[_date, FundingSeries]] = []
        for state, name, amount, indexes, days, cadence, average_gap in series:
            first = min(days)
            if first <= deposit or (first - deposit).days > FUNDING_SERIES_WINDOW_DAYS:
                continue
            if any(day <= deposit for day in attempts.get((state, name, amount), ())):
                continue  # R3-66: an attempt on or before the deposit's day: the series was already running
            lookback = max(FUNDING_SERIES_MIN_LOOKBACK_DAYS, math.ceil(average_gap))
            first_row = next(index for index, day in zip(indexes, days) if day == first)
            found.append((first, FundingSeries(
                payee=name,
                lender_state=state,
                amount=amount,
                cadence=cadence,
                average_gap_days=average_gap,
                first_date=records[first_row].date,
                days_after=(first - deposit).days,
                payments=len(set(days)),
                start_observed=start is not None and (deposit - start).days >= lookback,
                source_locations=tuple(
                    location for index in indexes if (location := records[index].source_location)
                ),
            )))
        if found:
            found.sort(key=lambda item: (item[0], -item[1].amount, item[1].payee))
            updated[target] = replace(records[target], revenue_funding_series=tuple(item for _, item in found))
    return updated


def apply_true_revenue_pass(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
    unread_indexes: frozenset[int] = frozenset(),
    unread_texts: dict[int, str] | None = None,
    *,
    premium_trust: str | None = None,
    statement_start: str | None = None,
    zelle_true_revenue: bool = False,
) -> list[TransactionClassification]:
    """Statement pass 7 (§6.2): payer facts, Q7's credit-union arm, the Q5 and Q6 verifications, then the tiers. Audit
    B3 (I11): first, with the owner's switch on (PROCESSOR_CARD_PAYOUT_RELEASE), a processor's instant payouts printed
    as card credits leave the reversal rule (_processor_card_payouts). Audit B10 (I05, I60): `unread_indexes` are the
    credits the parser marked as read only by their label (payer_text_unread_indexes); their tier reason reads them
    (_tier_reason). Audit round 2, R2-B07 (R07): `unread_texts` are those credits' unread payer text
    (payer_text_unread_texts), which only _tier_reason reads. The owner's ruling of 2026-10-02 (the underwriter's Q3):
    every Zelle deposit is excluded after the tiers and before the $1 floor (_zelle_excluded). R2-OW03: a government
    payment that prints no purpose (Q12) takes its display reason, GOVERNMENT_NO_PURPOSE, with its non_revenue tier.
    Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's merchant payout is counted and flagged
    (customer_financing_payout), an earlier verification overruled after the factoring and self-own demotions, and
    after the tiers, before the Zelle step, a large one-off lump sum among those payouts is held
    (customer_financing_lump_sum). Owner ruling 2026-10-02 (Q9, part (c')): after the financier demotion, a listed auto
    lender's payables-only credit Q7 verified, on a statement with no dealer evidence (_dealer_contract_evidence), is
    counted and flagged as lender_paid_for_services, or held as financing_named_payer when the lender also collects
    from the account (_payer_collects). Owner ruling 2026-10-02 (the underwriter's Q11): (a) a builder's progress draw
    is counted and flagged (construction_progress_draw, read with the payer facts); (b) after the facts, on a statement
    that shows no dealer (_dealer_statement), the asset-sale reading (asset_sale_reading, on the unverified rows and the
    rows an invoice or customer-payment descriptor verified) keeps a row from Q5 and Q6, and the tier loop makes it
    non_revenue / asset_sale_proceeds after the payables demotion (a verified row) or after _tier_reason (a row the
    tier counts, or IAA's insurer-name hold); a held tier keeps the row held. Owner ruling 2026-10-02 (the
    underwriter's Q2): after the statement facts and before the payer facts, an insurer's credit paid for the business's
    work (_insurer_for_work) is re-stated as an unverified deposit of method INSURER_FOR_WORK_METHOD, unclaimed (§8.10's
    holds 4 to 11 still read it), never toward a Q5 or Q6 repeat, and tiered counted_flagged /
    insurer_paid_for_services. Owner ruling 2026-10-02 (the underwriter's Q9 (a), (b), (c); R2-OW09): beside the
    business shape and the disbursers, whether the business is in leasing or property (_lessor_business); the payer
    facts then lift T4's financing-root hold on a finance-named customer paying an invoice, a lessor's rent or a lender
    paying for services (finance_named_release, CreditFacts.q9), never verified, never a repeat, the counted reason
    relabelled last in _tier_reason. Owner ruling 2026-10-02 (the underwriter's Q10; R2-OW11): `premium_trust` is the
    statement's premium-trust title (premium_trust_title) or None; when set, the step after the $1 floor holds every
    credit a rule verified or counted as PREMIUM_TRUST_REASON (_held_in_premium_trust). None leaves every record as
    before. Owner ruling 2026-10-02 (the underwriter's Q1; R2-OW12): `statement_start` is the statement's printed
    period start or None; the pass's last step, after the premium-trust hold, records on each held wire with no sender
    the lender series that start after it (funding_series_after, a review aid that moves no tier or figure). The owner's
    amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): `zelle_true_revenue` False (the default) is the stored
    reading, every line as before; True is the counted reading, in which the Zelle step does not run and the two Q3-era
    carve-outs inside the rules are lifted (a builder's Zelle draw is a progress draw, credit_facts; a Zelle truck or
    equipment sale is asset-sale proceeds, asset_sale_reading). The lessor fact keeps its Zelle skip in both readings
    (_lessor_business), and every later step (the $1 floor, the premium-trust hold, funding_series_after) reads the
    counted tiers as it reads any row's."""
    unread_texts = unread_texts or {}
    classifier = _classifier()
    updated = list(records)
    releases = _processor_card_payouts(records, duplicate_indexes) if PROCESSOR_CARD_PAYOUT_RELEASE else {}
    for index, entity in releases.items():
        record = records[index]
        updated[index] = replace(
            classifier._replace_revenue_state(
                record,
                "unverified_deposit",
                match_method=PROCESSOR_CARD_PAYOUT_METHOD,
                matched_rule=_PROCESSOR_CARD_PAYOUT_RULE,
                confidence_score=0.60,
                reason=(
                    f"A card credit naming {entity} beside {entity}'s own ACH payout or pull, with no card purchase "
                    "at it: the processor's instant payout of the business's sales, counted and flagged, never "
                    "verified."
                ),
                context_signals=(*record.revenue_context_signals, PROCESSOR_CARD_PAYOUT_METHOD),
            ),
            revenue_canonical_entity=entity,
        )
    records = updated
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
        # Audit B7 (I36): the same credit unions' other dealer-funding entries (a deal's VADMIN FEE), beside their
        # verified VHCL PURCH credits or printing one's deal ID.
        unions = {records[index].revenue_canonical_entity for index in union_rows}
        deals = {found.group(1) for index in union_rows
                 if (found := _DEAL_ID.search(classifier.revenue_text(records[index].normalized_description)))}
        for index in credits:
            record = updated[index]
            if (
                index in union_rows or record.revenue_classification != "unverified_deposit"
                or not record.direction_consistent or _under_micro_floor(record)
                or record.revenue_match_method == "direction_conflict"
            ):
                continue
            text = classifier.revenue_text(record.normalized_description)
            entry = credit_union_dealer_entry(text)
            deal = _DEAL_ID.search(text)
            if entry is None or not (entry.entity in unions or (deal is not None and deal.group(1) in deals)):
                continue
            updated[index] = replace(
                _verify(record, "auto_lender_dealer_funding",
                        f"Credit union '{entry.entity}' funds the dealer's indirect auto loans (its VHCL PURCH credits "
                        f"verify in the statement): its {entry.word} entry is the same dealer funding.", 0.90),
                revenue_source_type="auto_dealer_funding",
                revenue_canonical_entity=entry.entity,
                revenue_matched_alias=entry.alias,
            )
    debits = counter_debits(records, duplicate_indexes)
    # Audit B7 (I09): whether the account reads as a business's, which the direct-deposit words read.
    business = _business_shape(records, duplicate_indexes)
    # A3-G refinement: the holder's names the statement's own receiver fields print, when its account name names nobody.
    receiver_holders = _receiver_holder_names(records, credits)
    # Audit round 2, R2-B11 (R09 part A): without TD Canada Trust's e-Transfer code (without_transfer_code). Audit
    # round 3, R3-12: and PNC's Zelle rail spelled as its ZELLE twin (pass_text).
    texts = {
        index: pass_text(updated[index], classifier.revenue_text(updated[index].normalized_description))
        for index in credits
    }
    # Audit B7 (I18): the ordinary payers whose disbursement entry repeats in the statement.
    disbursers = _recurring_disbursers(texts)
    # Owner ruling 2026-10-02 (the underwriter's Q9 (b); §8.1; R2-OW09): whether the business is in leasing or property,
    # which a rent LEASE needs to be released from T4's financing-root hold (_lessor_business).
    lessor = _lessor_business(updated, duplicate_indexes, credits)
    # Owner ruling 2026-10-02 (the underwriter's Q9, part (c'); §8.7): whether the statement shows dealer evidence,
    # which a listed auto lender's payables-only credit needs to stay verified (_dealer_contract_evidence).
    dealer = _dealer_contract_evidence(updated, duplicate_indexes, credits)
    # Owner ruling 2026-10-02 (the underwriter's Q2, "True revenue"; §8.1, §8.10 item 12): an insurer's credit paid for
    # the business's work (a holder trade, a service form, or three or more from one insurer within 31 days;
    # _insurer_for_work) is re-stated before the facts, as B3's processor release is: an unverified deposit of method
    # INSURER_FOR_WORK_METHOD, unclaimed, so §8.10's holds 4 to 11 still read it, never toward a Q5 or Q6 repeat, and
    # tiered counted_flagged / insurer_paid_for_services where no hold names it. The reason names the ground alone.
    for index, ground in _insurer_for_work(updated, credits, texts, receiver_holders).items():
        record = updated[index]
        updated[index] = classifier._replace_revenue_state(
            record,
            "unverified_deposit",
            match_method=INSURER_FOR_WORK_METHOD,
            matched_rule="insurer_paid_for_services",
            confidence_score=0.60,
            reason=_insurer_for_work_reason(ground),
            context_signals=(*record.revenue_context_signals, INSURER_FOR_WORK_METHOD),
        )
    def facts_of(index: int) -> CreditFacts:
        return credit_facts(
            updated[index], texts[index], debits=debits,
            receiver_holders=receiver_holders, business=business, disbursers=disbursers, lessor=lessor,
            zelle_true_revenue=zelle_true_revenue,
        )

    facts = {index: facts_of(index) for index in credits}
    # Audit round 3, R3-B10 review round 2 (finding 1; R3-90 part A: counted, never verified): a settlement under the
    # merchant's own name that an earlier rule verified, which only the bare settlement word lifted from the own-push
    # guard (CreditFacts.settlement_released), leaves verification before the repeats and the tiers read it
    # (_settlement_never_verified), its facts read again: every hold still reads it, and it is never a repeat. A credit
    # under $1 keeps the floor's hold, which runs after the tiers.
    for index in credits:
        record = updated[index]
        if (
            record.revenue_classification == "verified_revenue" and facts[index].settlement_released
            and not _under_micro_floor(record)
        ):
            updated[index] = _settlement_never_verified(record)
            facts[index] = facts_of(index)
    # Owner ruling 2026-10-02 (the underwriter's Q11 (b); §8.1, §8.10): on a statement that shows no dealer
    # (_dealer_statement, read over every non-duplicate record), an equipment auction's or a car buyer's seller payout
    # and a printed sale of a truck, trailer, vehicle or equipment are asset-sale proceeds (asset_sale_reading): read
    # here on the unverified rows and on the rows an invoice or customer-payment descriptor verified, never counted
    # toward a repeat nor verified by Q5 or Q6, and made non_revenue by the tier loop where the row would be counted or
    # that verification stands (a held tier keeps the row held).
    asset_sales: dict[int, str] = {}
    if not _dealer_statement(
        updated, duplicate_indexes, [index for index in range(len(updated)) if index not in duplicate_indexes]
    ):
        for index in credits:
            record = updated[index]
            verified = (
                record.revenue_classification == "verified_revenue"
                and record.revenue_match_method in ASSET_SALE_INVOICE_METHODS
            )
            if (
                (record.revenue_classification != "unverified_deposit" and not verified)
                or not record.direction_consistent or record.revenue_match_method == "direction_conflict"
                or _under_micro_floor(record)
            ):
                continue
            arm = asset_sale_reading(
                record, texts[index], facts[index], verified=verified, zelle_true_revenue=zelle_true_revenue,
            )
            if arm is not None:
                asset_sales[index] = arm
    # §5.2: repeats count a verified credit, or an unverified one no hold names; never a held or conflicting one, a
    # credit under $1, a row a family rule decides alone or a deferred source (_never_q5_or_q6), and on the wire
    # channel only an incoming wire (§8.5: the loose wire words are for tiering only; S4.2 review I4). Never a Q7 row
    # either (S4.3 review): a lender's dealer funding verifies by §8.7 alone, and Q6's lenders never count. Q11 (b): nor
    # a row the asset-sale reading names.
    never = {
        index: _never_q5_or_q6(updated[index], texts[index], facts[index]) or index in asset_sales
        for index in credits
    }
    counting = Counter()
    consumer_only: dict[tuple[str, tuple[str, ...]], bool] = {}
    for index in credits:
        record, fact = updated[index], facts[index]
        # Audit round 2, R2-B04 (R41): the holder's own push never counts toward a repeat, verified or not.
        if not fact.key or record.revenue_classification == "non_revenue" or never[index] or fact.self_own:
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
    # Owner ruling 2026-10-02 (Q8): the statement's posted credits in cents, non-revenue included (the T7 base), which
    # the lump-sum test reads, and the financiers' payouts the tiers give (index -> financier).
    posted_cents = sum(_cents(records[index].amount) for index in credits)
    financier_payouts: dict[int, str] = {}
    for index in credits:
        record, fact = updated[index], facts[index]
        # A3-H review: a factoring payer's credit is never verified, whichever earlier rule verified it. Audit B6 (I25,
        # I10): nor is a factoring payee's (the ledger's factoring aliases, a factoring review entity), whose name may
        # print no financing word ('<factor> OPER DES:INVOICE PMT' is an invoice descriptor's).
        # Audit round 3, R3-B15 (R3-63): a credit under $1 is left to the floor, which holds it with its own method,
        # rule and sentence naming the rule it overruled, as the self-own arm below leaves it.
        factor = fact.factor or record.classification == "factoring"
        if record.revenue_classification == "verified_revenue" and factor and not _under_micro_floor(record):
            updated[index] = _with_tier(_factor_never_verified(record), "counted_flagged", "factoring_payout")
            continue
        # Audit round 2, R2-B04 (R41): nor is the holder's own push, which an earlier rule verified (an
        # accounts-payable entry read by step 11): held as the holder's name. A credit under $1 keeps the floor's hold,
        # which runs after this.
        if record.revenue_classification == "verified_revenue" and fact.self_own and not _under_micro_floor(record):
            updated[index] = _with_tier(_holder_never_verified(record), "excluded_pending_review", "holder_name")
            continue
        # Owner ruling 2026-10-02 (Q8): nor is a lease-to-own or patient financier's merchant payout, whichever earlier
        # rule verified it: counted and flagged, and read by the lump-sum test below.
        if record.revenue_classification == "verified_revenue" and fact.financier:
            updated[index] = _with_tier(
                _financier_never_verified(record), "counted_flagged", CUSTOMER_FINANCING_PAYOUT
            )
            financier_payouts[index] = fact.financier
            continue
        # Owner ruling 2026-10-02 (the underwriter's Q9, part (c'); §8.7): nor is a listed auto lender's credit Q7 read
        # on a payables word alone, on a statement that shows no dealer evidence: a lender paying the business for its
        # services (a repossession agency's recoveries), counted and flagged, or held as financing_named_payer when
        # the lender also collects from the account (_payer_collects, the hidden-loan guard).
        if (
            record.revenue_classification == "verified_revenue"
            and record.revenue_match_method == "auto_lender_dealer_funding"
            and not dealer and _payables_only_dealer_funding(texts[index])
        ):
            held = _payer_collects(counter_credit(record, texts[index], fact.region), debits)
            updated[index] = _with_tier(
                _lender_service_never_verified(record),
                *(("excluded_pending_review", "financing_named_payer") if held
                  else ("counted_flagged", LENDER_PAID_FOR_SERVICES)),
            )
            continue
        # Owner ruling 2026-10-02 (the underwriter's Q11 (b)): nor is a non-dealer's printed vehicle sale an invoice or
        # customer-payment descriptor verified (asset_sales): asset-sale proceeds, non_revenue / asset_sale_proceeds.
        if record.revenue_classification == "verified_revenue" and index in asset_sales:
            updated[index] = _with_tier(_asset_sale_record(record, asset_sales[index]), "non_revenue", ASSET_SALE_METHOD)
            continue
        # Owner ruling 2026-10-02 (the underwriter's Q11 (a); R2-OW06 review round 1): nor is a builder's progress draw
        # an earlier rule verified (§7.5's accounts-payable remittance): counted and flagged, never verified. Audit
        # round 3, R3-B15 (R3-63): a credit under $1 is left to the floor, as the factoring arm's is.
        if (
            record.revenue_classification == "verified_revenue" and fact.progress_draw
            and not _under_micro_floor(record)
        ):
            updated[index] = _with_tier(
                _progress_draw_never_verified(record), "counted_flagged", CONSTRUCTION_PROGRESS_DRAW_REASON
            )
            continue
        tier = _TIER_OF_STATE.get(record.revenue_classification)
        if tier is not None:
            # R2-OW03 (Q12's display reason): a government payment that prints no purpose is named in the non-revenue
            # breakdown; every other verified or non_revenue row carries no reason, as before.
            no_purpose = tier == "non_revenue" and record.revenue_match_method == GOVERNMENT_NO_PURPOSE_METHOD
            updated[index] = _with_tier(record, tier, GOVERNMENT_NO_PURPOSE if no_purpose else None)
            continue
        round_repeat = fact.round_sum and bool(fact.key) and round_sums[fact.key] >= 2
        tier, reason = _tier_reason(
            record, texts[index], fact, round_repeat, _deferred_source(texts[index], fact),
            unread=index in unread_indexes, unread_text=unread_texts.get(index, ""),
        )
        # Owner ruling 2026-10-02 (the underwriter's Q11 (b)): asset-sale proceeds where the tier would count the row, or
        # where only IAA's insurer-name hold reads it (its INSURANCE is the auction's name); every other hold wins.
        if index in asset_sales and (tier == "counted_flagged" or reason == "insurer_named_payer"):
            record = _asset_sale_record(record, asset_sales[index])
            tier, reason = "non_revenue", ASSET_SALE_METHOD
        updated[index] = _with_tier(record, tier, reason)
        if reason == CUSTOMER_FINANCING_PAYOUT:
            financier_payouts[index] = fact.financier
    # Audit round 3, R3-B14 review round 1 (finding 2): a financier's credit whose claim the non-sale or financing veto
    # lifted and that the rules counted (an abbreviated advance, ADVNC, ADVN or ADVC, which no hold reads) is read by
    # the lump-sum test as the payout it was read as before the veto (_vetoed_financier), so a large one-off advance
    # stays held until sourced; its counted reason is kept otherwise.
    for index in credits:
        if (
            index not in financier_payouts and updated[index].revenue_tier == "counted_flagged"
            and not facts[index].claimed
        ):
            vetoed = _vetoed_financier(updated[index], texts[index])
            if vetoed is not None:
                financier_payouts[index] = vetoed
    # Owner ruling 2026-10-02 (Q8; §8.9, §8.10): after the tiers and before the Zelle step, a financier's payout that is
    # a large one-off lump sum is held until sourced (_customer_financing_lump), read over every payout the tiers gave.
    for index in financier_payouts:
        if _customer_financing_lump(index, financier_payouts, updated, facts[index].channel, posted_cents):
            updated[index] = _with_tier(updated[index], "excluded_pending_review", CUSTOMER_FINANCING_LUMP_SUM)
    # The owner's ruling of 2026-10-02 (the underwriter's Q3; §8.4, §8.10 step 26): the last tier step, after every
    # tier and before the $1 floor. Every Zelle deposit the rules tiered is excluded (_zelle_excluded), a hold or a
    # count alike; a row a non-revenue rule decided keeps that rule, and a direction conflict keeps its hold. Nothing
    # before this step changes: the facts, the holds, Q5's and Q6's counts and a sender's named round sums still read
    # Zelle rows. The floor and every later step skip the rows this step excludes (they are non_revenue). The owner's
    # amendment of 2026-10-06 (R2-OW17): the stored reading only; the counted reading (`zelle_true_revenue`) skips it.
    for index in credits:
        record = updated[index]
        if (
            not zelle_true_revenue
            and zelle_deposit(texts[index]) and record.revenue_classification != "non_revenue"
            and record.revenue_match_method != "direction_conflict"
        ):
            updated[index] = _zelle_excluded(record)
    # §7.0, §7.8, §8.10 (S4.4/S4.5 review): the $1 floor is absolute, so it runs after every verification. A posted
    # credit under $1 that any rule verified or counted (a single-row rule, the registry's own context, a descriptor or
    # a remittance, reads no floor of its own) is held as _MICRO_DEPOSIT_REASON; a held one keeps its first hold
    # (§8.10's order) and a non-revenue one stays non-revenue. None counted toward a repeat above (_never_q5_or_q6).
    for index in credits:
        record = updated[index]
        if _under_micro_floor(record) and record.revenue_tier in {"verified", "counted_flagged"}:
            updated[index] = _held_by_the_floor(record)
    # Owner ruling 2026-10-02 (the underwriter's Q10, "Hold every deposit into an account titled "premium trust""; §8.10;
    # R2-OW11): the step after the $1 floor. On a statement whose printed title reads PREMIUM TRUST (premium_trust_title,
    # read by classify_statement_transactions on the statement's own fields), every posted credit a rule verified or
    # counted is held as PREMIUM_TRUST_REASON (_held_in_premium_trust): the Q5, Q6 and Q7 verifications, the
    # demotions, the insurer-for-work release and every count before it included. A held credit keeps its first hold
    # (a direction conflict and the floor's included) and a non-revenue credit stays non-revenue (duplicates, lender
    # proceeds, premium finance, own transfers, the Zelle step's); Q5's and Q6's repeat counts are unchanged.
    if premium_trust:
        for index in credits:
            if updated[index].revenue_tier in {"verified", "counted_flagged"}:
                updated[index] = _held_in_premium_trust(updated[index], premium_trust)
    # Owner ruling 2026-10-02 (the underwriter's Q1, "Held for review (look at the day $ amount got deposited and see if
    # there is a frequent payment following the deposit)"; §8.5, §10.7; R2-OW12): the last step, on the final tiers (a
    # premium trust account's held wire keeps wire_no_sender and gets it too). Each held wire with no sender carries
    # the Lenders or Potential Lenders series that start after it (funding_series_after); nothing else changes.
    return funding_series_after(updated, duplicate_indexes, statement_start)


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


def guard_facts(record: TransactionClassification, text: str, *, zelle_true_revenue: bool = False) -> dict:
    """The census's §14.3 facts of one posted credit (tools/revenue_census.py), read with these readers. The customer
    descriptor is step 11's reading (the text without the receiver field's value, or the joined originator and entry
    before the receiver fields), so a descriptor in the holder's name never marks a row. The known payee is read the
    same way, as the record's claim reads it (S4.2 review M3). `claimed` is the pass's own claim (§8.1: the holds,
    the holder's included, skip a row the registry, a payout entity or a factoring payee claimed), which the census's
    holder guards read (review M1). Audit round 2, R2-B11 (R09 part A): the facts read the pass's own text, TD Canada
    Trust's e-Transfer code dropped (without_transfer_code). The owner's amendment of 2026-10-06 to the underwriter's
    Q3 (R2-OW17): `zelle_true_revenue` is the snapshot's reading, which the progress_draw fact follows as the pass's
    payer facts do (credit_facts). Audit round 3, R3-12: the pass's own text is pass_text (PNC's ZEL read as ZELLE)."""
    classifier = _classifier()
    text = pass_text(record, text)
    region = classifier.payer_region(text)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    words = classifier._without_receiver_value(text)
    known = match_known_payee(words, credit=True)
    # G12 (§8.7): Q7's payer and veto words, read as dealer_funding reads them (the holder's name never names a lender).
    listed = _dealer_funding_payer(words) is not None
    union = bool(_CREDIT_UNION_PAYER.search(region))
    # Audit B7 (I47): the pay and benefit words are read as the holds read them, without the holder's own name runs
    # (audit round 2, R2-B04: R40, and its other business names, _holder_strip_names).
    also = _holder_strip_names(record)
    pay_row = _without_holder_name(row, _holder(record), also=also)
    return {
        "claimed": _claimed(record, text),
        "financing_root": financing_named(text, region, entry, _holder(record), bank=record.bank, also=also),
        "registry_root": registry_financing_root(record, text),
        "registry_financing": registry_financing(record, text),
        "pay_or_personal": bool(
            _PAY_WORDS.search(pay_row) or _EARNED_WAGE_ACCESS.search(pay_row) or cpa_payroll_code(pay_row, record.bank)
            # Audit round 2, R2-B12 (R42): with the statement's bank, as the hold reads it.
            or _personal_income(text, pay_row, record.bank)
            # Audit B7 (I09): the direct-deposit words with the row's own sign of a person's pay (a person receiver, a
            # consumer entry); the account's shape is the statement's, which the pass alone reads (a row it holds on
            # that shape is out of True).
            or _direct_deposit_pay(text, pay_row, _holder(record), business=True)
        ),
        # Audit B2: the pass's own reading (_transfer_reading): the statement's bank, the explicit deposit forms. Audit
        # round 2, R2-B03 (R05): and an ACH pull whose payer region is only a bank (_bank_only_pull).
        "transfer_no_counterparty": _transfer_reading(record, text, _channel(text, record.bank), region)[2],
        # Audit round 2, R2-B03 (R05): the payer region names only a bank (_bank_only_payer), which Q6 never verifies.
        "bank_only_payer": _bank_only_payer(region, entry, record.bank, row=row),
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
        # Final review I7: the pass's own readings the census's demotion causes key on (the rule that fires).
        "hold_rule": hold_rule(record, text, region, entry),
        "relayed_customer": bool(classifier.wire_relayed_customer(text)),
        # Audit B5 (I15, I19, I26, I55, I59): the payer region reads past a bank's label, entry or reference.
        "payer_label_layout": classifier.payer_label_layout(text),
        "premium_coded": _premium_coded(text, region),
        "factoring_payer": _factoring_payout_payer(region, text),
        # Owner ruling 2026-10-02 (Q8): the lease-to-own or patient financier whose merchant payout the row is (a
        # ledger entity name, or None), which the census's narrowing and declared demotion read.
        "customer_financing_payer": _customer_financier(record, text),
        # Audit B6 (I10): the row is a factoring review entity's credit, routed to the factoring payout, unconfirmed.
        "factoring_review": (
            record.classification == "factoring" and record.match_method == "unconfirmed_flag_payee_alias"
        ),
        "deferred_source": _deferred_reading(text, _channel(text), region, entry),
        "short_healthcare_alias": (
            bool(region) and registry_match(region, HEALTHCARE_PAYER_ALIASES) is not None
            and healthcare_payer_match(region) is None
        ),
        # Audit round 2, R2-B12 (R17): an ordinary payer's disbursement entry, which B7's I18 spare drops from the
        # non-sale reading when it repeats in the statement (the pass's spared refused word; read here on the row).
        "spared_disbursement": bool(region) and _disbursing_payer(text, region) and _disbursement_entry(text, region),
        # Audit round 2, R2-B12 review round 2 (R37): a hold word only the trade-name reader's purpose arm spared (the
        # pass's refused word, read on the hold's text without the holder's names, as hold_rule reads it).
        "purpose_trade_name": purpose_trade_name(
            text, _without_holder_name(_hold_text(text), _holder(record), also=also), region
        ),
        # Owner ruling 2026-10-02 (the underwriter's Q11 (a)): a builder's progress draw on a row nothing claimed, as the
        # pass's payer facts read it (CreditFacts.progress_draw).
        "progress_draw": not (_claimed(record, text) or _factoring_payout_payer(region, text))
        and construction_progress_draw(text, region, _holder(record), also=also, zelle_true_revenue=zelle_true_revenue),
        # R2-OW06 review round 1: the pass's channel and payer key as a digest (never a name), by which the census finds
        # a Q5 or Q6 repeat whose same-payer row Q11 keeps from the repeat (an asset sale, a builder's progress draw).
        "payer_key_digest": payer_key_digest(text, region, record.bank),
    }


def payer_key_digest(text: str, region: str, bank: str | None = None) -> str | None:
    """R2-OW06 review round 1 (a census fact): sixteen hex digits of the SHA-256 of the row's channel and the payer key
    Q5 and Q6 group a repeat by (_channel, the classifier's _payer_key of the payer region), or None where the region
    names no payer. Rows of one payer on one channel share it; it never prints the payer's name."""
    key = _classifier()._payer_key(region) if region else ()
    if not key:
        return None
    return hashlib.sha256(f"{_channel(text, bank)}|{' '.join(key)}".encode("utf-8")).hexdigest()[:16]


def hold_rule(record: TransactionClassification, text: str, region: str, entry: str) -> str | None:
    """Final review I7 (a census fact): which 5.6 hold reading of §20 names the row, in §8.10's order: a bank that
    originates the wire, a financing root, a lending bank (audit B6: I23; the financing holds); a government benefit
    (GOV, the personal-income hold);
    a government grant (GOV), a title firm, the holder's currency conversion, a personal trust, owner money (the
    non-sale holds); a payroll provider's tax-service credit (audit B4: I56, the non-sale hold after the counter-debit
    holds); or None. The census keys a Q5 or Q6 row's later hold on it. Audit B8: a gambling payout (I28), a legal
    settlement (I44) and an owner-shaped payer's DISB, after a personal trust and before owner money. Audit round 2,
    R2-B12 (R37, R36): each read as non_sale_purpose reads it (owner money by owner_money_platform)."""
    classifier = _classifier()
    # Audit round 2, R2-B04 (R40): the holder's other business names are stripped as the holds strip them.
    also = _holder_strip_names(record)
    row = _without_holder_name(_hold_text(text), _holder(record), also=also)
    if _bank_originated_wire(text, region, wire=_channel(text, record.bank) == "wire"):
        return "bank_originated_wire"
    if financing_named(text, region, entry, _holder(record), bank=record.bank, also=also):
        return "financing_root"
    # Audit B6 (I23): a lending bank named as the payer (the financing hold).
    if lending_bank_payer(text, region):
        return "lending_bank"
    if government_benefit(text):
        return "government_benefit"
    if government_grant(text):
        return "government_grant"
    if region and _TITLE_FIRM.search(region) and _TITLE_FEE_WORDING.search(_title_purpose_text(text)) is None:
        return "title_firm"
    if _currency_conversion(text, bank=record.bank):
        return "currency_conversion"
    if _held_personal_trust(text, region):
        return "personal_trust"
    if gambling_payout(text, row):
        return "gambling_payout"
    if legal_settlement(text, row, region):
        return "legal_settlement"
    if owner_disbursement(text, row, region):
        return "owner_disbursement"
    if (
        (_INVESTMENT_PURPOSE.search(row) and not _accounts_payable_wording(text))
        # Audit round 2, R2-B12 (R37): read as non_sale_purpose reads it.
        or owner_money_platform(text, row, region)
        or classifier._matches_any(row, classifier._SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS)
    ):
        return "owner_money"
    if payroll_tax_credit(text, region):
        return "payroll_tax"
    return None
