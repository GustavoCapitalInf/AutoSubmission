"""Flagged positions as the owner's Settings present them (lender detection, spec §8.2).

The analysis publishes every flag group (analysis/flag_groups.py): each classification record carries
`flagged_group` and `contributes_to_flagged_totals`, each account's metrics carry `flagged_groups`, and its
detection carries `flagged_positions`. Settings has one checkbox per group, on by default. Unticking one HIDES
that group, on a copy, when an analysis is served; it never moves a row into review or into lender math (D7), and
the stored record is never rewritten, so a change applies to every statement at once, old and new, with no
re-analysis. The NSF basis (analysis/nsf_days.py) is the same kind of step.

A presentation step, so it never refuses: a payload that is not one of the two published shapes
(analysis/payload_shape.py) is returned unchanged, for the readers that refuse it to refuse it.
"""
from __future__ import annotations

import copy
from collections.abc import Mapping

from analysis.flag_groups import FLAG_GROUPS
from analysis.payload_shape import (
    ACCOUNTS_KEY,
    DOCUMENT_SHAPE,
    STATEMENT_KEY,
    PayloadShapeError,
    assert_payload_shape,
    payload_accounts,
)

_SURFACE = "analysis/flagged_view.py::apply_flagged_groups_to_payload"
#: The first classifier major version that writes flag groups (plan contract C4, `CLASSIFICATION_VERSION`).
FLAG_RULES_MAJOR = 5
#: The top-level key that says the stored rows were classified by older lender rules (spec §8.2, D12).
RULES_OUTDATED_KEY = "analysis_rules_outdated"


def enabled_group_keys(enabled: Mapping[str, bool]) -> frozenset[str]:
    """The flag-group keys Settings shows. `enabled` is keyed by `FlagGroup.setting`; a missing key is ticked."""
    return frozenset(group.key for group in FLAG_GROUPS if bool(enabled.get(group.setting, True)))


def _major_version(version: object) -> int | None:
    """The major number of a stored `classification_version` ("4.1" gives 4); None when it cannot be read."""
    if isinstance(version, int) and not isinstance(version, bool):
        return version
    if isinstance(version, str):
        head = version.strip().split(".", 1)[0]
        return int(head) if head.isdigit() else None
    return None


def _rules_outdated(accounts: list[Mapping]) -> bool:
    """Whether any stored record was written by a classifier older than the flag-group rules. Such an analysis
    keeps its stored labels until it is re-analysed (D12); the dashboard says so.

    A record with no `classification_version` (absent or null) predates the field, so it was classified by older
    rules. A version that is present but cannot be read says nothing either way. Rows without a record are skipped."""
    for account in accounts:
        statement = account.get(STATEMENT_KEY)
        rows = statement.get("transactions") if isinstance(statement, Mapping) else None
        for row in rows if isinstance(rows, list) else []:
            classification = row.get("classification") if isinstance(row, Mapping) else None
            if not isinstance(classification, Mapping):
                continue
            version = classification.get("classification_version")
            if version is None:
                return True
            major = _major_version(version)
            if major is not None and major < FLAG_RULES_MAJOR:
                return True
    return False


def _is_shown(group: object, shown: frozenset[str]) -> bool:
    """A group key Settings shows. Anything but a string (a malformed stored value) is never shown."""
    return isinstance(group, str) and group in shown


def _shown_account(account: Mapping, shown: frozenset[str]) -> dict:
    """One account with its ledger tagged and its flag summaries cut to the shown groups, on copies.

    Every structure that changes is deep-copied first: the stored job lives in the job store for the life of the
    process, and the review routes persist whatever it holds (webapp/app.py), so a tag written into it would be
    saved by the next review."""
    result = dict(account)
    statement = result.get(STATEMENT_KEY)
    if isinstance(statement, Mapping) and isinstance(statement.get("transactions"), list):
        transactions = copy.deepcopy(statement["transactions"])
        for row in transactions:
            classification = row.get("classification") if isinstance(row, dict) else None
            if isinstance(classification, dict):
                classification["flag_shown"] = _is_shown(classification.get("flagged_group"), shown)
        result[STATEMENT_KEY] = {**statement, "transactions": transactions}
    metrics = result.get("metrics")
    if isinstance(metrics, Mapping):
        metrics = copy.deepcopy(dict(metrics))
        if isinstance(metrics.get("flagged_groups"), dict):
            metrics["flagged_groups"] = {
                key: value for key, value in metrics["flagged_groups"].items() if _is_shown(key, shown)
            }
        result["metrics"] = metrics
    detection = result.get("detection")
    if isinstance(detection, Mapping):
        detection = copy.deepcopy(dict(detection))
        if isinstance(detection.get("flagged_positions"), list):
            detection["flagged_positions"] = [
                entry for entry in detection["flagged_positions"]
                if isinstance(entry, Mapping) and _is_shown(entry.get("group"), shown)
            ]
        result["detection"] = detection
    return result


def apply_flagged_groups_to_payload(payload: object, *, enabled: Mapping[str, bool]) -> object:
    """A copy of a published analysis payload as Settings shows its flag groups (plan contract C6).

    On every account, the account shape or each account of the document shape:
    * `metrics.flagged_groups` and `detection.flagged_positions` keep only the ticked groups;
    * every classification record in `statement.transactions` gains `flag_shown`: it names a flag group, and that
      group is ticked. The record's `flagged_group` and its contribution flags are kept as stored (D7).

    At the TOP level it sets `analysis_rules_outdated`: True when any record carries no `classification_version`
    (it predates the field) or one whose major version is below the flag-group rules (D12); False when there is
    no record.

    `enabled` is keyed by `FlagGroup.setting`; a missing key counts as ticked. A group key the contract does not
    define is never shown. The input is never mutated."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    shown = enabled_group_keys(enabled)
    outdated = _rules_outdated(accounts)
    if shape == DOCUMENT_SHAPE:
        return {
            **payload,
            ACCOUNTS_KEY: [_shown_account(account, shown) for account in accounts],
            RULES_OUTDATED_KEY: outdated,
        }
    return {**_shown_account(payload, shown), RULES_OUTDATED_KEY: outdated}
