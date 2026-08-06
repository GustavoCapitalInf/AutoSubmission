"""Registry dispatch resolves every corpus document exactly as the chain did.

The control R-3 exists to be judged by. `tests/data/parser_expectations.json`
records what the pre-R-3 or-chain did with each of the 109 pinned corpus
documents; these tests replay the same documents through the registry and
compare.

Marked `corpus` (opt-in, like the gate) because it reads the pinned PDFs.
Offline throughout: native text, or the committed OCR artifacts, resolved
exactly as `corpus_gate.py` resolves them.

Closed finding: five parsers used to detect their bank by a bare name
substring that also matched the bank as a *counterparty* in another bank's
statement, leaving 45 documents with two or more claimants. Each now requires
issuer furniture as well — see `docs/moneythumb-replacement/R3_DETECTION_FINDING.md`
and `tests/test_parser_detection_markers.py`. Every assertion below passes.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401  — populates the registry

pytestmark = pytest.mark.corpus

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "Bank Statements"
EXPECTATIONS = ROOT / "tests" / "data" / "parser_expectations.json"
BALANCE_CSV = ROOT / "docs" / "balance-metrics-audit-results.csv"

@pytest.fixture(scope="module")
def documents() -> list[dict]:
    return json.loads(EXPECTATIONS.read_text(encoding="utf-8"))["documents"]


@pytest.fixture(scope="module")
def sources(documents) -> dict[str, str]:
    """Corpus path -> source markdown, resolved offline."""
    from balance_forensic_audit import source_markdown
    from corpus_artifacts import DEFAULT_CACHE

    return {
        row["path"]: source_markdown(CORPUS / Path(row["path"]), ocr_cache=DEFAULT_CACHE)[0]
        for row in documents
    }


def _expected_id(row: dict) -> str:
    """The registration that should claim this document.

    A document the or-chain resolved through a nested sub-dispatch belongs to
    that sub-dispatch's own registration once R-3.3 promoted it.
    """
    return row["variant_id"] or row["parser_id"]


def _claimants(markdown: str) -> list[str]:
    return [reg.id for reg, _detection in pr._surviving_claimants(markdown)]


def test_no_corpus_document_is_left_unclaimed(documents, sources):
    """Every document the chain parsed deterministically still has a claimant."""
    orphans = [row["path"] for row in documents if not _claimants(sources[row["path"]])]
    assert not orphans, f"documents no registration claims: {orphans}"


def test_no_corpus_document_resolves_to_the_wrong_parser(documents, sources):
    """The property a wrong-parser claim would violate.

    Checked independently of the ambiguity finding: where the registry reaches
    a single winner, it must be the recorded one, and where it does not, the
    recorded parser must at least be among the claimants. A recorded parser
    that stopped claiming its own document is a regression regardless of how
    many others also claim it.
    """
    wrong = []
    for row in documents:
        claimants = _claimants(sources[row["path"]])
        expected = _expected_id(row)
        if expected not in claimants:
            wrong.append(f"{row['path']}: expected {expected}, claimants {claimants}")
        elif len(claimants) == 1 and claimants[0] != expected:
            wrong.append(f"{row['path']}: resolved to {claimants[0]}, expected {expected}")
    assert not wrong, "wrong-parser claims:\n  " + "\n  ".join(wrong)


def test_no_corpus_document_is_ambiguous(documents, sources):
    ambiguous = {
        row["path"]: _claimants(sources[row["path"]])
        for row in documents
        if len(_claimants(sources[row["path"]])) > 1
    }
    assert not ambiguous, f"{len(ambiguous)} ambiguous documents: {ambiguous}"


def test_every_corpus_document_resolves_to_the_recorded_parser(documents, sources):
    """The headline parity assertion, in its final form."""
    mismatches = []
    for row in documents:
        dispatch = pr.resolve(sources[row["path"]])
        expected = _expected_id(row)
        if dispatch.outcome != "claimed" or dispatch.parser_id != expected:
            mismatches.append(
                f"{row['path']}: expected {expected}, got {dispatch.outcome}"
                f" {dispatch.parser_id} candidates={dispatch.candidates}"
            )
    assert not mismatches, "parser parity broken:\n  " + "\n  ".join(mismatches)


def test_the_recorded_parser_is_always_the_highest_ranked_claimant(documents, sources):
    """Even while the ambiguity finding is open, the right parser leads.

    A weaker statement than full parity, but it holds today and it is what
    tells us the finding is about over-broad *rivals* rather than about the
    recorded parser having lost confidence in its own document.
    """
    demoted = []
    for row in documents:
        expected = _expected_id(row)
        scored = [
            (reg.id, detection.score)
            for reg, detection in pr._surviving_claimants(sources[row["path"]])
        ]
        best = max(score for _id, score in scored)
        mine = dict(scored).get(expected)
        if mine is None or mine < best:
            demoted.append(f"{row['path']}: {expected} scored {mine}, best was {best}")
    assert not demoted, "recorded parser outscored by a rival:\n  " + "\n  ".join(demoted)


def test_the_three_promoted_sub_dispatches_claim_their_documents(documents, sources):
    """R-3.3's specific control.

    The or-chain hid three decisions inside a parser. Each is now its own
    registration, and the documents the chain resolved through them must now
    resolve to them by name.
    """
    promoted = {"chase_export", "rbc_french", "td_canada_native"}
    rows = [row for row in documents if row["variant_id"]]
    assert {row["variant_id"] for row in rows} == promoted
    assert len(rows) == 8, f"expected 8 sub-dispatch documents, found {len(rows)}"
    for row in rows:
        claimants = _claimants(sources[row["path"]])
        assert row["variant_id"] in claimants, (
            f"{row['path']}: {row['variant_id']} no longer claims it ({claimants})"
        )
        assert row["parser_id"] not in claimants, (
            f"{row['path']}: {row['parser_id']} should have been superseded by "
            f"{row['variant_id']} ({claimants})"
        )


def test_expectations_cover_the_pinned_manifest(documents):
    with BALANCE_CSV.open(encoding="utf-8", newline="") as handle:
        pinned = {row["path"] for row in csv.DictReader(handle)}
    assert {row["path"] for row in documents} == pinned


def test_detect_sweep_stays_affordable_for_the_discovery_run(sources):
    """RFC risk 7: the full-registry sweep is per-document overhead on 3,506
    discovery documents, so it must stay far below the cost of one parse."""
    import time

    registrations = pr.registrations()
    worst = 0.0
    for markdown in sources.values():
        start = time.perf_counter()
        for registration in registrations:
            registration.detect(markdown)
        worst = max(worst, time.perf_counter() - start)
    assert worst < 0.25, f"slowest full-registry detect sweep was {worst * 1000:.1f} ms"


def test_detection_is_invariant_to_the_filename_echo(documents, sources):
    """R-4 check 4, over the real corpus: 46 registrations x 109 documents.

    The OCR/native layer prefixes every document with `<!-- SOURCE: <file> -->`.
    That is operator-supplied metadata — trivially wrong, and on the discovery
    archive a folder-derived guess — so the RFC's detect contract admits the
    document, not its name. Strip the comment and every `Detection` must be
    identical.

    Two registrations differ. They are pinned rather than patched (R-4 reports
    parser defects, it does not fix them): see
    `docs/moneythumb-replacement/R4_CONFORMANCE_FINDINGS.md`.
    """
    import re

    from tests.test_parser_conformance import FILENAME_DEPENDENT_PARSERS

    source_comment = re.compile(r"^<!--\s*SOURCE:.*?-->\s*$", re.MULTILINE | re.IGNORECASE)
    carrying = sum(1 for markdown in sources.values() if source_comment.search(markdown))
    assert carrying == len(sources), (
        "this check is only meaningful if the corpus carries the comment; "
        f"only {carrying}/{len(sources)} do"
    )

    differing: dict[str, list[str]] = {}
    for row in documents:
        markdown = sources[row["path"]]
        stripped = source_comment.sub("", markdown)
        for registration in pr.registrations():
            if registration.detect(markdown) != registration.detect(stripped):
                differing.setdefault(registration.id, []).append(row["path"])

    assert set(differing) == FILENAME_DEPENDENT_PARSERS, (
        "the set of filename-dependent parsers changed: "
        f"{ {k: v for k, v in differing.items()} }"
    )
