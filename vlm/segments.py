"""Prove the scope of adjacent printed page summaries without rewriting evidence.

Only reviewed transaction-bearing pages participate. Every segment must print
its opening, both direction totals, and both direction counts. The next printed
opening must equal the previous printed opening plus credits minus debits.
Missing intermediate closings may use that next printed opening as an explicitly
attributed boundary; no closing is manufactured from transaction rows.

This proof establishes metadata scope, not ledger correctness. Callers must
reconcile each segment's rows independently and then reconcile the whole ledger.
Identical zero-net boxes need per-page direction-count coverage to distinguish
page summaries from repeated document summaries. Otherwise scope stays unknown.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
import math
import re


SEGMENT_VERSION = 1
SEGMENT_POLICY = "printed_page_summary_chain_v1"
OPENING_OBSERVATION_SOURCE = "stage_a_printed_opening"
OPENING_OBSERVATION_RULE = "unique_explicit_balance_forward_before_transactions_v1"
TOTAL_FIELDS = ("stated_total_credits", "stated_total_debits")
COUNT_FIELDS = ("stated_credit_count", "stated_debit_count")
SUMMARY_FIELDS = TOTAL_FIELDS + COUNT_FIELDS
SCOPED_FIELDS = ("beginning_balance", "ending_balance") + SUMMARY_FIELDS
_REQUIRED = ("beginning_balance",) + SUMMARY_FIELDS


@dataclass(frozen=True)
class PageSegment:
    page: int
    account: dict
    row_count: int
    opening_source: dict
    closing_source: dict


@dataclass(frozen=True)
class SegmentPlan:
    status: str = "not_applicable"
    segments: tuple[PageSegment, ...] = ()
    document_fields: dict = field(default_factory=dict)
    checks: tuple[dict, ...] = ()
    occurrences: tuple[dict, ...] = ()
    strict_balance_pages: tuple[int, ...] = ()
    opening_observations: tuple[dict, ...] = ()

    @property
    def proven(self) -> bool:
        return self.status == "proven"


def _number(value) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _equal(left, right) -> bool:
    a, b = _number(left), _number(right)
    return a is not None and b is not None and a == b


def _field_source(page: int, name: str) -> dict:
    return {"page": page, "field": name, "source": "reviewer"}


def _bearing(merged) -> bool:
    # A cheque picture page (review.picture_page) is never segment evidence, whatever was read from it.
    from vlm.review import picture_page
    return not picture_page(merged) and (bool(merged.rows) or bool(merged.counts.get("unresolved", 0)))


def _count_covered(merged) -> bool:
    if any(row.direction not in ("credit", "debit") for row in merged.rows):
        return False
    return all(_equal(merged.account.get(name), sum(row.direction == direction for row in merged.rows))
               for name, direction in zip(COUNT_FIELDS, ("credit", "debit")))


def _supplement_openings(merges, observations):
    """Validate an explicit source contract; never derive an opening value.

    The caller must bind ``evidence_sha256`` to the exact persisted page-layout
    payload and establish the pinned extraction rule: one explicit balance-
    forward label, one same-row balance amount, before transaction candidates.
    This helper verifies that contract's shape/page/numeric binding. It does
    not read a file or independently assert what any source pixels contain.
    """
    sources = {merged.page: _field_source(merged.page, "beginning_balance") for merged in merges}
    if observations is None:
        return tuple(merges), sources, (), [], [], False
    expected = {"page", "value", "source", "locator", "evidence_sha256", "rule"}
    working = list(merges)
    indexes = {merged.page: index for index, merged in enumerate(merges)}
    evidence, checks, occurrences = [], [], []
    invalid_input = not isinstance(observations, dict)
    if invalid_input:
        checks.append({"code": "segment_opening_observation_invalid", "page": None,
                       "field": "beginning_balance", "ok": False})
        evidence.append({"page": None, "observation": deepcopy(observations), "status": "invalid"})
    for supplied_page, observation in observations.items() if isinstance(observations, dict) else ():
        page = supplied_page if isinstance(supplied_page, int) and not isinstance(supplied_page, bool) else None
        valid = (page in indexes and isinstance(observation, dict) and set(observation) == expected
                 and observation["page"] == page and type(observation["page"]) is int
                 and _number(observation["value"]) is not None
                 and observation["source"] == OPENING_OBSERVATION_SOURCE
                 and observation["rule"] == OPENING_OBSERVATION_RULE
                 and isinstance(observation["locator"], str) and bool(observation["locator"].strip())
                 and isinstance(observation["evidence_sha256"], str)
                 and re.fullmatch(r"[0-9a-f]{64}", observation["evidence_sha256"]) is not None)
        item = {"page": page, "observation": deepcopy(observation), "status": "invalid"}
        evidence.append(item)
        if not valid:
            invalid_input = True
            checks.append({"code": "segment_opening_observation_invalid", "page": page,
                           "field": "beginning_balance", "ok": False})
            continue
        merged = working[indexes[page]]
        reviewed = merged.account.get("beginning_balance")
        if reviewed is not None:
            if _equal(reviewed, observation["value"]):
                item["status"] = "agreed_with_reviewed"
            else:
                item["status"] = "conflict"
                occurrences.append({"code": "anchor_disagreement", "page": page,
                                    "field": "beginning_balance", "source": "metadata"})
                checks.append({"code": "segment_opening_source_conflict", "page": page,
                               "field": "beginning_balance", "ok": False})
        else:
            item["status"] = "selected_when_reviewed_missing"
            account = {**merged.account, "beginning_balance": deepcopy(observation["value"])}
            working[indexes[page]] = replace(merged, account=account)
            sources[page] = {key: deepcopy(value) for key, value in observation.items() if key != "value"}
            sources[page]["field"] = "beginning_balance"
    return tuple(working), sources, tuple(evidence), checks, occurrences, invalid_input


def detect_page_segments(merges, *, opening_observations: dict | None = None) -> SegmentPlan:
    """Return a closed scope proof; unusable or ambiguous evidence never sums.

    ``strict_balance_pages`` prevents the legacy running-balance continuation
    shortcut from excusing a contradictory printed summary chain. ``checks``
    and ``occurrences`` contain only field names, page numbers and closed codes.
    Raw values remain in the caller's ordinary metadata provenance, and in the
    private per-segment account needed for independent reconciliation.

    Optional ``opening_observations`` maps physical page numbers to exactly
    ``page,value,source,locator,evidence_sha256,rule``. Source and rule must equal
    the exported constants. A source observation supplements only a missing
    reviewed opening; disagreements are real conflicts. Original reviewed
    accounts remain unchanged, and all observations survive separately in the
    returned plan, including matching sources not selected as the anchor.
    """
    merges = tuple(merges)
    merges, opening_sources, opening_evidence, checks, occurrences, invalid_input = _supplement_openings(
        merges, opening_observations)
    from vlm.review import picture_page
    selected = [(index, merged) for index, merged in enumerate(merges) if _bearing(merged)]
    def initial(status="not_applicable"):
        return SegmentPlan(status=status, checks=tuple(checks), occurrences=tuple(occurrences),
                           opening_observations=opening_evidence)
    if occurrences:
        return initial("invalid")
    if invalid_input:
        return initial("unproven")
    if len(selected) < 2:
        return initial()
    openings = [_number(merged.account.get("beginning_balance")) for _, merged in selected]
    known_openings = [value for value in openings if value is not None]
    changing = len(set(known_openings)) > 1
    boxes = [all(merged.account.get(name) is not None for name in _REQUIRED)
             for _, merged in selected]
    if not changing and not all(boxes):
        return initial()
    # Without page movement, a nonzero printed net is a repeated document
    # summary, not evidence for summing the same summary once per page.
    if not changing and any(
        not _equal(merged.account.get(TOTAL_FIELDS[0]), merged.account.get(TOTAL_FIELDS[1]))
        for _, merged in selected
    ):
        return initial()
    pages = tuple(merged.page for _, merged in selected)
    strict = pages if changing and any(boxes) else ()

    def check(code, *, page=None, field=None, previous_page=None, ok=False):
        item = {"code": code, "page": page, "ok": ok}
        if field is not None:
            item["field"] = field
        if previous_page is not None:
            item["previous_page"] = previous_page
        checks.append(item)

    def invalid(page, name, code):
        check(code, page=page, field=name)
        item = {"code": "anchor_disagreement", "page": page, "field": name, "source": "metadata"}
        if item not in occurrences:
            occurrences.append(item)

    def stopped(status="unproven"):
        return SegmentPlan(status=status, checks=tuple(checks), occurrences=tuple(occurrences),
                           strict_balance_pages=strict, opening_observations=opening_evidence)

    physical = [merged.page for merged in merges]
    if (any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in physical)
            or physical != sorted(set(physical))):
        check("segment_page_order_unproven")
        return stopped()
    if any(right_index != left_index + 1 or right.page != left.page + 1
           for (left_index, left), (right_index, right) in zip(selected, selected[1:])):
        check("segment_page_gap")
        return stopped()
    selected_indexes = {index for index, _ in selected}
    if any(index not in selected_indexes and not picture_page(merged)
           and any(merged.account.get(name) is not None for name in SCOPED_FIELDS)
           for index, merged in enumerate(merges)):
        check("segment_mixed_scope_unproven")
        return stopped()
    for _, merged in selected:
        if (merged.page_role != "statement_page" or merged.errors or not merged.rows
                or merged.counts.get("unresolved", 0) or merged.metadata_evidence
                or any(item.get("state") == "unresolved" for item in merged.evidence)):
            check("segment_page_unresolved", page=merged.page)
            return stopped()
        for name in _REQUIRED:
            value = _number(merged.account.get(name))
            if value is None or (name != "beginning_balance" and value < 0):
                check("segment_summary_incomplete", page=merged.page, field=name)
                return stopped()
            if name in COUNT_FIELDS and value != value.to_integral_value():
                check("segment_count_invalid", page=merged.page, field=name)
                return stopped()
    if not changing and not all(_count_covered(merged) for _, merged in selected):
        check("segment_zero_net_scope_unproven")
        return stopped()
    final = selected[-1][1]
    final_closing = _number(final.account.get("ending_balance"))
    if final_closing is None:
        check("segment_final_closing_missing", page=final.page, field="ending_balance")
        return stopped()

    endpoints = []
    for index, (_, merged) in enumerate(selected):
        opening = _number(merged.account["beginning_balance"])
        endpoint = opening + _number(merged.account[TOTAL_FIELDS[0]]) - _number(merged.account[TOTAL_FIELDS[1]])
        endpoints.append(endpoint)
        if index + 1 < len(selected):
            following = selected[index + 1][1]
            matched = endpoint == _number(following.account["beginning_balance"])
            if not matched:
                invalid(following.page, "beginning_balance", "segment_opening_chain_mismatch")
            else:
                check("segment_opening_chain", page=following.page, previous_page=merged.page,
                      field="beginning_balance", ok=True)
        elif endpoint != final_closing:
            invalid(merged.page, "ending_balance", "segment_final_closing_mismatch")
    # Closing observations can be page endpoints or repeated document closings;
    # each is classified against independently printed boundaries, never rows.
    closing_sources = []
    for index, (_, merged) in enumerate(selected):
        closing = merged.account.get("ending_balance")
        if closing is not None and _number(closing) not in (endpoints[index], final_closing):
            invalid(merged.page, "ending_balance", "segment_closing_scope_mismatch")
        if _equal(closing, endpoints[index]):
            closing_sources.append(_field_source(merged.page, "ending_balance"))
            check("segment_page_closing", page=merged.page, field="ending_balance", ok=True)
        elif index + 1 < len(selected):
            following = selected[index + 1][1]
            closing_sources.append(deepcopy(opening_sources[following.page]))
            check("segment_document_closing_restatement" if closing is not None else "segment_next_opening_boundary",
                  page=merged.page, field="ending_balance", ok=True)
        else:
            closing_sources.append(_field_source(merged.page, "ending_balance"))
    if occurrences:
        return stopped("invalid")

    document_fields = {"beginning_balance": deepcopy(selected[0][1].account["beginning_balance"]),
                       "ending_balance": deepcopy(final.account["ending_balance"])}
    for name in SUMMARY_FIELDS:
        total = sum((_number(merged.account[name]) for _, merged in selected), Decimal(0))
        value = int(total) if name in COUNT_FIELDS else float(total)
        if isinstance(value, float) and not math.isfinite(value):
            check("segment_total_unrepresentable", field=name)
            return stopped()
        document_fields[name] = value
    segments = []
    page_accounts = {merged.page: merged.account for merged in merges}
    for index, (_, merged) in enumerate(selected):
        account = {name: deepcopy(merged.account[name]) for name in _REQUIRED}
        source = closing_sources[index]
        next_account = page_accounts[source["page"]]
        account["ending_balance"] = deepcopy(next_account[source["field"]])
        segments.append(PageSegment(merged.page, account, len(merged.rows),
                                    deepcopy(opening_sources[merged.page]), source))
    return SegmentPlan("proven", tuple(segments), document_fields, tuple(checks), (), strict, opening_evidence)
