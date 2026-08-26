"""Did the source posting-date scan remove a REAL posting day anywhere?

W3 §WITHHELDGRIDS's second committed instrument, and the one the review's
MAJOR-1 is about. `source_posting_dates` is removal-only by construction, so
every rule this card added can only make `posting_dates_cover_source` quieter.
"Quieter" is three different things and the record reported them as one count:

* removing a FALSE day — a printed date the ledger does not post and that is
  not the printed period boundary (a masthead, an interest-rate line, a
  marketing sentence) — is the rule working;
* removing the printed period BOUNDARY where the ledger posts nothing on it —
  the statement date, the `Beginning Balance` day — is the rule working too,
  and it is the single largest class the card's lifts depend on, so it is
  counted separately rather than folded into either side;
* removing a REAL day — a date the LEDGER ITSELF POSTS — is evidence loss.
  The check cannot fail on a day it can no longer see, and
  `posting_dates_cover_source` is the only required check that exists to catch
  a parser folding several printed posting days into one.

This instrument measures all three archive-wide, attributes every removal to a
RULE by ablation, and names every residual. It also counts the documents whose
source set is EMPTY while their ledger posts something, because an empty
source set is a required check that cannot fail at all.

    python -m tools.withheldgrids_srcdates_audit \
        --rows discovery_reports/<run>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> [--base-rev 10cc722]

READ-ONLY, by the same rules as `tools/withheldgrids_leaf_diff.py`: the
`webapp_data` sqlite index is never opened, OCR and analysis payloads are
reached by DIRECT file path, every capability partition of `ocr_settings_key`
is enumerated and the artifact chosen is the one whose reconstruction resolves
the run's own stored analysis payload. No hosted model is called ($0.00).

WHERE THE NUMBERS COME FROM, and why none of them costs a re-parse:

* the statement period is `metrics.adb.period_start` / `period_end` of the
  run's own stored payload — literally the `start` / `end` that
  `analysis/adb.py` passed to `source_posting_dates`;
* the LEDGER's posting days are the stored payload's transaction dates,
  clipped to the period exactly as `analysis/adb.py` clips them;
* both are self-checked against the stored `parsed_posting_days` and
  `source_posting_days`, so a resolution that picked the wrong artifact
  partition is reported (`stored_mismatch`) rather than averaged in.

Only documents whose two source sets DIFFER are re-parsed on the branch tree,
to pick up the ledger days the branch's reader hunks add; that is a few dozen
documents, not the archive.

HOW A REMOVAL IS ATTRIBUTED TO A RULE. Not by a second copy of the cascade —
a duplicate walk drifts out of date silently. Each rule is ABLATED by a
literal substitution in the module's own source text, the ablated text is
exec'd as its own module inside the package, and a day that comes back when
rule R is ablated is a day rule R removed. A substitution that does not appear
exactly once is a hard failure of the run, so an ablation cannot silently do
nothing (the batch-7 trap).

PRIVACY (batch-7 standing rule): this tool prints counts, `content_sha256`
prefixes and RULE NAMES. It never prints a date, an amount, a description or
any other literal read out of a document.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import subprocess
import sys
import types
from collections import Counter
from datetime import date
from pathlib import Path

#: The rules this card added to `source_posting_dates`, each as the literal
#: substitution that puts `analysis/dates.py` back the way `10cc722` had it for
#: that rule and no other. The names are this tool's vocabulary for them.
ABLATIONS: dict[str, tuple[str, str]] = {
    "forward_label": (
        "                following = next(\n"
        "                    (l.strip() for l in lines[index + 1:] if l.strip()), \"\"\n"
        "                )",
        '                following = ""',
    ),
    "money_proximity": (
        "            lookahead = [l for l in lines[index + 1: index + 5] if l.strip()][:3]",
        "            if len(remainder) >= 3:\n"
        "                found.add(parsed)\n"
        "                continue\n"
        "            lookahead = [l for l in lines[index + 1: index + 5] if l.strip()][:3]",
    ),
    "grid_caption_dot_leaders": (
        "    stripped = _without_leaders(line)\n"
        "    return stripped is not line and bool(_DAILY_BALANCE_GRID_CAPTION.match(stripped))",
        "    return False",
    ),
    "comma_decimal": (
        '_MONEY_RE = re.compile(r"\\d[\\d, ]*[.,]\\d{2}(?!\\d)")',
        '_MONEY_RE = re.compile(r"\\d[\\d,]*\\.\\d{2}(?!\\d)")',
    ),
}


def _load_module(name: str, source: str) -> types.ModuleType:
    """Exec a `analysis/dates.py` text as its own module inside the package.

    `__package__` is what makes `from .schema import Statement` resolve, so the
    base blob, the branch's working copy and every ablation of it can be live
    in ONE process and be compared without a second interpreter or a second
    checkout.
    """
    module = types.ModuleType(name)
    module.__package__ = "analysis"
    module.__file__ = f"<{name}>"
    sys.modules[name] = module
    exec(compile(source, f"<{name}>", "exec"), module.__dict__)  # noqa: S102
    return module


def _base_source(base_rev: str, repo: Path) -> str:
    return subprocess.run(
        ["git", "show", f"{base_rev}:analysis/dates.py"],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout


def _ablate(branch_source: str, name: str) -> str:
    old, new = ABLATIONS[name]
    count = branch_source.count(old)
    if count != 1:
        raise SystemExit(
            f"ABLATION {name} matched {count} times in analysis/dates.py; "
            "it must match exactly once or it silently measures nothing"
        )
    return branch_source.replace(old, new)


def _iso(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _resolve(root: Path, sha: str, ocr_keys, baseline, cache_key,
             analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown):
    """The leaf-diff's resolution, unchanged: partition that rebuilds the run."""
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
        candidates.append((
            StatementMarkdown(
                source_file="srcdates.pdf",
                model=str(document.get("model") or ""),
                pages=pages,
            ).to_markdown(),
            pages,
        ))
    if not candidates:
        return None, None, None
    for markdown, pages in candidates:
        composed = cache_key(STAGE_ANALYSIS, analysis_input_sha(markdown, pages), baseline)
        stored = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
        if not stored.exists():
            continue
        try:
            payload = json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
        except (OSError, ValueError, KeyError):
            continue
        return markdown, pages, payload
    return candidates[0][0], candidates[0][1], None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--baseline-settings-key", required=True)
    ap.add_argument("--base-rev", default="10cc722")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json-out", default="")
    ap.add_argument("--no-reparse", action="store_true")
    ap.add_argument("--quiet-rows", action="store_true")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()

    from analysis import dates as branch_dates
    from analysis.dates import parse_date
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )

    branch_source = (repo / "analysis" / "dates.py").read_text(encoding="utf-8")
    base_dates = _load_module("analysis._srcdates_base", _base_source(args.base_rev, repo))
    ablated = {
        name: _load_module(f"analysis._srcdates_ablate_{name}", _ablate(branch_source, name))
        for name in ABLATIONS
    }

    root = Path(args.data_dir) / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
        for f, l, v in itertools.product((False, True), repeat=3)
    ]

    seen: set[str] = set()
    shas: list[str] = []
    with open(args.rows, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if sha and sha not in seen:
                seen.add(sha)
                shas.append(sha)
    if args.limit:
        shas = shas[: args.limit]

    resolved = no_artifact = no_payload = no_period = stored_mismatch = 0
    real_total = boundary_total = false_total = 0
    empty_base = empty_branch = 0
    empty_base_ledger = empty_branch_ledger = 0
    newly_empty_with_ledger: list[str] = []
    rule_real, rule_boundary, rule_false = Counter(), Counter(), Counter()
    residuals: list[dict] = []
    boundary_rows: list[dict] = []
    movers: list[str] = []
    records: list[dict] = []

    for sha in shas:
        markdown, pages, stored = _resolve(
            root, sha, ocr_keys, args.baseline_settings_key, cache_key,
            analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown,
        )
        if markdown is None:
            no_artifact += 1
            continue
        if stored is None:
            no_payload += 1
            continue
        adb = ((stored.get("metrics") or {}).get("adb") or {})
        start, end = _iso(adb.get("period_start")), _iso(adb.get("period_end"))
        if start is None or end is None:
            no_period += 1
            continue
        resolved += 1

        ledger = {
            day for day in (
                parse_date(txn.get("date"))
                for txn in ((stored.get("statement") or {}).get("transactions") or [])
            ) if day is not None and start <= day <= end
        }
        base_set = set(base_dates.source_posting_dates(markdown, start, end))
        branch_set = set(branch_dates.source_posting_dates(markdown, start, end))

        if (adb.get("source_posting_days") is not None
                and adb["source_posting_days"] != len(base_set)) or (
                adb.get("parsed_posting_days") is not None
                and adb["parsed_posting_days"] != len(ledger)):
            stored_mismatch += 1

        lost = base_set - branch_set
        real_lost = sorted(lost & ledger)
        boundary_lost = sorted((lost & {start, end}) - ledger)
        false_removed = sorted(lost - ledger - {start, end})
        real_total += len(real_lost)
        boundary_total += len(boundary_lost)
        false_total += len(false_removed)

        if lost:
            movers.append(sha)
            attribution: dict[date, list[str]] = {}
            for name, module in ablated.items():
                back = set(module.source_posting_dates(markdown, start, end)) & lost
                for day in back:
                    attribution.setdefault(day, []).append(name)
            for day in real_lost:
                for rule in attribution.get(day, ["unattributed"]):
                    rule_real[rule] += 1
            for day in boundary_lost:
                for rule in attribution.get(day, ["unattributed"]):
                    rule_boundary[rule] += 1
            for day in false_removed:
                for rule in attribution.get(day, ["unattributed"]):
                    rule_false[rule] += 1
            if real_lost:
                residuals.append({
                    "sha8": sha[:8], "days": len(real_lost),
                    "rules": sorted({r for d in real_lost
                                     for r in attribution.get(d, ["unattributed"])}),
                })
            if boundary_lost:
                boundary_rows.append({
                    "sha8": sha[:8], "days": len(boundary_lost),
                    "rules": sorted({r for d in boundary_lost
                                     for r in attribution.get(d, ["unattributed"])}),
                })
            if not args.quiet_rows:
                print(f"{sha[:8]} base={len(base_set):3d} branch={len(branch_set):3d} "
                      f"ledger={len(ledger):3d} real={len(real_lost)} "
                      f"boundary={len(boundary_lost)} false={len(false_removed)}")

        if not base_set:
            empty_base += 1
            if ledger:
                empty_base_ledger += 1
        if not branch_set:
            empty_branch += 1
            if ledger:
                empty_branch_ledger += 1
                if base_set:
                    newly_empty_with_ledger.append(sha)
        records.append({
            "sha8": sha[:8], "base": len(base_set), "branch": len(branch_set),
            "ledger": len(ledger), "real": len(real_lost),
            "boundary": len(boundary_lost), "false": len(false_removed),
        })

    # The branch's own reader hunks add ledger days on a handful of documents.
    # Re-parse only those whose source sets moved, so a day the BRANCH ledger
    # posts is not scored as removed-and-not-real because the RUN's ledger
    # (built by the base tree) did not carry it.
    reparsed = reclassified = 0
    reclassified_shas: list[str] = []
    if movers and not args.no_reparse:
        from analysis.pipeline import analyze_markdown
        for sha in movers:
            markdown, pages, stored = _resolve(
                root, sha, ocr_keys, args.baseline_settings_key, cache_key,
                analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown,
            )
            adb = ((stored.get("metrics") or {}).get("adb") or {})
            start, end = _iso(adb.get("period_start")), _iso(adb.get("period_end"))
            try:
                report = analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
            except Exception:  # noqa: BLE001 - a refusal is an answer
                continue
            reparsed += 1
            branch_ledger = {
                day for day in (parse_date(t.date) for t in report.statement.transactions)
                if day is not None and start <= day <= end
            }
            stored_ledger = {
                day for day in (
                    parse_date(txn.get("date"))
                    for txn in ((stored.get("statement") or {}).get("transactions") or [])
                ) if day is not None and start <= day <= end
            }
            lost = (set(base_dates.source_posting_dates(markdown, start, end))
                    - set(branch_dates.source_posting_dates(markdown, start, end)))
            gained = lost & (branch_ledger - stored_ledger)
            if gained:
                reclassified += len(gained)
                reclassified_shas.append(sha[:8])

    print()
    print(f"POPULATION rows={len(shas)} resolved={resolved} "
          f"no_ocr_artifact={no_artifact} no_baseline_payload={no_payload} "
          f"no_period={no_period} stored_mismatch={stored_mismatch}")
    print(f"REAL_DAY_LOSS={real_total} (documents={len(residuals)})   "
          f"[a day the run's own ledger posts]")
    print(f"PERIOD_BOUNDARY_ONLY_LOSS={boundary_total} (documents={len(boundary_rows)})   "
          f"[the printed period boundary, no ledger posting on it]")
    print(f"FALSE_DAYS_REMOVED={false_total}")
    print(f"EMPTY_SOURCE_SET base={empty_base} branch={empty_branch}")
    print(f"EMPTY_WITH_LEDGER_POSTINGS base={empty_base_ledger} branch={empty_branch_ledger}")
    print(f"NEWLY_EMPTY_WITH_LEDGER_POSTINGS={len(newly_empty_with_ledger)} "
          + " ".join(s[:8] for s in sorted(newly_empty_with_ledger)))
    print(f"REPARSED_MOVERS={reparsed} branch_ledger_reclassified_days={reclassified} "
          + " ".join(sorted(reclassified_shas)))
    print("removals by rule (real / boundary / false):")
    for rule in list(ABLATIONS) + ["unattributed"]:
        if rule_real[rule] or rule_boundary[rule] or rule_false[rule]:
            print(f"  {rule:22s} real={rule_real[rule]:4d}  "
                  f"boundary={rule_boundary[rule]:4d}  false={rule_false[rule]:4d}")
    if residuals:
        print("RESIDUAL real-day losses, named:")
        for entry in sorted(residuals, key=lambda e: e["sha8"]):
            print(f"  {entry['sha8']}  days={entry['days']}  rules={','.join(entry['rules'])}")
    if boundary_rows:
        print(f"PERIOD-BOUNDARY-only removals, {len(boundary_rows)} documents "
              f"(rules: {','.join(sorted({r for e in boundary_rows for r in e['rules']}))})")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "resolved": resolved,
            "real_day_loss": real_total,
            "period_boundary_only_loss": boundary_total,
            "false_days_removed": false_total,
            "empty_base": empty_base, "empty_branch": empty_branch,
            "empty_base_with_ledger": empty_base_ledger,
            "empty_branch_with_ledger": empty_branch_ledger,
            "newly_empty_with_ledger": sorted(newly_empty_with_ledger),
            "rule_real": dict(rule_real), "rule_boundary": dict(rule_boundary),
            "rule_false": dict(rule_false),
            "residuals": residuals, "boundary_rows": boundary_rows,
            "records": records,
        }, indent=1), encoding="utf-8")
    return 0 if real_total == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
