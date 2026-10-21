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


#: P22-TRUTHTABLE. The two labels that are DERIVED rather than carried: R is
#: "the offline ladder (Tesseract included) produced no text at all", and U is
#: a Tesseract read no reader claimed. Both are the definitions the Phase-2
#: baseline was measured with (`PHASE2-RULES.md` §"Baseline triggers"),
#: restated here so the report and that baseline cannot drift apart.
#:
#: R has two spellings (plan D19). Until slice S5 of the model-code removal
#: the runner recorded it as the deferral `deferred_visual_ocr`; since S5 it
#: records `refused:insufficient_evidence` with `source_path` `none` (the
#: visual rung the deferral waited for is gone). R counts BOTH, so its meaning
#: and its count are unchanged across the move. The new spelling was measured
#: absent from every local historical `rows.csv` before S5 (0 of 201,769 rows
#: in 170 discovery runs), so no historical R moves.
R_LABEL_REASON = "deferred_visual_ocr"
R_REFUSED_CLASS = "refused"
R_REFUSED_REASON = "insufficient_evidence"
R_REFUSED_SOURCE = "none"
U_LABEL_SOURCE = "local_tesseract"


def offline_ladder_read_nothing(row) -> bool:
    """Trigger R for one row, in either spelling (see `R_LABEL_REASON`)."""
    if row.outcome_reason == R_LABEL_REASON:
        return True
    return (row.outcome_class == R_REFUSED_CLASS and row.outcome_reason == R_REFUSED_REASON
            and row.source_path == R_REFUSED_SOURCE)

#: The funnel stage columns, in `ROW_FIELDS` order. One list, read by the
#: research table and by nothing else in this module.
STAGE_FIELDS = ("stage_extract", "stage_evidence", "stage_geometry",
                "stage_layout", "stage_candidate", "stage_verdict")


def _sha_index(rows: list) -> tuple[list[str], dict[str, list]]:
    """`(shas in run order, sha -> its rows)`.

    The archive's denominator is DOCUMENTS, not rows: one document that
    appears twice under two paths is one sha and one document, and counting
    its rows would inflate every denominator this module prints. The first row
    of a sha (run order) is the one whose recorded facts are reported.
    """
    order: list[str] = []
    groups: dict[str, list] = {}
    for row in rows:
        sha = row.content_sha256
        if sha not in groups:
            groups[sha] = []
            order.append(sha)
        groups[sha].append(row)
    return order, groups


def _classification_block(shas: list[str], groups: dict[str, list]) -> dict:
    """The DISJOINT primary classification over a set of documents (D2, case 8).

    `sum` is printed BESIDE `population` rather than instead of it, so the
    claim "these buckets account for exactly this population" is a visible
    arithmetic identity in the report and not a promise in a docstring.
    `disjoint` is False the moment two rows of one document disagree about its
    kind — the way a disjointness claim actually dies.
    """
    by_kind: Counter = Counter()
    triples: Counter = Counter()
    disjoint = True
    for sha in shas:
        rows = groups[sha]
        if len({row.document_class for row in rows}) != 1:
            disjoint = False
        first = rows[0]
        by_kind[first.document_class] += 1
        triples[(first.document_class, first.class_modality, first.class_tier)] += 1
    return {
        "population": len(shas),
        "sum": sum(by_kind.values()),
        "disjoint": disjoint,
        "by_kind": dict(by_kind.most_common()),
        "kind_modality_tier": [[kind, modality, tier, count]
                               for (kind, modality, tier), count in sorted(triples.items())],
    }


