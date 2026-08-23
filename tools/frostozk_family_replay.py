"""Replay the two W3 §FROSTOZK families at HEAD and print what they publish.

The card's closure instrument, committed so its headline numbers are
reproducible by review rather than described in a log::

    python -m tools.frostozk_family_replay \
        --data-dir <checkout>/webapp_data \
        --shas-file <list of content_sha256, one per line> [--shas-file ...]

READ-ONLY in the two senses the wave requires. Nothing is written anywhere; and
the `webapp_data` sqlite index is never opened — OCR payloads are reached by
DIRECT file path, enumerating every capability partition of `ocr_settings_key`
exactly as `tools/regfp_zero_movement_sweep.py` does and taking the longest
reconstruction. `parse_mode="deterministic"` cannot reach the extraction
branch, so it makes no model call and costs $0.00.

WHAT IT PRINTS, AND WHAT IT DELIBERATELY DOES NOT. Counts, class names and
booleans. Never an amount, a balance, a date, a name, an account number or a
line of document text: the whole point of an instrument that reads the archive
is that its output can be pasted into a review, so it must not carry archive
content out with it. `adb` is reported as present or absent rather than as a
figure for the same reason.

THREE MEASUREMENTS, one per section of the card:

``outcome``
    the published outcome class and reason (`telemetry.record.classify_outcome`
    over the real analysis payload), the integrity flags, and the captured vs
    expected per-direction counts `analysis/reconcile.py` computed.
``frost scope``
    the count-semantics measurement behind the `frost:debit` entry in
    `analysis/count_semantics.py`: how far the captured debit rows exceed the
    printed withdrawal figure, and whether that excess is exactly accounted for
    by the two named row classes (rows the bank printed under its own
    `SERVICE CHARGE/FEE` transaction type, and rows printed with a zero
    amount). `explained` is the claim; it is measured per document, not
    asserted.
``ozk solve``
    the direction solve's ambiguity census: how many days the daily grid
    carries, how many of those admit more than one sign assignment locally, and
    how many the printed credit count leaves ambiguous after the cross-day
    constraint. The reader publishes only when the last number is zero, so this
    is the measurement that says whether the family's uniqueness is a property
    of the documents or of luck.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

from analysis import bank_ozk, parser_registry_entries  # noqa: F401
from analysis.parser_registry import admissible_text, resolve
from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from ocr.document import StatementMarkdown
from telemetry.record import classify_outcome
from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

_PARTITIONS = [
    ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
    for force, local, visual in itertools.product((False, True), repeat=3)
]


def _document(artifacts: Path, sha: str) -> StatementMarkdown | None:
    """The cached OCR document for one sha, by direct path.

    Every partition is enumerated and the longest reconstruction wins — the
    same "never guess a rung" discipline the sweep instrument documents,
    without its stored-payload proof, which this tool does not need: it is
    recomputing rather than comparing against a run.
    """
    best: StatementMarkdown | None = None
    for partition in _PARTITIONS:
        composed = cache_key(STAGE_OCR, sha, partition)
        path = artifacts / STAGE_OCR / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            continue
        candidate = StatementMarkdown(
            source_file="document.pdf",
            model=str(document.get("model") or ""),
            pages=[str(page) for page in (document.get("pages") or [])],
        )
        if best is None or len(candidate.to_markdown()) > len(best.to_markdown()):
            best = candidate
    return best


def _frost_scope(payload: dict) -> str:
    """How the printed withdrawal count and the captured debit rows differ."""
    statement = payload.get("statement") or {}
    rows = statement.get("transactions") or []
    debits = [row for row in rows if row.get("direction") == "debit"]
    printed = statement.get("stated_debit_count")
    charges = [
        row for row in debits if "SERVICE CHARGE/FEE" in (row.get("description") or "")
    ]
    zeroes = [row for row in debits if row.get("amount") == 0.0]
    overlap = {id(row) for row in charges} & {id(row) for row in zeroes}
    excess = None if printed is None else len(debits) - printed
    explained = excess is not None and excess == len(charges) + len(zeroes)
    return (
        f"debit_rows={len(debits)} printed={printed} excess={excess} "
        f"service_charge_rows={len(charges)} zero_amount_rows={len(zeroes)} "
        f"overlap={len(overlap)} explained={explained}"
    )


def _ozk_solve(markdown: str) -> str:
    """The direction solve's ambiguity census for one document.

    Re-derives the reader's own per-day enumeration through its private
    helpers, so the census is of the shipped solver rather than of a second
    implementation of it.
    """
    summary = bank_ozk.unique_match(markdown, bank_ozk._SUMMARY_RE)
    if summary is None:
        return "no_summary"
    statement = bank_ozk.parse_bank_ozk_statement(markdown)
    opening = bank_ozk._as_of(summary.group(1))
    closing = bank_ozk._as_of(summary.group(7))
    if opening is None or closing is None or statement is None:
        return "unparsed"
    from datetime import timedelta

    start, end = opening + timedelta(days=1), closing
    grid: dict[str, int] = {}
    for region in bank_ozk._regions(markdown, bank_ozk._DAILY_HEAD_RE):
        region = region.split("DATE AMOUNT")[-1]
        for match in bank_ozk._ROW_DATE_RE.finditer(region):
            iso = bank_ozk.iso_unique_in_period(
                int(match.group(1)), int(match.group(2)), start=start, end=end
            )
            balance = bank_ozk._SIGNED_RE.match(region[match.end():].lstrip())
            if iso is None or balance is None:
                return "unreadable_grid"
            grid[iso] = bank_ozk._cents(balance.group(0), signed=True)
    read = bank_ozk._rows(markdown, start, end)
    if read is None:
        return "unreadable_rows"
    cheques, others = read
    previous = bank_ozk._cents(summary.group(2))
    credit_count = int(summary.group(3))

    locally_ambiguous = 0
    counts: list[list[int]] = []
    balance = previous
    for day, printed_balance in sorted(grid.items()):
        known = [row for row in cheques if row.day == day]
        unknown = [row for row in others if row.day == day]
        residual = printed_balance - balance + sum(row.cents for row in known)
        solutions = bank_ozk._day_solutions([row.cents for row in unknown], residual)
        if not solutions:
            return "unsolved_day"
        if len(solutions) > 1:
            locally_ambiguous += 1
        counts.append(sorted({len(solution) for solution in solutions}))
        balance = printed_balance

    # How many days the printed count still leaves open, once the cross-day
    # constraint has chosen. Zero on every document the reader publishes.
    residual_ambiguous = 0
    total = sum(min(count) for count in counts)
    if total != credit_count:
        residual_ambiguous = sum(1 for count in counts if len(count) > 1)
    return (
        f"grid_days={len(grid)} cheque_rows={len(cheques)} other_rows={len(others)} "
        f"locally_ambiguous_days={locally_ambiguous} "
        f"days_needing_the_printed_count={residual_ambiguous} "
        f"published={statement is not None}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--sha", action="append", default=[])
    parser.add_argument("--shas-file", action="append", default=[])
    parser.add_argument(
        "--claims-only",
        action="append",
        default=[],
        help=(
            "score ONE registration's detection markers over every sha and "
            "report only the claims, skipping the analysis. This is the "
            "non-target probe: run over the whole archive it answers 'does "
            "this registration claim anything outside its named population', "
            "which is a different question from whether an analysis moved, and "
            "it is answerable on documents whose analysis raises."
        ),
    )
    args = parser.parse_args(argv)

    shas: list[str] = [sha.strip().upper() for sha in args.sha if sha.strip()]
    for path in args.shas_file:
        shas.extend(
            line.strip().upper()
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    if not shas:
        parser.error("no shas given")

    artifacts = Path(args.data_dir) / "artifacts"
    tally: dict[str, int] = {}

    if args.claims_only:
        from analysis.parser_registry import by_id, score_markers

        probed = [by_id(parser_id) for parser_id in args.claims_only]
        for sha in shas:
            document = _document(artifacts, sha)
            if document is None:
                tally["no_cached_text"] = tally.get("no_cached_text", 0) + 1
                continue
            tally["scored"] = tally.get("scored", 0) + 1
            markdown = admissible_text(document.to_markdown())
            for registration in probed:
                prepared = (
                    registration.normalize(markdown)
                    if registration.normalize
                    else markdown
                )
                detection = score_markers(registration.markers, prepared)
                if detection.claims:
                    print(f"{sha} CLAIMED by {registration.id} score={detection.score}")
                    key = f"claimed:{registration.id}"
                    tally[key] = tally.get(key, 0) + 1
        print("SUMMARY", json.dumps(tally, sort_keys=True))
        return 0

    for sha in shas:
        document = _document(artifacts, sha)
        if document is None:
            print(f"{sha[:8]} no_cached_text")
            tally["no_cached_text"] = tally.get("no_cached_text", 0) + 1
            continue
        markdown = document.to_markdown()
        dispatch = resolve(markdown)
        report = analyze_markdown(markdown, parse_mode="deterministic", sheets=document.pages)
        payload = report_to_dict(report) if report is not None else None
        outcome, reason = classify_outcome(payload)
        tally[f"{outcome}/{reason}"] = tally.get(f"{outcome}/{reason}", 0) + 1
        integrity = (payload or {}).get("integrity") or {}
        metrics = (payload or {}).get("metrics") or {}
        recon = (payload or {}).get("reconciliation") or {}
        statement = (payload or {}).get("statement") or {}
        line = (
            f"{sha[:8]} parser={dispatch.parser_id or dispatch.outcome} "
            f"outcome={outcome}/{reason} flags={sorted(integrity.get('flags') or [])} "
            f"adb={'present' if metrics.get('average_daily_balance') is not None else 'withheld'} "
            f"rows={len(statement.get('transactions') or [])} "
            f"credit={recon.get('captured_credit_count')}/{recon.get('expected_credit_count')} "
            f"debit={recon.get('captured_debit_count')}/{recon.get('expected_debit_count')} "
            f"coverage={recon.get('credit_coverage')}/{recon.get('debit_coverage')}"
        )
        if dispatch.parser_id == "frost" and payload is not None:
            line += f" | {_frost_scope(payload)}"
        if dispatch.parser_id == "bank_ozk":
            line += f" | {_ozk_solve(markdown)}"
        print(line)
    print("SUMMARY", json.dumps(tally, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
