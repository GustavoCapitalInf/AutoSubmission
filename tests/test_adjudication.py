"""W3-4: the adjudication workspace, the routing rules, and coverage movement.

Every test builds its own synthetic run directory from telemetry records, so
nothing here needs the archive, the corpus, or a previous run's artifacts.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from discovery.adjudication import (
    DISPOSITIONS,
    MIN_CLUSTER,
    NEW_PARSER_VOLUME_FLOOR,
    RULES,
    UNATTRIBUTED,
    UnattributedParsers,
    build_clusters,
    render,
    workspace,
    write_workspace,
)
from discovery.compare import LADDER, compare, direction
from discovery.compare import render as render_movement
from discovery.evidence import (
    ADMISSIBLE_ROW_COLUMNS,
    DERIVED_ROW_COLUMNS,
    bank_is_registered,
    label_agrees,
    load_run,
    parser_index,
    registered_bank_tokens,
    registration_labels,
)

ROOT = Path(__file__).resolve().parents[1]


def _record(sha: str, **kw) -> dict:
    """One telemetry record, in the shape the emitters write."""
    diagnostics = kw.get("diagnostics")
    return {
        "telemetry_version": 1,
        "record_id": sha[:8],
        "run_id": kw.get("run_id", "run-A"),
        "emitted_at": "2026-08-07T00:00:00+00:00",
        "emitter": "discovery",
        "job_id": None,
        "document": {
            "content_sha256": sha,
            "byte_size": kw.get("byte_size", 1000),
            "page_count": kw.get("page_count", 4),
            "classification": kw.get("classification", "digital"),
            "valid_pdf": kw.get("valid_pdf", True),
            "encrypted": kw.get("encrypted", False),
            "malformed_page_count": 0,
            "likely_account_count": 1,
            "duplicate_of_prior_record": False,
        },
        "source": {
            "path": kw.get("source_path", "native"),
            "model": "native-pdf-text",
            "page_count": 4,
            "truncation": {
                "assessed": True,
                "truncated_page_count": kw.get("truncated", 0),
                "truncated_page_indices": [],
                "signals": [],
            },
        },
        "dispatch": {
            "source": kw.get("dispatch_source", "live"),
            "outcome": kw.get("dispatch_outcome", "claimed"),
            "parser_id": kw.get("parser_id"),
            "score": 1.0,
            "candidates": [],
            "attempted": [],
            "exceptions": kw.get("exceptions", []),
            "scores": kw.get("scores", []),
            "scores_floor": 0.0,
            "scores_capped": False,
            "registration_count": 46,
        },
        "stages": {},
        "models": {"calls": [], "cost": {"amount": 0.0, "unpriced_models": []}},
        "outcome": {
            "class": kw.get("outcome_class", "validated"),
            "reason": kw.get("outcome_reason", "approved"),
            "escalated": False,
            "error_type": None,
            "fallback_reason": None,
        },
        "diagnostics": diagnostics or {
            "evaluated": False, "diagnostics_version": 1, "primary_class": None,
            "classes": [], "codes": [], "adb_checks_failed": [],
            "integrity_flags": [], "summary_fields_absent": [], "counts": {},
            "unmapped": [],
        },
    }


def _withheld(sha: str, primary: str, parser: str, **kw) -> dict:
    return _record(
        sha, parser_id=parser, outcome_class="withheld", outcome_reason="withheld_adb",
        diagnostics={
            "evaluated": True, "diagnostics_version": 1, "primary_class": primary,
            "classes": [primary], "codes": [f"integrity:{primary}"],
            "adb_checks_failed": ["ledger_reconciles_to_closing"],
            "integrity_flags": [], "summary_fields_absent": [], "counts": {},
            "unmapped": [],
        },
        **kw,
    )


def _write_run(directory: Path, records: list[dict],
               folders: dict[str, str] | None = None,
               no_issuer: frozenset[str] = frozenset()) -> Path:
    """A run directory. `no_issuer` names the shas whose claiming parser
    published no issuer - the §U template registrations' shape (#TELCOV)."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "telemetry.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )
    if folders is not None:
        with (directory / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["relative_path", "folder_label", "content_sha256",
                            "dedup_status", "statement_bank", "account_last4"],
            )
            writer.writeheader()
            for sha, folder in folders.items():
                writer.writerow({
                    "relative_path": f"{folder}/secret-customer-name.pdf",
                    "folder_label": folder,
                    "content_sha256": sha,
                    "dedup_status": "unique",
                    "statement_bank": (
                        "" if sha in no_issuer else "EXTRACTED BANK LABEL"
                    ),
                    "account_last4": "1234",
                })
    return directory


