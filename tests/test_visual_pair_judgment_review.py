"""Private viewer tests use fabricated PDFs and fabricated reader evidence only."""
from argparse import Namespace
from html.parser import HTMLParser
import json
from pathlib import Path

import pytest

from tools.phase3_pair import review_judgment as viewer
from vlm.receipts import Refused, sha256_bytes


def _fixture(tmp_path):
    from tests.paddle_synthetic import build_ledger_page, render_native_pdf

    source = tmp_path / "source"
    run = tmp_path / "run"
    source.mkdir()
    run.mkdir()
    docs = []
    for index in range(2):
        pdf = source / f"fabricated-{index}.pdf"
        pdf.write_bytes(render_native_pdf(build_ledger_page(n_rows=4 + index)))
        docs.append({"id": f"J{index+1:02}", "path": pdf.name, "sha256": sha256_bytes(pdf.read_bytes())})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "scope": "real_judgment", "documents": docs}))
    digest = sha256_bytes(manifest.read_bytes())
    (run / "summary.private.json").write_text(json.dumps({
        "scope": "real_judgment", "manifest_sha256": digest, "documents": 2,
        "runs": [{"document_id": doc["id"]} for doc in docs]}))
    for doc in docs:
        records = []
        for index, state in enumerate(("corrected", "rejected", "unresolved", "agreed", "added")):
            original = {"date": "2025-01-02", "description": "FABRICATED ORIGINAL", "amount": 12,
                        "direction": "credit", "balance": 102, "date_text": "1/2",
                        "printed_amount": None, "bbox": None}
            corrected = {**original, "description": '</script><script>alert("PRIVATE")</script>', "amount": 13}
            records.append({"state": state, "page": 1, "candidate_id": f"p1r{index}", "locator": "b0t0r1",
                            "original": None if state == "added" else original,
                            "corrected": corrected if state in {"corrected", "unresolved"} else None,
                            "row": None if state in {"rejected", "unresolved"} else corrected,
                            "observed_description": '<img src="https://evil.invalid" onerror="alert(1)">',
                            "corrections": [{"field": "amount", "value": 13}, {"field": "description", "value": corrected["description"]}],
                            "reason": "FABRICATED REASON", "review_verdict": "correct"})
        body = {"pdf_sha256": doc["sha256"], "pages": ["PRIVATE PAGE"], "visual_pair": {
            "gate": {"admitted": False, "reasons": ["summary_mismatch"]},
            "receipt_sha256": "f" * 64, "row_evidence": records, "confidence": {"counts": {"corrected": 1}},
            "field_evidence": [{"page": 1, "field": "beginning_balance", "value": 100}],
            "pages": [{"page": 1, "errors": ["summary_mismatch"], "truncated": False}],
            "statement": None}}
        (run / f'{doc["id"]}-document.private.json').write_text(json.dumps(body))
        (run / f'{doc["id"]}-analysis.private.json').write_text('{"secret_metric":"NEVER READ THIS ANALYSIS FILE"}')
    return Namespace(manifest=manifest, manifest_sha256=digest, source_root=source, run_dir=run,
                     output_dir=tmp_path / "private-viewer"), docs


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_build_renders_only_bound_pdfs_with_all_states_and_held_status(tmp_path):
    args, _ = _fixture(tmp_path)
    result = viewer.build(args)
    assert result == {"status": "created", "path": str(args.output_dir / "review.html")}
    text = (args.output_dir / "review.html").read_text()
    assert text.count('class="row-card"') == 10
    assert text.count("HELD · not admitted for publication") == 2
    for state in ("corrected", "rejected", "unresolved", "agreed", "added"):
        assert f'data-row-state="{state}"' in text
    assert "Original candidate" in text and "Effective / retained evidence" in text
    assert "amount" in text and "Reviewer observation and every proposed field change" in text
    assert "NEVER READ THIS ANALYSIS FILE" not in text
    assert len(list((args.output_dir / "pages").glob("*.jpg"))) == 2
    binding = json.loads((args.output_dir / "viewer-binding.private.json").read_text())
    assert binding["counts"] == {"documents": 2, "pages": 2, "rows": 10, "held_documents": 2}
    assert len(binding["items"]) == 12  # all rows plus both page verdict controls
    assert (args.output_dir / "review.html").stat().st_mode & 0o777 == 0o600
    assert (args.output_dir / "pages").stat().st_mode & 0o777 == 0o700


