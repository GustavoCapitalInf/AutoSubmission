"""The Zelle setting's two readings of a published analysis (the owner's amendment of 2026-10-06 to the underwriter's
Q3; true revenue spec §8.4, §9.1, §9.2, §10.7; R2-OW17).

"Mark Zelle Payments as True Revenue" is a DISPLAY setting (webapp/settings.py): Yes (the default) counts every Zelle
deposit as the rules read it, a person-to-person credit; No keeps the underwriter's Q3 exclusion (`zelle_excluded`).
The analysis computes both readings when it runs (analysis/pipeline.py `Report.zelle_counted`). The stored payload is
the No reading, unchanged; an account whose readings differ carries beside it, under ZELLE_EDITS_KEY, the edits that
turn it into the Yes reading (`reading_edits`). Nothing here re-analyses anything or rewrites a stored record:

* `reading` materialises one reading of a payload (the edits applied and the account's revenue views rebuilt), with no
  display key: the view below, the review writer, the replay and the CLI read it;
* `apply_zelle_view` is the served view: the reading the setting asks for, plus the Zelle figures
  (`metrics.zelle_deposits`) and, under Yes, the row tag (`zelle_deposit`) the dashboard and the downloads read;
* `with_both_readings` is the review writer's wrapper: a decision is validated on the reading the reviewer sees, and
  the latest decision on a posting sets every reading (a reading that refuses it returns to its analysis state).

It reads serialized payloads only, and never imports analysis/serialization.py (which imports it).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

from .payload_shape import ACCOUNTS_KEY, DOCUMENT_SHAPE, PayloadShapeError, assert_payload_shape, payload_accounts
from .revenue import (
    REVENUE_TIERS,
    rebuild_serialized_revenue_views,
    record_serialized_revenue_review,
    revenue_contribution_flags,
)
from .descriptor.lexical import revenue_text
from .true_revenue import ZELLE_POLICY_METHOD, pass_text, zelle_deposit

#: The account key of the stored edits that turn the stored (No) reading into the counted (Yes) one.
ZELLE_EDITS_KEY = "zelle_counted_reading"
#: The served metrics key of the Zelle figures (`zelle_deposit_figures`, with the reading served).
ZELLE_DEPOSITS_KEY = "zelle_deposits"
#: Every display key the view adds to an account's metrics; the row tag is ZELLE_ROW_TAG.
ZELLE_VIEW_KEYS: tuple[str, ...] = (ZELLE_DEPOSITS_KEY,)
#: The served transaction's tag on a Zelle row under Yes: the owner's per-row "flagged 'Zelle'".
ZELLE_ROW_TAG = "zelle_deposit"

_SURFACE = "analysis/zelle_view.py::reading"
_STATUS_SURFACE = "analysis/zelle_view.py::reading_with_status"
_VIEW_SURFACE = "analysis/zelle_view.py::apply_zelle_view"
_WRITER_SURFACE = "analysis/zelle_view.py::with_both_readings"
_SPLIT_SURFACE = "analysis/zelle_view.py::split_readings"
_JOIN_SURFACE = "analysis/zelle_view.py::join_readings"

#: Any list index in a REBUILT_KEYS path.
_ANY_INDEX = "*"
#: The record flags the rebuild derives from a record's state and tier (analysis/revenue.py
#: revenue_contribution_flags), on every posted credit's statement row.
_REBUILT_RECORD_FLAGS = tuple(revenue_contribution_flags(None))
#: The paths analysis/revenue.py `_rebuild_account_revenue_views` assigns from the account's records: the revenue
#: metrics and their evidence lists, the withholding figures it recomputes on a verified or True basis, the detection
#: evidence lists and manual_review, the classifications view, and each statement row's contribution flags. The view
#: rebuilds an account after applying its edits, so `reading_edits` drops every edit under one of these (a test runs the
#: rebuild on samples and pins the set: tests/test_zelle_setting.py).
REBUILT_KEYS: tuple[tuple[str, ...], ...] = (
    *(("metrics", key) for key in (
        "total_posted_credits", "total_posted_credit_count", "verified_revenue_total", "verified_revenue_count",
        "unverified_deposit_total", "unverified_deposit_count", "non_revenue_total", "non_revenue_count",
        "maximum_revenue", "revenue_classified_total", "revenue_classified_count", "revenue_reconciliation_delta",
        "revenue_tiers_sum_to_posted", "revenue_reconciles", "verified_revenue_evidence",
        "unverified_deposit_evidence", "non_revenue_evidence", "true_revenue", "confirmed_true_revenue",
        "confirmed_true_revenue_total", "confirmed_true_revenue_count", "potential_revenue_total",
        "potential_revenue_count", "true_revenue_evidence", "potential_revenue_evidence", "true_revenue_total",
        "true_revenue_count", "counted_flagged_total", "counted_flagged_count", "excluded_pending_review_total",
        "excluded_pending_review_count", "counted_flagged_by_reason", "excluded_pending_review_by_reason",
        "non_revenue_by_reason", "revenue_review_items", "revenue_review_required", "counted_flagged_evidence",
        "excluded_pending_review_evidence", "withholding_denominator_mode", "withholding_denominator_label",
        "eligible_deposit_definition", "eligible_deposits", "withholding_denominator",
        "potential_withholding_denominator", "withholding_rate", "potential_withholding_exposure",
        "withholding_review_required",
        # Audit round 3, R3-B03 (R3-20): the floor's flag.
        "withholding_basis_below_floor",
    )),
    *(("detection", key) for key in (
        "verified_revenue_evidence", "unverified_deposit_evidence", "non_revenue_evidence", "true_revenue_evidence",
        "potential_revenue_evidence", "counted_flagged_evidence", "excluded_pending_review_evidence", "manual_review",
    )),
    # Audit round 3, R3-B03 (R3-13): each potential lender's basis and exposure. `metrics.notes` stays out: the rebuild
    # edits only its basis notes, and `reading_edits` keeps its exactness through its full-list fallback.
    *(("detection", "potential_lenders", _ANY_INDEX, key)
      for key in ("eligible_deposit_denominator", "potential_withholding_exposure")),
    ("classifications",),
    *(("statement", "transactions", _ANY_INDEX, "classification", flag) for flag in _REBUILT_RECORD_FLAGS),
)

#: The tiers a Zelle row's figures name, in the dashboard's order.
_TIER_ORDER = tuple(REVENUE_TIERS)


# --- the edits ---------------------------------------------------------------------------------------------------


def _full_diff(a: object, b: object) -> list[list]:
    """Every edit that turns `a` into `b`: `[path, value]` sets the value at `path` (a list of dict keys and list
    indexes), `[path]` deletes it. Dicts are compared key by key and lists of equal length element by element (a value's
    type counts: 1, 1.0 and True differ); anything else, a dict with a key that is not text included, is replaced whole.
    JSON-safe; the values are copies."""
    edits: list[list] = []
    _diff(a, b, [], edits)
    return edits


def _diff(a: object, b: object, path: list, edits: list[list]) -> None:
    if type(a) is not type(b):
        edits.append([list(path), deepcopy(b)])
        return
    if isinstance(a, dict):
        if not all(isinstance(key, str) for key in (*a, *b)):
            if a != b:
                edits.append([list(path), deepcopy(b)])
            return
        for key in a:
            if key not in b:
                edits.append([[*path, key]])
        for key, value in b.items():
            if key not in a:
                edits.append([[*path, key], deepcopy(value)])
            else:
                _diff(a[key], value, [*path, key], edits)
        return
    if isinstance(a, list):
        if len(a) != len(b):
            edits.append([list(path), deepcopy(b)])
            return
        for index, (left, right) in enumerate(zip(a, b)):
            _diff(left, right, [*path, index], edits)
        return
    if a != b:
        edits.append([list(path), deepcopy(b)])


def apply_reading_edits(a: object, edits: Sequence) -> object:
    """A copy of `a` with `edits` applied in order (`_full_diff`'s form); `a` and `edits` are never mutated. A malformed
    edit or a path `a` does not hold raises (KeyError, IndexError, TypeError or ValueError)."""
    result = deepcopy(a)
    for edit in edits:
        if not isinstance(edit, (list, tuple)) or len(edit) not in (1, 2) or not isinstance(edit[0], (list, tuple)):
            raise ValueError("a Zelle reading edit is [path] or [path, value]")
        path = list(edit[0])
        if not path:
            if len(edit) == 1:
                raise ValueError("a Zelle reading edit cannot delete the whole payload")
            result = deepcopy(edit[1])
            continue
        parent = result
        for step in path[:-1]:
            parent = _step(parent, step)
        last = path[-1]
        if isinstance(parent, dict):
            if not isinstance(last, str):
                raise TypeError("a Zelle reading edit names a dict key that is not text")
            if len(edit) == 1:
                del parent[last]
            else:
                parent[last] = deepcopy(edit[1])
        elif isinstance(parent, list):
            if isinstance(last, bool) or not isinstance(last, int) or not 0 <= last < len(parent) or len(edit) == 1:
                raise IndexError("a Zelle reading edit names a list position the payload does not hold")
            parent[last] = deepcopy(edit[1])
        else:
            raise TypeError("a Zelle reading edit's path runs through a value that is not a dict or a list")
    return result


def _step(node: object, step: object) -> object:
    if isinstance(node, dict):
        if not isinstance(step, str):
            raise TypeError("a Zelle reading edit names a dict key that is not text")
        return node[step]
    if isinstance(node, list):
        if isinstance(step, bool) or not isinstance(step, int) or not 0 <= step < len(node):
            raise IndexError("a Zelle reading edit names a list position the payload does not hold")
        return node[step]
    raise TypeError("a Zelle reading edit's path runs through a value that is not a dict or a list")


def _rebuilt(path: Sequence) -> bool:
    """Whether `path` lies under one of REBUILT_KEYS (an any-index step matching any list position)."""
    for rebuilt in REBUILT_KEYS:
        if len(path) >= len(rebuilt) and all(
            (step == _ANY_INDEX and isinstance(found, int) and not isinstance(found, bool)) or step == found
            for step, found in zip(rebuilt, path)
        ):
            return True
    return False


def reading_edits(a: Mapping, b: Mapping) -> list[list]:
    """The LEAN edits that turn account payload `a` into account payload `b`, both rebuilt: `_full_diff(a, b)` without
    the edits under REBUILT_KEYS, which the rebuild that follows every application recomputes from the records. It is
    exact either way: when `rebuild(apply_reading_edits(a, lean))` is not `b` (a difference the rebuild does not derive,
    such as a withholding figure on the legacy basis), the full list is returned. [] when the two are equal."""
    full = _full_diff(a, b)
    if not full:
        return []
    lean = [edit for edit in full if not _rebuilt(edit[0])]
    if len(lean) == len(full):
        return full
    try:
        rebuilt = rebuild_serialized_revenue_views(apply_reading_edits(a, lean))
    except (KeyError, IndexError, TypeError, ValueError):
        return full
    return lean if rebuilt == b else full


# --- one reading ---------------------------------------------------------------------------------------------------


def _accounts(payload: object, surface: str) -> tuple[str, list[Mapping]] | None:
    try:
        shape = assert_payload_shape(payload, surface=surface)
        return shape, payload_accounts(payload, surface=surface)
    except PayloadShapeError:
        return None


def _with_accounts(payload: Mapping, shape: str, accounts: list) -> object:
    if shape == DOCUMENT_SHAPE:
        return {**payload, ACCOUNTS_KEY: accounts}
    return accounts[0]


def _materialised(account: Mapping, *, counted: bool) -> tuple[Mapping, bool | None]:
    """One account in the reading asked for, without the edits key: `(account, applied)`, where `applied` is None when
    the account carries no edits, True when they were applied (the account copied and its revenue views rebuilt) and
    False when they could not be (a missing path, a wrong type, a rebuild refusal): it is then served as stored."""
    if ZELLE_EDITS_KEY not in account:
        return account, None
    stored = {key: value for key, value in account.items() if key != ZELLE_EDITS_KEY}
    if not counted:
        return stored, None
    edits = account[ZELLE_EDITS_KEY]
    if not isinstance(edits, list):
        return stored, False
    try:
        return rebuild_serialized_revenue_views(apply_reading_edits(stored, edits)), True
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return stored, False


def reading_with_status(payload: object, *, counted: bool) -> tuple[object, list[int]]:
    """`reading`, and the 1-based account numbers (printed order) whose edits could not be applied, each served in its
    stored reading."""
    found = _accounts(payload, _STATUS_SURFACE)
    if found is None:
        return payload, []
    shape, accounts = found
    if not any(ZELLE_EDITS_KEY in account for account in accounts):
        return payload, []
    served: list = []
    unapplied: list[int] = []
    for number, account in enumerate(accounts, start=1):
        account, applied = _materialised(account, counted=counted)
        if applied is False:
            unapplied.append(number)
        served.append(account)
    return _with_accounts(payload, shape, served), unapplied


def reading(payload: object, *, counted: bool) -> object:
    """The payload in one Zelle reading, with no display key: each account loses ZELLE_EDITS_KEY; with `counted`, an
    account's edits are applied and its revenue views rebuilt. An account whose edits cannot be applied stays in its
    stored reading (`reading_with_status` reports it). The input is never mutated, and is returned itself when no
    account carries the key; a payload of neither published shape is returned as it is. Per account: every account is
    materialised in the reading asked for, through payload_accounts."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    if not any(ZELLE_EDITS_KEY in account for account in accounts):
        return payload
    return _with_accounts(payload, shape, [_materialised(account, counted=counted)[0] for account in accounts])


# --- the Zelle rows and their figures ------------------------------------------------------------------------------


def _posted_credits(account: Mapping) -> Iterable[tuple[int, dict, dict]]:
    """(position, transaction, record) of each posted, non-duplicate credit of the account's statement."""
    statement = account.get("statement")
    transactions = statement.get("transactions") if isinstance(statement, Mapping) else None
    for position, transaction in enumerate(transactions if isinstance(transactions, list) else []):
        if not isinstance(transaction, Mapping):
            continue
        record = transaction.get("classification")
        if not isinstance(record, Mapping):
            continue
        try:
            amount = float(transaction.get("amount") or 0.0)
        except (TypeError, ValueError):
            continue
        if amount > 0 and record.get("is_posted") is not False and not record.get("duplicate_of"):
            yield position, transaction, record


def _reads_zelle(record: Mapping) -> bool:
    """The pass's own Zelle reading of a serialized record: the classifier's revenue text of its normalized
    description, read as pass 7 reads it (true_revenue.pass_text, on the record's bank and printed description: TD
    Canada Trust's e-Transfer code dropped; audit round 3, R3-12: PNC's ZEL spelled ZELLE, which reads the same), read
    by true_revenue.zelle_deposit. A description that never prints the letters ZEL (the rail's every form, ZELLE and
    PNC's ZEL FROM / ZEL TO) is read no further: the reader runs on every served account."""
    description = str(record.get("normalized_description") or "")
    if "ZEL" not in description.upper():
        return False
    text = revenue_text(description)
    holder = SimpleNamespace(bank=record.get("bank"), original_description=record.get("original_description"))
    return zelle_deposit(pass_text(holder, text))


def zelle_rows(account: Mapping) -> tuple[list[int], bool]:
    """The positions (in the statement's transactions) of an account's Zelle rows, and whether it is a LEGACY account.

    The Zelle rows are the stored reading's posted, non-duplicate credits whose method is the Zelle policy's
    (ZELLE_POLICY_METHOD): the deposits the policy excluded, and those a reviewer has confirmed since; never a row a
    non-revenue rule decided. An account with none is a legacy account when a posted, non-duplicate credit of it reads
    the Zelle rail (`_reads_zelle`), carries a counted, held or verified tier and is no direction conflict: it was
    analysed before the policy (R2-OW02), its Zelle natively counted, and those credits are its Zelle rows."""
    credits = list(_posted_credits(account))
    policy = [position for position, _transaction, record in credits
              if record.get("revenue_match_method") == ZELLE_POLICY_METHOD]
    if policy:
        return policy, False
    legacy = [
        position for position, _transaction, record in credits
        if record.get("revenue_tier") in ("verified", "counted_flagged", "excluded_pending_review")
        and record.get("revenue_match_method") != "direction_conflict" and _reads_zelle(record)
    ]
    return legacy, bool(legacy)


def zelle_deposit_figures(rows: Iterable[tuple[str | None, float]]) -> dict:
    """The one figure function, over (served tier, amount) pairs: {count, total, by_tier: {tier: {count, total}}}, the
    tiers present in the dashboard's order, money rounded as the non-revenue breakdown's is. Every surface reads its
    parts: in True = verified + counted_flagged, held = excluded_pending_review, out = non_revenue."""
    slots: dict[str, list] = {}
    count = 0
    total = 0.0
    for tier, amount in rows:
        value = float(amount or 0.0)
        count += 1
        total += value
        slot = slots.setdefault(str(tier), [0, 0.0])
        slot[0] += 1
        slot[1] += value
    order = {tier: position for position, tier in enumerate(_TIER_ORDER)}
    return {
        "count": count,
        "total": round(total, 2),
        "by_tier": {
            tier: {"count": slot[0], "total": round(slot[1], 2)}
            for tier, slot in sorted(slots.items(), key=lambda item: (order.get(item[0], len(order)), item[0]))
        },
    }


def record_zelle_figures(stored: Sequence, shown: Sequence) -> dict | None:
    """D2's thin adapter for the CLI (analyze.py, batch.py), over a Report's classification records: the stored (No)
    reading's Zelle policy records (posted, non-duplicate credits of method ZELLE_POLICY_METHOD), their tiers read from
    the reading shown at the same positions, through `zelle_deposit_figures`; None when there is no policy record."""
    rows = [
        (getattr(shown[index], "revenue_tier", None), record.amount)
        for index, record in enumerate(stored)
        if record.amount > 0 and record.is_posted and not record.duplicate_of
        and record.revenue_match_method == ZELLE_POLICY_METHOD
    ]
    return zelle_deposit_figures(rows) if rows else None


def figure_parts(figures: Mapping) -> dict[str, float]:
    """The parts every surface prints (in True = verified + counted, held, out), in money, from Zelle figures."""
    by_tier = figures.get("by_tier") if isinstance(figures.get("by_tier"), Mapping) else {}

    def total(tier: str) -> float:
        slot = by_tier.get(tier)
        return float(slot.get("total") or 0.0) if isinstance(slot, Mapping) else 0.0

    return {"in_true": round(total("verified") + total("counted_flagged"), 2),
            "held": round(total("excluded_pending_review"), 2), "out": round(total("non_revenue"), 2)}


# --- the served view -----------------------------------------------------------------------------------------------


def _served_tier(record: Mapping) -> str | None:
    tier = record.get("revenue_tier")
    return tier if isinstance(tier, str) else None


def _view_account(account: Mapping, *, counted: bool) -> Mapping:
    """One account as `apply_zelle_view` serves it (the input account itself when nothing changes)."""
    positions, legacy = zelle_rows(account)
    served, applied = _materialised(account, counted=counted)
    if not positions:
        return served
    if counted:
        setting_applied = legacy or applied is True
        counted_as_true_revenue = legacy or applied is True
    else:
        setting_applied = not legacy
        counted_as_true_revenue = legacy
    transactions = served["statement"]["transactions"]
    rows = [transactions[position] for position in positions]
    figures = zelle_deposit_figures(
        (_served_tier(transaction["classification"]), transaction.get("amount")) for transaction in rows
    )
    served_key = counted or not setting_applied or any(
        _served_tier(transaction["classification"]) != "non_revenue" for transaction in rows
    )
    if not served_key and not counted:
        return served
    copied = applied is True  # a materialised account is already this view's own copy
    if not copied:
        served = {**served, "statement": {**served["statement"], "transactions": list(transactions)}}
    if served_key:
        served["metrics"] = {
            **(served.get("metrics") or {}),
            ZELLE_DEPOSITS_KEY: {"counted_as_true_revenue": counted_as_true_revenue,
                                 "setting_applied": setting_applied, **figures},
        }
    if counted:
        rows_out = served["statement"]["transactions"]
        for position in positions:
            rows_out[position] = {**rows_out[position], ZELLE_ROW_TAG: True}
    return served


def apply_zelle_view(payload: object, *, counted: bool) -> object:
    """The served copy of a stored analysis in the Zelle reading the setting asks for (`counted`: Yes).

    Copy on write: the input is never mutated, an account it changes is copied, and the input itself is returned when no
    account has a Zelle row or the edits key; a payload of neither published shape is returned as it is. It serves
    `reading(payload, counted=counted)`, and on an account with Zelle rows (`zelle_rows`) it adds
    `metrics.zelle_deposits` = {counted_as_true_revenue, setting_applied, count, total, by_tier}, read from the rows in
    the served reading:

    * Yes: on every account with Zelle rows; each Zelle row's served transaction gains `zelle_deposit: true`;
    * No: only where today's output would misstate where the Zelle money sits: a Zelle row whose served tier is not
      non_revenue (one a reviewer confirmed, or a legacy account's), or `setting_applied` False.

    `counted_as_true_revenue` is the reading served (a legacy account is served as stored, so True there).
    `setting_applied` is False where the reading asked for cannot be served: under Yes, an account with Zelle policy
    rows and no usable edits (analysed between the Zelle policy and the setting, or its edits corrupt); under No, a
    legacy account, whose Zelle stays counted. It never refuses: a malformed document passes untouched."""
    try:
        shape = assert_payload_shape(payload, surface=_VIEW_SURFACE)
        accounts = payload_accounts(payload, surface=_VIEW_SURFACE)
    except PayloadShapeError:
        return payload
    served = [_view_account(account, counted=counted) for account in accounts]
    if all(new is old for new, old in zip(served, accounts)):
        return payload
    return _with_accounts(payload, shape, served)


# --- the two readings for a decision -------------------------------------------------------------------------------


def split_readings(analysis: object) -> tuple[object, object, bool]:
    """Private copies of the stored (No) reading and the counted (Yes) reading of `analysis`, neither carrying the edits
    key, and whether any account carried usable edits. An account whose edits are unusable carries none: its key is
    dropped and both copies hold it as stored."""
    no = reading(deepcopy(analysis), counted=False)
    yes, unapplied = reading_with_status(deepcopy(analysis), counted=True)
    found = _accounts(analysis, _SPLIT_SURFACE)
    carrying = found is not None and any(
        ZELLE_EDITS_KEY in account and number not in unapplied
        for number, account in enumerate(found[1], start=1)
    )
    return no, yes, carrying


def join_readings(no: object, yes: object) -> object:
    """The stored payload of two readings: `no`, each account carrying the edits that turn it into `yes`'s account
    (ZELLE_EDITS_KEY, only where non-empty). Both are rebuilt payloads of one statement."""
    no_found, yes_found = _accounts(no, _JOIN_SURFACE), _accounts(yes, _JOIN_SURFACE)
    if no_found is None or yes_found is None or len(no_found[1]) != len(yes_found[1]):
        return no
    for account, counted in zip(no_found[1], yes_found[1]):
        edits = reading_edits(account, counted)
        if edits:
            account[ZELLE_EDITS_KEY] = edits
    return no


def with_both_readings(
    analysis: object, *, shown: bool, decisions: Sequence[tuple[str, str, int | None]],
) -> object:
    """Write a reviewer's decisions (each `(source_location, decision, account)`, in order) onto a stored analysis, in
    both Zelle readings (spec §10.7; R2-OW17), and return the new stored payload. `analysis` is the caller's copy.

    One `reviewed_at` is taken per call and given to every write in both readings. When no account carries usable
    edits this is today's path exactly: every decision applied in order through record_serialized_revenue_review, which
    checks everything before it writes, then one rebuild (an unusable key is dropped). Otherwise:

    1. no = the stored reading, yes = the counted reading (`split_readings`);
    2. every decision is applied to the reading shown (`shown`: Yes), in order; the first LookupError or ValueError
       propagates and nothing is written (all or nothing, as the batch route is);
    3. each decision is applied to the other reading on its own: the latest decision on a posting sets every reading,
       and a reading that refuses it goes back to its analysis state (a `reset` there; a refused reset means that
       reading never took a decision on the posting, so it already is at its analysis state);
    4. both are rebuilt (a rebuild error propagates, as today);
    5. each account's edits are computed again (`join_readings`) and the No reading is returned with them.

    Per account: each decision names one posting of one account (record_serialized_revenue_review searches every
    account), and each account's edits are its own; a malformed payload takes today's path, whose writer refuses it."""
    reviewed_at = datetime.now(UTC).isoformat()
    try:
        payload_accounts(analysis, surface=_WRITER_SURFACE)
    except PayloadShapeError:
        no, yes, carrying = analysis, analysis, False
    else:
        no, yes, carrying = split_readings(analysis)
    if not carrying:
        for source_location, decision, account in decisions:
            record_serialized_revenue_review(
                no, source_location=source_location, decision=decision, account=account, reviewed_at=reviewed_at,
            )
        return rebuild_serialized_revenue_views(no)
    seen, other = (yes, no) if shown else (no, yes)
    for source_location, decision, account in decisions:
        record_serialized_revenue_review(
            seen, source_location=source_location, decision=decision, account=account, reviewed_at=reviewed_at,
        )
    for source_location, decision, account in decisions:
        try:
            record_serialized_revenue_review(
                other, source_location=source_location, decision=decision, account=account, reviewed_at=reviewed_at,
            )
        except (LookupError, ValueError):
            try:
                record_serialized_revenue_review(
                    other, source_location=source_location, decision="reset", account=account,
                    reviewed_at=reviewed_at,
                )
            except (LookupError, ValueError):
                pass
    rebuild_serialized_revenue_views(no)
    rebuild_serialized_revenue_views(yes)
    return join_readings(no, yes)
