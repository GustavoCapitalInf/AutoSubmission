"""pagecov_form_census.py — the page-declaration reading, censused over the
WHOLE archive, and what each candidate widening would do to every document.

    python -m tools.pagecov_form_census --rows <run>/rows.csv \
        --data-dir <cold cache> [--start A --end B] [--json <private>.json]

The `missing_declared_statement_page` check is SHARED — every document with a
page declaration is in its blast radius, not only the eleven that carry the
flag. This walks every sha in the run of record from that run's own cached text
and reports, for the whole archive:

* the declaration FORMS the corpus prints, and how many documents print a form
  the check's own pattern refuses;
* the check's decision at THIS tree's reading, against the baseline outcome;
* for each candidate widening — the alternative forms trusted, the denominator
  taken by weight rather than by size, a text-empty sheet counted as a present
  sheet — how many documents' decision would CHANGE, split into `cleared` and
  `RAISED`, and split by baseline outcome so a raise on a validated document is
  visible as the regression it would be.

The point of the RAISED column: a widening of the reading is not
restriction-only. `declared_total` is the largest denominator found, so a form
the check newly reads can INCREASE the declared total and manufacture a flag on
a document that did not carry one. That is a `validated -> review` regression,
and it is measured here rather than argued.

Read-only, no pipeline, no OCR, no model, no network, $0. It prints shas,
outcome classes, form names, page ordinals and counts — never a document value.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from tools.pagecov_probe import ColdCache, _TRUSTED, _decide, forms_on

DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")


def reading(markdown: str, sheets: list[str]) -> dict | None:
    """The check's own arithmetic at this tree, plus each widened arithmetic."""
    from analysis.pipeline import _PAGE_DECLARATION_RE

    declarations = [
        (int(current), int(total)) for current, total in _PAGE_DECLARATION_RE.findall(markdown)
    ]
    if not declarations:
        return None
    printed = [sheet for sheet in sheets if sheet.strip()]
    declared_total = max(total for _, total in declarations)
    unlabelled = sum(1 for sheet in printed if not _PAGE_DECLARATION_RE.search(sheet))
    _, flag = _decide(declared_total, declarations, len(printed), unlabelled)

    widened = list(declarations)
    widened_unlabelled = 0
    forms_seen: set[str] = set()
    unread_but_formed = 0
    for sheet in printed:
        found = forms_on(sheet, _PAGE_DECLARATION_RE)
        forms_seen.update(found)
        read = "READ_BY_CHECK" in found
        gained = [pair for name in _TRUSTED for pair in found.get(name, [])]
        widened.extend(gained)
        if not read:
            if gained:
                unread_but_formed += 1
            else:
                widened_unlabelled += 1

    denominators: dict[int, int] = {}
    for _, total in declarations:
        denominators[total] = denominators.get(total, 0) + 1
    majority = max(denominators.items(), key=lambda item: (item[1], item[0]))[0]

    widened_total = max(total for _, total in widened)
    _, flag_form = _decide(widened_total, widened, len(printed), widened_unlabelled)
    _, flag_major = _decide(majority, declarations, len(printed), unlabelled)
    blank = len(sheets) - len(printed)
    _, flag_blank = _decide(declared_total, declarations, len(sheets), unlabelled + blank)

    return {
        "sheets": len(sheets),
        "printed_sheets": len(printed),
        "declared_total": declared_total,
        "widened_total": widened_total,
        "majority_denominator": majority,
        "unlabelled_sheets": unlabelled,
        "sheets_unread_but_carrying_a_form": unread_but_formed,
        "forms_seen": sorted(forms_seen),
        "flag": flag,
        "flag_form_widened": flag_form,
        "flag_majority_denominator": flag_major,
        "flag_blank_sheet_counted": flag_blank,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    baseline: dict[str, str] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if sha and sha not in baseline:
                baseline[sha] = (row.get("outcome_class") or row.get("outcome") or "").strip()
    shas = sorted(baseline)[args.start: args.end]

    cache = ColdCache(args.data_dir)
    started = time.time()
    records: list[dict] = []
    no_text = 0
    no_declaration = 0
    form_counts: dict[str, int] = {}
    changes: dict[str, dict[str, dict[str, int]]] = {
        key: {} for key in ("form_widened", "majority_denominator", "blank_sheet_counted")
    }
    for index, sha in enumerate(shas, start=1):
        markdown, sheets = cache.text(sha)
        if markdown is None:
            no_text += 1
            continue
        record = reading(markdown, sheets)
        if record is None:
            no_declaration += 1
            continue
        record["sha16"] = sha[:16]
        record["baseline"] = baseline[sha]
        for name in record["forms_seen"]:
            form_counts[name] = form_counts.get(name, 0) + 1
        for key, flagged in (
            ("form_widened", record["flag_form_widened"]),
            ("majority_denominator", record["flag_majority_denominator"]),
            ("blank_sheet_counted", record["flag_blank_sheet_counted"]),
        ):
            if flagged != record["flag"]:
                direction = "cleared" if record["flag"] else "RAISED"
                bucket = changes[key].setdefault(direction, {})
                bucket[record["baseline"]] = bucket.get(record["baseline"], 0) + 1
                record.setdefault("changes", []).append(f"{key}:{direction}")
        if record.get("changes"):
            records.append(record)
        if index % 250 == 0:
            print(f"  {index}/{len(shas)} ({int(time.time() - started)}s)", file=sys.stderr)

    print(f"# pagecov form census — {args.label or 'unlabelled'} — {len(shas)} shas "
          f"[{args.start}:{args.end}]")
    print()
    print(f"no cached text {no_text} · no page declaration {no_declaration} · "
          f"with a declaration {len(shas) - no_text - no_declaration}")
    print()
    print("| declaration form seen on a sheet | documents |")
    print("|---|---:|")
    for name, count in sorted(form_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"| {name} | {count} |")
    print()
    print("| candidate widening | direction | baseline outcome | documents |")
    print("|---|---|---|---:|")
    for key in ("form_widened", "majority_denominator", "blank_sheet_counted"):
        if not changes[key]:
            print(f"| {key} | — | — | 0 |")
            continue
        for direction in sorted(changes[key]):
            for outcome, count in sorted(changes[key][direction].items()):
                print(f"| {key} | **{direction}** | {outcome} | {count} |")
    print()
    print("| sha16 | baseline | sheets | printed | declared | widened | majority | changes |")
    print("|---|---|---:|---:|---:|---:|---:|---|")
    for record in records:
        print(
            f"| `{record['sha16']}` | {record['baseline']} | {record['sheets']} | "
            f"{record['printed_sheets']} | {record['declared_total']} | "
            f"{record['widened_total']} | {record['majority_denominator']} | "
            f"{' '.join(record['changes'])} |"
        )
    if args.json:
        args.json.write_text(json.dumps(records, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
