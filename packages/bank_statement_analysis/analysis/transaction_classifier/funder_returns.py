"""Returned and re-presented funder payments (passes 7b, 7c)."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from analysis.classification.record import TransactionClassification
from analysis.dates import parse_date
from analysis.descriptor.credit_words import _NO_LEGAL_FORM_LATER
from analysis.descriptor.rails import _matches_any
from analysis.descriptor.words import _DEPOSIT_UNDO_FEE, _SETTLEMENT_REVERSAL_PATTERNS
from analysis.payee_matcher import match_known_payee


def _is_paid_funder_debit(record: TransactionClassification) -> bool:
    """A confirmed funder's posted payment counted as paid to lenders, the debit a returned funder payment takes out
    of the paid figure."""
    return (
        record.amount < 0
        and record.is_posted
        and record.classification == "confirmed_lender"
        and record.contributes_to_lender_totals
    )


def _returned_payoff_in_rate(record: TransactionClassification) -> dict:
    """The worded-payoff rule meets Q5: the rule takes a PAID
    payoff-worded debit out of the withholding numerator, keeping it in paid to lenders; a returned one is out of
    paid, and Q5 keeps every returned funder payment in the rate ("keep it in the withholding rate"), so a payoff
    attempt the bank returned rejoins the numerator and is no lump sum. {} for every other debit."""
    if record.lump_sum_payoff is None:
        return {}
    return {"contributes_to_withholding_rate": True, "lump_sum_payoff": None}


def _is_counted_potential_payment(record: TransactionClassification) -> bool:
    """A potential lender's posted payment counted in the potential totals (keyword, registry or D6 potential
    lenders alike: D6 and the recurrence promotion run before pass 4)."""
    return (
        record.amount < 0
        and record.is_posted
        and record.classification == "potential_lender"
        and record.contributes_to_potential_lender_totals
    )


def _returns_a_later_lender_payment(
    records: list[TransactionClassification], credit_index: int, debit_index: int,
) -> bool:
    """The final review of round 2, F2(a) (its ruling "same amount, after it, a return/NSF form"; true revenue spec §6.2
    pass 4): whether a lender-side pair of this credit and debit would take a lender's payment dated AFTER the return,
    which the return cannot reverse. The pair is a settlement reversal (the credit or the debit prints a reversal word,
    the restore's own test) and the debit is a confirmed funder's paid payment (_is_paid_funder_debit) or a potential
    lender's counted payment (_is_counted_potential_payment, whose zeroing is §17.1's default (1)), dated after the
    credit; where either row prints no date, printed after it (rule D's order, _return_gap). Such a candidate is
    refused, so the return pairs with a payment on or before it, or with none (rule D and the package's pass 4 may still
    read a confirmed funder's). Every other debit keeps classification 5.4's pair, either way."""
    credit, debit = records[credit_index], records[debit_index]
    if not (_is_paid_funder_debit(debit) or _is_counted_potential_payment(debit)):
        return False
    if not (_matches_any(credit.normalized_description, _SETTLEMENT_REVERSAL_PATTERNS)
            or _matches_any(debit.normalized_description, _SETTLEMENT_REVERSAL_PATTERNS)):
        return False
    credit_date, debit_date = parse_date(credit.date), parse_date(debit.date)
    if credit_date is None or debit_date is None:
        return debit_index > credit_index
    return debit_date > credit_date


def _returned_unpaid_reason(credit_location: str, *, re_debited: bool = False) -> str:
    """The sentence a returned funder payment's debit adds to its reason. The ruling is named without its date: the
    analysis layer keeps no year literal outside date parsing (tests/test_no_statement_hardcodes.py). Pass 7c rewrites
    it for a payment its funder re-debited, which is out of the withholding rate (`re_debited`)."""
    if re_debited:
        return (f"Returned unpaid by {credit_location}: out of paid to lenders (the owner's ruling on the "
                "underwriter's Q5).")
    return (
        f"Returned unpaid by {credit_location}: out of paid to lenders, kept in the withholding rate (the owner's "
        "ruling on the underwriter's Q5)."
    )


#: True revenue spec §6.2 pass 7b, §11: the forms a bank prints when it returns the business's own payment unpaid (a
#: bounce), read on a credit by the returned-funder-payment pass alone (rule D, _returned_funder_payment_pairs): never a
#: refund, a card return, a correction or a reversal word on its own, and never with the fee words of _DEPOSIT_UNDO_FEE.
#: Arms (2) to (6) read only where no legal-form word follows on the row (a return code inside a company's name is no
#: bounce: SAMPLE RTN TRUCKING LLC). The two French arms are arms (a) and (c) of
#: _RETURN_REFUND_R2_B08_ARMS (EFFET RETOURNE, EFFET or CHEQUE REFUSE SANS PROVISION), copied here and read on the lender
#: side only (a test keeps them equal); their revenue-side reading is unchanged. The copies follow the arms'
#: lost-accent hardening (CH QUE, RETOURN), so a bounce printed with a lost accent is read as one here too (0 corpus
#: rows).
_RETURNED_PAYMENT_CREDIT_PATTERNS = (
    re.compile(r"\bRETURN OF POSTED (?:CHECK|ITEM)\b"),
    re.compile(r"(?<![A-Z])(?:ITEM RET|RET ITEM|RET NOT PAID)\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])(?:RTN|RETN)\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])NSF\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])(?:UNPAID|NOT PAID)\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"(?<![A-Z])REJECT(?:ED)?\b" + _NO_LEGAL_FORM_LATER),
    re.compile(r"\bRETURN(?:ED)? (?:ITEM|ACH|PAYMENT|DEBIT|PAD|CHECK|CHEQUE|EFT|ENTRY|DR)S?\b"),
    re.compile(r"\b(?:ITEM|ACH|PAYMENT|DEBIT|PAD|EFT|CHECK|CHEQUE|ENTRY|DR)S? RETURN(?:ED)?\b"),
    re.compile(r"\bCREDIT RETURNED\b"),
    re.compile(r"(?<![A-Z])EFFETS? (?:RET|RETOUR|RETOURNEE?S?|RETOURN(?: E?E?S)?)\b"),
    re.compile(r"(?<![A-Z])(?:EFFETS?|CHEQUES?|CH QUES?|CHQ) REFUS\w* SANS PROV(?:ISION)?\b"),
)
#: Rule D's window: the return credit is dated 0 to this many days after the funder's debit. A 14-day window adds no
#: corpus row.
RETURNED_FUNDER_PAYMENT_WINDOW_DAYS = 7
#: Bank of America's return names the day the returned item was received ('RECEIVED ON 03/03', its slash normalized
#: to a space): a candidate debit dated that month and day is the one returned.
_RECEIVED_ON_DAY = re.compile(r"\bRECEIVED ON (\d{1,2}) ?(\d{1,2})\b")
#: The tiers a return credit rule D reads may carry: out of True (a credit the revenue side counts is never a return).
_RETURN_CREDIT_TIERS = frozenset({"non_revenue", "excluded_pending_review"})


def _returned_payment_credit(text: str) -> bool:
    """A credit printing a bounce form (_RETURNED_PAYMENT_CREDIT_PATTERNS) and no fee word."""
    return _matches_any(text, _RETURNED_PAYMENT_CREDIT_PATTERNS) and _DEPOSIT_UNDO_FEE.search(text) is None


def _received_on_day(text: str) -> tuple[int, int] | None:
    """The (month, day) Bank of America's 'RECEIVED ON <mm> <dd>' prints, or None."""
    found = _RECEIVED_ON_DAY.search(text)
    if found is None:
        return None
    month, day = int(found.group(1)), int(found.group(2))
    return (month, day) if 1 <= month <= 12 and 1 <= day <= 31 else None


def _return_gap(
    records: list[TransactionClassification], credit_index: int, debit_index: int,
) -> tuple[bool, int | None]:
    """(inside rule D's window, the gap in days): the credit dated 0 to RETURNED_FUNDER_PAYMENT_WINDOW_DAYS days after
    the debit; when either row is undated, the debit printed before the credit (the gap then None)."""
    credit_date, debit_date = parse_date(records[credit_index].date), parse_date(records[debit_index].date)
    if credit_date is None or debit_date is None:
        return debit_index < credit_index, None
    days = (credit_date - debit_date).days
    return 0 <= days <= RETURNED_FUNDER_PAYMENT_WINDOW_DAYS, days


def _returned_funder_payment_pairs(
    records: list[TransactionClassification], duplicate_indexes: set[int],
) -> list[tuple[int, int]]:
    """True revenue spec §6.2 pass 7b: rule D's (credit index, debit index) pairs, in the credits' (date, row) order,
    undated first.

    - Funder debits: posted, not duplicates, confirmed lenders' payments counted as paid (_is_paid_funder_debit) that
      no pair reversed and no earlier return took. Guard debits: every other posted debit that is no duplicate and no
      confirmed lender's (potential lenders included).
    - Return credits: posted, not duplicates, not a named pair's credit (another debit's reversed_by), not a lender
      credit, out of True (_RETURN_CREDIT_TIERS: never a credit the revenue side counts) and printing a bounce form
      (_returned_payment_credit).
    - A credit the revenue side paired (matched_reversal_pair) pairs only with its partner, when that is an unused
      funder debit of equal cents inside the window and order (_return_gap); otherwise it is left alone. A credit that
      names a confirmed funder (the credit index of the known payees) pairs only with that funder's debits.
    - Otherwise the candidates are the unused funder debits of equal cents inside the window and order. A candidate
      dated on the 'RECEIVED ON' day the credit prints wins; else the latest debit date, then the nearest row. The
      credit is skipped when an equal guard debit lies in the window as near as the chosen one, or undated.
    Each debit pairs once."""
    def location(index: int) -> str:
        return records[index].source_location or f"transaction:{index + 1}"

    def cents(index: int) -> int:
        return round(abs(records[index].amount) * 100)

    funder_debits = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and _is_paid_funder_debit(record)
        and record.reversed_by is None and record.returned_funder_payment_by is None
    ]
    if not funder_debits:
        return []
    guard_debits = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount < 0 and record.is_posted
        and record.classification != "confirmed_lender"
    ]
    paired_credits = {record.reversed_by for record in records if record.reversed_by}
    credits: list[tuple[date, int]] = []
    for index, record in enumerate(records):
        if (
            index in duplicate_indexes
            or record.amount <= 0
            or not record.is_posted
            or location(index) in paired_credits
            or record.contributes_to_lender_credit_exclusion
            or record.revenue_tier not in _RETURN_CREDIT_TIERS
            or not _returned_payment_credit(record.normalized_description)
        ):
            continue
        credits.append((parse_date(record.date) or date.min, index))
    credits.sort()
    used: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _, credit_index in credits:
        credit = records[credit_index]
        named = match_known_payee(credit.normalized_description, credit=True)
        funder = named.entity if named is not None and named.state == "confirmed_lender" else None
        candidates = [
            index for index in funder_debits
            if index not in used and cents(index) == cents(credit_index)
            and (funder is None or records[index].canonical_entity == funder)
            and _return_gap(records, credit_index, index)[0]
        ]
        if credit.revenue_match_method == "matched_reversal_pair":
            partner = next((index for index in candidates if location(index) == credit.revenue_related_transaction),
                           None)
            if partner is not None:
                used.add(partner)
                pairs.append((credit_index, partner))
            continue
        if not candidates:
            continue
        received = _received_on_day(credit.normalized_description)

        def rank(index: int) -> tuple[int, int, int]:
            debit_date = parse_date(records[index].date)
            on_received = received is not None and debit_date is not None and (
                (debit_date.month, debit_date.day) == received)
            return (0 if on_received else 1, -(debit_date.toordinal() if debit_date else 0),
                    abs(credit_index - index))

        chosen = min(candidates, key=rank)
        chosen_gap = _return_gap(records, credit_index, chosen)[1]
        if any(
            cents(index) == cents(credit_index)
            and (window := _return_gap(records, credit_index, index))[0]
            and (window[1] is None or chosen_gap is None or window[1] <= chosen_gap)
            for index in guard_debits
        ):
            continue
        used.add(chosen)
        pairs.append((credit_index, chosen))
    return pairs


