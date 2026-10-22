from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from analysis.payee_matcher import match_memo
from analysis.descriptor.financing import _names_financing
from analysis.descriptor.lexical import revenue_text
from analysis.descriptor.payer import payer_region
from analysis.classification.record import (
    TransactionClassification,
    UNIDENTIFIED_LENDER_OBLIGATION,
    _promotion_cadence,
    _replace_revenue_state,
)
from analysis.classification.payees import _unknown_entity_for_text
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
from analysis.true_revenue.counter_debit_pairing import also_debited, counter_credit, counter_debits, debited_as_lender
from analysis.true_revenue.tiers import payer_text_unread_indexes, payer_text_unread_texts
from analysis.true_revenue.trust import premium_trust_title
from analysis.true_revenue.zelle import zelle_credits_present
from analysis.transaction_classifier.row import classify_transaction
from analysis.true_revenue.pass7 import apply_true_revenue_pass

if TYPE_CHECKING:
    from analysis.schema import Statement


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
