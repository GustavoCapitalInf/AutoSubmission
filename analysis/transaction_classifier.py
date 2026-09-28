from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from statistics import mean, pstdev
from typing import Literal, Sequence, TYPE_CHECKING

from .classification_registry import (
    BANK_NAME_ALIASES,
    BANK_SPECIFIC_LENDER_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    FIELD_ORDER_PAYEE_FORMS,
    INSURANCE_PROVIDER_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    PAYEE_GROUP_REGISTRIES,
    PAYOUT_CREDIT_ENTITIES,
    POTENTIAL_LENDER_ALIASES,
    PREMIUM_FINANCE_ALIASES,
    REVIEW_FLAG_ENTITIES,
)
from .dates import parse_date
from .flag_groups import FINANCING_STATES, FLAG_GROUP_BY_KEY, FLAG_GROUP_BY_STATE
from .revenue import RevenueState, revenue_contribution_flags
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from .description_text import normalize_transaction_description
from .payee_matcher import PayeeMatch, match_debt_relief_payee, match_known_payee, registry_match

if TYPE_CHECKING:
    from .schema import Statement


ClassificationState = Literal[
    "confirmed_lender",
    "potential_lender",
    "insurance",
    "alternative_position",
    "line_of_credit",
    "vehicle_financing",
    "bank_loan",
    "mortgage",
    "lease_or_rental",
    "personal_loan",
    "floor_plan_financing",
    "factoring",
    "debt_relief",
    # Retired in classification version 5.0: no rule produces it, but records
    # stored before 5.0 carry it and must still validate (spec §4.1).
    "lease_or_equipment_financing",
    "fee",
    "transfer",
    "credit_card_payment",
    "payroll",
    "tax",
    "utility",
    "rent",
    "pos",
    "atm",
    "nsf_or_return",
    "refund_or_reversal",
    "other",
]

CLASSIFICATION_STATES: tuple[ClassificationState, ...] = (
    "confirmed_lender",
    "potential_lender",
    "insurance",
    "alternative_position",
    "line_of_credit",
    "vehicle_financing",
    "bank_loan",
    "mortgage",
    "lease_or_rental",
    "personal_loan",
    "floor_plan_financing",
    "factoring",
    "debt_relief",
    "lease_or_equipment_financing",
    "fee",
    "transfer",
    "credit_card_payment",
    "payroll",
    "tax",
    "utility",
    "rent",
    "pos",
    "atm",
    "nsf_or_return",
    "refund_or_reversal",
    "other",
)

#: 5.0 (2026-09-24): the lender-detection rules. 5.1 (2026-09-26): the D6
#: clarification (three different dates; no card-purchase posting). 5.2
#: (2026-09-27): D6 skips compensation memos, and a masked recipient account
#: printed after TO is part of the payee. Moves with
#: `webapp.artifact_cache.ANALYSIS_STAGE_VERSION`.
CLASSIFICATION_VERSION = "5.2"

#: The entity of an unknown obligation whose descriptor names no organisation (D11).
UNIDENTIFIED_LENDER_OBLIGATION = "Unidentified lender obligation"

#: 5.3 (2026-09-27): the fixed D10 name of an MCA SERVICING payee. The two words print for two unrelated funders
#: (ledger decision of 2026-09-25), so no D11 name is ever built from them.
UNIDENTIFIED_MCA_SERVICER = "MCA servicer (funder not identified)"


@dataclass(frozen=True)
class _RevenueDecision:
    classification: RevenueState
    canonical_entity: str | None
    match_method: str
    matched_alias: str | None
    matched_rule: str
    confidence_score: float
    reason: str
    source_type: str | None = None
    context_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransactionClassification:
    original_description: str
    normalized_description: str
    classification: ClassificationState
    date: str = ""
    amount: float = 0.0
    direction: str = "debit"
    bank: str | None = None
    account: str | None = None
    account_name: str | None = None
    source_direction: str | None = None
    direction_consistent: bool = True
    source_page: int | None = None
    source_location: str | None = None
    canonical_entity: str | None = None
    match_method: str = "default"
    matched_alias: str | None = None
    matched_rule: str | None = None
    confidence_score: float = 0.5
    reason: str = "No higher-confidence classification rule matched."
    is_posted: bool = True
    review_required: bool = False
    # Spec §4.2: the FlagGroup.key of a flag-group state, otherwise None.
    flagged_group: str | None = None
    revenue_classification: RevenueState | None = None
    revenue_initial_classification: RevenueState | None = None
    revenue_canonical_entity: str | None = None
    revenue_match_method: str | None = None
    revenue_matched_alias: str | None = None
    revenue_matched_rule: str | None = None
    revenue_confidence_score: float | None = None
    revenue_reason: str | None = None
    revenue_source_type: str | None = None
    revenue_context_signals: tuple[str, ...] = ()
    revenue_related_transaction: str | None = None
    revenue_review_required: bool = False
    revenue_review_status: str | None = None
    revenue_review_note: str | None = None
    revenue_reviewed_at: str | None = None
    duplicate_of: str | None = None
    reversal_of: str | None = None
    reversed_by: str | None = None
    settlement_reversal: bool = False
    contributes_to_lender_count: bool = False
    contributes_to_potential_lender_count: bool = False
    contributes_to_lender_totals: bool = False
    contributes_to_withholding_rate: bool = False
    contributes_to_potential_lender_totals: bool = False
    contributes_to_potential_withholding_exposure: bool = False
    contributes_to_insurance_totals: bool = False
    # Spec §4.2: a posted flag-group debit; cleared for proven duplicates and
    # settlement-reversed debits. Never read by lender, withholding or revenue math.
    contributes_to_flagged_totals: bool = False
    contributes_to_verified_revenue: bool = False
    contributes_to_unverified_deposit: bool = False
    contributes_to_true_revenue: bool = False
    contributes_to_potential_revenue: bool = False
    contributes_to_non_revenue: bool = False
    contributes_to_lender_credit_exclusion: bool = False
    is_ach: bool = False
    is_check: bool = False
    is_loan_payment: bool = False
    is_pos_context: bool = False
    classification_version: str = CLASSIFICATION_VERSION
    # 5.3 (2026-09-27): the Potential Lenders line of an unnamed potential payee, one per payee key within the
    # statement ('Unidentified lender obligation (weekly, 450.00)'). None for every other row, whose line is its
    # canonical_entity.
    potential_payee_label: str | None = None

    @property
    def is_pos_purchase(self) -> bool:
        return self.classification == "pos" and self.amount < 0

    @property
    def is_pos_credit_or_refund(self) -> bool:
        return self.classification == "refund_or_reversal" and self.is_pos_context

    @property
    def is_nsf_event(self) -> bool:
        return self.classification == "nsf_or_return"

    @property
    def is_atm_withdrawal(self) -> bool:
        return self.classification == "atm" and self.amount < 0

    @property
    def categories(self) -> tuple[str, ...]:
        categories: list[str] = [self.classification]
        if self.is_pos_purchase:
            categories.append("pos_purchase")
        if self.is_pos_credit_or_refund:
            categories.append("pos_credit_or_refund")
        if self.is_nsf_event:
            categories.append("nsf_event")
        if self.is_atm_withdrawal:
            categories.append("atm_withdrawal")
        return tuple(categories)


#: The ACH token, compiled once (it used to be re-normalized on every row).
_ACH_TOKEN = re.compile(r"(?<![A-Z0-9])ACH(?![A-Z0-9])")


def match_verified_lender_alias(description: str) -> tuple[str, str] | None:
    return registry_match(
        normalize_transaction_description(description),
        PAYEE_GROUP_REGISTRIES["confirmed_lender"],
    )


def match_insurance_provider(description: str) -> tuple[str, str] | None:
    return registry_match(normalize_transaction_description(description), INSURANCE_PROVIDER_ALIASES)


#: The flag group of an insurance row whose insurer is a premium-finance payee
#: (C1: the one flag group that is not a classification state).
_PREMIUM_FINANCING_GROUP = "premium_financing"

#: Owner ruling 2026-09-26: a factor's payout is the business's own sales, paid
#: by the factor that bought its invoices. A credit from a payee of these states
#: is not financing proceeds: it takes the operating-revenue path, as a
#: PAYOUT_CREDIT_ENTITIES credit does, and it still carries its group's flag (C4).
_FLAGGED_REVENUE_CREDIT_STATES: frozenset[str] = frozenset({"factoring"})


def _insurance_registry_match(text: str) -> tuple[str, str, bool] | None:
    """Spec §4.3 step 4: the insurer of an insurance row, as (entity, alias, premium_finance).

    Premium-finance payees (`PREMIUM_FINANCE_ALIASES`, spec §4.2) are consulted
    first, so a premium financier whose name contains an insurer's name is still
    the premium financier.
    """
    premium = registry_match(text, PREMIUM_FINANCE_ALIASES)
    if premium is not None:
        return premium[0], premium[1], True
    insurer = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurer is not None:
        return insurer[0], insurer[1], False
    return None


#: Owner decision 2026-09-25 (premium_finance_wording): premium-finance wording on
#: a row no premium-finance alias claimed is premium financing too. Read by the
#: insurance rule of `classify_transaction` only; credit revenue reads the registries.
_PREMIUM_FINANCE_WORDING_PATTERNS = (
    re.compile(r"\bPREM(?:IUM)? ?FIN(?:ANCE|ANCING)?\b"),
    re.compile(r"\bINSPREMFIN\b"),
)


