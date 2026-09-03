"""P22-HOLDOUT case 20: the adjudication CLI.

Renders pages locally from a PDF (PyMuPDF) into a PRIVATE packet directory
outside the checkout, presents the evidence packet (classifier proposal and
the census tag as EVIDENCE, labelled as such, never as a default), records
the verdict into the sealed store with the packet digest, writes nothing into
the checkout. Every document here is a synthetic PDF drawn from literal
strings (dates in 2031); the "proposal" is deliberately WRONG so a CLI that
adopted it would be caught.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import pytest

from tools import adjudicate
from tools.holdout.digest import parse_digest
from tools.holdout.manifest import HoldoutManifest
from tools.holdout.store import TruthStore, description_hash

ROOT = Path(__file__).resolve().parents[1]
DIGEST = ROOT / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt"

CENSUS_COLUMNS = ["sha", "sha16", "cluster", "cluster_group", "b8_kind", "text_density",
                  "classification", "text_route"]
ROW_COLUMNS = ["relative_path", "folder_label", "content_sha256", "valid_pdf", "classification",
               "page_count", "outcome_class", "outcome_reason", "failure_class", "source_path",
               "parser_id", "account_count"]


def synthetic_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    try:
        for number, lines in enumerate((
            ("SYNTHETIC ACCOUNT STATEMENT", "Statement period 2031-01-01 to 2031-01-31",
             "Opening balance 100.00", "2031-01-05 SYNTHETIC ROW ONE -12.34"),
            ("Page two of the synthetic statement", "Closing balance 87.66"),
        ), start=1):
            page = doc.new_page(width=612, height=792)
            for index, line in enumerate(lines):
                page.insert_text((72, 100 + 20 * index), line, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


def upper_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A private world: PDFs, a rows.csv, a census, a proposal, the store."""
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(tmp_path / "sealed"))
    pdf_root = tmp_path / "pdfs"
    (pdf_root / "synthetic_a").mkdir(parents=True)
    (pdf_root / "synthetic_b").mkdir(parents=True)
    good = synthetic_pdf()
    invalid = b"\xac\xed\x00\x05" + b"\x00" * 200  # a serialised-object blob saved as .pdf
    (pdf_root / "synthetic_a" / "statement.pdf").write_bytes(good)
    (pdf_root / "synthetic_b" / "export.pdf").write_bytes(invalid)
    sha_good, sha_invalid = upper_sha(good), upper_sha(invalid)
    sha_missing = hashlib.sha256(b"synthetic:missing").hexdigest().upper()

    rows = tmp_path / "rows.csv"
    with rows.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS)
        writer.writeheader()
        writer.writerow(dict(relative_path="synthetic_a/statement.pdf", folder_label="synthetic_a",
                             content_sha256=sha_good, valid_pdf="True", classification="digital",
                             page_count="2", outcome_class="failed", outcome_reason="no_parser_matched",
                             failure_class="B", source_path="native", parser_id="", account_count=""))
        writer.writerow(dict(relative_path="synthetic_b/export.pdf", folder_label="synthetic_b",
                             content_sha256=sha_invalid, valid_pdf="False", classification="unknown",
                             page_count="0", outcome_class="failed", outcome_reason="invalid_pdf",
                             failure_class="", source_path="none", parser_id="", account_count=""))

    census = tmp_path / "per_sha.csv"
    with census.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CENSUS_COLUMNS)
        writer.writeheader()
        writer.writerow(dict(sha=sha_good, sha16=sha_good[:16], cluster="FAM:synthetic_family",
                             cluster_group="FAM:synthetic_family", b8_kind="family",
                             text_density="medium", classification="digital", text_route="native"))
        writer.writerow(dict(sha=sha_invalid, sha16=sha_invalid[:16], cluster="PF-INVALID-PDF",
                             cluster_group="PF-INVALID-PDF", b8_kind="none", text_density="thin",
                             classification="unknown", text_route="none"))

    proposal = tmp_path / "classification.csv"
    with proposal.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["content_sha256", "kind", "sub_kind", "tier", "signals"])
        writer.writeheader()
        # Deliberately WRONG: the document is a complete synthetic statement.
        writer.writerow(dict(content_sha256=sha_good, kind="NOT_A_STATEMENT", sub_kind="letter",
                             tier="lexical", signals="synthetic_signal"))

    shas = tmp_path / "slice.txt"
    shas.write_text(f"{sha_good}\n# a comment\n{sha_invalid}\n{sha_missing}\n", encoding="utf-8")

    return dict(tmp=tmp_path, pdf_root=pdf_root, rows=rows, census=census, proposal=proposal,
                shas=shas, packets=tmp_path / "packets", sha_good=sha_good,
                sha_invalid=sha_invalid, sha_missing=sha_missing)