# --- evidence loading --------------------------------------------------------


def test_documents_are_keyed_by_content_hash(tmp_path: Path):
    run = load_run(_write_run(tmp_path / "r", [
        _record("A" * 64), _record("B" * 64), _record("A" * 64),
    ]))
    assert len(run) == 2
    assert run.records == 3


def test_only_admissible_row_columns_ever_load(tmp_path: Path):
    """rows.csv carries paths, the extracted bank label and an account
    fragment. None of them may reach a W3-4 artifact.

    `statement_bank` is READ since #TELCOV and still never crosses: what
    crosses is one boolean about our own claim. This test is the guard for
    that, and it fails on the label's text rather than on a promise.
    """
    run = load_run(_write_run(
        tmp_path / "r", [_record("A" * 64)], folders={"A" * 64: "Chase"},
    ))
    document = run.documents["A" * 64]
    assert document.folder_label == "Chase"
    assert ADMISSIBLE_ROW_COLUMNS == ("content_sha256", "folder_label", "dedup_status")
    assert DERIVED_ROW_COLUMNS == ("statement_bank",)
    assert document.claim_names_issuer is True
    assert not hasattr(document, "statement_bank")
    blob = json.dumps(workspace(run), sort_keys=True)
    assert "secret-customer-name" not in blob
    assert "EXTRACTED BANK LABEL" not in blob
    assert "1234" not in blob


def test_a_run_without_rows_csv_still_loads(tmp_path: Path):
    run = load_run(_write_run(tmp_path / "r", [_record("A" * 64)]))
    assert run.folder_labels_available is False
    assert render(workspace(run)).startswith("adjudication workspace")


def test_parser_identity_is_recovered_by_hash_from_a_companion_run(tmp_path: Path):
    """The cache-hit hole (H3_SCHEMA 5.4), which is fatal for class x parser.

    The W3-2 baseline over the archive was served from the analysis cache: 614
    withheld documents, every one diagnosed, not one carrying a parser_id. The
    parser claim is a property of the document and the registry, so recovering
    it from another run over the same bytes is sound - and it is declared in
    the output, never silently merged.
    """
    live = _write_run(tmp_path / "live", [
        _record("A" * 64, parser_id="chase", dispatch_outcome="claimed"),
    ])
    cached = _write_run(tmp_path / "cached", [
        _withheld("A" * 64, "detail_coverage", None,
                  dispatch_outcome=None, dispatch_source="unavailable"),
    ])

    plain = load_run(cached)
    assert plain.documents["A" * 64].parser_id is None

    joined = load_run(cached, enrich_parsers_from=[live])
    document = joined.documents["A" * 64]
    assert document.parser_id == "chase"
    assert document.dispatch_outcome == "claimed"   # travels with the parser id
    assert document.parser_enriched_from == "run-A"
    assert joined.enrichment_runs == ("run-A",)


def test_enrichment_never_overwrites_a_real_claim(tmp_path: Path):
    live = _write_run(tmp_path / "live", [_record("A" * 64, parser_id="wells_fargo")])
    own = _write_run(tmp_path / "own", [_record("A" * 64, parser_id="chase")])
    document = load_run(own, enrich_parsers_from=[live]).documents["A" * 64]
    assert document.parser_id == "chase"
    assert document.parser_enriched_from is None


