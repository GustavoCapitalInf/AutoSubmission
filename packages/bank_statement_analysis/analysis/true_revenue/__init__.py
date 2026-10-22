"""The true-revenue pass (docs/superpowers/specs/2026-09-28-true-revenue-design.md §5, §8).

Statement pass 7 (§6.2) runs after every verifying rule of `analysis/transaction_classifier/`. It reads each posted
credit's payer facts (channel family, payer region, payer name and key, entry fields, the holds of §8.1), then runs
Q7's credit-union arm (§8.7) and the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold names, and last
gives every posted credit its tier and reason (§5.3), in the order of §8.10.

It imports the classifier's readers at call time (`_classifier`), never at load: the classifier imports this module
at its own load, so a load-time import back would be circular.

The payer region, payer name, entry fields and wire reading are the 5.5 readers' (S2.1 to S2.4): a holder's name in
the receiver field never names a payer (§5.2), a glued leading date never changes a reading (revenue_text), the
§7.9 wire vetoes are `_wire_vetoed` itself, and a wire is any row the 5.5 wire vetoes read as one
(`_wire_vetoes_apply`). The hold words follow the owner's veto convention: a spelling of four letters or more (all
its words counted) takes a (?<![A-Z]) left boundary, so a digit glued on its left never hides it; a spelling of
three letters or fewer keeps \\b.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import replace
from typing import TYPE_CHECKING, Sequence

from analysis.classification_registry import (
    ASSET_SALE_PAYERS,
    ASSET_SALE_SELLER_WORD_ONLY,
    HEALTHCARE_PAYER_ALIASES,
    PAYOUT_CREDIT_ENTITIES,
    WHOLESALE_AUCTION_PAYOUT_FORMS,
)
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import match_known_payee, registry_match
from analysis.true_revenue.channel import (
    _channel,
    _explicit_deposit,
    _named_transfer_sender,
    _transfer_code,
    _transfer_counterparty_words,
    _transfer_row,
    cpa_payment_code,
    cpa_payroll_code,
)
from analysis.true_revenue.hold_text import (
    _hold_text,
    _payer_name_proper,
    _prints_payer_name_field,
    _title_purpose_text,
)
from analysis.true_revenue.holder_names import (
    _holder,
    _holder_names,
    _holder_strip_names,
    _receiver_alias_reads,
    _receiver_holder_named,
    _receiver_holder_names,
    _without_holder_name,
)
from analysis.true_revenue.model import CounterDebits, CreditFacts, _under_micro_floor
from analysis.true_revenue.sender import _bank_account_payer, _bank_only_payer, _p2p_sender_readings, _sender_key
from analysis.true_revenue.words import (
    ASSET_SALE_METHOD,
    CONSTRUCTION_PROGRESS_DRAW_REASON,
    CUSTOMER_FINANCING_PAYOUT,
    DEALER_FUNDING_WORDS,
    INSURER_FOR_WORK_METHOD,
    LENDER_PAID_FOR_SERVICES,
    PROCESSOR_CARD_PAYOUT_METHOD,
    _CARD_CREDIT_LABEL,
    _CREDIT_UNION_PAYER,
    _DEALER_FUNDING_VETO,
    _DEALER_HOLDER_VETO,
    _EARNED_WAGE_ACCESS,
    _HOLDER_NAMED_SETTLEMENT_ENTRY,
    _IAA,
    _INVESTMENT_PURPOSE,
    _MICRO_DEPOSIT_REASON,
    _PAY_WORDS,
    _POSSIBLE_RETURN,
    _TITLE_FEE_WORDING,
    _TITLE_FIRM,
    _VEHICLE_PURCHASE_ENTRY,
)
from analysis.true_revenue.claimed import _claimed, _customer_financier, _own_word, _own_words, registry_financing
from analysis.true_revenue.financing_roots import _accounts_payable_wording, financing_named
from analysis.true_revenue.payroll import (
    _business_shape,
    _direct_deposit_pay,
    _pay_wording,
    _premium_coded,
    lending_bank_payer,
)
from analysis.true_revenue.public_payers import (
    _account_designation,
    _personal_income,
    consumer_entry,
    government_benefit,
    government_grant,
    government_payer,
    healthcare_payer,
    healthcare_payer_match,
    public_region,
)
from analysis.true_revenue.self_originated_credits import (
    _bank_originated_wire,
    _facts_region,
    merchant_settlement,
    platform_credit,
    processor_payout,
    self_originated,
)
from analysis.true_revenue.counter_debit_pairing import (
    _cents,
    _payer_collects,
    also_debited,
    counter_credit,
    counter_debits,
    debited_as_lender,
)
from analysis.true_revenue.demotions import (
    _customer_financing_lump,
    _factor_never_verified,
    _financier_never_verified,
    _holder_never_verified,
    _leading_card_credit,
    _lender_service_never_verified,
    _processor_card_payouts,
    _progress_draw_never_verified,
    _settlement_never_verified,
)
from analysis.true_revenue.eligibility import (
    _b_o_field,
    _deferred_reading,
    _deferred_source,
    _factor_tail,
    _factoring_payout_payer,
    _never_q5_or_q6,
    _q6_eligible,
    _q6_method,
    _vetoed_financier,
    _wire_verifies,
)
from analysis.true_revenue.tiers import _held_by_the_floor, _tier_reason, _verify, _with_tier
from analysis.true_revenue.trust import _held_in_premium_trust, _held_personal_trust
from analysis.true_revenue.dealer import (
    _dealer_activity,
    _dealer_contract_evidence,
    _dealer_funding_payer,
    _dealer_word_lender,
    _payables_only_dealer_funding,
    credit_union_dealer_entry,
    funding_series_after,
)
from analysis.true_revenue.finance_release import _lessor_business, finance_named_release, payroll_tax_credit
from analysis.true_revenue.insurer import _insurer_for_work, _insurer_for_work_reason, insurer_payer_reading
from analysis.true_revenue.purpose import (
    _currency_conversion,
    _disbursement_entry,
    _disbursing_payer,
    _recurring_disbursers,
    _vendor_payment,
    construction_progress_draw,
    gambling_payout,
    legal_settlement,
    non_sale_purpose,
    owner_disbursement,
    owner_money_platform,
    purpose_trade_name,
)
from analysis.true_revenue.zelle import _zelle_excluded, pass_text, zelle_deposit

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.7: a deal's ID on Chase's credit-union layout ('IND ID:<deal>'), which a credit union prints on the vehicle
#: purchase and on the same deal's admin fee.
_DEAL_ID = re.compile(r"\bIND ID (\S+)")
#: §8.7: a statement's credit-union dealer funding needs this many credits.
CREDIT_UNION_DEALER_MIN_CREDITS = 2
#: The release stays off by spec §19.1: a processor's payout printed as a bare card credit stays a card refund. The code
#: stays as the declined option's record; turning it on needs the owner's word again (and re-pins the Relay fixture of
#: tests/test_new_statement_corpus.py).
PROCESSOR_CARD_PAYOUT_RELEASE = False
_PROCESSOR_CARD_PAYOUT_RULE = "processor_card_credit_beside_its_ach_activity"


#: §8.6: the verification-only words: sales wording often enough to count, never proof. SETTLEMENT alone again, as
#: before the batch: a row the settlement exemption releases is refused as proof by its own flag
#: (CreditFacts.settlement_released), whatever slot or boundary its word sits in, and a third party's short spelling
#: keeps the reading it had.
_VERIFICATION_ONLY = re.compile(
    r"(?<![A-Z])(?:SETTLEMENT\b|TAXES\b|FEES\b|SUBSCRIPTIONS?\b|DISCOUNT\w*|COMM?ISS?IONS?\b"
    r"|COMPENSATION\b|EXPENSES?\b|AFFILIATE\b|PERSONAL\b|CLOSING\b|SUPPLY CHAIN\b"
    r"|EARLY PAY(?:MENT)?\b|ALLOWANCES?\b|SHORTAGES?\b)"
    r"|\b(?:TAX|IRS|CRA|FEE|SCF|RMA)\b"
)
_ENTRY_VERIFICATION_ONLY = re.compile(r"(?<![A-Z])(?:FLOOR ?PLAN\b|FLOORPLAN\b|EQUIP\w*)|\bVIN\b")
#: G2: a financing root glued inside a word of a registry row (STRIPECAPITAL, SHOPIFYCAPITAL).
_GLUED_FINANCING_ROOT = re.compile(r"CAPITAL|CAPTL|FINANC|FUNDING|FUNDNG|LENDING|LENDER|LOAN")
#: §5.3: tiers by revenue state; the two middle tiers are unverified.
_TIER_OF_STATE = {"verified_revenue": "verified", "non_revenue": "non_revenue"}
CUSTOMER_FINANCING_LUMP_SUM = "customer_financing_lump_sum"
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
#: (EQUIPMENT, EQUIP, MACHINERY) that many trades sell and invoice. FLEET alone is no asset noun of a sale ('FLEET
#: SALE' is a fleet card's settlement wording, a fuel merchant's revenue); a fleet's vehicles or trucks still read
#: through their noun ('SALE OF FLEET VEHICLES', 'FLEET TRUCK SALE').
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
    # FLEET left the asset nouns of a sale, never this arm ('<NAME> FLEET SALES' still trades).
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
#: Q11 (b), a commission or a fee printed next to the sale, right after it ('CAR SALE COMMISSION', 'TRUCK SALE FEE') or
#: right before it with at most a connector ('COMMISSION ON TRUCK SALE'): a broker's or an agent's earned revenue, never
#: the proceeds of its own asset. A fee printed apart ('TRUCK SALE NET OF FEES') leaves the sale.
_ASSET_SALE_COMMISSION_AFTER = re.compile(r"^\s*(?:COMMISSIONS?|COMMS?|FEES?)\b")
_ASSET_SALE_COMMISSION_BEFORE = re.compile(r"(?<![A-Z])(?:COMMISSIONS?|FEES?)(?:\s+(?:ON|FOR|FROM|OF))?\s*$")
#: §4.2: a netting word beside that commission or fee, after it ('TRUCK SALE FEES WITHHELD', 'TRUCK SALE COMM
#: DEDUCTED') or before it ('LESS FEES TRUCK SALE', 'NET OF COMMISSION TRUCK SALE'): what the seller's proceeds are net
#: of, never a broker's earned fee, so the sale is read (_asset_sale_commission). A bare NET reads only before FEES
#: ('NET FEES TRUCK SALE'); a broker's or an agent's NET COMMISSION is its own earned commission after splits, and NET
#: FEE its own fee, so both stay a broker's revenue.
_ASSET_SALE_NETTING_AFTER = re.compile(r"^\s*(?:COMMISSIONS?|COMMS?|FEES?)\s+(?:WITHHELD|DEDUCTED|DEDUCT\w*|NETTED)\b")
_ASSET_SALE_NETTING_BEFORE = re.compile(
    r"(?<![A-Z])(?:(?:NET OF|LESS|AFTER|MINUS)\s+(?:COMMISSIONS?|COMMS?|FEES?)|NET\s+FEES)"
    r"(?:\s+(?:ON|FOR|FROM|OF))?\s*$"
)
#: A seller's proceeds never lead with or come out of a commission. A commission word printed directly before that
#: netting phrase ('COMMISSION LESS FEES ON TRUCK SALE', 'NET COMMISSION LESS FEES TRUCK SALE': a broker's or an agent's
#: commission less its fees) or fees a netting word takes from or off a commission after the sale ('TRUCK SALE FEES
#: WITHHELD FROM COMMISSION') is the broker's own earned commission, so the veto stays, as for its mirror 'TRUCK SALE
#: COMMISSION LESS FEES'; never a commission a netting word itself stands before ('NET OF COMMISSION LESS FEES TRUCK
#: SALE', _ASSET_SALE_NETTED_WORD: what a seller's proceeds are net of; a bare NET is a broker's NET COMMISSION).
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


def _classifier():
    from analysis import transaction_classifier

    return transaction_classifier


#: Spec §5.3: the display reason a government payment that prints no purpose carries (§6.1 step 3a decided it
#: non_revenue, method GOVERNMENT_NO_PURPOSE_METHOD), so the non-revenue breakdown names the excluded government money.
#: Display only: the row's tier, state, method, rule and flags are step 3a's, and it has no review path.
GOVERNMENT_NO_PURPOSE = "government_no_purpose"
GOVERNMENT_NO_PURPOSE_METHOD = "government_no_purpose_exclusion"
#: RBC's French 'Paiement divers' label before the holder's own chequing or savings account and its number: the
#: holder's own account, held as transfer_account_designation.
_FRENCH_OWN_ACCOUNT_PAYMENT = re.compile(r"^PAIEMENT DIVERS COMPTE (?:CHEQUE|EPARGNE) \d+")
#: A credit 'FR' (from) an account designation, printed with no transfer word (Bank of America's banking-centre
#: 'BKOFAMERICA BC <date> <ref> FR SAV' or 'FR CHKG'): it names an account, never a payer, and is held as
#: transfer_account_designation whatever debits the statement prints.
_FROM_ACCOUNT_ABBREVIATION = re.compile(
    r"(?<![A-Z])FR (?:SAV|SAVINGS|SVGS|CHKG|CHK|CKG|CHECKING|DDA|MMA)\b"
)


def _transfer_reading(
    record: TransactionClassification, text: str, channel: str, region: str,
) -> tuple[bool, list[str], bool]:
    """§8.2, T13: (transfer row, its counterparty words, transfer_no_counterparty), as the pass and the census's G4
    read them. An explicit check, cash or ATM deposit form is no bare transfer (Q2 and Q3 count it); the
    counterparty is read with the statement's bank; and an ACH or unlabelled payer region that is only a bank's name
    and an account description (_bank_account_payer) names no payer either. A wire is decided by Q5 before this hold
    (§8.10), so a wire row never carries it.

    Nor does an ACH or unlabelled payer region that is only a sending bank's name or a bank by its own form
    (_bank_only_payer: 'sending' or 'form'), on a row that prints no entry field, which no rule verified and nothing
    claimed: the holder's pull from another of its own bank accounts ('ACH CREDIT <bank>', '<bank> ACH'). The
    statement's own bank's channel ('own': 'CHASE ONLINE' on a Chase statement) is never held: it is a customer's bill
    payment through the bank (counted, never verified)."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    transfer_row = _transfer_row(row) and not _explicit_deposit(channel, row)
    words = _transfer_counterparty_words(text, record.bank) if channel == "person_to_person" else []
    bank_account = channel in {"ach_eft", "other"} and (
        _bank_account_payer(region, record.bank) or _bank_only_pull(record, text, region)
    )
    return transfer_row, words, channel != "wire" and ((transfer_row and not words) or bank_account)


