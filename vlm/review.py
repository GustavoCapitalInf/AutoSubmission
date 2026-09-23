"""Strict, deterministic review merge. Model decisions never overwrite source evidence.

Row agreement is an uncalibrated observation, not a probability of correctness.
No confidence bands or admission policy are implied by the score here.
"""
from __future__ import annotations

import copy
import math
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

import jsonschema

from vlm.assemble import BALANCE_LINE, CandidateRow
from vlm.native_text import contains_words, spaced
from vlm.schema import PAGE_REVIEW_SCHEMA, REVIEW_ROW_FIELDS, empty_review, valid_review_row

ROW_STATES = ("agreed", "corrected", "added", "rejected", "unresolved")
REVIEW_MERGE_VERSION = 5


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
    diagnostics: tuple[dict, ...] = ()
    metadata_evidence: tuple[dict, ...] = ()
    # Set only by mark_ledger_echoes: every kept row repeats a transaction on an earlier ledger page.
    ledger_echo: bool = False


def review_envelope_valid(payload: object, schema: dict = PAGE_REVIEW_SCHEMA) -> bool:
    """Check transport/envelope shape without conflating identified observations.

    Wire schemas stay unchanged. Local validation checks review/addition entries
    separately, and attributable metadata observations separately. Top-level
    keys, page role, notes, review/addition containers and batch sizes retain
    their original schema requirements. Candidate identity coverage is checked
    by the caller before any row may become usable.
    """
    envelope = copy.deepcopy(schema)
    properties = envelope["properties"]
    for name in ("reviews", "added"):
        if name in properties:
            properties[name]["items"] = {}
    for name in ("account", "account_numbers_seen", "daily_balances"):
        if name in properties:
            properties[name] = {}
    return jsonschema.Draft202012Validator(envelope).is_valid(payload)


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
    if not _finite(row["amount"]) or row["amount"] < 0:
        errors.append(f"review_invalid_amount:{label}")
    elif row["amount"] == 0:
        # A zero amount stands only where the row's own print shows it (_settle_zero_amount).
        errors.append(f"review_zero_amount:{label}")
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


# Figures the reviewer reports as printed on the page. With printed evidence (vlm/native_text.py), each is kept
# only if it is printed there; a figure printed nowhere is not evidence and never contradicts the arithmetic.
_PRINTED_AMOUNT_FIELDS = ("beginning_balance", "ending_balance", "stated_total_credits", "stated_total_debits",
                          "stated_service_charge", "stated_interest_paid", "bank_reported_average_balance")
_PRINTED_INTEGER_FIELDS = ("stated_credit_count", "stated_debit_count", "stated_nsf_count", "days_in_period")


def _figure_printed(printed, value) -> bool:
    """A reported money figure is printed on the page: as money, or, a whole non-zero amount, as whole dollars
    with a currency sign ("Average daily balance $1,822"). A bare integer (a day, a page or cheque number) is
    not a money figure."""
    if printed.amount_printed(value):
        return True
    try:
        number = Decimal(str(value))
    except ArithmeticError:
        return False
    return number != 0 and number == number.to_integral_value() and int(abs(number)) in printed.whole_dollars


