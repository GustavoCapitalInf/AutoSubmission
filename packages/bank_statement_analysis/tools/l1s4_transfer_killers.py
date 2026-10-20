"""l1s4_transfer_killers.py — R-d's killer set, run against the PRODUCTION rule.

    python -m tools.l1s4_transfer_killers --census-dir <census> --data-dir <cold cache>

The design measured the internal-transfer population and priced the rule on it:
**7 documents, 47 candidate pairs, 43 carrying a printed INTERNAL-MOVEMENT
designation on at least one leg and 4 not** — 3 admitted only by the
peer-to-peer vocabulary this rule refuses, and 1 with nothing printed at all
(`L1_INDEPENDENT_ACCOUNT_DESIGN.md` §3.2, `tools/l1_design_transfer_probe.py`).
That was a measurement of the DESIGN's rule by the design's own instrument.

This runs the same population, from the same reconstruction, through the code
that actually ships:

* `analysis.pipeline.identify_internal_transfers` — R-d's four clauses, whole;
* `analysis.transaction_classifier.prints_internal_transfer_designation` — the
  fourth clause's vocabulary, `_INTERNAL_TRANSFER_CREDIT_PATTERNS` alone.

and asserts the production rule reproduces the measured split. A gap between the
two is a finding either way: the design's number is wrong, or the implementation
is, and the run says which pairs moved.

**The ambiguity branch has NO archive instance** — the design measured 0
postings with two or more admissible counterparts — so its killer is a
CONSTRUCTED fixture and is named as one. It is built here as well as in
`tests/test_l1s4_transfers.py`, because the archive half of this instrument
cannot exercise a branch the archive does not print.

Read-only over the run of record and the cold cache. Prints shas, counts and
class names; never a description, an amount or a date.

NOT in `corpus_gate.py`'s caller register, deliberately: it calls no analysis
path at all — it reconstructs its ledgers with the design's own prototype and
hands them to one production function. The register is for modules that call
the analysis, and its guard refuses a stale declaration as firmly as a missing
one, so registering this file would turn that guard red.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import l1_design_transfer_probe as probe  # noqa: E402
from tools import l1_split_prototype as proto  # noqa: E402
from tools.cohort_replay import ColdCache  # noqa: E402
from tools.l1_census import load_census  # noqa: E402

#: What the design measured, and therefore what this run must reproduce.
EXPECTED_DOCUMENTS = 7
EXPECTED_PAIRS = 47
EXPECTED_DESIGNATED = 43
EXPECTED_REFUSED = 4


def _account(postings) -> SimpleNamespace:
    """A stand-in carrying exactly what the production rule reads: one
    account's transaction list. Nothing else of a `Report` is touched by
    `identify_internal_transfers`, and building a whole one here would be
    building a fixture rather than exercising the rule."""
    from analysis.schema import Statement, Transaction

    return SimpleNamespace(statement=Statement(transactions=[
        Transaction(
            date=iso,
            description=text or "",
            amount=amount,
            direction="credit" if amount > 0 else "debit",
        )
        for iso, amount, text in postings
    ]))


def _ledgers_for(sha16: str, group: str, band: str, markdown: str, pages: int):
    """The document's live ledgers as `(iso, amount, printed text)` triples.

    The reconstruction is the design prototype's own, and the printed text is
    recovered the way `l1_design_transfer_probe` recovers it — by correlating
    each section's accepted postings with the walk that produced them. A
    section whose text cannot be recovered UNIQUELY contributes postings with
    no description, which can only make a pair fail the designation clause; the
    count is reported so a silent loss cannot be mistaken for a refusal.
    """
    capture = probe.WalkCapture()
    with capture:
        document = proto.run_document(sha16, group, band, markdown, pages)
    live = [section for section in document.sections if section.postings]
    if len(live) < 2:
        return [], 0
    ledgers = []
    without_text = 0
    for section in live:
        texts = probe._descriptions_for(section, capture.walks)
        if texts is None:
            without_text += len(section.postings)
        ledgers.append([
            (iso, amount, texts[offset] if texts is not None else None)
            for offset, (iso, amount) in enumerate(section.postings)
        ])
    return ledgers, without_text


def _constructed_ambiguous_pair() -> tuple[int, list[str]]:
    """The branch the archive does not print: TWO admissible counterparts.

    One credit in account A, and TWO sibling debits of the same date and the
    same magnitude in account B — so which sibling row the credit came from is
    not established. Both printed legs carry an internal designation, which is
    the point: the refusal is about the PAIRING and not about the evidence, so
    a fixture whose legs printed nothing would prove the wrong thing.
    """
    from analysis.pipeline import identify_internal_transfers

    credit = [("2026-04-02", 250.0, "Deposit Transfer From Savings")]
    debits = [
        ("2026-04-02", -250.0, "Withdrawal Transfer From Checking"),
        ("2026-04-02", -250.0, "Withdrawal Transfer From Checking"),
    ]
    transfers, notes = identify_internal_transfers(
        [_account(credit), _account(debits)]
    )
    return len(transfers), notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    from analysis.pipeline import identify_internal_transfers
    from analysis.transaction_classifier import prints_internal_transfer_designation

    groups, opportunities, per_sha = load_census(args.census_dir)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(args.data_dir)

    rows: list[tuple[str, int, int, int, int, list[str]]] = []
    total_candidates = total_flagged = total_no_text = 0
    for band, group, sha16 in proto._population(groups, opportunities):
        markdown, pages = cache.text(sha_by16[sha16])
        if markdown is None:
            continue
        ledgers, without_text = _ledgers_for(sha16, group, band, markdown, len(pages))
        if not ledgers:
            continue
        # The CANDIDATE population is the design's own arithmetic pairing, so
        # this instrument compares like with like: every pair the design counted
        # is offered to the production rule, and the rule's refusals are what
        # the split measures.
        postings = [probe.Posting(ledger=ordinal, index=index, date=iso,
                                  amount=amount, description=text)
                    for ordinal, ledger in enumerate(ledgers)
                    for index, (iso, amount, text) in enumerate(
                        ledger, start=sum(len(l) for l in ledgers[:ordinal]))]
        by_ledger: list[list[probe.Posting]] = [[] for _ in ledgers]
        for posting in postings:
            by_ledger[posting.ledger].append(posting)
        candidates = probe.pair_greedy(by_ledger)
        if not candidates:
            continue
        designated = sum(
            1 for left, right in candidates
            if any(prints_internal_transfer_designation(text)
                   for text in (left.description, right.description) if text)
        )
        flagged, notes = identify_internal_transfers(
            [_account(ledger) for ledger in ledgers]
        )
        rows.append((sha16, len(candidates), designated, len(flagged),
                     without_text, notes))
        total_candidates += len(candidates)
        total_flagged += len(flagged)
        total_no_text += without_text

    print("# L1-S4 — the 47-pair transfer killer set, against the PRODUCTION rule\n")
    print("| document | candidate pairs | designated (vocabulary) | FLAGGED by the rule | postings with no recovered text | document notes |")
    print("|---|---:|---:|---:|---:|---|")
    for sha16, candidates, designated, flagged, no_text, notes in sorted(rows):
        print(f"| `{sha16}` | {candidates} | {designated} | {flagged} | {no_text} | "
              f"{', '.join(notes) if notes else '—'} |")
    documents = len(rows)
    refused = total_candidates - total_flagged
    print(f"\n* documents carrying candidate pairs: **{documents}** "
          f"(design: {EXPECTED_DOCUMENTS})")
    print(f"* candidate pairs: **{total_candidates}** (design: {EXPECTED_PAIRS})")
    print(f"* FLAGGED internal by the production rule: **{total_flagged}** "
          f"(design: {EXPECTED_DESIGNATED})")
    print(f"* REFUSED — no printed internal designation on either leg: "
          f"**{refused}** (design: {EXPECTED_REFUSED})")
    print(f"* postings whose printed text could not be recovered uniquely: {total_no_text}")

    ambiguous_flagged, ambiguous_notes = _constructed_ambiguous_pair()
    ok_ambiguous = ambiguous_flagged == 0 and "ambiguous_internal_transfer" in ambiguous_notes
    print(f"\n* the CONSTRUCTED ambiguous pair (0 in the archive): "
          f"flagged {ambiguous_flagged}, notes {ambiguous_notes} — "
          f"{'REFUSED as required' if ok_ambiguous else 'NOT REFUSED'}")

    agrees = (documents == EXPECTED_DOCUMENTS
              and total_candidates == EXPECTED_PAIRS
              and total_flagged == EXPECTED_DESIGNATED
              and refused == EXPECTED_REFUSED)
    print(f"\nDOCUMENTS={documents} PAIRS={total_candidates} "
          f"FLAGGED={total_flagged} REFUSED={refused} "
          f"AMBIGUOUS_FIXTURE_REFUSED={ok_ambiguous} AGREES_WITH_THE_DESIGN={agrees}")
    return 0 if agrees and ok_ambiguous else 1


if __name__ == "__main__":
    raise SystemExit(main())