def _bank_only_pull(record: TransactionClassification, text: str, region: str) -> bool:
    """§8.2: an ACH or unlabelled credit whose payer region is only a sending bank's name or a bank by its own form
    (_bank_only_payer), on a row that prints no entry field, which no rule verified and no registry, payout, factoring
    payee or factor claimed: no payer is printed (held as transfer_no_counterparty, Q2)."""
    if not region or record.revenue_classification == "verified_revenue":
        return False
    classifier = _classifier()
    if classifier.entry_fields(text).strip():
        return False
    if _bank_only_payer(region, "", record.bank, row=classifier._before_receiver(text)) not in {"sending", "form"}:
        return False
    return not (_claimed(record, text) or _factoring_payout_payer(region, text))


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
    person-to-person sender printed without FROM is read after its rail for Q4's two holds only: the holder test and
    the round-sum repeat (its key). So is the counterparty of a named transfer printed without FROM (T13, S4.2 fix
    round 5: _named_transfer_sender), which the FROM form's payer region reads. Every other hold reads the payer
    region, so such a row's financing root is still read on the whole row. A3-G refinement: on the wire channel a
    region of bare channel words (_BARE_CHANNEL_WORDS: 'WIRE') names no sender; `receiver_holders` are the holder's
    names the statement's own receiver fields print (_receiver_holder_names), read by the holder hold only. `business`
    is the statement's _business_shape, which the direct-deposit words read, and `disbursers` the statement's
    _recurring_disbursers, whose disbursement entry is no non-sale purpose. On an unverified credit nothing claimed,
    the release of T4's financing-root hold (finance_named_release, `lessor` the statement's _lessor_business) lifts
    that root arm alone in _first_hold (`released`); CreditFacts.q9 carries its reason only where no hold names the row
    then. `zelle_true_revenue` is the counted reading, in which a builder's Zelle draw is a progress draw
    (construction_progress_draw); nothing else here reads it."""
    classifier = _classifier()
    channel = _channel(text, record.bank)
    region = _facts_region(text, channel, record.bank, _holder_names(record))
    # A TD Canada Trust e-Transfer prints a per-transfer code where a sender would stand, which the pass's text no
    # longer prints (without_transfer_code): the row reads no sender and no key.
    sender, holder_sender = (
        _p2p_sender_readings(text)
        if not region and channel == "person_to_person" and _transfer_code(record) is None else ("", "")
    )
    name = classifier.payer_name(region)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    # A factor the registry names claims its row as a factoring payee does (only the insurer,
    # possible-return, pay and benefit holds read it), so its trade name's financing word holds nothing.
    factor = _factoring_payout_payer(region, text)
    # A lease-to-own or patient financier's merchant payout, which _claimed claims too.
    financier = _customer_financier(record, text)
    claimed = _claimed(record, text) or factor
    wire_n1 = classifier._is_wire_row(text)
    # TD Canada Trust's trailing CPA code is an electronic-payment form.
    electronic = bool(classifier._ELECTRONIC_PAYMENT_FORM.search(row)) or cpa_payment_code(row, record.bank)
    # §8.5: Q5 reads a healthcare payer on an incoming wire too; Q6 on an electronic-payment form.
    healthcare = healthcare_payer(region) and (wire_n1 or electronic)
    public = government_payer(public_region(text))
    transfer_row, transfer_words, no_counterparty = _transfer_reading(record, text, channel, region)
    if not region and not sender and transfer_row and transfer_words and re.search(r"\bFROM\b", row) is None:
        # T13 (S4.2 fix round 5): a named transfer printed without FROM takes the same two holds.
        sender = holder_sender = _named_transfer_sender(text)
    disbursing = bool(region) and classifier._payer_key(region) in disbursers
    # A builder's progress draw, read only on a named payer that no registry, payout entity, factor or financier
    # claimed.
    progress_draw = not claimed and construction_progress_draw(
        text, region, _holder(record), also=_holder_strip_names(record), zelle_true_revenue=zelle_true_revenue,
    )
    # T4's root arm lifted for a finance-named customer paying an invoice, a lessor's rent or a lender paying for
    # services, on an unverified credit nothing claimed (finance_named_release); every other financing arm and every
    # later hold still read the row.
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
    # IAA's insurer-name hold reads the auction's own name; the hold after it, which keeps an IAA seller payout held
    # where any other hold names it.
    past_insurer_name = (
        _first_hold(record, text, **hold_reading, insurer_name=False)
        if hold == "insurer_named_payer" and asset_sale_platform(region, text) == _IAA else None
    )
    # The holder's own push, read on the row alone, as _first_hold reads it.
    self_own = not claimed and self_originated(text, region, record.bank)
    # The bare settlement word alone lifted the row from the own-push guard, or an unverified credit from the pass-7
    # holder hold: the reading with B9's settlement words alone holds it as holder_name, the row's own reading does
    # not. Read only where the row prints the word somewhere.
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
            # A recurring disbursement entry the purpose-only spare dropped from the non-sale reading counts, never proves
            # (§8.6, as an unregistered payer's SETTLEMENT).
            or (disbursing and _disbursement_entry(text, region))
            # A legal, gambling or owner-money word only the trade-name reader's purpose arm spared counts, never
            # proves (the hold's own text, without the holder's names).
            or purpose_trade_name(
                text, _without_holder_name(_hold_text(text), _holder(record), also=_holder_strip_names(record)),
                region,
            )
            # A settlement the bare word alone released, wherever the word prints (an ID field, an originator's
            # tail, digits glued on), counts, never proves (§8.6).
            or settlement_released
        ),
        round_sum=classifier.is_round_sum(record.amount),
        consumer_entry=consumer_entry(text, _holder(record)),
        transfer_no_counterparty=no_counterparty,
        account_designation=transfer_row and bool(transfer_words) and _account_designation(row, record.bank),
        factor=factor,
        financier=financier,
        # A payer region that names only a bank names no customer.
        bank_only=_bank_only_payer(region, entry, record.bank, row=row),
        self_own=self_own,
        progress_draw=progress_draw,
        hold_past_insurer_name=past_insurer_name,
        # Q9: the release's reason where it took effect (no hold names the row).
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
    """§8.1 in §8.10's order (2 to 11): the first hold that names the row, or None. A bank's own wire is read on every
    row pass 7's wire channel reads (`wire`), and TD Canada Trust's payroll-deposit code is pay wording. A row the
    registry, a payout entity or a factoring payee claimed takes only the insurer, possible-return, pay and benefit
    holds; a registry row that prints a financing word is held as financing_named_payer. The holder test also reads a
    person-to-person sender printed without FROM (`sender`, Q4), and its holder-test reading, which keeps a layout
    word inside the name; or a named transfer's counterparty printed without FROM (T13, S4.2 fix round 5), both
    readings one. The counter-debit holds read the statement's debits by kind (debited_as_lender, also_debited), and a
    payroll provider's tax-service credit no debit holds is non_sale_purpose, on a claimed row too (the pay holds'
    convention).

    The possible-return, financing-root, pay, personal-income and non-sale tests read the row without the holder's own
    name runs (_without_holder_name); the direct-deposit words are pay wording only with a sign of a person's pay
    (_direct_deposit_pay, `business` the statement's _business_shape); and the dealer-word hold never reads a named
    non-lender's wire purpose (_dealer_word_lender). On a builder's progress draw (`progress_draw`) the non-sale test
    spares DRAW alone. With `insurer_name` False the insurer-name hold is passed over, so credit_facts reads the hold an
    IAA seller payout would take after it (CreditFacts.hold_past_insurer_name). The insurer-name hold reads
    insurer_payer_reading, every insurer spelling and brand without the holder's names. A credit the insurer-for-work
    release re-stated (INSURER_FOR_WORK_METHOD) takes no insurer-name hold, and the non-sale test reads no CLAIM on it;
    every other hold reads it as before. With `released` (finance_named_release lifted the row) the financing hold's root
    arm (financing_named) is passed over; its other arms keep their order and still hold, and every later hold reads the
    row. With `bare_settlement` False the holder hold and the own-push guard read B9's settlement words alone
    (merchant_settlement), the hold credit_facts compares to name a row the bare settlement word alone released
    (CreditFacts.settlement_released)."""
    classifier = _classifier()
    # The holder-name strip reads the holder's other business names too (_holder_strip_names).
    also = _holder_strip_names(record)
    row = _without_holder_name(_hold_text(text), _holder(record), also=also)
    before = _without_holder_name(classifier._before_receiver(text), _holder(record), also=also)
    if record.revenue_match_method == "insurer_customer_payment":
        return "insurer_payer"
    # An insurer however the bank spells it (insurer_payer_reading: the spelled words, the INS abbreviation, the cut
    # forms, LOSS PMT, SUBRO, the brand table, CLAIM), read without the holder's names; a listed insurer's reading is
    # the insurance rule's (non_revenue), never this hold. A credit the insurer-for-work release re-stated
    # (INSURER_FOR_WORK_METHOD) is no insurer-name hold; every later hold still reads it.
    if insurer_name and not claimed and region and record.revenue_match_method != INSURER_FOR_WORK_METHOD:
        reading = insurer_payer_reading(record, text, region, entry, receiver_holders)
        if reading is not None and reading.kind != "registry":
            return "insurer_named_payer"
    if record.revenue_match_method != "reversal_cancellation_exclusion" and (
        _POSSIBLE_RETURN.search(row)
        or (
            _CARD_CREDIT_LABEL.search(text) and record.revenue_classification != "verified_revenue"
            # A processor's instant payout, released beside its ACH activity, is counted.
            and record.revenue_match_method != PROCESSOR_CARD_PAYOUT_METHOD
        )
        # A card credit printed first, with no push or person-to-person rail.
        or (_leading_card_credit(text) and record.revenue_classification != "verified_revenue")
    ):
        return "possible_return"
    if not claimed and (
        # The root arm alone is lifted on a released row.
        (financing_named(text, region, entry, _holder(record), bank=record.bank, also=also) and not released)
        or registry_financing(record, text)
        # §8.7: a listed lender's or a dealer-funding word's row that Q7 did not verify, and a lone credit union's.
        # Never on a named non-lender's wire purpose (_dealer_word_lender).
        or (_dealer_funding_payer(text) is not None and record.revenue_match_method != "auto_lender_dealer_funding")
        or (
            DEALER_FUNDING_WORDS.search(row) and record.revenue_match_method != "auto_lender_dealer_funding"
            and _dealer_word_lender(text, region)
        )
        or record.revenue_match_method == "credit_union_vehicle_purchase"
        # A3-G: a wire a bank originates on its own behalf.
        or _bank_originated_wire(text, region, wire=wire)
        # A bank that lends to small businesses, named as the payer.
        or lending_bank_payer(text, region)
    ):
        return "financing_named_payer"
    # RBC's French label before the holder's own chequing or savings account (T13), which the counter-debit holds no
    # longer read by its label word; a credit from an account designation printed with no transfer word ('BKOFAMERICA
    # BC <date> <ref> FR SAV'), which only a debit sharing the bank's word held before.
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
    # A processor's or a platform's settlement or payout under the merchant's own name is never the holder's own money
    # (merchant_settlement). Read outside the holder's own names, never on a wire or a person-to-person rail; the
    # holder's names include an account-name field naming a holder beside the parser's (_holder_names), and the row's
    # layout sets where another payer's receiver block can print (holder_receiver_block). Nor a platform's payout known
    # by its payout id (processor_payout), whatever descriptor it prints. Nor a processor's, a platform's or a
    # franchisor's credit printing the merchant's own name (platform_credit).
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
        # The row's own originator is its receiver field, or a wire's sender its beneficiary.
        or self_originated(text, region, record.bank, bare_settlement=bare_settlement)
    ):
        return "holder_name"
    if _pay_wording(before, record.bank, text=text, account_name=_holder(record), business=business):
        return "payroll_or_salary"
    # The statement's bank, so TD Canada Trust's cut payer name is read as a name.
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
    # §7.0, §7.8, §8.10: the $1 floor is absolute. A posted credit under $1 is never verified and never counted,
    # whichever rule read it, claimed or not: an unverified one that no earlier hold names is held here, and one a rule
    # verified is held by the pass's last step (_held_by_the_floor).
    if _under_micro_floor(record):
        return _MICRO_DEPOSIT_REASON
    return None


def asset_sale_platform(region: str, text: str = "") -> str | None:
    """§8.1: the equipment auction or car buyer (ASSET_SALE_PAYERS) the payer region names as its whole payer name, or
    None: the alias's words start the region and the words after it, a seller's words aside (_ASSET_SALE_TAIL_WORDS:
    'CARVANA PAYOUT', 'RITCHIE BROS SELLER PAYOUT'), add nothing to its name, as _factor_tail reads a factor's (company
    forms, entry words, references, a DBA tail, a B/O field's address). A longer name that starts with it ('VROOM
    DELIVERY LLC', 'CARMAX BUSINESS SERVICES LLC', 'BIG IRON TRUCKING LLC') names another payer; a glued '<alias>LLC' is
    not read (fail-safe)."""
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
    """§8.1: 'payer' when an equipment auction or a car buyer pays a seller (asset_sale_platform: with a seller's word
    on the row, or, except Copart and IAA, with no service word on the purpose and a holder whose trade does not serve
    the platforms), 'purpose' when the row prints the sale of a truck, trailer, vehicle or equipment
    (_ASSET_SALE_PURPOSE, read outside the payer's own name, _payer_name_proper); or None. A vehicle's or heavy
    equipment's sale reads through an invoice reference (_INVOICE_REFERENCE), so only accounts-payable, vendor or
    payables wording spares it (_vendor_payment); a generic EQUIPMENT or MACHINERY sale keeps the invoice veto, a
    single-row verification and a supplier's holder name. Never a claimed row, a row an insurer-name hold reads unless
    the payer is IAA (its INSURANCE is the auction's name) and no later hold would name it
    (CreditFacts.hold_past_insurer_name), a Zelle row (Q3), a possible return or a refund; nor a printed sale with a
    commission or a fee next to it (_ASSET_SALE_COMMISSION_AFTER and _BEFORE, a broker's or an agent's earned revenue).
    `verified` is a row an invoice or customer-payment descriptor verified (ASSET_SALE_INVOICE_METHODS): only its
    printed sale is read, never a platform. The pass reads the statement's dealer evidence first (_dealer_statement) and
    applies the reading where the tier would count the row or a verification it overrules; a held tier keeps the row
    held. In the counted reading (`zelle_true_revenue`) a Zelle row is read as any other rail's, so a Zelle truck or
    equipment sale is asset-sale proceeds, as a Venmo one is."""
    classifier = _classifier()
    region = facts.region
    entity = asset_sale_platform(region, text) if region and not verified else None
    # IAA's insurer-name hold yields only where no later hold would name the row.
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
    # A commission or a fee next to the sale is earned revenue (_ASSET_SALE_COMMISSION_*); unless a netting word
    # makes it what the proceeds are net of.
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
    """§8.1 (Q11 (b)): a commission or a fee printed right after a printed sale (`after`, the purpose after it:
    _ASSET_SALE_COMMISSION_AFTER) or right before it with at most a connector (`before`, the purpose before it:
    _ASSET_SALE_COMMISSION_BEFORE), a broker's or an agent's earned revenue, so the purpose arm reads no sale. §4.2:
    never one a netting word stands beside (_ASSET_SALE_NETTING_AFTER: WITHHELD, DEDUCTED, DEDUCT..., NETTED after it),
    which is what the seller's proceeds are net of: 'TRUCK SALE FEES WITHHELD', 'NET FEES TRUCK SALE' and 'LESS
    COMMISSION TRUCK SALE' are the sale, as 'TRUCK SALE NET OF FEES' was; 'TRUCK SALE COMMISSION', 'COMMISSION ON TRUCK
    SALE', 'TRUCK SALE FEE', 'FEE FOR TRUCK SALE' and a broker's or an agent's 'NET COMMISSION ON TRUCK SALE' (its own
    earned commission after splits) stay a broker's revenue. A seller's proceeds never lead with or come out of a
    commission, so a commission word printed directly before the netting phrase (_ASSET_SALE_COMMISSION_NETTED_BEFORE:
    'COMMISSION LESS FEES ON TRUCK SALE', 'NET COMMISSION LESS FEES TRUCK SALE') or fees taken from or off a commission
    (_ASSET_SALE_FEES_FROM_COMMISSION: 'TRUCK SALE FEES WITHHELD FROM COMMISSION') keeps the veto, as its mirror 'TRUCK
    SALE COMMISSION LESS FEES' does; a commission a netting word itself stands before ('NET OF COMMISSION LESS FEES
    TRUCK SALE') is still the sale."""
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
    """§8.1: the statement shows a dealer, whose sales of vehicles or equipment stay revenue: the dealer activity
    (_dealer_activity: Q7 dealer funding that is not payables-only, a credit union's VHCL PURCH, a floor-plan
    financier's row or a FLOOR PLAN form, a posted debit at a dealer-only wholesale auction), a §7.8 auction's payout
    credit (a non-duplicate record of `indexes` whose revenue entity is one of WHOLESALE_AUCTION_PAYOUT_FORMS'
    auctions), or a vehicle or equipment trade name on one of the holder's names (the first record's _holder_names, read
    through account_name_text: _ASSET_TRADE_HOLDER) that prints no recovery, repossession, towing or collateral word
    (_DEALER_HOLDER_VETO). Read once per statement, before the tiers. _dealer_activity's narrowed arms (no card purchase
    at an auction, no floor-plan financier's service credit, no FLOORPLANNER or FLOOR PLANKS), so a non-dealer's asset
    sale beside such a row is asset-sale proceeds."""
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
    """§8.1, §8.10: the record made non_revenue as a non-dealer's asset-sale proceeds (method ASSET_SALE_METHOD, rule
    asset_sale_payer or asset_sale_purpose); its reason names the rule it overrules, for the audit. The pass gives it
    the reason code asset_sale_proceeds; it has no review path."""
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
    """Statement pass 7 (§6.2): payer facts, Q7's credit-union arm, the Q5 and Q6 verifications, then the tiers. First,
    with the owner's switch on (PROCESSOR_CARD_PAYOUT_RELEASE), a processor's instant payouts printed as card credits
    leave the reversal rule (_processor_card_payouts). `unread_indexes` are the credits the parser marked as read only
    by their label (payer_text_unread_indexes); their tier reason reads them (_tier_reason). `unread_texts` are those
    credits' unread payer text (payer_text_unread_texts), which only _tier_reason reads. Every Zelle deposit is excluded
    after the tiers and before the $1 floor (_zelle_excluded). A government payment that prints no purpose (Q12) takes
    its display reason, GOVERNMENT_NO_PURPOSE, with its non_revenue tier. A lease-to-own or patient financier's merchant
    payout is counted and flagged (customer_financing_payout), an earlier verification overruled after the factoring and
    self-own demotions, and after the tiers, before the Zelle step, a large one-off lump sum among those payouts is held
    (customer_financing_lump_sum). After the financier demotion, a listed auto lender's payables-only credit Q7
    verified, on a statement with no dealer evidence (_dealer_contract_evidence), is counted and flagged as
    lender_paid_for_services, or held as financing_named_payer when the lender also collects from the account
    (_payer_collects). (a) a builder's progress draw is counted and flagged (construction_progress_draw, read with the
    payer facts); (b) after the facts, on a statement that shows no dealer (_dealer_statement), the asset-sale reading
    (asset_sale_reading, on the unverified rows and the rows an invoice or customer-payment descriptor verified) keeps a
    row from Q5 and Q6, and the tier loop makes it non_revenue / asset_sale_proceeds after the payables demotion (a
    verified row) or after _tier_reason (a row the tier counts, or IAA's insurer-name hold); a held tier keeps the row
    held. After the statement facts and before the payer facts, an insurer's credit paid for the business's work
    (_insurer_for_work) is re-stated as an unverified deposit of method INSURER_FOR_WORK_METHOD, unclaimed (§8.10's
    holds 4 to 11 still read it), never toward a Q5 or Q6 repeat, and tiered counted_flagged /
    insurer_paid_for_services. Beside the business shape and the disbursers, whether the business is in leasing or
    property (_lessor_business); the payer facts then lift T4's financing-root hold on a finance-named customer paying
    an invoice, a lessor's rent or a lender paying for services (finance_named_release, CreditFacts.q9), never verified,
    never a repeat, the counted reason relabelled last in _tier_reason. `premium_trust` is the statement's premium-trust
    title (premium_trust_title) or None; when set, the step after the $1 floor holds every credit a rule verified or
    counted as PREMIUM_TRUST_REASON (_held_in_premium_trust). None leaves every record as before. `statement_start` is
    the statement's printed period start or None; the pass's last step, after the premium-trust hold, records on each
    held wire with no sender the lender series that start after it (funding_series_after, a review aid that moves no
    tier or figure). `zelle_true_revenue` False (the default) is the stored reading, every line as before; True is the
    counted reading, in which the Zelle step does not run and the two Q3-era carve-outs inside the rules are lifted (a
    builder's Zelle draw is a progress draw, credit_facts; a Zelle truck or equipment sale is asset-sale proceeds,
    asset_sale_reading). The lessor fact keeps its Zelle skip in both readings (_lessor_business), and every later step
    (the $1 floor, the premium-trust hold, funding_series_after) reads the counted tiers as it reads any row's."""
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
            # The reason names the credit union step 4 read (its revenue entity and alias stay); the count is the
            # statement's, across credit unions (§8.7).
            updated[index] = replace(
                _verify(record, "auto_lender_dealer_funding",
                        f"Credit union '{record.revenue_canonical_entity}' funds the dealer's indirect auto loans: its "
                        f"VHCL PURCH entry, one of {len(union_rows)} such credit-union credits in the statement (two "
                        "or more are dealer funding).", 0.90),
                revenue_source_type="auto_dealer_funding",
            )
        # The same credit unions' other dealer-funding entries (a deal's VADMIN FEE), beside their verified VHCL
        # PURCH credits or printing one's deal ID.
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
    # Whether the account reads as a business's, which the direct-deposit words read.
    business = _business_shape(records, duplicate_indexes)
    # A3-G refinement: the holder's names the statement's own receiver fields print, when its account name names nobody.
    receiver_holders = _receiver_holder_names(records, credits)
    # Without TD Canada Trust's e-Transfer code (without_transfer_code). And PNC's Zelle rail spelled as its ZELLE
    # twin (pass_text).
    texts = {
        index: pass_text(updated[index], classifier.revenue_text(updated[index].normalized_description))
        for index in credits
    }
    # The ordinary payers whose disbursement entry repeats in the statement.
    disbursers = _recurring_disbursers(texts)
    # §8.1: whether the business is in leasing or property, which a rent LEASE needs to be released from T4's
    # financing-root hold (_lessor_business).
    lessor = _lessor_business(updated, duplicate_indexes, credits)
    # §8.7: whether the statement shows dealer evidence, which a listed auto lender's payables-only credit needs to
    # stay verified (_dealer_contract_evidence).
    dealer = _dealer_contract_evidence(updated, duplicate_indexes, credits)
    # §8.1, §8.10: an insurer's credit paid for the business's work (a holder trade, a service form, or three or more
    # from one insurer within 31 days; _insurer_for_work) is re-stated before the facts, as B3's processor release is:
    # an unverified deposit of method INSURER_FOR_WORK_METHOD, unclaimed, so §8.10's holds 4 to 11 still read it, never
    # toward a Q5 or Q6 repeat, and tiered counted_flagged / insurer_paid_for_services where no hold names it. The
    # reason names the ground alone.
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
    # A settlement under the merchant's own name that an earlier rule verified, which only the bare settlement word
    # lifted from the own-push guard (CreditFacts.settlement_released), leaves verification before the repeats and the
    # tiers read it (_settlement_never_verified), its facts read again: every hold still reads it, and it is never a
    # repeat. A credit under $1 keeps the floor's hold, which runs after the tiers.
    for index in credits:
        record = updated[index]
        if (
            record.revenue_classification == "verified_revenue" and facts[index].settlement_released
            and not _under_micro_floor(record)
        ):
            updated[index] = _settlement_never_verified(record)
            facts[index] = facts_of(index)
    # §8.1, §8.10: on a statement that shows no dealer (_dealer_statement, read over every non-duplicate record), an
    # equipment auction's or a car buyer's seller payout and a printed sale of a truck, trailer, vehicle or equipment
    # are asset-sale proceeds (asset_sale_reading): read here on the unverified rows and on the rows an invoice or
    # customer-payment descriptor verified, never counted toward a repeat nor verified by Q5 or Q6, and made
    # non_revenue by the tier loop where the row would be counted or that verification stands (a held tier keeps the
    # row held).
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
    # credit under $1, a row a family rule decides alone or a deferred source (_never_q5_or_q6), and on the wire channel
    # only an incoming wire (§8.5: the loose wire words are for tiering only). Never a Q7 row either: a lender's dealer
    # funding verifies by §8.7 alone, and Q6's lenders never count. Q11 (b): nor a row the asset-sale reading names.
    never = {
        index: _never_q5_or_q6(updated[index], texts[index], facts[index]) or index in asset_sales
        for index in credits
    }
    counting = Counter()
    consumer_only: dict[tuple[str, tuple[str, ...]], bool] = {}
    for index in credits:
        record, fact = updated[index], facts[index]
        # The holder's own push never counts toward a repeat, verified or not.
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
    # counts toward it (§5.2, §7.0).
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
    # The statement's posted credits in cents, non-revenue included (the T7 base), which the lump-sum test reads, and
    # the financiers' payouts the tiers give (index -> financier).
    posted_cents = sum(_cents(records[index].amount) for index in credits)
    financier_payouts: dict[int, str] = {}
    for index in credits:
        record, fact = updated[index], facts[index]
        # A factoring payer's credit is never verified, whichever earlier rule verified it. Nor is a factoring payee's
        # (the ledger's factoring aliases, a factoring review entity), whose name may print no financing word
        # ('<factor> OPER DES:INVOICE PMT' is an invoice descriptor's). A credit under $1 is left to the floor, which
        # holds it with its own method, rule and sentence naming the rule it overruled, as the self-own arm below
        # leaves it.
        factor = fact.factor or record.classification == "factoring"
        if record.revenue_classification == "verified_revenue" and factor and not _under_micro_floor(record):
            updated[index] = _with_tier(_factor_never_verified(record), "counted_flagged", "factoring_payout")
            continue
        # Nor is the holder's own push, which an earlier rule verified (an accounts-payable entry read by step 11):
        # held as the holder's name. A credit under $1 keeps the floor's hold, which runs after this.
        if record.revenue_classification == "verified_revenue" and fact.self_own and not _under_micro_floor(record):
            updated[index] = _with_tier(_holder_never_verified(record), "excluded_pending_review", "holder_name")
            continue
        # Nor is a lease-to-own or patient financier's merchant payout, whichever earlier rule verified it: counted and
        # flagged, and read by the lump-sum test below.
        if record.revenue_classification == "verified_revenue" and fact.financier:
            updated[index] = _with_tier(
                _financier_never_verified(record), "counted_flagged", CUSTOMER_FINANCING_PAYOUT
            )
            financier_payouts[index] = fact.financier
            continue
        # §8.7: nor is a listed auto lender's credit Q7 read on a payables word alone, on a statement that shows no
        # dealer evidence: a lender paying the business for its services (a repossession agency's recoveries), counted
        # and flagged, or held as financing_named_payer when the lender also collects from the account
        # (_payer_collects, the hidden-loan guard).
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
        # Nor is a non-dealer's printed vehicle sale an invoice or customer-payment descriptor verified (asset_sales):
        # asset-sale proceeds, non_revenue / asset_sale_proceeds.
        if record.revenue_classification == "verified_revenue" and index in asset_sales:
            updated[index] = _with_tier(_asset_sale_record(record, asset_sales[index]), "non_revenue", ASSET_SALE_METHOD)
            continue
        # Nor is a builder's progress draw an earlier rule verified (§7.5's accounts-payable remittance): counted and
        # flagged, never verified. A credit under $1 is left to the floor, as the factoring arm's is.
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
            # A government payment that prints no purpose is named in the non-revenue breakdown; every other verified
            # or non_revenue row carries no reason, as before.
            no_purpose = tier == "non_revenue" and record.revenue_match_method == GOVERNMENT_NO_PURPOSE_METHOD
            updated[index] = _with_tier(record, tier, GOVERNMENT_NO_PURPOSE if no_purpose else None)
            continue
        round_repeat = fact.round_sum and bool(fact.key) and round_sums[fact.key] >= 2
        tier, reason = _tier_reason(
            record, texts[index], fact, round_repeat, _deferred_source(texts[index], fact),
            unread=index in unread_indexes, unread_text=unread_texts.get(index, ""),
        )
        # Asset-sale proceeds where the tier would count the row, or where only IAA's insurer-name hold reads it (its
        # INSURANCE is the auction's name); every other hold wins.
        if index in asset_sales and (tier == "counted_flagged" or reason == "insurer_named_payer"):
            record = _asset_sale_record(record, asset_sales[index])
            tier, reason = "non_revenue", ASSET_SALE_METHOD
        updated[index] = _with_tier(record, tier, reason)
        if reason == CUSTOMER_FINANCING_PAYOUT:
            financier_payouts[index] = fact.financier
    # A financier's credit whose claim the non-sale or financing veto lifted and that the rules counted (an abbreviated
    # advance, ADVNC, ADVN or ADVC, which no hold reads) is read by the lump-sum test as the payout it was read as
    # before the veto (_vetoed_financier), so a large one-off advance stays held until sourced; its counted reason is
    # kept otherwise.
    for index in credits:
        if (
            index not in financier_payouts and updated[index].revenue_tier == "counted_flagged"
            and not facts[index].claimed
        ):
            vetoed = _vetoed_financier(updated[index], texts[index])
            if vetoed is not None:
                financier_payouts[index] = vetoed
    # §8.9, §8.10: after the tiers and before the Zelle step, a financier's payout that is a large one-off lump sum is
    # held until sourced (_customer_financing_lump), read over every payout the tiers gave.
    for index in financier_payouts:
        if _customer_financing_lump(index, financier_payouts, updated, facts[index].channel, posted_cents):
            updated[index] = _with_tier(updated[index], "excluded_pending_review", CUSTOMER_FINANCING_LUMP_SUM)
    # §8.4, §8.10: the last tier step, after every tier and before the $1 floor. Every Zelle deposit the rules tiered
    # is excluded (_zelle_excluded), a hold or a count alike; a row a non-revenue rule decided keeps that rule, and a
    # direction conflict keeps its hold. Nothing before this step changes: the facts, the holds, Q5's and Q6's counts
    # and a sender's named round sums still read Zelle rows. The floor and every later step skip the rows this step
    # excludes (they are non_revenue). The stored reading only; the counted reading (`zelle_true_revenue`) skips it.
    for index in credits:
        record = updated[index]
        if (
            not zelle_true_revenue
            and zelle_deposit(texts[index]) and record.revenue_classification != "non_revenue"
            and record.revenue_match_method != "direction_conflict"
        ):
            updated[index] = _zelle_excluded(record)
    # §7.0, §7.8, §8.10: the $1 floor is absolute, so it runs after every verification. A posted credit under $1 that
    # any rule verified or counted (a single-row rule, the registry's own context, a descriptor or a remittance, reads
    # no floor of its own) is held as _MICRO_DEPOSIT_REASON; a held one keeps its first hold (§8.10's order) and a
    # non-revenue one stays non-revenue. None counted toward a repeat above (_never_q5_or_q6).
    for index in credits:
        record = updated[index]
        if _under_micro_floor(record) and record.revenue_tier in {"verified", "counted_flagged"}:
            updated[index] = _held_by_the_floor(record)
    # §8.10: the step after the $1 floor. On a statement whose printed title reads PREMIUM TRUST (premium_trust_title,
    # read by classify_statement_transactions on the statement's own fields), every posted credit a rule verified or
    # counted is held as PREMIUM_TRUST_REASON (_held_in_premium_trust): the Q5, Q6 and Q7 verifications, the demotions,
    # the insurer-for-work release and every count before it included. A held credit keeps its first hold (a direction
    # conflict and the floor's included) and a non-revenue credit stays non-revenue (duplicates, lender proceeds, premium
    # finance, own transfers, the Zelle step's); Q5's and Q6's repeat counts are unchanged.
    if premium_trust:
        for index in credits:
            if updated[index].revenue_tier in {"verified", "counted_flagged"}:
                updated[index] = _held_in_premium_trust(updated[index], premium_trust)
    # §8.5, §10.7: the last step, on the final tiers (a premium trust account's held wire keeps wire_no_sender and gets
    # it too). Each held wire with no sender carries the Lenders or Potential Lenders series that start after it
    # (funding_series_after); nothing else changes.
    return funding_series_after(updated, duplicate_indexes, statement_start)


_Q6_REASONS = {
    "named_payer_repeats": "The same named payer pays the business twice or more in the statement.",
    "named_payer_company_form": "A named company pays the business by ACH or EFT.",
    "public_or_healthcare_payer": "A government or healthcare payer pays the business.",
}


def registry_financing_root(record: TransactionClassification, text: str) -> bool:
    """G2 on a registry row: a registry financing word (registry_financing), or a financing root glued inside a word
    of the row before its receiver fields, the holder's own words (on a store-name platform) and §7.0's FUNDING
    settlements aside. A root inside a place name (a city whose name holds LEND) is not one: the registry's reads
    are whole words."""
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
    same way, as the record's claim reads it. `claimed` is the pass's own claim (§8.1: the holds, the holder's
    included, skip a row the registry, a payout entity or a factoring payee claimed), which the census's holder guards
    read. The facts read the pass's own text, TD Canada Trust's e-Transfer code dropped (without_transfer_code).
    `zelle_true_revenue` is the snapshot's reading, which the progress_draw fact follows as the pass's payer facts do
    (credit_facts). The pass's own text is pass_text (PNC's ZEL read as ZELLE)."""
    classifier = _classifier()
    text = pass_text(record, text)
    region = classifier.payer_region(text)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    words = classifier._without_receiver_value(text)
    known = match_known_payee(words, credit=True)
    # G12 (§8.7): Q7's payer and veto words, read as dealer_funding_reading reads them (the holder's name never names a lender).
    listed = _dealer_funding_payer(words) is not None
    union = bool(_CREDIT_UNION_PAYER.search(region))
    # The pay and benefit words are read as the holds read them, without the holder's own name runs (and its
    # other business names, _holder_strip_names).
    also = _holder_strip_names(record)
    pay_row = _without_holder_name(row, _holder(record), also=also)
    return {
        "claimed": _claimed(record, text),
        "financing_root": financing_named(text, region, entry, _holder(record), bank=record.bank, also=also),
        "registry_root": registry_financing_root(record, text),
        "registry_financing": registry_financing(record, text),
        "pay_or_personal": bool(
            _PAY_WORDS.search(pay_row) or _EARNED_WAGE_ACCESS.search(pay_row) or cpa_payroll_code(pay_row, record.bank)
            # With the statement's bank, as the hold reads it.
            or _personal_income(text, pay_row, record.bank)
            # The direct-deposit words with the row's own sign of a person's pay (a person receiver, a consumer
            # entry); the account's shape is the statement's, which the pass alone reads (a row it holds on that shape
            # is out of True).
            or _direct_deposit_pay(text, pay_row, _holder(record), business=True)
        ),
        # The pass's own reading (_transfer_reading): the statement's bank, the explicit deposit forms. And an ACH pull
        # whose payer region is only a bank (_bank_only_pull).
        "transfer_no_counterparty": _transfer_reading(record, text, _channel(text, record.bank), region)[2],
        # The payer region names only a bank (_bank_only_payer), which Q6 never verifies.
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
        # The payer region reads past a bank's label, entry or reference.
        "payer_label_layout": classifier.payer_label_layout(text),
        "premium_coded": _premium_coded(text, region),
        "factoring_payer": _factoring_payout_payer(region, text),
        # The lease-to-own or patient financier whose merchant payout the row is (a ledger entity name, or None),
        # which the census's narrowing and declared demotion read.
        "customer_financing_payer": _customer_financier(record, text),
        # The row is a factoring review entity's credit, routed to the factoring payout, unconfirmed.
        "factoring_review": (
            record.classification == "factoring" and record.match_method == "unconfirmed_flag_payee_alias"
        ),
        "deferred_source": _deferred_reading(text, _channel(text), region, entry),
        "short_healthcare_alias": (
            bool(region) and registry_match(region, HEALTHCARE_PAYER_ALIASES) is not None
            and healthcare_payer_match(region) is None
        ),
        # An ordinary payer's disbursement entry, which the purpose-only spare drops from the non-sale reading when it
        # repeats in the statement (the pass's spared refused word; read here on the row).
        "spared_disbursement": bool(region) and _disbursing_payer(text, region) and _disbursement_entry(text, region),
        # A hold word only the trade-name reader's purpose arm spared (the pass's refused word, read on the hold's
        # text without the holder's names, as hold_rule reads it).
        "purpose_trade_name": purpose_trade_name(
            text, _without_holder_name(_hold_text(text), _holder(record), also=also), region
        ),
        # A builder's progress draw on a row nothing claimed, as the pass's payer facts read it
        # (CreditFacts.progress_draw).
        "progress_draw": not (_claimed(record, text) or _factoring_payout_payer(region, text))
        and construction_progress_draw(text, region, _holder(record), also=also, zelle_true_revenue=zelle_true_revenue),
        # The pass's channel and payer key as a digest (never a name), by which the census finds a Q5 or Q6 repeat whose
        # same-payer row Q11 keeps from the repeat (an asset sale, a builder's progress draw).
        "payer_key_digest": payer_key_digest(text, region, record.bank),
    }


def payer_key_digest(text: str, region: str, bank: str | None = None) -> str | None:
    """Sixteen hex digits of the SHA-256 of the row's channel and the payer key Q5 and Q6 group a repeat by (_channel,
    the classifier's _payer_key of the payer region), or None where the region names no payer. Rows of one payer on one
    channel share it; it never prints the payer's name."""
    key = _classifier()._payer_key(region) if region else ()
    if not key:
        return None
    return hashlib.sha256(f"{_channel(text, bank)}|{' '.join(key)}".encode("utf-8")).hexdigest()[:16]


def hold_rule(record: TransactionClassification, text: str, region: str, entry: str) -> str | None:
    """Final review I7 (a census fact): which 5.6 hold reading of §20 names the row, in §8.10's order: a bank that
    originates the wire, a financing root, a lending bank (the financing holds); a government benefit (GOV, the
    personal-income hold); a government grant (GOV), a title firm, the holder's currency conversion, a personal trust,
    owner money (the non-sale holds); a payroll provider's tax-service credit (the non-sale hold after the
    counter-debit holds); or None. The census keys a Q5 or Q6 row's later hold on it. A gambling payout, a legal
    settlement and an owner-shaped payer's DISB, after a personal trust and before owner money. Each read as
    non_sale_purpose reads it (owner money by owner_money_platform)."""
    classifier = _classifier()
    # The holder's other business names are stripped as the holds strip them.
    also = _holder_strip_names(record)
    row = _without_holder_name(_hold_text(text), _holder(record), also=also)
    if _bank_originated_wire(text, region, wire=_channel(text, record.bank) == "wire"):
        return "bank_originated_wire"
    if financing_named(text, region, entry, _holder(record), bank=record.bank, also=also):
        return "financing_root"
    # A lending bank named as the payer (the financing hold).
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
        # Read as non_sale_purpose reads it.
        or owner_money_platform(text, row, region)
        or classifier._matches_any(row, classifier._SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS)
    ):
        return "owner_money"
    if payroll_tax_credit(text, region):
        return "payroll_tax"
    return None
