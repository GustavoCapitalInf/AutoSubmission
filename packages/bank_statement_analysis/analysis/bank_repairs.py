"""analysis/bank_repairs.py — the post-parse repairs, each keyed on the bank
label its own guard compares.

R10 put the six bank-keyed rewrites through a hygiene
ceremony at the Phase 2.3 milestone: inventory, independent reproduction over
the run of record, comparison with the repair doctrine, classification, and a
consequence. The ceremony repairs below DECLARE their classification on a
`R10-CLASSIFICATION:` line, in the closed vocabulary
`safe_evidence_preserving_normalisation` / `unsafe_rewrite` /
`legacy_needing_replacement`, with the reason beside it.
`tests/test_bank_repairs_ceremony.py` reads those declarations out of this
module and holds them to it: a repair that loses its declaration, or gains one
outside the vocabulary, fails the build.

The repair bodies retain their historical behaviour. Subsequent rulings
(S-1..S-5, 2026-09-15) fenced four unsafe repairs and one legacy repair by
removing their analysis imports and callers; their definitions, measured
populations and doctrine reasons remain here. The ceremony tripwire rejects
references that could restore a caller, including alias bindings. A further
correctness correction that moves a validated document still requires a
ruling (BATCH9-RULES).

The fence was reviewed on the Phase 2.3 branch `wave23-precision` and never
composed into the shipped line; the audit of 2026-10-13 (PARSERS-1) ported it.

The doctrine each classification is measured against (batch 9): a parser
never writes an amount or a date the paper did not print; and the
anti-optimizer rule — reconciliation is a VERIFIER, never the evidence that
selects a figure.
"""
from __future__ import annotations

from .schema import Statement, Transaction


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _row_key(transaction: Transaction) -> tuple:
    return (transaction.date, transaction.description)


def restates_a_printed_figure(before: Statement, after: Statement) -> bool:
    """The R10 INVENTION GUARD: is `after` a restatement of figures `before`
    already carried, or does it carry a figure the paper did not print?

    TRUE when the repair only (a) dropped SOME rows, (b) left an amount alone,
    or (c) changed an amount's SIGN while keeping the magnitude the paper
    printed. FALSE as soon as

    * a row's magnitude, date or description changes, or a row appears that
      was not printed;
    * a printed row is DUPLICATED — `after` must be a sub-multiset of
      `before`, row for row, not merely a set of familiar keys;
    * a row's `running_balance` changes, in either direction: a repair may
      neither write a balance the paper did not print nor erase one it did;
    * the statement's own `beginning_balance` or `ending_balance` changes;
    * EVERY row is deleted — a repair that empties the ledger has not
      normalised a statement, it has replaced one.

    The first version of this guard read transaction magnitudes keyed on
    `(date, description)` and nothing else, so it returned True for a
    statement whose every running balance had been rewritten, for one whose
    opening and closing figures had been rewritten, for one with every row
    deleted, and for one with a row duplicated (review MINOR-2 reproduced all
    five). The docstring already promised otherwise. The promise is the part
    that was right.

    This predicate is NOT called by any repair and changes no behaviour: it is
    the contract `tests/test_bank_repairs_ceremony.py` holds the repairs
    classified `safe_evidence_preserving_normalisation` to, and the line the
    ones classified `unsafe_rewrite` are recorded as crossing. A repair may
    not be promoted to the safe class while this returns False for it.
    """
    if _round(before.beginning_balance) != _round(after.beginning_balance):
        return False
    if _round(before.ending_balance) != _round(after.ending_balance):
        return False
    if before.transactions and not after.transactions:
        return False
    if len(after.transactions) > len(before.transactions):
        return False
    # A sub-multiset, row for row: every row of `after` is CONSUMED from
    # `before`, so a duplicated row runs out of originals to match.
    unmatched: dict[tuple, list[Transaction]] = {}
    for transaction in before.transactions:
        unmatched.setdefault(_row_key(transaction), []).append(transaction)
    for transaction in after.transactions:
        candidates = unmatched.get(_row_key(transaction), [])
        match = next(
            (candidate for candidate in candidates
             if round(abs(candidate.amount), 2) == round(abs(transaction.amount), 2)
             and _round(candidate.running_balance) == _round(transaction.running_balance)),
            None,
        )
        if match is None:
            return False
        candidates.remove(match)
    return True


def repair_b1_beginning_balance(stmt: Statement) -> Statement:
    if "B1" not in (stmt.bank or "").upper() or stmt.beginning_balance is None:
        return stmt
    beginning = round(stmt.beginning_balance, 2)
    txns = [
        t for t in stmt.transactions
        if not (
            t.description.strip().upper().startswith("BEGINNING BALANCE")
            and round(t.amount, 2) == beginning
        )
    ]
    return stmt.model_copy(update={"transactions": txns}) if len(txns) != len(stmt.transactions) else stmt


