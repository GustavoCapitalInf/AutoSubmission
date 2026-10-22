"""Insurer readings and insurer-for-work."""
from __future__ import annotations

import re
from datetime import date as _date
from typing import Sequence, TYPE_CHECKING

from analysis.classification.counter_debit_reading import _payer_key
from analysis.classification.credit_predicates import _split_glued_claim
from analysis.classification.payees import _insurance_registry_match
from analysis.classification_registry import INSURER_CREDIT_BRANDS
from analysis.descriptor.credit_words import _HCCLAIMPMT, _INSURER_CUSTOMER_PAYMENT
from analysis.descriptor.holder import account_name_text
from analysis.descriptor.lexical import _before_receiver, company_form
from analysis.descriptor.payer import entry_fields
from analysis.descriptor.rails import _is_wire_row
from analysis.descriptor.words import _PREMIUM_FINANCE_WORDING_PATTERNS
from analysis.true_revenue.channel import _channel, _p2p_rail
from analysis.true_revenue.claimed import _claimed
from analysis.true_revenue.eligibility import _deferred_reading, _factoring_payout_payer
from analysis.true_revenue.hold_text import _layout_entry, _title_purpose_text
from analysis.true_revenue.holder_names import _holder_names, _holder_strip_names, _without_holder_name
from analysis.true_revenue.model import InsurerReading, _under_micro_floor
from analysis.true_revenue.public_payers import government_payer, healthcare_payer, public_region
from analysis.true_revenue.self_originated_credits import _facts_region
from analysis.true_revenue.words import _CLAIM_WORD, _INSURER_NAME, _INSURER_SPELLINGS, _TITLE_FIRM

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.1 insurer_named_payer: the registry's INSURER_CREDIT_BRANDS, each pattern bounded as a whole name, (entity,
#: compiled patterns) in the table's order.
_INSURER_CREDIT_BRANDS = tuple(
    (entity, tuple(re.compile(rf"(?<![A-Z])(?:{pattern})(?![A-Z])") for pattern in patterns))
    for entity, patterns in INSURER_CREDIT_BRANDS.items()
)
#: §8.1: the revenue methods a listed insurer's credit carries (§6.1 step 5: the insurance rule's non-revenue exclusion
#: and T14's customer-payment reading), on which the reader names the registry's entity. And the release's method, so a
#: listed insurer's released credit reads as it read before the release (the registry lookup still decides; this set is
#: no claimed set).
_INSURER_REGISTRY_METHODS = frozenset({
    "insurance_provider_credit_exclusion", "insurer_customer_payment", "insurer_paid_for_services",
})


def insurer_credit_brand(region: str) -> str | None:
    """§8.1: the entity of the first INSURER_CREDIT_BRANDS carrier a payer region names, or None. Credit-only: no
    debit and no classifier rule reads it."""
    if not region:
        return None
    for entity, patterns in _INSURER_CREDIT_BRANDS:
        if any(pattern.search(region) for pattern in patterns):
            return entity
    return None