_NON_POSTED_PATTERNS = (
    re.compile(r"\bPENDING\b"),
    re.compile(r"\bNON POSTED\b"),
    re.compile(r"\bNOT POSTED\b"),
    re.compile(r"\bAUTHORI[ZS]ATION HOLD\b"),
    re.compile(r"\bMEMO POST(?:ING)?\b"),
)
_NSF_PATTERNS = (
    re.compile(r"\bNSF\b"),
    re.compile(r"\bNON ?SUFFICIENT FUNDS?\b"),
    re.compile(r"\bINSUFFICIENT FUNDS?\b"),
    re.compile(r"\b(?:RETURNED|RETURN) ITEM FEE\b"),
    re.compile(r"\bRETURNED (?:CHECK|CHEQUE) FEE\b"),
    re.compile(r"\bUNPAID ITEM FEE\b"),
    re.compile(r"\bITEM RETURNED\b.*\bNSF\b"),
    # 5.3 (2026-09-27): a returned item in the banks' abbreviated and French wording: TD's stop-payment return of
    # the business's own debit, and the French returned-item charge. A deposited item returned under a stop payment
    # is a reversal (_REFUND_REVERSAL_PATTERNS), as RETURNED DEPOSIT is.
    re.compile(r"\bRTN STOP PAY(?:T|MT|MENT)?\b|(?<!\bITEM )\bRETURNED STOP PAY(?:T|MT|MENT)?\b"),
    re.compile(r"\bEFFETS? (?:RET|RETOUR|RETOURNES?)\b"),
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
    # 5.3 (2026-09-27): bank card-purchase labels of the same kind (BofA MOBILE PURCHASE, CIBC RETAIL PURCHASE,
    # Regions PIN PURCHASE) and the French card-purchase forms the corpus prints (C/ACHAT, CIBC ACHAT AU DETAIL,
    # RBC ACHAT INTERAC, BMO ACHAT PAR CARTE and ACHAT EN LIGNE). A bare ACHAT is never read: 'ACHAT DE CREANCES'
    # is a factor's wording.
    re.compile(r"\b(?:RETAIL|MOBILE|PIN) PURCHASE\b"),
    re.compile(r"\bC ACHAT\b|\bACHAT (?:AU DETAIL|INTERAC|PAR CARTE|EN LIGNE)\b"),
)
_POS_EXCLUSION_PATTERNS = (
    re.compile(r"\bCASH ADVANCE\b"),
    re.compile(r"\bFEES?\b"),
    re.compile(r"\bSERVICE CHARGE\b"),
    re.compile(r"\bATM\b"),
)
_EXPLICIT_CARD_PURCHASE_PATTERNS = (
    re.compile(r"\b(?:DEBIT |VISA DEBIT |MASTER ?CARD DEBIT )?CARD PURCHASE\b"),
    re.compile(r"\bDEBIT CARD PURCHASE\b"),
    re.compile(r"\bBUSINESS DEBIT MERCH(?:ANT)?\b"),
)
_ATM_PATTERNS = (
    re.compile(r"\bATM\s+(?:CASH\s+)?WITHDRAW(?:AL)?\b"),
    re.compile(r"\bATM\s+(?:W D|WD|WDL)\b"),
    re.compile(r"\bCASH WITHDRAWAL\b.*\bATM\b"),
)
_FEE_PATTERNS = (
    re.compile(r"\bFEES?\b"),
    re.compile(r"\bSERVICE CHARGE\b"),
    re.compile(r"\bMERCHANT PROCESSING\b"),
    re.compile(r"\bPROCESSING CHARGE\b"),
    re.compile(r"\bMONTHLY CHARGE\b"),
    # Owner decision 2026-09-25: the bank's overdraft charge for an item is a fee,
    # even when it prints the item's payee (step 6 runs before the known payee).
    re.compile(r"\bOVERDRAFT CHARGES?\b"),
    # 5.3 (2026-09-27): bank charges printed without FEE: the SVC/SERV/CHG abbreviations, charges whose CHARGE is
    # not next to SERVICE/MONTHLY/OVERDRAFT/PROCESSING, RBC's Interac service-charge code SC, the ATM withdrawal
    # service charge, and the French FRAIS, never beside French loan or line-of-credit words. A bare CHARGE or CHG
    # is never a fee word (Capital One prints 'CHARGE <merchant>').
    re.compile(r"\b(?:SVC|SRVC?|SERV|SERVICES?) (?:CHARGES?|CHGS?|CHRGS?)\b|\bSERVICE (?:CHGS?|CHRGS?)\b"),
    re.compile(r"\b(?:OVERDRAWN|OVERDRAFT|HANDLING|BATCH) (?:CHARGES?|CHGS?|CHRGS?)\b"),
    re.compile(
        r"\b(?:EXTENDED OVERDRAFT|CONTINUOUS OD|OD|OVERDRAFT ITEM|PAID ITEM|PER ITEM|UNCOLLECTED FUNDS|COURTESY PAY"
        r"|WIRE|ACH ORIGINATION|CURRENCY HANDLING) (?:CHARGES?|CHGS?)\b"
    ),
    re.compile(r"\bINTERAC SC\b"),
    re.compile(r"\bW D SVC\b"),
    re.compile(r"^FRAIS\b(?!.*\b(?:FINANCEMENT|INTERETS?|PRET|MARGE|MCR)\b)"),
)
_TRANSFER_PATTERNS = (
    re.compile(r"\b(?:INTERNAL|ONLINE|ACCOUNT|BOOK|FUNDS?) TRANSFER\b"),
    re.compile(r"\bE TRANSFER\b"),
    re.compile(r"\bETRANSFER\b"),
    re.compile(r"\bXFER\b"),
    re.compile(r"\bZELLE\b"),
    re.compile(r"\bVENMO\b"),
    re.compile(r"\bCASH APP\b"),
)
_PAYROLL_PATTERNS = (
    re.compile(r"\bPAYROLL\b"),
    re.compile(r"\bPAYCHEX\b"),
    re.compile(r"\bADP\b"),
    re.compile(r"\bGUSTO\b"),
    re.compile(r"\bCERIDIAN\b"),
    re.compile(r"\bWAGES?\b"),
)
_TAX_PATTERNS = (
    re.compile(r"\bTAX(?:ES)?\b"),
    re.compile(r"\bIRS\b"),
    re.compile(r"\bCRA\b"),
    re.compile(r"\bCANADA REVENUE AGENCY\b"),
    re.compile(r"\bDEPARTMENT OF REVENUE\b"),
    re.compile(r"\bGST HST\b"),
)
_UTILITY_PATTERNS = (
    re.compile(r"\bUTILIT(?:Y|IES)\b"),
    re.compile(r"\bELECTRIC(?:ITY)?\b"),
    re.compile(r"\bWATER (?:BILL|UTILITY)\b"),
    re.compile(r"\bHYDRO\b"),
    re.compile(r"\bNATURAL GAS\b"),
    re.compile(r"\bTELEPHONE BILL\b"),
)
_RENT_PATTERNS = (
    re.compile(r"\bRENT\b"),
    re.compile(r"\bLANDLORD\b"),
    re.compile(r"\bPROPERTY RENTAL\b"),
)
#: POS precedence is unchanged (spec §4.3 step 5): a card row with lease,
#: equipment-financing or vehicle wording is not a POS purchase. These rows are
#: then decided by the step-8 descriptors.
_POS_LEASE_EXCLUSION_PATTERNS = (
    re.compile(r"\bLEASE(?:S|D| PAYMENT| PMT)?\b"),
    re.compile(r"\bEQUIPMENT (?:FINANCING|FINANCE|RENT|RENTAL|PAYMENT)\b"),
    re.compile(r"\bVEHICLE (?:FINANCING|FINANCE|LEASE|PAYMENT)\b"),
    re.compile(r"\bAUTO LEASE\b"),
)
_CREDIT_CARD_PATTERNS = (
    # One bank prints its ECS channel word between CREDIT CARD and PAYMENT.
    re.compile(r"\bCREDIT CARD (?:ECS )?(?:PAYMENT|PMT|PYMT)\b"),
    re.compile(r"\bCARDMEMBER SERVICES?\b"),
    re.compile(r"\b(?:VISA|MASTER ?CARD|AMEX|AMERICAN EXPRESS) (?:PAYMENT|PMT|PYMT|EPAYMENT)\b"),
    # The card network itself as the ACH originator, with a PAYMENT entry in its own
    # field (Bank of America's DES field; Chase's CO ENTRY DESCR field).
    re.compile(r"\b(?:VISA|MASTER ?CARD) DES (?:PAYMENT|PMT|PYMT|EPAYMENT)\b"),
    re.compile(r"\bORIG CO NAME (?:VISA|MASTER ?CARD) ORIG ID\b.*?\bCO ENTRY DESCR (?:PAYMENT|PMT|PYMT|EPAYMENT)\b"),
    re.compile(r"\bATB MASTER ?CARD\b"),
    re.compile(r"\bCAPITAL ONE\b.*\b(?:ONLINE PMT|CARD PAYMENT|PAYMENT)\b"),
    re.compile(r"\bCAPITAL ?ON ?TAP\b"),
    # A payment to a card account named only by its type.
    re.compile(r"\b(?:PAYMENT|PMT|PYMT) TO (?:CRD|CREDIT CARD|VSA|VISA|MASTER ?CARD|AMEX|AMERICAN EXPRESS)\b"),
    # 5.3 (2026-09-27): Navy Federal's memo for a recurring card payment.
    re.compile(r"\bCREDIT CARD RECUR(?:RING)?\b"),
)
#: Owner decision 2026-09-25 (step8_own_account_transfer_guard): a fintech transfer
#: between the holder's own accounts takes no step-8 rule, whatever the holder
#: named the sub-account.
_OWN_ACCOUNT_TRANSFER_GUARD = re.compile(r"^TRANSFER (?:TO|FROM) .+ (?:ACCOUNT )?TRANSFER (?:OUT|IN)$")
#: Owner decision 2026-09-25 (floor_plan_per_vehicle): a per-vehicle floor-plan payoff.
_FLOOR_PLAN_PAYOFF_PATTERN = re.compile(r"^PAYOFF (?:19|20)\d\d .*\bVIN\b")
#: A home-equity loan is a second mortgage (owner decision 2026-09-25). It has no
#: leading word boundary, so a run-together payee nickname matches too.
_MORTGAGE_PATTERNS = (
    re.compile(r"\bMORTGAGES?\b"),
    re.compile(r"HOME ?EQUITY ?LOANS?\b"),
    # 5.3 (2026-09-27): the mortgage payment abbreviations (MTG PYMT, MTGE PAYMENT).
    re.compile(r"\bMTGE? (?:PYMTS?|PMTS?|PAYMENTS?)\b"),
)
#: "AUTO PAYMENT" is a bank's autopay wording, not a car payment, so AUTO needs
#: loan, lease or finance wording while VEHICLE may carry PAYMENT.
_VEHICLE_FINANCING_PATTERNS = (
    re.compile(r"\b(?:AUTO|CAR) (?:LOAN|LOANS|LEASE|FINANCE|FINANCING)\b"),
    re.compile(r"\bVEHICLE (?:LOAN|LEASE|PAYMENT|PMT|PYMT|FINANCE|FINANCING)\b"),
)
#: Owner decision 2026-09-25 (student_loan_wording): an unnamed student-loan payee.
_STUDENT_LOAN_PATTERNS = (
    re.compile(r"\bSTUDENT ?LOANS?\b"),
    re.compile(r"\bSTDNT ?LOANS?\b"),
    re.compile(r"\bSTUDNT ?LOANS?\b"),
    re.compile(r"\bSTUDENT LN\b"),
)
#: D5 loan wording for the bank-name rule. French PRET is loan wording too (owner
#: decision 2026-09-25).
_LOAN_WORD_PATTERNS = (re.compile(r"\bLOANS?\b"), re.compile(r"\bPRETS?\b"))
#: D5: a transfer to the statement bank's own loan account.
_OWN_LOAN_TRANSFER_PATTERNS = (
    re.compile(r"\b(?:TRANSFER|TFR) TO (?:MY |YOUR )?LOANS?\b"),
    re.compile(r"\bLOAN (?:TRANSFER|TFR)\b"),
)
#: D5, owner decisions 2026-09-25. Another bank's loan whose originator is only a
#: generic bank or loan name: the statement bank is not the lender.
_OUTSIDE_BANK_LOAN_PATTERNS = (
    re.compile(r"\bORIG CO NAME COMMERCIAL LOAN\b"),
    re.compile(r"\bSAVINGS BANK LOAN (?:PAYMENT|PMT|PYMT)\b"),
)
#: The statement bank's own loan-payment wording, commercial-loan billing and
#: French loan wording, with no lender named. A bare PRET is never enough: it is
#: also a restaurant's name and a named funder's term-loan word.
_OWN_LOAN_PAYMENT_PATTERNS = (
    re.compile(r"\bAUTOMATIC LOAN (?:PAYMENT|PMT|PYMT|PAY)\b"),
    re.compile(r"\bAUTOMATED LOAN PAYMENT\b"),
    re.compile(r"\bPAYMENT TO (?:CMML |COMMERCIAL )?LOAN\b"),
)
_COMMERCIAL_LOAN_BILLING_PATTERNS = (
    re.compile(r"\b(?:INTEREST|PRINCIPAL|LATE CHARGE) PAYMENT CUSTOMER \d+ OBLIGATION \d+"),
)
_FRENCH_OWN_LOAN_PATTERNS = (
    re.compile(r"\bVERSEMENT PRET\b"),
    re.compile(r"\bINTERETS? SUR PRET\b"),
    re.compile(r"\b(?:VERS|INT) P A TERME\b"),
    re.compile(r"\bPMT PRET\b"),
    re.compile(r"\bPRET PMT\b"),
)
#: D3: PROPERTY RENTAL is landlord rent, never a flagged rental.
_LEASE_RENTAL_PATTERNS = (
    re.compile(r"\bLEAS(?:E|ES|ED|ING)\b"),
    re.compile(r"(?<!PROPERTY )\bRENTALS?\b"),
    re.compile(r"\bEQUIPMENT (?:RENT|PAYMENT)\b"),
)
#: A listed card issuer (CARD_ISSUER_CONTEXT_ALIASES) counts only with card or payment
#: wording. Owner decision 2026-09-25: Synchrony's PAYMNT, and a payment word glued to
#: the SEC label in Chase's field layout, are payment wording too.
_CARD_PAYMENT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:CREDIT CARD|CREDITCARD|CRCARD|CRD|CARD|CARDMEMBER)\b"),
    re.compile(
        r"\b(?:AUTOPAY|AUTO PAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)\b"
        r"|\b(?:AUTOPAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)SEC\b"
    ),
)
#: D4: equipment financing with no named company.
_EQUIPMENT_FINANCING_PATTERNS = (re.compile(r"\bEQUIPMENT (?:FINANCING|FINANCE)\b"),)
_CHECK_PATTERNS = (
    re.compile(r"\bCHECKS?\b"),
    re.compile(r"\bCHEQUES?\b"),
    # 5.3 (2026-09-27): the Canadian, credit-union and short cheque spellings, anchored at the start and with the
    # instrument's number, so a label ('BUS CHQ', '... SHARE DRAFT', Navy Federal's 'Paid To - <payee> Chk nnn')
    # never makes a row a cheque. Bare DRAFT is lender collection wording (AUTO DRAFT, WEB DRAFT).
    re.compile(r"^CHQ ?[0-9]"),
    re.compile(r"^SHARE DRAFTS? ?[0-9]"),
    re.compile(r"^DRAFT WITHDRAWAL DRAFT ?[0-9]"),
    re.compile(r"^(?:IMAGE |PAID )?CHK ?[0-9]"),
    re.compile(r"^CK ?[0-9]"),
)
_SUBSCRIPTION_PATTERNS = (
    re.compile(r"\bSUBSCRIPTION\b"),
    re.compile(r"\bMEMBERSHIP\b"),
)
_INSURANCE_TERM_PATTERNS = (
    re.compile(r"\bINSURANCE\b"),
    re.compile(r"\bPREMIUM\b"),
    re.compile(r"\bINS PREM\b"),
    re.compile(r"\bPOLICY\b"),
    re.compile(r"\bCOMMERCIAL INSURANCE\b"),
    re.compile(r"\bBUSINESS INSURANCE\b"),
    re.compile(r"\bLIABILITY COVERAGE\b"),
    re.compile(r"\bPROPERTY COVERAGE\b"),
    re.compile(r"\bVEHICLE COVERAGE\b"),
)
_DIRECT_DEBIT_LOAN_PATTERNS = (
    re.compile(r"\b(?:DIRECT DEB(?:IT)?|ACH DEBIT|BUSINESS PAD)\b.*\bLOANS?\b"),
    re.compile(r"\bLOANS?\b.*\b(?:DIRECT DEB(?:IT)?|ACH DEBIT|BUSINESS PAD)\b"),
)
#: D10: a loan servicer or debt collector whose funder is not in a registry.
#: (A servicer whose funder is known is an alias of that funder in the registry, via the C10 ledger.)
#: MCA SERVICING: owner decision 2026-09-25 (the words stay out of every alias table).
#: 5.3 (2026-09-27): the MCA SERVICING words, named by the fixed UNIDENTIFIED_MCA_SERVICER label (D10).
_MCA_SERVICING_PATTERN = re.compile(r"\bMCA SERVICING\b")
_SERVICER_COLLECTOR_PATTERNS = (
    re.compile(r"\bSERVICER\b"),
    re.compile(r"\bLOAN SERVICING\b"),
    re.compile(r"\bMCA SERVICING\b"),
    re.compile(r"\bDEBT (?:COLLECTION|COLLECTIONS|COLLECTOR|COLLECTORS)\b"),
    re.compile(r"\bCOLLECTION AGENCY\b"),
)
#: D5, owner decision 2026-09-25 (d5_unnamed_loan_payment): loan-payment wording
#: (normalization already reads LN as LOAN and PAYMT as PAYMENT) ...
_UNNAMED_LOAN_PAYMENT_PATTERNS = (
    re.compile(r"\bLOANS? (?:PAYMENT|PAYMENTS|PYMT|PMT|REPAYMENT)\b"),
    # 5.3 (2026-09-27): the statement bank's own loan interest, with no payee printed.
    re.compile(r"\bLOAN INTEREST\b"),
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
_FINANCING_SIGNAL_PATTERNS = (
    re.compile(r"\bLOAN\b"),
    re.compile(r"\bADVANCE\b"),
    re.compile(r"\bFINANC(?:E|ING|IAL)\b"),
    re.compile(r"\bFUND(?:ER|ING)\b"),
    re.compile(r"\bWORKING CAPITAL\b"),
    re.compile(r"\bMCA\b"),
)
_PAYMENT_MARKER_PATTERNS = (
    re.compile(r"\bPAYMENT\b"),
    re.compile(r"\bPMT\b"),
    re.compile(r"\bPYMT\b"),
    re.compile(r"\bREPAYMENT\b"),
    re.compile(r"\bREMITTANCE\b"),
    re.compile(r"\bACH DEBIT\b"),
    re.compile(r"\bDIRECT DEB(?:IT)?\b"),
    re.compile(r"\bBUSINESS PAD\b"),
)
#: 5.3 (2026-09-27): PAYROLL glued to an ACH entry-description suffix (a closed list, so a receiver name that only
#: contains PAYROLL is not read), payroll providers seen in the corpus, benefit administrators and retirement-plan
#: recordkeepers, and the French pay words. Provider, administrator and French words are read on the originator
#: segment only (_originator_segment): a holder named like one of them in INDN or IND NAME never hides its lender.
#: No new pattern fires on a row that names financing. 401(k) is left out (it prints in holder names).
_PAYROLL_GLUED_PATTERN = re.compile(r"\bPAYROLL(?:TAX(?:ES)?|TX|TS|DDS?|DEP|FEES?)\b")
_PAYROLL_PROVIDER_PATTERNS = (
    re.compile(r"\b(?:PATRIOT SOFTWARE|DATAPAY|PAYCOR|ONPAY|PAYWORKS|PAYCOM|PAYLOCITY)\b"),
    re.compile(r"\b(?:HEALTH ?EQUI(?:TY)?|WAGEWORKS|TASC|ASCENSUS|HUMAN INTEREST|GUIDELINE RETIRE(?:MENT)?)\b"),
    re.compile(r"\bPAIE\b|\bSALAIRES?\b"),
)
#: 5.3 (2026-09-27): a loan from the business's own shareholder, owner or director, repaid to them: no lender is
#: named. The loan producers never take it (debits only, and only when the row names no organisation). MEMBER and
#: PARTNER are left out: a funder can be named '... Partners'.
_RELATED_PARTY_LOAN_PATTERNS = (
    re.compile(r"\b(?:SHAREHOLDERS?|OWNERS?|DIRECTORS?) LOANS?\b"),
    re.compile(r"\bDUE TO (?:SHAREHOLDERS?|OWNERS?)\b"),
)

_REVERSAL_CANCELLATION_CREDIT_PATTERNS = (
    *_REFUND_REVERSAL_PATTERNS,
    re.compile(r"\b(?:E TRANSFER|ETRANSFER|TRANSFER) (?:RETURNED|CANCEL(?:LED|ED)?|CNCL)\b"),
    re.compile(r"\b(?:RETURNED|CANCEL(?:LED|ED)?|CNCL) (?:E TRANSFER|ETRANSFER|TRANSFER)\b"),
    re.compile(r"\bCNCL\b"),
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

_INTERNAL_ACCOUNT_SOURCE = (
    r"(?:ACCOUNTS?|CHK|CHECKING|CK|SAV|SAVINGS|SV|SHARES?|MMA|"
    r"MONEY MARKET|PCA|(?:SUB )?RESERVE ACCOUNTS?)"
)
_INTERNAL_TRANSFER_CREDIT_PATTERNS = (
    re.compile(r"\b(?:INTERNAL|ACCOUNT|BOOK|FUNDS?) TRANSFER\b"),
    re.compile(r"\bTRANSFER (?:FROM|BETWEEN) (?:OWN|MY|INTERNAL) ACCOUNTS?\b"),
    re.compile(rf"\b(?:TRANSFER|XFER|TFR) FROM {_INTERNAL_ACCOUNT_SOURCE}\b"),
    re.compile(
        rf"\b(?:BRANCH|ONLINE|MOBILE|INTERNET|HOME|BUSINESS ONLINE|TELEPHONE)"
        rf"(?: BANKING)?(?: ACCOUNT)? (?:TRANSFER|XFER)(?: TRANSFER)? FROM "
        rf"(?:{_INTERNAL_ACCOUNT_SOURCE}|X+\d*|\d{{3,}})\b"
    ),
    re.compile(r"\bTRANSFER DEPOSIT FROM (?:ACCOUNT )?(?:X+\d*|\d{3,})\b"),
    re.compile(r"\bTFR FROM (?:X+\d*|\d{3,})\b.*\bTRANSFER DEPOSIT\b"),
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
_NON_REVENUE_CREDIT_PATTERNS = (
    re.compile(
        r"\b(?:LOAN|BUSINESS LOAN|MCA|MERCHANT CASH ADVANCE|FINANCING) "
        r"(?:FUNDING|PROCEEDS|DISBURSEMENT|ADVANCE)\b"
    ),
    re.compile(r"\b(?:BUSINESS |COMMERCIAL )?LOANS?\b"),
    re.compile(r"\b(?:MCA|MERCHANT CASH ADVANCES?)\b"),
    re.compile(r"\bCASH ADVANCE\b"),
    re.compile(r"\b(?:LOAN|MCA) ORIGINATION CREDIT\b"),
    *_INTERNAL_TRANSFER_CREDIT_PATTERNS,
    re.compile(r"\bOWNER(?:S)? (?:CONTRIBUTION|CAPITAL|DEPOSIT|TRANSFER)\b"),
    re.compile(r"\bSHAREHOLDER (?:CONTRIBUTION|LOAN|DEPOSIT)\b"),
    re.compile(r"\bCAPITAL CONTRIBUTION\b"),
    re.compile(r"\bINSURANCE (?:PROCEEDS|CLAIM|PAYMENT)\b"),
    re.compile(r"\bTAX REFUND\b"),
    re.compile(r"\b(?:IRS|CRA|REVENUE AGENCY) REFUND\b"),
    re.compile(
        r"\b(?:CASH ?BACK|CASH ?REWARDS?|CARD REWARDS?|CREDIT CARD REWARDS?)"
        r"(?: CREDIT|REDEMPTION|REBATE)?\b"
    ),
    re.compile(r"\bINTEREST (?:CREDIT(?:ED)?|PAID|PAYMENT|DEPOSIT|EARNED)\b"),
    re.compile(r"\bCREDIT INTEREST\b"),
    re.compile(r"\b(?:BANK |SERVICE |ACCOUNT )?FEES? (?:REFUND|REBATE|REVERSAL|CREDIT)\b"),
    re.compile(r"\bDAILY CAP OF \d+ FEES?\b"),
    re.compile(r"\bINVEST(?:MENT)? TRANSFER\b"),
    re.compile(r"\b(?:ASSET|VEHICLE|EQUIPMENT|PROPERTY) SALE (?:PROCEEDS|DEPOSIT)\b"),
    re.compile(r"\bPROCEEDS FROM (?:ASSET|VEHICLE|EQUIPMENT|PROPERTY) SALE\b"),
)
_VERIFIED_REVENUE_CREDIT_PATTERNS = (
    re.compile(r"\bMRCH\d{5,}\b"),
    re.compile(r"\bMERCHANT (?:PROCESSOR )?(?:SETTLEMENT|DEPOSIT|PAYOUT)\b"),
    re.compile(r"\bCARD SALES? (?:DEPOSIT|SETTLEMENT|PAYOUT)\b"),
    re.compile(r"\bCUSTOMER\b.*\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b"),
    re.compile(r"\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b.*\bCUSTOMER\b"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
    re.compile(r"\bMARKETPLACE (?:PAYOUT|SETTLEMENT)\b"),
    re.compile(r"\bH(?:C|E)?CLAIMPMT\b"),
    re.compile(r"\bEDIRPAY\b"),
    re.compile(r"\bMERCHANT BANK(?:CD|CARD|ED) DEPOSIT\b"),
    re.compile(r"\bMTOT DEP\b"),
)
_OPERATING_CREDIT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:SETTLEMENT|PAYOUT|DISBURSEMENT)\b"),
    re.compile(r"\bMERCHANT (?:CREDIT|DEPOSIT|PAYMENT|BATCH|PROCESSING)\b"),
    re.compile(r"\bCARD SALES?\b"),
    re.compile(r"\bSALES? (?:CREDIT|DEPOSIT|PROCEEDS)\b"),
    re.compile(r"\bDIRECT DEPOSIT MISC(?:ELLANEOUS)? PAYMENTS?\b"),
    re.compile(r"\bACH (?:CREDIT|SETTLEMENT|PAYOUT)\b"),
    re.compile(r"\bMARKETPLACE (?:PAYMENT|PAYOUT|SETTLEMENT)\b"),
    re.compile(r"\bBATCH (?:CREDIT|DEPOSIT|SETTLEMENT)\b"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
)
_UNVERIFIED_DEPOSIT_CREDIT_PATTERNS = (
    re.compile(r"\bMOBILE DEPOSIT\b"),
    re.compile(r"\bACH CREDIT\b"),
    re.compile(r"\bDIRECT DEPOSIT\b"),
    re.compile(r"\bE TRANSFER (?:RECEIVED|DEPOSIT)\b"),
    re.compile(r"\bETRANSFER (?:RECEIVED|DEPOSIT)\b"),
    re.compile(r"\b(?:CHECK|CHEQUE) DEPOSIT\b"),
    re.compile(r"\bCASH DEPOSIT\b"),
    re.compile(r"\bDEPOSIT\b"),
)
_BUSINESS_ACCOUNT_PATTERNS = (
    re.compile(r"\bBUSINESS\b"),
    re.compile(r"\bCOMMERCIAL\b"),
    re.compile(r"\bOPERATING\b"),
    re.compile(r"\bMERCHANT\b"),
)
_OPERATING_PLATFORM_DEBIT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:PROCESSING|MERCHANT|PLATFORM|SERVICE) FEES?\b"),
    re.compile(r"\bCOMMISSIONS?\b"),
    re.compile(r"\bCHARGEBACK\b"),
    re.compile(r"\bSETTLEMENT ADJUSTMENT\b"),
)
_PAIR_FAMILY_PATTERNS = (
    re.compile(r"\bE TRANSFER\b"),
    re.compile(r"\bETRANSFER\b"),
    re.compile(r"\bCHECK\b"),
    re.compile(r"\bCHEQUE\b"),
    re.compile(r"\bACH\b"),
    re.compile(r"\bWIRE\b"),
)


def _matches_any(text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) is not None for pattern in patterns)


