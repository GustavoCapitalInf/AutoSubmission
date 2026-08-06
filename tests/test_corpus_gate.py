"""The corpus gate, and the fast tests that keep the gate itself honest.

`test_corpus_gate_is_green` carries the `corpus` marker and is deselected from
the default `pytest` run, because it re-audits all 109 statements and takes
minutes. Run it with `pytest -m corpus`, or `python corpus_gate.py`.

Everything else in this module is fast and runs by default: these protect the
gate's own guarantees — that it stays offline, that it cannot silently drop a
statement, and that a corrupted cache is an error rather than a shrug.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import corpus_artifacts
import corpus_gate
from corpus_artifacts import ArtifactError, cached_markdown, sha256_hex

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "tests" / "corpus_cache"


@pytest.mark.corpus
def test_corpus_gate_is_green():
    result = corpus_gate.run_gate(corpus_gate.CORPUS, CACHE)
    failed = [check for check in result.checks if not check.ok]
    assert not failed, "\n".join(
        f"{check.name}: {check.summary}\n  " + "\n  ".join(check.details) for check in failed
    )
    assert result.stats["corpus_pdfs"] == corpus_gate.EXPECTED_PDF_COUNT
    assert result.stats["native_text_statements"] + result.stats["committed_ocr_statements"] == (
        corpus_gate.EXPECTED_PDF_COUNT
    )
    assert result.stats["exclusions"] == 0


def test_gate_expectations_match_the_committed_audits():
    balance = corpus_gate.read_csv(corpus_gate.BALANCE_CSV)
    adb = corpus_gate.read_csv(corpus_gate.ADB_CSV)

    assert len(balance) == corpus_gate.EXPECTED_PDF_COUNT
    assert len(adb) == corpus_gate.EXPECTED_PDF_COUNT
    assert sum(row["status"] == "PASS" for row in balance) == corpus_gate.EXPECTED_PASS
    assert sum(row["status"] == "PASS" for row in adb) == corpus_gate.EXPECTED_PASS
    assert {
        row["statement"] for row in balance if row["status"] == "WITHHELD_SOURCE_CONTRADICTION"
    } == corpus_gate.WITHHELD_STATEMENTS
    assert {
        row["statement"] for row in adb if row["status"] == "WITHHELD"
    } == corpus_gate.WITHHELD_STATEMENTS


def test_every_pinned_corpus_pdf_is_accounted_for_without_parsing():
    """Both audits pin the same 109 paths, and every one is on disk.

    Scoped to the pinned manifest: the corpus root is shared with untracked
    discovery material, so set-equality against an rglob of the root is not a
    property the tree can have. Foreign files are handled by
    `check_foreign_files` — counted, reported, never fatal.
    """
    balance = {row["path"] for row in corpus_gate.read_csv(corpus_gate.BALANCE_CSV)}
    adb = {corpus_gate.relative_key(row) for row in corpus_gate.read_csv(corpus_gate.ADB_CSV)}
    manifest = corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))

    assert len(manifest) == corpus_gate.EXPECTED_PDF_COUNT
    assert balance == adb == set(manifest)
    for path in corpus_gate.manifest_pdfs(corpus_gate.CORPUS, manifest):
        assert path.is_file(), path


def test_committed_ocr_artifacts_cover_every_scanned_statement():
    entries = corpus_artifacts.manifest_entries(CACHE)
    on_disk = set(
        corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))
    )
    scanned = {
        row["path"]
        for row in corpus_gate.read_csv(corpus_gate.BALANCE_CSV)
        if row["source_type"].startswith("scanned")
    }

    assert {entry["path"] for entry in entries.values()} == scanned
    assert {entry["path"] for entry in entries.values()} <= on_disk
    for entry in entries.values():
        source = corpus_gate.CORPUS / entry["path"]
        assert sha256_hex(source.read_bytes()) == entry["pdf_sha256"], entry["path"]
        artifact = CACHE / entry["artifact"]
        assert sha256_hex(artifact.read_text(encoding="utf-8").encode("utf-8")) == (
            entry["artifact_sha256"]
        ), entry["path"]


def test_cached_markdown_returns_none_for_an_unknown_document():
    assert cached_markdown(b"%PDF-not-in-the-corpus", CACHE) is None


def test_cached_markdown_rejects_an_altered_artifact(tmp_path):
    entry = next(iter(corpus_artifacts.manifest_entries(CACHE).values()))
    source = (corpus_gate.CORPUS / entry["path"]).read_bytes()

    (tmp_path / "ocr").mkdir()
    (tmp_path / entry["artifact"]).write_text("tampered", encoding="utf-8")
    (tmp_path / corpus_artifacts.MANIFEST_NAME).write_text(
        json.dumps({"artifacts": [entry]}), encoding="utf-8"
    )

    with pytest.raises(ArtifactError, match="has been altered"):
        cached_markdown(source, tmp_path)


def test_offline_source_resolution_refuses_to_run_ocr(tmp_path, monkeypatch):
    """A scanned statement with no committed artifact fails loudly, never silently."""
    import adb_forensic_audit
    import balance_forensic_audit

    scanned = tmp_path / "scanned.pdf"
    scanned.write_bytes(b"%PDF-no-native-text")
    (tmp_path / corpus_artifacts.MANIFEST_NAME).write_text(
        json.dumps({"artifacts": []}), encoding="utf-8"
    )

    def explode(*args, **kwargs):
        raise AssertionError("the gate must never invoke Tesseract")

    monkeypatch.setattr(adb_forensic_audit, "native_statement", lambda *a, **k: None)
    monkeypatch.setattr(balance_forensic_audit, "native_document", lambda *a, **k: None)
    monkeypatch.setattr(adb_forensic_audit, "parse_local_tesseract", explode)
    monkeypatch.setattr(balance_forensic_audit, "parse_local_tesseract", explode)

    with pytest.raises(ArtifactError, match="refusing to run OCR in offline mode"):
        adb_forensic_audit.source_markdown(scanned, ocr_cache=tmp_path)
    with pytest.raises(ArtifactError, match="refusing to run OCR in offline mode"):
        balance_forensic_audit.source_markdown(scanned, ocr_cache=tmp_path)


def test_gate_reports_drift_in_any_audited_field():
    """The comparison is field-level, not status-level."""
    committed = [{"path": "a.pdf", "status": "PASS", "expected_lowest": "10.00"}]
    same = [{"path": "a.pdf", "status": "PASS", "expected_lowest": "10.00"}]
    drifted = [{"path": "a.pdf", "status": "PASS", "expected_lowest": "10.01"}]

    assert corpus_gate.compare_rows(same, committed, "path", "t")[0] is True
    ok, details = corpus_gate.compare_rows(drifted, committed, "path", "t")
    assert ok is False
    assert "expected_lowest" in details[0]


def test_gate_reports_a_statement_that_disappears_from_the_run():
    committed = [{"path": "a.pdf", "status": "PASS"}, {"path": "b.pdf", "status": "PASS"}]
    ok, details = corpus_gate.compare_rows(
        [{"path": "a.pdf", "status": "PASS"}], committed, "path", "t"
    )
    assert ok is False
    assert any("b.pdf" in detail and "not re-audited" in detail for detail in details)


def test_gate_rejects_a_reinterpreted_source_contradiction():
    rows = [
        {"statement": name, "status": "PASS"}
        for name in sorted(corpus_gate.WITHHELD_STATEMENTS)
    ]
    rows += [{"statement": f"ok-{i}.pdf", "status": "PASS"} for i in range(corpus_gate.EXPECTED_PASS)]

    result = corpus_gate.Result()
    corpus_gate.check_outcomes(result, "balance", rows, "PASS", "WITHHELD_SOURCE_CONTRADICTION")

    check = result.checks[0]
    assert check.ok is False
    assert any("must stay withheld" in detail for detail in check.details)


# --- manifest scoping: the corpus root is shared with foreign documents ------
#
# These build a throwaway corpus out of generated bytes. They never read, move,
# or mutate a real corpus file, and never touch the discovery archive.

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _synthetic_corpus(root: Path, name: str, body: bytes = MINIMAL_PDF) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _pin(corpus: Path, rel: str) -> dict[str, str]:
    return {"path": rel, "sha256": corpus_gate.sha256_upper((corpus / rel).read_bytes())}


def test_a_foreign_pdf_under_the_corpus_root_is_counted_but_never_fails(tmp_path):
    """The discovery archive lives under the same root. It is reported, not fatal."""
    _synthetic_corpus(tmp_path, "Bank X/pinned.pdf")
    _synthetic_corpus(tmp_path, "Bank X/foreign.pdf", MINIMAL_PDF + b"% foreign\n")
    _synthetic_corpus(tmp_path, "Unidentified/also foreign.pdf", MINIMAL_PDF + b"% other\n")
    balance = [_pin(tmp_path, "Bank X/pinned.pdf")]
    manifest = corpus_gate.manifest_paths(balance)

    result = corpus_gate.Result()
    foreign = corpus_gate.check_foreign_files(result, tmp_path, manifest)
    corpus_gate.check_source_integrity(result, tmp_path, balance)

    assert foreign == 2
    assert result.ok, [c.details for c in result.checks if not c.ok]
    counted = result.checks[0]
    assert counted.ok is True
    assert counted.summary == "2 non-corpus PDFs present — ignored (discovery archive)"
    assert "2 top-level folder(s)" in counted.details[0]
    # Reported by count only: unpinned documents under this root are sensitive.
    assert not any("foreign.pdf" in detail for detail in counted.details)
    # The foreign files are not hashed, audited, or otherwise claimed.
    assert result.checks[1].summary == "1/1 pinned source PDFs match their pinned SHA-256"


def test_no_foreign_pdfs_is_reported_explicitly(tmp_path):
    _synthetic_corpus(tmp_path, "Bank X/pinned.pdf")
    balance = [_pin(tmp_path, "Bank X/pinned.pdf")]

    result = corpus_gate.Result()
    assert corpus_gate.check_foreign_files(result, tmp_path, corpus_gate.manifest_paths(balance)) == 0
    assert result.checks[0].summary == "no non-corpus PDFs under the corpus root"


def test_a_missing_pinned_statement_fails_the_gate(tmp_path, monkeypatch):
    """A pinned path that is not on disk is red — it can no longer just vanish."""
    _synthetic_corpus(tmp_path, "Bank X/present.pdf")
    balance = [_pin(tmp_path, "Bank X/present.pdf"), {"path": "Bank X/gone.pdf", "sha256": "0" * 64}]
    adb = [
        {"folder": "Bank X", "statement": "present.pdf"},
        {"folder": "Bank X", "statement": "gone.pdf"},
    ]
    monkeypatch.setattr(corpus_gate, "EXPECTED_PDF_COUNT", 2)

    result = corpus_gate.Result()
    corpus_gate.check_inventory(
        result, corpus_gate.manifest_paths(balance), tmp_path, balance, adb
    )
    corpus_gate.check_source_integrity(result, tmp_path, balance)

    assert result.ok is False
    assert any("Bank X/gone.pdf is pinned but missing" in d for d in result.checks[0].details)
    assert any("Bank X/gone.pdf is pinned but missing" in d for d in result.checks[1].details)


def test_a_missing_pinned_statement_renders_red_instead_of_crashing(tmp_path):
    """run_gate over an empty root: the oracles are skipped, the report is red."""
    result = corpus_gate.run_gate(tmp_path, CACHE)

    assert result.ok is False
    assert result.stats["foreign_pdfs"] == 0
    audits = next(check for check in result.checks if check.name == "audits")
    assert "pinned statement(s) missing" in audits.summary
    assert "RESULT: RED" in corpus_gate.render(result)


def test_an_altered_pinned_statement_fails_the_gate(tmp_path):
    """Same bytes or red: manifest scoping did not soften source integrity."""
    _synthetic_corpus(tmp_path, "Bank X/pinned.pdf")
    balance = [_pin(tmp_path, "Bank X/pinned.pdf")]
    (tmp_path / "Bank X" / "pinned.pdf").write_bytes(MINIMAL_PDF + b"% tampered\n")

    result = corpus_gate.Result()
    corpus_gate.check_source_integrity(result, tmp_path, balance)

    check = result.checks[0]
    assert check.ok is False
    assert any("SHA-256 drifted" in detail for detail in check.details)


def test_an_orphan_ocr_artifact_is_detected_against_the_manifest():
    """An artifact for an unpinned document stays an error, foreign files or not."""
    result = corpus_gate.Result()
    corpus_gate.check_ocr_coverage(result, {"a.pdf": "native"}, ["a.pdf"], CACHE)

    check = result.checks[0]
    assert check.ok is False
    assert any("not in the corpus" in detail for detail in check.details)


def test_audit_oracles_do_not_import_production_financial_mathematics():
    result = corpus_gate.Result()
    corpus_gate.check_oracle_independence(result)
    check = result.checks[0]
    assert check.ok, check.details
    assert set(corpus_gate.INDEPENDENT_SOURCES) >= {
        "adb_forensic_audit.py",
        "balance_forensic_audit.py",
    }
