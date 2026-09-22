"""Synthetic path and worker seams only; no private documents or model calls."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocr import private_artifacts as private
from vlm.receipts import Refused


@pytest.fixture
def external_root(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.setattr(private, "CHECKOUT_ROOT", checkout)
    root = tmp_path / "external" / "private"
    monkeypatch.setenv(private.PRIVATE_ROOT_ENV, str(root))
    return root


def test_default_is_external_home_location_without_creating_it(tmp_path, monkeypatch, external_root):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    expected = home / ".local/share/bank-statement-analysis/phase31-private"
    assert private.private_artifact_root({}) == expected
    assert not expected.exists()


@pytest.mark.parametrize("value", ["", ".claude/phase31-private", "relative", "~/private"])
def test_relative_or_empty_override_is_refused(value, external_root):
    with pytest.raises(private.PrivateArtifactPathError, match="must_be_absolute"):
        private.private_artifact_root({private.PRIVATE_ROOT_ENV: value})


def test_absolute_external_override_is_resolved_without_creation(external_root):
    assert private.private_artifact_root() == external_root
    assert private.private_artifact_path("visual_pair_evidence") == external_root / "visual_pair_evidence"
    assert not external_root.exists()


@pytest.mark.parametrize("suffix", ["", ".claude/phase31-private", "nested"])
def test_checkout_root_and_descendants_are_refused(suffix, external_root):
    candidate = private.CHECKOUT_ROOT / suffix
    with pytest.raises(private.PrivateArtifactPathError, match="outside_checkout"):
        private.private_artifact_root({private.PRIVATE_ROOT_ENV: str(candidate)})
    assert not (private.CHECKOUT_ROOT / ".claude").exists()


def test_root_symlink_into_checkout_is_refused(tmp_path, external_root):
    alias = tmp_path / "alias"
    alias.symlink_to(private.CHECKOUT_ROOT, target_is_directory=True)
    with pytest.raises(private.PrivateArtifactPathError, match="outside_checkout"):
        private.private_artifact_root({private.PRIVATE_ROOT_ENV: str(alias / "private")})


def test_checkout_symlink_outside_is_still_refused(external_root):
    alias = private.CHECKOUT_ROOT / "external-link"
    alias.symlink_to(external_root, target_is_directory=True)
    with pytest.raises(private.PrivateArtifactPathError, match="outside_checkout"):
        private.validate_private_artifact_path(alias)


@pytest.mark.parametrize("into_checkout", [True, False])
def test_child_symlink_cannot_escape_root(tmp_path, external_root, into_checkout):
    external_root.mkdir(parents=True)
    destination = private.CHECKOUT_ROOT if into_checkout else tmp_path / "another-external"
    (external_root / "visual_pair_evidence").symlink_to(destination, target_is_directory=True)
    with pytest.raises(private.PrivateArtifactPathError):
        private.private_artifact_path("visual_pair_evidence")


def test_cli_defaults_external_and_retains_source_overlap_refusal(tmp_path, external_root):
    from tools.phase3_pair.check_judgment import _private_output

    output = _private_output(None, tmp_path / "source")
    assert output == external_root / "judgment-checks"
    assert output.stat().st_mode & 0o777 == 0o700
    with pytest.raises(Refused, match="overlaps_inputs"):
        _private_output(tmp_path / "source" / "outputs", tmp_path / "source")
    with pytest.raises(Refused, match="overlaps_inputs"):
        _private_output(tmp_path, tmp_path / "source")


def test_cli_refuses_old_ignored_checkout_output(tmp_path, external_root):
    from tools.phase3_pair.check_judgment import _private_output

    with pytest.raises(Refused, match="must_be_private"):
        _private_output(private.CHECKOUT_ROOT / ".claude/phase31-private", tmp_path / "source")
    assert not (private.CHECKOUT_ROOT / ".claude").exists()


def test_worker_passes_external_evidence_to_extractor(tmp_path, monkeypatch, external_root):
    from ocr.document import StatementMarkdown
    from webapp import worker

    observed = []
    document = StatementMarkdown("synthetic.pdf", "visual-pair-dots-qwen", ["fabricated"])
    def extract(pdf, **kwargs):
        observed.append(kwargs["evidence_dir"])
        return document

    monkeypatch.setattr("vlm.pair.extract_visual_pair", extract)
    monkeypatch.setattr(worker, "check_remote_authorization", lambda *a, **k: None)
    monkeypatch.setattr(worker, "_cached_ocr_timed",
                        lambda *a, compute, **k: SimpleNamespace(value=compute()))
    monkeypatch.setattr(worker, "_note_cache", lambda *a, **k: None)
    store = SimpleNamespace(storage=SimpleNamespace(data_dir=tmp_path / "old-webapp-data"),
                            set_page_live=lambda *a: None)
    worker._read_visual_pair("synthetic-job", store, None, b"%PDF-fabricated", "synthetic.pdf",
                             SimpleNamespace(content_sha256="fabricated"), timer=None)
    assert observed == [external_root / "visual_pair_evidence"]
    assert not store.storage.data_dir.exists()


def test_webapp_default_and_explicit_storage_cannot_recreate_checkout_cache(monkeypatch, external_root):
    from webapp.storage import Storage, default_data_dir

    monkeypatch.delenv('WEBAPP_DATA_DIR', raising=False)
    assert default_data_dir() == external_root / 'webapp_data'
    assert not external_root.exists()
    inside = private.CHECKOUT_ROOT / 'webapp_data'
    monkeypatch.setenv('WEBAPP_DATA_DIR', str(inside))
    with pytest.raises(private.PrivateArtifactPathError, match='outside_checkout'):
        default_data_dir()
    with pytest.raises(private.PrivateArtifactPathError, match='outside_checkout'):
        Storage(inside)
    assert not inside.exists()


def test_external_webapp_override_stays_absolute(tmp_path, monkeypatch, external_root):
    from webapp.storage import default_data_dir

    outside = tmp_path / 'separate-webapp'
    monkeypatch.setenv('WEBAPP_DATA_DIR', str(outside))
    assert default_data_dir() == outside
    assert not outside.exists()
    monkeypatch.setenv('WEBAPP_DATA_DIR', 'relative-webapp')
    with pytest.raises(private.PrivateArtifactPathError, match='must_be_absolute'):
        default_data_dir()


@pytest.mark.parametrize("module_name,extra", [
    ("check_judgment", []), ("review_judgment", ["--run-dir", "/synthetic/run"]),
])
def test_cli_output_flag_is_optional_without_reading_inputs(monkeypatch, external_root, module_name, extra):
    from importlib import import_module

    cli = import_module("tools.phase3_pair." + module_name)
    captured = []
    if module_name == "check_judgment":
        def run(args):
            captured.append(args.output_dir)
            return dict(documents=0, pages=0, admitted=0, analyzed=0, counts={}, gate_checks=[])
        monkeypatch.setattr(cli, "run", run)
    else:
        def build(args):
            captured.append(args.output_dir)
            return {"status": "synthetic"}
        monkeypatch.setattr(cli, "build", build)
    assert cli.main(["--manifest", "/synthetic/manifest", "--manifest-sha256", "0" * 64,
                     "--source-root", "/synthetic/source", *extra]) == 0
    assert captured == [None]
