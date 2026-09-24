import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.phase3_pair.check_synthetic import checked_fixtures, _private_output, run
from tools.phase3_pair import smoke_pair
from tools.phase3_pair import check_synthetic as checker
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


@pytest.mark.parametrize('target', ['relative-output', '.claude/fabricated-output'])
def test_output_requires_absolute_external_path(tmp_path, target):
    with pytest.raises(Refused, match='synthetic_output_must_be_private'):
        _private_output(Path(target), tmp_path / 'source')


def test_checkout_output_and_symlink_alias_are_refused_before_creation(tmp_path, monkeypatch):
    checkout = tmp_path / 'fabricated-checkout'
    checkout.mkdir()
    monkeypatch.setattr('ocr.private_artifacts.CHECKOUT_ROOT', checkout)
    alias = tmp_path / 'checkout-alias'
    alias.symlink_to(checkout, target_is_directory=True)
    for target in (checkout / '.claude' / 'output', alias / 'output'):
        with pytest.raises(Refused, match='synthetic_output_must_be_private'):
            _private_output(target, tmp_path / 'source')
    assert not (checkout / '.claude').exists()
    assert not (checkout / 'output').exists()


def test_default_synthetic_output_uses_configured_external_root(tmp_path, monkeypatch):
    external = tmp_path / 'external-private'
    monkeypatch.setenv('VISUAL_PAIR_PRIVATE_ROOT', str(external))
    output = _private_output(None, tmp_path / 'source')
    assert output == external / 'synthetic-checks'
    assert output.stat().st_mode & 0o777 == 0o700
    with pytest.raises(Refused, match='synthetic_output_overlaps_inputs'):
        _private_output(tmp_path, tmp_path / 'source')


def test_synthetic_cli_reports_actual_reason_counts_without_source_fields(tmp_path, monkeypatch, capsys):
    root, _, manifest, digest = _manifest(tmp_path)
    counts = {'date_unparsed': {'count': 6, 'pages': [{'page': 2, 'count': 4}, {'page': 3, 'count': 2}],
                                'document_count': 0, 'source_text': 'FABRICATED HIDDEN SOURCE'}}
    document = SimpleNamespace(pages=['FABRICATED PAGE'], visual_pair={
        'gate': {'admitted': False, 'reasons': ['date_unparsed'], 'reason_counts': counts},
        'confidence': {'counts': {'unresolved': 6}}, 'receipt_sha256': 'f' * 64})
    monkeypatch.setattr('ocr.visual_pair_config.load_visual_pair_settings', lambda: object())
    monkeypatch.setattr('vlm.pair.extract_visual_pair', lambda *a, **k: document)
    monkeypatch.setattr('vlm.pair_adapter.analyze_visual_pair', lambda *a, **k: pytest.fail('analysis reached'))
    assert checker.main(['--manifest', str(manifest), '--manifest-sha256', digest,
                         '--synthetic-root', str(root), '--output-dir', str(tmp_path / 'private')]) == 2
    output = capsys.readouterr().out
    events = [json.loads(line) for line in output.splitlines()]
    assert events[0]['gate_reason_count'] == 6
    assert events[0]['gate_reason_counts']['date_unparsed']['pages'] == counts['date_unparsed']['pages']
    assert events[-1]['gate_checks'][0]['gate_reason_count'] == 6
    assert 'FABRICATED' not in output and str(root) not in output
