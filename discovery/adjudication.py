"""W3-4 — cluster adjudication and routing.

    python -m discovery.adjudicate <run_dir> [--enrich <run_dir> ...]

Turns a finished discovery run into an **adjudication workspace**: one masked
evidence card per cluster, each carrying a disposition from a closed
vocabulary. Where the evidence decides mechanically, a rule decides and says
which rule; where it does not, the cluster goes to the human queue and the
tool says nothing more. **It never decides taste questions** - Ocean and
Gustavo adjudicate the human queue, and every new-parser proposal is a
proposal (WAVE3_BRIEF gate 3).

Systemic by construction: a cluster is the unit, never a statement. No card
names a document; documents appear only as content hashes, and only as a
sample. Remediation aimed at a card is remediation aimed at a layout family.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from telemetry.diagnostics import UNATTRIBUTED

from .evidence import (
    LABEL_UNMATCHED,
    TEMPLATE_CLAIM,
    Document,
    Run,
    bank_is_registered,
    label_verdict,
    load_run,
    registered_bank_tokens,
    registration_labels,
)

#: The closed disposition vocabulary (Ocean, W3-4 dispatch). A cluster carries
#: exactly one. `needs_human_review` is not a failure of the tool - it is the
#: honest answer whenever the evidence does not decide, and it is where taste
#: questions belong.
DISPOSITIONS = (
    "variant_completeness",
    "generic_structurer",
    "new_parser_candidate",
    "misfiled",
    "junk_unusable",
    # W3-2b (Ocean ruling 1). A parser crash is a code defect, not a layout
    # family and not an adjudication question - routing it to
    # `needs_human_review` made the human queue look like it contained a
    # taste question when it contained a bug. Remediation is owned by W3-1's
    # exception ranking; this disposition exists so the workspace can say so
    # and get it out of the queue.
    "parser_defect",
    "needs_human_review",
)


class UnattributedParsers(RuntimeError):
    """A class x parser view was asked for over a run that has no parsers.

    Raised rather than degraded (Ocean ruling 2). The failure it prevents is
    silent: a cache-served run produces a complete-looking table in which every
    row reads `(parser unknown)`, and nothing about the output says the
    question was not answered.
    """

#: Volume at or above which an unclaimed cluster for an UNREGISTERED bank is
#: proposed as a new-parser candidate. A policy threshold, not a
#: statement-specific constant: it encodes "per-bank volume must justify parser
#: #47", the argument DISCOVERY_COMBINED_REPORT §2 class 4 makes, and Huntington
#: (54) is the first case it is meant to catch. Overridable from the CLI, and
#: the volume half is all it can measure - layout stability is not observable
#: from telemetry, so the card says so and a human rules.
NEW_PARSER_VOLUME_FLOOR = 50

#: Minimum cluster size worth a card at all. Below it, documents are rolled
#: into a `tail` card per kind so a 400-line workspace does not hide the ten
#: clusters that matter.
MIN_CLUSTER = 5

CLUSTER_KINDS = (
    "withheld_check_cell",
    "unclaimed_bank_folder",
    "unclaimed_unlabelled",
    "label_disagreement",
    "unlabelled_folder_claims",
    "parser_crash",
    "advisory_flag",
    "unusable_document",
)


@dataclass(frozen=True)
class Rule:
    id: str
    disposition: str
    because: str


#: Every mechanical routing rule, with the reason it is mechanical. A rule is
#: only allowed here if the evidence ALONE decides it.
RULES: dict[str, Rule] = {
    rule.id: rule for rule in (
        Rule("R1_claimed_but_withheld", "variant_completeness",
             "a parser claimed these and the platform withheld: detection is "
             "already right, so the gap is extraction completeness for this "
             "layout variant - true by definition, no judgement involved"),
        Rule("R2_known_bank_unseen_layout", "variant_completeness",
             "unclaimed, but the registry already has a parser for this bank: "
             "a layout we have not seen from an institution we do support"),
        Rule("R3_unregistered_bank_volume", "new_parser_candidate",
             "unclaimed, no registered parser for this bank, and volume clears "
             "the floor - PROPOSAL ONLY: layout stability is not observable "
             "from telemetry and Gustavo rules on any new parser"),
        Rule("R4_unregistered_bank_tail", "generic_structurer",
             "unclaimed, no registered parser, and per-bank volume does not "
             "justify a parser - exactly the case AD-7 built generic "
             "understanding for"),
        Rule("R5_unlabelled_mix", "generic_structurer",
             "unclaimed documents a human could not even sort into a bank "
             "folder: composition unknown, so the layout-agnostic structurer "
             "is the only mechanism that does not need to know first"),
        Rule("R6_label_disagreement", "needs_human_review",
             "claimed and validated end-to-end, but the folder a human filed it "
             "in matches neither the claiming parser's id nor its registered "
             "bank name. That is a QUESTION, not a verdict: it is a misfiled "
             "document or an alias the matcher cannot see through, and only a "
             "human can tell. Ranked by distinct pair, so the answer is given "
             "once and applies to every document in it"),
        Rule("R7_unusable_document", "junk_unusable",
             "not a readable PDF, or encrypted: honest rejection, no layout "
             "work can help"),
        Rule("R8_parser_defect", "parser_defect",
             "a parser raised. This is our defect, not a layout family and not "
             "an adjudication question, so it is routed mechanically and out "
             "of the human queue. REMEDIATION IS OWNED BY W3-1's exception "
             "ranking, which groups the same crashes by parser and exception "
             "class; this card exists so the workspace accounts for the "
             "documents, not so anyone fixes them from here"),
        Rule("R9_advisory_flag", "needs_human_review",
             "an advisory integrity signal fired; whether it should force "
             "review is a policy question Ocean already queued, not evidence"),
        Rule("R10_unlabelled_folder_claims", "needs_human_review",
             "claims in folders that carry no bank label: the claim may be "
             "right, but there is no label to check it against"),
    )
}


@dataclass
class Cluster:
    """One masked evidence card. Nothing here identifies a document."""

    kind: str
    key: str
    documents: int
    disposition: str
    rule: str
    because: str
    evidence: dict = field(default_factory=dict)
    sample_hashes: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return asdict(self)


def _stats(documents: list[Document]) -> dict:
    """Aggregate structural signals. Counts and enum codes only."""
    pages = sorted(d.page_count for d in documents)
    sizes = sorted(d.byte_size for d in documents)

    def median(values: list[int]) -> int:
        return values[len(values) // 2] if values else 0

    return {
        "documents": len(documents),
        "classification": dict(Counter(d.classification for d in documents).most_common()),
        "source_path": dict(Counter(d.source_path for d in documents).most_common()),
        "outcome": dict(Counter(d.outcome_class for d in documents).most_common()),
        "page_count": {"min": pages[0] if pages else 0,
                       "median": median(pages),
                       "max": pages[-1] if pages else 0},
        "byte_size_median": median(sizes),
        "malformed_pages": sum(d.malformed_page_count for d in documents),
        "truncation_flagged": sum(1 for d in documents if d.truncated_page_count),
        "duplicates": sum(
            1 for d in documents if (d.dedup_status or "unique") != "unique"
        ),
        "parser_enriched": sum(1 for d in documents if d.parser_enriched_from),
    }


def _card(kind: str, key: str, documents: list[Document], rule_id: str,
          extra: dict | None = None, *, sample: int = 5) -> Cluster:
    rule = RULES[rule_id]
    evidence = _stats(documents)
    if extra:
        evidence.update(extra)
    return Cluster(
        kind=kind,
        key=key,
        documents=len(documents),
        disposition=rule.disposition,
        rule=rule.id,
        because=rule.because,
        evidence=evidence,
        sample_hashes=tuple(sorted(d.content_sha256 for d in documents)[:sample]),
    )


def label_check(
    documents: list[Document],
) -> tuple[dict[str, list[Document]], list[Document]]:
    """(disagreeing pairs, template claims) over the documents this check can
    ask about at all.

    ONE function, because two consumers must not disagree: the
    `label_disagreement` clusters and the workspace header that names what was
    exempted from them. It owns the population filter as well as the verdict —
    a document is judged only if the platform published a claim for it
    (`claimed`, with a parser, outcome `validated` or `review`) AND a human
    filed it under something usable. An unusable document, an unlabelled
    folder or a withheld outcome answers no filing question.

    The third verdict is the #TELCOV fix (§DISCOBS DO7#3). A §U registration
    claims a document TEMPLATE and publishes no issuer, so a bank folder can
    neither agree nor disagree with it; those documents used to land in
    `label_disagreement` (six `Desjardins -> releve_facturation` on the run of
    record) where the obvious way to make them disappear is to rename the
    parser after the folder. §U4.1's evidence forbids that and
    `tests/test_parser_detection_markers.py` exists to prevent it: the other
    ten documents of that template sit in `Unidentified/` and are not that
    bank's paper. So they are exempted from the disagreement and RETURNED, not
    dropped - the workspace prints the count and the warning.
    """
    labels_by_parser = registration_labels()
    mismatched: dict[str, list[Document]] = defaultdict(list)
    template_claims: list[Document] = []
    for document in documents:
        if not document.valid_pdf or document.encrypted:
            continue
        if document.dispatch_outcome != "claimed" or not document.parser_id:
            continue
        if not document.folder_label or document.is_unlabelled_folder:
            continue
        if document.outcome_class not in ("validated", "review"):
            continue
        admissible = labels_by_parser.get(document.parser_id or "", frozenset())
        verdict = label_verdict(document, admissible)
        if verdict == TEMPLATE_CLAIM:
            template_claims.append(document)
        elif verdict == LABEL_UNMATCHED:
            mismatched[f"{document.folder_label} -> {document.parser_id}"].append(document)
    return mismatched, template_claims


def build_clusters(
    run: Run,
    *,
    volume_floor: int = NEW_PARSER_VOLUME_FLOOR,
    min_cluster: int = MIN_CLUSTER,
    allow_unattributed: bool = False,
) -> list[Cluster]:
    """Every cluster in a run, routed. Ranked by volume within each kind.

    Raises `UnattributedParsers` if any diagnosed document has no parser and
    `allow_unattributed` is not set - see that exception for why.
    """
    tokens = registered_bank_tokens()
    documents = list(run.values())
    clusters: list[Cluster] = []

    # --- unusable, first: these must not be counted as layout problems ------
    unusable = [d for d in documents if not d.valid_pdf or d.encrypted]
    if unusable:
        clusters.append(_card(
            "unusable_document", "invalid_or_encrypted", unusable, "R7_unusable_document",
            {"encrypted": sum(1 for d in unusable if d.encrypted),
             "invalid_pdf": sum(1 for d in unusable if not d.valid_pdf)},
        ))
    usable = [d for d in documents if d.valid_pdf and not d.encrypted]

    # --- W3-2's ranked queue: failure class x parser ------------------------
    diagnosed = [d for d in usable if d.primary_class is not None]
    unattributed = [d for d in diagnosed if not d.parser_id]
    if unattributed and not allow_unattributed:
        raise UnattributedParsers(
            f"{len(unattributed)} of {len(diagnosed)} diagnosed documents carry "
            "no parser_id, so a failure-class x parser view cannot be built.\n"
            "This is the H3_SCHEMA 5.4 cache-hit hole. A run emitted before "
            "the #TELCOV fix has it on every cache-served document; a run "
            "emitted after it has it only where the identity reconstruction "
            "refused to name one parser.\n"
            "  --enrich <run_dir>        recover parser identity by content "
            "hash from a run that dispatched these documents live (for a run "
            "from before that fix)\n"
            "  --allow-unattributed      build the view anyway; the affected "
            "rows are labelled '(parser unknown)' explicitly"
        )
    cells: dict[tuple[str, str], list[Document]] = defaultdict(list)
    for document in diagnosed:
        cells[(document.primary_class, document.parser_id or UNATTRIBUTED)].append(document)
    for (failure_class, parser), group in sorted(
        cells.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        clusters.append(_card(
            "withheld_check_cell", f"{failure_class} x {parser}", group,
            "R1_claimed_but_withheld",
            {"failure_class": failure_class,
             "parser": parser,
             "top_codes": dict(Counter(
                 code for d in group for code in d.diagnostics.get("codes") or []
             ).most_common(6)),
             "adb_checks_failed": dict(Counter(
                 check for d in group
                 for check in d.diagnostics.get("adb_checks_failed") or []
             ).most_common(6))},
        ))

    # --- parser crashes (W3-1 owns the fix; this routes them to a human) ----
    crashes: dict[str, list[Document]] = defaultdict(list)
    for document in usable:
        for parser, _stage, exception in document.exceptions:
            crashes[f"{parser}:{exception}"].append(document)
    for key, group in sorted(crashes.items(), key=lambda item: (-len(item[1]), item[0])):
        clusters.append(_card("parser_crash", key, group, "R8_parser_defect"))

    # --- unclaimed, grouped by the analyst's folder label -------------------
    unclaimed = [
        d for d in usable
        if d.dispatch_outcome in ("unclaimed", "ambiguous")
        and d.outcome_class != "deferred"
    ]
    by_folder: dict[str, list[Document]] = defaultdict(list)
    unlabelled: list[Document] = []
    for document in unclaimed:
        if document.folder_label is None:
            by_folder["(folder labels unavailable)"].append(document)
        elif document.is_unlabelled_folder:
            unlabelled.append(document)
        else:
            by_folder[document.folder_label].append(document)

    tail: dict[str, list[Document]] = defaultdict(list)
    for folder, group in sorted(by_folder.items(), key=lambda item: (-len(item[1]), item[0])):
        registered = bank_is_registered(folder, tokens)
        if registered:
            rule_id = "R2_known_bank_unseen_layout"
        elif len(group) >= volume_floor:
            rule_id = "R3_unregistered_bank_volume"
        else:
            rule_id = "R4_unregistered_bank_tail"
        if len(group) < min_cluster:
            tail[rule_id].extend(group)
            continue
        clusters.append(_card(
            "unclaimed_bank_folder", folder, group, rule_id,
            {"bank_has_registered_parser": registered,
             "volume_floor": volume_floor,
             "layout_stability": "unmeasured",
             "near_miss_parsers": dict(Counter(
                 name for d in group for name in d.near_miss
             ).most_common(5))},
        ))
    for rule_id, group in sorted(tail.items()):
        clusters.append(_card(
            "unclaimed_bank_folder", f"(tail: clusters under {min_cluster})",
            group, rule_id,
            {"folders": len({d.folder_label for d in group}),
             "bank_has_registered_parser": rule_id == "R2_known_bank_unseen_layout"},
        ))

    if unlabelled:
        clusters.append(_card(
            "unclaimed_unlabelled", "unlabelled folders", unlabelled, "R5_unlabelled_mix",
            {"folders": dict(Counter(d.folder_label for d in unlabelled).most_common()),
             "near_miss_parsers": dict(Counter(
                 name for d in unlabelled for name in d.near_miss
             ).most_common(5))},
        ))

    # --- claims a human would want to look at -------------------------------
    claimed = [d for d in usable if d.dispatch_outcome == "claimed" and d.parser_id]
    unlabelled_claims = [d for d in claimed if d.folder_label and d.is_unlabelled_folder]
    if unlabelled_claims:
        clusters.append(_card(
            "unlabelled_folder_claims", "claims in unlabelled folders",
            unlabelled_claims, "R10_unlabelled_folder_claims",
            {"parsers": dict(Counter(d.parser_id for d in unlabelled_claims).most_common(8))},
        ))

    # The label question, ruled on by `label_check` so that the workspace
    # header and this cluster read one verdict per document.
    mismatched, _template_claims = label_check(documents)
    for key, group in sorted(mismatched.items(), key=lambda item: (-len(item[1]), item[0])):
        clusters.append(_card("label_disagreement", key, group, "R6_label_disagreement"))

    # --- advisory signals: a policy question, never a mechanical route ------
    flagged = [d for d in usable if d.truncated_page_count]
    if flagged:
        clusters.append(_card(
            "advisory_flag", "truncation flagged", flagged, "R9_advisory_flag",
            {"still_validated": sum(1 for d in flagged if d.outcome_class == "validated")},
        ))

    return clusters


def workspace(run: Run, **kwargs) -> dict:
    clusters = build_clusters(run, **kwargs)
    unattributed = sum(
        cluster.documents for cluster in clusters
        if cluster.kind == "withheld_check_cell" and cluster.evidence.get("parser") == UNATTRIBUTED
    )
    # Ranked pairs, not a bare total: the rule that fills this class is "the
    # claim published no issuer", so a BANK-specific parser that ever lands
    # here is on the page instead of inside a bucket total. That is the same
    # thing `discovery.report`'s `template_claim_pairs` does with the same
    # census caveat (§DISCOBS DO4: five registrations can publish `bank=None`
    # by design, and nothing enforces that they are all platform-named).
    _mismatched, template_claims = label_check(list(run.values()))
    template_pairs = Counter(
        (d.folder_label, d.parser_id) for d in template_claims
    )
    by_disposition = Counter(cluster.disposition for cluster in clusters)
    documents_by_disposition: Counter = Counter()
    for cluster in clusters:
        documents_by_disposition[cluster.disposition] += cluster.documents
    return {
        "run_id": run.run_id,
        "documents": len(run),
        "telemetry_records": run.records,
        "duplicate_records_collapsed": max(0, run.records - len(run)),
        "folder_labels_available": run.folder_labels_available,
        "parser_enrichment_runs": list(run.enrichment_runs),
        "unattributed_documents": unattributed,
        "template_claim_documents": len(template_claims),
        "template_claim_pairs": [
            {"folder": folder, "parser": parser, "documents": count}
            for (folder, parser), count in template_pairs.most_common()
        ],
        "dispositions": dict(by_disposition),
        "documents_by_disposition": dict(documents_by_disposition.most_common()),
        "clusters": [cluster.as_dict() for cluster in clusters],
    }


def render(space: dict, *, top: int = 40) -> str:
    """ASCII only, same reason the other CLI reports are."""
    lines = [
        f"adjudication workspace  run {space['run_id']}",
        f"{space['documents']} distinct documents "
        f"(from {space['telemetry_records']} telemetry records; "
        f"{space['duplicate_records_collapsed']} duplicate-hash records collapsed)",
    ]
    if not space["folder_labels_available"]:
        lines.append(
            "  NOTE rows.csv absent: folder-keyed clusters are unavailable "
            "(parser- and check-keyed clusters are unaffected)"
        )
    if space["parser_enrichment_runs"]:
        lines.append(
            "  NOTE parser identity joined by content hash from: "
            + ", ".join(space["parser_enrichment_runs"])
        )
    if space.get("unattributed_documents"):
        lines.append(
            f"  WARNING --allow-unattributed: {space['unattributed_documents']} "
            "diagnosed documents have no parser and are grouped under "
            f"'{UNATTRIBUTED}'; those rows answer no class x parser question"
        )
    if space.get("template_claim_documents"):
        lines.append(
            f"  NOTE {space['template_claim_documents']} claims name no issuer "
            "(a document TEMPLATE, not a bank) and are outside the label check: "
            "a folder's"
        )
        lines.append(
            "       bank name can neither agree nor disagree with them. DO NOT "
            "rename the parser after the folder (W3 U4.1)."
        )
        for pair in space.get("template_claim_pairs") or []:
            lines.append(
                f"       {pair['folder']} -> {pair['parser']}   "
                f"{pair['documents']}"
            )
    lines.extend(["", "documents by disposition"])
    total = space["documents"]
    for name, count in space["documents_by_disposition"].items():
        share = f"{count / total:6.1%}" if total else "     -"
        lines.append(f"  {name:<24}{count:>7}   {share}")

    lines.extend(["", f"clusters ({len(space['clusters'])}), ranked by volume", ""])
    lines.append(f"  {'kind':<24}{'cluster':<34}{'docs':>6}  disposition / rule")
    ranked = sorted(space["clusters"], key=lambda c: -c["documents"])[:top]
    for cluster in ranked:
        key = cluster["key"]
        if len(key) > 32:
            key = key[:31] + "~"
        lines.append(
            f"  {cluster['kind']:<24}{key:<34}{cluster['documents']:>6}  "
            f"{cluster['disposition']} / {cluster['rule']}"
        )
    if len(space["clusters"]) > top:
        lines.append(f"  ... {len(space['clusters']) - top} smaller clusters omitted")

    human = [c for c in space["clusters"] if c["disposition"] == "needs_human_review"]
    lines.extend(["", f"human queue ({len(human)} clusters, "
                      f"{sum(c['documents'] for c in human)} documents)"])
    for cluster in sorted(human, key=lambda c: -c["documents"]):
        lines.append(f"  {cluster['key']:<40}{cluster['documents']:>6}  {cluster['rule']}")
    if not human:
        lines.append("  (none)")
    return "\n".join(lines)


WORKSPACE_COLUMNS = (
    "kind", "cluster", "documents", "proposed_disposition", "rule",
    "adjudicated_disposition", "adjudicator", "note",
)


def write_workspace(directory: Path, space: dict) -> tuple[Path, Path]:
    """`adjudication.json` (full cards) + `adjudication.csv` (the worksheet).

    The CSV carries the proposal and three EMPTY columns. A human fills
    `adjudicated_disposition` and the file becomes the record of the ruling;
    nothing here ever writes into them, because the tool does not adjudicate.
    """
    import csv

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "adjudication.json"
    csv_path = directory / "adjudication.csv"
    json_path.write_text(json.dumps(space, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(WORKSPACE_COLUMNS))
        writer.writeheader()
        for cluster in sorted(space["clusters"], key=lambda c: -c["documents"]):
            writer.writerow({
                "kind": cluster["kind"],
                "cluster": cluster["key"],
                "documents": cluster["documents"],
                "proposed_disposition": cluster["disposition"],
                "rule": cluster["rule"],
                "adjudicated_disposition": "",
                "adjudicator": "",
                "note": "",
            })
    return json_path, csv_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="W3-4 adjudication workspace over a finished discovery run.")
    parser.add_argument("run", help="A discovery run directory.")
    parser.add_argument(
        "--enrich", action="append", default=[], metavar="RUN_DIR",
        help="Recover parser identity by content hash from another run. Only "
             "for runs emitted before #TELCOV: a cache-served record has "
             "carried its own reconstructed claim since then.")
    parser.add_argument(
        "--allow-unattributed", action="store_true",
        help="Build the class x parser view even when some diagnosed documents "
             "have no parser; those rows are labelled '(parser unknown)'.")
    parser.add_argument("--volume-floor", type=int, default=NEW_PARSER_VOLUME_FLOOR)
    parser.add_argument("--min-cluster", type=int, default=MIN_CLUSTER)
    parser.add_argument("--write", action="store_true",
                        help="Write adjudication.json + adjudication.csv into the run dir.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args(argv)

    run = load_run(args.run, enrich_parsers_from=args.enrich)
    try:
        space = workspace(
            run,
            volume_floor=args.volume_floor,
            min_cluster=args.min_cluster,
            allow_unattributed=args.allow_unattributed,
        )
    except UnattributedParsers as error:
        print(f"discovery.adjudication: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(space, indent=2, sort_keys=True))
    else:
        print(render(space, top=args.top))
    if args.write:
        json_path, csv_path = write_workspace(Path(args.run), space)
        print(f"\nwritten {json_path}\nwritten {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