def queue_args(world, **extra) -> list[str]:
    args = ["queue", "--rows", str(world["rows"]), "--slice", "synthetic-slice", "--shas",
            str(world["shas"]), "--packets", str(world["packets"]), "--pdf-root",
            str(world["pdf_root"]), "--census", str(world["census"]), "--classification",
            str(world["proposal"])]
    for key, value in extra.items():
        args += [f"--{key.replace('_', '-')}", str(value)]
    return args


def checkout_snapshot() -> tuple:
    return (tuple(sorted(os.listdir(ROOT))), DIGEST.read_bytes() if DIGEST.exists() else None,
            (ROOT / "packets").exists(), (ROOT / "sealed").exists())


# --- queue -------------------------------------------------------------------


def test_queue_renders_pages_and_packets_into_the_private_directory(world, capsys):
    before = checkout_snapshot()
    assert adjudicate.main(queue_args(world)) == 0
    assert checkout_snapshot() == before
    slice_dir = world["packets"] / "synthetic-slice"
    good_dir = slice_dir / world["sha_good"][:16]
    assert sorted(p.name for p in good_dir.glob("page-*.png")) == ["page-001.png", "page-002.png"]
    packet = json.loads((good_dir / "packet.json").read_text(encoding="utf-8"))
    assert packet["content_sha256"] == world["sha_good"]
    assert packet["render"]["page_count"] == 2 and packet["render"]["rendered"] == 2
    assert packet["render"]["error"] is None
    assert len(packet["packet_digest"]) == 64
    evidence = packet["evidence"]
    assert evidence["census"]["label"] == "EVIDENCE (census, agent-derived, not truth)"
    assert evidence["census"]["values"]["cluster_group"] == "FAM:synthetic_family"
    assert evidence["classifier"]["label"] == "EVIDENCE (classifier proposal, tool-derived, not truth)"
    assert evidence["classifier"]["values"]["kind"] == "NOT_A_STATEMENT"
    assert "moneythumb" not in evidence  # absent unless explicitly supplied
    text = (good_dir / "EVIDENCE.txt").read_text(encoding="utf-8")
    assert "EVIDENCE (census, agent-derived, not truth)" in text
    assert "EVIDENCE (classifier proposal, tool-derived, not truth)" in text
    assert "MoneyThumb" not in text
    assert "default" not in text.lower()

    invalid_dir = slice_dir / world["sha_invalid"][:16]
    invalid_packet = json.loads((invalid_dir / "packet.json").read_text(encoding="utf-8"))
    assert invalid_packet["render"]["error"] is not None
    assert invalid_packet["render"]["rendered"] == 0
    assert not list(invalid_dir.glob("page-*.png"))

    queue = json.loads((slice_dir / "queue.json").read_text(encoding="utf-8"))
    assert queue["slice"] == "synthetic-slice"
    assert [e["status"] for e in queue["entries"]] == ["pending", "pending", "unavailable"]
    assert queue["entries"][2]["content_sha256"] == world["sha_missing"]
    digest_text = (slice_dir / "QUEUE_DIGEST.txt").read_text(encoding="utf-8")
    assert "count: 3" in digest_text and "queue_digest: " in digest_text
    out = capsys.readouterr().out
    assert "packets: 2" in out and "unavailable: 1" in out