def _review_metadata(data: dict, *, page: int, printed=None):
    """Quarantine invalid source observations without changing other fields.

    Invalid/missing account fields become unknown individually. Invalid daily
    balance and account-number entries are omitted individually; an undated
    daily balance is unknown and omitted without quarantine. With printed
    evidence, a reported figure or daily balance that is not printed on the
    page is unknown too: omitted with an audit-only diagnostic, never held.
    Raw invalid observations remain private evidence; closed diagnostics
    identify their scope. These are validation decisions, never replacement
    source values or changes to financial gate policy.
    """
    account = empty_review()["account"]
    daily, numbers, diagnostics, evidence = [], [], [], []

    def invalid(scope, raw, codes, *, field=None, index=None, present=True):
        location = {"scope": scope, "page": page}
        if field is not None:
            location["field"] = field
        if index is not None:
            location["index"] = index
        diagnostics.extend({**location, "code": code} for code in dict.fromkeys(codes))
        evidence.append(copy.deepcopy({**location, "raw_value": raw, "present": present,
                                       "validation_errors": list(dict.fromkeys(codes))}))

    raw_account = data["account"]
    properties = PAGE_REVIEW_SCHEMA["properties"]["account"]["properties"]
    if not isinstance(raw_account, dict):
        invalid("account", raw_account, ["review_account_schema_invalid"])
    else:
        for key, schema in properties.items():
            value = raw_account.get(key)
            codes = []
            if key not in raw_account:
                codes.append("review_account_field_missing")
            elif not jsonschema.Draft202012Validator(schema).is_valid(value):
                codes.append("review_account_field_schema_invalid")
            else:
                if key in ("period_start", "period_end") and not _valid_date(value):
                    codes.append("review_invalid_account_date")
                if isinstance(value, (int, float)) and not _finite(value):
                    codes.append("review_invalid_account_number")
                if (key.startswith("stated_") or key == "days_in_period") and isinstance(value, (int, float)) and value < 0:
                    codes.append("review_negative_source_magnitude")
            if codes:
                invalid("account", value, codes, field=key, present=key in raw_account)
            elif printed is not None and value is not None and (
                    (key in _PRINTED_AMOUNT_FIELDS and not _figure_printed(printed, value))
                    or (key in _PRINTED_INTEGER_FIELDS and not printed.integer_printed(value))):
                diagnostics.append({"scope": "account", "page": page, "field": key,
                                    "code": "review_figure_not_printed"})
            else:
                account[key] = copy.deepcopy(value)
        for key in raw_account.keys() - properties.keys():
            invalid("account", {key: raw_account[key]}, ["review_account_unknown_field"], field="unknown")

    raw_daily = data["daily_balances"]
    daily_schema = PAGE_REVIEW_SCHEMA["properties"]["daily_balances"]["items"]
    if not isinstance(raw_daily, list):
        invalid("daily_balances", raw_daily, ["review_daily_balances_schema_invalid"])
    else:
        for index, item in enumerate(raw_daily):
            if not jsonschema.Draft202012Validator(daily_schema).is_valid(item):
                invalid("daily_balances", item, ["review_daily_balance_schema_invalid"], index=index)
            elif item["date"] is None and _finite(item["balance"]):
                # Unread, like a null account field: unknown, not a misreading. It carries no checkable
                # claim (an empty list would pass), so it is omitted with an audit-only diagnostic.
                diagnostics.append({"scope": "daily_balances", "page": page, "index": index,
                                    "code": "review_daily_balance_undated"})
            elif item["date"] is None or not _valid_date(item["date"]) or not _finite(item["balance"]):
                invalid("daily_balances", item, ["review_invalid_daily_balance"], index=index)
            elif printed is not None and not printed.amount_printed(item["balance"]):
                diagnostics.append({"scope": "daily_balances", "page": page, "index": index,
                                    "code": "review_daily_balance_not_printed"})
            else:
                daily.append(copy.deepcopy(item))

    raw_numbers = data["account_numbers_seen"]
    if not isinstance(raw_numbers, list):
        invalid("account_numbers_seen", raw_numbers, ["review_account_numbers_schema_invalid"])
    else:
        for index, item in enumerate(raw_numbers):
            if not isinstance(item, str):
                invalid("account_numbers_seen", item, ["review_account_number_schema_invalid"], index=index)
            else:
                numbers.append(item)
    return account, tuple(daily), tuple(numbers), diagnostics, evidence


def _review_entry(original: dict, item: dict, *, candidate_id: str):
    """Validate one identified verdict; normalize only an irrelevant reject observation."""
    effective = copy.deepcopy(item)
    errors, warnings = [], []
    if effective.get("verdict") == "reject" and effective.get("observed_description") is not None:
        effective["observed_description"] = None
        warnings.append("review_unexpected_description_observation")
    schema = PAGE_REVIEW_SCHEMA["properties"]["reviews"]["items"]
    if not jsonschema.Draft202012Validator(schema).is_valid(effective):
        errors.append("review_entry_schema_invalid")
    verdict = effective.get("verdict")
    changes = effective.get("corrections")
    corrected = None
    if verdict == "correct":
        corrected = copy.deepcopy(original)
        if not isinstance(changes, list) or not changes:
            errors.append("review_correction_missing")
        fields = []
        for change in changes if isinstance(changes, list) else ():
            if not isinstance(change, dict) or change.get("field") not in REVIEW_ROW_FIELDS:
                continue
            field = change["field"]
            fields.append(field)
            if "original" not in change or change["original"] != original[field]:
                errors.append("review_original_mismatch")
            if "corrected" in change:
                corrected[field] = copy.deepcopy(change["corrected"])
                if field == "date_text" and corrected[field] is None:
                    # No date printed on the row's line (a date printed once for the day): the schema's "".
                    corrected[field] = ""
        if len(fields) != len(set(fields)):
            errors.append("review_duplicate_correction_field")
        errors.extend(_row_errors(corrected, label=candidate_id))
        if changes and corrected == original:
            errors.append("review_correction_unchanged")
    elif changes:
        errors.append("review_unexpected_replacement")
    if verdict == "confirm":
        errors.extend(_row_errors(original, label=candidate_id))
    observed = effective.get("observed_description")
    if verdict in ("confirm", "correct"):
        row = corrected if verdict == "correct" else original
        if not isinstance(observed, str) or not observed.strip():
            errors.append("review_description_observation_missing")
        elif spaced(observed) != spaced(row["description"]):
            # Line breaks inside a printed cell are layout: the proposer writes "<br>", the reviewer a newline.
            errors.append("review_description_observation_mismatch")
    elif observed is not None:
        errors.append("review_unexpected_description_observation")
    if verdict == "unresolved":
        errors.append("review_unresolved")
    return effective, corrected, list(dict.fromkeys(errors)), warnings


