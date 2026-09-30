from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import cache
from datetime import date
from statistics import mean, pstdev
from typing import Literal, Sequence, TYPE_CHECKING

from .classification_registry import (
    BANK_NAME_ALIASES,
    BLUE_PLAN_CLAIM_PAYERS,
    CARD_SETTLEMENT_CREDIT_FORMS,
    CardSettlementForm,
    BANK_SPECIFIC_LENDER_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    FIELD_ORDER_PAYEE_FORMS,
    GATED_PROCESSOR_ALIASES,
    INSURANCE_PROVIDER_ALIASES,
    OPERATING_ALIASES_READ_WITH_VETOES,
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    OPERATING_REVENUE_TRUNCATIONS,
    OPERATING_SOURCE_CONTEXT_WORDS,
    OPERATING_SOURCE_PAYOUT_FORMS,
    OPERATING_SOURCES_READ_WITH_VETOES,
    PAYEE_GROUP_REGISTRIES,
    PAYOUT_CREDIT_ENTITIES,
    POTENTIAL_LENDER_ALIASES,
    PREMIUM_FINANCE_ALIASES,
    REVIEW_FLAG_ENTITIES,
    WHOLESALE_AUCTION_PAYOUT_FORMS,
    WHOLESALE_AUCTION_REFUND_NAMES,
    _operating_alias_cut,
)
from .dates import parse_date
from .flag_groups import FINANCING_STATES, FLAG_GROUP_BY_KEY, FLAG_GROUP_BY_STATE
from .revenue import RevenueState, revenue_contribution_flags, tier_of_state
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from .description_text import normalize_transaction_description
from .payee_matcher import PayeeMatch, match_debt_relief_payee, match_known_payee, registry_match
# 5.6: the true-revenue pass reads this module's readers at call time, so it imports nothing from here at load.
from .true_revenue import DealerFunding, apply_true_revenue_pass, dealer_funding_reading

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
#: printed after TO is part of the payee. 5.3 (2026-09-27): the
#: false-potential-lender release: D6 skips, rule extensions, the routing of
#: unconfirmed flag payees, the D11 naming fixes, the tab's payee labels and the
#: Debt relief group. 5.4 (2026-09-28): the owner's ruling that Idea Financial is
#: a counted lender, no longer a line of credit (its rows printing LOC or LINE OF
#: CREDIT stay Lines of credit, D9). 5.5 (2026-09-28): the true-revenue bug fixes
#: (docs/superpowers/specs/2026-09-28-true-revenue-design.md §7): the revenue
#: text readers, the operating registry, card and payout forms, the recurrence
#: pass, payer remittance, public and healthcare payers, wires that cite an
#: invoice, auctions and property platforms, and the non-revenue narrowings.
#: Review fixes (2026-09-29): glued dates never change a reading; the holder's
#: name never names a payer; own-account transfers, glued and invoice wires and
#: platform financing words keep their vetoes.
#: 5.6 (2026-09-28): the definitional rules (§8): every posted credit carries a
#: revenue tier, True revenue and its counted and held parts, and the review gate.
#: Review decisions (2026-09-29): direction conflicts never lifted; bare
#: transfers, micro entries, owner money, deferred sources and round-sum repeats
#: held or counted as ruled; Q7 honours the section 8.1 holds.
#: Moves with `webapp.artifact_cache.ANALYSIS_STAGE_VERSION`.
CLASSIFICATION_VERSION = "5.6"

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
    # 5.6 (true revenue spec §5.4): the per-row contract. Every posted credit carries exactly one tier (verified,
    # counted_flagged, excluded_pending_review, non_revenue); a counted or held row carries its reason code
    # (analysis.revenue.REVENUE_TIER_REASONS). The initial tier is the one the rules gave, which a reset restores.
    revenue_tier: str | None = None
    revenue_initial_tier: str | None = None
    revenue_tier_reason: str | None = None
    contributes_to_counted_flagged: bool = False
    contributes_to_excluded_pending_review: bool = False

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
#: (normalization reads PAYMT as PAYMENT, and LN as LOAN except where LN ends a street address with no
#: loan-product word before it and no payment word after it, 5.5 §7.11: 'CML LN PAYMT' reads LOAN PAYMENT) ...
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
    # S4.2 final review (fix 4): CANCELLED's French words ('VIREMENT ANNULE', 'VIREMENT INTERAC ANNULE', 'ANNUL VFC'),
    # whole words with the veto convention's (?<![A-Z]) left boundary, so a digit glued on the left never hides one.
    # S4.2 fix round 5: and their plurals, ANNULES and ANNULEES.
    re.compile(r"(?<![A-Z])(?:ANNUL|ANNULE|ANNULEE|ANNULES|ANNULEES|ANNULATION)\b"),
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
    # 5.5 (§7.11): BOOK TRANSFER and FUNDS TRANSFER are own-account only without a third-party originator
    # (_own_book_or_funds_transfer).
    re.compile(r"\b(?:INTERNAL|ACCOUNT) TRANSFER\b"),
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
#: 5.6 (A3-G re-review): the posting words a bank prints before the Canada Revenue Agency's refund, read after the
#: revenue text and the template prefixes are stripped: a glued or spaced date, Canada's GC (Government of Canada) and
#: the direct-deposit, EFT and payment words ('0102DIRECT DEPOSIT CANADA RIT', 'GC DIRECT DEPOSIT CANADA RIT',
#: 'PAYMENT FROM CANADA RIT'). Each number ends at a space or a letter, so no number splits two ways.
_CRA_POSTING_PREFIX = re.compile(
    r"^(?:\d+(?: |(?=[A-Z])))*(?:(?:GC|DIRECT DEPOSIT|DIRECT DEP|DEPOSIT|DEP|ELECTRONIC DEPOSIT"
    r"|EFT(?: CREDIT| DEPOSIT)?|MISC PAYMENT|PAY(?:MENT)?(?: FROM)?) (?:\d+(?: |(?=[A-Z])))*)*"
)
_CRA_REFUND_PAYER = re.compile(r"CANADA (?:RIT|RIF)\b")


def _canada_tax_refund(text: str) -> bool:
    """5.6 (A3-G, review and re-review): the refund's form starts the payer, after the posting words only; a payer
    that names Canada's form after its own name is that payer ('FABRIKAM LIFE CANADA RIF PMT')."""
    payer = _strip_revenue_template(revenue_text(text))
    return _CRA_REFUND_PAYER.match(_CRA_POSTING_PREFIX.sub("", payer, count=1)) is not None


