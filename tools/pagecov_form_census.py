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
* for each candidate widening — each alternative form ON ITS OWN and the trusted
  set together, the denominator taken by weight rather than by size, a
  text-empty sheet counted as a present sheet — how many documents' decision
  would CHANGE, split into `cleared` and `RAISED`, and split by baseline outcome
  so a raise on a validated document is visible as the regression it would be.

The point of the RAISED column: a widening of the reading is not
restriction-only. `declared_total` is the largest denominator found, so a form
the check newly reads can INCREASE the declared total and manufacture a flag on
a document that did not carry one. That is a `validated -> review` regression,
and it is measured here rather than argued.

**Both halves of the archive are walked, and the second one is where the raises
are.** A document the check reads no declaration on cannot carry this flag at
all today — there is no declared total for a label to be missing from. Give the
reading one form it did not have and that document acquires a declared total for
the first time, and with it the flag. An earlier form of this instrument
returned early on exactly those documents, so its `RAISED 0` was measured over
the half where a raise is impossible (PAGECOV review, MAJOR-2). Every document
with cached text now gets the widened arithmetic, and `has_declaration` says
which half it is in.

**Each form is measured on its own, not only as a set.** An aggregate hides
which member did the damage, and here it did: measured per form, every raise in
the archive comes from ONE of the three the branch first trusted, and the two
others raise nothing. A follow-on card inheriting the aggregate would have
retired a safe form along with an unsafe one. `AS_SHIPPED` keeps the branch's
original trusted set as its own row so the review's number stays reproducible at
this tree.

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

#: The set this branch trusted before the PAGECOV review, kept so the review's
#: measurement reproduces at this tree even though `_TRUSTED` has since dropped
#: a member. Never used as a recommendation — only as a row in the table.
AS_SHIPPED = (
    "PAGE_N_OF_M_NO_SPACE",
    "PAGE_N_OF_M_SPLIT_BY_CONTROL_BYTE",
    "PAGE_N_SLASH_M",
)


def form_sets() -> dict[str, tuple[str, ...]]:
    """The candidate readings, each evaluated separately over the whole archive."""
    candidates: dict[str, tuple[str, ...]] = {
        "trusted_now": tuple(_TRUSTED),
        "as_shipped": AS_SHIPPED,
    }
    for name in dict.fromkeys(AS_SHIPPED + tuple(_TRUSTED)):
        candidates[f"only:{name}"] = (name,)
    return candidates