def test_parser_index_takes_the_first_run_that_dispatched(tmp_path: Path):
    first = _write_run(tmp_path / "1", [_record("A" * 64, parser_id="chase")])
    second = _write_run(tmp_path / "2", [_record("A" * 64, parser_id="wells_fargo")])
    assert parser_index([first, second])["A" * 64][0] == "chase"


#: A bank name no registration will ever answer to, for the tests that need
#: "unregistered" to stay true. See the note in
#: `test_registered_banks_are_read_from_the_live_registry`.
UNREGISTERED_BANK = "Thornbury Savings Bank"


# --- the registry is the source of truth for "do we support this bank" -------


def test_registered_banks_are_read_from_the_live_registry():
    tokens = registered_bank_tokens()
    assert len(tokens) > 40
    assert bank_is_registered("Chase", tokens)
    assert bank_is_registered("Bank of America", tokens)
    # DELIBERATELY FICTIONAL. This assertion needs a bank the registry does
    # not know, and naming a real one dates the test: it used to name
    # Huntington, and broke the day Huntington was registered (W3 §HUNT-CELL).
    # A bank that cannot be registered cannot break it again.
    assert not bank_is_registered(UNREGISTERED_BANK, tokens)


def test_a_parser_answers_to_its_registered_bank_name_not_just_its_id():
    """The false-misfiled guard. `td_us` is registered as "TD Bank", so a
    document filed under `TD Bank/` and claimed by `td_us` is in the RIGHT
    folder - matching the id alone called 28 correct statements misfiled."""
    labels = registration_labels()
    assert label_agrees("TD Bank", labels["td_us"])
    assert not label_agrees("Chase", labels["td_us"])


# --- routing rules -----------------------------------------------------------


def test_every_rule_proposes_a_disposition_from_the_closed_vocabulary():
    for rule in RULES.values():
        assert rule.disposition in DISPOSITIONS, rule.id
        assert rule.because, rule.id


def test_misfiled_is_reachable_only_by_a_human():
    """No rule proposes it: nothing in the evidence separates a misfiled
    document from an alias the matcher cannot see through. The vocabulary
    member stays, because that is what the human writes in the worksheet."""
    proposed = {rule.disposition for rule in RULES.values()}
    assert "misfiled" not in proposed
    assert "misfiled" in DISPOSITIONS


def test_a_claimed_but_withheld_cluster_is_variant_completeness(tmp_path: Path):
    records = [_withheld(f"{i:064d}", "detail_coverage", "chase") for i in range(9)]
    run = load_run(_write_run(tmp_path / "r", records))
    cells = [c for c in build_clusters(run) if c.kind == "withheld_check_cell"]
    assert len(cells) == 1
    assert cells[0].key == "detail_coverage x chase"
    assert cells[0].documents == 9
    assert cells[0].disposition == "variant_completeness"
    assert cells[0].rule == "R1_claimed_but_withheld"


def test_an_unclaimed_cluster_for_a_known_bank_is_a_variant(tmp_path: Path):
    shas = [f"{i:064d}" for i in range(6)]
    run = load_run(_write_run(
        tmp_path / "r",
        [_record(s, dispatch_outcome="unclaimed", parser_id=None,
                 outcome_class="failed") for s in shas],
        folders={s: "Chase" for s in shas},
    ))
    cluster = next(c for c in build_clusters(run) if c.key == "Chase")
    assert cluster.disposition == "variant_completeness"
    assert cluster.rule == "R2_known_bank_unseen_layout"
    assert cluster.evidence["bank_has_registered_parser"] is True


def test_an_unregistered_bank_over_the_floor_is_proposed_as_a_new_parser(tmp_path: Path):
    shas = [f"{i:064d}" for i in range(NEW_PARSER_VOLUME_FLOOR)]
    run = load_run(_write_run(
        tmp_path / "r",
        [_record(s, dispatch_outcome="unclaimed", parser_id=None,
                 outcome_class="failed") for s in shas],
        folders={s: UNREGISTERED_BANK for s in shas},
    ))
    cluster = next(c for c in build_clusters(run) if c.key == UNREGISTERED_BANK)
    assert cluster.disposition == "new_parser_candidate"
    assert cluster.rule == "R3_unregistered_bank_volume"
    # A proposal, not a decision: the other half of the test is unmeasurable.
    assert cluster.evidence["layout_stability"] == "unmeasured"
    assert "PROPOSAL ONLY" in cluster.because


