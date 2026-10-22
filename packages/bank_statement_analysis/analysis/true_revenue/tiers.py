"""Tier reasons and verification; unread payer text and holder_unscreened."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Sequence, TYPE_CHECKING

from analysis.classification.credit_predicates import _named_sender_after_designation
from analysis.classification.record import _replace_revenue_state
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.holder import holder_reading, holder_words
from analysis.descriptor.payer import _is_bare_row
from analysis.payee_matcher import match_known_payee
from analysis.revenue import REVENUE_TIER_REASONS, revenue_contribution_flags
from analysis.true_revenue.claimed import _payout_entity
from analysis.true_revenue.holder_names import _holder, _receiver_holder_names, _usable_holder_name
from analysis.true_revenue.model import CreditFacts
from analysis.true_revenue.words import (
    CONSTRUCTION_PROGRESS_DRAW_REASON,
    CUSTOMER_FINANCING_PAYOUT,
    INSURER_FOR_WORK_METHOD,
    LENDER_DEBIT_STATES,
    LENDER_PAID_FOR_SERVICES,
    PROCESSOR_CARD_PAYOUT_METHOD,
    _LENDING_BANK_PAYER,
    _MICRO_DEPOSIT_REASON,
    _REGISTRY_METHODS,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: Q9: the counted reasons a released row keeps (the relabel never renames them): the owner batches' specific counted
#: reasons and the platform, payout, numbered-company and unread-payer readings.
_Q9_KEEPS = frozenset({
    "numbered_company_payer", "factoring_payout", "payout_credit_entity", "platform_unconfirmed", "payer_text_not_read",
    "customer_financing_payout", "construction_progress_draw", "insurer_paid_for_services", LENDER_PAID_FOR_SERVICES,
})


#: §8.2, §8.10: the reason of a counted credit whose payer text the parser could not read (the parser's own mark,
#: Transaction.payer_text_unread). Q2's no_payer_printed is for a row whose statement prints no payer; this one is for a
#: row whose statement printed one the parser lost. Counted and flagged, never Verified.
PAYER_TEXT_NOT_READ = "payer_text_not_read"


#: The share of a statement's posted credit rows whose payer text was not read above which the statement carries
#: the payer_text_unread fact (metrics.payer_text_unread): its True rests on rows nobody read.
PAYER_TEXT_UNREAD_SHARE = 0.30


def payer_text_unread_indexes(transactions: Sequence) -> frozenset[int]:
    """The ledger indexes of the credits the parser marked as read only by their label
    (Transaction.payer_text_unread)."""
    return frozenset(
        index for index, transaction in enumerate(transactions)
        if getattr(transaction, "payer_text_unread", False) and transaction.amount > 0
    )


#: The reason of a credit the parser marked unread whose unread run of payer blocks prints a lender's or a lending
#: bank's block (unread_run_names_financing): held, never counted, since one row of the run is that lender's money and
#: the text cannot say which.
UNREAD_RUN_NAMES_FINANCING = "unread_run_names_financing"
#: The ACH standard entry class code an ACH block closes on (`<originator> <entry> <id> <receiver> CCD`), read on the
#: normalized text: layout grammar, where a run of welded blocks splits into its blocks. A class-code word followed by
#: a legal form is part of a name, never a block's end (CashArc's ACH company name 'CASH-ARC LLC', normalized 'CASH
#: ARC LLC', the registry's alias), as the counted template's one-block count reads it
#: (core_processor_counted._ACH_CLASS_CODE). The LLC family only (LLC, L L C, LLP, PLLC), as that count reads it: INC,
#: CO, COMPANY, CORP, LTD, LP and the rest open real originator names, so a code before them closes its block and the
#: next block opens on them.
_UNREAD_BLOCK_END = re.compile(
    r"\b(?:CCD|CTX|PPD|WEB|IAT|TEL|POP|ARC|BOC|RCK|CIE)\b"
    r"(?! (?:LLC|L L C|LLP|PLLC)\b)"
)
#: The registry states whose block in an unread run holds its rows: the lender and financing states
#: (LENDER_DEBIT_STATES) without an alternative position (a platform's own settlement of the merchant's sales)
#: and a factor (whose payout is counted and flagged, never held).
_UNREAD_RUN_LENDER_STATES = LENDER_DEBIT_STATES - {"alternative_position", "factoring"}


def payer_text_unread_texts(transactions: Sequence) -> dict[int, str]:
    """The unread payer text (Transaction.unread_payer_text) of each credit the parser marked as read only by its
    label, by ledger index."""
    return {
        index: text for index, transaction in enumerate(transactions)
        if getattr(transaction, "payer_text_unread", False) and transaction.amount > 0
        and (text := getattr(transaction, "unread_payer_text", "") or "")
    }


def unread_run_blocks(text: str) -> list[str]:
    """An unread run of welded payer blocks, normalized and split after each ACH class code (_UNREAD_BLOCK_END);
    words after the last code are one more block."""
    normalized = normalize_transaction_description(text)
    blocks: list[str] = []
    start = 0
    for found in _UNREAD_BLOCK_END.finditer(normalized):
        blocks.append(normalized[start:found.end()].strip())
        start = found.end()
    blocks.append(normalized[start:].strip())
    return [block for block in blocks if block]


def unread_run_names_financing(text: str) -> bool:
    """One block of an unread run (unread_run_blocks) names a registry lender of _UNREAD_RUN_LENDER_STATES
    (match_known_payee, read as a credit) or a lending bank (_LENDING_BANK_PAYER). The bare financing root is never
    read: a customer named CAPITAL is no lender."""
    for block in unread_run_blocks(text):
        known = match_known_payee(block, credit=True)
        if known is not None and known.state in _UNREAD_RUN_LENDER_STATES:
            return True
        if _LENDING_BANK_PAYER.search(block):
            return True
    return False


def payer_text_unread(
    transactions: Sequence, records: Sequence[TransactionClassification],
) -> tuple[bool, int]:
    """(the statement's payer text is mostly unread, the count of its unread posted credits): more than
    PAYER_TEXT_UNREAD_SHARE of its posted credit rows (duplicates aside) carry the parser's mark. Published as
    metrics.payer_text_unread and metrics.payer_text_unread_count."""
    unread = payer_text_unread_indexes(transactions)
    posted = [
        index for index, record in enumerate(records)
        if record.amount > 0 and record.is_posted and record.duplicate_of is None
    ]
    count = sum(1 for index in posted if index in unread)
    return (bool(posted) and count / len(posted) > PAYER_TEXT_UNREAD_SHARE), count


def holder_unscreened(
    records: Sequence[TransactionClassification], *, holder_name: str | None = None, account_name: str | None = None,
) -> bool:
    """§8.1: no holder's name is known for the statement, so no holder test can see the holder's own money: the
    holder's name (_holder) names nobody (_usable_holder_name) and the statement's receiver fields name no holder
    (_receiver_holder_names). Published as metrics.holder_unscreened. The names are the statement's (its first
    record's, or `holder_name` and `account_name` for a statement with no transaction); a holder's name the parser read
    is known whenever the holder test reads a word of it (classifier.holder_words, which the holder hold reads with no
    usability test), whatever its shape, and an account-name field is known when it names a holder (_usable_holder_name
    on holder_reading's name)."""
    if records:
        holder_name, account_name = records[0].holder_name, records[0].account_name
    if holder_name and holder_name.strip() and holder_words(holder_name):
        return False
    if _usable_holder_name(holder_reading(account_name, holder_name)):
        return False
    credits = [index for index, record in enumerate(records) if record.amount > 0 and record.is_posted]
    return not _receiver_holder_names(records, credits)


def _held_by_the_floor(record: TransactionClassification) -> TransactionClassification:
    """§7.0, §7.8, §8.10: a tiered credit under the $1 floor that a rule verified or counted, held for review with
    the floor's reason (_MICRO_DEPOSIT_REASON). A verified one leaves verification as a new first state
    (unverified_deposit, method micro_deposit_floor, pending review, so the analyst may confirm it); its reason names
    the rule the floor overruled, for the audit."""
    if record.revenue_classification == "verified_revenue":
        record = _replace_revenue_state(
            record,
            "unverified_deposit",
            match_method="micro_deposit_floor",
            matched_rule="credit_under_micro_deposit_floor",
            confidence_score=0.40,
            reason=(
                "A credit under $1 is never verified and never counted (the absolute micro-deposit floor): the rule "
                f"that read it ({record.revenue_match_method}) is overruled, and it is held for review."
            ),
            context_signals=(*record.revenue_context_signals, "micro_deposit_floor"),
            related_transaction=record.revenue_related_transaction,
        )
    return _with_tier(record, "excluded_pending_review", _MICRO_DEPOSIT_REASON)


def _tier_reason(
    record: TransactionClassification, text: str, facts: CreditFacts, round_repeat: bool, deferred: bool = False,
    unread: bool = False, unread_text: str = "",
) -> tuple[str, str]:
    """§8.10: the tier and reason of an unverified posted credit, in order. A deferred source (§15, `deferred`) on a
    wire or an ACH or EFT row is a named payer Q5 and Q6 refuse as proof, as a verification-only word refuses one:
    named_payer_purpose_refused, never "One-off payer" (a deferred source often repeats). On a row with no
    electronic-payment form it keeps named_payer_unlabelled: Q6 never reads such a row, deferred or not. A row the
    parser marked as read only by its label (`unread`) that would be counted as Q2's no_payer_printed at the bare-row
    fall-through is counted as payer_text_not_read instead: the statement printed a payer the parser did not read.
    Every hold before it still applies (a bare transfer label stays transfer_no_counterparty). B10 review (round 1):
    a cash, branch, teller or ATM row (the cash_branch_atm channel) keeps no_payer_printed, marked or not: its own
    label says the statement printed no payer (Q2). Such a marked row whose unread run of payer blocks
    (`unread_text`, Transaction.unread_payer_text) prints a lender's or a lending bank's block
    (unread_run_names_financing) is held as unread_run_names_financing instead: one row of the run is that lender's
    money and the text cannot say which (Q6: lenders never count). It is never a lender credit and names no payer.

    §8.10: last, after the unread branch, a credit the financing-root release lifted (CreditFacts.q9) that the tiers
    count takes the release's reason, unless its counted reason is one a released row keeps (_Q9_KEEPS:
    payer_text_not_read, the platform, payout, numbered-company and factoring readings, and the owner batches'
    specific counted reasons). A held reason is never overridden."""
    tier, reason = _tier_reason_read(record, text, facts, round_repeat, deferred)
    if unread and reason == "no_payer_printed" and facts.channel != "cash_branch_atm":
        if unread_text and unread_run_names_financing(unread_text):
            return "excluded_pending_review", UNREAD_RUN_NAMES_FINANCING
        reason = PAYER_TEXT_NOT_READ
    if facts.q9 is not None and tier == "counted_flagged" and reason not in _Q9_KEEPS:
        reason = facts.q9
    return tier, reason


def _tier_reason_read(
    record: TransactionClassification, text: str, facts: CreditFacts, round_repeat: bool, deferred: bool,
) -> tuple[str, str]:
    """§8.10's order (_tier_reason), on the row's text alone."""
    if record.revenue_match_method == "direction_conflict":
        return "excluded_pending_review", "direction_conflict"
    if facts.hold is not None:
        return "excluded_pending_review", facts.hold
    # §6.3: a named sender after an own-account designation left the strong non-revenue rule only to be held (T13),
    # on any channel and whoever the sender is: it never enters True.
    if _named_sender_after_designation(text, _holder(record)):
        return "excluded_pending_review", "transfer_account_designation"
    # §8.10: an insurer paying the business for its work, which the release before the facts re-stated
    # (_insurer_for_work); every hold before it still wins. On a person-to-person row §8.4's round-sum repeat still
    # wins, as for the progress draw: the released row falls through to the person-to-person arm below, held
    # p2p_round_repeat, its method still the release's.
    if record.revenue_match_method == INSURER_FOR_WORK_METHOD and not (
        facts.channel == "person_to_person" and round_repeat
    ):
        return "counted_flagged", INSURER_FOR_WORK_METHOD
    # §6.3: a processor's instant payout printed as a card credit, released beside the processor's own ACH
    # activity: a platform payout no form confirms.
    if record.revenue_match_method == PROCESSOR_CARD_PAYOUT_METHOD:
        return "counted_flagged", "platform_unconfirmed"
    # A3-H: a factoring payer's payout, on any channel (FACTORING_PAYOUT_PAYERS).
    if facts.factor:
        return "counted_flagged", "factoring_payout"
    # A lease-to-own or patient financier's merchant payout (CUSTOMER_FINANCING_PAYERS), on a wire, an ACH or EFT row
    # or an unlabelled one; a one-off lump sum is held after the tiers.
    if facts.financier:
        return "counted_flagged", CUSTOMER_FINANCING_PAYOUT
    # A builder's progress draw, on any channel but Zelle (Q3's); a bare transfer's and an account designation's holds
    # and Q4's round-sum repeat still win (any hold wins above).
    if (
        facts.progress_draw and not facts.transfer_no_counterparty and not facts.account_designation
        and not (facts.channel == "person_to_person" and round_repeat)
    ):
        return "counted_flagged", CONSTRUCTION_PROGRESS_DRAW_REASON
    if facts.channel == "wire" and not facts.claimed:
        if not facts.region:
            return "excluded_pending_review", "wire_no_sender"
        if facts.refused_word or deferred:
            return "counted_flagged", "named_payer_purpose_refused"
        return "counted_flagged", "wire_named_sender"
    if facts.transfer_no_counterparty and not facts.claimed:
        return "excluded_pending_review", "transfer_no_counterparty"
    if facts.account_designation and not facts.claimed:
        return "excluded_pending_review", "transfer_account_designation"
    if facts.channel == "check":
        return "counted_flagged", "check_deposit"
    if facts.channel == "cash_branch_atm":
        return "counted_flagged", "no_payer_printed"
    if facts.channel == "person_to_person" and not facts.claimed:
        return ("excluded_pending_review", "p2p_round_repeat") if round_repeat else ("counted_flagged", "p2p")
    if record.revenue_match_method in _REGISTRY_METHODS:
        return "counted_flagged", "platform_unconfirmed"
    if record.classification == "factoring":
        return "counted_flagged", "factoring_payout"
    if _payout_entity(text) is not None:
        return "counted_flagged", "payout_credit_entity"
    if facts.numbered:
        return "counted_flagged", "numbered_company_payer"
    if facts.region and (facts.refused_word or (deferred and facts.electronic)):
        return "counted_flagged", "named_payer_purpose_refused"
    # A payer region that names only a bank names no customer (Q2): counted as no_payer_printed, never as a
    # named payer.
    if facts.region and facts.bank_only:
        return "counted_flagged", "no_payer_printed"
    if facts.region and facts.electronic:
        return "counted_flagged", "named_payer_one_off"
    if facts.region and not _is_bare_row(text):
        return "counted_flagged", "named_payer_unlabelled"
    return "counted_flagged", "no_payer_printed"


#: §5.3: the words a counted re-statement's reason sentence says it is counted with (the insurer-for-work release, the
#: factoring, financier, payables, progress-draw and settlement demotions, the processor card payout), which a hold
#: that re-tiers the row replaces (_held_reason).
_COUNTED_SENTENCE = "counted and flagged, never verified"


def _with_tier(record: TransactionClassification, tier: str, reason: str | None) -> TransactionClassification:
    """A record with its 5.6 tier, initial tier, reason and contribution flags. The review flag is set for a held row
    only; a counted row is reviewable, not required. §5.3: a held row's reason sentence never says it is counted
    (_held_reason); every other field, and a counted row's sentence, is as before."""
    return replace(
        record,
        revenue_tier=tier,
        revenue_initial_tier=tier,
        revenue_tier_reason=reason,
        revenue_review_required=tier == "excluded_pending_review",
        revenue_reason=_held_reason(record.revenue_reason, reason) if tier == "excluded_pending_review" else (
            record.revenue_reason),
        **revenue_contribution_flags(record.revenue_classification, tier),
    )


def _held_reason(sentence: str | None, reason: str | None) -> str | None:
    """§5.3: the reason sentence of a row a hold re-tiers (`reason`, the held reason code): where an earlier counted
    re-statement wrote "counted and flagged, never verified" (_COUNTED_SENTENCE), that phrase becomes "never verified,
    and held for review (<label>)", the label the held reason's own (REVENUE_TIER_REASONS; the code itself when the
    table lists none). The wording follows _zelle_excluded, which names the rules' reading inside its own sentence. It
    covers every hold of the owner batches: the Q2 release a later hold names, Q8's lump sum, Q9 (c')'s hidden-loan
    guard, Q10's premium-trust hold and the $1 floor on a counted or demoted unverified row (a Verified row the floor
    or the premium-trust hold re-states gets its own sentence first). Any other sentence is returned unchanged."""
    if not sentence or _COUNTED_SENTENCE not in sentence:
        return sentence
    label = REVENUE_TIER_REASONS.get(reason or "", (None, reason or "excluded_pending_review"))[1]
    return sentence.replace(_COUNTED_SENTENCE, f"never verified, and held for review ({label})")


def _verify(record: TransactionClassification, method: str, reason: str, confidence: float) -> TransactionClassification:
    return _replace_revenue_state(
        record,
        "verified_revenue",
        match_method=method,
        matched_rule=f"verified_{method}",
        confidence_score=confidence,
        reason=reason,
        context_signals=(*record.revenue_context_signals, method),
    )
