"""Per document, which printed check disagrees — and therefore what the ceiling is.

W3 §CPSCAN's diagnosis instrument. The census (`tools.cpscan_census`) names
the gate that refuses; this says WHAT the gate saw, for the two templates this
card owns, so that "the scan lost rows" and "the reader lost rows" are
separated by measurement rather than by assertion.

    python -m tools.cpscan_ceiling \
        --rows <reports>/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> \
        --sha-file <private>/population.txt [--out ceiling.json]

Per document it reports, for whichever of the two templates claims it:

* `rows_short_credit` / `rows_short_debit` — the ledger's row count minus the
  count the summary printed, per direction. Negative is a lost row; positive
  is an invented one, which is the direction that would be a defect of ours;
* `credits_agree` / `debits_agree` / `identity_closes` — whether each printed
  total reconciles to the cent;
* `grid_days_printed`, `grid_days_disagreeing`, `grid_days_missing`,
  `grid_days_invented` — the daily-balance grid walked against the ledger;
* `unreadable_sections` — sections where a row's date or amount could not be
  read at all, which is the refusal that precedes every check above.

**NO FIGURE IS REPORTED, only whether figures agree and how many rows or days
are involved.** A delta between two printed totals is still a fact about a
customer's statement; a count of disagreeing days is a fact about the scan.
That is the batch-7 privacy rule applied to a diagnostic (§PRIVACY3), and it
costs this report nothing it needed.

READ-ONLY and $0: the sqlite index is never opened, artifacts are reached by
DIRECT file path, and only the two deterministic readers run.
"""
from __future__ import annotations

import argparse
import itertools
import json
from datetime import date, timedelta
from pathlib import Path

TOLERANCE = 0.005


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", required=True)
    parser.add_argument("--sha-file", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def _walk(rows, opening: float, seed: str | None = None) -> dict[str, float]:
    walked: dict[str, float] = {} if seed is None else {seed: opening}
    running = opening
    for row in sorted(rows, key=lambda item: item.date):
        running = round(running + row.amount, 2)
        walked[row.date] = running
    return walked


def _grid_verdict(walked, printed) -> dict[str, int]:
    days = {entry.date: entry.balance for entry in printed}
    return {
        "grid_days_printed": len(printed),
        "grid_days_disagreeing": sum(
            1 for day, balance in days.items()
            if day in walked and abs(walked[day] - balance) > TOLERANCE),
        "grid_days_missing": len(set(walked) - set(days)),
        "grid_days_invented": len(set(days) - set(walked)),
    }


def sectioned(module, markdown: str) -> dict[str, object] | None:
    summary = module._summary(markdown)
    if summary is None:
        return {"template": "sectioned", "summary_read": False}
    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    sections = module._sections(markdown)
    rows, unreadable = [], []
    for name, credit, default in module._LEDGER_SECTIONS:
        block = sections.get(name)
        if block is None:
            continue
        found = module._rows(block, credit=credit, start=start, end=end, default=default)
        if found is None:
            unreadable.append(name)
            continue
        rows.extend(found)
    credits_ = [row for row in rows if row.direction == "credit"]
    debits = [row for row in rows if row.direction == "debit"]
    out: dict[str, object] = {
        "template": "sectioned",
        "summary_read": True,
        "unreadable_sections": unreadable,
        "rows_short_credit": len(credits_) - summary.credit_count,
        "rows_short_debit": len(debits) - summary.debit_count,
        "credits_agree": abs(sum(r.amount for r in credits_) - summary.credits) <= TOLERANCE,
        "debits_agree": abs(-sum(r.amount for r in debits) - summary.debits) <= TOLERANCE,
        "identity_closes": abs(
            summary.opening + summary.credits - summary.debits - summary.closing) <= TOLERANCE,
        "grid_printed": "DAILY BALANCE" in sections,
    }
    if out["grid_printed"] and not unreadable:
        printed = module._daily_balances(sections["DAILY BALANCE"], start=start, end=end)
        if printed is None:
            out["grid_unreadable"] = True
        else:
            out.update(_grid_verdict(_walk(rows, summary.opening), printed))
    return out


def daily(module, markdown: str) -> dict[str, object] | None:
    summary = module._summary(markdown)
    if summary is None:
        return {"template": "daily", "summary_read": False}
    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    seed = start - timedelta(days=1)
    sections = module._sections(markdown)
    rows, unreadable = [], []
    for name, credit, default in module._LEDGER_SECTIONS:
        block = sections.get(name)
        if block is None:
            continue
        found = module._rows(block, credit=credit, start=start, end=end, default=default)
        if found is None:
            unreadable.append(name)
            continue
        rows.extend(found)
    credits_ = sum(row.amount for row in rows if row.direction == "credit")
    debits = -sum(row.amount for row in rows if row.direction == "debit")
    out: dict[str, object] = {
        "template": "daily",
        "summary_read": True,
        "unreadable_sections": unreadable,
        "credit_rows": sum(1 for row in rows if row.direction == "credit"),
        "debit_rows": sum(1 for row in rows if row.direction == "debit"),
        "credits_agree": abs(credits_ - summary.additions) <= TOLERANCE,
        "debits_agree": abs(debits - summary.subtractions) <= TOLERANCE,
        "identity_closes": abs(
            summary.beginning + summary.additions - summary.subtractions
            - summary.ending) <= TOLERANCE,
        "grid_printed": "DAILY BALANCES" in sections,
    }
    if out["grid_printed"] and not unreadable:
        printed = module._grid(sections["DAILY BALANCES"], seed=seed, end=end)
        if printed is None:
            out["grid_unreadable"] = True
        else:
            out.update(_grid_verdict(
                _walk(rows, summary.beginning, seed=seed.isoformat()), printed))
    return out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from analysis import core_processor_daily as daily_module
    from analysis import core_processor_sectioned as sectioned_module
    from analysis import parser_registry_entries  # noqa: F401
    from analysis.parser_registry import prepare, safe_detect, by_id
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )

    baseline = args.baseline_settings_key.strip().upper()
    root = args.data_dir / "artifacts"
    ocr_keys = [ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
                for f, l, v in itertools.product((False, True), repeat=3)]
    shas = [line.strip().upper()
            for line in args.sha_file.read_text(encoding="utf-8").splitlines()
            if line.strip()]

    reports = []
    for sha in shas:
        candidates = []
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
                source_file="ceiling.pdf", model=str(document.get("model") or ""),
                pages=pages).to_markdown(), pages))
        if not candidates:
            reports.append({"content_sha256": sha, "verdict": "no_ocr_artifact"})
            continue
        markdown, pages = candidates[0]
        for text, page_list in candidates:
            composed = cache_key(STAGE_ANALYSIS, analysis_input_sha(text, page_list), baseline)
            if (root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json").exists():
                markdown, pages = text, page_list
                break
        prepared = prepare(markdown)
        entry: dict[str, object] = {"content_sha256": sha}
        if safe_detect(by_id("core_processor_sectioned"), prepared).claims:
            entry.update(sectioned(sectioned_module, markdown) or {})
        elif safe_detect(by_id("core_processor_daily"), prepared).claims:
            entry.update(daily(daily_module, markdown) or {})
        else:
            entry["verdict"] = "not_this_complex"
        reports.append(entry)

    text = json.dumps({"documents": len(reports), "reports": reports}, indent=1)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
