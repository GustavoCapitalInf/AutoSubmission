import json
from types import SimpleNamespace

import pytest

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from tests.test_vlm_runner import FakeStageA, FakeStageB, _ctx, _wave
from vlm import regate
from vlm.partitions import Member
from vlm.receipts import Refused

SHA = "F" * 64


def _member(tmp_path):
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "doc.pdf").write_bytes(render_native_pdf(build_ledger_page(n_rows=4)))
    return Member(SHA, "fam/doc.pdf", 100, 1, "fam", "digital", "validated", 1), archive


def test_regate_reproduces_the_verdict_and_binds_the_source(tmp_path):
    member, archive = _member(tmp_path)
    _wave([member], _ctx("hybrid", stage_a=FakeStageA(), stage_b=FakeStageB()), tmp_path / "w", archive)
    result = regate.regate_wave(tmp_path / "w", tmp_path / "w-regate")
    assert result["status"] == "complete" and result["counts"]["admitted"] == 1 and result["counts"]["refused_by_gate"] == 0
    public = json.loads((tmp_path / "w-regate" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["gate"]["admitted"] and public["gate"]["regated"] is True and public["match"] is None
    launch = json.loads((tmp_path / "w-regate" / "launch.json").read_text(encoding="utf-8"))
    assert launch["regated_from"]["result"]["sha256"] and launch["gate_version"] >= 4
    release = json.loads((tmp_path / "w-regate" / "release.json").read_text(encoding="utf-8"))
    assert release["regated_from_result_sha256"] == launch["regated_from"]["result"]["sha256"]
    with pytest.raises(Refused) as exc:
        regate.regate_wave(tmp_path / "w", tmp_path / "w-regate")
    assert exc.value.code == "wave_already_attempted"


def test_regate_copies_failures_and_reader_baseline_receipts(tmp_path):
    member, archive = _member(tmp_path)
    _wave([member], _ctx("reader_baseline"), tmp_path / "w", archive, settings=None)
    result = regate.regate_wave(tmp_path / "w", tmp_path / "w2")
    assert result["counts"]["attempted"] == 1 and result["counts"]["admitted"] == 0
    assert (tmp_path / "w2" / "results" / f"{SHA}.json").exists()
