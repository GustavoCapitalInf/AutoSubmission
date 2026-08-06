from __future__ import annotations

from .schema import Statement, Transaction


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


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
    """Correct isolated OCR amount slips when adjacent balances prove the amount."""
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
    """
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
