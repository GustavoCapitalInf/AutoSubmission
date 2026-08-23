"""Replay `analysis/lili.py` over its census family and name every outcome.

W3 §LILI's family instrument, committed so the log's headline numbers are
re-derivable by review rather than asserted:

    python -m tools.lili_family_replay --data-dir <checkout>/webapp_data

READ-ONLY. Nothing is written anywhere; the `webapp_data` sqlite index is
never opened — OCR payloads are reached by DIRECT file path, enumerating every
capability partition of `ocr_settings_key` exactly as
`tools/regfp_zero_movement_sweep.py` does. It makes no model call and costs
$0.00: only `detect` and `parse` run.

THE POPULATION IS NOT A LIST IN THIS FILE. It is read out of the committed
census — `docs/moneythumb-replacement/CENSUS_BATCH8_DIGITAL.md`, the family
whose key `--family` names — so the instrument and the staffing record cannot
drift apart, and so this tool carries no archive-derived data of its own. A
`content_sha256` is a hash, not content; nothing else about a document is
printed. In particular NO document text, amount, name, account number or date
is read out of this tool.

WHAT IT PRINTS, per document: whether the registry claims it, whether any
OTHER registration also claims it (an ambiguity this card must not create),
the VERDICT the platform reaches on it (claimed is not validated: the reader
publishing a `Statement` is one thing and reconciliation, the metrics and the
withholding rules accepting it is another, so the verdict is measured through
`analyze_markdown` and `classify_outcome` rather than assumed from a parse),
and — where the reader declines — WHICH named gate declined it. The gate
attribution replays `parse_lili_statement`'s own sequence of gates against the
same helpers the reader uses, and the tool asserts on every document that the
attribution and `parse` agree: a `PUBLISHED` attribution must produce a
`Statement` and every other attribution must produce `None`. That assertion is
what makes the attribution a measurement rather than a reading of the source.

Gate ORDER is not observable at the parse boundary — every gate answers by
declining — so the order this tool reports is the order the reader applies,
and its value is exactly that: it says which fact about a document is the
first one that disqualifies it, which is what a refusal has to be able to say.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from datetime import date
from pathlib import Path

from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis import lili
from analysis.parser_registry import admissible_text, registrations, resolve
from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from ocr.document import StatementMarkdown
from telemetry.record import classify_outcome
from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CENSUS = REPO / "docs" / "moneythumb-replacement" / "CENSUS_BATCH8_DIGITAL.md"
DEFAULT_FAMILY = "lili_sunrise_banks_checking"

#: Every capability partition an OCR artifact can have been written under.
_OCR_KEYS = [
    ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
    for force, local, visual in itertools.product((False, True), repeat=3)
]

_SHA_RE = re.compile(r"^[0-9A-F]{64}$")


def family_shas(census: Path, family: str) -> list[str]:
    """The `content_sha256` list the committed census records for `family`."""
    lines = census.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("### ") and f"`{family}`" in line),
        None,
    )
    if start is None:
        raise SystemExit(f"census has no family `{family}`")
    shas: list[str] = []
    for line in lines[start:]:
        if line.startswith("### ") and shas:
            break
        if _SHA_RE.match(line.strip()):
            shas.append(line.strip())
    if not shas:
        raise SystemExit(f"census family `{family}` lists no shas")
    return shas


def cached_document(artifacts: Path, sha: str) -> tuple[str, list[str]] | None:
    """The document's cached OCR markdown AND its page partition.

    The partition matters as much as the text. It is part of the analysis
    input key and it is what a discovery run passes as `sheets`, so a replay
    that rebuilt the markdown and dropped the partition would be measuring a
    document the run never analysed.
    """
    best = None
    for key in _OCR_KEYS:
        composed = cache_key(STAGE_OCR, sha.upper(), key)
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
        pages = [str(page) for page in (document.get("pages") or [])]
        rendered = StatementMarkdown(
            source_file="", model=str(document.get("model") or ""), pages=pages,
        ).to_markdown()
        if best is None or len(rendered) > len(best[0]):
            best = (rendered, pages)
    return best


def cached_text(artifacts: Path, sha: str) -> str | None:
    """Just the markdown, for the instruments that do not run the analysis."""
    found = cached_document(artifacts, sha)
    return None if found is None else found[0]


def gate(text: str) -> str:
    """The first of `parse_lili_statement`'s gates that declines `text`."""
    if not lili.detect(text).claims:
        return "not_claimed"
    header = lili._header(text)
    if header is None:
        return "header_unreadable_or_contradictory"
    _account, start, end = header
    if not lili._dates_are_all_inside(text, start, end):
        return "INTEGRITY_printed_date_outside_the_printed_period"
    summary = lili._summary(text)
    if summary is None:
        return "summary_not_line_anchored"
    if len(summary[0]) != 1:
        return f"L1_summary_money_columns={len(summary[0])}"
    heads = len(lili._LEDGER_HEAD_RE.findall(text))
    if heads != 1:
        return f"L1_ledger_column_heads={heads}"
    beginning, deposits, withdrawals, fees, ending = (row[0] for row in summary)
    if withdrawals > 0 or fees > 0:
        return "debit_term_printed_as_an_inflow"
    if abs(beginning + deposits + withdrawals + fees - ending) > lili._CENT:
        return "summary_does_not_close_on_itself"
    postings = lili._postings(text)
    if postings is None:
        return "posting_unreadable"
    if not lili._chain_holds(postings, beginning, ending):
        return "chain_does_not_walk_beginning_to_ending"
    debited = sum(-posting.amount for posting in postings if posting.amount < 0)
    if abs(debited + withdrawals + fees) > lili._CENT:
        return "gross_debits_do_not_total_to_the_printed_terms"
    return "PUBLISHED"