def test_an_unregistered_bank_under_the_floor_goes_to_the_structurer(tmp_path: Path):
    shas = [f"{i:064d}" for i in range(MIN_CLUSTER + 1)]
    run = load_run(_write_run(
        tmp_path / "r",
        [_record(s, dispatch_outcome="unclaimed", parser_id=None,
                 outcome_class="failed") for s in shas],
        folders={s: UNREGISTERED_BANK for s in shas},
    ))
    cluster = next(c for c in build_clusters(run) if c.key == UNREGISTERED_BANK)
    assert cluster.disposition == "generic_structurer"
    assert cluster.rule == "R4_unregistered_bank_tail"


def test_unclaimed_documents_in_unlabelled_folders_go_to_the_structurer(tmp_path: Path):
    shas = [f"{i:064d}" for i in range(7)]
    run = load_run(_write_run(
        tmp_path / "r",
        [_record(s, dispatch_outcome="unclaimed", parser_id=None,
                 outcome_class="failed") for s in shas],
        folders={s: "Unidentified" for s in shas},
    ))
    cluster = next(c for c in build_clusters(run) if c.kind == "unclaimed_unlabelled")
    assert cluster.disposition == "generic_structurer"
    assert cluster.rule == "R5_unlabelled_mix"


def test_an_unreadable_document_is_junk_not_a_layout_problem(tmp_path: Path):
    run = load_run(_write_run(tmp_path / "r", [
        _record("A" * 64, valid_pdf=False, outcome_class="failed"),
        _record("B" * 64, encrypted=True, outcome_class="failed"),
    ]))
    cluster = next(c for c in build_clusters(run) if c.kind == "unusable_document")
    assert cluster.disposition == "junk_unusable"
    assert cluster.evidence == {**cluster.evidence, "encrypted": 1, "invalid_pdf": 1}
    # And it is not also counted as an unclaimed layout cluster.
    assert not [c for c in build_clusters(run) if c.kind == "unclaimed_bank_folder"]


def test_a_parser_crash_is_a_code_defect_not_a_layout_family(tmp_path: Path):
    """W3-2b: routed mechanically to `parser_defect`, OUT of the human queue.

    It was `needs_human_review` in W3-4, which made the queue look like it held
    a taste question when it held a bug. W3-1's exception ranking owns the fix;
    this card only accounts for the documents.
    """
    run = load_run(_write_run(tmp_path / "r", [
        _record("A" * 64, dispatch_outcome="parser_exception",
                exceptions=[["us_bank", "parse", "AttributeError"]],
                outcome_class="failed"),
    ]))
    clusters = build_clusters(run)
    cluster = next(c for c in clusters if c.kind == "parser_crash")
    assert cluster.key == "us_bank:AttributeError"
    assert cluster.disposition == "parser_defect"
    assert cluster.rule == "R8_parser_defect"
    assert "W3-1" in cluster.because
    assert not [c for c in clusters if c.disposition == "needs_human_review"]


def test_an_unattributed_class_by_parser_view_errors_rather_than_degrades(tmp_path: Path):
    """W3-2b ruling 2. The failure this prevents is silent.

    A cache-served run produces a complete-LOOKING table in which every row
    reads `(parser unknown)`, and nothing about the output says the question
    was not answered. That is exactly the shape of the archive's W3-2 baseline.
    """
    run = load_run(_write_run(tmp_path / "r", [
        _withheld(f"{i:064d}", "detail_coverage", None,
                  dispatch_outcome=None, dispatch_source="unavailable")
        for i in range(6)
    ]))
    with pytest.raises(UnattributedParsers) as caught:
        build_clusters(run)
    message = str(caught.value)
    assert "6 of 6" in message
    assert "--enrich" in message
    assert "--allow-unattributed" in message