class _CanadaTaxRefundForm:
    """5.6 (A3-G re-review): the refund reader in the strong non-revenue list, read as its patterns are (search)."""

    pattern = "CANADA (?:RIT|RIF) after the posting words"

    def search(self, text: str) -> "_CanadaTaxRefundForm | None":
        return self if _canada_tax_refund(text) else None


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
    # 5.5 (§7.11, T5): the tax-refund abbreviations (Treasury's TAX REF; a state's glued TAXRFD, and TAXEIC, review
    # I6) and account-verification micro-deposits.
    re.compile(r"\bTAX ?REF(?:UND)?S?\b|[A-Z]*TAXRFD\b|\bTAX RFD\b|\bTAXEIC\b"),
    # 5.6 (A3-G): the Canada Revenue Agency's income-tax refund direct deposit (RIT and RIF are the banks' two labels
    # of one refund, 'DIRECT DEPOSIT CANADA RIT RIF'). Its benefit, credit and payment forms (GST TPS, CCB, EI, CPP,
    # OAS, CEWS) wait for the owner. A3-G review and re-review: the form starts the payer (_CanadaTaxRefundForm).
    _CanadaTaxRefundForm(),
    re.compile(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b"),
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
    re.compile(r"\bMARKETPLACE (?:PAYOUT|SETTLEMENT)\b"),
    # 5.5 (§7.7): the NACHA claim-payment entry, glued on either side (Chase's SEC, a sixteen-character name or
    # digits on the left); its unbounded branch takes only the full token, so THECLAIMPMT stays unmatched.
    re.compile(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"),
    re.compile(r"\bEDIRPAY\b"),
    re.compile(r"\bMERCHANT BANK(?:CD|CARD|ED) DEPOSIT\b"),
    re.compile(r"\bMTOT DEP\b"),
)
#: 5.5 (§6.1 step 11, §7.11): the customer and invoice descriptors. CUSTOMER is never read in CUSTOMER ID (Truist
#: prints it on every ACH line) and never with CHECK or CHEQUE (Q3). A payer the holder test or the numbered-company
#: guard matches never verifies through them (§5.2).
_CUSTOMER_INVOICE_DESCRIPTORS = (
    re.compile(r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\bCUSTOMER\b(?! ID\b).*\b(?:ACH|PAYMENT|DEPOSIT)\b"),
    re.compile(r"^(?!.*\bCHE(?:CK|QUE)S?\b).*\b(?:ACH|PAYMENT|DEPOSIT)\b.*\bCUSTOMER\b(?! ID\b)"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
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

    **Decided by `_INTERNAL_TRANSFER_CREDIT_PATTERNS` and, since 5.5 (§7.11),
    the narrowed book and funds transfer rule, and by nothing else.** Every
    member of that tuple names one member's OWN accounts as the source or the
    destination — `TRANSFER FROM SAVINGS`, `SH TO SH`, `ACCOUNT TO ACCOUNT`,
    `TRANSFER FROM <masked> TO <masked>`. A `BOOK TRANSFER` or `FUNDS TRANSFER`
    (never `ELECTRONIC FUNDS TRANSFER DEPOSIT`, an EFT channel) designates an
    own account only when it prints no third-party originator
    (`_third_party_originator`): an account description after FROM
    (`BUSINESS SAVINGS`, `LINE OF CREDIT`) names no payer, a payer's name does.
    Without the owner's yes to T19 every `BOOK TRANSFER` designates one. No
    account name is read here, so `_own_book_or_funds_transfer`'s holder test
    does not apply: a transfer that prints the holder's own name as its
    originator designates no own account for R-d, the conservative direction.

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
    text = normalize_transaction_description(description)
    # 5.5 (§7.11): a book or funds transfer designates an own account only when it prints no third-party originator.
    return _matches_any(text, _INTERNAL_TRANSFER_CREDIT_PATTERNS) or (
        _BOOK_OR_FUNDS_TRANSFER.search(text) is not None
        and _EFT_FUNDS_TRANSFER.search(text) is None
        and (
            (_BOOK_OR_FUNDS_TRANSFER.search(text).group(0).startswith("BOOK") and not THIRD_PARTY_BOOK_TRANSFER_AS_WIRE)
            or _third_party_originator(text) is None
        )
    )


# ---------------------------------------------------------------------------------------------------------------------
# Classification 5.5 (docs/superpowers/specs/2026-09-28-true-revenue-design.md §5.2, §6.1, §7): the credit revenue
# readers. Every credit revenue rule reads revenue_text(text); D11, normalized_description and every debit rule keep
# the normalized row as it is.
# ---------------------------------------------------------------------------------------------------------------------

#: T18 (owner, 2026-09-28: yes; OQ5): a credit that prints the NACHA claim-payment entry skips the insurer registry, so
#: an insurer's healthcare claim payment to a provider verifies. Off, it is held with the insurer's other credits.
HCCLAIMPMT_CLAIM_FIRST = True
#: T19 (owner, 2026-09-28: yes; OQ6): Chase's BOOK TRANSFER CREDIT B/O <originator> from someone other than the holder,
#: and Bank of America's WIRE TYPE BOOK IN, are incoming wires, not own-account transfers.
THIRD_PARTY_BOOK_TRANSFER_AS_WIRE = True

#: §7.0: Chase glues the SEC code to the entry description ('CO ENTRY DESCR HCCLAIMPMTSEC CCD'). Bounded to the
#: entry-description field, so a word elsewhere that ends in SEC is untouched.
_GLUED_SEC_CODE = re.compile(
    r"(\bCO (?:ENTRY )?DESCR (?:\S+ ){0,2}?\S{2,}?)SEC (CCD|CTX|PPD|WEB|IAT|COR|TEL|POP|BOC|ARC|RCK|CIE)\b"
)
#: §7.0, S2.1 review finding 1: a date the bank prints at the row's start, glued to the first word ('01/02Zelle ...'
#: normalizes to '01 02ZELLE ...'). Two numbers of one or two digits, each 1 to 31 (a month and a day, in either
#: order), then a letter with no space before it; no other leading number is removed. A spaced pair is kept: '5 3 ...'
#: is Fifth Third's 5/3 brand (fix round 2). The channel gate reads a spaced row through its own patterns: their left
#: boundary is (?<![A-Z]) and a form anchored at the row's start accepts a leading date (fix round 3).
_LEADING_DATE = re.compile(r"^(?:0?[1-9]|[12]\d|3[01]) (?:0?[1-9]|[12]\d|3[01])(?=[A-Z])")
#: §7.0: the fields between Chase's originator and its entry description, and Bank of America's DES label.
_CHASE_FIELDS_BETWEEN = re.compile(r" ORIG ID \S+ DESC DATE(?: \S+)? CO (?:ENTRY )?DESCR ")
_BOFA_DES_FIELD = re.compile(r" DES ")
#: §5.2: the receiver fields, where the bank prints the account holder (PNC labels its RECEIVER NAME).
_CREDIT_RECEIVER_FIELD = re.compile(r"\b(?:INDN|IND NAME|IND ID|RECEIVER NAME)\b")
#: A receiver field's value ends at the next ACH field: CO ID, TRN, TRACE or the SEC code (5.3, shared with
#: _RECEIVER_FIELD_VALUE).
_RECEIVER_VALUE_END = r".*?(?=\b(?:CO ID|TRN|TRACE|PPD|CCD|WEB|CTX|TEL|ARC|BOC)\b|$)"
#: §5.2 (S2.2 review): a receiver field of _CREDIT_RECEIVER_FIELD with its value.
_CREDIT_RECEIVER_VALUE = re.compile(_CREDIT_RECEIVER_FIELD.pattern + _RECEIVER_VALUE_END)
#: §5.2 (S4.2 re-review fix 7): an incoming wire's beneficiary field (BNF, NBNF, BENEFICIARY, BNF NAME, as the wire
#: readers name them) with its value, up to the next wire field. ORIG TO BNF is the originator's remittance text, not
#: a beneficiary. S4.2 final review (fix 6): the value also ends at every originator label the wire readers read
#: (_WIRE_ORIGINATOR_LABEL: WIRE IN FROM, WIRE FROM, FUNDS TRANSFER CREDIT TT, INBD FUNDS TRANSFER RECEIVED) and at
#: FROM, so 'INCOMING WIRE BNF <holder> FROM STRIPE INC' still names its originator.
_CREDIT_WIRE_BENEFICIARY_VALUE = re.compile(
    r"(?<!\bTO )\b(?:N?BNF|BENEFICIARY)(?: NAME)?\b.*?"
    r"(?=\b(?:REF|OBI|RFB|IMAD|OMAD|TRN|SRF|BBI|SND BK|PMT DET|RMR|ORIG|ORIGINATOR|ORG|B O|WIRE IN FROM|WIRE FROM"
    r"|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER RECEIVED|FROM)\b|$)"
)
#: §5.2: the bank's words printed before the payer, removed before the payer is read (with _PAYEE_TEMPLATE_PREFIX).
_REVENUE_TEMPLATE_PREFIX = re.compile(
    r"^(?:BUSINESS TO BUSINESS ACH CREDIT|CCD DEPOSIT|CTX DEPOSIT|ELECTRONIC DEPOSIT FROM|ELECTRONIC DEPOSIT"
    r"|ELECTRONIC CREDIT|ACH CORP CREDIT|ACH DEPOSIT|ACH CREDIT|DEPOSIT FROM|PREAUTHORIZED CREDIT|EFT CREDIT"
    r"|DIRECT DEPOSIT|MISC PAYMENT|BILL PAYMENT)\b ?"
)
#: §5.2: a wire's originator starts after one of these labels (never ORIG CO NAME, ORIG ID or ORIG TO BNF). 5.6 (A3-G
#: re-review): ORIGINATOR and ORG take the same guards: ORIGINATOR TO BENEFICIARY (ORG TO BNF) is a purpose field's
#: label, never an originator label.
_WIRE_ORIGINATOR_LABEL = re.compile(
    r"\b(?:B O|ORIGINATOR(?: NAME)?(?! TO BNF\b| TO BENEFICIARY\b)|ORIG(?! CO NAME\b)(?! ID\b)(?! TO BNF\b)"
    r"|ORG(?! TO BNF\b| TO BENEFICIARY\b)|WIRE IN FROM|WIRE FROM"
    r"|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER RECEIVED)\b ?"
)
#: §5.2: ... and ends at the next wire field. ID is read as a field too: Bank of America prints 'ORIG:<name> ID:<n>'.
#: 5.6 (A3-G re-review): so does the originator-to-beneficiary phrase, which opens a purpose field.
_WIRE_FIELD_END = re.compile(
    r"\b(?:BNF|NBNF|BENEFICIARY|BBI|OBI|REF|SRF|TRN|RFB|IMAD|ACCT|SND BK|ID"
    r"|(?:ORG|ORIGINATOR) TO (?:BNF|BENEFICIARY))\b"
)
#: §5.2, §7.9 (Santander's layout): 'USD WIRE IN FROM <sending bank> ACCT <n> <originator> REF <purpose>'. The words
#: after WIRE IN FROM name the sending bank; the originator follows the account number (the field §7.9 cuts at 16).
_SANTANDER_WIRE = re.compile(r"^(?:[A-Z]{3} )?WIRE IN FROM\b(?P<bank>.*?)\bACCT \d+ (?P<originator>.*?)(?=\bREF\b|$)")
#: §5.2: a person-to-person or transfer sender follows FROM and ends at one of these words.
_SENDER_END = re.compile(r"\b(?:ON|REF|CONF|MEMO|TRN|ID|FOR|NOTE|PMT INFO|PAYMENT INFO)\b")
#: §5.2: the entry fields: Bank of America's DES, Chase's CO ENTRY DESCR, a wire's purpose fields, a transfer's memo.
_BOFA_ENTRY_FIELD = re.compile(
    r"\bDES (.*?)(?=\b(?:ID|INDN|CO ID|IND NAME|IND ID|CCD|CTX|PPD|WEB|IAT|TEL|POP|BOC|ARC|RCK|CIE)\b|$)"
)
_CHASE_ENTRY_FIELD = re.compile(
    r"\bCO (?:ENTRY )?DESCR (.*?)(?=\b(?:SEC|TRACE|EED|IND ID|IND NAME|TRN|CCD|CTX|PPD|WEB|IAT)\b|$)"
)
_WIRE_ENTRY_FIELD = re.compile(
    r"\b(?:OBI|RMR|PMT DET|RFB|REF)\b (.*?)(?=\b(?:BNF|NBNF|BBI|OBI|SRF|TRN|IMAD|ACCT|SND BK|RFB|ORIG|B O|ORG)\b|$)"
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
    r"|DEPOSIT FROM|PAID FROM|PAYMENT FROM|CREDIT FROM|MSP DIV|AP CC)\b"
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
#: §5.2, T11: a numbered company. The template form is read on the row before the receiver fields (BMO cuts the name
#: to the field, so the digits alone decide); the payer-region form keeps the region's leading digit token.
_NUMBERED_COMPANY_TEMPLATE = re.compile(
    r"^(?:DIRECT DEPOSIT|ACC(?:OUN)?TS? PAYABLE(?: PMT)?|MISC PAYMENT|BILL PAYMENT) \d{6,}\b"
)
#: A3: a numbered company's number before its province or territory, or Quebec's NNNN NNNN before QUEBEC (the
#: province arm of _NUMBERED_COMPANY_REGION), kept when a wire's sender is read after its label.
_NUMBERED_PROVINCE_START = re.compile(rf"^\d{{6,}} {_PROVINCE}\b|^\d{{4}} \d{{4}} {_QUEBEC}\b")
_NUMBERED_COMPANY_REGION = re.compile(
    rf"^\d{{6,}}\b(?: {_PROVINCE}\b| (?:[A-Z]+ ){{0,4}}(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|ULC|LLC|LP|CO"
    rf"|COMPANY)\b)"
    # Quebec prints its numbered companies as NNNN-NNNN (normalized NNNN NNNN), always before the province. S4.2 fix
    # round 5: Quebec's words only, so another province's word or code starting a name ('NORTH STAR', 'AB') is none.
    rf"|^\d{{4}} \d{{4}} {_QUEBEC}\b"
)
#: §6.1 step 9b: consumer person-to-person rails (never verified by any step), and real-time or push rails (verified
#: by the operating registry only).
#: S2.1 re-review (fix round 3): in these four gate families every left boundary is (?<![A-Z]), never \b (the owner's
#: card-form convention), so digits glued to a rail or a form ('01/02/2054Zelle', '0102Zelle') no longer hide it; a
#: right boundary stays \b. A form anchored at the row's start accepts a leading MM DD pair, glued or spaced
#: ('01/02 Remote'). Residual (0 corpus rows): a longer prefix before the bare anchored REMOTE or GC form
#: ('0102Remote', '01/02/2054 Remote', '2054 GC 1234 Deposit') still reads no gate. Against the older \b patterns
#: the gate reading only moves toward closed or push; the shared patterns also move the payer region and entry
#: fields of those same rows.
_CONSUMER_P2P_RAIL = re.compile(
    r"(?<![A-Z])(?:ZELLE|INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|VIREMENT|VFC|AUTODEPOSIT|VENMO|CASH ?APP|SQUARE CASH"
    r"|APPLE CASH|POPMONEY)\b"
)
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
#: §8.2: cash, branch and teller, and ATM deposits (Q2: counted, never verified), read only on a row that prints no
#: electronic-payment form and no person-to-person rail.
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
)
#: §8.2: transfer wording.
_TRANSFER_WORDING = re.compile(
    r"\b(?:TRANSFER|TRNSFR|XFER|TFR|BR TO BR|ONLINE BANKING|INTERNET (?:BANKING|TRANSFER)|FUNDS TRANSFER)\b"
)
#: §5.2: the ACH originator and entry fields (Bank of America's DES, Chase's ORIG CO NAME and CO ENTRY DESCR).
_ACH_ORIGINATOR_FIELD = re.compile(r"\b(?:DES|CO ENTRY DESCR|ORIG CO NAME)\b")


def revenue_text(text: str) -> str:
    """5.5 (§7.0): the text every credit revenue rule reads: the normalized row without a glued leading date
    ('01 02ZELLE PAYMENT' becomes 'ZELLE PAYMENT', so a glued date never hides a rail from the channel gate or a label
    from a reader anchored at the row's start; a spaced '5 3 ...' is kept), and with Chase's glued SEC code split
    ('CO ENTRY DESCR HCCLAIMPMTSEC CCD' becomes 'CO ENTRY DESCR HCCLAIMPMT SEC CCD')."""
    return _GLUED_SEC_CODE.sub(r"\1 SEC \2", _LEADING_DATE.sub("", text, count=1))


def _joined_text(text: str) -> str:
    """5.5 (§7.0): the originator and the entry description side by side: Bank of America's ' DES ' and Chase's
    'ORIG ID <id> DESC DATE [<date>] CO ENTRY DESCR' removed between them."""
    return _BOFA_DES_FIELD.sub(" ", _CHASE_FIELDS_BETWEEN.sub(" ", text, count=1), count=1)


def _before_receiver(text: str) -> str:
    """5.5 (§5.2): the row up to its first receiver field (INDN, IND NAME, IND ID, RECEIVER NAME)."""
    return _CREDIT_RECEIVER_FIELD.split(text, 1)[0].rstrip()


def _without_receiver_value(text: str) -> str:
    """5.5 (§5.2, S2.2 review): the text with each receiver field's value removed and every field after it kept, for
    the operating alias and the ledger gate. The holder's name never names a source ('INDN SQUARE INC CO ID ...' is
    the holder), while Bank of America's PMT INFO addenda, printed after INDN and CO ID, still does ('... CO ID 1 CCD
    PMT INFO WORLDPAY ...'): _before_receiver would cut the addenda away with the receiver.

    S4.2 re-review (fix 7): on an incoming wire (_is_wire_row: labels only a credit prints) the beneficiary field's
    value goes too, as a receiver's does: a credit wire's beneficiary is the holder ('... ORIG NORTHWIND EXPORTS LLC
    ... BNF SQUARE ONE BAKERY'). Any other row keeps it: Chase's real-time layout prints the originator there ('FROM
    BNF INTUIT PAYMENTS INC'), and a debit's beneficiary is its payee."""
    stripped = _CREDIT_RECEIVER_VALUE.sub(" ", text)
    if _is_wire_row(text):
        stripped = _CREDIT_WIRE_BENEFICIARY_VALUE.sub(" ", stripped)
    return stripped


def _strip_revenue_template(row: str) -> str:
    """5.5 (§5.2): the row with the bank's template words before the payer removed."""
    for _ in range(3):
        stripped = _PAYEE_TEMPLATE_PREFIX.sub("", row, count=1).lstrip()
        stripped = _REVENUE_TEMPLATE_PREFIX.sub("", stripped, count=1).lstrip()
        if stripped == row:
            break
        row = stripped
    return row


def _leading_name_words(region: str) -> str:
    """The region's words up to the first reference token after a name word; leading reference tokens are kept, so a
    numbered company keeps its number (§5.2)."""
    words: list[str] = []
    started = False
    for token in region.split():
        if _is_reference_token(token):
            if started:
                break
        else:
            started = True
        words.append(token)
    return " ".join(words)


def _is_wire_row(text: str) -> bool:
    """5.5 (§7.9 N1, §8.5): the row begins with an incoming-wire label, or (T19) is a third-party book transfer."""
    return _INCOMING_WIRE_LABEL.match(text) is not None or _third_party_book_transfer(text)


#: S2.3 review (fix 2): WIRE printed anywhere on the row, a reference glued on its left included
#: ('123456W1234567WIRE FROM ...', which _INCOMING_WIRE_LABEL, anchored at the row's start, never reads).
_WIRE_WORD = re.compile(r"(?<![A-Z])WIRE\b")


def _wire_vetoes_apply(text: str) -> bool:
    """S2.3 review (fixes 2 and 3): the wire vetoes (_wire_vetoed) and the wire company-form gate read a wire row
    (_is_wire_row) and, failing closed, any row that prints WIRE, so a reference glued to WIRE never skips them. The
    verifier's own channel test (N1, _wire_remittance_purpose) keeps _is_wire_row. WIRE in the receiver's (the
    holder's) name makes no row a wire (§5.2; S2.3 re-review minor 1)."""
    return _is_wire_row(text) or _WIRE_WORD.search(_without_receiver_value(text)) is not None


def _is_transfer_or_p2p_row(text: str) -> bool:
    """5.5 (§8.4): a person-to-person rail, or transfer wording, on a row that is no wire."""
    row = _before_receiver(text)
    return _CONSUMER_P2P_RAIL.search(row) is not None or _PUSH_RAIL.search(row) is not None or (
        _TRANSFER_WORDING.search(row) is not None
    )


def _wire_payer_region(text: str) -> str:
    """5.5 (§5.2): a wire's originator, after its label, up to the next wire field; on Santander's layout, the words
    after the account number (the words after WIRE IN FROM are the sending bank)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return _leading_name_words(santander.group("originator").strip())
    found = _WIRE_ORIGINATOR_LABEL.search(text)
    if found is None:
        return _wire_sender_after_label(text)
    # 5.6 (A3-G review): a SWIFT 50F line number is dropped by the normalizer, where its slash still shows.
    rest = text[found.end():]
    end = _WIRE_FIELD_END.search(rest)
    region = _leading_name_words(rest[: end.start()] if end is not None else rest)
    after, city_state_end = originator_address(text, region)
    customer = relayed_customer_text(region, rest, after=after, city_state_end=city_state_end)
    return _leading_name_words(customer) if customer else region


#: 5.6 (A3-G): a wire originator that reads as a bank by its own form (BANK, BANCORP, BANK N A, CREDIT UNION, SAVINGS
#: BANK, FEDERAL SAVINGS), and a bank's merchant-services, bankcard, processor and settlement forms, which are
#: settlements, never a bank's own money nor a relay. The true-revenue pass holds a bank originator
#: (financing_named_payer). A3-G review: never a food or blood bank, and never a company whose name holds the word
#: (bank_by_form).
BANK_FORM_ORIGINATOR = re.compile(r"(?<![A-Z])(?:BANK|BANCORP|CREDIT UNION|FEDERAL SAVINGS)\b")
BANK_SETTLEMENT_ORIGINATOR = re.compile(
    r"(?<![A-Z])(?:MERCHANT\w*|MERCH SVCS|BANKCARD\w*|CARD (?:SERVICES|SVCS)|PAYMENTECH|PROCESSING|SETTLEMENT\w*)\b"
    r"|\b(?:MERCH|MRCH|BNKCD|BKCD|STLMT)\b"
)
_NOT_A_BANK = re.compile(r"(?<![A-Z])(?:FOOD|BLOOD) BANK\b")
#: A3-G review: a company form; a company whose name holds BANK is no bank ('LEFT BANK BAKERY LLC', 'BANK STREET
#: PARTNERS LLC'), unless the form is the bank's own, right after its bank word ('<X> BANK LTD', '<X> BANK CO LTD',
#: '<X> BANK PUBLIC CO LTD', 'BANK OF <place> LIMITED').
_BANK_COMPANY_FORM = re.compile(
    r"\b(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC|PARTNERS|PARTNERSHIP"
    r"|GMBH|AG|SA|BV|NV|PTY)\b"
)
_BANK_OWN_FORM_WORDS = frozenset({"CO", "PUBLIC", "N", "A", "NA", "AND", "TRUST"})
_BANK_OF_PLACE_WORDS = 4
#: 5.6 (A3-G re-review): the company-form words that are also US state codes (Colorado, Nevada). Printed as the
#: address's state they are never a company form: 'NORTHWIND BANK DENVER CO 80202 US'. A3-G re-review 2: the word is
#: the state only when a ZIP or the country code follows it (_AFTER_ADDRESS_STATE, read on the region and the row's
#: text after it), or when it ends a Fedwire or CHIPS B/O field's city and state (_CITY_STATE_WIRE_LAYOUT); never at
#: the end of any other field, so Bank of America's 'ORIG:LEFT BANK TRADING CO' and Chase's 'B O WEST BANK OIL CO REF'
#: print a company form.
_STATE_CODE_FORM_WORDS = frozenset({"CO", "NV"})
_AFTER_ADDRESS_STATE = re.compile(r"\s*(?:\d{5}\b|(?:US|USA|UNITED STATES)\b)")
#: 5.6 (A3-G re-review 2): the wire layouts whose B/O field prints the sender's city and state last.
_CITY_STATE_WIRE_LAYOUT = re.compile(r"^(?:FEDWIRE|CHIPS) CREDIT\b")


def company_form_outside_address(
    region: str, after: str = "", *, city_state_end: bool = False
) -> re.Match[str] | None:
    """5.6 (A3-G re-review, re-review 2): the first company form (_BANK_COMPANY_FORM) of the region that is not the
    address's state. CO or NV is the state when a ZIP or the country code follows it, in the region or in `after` (the
    row's text right after the region), or when it ends the region and `city_state_end` says the region is a Fedwire
    or CHIPS B/O field (originator_address)."""
    region = region or ""
    tail = region + after
    for form in _BANK_COMPANY_FORM.finditer(region):
        if form.group(0) in _STATE_CODE_FORM_WORDS and (
            _AFTER_ADDRESS_STATE.match(tail, form.end()) is not None
            or (city_state_end and not region[form.end():].strip())
        ):
            continue
        return form
    return None


def originator_address(text: str, region: str) -> tuple[str, bool]:
    """5.6 (A3-G re-review 2): the address context of a wire's originator region: the row's text right after the
    region, and whether the region is a Fedwire or CHIPS B/O field, which prints the sender's city and state last.
    ('', False) when no originator label starts the region (a sender printed after the wire's label, Santander's
    layout, or a relayed customer)."""
    found = _WIRE_ORIGINATOR_LABEL.search(text or "")
    if found is None or not region:
        return "", False
    rest = text[found.end():]
    if not rest.startswith(region):
        return "", False
    city_state = found.group(0).strip() == "B O" and _CITY_STATE_WIRE_LAYOUT.match(text) is not None
    return rest[len(region):], city_state


def bank_by_form(region: str, after: str = "", *, city_state_end: bool = False) -> bool:
    """5.6 (A3-G, A3-G review): the originator reads as a bank by its own form (BANK_FORM_ORIGINATOR), never a bank's
    settlement form (BANK_SETTLEMENT_ORIGINATOR), a food or blood bank, or a company whose name holds the bank word:
    a company form (_BANK_COMPANY_FORM) counts only as the bank's own, right after its bank word, after 'OF <place>'
    (_BANK_OF_PLACE_WORDS words) or the bank's own form words (_BANK_OWN_FORM_WORDS). Read on the originator up to a
    relay label, whose relayed customer is no part of the bank's name. A3-G re-review 2: `after` and `city_state_end`
    are the region's address context (originator_address), read for the address's state only."""
    relay = next((label for label in _RELAY_ORIGINATOR_LABEL.finditer(region or "") if label.start() > 0), None)
    if relay is not None:
        after = region[relay.start():] + after
    region = (region or "")[: relay.start()] if relay is not None else (region or "")
    found = BANK_FORM_ORIGINATOR.search(region)
    if found is None or BANK_SETTLEMENT_ORIGINATOR.search(region) or _NOT_A_BANK.search(region):
        return False
    form = company_form_outside_address(region, after, city_state_end=city_state_end)
    if form is None:
        return True
    if form.start() < found.start():
        return False
    between = region[found.end(): form.start()].split()
    if not between or all(word in _BANK_OWN_FORM_WORDS for word in between):
        return True
    return between[0] == "OF" and len(between) <= _BANK_OF_PLACE_WORDS


#: 5.6 (A3-G refinement): the labels after which a relaying (correspondent) bank prints the ultimate originator
#: ('B O <bank> ... ORG <account> <customer> OGB <bank>'), and the fields the customer's name ends at: a wire field,
#: the originating bank (OGB) and the relay's charge and amount fields. A3-G review: never the purpose's own label,
#: ORIGINATOR TO BENEFICIARY or ORG TO BNF (the guards _WIRE_ORIGINATOR_LABEL has).
_RELAY_ORIGINATOR_LABEL = re.compile(
    r"\b(?:ORG(?! TO BNF\b| TO BENEFICIARY\b)|B O|ORIGINATOR(?: NAME)?(?! TO BNF\b| TO BENEFICIARY\b)"
    r"|ORIG CUST(?:OMER)?|BY ORDER OF)\b ?"
)
_RELAY_CUSTOMER_END = re.compile(
    _WIRE_FIELD_END.pattern + r"|\b(?:OGB|ORIGINATING BANK|OCMT|CHGS|INS|BBK|INT BK|INTERMEDIARY)\b"
)


def relayed_customer_text(region: str, rest: str, *, after: str = "", city_state_end: bool = False) -> str:
    """5.6 (A3-G refinement, §8.5): when a wire's originator (`region`, read from `rest`, the text after the originator
    label) reads as a bank, and a relay label after it names the ultimate originator, that customer's text up to its
    end (_RELAY_CUSTOMER_END), after its account number and any SWIFT line number: the bank only relays, so the
    customer is the sender, read normally. '' when the originator is no bank by form (bank_by_form, read with the
    region's address context, A3-G re-review 2), or no relay label names a customer (a bank sending on its own
    behalf)."""
    if not region or not bank_by_form(region, after, city_state_end=city_state_end):
        return ""
    for label in _RELAY_ORIGINATOR_LABEL.finditer(rest):
        if label.start() == 0:
            continue
        after = rest[label.end():]
        end = _RELAY_CUSTOMER_END.search(after)
        tokens = (after[: end.start()] if end is not None else after).split()
        while tokens and _is_reference_token(tokens[0]) and _NUMBERED_PROVINCE_START.match(" ".join(tokens)) is None:
            tokens.pop(0)
        name = " ".join(tokens)
        if any(
            _is_payer_word(token) and not _is_reference_token(token) and token not in _WIRE_LABEL_WORDS
            for token in _leading_name_words(name).split()
        ):
            return name
    return ""


#: A3 (orchestrator ruling, 2026-09-30): the incoming-wire layouts that print the sender right after their label, with
#: no originator label: BMO's label printed twice, then the sender's country code ('INCOMING WIRE PAYMENT INCOMING
#: WIRE PAYMENT CA <sender>'); a reference, then the sender ('INCOMING WIRE <reference> <sender> NOTPROVIDED'); TD
#: Bank's 'WIRE TRANSFER INCOMING <sender>'; Wilson & Muir's 'WIRE TRANSFER FROM <sender>'; Capital One's 'WIRE
#: TRANSFER DEPOSIT <sender> <reference> USD<...>'; Scotiabank's 'INCOMING WIRE TRANSFER <sender> WIRE PAYMENT'; and
#: SECU's 'DOMESTIC WIRE DEPOSIT WIRE IN <sender>'. Anchored at the row's start, so a sending bank after VIA or a
#: reference-only row ('DOMESTIC INCOMING WIRE <reference>') is never read as a sender.
_WIRE_SENDER_AFTER_LABEL = re.compile(
    r"^(?:INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT [A-Z]{2}|INCOMING WIRE(?= \d+ [A-Z])"
    r"|WIRE TRANSFER (?:INCOMING|FROM|DEPOSIT)|INCOMING WIRE TRANSFER(?= .*\bWIRE PAYMENT$)"
    r"|(?:DOMESTIC )?WIRE DEPOSIT WIRE IN)\b ?"
)
#: A3: the sender printed after the label ends at a wire field, at NOTPROVIDED, or at Scotiabank's WIRE PAYMENT.
_WIRE_SENDER_AFTER_LABEL_END = re.compile(_WIRE_FIELD_END.pattern + r"|\b(?:NOTPROVIDED|WIRE PAYMENT)\b")
#: A3: the words of the label layouts, never a sender's name ('WIRE TRANSFER DEPOSIT WIRE REF ...'), and a legal form
#: or an article, which alone names nobody (as the person-to-person reader holds: 'WIRE TRANSFER INCOMING 1ABC LLC',
#: whose name the reference reading drops, stays a wire with no sender).
_WIRE_LABEL_WORDS = frozenset({
    "INCOMING", "WIRE", "PAYMENT", "TRANSFER", "DEPOSIT", "CREDIT", "IN", "FROM",
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "COMPANY", "CO", "LTD", "LIMITED", "LP", "LLP", "PLLC", "ULC",
    "PLC", "THE", "OF", "AND",
})


def _wire_sender_after_label(text: str) -> str:
    """A3 (orchestrator ruling): the sender a wire prints right after its label (_WIRE_SENDER_AFTER_LABEL), read as the
    originator is: up to the next wire field, NOTPROVIDED or WIRE PAYMENT, and to the first reference token after a
    name word (_leading_name_words). A reference printed before the sender is no part of it, except a numbered
    company's number before its province ('CA 1234567 ONTARIO INC', §5.2). '' when no payer word is left."""
    found = _WIRE_SENDER_AFTER_LABEL.match(text)
    if found is None:
        return ""
    rest = text[found.end():]
    end = _WIRE_SENDER_AFTER_LABEL_END.search(rest)
    tokens = (rest[: end.start()] if end is not None else rest).split()
    while tokens and tokens[0].isdigit() and _NUMBERED_PROVINCE_START.match(" ".join(tokens)) is None:
        tokens.pop(0)
    region = _leading_name_words(" ".join(tokens))
    named = any(
        _is_payer_word(token) and not _is_reference_token(token) and token not in _WIRE_LABEL_WORDS
        for token in region.split()
    )
    return region if named else ""


def _sender_payer_region(text: str) -> str:
    """5.5 (§5.2): a person-to-person or transfer sender: the words after FROM, up to ON, REF, CONF, MEMO, TRN, ID,
    FOR or a reference token. Venmo and Cash App cash-outs print no sender."""
    row = _before_receiver(text)
    found = re.search(r"\bFROM\b ?", row)
    if found is None:
        return ""
    rest = row[found.end():]
    end = _SENDER_END.search(rest)
    return _leading_name_words(rest[: end.start()] if end is not None else rest)


def _ach_payer_region(text: str) -> str:
    """5.5 (§5.2): an ACH or EFT payer: the row before its receiver fields, template prefixes removed, originator
    labels removed, cut at the first ACH field, up to the first reference token after a name word."""
    return _leading_name_words(_payee_region(_strip_revenue_template(_before_receiver(text))))


def _prints_no_payer(text: str) -> bool:
    """5.5 (§5.2, §6.1 step 9b): a check, cash, branch, ATM or bare row: a channel that prints no payer."""
    row = _before_receiver(text)
    if _CHECK_DEPOSIT_FORM.search(row):
        return True
    if (
        not _ELECTRONIC_PAYMENT_FORM.search(row)
        and not _CONSUMER_P2P_RAIL.search(row)
        and _CASH_BRANCH_ATM_FORM.search(row)
    ):
        return True
    return _is_bare_row(text)


def _is_bare_row(text: str) -> bool:
    """5.5 (§8.2): a bare deposit, credit or EFT: once the template prefixes, the generic words, the reference tokens
    and single letters are removed, no payer word remains, and the row prints no transfer wording."""
    row = _before_receiver(text)
    if _TRANSFER_WORDING.search(row):
        return False
    return not any(_is_payer_word(token) for token in _strip_revenue_template(row).split())


def _is_payer_word(token: str) -> bool:
    """5.5 (§8.2): a token that may name a payer: not a generic word, a single letter, a masked number or a month.
    A token that holds digits names one only through three or more letters glued to them ('2054BANKCARD' after a
    glued date with a year, 'MRCH22064280019')."""
    if token in REVENUE_GENERIC_WORDS or len(token) < 2 or _MASKED_TOKEN.fullmatch(token) or token in _ENTITY_MONTHS:
        return False
    if not any(ch.isdigit() for ch in token):
        return True
    letters = "".join(ch for ch in token if ch.isalpha())
    return len(letters) >= 3 and letters not in REVENUE_GENERIC_WORDS


def payer_region(text: str) -> str:
    """5.5 (§5.2): the payer region of a credit's revenue text, read by its channel: a wire's originator, a
    person-to-person or transfer sender, an ACH or EFT payer, or nothing on a check, cash, branch, ATM or bare row.
    Read before any token is filtered, so a numbered company's leading digits and a legal word are kept."""
    if _is_wire_row(text):
        return _wire_payer_region(text)
    if _is_transfer_or_p2p_row(text):
        sender = _sender_payer_region(text)
        row = _before_receiver(text)
        # A transfer-worded row that prints an ACH originator field and no FROM sender names its payer the ACH way
        # ('CONTOSO BAKERY LLC DES:TRANSFER'), so the holder test and the counter-debit hold read it.
        if (
            not sender
            and _ACH_ORIGINATOR_FIELD.search(row)
            and not _CONSUMER_P2P_RAIL.search(row)
            and not _PUSH_RAIL.search(row)
        ):
            return _ach_payer_region(text)
        return sender
    if _prints_no_payer(text):
        return ""
    return _ach_payer_region(text)


def payer_name(region: str) -> str:
    """5.5 (§5.2): the payer region's words without the tokens that hold a digit and the single letters."""
    return " ".join(
        token for token in region.split() if not any(ch.isdigit() for ch in token) and len(token) > 1
    )


def entry_fields(text: str) -> str:
    """5.5 (§5.2): the words the payer prints about the payment: Bank of America's DES field, Chase's CO ENTRY DESCR
    field, a wire's OBI, RMR, PMT DET, RFB and REF text, a transfer's memo. Empty when the layout has none (its entry
    words sit inside the payer region, which the holds read too)."""
    row = _before_receiver(text)
    fields = []
    for pattern in (_BOFA_ENTRY_FIELD, _CHASE_ENTRY_FIELD):
        found = pattern.search(row)
        if found is not None:
            fields.append(found.group(1).strip())
    if _is_wire_row(text):
        fields.extend(found.group(1).strip() for found in _WIRE_ENTRY_FIELD.finditer(text))
    elif _is_transfer_or_p2p_row(text):
        fields.extend(found.group(1).strip() for found in _MEMO_ENTRY_FIELD.finditer(row))
    return " ".join(field for field in fields if field)


def _distinctive_words(words: Sequence[str]) -> list[str]:
    """5.5 (§5.2): the words that may name a holder or a payer: no noise word, no digit, three letters or more."""
    return [
        word for word in words
        if word not in HOLDER_NOISE and not any(ch.isdigit() for ch in word) and len(word) > 2
    ]


def _first_distinctive_word(words: Sequence[str]) -> str | None:
    """5.5 (§5.2): the first word of four or more letters that is not a common name-starter."""
    return next((word for word in words if len(word) >= 4 and word not in _NAME_STARTERS), None)


@cache
def account_name_text(account_name: str | None) -> str:
    """5.5: the statement's account name, normalized once per name ('' when none is printed), so the holder test
    never re-normalizes it row by row."""
    return normalize_transaction_description(account_name) if account_name else ""


def holder_words(account_name: str | None) -> tuple[str, ...]:
    """5.5 (§5.2): the statement's account name, normalized, without holder noise, digit tokens and short tokens.
    Often empty: account_name is frequently only a product name."""
    return tuple(_distinctive_words(account_name_text(account_name).split()))


def holder_named(region: str, account_name: str | None) -> bool:
    """5.5 (§5.2): the holder test, read on a payer region (never on a check, cash, branch, ATM or bare row, which has
    none). It matches when the payer's first distinctive word is the holder's, when the payer name holds
    min(2, number of holder words) holder words, or when the region prints a run of four or more digits that the
    account name also prints."""
    if not region or not account_name:
        return False
    holder = holder_words(account_name)
    payer = _distinctive_words(payer_name(region).split())
    if holder:
        holder_first = _first_distinctive_word(holder)
        if holder_first is not None and _first_distinctive_word(payer) == holder_first:
            return True
        shared = sum(1 for word in dict.fromkeys(payer) if word in holder)
        if shared >= min(2, len(holder)):
            return True
    printed = account_name_text(account_name)
    if _holder_cut_name(payer_name(region), printed):
        return True
    return any(
        re.search(rf"(?<!\d){run}(?!\d)", printed) for run in re.findall(r"\d{4,}", region)
    )


#: 5.6 (A3-G): a cut holder name names the holder when it keeps this many whole words before the cut, or this many
#: letters in all.
_HOLDER_CUT_WHOLE_WORDS = 2
_HOLDER_CUT_LETTERS = 12


def _holder_cut_name(payer: str, holder: str) -> bool:
    """5.6 (A3-G, §5.2): the payer name is the holder's normalized name cut short: a word-by-word prefix of it whose
    last word is a proper prefix of the holder's word there ('GLOBAL AMERICAN NORTHW' against 'GLOBAL AMERICAN
    NORTHWIND...'), with _HOLDER_CUT_WHOLE_WORDS whole words before the cut or _HOLDER_CUT_LETTERS letters in all, so
    a single common word never matches."""
    sender = payer.split()
    words = holder.split()
    if not sender or len(sender) > len(words):
        return False
    whole, cut = sender[:-1], sender[-1]
    if whole != words[: len(whole)]:
        return False
    target = words[len(whole)]
    if cut == target or not target.startswith(cut):
        return False
    return len(whole) >= _HOLDER_CUT_WHOLE_WORDS or sum(len(word) for word in sender) >= _HOLDER_CUT_LETTERS


#: S4.2 review (I1): a date the bank prints at the row's start, before a numbered company's number or a numbered
#: template: 'MM DD ', 'MMDD ', or 'MM ' before a day glued to the number ('03/021234567 ONTARIO INC' normalizes to
#: '03 021234567 ONTARIO INC', whose glued run is itself six or more digits). Only the numbered-company guard reads
#: past it, failing closed (more rows are numbered); revenue_text keeps a spaced pair, so Fifth Third's '5 3 ...' is
#: otherwise untouched.
_NUMBERED_LEADING_DATE = re.compile(
    r"^(?:\d{1,2} \d{1,2} |\d{4} |\d{1,2} )"
    # S4.2 re-review (fix 3): the lookahead takes every template of _NUMBERED_COMPANY_TEMPLATE, PMT included.
    r"(?=\d{6,}\b|\d{4} \d{4} [A-Z]|(?:DIRECT DEPOSIT|ACC(?:OUN)?TS? PAYABLE(?: PMT)?|MISC PAYMENT|BILL PAYMENT)"
    r" \d{6,}\b)"
)


def _skip_numbered_leading_date(text: str) -> str:
    """S4.2 review (I1): the text without a leading date printed before a numbered company's number."""
    return _NUMBERED_LEADING_DATE.sub("", text, count=1)


def numbered_company(text: str, region: str | None = None) -> bool:
    """5.5 (§5.2, T11): the payer is a Canadian numbered company: a template prefix followed by six or more digits,
    or a payer region that begins with six or more digits and then a province, territory, CANADA or a cut of one, or
    up to four words and a legal form, or with Quebec's form: four digits, a hyphen and four digits, then QUEBEC, a
    cut of it or QC (S4.2 round 4; fix round 5: Quebec's words only, '1234-5678 QUEBEC INC'). Both read past a leading
    date (S4.2 review, I1)."""
    if _NUMBERED_COMPANY_TEMPLATE.search(_skip_numbered_leading_date(_before_receiver(text))):
        return True
    region = payer_region(text) if region is None else region
    return _NUMBERED_COMPANY_REGION.search(_skip_numbered_leading_date(region)) is not None


def company_form(name: str) -> bool:
    """5.5 (§5.2): a legal-form word after the payer name's first word, or an institution word."""
    return _COMPANY_FORM.search(name) is not None


def is_round_sum(amount: float) -> bool:
    """5.6 (§5.2): at least $100 and a whole multiple of $100, compared in integer cents."""
    cents = round(abs(amount) * 100)
    return cents >= _ROUND_SUM_DOLLARS * 100 and cents % (_ROUND_SUM_DOLLARS * 100) == 0


#: §8.10: the round sum's step, in whole dollars.
_ROUND_SUM_DOLLARS = 100


def channel_gate(text: str) -> str | None:
    """5.5 (§6.1 step 9b), read on a credit's revenue text: 'closed' when a consumer person-to-person rail, a
    check-deposit form, a cash, branch or ATM form, or no payer word at all is printed (no step verifies it);
    'push' for a real-time or push rail (only the operating registry may verify it); None otherwise."""
    row = _before_receiver(text)
    if _CONSUMER_P2P_RAIL.search(row):
        return "closed"
    if _prints_no_payer(text) and not _is_wire_row(text):
        return "closed"
    if _PUSH_RAIL.search(row):
        return "push"
    return None

#: §7.9 N1 and §7.11 (T19): the labels a reader needs to tell an incoming wire, and the originator a book or
#: funds transfer prints after B O, CUSTOMER, ORIGINATOR, ORG, TT, FROM or WIRE FROM.
_THIRD_PARTY_ORIGINATOR = re.compile(r"\b(?:B O|CUSTOMER|ORIGINATOR|ORG|TT|FROM|WIRE FROM)\b ?")
#: §7.9 N1 and §7.11: the incoming-wire labels a row begins with.
_INCOMING_WIRE_LABEL = re.compile(
    r"^(?:WIRE TYPE (?:WIRE|INTL|FX) IN\b|USD WIRE IN\b|[A-Z]{3} WIRE IN\b|FEDWIRE CREDIT\b|CHIPS CREDIT\b|WT FED"
    r"|WIRE TSF\b|WIRE TRANSFER (?:DEPOSIT|CREDIT|IN|INCOMING|FROM)\b|INCOMING WIRE\b|WIRE IN\b|WIRE FROM\b"
    r"|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN) (?:INCOMING )?WIRE\b|INCOMING FUNDS TRANSFER\b"
    r"|FUNDS TRANSFER CREDIT TT\b|INBD FUNDS TRANSFER\b|FUNDS TRANSFER WIRE FROM\b)"
)
_BOOK_TRANSFER_FROM = re.compile(r"^(?:BOOK TRANSFER CREDIT B O|WIRE TYPE BOOK IN\b.*\bORIG)\b ?")
#: §7.11: the funds-transfer labels of an incoming wire (the label stands for FROM).
_FUNDS_TRANSFER_WIRE_LABEL = re.compile(
    r"\b(?:INCOMING FUNDS TRANSFER|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER(?: RECEIVED)?|FUNDS TRANSFER WIRE FROM)"
    r"\b ?"
)


def _third_party_originator(text: str) -> str | None:
    """5.5 (§7.11): the originator a book or funds transfer prints (after B O, CUSTOMER, ORIGINATOR, ORG, TT, FROM or
    WIRE FROM, or one of the four funds-transfer wire labels), when it prints a distinctive payer word; otherwise
    None. S2.3 review (fix 1): an account description is no payer ('FROM BUSINESS SAVINGS', 'FROM LINE OF CREDIT',
    'FROM TAX RESERVE'): _originator_payer_words."""
    labels: tuple[re.Pattern[str], ...] = (_FUNDS_TRANSFER_WIRE_LABEL, _THIRD_PARTY_ORIGINATOR)
    if _BOFA_BOOK_IN.match(text):
        # 5.6 (A3-G refinement): Bank of America's WIRE TYPE BOOK IN is its WIRE TYPE WIRE IN layout: the originator
        # follows ORIG (the normalizer drops a SWIFT 50F line number printed with its slash).
        labels = (*labels, _BOFA_BOOK_IN_ORIGINATOR)
    for label in labels:
        for found in label.finditer(text):
            rest = text[found.end():]
            end = _WIRE_FIELD_END.search(rest)
            words = _leading_name_words(rest[: end.start()] if end is not None else rest)
            if _originator_payer_words(words):
                return words
    return None


#: 5.6 (A3-G refinement): Bank of America's book-transfer wire and its originator label (never ORIG CO NAME, ORIG ID or
#: ORIG TO BNF).
_BOFA_BOOK_IN = re.compile(r"^WIRE TYPE BOOK IN\b")
_BOFA_BOOK_IN_ORIGINATOR = re.compile(r"\bORIG\b(?! CO NAME\b)(?! ID\b)(?! TO BNF\b) ?")


#: S2.3 review (fix 1, §7.11): the account-type and product words a transfer prints after FROM about one of the
#: holder's own accounts. _INTERNAL_ACCOUNT_SOURCE's words and HOLDER_NOISE (BUSINESS, CHECKING, SAVINGS, ACCOUNT,
#: OPERATING, MONEY MARKET, TRUST, the generic words) are read too, so neither is repeated here.
_OWN_ACCOUNT_PRODUCT_WORDS = frozenset({
    "SAVS", "SVG", "SVGS", "CHKG", "CHKING", "MMDA", "OPER", "RESERVE", "RESERVES", "TAX", "TAXES", "PAYROLL",
    "PERSONAL", "BUS", "BUSN", "ACCTS", "LOC", "LINE", "HELOC", "SWEEP", "ESCROW", "INVESTMENT", "INVESTMENTS",
    "BROKERAGE", "IRA", "SUB",
    # S2.3 re-review (minor 2): the adjectives an own account prints before its product word, and a loan account.
    "PRIMARY", "SECONDARY", "MAIN", "JOINT", "HIGH", "YIELD", "SPENDING", "SHARE", "DRAFT", "LOAN",
})
_INTERNAL_ACCOUNT_SOURCE_WORDS = re.compile(rf"\b{_INTERNAL_ACCOUNT_SOURCE}\b")


def _originator_payer_words(words: str) -> list[str]:
    """S2.3 review (fix 1): the words of a transfer's originator that may name a payer: no reference token, no
    _INTERNAL_ACCOUNT_SOURCE account word, no HOLDER_NOISE or generic word (_distinctive_words) and no account-type or
    product word. An originator that prints none describes one of the holder's own accounts."""
    return [
        word for word in _distinctive_words(_INTERNAL_ACCOUNT_SOURCE_WORDS.sub(" ", words).split())
        if word not in _OWN_ACCOUNT_PRODUCT_WORDS and not _is_reference_token(word)
    ]


def _third_party_book_transfer(text: str) -> bool:
    """5.5 (T19): a Chase BOOK TRANSFER CREDIT B/O <originator> or a Bank of America WIRE TYPE BOOK IN that prints an
    originator. Read as an incoming wire only on the owner's yes (THIRD_PARTY_BOOK_TRANSFER_AS_WIRE)."""
    return (
        THIRD_PARTY_BOOK_TRANSFER_AS_WIRE
        and _BOOK_TRANSFER_FROM.match(text) is not None
        and _third_party_originator(text) is not None
    )


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
#: §7.11: a claim or provider signal. REIMBURSEMENT on such a row is a provider's claim payment, not a refund.
_CLAIM_OR_PROVIDER_SIGNAL = re.compile(
    r"\b(?:MEDICAID|MEDICARE|MEDI CAL|TRICARE|CHAMPVA|GEMT|EMS|PROV(?:IDER)? ?PAY(?:MENTS?)?|EDI PYMNTS|CLAIM PMT)\b"
    r"|(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"
)
_REIMBURSEMENT_WORD = re.compile(r"\bREIMBURSEMENT\b")
#: §7.11: push payouts printed as card credits: a push-rail word, or a processor or invoice source with a payout word.
_CARD_CREDIT_LABEL = re.compile(r"\b(?:DEBIT CARD CREDIT|POS CREDIT)\b")
_CARD_CREDIT_PUSH_WORD = re.compile(
    r"\b(?:VISA DIRECT|MC SEND|VISA MONEY TRANSFER|FASTPAY|INSTANT PAY|INSTANT PAYOUT)\b"
)
_CARD_CREDIT_PAYOUT_WORD = re.compile(r"\b(?:PAYOUTS?|INSTANT (?:PAYOUT|PAY|TRANSFER)|SETTLEMENT|DEPOSIT)\b")
#: §7.11 (T5): account verification, Square Capital's SQ CAP, SBA and EIDL disbursements (the tax-refund forms sit
#: in _NON_REVENUE_CREDIT_PATTERNS).
_ACCOUNT_VERIFICATION_CREDIT = re.compile(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b")
_SQUARE_CAPITAL_CREDIT = re.compile(r"\bSQ ?CAP\d*\b")
_SQUARE_NAME = re.compile(r"\bSQ\b|\bSQUARE\b")
_SBA_DISBURSEMENT_CREDIT = re.compile(r"\bSBAD TREAS\b|\bSBA (?:EIDL|LOAN|DISB\w*)\b|\bEIDL\b")
#: A3 (the precision sample of the largest counted rows, 2026-09-30): the Small Business Administration's name cut to
#: an originator field, read on the payer region alone: exactly SMALL BUSINESS, or SMALL BUSINESS and a leading cut of
#: ADMINISTRATION (A, AD, ADM ... ADMIN ... ADMINISTRATION), a U S prefix allowed. A payer whose name goes on in other
#: words (SMALL BUSINESS SOLUTIONS LLC) is a named payer.
_SBA_CUT_ORIGINATOR = re.compile(
    r"^(?:U ?S )?SMALL BUSINESS(?: (?:"
    + "|".join("ADMINISTRATION"[:length] for length in range(len("ADMINISTRATION"), 0, -1))
    + r"))?$"
)
#: §7.11 (T19 and this spec): a book or funds transfer is own-account only when no third-party originator is printed.
_BOOK_OR_FUNDS_TRANSFER = re.compile(r"\b(?:BOOK|FUNDS?) TRANSFER\b")
#: §7.11: the Electronic Funds Transfer channel, never a book or funds transfer between accounts.
_EFT_FUNDS_TRANSFER = re.compile(r"\bELECTRONIC FUNDS TRANSFER DEPOSIT\b")

#: S2.2 review (item A): in the 5.5 veto patterns below (the recurrence, card, operating, employer, transport, auction,
#: property, payer-remittance, public-payer and wire vetoes) a veto spelling of four letters or more (all its words
#: counted) takes a (?<![A-Z]) left boundary, the owner's card-form convention, so digits glued on its left
#: ('0102CHBK', '1234PAYROLL') never hide it; a spelling of three letters or fewer keeps \b, since a digit glued to
#: it is usually an ID's suffix ('ID 1234CB'). Each spelling counts on its own: FEES reads through a glued digit, FEE
#: does not. Measured exceptions (the cached corpus, S2.2 review): the card veto's BOOK and its DUP spellings keep \b,
#: since a digit glued to them there was a company name or an ID fragment, never the word. \b stays on the right of
#: every word.
#: §7.0: the recurrence pass's veto: pay, financing and verification words and the card-credit labels, read on the
#: row before its receiver fields.
_RECURRENCE_VETO = re.compile(
    r"(?<![A-Z])(?:LOANS?|CAPITAL|CAPI|CAPIT|CAPITA|CAPSEC|ADVANCE|FINANC\w*|LEND\w*|CASH ADV\w*"
    r"|PAYROLL\w*|PAYRLL|PAYROL|PAYRL|DIR ?DEP|DIRDEP|DIRECT DEP|SALARY|SALARIES|REG SAL|WAGES?|NET ?PAY|BONUS"
    r"|REIMB\w*|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY|VERIFICATION|INSUR\w*|DEBIT CARD CREDIT|POS CREDIT)\b"
    r"|\b(?:CAP\d*(?:SEC)?|FIN|ADV|MCA)\b"
)
#: §7.0 (review C2): FUNDING vetoes recurrence too, except on the settlements of the platforms that print it there.
_FUNDING_WORD = re.compile(r"(?<![A-Z])(?:FUNDING|FUNDED)\b")
_FUNDING_SETTLEMENT_ENTITIES = frozenset({"TapGoods Payments", "Braintree", "Buildium"})
#: §7.0, §5.2 (S2.4 review): the operating sources whose payout rows print the merchant's store name, which is the
#: holder's, in the entry field: the food-delivery and ordering platforms of the registry ('DOORDASH INC DES:<store>
#: CAPITA ... INDN:<store> CAPITAL GROUP'; BMO's 'DIRECT DEPOSIT DOORDASH <store> MSP/DIV'). Only on their rows does
#: the recurrence veto spare a veto word that is one of the holder's own words. On every other source (Square, Stripe,
#: PayPal, Shopify, the marketplaces and processors) the entry field is the platform's own wording, and a holder
#: named like a veto word ('CAPITAL CITY BAKERY LLC', 'SAMPLE LENDING LLC') would otherwise let that source's
#: financing credits verify ('SQUARE INC DES:CAPITAL'), so a veto word always vetoes there. The registry's Uber
#: (driver payouts) and Instacart (shopper payouts) pay no store and stay out.
_STORE_NAME_PAYOUT_ENTITIES = frozenset({
    "DoorDash", "Uber Eats", "Grubhub", "SkipTheDishes", "ezCater", "Menufy", "Snackpass",
})
#: §7.0, §7.8, §7.10: the absolute micro-deposit floor, in whole dollars.
_MICRO_DEPOSIT_FLOOR = 1
#: §7.0: a legal-form holder name is a business account for the recurrence rule.
_LEGAL_FORM_HOLDER = re.compile(r"\b(?:LLC|INC|CORP|LTD|LLP|PLLC)\b")
#: §7.0: the operating-source methods whose rows may join the recurrence pool.
_OPERATING_POOL_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "operating_source_payout_form",
})
#: §7.8, §7.10: the operating methods an auction or property branch may touch.
_OPERATING_SOURCE_METHODS = frozenset({
    "operating_source_requires_context", "recurring_operating_source", "operating_source_related_activity",
    "operating_source_with_credit_context",
})

#: §7.1: the card veto: neither a card form nor the processor payout context fires on a row that prints it.
_CARD_VETO = re.compile(
    r"(?<![A-Z])(?:CHBK|CHGBK|CHARGEBACKS?|DISPUTE\w*|ADJUSTMENT|BILLING|DISC|DISCOUNT|MTHLY|INTERCHANGE|PAYROLL"
    r"|LOANS?|CAPITAL|ADVANCE|FUNDING|FINANCING|FINANCE|RETURN(?:ED|S)?|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY"
    r"|VERIFICATION|INSUR\w*|ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC|REWARDS?|REBATES?|CASH ?BACK|INTEREST|CLAIMS?"
    r"|CAPI|CAPIT|CAPITA|CAPSEC|FUNDS?|FUNDED|FNDG|FNDNG|FINANCIAL|FINCL|LEND\w*|PROCEEDS|DISB\w*"
    r"|PURCH\w*|CONTRIB\w*|OWNERS?|MEMBER|SHAREHOLDER|RVSL|RVRSL|INTCHG|CORR\w*|FEES|ADV(?:NC?|C)"
    r"|OVERPAY\w*|XFER|SWEEP)\b"
    r"|\b(?:ADJ|FEE|TAX|ADV|CAP\d*(?:SEC)?|MCA|RTN|RET|REV\d*|CB|DUP\w*|TFR|ZBA|BOOK)\b"
    r"|(?<![A-Z])(?:TRANSFER|XFER|TFR) (?:FROM|TO)\b|(?<![A-Z])ONLINE TRANSFER\b"
)
#: §7.1: processor payout context, for merchant_processor and invoice_and_receivables sources only (context, never
#: proof on its own).
_PROCESSOR_PAYOUT_CONTEXT = re.compile(
    r"\bSQ ?\d{6}\b|\bMISC PAYMENTS?\b|\bMSP(?: DIV)?\b|\bDAILY DEP\b|\bST [A-Z0-9]{6,}\b"
    r"|\b(?:RTP|FEDNOW|REAL TIME (?:TRANSFER|PAYMENT)|INSTANT (?:PMT|PAYMENT|TRANSFER)|VISA DIRECT|MC SEND"
    r"|PMNT RCVD|PAYMENT RECEIVED)\b"
)
_PROCESSOR_CONTEXT_TYPES = frozenset({"merchant_processor", "invoice_and_receivables"})
#: §7.2: the vetoes on every new operating read (a payout form, and an alias added in 5.5).
_OPERATING_PAY_VETO = re.compile(
    r"(?<![A-Z])(?:PAYROLL\w*|PAYRLL|PAYROL|PAYRL|SALARY|SALARIES|REG SAL|WAGES?|DIR ?DEP|DIRDEP|DIRECT DEP|NET ?PAY"
    r"|BONUS|REIMB\w*)\b"
)
_OPERATING_FINANCING_VETO = re.compile(
    r"(?<![A-Z])(?:LOANS?|ADVANCE[SD]?|CAPITAL|LENDING|LENDER|FINANC\w*|FUNDING|FUNDED|PROCEEDS|DRAW)\b|\bADV\b"
)
_OPERATING_REVERSAL_VETO = re.compile(
    r"(?<![A-Z])(?:RETURN(?:ED|S)?|REFUND(?:ED|S)?|RFND|REFND|REVERS(?:AL|ED|E)|VOID(?:ED)?"
    r"|CANCEL(?:LED|ED|LATION)?|CNCL|ADJUSTMENT|ADJUSTED|DISPUTE[DS]?|CHARGEBACK|CREDIT MEMO|REJECT(?:ED)?)\b"
    r"|\b(?:RTN|RFD|ADJ|NSF)\b"
)
_OPERATING_P2P_VETO = re.compile(r"(?<![A-Z])(?:ZELLE|VENMO|CASH APP|E ?TRANSFER|ETRANSFER|INTERAC)\b")


def _with_served_cuts(aliases: frozenset[str]) -> frozenset[str]:
    """5.5 (§7.0, S1.1 review): a sixteen-character cut reads as its alias, so a set of operating aliases that carries
    a rule of §7.2 carries each alias's served cut (OPERATING_REVENUE_TRUNCATIONS) too. Derived once, at import."""
    return aliases | frozenset(
        cut
        for entity, source_aliases in OPERATING_REVENUE_SOURCE_ALIASES.items()
        for alias in source_aliases
        if alias in aliases and (cut := _operating_alias_cut(alias)) in OPERATING_REVENUE_TRUNCATIONS.get(entity, ())
    )


#: §7.2: the aliases of older entities whose reads carry the vetoes above, with their cuts ('RTP CREDIT AMAZO').
_OPERATING_ALIASES_VETOED = _with_served_cuts(OPERATING_ALIASES_READ_WITH_VETOES)
#: §7.2: an employer-type alias (TikTok, Amazon's RTP alias) also refuses these pay words, and the TikTok aliases count
#: only on an ACH-shaped row. Each set holds its aliases' cuts too (§7.0).
_EMPLOYER_PAY_WORDS = re.compile(r"(?<![A-Z])(?:DIR DEP|DIRECT DEP|PAYRL|REIMB|EXP REIMB)\b")
_EMPLOYER_TYPE_ALIASES = _with_served_cuts(
    frozenset({"TIKTOK INC", "TIKTOK USA", "TIKTOK SHOP", "RTP CREDIT AMAZON COM"})
)
_TIKTOK_ALIASES = _with_served_cuts(frozenset({"TIKTOK INC", "TIKTOK USA", "TIKTOK SHOP"}))
_ACH_SHAPED_ROW = re.compile(r"\b(?:ACH|CCD|PPD|ORIG CO NAME|DEPOSIT|PAYMENT|PAYOUT|CORP|CORPORATE)\b")
#: §7.3: a transport marketplace's credit never counts toward recurrence with a wallet, subscription or wire word.
_TRANSPORT_EXTRA_VETO = re.compile(
    r"(?<![A-Z])(?:CASHOUT|CASH OUT|SUBSCRIPTION|MEMBERSHIP|WIRE|FEDWIRE)\b|\b(?:WT|OBI|BNF)\b"
)
#: §7.8: an ACV credit printing a buyer-payment reference stays unverified.
_AUCTION_BUYER_PAYMENT = re.compile(r"(?<![A-Z])PYMT\d")
#: §7.8, §14.1: an auction credit printing a floor-plan or financing word (NextGear's NGC, AFC's FUNDNG) or a
#: consumer entry (PPD) is never the auction's payout, whatever form it prints.
_AUCTION_VETO = re.compile(
    r"(?<![A-Z])(?:FUNDING|FUNDNG|FUNDED|ADVANCES?|CAPTL|CAPITAL|FLOOR ?PLAN|FLOORPLAN|FINANC\w*|LOANS?)\b"
    r"|\b(?:ADV|NGC|PPD)\b"
)
#: §7.8: the auction refund pair's window, in days.
_AUCTION_REFUND_WINDOW_DAYS = 14
#: §7.10: owner, distribution and deposit wording on a property-management platform's row, and micro-deposits. The
#: last branch is a row shape (two originator labels), not a veto word.
_PROPERTY_PLATFORM_GUARD = re.compile(
    r"(?<![A-Z])OWNERS? ?(?:DIST\w*|DISB\w*|DRAWS?\w*|CONT\w*)|(?<![A-Z])DISTRIBUT\w*|(?<![A-Z])SEC(?:URITY)? ?DEP\w*"
    r"|(?<![A-Z])DEP(?:OSIT)? ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)|(?<![A-Z])SD ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)"
    r"|(?<![A-Z])ADVANCE\w*|\bORIG CO NAME\b.*\bORIG CO NAME\b"
)
_PROPERTY_MICRO_DEPOSIT = re.compile(
    r"(?<![A-Z])ACCT ?VERIFY\w*|(?<![A-Z])MICRO ?(?:DEP\w*|ENTRY)\b|(?<![A-Z])PENNY TEST\b"
    r"|(?<![A-Z])TRIAL (?:DEP\w*|CREDIT)\b"
)
_PROPERTY_PUSH_SHAPE = re.compile(r"(?<![A-Z])(?:VISA DIRECT|PMNT RCVD|PAYMENT RECEIVED)\b|\bRTP\b")
#: §7.1: an unregistered NET SETTLE originator needs this many NET SETTLE credits in the statement.
_NET_SETTLE_MIN_CREDITS = 3
#: §7.0: the operating recurrence rule.
_RECURRENCE_MIN_CREDITS = 3
_RECURRENCE_MIN_BUSINESS_CREDITS = 2

#: §7.7: the NACHA claim-payment entry. The unbounded branch takes only the full token (never THECLAIMPMT).
_HCCLAIMPMT = re.compile(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b")
#: §7.7: inside the credit decision, the financing, potential-lender and insurer lookups read a glued HCCLAIMPMT
#: split from the name before it, so a sixteen-character funder name glued to the token is still found.
_GLUED_CLAIM_ENTRY = re.compile(r"(?<=[A-Z0-9])(H[CE]?CLAIMPMT)")
#: §8.1 (T14): an insurer's customer-payment wording (a DRP payment, a vendor payment, a commission).
_INSURER_CUSTOMER_PAYMENT = re.compile(
    r"\b(?:DRP|VENDOR ?(?:PMT|PAY|PAYMENT)|COMM?ISS?IONS?|AGT ?COMM|AGENT COMP|AGTEFT|REPAIR)\b"
)
_BLUE_PLAN_CLAIM_PAYER = re.compile("|".join(BLUE_PLAN_CLAIM_PAYERS))

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
#: §7.5: the free-text forms (invoice, bill and 'for invoices') count on a PAYPAL row or a wire from a person only
#: when the sender prints a company form.
_FREE_TEXT_REMITTANCE = re.compile(
    r"\bPAYING BILLS?\b|\bFOR \d+ BILLS\b|\b(?:OF|FOR) INVOI ?CES?\b|\bINV(?:OICE)?S?(?: (?:NO|NUM|NUMBER|N))? ?\d"
)
#: §7.5: the credit posting labels removed before the veto reads the row.
_CREDIT_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE)\s+CREDIT\b|^CREDIT\b"
)
#: §7.5: the veto of the payer remittance rule.
_PAYER_REMITTANCE_VETO = re.compile(
    r"(?:FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|PORTFOL|CREDIT)"
    r"|CRED(?=ORA|IBLY|\b)|CAPI?\b|LEAS(?:E|ES|ING|IN|I)?\b"
    r"|(?<![A-Z])(?:FINA|FINAN|FINL|FNCL|FUNDI)\b|\b(?:CAP|FIN|FI|ADV|MTG|MCA|RTR|SPV|FUN|LOA)\b"
    r"|(?<![A-Z])(?:INSUR\w*|ASSURANCE|INVEST\w*|BROKERAGE|SECURITIES|WEALT\w*|TAXES|GRANTS?|REBATES?|DIVIDENDS?)\b"
    r"|\b(?:INS|TAX|IRS|CRA)\b"
    r"|(?<![A-Z])(?:PAYROLL|SALARY|WAGES?|REIMB\w*|EXPENSES?|BONUS|COMM?ISS?IONS?|CLAIMS?|MUTUAL|INDEMNITY|CASUALTY"
    r"|UNDERWRIT\w*)\b"
    r"|(?<![A-Z])(?:EQUIP\w*|FLOOR\w*|MERCH\w*)\b|\bVIN\b"
    r"|\bSBA\b|(?<![A-Z])(?:SBAD|EIDL)\b"
    r"|(?<![A-Z])(?:INTERCO(?:MPANY)?|DUE FROM|SHAREHOLDER|OWNERS?|SWEEP|INTERNAL)\b|(?<![A-Z])ZERO BAL\w*|\bZBA\b"
    r"|(?<![A-Z])CONTROLLED DISB\w*|(?<![A-Z])(?:TRANSFER|XFER|TFR) FROM\b"
    r"|\bRTN\b|(?<![A-Z])RETURN(?:ED)? ITEM\b|(?<![A-Z])RECALL\w*|(?<![A-Z])UNPAID\b|\bADJ\b"
    r"|ACIMA"
)
#: §7.5, §8.1: words that never make a payer's or a debit's first distinctive word: the AP words, the public-payer
#: words, the holder noise (legal suffixes, generic words) and the bank's template and channel words (D11's channel
#: words, D6's channel vocabulary and bank template words, read at call time: _counter_debit_skip_words).
_COUNTER_DEBIT_SKIP_WORDS = frozenset({
    "PAYABLE", "PAYABLES", "ACCOUNTS", "ACCTS", "VENDOR", "TRADE", "REMIT", "REMITTANCE", "STATE", "COUNTY", "CITY",
    "TOWN", "DEPT", "DEPARTMENT", "TREAS", "GOVERNMENT",
    "CHECKCARD", "OVERDRAFT", "TRANF", "CHECKG", "TRANSFERS", "WITHDRAW", "OUTGOING", "PURCHASES",
}) | HOLDER_NOISE


@cache
def _counter_debit_skip_words() -> frozenset[str]:
    return _COUNTER_DEBIT_SKIP_WORDS | frozenset(_ENTITY_NOISE) | _CHANNEL_VOCABULARY | _BANK_TEMPLATE_WORDS


#: §7.6: the public-payer remittance rule. Arm A reads the whole row.
_PUBLIC_PAYER_ARM_A = (
    re.compile(r"^(?!.*\bPPD\b).*\bTREAS \d{3}(?: DES)? DOD MISC\b"),
    re.compile(r"\bTREAS \d{3}\b.*\bMISC PAY(?:SEC)?\b.*\bRMR IV\b"),
)
#: §7.6 arm B: a public payer anchored on the payer name.
_PUBLIC_PAYER_NAME = re.compile(
    r"^((?:\S+ ){0,3})(?:TREAS \d{3}"
    r"|(?:STATE|COUNTY|CITY|TOWN|VILLAGE|TOWNSHIP|BOROUGH|PARISH|DISTRICT|PROVINCE|COMMONWEALTH|GOVERNMENT|GOVT"
    r"|MUNICIPALITY) OF [A-Z]"
    r"|(?<!\bFROM )(?<!\bTO )(?<!\bTHE )(?<!\bOF )(?<!\bAND )(?<!\bINTO )\b[A-Z]{3,} (?:COUNTY|PARISH|TOWNSHIP|BOROUGH)\b"
    r"|(?:DEPT|DEPARTMENT|MINISTRY) OF\b|(?:DHS|DHHS|DSHS|DCF|DCFS|DSS)\b|SCHOOL DIST(?:RICT)?\b|DFAS\b)"
)
_PUBLIC_PAYER_TEMPLATE = re.compile(
    r"^(?:ELECTRONIC (?:CREDIT|DEPOSIT)(?: FROM)?|ACH (?:CORP )?CREDIT|ACH DEPOSIT|CCD DEPOSIT|DEPOSIT FROM"
    r"|PREAUTHORIZED CREDIT|EFT CREDIT)\b ?"
)
_PUBLIC_PAYER_PURPOSE = re.compile(
    r"\bVEN(?:DOR)? ?(?:PAY(?:MENTS?)?|P(?:Y)?MTS?)(?:SEC)?\b|\bPROV(?:IDER)? ?PAY(?:MENTS?)?(?:SEC)?\b"
    r"|\bEDI ?(?:PYMNTS|PAYMENTS?|PMTS?)(?:SEC)?\b"
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
_PUBLIC_PAYER_OTHER_VETO = re.compile(
    r"(?<![A-Z])(?:ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC)\b"
    r"|(?<![A-Z])(?:FUNDING|FUNDER|LENDING|LENDER|FINANC\w*|CAPITAL|CREDIT UNION|MORTGAGE|LEASE|LEASING|FACTOR\w*)\b"
    r"|\bFCU\b|(?<![A-Z])SETTLEMENT\b"
)
_PUBLIC_PAYER_ARM_B_TRANSFER = re.compile(r"(?<![A-Z])(?:TRANSFER|XFER)\b|\bTFR\b")

_WIRE_PARTY_FIELDS = re.compile(
    r"\bB O\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)|\bN?BNF\b.*?(?=\b(?:REF|OBI|RFB|IMAD|TRN|ORIG)\b|$)"
    r"|\bORIG\b(?! TO BNF).*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN|SND BK|PMT DET)\b|$)|\bACCT \d+\b"
    r"|\bORIGINATOR NAME\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)|\bORG\b.*?(?=\b(?:REF|OBI|RFB|BNF|IMAD|TRN)\b|$)"
)
_WIRE_NON_SALE_PURPOSE = re.compile(
    r"(?<![A-Z])(?:INVEST\w*|DISTRIBUTION|DIVIDEND|EQUITY|MEMBERSHIP INTEREST|SHAREHOLDER|STOCK|CONTRIBUTION|PROCEEDS"
    r"|ESCROW|CLOSING|OVER PAYMENT|REBATE|RETURN(?:ED)?|CREDIT MEMO|DUPLICATE|SALARY|PAYROLL|WAGES|GRANT|DONATION|GIFT"
    r"|INTEREST|REPAY\w*|PRINCIPAL|SECURITY DEPOSIT|INTER ?COMPANY|INTERCO|AFFILIATE|OWNERS?|PERSONAL|COURT|JUDGMENT"
    r"|INSURANCE|CLAIMS?|RETN|REJT|REJECT(?:ED)?|RECALL(?:ED)?|UNABLE TO APPLY|DRAWS?|DRAWDOWNS?|DISBURS\w*"
    r"|SUPPLY CHAIN|EARLY PAY(?:MENT)?|DISCOUNT(?:ED|ING)?|PAYOFF|SURPLUS|EARNEST|SUBSCRIPTIONS?|COMPENSATION"
    r"|ADJUSTMENTS?|SHORTAGES?|ALLOWANCES?|PROMISSORY|CONVERTIBLE|BRIDGE|SAFE|TRANCHE|DEPOSIT BACK|FEES)\b"
    r"|\b(?:TAX|RTN|FEE|SCF|ADJ|RMA)\b"
)
#: §7.9: the channel and bank fields removed before the financing roots are read on a wire.
_WIRE_CHANNEL_AND_BANK_FIELDS = re.compile(
    r"^(?:WIRE TYPE \S+ IN|USD WIRE IN|[A-Z]{3} WIRE IN|FEDWIRE CREDIT|CHIPS CREDIT|WT FED|WIRE TSF"
    r"|WIRE TRANSFER \S+|INCOMING WIRE|WIRE IN|WIRE FROM|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN)(?: INCOMING)? WIRE"
    r"|INCOMING FUNDS TRANSFER|FUNDS TRANSFER CREDIT TT|INBD FUNDS TRANSFER|FUNDS TRANSFER WIRE FROM"
    r"|BOOK TRANSFER CREDIT)\b"
    r"|\b(?:SND BK|BBI|VIA|INTERMEDIARY|INT BK|OGB)\b.*?(?=\b(?:B O|ORIG|ORG|REF|OBI|BNF|TRN|IMAD|PMT DET|RFB|RMR|ID)\b|$)"
)
#: §7.9, §8.5: a wire from a title or escrow firm carries sale, closing or escrow money, never a sale of the business.
_TITLE_OR_ESCROW_ORIGINATOR = re.compile(r"(?<![A-Z])(?:TITLE|ESCROW)\b")
#: §7.9: a cut originator field: the field widths of Santander (16) and Bank of America (25).
_WIRE_ORIGINATOR_FIELD_WIDTHS = (16, 25)
_FINANCING_FULL_WORDS = (
    "FUNDING", "FINANCIAL", "CAPITAL", "LENDING", "LOANS", "ADVANCE", "MERCHANT", "CREDIT", "LEASING", "SERVICING",
    "FACTORING", "MORTGAGE", "RECEIVABLES", "EQUIPMENT", "ACCEPTANCE", "COLLECTIONS", "RECOVERY", "SETTLEMENT",
    "REMITTANCE", "EQUITIES", "EQUITY", "VENTURES",
)

#: §7.9: the financing and potential aliases, run together, for the cut-originator test.
_FINANCING_RUN_TOGETHER_ALIASES = frozenset(
    normalize_transaction_description(alias).replace(" ", "")
    for state, registry in (*PAYEE_GROUP_REGISTRIES.items(), ("potential_lender", POTENTIAL_LENDER_ALIASES))
    if state in FINANCING_STATES or state == "potential_lender"
    for aliases in registry.values()
    for alias in aliases
)
#: §7.8: each wholesale auction's aliases as a registry of its own, read on the originator segment.
_AUCTION_ALIAS_REGISTRIES = {
    entity: {entity: OPERATING_REVENUE_READ_ALIASES[entity]}
    for entity, source_type in OPERATING_REVENUE_SOURCE_TYPES.items()
    if source_type == "wholesale_auto_auction"
}
_CARD_FORMS = tuple(
    (form, re.compile(form.pattern), re.compile(form.refusal) if form.refusal else None)
    for form in CARD_SETTLEMENT_CREDIT_FORMS
)
_PAYOUT_FORMS = tuple(
    (entity, label, re.compile(pattern))
    for entity, forms in OPERATING_SOURCE_PAYOUT_FORMS.items()
    for label, pattern in forms
)
_AUCTION_PAYOUT_FORMS = {
    entity: tuple(re.compile(pattern) for pattern in patterns)
    for entity, patterns in WHOLESALE_AUCTION_PAYOUT_FORMS.items()
}
_AUCTION_REFUND_NAMES = {entity: re.compile(pattern) for entity, pattern in WHOLESALE_AUCTION_REFUND_NAMES.items()}
_OPERATING_CONTEXT_WORDS = {
    entity: re.compile(r"\b(?:" + "|".join(words) + r")\b") for entity, words in OPERATING_SOURCE_CONTEXT_WORDS.items()
}
#: §7.1 (the ledger gate): each waiting processor's bare aliases, as whole words, longest first.
_GATED_PROCESSOR_PATTERNS = {
    processor: re.compile(r"\b(?:" + "|".join(
        re.escape(normalize_transaction_description(alias)) for alias in sorted(aliases, key=len, reverse=True)
    ) + r")\b")
    for processor, aliases in GATED_PROCESSOR_ALIASES.items()
}
_WIRE_INVOICE_SPLITS = tuple(
    dict.fromkeys(word[:cut] + " " + word[cut:] for word in ("INVOICE", "INVOICES") for cut in range(1, len(word)))
)
_WIRE_SALE_PURPOSE = re.compile(
    r"\b(?:INVOICES?|" + "|".join(_WIRE_INVOICE_SPLITS) + r")\b"
    r"|\bINV(?:OICE)?S? ?(?:NO |NUM |NBR |NUMBER )?\d"
    r"|\bPO ?(?:NO |NUM |NBR |NUMBER )?\d{3,}|\bPURCHASE ORDERS?\b"
    r"|(?<!\bMONEY )(?<!\bSTANDING )(?<!\bPAYMENT )(?<!\bPMT )(?<!\bCOURT )(?<!\bPAY )(?<!\bTRANSFER )(?<!\bSUPPORT )"
    r"(?<!\bBANK )(?<!\bWIRE )\bORDERS? ?(?:NO\b|NUM\b|NBR\b|NUMBER\b|\d)"
    r"|\bPAYMENT FOR GOO(?:DS?)?\b|\bPAGO PROVEEDOR\b|\bFACTURA\b|\bREF INV\b|\bPRO ?FORMA\b|\bCOMPRA (?:DE )?MERCAD\w*"
)


@dataclass(frozen=True)
class _OperatingSource:
    """5.5 (§7.2): what the operating-source reader found on one credit."""

    entity: str
    alias: str
    source_type: str | None
    payout_form: bool


def _operating_read_vetoed(row: str, entity: str, alias: str, payout_form: bool) -> bool:
    """5.5 (§7.2, §7.3): the vetoes of a new operating read (a payout form, or an alias this release added), read on
    the row before its receiver fields: pay, financing, reversal and adjustment, and person-to-person words. An
    employer-type alias also refuses DIR DEP, PAYRL and REIMB, and the TikTok aliases count only on an ACH-shaped row.
    A transport marketplace also refuses wallet, subscription and wire words. A sixteen-character cut carries its
    alias's vetoes (§7.0)."""
    new_read = payout_form or entity in OPERATING_SOURCES_READ_WITH_VETOES or alias in _OPERATING_ALIASES_VETOED
    if not new_read:
        return False
    if (
        _OPERATING_PAY_VETO.search(row)
        or _matches_any(row, _PAYROLL_PATTERNS)
        or _is_payroll_provider_row(row)
        or _OPERATING_FINANCING_VETO.search(row)
        or _OPERATING_REVERSAL_VETO.search(row)
        or _OPERATING_P2P_VETO.search(row)
    ):
        return True
    if alias in _EMPLOYER_TYPE_ALIASES and _EMPLOYER_PAY_WORDS.search(row):
        return True
    if alias in _TIKTOK_ALIASES and not _ACH_SHAPED_ROW.search(row):
        return True
    return OPERATING_REVENUE_SOURCE_TYPES.get(entity) == "transport_marketplace" and bool(
        _TRANSPORT_EXTRA_VETO.search(row)
    )


def _read_inside_a_waiting_processor(text: str, entity: str, alias: str) -> bool:
    """5.5 (§7.1, the ledger gate): the operating alias read lies inside the bare alias of another processor the
    ledger has not cleared ('BY STRI' inside 'JOBBER BY STRI'), so it names no source while that processor waits."""
    return any(
        processor != entity and any(alias in found.group(0) for found in pattern.finditer(text))
        for processor, pattern in _GATED_PROCESSOR_PATTERNS.items()
    )


def _operating_source(text: str) -> _OperatingSource | None:
    """5.5 (§7.2): the operating source a credit's revenue text names: a payout form first (it names the entity and
    counts as payout context), else the longest operating alias or its sixteen-character cut, read with the receiver
    field's value removed (§5.2). A wholesale-auction alias counts only on the originator segment. A new read that a
    veto of §7.2 refuses names no source, and so does an alias read inside a waiting processor's bare alias (§7.1).
    One helper for step 10 and the recurrence pass."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    for entity, label, pattern in _PAYOUT_FORMS:
        if pattern.search(row) or pattern.search(joined):
            if _operating_read_vetoed(row, entity, label, True):
                return None
            return _OperatingSource(entity, label, OPERATING_REVENUE_SOURCE_TYPES.get(entity), True)
    alias_text = _without_receiver_value(text)
    found = registry_match(alias_text, OPERATING_REVENUE_READ_ALIASES)
    if found is None or _read_inside_a_waiting_processor(alias_text, *found):
        return None
    entity, alias = found
    source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
    if source_type == "wholesale_auto_auction" and registry_match(
        _originator_segment(text), _AUCTION_ALIAS_REGISTRIES[entity]
    ) is None:
        return None
    if _operating_read_vetoed(row, entity, alias, False):
        return None
    return _OperatingSource(entity, alias, source_type, False)


def _card_settlement_form(text: str, *, bank: str | None) -> CardSettlementForm | None:
    """5.5 (§7.1): the first card-settlement form a credit prints, read on the row before its receiver fields and on
    the joined text, unless the form's own refusal or the card veto matches. NET SETTLE is returned too; the caller
    decides it (an unregistered originator needs three such credits, which the recurrence pass counts)."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    if _CARD_VETO.search(row):
        return None
    for form, pattern, refusal in _CARD_FORMS:
        if form.bank is not None and (bank or "").upper() != form.bank:
            continue
        if not (pattern.search(row) or pattern.search(joined)):
            continue
        if refusal is not None and (refusal.search(row) or refusal.search(joined)):
            continue
        # §7.1 (structural S53): the generic credit-card sales words never read on a row that names a card issuer.
        if form.label == "generic_card_sales" and registry_match(row, CARD_ISSUER_CONTEXT_ALIASES) is not None:
            continue
        return form
    return None


def _has_operating_context(text: str, source: _OperatingSource, *, bank: str | None) -> bool:
    """5.5 (§7.1, §7.2): a registry alias verifies one row with payout context: a payout form, the operating-context
    words (read on the row and the joined text), a card-settlement form, the entity's own context words, or, for a
    merchant processor or an invoice platform, the processor payout context. The card veto refuses the last two."""
    if source.payout_form:
        return True
    row = _before_receiver(text)
    joined = _joined_text(row)
    if _matches_any(text, _OPERATING_CREDIT_CONTEXT_PATTERNS) or _matches_any(joined, _OPERATING_CREDIT_CONTEXT_PATTERNS):
        return True
    words = _OPERATING_CONTEXT_WORDS.get(source.entity)
    if words is not None and words.search(row):
        return True
    form = _card_settlement_form(text, bank=bank)
    if form is not None and form.label != "net_settle":
        return True
    return (
        source.source_type in _PROCESSOR_CONTEXT_TYPES
        and not _CARD_VETO.search(row)
        and _PROCESSOR_PAYOUT_CONTEXT.search(row) is not None
    )


def _reversal_credit(text: str) -> bool:
    """5.5 (§6.1 step 3, §7.11): the reversal, cancellation, NSF and provisional-credit rule, with the return codes.
    REIMBURSEMENT never fires on a row that prints a claim or provider signal, and DEBIT CARD CREDIT and POS CREDIT
    never fire on a push payout printed as a card credit (_card_credit_released)."""
    for pattern in _REVERSAL_CANCELLATION_CREDIT_PATTERNS:
        found = pattern.search(text)
        if found is None:
            continue
        if pattern.pattern == _REIMBURSEMENT_WORD.pattern and _CLAIM_OR_PROVIDER_SIGNAL.search(text):
            continue
        if _CARD_CREDIT_LABEL.fullmatch(found.group(0)) and _card_credit_released(text):
            continue
        return True
    return _matches_any(text, _RETURN_CODE_CREDIT_PATTERNS)


def _card_credit_released(text: str) -> bool:
    """5.5 (§7.11): a DEBIT CARD CREDIT or POS CREDIT row that prints a push-rail word, or names a merchant-processor
    or invoice source together with a payout word. Naming another source (a marketplace's card refund) is not
    enough. Such a row is never pooled for recurrence and verifies only by a form or single-row registry context."""
    if not _CARD_CREDIT_LABEL.search(text):
        return False
    if _CARD_CREDIT_PUSH_WORD.search(text):
        return True
    source = _operating_source(text)
    return (
        source is not None
        and source.source_type in _PROCESSOR_CONTEXT_TYPES
        and _CARD_CREDIT_PAYOUT_WORD.search(text) is not None
    )


def _own_book_or_funds_transfer(text: str, account_name: str | None) -> bool:
    """5.5 (§7.11): BOOK TRANSFER and FUNDS TRANSFER are own-account only when no third-party originator is printed,
    or when that originator is the holder (§5.2's holder test). ELECTRONIC FUNDS TRANSFER DEPOSIT is an EFT channel.
    Without the owner's yes to T19, every BOOK TRANSFER stays own-account."""
    found = _BOOK_OR_FUNDS_TRANSFER.search(text)
    if found is None or _EFT_FUNDS_TRANSFER.search(text):
        return False
    if found.group(0).startswith("BOOK") and not THIRD_PARTY_BOOK_TRANSFER_AS_WIRE:
        return True
    originator = _third_party_originator(text)
    return originator is None or holder_named(originator, account_name)


def _split_glued_claim(text: str) -> str:
    """5.5 (§7.7): the text the financing, potential-lender and insurer lookups read: a space before a glued
    HCCLAIMPMT, so a sixteen-character name glued to the token is still found."""
    return _GLUED_CLAIM_ENTRY.sub(r" \1", text)


def _refused_by_payer_guards(text: str, region: str, account_name: str | None) -> str | None:
    """5.5 (§6.1): steps 11 (the customer and invoice descriptors) to 14 refuse a payer the holder test or the
    numbered-company guard matches. Returns 'holder' or 'numbered', or None."""
    if holder_named(region, account_name):
        return "holder"
    if numbered_company(text, region):
        return "numbered"
    return None


def _payer_remittance(text: str, region: str, account_name: str | None) -> bool:
    """5.5 (§7.5): the payer's accounts-payable remittance: an AP pattern, or an invoice number on a row that also
    prints a payment-channel word; the free-text forms count on a PayPal row or a wire only with a company form; the
    veto reads the row with the matched words and the credit posting labels removed."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    matched = None
    for pattern in _PAYER_REMITTANCE_CREDIT_PATTERNS:
        found = pattern.search(row) or pattern.search(joined)
        if found is not None and not (found.group(0) == "PAYABLES" and _BILL_COM.search(row)):
            matched = found.group(0)
            break
    if matched is None:
        found = _INVOICE_NUMBER.search(row)
        if found is not None and _PAYMENT_CHANNEL_WORD.search(row[: found.start()] + " " + row[found.end():]):
            matched = found.group(0)
    if matched is None:
        return False
    # S2.3 review (fix 2): a wire whose reference is glued to WIRE answers to the gate and the vetoes too.
    wire = _wire_vetoes_apply(text)
    if _FREE_TEXT_REMITTANCE.search(matched) and (re.search(r"\bPAYPAL\b", row) or wire):
        if not company_form(payer_name(region)):
            return False
    rest = _CREDIT_POSTING_LABELS.sub(" ", row.replace(matched, " "))
    if _PAYER_REMITTANCE_VETO.search(rest) is not None:
        return False
    if wire and _wire_vetoed(text, region, account_name):
        return False
    # A public payer's vendor payment also answers to §7.6's whole-row veto (a grant, a refund, a benefit, a
    # settlement, assistance), so a public payer never verifies here what §7.6 refuses.
    whole = _TREASURY_BOILERPLATE.sub(" ", text)
    public = _PUBLIC_PAYER_NAME.match(_PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)) is not None
    return not (public and (_PUBLIC_PAYER_NON_SALE_WORDS.search(whole) or _PUBLIC_PAYER_OTHER_VETO.search(whole)))


def _public_payer_remittance(text: str) -> str | None:
    """5.5 (§7.6): a public payer's remittance: arm A (Treasury vendor codes, whole row) or arm B (a public payer
    anchored on the payer name, with a payer-side purpose). Returns the matched rule, or None. Every veto is read on
    the row after Bank of America's Treasury boilerplate is deleted."""
    whole = _TREASURY_BOILERPLATE.sub(" ", text)
    row = _before_receiver(whole)
    if _PUBLIC_PAYER_NON_SALE_WORDS.search(whole) or _PUBLIC_PAYER_OTHER_VETO.search(whole):
        return None
    if any(pattern.search(whole) for pattern in _PUBLIC_PAYER_ARM_A):
        return "treasury_vendor_payment"
    name = _PUBLIC_PAYER_TEMPLATE.sub("", _payee_region(row).strip(), count=1)
    found = _PUBLIC_PAYER_NAME.match(name)
    if found is None:
        return None
    lead = found.group(1)
    if any(ch.isdigit() for ch in lead) or _PUBLIC_PAYER_PURPOSE.search(name[: found.end()]):
        return None
    if _PUBLIC_PAYER_NAME_VETO.search(name) or _PUBLIC_PAYER_ARM_B_TRANSFER.search(whole):
        return None
    if not _PUBLIC_PAYER_PURPOSE.search(row):
        return None
    return "public_payer_vendor_or_provider_payment"


def _wire_financing_text(text: str) -> str:
    """5.5 (§7.9): the wire row the financing roots are read on: the channel words and the sending, originating and
    intermediary bank fields removed (Santander prints its sending bank after WIRE IN FROM, Chase its originating
    bank after OGB)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        text = text[: santander.start("bank")] + " " + text[santander.end("bank"):]
    return _WIRE_CHANNEL_AND_BANK_FIELDS.sub(" ", text)


def _wire_originator_run(text: str) -> str | None:
    """5.5 (§7.9): the first six words of a wire's originator field run together (wrap-tolerant, so 'CAPI TAL' reads
    CAPITAL), or None when the row prints no originator label. On Santander's layout the originator follows the
    account number."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return "".join(santander.group("originator").split()[:6])
    label = _WIRE_ORIGINATOR_LABEL.search(text)
    return None if label is None else "".join(text[label.end():].split()[:6])


