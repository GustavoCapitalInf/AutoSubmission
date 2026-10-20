"""FABRICATED payloads that follow the lender-detection payload contract (plan C4/C5). Never a real statement.

Every payee is an invented name built from its group key, every amount a short named constant, and every date
falls in a year no statement in the archive covers. The rows carry exactly the fields the contract publishes, so
the serving, export and package tests run before the classifier that produces them (service S2) has landed.
"""
from __future__ import annotations

from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from tests.l1s3_payloads import account_payload, document_payload

#: The invented debit each fabricated flagged row posts. Short and named once, as tests/l1s3_payloads.py does,
#: so no added line carries a figure a real statement could have printed.
FLAGGED_DEBIT = 7.0
#: The classifier version the contract's records carry (C4). Re-pinned 5.0 -> 5.1 with the D6 clarification,
#: 5.1 -> 5.2 with its second one (2026-09-27: compensation memos, masked recipient accounts), 5.2 -> 5.3 with
#: the false-positive release, 5.3 -> 5.4 with the Idea Financial ruling (2026-09-28), and 5.4 -> 5.5 with the
#: true-revenue bug fixes, 5.5 -> 5.6 with its revenue tiers, and 5.6 -> 5.7 with the audit's fix batches, round 2 and
#: the owner's rulings (audit round 2, R2-B16: R56), and 5.7 -> 5.8 with the round-3 fix batches (audit round 3,
#: R3-B25), and 5.8 -> 5.9 with the Amerifi Capital ruling (2026-10-11).
CURRENT_VERSION = "5.9"
#: The flag-group keys in contract order.
GROUP_KEYS = tuple(group.key for group in FLAG_GROUPS)
#: The state a premium-financing row keeps: it has no state of its own and stays insurance (plan contract C1, C4).
PREMIUM_FINANCING_STATE = "insurance"
#: The groups whose posted credits count in the flagged totals (plan contract C4; owner ruling 2026-09-26: a
#: factor's payout is the business's own sales, stays revenue and carries the Factoring flag).
CREDITED_GROUP_KEYS = ("factoring",)


def fabricated_payee(group_key: str) -> str:
    """An obviously invented payee for one flag group."""
    return f"FABRICATED {group_key.upper()} PAYEE"


def row_state(group_key: str | None) -> str:
    """The classification state a row of `group_key` carries: the group's own state, "insurance" for premium
    financing (C1 `state=None`), or "other" for a row of no flag group."""
    if group_key is None:
        return "other"
    return FLAG_GROUP_BY_KEY[group_key].state or PREMIUM_FINANCING_STATE


def flagged_row(
    group_key: str | None,
    *,
    payee: str | None = None,
    amount: float = -FLAGGED_DEBIT,
    date: str = "2054-01-05",
    contributes: bool | None = None,
    version: str | None = CURRENT_VERSION,
) -> dict:
    """One ledger row whose classification record follows C4. `group_key` None is a row of no flag group.

    `contributes` defaults to the contract rule (a debit of a flag group, or a credit of a CREDITED_GROUP_KEYS
    group); pass False for a duplicate or a reversed row. A premium-financing row is an insurance row that also
    carries the flag, so its `contributes_to_insurance_totals` follows the same rule. `version` None leaves
    `classification_version` out, as a record written before the field existed would."""
    state = row_state(group_key)
    name = payee if payee is not None else (fabricated_payee(group_key) if group_key else None)
    if contributes is None:
        contributes = group_key is not None and (amount < 0 or (amount > 0 and group_key in CREDITED_GROUP_KEYS))
    direction = "debit" if amount < 0 else "credit"
    classification = {
        "source_location": None,
        "date": date,
        "amount": amount,
        "direction": direction,
        "classification": state,
        "canonical_entity": name,
        "matched_alias": name,
        "is_posted": True,
        "review_required": False,
        "revenue_classification": None,
        "contributes_to_insurance_totals": state == PREMIUM_FINANCING_STATE and contributes,
        "flagged_group": group_key,
        "contributes_to_flagged_totals": contributes,
    }
    if version is not None:
        classification["classification_version"] = version
    return {
        "date": date,
        "description": f"FABRICATED {state.upper()} ROW",
        "amount": amount,
        "direction": direction,
        "classification": classification,
    }