def prints_internal_transfer_designation(description: str) -> bool:
    """Does this printed row DESIGNATE a movement between the member's own accounts?

    R-d's fourth clause, and the only place it is decided. A movement is
    INTERNAL only when the paper prints such a designation on at least one of
    the two legs; an arithmetic coincidence — same day, same cent, opposite
    sign — never sets it, because a member who deposits a sum into checking on
    the day they withdraw the same sum from savings for an unrelated purpose
    produces exactly that signature, and flagging it removes a printed deposit
    from a funder's view of the business by an inference (design §3.2).

    **Decided by `_INTERNAL_TRANSFER_CREDIT_PATTERNS` ALONE.** Every member of
    that tuple names one member's OWN accounts as the source or the
    destination — `TRANSFER FROM SAVINGS`, `SH TO SH`, `ACCOUNT TO ACCOUNT`,
    `TRANSFER FROM <masked> TO <masked>`.

    **`_TRANSFER_PATTERNS` is REFUSED as evidence for this question, and the
    refusal is a ruling rather than a preference** (Gustavo, 2026-08-30,
    BATCH9_TRANSITION §8.14). That tuple carries `ZELLE`, `VENMO`, `CASH APP`,
    `E TRANSFER`, `ETRANSFER` and `XFER`, and its one production use builds a
    `strong_non_lender_exclusion` whose own reason string says the descriptor
    identifies "an account, online, or person-to-person transfer" — so it
    answers *this row is not a lender debit*, never *this row is an internal
    movement*. A payment to or from another PERSON is not evidence that money
    moved inside one member's ledger set, and admitting it would flag the pair
    and then delete the matching printed deposit from package gross deposits,
    deposit counts, revenue and the withholding denominator. Measured over the
    archive's 47 candidate pairs: 43 carry an internal designation, 3 are
    admitted only by the peer-to-peer vocabulary and 1 prints nothing at all,
    and all 4 stay refused.

    The description is normalised by this module's own normaliser first, so the
    question is asked of exactly the text every other classification in this
    module is decided on.
    """
    return _matches_any(
        normalize_transaction_description(description),
        _INTERNAL_TRANSFER_CREDIT_PATTERNS,
    )


def _classify_credit_revenue(
    text: str,
    amount: float,
    *,
    posted: bool,
    account_name: str | None,
    direction_consistent: bool,
    bank: str | None = None,
) -> _RevenueDecision | None:
    if amount <= 0 or not posted:
        return None

    if not direction_consistent:
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "direction_conflict",
            None,
            "source_direction_conflicts_with_signed_amount",
            0.20,
            "The source direction conflicts with the signed amount, so the credit requires review.",
            context_signals=("positive_amount", "direction_conflict"),
        )
    if _matches_any(text, _REVERSAL_CANCELLATION_CREDIT_PATTERNS):
        return _RevenueDecision(
            "non_revenue",
            None,
            "reversal_cancellation_exclusion",
            None,
            "returned_cancelled_reversed_or_provisional_credit",
            0.99,
            "Credit is a return, cancellation, reversal, refund, correction, chargeback, or provisional credit.",
            context_signals=("credit_direction", "strong_non_revenue_descriptor"),
        )

    # A premium-finance credit keeps the insurance credit treatment (spec §4.2).
    insurance_match = _insurance_registry_match(text)
    if insurance_match is not None:
        entity, alias, _premium_finance = insurance_match
        return _RevenueDecision(
            "non_revenue",
            entity,
            "insurance_provider_credit_exclusion",
            alias,
            "insurance_proceeds_or_refund",
            0.99,
            f"Credit matched insurance provider alias '{alias}' and is not operating revenue.",
            context_signals=("credit_direction", "insurance_provider"),
        )
    # Spec §4.4 / D1: a credit from a financing group is proceeds. It is decided
    # before the operating-revenue registry, and group aliases are
    # financing-specific (SQUARE CAPITAL, never bare SQUARE), so a platform's
    # sales settlement still reaches the operating registry below. Card-issuer
    # and lease/rental payees never apply to credits, and neither does a
    # payout-credit entity (owner decision 2026-09-25).
    financing_match = _financing_proceeds_payee(text)
    if financing_match is not None:
        return _RevenueDecision(
            "non_revenue",
            financing_match.entity,
            "financing_proceeds_credit",
            financing_match.alias,
            "financing_proceeds_credit",
            0.99,
            (
                f"Credit matched maintained {_state_words(financing_match.state)} alias "
                f"'{financing_match.alias}'; financing proceeds are not revenue."
            ),
            context_signals=("credit_direction", "financing_proceeds"),
        )
    # D1 by descriptor (owner decisions 2026-09-25). `_descriptor_proceeds` keeps
    # the potential registry and the strong non-revenue rule below ahead of a
    # line-of-credit draw or a floor-plan advance.
    descriptor_proceeds = _descriptor_proceeds(text)
    if descriptor_proceeds is not None:
        rule, names_bank = descriptor_proceeds
        return _RevenueDecision(
            "non_revenue",
            (bank or None) if names_bank else None,
            "financing_proceeds_credit",
            None,
            rule,
            0.97,
            f"The credit's descriptor identifies financing proceeds ({_state_words(rule)}); they are not revenue.",
            context_signals=("credit_direction", "financing_proceeds"),
        )
    potential_lender_match = registry_match(text, POTENTIAL_LENDER_ALIASES)
    if potential_lender_match is not None:
        entity, alias = potential_lender_match
        return _RevenueDecision(
            "non_revenue",
            entity,
            "potential_lender_registry_credit_exclusion",
            alias,
            "potential_lender_funding_credit",
            0.95,
            f"Credit matched potential lender alias '{alias}' and is excluded from revenue.",
            context_signals=("credit_direction", "potential_lender_source"),
        )
    if _matches_any(text, _NON_REVENUE_CREDIT_PATTERNS):
        return _RevenueDecision(
            "non_revenue",
            None,
            "strong_non_revenue_rule",
            None,
            "non_operating_credit",
            0.97,
            (
                "Credit matched identifiable financing, own-account transfer, reward, "
                "interest, contribution, or other non-operating proceeds evidence."
            ),
            context_signals=("credit_direction", "strong_non_revenue_descriptor"),
        )

    revenue_match = registry_match(text, OPERATING_REVENUE_SOURCE_ALIASES)
    if revenue_match is not None:
        entity, alias = revenue_match
        source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
        has_operating_context = _matches_any(text, _OPERATING_CREDIT_CONTEXT_PATTERNS)
        business_account = _matches_any(
            normalize_transaction_description(account_name or ""),
            _BUSINESS_ACCOUNT_PATTERNS,
        )
        signals = ["credit_direction", "maintained_operating_source"]
        if has_operating_context:
            signals.append("settlement_or_payout_descriptor")
        if business_account:
            signals.append("business_account")
        if has_operating_context:
            return _RevenueDecision(
                "verified_revenue",
                entity,
                "operating_source_with_credit_context",
                alias,
                "verified_operating_source_credit",
                0.98 if business_account else 0.96,
                (
                    f"Credit matched maintained {source_type or 'operating-source'} alias "
                    f"'{alias}' with settlement, payout, or deposit context."
                ),
                source_type=source_type,
                context_signals=tuple(signals),
            )
        return _RevenueDecision(
            "unverified_deposit",
            entity,
            "operating_source_requires_context",
            alias,
            "operating_source_without_payout_context",
            0.70,
            (
                f"Credit matched maintained {source_type or 'operating-source'} alias "
                f"'{alias}', but the row needs recurrence or related operating activity to verify revenue."
            ),
            source_type=source_type,
            context_signals=tuple(signals),
        )
    if _matches_any(text, _VERIFIED_REVENUE_CREDIT_PATTERNS):
        return _RevenueDecision(
            "verified_revenue",
            None,
            "operating_income_descriptor",
            None,
            "verified_operating_income_descriptor",
            0.93,
            "Credit has a customer-payment, merchant-settlement, card-sales, invoice, or verified business-deposit descriptor.",
            context_signals=("credit_direction", "operating_income_descriptor"),
        )
    if _matches_any(text, _UNVERIFIED_DEPOSIT_CREDIT_PATTERNS):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "ambiguous_credit_descriptor",
            None,
            "deposit_source_requires_review",
            0.60,
            "The credit is a deposit or incoming transfer without enough evidence to confirm operating revenue.",
            context_signals=("credit_direction", "generic_deposit_descriptor"),
        )
    return _RevenueDecision(
        "unverified_deposit",
        None,
        "unidentified_posted_credit",
        None,
        "unknown_credit_source_requires_review",
        0.40,
        "The posted credit source is not identified strongly enough to confirm or exclude revenue.",
        context_signals=("credit_direction", "unidentified_source"),
    )


#: Channel and payment words that never name a payee (D11).
_ENTITY_NOISE = {
    "ACH", "EFT", "DEBIT", "DIRECT", "DEB", "EXTERNAL", "WITHDRAWAL", "ELECTRONIC",
    "PREAUTHORIZED", "PREAUTH", "AUTOMATIC", "AUTO", "ORIG", "ORIGINATOR", "NAME",
    "DESCR", "DESCRIPTION", "ENTRY", "DETAIL", "PAYMENT", "PAYMENTS", "PAY", "PMT",
    "PYMT", "REPAYMENT", "REMITTANCE", "PAD", "BUSINESS", "ONLINE", "WEB", "CCD", "PPD",
    "LOAN", "MCA", "TO", "FROM", "FOR", "TFR", "XFER", "TRANSFER", "MISC",
    # 5.3: the paid-to label a bank prints before the payee (Navy Federal "Paid To -").
    "PAID",
}
#: Financing words that describe the payment, not the payee, when they lead the name.
_GENERIC_ENTITY_WORDS = {"FINANCE", "FINANCING", "FUNDING", "CAPITAL", "FUNDER", "ADVANCE"}
#: D11: a name is published only when one of these organisation cues survives.
#: The last eight are the registry-style company tokens (legal-form suffixes).
#: 5.3 (2026-09-27): CO is no cue (it is also Colorado's state code: 'NAME, CITY, CO'); COMPANY stays one.
_ORGANISATION_CUES = {
    "LLC", "INC", "CORP", "FUNDING", "CAPITAL", "FINANCIAL", "FINANCE", "BANK",
    "CREDIT", "LENDING", "ADVANCE", "GROUP", "HOLDINGS", "SERVICES",
    "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
}
_ENTITY_MONTHS = {
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "SEPT", "OCT", "NOV",
    "DEC", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
    "OCTOBER", "NOVEMBER", "DECEMBER",
}
_ENTITY_ACRONYMS = {"ACH", "BDC", "CMCA", "EFT", "LLC", "LLP", "LP", "MCA", "PLLC", "SBA", "SNAP"}
#: Labels that introduce the originator's name: the label goes, the name stays.
_ENTITY_NAME_LABELS = re.compile(r"\b(?:ORIG CO NAME|ORIGINATOR NAME|COMPANY NAME|CO NAME)\b")
#: D11: ACH field segments. Everything from the first one on is dropped, so a
#: name is never built from ID, INDN, IND NAME, CO ID, TRACE or similar fields.
_ACH_FIELD_SEGMENT = re.compile(
    r"\b(?:DES|DESC|DESCR|ORIG ID|CO ID|IND ID|IND NAME|INDN|IND|ID|TRACE|SEC|EED|TRN|"
    # 5.3 (2026-09-27): Truist's receiver field label, Huntington's instruction field and the wire fields.
    r"CONF|REF|MEMO|CUST|TYPE|CUSTOMER ID|INSTR|SRF|RFB|IMAD)\b"
)
_MASKED_TOKEN = re.compile(r"X{2,}[A-Z0-9]*")
_MAX_ENTITY_TOKENS = 4
#: 5.3: connectors that never end a name (a name cut by the four-word cap: 'BOKF NATIONAL BANK OF').
_TRAILING_CONNECTORS = frozenset({"OF", "AND", "THE", "DE", "DU", "DES"})
#: 5.3 (2026-09-27): bank template words printed before the payee: removed before the payee words start, so two
#: recipients paid through one template are never one payee (D11) and a template is never a name. Read at the start
#: of the normalized row. 'ACH CORP DEBIT' is Truist's; its name then passes _truist_name_is_published.
_PAYEE_TEMPLATE_PREFIX = re.compile(
    r"^(?:(?:PMNT|PAYMENT) SENT|CORPORATE ACH|DOMESTIC ASSIST WIRE|HIP CREDIT SENT(?: TO)?|RETAIL PURCHASE"
    r"|DBCRD PUR AP(?: AUT)?(?: [0-9]+)?(?: VISA DDA PUR(?: AP)?)?|ACH CORP (?:DEBIT|CREDIT))\b"
)
_TRUIST_CORP_PREFIX = re.compile(r"^ACH CORP (?:DEBIT|CREDIT)\b")
#: 5.3: Truist prints no padding, so a short originator lets the receiver's words into the 16-character company
#: field. A Truist name is published only when a whole legal-form word lies inside those 16 characters.
_TRUIST_COMPANY_FIELD = 16
#: 5.3: a wire's beneficiary starts after BNF (Wells Fargo /Bnf=, Bank of America BNF:), else after the account
#: label of Chase's 'Wire Transfer Via: <bank> A/C: <beneficiary>'.
_WIRE_BENEFICIARY_PATTERNS = (
    re.compile(r"\bBNF(?: FFC)?\b"),
    re.compile(r"\bWIRE TRANSFER VIA\b.*?\bA C\b"),
)
#: 5.3: the receiver fields. The account holder's own name prints there (Bank of America INDN, Chase IND NAME).
_RECEIVER_NAME_FIELD = re.compile(r"\b(?:INDN|IND NAME|IND ID)\b")
#: 5.3 (owner ruling 2026-09-27): a receiver-name field with its value, up to the next ACH field, removed before the
#: debt-relief table is read: the account holder's own name never makes a row debt relief.
_RECEIVER_FIELD_VALUE = re.compile(
    r"\b(?:INDN|IND NAME|RECEIVER NAME|RECV NAME)\b.*?(?=\b(?:CO ID|TRN|TRACE|PPD|CCD|WEB|CTX|TEL|ARC|BOC)\b|$)"
)
#: 5.3: bill-payment prefix words a bank prints before the payee. The leading payee words start after them.
_LEADING_PREFIX_WORDS = frozenset({
    "BILL", "BILLS", "PRE", "AUTHORIZED", "AUTHORISED", "RECURRING", "RECUR", "INTERNET", "BANKING", "PAIEMENT",
    "FACTURE", "BM", "CABLE", "TV", "TELEPHONE", "PCS", "SVC", "ON",
})


def _is_reference_token(token: str) -> bool:
    return (
        any(character.isdigit() for character in token)
        or _MASKED_TOKEN.fullmatch(token) is not None
        or token in _ENTITY_MONTHS
    )


def _payee_region(text: str) -> str:
    """D11: the payee part of a normalized row: originator-name labels removed, cut at the first ACH field segment
    (so never an ID, INDN, IND NAME, CO ID or TRACE field). `_unknown_payee_tokens` reads its words."""
    text = _ENTITY_NAME_LABELS.sub(" ", text)
    segment = _ACH_FIELD_SEGMENT.search(text)
    return text[: segment.start()] if segment is not None else text


def _row_before_receiver(text: str) -> str:
    """5.3: the normalized row up to its first receiver field, so the account holder's own name never decides a D6
    skip. The entry-description fields stay (DES:FACTS, DES:CHILD SUPP). A row with no receiver field is read whole:
    a label-less format prints the holder unmarked, which the payee-word readers cover instead."""
    return _RECEIVER_NAME_FIELD.split(text, 1)[0]


def _leading_payee_words(text: str) -> str:
    """5.3: the payee's leading words: the payee region after channel words, bill-payment prefix words and any
    leading reference, up to the next reference token. A word printed after the payee's own name (a receiver in a
    label-less format) is never a leading word."""
    words: list[str] = []
    for token in _payee_region(text).split():
        if not words:
            if token in _ENTITY_NOISE or token in _LEADING_PREFIX_WORDS or _is_reference_token(token):
                continue
        elif _is_reference_token(token):
            break
        words.append(token)
    return " ".join(words)


def _originator_segment(text: str) -> str:
    """5.3 (payroll N1): D11's reading of the originator without the four-word cap and keeping channel words: the
    payee region up to the first reference token after a name word. Provider and benefit-administrator names are
    read here, never in a receiver field."""
    words: list[str] = []
    started = False
    for token in _payee_region(text).split():
        if _is_reference_token(token):
            if started:
                break
            continue
        words.append(token)
        started = started or (token not in _ENTITY_NOISE and len(token) > 1)
    return " ".join(words)


