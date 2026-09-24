"""Fabricated local inputs and mocked readers only; no model or corpus calls."""
from argparse import Namespace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocr.visual_pair_config import CUSTOMER_DATA_OPT_IN_ENV, CUSTOMER_DATA_OPT_IN_LITERAL
from tools.phase3_pair import check_judgment as checker
from vlm.receipts import Refused, sha256_bytes


def _manifest(tmp_path, count=2, scope="real_judgment"):
    root = tmp_path / "source"
    root.mkdir()
    entries = []
    for index in range(count):
        path = root / f"fabricated-{index}.pdf"
        path.write_bytes(f"%PDF-fabricated-{index}".encode())
        entries.append({"id": f"J{index + 1:02}", "path": path.name,
                        "sha256": sha256_bytes(path.read_bytes())})
    manifest = tmp_path / "selection.private.json"
    manifest.write_text(json.dumps({"version": 1, "scope": scope, "documents": entries}))
    return Namespace(manifest=manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
                     source_root=root, output_dir=tmp_path / "private"), entries


def _replace_manifest(args, entries):
    args.manifest.write_text(json.dumps({"version": 1, "scope": "real_judgment", "documents": entries}))
    args.manifest_sha256 = sha256_bytes(args.manifest.read_bytes())


def _row(state, old, new=None, page=1):
    return {"candidate_id": "p1r0", "state": state, "page": page,
            "original": {"description": old},
            "corrected": {"description": new} if new is not None else None,
            "row": {"description": new if new is not None else old}}


def _doc(admitted=True):
    return SimpleNamespace(source_file="private-name.pdf", model="visual-pair-dots-qwen",
                           pages=["PRIVATE PAGE CONTENT"], page_integrity=[], visual_pair={
        "gate": {"admitted": admitted, "reasons": []},
        "confidence": {"counts": {"agreed": 1, "corrected": 0, "added": 0,
                                   "rejected": 0, "unresolved": 0}},
        "row_evidence": [_row("agreed", "PRIVATE MERCHANT")],
        "statement": {"period_start": "2025-01-01", "period_end": "2025-01-31",
                      "beginning_balance": 0, "ending_balance": 20,
                      "transactions": [{"description": "PRIVATE MERCHANT"}],
                      "stated_daily_balances": [{"date": "2025-01-02", "balance": 20}]} if admitted else None,
        "field_evidence": [{"field": "beginning_balance", "value": 0, "page": 1}],
    })


def test_manifest_binds_all_two_or_three_inputs(tmp_path):
    args, entries = _manifest(tmp_path, count=3)
    result = checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)
    assert len(result) == 3
    assert result[0]["path"] == args.source_root / entries[0]["path"]
    (args.source_root / entries[-1]["path"]).write_bytes(b"%PDF-changed")
    with pytest.raises(Refused, match="judgment_document_changed"):
        checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)


@pytest.mark.parametrize("count", [0, 1, 4, 16])
def test_manifest_refuses_unbounded_or_one_document_runs(tmp_path, count):
    args, _ = _manifest(tmp_path, count=count)
    with pytest.raises(Refused, match="judgment_document_count_invalid"):
        checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)


def test_scope_hash_and_paths_are_required(tmp_path):
    args, entries = _manifest(tmp_path, scope="synthetic")
    with pytest.raises(Refused, match="judgment_manifest_changed"):
        checker.checked_documents(args.manifest, "0" * 64, args.source_root)
    with pytest.raises(Refused, match="judgment_manifest_scope_invalid"):
        checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)
    entries[0]["path"] = "../selection.private.json"
    _replace_manifest(args, entries)
    with pytest.raises(Refused, match="judgment_document_path_invalid"):
        checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)


def test_symlink_escape_and_duplicate_documents_refused(tmp_path):
    args, entries = _manifest(tmp_path)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-outside")
    link = args.source_root / "link.pdf"
    link.symlink_to(outside)
    entries[0].update(path="link.pdf", sha256=sha256_bytes(outside.read_bytes()))
    _replace_manifest(args, entries)
    with pytest.raises(Refused, match="judgment_document_path_invalid"):
        checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)
    entries[0].update(path=entries[1]["path"], sha256=entries[1]["sha256"])
    _replace_manifest(args, entries)
    with pytest.raises(Refused, match="judgment_document_duplicate"):
        checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)


