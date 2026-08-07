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
    """
    if not row.parser_id:
        return "no_claim"
    folder = _normalise(row.folder_label)
    if not folder or folder in {"root", "misc", "others", "unidentified"}:
        return "unlabelled_folder"
    candidates = {_normalise(row.parser_id)}
    if row.statement_bank:
        candidates.add(_normalise(row.statement_bank))
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
    total = len(rows)
    processed = [r for r in rows if r.outcome_class != DEFERRED_CLASS]
    deferred = [r for r in rows if r.outcome_class == DEFERRED_CLASS]

    # A document served from the D-3 analysis cache never re-dispatched, so it
    # has no parser verdict this run. Counting those as "unclaimed" would be a
    # lie with consequences: on a re-run every folder would be reported as an
    # unknown-layout cluster and coverage would read ~0%. Coverage is therefore
    # computed over documents that actually dispatched, and the cached ones are
    # reported as their own line. `--no-cache` forces a full re-dispatch.
    dispatched = [r for r in processed if r.dispatch_outcome]
    cached_dispatch = len(processed) - len(dispatched)
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

    unknown = [r for r in dispatched if r.dispatch_outcome != "claimed"]
    unknown_clusters = Counter(r.folder_label for r in unknown)

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

    return {
        "run_id": run_id,
        "mode": mode,
        "documents": total,
        "processed": len(processed),
        "deferred": len(deferred),
        "deferred_reasons": dict(Counter(r.outcome_reason for r in deferred)),
        "dispatched": len(dispatched),
        "dispatch_cached": cached_dispatch,
        "deterministic_coverage": (claimed / len(dispatched)) if dispatched else 0.0,
        "dispatch": dict(dispatch),
        "outcome": dict(outcome),
        "reasons": dict(reasons),
        "classification": dict(classification),
        "dedup": dict(dedup),
        "source_path": dict(source_path),
        "folder_agreement": dict(agreement),
        "label_unmatched_pairs": label_unmatched[:50],
        "parsers": dict(parsers.most_common()),
        "folders": dict(folders.most_common()),
        "unknown_layout_clusters": dict(unknown_clusters.most_common()),
        "ambiguity_clusters": dict(ambiguity_clusters.most_common()),
        "near_miss_parsers": dict(near_miss.most_common(20)),
        "truncated_documents": sum(1 for r in rows if r.truncated_pages),
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
            "   (no dispatch this run; --no-cache to re-dispatch)"
        )
    for key in ("ambiguous", "unclaimed") if not profile_only else ():
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

    if summary["folder_agreement"]:
        lines.append("parser claim vs folder label")
    for key, count in sorted(summary["folder_agreement"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_bar(key, count, processed))
    for entry in summary["label_unmatched_pairs"][:15]:
        lines.append(
            f"    unmatched: {entry['folder']} -> {entry['parser']}"
            f"   ({entry['documents']} document(s))"
        )

    if summary["unknown_layout_clusters"]:
        lines.append("unknown-layout clusters, ranked by volume")
        for key, count in list(summary["unknown_layout_clusters"].items())[:20]:
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
    "candidates", "near_miss", "outcome_class", "outcome_reason", "error_type",
    "statement_bank", "account_last4", "cache_ocr", "cache_analysis", "elapsed_ms",
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
