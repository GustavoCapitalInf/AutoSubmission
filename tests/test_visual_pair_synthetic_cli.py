import json
from argparse import Namespace

import pytest

from tools.phase3_pair.check_synthetic import checked_fixtures, _private_output, run
from tools.phase3_pair import smoke_pair
from vlm.receipts import Refused, sha256_bytes


def _manifest(tmp_path, entries=None, scope="synthetic"):
    root = tmp_path / "synthetic"
    root.mkdir()
    pdf = root / "fabricated.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfabricated test stub\n")
    entries = entries or [{"path": "fabricated.pdf", "sha256": sha256_bytes(pdf.read_bytes())}]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "data_scope": scope, "files": entries}))
    return root, pdf, manifest, sha256_bytes(manifest.read_bytes())


def test_only_checksum_bound_synthetic_fixtures_are_accepted(tmp_path):
    root, pdf, manifest, digest = _manifest(tmp_path)
    assert checked_fixtures(manifest, digest, root) == [pdf]
    pdf.write_bytes(b"%PDF-changed")
    with pytest.raises(Refused, match="synthetic_fixture_changed"):
        checked_fixtures(manifest, digest, root)


def test_supplied_fixture_manifest_uses_identical_file_binding(tmp_path):
    root, pdf, manifest, _ = _manifest(tmp_path)
    supplied = {"manifest_version": 1, "scope": "synthetic", "documents": 1,
                "docs": [{"source_rel": pdf.name, "source_sha256": sha256_bytes(pdf.read_bytes()),
                          "kind": "synthetic_native", "physical_pages": 1, "bytes": pdf.stat().st_size}]}
    manifest.write_text(json.dumps(supplied))
    digest = sha256_bytes(manifest.read_bytes())
    assert checked_fixtures(manifest, digest, root) == [pdf]
    pdf.write_bytes(b"%PDF-changed")
    with pytest.raises(Refused, match="synthetic_fixture_changed"):
        checked_fixtures(manifest, digest, root)


def test_mixed_manifest_formats_are_refused(tmp_path):
    root, _, manifest, _ = _manifest(tmp_path)
    mixed = json.loads(manifest.read_text())
    mixed.update(manifest_version=1, scope="synthetic", docs=[])
    manifest.write_text(json.dumps(mixed))
    with pytest.raises(Refused, match="synthetic_manifest_scope_invalid"):
        checked_fixtures(manifest, sha256_bytes(manifest.read_bytes()), root)


def test_scope_and_manifest_hash_are_checked_before_requests(tmp_path, monkeypatch):
    root, pdf, manifest, digest = _manifest(tmp_path, scope="customer")
    monkeypatch.setattr("vlm.pair.extract_visual_pair", lambda *a, **k: pytest.fail("network reached"))
    args = Namespace(manifest=manifest, manifest_sha256=digest, synthetic_root=root,
                     output_dir=tmp_path / "private")
    with pytest.raises(Refused, match="synthetic_manifest_scope_invalid"):
        run(args)
    with pytest.raises(Refused, match="synthetic_manifest_changed"):
        checked_fixtures(manifest, "0" * 64, root)


def test_manifest_cannot_escape_synthetic_root(tmp_path):
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-fabricated")
    root, pdf, manifest, digest = _manifest(tmp_path, entries=[
        {"path": "../outside.pdf", "sha256": sha256_bytes(outside.read_bytes())},
    ])
    with pytest.raises(Refused, match="synthetic_fixture_path_invalid"):
        checked_fixtures(manifest, digest, root)


def test_output_never_writes_to_fixture_or_cold_cache(tmp_path):
    with pytest.raises(Refused, match="synthetic_output_overlaps_inputs"):
        _private_output(tmp_path / "synthetic" / "output", tmp_path / "synthetic")
    with pytest.raises(ValueError):
        _private_output(tmp_path / "webapp_data_train12_cold", tmp_path / "synthetic")


def test_smoke_refuses_image_outside_synthetic_tree_before_network(tmp_path, monkeypatch):
    root = tmp_path / "synthetic"
    root.mkdir()
    page = tmp_path / "outside.png"
    page.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(smoke_pair, "ask", lambda *a, **k: pytest.fail("network reached"))
    assert smoke_pair.main(["--page", str(page), "--synthetic-root", str(root)]) == 1


def test_smoke_explicit_synthetic_page_and_no_content_output(tmp_path, monkeypatch, capsys):
    root = tmp_path / "synthetic"
    root.mkdir()
    page = root / "fixture.png"
    page.write_bytes(b"\x89PNG\r\n\x1a\nFABRICATED_IMAGE_BYTES")
    calls = []

    def ask(port, model, prompt, b64, extra=None):
        calls.append((port, model))
        return {"http": 200, "chars": 123}

    monkeypatch.setattr(smoke_pair, "ask", ask)
    assert smoke_pair.main(["--page", str(page), "--synthetic-root", str(root)]) == 0
    assert [port for port, _ in calls] == [18013, 18022]
    output = capsys.readouterr().out
    assert "FABRICATED_IMAGE_BYTES" not in output and str(page) not in output
