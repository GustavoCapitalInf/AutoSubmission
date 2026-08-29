"""L1-ARCH-DESIGN instrument 3 — READ-ONLY payload-reader response probe.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**

The design claims that a multi-account payload must NOT carry a top-level
`statement` key, because a consumer reading `payload["statement"]` on a
document with three accounts reads one of them and calls it the document —
which is the L-1 defect itself, moved out of the parser and into the payload.

That claim has a second half, and the second half is the one that decides the
delivery order: **what does each payload reader DO when it meets a shape it
was not taught?** If every reader raises, an untaught reader is a loud bug and
the order of the implementation slices barely matters. If some readers answer
— quietly, with a wrong answer — then no multi-account payload may be
published until every reader has been taught, and the design has to say so.

This instrument answers that by CALLING them. It builds one document-shaped
payload out of one real single-account `Report` (so nothing is invented) and
hands it to every payload reader that is a pure function of the payload dict.
Each response is classified:

  `raises`
      loud and fail-closed: the reader refuses a shape it does not know.
  `answers`
      the reader returns a value. Whether that value is RIGHT is then the
      question, and for the readers below it is not: the probe reports the
      answer's CLASS (an outcome token, an emptied view), never its content.

A third variant is measured because it is the shim Option D would need: the
document shape with a top-level `statement` put back, pointing at the first
account. Every reader then answers, and answers about one account. That is
the measurement that makes "publish one, carry the rest" a defect rather than
a preference.

PRIVACY
-------
Reader names, response classes and one outcome token per reader. No payload
content is printed: the probe reports whether a rebuilt view is EMPTY, never
what was in it.

Usage:

    python -m tools.l1_design_reader_probe --run <run dir> --data-dir <cold cache> \
        [--sha <content sha256>] [--json <private>.json]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cohort_replay import ColdCache, load_baseline_rows  # noqa: E402
from tools.l1_design_payload_probe import (  # noqa: E402
    DocumentReport,
    classify_document,
    document_to_payload_unconditional,
)


def _shape_variants(report) -> dict[str, dict]:
    from analysis.serialization import report_to_dict

    baseline = json.loads(json.dumps(report_to_dict(report), sort_keys=True, default=str))
    doc = DocumentReport(accounts=[report], boundary_mechanism="rollup-oracle")
    document = json.loads(json.dumps(
        document_to_payload_unconditional(doc, report_to_dict), sort_keys=True, default=str))
    shim = copy.deepcopy(document)
    # Option D's compatibility shim: the document shape with the FIRST account
    # promoted back to the key every reader already reads.
    shim["statement"] = copy.deepcopy(document["accounts"][0]["statement"])
    for key in ("metrics", "quality", "integrity", "reconciliation",
                "classifications", "detection"):
        shim[key] = copy.deepcopy(document["accounts"][0][key])
    return {"baseline": baseline, "document": document, "shim": shim}


# ---------------------------------------------------------------------------
# the readers, each a pure function of the payload dict
# ---------------------------------------------------------------------------


def _reader_classify_outcome(payload: dict) -> str:
    from telemetry.record import classify_outcome

    klass, reason = classify_outcome(copy.deepcopy(payload))
    return f"{klass}/{reason}"


def _reader_classify_document(payload: dict) -> str:
    """The design's own function, for contrast: it is taught the shape."""
    from telemetry.record import classify_outcome

    klass, reason = classify_document(copy.deepcopy(payload), classify_outcome)
    return f"{klass}/{reason}"


def _reader_revenue_views(payload: dict) -> str:
    from analysis.revenue import rebuild_serialized_revenue_views

    out = rebuild_serialized_revenue_views(copy.deepcopy(payload))
    statement = out.get("statement") or {}
    transactions = statement.get("transactions") or []
    metrics = out.get("metrics") or {}
    return (f"rebuilt over {len(transactions)} transaction(s); "
            f"verified_revenue_total is "
            f"{'absent' if 'verified_revenue_total' not in metrics else 'present'}")


def _reader_analysis_rows(payload: dict) -> str:
    from webapp.app import _analysis_rows

    rows = _analysis_rows(copy.deepcopy(payload))
    return f"{len(rows)} export row(s)"