def _wire_remittance_purpose(text: str, region: str, account_name: str | None) -> bool:
    """5.5 (§7.9): an incoming wire (N1) whose purpose cites an invoice, a PO, an order or goods, and that no wire veto
    refuses (_wire_vetoed)."""
    if not _is_wire_row(text):
        return False
    purpose_text = _WIRE_PARTY_FIELDS.sub(" ", text)
    holder_text = account_name_text(account_name)
    if len(holder_text) >= 6:
        purpose_text = purpose_text.replace(holder_text, " ")
    if not _WIRE_SALE_PURPOSE.search(purpose_text):
        return False
    return not _wire_vetoed(text, region, account_name)


def _wire_vetoed(text: str, region: str, account_name: str | None) -> bool:
    """5.5 (§7.9): the vetoes of an incoming wire: a non-sale purpose; a financing root after the channel and bank
    fields are removed, or in the first six words after the originator label run together (wrap-tolerant); any known
    payee; the own account (the originator's first two words are the beneficiary's or in the account name); a
    brand-word affiliate (the originator's first distinctive word is the beneficiary's first word or the account
    name's); a cut originator field that starts a financing name; a title or escrow firm (§8.5). The AP rule reads
    them on a wire too (§7.5)."""
    if _WIRE_NON_SALE_PURPOSE.search(text):
        return True
    if _names_financing(_wire_financing_text(text)):
        return True
    run = _wire_originator_run(text)
    if run is not None and _names_financing(run):
        return True
    if match_known_payee(text) is not None:
        return True
    holder_text = account_name_text(account_name)
    originator = region.split()
    beneficiary = re.search(r"\bN?BNF\b (\S+)(?: (\S+))?", text)
    if originator:
        first_two = " ".join(originator[:2])
        if beneficiary is not None and " ".join(word for word in beneficiary.groups() if word) == first_two:
            return True
        if holder_text and len(originator) >= 2 and first_two in holder_text:
            return True
        originator_first = _first_distinctive_word(_distinctive_words(originator))
        holder_first = holder_text.split()[0] if holder_text else None
        if originator_first is not None and (
            (beneficiary is not None and beneficiary.group(1) == originator_first) or originator_first == holder_first
        ):
            return True
        if _cut_financing_originator(region):
            return True
        if _TITLE_OR_ESCROW_ORIGINATOR.search(region):
            return True
    return False