def test_allow_unattributed_labels_the_rows_explicitly(tmp_path: Path):
    run = load_run(_write_run(tmp_path / "r", [
        _withheld(f"{i:064d}", "detail_coverage", None,
                  dispatch_outcome=None, dispatch_source="unavailable")
        for i in range(6)
    ]))
    space = workspace(run, allow_unattributed=True)
    cell = next(c for c in space["clusters"] if c["kind"] == "withheld_check_cell")
    assert cell["key"] == f"detail_coverage x {UNATTRIBUTED}"
    assert space["unattributed_documents"] == 6
    rendered = render(space)
    assert "WARNING --allow-unattributed" in rendered
    assert UNATTRIBUTED in rendered


def test_enrichment_satisfies_the_gate_without_the_escape_hatch(tmp_path: Path):
    """The intended remedy: recover the parsers, do not silence the check."""
    live = _write_run(tmp_path / "live", [
        _record(f"{i:064d}", parser_id="chase") for i in range(6)])
    cached = _write_run(tmp_path / "cached", [
        _withheld(f"{i:064d}", "detail_coverage", None,
                  dispatch_outcome=None, dispatch_source="unavailable")
        for i in range(6)])
    cell = next(
        c for c in build_clusters(load_run(cached, enrich_parsers_from=[live]))
        if c.kind == "withheld_check_cell"
    )
    assert cell.key == "detail_coverage x chase"


def test_a_fully_attributed_run_needs_no_flag(tmp_path: Path):
    run = load_run(_write_run(tmp_path / "r", [
        _withheld(f"{i:064d}", "detail_coverage", "chase") for i in range(6)]))
    space = workspace(run)
    assert space["unattributed_documents"] == 0
    assert "WARNING --allow-unattributed" not in render(space)


def test_the_cli_exits_non_zero_on_unattributed_parsers(tmp_path: Path, capsys):
    from discovery.adjudication import main

    run = _write_run(tmp_path / "r", [
        _withheld(f"{i:064d}", "detail_coverage", None,
                  dispatch_outcome=None, dispatch_source="unavailable")
        for i in range(6)])
    assert main([str(run)]) == 2
    assert "--enrich" in capsys.readouterr().err
    assert main([str(run), "--allow-unattributed"]) == 0
    assert UNATTRIBUTED in capsys.readouterr().out


def test_a_label_disagreement_is_a_question_not_a_verdict(tmp_path: Path):
    shas = [f"{i:064d}" for i in range(3)]
    run = load_run(_write_run(
        tmp_path / "r",
        [_record(s, parser_id="relay", outcome_class="validated") for s in shas],
        folders={s: "Chase" for s in shas},
    ))
    cluster = next(c for c in build_clusters(run) if c.kind == "label_disagreement")
    assert cluster.key == "Chase -> relay"
    assert cluster.disposition == "needs_human_review"


def test_a_correctly_filed_document_raises_no_label_question(tmp_path: Path):
    run = load_run(_write_run(
        tmp_path / "r",
        [_record("A" * 64, parser_id="td_us", outcome_class="validated")],
        folders={"A" * 64: "TD Bank"},
    ))
    assert not [c for c in build_clusters(run) if c.kind == "label_disagreement"]


def test_a_template_claim_is_not_a_label_disagreement(tmp_path: Path):
    """§DISCOBS DO7#3, closed one layer over `registration_labels()`.

    `releve_facturation` is registered under the name of the TEMPLATE it
    reads, and publishes `Statement.bank = None` because the paper names no
    institution. Both strings the matcher is given are therefore template
    names, so six documents a human had filed under `Desjardins/` read as a
    label disagreement on the run of record — a category error, and the
    obvious way to make it go away is to rename the parser after the folder,
    which §U4.1's evidence forbids.
    """
    shas = [f"{i:064d}" for i in range(6)]
    directory = _write_run(
        tmp_path / "r",
        [_record(s, parser_id="releve_facturation", outcome_class="validated")
         for s in shas],
        folders={s: "Desjardins" for s in shas},
        no_issuer=frozenset(shas),
    )
    run = load_run(directory)
    assert not [c for c in build_clusters(run) if c.kind == "label_disagreement"]

    space = workspace(run)
    assert space["template_claim_documents"] == 6
    assert space["template_claim_pairs"] == [
        {"folder": "Desjardins", "parser": "releve_facturation", "documents": 6}
    ]
    printed = render(space)
    assert "6 claims name no issuer" in printed
    assert "Desjardins -> releve_facturation   6" in printed
    assert "DO NOT rename the parser after the folder" in printed


