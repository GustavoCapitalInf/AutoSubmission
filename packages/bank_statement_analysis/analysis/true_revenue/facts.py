"""credit_facts, _first_hold and the §8.2 transfer reading."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from analysis.classification.counter_debit_reading import _payer_key
from analysis.descriptor.holder import holder_named, holder_receiver_block
from analysis.descriptor.lexical import _before_receiver, company_form, is_round_sum, payer_name
from analysis.descriptor.payer import entry_fields, numbered_company
from analysis.descriptor.rails import _is_wire_row
from analysis.descriptor.words import _ELECTRONIC_PAYMENT_FORM
from analysis.true_revenue.asset_sale import asset_sale_platform
from analysis.true_revenue.channel import (
    _channel,
    _explicit_deposit,
    _named_transfer_sender,
    _transfer_code,
    _transfer_counterparty_words,
    _transfer_row,
    cpa_payment_code,
)
from analysis.true_revenue.claimed import _claimed, _customer_financier, registry_financing
from analysis.true_revenue.counter_debit_pairing import also_debited, counter_credit, debited_as_lender
from analysis.true_revenue.dealer import _dealer_funding_payer, _dealer_word_lender
from analysis.true_revenue.demotions import _leading_card_credit
from analysis.true_revenue.eligibility import _factoring_payout_payer
from analysis.true_revenue.finance_release import finance_named_release, payroll_tax_credit
from analysis.true_revenue.financing_roots import financing_named
from analysis.true_revenue.hold_text import _hold_text
from analysis.true_revenue.holder_names import (
    _holder,
    _holder_names,
    _holder_strip_names,
    _receiver_alias_reads,
    _receiver_holder_named,
    _without_holder_name,
)
from analysis.true_revenue.insurer import insurer_payer_reading
from analysis.true_revenue.model import CounterDebits, CreditFacts, _under_micro_floor
from analysis.true_revenue.payroll import _pay_wording, _premium_coded, lending_bank_payer
from analysis.true_revenue.public_payers import (
    _account_designation,
    _personal_income,
    consumer_entry,
    government_payer,
    healthcare_payer,
    public_region,
)
from analysis.true_revenue.purpose import (
    _disbursement_entry,
    construction_progress_draw,
    non_sale_purpose,
    purpose_trade_name,
)
from analysis.true_revenue.self_originated_credits import (
    _bank_originated_wire,
    _facts_region,
    merchant_settlement,
    platform_credit,
    processor_payout,
    self_originated,
)
from analysis.true_revenue.sender import _bank_account_payer, _bank_only_payer, _p2p_sender_readings, _sender_key
from analysis.true_revenue.words import (
    DEALER_FUNDING_WORDS,
    INSURER_FOR_WORK_METHOD,
    PROCESSOR_CARD_PAYOUT_METHOD,
    _CARD_CREDIT_LABEL,
    _HOLDER_NAMED_SETTLEMENT_ENTRY,
    _IAA,
    _INVESTMENT_PURPOSE,
    _MICRO_DEPOSIT_REASON,
    _POSSIBLE_RETURN,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


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
    row = _before_receiver(text)
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
    if entry_fields(text).strip():
        return False
    if _bank_only_payer(region, "", record.bank, row=_before_receiver(text)) not in {"sending", "form"}:
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
    channel = _channel(text, record.bank)
    region = _facts_region(text, channel, record.bank, _holder_names(record))
    # A TD Canada Trust e-Transfer prints a per-transfer code where a sender would stand, which the pass's text no
    # longer prints (without_transfer_code): the row reads no sender and no key.
    sender, holder_sender = (
        _p2p_sender_readings(text)
        if not region and channel == "person_to_person" and _transfer_code(record) is None else ("", "")
    )
    name = payer_name(region)
    entry = entry_fields(text)
    row = _before_receiver(text)
    # A factor the registry names claims its row as a factoring payee does (only the insurer,
    # possible-return, pay and benefit holds read it), so its trade name's financing word holds nothing.
    factor = _factoring_payout_payer(region, text)
    # A lease-to-own or patient financier's merchant payout, which _claimed claims too.
    financier = _customer_financier(record, text)
    claimed = _claimed(record, text) or factor
    wire_n1 = _is_wire_row(text)
    # TD Canada Trust's trailing CPA code is an electronic-payment form.
    electronic = bool(_ELECTRONIC_PAYMENT_FORM.search(row)) or cpa_payment_code(row, record.bank)
    # §8.5: Q5 reads a healthcare payer on an incoming wire too; Q6 on an electronic-payment form.
    healthcare = healthcare_payer(region) and (wire_n1 or electronic)
    public = government_payer(public_region(text))
    transfer_row, transfer_words, no_counterparty = _transfer_reading(record, text, channel, region)
    if not region and not sender and transfer_row and transfer_words and re.search(r"\bFROM\b", row) is None:
        # T13 (S4.2 fix round 5): a named transfer printed without FROM takes the same two holds.
        sender = holder_sender = _named_transfer_sender(text)
    disbursing = bool(region) and _payer_key(region) in disbursers
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
        key=_payer_key(region) if region else _sender_key(sender),
        entry=entry,
        hold=hold,
        claimed=claimed,
        wire_n1=wire_n1,
        company_form=company_form(name),
        public_or_healthcare=public or healthcare,
        healthcare=healthcare,
        numbered=numbered_company(text, region),
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
        round_sum=is_round_sum(record.amount),
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
    # The holder-name strip reads the holder's other business names too (_holder_strip_names).
    also = _holder_strip_names(record)
    row = _without_holder_name(_hold_text(text), _holder(record), also=also)
    before = _without_holder_name(_before_receiver(text), _holder(record), also=also)
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
        _FRENCH_OWN_ACCOUNT_PAYMENT.match(_before_receiver(text))
        or _FROM_ACCOUNT_ABBREVIATION.search(_before_receiver(text))
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
    block = holder_receiver_block(text, record.bank)
    if not claimed and (
        (region or sender)
        and not merchant_settlement(text, (*names, *receiver_holders), bare_settlement=bare_settlement)
        and not processor_payout(text) and not platform_credit(text, region, (*names, *receiver_holders)) and (
            any(holder_named(region or sender, name, receiver_block=block) for name in names)
            or (
                not region and holder_sender != sender
                and any(holder_named(holder_sender, name, receiver_block=block) for name in names)
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