def _settle_description(original: dict, corrected: dict | None, observed, printed) -> tuple[dict, str] | None:
    """A reviewer that contradicts itself about a description (its correction, or the proposer's reading it
    confirmed, differs from what it says it observed) is settled by the page's text layer, on the lines that
    print the row's own amount (PrintedEvidence.description_printed_near): the reading printed there wins, or,
    when several are printed there, the one that contains every other printed reading (a fragment is printed
    inside the full text). No text layer, or no single winner: None, and the row stays unresolved. Every
    other field keeps the reviewer's verdict. Returns (row, which reading won)."""
    readings = [("proposer", original["description"])]
    if corrected is not None:
        readings.append(("reviewer_correction", corrected["description"]))
    readings.append(("reviewer_observation", observed))
    readings = [(label, text) for label, text in readings if isinstance(text, str) and text.strip()]
    # Only the row's own print can settle it: a reading printed elsewhere on the page (another row, a heading)
    # is not this row's print, and a row whose amount several rows print is told apart by its printed date.
    row = corrected if corrected is not None else original
    found = [printed.description_printed_near(text, row.get("amount"), row.get("date_text"), row.get("balance"))
             for _, text in readings]
    if any(flag is None for flag in found):
        return None
    printed_texts = {spaced(text) for (_, text), flag in zip(readings, found) if flag}
    # A fragment is printed inside the full text as whole words: "123" is not part of "1234".
    fullest = [text for text in printed_texts
               if all(contains_words(text.split(), other.split()) for other in printed_texts)]
    if len(fullest) != 1:
        return None
    label, text = next((label, text) for label, text in readings if spaced(text) == fullest[0])
    row = {**(corrected if corrected is not None else original), "description": text}
    return (row, label) if not _row_errors(row, label="settled") else None


def _unchanged_reading_printed(row: dict, observed, printed) -> bool:
    """Whether the reviewer observed exactly the row's reading and the row's own lines print it
    (PrintedEvidence.description_printed_near): a correction that changes nothing then confirms it."""
    return (isinstance(observed, str) and spaced(observed) == spaced(row["description"])
            and printed.description_printed_near(row["description"], row.get("amount"), row.get("date_text"),
                                                 row.get("balance")) is True)


def _settle_zero_amount(row, codes: list[str], printed) -> tuple[list[str], bool]:
    """A zero amount is a row the page prints with 0.00 ("AutoPay ... 0.00", a payment of nothing): its own
    text-layer line prints a zero amount beside its words (PrintedEvidence.zero_amount_printed_for), and then it
    is a row like any other. Returns the codes without the zero-amount code when printed so, and whether the text
    layer shows no such line: a line printed without an amount (a cheque listed without one, posted elsewhere),
    which is no transaction. Without a text layer the code stays."""
    zero = [code for code in codes if code.startswith("review_zero_amount:")]
    if not zero or printed is None or not isinstance(row, dict):
        return codes, False
    shown = printed.zero_amount_printed_for(row.get("description"), row.get("date_text"))
    if shown:
        return [code for code in codes if code not in zero], False
    return codes, shown is False


