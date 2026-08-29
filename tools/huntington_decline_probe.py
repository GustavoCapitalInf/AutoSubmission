"""huntington_decline_probe.py — WHICH gate declines each huntington document.

    python -m tools.huntington_decline_probe --run <run> --data-dir <cold cache> \
        [--shas <file> | --group DECL:huntington] [--out <private>.md] [--json <private>.json]

`analysis.huntington.parse_huntington_statement` is a chain of refusals: the
line-of-credit guard, the period, the summary, three section grammars and the
four printed identities of `_validate`. When it returns ``None`` the runner
records `failed / parser_declined` and nothing says WHICH link refused. This
instrument walks the same chain in the same order over the run of record's own
cached text and names the first link that refused, plus the structural facts a
widening decision needs.

It is a READ-ONLY diagnostic and it never prints a document value: no amount,
no date, no description, no account number, no customer token. Every digit in
any label it echoes is masked to ``#`` before it reaches the report, and money
is masked whole. What it prints is gate NAMES, block NAMES, booleans and
counts — the vocabulary a grammar decision is made in.

Classification (the card's three classes):

  ``L1``        the second-account refusal (`_LINE_OF_CREDIT_RE`) — an honest
                L-1 decline, out of scope for a coverage widening.
  ``GRAMMAR``   a gate before `_validate` refused, or `_validate` refused with
                a structural cause the text explains (a heading the grammar
                does not know, a section that produced no rows).
  ``IDENTITY``  every gate parsed and one of the four printed identities does
                not close — the document's own arithmetic, not our grammar.

The class is a summary of the trace, not a substitute for it: the trace is the
evidence and it is printed per sha.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_CLUSTERS = Path("docs/moneythumb-replacement/census_batch9/clusters.json")

#: Anything that could carry a document value is masked before it is printed.
#: Digits become ``#`` (account numbers, dates, amounts, reference numbers) and
#: a money-shaped token becomes ``<money>`` whole, so a masked figure can never
#: be reassembled from its punctuation.
_MONEY = re.compile(r"\$?\d[\d,]*\.\d{2}-?")
_DIGIT = re.compile(r"\d")


def mask(text: str) -> str:
    return _DIGIT.sub("#", _MONEY.sub("<money>", text))


# ---------------------------------------------------------------- the trace

def trace(markdown: str) -> dict:
    """Walk `parse_huntington_statement`'s refusal chain and name the refusal."""
    from analysis import huntington as H

    out: dict = {"gate": None, "class": None, "notes": []}

    out["claims"] = bool(H.detect(markdown).claims)
    if not out["claims"]:
        out.update(gate="detect", **{"class": "GRAMMAR"})
        return out

    if H._LINE_OF_CREDIT_RE.search(markdown):
        out.update(gate="line_of_credit", **{"class": "L1"})
        # The heading is the whole finding; nothing else is read for it.
        return out

    lines = H._lines(markdown)
    period = H._period(markdown)
    summary = H._summary(lines)
    out["period_ok"] = period is not None
    out["summary_ok"] = summary is not None
    # Is the EVIDENCE for an identity printed at all? Taken from the block's
    # own heading words anywhere in the document, not from what the grammar
    # managed to collect: "the parser found no rows" and "the bank printed no
    # table" are different findings and only the second is a document fact.
    out["fee_block_printed"] = any(
        phrase in markdown for phrase in ("Service Charge Detail", "Service Charge Summary"))
    out["daily_block_printed"] = any(
        phrase in markdown for phrase in ("Balance Activity", "Daily Balance"))
    if period is None:
        out.update(gate="_period", **{"class": "GRAMMAR"})
        return out
    if summary is None:
        out.update(gate="_summary", **{"class": "GRAMMAR"})
        return out
    start, end = period

    blocks = H._blocks(lines)
    out["blocks"] = [{"name": name, "sign": sign, "rows": len(body)} for name, sign, body in blocks]
    out["unknown_headings"] = unknown_headings(lines, H)
    out["summary_labels"] = sorted(summary)
    out["unread_figures"] = unread_figures(lines, blocks, H)

    txns = H._transactions(blocks, start, end)
    fees = H._service_charges(blocks, start, end)
    balances = H._daily_balances(blocks, start, end)
    out["transactions_ok"] = txns is not None
    out["service_charges_ok"] = fees is not None
    out["daily_balances_ok"] = balances is not None
    if txns is None:
        out.update(gate="_transactions", **{"class": "GRAMMAR"})
        return out
    if fees is None:
        out.update(gate="_service_charges", **{"class": "GRAMMAR"})
        out["fee_detail"] = fee_refusal(blocks, start, end, H)
        return out
    if balances is None:
        out.update(gate="_daily_balances", **{"class": "GRAMMAR"})
        return out

    fee_txns, service_net = fees
    out["n_section_txns"] = len(txns)
    out["n_fee_txns"] = len(fee_txns)
    out["n_daily_balances"] = len(balances)
    if not txns and not fee_txns:
        out.update(gate="no_rows", **{"class": "GRAMMAR"})
        return out

    checks = identities(summary, txns, fee_txns, service_net, balances, H)
    out["identities"] = checks
    failed = [name for name, ok in checks.items() if ok is False]
    out["identities_failed"] = failed
    if failed:
        out.update(gate="_validate:" + ",".join(failed), **{"class": "IDENTITY"})
        return out

    out.update(gate="none (parses)", **{"class": "PARSES"})
    return out


