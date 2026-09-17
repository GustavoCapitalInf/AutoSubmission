import json
from pathlib import Path

import pytest

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from vlm import runner
from vlm.partitions import Member
from vlm.schema import empty_proposal

SHA = "F" * 64


def _table_html(n=4):
    rows = "".join(
        f"<tr><td>2031-01-{i:02d}</td><td>SYNTHETIC ROW {i:02d}</td><td>{i * 10:.2f}</td><td>{500 + sum(range(1, i + 1)) * 10:.2f}</td></tr>"
        for i in range(1, n + 1))
    return f"<table><tr><th>Date</th><th>Description</th><th>Deposits</th><th>Balance</th></tr>{rows}</table>"


class FakeStageA:
    def __init__(self):
        self.calls = 0

    def version(self):
        return {"model": "fake-parser", "pipeline_version": "v1.6"}

    def parse_page(self, jpeg, *, request_id, page_index):
        self.calls += 1
        return {"blocks": [
            {"label": "text", "bbox": [0, 0, 100, 10], "content": "Beginning Balance 500.00\nEnding Balance 600.00\nStatement Period 01/01/2031 - 01/31/2031", "order": 0},
            {"label": "table", "bbox": [0, 20, 100, 90], "content": _table_html(), "order": 1}],
            "timing": {"total_ms": 2.0}}


class FakeStageB:
    def __init__(self, good=True):
        self.good = good
        self.calls = 0

    def models(self):
        return ["fake-vlm"]

    def chat(self, model, prompt, *, image_jpeg=None, schema=None, **kwargs):
        from vlm.client import ChatResult
        self.calls += 1
        proposal = empty_proposal("statement_page")
        proposal["account"].update({"beginning_balance": 500.0, "ending_balance": 600.0 if self.good else 601.0,
                                    "period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD"})
        balance = 500.0
        for i in range(1, 5):
            balance += i * 10
            proposal["rows"].append({"date": f"2031-01-{i:02d}", "date_text": f"01/{i:02d}", "description": f"SYNTHETIC ROW {i:02d}",
                                     "amount": float(i * 10), "direction": "credit", "balance": balance, "section_index": None,
                                     "continues_previous": False, "box": None})
        text = json.dumps(proposal)
        return ChatResult(text=text, parsed=proposal, parse_error=None, finish_reason="stop", prompt_tokens=100,
                          completion_tokens=50, total_ms=3.0, request_sha256="a" * 64, response_sha256="b" * 64)


def _member(tmp_path) -> tuple[Member, Path]:
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "doc.pdf").write_bytes(render_native_pdf(build_ledger_page(n_rows=4)))
    return Member(SHA, "fam/doc.pdf", 100, 1, "fam", "digital", "validated", 1), archive


def _ctx(arm, stage_a=None, stage_b=None):
    return runner.RunContext(arm=arm, stage_a=stage_a, stage_b=stage_b, stage_b_model="fake-vlm", truth=None,
                             long_edge=800, quality=85, seed=0, data_scope="synthetic", hourly_rate=None)


BINDING = {"path": "m", "sha256": "0" * 64}


