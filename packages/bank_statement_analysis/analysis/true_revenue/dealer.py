"""Dealer funding reading and funding_series_after."""
from __future__ import annotations

import math
import re
from dataclasses import replace
from datetime import date as _date
from typing import Sequence, TYPE_CHECKING

from analysis.classification.credit_predicates import _split_glued_claim
from analysis.classification.payees import _descriptor_proceeds, _insurance_registry_match, _is_payroll_provider_row
from analysis.classification.record import DealerFunding, FundingSeries, _promotion_cadence
from analysis.classification.tax_forms import _NON_REVENUE_CREDIT_PATTERNS
from analysis.classification_registry import (
    DEALER_FUNDING_PAYERS,
    FLOOR_PLAN_ALIASES,
    POTENTIAL_LENDER_ALIASES,
    WHOLESALE_AUCTION_REFUND_NAMES,
)
from analysis.dates import parse_date
from analysis.descriptor.holder import account_name_text
from analysis.descriptor.lexical import _before_receiver, _originator_segment, payer_name, revenue_text
from analysis.descriptor.payer import channel_gate, entry_fields, payer_region
from analysis.descriptor.rails import _matches_any, _without_receiver_value
from analysis.descriptor.words import _CARD_FORM_DEBIT_PREFIX
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import match_known_payee, registry_match
from analysis.true_revenue.channel import _channel, _transfer_wording
from analysis.true_revenue.holder_names import _holder_names, without_receiver_and_holder
from analysis.true_revenue.public_payers import _personal_income
from analysis.true_revenue.purpose import non_sale_purpose
from analysis.true_revenue.words import (
    DEALER_FUNDING_WORDS,
    _BANK_OR_TITLE_SENDER,
    _CARD_CREDIT_LABEL,
    _CARD_FORM_DEBIT,
    _CLAIM_WORD,
    _CREDIT_UNION_PAYER,
    _DEALER_FUNDING_VETO,
    _DEALER_HOLDER_VETO,
    _DIRECT_DEPOSIT_WORDS,
    _FINANCING_ROOT,
    _HOLD_POSTING_LABELS,
    _INSURER_NAME,
    _PAY_WORDS,
    _POSSIBLE_RETURN,
    _VEHICLE_PURCHASE_ENTRY,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.7: the dealer-payables words a listed auto lender prints on its dealer funding (Westlake's DES:PAYABLES).
_DEALER_PAYABLES_WORDS = re.compile(r"\bPAYABLES\b|\bTRADE PAY\w*|\bACCT FUND\w*")
#: §8.7: a lender's floor-plan (wholesale) financing of the dealer's inventory is never dealer funding.
_DEALER_FLOOR_PLAN_WORDS = re.compile(r"(?<![A-Z])(?:FLOOR\w*|WHOLESALE\w*)")
#: §8.1, §8.7: a floor-plan lender's name on a wire's sender (_dealer_word_lender): a floor-plan form, or WHOLESALE
#: beside a lender's or a vehicle trade's whole word ('<NAME> WHOLESALE AUTO LLC'); never a flooring contractor's or a
#: wholesale grocer's name ('<NAME> FLOORING LLC', '<NAME> WHOLESALE GROCERS INC'). And a finance company's glued
#: spellings that the financing root does not read (FINCO, FINCORP, CAPCO, CAPCORP, AUTOFIN).
_FLOOR_PLAN_LENDER_WORDS = (
    r"(?:FUND|FUNDS|FUNDING|FIN|FINANCE|FINANCIAL|FINANCING|LEND|LENDER|LENDERS|LENDING|CAP|CAPITAL|CREDIT|AUTO|AUTOS"
    r"|AUTOMOTIVE|MOTOR|MOTORS|DEALER|DEALERS|FINCO|FINCORP|CAPCO|CAPCORP|AUTOFIN)"
)
_FLOOR_PLAN_LENDER_NAME = re.compile(
    r"(?<![A-Z])FLOOR ?PLAN\w*"
    rf"|(?<![A-Z])WHOLESALE\w* {_FLOOR_PLAN_LENDER_WORDS}(?![A-Z])"
    rf"|(?<![A-Z]){_FLOOR_PLAN_LENDER_WORDS} WHOLESALE\w*"
)
#: §8.7: dealer evidence on a statement's rows: a floor-plan form printed anywhere (FLOORPLAN, FLOOR PLAN), beside
#: the registry's floor-plan financiers (FLOOR_PLAN_ALIASES). The form's own words only, FLOORPLAN(S) and FLOOR
#: PLANNING, never FLOORPLANNER (a planning tool's subscription) or FLOOR PLANKS (flooring). And the glued words a
#: narrow field prints, FLOORPLANINT, FLOORPLANPAYOFF, FLOORPLANADV and FLOORPLANXPRESS.
_FLOOR_PLAN_FORM = re.compile(r"(?<![A-Z])FLOOR ?PLAN(?:S|NING|INT|PAYOFF|ADV|XPRESS)?\b")
#: A floor-plan financier's credit printing service wording (a vendor payment, a repossession, a recovery, a tow, a
#: transport, an inspection, a commission) pays the business for its services and is no dealer evidence; every corpus
#: floor-plan credit is a VIN-bearing dealer advance, which still is.
_FLOOR_PLAN_SERVICE_CREDIT = re.compile(
    r"(?<![A-Z])(?:VENDOR ?(?:PMT|PAY|PAYMENT)|REPO|REPOS|REPOSSESS\w*|RECOVER\w*|TOW(?:ING|S)?|TRANSPORT\w*|INSPECT\w*"
    r"|COMMISSIONS?)\b"
)
#: §8.7: a dealer's name on the holder's name (the Q11 holder reading): a vehicle or
#: equipment noun before a dealer's trade word, or a dealership's own word. Never read where the same name prints a
#: recovery, repossession, towing or collateral word (_DEALER_HOLDER_VETO): a repossession or towing agency named
#: '<NAME> AUTOMOTIVE RECOVERY' is no dealer.
_DEALER_HOLDER_NAME = re.compile(
    r"(?<![A-Z])(?:AUTOS?|CARS?|TRUCKS?|TRAILERS?|EQUIPMENT|TRACTORS?|MOTOR|RVS?|BOATS?|MARINE|MACHINERY|POWERSPORTS"
    r"|MOTORSPORTS) (?:SALES|DEALERS?|DEALERSHIP|MART|OUTLET|EXCHANGE|SUPERSTORES?)\b"
    r"|(?<![A-Z])(?:MOTORS|AUTOMOTIVE|AUTO GROUP|AUTO PLAZA|AUTO MALL|DEALERSHIP|CAR LOT)\b"
)
#: §7.8, §8.7: the dealer-only wholesale auctions' names on a posted debit (the registry's
#: WHOLESALE_AUCTION_REFUND_NAMES: MANHEIM, ACV AUCTIONS, OPENLANE or BACKLOT CARS), a purchase there being dealer
#: evidence.
_WHOLESALE_AUCTION_DEBIT_NAMES = tuple(re.compile(pattern) for pattern in WHOLESALE_AUCTION_REFUND_NAMES.values())


def _listed_auto_lender(text: str) -> tuple[str, str] | None:
    """§8.7: the listed auto lender the originator segment names, and the alias that named it: a vehicle_financing
    registry entity or a DEALER_FUNDING_PAYERS entry; or None."""
    segment = _originator_segment(text)
    known = match_known_payee(segment, credit=True)
    if known is not None and known.state == "vehicle_financing":
        return known.entity, known.alias
    return registry_match(segment, DEALER_FUNDING_PAYERS)


def _dealer_funding_payer(text: str) -> str | None:
    """§8.7: the listed auto lender the originator segment names (_listed_auto_lender), or None."""
    found = _listed_auto_lender(text)
    return found[0] if found is not None else None


def _q7_refused_by_a_hold(text: str, words: str, region: str) -> bool:
    """§8.1: Q7 decides at step 4, before any hold of §8.1 reads the row, so it refuses a row whose wording one of
    those holds names, fail closed: the pay and personal-income words and the payroll providers (Q8, G11), a non-sale
    purpose, a possible return (an overpaid payoff refunded, an adjustment, a credit memo, a dispute), an insurer or
    claim word, and a floor-plan word (FLOOR..., WHOLESALE). Each reads as §8.1 reads it, on the row before its
    receiver fields, and again on the whole row without the receiver field's value, as the Q7 veto words do (a BofA PMT
    INFO addenda after the receiver prints the lender's own words; the holder's name never refuses). Such a row keeps
    the reading it has without Q7: a ledger lender's financing proceeds, or a held row."""
    if _CARD_CREDIT_LABEL.search(text) or non_sale_purpose(text, region) or non_sale_purpose(words, region):
        return True
    for row in (_before_receiver(text), words):
        hold = _HOLD_POSTING_LABELS.sub(" ", row)
        if (
            # The direct-deposit words still refuse Q7 alone (G11, fail closed).
            _PAY_WORDS.search(row) or _DIRECT_DEPOSIT_WORDS.search(row) or _is_payroll_provider_row(row)
            or _personal_income(text, row)
            or _POSSIBLE_RETURN.search(hold)
            or _INSURER_NAME.search(hold) or _CLAIM_WORD.search(hold)
            or _DEALER_FLOOR_PLAN_WORDS.search(row)
        ):
            return True
    return False


def dealer_funding_reading(text: str) -> DealerFunding | None:
    """§6.1 step 4 (Q7), read on a credit's revenue text: arm 'listed' when a listed auto lender pays dealer-funding
    words, 'credit_union' when a credit union prints the VHCL PURCH entry (the statement pass decides it), each with
    the lender it names; or None. Never on a row that names a lender outside vehicle financing, a potential lender or
    an insurer, that prints a loan, proceeds, advance or refund word, or that the channel gate closes; nor on a row
    whose wording a hold of §8.1 names.

    The lender is read on the originator segment without the receiver field's value, and the veto words on the whole
    row without it (S4.3, §5.2: the holder's name never names a payer, and never vetoes one; a BofA PMT INFO addenda
    after the receiver still prints the row's own words). §6 precedence (S4.3): the non-revenue rules stay first, so
    Q7 also never fires on a row the strong non-revenue rule or D1's descriptors decide, or that prints transfer
    wording (Q4: a named transfer is never Verified), and a push rail is the registry's alone (§6.1 step 9b). The
    caller keeps steps 2 and 3 ahead of it (a direction conflict and a reversal marker win) and the $1 floor (§7.0)."""
    row = _before_receiver(text)
    # Both arms need their word (a wire's entry fields may run past the row, so the VHCL PURCH entry is looked for on
    # the whole text): a row that prints neither is refused before the slower readers run.
    if not (
        DEALER_FUNDING_WORDS.search(row) or _DEALER_PAYABLES_WORDS.search(row) or _VEHICLE_PURCHASE_ENTRY.search(text)
    ):
        return None
    words = _without_receiver_value(text)
    region = _dealer_funding_region(text, row, words)
    if region is None:
        return None
    lender = _listed_auto_lender(words)
    word = DEALER_FUNDING_WORDS.search(row) or _DEALER_PAYABLES_WORDS.search(row)
    if lender is not None and word is not None:
        return DealerFunding("listed", lender[0], lender[1], word.group(0))
    entry = _VEHICLE_PURCHASE_ENTRY.search(entry_fields(text) or row)
    if _CREDIT_UNION_PAYER.search(region) and entry is not None:
        # The credit union as its payer region prints it (§5.2: never a receiver field): no registry names it.
        return DealerFunding("credit_union", payer_name(region) or region, region, entry.group(0))
    return None


def _dealer_funding_region(text: str, row: str, words: str) -> str | None:
    """§6.1 step 4 (Q7): the payer region of a credit Q7 may read, or None when one of its refusals names the row (the
    loan, proceeds, advance and refund words, the channel gate, the strong non-revenue rule and D1's descriptors,
    transfer wording, a hold's wording, a lender outside vehicle financing, a potential lender, an insurer)."""
    if (
        _DEALER_FUNDING_VETO.search(words)
        or channel_gate(text) is not None
        or _matches_any(words, _NON_REVENUE_CREDIT_PATTERNS)
        or _descriptor_proceeds(text) is not None
        or _transfer_wording(row)
    ):
        return None
    region = payer_region(text)
    if _q7_refused_by_a_hold(text, words, region):
        return None
    known = match_known_payee(text, credit=True)
    if known is not None and known.state in FINANCING_STATES and known.state != "vehicle_financing":
        return None
    if registry_match(text, POTENTIAL_LENDER_ALIASES) is not None:
        return None
    # Final review M9: the insurer is read as step 5 reads it, on the lookup text (a glued HCCLAIMPMT split from the
    # name before it, _split_glued_claim).
    if _insurance_registry_match(_split_glued_claim(text), glued_digits=True) is not None:
        return None
    return region


def credit_union_dealer_entry(text: str) -> DealerFunding | None:
    """§8.7: a credit union's other dealer-funding entry, read on a credit's revenue text: a credit union named on the
    payer region (_CREDIT_UNION_PAYER, no listed auto lender) prints a dealer-funding word other than the VHCL PURCH
    entry ('VADMIN FEE', the same deal's admin fee), and none of Q7's refusals names the row (_dealer_funding_region).
    Arm 'credit_union_entry', with the credit union as its payer region prints it; or None. The statement pass verifies
    it beside the same credit union's verified VHCL PURCH credits, or one that prints its deal ID (_DEAL_ID)."""
    row = _before_receiver(text)
    word = DEALER_FUNDING_WORDS.search(row)
    if word is None or _VEHICLE_PURCHASE_ENTRY.search(entry_fields(text) or row):
        return None
    words = _without_receiver_value(text)
    region = _dealer_funding_region(text, row, words)
    if region is None or not _CREDIT_UNION_PAYER.search(region) or _listed_auto_lender(words) is not None:
        return None
    return DealerFunding("credit_union_entry", payer_name(region) or region, region, word.group(0))


def _dealer_word_lender(text: str, region: str) -> bool:
    """§8.1, §8.7: the dealer-word hold reads every row but a wire whose purpose alone prints the word and whose
    sender is a named non-lender ('B/O <person> ... OBI VEHICLE PURCHASE', a customer's own wire to the dealer): Q5
    reads that wire. A wire is still held when it names no sender, when the sender's own name prints the word, or when
    the sender reads as a lender, a credit union or a bank: a financing root, a floor-plan lender's name (round 2,
    _FLOOR_PLAN_LENDER_NAME: a floor-plan form, or WHOLESALE beside a lender's or a vehicle trade's whole word, never
    a flooring contractor, a wholesale grocer or a customer's FINE, CAPE or AUTOMATION), a credit union's or a bank's,
    title or escrow firm's form, a financing payee of the registry or a potential lender. An ACH or EFT entry printing
    the word from an unlisted originator stays held ('<NAME> AUTO DES:DEALER PAY': an auto lender the registry does
    not list)."""
    if not region or _channel(text) != "wire" or DEALER_FUNDING_WORDS.search(region):
        return True
    if (
        _CREDIT_UNION_PAYER.search(region) or _BANK_OR_TITLE_SENDER.search(region) or _FINANCING_ROOT.search(region)
        or _FLOOR_PLAN_LENDER_NAME.search(region)
    ):
        return True
    known = match_known_payee(_without_receiver_value(text), credit=True)
    if known is not None and known.state in FINANCING_STATES:
        return True
    return registry_match(region, POTENTIAL_LENDER_ALIASES) is not None


def _payables_only_dealer_funding(text: str) -> bool:
    """§8.7: a listed auto lender's credit Q7 reads on a payables word alone (PAYABLES, TRADE PAY..., ACCT FUND...):
    dealer_funding_reading's listed arm, whose word is no dealer-specific funding word (it reads one first), on a
    credit's revenue text."""
    reading = dealer_funding_reading(text)
    return reading is not None and reading.arm == "listed" and _DEALER_PAYABLES_WORDS.fullmatch(reading.word) is not None


def _dealer_activity(
    records: Sequence[TransactionClassification], duplicate_indexes: set[int], indexes: Sequence[int],
) -> bool:
    """§8.7: the statement's dealer activity, the shared core of the dealer evidence. True when one of the statement's
    credits (`indexes`, the pass's posted, non-duplicate credits) is a credit union's VHCL PURCH (method
    credit_union_vehicle_purchase) or a Q7 credit that is not payables-only (a dealer-specific word, or the credit-union
    arm); or when a posted, non-duplicate row, credit or debit, is a floor-plan financier's (classification
    floor_plan_financing, the registry's FLOOR_PLAN_ALIASES, or a FLOOR PLAN form); or when a posted, non-duplicate
    debit is a purchase at a dealer-only wholesale auction (_WHOLESALE_AUCTION_DEBIT_NAMES). A listed auto lender's
    payables-only credit is no dealer evidence: a repossession agency's own payables would make its statement a dealer's
    (the Q9 card); nor is a §7.8 auction payout credit.

    The auction arm reads a debit that is no card purchase (_card_purchase_debit: classification pos, or the card forms
    classifier._CARD_FORM_DEBIT_PREFIX and _CARD_FORM_DEBIT), so a purchase in Manheim, PA is no auction purchase, while
    an ACH, wire or check debit to the auction still is; the floor-plan form reads FLOORPLAN(S) and FLOOR PLANNING only
    (_FLOOR_PLAN_FORM: never FLOORPLANNER or FLOOR PLANKS); and a floor-plan financier's posted credit (any of the three
    arms) is evidence only where it prints no service wording (_FLOOR_PLAN_SERVICE_CREDIT, read without the receiver
    field's value: a vendor payment, a repossession, a recovery, a tow, a transport, an inspection, a commission).
    Debits are read as before. Q11 (b)'s _dealer_statement reads the same arms. The service wording is read without the
    holder's names too (without_receiver_and_holder), so a dealer advance whose unlabelled receiver is the holder's own
    name printing RECOVERY, TRANSPORT or COMMISSIONS stays evidence; a card form's '<ST> USA|CAN' tail on a wire, ACH or
    check row is no card purchase (_card_purchase_debit); and the floor-plan form reads its glued words (FLOORPLANINT,
    FLOORPLANPAYOFF, FLOORPLANADV, FLOORPLANXPRESS)."""
    for index in indexes:
        record = records[index]
        if record.revenue_match_method == "credit_union_vehicle_purchase":
            return True
        if record.revenue_match_method == "auto_lender_dealer_funding" and not _payables_only_dealer_funding(
            revenue_text(record.normalized_description)
        ):
            return True
    for index, record in enumerate(records):
        if index in duplicate_indexes or not record.is_posted:
            continue
        text = revenue_text(record.normalized_description)
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
    """A debit that is a card purchase, as the counter-debit hold reads one: the classifier's class `pos`, or a card
    form on its revenue text (classifier._CARD_FORM_DEBIT_PREFIX: CHECKCARD or PURCHASE <mmdd>; _CARD_FORM_DEBIT: DEBIT
    CARD PURCHASE, DBCRD PUR, POS DB|DEBIT|PUR, POINT OF SALE, a glued PURCHASE<digits>, a charge ending in a state or
    province code and its country). That tail, Found's and Bluevine's card-charge form, is no card purchase on a row
    that prints a wire, ACH or check form (_NON_CARD_DEBIT_FORM: 'OUTGOING WIRE <auction> ATLANTA GA USA', 'ACH DEBIT
    <auction> ... GA USA')."""
    stripped = text.strip()
    if record.classification == "pos" or _CARD_FORM_DEBIT_PREFIX.search(stripped) is not None:
        return True
    card = _CARD_FORM_DEBIT.search(stripped)
    if card is None:
        return False
    return _CARD_FORM_TAIL.fullmatch(card.group(0)) is None or _NON_CARD_DEBIT_FORM.search(stripped) is None


def _dealer_contract_evidence(
    records: Sequence[TransactionClassification], duplicate_indexes: set[int], indexes: Sequence[int],
) -> bool:
    """§8.7: the statement shows dealer evidence, which a listed auto lender's payables-only credit needs to stay
    verified as dealer funding: the statement's dealer activity (_dealer_activity), or a dealer's name on one of the
    holder's names (the first credit's _holder_names, its account name and its holder name, each read through
    account_name_text) that prints no recovery, repossession, towing or collateral word (_DEALER_HOLDER_NAME,
    _DEALER_HOLDER_VETO)."""
    if _dealer_activity(records, duplicate_indexes, indexes):
        return True
    if not indexes:
        return False
    first = records[indexes[0]]
    names = (*_holder_names(first), first.account_name, first.holder_name)
    for name in names:
        printed = account_name_text(name) if name else ""
        if printed and _DEALER_HOLDER_NAME.search(printed) and not _DEALER_HOLDER_VETO.search(printed):
            return True
    return False


#: _CARD_FORM_DEBIT's tail arm, the '<ST> USA|CAN' ending, which a wire, ACH or check debit printing its
#: beneficiary's state and country prints too (_NON_CARD_DEBIT_FORM); read by _card_purchase_debit alone (the
#: counter-debit reader keeps _CARD_FORM_DEBIT whole).
_CARD_FORM_TAIL = re.compile(r"(?<![A-Z])[A-Z]{2} (?:USA|CAN)$")
_NON_CARD_DEBIT_FORM = re.compile(r"(?<![A-Z])(?:WIRE|ACH|CHECK|CHK|CHEQUE)\b")


#: §8.5, §10.7: the funding aid's constants, whole numbers. A series' first payment comes at most
#: FUNDING_SERIES_WINDOW_DAYS after the deposit and falls on FUNDING_SERIES_MIN_PAYMENTS distinct dates or more; its
#: start is observed when the statement shows one full gap of the series, and at least
#: FUNDING_SERIES_MIN_LOOKBACK_DAYS, before the deposit.
FUNDING_SERIES_WINDOW_DAYS = 10
FUNDING_SERIES_MIN_PAYMENTS = 2
FUNDING_SERIES_MIN_LOOKBACK_DAYS = 3
#: The states the Lenders and Potential Lenders tabs list, the only payees the aid reads ("frequent payment" read as a
#: lender-side series: an all-debits pool is card purchases, payroll, own transfers and person-to-person payments).
_FUNDING_SERIES_STATES = ("confirmed_lender", "potential_lender")


def funding_series_after(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
    statement_start: str | None,
) -> list[TransactionClassification]:
    """§8.5, §10.7: pass 7's last step. Every incoming wire with no sender printed stays held (`wire_no_sender`); this
    step records on each such held credit, as `revenue_funding_series`, every series of the Lenders or Potential
    Lenders tabs that starts after it, so the review can see a funding the wire may be. It reads the records only, and
    writes that one field and only on those credits: no tier, reason, state, flag, figure, gate, debit or lender
    reading moves.

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
       A settlement-reversed debit is no payment of the series, but an attempt on or
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
    # Every attempt of a key, a settlement-reversed one included (its dates only).
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
    series: list[tuple[str, str, float, list[int], list[_date], str, float]] = []
    for (state, name, amount), indexes in groups.items():
        days = [parse_date(records[index].date) for index in indexes]
        if any(day is None for day in days):
            continue
        promotion = _promotion_cadence(records, indexes, FUNDING_SERIES_MIN_PAYMENTS)
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
                continue  # An attempt on or before the deposit's day: the series was already running
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
