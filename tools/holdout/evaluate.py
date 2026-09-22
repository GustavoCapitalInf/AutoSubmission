"""The holdout evaluation event (P22-HOLDOUT item 4) — design plus a working
skeleton; the first REAL evaluation is Phase 2.4's.

    python -m tools.holdout.evaluate --rows <run>/rows.csv --engine-version <key or tag>
        --run-id <id> [--figures <csv>] [--ledger <csv>] [--report <PRIVATE path>]

For every holdout item in `unseen | evaluated` that has BOTH a sealed oracle
record and a row in the run: the system's verdict and key figures are
compared with the oracle; every miss is classed A / B / C from the row's
`failure_class` and reasons; the judgements are

    false_accept        system `validated` AND the oracle contradicts a money
                        identity (a parsed figure) or a sampled row — never the
                        verdict alone, never an unparseable export value
    kind_conflict       system `validated`, no figure/row contradiction, but the
                        oracle's kind is not STATEMENT_COMPLETE (reported on
                        its own line; never summed with false_accept)
    agree               system `validated`, no contradiction, and at least ONE
                        money identity compared (opening / closing balance, or
                        a sampled row against the ledger)
    agree_partial       system `validated`, no contradiction, only non-money
                        figures compared (account_count, period, counts)
    not_judgeable       system `validated`, nothing comparable was supplied
    false_refusal       oracle complete + legible statement, system not validated
    consistent_refusal  system not validated and the oracle agrees it is not a
                        complete legible statement

`layout_generalization` counts validated, non-contradicted items whose stratum
is `unknown_bank`, read natively when digital. Items compared are marked
`evaluated` with the engine version and the run id. Stdout carries aggregates
only; the per-item detail (sha16, judgement, contradiction NAMES — no figures)
goes to the private report, which refuses a path inside the checkout. The
store and the manifest are verified against their sidecar manifests before
anything is read (a truncated file refuses the evaluation).

What the skeleton cannot judge without help: `rows.csv` carries no balances,
periods or ledger rows, so a money identity is compared only when a per-sha
`--figures` export (opening / closing / period / counts) is supplied, and a
sampled row only when a per-sha `--ledger` export (date, description, amount)
is; with `rows.csv` alone the only comparable figure is the row's
`account_count`, which can yield `agree_partial` at most. A value that does
not parse (a figure export's `n/a`) is NOT compared — it is listed under
`unparseable` in the detail and never becomes a contradiction. A system
`refused` row (R11, cell T) classes as `unclassified` until its reasons are
mapped here. Money is compared as `Decimal` VALUES (never as text): `100`,
`100.00` and `100.000` are one figure, `-0.00` is `0`, and a ledger amount
matches a sampled row whatever scale either side printed (review NEW-1).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .manifest import HoldoutManifest
from .store import (
    StoreError,
    TruthStore,
    _retry,
    description_hash,
    refuse_inside_checkout,
    utc_now_iso,
)

LADDER = {"failed": 0, "deferred": 0, "withheld": 1, "review": 2, "validated": 3}
FIGURE_FIELDS = (
    "account_count",
    "printed_period_start",
    "printed_period_end",
    "opening_balance",
    "closing_balance",
    "printed_transaction_count",
)
MONEY_FIELDS = ("opening_balance", "closing_balance")
JUDGEMENTS = (
    "false_accept",
    "kind_conflict",
    "agree",
    "agree_partial",
    "not_judgeable",
    "false_refusal",
    "consistent_refusal",
    "not_adjudicated",
    "not_in_run",
)
MISS_CLASSES = ("A", "B", "C", "unclassified")
#: Reason -> class when the row carries no `failure_class` (the run of record's
#: own vocabulary: extraction-level reasons are A, dispatch reasons B,
#: validator reasons C).
_REASON_CLASS = {
    "deferred_visual_ocr": "A",
    "invalid_pdf": "A",
    "no_parser_matched": "B",
    "parser_declined": "B",
    "withheld_adb": "C",
    "integrity_flags": "C",
}
_UNPARSEABLE = object()


def classify_miss(row: Mapping) -> str:
    failure_class = (row.get("failure_class") or "").strip().upper()
    if failure_class in ("A", "B", "C"):
        return failure_class
    return _REASON_CLASS.get((row.get("outcome_reason") or "").strip(), "unclassified")


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def best_row_per_sha(rows_csv: Path) -> dict[str, dict]:
    """One row per sha: the best outcome on the ladder (a duplicate path with
    a worse outcome never hides a validated one); ties by relative path."""
    best: dict[str, dict] = {}
    rows = sorted(_read_csv(rows_csv), key=lambda r: (r.get("relative_path") or ""))
    for row in rows:
        sha = (row.get("content_sha256") or "").strip().upper()
        if not sha:
            continue
        rank = LADDER.get((row.get("outcome_class") or "").strip(), 0)
        current = best.get(sha)
        if current is None or rank > LADDER.get((current.get("outcome_class") or "").strip(), 0):
            best[sha] = row
    return best


def _canon_money(value):
    """The VALUE of a money figure as a `Decimal` (scale is not meaning: `100`
    == `100.00` == `100.000`; negative zero is zero) — review NEW-1."""
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        figure = Decimal(text)
    except InvalidOperation:
        return _UNPARSEABLE
    if not figure.is_finite():
        return _UNPARSEABLE
    return Decimal(0) if figure == 0 else figure


def money_key(value) -> str | None:
    """A scale-free, sign-of-zero-free text key for a money value (the ledger
    key and the sampled-row key must agree whatever scale each side printed)."""
    figure = _canon_money(value)
    if figure is None or figure is _UNPARSEABLE:
        return None
    return format(figure.normalize(), "f")


def _canon_date(value):
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return _UNPARSEABLE


def _canon_count(value):
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        return str(int(text))
    except ValueError:
        return _UNPARSEABLE


_CANON = {
    "account_count": _canon_count,
    "printed_period_start": _canon_date,
    "printed_period_end": _canon_date,
    "opening_balance": _canon_money,
    "closing_balance": _canon_money,
    "printed_transaction_count": _canon_count,
}


def load_figures(path: Path | None) -> dict[str, dict[str, str]]:
    figures: dict[str, dict[str, str]] = {}
    if path is None:
        return figures
    for row in _read_csv(path):
        sha = (row.get("content_sha256") or "").strip().upper()
        if not sha:
            continue
        figures[sha] = {
            field: row[field].strip()
            for field in FIGURE_FIELDS
            if row.get(field) is not None and str(row[field]).strip()
        }
    return figures


def load_ledger(path: Path | None) -> dict[str, set[tuple[str, str, str]]] | None:
    if path is None:
        return None
    ledger: dict[str, set[tuple[str, str, str]]] = {}
    for row in _read_csv(path):
        sha = (row.get("content_sha256") or "").strip().upper()
        if not sha:
            continue
        when = _canon_date(row.get("date"))
        amount = money_key(row.get("amount"))
        if when in (None, _UNPARSEABLE) or amount is None:
            continue  # an unparseable ledger row is never evidence of anything
        key = (when, description_hash(row.get("description") or ""), amount)
        ledger.setdefault(sha, set()).add(key)
    return ledger


def compare_figures(oracle: Mapping, system: Mapping) -> tuple[list[str], int, int, list[str]]:
    """(contradictions, compared, money_compared, unparseable). A field is
    compared only when both sides carry a value that PARSES; an unparseable
    system value is listed, never a contradiction (review MINOR-3a)."""
    contradictions: list[str] = []
    unparseable: list[str] = []
    compared = 0
    money_compared = 0
    for field in FIGURE_FIELDS:
        oracle_value = oracle.get(field)
        system_value = system.get(field)
        if oracle_value is None or system_value is None or str(system_value).strip() == "":
            continue
        canonical_oracle = _CANON[field](oracle_value)
        canonical_system = _CANON[field](system_value)
        if canonical_system is _UNPARSEABLE or canonical_oracle is _UNPARSEABLE:
            unparseable.append(field)
            continue
        compared += 1
        if field in MONEY_FIELDS:
            money_compared += 1
        if canonical_oracle != canonical_system:  # Decimal vs Decimal for money: a VALUE comparison
            contradictions.append(field)
    return contradictions, compared, money_compared, unparseable


def compare_rows(oracle_rows, ledger_rows) -> tuple[list[str], int]:
    if ledger_rows is None:
        return [], 0
    contradictions: list[str] = []
    compared = 0
    for sampled in oracle_rows:
        compared += 1
        key = (sampled["date"], sampled["description_hash"], money_key(sampled["amount"]))
        if key not in ledger_rows:
            contradictions.append("sampled_row_absent")
    return contradictions, compared


def evaluate_run(
    rows_csv: Path,
    *,
    store: TruthStore,
    manifest: HoldoutManifest,
    engine_version: str,
    run_id: str,
    figures_csv: Path | None = None,
    ledger_csv: Path | None = None,
    report_path: Path | None = None,
    out=print,
    now: str | None = None,
) -> dict:
    report_target = (
        refuse_inside_checkout(report_path, what="the evaluation report")
        if report_path is not None else None
    )
    store.verify_against_manifest()  # MAJOR-1: a truncated store never feeds an evaluation
    manifest.verify_against_manifest()
    rows = best_row_per_sha(Path(rows_csv))
    figures = load_figures(figures_csv)
    ledger = load_ledger(ledger_csv)
    oracle = store.latest_by_sha()
    items = sorted(
        (item for item in manifest.items().values() if item["status"] in ("unseen", "evaluated")),
        key=lambda item: item["holdout_id"],
    )

    counts: Counter = Counter()
    miss: Counter = Counter({cls: 0 for cls in MISS_CLASSES})
    generalization = 0
    compared_items = 0
    details: list[dict] = []

    for item in items:
        sha = item["content_sha256"]
        detail = {
            "holdout_id": item["holdout_id"],
            "sha16": sha[:16],
            "status_before": item["status"],
            "strata": item["strata"],
            "judgement": None,
            "system_outcome": None,
            "oracle_kind": None,
            "miss_class": None,
            "contradictions": [],
            "unparseable": [],
            "compared": 0,
            "money_compared": 0,
            "layout_generalization": False,
        }
        truth = oracle.get(sha)
        row = rows.get(sha)
        if truth is None:
            detail["judgement"] = "not_adjudicated"
            counts["not_adjudicated"] += 1
            details.append(detail)
            continue
        detail["oracle_kind"] = truth["kind"]
        if row is None:
            detail["judgement"] = "not_in_run"
            counts["not_in_run"] += 1
            details.append(detail)
            continue

        system_outcome = (row.get("outcome_class") or "").strip()
        detail["system_outcome"] = system_outcome
        system_figures = dict(figures.get(sha, {}))
        if "account_count" not in system_figures and (row.get("account_count") or "").strip():
            system_figures["account_count"] = row["account_count"].strip()
        oracle_figures = {field: truth.get(field) for field in FIGURE_FIELDS}
        contradictions, compared, money_compared, unparseable = compare_figures(oracle_figures, system_figures)
        row_contradictions, row_compared = compare_rows(
            truth.get("sampled_rows", []), None if ledger is None else ledger.get(sha)
        )
        contradictions += row_contradictions
        compared += row_compared
        money_compared += row_compared  # a sampled row carries an amount: a money identity
        detail["contradictions"] = contradictions
        detail["unparseable"] = unparseable
        detail["compared"] = compared
        detail["money_compared"] = money_compared

        oracle_complete = truth["kind"] == "STATEMENT_COMPLETE" and bool(truth["legible"])
        if system_outcome == "validated":
            if contradictions:
                judgement = "false_accept"
            elif truth["kind"] != "STATEMENT_COMPLETE":
                judgement = "kind_conflict"
            elif compared > 0 and money_compared > 0:
                judgement = "agree"
            elif compared > 0:
                judgement = "agree_partial"
            else:
                judgement = "not_judgeable"
        elif oracle_complete:
            judgement = "false_refusal"
            detail["miss_class"] = classify_miss(row)
            miss[detail["miss_class"]] += 1
        else:
            judgement = "consistent_refusal"
        detail["judgement"] = judgement
        counts[judgement] += 1

        strata = item["strata"]
        generalizes = (
            system_outcome == "validated"
            and judgement in ("agree", "agree_partial", "not_judgeable")
            and strata.get("bank_familiarity") == "unknown_bank"
            and (strata.get("modality") != "digital" or (row.get("source_path") or "") == "native")
        )
        detail["layout_generalization"] = generalizes
        generalization += int(generalizes)

        manifest.record_evaluation(
            item["holdout_id"], engine_version=engine_version, evaluation_run_id=run_id,
            evaluated_at=now,
        )
        compared_items += 1
        details.append(detail)

    result = {
        "items": len(items),
        "compared": compared_items,
        "engine_version": engine_version,
        "run_id": run_id,
        "evaluated_at": now or utc_now_iso(),
        **{judgement: counts[judgement] for judgement in JUDGEMENTS},
        "miss_class": {cls: miss[cls] for cls in MISS_CLASSES},
        "layout_generalization": generalization,
        "details": details,
    }
    for key in ("items", "compared", *JUDGEMENTS, "layout_generalization"):
        out(f"{key}: {result[key]}")
    out("miss_class: " + " ".join(f"{cls}={miss[cls]}" for cls in MISS_CLASSES))
    out(f"engine_version: {engine_version}")

    if report_target is not None:
        aggregates = {k: v for k, v in result.items() if k != "details"}
        text = json.dumps({"aggregates": aggregates, "details": details}, indent=2, sort_keys=True)

        def _write():
            report_target.parent.mkdir(parents=True, exist_ok=True)
            report_target.write_text(text + "\n", encoding="utf-8")

        _retry(_write)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=Path, required=True, help="a run's rows.csv")
    parser.add_argument("--engine-version", required=True, help="a settings key or freeze tag")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--figures", type=Path, default=None, help="per-sha system figures (private)")
    parser.add_argument("--ledger", type=Path, default=None, help="per-sha system rows (private)")
    parser.add_argument("--report", type=Path, default=None, help="PRIVATE report path, outside the checkout")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        store = TruthStore.open()
        manifest = HoldoutManifest.open()
        evaluate_run(
            args.rows, store=store, manifest=manifest, engine_version=args.engine_version,
            run_id=args.run_id, figures_csv=args.figures, ledger_csv=args.ledger,
            report_path=args.report,
        )
    except StoreError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