def _ground_balances(rows, evidence, diagnostics, printed, *, page: int) -> list:
    """A running balance the reading puts on a row stands only if the row's own print carries it
    (PrintedEvidence.balance_printed_for): a day's closing balance printed on the day's last row, attached to an
    earlier row of the day, is the other row's. Dropped (the row keeps its amount, and the balance walk skips
    it), with an audit-only diagnostic; where the text layer cannot locate the row, nothing changes."""
    grounded = []
    for row in rows:
        if row.balance is not None and printed.balance_printed_for(row.amount, row.balance, row.date_text) is False:
            row = replace(row, balance=None)
            diagnostics.append({"scope": "row", "page": page, "locator": row.locator,
                                "code": "review_balance_not_printed_on_row"})
            for item in evidence:
                if item["locator"] == row.locator:
                    item["balance_dropped"] = True
        grounded.append(row)
    return grounded


def merge_review(candidates, payload: object, *, page: int, truncated: bool = False,
                 validation_errors=(), candidate_validation_errors=None, printed=None) -> PageReviewMerge:
    """Keep usable peers while isolating attributable row/metadata failures.

    ``errors`` contains fatal response/coverage/source-page failures only. A
    malformed identified entry or semantic mismatch is unresolved on that row;
    its raw review and attempted correction remain evidence. Fatal envelopes,
    missing/duplicate/unknown IDs, non-stop responses and explicit page errors
    still prevent every row from becoming usable. Candidate source errors hold
    confirm/correct rows only: a valid reviewer rejection remains a rejection.

    ``printed`` (vlm.native_text.PrintedEvidence) is what the page shows in print from sources other than the
    reviewer. With it, a description the reviewer contradicts itself about is settled by the text layer
    (_settle_description), and reported figures not printed on the page are dropped (_review_metadata).
    """
    candidates = list(candidates)
    records = candidate_records(candidates)
    originals = {record["candidate_id"]: record["row"] for record in records}
    errors: list[str] = list(validation_errors)
    if any(candidate.page != page for candidate in candidates):
        errors.append("review_candidate_page_mismatch")
    if truncated:
        errors.append("review_truncated")
    source_errors = candidate_validation_errors or {}
    if set(source_errors) - set(originals):
        errors.append("review_source_candidate_unknown")
    if not review_envelope_valid(payload):
        errors.append("review_schema_invalid")
        data = empty_review()
    else:
        data = copy.deepcopy(payload)
    reviews = data["reviews"]
    identified = [item for item in reviews if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)]
    if len(identified) != len(reviews):
        errors.append("review_schema_invalid")
    ids = [item["candidate_id"] for item in identified]
    if len(ids) != len(set(ids)):
        errors.append("review_duplicate_candidate_id")
    if set(ids) - set(originals):
        errors.append("review_unknown_candidate_id")
    if set(originals) - set(ids):
        errors.append("review_missing_candidate_id")
    by_id = {item["candidate_id"]: item for item in identified if ids.count(item["candidate_id"]) == 1}
    checked = {}
    diagnostics = []
    for record in records:
        candidate_id = record["candidate_id"]
        item = by_id.get(candidate_id)
        if item is None:
            continue
        effective, corrected, row_errors, warnings = _review_entry(record["row"], item, candidate_id=candidate_id)
        row_errors, _ = _settle_zero_amount(corrected if corrected is not None else record["row"], row_errors, printed)
        inherited = list(dict.fromkeys(source_errors.get(candidate_id, ())))
        checked[candidate_id] = (effective, corrected, row_errors, warnings, inherited)
        diagnostics.extend({"scope": "row", "page": page, "candidate_id": candidate_id, "code": code}
                           for code in dict.fromkeys((*row_errors, *inherited)))
        diagnostics.extend({"scope": "row_warning", "page": page, "candidate_id": candidate_id, "code": code}
                           for code in warnings)

    additions = []
    unprinted_zero = set()  # additions the page prints without any amount: no transaction
    addition_schema = PAGE_REVIEW_SCHEMA["properties"]["added"]["items"]
    for index, item in enumerate(data["added"]):
        codes = []
        if isinstance(item, dict) and isinstance(item.get("row"), dict) and item["row"].get("date_text", "") is None:
            # A reviewer writes null where the row prints no date (a date printed once for the day): "".
            item = {**item, "row": {**item["row"], "date_text": ""}}
        if not jsonschema.Draft202012Validator(addition_schema).is_valid(item):
            codes.append("review_addition_schema_invalid")
        else:
            if item["after_candidate_id"] is not None and item["after_candidate_id"] not in originals:
                codes.append("review_unknown_addition_anchor")
            row_codes, unprinted = _settle_zero_amount(item["row"], _row_errors(item["row"], label=f"added{index}"),
                                                       printed)
            if unprinted and row_codes == [f"review_zero_amount:added{index}"]:
                unprinted_zero.add(index)
                row_codes = []
            codes.extend(row_codes)
        additions.append((index, item, list(dict.fromkeys(codes))))
        diagnostics.extend({"scope": "row", "page": page, "candidate_id": f"p{page}a{index}", "code": code}
                           for code in dict.fromkeys(codes))
    account, daily, numbers, metadata_diagnostics, metadata_evidence = _review_metadata(data, page=page,
                                                                                        printed=printed)
    diagnostics.extend(metadata_diagnostics)
    fatal = bool(errors)
    evidence, rows = [], []
    anchored = {}
    for index, item, codes in additions:
        if isinstance(item, dict) and isinstance(item.get("after_candidate_id"), (str, type(None))):
            anchor = item.get("after_candidate_id")
            if anchor is None or anchor in originals:
                anchored.setdefault(anchor, []).append((index, item, codes))

    emitted_additions = set()

    def add_after(anchor):
        for index, item, codes in anchored.get(anchor, ()):
            append_addition(index, item, codes)

    def append_addition(index, item, codes):
        if index in emitted_additions:
            return
        emitted_additions.add(index)
        usable = not fatal and not codes
        row = item.get("row") if isinstance(item, dict) else None
        locator = f"added{index}"
        # Stage A never proposes a printed balance line; a reviewer addition of one is not a transaction either,
        # nor is a line the page prints without any amount that the reviewer added at 0.00.
        balance_line = usable and bool(BALANCE_LINE.match(str(row.get("description") or "").strip()))
        no_amount = usable and index in unprinted_zero
        if usable and not balance_line and not no_amount:
            rows.append(_source_row(row, page=page, locator=locator))
        # A malformed proposed row remains in raw_addition, without implying
        # that it has valid field provenance or can enter the row ledger.
        evidence.append(_evidence(candidate_id=f"p{page}a{index}",
                                  state="rejected" if balance_line or no_amount else "added" if usable else "unresolved",
                                  page=page, locator=locator, original=None, corrected=None,
                                  row=row if valid_review_row(row) and not balance_line and not no_amount else None,
                                  reason="addition_is_balance_line" if balance_line
                                  else "addition_amount_not_printed" if no_amount else "reviewer_only" if usable
                                  else "page_review_invalid" if fatal else "row_review_invalid"))
        evidence[-1].update(validation_errors=list(codes), validation_warnings=[],
                            raw_addition=copy.deepcopy(item))

    add_after(None)
    for candidate, record in zip(candidates, records):
        candidate_id = record["candidate_id"]
        checked_item = checked.get(candidate_id)
        raw_item = by_id.get(candidate_id)
        effective, corrected, row_errors, warnings, inherited = checked_item or (
            {}, None, [], [], list(dict.fromkeys(source_errors.get(candidate_id, ()))))
        verdict = effective.get("verdict")
        settled, resolved = None, "review_description_observation_mismatch"
        if (printed is not None and not fatal and checked_item is not None and not inherited
                and row_errors == ["review_description_observation_mismatch"] and verdict in ("confirm", "correct")):
            settled = _settle_description(record["row"], corrected if verdict == "correct" else None,
                                          effective.get("observed_description"), printed)
        elif (printed is not None and not fatal and checked_item is not None and not inherited
                and row_errors == ["review_correction_unchanged"] and verdict == "correct"
                and _unchanged_reading_printed(record["row"], effective.get("observed_description"), printed)):
            # A "correction" that changes nothing, of a reading the reviewer observed and the row's own lines print,
            # confirms that reading.
            settled, resolved = (record["row"], "proposer"), "review_correction_unchanged"
        if settled is not None:
            row_errors = []
            verdict = "confirm" if settled[0] == record["row"] else "correct"
            corrected = None if verdict == "confirm" else settled[0]
        usable = not fatal and not row_errors and (not inherited or verdict == "reject") and checked_item is not None
        state = {"confirm": "agreed", "correct": "corrected", "reject": "rejected"}.get(verdict, "unresolved") if usable else "unresolved"
        value = record["row"] if state == "agreed" else corrected if state == "corrected" else None
        if state == "agreed":
            rows.append(replace(candidate, source="stage_a+stage_b"))
        elif state == "corrected":
            rows.append(replace(_source_row(value, page=page, locator=candidate.locator),
                                description_label=candidate.description_label,
                                side_by_side=candidate.side_by_side))
        raw_changes = raw_item.get("corrections") if raw_item is not None else ()
        evidence.append(_evidence(candidate_id=candidate_id, state=state, page=page, locator=record["locator"],
                                  original=record["row"], corrected=corrected, row=value,
                                  reason="page_review_invalid" if fatal else "row_review_invalid" if state == "unresolved" else effective.get("reason", ""),
                                  observed_description=effective.get("observed_description"),
                                  corrections=raw_changes if isinstance(raw_changes, list) else ()))
        evidence[-1].update(review_verdict=raw_item.get("verdict") if raw_item is not None else None,
                            validation_errors=list(dict.fromkeys((*row_errors, *inherited))),
                            validation_warnings=list(warnings), raw_review=copy.deepcopy(raw_item),
                            raw_observed_description=copy.deepcopy(raw_item.get("observed_description")) if raw_item is not None else None)
        if settled is not None:
            evidence[-1]["resolution"] = {"method": "text_layer", "chosen": settled[1], "resolved_errors": [resolved]}
        add_after(candidate_id)
    # Invalid or missing anchors cannot silently discard an addition. Their
    # own evidence stays unresolved after the ordered candidate sequence.
    for index, item, codes in additions:
        append_addition(index, item, codes)
    if printed is not None:
        rows = _ground_balances(rows, evidence, diagnostics, printed, page=page)
    counts = Counter(item["state"] for item in evidence)
    return PageReviewMerge(page, tuple(rows), tuple(evidence), {state: counts[state] for state in ROW_STATES},
                           tuple(dict.fromkeys(errors)), account, daily, data["page_role"], numbers,
                           tuple(diagnostics), tuple(metadata_evidence))


