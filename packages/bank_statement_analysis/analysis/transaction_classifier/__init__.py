from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from functools import cache
from datetime import date
from statistics import mean, pstdev
from typing import Callable, Literal, Sequence, TYPE_CHECKING

from analysis.classification_registry import (
    BANK_NAME_ALIASES,
    BANK_POSTING_TYPE_LABELS,
    BLUE_PLAN_CLAIM_PAYERS,
    CARD_SETTLEMENT_CREDIT_FORMS,
    CardSettlementForm,
    BANK_SPECIFIC_LENDER_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    FACTORING_REVIEW_ENTITIES,
    GATED_PROCESSOR_ALIASES,
    INSURANCE_PROVIDER_ALIASES,
    OPERATING_ALIASES_READ_WITH_VETOES,
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    OPERATING_SOURCE_CONTEXT_WORDS,
    OPERATING_SOURCES_READ_WITH_VETOES,
    PAYEE_GROUP_REGISTRIES,
    PAYOUT_CREDIT_ENTITIES,
    POTENTIAL_LENDER_ALIASES,
    PREMIUM_FINANCE_ALIASES,
    REVIEW_FLAG_ENTITIES,
    WHOLESALE_AUCTION_PAYOUT_FORMS,
    WHOLESALE_AUCTION_REFUND_NAMES,
)
from analysis.dates import parse_date
from analysis.flag_groups import FINANCING_STATES, FLAG_GROUP_BY_KEY, FLAG_GROUP_BY_STATE
from analysis.revenue import RevenueState, revenue_contribution_flags, tier_of_state
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from analysis.description_text import ln_name_spans, normalize_transaction_description
from analysis.payee_matcher import PayeeMatch, match_debt_relief_payee, match_known_payee, match_memo, registry_match
from analysis.descriptor.financing import (
    _card_posting_vetoed,
    _names_card_issuer,
    _names_financing,
    _skips,
    _vendor_match_names_financing,
)
from analysis.descriptor.lexical import (
    _before_receiver,
    _distinctive_words,
    _first_distinctive_word,
    _is_reference_token,
    _joined_text,
    _leading_name_words,
    _leading_payee_words,
    _originator_payer_words,
    _originator_segment,
    _payee_region,
    _row_before_receiver,
    _skip_numbered_leading_date,
    _strip_revenue_template,
    _wire_beneficiary,
    company_form,
    payer_name,
    revenue_text,
    without_statement_furniture,
)
from analysis.descriptor.words import (
    IRS_TREASURY_FORM,
    REVENUE_GENERIC_WORDS,
    THIRD_PARTY_BOOK_TRANSFER_AS_WIRE,
    _ACH_FIELD_SEGMENT,
    _AMEX_ACH_CREDIT,
    _BANK_TEMPLATE_WORDS,
    _BMO_CODE_TAIL,
    _BNPL_CONSUMER_CREDIT,
    _BUSINESS_ACCOUNT_PATTERNS,
    _CARD_FORM_DEBIT_PREFIX,
    _CASH_BRANCH_ATM_FORM,
    _CHANNEL_TRANSFER_FROM_ACCOUNT,
    _CHANNEL_VOCABULARY,
    _CHECK_DEPOSIT_FORM,
    _CHECK_PATTERNS,
    _CONSUMER_P2P_RAIL,
    _CUSTOMER_INVOICE_DESCRIPTORS,
    _DEPOSIT_UNDO_FEE,
    _DIRECT_DEBIT_LOAN_PATTERNS,
    _ELECTRONIC_PAYMENT_FORM,
    _ENTITY_NAME_LABELS,
    _ENTITY_NOISE,
    _EXPLICIT_REPAYMENT_PATTERNS,
    _FINANCING_ROOT_PATTERN,
    _FLAGGED_REVENUE_CREDIT_STATES,
    _FRENCH_CANCEL_CREDIT_PATTERN,
    _FRENCH_INTEREST_CREDIT,
    _INTERNAL_TRANSFER_CREDIT_PATTERNS,
    _LEGAL_FORM_SUFFIXES,
    _LINE_OF_CREDIT_PATTERNS,
    _NAME_STARTERS,
    _NUMBERED_COMPANY_REGION,
    _NUMBERED_TAIL_WORDS,
    _ORGANISATION_CUES,
    _OWN_ACCOUNT_SWEEP_CREDIT_PATTERNS,
    _PAYEE_TEMPLATE_PREFIX,
    _PAYOUT_NON_SALE_CREDIT,
    _PAYROLL_PATTERNS,
    _POS_PATTERNS,
    _PREMIUM_FINANCE_WORDING_PATTERNS,
    _PROVINCE_NOT_A_NAME_START,
    _PUSH_RAIL,
    _QUEBEC,
    _RECEIVER_FIELD_VALUE,
    _REFUND_REVERSAL_PATTERNS,
    _RETAIL_CASH_LOAD,
    _REVERSAL_CANCELLATION_CREDIT_PATTERNS,
    _SANTANDER_WIRE,
    _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS,
    _SETTLEMENT_REVERSAL_PATTERNS,
    _SNAP_MERCHANT_FUNDING,
    _TFR_TRANSFER_DEPOSIT,
    _TRANSFER_FROM_ACCOUNT,
    _WIRE_ORIGINATOR_LABEL,
    _WIRE_WORD,
)
from analysis.descriptor.credit_words import (
    _BILL_COM,
    _BOOK_OR_FUNDS_TRANSFER,
    _CARD_CREDIT_PUSH_WORD,
    _CARD_REFUND_LABELS,
    _EFT_FUNDS_TRANSFER,
    _FUNDING_SETTLEMENT_ENTITIES,
    _FUNDING_WORD,
    _HCCLAIMPMT,
    _INSURER_CUSTOMER_PAYMENT,
    _INVOICE_NUMBER,
    _MICRO_DEPOSIT_FLOOR,
    _NO_LEGAL_FORM_LATER,
    _PAYER_REMITTANCE_CREDIT_PATTERNS,
    _PAYMENT_CHANNEL_WORD,
    _PAYOUT_FORMS,
    _PROCESSOR_CONTEXT_TYPES,
    _PUBLIC_PAYER_NAME,
    _PUBLIC_PAYER_NAME_VETO,
    _PUBLIC_PAYER_NON_SALE_WORDS,
    _PUBLIC_PAYER_TEMPLATE,
    _RECURRENCE_VETO,
    _REMBOURSEMENT_WORD,
    _RETURN_CODE_CREDIT_PATTERNS,
    _RETURN_REFUND_CREDIT_PATTERNS,
    _STORE_NAME_PAYOUT_ENTITIES,
    _TREASURY_BOILERPLATE,
)
from analysis.descriptor.holder import (
    _business_account,
    account_name_text,
    holder_named,
    holder_reading,
    holder_words,
    platform_entry_leads_with_financing,
    store_name_printed,
    store_name_run_words,
)
from analysis.descriptor.payer import (
    _is_bare_row,
    _sender_payer_region,
    channel_gate,
    entry_fields,
    numbered_company,
    payer_region,
)
from analysis.descriptor.rails import (
    _bare_incoming_wire,
    _compile_field_order_forms,
    _counter_debit_skip_words,
    _is_wire_row,
    _matches_any,
    _public_payer_arm_a,
    _state_words,
    _third_party_originator,
    _wire_vetoes_apply,
    _with_served_cuts,
    _without_receiver_value,
)
# The true-revenue pass reads this module's readers at call time, so it imports nothing from here at load.
from analysis.true_revenue import (
    DealerFunding,
    FundingSeries,
    also_debited,
    apply_true_revenue_pass,
    counter_credit,
    counter_debits,
    dealer_funding_reading,
    debited_as_lender,
    payer_text_unread_indexes,
    payer_text_unread_texts,
    premium_trust_title,
    without_receiver_and_holder,
    zelle_credits_present,
)

# True revenue reads these through _classifier() until its readers leave analysis/true_revenue/.
from analysis.description_text import _TRANSFER_WORDING
from analysis.descriptor.credit_words import (
    CUSTOMER_FINANCING_LUMP_FLOOR,
    CUSTOMER_FINANCING_LUMP_ROUND,
    CUSTOMER_FINANCING_LUMP_SHARE,
    CUSTOMER_FINANCING_SERIES_MIN,
    CUSTOMER_FINANCING_SERIES_SHARE,
)
from analysis.descriptor.holder import _summary_grid_header, account_product, holder_receiver_block
from analysis.descriptor.lexical import (
    _is_payer_word,
    bank_by_form,
    company_form_outside_address,
    is_round_sum,
    originator_address,
)
from analysis.descriptor.payer import (
    _is_transfer_or_p2p_row,
    credit_transfer_wording,
    payer_label_layout,
    relayed_customer_text,
    wire_relayed_customer,
)
from analysis.descriptor.rails import _loose_wire_originator
from analysis.descriptor.words import (
    BANK_SETTLEMENT_ORIGINATOR,
    HOLDER_NOISE,
    _ACH_ORIGINATOR_FIELD,
    _BANK_COMPANY_FORM,
    _BOFA_ENTRY_FIELD,
    _BRANCH_DEPOSIT_TRANSIT,
    _CHASE_ENTRY_FIELD,
    _CREDIT_WIRE_BENEFICIARY_VALUE,
    _GLUED_SEC_CODE,
    _HOLDER_TEST_NOISE,
    _HOLDER_TRADE_NAME,
    _INTERNAL_ACCOUNT_SOURCE_WORDS,
    _MEMO_ENTRY_FIELD,
    _NUMBERED_PROVINCE_START,
    _OWN_ACCOUNT_PRODUCT_WORDS,
    _PROVINCE,
    _REVENUE_TEMPLATE_PREFIX,
    _SENDER_END,
    _WIRE_FIELD_END,
    _WIRE_SENDER_AFTER_LABEL,
    _WIRE_SENDER_AFTER_LABEL_END,
)

if TYPE_CHECKING:
    from analysis.schema import Statement


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

#: Bump when a stored classification, tier, reason or review-gate reading changes: an analysis saved under an
#: older value gets the re-analyze notice. Compared as numbers (5.10 is newer than 5.9). Bump
#: `webapp.artifact_cache.ANALYSIS_STAGE_VERSION` in the same commit.
CLASSIFICATION_VERSION = "5.9"

#: The entity of an unknown obligation whose descriptor names no organisation (D11).
UNIDENTIFIED_LENDER_OBLIGATION = "Unidentified lender obligation"

#: The fixed D10 name of an MCA SERVICING payee. The two words print for two unrelated funders, so no D11 name
#: is ever built from them.
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
    #: The statement's holder name (Statement.holder_name); the holder tests read
    #: holder_reading(account_name, holder_name).
    holder_name: str | None = None
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
    # True revenue spec §6.2, §9.1, §11: a confirmed funder's payment the bank returned unpaid. On the DEBIT, the
    # return credit's location: the row leaves paid to lenders (contributes_to_lender_totals) and stays in the
    # withholding rate and the lender count. On the CREDIT, the debit's location; its revenue reading is untouched.
    # None on every other row.
    returned_funder_payment_by: str | None = None
    returns_funder_payment: str | None = None
    # True revenue spec §6.2 pass 7c, §11: on a returned funder payment's DEBIT, the location of the same funder's
    # re-debit that re-presented it or caught it up 2x; the debit then leaves the withholding rate
    # (contributes_to_withholding_rate False), the re-debit counting the obligation once. None on every other row.
    represented_by: str | None = None
    # True revenue spec §9.1, §11: on a confirmed funder's paid debit whose own text prints a payoff word (PAYOFF, PAY
    # OFF, PAY-OFF, PREPAY, PRE-PAY, PREPAYMENT, BUYOUT, BUY OUT, PAYOUT; LUMP_SUM_PAYOFF_WORDS), the word as the bank
    # printed it; the debit is a lump sum out of the withholding rate (contributes_to_withholding_rate False), still in
    # paid to lenders and the lender count. None on every other row, a returned one included (Q5 keeps it in the rate).
    lump_sum_payoff: str | None = None
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
    # The Potential Lenders line of an unnamed potential payee, one per payee key within the statement
    # ('Unidentified lender obligation (weekly, 450.00)'). None for every other row, whose line is its
    # canonical_entity.
    potential_payee_label: str | None = None
    # True revenue spec §9.1: on every potential_lender row, named or not, its payee's amount-free key (an opaque
    # digest of the entity, D6's payee words and the masked recipient: no payee word is published), which
    # analysis.lender_payment_changes reads to follow a payee across an amount change; nothing else reads it. None for
    # every other row.
    potential_payee_key: str | None = None
    # True revenue spec §5.4: the per-row contract. Every posted credit carries exactly one tier (verified,
    # counted_flagged, excluded_pending_review, non_revenue); a counted or held row carries its reason code
    # (analysis.revenue.REVENUE_TIER_REASONS). The initial tier is the one the rules gave, which a reset restores.
    revenue_tier: str | None = None
    revenue_initial_tier: str | None = None
    revenue_tier_reason: str | None = None
    contributes_to_counted_flagged: bool = False
    contributes_to_excluded_pending_review: bool = False
    # True revenue spec §5.4, §8.5: on a held wire with no sender printed (`wire_no_sender`), each Lenders or
    # Potential Lenders series that starts after it (pass 7's last step, analysis.true_revenue.funding_series_after);
    # () on every other row. A review aid: no tier, state, flag, figure or gate reads it. Serialized as a list of
    # objects.
    revenue_funding_series: tuple[FundingSeries, ...] = ()

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


#: The flag group of an insurance row whose insurer is a premium-finance payee
#: (C1: the one flag group that is not a classification state).
_PREMIUM_FINANCING_GROUP = "premium_financing"