def test_all_source_content_is_escaped_and_browser_network_is_disabled(tmp_path):
    args, _ = _fixture(tmp_path)
    viewer.build(args)
    text = (args.output_dir / "review.html").read_text()
    parsed = _Tags()
    parsed.feed(text)
    assert sum(tag == "script" for tag, _ in parsed.tags) == 2
    assert sum(tag == "img" for tag, _ in parsed.tags) == 2
    assert all(not any(name.startswith("on") for name in attrs) for _, attrs in parsed.tags)
    assert all(not attrs.get("src", "").startswith("http") for _, attrs in parsed.tags)
    assert '&lt;/script&gt;&lt;script&gt;alert(&quot;PRIVATE&quot;)' in text
    policy = next(attrs["content"] for tag, attrs in parsed.tags
                  if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy")
    assert "connect-src 'none'" in policy and "default-src 'none'" in policy
    assert "script-src 'sha256-" in policy
    assert "localStorage.setItem" in text and "judgment-verdicts.private.json" in text


def test_script_json_cannot_close_script_or_inject_markup():
    value = {"x": '</script><img src=x onerror="alert(1)"> & \u2028'}
    encoded = viewer._json_script(value)
    assert "</script>" not in encoded and "<" not in encoded and "&" not in encoded
    assert json.loads(encoded) == value


def test_all_input_hashes_verified_before_rendering(tmp_path, monkeypatch):
    args, docs = _fixture(tmp_path)
    (args.source_root / docs[1]["path"]).write_bytes(b"%PDF-changed")
    monkeypatch.setattr("vlm.render.render_pages", lambda *a, **k: pytest.fail("renderer reached"))
    with pytest.raises(Refused, match="judgment_document_changed"):
        viewer.build(args)
    assert not args.output_dir.exists()


def test_all_artifact_pdf_bindings_verified_before_rendering(tmp_path, monkeypatch):
    args, _ = _fixture(tmp_path)
    path = args.run_dir / "J02-document.private.json"
    body = json.loads(path.read_text())
    body["pdf_sha256"] = "0" * 64
    path.write_text(json.dumps(body))
    monkeypatch.setattr("vlm.render.render_pages", lambda *a, **k: pytest.fail("renderer reached"))
    with pytest.raises(Refused, match="review_document_source_mismatch"):
        viewer.build(args)
    assert not args.output_dir.exists()


def test_run_must_be_for_this_manifest(tmp_path):
    args, _ = _fixture(tmp_path)
    path = args.run_dir / "summary.private.json"
    summary = json.loads(path.read_text())
    summary["manifest_sha256"] = "0" * 64
    path.write_text(json.dumps(summary))
    with pytest.raises(Refused, match="review_run_manifest_mismatch"):
        viewer.build(args)


def test_artifact_symlink_cannot_escape_run(tmp_path):
    args, _ = _fixture(tmp_path)
    path = args.run_dir / "J01-document.private.json"
    outside = tmp_path / "outside.json"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(Refused, match="review_document_path_invalid"):
        viewer.build(args)


def test_optional_native_evidence_cannot_escape_run(tmp_path):
    args, _ = _fixture(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text('{}')
    (args.run_dir / "J01-native-check.private.json").symlink_to(outside)
    with pytest.raises(Refused, match="review_document_path_invalid"):
        viewer.build(args)


def test_invalid_page_row_is_preserved_for_review(tmp_path):
    args, _ = _fixture(tmp_path)
    path = args.run_dir / "J01-document.private.json"
    body = json.loads(path.read_text())
    body["visual_pair"]["row_evidence"][2]["page"] = 99
    path.write_text(json.dumps(body))
    viewer.build(args)
    text = (args.output_dir / "review.html").read_text()
    assert "Rows without a valid source page" in text
    assert text.count('class="row-card"') == 10
    binding = json.loads((args.output_dir / "viewer-binding.private.json").read_text())
    assert next(row for row in binding["items"] if row["key"] == "J01-r2")["page"] == 99


def test_no_model_or_analysis_calls_needed(tmp_path, monkeypatch):
    args, _ = _fixture(tmp_path)
    monkeypatch.setattr("vlm.pair.extract_visual_pair", lambda *a, **k: pytest.fail("model called"))
    monkeypatch.setattr("vlm.pair_adapter.analyze_visual_pair", lambda *a, **k: pytest.fail("analysis called"))
    viewer.build(args)


def test_existing_review_is_not_overwritten(tmp_path):
    args, _ = _fixture(tmp_path)
    viewer.build(args)
    before = (args.output_dir / "review.html").read_bytes()
    with pytest.raises(Refused, match="review_output_already_exists"):
        viewer.build(args)
    assert (args.output_dir / "review.html").read_bytes() == before


def test_cli_only_prints_output_path_and_status(tmp_path, monkeypatch, capsys):
    args, _ = _fixture(tmp_path)

    def build(_):
        print("PRIVATE LIBRARY DIAGNOSTIC")
        return {"status": "created", "path": str(args.output_dir / "review.html")}

    monkeypatch.setattr(viewer, "build", build)
    argv = ["--manifest", str(args.manifest), "--manifest-sha256", args.manifest_sha256,
            "--source-root", str(args.source_root), "--run-dir", str(args.run_dir),
            "--output-dir", str(args.output_dir)]
    assert viewer.main(argv) == 0
    result = capsys.readouterr()
    assert "PRIVATE" not in result.out and result.err == ""
    assert json.loads(result.out)["status"] == "created"


def test_cli_failure_does_not_print_contents_or_paths(tmp_path, monkeypatch, capsys):
    args, _ = _fixture(tmp_path)

    def build(_):
        print("PRIVATE LIBRARY DIAGNOSTIC")
        raise ValueError("PRIVATE STATEMENT DETAILS")

    monkeypatch.setattr(viewer, "build", build)
    assert viewer.main(["--manifest", str(args.manifest), "--manifest-sha256", args.manifest_sha256,
                        "--source-root", str(args.source_root), "--run-dir", str(args.run_dir),
                        "--output-dir", str(args.output_dir)]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed", "error_type": "ValueError"}
