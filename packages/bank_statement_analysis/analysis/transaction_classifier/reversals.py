"""Reversal pairs (pass 4) and deposit returns."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Callable, Sequence

from analysis.classification.credit_predicates import _remboursement_from_a_provider
from analysis.classification.record import TransactionClassification, _replace_revenue_state
from analysis.dates import parse_date
from analysis.descriptor.credit_words import (
    _REMBOURSEMENT_WORD,
    _RETURN_CODE_CREDIT_PATTERNS,
    _RETURN_REFUND_CREDIT_PATTERNS,
)
from analysis.descriptor.lexical import _before_receiver, revenue_text
from analysis.descriptor.payer import _is_bare_row
from analysis.descriptor.rails import _is_wire_row, _matches_any
from analysis.descriptor.words import (
    _CASH_BRANCH_ATM_FORM,
    _CHECK_DEPOSIT_FORM,
    _CONSUMER_P2P_RAIL,
    _DEPOSIT_UNDO_FEE,
    _ELECTRONIC_PAYMENT_FORM,
    _FRENCH_CANCEL_CREDIT_PATTERN,
    _PUSH_RAIL,
    _RETAIL_CASH_LOAD,
    _REVERSAL_CANCELLATION_CREDIT_PATTERNS,
    _SETTLEMENT_REVERSAL_PATTERNS,
    _WIRE_WORD,
)
from analysis.transaction_classifier.funder_returns import (
    _is_paid_funder_debit,
    _returned_payoff_in_rate,
    _returned_unpaid_reason,
    _returns_a_later_lender_payment,
)


_PAIR_FAMILY_PATTERNS = (
    re.compile(r"\bE TRANSFER\b"),
    re.compile(r"\bETRANSFER\b"),
    re.compile(r"\bCHECK\b"),
    re.compile(r"\bCHEQUE\b"),
    re.compile(r"\bACH\b"),
    re.compile(r"\bWIRE\b"),
)


_REVENUE_PAIR_NOISE = {
    "CANCEL", "CANCELED", "CANCELLED", "CANCELLATION", "CNCL",
    "RETURN", "RETURNED", "REVERSAL", "REVERSED", "REVERSE",
    "REFUND", "REFUNDED", "CREDIT", "DEBIT", "SENT", "RECEIVED",
    "PAYMENT", "PAY", "PMT", "PYMT", "ITEM", "PROVISIONAL", "TEMPORARY",
    "CONDITIONAL", "ACH", "PULL", "CARD", "PURCHASE", "CHECK", "CHEQUE",
    "WIRE", "TRANSFER", "DEPOSIT", "WITHDRAWAL",
}


def _revenue_pair_tokens(text: str) -> set[str]:
    return {
        token
        for token in text.split()
        if token not in _REVENUE_PAIR_NOISE and len(token) > 1
    }


def _descriptions_share_pair_context(left: str, right: str) -> bool:
    if _revenue_pair_tokens(left) & _revenue_pair_tokens(right):
        return True
    return any(pattern.search(left) and pattern.search(right) for pattern in _PAIR_FAMILY_PATTERNS)


#: §6.2, §20: the undo wordings of a deposit, read as pass 4's revenue-side markers on either row: a returned deposited
#: item (PNC's RET DEP ITEM, RETURNED DEPOSIT ITEM, Wells Fargo's DEPOSITED ITEM RETN and Chase's DEPOSITED ITEM
#: RETURNED), an error, transaction or deposit correction, a mobile, remote or ATM deposit adjustment, and Bank of
#: America's ADJUSTMENT CORRECTION. And a credit union's deposit correction cut short or with its type between the words
#: (DEPOSIT TYPE CORRECT, DEPOSIT CORRECT).
_DEPOSIT_CORRECTION_MARKERS = (
    re.compile(r"\b(?:ERROR|TRANSACTION|DEPOSIT) CORRECTION\b"),
    re.compile(r"\b(?:MOBILE|REMOTE|ATM) DEPOSIT ADJUSTMENT\b"),
    re.compile(r"\bADJUSTMENT CORRECTION\b"),
    re.compile(r"\bDEPOSIT (?:TYPE )?CORRECT(?:ION)?\b"),
)
_DEPOSIT_UNDO_MARKERS = (
    re.compile(r"\bRET(?:URN(?:ED)?)? DEP(?:OSIT(?:ED)?)? ITEMS?\b"),
    re.compile(r"\bDEPOSITED ITEMS? RET\w*"),
    *_DEPOSIT_CORRECTION_MARKERS,
)
#: The debits that undo a deposit, which pair with the deposit itself (_deposit_return_pairs): the undo markers, a
#: deposited check returned, a bare RETURNED ITEM (and Bank of America's RETURN ITEM CHARGEBACK), RBC's ITEM RETURNED
#: UNPAID and a returned check; never the bank's fee for the return (_DEPOSIT_UNDO_FEE). TD's RTN NSF is not one. And
#: TD Bank's returned deposited item, DEP RETURN CHARGEBACK (its DEP RETURN FEE prints beside it), and a bank's
#: row-leading two-word CHARGE BACK of a deposited item, with ITEM or a return reason after it (CHARGE BACK ITEM CHECK
#: <n>, CHARGE BACK - SIGNATURE(S) IRREGULAR, ... NSF, INSUFFICIENT, UNCOLLECTED, ACCOUNT CLOSED, STOP PAY, REFER TO
#: MAKER); read on debits only, never a bare CHARGEBACK, a processor's or a merchant's chargeback,
#: the bank's fee, a bare DEP RETURN or RTN NSF.
_DEPOSIT_RETURN_DEBIT_PATTERNS = (
    *_DEPOSIT_UNDO_MARKERS,
    re.compile(r"\bDEPOSITED (?:CHECK|CHEQUE)S? RET\w*"),
    re.compile(r"\bRETURN(?:ED)? ITEMS?\b"),
    re.compile(r"(?<![A-Z])ITEMS? RET(?:URNED)?\b"),
    re.compile(r"\bRETURNED (?:CHECK|CHEQUE)S?\b|\b(?:CHECK|CHEQUE)S? RETURNED\b"),
    re.compile(r"\bDEP(?:OSIT)? RETURN CHARGE ?BACK\b"),
    re.compile(
        r"^(?:\d{1,2} \d{1,2} )?CHARGE ?BACK (?:ITEMS?\b|SIGNATURE|ENDORSE|NSF\b|INSUFFICIENT|UNCOLLECTED"
        r"|ACC(?:OUN)?T CLOSED|STOP PAY|REFER TO MAKER)"
    ),
)
#: A paid check printed first with its number (the holder's own check, whatever its memo says).
_PAID_CHECK_FIRST = re.compile(r"^(?:\d{1,2} \d{1,2} )?(?:CHECK|CHEQUE|CHK|CHQ) ?#? ?\d")
#: A returned deposit pairs with a deposit up to this many days before it, the same day included.
_DEPOSIT_RETURN_DAYS = 14
#: A mobile or electronic deposit capture glued to its word (MDEPOSIT, EDEPOSIT IN BRANCH), a deposit word, and the card
#: words a bare deposit never prints (a card settlement's VISA DEPOSIT is no deposit channel).
_DEPOSIT_CAPTURE_WORD = re.compile(r"(?<![A-Z])(?:MDEPOSIT|EDEPOSIT)\b")
_DEPOSIT_WORD = re.compile(r"(?<![A-Z])(?:DEP|DEPOSITS?)\b")
_CARD_WORD = re.compile(r"(?<![A-Z])(?:CARDS?|VISA|MC|MASTERCARD|AMEX|DISCOVER|BANKCARD|POS)\b")


def _deposit_return_debit(text: str) -> bool:
    """A debit that undoes a deposit (_DEPOSIT_RETURN_DEBIT_PATTERNS), never the bank's fee for it.

    And only the bank's own return, never the holder's payment that prints a 'return item' memo: a person-to-person
    or push rail, WIRE, an electronic payment's mark (which names its payee) or a paid check printed first with its
    number refuses it. A credit union's returned check prints the check's number and its maker after RETURNED CHECK;
    that stays a return."""
    if not _matches_any(text, _DEPOSIT_RETURN_DEBIT_PATTERNS) or _DEPOSIT_UNDO_FEE.search(text) is not None:
        return False
    return not (
        _CONSUMER_P2P_RAIL.search(text) or _PUSH_RAIL.search(text) or _WIRE_WORD.search(text)
        or _ELECTRONIC_PAYMENT_FORM.search(text) or _PAID_CHECK_FIRST.search(text)
    )


#: True revenue spec §6.2's package passes, §9.1: a processor's chargeback of a card sale, and a processor's merchant,
#: financial or bankcard adjustment, read on a debit's text (processor_chargeback_debit); never the bank's or the
#: processor's fee for one (_PROCESSOR_CHARGEBACK_FEE: the chargeback words are spared, so CHG BACK and CHARGE BACK stay
#: chargebacks).
_PROCESSOR_CHARGEBACK_WORD = re.compile(r"(?<![A-Z])(?:CHARGE ?BACKS?|CHBK|CHGBK|CHG BACK)(?![A-Z])")
_PROCESSOR_ADJUSTMENT_WORD = re.compile(r"(?<![A-Z])(?:MERCH(?:ANT)? ADJ\w*|FINCL ADJ|BANKCD ADJ)(?![A-Z])")
_PROCESSOR_CHARGEBACK_FEE = re.compile(
    r"(?<![A-Z])(?:FEES?|FRAIS|SVC CHG|SERVICE CHARGE|CHRG|CHG(?! ?BACK)|CHARGES?(?! ?BACK))(?![A-Z])"
)


def processor_chargeback_debit(text: str) -> str | None:
    """The wording of a debit that is a processor's chargeback or adjustment, 'chargeback' or 'adjustment', else None.
    A flag's reader only: no classification, tier, figure or lender reading reads it (analysis/revenue_view.py
    debit_side_flags flags the row on the statement and the package, never deducted).

    The fee wording (_PROCESSOR_CHARGEBACK_FEE) refuses it (the bank's chargeback fee, CHBK CHRG), and a returned
    deposited item reads first (_deposit_return_debit: the DEP RETURN CHARGEBACK and a bank's row-leading CHARGE
    BACK of a deposited item are returns, never processor chargebacks). The caller reads the row's posting, duplicate
    mark, lender contributions and class."""
    if _PROCESSOR_CHARGEBACK_FEE.search(text) is not None or _deposit_return_debit(text):
        return None
    if _PROCESSOR_CHARGEBACK_WORD.search(text) is not None:
        return "chargeback"
    if _PROCESSOR_ADJUSTMENT_WORD.search(text) is not None:
        return "adjustment"
    return None


#: True revenue spec §6.2's package passes, §8.2: a cash device's word on a cash, branch, teller or ATM deposit
#: (_CASH_BRANCH_ATM_FORM): an ATM or ABM, cash or coin, a smart safe or a currency-processing device, a night deposit
#: or drop, a vault or a pre-encoded bag. A teller's, counter's or branch's deposit prints none of them.
_CASH_DEVICE_WORD = re.compile(
    r"(?<![A-Z])(?:ATM|ABM|CASH|COIN|SMART ?SAFE|CPS DEVICE|CURRENCY PROCESSING|NIGHT (?:DEP\w*|DROP)|VAULT"
    r"|PRE ?ENCODED)(?![A-Z])"
)
#: Arm R (a retail cash load, _RETAIL_CASH_LOAD) on its own: a retail network's cash load is cash.
_RETAIL_CASH_LOAD_FORM = re.compile(_RETAIL_CASH_LOAD)


def paper_or_cash_deposit(text: str) -> bool:
    """Whether a credit is a paper or cash deposit, which is never the receiving leg of an electronic transfer between
    two of the business's accounts. Read on the row before its receiver fields (`_before_receiver` of `revenue_text`):
    a check deposit (§8.3's _CHECK_DEPOSIT_FORM), a cash, branch, teller or ATM deposit (§8.2's _CASH_BRANCH_ATM_FORM)
    that prints a cash device's word (_CASH_DEVICE_WORD), or a retail cash load (arm R). A teller's, counter's
    or branch's deposit that prints no such word stays eligible: a branch transfer between two of the business's
    accounts can print that way on its receiving side. A package pass's reader only
    (analysis/package/passes.py `package_matches`, pass 2): no classification, tier, figure or lender reading reads
    it."""
    row = _before_receiver(revenue_text(text))
    if _CHECK_DEPOSIT_FORM.search(row) is not None:
        return True
    if _CASH_BRANCH_ATM_FORM.search(row) is not None and _CASH_DEVICE_WORD.search(row) is not None:
        return True
    return _RETAIL_CASH_LOAD_FORM.search(row) is not None


def _deposit_channel_credit(text: str) -> bool:
    """A credit a returned item may undo: a check deposit (§8.3), a cash, branch, teller or ATM deposit (§8.2), a
    deposit capture glued to its word (_DEPOSIT_CAPTURE_WORD), or a bare deposit that names no payer (§8.2's bare row
    printing a deposit word and no card word); never a wire, a person-to-person or push rail, or an electronic payment
    (a returned item names no payer, so it never undoes a named payer's payment)."""
    text = revenue_text(text)
    row = _before_receiver(text)
    if _is_wire_row(text) or _CONSUMER_P2P_RAIL.search(row) or _PUSH_RAIL.search(row):
        return False
    if _CHECK_DEPOSIT_FORM.search(row) or _DEPOSIT_CAPTURE_WORD.search(row):
        return True
    if _ELECTRONIC_PAYMENT_FORM.search(row):
        return False
    if _CASH_BRANCH_ATM_FORM.search(row):
        return True
    return _DEPOSIT_WORD.search(row) is not None and _CARD_WORD.search(row) is None and _is_bare_row(text)


def _deposit_return_pairs(
    records: list[TransactionClassification], duplicate_indexes: set[int],
) -> list[tuple[int, int]]:
    """§6.2: the (credit index, debit index) pairs of a debit that undoes a deposit (_deposit_return_debit) and an equal
    posted deposit-channel credit (_deposit_channel_credit) 0 to _DEPOSIT_RETURN_DAYS days before it. No shared word is
    needed: a returned item never prints the depositor's words. Each such debit, in row order, takes the earliest such
    credit not yet taken (then the first row), so a redeposit after the return, or beside a corrected deposit, stays
    counted.

    An undated credit or debit reads the row order (the deposit printed before the return), and an undo debit that
    names an equal credit's payer (_undo_debit_names_a_credit) is left to the shared-word pairing."""
    pairs: list[tuple[int, int]] = []
    taken: set[int] = set()
    for debit_index, debit in enumerate(records):
        if (
            debit_index in duplicate_indexes
            or debit.amount >= 0
            or not debit.is_posted
            or not _deposit_return_debit(debit.normalized_description)
            or _undo_debit_names_a_credit(records, duplicate_indexes, debit_index)
        ):
            continue
        amount = round(abs(debit.amount), 2)
        debit_date = parse_date(debit.date)
        best: tuple[tuple[date, int], int] | None = None
        for credit_index, credit in enumerate(records):
            if (
                credit_index in duplicate_indexes
                or credit_index in taken
                or credit.amount <= 0
                or not credit.is_posted
                or round(credit.amount, 2) != amount
            ):
                continue
            credit_date = parse_date(credit.date)
            if credit_date is None or debit_date is None:
                if credit_index >= debit_index:
                    continue
            elif not 0 <= (debit_date - credit_date).days <= _DEPOSIT_RETURN_DAYS:
                continue
            if not _deposit_channel_credit(credit.normalized_description):
                continue
            key = (credit_date or debit_date or date.min, credit_index)
            if best is None or key < best[0]:
                best = (key, credit_index)
        if best is not None:
            taken.add(best[1])
            pairs.append((best[1], debit_index))
    return pairs


def _undo_debit_names_a_credit(
    records: list[TransactionClassification], duplicate_indexes: set[int], debit_index: int,
) -> bool:
    """§6.2: a correction debit (_DEPOSIT_CORRECTION_MARKERS, one of pass 4's revenue-side markers) that shares a word
    or a family with an equal posted credit, 14 days either side, that is no deposit-channel credit. Such a correction
    undoes that credit ('ERROR CORRECTION CONTOSO SUPPLY LLC' undoes Contoso's payment), so the deposit mode never
    seizes it for an equal deposit; pass 4's shared-word pairing takes it. A returned item is never one: the name it
    prints is the returned check's maker, so it undoes the deposited check, never the maker's equal electronic
    payment. A deposit-channel credit sharing the correction's words is left to the deposit mode, which reads only
    deposits printed before the undo."""
    debit = records[debit_index]
    debit_text = debit.normalized_description
    if not _matches_any(debit_text, _DEPOSIT_CORRECTION_MARKERS):
        return False
    amount = round(abs(debit.amount), 2)
    debit_date = parse_date(debit.date)
    for credit_index, credit in enumerate(records):
        if (
            credit_index in duplicate_indexes
            or credit.amount <= 0
            or not credit.is_posted
            or round(credit.amount, 2) != amount
        ):
            continue
        credit_date = parse_date(credit.date)
        if credit_date is not None and debit_date is not None and abs((credit_date - debit_date).days) > 14:
            continue
        text = credit.normalized_description
        if not _deposit_channel_credit(text) and _descriptions_share_pair_context(text, debit_text):
            return True
    return False


def _credit_pair_marker(text: str, credit_markers: Sequence[re.Pattern[str]]) -> bool:
    """A credit-row-only pass-4 marker (`credit_markers`: step 3's 5.6 credit markers on the revenue side, none
    on the lender side). §7.11: with step 3's carve-out, so a provider's REMBOURSEMENT
    (_remboursement_from_a_provider), which leaves step 3, marks no pair either."""
    return any(
        pattern.search(text) is not None
        and not (pattern is _REMBOURSEMENT_WORD and _remboursement_from_a_provider(text))
        for pattern in credit_markers
    )


#: §6.2: the reversal pair reads the credit markers of step 3, return codes included. §20: on the revenue side, the
#: deposit undo markers too, read on either row.
_PAIR_MARKER_PATTERNS = (*_REVERSAL_CANCELLATION_CREDIT_PATTERNS, *_RETURN_CODE_CREDIT_PATTERNS, *_DEPOSIT_UNDO_MARKERS)
#: §20: the revenue side also reads step 3's 5.6 credit markers, on the credit row only: on a debit several of them are
#: a purchase (CHECKCARD <mmdd>), a repayment (REMBOURSEMENT) or a charge. With step 3's REMBOURSEMENT carve-out
#: (_credit_pair_marker).
_CREDIT_PAIR_MARKER_PATTERNS = _RETURN_REFUND_CREDIT_PATTERNS
#: §20: the lender side keeps classification 5.4's pairs. A pair the 5.4 credit markers make (step 3's markers
#: without the return codes and the French cancel words) alone zeroes the debit's lender, potential-lender,
#: withholding, insurance and flag contributions (setting its reversed_by) and sets the credit's
#: settlement-reversal fields and flag contribution; the widened markers change the credit's revenue reading only.
_LENDER_PAIR_MARKER_PATTERNS = tuple(
    pattern for pattern in _REVERSAL_CANCELLATION_CREDIT_PATTERNS if pattern is not _FRENCH_CANCEL_CREDIT_PATTERN
)


def _reversal_pairs(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
    markers: Sequence[re.Pattern[str]],
    marked: dict[int, bool] | None = None,
    *,
    credit_markers: Sequence[re.Pattern[str]] = (),
    seeded: Sequence[tuple[int, int]] = (),
    refuse: Callable[[int, int], bool] | None = None,
) -> list[tuple[int, int]]:
    """§6.2 pass 4: the (credit index, debit index) pairs, in credit order: an equal posted debit within 14 days that
    shares the credit's transaction family, where the credit or the debit prints one of `markers`; the nearest date,
    then the nearest row, wins, and a debit pairs once. `marked` caches each row's marker reading.

    `credit_markers` are read on a credit row only (step 3's 5.6 credit markers, with its REMBOURSEMENT carve-out:
    _credit_pair_marker), and the `seeded` pairs (the returned deposits, _deposit_return_pairs) are made first: their
    credits and debits pair no further.

    Lender side only: a (credit, debit) candidate `refuse` names is no candidate (_returns_a_later_lender_payment: a
    confirmed funder's paid payment or a potential lender's counted payment, dated after the return)."""
    marked = {} if marked is None else marked

    def has_marker(index: int) -> bool:
        if index not in marked:
            text = records[index].normalized_description
            marked[index] = _matches_any(text, markers) or (
                records[index].amount > 0 and _credit_pair_marker(text, credit_markers)
            )
        return marked[index]

    pairs: list[tuple[int, int]] = list(seeded)
    matched_debit_indexes: set[int] = {debit_index for _, debit_index in seeded}
    seeded_credits = {credit_index for credit_index, _ in seeded}
    # The posted, non-duplicate debits by their rounded amount, in row order, built once, so a credit visits only its
    # equal debits and in the order the scan of every row visited them: the pairs, the marker cache and the refuse
    # calls are the same. A NaN debit is listed nowhere, and the scan never paired one.
    debits_by_amount: dict[float, list[int]] = {}
    for debit_index, debit in enumerate(records):
        if debit_index not in duplicate_indexes and debit.amount < 0 and debit.is_posted:
            debits_by_amount.setdefault(round(abs(debit.amount), 2), []).append(debit_index)
    for credit_index, credit in enumerate(records):
        if (
            credit_index in duplicate_indexes
            or credit_index in seeded_credits
            or credit.amount <= 0
            or not credit.is_posted
        ):
            continue
        credit_has_marker = has_marker(credit_index)
        candidates: list[tuple[int, int]] = []
        credit_date = parse_date(credit.date)
        for debit_index in debits_by_amount.get(round(credit.amount, 2), ()):
            # Checked here, not when the list is built: the debits a credit takes change as the loop goes.
            if debit_index in matched_debit_indexes:
                continue
            debit = records[debit_index]
            if not credit_has_marker and not has_marker(debit_index):
                continue
            if refuse is not None and refuse(credit_index, debit_index):
                continue
            debit_date = parse_date(debit.date)
            day_gap = (
                abs((credit_date - debit_date).days)
                if credit_date is not None and debit_date is not None
                else 0
            )
            if day_gap > 14 or not _descriptions_share_pair_context(
                credit.normalized_description,
                debit.normalized_description,
            ):
                continue
            candidates.append((day_gap, debit_index))
        if not candidates:
            continue
        _, debit_index = min(
            candidates,
            key=lambda item: (item[0], abs(item[1] - credit_index), item[1]),
        )
        matched_debit_indexes.add(debit_index)
        pairs.append((credit_index, debit_index))
    return sorted(pairs)


def _apply_reversal_pair_context(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    updated = list(records)
    revenue_marked: dict[int, bool] = {}
    # The revenue side pairs each returned deposit with its deposit first.
    deposit_pairs = _deposit_return_pairs(records, duplicate_indexes)
    revenue_pairs = _reversal_pairs(
        records, duplicate_indexes, _PAIR_MARKER_PATTERNS, revenue_marked,
        credit_markers=_CREDIT_PAIR_MARKER_PATTERNS, seeded=deposit_pairs,
    )
    # The lender side's pairs are 5.4's. A statement where no row prints a widened-only marker, and where no returned
    # deposit paired, has the same pairs on both sides.
    widened = bool(deposit_pairs) or any(
        revenue_marked.get(index) and not _matches_any(records[index].normalized_description,
                                                        _LENDER_PAIR_MARKER_PATTERNS)
        for index in revenue_marked
    )

    def refuse(credit_index: int, debit_index: int) -> bool:
        return _returns_a_later_lender_payment(records, credit_index, debit_index)

    # The final review of round 2, F2(a): a confirmed funder's paid payment pairs on the lender side only with a return
    # dated on or after it; so does a potential lender's counted payment. Refusing a candidate only removes it, so a
    # statement where no revenue pair is such a candidate (and no widened marker reads) keeps the revenue side's pairs,
    # as before.
    lender_pairs = (
        _reversal_pairs(records, duplicate_indexes, _LENDER_PAIR_MARKER_PATTERNS, refuse=refuse)
        if widened or any(refuse(credit_index, debit_index) for credit_index, debit_index in revenue_pairs)
        else revenue_pairs
    )
    deposit_returns = set(deposit_pairs)
    for credit_index, debit_index in revenue_pairs:
        credit, debit = records[credit_index], records[debit_index]
        related_location = debit.source_location or f"transaction:{debit_index + 1}"
        returned_deposit = (credit_index, debit_index) in deposit_returns
        updated[credit_index] = _replace_revenue_state(
            credit,
            "non_revenue",
            match_method="matched_reversal_pair",
            matched_rule=(
                "returned_deposit_amount_date_match" if returned_deposit
                else "opposite_direction_amount_date_description_match"
            ),
            confidence_score=1.0,
            reason=(
                f"Deposit undone by the returned-item or correction row {related_location} (the same amount, 0 to "
                f"{_DEPOSIT_RETURN_DAYS} days later)." if returned_deposit else
                f"Credit matches reversal or cancellation row {related_location} by "
                "amount, date proximity, and transaction-family description."
            ),
            context_signals=(
                *credit.revenue_context_signals,
                "matched_opposite_direction_row",
                "returned_deposit" if returned_deposit else "amount_date_description_match",
            ),
            related_transaction=related_location,
        )
    for credit_index, debit_index in lender_pairs:
        credit, debit = records[credit_index], records[debit_index]
        related_location = debit.source_location or f"transaction:{debit_index + 1}"
        credit_location = credit.source_location or f"transaction:{credit_index + 1}"
        is_settlement_reversal = _matches_any(
            credit.normalized_description,
            _SETTLEMENT_REVERSAL_PATTERNS,
        ) or _matches_any(
            debit.normalized_description,
            _SETTLEMENT_REVERSAL_PATTERNS,
        )
        # A credit this pass pairs with a debit is money coming back, not a factor's
        # payout, so it leaves the flagged totals.
        updated[credit_index] = replace(
            updated[credit_index],
            reversal_of=related_location if is_settlement_reversal else None,
            settlement_reversal=is_settlement_reversal,
            contributes_to_flagged_totals=False,
        )
        if is_settlement_reversal and _is_paid_funder_debit(updated[debit_index]):
            # A confirmed funder's payment returned unpaid leaves paid to lenders and keeps its withholding and its
            # lender count; reversed_by is set as before.
            updated[debit_index] = replace(
                updated[debit_index],
                reversed_by=credit_location,
                contributes_to_potential_lender_count=False,
                contributes_to_lender_totals=False,
                contributes_to_potential_lender_totals=False,
                contributes_to_potential_withholding_exposure=False,
                contributes_to_insurance_totals=False,
                contributes_to_flagged_totals=False,
                returned_funder_payment_by=credit_location,
                reason=f"{updated[debit_index].reason} {_returned_unpaid_reason(credit_location)}",
                # A returned payoff attempt stays in the rate, as Q5 rules.
                **_returned_payoff_in_rate(updated[debit_index]),
            )
            updated[credit_index] = replace(updated[credit_index], returns_funder_payment=related_location)
        elif is_settlement_reversal:
            updated[debit_index] = replace(
                updated[debit_index],
                reversed_by=credit_location,
                contributes_to_lender_count=False,
                contributes_to_potential_lender_count=False,
                contributes_to_lender_totals=False,
                contributes_to_withholding_rate=False,
                contributes_to_potential_lender_totals=False,
                contributes_to_potential_withholding_exposure=False,
                contributes_to_insurance_totals=False,
                contributes_to_flagged_totals=False,
            )
    return updated
