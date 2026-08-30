"""rowcap_wells_cells.py — the currency-symbol census, over both populations.

    python -m tools.rowcap_wells_cells --run <run dir> --data-dir <cold cache>
        [--parser wells_fargo] [--out <private>.md]

W3 §ROWCAP's wells change rests on one measurement: across every document this
reader claimed, a money cell carrying the currency symbol is the transaction
history's own restatement and never a posting amount. The load-bearing half of
that is small and exact — how many symbol-carrying cells there are and which
documents they sit on — and it reproduces under any reading. The DENOMINATORS
do not: a record can be counted two ways, and the two answers differ.

So this reports both, side by side, and names them:

* **printed** — every `WF_TX` record the document carries, wherever it sits.
  This is the archive-wide denominator: it asks what the native grid emitted
  for these statements at all.
* **published** — every record inside the account section the reader publishes
  (`analysis.wells._published_section`, then `_transaction_rows`). This is the
  reader's own denominator: it asks what the refusal is actually applied to.

The second is a subset of the first, and the difference is the records the
reader never reaches — a Wells statement bundles several accounts' sections and
publishes the one the bank marks primary. The symbol counts are reported
against both, and the conclusion the reader rests on is the one that holds in
either: the symbol-carrying cells are the same cells, on the same documents.

Counts and content shas only: no amount, no date, no description and no account
number reaches the report. Read-only over the archive and the cold cache; no
OCR, no model, $0.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rowcap_probe import ColdCache, DEFAULT_DATA_DIR, DEFAULT_RUN_POINTER, load_rows  # noqa: E402

_SYMBOL = "$"


def _tally(records) -> dict[str, int]:
    """Counts over one list of `(mmdd, description, credit, debit, balance)`."""
    money_cells = balance_cells = symbol_money = symbol_balance = 0
    for _mmdd, _description, credit, debit, balance in records:
        for cell in (credit, debit):
            if cell:
                money_cells += 1
                if _SYMBOL in cell:
                    symbol_money += 1
        if balance:
            balance_cells += 1
            if _SYMBOL in balance:
                symbol_balance += 1
    return {
        "records": len(records),
        "money_cells": money_cells,
        "balance_cells": balance_cells,
        "symbol_money": symbol_money,
        "symbol_balance": symbol_balance,
    }


def census(markdown: str) -> dict[str, dict[str, int]]:
    from analysis.wells import _published_section, _transaction_rows

    lines = markdown.splitlines()
    return {
        "printed": _tally(_transaction_rows(lines)),
        "published": _tally(_transaction_rows(_published_section(lines))),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--parser", action="append", default=["wells_fargo"])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    rows = load_rows(args.run)
    chosen = sorted(sha for sha, row in rows.items()
                    if (row.get("parser_id") or "") in args.parser)

    cache = ColdCache(args.data_dir)
    totals = {
        scope: dict.fromkeys(
            ("records", "money_cells", "balance_cells", "symbol_money", "symbol_balance"), 0)
        for scope in ("printed", "published")
    }
    read = 0
    carriers: dict[str, set[str]] = {"printed": set(), "published": set()}
    for sha in chosen:
        cached = cache.text(sha)
        if cached is None:
            continue
        read += 1
        for scope, tally in census(cached[0]).items():
            for key, value in tally.items():
                totals[scope][key] += value
            if tally["symbol_money"] or tally["symbol_balance"]:
                carriers[scope].add(sha[:16])

    lines = [
        f"| population | records | money cells | balance cells | money cells with the "
        f"symbol | balance cells with the symbol |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for scope in ("printed", "published"):
        t = totals[scope]
        lines.append(
            f"| {scope} | {t['records']} | {t['money_cells']} | {t['balance_cells']} "
            f"| **{t['symbol_money']}** | **{t['symbol_balance']}** |")
    lines.append("")
    lines.append(f"documents claimed {len(chosen)}, read {read}")
    for scope in ("printed", "published"):
        named = ", ".join(sorted(carriers[scope])) or "none"
        lines.append(f"{scope}: documents carrying a symbol cell — {named}")
    table = "\n".join(lines) + "\n"
    print(table)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(table, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
