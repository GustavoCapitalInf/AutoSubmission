"""commsec_decline_probe.py — WHICH gate declines each `community_section` document.

    python -m tools.commsec_decline_probe --run <run> --data-dir <cold cache> \
        [--group DECL:community_section] [--shas <file>] \
        [--out <private>.md] [--json <private>.json]

`analysis/community_section.py` is the archive's largest platform reader: it
claims a document on the core processor's own summary-grid furniture and then
returns ``None`` from ``parse`` on nine of them, which the runner records as
`failed / parser_declined` without saying WHICH link refused.

This walks the reader's own refusal chain in the reader's own order — and,
because this reader's last gate is `len(parsed) != 1`, it walks that chain ONCE
PER PRINTED ACCOUNT BLOCK, so "no account could be read" and "two accounts were
read and the single-account schema can hold one" are different answers rather
than the same `None`.

It keeps the two properties `tools/cpdecl_decline_probe.py` established:

* **the trace is CHECKED against the reader.** After tracing, the real
  ``parse_community_section_statement`` runs on the same text; a sha whose trace
  says "declines" while the reader publishes — or the reverse — is reported as
  ``TRACE-DISAGREES`` instead of being given a gate it did not hit. A mirrored
  chain that has drifted from its reader is worse than no chain;
* **the class of a document is a fact about a TREE.** Run at a tree where a
  member publishes, the same probe reports it ``PARSES``; the agreement check is
  what tells that apart from a defect in the mirror.

The text is the run of record's cached OCR/native artifact with
``parser_registry.admissible_text`` applied — the pipeline's own single parse
seam — so the mirror reads exactly what the reader reads in production.

READ-ONLY, and it never prints a document value: no amount, no date, no
description, no account number, no issuer domain, no customer token. Every digit
in any label it echoes is masked to ``#`` and money is masked whole. What it
prints is gate NAMES, block NAMES, booleans and counts.

Classification:

  ``L1``        two or more of the document's printed accounts publish a
                statement, and the schema holds one (MASTER_PLAN L-1). An
                honest refusal, out of this card's scope — named and left
                declined until the independent-account architecture lands.
  ``GRAMMAR``   a gate BEFORE the printed identities refused on every account
                block: a summary grid that did not read end to end, no ledger
                section this reader knows, a row whose date or amount is not
                readable, a grid that contradicts itself.
  ``IDENTITY``  every gate parsed and the printed identities do not close — the
                document's own arithmetic against its own ledger.
  ``ISSUER``    the masthead names two or more labelled domains, so the document
                contradicts itself about its issuer (or the masthead scope ran
                past the first account). Fail-closed by the reader's docstring.
  ``DETECT``    the reader does not claim this text at all.
  ``PARSES``    the trace found no refusal (a control, or a drifted mirror —
                the agreement check decides which).
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
DEFAULT_CENSUS = Path("docs/moneythumb-replacement/census_batch9/per_sha.csv")

#: Anything that could carry a document value is masked before it is printed.
_MONEY = re.compile(r"\$?-?\d[\d,]*\.\d{2}-?")
_DIGIT = re.compile(r"\d")


def mask(text: str) -> str:
    return _DIGIT.sub("#", _MONEY.sub("<money>", text))


def _money_tokens(text: str) -> int:
    """How many money-shaped tokens a span carries. A COUNT, never a value."""
    return len(_MONEY.findall(text))


# ---------------------------------------------------------------------------
# one printed account block, through `_parse_sectioned_statement`'s own chain
# ---------------------------------------------------------------------------

def trace_block(block: str) -> dict:
    """The first link of `_parse_sectioned_statement` that refused this block.

    Mirrors the function statement by statement. Where the reader computes a
    value this reports whether it was READABLE and never what it was.
    """
    from analysis import community_section as M

    out: dict = {}
    cleaned = M._clean(block)
    region = M._summary_region(cleaned)
    out["summary_region"] = region is not None
    if region is None:
        # Unreachable through `_account_blocks` (the block is cut ON the grid
        # header), so it is only ever a caller passing a different block.
        return {**out, "gate": "_summary:no_grid_header", "class": "GRAMMAR"}

    balances = M._balance_rows(region)
    out["dated_balance_rows"] = len(balances)
    counts = {"credit": False, "debit": False}
    for match in M._COUNT_ROW_RE.finditer(region):
        counts["credit" if match.group(1) is not None else "debit"] = True
    out["count_rows"] = dict(counts)
    #: The same rows sought ANYWHERE in the block rather than inside the summary
    #: region: "the bank did not print this row" and "the reader did not read
    #: the row the bank printed" are different findings, and only the first is a
    #: fact about the document.
    out["labels_in_block"] = {
        "credit_count_row": bool(re.search(r"Credit\(s\) This Period", cleaned, re.I)),
        "debit_count_row": bool(re.search(r"Debit\(s\) This Period", cleaned, re.I)),
        "balance_word": bool(re.search(r"\bBalance\b", cleaned, re.I)),
    }
    out["summary_region_money_tokens"] = _money_tokens(region)

    missing = ([f"balance_rows({len(balances)})"] if len(balances) < 2 else []) + [
        f"{name}_count_row" for name, ok in counts.items() if not ok]
    if missing:
        return {**out, "gate": "_summary:" + ",".join(missing), "class": "GRAMMAR"}

    summary = M._summary(block)
    if summary is None:
        return {**out, "gate": "_summary:unexplained", "class": "GRAMMAR"}

    try:
        start_year = M._strptime(summary.start_date, "probe").year
        end_year = M._strptime(summary.end_date, "probe").year
    except ValueError:
        return {**out, "gate": "_summary:period_not_a_date", "class": "GRAMMAR"}
    out["period_one_year"] = start_year == end_year
    if start_year != end_year:
        return {**out, "gate": "period_spans_two_years", "class": "GRAMMAR"}

    sections = M._sections(block)
    out["sections"] = {mask(name): sum(1 for n, _s, _b in sections if n == name)
                       for name, _s, _b in sections}
    by_section = [M._dated_amount_rows(body, sign=sign, year=end_year)
                  for _name, sign, body in sections]
    section_rows = [txn for rows in by_section for txn in rows]
    out["n_section_rows"] = len(section_rows)
    out["activity_header"] = bool(M._ACTIVITY_HEADER_RE.search(M._clean(block)))

    if section_rows:
        out["layout"] = "sectioned"
        if M._section_oracle_disagrees(block, by_section):
            return {**out, "gate": "_section_oracle_disagrees", "class": "IDENTITY"}
        check_rows = M._check_rows(block, year=end_year)
        out["n_check_rows"] = len(check_rows)
        txns = section_rows + check_rows
    else:
        out["layout"] = "activity(J-B)"
        txns = M._activity_rows(block, year=end_year)
        out["n_activity_rows"] = len(txns)
    if not txns:
        return {**out, "gate": "no_rows", "class": "GRAMMAR"}

    try:
        grid = M._daily_balances(block)
    except ValueError:
        return {**out, "gate": "_daily_balances:day_printed_twice", "class": "GRAMMAR"}
    out["n_grid_days"] = len(grid)

    credit_total = round(sum(t.amount for t in txns if t.amount > 0), 2)
    debit_total = round(sum(abs(t.amount) for t in txns if t.amount < 0), 2)
    credit_rows = sum(1 for t in txns if t.direction == "credit")
    debit_rows = sum(1 for t in txns if t.direction == "debit")
    stated_credits = M._money(summary.credits) or 0.0
    stated_debits = M._money(summary.debits) or 0.0
    checks = {
        "credit_total": abs(credit_total - stated_credits) <= 0.02,
        "debit_total": abs(debit_total - stated_debits) <= 0.02,
        "credit_count": credit_rows == int(summary.credit_count),
        "debit_count": debit_rows == int(summary.debit_count),
    }
    out["identities"] = checks
    out["count_delta"] = {"credit": credit_rows - int(summary.credit_count),
                          "debit": debit_rows - int(summary.debit_count)}
    #: The summary's OWN arithmetic, which no gate of this reader checks: it is
    #: reported because a block whose printed grid does not close is a document
    #: fact and a block whose ledger misses a closing grid is a reader fact.
    beginning = M._balance(summary.beginning)
    ending = M._balance(summary.ending)
    out["summary_closes"] = (
        None if beginning is None or ending is None
        else abs(round(beginning + stated_credits - stated_debits - ending, 2)) <= 0.02)
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return {**out, "gate": "_matches_the_printed_summary:" + ",".join(failed),
                "class": "IDENTITY"}
    return {**out, "gate": "none (publishes)", "class": "PARSES"}


# ---------------------------------------------------------------------------
# the document
# ---------------------------------------------------------------------------

def trace_community_section(markdown: str) -> dict:
    from analysis import community_section as M

    out: dict = {"reader": "community_section"}
    out["claims"] = bool(M.detect_platform(markdown).claims)
    if not out["claims"]:
        return {**out, "gate": "detect", "class": "DETECT"}

    domains = M._masthead_domains(markdown)
    out["masthead_labelled_domains"] = len(domains)
    if len(domains) > 1:
        return {**out, "gate": "_masthead_domains:more_than_one", "class": "ISSUER"}

    blocks = M._account_blocks(markdown)
    out["n_account_blocks"] = len(blocks)
    #: The heading shape sought without its grid anchor: a document printing
    #: headings that no grid follows is a different finding from one printing
    #: no headings at all.
    out["heading_shape_hits"] = len(re.findall(
        r"(?:[A-Za-z][A-Za-z&'.-]*)(?: (?:[A-Za-z][A-Za-z&'.-]*|\d{1,3})){0,7}?\s*-\s*[X\d]{4,}",
        M._clean(markdown)))
    out["grid_headers"] = len(re.findall(
        r"Account Summary Date Description Amount", M._clean(markdown), re.I))
    if not blocks:
        return {**out, "gate": "_account_blocks:none", "class": "GRAMMAR"}

    traces = []
    for product, _number, block in blocks:
        traced = trace_block(block)
        traced["product"] = mask(product)
        traces.append(traced)
    out["blocks"] = traces
    publishing = [t for t in traces if t["class"] == "PARSES"]
    out["n_blocks_publishing"] = len(publishing)

    if len(publishing) > 1:
        return {**out, "gate": "len(parsed)!=1:two_or_more_accounts_publish",
                "class": "L1"}
    if len(publishing) == 1:
        return {**out, "gate": "none (publishes)", "class": "PARSES"}

    # No account block published. The document's class is the class of the
    # block that got FURTHEST — an identity that does not close is the
    # document's arithmetic, and it is not made a grammar gap by a sibling
    # block that stopped earlier.
    order = {"GRAMMAR": 0, "ISSUER": 1, "IDENTITY": 2, "PARSES": 3}
    best = max(traces, key=lambda t: order.get(t["class"], 0))
    return {**out, "gate": "len(parsed)!=1:no_account_publishes -> " + best["gate"],
            "class": best["class"]}


def publishes(markdown: str) -> bool | str:
    """Does the real reader publish this document? The trace's control."""
    from analysis.community_section import parse_community_section_statement
    try:
        return parse_community_section_statement(markdown) is not None
    except Exception as exc:  # a raise is not a decline; say so
        return f"raises:{type(exc).__name__}"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def load_population(args) -> list[str]:
    found: set[str] = set()
    for name in args.group:
        groups = json.loads(args.clusters.read_text(encoding="utf-8"))["groups"]
        found.update(groups.get(name, {}).get("shas16", []))
    if args.shas:
        for raw in Path(args.shas).read_text(encoding="utf-8").splitlines():
            token = raw.strip()
            if token and not token.startswith("#"):
                found.add(token.split()[0].upper()[:16])
    if args.parser:
        from tools.cohort_replay import load_baseline_rows
        for sha, row in load_baseline_rows(args.run).items():
            if (row.get("parser_id") or "") in args.parser:
                found.add(sha[:16])
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=None)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    ap.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--parser", action="append", default=[],
                    help="baseline parser_id (the control cohort)")
    ap.add_argument("--shas", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    if not args.group and not args.shas and not args.parser:
        args.group = ["DECL:community_section"]

    import csv
    from analysis.parser_registry import admissible_text
    from tools.cohort_replay import ColdCache, load_baseline_rows

    population = load_population(args)
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
        entry: dict = {"sha16": sha16, "route": route.get(sha16, "")}
        sha = by16.get(sha16)
        if sha is None:
            table.append({**entry, "gate": "absent-from-run", "class": "ABSENT"})
            continue
        entry["outcome"] = rows[sha].get("outcome_class", "")
        entry["reason"] = rows[sha].get("outcome_reason", "")
        entry["folder"] = rows[sha].get("folder_label", "")
        entry["baseline_parser"] = rows[sha].get("parser_id", "")
        markdown, pages = cache.text(sha)
        if markdown is None:
            table.append({**entry, "gate": "no-cached-text", "class": "ABSENT"})
            continue
        markdown = admissible_text(markdown)
        entry["pages"] = len(pages)
        traced = trace_community_section(markdown)
        entry.update(traced)
        published = publishes(markdown)
        entry["reader_publishes"] = published
        says_declines = traced["class"] != "PARSES"
        if published is not (not says_declines):
            entry["class"] = "TRACE-DISAGREES"
            entry["gate"] = f"{traced['gate']} vs reader publishes={published}"
        table.append(entry)

    counts: dict[str, int] = {}
    for e in table:
        counts[e["class"]] = counts.get(e["class"], 0) + 1

    lines = [f"# DECL-COMMUNITY-SECTION decline probe — run `{args.run.name}`", "",
             "| class | documents |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(counts.items())]
    lines += ["", "| sha16 | route | folder | outcome | blocks | publishing | class | first refusing gate |",
              "|---|---|---|---|---:|---:|---|---|"]
    for e in table:
        lines.append(
            f"| {e['sha16']} | {e.get('route','')} | {e.get('folder','')} | "
            f"{e.get('outcome','')}/{e.get('reason','')} | "
            f"{e.get('n_account_blocks','')} | {e.get('n_blocks_publishing','')} | "
            f"{e['class']} | `{e['gate']}` |")
    lines.append("")
    for e in table:
        lines.append(f"## {e['sha16']} — {e['class']} — `{e['gate']}`")
        lines.append("")
        for key, value in e.items():
            if key in ("sha16", "class", "gate", "outcome", "reason", "folder", "blocks"):
                continue
            lines.append(f"- {key}: {value}")
        for index, block in enumerate(e.get("blocks", [])):
            lines.append(f"- block {index} — `{block['gate']}` ({block['class']})")
            for key, value in block.items():
                if key in ("gate", "class"):
                    continue
                lines.append(f"    - {key}: {value}")
        lines.append("")
    report = "\n".join(lines) + "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(table, indent=1, default=str), encoding="utf-8")
    print(report if not args.out else "\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
