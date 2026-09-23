"""Statement confidence (evidence_v2): how much of a visual reading was independently verified.

An admitted statement has passed every arithmetic check the gate runs (beginning plus rows equals ending,
dates in period, order, duplicates, and whatever totals, counts and running balances the page printed). That
earns half the score. The other half is the mean of the independent evidence that applies to it:

* stated_totals        the printed credit and debit totals were present and reconciled (1, 0.5 or 0);
* stated_counts        the printed credit and debit counts were present and matched (1, 0.5 or 0);
* amounts_printed      share of rows whose amount the PDF's own text layer prints (not applicable to scanned
                       pages: the proposer's reading is where the rows came from, so it cannot corroborate them);
* two_readers          share of rows two independent sources agree on: confirmed by the reviewer, settled by
                       the text layer on the row's own lines, a correction that only fills a field the proposer
                       left empty (a year), or a correction the text layer prints on the row's lines; other
                       corrections count half and reviewer-only rows zero;
* descriptions_in_text_layer   share of rows whose description's words the text layer prints on the lines of
                       the row's own amount (not applicable to scanned pages);
* running_balances     share of rows a printed balance proves (its own row and the earlier rows of that day
                       in the listing), counted only when the balances continued without a break (not
                       applicable when none is printed).

A held statement scores below one half, whatever its evidence. The score is verification coverage, not a
calibrated probability: it says how much was checked, not how often such readings are right.
"""
from __future__ import annotations

CONFIDENCE_METHOD = "evidence_v2"
BANDS = ((0.95, "very_high"), (0.85, "high"), (0.70, "moderate"), (0.0, "low"))


def _printed(printed_pages, page):
    return printed_pages[page - 1] if 0 < page <= len(printed_pages) else None


def _bare_description(row) -> str:
    """The description as printed: a cheque label applied after review is not text the page prints there."""
    label = getattr(row, "description_label", None)
    if label and row.description.startswith(label + " "):
        return row.description[len(label) + 1:]
    return row.description


# A field the proposer may leave empty for want of context the row does not print: the ISO date of a row that
# prints no year. Filling it in completes the proposer's reading rather than contradicting it.
_COMPLETABLE_FIELDS = frozenset({"date"})


def completion_only(item: dict) -> bool:
    """Whether a reviewer correction (a row_evidence item) only filled fields the proposer left empty, changing
    nothing the proposer read."""
    original, corrected = item.get("original"), item.get("corrected")
    if item.get("state") != "corrected" or not isinstance(original, dict) or not isinstance(corrected, dict):
        return False
    changed = [field for field in corrected if corrected.get(field) != original.get(field)]
    return bool(changed) and all(field in _COMPLETABLE_FIELDS and original.get(field) is None for field in changed)


def _rows_proven_by_balances(rows) -> int:
    """Rows a printed balance proves: within each run of same-date rows in listing order, every row up to and
    including the last one that prints a balance."""
    proven, run = 0, []
    for row in [*rows, None]:
        if run and (row is None or row.date != run[-1].date):
            last = max((index for index, item in enumerate(run) if item.balance is not None), default=-1)
            proven += last + 1
            run = []
        if row is not None:
            run.append(row)
    return proven


def statement_confidence(*, admitted: bool, checks: dict, account: dict, rows, row_states: dict,
                         printed_pages, reasons=()) -> dict:
    """row_states maps (page, locator) to (state, resolution method, whether a correction only filled fields
    the proposer left empty)."""
    rows = list(rows)
    checks = checks or {}
    components: dict[str, float | None] = {}
    if checks.get("summary_ok") is True:
        present = sum(account.get(field) is not None for field in ("stated_total_credits", "stated_total_debits"))
        components["stated_totals"] = present / 2
    else:
        components["stated_totals"] = 0.0
    components["stated_counts"] = sum(checks.get(name) is True for name in
                                      ("credit_count_matches", "debit_count_matches")) / 2

    evidence = {"rows": len(rows), "reviewer_only_rows": 0, "corrected_rows": 0, "completion_only_corrections": 0,
                "settled_by_text_layer": 0, "amounts_in_text_layer": 0, "text_layer_rows": 0,
                "descriptions_in_text_layer": 0, "running_balance_rows": 0, "rows_proven_by_balances": 0}
    readers = []
    for row in rows:
        printed = _printed(printed_pages, row.page)
        in_text_layer = printed.amount_in_text_layer(row.amount) if printed is not None else None
        described = (printed.description_words_near(_bare_description(row), row.amount)
                     if printed is not None else None)
        if in_text_layer is not None:
            evidence["text_layer_rows"] += 1
            evidence["amounts_in_text_layer"] += in_text_layer
            evidence["descriptions_in_text_layer"] += bool(described)
        if row.balance is not None:
            evidence["running_balance_rows"] += 1
        state, method, completion_only = (tuple(row_states.get((row.page, row.locator), ())) + (None, None, False))[:3]
        if method == "text_layer":
            evidence["settled_by_text_layer"] += 1
            readers.append(1.0)
        elif state == "agreed":
            readers.append(1.0)
        elif state == "corrected":
            evidence["corrected_rows"] += 1
            evidence["completion_only_corrections"] += bool(completion_only)
            readers.append(1.0 if completion_only or (in_text_layer and described) else 0.5)
        else:
            evidence["reviewer_only_rows"] += state == "added"
            readers.append(0.0)
    text_rows = evidence["text_layer_rows"]
    components["amounts_printed"] = evidence["amounts_in_text_layer"] / text_rows if text_rows else None
    components["two_readers"] = sum(readers) / len(readers) if readers else None
    components["descriptions_in_text_layer"] = evidence["descriptions_in_text_layer"] / text_rows if text_rows else None
    # A printed balance proves its own row and the earlier rows of the same day in the listing (an end-of-day
    # balance); the continuity check refuses the statement on any break, so a break proves nothing.
    evidence["rows_proven_by_balances"] = _rows_proven_by_balances(rows)
    components["running_balances"] = ((0.0 if "continuity_break" in reasons
                                       else evidence["rows_proven_by_balances"] / len(rows))
                                      if evidence["running_balance_rows"] else None)

    applicable = [value for value in components.values() if value is not None]
    strength = sum(applicable) / len(applicable) if rows and applicable else 0.0
    score = 0.5 + 0.5 * strength if admitted else 0.49 * strength
    band = next(name for floor, name in BANDS if score >= floor) if admitted else "held"
    return {"methodology": CONFIDENCE_METHOD, "provisional": False, "score": round(score, 4), "band": band,
            "components": {name: None if value is None else round(value, 4) for name, value in components.items()},
            "evidence": evidence}