def test_queue_is_deterministic_for_the_same_inputs(world):
    assert adjudicate.main(queue_args(world)) == 0
    first = (world["packets"] / "synthetic-slice" / "QUEUE_DIGEST.txt").read_text(encoding="utf-8")
    first_queue = json.loads((world["packets"] / "synthetic-slice" / "queue.json").read_text(encoding="utf-8"))
    assert adjudicate.main(queue_args(world)) == 0
    second = (world["packets"] / "synthetic-slice" / "QUEUE_DIGEST.txt").read_text(encoding="utf-8")
    second_queue = json.loads((world["packets"] / "synthetic-slice" / "queue.json").read_text(encoding="utf-8"))
    assert first == second
    assert [e.get("packet_digest") for e in first_queue["entries"]] == [e.get("packet_digest") for e in second_queue["entries"]]
    assert sum(1 for e in first_queue["entries"] if e.get("packet_digest")) == 2


def test_queue_refuses_a_packet_directory_inside_the_checkout(world):
    before = checkout_snapshot()
    inside = ROOT / "packets_probe"
    assert adjudicate.main(queue_args(world, packets=inside)) != 0
    assert not inside.exists()
    assert checkout_snapshot() == before


def test_queue_verifies_the_file_bytes_against_the_content_sha(world):
    (world["pdf_root"] / "synthetic_a" / "statement.pdf").write_bytes(b"%PDF-1.4 tampered")
    assert adjudicate.main(queue_args(world)) == 0
    queue = json.loads((world["packets"] / "synthetic-slice" / "queue.json").read_text(encoding="utf-8"))
    entry = next(e for e in queue["entries"] if e["content_sha256"] == world["sha_good"])
    assert entry["status"] == "unavailable" and entry["reason"] == "pdf_sha_mismatch"


def test_moneythumb_evidence_only_when_explicitly_supplied(world, tmp_path):
    mt = tmp_path / "mt.csv"
    with mt.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["content_sha256", "mt_outcome"])
        writer.writeheader()
        writer.writerow(dict(content_sha256=world["sha_good"], mt_outcome="synthetic-vendor-value"))
    assert adjudicate.main(queue_args(world, moneythumb=mt)) == 0
    packet = json.loads((world["packets"] / "synthetic-slice" / world["sha_good"][:16] / "packet.json").read_text(encoding="utf-8"))
    assert packet["evidence"]["moneythumb"]["label"] == "EVIDENCE (MoneyThumb, vendor output, not truth)"


# --- run ----------------------------------------------------------------------


def answers_for(world, **overrides) -> dict:
    answers = {
        world["sha_good"]: dict(
            kind="STATEMENT_COMPLETE", sub_kind=None, account_kind="deposit", modality="digital",
            legible=True, completeness_findings=[], account_count=1,
            printed_period_start="2031-01-01", printed_period_end="2031-01-31",
            opening_balance="100.00", closing_balance="87.66", printed_transaction_count=1,
            sampled_rows=[{"date": "2031-01-05", "description": "SYNTHETIC ROW ONE", "amount": "-12.34"}],
            notes="a synthetic note",
        ),
        world["sha_invalid"]: dict(
            kind="FILE_INVALID", sub_kind="serialised_object", account_kind="unknown",
            modality="unknown", legible=False, completeness_findings=[], account_count=None,
            printed_period_start=None, printed_period_end=None, opening_balance=None,
            closing_balance=None, printed_transaction_count=None, sampled_rows=[], notes=None,
        ),
    }
    answers.update(overrides)
    return {"adjudicator": "principal_adjudicator", "answers": answers}


def run_args(world, answers_path: Path | None = None) -> list[str]:
    args = ["run", "--slice", "synthetic-slice", "--packets", str(world["packets"])]
    if answers_path is not None:
        args += ["--answers", str(answers_path)]
    return args