def repair_capital_one_running_amount(stmt: Statement) -> Statement:
    """Correct isolated OCR amount slips when adjacent balances prove the amount.

    R10-CLASSIFICATION: unsafe_rewrite

    Reason: the figure it writes (`inferred`, the difference of two printed
    running balances) is not a token the paper printed, and the row it writes
    it on is SELECTED because that one correction closes the summary identity
    — `round(inferred - old, 2) != needed_delta: continue`. Both halves of
    the anti-optimizer rule are crossed: a derived figure replaces a read one,
    and reconciliation is the evidence that chooses it. The adjacent balances
    are real evidence, which is why this is a rewrite to be REPLACED by a
    reconstruction that reads the row (2.4), not a defect to be patched here.
    FENCED under Gustavo's ruling (R10 item S-1). The definition is retained
    as the record of what ran; nothing under `analysis/` calls it. The
    instrumented ceremony found no payload change on its candidates. The
    union replay must establish zero movement with all five fences together;
    any movement is a STOP."""
    if "CAPITAL ONE" not in (stmt.bank or "").upper():
        return stmt
    if stmt.beginning_balance is None or stmt.ending_balance is None:
        return stmt

    txns = list(stmt.transactions)
    computed = round(stmt.beginning_balance + sum(t.amount for t in txns), 2)
    needed_delta = round(stmt.ending_balance - computed, 2)
    if needed_delta == 0:
        return stmt

    for i in range(1, len(txns)):
        prev_balance = txns[i - 1].running_balance
        cur_balance = txns[i].running_balance
        if prev_balance is None or cur_balance is None:
            continue
        inferred = round(cur_balance - prev_balance, 2)
        old = round(txns[i].amount, 2)
        if old == inferred:
            continue
        if (old > 0) != (inferred > 0):
            continue
        if round(inferred - old, 2) != needed_delta:
            continue
        txns[i] = txns[i].model_copy(update={
            "amount": inferred,
            "direction": "credit" if inferred > 0 else "debit",
        })
        return stmt.model_copy(update={"transactions": txns})
    return stmt


def repair_regions_transactions(markdown: str, stmt: Statement) -> Statement:
    """Clear a balance column that is not a per-row running balance, and fill
    the one zero-amount card-transaction row from the summary shortfall.

    R10-CLASSIFICATION: unsafe_rewrite

    Reason: the second half writes `needed_delta` — the amount by which the
    printed summary fails to balance — into a row whose own amount was read
    as zero, gated on there being exactly one such row and on the shortfall
    being under a bare 100.00. That is a figure the paper did not print,
    computed from the identity it then satisfies, admitted by a magic bound.
    The first half (clearing every `running_balance` when the document prints
    a daily-balance summary) invents nothing and is defensible on its own; a
    function is classified by the most dangerous thing it does.
    FENCED under Gustavo's ruling (R10 item S-2). The definition is retained
    as the record of what ran; nothing under `analysis/` calls it. The
    instrumented ceremony found no payload change on its candidates. The
    union replay must establish zero movement with all five fences together;
    any movement is a STOP."""
    if "REGIONS" not in (stmt.bank or "").upper():
        return stmt

    txns = list(stmt.transactions)
    changed = False
    if "DAILY BALANCE SUMMARY" in markdown.upper():
        cleared = [t.model_copy(update={"running_balance": None}) if t.running_balance is not None else t for t in txns]
        changed = any(a.running_balance != b.running_balance for a, b in zip(txns, cleared))
        txns = cleared

    if stmt.beginning_balance is not None and stmt.ending_balance is not None:
        computed = round(stmt.beginning_balance + sum(t.amount for t in txns), 2)
        needed_delta = round(stmt.ending_balance - computed, 2)
        zero_indexes = [
            i for i, t in enumerate(txns)
            if round(t.amount, 2) == 0.0 and "CARD TRANSACTION" in t.description.upper()
        ]
        if len(zero_indexes) == 1 and 0 < abs(needed_delta) <= 100:
            i = zero_indexes[0]
            txns[i] = txns[i].model_copy(update={
                "amount": needed_delta,
                "direction": "credit" if needed_delta > 0 else "debit",
            })
            changed = True

    return stmt.model_copy(update={"transactions": txns}) if changed else stmt


