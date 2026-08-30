"""pagecov_probe.py — the RV-PAGE-COVERAGE probe: why each document carries
`missing_declared_statement_page`, in SHAPES and COUNTS only.

    python -m tools.pagecov_probe --shas <population>.txt \
        --data-dir <cold cache> [--json <private>.json] [--label "<tree, card>"]

Read-only. It replays each sha from the run of record's own cached text — the
same cold-cache read `tools.cohort_replay` makes — and reports, per document:

* `sheets` / `printed` — the intake object's page list, and the subset the check
  counts (a blank or whitespace-only sheet is excluded by the check itself);
* `declared` — the largest declared denominator, exactly as `analysis.pipeline`
  derives it. The probe IMPORTS `_PAGE_DECLARATION_RE` from the production
  module rather than carrying a copy, so at a tree where the reading changes it
  reports THAT tree's reading (the CPDECL lesson: ask the reader, never mirror
  a rule);
* the declaration FORMS each sheet carries, as named shapes;
* which declared labels the check cannot find, and how many sheets carry no
  declaration it can read;
* CAUSE TAGS (below), and the class — the card's (a)/(b)/(c), with (a) split
  three ways because "the flag is correct" has three different reasons:
  `a_SHEETS_GENUINELY_ABSENT` (the PDF carries fewer sheets than it declares),
  `a_DECLARED_SHEET_CARRIES_NO_TEXT` (it carries enough sheets, one of which
  holds no text, so the check drops it from both counts) and
  `a_LABEL_GLYPHS_DESTROYED` (every declared sheet is there and text-bearing;
  what is missing is a readable LABEL);
* three COUNTERFACTUALS — for each candidate widening, whether the flag would
  clear on this document. A cause that clears nothing is still reported: the
  card's deliverable is the table, not the movement.

Cause tags
----------
`SHEETS_SHORT`            the PDF carries fewer physical sheets than it declares
`BLANK_SHEET_SHORTFALL`   it carries enough sheets, but one or more of them hold
                          no text at all, and the check drops those from both
                          of its counts
`FORM_UNREAD_ON_SHEET`    a sheet the check calls unlabelled carries a page
                          declaration in a form the check's pattern refuses
`WORD_PAGE_NO_ORDINAL`    such a sheet prints the word `Page` with no readable
                          ordinal beside it — the glyphs, not the pattern
`DUPLICATE_ORDINAL`       one ordinal is declared on two different sheets at the
                          document's own denominator
`MINORITY_DENOMINATOR`    the largest denominator is declared by strictly fewer
                          declarations than a smaller one

**The control.** A mirrored decision that has drifted from the check it mirrors
is worse than no mirror, so after tracing, the real pipeline runs on the same
text and the published integrity flags are compared with the probe's own
decision. A document where they differ is reported as `TRACE-DISAGREES`, is not
given a class, and makes the exit code 2. That count must be 0 for the table to
mean anything.

It never prints a document value: shas, form NAMES, page ordinals and counts
only. No OCR, no model, no network, $0.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")

# C0 controls, minus the whitespace three (\t \n \r) that `\s` already matches.
# PNC9.3 measured a NUL where a column gap belongs; `\s` does not match it, so a
# pattern spanning that gap does not match either.
_C0 = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

#: Alternative declaration forms, by NAME. The form the check itself reads is
#: imported from the production module and is never restated here.
#: `supplies` is False for a form that cannot place a page: it carries no
#: denominator, or its shape is shared with things that are not page footers.
_ALT_FORMS: tuple[tuple[str, "re.Pattern[str] | None", bool], ...] = (
    # `Page 1of 11` — the ordinal and `of` with no space between them. Measured
    # on a Tesseract scan whose every other sheet prints the spaced form.
    ("PAGE_N_OF_M_NO_SPACE", re.compile(r"\bPage\s*:?\s*(\d{1,3})\s*of\s+(\d{1,3})\b", re.IGNORECASE), True),
    # `Page 3 of 8` with a C0 control byte in one of the gaps (handled below).
    ("PAGE_N_OF_M_SPLIT_BY_CONTROL_BYTE", None, True),
    # `Page 3/8`, `Page: 3 / 8`.
    ("PAGE_N_SLASH_M", re.compile(r"\bPage\s*:?\s*(\d{1,3})\s*/\s*(\d{1,3})\b", re.IGNORECASE), True),
    # `3 of 8` with no `Page` word in front of it — reported, not trusted: the
    # shape is also `3 of 8 checks enclosed`.
    ("N_OF_M_NO_PAGE_WORD", re.compile(r"(?<![A-Za-z])(\d{1,3})\s+of\s+(\d{1,3})(?!\d)", re.IGNORECASE), False),
    # a bare `3/8` — reported, never trusted: it is also every fraction and half
    # of every date the paper prints.
    ("N_SLASH_M_BARE", re.compile(r"(?<![\d/])(\d{1,3})\s*/\s*(\d{1,3})(?![\d/])"), False),
    # `Page 3` with no denominator at all — cannot place a page against a total.
    ("PAGE_N_NO_DENOMINATOR", re.compile(r"\bPage\s*:?\s*(\d{1,3})\b(?!\s*(?:of|/))", re.IGNORECASE), False),
)

#: The word `Page` with no digit anywhere after it on the line — the glyph
#: failure, reported so it is never mistaken for a pattern failure.
_PAGE_WORD = re.compile(r"\bPage\b", re.IGNORECASE)
_PAGE_WORD_WITH_ORDINAL = re.compile(r"\bPage\s*:?\s*\d", re.IGNORECASE)

#: The forms a counterfactual widening would trust.
_TRUSTED = tuple(name for name, _, supplies in _ALT_FORMS if supplies)


class ColdCache:
    """The cold cache reader, identical in behaviour to `tools.cohort_replay`'s."""

    def __init__(self, data_dir: Path):
        import sqlite3

        self.root = data_dir / "artifacts"
        self.conn = sqlite3.connect(
            f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True
        )
        from ocr.document import StatementMarkdown

        self._markdown = StatementMarkdown

    def text(self, sha: str) -> tuple[str | None, list[str]]:
        rows = self.conn.execute(
            "SELECT artifact_path FROM artifact_cache WHERE stage = ? AND input_sha256 = ?",
            ("ocr", sha),
        ).fetchall()
        if not rows:
            return None, []
        try:
            payload = json.loads((self.root / rows[0][0]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, []
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            return None, []
        pages = [str(p) for p in (document.get("pages") or [])]
        markdown = self._markdown(
            source_file="replay.pdf",
            model=str(document.get("model") or ""),
            pages=pages,
        ).to_markdown()
        return markdown, pages


def forms_on(sheet: str, read_by_check: "re.Pattern[str]") -> dict[str, list[tuple[int, int]]]:
    """The declaration forms this sheet carries, NAME -> [(ordinal, denominator)].

    A denominator of 0 means the form carries none. What the check itself reads
    is reported under `READ_BY_CHECK`; an alternative form is reported only for
    the pairs the check did NOT already read, so the table counts new
    information rather than restating the same footer twice.
    """
    found: dict[str, list[tuple[int, int]]] = {}
    read = [(int(a), int(b)) for a, b in read_by_check.findall(sheet)]
    if read:
        found["READ_BY_CHECK"] = sorted(set(read))
    already = set(read)

    normalised = _C0.sub(" ", sheet)
    if normalised != sheet:
        gained = {(int(a), int(b)) for a, b in read_by_check.findall(normalised)} - already
        if gained:
            found["PAGE_N_OF_M_SPLIT_BY_CONTROL_BYTE"] = sorted(gained)

    for name, pattern, _supplies in _ALT_FORMS:
        if pattern is None:
            continue
        pairs: set[tuple[int, int]] = set()
        for match in pattern.finditer(sheet):
            groups = match.groups()
            pairs.add((int(groups[0]), int(groups[1]) if len(groups) > 1 else 0))
        pairs -= already
        if pairs:
            found[name] = sorted(pairs)

    if not read and _PAGE_WORD.search(sheet) and not _PAGE_WORD_WITH_ORDINAL.search(sheet):
        found["WORD_PAGE_NO_ORDINAL"] = []
    return found


def _decide(declared_total: int, declarations: list[tuple[int, int]],
            printed_sheets: int, unlabelled_sheets: int) -> tuple[list[int], bool]:
    """The check's own arithmetic, given a reading. -> (missing, flag)."""
    present = {current for current, total in declarations if total == declared_total}
    missing = sorted(set(range(1, declared_total + 1)) - present)
    accounted_for = printed_sheets >= declared_total and len(missing) <= unlabelled_sheets
    return missing, bool(missing) and not accounted_for


def probe_one(markdown: str, sheets: list[str]) -> dict:
    from analysis.pipeline import _PAGE_DECLARATION_RE

    declarations = [
        (int(current), int(total)) for current, total in _PAGE_DECLARATION_RE.findall(markdown)
    ]
    printed = [sheet for sheet in sheets if sheet.strip()]
    record: dict = {
        "sheets": len(sheets),
        "printed_sheets": len(printed),
        "declarations_read": len(declarations),
    }
    if not declarations:
        record.update(
            {"declared_total": None, "missing": [], "unlabelled_sheets": None,
             "accounted_for": None, "probe_flag": False, "denominators": {},
             "tags": [], "forms": [], "class": "NO_DECLARATION",
             "would_clear": {}}
        )
        return record

    declared_total = max(total for _, total in declarations)
    unlabelled_sheets = sum(1 for sheet in printed if not _PAGE_DECLARATION_RE.search(sheet))
    missing, probe_flag = _decide(declared_total, declarations, len(printed), unlabelled_sheets)

    denominators: dict[int, int] = {}
    for _, total in declarations:
        denominators[total] = denominators.get(total, 0) + 1

    per_sheet: list[dict] = []
    widened: list[tuple[int, int]] = list(declarations)
    widened_labelled: list[bool] = []
    tags: set[str] = set()
    for index, sheet in enumerate(printed, start=1):
        found = forms_on(sheet, _PAGE_DECLARATION_RE)
        read = "READ_BY_CHECK" in found
        alternatives = {k: v for k, v in found.items() if k != "READ_BY_CHECK"}
        gained = [pair for name in _TRUSTED for pair in alternatives.get(name, [])]
        widened.extend(gained)
        widened_labelled.append(bool(read or gained))
        if not read:
            if gained:
                tags.add("FORM_UNREAD_ON_SHEET")
            if "WORD_PAGE_NO_ORDINAL" in alternatives:
                tags.add("WORD_PAGE_NO_ORDINAL")
        per_sheet.append({
            "sheet": index,
            "read_by_check": found.get("READ_BY_CHECK", []),
            "alternative_forms": {k: v for k, v in sorted(alternatives.items())},
        })

    if len(sheets) < declared_total:
        tags.add("SHEETS_SHORT")
    elif len(printed) < declared_total:
        tags.add("BLANK_SHEET_SHORTFALL")
    ordinals_at_total = [c for c, t in declarations if t == declared_total]
    if len(ordinals_at_total) != len(set(ordinals_at_total)):
        tags.add("DUPLICATE_ORDINAL")
    if denominators[declared_total] < max(denominators.values()):
        tags.add("MINORITY_DENOMINATOR")

    # ---- counterfactuals, each measured rather than argued -------------------
    would: dict[str, bool] = {}
    # 1. the declaration reading widened to the trusted alternative forms.
    widened_unlabelled = sum(1 for labelled in widened_labelled if not labelled)
    widened_total = max(total for _, total in widened)
    _, flag_form = _decide(widened_total, widened, len(printed), widened_unlabelled)
    would["form_widened"] = probe_flag and not flag_form
    # 2. the denominator taken by weight of declarations rather than by size.
    majority = max(denominators.items(), key=lambda item: (item[1], item[0]))[0]
    _, flag_major = _decide(majority, declarations, len(printed), unlabelled_sheets)
    would["majority_denominator"] = probe_flag and not flag_major
    # 3. a text-empty sheet counted as a present, unlabelled sheet.
    blank = len(sheets) - len(printed)
    _, flag_blank = _decide(declared_total, declarations, len(sheets), unlabelled_sheets + blank)
    would["blank_sheet_counted"] = probe_flag and not flag_blank
    # 4. all three together — the majority recomputed over the widened reading.
    widened_denominators: dict[int, int] = {}
    for _, total in widened:
        widened_denominators[total] = widened_denominators.get(total, 0) + 1
    widened_majority = max(widened_denominators.items(), key=lambda item: (item[1], item[0]))[0]
    _, flag_all = _decide(
        widened_majority, widened, len(sheets), widened_unlabelled + blank
    )
    would["all_three"] = probe_flag and not flag_all

    # The residual class is NOT "the sheets are absent". A document can carry
    # every sheet it declares, all of them text-bearing, and still be flagged
    # because two sheets were read with the SAME ordinal or a footer's digits
    # came out of the scan as letters. Calling that "genuinely absent" would be
    # the probe asserting the one thing it cannot see, so the shortfall is named
    # for where it actually is — in the labels — and the cause tags say why.
    if not probe_flag:
        klass = "NOT_FLAGGED"
    elif "FORM_UNREAD_ON_SHEET" in tags:
        klass = "b_DECLARATION_FORM_UNREAD"
    elif "MINORITY_DENOMINATOR" in tags:
        klass = "c_DENOMINATOR_NOT_A_PAGE_COUNT"
    elif "BLANK_SHEET_SHORTFALL" in tags:
        klass = "a_DECLARED_SHEET_CARRIES_NO_TEXT"
    elif "SHEETS_SHORT" in tags:
        klass = "a_SHEETS_GENUINELY_ABSENT"
    else:
        klass = "a_LABEL_GLYPHS_DESTROYED"

    record.update({
        "declared_total": declared_total,
        "max_declared_ordinal": max(current for current, _ in declarations),
        "missing": missing,
        "unlabelled_sheets": unlabelled_sheets,
        "accounted_for": len(printed) >= declared_total and len(missing) <= unlabelled_sheets,
        "probe_flag": probe_flag,
        "denominators": {str(k): v for k, v in sorted(denominators.items())},
        "tags": sorted(tags),
        "forms": per_sheet,
        "would_clear": would,
        "class": klass,
    })
    return record


def outcome_of(markdown: str, sheets: list[str]) -> tuple[str, str, list[str]]:
    """The runner's own classification of this text and this page list."""
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from telemetry.record import classify_outcome

    try:
        payload = report_to_dict(
            analyze_markdown(markdown, parse_mode="deterministic", sheets=sheets)
        )
    except Exception as exc:  # the runner's own boundary: never raises
        return "failed", f"raised:{type(exc).__name__}", []
    klass, reason = classify_outcome(payload)
    flags = sorted((payload.get("integrity") or {}).get("flags") or [])
    return klass, reason, flags


def blank_sheet_counterfactual(markdown: str, sheets: list[str]) -> dict | None:
    """What outcome would this document reach if a TEXT-EMPTY sheet counted?

    No production code is changed and no rule is relaxed: the counterfactual is
    expressed entirely in the `sheets` ARGUMENT — the intake object's page list —
    by substituting a single placeholder character for each text-empty sheet.
    The document text passed as `markdown` is untouched, so the substitution
    reproduces exactly what the check would see if `printed_sheets` kept a blank
    sheet: one more present sheet, and one more UNLABELLED sheet, since a
    placeholder carries no declaration.

    Returns None for a document with no text-empty sheet, which is every
    document this question is not about.
    """
    blank = sum(1 for sheet in sheets if not sheet.strip())
    if not blank:
        return None
    actual_class, actual_reason, actual_flags = outcome_of(markdown, sheets)
    substituted = [sheet if sheet.strip() else "." for sheet in sheets]
    cf_class, cf_reason, cf_flags = outcome_of(markdown, substituted)
    return {
        "blank_sheets": blank,
        "actual": f"{actual_class}/{actual_reason}",
        "actual_flags": actual_flags,
        "counterfactual": f"{cf_class}/{cf_reason}",
        "counterfactual_flags": cf_flags,
    }


def published_flags(markdown: str, sheets: list[str]) -> tuple[list[str] | None, str]:
    """The real pipeline's integrity flags on the same text — the probe's control."""
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict

    try:
        payload = report_to_dict(
            analyze_markdown(markdown, parse_mode="deterministic", sheets=sheets)
        )
    except Exception as exc:  # the runner's own boundary: never raises
        return None, f"raised:{type(exc).__name__}"
    flags = (payload.get("integrity") or {}).get("flags")
    if flags is None:
        return None, "no_integrity_section"
    return [str(flag) for flag in flags], "ok"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shas", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--label", default="")
    parser.add_argument("--forms", action="store_true", help="print the per-sheet form table")
    parser.add_argument(
        "--outcome-counterfactual", action="store_true",
        help="for each document with a text-empty sheet, the OUTCOME it reaches now and the "
             "outcome it would reach if that sheet counted (expressed in the sheets argument "
             "only; no production code is changed)",
    )
    args = parser.parse_args(argv)

    shas = [
        line.strip().upper()
        for line in args.shas.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    cache = ColdCache(args.data_dir)

    rows: list[dict] = []
    disagrees = 0
    for sha in shas:
        markdown, sheets = cache.text(sha)
        if markdown is None:
            rows.append({"sha16": sha[:16], "class": "NO_TEXT", "tags": [], "forms": []})
            continue
        record = probe_one(markdown, sheets)
        record["sha16"] = sha[:16]
        if args.outcome_counterfactual:
            counterfactual = blank_sheet_counterfactual(markdown, sheets)
            if counterfactual is not None:
                record["blank_sheet_outcome"] = counterfactual
        flags, status = published_flags(markdown, sheets)
        record["control_status"] = status
        if flags is None:
            record["published_flag"] = None
            record["trace_disagrees"] = True
        else:
            published = "missing_declared_statement_page" in flags
            record["published_flag"] = published
            record["other_published_flags"] = sorted(
                flag for flag in flags if flag != "missing_declared_statement_page"
            )
            record["trace_disagrees"] = published != bool(record["probe_flag"])
        if record["trace_disagrees"]:
            disagrees += 1
            record["class"] = "TRACE-DISAGREES"
        rows.append(record)

    print(f"# pagecov probe — {args.label or 'unlabelled'} — population {len(shas)}")
    print()
    print("| sha16 | sheets | printed | declared | denominators | missing | unlab | flag probe/published | other flags | cause tags | class |")
    print("|---|---:|---:|---:|---|---|---:|---|---:|---|---|")
    for row in rows:
        if row.get("class") in ("NO_TEXT", "NO_DECLARATION"):
            print(f"| `{row['sha16']}` | | | | | | | | | | {row['class']} |")
            continue
        denominators = " ".join(f"{k}x{v}" for k, v in row["denominators"].items())
        missing = ",".join(str(m) for m in row["missing"]) or "-"
        print(
            f"| `{row['sha16']}` | {row['sheets']} | {row['printed_sheets']} | "
            f"{row['declared_total']} | {denominators} | {missing} | "
            f"{row['unlabelled_sheets']} | {row['probe_flag']}/{row.get('published_flag')} | "
            f"{len(row.get('other_published_flags') or [])} | {' '.join(row['tags']) or '-'} | "
            f"{row['class']} |"
        )
    print()
    counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for row in rows:
        counts[row.get("class", "?")] = counts.get(row.get("class", "?"), 0) + 1
        for tag in row.get("tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    print("| class | n |")
    print("|---|---:|")
    for name, count in sorted(counts.items()):
        print(f"| {name} | {count} |")
    print()
    print("| cause tag | n |")
    print("|---|---:|")
    for name, count in sorted(tag_counts.items()):
        print(f"| {name} | {count} |")
    print()
    print("| counterfactual | documents whose flag would clear |")
    print("|---|---:|")
    for key in ("form_widened", "majority_denominator", "blank_sheet_counted", "all_three"):
        cleared = sum(1 for row in rows if (row.get("would_clear") or {}).get(key))
        print(f"| {key} | {cleared} |")
    print()
    print(f"**TRACE-DISAGREES {disagrees}**")

    if args.outcome_counterfactual:
        measured = [row for row in rows if row.get("blank_sheet_outcome")]
        print()
        print("## the text-empty sheet, as an OUTCOME rather than a flag")
        print()
        print("| sha16 | blank sheets | outcome now | flags now | outcome if the sheet counted | flags then |")
        print("|---|---:|---|---:|---|---:|")
        for row in measured:
            cell = row["blank_sheet_outcome"]
            print(
                f"| `{row['sha16']}` | {cell['blank_sheets']} | {cell['actual']} | "
                f"{len(cell['actual_flags'])} | **{cell['counterfactual']}** | "
                f"{len(cell['counterfactual_flags'])} |"
            )
        moved = sum(
            1 for row in measured
            if row["blank_sheet_outcome"]["counterfactual"].startswith("validated")
            and not row["blank_sheet_outcome"]["actual"].startswith("validated")
        )
        print()
        print(f"**{moved} of {len(measured)} would reach `validated`** — measured, not inferred, "
              "and refused: a text-empty sheet is not a proven page.")

    if args.forms:
        print()
        print("## declaration forms, by document and sheet")
        print()
        print("| sha16 | sheet | read by check | alternative forms |")
        print("|---|---:|---|---|")
        for row in rows:
            for sheet in row.get("forms") or []:
                alternatives = sheet["alternative_forms"]
                if not alternatives and sheet["read_by_check"]:
                    continue
                shapes = "; ".join(
                    f"{name}x{len(pairs)}" for name, pairs in alternatives.items()
                ) or "none"
                read = ",".join(f"{a}of{b}" for a, b in sheet["read_by_check"]) or "none"
                print(f"| `{row['sha16']}` | {sheet['sheet']} | {read} | {shapes} |")

    if args.json:
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 2 if disagrees else 0


if __name__ == "__main__":
    raise SystemExit(main())