def _cut_financing_originator(region: str) -> bool:
    """5.5 (§7.9): an originator that fills its field to within two characters of the width (Santander 16, Bank of
    America 25), whose run-together name starts a financing or potential alias of six or more characters, or whose
    last word of three or more letters is a proper prefix of a financing word."""
    name = region.strip()
    if not any(width - 2 <= len(name) <= width for width in _WIRE_ORIGINATOR_FIELD_WIDTHS):
        return False
    run = name.replace(" ", "")
    if any(
        len(alias) >= 6 and (alias.startswith(run) or run.startswith(alias)) for alias in _FINANCING_RUN_TOGETHER_ALIASES
    ):
        return True
    last = name.split()[-1] if name.split() else ""
    return len(last) >= 3 and last.isalpha() and any(
        word.startswith(last) and word != last for word in _FINANCING_FULL_WORDS
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
    text = revenue_text(text)

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
    if _reversal_credit(text):
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

    # §6.1 step 4 (Q7, 5.6): a dealer's funding from a listed auto lender is revenue; a credit union's VHCL PURCH
    # entry waits for the statement pass, which verifies two or more of them. Never under the $1 floor (§7.0). The
    # decision names the lender and its alias (S4.3 review), as the financing-proceeds decision it replaces did.
    dealer = dealer_funding_reading(text) if amount >= _MICRO_DEPOSIT_FLOOR else None
    if dealer is not None and dealer.arm == "listed":
        return _RevenueDecision(
            "verified_revenue",
            dealer.entity,
            "auto_lender_dealer_funding",
            dealer.alias,
            "verified_auto_lender_dealer_funding",
            0.90,
            (
                f"Listed auto lender '{dealer.entity}' (alias '{dealer.alias}') pays the dealer on a vehicle contract "
                f"it financed ({dealer.word}): the dealer's revenue, not financing proceeds."
            ),
            source_type="auto_dealer_funding",
            context_signals=("credit_direction", "auto_lender_dealer_funding"),
        )
    if dealer is not None:
        return _RevenueDecision(
            "unverified_deposit",
            dealer.entity,
            "credit_union_vehicle_purchase",
            dealer.alias,
            "credit_union_vehicle_purchase_requires_statement_count",
            0.60,
            (
                f"Credit union '{dealer.entity}' prints the {dealer.word} entry, a credit union's funding of a dealer's "
                "indirect auto loan; two or more such credits in the statement are dealer funding."
            ),
            source_type="auto_dealer_funding",
            context_signals=("credit_direction", "credit_union_vehicle_purchase"),
        )
    # §7.7: the lookups below read a glued HCCLAIMPMT split from the name before it.
    lookup_text = _split_glued_claim(text)
    claim_entry = _HCCLAIMPMT.search(text) is not None
    # A premium-finance credit keeps the insurance credit treatment (spec §4.2). T18: a claim payment skips the
    # insurer registry when the owner's switch is on; T14: an insurer's customer payment is held, not decided.
    insurance_match = _insurance_registry_match(lookup_text)
    if insurance_match is not None and not (claim_entry and HCCLAIMPMT_CLAIM_FIRST):
        entity, alias, _premium_finance = insurance_match
        if claim_entry or _INSURER_CUSTOMER_PAYMENT.search(_before_receiver(text)):
            return _RevenueDecision(
                "unverified_deposit",
                entity,
                "insurer_customer_payment",
                alias,
                "insurer_customer_payment_requires_review",
                0.60,
                (
                    f"Credit matched insurance provider alias '{alias}' with customer-payment or claim-payment "
                    "wording; an analyst decides whether it is revenue."
                ),
                context_signals=("credit_direction", "insurance_provider", "customer_payment_wording"),
            )
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
    if claim_entry and not HCCLAIMPMT_CLAIM_FIRST and _BLUE_PLAN_CLAIM_PAYER.search(_before_receiver(text)):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "insurer_customer_payment",
            None,
            "insurer_customer_payment_requires_review",
            0.60,
            "A Blue-plan claim payment is held with the insurer's credits until the owner rules on claim first.",
            context_signals=("credit_direction", "insurance_provider", "customer_payment_wording"),
        )
    # Spec §4.4 / D1: a credit from a financing group is proceeds. It is decided
    # before the operating-revenue registry, and group aliases are
    # financing-specific (SQUARE CAPITAL, never bare SQUARE), so a platform's
    # sales settlement still reaches the operating registry below. Card-issuer
    # and lease/rental payees never apply to credits, and neither does a
    # payout-credit entity (owner decision 2026-09-25).
    financing_match = _financing_proceeds_payee(lookup_text)
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
    # D1 by descriptor (owner decisions 2026-09-25; 5.5: Square Capital's SQ CAP, SBA and EIDL). `_descriptor_proceeds`
    # keeps the potential registry and the strong non-revenue rule below ahead of a line-of-credit draw or a
    # floor-plan advance.
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
    potential_lender_match = registry_match(lookup_text, POTENTIAL_LENDER_ALIASES)
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
    if _matches_any(text, _NON_REVENUE_CREDIT_PATTERNS) or _own_book_or_funds_transfer(text, account_name):
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

    # §6.1 step 9b, the channel gate: a consumer rail, a check, cash, branch or ATM deposit, or a row with no payer
    # word is never verified; a real-time or push rail is verified by the operating registry only.
    gate = channel_gate(text)
    if gate != "closed":
        source_text = _before_receiver(text) if gate == "push" else text
        source = _operating_source(source_text)
        if source is not None:
            return _operating_source_decision(text, source, account_name=account_name, bank=bank)
    if gate is not None:
        return _fallback_credit_decision(text)

    region = payer_region(text)
    form = _card_settlement_form(text, bank=bank)
    if form is not None and form.label != "net_settle":
        return _RevenueDecision(
            "verified_revenue",
            form.entity,
            "operating_income_descriptor",
            form.label,
            f"card_settlement_form_{form.label}",
            0.93,
            f"Credit prints the card-settlement form '{form.label}'.",
            source_type=OPERATING_REVENUE_SOURCE_TYPES.get(form.entity) if form.entity else None,
            context_signals=("credit_direction", "operating_income_descriptor", "card_settlement_form"),
        )
    joined = _joined_text(_before_receiver(text))
    # S2.3 review: the customer and invoice descriptors never read the receiver field's value, the holder (fix 4,
    # §5.2); on a wire they answer to the §7.9 wire vetoes as steps 12 and 14 do, and a vetoed row falls through (fix 3).
    customer_or_invoice = (
        _matches_any(_without_receiver_value(text), _CUSTOMER_INVOICE_DESCRIPTORS)
        or _matches_any(joined, _CUSTOMER_INVOICE_DESCRIPTORS)
    ) and not (_wire_vetoes_apply(text) and _wire_vetoed(text, region, account_name))
    if _matches_any(text, _VERIFIED_REVENUE_CREDIT_PATTERNS) or _matches_any(joined, _VERIFIED_REVENUE_CREDIT_PATTERNS):
        return _RevenueDecision(
            "verified_revenue",
            None,
            "operating_income_descriptor",
            None,
            "verified_operating_income_descriptor",
            0.93,
            "Credit has a merchant-settlement, card-sales, claim-payment, or verified business-deposit descriptor.",
            context_signals=("credit_direction", "operating_income_descriptor"),
        )
    guard = _refused_by_payer_guards(text, region, account_name)
    if guard == "holder" and (
        customer_or_invoice
        or _payer_remittance(text, region, account_name)
        or _public_payer_remittance(text) is not None
        or _wire_remittance_purpose(text, region, account_name)
    ):
        return _RevenueDecision(
            "unverified_deposit",
            None,
            "holder_named_payer",
            None,
            "payer_prints_the_holders_name",
            0.40,
            "The payer prints the account holder's own name or brand, so its remittance wording is not proof.",
            context_signals=("credit_direction", "holder_named_payer"),
        )
    if guard is None:
        if customer_or_invoice:
            return _RevenueDecision(
                "verified_revenue",
                None,
                "operating_income_descriptor",
                None,
                "verified_operating_income_descriptor",
                0.93,
                "Credit has a customer-payment or invoice descriptor.",
                context_signals=("credit_direction", "operating_income_descriptor"),
            )
        if _payer_remittance(text, region, account_name):
            return _RevenueDecision(
                "verified_revenue",
                None,
                "payer_remittance_descriptor",
                None,
                "verified_payer_accounts_payable_remittance",
                0.90,
                "The payer prints its accounts-payable remittance: the credit pays an invoice of the business.",
                context_signals=("credit_direction", "payer_remittance"),
            )
        public_rule = _public_payer_remittance(text)
        if public_rule is not None:
            return _RevenueDecision(
                "verified_revenue",
                None,
                "public_payer_remittance",
                None,
                public_rule,
                0.90,
                "A public payer pays a vendor or provider remittance of the business.",
                source_type="government_payer",
                context_signals=("credit_direction", "public_payer_remittance"),
            )
        if _wire_remittance_purpose(text, region, account_name):
            return _RevenueDecision(
                "verified_revenue",
                None,
                "wire_remittance_purpose",
                None,
                "verified_wire_remittance_purpose",
                0.90,
                "The incoming wire's remittance cites an invoice, a purchase order, an order or goods.",
                context_signals=("credit_direction", "wire_remittance_purpose"),
            )
    return _fallback_credit_decision(text)


