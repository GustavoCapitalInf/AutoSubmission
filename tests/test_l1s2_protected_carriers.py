"""The 15 protected carriers, pinned against a silent demotion at S3.

Gustavo's Q10 ruling (`BATCH9_TRANSITION.md` §8.7): SURFACE THE OMISSION, DO NOT
DEMOTE. L-1 stage 2 surfaces a sibling omission on 15 batch-8 `validated`
documents. §1.5 of the design would, read carelessly, fold every one of them to
`review` when S3 lands the document outcome — which is exactly what the ruling
forbids, and exactly the kind of movement that is easy to ship by accident and
hard to notice afterwards, because each of the 15 would still LOOK read.

So the coverage is pinned here, on the real documents, from the run of record's
own cached text:

* every one of the 15 publishes;
* every one carries at least one omission, and every omission names a ratified
  L1-C17 class — a record whose reason fell outside the vocabulary would have
  raised where it was built, so this asserts the vocabulary end to end;
* every one's ACCOUNT outcome, through the unchanged `classify_outcome`, is
  `validated`;
* every one's DOCUMENT outcome, through
  `tests/test_l1s2_document_outcome.py::document_outcome`, is `validated`;
* every one's published account block is byte-identical to the payload the run
  of record stored — so nothing crossed the boundary from the omitted sibling.

**The document leg is the one a fold walks through, and it is why that resolver
exists.** The first version of this file asserted the account leg and left the
other to a docstring — "when `classify_document` lands, add its verdict" — and
the independent re-review showed a `classify_document` demoting all 15 while
every assertion here stayed green. `document_outcome` resolves the document's
verdict through whatever this tree exposes: a declared fold if one exists (found
by scanning `analysis/` and `telemetry/`, not by a hard-coded name), the
published account otherwise. So the assertion below starts reading S3's fold on
the day it lands, with nobody remembering to extend anything, and
`tests/test_l1s2_document_outcome.py`'s tripwire fails if a fold is declared that
the resolver cannot reach.

FAIL CLOSED, never vacuously. The population is asserted to be exactly 15 when
the archive is present, and the whole module SKIPS with a stated reason only
when the cold cache or the run of record cannot be found — a git worktree does
not carry either, so this walks the checkout's ancestors, which is the same
idiom `tests/test_rbc_variants.py` uses for the OCR store. Run it from the repo
tree or from a worktree beneath `.claude/worktrees/`.

Content shas only. No printed value, name, amount or date is read out of this
test or reported by it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

#: The 15 documents L-1 stage 2 surfaces an omission on, by content sha16, as
#: measured by `tools/l1s2_admission_probe.py` at the branch tip. Prefixes and
#: not whole shas because that is how the record names them everywhere else;
#: they are resolved against the run of record below and the resolution is
#: asserted to be total.
CARRIERS: tuple[str, ...] = (
    # symitar — 4 with a printed dormancy declaration, 3 yield-only
    "0A14AC169DEA62D4", "21643A62A463EA39", "3600FE7830C4A484", "9C5B7D628D7511EE",
    "A4D0F58E054F8CFA", "C067BE96F6B0BE0F", "E07F381DC420725A",
    # community_section — printed zero-activity summary
    "31F347BE1494314F", "59DA140E7579A851", "5F1CC8C0198DB4EB", "C6E5B0D3EA9F857B",
    "F627D7A6A057EF35",
    # dakota_west — printed zero-activity summary (one of the two is PINNED)
    "037774298FE1CD66", "F748A799FDC7F25E",
    # zions — printed dormancy declaration, the other ratified wording
    "1019F3C638AB1C81",
)

#: The pinned corpus document among them, named so a reviewer can see that the
#: truth set is inside this proof rather than beside it.
PINNED_CARRIER = "F748A799FDC7F25E"

COLD_CACHE = (".claude", "recovery", "webapp_data_train8_cold")
RUN_POINTER = ("discovery_reports", "train8-logs", "train8_run_dir.txt")


def _checkout_ancestor(*relative: str) -> Path | None:
    """The nearest enclosing directory that holds `relative`, or None.

    A git worktree does not carry the gitignored recovery cache or the discovery
    reports; the checkout it was created from does. Searching upwards is what
    lets this proof run from either.
    """
    root = Path(__file__).resolve().parents[1]
    for base in (root, *root.parents):
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


def _archive() -> tuple[Path, Path]:
    cache = _checkout_ancestor(*COLD_CACHE)
    pointer = _checkout_ancestor(*RUN_POINTER)
    if cache is None or pointer is None:
        pytest.skip(
            "the batch-8 cold cache and the run-of-record pointer were not "
            "found in this checkout or any ancestor; this proof replays real "
            "documents and has nothing to read. Run it from the repository "
            "tree or from a worktree beneath .claude/worktrees/."
        )
    run = pointer.parent.parent.parent / pointer.read_text(encoding="utf-8").strip()
    if not run.exists():
        pytest.skip(f"the run of record named by {pointer.name} is not present")
    return cache, run


@pytest.mark.corpus
def test_the_fifteen_carriers_surface_their_omission_and_stay_validated():
    """Q10, on the protected documents themselves.

    One test rather than fifteen parametrised ones because the analysis is the
    expensive half and the population assertion is part of the proof: a run that
    resolved fourteen would be a proof that had quietly stopped covering one.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from analysis.pipeline import analyze_document
    from analysis.serialization import report_to_dict
    from analysis.sibling_omission import EVIDENCE_CLASSES
    from telemetry.record import classify_outcome
    from tests.test_l1s2_document_outcome import document_outcome
    from tools.cohort_replay import ColdCache, leaf_diff, load_baseline_rows

    cache_dir, run = _archive()
    rows = load_baseline_rows(run)
    # P20-ARTIFACTS (Phase 2.0): `ColdCache` now resolves through
    # `telemetry.run_of_record`'s one selection policy and needs the run
    # directory its partitions come from, and `text()` needs each document's
    # own row (`source_path` / `visual_rung`) rather than an internal
    # preference order — the batch-8 archive has one OCR partition regardless,
    # so this is a mechanical adoption of the new signature, not a behavior
    # change for this population.
    cache = ColdCache(cache_dir, run)

    wanted = {prefix.upper() for prefix in CARRIERS}
    resolved = {sha[:16].upper(): sha for sha in rows if sha[:16].upper() in wanted}
    assert set(resolved) == wanted, (
        "the run of record does not carry every named carrier: missing "
        f"{sorted(wanted - set(resolved))}"
    )
    assert len(resolved) == 15, f"expected exactly 15 carriers, resolved {len(resolved)}"
    assert PINNED_CARRIER in resolved, "the pinned corpus carrier is not in the population"

    failures: list[str] = []
    for prefix in sorted(resolved):
        sha = resolved[prefix]
        markdown, pages = cache.text(sha, rows[sha])
        if markdown is None:
            failures.append(f"{prefix}: no cached text — this proof may not skip a document")
            continue
        try:
            document = analyze_document(markdown, parse_mode="deterministic", sheets=pages)
        except Exception as exc:  # a refusal is a demotion by another name
            failures.append(f"{prefix}: no longer published ({type(exc).__name__})")
            continue

        reasons = [record.reason for record in document.omissions]
        if not reasons:
            failures.append(f"{prefix}: publishes with NO omission recorded")
        for reason in reasons:
            if reason not in EVIDENCE_CLASSES:
                failures.append(f"{prefix}: omission reason {reason!r} is not a ratified class")

        account = report_to_dict(document.accounts[0])
        outcome = tuple(classify_outcome(account))
        if outcome[0] != "validated":
            failures.append(f"{prefix}: account outcome is {outcome[0]!r}, not 'validated'")
        # The other leg, and the one a document-level fold walks through. Q10
        # says a surfaced omission does not demote the document either.
        folded = document_outcome(document)
        if folded[0] != "validated":
            failures.append(
                f"{prefix}: DOCUMENT outcome is {folded[0]!r} ({folded[1]!r}), not "
                f"'validated' — Q10 (BATCH9_TRANSITION §8.7) forbids demoting a "
                f"protected carrier for surfacing its omission"
            )

        baseline = cache.baseline_payload(markdown, pages)
        if baseline is None:
            failures.append(f"{prefix}: the run of record stored no payload to compare")
            continue
        # `tools/cohort_replay.py::replay_one`'s normalisation, and for its
        # reason: the cache stores canonical JSON and `report_to_dict` returns
        # tuples where the stored payload holds lists.
        published = json.loads(json.dumps(account, sort_keys=True, default=str))
        moved = leaf_diff(baseline, published)
        if moved:
            failures.append(f"{prefix}: account block moved at {sorted(moved)}")

    assert not failures, "Q10 is violated on:\n  " + "\n  ".join(failures)