def test_run_with_answers_appends_records_with_the_packet_digest(world, capsys):
    assert adjudicate.main(queue_args(world)) == 0
    answers = world["tmp"] / "answers.json"
    answers.write_text(json.dumps(answers_for(world)), encoding="utf-8")
    before = checkout_snapshot()
    assert adjudicate.main(run_args(world, answers)) == 0
    assert checkout_snapshot() == before
    store = TruthStore.open()
    records = store.records()
    assert [r["kind"] for r in records] == ["STATEMENT_COMPLETE", "FILE_INVALID"]
    assert store.verify_chain() == records[-1]["hash"]
    queue = json.loads((world["packets"] / "synthetic-slice" / "queue.json").read_text(encoding="utf-8"))
    by_sha = {e["content_sha256"]: e for e in queue["entries"]}
    assert records[0]["packet_digest"] == by_sha[world["sha_good"]]["packet_digest"]
    assert by_sha[world["sha_good"]]["status"] == "adjudicated"
    assert by_sha[world["sha_good"]]["record_id"] == records[0]["record_id"]
    assert records[0]["adjudicator"] == "principal_adjudicator"
    raw = (world["tmp"] / "sealed" / "truth.jsonl").read_text(encoding="utf-8")
    assert "SYNTHETIC ROW ONE" not in raw and "a synthetic note" not in raw
    assert records[0]["sampled_rows"][0]["description_hash"] == description_hash("SYNTHETIC ROW ONE")
    out = capsys.readouterr().out
    assert "EVIDENCE (classifier proposal, tool-derived, not truth)" in out
    assert "NOT_A_STATEMENT" in out  # shown ...
    assert records[0]["kind"] == "STATEMENT_COMPLETE"  # ... never adopted
    assert "default" not in out.lower()
    assert "hashed" in out.lower() and "not stored" in out.lower()


def test_run_never_prefills_the_kind_from_the_proposal(world, capsys):
    """M4's killer: an answer without a kind, beside a classifier proposal,
    appends NOTHING; the entry stays pending."""
    assert adjudicate.main(queue_args(world)) == 0
    answers = answers_for(world)
    del answers["answers"][world["sha_good"]]["kind"]
    answers["answers"][world["sha_invalid"]]["kind"] = ""
    path = world["tmp"] / "answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    assert adjudicate.main(run_args(world, path)) == 0
    assert TruthStore.open().records() == []
    queue = json.loads((world["packets"] / "synthetic-slice" / "queue.json").read_text(encoding="utf-8"))
    assert [e["status"] for e in queue["entries"]][:2] == ["pending", "pending"]
    out = capsys.readouterr().out
    assert "no kind" in out.lower() and "not a default" in out.lower()


def test_run_interactive_asks_the_kind_with_no_default(world, monkeypatch, capsys):
    assert adjudicate.main(queue_args(world)) == 0
    prompts: list[str] = []
    script = iter([
        # document 1: the human types every field
        "STATEMENT_COMPLETE", "", "deposit", "digital", "y", "", "1", "2031-01-01", "2031-01-31",
        "100.00", "87.66", "1", "2031-01-05 | SYNTHETIC ROW ONE | -12.34", "", "a synthetic note", "y",
        # document 2: an empty kind is refused, then the human quits
        "", "quit",
    ])

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(script)

    monkeypatch.setattr(adjudicate, "ask", ask)
    assert adjudicate.main(run_args(world) + ["--adjudicator", "principal_adjudicator"]) == 0
    records = TruthStore.open().records()
    assert len(records) == 1 and records[0]["kind"] == "STATEMENT_COMPLETE"
    assert records[0]["sampled_rows"][0]["amount"] == "-12.34"
    kind_prompts = [p for p in prompts if p.lower().startswith("kind")]
    assert kind_prompts, prompts
    for prompt in kind_prompts:
        assert "default" not in prompt.lower()
        assert "NOT_A_STATEMENT" not in prompt.split(">")[0].replace("|", " ").split("one of")[0]
        assert "[" not in prompt  # no bracketed default anywhere in the kind prompt
    out = capsys.readouterr().out
    assert "no kind" in out.lower()