def test_stage_a_rules_arm_admits_synthetic_ledger(tmp_path):
    member, archive = _member(tmp_path)
    ctx = _ctx("stage_a_rules", stage_a=FakeStageA())
    result = runner.run_wave([member], ctx, tmp_path / "wave", archive_root=archive, manifest_binding=BINDING,
                             authorize=lambda scope: None, git_tip="deadbeef")
    assert result["status"] == "complete" and result["counts"]["admitted"] == 1 and result["counts"]["attempted"] == 1
    public = json.loads((tmp_path / "wave" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["gate"]["admitted"] and public["rows_proposed"] == 4 and public["pages"] == 1
    assert public["timings"]["stage_a_ms"] >= 0 and len(public["page_hashes"]) == 1
    assert "fam/doc.pdf" not in json.dumps(public)
    private = json.loads((tmp_path / "wave" / "results" / f"{SHA}.private.json").read_text(encoding="utf-8"))
    assert private["rows"][0]["amount"] == "10.00" and private["meta"]["beginning_balance"] == "500.00"
    assert (tmp_path / "wave" / "release.json").exists() and (tmp_path / "wave" / "launch.json").exists()


def test_stage_b_and_hybrid_arms(tmp_path):
    member, archive = _member(tmp_path)
    b = FakeStageB()
    result = runner.run_wave([member], _ctx("stage_b_only", stage_b=b), tmp_path / "w1", archive_root=archive,
                             manifest_binding=BINDING, authorize=lambda s: None, git_tip="x")
    assert result["counts"]["admitted"] == 1 and b.calls == 1
    a = FakeStageA()
    result = runner.run_wave([member], _ctx("hybrid", stage_a=a, stage_b=FakeStageB()), tmp_path / "w2", archive_root=archive,
                             manifest_binding=BINDING, authorize=lambda s: None, git_tip="x")
    assert result["counts"]["admitted"] == 1 and a.calls == 1
    public = json.loads((tmp_path / "w2" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["agreement"]["stage_a_rows"] == 4 and public["agreement"]["matched"] == 4


def test_gate_refusal_is_recorded_not_raised(tmp_path):
    member, archive = _member(tmp_path)
    result = runner.run_wave([member], _ctx("stage_b_only", stage_b=FakeStageB(good=False)), tmp_path / "w", archive_root=archive,
                             manifest_binding=BINDING, authorize=lambda s: None, git_tip="x")
    assert result["counts"]["admitted"] == 0 and result["counts"]["refused_by_gate"] == 1
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert "sum_mismatch" in public["gate"]["reasons"]


def test_reader_baseline_arm_needs_no_models(tmp_path):
    member, archive = _member(tmp_path)
    result = runner.run_wave([member], _ctx("reader_baseline"), tmp_path / "w", archive_root=archive,
                             manifest_binding=BINDING, authorize=lambda s: None, git_tip="x")
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["reader_outcome"] == "validated" and result["counts"]["reader_validated"] == 1


def test_resume_skips_existing_and_wave_dir_is_never_reused(tmp_path):
    member, archive = _member(tmp_path)
    ctx = _ctx("stage_a_rules", stage_a=FakeStageA())
    runner.run_wave([member], ctx, tmp_path / "w", archive_root=archive, manifest_binding=BINDING,
                    authorize=lambda s: None, git_tip="x")
    with pytest.raises(runner.Refused) as exc:
        runner.run_wave([member], ctx, tmp_path / "w", archive_root=archive, manifest_binding=BINDING,
                        authorize=lambda s: None, git_tip="x")
    assert exc.value.code == "wave_already_attempted"
    result = runner.run_wave([member], ctx, tmp_path / "w2", archive_root=archive, manifest_binding=BINDING,
                             authorize=lambda s: None, git_tip="x", resume_from=tmp_path / "w")
    assert result["counts"]["skipped_existing"] == 1 and result["counts"]["attempted"] == 0


def test_transport_failure_recorded_and_aborts_after_three(tmp_path):
    from vlm.client import TransportError

    class Broken:
        def version(self):
            return {}

        def parse_page(self, *a, **k):
            raise TransportError("connection_failed:ConnectionRefusedError")

    members = [Member(f"{i:064X}", "fam/doc.pdf", 100, 1, "fam", "digital", "failed", 1) for i in range(5)]
    _, archive = _member(tmp_path)
    result = runner.run_wave(members, _ctx("stage_a_rules", stage_a=Broken()), tmp_path / "w", archive_root=archive,
                             manifest_binding=BINDING, authorize=lambda s: None, git_tip="x")
    assert result["status"] == "failed" and result["failure_code"] == "transport_failing" and result["counts"]["failed"] == 3


def test_authorize_is_called_with_scope(tmp_path):
    member, archive = _member(tmp_path)
    seen = []
    runner.run_wave([member], _ctx("stage_a_rules", stage_a=FakeStageA()), tmp_path / "w", archive_root=archive,
                    manifest_binding=BINDING, authorize=lambda s: seen.append(s), git_tip="x")
    assert seen == ["synthetic"]


def test_stage_b_concurrency_keeps_page_order(tmp_path):
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    import pypdfium2 as pdfium
    one = render_native_pdf(build_ledger_page(n_rows=4))
    doc = pdfium.PdfDocument(one)
    merged = pdfium.PdfDocument.new()
    for _ in range(3):
        merged.import_pages(doc)
    (archive / "fam" / "three.pdf").write_bytes(merged.save_to_bytes() if hasattr(merged, "save_to_bytes") else _save(merged))
    member = Member(SHA, "fam/three.pdf", 100, 3, "fam", "digital", "validated", 1)
    ctx = runner.RunContext(arm="stage_b_only", stage_a=None, stage_b=FakeStageB(), stage_b_model="fake-vlm", truth=None,
                            long_edge=600, quality=80, seed=0, data_scope="synthetic", hourly_rate=None, concurrency=3)
    result = runner.run_wave([member], ctx, tmp_path / "w", archive_root=archive, manifest_binding=BINDING,
                             authorize=lambda s: None, git_tip="x")
    assert result["counts"]["attempted"] == 1
    private = json.loads((tmp_path / "w" / "results" / f"{SHA}.private.json").read_text(encoding="utf-8"))
    assert [t["page"] for t in private["stage_b"]] == [0, 1, 2]
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["pages"] == 3 and public["timings"]["prompt_tokens"] == 300


def _save(doc):
    import io
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