def _is_payroll_provider_row(text: str) -> bool:
    """5.3: a payroll provider, benefit administrator or French pay row (payroll N1 and N2)."""
    if _names_financing(text):
        return False
    return _PAYROLL_GLUED_PATTERN.search(text) is not None or _matches_any(
        _originator_segment(text), _PAYROLL_PROVIDER_PATTERNS
    )


def _wire_beneficiary(text: str) -> str | None:
    """5.3 (2026-09-27): the text after a wire's beneficiary label, or None for a row that is no such wire."""
    for pattern in _WIRE_BENEFICIARY_PATTERNS:
        found = pattern.search(text)
        if found is not None:
            return text[found.end():]
    return None


def _unknown_payee_tokens(text: str) -> tuple[str, ...]:
    """D11: the payee words of an unknown counterparty, at most four.

    Removes originator-name labels, cuts at the first ACH field segment, drops
    channel words, single letters and leading financing words, and stops at the
    first reference token (digits, a masked number or a month) once a name has
    started, so a person's name printed after the references never joins it.

    5.3 (2026-09-27): a name ends at its first legal-form word after the first word; a leading AND and a trailing
    connector are dropped. A bank template prefix is removed first. A wire is read from its beneficiary, where a
    name ends at its first organisation cue after the first word.
    """
    beneficiary = _wire_beneficiary(text)
    region = _payee_region(beneficiary if beneficiary is not None else _PAYEE_TEMPLATE_PREFIX.sub(" ", text, count=1))
    tokens: list[str] = []
    for token in region.split():
        if token in _ENTITY_NOISE or len(token) == 1:
            continue
        if _is_reference_token(token):
            if tokens:
                break
            continue
        if not tokens and (token in _GENERIC_ENTITY_WORDS or token == "AND"):
            continue
        tokens.append(token)
        if len(tokens) > 1 and (
            token in _LEGAL_FORM_SUFFIXES or (beneficiary is not None and token in _ORGANISATION_CUES)
        ):
            break
        if len(tokens) == _MAX_ENTITY_TOKENS:
            break
    while tokens and tokens[-1] in _TRAILING_CONNECTORS:
        tokens.pop()
    return tuple(tokens)


def _names_an_organisation(tokens: Sequence[str]) -> bool:
    """D11 and 5.3 (2026-09-27): a cue names an organisation, except a legal-form word printed first (CORP of
    'CORP FABRIKAM ...'); a name made only of cue words ('BANK', 'CORP') names none."""
    if all(token in _ORGANISATION_CUES for token in tokens):
        return False
    return any(
        token in _ORGANISATION_CUES and (position > 0 or token not in _LEGAL_FORM_SUFFIXES)
        for position, token in enumerate(tokens)
    )


def _unknown_payee_name(tokens: Sequence[str]) -> str | None:
    """D11: the published name, the unidentified label, or None when no payee is named."""
    if not tokens:
        return None
    if not _names_an_organisation(tokens):
        return UNIDENTIFIED_LENDER_OBLIGATION
    return " ".join(token if token in _ENTITY_ACRONYMS else token.title() for token in tokens)


def _truist_name_is_published(text: str) -> bool:
    """5.3 (2026-09-27): on a Truist 'ACH CORP DEBIT' row, whether a whole legal-form word lies inside the first 16
    characters of the payee words, the width of the company-name field. True for every other row."""
    if not _TRUIST_CORP_PREFIX.match(text):
        return True
    words: list[str] = []
    for token in _payee_region(_PAYEE_TEMPLATE_PREFIX.sub(" ", text, count=1)).split():
        if not words and (token in _ENTITY_NOISE or len(token) == 1 or _is_reference_token(token)):
            continue
        words.append(token)
    printed = " ".join(words)
    field = printed[:_TRUIST_COMPANY_FIELD].split()
    if len(printed) > _TRUIST_COMPANY_FIELD and printed[_TRUIST_COMPANY_FIELD] != " ":
        field = field[:-1]  # the field's edge cut the last word
    return any(word in _LEGAL_FORM_SUFFIXES for word in field)


def _unknown_entity_for_text(text: str, tokens: Sequence[str]) -> str | None:
    """D11: the published name of the payee words `tokens` read from the normalized row `text` (5.3: a Truist name
    only through its company field)."""
    name = _unknown_payee_name(tokens)
    if name not in (None, UNIDENTIFIED_LENDER_OBLIGATION) and not _truist_name_is_published(text):
        return UNIDENTIFIED_LENDER_OBLIGATION
    return name


def _canonical_unknown_entity(text: str) -> str | None:
    return _unknown_entity_for_text(text, _unknown_payee_tokens(text))


def _build_record(
    *,
    description: str,
    text: str,
    classification: ClassificationState,
    amount: float,
    date_value: str,
    bank: str | None,
    account: str | None,
    account_name: str | None,
    source_direction: str | None,
    direction_consistent: bool,
    source_page: int | None,
    source_location: str | None,
    canonical_entity: str | None = None,
    match_method: str,
    matched_alias: str | None = None,
    matched_rule: str | None = None,
    confidence_score: float,
    reason: str,
    is_posted: bool = True,
    review_required: bool = False,
    contributes_to_lender_credit_exclusion: bool = False,
    flagged_group: str | None = None,
) -> TransactionClassification:
    is_debit = amount < 0
    contributes_lender = classification == "confirmed_lender" and is_debit and is_posted
    contributes_potential = classification == "potential_lender" and is_debit and is_posted
    contributes_insurance = classification == "insurance" and is_debit and is_posted
    flag_group = FLAG_GROUP_BY_STATE.get(classification)
    # A flag-group state names its own group. Premium financing is the one group
    # a rule passes in, on an insurance row (C1, C4).
    group_key = flag_group.key if flag_group is not None else flagged_group
    # A posted debit of a flag group counts in the flagged totals, and so does a
    # posted credit of a group whose credits are flagged revenue (owner ruling
    # 2026-09-26: factoring; C5 count_credited and total_credited).
    contributes_flagged = group_key is not None and is_posted and (
        is_debit or (amount > 0 and classification in _FLAGGED_REVENUE_CREDIT_STATES)
    )
    revenue = _classify_credit_revenue(
        text,
        amount,
        posted=is_posted,
        bank=bank,
        account_name=account_name,
        direction_consistent=direction_consistent,
    )
    revenue_state = revenue.classification if revenue is not None else None
    revenue_flags = revenue_contribution_flags(revenue_state)
    # Contract C4, spec §4.4: a credit whose revenue decision is financing proceeds (D1) is
    # also excluded from eligible deposits, whichever rule named the row. A transfer or an
    # insurance term can claim a financing group's credit before step 7. A payout-credit
    # entity's credit and a premium-finance payee's credit never reach this revenue decision.
    if revenue is not None and revenue.match_method == "financing_proceeds_credit":
        contributes_to_lender_credit_exclusion = True
    return TransactionClassification(
        original_description=description,
        normalized_description=text,
        classification=classification,
        date=date_value,
        amount=amount,
        direction="debit" if amount < 0 else "credit",
        bank=bank,
        account=account,
        account_name=account_name,
        source_direction=source_direction,
        direction_consistent=direction_consistent,
        source_page=source_page,
        source_location=source_location,
        canonical_entity=canonical_entity,
        match_method=match_method,
        matched_alias=matched_alias,
        matched_rule=matched_rule,
        confidence_score=confidence_score,
        reason=reason,
        is_posted=is_posted,
        review_required=review_required,
        flagged_group=group_key,
        revenue_classification=revenue_state,
        revenue_initial_classification=revenue_state,
        revenue_canonical_entity=revenue.canonical_entity if revenue else None,
        revenue_match_method=revenue.match_method if revenue else None,
        revenue_matched_alias=revenue.matched_alias if revenue else None,
        revenue_matched_rule=revenue.matched_rule if revenue else None,
        revenue_confidence_score=revenue.confidence_score if revenue else None,
        revenue_reason=revenue.reason if revenue else None,
        revenue_source_type=revenue.source_type if revenue else None,
        revenue_context_signals=revenue.context_signals if revenue else (),
        revenue_review_required=revenue_state == "unverified_deposit",
        revenue_review_status=(
            "pending" if revenue_state == "unverified_deposit"
            else "not_required" if revenue_state else None
        ),
        contributes_to_lender_count=contributes_lender,
        contributes_to_potential_lender_count=contributes_potential,
        contributes_to_lender_totals=contributes_lender,
        contributes_to_withholding_rate=contributes_lender,
        contributes_to_potential_lender_totals=contributes_potential,
        contributes_to_potential_withholding_exposure=contributes_potential,
        contributes_to_insurance_totals=contributes_insurance,
        contributes_to_flagged_totals=contributes_flagged,
        **revenue_flags,
        contributes_to_lender_credit_exclusion=contributes_to_lender_credit_exclusion,
        is_ach=_ACH_TOKEN.search(text) is not None,
        is_check=_matches_any(text, _CHECK_PATTERNS),
        is_loan_payment=_matches_any(text, _EXPLICIT_REPAYMENT_PATTERNS),
        is_pos_context=_matches_any(text, _POS_PATTERNS),
    )


def _state_words(state: str) -> str:
    return state.replace("_", " ")


#: D9: LOC wording. Also the first step-8 descriptor rule (Task 8).
_LINE_OF_CREDIT_PATTERNS = (
    re.compile(r"\bLOC\b"),
    re.compile(r"\bLINE OF CREDIT\b"),
)
#: D9: known-payee groups that LOC wording moves to lines of credit.
_LOC_OVERRIDE_STATES = frozenset({"confirmed_lender", "alternative_position", "line_of_credit"})


def _compile_field_order_forms() -> tuple[tuple[re.Pattern[str], PayeeMatch], ...]:
    """FIELD_ORDER_PAYEE_FORMS compiled once, each with its payee's group (PAYEE_GROUP_REGISTRIES)."""
    state_of = {entity: state for state, registry in PAYEE_GROUP_REGISTRIES.items() for entity in registry}
    return tuple(
        (re.compile(form), PayeeMatch(entity, state_of[entity], ""))
        for entity, forms in FIELD_ORDER_PAYEE_FORMS.items()
        if entity in state_of
        for form in forms
    )


_FIELD_ORDER_FORMS = _compile_field_order_forms()


def _field_order_payee(text: str) -> PayeeMatch | None:
    """5.3 (owner ruling 2026-09-27): the admitted payee a debit prints in the bank's field order, or None."""
    return next((match for pattern, match in _FIELD_ORDER_FORMS if pattern.search(text)), None)


def _field_order_debit_record(
    common: dict[str, object],
    text: str,
    match: PayeeMatch,
) -> TransactionClassification:
    """A debit to a payee read from the bank's fields: its group (D9's LOC wording still wins), with no alias."""
    if match.state in _LOC_OVERRIDE_STATES and _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        state, rule = "line_of_credit", "line_of_credit_descriptor_override"
    else:
        state, rule = match.state, f"{match.state}_field_order"
    return _build_record(
        **common,
        classification=state,
        canonical_entity=match.entity,
        match_method="known_payee_field_order",
        matched_rule=rule,
        confidence_score=0.97,
        reason=(
            f"The bank printed the originator and the entry description of {match.entity} in separate fields; "
            f"read from those fields, the row is {_state_words(state)}."
        ),
    )


def _known_payee_debit_record(
    common: dict[str, object],
    text: str,
    match: PayeeMatch,
) -> TransactionClassification:
    """Spec §4.3 step 7 and D9: a debit to a known payee takes the payee's group."""
    if match.state in _LOC_OVERRIDE_STATES and _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        return _build_record(
            **common,
            classification="line_of_credit",
            canonical_entity=match.entity,
            match_method="known_payee_alias",
            matched_alias=match.alias,
            matched_rule="line_of_credit_descriptor_override",
            confidence_score=0.97,
            reason=(
                f"Matched maintained {_state_words(match.state)} alias '{match.alias}', and the "
                "descriptor says LOC or line of credit, so the row is a line of credit (D9)."
            ),
        )
    if match.state == "confirmed_lender":
        return _build_record(
            **common,
            classification="confirmed_lender",
            canonical_entity=match.entity,
            match_method="verified_lender_alias",
            matched_alias=match.alias,
            matched_rule="confirmed_lender_registry",
            confidence_score=0.99,
            reason=f"Matched maintained lender alias '{match.alias}' after all strong exclusions.",
        )
    return _build_record(
        **common,
        classification=match.state,
        canonical_entity=match.entity,
        match_method="known_payee_alias",
        matched_alias=match.alias,
        matched_rule=f"{match.state}_registry",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}'; "
            "it is a flagged obligation and never enters lender math."
        ),
    )


#: Owner decision 2026-09-25 (Klarna Inc): an alternative-position payee's paid
#: membership, or a top-up of the customer's own balance with it, printed right
#: after the payee's alias, is not a repayment. The words are read after the
#: matched alias, so no payee name is written here.
_MEMBERSHIP_OR_TOP_UP_AFTER_ALIAS = (
    r" (?:PLUS|PLU|MEM|MEMB|MEMBER|MEMBERSHIP)\b",
    r" BALANCE TOP ?(?:UP|U)\b",
)


def _is_membership_or_top_up(text: str, match: PayeeMatch) -> bool:
    """True when a debit to an alternative-position payee is its membership or a balance top-up."""
    if match.state != "alternative_position":
        return False
    alias = re.escape(match.alias)
    return any(re.search(rf"\b{alias}{tail}", text) for tail in _MEMBERSHIP_OR_TOP_UP_AFTER_ALIAS)


def _financing_proceeds_payee(text: str) -> PayeeMatch | None:
    """D1: the known payee whose credit is financing proceeds, or None.

    Owner decision 2026-09-25: the credits of a payout-credit entity
    (PAYOUT_CREDIT_ENTITIES) are the account holder's own sales settled by the
    platform, so they are revenue; that entity's debits keep their group.
    Owner ruling 2026-09-26: a factoring payee's credits are the business's own
    sales paid by the factor, so they are revenue too, and they keep the
    factoring flag (_FLAGGED_REVENUE_CREDIT_STATES).
    """
    match = match_known_payee(text)
    if (
        match is None
        or match.state not in FINANCING_STATES
        or match.state in _FLAGGED_REVENUE_CREDIT_STATES
        or match.entity in PAYOUT_CREDIT_ENTITIES
    ):
        return None
    return match


#: D1 by descriptor (owner decisions 2026-09-25): credits whose own words say they
#: are financing proceeds, with no registry payee named. Credits only.
_BANK_LINE_ADVANCE_CREDIT = re.compile(r"^LOAN CREDIT$")
_LOC_DRAW_CREDIT_PATTERNS = (
    re.compile(r"\b(?:LOC|LINE OF CREDIT) (?:ADVANCE|ADV|DRAW)\b"),
    re.compile(r"\bADVANCE FROM (?:LOC|LINE OF CREDIT)\b"),
    re.compile(r"\bDRAW (?:ON|FROM) (?:LOC|LINE OF CREDIT)\b"),
)
_FLOOR_PLAN_ADVANCE_CREDIT = re.compile(r"^ADVANCE (?:19|20)\d\d .*\bVIN\b")


def _descriptor_proceeds(text: str) -> tuple[str, bool] | None:
    """D1 by descriptor: (rule, whether the statement bank is the lender), or None.

    Read after the known-payee check. The bank's own line advance (exactly
    LOAN CREDIT) is decided there, ahead of the strong non-revenue rule that
    would otherwise claim it. A line-of-credit draw or a per-vehicle floor-plan
    advance counts only when no potential alias and no strong non-revenue rule
    (an own-account transfer, for example) claims the credit.
    """
    if _BANK_LINE_ADVANCE_CREDIT.search(text):
        return "bank_line_advance_credit", True
    if registry_match(text, POTENTIAL_LENDER_ALIASES) is not None or _matches_any(
        text, _NON_REVENUE_CREDIT_PATTERNS
    ):
        return None
    if _matches_any(text, _LOC_DRAW_CREDIT_PATTERNS):
        return "loc_draw_credit", True
    if _FLOOR_PLAN_ADVANCE_CREDIT.search(text):
        return "floor_plan_advance_credit", False
    return None


def _financing_proceeds_credit_record(
    common: dict[str, object],
    amount: float,
    match: PayeeMatch,
) -> TransactionClassification:
    """D1: a credit from a financing group is proceeds, excluded from eligible deposits."""
    return _build_record(
        **common,
        classification="other",
        canonical_entity=match.entity,
        match_method="financing_proceeds_credit",
        matched_alias=match.alias,
        matched_rule="financing_proceeds_credit",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}' on a credit; "
            "financing proceeds are excluded from lender debits and eligible deposits."
        ),
        contributes_to_lender_credit_exclusion=amount > 0,
    )


def _flagged_revenue_credit_record(
    common: dict[str, object],
    match: PayeeMatch,
) -> TransactionClassification:
    """Owner ruling 2026-09-26: a factoring payee's credit is the business's own sales, paid by the factor.

    The row takes the payee's group, so it carries the group's flag and counts in
    the flagged totals as a credit. Its revenue decision is the operating-revenue
    path's (the payee is skipped there), so it is never financing proceeds and it
    stays in eligible deposits.
    """
    return _build_record(
        **common,
        classification=match.state,
        canonical_entity=match.entity,
        match_method="known_payee_alias",
        matched_alias=match.alias,
        matched_rule=f"{match.state}_revenue_credit",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}' on a credit: a "
            "factor's payout is the business's own sales, so it stays revenue and in eligible "
            "deposits, and it is flagged as a factoring position (owner ruling)."
        ),
    )


def _descriptor_proceeds_credit_record(
    common: dict[str, object],
    amount: float,
    proceeds: tuple[str, bool],
    bank: str | None,
) -> TransactionClassification:
    """D1 by descriptor: the credit's own words say it is financing proceeds."""
    rule, names_bank = proceeds
    return _build_record(
        **common,
        classification="other",
        canonical_entity=(bank or None) if names_bank else None,
        match_method="financing_proceeds_credit",
        matched_rule=rule,
        confidence_score=0.95,
        reason=(
            f"The credit's descriptor identifies financing proceeds ({_state_words(rule)}); they are "
            "excluded from lender debits and eligible deposits."
        ),
        contributes_to_lender_credit_exclusion=amount > 0,
    )


def _obligation_fields(
    state: str,
    rule: str,
    reason: str,
    *,
    entity: str | None = None,
    alias: str | None = None,
    match_method: str = "obligation_descriptor",
) -> dict[str, object]:
    return {
        "classification": state,
        "canonical_entity": entity,
        "match_method": match_method,
        "matched_alias": alias,
        "matched_rule": rule,
        "confidence_score": 0.95,
        "reason": f"{reason} It is a flagged obligation and never enters lender math.",
    }


