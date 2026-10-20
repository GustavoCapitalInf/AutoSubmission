"""Synthetic path and worker seams only; no private documents or model calls."""
from pathlib import Path

import pytest

from ocr import private_artifacts as private


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


def test_a_folder_at_the_monorepo_root_is_refused():
    root_folder = Path(private.__file__).resolve().parents[3] / "data"
    with pytest.raises(private.PrivateArtifactPathError, match="outside_checkout"):
        private.validate_private_artifact_path(root_folder)


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


# The webapp worker's visual-pair evidence write (test_worker_passes_external_evidence_to_extractor) left with the
# worker's pair read (model-code removal, slice S1), and the pair command-line tools' private-output tests
# (test_cli_defaults_external_and_retains_source_overlap_refusal, test_cli_refuses_old_ignored_checkout_output and
# test_cli_output_flag_is_optional_without_reading_inputs) left with those tools (`tools/phase3_pair/`, slice S4):
# guards deleted with their only subject. The data-directory rule below, and the path rules above, are untouched.


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
