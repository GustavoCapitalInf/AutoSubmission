"""L1-ARCH-DESIGN instrument 1 — READ-ONLY payload-shape probe.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**
It exists to MEASURE one design claim and to be deleted by whoever implements
the design: *does a `DocumentStatement` wrapper leave every single-account
payload byte-identical, and what does each rejected wrapper shape cost?*

The claim cannot be argued. `analysis/serialization.py::report_to_dict` is the
one JSON contract for the CLI, the web app, the downloads and package
aggregation, and `telemetry/record.py::classify_outcome` reads that dict to put
a document on the ladder. A publication-model change that adds one key to it
changes every payload in the archive; a change that adds none changes nothing.
Which of those two a wrapper is, is a measurement, so this file measures it.

METHOD
------
For every document in the cohort: the run of record's own cached OCR text is
read (READ-ONLY), `analysis.pipeline.analyze_markdown(parse_mode=
"deterministic")` is called exactly as `tools/cohort_replay.py` calls it, and
the resulting `Report` is serialised SEVEN ways from the SAME in-memory object,
so nothing in the comparison can move except the shape under test:

  `baseline`
      `report_to_dict(report)` — today's payload, the control.
  `wrapper_conditional` (the design's RULE S)
      the report is placed in a prototype `DocumentReport` carrying
      `accounts=[report]`, and the document serialiser emits, for a document
      whose account list has exactly one member and which omitted nothing and
      read no roll-up, `report_to_dict(accounts[0])` and NOTHING ELSE — no
      wrapper key, no marker, no empty list.
  `wrapper_unconditional`
      the same wrapper emitting `accounts` and `document` on EVERY document,
      which is the shape a reader reaches for first.
  `omission_field_always`
      SIBLING-OMISSION-SURFACE as a plain `Statement` field
      (`unpublished_sibling_sections: list = []`) — i.e. a field that pydantic
      dumps on every document whether or not anything was omitted.
  `omission_field_elided`
      the same field, elided from the payload when it is empty.
  `integrity_split_order_preserved` / `integrity_split_naive_order` /
  `integrity_split_dropped`
      the review's MAJOR-2. RULE S's byte-identity is a property of the
      SERIALISER; the risk it is offered against lives one layer up, in the
      `assess_document_integrity` scope split the design prescribes. These
      three are the same split assembled three ways — the safe one, the one an
      implementer writes first (the two scopes concatenated, which is identical
      as a SET and different as the LIST the corpus gate pins), and the one the
      design's prose reads as literally (the document-scope flags MOVE, so the
      account payload stops carrying them).

Each variant is compared with the baseline as CANONICAL JSON BYTES
(`json.dumps(..., sort_keys=True)`), and `classify_outcome` is run on the
baseline and on each variant that still carries a top-level `statement`, so the
probe reports whether the ladder moved as well as whether the bytes did.

WHAT IT DOES NOT CLAIM
----------------------
Byte-identity here is a statement about the SERIALISER, measured over the
cohort named in the output — not a substitute for the archive sweep, which is
what proves it over the whole archive at an implementation tree. This probe
runs no parser it wrote, publishes no second account, and touches no
production file: it only re-serialises what production already produced.

PRIVACY
-------
Nothing printed by this instrument comes from a document's content. It prints
content sha16s, registration ids, counts, and CHANGED LEAF PATHS (key names,
list indices collapsed to `[*]`) — never a value, name, number, amount or date.
The leaf-path projection is `tools.cohort_replay.leaf_diff`, which is the
projection the coverage cells already report under.

Usage:

    python -m tools.l1_design_payload_probe --run <run dir> --data-dir <cold cache> \
        [--per-parser N] [--shas <file>] [--json <private>.json] [--limit N]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cohort_replay import ColdCache, leaf_diff, load_baseline_rows  # noqa: E402


# ---------------------------------------------------------------------------
# the prototype document model
# ---------------------------------------------------------------------------
#
# This is the design's data model expressed in the smallest form that can be
# MEASURED. It deliberately does not subclass, patch or import anything from
# `analysis/schema.py`: the whole point of RULE S is that the single-account
# path is the untouched one, and a prototype that reached into the schema could
# not demonstrate that.


@dataclass
class SiblingOmission:
    """A printed deposit section that was established and NOT published.

    `label` is the section's own printed identity token as the boundary layer
    resolved it; the probe never fills it, because a real one would be document
    content and this instrument publishes none.
    """

    reason: str
    posting_count: int
    label: str | None = None


@dataclass
class RollupOracle:
    """The printed enumerating table, kept as EVIDENCE rather than as a value."""

    caption_class: str
    column_roles_printed: bool
    rows: int
    cross_account_total_printed: bool


@dataclass
class DocumentReport:
    """The wrapper: N account reports plus the document's own printed facts."""

    accounts: list = field(default_factory=list)
    document_period: tuple[str, str] | None = None
    rollup: RollupOracle | None = None
    omissions: list[SiblingOmission] = field(default_factory=list)
    boundary_mechanism: str | None = None