def _descriptor_obligation(text: str, bank: str | None) -> dict[str, object] | None:
    """Spec §4.3 step 8: obligation descriptors on a debit no known payee claimed.

    The rules run in the spec's order, with the rules of the owner decisions of
    2026-09-25 where their own placement puts them, and the first match wins.
    Returns the `_build_record` keyword arguments, or None when no descriptor
    rule matches.
    """
    # A transfer between the holder's own accounts takes no step-8 rule.
    if _OWN_ACCOUNT_TRANSFER_GUARD.search(text):
        return None
    if _FLOOR_PLAN_PAYOFF_PATTERN.search(text):
        return _obligation_fields(
            "floor_plan_financing",
            "floor_plan_payoff_descriptor",
            "The descriptor is a per-vehicle floor-plan payoff.",
        )
    if _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        return _obligation_fields(
            "line_of_credit", "line_of_credit_descriptor", "The descriptor says LOC or line of credit."
        )
    if _matches_any(text, _MORTGAGE_PATTERNS):
        return _obligation_fields(
            "mortgage", "mortgage_descriptor", "The descriptor identifies a mortgage or home-equity loan payment."
        )
    if _matches_any(text, _VEHICLE_FINANCING_PATTERNS):
        return _obligation_fields(
            "vehicle_financing",
            "vehicle_financing_descriptor",
            "The descriptor identifies a vehicle loan, lease or payment.",
        )
    if _matches_any(text, _STUDENT_LOAN_PATTERNS):
        return _obligation_fields(
            "personal_loan", "student_loan_descriptor", "The descriptor identifies a student-loan payment."
        )
    bank_match = registry_match(text, BANK_NAME_ALIASES)
    if bank_match is not None and _matches_any(text, _LOAN_WORD_PATTERNS):
        entity, alias = bank_match
        return _obligation_fields(
            "bank_loan",
            "bank_name_loan_payment",
            f"A listed bank ('{alias}') with loan wording is a bank loan (D5).",
            entity=entity,
            alias=alias,
            match_method="bank_name_alias",
        )
    if _matches_any(text, _OWN_LOAN_TRANSFER_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "own_bank_loan_transfer",
            "The descriptor is a transfer to the statement bank's own loan (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _OUTSIDE_BANK_LOAN_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "outside_bank_loan_payment",
            "The descriptor is another bank's loan payment, with no lender named (D5).",
        )
    if _matches_any(text, _OWN_LOAN_PAYMENT_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "own_bank_loan_payment",
            "The descriptor is the statement bank's own loan-payment wording (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _COMMERCIAL_LOAN_BILLING_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "commercial_loan_billing",
            "The descriptor is the statement bank's commercial-loan billing (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _FRENCH_OWN_LOAN_PATTERNS):
        return _obligation_fields(
            "bank_loan",
            "french_loan_wording",
            "The descriptor is the statement bank's own French loan wording (D5).",
            entity=bank or None,
        )
    # D5 (owner decision 2026-09-25): a loan payment that prints no payee is the
    # statement bank's own loan, not a potential lender. The last D5 rule.
    if _matches_any(text, _UNNAMED_LOAN_PAYMENT_PATTERNS) and (
        set(_unknown_payee_tokens(text)) <= _BANK_TEMPLATE_WORDS
    ):
        return _obligation_fields(
            "bank_loan",
            "unnamed_loan_payment",
            "The descriptor is a loan payment that names no lender: the statement bank's own loan (D5).",
            entity=bank or None,
        )
    if _matches_any(text, _LEASE_RENTAL_PATTERNS):
        return _obligation_fields(
            "lease_or_rental",
            "lease_or_rental_descriptor",
            "The descriptor identifies a lease, rental or lease-to-own payment.",
        )
    issuer = registry_match(text, CARD_ISSUER_CONTEXT_ALIASES)
    if _matches_any(text, _CREDIT_CARD_PATTERNS) or (
        issuer is not None and _matches_any(text, _CARD_PAYMENT_CONTEXT_PATTERNS)
    ):
        entity, alias = issuer if issuer is not None else (None, None)
        return _obligation_fields(
            "credit_card_payment",
            "credit_card_payment",
            "The descriptor identifies a credit-card account payment.",
            entity=entity,
            alias=alias,
        )
    if _matches_any(text, _EQUIPMENT_FINANCING_PATTERNS):
        named = _canonical_unknown_entity(_EQUIPMENT_FINANCING_PATTERNS[0].sub(" ", text))
        return {
            "classification": "potential_lender",
            "canonical_entity": named or UNIDENTIFIED_LENDER_OBLIGATION,
            "match_method": "unnamed_equipment_financing",
            "matched_rule": "equipment_financing_without_verified_entity",
            "confidence_score": 0.72,
            "reason": (
                "Equipment financing with no named, verified company is a potential "
                "lender; it requires review (D4)."
            ),
            "review_required": True,
        }
    return None


def classify_transaction(
    description: str,
    amount: float,
    *,
    date: str = "",
    bank: str | None = None,
    account: str | None = None,
    account_name: str | None = None,
    direction: str | None = None,
    source_page: int | None = None,
    source_location: str | None = None,
    posted: bool = True,
) -> TransactionClassification:
    text = normalize_transaction_description(description)
    derived_direction = "credit" if amount >= 0 else "debit"
    source_direction = str(direction or derived_direction).strip().lower()
    direction_consistent = source_direction == derived_direction
    common: dict[str, object] = {
        "description": description,
        "text": text,
        "amount": amount,
        "date_value": date,
        "bank": bank,
        "account": account,
        "account_name": account_name,
        "source_direction": source_direction,
        "direction_consistent": direction_consistent,
        "source_page": source_page,
        "source_location": source_location,
    }

    if not posted or _matches_any(text, _NON_POSTED_PATTERNS):
        return _build_record(
            **common,
            classification="other",
            match_method="posting_status",
            matched_rule="non_posted_item",
            confidence_score=1.0,
            reason="The row is pending, memo-posted, or otherwise not a posted transaction.",
            is_posted=False,
        )

    if _matches_any(text, _NSF_PATTERNS):
        return _build_record(
            **common,
            classification="nsf_or_return",
            match_method="ordered_rule",
            matched_rule="nsf_or_return",
            confidence_score=0.99,
            reason="An NSF, insufficient-funds, or returned-item rule matched before lender detection.",
        )

    if _matches_any(text, _REFUND_REVERSAL_PATTERNS):
        return _build_record(
            **common,
            classification="refund_or_reversal",
            match_method="ordered_rule",
            matched_rule="refund_or_reversal",
            confidence_score=0.98,
            reason="A refund, reversal, void, cancellation, or returned-payment rule matched.",
        )

    insurance_match = _insurance_registry_match(text)
    # Owner decision 2026-09-25: premium-finance wording on a row no premium-finance
    # alias claimed is premium financing too, under the insurer when one is named.
    premium_wording = (insurance_match is None or not insurance_match[2]) and _matches_any(
        text, _PREMIUM_FINANCE_WORDING_PATTERNS
    )
    if insurance_match is not None or premium_wording:
        provider, alias, premium_finance = insurance_match or ("Insurance provider not identified", None, False)
        if premium_finance:
            rule = "premium_finance_provider"
            reason = (
                f"Matched maintained premium-finance alias '{alias}'; the row stays insurance "
                "and is also flagged as premium financing."
            )
        elif premium_wording:
            rule = "premium_finance_descriptor"
            reason = (
                "The descriptor says premium finance; the row stays insurance and is also "
                "flagged as premium financing."
            )
        else:
            rule = "verified_insurance_provider"
            reason = f"Matched maintained insurance provider alias '{alias}'."
        return _build_record(
            **common,
            classification="insurance",
            canonical_entity=provider,
            match_method="insurance_provider_alias" if alias is not None else "insurance_descriptor",
            matched_alias=alias,
            matched_rule=rule,
            confidence_score=0.99 if alias is not None else 0.95,
            reason=reason,
            # Spec §4.2: premium financing keeps the insurance state and the
            # insurance totals, and also carries its flag, on debits only.
            flagged_group=(
                _PREMIUM_FINANCING_GROUP if (premium_finance or premium_wording) and amount < 0 else None
            ),
        )

    if _matches_any(text, _INSURANCE_TERM_PATTERNS):
        return _build_record(
            **common,
            classification="insurance",
            canonical_entity="Insurance provider not identified",
            match_method="insurance_descriptor",
            matched_rule="insurance_term",
            confidence_score=0.95,
            reason="Matched an insurance-specific provider or policy/premium descriptor.",
        )

    # Spec §4.6: one lookup over every group registry. A known payee is excepted
    # from the POS and ATM rules (D8) and takes its group at step 7 below.
    known_payee = match_known_payee(text)
    # Owner decision 2026-09-25: a membership or balance top-up debit of an
    # alternative-position payee matches no known payee (steps 5 and 7).
    if known_payee is not None and amount < 0 and _is_membership_or_top_up(text, known_payee):
        known_payee = None
    # 5.3 (owner ruling 2026-09-27): an admitted payee printed in the bank's field order, on a debit no alias
    # matched (FIELD_ORDER_PAYEE_FORMS). Credits keep today's rules.
    field_order_payee = _field_order_payee(text) if known_payee is None and amount < 0 else None
    if field_order_payee is not None:
        known_payee = field_order_payee
    # 5.3 (owner ruling 2026-09-27): a debt-relief payee, on a debit no known payee claimed, read without the row's
    # receiver fields (the account holder may itself be a debt-relief firm). It then stands in for the known payee:
    # the POS and ATM exceptions (D8) and step 7 treat it as one. Credits keep today's rules.
    if known_payee is None and amount < 0:
        known_payee = match_debt_relief_payee(_RECEIVER_FIELD_VALUE.sub(" ", text))

    if (
        amount < 0
        and known_payee is None
        and _matches_any(text, _POS_PATTERNS)
        and not _matches_any(text, _POS_EXCLUSION_PATTERNS)
        and (
            "TRANSFER" not in text
            or _matches_any(text, _EXPLICIT_CARD_PURCHASE_PATTERNS)
        )
        and not _matches_any(text, _POS_LEASE_EXCLUSION_PATTERNS)
    ):
        return _build_record(
            **common,
            classification="pos",
            match_method="ordered_rule",
            matched_rule="point_of_sale_purchase",
            confidence_score=0.98,
            reason="The posted debit is explicitly identified as a point-of-sale purchase.",
        )

    if (
        amount < 0
        and known_payee is None
        and _matches_any(text, _ATM_PATTERNS)
        and not _matches_any(text, _FEE_PATTERNS)
    ):
        return _build_record(
            **common,
            classification="atm",
            match_method="ordered_rule",
            matched_rule="atm_withdrawal",
            confidence_score=0.98,
            reason="The posted debit is explicitly identified as an ATM cash withdrawal.",
        )

    if _matches_any(text, _FEE_PATTERNS):
        return _build_record(
            **common,
            classification="fee",
            match_method="strong_non_lender_exclusion",
            matched_rule="bank_or_processing_fee",
            confidence_score=0.97,
            reason="A bank, ACH, transfer, service, or merchant-processing fee rule matched.",
        )

    if _matches_any(text, _TRANSFER_PATTERNS):
        return _build_record(
            **common,
            classification="transfer",
            match_method="strong_non_lender_exclusion",
            matched_rule="transfer",
            confidence_score=0.96,
            reason="The descriptor identifies an account, online, or person-to-person transfer.",
        )

    if _matches_any(text, _TAX_PATTERNS):
        return _build_record(
            **common,
            classification="tax",
            match_method="strong_non_lender_exclusion",
            matched_rule="tax_payment",
            confidence_score=0.96,
            reason="The descriptor identifies a tax authority or tax payment.",
        )

    if _matches_any(text, _PAYROLL_PATTERNS) or _is_payroll_provider_row(text):
        return _build_record(
            **common,
            classification="payroll",
            match_method="strong_non_lender_exclusion",
            matched_rule="payroll",
            confidence_score=0.96,
            reason=(
                "The descriptor identifies payroll, wages, a payroll provider or an employee-benefits administrator."
            ),
        )

    if _matches_any(text, _UTILITY_PATTERNS):
        return _build_record(
            **common,
            classification="utility",
            match_method="strong_non_lender_exclusion",
            matched_rule="utility_payment",
            confidence_score=0.94,
            reason="The descriptor identifies a utility payment.",
        )

    # Step 7: the known payee's group (D9 inside). A credit is proceeds only
    # for a financing group (D1), and never for a payout-credit entity (owner
    # decision 2026-09-25: its credits are the holder's own sales); a card-issuer
    # or lease/rental payee on a credit falls through to the rules below. A
    # factoring payee's credit is revenue and keeps the factoring flag (owner
    # ruling 2026-09-26).
    if known_payee is not None:
        if amount < 0:
            if field_order_payee is not None:
                return _field_order_debit_record(common, text, known_payee)
            return _known_payee_debit_record(common, text, known_payee)
        if known_payee.state in _FLAGGED_REVENUE_CREDIT_STATES:
            return _flagged_revenue_credit_record(common, known_payee)
        if known_payee.state in FINANCING_STATES and known_payee.entity not in PAYOUT_CREDIT_ENTITIES:
            return _financing_proceeds_credit_record(common, amount, known_payee)
    # D1 by descriptor (owner decisions 2026-09-25): the bank's own line advance,
    # a line-of-credit draw or a per-vehicle floor-plan advance. Credits only.
    if amount > 0:
        descriptor_proceeds = _descriptor_proceeds(text)
        if descriptor_proceeds is not None:
            return _descriptor_proceeds_credit_record(common, amount, descriptor_proceeds, bank)

    # Step 8: obligation descriptors, debits only (D1: these never apply to credits).
    if amount < 0:
        obligation = _descriptor_obligation(text, bank)
        if obligation is not None:
            return _build_record(**common, **obligation)

    if _matches_any(text, _RENT_PATTERNS):
        return _build_record(
            **common,
            classification="rent",
            match_method="strong_non_lender_exclusion",
            matched_rule="rent",
            confidence_score=0.95,
            reason="The descriptor identifies rent or a landlord payment.",
        )

    if _matches_any(text, _CHECK_PATTERNS):
        return _build_record(
            **common,
            classification="other",
            match_method="strong_non_lender_exclusion",
            matched_rule="check",
            confidence_score=0.94,
            reason="The row is a check or cheque and has no separate verified lender evidence.",
        )

    if _matches_any(text, _SUBSCRIPTION_PATTERNS):
        return _build_record(
            **common,
            classification="other",
            match_method="strong_non_lender_exclusion",
            matched_rule="subscription",
            confidence_score=0.93,
            reason="The row is a subscription or membership payment with no verified lender evidence.",
        )

    bank_registry = BANK_SPECIFIC_LENDER_ALIASES.get((bank or "").upper())
    bank_match = registry_match(text, bank_registry) if bank_registry and amount < 0 else None
    if bank_match is not None:
        lender, alias = bank_match
        return _build_record(
            **common,
            classification="confirmed_lender",
            canonical_entity=lender,
            match_method="bank_specific_lender_rule",
            matched_alias=alias,
            matched_rule=f"{bank}_lender_registry",
            confidence_score=0.98,
            reason=f"Matched lender alias or transaction code '{alias}' for {bank}.",
        )

    potential_match = registry_match(text, POTENTIAL_LENDER_ALIASES)
    if potential_match is not None and amount < 0:
        lender, alias = potential_match
        # 5.3 (owner ruling 2026-09-27): a review entity of a flag group takes its flag, marked unconfirmed. Its
        # aliases stay in POTENTIAL_LENDER_ALIASES, so its credits keep the potential tier's exclusion.
        routed = REVIEW_FLAG_ENTITIES.get(lender)
        if routed is not None:
            return _build_record(
                **common,
                classification=routed,
                canonical_entity=lender,
                match_method="unconfirmed_flag_payee_alias",
                matched_alias=alias,
                matched_rule=f"{routed}_review_registry",
                confidence_score=0.82,
                reason=(
                    f"Matched maintained candidate alias '{alias}' of an unconfirmed {_state_words(routed)} payee: "
                    "it is flagged, marked unconfirmed, and never enters lender math."
                ),
                review_required=True,
            )
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity=lender,
            match_method="candidate_lender_alias",
            matched_alias=alias,
            matched_rule="potential_lender_registry",
            confidence_score=0.82,
            reason=f"Matched maintained candidate alias '{alias}'; confirmation requires review.",
            review_required=True,
        )

    if (
        amount < 0
        and _matches_any(text, _RELATED_PARTY_LOAN_PATTERNS)
        and _canonical_unknown_entity(text) in (None, UNIDENTIFIED_LENDER_OBLIGATION)
    ):
        return _build_record(
            **common,
            classification="other",
            match_method="strong_non_lender_exclusion",
            matched_rule="related_party_loan",
            confidence_score=0.90,
            reason=(
                "The descriptor names a loan from the business's own shareholder, owner or director; it names "
                "no lender."
            ),
        )

    if amount < 0 and _matches_any(text, _SERVICER_COLLECTOR_PATTERNS):
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity=(
                UNIDENTIFIED_MCA_SERVICER
                if _MCA_SERVICING_PATTERN.search(text)
                else _canonical_unknown_entity(text) or UNIDENTIFIED_LENDER_OBLIGATION
            ),
            match_method="unknown_servicer_or_collector",
            matched_rule="servicer_or_collector_without_verified_funder",
            confidence_score=0.74,
            reason=(
                "The payee is a loan servicer or debt collector whose funder is not "
                "identified; it is potential only and requires review (D10)."
            ),
            review_required=True,
        )

    if amount < 0 and _matches_any(text, _DIRECT_DEBIT_LOAN_PATTERNS):
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity=UNIDENTIFIED_LENDER_OBLIGATION,
            match_method="unidentified_loan_obligation",
            matched_rule="direct_debit_loan_without_verified_counterparty",
            confidence_score=0.78,
            reason=(
                "The posted debit explicitly identifies a loan obligation, but no verified "
                "lender counterparty is available."
            ),
            review_required=True,
        )

    explicit_repayment = _matches_any(text, _EXPLICIT_REPAYMENT_PATTERNS)
    financing_signal = _matches_any(text, _FINANCING_SIGNAL_PATTERNS)
    payment_marker = _matches_any(text, _PAYMENT_MARKER_PATTERNS)
    candidate = _canonical_unknown_entity(text) if financing_signal else None
    if amount < 0 and explicit_repayment:
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity=candidate or UNIDENTIFIED_LENDER_OBLIGATION,
            match_method="explicit_financing_repayment",
            matched_rule="unknown_explicit_repayment",
            confidence_score=0.78,
            reason="The debit has an explicit financing-repayment descriptor, but the counterparty is not verified.",
            review_required=True,
        )

    if amount < 0 and financing_signal and payment_marker:
        return _build_record(
            **common,
            classification="other",
            canonical_entity=candidate,
            match_method="financing_keyword_review",
            matched_rule="financing_keyword_without_verified_entity",
            confidence_score=0.35,
            reason="Financing language alone is insufficient; recurrence and counterparty evidence are required.",
            review_required=True,
        )

    return _build_record(
        **common,
        classification="other",
        match_method="default",
        matched_rule="no_classification_rule",
        confidence_score=0.60,
        reason="No verified lender, insurance, or operational-category rule matched.",
    )