def test_run_refuses_a_malformed_answer_without_appending(world, capsys):
    assert adjudicate.main(queue_args(world)) == 0
    answers = answers_for(world)
    answers["answers"][world["sha_good"]]["opening_balance"] = "1,000.00"
    path = world["tmp"] / "answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    assert adjudicate.main(run_args(world, path)) == 0
    records = TruthStore.open().records()
    assert [r["kind"] for r in records] == ["FILE_INVALID"]
    assert "refused" in capsys.readouterr().out.lower()


def test_run_requires_an_adjudicator_role(world, capsys):
    assert adjudicate.main(queue_args(world)) == 0
    answers = answers_for(world)
    answers["adjudicator"] = "someone@example.com"
    path = world["tmp"] / "answers.json"
    path.write_text(json.dumps(answers), encoding="utf-8")
    assert adjudicate.main(run_args(world, path)) != 0
    assert TruthStore.open().records() == []


# --- status / export-digest -------------------------------------------------


def test_status_prints_aggregates_only(world, capsys):
    assert adjudicate.main(queue_args(world)) == 0
    path = world["tmp"] / "answers.json"
    path.write_text(json.dumps(answers_for(world)), encoding="utf-8")
    assert adjudicate.main(run_args(world, path)) == 0
    capsys.readouterr()
    assert adjudicate.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "STATEMENT_COMPLETE: 1" in out and "FILE_INVALID: 1" in out
    assert "records: 2" in out
    assert world["sha_good"] not in out and world["sha_good"][:16] not in out


def test_status_refuses_without_the_store_variable(monkeypatch):
    monkeypatch.delenv("SEALED_TRUTH_DIR", raising=False)
    assert adjudicate.main(["status"]) != 0


def test_export_digest_writes_the_non_sensitive_digest(world, tmp_path):
    assert adjudicate.main(queue_args(world)) == 0
    path = world["tmp"] / "answers.json"
    path.write_text(json.dumps(answers_for(world)), encoding="utf-8")
    assert adjudicate.main(run_args(world, path)) == 0
    out = tmp_path / "digest_out" / "MANIFEST_DIGEST.txt"
    before = checkout_snapshot()
    assert adjudicate.main(["export-digest", "--out", str(out)]) == 0
    assert checkout_snapshot() == before
    parsed = parse_digest(out.read_text(encoding="utf-8"))
    assert parsed["record_count"] == 2
    assert parsed["adjudicated_sha16"] == sorted([world["sha_good"][:16], world["sha_invalid"][:16]])
    text = out.read_text(encoding="utf-8")
    assert "STATEMENT_COMPLETE" not in text and "87.66" not in text


def test_the_committed_digest_matches_an_empty_store(tmp_path, monkeypatch):
    """The initial commit carries an EMPTY store's digest. Once real
    adjudications are exported this pins only the grammar and the header."""
    from tools.holdout.digest import render_digest

    text = DIGEST.read_text(encoding="utf-8")
    parsed = parse_digest(text)
    assert parsed["store_version"] == 1
    if parsed["record_count"] == 0 and not parsed["holdout_sha16_status"]:
        assert text == render_digest(None, None)


# --- holdout commands --------------------------------------------------------


def test_holdout_add_refuses_a_development_corpus_sha_and_accepts_a_new_one(world, capsys):
    common = ["--source-batch", "unseen-2031-01", "--modality", "digital", "--bank", "unknown_bank",
              "--accounts", "single", "--table", "table_heavy", "--currency", "usd", "--pages", "3",
              "--layout-family", "fam_synthetic", "--dev-rows", str(world["rows"])]
    assert adjudicate.main(["holdout-add", "--sha", world["sha_good"]] + common) != 0
    assert HoldoutManifest.open().items() == {}
    fresh = hashlib.sha256(b"synthetic:fresh-unseen").hexdigest().upper()
    assert adjudicate.main(["holdout-add", "--sha", fresh] + common) == 0
    items = HoldoutManifest.open().items()
    assert len(items) == 1
    item = items["H000001"]
    assert item["content_sha256"] == fresh and item["strata"]["currency"] == "USD"
    assert item["strata"]["page_count_bucket"] == "2-5"
    out = capsys.readouterr().out
    assert "H000001" in out and fresh not in out