def test_a_claim_that_names_an_issuer_is_still_judged(tmp_path: Path):
    """The exemption is one bit about OUR claim, not a licence for the parser.

    Same parser, same folder, but this document published an issuer, so the
    disagreement is a real one and stays in the queue. Without this the
    template class would be a name-based rule on the registration after all.
    """
    run = load_run(_write_run(
        tmp_path / "r",
        [_record("A" * 64, parser_id="releve_facturation", outcome_class="validated")],
        folders={"A" * 64: "Desjardins"},
    ))
    cluster = next(c for c in build_clusters(run) if c.kind == "label_disagreement")
    assert cluster.key == "Desjardins -> releve_facturation"
    assert workspace(run)["template_claim_documents"] == 0


def test_a_template_claim_is_tested_before_the_containment_match(tmp_path: Path):
    """Order is load-bearing, and it is the report's order (§DISCOBS DO4).

    A template name that happens to be contained in a folder name would
    otherwise be reported as AGREEMENT, manufacturing a detection-accuracy
    datum out of a coincidence.
    """
    from discovery.evidence import TEMPLATE_CLAIM, label_verdict, registration_labels

    run = load_run(_write_run(
        tmp_path / "r",
        [_record("A" * 64, parser_id="community_section", outcome_class="validated")],
        folders={"A" * 64: "Community Section Bank"},
        no_issuer=frozenset({"A" * 64}),
    ))
    document = run.documents["A" * 64]
    labels = registration_labels()["community_section"]
    assert label_agrees(document.folder_label, labels), (
        "vacuous unless the folder really does contain the template name"
    )
    assert label_verdict(document, labels) == TEMPLATE_CLAIM


def test_the_template_exemption_fails_closed_when_it_cannot_be_asked(tmp_path: Path):
    """`claim_names_issuer` is None without a rows.csv, and None is not an
    exemption. It cannot arise in practice — the folder label the check needs
    comes from the same file and the same row, so a run with no rows.csv has
    no label check at all — and this pins both halves of that."""
    from discovery.evidence import LABEL_UNMATCHED, label_verdict, registration_labels

    run = load_run(_write_run(
        tmp_path / "r",
        [_record("A" * 64, parser_id="releve_facturation", outcome_class="validated")],
    ))
    document = run.documents["A" * 64]
    assert document.claim_names_issuer is None
    assert document.is_template_claim is False
    assert document.folder_label is None
    # Asked directly with a folder label it could not have: still judged.
    labels = registration_labels()["releve_facturation"]
    assert label_verdict(document, labels) == LABEL_UNMATCHED
    # And through the workspace, where it is never asked at all.
    assert workspace(run)["template_claim_documents"] == 0
    assert not [c for c in build_clusters(run) if c.kind == "label_disagreement"]


def test_the_two_artifacts_of_one_run_use_one_template_rule(tmp_path: Path):
    """The workspace and the run report must not describe the same document
    two ways, so the word and the rule are shared rather than restated."""
    from discovery.evidence import TEMPLATE_CLAIM
    from discovery.report import TEMPLATE_CLAIM as REPORT_TEMPLATE_CLAIM
    from discovery.report import folder_agreement
    from discovery.runner import DocumentRow

    assert TEMPLATE_CLAIM is REPORT_TEMPLATE_CLAIM
    row = DocumentRow(
        relative_path="Desjardins/x.pdf", folder_label="Desjardins",
        content_sha256="A" * 64, byte_size=1, parser_id="releve_facturation",
        dispatch_outcome="claimed", statement_bank=None,
    )
    assert folder_agreement(row) == TEMPLATE_CLAIM

    run = load_run(_write_run(
        tmp_path / "r",
        [_record("A" * 64, parser_id="releve_facturation", outcome_class="validated")],
        folders={"A" * 64: "Desjardins"},
        no_issuer=frozenset({"A" * 64}),
    ))
    assert run.documents["A" * 64].is_template_claim