def classify_cadence(dates: list[date]) -> tuple[str, float | None]:
    ordered = sorted(set(dates))
    gaps = [(b - a).days for a, b in zip(ordered, ordered[1:]) if (b - a).days > 0]
    if not gaps:
        return "irregular", None
    average = mean(gaps)
    spread = pstdev(gaps) if len(gaps) > 1 else 0.0
    if average <= 1.6 and spread <= 1.5:
        return "daily", round(average, 1)
    if 5 <= average <= 9 and spread <= 2.5:
        return "weekly", round(average, 1)
    return "irregular", round(average, 1)


def flagged_payee(record: TransactionClassification) -> str:
    """The payee a flagged row is grouped under: its entity, else its group's label (spec §6)."""
    if record.canonical_entity:
        return record.canonical_entity
    group = FLAG_GROUP_BY_KEY.get(record.flagged_group or "")
    return group.label if group is not None else (record.flagged_group or "")


def _replace_revenue_state(
    record: TransactionClassification,
    state: RevenueState,
    *,
    match_method: str,
    matched_rule: str,
    confidence_score: float,
    reason: str,
    context_signals: Sequence[str],
    related_transaction: str | None = None,
) -> TransactionClassification:
    return replace(
        record,
        revenue_classification=state,
        revenue_initial_classification=state,
        revenue_match_method=match_method,
        revenue_matched_rule=matched_rule,
        revenue_confidence_score=confidence_score,
        revenue_reason=reason,
        revenue_context_signals=tuple(dict.fromkeys(context_signals)),
        revenue_related_transaction=related_transaction,
        revenue_review_required=state == "unverified_deposit",
        revenue_review_status=(
            "pending" if state == "unverified_deposit" else "not_required"
        ),
        **revenue_contribution_flags(state),
    )


_REVENUE_PAIR_NOISE = {
    "CANCEL", "CANCELED", "CANCELLED", "CANCELLATION", "CNCL",
    "RETURN", "RETURNED", "REVERSAL", "REVERSED", "REVERSE",
    "REFUND", "REFUNDED", "CREDIT", "DEBIT", "SENT", "RECEIVED",
    "PAYMENT", "PAY", "PMT", "PYMT", "ITEM", "PROVISIONAL", "TEMPORARY",
    "CONDITIONAL", "ACH", "PULL", "CARD", "PURCHASE", "CHECK", "CHEQUE",
    "WIRE", "TRANSFER", "DEPOSIT", "WITHDRAWAL",
}


def _revenue_pair_tokens(text: str) -> set[str]:
    return {
        token
        for token in text.split()
        if token not in _REVENUE_PAIR_NOISE and len(token) > 1
    }


def _descriptions_share_pair_context(left: str, right: str) -> bool:
    if _revenue_pair_tokens(left) & _revenue_pair_tokens(right):
        return True
    return any(pattern.search(left) and pattern.search(right) for pattern in _PAIR_FAMILY_PATTERNS)