def _single_account_document(doc: DocumentReport) -> bool:
    """RULE S — the exact condition under which the payload is today's payload.

    All four clauses, because each one is a way the document could carry a fact
    the single-account payload has nowhere to put:

      * one account — more than one and the payload must publish a list;
      * nothing omitted — an omission is a published gap and must be visible;
      * no roll-up read — a roll-up that was READ is document-level evidence;
      * no document-level partition mechanism recorded, for the same reason.

    A document failing any clause takes the document shape. A document meeting
    all four is, by construction, a document about which the new model learned
    nothing the old payload could not say — so it says it the old way.
    """
    return (
        len(doc.accounts) == 1
        and not doc.omissions
        and doc.rollup is None
        and doc.boundary_mechanism is None
    )


def document_to_payload_conditional(doc: DocumentReport, to_dict) -> dict:
    """RULE S. Single-account documents get today's dict, unchanged."""
    if _single_account_document(doc):
        return to_dict(doc.accounts[0])
    return _document_shape(doc, to_dict)


def document_to_payload_unconditional(doc: DocumentReport, to_dict) -> dict:
    """The shape a reader reaches for first: the wrapper on every document."""
    return _document_shape(doc, to_dict)


def _document_shape(doc: DocumentReport, to_dict) -> dict:
    """The multi-account payload.

    There is deliberately NO top-level `statement` key. A consumer that reads
    `payload["statement"]` on a multi-account document would read ONE account
    and call it the document — which is the L-1 defect itself, moved from the
    parser into the payload. Its absence is what makes such a consumer fail
    rather than answer.
    """
    return {
        "document": {
            "period_start": doc.document_period[0] if doc.document_period else None,
            "period_end": doc.document_period[1] if doc.document_period else None,
            "boundary_mechanism": doc.boundary_mechanism,
            "account_count": len(doc.accounts),
            "rollup": (
                {
                    "caption_class": doc.rollup.caption_class,
                    "column_roles_printed": doc.rollup.column_roles_printed,
                    "rows": doc.rollup.rows,
                    "cross_account_total_printed": doc.rollup.cross_account_total_printed,
                }
                if doc.rollup is not None
                else None
            ),
            "omitted_sections": [
                {"label": o.label, "reason": o.reason, "posting_count": o.posting_count}
                for o in doc.omissions
            ],
        },
        "accounts": [to_dict(report) for report in doc.accounts],
    }


# ---------------------------------------------------------------------------
# the two SIBLING-OMISSION-SURFACE variants
# ---------------------------------------------------------------------------

VARIANTS = ("wrapper_conditional", "wrapper_unconditional",
            "omission_field_always", "omission_field_elided",
            "integrity_split_order_preserved",
            "integrity_split_naive_order",
            "integrity_split_dropped")

OMISSION_KEY = "unpublished_sibling_sections"

# ---------------------------------------------------------------------------
# the `assess_document_integrity` SCOPE SPLIT (the review's MAJOR-2)
# ---------------------------------------------------------------------------
#
# RULE S's byte-identity is a statement about the SERIALISER, and the review was
# right that the risk it is offered against lives one layer up: the design has
# `assess_document_integrity` (`analysis/pipeline.py`:260-512) SPLIT BY SCOPE,
# with some flags moving to the document block and the rest staying per account.
# On a single-account document those flags must land in exactly the payload keys
# they land in today — and that is a property of the pipeline change, not of the
# serialiser.
#
# It is measurable here without touching production: partition the integrity
# block the way the design says to, then re-assemble it under RULE S, and
# compare. Three assemblies are measured because two of them are the ones an
# implementer would write first and both are wrong in a way no test would name.

#: Flags whose SCOPE is the document, not one account
#: (`pipeline.py`:345-358, :388-395, :400, :481).
DOCUMENT_SCOPE_FLAGS: frozenset[str] = frozenset({
    "parser_ambiguous",
    "parser_exception",
    "repair_exception",
    "integrity_check_exception",
    "missing_declared_statement_page",
})


