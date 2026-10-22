from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from analysis.classification_registry import (
    BANK_NAME_ALIASES,
    BLUE_PLAN_CLAIM_PAYERS,
    BANK_SPECIFIC_LENDER_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    FACTORING_REVIEW_ENTITIES,
    OPERATING_REVENUE_SOURCE_TYPES,
    PAYOUT_CREDIT_ENTITIES,
    POTENTIAL_LENDER_ALIASES,
    REVIEW_FLAG_ENTITIES,
)
from analysis.flag_groups import FINANCING_STATES, FLAG_GROUP_BY_STATE
from analysis.revenue import revenue_contribution_flags, tier_of_state
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from analysis.description_text import ln_name_spans, normalize_transaction_description
from analysis.payee_matcher import PayeeMatch, match_debt_relief_payee, match_known_payee, match_memo, registry_match
from analysis.descriptor.financing import _names_financing
from analysis.descriptor.lexical import _before_receiver, _joined_text, revenue_text, without_statement_furniture
from analysis.descriptor.words import (
    _BANK_TEMPLATE_WORDS,
    _BNPL_CONSUMER_CREDIT,
    _CHECK_PATTERNS,
    _CUSTOMER_INVOICE_DESCRIPTORS,
    _DIRECT_DEBIT_LOAN_PATTERNS,
    _EXPLICIT_REPAYMENT_PATTERNS,
    _FLAGGED_REVENUE_CREDIT_STATES,
    _LINE_OF_CREDIT_PATTERNS,
    _PAYOUT_NON_SALE_CREDIT,
    _PAYROLL_PATTERNS,
    _POS_PATTERNS,
    _PREMIUM_FINANCE_WORDING_PATTERNS,
    _RECEIVER_FIELD_VALUE,
    _REFUND_REVERSAL_PATTERNS,
    _SNAP_MERCHANT_FUNDING,
)
from analysis.descriptor.credit_words import _HCCLAIMPMT, _INSURER_CUSTOMER_PAYMENT, _MICRO_DEPOSIT_FLOOR
from analysis.descriptor.holder import _business_account, holder_reading, platform_entry_leads_with_financing
from analysis.descriptor.payer import channel_gate, payer_region
from analysis.descriptor.rails import _matches_any, _state_words, _wire_vetoes_apply, _without_receiver_value
from analysis.classification.record import (
    ClassificationState,
    DealerFunding,
    TransactionClassification,
    UNIDENTIFIED_LENDER_OBLIGATION,
    UNIDENTIFIED_MCA_SERVICER,
    _RevenueDecision,
    _promotion_cadence,
    _replace_revenue_state,
)
from analysis.classification.credit_predicates import (
    _named_sender_after_designation,
    _own_book_or_funds_transfer,
    _payer_remittance,
    _public_payer_remittance,
    _refused_by_payer_guards,
    _reversal_credit,
    _split_glued_claim,
    _wire_remittance_purpose,
    _wire_vetoed,
)
from analysis.classification.operating_sources import (
    _OperatingSource,
    _card_settlement_form,
    _has_operating_context,
    _operating_source,
)
from analysis.classification.payees import (
    _canonical_unknown_entity,
    _descriptor_proceeds,
    _factoring_review_payee,
    _field_order_payee,
    _insurance_registry_match,
    _is_membership_or_top_up,
    _is_payroll_provider_row,
    _unknown_entity_for_text,
    _unknown_payee_tokens,
)
from analysis.classification.tax_forms import _NON_REVENUE_CREDIT_PATTERNS, government_no_purpose
from analysis.transaction_classifier.funder_returns import (
    _apply_represented_funder_payments,
    _apply_returned_funder_payments,
)
from analysis.transaction_classifier.operating_context import _apply_operating_source_context
from analysis.transaction_classifier.potential_lenders import (
    _d6_skip,
    _keyword_recurrence_skip,
    _label_unnamed_potential_payees,
    _masked_recipient,
    _record_payee_tokens,
)
from analysis.transaction_classifier.reversals import _apply_reversal_pair_context
from analysis.true_revenue.holder_names import without_receiver_and_holder
# The true-revenue pass reads this module's readers at call time, so it imports nothing from here at load.
from analysis.true_revenue import (
    also_debited,
    apply_true_revenue_pass,
    counter_credit,
    counter_debits,
    dealer_funding_reading,
    debited_as_lender,
    payer_text_unread_indexes,
    payer_text_unread_texts,
    premium_trust_title,
    zelle_credits_present,
)

