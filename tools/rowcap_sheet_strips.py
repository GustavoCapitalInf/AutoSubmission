"""rowcap_sheet_strips.py — the Scotiabank sheet strips, as an independent check.

    python -m tools.rowcap_sheet_strips --run <run dir> --data-dir <cold cache>
        --shas <population> [--out <private>.md]

Scotiabank prints, at the foot of every sheet, that sheet's own debit count and
total and credit count and total. `analysis/scotia.py` never reads them — it
takes each row's direction from the printed running balance — so they are an
INDEPENDENT check on every direction the reader assigned, and on the ordering
this card put the sheets back into: a row whose direction is wrong changes two
of its sheet's four printed figures at once.

Per document it reports how many sheet strips the published ledger reproduces
EXACTLY, in count and in total, and how many it does not. Counts only: no
amount, no date, no description and no account number reaches the report.

Page one carries two strips — the account-level one printed above
`Account Details:` and the sheet's own at the foot — and it is the sheet's,
the last on the page, that is checked here.

Read-only over the archive and the cold cache; no OCR, no model, $0.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rowcap_probe import ColdCache, DEFAULT_DATA_DIR, DEFAULT_RUN_POINTER, load_rows  # noqa: E402

_STRIP = re.compile(
    r"No\. of Debits Total Amount - Debits No\. of Credits Total Amount\s+-\s+Credits\s+"
    r"(\d+)\s+\$([\d,]+\.\d{2})\s+(\d+)\s+\$([\d,]+\.\d{2})")


def _sheet_rows(page: str) -> list[tuple[str, str, float, float]]:
    """The sheet's own posting rows, read with the reader's own sweep."""
    import analysis.scotia as scotia
    from analysis.money import parse_money

    rows: list[tuple[str, str, float, float]] = []
    for table in scotia._posting_tables(page):
        for row in scotia._split_rows(table):
            found = scotia._DATE_RE.search(row)
            if not found:
                continue
            rest = row[found.end():].strip()
            if rest.upper().startswith("BALANCE FORWARD"):
                continue
            tokens = rest.split()
            balance_at = next((i for i in range(len(tokens) - 1, -1, -1)
                               if scotia._is_balance_cell(tokens[i])), None)
            if balance_at is None:
                continue
            amount_at = next((i for i in range(balance_at - 1, -1, -1)
                              if scotia._is_amount_cell(tokens[i])), None)
            if amount_at is None:
                continue
            balance = parse_money(tokens[balance_at])
            amount = scotia._amount_value(tokens[amount_at])
            description = " ".join(tokens[:amount_at]).strip()
            if balance is None or amount is None or not description:
                continue
            rows.append((f"{found.group(3)}-{found.group(1)}-{found.group(2)}",
                         description, balance, abs(amount)))
    return rows


def check(markdown: str, pages: list[str]) -> tuple[int, int]:
    """(strips reproduced exactly, strips that differ)."""
    from analysis.pipeline import analyze_markdown

    statement = analyze_markdown(
        markdown, parse_mode="deterministic", sheets=pages).statement
    published: dict[tuple, list[float]] = {}
    for txn in statement.transactions or []:
        published.setdefault((txn.date, txn.description, txn.running_balance), []).append(txn.amount)

    agree = differ = 0
    for page in markdown.split("--- Page "):
        strips = list(_STRIP.finditer(re.sub(r"\s+", " ", page)))
        rows = _sheet_rows(page)
        if not strips or not rows:
            continue
        strip = strips[-1]
        credits = debits = 0
        credit_total = debit_total = 0.0
        seen = True
        for date, description, balance, _magnitude in rows:
            amounts = published.get((date, description, balance))
            if not amounts:
                seen = False
                break
            value = amounts[0]
            if value > 0:
                credits += 1
                credit_total += value
            else:
                debits += 1
                debit_total += -value
        expected = (int(strip.group(1)), float(strip.group(2).replace(",", "")),
                    int(strip.group(3)), float(strip.group(4).replace(",", "")))
        got = (debits, round(debit_total, 2), credits, round(credit_total, 2))
        if seen and got[0] == expected[0] and got[2] == expected[2] \
                and abs(got[1] - expected[1]) <= 0.005 and abs(got[3] - expected[3]) <= 0.005:
            agree += 1
        else:
            differ += 1
    return agree, differ


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--shas", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    rows = load_rows(args.run)
    wanted = {line.strip().upper() for line in
              args.shas.read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.strip().startswith("#")}
    chosen = sorted(sha for sha in rows if sha in wanted or sha[:16] in wanted)

    cache = ColdCache(args.data_dir)
    lines = ["| sha16 | sheet strips | reproduced exactly | differing |", "|---|---:|---:|---:|"]
    for sha in chosen:
        cached = cache.text(sha)
        if cached is None:
            lines.append(f"| {sha[:16]} | no text | - | - |")
            continue
        agree, differ = check(*cached)
        lines.append(f"| {sha[:16]} | {agree + differ} | {agree} | {differ} |")
    table = "\n".join(lines) + f"\n\ndocuments {len(chosen)}\n"
    print(table)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(table, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
