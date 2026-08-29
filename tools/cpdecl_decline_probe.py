"""cpdecl_decline_probe.py — WHICH gate declines each core-processor template document.

    python -m tools.cpdecl_decline_probe --run <run> --data-dir <cold cache> \
        [--group DECL:core_processor_sectioned ...] [--shas <file>] \
        [--out <private>.md] [--json <private>.json]

Four template readers claim a document on an EXCLUSIVE marker pair and then
return ``None`` from ``parse``; the runner records `failed / parser_declined`
and nothing says WHICH link of the chain refused. This instrument walks each
reader's own refusal chain, in the reader's own order, over the run of record's
cached text, and names the first link that refused.

It is the `tools/huntington_decline_probe.py` shape with one addition that
matters: **the trace is CHECKED against the reader itself.** After tracing, the
real `parse_*` function is called on the same text; if the trace says "declines"
and the parser publishes (or the reverse), the sha is reported as
``TRACE-DISAGREES`` rather than being given a gate it did not hit. A mirrored
chain that has drifted from its reader is worse than no chain at all, and this
is the only way to know.

READ-ONLY, and it never prints a document value: no amount, no date, no
description, no account number, no customer token. Every digit in any label it
echoes is masked to ``#`` and money is masked whole. What it prints is gate
NAMES, block NAMES, booleans and counts — the vocabulary a grammar decision is
made in.

Classification:

  ``L1``        the document carries a second account (the relationship block
                lists more than one) — an honest L-1 decline, out of scope.
  ``GRAMMAR``   a gate BEFORE the printed identities refused: a summary strip
                that did not read end to end, a ledger block this reader does
                not know, a row whose date or amount is not readable, a grid
                that did not parse. On a native document this is a candidate
                widening; on a Tesseract document it is a candidate OCR damage,
                and the two are reported separately because they are different
                findings with different remedies.
  ``IDENTITY``  every gate parsed and one of the printed identities does not
                close — the document's own arithmetic against its own ledger.
  ``PARSES``    the trace found no refusal (a control, or a bug in the probe —
                the agreement check decides which).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_CLUSTERS = Path("docs/moneythumb-replacement/census_batch9/clusters.json")
DEFAULT_CENSUS = Path("docs/moneythumb-replacement/census_batch9/per_sha.csv")

#: Anything that could carry a document value is masked before it is printed.
_MONEY = re.compile(r"\$?\d[\d,]*\.\d{2}-?")
_DIGIT = re.compile(r"\d")


def mask(text: str) -> str:
    return _DIGIT.sub("#", _MONEY.sub("<money>", text))


def _money_tokens(text: str) -> int:
    """How many money-shaped tokens a span carries. A COUNT, never a value."""
    return len(_MONEY.findall(text))


# ---------------------------------------------------------------------------
# core_processor_sectioned
# ---------------------------------------------------------------------------

def trace_sectioned(markdown: str) -> dict:
    from analysis import core_processor_sectioned as M

    out: dict = {"reader": "core_processor_sectioned"}
    out["claims"] = bool(M.detect(markdown).claims)
    if not out["claims"]:
        return {**out, "gate": "detect", "class": "DETECT"}

    heading = M._ACCOUNT_HEADING_RE.search(markdown)
    out["account_heading"] = heading is not None
    region = M._summary_region(markdown)
    if region is None:
        return {**out, "gate": "_summary_region:no_account_heading", "class": "GRAMMAR"}

    # The strip, component by component: which printed cell did not read.
    period = M._once(region, M._PERIOD_RE)
    opening = M._once(region, M._OPENING_RE)
    closing = M._once(region, M._CLOSING_RE)
    credits_ = M._counts(region, M._CREDITS_RE)
    debits = M._counts(region, M._DEBITS_RE)
    strip = {
        "period_line": period is not None,
        "opening_row": opening is not None,
        "closing_row": closing is not None,
        "credit_row": credits_ is not None,
        "debit_row": debits is not None,
    }
    out["strip"] = strip
    #: The same labels, sought ANYWHERE in the document rather than in the
    #: strip: "the bank did not print this row" and "the reader did not read
    #: the row the bank printed" are different findings, and only the first is
    #: a document fact.
    upper = markdown.upper()
    out["labels_printed"] = {
        "period_phrase": "TOTAL DAYS IN STATEMENT PERIOD" in upper,
        "opening_label": M._OPENING_LABEL in upper,
        "closing_label": M._CLOSING_LABEL in upper,
        "credits_label": "CREDITS" in upper,
        "debits_label": "DEBITS" in upper,
    }
    missing = [name for name, ok in strip.items() if not ok]
    if missing:
        return {**out, "gate": "_summary:" + ",".join(missing), "class": "GRAMMAR"}
    if M._period_dates(period.group(1), period.group(2)) is None:
        return {**out, "gate": "_summary:period_not_a_date", "class": "GRAMMAR"}
    if M._figure(opening.group(2)) is None or M._figure(closing.group(2)) is None:
        return {**out, "gate": "_summary:balance_not_money", "class": "GRAMMAR"}

    summary = M._summary(markdown)
    if summary is None:
        return {**out, "gate": "_summary:unexplained", "class": "GRAMMAR"}
    if heading is None:
        return {**out, "gate": "account_heading", "class": "GRAMMAR"}

    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    if end < start:
        return {**out, "gate": "period_order", "class": "GRAMMAR"}

    sections = M._sections(markdown)
    out["sections"] = {name: len(runs) for name, runs in sorted(sections.items())}
    ledger_names = {name for name, _c, _d in M._LEDGER_SECTIONS}
    if not sections.keys() & ledger_names:
        return {**out, "gate": "no_ledger_section", "class": "GRAMMAR"}

    rows = []
    for name, credit, default in M._LEDGER_SECTIONS:
        block = sections.get(name)
        if block is None:
            continue
        found = M._rows(block, credit=credit, start=start, end=end, default=default)
        if found is None:
            return {**out, "gate": f"_rows:{name}", "class": "GRAMMAR"}
        rows.extend(found)
    out["n_rows"] = len(rows)

    # The printed identities, one by one.
    credits_rows = [r for r in rows if r.direction == "credit"]
    debit_rows = [r for r in rows if r.direction == "debit"]
    checks = {
        "credit_count": len(credits_rows) == summary.credit_count,
        "debit_count": len(debit_rows) == summary.debit_count,
        "credit_total": abs(sum(r.amount for r in credits_rows) - summary.credits) <= 0.005,
        "debit_total": abs(-sum(r.amount for r in debit_rows) - summary.debits) <= 0.005,
        "summary_identity": abs(summary.opening + summary.credits - summary.debits
                                - summary.closing) <= 0.005,
        "walk": abs(summary.opening + sum(r.amount for r in rows)
                    - summary.closing) <= 0.005,
    }
    out["identities"] = checks
    out["count_delta"] = {"credit": len(credits_rows) - summary.credit_count,
                          "debit": len(debit_rows) - summary.debit_count}
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return {**out, "gate": "_matches_the_printed_summary:" + ",".join(failed),
                "class": "IDENTITY"}

    if "DAILY BALANCE" in sections:
        grid = M._daily_balances(sections["DAILY BALANCE"], start=start, end=end)
        if grid is None:
            return {**out, "gate": "_daily_balances", "class": "GRAMMAR"}
        out["n_grid_days"] = len(grid)
        if not M._matches_the_printed_grid(rows, grid, summary.opening):
            walked = {}
            running = summary.opening
            for row in sorted(rows, key=lambda item: item.date):
                running = round(running + row.amount, 2)
                walked[row.date] = running
            printed_days = {entry.date for entry in grid}
            out["grid"] = {"days_only_in_grid": len(printed_days - set(walked)),
                           "days_only_in_ledger": len(set(walked) - printed_days)}
            return {**out, "gate": "_matches_the_printed_grid", "class": "IDENTITY"}

    return {**out, "gate": "none (parses)", "class": "PARSES"}


# ---------------------------------------------------------------------------
# core_processor_enclosures
# ---------------------------------------------------------------------------

def trace_enclosures(markdown: str) -> dict:
    from analysis import core_processor_enclosures as M
    from analysis.date_tokens import iso_within_period
    from analysis.tables import unique_match

    out: dict = {"reader": "core_processor_enclosures"}
    out["claims"] = bool(M.detect(markdown).claims)
    if not out["claims"]:
        return {**out, "gate": "detect", "class": "DETECT"}

    period_line = unique_match(markdown, M._STRIP_PERIOD_RE)
    if period_line is None:
        return {**out, "gate": "_strip:period_not_unique", "class": "GRAMMAR"}
    opens = markdown.rfind("\n", 0, period_line.start()) + 1
    closes = markdown.find("\n", period_line.end())
    line = markdown[opens: closes if closes >= 0 else len(markdown)]
    closing_on_line = unique_match(line, M._CLOSING_RE)
    out["strip_line_money_tokens"] = _money_tokens(line)
    if closing_on_line is None:
        out["closing_label_in_document"] = bool(M._CLOSING_RE.search(markdown))
        out["closing_label_hits_on_line"] = len(M._CLOSING_RE.findall(line))
        return {**out, "gate": "_strip:no_closing_balance_on_the_line", "class": "GRAMMAR"}
    strip = line[: closing_on_line.end()]

    cells = {
        "period": unique_match(strip, M._STRIP_PERIOD_RE),
        "account": unique_match(strip, M._ACCOUNT_RE),
        "previous": unique_match(strip, M._PREVIOUS_RE),
        "days": unique_match(strip, M._DAYS_RE),
        "credits": unique_match(strip, M._CREDITS_RE),
        "debits": unique_match(strip, M._DEBITS_RE),
        "service": unique_match(strip, M._SERVICE_RE),
        "interest": unique_match(strip, M._INTEREST_RE),
        "closing": unique_match(strip, M._CLOSING_RE),
    }
    out["strip"] = {name: value is not None for name, value in cells.items()}
    #: Was the cell printed ANYWHERE (the document's fact) as against read in
    #: the strip (the reader's)? A label present in the document and absent
    #: from the strip is a REGION problem; a label absent from both is a
    #: document that does not print that row.
    out["labels_in_document"] = {
        "account": bool(M._ACCOUNT_RE.search(markdown)),
        "previous": bool(M._PREVIOUS_RE.search(markdown)),
        "days": bool(M._DAYS_RE.search(markdown)),
        "credits": bool(M._CREDITS_RE.search(markdown)),
        "debits": bool(M._DEBITS_RE.search(markdown)),
        "service": bool(M._SERVICE_RE.search(markdown)),
        "interest": bool(M._INTEREST_RE.search(markdown)),
    }
    missing = [name for name, value in cells.items() if value is None]
    if missing:
        return {**out, "gate": "_summary:" + ",".join(missing), "class": "GRAMMAR"}

    summary = M._summary(markdown)
    if summary is None:
        return {**out, "gate": "_summary:figure_not_money_or_period", "class": "GRAMMAR"}
    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    if end < start:
        return {**out, "gate": "period_order", "class": "GRAMMAR"}

    blocks = M._blocks(markdown)
    out["blocks"] = {role: [name for name, _runs in entries]
                     for role, entries in sorted(blocks.items())}
    running = bool(M._RUNNING_BALANCE_RE.search(markdown))
    out["running_balance_header"] = running
    postings = []
    for role, (_d, _s, restated, _default) in M._ROLE_READING.items():
        if running and restated:
            continue
        for name, runs in blocks.get(role, []):
            found = M._section_rows(runs, role=role)
            if found is None:
                return {**out, "gate": f"_section_rows:{role}",
                        "block": mask(name), "class": "GRAMMAR"}
            postings.extend(found)
    out["n_postings"] = len(postings)
    if not postings:
        return {**out, "gate": "no_postings", "class": "GRAMMAR"}

    rows = []
    from analysis.schema import Transaction
    for posting in postings:
        iso = iso_within_period(posting.day, start, end)
        if iso is None:
            return {**out, "gate": "row_date_outside_period", "class": "GRAMMAR"}
        rows.append(Transaction(
            date=iso, description=posting.description,
            amount=round(posting.amount if posting.credit else -posting.amount, 2),
            direction="credit" if posting.credit else "debit"))

    credits_rows = [r for r in rows if r.direction == "credit"]
    debit_rows = [r for r in rows if r.direction == "debit"]
    credited = sum(r.amount for r in credits_rows)
    debited = -sum(r.amount for r in debit_rows)
    checks = {
        "summary_identity": abs(
            summary.previous + summary.credits - summary.debits
            - summary.service_charge + summary.interest - summary.closing) <= M._TOLERANCE,
        "credit_side": (
            (len(credits_rows) == summary.credit_count
             and abs(credited - summary.credits) <= M._TOLERANCE)
            or (summary.interest > 0 and len(credits_rows) == summary.credit_count + 1
                and abs(credited - summary.credits - summary.interest) <= M._TOLERANCE)),
        "debit_side": (
            (len(debit_rows) == summary.debit_count
             and abs(debited - summary.debits) <= M._TOLERANCE)
            or (summary.service_charge > 0 and len(debit_rows) > summary.debit_count
                and abs(debited - summary.debits - summary.service_charge) <= M._TOLERANCE)),
    }
    out["identities"] = checks
    out["count_delta"] = {"credit": len(credits_rows) - summary.credit_count,
                          "debit": len(debit_rows) - summary.debit_count}
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return {**out, "gate": "_matches_the_printed_summary:" + ",".join(failed),
                "class": "IDENTITY"}

    printed_grid: dict[str, float] = {}
    for name, runs in blocks.get("grid", []):
        found = M._grid(runs, start=start, end=end)
        if found is None:
            return {**out, "gate": "_grid", "block": mask(name), "class": "GRAMMAR"}
        for day, balance in found.items():
            if day in printed_grid and abs(printed_grid[day] - balance) > M._TOLERANCE:
                return {**out, "gate": "_grid:day_printed_twice", "class": "GRAMMAR"}
            printed_grid[day] = balance
    out["n_grid_days"] = len(printed_grid)
    if printed_grid and not M._matches_the_printed_grid(rows, printed_grid, summary):
        walked = {}
        running_balance = summary.previous
        for row in sorted(rows, key=lambda item: item.date):
            running_balance = round(running_balance + row.amount, 2)
            walked[row.date] = running_balance
        out["grid"] = {"days_only_in_ledger": len(set(walked) - set(printed_grid)),
                       "days_only_in_grid": len(set(printed_grid) - set(walked))}
        return {**out, "gate": "_matches_the_printed_grid", "class": "IDENTITY"}

    return {**out, "gate": "none (parses)", "class": "PARSES"}


# ---------------------------------------------------------------------------
# core_processor_daily
# ---------------------------------------------------------------------------

def trace_daily(markdown: str) -> dict:
    from analysis import core_processor_daily as M

    out: dict = {"reader": "core_processor_daily"}
    out["claims"] = bool(M.detect(markdown).claims)
    if not out["claims"]:
        return {**out, "gate": "detect", "class": "DETECT"}

    front = M._front_matter(markdown)
    period_cells = {
        "last_statement": M._once(front, M._OPENING_DATE_RE),
        "this_statement": M._once(front, M._CLOSING_DATE_RE),
        "days": M._once(front, M._DAYS_RE),
    }
    out["period"] = {name: value is not None for name, value in period_cells.items()}
    missing = [name for name, value in period_cells.items() if value is None]
    if missing:
        return {**out, "gate": "_period:" + ",".join(missing), "class": "GRAMMAR"}
    if (M._long_date(period_cells["last_statement"]) is None
            or M._long_date(period_cells["this_statement"]) is None):
        return {**out, "gate": "_period:not_a_date", "class": "GRAMMAR"}

    account = M._ACCOUNT_RE.search(markdown)
    out["account_field"] = account is not None
    region = M._summary_region(markdown)
    if region is None:
        return {**out, "gate": "_summary_region:no_account_field", "class": "GRAMMAR"}
    strip = {
        "beginning": M._once(region, M._BEGINNING_RE),
        "ending": M._once(region, M._ENDING_RE),
        "additions": M._once(region, M._ADDITIONS_RE),
        "subtractions": M._once(region, M._SUBTRACTIONS_RE),
    }
    out["strip"] = {name: value is not None for name, value in strip.items()}
    out["labels_in_document"] = {
        "beginning": "Beginning balance" in markdown,
        "ending": "Ending balance" in markdown,
        "additions": "Total additions" in markdown,
        "subtractions": "Total subtractions" in markdown,
    }
    missing = [name for name, value in strip.items() if value is None]
    if missing:
        return {**out, "gate": "_summary:" + ",".join(missing), "class": "GRAMMAR"}

    summary = M._summary(markdown)
    if summary is None:
        return {**out, "gate": "_summary:figure_not_money", "class": "GRAMMAR"}
    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)
    if end < start:
        return {**out, "gate": "period_order", "class": "GRAMMAR"}
    if (end - start).days + 1 != summary.days:
        return {**out, "gate": "printed_days_disagree_with_printed_dates",
                "class": "IDENTITY"}
    seed = start - timedelta(days=1)

    sections = M._sections(markdown)
    out["sections"] = {name: len(runs) for name, runs in sorted(sections.items())}
    ledger_names = {name for name, _c, _d in M._LEDGER_SECTIONS}
    if not sections.keys() & ledger_names:
        return {**out, "gate": "no_ledger_section", "class": "GRAMMAR"}

    rows = []
    for name, credit, default in M._LEDGER_SECTIONS:
        block = sections.get(name)
        if block is None:
            continue
        found = M._rows(block, credit=credit, start=start, end=end, default=default)
        if found is None:
            return {**out, "gate": f"_rows:{name}", "class": "GRAMMAR"}
        rows.extend(found)
    out["n_rows"] = len(rows)

    credited = sum(r.amount for r in rows if r.direction == "credit")
    debited = -sum(r.amount for r in rows if r.direction == "debit")
    checks = {
        "credit_total": abs(credited - summary.additions) <= 0.005,
        "debit_total": abs(debited - summary.subtractions) <= 0.005,
        "summary_identity": abs(summary.beginning + summary.additions
                                - summary.subtractions - summary.ending) <= 0.005,
    }
    out["identities"] = checks
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return {**out, "gate": "_matches_the_printed_summary:" + ",".join(failed),
                "class": "IDENTITY"}

    out["grid_section_present"] = "DAILY BALANCES" in sections
    printed = M._grid(sections.get("DAILY BALANCES", []), seed=seed, end=end)
    if printed is None:
        return {**out, "gate": "_grid", "class": "GRAMMAR"}
    out["n_grid_days"] = len(printed)
    if not printed:
        return {**out, "gate": "_grid:empty", "class": "GRAMMAR"}
    if not M._matches_the_printed_grid(rows, printed, beginning=summary.beginning,
                                       seed=seed.isoformat()):
        walked = {seed.isoformat(): summary.beginning}
        running = summary.beginning
        for row in sorted(rows, key=lambda item: item.date):
            running = round(running + row.amount, 2)
            walked[row.date] = running
        printed_days = {entry.date for entry in printed}
        out["grid"] = {"days_only_in_grid": len(printed_days - set(walked)),
                       "days_only_in_ledger": len(set(walked) - printed_days)}
        return {**out, "gate": "_matches_the_printed_grid", "class": "IDENTITY"}

    return {**out, "gate": "none (parses)", "class": "PARSES"}


# ---------------------------------------------------------------------------
# category_partition
# ---------------------------------------------------------------------------

def trace_category_partition(markdown: str) -> dict:
    from analysis import category_partition as M
    from analysis.tables import section_runs, unique_match

    out: dict = {"reader": "category_partition"}
    out["claims"] = bool(M.detect(markdown).claims)
    if not out["claims"]:
        return {**out, "gate": "detect", "class": "DETECT"}

    header = unique_match(markdown, M._SUMMARY_HEADER_RE)
    line = unique_match(markdown, M._PARTITION_LINE_RE)
    account = unique_match(markdown, M._ACCOUNT_NUMBER_RE)
    out["strip"] = {"summary_header": header is not None,
                    "partition_line": line is not None,
                    "account_number_unique": account is not None}
    out["account_numbers_printed"] = len({
        m.group(1) for m in M._ACCOUNT_NUMBER_RE.finditer(markdown)})
    missing = [name for name, ok in out["strip"].items() if not ok]
    if missing:
        # More than one DISTINCT account number is a second account, not a
        # reading to choose between (L-1); `unique_match` refuses either way.
        if account is None and out["account_numbers_printed"] > 1:
            return {**out, "gate": "_summary:two_account_numbers", "class": "L1"}
        return {**out, "gate": "_summary:" + ",".join(missing), "class": "GRAMMAR"}

    entries = M._entries(line.group(1))
    out["n_partition_entries"] = len(entries) if entries else 0
    if entries is None:
        return {**out, "gate": "_entries:line_holds_unaccounted_text", "class": "GRAMMAR"}
    out["entry_labels"] = [mask(label) for label, _m in entries]

    summary = M._summary(markdown)
    if summary is None:
        cycle = unique_match(markdown, M._CYCLE_DAYS_RE)
        out["cycle_days_printed_once"] = cycle is not None
        return {**out, "gate": "_summary:entry_or_period", "class": "GRAMMAR"}
    start, end = date.fromisoformat(summary.start), date.fromisoformat(summary.end)

    sections = section_runs(markdown, M._SECTION_RE)
    out["sections"] = {name: len(runs) for name, runs in sorted(sections.items())}
    unified = sections.get(M._UNIFIED_HEADING, [])
    out["issue"] = "unified" if unified else "sectioned"
    if unified:
        rows = M._unified_rows(unified, start=start, end=end)
        if rows is None:
            return {**out, "gate": "_unified_rows", "class": "GRAMMAR"}
        recap = M._recap_pairs(sections.get("CHECKS AND OTHER DEBITS", []),
                               start=start, end=end)
        if recap is None:
            return {**out, "gate": "_recap_pairs", "class": "GRAMMAR"}
        if not M._reprints(recap, rows):
            return {**out, "gate": "_reprints:recap_row_not_in_ledger", "class": "IDENTITY"}
    else:
        rows = []
        for heading, credit in ((M._CREDIT_HEADING, True),
                                *((h, False) for h in M._DEBIT_HEADINGS)):
            found = M._sectioned_rows(sections.get(heading, []), credit=credit,
                                      start=start, end=end)
            if found is None:
                return {**out, "gate": f"_sectioned_rows:{heading}", "class": "GRAMMAR"}
            rows.extend(found)
    out["n_rows"] = len(rows)

    printed = list(M._SERVICE_CHARGE_TOTAL_RE.finditer(markdown))
    if printed and len({found.groups() for found in printed}) != 1:
        return {**out, "gate": "service_charge_total_printed_twice", "class": "GRAMMAR"}
    charged = M._signed(printed[0]) if printed else None
    if printed and (charged is None or charged[1] != ""):
        return {**out, "gate": "service_charge_total_marked", "class": "GRAMMAR"}
    total_charge = charged[0] if charged else None

    credit_rows = [r for r in rows if r.direction == "credit"]
    debit_rows = [r for r in rows if r.direction == "debit"]
    checks = {
        "partition_identity": abs(summary.beginning + summary.credits
                                  - summary.debits - summary.ending) <= M._TOLERANCE,
        "uncounted_vs_charge_recap": abs(
            summary.uncounted - (total_charge or 0.0)) <= M._TOLERANCE,
        "credit_count": len(credit_rows) == summary.expected_rows(credit=True),
        "debit_count": len(debit_rows) == summary.expected_rows(credit=False),
        "credit_total": abs(sum(abs(r.amount) for r in credit_rows)
                            - summary.credits) <= M._TOLERANCE,
        "debit_total": abs(sum(abs(r.amount) for r in debit_rows)
                           - summary.debits) <= M._TOLERANCE,
    }
    out["identities"] = checks
    out["count_delta"] = {
        "credit": len(credit_rows) - summary.expected_rows(credit=True),
        "debit": len(debit_rows) - summary.expected_rows(credit=False)}
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return {**out, "gate": "_matches_the_printed_partition:" + ",".join(failed),
                "class": "IDENTITY"}

    glance = list(M._GLANCE_ROW_RE.finditer(markdown))
    out["relationship_rows"] = len(glance)
    if glance:
        out["relationship_accounts_listed"] = len(M._AMOUNT_RE.findall(glance[0].group(1)))
        if not M._matches_the_relationship_block(markdown, summary):
            klass = "L1" if out["relationship_accounts_listed"] > 1 else "IDENTITY"
            return {**out, "gate": "_matches_the_relationship_block", "class": klass}

    if M._COLLECTED_GRID_HEADING in sections and not M._grid_seed(
            sections[M._COLLECTED_GRID_HEADING], summary):
        return {**out, "gate": "_grid_seed:collected", "class": "GRAMMAR"}

    grid = None
    if M._LEDGER_GRID_HEADING in sections:
        grid = M._grid(sections[M._LEDGER_GRID_HEADING], summary=summary)
        if grid is None:
            return {**out, "gate": "_grid:ledger", "class": "GRAMMAR"}
        out["n_grid_days"] = len(grid)
        if not M._matches_the_printed_grid(rows, grid, summary):
            return {**out, "gate": "_matches_the_printed_grid", "class": "IDENTITY"}
    if unified and not M._walks_to_the_printed_ending(rows, summary):
        return {**out, "gate": "_walks_to_the_printed_ending", "class": "IDENTITY"}
    if grid is None and not unified:
        return {**out, "gate": "no_per_day_oracle", "class": "GRAMMAR"}

    return {**out, "gate": "none (parses)", "class": "PARSES"}


# ---------------------------------------------------------------------------
# the readers, and the agreement check
# ---------------------------------------------------------------------------

READERS = {
    "core_processor_sectioned": (
        trace_sectioned, "analysis.core_processor_sectioned",
        "parse_core_processor_sectioned_statement"),
    "core_processor_enclosures": (
        trace_enclosures, "analysis.core_processor_enclosures",
        "parse_core_processor_enclosures_statement"),
    "core_processor_daily": (
        trace_daily, "analysis.core_processor_daily",
        "parse_core_processor_daily_statement"),
    "category_partition": (
        trace_category_partition, "analysis.category_partition",
        "parse_category_partition_statement"),
}

GROUP_READER = {
    "DECL:core_processor_sectioned": "core_processor_sectioned",
    "DECL:core_processor_enclosures": "core_processor_enclosures",
    "DECL:core_processor_daily": "core_processor_daily",
    "DECL:category_partition": "category_partition",
    "RV:core_processor_enclosures": "core_processor_enclosures",
    "WH:core_processor_enclosures": "core_processor_enclosures",
}


def publishes(reader: str, markdown: str) -> bool | str:
    """Does the real reader publish this document? The trace's control."""
    import importlib
    _trace, module_name, func_name = READERS[reader]
    module = importlib.import_module(module_name)
    try:
        return getattr(module, func_name)(markdown) is not None
    except Exception as exc:  # a raise is not a decline; say so
        return f"raises:{type(exc).__name__}"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def load_population(args) -> list[tuple[str, str]]:
    """`(sha16, reader)` pairs."""
    found: dict[str, str] = {}
    if args.group:
        groups = json.loads(args.clusters.read_text(encoding="utf-8"))["groups"]
        for name in args.group:
            reader = GROUP_READER.get(name)
            for sha16 in groups.get(name, {}).get("shas16", []):
                found[sha16] = reader or ""
    if args.shas:
        for raw in Path(args.shas).read_text(encoding="utf-8").splitlines():
            token = raw.strip()
            if not token or token.startswith("#"):
                continue
            parts = token.split()
            found[parts[0].upper()] = parts[1] if len(parts) > 1 else args.reader or ""
    return sorted(found.items())


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
    ap.add_argument("--shas", type=Path, default=None)
    ap.add_argument("--reader", default=None, help="reader for a --shas population")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    if not args.group and not args.shas:
        args.group = list(GROUP_READER)[:4]

    import csv
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
    for sha16, reader in population:
        entry: dict = {"sha16": sha16, "reader": reader, "route": route.get(sha16, "")}
        sha = by16.get(sha16)
        if sha is None:
            table.append({**entry, "gate": "absent-from-run", "class": "ABSENT"})
            continue
        entry["outcome"] = rows[sha].get("outcome_class", "")
        entry["reason"] = rows[sha].get("outcome_reason", "")
        entry["folder"] = rows[sha].get("folder_label", "")
        markdown, pages = cache.text(sha)
        if markdown is None:
            table.append({**entry, "gate": "no-cached-text", "class": "ABSENT"})
            continue
        entry["pages"] = len(pages)
        if reader not in READERS:
            table.append({**entry, "gate": "no-reader-for-group", "class": "ABSENT"})
            continue
        traced = READERS[reader][0](markdown)
        entry.update(traced)
        published = publishes(reader, markdown)
        entry["reader_publishes"] = published
        says_declines = traced["class"] != "PARSES"
        if published is not (not says_declines):
            entry["class"] = "TRACE-DISAGREES"
            entry["gate"] = f"{traced['gate']} vs reader publishes={published}"
        table.append(entry)

    counts: dict[str, int] = {}
    by_route: dict[tuple[str, str], int] = {}
    for e in table:
        counts[e["class"]] = counts.get(e["class"], 0) + 1
        key = (e["class"], e.get("route", ""))
        by_route[key] = by_route.get(key, 0) + 1

    lines = [f"# CP-DECLINES decline probe — run `{args.run.name}`", "",
             "| class | documents |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(counts.items())]
    lines += ["", "| class | route | documents |", "|---|---|---:|"]
    lines += [f"| {k[0]} | {k[1]} | {v} |" for k, v in sorted(by_route.items())]
    lines += ["", "| sha16 | reader | route | outcome | class | first refusing gate |",
              "|---|---|---|---|---|---|"]
    for e in table:
        lines.append(
            f"| {e['sha16']} | {e.get('reader','')} | {e.get('route','')} | "
            f"{e.get('outcome','')}/{e.get('reason','')} | {e['class']} | `{e['gate']}` |")
    lines.append("")
    for e in table:
        lines.append(f"## {e['sha16']} — {e.get('reader','')} — {e['class']} — `{e['gate']}`")
        lines.append("")
        for key, value in e.items():
            if key in ("sha16", "reader", "class", "gate", "outcome", "reason",
                       "folder", "entry_labels"):
                continue
            lines.append(f"- {key}: {value}")
        if e.get("entry_labels"):
            lines.append("- partition entries: " + ", ".join(
                f"`{label}`" for label in e["entry_labels"]))
        lines.append("")
    report = "\n".join(lines) + "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(table, indent=1, default=str), encoding="utf-8")
    print(report if not args.out else "\n".join(lines[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
