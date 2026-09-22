"""Strict, deterministic review merge. Model decisions never overwrite source evidence.

Row agreement is an uncalibrated observation, not a probability of correctness.
No confidence bands or admission policy are implied by the score here.
"""
from __future__ import annotations

import copy
import math
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.schema import REVIEW_ROW_FIELDS, empty_review, valid_review_row, validate_page_review

ROW_STATES = ("agreed", "corrected", "added", "rejected", "unresolved")
REVIEW_MERGE_VERSION = 4


def _number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def row_record(row: CandidateRow) -> dict:
    return {"date": row.date, "date_text": row.date_text, "description": row.description,
            "amount": _number(row.amount), "direction": row.direction, "balance": _number(row.balance),
            "bbox": list(row.bbox) if row.bbox is not None else None,
            "printed_amount": _number(row.printed_amount)}


def candidate_records(rows) -> list[dict]:
    return [{"candidate_id": f"p{row.page}r{index}", "page": row.page, "locator": row.locator,
             "row": row_record(row)} for index, row in enumerate(rows)]


@dataclass(frozen=True)
class PageReviewMerge:
    page: int
    rows: tuple[CandidateRow, ...]
    evidence: tuple[dict, ...]
    counts: dict[str, int]
    errors: tuple[str, ...]
    account: dict
    daily_balances: tuple[dict, ...]
    page_role: str
    account_numbers_seen: tuple[str, ...] = ()


