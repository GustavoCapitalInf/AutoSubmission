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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=10 ** 9)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    baseline = args.baseline_settings_key.strip().upper()

    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown

    paths, outcome = {}, {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if sha and sha not in paths:
                paths[sha] = row["relative_path"]
                outcome[sha] = row["outcome_class"]

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

    report = {"counts": counts, "seconds": round(time.time() - began, 1),
              "documents": documents}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(counts, sort_keys=True))
    print(f"seconds={report['seconds']}")
    return 1 if counts["moved"] or counts["payload_now_raises"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