def test_holdout_add_requires_a_development_corpus_source(world):
    fresh = hashlib.sha256(b"synthetic:fresh-unseen").hexdigest().upper()
    assert adjudicate.main([
        "holdout-add", "--sha", fresh, "--source-batch", "unseen-2031-01", "--modality", "digital",
        "--bank", "unknown_bank", "--accounts", "single", "--table", "table_heavy", "--currency",
        "usd", "--pages", "3", "--layout-family", "fam_synthetic",
    ]) != 0


def test_holdout_burn_and_graduate_follow_the_matrix(world, tmp_path, capsys):
    fresh = hashlib.sha256(b"synthetic:fresh-unseen").hexdigest().upper()
    assert adjudicate.main([
        "holdout-add", "--sha", fresh, "--source-batch", "unseen-2031-01", "--modality", "digital",
        "--bank", "unknown_bank", "--accounts", "single", "--table", "table_heavy", "--currency",
        "usd", "--pages", "3", "--layout-family", "fam_synthetic", "--dev-rows", str(world["rows"]),
    ]) == 0
    # unseen -> burned refuses; the CLI has no way to mark `evaluated`.
    assert adjudicate.main(["holdout-burn", "--id", "H000001", "--by", "P24-LAYOUT"]) != 0
    assert not any(command.startswith("holdout-evaluate") for command in adjudicate.COMMANDS)
    manifest = HoldoutManifest.open()
    manifest.record_evaluation("H000001", engine_version="engine-v1", evaluation_run_id="run-1")
    tags = tmp_path / "tags.txt"
    tags.write_text("batch9-final\nphase2.1-final\n", encoding="utf-8")
    assert adjudicate.main(["holdout-graduate", "--id", "H000001", "--tag", "phase9.9-final",
                            "--tags-from", str(tags), "--attest", "--attested-by",
                            "principal_adjudicator"]) != 0
    assert adjudicate.main(["holdout-graduate", "--id", "H000001", "--tag", "phase2.1-final",
                            "--tags-from", str(tags), "--attested-by", "principal_adjudicator"]) != 0
    assert adjudicate.main(["holdout-graduate", "--id", "H000001", "--tag", "phase2.1-final",
                            "--tags-from", str(tags), "--attest", "--attested-by",
                            "principal_adjudicator"]) == 0
    assert HoldoutManifest.open().items()["H000001"]["status"] == "graduated"
    capsys.readouterr()
    assert adjudicate.main(["holdout-list"]) == 0
    out = capsys.readouterr().out
    assert "graduated: 1" in out and fresh not in out


def test_holdout_graduate_reads_freeze_tags_from_git_by_default(world, monkeypatch):
    fresh = hashlib.sha256(b"synthetic:fresh-unseen").hexdigest().upper()
    assert adjudicate.main([
        "holdout-add", "--sha", fresh, "--source-batch", "unseen-2031-01", "--modality", "digital",
        "--bank", "unknown_bank", "--accounts", "single", "--table", "table_heavy", "--currency",
        "usd", "--pages", "3", "--layout-family", "fam_synthetic", "--dev-rows", str(world["rows"]),
    ]) == 0
    HoldoutManifest.open().record_evaluation("H000001", engine_version="engine-v1", evaluation_run_id="run-1")
    monkeypatch.setattr(adjudicate, "git_tags", lambda: frozenset({"batch9-final"}))
    assert adjudicate.main(["holdout-graduate", "--id", "H000001", "--tag", "nope-final", "--attest",
                            "--attested-by", "principal_adjudicator"]) != 0
    assert adjudicate.main(["holdout-graduate", "--id", "H000001", "--tag", "batch9-final", "--attest",
                            "--attested-by", "principal_adjudicator"]) == 0


def test_the_cli_has_exactly_the_ruled_commands():
    assert set(adjudicate.COMMANDS) == {
        "queue", "run", "status", "export-digest",
        "holdout-add", "holdout-burn", "holdout-graduate", "holdout-list",
    }