def _insurance_registry_match(text: str, *, glued_digits: bool = False) -> tuple[str, str, bool] | None:
    """Spec §4.3 step 4: the insurer of an insurance row, as (entity, alias, premium_finance).

    Premium-finance payees (`PREMIUM_FINANCE_ALIASES`, spec §4.2) are consulted
    first, so a premium financier whose name contains an insurer's name is still
    the premium financier. With `glued_digits` (a credit), the premium-finance
    lookup also reads a one-word alias with a digit run glued after it ('IPFS888',
    'IPFSFLP12'), so every spelling of a premium financier's credit takes the one
    insurance treatment; a debit keeps today's reading.
    """
    premium = registry_match(text, PREMIUM_FINANCE_ALIASES, glued_digits=glued_digits)
    if premium is not None:
        return premium[0], premium[1], True
    insurer = registry_match(text, INSURANCE_PROVIDER_ALIASES)
    if insurer is not None:
        return insurer[0], insurer[1], False
    return None


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
    # A returned item in the banks' abbreviated and French wording: TD's stop-payment return of the business's own
    # debit, and the French returned-item charge. A deposited item returned under a stop payment is a reversal
    # (_REFUND_REVERSAL_PATTERNS), as RETURNED DEPOSIT is.
    re.compile(r"\bRTN STOP PAY(?:T|MT|MENT)?\b|(?<!\bITEM )\bRETURNED STOP PAY(?:T|MT|MENT)?\b"),
    re.compile(r"\bEFFETS? (?:RET|RETOUR|RETOURNES?)\b"),
)
#: A returned or unpaid item's charge printed with CHARGE/CHG rather than FEE, read with _NSF_PATTERNS on a DEBIT only
#: (a credit keeps today's reading), so a charge that prints the item's payee is never that payee's payment. A bare
#: 'UNPAID ITEM <payee>' may be the payee's own debit and is not read.
_DEBIT_ITEM_CHARGE_NSF_PATTERNS = (
    re.compile(r"\b(?:RETURNED|RETURN) ITEM (?:CHARGES?|CHGS?)\b"),
    re.compile(r"\bUNPAID ITEM (?:CHARGES?|CHGS?)\b"),
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
    # The bank's overdraft charge for an item is a fee, even when it prints the
    # item's payee (step 6 runs before the known payee).
    re.compile(r"\bOVERDRAFT CHARGES?\b"),
    # Bank charges printed without FEE: the SVC/SERV/CHG abbreviations, charges whose CHARGE is not next to
    # SERVICE/MONTHLY/OVERDRAFT/PROCESSING, RBC's Interac service-charge code SC, the ATM withdrawal service
    # charge, and the French FRAIS, never beside French loan or line-of-credit words. A bare CHARGE or CHG is
    # never a fee word (Capital One prints 'CHARGE <merchant>').
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
#: The bank's stop-payment and OD item charges printed without FEE, read with _FEE_PATTERNS on a DEBIT only (a credit
#: keeps today's reading). A stop word is a bank instruction, never a payment, so a bare stop-payment row is a charge
#: too; it is read only at the row's start, so a payee whose name holds STOP is never read.
_DEBIT_BANK_CHARGE_FEE_PATTERNS = (
    re.compile(r"\bSTOP (?:PAY(?:MENT|MT|T)?|PMT)(?: (?:REQUEST|REQ|ORDER))? (?:CHARGES?|CHGS?)\b"),
    re.compile(r"\bOD ITEM (?:CHARGES?|CHGS?)\b"),
    re.compile(r"^(?:ACH )?STOP (?:PAY(?:MENT|MT|T)?|PMT)\b"),
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
    # Navy Federal's memo for a recurring card payment.
    re.compile(r"\bCREDIT CARD RECUR(?:RING)?\b"),
)
#: A fintech transfer between the holder's own accounts takes no step-8 rule,
#: whatever the holder named the sub-account.
_OWN_ACCOUNT_TRANSFER_GUARD = re.compile(r"^TRANSFER (?:TO|FROM) .+ (?:ACCOUNT )?TRANSFER (?:OUT|IN)$")
#: A per-vehicle floor-plan payoff.
_FLOOR_PLAN_PAYOFF_PATTERN = re.compile(r"^PAYOFF (?:19|20)\d\d .*\bVIN\b")
#: A home-equity loan is a second mortgage. It has no leading word boundary, so a
#: run-together payee nickname matches too.
_MORTGAGE_PATTERNS = (
    re.compile(r"\bMORTGAGES?\b"),
    re.compile(r"HOME ?EQUITY ?LOANS?\b"),
    # The mortgage payment abbreviations (MTG PYMT, MTGE PAYMENT).
    re.compile(r"\bMTGE? (?:PYMTS?|PMTS?|PAYMENTS?)\b"),
)
#: "AUTO PAYMENT" is a bank's autopay wording, not a car payment, so AUTO needs
#: loan, lease or finance wording while VEHICLE may carry PAYMENT.
_VEHICLE_FINANCING_PATTERNS = (
    re.compile(r"\b(?:AUTO|CAR) (?:LOAN|LOANS|LEASE|FINANCE|FINANCING)\b"),
    re.compile(r"\bVEHICLE (?:LOAN|LEASE|PAYMENT|PMT|PYMT|FINANCE|FINANCING)\b"),
)
#: An unnamed student-loan payee.
_STUDENT_LOAN_PATTERNS = (
    re.compile(r"\bSTUDENT ?LOANS?\b"),
    re.compile(r"\bSTDNT ?LOANS?\b"),
    re.compile(r"\bSTUDNT ?LOANS?\b"),
    re.compile(r"\bSTUDENT LN\b"),
)
#: D5 loan wording for the bank-name rule. French PRET is loan wording too.
_LOAN_WORD_PATTERNS = (re.compile(r"\bLOANS?\b"), re.compile(r"\bPRETS?\b"))
#: D5: a transfer to the statement bank's own loan account.
_OWN_LOAN_TRANSFER_PATTERNS = (
    re.compile(r"\b(?:TRANSFER|TFR) TO (?:MY |YOUR )?LOANS?\b"),
    re.compile(r"\bLOAN (?:TRANSFER|TFR)\b"),
)
#: D5. Another bank's loan whose originator is only a
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
#: wording. Synchrony's PAYMNT, and a payment word glued to the SEC label in Chase's
#: field layout, are payment wording too.
_CARD_PAYMENT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:CREDIT CARD|CREDITCARD|CRCARD|CRD|CARD|CARDMEMBER)\b"),
    re.compile(
        r"\b(?:AUTOPAY|AUTO PAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)\b"
        r"|\b(?:AUTOPAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT|PAYMNT)SEC\b"
    ),
)
#: D4: equipment financing with no named company.
_EQUIPMENT_FINANCING_PATTERNS = (re.compile(r"\bEQUIPMENT (?:FINANCING|FINANCE)\b"),)
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
#: D10: a loan servicer or debt collector whose funder is not in a registry. (A servicer whose funder
#: is known is an alias of that funder in the registry, via the C10 ledger.) MCA SERVICING
#: stays out of every alias table. The MCA SERVICING words, named by the
#: fixed UNIDENTIFIED_MCA_SERVICER label (D10).
_MCA_SERVICING_PATTERN = re.compile(r"\bMCA SERVICING\b")
_SERVICER_COLLECTOR_PATTERNS = (
    re.compile(r"\bSERVICER\b"),
    re.compile(r"\bLOAN SERVICING\b"),
    re.compile(r"\bMCA SERVICING\b"),
    re.compile(r"\bDEBT (?:COLLECTION|COLLECTIONS|COLLECTOR|COLLECTORS)\b"),
    re.compile(r"\bCOLLECTION AGENCY\b"),
)
#: D5, loan-payment wording (normalization reads PAYMT as PAYMENT, and LN as LOAN except where LN ends a
#: street address with no loan-product word before it and no payment word after it, 5.5 §7.11: 'CML LN PAYMT'
#: reads LOAN PAYMENT) ...
_UNNAMED_LOAN_PAYMENT_PATTERNS = (
    re.compile(r"\bLOANS? (?:PAYMENT|PAYMENTS|PYMT|PMT|REPAYMENT)\b"),
    # The statement bank's own loan interest, with no payee printed.
    re.compile(r"\bLOAN INTEREST\b"),
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
#: PAYROLL glued to an ACH entry-description suffix (a closed list, so a receiver name that only contains PAYROLL
#: is not read), payroll providers seen in the corpus, benefit administrators and retirement-plan recordkeepers,
#: and the French pay words. Provider, administrator and French words are read on the originator segment only
#: (_originator_segment): a holder named like one of them in INDN or IND NAME never hides its lender. No new
#: pattern fires on a row that names financing. 401(k) is left out (it prints in holder names).
_PAYROLL_GLUED_PATTERN = re.compile(r"\bPAYROLL(?:TAX(?:ES)?|TX|TS|DDS?|DEP|FEES?)\b")
_PAYROLL_PROVIDER_PATTERNS = (
    re.compile(r"\b(?:PATRIOT SOFTWARE|DATAPAY|PAYCOR|ONPAY|PAYWORKS|PAYCOM|PAYLOCITY)\b"),
    re.compile(r"\b(?:HEALTH ?EQUI(?:TY)?|WAGEWORKS|TASC|ASCENSUS|HUMAN INTEREST|GUIDELINE RETIRE(?:MENT)?)\b"),
    re.compile(r"\bPAIE\b|\bSALAIRES?\b"),
)
#: A loan from the business's own shareholder, owner or director, repaid to them: no lender is named. The loan
#: producers never take it (debits only, and only when the row names no organisation). MEMBER and PARTNER are
#: left out: a funder can be named '... Partners'.
_RELATED_PARTY_LOAN_PATTERNS = (
    re.compile(r"\b(?:SHAREHOLDERS?|OWNERS?|DIRECTORS?) LOANS?\b"),
    re.compile(r"\bDUE TO (?:SHAREHOLDERS?|OWNERS?)\b"),
)
#: §6.3: the two layouts that print a named sender after an own-account designation, and the sender's words: Bank of
#: America's 'ONLINE|MOBILE [BANKING] TRANSFER FROM CHK|SAV <n> CONFIRMATION <reference> <sender>' (its own-account
#: form prints only the reference, ten digits) and a credit union's 'TFR FROM X...<n> TRANSFER DEPOSIT <sender>'.
#: Navy Federal's 'TRANSFER FROM SHARES|CHECKING <name>' is neither: its holder test is blind, so it stays the
#: holder's own transfer.
_NAMED_DESIGNATION_TRANSFERS = (
    re.compile(r"\b(?:ONLINE|MOBILE) (?:BANKING )?TRANSFER FROM (?:CHK|SAV) \d+ CONFIRMATION \S+ (?P<sender>\S.*)$"),
    re.compile(r"\bTFR FROM X+\d* TRANSFER DEPOSIT (?P<sender>\S.*)$"),
)
#: The own-account patterns a named sender after the designation refuses.
_NAMED_DESIGNATION_PATTERNS = (_TRANSFER_FROM_ACCOUNT, _CHANNEL_TRANSFER_FROM_ACCOUNT, _TFR_TRANSFER_DEPOSIT)
#: The posting words a bank prints before the Canada Revenue Agency's refund, read after the revenue text and the
#: template prefixes are stripped: a glued or spaced date, Canada's GC (Government of Canada) and the direct-deposit,
#: EFT and payment words ('0102DIRECT DEPOSIT CANADA RIT', 'GC DIRECT DEPOSIT CANADA RIT', 'PAYMENT FROM CANADA RIT').
#: Each number ends at a space or a letter, so no number splits two ways.
_CRA_POSTING_PREFIX = re.compile(
    r"^(?:\d+(?: |(?=[A-Z])))*(?:(?:GC|DIRECT DEPOSIT|DIRECT DEP|DEPOSIT|DEP|ELECTRONIC DEPOSIT"
    r"|EFT(?: CREDIT| DEPOSIT)?|MISC PAYMENT|PAY(?:MENT)?(?: FROM)?) (?:\d+(?: |(?=[A-Z])))*)*"
)
_CRA_REFUND_PAYER = re.compile(r"CANADA (?:RIT|RIF)\b")
#: A business's GST/HST refund, the Canada Revenue Agency's ('CANADA GST TPS', 'GST CANADA') and Revenu Quebec's ('RQ
#: GST'). The form is the whole payer after the posting words, with only a posting code or a reference after it ('...
#: MSP DIV', '... 12345678'), so GST inside a name ('GST CANADA LOGISTICS INC', 'NORTHWIND GST SERVICES') is never a
#: refund. The CRA's name after the form ('CANADA GST TPS CANADA'), a country code ('GST CANADA CA') and the GST
#: program account ('... RT0001') too.
_GST_REFUND_PAYER = re.compile(
    r"(?:CANADA GST(?: TPS)?(?: CANADA)?|GST(?: TPS)? CANADA(?: CA)?|RQ GST)(?: (?:MSP|DIV|RT\d{4}|\d+))*"
)


def government_form_payer(text: str) -> str:
    """The payer a government's form is read on as the whole payer: the revenue text with the bank's template prefixes
    (_strip_revenue_template) and the posting words a bank prints before a government's form (_CRA_POSTING_PREFIX: a
    glued or spaced date, GC, DIRECT DEPOSIT, EFT, MISC PAYMENT, PAYMENT FROM ...) removed."""
    return _CRA_POSTING_PREFIX.sub("", _strip_revenue_template(revenue_text(text)), count=1).strip()


def _canada_tax_refund(text: str) -> bool:
    """The refund's form starts the payer, after the posting words only; a payer that names Canada's form after
    its own name is that payer ('FABRIKAM LIFE CANADA RIF PMT'). GOV: or the GST/HST refund form is the whole
    payer (_GST_REFUND_PAYER)."""
    payer = government_form_payer(text)
    return _CRA_REFUND_PAYER.match(payer) is not None or _GST_REFUND_PAYER.fullmatch(payer) is not None


class _CanadaTaxRefundForm:
    """The refund reader in the strong non-revenue list, read as its patterns are (search)."""

    pattern = "CANADA (?:RIT|RIF) after the posting words, or the whole payer a GST/HST refund form"

    def search(self, text: str) -> "_CanadaTaxRefundForm | None":
        return self if _canada_tax_refund(text) else None


_IRS_BENEFIT_ENTRY = re.compile(r"(?<![A-Z])(?:CHI?LD ?CTC|TAX ?EIP ?\d?)\b")
#: And the IRS's interest entry, the interest it pays on a refund it paid late ('IRS TREAS 310 DES:INT'), interest and
#: no sale (§8.1, standard G5), never an IRS vendor payment's word.
_IRS_REFUND_WORDING = re.compile(r"(?<![A-Z])(?:TAX ?REF\w*|TAX ?EIC|[A-Z]*REFUNDS?|RFND|REFND|RFD|INT|INTEREST)\b")
_IRS_LAYOUT_WORDS = frozenset("ORIG CO NAME ID DESC DATE ENTRY DESCR SEC CCD CTX PPD WEB TRACE EED IND TRN DES".split())


def _irs_tax_refund(text: str) -> bool:
    """A credit the IRS issues through the Treasury is a tax refund when its entry is a refund's wording or it prints
    no entry at all ('ELECTRONIC DEPOSIT FROM IRS TREAS 310', 'ACH CREDIT IRS TREAS 310 <reference>'). Treasury's
    Green Book gives MISC PAY to federal vendor payments, and the IRS pays its contractors that way, so an entry such
    as MISC PAY, VENDOR or VENDOR PAY keeps the row's own reading. The entry is the DES or CO ENTRY DESCR field
    (entry_fields), or on a layout with no field the words printed after the form, references and field labels left
    out. An interest entry (INT, INTEREST), the interest on a refund, is no revenue either."""
    row = _before_receiver(text)
    found = IRS_TREASURY_FORM.search(row)
    if found is None or _IRS_BENEFIT_ENTRY.search(text):
        return False
    entry = entry_fields(text) or " ".join(
        word for word in row[found.end():].split() if not _is_reference_token(word) and word not in _IRS_LAYOUT_WORDS
    )
    return not entry.strip() or _IRS_REFUND_WORDING.search(entry) is not None


class _IrsTaxRefundForm:
    """The IRS refund reader in the strong non-revenue list, read as its patterns are (search)."""

    pattern = "IRS TREAS nnn with no entry or a refund- or interest-worded entry"

    def search(self, text: str) -> "_IrsTaxRefundForm | None":
        return self if _irs_tax_refund(text) else None


#: Spec §6.1 step 3a: the seven government payments the owner excluded when the row prints no purpose, each named by its
#: key (the step's matched_alias), in the order the reader tests them. The VA's Treasury form is read with agency code
#: 36 only (a blank, 12, USDA, VACP, DOD or SSA code and the letter form VA are other agencies' or unruled); WORK COMP
#: BOARD without WSIB is another board. The six letter-led forms take the left boundary (?<![A-Z]), so a digit run glued
#: before a form's first letter ('0102GOUV QUEBEC MSP', a glued date) is a reference the rest-of-row test reads
#: (_is_reference_token), as _CRA_POSTING_PREFIX reads a glued lead for the GST form; the VA's form keeps (?<![A-Z0-9])
#: (a digit glued before its agency code makes the code unreadable).
GOVERNMENT_NO_PURPOSE_FORMS = (
    ("mn_mmb", re.compile(r"(?<![A-Z])MN STATE MMB\b")),
    ("va_treasury", re.compile(r"(?<![A-Z0-9])36 TREAS ?\d{3}\b")),
    ("wi_dcf", re.compile(r"(?<![A-Z])WI ?DCF\b")),
    ("bc_provincial", re.compile(r"(?<![A-Z])(?:PROVINCIAL PAYMENT )?PROVINCE OF (?:BC|BRITISH COLUMBIA)\b")),
    ("ontario_wsib", re.compile(r"(?<![A-Z])(?:(?:WORK COMP BOARD )?WSIB|WORKPLACE SAFETY AND INSURANCE BOARD)\b")),
    ("quebec_government", re.compile(r"(?<![A-Z])GOUV(?:ERNEMENT)?(?: DU)? QUEBEC\b")),
    ("nd_workforce_safety", re.compile(
        r"(?<![A-Z])(?:ND |NORTH DAKOTA )?WORKFORCE SAFETY(?: AND INS(?:URANCE)?| INS(?:URANCE)?)?\b")),
)
#: Q12: the ACH field labels read past (Chase's and Bank of America's), and the only words a no-purpose row may print
#: besides its form and its references: posting words, SEC codes, the X12 envelope's segment names and the no-purpose
#: entries (MISC PAY, PAYMENT, PMT, DD, WIDCF, EME, MSP, DIV). Keep the set to these: a name, funding or purpose word
#: here would let step 3a pre-empt a lender's D1 reading or swallow a purpose.
_GOVERNMENT_NO_PURPOSE_LAYOUT = re.compile(r"\b(?:ORIG CO NAME|ORIG ID|DESC DATE|CO ENTRY DESCR|CO ID|IND ID|IND NAME)\b")
_GOVERNMENT_NO_PURPOSE_WORDS = frozenset(
    "ELECTRONIC DEPOSIT FROM DESCRIPTIVE ACH CREDIT DIRECT DEP EFT GC PREAUTHORIZED MISC PAY PAYMENT PAYMENTS PMT DD "
    "WIDCF EME MSP DIV DES ID SEC CCD CTX PPD WEB TRACE EED TRN ISA IEA GS GE ST SE".split()
)
#: Q12: a masked prefix followed by letters is an entry, not a reference: the VA's XXVA CH33, CH31, BENEF and EDU
#: print a purpose. A mask with digits (XXXXX1234) and an all-X mask (XXXXXX) stay references.
_GOVERNMENT_NO_PURPOSE_MASKED_ENTRY = re.compile(r"X{2,}[A-WYZ][A-Z]*")


def government_no_purpose(text: str) -> str | None:
    """Spec §6.1 step 3a: the key of the government form a credit prints when the row prints no purpose
    (GOVERNMENT_NO_PURPOSE_FORMS), else None. `text` is the revenue text.

    The row is read with each receiver field's value removed and every field after it kept (_without_receiver_value),
    so Bank of America's PMT INFO addenda, printed after INDN ... CO ID ... CCD, stays in the row and an invoice there is
    a purpose. American Express's incoming-ACH template (_AMEX_ACH_CREDIT) is read from its originator up to its id, as
    _before_receiver ends it, never its EXTERNAL, sending-bank and trace trailer; its label is the template's own words
    whatever the originator's first word. The template prefixes and the ACH field labels are read past. Besides the
    form, the row may print only _GOVERNMENT_NO_PURPOSE_WORDS and references (_is_reference_token: a digit, a mask, a
    month; a masked prefix followed by letters is an entry word). The first form found decides: any other word leaves
    the row to the later steps, with no fall-through to another form."""
    amex = _AMEX_ACH_CREDIT.match(text)
    base = text[amex.start("payer"): amex.end("id")] if amex is not None else _without_receiver_value(text)
    row = _GOVERNMENT_NO_PURPOSE_LAYOUT.sub(" ", _strip_revenue_template(base))
    for name, form in GOVERNMENT_NO_PURPOSE_FORMS:
        found = form.search(row)
        if found is None:
            continue
        rest = (row[: found.start()] + " " + row[found.end():]).split()
        no_purpose = all(
            word in _GOVERNMENT_NO_PURPOSE_WORDS
            or (_is_reference_token(word) and _GOVERNMENT_NO_PURPOSE_MASKED_ENTRY.fullmatch(word) is None)
            for word in rest
        )
        return name if no_purpose else None
    return None


#: American Express's Membership Rewards redemption, read only beside a card issuer's name (American Express, Amex, or
#: a card issuer's context alias), so a payer whose entry happens to print MR REDEEM keeps its reading.
_CARD_REWARD_PROGRAM = re.compile(r"\b(?:MR REDEEM|MEMBERSHIP REWARDS?)\b")
_CARD_ISSUER_NAME = re.compile(r"(?<![A-Z])(?:AMERICAN EXPRESS|AMEX)\b")


class _CardIssuerRewardRedemption:
    """A card issuer's rewards redemption in the strong non-revenue list, read as its patterns are (search)."""

    pattern = "MR REDEEM or MEMBERSHIP REWARDS beside a card issuer's name"

    def search(self, text: str) -> "_CardIssuerRewardRedemption | None":
        if _CARD_REWARD_PROGRAM.search(text) is None:
            return None
        if _CARD_ISSUER_NAME.search(text) or registry_match(text, CARD_ISSUER_CONTEXT_ALIASES) is not None:
            return self
        return None


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
    *_OWN_ACCOUNT_SWEEP_CREDIT_PATTERNS,
    re.compile(r"\bOWNER(?:S)? (?:CONTRIBUTION|CAPITAL|DEPOSIT|TRANSFER)\b"),
    re.compile(r"\bSHAREHOLDER (?:CONTRIBUTION|LOAN|DEPOSIT)\b"),
    re.compile(r"\bCAPITAL CONTRIBUTION\b"),
    re.compile(r"\bINSURANCE (?:PROCEEDS|CLAIM|PAYMENT)\b"),
    re.compile(r"\bTAX REFUND\b"),
    # §7.11: the tax-refund abbreviations (Treasury's TAX REF) and account-verification micro-deposits.
    re.compile(r"\bTAX ?REF(?:UND)?S?\b|[A-Z]*TAXRFD\b|\bTAX RFD\b|\bTAXEIC\b"),
    # The Canada Revenue Agency's income-tax refund direct deposit (RIT and RIF are the banks' two labels of one refund,
    # 'DIRECT DEPOSIT CANADA RIT RIF'). The form starts the payer (_CanadaTaxRefundForm). GOV: and a business's GST/HST
    # refund is the whole payer; the CRA's benefit forms are personal income, held by the true-revenue pass (class B),
    # never non_revenue.
    _CanadaTaxRefundForm(),
    # GOV: a payment the IRS issues through the Treasury ('IRS TREAS 310') with no entry or a refund-worded one is a
    # tax refund; an IRS vendor payment (MISC PAY, VENDOR PAY) keeps its reading, and the child tax credit and the
    # stimulus are personal benefits (class B) (_IrsTaxRefundForm).
    _IrsTaxRefundForm(),
    re.compile(r"\bACCT ?VERIFY\w*\b|\bMICRO ?DEPOSITS?\b|\bPENNY TEST\b|\bTRIAL DEPOSITS?\b"),
    re.compile(r"\b(?:IRS|CRA|REVENUE AGENCY) REFUND\b"),
    re.compile(
        r"\b(?:CASH ?BACK|CASH ?REWARDS?|CARD REWARDS?|CREDIT CARD REWARDS?)"
        r"(?: CREDIT|REDEMPTION|REBATE)?\b"
    ),
    # Card-rewards redemptions the patterns above miss, each anchored so a payer named REDEMPTION ... is never read:
    # Chase's payer-less CASH REDEMPTION as the whole row (a reference after it), PNC's PURCHASE PAYBACK [AWARD], a
    # POINTS REDEMPTION, and a card issuer's MR REDEEM or MEMBERSHIP REWARDS.
    re.compile(r"^(?:\d{1,2} \d{1,2} )?CASH REDEMPTION(?: \S*\d\S*)*$"),
    re.compile(r"\bPURCHASE PAYBACK(?: AWARD)?\b"),
    re.compile(r"\bPOINTS REDEMPTION\b"),
    _CardIssuerRewardRedemption(),
    re.compile(r"\bINTEREST (?:CREDIT(?:ED)?|PAID|PAYMENT|DEPOSIT|EARNED)\b"),
    re.compile(r"\bCREDIT INTEREST\b"),
    # The French interest credit (_FRENCH_INTEREST_CREDIT).
    _FRENCH_INTEREST_CREDIT,
    re.compile(r"\b(?:BANK |SERVICE |ACCOUNT )?FEES? (?:REFUND|REBATE|REVERSAL|CREDIT)\b"),
    # The French fee rebate (RABAIS SUR LES FRAIS MENSUELS), as FEE REBATE reads. Copied in tools/revenue_census.py.
    re.compile(r"(?<![A-Z])RABAIS (?:SUR )?(?:LES )?FRAIS\b"),
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
    # §7.7: the NACHA claim-payment entry, glued on either side (Chase's SEC, a sixteen-character name or
    # digits on the left); its unbounded branch takes only the full token, so THECLAIMPMT stays unmatched.
    re.compile(r"(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"),
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


# ---------------------------------------------------------------------------------------------------------------------
# True revenue spec §5.2, §6.1, §7: the credit revenue
# readers. Every credit revenue rule reads revenue_text(text); D11, normalized_description and every debit rule keep
# the normalized row as it is.
# ---------------------------------------------------------------------------------------------------------------------

#: T18 (OQ5): a credit that prints the NACHA claim-payment entry skips the insurer registry, so an insurer's healthcare
#: claim payment to a provider verifies. Off, it is held with the insurer's other credits.
HCCLAIMPMT_CLAIM_FIRST = True
#: §5.2, §8.1: the numbered-company form the counter-debit holds key a numbered company by: six to ten digits (no
#: digit before them) and then a province or territory (or a cut of one) or BMO's code tail that is no name's first
#: word (_PROVINCE_NOT_A_NAME_START), or Quebec's NNNN NNNN before QUEBEC (or its cut, or QC), then any legal forms,
#: BMO codes and tail words (_BMO_CODE_TAIL, _NUMBERED_TAIL_WORDS). Its number is `number`, or Quebec's two groups
#: joined (_numbered_form_number). Never any digits alone: a cheque, confirmation or payment number before a name
#: word ('CHEQUE 1234567', 'BILL PAYMENT 1234567 NORTHWIND SUPPLY INC', 'MISC PAYMENT 123456 NORTH MOUNTAIN PAVING')
#: is none.
_NUMBERED_FORM = re.compile(
    rf"(?<![0-9])(?:(?P<number>\d{{6,10}}) {_PROVINCE_NOT_A_NAME_START}"
    rf"|(?P<first>\d{{4}}) (?P<second>\d{{4}}) {_QUEBEC}\b)"
    rf"(?: (?:{_BMO_CODE_TAIL}|{_NUMBERED_TAIL_WORDS})\b)*"
)
#: §7.11: a claim or provider signal. REIMBURSEMENT on such a row is a provider's claim payment, not a refund.
_CLAIM_OR_PROVIDER_SIGNAL = re.compile(
    r"\b(?:MEDICAID|MEDICARE|MEDI CAL|TRICARE|CHAMPVA|GEMT|EMS|PROV(?:IDER)? ?PAY(?:MENTS?)?|EDI PYMNTS|CLAIM PMT)\b"
    r"|(?:\bH[CE]?|HC)CLAIMPMT(?:SEC)?\b"
)
_REIMBURSEMENT_WORD = re.compile(r"\bREIMBURSEMENT\b")
#: §7.11: the Quebec health insurance board (the Régie de l'assurance maladie du Québec, a public body that pays health
#: professionals and clinics for the insured services they bill; ramq.gouv.qc.ca), the French rows' provider signal:
#: REMBOURSEMENT on such a row is the clinic's claim payment, as REIMBURSEMENT is beside a claim or provider signal
#: (_CLAIM_OR_PROVIDER_SIGNAL).
_QUEBEC_HEALTH_PAYER = re.compile(r"(?<![A-Z])(?:RAMQ|REGIE (?:DE L )?ASSURANCE MALADIE(?: DU QUEBEC)?)\b")
#: §7.11: push payouts printed as card credits: a push-rail word, or a processor or invoice source with a payout word.
#: The card-credit labels include Citibank's cut DEBIT CARD CREDI and the card-shaped refund labels step 3 adds
#: (_CARD_REFUND_LABELS).
_CARD_CREDIT_LABEL = re.compile(
    r"\b(?:DEBIT CARD CREDIT?|POS CREDIT)\b|^(?:\d{1,2} \d{1,2} )?CHECKCARD \d{4}\b|\bPOINT OF SALE DEPOSIT\b"
)
#: §7.11: Cash App and Apple Cash pushes printed as a DEBIT CARD CREDIT or POS CREDIT join the push words (released from
#: the reversal rule, then held by §8.1 as any released card credit is) only with CASH_APP_CARD_PUSH_RELEASE on. It
#: stays off by the owner's card-push ruling; switched on, it would only hold a few rows and move no True. A card
#: credit printed first ('CARD CREDIT CASH APP ...') stays a counted person-to-person push either way
#: (true_revenue._leading_card_credit).
CASH_APP_CARD_PUSH_RELEASE = False
_CARD_CREDIT_P2P_PUSH_WORD = re.compile(r"(?<![A-Z])(?:CASH ?APP|APPLE CASH)\b")
_CARD_CREDIT_PAYOUT_WORD = re.compile(r"\b(?:PAYOUTS?|INSTANT (?:PAYOUT|PAY|TRANSFER)|SETTLEMENT|DEPOSIT)\b")
_SQUARE_CAPITAL_CREDIT = re.compile(r"\bSQ ?CAP\d*\b")
_SQUARE_NAME = re.compile(r"\bSQ\b|\bSQUARE\b")
_SBA_DISBURSEMENT_CREDIT = re.compile(r"\bSBAD TREAS\b|\bSBA (?:EIDL|LOAN|DISB\w*)\b|\bEIDL\b")
#: A3: the Small Business Administration's name cut to
#: an originator field, read on the payer region alone: exactly SMALL BUSINESS, or SMALL BUSINESS and a leading cut of
#: ADMINISTRATION (A, AD, ADM ... ADMIN ... ADMINISTRATION), a U S prefix allowed. A payer whose name goes on in other
#: words (SMALL BUSINESS SOLUTIONS LLC) is a named payer.
_SBA_CUT_ORIGINATOR = re.compile(
    r"^(?:U ?S )?SMALL BUSINESS(?: (?:"
    + "|".join("ADMINISTRATION"[:length] for length in range(len("ADMINISTRATION"), 0, -1))
    + r"))?$"
)
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
#: §7.7: inside the credit decision, the financing, potential-lender and insurer lookups read a glued HCCLAIMPMT
#: split from the name before it, so a sixteen-character funder name glued to the token is still found.
_GLUED_CLAIM_ENTRY = re.compile(r"(?<=[A-Z0-9])(H[CE]?CLAIMPMT)")
_BLUE_PLAN_CLAIM_PAYER = re.compile("|".join(BLUE_PLAN_CLAIM_PAYERS))
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
_PUBLIC_PAYER_PURPOSE = re.compile(
    r"\bVEN(?:DOR)? ?(?:PAY(?:MENTS?)?|P(?:Y)?MTS?)(?:SEC)?\b|\bPROV(?:IDER)? ?PAY(?:MENTS?)?(?:SEC)?\b"
    r"|\bEDI ?(?:PYMNTS|PAYMENTS?|PMTS?)(?:SEC)?\b"
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
#: §7.9: the channel and bank fields removed before the financing roots are read on a wire. And U.S. Bank's 'WIRE
#: CREDIT REF<n>' and the '<INCOMING|DOMESTIC|INTL|INTERNATIONAL|FOREIGN> WIRE CREDIT' labels, whose CREDIT is the
#: channel's word, never a lender's name (removed from the veto's text only: the row keeps its label and reads as a
#: wire). And R21 part C's plural label ('WIRE TRANSFERS CREDIT <sender>'), whose CREDIT is the channel's word as the
#: singular's is, now that the sender after it is read.
_WIRE_CHANNEL_AND_BANK_FIELDS = re.compile(
    r"^(?:WIRE CREDIT REF ?\d+|(?:INCOMING|DOMESTIC|INTL|INTERNATIONAL|FOREIGN) WIRE CREDIT)\b|"
    r"^(?:WIRE TYPE \S+ IN|USD WIRE IN|[A-Z]{3} WIRE IN|FEDWIRE CREDIT|CHIPS CREDIT|WT FED|WIRE TSF"
    r"|WIRE TRANSFER \S+|WIRE TRANSFERS (?:DEPOSIT|CREDIT|IN|INCOMING|FROM)"
    r"|INCOMING WIRE|WIRE IN|WIRE FROM|(?:DOMESTIC|INTL|INTERNATIONAL|FOREIGN)(?: INCOMING)? WIRE"
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
    """§7.2: what the operating-source reader found on one credit."""

    entity: str
    alias: str
    source_type: str | None
    payout_form: bool


def _operating_read_vetoed(row: str, entity: str, alias: str, payout_form: bool) -> bool:
    """§7.2, §7.3: the vetoes of a new operating read (a payout form, or an alias this release added), read on the row
    before its receiver fields: pay, financing, reversal and adjustment, and person-to-person words. An employer-type
    alias also refuses DIR DEP, PAYRL and REIMB, and the TikTok aliases count only on an ACH-shaped row. A transport
    marketplace also refuses wallet, subscription and wire words. A sixteen-character cut carries its alias's vetoes
    (§7.0)."""
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
    """§7.1: the operating alias read lies inside the bare alias of another processor the ledger has not cleared
    ('BY STRI' inside 'JOBBER BY STRI'), so it names no source while that processor waits."""
    return any(
        processor != entity and any(alias in found.group(0) for found in pattern.finditer(text))
        for processor, pattern in _GATED_PROCESSOR_PATTERNS.items()
    )


def _operating_source(text: str) -> _OperatingSource | None:
    """§7.2: the operating source a credit's revenue text names: a payout form first (it names the entity and counts
    as payout context), else the longest operating alias or its sixteen-character cut, read with the receiver
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
    """§7.1: the first card-settlement form a credit prints, read on the row before its receiver fields and on the
    joined text, unless the form's own refusal or the card veto matches. NET SETTLE is returned too; the caller
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
    """§7.1, §7.2: a registry alias verifies one row with payout context: a payout form, the operating-context words
    (read on the row and the joined text), a card-settlement form, the entity's own context words, or, for a
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
    """§6.1, §7.11: the reversal, cancellation, NSF and provisional-credit rule, with the return codes.
    REIMBURSEMENT never fires on a row that prints a claim or provider signal, and DEBIT CARD CREDIT and POS CREDIT
    never fire on a push payout printed as a card credit (_card_credit_released).

    And step 3's other return, correction and refund spellings (_RETURN_REFUND_CREDIT_PATTERNS): REMBOURSEMENT with
    REIMBURSEMENT's provider carve-out (_remboursement_from_a_provider), and the card-shaped refund labels
    (_CARD_REFUND_LABELS) released as a card credit is."""
    for pattern in (*_REVERSAL_CANCELLATION_CREDIT_PATTERNS, *_RETURN_REFUND_CREDIT_PATTERNS):
        found = pattern.search(text)
        if found is None:
            continue
        if pattern.pattern == _REIMBURSEMENT_WORD.pattern and _CLAIM_OR_PROVIDER_SIGNAL.search(text):
            continue
        if pattern is _REMBOURSEMENT_WORD and _remboursement_from_a_provider(text):
            continue
        if (
            _CARD_CREDIT_LABEL.fullmatch(found.group(0)) or any(pattern is label for label in _CARD_REFUND_LABELS)
        ) and _card_credit_released(text):
            continue
        return True
    return _matches_any(text, _RETURN_CODE_CREDIT_PATTERNS)


def _remboursement_from_a_provider(text: str) -> bool:
    """§7.11: French REMBOURSEMENT is a claim payment, not a refund, on a row that prints REIMBURSEMENT's claim or
    provider signal (_CLAIM_OR_PROVIDER_SIGNAL) or names the Quebec health insurance board (_QUEBEC_HEALTH_PAYER)."""
    return _CLAIM_OR_PROVIDER_SIGNAL.search(text) is not None or _QUEBEC_HEALTH_PAYER.search(text) is not None


def _card_credit_released(text: str) -> bool:
    """§7.11: a DEBIT CARD CREDIT or POS CREDIT row that prints a push-rail word, or names a merchant-processor or
    invoice source together with a payout word. Naming another source (a marketplace's card refund) is not enough.
    Such a row is never pooled for recurrence and verifies only by a form or single-row registry context."""
    if not _CARD_CREDIT_LABEL.search(text):
        return False
    if _CARD_CREDIT_PUSH_WORD.search(text):
        return True
    # Cash App and Apple Cash pushes, on the owner's switch.
    if CASH_APP_CARD_PUSH_RELEASE and _CARD_CREDIT_P2P_PUSH_WORD.search(text):
        return True
    source = _operating_source(text)
    return (
        source is not None
        and source.source_type in _PROCESSOR_CONTEXT_TYPES
        and _CARD_CREDIT_PAYOUT_WORD.search(text) is not None
    )


def _own_book_or_funds_transfer(text: str, account_name: str | None) -> bool:
    """§7.11: BOOK TRANSFER and FUNDS TRANSFER are own-account only when no third-party originator is printed, or when
    that originator is the holder (§5.2's holder test). ELECTRONIC FUNDS TRANSFER DEPOSIT is an EFT channel. Without the
    owner's yes to T19, every BOOK TRANSFER stays own-account. A row an incoming-wire label starts that prints only a
    reference (_bare_incoming_wire: 'FUNDS TRANSFER CREDIT TT <reference> O', 'INCOMING FUNDS TRANSFER <reference>') is
    an incoming wire with no sender, never own-account: pass 7 holds it as wire_no_sender."""
    found = _BOOK_OR_FUNDS_TRANSFER.search(text)
    if found is None or _EFT_FUNDS_TRANSFER.search(text):
        return False
    if found.group(0).startswith("BOOK") and not THIRD_PARTY_BOOK_TRANSFER_AS_WIRE:
        return True
    originator = _third_party_originator(text)
    if originator is None:
        return not _bare_incoming_wire(text)
    return holder_named(originator, account_name)


def named_designation_sender(text: str) -> str | None:
    """§6.3: the sender one of the two layouts prints after an own-account designation (_NAMED_DESIGNATION_TRANSFERS),
    up to its first reference token after a name word, when it prints a word that may name a payer
    (_originator_payer_words, as a book or funds transfer's originator is read); otherwise None."""
    row = _before_receiver(text)
    for pattern in _NAMED_DESIGNATION_TRANSFERS:
        found = pattern.search(row)
        if found is None:
            continue
        sender = _leading_name_words(found.group("sender"))
        if _originator_payer_words(sender):
            return sender
    return None


def _named_sender_after_designation(text: str, account_name: str | None) -> bool:
    """§6.3: the strong rule's own-account patterns read the whole row and never who sent the money. A named sender
    printed after the designation (named_designation_sender) that the holder test does not match (§5.2) refuses them,
    when no other non-revenue pattern reads the row: the credit then falls to the pass's T13 hold
    (transfer_account_designation), which an analyst may review. No sender, or the holder's own name, keeps the
    own-account reading."""
    if not _matches_any(text, _NAMED_DESIGNATION_PATTERNS):
        return False
    sender = named_designation_sender(text)
    if sender is None or holder_named(sender, account_name):
        return False
    return not any(
        pattern.search(text) is not None
        for pattern in _NON_REVENUE_CREDIT_PATTERNS if pattern not in _NAMED_DESIGNATION_PATTERNS
    )


def _split_glued_claim(text: str) -> str:
    """§7.7: the text the financing, potential-lender and insurer lookups read: a space before a glued
    HCCLAIMPMT, so a sixteen-character name glued to the token is still found."""
    return _GLUED_CLAIM_ENTRY.sub(r" \1", text)


def _refused_by_payer_guards(text: str, region: str, account_name: str | None) -> str | None:
    """§6.1: steps 11 (the customer and invoice descriptors) to 14 refuse a payer the holder test or the
    numbered-company guard matches. Returns 'holder' or 'numbered', or None."""
    if holder_named(region, account_name):
        return "holder"
    if numbered_company(text, region):
        return "numbered"
    return None


def _payer_remittance(text: str, region: str, account_name: str | None) -> bool:
    """§7.5: the payer's accounts-payable remittance: an AP pattern, or an invoice number on a row that also prints
    a payment-channel word; the free-text forms count on a PayPal row or a wire only with a company form; the veto
    reads the row with the matched words and the credit posting labels removed."""
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
    # A wire whose reference is glued to WIRE answers to the gate and the vetoes too.
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
    """§7.6: a public payer's remittance: arm A (Treasury vendor codes, whole row) or arm B (a public payer anchored
    on the payer name, with a payer-side purpose). Returns the matched rule, or None. Every veto is read on the row
    after Bank of America's Treasury boilerplate is deleted."""
    whole = _TREASURY_BOILERPLATE.sub(" ", text)
    row = _before_receiver(whole)
    if _PUBLIC_PAYER_NON_SALE_WORDS.search(whole) or _PUBLIC_PAYER_OTHER_VETO.search(whole):
        return None
    if _public_payer_arm_a(whole):
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
    """§7.9: the wire row the financing roots are read on: the channel words and the sending, originating and
    intermediary bank fields removed (Santander prints its sending bank after WIRE IN FROM, Chase its originating
    bank after OGB)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        text = text[: santander.start("bank")] + " " + text[santander.end("bank"):]
    return _WIRE_CHANNEL_AND_BANK_FIELDS.sub(" ", text)


def _wire_originator_run(text: str) -> str | None:
    """§7.9: the first six words of a wire's originator field run together (wrap-tolerant, so 'CAPI TAL' reads
    CAPITAL), or None when the row prints no originator label. On Santander's layout the originator follows the
    account number."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return "".join(santander.group("originator").split()[:6])
    label = _WIRE_ORIGINATOR_LABEL.search(text)
    return None if label is None else "".join(text[label.end():].split()[:6])


def _wire_remittance_purpose(text: str, region: str, account_name: str | None) -> bool:
    """§7.9: an incoming wire (N1) whose purpose cites an invoice, a PO, an order or goods, and that no wire veto
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
    """§7.9: the vetoes of an incoming wire: a non-sale purpose; a financing root after the channel and bank fields
    are removed, or in the first six words after the originator label run together (wrap-tolerant); any known payee;
    the own account (the originator's first two words are the beneficiary's or in the account name); a brand-word
    affiliate (the originator's first distinctive word is the beneficiary's first word or the account name's); a cut
    originator field that starts a financing name; a title or escrow firm (§8.5). The AP rule reads them on a wire
    too (§7.5)."""
    if _WIRE_NON_SALE_PURPOSE.search(text):
        return True
    if _names_financing(_wire_financing_text(text)):
        return True
    run = _wire_originator_run(text)
    if run is not None and _names_financing(run):
        return True
    if match_known_payee(text, credit=True) is not None:
        return True
    holder_text = account_name_text(account_name)
    originator = region.split()
    beneficiary = _WIRE_BENEFICIARY_WORDS.search(text)
    if originator:
        first_two = " ".join(originator[:2])
        if wire_sender_is_beneficiary(text, region):
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


#: §7.9: an incoming wire's beneficiary field and its first two words.
_WIRE_BENEFICIARY_WORDS = re.compile(r"\bN?BNF\b (\S+)(?: (\S+))?")


def wire_sender_is_beneficiary(text: str, region: str) -> bool:
    """§7.9: an incoming wire's originator is its own beneficiary, the holder sending from its account at another
    bank: the originator's first two words are the beneficiary's. _wire_vetoed refuses Q5 on it, and pass 7 holds it
    as the holder's own money (holder_name)."""
    originator = region.split()
    beneficiary = _WIRE_BENEFICIARY_WORDS.search(text)
    if not originator or beneficiary is None:
        return False
    return " ".join(word for word in beneficiary.groups() if word) == " ".join(originator[:2])


def _cut_financing_originator(region: str) -> bool:
    """§7.9: an originator that fills its field to within two characters of the width (Santander 16, Bank of
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
    holder_name: str | None = None,
    description: str | None = None,
) -> _RevenueDecision | None:
    """The credit's revenue decision. `description` is the printed description, read only by the strong non-revenue
    step's LN-name reading (description_text.ln_name_spans)."""
    if amount <= 0 or not posted:
        return None
    text = revenue_text(text)
    # The holder tests read the holder's own name when the parser read it; the account-name field keeps its product
    # readings (_business_account).
    holder = holder_reading(account_name, holder_name)

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
    # §6.1 step 3a: a government payment that prints no purpose is excluded, at any amount (under the $1 floor too,
    # as step 3), after the direction conflict and the reversal (a government row printing a return word stays the
    # reversal's) and before every other rule; the residue test keeps any other payer's name off the row, so a
    # lender's D1 reading is never pre-empted.
    no_purpose = government_no_purpose(text)
    if no_purpose is not None:
        return _RevenueDecision(
            "non_revenue",
            None,
            "government_no_purpose_exclusion",
            no_purpose,
            "government_payment_no_purpose",
            0.95,
            (
                f"A government payment that prints no purpose ({no_purpose}): excluded from revenue by the owner's "
                "ruling (the underwriter's Q12, spec §19.1)."
            ),
            context_signals=("credit_direction", "government_no_purpose"),
        )

    # §6.1 step 4 (Q7, 5.6): a dealer's funding from a listed auto lender is revenue; a credit union's VHCL PURCH
    # entry waits for the statement pass, which verifies two or more of them. Never under the $1 floor (§7.0). The
    # decision names the lender and its alias, as the financing-proceeds decision it replaces did.
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
    insurance_match = _insurance_registry_match(lookup_text, glued_digits=True)
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
    # payout-credit entity.
    financing_match = _financing_proceeds_payee(lookup_text, account_name=account_name, holder_name=holder_name)
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
    # D1 by descriptor (Square Capital's SQ CAP, SBA and EIDL). `_descriptor_proceeds` keeps the potential registry and
    # the strong non-revenue rule below ahead of a line-of-credit draw or a floor-plan advance.
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
    # §6.3, §5: a factoring review entity's credit is a factor's payout, never the potential tier's exclusion: it goes
    # on to the operating-revenue path, as an admitted factor's does.
    if potential_lender_match is not None and potential_lender_match[0] not in FACTORING_REVIEW_ENTITIES:
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
    # §6.3: a named sender after an own-account designation refuses the own-account patterns; such a credit is no sale
    # the text proves either, so no later step verifies it: the pass holds it (T13).
    named_after_designation = _named_sender_after_designation(text, holder)
    # §6.3: Snap's merchant funding printed with the strong LOAN word ('SNAP LOAN FUNDING F<digits> <merchant>') is a
    # lease-to-own financier's payout of the merchant's sale, which the true-revenue pass claims
    # (CUSTOMER_FINANCING_PAYERS): the strong rule reads the row without that form only. Every other reader (the
    # designation test above, the descriptor proceeds, the lender-credit reader) keeps the full text. §7.11: a company
    # name that holds LN ('LN TRUCKING LLC', 'CONTOSO LN HOLDINGS LLC'; description_text.ln_name_spans, read on the
    # printed description: no street, no loan word around it, no transfer wording) is read by the strong patterns with
    # the LOAN the normalizer made of its LN blanked, as Snap's form is, so the row reaches pass 7, whose financing root
    # holds it for review (financing_named_payer). Every other reader keeps the full text.
    strong_text = _SNAP_MERCHANT_FUNDING.sub(" ", text)
    for name, blanked in ln_name_spans(description or ""):
        strong_text = re.sub(
            r"(?<![A-Z0-9])" + re.escape(name) + r"(?![A-Z0-9])", lambda _found, kept=blanked: kept, strong_text
        )
    if (
        _matches_any(strong_text, _NON_REVENUE_CREDIT_PATTERNS) and not named_after_designation
    ) or _own_book_or_funds_transfer(text, holder):
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
    if named_after_designation:
        return _fallback_credit_decision(text)

    # §6.1 step 9b, the channel gate: a consumer rail, a check, cash, branch or ATM deposit, or a row with no payer
    # word is never verified; a real-time or push rail is verified by the operating registry only.
    gate = channel_gate(text)
    if gate != "closed":
        source_text = _before_receiver(text) if gate == "push" else text
        source = _operating_source(source_text)
        if source is not None:
            return _operating_source_decision(text, source, account_name=account_name, bank=bank, holder=holder)
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
    # The customer and invoice descriptors never read the receiver field's value, the holder (§5.2); on a wire they
    # answer to the §7.9 wire vetoes as steps 12 and 14 do, and a vetoed row falls through.
    customer_or_invoice = (
        _matches_any(_without_receiver_value(text), _CUSTOMER_INVOICE_DESCRIPTORS)
        or _matches_any(joined, _CUSTOMER_INVOICE_DESCRIPTORS)
    ) and not (_wire_vetoes_apply(text) and _wire_vetoed(text, region, holder))
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
    guard = _refused_by_payer_guards(text, region, holder)
    if guard == "holder" and (
        customer_or_invoice
        or _payer_remittance(text, region, holder)
        or _public_payer_remittance(text) is not None
        or _wire_remittance_purpose(text, region, holder)
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
        if _payer_remittance(text, region, holder):
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
        if _wire_remittance_purpose(text, region, holder):
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
    holder: str | None = None,
) -> _RevenueDecision:
    """§6.1: a credit the operating registry names: verified with payout context, otherwise it needs recurrence or
    related activity. Property-management platforms and wholesale auctions never verify here: the recurrence pass
    decides them."""
    entity, alias, source_type = source.entity, source.alias, source.source_type
    business_account = _business_account(account_name)
    if platform_entry_leads_with_financing(text, entity, account_name if holder is None else holder):
        # §20: an entry field that leads with a financing word is the platform's own financing, never verified here;
        # pass 7 holds it as financing_named_payer (the registry does not claim a financing row).
        return _RevenueDecision(
            "unverified_deposit",
            entity,
            "operating_source_requires_context",
            alias,
            PLATFORM_FINANCING_ENTRY_RULE,
            0.50,
            (
                f"Credit matched maintained {source_type or 'operating-source'} alias '{alias}', but its entry field "
                "leads with a financing word: the platform's financing is never revenue."
            ),
            source_type=source_type,
            context_signals=("credit_direction", "maintained_operating_source", "financing_entry"),
        )
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


#: Financing words that describe the payment, not the payee, when they lead the name.
_GENERIC_ENTITY_WORDS = {"FINANCE", "FINANCING", "FUNDING", "CAPITAL", "FUNDER", "ADVANCE"}
_ENTITY_ACRONYMS = {"ACH", "BDC", "CMCA", "EFT", "LLC", "LLP", "LP", "MCA", "PLLC", "SBA", "SNAP"}
_MAX_ENTITY_TOKENS = 4
#: Connectors that never end a name (a name cut by the four-word cap: 'BOKF NATIONAL BANK OF').
_TRAILING_CONNECTORS = frozenset({"OF", "AND", "THE", "DE", "DU", "DES"})
_TRUIST_CORP_PREFIX = re.compile(r"^ACH CORP (?:DEBIT|CREDIT)\b")
#: Truist prints no padding, so a short originator lets the receiver's words into the 16-character company
#: field. A Truist name is published only when a whole legal-form word lies inside those 16 characters.
_TRUIST_COMPANY_FIELD = 16


def _is_payroll_provider_row(text: str) -> bool:
    """A payroll provider, benefit administrator or French pay row (payroll N1 and N2)."""
    if _names_financing(text):
        return False
    return _PAYROLL_GLUED_PATTERN.search(text) is not None or _matches_any(
        _originator_segment(text), _PAYROLL_PROVIDER_PATTERNS
    )


def _unknown_payee_tokens(text: str) -> tuple[str, ...]:
    """D11: the payee words of an unknown counterparty, at most four.

    Removes originator-name labels, cuts at the first ACH field segment, drops
    channel words, single letters and leading financing words, and stops at the
    first reference token (digits, a masked number or a month) once a name has
    started, so a person's name printed after the references never joins it.

    A name ends at its first legal-form word after the first word; a leading AND and a trailing connector are
    dropped. A bank template prefix is removed first. A wire is read from its beneficiary, where a name ends at
    its first organisation cue after the first word.
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
    """D11 and 5.3: a cue names an organisation, except a legal-form word printed first (CORP of 'CORP
    FABRIKAM ...'); a name made only of cue words ('BANK', 'CORP') names none."""
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
    """On a Truist 'ACH CORP DEBIT' row, whether a whole legal-form word lies inside the first 16 characters of the
    payee words, the width of the company-name field. True for every other row."""
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


#: True revenue spec §11, §17.1, §19.1: the payoff words a confirmed funder's debit may print, read as whole words on its
#: own normalized text (PAY-OFF and PRE-PAY normalize to PAY OFF and PRE PAY): PAYOFF, PAY OFF, PAY-OFF, PREPAY, PRE-PAY,
#: PREPAYMENT, BUYOUT, BUY OUT and PAYOUT. A word glued to letters or digits (a reference such as XPAYOFF12) is no whole
#: word and reads nothing; a word followed by punctuation (`PrePay:[...]`) is one.
LUMP_SUM_PAYOFF_WORDS = re.compile(r"\b(?:PAYOFF|PAY OFF|PREPAYMENT|PREPAY|PRE PAY|BUYOUT|BUY OUT|PAYOUT)\b")
#: The same words as a bank may print them, to quote: any case, any separator a normalization reads as a space.
_LUMP_SUM_PAYOFF_PRINTED = re.compile(
    r"(?<![A-Za-z0-9])(?:PAY[^A-Za-z0-9]*OFF|PRE[^A-Za-z0-9]*PAY(?:MENT)?|BUY[^A-Za-z0-9]*OUT|PAYOUT)(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def lump_sum_payoff_words(description: str, text: str) -> str | None:
    """The first payoff word a row's normalized `text` prints, quoted as the bank printed it in `description` (the
    first printed match that normalizes to one of the words; else the normalized word), or None. The caller reads it
    on a confirmed funder's paid debit only, never on a credit."""
    found = LUMP_SUM_PAYOFF_WORDS.search(text or "")
    if found is None:
        return None
    for printed in _LUMP_SUM_PAYOFF_PRINTED.finditer(description or ""):
        if LUMP_SUM_PAYOFF_WORDS.fullmatch(normalize_transaction_description(printed.group(0))):
            return printed.group(0)
    return found.group(0)


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
    holder_name: str | None = None,
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
    category_text: str | None = None,
) -> TransactionClassification:
    # The is_check, is_ach and is_pos_context flags read the category chain's text (a credit without its statement
    # furniture, classify_transaction); the row's text where none is given.
    flags_text = text if category_text is None else category_text
    is_debit = amount < 0
    contributes_lender = classification == "confirmed_lender" and is_debit and is_posted
    # A confirmed funder's paid debit printing a payoff word is a lump sum, in paid to lenders and the lender count and
    # out of the withholding numerator, beside the contribution flags. Potential lenders and every other row are
    # unchanged.
    lump_sum_payoff = lump_sum_payoff_words(description, text) if contributes_lender else None
    contributes_potential = classification == "potential_lender" and is_debit and is_posted
    contributes_insurance = classification == "insurance" and is_debit and is_posted
    flag_group = FLAG_GROUP_BY_STATE.get(classification)
    # A flag-group state names its own group. Premium financing is the one group
    # a rule passes in, on an insurance row.
    group_key = flag_group.key if flag_group is not None else flagged_group
    # A posted debit of a flag group counts in the flagged totals, and so does a
    # posted credit of a group whose credits are flagged revenue (factoring; C5
    # count_credited and total_credited).
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
        holder_name=holder_name,
        description=description,
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
        holder_name=holder_name,
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
        lump_sum_payoff=lump_sum_payoff,
        contributes_to_lender_count=contributes_lender,
        contributes_to_potential_lender_count=contributes_potential,
        contributes_to_lender_totals=contributes_lender,
        contributes_to_withholding_rate=contributes_lender and lump_sum_payoff is None,
        contributes_to_potential_lender_totals=contributes_potential,
        contributes_to_potential_withholding_exposure=contributes_potential,
        contributes_to_insurance_totals=contributes_insurance,
        contributes_to_flagged_totals=contributes_flagged,
        **revenue_flags,
        contributes_to_lender_credit_exclusion=contributes_to_lender_credit_exclusion,
        is_ach=_ACH_TOKEN.search(flags_text) is not None,
        is_check=_matches_any(flags_text, _CHECK_PATTERNS),
        is_loan_payment=_matches_any(text, _EXPLICIT_REPAYMENT_PATTERNS),
        is_pos_context=_matches_any(flags_text, _POS_PATTERNS),
    )


#: D9: known-payee groups that LOC wording moves to lines of credit.
_LOC_OVERRIDE_STATES = frozenset({"confirmed_lender", "alternative_position", "line_of_credit"})


_FIELD_ORDER_FORMS = _compile_field_order_forms()


def _field_order_payee(text: str) -> PayeeMatch | None:
    """The admitted payee a debit prints in the bank's field order, or None."""
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


#: An alternative-position payee's paid membership, or a top-up of the
#: customer's own balance with it, printed right after the payee's alias, is not
#: a repayment. The words are read after the matched alias, so no payee name is
#: written here.
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


#: OQ2 (true revenue spec §19) puts the five BNPL providers in PAYOUT_CREDIT_ENTITIES: a provider's settlement to the
#: merchant is the merchant's own sale, so revenue. It covers settlements only: a credit where the account holder is the
#: provider's customer, not its merchant (a Klarna WITHDRAWAL, a RETURN FOR ... PURCHASE), is not one. A credit of one of
#: the five that prints one of these consumer-side words (a return, a withdrawal, a refund, a balance, cash back, a
#: reward, a card product, a purchase, or the debt collector TRUEACCORD) stays D1. Sezzle, American First Finance and
#: PAYABILITY keep an entity-wide exception: the corpus prints WITHDRAWAL on Sezzle's merchant payouts and CARD on
#: PAYABILITY's transfers. Cherry Technologies joins PAYOUT_CREDIT_ENTITIES under the same consumer-side veto, so a
#: Cherry consumer credit (a refund, a card credit) keeps its D1 reading.
_OQ2_BNPL_ENTITIES = frozenset({"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit", "Cherry Technologies, Inc."})
#: Cherry joined the payout entities under OQ2's consumer-side veto only (Q8), so a Cherry loan or advance left D1;
#: it keeps D1 again, as before the Q8 ruling. The other OQ2 entities' LOAN readings are OQ2's.
_CHERRY_ENTITY = "Cherry Technologies, Inc."
_CHERRY_LOAN_CREDIT = re.compile(r"(?<![A-Z])LOANS?\b")


def _is_payout_credit(
    text: str, match: PayeeMatch, *, account_name: str | None = None, holder_name: str | None = None,
) -> bool:
    """Whether a credit of ``match`` is a payout-credit entity's settlement: revenue, not D1 financing proceeds.

    PAYOUT_CREDIT_ENTITIES; OQ2 (§19) narrowed to the five
    BNPL providers' settlements (_BNPL_CONSUMER_CREDIT). Credits only. A Cherry credit
    printing LOAN(S) or a non-sale or financing word (_PAYOUT_NON_SALE_CREDIT: an
    advance, capital, interest, a dividend, a rebate) is no settlement either: it keeps
    D1, its reading before the Q8 ruling. Those words are read as the true-revenue pass's
    veto reads them, without the receiver field's value and without the holder's names
    (true_revenue's without_receiver_and_holder on the statement's `account_name` and
    `holder_name`), so a practice whose own name prints CAPITAL, ADVANCE or INTEREST as
    an unlabelled receiver (Wells Fargo, TD, a generic ACH CREDIT) keeps its Cherry
    payouts.
    """
    if match.entity not in PAYOUT_CREDIT_ENTITIES:
        return False
    # Both sites read the same text: the revenue text (a glued leading date dropped) without the receiver's name, so
    # the holder's own name ('INDN:BALANCE DENTAL LLC') never makes a settlement consumer-side (§5.2).
    words = _without_receiver_value(revenue_text(text))
    if match.entity == _CHERRY_ENTITY and (_CHERRY_LOAN_CREDIT.search(words) or _PAYOUT_NON_SALE_CREDIT.search(words)):
        cherry = without_receiver_and_holder(revenue_text(text), account_name, holder_name)
        if _CHERRY_LOAN_CREDIT.search(cherry) or _PAYOUT_NON_SALE_CREDIT.search(cherry):
            return False
    return not (match.entity in _OQ2_BNPL_ENTITIES and _BNPL_CONSUMER_CREDIT.search(words))


def _financing_proceeds_payee(
    text: str, *, account_name: str | None = None, holder_name: str | None = None,
) -> PayeeMatch | None:
    """D1: the known payee whose credit is financing proceeds, or None.

    The credits of a payout-credit entity (PAYOUT_CREDIT_ENTITIES) are the account
    holder's own sales settled by the platform, so they are revenue; that entity's
    debits keep their group. A BNPL provider's consumer-side credit is not a
    settlement (OQ2, _is_payout_credit). A factoring payee's credits are the
    business's own sales paid by the factor, so they are revenue too, and they keep
    the factoring flag (_FLAGGED_REVENUE_CREDIT_STATES). `account_name` and
    `holder_name` are the statement's, which the Cherry veto of _is_payout_credit
    reads out of the row.
    """
    match = match_known_payee(text, credit=True)
    if (
        match is None
        or match.state not in FINANCING_STATES
        or match.state in _FLAGGED_REVENUE_CREDIT_STATES
        or _is_payout_credit(text, match, account_name=account_name, holder_name=holder_name)
    ):
        return None
    return match


def _q7_dealer_funding(text: str, amount: float, direction_consistent: bool) -> DealerFunding | None:
    """§6.1: the credit's dealer-funding reading, read as _classify_credit_revenue reads it: a credit of $1 or more
    whose direction agrees and that no reversal marker claims (steps 2 and 3 win), which dealer_funding_reading reads
    on its revenue text; or None."""
    if amount < _MICRO_DEPOSIT_FLOOR or not direction_consistent:
        return None
    revenue = revenue_text(text)
    dealer = dealer_funding_reading(revenue)
    return None if dealer is None or _reversal_credit(revenue) else dealer


def _dealer_funding_credit_record(
    common: dict[str, object],
    dealer: DealerFunding,
) -> TransactionClassification:
    """A dealer-funding credit's record keeps its lender, as the financing-proceeds record it replaces did: the listed
    auto lender and its alias, or the credit union its payer region prints. A listed lender's dealer funding is never
    financing proceeds (D1), so it leaves the lender credits; a credit union's VHCL PURCH entry is decided by the
    statement pass (two or more verify, one alone is held)."""
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


#: D1 by descriptor: credits whose own words say they are financing proceeds, with
#: no registry payee named. Credits only.
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
    # §7.11: Square Capital's SQ CAP spelling on a row that names Square, and SBA and EIDL disbursements (A3: the
    # SBA's name cut to its originator field too).
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
    """A factoring payee's credit is the business's own sales, paid by the factor.

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


def _factoring_review_payee(text: str) -> PayeeMatch | None:
    """Lender detection spec §5, amended: the factoring review entity (FACTORING_REVIEW_ENTITIES) whose potential alias
    wins on the row, as a factoring payee, or None."""
    found = registry_match(text, POTENTIAL_LENDER_ALIASES)
    if found is None or found[0] not in FACTORING_REVIEW_ENTITIES:
        return None
    return PayeeMatch(found[0], "factoring", found[1])


def _unconfirmed_factoring_credit_record(
    common: dict[str, object],
    match: PayeeMatch,
) -> TransactionClassification:
    """A factoring review entity's credit is a factor's payout, as an admitted factor's is
    (_flagged_revenue_credit_record): the row takes the factoring group, carries its flag and counts in the flagged
    totals as a credit, and its revenue decision is the operating-revenue path's. The ledger has not confirmed the
    factor, so the row is marked unconfirmed (review_required), as a 5.3 review entity's debit is. Its debits keep the
    potential tier."""
    return _build_record(
        **common,
        classification=match.state,
        canonical_entity=match.entity,
        match_method="unconfirmed_flag_payee_alias",
        matched_alias=match.alias,
        matched_rule="factoring_review_revenue_credit",
        confidence_score=0.82,
        reason=(
            f"Matched maintained candidate alias '{match.alias}' of an unconfirmed factor on a credit: a factor's "
            "payout is the business's own sales, so it stays revenue and in eligible deposits; it is flagged as a "
            "factoring position, marked unconfirmed."
        ),
        review_required=True,
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

    The rules run in the spec's order, with the owner's added rules where their
    own placement puts them, and the first match wins.
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
    # D5: a loan payment that prints no payee is the statement bank's own loan,
    # not a potential lender. The last D5 rule.
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
    holder_name: str | None = None,
) -> TransactionClassification:
    text = normalize_transaction_description(description)
    derived_direction = "credit" if amount >= 0 else "debit"
    source_direction = str(direction or derived_direction).strip().lower()
    direction_consistent = source_direction == derived_direction
    # §7.0: a credit's category chain (the fee, transfer, tax, payroll, utility, rent, check and subscription rules, and
    # the record's is_check, is_ach and is_pos_context flags) reads the credit without the statement furniture a parser
    # glued onto it (without_statement_furniture: TD's back panel, a Symitar fee or balance summary, Citizens'
    # continued-page header), as every credit revenue rule reads it (revenue_text). The record keeps its text; the
    # posting-status, NSF, refund, insurance, known-payee, dealer-funding, factoring, lender-credit and registry readers
    # keep the row's text. A debit keeps today's text until the owner admits the G7 move (spec §17.1, "Debit readings
    # waiting on a G7 admission").
    category_text = without_statement_furniture(text) if amount > 0 else text
    common: dict[str, object] = {
        "description": description,
        "text": text,
        "category_text": category_text,
        "amount": amount,
        "date_value": date,
        "bank": bank,
        "account": account,
        "account_name": account_name,
        "holder_name": holder_name,
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

    # A debit's returned or unpaid item charge is a returned item too.
    if _matches_any(text, _NSF_PATTERNS) or (amount < 0 and _matches_any(text, _DEBIT_ITEM_CHARGE_NSF_PATTERNS)):
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

    # A credit's premium-finance lookup reads a glued digit run; a debit keeps today's reading.
    insurance_match = _insurance_registry_match(text, glued_digits=amount > 0)
    # Premium-finance wording on a row no premium-finance alias claimed is premium
    # financing too, under the insurer when one is named.
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
    # from the POS and ATM rules (D8) and takes its group at step 7 below. A
    # credit is read with the credit index (a run-together alias with a digit run
    # glued after it, the credit-only aliases).
    known_payee = match_known_payee(text, credit=amount > 0)
    # A membership or balance top-up debit of an alternative-position payee
    # matches no known payee (steps 5 and 7).
    if known_payee is not None and amount < 0 and _is_membership_or_top_up(text, known_payee):
        known_payee = None
    # An admitted payee printed in the bank's field order, on a debit no alias matched
    # (FIELD_ORDER_PAYEE_FORMS). Credits keep today's rules.
    field_order_payee = _field_order_payee(text) if known_payee is None and amount < 0 else None
    if field_order_payee is not None:
        known_payee = field_order_payee
    # A debt-relief payee, on a debit no known payee claimed, read without the row's receiver fields (the account
    # holder may itself be a debt-relief firm). It then stands in for the known payee: the POS and ATM exceptions
    # (D8) and step 7 treat it as one. Credits keep today's rules.
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

    # §6.1: a dealer-funding credit takes its lender's record ahead of the fee, transfer, tax, payroll and utility
    # rules and of D1 (CU Direct's VADMIN FEE is the dealer's fee income, never a bank fee; a listed auto lender's
    # dealer funding is never financing proceeds), as its revenue decision runs ahead of D1.
    if amount > 0:
        dealer = _q7_dealer_funding(text, amount, direction_consistent)
        if dealer is not None:
            return _dealer_funding_credit_record(common, dealer)

    # A debit's stop-payment or OD item charge, and a bare stop-payment row, are charges. From here the category rules
    # read category_text (a credit without its furniture).
    if _matches_any(category_text, _FEE_PATTERNS) or (
        amount < 0 and _matches_any(category_text, _DEBIT_BANK_CHARGE_FEE_PATTERNS)
    ):
        return _build_record(
            **common,
            classification="fee",
            match_method="strong_non_lender_exclusion",
            matched_rule="bank_or_processing_fee",
            confidence_score=0.97,
            reason="A bank, ACH, transfer, service, or merchant-processing fee rule matched.",
        )

    if _matches_any(category_text, _TRANSFER_PATTERNS):
        return _build_record(
            **common,
            classification="transfer",
            match_method="strong_non_lender_exclusion",
            matched_rule="transfer",
            confidence_score=0.96,
            reason="The descriptor identifies an account, online, or person-to-person transfer.",
        )

    if _matches_any(category_text, _TAX_PATTERNS):
        return _build_record(
            **common,
            classification="tax",
            match_method="strong_non_lender_exclusion",
            matched_rule="tax_payment",
            confidence_score=0.96,
            reason="The descriptor identifies a tax authority or tax payment.",
        )

    if _matches_any(category_text, _PAYROLL_PATTERNS) or _is_payroll_provider_row(category_text):
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

    if _matches_any(category_text, _UTILITY_PATTERNS):
        return _build_record(
            **common,
            classification="utility",
            match_method="strong_non_lender_exclusion",
            matched_rule="utility_payment",
            confidence_score=0.94,
            reason="The descriptor identifies a utility payment.",
        )

    # Step 7: the known payee's group (D9 inside). A credit is proceeds only for
    # a financing group (D1), and never for a payout-credit entity (its credits
    # are the holder's own sales; OQ2 covers a BNPL provider's settlements only,
    # _is_payout_credit); a card-issuer or lease/rental payee on a credit falls
    # through to the rules below. A factoring payee's credit is revenue and
    # keeps the factoring flag.
    if known_payee is not None:
        if amount < 0:
            if field_order_payee is not None:
                return _field_order_debit_record(common, text, known_payee)
            return _known_payee_debit_record(common, text, known_payee)
        if known_payee.state in _FLAGGED_REVENUE_CREDIT_STATES:
            return _flagged_revenue_credit_record(common, known_payee)
        # A listed auto lender's dealer funding took its own record above, never financing proceeds.
        if known_payee.state in FINANCING_STATES and not _is_payout_credit(
            text, known_payee, account_name=account_name, holder_name=holder_name
        ):
            return _financing_proceeds_credit_record(common, amount, known_payee)
    # Lender detection spec §5, amended: a factoring review entity's credit is a factor's payout, flagged and marked
    # unconfirmed; its aliases stay in the potential table, so its debits keep the potential tier. A credit the
    # revenue path's reversal rule reads (§6.1 step 3: a trailing RETURNED ITEM that step 3's row rule above does not
    # read) is no payout: it takes no Factoring flag and no review mark.
    if amount > 0:
        review_factor = _factoring_review_payee(text)
        if review_factor is not None and not _reversal_credit(revenue_text(text)):
            return _unconfirmed_factoring_credit_record(common, review_factor)
    # D1 by descriptor: the bank's own line advance, a line-of-credit draw or a
    # per-vehicle floor-plan advance. Credits only.
    if amount > 0:
        descriptor_proceeds = _descriptor_proceeds(text)
        if descriptor_proceeds is not None:
            return _descriptor_proceeds_credit_record(common, amount, descriptor_proceeds, bank)

    # Step 8: obligation descriptors, debits only (D1: these never apply to credits).
    if amount < 0:
        obligation = _descriptor_obligation(text, bank)
        if obligation is not None:
            return _build_record(**common, **obligation)

    if _matches_any(category_text, _RENT_PATTERNS):
        return _build_record(
            **common,
            classification="rent",
            match_method="strong_non_lender_exclusion",
            matched_rule="rent",
            confidence_score=0.95,
            reason="The descriptor identifies rent or a landlord payment.",
        )

    if _matches_any(category_text, _CHECK_PATTERNS):
        return _build_record(
            **common,
            classification="other",
            match_method="strong_non_lender_exclusion",
            matched_rule="check",
            confidence_score=0.94,
            reason="The row is a check or cheque and has no separate verified lender evidence.",
        )

    if _matches_any(category_text, _SUBSCRIPTION_PATTERNS):
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
        # A review entity of a flag group takes its flag, marked unconfirmed. Its aliases stay in
        # POTENTIAL_LENDER_ALIASES, so its credits keep the potential tier's exclusion.
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


#: §6.2, §20: the undo wordings of a deposit, read as pass 4's revenue-side markers on either row: a returned deposited
#: item (PNC's RET DEP ITEM, RETURNED DEPOSIT ITEM, Wells Fargo's DEPOSITED ITEM RETN and Chase's DEPOSITED ITEM
#: RETURNED), an error, transaction or deposit correction, a mobile, remote or ATM deposit adjustment, and Bank of
#: America's ADJUSTMENT CORRECTION. And a credit union's deposit correction cut short or with its type between the words
#: (DEPOSIT TYPE CORRECT, DEPOSIT CORRECT).
_DEPOSIT_CORRECTION_MARKERS = (
    re.compile(r"\b(?:ERROR|TRANSACTION|DEPOSIT) CORRECTION\b"),
    re.compile(r"\b(?:MOBILE|REMOTE|ATM) DEPOSIT ADJUSTMENT\b"),
    re.compile(r"\bADJUSTMENT CORRECTION\b"),
    re.compile(r"\bDEPOSIT (?:TYPE )?CORRECT(?:ION)?\b"),
)
_DEPOSIT_UNDO_MARKERS = (
    re.compile(r"\bRET(?:URN(?:ED)?)? DEP(?:OSIT(?:ED)?)? ITEMS?\b"),
    re.compile(r"\bDEPOSITED ITEMS? RET\w*"),
    *_DEPOSIT_CORRECTION_MARKERS,
)
#: The debits that undo a deposit, which pair with the deposit itself (_deposit_return_pairs): the undo markers, a
#: deposited check returned, a bare RETURNED ITEM (and Bank of America's RETURN ITEM CHARGEBACK), RBC's ITEM RETURNED
#: UNPAID and a returned check; never the bank's fee for the return (_DEPOSIT_UNDO_FEE). TD's RTN NSF is not one. And
#: TD Bank's returned deposited item, DEP RETURN CHARGEBACK (its DEP RETURN FEE prints beside it), and a bank's
#: row-leading two-word CHARGE BACK of a deposited item, with ITEM or a return reason after it (CHARGE BACK ITEM CHECK
#: <n>, CHARGE BACK - SIGNATURE(S) IRREGULAR, ... NSF, INSUFFICIENT, UNCOLLECTED, ACCOUNT CLOSED, STOP PAY, REFER TO
#: MAKER); read on debits only, never a bare CHARGEBACK, a processor's or a merchant's chargeback,
#: the bank's fee, a bare DEP RETURN or RTN NSF.
_DEPOSIT_RETURN_DEBIT_PATTERNS = (
    *_DEPOSIT_UNDO_MARKERS,
    re.compile(r"\bDEPOSITED (?:CHECK|CHEQUE)S? RET\w*"),
    re.compile(r"\bRETURN(?:ED)? ITEMS?\b"),
    re.compile(r"(?<![A-Z])ITEMS? RET(?:URNED)?\b"),
    re.compile(r"\bRETURNED (?:CHECK|CHEQUE)S?\b|\b(?:CHECK|CHEQUE)S? RETURNED\b"),
    re.compile(r"\bDEP(?:OSIT)? RETURN CHARGE ?BACK\b"),
    re.compile(
        r"^(?:\d{1,2} \d{1,2} )?CHARGE ?BACK (?:ITEMS?\b|SIGNATURE|ENDORSE|NSF\b|INSUFFICIENT|UNCOLLECTED"
        r"|ACC(?:OUN)?T CLOSED|STOP PAY|REFER TO MAKER)"
    ),
)
#: A paid check printed first with its number (the holder's own check, whatever its memo says).
_PAID_CHECK_FIRST = re.compile(r"^(?:\d{1,2} \d{1,2} )?(?:CHECK|CHEQUE|CHK|CHQ) ?#? ?\d")
#: A returned deposit pairs with a deposit up to this many days before it, the same day included.
_DEPOSIT_RETURN_DAYS = 14
#: A mobile or electronic deposit capture glued to its word (MDEPOSIT, EDEPOSIT IN BRANCH), a deposit word, and the card
#: words a bare deposit never prints (a card settlement's VISA DEPOSIT is no deposit channel).
_DEPOSIT_CAPTURE_WORD = re.compile(r"(?<![A-Z])(?:MDEPOSIT|EDEPOSIT)\b")
_DEPOSIT_WORD = re.compile(r"(?<![A-Z])(?:DEP|DEPOSITS?)\b")
_CARD_WORD = re.compile(r"(?<![A-Z])(?:CARDS?|VISA|MC|MASTERCARD|AMEX|DISCOVER|BANKCARD|POS)\b")


def _deposit_return_debit(text: str) -> bool:
    """A debit that undoes a deposit (_DEPOSIT_RETURN_DEBIT_PATTERNS), never the bank's fee for it.

    And only the bank's own return, never the holder's payment that prints a 'return item' memo: a person-to-person
    or push rail, WIRE, an electronic payment's mark (which names its payee) or a paid check printed first with its
    number refuses it. A credit union's returned check prints the check's number and its maker after RETURNED CHECK;
    that stays a return."""
    if not _matches_any(text, _DEPOSIT_RETURN_DEBIT_PATTERNS) or _DEPOSIT_UNDO_FEE.search(text) is not None:
        return False
    return not (
        _CONSUMER_P2P_RAIL.search(text) or _PUSH_RAIL.search(text) or _WIRE_WORD.search(text)
        or _ELECTRONIC_PAYMENT_FORM.search(text) or _PAID_CHECK_FIRST.search(text)
    )


#: True revenue spec §6.2's package passes, §9.1: a processor's chargeback of a card sale, and a processor's merchant,
#: financial or bankcard adjustment, read on a debit's text (processor_chargeback_debit); never the bank's or the
#: processor's fee for one (_PROCESSOR_CHARGEBACK_FEE: the chargeback words are spared, so CHG BACK and CHARGE BACK stay
#: chargebacks).
_PROCESSOR_CHARGEBACK_WORD = re.compile(r"(?<![A-Z])(?:CHARGE ?BACKS?|CHBK|CHGBK|CHG BACK)(?![A-Z])")
_PROCESSOR_ADJUSTMENT_WORD = re.compile(r"(?<![A-Z])(?:MERCH(?:ANT)? ADJ\w*|FINCL ADJ|BANKCD ADJ)(?![A-Z])")
_PROCESSOR_CHARGEBACK_FEE = re.compile(
    r"(?<![A-Z])(?:FEES?|FRAIS|SVC CHG|SERVICE CHARGE|CHRG|CHG(?! ?BACK)|CHARGES?(?! ?BACK))(?![A-Z])"
)


def processor_chargeback_debit(text: str) -> str | None:
    """The wording of a debit that is a processor's chargeback or adjustment, 'chargeback' or 'adjustment', else None.
    A flag's reader only: no classification, tier, figure or lender reading reads it (analysis/revenue_view.py
    debit_side_flags flags the row on the statement and the package, never deducted).

    The fee wording (_PROCESSOR_CHARGEBACK_FEE) refuses it (the bank's chargeback fee, CHBK CHRG), and a returned
    deposited item reads first (_deposit_return_debit: the DEP RETURN CHARGEBACK and a bank's row-leading CHARGE
    BACK of a deposited item are returns, never processor chargebacks). The caller reads the row's posting, duplicate
    mark, lender contributions and class."""
    if _PROCESSOR_CHARGEBACK_FEE.search(text) is not None or _deposit_return_debit(text):
        return None
    if _PROCESSOR_CHARGEBACK_WORD.search(text) is not None:
        return "chargeback"
    if _PROCESSOR_ADJUSTMENT_WORD.search(text) is not None:
        return "adjustment"
    return None


#: True revenue spec §6.2's package passes, §8.2: a cash device's word on a cash, branch, teller or ATM deposit
#: (_CASH_BRANCH_ATM_FORM): an ATM or ABM, cash or coin, a smart safe or a currency-processing device, a night deposit
#: or drop, a vault or a pre-encoded bag. A teller's, counter's or branch's deposit prints none of them.
_CASH_DEVICE_WORD = re.compile(
    r"(?<![A-Z])(?:ATM|ABM|CASH|COIN|SMART ?SAFE|CPS DEVICE|CURRENCY PROCESSING|NIGHT (?:DEP\w*|DROP)|VAULT"
    r"|PRE ?ENCODED)(?![A-Z])"
)
#: Arm R (a retail cash load, _RETAIL_CASH_LOAD) on its own: a retail network's cash load is cash.
_RETAIL_CASH_LOAD_FORM = re.compile(_RETAIL_CASH_LOAD)


def paper_or_cash_deposit(text: str) -> bool:
    """Whether a credit is a paper or cash deposit, which is never the receiving leg of an electronic transfer between
    two of the business's accounts. Read on the row before its receiver fields (`_before_receiver` of `revenue_text`):
    a check deposit (§8.3's _CHECK_DEPOSIT_FORM), a cash, branch, teller or ATM deposit (§8.2's _CASH_BRANCH_ATM_FORM)
    that prints a cash device's word (_CASH_DEVICE_WORD), or a retail cash load (arm R). A teller's, counter's
    or branch's deposit that prints no such word stays eligible: a branch transfer between two of the business's
    accounts can print that way on its receiving side. A package pass's reader only
    (analysis/package/passes.py `package_matches`, pass 2): no classification, tier, figure or lender reading reads
    it."""
    row = _before_receiver(revenue_text(text))
    if _CHECK_DEPOSIT_FORM.search(row) is not None:
        return True
    if _CASH_BRANCH_ATM_FORM.search(row) is not None and _CASH_DEVICE_WORD.search(row) is not None:
        return True
    return _RETAIL_CASH_LOAD_FORM.search(row) is not None


def _deposit_channel_credit(text: str) -> bool:
    """A credit a returned item may undo: a check deposit (§8.3), a cash, branch, teller or ATM deposit (§8.2), a
    deposit capture glued to its word (_DEPOSIT_CAPTURE_WORD), or a bare deposit that names no payer (§8.2's bare row
    printing a deposit word and no card word); never a wire, a person-to-person or push rail, or an electronic payment
    (a returned item names no payer, so it never undoes a named payer's payment)."""
    text = revenue_text(text)
    row = _before_receiver(text)
    if _is_wire_row(text) or _CONSUMER_P2P_RAIL.search(row) or _PUSH_RAIL.search(row):
        return False
    if _CHECK_DEPOSIT_FORM.search(row) or _DEPOSIT_CAPTURE_WORD.search(row):
        return True
    if _ELECTRONIC_PAYMENT_FORM.search(row):
        return False
    if _CASH_BRANCH_ATM_FORM.search(row):
        return True
    return _DEPOSIT_WORD.search(row) is not None and _CARD_WORD.search(row) is None and _is_bare_row(text)


def _deposit_return_pairs(
    records: list[TransactionClassification], duplicate_indexes: set[int],
) -> list[tuple[int, int]]:
    """§6.2: the (credit index, debit index) pairs of a debit that undoes a deposit (_deposit_return_debit) and an equal
    posted deposit-channel credit (_deposit_channel_credit) 0 to _DEPOSIT_RETURN_DAYS days before it. No shared word is
    needed: a returned item never prints the depositor's words. Each such debit, in row order, takes the earliest such
    credit not yet taken (then the first row), so a redeposit after the return, or beside a corrected deposit, stays
    counted.

    An undated credit or debit reads the row order (the deposit printed before the return), and an undo debit that
    names an equal credit's payer (_undo_debit_names_a_credit) is left to the shared-word pairing."""
    pairs: list[tuple[int, int]] = []
    taken: set[int] = set()
    for debit_index, debit in enumerate(records):
        if (
            debit_index in duplicate_indexes
            or debit.amount >= 0
            or not debit.is_posted
            or not _deposit_return_debit(debit.normalized_description)
            or _undo_debit_names_a_credit(records, duplicate_indexes, debit_index)
        ):
            continue
        amount = round(abs(debit.amount), 2)
        debit_date = parse_date(debit.date)
        best: tuple[tuple[date, int], int] | None = None
        for credit_index, credit in enumerate(records):
            if (
                credit_index in duplicate_indexes
                or credit_index in taken
                or credit.amount <= 0
                or not credit.is_posted
                or round(credit.amount, 2) != amount
            ):
                continue
            credit_date = parse_date(credit.date)
            if credit_date is None or debit_date is None:
                if credit_index >= debit_index:
                    continue
            elif not 0 <= (debit_date - credit_date).days <= _DEPOSIT_RETURN_DAYS:
                continue
            if not _deposit_channel_credit(credit.normalized_description):
                continue
            key = (credit_date or debit_date or date.min, credit_index)
            if best is None or key < best[0]:
                best = (key, credit_index)
        if best is not None:
            taken.add(best[1])
            pairs.append((best[1], debit_index))
    return pairs


def _undo_debit_names_a_credit(
    records: list[TransactionClassification], duplicate_indexes: set[int], debit_index: int,
) -> bool:
    """§6.2: a correction debit (_DEPOSIT_CORRECTION_MARKERS, one of pass 4's revenue-side markers) that shares a word
    or a family with an equal posted credit, 14 days either side, that is no deposit-channel credit. Such a correction
    undoes that credit ('ERROR CORRECTION CONTOSO SUPPLY LLC' undoes Contoso's payment), so the deposit mode never
    seizes it for an equal deposit; pass 4's shared-word pairing takes it. A returned item is never one: the name it
    prints is the returned check's maker, so it undoes the deposited check, never the maker's equal electronic
    payment. A deposit-channel credit sharing the correction's words is left to the deposit mode, which reads only
    deposits printed before the undo."""
    debit = records[debit_index]
    debit_text = debit.normalized_description
    if not _matches_any(debit_text, _DEPOSIT_CORRECTION_MARKERS):
        return False
    amount = round(abs(debit.amount), 2)
    debit_date = parse_date(debit.date)
    for credit_index, credit in enumerate(records):
        if (
            credit_index in duplicate_indexes
            or credit.amount <= 0
            or not credit.is_posted
            or round(credit.amount, 2) != amount
        ):
            continue
        credit_date = parse_date(credit.date)
        if credit_date is not None and debit_date is not None and abs((credit_date - debit_date).days) > 14:
            continue
        text = credit.normalized_description
        if not _deposit_channel_credit(text) and _descriptions_share_pair_context(text, debit_text):
            return True
    return False


def _credit_pair_marker(text: str, credit_markers: Sequence[re.Pattern[str]]) -> bool:
    """A credit-row-only pass-4 marker (`credit_markers`: step 3's 5.6 credit markers on the revenue side, none
    on the lender side). §7.11: with step 3's carve-out, so a provider's REMBOURSEMENT
    (_remboursement_from_a_provider), which leaves step 3, marks no pair either."""
    return any(
        pattern.search(text) is not None
        and not (pattern is _REMBOURSEMENT_WORD and _remboursement_from_a_provider(text))
        for pattern in credit_markers
    )


#: §6.2: the reversal pair reads the credit markers of step 3, return codes included. §20: on the revenue side, the
#: deposit undo markers too, read on either row.
_PAIR_MARKER_PATTERNS = (*_REVERSAL_CANCELLATION_CREDIT_PATTERNS, *_RETURN_CODE_CREDIT_PATTERNS, *_DEPOSIT_UNDO_MARKERS)
#: §20: the revenue side also reads step 3's 5.6 credit markers, on the credit row only: on a debit several of them are
#: a purchase (CHECKCARD <mmdd>), a repayment (REMBOURSEMENT) or a charge. With step 3's REMBOURSEMENT carve-out
#: (_credit_pair_marker).
_CREDIT_PAIR_MARKER_PATTERNS = _RETURN_REFUND_CREDIT_PATTERNS
#: §20: the lender side keeps classification 5.4's pairs. A pair the 5.4 credit markers make (step 3's markers
#: without the return codes and the French cancel words) alone zeroes the debit's lender, potential-lender,
#: withholding, insurance and flag contributions (setting its reversed_by) and sets the credit's
#: settlement-reversal fields and flag contribution; the widened markers change the credit's revenue reading only.
_LENDER_PAIR_MARKER_PATTERNS = tuple(
    pattern for pattern in _REVERSAL_CANCELLATION_CREDIT_PATTERNS if pattern is not _FRENCH_CANCEL_CREDIT_PATTERN
)


def _reversal_pairs(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
    markers: Sequence[re.Pattern[str]],
    marked: dict[int, bool] | None = None,
    *,
    credit_markers: Sequence[re.Pattern[str]] = (),
    seeded: Sequence[tuple[int, int]] = (),
    refuse: Callable[[int, int], bool] | None = None,
) -> list[tuple[int, int]]:
    """§6.2 pass 4: the (credit index, debit index) pairs, in credit order: an equal posted debit within 14 days that
    shares the credit's transaction family, where the credit or the debit prints one of `markers`; the nearest date,
    then the nearest row, wins, and a debit pairs once. `marked` caches each row's marker reading.

    `credit_markers` are read on a credit row only (step 3's 5.6 credit markers, with its REMBOURSEMENT carve-out:
    _credit_pair_marker), and the `seeded` pairs (the returned deposits, _deposit_return_pairs) are made first: their
    credits and debits pair no further.

    Lender side only: a (credit, debit) candidate `refuse` names is no candidate (_returns_a_later_lender_payment: a
    confirmed funder's paid payment or a potential lender's counted payment, dated after the return)."""
    marked = {} if marked is None else marked

    def has_marker(index: int) -> bool:
        if index not in marked:
            text = records[index].normalized_description
            marked[index] = _matches_any(text, markers) or (
                records[index].amount > 0 and _credit_pair_marker(text, credit_markers)
            )
        return marked[index]

    pairs: list[tuple[int, int]] = list(seeded)
    matched_debit_indexes: set[int] = {debit_index for _, debit_index in seeded}
    seeded_credits = {credit_index for credit_index, _ in seeded}
    # The posted, non-duplicate debits by their rounded amount, in row order, built once, so a credit visits only its
    # equal debits and in the order the scan of every row visited them: the pairs, the marker cache and the refuse
    # calls are the same. A NaN debit is listed nowhere, and the scan never paired one.
    debits_by_amount: dict[float, list[int]] = {}
    for debit_index, debit in enumerate(records):
        if debit_index not in duplicate_indexes and debit.amount < 0 and debit.is_posted:
            debits_by_amount.setdefault(round(abs(debit.amount), 2), []).append(debit_index)
    for credit_index, credit in enumerate(records):
        if (
            credit_index in duplicate_indexes
            or credit_index in seeded_credits
            or credit.amount <= 0
            or not credit.is_posted
        ):
            continue
        credit_has_marker = has_marker(credit_index)
        candidates: list[tuple[int, int]] = []
        credit_date = parse_date(credit.date)
        for debit_index in debits_by_amount.get(round(credit.amount, 2), ()):
            # Checked here, not when the list is built: the debits a credit takes change as the loop goes.
            if debit_index in matched_debit_indexes:
                continue
            debit = records[debit_index]
            if not credit_has_marker and not has_marker(debit_index):
                continue
            if refuse is not None and refuse(credit_index, debit_index):
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
        matched_debit_indexes.add(debit_index)
        pairs.append((credit_index, debit_index))
    return sorted(pairs)


def _apply_reversal_pair_context(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    updated = list(records)
    revenue_marked: dict[int, bool] = {}
    # The revenue side pairs each returned deposit with its deposit first.
    deposit_pairs = _deposit_return_pairs(records, duplicate_indexes)
    revenue_pairs = _reversal_pairs(
        records, duplicate_indexes, _PAIR_MARKER_PATTERNS, revenue_marked,
        credit_markers=_CREDIT_PAIR_MARKER_PATTERNS, seeded=deposit_pairs,
    )
    # The lender side's pairs are 5.4's. A statement where no row prints a widened-only marker, and where no returned
    # deposit paired, has the same pairs on both sides.
    widened = bool(deposit_pairs) or any(
        revenue_marked.get(index) and not _matches_any(records[index].normalized_description,
                                                        _LENDER_PAIR_MARKER_PATTERNS)
        for index in revenue_marked
    )

    def refuse(credit_index: int, debit_index: int) -> bool:
        return _returns_a_later_lender_payment(records, credit_index, debit_index)

    # The final review of round 2, F2(a): a confirmed funder's paid payment pairs on the lender side only with a return
    # dated on or after it; so does a potential lender's counted payment. Refusing a candidate only removes it, so a
    # statement where no revenue pair is such a candidate (and no widened marker reads) keeps the revenue side's pairs,
    # as before.
    lender_pairs = (
        _reversal_pairs(records, duplicate_indexes, _LENDER_PAIR_MARKER_PATTERNS, refuse=refuse)
        if widened or any(refuse(credit_index, debit_index) for credit_index, debit_index in revenue_pairs)
        else revenue_pairs
    )
    deposit_returns = set(deposit_pairs)
    for credit_index, debit_index in revenue_pairs:
        credit, debit = records[credit_index], records[debit_index]
        related_location = debit.source_location or f"transaction:{debit_index + 1}"
        returned_deposit = (credit_index, debit_index) in deposit_returns
        updated[credit_index] = _replace_revenue_state(
            credit,
            "non_revenue",
            match_method="matched_reversal_pair",
            matched_rule=(
                "returned_deposit_amount_date_match" if returned_deposit
                else "opposite_direction_amount_date_description_match"
            ),
            confidence_score=1.0,
            reason=(
                f"Deposit undone by the returned-item or correction row {related_location} (the same amount, 0 to "
                f"{_DEPOSIT_RETURN_DAYS} days later)." if returned_deposit else
                f"Credit matches reversal or cancellation row {related_location} by "
                "amount, date proximity, and transaction-family description."
            ),
            context_signals=(
                *credit.revenue_context_signals,
                "matched_opposite_direction_row",
                "returned_deposit" if returned_deposit else "amount_date_description_match",
            ),
            related_transaction=related_location,
        )
    for credit_index, debit_index in lender_pairs:
        credit, debit = records[credit_index], records[debit_index]
        related_location = debit.source_location or f"transaction:{debit_index + 1}"
        credit_location = credit.source_location or f"transaction:{credit_index + 1}"
        is_settlement_reversal = _matches_any(
            credit.normalized_description,
            _SETTLEMENT_REVERSAL_PATTERNS,
        ) or _matches_any(
            debit.normalized_description,
            _SETTLEMENT_REVERSAL_PATTERNS,
        )
        # A credit this pass pairs with a debit is money coming back, not a factor's
        # payout, so it leaves the flagged totals.
        updated[credit_index] = replace(
            updated[credit_index],
            reversal_of=related_location if is_settlement_reversal else None,
            settlement_reversal=is_settlement_reversal,
            contributes_to_flagged_totals=False,
        )
        if is_settlement_reversal and _is_paid_funder_debit(updated[debit_index]):
            # A confirmed funder's payment returned unpaid leaves paid to lenders and keeps its withholding and its
            # lender count; reversed_by is set as before.
            updated[debit_index] = replace(
                updated[debit_index],
                reversed_by=credit_location,
                contributes_to_potential_lender_count=False,
                contributes_to_lender_totals=False,
                contributes_to_potential_lender_totals=False,
                contributes_to_potential_withholding_exposure=False,
                contributes_to_insurance_totals=False,
                contributes_to_flagged_totals=False,
                returned_funder_payment_by=credit_location,
                reason=f"{updated[debit_index].reason} {_returned_unpaid_reason(credit_location)}",
                # A returned payoff attempt stays in the rate, as Q5 rules.
                **_returned_payoff_in_rate(updated[debit_index]),
            )
            updated[credit_index] = replace(updated[credit_index], returns_funder_payment=related_location)
        elif is_settlement_reversal:
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


def _is_paid_funder_debit(record: TransactionClassification) -> bool:
    """A confirmed funder's posted payment counted as paid to lenders, the debit a returned funder payment takes out
    of the paid figure."""
    return (
        record.amount < 0
        and record.is_posted
        and record.classification == "confirmed_lender"
        and record.contributes_to_lender_totals
    )


def _returned_payoff_in_rate(record: TransactionClassification) -> dict:
    """The worded-payoff rule meets Q5: the rule takes a PAID
    payoff-worded debit out of the withholding numerator, keeping it in paid to lenders; a returned one is out of
    paid, and Q5 keeps every returned funder payment in the rate ("keep it in the withholding rate"), so a payoff
    attempt the bank returned rejoins the numerator and is no lump sum. {} for every other debit."""
    if record.lump_sum_payoff is None:
        return {}
    return {"contributes_to_withholding_rate": True, "lump_sum_payoff": None}


def _is_counted_potential_payment(record: TransactionClassification) -> bool:
    """A potential lender's posted payment counted in the potential totals (keyword, registry or D6 potential
    lenders alike: D6 and the recurrence promotion run before pass 4)."""
    return (
        record.amount < 0
        and record.is_posted
        and record.classification == "potential_lender"
        and record.contributes_to_potential_lender_totals
    )


def _returns_a_later_lender_payment(
    records: list[TransactionClassification], credit_index: int, debit_index: int,
) -> bool:
    """The final review of round 2, F2(a) (its ruling "same amount, after it, a return/NSF form"; true revenue spec §6.2
    pass 4): whether a lender-side pair of this credit and debit would take a lender's payment dated AFTER the return,
    which the return cannot reverse. The pair is a settlement reversal (the credit or the debit prints a reversal word,
    the restore's own test) and the debit is a confirmed funder's paid payment (_is_paid_funder_debit) or a potential
    lender's counted payment (_is_counted_potential_payment, whose zeroing is §17.1's default (1)), dated after the
    credit; where either row prints no date, printed after it (rule D's order, _return_gap). Such a candidate is
    refused, so the return pairs with a payment on or before it, or with none (rule D and the package's pass 4 may still
    read a confirmed funder's). Every other debit keeps classification 5.4's pair, either way."""
    credit, debit = records[credit_index], records[debit_index]
    if not (_is_paid_funder_debit(debit) or _is_counted_potential_payment(debit)):
        return False
    if not (_matches_any(credit.normalized_description, _SETTLEMENT_REVERSAL_PATTERNS)
            or _matches_any(debit.normalized_description, _SETTLEMENT_REVERSAL_PATTERNS)):
        return False
    credit_date, debit_date = parse_date(credit.date), parse_date(debit.date)
    if credit_date is None or debit_date is None:
        return debit_index > credit_index
    return debit_date > credit_date


def _returned_unpaid_reason(credit_location: str, *, re_debited: bool = False) -> str:
    """The sentence a returned funder payment's debit adds to its reason. The ruling is named without its date: the
    analysis layer keeps no year literal outside date parsing (tests/test_no_statement_hardcodes.py). Pass 7c rewrites
    it for a payment its funder re-debited, which is out of the withholding rate (`re_debited`)."""
    if re_debited:
        return (f"Returned unpaid by {credit_location}: out of paid to lenders (the owner's ruling on the "
                "underwriter's Q5).")
    return (
        f"Returned unpaid by {credit_location}: out of paid to lenders, kept in the withholding rate (the owner's "
        "ruling on the underwriter's Q5)."
    )


#: True revenue spec §6.2 pass 7b, §11: the forms a bank prints when it returns the business's own payment unpaid (a
#: bounce), read on a credit by the returned-funder-payment pass alone (rule D, _returned_funder_payment_pairs): never a
#: refund, a card return, a correction or a reversal word on its own, and never with the fee words of _DEPOSIT_UNDO_FEE.
#: Arms (2) to (6) read only where no legal-form word follows on the row (a return code inside a company's name is no
#: bounce: SAMPLE RTN TRUCKING LLC). The two French arms are arms (a) and (c) of
#: _RETURN_REFUND_R2_B08_ARMS (EFFET RETOURNE, EFFET or CHEQUE REFUSE SANS PROVISION), copied here and read on the lender
#: side only (a test keeps them equal); their revenue-side reading is unchanged. The copies follow the arms'
#: lost-accent hardening (CH QUE, RETOURN), so a bounce printed with a lost accent is read as one here too (0 corpus
#: rows).
_RETURNED_PAYMENT_CREDIT_PATTERNS = (
    re.compile(r"\bRETURN OF POSTED (?:CHECK|ITEM)\b"),
    re.compile(r"(?<![A-Z])(?:ITEM RET|RET ITEM|RET NOT PAID)\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])(?:RTN|RETN)\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])NSF\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])(?:UNPAID|NOT PAID)\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])REJECT(?:ED)?\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"\bRETURN(?:ED)? (?:ITEM|ACH|PAYMENT|DEBIT|PAD|CHECK|CHEQUE|EFT|ENTRY|DR)S?\b"),
    re.compile(r"\b(?:ITEM|ACH|PAYMENT|DEBIT|PAD|EFT|CHECK|CHEQUE|ENTRY|DR)S? RETURN(?:ED)?\b"),
    re.compile(r"\bCREDIT RETURNED\b"),
    re.compile(r"(?<![A-Z])EFFETS? (?:RET|RETOUR|RETOURNEE?S?|RETOURN(?: E?E?S)?)\b"),
    re.compile(r"(?<![A-Z])(?:EFFETS?|CHEQUES?|CH QUES?|CHQ) REFUS\w* SANS PROV(?:ISION)?\b"),
)
#: Rule D's window: the return credit is dated 0 to this many days after the funder's debit. A 14-day window adds no
#: corpus row.
RETURNED_FUNDER_PAYMENT_WINDOW_DAYS = 7
#: Bank of America's return names the day the returned item was received ('RECEIVED ON 03/03', its slash normalized
#: to a space): a candidate debit dated that month and day is the one returned.
_RECEIVED_ON_DAY = re.compile(r"\bRECEIVED ON (\d{1,2}) ?(\d{1,2})\b")
#: The tiers a return credit rule D reads may carry: out of True (a credit the revenue side counts is never a return).
_RETURN_CREDIT_TIERS = frozenset({"non_revenue", "excluded_pending_review"})


def _returned_payment_credit(text: str) -> bool:
    """A credit printing a bounce form (_RETURNED_PAYMENT_CREDIT_PATTERNS) and no fee word."""
    return _matches_any(text, _RETURNED_PAYMENT_CREDIT_PATTERNS) and _DEPOSIT_UNDO_FEE.search(text) is None


def _received_on_day(text: str) -> tuple[int, int] | None:
    """The (month, day) Bank of America's 'RECEIVED ON <mm> <dd>' prints, or None."""
    found = _RECEIVED_ON_DAY.search(text)
    if found is None:
        return None
    month, day = int(found.group(1)), int(found.group(2))
    return (month, day) if 1 <= month <= 12 and 1 <= day <= 31 else None


def _return_gap(
    records: list[TransactionClassification], credit_index: int, debit_index: int,
) -> tuple[bool, int | None]:
    """(inside rule D's window, the gap in days): the credit dated 0 to RETURNED_FUNDER_PAYMENT_WINDOW_DAYS days after
    the debit; when either row is undated, the debit printed before the credit (the gap then None)."""
    credit_date, debit_date = parse_date(records[credit_index].date), parse_date(records[debit_index].date)
    if credit_date is None or debit_date is None:
        return debit_index < credit_index, None
    days = (credit_date - debit_date).days
    return 0 <= days <= RETURNED_FUNDER_PAYMENT_WINDOW_DAYS, days


def _returned_funder_payment_pairs(
    records: list[TransactionClassification], duplicate_indexes: set[int],
) -> list[tuple[int, int]]:
    """True revenue spec §6.2 pass 7b: rule D's (credit index, debit index) pairs, in the credits' (date, row) order,
    undated first.

    - Funder debits: posted, not duplicates, confirmed lenders' payments counted as paid (_is_paid_funder_debit) that
      no pair reversed and no earlier return took. Guard debits: every other posted debit that is no duplicate and no
      confirmed lender's (potential lenders included).
    - Return credits: posted, not duplicates, not a named pair's credit (another debit's reversed_by), not a lender
      credit, out of True (_RETURN_CREDIT_TIERS: never a credit the revenue side counts) and printing a bounce form
      (_returned_payment_credit).
    - A credit the revenue side paired (matched_reversal_pair) pairs only with its partner, when that is an unused
      funder debit of equal cents inside the window and order (_return_gap); otherwise it is left alone. A credit that
      names a confirmed funder (the credit index of the known payees) pairs only with that funder's debits.
    - Otherwise the candidates are the unused funder debits of equal cents inside the window and order. A candidate
      dated on the 'RECEIVED ON' day the credit prints wins; else the latest debit date, then the nearest row. The
      credit is skipped when an equal guard debit lies in the window as near as the chosen one, or undated.
    Each debit pairs once."""
    def location(index: int) -> str:
        return records[index].source_location or f"transaction:{index + 1}"

    def cents(index: int) -> int:
        return round(abs(records[index].amount) * 100)

    funder_debits = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and _is_paid_funder_debit(record)
        and record.reversed_by is None and record.returned_funder_payment_by is None
    ]
    if not funder_debits:
        return []
    guard_debits = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount < 0 and record.is_posted
        and record.classification != "confirmed_lender"
    ]
    paired_credits = {record.reversed_by for record in records if record.reversed_by}
    credits: list[tuple[date, int]] = []
    for index, record in enumerate(records):
        if (
            index in duplicate_indexes
            or record.amount <= 0
            or not record.is_posted
            or location(index) in paired_credits
            or record.contributes_to_lender_credit_exclusion
            or record.revenue_tier not in _RETURN_CREDIT_TIERS
            or not _returned_payment_credit(record.normalized_description)
        ):
            continue
        credits.append((parse_date(record.date) or date.min, index))
    credits.sort()
    used: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, credit_index in credits:
        credit = records[credit_index]
        named = match_known_payee(credit.normalized_description, credit=True)
        funder = named.entity if named is not None and named.state == "confirmed_lender" else None
        candidates = [
            index for index in funder_debits
            if index not in used and cents(index) == cents(credit_index)
            and (funder is None or records[index].canonical_entity == funder)
            and _return_gap(records, credit_index, index)[0]
        ]
        if credit.revenue_match_method == "matched_reversal_pair":
            partner = next((index for index in candidates if location(index) == credit.revenue_related_transaction),
                           None)
            if partner is not None:
                used.add(partner)
                pairs.append((credit_index, partner))
            continue
        if not candidates:
            continue
        received = _received_on_day(credit.normalized_description)

        def rank(index: int) -> tuple[int, int, int]:
            debit_date = parse_date(records[index].date)
            on_received = received is not None and debit_date is not None and (
                (debit_date.month, debit_date.day) == received)
            return (0 if on_received else 1, -(debit_date.toordinal() if debit_date else 0),
                    abs(credit_index - index))

        chosen = min(candidates, key=rank)
        chosen_gap = _return_gap(records, credit_index, chosen)[1]
        if any(
            cents(index) == cents(credit_index)
            and (window := _return_gap(records, credit_index, index))[0]
            and (window[1] is None or chosen_gap is None or window[1] <= chosen_gap)
            for index in guard_debits
        ):
            continue
        used.add(chosen)
        pairs.append((credit_index, chosen))
    return pairs


def _apply_returned_funder_payments(
    records: list[TransactionClassification], duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """True revenue spec §6.2 pass 7b, §11: each rule-D pair (_returned_funder_payment_pairs) takes the funder's debit
    out of paid to lenders (contributes_to_lender_totals and, as a named pair does, contributes_to_flagged_totals
    False; returned_funder_payment_by the credit's location; the reason's returned-unpaid sentence) and keeps its
    withholding and its lender count; the credit names the debit (returns_funder_payment). reversed_by,
    settlement_reversal and every revenue field stay as they are, so the reconciliation's reversal coverage, the
    settled-activity counts and every revenue reading are unchanged. It runs after pass 7, so the credit's tier is
    final, and before the duplicate finalisation."""
    pairs = _returned_funder_payment_pairs(records, duplicate_indexes)
    if not pairs:
        return records
    updated = list(records)
    for credit_index, debit_index in pairs:
        credit_location = records[credit_index].source_location or f"transaction:{credit_index + 1}"
        debit_location = records[debit_index].source_location or f"transaction:{debit_index + 1}"
        updated[debit_index] = replace(
            updated[debit_index],
            contributes_to_lender_totals=False,
            contributes_to_flagged_totals=False,
            returned_funder_payment_by=credit_location,
            reason=f"{updated[debit_index].reason} {_returned_unpaid_reason(credit_location)}",
            # A returned payoff attempt stays in the rate, as Q5 rules.
            **_returned_payoff_in_rate(updated[debit_index]),
        )
        updated[credit_index] = replace(updated[credit_index], returns_funder_payment=debit_location)
    return updated


def _represented_reason(debit_location: str, kind: str) -> str:
    """The sentence a re-debited returned payment adds to its reason (the owner's answer named without its date, as
    _returned_unpaid_reason names Q5's)."""
    how = "caught it up 2x" if kind == "caught_up" else "re-presented it"
    return (
        f"The funder {how} by {debit_location}: out of the withholding rate, which counts the obligation once (the "
        "owner's answer on re-presented payments, \"Count it once\")."
    )


def _apply_represented_funder_payments(
    records: list[TransactionClassification], duplicate_indexes: set[int], calendar: str = "US",
) -> list[TransactionClassification]:
    """True revenue spec §6.2 pass 7c, §11, §17.1: a confirmed funder's payment returned unpaid LEAVES the withholding
    numerator once the same funder re-debits it, the same cents off its cycle or an exact 2x catch-up, dated on or after
    the return and within one cadence gap after it (analysis.represented_payments.re_debits). The returned debit's
    `contributes_to_withholding_rate` is cleared, `represented_by` names the re-debit and its reason gains a sentence;
    nothing else moves (paid to lenders, the lender count, `reversed_by`, the re-debit itself and every revenue field
    stay as they were). Until such a re-debit exists the returned attempt stays in the numerator, as Q5 rules. It runs
    after pass 7b, which makes the last returned payments, and before the duplicate finalisation. A paid debit the rate
    leaves out (`out_of_rate_payment`: a worded lump-sum payoff) is never the re-debit, since the returned attempt would
    then leave the numerator beside it and the obligation would count zero times; it stays in the series the schedule
    and the 2x level are read from."""
    from analysis.represented_payments import Attempt, Returned, out_of_rate_payment, re_debits

    def location(index: int) -> str:
        return records[index].source_location or f"transaction:{index + 1}"

    by_location = {location(index): index for index in range(len(records))}
    attempts: list[Attempt] = []
    returned: list[Returned] = []
    out_of_rate: set[int] = set()
    for index, record in enumerate(records):
        if (index in duplicate_indexes or record.amount >= 0 or not record.is_posted
                or record.classification != "confirmed_lender" or not record.canonical_entity):
            continue
        if not (record.contributes_to_lender_totals or record.returned_funder_payment_by):
            continue
        day = parse_date(record.date)
        if day is None:
            continue
        attempt = Attempt(index, record.canonical_entity, day, round(abs(record.amount) * 100), (day, index))
        attempts.append(attempt)
        if out_of_rate_payment(record.returned_funder_payment_by, record.contributes_to_withholding_rate):
            out_of_rate.add(index)
        credit = by_location.get(record.returned_funder_payment_by or "")
        credit_day = parse_date(records[credit].date) if credit is not None else None
        if record.returned_funder_payment_by and record.contributes_to_withholding_rate and credit_day is not None:
            returned.append(Returned(attempt, credit_day))
    if not returned:
        return records
    found = re_debits(returned, attempts, calendar,
                      may_re_debit=lambda _returned, candidate: candidate.key not in out_of_rate)
    if not found:
        return records
    updated = list(records)
    for index, (debit_index, kind) in found.items():
        # Its Q5 sentence no longer says "kept in the withholding rate".
        credit_location = updated[index].returned_funder_payment_by
        head, standing, tail = updated[index].reason.rpartition(_returned_unpaid_reason(credit_location))
        reason = f"{head}{_returned_unpaid_reason(credit_location, re_debited=True)}{tail}" if standing else (
            updated[index].reason)
        updated[index] = replace(
            updated[index],
            contributes_to_withholding_rate=False,
            represented_by=location(debit_index),
            reason=f"{reason} {_represented_reason(location(debit_index), kind)}",
        )
    return updated


def _recurrence_vetoed(record: TransactionClassification, text: str) -> bool:
    """§7.0: a credit that never counts toward recurrence and is never lifted by it: payroll, the recurrence veto
    words and card-credit labels (read on the row before its receiver fields), FUNDING outside the three platforms
    that print it on settlements, under the $1 floor, or a direction conflict."""
    return (
        _recurrence_veto_wording(record, text)
        or record.amount < _MICRO_DEPOSIT_FLOOR
        or record.revenue_match_method == "direction_conflict"
        or not record.direction_consistent
    )


def _recurrence_veto_wording(record: TransactionClassification, text: str) -> bool:
    """§7.0: the worded part of the recurrence veto: payroll, a veto word or card-credit label, or FUNDING
    outside the three platforms that print it on settlements."""
    entity = record.revenue_canonical_entity
    # The holder's own words are read on the holder's name when the parser read it.
    holder = holder_reading(record.account_name, record.holder_name)
    return (
        record.classification == "payroll"
        or _recurrence_veto_word(text, holder, entity)
        or (
            entity not in _FUNDING_SETTLEMENT_ENTITIES
            and _recurrence_veto_word(text, holder, entity, _FUNDING_WORD)
        )
    )


def _recurrence_veto_word(
    text: str, account_name: str | None, entity: str | None, pattern: re.Pattern[str] = _RECURRENCE_VETO
) -> bool:
    """§7.0: the recurrence veto on the row before its receiver fields. On a store-name platform
    (_STORE_NAME_PAYOUT_ENTITIES) a veto word that is one of the holder's own words (its account name, or the name the
    bank prints in the receiver field), or the start of one (four letters or more), is not read: the platform prints
    the merchant's store name, which is the holder's, in its entry field ('DOORDASH INC DES:<store> CAPITA ...
    INDN:<store> CAPITAL GROUP'). On every other source, and on a row no registry source decided, a veto word always
    vetoes."""
    if entity not in _STORE_NAME_PAYOUT_ENTITIES or not store_name_printed(text, entity, account_name):
        return pattern.search(_before_receiver(text)) is not None
    holder = set(holder_words(account_name))
    for found in _RECEIVER_FIELD_VALUE.finditer(text):
        holder.update(_distinctive_words(found.group(0).split()[1:]))
    # FW wave 3 (W2-1): the words of a store name that is a run of the holder's name are spared at any length.
    run = store_name_run_words(text, entity, account_name)
    row = _before_receiver(text)
    for found in pattern.finditer(row):
        word = found.group(0)
        if word in run or (len(word) >= 4 and any(own == word or own.startswith(word) for own in holder)):
            continue
        return True
    return False


#: The matched rule of an operating-registry credit whose entry leads with a financing word.
PLATFORM_FINANCING_ENTRY_RULE = "platform_entry_leads_with_financing"


def _in_operating_pool(record: TransactionClassification) -> bool:
    """§7.0: only a credit the operating registry decided, or that an operating-source method or an
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
    """§7.8, §7.10, §14.1: a vetoed pool row of a wholesale auction or a property-management platform never counts and
    is never lifted, and still carries its branch's rule. Only a direction-consistent unverified row in an operating
    method is renamed; its classification stays. An auction row takes the auction's refusal (a payout-form row vetoed
    by a pay, financing or other veto word takes the financing or consumer rule; one vetoed only by the $1 floor has
    no rule of its own and is left as it is); a property row takes the owner or deposit wording rule when it prints
    that wording."""
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
    """§7.8, §14.1: the rule that refuses an auction credit on its wording (a buyer-payment reference, a floor-plan or
    financing word or a consumer entry, or no observed payout form), or None when it prints the payout form. The
    payout form is read with the receiver field's value removed (§5.2): the holder's name never verifies."""
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
    """§7.8: an auction credit that is not the auction's verified payout."""
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
    """§7.10: a property-management platform's credit printing owner, distribution or deposit wording."""
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
    """§7.8: a dealer-only wholesale auction verifies only its observed payout form, never a buyer-payment reference,
    a floor-plan or financing word or a consumer entry (§14.1), and never a credit paired with an equal same-auction
    debit within 14 days (each debit used once). The payout form is read with the receiver field's value removed
    (§5.2): the holder's name never verifies."""
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
    """§7.8: the index of an unused posted debit that names the auction (on its row or its wire BNF line), for the
    same amount to the cent, within 14 days of the credit; or None."""
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
    """§7.10: a property-management platform verifies by recurrence of its ACH payout shape only (three credits,
    or two in a business account), never by a related fee debit. A row printing owner, distribution or deposit
    wording is left out of the count and stays unverified; micro-deposits never count; a push-shaped row stays
    operating_source_requires_context. A verified row carries the property-management chip."""
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
    """§5.2: the payer key: the payer name's words without the generic words, at most the first four."""
    return tuple(word for word in payer_name(region).split() if word not in REVENUE_GENERIC_WORDS)[:4]


def _payer_first_distinctive_word(region: str) -> str | None:
    """§7.5, §8.1: the payer's first distinctive word: four or more letters, not an AP, bank-template,
    legal-suffix, generic or public-payer word, and not a common name-starter."""
    words = [word for word in _distinctive_words(payer_name(region).split()) if word not in _counter_debit_skip_words()]
    return _first_distinctive_word(words)


#: §7.5: the words of a card purchase's merchant pass 6 reads. The city and state follow them.
_CARD_MERCHANT_WORDS = 2


def _card_processor_code(token: str, printed: str) -> bool:
    """A card purchase's leading token is a processor code ('SQ *', 'TST*'): at most three letters printed right
    before a star, which normalization drops."""
    return (
        token.isalpha() and len(token) <= 3
        and re.search(rf"(?<![A-Za-z0-9]){re.escape(token)} ?\*", printed, re.IGNORECASE) is not None
    )


def _card_merchant_text(text: str, printed: str) -> str | None:
    """§7.5: a card purchase's merchant, after its card-form prefix and a processor code: its first two words, or
    None when the merchant's first token is a reference or a short token ('76', 'BP1234567', 'SQ *AB'). Never read
    past the merchant's first words, so the city printed after it is never the debit's word."""
    tokens = _payee_region(text).split()
    if tokens and _card_processor_code(tokens[0], printed):
        tokens = tokens[1:]
    if not tokens or _is_reference_token(tokens[0]) or len(tokens[0]) <= 2:
        return None
    return " ".join(tokens[:_CARD_MERCHANT_WORDS])


#: §17.1: a leading pre-authorized-debit label, on any bank (CIBC's `PRE-AUTH DEBIT [<reference>] <name> [BUSINESS
#: PAD]`, `PRE-AUTHORIZED DEBIT`, `PREAUTHORISED DEBIT`), with the references printed after it: cut from a debit before
#: the counter-debit readings, so the funder's name is read (`PRE AUTH DEBIT 0000000 WOODGROVE CAPITAL BUSINESS PAD`
#: reads WOODGROVE, never AUTH). A numbered company's number after it is no reference (`PRE AUTH DEBIT 1234567 ONTARIO
#: INC` keeps `1234567 ONTARIO INC`). The D6 lender names are not read through it (_unknown_payee_tokens is unchanged).
_PAD_LABEL_BEFORE_PAYEE = re.compile(
    r"^(?:PRE ?AUTH(?:ORI[SZ]ED)?|PREAUTH(?:ORI[SZ]ED)?) DEBIT"
    rf"(?: (?!\d{{6,10}} {_PROVINCE_NOT_A_NAME_START}|\d{{4}} \d{{4}} {_QUEBEC}\b)\d+)*(?= |$) ?"
)


@cache
def _posting_type_label_pattern(bank: str) -> re.Pattern[str] | None:
    """The posting-type labels of the statement's bank (BANK_POSTING_TYPE_LABELS, read when the bank field contains one
    of the entry's bank words as whole words, in any case), longest first, as a pattern that reads one of them at a
    text's start with a word after it; None when the bank prints none."""
    field = normalize_transaction_description(bank).strip().upper()
    labels: set[str] = set()
    for markers, printed in BANK_POSTING_TYPE_LABELS:
        if any(re.search(r"(?<![A-Z])" + re.escape(marker) + r"(?![A-Z])", field) for marker in markers):
            labels.update(printed)
    if not labels:
        return None
    alternatives = "|".join(re.escape(label) for label in sorted(labels, key=lambda label: (-len(label), label)))
    return re.compile(rf"^(?:{alternatives}) (?=\S)")


def _without_posting_type_label(text: str, bank: str | None) -> str:
    """`text` without ONE posting-type label of the statement's bank (`bank`, Statement.bank) that starts it and has a
    word after it: RBC's `INSURANCE`, `INVESTMENT`, `FEES DUES`, `EQUIPMENT RENT` and `PAY EMPLOYEE VENDOR`,
    Scotiabank's `INVESTMENT` (BANK_POSTING_TYPE_LABELS). The bank's own label names no party, so on RBC `INSURANCE
    SUNLIFE MED INS` reads SUNLIFE and `INVESTMENT MERCH PAD` reads MERCH. Any other bank, or no bank, reads `text`
    unchanged (`INSURANCE AUTO AUCTIONS` keeps its first word)."""
    if not bank:
        return text
    pattern = _posting_type_label_pattern(bank)
    return text if pattern is None else pattern.sub("", text, count=1)


def _counter_debit_text(record: TransactionClassification) -> tuple[str | None, bool]:
    """§7.5, §8.1: the text a posted debit's counter-debit readings read, and whether it is a card purchase (its
    card-form prefix matched): on a card purchase its merchant's first two words (_card_merchant_text; None when it
    prints none), else the text after the prefix. On a debit that is no card purchase, without the statement's bank's
    posting-type label and then without a leading pre-authorized-debit label."""
    text, card_form = _CARD_FORM_DEBIT_PREFIX.subn("", record.normalized_description, count=1)
    if card_form:
        return _card_merchant_text(text, record.original_description or ""), True
    return _PAD_LABEL_BEFORE_PAYEE.sub("", _without_posting_type_label(text, record.bank), count=1), False


def _debit_word_reading(
    record: TransactionClassification, *, keep_places: bool = False,
) -> tuple[str | None, bool]:
    """§7.5, §8.1: a posted debit's first distinctive word, read on its D11 payee words; on a card purchase, after
    its leading card-form words and MMDD date and only on its merchant's first two words (D11 itself is unchanged).
    The second value says whether the debit is a card purchase (its card-form prefix matched): pass 7 leaves a card
    purchase's merchant out of payer_also_debited (5.6, A1 census). Never a rail's, a bank label's or (unless
    `keep_places`) a place's word (_without_not_a_payer). Read on _counter_debit_text, so a debit that is no card
    purchase is read without its bank's posting-type label and a leading pre-authorized-debit label."""
    text, card_form = _counter_debit_text(record)
    if text is None:
        return None, True
    words = [
        word for word in _distinctive_words(_without_not_a_payer(_unknown_payee_tokens(text), keep_places=keep_places))
        if word not in _counter_debit_skip_words()
    ]
    return _first_distinctive_word(words), card_form


def _debit_first_distinctive_word(record: TransactionClassification) -> str | None:
    """§7.5, §8.1: a posted debit's first distinctive word (_debit_word_reading), a card purchase's merchant
    included. Passes 6 and 7 read _debit_word_reading itself, with its card flag."""
    return _debit_word_reading(record)[0]


#: Words that never make a payer's or a debit's first distinctive word when passes 6 and 7 compare a payer with the
#: statement's debits (counter_debit_payer_reading), beside _counter_debit_skip_words. Generic words let unrelated
#: companies match: '<initials> EXPRESS INC' against American Express, 'MERCHANT SERVICES' against another processor's
#: 'MERCHANT SERVICE ... FEE', a utility against another utility, INCOME, PAIEMENT, POSTED, SERVICE, TRSFR. A bank's
#: own name prints as its channel (a bank's online payment, its merchant deposit, its card, its ATM, its pay product),
#: never as the payer the holder also pays; only the names the corpus prints that way are listed (a bank's name
#: printed as the holder's own account at it, a transfer to or from the holder's savings there, keeps matching: the
#: guard keeps every transfer and lender match).
_COUNTER_DEBIT_GENERIC_WORDS = frozenset({
    "MERCHANT", "UTILITIES", "EXPRESS", "INCOME", "PAIEMENT", "POSTED", "SERVICE", "SERVICES", "TRSFR",
    "CHASE", "TRUIST", "BLUEVINE",
})
#: §5.2: words that name no counterparty, which the counter-debit readings skip (counter_debit_payer_reading's legacy
#: word, _debit_word_reading, _counter_debit_head; never the payer's first distinctive word other readers group payers
#: by, nor _counter_debit_skip_words): the person-to-person rails' and RBC's French label's own words (a Zelle or
#: e-Transfer debit keeps its recipient's name; _COUNTER_DEBIT_LABEL_WORDS), and the place words
#: (_COUNTER_DEBIT_PLACE_WORDS): the US states (the words of a two-word state that are no generic word or name-starter),
#: the provinces and territories, CANADA, CANADIAN and AMERICAN (a town's or a nation's adjective names a place, never a
#: payer). The CASH APP phrase is skipped whole (_without_not_a_payer). The lender hold (payer_debited_as_lender) keeps
#: the place words (`keep_places`): a funder may carry a state's name ('<STATE> VENTURE'), and that hold never lets a
#: funder's money into True. Scotiabank's ACHDEBIT label ('MISC PAYMENT ACHDEBIT <name> CA') is a label word too.
_COUNTER_DEBIT_LABEL_WORDS = frozenset({
    "ZELLE", "INTERAC", "VENMO", "POPMONEY", "AUTODEPOSIT", "CASHAPP", "PAIEMENT", "ACHDEBIT",
})
_COUNTER_DEBIT_PLACE_WORDS = frozenset("""
ALABAMA ALASKA ARIZONA ARKANSAS CALIFORNIA COLORADO CONNECTICUT DELAWARE FLORIDA GEORGIA HAWAII IDAHO ILLINOIS INDIANA
IOWA KANSAS KENTUCKY LOUISIANA MAINE MARYLAND MASSACHUSETTS MICHIGAN MINNESOTA MISSISSIPPI MISSOURI MONTANA NEBRASKA
NEVADA HAMPSHIRE JERSEY MEXICO YORK CAROLINA DAKOTA OHIO OKLAHOMA OREGON PENNSYLVANIA RHODE TENNESSEE TEXAS UTAH
VERMONT VIRGINIA WASHINGTON WISCONSIN WYOMING
ONTARIO QUEBEC ALBERTA MANITOBA SASKATCHEWAN BRITISH COLUMBIA NOVA SCOTIA BRUNSWICK NEWFOUNDLAND LABRADOR PRINCE EDWARD
YUKON NORTHWEST TERRITORIES NUNAVUT CANADA CANADIAN AMERICAN
""".split())
_COUNTER_DEBIT_NOT_A_PAYER = _COUNTER_DEBIT_LABEL_WORDS | _COUNTER_DEBIT_PLACE_WORDS


def _without_not_a_payer(words: Sequence[str], *, keep_places: bool = False) -> list[str]:
    """`words` without _COUNTER_DEBIT_NOT_A_PAYER (with `keep_places`, without the label words only) and the CASH APP
    phrase."""
    skip = _COUNTER_DEBIT_LABEL_WORDS if keep_places else _COUNTER_DEBIT_NOT_A_PAYER
    kept: list[str] = []
    skip_next = False
    for index, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        if word == "CASH" and index + 1 < len(words) and words[index + 1] == "APP":
            skip_next = True
            continue
        if word not in skip:
            kept.append(word)
    return kept


#: A payroll provider whose name has three letters is still a counter-debit word: an 'ADP TAX' credit beside the
#: holder's own 'ADP TAX' debits is its tax impound coming back.
_SHORT_PAYROLL_PROVIDER_WORDS = frozenset({"ADP"})
#: A name with a reference glued after it ('FABRIKAMGROUPINC1', 'FORWARDFINUSA1'): its three or more letters, never
#: a masked run of X, read as a word once the digits are split off.
_GLUED_DIGIT_RUN = re.compile(r"(?<![A-Z0-9])(?!X+\d)([A-Z]{3,})(\d+)(?![A-Z0-9])")
#: The words after the first distinctive word that its glued forms take ('CONTOSO RIDGE' is
#: 'CONTOSORIDGE').
_GLUED_FORM_WORDS = 2


def _split_glued_digits(text: str) -> str:
    """The text with each glued digit run split off its name ('FABRIKAMUSA1' reads 'FABRIKAMUSA 1')."""
    return _GLUED_DIGIT_RUN.sub(r"\1 \2", text)


@dataclass(frozen=True)
class CounterDebitReading:
    """How passes 6 and 7 compare a payer with a posted debit. `legacy` is the 5.6 first distinctive word
    (_payer_first_distinctive_word, _debit_word_reading); a transfer, wire, person-to-person or lender debit still
    matches on it. `keys` are the B4 forms: the first distinctive word read without _COUNTER_DEBIT_GENERIC_WORDS, a
    three-letter payroll provider allowed, and that word glued to the next one or two ('CONTOSO RIDGE' matches
    'CONTOSORIDGE'), read on the text as printed and with its glued digit runs split off. `heads` are each first word
    with the words after it, which payer_debited_as_lender's prefix comparison reads. §5.2, §8.1: `number`, a numbered
    company's number (Quebec's NNNN NNNN joined), read only where the numbered-company form prints
    (counter_debit_payer_reading, counter_debit_debit_reading; never any digits alone), which true_revenue._same_payer
    matches before the words: a numbered company's words are a province and a legal form, which name no payer."""

    legacy: str | None
    keys: frozenset[str]
    heads: tuple[tuple[str, tuple[str, ...]], ...]
    number: str | None = None


_NO_COUNTER_DEBIT_READING = CounterDebitReading(None, frozenset(), ())


def _numbered_form_number(found: re.Match[str]) -> str:
    """The number of a _NUMBERED_FORM match: its six to ten digits, or Quebec's two groups joined ('1234 5678
    QUEBEC INC' reads '12345678')."""
    return found.group("number") or found.group("first") + found.group("second")


#: The leading number of a payer region _NUMBERED_COMPANY_REGION reads: Quebec's two groups, or the six to ten
#: digits.
_NUMBERED_REGION_NUMBER = re.compile(
    rf"^(?:(?P<first>\d{{4}}) (?P<second>\d{{4}}) {_QUEBEC}\b|(?P<number>\d{{6,10}})\b)"
)


def _payer_region_number(region: str) -> tuple[str | None, str]:
    """§5.2: a credit's numbered-company number and the region its words are read on. The region is read past a leading
    date (as numbered_company reads it): when it is a numbered company's (_NUMBERED_COMPANY_REGION), the number is its
    leading digits (Quebec's form joined); when the numbered-company form starts it (_NUMBERED_FORM), its words are
    read without that form, so the province, its cut, the legal forms and BMO's code name no payer ('7654321 ONTA AP
    CC' reads only its number; '1234567 ONTARIO INC O A NORTHWIND BAKERY' its number and NORTHWIND)."""
    numbered = _skip_numbered_leading_date(region)
    number = None
    if _NUMBERED_COMPANY_REGION.match(numbered) is not None:
        found = _NUMBERED_REGION_NUMBER.match(numbered)
        if found is not None:
            number = _numbered_form_number(found)
    form = _NUMBERED_FORM.match(numbered)
    return number, region if form is None else numbered[form.end():].strip()


def _counter_debit_head(
    words: Sequence[str], *, keep_places: bool = False,
) -> tuple[str, tuple[str, ...]] | None:
    """The first distinctive word of `words` (four letters or more and no name-starter, or a three-letter payroll
    provider), the generic words and banks' names left out, with the distinctive words after it. And the words that
    name no counterparty (_without_not_a_payer; the place words kept with `keep_places`)."""
    skip = _counter_debit_skip_words() | _COUNTER_DEBIT_GENERIC_WORDS
    kept = [
        word for word in _distinctive_words(_without_not_a_payer(words, keep_places=keep_places)) if word not in skip
    ]
    for index, word in enumerate(kept):
        if (len(word) >= 4 and word not in _NAME_STARTERS) or word in _SHORT_PAYROLL_PROVIDER_WORDS:
            return word, tuple(kept[index + 1:])
    return None


def _counter_debit_reading(
    legacy: str | None, readings: Sequence[Sequence[str]], *, keep_places: bool = False, number: str | None = None,
) -> CounterDebitReading:
    heads: list[tuple[str, tuple[str, ...]]] = []
    for words in readings:
        head = _counter_debit_head(words, keep_places=keep_places)
        if head is not None and head not in heads:
            heads.append(head)
    keys = frozenset(
        word + "".join(following[:count]) for word, following in heads for count in range(_GLUED_FORM_WORDS + 1)
        if count <= len(following)
    )
    return CounterDebitReading(legacy, keys, tuple(heads), number)


def counter_debit_payer_reading(
    region: str, *, keep_places: bool = False, bank: str | None = None,
) -> CounterDebitReading:
    """A credit's counter-debit reading, on its payer region (§5.2: never a receiver field). Its legacy word is the
    payer's first distinctive word (_payer_first_distinctive_word) read without the words that name no counterparty
    (_without_not_a_payer; with `keep_places`, the label words only: the lender hold's reading). The region is read
    without the statement's bank's posting-type label; a numbered company's region gives its number, and its words are
    read without the numbered-company form."""
    if not region:
        return _NO_COUNTER_DEBIT_READING
    number, region = _payer_region_number(_without_posting_type_label(region, bank))
    legacy = _first_distinctive_word([
        word for word in _distinctive_words(_without_not_a_payer(payer_name(region).split(), keep_places=keep_places))
        if word not in _counter_debit_skip_words()
    ])
    return _counter_debit_reading(
        legacy, (payer_name(region).split(), payer_name(_split_glued_digits(region)).split()), keep_places=keep_places,
        number=number,
    )


def counter_debit_debit_reading(
    record: TransactionClassification, *, keep_places: bool = False,
) -> tuple[CounterDebitReading, bool]:
    """A posted debit's counter-debit reading on its D11 payee words (a card purchase's merchant, as
    _debit_word_reading reads it), and whether it is a card purchase. The glued-digit reading is taken only when the
    printed one finds no word: D11 stops a name at its first reference, so splitting a leading reference ('CHECK1234
    <name>') would cut the name the printed text reads. `keep_places` keeps the place words (the lender hold's
    reading, _without_not_a_payer). Read on _counter_debit_text; `number` is the first numbered-company form the debit
    prints outside its receiver fields' values ('CHEQUE 1234567' none), its word readings unchanged (they stop at the
    number)."""
    legacy, card_purchase = _debit_word_reading(record, keep_places=keep_places)
    text, _ = _counter_debit_text(record)
    if text is None:
        return _NO_COUNTER_DEBIT_READING, card_purchase
    printed = _unknown_payee_tokens(text)
    readings: list[Sequence[str]] = [printed]
    if _counter_debit_head(printed, keep_places=keep_places) is None:
        readings.append(_unknown_payee_tokens(_split_glued_digits(text)))
    found = _NUMBERED_FORM.search(_without_receiver_value(text))
    number = None if found is None else _numbered_form_number(found)
    return _counter_debit_reading(legacy, readings, keep_places=keep_places, number=number), card_purchase


def _apply_payer_remittance_counter_debit_guard(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 6 (§6.2, §7.5): a credit the payer-remittance rule verified goes back to unverified when a
    posted debit in the same statement shares the payer's first distinctive word (an own account, an affiliate or a
    funder that collects). §20: a card purchase the classifier names as no lender or financing payee is left out
    (_debit_word_reading's card flag), as pass 7's payer_also_debited leaves it out: buying from a customer
    by card is spending, never the circular money the guard holds. The debits are read by kind as pass 7's holds read
    them (true_revenue.counter_debits, debited_as_lender, also_debited): the bank's receiving fee, a processor's fee
    beside a settlement and a bill the holder pays never demote the remittance; a lender debit is compared by whole
    words and registry entity, never by prefix (this pass demotes a verified row)."""
    debits = counter_debits(records, duplicate_indexes)
    updated = list(records)
    for index, record in enumerate(records):
        if record.revenue_match_method != "payer_remittance_descriptor":
            continue
        text = revenue_text(record.normalized_description)
        credit = counter_credit(record, text, payer_region(text))
        if not (debited_as_lender(credit, debits, prefix=False) or also_debited(credit, debits)):
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
    # The bank card formats the POS rule does not read, never on a row that names financing, a bank or an
    # organisation (read on the whole row, not on the D11 payee words, which are the card template).
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


def _names_only_channel_words(payee: Sequence[str], text: str) -> bool:
    """The D6 payee words are all channel words and the payee region of the normalized row `text` prints no
    organisation cue. D11's key stops at the first reference token once a name has started, so a format that prints
    a reference before the merchant keys as its template ('RECURRING PAYMENT AUTHORIZED ON 01 02 FAB HOLDINGS LLC
    CARD 4321' keys as RECURRING AUTHORIZED ON): the cue keeps such a row in review, as the card veto does (A1)."""
    return (
        bool(payee)
        and all(token in _CHANNEL_VOCABULARY for token in payee)
        and not any(token in _ORGANISATION_CUES for token in _payee_region(text).split())
    )


#: Card-posting labels the POS rule does not read, read on the normalized row with no ACH guard, as _POS_PATTERNS
#: are. MOBILE, RETAIL and PIN PURCHASE and the French ACHAT join the POS rule itself.
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
#: Wealthsimple Chequing prints a card purchase as the bare merchant; its other debits carry one of these words
#: (seen in 32 corpus accounts; its bill-payment print form is unverified: re-check when one arrives).
_WEALTHSIMPLE_CHANNEL_PATTERN = re.compile(
    r"\b(?:TRANSFER|TRANSFERT|INTERAC|PRE ?AUTHORI[ZS]ED|PAD|DEBIT|BILL|PAYMENT|EFT|WITHDRAWAL|DEPOSIT|CHEQUE|CHECK|"
    r"LOAN|WIRE|FEE)\b"
)
#: The card network's merchant location, 'NAME, CITY, ST' (Bluevine) or 'NAME ###, CITY, ST, USA' (Found), read
#: on the printed text of those two banks' rows only, and only without an ACH field mark. Bluevine's glued 'CITY,
#: NYUS' variant is a known non-match.
_CARD_LOCATION_SUFFIX_PATTERN = re.compile(
    r",\s*[A-Za-z][A-Za-z .'-]*?\s*,\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|"
    r"MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|PR|GU|VI|AB|BC|MB|NB|NL|NS|NT|NU|"
    r"ON|PE|QC|SK|YT)\s*(?:,\s*USA)?\s*$"
)
_CARD_LOCATION_SUFFIX_BANKS = frozenset({"Bluevine", "Lead Bank (Found)"})


#: Person-to-person, wallet and card-push rails the transfer rule does not read. D6 only: the transfer rule runs
#: before the known payee (step 6 before 7), so widening it would hide a counted funder paid by e-Transfer.
#: VIREMENT covers every French RBC transfer line (Interac e-Transfer, 'Virement envoye', 'Virement par Banque en
#: direct'). Bare WISE is never a rail (WISE CHOICE, FINWISE).
_P2P_RAIL_PATTERNS = (
    re.compile(r"\bVIREMENTS?\b"),
    re.compile(r"\bZEL (?:TO|FROM)\b"),
    re.compile(r"^(?:PMNT|PAYMENT) SENT \d{2} ?\d{2}\b"),
    re.compile(r"\bAPPLE (?:CASH|WALLET)\b"),
    re.compile(r"\b(?:WISE (?:INC|US INC)|TRANSFERWISE)\b|\bDES WISE\b"),
    re.compile(r"\bIAT PAYPAL\b"),
    re.compile(r"\bGREENLIGHT DES APP\b"),
)
#: Transfer templates the 5.2 transfer-word skip does not read. Each fires only for a payee that names no
#: organisation (D11 would publish 'Unidentified lender obligation') and a row that names no financing.
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
#: Rows whose own words say they cannot pay a funder: the holder's cash withdrawal in the formats the ATM rule does
#: not read (only reference tokens or NETWORK may sit between ATM/ABM and the withdrawal word, so a payee name never
#: fills the gap), the offset of an ACH batch the holder sent from its own bank's portal (inferred from the row
#: shape; D11 already drops the batch name from the review entry), and school, tuition and childcare billing.
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
#: Vendors and other payees that never lend, read on the D11 payee words only (never an entry description: SBFS/Rapid
#: Finance prints 'Vendor Pay'; never the holder: a holder named '... Distributions' pays Credibly), guarded by the
#: lending words below and by the holder's own name. DISTRIBUT* also clears recurring owner distributions. Names join
#: only after collision_check.py prints no registry or ledger hit.
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
#: A Bill.com or Melio payment is a vendor's only when the row prints an invoice number.
_BILL_PAY_PLATFORM_PATTERN = re.compile(r"^(?:BILL COM|MELIO)\b")
_INVOICE_NUMBER_PATTERN = re.compile(r"\bINV \d")
#: The vendor skip's lending guard: the shared roots plus the Canadian pre-authorized-debit channel word.
_VENDOR_LENDING_GUARD = re.compile(_FINANCING_ROOT_PATTERN.pattern + r"|\bPAD\b")
#: The account holder's name words, read without the module normalizer: classifying a row normalizes exactly one
#: text (tests/test_classifier_lookups.py::test_each_row_is_normalized_exactly_once).
_HOLDER_WORD = re.compile(r"[A-Z0-9]+")


def _payee_words_are_bounded(text: str) -> bool:
    """Whether an ACH field, or a reference token after the payee's first name word, ends the payee's words before
    the normalized row `text` ends. A row that is one run of words (Regions '<funder> ACHPMT <receiver>', Bluevine
    '<funder> PAY PAYMENT TO <receiver>') can end with the account holder's name."""
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
    """The D11 payee words (or, on a bounded row, the originator segment, which then never reads a receiver field)
    name a vendor or another payee that never lends, the row prints no lending word (outside the matched vendor words,
    which carry none themselves), and those words carry none of the account holder's own name words. On a row that is
    one run of words the segment is never read, and when the holder's name is unknown the vendor word must be the
    payee's first word."""
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


#: Tax authorities and government agencies printed without TAX, IRS or CRA, read on the payee region only (never
#: an entry description or memo) and only for a payee that names no organisation. The row stays 'other': the tax
#: rule has no amount guard and runs before the known payee, so it is not widened.
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
#: Payees the financing-keyword recurrence never promotes: a government finance department (FINANCE is its
#: name, not a loan) and a retailer named ADVANCE. Their single rows stay 'other' / financing_keyword_review.
_GOVERNMENT_FINANCE_DEPARTMENT_PATTERNS = (
    re.compile(r"\b(?:DEPT|DEPARTMENT|MINISTRY|MIN|MINISTERE|DIV) (?:OF |DES )?FINANCES?\b"),
    re.compile(r"\bFINANCE DEPT\b"),
)
_RETAILER_ADVANCE_PATTERNS = (re.compile(r"\bADVANCE (?:AUTO PARTS|STORES)\b"),)
#: A court-ordered family-support payment through a state conduit is not an MCA remittance. Read before the
#: receiver fields (a holder named '... Child Support Svcs' never silences its funder). GARNISH, LEVY, LEGAL
#: ORDER, bare SDU and CSE stay out: an MCA judgment creditor collects through a law office or a marshal.
_FAMILY_SUPPORT_WORD_PATTERNS = (
    re.compile(r"\bCHI?LD ?SUPP(?:ORT|T)?\b"),
    re.compile(r"\bFAM(?:ILY)? SUPP(?:ORT)? (?:REG(?:ISTRY)?|PAYMENT CENTER|PMT CTR|PAYMENT CTR)\b"),
    re.compile(r"\bSTATE DISBURSEMENT UNIT\b"),
)
#: Owner money is not an MCA remittance: a draw or distribution to an owner, member, partner or shareholder, a
#: dividend, a per diem, a guaranteed payment. Read before the receiver fields, with the veto (DIVIDEND FINANCE
#: is a lender); a bare DISTRIBUTION is a vendor's name.
_OWNER_PAY_WORD_PATTERNS = (
    re.compile(r"\b(?:OWNERS?|MEMBERS?|PARTNERS?|SHAREHOLDERS?) (?:DRAWS?|DISTRIBUTIONS?)\b"),
    re.compile(r"\bPER DIEM\b"),
    re.compile(r"\bGUARANTEED PAYMENTS?\b"),
    re.compile(r"\bDIVIDENDS?\b"),
)
#: A payments platform paying a recipient it names ('Pay To: <name>'): the platform is the originator, not a
#: creditor. Only a person recipient is skipped: Payoneer's Capital Advance is collected by ACH bank debit (an
#: alternative position), so an organisation recipient, the platform itself or no recipient stays reviewed.
_PLATFORM_PAYOUT_PATTERN = re.compile(r"\bPAYONEER\b.*\bPAY TO\b(?P<recipient>.*?)(?:\bPAYMENT DATE\b|\bTRN\b|$)")


def _is_platform_payout_to_person(text: str) -> bool:
    """The shared veto reads the whole row `text`, the recipient included. The skip's own words (PAYONEER, PAY TO,
    PAYMENT DATE, TRN) carry no financing root, so nothing is removed first: the pattern's spans are never hidden
    from the veto."""
    found = _PLATFORM_PAYOUT_PATTERN.search(text)
    if found is None:
        return False
    recipient = [token for token in found.group("recipient").split()
                 if len(token) > 1 and not _is_reference_token(token)]
    return bool(recipient) and not any(
        token in _ORGANISATION_CUES or token == "PAYONEER" for token in recipient
    ) and not _names_financing(text)


#: D6 does not take a same-amount group under this amount whose payee names no organisation (it would publish as
#: 'Unidentified lender obligation') and whose row names no financing. Strict: a 25-dollar debit promotes. A
#: named payee promotes at any amount. A whole number: analysis/ carries no exact-cent literal
#: (tests/test_no_statement_hardcodes.py).
_D6_MIN_FIXED_DEBIT = 25
#: A payment processor's own small charge to its merchant, through its merchant-services spelling: Square's
#: seller-account entry code (SQ + the entry date yymmdd) and Intuit Payment Solutions. Capped at 50 dollars
#: (Intuit's fees and chargebacks, Square's small charges): these rails also carry invoice payments to third parties
#: in the thousands, so a fixed debit above the cap stays in review. Never with loan or capital wording, including
#: Square's glued loan codes (SQCAP, SQ LOAN). A whole number (tests/test_no_statement_hardcodes.py).
_PROCESSOR_ACCOUNT_DEBIT_PATTERNS = (
    re.compile(r"\bSQUARE\b.*\bSQ ?\d{6}\b|\bSQ ?\d{6}\b.*\bSQUARE\b"),
    re.compile(r"\bINTUIT (?:PYMT|PMT|PAYMENTS?) SOL(?:N|NS|UTIONS?)?\b"),
)
_PROCESSOR_DEBIT_FINANCING_GUARD = re.compile(
    r"\bLOANS?\b|\bADVANCE\b|\bFINANC(?:E|ING|IAL)\b|\bFUND(?:ER|ING)\b|\bCAP(?:ITAL)?(?![A-Z])|\bMCA\b"
    r"|\bSQ ?CAP|\bSQ ?LOAN|\bLENDING\b"
)
_PROCESSOR_ACCOUNT_CHARGE_MAX = 50
#: An insurer whose name the ACH field cut short (INSU, INSUR, INSURA, INSURAN, INSURANC: the 16-character company
#: name or the 10-character entry description). Read on the D11 payee words only: the holder's name (INDN, IND
#: NAME, or unlabeled) never decides. INSURED, INSURER and the bare INS stay out.
_TRUNCATED_INSURANCE_WORD_PATTERN = re.compile(r"\bINSU(?:R|RA|RAN|RANC)?\b")
#: Phone and cable carriers, matched at the START of the payee's leading words (_leading_payee_words), so a carrier
#: printed after the payee's own name (a receiver that is a wireless dealer) never decides. Brand names only; BELL,
#: ROGERS, SHAW and SPRINT need their telecom word; ATT only in its bill and payment forms. The VERIZON lookahead
#: covers the registry's Verizon Visa alias only (a 'SYNCB VERIZON' card payment in 'other' hides no funder).
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
    """Besides its own loan and capital guard, the skip reads the shared veto on the whole row. The skip's own words
    (SQUARE, SQ and the entry date, INTUIT PYMT SOLN) carry no financing root, so nothing is removed first."""
    text = record.normalized_description
    return (
        abs(record.amount) <= _PROCESSOR_ACCOUNT_CHARGE_MAX
        and _matches_any(text, _PROCESSOR_ACCOUNT_DEBIT_PATTERNS)
        and _PROCESSOR_DEBIT_FINANCING_GUARD.search(text) is None
        and not _names_financing(text)
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


#: The D6 payee words of a card network's 'NAME, CITY, ST' line are the printed name before the first comma (the
#: city never joins the name), read without the module normalizer.
_PRINTED_NAME_WORD = re.compile(r"[A-Z0-9]+")


def _record_payee_tokens(record: TransactionClassification) -> tuple[str, ...]:
    """D6's payee words for one row: D11's words, or, on a 'NAME, CITY, ST' line with no ACH field mark, the words of
    the printed name before the first comma."""
    printed = record.original_description or ""
    if _CARD_LOCATION_SUFFIX_PATTERN.search(printed) and not _has_ach_field_mark(record):
        return _unknown_payee_tokens(" ".join(_PRINTED_NAME_WORD.findall(printed.split(",", 1)[0].upper())))
    return _unknown_payee_tokens(record.normalized_description)


#: The names D11 and D10 publish for a payee they cannot name. The Potential Lenders tab lists each payee key of
#: them on its own line (potential_payee_label), never one line for all.
_UNNAMED_POTENTIAL_ENTITIES = frozenset({UNIDENTIFIED_LENDER_OBLIGATION, UNIDENTIFIED_MCA_SERVICER})
_RECURRENCE_CADENCE = re.compile(r"^(daily|weekly)_fixed_debit_")


def _label_unnamed_potential_payees(records: list[TransactionClassification]) -> list[TransactionClassification]:
    """One Potential Lenders line per unnamed payee of a statement. The rows of one payee key (entity, rule, payee
    words, amount and masked recipient) share a label that names the entity, the cadence of a recurrence and the
    amount, never a payee word (D11): 'Unidentified lender obligation (weekly, 450.00)'. A second key with the same
    label gets ' #2'. canonical_entity is unchanged."""
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
    # Every potential lender row, named or not, gains its payee's amount-free key in the same step. The labels above
    # are unchanged.
    for index, record in enumerate(labelled):
        if record.classification == "potential_lender":
            labelled[index] = replace(record, potential_payee_key=_potential_payee_key(record))
    return labelled


def _potential_payee_key(record: TransactionClassification) -> str:
    """One key per payee of a potential lender, named or not, which lender_payment_changes reads to follow a payee
    across an amount change; nothing else reads it. The probe's key (the entity, D6's payee words and the masked
    recipient), with no amount and no match method, as the first 16 hex characters of its SHA-256 digest: stable
    across statements and processes, and no payee word is published (D11)."""
    parts = [record.canonical_entity or "", " ".join(_record_payee_tokens(record)), _masked_recipient(record) or ""]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def classify_statement_transactions(
    statement: Statement,
    *,
    min_recurring_count: int = 3,
    zelle_true_revenue: bool = False,
) -> list[TransactionClassification]:
    """Create the one authoritative classification record for every ledger row.

    True revenue spec §8.4: `zelle_true_revenue` False (the default) is the STORED reading, every Zelle deposit
    excluded by pass 7's Zelle step, which every caller that names no reading keeps; True is the counted reading
    (apply_true_revenue_pass). classify_statement_readings gives both at once."""
    # The matcher answers each of this statement's questions once, and forgets them when the classification
    # returns (payee_matcher.match_memo).
    with match_memo():
        records, duplicate_of = _classify_statement_prefix(statement, min_recurring_count)
        return _classify_statement_reading(statement, records, duplicate_of, zelle_true_revenue=zelle_true_revenue)


def classify_statement_readings(
    statement: Statement,
    *,
    min_recurring_count: int = 3,
) -> tuple[list[TransactionClassification], list[TransactionClassification] | None]:
    """True revenue spec §8.4, §9.1: the stored (No) reading and the counted (Yes) reading of one statement, element for
    element equal to `(classify_statement_transactions(statement), classify_statement_transactions(statement,
    zelle_true_revenue=True))`. The shared prefix (the per-row classification, the duplicates, recurrence and D6, passes
    1 to 6) runs once; pass 7, pass 7b and the duplicate finalisation run once per reading. The second element is None
    when no credit pass 7 reads prints the Zelle rail (true_revenue.zelle_credits_present): such a statement has a
    single reading."""
    # One matcher memo for the prefix and both readings, dropped on return.
    with match_memo():
        records, duplicate_of = _classify_statement_prefix(statement, min_recurring_count)
        stored = _classify_statement_reading(statement, list(records), duplicate_of, zelle_true_revenue=False)
        if not zelle_credits_present(records, set(duplicate_of)):
            return stored, None
        return stored, _classify_statement_reading(statement, list(records), duplicate_of, zelle_true_revenue=True)


def classify_statement_reversals(
    statement: Statement,
    *,
    min_recurring_count: int = 3,
) -> list[TransactionClassification]:
    """The records through statement passes 1 to 6, for a reader of the reversal pass's fields alone (reconcile's
    coverage check). Pass 4 sets `settlement_reversal` and `reversed_by` and nothing after it writes either (pass 7,
    7b, 7c and the duplicate finalisation leave them, and every record's amount, as they are;
    tests/test_reconcile_reversal_prefix.py holds the source check), so they are both readings' values, without the
    true-revenue pass. Every other field may differ from classify_statement_transactions'."""
    with match_memo():
        return _classify_statement_prefix(statement, min_recurring_count)[0]


def _classify_statement_prefix(
    statement: Statement, min_recurring_count: int,
) -> tuple[list[TransactionClassification], dict[int, int]]:
    """Every row's classification record through statement passes 1 to 6, and the proven duplicates (index -> the
    index it repeats): the part of classify_statement_transactions both Zelle readings share."""
    records = [
        classify_transaction(
            transaction.description,
            transaction.amount,
            date=transaction.date,
            bank=statement.bank,
            account=statement.account_number,
            account_name=statement.account_name,
            holder_name=statement.holder_name,
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
    return records, duplicate_of


def _classify_statement_reading(
    statement: Statement,
    records: list[TransactionClassification],
    duplicate_of: dict[int, int],
    *,
    zelle_true_revenue: bool,
) -> list[TransactionClassification]:
    """Pass 7, pass 7b and the duplicate finalisation over the shared prefix, in one Zelle reading."""
    # §6.2: payer facts, Q7's credit-union arm, the Q5 and Q6 verifications, then the tiers. With the credits the
    # parser marked as read only by their label. And their unread payer text. §8.10: and the statement's
    # premium-trust title, read on its printed title, account name and holder name (premium_trust_title; this is the
    # pass's only caller, so every consumer reads it). §8.5: and the statement's printed period start, which the
    # funding aid on held no-sender wires reads. And the Zelle reading.
    records = apply_true_revenue_pass(
        records, set(duplicate_of), payer_text_unread_indexes(statement.transactions),
        payer_text_unread_texts(statement.transactions),
        premium_trust=premium_trust_title(
            getattr(statement, "account_title", None), statement.account_name, statement.holder_name
        ),
        statement_start=statement.period_start,
        zelle_true_revenue=zelle_true_revenue,
    )
    # True revenue spec §6.2 pass 7b: a confirmed funder's payment a bounce-worded credit returned leaves paid to
    # lenders and stays in the withholding rate. After pass 7, so the return credit's tier is final; it reads and writes
    # nothing passes 5 to 7 read.
    records = list(_apply_returned_funder_payments(records, set(duplicate_of)))
    # §6.2: a returned payment the same funder re-presented or caught up leaves the withholding numerator. After pass
    # 7b, which makes the last returned payments; it reads and writes lender fields only.
    records = _apply_represented_funder_payments(
        records, set(duplicate_of), "CA" if str(statement.currency or "").strip().upper() == "CAD" else "US",
    )

    for index, original_index in duplicate_of.items():
        record = records[index]
        duplicate_revenue = record.amount > 0 and record.is_posted
        records[index] = replace(
            record,
            duplicate_of=f"transaction:{original_index + 1}",
            review_required=True,
            reason=f"{record.reason} Exact duplicate of transaction:{original_index + 1}; excluded from all totals.",
            # A duplicate is in no total, so it is no lump sum either.
            lump_sum_payoff=None,
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
