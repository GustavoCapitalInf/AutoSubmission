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


#: The registry size the budget is required to hold at (ratified by Ocean,
#: batch 4). Now that the text is prepared once per document, a registration
#: adds its own markers and — if it brings one nobody else has — its own
#: normalization, so a budget measured at today's size says nothing on its own
#: about the size the coverage wave is heading for. The affordability
#: assertion is therefore made against the cost PROJECTED to this many
#: registrations, `worst * 80 / 68`.
#:
#: **That projection is a FLOOR on the cost at 80, not a bound.** It scales by
#: the mean cost of today's registrations, and that mean is diluted by the 32
#: which have no normalization at all: review measured projection/actual at
#: 1.00 for a growth shape resembling today's mix and 0.79 for one where every
#: new registration brings its own normalizer — i.e. the real cost can exceed
#: this projection by a quarter. It is used because it is strictly harsher
#: than asserting at today's 68 and it is honest about direction, not because
#: it predicts. The load-independent clause above is the exact guard for the
#: quadratic class this cell removed; other superlinear growth shapes are not
#: caught by either, and are carried in W3 §DETBUDGET DT9.
PLANNED_REGISTRATIONS = 80

#: The absolute ceiling, unchanged since R-3 risk 7: no document may cost the
#: discovery run a quarter-second of routing before a single parse has run.
SWEEP_BUDGET_SECONDS = 0.25

#: Repetitions the wall-clock reading is taken as the MINIMUM of. Contention
#: on a shared machine can only ever make a sample slower — never faster — so
#: the minimum of several samples is the reading least contaminated by load,
#: and it converges on the cost the discovery run actually pays on a machine
#: doing nothing else. Three cells of the batch-4 wave read this test red on
#: an unmodified base while ten agents shared the machine; a single sample is
#: simply the wrong instrument for an absolute cost contract.
SWEEP_SAMPLES = 5


def _sweep_seconds(markdown: str) -> float:
    """One production detect sweep: what `resolve` costs before any parse.

    `_surviving_claimants` and not a loop of `Registration.detect`, because the
    loop is not a sweep — it prepares the document's text once per
    registration, which is precisely the cost this budget exists to keep out
    of the discovery run, and no caller has done it that way since the
    `PreparedDocument` seam landed.
    """
    import time

    start = time.perf_counter()
    pr._surviving_claimants(markdown)
    return time.perf_counter() - start


def test_the_detect_sweep_prepares_each_document_once(documents, sources):
    """The structural half of the budget, and the load-independent half.

    A sweep's text preparation — `admissible_text`, then each parser's own
    normalization — is a function of the document, not of the registration
    asking. Preparing it per registration made the sweep quadratic in registry
    size in its dominant term: on the largest pinned document that was 68
    `admissible_text` calls (116 ms) and 36 normalizations (77 ms) — four
    fifths of a 242 ms sweep — to produce five distinct strings.

    This states the property directly, in operations rather than milliseconds,
    so it cannot be read differently by a busy machine and a quiet one — the
    wall-clock assertion below is the one that needs an instrument, and this is
    the one that catches the regression.
    """
    registrations = pr.registrations()
    expected = 1 + len({reg.normalize for reg in registrations if reg.normalize})

    for row in documents:
        prepared = pr.prepare(sources[row["path"]])
        for registration in registrations:
            registration.detect_prepared(prepared)
        assert prepared.preparations == expected, (
            f"{row['path']}: {prepared.preparations} text preparations for "
            f"{len(registrations)} registrations; expected {expected}"
        )


def test_the_sweep_entry_points_strip_the_filename_comment_once(sources, monkeypatch):
    """...and that the entry points really are the seam, not just `prepare`.

    `admissible_text` is the one preparation every registration shares
    unconditionally, so counting it counts whether the entry point prepared
    once or sixty-eight times. Both sweeping entry points are checked:
    `resolve`'s, and the one telemetry's near-miss vector runs.
    """
    markdown = next(iter(sources.values()))
    real = pr.admissible_text
    calls: list[int] = []

    def counted(text: str) -> str:
        calls.append(len(text))
        return real(text)

    monkeypatch.setattr(pr, "admissible_text", counted)

    pr._surviving_claimants(markdown)
    assert len(calls) == 1, f"resolve's sweep stripped the comment {len(calls)} times"

    calls.clear()
    pr.detection_report(markdown)
    assert len(calls) == 1, f"the near-miss sweep stripped the comment {len(calls)} times"


def test_detect_sweep_stays_affordable_for_the_discovery_run(sources):
    """RFC risk 7: the full-registry sweep is per-document overhead on 3,506
    discovery documents, so it must stay far below the cost of one parse.

    The ceiling is absolute and unchanged — a quarter-second per document —
    but two things about how it is read have changed, because the reading and
    not the ceiling was what went wrong (batch 4, DETECT-BUDGET):

    * the sweep is timed through the seam production sweeps through, and
    * the reading is the best of `SWEEP_SAMPLES`, which is the estimator that
      survives a shared machine.

    And the assertion is made against the cost projected to
    `PLANNED_REGISTRATIONS` — a FLOOR on the cost at that size, not a bound;
    see the note on the constant.

    **Every document is read the same way the winner is.** The first revision
    of this test picked the worst document from one noisy sample and only then
    applied best-of-N to it, which is the same instrument error one level up:
    review measured that selection finding the true worst 0 times in 7 and
    understating the reading by up to 44%, because a document that got one
    unlucky sample wins a selection it should not and then has that sample
    thrown away. Selection and reading are now the same quantity — the minimum
    of `SWEEP_SAMPLES` — so an unlucky sample can neither win nor mislead. It
    costs `SWEEP_SAMPLES` passes over the corpus instead of one, which is
    seconds against the twenty minutes the corpus-marked slice already takes.
    """
    registrations = pr.registrations()
    worst, worst_doc = 0.0, ""
    for path, markdown in sources.items():
        elapsed = min(_sweep_seconds(markdown) for _ in range(SWEEP_SAMPLES))
        if elapsed > worst:
            worst, worst_doc = elapsed, path

    projected = worst * PLANNED_REGISTRATIONS / len(registrations)

    assert projected < SWEEP_BUDGET_SECONDS, (
        f"slowest full-registry detect sweep was {worst * 1000:.1f} ms over "
        f"{len(registrations)} registrations ({worst_doc}), which projects to "
        f"{projected * 1000:.1f} ms at {PLANNED_REGISTRATIONS} — the budget is "
        f"{SWEEP_BUDGET_SECONDS * 1000:.0f} ms"
    )


def test_detection_is_invariant_to_the_filename_echo(documents, sources):
    """R-4 check 4, over the real corpus: 46 registrations x 109 documents.

    The OCR/native layer prefixes every document with `<!-- SOURCE: <file> -->`.
    That is operator-supplied metadata — trivially wrong, and on the discovery
    archive a folder-derived guess — so the RFC's detect contract admits the
    document, not its name.

    R-4b made this structural: `parser_registry.admissible_text` removes the
    comment centrally, before any parser's own normalization. So the assertion
    is no longer "two known parsers differ" but "stripping it changes nothing
    for anyone" — the strip is already in force, for all 46.
    """
    import re

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

    assert not differing, (
        "detection still reads the filename comment for: "
        f"{ {k: v[:3] for k, v in differing.items()} }"
    )
