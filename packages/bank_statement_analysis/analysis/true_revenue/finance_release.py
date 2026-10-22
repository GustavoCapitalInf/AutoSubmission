"""Finance-named release, rent and lessor, payroll-tax credit."""
from __future__ import annotations

import re
from typing import Sequence, TYPE_CHECKING

from analysis.classification.counter_debit_reading import _payer_key
from analysis.classification_registry import DEALER_FUNDING_PAYERS, OPERATING_REVENUE_SOURCE_TYPES
from analysis.descriptor.holder import account_name_text
from analysis.descriptor.lexical import _before_receiver, _originator_segment, revenue_text
from analysis.descriptor.payer import entry_fields
from analysis.descriptor.rails import _without_receiver_value
from analysis.descriptor.words import REVENUE_GENERIC_WORDS
from analysis.payee_matcher import registry_match
from analysis.true_revenue.channel import _channel
from analysis.true_revenue.counter_debit_pairing import _payer_collects, counter_credit
from analysis.true_revenue.financing_roots import _RootPlaces, _accounts_payable_wording, _financing_root_places
from analysis.true_revenue.hold_text import _payer_name_proper, _prints_payer_name_field
from analysis.true_revenue.holder_names import _holder, _holder_names, _holder_strip_names, _without_holder_name
from analysis.true_revenue.model import CounterDebits
from analysis.true_revenue.self_originated_credits import _facts_region, region_names_holder
from analysis.true_revenue.sender import _bank_only_payer
from analysis.true_revenue.words import LENDER_PAID_FOR_SERVICES, _CARD_CREDIT_LABEL, _DEPOSIT_CHANNELS, _FINANCING_ROOT
from analysis.true_revenue.zelle import pass_text, zelle_deposit

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §5.3, §8.1: the reasons of T4's financing-root hold lifted (finance_named_release): (a) a customer whose own name
#: carries a finance word, paying on a line that prints invoice, accounts-payable or vendor-payment wording, and (b) a
#: rent LEASE received by a business in leasing or property; (c) is LENDER_PAID_FOR_SERVICES. Each counted and flagged,
#: never verified, never toward a Q5 or Q6 repeat.
FINANCE_NAMED_CUSTOMER = "finance_named_customer"
LESSOR_RENT = "lessor_rent"
#: Q9 (a), (c): a commission is service wording too (not Q9's own words), read on the row before its receiver
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
#: A payroll provider's tax-service credit (ADP TAX, PAYCHEX TPS TAX[ES], GUSTO TAX, INTUIT TAX), read with its tax
#: word on the payer region and the entry fields: the holder's own tax impound coming back, never a sale.
_PAYROLL_PROVIDER_WORD = re.compile(r"(?<![A-Z])(?:ADP|PAYCHEX|GUSTO|INTUIT)\b")
_PAYROLL_TAX_WORD = re.compile(r"(?<![A-Z])TAX(?:ES)?\b")


def finance_named_release(
    record: TransactionClassification,
    text: str,
    *,
    region: str,
    entry: str,
    debits: CounterDebits,
    lessor: bool = False,
) -> str | None:
    """§8.1: the reason T4's financing-root hold is lifted with on an unverified credit nothing claimed, or None. Only
    the root arm (financing_named, read by place: _financing_root_places) is lifted; every other financing arm still
    holds, and a released row takes every later hold (_first_hold's `released`).

    None when no root fires, or when the row before its receiver fields (the holder's names removed) prints PROCEEDS or a
    disbursement (_Q9_REFUSAL). (a) and (c): the root fires on the payer's name alone (no entry or row place) and the
    line prints accounts-payable, vendor-payment or invoice wording (_accounts_payable_wording, the holder's names
    removed) or a commission. Never a payer region that names only a bank; on a layout with no entry label (empty entry
    fields: the entry words print inside the payer region) never a payer reading with two or more roots or a root at or
    after the end of its first company form (_labelless_root_refusal): a single root such a layout prints cannot tell a
    name from a purpose and is read as the name. The reason is lender_paid_for_services when the payer's name reads as a
    lender's (_LENDER_NAME_WORD, a label only) or a listed auto lender (DEALER_FUNDING_PAYERS) originates the row, else
    finance_named_customer. (b): the statement's business is in leasing or property (`lessor`, _lessor_business), no
    special payer arm fired, and every place that fired is a rent LEASE alone (_rent_only), a payer place only as a memo
    printed after the payer's first company form with no root before the form's end (_rent_memo_payer): lessor_rent.

    Last, the hidden-loan guard: None when the payer also collects from the account (_payer_collects: any lender or
    other posted debit naming it, the bank's receiving fee and a card charge aside; a documented over-hold)."""
    holder = _holder(record)
    also = _holder_strip_names(record)
    places = _financing_root_places(text, region, entry, holder, bank=record.bank, also=also)
    if not places:
        return None
    row = _without_holder_name(_before_receiver(text), holder, also=also)
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
            _originator_segment(_without_receiver_value(text)), DEALER_FUNDING_PAYERS
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
    """Q9 (a), (c) on a layout with no entry label: the payer reading prints two or more financing roots, or a root at
    or after the end of its first company form (_Q9_FORM_WORD): a funder's purpose printed inside the region ('<NAME>
    CAPITAL ADVANCE VENDOR PMT', '<NAME> LLC FUNDING PAYABLES'), never released."""
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
    """§8.1: the statement's business is in leasing or property, which a rent LEASE needs to be released
    (finance_named_release). True when one of the holder's names (the first credit's _holder_names, its account name
    and its holder name, each read through account_name_text) prints a leasing or property trade word
    (_PROPERTY_TRADE); or a posted credit's revenue entity is a property-management platform
    (OPERATING_REVENUE_SOURCE_TYPES 'property_management_payments'); or two or more distinct payers pay rent: posted
    credits that no duplicate, no non_revenue rule, no card credit and no Zelle deposit is, printing RENT, RENTS,
    RENTAL(S) or a rent LEASE on the row before its receiver fields, the holder's names removed; a row with a payer
    region counts under its payer key unless the region names the holder (region_names_holder), and a payer-less row
    counts as its own payer only on a check, cash, branch or ATM deposit (a payer-less transfer, person-to-person or
    wire row never does).

    §8.1: in the third arm, a row whose payer region gives an empty payer key (an account designation: 'ONLINE BANKING
    TRANSFER FROM CHK <n> ... RENT') is no rent payer, and the rent words are read on the row with the payer's own name
    removed (_rent_payer_name), so a payer named '... RENTALS' is no rent payer while a DES entry, a memo after the
    payer's company form and a wire's REF still read."""
    if not credits:
        return False
    first = records[credits[0]]
    for name in (*_holder_names(first), first.account_name, first.holder_name):
        if name and _PROPERTY_TRADE.search(account_name_text(name)):
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
        text = pass_text(record, revenue_text(record.normalized_description))
        if _CARD_CREDIT_LABEL.search(text) or zelle_deposit(text):
            continue
        holder, also = _holder(record), _holder_strip_names(record)
        row = _before_receiver(text)
        if not _rent_words(_without_holder_name(row, holder, also=also)):
            continue
        channel = _channel(text, record.bank)
        region = _facts_region(text, channel, record.bank, _holder_names(record))
        if region and _payer_key(region) == ():
            continue
        name = _rent_payer_name(text, region)
        if name and not _rent_words(_without_holder_name(row.replace(name, " ", 1), holder, also=also)):
            continue
        if region:
            if not region_names_holder(record, text, region):
                payers.add(("payer", _payer_key(region)))
        elif channel in _DEPOSIT_CHANNELS:
            payers.add(("row", index))
    return len(payers) >= 2


