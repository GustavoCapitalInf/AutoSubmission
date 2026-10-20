"""What the printed-row rung changes: which documents it claims, and what moves.

W3 §DESCCOLS' movement instrument. `tools.regfp_zero_movement_sweep` answers
the archive question — does any published analysis differ from what the run of
record stored — and reports FIELD names. This tool answers the two questions a
card that moves a field on purpose owes on top of that:

1. **REACH.** For every document, does `ocr.native_text.native_statement` at
   this tree still produce the text the run of record's own OCR artifact
   holds? A document whose pages come back identical keeps a byte-identical
   analysis INPUT, so its cache key cannot rotate — that is the fallback
   proof, and it is MEASURED against the archive per document rather than
   argued. The ladder is BOUND, never recomposed, and no rung is called here:
   `tests/test_native_rung_parity.py` is what says an instrument that reads
   different bytes than production is not an instrument.
2. **MOVEMENT.** For the documents it does claim, the published payload
   recomputed from the new text, compared to the stored one twice: once with
   every `description` leaf MASKED — so amounts, dates, directions, counts,
   totals, the grid, the ADB, the verdict and the flags are all inside the
   comparison — and once on the description leaves alone, reported as classes
   (`shortened` / `lengthened` / `replaced`) with LENGTHS.

    python -m tools.desccols_movement --rows <run>/rows.csv \
        --data-dir <checkout>/webapp_data --corpus "<checkout>/Bank Statements" \
        --baseline-settings-key <64 hex> [--start 0 --end 3380] [--out m.json]

READ-ONLY and $0, by the same construction as the sweep beside it: the
`webapp_data` sqlite index is never opened, artifacts are reached by direct
file path, the OCR artifact compared against is the one whose reconstruction
resolves the run's own stored analysis payload, the PDFs are opened read-only,
and `parse_mode="deterministic"` cannot reach the extraction branch.

**It prints no document text and no figure**: every field of the output is a
count, a class, a LENGTH, a leaf path or a `content_sha256`.

Exit 1 whenever it finds any movement at all, so a proof log cannot record a
zero it did not measure.
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
import time
from pathlib import Path

from ocr.native_text import native_statement

#: The model label the rung this card adds stamps on a document it claims.
CLAIMED_MODEL = "native-pdf-text+printed-rows"
DESCRIPTION_LEAF = "description"
MASK = "\x00masked\x00"
ABSENT = "\x00absent\x00"


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def leaves(node: object, path: str = "") -> dict[str, object]:
    """Every scalar of a payload by its path; a tuple is a list here.

    The stored artifact is JSON and the recompute is the in-memory object, so
    the same field arrives as `[...]` from one side and `(...)` from the
    other. Treating those apart would report every sequence in every payload
    as a mover and drown the finding this tool exists to make.
    """
    out: dict[str, object] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            out.update(leaves(value, f"{path}.{key}"))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            out.update(leaves(value, f"{path}[{index}]"))
    else:
        out[path] = node
    return out


def masked(payload: object) -> object:
    if isinstance(payload, dict):
        return {key: (MASK if key == DESCRIPTION_LEAF else masked(value))
                for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [masked(value) for value in payload]
    return payload


def stored_document(sha: str, root: Path, baseline: str):
    """(pages, model, stored analysis) for the artifact the run itself used."""
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )
    candidates = []
    for flags in itertools.product((False, True), repeat=3):
        key = ocr_settings_key(force_ocr=flags[0], allow_local_ocr=flags[1],
                               allow_visual_ocr=flags[2])
        composed = cache_key(STAGE_OCR, sha, key)
        path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            continue
        pages = [str(page) for page in (document.get("pages") or [])]
        candidates.append((pages, str(document.get("model") or "")))
    for pages, model in candidates:
        markdown = StatementMarkdown(source_file="movement.pdf", model=model,
                                     pages=pages).to_markdown()
        composed = cache_key(STAGE_ANALYSIS, analysis_input_sha(markdown, pages),
                             baseline)
        stored = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
        if stored.exists():
            analysis = json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
            return pages, model, analysis
    if candidates:
        return candidates[0][0], candidates[0][1], None
    return None, None, None


#: The leaf-path markers the required-check vector is read off. Every one is a
#: check, a flag, a note, a verdict input or an ADB value the platform will not
#: move outside a ceremony; the vector is the count of MOVED leaf paths under
#: each, over every document compared, and it is printed with the counts so a
#: reader re-derives "0 verdict movement" rather than believing it.
REQUIRED_CHECK_MARKERS = (
    ".checks", ".integrity", ".flags", ".notes", ".risk",
    ".possible_document_issue", ".warnings", ".outcome", ".reconciliation",
    ".escalat", ".model_used", ".parsed_posting_days", ".missing_posting_dates",
    ".posting_dates_cover_source", ".metrics.adb",
)


def required_check_vector(paths) -> dict[str, int]:
    """How many moved leaf paths sit under each required-check marker."""
    vector = {marker: 0 for marker in REQUIRED_CHECK_MARKERS}
    for path in paths:
        for marker in REQUIRED_CHECK_MARKERS:
            if marker in path:
                vector[marker] += 1
    return vector


def base_module(commit: str = "10cc722"):
    """`ocr/native_text.py` AS OF `commit`, loaded as its own module.

    The fallback claim is that a document this rung does not claim comes out of
    the LADDER byte-identical to what the ladder gave before the branch
    existed. Proving that against a monkeypatched rung proves something weaker
    — that the rung returns None — so the comparison here is against the module
    the base commit actually holds, read out of its git blob and imported
    beside the branch's own.
    """
    import importlib.util
    import subprocess
    import tempfile

    blob = subprocess.run(["git", "show", f"{commit}:ocr/native_text.py"],
                          capture_output=True, check=True)
    handle = tempfile.NamedTemporaryFile("wb", suffix="_base_native_text.py",
                                         delete=False)
    with handle:
        handle.write(blob.stdout)
    # Loaded INSIDE the `ocr` package: the module's imports are relative
    # (`from .column_grid import …`), so a top-level name cannot resolve them.
    # It is not registered in `sys.modules`, so `ocr.native_text` at this tree
    # stays exactly what production imports.
    import ocr  # noqa: F401 — the parent package must be imported first

    spec = importlib.util.spec_from_file_location("ocr._desccols_base_native_text",
                                                  handle.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command_fallback(args) -> int:
    """The fail-closed half, BASE GIT BLOB against branch, on one tree.

    For every sampled document: the base ladder's pages and the branch
    ladder's pages, and the `analysis_input_sha` each produces — the hash that
    decides whether a document's analysis cache key rotates.
    """
    from webapp.artifact_cache import analysis_input_sha
    from ocr.document import StatementMarkdown
    import ocr.native_text as branch

    base = base_module(args.base)
    paths = document_paths(args.rows)[0]
    counts = collections.Counter()
    began = time.time()
    for sha in sorted(paths)[::args.stride]:
        pdf = args.corpus / paths[sha]
        if not pdf.exists():
            continue
        counts["sample"] += 1
        raw = pdf.read_bytes()
        base._native_pages_cached.cache_clear()
        was = base.native_statement(raw)
        branch.clear_page_caches()
        now = branch.native_statement(raw)
        if was is None and now is None:
            counts["no_native_text"] += 1
            continue
        if was is None or now is None:
            counts["LADDER_APPEARED_OR_VANISHED"] += 1
            print("UNEXPECTED", sha)
            continue
        if now.model == CLAIMED_MODEL:
            counts["claimed"] += 1
            continue
        def key(document):
            pages = list(document.pages)
            markdown = StatementMarkdown(source_file="movement.pdf",
                                         model=document.model,
                                         pages=pages).to_markdown()
            return list(pages), analysis_input_sha(markdown, pages)

        was_pages, was_key = key(was)
        now_pages, now_key = key(now)
        if was_pages == now_pages and was_key == now_key:
            counts["identical"] += 1
        else:
            counts["DIFFERENT"] += 1
            print("UNEXPECTED INPUT MOVE", sha)
    print(json.dumps(dict(counts), sort_keys=True))
    print(f"seconds={round(time.time() - began, 1)}")
    return 1 if counts["DIFFERENT"] or counts["LADDER_APPEARED_OR_VANISHED"] else 0


def command_gates(args) -> int:
    """What the two furniture gates refuse, region by region and band by band.

    Reads each page's boxes ONCE and asks the rung's own helpers twice: with
    the document's repeated-furniture marks, and with none. The difference is
    G9's cost. G10's is counted beside it by the extent predicate, which the
    instrument computes itself because a refusal from `_described_rows` does
    not say which gate made it.
    """
    import fitz
    import ocr.native_text as nt

    paths, _outcome, _parser = document_paths(args.rows)
    only = ({line.strip() for line in args.only.read_text(encoding="utf-8").split()}
            if args.only else None)
    counts = collections.Counter()
    shape = collections.Counter()
    documents = []
    began = time.time()
    for sha in sorted(paths)[args.start:args.end]:
        if only is not None and sha not in only:
            continue
        pdf = args.corpus / paths[sha]
        if not pdf.exists():
            continue
        counts["documents"] += 1
        raw = pdf.read_bytes()
        flat = nt._native_pages(raw)
        if flat is None:
            counts["no_native_text"] += 1
            continue
        with fitz.open(stream=raw, filetype="pdf") as document:
            printed = [nt._printed_lines(page) for page in document]
        if len(printed) > len(flat):
            counts["page_count_disagrees"] += 1
            continue
        marks = nt._repeated_furniture(printed)
        per = collections.Counter()
        for index, lines in enumerate(printed):
            if lines is None:
                # The F8 guard: a page whose boxes are malformed keeps the
                # flattening's own text. Counted, because a guard that fires on
                # this archive would be costing claims silently.
                per["pages_the_box_guard_refuses"] += 1
                continue
            if not lines:
                per["pages_with_no_printed_line"] += 1
                continue
            bands = nt._row_bands(lines)
            band_of = {p: b for b, band in enumerate(bands) for p in band}
            for end, starts in nt._candidate_regions(lines, bands):
                free = nt._described_rows(lines, bands, end, starts)
                if free is None:
                    # refused by G3/G4/G8/G10 together; the extent clause is
                    # asked on its own so G10 has a number of its own.
                    rows = [[p for band in range(start, (starts + [end])[order + 1])
                             for p in bands[band]]
                            for order, start in enumerate(starts)]
                    edges = [lines[p].right for row in rows for p in row
                             if nt._ROW_MONEY_RE.match(lines[p].text)]
                    if edges:
                        left = min(lines[row[0]].left for row in rows)
                        if any(lines[p].right < left - nt._ROW_COLUMN_TOLERANCE
                               or lines[p].left > max(edges) + nt._ROW_COLUMN_TOLERANCE
                               for row in rows for p in row):
                            per["regions_the_extent_clause_refuses"] += 1
                    continue
                per["regions_admitted_ignoring_furniture"] += 1
                marked = [p for row in free for p in row if p in marks[index]]
                if marked:
                    per["regions_G9_refuses"] += 1
                    per["bands_G9_refuses"] += len({band_of[p] for p in marked})
                    per["lines_marked_inside_a_region"] += len(marked)
                    # What KIND of line is being marked inside a ledger: how
                    # many pages print it at that band, and how long it is.
                    # Running furniture repeats on every page of a section; a
                    # coincidence repeats on two. Classes only, never text.
                    for position in marked:
                        line = lines[position]
                        pages_with = {
                            other for other, others in enumerate(printed)
                            for candidate in (others or ())
                            if candidate.text == line.text
                            and nt._shares_a_band(line.top, line.bottom,
                                                  candidate.top, candidate.bottom)}
                        shape[f"pages={min(len(pages_with), 6)}"] += 1
                        shape[f"tokens={min(len(line.text.split()), 6)}"] += 1
            with_gate = nt._printed_row_text(lines, flat[index], marks[index])
            without = nt._printed_row_text(lines, flat[index], frozenset())
            if with_gate != without:
                per["pages_the_furniture_gate_changes"] += 1
            for label, answer in (("", with_gate), ("_ignoring_furniture", without)):
                if answer is None:
                    per["pages_refusing_the_document" + label] += 1
                elif answer != flat[index]:
                    per["pages_repaired" + label] += 1
        # A document is claimed exactly as the rung claims it: no page refuses
        # the document, and at least one page changed.
        for label in ("", "_ignoring_furniture"):
            if per["pages_refusing_the_document" + label]:
                counts["refused_outright" + label] += 1
            elif per["pages_repaired" + label]:
                counts["claimed" + label] += 1
        claimed_now = (not per["pages_refusing_the_document"]
                       and per["pages_repaired"])
        claimed_before = (not per["pages_refusing_the_document_ignoring_furniture"]
                          and per["pages_repaired_ignoring_furniture"])
        if bool(claimed_now) != bool(claimed_before):
            counts["claim_gained" if claimed_now else "claim_lost"] += 1
        if per["pages_the_furniture_gate_changes"]:
            counts["documents_the_furniture_gate_changes"] += 1
            documents.append({"content_sha256": sha,
                              "claimed_now": bool(claimed_now),
                              "claimed_before": bool(claimed_before),
                              **{key: per[key] for key in sorted(per)}})
        counts.update(per)
    report = {"counts": dict(counts), "seconds": round(time.time() - began, 1),
              "marked_line_shape": dict(shape), "documents": documents}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True),
                            encoding="utf-8")
    print(json.dumps(dict(counts), sort_keys=True))
    print("marked_line_shape " + json.dumps(dict(shape), sort_keys=True))
    print(f"seconds={report['seconds']}")
    return 1 if counts["documents_the_furniture_gate_changes"] else 0


def document_paths(rows: Path):
    """(sha -> relative path, sha -> outcome class, sha -> parser id)."""
    paths, outcome, parser = {}, {}, {}
    with rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if sha and sha not in paths:
                paths[sha] = row["relative_path"]
                outcome[sha] = row["outcome_class"]
                parser[sha] = row["parser_id"]
    return paths, outcome, parser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", default="")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=10 ** 9)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--mode", choices=("movement", "gates", "fallback"),
                        default="movement")
    parser.add_argument("--stride", type=int, default=23,
                        help="fallback: sample every Nth document")
    parser.add_argument("--base", default="10cc722",
                        help="fallback: the commit whose module is the before half")
    parser.add_argument("--only", type=Path,
                        help="gates: a file of content_sha256 to restrict the census to")
    args = parser.parse_args(argv)
    if args.mode == "fallback":
        return command_fallback(args)
    if args.mode == "gates":
        return command_gates(args)
    if args.data_dir is None or not args.baseline_settings_key:
        parser.error("movement needs --data-dir and --baseline-settings-key")
    baseline = args.baseline_settings_key.strip().upper()

    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown

    paths, outcome, _parser = document_paths(args.rows)

    counts = {"documents": 0, "ladder_unchanged": 0,
              "ladder_identical_to_the_archive": 0, "claimed": 0, "no_pdf": 0,
              "no_native_text": 0, "claimed_but_text_unchanged": 0,
              "no_payload": 0, "moved": 0, "payload_now_raises": 0,
              "other_movement": 0, "shortened": 0, "lengthened": 0,
              "replaced": 0}
    documents = []
    began = time.time()

    for sha in sorted(paths)[args.start:args.end]:
        pdf = args.corpus / paths[sha]
        if not pdf.exists():
            counts["no_pdf"] += 1
            continue
        counts["documents"] += 1
        ladder = native_statement(pdf.read_bytes())
        if ladder is None:
            counts["no_native_text"] += 1
            continue
        pages, model, before = stored_document(sha, args.data_dir / "artifacts", baseline)
        if ladder.model != CLAIMED_MODEL:
            # Every other rung is untouched by this card, so the ladder's
            # answer here is the one it always gave. Say so by MEASUREMENT
            # where the archive holds the text to say it against.
            counts["ladder_unchanged"] += 1
            if pages is not None and list(pages) == list(ladder.pages):
                counts["ladder_identical_to_the_archive"] += 1
            continue
        counts["claimed"] += 1

        record = {"content_sha256": sha, "outcome": outcome[sha],
                  "stored_model": model, "pages": len(ladder.pages)}
        if pages is not None and list(pages) == list(ladder.pages):
            counts["claimed_but_text_unchanged"] += 1
            record["verdict"] = "claimed_but_text_unchanged"
            documents.append(record)
            continue
        if before is None:
            counts["no_payload"] += 1
            record["verdict"] = "no_stored_payload"
            documents.append(record)
            continue

        markdown = StatementMarkdown(source_file="movement.pdf", model=ladder.model,
                                     pages=list(ladder.pages)).to_markdown()
        try:
            after = report_to_dict(analyze_markdown(markdown, parse_mode="deterministic",
                                                    sheets=list(ladder.pages)))
        except Exception as exc:  # noqa: BLE001 — the class IS the finding
            counts["payload_now_raises"] += 1
            record["verdict"] = f"payload_now_raises:{type(exc).__name__}"
            documents.append(record)
            continue

        before_masked, after_masked = leaves(masked(before)), leaves(masked(after))
        elsewhere = sorted(path for path in set(before_masked) | set(after_masked)
                           if canonical(before_masked.get(path, ABSENT))
                           != canonical(after_masked.get(path, ABSENT)))
        before_leaves = {p: v for p, v in leaves(before).items()
                         if p.endswith("." + DESCRIPTION_LEAF)}
        after_leaves = {p: v for p, v in leaves(after).items()
                        if p.endswith("." + DESCRIPTION_LEAF)}
        moved = []
        for path in sorted(set(before_leaves) | set(after_leaves)):
            old, new = before_leaves.get(path), after_leaves.get(path)
            if old == new:
                continue
            if isinstance(old, str) and isinstance(new, str) and old.startswith(new):
                kind = "shortened"
            elif isinstance(old, str) and isinstance(new, str) and new.startswith(old):
                kind = "lengthened"
            else:
                kind = "replaced"
            counts[kind] += 1
            moved.append({"path": path, "class": kind,
                          "before_len": len(old) if isinstance(old, str) else None,
                          "after_len": len(new) if isinstance(new, str) else None})
        counts["other_movement"] += len(elsewhere)
        if moved or elsewhere:
            counts["moved"] += 1
        record.update({"verdict": "compared", "description_leaves_moved": len(moved),
                       "descriptions": moved,
                       "other_leaves_moved": len(elsewhere), "other_paths": elsewhere})
        documents.append(record)

    moved_paths = sorted({path for record in documents
                          for path in record.get("other_paths", ())})
    vector = required_check_vector(moved_paths)
    report = {"counts": counts, "seconds": round(time.time() - began, 1),
              "required_check_vector": vector,
              "moved_leaf_paths": moved_paths, "documents": documents}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(counts, sort_keys=True))
    print("required_check_vector " + json.dumps(vector, sort_keys=True))
    print("moved_leaf_names " + json.dumps(
        sorted({path.rsplit(".", 1)[-1] for path in moved_paths}), sort_keys=True))
    print(f"seconds={report['seconds']}")
    return 1 if counts["moved"] or counts["payload_now_raises"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