def test_document_id_cannot_contain_source_information(tmp_path):
    args, entries = _manifest(tmp_path)
    entries[0]["id"] = "PRIVATE CUSTOMER"
    _replace_manifest(args, entries)
    with pytest.raises(Refused, match="judgment_document_id_invalid"):
        checker.checked_documents(args.manifest, args.manifest_sha256, args.source_root)


def test_all_hashes_checked_before_calls_and_failures_logged(tmp_path, monkeypatch):
    args, entries = _manifest(tmp_path)
    (args.source_root / entries[1]["path"]).write_bytes(b"%PDF-changed")
    monkeypatch.setenv(CUSTOMER_DATA_OPT_IN_ENV, CUSTOMER_DATA_OPT_IN_LITERAL)
    monkeypatch.setattr("vlm.pair.extract_visual_pair", lambda *a, **k: pytest.fail("network reached"))
    with pytest.raises(Refused, match="judgment_document_changed"):
        checker.run(args)
    ledger = (args.output_dir / "RUN_STATE.md").read_text()
    assert '"status":"started"' in ledger and '"status":"failed"' in ledger
    assert str(args.source_root) not in ledger


def test_customer_authorization_cannot_be_invented_by_checker(tmp_path, monkeypatch):
    args, _ = _manifest(tmp_path)
    monkeypatch.delenv(CUSTOMER_DATA_OPT_IN_ENV, raising=False)
    monkeypatch.setattr("vlm.pair.extract_visual_pair", lambda *a, **k: pytest.fail("network reached"))
    with pytest.raises(Exception, match="visual_pair_remote_customer_data_refused"):
        checker.run(args)
    assert CUSTOMER_DATA_OPT_IN_ENV not in __import__("os").environ


@pytest.mark.parametrize("where", ["source/subdir", "webapp_data", ".claude/recovery/test"])
def test_private_output_refuses_inputs_and_historical_caches(tmp_path, where):
    with pytest.raises((ValueError, Refused)):
        checker._private_output(tmp_path / where, tmp_path / "source")


def test_output_inside_repository_must_be_ignored_runtime(tmp_path):
    with pytest.raises(Refused, match="judgment_output_must_be_private"):
        checker._private_output(checker.REPO / "docs" / "private-judgment", tmp_path / "source")


def test_native_comparison_is_advisory_and_distinguishes_corrections():
    rows = [_row("corrected", "MISSPELLED", "printed merchant"),
            _row("corrected", "printed merchant", "REWORDED"),
            _row("corrected", "printed", "printed merchant"),
            _row("corrected", "printed merchant", "printed merchant"),
            _row("agreed", "line wrap"), _row("agreed", "MISSING"),
            _row("agreed", "unknown", page=2)]
    result = checker.compare_descriptions({"row_evidence": rows}, ["printed merchant\nline\nwrap", ""])
    counts = result["counts"]
    assert counts["corrections_supported"] == counts["corrections_damaged"] == 1
    assert counts["corrections_indeterminate"] == 2
    assert counts["corrected_description_unchanged"] == 1
    assert counts["agreed_exact_mismatched"] == 2
    assert counts["agreed_whitespace_mismatched"] == counts["agreed_native_unavailable"] == 1
    assert "not ground truth" in result["limitations"]
    assert "printed merchant" not in json.dumps(result)
    assert len(result["rows"]) == len(rows)


def test_missing_metadata_is_not_invented_and_zero_is_present():
    fields = checker.printed_field_presence(_doc(admitted=False).visual_pair)
    assert fields["printed_fields_present"]["beginning_balance"] is True
    assert fields["printed_fields_present"]["ending_balance"] is False
    assert fields["daily_balance_snapshot_count"] is None
    assert fields["transaction_ledger_count"] == 1
    assert fields["usable_daily_ledger"] is False


