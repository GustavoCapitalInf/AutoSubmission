"""Ground truth for description attribution, read from PDF word geometry.

W3 §DESCATTRIB's oracle, committed because the numbers in that section are only
as durable as the instrument that produced them (the review's MAJOR-2). The
flattened text layer a reader sees has lost the columns; the PDF has not. This
reads each row's TRUE description from the word coordinates and scores what the
readers publish against it.

    # DA2/DA3 — the per-document row classes and the exact/prefix/foreign score
    python -m tools.descattrib_oracle rows --rows <run>/rows.csv \
        --data-dir <checkout>/webapp_data --corpus "<checkout>/Bank Statements" \
        --baseline-settings-key <64 hex>

    # DA9 — the third reader of the complex, censused and not touched
    python -m tools.descattrib_oracle sectioned  <same arguments>

    # DA6 — which classifier detections the fix removes, and whether the text
    # they matched on was ever printed for the row they were attributed to
    python -m tools.descattrib_oracle detections <same arguments>

READ-ONLY and $0: the `webapp_data` sqlite index is never opened, OCR artifacts
are reached by direct file path and selected by the one whose reconstruction
resolves the run's own stored analysis payload, the PDFs are opened read-only,
and `parse_mode="deterministic"` cannot reach the extraction branch.

**It prints no document text and no figure.** Every output is a count, a class,
a length or a `content_sha256` — the same contract as the sweep beside it. The
oracle is test-side by construction: no reader can see a coordinate, and
nothing here is imported by `analysis/`.

WHY A GEOMETRY ORACLE IS TRUSTWORTHY HERE, stated so a reader can check it
rather than take it. It is validated before it is used: `rows` asserts that the
oracle's rows and the reader's rows agree 1:1 on (section, date, amount) in
document order for every row of every document, and refuses to score a document
where they do not. A wrong segmentation therefore cannot quietly produce a
score; it produces a refusal.
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

WS = re.compile(r"\s+")
#: The row date of the two `dated_cells` templates, and of the third one.
HYPHEN_DATE = re.compile(r"^(?:1[0-2]|0?[1-9])-(?:3[01]|[12][0-9]|0?[1-9])$")
SLASH_DATE = re.compile(r"^[0-9]{2}/[0-9]{2}$")
MONEY = re.compile(r"^(?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2})$")


@dataclass
class OracleRow:
    page: int
    section: str
    date: str
    amount: str
    described: str


def _mode(values):
    return collections.Counter(values).most_common(1)[0][0] if values else None


def _page_spans(page, section_names, carried):
    """(words, [(section, top, bottom), ...]) for one page, in document order."""
    words = [(round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2), text)
             for x0, y0, x1, y1, text, *_ in page.get_text("words")]
    bands = collections.defaultdict(list)
    for word in words:
        bands[round(word[1] / 3.0) * 3.0].append(word)
    marks = []
    for key in sorted(bands):
        line = " ".join(w[4] for w in sorted(bands[key], key=lambda w: w[0])).upper()
        for name in section_names:
            if name in line:
                marks.append((min(w[1] for w in bands[key]), name))
                break
    spans = []
    if not marks or marks[0][0] > 0:
        spans.append((carried, -1.0, marks[0][0] if marks else 1e4))
    for index, (y, name) in enumerate(marks):
        spans.append((name, y, marks[index + 1][0] if index + 1 < len(marks) else 1e4))
    return words, spans


def oracle_rows(path: str, section_names, ledger, *, date_re=HYPHEN_DATE,
                description_side: str = "right") -> list[OracleRow]:
    """Every ledger row the PDF prints, with the description it printed for it.

    `description_side` is the template's column order: `right` for the two
    `dated_cells` templates (`DATE DESCRIPTION AMOUNT`) and `left` for the
    third (`DESCRIPTION DATE AMOUNT`).
    """
    import fitz  # imported here so the module costs nothing to import

    document = fitz.open(path)
    pages, carried = [], None
    for index in range(document.page_count):
        words, spans = _page_spans(document[index], section_names, carried)
        if spans:
            carried = spans[-1][0]
        pages.append((index, words, spans))

    lefts, rights = [], []
    for _index, words, spans in pages:
        for name, top, bottom in spans:
            if name not in ledger:
                continue
            for word in words:
                if not top <= word[1] < bottom:
                    continue
                if date_re.match(word[4]):
                    lefts.append(round(word[0]))
                if MONEY.match(word[4]):
                    rights.append(round(word[2]))
    date_x, amount_x1 = _mode(lefts), _mode(rights)
    if date_x is None or amount_x1 is None:
        return []

    out: list[OracleRow] = []
    for index, words, spans in pages:
        for name, top, bottom in spans:
            if name not in ledger:
                continue
            inside = [w for w in words if top <= w[1] < bottom]
            dates = sorted((w for w in inside if date_re.match(w[4])
                            and abs(w[0] - date_x) < 3.0), key=lambda w: w[1])
            for position, dword in enumerate(dates):
                row_top = dword[1] - 1.5
                row_bottom = (dates[position + 1][1] - 1.5
                              if position + 1 < len(dates) else bottom)
                band = [w for w in inside
                        if row_top <= w[1] < row_bottom and w is not dword]
                amount = None
                for word in sorted(band, key=lambda w: (-w[1], -w[0])):
                    if MONEY.match(word[4]) and abs(round(word[2]) - amount_x1) < 4.0:
                        amount = word
                        break
                if amount is None:
                    out.append(OracleRow(index, name, dword[4], "", ""))
                    continue
                if description_side == "right":
                    described = [w for w in band if w is not amount and w[0] > dword[2]]
                else:
                    described = [w for w in band if w is not amount and w[0] < dword[0]]
                described.sort(key=lambda w: (round(w[1] / 3.0), w[0]))
                out.append(OracleRow(index, name, dword[4], amount[4],
                                     " ".join(w[4] for w in described)))
    return out


# ---------------------------------------------------------------------------
# The archive side: the text the run analysed, by direct path
# ---------------------------------------------------------------------------

def analysed_text(sha: str, data_dir: Path, baseline: str):
    """(markdown, pages, stored analysis payload or None) for one document."""
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )
    root = data_dir / "artifacts"
    keys = [ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
            for f, l, v in itertools.product((False, True), repeat=3)]
    candidates = []
    for key in keys:
        composed = cache_key(STAGE_OCR, sha, key)
        path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            continue
        pages = [str(page) for page in (document.get("pages") or [])]
        candidates.append((StatementMarkdown(
            source_file="oracle.pdf", model=str(document.get("model") or ""),
            pages=pages).to_markdown(), pages))
    if not candidates:
        return None, None, None
    for markdown, pages in candidates:
        composed = cache_key(STAGE_ANALYSIS, analysis_input_sha(markdown, pages), baseline)
        stored = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
        if stored.exists():
            analysis = json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
            return markdown, pages, analysis
    return candidates[0][0], candidates[0][1], None


def runs_in_document_order(markdown, section_re):
    marks = [(m.start(), m.end(), m.group(1)) for m in section_re.finditer(markdown)]
    for index, (_start, end, name) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(markdown)
        yield name, markdown[end:stop]


def population(rows_csv: Path, data_dir: Path, baseline: str, wanted_prefix="core_processor"):
    """{sha: (parser_id, relative_path)} by LIVE detection replay."""
    from analysis import parser_registry_entries  # noqa: F401 — registers
    from analysis.parser_registry import registrations, resolve
    assert registrations(), "empty registry"

    paths, order = {}, []
    with rows_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if sha and sha not in paths:
                paths[sha] = row["relative_path"]
                order.append(sha)
    found = {}
    for sha in sorted(order):
        markdown, _pages, _payload = analysed_text(sha, data_dir, baseline)
        if markdown is None:
            continue
        dispatch = resolve(markdown)
        if dispatch.parser_id and dispatch.parser_id.startswith(wanted_prefix):
            found[sha] = (dispatch.parser_id, paths[sha])
    return found


# ---------------------------------------------------------------------------
# rows — DA2/DA3
# ---------------------------------------------------------------------------

def _read_pairs(markdown, module):
    """[(section, [DatedCell, ...]), ...] over the DESCRIBED sections only."""
    from analysis.tables import dated_cells
    import analysis.core_processor_counted as CC
    if module is CC:
        described = {c.heading for c in CC._CATEGORIES if not c.serialled}
    else:
        described = {n for n, credit, _d in module._LEDGER_SECTIONS if credit is not None}
    out = []
    for name, run in runs_in_document_order(markdown, module._SECTION_RE):
        if name not in described:
            continue
        cells = dated_cells(run, date_pattern=module._DATE_RE,
                            value_pattern=module._FIGURE_RE)
        if cells is None:
            raise SystemExit(f"unreadable run {name}")
        out.append((name, cells))
    return out


def _classify(published: str, truth: str) -> str:
    if published == truth:
        return "exact"
    if truth.startswith(published) or published in truth:
        return "prefix"
    return "FOREIGN"


def command_rows(args) -> int:
    import analysis.core_processor_counted as CC
    import analysis.core_processor_daily as CD
    from analysis.tables import attributed_descriptions

    found = population(args.rows, args.data_dir, args.baseline_settings_key)
    total = collections.Counter()
    print(f"{'document':10} {'reader':8} {'rows':>5} {'label':>6} {'own':>4} "
          f"{'+N':>3} | {'exact':>6} {'prefix':>7} {'FOREIGN':>8}")
    for sha, (parser, relative) in sorted(found.items()):
        if parser == "core_processor_sectioned":
            continue
        module = CC if parser == "core_processor_counted" else CD
        markdown, _pages, _payload = analysed_text(sha, args.data_dir,
                                                   args.baseline_settings_key)
        pairs = _read_pairs(markdown, module)
        texts = {}
        for name in {n for n, _c in pairs}:
            runs = [cells for n, cells in pairs if n == name]
            texts[name] = attributed_descriptions(
                runs, strip=module._DESCRIPTION_FURNITURE,
                limit=module._DESCRIPTION_LIMIT)
        names = tuple(sorted(module._SECTION_NAMES, key=len, reverse=True))
        ledger = tuple(sorted({n for n, _c in pairs}))
        truth = oracle_rows(str(args.corpus / relative), names, ledger)

        flat, seen = [], collections.Counter()
        for name, cells in pairs:
            index = seen[name]
            seen[name] += 1
            for position, cell in enumerate(cells):
                flat.append((name, cell, texts[name][index][position]))
        if len(flat) != len(truth):
            print(f"{sha[:8]:10} {parser[15:]:8} UNPAIRED published={len(flat)} "
                  f"oracle={len(truth)} — not scored")
            total["unpaired_documents"] += 1
            continue
        counts = collections.Counter()
        for (name, cell, published), want in zip(flat, truth):
            assert (name, cell.date, cell.value) == (want.section, want.date, want.amount), (
                f"{sha}: the oracle and the reader disagree about a row")
            strip = module._DESCRIPTION_FURNITURE
            printed = WS.sub(" ", want.described).strip(strip).strip()
            counts[_classify(published, printed)] += 1
            label, _sep, flushed = cell.described.partition("\n")
            lines = [line for line in flushed.split("\n") if line.strip()]
            counts["label_only" if not lines
                   else ("own_block" if published != WS.sub(" ", label).strip(strip).strip()
                         else "indeterminate")] += 1
        print(f"{sha[:8]:10} {parser[15:]:8} {len(flat):5} {counts['label_only']:6} "
              f"{counts['own_block']:4} {counts['indeterminate']:3} | "
              f"{counts['exact']:6} {counts['prefix']:7} {counts['FOREIGN']:8}")
        total.update(counts)
        total["rows"] += len(flat)
    print(f"{'TOTAL':10} {'':8} {total['rows']:5} {total['label_only']:6} "
          f"{total['own_block']:4} {total['indeterminate']:3} | "
          f"{total['exact']:6} {total['prefix']:7} {total['FOREIGN']:8}")
    return 1 if total["FOREIGN"] or total["unpaired_documents"] else 0


# ---------------------------------------------------------------------------
# sectioned — DA9
# ---------------------------------------------------------------------------

def command_sectioned(args) -> int:
    import analysis.core_processor_sectioned as CS

    found = population(args.rows, args.data_dir, args.baseline_settings_key)
    names = tuple(sorted((n.upper() for n in CS._SECTION_NAMES), key=len, reverse=True))
    ledger = tuple(n for n, credit, _d in CS._LEDGER_SECTIONS if credit is not None)
    described = set(ledger)
    grand = collections.Counter()
    for sha, (parser, relative) in sorted(found.items()):
        if parser != "core_processor_sectioned":
            continue
        markdown, _pages, _payload = analysed_text(sha, args.data_dir,
                                                   args.baseline_settings_key)
        mine = []
        for name, run in runs_in_document_order(markdown, CS._SECTION_RE):
            if name not in described:
                continue
            cursor = 0
            for match in CS._ROW_RE.finditer(run):
                mine.append((name, match.group(1), match.group(2),
                             CS._printed_before(run[cursor:match.start()])))
                cursor = match.end()
        truth = oracle_rows(str(args.corpus / relative), names, ledger,
                            date_re=SLASH_DATE, description_side="left")
        if len(mine) != len(truth):
            print(f"{sha[:8]} UNPAIRED published={len(mine)} oracle={len(truth)}")
            grand["unpaired_documents"] += 1
            continue
        counts = collections.Counter()
        for (name, date, value, published), want in zip(mine, truth):
            if (date, value) != (want.date, want.amount):
                counts["misaligned"] += 1
                continue
            counts[_classify(WS.sub(" ", published).strip().upper(),
                             WS.sub(" ", want.described).strip().upper())] += 1
        print(f"{sha[:8]} rows={len(mine)} {dict(counts)}")
        grand.update(counts)
        grand["rows"] += len(mine)
    print("TOTAL", dict(grand))
    return 0


# ---------------------------------------------------------------------------
# detections — DA6
# ---------------------------------------------------------------------------

GROUPS = ("lender_evidence", "potential_lender_evidence", "insurance_evidence",
          "non_revenue_evidence")


def command_detections(args) -> int:
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    import analysis.core_processor_counted as CC
    import analysis.core_processor_daily as CD

    found = population(args.rows, args.data_dir, args.baseline_settings_key)
    grand = collections.Counter()
    for sha, (parser, relative) in sorted(found.items()):
        if parser == "core_processor_sectioned":
            continue
        module = CC if parser == "core_processor_counted" else CD
        markdown, pages, before = analysed_text(sha, args.data_dir,
                                                args.baseline_settings_key)
        if before is None:
            continue
        after = report_to_dict(
            analyze_markdown(markdown, parse_mode="deterministic", sheets=pages))
        names = tuple(sorted(module._SECTION_NAMES, key=len, reverse=True))
        pairs = _read_pairs(markdown, module)
        ledger = tuple(sorted({n for n, _c in pairs}))
        truth = {}
        for row in oracle_rows(str(args.corpus / relative), names, ledger):
            truth.setdefault((row.date, row.amount.replace(",", "")),
                             WS.sub(" ", row.described).upper())
        for group in GROUPS:
            kept = {(r["date"], r["amount"], r["canonical_entity"])
                    for r in (after["detection"].get(group) or [])
                    if isinstance(r, dict) and "canonical_entity" in r}
            for record in (before["detection"].get(group) or []):
                if not isinstance(record, dict) or "canonical_entity" not in record:
                    continue
                if (record["date"], record["amount"], record["canonical_entity"]) in kept:
                    continue
                month, day = record["date"][5:7], record["date"][8:10]
                key = None
                for (date, value) in truth:
                    parts = date.split("-")
                    if (f"{int(parts[0]):02d}", f"{int(parts[1]):02d}") == (month, day) \
                            and value == f"{abs(record['amount']):.2f}":
                        key = (date, value)
                        break
                printed = truth.get(key, "")
                alias = (record.get("matched_alias")
                         or record.get("canonical_entity") or "").upper()
                own = bool(alias) and alias in printed
                grand[(group, "own_text" if own else "not_the_rows_own_text")] += 1
                print(f"{sha[:8]} {group:26} REMOVED "
                      f"method={record.get('match_method')} "
                      f"alias_in_the_rows_own_printing={own}")
    print("TOTAL", {f"{g}:{k}": v for (g, k), v in sorted(grand.items())})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("rows", "sectioned", "detections"))
    parser.add_argument("--rows", required=True, type=Path, help="a run's rows.csv")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path,
                        help="the checkout's `Bank Statements` directory")
    parser.add_argument("--baseline-settings-key", required=True)
    args = parser.parse_args(argv)
    args.baseline_settings_key = args.baseline_settings_key.strip().upper()
    return {"rows": command_rows, "sectioned": command_sectioned,
            "detections": command_detections}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
