"""The four measurements W3 §DESCCOLS reports that the other two tools do not.

`tools/desccols_census.py` measures the weld and `tools/desccols_movement.py`
measures reach and payload movement. These are the rest, committed for the
same reason: a headline number whose instrument lives in a scratchpad is a
number nobody can re-derive.

    python -m tools.desccols_proofs oracle    --rows <run>/rows.csv --data-dir <checkout>/webapp_data \
        --corpus "<checkout>/Bank Statements" --baseline-settings-key <64 hex>
    python -m tools.desccols_proofs furniture <the same arguments>
    python -m tools.desccols_proofs pinned   --corpus "<checkout>/Bank Statements" --balance-csv docs/balance-metrics-audit-results.csv
    python -m tools.desccols_proofs fallback --rows <run>/rows.csv --corpus "<checkout>/Bank Statements" [--stride 7]
    python -m tools.desccols_proofs boundary --rows <run>/rows.csv --data-dir <checkout>/webapp_data \
        --corpus "<checkout>/Bank Statements" --baseline-settings-key <64 hex>

**oracle** — scores what the readers publish from the REPAIRED text against
§DESCATTRIB's committed geometry oracle, which reads each row's true
description from the PDF's WORD boxes. A different extraction from the line
boxes this card's rung reads, validated before it was used, and refusing any
document whose rows do not pair 1:1 on (section, date, amount). `--shipped`
scores the run's own stored text instead, which is the before half.

**furniture** — the class that oracle CANNOT see, asked directly: a published
description token the oracle does not find between its row's own date and
amount, printed on a line another page of the document repeats at the same band
position. The review's F3, measured on the same rows.

**pinned** — how many of the pinned manifest's statements the new rung claims,
and whether the published payload moves for them. The corpus gate resolves the
pinned set through the PRODUCTION ladder, so an extraction rung can reach the
truth set and must say so before anything else is claimed.

**fallback** — the fail-closed half, measured on the hash that actually
decides whether a document's analysis cache key rotates:
`analysis_input_sha(markdown, sheets)` with the rung live and with it forced
to return None, on the one tree.

**boundary** — for every document the rung claims that the run stored no
payload for, does it publish now? The movement of a document across the line
between publishing and refusing is the one movement a coverage wave may not
leave unmeasured.

READ-ONLY and $0 throughout: the sqlite index is never opened, artifacts are
reached by direct file path, PDFs are opened read-only, and
`parse_mode="deterministic"` cannot reach the extraction branch. Every line of
output is a count, a class or a `content_sha256`; no document text, no figure.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

from ocr.native_text import native_statement

CLAIMED_MODEL = "native-pdf-text+printed-rows"


def _paths(rows_csv: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with rows_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["content_sha256"]:
                out.setdefault(row["content_sha256"], row["relative_path"])
    return out


def _repaired_markdown(pdf: Path):
    """(markdown, pages, model) through the production ladder at this tree."""
    from ocr.document import StatementMarkdown

    document = native_statement(pdf.read_bytes())
    if document is None:
        return None, None, None
    pages = list(document.pages)
    return (StatementMarkdown(source_file="proofs.pdf", model=document.model,
                              pages=pages).to_markdown(), pages, document.model)


# ---------------------------------------------------------------------------
# oracle
# ---------------------------------------------------------------------------

def _published_and_truth(markdown: str, pdf: Path, CC):
    """`([(section, cell, published description)], [OracleRow])` for one document.

    The two halves are computed independently — the published side through the
    readers' own two shared functions, the truth side from the PDF's WORD boxes
    — and are paired 1:1 by the caller on (section, date, amount).
    """
    from analysis.tables import attributed_descriptions
    from tools.descattrib_oracle import _read_pairs, oracle_rows

    pairs = _read_pairs(markdown, CC)
    texts = {}
    for name in {n for n, _c in pairs}:
        runs = [cells for n, cells in pairs if n == name]
        texts[name] = attributed_descriptions(
            runs, strip=CC._DESCRIPTION_FURNITURE, limit=CC._DESCRIPTION_LIMIT)
    flat, seen = [], collections.Counter()
    for name, cells in pairs:
        index = seen[name]
        seen[name] += 1
        for position, cell in enumerate(cells):
            flat.append((name, cell, texts[name][index][position]))
    names = tuple(sorted(CC._SECTION_NAMES, key=len, reverse=True))
    truth = oracle_rows(str(pdf), names, tuple(sorted({n for n, _c in pairs})))
    return flat, truth


def command_oracle(args) -> int:
    from tools.descattrib_oracle import WS, _classify, analysed_text, population
    import analysis.core_processor_counted as CC

    found = population(args.rows, args.data_dir, args.baseline_settings_key)
    grand = collections.Counter()
    print(f"{'document':10} {'rows':>5} | {'exact':>6} {'prefix':>7} {'FOREIGN':>8}")
    for sha, (parser, relative) in sorted(found.items()):
        if parser != "core_processor_counted":
            continue
        pdf = args.corpus / relative
        if args.shipped:
            markdown, _pages, _stored = analysed_text(sha, args.data_dir,
                                                      args.baseline_settings_key)
        else:
            markdown, _pages, _model = _repaired_markdown(pdf)
        if markdown is None:
            grand["unreadable"] += 1
            continue
        flat, truth = _published_and_truth(markdown, pdf, CC)
        if len(flat) != len(truth):
            print(f"{sha[:8]:10} UNPAIRED published={len(flat)} oracle={len(truth)}")
            grand["unpaired"] += 1
            continue
        counts = collections.Counter()
        for (name, cell, published), want in zip(flat, truth):
            assert (name, cell.date, cell.value) == (want.section, want.date, want.amount), (
                f"{sha}: the oracle and the reader disagree about a row")
            printed = WS.sub(" ", want.described).strip(
                CC._DESCRIPTION_FURNITURE).strip()
            counts[_classify(published, printed)] += 1
        print(f"{sha[:8]:10} {len(flat):5} | {counts['exact']:6} "
              f"{counts['prefix']:7} {counts['FOREIGN']:8}")
        grand.update(counts)
        grand["rows"] += len(flat)
    print(f"{'TOTAL':10} {grand['rows']:5} | {grand['exact']:6} {grand['prefix']:7} "
          f"{grand['FOREIGN']:8}   unpaired={grand['unpaired']}")
    return 1 if grand["FOREIGN"] or grand["unpaired"] else 0


# ---------------------------------------------------------------------------
# furniture — the class DC3.1's oracle cannot see, asked directly
# ---------------------------------------------------------------------------

def command_furniture(args) -> int:
    """Can a PUBLISHED description token be this document's page furniture?

    §DESCATTRIB's oracle reads a row's true description from the words printed
    between that row's date and its amount, so a line absorbed from the row's
    own band is part of the truth it compares against and its 0 FOREIGN cannot
    distinguish an absorbed one from a clean one. This mode asks the question
    the oracle cannot, on the same rows, and reports three counts per document:

    * **outside** — published description tokens the oracle does NOT find
      between that row's date and its amount;
    * **repeated** — published description tokens printed on a line that
      ANOTHER page of the document prints at the same band position, i.e. the
      shape G9 refuses;
    * **FLAGGED** — both at once, which is the review's F3 case reaching a
      published description.

    `repeated` is deliberately over-inclusive: it is a token test, so a token
    that also occurs in an ordinary cell counts. An over-inclusive detector
    reporting zero is a stronger statement than an exact one reporting zero.
    Counts only — no document text and no figure is printed.
    """
    import fitz
    import analysis.core_processor_counted as CC
    import ocr.native_text as native_text
    from tools.descattrib_oracle import WS, population

    found = population(args.rows, args.data_dir, args.baseline_settings_key)
    grand = collections.Counter()
    print(f"{'document':10} {'rows':>5} {'tokens':>7} {'outside':>8} "
          f"{'repeated':>9} {'FLAGGED':>8}")
    for sha, (parser, relative) in sorted(found.items()):
        if parser != "core_processor_counted":
            continue
        pdf = args.corpus / relative
        markdown, _pages, _model = _repaired_markdown(pdf)
        if markdown is None:
            grand["unreadable"] += 1
            continue
        with fitz.open(str(pdf)) as document:
            printed = [native_text._printed_lines(page) for page in document]
        repeated = set()
        for lines, marked in zip(printed, native_text._repeated_furniture(printed)):
            for position in marked:
                repeated.update(lines[position].text.split())

        flat, truth = _published_and_truth(markdown, pdf, CC)
        if len(flat) != len(truth):
            print(f"{sha[:8]:10} UNPAIRED published={len(flat)} oracle={len(truth)}")
            grand["unpaired"] += 1
            continue
        counts = collections.Counter()
        for (name, cell, published), want in zip(flat, truth):
            assert (name, cell.date, cell.value) == (want.section, want.date, want.amount), (
                f"{sha}: the oracle and the reader disagree about a row")
            printed_tokens = set(WS.sub(" ", want.described).split())
            for token in published.split():
                counts["tokens"] += 1
                outside = token not in printed_tokens
                counts["outside"] += outside
                counts["repeated"] += token in repeated
                counts["FLAGGED"] += outside and token in repeated
        counts["rows"] = len(flat)
        print(f"{sha[:8]:10} {counts['rows']:5} {counts['tokens']:7} "
              f"{counts['outside']:8} {counts['repeated']:9} {counts['FLAGGED']:8}")
        grand.update(counts)
    print(f"{'TOTAL':10} {grand['rows']:5} {grand['tokens']:7} {grand['outside']:8} "
          f"{grand['repeated']:9} {grand['FLAGGED']:8}   "
          f"unpaired={grand['unpaired']} unreadable={grand['unreadable']}")
    return 1 if grand["FLAGGED"] or grand["unpaired"] else 0


# ---------------------------------------------------------------------------
# pinned
# ---------------------------------------------------------------------------

def command_pinned(args) -> int:
    import ocr.native_text as native_text
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.inspect import inspect_pdf
    from ocr.pipeline import parse_statement
    from telemetry.record import classify_outcome
    from tools.desccols_movement import canonical, leaves

    with args.balance_csv.open(encoding="utf-8", newline="") as handle:
        pinned = sorted({row["path"] for row in csv.DictReader(handle)})
    print(f"pinned statements: {len(pinned)}")

    real = native_text.parse_native_printed_rows

    def verdict(raw):
        document = parse_statement(raw, source_file="proofs.pdf",
                                   profile=inspect_pdf(raw), force_ocr=False,
                                   allow_local_ocr=False, allow_visual_ocr=False)
        if document is None:
            return None
        return report_to_dict(analyze_markdown(
            document.to_markdown(), parse_mode="deterministic",
            sheets=list(document.pages)))

    counts = collections.Counter()
    for relative in pinned:
        pdf = args.corpus / relative
        if not pdf.exists():
            counts["missing"] += 1
            continue
        raw = pdf.read_bytes()
        document = native_statement(raw)
        if document is None or document.model != CLAIMED_MODEL:
            counts["not_claimed"] += 1
            continue
        counts["claimed"] += 1
        # The card names every mover by content_sha256; a pinned document is
        # named by the same identity as an archive one, and the 8-hex prefix
        # is what the log carries.
        sha = hashlib.sha256(raw).hexdigest().upper()
        native_text.parse_native_printed_rows = lambda *a, **k: None
        native_text.clear_page_caches()
        before = verdict(raw)
        native_text.parse_native_printed_rows = real
        native_text.clear_page_caches()
        after = verdict(raw)
        if before is None or after is None:
            counts["unresolved"] += 1
            continue
        old, new = leaves(before), leaves(after)
        moved = sorted(path for path in set(old) | set(new)
                       if canonical(old.get(path, "\x00"))
                       != canonical(new.get(path, "\x00")))
        outcomes = (classify_outcome(before)[0], classify_outcome(after)[0])
        if outcomes[0] != outcomes[1]:
            counts["OUTCOME_MOVED"] += 1
        counts["leaves_moved"] += len(moved)
        print(f"claimed  {sha[:8]}  outcome {outcomes[0]} -> {outcomes[1]}  "
              f"leaves_moved={len(moved)}  {sorted(set(moved))}")
    native_text.parse_native_printed_rows = real
    print(json.dumps(dict(counts), sort_keys=True))
    return 1 if counts["OUTCOME_MOVED"] else 0


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------

def command_fallback(args) -> int:
    import ocr.native_text as native_text
    from webapp.artifact_cache import analysis_input_sha

    paths = _paths(args.rows)
    real = native_text.parse_native_printed_rows

    def key(pdf: Path):
        native_text.clear_page_caches()
        markdown, pages, model = _repaired_markdown(pdf)
        return (None, None) if markdown is None else (
            analysis_input_sha(markdown, pages), model)

    counts = collections.Counter()
    for sha in sorted(paths)[::args.stride]:
        pdf = args.corpus / paths[sha]
        if not pdf.exists():
            continue
        counts["sample"] += 1
        native_text.parse_native_printed_rows = lambda *a, **k: None
        before, _mb = key(pdf)
        native_text.parse_native_printed_rows = real
        after, model = key(pdf)
        if before is None and after is None:
            counts["no_native_text"] += 1
        elif model == CLAIMED_MODEL:
            counts["claimed"] += 1
        elif before == after:
            counts["analysis_input_identical"] += 1
        else:
            counts["ANALYSIS_INPUT_DIFFERENT"] += 1
            print("UNEXPECTED INPUT MOVE", sha)
    native_text.parse_native_printed_rows = real
    print(json.dumps(dict(counts), sort_keys=True))
    return 1 if counts["ANALYSIS_INPUT_DIFFERENT"] else 0


# ---------------------------------------------------------------------------
# boundary
# ---------------------------------------------------------------------------

def command_boundary(args) -> int:
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from tools.desccols_movement import stored_document

    paths = _paths(args.rows)
    root = args.data_dir / "artifacts"
    baseline = args.baseline_settings_key.strip().upper()
    counts = collections.Counter()
    for sha in sorted(paths):
        pdf = args.corpus / paths[sha]
        if not pdf.exists():
            continue
        markdown, pages, model = _repaired_markdown(pdf)
        if model != CLAIMED_MODEL:
            continue
        _stored_pages, _stored_model, before = stored_document(sha, root, baseline)
        if before is not None:
            counts["had_a_payload"] += 1
            continue
        counts["no_stored_payload"] += 1
        try:
            report_to_dict(analyze_markdown(markdown, parse_mode="deterministic",
                                            sheets=pages))
        except Exception:  # noqa: BLE001 — refusing again is the expected answer
            counts["still_refuses"] += 1
            continue
        counts["NO_PAYLOAD_NOW_PUBLISHES"] += 1
        print("NOW PUBLISHES", sha)
    print(json.dumps(dict(counts), sort_keys=True))
    return 1 if counts["NO_PAYLOAD_NOW_PUBLISHES"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command",
                        choices=("oracle", "furniture", "pinned", "fallback",
                                 "boundary"))
    parser.add_argument("--rows", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", default="")
    parser.add_argument("--balance-csv", type=Path,
                        default=Path("docs/balance-metrics-audit-results.csv"))
    parser.add_argument("--stride", type=int, default=7)
    parser.add_argument("--shipped", action="store_true",
                        help="oracle: score the run's own stored text instead")
    args = parser.parse_args(argv)
    return {"oracle": command_oracle, "furniture": command_furniture,
            "pinned": command_pinned, "fallback": command_fallback,
            "boundary": command_boundary}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