def _sanity(statement, start: date, end: date) -> list[str]:
    """Properties every published statement must have, checked not assumed.

    The gates in the reader decide WHETHER to publish. These are twelve
    properties of what it published — the shape a downstream consumer is
    entitled to assume — and they are checked here rather than trusted,
    because a reader can pass every arithmetic gate and still hand the
    schema a direction that disagrees with its own sign.
    """
    problems: list[str] = []
    if statement.days_in_period != (end - start).days + 1:
        problems.append("days_in_period")
    if any(t.running_balance is None for t in statement.transactions):
        problems.append("a posting with no running balance")
    if any(not (start <= date.fromisoformat(t.date) <= end)
           for t in statement.transactions):
        problems.append("a posting dated outside the period")
    if any(t.direction not in ("debit", "credit") for t in statement.transactions):
        problems.append("a direction outside the vocabulary")
    if any((t.amount < 0) != (t.direction == "debit") for t in statement.transactions):
        problems.append("a direction that disagrees with its own sign")
    if not (statement.account_number or "").isdigit():
        problems.append("account_number")
    if statement.stated_total_debits is None or statement.stated_total_debits < 0:
        problems.append("stated_total_debits")
    if statement.stated_service_charge is None or statement.stated_service_charge < 0:
        problems.append("stated_service_charge")
    if statement.beginning_balance is None or statement.ending_balance is None:
        problems.append("a missing balance")
    if statement.stated_daily_balances:
        problems.append("daily balances this family does not print")
    if statement.bank != "Lili":
        problems.append("bank")
    if statement.account_name is not None:
        problems.append("account_name should stay unset")
    return problems


def _l1_packet(text: str) -> str:
    """The three-column packet, for a document the §L-1 gate refuses.

    The reader refuses these because the single-account schema cannot carry
    the sibling ledger. What the pending L-1 ruling needs is not that refusal
    but the BINDING behind it — which column is the checking account — so this
    prints the three readings that answer it independently of the header,
    which on this printing arrives interleaved and sometimes truncated:

    * the three-column arithmetic (column 1 + column 2 == column 3, per row);
    * whether the MAIN ledger's printed chain walks column 1's beginning to
      column 1's ending — and whether it walks column 3's;
    * whether the SIBLING ledger's chain walks column 2's.
    """
    summary = lili._summary(text)
    if summary is None or len(summary[0]) < 2:
        return ""
    heads = list(lili._LEDGER_HEAD_RE.finditer(text))
    identity = [round(row[0] + row[1] - row[-1], 2) for row in summary]
    closes = [round(c[0] + c[1] + c[2] + c[3] - c[4], 2) for c in zip(*summary)]
    if len(heads) < 2:
        return (f"      columns={len(summary[0])} heads={len(heads)} "
                f"col1+col2-colN={identity} per-column sum residuals={closes}")
    cut = heads[1].start()
    main, sibling = lili._postings(text[:cut]), lili._postings(text[cut:])
    on_first = main is not None and lili._chain_holds(main, summary[0][0], summary[4][0])
    on_last = main is not None and lili._chain_holds(main, summary[0][-1], summary[4][-1])
    on_second = sibling is not None and lili._chain_holds(sibling, summary[0][1], summary[4][1])
    return (f"      columns={len(summary[0])} heads={len(heads)} "
            f"col1+col2-colN={identity} per-column sum residuals={closes} "
            f"main_rows={0 if main is None else len(main)} "
            f"sibling_rows={0 if sibling is None else len(sibling)} "
            f"main_chains_on_col1={on_first} on_last_col={on_last} "
            f"sibling_chains_on_col2={on_second}")