def _valid_date(value: object) -> bool:
    if value is None:
        return True
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _finite(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _row_errors(row: dict, *, label: str) -> list[str]:
    if not valid_review_row(row):
        return [f"review_row_schema_invalid:{label}"]
    errors: list[str] = []
    if not row["description"].strip():
        errors.append(f"review_empty_description:{label}")
    if not _valid_date(row["date"]):
        errors.append(f"review_invalid_date:{label}")
    if not _finite(row["amount"]) or row["amount"] <= 0:
        errors.append(f"review_invalid_amount:{label}")
    for key in ("balance", "printed_amount"):
        if row[key] is not None and not _finite(row[key]):
            errors.append(f"review_invalid_{key}:{label}")
    printed = row["printed_amount"]
    if printed is not None and (_finite(printed) and _finite(row["amount"])):
        if abs(Decimal(str(printed))) != Decimal(str(row["amount"])) or row["direction"] not in ("credit", "debit"):
            errors.append(f"review_printed_amount_mismatch:{label}")
    box = row["bbox"]
    if box is not None and (len(box) != 4 or any(not _finite(v) for v in box) or
                            not (0 <= box[0] <= box[2] <= 1 and 0 <= box[1] <= box[3] <= 1)):
        errors.append(f"review_invalid_bbox:{label}")
    return errors


def _source_row(record: dict, *, page: int, locator: str) -> CandidateRow:
    return CandidateRow(record["date"], record["date_text"], record["description"], Decimal(str(record["amount"])),
                        record["direction"], Decimal(str(record["balance"])) if record["balance"] is not None else None,
                        page, "stage_b", locator, "column" if record["printed_amount"] is not None else "printed",
                        tuple(record["bbox"]) if record["bbox"] is not None else None,
                        Decimal(str(record["printed_amount"])) if record["printed_amount"] is not None else None)


def _evidence(*, candidate_id: str, state: str, page: int, locator: str, original: dict | None,
              corrected: dict | None, row: dict | None, reason: str,
              observed_description: str | None = None, corrections=()) -> dict:
    provenance = {}
    for field in REVIEW_ROW_FIELDS:
        if row is not None:
            source = "stage_a+stage_b" if original is not None and original[field] == row[field] else "stage_b"
            provenance[field] = {"page": page, "locator": locator, "bbox": row.get("bbox"), "source": source}
    return copy.deepcopy({"candidate_id": candidate_id, "state": state, "page": page, "locator": locator,
                          "bbox": (row or original or {}).get("bbox"), "original": original, "corrected": corrected,
                          "row": row, "reason": reason, "field_provenance": provenance,
                          "observed_description": observed_description, "corrections": list(corrections)})


def merge_review(candidates, payload: object, *, page: int, truncated: bool = False,
                 validation_errors=()) -> PageReviewMerge:
    """Validate complete review coverage before constructing *any* usable page rows.

    Every bad page retains its slot and every proposed row as unresolved evidence.
    The raw model response is separately retained by the calling evidence store.
    """
    candidates = list(candidates)
    records = candidate_records(candidates)
    originals = {record["candidate_id"]: record["row"] for record in records}
    errors: list[str] = list(validation_errors)
    if any(candidate.page != page for candidate in candidates):
        errors.append("review_candidate_page_mismatch")
    if truncated:
        errors.append("review_truncated")
    schema_errors = validate_page_review(payload)
    if schema_errors:
        # Details may contain source values; callers can separately store validator
        # details privately. Public status uses only the closed structural reason.
        errors.append("review_schema_invalid")
        data = empty_review()
    else:
        data = copy.deepcopy(payload)
    reviews = data["reviews"]
    ids = [item["candidate_id"] for item in reviews]
    if len(ids) != len(set(ids)):
        errors.append("review_duplicate_candidate_id")
    if set(ids) - set(originals):
        errors.append("review_unknown_candidate_id")
    if set(originals) - set(ids):
        errors.append("review_missing_candidate_id")
    replacements: dict[str, dict] = {}
    for item in reviews:
        candidate_id = item["candidate_id"]
        original = originals.get(candidate_id)
        observed = item["observed_description"]
        if item["verdict"] == "correct":
            changes = item["corrections"]
            if not changes:
                errors.append("review_correction_missing")
            fields = [change["field"] for change in changes]
            if len(fields) != len(set(fields)):
                errors.append("review_duplicate_correction_field")
            corrected = copy.deepcopy(original) if original is not None else None
            for change in changes:
                field = change["field"]
                if original is None or change["original"] != original[field]:
                    errors.append("review_original_mismatch")
                if corrected is not None:
                    corrected[field] = copy.deepcopy(change["corrected"])
            if corrected is not None:
                replacements[candidate_id] = corrected
                errors.extend(_row_errors(corrected, label=candidate_id))
                # Redundant patches are harmless only beside an actual change.
                # Apply and validate every value first; keep every raw patch in
                # evidence, and let equality determine each field's provenance.
                if changes and corrected == original:
                    errors.append("review_correction_unchanged")
        elif item["corrections"]:
            errors.append("review_unexpected_replacement")
        if item["verdict"] == "confirm" and candidate_id in originals:
            errors.extend(_row_errors(originals[candidate_id], label=candidate_id))
        if item["verdict"] in ("confirm", "correct"):
            effective = replacements.get(candidate_id) if item["verdict"] == "correct" else original
            if observed is None or not observed.strip():
                errors.append("review_description_observation_missing")
            elif effective is not None and observed != effective["description"]:
                errors.append("review_description_observation_mismatch")
        elif observed is not None:
            errors.append("review_unexpected_description_observation")
        if item["verdict"] == "unresolved":
            errors.append("review_unresolved")
    for index, item in enumerate(data["added"]):
        if item["after_candidate_id"] is not None and item["after_candidate_id"] not in originals:
            errors.append("review_unknown_addition_anchor")
        errors.extend(_row_errors(item["row"], label=f"added{index}"))
    for key, value in data["account"].items():
        if key in ("period_start", "period_end") and not _valid_date(value):
            errors.append("review_invalid_account_date")
        if isinstance(value, (int, float)) and not _finite(value):
            errors.append("review_invalid_account_number")
        if key.startswith("stated_") or key == "days_in_period":
            if isinstance(value, (int, float)) and value < 0:
                errors.append("review_negative_source_magnitude")
    for item in data["daily_balances"]:
        if item["date"] is None or not _valid_date(item["date"]) or not _finite(item["balance"]):
            errors.append("review_invalid_daily_balance")
    evidence: list[dict] = []
    rows: list[CandidateRow] = []
    if errors:
        by_id = {item["candidate_id"]: item for item in reviews if ids.count(item["candidate_id"]) == 1}
        for record in records:
            reviewed = by_id.get(record["candidate_id"], {})
            evidence.append(_evidence(candidate_id=record["candidate_id"], state="unresolved", page=page,
                                      locator=record["locator"], original=record["row"],
                                      corrected=replacements.get(record["candidate_id"]) if reviewed else None,
                                      row=None, reason="page_review_invalid",
                                      observed_description=reviewed.get("observed_description"),
                                      corrections=reviewed.get("corrections", ())))
            evidence[-1]["review_verdict"] = reviewed.get("verdict")
        for index, item in enumerate(data["added"]):
            evidence.append(_evidence(candidate_id=f"p{page}a{index}", state="unresolved", page=page,
                                      locator=f"added{index}", original=None, corrected=None,
                                      row=item["row"], reason="page_review_invalid"))
    else:
        by_id = {item["candidate_id"]: item for item in reviews}
        additions: dict[str | None, list[tuple[int, dict]]] = {}
        for index, item in enumerate(data["added"]):
            additions.setdefault(item["after_candidate_id"], []).append((index, item["row"]))

        def add_after(anchor: str | None) -> None:
            for index, item in additions.get(anchor, []):
                locator = f"added{index}"
                rows.append(_source_row(item, page=page, locator=locator))
                evidence.append(_evidence(candidate_id=f"p{page}a{index}", state="added", page=page,
                                          locator=locator, original=None, corrected=None, row=item,
                                          reason="reviewer_only"))

        add_after(None)
        for candidate, record in zip(candidates, records):
            item = by_id[record["candidate_id"]]
            state = {"confirm": "agreed", "correct": "corrected", "reject": "rejected"}[item["verdict"]]
            value = record["row"] if state == "agreed" else replacements.get(record["candidate_id"])
            if state == "agreed":
                rows.append(replace(candidate, source="stage_a+stage_b"))
            elif state == "corrected":
                rows.append(_source_row(value, page=page, locator=candidate.locator))
            evidence.append(_evidence(candidate_id=record["candidate_id"], state=state, page=page,
                                      locator=candidate.locator, original=record["row"],
                                      corrected=replacements.get(record["candidate_id"]),
                                      row=value, reason=item["reason"],
                                      observed_description=item["observed_description"], corrections=item["corrections"]))
            add_after(record["candidate_id"])
    counts = Counter(item["state"] for item in evidence)
    return PageReviewMerge(page, tuple(rows), tuple(evidence), {state: counts[state] for state in ROW_STATES},
                           tuple(dict.fromkeys(errors)), data["account"], tuple(data["daily_balances"]),
                           data["page_role"], tuple(data["account_numbers_seen"]))


def confidence_summary(merges, *, gate_admitted: bool, gate_reasons=()) -> dict:
    merges = list(merges)
    counts = {state: sum(page.counts[state] for page in merges) for state in ROW_STATES}
    total = sum(counts.values())
    ratio = counts["agreed"] / total if total else None
    admitted = gate_admitted and not any(page.errors for page in merges)
    pages = []
    for page in merges:
        page_total = sum(page.counts.values())
        page_ratio = round(page.counts["agreed"] / page_total, 6) if page_total else None
        pages.append({"page": page.page, "counts": dict(page.counts), "agreement_ratio": page_ratio,
                      "score": page_ratio if admitted and page_ratio is not None else 0.0,
                      "provisional": True, "gate_scope": "document", "errors": list(page.errors)})
    return {"provisional": True, "methodology": "review_agreement_v1", "counts": counts,
            "agreement_ratio": round(ratio, 6) if ratio is not None else None,
            "score": round(ratio, 6) if admitted and ratio is not None else 0.0,
            "gate_admitted": admitted, "gate_reasons": list(gate_reasons),
            "page_count": len(merges), "invalid_page_count": sum(bool(page.errors) for page in merges), "pages": pages}
