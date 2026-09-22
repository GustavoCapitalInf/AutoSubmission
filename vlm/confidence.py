"""Statement confidence (evidence_v2): how much of a visual reading was independently verified.

An admitted statement has passed every arithmetic check the gate runs (beginning plus rows equals ending,
dates in period, order, duplicates, and whatever totals, counts and running balances the page printed). That
earns half the score. The other half is the mean of the independent evidence that applies to it:

* stated_totals        the printed credit and debit totals were present and reconciled (1, 0.5 or 0);
* stated_counts        the printed credit and debit counts were present and matched (1, 0.5 or 0);
* amounts_printed      share of rows whose amount is printed on its page (text layer or proposer reading);
* two_readers          share of rows both readers agree on: confirmed, settled by the text layer, or a
                       correction the page prints (other corrections count half, reviewer-only rows zero);
* descriptions_in_text_layer   share of rows on text-layer pages every word of whose description the text
                       layer prints (not applicable to scanned pages);
* running_balances     the printed running balances continued without a break (1 or 0; not applicable when
                       none is printed).

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


def statement_confidence(*, admitted: bool, checks: dict, account: dict, rows, row_states: dict,
                         printed_pages, reasons=()) -> dict:
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

    evidence = {"rows": len(rows), "reviewer_only_rows": 0, "corrected_rows": 0, "settled_by_text_layer": 0,
                "amounts_printed": 0, "rows_with_printed_evidence": 0, "text_layer_rows": 0,
                "descriptions_in_text_layer": 0, "running_balance_rows": 0}
    readers = []
    for row in rows:
        printed = _printed(printed_pages, row.page)
        amount_printed = printed is not None and printed.amount_printed(row.amount)
        if printed is not None:
            evidence["rows_with_printed_evidence"] += 1
            evidence["amounts_printed"] += amount_printed
        described = printed.description_words_printed(_bare_description(row)) if printed is not None else None
        if described is not None:
            evidence["text_layer_rows"] += 1
            evidence["descriptions_in_text_layer"] += described
        if row.balance is not None:
            evidence["running_balance_rows"] += 1
        state, method = row_states.get((row.page, row.locator), (None, None))
        if method == "text_layer":
            evidence["settled_by_text_layer"] += 1
            readers.append(1.0)
        elif state == "agreed":
            readers.append(1.0)
        elif state == "corrected":
            evidence["corrected_rows"] += 1
            readers.append(1.0 if amount_printed and described is not False else 0.5)
        else:
            evidence["reviewer_only_rows"] += state == "added"
            readers.append(0.0)
    components["amounts_printed"] = (evidence["amounts_printed"] / evidence["rows_with_printed_evidence"]
                                     if evidence["rows_with_printed_evidence"] else None)
    components["two_readers"] = sum(readers) / len(readers) if readers else None
    components["descriptions_in_text_layer"] = (evidence["descriptions_in_text_layer"] / evidence["text_layer_rows"]
                                                if evidence["text_layer_rows"] else None)
    # Printed running balances (on every row, or only at the end of each day) are verified by the continuity
    # check, which refuses the statement on any break.
    components["running_balances"] = ((0.0 if "continuity_break" in reasons else 1.0)
                                      if evidence["running_balance_rows"] else None)

    applicable = [value for value in components.values() if value is not None]
    strength = sum(applicable) / len(applicable) if rows and applicable else 0.0
    score = 0.5 + 0.5 * strength if admitted else 0.49 * strength
    band = next(name for floor, name in BANDS if score >= floor) if admitted else "held"
    return {"methodology": CONFIDENCE_METHOD, "provisional": False, "score": round(score, 4), "band": band,
            "components": {name: None if value is None else round(value, 4) for name, value in components.items()},
            "evidence": evidence}