def _summary_figures(merged) -> bool:
    from vlm.segments import SCOPED_FIELDS
    return any(merged.account.get(name) is not None for name in SCOPED_FIELDS)


# Printed statement figures beyond the summary box; no picture of a cheque or deposit slip carries them.
_STATEMENT_FIGURES = ("stated_service_charge", "stated_interest_paid", "stated_nsf_count", "days_in_period",
                      "bank_reported_average_balance")


def _statement_evidence(merged) -> bool:
    """What no picture of a cheque or deposit slip carries: a failed review, a statement summary figure
    (opening, closing, totals or counts) or another printed statement figure, or a daily-balance table,
    read, quarantined or read without dates. A money figure or daily balance the reviewer reported but the
    page does not print still says the reviewer saw a statement page, so it counts too; a count or a number of
    days it reported without the page printing it does not (a reviewer repeats those from other pages, or
    writes 0 for none). Repeated header details such as bank, account or period do not count."""
    return (bool(merged.errors) or _summary_figures(merged)
            or any(merged.account.get(name) is not None for name in _STATEMENT_FIGURES)
            or bool(merged.daily_balances)
            or any(item.get("scope") == "daily_balances" for item in merged.metadata_evidence)
            or any(item.get("code") in ("review_daily_balance_undated", "review_daily_balance_not_printed")
                   or (item.get("code") == "review_figure_not_printed" and item.get("field") in _PRINTED_AMOUNT_FIELDS)
                   for item in merged.diagnostics))