def repair_truist_converted_checks(stmt: Statement) -> Statement:
    """Retained transfer-direction and converted-check normalization.

    R10-CLASSIFICATION: legacy_needing_replacement

    Reason: the converted-check witness set includes tilde-marked rows
    themselves. A lone tilde converted-check row can therefore be removed
    without a separate duplicate witness and can empty a nonempty ledger.
    The legitimate paired-duplicate and transfer-direction cases do not
    establish the broader deletion as safe. No amount is derived and no
    reconciliation is optimized, so this is a legacy replacement need.

    FENCED under the S-5 ruling. The executable definition is kept
    as the record of what ran; its analysis import and caller are removed.
    The instrumented corpus reached it on 900 documents and observed no
    payload change, including its 48 candidates. The combined five-fence
    identity proof is the gate: any payload or outcome movement is a STOP.
    Replacement belongs in the reader that establishes a separate duplicate
    witness.
    """
    if "TRUIST" not in (stmt.bank or "").upper():
        return stmt

    txns = [
        t.model_copy(update={"amount": abs(t.amount), "direction": "credit"})
        if "TRUIST ONLINE TRANSFER ONLINE FROM" in t.description.upper() and t.amount < 0
        else t
        for t in stmt.transactions
    ]

    converted = {
        (t.date, round(abs(t.amount), 2))
        for t in txns
        if "CONVERTED CHECK" in t.description.upper()
    }
    if not converted:
        return stmt.model_copy(update={"transactions": txns}) if txns != stmt.transactions else stmt

    filtered: list[Transaction] = []
    for t in txns:
        desc = t.description.strip().upper()
        if "~" in desc and (t.date, round(abs(t.amount), 2)) in converted:
            continue
        filtered.append(t)
    return stmt.model_copy(update={"transactions": filtered}) if filtered != stmt.transactions else stmt


def repair_chase_remote_deposit_count_column(stmt: Statement) -> Statement:
    """Undo an item-count digit merged into a Remote Online Deposit amount.

    Chase prints "Remote Online Deposit <count>" next to the amount; flattened
    text sometimes fuses the count into the amount's leading digits (e.g.
    count "1" + "40.98" read as "1,040.98"). Evidence gates (R-1 item 6 - the
    old rule fired only on an exact -1000.00 delta with a 1000-2000 amount):

    - the printed summary identity (beginning + sum = ending) must currently
      fail by some negative delta;
    - exactly the correction the identity demands must equal the row's amount
      with a fused digit prefix removed - i.e. the corrected amount's digits
      are a proper suffix of the parsed amount's digits;
    - applying that one correction restores the identity exactly.

    R10-CLASSIFICATION: unsafe_rewrite

    Reason: the amount it writes is `amount + needed_delta` — computed FROM
    the summary shortfall — and the third gate is, in the docstring's own
    words, that applying it "restores the identity exactly". The digit-suffix
    test is real independent evidence of the defect's shape and is why this is
    the narrowest of the three rewrites, but it confirms the correction rather
    than producing it: the figure still comes from the identity, and the
    identity is a verifier. The correct home is a reader that sees the count
    column as a column (2.4).
    FENCED under Gustavo's ruling (R10 item S-3). The definition is retained
    as the record of what ran; nothing under `analysis/` calls it. The
    instrumented ceremony found no payload change on its candidates. The
    union replay must establish zero movement with all five fences together;
    any movement is a STOP."""
    if "CHASE" not in (stmt.bank or "").upper():
        return stmt
    if stmt.beginning_balance is None or stmt.ending_balance is None:
        return stmt

    txns = list(stmt.transactions)
    computed = round(stmt.beginning_balance + sum(t.amount for t in txns), 2)
    needed_delta = round(stmt.ending_balance - computed, 2)
    if needed_delta >= 0:
        return stmt

    for i, t in enumerate(txns):
        desc = t.description.upper()
        amount = round(t.amount, 2)
        if "REMOTE ONLINE DEPOSIT" not in desc or amount <= 0:
            continue
        corrected = round(amount + needed_delta, 2)
        if corrected <= 0:
            continue
        amount_digits = str(round(amount * 100))
        corrected_digits = str(round(corrected * 100))
        fused_prefix_removed = (
            len(amount_digits) > len(corrected_digits)
            and amount_digits.endswith(corrected_digits)
        )
        if not fused_prefix_removed:
            continue
        txns[i] = t.model_copy(update={"amount": corrected, "direction": "credit"})
        return stmt.model_copy(update={"transactions": txns})
    return stmt