def test_a_truncation_flag_is_a_policy_question(tmp_path: Path):
    run = load_run(_write_run(tmp_path / "r", [
        _record("A" * 64, truncated=2, outcome_class="validated"),
    ]))
    cluster = next(c for c in build_clusters(run) if c.kind == "advisory_flag")
    assert cluster.disposition == "needs_human_review"
    assert cluster.evidence["still_validated"] == 1


def test_small_clusters_roll_into_a_tail_rather_than_hiding_the_big_ones(tmp_path: Path):
    records, folders = [], {}
    for index in range(6):
        sha = f"{index:064d}"
        records.append(_record(sha, dispatch_outcome="unclaimed", parser_id=None,
                               outcome_class="failed"))
        folders[sha] = f"Tiny Bank {index}"
    run = load_run(_write_run(tmp_path / "r", records, folders=folders))
    clusters = [c for c in build_clusters(run) if c.kind == "unclaimed_bank_folder"]
    assert len(clusters) == 1
    assert clusters[0].key.startswith("(tail:")
    assert clusters[0].documents == 6
    assert clusters[0].evidence["folders"] == 6


# --- the workspace -----------------------------------------------------------


def test_no_card_ever_names_a_document(tmp_path: Path):
    """Cards carry aggregate stats and content hashes. Nothing else."""
    records = [_withheld(f"{i:064d}", "ledger_identity", "chase") for i in range(6)]
    run = load_run(_write_run(tmp_path / "r", records,
                              folders={f"{i:064d}": "Chase" for i in range(6)}))
    space = workspace(run)
    for cluster in space["clusters"]:
        for sha in cluster["sample_hashes"]:
            assert len(sha) == 64 and sha in run.documents
        assert set(cluster) == {
            "kind", "key", "documents", "disposition", "rule", "because",
            "evidence", "sample_hashes",
        }


def test_the_worksheet_leaves_the_adjudication_columns_empty(tmp_path: Path):
    run = load_run(_write_run(
        tmp_path / "r", [_withheld(f"{i:064d}", "detail_coverage", "chase")
                         for i in range(5)]))
    json_path, csv_path = write_workspace(tmp_path / "out", workspace(run))
    assert json.loads(json_path.read_text(encoding="utf-8"))["clusters"]
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert rows
    for row in rows:
        assert row["proposed_disposition"] in DISPOSITIONS
        assert row["adjudicated_disposition"] == ""
        assert row["adjudicator"] == ""


def test_the_workspace_renders_ascii_only(tmp_path: Path):
    run = load_run(_write_run(tmp_path / "r", [
        _withheld(f"{i:064d}", "detail_coverage", "chase") for i in range(5)
    ]))
    assert render(workspace(run)).isascii()


# --- coverage movement -------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ("withheld", "validated", "improved"),
        ("failed", "withheld", "improved"),
        ("validated", "withheld", "regressed"),
        ("review", "failed", "regressed"),
        ("validated", "validated", "unchanged"),
        ("deferred", "validated", "unranked"),
        ("validated", "deferred", "unranked"),
    ],
)
def test_direction_ranks_the_outcome_ladder(before, after, expected):
    assert direction(before, after) == expected


def test_deferred_sits_outside_the_ladder():
    """"We chose not to try" is a statement about the RUN, so moving in or out
    of it is neither an improvement nor a regression."""
    assert "deferred" not in LADDER


