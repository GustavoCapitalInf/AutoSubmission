"""cohort_replay.py — the batch-9 targeted-cohort proof, one instrument for every cell.

    python -m tools.cohort_replay --group DECL:huntington --out <private>/huntington.md
    python -m tools.cohort_replay --parser huntington            # every sha the baseline run CLAIMED with this reader
    python -m tools.cohort_replay --family wpcu_summary_of_account_by_transaction
    python -m tools.cohort_replay --folder "Huntington Bank"
    python -m tools.cohort_replay --shas population.txt [--start A --end B]
    (selectors combine as a UNION; --json <path> writes the per-sha table)

Replays each sha of the cohort from the RUN OF RECORD's own cached OCR/native
text (batch 8: `TRAIN8-7185633 / cda8882d`, cold cache
`.claude/recovery/webapp_data_train8_cold`) through THIS tree's
`analysis.pipeline.analyze_markdown(parse_mode="deterministic")` — exactly the
call `discovery.runner._analyse` makes, same page partition — classifies the
result with `telemetry.record.classify_outcome` and the runner's own
`_failure_reason`, and compares against the baseline outcome in `rows.csv` and
the baseline payload stored under the run's own analysis key.

It reports movement in the proof shape batch 9 requires:

    population | newly validated | other ladder movement | previously validated
    preserved (payload identical / payload changed, with the changed leaf PATHS)
    | validated regressions (BLOCKING, exit 2) | other ladder regressions

Doctrine it enforces by construction: a gain never cancels a regression — the
exit code is 2 whenever ANY previously validated sha moves down the ladder,
whatever the newly validated count; a validated -> validated sha whose payload
changed is listed with its changed paths so the cell proves the change is
semantically correct (the ladder outcome alone is not the standard).

Read-only over the archive and the cache (artifacts by direct path through the
sqlite index of the COLD cache, which nothing writes to); no OCR; no model; $0.
Never prints a document value: the report carries shas, outcomes, reasons,
reader ids, counts and leaf PATHS. `deferred` baseline shas have no cached
text and are reported as `no_text`, never replayed.

Baseline fidelity: at an unchanged tree every sha must reproduce its baseline
outcome and an identical payload; run it once at the base commit before any
change (`--expect-identical` exits 3 otherwise) so a proof is measured against
an instrument that is known to reproduce the run.

Artifact selection (P20-ARTIFACTS, Phase 2.0; OQ8/OQ10; F-9)
--------------------------------------------------------------
`ColdCache` used to take `rows[0]` of whatever the cache held for a stage and
an input hash, with no `ORDER BY` and no settings-key filter on EITHER stage
(SQLite's row order without `ORDER BY` is unspecified). That was correct only
because every input in the batch-8/9 archive has ever held exactly one
artifact per stage. It now resolves through `telemetry/run_of_record.py`'s ONE
selection policy, shared with `telemetry/stated_counts.py::_ArtifactJoin`: the
`--run` directory's partitions (recorded, or deterministically reconstructed
and verified against `--data-dir`'s own cache index — a mismatch is exit 5,
never a guess), and each row's OWN partition on both stages
(`ocr_partition_for_row`, `analysis_partition`) rather than a preference order
or an incidental one.

`--run` is REQUIRED and has no pointer-file default: a hidden default is
exactly the class of staleness this fix exists to close (the tool's OLD
default silently pointed at the train-8 pointer file long after the batch-9
run of record became current — every other Phase-2.0 cell had to remember to
override it by hand). The batch-9 run of record is recorded, for convenience,
at `discovery_reports/train9-logs/train9_run_dir.txt` (gitignored, like the
train-8 pointer it succeeds) — read that file's content and pass it to
`--run` explicitly; this tool does not read it for you.

Exit codes: 0 clean, 2 a validated regression, 3 `--expect-identical` drift,
4 an empty cohort, 5 the artifact-selection policy could not resolve a run's
partitions or found a corrupt cache index (`telemetry.run_of_record.RunOfRecordError`).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path

#: No longer read automatically (`--run` is REQUIRED — see the module
#: docstring's "Artifact selection" note): this is the batch-9 run-of-record
#: pointer file this cell writes, for a caller to `cat` and pass explicitly.
BATCH9_RUN_POINTER = Path("discovery_reports/train9-logs/train9_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_CENSUS = Path("docs/moneythumb-replacement/census_batch9/per_sha.csv")
LADDER = ("failed", "withheld", "review", "validated")


# ----------------------------------------------------------------------------
# baseline
# ----------------------------------------------------------------------------

def load_baseline_rows(run: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with (run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if sha and sha not in rows:
                rows[sha] = row
    return rows


def load_census(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["sha"]: row for row in csv.DictReader(handle)}


def select_cohort(args, rows: dict[str, dict], census: dict[str, dict]) -> list[str]:
    chosen: set[str] = set()
    if args.shas:
        for line in Path(args.shas).read_text(encoding="utf-8").splitlines():
            token = line.strip().upper()
            if token and not token.startswith("#"):
                chosen.add(token)
    if args.group:
        for sha, rec in census.items():
            if rec.get("cluster_group") in args.group or rec.get("cluster") in args.group:
                chosen.add(sha)
    if args.family:
        for sha, rec in census.items():
            if rec.get("b8_family") in args.family:
                chosen.add(sha)
    if args.parser:
        for sha, row in rows.items():
            if (row.get("parser_id") or "") in args.parser:
                chosen.add(sha)
    if args.folder:
        for sha, row in rows.items():
            if (row.get("folder_label") or "") in args.folder:
                chosen.add(sha)
    cohort = sorted(chosen)
    return cohort[args.start: args.end]


# ----------------------------------------------------------------------------
# cache
# ----------------------------------------------------------------------------

class ColdCache:
    """A read-only view of one data directory's D-3 artifact cache, resolving
    strictly through `telemetry/run_of_record.py`'s ONE selection policy — no
    `rows[0]`, no preference order, no incidental DB order. `run_dir` is the
    discovery run whose partitions govern every lookup this instance makes."""

    def __init__(self, data_dir: Path, run_dir: Path):
        from telemetry.run_of_record import partitions_for_run

        self.root = data_dir / "artifacts"
        self.conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
        from ocr.document import StatementMarkdown
        from webapp.artifact_cache import analysis_input_sha
        self._markdown = StatementMarkdown
        self._input_sha = analysis_input_sha
        # Raises `telemetry.run_of_record.RunOfRecordError` on a malformed
        # record or a reconstruction the cache does not corroborate — caught
        # at `main()` and reported as exit 5, never silently guessed past.
        self.partitions = partitions_for_run(run_dir, conn=self.conn)

    def _payload(self, stage: str, input_sha: str, settings_key: str | None):
        from telemetry.run_of_record import select_artifact

        path = select_artifact(self.conn, stage, input_sha, settings_key)
        if path is None:
            return None
        try:
            return json.loads((self.root / path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def text(self, sha: str, row: dict) -> tuple[str | None, list[str]]:
        from telemetry.run_of_record import ocr_partition_for_row

        settings_key = ocr_partition_for_row(row, self.partitions)
        payload = self._payload("ocr", sha, settings_key)
        if payload is None:
            return None, []
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            return None, []
        pages = [str(p) for p in (document.get("pages") or [])]
        markdown = self._markdown(source_file="replay.pdf", model=str(document.get("model") or ""),
                                  pages=pages).to_markdown()
        return markdown, pages

    def baseline_payload(self, markdown: str, pages: list[str]) -> dict | None:
        from telemetry.run_of_record import analysis_partition

        settings_key = analysis_partition(self.partitions)
        payload = self._payload("analysis", self._input_sha(markdown, pages), settings_key)
        if payload is None:
            return None
        try:
            return payload["artifact"]["analysis"]
        except (KeyError, TypeError):
            return None


# ----------------------------------------------------------------------------
# replay
# ----------------------------------------------------------------------------

def replay_one(markdown: str, pages: list[str]) -> tuple[dict | None, str, str, str | None]:
    """(payload, outcome_class, outcome_reason, claimed_parser)."""
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from discovery.runner import DispatchCollector, _failure_reason
    from telemetry.record import classify_outcome

    collector = DispatchCollector()
    try:
        payload = report_to_dict(analyze_markdown(
            markdown, parse_mode="deterministic", on_dispatch=collector, sheets=pages))
    except Exception as exc:  # the runner's own boundary: never raises
        error_type = type(exc).__name__
        dispatch = collector.dispatch if collector.seen else None
        reason = _failure_reason(error_type, dispatch) or "exception"
        return None, "failed", reason, _claimed(collector)
    klass, reason = classify_outcome(payload)
    # The cache stores canonical JSON; `report_to_dict` returns tuples where the
    # stored payload holds lists (measured: every huntington document differed
    # ONLY by that type at an unchanged tree). Compare like with like.
    payload = json.loads(json.dumps(payload, sort_keys=True))
    return payload, klass, reason, _claimed(collector)


def _claimed(collector) -> str | None:
    if not collector.seen:
        return None
    dispatch = collector.dispatch
    return getattr(dispatch, "parser_id", None) or (dispatch.attempted[0] if getattr(dispatch, "attempted", None) else None)


def flatten(value, prefix: str = "") -> dict[str, object]:
    """Leaf paths -> values. A list whose members are ALL scalars is compared as
    a multiset (sorted): those lists are serialised sets (`revenue_context_signals`,
    `withholding_denominator_options`) whose order follows the process hash seed
    — at an unchanged tree the run of record and a replay differ ONLY there
    (measured on the huntington cohort, 38/38). Lists of dicts keep their order:
    transaction order is semantic."""
    out: dict[str, object] = {}
    # An EMPTY container is a leaf too. Without this an added key whose value
    # is `[]` or `{}` projected to nothing and two payloads that differed by
    # that key compared as identical (found by the L1-ARCH-DESIGN cell: 0
    # byte-identical vs 208 "leaf-identical" on an omission-field variant).
    if isinstance(value, (dict, list)) and not value:
        out[prefix] = "<empty-dict>" if isinstance(value, dict) else "<empty-list>"
        return out
    if isinstance(value, dict):
        for key, item in value.items():
            out.update(flatten(item, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        if value and all(not isinstance(item, (dict, list)) for item in value):
            ordered = sorted(value, key=lambda item: (type(item).__name__, str(item)))
            for index, item in enumerate(ordered):
                out[f"{prefix}[{index}]"] = item
        else:
            for index, item in enumerate(value):
                out.update(flatten(item, f"{prefix}[{index}]"))
    else:
        out[prefix] = value
    return out


def leaf_diff(before: dict | None, after: dict | None) -> dict[str, int]:
    """Changed leaf paths, indices collapsed to [*], as path -> count. Values never leave."""
    if before is None or after is None:
        return {"<payload presence>": 1}
    left, right = flatten(before), flatten(after)
    changed = collections.Counter()
    import re
    for path in set(left) | set(right):
        if left.get(path, "<absent>") != right.get(path, "<absent>"):
            changed[re.sub(r"\[\d+\]", "[*]", path)] += 1
    return dict(sorted(changed.items()))


def rank(klass: str):
    return LADDER.index(klass) if klass in LADDER else None


def direction(before: str, after: str) -> str:
    b, a = rank(before), rank(after)
    if b is None or a is None:
        return "unranked"
    return "improved" if a > b else "regressed" if a < b else "unchanged"


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, required=True,
                        help="the discovery run of record (REQUIRED — no pointer-file default; "
                             "see the module docstring's 'Artifact selection' note). The batch-9 "
                             "run is recorded at discovery_reports/train9-logs/train9_run_dir.txt")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    parser.add_argument("--shas", type=Path, default=None)
    parser.add_argument("--group", action="append", default=[], help="census cluster_group or cluster (repeatable)")
    parser.add_argument("--family", action="append", default=[], help="batch-8 census family key (repeatable)")
    parser.add_argument("--parser", action="append", default=[], help="baseline parser_id (repeatable)")
    parser.add_argument("--folder", action="append", default=[], help="folder label (repeatable)")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None, help="markdown report (private; never commit values)")
    parser.add_argument("--json", type=Path, default=None, help="per-sha table")
    parser.add_argument("--expect-identical", action="store_true",
                        help="baseline-fidelity mode: exit 3 unless every sha reproduces its outcome and payload")
    parser.add_argument("--label", default="", help="free text for the report header (tree, card)")
    args = parser.parse_args(argv)

    rows = load_baseline_rows(args.run)
    census = load_census(args.census)
    cohort = select_cohort(args, rows, census)
    if not cohort:
        print("empty cohort")
        return 4
    from telemetry.run_of_record import RunOfRecordError

    try:
        cache = ColdCache(args.data_dir, args.run)
    except RunOfRecordError as exc:
        print(f"artifact-selection policy failed: {exc}")
        return 5

    import subprocess
    tree = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()

    table: list[dict] = []
    started = time.perf_counter()
    for index, sha in enumerate(cohort, 1):
        base = rows.get(sha)
        entry = {"sha": sha, "sha16": sha[:16], "folder": (base or {}).get("folder_label", ""),
                 "before": (base or {}).get("outcome_class", "absent"), "before_reason": (base or {}).get("outcome_reason", ""),
                 "before_parser": (base or {}).get("parser_id", ""), "after": None, "after_reason": None,
                 "after_parser": None, "direction": None, "payload": None, "changed_paths": {}, "ms": None}
        if base is None:
            entry.update(after="absent", direction="unranked", payload="absent")
            table.append(entry)
            continue
        try:
            markdown, pages = cache.text(sha, base)
        except RunOfRecordError as exc:
            print(f"artifact-selection policy failed on {sha[:16]}: {exc}")
            return 5
        if markdown is None:
            entry.update(after="no_text", direction="unranked", payload="no_text")
            table.append(entry)
            continue
        try:
            baseline_payload = cache.baseline_payload(markdown, pages)
        except RunOfRecordError as exc:
            print(f"artifact-selection policy failed on {sha[:16]}: {exc}")
            return 5
        t0 = time.perf_counter()
        payload, klass, reason, claimed = replay_one(markdown, pages)
        entry["ms"] = round((time.perf_counter() - t0) * 1000)
        entry.update(after=klass, after_reason=reason, after_parser=claimed or "", direction=direction(entry["before"], klass))
        if payload is None and baseline_payload is None:
            entry["payload"] = "none-both"
        elif payload is None or baseline_payload is None:
            entry["payload"] = "presence-changed"
            entry["changed_paths"] = leaf_diff(baseline_payload, payload)
        else:
            diff = leaf_diff(baseline_payload, payload)
            entry["payload"] = "identical" if not diff else "changed"
            entry["changed_paths"] = diff
        table.append(entry)
        if index % 25 == 0 or index == len(cohort):
            print(f"  {index}/{len(cohort)} replayed ({time.perf_counter() - started:.0f}s)", flush=True)

    # --- accounting
    newly = [e for e in table if e["before"] != "validated" and e["after"] == "validated"]
    up_other = [e for e in table if e["direction"] == "improved" and e["after"] != "validated"]
    preserved = [e for e in table if e["before"] == "validated" and e["after"] == "validated"]
    preserved_identical = [e for e in preserved if e["payload"] == "identical"]
    preserved_changed = [e for e in preserved if e["payload"] != "identical"]
    val_regressions = [e for e in table if e["before"] == "validated" and e["after"] in LADDER and e["after"] != "validated"]
    other_regressions = [e for e in table if e["direction"] == "regressed" and e["before"] != "validated"]
    unchanged_nonval = [e for e in table if e["direction"] == "unchanged" and e["before"] != "validated"]
    nonval_payload_changed = [e for e in unchanged_nonval if e["payload"] in ("changed", "presence-changed")]
    no_text = [e for e in table if e["after"] in ("no_text", "absent")]

    lines = [
        f"# cohort replay — {args.label or 'unlabelled'} — tree `{tree}` — run `{args.run.name}`", "",
        f"selectors: shas={args.shas} group={args.group} family={args.family} parser={args.parser} folder={args.folder} "
        f"slice=[{args.start}:{args.end}]", "",
        "| measure | count |", "|---|---:|",
        f"| population | {len(table)} |",
        f"| replayed (text available) | {len(table) - len(no_text)} |",
        f"| newly validated | **{len(newly)}** |",
        f"| other ladder movement (up, not validated) | {len(up_other)} |",
        f"| previously validated preserved | **{len(preserved)}** of {sum(1 for e in table if e['before'] == 'validated')} |",
        f"| … payload identical | {len(preserved_identical)} |",
        f"| … payload changed (prove semantics) | {len(preserved_changed)} |",
        f"| validated regressions (BLOCKING) | **{len(val_regressions)}** |",
        f"| other ladder regressions | {len(other_regressions)} |",
        f"| unchanged non-validated | {len(unchanged_nonval)} (payload changed on {len(nonval_payload_changed)}) |",
        f"| no text / absent | {len(no_text)} |", "",
    ]

    def block(title: str, items: list[dict], with_paths: bool = False) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("none")
        else:
            lines.append("| sha16 | folder | before | after | reader before → after | payload |")
            lines.append("|---|---|---|---|---|---|")
            for e in items:
                lines.append(f"| {e['sha16']} | {e['folder']} | {e['before']}/{e['before_reason']} | "
                             f"{e['after']}/{e['after_reason']} | {e['before_parser'] or '-'} → {e['after_parser'] or '-'} | {e['payload']} |")
            if with_paths:
                for e in items:
                    if e["changed_paths"]:
                        lines.append(f"- {e['sha16']}: " + ", ".join(f"`{p}`×{n}" for p, n in e["changed_paths"].items()))
        lines.append("")

    block("validated regressions — BLOCKING", val_regressions, with_paths=True)
    block("newly validated", newly)
    block("other ladder movement (up)", up_other)
    block("other ladder regressions (down, from a non-validated class)", other_regressions)
    block("previously validated, payload changed — prove each change is correct", preserved_changed, with_paths=True)
    block("unchanged non-validated with a changed payload", nonval_payload_changed, with_paths=True)
    lines.append(f"## previously validated, payload identical ({len(preserved_identical)})")
    lines.append("")
    lines.append(", ".join(e["sha16"] for e in preserved_identical) or "none")
    lines.append("")
    lines.append(f"## unchanged non-validated ({len(unchanged_nonval)})")
    lines.append("")
    lines.append(", ".join(f"{e['sha16']}({e['after']}/{e['after_reason']})" for e in unchanged_nonval) or "none")
    lines.append("")
    lines.append(f"runtime {time.perf_counter() - started:.0f}s; per-doc ms median "
                 f"{sorted(e['ms'] for e in table if e['ms'] is not None)[max(0, (len(table) - len(no_text)) // 2 - 1)] if len(table) > len(no_text) else '-'}")
    report = "\n".join(lines) + "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"tree": tree, "run": args.run.name, "rows": table}, indent=1), encoding="utf-8")
    print(report if not args.out else "\n".join(lines[:16]))

    if val_regressions:
        return 2
    if args.expect_identical:
        drift = [e for e in table if e["after"] not in ("no_text", "absent")
                 and (e["direction"] != "unchanged" or e["payload"] not in ("identical", "none-both")
                      or e["after_reason"] != e["before_reason"])]
        if drift:
            print(f"BASELINE FIDELITY FAILED on {len(drift)} shas: " + ", ".join(e["sha16"] for e in drift[:20]))
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
