from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from tools import vlm_ceiling
from vlm.receipts import dump_new

SHA = "E" * 64


def test_run_reader_baseline_and_report(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "d.pdf").write_bytes(render_native_pdf(build_ledger_page(2)))
    private = tmp_path / "X.manifest.private.json"
    dump_new(private, {"manifest_version": 1, "name": "X", "set_sha256": "0" * 64, "archive_root": str(archive),
                       "members": [{"sha": SHA, "relative_path": "fam/d.pdf", "byte_size": 1, "page_count": 1,
                                    "folder_label": "fam", "classification": "digital", "outcome_class": "validated", "account_count": 1}]})
    monkeypatch.setattr(vlm_ceiling, "default_authorize", lambda scope: None)
    code = vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave"), "--data-scope", "synthetic"])
    assert code == 0
    assert vlm_ceiling.main(["report", "--wave", str(tmp_path / "wave")]) == 0
    assert any(p.name.startswith("report-") for p in (tmp_path / "wave").iterdir())
    assert vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave"), "--data-scope", "synthetic"]) == 2