def _apply_reversal_pair_context(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    updated = list(records)
    matched_debit_indexes: set[int] = set()
    for credit_index, credit in enumerate(records):
        if (
            credit_index in duplicate_indexes
            or credit.amount <= 0
            or not credit.is_posted
        ):
            continue
        credit_has_marker = _matches_any(
            credit.normalized_description,
            _REVERSAL_CANCELLATION_CREDIT_PATTERNS,
        )
        candidates: list[tuple[int, int]] = []
        credit_date = parse_date(credit.date)
        for debit_index, debit in enumerate(records):
            if (
                debit_index in duplicate_indexes
                or debit_index in matched_debit_indexes
                or debit.amount >= 0
                or not debit.is_posted
                or round(abs(debit.amount), 2) != round(credit.amount, 2)
            ):
                continue
            debit_has_marker = _matches_any(
                debit.normalized_description,
                _REVERSAL_CANCELLATION_CREDIT_PATTERNS,
            )
            if not credit_has_marker and not debit_has_marker:
                continue
            debit_date = parse_date(debit.date)
            day_gap = (
                abs((credit_date - debit_date).days)
                if credit_date is not None and debit_date is not None
                else 0
            )
            if day_gap > 14 or not _descriptions_share_pair_context(
                credit.normalized_description,
                debit.normalized_description,
            ):
                continue
            candidates.append((day_gap, debit_index))
        if not candidates:
            continue
        _, debit_index = min(
            candidates,
            key=lambda item: (item[0], abs(item[1] - credit_index), item[1]),
        )
        debit = records[debit_index]
        matched_debit_indexes.add(debit_index)
        related_location = debit.source_location or f"transaction:{debit_index + 1}"
        credit_location = credit.source_location or f"transaction:{credit_index + 1}"
        is_settlement_reversal = _matches_any(
            credit.normalized_description,
            _SETTLEMENT_REVERSAL_PATTERNS,
        ) or _matches_any(
            debit.normalized_description,
            _SETTLEMENT_REVERSAL_PATTERNS,
        )
        updated_credit = _replace_revenue_state(
            credit,
            "non_revenue",
            match_method="matched_reversal_pair",
            matched_rule="opposite_direction_amount_date_description_match",
            confidence_score=1.0,
            reason=(
                f"Credit matches reversal or cancellation row {related_location} by "
                "amount, date proximity, and transaction-family description."
            ),
            context_signals=(
                *credit.revenue_context_signals,
                "matched_opposite_direction_row",
                "amount_date_description_match",
            ),
            related_transaction=related_location,
        )
        # A credit this pass pairs with a debit is money coming back, not a factor's
        # payout (owner ruling 2026-09-26), so it leaves the flagged totals.
        updated[credit_index] = replace(
            updated_credit,
            reversal_of=related_location if is_settlement_reversal else None,
            settlement_reversal=is_settlement_reversal,
            contributes_to_flagged_totals=False,
        )
        if is_settlement_reversal:
            updated[debit_index] = replace(
                updated[debit_index],
                reversed_by=credit_location,
                contributes_to_lender_count=False,
                contributes_to_potential_lender_count=False,
                contributes_to_lender_totals=False,
                contributes_to_withholding_rate=False,
                contributes_to_potential_lender_totals=False,
                contributes_to_potential_withholding_exposure=False,
                contributes_to_insurance_totals=False,
                contributes_to_flagged_totals=False,
            )
    return updated


def _apply_operating_source_context(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    updated = list(records)
    credits_by_entity: dict[str, list[int]] = {}
    activity_by_entity: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        if index in duplicate_indexes or not record.is_posted:
            continue
        match = registry_match(
            record.normalized_description,
            OPERATING_REVENUE_SOURCE_ALIASES,
        )
        if match is None:
            continue
        entity, _ = match
        if record.amount > 0 and record.revenue_classification == "unverified_deposit":
            credits_by_entity.setdefault(entity, []).append(index)
        elif record.amount < 0 and _matches_any(
            record.normalized_description,
            _OPERATING_PLATFORM_DEBIT_CONTEXT_PATTERNS,
        ):
            activity_by_entity.setdefault(entity, []).append(index)

    for entity, indexes in credits_by_entity.items():
        business_context = any(
            "business_account" in records[index].revenue_context_signals
            for index in indexes
        )
        recurring = len(indexes) >= 3 or (len(indexes) >= 2 and business_context)
        related_activity = activity_by_entity.get(entity) or []
        if not recurring and not related_activity:
            continue
        for index in indexes:
            record = updated[index]
            signals = list(record.revenue_context_signals)
            if recurring:
                signals.append(f"recurring_source_{len(indexes)}_credits")
            if business_context:
                signals.append("business_account")
            if related_activity:
                signals.append("related_platform_fee_or_chargeback")
            method = (
                "recurring_operating_source"
                if recurring
                else "operating_source_related_activity"
            )
            rule = (
                "maintained_source_recurs_across_statement"
                if recurring
                else "maintained_source_has_related_operating_debit"
            )
            evidence_text = (
                f"recurs in {len(indexes)} posted credits"
                if recurring
                else "has a related processing fee, commission, chargeback, or adjustment"
            )
            updated[index] = _replace_revenue_state(
                record,
                "verified_revenue",
                match_method=method,
                matched_rule=rule,
                confidence_score=0.90 if recurring else 0.88,
                reason=(
                    f"Maintained operating source '{entity}' {evidence_text}; "
                    "the credit is verified as operating revenue."
                ),
                context_signals=signals,
            )
    return updated


#: D6 skips a row whose own words say it is a transfer, even when no transfer
#: rule claimed it (a transfer to a person is not an MCA remittance).
_TRANSFER_WORD_PATTERNS = (re.compile(r"\b(?:TRANSFER|XFER|TFR)\b"),)
#: D6 also skips a row whose own words say it pays compensation: a commission
#: (with its common misspellings: COMMISION, COMISSION, COMISION, COMMISSON), a
#: bonus, a salary, a stipend or a reimbursement. Pay is not an MCA remittance.
#: The row stays "other"; payroll and wages already classify as payroll.
_COMPENSATION_WORD_PATTERNS = (
    re.compile(r"\bCOMM?ISS?I?ONS?\b"),
    re.compile(r"\b(?:BONUS(?:ES)?|SALARY|SALARIES|STIPENDS?|REIMB(?:URS\w*)?)\b"),
)
#: D6 does not apply to a card purchase, including the card formats the POS rule
#: does not read: a posting that starts "PURCHASE" and its mmdd (after an
#: optional "RECURRING"), read on the normalized text, and a processor*merchant
#: mark, read on the printed text because normalization drops the star. The word
#: PURCHASE alone is not a card mark: an ACH entry description can print it.
_CARD_PURCHASE_POSTING_PATTERN = re.compile(r"^(?:RECURRING )?PURCHASE \d{4}\b")
#: The processor*merchant mark: a letter or digit, an optional space, "*", an
#: optional space, a letter or digit ("TST*NAME", "SQ *NAME", "TST* NAME"). ASCII
#: letters and digits only: `\w` would also take "_" and non-ASCII letters.
_PROCESSOR_MERCHANT_MARK_PATTERN = re.compile(r"[A-Za-z0-9] ?\* ?[A-Za-z0-9]")
#: An ACH entry prints stars too: in its addenda ("RMR*IV*"), a masked account
#: or an ID. A row with an ACH field mark is never read as a card purchase by
#: its star. The SEC codes and field names are read as words on the normalized
#: text; the labels whose colon normalization drops, on the printed text.
_ACH_FIELD_MARK_WORD_PATTERN = re.compile(r"\b(?:ACH|CCD|PPD|CTX|WEB|INDN|RMR|CO ID|ORIG CO)\b")
_ACH_FIELD_MARK_LABEL_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:DES|ID)\s*:", re.IGNORECASE)
#: D6: a masked recipient account printed after TO ("To ....1234", "TO XXXX1234",
#: "TO ***1234", "TO #1234", "TO x1234", "TO ACCT XXXX1234"), read on the printed
#: text because normalization drops the dots, stars and "#". Its digits are part
#: of the payee, so payments to two recipient accounts are never one payee (D11).
_MASKED_RECIPIENT_PATTERN = re.compile(
    r"\bTO\b[\s:]*(?:(?:ACCOUNT|ACCT)\b[\s:]*)?(?:\.{2,}|…+|X+|\*+|#)[ -]?([0-9]{2,})(?![0-9])",
    re.IGNORECASE,
)
#: 5.3 (2026-09-27): the financing veto every 5.3 D6 skip reads. Funders ARE paid by card, Zelle, Interac, bill pay
#: and wire, so no skip fires on a row that names financing. The roots have no left word boundary, so a
#: run-together or cut name hits (KOVOCREDIT, CONSTRULOANS, BYZFUNDER, FUNDIN, CAPITA, FINANC, CLICKLEASE), and so
#: does a collector of MCA debt (RECOVERY, RECEIVABLES, COLLECTIONS). The card verifier's roots: SETTLE (an
#: unregistered debt-settlement payee stays reviewed; the registry alone names it debt relief), CRED before IT, ORA,
#: IBLY or a word end (CREDIBLY, CREDORA, a cut CRED; never INCREDIBLE) and ACCEPT (ACCEPTANCE). A skip's own matched
#: words are removed before the veto reads the row (_skips), so A4's 'BUS ONLINE ACH SETTLEMENT' template still skips.
#: The short abbreviations are whole words. Known over-reach, in the safe direction (the row stays in review):
#: CALENDAR, RELEASE, REFUNDABLE, FUNDRAISER, a processor's SETTLEMENT wording, ACCEPTED.
_FINANCING_ROOT_PATTERN = re.compile(
    r"(?:FUND|CAPITA|CAPTL|CRED(?=IT|ORA|IBLY|\b)|LOAN|LEND|FINANC|ADVANC|MERCH|RECOVER|RECEIVAB|COLLECT"
    r"|SERVICING|SERVICER|FACTOR|LEASE|LEASING|EQUIP|MORTG|ACCEPT|REMIT|SETTLE)"
    r"|\b(?:CAP|FIN|FINL|FNCL|ADV|MTG|MCA|RTR|SPV|DLY|DAILY|WKLY|WEEKLY)\b"
)
#: D11 and 5.3: the legal-form suffixes. A legal form names an organisation only after the name's first word.
_LEGAL_FORM_SUFFIXES = frozenset({
    "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
})


def _names_financing(text: str, *, besides: str = "") -> bool:
    """5.3: whether a normalized row names financing anywhere but in `besides`, the words a D6 skip matched.

    Read on the whole row, the account holder's name included: a holder named like a funder keeps its rows in
    review, which is the safe direction. The skip's own words are removed first, so they never veto the skip."""
    rest = text.replace(besides, " ") if besides else text
    return _FINANCING_ROOT_PATTERN.search(rest) is not None


def _skips(region: str, patterns: Sequence[re.Pattern[str]], text: str) -> bool:
    """5.3: a D6 skip fires when one of `patterns` is found in `region` (the part of the row the skip reads) and
    the rest of the whole row `text` names no financing (`_names_financing`)."""
    for pattern in patterns:
        found = pattern.search(region)
        if found is not None and not _names_financing(text, besides=found.group(0)):
            return True
    return False


def _has_ach_field_mark(record: TransactionClassification) -> bool:
    return bool(
        _ACH_FIELD_MARK_WORD_PATTERN.search(record.normalized_description)
        or _ACH_FIELD_MARK_LABEL_PATTERN.search(record.original_description or "")
    )


def _is_card_purchase_posting(record: TransactionClassification) -> bool:
    if _CARD_PURCHASE_POSTING_PATTERN.match(record.normalized_description):
        return True
    if _PROCESSOR_MERCHANT_MARK_PATTERN.search(record.original_description or "") and not _has_ach_field_mark(record):
        return True
    # 5.3 (2026-09-27): the bank card formats the POS rule does not read, never on a row that names financing,
    # a bank or an organisation (read on the whole row, not on the D11 payee words, which are the card template).
    text = record.normalized_description
    if _card_posting_vetoed(text):
        return False
    if _matches_any(text, _CARD_POSTING_LABEL_PATTERNS):
        return True
    if record.bank == "Wealthsimple" and not _WEALTHSIMPLE_CHANNEL_PATTERN.search(text):
        return True
    return bool(
        record.bank in _CARD_LOCATION_SUFFIX_BANKS
        and _CARD_LOCATION_SUFFIX_PATTERN.search(record.original_description or "")
        and not _has_ach_field_mark(record)
    )


def _masked_recipient(record: TransactionClassification) -> str | None:
    """D6: the printed digits of a masked recipient account after TO, or None."""
    match = _MASKED_RECIPIENT_PATTERN.search(record.original_description or "")
    return match.group(1) if match else None


#: 5.3 (2026-09-27): bank channel vocabulary. A D6 group whose payee words are all channel words names no payee:
#: a card, cash, cheque or bill-pay posting printed without its merchant or recipient. OTHER, BANK and the bare
#: withdrawal abbreviations (WD, WDL, WDRL) are left out on purpose: 'Other Debit', 'Bank Debit' and 'Preauthorized
#: Wd' rows stay in review, because the 2026-09-27 hunt could not tell what they pay.
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


def _names_only_channel_words(payee: Sequence[str], text: str) -> bool:
    """5.3: the D6 payee words are all channel words and the payee region of the normalized row `text` prints no
    organisation cue. D11's key stops at the first reference token once a name has started, so a format that prints
    a reference before the merchant keys as its template ('RECURRING PAYMENT AUTHORIZED ON 01 02 FAB HOLDINGS LLC
    CARD 4321' keys as RECURRING AUTHORIZED ON): the cue keeps such a row in review, as the card veto does (A1)."""
    return (
        bool(payee)
        and all(token in _CHANNEL_VOCABULARY for token in payee)
        and not any(token in _ORGANISATION_CUES for token in _payee_region(text).split())
    )


#: 5.3 (2026-09-27): card-posting labels the POS rule does not read, read on the normalized row with no ACH guard,
#: as _POS_PATTERNS are. MOBILE, RETAIL and PIN PURCHASE and the French ACHAT join the POS rule itself (B7).
_CARD_POSTING_LABEL_PATTERNS = (
    re.compile(r"\b\d{2} \d{2} \d{6,} (?:MOBILE )?PURCHASE\b"),        # Bank of America merchant-first card row
    re.compile(r"\bDE?BI?T CRD\b"),                                     # DBT CRD, DEBIT CRD
    re.compile(r"^DEBIT CARD\b"),                                       # Truist DEBIT CARD RECURRING PYMT / MISC DEBIT
    re.compile(r"^CARD$"),                                              # a type-only card row (CSV export)
    re.compile(r"\bCARD SPEND$"),                                       # Square Checking '<merchant> Card spend'
    re.compile(r"\bAUTHORI[ZS]ED ON \d{2} \d{2}\b.*\bCARD \d{4}$"),     # Wells Fargo '... authorized on mm/dd ... Card nnnn'
    re.compile(r"\bPIN DEBIT\b"),
    re.compile(r"\bRECURRING (?:DEBIT )?CARD\b"),                       # PNC RECURRING DEBIT CARD
    re.compile(r"\bCARD TRANSACTION\b"),                                # Regions
    re.compile(r"\bPURCH\b"),                                           # Citi DEBIT PURCH
    re.compile(r"\bCARD ENDING IN\b"),
    re.compile(r"\bDDA PUR\b"),                                         # TD Bank VISA DDA PUR (without its star)
)
#: 5.3: Wealthsimple Chequing prints a card purchase as the bare merchant; its other debits carry one of these words
#: (seen in 32 corpus accounts; its bill-payment print form is unverified: re-check when one arrives).
_WEALTHSIMPLE_CHANNEL_PATTERN = re.compile(
    r"\b(?:TRANSFER|TRANSFERT|INTERAC|PRE ?AUTHORI[ZS]ED|PAD|DEBIT|BILL|PAYMENT|EFT|WITHDRAWAL|DEPOSIT|CHEQUE|CHECK|"
    r"LOAN|WIRE|FEE)\b"
)
#: 5.3: the card network's merchant location, 'NAME, CITY, ST' (Bluevine) or 'NAME ###, CITY , ST , USA' (Found),
#: read on the printed text of those two banks' rows only, and only without an ACH field mark. Bluevine's glued
#: 'CITY, NYUS' variant is a known non-match.
_CARD_LOCATION_SUFFIX_PATTERN = re.compile(
    r",\s*[A-Za-z][A-Za-z .'-]*?\s*,\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|"
    r"MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|PR|GU|VI|AB|BC|MB|NB|NL|NS|NT|NU|"
    r"ON|PE|QC|SK|YT)\s*(?:,\s*USA)?\s*$"
)
_CARD_LOCATION_SUFFIX_BANKS = frozenset({"Bluevine", "Lead Bank (Found)"})
#: 5.3: besides the shared roots, a card-format skip never fires on a row that names a bank, an investment firm or an
#: organisation (an organisation cue or a financing-organisation word): funders ARE paid by debit card in these
#: formats (card lender-risk verifier: Dakota Financial on Bluevine, Hillcrest and CNAC on Square 'Card spend').
_CARD_POSTING_VETO_PATTERN = re.compile(
    r"(?:BANK|BANQUE|INVEST)"
    r"|\b(?:HOLDINGS?|PARTNERS?|VENTURES?|EQUITIES|GROUP|SOLUTIONS?|ENTERPRISES?|RESOURCES?|LP)\b"
)


def _card_posting_vetoed(text: str) -> bool:
    return (
        _names_financing(text)
        or _CARD_POSTING_VETO_PATTERN.search(text) is not None
        or any(token in _ORGANISATION_CUES for token in text.split())
    )


#: 5.3 (2026-09-27): person-to-person, wallet and card-push rails the transfer rule does not read. D6 only: the
#: transfer rule runs before the known payee (step 6 before 7), so widening it would hide a counted funder paid by
#: e-Transfer. VIREMENT covers every French RBC transfer line (Interac e-Transfer, 'Virement envoye', 'Virement par
#: Banque en direct'). Bare WISE is never a rail (WISE CHOICE, FINWISE).
_P2P_RAIL_PATTERNS = (
    re.compile(r"\bVIREMENTS?\b"),
    re.compile(r"\bZEL (?:TO|FROM)\b"),
    re.compile(r"^(?:PMNT|PAYMENT) SENT \d{2} ?\d{2}\b"),
    re.compile(r"\bAPPLE (?:CASH|WALLET)\b"),
    re.compile(r"\b(?:WISE (?:INC|US INC)|TRANSFERWISE)\b|\bDES WISE\b"),
    re.compile(r"\bIAT PAYPAL\b"),
    re.compile(r"\bGREENLIGHT DES APP\b"),
)
#: 5.3 (2026-09-27): transfer templates the 5.2 transfer-word skip does not read. Each fires only for a payee that
#: names no organisation (D11 would publish 'Unidentified lender obligation') and a row that names no financing.
_TRANSFER_TEMPLATE_PATTERNS = (
    re.compile(r"\b(?:XFR|TRF|TRSFR|TRNSFR)\b|\b(?:TRANSFER|XFER|TFR)(?=\d)"),      # abbreviations; glued digits
    re.compile(r"\bTO (?:CHKG|CHK|CHECKG|CHECKING|SAV|SAVINGS|SVGS|SHARES?|MMA)(?: ACCOUNT| ACCT)? X*\d{2,}\b"),
    re.compile(r"^(?:INTERNET|ONLINE|PHONE|TELEPHONE|MOBILE|WEB) (?:WITHDRAWAL|WDRL|WDL)$"),
    re.compile(r"\bSMART ?SAVE\b.*\bATLAS ?FIN\w*|\bATLAS ?FIN\w*.*\bSMART ?SAVE\b"),  # Atlas's Smart Save sweep
    re.compile(r"\b(?:RTP SENT|REAL TIME PAYMENT TO|FEDNOW (?:PAYMENT|PMT) TO)\b"),
)
#: 5.3 (2026-09-27): rows whose own words say they cannot pay a funder: the holder's cash withdrawal in the formats
#: the ATM rule does not read (only reference tokens or NETWORK may sit between ATM/ABM and the withdrawal word, so a
#: payee name never fills the gap), the offset of an ACH batch the holder sent from its own bank's portal (inferred
#: from the row shape; D11 already drops the batch name from the review entry), and school, tuition and childcare
#: billing.
_NON_REMITTANCE_WORD_PATTERNS = (
    re.compile(
        r"\b(?:ATM|ABM)\b(?:\s+(?:\S*\d\S*|NETWORK)){0,3}\s+(?:CASH\s+)?"
        r"(?:WITHDRAWALS?|WITHDRAW|WITHDRWLS?|WDRLS?|WDL|W D|WD)\b"
    ),
    re.compile(r"\bWITHDRAWALS? (?:ATM|ABM)(?:\s+\S*\d\S*|$)"),
    re.compile(r"\bWITHDRWLS?\b"),
    re.compile(r"(?:^|(?<=\d )|\b(?:ATM|ABM|NETWORK|TELLER|COUNTER|BRANCH|LARGE|NON \S+)\s)CASH WITHDRA\w*"),
    re.compile(r"\bRETRAITS? (?:GAB|DAB|ATM|ABM|PAR GA|AU GUICHET|AU COMPTOIR)\b"),
    re.compile(r"^G RETRAIT\b"),
    re.compile(r"^(?:BUS ONLINE ACH SETTLEMENT|ACH SETTLMT REL DATE FUND)\b"),
    re.compile(r"\bDES FACTS\b|\bPAYMENT FACTS\b|\bFACTS(?: \d+)?$"),
    re.compile(r"\b(?:TUITION|DAYCARE|CHILD ?CARE|PRESCHOOL|MONTESSORI|KINDERCARE|BRIGHTWHEEL|PROCARE)\b"),
)
#: 5.3 (2026-09-27): named consumer savings and investing originators: a closed list of verified non-funder ACH
#: names, never a category by resemblance. A name joins only after collision_check.py (registry tables, the whole
#: ledger, all_keys.json) prints no hit. Bare VANGUARD, INVEST, SAVINGS, FIDELITY and MONEYLINE stay out.
_SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS = (
    re.compile(r"\bSTASH (?:CAPITAL|INVEST(?:MENTS?)?)\b"),
    re.compile(r"\bALINEA\b"),
    re.compile(r"\bFID BKG SVC\b"),                                   # Fidelity Brokerage Services MoneyLine
    re.compile(r"\bALBERT (?:SAVINGS )?(?:DES )?EDI PYMNTS\b"),         # Albert's money movement, not its advances
    re.compile(r"\b(?:ACORNS|ROBINHOOD|COINBASE|BETTERMENT|WEALTHFRONT)\b"),
)
#: 5.3 (2026-09-27): vendors and other payees that never lend, read on the D11 payee words only (never an entry
#: description: SBFS/Rapid Finance prints 'Vendor Pay'; never the holder: a holder named '... Distributions' pays
#: Credibly), guarded by the lending words below and by the holder's own name. DISTRIBUT* also clears recurring owner
#: distributions. Names join only after collision_check.py prints no registry or ledger hit.
_VENDOR_PAYEE_PATTERNS = (
    re.compile(r"\bBOOKK\w*"),
    re.compile(r"\b(?:DISTR|DISTRIBUT\w*|FOODSERVICE)\b"),
    re.compile(r"\bMANUFACTURING\b"),
    re.compile(r"\bINVOICES?\b"),
    re.compile(r"\b(?:CINTAS\w*|UNIFIRST|ARAMARK|SYSCO|ALSCO)\b|\bUS FOODS\b"),
    re.compile(r"^(?:FACEBOOK|FACEBK|META ADS|META PLATFORMS|GOOGLE ADS|TIKTOK ADS|YELP|ANGI|HOMEADVISOR|THUMBTACK)\b"),
    re.compile(r"\b(?:UNIFORMS?|LINEN|JANITORIAL|LANDSCAP\w*|LAWN|PEST CONTROL)\b"),
    re.compile(r"\bROYALT(?:Y|IES)\b|\bFRANCHIS\w*|\b(?:AD|MARKETING|ADVERTISING) FUND\b"),
    re.compile(r"\bTITHE\w*|\bCHURCH\b|\bMINISTRIES\b|\bDONATIONS?\b|\b(?:PUSHPAY|GIVELIFY|VANCO|SUBSPLASH|EASYTITHE)\b"),
    re.compile(r"\b(?:EZPASS|ZPASS|SUNPASS|FASTRAK|TXTAG|NTTA|HCTRA|PEACH PASS|IPASS|BESTPASS|PREPASS|TOLLS?|TOLLWAY)\b"),
    re.compile(r"\b(?:DRAFTKINGS|FANDUEL|BETMGM|LOTTERY|OLG|CASINO)\b"),
)
#: 5.3: a Bill.com or Melio payment is a vendor's only when the row prints an invoice number.
_BILL_PAY_PLATFORM_PATTERN = re.compile(r"^(?:BILL COM|MELIO)\b")
_INVOICE_NUMBER_PATTERN = re.compile(r"\bINV \d")
#: 5.3: the vendor skip's lending guard: the shared roots plus the Canadian pre-authorized-debit channel word.
_VENDOR_LENDING_GUARD = re.compile(_FINANCING_ROOT_PATTERN.pattern + r"|\bPAD\b")
#: 5.3: the account holder's name words, read without the module normalizer: classifying a row normalizes exactly
#: one text (tests/test_classifier_lookups.py::test_each_row_is_normalized_exactly_once).
_HOLDER_WORD = re.compile(r"[A-Z0-9]+")


def _payee_words_are_bounded(text: str) -> bool:
    """5.3 (plan review 2026-09-28): whether an ACH field, or a reference token after the payee's first name word,
    ends the payee's words before the normalized row `text` ends. A row that is one run of words (Regions '<funder>
    ACHPMT <receiver>', Bluevine '<funder> PAY PAYMENT TO <receiver>') can end with the account holder's name."""
    labelled = _ENTITY_NAME_LABELS.sub(" ", text)
    if _ACH_FIELD_SEGMENT.search(labelled) is not None:
        return True
    started = False
    for token in labelled.split():
        if _is_reference_token(token):
            if started:
                return True
            continue
        started = started or (token not in _ENTITY_NOISE and len(token) > 1)
    return False


def _is_vendor_payee(payee: Sequence[str], text: str, account_name: str | None) -> bool:
    """5.3: the D11 payee words (or, on a bounded row, the originator segment, which then never reads a receiver
    field) name a vendor or another payee that never lends, the row prints no lending word (outside the matched vendor
    words), and those words carry none of the account holder's own name words. On a row that is one run of words the
    segment is never read, and when the holder's name is unknown the vendor word must be the payee's first word."""
    words = " ".join(payee)
    bounded = _payee_words_are_bounded(text)
    segment = _originator_segment(text) if bounded else ""
    found = next(
        (match for source in (words, segment) for pattern in _VENDOR_PAYEE_PATTERNS if (match := pattern.search(source))),
        None,
    )
    if found is None and _BILL_PAY_PLATFORM_PATTERN.search(words) and _INVOICE_NUMBER_PATTERN.search(text):
        found = _BILL_PAY_PLATFORM_PATTERN.search(words)
    if found is None:
        return False
    holder = {
        word for word in _HOLDER_WORD.findall((account_name or "").upper())
        if len(word) >= 4 and word not in _LEGAL_FORM_SUFFIXES
    }
    if not bounded and not holder and found.start() > 0:
        return False  # a label-less run of words may end with the holder's name, which is unknown here
    if holder & (set(payee) | set(segment.split())):
        return False
    return _VENDOR_LENDING_GUARD.search(text.replace(found.group(0), " ")) is None


#: 5.3 (2026-09-27): tax authorities and government agencies printed without TAX, IRS or CRA, read on the payee
#: region only (never an entry description or memo) and only for a payee that names no organisation. The row stays
#: 'other': the tax rule has no amount guard and runs before the known payee, so it is not widened.
_GOVERNMENT_PAYEE_PATTERNS = (
    re.compile(r"\b(?:UNITED STATES|U ?S) (?:(?:DEPT|DEPARTMENT) OF (?:THE )?)?TREAS(?:URY)?\b"),
    re.compile(r"\bEFTPS\b"),
    re.compile(r"\bCCRA\b"),
    re.compile(r"\bRECEIVER GENERAL\b"),
    re.compile(r"\bSECRETARY OF STATE\b"),
    re.compile(r"\bSTATE OF [A-Z]+(?: [A-Z]+)? (?:SOS|DMV)\b"),
    re.compile(r"\b(?:DEPT|DEPARTMENT) OF MOTOR VEHICLES?\b"),
    re.compile(r"\b(?:DTF|EDD|DOR|TAXATION|COMPTROLLER)\b"),
    re.compile(r"\b(?:DEPT|DEPARTMENT) (?:OF )?REV(?:ENUE)?\b"),
    re.compile(r"\bTREASURER OF STATE\b|\b[A-Z]{2} TREASURY\b"),
    re.compile(r"\bREVENU QUEBEC\b|\bMINISTRE DU REVENU\b"),
    re.compile(r"\b(?:WSIB|WORKSAFE\w*|WCB|EHT|CNESST)\b"),
)
#: 5.3: payees the financing-keyword recurrence never promotes: a government finance department (FINANCE is its
#: name, not a loan) and a retailer named ADVANCE. Their single rows stay 'other' / financing_keyword_review.
_GOVERNMENT_FINANCE_DEPARTMENT_PATTERNS = (
    re.compile(r"\b(?:DEPT|DEPARTMENT|MINISTRY|MIN|MINISTERE|DIV) (?:OF |DES )?FINANCES?\b"),
    re.compile(r"\bFINANCE DEPT\b"),
)
_RETAILER_ADVANCE_PATTERNS = (re.compile(r"\bADVANCE (?:AUTO PARTS|STORES)\b"),)
#: 5.3 (2026-09-27): a court-ordered family-support payment through a state conduit is not an MCA remittance. Read
#: before the receiver fields (a holder named '... Child Support Svcs' never silences its funder). GARNISH, LEVY,
#: LEGAL ORDER, bare SDU and CSE stay out: an MCA judgment creditor collects through a law office or a marshal.
_FAMILY_SUPPORT_WORD_PATTERNS = (
    re.compile(r"\bCHI?LD ?SUPP(?:ORT|T)?\b"),
    re.compile(r"\bFAM(?:ILY)? SUPP(?:ORT)? (?:REG(?:ISTRY)?|PAYMENT CENTER|PMT CTR|PAYMENT CTR)\b"),
    re.compile(r"\bSTATE DISBURSEMENT UNIT\b"),
)
#: 5.3 (2026-09-27): owner money is not an MCA remittance: a draw or distribution to an owner, member, partner or
#: shareholder, a dividend, a per diem, a guaranteed payment. Read before the receiver fields, with the veto
#: (DIVIDEND FINANCE is a lender); a bare DISTRIBUTION is a vendor's name.
_OWNER_PAY_WORD_PATTERNS = (
    re.compile(r"\b(?:OWNERS?|MEMBERS?|PARTNERS?|SHAREHOLDERS?) (?:DRAWS?|DISTRIBUTIONS?)\b"),
    re.compile(r"\bPER DIEM\b"),
    re.compile(r"\bGUARANTEED PAYMENTS?\b"),
    re.compile(r"\bDIVIDENDS?\b"),
)
#: 5.3: a payments platform paying a recipient it names ('Pay To: <name>'): the platform is the originator, not a
#: creditor. Only a person recipient is skipped: Payoneer's Capital Advance is collected by ACH bank debit (an
#: alternative position), so an organisation recipient, the platform itself or no recipient stays reviewed.
_PLATFORM_PAYOUT_PATTERN = re.compile(r"\bPAYONEER\b.*\bPAY TO\b(?P<recipient>.*?)(?:\bPAYMENT DATE\b|\bTRN\b|$)")


def _is_platform_payout_to_person(text: str) -> bool:
    found = _PLATFORM_PAYOUT_PATTERN.search(text)
    if found is None:
        return False
    recipient = [token for token in found.group("recipient").split()
                 if len(token) > 1 and not _is_reference_token(token)]
    return bool(recipient) and not any(
        token in _ORGANISATION_CUES or token == "PAYONEER" for token in recipient
    ) and not _names_financing(" ".join(recipient))


#: 5.3 (2026-09-27): D6 does not take a same-amount group under this amount whose payee names no organisation (it
#: would publish as 'Unidentified lender obligation') and whose row names no financing. Strict: a 25-dollar debit
#: promotes. A named payee promotes at any amount. A whole number: analysis/ carries no exact-cent literal
#: (tests/test_no_statement_hardcodes.py).
_D6_MIN_FIXED_DEBIT = 25
#: 5.3 (2026-09-27): a payment processor's own small charge to its merchant, through its merchant-services
#: spelling: Square's seller-account entry code (SQ + the entry date yymmdd) and Intuit Payment Solutions. Capped at
#: 50 dollars (Intuit's fees and chargebacks, Square's small charges): these rails also carry invoice payments to
#: third parties in the thousands, so a fixed debit above the cap stays in review. Never with loan or capital
#: wording, including Square's glued loan codes (SQCAP, SQ LOAN). A whole number
#: (tests/test_no_statement_hardcodes.py).
_PROCESSOR_ACCOUNT_DEBIT_PATTERNS = (
    re.compile(r"\bSQUARE\b.*\bSQ ?\d{6}\b|\bSQ ?\d{6}\b.*\bSQUARE\b"),
    re.compile(r"\bINTUIT (?:PYMT|PMT|PAYMENTS?) SOL(?:N|NS|UTIONS?)?\b"),
)
_PROCESSOR_DEBIT_FINANCING_GUARD = re.compile(
    r"\bLOANS?\b|\bADVANCE\b|\bFINANC(?:E|ING|IAL)\b|\bFUND(?:ER|ING)\b|\bCAP(?:ITAL)?(?![A-Z])|\bMCA\b"
    r"|\bSQ ?CAP|\bSQ ?LOAN|\bLENDING\b"
)
_PROCESSOR_ACCOUNT_CHARGE_MAX = 50
#: 5.3 (2026-09-27): an insurer whose name the ACH field cut short (INSU, INSUR, INSURA, INSURAN, INSURANC: the
#: 16-character company name or the 10-character entry description). Read on the D11 payee words only: the holder's
#: name (INDN, IND NAME, or unlabeled) never decides. INSURED, INSURER and the bare INS stay out.
_TRUNCATED_INSURANCE_WORD_PATTERN = re.compile(r"\bINSU(?:R|RA|RAN|RANC)?\b")
#: 5.3 (2026-09-27): phone and cable carriers, matched at the START of the payee's leading words
#: (_leading_payee_words), so a carrier printed after the payee's own name (a receiver that is a wireless dealer)
#: never decides. Brand names only; BELL, ROGERS, SHAW and SPRINT need their telecom word; ATT only in its bill and
#: payment forms. The VERIZON lookahead covers the registry's Verizon Visa alias only (a 'SYNCB VERIZON' card
#: payment in 'other' hides no funder).
_TELECOM_CARRIER_PATTERNS = (
    re.compile(r"(?:KOODO|FIDO|TELUS|VIDEOTRON|SASKTEL|EASTLINK|CHATR|COGECO)\b"),
    re.compile(r"(?:FREEDOM|VIRGIN|PUBLIC|LUCKY|BOOST|MINT|T) ?MOBILE\b"),
    re.compile(r"VIRGIN PLUS\b"),
    re.compile(r"BELL (?:CANADA|MOBILITY|MTS|ALIANT)\b"),
    re.compile(r"ROGERS (?:WIRELESS|COMMUNICATIONS?|CABLE)\b"),
    re.compile(r"SHAW (?:CABLE|COMMUNICATIONS?|DIRECT)\b"),
    re.compile(r"VERIZON\b(?! (?:CREDIT|VISA))"),
    re.compile(r"(?:VZWRLSS|AT AND T|METRO ?PCS|METRO BY T MOBILE|TRACFONE|COMCAST|XFINITY|CENTURYLINK|WINDSTREAM|"
               r"DIRECTV)\b"),
    re.compile(r"ATT\b(?= (?:BILL|PAYMENT|MOBILITY|UVERSE|WIRELESS)\b|\s*$)"),
    re.compile(r"(?:SPRINT|CRICKET|TOTAL) WIRELESS\b"),
    re.compile(r"(?:US|U S|CONSUMER) CELLULAR\b|USCELLULAR\b"),
    re.compile(r"(?:CHARTER|COX|FRONTIER) COMM(?:UNICATIONS?)?\b"),
    re.compile(r"DISH NETWORK\b"),
)


def _is_processor_account_charge(record: TransactionClassification) -> bool:
    text = record.normalized_description
    return (
        abs(record.amount) <= _PROCESSOR_ACCOUNT_CHARGE_MAX
        and _matches_any(text, _PROCESSOR_ACCOUNT_DEBIT_PATTERNS)
        and _PROCESSOR_DEBIT_FINANCING_GUARD.search(text) is None
    )


#: 5.3 (2026-09-27): each card_issuer_context alias's normalized words, computed once.
_CARD_ISSUER_CONTEXT_WORDS = {
    alias: tuple(normalize_transaction_description(alias).split())
    for aliases in CARD_ISSUER_CONTEXT_ALIASES.values()
    for alias in aliases
}


def _names_card_issuer(payee: Sequence[str], text: str) -> bool:
    """5.3: the payee IS a listed card issuer printed alone (C10 keeps that row unflagged): the issuer alias's words
    lead the D11 payee words, and the rest of the row names no financing. An issuer token inside a longer name
    (FABRICATED SYF CAPITAL) is never enough."""
    found = registry_match(" ".join(payee), CARD_ISSUER_CONTEXT_ALIASES)
    if found is None:
        return False
    words = _CARD_ISSUER_CONTEXT_WORDS.get(found[1], ())
    return bool(words) and tuple(payee[: len(words)]) == words and not _names_financing(
        text, besides=" ".join(words)
    )


def _d6_skip(record: TransactionClassification, payee: tuple[str, ...]) -> str | None:
    """Why D6 (spec D6 and its clarifications) does not take this default debit, or None when it may.

    `payee` is the row's D11 payee words (`_unknown_payee_tokens`). Every clause added in 5.3 reads the payee's
    words (never a receiver field) and carries the shared financing veto (`_names_financing`)."""
    text = record.normalized_description
    if _matches_any(text, _TRANSFER_WORD_PATTERNS):
        return "transfer_word"
    if _matches_any(text, _COMPENSATION_WORD_PATTERNS):
        return "compensation"
    if _is_card_purchase_posting(record):
        return "card_purchase_posting"
    if _names_only_channel_words(payee, text) and not _names_financing(text):
        return "channel_words_only"
    if _skips(_row_before_receiver(text), _P2P_RAIL_PATTERNS, text):
        return "p2p_rail"
    if _unknown_payee_name(payee) in (None, UNIDENTIFIED_LENDER_OBLIGATION) and _skips(
        _row_before_receiver(text), _TRANSFER_TEMPLATE_PATTERNS, text
    ):
        return "transfer_template"
    if _skips(_row_before_receiver(text), _NON_REMITTANCE_WORD_PATTERNS, text):
        return "not_a_remittance"
    if _skips(_row_before_receiver(text), _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS, text):
        return "savings_or_investment"
    if _is_vendor_payee(payee, text, record.account_name):
        return "named_non_lender"
    if _unknown_payee_name(payee) in (None, UNIDENTIFIED_LENDER_OBLIGATION) and _skips(
        _payee_region(text), _GOVERNMENT_PAYEE_PATTERNS, text
    ):
        return "government_payee"
    if _skips(_row_before_receiver(text), _FAMILY_SUPPORT_WORD_PATTERNS, text):
        return "family_support"
    if _skips(_row_before_receiver(text), _OWNER_PAY_WORD_PATTERNS, text):
        return "owner_pay"
    if _is_platform_payout_to_person(text):
        return "platform_payout_to_person"
    if _is_processor_account_charge(record):
        return "processor_account_charge"
    if _skips(" ".join(payee), (_TRUNCATED_INSURANCE_WORD_PATTERN,), text):
        return "truncated_insurer"
    leading = _leading_payee_words(text)
    carrier = next((found for pattern in _TELECOM_CARRIER_PATTERNS if (found := pattern.match(leading))), None)
    if carrier is not None and not _names_financing(text, besides=carrier.group(0)):
        return "telecom_carrier"
    if _names_card_issuer(payee, text):
        return "card_issuer_alone"
    return None


def _keyword_recurrence_skip(record: TransactionClassification) -> str | None:
    """Why the financing-keyword recurrence (recurring_financing_counterparty) does not take this row, or None.

    Its rows carry a financing word by definition (LOAN, ADVANCE, FINANCE, FUNDING…), so these clauses carry no
    financing veto; each names a payee that is never a lender (A7, A8)."""
    region = _row_before_receiver(record.normalized_description)
    if _matches_any(region, _GOVERNMENT_FINANCE_DEPARTMENT_PATTERNS):
        return "government_finance_department"
    if _matches_any(region, _RETAILER_ADVANCE_PATTERNS):
        return "retailer_named_advance"
    if _matches_any(region, _FAMILY_SUPPORT_WORD_PATTERNS):
        return "family_support"
    return None


def _promotion_cadence(
    records: list[TransactionClassification],
    indexes: list[int],
    min_recurring_count: int,
) -> tuple[str, float | None] | None:
    """The daily or weekly cadence of a same-amount group, or None when it does not promote.

    A recurrence needs at least ``min_recurring_count`` different dates: several
    rows on one day are one occurrence, as classify_cadence reads them.
    """
    if len(indexes) < min_recurring_count:
        return None
    dates = [parsed for index in indexes if (parsed := parse_date(records[index].date)) is not None]
    if len(set(dates)) < min_recurring_count:
        return None
    cadence, average_gap = classify_cadence(dates)
    if cadence not in {"daily", "weekly"}:
        return None
    return cadence, average_gap


#: 5.3 (2026-09-27): the D6 payee words of a card network's 'NAME, CITY, ST' line are the printed name before the
#: first comma (the city never joins the name), read without the module normalizer.
_PRINTED_NAME_WORD = re.compile(r"[A-Z0-9]+")


def _record_payee_tokens(record: TransactionClassification) -> tuple[str, ...]:
    """D6's payee words for one row: D11's words, or, on a 'NAME, CITY, ST' line with no ACH field mark, the words of
    the printed name before the first comma (5.3, 2026-09-27)."""
    printed = record.original_description or ""
    if _CARD_LOCATION_SUFFIX_PATTERN.search(printed) and not _has_ach_field_mark(record):
        return _unknown_payee_tokens(" ".join(_PRINTED_NAME_WORD.findall(printed.split(",", 1)[0].upper())))
    return _unknown_payee_tokens(record.normalized_description)


#: 5.3 (2026-09-27): the names D11 and D10 publish for a payee they cannot name. The Potential Lenders tab lists
#: each payee key of them on its own line (potential_payee_label), never one line for all.
_UNNAMED_POTENTIAL_ENTITIES = frozenset({UNIDENTIFIED_LENDER_OBLIGATION, UNIDENTIFIED_MCA_SERVICER})
_RECURRENCE_CADENCE = re.compile(r"^(daily|weekly)_fixed_debit_")


def _label_unnamed_potential_payees(records: list[TransactionClassification]) -> list[TransactionClassification]:
    """5.3 (2026-09-27): one Potential Lenders line per unnamed payee of a statement. The rows of one payee key
    (entity, rule, payee words, amount and masked recipient) share a label that names the entity, the cadence of a
    recurrence and the amount, never a payee word (D11): 'Unidentified lender obligation (weekly, 450.00)'. A second
    key with the same label gets ' #2'. canonical_entity is unchanged."""
    groups: dict[tuple[object, ...], list[int]] = {}
    for index, record in enumerate(records):
        if record.classification == "potential_lender" and record.canonical_entity in _UNNAMED_POTENTIAL_ENTITIES:
            key = (record.canonical_entity, record.match_method, _record_payee_tokens(record),
                   round(abs(record.amount), 2), _masked_recipient(record))
            groups.setdefault(key, []).append(index)
    labelled = list(records)
    used: dict[str, int] = {}
    for (entity, _method, _payee, amount, _recipient), indexes in groups.items():
        cadence = _RECURRENCE_CADENCE.match(records[indexes[0]].matched_rule or "")
        label = f"{entity} ({cadence.group(1)}, {amount:,.2f})" if cadence else f"{entity} ({amount:,.2f})"
        used[label] = used.get(label, 0) + 1
        if used[label] > 1:
            label = f"{label} #{used[label]}"
        for index in indexes:
            labelled[index] = replace(records[index], potential_payee_label=label)
    return labelled


def classify_statement_transactions(
    statement: Statement,
    *,
    min_recurring_count: int = 3,
) -> list[TransactionClassification]:
    """Create the one authoritative classification record for every ledger row."""
    records = [
        classify_transaction(
            transaction.description,
            transaction.amount,
            date=transaction.date,
            bank=statement.bank,
            account=statement.account_number,
            account_name=statement.account_name,
            direction=transaction.direction,
            source_location=f"transaction:{index + 1}",
        )
        for index, transaction in enumerate(statement.transactions)
    ]

    duplicate_of: dict[int, int] = {}
    seen: dict[tuple[object, ...], int] = {}
    for index, (transaction, record) in enumerate(zip(statement.transactions, records)):
        # Identical date/description/amount rows can be separate real postings.
        # A repeated printed running balance proves the same ledger row was
        # duplicated; without that evidence, retain both and fail closed.
        if transaction.running_balance is None:
            continue
        fingerprint = (
            transaction.date,
            record.normalized_description,
            round(transaction.amount, 2),
            round(transaction.running_balance, 2),
        )
        if fingerprint in seen:
            duplicate_of[index] = seen[fingerprint]
        else:
            seen[fingerprint] = index

    # Recurrence (spec §4.3 statement pass 2). Both kinds group by payee words
    # and amount, so two unnamed payees are never merged (D11). D6 adds the
    # digits of a masked recipient account printed after TO (None without one).
    keyword_groups: dict[tuple[tuple[str, ...], float], list[int]] = {}
    fixed_debit_groups: dict[tuple[tuple[str, ...], float, str | None], list[int]] = {}
    for index, record in enumerate(records):
        if index in duplicate_of or record.amount >= 0 or record.classification != "other":
            continue
        payee = _record_payee_tokens(record)
        if not payee:
            continue
        key = (payee, round(abs(record.amount), 2))
        if record.match_method == "financing_keyword_review" and record.canonical_entity:
            if _keyword_recurrence_skip(record) is None:
                keyword_groups.setdefault(key, []).append(index)
        elif record.match_method == "default" and _d6_skip(record, payee) is None:
            fixed_debit_groups.setdefault((*key, _masked_recipient(record)), []).append(index)

    for indexes in keyword_groups.values():
        promotion = _promotion_cadence(records, indexes, min_recurring_count)
        if promotion is None:
            continue
        cadence, average_gap = promotion
        for index in indexes:
            records[index] = replace(
                records[index],
                classification="potential_lender",
                match_method="recurring_financing_counterparty",
                matched_rule=f"{cadence}_fixed_debit_{average_gap}_day_average",
                confidence_score=0.76,
                reason=(
                    f"An unverified financing-related counterparty repeats on a {cadence} cadence; "
                    "it is potential only and requires review."
                ),
                review_required=True,
                contributes_to_potential_lender_count=True,
                contributes_to_potential_lender_totals=True,
                contributes_to_potential_withholding_exposure=True,
            )

    # D6: an unknown payee (a row no rule claimed) with fixed daily or weekly
    # debits joins the review tier. Nothing is counted without a named lender.
    for (payee, amount, _), indexes in fixed_debit_groups.items():
        entity = _unknown_entity_for_text(records[indexes[0]].normalized_description, payee) or (
            UNIDENTIFIED_LENDER_OBLIGATION
        )
        if (
            entity == UNIDENTIFIED_LENDER_OBLIGATION
            and amount < _D6_MIN_FIXED_DEBIT
            and not _names_financing(records[indexes[0]].normalized_description)
        ):
            continue
        promotion = _promotion_cadence(records, indexes, min_recurring_count)
        if promotion is None:
            continue
        cadence, average_gap = promotion
        for index in indexes:
            records[index] = replace(
                records[index],
                classification="potential_lender",
                canonical_entity=entity,
                match_method="recurring_fixed_debit",
                matched_rule=f"{cadence}_fixed_debit_{average_gap}_day_average",
                confidence_score=0.70,
                reason=(
                    f"An unknown payee repeats the same debit on a {cadence} cadence (D6); "
                    "it is potential only and requires review."
                ),
                review_required=True,
                contributes_to_potential_lender_count=True,
                contributes_to_potential_lender_totals=True,
                contributes_to_potential_withholding_exposure=True,
            )

    records = _label_unnamed_potential_payees(records)
    records = _apply_reversal_pair_context(records, set(duplicate_of))
    records = _apply_operating_source_context(records, set(duplicate_of))

    for index, original_index in duplicate_of.items():
        record = records[index]
        duplicate_revenue = record.amount > 0 and record.is_posted
        records[index] = replace(
            record,
            duplicate_of=f"transaction:{original_index + 1}",
            review_required=True,
            reason=f"{record.reason} Exact duplicate of transaction:{original_index + 1}; excluded from all totals.",
            contributes_to_lender_count=False,
            contributes_to_potential_lender_count=False,
            contributes_to_lender_totals=False,
            contributes_to_withholding_rate=False,
            contributes_to_potential_lender_totals=False,
            contributes_to_potential_withholding_exposure=False,
            contributes_to_insurance_totals=False,
            contributes_to_flagged_totals=False,
            contributes_to_lender_credit_exclusion=False,
            revenue_classification="non_revenue" if duplicate_revenue else None,
            revenue_initial_classification="non_revenue" if duplicate_revenue else None,
            revenue_match_method="duplicate_credit_exclusion" if duplicate_revenue else None,
            revenue_matched_rule="proven_duplicate_credit" if duplicate_revenue else None,
            revenue_confidence_score=1.0 if duplicate_revenue else None,
            revenue_reason=(
                f"Exact duplicate of transaction:{original_index + 1}; excluded from revenue."
                if duplicate_revenue else None
            ),
            revenue_review_required=False,
            revenue_review_status="not_required" if duplicate_revenue else None,
            revenue_context_signals=("proven_duplicate",) if duplicate_revenue else (),
            revenue_related_transaction=(
                f"transaction:{original_index + 1}" if duplicate_revenue else None
            ),
            contributes_to_verified_revenue=False,
            contributes_to_unverified_deposit=False,
            contributes_to_true_revenue=False,
            contributes_to_potential_revenue=False,
            contributes_to_non_revenue=duplicate_revenue,
        )

    return records