def _operating_source_decision(
    text: str,
    source: _OperatingSource,
    *,
    account_name: str | None,
    bank: str | None,
) -> _RevenueDecision:
    """5.5 (§6.1 step 10): a credit the operating registry names: verified with payout context, otherwise it needs
    recurrence or related activity. Property-management platforms and wholesale auctions never verify here: the
    recurrence pass decides them."""
    entity, alias, source_type = source.entity, source.alias, source.source_type
    business_account = _business_account(account_name)
    has_context = source_type not in {"property_management_payments", "wholesale_auto_auction"} and (
        _has_operating_context(text, source, bank=bank)
    )
    signals = ["credit_direction", "maintained_operating_source"]
    if source.payout_form:
        signals.append("payout_form")
    if has_context:
        signals.append("settlement_or_payout_descriptor")
    if business_account:
        signals.append("business_account")
    if has_context:
        return _RevenueDecision(
            "verified_revenue",
            entity,
            "operating_source_with_credit_context",
            alias,
            "verified_operating_source_credit",
            0.98 if business_account else 0.96,
            (
                f"Credit matched maintained {source_type or 'operating-source'} "
                f"{'payout form' if source.payout_form else 'alias'} '{alias}' with settlement, payout, or deposit "
                "context."
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


def _business_account(account_name: str | None) -> bool:
    """§7.0: a business account for the recurrence rule: BUSINESS, COMMERCIAL, OPERATING or MERCHANT, or (5.5) a
    holder name that prints a legal form."""
    name = account_name_text(account_name)
    return _matches_any(name, _BUSINESS_ACCOUNT_PATTERNS) or _LEGAL_FORM_HOLDER.search(name) is not None


def _fallback_credit_decision(text: str) -> _RevenueDecision:
    """§6.1 steps 15 and 16: deposit wording, else an unidentified posted credit."""
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
_RECEIVER_FIELD_VALUE = re.compile(r"\b(?:INDN|IND NAME|RECEIVER NAME|RECV NAME)\b" + _RECEIVER_VALUE_END)
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
    revenue_tier = tier_of_state(revenue_state)
    revenue_flags = revenue_contribution_flags(revenue_state, revenue_tier)
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
        revenue_tier=revenue_tier,
        revenue_initial_tier=revenue_tier,
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


#: Owner ruling OQ2 (true revenue spec §19, 2026-09-28) put the five BNPL providers in PAYOUT_CREDIT_ENTITIES: a
#: provider's settlement to the merchant is the merchant's own sale, so revenue. The ruling covers settlements only.
#: The 5.4 -> 5.5 census (S3.2) found 7 of the 8 corpus credits that left D1 under it consumer-side (a Klarna
#: WITHDRAWAL, a RETURN FOR ... PURCHASE), and a 9th Klarna WITHDRAWAL that left the lender-credit exclusion: the
#: account holder as the provider's customer, not its merchant. A credit of one of the five that prints one of
#: these consumer-side words (a return, a withdrawal, a refund, a balance, cash back, a reward, a card product, a
#: purchase, or the debt collector TRUEACCORD) keeps its 5.4 reading: D1. Sezzle, American First Finance and
#: PAYABILITY keep the entity-wide exception of 2026-09-25: the corpus prints WITHDRAWAL on Sezzle's merchant payouts
#: and CARD on PAYABILITY's transfers.
_OQ2_BNPL_ENTITIES = frozenset({"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit"})
_BNPL_CONSUMER_CREDIT = re.compile(
    r"\bRETURN\w*|\bWITHDRAW\w*|REFUND\w*|\bRFND\w*|\bREFND\w*|\bRFD\b|\bBALANCE\b|\bCASH ?BACK\b|\bREWARDS?\b"
    r"|\bAFFIRMCARD\b|\bCARD\b|\bPURCHASES?\b|\bTRUE ?ACCORD\b"
)


def _is_payout_credit(text: str, match: PayeeMatch) -> bool:
    """Whether a credit of ``match`` is a payout-credit entity's settlement: revenue, not D1 financing proceeds.

    Owner decision 2026-09-25 (PAYOUT_CREDIT_ENTITIES); OQ2 (§19) narrowed to the
    five BNPL providers' settlements (_BNPL_CONSUMER_CREDIT). Credits only.
    """
    if match.entity not in PAYOUT_CREDIT_ENTITIES:
        return False
    # Both sites read the same text: the revenue text (a glued leading date dropped) without the receiver's name, so
    # the holder's own name ('INDN:BALANCE DENTAL LLC') never makes a settlement consumer-side (§5.2).
    words = _without_receiver_value(revenue_text(text))
    return not (match.entity in _OQ2_BNPL_ENTITIES and _BNPL_CONSUMER_CREDIT.search(words))


def _financing_proceeds_payee(text: str) -> PayeeMatch | None:
    """D1: the known payee whose credit is financing proceeds, or None.

    Owner decision 2026-09-25: the credits of a payout-credit entity
    (PAYOUT_CREDIT_ENTITIES) are the account holder's own sales settled by the
    platform, so they are revenue; that entity's debits keep their group. A BNPL
    provider's consumer-side credit is not a settlement (OQ2, _is_payout_credit).
    Owner ruling 2026-09-26: a factoring payee's credits are the business's own
    sales paid by the factor, so they are revenue too, and they keep the
    factoring flag (_FLAGGED_REVENUE_CREDIT_STATES).
    """
    match = match_known_payee(text)
    if (
        match is None
        or match.state not in FINANCING_STATES
        or match.state in _FLAGGED_REVENUE_CREDIT_STATES
        or _is_payout_credit(text, match)
    ):
        return None
    return match


def _q7_dealer_funding(text: str, amount: float, direction_consistent: bool) -> DealerFunding | None:
    """5.6 (§6.1 step 4, Q7): the credit's dealer-funding reading, read as _classify_credit_revenue reads it: a credit
    of $1 or more whose direction agrees and that no reversal marker claims (steps 2 and 3 win), which
    dealer_funding_reading reads on its revenue text; or None."""
    if amount < _MICRO_DEPOSIT_FLOOR or not direction_consistent:
        return None
    revenue = revenue_text(text)
    dealer = dealer_funding_reading(revenue)
    return None if dealer is None or _reversal_credit(revenue) else dealer


def _dealer_funding_credit_record(
    common: dict[str, object],
    dealer: DealerFunding,
) -> TransactionClassification:
    """5.6 (Q7; S4.3 review): a dealer-funding credit's record keeps its lender, as the financing-proceeds record it
    replaces did: the listed auto lender and its alias, or the credit union its payer region prints. A listed lender's
    dealer funding is never financing proceeds (D1), so it leaves the lender credits; a credit union's VHCL PURCH
    entry is decided by the statement pass (two or more verify, one alone is held)."""
    if dealer.arm == "listed":
        method, rule, confidence = "auto_lender_dealer_funding", "auto_lender_dealer_funding_credit", 0.90
        reason = (
            f"Matched listed auto lender '{dealer.entity}' (alias '{dealer.alias}') on a dealer-funding credit "
            f"({dealer.word}): the lender pays the dealer on a vehicle contract it financed, the dealer's revenue, "
            "never financing proceeds."
        )
    else:
        method, rule, confidence = "credit_union_vehicle_purchase", "credit_union_vehicle_purchase_credit", 0.60
        reason = (
            f"Credit union '{dealer.entity}' prints the {dealer.word} entry, a credit union's funding of a dealer's "
            "indirect auto loan; the statement pass counts such credits (two or more are dealer funding, one alone "
            "is held)."
        )
    return _build_record(
        **common,
        classification="other",
        canonical_entity=dealer.entity,
        match_method=method,
        matched_alias=dealer.alias,
        matched_rule=rule,
        confidence_score=confidence,
        reason=reason,
    )


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
    # 5.5 (§7.11, T5): Square Capital's SQ CAP spelling on a row that names Square, and SBA and EIDL disbursements
    # (A3: the SBA's name cut to its originator field too).
    if _SQUARE_CAPITAL_CREDIT.search(text) and _SQUARE_NAME.search(text):
        return "square_capital_credit", False
    if _SBA_DISBURSEMENT_CREDIT.search(text) or _sba_cut_originator(text):
        return "sba_disbursement_credit", False
    if registry_match(text, POTENTIAL_LENDER_ALIASES) is not None or _matches_any(
        text, _NON_REVENUE_CREDIT_PATTERNS
    ):
        return None
    if _matches_any(text, _LOC_DRAW_CREDIT_PATTERNS):
        return "loc_draw_credit", True
    if _FLOOR_PLAN_ADVANCE_CREDIT.search(text):
        return "floor_plan_advance_credit", False
    return None


def _sba_cut_originator(text: str) -> bool:
    """A3 (precision sample): the payer region of a wire or of a row with an electronic-payment form (an originator
    field) is the SBA's name cut to the field (_SBA_CUT_ORIGINATOR). Never read on a person-to-person or push rail,
    nor on a transfer's sender after FROM, which names an account ('ONLINE TRANSFER FROM SMALL BUSINESS XXXXXX1234')."""
    if "SMALL BUSINESS" not in text:
        return False
    text = revenue_text(text)
    row = _before_receiver(text)
    if not _is_wire_row(text) and (
        _ELECTRONIC_PAYMENT_FORM.search(row) is None
        or _CONSUMER_P2P_RAIL.search(row) is not None
        or _PUSH_RAIL.search(row) is not None
        or _sender_payer_region(text)
    ):
        return False
    return _SBA_CUT_ORIGINATOR.match(payer_region(text).strip()) is not None


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

    # 5.6 (§6.1 step 4, Q7; S4.3 review): a dealer-funding credit takes its lender's record ahead of the fee, transfer,
    # tax, payroll and utility rules and of D1 (CU Direct's VADMIN FEE is the dealer's fee income, never a bank fee;
    # a listed auto lender's dealer funding is never financing proceeds), as its revenue decision runs ahead of D1.
    if amount > 0:
        dealer = _q7_dealer_funding(text, amount, direction_consistent)
        if dealer is not None:
            return _dealer_funding_credit_record(common, dealer)

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
    # decision 2026-09-25: its credits are the holder's own sales; OQ2 covers a
    # BNPL provider's settlements only, _is_payout_credit); a card-issuer
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
        # 5.6 (Q7): a listed auto lender's dealer funding took its own record above, never financing proceeds.
        if known_payee.state in FINANCING_STATES and not _is_payout_credit(text, known_payee):
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
        revenue_tier=tier_of_state(state),
        revenue_initial_tier=tier_of_state(state),
        revenue_tier_reason=None,
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
        **revenue_contribution_flags(state, tier_of_state(state)),
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


#: 5.5 (§6.2 pass 4): the reversal pair reads the credit markers of step 3, return codes included.
_PAIR_MARKER_PATTERNS = (*_REVERSAL_CANCELLATION_CREDIT_PATTERNS, *_RETURN_CODE_CREDIT_PATTERNS)


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
        credit_has_marker = _matches_any(credit.normalized_description, _PAIR_MARKER_PATTERNS)
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
            debit_has_marker = _matches_any(debit.normalized_description, _PAIR_MARKER_PATTERNS)
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


def _recurrence_vetoed(record: TransactionClassification, text: str) -> bool:
    """5.5 (§7.0): a credit that never counts toward recurrence and is never lifted by it: payroll, the recurrence
    veto words and card-credit labels (read on the row before its receiver fields), FUNDING outside the three
    platforms that print it on settlements (review C2), under the $1 floor, or a direction conflict."""
    return (
        _recurrence_veto_wording(record, text)
        or record.amount < _MICRO_DEPOSIT_FLOOR
        or record.revenue_match_method == "direction_conflict"
        or not record.direction_consistent
    )


def _recurrence_veto_wording(record: TransactionClassification, text: str) -> bool:
    """5.5 (§7.0): the worded part of the recurrence veto: payroll, a veto word or card-credit label, or FUNDING
    outside the three platforms that print it on settlements (review C2)."""
    entity = record.revenue_canonical_entity
    return (
        record.classification == "payroll"
        or _recurrence_veto_word(text, record.account_name, entity)
        or (
            entity not in _FUNDING_SETTLEMENT_ENTITIES
            and _recurrence_veto_word(text, record.account_name, entity, _FUNDING_WORD)
        )
    )


def _recurrence_veto_word(
    text: str, account_name: str | None, entity: str | None, pattern: re.Pattern[str] = _RECURRENCE_VETO
) -> bool:
    """5.5 (§7.0): the recurrence veto on the row before its receiver fields. On a store-name platform
    (_STORE_NAME_PAYOUT_ENTITIES) a veto word that is one of the holder's own words (its account name, or the name the
    bank prints in the receiver field), or the start of one (four letters or more), is not read: the platform prints
    the merchant's store name, which is the holder's, in its entry field ('DOORDASH INC DES:<store> CAPITA ...
    INDN:<store> CAPITAL GROUP'). On every other source, and on a row no registry source decided, a veto word always
    vetoes (S2.4 review)."""
    if entity not in _STORE_NAME_PAYOUT_ENTITIES:
        return pattern.search(_before_receiver(text)) is not None
    holder = set(holder_words(account_name))
    for found in _RECEIVER_FIELD_VALUE.finditer(text):
        holder.update(_distinctive_words(found.group(0).split()[1:]))
    row = _before_receiver(text)
    for found in pattern.finditer(row):
        word = found.group(0)
        if len(word) >= 4 and any(own == word or own.startswith(word) for own in holder):
            continue
        return True
    return False


def _in_operating_pool(record: TransactionClassification) -> bool:
    """5.5 (§7.0): only a credit the operating registry decided, or that an operating-source method or an
    entity-naming card form verified, joins an entity's recurrence pool."""
    if record.revenue_canonical_entity is None:
        return False
    if record.revenue_match_method in _OPERATING_POOL_METHODS:
        return True
    return record.revenue_match_method == "operating_income_descriptor" and (
        record.revenue_matched_rule or ""
    ).startswith("card_settlement_form_")


def _upgrade_by_recurrence(
    record: TransactionClassification,
    *,
    entity: str,
    count: int,
    recurring: bool,
    business: bool,
    related_activity: bool,
    extra_signals: Sequence[str] = (),
) -> TransactionClassification:
    """The recurrence pass's verified record for one pooled credit (today's wording)."""
    signals = list(record.revenue_context_signals)
    if recurring:
        signals.append(f"recurring_source_{count}_credits")
    if business:
        signals.append("business_account")
    if related_activity:
        signals.append("related_platform_fee_or_chargeback")
    signals.extend(extra_signals)
    evidence_text = (
        f"recurs in {count} posted credits"
        if recurring
        else "has a related processing fee, commission, chargeback, or adjustment"
    )
    return _replace_revenue_state(
        record,
        "verified_revenue",
        match_method="recurring_operating_source" if recurring else "operating_source_related_activity",
        matched_rule=(
            "maintained_source_recurs_across_statement"
            if recurring
            else "maintained_source_has_related_operating_debit"
        ),
        confidence_score=0.90 if recurring else 0.88,
        reason=f"Maintained operating source '{entity}' {evidence_text}; the credit is verified as operating revenue.",
        context_signals=signals,
    )


def _apply_operating_source_context(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 5 (§6.2, §7.0): operating-source recurrence and related activity, fixed for every source.

    The pool admits only registry rows and operating-method rows (_in_operating_pool); it counts an entity's credits
    already verified by an operating-source method and upgrades only the unverified ones, so a per-row upgrade never
    shrinks it; a vetoed credit never counts and is never lifted (_recurrence_vetoed). A wholesale auction (§7.8) and
    a property-management platform (§7.10) take their own branches, and an unregistered NET SETTLE originator
    verifies with three such credits (§7.1). A debit names its platform as the operating reader does, with the
    receiver field's value removed (§5.2: the holder's name never names a source) and through the ledger gate."""
    updated = list(records)
    pools: dict[str, list[int]] = {}
    vetoed: dict[str, list[int]] = {}
    activity_by_entity: dict[str, list[int]] = {}
    net_settle: dict[tuple[str, ...], list[int]] = {}
    for index, record in enumerate(records):
        if index in duplicate_indexes or not record.is_posted:
            continue
        text = revenue_text(record.normalized_description)
        if record.amount < 0:
            alias_text = _without_receiver_value(text)
            found = registry_match(alias_text, OPERATING_REVENUE_READ_ALIASES)
            if found is not None and _read_inside_a_waiting_processor(alias_text, *found):
                found = None
            if found is not None and _matches_any(alias_text, _OPERATING_PLATFORM_DEBIT_CONTEXT_PATTERNS):
                activity_by_entity.setdefault(found[0], []).append(index)
            continue
        if record.amount <= 0:
            continue
        if _recurrence_vetoed(record, text):
            if _in_operating_pool(record):
                vetoed.setdefault(record.revenue_canonical_entity, []).append(index)
            continue
        if _in_operating_pool(record):
            pools.setdefault(record.revenue_canonical_entity, []).append(index)
        elif (
            record.revenue_classification == "unverified_deposit"
            and record.revenue_match_method in {"ambiguous_credit_descriptor", "unidentified_posted_credit"}
            and channel_gate(text) is None
        ):
            form = _card_settlement_form(text, bank=record.bank)
            if form is not None and form.label == "net_settle":
                key = _payer_key(payer_region(text))
                if key:
                    net_settle.setdefault(key, []).append(index)

    for entity, indexes in pools.items():
        source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
        if source_type == "wholesale_auto_auction":
            _apply_auction_branch(updated, records, entity, indexes, duplicate_indexes)
            continue
        if source_type == "property_management_payments":
            _apply_property_branch(updated, records, entity, indexes)
            continue
        business = any(
            _business_account(records[index].account_name)
            if source_type != "customer_payment_platform"
            else _matches_any(
                account_name_text(records[index].account_name), _BUSINESS_ACCOUNT_PATTERNS
            )
            for index in indexes
        )
        count = len(indexes)
        recurring = count >= _RECURRENCE_MIN_CREDITS or (count >= _RECURRENCE_MIN_BUSINESS_CREDITS and business)
        related = bool(activity_by_entity.get(entity))
        if not recurring and not related:
            continue
        for index in indexes:
            record = updated[index]
            if record.revenue_classification != "unverified_deposit":
                continue
            updated[index] = _upgrade_by_recurrence(
                record, entity=entity, count=count, recurring=recurring, business=business, related_activity=related,
            )

    for indexes in net_settle.values():
        if len(indexes) < _NET_SETTLE_MIN_CREDITS:
            continue
        for index in indexes:
            updated[index] = _replace_revenue_state(
                updated[index],
                "verified_revenue",
                match_method="operating_income_descriptor",
                matched_rule="card_settlement_form_net_settle",
                confidence_score=0.90,
                reason=f"One originator's NET SETTLE entry recurs in {len(indexes)} posted credits: card settlements.",
                context_signals=(*updated[index].revenue_context_signals, "card_settlement_form"),
            )
    _name_vetoed_branch_rows(updated, vetoed)
    return updated


def _name_vetoed_branch_rows(updated: list[TransactionClassification], vetoed: dict[str, list[int]]) -> None:
    """5.5 (§7.8, §7.10, §14.1; S2.4 review): a vetoed pool row of a wholesale auction or a property-management
    platform never counts and is never lifted, and still carries its branch's rule. Only a direction-consistent
    unverified row in an operating method is renamed; its classification stays. An auction row takes the auction's
    refusal (a payout-form row vetoed by a pay, financing or other veto word takes the financing or consumer rule; one
    vetoed only by the $1 floor has no rule of its own and is left as it is); a property row takes the owner or
    deposit wording rule when it prints that wording."""
    for entity, indexes in vetoed.items():
        source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
        if source_type not in {"wholesale_auto_auction", "property_management_payments"}:
            continue
        forms = _AUCTION_PAYOUT_FORMS.get(entity, ())
        for index in indexes:
            record = updated[index]
            if (
                not record.direction_consistent
                or record.revenue_classification != "unverified_deposit"
                or record.revenue_match_method not in _OPERATING_SOURCE_METHODS
            ):
                continue
            text = revenue_text(record.normalized_description)
            if source_type == "property_management_payments":
                if _PROPERTY_PLATFORM_GUARD.search(_before_receiver(text)):
                    updated[index] = _property_wording_record(record, entity)
                continue
            rule = _auction_refusal(text, forms)
            if rule is None:
                if not _recurrence_veto_wording(record, text):
                    continue
                rule = "auction_credit_prints_financing_or_consumer_word"
            updated[index] = _auction_unverified_record(record, entity, rule)


def _auction_refusal(text: str, forms: Sequence[re.Pattern[str]]) -> str | None:
    """5.5 (§7.8, §14.1): the rule that refuses an auction credit on its wording (a buyer-payment reference, a
    floor-plan or financing word or a consumer entry, or no observed payout form), or None when it prints the payout
    form. The payout form is read with the receiver field's value removed (§5.2): the holder's name never verifies."""
    if _AUCTION_BUYER_PAYMENT.search(text):
        return "auction_credit_prints_buyer_payment_reference"
    if _AUCTION_VETO.search(_before_receiver(text)):
        return "auction_credit_prints_financing_or_consumer_word"
    if not any(form.search(_without_receiver_value(text)) for form in forms):
        return "auction_credit_without_payout_form"
    return None


def _auction_unverified_record(
    record: TransactionClassification, entity: str, rule: str
) -> TransactionClassification:
    """5.5 (§7.8): an auction credit that is not the auction's verified payout."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="operating_source_requires_context",
        matched_rule=rule,
        confidence_score=0.60,
        reason=f"A credit from the wholesale auction '{entity}' that is not its observed payout form.",
        context_signals=record.revenue_context_signals,
    )


def _property_wording_record(record: TransactionClassification, entity: str) -> TransactionClassification:
    """5.5 (§7.10): a property-management platform's credit printing owner, distribution or deposit wording."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="operating_source_requires_context",
        matched_rule="property_platform_owner_or_deposit_wording",
        confidence_score=0.60,
        reason=f"A '{entity}' credit prints owner, distribution or deposit wording.",
        context_signals=record.revenue_context_signals,
    )


def _apply_auction_branch(
    updated: list[TransactionClassification],
    records: list[TransactionClassification],
    entity: str,
    indexes: Sequence[int],
    duplicate_indexes: set[int],
) -> None:
    """5.5 (§7.8): a dealer-only wholesale auction verifies only its observed payout form, never a buyer-payment
    reference, a floor-plan or financing word or a consumer entry (§14.1), and never a credit paired with an equal
    same-auction debit within 14 days (each debit used once). The payout form is read with the receiver field's value
    removed (§5.2): the holder's name never verifies."""
    forms = _AUCTION_PAYOUT_FORMS.get(entity, ())
    refund_name = _AUCTION_REFUND_NAMES.get(entity)
    used_debits: set[int] = set()
    for index in indexes:
        record = updated[index]
        rule, verified = _auction_refusal(revenue_text(record.normalized_description), forms), False
        if rule is None:
            pair = _auction_refund_pair(records, index, refund_name, used_debits, duplicate_indexes)
            if pair is not None:
                used_debits.add(pair)
                rule = "auction_credit_matches_same_source_debit"
            else:
                rule, verified = "wholesale_auto_auction_proceeds", True
        if verified:
            updated[index] = _replace_revenue_state(
                record,
                "verified_revenue",
                match_method="wholesale_auction_payout_form",
                matched_rule=rule,
                confidence_score=0.90,
                reason=f"A dealer-only wholesale auction ('{entity}') pays out in its observed payout form.",
                context_signals=(*record.revenue_context_signals, "wholesale_auction_payout_form"),
            )
        else:
            updated[index] = _auction_unverified_record(record, entity, rule)


def _auction_refund_pair(
    records: list[TransactionClassification],
    credit_index: int,
    refund_name: re.Pattern[str] | None,
    used: set[int],
    duplicate_indexes: set[int],
) -> int | None:
    """5.5 (§7.8): the index of an unused posted debit that names the auction (on its row or its wire BNF line), for
    the same amount to the cent, within 14 days of the credit; or None."""
    if refund_name is None:
        return None
    credit = records[credit_index]
    credit_date = parse_date(credit.date)
    for index, debit in enumerate(records):
        if (
            index in used or index in duplicate_indexes or debit.amount >= 0 or not debit.is_posted
            or round(abs(debit.amount), 2) != round(credit.amount, 2)
            or not refund_name.search(debit.normalized_description)
            or re.search(r"\bACV CAPITAL\b", debit.normalized_description)
        ):
            continue
        debit_date = parse_date(debit.date)
        if credit_date is not None and debit_date is not None and abs(
            (credit_date - debit_date).days
        ) > _AUCTION_REFUND_WINDOW_DAYS:
            continue
        return index
    return None


def _apply_property_branch(
    updated: list[TransactionClassification],
    records: list[TransactionClassification],
    entity: str,
    indexes: Sequence[int],
) -> None:
    """5.5 (§7.10, T15): a property-management platform verifies by recurrence of its ACH payout shape only (three
    credits, or two in a business account), never by a related fee debit. A row printing owner, distribution or
    deposit wording is left out of the count and stays unverified; micro-deposits never count; a push-shaped row
    stays operating_source_requires_context. A verified row carries the property-management chip."""
    counted: list[int] = []
    for index in indexes:
        record = updated[index]
        text = revenue_text(record.normalized_description)
        row = _before_receiver(text)
        if _PROPERTY_PLATFORM_GUARD.search(row):
            updated[index] = _property_wording_record(record, entity)
            continue
        if _PROPERTY_MICRO_DEPOSIT.search(row) or _PROPERTY_PUSH_SHAPE.search(row):
            continue
        if not _ELECTRONIC_PAYMENT_FORM.search(row):
            continue
        counted.append(index)
    business = any(_business_account(records[index].account_name) for index in counted)
    count = len(counted)
    if not (count >= _RECURRENCE_MIN_CREDITS or (count >= _RECURRENCE_MIN_BUSINESS_CREDITS and business)):
        return
    for index in counted:
        record = updated[index]
        if record.revenue_classification != "unverified_deposit":
            continue
        updated[index] = _upgrade_by_recurrence(
            record, entity=entity, count=count, recurring=True, business=business, related_activity=False,
            extra_signals=("property_management_collections",),
        )


def _payer_key(region: str) -> tuple[str, ...]:
    """5.6 (§5.2): the payer key: the payer name's words without the generic words, at most the first four."""
    return tuple(word for word in payer_name(region).split() if word not in REVENUE_GENERIC_WORDS)[:4]


def _payer_first_distinctive_word(region: str) -> str | None:
    """5.5 (§7.5, §8.1): the payer's first distinctive word: four or more letters, not an AP, bank-template,
    legal-suffix, generic or public-payer word, and not a common name-starter."""
    words = [word for word in _distinctive_words(payer_name(region).split()) if word not in _counter_debit_skip_words()]
    return _first_distinctive_word(words)


#: 5.5 (§7.5, S2.4 review): a card purchase's leading card-form words and the MMDD date after them. D11 stops at that
#: date, so 'CHECKCARD 0302 NORTHWIND GRILL' reads CHECKCARD alone; pass 6 reads the debit after them.
_CARD_FORM_DEBIT_PREFIX = re.compile(
    r"^(?:RECURRING )?(?:CHECKCARD|(?:MOBILE |CARD )?PURCHASE(?: AUTHORIZED ON)?) (?:\d{4}|\d{2} \d{2}) (?=\S)"
)


#: 5.5 (§7.5, S2.4 re-review): the words of a card purchase's merchant pass 6 reads. The city and state follow them.
_CARD_MERCHANT_WORDS = 2


def _card_processor_code(token: str, printed: str) -> bool:
    """5.5 (S2.4 re-review): a card purchase's leading token is a processor code ('SQ *', 'TST*'): at most three
    letters printed right before a star, which normalization drops."""
    return (
        token.isalpha() and len(token) <= 3
        and re.search(rf"(?<![A-Za-z0-9]){re.escape(token)} ?\*", printed, re.IGNORECASE) is not None
    )


def _card_merchant_text(text: str, printed: str) -> str | None:
    """5.5 (§7.5, S2.4 re-review): a card purchase's merchant, after its card-form prefix and a processor code: its
    first two words, or None when the merchant's first token is a reference or a short token ('76', 'BP1234567',
    'SQ *AB'). Never read past the merchant's first words, so the city printed after it is never the debit's word."""
    tokens = _payee_region(text).split()
    if tokens and _card_processor_code(tokens[0], printed):
        tokens = tokens[1:]
    if not tokens or _is_reference_token(tokens[0]) or len(tokens[0]) <= 2:
        return None
    return " ".join(tokens[:_CARD_MERCHANT_WORDS])


def _debit_word_reading(record: TransactionClassification) -> tuple[str | None, bool]:
    """5.5 (§7.5, §8.1): a posted debit's first distinctive word, read on its D11 payee words; on a card purchase,
    after its leading card-form words and MMDD date and only on its merchant's first two words (S2.4 review and
    re-review; D11 itself is unchanged). The second value says whether the debit is a card purchase (its card-form
    prefix matched): pass 7 leaves a card purchase's merchant out of payer_also_debited (5.6, A1 census)."""
    text, card_form = _CARD_FORM_DEBIT_PREFIX.subn("", record.normalized_description, count=1)
    if card_form:
        text = _card_merchant_text(text, record.original_description or "")
        if text is None:
            return None, True
    words = [
        word for word in _distinctive_words(_unknown_payee_tokens(text))
        if word not in _counter_debit_skip_words()
    ]
    return _first_distinctive_word(words), bool(card_form)


def _debit_first_distinctive_word(record: TransactionClassification) -> str | None:
    """5.5 (§7.5, §8.1): a posted debit's first distinctive word (_debit_word_reading), a card purchase's merchant
    included: pass 6's counter-debit guard reads it."""
    return _debit_word_reading(record)[0]


def _apply_payer_remittance_counter_debit_guard(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 6 (§6.2, §7.5): a credit the payer-remittance rule verified goes back to unverified when a
    posted debit in the same statement shares the payer's first distinctive word (an own account, an affiliate or a
    funder that collects)."""
    debit_words = {
        word
        for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount < 0 and record.is_posted
        and (word := _debit_first_distinctive_word(record)) is not None
    }
    updated = list(records)
    for index, record in enumerate(records):
        if record.revenue_match_method != "payer_remittance_descriptor":
            continue
        word = _payer_first_distinctive_word(payer_region(revenue_text(record.normalized_description)))
        if word is None or word not in debit_words:
            continue
        updated[index] = _replace_revenue_state(
            record,
            "unverified_deposit",
            match_method="payer_remittance_with_counter_debit",
            matched_rule="payer_also_debited_in_statement",
            confidence_score=0.50,
            reason="The payer of this accounts-payable remittance is also debited in the statement.",
            context_signals=(*record.revenue_context_signals, "payer_also_debited"),
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
    # Atlas's Smart Save sweep ('SMARTSAVE <reference> ATLASFINANCIAL <trace>'): only reference numbers may sit
    # between the two words, since the veto reads the row without the matched words, and the tail stops at
    # ATLASFINANCIAL, so no name printed inside the match is hidden from it.
    re.compile(r"\bSMART ?SAVE(?:\s+[0-9]+)*\s+ATLAS ?FIN(?:ANCIAL)?\b"),
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


def _vendor_match_names_financing(matched: str) -> bool:
    """5.3: whether a vendor match carries a financing root. A vendor stem's trailing letters would swallow a root run
    together with it ('FAB DISTRIBUTIONCAPITAL LLC', 'BOOKKEEPINGFUNDING', 'FAB DISTRIBUTORSCREDIT'), and the lending
    guard reads the row without the matched words, so such a match is no vendor. The whole word FUND of the ad-fund
    phrases (AD FUND, MARKETING FUND, ADVERTISING FUND) is their own vocabulary, not a glued root."""
    return any(word != "FUND" and _FINANCING_ROOT_PATTERN.search(word) for word in matched.split())


def _is_vendor_payee(payee: Sequence[str], text: str, account_name: str | None) -> bool:
    """5.3: the D11 payee words (or, on a bounded row, the originator segment, which then never reads a receiver
    field) name a vendor or another payee that never lends, the row prints no lending word (outside the matched vendor
    words, which carry none themselves), and those words carry none of the account holder's own name words. On a row
    that is one run of words the segment is never read, and when the holder's name is unknown the vendor word must be
    the payee's first word."""
    words = " ".join(payee)
    bounded = _payee_words_are_bounded(text)
    segment = _originator_segment(text) if bounded else ""
    found = next(
        (
            match
            for source in (words, segment)
            for pattern in _VENDOR_PAYEE_PATTERNS
            if (match := pattern.search(source)) and not _vendor_match_names_financing(match.group(0))
        ),
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
    """5.3: the shared veto reads the whole row `text`, the recipient included. The skip's own words (PAYONEER, PAY
    TO, PAYMENT DATE, TRN) carry no financing root, so nothing is removed first: the pattern's spans are never
    hidden from the veto."""
    found = _PLATFORM_PAYOUT_PATTERN.search(text)
    if found is None:
        return False
    recipient = [token for token in found.group("recipient").split()
                 if len(token) > 1 and not _is_reference_token(token)]
    return bool(recipient) and not any(
        token in _ORGANISATION_CUES or token == "PAYONEER" for token in recipient
    ) and not _names_financing(text)


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
    """5.3: besides its own loan and capital guard, the skip reads the shared veto on the whole row. The skip's own
    words (SQUARE, SQ and the entry date, INTUIT PYMT SOLN) carry no financing root, so nothing is removed first."""
    text = record.normalized_description
    return (
        abs(record.amount) <= _PROCESSOR_ACCOUNT_CHARGE_MAX
        and _matches_any(text, _PROCESSOR_ACCOUNT_DEBIT_PATTERNS)
        and _PROCESSOR_DEBIT_FINANCING_GUARD.search(text) is None
        and not _names_financing(text)
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
    records = _apply_payer_remittance_counter_debit_guard(records, set(duplicate_of))
    # 5.6 (§6.2 pass 7): payer facts, Q7's credit-union arm, the Q5 and Q6 verifications, then the tiers.
    records = apply_true_revenue_pass(records, set(duplicate_of))

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
            contributes_to_counted_flagged=False,
            contributes_to_excluded_pending_review=False,
            revenue_tier="non_revenue" if duplicate_revenue else None,
            revenue_initial_tier="non_revenue" if duplicate_revenue else None,
            revenue_tier_reason=None,
        )

    return records
