import json

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from tools import vlm_ceiling
from vlm.receipts import dump_new

SHA = "E" * 64


def test_run_reader_baseline_and_report(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "d.pdf").write_bytes(render_native_pdf(build_ledger_page(2)))
    member = {"sha": SHA, "relative_path": "fam/d.pdf", "byte_size": 1, "page_count": 1, "folder_label": "fam",
              "classification": "digital", "outcome_class": "validated", "account_count": 1}
    private = tmp_path / "X.manifest.private.json"
    dump_new(private, {"manifest_version": 1, "name": "X", "data_scope": "synthetic", "set_sha256": "0" * 64,
                       "archive_root": str(archive), "members": [member]})
    seen = []
    monkeypatch.setattr(vlm_ceiling, "default_authorize", lambda scope: seen.append(scope))
    code = vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave")])
    assert code == 0 and seen == ["synthetic"]   # the scope came from the manifest, not from a flag
    launch = json.loads((tmp_path / "wave" / "launch.json").read_text(encoding="utf-8"))
    assert launch["data_scope"] == "synthetic" and launch["manifest_scope"] == "synthetic"
    assert vlm_ceiling.main(["report", "--wave", str(tmp_path / "wave"), "--exclude-manifest", str(private)]) == 0
    assert any(p.name.startswith("report-") for p in (tmp_path / "wave").iterdir())
    assert vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave")]) == 2
    # a manifest without a declared scope refuses before anything runs
    unscoped = tmp_path / "U.manifest.private.json"
    dump_new(unscoped, {"manifest_version": 1, "name": "CTRL", "set_sha256": "0" * 64, "archive_root": str(archive), "members": [member]})
    assert vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(unscoped), "--out", str(tmp_path / "w2")]) == 2
    assert not (tmp_path / "w2").exists()


def test_data_scope_flag_no_longer_exists():
    import pytest

    with pytest.raises(SystemExit):
        vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", "x", "--out", "y", "--data-scope", "synthetic"])
