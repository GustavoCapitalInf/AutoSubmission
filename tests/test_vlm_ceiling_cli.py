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


def test_adapter_key_binds_base_fetch_and_training_receipts(tmp_path):
    import json

    from tools.vlm_ceiling import _weights_bindings
    from vlm.receipts import Refused

    (tmp_path / "fetch-b27bf16-20260919T000000Z.json").write_text(json.dumps({"repo": "Qwen/Qwen3.8-27B", "local_dir": "/w/base", "hashes": ["a b"]}), encoding="utf-8")
    import pytest

    with pytest.raises(Refused) as exc:
        _weights_bindings(tmp_path, ("b27lora",))
    assert exc.value.code == "train_receipt_missing"
    (tmp_path / "train-receipt-20260919T010000Z.json").write_text(json.dumps({"adapter": {"path": "/w/lora", "files": {"adapter_model.safetensors": "f" * 64}}, "steps": 300,
                                                                            "dataset": {"manifest_sha256": "d" * 64}}), encoding="utf-8")
    out = _weights_bindings(tmp_path, ("b27lora",))
    assert out["b27lora"]["base"]["repo"] == "Qwen/Qwen3.8-27B" and out["b27lora"]["steps"] == 300
    assert out["b27lora"]["adapter"]["files"]["adapter_model.safetensors"] == "f" * 64 and out["b27lora"]["train_receipt"]["sha256"]
