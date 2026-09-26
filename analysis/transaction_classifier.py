from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from statistics import mean, pstdev
from typing import Literal, Sequence, TYPE_CHECKING

from .classification_registry import (
    BANK_SPECIFIC_LENDER_ALIASES,
    INSURANCE_PROVIDER_ALIASES,
    LEASE_PROVIDER_ALIASES,
    LEGACY_CONFIRMED_LENDER_ALIASES,
    LEGACY_POTENTIAL_LENDER_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
)
from .dates import parse_date
from .flag_groups import FLAG_GROUP_BY_STATE
from .revenue import RevenueState, revenue_contribution_flags
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from .description_text import normalize_transaction_description
from .payee_matcher import registry_match

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

CLASSIFICATION_VERSION = "5.0"


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
    return registry_match(normalize_transaction_description(description), LEGACY_CONFIRMED_LENDER_ALIASES)


def match_insurance_provider(description: str) -> tuple[str, str] | None:
    return registry_match(normalize_transaction_description(description), INSURANCE_PROVIDER_ALIASES)


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
_LEASE_PATTERNS = (
    re.compile(r"\bLEASE(?:S|D| PAYMENT| PMT)?\b"),
    re.compile(r"\bEQUIPMENT (?:FINANCING|FINANCE|RENT|RENTAL|PAYMENT)\b"),
    re.compile(r"\bVEHICLE (?:FINANCING|FINANCE|LEASE|PAYMENT)\b"),
    re.compile(r"\bAUTO LEASE\b"),
)
_CREDIT_CARD_PATTERNS = (
    re.compile(r"\bCREDIT CARD (?:PAYMENT|PMT|PYMT)\b"),
    re.compile(r"\bCARDMEMBER SERVICES?\b"),
    re.compile(r"\b(?:VISA|MASTER ?CARD|AMEX|AMERICAN EXPRESS) (?:PAYMENT|PMT|PYMT|EPAYMENT)\b"),
    re.compile(r"\bATB MASTER ?CARD\b"),
    re.compile(r"\bCAPITAL ONE\b.*\b(?:ONLINE PMT|CARD PAYMENT|PAYMENT)\b"),
    re.compile(r"\bCAPITAL ?ON ?TAP\b"),
    re.compile(r"\bPAYMENT TO (?:VISA|MASTER ?CARD|AMEX|AMERICAN EXPRESS)\b"),
)
_CHECK_PATTERNS = (
    re.compile(r"\bCHECKS?\b"),
    re.compile(r"\bCHEQUES?\b"),
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

    insurance_match = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurance_match is not None:
        entity, alias = insurance_match
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
    lender_match = registry_match(text, LEGACY_CONFIRMED_LENDER_ALIASES)
    if lender_match is not None:
        entity, alias = lender_match
        return _RevenueDecision(
            "non_revenue",
            entity,
            "lender_registry_credit_exclusion",
            alias,
            "confirmed_lender_funding_credit",
            0.99,
            f"Credit matched confirmed lender alias '{alias}' and is funding, not revenue.",
            context_signals=("credit_direction", "confirmed_lender_source"),
        )
    potential_lender_match = registry_match(text, LEGACY_POTENTIAL_LENDER_ALIASES)
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
    lease_match = registry_match(text, LEASE_PROVIDER_ALIASES)
    if lease_match is not None:
        entity, alias = lease_match
        return _RevenueDecision(
            "non_revenue",
            entity,
            "lease_provider_credit_exclusion",
            alias,
            "lease_or_equipment_financing_credit",
            0.95,
            f"Credit matched lease or equipment-financing alias '{alias}' and is not operating revenue.",
            context_signals=("credit_direction", "lease_provider"),
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


_ENTITY_NOISE = {
    "ACH", "EFT", "DEBIT", "DIRECT", "DEB", "EXTERNAL", "WITHDRAWAL",
    "AUTOMATIC", "AUTO", "W", "D", "ORIG", "ORIGINATOR", "CO", "COMPANY",
    "NAME", "DESCR", "DESCRIPTION", "ENTRY", "DETAIL", "PAYMENT", "PAYMENTS",
    "PAY", "PMT", "PYMT", "REPAYMENT", "REMITTANCE", "PAD", "BUSINESS", "ONLINE",
    "WEB", "CCD", "PPD", "LOAN", "MCA", "TO", "FROM", "FOR",
}
_ENTITY_ACRONYMS = {"ACH", "BDC", "CMCA", "EFT", "LLC", "MCA", "SBA", "SNAP"}


def _canonical_unknown_entity(text: str) -> str | None:
    tokens: list[str] = []
    for token in text.split():
        if token in _ENTITY_NOISE:
            continue
        if token.isdigit() and len(token) >= 4:
            continue
        if re.fullmatch(r"X{2,}\d*", token):
            continue
        if re.fullmatch(r"(?:TRACE|REF|ID)\d+", token):
            continue
        if re.fullmatch(r"\d{1,2}(?:\d{1,2}){1,2}", token):
            continue
        tokens.append(token)
    if not tokens:
        return None
    meaningful = [token for token in tokens if token not in {"FINANCE", "FINANCING", "FUNDING", "CAPITAL", "FUNDER"}]
    if not meaningful:
        return None
    rendered = [token if token in _ENTITY_ACRONYMS else token.title() for token in tokens[:8]]
    return " ".join(rendered)


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
) -> TransactionClassification:
    is_debit = amount < 0
    contributes_lender = classification == "confirmed_lender" and is_debit and is_posted
    contributes_potential = classification == "potential_lender" and is_debit and is_posted
    contributes_insurance = classification == "insurance" and is_debit and is_posted
    flag_group = FLAG_GROUP_BY_STATE.get(classification)
    contributes_flagged = flag_group is not None and is_debit and is_posted
    revenue = _classify_credit_revenue(
        text,
        amount,
        posted=is_posted,
        account_name=account_name,
        direction_consistent=direction_consistent,
    )
    revenue_state = revenue.classification if revenue is not None else None
    revenue_flags = revenue_contribution_flags(revenue_state)
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
        flagged_group=flag_group.key if flag_group is not None else None,
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
    common = {
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

    insurance_match = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurance_match is not None:
        provider, alias = insurance_match
        return _build_record(
            **common,
            classification="insurance",
            canonical_entity=provider,
            match_method="insurance_provider_alias",
            matched_alias=alias,
            matched_rule="verified_insurance_provider",
            confidence_score=0.99,
            reason=f"Matched maintained insurance provider alias '{alias}'.",
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

    if (
        amount < 0
        and _matches_any(text, _POS_PATTERNS)
        and not _matches_any(text, _POS_EXCLUSION_PATTERNS)
        and (
            "TRANSFER" not in text
            or _matches_any(text, _EXPLICIT_CARD_PURCHASE_PATTERNS)
        )
        and not _matches_any(text, _LEASE_PATTERNS)
        and registry_match(text, LEASE_PROVIDER_ALIASES) is None
    ):
        return _build_record(
            **common,
            classification="pos",
            match_method="ordered_rule",
            matched_rule="point_of_sale_purchase",
            confidence_score=0.98,
            reason="The posted debit is explicitly identified as a point-of-sale purchase.",
        )

    if amount < 0 and _matches_any(text, _ATM_PATTERNS) and not _matches_any(text, _FEE_PATTERNS):
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

    if _matches_any(text, _PAYROLL_PATTERNS):
        return _build_record(
            **common,
            classification="payroll",
            match_method="strong_non_lender_exclusion",
            matched_rule="payroll",
            confidence_score=0.96,
            reason="The descriptor identifies payroll, wages, or a payroll provider.",
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

    lease_match = registry_match(text, LEASE_PROVIDER_ALIASES)
    if lease_match is not None or _matches_any(text, _LEASE_PATTERNS):
        entity, alias = lease_match or (None, None)
        return _build_record(
            **common,
            classification="lease_or_equipment_financing",
            canonical_entity=entity,
            match_method="lease_provider_alias" if lease_match else "strong_non_lender_exclusion",
            matched_alias=alias,
            matched_rule="lease_or_equipment_financing",
            confidence_score=0.98 if lease_match else 0.95,
            reason="The descriptor identifies a lease, vehicle lease, or equipment-financing obligation.",
        )

    if _matches_any(text, _RENT_PATTERNS):
        return _build_record(
            **common,
            classification="rent",
            match_method="strong_non_lender_exclusion",
            matched_rule="rent",
            confidence_score=0.95,
            reason="The descriptor identifies rent or a landlord payment.",
        )

    if _matches_any(text, _CREDIT_CARD_PATTERNS):
        return _build_record(
            **common,
            classification="credit_card_payment",
            match_method="strong_non_lender_exclusion",
            matched_rule="credit_card_payment",
            confidence_score=0.97,
            reason="The descriptor identifies a credit-card account payment.",
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

    lender_match = registry_match(text, LEGACY_CONFIRMED_LENDER_ALIASES)
    if lender_match is not None:
        lender, alias = lender_match
        if amount < 0:
            return _build_record(
                **common,
                classification="confirmed_lender",
                canonical_entity=lender,
                match_method="verified_lender_alias",
                matched_alias=alias,
                matched_rule="confirmed_lender_registry",
                confidence_score=0.99,
                reason=f"Matched maintained lender alias '{alias}' after all strong exclusions.",
            )
        return _build_record(
            **common,
            classification="other",
            canonical_entity=lender,
            match_method="verified_lender_alias_credit",
            matched_alias=alias,
            matched_rule="lender_funding_credit",
            confidence_score=0.97,
            reason="Matched a verified lender on a credit; it is excluded from lender debits and the withholding numerator.",
            contributes_to_lender_credit_exclusion=amount > 0,
        )

    bank_registry = BANK_SPECIFIC_LENDER_ALIASES.get((bank or "").upper(), {})
    bank_match = registry_match(text, bank_registry)
    if bank_match is not None and amount < 0:
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

    potential_match = registry_match(text, LEGACY_POTENTIAL_LENDER_ALIASES)
    if potential_match is not None and amount < 0:
        lender, alias = potential_match
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

    if amount < 0 and _matches_any(text, _DIRECT_DEBIT_LOAN_PATTERNS):
        return _build_record(
            **common,
            classification="potential_lender",
            canonical_entity="Unidentified lender obligation",
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
            canonical_entity=candidate or "Unidentified lender obligation",
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
        updated[credit_index] = replace(
            updated_credit,
            reversal_of=related_location if is_settlement_reversal else None,
            settlement_reversal=is_settlement_reversal,
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

    groups: dict[tuple[str, float], list[int]] = {}
    for index, record in enumerate(records):
        if index in duplicate_of:
            continue
        if (
            record.classification == "other"
            and record.match_method == "financing_keyword_review"
            and record.canonical_entity
            and record.amount < 0
        ):
            groups.setdefault((record.canonical_entity, round(abs(record.amount), 2)), []).append(index)

    for (entity, _), indexes in groups.items():
        if len(indexes) < min_recurring_count:
            continue
        dates = [parsed for index in indexes if (parsed := parse_date(records[index].date)) is not None]
        cadence, average_gap = classify_cadence(dates)
        if cadence not in {"daily", "weekly"}:
            continue
        for index in indexes:
            record = records[index]
            records[index] = replace(
                record,
                classification="potential_lender",
                canonical_entity=entity,
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