def classified_now(payload: dict) -> dict:
    """`payload`, an ACCOUNT payload, with the current `classification_version` on every ledger record that carries
    none. Today's classifier writes the field on every record it publishes (C4); the records of the L1-S3 fixture
    (tests/l1s3_payloads.py) predate it, so an analysis built on them reads as classified by older rules (C6).
    Mutates and returns `payload`."""
    for row in payload.get("statement", {}).get("transactions", []):
        row["classification"].setdefault("classification_version", CURRENT_VERSION)
    return payload


def with_flagged_rows(payload: dict, rows: list[dict]) -> dict:
    """`payload`, an ACCOUNT payload, with `rows` appended to its ledger (numbered after the rows already there)
    and its `metrics.flagged_groups` and `detection.flagged_positions` rebuilt from the whole ledger the way C5
    publishes them. Mutates and returns `payload`."""
    ledger = payload.setdefault("statement", {}).setdefault("transactions", [])
    for row in rows:
        row["classification"]["source_location"] = f"transaction:{len(ledger) + 1}"
        ledger.append(row)
    by_payee: dict[tuple[str, str], list[dict]] = {}
    for row in ledger:
        record = row.get("classification") or {}
        if record.get("contributes_to_flagged_totals") is True:
            group = record["flagged_group"]
            payee = record.get("canonical_entity") or FLAG_GROUP_BY_KEY[group].label
            by_payee.setdefault((group, payee), []).append(row)
    entries = []
    for (group, payee), members in by_payee.items():
        dates = sorted(row["date"] for row in members)
        debits = [row for row in members if row["amount"] < 0]
        credits = [row for row in members if row["amount"] >= 0]
        entries.append({
            "group": group,
            "payee": payee,
            "matched_alias": payee,
            "count": len(debits),
            "total_debited": round(sum(abs(row["amount"]) for row in debits), 2),
            "count_credited": len(credits),
            "total_credited": round(sum(row["amount"] for row in credits), 2),
            "cadence": "single" if len(dates) == 1 else "irregular",
            "avg_gap_days": None,
            "first_date": dates[0],
            "last_date": dates[-1],
            "source_locations": [row["classification"]["source_location"] for row in members],
            "review_required": any(row["classification"].get("review_required") is True for row in members),
        })
    entries.sort(key=lambda entry: (GROUP_KEYS.index(entry["group"]),
                                    -(entry["total_debited"] + entry["total_credited"]), entry["payee"]))
    summaries: dict[str, dict] = {}
    for entry in entries:
        summary = summaries.setdefault(
            entry["group"], {"count": 0, "total": 0.0, "count_credited": 0, "total_credited": 0.0, "payees": 0})
        summary["count"] += entry["count"]
        summary["total"] = round(summary["total"] + entry["total_debited"], 2)
        summary["count_credited"] += entry["count_credited"]
        summary["total_credited"] = round(summary["total_credited"] + entry["total_credited"], 2)
        summary["payees"] += 1
    payload.setdefault("metrics", {})["flagged_groups"] = summaries
    payload.setdefault("detection", {})["flagged_positions"] = entries
    return payload


def flagged_account_payload(
    index: int = 0,
    *,
    groups: tuple[str, ...] = GROUP_KEYS,
    currency: str = "USD",
    amount: float = -FLAGGED_DEBIT,
    date: str = "2054-01-05",
) -> dict:
    """A validated ACCOUNT payload (tests/l1s3_payloads.py) in `currency`, with one fabricated debit of `amount`
    on `date` per group in `groups`, each to its own fabricated payee. Every record carries the current
    `classification_version`, as a fresh analysis's records do."""
    payload = classified_now(account_payload(index))
    payload["statement"]["currency"] = currency
    return with_flagged_rows(payload, [flagged_row(key, amount=amount, date=date) for key in groups])


def flagged_document_payload(*, groups: tuple[str, ...] = GROUP_KEYS) -> dict:
    """The DOCUMENT shape (tests/l1s3_payloads.py): two validated accounts, each with one fabricated debit per
    group in `groups`; the second account's debits are twice the first's. Every record carries the current
    `classification_version`, as a fresh analysis's records do."""
    payload = document_payload()
    for index, account in enumerate(payload["accounts"]):
        with_flagged_rows(classified_now(account),
                          [flagged_row(key, amount=-FLAGGED_DEBIT * (index + 1)) for key in groups])
    return payload
