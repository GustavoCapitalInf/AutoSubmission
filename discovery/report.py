"""Discovery rollups and the written artifacts.

Everything here goes to a gitignored directory. The rows carry relative paths
and folder labels because a human has to act on a finding; account identifiers
are masked to last-4 and no transaction-level detail is written anywhere.
The hash->path map is its own file, so a telemetry consumer never needs it and
a report reader never has to join by hand.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

#: The outcome class for "the tranche chose not to do this work" (H-3).
#: Keyed on the CLASS, not the reason: the reason vocabulary belongs to
#: telemetry, and this stays correct when it grows.
DEFERRED_CLASS = "deferred"

#: The folder-agreement class for a claim that names no issuer. See
#: `folder_agreement` — and read its warning before touching this.
TEMPLATE_CLAIM = "template_claim"


def _normalise(label: str) -> str:
    return "".join(character for character in label.lower() if character.isalnum())


def folder_agreement(row) -> str:
    """Does the parser's claim line up with the analyst's folder label?

    Folder names are human bank labels, which makes this a free
    detection-accuracy reference (WAVE2_BRIEF §9.4). Matching is containment
    after normalisation, in either direction.

    The unmatched bucket is called `label_unmatched`, NOT "disagree", and the
    distinction is the whole point. On the pinned 109 this bucket is 11
    documents and every one of them is an abbreviation the matcher cannot see
    through — `Amex` vs `american_express`, `BofA` vs `bank_of_america`. Those
    are not wrong claims. Calling them disagreements would manufacture a
    detection-accuracy problem out of a string-matching limitation, and on
    3,506 archive documents that fiction would be the headline number. So the
    runner reports the bucket, ranks the distinct (folder -> parser) pairs by
    volume, and leaves the judgement to a human who resolves each pair once.

    `template_claim` is the second thing that bucket was carrying, and it is
    not a string-matching limitation at all — it is a CATEGORY ERROR. The
    honest-unknown-issuer registrations (§U) claim a document TEMPLATE, not a
    bank: they are registered under a template name ("Releve de Compte
    Statement Template", "Core Processor Sectioned Platform") and they publish
    `Statement.bank = None` on purpose, because the paper names no issuer. A
    claim that names no issuer cannot agree or disagree with a folder's bank
    label; there is nothing on the claim side to compare. Measured on the run
    of record (`c924d751`): 41 claims publish no issuer, and all 41 come from
    four template registrations.

    **That census measures today's data; it is not a structural guarantee, and
    the difference matters here.** At least five registrations can publish
    `bank=None` by design — the four in the census plus `fiserv_premier`,
    which deliberately declines to publish a capitalized run in front of an
    address as an identity. It is absent from the 41 only because all ten
    documents it claimed happened to print a readable issuer, which is a fact
    about this archive and not about the registry. (It is registered under a
    platform name too, so the class would still be right for it — but nothing
    here ENFORCES that, and a bank-specific parser that failed to set `bank`
    would land in this bucket and be described as a template claim.)

    Two things keep that honest rather than hidden: the pairs are ranked and
    printed, so such a parser is on the page instead of inside a bucket total;
    and the real fix is a registry-side "this label is not an issuer claim"
    fact, carried as a card (§DISCOBS DO7#4) rather than approximated here by
    sniffing registration names for "Platform" or "Template".

    **THIS BUCKET MUST NOT BE "FIXED" (§U D3, verbatim in substance).** The
    obvious way to make the six `Desjardins -> releve_facturation` entries
    disappear is to name the registration after the folder it is filed under.
    Never do that. §U4.1's evidence forbids it and
    `tests/test_parser_detection_markers.py` exists to prevent it: the other
    ten documents of that same template sit in `Unidentified/` and are not
    Desjardins paper at all. The rollup is reporting a true fact — statements
    filed under a bank name that appears nowhere in them — and re-labelling a
    parser to silence a rollup would put the folder's guess into the registry
    as if it were evidence.

    Order is load-bearing. `unlabelled_folder` is tested first because it is a
    statement about the REFERENCE side (the analyst filed this under nothing
    usable) and it already exempts those documents; `template_claim` is tested
    before the containment match because a template name that happened to be
    contained in a folder name would otherwise be reported as `agree` —
    manufacturing a detection-accuracy datum out of a coincidence, which is
    the same failure this docstring opens with, in the other direction.
    """
    if not row.parser_id:
        return "no_claim"
    folder = _normalise(row.folder_label)
    if not folder or folder in {"root", "misc", "others", "unidentified"}:
        return "unlabelled_folder"
    if not row.statement_bank:
        return TEMPLATE_CLAIM
    candidates = {_normalise(row.parser_id), _normalise(row.statement_bank)}
    for candidate in candidates:
        if candidate and (candidate in folder or folder in candidate):
            return "agree"
    return "label_unmatched"


@dataclass
class Rollups:
    payload: dict

    def render(self) -> str:
        return render_report(self.payload)


def summarize(rows: list, *, mode: str, run_id: str, inventory=None,
              cache_stats: dict | None = None) -> dict:
    # Imported here, not at module scope: the runner owns the row vocabulary
    # (as it owns `visual_rung`'s), and pulling `analysis.pipeline` in behind
    # every `import discovery.report` to read one string constant is a cost the
    # rollups do not need to impose on their readers.
    from .runner import PARSER_ID_LIVE_DETECT, PARSER_ID_UNAVAILABLE

    total = len(rows)
    processed = [r for r in rows if r.outcome_class != DEFERRED_CLASS]
    deferred = [r for r in rows if r.outcome_class == DEFERRED_CLASS]

    # A document served from the D-3 analysis cache never re-dispatched.
    # Counting those as "unclaimed" would be a lie with consequences (on a
    # re-run every folder would read as an unknown-layout cluster and coverage
    # as ~0%), so they used to be excluded from the denominator entirely and
    # reported as their own line. That was honest and blind: on a warm run the
    # excluded set is most of the archive, and every parser-keyed rollup here
    # silently lost it.
    #
    # Since §DISCOBS the runner RECONSTRUCTS the identity of a cache-served row
    # from a live detection sweep and marks it `parser_id_source=live_detect`,
    # so those rows carry a verdict again and belong in the denominator. The
    # two lines below keep the distinction visible rather than assuming it away:
    #
    #   `dispatch_cached`      — verdicts reconstructed, not observed. The name
    #                            is now exact: it is the analysis-cache-served
    #                            set and nothing else.
    #   `dispatch_unavailable` — processed documents the analysis stage never
    #                            ran for (invalid PDF, OCR failure). These were
    #                            previously counted as "served from cache",
    #                            which they never were.
    #   `dispatch_inconclusive`— processed documents the analysis stage DID run
    #                            for, served from cache, whose identity the
    #                            projection refused to reconstruct (structurer
    #                            payload, or a sweep that named no single
    #                            survivor). Split out rather than folded into
    #                            the line above, because "never analysed" and
    #                            "analysed, identity refused" are different
    #                            findings and only the first is a document we
    #                            know nothing about. Zero on every run so far;
    #                            a non-zero here is the REGFP card arriving.
    dispatched = [r for r in processed if r.dispatch_outcome]
    cached_dispatch = sum(
        1 for r in dispatched
        if getattr(r, "parser_id_source", "") == PARSER_ID_LIVE_DETECT
    )
    inconclusive_dispatch = sum(
        1 for r in processed
        if getattr(r, "parser_id_source", "") == PARSER_ID_UNAVAILABLE
    )
    unavailable_dispatch = len(processed) - len(dispatched) - inconclusive_dispatch
    identity_source = Counter(
        getattr(r, "parser_id_source", "") for r in processed
        if getattr(r, "parser_id_source", "")
    )
    dispatch = Counter(r.dispatch_outcome for r in dispatched)
    outcome = Counter(r.outcome_class for r in processed)
    reasons = Counter(r.outcome_reason for r in processed)
    classification = Counter(r.classification for r in rows)
    dedup = Counter(r.dedup_status for r in rows)
    source_path = Counter(r.source_path for r in processed)
    agreement = Counter(folder_agreement(r) for r in dispatched)

    claimed = dispatch.get("claimed", 0)
    parsers = Counter(r.parser_id for r in dispatched if r.parser_id)
    folders = Counter(r.folder_label for r in rows)

    # A crash is a defect of ours, not a layout we have never seen. Ranking the
    # two together would put a bug at the top of the "which bank needs a
    # parser" list and hide it at the bottom of the "which parser needs a fix"
    # one, so `parser_exception` gets its own cluster ranking (W3-1).
    crashed = [r for r in dispatched if r.dispatch_outcome == "parser_exception"]
    crash_clusters = Counter(entry for r in crashed for entry in r.parser_exceptions)
    unknown = [
        r for r in dispatched
        if r.dispatch_outcome not in ("claimed", "parser_exception")
    ]
    unknown_clusters = Counter(r.folder_label for r in unknown)

    # "A parser claimed this and then declined it" is a different work item from
    # "no parser has ever seen this layout", and it is the cheaper one: the
    # parser already exists and already detects. Ranking the declining PARSER
    # (not the folder) is what makes it actionable — the unknown-layout ranking
    # above answers "which bank needs a parser", this one answers "which parser
    # needs widening". A row can name several: every claimant that declined
    # before the document ran out of claimants is counted once.
    declined_clusters = Counter(
        entry for r in dispatched if r.outcome_reason == "parser_declined"
        for entry in r.attempted
    )

    ambiguity_clusters = Counter(
        " + ".join(sorted(entry.split(":")[0] for entry in r.candidates))
        for r in dispatched if r.dispatch_outcome == "ambiguous"
    )

    near_miss = Counter()
    for row in unknown:
        for entry in row.near_miss:
            near_miss[entry.split(":")[0]] += 1

    # Ranked distinct pairs, not per-document lines: an adjudicator resolves
    # "Amex -> american_express" once, not eleven times.
    unmatched_pairs = Counter(
        (r.folder_label, r.parser_id)
        for r in dispatched if folder_agreement(r) == "label_unmatched"
    )
    label_unmatched = [
        {"folder": folder, "parser": parser, "documents": count}
        for (folder, parser), count in unmatched_pairs.most_common()
    ]
    # The same ranking for the template class, and for the same reason: it is
    # reported, never resolved by renaming a parser after a folder. Printing
    # the pairs is also what keeps the class honest — the rule that fills it is
    # "the claim published no issuer", so a bank-specific parser that ever
    # lands here is on the page instead of inside a bucket total.
    template_pairs = Counter(
        (r.folder_label, r.parser_id)
        for r in dispatched if folder_agreement(r) == TEMPLATE_CLAIM
    )
    template_claims = [
        {"folder": folder, "parser": parser, "documents": count}
        for (folder, parser), count in template_pairs.most_common()
    ]

    return {
        "run_id": run_id,
        "mode": mode,
        "documents": total,
        "processed": len(processed),
        "deferred": len(deferred),
        "deferred_reasons": dict(Counter(r.outcome_reason for r in deferred)),
        "dispatched": len(dispatched),
        "dispatch_cached": cached_dispatch,
        "dispatch_unavailable": unavailable_dispatch,
        "dispatch_inconclusive": inconclusive_dispatch,
        "parser_id_source": dict(identity_source.most_common()),
        "deterministic_coverage": (claimed / len(dispatched)) if dispatched else 0.0,
        "dispatch": dict(dispatch),
        "outcome": dict(outcome),
        "reasons": dict(reasons),
        "classification": dict(classification),
        "dedup": dict(dedup),
        "source_path": dict(source_path),
        "folder_agreement": dict(agreement),
        "label_unmatched_pairs": label_unmatched[:50],
        "template_claim_pairs": template_claims[:50],
        "parsers": dict(parsers.most_common()),
        "folders": dict(folders.most_common()),
        "unknown_layout_clusters": dict(unknown_clusters.most_common()),
        "declined_clusters": dict(declined_clusters.most_common()),
        "crash_clusters": dict(crash_clusters.most_common()),
        "ambiguity_clusters": dict(ambiguity_clusters.most_common()),
        "near_miss_parsers": dict(near_miss.most_common(20)),
        "truncated_documents": sum(1 for r in rows if r.truncated_pages),
        # W3-5: what the visual rung did, over EVERY enumerated document. Rows
        # whose visual read failed closed are `failed` and so already counted in
        # `outcome`; this is the second axis — how many documents the rung was
        # asked for, and what it bought. Empty in every offline mode.
        "visual_rung": dict(
            Counter(
                r.visual_rung for r in rows
                if getattr(r, "visual_rung", "not_attempted") != "not_attempted"
            ).most_common()
        ),
        "cache": cache_stats or {},
        "inventory": {
            "files": inventory.files, "pdfs": inventory.pdf_count,
            "total_bytes": inventory.total_bytes,
            "pinned": len(inventory.pinned), "discovery": len(inventory.discovery),
        } if inventory is not None else {},
    }


def _bar(label: str, count: int, total: int, width: int = 26) -> str:
    share = f"{count / total:6.1%}" if total else "     -"
    return f"  {label:<{width}}{count:>7}   {share}"


def render_report(summary: dict) -> str:
    """ASCII only: this is printed by a CLI, and a legacy console code page
    must not be able to turn a measurement into a UnicodeEncodeError.

    Tranche 0 gets a shorter report on purpose: with nothing parsed there is no
    coverage, no outcome and no parser claim, and printing those as a row of
    zeros would read like a result rather than like a mode that did not ask the
    question.
    """
    total = summary["documents"]
    processed = summary["processed"]
    profile_only = summary["mode"] == "profile-only"
    lines = [
        f"discovery run {summary['run_id']}  mode={summary['mode']}",
        "",
        f"documents enumerated      {total:>7}",
    ]
    if profile_only:
        lines.append(f"  not parsed (mode)       {summary['deferred']:>7}")
    else:
        lines.append(f"  processed               {processed:>7}")
        lines.append(
            f"  deferred                {summary['deferred']:>7}"
            + (f"   ({', '.join(f'{k} {v}' for k, v in sorted(summary['deferred_reasons'].items()))})"
               if summary["deferred_reasons"] else "")
        )
    lines.append("")
    if not profile_only:
        lines.append(
            f"deterministic coverage    {summary['dispatch'].get('claimed', 0):>7} / "
            f"{summary['dispatched']}   {summary['deterministic_coverage']:.1%}"
        )
    if summary.get("dispatch_cached"):
        lines.append(
            f"  served from cache       {summary['dispatch_cached']:>7}"
            "   (identity re-derived by detect, not re-dispatched; --no-cache"
            " to re-dispatch)"
        )
    if summary.get("dispatch_unavailable"):
        lines.append(
            f"  no dispatch record      {summary['dispatch_unavailable']:>7}"
            "   (the analysis stage never ran for these)"
        )
    if summary.get("dispatch_inconclusive"):
        lines.append(
            f"  identity refused        {summary['dispatch_inconclusive']:>7}"
            "   (analysed and cached; detect named no single parser)"
        )
    for key in ("ambiguous", "unclaimed", "parser_exception") if not profile_only else ():
        if key in summary["dispatch"]:
            lines.append(_bar(key, summary["dispatch"][key], summary["dispatched"]))

    if summary["outcome"]:
        lines.append("outcome")
        for key in ("validated", "review", "withheld", "failed"):  # deferred is counted above
            if key in summary["outcome"]:
                lines.append(_bar(key, summary["outcome"][key], processed))

    if summary["reasons"]:
        lines.append("reason")
        for key, count in sorted(summary["reasons"].items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(_bar(key, count, processed))

    lines.append("intake")
    for key, count in sorted(summary["classification"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_bar(f"profile {key}", count, total))
    for key, count in sorted(summary["source_path"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_bar(f"read via {key}", count, processed))
    for key, count in sorted(summary["dedup"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_bar(f"dedup {key}", count, total))
    lines.append(_bar("truncation flagged", summary["truncated_documents"], total))

    if summary.get("visual_rung"):
        lines.append("visual OCR rung (local, $0 vendor)")
        for key, count in summary["visual_rung"].items():
            lines.append(_bar(key, count, total))

    if summary.get("parser_id_source"):
        # "routing verdict", not "parser identity": a live `unclaimed` is a
        # verdict too, and it is an observation like any other. The column is
        # named `parser_id_source` because that is the field it explains.
        lines.append("routing verdict provenance (parser_id_source)")
        for key, count in summary["parser_id_source"].items():
            lines.append(_bar(key, count, processed))

    if summary["folder_agreement"]:
        lines.append("parser claim vs folder label")
    for key, count in sorted(summary["folder_agreement"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_bar(key, count, processed))
    for entry in summary["label_unmatched_pairs"][:15]:
        lines.append(
            f"    unmatched: {entry['folder']} -> {entry['parser']}"
            f"   ({entry['documents']} document(s))"
        )
    # Printed under its own heading, not folded in above: these are NOT
    # unmatched labels, and the one thing a reader must not do with them is
    # rename the parser after the folder (see `folder_agreement`).
    for entry in summary.get("template_claim_pairs", [])[:15]:
        lines.append(
            f"    template claim (no issuer printed): {entry['folder']} ->"
            f" {entry['parser']}   ({entry['documents']} document(s))"
        )

    if summary["unknown_layout_clusters"]:
        lines.append("unknown-layout clusters, ranked by volume")
        for key, count in list(summary["unknown_layout_clusters"].items())[:20]:
            lines.append(_bar(key, count, processed))
    if summary.get("declined_clusters"):
        lines.append("claimed then declined (parser_declined), ranked by parser")
        for key, count in list(summary["declined_clusters"].items())[:20]:
            lines.append(_bar(key, count, processed))
    if summary.get("crash_clusters"):
        lines.append("parser crashes (parser:stage:exception), ranked")
        for key, count in list(summary["crash_clusters"].items())[:20]:
            lines.append(_bar(key, count, processed))
    if summary["near_miss_parsers"]:
        lines.append("near-miss parsers on unclaimed documents")
        for key, count in list(summary["near_miss_parsers"].items())[:10]:
            lines.append(_bar(key, count, processed))
    if summary["ambiguity_clusters"]:
        lines.append("ambiguity clusters")
        for key, count in list(summary["ambiguity_clusters"].items())[:20]:
            lines.append(_bar(key, count, processed))

    if summary["parsers"]:
        lines.append("parsers claiming, ranked")
        for key, count in list(summary["parsers"].items())[:20]:
            lines.append(_bar(key, count, processed))

    if summary["cache"]:
        lines.append("cache")
        for stage, stats in sorted(summary["cache"].items()):
            body = " ".join(f"{k} {v}" for k, v in sorted(stats.items()))
            lines.append(f"  {stage:<26}{body}")

    inventory = summary.get("inventory") or {}
    if inventory:
        lines += [
            "",
            f"inventory  {inventory['files']:,} files | {inventory['pdfs']:,} PDFs | "
            f"{inventory['total_bytes']:,} bytes | "
            f"{inventory['pinned']} pinned + {inventory['discovery']} discovery",
        ]
    return "\n".join(lines)


ROW_FIELDS = [
    "relative_path", "folder_label", "content_sha256", "byte_size", "valid_pdf",
    "encrypted", "classification", "page_count", "likely_account_count",
    "dedup_status", "duplicate_of", "source_path", "source_model",
    "truncated_pages", "parser_id", "parser_score", "dispatch_outcome",
    "parser_id_source",
    "candidates", "attempted", "near_miss", "parser_exceptions",
    "outcome_class", "outcome_reason", "error_type",
    "statement_bank", "account_last4", "cache_ocr", "cache_analysis",
    "cache_visual", "visual_rung", "elapsed_ms",
]


def write_rows(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.as_dict()[key] for key in ROW_FIELDS})


def write_hash_map(path: Path, rows: list) -> None:
    """The hash -> path map, deliberately its own file (H-3 ruling 4).

    Telemetry identifies documents by hash and carries no path; this is the
    only place the join exists, and it is gitignored like everything else here.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["content_sha256", "relative_path"])
        for row in rows:
            writer.writerow([row.content_sha256, row.relative_path])


def write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_report(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(summary) + "\n", encoding="utf-8")