def picture_page(merged) -> bool:
    """Owner ruling, 2026-09-22 ("dont hold cheque picture pages"): a cheque picture page shows pictures of
    documents whose transactions are listed elsewhere. It contributes no ledger rows, no compared metadata
    and no text for a bank reader, and nothing on it holds the statement.

    It carries no statement evidence (a valid review, no summary figure, no daily-balance table: a page that
    prints them is a statement page whatever it was called, and treating it as pictures would silently drop
    its rows from a chain that then proves over the other pages), and it is either
    * a page whose every kept row repeats an earlier ledger transaction (mark_ledger_echoes), whatever the
      reviewer called it; or
    * a page the reviewer labelled cheque_images on which it kept no row at all.
    A labelled page that kept rows which do NOT all repeat earlier transactions is not pictures: those rows
    are new to the statement, so they enter the ledger and the arithmetic judges them."""
    if _statement_evidence(merged):
        return False
    return merged.ledger_echo or (merged.page_role == "cheque_images" and not merged.rows)


# Two rows repeating earlier transactions by chance is implausible for a real page; one is not, so a page the
# reviewer did not label cheque_images needs at least two.
_UNLABELLED_ECHO_MIN_ROWS = 2


def _repeat_key(row, window=None) -> tuple | None:
    """(amount, direction, date) of a row, or None when it cannot be compared: no finite amount, or no date. The
    date is the row's ISO date, else the one date its printed month and day can mean inside the statement period
    (`window`; a row the reviewer confirmed as printed, "04/27", leaves the year to the date resolver). An
    undated row cannot be shown to repeat anything."""
    try:
        amount = abs(Decimal(str(row.amount))).quantize(Decimal("0.01"))
    except (ArithmeticError, TypeError, ValueError):
        return None
    try:
        when = date.fromisoformat(row.date)
    except (TypeError, ValueError):
        from vlm.dates import _possibilities
        readings = _possibilities(row.date_text, *window) if window is not None and row.date_text else ()
        if len(readings) != 1:
            return None
        when = date.fromisoformat(readings[0])
    return amount, row.direction, when


