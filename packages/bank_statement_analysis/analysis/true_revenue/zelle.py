"""Pass text, Zelle deposit and the Zelle policy."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Sequence, TYPE_CHECKING

from analysis.classification.record import _replace_revenue_state
from analysis.descriptor.lexical import _before_receiver, revenue_text
from analysis.descriptor.rails import _is_wire_row, _loose_wire_originator
from analysis.revenue import REVENUE_TIER_REASONS
from analysis.true_revenue.channel import without_transfer_code

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: Spec §8.4, §8.10 step 26, §19.1: every posted Zelle deposit is non_revenue with this reason, whoever sent it, a
#: lender or a processor paying through Zelle included (_zelle_excluded). A row a non-revenue rule already decided keeps
#: that rule, and a direction conflict keeps its hold.
ZELLE_EXCLUDED = "zelle_excluded"
#: Q3: the method and the rule of a Zelle deposit the policy excluded.
ZELLE_POLICY_METHOD = "zelle_deposit_excluded"
#: Q3: the context signal that keeps the rules' own reading of an excluded Zelle deposit
#: ('zelle_prior:<tier>:<reason>', read by zelle_prior_reading).
_ZELLE_PRIOR = "zelle_prior:"
#: Q3: the Zelle rail, read on the revenue text before the receiver fields (zelle_deposit). The corpus prints it as
#: 'ZELLE PAYMENT FROM <sender> (CONF#)', 'ZELLE FROM <sender> ON ## ## REF', 'ZELLE INSTANT PMT FROM', 'ZELLE
#: BUSINESS PAYMENT FROM <sender> PAYMENT ID', 'ZELLE CREDIT (FROM)', 'ZELLE MONEY RECEIVED FROM', 'TRANSFER IN ZELLE
#: FROM', 'TD ZELLE RECEIVED', Citizens' '... CREDIT ZELLE CREDIT ... ZELLE <name>', Navy Federal's 'ZELLE (CR) <name>'
#: and PNC's 'Zel From <name>', with a date or a reference glued on either side ('ZELLE1234567', '0302ZELLE': the
#: right boundary is a letter, so the glued reference reads with or without the revenue text's rail split). The left
#: boundary is the card forms' (no letter before), so a name holding the letters (HAZEL, ROSZELL, MAZZELLA, ZELLER,
#: EZELL) is never read. The classifier's _CONSUMER_P2P_RAIL, shared with the legacy classes and the debits, does not
#: read PNC's ZEL and is not changed. Pass 7 reads PNC's ZEL as its ZELLE twin on its own text (pass_text); the ZEL
#: arm stays here for the readers of the raw text.
_ZELLE_RAIL = re.compile(r"(?<![A-Z])ZELLE(?![A-Z])|(?<![A-Z])ZEL (?:FROM|TO)\b")
#: PNC's spelling of the Zelle rail, 'ZEL FROM <sender>' and 'ZEL TO <recipient>', which pass_text spells 'ZELLE '.
_ZEL_SPELLING = re.compile(r"(?<![A-Z])ZEL (?=(?:FROM|TO)\b)")


def pass_text(record, text: str) -> str:
    """§8.4: the credit text pass 7's payer facts, holds, counter-credit reading and Zelle step read, and the census's
    facts (guard_facts) and the served Zelle view (zelle_view._reads_zelle) read: the revenue text without TD Canada
    Trust's e-Transfer code (without_transfer_code), with PNC's Zelle rail, printed 'ZEL FROM <sender>' or 'ZEL TO
    <recipient>' (_ZEL_SPELLING), spelled as its ZELLE twin. So a PNC Zelle credit reads as the same sender's 'ZELLE
    FROM' row: the person-to-person channel (_p2p_rail), the payer region and key (pooled with that sender's ZELLE
    rows), the round-sum repeat, and the person match of the counter-debit hold. `record` needs only its bank and
    printed description. The classifier's _CONSUMER_P2P_RAIL (the 5.5 channel gate, the legacy classes, the debits) is
    unchanged: a 'ZEL TO' debit keeps the classifier's debit reading. §8.4: the classifier's earlier reading of the
    raw text is not pass 7's, so a ZEL credit whose sender looks like an operating platform is still claimed as an
    operating source (counted, and Verified on a repeat), and a 'ZEL TO' debit keeps its legacy class 'other' and no
    person key (a credit for its own amount, or one with no person key, names it by the first word)."""
    return _ZEL_SPELLING.sub("ZELLE ", without_transfer_code(record, text))


def zelle_deposit(text: str) -> bool:
    """Q3 (spec §8.4): the credit's revenue text prints the Zelle rail before its receiver fields (_ZELLE_RAIL). An
    incoming wire or a loose wire's originator row is never a Zelle deposit, whatever its memo prints ('PMT
    DET:INVOICE <n> PAID BY WIRE INSTEAD OF ZELLE'): an incoming wire (the classifier's _is_wire_row) or a loose
    wire's originator row (_loose_wire_originator, as merchant_settlement reads it; read on the row up to its first
    Zelle word, since the classifier's loose-wire label refuses a row that prints a consumer rail, so a word in the
    originator's name or memo after the label reads as the wire's) is not read. The ACH entry-description forms
    ('DES:ZELLE') and the rail printed mid-row are kept; a company whose name holds the word ZELLE paying by ACH still
    reads (§8.4's residual). A wire layout neither gate reads ('<sender> WIRE' with no originator label, 'ONLINE WIRE
    TRANSFER FROM', 'WIRE TRANS SVC CREDIT', 'WIRE DEPOSIT') still reads a memo's ZELLE, and a Zelle row that prints
    WIRE and an originator label before its rail word is refused (§8.4's residuals, 0 corpus rows)."""
    row = _before_receiver(text)
    rail = _ZELLE_RAIL.search(row)
    if rail is None:
        return False
    return not (
        _is_wire_row(text) or _loose_wire_originator(text)
        or _loose_wire_originator(row[: rail.start()])
    )


def _zelle_excluded(record: TransactionClassification) -> TransactionClassification:
    """Q3 (spec §8.4, §8.10 step 26): a Zelle deposit the rules tiered, excluded by the owner's policy: non_revenue,
    method and rule ZELLE_POLICY_METHOD, reason ZELLE_EXCLUDED. The rules' own reading (its tier and reason) stays in
    the reason sentence and in the zelle_prior signal (zelle_prior_reading); a reason code the table does not list
    names itself. Only the revenue fields and the contribution flags change: the legacy classification, the entity,
    the flag group, the lender-credit exclusion, the withholding flag and the review flag stay."""
    tier, reason = record.revenue_tier, record.revenue_tier_reason
    label = "Verified revenue" if tier == "verified" else REVENUE_TIER_REASONS.get(reason, (None, reason or tier))[1]
    excluded = _replace_revenue_state(
        record,
        "non_revenue",
        match_method=ZELLE_POLICY_METHOD,
        matched_rule=ZELLE_POLICY_METHOD,
        confidence_score=1.0,
        reason=(
            "A Zelle deposit, excluded from true revenue by the owner's policy (the underwriter's Q3, spec §19.1); the "
            f"rules read it as: {label}."
        ),
        context_signals=(*record.revenue_context_signals, ZELLE_POLICY_METHOD, f"{_ZELLE_PRIOR}{tier}:{reason or ''}"),
        related_transaction=record.revenue_related_transaction,
    )
    return replace(excluded, revenue_tier_reason=ZELLE_EXCLUDED)


def zelle_prior_reading(record: TransactionClassification) -> tuple[str, str | None] | None:
    """Q3: the tier and reason the rules gave a Zelle deposit the policy excluded (the zelle_prior signal), or
    None for any other row."""
    for signal in record.revenue_context_signals:
        if signal.startswith(_ZELLE_PRIOR):
            tier, _, reason = signal[len(_ZELLE_PRIOR):].partition(":")
            return tier, reason or None
    return None


def zelle_credits_present(records: Sequence[TransactionClassification], duplicate_indexes: set[int]) -> bool:
    """Whether any credit pass 7 reads (posted, not a duplicate, carrying a revenue state) prints the Zelle rail on
    the pass's own text (zelle_deposit, on pass_text). Only such a row can read differently in the counted reading:
    the Zelle step and the two lifted carve-outs read nothing else, so a statement without one has a single reading."""
    return any(
        index not in duplicate_indexes and record.amount > 0 and record.is_posted
        and record.revenue_classification is not None
        and zelle_deposit(pass_text(record, revenue_text(record.normalized_description)))
        for index, record in enumerate(records)
    )