def _split_integrity(integrity: dict) -> tuple[list, list]:
    """(document-scope flags, account-scope flags), each in PUBLISHED order."""
    flags = list(integrity.get("flags") or [])
    document = [f for f in flags if f in DOCUMENT_SCOPE_FLAGS]
    account = [f for f in flags if f not in DOCUMENT_SCOPE_FLAGS]
    return document, account


def integrity_split_order_preserved(payload: dict) -> dict:
    """The SAFE assembly: split by scope, and re-assemble in PUBLISHED order.

    RULE S says a single-account document publishes today's payload, so the
    account's integrity block must be re-assembled as the original list, not as
    a concatenation of the two scopes.
    """
    out = json.loads(json.dumps(payload, sort_keys=True, default=str))
    integrity = out.get("integrity") or {}
    document, account = _split_integrity(integrity)
    original = list(integrity.get("flags") or [])
    rebuilt = [f for f in original if f in set(document) | set(account)]
    integrity["flags"] = rebuilt
    return out


def integrity_split_naive_order(payload: dict) -> dict:
    """The assembly an implementer writes first: the two scopes concatenated,
    document-scope leading. Identical as a SET, different as a LIST — and
    `corpus_gate.py`:1360-1362 pins the flag tuple in "Published ORDER, not
    sorted"."""
    out = json.loads(json.dumps(payload, sort_keys=True, default=str))
    integrity = out.get("integrity") or {}
    document, account = _split_integrity(integrity)
    integrity["flags"] = document + account
    return out


def integrity_split_dropped(payload: dict) -> dict:
    """The assembly that follows the design's prose literally: the
    document-scope flags MOVE to the document block, so a single-account
    document's account payload no longer carries them."""
    out = json.loads(json.dumps(payload, sort_keys=True, default=str))
    integrity = out.get("integrity") or {}
    _document, account = _split_integrity(integrity)
    integrity["flags"] = account
    return out


def omission_field_always(payload: dict, omissions: list[SiblingOmission]) -> dict:
    """A plain `Statement` field: pydantic dumps it whether or not it is empty."""
    out = json.loads(json.dumps(payload, sort_keys=True, default=str))
    out["statement"][OMISSION_KEY] = [
        {"label": o.label, "reason": o.reason, "posting_count": o.posting_count}
        for o in omissions
    ]
    return out


def omission_field_elided(payload: dict, omissions: list[SiblingOmission]) -> dict:
    """The same field, elided from the payload when nothing was omitted."""
    out = json.loads(json.dumps(payload, sort_keys=True, default=str))
    if omissions:
        out["statement"][OMISSION_KEY] = [
            {"label": o.label, "reason": o.reason, "posting_count": o.posting_count}
            for o in omissions
        ]
    return out


# ---------------------------------------------------------------------------
# the document outcome function under test
# ---------------------------------------------------------------------------

LADDER = ("failed", "withheld", "review", "validated")


def classify_document(payload: dict, classify) -> tuple[str, str]:
    """The proposed document outcome: the WEAKEST account, fail-closed.

    A single-account payload never reaches the second branch, which is the
    whole point: today's function is today's answer on every document that has
    one account, by construction rather than by measurement.
    """
    if "accounts" not in payload:
        return classify(payload)
    accounts = payload.get("accounts") or []
    if not accounts:
        # A document shape with no account is a defect in the publisher, not a
        # document: it fails rather than being scored on an empty minimum.
        return "failed", "document_publishes_no_account"
    per = [classify(account) for account in accounts]
    for klass, _reason in per:
        if klass not in LADDER:
            # The review's MINOR-11. Ranking an unranked class LOWEST (`-1`)
            # would make it the document's class, and `discovery/compare.py::
            # direction` scores an unranked class as neither an improvement nor
            # a regression — i.e. invisible to the whole non-regression regime.
            # Unreachable today (per-account `classify_outcome` is called
            # without `deferred=`), and a refusal rather than a rank is what an
            # unreachable state should get.
            raise ValueError(
                f"account outcome {klass!r} is not on the ladder; a document "
                f"fold over an unranked class would be invisible to the "
                f"non-regression regime")
    weakest = min(per, key=lambda pair: LADDER.index(pair[0]))
    if weakest[0] == "validated":
        omitted = ((payload.get("document") or {}).get("omitted_sections")) or []
        if omitted:
            # An omission is a published gap. It may only stand on the ratified
            # evidence, and the reason token is what says which rule admitted
            # it; anything else refuses to be called validated.
            return "review", "sibling_section_omitted"
        return "validated", "approved"
    return weakest[0], f"account_{weakest[1]}"