def test_a_run_compared_to_itself_reports_no_movement(tmp_path: Path):
    """Ordering, run ids, timings and record ids must not register as change."""
    records = [_record(f"{i:064d}", parser_id="chase") for i in range(5)]
    left = _write_run(tmp_path / "a", records)
    right = _write_run(tmp_path / "b", list(reversed(records)))
    report = compare(load_run(left), load_run(right))
    assert report["identical"] is True
    assert report["movement"] == {"unchanged": 5}
    assert report["transitions"] == {}
    assert render_movement(report).isascii()


def test_movement_is_reported_by_failure_class_and_family(tmp_path: Path):
    baseline = _write_run(tmp_path / "base", [
        _withheld("A" * 64, "detail_coverage", "chase"),
        _withheld("B" * 64, "ledger_identity", "chase"),
        _record("C" * 64, parser_id="wells_fargo", outcome_class="validated"),
    ])
    candidate = _write_run(tmp_path / "cand", [
        _record("A" * 64, parser_id="chase", outcome_class="validated"),
        _withheld("B" * 64, "ledger_identity", "chase"),
        _withheld("C" * 64, "period_integrity", "wells_fargo"),
    ])
    report = compare(load_run(baseline), load_run(candidate))

    assert report["movement"] == {"improved": 1, "unchanged": 1, "regressed": 1}
    assert report["transitions"] == {"withheld -> validated": 1, "validated -> withheld": 1}
    assert report["failure_class_movement"] == {
        "left detail_coverage": 1, "entered period_integrity": 1,
    }
    assert report["by_family"]["chase"] == {"improved": 1}
    assert report["by_family"]["wells_fargo"] == {"regressed": 1}


def test_a_regression_is_never_averaged_away(tmp_path: Path):
    """A change that fixes many and breaks a few must report both."""
    baseline = _write_run(tmp_path / "base", (
        [_withheld(f"{i:064d}", "detail_coverage", "chase") for i in range(10)]
        + [_record("F" * 64, parser_id="wells_fargo", outcome_class="validated")]
    ))
    candidate = _write_run(tmp_path / "cand", (
        [_record(f"{i:064d}", parser_id="chase", outcome_class="validated")
         for i in range(10)]
        + [_withheld("F" * 64, "ledger_identity", "wells_fargo")]
    ))
    report = compare(load_run(baseline), load_run(candidate))
    assert report["movement"]["improved"] == 10
    assert report["movement"]["regressed"] == 1
    assert report["regressed_sample"][0]["family"] == "wells_fargo"
    assert "regressed" in render_movement(report)


def test_document_sets_that_differ_are_reported_not_silently_intersected(tmp_path: Path):
    baseline = _write_run(tmp_path / "base", [_record("A" * 64), _record("B" * 64)])
    candidate = _write_run(tmp_path / "cand", [_record("A" * 64), _record("C" * 64)])
    report = compare(load_run(baseline), load_run(candidate))
    assert report["documents"] == {
        "baseline": 2, "candidate": 2, "shared": 1,
        "only_baseline": 1, "only_candidate": 1,
    }
    assert report["identical"] is False
    assert "NOT COMPARABLE" in render_movement(report)


def test_the_comparison_cli_can_fail_a_build_on_a_regression(tmp_path: Path):
    from discovery.compare import main

    baseline = _write_run(tmp_path / "base", [
        _record("A" * 64, parser_id="chase", outcome_class="validated")])
    candidate = _write_run(tmp_path / "cand", [
        _withheld("A" * 64, "ledger_identity", "chase")])
    assert main([str(baseline), str(candidate)]) == 0
    assert main([str(baseline), str(candidate), "--fail-on-regression"]) == 2
    assert main([str(baseline), str(baseline), "--fail-on-regression"]) == 0


def test_the_adjudication_cli_runs_and_writes(tmp_path: Path, capsys):
    from discovery.adjudication import main

    run = _write_run(tmp_path / "r", [
        _withheld(f"{i:064d}", "detail_coverage", "chase") for i in range(6)
    ])
    assert main([str(run), "--write"]) == 0
    out = capsys.readouterr().out
    assert "adjudication workspace" in out
    assert "variant_completeness" in out
    assert (run / "adjudication.json").is_file()
    assert (run / "adjudication.csv").is_file()
