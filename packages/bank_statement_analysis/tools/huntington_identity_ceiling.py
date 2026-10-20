"""huntington_identity_ceiling.py — the CEILING of any widening of this reader.

    python -m tools.huntington_identity_ceiling --run <run> --data-dir <cold cache> \
        --mode all_identities [--group DECL:huntington] [--out <private>.md]

`analysis.huntington._validate` runs the four identities the statement prints
and refuses the document if any one misses. `huntington_decline_probe` names
which one refused. This instrument answers the question that decides whether a
widening is worth designing at all:

    if the identities were not there, would the PLATFORM validate these
    documents?

It replays each sha through the same call the runner makes, with
`analysis.huntington._validate` replaced IN MEMORY (the tree on disk is never
touched) by:

  ``absent_evidence``  the four identities minus the ones whose EVIDENCE this
                       print does not carry — the fee net where no
                       ``Service Charge Detail`` block is printed, the
                       ``Balance Activity`` walk where no daily-balance block
                       is printed. This is the most a defensible widening could
                       ever skip: it never skips a check the document can make.
  ``all_identities``   every identity removed. The ceiling of RELAXATION: with
                       the payload unchanged there is nothing left to relax.
  ``recon_forced``     `all_identities`, plus `reconcile` forced to `ok` and
                       `summary_ok` — the platform tolerance the carried finding
                       once asked for, granted in full, with NO amount written.
  ``written_fee``      the reader publishes the bank-stated
                       ``Total Service Charges (-)`` as a debit dated the period
                       end, so the ledger closes. This is a READING, not a
                       relaxation, and it WRITES AN AMOUNT the statement never
                       dates — barred by the repair doctrine. It is here because
                       the record has to name the real barrier, and because
                       "nothing can beat the ceiling" was the claim this mode
                       disproved (review MAJOR-1).

**What this instrument bounds, stated exactly.** `absent_evidence` and
`all_identities` bound RELAXATIONS of `_validate` over the payload the reader
already builds. They do NOT bound every possible reader change: a reader that
builds a DIFFERENT payload is outside them, and `written_fee` is the measured
proof of that. Read the two together or the smaller number will be mistaken for
an impossibility.

The outcome is the platform's own — `telemetry.record.classify_outcome` over
the pipeline payload — so a ceiling of zero validated is a measured fact about
the documents and the platform, not an opinion about the grammar. That is the
number a "newly validated = 0" finding has to stand on.

Read-only, deterministic, $0, and it prints no document value: sha, outcome
class, outcome reason and counts only. The patch lives inside this process for
the duration of one replay and is removed in a `finally`.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_CLUSTERS = Path("docs/moneythumb-replacement/census_batch9/clusters.json")

MODES = ("absent_evidence", "all_identities", "recon_forced", "written_fee")


@contextlib.contextmanager
def relaxed(mode: str, markdown: str):
    """`_validate` with the named identities removed, for one replay only."""
    from analysis import huntington as H

    original = H._validate
    original_fees = H._service_charges
    from analysis import pipeline as P
    original_reconcile = P.reconcile
    undo = []

    if mode == "recon_forced":
        # The platform tolerance the carried finding once asked for, granted in
        # full and then some: the reconciler cannot object at all. No amount is
        # written, so the ledger is still short by the stated fee.
        def forced(stmt, *, parser_id=None):
            result = original_reconcile(stmt, parser_id=parser_id)
            result.ok = True
            result.summary_ok = True
            return result
        P.reconcile = forced
        undo.append(lambda: setattr(P, "reconcile", original_reconcile))

    if mode == "written_fee":
        # A READER change, and the one the ceiling does not bound: where the
        # print itemises no fees, publish the bank-stated total as a single
        # debit dated the period END. `_service_charges` is where a reader
        # would put it, and it is read as a module global at call time, so the
        # substitution exercises the real path rather than a post-edit.
        #
        # This writes an amount on a date the statement never prints. That is
        # exactly what the repair doctrine forbids, and the point of measuring
        # it is to name the barrier correctly, never to propose it.
        has_fee_block = ("Service Charge Detail" in markdown
                         or "Service Charge Summary" in markdown)

        def fees_with_written_charge(blocks, start, end):
            got = original_fees(blocks, start, end)
            if has_fee_block or got is None:
                return got
            rows, net = got
            if rows:
                return got
            summary = H._summary(H._lines(markdown))
            charge = None if summary is None else summary.get("Total Service Charges (-)")
            if not charge:
                return got
            written = H.Transaction(
                date=end.isoformat(),
                description="Service charge (stated, never itemised — WRITTEN BY THE PROBE)",
                amount=round(-charge, 2),
                direction="debit",
            )
            return [written], round(charge, 2)
        H._service_charges = fees_with_written_charge
        undo.append(lambda: setattr(H, "_service_charges", original_fees))

    if mode in ("all_identities", "recon_forced"):
        def patched(*_args, **_kwargs) -> bool:
            return True
    else:
        # Only the identities this print carries no evidence for. Absence is
        # established from the PRINT — the block's own heading words are not in
        # the document at all — never from "the grammar found nothing", which
        # is how a mis-parse would silently license a skip.
        has_fee_block = "Service Charge Detail" in markdown or "Service Charge Summary" in markdown
        has_daily_block = "Balance Activity" in markdown or "Daily Balance" in markdown

        def patched(summary, section_txns, fee_txns, service_net, balances) -> bool:
            if has_fee_block and has_daily_block:
                return original(summary, section_txns, fee_txns, service_net, balances)
            charges = summary.get("Total Service Charges (-)", 0.0)
            probe_net = charges if not has_fee_block else service_net
            probe_balances = balances
            if not has_daily_block and not balances:
                # Substitute the one day the document does print an end-of-day
                # balance for: the last day of the period, at the stated ending
                # balance. That is the weakest possible stand-in and it keeps
                # the closing identity live.
                ending = summary.get("Ending Balance")
                if ending is None:
                    return False
                from datetime import date
                probe_balances = [(date.max, ending)]
            return original(summary, section_txns, fee_txns, probe_net, probe_balances)

    H._validate = patched
    undo.append(lambda: setattr(H, "_validate", original))
    try:
        yield
    finally:
        for restore in reversed(undo):
            restore()


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=None)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    # `action="append"` APPENDS TO ITS DEFAULT, so a non-empty default here would
    # make `--group OTHER` mean "DECL:huntington and OTHER" — an instrument that can
    # be widened but never aimed. The default is filled in after parsing instead.
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--mode", choices=MODES, default="all_identities")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    if not args.group:
        args.group = ["DECL:huntington"]

    from tools.cohort_replay import ColdCache, load_baseline_rows, replay_one

    groups = json.loads(args.clusters.read_text(encoding="utf-8"))["groups"]
    population: list[str] = []
    for name in args.group:
        population.extend(groups.get(name, {}).get("shas16", []))
    rows = load_baseline_rows(args.run)
    by16 = {sha[:16]: sha for sha in rows}
    cache = ColdCache(args.data_dir)

    table = []
    for token in sorted(set(population)):
        sha = by16.get(token)
        if sha is None:
            table.append({"sha16": token, "after": "absent", "reason": "-"})
            continue
        markdown, pages = cache.text(sha)
        if markdown is None:
            table.append({"sha16": token, "after": "no_text", "reason": "-"})
            continue
        with relaxed(args.mode, markdown):
            _payload, klass, reason, claimed = replay_one(markdown, pages, account_shape=True)
        table.append({"sha16": token, "before": rows[sha].get("outcome_class", ""),
                      "after": klass, "reason": reason, "claimed": claimed or "-"})

    validated = [e for e in table if e["after"] == "validated"]
    lines = [f"# huntington identity ceiling — mode `{args.mode}` — run `{args.run.name}`", "",
             f"population {len(table)} · **validated at the ceiling: {len(validated)}**", "",
             f"| sha16 | baseline | under `{args.mode}` | reason |", "|---|---|---|---|"]
    for e in table:
        lines.append(f"| {e['sha16']} | {e.get('before','-')} | {e['after']} | {e['reason']} |")
    report = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
