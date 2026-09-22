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


def test_regate_merges_an_incomplete_source_with_its_resume(tmp_path):
    """A killed wave has receipts but no result.json; the wave that resumed it holds the rest."""
    member, archive = _member(tmp_path)
    other = Member("E" * 64, "fam/doc.pdf", 100, 1, "fam", "digital", "validated", 1)
    _wave([member, other], _ctx("hybrid", stage_a=FakeStageA(), stage_b=FakeStageB()), tmp_path / "w1", archive)
    (tmp_path / "w1" / "result.json").unlink()   # simulate the kill: receipts kept, no result
    (tmp_path / "w1" / "release.json").unlink()
    (tmp_path / "w1" / "results" / ("E" * 64 + ".json")).unlink()
    (tmp_path / "w1" / "results" / ("E" * 64 + ".private.json")).unlink()
    _wave([member, other], _ctx("hybrid", stage_a=FakeStageA(), stage_b=FakeStageB()), tmp_path / "w2", archive,
          resume_from=tmp_path / "w1")
    result = regate.regate_wave(tmp_path / "w1", tmp_path / "merged", also=[tmp_path / "w2"])
    assert result["counts"]["attempted"] == 2 and result["counts"]["admitted"] == 2 and result["sources_incomplete"] is True
    assert len(list((tmp_path / "merged" / "results").glob("*.json"))) == 4
    launch = json.loads((tmp_path / "merged" / "launch.json").read_text(encoding="utf-8"))
    assert launch["regated_from"]["sources"][0]["incomplete"] is True and launch["regated_from"]["sources"][1]["incomplete"] is False


def test_regate_prefers_a_resumed_success_over_the_earlier_failure_receipt(tmp_path):
    """The wave that resumes a killed wave retries its failed documents; the merge keeps the success."""
    member, archive = _member(tmp_path)
    _wave([member], _ctx("hybrid", stage_a=FakeStageA(), stage_b=FakeStageB()), tmp_path / "w2", archive)
    (tmp_path / "w1" / "results").mkdir(parents=True)
    launch = json.loads((tmp_path / "w2" / "launch.json").read_text(encoding="utf-8"))
    (tmp_path / "w1" / "launch.json").write_text(json.dumps(launch), encoding="utf-8")
    (tmp_path / "w1" / "results" / f"{SHA}.json").write_text(
        json.dumps({"sha": SHA, "arm": "hybrid", "failure": {"class": "TransportError", "code": "connection_failed:ConnectionRefusedError"}}),
        encoding="utf-8")
    result = regate.regate_wave(tmp_path / "w1", tmp_path / "merged", also=[tmp_path / "w2"])
    assert result["counts"]["failed"] == 0 and result["counts"]["attempted"] == 1 and result["counts"]["admitted"] == 1
    public = json.loads((tmp_path / "merged" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public.get("failure") is None and public["gate"]["admitted"]
