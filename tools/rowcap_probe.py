"""rowcap_probe.py — the WH-ROW-CAPTURE signature probe.

    python -m tools.rowcap_probe --run <run dir> --data-dir <cold cache>
        [--parser scotiabank ...] [--shas <file>] [--out <private>.md]

For every document the run of record CLAIMED with one of the named readers,
re-runs THIS tree's reader over the run's own cached text and reports what the
row capture looks like AGAINST THE PAPER'S OWN ARITHMETIC — never a value:

* `rows` — postings published, and `stated` — the instance count the bank
  itself printed (credits + debits) where it prints one, with their difference.
  A positive difference is rows read LONG (duplicated); a negative one is rows
  MISSED.
* `cov cr/db` — published credit and debit totals as a RATIO of the totals the
  bank printed. 1.0 / 1.0 is the paper's own answer.
* `chain` — postings whose printed running balance does not move by the
  magnitude printed beside it. This is the row-grammar's own contradiction
  count and it is independent of the summary.
* `order` — whether the postings come out in the order the bank DATED them.
  `binder` means the document's sheets are bound out of ledger order, which
  makes the print-order chain step across a boundary that is not a ledger step
  and makes the last printed row's balance a mid-period figure.
* `adb` — the NAMES of the ADB checks that fail, which is the ceiling: a
  document whose only failures are `ledger_reconciles_to_closing` and
  `final_balance_matches_statement_closing` is one whose ledger does not close,
  and one that also fails `daily_balance_count_equals_calendar_days` or
  `opening_balance_matches_statement` needs something row capture cannot give.

Shapes, names, counts and ratios only: no amount, no date, no description and
no account number ever reaches the report. Read-only over the archive and the
cold cache; no OCR, no model, $0.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")


def load_rows(run: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with (run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if sha and sha not in rows:
                rows[sha] = row
    return rows


class ColdCache:
    """The run's own cached text, by content sha. Nothing is written."""

    def __init__(self, data_dir: Path):
        self.root = data_dir / "artifacts"
        self.conn = sqlite3.connect(
            f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
        from ocr.document import StatementMarkdown
        self._markdown = StatementMarkdown

    def text(self, sha: str) -> str | None:
        found = self.conn.execute(
            "SELECT artifact_path FROM artifact_cache WHERE stage = ? AND input_sha256 = ?",
            ("ocr", sha)).fetchall()
        if not found:
            return None
        try:
            payload = json.loads((self.root / found[0][0]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            return None
        pages = [str(page) for page in (document.get("pages") or [])]
        return self._markdown(source_file="probe.pdf",
                              model=str(document.get("model") or ""),
                              pages=pages).to_markdown()


def _ratio(published: float | None, stated: float | None) -> str:
    if published is None or not stated:
        return "-"
    return f"{published / stated:.3f}"


def probe_one(markdown: str) -> dict:
    from analysis.pipeline import analyze_markdown

    report = analyze_markdown(markdown, parse_mode="deterministic")
    statement = report.statement
    postings = list(statement.transactions or [])
    credits = [t for t in postings if (t.amount or 0) > 0]
    debits = [t for t in postings if (t.amount or 0) < 0]

    stated_count = None
    if statement.stated_credit_count is not None and statement.stated_debit_count is not None:
        stated_count = statement.stated_credit_count + statement.stated_debit_count

    previous = statement.beginning_balance
    chain_breaks = 0
    for posting in postings:
        balance = posting.running_balance
        if balance is None or previous is None:
            previous = balance if balance is not None else previous
            continue
        if abs(round(balance - previous, 2) - (posting.amount or 0.0)) > 0.005:
            chain_breaks += 1
        previous = balance

    dates = [posting.date for posting in postings]
    order = "dated" if dates == sorted(dates) else "binder"

    adb = report.metrics.adb
    failed = sorted(name for name, ok in (adb.validations or {}).items() if not ok) if adb else []

    return {
        "reader": statement.bank or "-",
        "rows": len(postings),
        "credits": len(credits),
        "debits": len(debits),
        "stated": stated_count,
        "delta": None if stated_count is None else len(postings) - stated_count,
        "cov_credit": _ratio(sum(t.amount for t in credits) if credits else 0.0,
                             statement.stated_total_credits),
        "cov_debit": _ratio(-sum(t.amount for t in debits) if debits else 0.0,
                            statement.stated_total_debits),
        "chain": chain_breaks,
        "order": order,
        "adb_ok": bool(adb.ok) if adb else False,
        "adb_failed": failed,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--parser", action="append", default=[],
                        help="baseline parser_id (repeatable)")
    parser.add_argument("--shas", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    rows = load_rows(args.run)

    chosen: set[str] = set()
    if args.shas:
        # A census names documents by their 16-character prefix; the cache is
        # keyed by the whole content sha. Resolve through the run's own rows so
        # a `--shas` file written from `clusters.json` selects the same
        # documents a `--parser` sweep would.
        wanted = {line.strip().upper() for line in
                  args.shas.read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.strip().startswith("#")}
        for sha in rows:
            if sha in wanted or sha[:16] in wanted:
                chosen.add(sha)
    for sha, row in rows.items():
        if (row.get("parser_id") or "") in args.parser:
            chosen.add(sha)

    cache = ColdCache(args.data_dir)
    lines = ["| sha16 | baseline | reader | rows | stated | delta | cov cr | cov db "
             "| chain | order | adb | failing ADB checks |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|"]
    counted = 0
    for sha in sorted(chosen):
        markdown = cache.text(sha)
        baseline = rows.get(sha, {})
        outcome = (baseline.get("outcome_class") or baseline.get("outcome") or "-")
        if markdown is None:
            lines.append(f"| {sha[:16]} | {outcome} | - | - | - | - | - | - | - | - | no text | |")
            continue
        try:
            fact = probe_one(markdown)
        except Exception as error:  # noqa: BLE001 — a probe never stops on one document
            lines.append(f"| {sha[:16]} | {outcome} | - | - | - | - | - | - | - | - "
                         f"| raised | {type(error).__name__} |")
            continue
        counted += 1
        lines.append(
            f"| {sha[:16]} | {outcome} | {fact['reader']} | {fact['rows']} "
            f"| {fact['stated'] if fact['stated'] is not None else '-'} "
            f"| {fact['delta'] if fact['delta'] is not None else '-'} "
            f"| {fact['cov_credit']} | {fact['cov_debit']} | {fact['chain']} "
            f"| {fact['order']} | {'ok' if fact['adb_ok'] else 'no'} "
            f"| {', '.join(fact['adb_failed']) or '-'} |")
    table = "\n".join(lines) + f"\n\nprobed {counted} of {len(chosen)}\n"
    print(table)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(table, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