def _rent_words(row: str) -> bool:
    """Q9 (b), the lessor's third arm: `row` prints RENT, RENTS, RENTAL(S) (never RENT A CAR) or a rent LEASE."""
    return _RENT_RECEIVED.search(row) is not None or _RENT_LEASE.search(row) is not None


def _rent_payer_name(text: str, region: str) -> str:
    """The payer's own name, which the lessor's third arm reads no rent word in. On a row that prints a payer-name field
    (_prints_payer_name_field: a wire's sender, an ACH originator, a transfer's sender after FROM) the name proper
    (_payer_name_proper: a wire's or an originator's whole region); on a row that prints none, the region up to the end
    of its first company form (_Q9_FORM_WORD, the _rent_memo_payer convention: '<NAME> LLC LEASE PMT' keeps its memo).
    '' for a payer-less row.

    A row that prints no payer-name field prints the entry description inside the region, so only the payer's name
    proper is removed: the region's leading rent words are the entry description a label-less layout prints first
    (Truist's '<entry> <company field> <receiver> CUSTOMER ID': 'RENT <tenant> LLC'), never the name; and with no
    company form, the name is the region up to a trade noun, RENTALS after a name word or RENTAL ending the region
    after one (_rent_trade_noun_name: 'PAYMENT <NAME> RENTALS', '<NAME> AUTO RENTALS ACH PAYMNT'), or none at all, so
    a tenant's memo after a name with no form ('<tenant> RENT 540301 ...', 'ACH DEPOSIT <tenant> RENT', '<tenant>
    RENTAL PAYMENT', 'RENTAL INCOME <tenant>') still reads."""
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
    """A label-less region with no company form, as `words`, whose name is a rental trade: the words up to and
    including RENTALS after a name word (a word of two letters or more, no generic word, no rent word), or RENTAL as
    the last word after one; '' when it prints neither."""
    for at, word in enumerate(words):
        if word not in ("RENTAL", "RENTALS") or (word == "RENTAL" and at != len(words) - 1):
            continue
        if any(
            before.isalpha() and len(before) > 1 and before not in REVENUE_GENERIC_WORDS
            and not _rent_words(before) for before in words[:at]
        ):
            return " ".join(words[: at + 1])
    return ""


def payroll_tax_credit(text: str, region: str) -> bool:
    """§8.1 non_sale_purpose: a payroll provider's tax-service credit: _PAYROLL_PROVIDER_WORD on the row before its
    receiver fields, with a TAX or TAXES word. The tax word is read on the payer region (`region`, payer_region) and
    the entry fields only, never on the rest of the row, where a layout with no receiver label prints the holder's
    own name ('<PROVIDER> DEPOSIT <ref> <NAME> TAX SERVICES LLC' is the provider paying a holder named for taxes); a
    layout that prints its entry first ('ACH TAXES <ref> PAYCHEX TPS') reads it as the payer region."""
    if _PAYROLL_PROVIDER_WORD.search(_before_receiver(text)) is None:
        return False
    return _PAYROLL_TAX_WORD.search(f"{region} {entry_fields(text)}") is not None