def _repeats(picture: tuple, posting: tuple) -> bool:
    """A picture repeats a ledger posting of the same amount, the same direction when the picture's is known,
    posted on or after the picture's date (a cheque is written before it clears; a real later page lists
    later postings, which is what separates it from pictures)."""
    amount, direction, when = picture
    return (amount == posting[0] and (direction not in ("credit", "debit") or direction == posting[1])
            and posting[2] >= when)


def _assign(pictures: list, postings: list) -> list | None:
    """One-to-one assignment of every picture to a distinct repeating posting (augmenting paths), as the
    posting indices in picture order, or None when none exists."""
    owner: dict[int, int] = {}

    def place(index: int, seen: set) -> bool:
        for candidate, posting in enumerate(postings):
            if candidate in seen or not _repeats(pictures[index], posting):
                continue
            seen.add(candidate)
            if candidate not in owner or place(owner[candidate], seen):
                owner[candidate] = index
                return True
        return False

    if not all(place(index, set()) for index in range(len(pictures))):
        return None
    return sorted(owner, key=owner.get)


def _period_window(merges) -> tuple | None:
    """The narrowest statement period the pages printed: the latest period_start and the earliest period_end
    any page with a valid review read, each bound from whichever pages printed it. None when either bound
    is missing or they conflict: a wrong, wide period read on one page never widens it past what another
    page printed, and a conflict allows no echo."""
    def bound(field):
        found = []
        for merged in merges:
            if merged.errors:
                continue
            try:
                found.append(date.fromisoformat(merged.account.get(field)))
            except (TypeError, ValueError):
                continue
        return found

    starts, ends = bound("period_start"), bound("period_end")
    if not starts or not ends or max(starts) > min(ends):
        return None
    return max(starts), min(ends)


def _directed(keys: list) -> list:
    """An unknown direction takes the page's one known direction, so a row whose direction the reviewer did
    not read still has to repeat a posting in that direction (it cannot hide the other side of a zero net).
    With no known direction, or two, keys are unchanged and _plausible_pictures refuses them."""
    known = {key[1] for key in keys if key[1] in ("credit", "debit")}
    if len(known) != 1:
        return keys
    direction = known.pop()
    return [(amount, direction if side not in ("credit", "debit") else side, when) for amount, side, when in keys]


def _plausible_pictures(keys: list, period: tuple | None) -> bool:
    """What a page of pictures looks like beyond its dates: every row dated inside the statement period
    (_period_window, with the gate's grace; a real page misdated outside it is the period check's to
    refuse, never absorbed), and one direction: enough rows (min(_UNLABELLED_ECHO_MIN_ROWS, rows)) name it,
    and none names the other. A page of pictured cheques is debits and a page of deposit slips credits; a
    real page that nets to zero, the case the arithmetic cannot see, needs both."""
    from vlm.gate import PERIOD_GRACE_DAYS
    if period is None:
        return False
    lower, upper = (period[0] - timedelta(days=PERIOD_GRACE_DAYS), period[1] + timedelta(days=PERIOD_GRACE_DAYS))
    known = [key[1] for key in keys if key[1] in ("credit", "debit")]
    return (all(lower <= key[2] <= upper for key in keys) and len(set(known)) <= 1
            and len(known) >= min(_UNLABELLED_ECHO_MIN_ROWS, len(keys)))


def _oldest_first(dates: list) -> bool:
    """The listing so far reads oldest first: strictly more ascending than descending date steps (the gate's
    orient rule, with a tie undetermined)."""
    up = sum(1 for a, b in zip(dates, dates[1:]) if b > a)
    down = sum(1 for a, b in zip(dates, dates[1:]) if b < a)
    return up > down