def _reader_adb_rows(payload: dict) -> str:
    from webapp.app import _adb_rows

    rows = _adb_rows(copy.deepcopy(payload))
    return f"{len(rows)} ADB row(s)"


def _reader_masked(payload: dict) -> str:
    from webapp.app import _masked

    out = _masked(copy.deepcopy(payload))
    return f"{len(out)} top-level key(s) returned"


READERS = (
    ("telemetry/record.py::classify_outcome", _reader_classify_outcome),
    ("(design) classify_document", _reader_classify_document),
    ("analysis/revenue.py::rebuild_serialized_revenue_views", _reader_revenue_views),
    ("webapp/app.py::_analysis_rows (CSV/XLSX export)", _reader_analysis_rows),
    ("webapp/app.py::_adb_rows (ADB export)", _reader_adb_rows),
    ("webapp/app.py::_masked (the /analysis route)", _reader_masked),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 design payload-reader probe")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--sha", help="content sha256; default: the first validated document")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    rows = load_baseline_rows(args.run)
    sha = (args.sha or "").upper() or next(
        sha for sha in sorted(rows)
        if (rows[sha].get("outcome_class") or "") == "validated")
    cache = ColdCache(args.data_dir)
    markdown, pages = cache.text(sha)
    if markdown is None:
        print(f"no cached text for {sha[:16]}")
        return 2

    from analysis.pipeline import analyze_markdown

    report = analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
    variants = _shape_variants(report)

    print("# L1-ARCH-DESIGN — payload-reader response probe")
    print()
    print(f"One real `validated` document (`{sha[:16]}`, registration "
          f"`{rows[sha].get('parser_id') or '?'}`), analysed once and offered "
          f"to each reader in three payload shapes. `baseline` is today's "
          f"payload; `document` is the design's multi-account shape "
          f"(`document` + `accounts`, no top-level `statement`); `shim` is "
          f"that shape with the first account promoted back to `statement`, "
          f"which is what a compatibility layer would do.")
    print()
    print("| payload reader | `baseline` | `document` | `shim` |")
    print("|---|---|---|---|")
    results: dict[str, dict[str, str]] = {}
    for name, reader in READERS:
        row: dict[str, str] = {}
        for shape in ("baseline", "document", "shim"):
            try:
                row[shape] = reader(variants[shape])
            except Exception as exc:
                row[shape] = f"RAISES {type(exc).__name__}"
        results[name] = row
        print(f"| `{name}` | {row['baseline']} | {row['document']} | {row['shim']} |")
    print()

    loud = sum(1 for row in results.values() if row["document"].startswith("RAISES"))
    quiet = len(results) - loud
    shim_loud = sum(1 for row in results.values() if row["shim"].startswith("RAISES"))
    print("| measure | value |")
    print("|---|---:|")
    print(f"| payload readers probed | {len(results)} |")
    print(f"| ... that REFUSE the document shape (loud, fail-closed) | {loud} |")
    print(f"| ... that ANSWER a shape they were not taught (quiet) | **{quiet}** |")
    print(f"| ... that refuse the Option-D shim | **{shim_loud}** |")
    print()
    print("The last row is the finding. A shim that puts one account back "
          "under `statement` makes every untaught reader answer, and answer "
          "about one account of several — silently, on every surface, "
          "forever. The design refuses the shim for that reason and requires "
          "every reader to be taught BEFORE the first document publishes two "
          "accounts, because the untaught failure is not loud either.")
    print()
    print("Readers that are NOT pure functions of the payload dict are not "
          "probed here and are named in the design's surface table by file "
          "and line: `webapp/app.py::_package_analysis` (needs Job objects), "
          "`discovery/runner.py` and `corpus_gate.py` (inline "
          "`payload[\"statement\"][...]` reads), `webapp/jobs.py::"
          "_classification_for`, `webapp/static/app.js::renderAnalysis`.")

    if args.json:
        args.json.write_text(json.dumps({
            "sha16": sha[:16],
            "parser_id": rows[sha].get("parser_id"),
            "results": results,
            "document_shape_loud": loud,
            "document_shape_quiet": quiet,
            "shim_loud": shim_loud,
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
