"""l1s2_admission_probe.py — the omission, MEASURED at the document seam.

    python -m tools.l1s2_admission_probe --run <run dir> --data-dir <cold cache> \
        [--registrations a,b,c] [--json <private>.json]

WHY THIS EXISTS RATHER THAN A RE-RUN OF THE DESIGN'S PROBE
----------------------------------------------------------
`tools/l1_design_skip_probe.py` measured the population this card acts on by
watching three source LINES execute — `symitar`'s `continue`, the `return None`
inside `community_section._parse_sectioned_statement`, and `zions._inert`. It
verifies those line numbers against the source text they must sit on and
REFUSES rather than reporting a zero if any has moved. Those are precisely the
lines this card rewrote, so at this tree that probe refuses, by its own design,
and its refusal is evidence that the sites changed rather than a result to
report.

What has to be measured now is a different thing anyway. The question is no
longer *where does a skip fire* but *what admitted every section the readers do
not publish*, and that is answered at the seam that owns the record rather than
by watching a line: this probe runs each reader over its own `validated`
documents through `analysis.pipeline.analyze_document(parse_mode="deterministic")`
and reads the omissions the readers themselves recorded.

WHAT IT REPORTS
---------------
1. **Per registration** — documents read, documents carrying an omission,
   sections omitted, and the omission's evidence class. Every class is a member
   of L1-C17's closed vocabulary by construction (`SiblingOmission` refuses any
   other at the point it is built), so a section admitted by anything the design
   did not ratify cannot reach this table; it raises where it is made.
2. **Refusals** — a document the run of record has as `validated` that this tree
   no longer publishes. That is the number the card's STOP condition is written
   on: a validated document refused here means the evidence classes are narrower
   than the paper, and it is reported with its sha and its refusal class.
3. **The payload claim, byte for byte.** For every document carrying an
   omission, the ACCOUNT block this tree publishes is compared against the run
   of record's own stored payload for that document, as canonical bytes; and the
   document block is checked to carry NOTHING but the omission record and the
   account count. Together those two are the card's "payload changed only by the
   omission field", stated as a measurement rather than as a claim about which
   fields an implementer believes were touched.

PRIVACY
-------
Content sha16s, registration ids, evidence-class names, counts, exception class
names and payload leaf PATHS. The omitted section's printed LABEL is read by the
readers and deliberately never printed here: it is a caption off the paper.
Nothing else this instrument holds comes from a document either.

READ-ONLY over the run of record and the cold cache. No OCR, no model, $0.
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

DEFAULT_REGISTRATIONS = ("symitar", "community_section", "dakota_west",
                         "mission_valley", "zions")

#: The document-level facts a stage-2 tree may fill. Anything else non-empty in
#: the published document block is a fact this stage did not read.
ALLOWED_DOCUMENT_FACTS = ("account_count", "omitted_sections")


@dataclass
class DocProbe:
    sha16: str
    parser_id: str
    published: bool = False
    error: str = ""
    #: (evidence class, posting count) per omitted section — never the label.
    omissions: list[tuple[str, int]] = field(default_factory=list)
    account_payload_identical: bool | None = None
    changed_leaves: dict = field(default_factory=dict)
    document_facts_beyond_the_omission: list[str] = field(default_factory=list)


def probe_document(sha: str, parser_id: str, cache: ColdCache) -> DocProbe | None:
    from analysis.pipeline import analyze_document
    from analysis.serialization import document_report_to_dict, report_to_dict

    markdown, pages = cache.text(sha)
    if markdown is None:
        return None
    out = DocProbe(sha16=sha[:16], parser_id=parser_id)
    try:
        document = analyze_document(markdown, parse_mode="deterministic", sheets=pages)
    except Exception as exc:  # the runner's own boundary: a refusal is data
        out.error = type(exc).__name__
        return out
    out.published = True
    out.omissions = [(omission.reason, omission.posting_count)
                     for omission in document.omissions]
    if not out.omissions:
        return out

    # The two halves of "the payload changed ONLY by the omission field".
    baseline = cache.baseline_payload(markdown, pages)
    # `tools/cohort_replay.py::replay_one`'s normalisation, and for its reason:
    # the cache stores canonical JSON, `report_to_dict` returns tuples where the
    # stored payload holds lists, and a comparison that skips this round trip
    # reports every serialised set as a mover. Compare like with like.
    account = json.loads(json.dumps(report_to_dict(document.accounts[0]),
                                    sort_keys=True, default=str))
    if baseline is None:
        out.account_payload_identical = None
    else:
        out.changed_leaves = leaf_diff(baseline, account)
        out.account_payload_identical = not out.changed_leaves
    block = document_report_to_dict(document).get("document") or {}
    out.document_facts_beyond_the_omission = sorted(
        key for key, value in block.items()
        if key not in ALLOWED_DOCUMENT_FACTS and value not in (None, [], {})
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--registrations", default=",".join(DEFAULT_REGISTRATIONS))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    registrations = tuple(r.strip() for r in args.registrations.split(",") if r.strip())
    rows = load_baseline_rows(args.run)
    cache = ColdCache(args.data_dir)

    results: dict[str, list[DocProbe]] = {}
    for registration in registrations:
        shas = sorted(sha for sha, row in rows.items()
                      if (row.get("parser_id") or "") == registration
                      and (row.get("outcome_class") or "") == "validated")
        found: list[DocProbe] = []
        for sha in shas:
            probe = probe_document(sha, registration, cache)
            if probe is not None:
                found.append(probe)
        results[registration] = found

    every = [probe for found in results.values() for probe in found]
    refused = [probe for probe in every if not probe.published]
    carriers = [probe for probe in every if probe.omissions]

    print("# L1-S2 — the omission, measured at the DOCUMENT seam")
    print()
    print("Every row is produced by running the reader over its own `validated` "
          "documents of the run of record through "
          "`analyze_document(parse_mode=\"deterministic\")` and reading the "
          "omissions the reader itself recorded. Every evidence class below is "
          "a member of L1-C17's closed vocabulary by construction: "
          "`SiblingOmission` refuses any other where the record is built.")
    print()
    print("| registration | `validated` documents read | documents carrying an omission | sections omitted | REFUSED |")
    print("|---|---:|---:|---:|---:|")
    for registration in registrations:
        found = results[registration]
        movers = [probe for probe in found if probe.omissions]
        sections = sum(len(probe.omissions) for probe in found)
        no_longer = sum(1 for probe in found if not probe.published)
        print(f"| `{registration}` | {len(found)} | **{len(movers)}** | {sections} | {no_longer} |")
    print(f"| **total** | **{len(every)}** | **{len(carriers)}** | "
          f"**{sum(len(p.omissions) for p in every)}** | **{len(refused)}** |")
    print()

    print("## Which evidence class admitted each omitted section")
    print()
    print("| registration | `printed_dormancy_declaration` | `printed_zero_activity_summary` | `yield_only_arithmetic_with_summary_equality` |")
    print("|---|---:|---:|---:|")
    totals: collections.Counter = collections.Counter()
    for registration in registrations:
        counter: collections.Counter = collections.Counter()
        for probe in results[registration]:
            for reason, _rows in probe.omissions:
                counter[reason] += 1
                totals[reason] += 1
        print(f"| `{registration}` | {counter['printed_dormancy_declaration']} | "
              f"{counter['printed_zero_activity_summary']} | "
              f"{counter['yield_only_arithmetic_with_summary_equality']} |")
    print(f"| **total** | **{totals['printed_dormancy_declaration']}** | "
          f"**{totals['printed_zero_activity_summary']}** | "
          f"**{totals['yield_only_arithmetic_with_summary_equality']}** |")
    print()

    print("## The payload claim, on the documents carrying an omission")
    print()
    identical = sum(1 for probe in carriers if probe.account_payload_identical is True)
    moved = [probe for probe in carriers if probe.account_payload_identical is False]
    unmeasured = [probe for probe in carriers if probe.account_payload_identical is None]
    extra = [probe for probe in carriers if probe.document_facts_beyond_the_omission]
    print("| property | documents |")
    print("|---|---:|")
    print(f"| carrying an omission | {len(carriers)} |")
    print(f"| **account block byte-identical to the run of record's payload** | **{identical}** |")
    print(f"| ... account block moved | {len(moved)} |")
    print(f"| ... no baseline payload to compare | {len(unmeasured)} |")
    print(f"| document block carrying a fact beyond the omission and the count | {len(extra)} |")
    print()
    for probe in moved:
        print(f"* `{probe.sha16}` `{probe.parser_id}` — "
              + ", ".join(f"`{path}`x{count}" for path, count in probe.changed_leaves.items()))
    for probe in extra:
        print(f"* `{probe.sha16}` `{probe.parser_id}` — document facts: "
              + ", ".join(f"`{name}`" for name in probe.document_facts_beyond_the_omission))
    if moved or extra:
        print()

    print("## Documents this tree no longer publishes")
    print()
    if not refused:
        print("none")
    else:
        print("| sha16 | registration | refusal |")
        print("|---|---|---|")
        for probe in refused:
            print(f"| `{probe.sha16}` | `{probe.parser_id}` | `{probe.error}` |")
    print()

    print("## The documents carrying an omission, by sha16")
    print()
    for registration in registrations:
        shas = [probe.sha16 for probe in results[registration] if probe.omissions]
        if shas:
            print(f"* `{registration}` — " + ", ".join(f"`{sha}`" for sha in shas))
    print()

    if args.json:
        args.json.write_text(json.dumps({
            "registrations": list(registrations),
            "documents_read": len(every),
            "documents_with_an_omission": len(carriers),
            "sections_omitted": sum(len(p.omissions) for p in every),
            "by_class": dict(totals),
            "refused": [{"sha16": p.sha16, "parser_id": p.parser_id, "error": p.error}
                        for p in refused],
            "carriers": {
                registration: sorted(p.sha16 for p in results[registration] if p.omissions)
                for registration in registrations
            },
            "account_payload_identical": identical,
            "account_payload_moved": [
                {"sha16": p.sha16, "parser_id": p.parser_id, "paths": p.changed_leaves}
                for p in moved
            ],
            "document_facts_beyond_the_omission": [
                {"sha16": p.sha16, "facts": p.document_facts_beyond_the_omission}
                for p in extra
            ],
        }, indent=1), encoding="utf-8")

    # Exit 2 on either half of the card's STOP condition: a validated document
    # this tree refuses, or an omission carrier whose account payload moved.
    return 2 if (refused or moved or extra) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