def reading(markdown: str, sheets: list[str], candidates: dict[str, tuple[str, ...]]) -> dict:
    """The check's own arithmetic at this tree, plus each widened arithmetic.

    THE DOCUMENTS WITH NO DECLARATION ARE THE POINT, not an empty case to skip.
    An earlier form of this function returned None whenever the check's own
    pattern found nothing, and those 1,425 documents entered neither the form
    table nor the widening columns — which is exactly the population where a
    widening is dangerous. Today they have no `declared_total`, so
    `missing_declared_statement_page` CANNOT fire on them; give the reading one
    form it did not have, and it can. Skipping them measured "raises nothing"
    over the half of the archive where a raise is impossible (found by the
    PAGECOV review, MAJOR-2).

    The sheets are scanned for forms ONCE and every candidate reading is
    evaluated from that one scan, so adding a candidate costs arithmetic rather
    than another pass over the archive.
    """
    from analysis.pipeline import _PAGE_DECLARATION_RE

    declarations = [
        (int(current), int(total)) for current, total in _PAGE_DECLARATION_RE.findall(markdown)
    ]
    printed = [sheet for sheet in sheets if sheet.strip()]
    unlabelled = sum(1 for sheet in printed if not _PAGE_DECLARATION_RE.search(sheet))
    if declarations:
        declared_total = max(total for _, total in declarations)
        _, flag = _decide(declared_total, declarations, len(printed), unlabelled)
    else:
        declared_total = None
        flag = False

    per_sheet = [forms_on(sheet, _PAGE_DECLARATION_RE) for sheet in printed]
    forms_seen: set[str] = set()
    for found in per_sheet:
        forms_seen.update(found)

    widened_flags: dict[str, bool] = {}
    widened_totals: dict[str, int | None] = {}
    gains: dict[str, bool] = {}
    for label, names in candidates.items():
        widened = list(declarations)
        widened_unlabelled = 0
        for found in per_sheet:
            gained = [pair for name in names for pair in found.get(name, [])]
            widened.extend(gained)
            if "READ_BY_CHECK" not in found and not gained:
                widened_unlabelled += 1
        if widened:
            total = max(denominator for _, denominator in widened)
            _, widened_flag = _decide(total, widened, len(printed), widened_unlabelled)
        else:
            total = None
            widened_flag = flag
        widened_flags[label] = widened_flag
        widened_totals[label] = total
        gains[label] = bool(widened) and not declarations

    denominators: dict[int, int] = {}
    for _, total in declarations:
        denominators[total] = denominators.get(total, 0) + 1

    if declarations:
        majority = max(denominators.items(), key=lambda item: (item[1], item[0]))[0]
        _, flag_major = _decide(majority, declarations, len(printed), unlabelled)
        blank = len(sheets) - len(printed)
        _, flag_blank = _decide(declared_total, declarations, len(sheets), unlabelled + blank)
    else:
        # Both candidates re-weigh or re-count against a DECLARED TOTAL, and
        # this document declares none, so neither can move it. Reported as
        # unchanged rather than omitted: an omission is what MAJOR-2 was.
        majority = None
        flag_major = flag
        flag_blank = flag

    return {
        "sheets": len(sheets),
        "printed_sheets": len(printed),
        "has_declaration": bool(declarations),
        "declared_total": declared_total,
        "majority_denominator": majority,
        "unlabelled_sheets": unlabelled,
        "forms_seen": sorted(forms_seen),
        "flag": flag,
        "widened_flags": widened_flags,
        "widened_totals": widened_totals,
        "would_gain_a_declaration": gains,
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

    candidates = form_sets()
    cache = ColdCache(args.data_dir)
    started = time.time()
    records: list[dict] = []
    movers: list[dict] = []
    no_text = 0
    no_declaration = 0
    gained_a_declaration: dict[str, dict[str, int]] = {}
    form_counts: dict[str, int] = {}
    form_counts_by_half: dict[str, dict[str, int]] = {"reads": {}, "reads_none": {}}
    change_keys = list(candidates) + ["majority_denominator", "blank_sheet_counted"]
    changes: dict[str, dict[str, dict[str, int]]] = {key: {} for key in change_keys}

    for index, sha in enumerate(shas, start=1):
        markdown, sheets = cache.text(sha)
        if markdown is None:
            no_text += 1
            continue
        record = reading(markdown, sheets, candidates)
        record["sha16"] = sha[:16]
        record["baseline"] = baseline[sha]
        half = "reads" if record["has_declaration"] else "reads_none"
        if not record["has_declaration"]:
            no_declaration += 1
        for name in record["forms_seen"]:
            form_counts[name] = form_counts.get(name, 0) + 1
            form_counts_by_half[half][name] = form_counts_by_half[half].get(name, 0) + 1
        for label in candidates:
            if record["would_gain_a_declaration"][label]:
                bucket = gained_a_declaration.setdefault(label, {})
                bucket[record["baseline"]] = bucket.get(record["baseline"], 0) + 1
        pairs = [(label, record["widened_flags"][label]) for label in candidates]
        pairs += [
            ("majority_denominator", record["flag_majority_denominator"]),
            ("blank_sheet_counted", record["flag_blank_sheet_counted"]),
        ]
        for key, flagged in pairs:
            if flagged != record["flag"]:
                direction = "cleared" if record["flag"] else "RAISED"
                bucket = changes[key].setdefault(direction, {})
                bucket[record["baseline"]] = bucket.get(record["baseline"], 0) + 1
                record.setdefault("changes", []).append(f"{key}:{direction}")
        records.append(record)
        if record.get("changes"):
            movers.append(record)
        if index % 250 == 0:
            print(f"  {index}/{len(shas)} ({int(time.time() - started)}s)", file=sys.stderr)

    print(f"# pagecov form census — {args.label or 'unlabelled'} — {len(shas)} shas "
          f"[{args.start}:{args.end}]")
    print()
    print(f"no cached text {no_text} · no page declaration {no_declaration} · "
          f"with a declaration {len(shas) - no_text - no_declaration}")
    print()
    print("Both halves are walked. The `reads none` column is the population a")
    print("widening can only ever ADD a declared total to, so it is where a raise")
    print("comes from; it was the half an earlier form of this instrument skipped.")
    print()
    print("| declaration form seen on a sheet | check reads a declaration | check reads none | all |")
    print("|---|---:|---:|---:|")
    for name, count in sorted(form_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"| {name} | {form_counts_by_half['reads'].get(name, 0)} | "
              f"{form_counts_by_half['reads_none'].get(name, 0)} | {count} |")
    print()
    print("| candidate reading | documents given a declared total for the first time |")
    print("|---|---|")
    for label in candidates:
        bucket = gained_a_declaration.get(label, {})
        detail = ", ".join(f"{outcome} {n}" for outcome, n in sorted(bucket.items()))
        print(f"| {label} | {sum(bucket.values())}{' (' + detail + ')' if detail else ''} |")
    print()
    print("| candidate | direction | baseline outcome | documents |")
    print("|---|---|---|---:|")
    for key in change_keys:
        if not changes[key]:
            print(f"| {key} | — | — | 0 |")
            continue
        for direction in sorted(changes[key]):
            for outcome, count in sorted(changes[key][direction].items()):
                print(f"| {key} | **{direction}** | {outcome} | {count} |")
    print()
    print("| sha16 | baseline | half | sheets | printed | declared | majority | changes |")
    print("|---|---|---|---:|---:|---:|---:|---|")

    def cell(value) -> str:
        return "—" if value is None else str(value)

    for record in sorted(movers, key=lambda r: (r["has_declaration"], r["sha16"])):
        print(
            f"| `{record['sha16']}` | {record['baseline']} | "
            f"{'reads' if record['has_declaration'] else '**reads none**'} | "
            f"{record['sheets']} | {record['printed_sheets']} | "
            f"{cell(record['declared_total'])} | {cell(record['majority_denominator'])} | "
            f"{' '.join(record['changes'])} |"
        )

    if args.json:
        # Every record, not only the movers: the headline tables above are
        # aggregates over the whole population, and an artefact holding only the
        # movers cannot reproduce them (PAGECOV review, MINOR-3).
        args.json.write_text(
            json.dumps(
                {
                    "shas": len(shas),
                    "no_cached_text": no_text,
                    "no_declaration": no_declaration,
                    "candidates": {k: list(v) for k, v in candidates.items()},
                    "form_counts": form_counts,
                    "form_counts_by_half": form_counts_by_half,
                    "records": records,
                },
                indent=1,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
