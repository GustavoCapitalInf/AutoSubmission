"""L1-ARCH-DESIGN instrument 3 — READ-ONLY payload-reader response probe,
plus the `analyze_markdown` -> `report_to_dict` SEAM CENSUS.

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

WHAT THE REVIEW ADDED (BLOCK-3)
-------------------------------
The first version of this probe measured SIX readers and the design stated its
ordering constraint as a universal quantifier over "every payload reader" — an
unstated set. The review found five more by the probe's own criterion. All
eleven are here now, and the design's exit criterion for the "teach the
surfaces dark" stage is no longer a universal quantifier: it is
`READERS` below, plus `SEAMS` below, both of which are CHECKED.

`--census` is what makes the zero non-vacuous. There are nine production call
sites pairing `analyze_markdown` with `report_to_dict`, and each must move to
the document entry point or a multi-account document publishes one account
through the old seam. The census greps the tree for them and compares what it
finds against the declared list: an undeclared seam, or a declared seam that
has moved, makes this instrument EXIT NON-ZERO. A list that cannot fail is not
an exit criterion.

PRIVACY
-------
Reader names, response classes and one outcome token per reader. No payload
content is printed: the probe reports whether a rebuilt view is EMPTY, never
what was in it.

Usage:

    python -m tools.l1_design_reader_probe --run <run dir> --data-dir <cold cache> \
        [--sha <content sha256>] [--json <private>.json]
    python -m tools.l1_design_reader_probe --census        # the seam census alone
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cohort_replay import ColdCache, load_baseline_rows  # noqa: E402
from tools.l1_design_payload_probe import (  # noqa: E402
    DocumentReport,
    classify_document,
    document_to_payload_unconditional,
)


REPO = Path(__file__).resolve().parent.parent


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
    return f"rebuilt over {len(transactions)} transaction(s)"


def _reader_analysis_rows(payload: dict) -> str:
    from webapp.app import _analysis_rows

    return f"{len(_analysis_rows(copy.deepcopy(payload)))} export row(s)"


def _reader_adb_rows(payload: dict) -> str:
    from webapp.app import _adb_rows

    return f"{len(_adb_rows(copy.deepcopy(payload)))} ADB row(s)"


def _reader_masked(payload: dict) -> str:
    from webapp.app import _masked

    return f"{len(_masked(copy.deepcopy(payload)))} top-level key(s)"


# ---- the five the review found, by the same criterion --------------------


def _reader_diagnose(payload: dict) -> str:
    """Wired into `telemetry/record.py::build_record`:417 — it rides in EVERY
    discovery telemetry record."""
    from telemetry.diagnostics import diagnose
    from telemetry.record import classify_outcome

    outcome, _reason = classify_outcome(copy.deepcopy(payload))
    result = diagnose(copy.deepcopy(payload), outcome)
    codes = result.get("codes") if isinstance(result, dict) else None
    evaluated = result.get("evaluated") if isinstance(result, dict) else None
    return f"{len(codes or ())} code(s), evaluated={evaluated}"


def _reader_stated_counts(payload: dict) -> str:
    from telemetry.stated_counts import evaluate

    observation = evaluate(copy.deepcopy(payload))
    # `DirectionObservation` carries the bank-STATED count, so only its two
    # enum tokens are projected. This instrument publishes classes, never
    # figures a document printed.
    credit = observation.credit
    return (f"{observation.transactions} transaction(s), "
            f"credit {credit.result}/{credit.reason}")


def _reader_ourside(payload: dict) -> str:
    from benchmark.ourside import OurFileResult

    result = OurFileResult(relative_path="probe.pdf", source_type="digital/native",
                           markdown="", payload=copy.deepcopy(payload))
    return (f"{len(result.statement)} statement / {len(result.metrics)} metrics / "
            f"{len(result.reconciliation)} reconciliation key(s)")


def _reader_forensic_production(payload: dict) -> str:
    """`balance_forensic_audit.py`:528-529 indexes rather than `.get()`s."""
    statement = payload["statement"]
    return (f"opening {'present' if 'beginning_balance' in statement else 'absent'}, "
            f"ending {'present' if 'ending_balance' in statement else 'absent'}")


def _reader_production_verdict(payload: dict) -> str:
    """The `_Verdict` `corpus_gate.py::production_verdict`:1358-1366 builds."""
    from telemetry.record import classify_outcome

    outcome, _reason = classify_outcome(copy.deepcopy(payload))
    integrity = payload.get("integrity") or {}
    return (f"_Verdict({outcome!r}, flags {len(integrity.get('flags') or ())}, "
            f"risk {str(integrity.get('risk_level') or '')!r})")


READERS = (
    ("telemetry/record.py::classify_outcome", _reader_classify_outcome),
    ("(design) classify_document", _reader_classify_document),
    ("telemetry/diagnostics.py::diagnose (in every telemetry record)", _reader_diagnose),
    ("telemetry/stated_counts.py::evaluate", _reader_stated_counts),
    ("analysis/revenue.py::rebuild_serialized_revenue_views", _reader_revenue_views),
    ("webapp/app.py::_analysis_rows (CSV/XLSX export)", _reader_analysis_rows),
    ("webapp/app.py::_adb_rows (ADB export)", _reader_adb_rows),
    ("webapp/app.py::_masked (the /analysis route)", _reader_masked),
    ("benchmark/ourside.py::OurFileResult.statement/.metrics/.reconciliation", _reader_ourside),
    ("balance_forensic_audit.py:528-529 (indexes `payload['statement']`)",
     _reader_forensic_production),
    ("corpus_gate.py::production_verdict -> _Verdict", _reader_production_verdict),
)


# ---------------------------------------------------------------------------
# the seam census — every `analyze_markdown` -> `report_to_dict` call site
# ---------------------------------------------------------------------------
#
# Nine, measured at this base. Each must move to the document entry point or a
# multi-account document publishes ONE account through the old seam. The list
# is checked against the tree, so it cannot quietly go stale.

#: Line numbers are at the tree that declares them and are re-read at every
#: closure: L1-S3 moved all nine to `document_report_to_dict`, which is what
#: this census is here to make checkable.
SEAMS: tuple[tuple[str, int, str], ...] = (
    ("discovery/runner.py", 503, "the discovery run"),
    ("corpus_gate.py", 1549, "production_verdict — the pinned corpus"),
    ("benchmark/ourside.py", 117, "the benchmark's production side"),
    ("batch.py", 185, "the batch CLI"),
    ("balance_forensic_audit.py", 515, "the balance forensic audit"),
    ("webapp/artifact_cache.py", 215, "the analysis cache — every web upload"),
    ("analyze.py", 176, "the CLI"),
    ("webapp/worker.py", 36, "the web worker"),
    ("adb_forensic_audit.py", 492, "the ADB forensic audit"),
)

#: The module that DEFINES the publisher is not one of its call sites. Its
#: three matches are `def document_report_to_dict`, RULE S's verbatim return
#: and the per-account list comprehension — the implementation, not a seam.
PUBLISHER_MODULE = "analysis/serialization.py"

_SEAM_RE = re.compile(r"report_to_dict\(")


def census_seams() -> tuple[list[tuple[str, int]], list[tuple[str, int]], list[str]]:
    """(found, undeclared, missing) — the census, checked both ways."""
    out = subprocess.run(
        ["git", "grep", "-n", "report_to_dict(", "--", "*.py"],
        cwd=REPO, capture_output=True, text=True, check=False)
    found: list[tuple[str, int]] = []
    for line in out.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, lineno, text = parts[0], int(parts[1]), parts[2]
        if path.startswith(("tools/", "tests/")) or path == PUBLISHER_MODULE:
            continue
        if "def report_to_dict" in text or "import" in text:
            continue
        if not _SEAM_RE.search(text):
            continue
        found.append((path, lineno))
    declared = {(path, lineno) for path, lineno, _why in SEAMS}
    undeclared = sorted(set(found) - declared)
    missing = [f"{path}:{lineno}" for path, lineno, _why in SEAMS
               if (path, lineno) not in set(found)]
    return sorted(found), undeclared, missing


def print_census() -> int:
    found, undeclared, missing = census_seams()
    print("## The `analyze_markdown` -> `report_to_dict` seam census")
    print()
    print("Every production call site that turns a `Report` into the published "
          "payload. Each must move to the document entry point, or a "
          "multi-account document publishes ONE account through the old seam. "
          "The declared list is checked against the tree in BOTH directions, "
          "so it cannot go stale without this instrument failing.")
    print()
    print("| seam | what it feeds |")
    print("|---|---|")
    for path, lineno, why in SEAMS:
        print(f"| `{path}`:{lineno} | {why} |")
    print(f"| **declared** | **{len(SEAMS)}** |")
    print()
    print("| check | result |")
    print("|---|---|")
    print(f"| call sites found in the tree | {len(found)} |")
    print(f"| declared but NOT found (moved or removed) | "
          f"{len(missing)}{'' if not missing else ' — ' + ', '.join(missing)} |")
    print(f"| found but NOT declared (a new seam) | "
          f"{len(undeclared)}{'' if not undeclared else ' — ' + ', '.join(f'{p}:{n}' for p, n in undeclared)} |")
    print()
    if undeclared or missing:
        print("**CENSUS FAILS.** The list and the tree disagree; the exit "
              "criterion built on this list is not safe to use until they are "
              "reconciled.")
        return 1
    print("**CENSUS HOLDS** at this tree: the declared list is exactly the "
          "tree's, both ways.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 design payload-reader probe")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--sha", help="content sha256; default: the first validated document")
    parser.add_argument("--census", action="store_true",
                        help="run the seam census alone and exit")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    if args.census:
        print("# L1-ARCH-DESIGN — seam census")
        print()
        return print_census()

    if args.run is None or args.data_dir is None:
        parser.error("--run and --data-dir are required unless --census is given")

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

    # `classify_document` is the design's own, taught function: it is measured
    # for contrast and is not part of the census of readers that exist TODAY.
    census = {name: row for name, row in results.items()
              if not name.startswith("(design)")}
    loud = sum(1 for row in census.values() if row["document"].startswith("RAISES"))
    quiet = len(census) - loud
    shim_loud = sum(1 for row in census.values() if row["shim"].startswith("RAISES"))
    print("| measure | value |")
    print("|---|---:|")
    print(f"| payload readers probed (excluding the design's own) | {len(census)} |")
    print(f"| ... that REFUSE the document shape (loud, fail-closed) | **{loud}** |")
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

    code = print_census()

    if args.json:
        args.json.write_text(json.dumps({
            "sha16": sha[:16],
            "parser_id": rows[sha].get("parser_id"),
            "results": results,
            "readers_probed": len(census),
            "document_shape_loud": loud,
            "document_shape_quiet": quiet,
            "shim_loud": shim_loud,
            "seams_declared": len(SEAMS),
            "census_exit": code,
        }, indent=1), encoding="utf-8")
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