def _insurer_own_region(
    record: TransactionClassification, region: str, receiver_holders: Sequence[str] = (),
) -> str:
    """§8.1: the payer region without the holder's names (each of _holder_names by its runs, then
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
    """§8.1 insurer_named_payer: the insurer a credit's payer region names, or None; the first arm that reads wins. (a)
    An HCCLAIMPMT entry is a claim paid to a provider, never an insurer's reading (T18's claim-first rule keeps
    verifying it). (b) A listed insurer's credit (its revenue method one of _INSURER_REGISTRY_METHODS and the
    classifier's insurer lookup naming it): the registry's entity, or None for a premium financier. Read before the
    government arm, so a row the classifier's insurance rule read as a listed insurer is that insurer, government-shaped
    name or not ('ALLSTATE COUNTY', a Texas county mutual's cut the classifier's _PUBLIC_PAYER_NAME veto does not
    reach). (c) A government payer (§7.6) is an insurer only by _INSURER_NAME's spelled words or CLAIM (CLAIM never on a
    healthcare payer), read on the region without the holder's names, never for work: the reading the insurer-name hold
    makes without the widened spellings, so a government insurance programme's credit (employment, parental, disability
    or family-leave insurance, a public insurer) stays held and never counts as the business's work; the widened
    spellings and brands never read a government payer. (d) Then the region is read without the holder's names
    (_insurer_own_region); empty, None. (e) A title firm is a title insurer when an insurer word or spelling prints
    (never for work), else None. (f) A premium-finance wording on the row before its receiver fields is premium
    financing, None. (g) A healthcare payer is an insurer only by _INSURER_NAME's spelled words (Q6c unchanged). (g2) A
    §15 deferred payer (_deferred_reading: the Canadian benefit carriers, HEALTH DENTAL CLAIM, CLMEFT) only by those
    words or CLAIM: the widened spellings and brands never read it, so a medical claim payment to a provider keeps its
    tier. (h) An INSURER_CREDIT_BRANDS carrier, by the brand's entity. (i) _INSURER_NAME, _INSURER_SPELLINGS or
    _CLAIM_WORD, keyed by the payer key. No channel gate, but on a consumer person-to-person rail (_p2p_rail: Zelle,
    Interac and its e-Transfer and VIREMENT forms, Venmo, Cash App, Square Cash, Apple Cash, Popmoney) the widened
    spellings and the brands are not read: a sender's surname or given name (MUTUA, SUBROTO) or the rail's own word
    (APPLE CASH INS) is no cut insurer, so the rail keeps the spelled-out words and CLAIM only. A push or instant rail
    (RTP, FEDNOW, INSTANT PAYMENT ...), a named transfer and an ACH entry worded TRANSFER, which sit on the
    person-to-person channel too, read every spelling and the brands, except that the cut MUTUA reads there only beside
    a company form on the payer region without the holder's names (classifier.company_form: 'REAL TIME PAYMENT FROM
    <GIVEN NAME> MUTUA' is a person's surname)."""
    channel = _channel(text, record.bank)
    if _HCCLAIMPMT.search(text):
        return None
    own = _insurer_own_region(record, region, receiver_holders)
    # The registry arm reads before the government arm.
    if record.revenue_match_method in _INSURER_REGISTRY_METHODS:
        match = _insurance_registry_match(_split_glued_claim(text), glued_digits=True)
        if match is not None:
            return None if match[2] else InsurerReading(match[0], "registry", True)
    if government_payer(public_region(text)):
        if own and (
            _INSURER_NAME.search(own) or (_CLAIM_WORD.search(own) and not healthcare_payer(own))
        ):
            return InsurerReading(" ".join(_payer_key(own)) or own, "named", False)
        return None
    if not own:
        return None
    row = _before_receiver(text)
    # A consumer person-to-person rail reads the spelled-out words and CLAIM alone. Only a consumer rail; a push rail,
    # a named transfer and a TRANSFER entry read every spelling and the brands, the cut MUTUA only beside a company
    # form.
    widened = channel != "person_to_person" or not _p2p_rail(row)
    named = _INSURER_NAME.search(own) is not None
    spelled = named or (widened and any(
        found.group(0) != "MUTUA" or channel != "person_to_person" or company_form(own)
        for found in _INSURER_SPELLINGS.finditer(own)
    ))
    if _TITLE_FIRM.search(own):
        return InsurerReading(own, "title", False) if spelled else None
    if any(pattern.search(row) for pattern in _PREMIUM_FINANCE_WORDING_PATTERNS):
        return None
    key = " ".join(_payer_key(own)) or own
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
#: a vendor payment (the question's own example lines), read on the payer and the purpose words, never a wire's REF. The
#: classifier's customer-payment wording (_INSURER_CUSTOMER_PAYMENT), the service-form ground's other reader, reads the
#: row before its receiver fields, a wire's REF included: Chase's BOOK TRANSFER CREDIT and Santander print the purpose
#: there, which _title_purpose_text does not read (never a bare COMM, so 'REF COMM BANK NYC', the sending bank, stays
#: held).
_INSURER_SERVICE_FORM = re.compile(
    _INSURER_COMMISSION_FORM.pattern + r"|(?<![A-Z])(?:DRP|REPAIRS?|VENDOR ?(?:PMT|PAY|PAYMENT))(?![A-Z])"
)
#: Q2: a premium, refund, return, dividend, cancellation, overpayment, member or subscriber word, or one of the
#: personal-benefit stems DISAB..., INVALIDIT..., ANNUIT... and PENSION... (the MCA principle: personal benefits are
#: never revenue), refuses every ground, unless a commission form prints in the same words. The other
#: personal-benefit words are _INSURER_PERSONAL_BENEFIT, _INSURER_LTD_BENEFIT and _INSURER_NON_PROVIDER_BENEFIT
#: below.
_INSURER_NOT_FOR_WORK = re.compile(
    r"(?<![A-Z])(?:REFUND\w*|RFND|PREM|PREMIUMS?|PREMSEC|RETURN\w*|DIVIDEND\w*|CANCEL\w*|UNEARNED|OVERPA\w*|MEMBER"
    r"|SUBSCRIBER|MBR|DISAB\w*|INVALIDIT\w*|ANNUIT\w*|PENSION\w*)(?![A-Z])"
)
#: A disability benefit under another name (short-term disability's STD, a weekly or income benefit) and life-policy
#: money (a death or survivor benefit, a surrender, a policy's cash value, a maturity, a beneficiary's payment) refuse
#: every ground, read on the payer (without the holder's names) and the purpose, as _INSURER_NOT_FOR_WORK is. A bare
#: LIFE is never read (group health and dental claims print it).
_INSURER_PERSONAL_BENEFIT = re.compile(
    r"(?<![A-Z])(?:STD (?:BENEFITS?|BEN|BNFT|CLAIMS?|CLM|PMT|PAYMENT)|(?:WEEKLY|INCOME) (?:BENEFITS?|BEN|BNFT)|DEATH\w*"
    r"|SURVIVOR\w*|SURRENDER\w*|SURR|CASH ?VALUE|MATURITY|MATURED|BENEFICIAR\w*)(?![A-Z])"
)
#: Long-term disability's LTD before a benefit, claim or payment word, read on the purpose alone (the entry fields
#: or a wire's purpose fields), never on the payer region, where LTD is a carrier's legal form ('<carrier> CO LTD
#: DES:CLAIM PMT' is no disability benefit).
_INSURER_LTD_BENEFIT = re.compile(r"(?<![A-Z])LTD (?:BENEFITS?|BEN|BNFT|CLAIMS?|CLM|PMT|PAYMENT)(?![A-Z])")
#: Workers' compensation and a plain BENEFIT(S) wording, read on the payer and the purpose (_non_provider_benefit),
#: refuse every ground only where the holder is no provider (_holder_provider: the holder's first trade is no clinic
#: or pharmacy): a workers' compensation carrier paying a clinic, a therapy practice or a pharmacy for treatment pays
#: for its services; elsewhere it is a wage or an owner's benefit. A bare COMP is never read (Truist's 'INS COMP'
#: commission).
_INSURER_NON_PROVIDER_BENEFIT = re.compile(r"(?<![A-Z])(?:WC|WORKERS? ?COMP\w*|WORK ?COMP|BENEFITS?|BNFT)(?![A-Z])")
#: The plain benefit words of _INSURER_NON_PROVIDER_BENEFIT, and the words that, printed after one on the payer region,
#: make it the carrier's name ('MUTUAL BENEFIT INS CO', 'SAMPLE BENEFIT LIFE INS CO', 'MUTUAL BENEFIT GROUP'): an
#: insurer word or spelling (_INSURER_NAME, _INSURER_SPELLINGS) or a legal form.
_INSURER_PLAIN_BENEFIT = re.compile(r"BENEFITS?|BNFT")
_INSURER_NAME_FORM = re.compile(r"(?<![A-Z])(?:CO|COMPANY|CORP|CORPORATION|INC|LLC|LTD|GROUP)(?![A-Z])")
#: The holder trades whose insurer credits are medical claim payments to a provider.
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
    """Q2: the trade (label, word) a holder name reads: the first strict word (_SERVICE_TRADES) on the holder's
    names (_holder_names), the other business names (_holder_strip_names) and the statement's receiver-field
    holder names, in that order; only on a statement with INSURER_FOR_WORK_LOOSE_MIN_CREDITS eligible insurer
    credits or more (`eligible_count`), the first loose word; or None."""
    names = [
        printed for printed in (
            account_name_text(name)
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
    """The holder's trade, the first _holder_service_trade reads with its strict and its loose words
    (INSURER_FOR_WORK_LOOSE_MIN_CREDITS), is a clinic or a pharmacy (_PROVIDER_TRADES): a provider's insurer credit that
    prints workers' compensation or a plain BENEFIT(S) wording (_INSURER_NON_PROVIDER_BENEFIT) is paid for treatment. A
    name whose first trade is a repair shop or an insurance agency is no provider, whatever clinic or pharmacy word it
    also prints ('CONTOSO HEALTH INSURANCE AGENCY LLC', 'CONTOSO COLLISION DOCTORS LLC')."""
    trade = _holder_service_trade(record, receiver_holders, INSURER_FOR_WORK_LOOSE_MIN_CREDITS)
    return trade is not None and trade[0] in _PROVIDER_TRADES


def _non_provider_benefit(own: str, purpose: str) -> bool:
    """Workers' compensation or a plain BENEFIT(S) wording (_INSURER_NON_PROVIDER_BENEFIT) on the purpose, or on the
    payer region read without the holder's names (`own`). On the payer region a plain BENEFIT(S) or BNFT followed by an
    insurer word or spelling or a legal form is the carrier's name (_INSURER_PLAIN_BENEFIT, _INSURER_NAME_FORM: 'MUTUAL
    BENEFIT INS CO DES:DRP PAYMENT' is no benefit), while one printed after the name (a layout with no entry field:
    'SAMPLE MUTUAL INS BENEFIT PMT') and workers' compensation anywhere (WC, WORKERS COMP, WORK COMP: a workers'
    compensation carrier) are read."""
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
    """§8.1: the insurer credits pass 7 releases as the business's work, {index: ground}. A credit is eligible when the
    insurer reading (insurer_payer_reading, on the payer region the facts read) is for work; no registry, payout entity,
    factoring payee or financier claimed it (_claimed, _factoring_payout_payer: the insurer-name hold's convention); no
    not-for-work word prints on the payer (without the holder's names) or the purpose (_INSURER_NOT_FOR_WORK, unless a
    commission form prints there too); it is $1 or more, its direction agrees, and it is an unverified deposit or the
    insurance rule's non_revenue (insurance_provider_credit_exclusion): a row a classifier rule verified is left alone.
    Nor a personal benefit's word, unless a commission form prints in the same words: a disability benefit by another
    name or life-policy money on the payer or the purpose (_INSURER_PERSONAL_BENEFIT), long-term disability's LTD benefit
    on the purpose alone (_INSURER_LTD_BENEFIT: on the payer LTD is a legal form), and workers' compensation or a plain
    BENEFIT(S) wording on the payer or the purpose where the holder's first trade is no clinic or pharmacy
    (_holder_provider); a refused credit is no eligible credit, so it never counts toward its key's frequency or the
    loose-trade count. The purpose is a wire's purpose fields (_title_purpose_text, never its REF) or the entry fields,
    read with the layout entry (_layout_entry). The ground, the first that applies: 'holder_trade:<label>'
    (_holder_service_trade, with the statement's eligible count), 'service_form' (_INSURER_SERVICE_FORM on the payer and
    the purpose, or the classifier's own customer-payment wording on the row before its receiver fields, for layouts that
    print it before the payer or in a wire's REF, which Chase's book transfer and Santander print the purpose in),
    'same_insurer_3_in_31_days' (the reading's key frequent, _insurer_key_frequent: the registry's or the
    brand's entity, so one carrier is one key however it prints), and, only with the owner's switch
    INSURER_FOR_WORK_STATEMENT_ARM on, 'insurer_service_statement' (any key of the statement frequent). A credit with no
    ground is not released: a listed insurer's stays non_revenue, any other the insurer holds keep."""
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
        region = _facts_region(text, _channel(text, record.bank), record.bank, _holder_names(record))
        if _claimed(record, text) or _factoring_payout_payer(region, text):
            continue
        entry = entry_fields(text)
        reading = insurer_payer_reading(record, text, region, entry, receiver_holders)
        if reading is None or not reading.for_work:
            continue
        own = _insurer_own_region(record, region, receiver_holders)
        if _is_wire_row(text):
            purpose = _title_purpose_text(text)
        else:
            # The layout's entry (Bank of America's DES, Chase's CO ENTRY DESCR) through its helper, beside
            # entry_fields' other fields (PNC's entry, a transfer's memo).
            purpose = " ".join(part for part in (_layout_entry(text), entry) if part)
        words = f"{own} {purpose}"
        # The personal-benefit words refuse as the not-for-work words do; the commission form printed in the same words
        # still releases.
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
            or _INSURER_CUSTOMER_PAYMENT.search(_before_receiver(text))
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