# ---------------------------------------------------------------------------
# cohort
# ---------------------------------------------------------------------------


def select_cohort(rows: dict[str, dict], per_parser: int, shas_file: Path | None,
                  limit: int | None, include_unvalidated: bool = False) -> list[str]:
    """A deterministic cohort: the first `per_parser` VALIDATED documents of
    every registration in the run, so the claim is made about every reader the
    archive has rather than about a convenient family.

    `include_unvalidated` adds the registrations that claim documents but hold
    NO validated one — the review's extension. Those documents are where
    `report_to_dict` takes its OTHER branches: `ending_balance` nulled
    (`serialization.py`:146-151) and the ADB block emptied by `_metrics_dict`
    (:102-133). A byte-identity claim that never exercised them would be a
    claim about the happy path.
    """
    chosen: list[str] = []
    if shas_file is not None:
        for line in shas_file.read_text(encoding="utf-8").splitlines():
            token = line.strip().upper()
            if token and not token.startswith("#"):
                chosen.append(token)
    if per_parser:
        by_parser: dict[str, list[str]] = collections.defaultdict(list)
        for sha in sorted(rows):
            row = rows[sha]
            if (row.get("outcome_class") or "") != "validated":
                continue
            parser = (row.get("parser_id") or "").strip()
            if not parser:
                continue
            if len(by_parser[parser]) < per_parser:
                by_parser[parser].append(sha)
        if include_unvalidated:
            unvalidated: dict[str, list[str]] = collections.defaultdict(list)
            for sha in sorted(rows):
                row = rows[sha]
                parser = (row.get("parser_id") or "").strip()
                if not parser or parser in by_parser:
                    continue
                if len(unvalidated[parser]) < per_parser:
                    unvalidated[parser].append(sha)
            for parser in sorted(unvalidated):
                by_parser[parser] = unvalidated[parser]
        for parser in sorted(by_parser):
            chosen.extend(by_parser[parser])
    seen: set[str] = set()
    cohort = [sha for sha in chosen if not (sha in seen or seen.add(sha))]
    return cohort[:limit] if limit else cohort


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def canonical(payload: dict | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)


@dataclass
class DocProbe:
    sha16: str
    parser_id: str
    analysed: bool = False
    error: str | None = None
    baseline_class: str | None = None
    variants: dict[str, bool] = field(default_factory=dict)
    #: the SAME comparison made the way the coverage cells make it — the leaf
    #: projection `tools/cohort_replay.py` reports "payload identical" from.
    #: Measured separately because the two do not always agree (see the
    #: "blind spot" table in the output).
    leaf_same: dict[str, bool] = field(default_factory=dict)
    variant_class: dict[str, str] = field(default_factory=dict)
    paths: dict[str, list[str]] = field(default_factory=dict)