_HEADING_SHAPE = re.compile(r"^(.{0,60}?)\s+Account\s*:\s*-*\d+\s*$")


def unknown_headings(lines: list[str], H) -> list[str]:
    """Headings of this layout's shape that neither grammar recognises.

    The issuer heads every section and every block ``<name> Account: ----NNNN``.
    A line of that shape that `_SECTION_RE` and `_BLOCK_RE` both refuse is a
    part of the statement the grammar does not know it is looking at — the
    single most useful fact for a widening decision. The product line at the
    top of the statement has the same shape and is read by `_PRODUCT_RE`, so it
    is not unknown and is not reported. Names only; masked.
    """
    unknown: list[str] = []
    for line in lines:
        if not _HEADING_SHAPE.match(line):
            continue
        if H._SECTION_RE.match(line) or H._BLOCK_RE.match(line):
            continue
        if H._PRODUCT_RE.match(line):
            continue
        unknown.append(mask(line))
    return sorted(set(unknown))


_MONEY_TOKEN = re.compile(r"\$?\d[\d,]*\.\d{2}-?")


def unread_figures(lines: list[str], blocks, H) -> dict:
    """Printed money this reader never looks at, by the line that carries it.

    The complement of `unknown_headings`, and the stronger of the two: a
    grammar gap MUST leave money on the floor, because a section the reader
    cannot see is a section whose figures it never reads. Counting the money
    tokens on lines that are neither the summary grid nor the body of a block
    therefore bounds the gap from above — a document with nothing unread
    outside its known furniture has no unread section to widen for.

    Reported as a count plus the masked SHAPE of each carrying line (digits to
    ``#``, money to ``<money>``), which names the furniture without printing a
    figure.
    """
    consumed: set[str] = set()
    for line in lines:
        if "Beginning Balance" in line and "Ending Balance" in line:
            consumed.add(line)
            break
    for _name, _sign, body in blocks:
        consumed.update(body)
    count = 0
    where: list[str] = []
    for line in lines:
        if line in consumed:
            continue
        hits = [token for token in _MONEY_TOKEN.findall(line) if H._figure(token) is not None]
        if hits:
            count += len(hits)
            where.append(mask(line)[:60])
    return {"count": count, "lines": sorted(set(where))}


def fee_refusal(blocks, start, end, H) -> dict:
    """Why `_service_charges` refused: the block, the arbiter, or the cut."""
    detail = [b for b in blocks if b[0] == "Service Charge Detail"]
    summary_block = [b for b in blocks if b[0] == "Service Charge Summary"]
    info = {"detail_blocks": len(detail), "summary_blocks": len(summary_block)}
    rows = []
    bad_row = False
    for _name, _sign, body in detail:
        for line in body:
            for day, figure, _tail in H._row_groups(line):
                posted = H._posting_date(day, start, end)
                amount = H._figure(figure)
                if posted is None or amount is None or amount < 0:
                    bad_row = True
                else:
                    rows.append(amount)
    info["detail_rows"] = len(rows)
    info["row_refused"] = bad_row
    stated = H._service_charge_summary(blocks)
    info["summary_block_ok"] = stated is not None
    if stated is None or bad_row:
        return info
    charges, waivers = stated
    cuts = [
        cut
        for cut in range(len(rows) + 1)
        if abs(round(sum(rows[:cut]), 2) - charges) <= H._EXACT
        and abs(round(sum(rows[cut:]), 2) - waivers) <= H._EXACT
    ]
    info["cuts"] = len(cuts)
    return info


