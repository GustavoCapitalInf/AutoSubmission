"""W3 §COREENC C6: how far each published ledger outruns its printed counts.

The card states, in three places — `analysis/count_semantics.py`'s
`SECTION_LEVEL_ORACLES` entry, the module docstring and §COREENC C6 — that this
template's two printed counts each EXCLUDE a row class the ledger nonetheless
posts. That is a claim about a population, so it is measured by an instrument
rather than described:

    python -m tools.coreenc_count_scope \\
        --data-dir <checkout>/webapp_data \\
        --shas <file with one content_sha256 per line> [--out scope.json]

For every named document it runs the REAL reader
(`parse_core_processor_enclosures_statement`) over the cached OCR text and then
compares what the reader published against what the strip printed:

* `credit_excess` — published credit rows minus the printed credit count;
* `credit_excess_is_the_printed_interest` — whether the published credit money
  in excess of the printed credit TOTAL equals the printed `Interest Paid`
  figure to the cent;
* `debit_excess` and `debit_excess_is_the_printed_charge` — the same on the
  debit side against the printed service charge.

A document the reader declines cannot be measured on either side and is
reported as `declined`, so the denominator is explicit rather than assumed.

READ-ONLY and $0. Nothing is written to the archive or the artifact store, the
`webapp_data` sqlite index is never opened (OCR payloads are reached by DIRECT
file path across every capability partition of `ocr_settings_key`, longest
reconstruction wins), no model is called and no OCR is run.

**No document text, amount, name, account number or date is printed.** Each
document is named by its `content_sha256` and carries integer row counts, the
integer excesses, and booleans about whether the excess money equals a printed
figure. The figures themselves never leave the process.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

#: The cent the printed figures are rounded to — the reader's own tolerance.
_TOLERANCE = 0.005


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", required=True, type=Path,
                        help="the webapp_data directory")
    parser.add_argument("--shas", required=True, type=Path,
                        help="the named population, one content_sha256 per line")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the full report here")
    return parser.parse_args(argv)


def _ocr_text(root: Path, sha: str, ocr_keys: list[str]) -> str | None:
    """The longest cached OCR reconstruction of one document, by direct path."""
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key

    best: str | None = None
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
        markdown = StatementMarkdown(
            source_file="scope.pdf", model=str(document.get("model") or ""),
            pages=[str(page) for page in (document.get("pages") or [])],
        ).to_markdown()
        if best is None or len(markdown) > len(best):
            best = markdown
    return best


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from analysis.core_processor_enclosures import (
        detect, parse_core_processor_enclosures_statement,
    )
    from webapp.artifact_cache import ocr_settings_key

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]
    named = [line.strip().upper() for line in
             args.shas.read_text(encoding="utf-8").split() if line.strip()]

    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for sha in named:
        markdown = _ocr_text(root, sha, ocr_keys)
        if markdown is None:
            rows.append({"content_sha256": sha, "state": "no_ocr_artifact"})
            continue
        claims = bool(detect(markdown).claims)
        statement = parse_core_processor_enclosures_statement(markdown) if claims else None
        if statement is None:
            rows.append({"content_sha256": sha,
                         "state": "declined" if claims else "not_claimed"})
            continue
        credits = [row for row in statement.transactions if row.direction == "credit"]
        debits = [row for row in statement.transactions if row.direction == "debit"]
        credited = sum(row.amount for row in credits)
        debited = -sum(row.amount for row in debits)
        interest = statement.stated_interest_paid or 0.0
        charge = statement.stated_service_charge or 0.0
        rows.append({
            "content_sha256": sha,
            "state": "published",
            "credit_rows": len(credits),
            "credit_excess": len(credits) - (statement.stated_credit_count or 0),
            "prints_an_interest_credit": interest > 0,
            "credit_excess_is_the_printed_interest": abs(
                credited - (statement.stated_total_credits or 0.0) - interest
            ) <= _TOLERANCE,
            "debit_rows": len(debits),
            "debit_excess": len(debits) - (statement.stated_debit_count or 0),
            "prints_a_service_charge": charge > 0,
            "debit_excess_is_the_printed_charge": abs(
                debited - (statement.stated_total_debits or 0.0) - charge
            ) <= _TOLERANCE,
        })

    published = [row for row in rows if row["state"] == "published"]
    summary: dict[str, object] = {
        "named": len(named),
        "seconds": round(time.perf_counter() - started, 1),
        "published": len(published),
        "declined": sum(1 for row in rows if row["state"] == "declined"),
        "not_claimed": sum(1 for row in rows if row["state"] == "not_claimed"),
        "no_ocr_artifact": sum(1 for row in rows if row["state"] == "no_ocr_artifact"),
    }
    for side, excess_key, printed_key, money_key in (
        ("credit", "credit_excess", "prints_an_interest_credit",
         "credit_excess_is_the_printed_interest"),
        ("debit", "debit_excess", "prints_a_service_charge",
         "debit_excess_is_the_printed_charge"),
    ):
        table: dict[str, dict[str, int]] = {}
        for row in published:
            bucket = table.setdefault(str(row[excess_key]),
                                      {"documents": 0, "prints_the_figure": 0,
                                       "excess_money_equals_it": 0})
            bucket["documents"] += 1
            bucket["prints_the_figure"] += int(bool(row[printed_key]))
            bucket["excess_money_equals_it"] += int(bool(row[money_key]))
        summary[f"{side}_excess"] = dict(sorted(table.items(), key=lambda kv: int(kv[0])))
        summary[f"{side}_documents_with_an_excess"] = sum(
            1 for row in published if int(row[excess_key]) > 0)
    report = {"summary": summary, "rows": rows}
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    json.dump(summary, sys.stdout, indent=1)
    print()
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
