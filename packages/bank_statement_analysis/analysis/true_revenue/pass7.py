"""apply_true_revenue_pass and its tables."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from typing import TYPE_CHECKING

from analysis.classification.record import _replace_revenue_state
from analysis.descriptor.lexical import revenue_text
from analysis.true_revenue.asset_sale import _asset_sale_record, _dealer_statement, asset_sale_reading
from analysis.true_revenue.counter_debit_pairing import _cents, _payer_collects, counter_credit, counter_debits
from analysis.true_revenue.dealer import (
    _dealer_contract_evidence,
    _payables_only_dealer_funding,
    credit_union_dealer_entry,
    funding_series_after,
)
from analysis.true_revenue.demotions import (
    _customer_financing_lump,
    _factor_never_verified,
    _financier_never_verified,
    _holder_never_verified,
    _lender_service_never_verified,
    _processor_card_payouts,
    _progress_draw_never_verified,
    _settlement_never_verified,
)
from analysis.true_revenue.eligibility import (
    _deferred_source,
    _never_q5_or_q6,
    _q6_eligible,
    _q6_method,
    _vetoed_financier,
    _wire_verifies,
)
from analysis.true_revenue.facts import credit_facts
from analysis.true_revenue.finance_release import _lessor_business
from analysis.true_revenue.holder_names import _receiver_holder_names
from analysis.true_revenue.insurer import _insurer_for_work, _insurer_for_work_reason
from analysis.true_revenue.model import CreditFacts, _under_micro_floor
from analysis.true_revenue.payroll import _business_shape
from analysis.true_revenue.purpose import _recurring_disbursers
from analysis.true_revenue.tiers import _held_by_the_floor, _tier_reason, _verify, _with_tier
from analysis.true_revenue.trust import _held_in_premium_trust
from analysis.true_revenue.words import (
    ASSET_SALE_METHOD,
    CONSTRUCTION_PROGRESS_DRAW_REASON,
    CUSTOMER_FINANCING_PAYOUT,
    INSURER_FOR_WORK_METHOD,
    LENDER_PAID_FOR_SERVICES,
    PROCESSOR_CARD_PAYOUT_METHOD,
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
#: §5.3: tiers by revenue state; the two middle tiers are unverified.
_TIER_OF_STATE = {"verified_revenue": "verified", "non_revenue": "non_revenue"}
CUSTOMER_FINANCING_LUMP_SUM = "customer_financing_lump_sum"
#: Q11 (b): the single-row verifications that rest on an invoice or customer-payment reference; a non-dealer's printed
#: vehicle sale is read on them too (pass 7 overrules them: a verified asset sale).
ASSET_SALE_INVOICE_METHODS = frozenset(
    {"operating_income_descriptor", "payer_remittance_descriptor", "wire_remittance_purpose"}
)


#: Spec §5.3: the display reason a government payment that prints no purpose carries (§6.1 step 3a decided it
#: non_revenue, method GOVERNMENT_NO_PURPOSE_METHOD), so the non-revenue breakdown names the excluded government money.
#: Display only: the row's tier, state, method, rule and flags are step 3a's, and it has no review path.
GOVERNMENT_NO_PURPOSE = "government_no_purpose"
GOVERNMENT_NO_PURPOSE_METHOD = "government_no_purpose_exclusion"


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
    updated = list(records)
    releases = _processor_card_payouts(records, duplicate_indexes) if PROCESSOR_CARD_PAYOUT_RELEASE else {}
    for index, entity in releases.items():
        record = records[index]
        updated[index] = replace(
            _replace_revenue_state(
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
                 if (found := _DEAL_ID.search(revenue_text(records[index].normalized_description)))}
        for index in credits:
            record = updated[index]
            if (
                index in union_rows or record.revenue_classification != "unverified_deposit"
                or not record.direction_consistent or _under_micro_floor(record)
                or record.revenue_match_method == "direction_conflict"
            ):
                continue
            text = revenue_text(record.normalized_description)
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
        index: pass_text(updated[index], revenue_text(updated[index].normalized_description))
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
        updated[index] = _replace_revenue_state(
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