def mark_ledger_echoes(merges) -> list:
    """Mark pages whose every kept row repeats (_repeats) a distinct transaction on an EARLIER ledger page not
    already claimed by another marked page. Cheque and deposit-slip pictures follow the listing they
    illustrate. The page must carry no statement evidence and no kept row may print a running balance (a
    pictured cheque has neither); an unlabelled page needs _UNLABELLED_ECHO_MIN_ROWS rows. Returns new merges
    in page order; inputs are never mutated.

    Why a real page is not taken for pictures: in an oldest-first listing its rows post on or after the
    earlier pages' rows, so they cannot be shown to repeat them, and a statement with running balances
    prints one on each of them. Hence:
    * the earlier listing must read oldest first; a newest-first listing inverts the date test, so it
      allows no echo, and neither does an undetermined order;
    * at least min(_UNLABELLED_ECHO_MIN_ROWS, rows) rows must be dated strictly before the latest earlier
      posting (a cheque is written before it clears); a continuation page repeating same-day postings at a
      page break has none;
    * only pages on which the review kept rows the proposer read are the ledger, so pictures printed before
      the listing, added by the reviewer alone and not recognized, are not a ledger for the real listing to
      repeat;
    * the rows are plausible pictures (_plausible_pictures): inside the narrowest period any page printed,
      and of one direction, an unknown direction taking the page's (_directed). Sectioned statements
      restart dates, so the date tests alone cannot separate a later section's real rows from pictures;
    * a page whose every row repeats the listing uses up the postings it repeats, whether or not it passes
      the other tests, and is never a listing for later pages: otherwise a later real page could repeat
      those postings in its place while this page's duplicate rows made the sum pass.
    Only the whole-document arithmetic would otherwise judge a dropped page, and it cannot see a page whose
    rows net to zero or one at the end of a per-page summary chain whose box was not read."""
    window = _period_window(merges)
    postings, dates, marked = [], [], []
    for merged in merges:
        # A page's own rows are pictures only on the dates they carry; the statement period places only a
        # ledger posting that was confirmed with its printed month and day (a real cheque section listed by
        # number must not become pictures of earlier debits of the same amounts).
        raw = [_repeat_key(row) for row in merged.rows]
        keys = _directed(raw) if raw and None not in raw else raw
        claimed = _assign(keys, postings) if keys and None not in keys else None
        if claimed is not None:
            postings = [posting for index, posting in enumerate(postings) if index not in set(claimed)]
            if (not _statement_evidence(merged) and all(row.balance is None for row in merged.rows)
                    and (merged.page_role == "cheque_images" or len(keys) >= _UNLABELLED_ECHO_MIN_ROWS)
                    and _oldest_first(dates)
                    and sum(key[2] < max(dates) for key in keys) >= min(_UNLABELLED_ECHO_MIN_ROWS, len(keys))
                    and _plausible_pictures(raw, window)):
                merged = replace(merged, ledger_echo=True)
        elif (not picture_page(merged)
              and (merged.counts.get("agreed", 0) or merged.counts.get("corrected", 0))):
            placed = [_repeat_key(row, window) for row in merged.rows]
            placed = _directed(placed) if placed and None not in placed else placed
            ledger = [key for key in placed if key is not None]
            postings.extend(ledger)
            dates.extend(key[2] for key in ledger)
        marked.append(merged)
    return marked


def confidence_summary(merges, *, gate_admitted: bool, gate_reasons=()) -> dict:
    merges = list(merges)
    ledger_pages = [page for page in merges if not picture_page(page)]
    counts = {state: sum(page.counts.get(state, 0) for page in ledger_pages) for state in ROW_STATES}
    total = sum(counts.values())
    ratio = counts["agreed"] / total if total else None
    admitted = gate_admitted and not any(
        page.errors or page.counts.get("unresolved", 0) or page.metadata_evidence for page in ledger_pages)
    pages = []
    for page in merges:
        page_total = sum(page.counts.values())
        page_ratio = round(page.counts.get("agreed", 0) / page_total, 6) if page_total else None
        pages.append({"page": page.page, "counts": dict(page.counts), "agreement_ratio": page_ratio,
                      "score": page_ratio if admitted and page_ratio is not None else 0.0,
                      "provisional": True, "gate_scope": "document", "errors": list(page.errors),
                      "cheque_pictures": picture_page(page)})
    return {"provisional": True, "methodology": "review_agreement_v1", "counts": counts,
            "agreement_ratio": round(ratio, 6) if ratio is not None else None,
            "score": round(ratio, 6) if admitted and ratio is not None else 0.0,
            "gate_admitted": admitted, "gate_reasons": list(gate_reasons),
            "page_count": len(merges), "invalid_page_count": sum(bool(page.errors) for page in merges), "pages": pages}
