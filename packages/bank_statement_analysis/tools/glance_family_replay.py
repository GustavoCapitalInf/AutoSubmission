"""One card's whole population, replayed BASE against BRANCH in one process.

W3 §GLANCE, review closure 2 (and the instrument review finding 3 asked for).
The probe (`tools/glance_detection_probe.py`) answers what the registration
CLAIMS; this answers what changed for the documents it claims — the family it
was written for, the issuer cohort a `supersedes` edge routes elsewhere, and
the one pinned corpus document inside that cohort:

* every document's outcome CLASS and reason at both trees, in the vocabulary
  the discovery run itself records (`telemetry.record.classify_outcome` over
  the analysis payload, with `discovery/runner.py::_failure_reason`'s rule for
  the failures), so `failed/no_parser_matched` → `validated/approved` and
  `failed/no_parser_matched` → `failed/parser_declined` are told apart rather
  than both counted as movement;
* whether each document's PAYLOAD is byte-identical between the two trees, and
  whether it is byte-identical to the payload the run of record stored — the
  claim a `supersedes` edge has to earn is that the superseded documents did
  not move a field, and "the outcome class is the same" is not that claim;
* the dispatch each document takes at the branch tree, and whether it would
  resolve AMBIGUOUS with the edge removed — measured per document rather than
  asserted from the aggregate;
* two pieces of evidence about the printing itself that the record's own
  sentences depend on: how many documents print the bank's `Average Balance`
  entry MARKED with a trailing plus (the fourth sign case, review finding 4)
  and how many marked rows the sectioned ledger sections print at all (the
  reachability of the refusal added by review finding 5).

ONE PROCESS, TWO TREES. The base tree is materialised from git BLOBS — `git
archive <base> analysis` into a temporary directory — and the base arm runs
after the branch arm by purging every project package from `sys.modules` and
putting that directory first on `sys.path`. Nothing is checked out, no working
tree is touched, and the branch arm's texts are read before the switch so the
artifact reader is never the one that got swapped.

READ-ONLY and $0. OCR payloads are reached by DIRECT file path over every
capability partition of `ocr_settings_key` — the enumeration
`tools/regfp_zero_movement_sweep.py` established — and the `webapp_data`
sqlite index is never opened. `parse_mode="deterministic"` makes no model call.
Nothing is written except the report this tool prints.

    python -m tools.glance_family_replay \
        --rows <reports>/<run-id>/rows.csv --data-dir <checkout>/webapp_data \
        --baseline-settings-key <KEY> --base 10cc722 [--out replay.json]

NO ARCHIVE LITERAL LEAVES THIS TOOL. Documents are named by `content_sha256`
prefix; payloads are compared by digest; the only figures printed are counts.
The population is DERIVED rather than listed: the family by the eight
`content_sha256` prefixes W3 §GL1 already publishes, expanded against the run's
own rows (each must expand to exactly one document or the tool refuses), the
issuer cohort by the parser the run attributed, and the pinned document by
reading `tests/data/parser_expectations.json` for that same parser.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

#: W3 §GL1's eight, as the log publishes them. Prefixes, not shas: they are
#: expanded against the run of record and every one must be unique there.
FAMILY_PREFIXES = (
    "2065EFBD", "983F04D5", "A78F1E6A", "FC3FF0D3",
    "3A9502DF", "6E9A3A11", "889DAEBE", "C47BEFE5",
)

#: The project's own packages. Purged wholesale between the two arms: a module
#: left behind holds a direct reference to the tree it was imported from, and a
#: base `analysis.pipeline` importing a branch `telemetry` is neither tree.
PROJECT_PACKAGES = ("analysis", "ocr", "webapp", "discovery", "telemetry", "tests")


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def digest(text: str | None) -> str | None:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16].upper()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path, help="a run's rows.csv")
    parser.add_argument("--data-dir", required=True, type=Path,
                        help="the webapp_data directory of the same checkout")
    parser.add_argument("--baseline-settings-key", required=True,
                        help="the analysis settings key the run's payloads were written under")
    parser.add_argument("--base", default="10cc722",
                        help="the git ref whose `analysis` tree is the BASE arm")
    parser.add_argument("--issuer", default="wilson_muir",
                        help="the registration whose cohort the supersedes edge keeps")
    parser.add_argument("--superseder", default="category_partition",
                        help="the registration the edge supersedes")
    parser.add_argument("--expectations", type=Path,
                        default=Path("tests/data/parser_expectations.json"))
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# The population, derived from the run rather than listed
# ---------------------------------------------------------------------------

def population(args) -> tuple[dict[str, dict], list[str], list[str], list[str]]:
    rows: dict[str, dict[str, str]] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["content_sha256"]:
                rows.setdefault(row["content_sha256"], row)

    family: list[str] = []
    for prefix in FAMILY_PREFIXES:
        found = [sha for sha in rows if sha.startswith(prefix)]
        if len(found) != 1:
            raise SystemExit(f"{prefix} expands to {len(found)} documents, not one")
        family.append(found[0])

    cohort = sorted({
        sha for sha, row in rows.items() if row.get("parser_id") == args.issuer
    })

    pinned: list[str] = []
    if args.expectations.exists():
        documents = json.loads(args.expectations.read_text(encoding="utf-8"))["documents"]
        pinned = sorted({
            str(entry["sha256"]).upper()
            for entry in documents if entry.get("parser_id") == args.issuer
        })
    return rows, sorted(family), cohort, pinned


def texts_for(sha: str, *, root: Path, ocr_keys, baseline: str, helpers) -> tuple:
    """`(markdown, pages, stored_payload)` for one document, or `(None, ...)`.

    The partition chosen is the one whose analysis key resolves the payload the
    run of record stored — proof of which text the run analysed rather than an
    ordering over the partitions.
    """
    StatementMarkdown, cache_key, analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS = helpers
    candidates: list[tuple[str, list[str]]] = []
    for key in ocr_keys:
        composed = cache_key(STAGE_OCR, sha, key)
        path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            continue
        pages = [str(page) for page in (document.get("pages") or [])]
        candidates.append((StatementMarkdown(
            source_file="replay.pdf",
            model=str(document.get("model") or ""),
            pages=pages,
        ).to_markdown(), pages))
    if not candidates:
        return None, None, None

    markdown, pages = candidates[0]
    stored = None
    for candidate_markdown, candidate_pages in candidates:
        composed = cache_key(
            STAGE_ANALYSIS,
            analysis_input_sha(candidate_markdown, candidate_pages),
            baseline,
        )
        path = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))["artifact"]["analysis"]
        except (OSError, ValueError, KeyError):
            continue
        markdown, pages = candidate_markdown, candidate_pages
        break
    return markdown, pages, stored


# ---------------------------------------------------------------------------
# One arm
# ---------------------------------------------------------------------------

def outcome(markdown: str, pages: list[str]) -> dict:
    """One document at whichever tree is currently imported.

    The vocabulary is the run's own: `classify_outcome` over the analysis
    payload, and for the failures the rule `discovery/runner.py::_failure_reason`
    applies — an unclaimed document with a non-empty `attempted` is
    `parser_declined`, one with an empty `attempted` is `no_parser_matched`.
    """
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from telemetry.record import classify_outcome

    seen: dict[str, object] = {}
    try:
        report = analyze_markdown(
            markdown, parse_mode="deterministic", sheets=pages,
            on_dispatch=lambda dispatch: seen.setdefault("dispatch", dispatch),
        )
        payload = report_to_dict(report)
        outcome_class, reason = classify_outcome(payload)
        metrics = payload.get("metrics") or {}
        return {
            "class": outcome_class,
            "reason": reason,
            "payload_digest": digest(canonical(payload)),
            "deposits_source": metrics.get("deposits_source"),
            "withdrawals_source": metrics.get("withdrawals_source"),
        }
    except Exception as exc:
        dispatch = seen.get("dispatch")
        error_type = type(exc).__name__
        if error_type == "AmbiguousParserError":
            error_reason = "parser_ambiguous"
        elif dispatch is not None and getattr(dispatch, "outcome", None) == "parser_exception":
            error_reason = "parser_exception"
        elif dispatch is not None and getattr(dispatch, "outcome", None) == "unclaimed":
            error_reason = ("parser_declined" if getattr(dispatch, "attempted", None)
                            else "no_parser_matched")
        else:
            error_reason = "exception"
        outcome_class, reason = classify_outcome(
            None, error_type=error_type, error_reason=error_reason)
        return {
            "class": outcome_class,
            "reason": reason,
            "payload_digest": None,
            "deposits_source": None,
            "withdrawals_source": None,
        }


def dispatch_of(markdown: str, *, superseder: str, issuer: str) -> dict:
    """What the live registry does with this document, and what it would do
    with the `issuer → superseder` edge removed."""
    from analysis import parser_registry as pr
    from analysis import parser_registry_entries  # noqa: F401 — populates the registry

    registrations = pr.registrations()
    resolved = pr.resolve(markdown)
    claimants = [r for r in registrations if r.detect(markdown).claims]
    superseded = {
        identifier
        for claimant in claimants
        for identifier in getattr(claimant, "supersedes", frozenset())
        # the one edge under test, dropped
        if not (claimant.id == issuer and identifier == superseder)
    }
    survivors = [r.id for r in claimants if r.id not in superseded]
    return {
        "dispatch_outcome": resolved.outcome,
        "dispatch_parser_id": resolved.parser_id,
        "attempted": list(resolved.attempted or []),
        "candidates": [identifier for identifier, _score in resolved.candidates],
        "claimed_by_superseder": any(r.id == superseder for r in claimants),
        "claimants": sorted(r.id for r in claimants),
        "ambiguous_without_the_edge": len(survivors) > 1,
    }


def chain_evidence(texts: dict[str, str]) -> dict:
    """The account SLOTS the family prints, and the statement chains they form.

    §GL1 called the eight "two consecutive-month chains of two accounts" and
    review finding 7 measured otherwise. This re-derives the structure from the
    documents rather than from either account: each document's printed account
    slot is read with the reader's own `_summary`, hashed immediately (the slot
    itself never leaves this function), and two statements on one slot form a
    chain EDGE when the earlier one's `Ending Balance On <date>` is the later
    one's `Balance Forward From <date>` — the same date and the same figure.

    Nothing but counts is reported: no slot, no date, no balance.
    """
    from analysis import category_partition as cp

    read: dict[str, tuple[str, str, str, float, float]] = {}
    unreadable: list[str] = []
    for sha, markdown in texts.items():
        summary = cp._summary(markdown)
        if summary is None:
            unreadable.append(sha[:8])
            continue
        slot = hashlib.sha256(summary.account.encode("utf-8")).hexdigest()[:8].upper()
        read[sha] = (slot, summary.seed, summary.end, summary.beginning, summary.ending)

    slots: dict[str, list[tuple]] = {}
    for sha, entry in read.items():
        slots.setdefault(entry[0], []).append(entry)
    edges = date_edges = balance_edges = 0
    for statements in slots.values():
        by_end = {entry[2]: entry for entry in statements}
        for entry in statements:
            earlier = by_end.get(entry[1])
            if earlier is None:
                continue
            # The seed date of this statement IS the closing date of that one:
            # the edge exists. What it has to close on is the figure.
            edges += 1
            date_edges += 1
            if abs(earlier[4] - entry[3]) <= 0.005:
                balance_edges += 1
    return {
        "documents_read": len(read),
        "unreadable": unreadable,
        "distinct_account_slots": len(slots),
        "chain_sizes": sorted(len(v) for v in slots.values()),
        "chain_edges": edges,
        "chain_edges_closing_on_the_date": date_edges,
        "chain_edges_closing_on_the_balance": balance_edges,
    }


def printed_evidence(markdown: str) -> dict:
    """Two printings the record's own sentences rest on, read with the reader's
    own grammar rather than with a second one written here.

    * the bank's `Average Balance (<basis>)` partition entry, and whether the
      platform printed it MARKED with a trailing plus (review finding 4: a
      BALANCE this platform does mark, on the same line as two it does not);
    * every row the three named SECTIONED ledger sections print, and how many
      of them carry a mark of either sign (review finding 5's reachability).
    """
    from analysis import category_partition as cp
    from analysis.tables import dated_cells, section_runs

    evidence = {
        "prints_average_entry": False,
        "average_entry_marked_plus": False,
        "sectioned_issue": False,
        "sectioned_ledger_rows": 0,
        "sectioned_ledger_rows_marked": 0,
        "unreadable_sectioned_run": False,
    }
    line = cp._PARTITION_LINE_RE.search(markdown)
    if line is not None:
        entries = cp._entries(line.group(1))
        for label, match in entries or ():
            if cp._AVERAGE_ENTRY_RE.match(label) is None:
                continue
            evidence["prints_average_entry"] = True
            read = cp._signed(match)
            evidence["average_entry_marked_plus"] = bool(read and read[1] == "+")

    sections = section_runs(markdown, cp._SECTION_RE)
    evidence["sectioned_issue"] = not sections.get(cp._UNIFIED_HEADING, [])
    for heading in (cp._CREDIT_HEADING, *cp._DEBIT_HEADINGS):
        for run in sections.get(heading, []):
            cells = dated_cells(run, date_pattern=cp._DATE_RE, value_pattern=cp._AMOUNT_RE)
            if cells is None:
                evidence["unreadable_sectioned_run"] = True
                continue
            for cell in cells:
                evidence["sectioned_ledger_rows"] += 1
                marked = cp._AMOUNT_RE.search(
                    run, cell.start + len(cell.date), cell.end)
                read = cp._signed(marked) if marked is not None else None
                if read is not None and read[1]:
                    evidence["sectioned_ledger_rows_marked"] += 1
    return evidence


# ---------------------------------------------------------------------------
# The base tree, from git blobs
# ---------------------------------------------------------------------------

def materialise(base: str, into: Path) -> Path:
    """`<into>/analysis` as `base` recorded it. Nothing is checked out."""
    archive = subprocess.run(
        ["git", "archive", "--format=tar", base, "analysis"],
        check=True, stdout=subprocess.PIPE,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(into)
    root = into / "analysis"
    if not (root / "pipeline.py").exists():
        raise SystemExit(f"{base} holds no analysis/pipeline.py")
    return into


def switch_to(tree: Path) -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in PROJECT_PACKAGES:
            del sys.modules[name]
    sys.path.insert(0, str(tree))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()

    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )

    helpers = (StatementMarkdown, cache_key, analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS)
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]
    rows, family, cohort, pinned = population(args)
    order = family + [sha for sha in cohort if sha not in family]

    # Every text FIRST, at the branch tree, before any module is swapped.
    loaded: dict[str, tuple] = {}
    missing: list[str] = []
    for sha in order:
        markdown, pages, stored = texts_for(
            sha, root=args.data_dir / "artifacts", ocr_keys=ocr_keys,
            baseline=args.baseline_settings_key.strip().upper(), helpers=helpers)
        if markdown is None:
            missing.append(sha[:8])
            continue
        loaded[sha] = (markdown, pages, stored)

    chains = chain_evidence(
        {sha: loaded[sha][0] for sha in family if sha in loaded})

    branch: dict[str, dict] = {}
    for sha, (markdown, pages, stored) in loaded.items():
        branch[sha] = {
            "outcome": outcome(markdown, pages),
            "dispatch": dispatch_of(markdown, superseder=args.superseder, issuer=args.issuer),
            "evidence": printed_evidence(markdown),
            "stored_digest": digest(canonical(stored)) if stored is not None else None,
        }

    with tempfile.TemporaryDirectory(prefix="glance-base-") as tmp:
        switch_to(materialise(args.base, Path(tmp)))
        base: dict[str, dict] = {
            sha: outcome(markdown, pages)
            for sha, (markdown, pages, _stored) in loaded.items()
        }

    documents = []
    for sha in order:
        if sha not in loaded:
            continue
        after, before = branch[sha], base[sha]
        # "Identical" is claimed only where BOTH arms produced a payload. A
        # document that publishes at neither tree has nothing to compare, and
        # counting it as identical would inflate the very number the edge has
        # to earn.
        here, there = after["outcome"]["payload_digest"], before["payload_digest"]
        payload_state = (
            "none_in_either_arm" if here is None and there is None
            else "new_at_the_branch" if there is None
            else "lost_at_the_branch" if here is None
            else "identical" if here == there
            else "moved"
        )
        documents.append({
            "payload_state": payload_state,
            "sha8": sha[:8],
            "cohort": "family" if sha in family else "issuer",
            "pinned": sha in pinned,
            "run_outcome": f"{rows[sha].get('outcome_class')}/{rows[sha].get('outcome_reason')}",
            "base": f"{before['class']}/{before['reason']}",
            "branch": f"{after['outcome']['class']}/{after['outcome']['reason']}",
            "payload_identical_to_the_run":
                after["stored_digest"] is not None
                and after["stored_digest"] == after["outcome"]["payload_digest"],
            "has_stored_payload": after["stored_digest"] is not None,
            "deposits_source": after["outcome"]["deposits_source"],
            "withdrawals_source": after["outcome"]["withdrawals_source"],
            **after["dispatch"],
            **after["evidence"],
        })

    moved = [d for d in documents if d["base"] != d["branch"]]
    summary = {
        "base": args.base,
        "family_account_slots_and_chains": chains,
        "documents": len(documents),
        "family": len(family),
        "issuer_cohort": len(cohort),
        "pinned_in_cohort": sorted(sha[:8] for sha in pinned if sha in cohort),
        "no_ocr_artifact": missing,
        "seconds": round(time.perf_counter() - started, 1),
        "moved": len(moved),
        "movement": sorted({f"{d['base']} -> {d['branch']}" for d in moved}),
        "branch_outcomes": _tally(d["branch"] for d in documents),
        "payload_base_vs_branch": _tally(d["payload_state"] for d in documents),
        "payload_identical_to_the_run":
            sum(1 for d in documents if d["payload_identical_to_the_run"]),
        "documents_with_a_stored_payload":
            sum(1 for d in documents if d["has_stored_payload"]),
        "claimed_by_the_superseder":
            sum(1 for d in documents if d["claimed_by_superseder"]),
        "dispatch_at_head": _tally(
            f"{d['dispatch_outcome']}/{d['dispatch_parser_id']}" for d in documents),
        "ambiguous_at_head":
            sum(1 for d in documents if d["dispatch_outcome"] == "ambiguous"),
        "ambiguous_without_the_edge":
            sum(1 for d in documents if d["ambiguous_without_the_edge"]),
        "prints_average_entry": sum(1 for d in documents if d["prints_average_entry"]),
        "average_entry_marked_plus":
            sum(1 for d in documents if d["average_entry_marked_plus"]),
        "sectioned_issue_documents": sum(1 for d in documents if d["sectioned_issue"]),
        "sectioned_ledger_rows":
            sum(d["sectioned_ledger_rows"] for d in documents if d["sectioned_issue"]),
        "sectioned_ledger_rows_marked":
            sum(d["sectioned_ledger_rows_marked"] for d in documents if d["sectioned_issue"]),
        "sectioned_ledger_rows_all_documents":
            sum(d["sectioned_ledger_rows"] for d in documents),
        "sectioned_ledger_rows_marked_all_documents":
            sum(d["sectioned_ledger_rows_marked"] for d in documents),
        "provenance_of_the_direction_totals": _tally(
            f"{d['deposits_source']}/{d['withdrawals_source']}"
            for d in documents if d["deposits_source"] is not None
        ),
    }

    report = {"summary": summary, "documents": documents}
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=1, sort_keys=True))
    print()
    print(f"{'sha':9}{'cohort':8}{'base':26}{'branch':26}"
          f"{'payload vs base':20}{'payload=run':13}pinned")
    for document in documents:
        print(f"{document['sha8']:9}{document['cohort']:8}{document['base']:26}"
              f"{document['branch']:26}{document['payload_state']:20}"
              f"{str(document['payload_identical_to_the_run']):13}"
              f"{'yes' if document['pinned'] else ''}")
    return 0


def _tally(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