def identities(summary, section_txns, fee_txns, service_net, balances, H) -> dict:
    """The four printed identities of `_validate`, reported one by one.

    Mirrors `_validate` check for check so a decline can be attributed to the
    identity that failed rather than to the block as a whole. Booleans only;
    ``None`` means the check was not reached.
    """
    from datetime import date as _date

    checks: dict[str, object] = {
        "cells_present": None, "summary_identity": None, "components": None,
        "section_sums": None, "fee_net": None, "balance_activity": None,
    }
    beginning = summary.get("Beginning Balance")
    ending = summary.get("Ending Balance")
    credits = summary.get("Credits (+)")
    debits = summary.get("Debits (-)")
    checks["cells_present"] = not (
        beginning is None or ending is None or credits is None or debits is None
    )
    if not checks["cells_present"]:
        return checks
    charges = summary.get("Total Service Charges (-)", 0.0)

    checks["summary_identity"] = abs(
        round(beginning + credits - debits - charges, 2) - ending) <= H._EXACT

    ok = True
    for total, parts in ((credits, H._CREDIT_PARTS), (debits, H._DEBIT_PARTS)):
        present = [summary[label] for label in parts if label in summary]
        if present and abs(round(sum(present), 2) - total) > H._EXACT:
            ok = False
    checks["components"] = ok

    section_credits = round(sum(t.amount for t in section_txns if t.amount > 0), 2)
    section_debits = round(-sum(t.amount for t in section_txns if t.amount < 0), 2)
    checks["section_sums"] = (
        abs(section_credits - credits) <= H._EXACT
        and abs(section_debits - debits) <= H._EXACT
    )
    checks["fee_net"] = abs(service_net - charges) <= H._EXACT

    if not balances:
        checks["balance_activity"] = False
        return checks
    running = beginning
    index = 0
    ordered = sorted(section_txns + fee_txns, key=lambda t: t.date)
    day_ok = True
    first_bad = None
    for position, (day, printed) in enumerate(balances):
        while index < len(ordered) and _date.fromisoformat(ordered[index].date) <= day:
            running = round(running + ordered[index].amount, 2)
            index += 1
        if abs(running - printed) > H._EXACT and day_ok:
            day_ok, first_bad = False, position
    while index < len(ordered):
        running = round(running + ordered[index].amount, 2)
        index += 1
    close_ok = abs(running - ending) <= H._EXACT
    checks["balance_activity"] = bool(day_ok and close_ok)
    checks["balance_first_bad_index"] = first_bad
    checks["balance_closes"] = close_ok
    return checks


# ----------------------------------------------------------------------- main

def load_population(args) -> list[str]:
    shas: list[str] = []
    if args.shas:
        for line in Path(args.shas).read_text(encoding="utf-8").splitlines():
            token = line.strip().upper()
            if token and not token.startswith("#"):
                shas.append(token)
    if args.group:
        groups = json.loads(args.clusters.read_text(encoding="utf-8"))["groups"]
        for name in args.group:
            shas.extend(groups.get(name, {}).get("shas16", []))
    return sorted(set(shas))


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=None)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--shas", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    if not args.group and not args.shas:
        args.group = ["DECL:huntington"]

    from tools.cohort_replay import ColdCache, load_baseline_rows

    population = load_population(args)
    rows = load_baseline_rows(args.run)
    by16 = {sha[:16]: sha for sha in rows}
    cache = ColdCache(args.data_dir)

    table = []
    for token in population:
        sha = by16.get(token, token if len(token) > 16 else None)
        entry = {"sha16": token}
        if sha is None or sha not in rows:
            entry.update(gate="absent-from-run", **{"class": "ABSENT"})
            table.append(entry)
            continue
        entry["outcome"] = rows[sha].get("outcome_class", "")
        entry["reason"] = rows[sha].get("outcome_reason", "")
        markdown, pages = cache.text(sha)
        if markdown is None:
            entry.update(gate="no-cached-text", **{"class": "ABSENT"})
            table.append(entry)
            continue
        entry["pages"] = len(pages)
        entry.update(trace(markdown))
        table.append(entry)

    lines = [f"# huntington decline probe — run `{args.run.name}`", ""]
    counts: dict[str, int] = {}
    for e in table:
        counts[e["class"]] = counts.get(e["class"], 0) + 1
    lines += ["| class | documents |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(counts.items())]
    lines += ["", "| sha16 | outcome | class | first refusing gate |", "|---|---|---|---|"]
    for e in table:
        lines.append(f"| {e['sha16']} | {e.get('outcome','')}/{e.get('reason','')} | "
                     f"{e['class']} | `{e['gate']}` |")
    lines.append("")
    for e in table:
        lines.append(f"## {e['sha16']} — {e['class']} — `{e['gate']}`")
        lines.append("")
        for key in ("pages", "claims", "period_ok", "summary_ok", "fee_block_printed",
                    "daily_block_printed", "transactions_ok", "service_charges_ok",
                    "daily_balances_ok", "n_section_txns", "n_fee_txns", "n_daily_balances"):
            if key in e:
                lines.append(f"- {key}: {e[key]}")
        if e.get("unread_figures"):
            unread = e["unread_figures"]
            lines.append(f"- unread printed figures: {unread['count']}")
            for shape in unread["lines"]:
                lines.append(f"  - `{shape}`")
        if e.get("summary_labels"):
            lines.append("- summary cells: " + ", ".join(f"`{c}`" for c in e["summary_labels"]))
        if e.get("blocks") is not None:
            lines.append("- blocks: " + (", ".join(
                f"`{b['name']}`({b['sign']:+d},{b['rows']}r)" for b in e["blocks"]) or "none"))
        if e.get("unknown_headings"):
            lines.append("- UNKNOWN headings: " + ", ".join(f"`{h}`" for h in e["unknown_headings"]))
        if e.get("fee_detail"):
            lines.append(f"- fee detail: {e['fee_detail']}")
        if e.get("identities"):
            lines.append("- identities: " + ", ".join(
                f"{k}={v}" for k, v in e["identities"].items()))
        lines.append("")
    report = "\n".join(lines) + "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(table, indent=1), encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