def _apply_returned_funder_payments(
    records: list[TransactionClassification], duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """True revenue spec §6.2 pass 7b, §11: each rule-D pair (_returned_funder_payment_pairs) takes the funder's debit
    out of paid to lenders (contributes_to_lender_totals and, as a named pair does, contributes_to_flagged_totals
    False; returned_funder_payment_by the credit's location; the reason's returned-unpaid sentence) and keeps its
    withholding and its lender count; the credit names the debit (returns_funder_payment). reversed_by,
    settlement_reversal and every revenue field stay as they are, so the reconciliation's reversal coverage, the
    settled-activity counts and every revenue reading are unchanged. It runs after pass 7, so the credit's tier is
    final, and before the duplicate finalisation."""
    pairs = _returned_funder_payment_pairs(records, duplicate_indexes)
    if not pairs:
        return records
    updated = list(records)
    for credit_index, debit_index in pairs:
        credit_location = records[credit_index].source_location or f"transaction:{credit_index + 1}"
        debit_location = records[debit_index].source_location or f"transaction:{debit_index + 1}"
        updated[debit_index] = replace(
            updated[debit_index],
            contributes_to_lender_totals=False,
            contributes_to_flagged_totals=False,
            returned_funder_payment_by=credit_location,
            reason=f"{updated[debit_index].reason} {_returned_unpaid_reason(credit_location)}",
            # A returned payoff attempt stays in the rate, as Q5 rules.
            **_returned_payoff_in_rate(updated[debit_index]),
        )
        updated[credit_index] = replace(updated[credit_index], returns_funder_payment=debit_location)
    return updated


def _represented_reason(debit_location: str, kind: str) -> str:
    """The sentence a re-debited returned payment adds to its reason (the owner's answer named without its date, as
    _returned_unpaid_reason names Q5's)."""
    how = "caught it up 2x" if kind == "caught_up" else "re-presented it"
    return (
        f"The funder {how} by {debit_location}: out of the withholding rate, which counts the obligation once (the "
        "owner's answer on re-presented payments, \"Count it once\")."
    )


def _apply_represented_funder_payments(
    records: list[TransactionClassification], duplicate_indexes: set[int], calendar: str = "US",
) -> list[TransactionClassification]:
    """True revenue spec §6.2 pass 7c, §11, §17.1: a confirmed funder's payment returned unpaid LEAVES the withholding
    numerator once the same funder re-debits it, the same cents off its cycle or an exact 2x catch-up, dated on or after
    the return and within one cadence gap after it (analysis.represented_payments.re_debits). The returned debit's
    `contributes_to_withholding_rate` is cleared, `represented_by` names the re-debit and its reason gains a sentence;
    nothing else moves (paid to lenders, the lender count, `reversed_by`, the re-debit itself and every revenue field
    stay as they were). Until such a re-debit exists the returned attempt stays in the numerator, as Q5 rules. It runs
    after pass 7b, which makes the last returned payments, and before the duplicate finalisation. A paid debit the rate
    leaves out (`out_of_rate_payment`: a worded lump-sum payoff) is never the re-debit, since the returned attempt would
    then leave the numerator beside it and the obligation would count zero times; it stays in the series the schedule
    and the 2x level are read from."""
    from analysis.represented_payments import Attempt, Returned, out_of_rate_payment, re_debits

    def location(index: int) -> str:
        return records[index].source_location or f"transaction:{index + 1}"

    by_location = {location(index): index for index in range(len(records))}
    attempts: list[Attempt] = []
    returned: list[Returned] = []
    out_of_rate: set[int] = set()
    for index, record in enumerate(records):
        if (index in duplicate_indexes or record.amount >= 0 or not record.is_posted
                or record.classification != "confirmed_lender" or not record.canonical_entity):
            continue
        if not (record.contributes_to_lender_totals or record.returned_funder_payment_by):
            continue
        day = parse_date(record.date)
        if day is None:
            continue
        attempt = Attempt(index, record.canonical_entity, day, round(abs(record.amount) * 100), (day, index))
        attempts.append(attempt)
        if out_of_rate_payment(record.returned_funder_payment_by, record.contributes_to_withholding_rate):
            out_of_rate.add(index)
        credit = by_location.get(record.returned_funder_payment_by or "")
        credit_day = parse_date(records[credit].date) if credit is not None else None
        if record.returned_funder_payment_by and record.contributes_to_withholding_rate and credit_day is not None:
            returned.append(Returned(attempt, credit_day))
    if not returned:
        return records
    found = re_debits(returned, attempts, calendar,
                      may_re_debit=lambda _returned, candidate: candidate.key not in out_of_rate)
    if not found:
        return records
    updated = list(records)
    for index, (debit_index, kind) in found.items():
        # Its Q5 sentence no longer says "kept in the withholding rate".
        credit_location = updated[index].returned_funder_payment_by
        head, standing, tail = updated[index].reason.rpartition(_returned_unpaid_reason(credit_location))
        reason = f"{head}{_returned_unpaid_reason(credit_location, re_debited=True)}{tail}" if standing else (
            updated[index].reason)
        updated[index] = replace(
            updated[index],
            contributes_to_withholding_rate=False,
            represented_by=location(debit_index),
            reason=f"{reason} {_represented_reason(location(debit_index), kind)}",
        )
    return updated
