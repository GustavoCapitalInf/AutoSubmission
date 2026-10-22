"""Asset-sale platform and reading."""
from __future__ import annotations

import re
from typing import Sequence, TYPE_CHECKING

from analysis.classification.record import _replace_revenue_state
from analysis.classification_registry import (
    ASSET_SALE_PAYERS,
    ASSET_SALE_SELLER_WORD_ONLY,
    WHOLESALE_AUCTION_PAYOUT_FORMS,
)
from analysis.descriptor.holder import account_name_text
from analysis.true_revenue.dealer import _dealer_activity
from analysis.true_revenue.eligibility import _b_o_field, _factor_tail
from analysis.true_revenue.hold_text import _hold_text, _payer_name_proper, _prints_payer_name_field
from analysis.true_revenue.holder_names import _holder, _holder_names, _holder_strip_names, _without_holder_name
from analysis.true_revenue.model import CreditFacts
from analysis.true_revenue.purpose import _vendor_payment
from analysis.true_revenue.words import ASSET_SALE_METHOD, _DEALER_HOLDER_VETO, _IAA, _POSSIBLE_RETURN
from analysis.true_revenue.zelle import zelle_deposit

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


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
#: Q11 (b): a refund word, which no asset sale prints (a buyer's refund, a platform's refund of a purchase).
_ASSET_SALE_REFUND = re.compile(r"[A-Z]*REFUND\w*|(?<![A-Z])(?:RFND|REFND)\w*")
#: Q11 (b): the dealer-only wholesale auctions of §7.8, whose payout credit is dealer evidence for Q11 (never for Q9's
#: payables, _dealer_activity).
_WHOLESALE_AUCTION_ENTITIES = frozenset(WHOLESALE_AUCTION_PAYOUT_FORMS)


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
    holder = account_name_text(_holder(record)) or ""
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
    for name in _holder_names(records[indexes[0]]):
        printed = account_name_text(name) if name else ""
        if printed and _ASSET_TRADE_HOLDER.search(printed) and not _DEALER_HOLDER_VETO.search(printed):
            return True
    return False


def _asset_sale_record(record: TransactionClassification, arm: str) -> TransactionClassification:
    """§8.1, §8.10: the record made non_revenue as a non-dealer's asset-sale proceeds (method ASSET_SALE_METHOD, rule
    asset_sale_payer or asset_sale_purpose); its reason names the rule it overrules, for the audit. The pass gives it
    the reason code asset_sale_proceeds; it has no review path."""
    return _replace_revenue_state(
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