# True revenue reads these through _classifier() until its readers leave analysis/true_revenue/.
from analysis.classification.counter_debit_reading import (
    _counter_debit_head,
    _payer_key,
    _split_glued_digits,
    counter_debit_debit_reading,
    counter_debit_payer_reading,
)
from analysis.classification.operating_sources import _recurrence_vetoed
from analysis.description_text import _TRANSFER_WORDING
from analysis.descriptor.credit_words import (
    CUSTOMER_FINANCING_LUMP_FLOOR,
    CUSTOMER_FINANCING_LUMP_ROUND,
    CUSTOMER_FINANCING_LUMP_SHARE,
    CUSTOMER_FINANCING_SERIES_MIN,
    CUSTOMER_FINANCING_SERIES_SHARE,
    _CARD_CREDIT_PUSH_WORD,
    _FUNDING_SETTLEMENT_ENTITIES,
    _PAYOUT_FORMS,
    _PUBLIC_PAYER_NON_SALE_WORDS,
    _TREASURY_BOILERPLATE,
)
from analysis.descriptor.holder import account_name_text, holder_named, holder_receiver_block, holder_words
from analysis.descriptor.lexical import (
    _is_payer_word,
    _is_reference_token,
    _originator_segment,
    _skip_numbered_leading_date,
    company_form,
    is_round_sum,
    payer_name,
)
from analysis.descriptor.payer import (
    _is_bare_row,
    entry_fields,
    numbered_company,
    payer_label_layout,
    wire_relayed_customer,
)
from analysis.descriptor.rails import _is_wire_row, _loose_wire_originator
from analysis.descriptor.words import (
    HOLDER_NOISE,
    REVENUE_GENERIC_WORDS,
    _BANK_COMPANY_FORM,
    _CARD_FORM_DEBIT_PREFIX,
    _CONSUMER_P2P_RAIL,
    _ELECTRONIC_PAYMENT_FORM,
    _GLUED_SEC_CODE,
    _NUMBERED_COMPANY_REGION,
    _PUSH_RAIL,
    _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS,
    _WIRE_ORIGINATOR_LABEL,
    _WIRE_SENDER_AFTER_LABEL,
    _WIRE_SENDER_AFTER_LABEL_END,
    _WIRE_WORD,
)

if TYPE_CHECKING:
    from analysis.schema import Statement


#: The ACH token, compiled once (it used to be re-normalized on every row).
_ACH_TOKEN = re.compile(r"(?<![A-Z0-9])ACH(?![A-Z0-9])")


#: The flag group of an insurance row whose insurer is a premium-finance payee
#: (C1: the one flag group that is not a classification state).
_PREMIUM_FINANCING_GROUP = "premium_financing"


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
#: A loan from the business's own shareholder, owner or director, repaid to them: no lender is named. The loan
#: producers never take it (debits only, and only when the row names no organisation). MEMBER and PARTNER are
#: left out: a funder can be named '... Partners'.
_RELATED_PARTY_LOAN_PATTERNS = (
    re.compile(r"\b(?:SHAREHOLDERS?|OWNERS?|DIRECTORS?) LOANS?\b"),
    re.compile(r"\bDUE TO (?:SHAREHOLDERS?|OWNERS?)\b"),
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


# ---------------------------------------------------------------------------------------------------------------------
# True revenue spec §5.2, §6.1, §7: the credit revenue
# readers. Every credit revenue rule reads revenue_text(text); D11, normalized_description and every debit rule keep
# the normalized row as it is.
# ---------------------------------------------------------------------------------------------------------------------

#: T18 (OQ5): a credit that prints the NACHA claim-payment entry skips the insurer registry, so an insurer's healthcare
#: claim payment to a provider verifies. Off, it is held with the insurer's other credits.
HCCLAIMPMT_CLAIM_FIRST = True
_BLUE_PLAN_CLAIM_PAYER = re.compile("|".join(BLUE_PLAN_CLAIM_PAYERS))


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


#: The matched rule of an operating-registry credit whose entry leads with a financing word.
PLATFORM_FINANCING_ENTRY_RULE = "platform_entry_leads_with_financing"


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


#: D6 does not take a same-amount group under this amount whose payee names no organisation (it would publish as
#: 'Unidentified lender obligation') and whose row names no financing. Strict: a 25-dollar debit promotes. A
#: named payee promotes at any amount. A whole number: analysis/ carries no exact-cent literal
#: (tests/test_no_statement_hardcodes.py).
_D6_MIN_FIXED_DEBIT = 25


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
