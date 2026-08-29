"""cpdecl_identity_ceiling.py — what the declines could reach if the grammar read them.

    python -m tools.cpdecl_identity_ceiling --mode sectioned_strip [--run <run>] [--data-dir <cold>]
    python -m tools.cpdecl_identity_ceiling --mode enclosures_cells
    python -m tools.cpdecl_identity_ceiling --mode daily_cells

The huntington ceiling's question, one complex over: **would the platform
accept these documents if the reader's grammar read them?** A decline probe
names the gate; a ceiling says whether widening that gate could ever pay, so a
cell can stop before writing a grammar for a document whose figures are not on
the page at all.

Nothing here is a reader and nothing here is wired: each mode measures a
BOUND over the run of record's own cached text, prints counts, booleans and
gate names, and never prints a document value.

`sectioned_strip`
    `core_processor_sectioned`'s summary strip is read by ADJACENCY — a label,
    then the figure printed after it. On some documents the text layer emits
    the strip's labels and its figures in separate runs, so a cell that is
    printed is not read. The bound asks the only question that decides whether
    a cross-run pairing could ever help: **is the figure the printed identities
    REQUIRE actually printed, unclaimed, in the strip's own region?**

    It is a verification rather than a search. The ledger sections are read
    independently of the strip, so the row count and row total in each
    direction are known, and the summary's identity then fixes the closing
    balance. Each required value is looked for among the region's money tokens
    that the adjacency grammar did not already claim. A document whose required
    value is NOT printed there cannot be reached by any pairing rule; one whose
    values ARE all printed is reachable, and the report says how many distinct
    unclaimed tokens carry each value so ambiguity is visible rather than
    assumed.

`enclosures_cells` / `daily_cells`
    Both readers refuse a whole document when `tables.dated_cells` finds a date
    that closes no cell. The bound counts those dates, and then asks whether
    the ledger would close at all if every one of them were skipped: a document
    whose counts and totals still miss after the most generous possible skip is
    a document no tolerance reaches, and the refusal is the answer.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_CLUSTERS = Path("docs/moneythumb-replacement/census_batch9/clusters.json")
DEFAULT_CENSUS = Path("docs/moneythumb-replacement/census_batch9/per_sha.csv")

_TOLERANCE = 0.005


# ---------------------------------------------------------------------------
# sectioned_strip
# ---------------------------------------------------------------------------

def sectioned_strip(markdown: str) -> dict:
    """Are the strip figures the identities require printed in the region?"""
    from analysis import core_processor_sectioned as M

    out: dict = {"mode": "sectioned_strip"}
    region = M._summary_region(markdown)
    if region is None:
        return {**out, "verdict": "no_region"}

    period = M._once(region, M._PERIOD_RE)
    if period is None:
        return {**out, "verdict": "no_period"}
    printed_period = M._period_dates(period.group(1), period.group(2))
    if printed_period is None:
        return {**out, "verdict": "period_not_a_date"}
    start, end = (date.fromisoformat(printed_period[0]),
                  date.fromisoformat(printed_period[1]))
    if end < start:
        return {**out, "verdict": "period_order"}

    opening_match = M._once(region, M._OPENING_RE)
    if opening_match is None:
        return {**out, "verdict": "no_opening_balance"}
    opening = M._figure(opening_match.group(2))
    if opening is None:
        return {**out, "verdict": "opening_not_money"}

    # Every money token the region prints, and the ones the adjacency grammar
    # already claimed. A claimed token is not a candidate for another cell.
    tokens = [(m.start(1), m.group(1), M._figure(m.group(1)))
              for m in re.finditer(M._FIGURE_TOKEN, region)]
    claimed: set[int] = {opening_match.start(2)}
    read: dict[str, float] = {}
    closing_match = M._once(region, M._CLOSING_RE)
    if closing_match is not None:
        claimed.add(closing_match.start(2))
        value = M._figure(closing_match.group(2))
        if value is not None:
            read["closing"] = value
    for name, pattern in (("credits", M._CREDITS_RE), ("debits", M._DEBITS_RE)):
        found = M._once(region, pattern)
        if found is not None:
            claimed.add(found.start(2))
            value = M._figure(found.group(2))
            if value is not None:
                read[name] = value
                counted = M._counts(region, pattern)
                if counted is not None:
                    read[name + "_count"] = float(counted[0])
    out["region_money_tokens"] = len(tokens)
    out["claimed_by_adjacency"] = len(claimed)
    out["missing_cells"] = sorted(
        {"closing", "credits", "debits"} - set(read))

    # The ledger, read independently of the strip.
    sections = M._sections(markdown)
    if not sections.keys() & {n for n, _c, _d in M._LEDGER_SECTIONS}:
        return {**out, "verdict": "no_ledger_section"}
    rows = []
    for name, credit, default in M._LEDGER_SECTIONS:
        block = sections.get(name)
        if block is None:
            continue
        found = M._rows(block, credit=credit, start=start, end=end, default=default)
        if found is None:
            return {**out, "verdict": f"ledger_unreadable:{name}"}
        rows.extend(found)
    credit_rows = [r for r in rows if r.direction == "credit"]
    debit_rows = [r for r in rows if r.direction == "debit"]
    required = {
        "credits": round(sum(r.amount for r in credit_rows), 2),
        "debits": round(-sum(r.amount for r in debit_rows), 2),
        "closing": round(opening + sum(r.amount for r in rows), 2),
    }
    required_counts = {"credits_count": len(credit_rows),
                       "debits_count": len(debit_rows)}
    out["n_rows"] = {"credit": len(credit_rows), "debit": len(debit_rows)}

    # For each cell the adjacency grammar read, does it AGREE with the ledger?
    # For each cell it did not, is the required figure printed and unclaimed?
    findings: dict[str, str] = {}
    for cell, value in required.items():
        if cell in read:
            findings[cell] = ("adjacency_agrees"
                              if abs(read[cell] - value) <= _TOLERANCE
                              else "adjacency_disagrees")
            continue
        carriers = [pos for pos, _token, amount in tokens
                    if pos not in claimed and amount is not None
                    and abs(amount - value) <= _TOLERANCE]
        findings[cell] = (f"printed_unclaimed×{len(carriers)}" if carriers
                          else "NOT_PRINTED_in_region")
    for cell, count in required_counts.items():
        if cell in read:
            findings[cell] = ("adjacency_agrees" if int(read[cell]) == count
                              else "adjacency_disagrees")
        else:
            printed = len(re.findall(r"(?<![0-9])" + str(count) + r"(?![0-9])", region))
            findings[cell] = (f"printed×{printed}" if printed else "NOT_PRINTED_in_region")
    out["cells"] = findings

    # The grid, which is an independent printing and is checked as it stands.
    if "DAILY BALANCE" in sections:
        grid = M._daily_balances(sections["DAILY BALANCE"], start=start, end=end)
        if grid is None:
            out["grid"] = "unreadable"
        else:
            out["grid"] = ("agrees"
                           if M._matches_the_printed_grid(rows, grid, opening)
                           else "disagrees")
    else:
        out["grid"] = "not_printed"

    reachable = (all(not value.startswith("NOT_PRINTED")
                     and value != "adjacency_disagrees"
                     for value in findings.values())
                 and out["grid"] in ("agrees", "not_printed"))
    out["verdict"] = "REACHABLE" if reachable else "unreachable"
    return out


# ---------------------------------------------------------------------------
# enclosures_cells / daily_cells
# ---------------------------------------------------------------------------

def _cells_or_refusal(run, date_pattern, value_pattern) -> tuple[int, int]:
    """`(dates, dates that close no cell)` for one run."""
    dates = list(date_pattern.finditer(run))
    unclosed = 0
    for index, found in enumerate(dates):
        stop = dates[index + 1].start() if index + 1 < len(dates) else len(run)
        if value_pattern.search(run[found.end():stop]) is None:
            unclosed += 1
    return len(dates), unclosed


def enclosures_cells(markdown: str) -> dict:
    from analysis import core_processor_enclosures as M

    out: dict = {"mode": "enclosures_cells"}
    summary = M._summary(markdown)
    if summary is None:
        return {**out, "verdict": "no_summary"}
    blocks = M._blocks(markdown)
    running = bool(M._RUNNING_BALANCE_RE.search(markdown))
    totals = {"credit": 0.0, "debit": 0.0}
    counts = {"credit": 0, "debit": 0}
    per_role: dict[str, dict] = {}
    for role, (direction, _serialled, restated, _default) in M._ROLE_READING.items():
        if running and restated:
            continue
        for name, runs in blocks.get(role, []):
            dates = unclosed = 0
            for run in runs:
                cleaned = M._without_cross_references(run)
                found, missed = _cells_or_refusal(
                    cleaned, M._DATE_RE, M._LEDGER_FIGURE_RE)
                dates += found
                unclosed += missed
                # The most generous possible skip: every date that closes no
                # cell is dropped and every date that does close one is booked.
                opened = list(M._DATE_RE.finditer(cleaned))
                for index, cell in enumerate(opened):
                    stop = (opened[index + 1].start() if index + 1 < len(opened)
                            else len(cleaned))
                    value = M._LEDGER_FIGURE_RE.search(cleaned[cell.end():stop])
                    if value is None:
                        continue
                    amount = M._ledger_amount(value.group(1))
                    if amount is None:
                        continue
                    credit = (amount > 0) if direction is None else direction == "credit"
                    side = "credit" if credit else "debit"
                    totals[side] = round(totals[side] + abs(amount), 2)
                    counts[side] += 1
            entry = per_role.setdefault(role, {"dates": 0, "unclosed": 0})
            entry["dates"] += dates
            entry["unclosed"] += unclosed
    out["per_role"] = per_role
    out["unclosed_dates"] = sum(e["unclosed"] for e in per_role.values())
    out["counts_after_the_most_generous_skip"] = counts
    out["printed_counts"] = {"credit": summary.credit_count,
                             "debit": summary.debit_count}
    out["count_delta_after_skip"] = {
        "credit": counts["credit"] - summary.credit_count,
        "debit": counts["debit"] - summary.debit_count}
    out["totals_close_after_skip"] = {
        "credit": abs(totals["credit"] - summary.credits) <= _TOLERANCE
        or (summary.interest > 0
            and abs(totals["credit"] - summary.credits - summary.interest) <= _TOLERANCE),
        "debit": abs(totals["debit"] - summary.debits) <= _TOLERANCE
        or (summary.service_charge > 0
            and abs(totals["debit"] - summary.debits - summary.service_charge) <= _TOLERANCE)}
    out["verdict"] = ("REACHABLE_BY_SKIP"
                      if all(out["totals_close_after_skip"].values())
                      else "unreachable_by_skip")
    return out


def daily_cells(markdown: str) -> dict:
    from analysis import core_processor_daily as M

    out: dict = {"mode": "daily_cells"}
    summary = M._summary(markdown)
    if summary is None:
        return {**out, "verdict": "no_summary"}
    sections = M._sections(markdown)
    per_section: dict[str, dict] = {}
    for name, _credit, _default in M._LEDGER_SECTIONS:
        dates = unclosed = 0
        for run in sections.get(name, []):
            found, missed = _cells_or_refusal(run, M._DATE_RE, M._FIGURE_RE)
            dates += found
            unclosed += missed
        per_section[name] = {"dates": dates, "unclosed": unclosed}
    out["per_section"] = per_section
    out["unclosed_dates"] = sum(e["unclosed"] for e in per_section.values())
    out["grid_section_printed"] = "DAILY BALANCES" in sections
    return out


MODES = {"sectioned_strip": sectioned_strip,
         "enclosures_cells": enclosures_cells,
         "daily_cells": daily_cells}
MODE_GROUP = {"sectioned_strip": "DECL:core_processor_sectioned",
              "enclosures_cells": "DECL:core_processor_enclosures",
              "daily_cells": "DECL:core_processor_daily"}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=sorted(MODES), required=True)
    ap.add_argument("--run", type=Path, default=None)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    ap.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--shas", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    if not args.group and not args.shas:
        args.group = [MODE_GROUP[args.mode]]

    import csv
    from tools.cohort_replay import ColdCache, load_baseline_rows

    population: list[str] = []
    if args.group:
        groups = json.loads(args.clusters.read_text(encoding="utf-8"))["groups"]
        for name in args.group:
            population.extend(groups.get(name, {}).get("shas16", []))
    if args.shas:
        population.extend(
            line.strip().upper() for line in
            Path(args.shas).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#"))
    population = sorted(set(population))

    rows = load_baseline_rows(args.run)
    by16 = {sha[:16]: sha for sha in rows}
    route: dict[str, str] = {}
    if args.census.is_file():
        with args.census.open(encoding="utf-8", newline="") as handle:
            for record in csv.DictReader(handle):
                route[record["sha16"]] = record.get("text_route", "")
    cache = ColdCache(args.data_dir)

    table = []
    for sha16 in population:
        sha = by16.get(sha16)
        entry: dict = {"sha16": sha16, "route": route.get(sha16, "")}
        if sha is None:
            table.append({**entry, "verdict": "absent-from-run"})
            continue
        markdown, _pages = cache.text(sha)
        if markdown is None:
            table.append({**entry, "verdict": "no-cached-text"})
            continue
        entry.update(MODES[args.mode](markdown))
        table.append(entry)

    verdicts: dict[str, int] = {}
    for entry in table:
        verdicts[entry.get("verdict", "-")] = verdicts.get(entry.get("verdict", "-"), 0) + 1
    print(f"# cpdecl identity ceiling — mode {args.mode} — run `{args.run.name}`")
    print()
    for name, count in sorted(verdicts.items()):
        print(f"  {name}: {count}")
    print()
    for entry in table:
        print(f"## {entry['sha16']} [{entry['route']}] -> {entry.get('verdict')}")
        for key, value in entry.items():
            if key in ("sha16", "route", "verdict", "mode"):
                continue
            print(f"   - {key}: {value}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(table, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