def repair_single_row_signs_from_balances(stmt: Statement) -> Statement:
    """Flip the sign of the one row in a balance segment whose flip makes the
    segment's sum agree with the printed balance step.

    R10-CLASSIFICATION: unsafe_rewrite (anti-optimizer selection)

    FENCED — this function is NOT CALLED. It stays defined because deleting it
    would delete the record of what ran on every cold run up to this one;
    nothing under `analysis/` may invoke it, and
    `tests/test_bank_repairs_ceremony.py` refuses a caller by AST.

    Reason (STOP item S-4, ruled by Ocean on the reviewer's reproduction).
    Where a segment's sum disagrees with its printed step, this walks the
    segment's rows and flips the FIRST one whose flip reconciles it. When two
    rows of equal magnitude would both reconcile, it does not notice: it takes
    the earlier in document order and publishes it as a DIRECTION. That is
    several independently plausible interpretations, tested against a
    reconciliation, with whichever balances kept — the anti-optimizer pattern
    exactly, whose ruling is REVIEW or REFUSE and never "pick one".

    What is true in its favour, and why it took a ruling rather than a reading:
    every magnitude it publishes is the printed one (it passes the invention
    guard), the figure it reconciles against is a printed PER-ROW balance and
    not the statement's summary, and it is silent when nothing reconciles. It
    sits between `repair_santander_signs_from_balances` — which fires only
    where the magnitudes already agree and therefore chooses nothing — and the
    three rewrites that write a figure the paper did not print.

    It fired on 0 of its 201 candidate documents on the Phase 2.2 run of
    record: the reviewer's instrumented replay reached this stage 201 / 201
    times and the function returned the same object every time. That is why
    the fence costs no coverage, and it is also the reason the fence is worth
    putting up now rather than after a corpus in which it does fire."""
    bank = (stmt.bank or "").upper()
    if "CIBC" not in bank and bank != "ROYAL BANK OF CANADA":
        return stmt

    txns = list(stmt.transactions)
    changed = False
    prev_balance = stmt.beginning_balance
    segment: list[int] = []

    for i, t in enumerate(txns):
        segment.append(i)
        if t.running_balance is None or prev_balance is None:
            if t.running_balance is not None:
                prev_balance = t.running_balance
                segment.clear()
            continue

        expected = round(t.running_balance - prev_balance, 2)
        actual = round(sum(txns[j].amount for j in segment), 2)
        if actual != expected:
            for j in segment:
                candidate = round(actual - (2 * txns[j].amount), 2)
                if candidate == expected:
                    fixed = round(-txns[j].amount, 2)
                    txns[j] = txns[j].model_copy(update={
                        "amount": fixed,
                        "direction": "credit" if fixed > 0 else "debit",
                    })
                    changed = True
                    actual = expected
                    break
        prev_balance = t.running_balance
        segment.clear()

    return stmt.model_copy(update={"transactions": txns}) if changed else stmt


def repair_scotiabank_misc_payment_sign(stmt: Statement) -> Statement:
    """Read a misc-payment row's DIRECTION from the two printed balances it
    sits between.

    R10-CLASSIFICATION: safe_evidence_preserving_normalisation

    Reason: the magnitude it publishes is the magnitude the paper printed —
    only the sign changes — and the sign is taken from an identity between
    two figures the paper printed on the page (`prev_balance - amount ==
    this row's balance`), not from the statement's summary. Nothing is
    selected because it balances the statement. It is chain-DERIVED direction,
    which R14 rules a thing to flag and measure, never in itself a rewrite.
    Pinned by the invention guard in the ceremony tests."""
    if "SCOTIABANK" not in (stmt.bank or "").upper():
        return stmt

    txns = list(stmt.transactions)
    changed = False
    for i in range(1, len(txns)):
        t = txns[i]
        prev_balance = txns[i - 1].running_balance
        if prev_balance is None or t.running_balance is None:
            continue
        desc = t.description.upper()
        if "MISC PAYMENT FH" not in desc or t.amount <= 0:
            continue
        if round(prev_balance - t.amount, 2) == round(t.running_balance, 2):
            txns[i] = t.model_copy(update={"amount": -round(t.amount, 2), "direction": "debit"})
            changed = True
    return stmt.model_copy(update={"transactions": txns}) if changed else stmt


def repair_santander_signs_from_balances(stmt: Statement) -> Statement:
    """Read each row's DIRECTION from the printed balance it lands on.

    R10-CLASSIFICATION: safe_evidence_preserving_normalisation

    Reason: it fires only where the balance step and the parsed amount already
    agree in magnitude (`abs(delta) == abs(t.amount)`) and disagree in sign,
    and it writes `delta`, whose magnitude is therefore the printed one. No
    figure is produced that the paper did not carry, and the summary identity
    is never consulted — this is the same chain-derived DIRECTION R14 rules a
    thing to flag and measure. Pinned by the invention guard in the ceremony
    tests."""
    if "SANTANDER" not in (stmt.bank or "").upper() or stmt.beginning_balance is None:
        return stmt

    txns = list(stmt.transactions)
    changed = False
    prev_balance = stmt.beginning_balance
    for i, t in enumerate(txns):
        if t.running_balance is None:
            continue
        delta = round(t.running_balance - prev_balance, 2)
        if round(abs(delta), 2) == round(abs(t.amount), 2) and delta != round(t.amount, 2):
            txns[i] = t.model_copy(update={
                "amount": delta,
                "direction": "credit" if delta > 0 else "debit",
            })
            changed = True
        prev_balance = t.running_balance
    return stmt.model_copy(update={"transactions": txns}) if changed else stmt