def summarize(rows: list, *, mode: str, run_id: str, inventory=None,
              cache_stats: dict | None = None,
              escalation_budget: int | None = None,
              escalations_used: int = 0,
              research_partition: str = "") -> dict:
    # Imported here, not at module scope: the runner owns the row vocabulary
    # (as it owns `visual_rung`'s), and pulling `analysis.pipeline` in behind
    # every `import discovery.report` to read one string constant is a cost the
    # rollups do not need to impose on their readers.
    from layout.refusals import ACCOUNT_KINDS

    from .runner import PARSER_ID_LIVE_DETECT, PARSER_ID_UNAVAILABLE, RESEARCH_TRIGGERS

    # P22-TRUTHTABLE (D7). The HEADLINE population excludes research rows BY
    # CONSTRUCTION — not by a filter an operator can forget, and not by a flag
    # on the row that a rollup might not read: a research read is an artifact
    # the run of record can never select, so a coverage figure that counted it
    # would be a number about a partition that is not historical truth. In
    # every production run `research_partition` is empty on every row and this
    # partition is the identity, which is why the union replay is
    # byte-identical.
    all_rows = list(rows)
    research_rows = [r for r in all_rows if getattr(r, "research_partition", "")]
    rows = [r for r in all_rows if not getattr(r, "research_partition", "")]

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

    # ----------------------------------------------------------------------
    # P22-TRUTHTABLE items 3, 4, 5: the two denominators, the disjoint primary
    # classification, and the overlapping diagnostic labels beside it.
    # ----------------------------------------------------------------------
    shas, groups = _sha_index(rows)
    validated_shas = {
        sha for sha in shas
        if any(row.outcome_class == "validated" for row in groups[sha])
    }
    unresolved_shas = [sha for sha in shas if sha not in validated_shas]

    #: R11's FIRST denominator: validated documents over the corpus itself.
    #: Printed first, everywhere, and never replaced by the one below it.
    raw_coverage = {
        "validated": len(validated_shas),
        "denominator": len(shas),
        "coverage": (len(validated_shas) / len(shas)) if shas else 0.0,
    }

    #: R12's CCL, in the only form this process can honestly produce: the
    #: classifier's PROPOSAL. The adjudicated form is read from the sealed
    #: truth store, which no module under `discovery/` may touch (the leakage
    #: firewall), so the runner says so by name rather than printing a proxy
    #: under the adjudicated heading. `tools/truth_report.py` does the join.
    #: The primary CCL is the DEPOSIT-account complete statements — the kinds
    #: this engine targets; card, loan and brokerage are their own rows and
    #: are never folded in (R12).
    by_account_kind = {kind: {"proposed_complete": 0, "validated": 0} for kind in ACCOUNT_KINDS}
    for sha in shas:
        first = groups[sha][0]
        if first.document_class != "STATEMENT_COMPLETE":
            continue
        bucket = by_account_kind.setdefault(
            first.class_account_kind, {"proposed_complete": 0, "validated": 0})
        bucket["proposed_complete"] += 1
        if sha in validated_shas:
            bucket["validated"] += 1
    deposit = by_account_kind["deposit"]
    ccl_classifier_proposed = {
        "proposed_ccl": deposit["proposed_complete"],
        "validated_in_proposed_ccl": deposit["validated"],
        "coverage": (deposit["validated"] / deposit["proposed_complete"])
                    if deposit["proposed_complete"] else 0.0,
        "by_account_kind": by_account_kind,
    }

    #: Case 7. A validated document that did NOT classify `STATEMENT_COMPLETE`
    #: is either a classifier defect or a finding, and either way it must be
    #: NAMED. Counted by KIND here — a summary a report reader shares must not
    #: carry document identities; the per-sha list is the private census
    #: and the closure record.
    exception_kinds = Counter(
        groups[sha][0].document_class for sha in validated_shas
        if groups[sha][0].document_class != "STATEMENT_COMPLETE"
    )

    #: Case 8. The OVERLAPPING labels, in their own table, with no total. A
    #: document may carry several at once (a Tesseract read that no reader
    #: claimed, is Class B, and is truncation-flagged is all three), so a sum
    #: of this table would over-count the population it describes — which is
    #: precisely the arithmetic "755 unresolved" existed to prevent. There is
    #: no `sum` key and no `total` key here on purpose, and a test asserts the
    #: rendered block prints neither word.
    failure_class_labels = Counter(
        groups[sha][0].failure_class for sha in shas if groups[sha][0].failure_class
    )
    diagnostic_labels = {
        "note": "overlapping; never summed",
        "R": sum(1 for sha in shas
                 if any(offline_ladder_read_nothing(r) for r in groups[sha])),
        "U": sum(1 for sha in shas
                 if any(r.source_path == U_LABEL_SOURCE and r.dispatch_outcome != "claimed"
                        for r in groups[sha])),
        "failure_class": {name: failure_class_labels.get(name, 0) for name in ("A", "B", "C")},
        "truncation_flagged": sum(1 for sha in shas
                                  if any(r.truncated_pages for r in groups[sha])),
        "refused": sum(1 for sha in shas
                       if any(r.outcome_class == "refused" for r in groups[sha])),
        # Surfaced by the extraction gate as an advisory SIGNAL, never as a
        # row column (Ruling B keeps it surface-only), so this table says
        # where to look instead of printing a number it cannot compute.
        "density_surfaced": "not carried on rows",
    }

    #: D7. The research partition's own table, beside the headline and never
    #: inside it. `attempted` counts the documents the router actually admitted
    #: the research trigger for; a population miss and a holdout refusal are
    #: their own lines, because "we did not study this" and "we studied it and
    #: it produced nothing" are different findings. Row-driven, and kept when
    #: the research mode was removed (slice S5): a historical research run's
    #: rows still summarize exactly as before; a run today has no research row,
    #: so `research` is None and `research_rows` 0.
    attempted = [r for r in research_rows if r.escalation_trigger in RESEARCH_TRIGGERS]
    research = None
    if research_partition or research_rows:
        research = {
            "partition": research_partition or (
                research_rows[0].research_partition if research_rows else ""),
            "rows": len(research_rows),
            "attempted": len(attempted),
            "skipped_not_in_population": sum(
                1 for r in research_rows
                if r.outcome_reason == "research_skipped_not_in_population"),
            "refused_holdout": sum(
                1 for r in research_rows if r.outcome_reason == "research_refused_holdout"),
            "evidence": dict(Counter(
                r.stage_evidence for r in attempted if r.stage_evidence != "not_attempted")),
            "e_gate": dict(Counter(
                r.evidence_quality for r in attempted if r.evidence_quality != "none")),
            "stages": {name: dict(Counter(getattr(r, name) for r in attempted))
                       for name in STAGE_FIELDS},
            "outcome": dict(Counter(r.outcome_class for r in research_rows)),
        }

    return {
        "run_id": run_id,
        "mode": mode,
        "documents": total,
        "raw_coverage": raw_coverage,
        # R11: named, not computed. The sealed store is behind the firewall.
        "ccl_adjudicated": "not available in this process",
        "ccl_classifier_proposed": ccl_classifier_proposed,
        "document_class": {
            "archive": _classification_block(shas, groups),
            "unresolved": _classification_block(unresolved_shas, groups),
        },
        "validated_exceptions": {
            "count": sum(exception_kinds.values()),
            "by_kind": dict(exception_kinds.most_common()),
        },
        "diagnostic_labels": diagnostic_labels,
        "research": research,
        "research_rows": len(research_rows),
        # A report spanning a vocabulary change is not comparing like with
        # like; `render_report` warns when it sees more than one.
        "unresolved_taxonomy_versions": dict(sorted(
            Counter(str(getattr(r, "unresolved_taxonomy_version", "")) for r in all_rows).items()
        )),
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
        # asked for, and what it bought. Empty in every offline mode, so in
        # every run since the rungs were removed (slices S2 and S5); the
        # roll-ups below keep their keys so a historical run summarizes as it did.
        "visual_rung": dict(
            Counter(
                r.visual_rung for r in rows
                if getattr(r, "visual_rung", "not_attempted") != "not_attempted"
            ).most_common()
        ),
        # P21-ROUTING (Phase 2.1). The SAME shape as `visual_rung` above, for
        # the Paddle rung — empty in every mode but the retired
        # `--scanned-paddle` / `--research-paddle` (slice S5).
        "paddle_rung": dict(
            Counter(
                r.paddle_rung for r in rows
                if getattr(r, "paddle_rung", "not_attempted") != "not_attempted"
            ).most_common()
        ),
        "escalation_extractor": dict(
            Counter(
                r.escalation_extractor for r in rows
                if getattr(r, "escalation_extractor", "")
            ).most_common()
        ),
        # P20-ROUTER (Phase 2.0). `escalation_budget` is `None` (unbounded)
        # unless the caller set one (`discovery/cli.py::run()` did, for the
        # retired escalation modes only; since slice S5 it passes None and 0);
        # `failure_class`/`escalation_trigger` are measurement rollups over
        # EVERY enumerated row, and `escalation_trigger` is empty in every
        # offline mode exactly like `visual_rung` above.
        "escalation_budget": escalation_budget,
        "escalations_used": escalations_used,
        "failure_class": dict(
            Counter(
                r.failure_class for r in rows if getattr(r, "failure_class", "")
            ).most_common()
        ),
        "escalation_trigger": dict(
            Counter(
                r.escalation_trigger for r in rows if getattr(r, "escalation_trigger", "")
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

    # P22-TRUTHTABLE (R11/R12): BOTH denominators, the raw one FIRST and never
    # replaced. `ccl_adjudicated` is named as unavailable rather than
    # approximated: the adjudicated set lives in the sealed truth store and no
    # module under `discovery/` may read it.
    raw = summary.get("raw_coverage") or {"validated": 0, "denominator": 0, "coverage": 0.0}
    proposed = summary.get("ccl_classifier_proposed") or {}
    lines.append("")
    lines.append(
        f"raw coverage              {raw['validated']} / {raw['denominator']}"
        f"   {raw['coverage']:.1%}   (validated documents / the corpus; never replaced)"
    )
    lines.append(f"  ccl_adjudicated         {summary.get('ccl_adjudicated', '')}"
                 "   (tools/truth_report.py joins the sealed store)")
    if proposed:
        lines.append(
            f"  ccl_classifier_proposed {proposed['validated_in_proposed_ccl']} / "
            f"{proposed['proposed_ccl']}   {proposed['coverage']:.1%}"
            "   (deposit-account complete statements, classifier-proposed)"
        )
        for kind, bucket in sorted(proposed["by_account_kind"].items()):
            if kind == "deposit":
                continue
            lines.append(
                f"    account kind {kind:<12}{bucket['validated']:>7} / "
                f"{bucket['proposed_complete']}   (reported separately, never folded in)"
            )
    if summary.get("research_rows"):
        lines.append(
            f"  research rows excluded  {summary['research_rows']:>7}"
            "   (a research partition is never historical truth)"
        )

    if summary["outcome"]:
        lines.append("outcome")
        # deferred is counted above; `refused` (R11) is a terminal class and
        # belongs on this list, unranked though it is.
        for key in ("validated", "review", "withheld", "failed", "refused"):
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

    if summary.get("paddle_rung"):
        lines.append("Paddle OCR rung (remote_paid, explicit opt-in only)")
        for key, count in summary["paddle_rung"].items():
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

    # P22-TRUTHTABLE (D2, case 8): the DISJOINT primary classification, with
    # its arithmetic identity printed rather than promised.
    classes = summary.get("document_class") or {}
    if classes:
        lines.append("")
        lines.append("document classification (disjoint: exactly one kind per document)")
        for scope in ("archive", "unresolved"):
            block = classes[scope]
            lines.append(
                f"  disjoint sum over {scope}: {block['sum']} == {block['population']}"
                + ("" if block["disjoint"] else "   WARNING two rows of one document disagree")
            )
            for kind, count in block["by_kind"].items():
                lines.append(_bar(f"  {scope[:3]} {kind}", count, block["population"]))
        lines.append("  kind x modality x tier (archive)")
        for kind, modality, tier, count in classes["archive"]["kind_modality_tier"]:
            lines.append(f"    {kind:<22}{modality:<20}{tier:<12}{count:>7}")
        exceptions = summary.get("validated_exceptions") or {}
        if exceptions.get("count"):
            lines.append(
                f"  validated documents NOT classified STATEMENT_COMPLETE: {exceptions['count']}"
                "   (a finding or a classifier defect; named by sha16 in the private census)"
            )
            for kind, count in exceptions["by_kind"].items():
                lines.append(f"    {kind:<30}{count:>7}")

    research = summary.get("research")
    if research:
        lines.append("")
        lines.append(f"research partition {research['partition']}"
                     "   (excluded from every headline figure above, by construction)")
        lines.append(_bar("rows", research["rows"], research["rows"]))
        lines.append(_bar("attempted", research["attempted"], research["rows"]))
        lines.append(_bar("skipped, not in population",
                          research["skipped_not_in_population"], research["rows"]))
        lines.append(_bar("refused, holdout", research["refused_holdout"], research["rows"]))
        for name in STAGE_FIELDS:
            body = " ".join(f"{k} {v}" for k, v in sorted(research["stages"][name].items()))
            lines.append(f"    {name:<24}{body}")
        for label in ("evidence", "e_gate"):
            body = " ".join(f"{k} {v}" for k, v in sorted(research[label].items()))
            lines.append(f"    {label:<24}{body}")

    versions = summary.get("unresolved_taxonomy_versions") or {}
    if len(versions) > 1:
        lines.append("")
        lines.append(
            "WARNING mixed unresolved-taxonomy versions: "
            + ", ".join(f"v{k} {v}" for k, v in sorted(versions.items()))
            + " — class counts either side of a vocabulary change are not comparable"
        )

    inventory = summary.get("inventory") or {}
    if inventory:
        lines += [
            "",
            f"inventory  {inventory['files']:,} files | {inventory['pdfs']:,} PDFs | "
            f"{inventory['total_bytes']:,} bytes | "
            f"{inventory['pinned']} pinned + {inventory['discovery']} discovery",
        ]

    # LAST, deliberately. These labels OVERLAP — one document may carry
    # several — so the block prints no total of any kind, and printing it last
    # keeps a neighbouring section's total from being read as this table's.
    labels = summary.get("diagnostic_labels") or {}
    if labels:
        lines.append("")
        lines.append("diagnostic labels (overlapping; never summed)")
        lines.append(f"  R  offline ladder produced no text     {labels['R']:>7}")
        lines.append(f"  U  tesseract read, no reader claimed   {labels['U']:>7}")
        for name in ("A", "B", "C"):
            lines.append(f"  failure class {name}                        "
                         f"{labels['failure_class'][name]:>7}")
        lines.append(f"  truncation flagged                     {labels['truncation_flagged']:>7}")
        lines.append(f"  refused                                {labels['refused']:>7}")
        lines.append(f"  density surfaced                       {labels['density_surfaced']}")
    return "\n".join(lines)


ROW_FIELDS = [
    "relative_path", "folder_label", "content_sha256", "byte_size", "valid_pdf",
    "encrypted", "classification", "page_count", "likely_account_count",
    "dedup_status", "duplicate_of", "source_path", "source_model",
    "truncated_pages", "parser_id", "parser_score", "dispatch_outcome",
    "parser_id_source",
    "candidates", "attempted", "near_miss", "parser_exceptions",
    "outcome_class", "outcome_reason", "error_type",
    # `account_count` is the ANALYSIS's published count and sits beside
    # `account_last4` because it is the column that carries the fact when
    # `account_last4` must be empty (L1-C18).
    "statement_bank", "account_last4", "account_count", "cache_ocr", "cache_analysis",
    "cache_visual", "visual_rung", "elapsed_ms",
    # P20-ROUTER (Phase 2.0). Appended at the END so an existing reader that
    # selects columns by name is unaffected; see `discovery/runner.py`'s
    # `DocumentRow` docstring for what each carries.
    "failure_class", "escalation_trigger", "evidence_quality", "escalation_refused",
    # P21-ROUTING (Phase 2.1). Likewise appended at the END.
    "paddle_rung", "cache_paddle", "escalation_extractor", "evidence_sha256",
    "paddle_provider", "paddle_execution_class", "offline_source_model",
    # P21-ROUTING closure (MAJOR-1, MINOR-2). Likewise appended at the END.
    "cache_finding", "paddle_refusal_reason",
    # P22-TRUTHTABLE (Phase 2.2, case 25). APPENDED, never reordered: a reader
    # that selects columns by name is unaffected, and one that reads by
    # position keeps every position it had. Six funnel stages, four technical
    # telemetry columns plus the per-document peak RSS, the research
    # partition, the seven taxonomy layers with their primary pair and
    # version, and the classifier's verdict as a recorded fact. No cost, rate,
    # price or billing column anywhere — out of scope by ruling, and grepped.
    "stage_extract", "stage_evidence", "stage_geometry", "stage_layout",
    "stage_candidate", "stage_verdict",
    "bytes_up", "bytes_down", "inference_ms", "vram_mb", "peak_rss_mb",
    "research_partition",
    "reason_l0", "reason_l1", "reason_l2", "reason_l3", "reason_l4", "reason_l5",
    "reason_l6", "primary_reason_layer", "primary_reason", "unresolved_taxonomy_version",
    "document_class", "class_sub_kind", "class_modality", "class_account_kind",
    "class_tier", "class_signals", "class_version", "completeness_findings",
    "classifier_exception",
    # P23-EGATE (Phase 2.3, cell E). APPENDED, never reordered, for the same
    # reason every block above was: a reader that selects columns by name is
    # unaffected and one that reads by position keeps every position it had.
    # Thirteen extraction-quality columns, in `ocr.extraction_quality.
    # EQ_ROW_COLUMNS` order — which is the one table that says which figure
    # and which per-document fold each column carries, so the row and the
    # census cannot disagree about what a column means. MEASURED and
    # VERSIONED (`eq_version`), admitted as NOTHING: no trigger, no verdict,
    # no router input reads any of them (Ruling B's discipline; the router's
    # own module does not import the one that computes them). Empty on every
    # production row by construction — no production partition carries
    # extractor evidence. No cost, rate, price or billing column here either.
    "eq_version", "eq_word_count", "eq_density", "eq_rec_mean", "eq_rec_p10",
    "eq_money_rate", "eq_lexicon_rate", "eq_garbage_rate", "eq_line_height_cv",
    "eq_right_edge_residual", "eq_ink_outside_boxes", "eq_orientation_votes", "eq_class",
    # P23-AGREE (Phase 2.3 cell X, card item 2). APPENDED, never reordered,
    # exactly like the block above: the native<->extractor agreement
    # statistics and the geometry census of the document, EMPTY on every row
    # that does not carry both readings. See `discovery/runner.py`'s
    # `DocumentRow` for what each column carries and how it is folded, and
    # `layout/agreement.py` for what each measures. Review evidence only —
    # no threshold, no class, no verdict, and (still) no cost column anywhere.
    "agree_version", "agree_pages", "agree_matched_native", "agree_matched_paddle",
    "agree_char", "agree_amounts", "agree_dates", "agree_unmatched_table_density",
    "agree_frame_mismatch", "geom_rotation", "geom_skew_deg", "geom_page_size",
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