def _verdict(markdown: str, pages: list[str]) -> str:
    """`class/reason` the platform reaches, end to end and deterministically.

    `parse_mode="deterministic"` cannot reach the extraction branch, so this
    stays a $0.00 measurement. It runs the WHOLE analysis, not just the
    reader: a document whose parse succeeds can still be withheld or sent to
    review by reconciliation, the metrics or the withholding rules, and this
    is the number the coverage claim rests on.
    """
    error_type = reason = None
    payload = None
    try:
        payload = report_to_dict(
            analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
        )
    except Exception as exc:  # noqa: BLE001 - the class is the finding
        error_type = type(exc).__name__
    if payload is None:
        dispatch = resolve(markdown)
        reason = "parser_declined" if dispatch.attempted else "no_parser_matched"
        error_type = error_type or "RuntimeError"
    outcome, detail = classify_outcome(payload, error_type=error_type, error_reason=reason)
    return f"{outcome}/{detail}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--census", default=DEFAULT_CENSUS, type=Path)
    parser.add_argument("--family", default=DEFAULT_FAMILY)
    args = parser.parse_args()

    artifacts = args.data_dir / "artifacts"
    others = [r for r in registrations() if r.id != "lili"]
    shas = family_shas(args.census, args.family)

    published = claimed = ambiguous = missing = 0
    dispatched: dict[tuple[str, str, tuple], int] = {}
    tally: dict[str, int] = {}
    verdicts: dict[str, int] = {}
    unsound: list[str] = []
    postings_published = 0
    published_by_account: dict[str, list] = {}
    for sha in shas:
        found = cached_document(artifacts, sha)
        if found is None:
            missing += 1
            print(f"{sha[:16]}  no cached OCR artifact")
            continue
        markdown, pages = found
        text = admissible_text(markdown)
        claims = lili.detect(text).claims
        rivals = sorted(r.id for r in others if r.detect(text).claims)
        verdict = gate(text)
        statement = lili.parse_lili_statement(text)
        assert (verdict == "PUBLISHED") == (statement is not None), (
            f"{sha[:16]}: gate attribution {verdict!r} disagrees with parse"
        )
        claimed += bool(claims)
        ambiguous += bool(rivals)
        published += statement is not None
        tally[verdict] = tally.get(verdict, 0) + 1
        if statement is not None:
            problems = _sanity(statement,
                               date.fromisoformat(statement.period_start),
                               date.fromisoformat(statement.period_end))
            if problems:
                unsound.append(f"{sha[:16]} {problems}")
            postings_published += len(statement.transactions)
            published_by_account.setdefault(
                statement.account_number or "", []).append(statement)
        dispatch = resolve(text)
        key = (str(dispatch.parser_id), dispatch.outcome, tuple(sorted(dispatch.attempted)))
        dispatched[key] = dispatched.get(key, 0) + 1
        outcome = _verdict(markdown, pages)
        verdicts[outcome] = verdicts.get(outcome, 0) + 1
        rows = "" if statement is None else f"  postings={len(statement.transactions)}"
        rival_note = "" if not rivals else f"  ALSO CLAIMED BY {rivals}"
        print(f"{sha[:16]}  claimed={claims}  {outcome:24} {verdict}{rows}{rival_note}")
        packet = _l1_packet(text)
        if packet:
            print(packet)

    print(f"\n{len(shas)} documents: claimed {claimed}, published {published}, "
          f"declined {claimed - published}, no artifact {missing}, "
          f"claimed by another registration {ambiguous}")
    for verdict, count in sorted(tally.items()):
        print(f"  {count:3}  {verdict}")
    # --- the cross-document oracle: consecutive months must join
    joined = pairs = 0
    print()
    for index, (_account, statements) in enumerate(sorted(published_by_account.items()), 1):
        statements.sort(key=lambda s: s.period_start)
        months = [s.period_start[:7] for s in statements]
        print(f"account #{index}: {len(statements)} published, months {months}")
        for first, second in zip(statements, statements[1:]):
            end = date.fromisoformat(first.period_end)
            start = date.fromisoformat(second.period_start)
            if (start - end).days != 1:
                continue
            pairs += 1
            if abs(first.ending_balance - second.beginning_balance) <= 0.005:
                joined += 1
            else:
                print(f"    DISCONTINUITY {first.period_end} -> {second.period_start}")
    print(f"consecutive month pairs {pairs}; pairs whose printed closing balance "
          f"equals the next printed opening {joined}")

    print(f"postings published: {postings_published}")
    print(f"published statements failing a field-sanity property: {len(unsound)}")
    for entry in unsound:
        print(f"    UNSOUND {entry}")
    print("dispatch, as the run's own telemetry would record it:")
    for (parser_id, outcome_name, attempted), count in sorted(dispatched.items()):
        print(f"  {count:3}  parser_id={parser_id} outcome={outcome_name} "
              f"attempted={list(attempted)}")
    print("verdicts:")
    for outcome, count in sorted(verdicts.items()):
        print(f"  {count:3}  {outcome}")
    return 0 if not unsound and joined == pairs else 1


if __name__ == "__main__":
    sys.exit(main())