def test_run_keeps_content_private_and_uses_customer_scope_and_offline_analysis(tmp_path, monkeypatch, capsys):
    args, _ = _manifest(tmp_path)
    monkeypatch.setenv(CUSTOMER_DATA_OPT_IN_ENV, CUSTOMER_DATA_OPT_IN_LITERAL)
    calls, policies = [], []

    def extract(pdf, **kwargs):
        calls.append(kwargs)
        print("PRIVATE EXTRACTOR DIAGNOSTICS")
        kwargs["progress"]("visual_pair_proposing:1/1")
        kwargs["progress"]("PRIVATE UNSAFE EVENT")
        return _doc()

    def analyze(doc, **kwargs):
        policies.append(kwargs)
        print("PRIVATE ANALYSIS DIAGNOSTICS", file=__import__("sys").stderr)
        return SimpleNamespace(accounts=[SimpleNamespace(metrics=SimpleNamespace(
            adb_ok=True, adb=SimpleNamespace(daily_balances=[object()] * 31)))])

    monkeypatch.setattr("vlm.pair.extract_visual_pair", extract)
    monkeypatch.setattr("vlm.pair_adapter.analyze_visual_pair", analyze)
    monkeypatch.setattr("analysis.serialization.document_report_to_dict", lambda report: {"private": "PRIVATE REPORT"})
    monkeypatch.setattr(checker, "_native_pages", lambda pdf: ["PRIVATE MERCHANT"])
    summary = checker.run(args)
    assert summary["analyzed"] == summary["admitted"] == 2
    assert summary["runs"][0]["fields"]["computed_daily_ledger_count"] == 31
    assert summary["runs"][0]["fields"]["usable_daily_ledger"] is True
    assert all(call["data_scope"] == "customer" and call["settings"].customer_data_opt_in for call in calls)
    assert policies == [{"review_policy": "admit_gated"}] * 2
    captured = capsys.readouterr()
    assert "PRIVATE" not in captured.out and captured.err == ""
    assert str(args.source_root) not in captured.out
    assert '"stage":"proposing"' in captured.out
    folder = args.output_dir / summary["run_id"]
    assert "PRIVATE REPORT" in (folder / "J01-analysis.private.json").read_text()
    assert "PRIVATE ANALYSIS DIAGNOSTICS" in (folder / "diagnostics.private.log").read_text()
    assert (folder / "J01-document.private.json").stat().st_mode & 0o777 == 0o600
    assert args.output_dir.stat().st_mode & 0o777 == 0o700
    assert '"status":"finished"' in (args.output_dir / "RUN_STATE.md").read_text()


def test_whole_document_failure_reports_only_exception_type(tmp_path, monkeypatch, capsys):
    args, _ = _manifest(tmp_path)
    monkeypatch.setenv(CUSTOMER_DATA_OPT_IN_ENV, CUSTOMER_DATA_OPT_IN_LITERAL)

    def fail(*a, **k):
        raise RuntimeError("PRIVATE CONTENT WITH SENSITIVE ACCOUNT")

    monkeypatch.setattr("vlm.pair.extract_visual_pair", fail)
    summary = checker.run(args)
    assert summary["analyzed"] == 0
    assert all(item["error_type"] == "RuntimeError" for item in summary["runs"])
    assert "PRIVATE" not in capsys.readouterr().out


def test_cli_failures_never_print_exception_message(tmp_path, monkeypatch, capsys):
    args, _ = _manifest(tmp_path)

    def fail(*a, **k):
        raise OSError("PRIVATE PATH")

    monkeypatch.setattr(checker, "run", fail)
    assert checker.main(["--manifest", str(args.manifest), "--manifest-sha256", args.manifest_sha256,
                         "--source-root", str(args.source_root), "--output-dir", str(args.output_dir)]) == 1
    output = capsys.readouterr().out
    assert json.loads(output) == {"status": "failed", "error_type": "OSError"}


def test_native_reader_uses_local_pdf_text_only(tmp_path):
    from tests.paddle_synthetic import build_ledger_page, render_native_pdf

    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(render_native_pdf(build_ledger_page(n_rows=4)))
    pages = checker._native_pages(pdf)
    assert len(pages) == 1 and pages[0].strip()