def probe_one(sha: str, parser_id: str, cache: ColdCache) -> DocProbe:
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from telemetry.record import classify_outcome

    probe = DocProbe(sha16=sha[:16], parser_id=parser_id)
    markdown, pages = cache.text(sha)
    if markdown is None:
        probe.error = "no-cached-text"
        return probe
    try:
        report = analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
    except Exception as exc:  # the runner's own boundary: a refusal is data
        probe.error = type(exc).__name__
        return probe
    probe.analysed = True

    baseline = json.loads(json.dumps(report_to_dict(report), sort_keys=True, default=str))
    probe.baseline_class = classify_outcome(baseline)[0]
    reference = canonical(baseline)

    doc = DocumentReport(accounts=[report])
    candidates: dict[str, dict] = {
        "wrapper_conditional": json.loads(json.dumps(
            document_to_payload_conditional(doc, report_to_dict), sort_keys=True, default=str)),
        "wrapper_unconditional": json.loads(json.dumps(
            document_to_payload_unconditional(doc, report_to_dict), sort_keys=True, default=str)),
        "omission_field_always": omission_field_always(baseline, []),
        "omission_field_elided": omission_field_elided(baseline, []),
        "integrity_split_order_preserved": integrity_split_order_preserved(baseline),
        "integrity_split_naive_order": integrity_split_naive_order(baseline),
        "integrity_split_dropped": integrity_split_dropped(baseline),
    }
    for name, payload in candidates.items():
        probe.variants[name] = canonical(payload) == reference
        changed = leaf_diff(baseline, payload)
        probe.leaf_same[name] = not changed
        probe.variant_class[name] = classify_document(payload, classify_outcome)[0]
        if not probe.variants[name]:
            probe.paths[name] = sorted(changed)[:12]
    return probe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 design payload-shape probe")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--per-parser", type=int, default=2)
    parser.add_argument("--shas", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--include-unvalidated", action="store_true",
                        help="also cover registrations holding no validated document")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    rows = load_baseline_rows(args.run)
    cohort = select_cohort(rows, args.per_parser, args.shas, args.limit,
                           include_unvalidated=args.include_unvalidated)
    cache = ColdCache(args.data_dir)

    probes = [probe_one(sha, (rows.get(sha, {}).get("parser_id") or ""), cache)
              for sha in cohort]
    analysed = [p for p in probes if p.analysed]
    registrations = sorted({p.parser_id for p in analysed if p.parser_id})

    print("# L1-ARCH-DESIGN — payload-shape probe")
    print()
    print(f"Cohort: the first {args.per_parser} VALIDATED document(s) of every "
          f"registration in the run of record. Each document is analysed ONCE "
          f"and serialised four ways from the same `Report`.")
    print()
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents in the cohort | {len(cohort)} |")
    print(f"| ... analysed (a `Report` was produced) | {len(analysed)} |")
    print(f"| ... refused or with no cached text | {len(probes) - len(analysed)} |")
    print(f"| distinct registrations covered | {len(registrations)} |")
    print(f"| ... of them classified `validated` at baseline | "
          f"{len({p.parser_id for p in analysed if p.baseline_class == 'validated'})} |")
    print()

    print("## Does the payload move?")
    print()
    print("| variant | payload byte-identical | payload differs | ladder unchanged |")
    print("|---|---:|---:|---:|")
    for name in VARIANTS:
        same = sum(1 for p in analysed if p.variants.get(name))
        diff = len(analysed) - same
        ladder = sum(1 for p in analysed
                     if p.variant_class.get(name) == p.baseline_class)
        print(f"| `{name}` | **{same}** | {diff} | {ladder} |")
    print()

    print("## The proof instrument's own blind spot, measured")
    print()
    print("`tools/cohort_replay.py` reports `payload identical` from a LEAF "
          "projection (`flatten` / `leaf_diff`), and an empty list contributes "
          "no leaf. A variant that adds a key whose value is `[]` therefore "
          "changes the payload BYTES while the projection every coverage cell "
          "reports under sees nothing. Both comparisons are made here on the "
          "same pairs so the gap is a number rather than a worry.")
    print()
    print("| variant | byte-identical | leaf-projection identical | the gap |")
    print("|---|---:|---:|---:|")
    for name in VARIANTS:
        same = sum(1 for p in analysed if p.variants.get(name))
        leaf = sum(1 for p in analysed if p.leaf_same.get(name))
        print(f"| `{name}` | {same} | {leaf} | **{leaf - same}** |")
    print()

    print("## Where a differing variant differs (leaf PATHS, never values)")
    print()
    print("| variant | changed leaf paths (collapsed), most frequent first |")
    print("|---|---|")
    for name in VARIANTS:
        counter: collections.Counter = collections.Counter()
        for probe in analysed:
            for path in probe.paths.get(name, []):
                counter[path] += 1
        if not counter:
            # The review's MINOR-10. "no payload changed" was the wrong words
            # for this cell, and wrong in the exact direction this instrument
            # exists to expose: for `omission_field_always` the bytes changed on
            # every document and the LEAF PROJECTION saw nothing, which is the
            # blind spot itself. The label now says what was measured.
            print(f"| `{name}` | *(no leaf path changed — which is not the same "
                  f"as no payload change; see the blind-spot table)* |")
            continue
        listed = ", ".join(f"`{path}` ×{count}" for path, count in counter.most_common(6))
        print(f"| `{name}` | {listed} |")
    print()

    print("## Registrations covered")
    print()
    print(f"`{'`, `'.join(registrations)}`" if registrations else "*(none)*")
    print()

    unanalysed = [p for p in probes if not p.analysed]
    if unanalysed:
        print("## Documents the probe could not analyse (by class, never by value)")
        print()
        print("| reason | documents |")
        print("|---|---:|")
        for reason, count in collections.Counter(
                p.error or "unknown" for p in unanalysed).most_common():
            print(f"| `{reason}` | {count} |")
        print()

    if args.json:
        args.json.write_text(json.dumps([
            {
                "sha16": p.sha16,
                "parser_id": p.parser_id,
                "analysed": p.analysed,
                "error": p.error,
                "baseline_class": p.baseline_class,
                "variants": p.variants,
                "leaf_same": p.leaf_same,
                "variant_class": p.variant_class,
                "paths": p.paths,
            }
            for p in probes
        ], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
