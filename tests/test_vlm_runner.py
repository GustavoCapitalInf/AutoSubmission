import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from vlm import runner
from vlm.partitions import Member
from vlm.schema import empty_proposal

SHA = "F" * 64
REMOTE = SimpleNamespace(provider="vast.ai", execution_class="remote_paid", is_remote=True)
LOCAL = SimpleNamespace(provider="local", execution_class="local_free", is_remote=False)
BINDING = {"path": "m", "sha256": "0" * 64}


def _table_html(n=4):
    rows = "".join(
        f"<tr><td>2031-01-{i:02d}</td><td>SYNTHETIC ROW {i:02d}</td><td>{i * 10:.2f}</td><td>{500 + sum(range(1, i + 1)) * 10:.2f}</td></tr>"
        for i in range(1, n + 1))
    return f"<table><tr><th>Date</th><th>Description</th><th>Deposits</th><th>Balance</th></tr>{rows}</table>"


class FakeStageA:
    def __init__(self, provider="vast.ai", execution_class="remote_paid"):
        self.calls = 0
        self.identity = {"provider": provider, "execution_class": execution_class}

    def version(self):
        return {"model": "fake-parser", "pipeline_version": "v1.6", "retention": "none", **self.identity}

    def parse_page(self, jpeg, *, request_id, page_index):
        self.calls += 1
        return {"blocks": [
            {"label": "text", "bbox": [0, 0, 100, 10], "content": "Beginning Balance 500.00\nEnding Balance 600.00\nStatement Period 01/01/2031 - 01/31/2031", "order": 0},
            {"label": "table", "bbox": [0, 20, 100, 90], "content": _table_html(), "order": 1}],
            "timing": {"total_ms": 2.0}}


class FakeStageB:
    def __init__(self, good=True, limit=32768):
        self.good = good
        self.limit = limit
        self.calls = 0

    def models(self):
        return ["fake-vlm"]

    def model_limits(self):
        return {"fake-vlm": self.limit}

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
                                     "amount": float(i * 10), "direction": "credit", "balance": balance,
                                     "continues_previous": False})
        text = json.dumps(proposal)
        return ChatResult(text=text, parsed=proposal, parse_error=None, finish_reason="stop", prompt_tokens=100,
                          completion_tokens=50, total_ms=3.0, request_sha256="a" * 64, response_sha256="b" * 64,
                          content_sha256="c" * 64)


def _member(tmp_path) -> tuple[Member, Path]:
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "doc.pdf").write_bytes(render_native_pdf(build_ledger_page(n_rows=4)))
    return Member(SHA, "fam/doc.pdf", 100, 1, "fam", "digital", "validated", 1), archive


def _ctx(arm, stage_a=None, stage_b=None, identity=None, **kw):
    base = dict(arm=arm, stage_a=stage_a, stage_b=stage_b, stage_b_model="fake-vlm", truth=None, long_edge=800, quality=85,
                seed=0, data_scope="synthetic", hourly_rate=None, identity_client=identity)
    base.update(kw)
    return runner.RunContext(**base)


def _wave(members, ctx, out, archive, **kw):
    params = dict(archive_root=archive, manifest_binding=BINDING, manifest_scope="synthetic", authorize=lambda s: None,
                  git_tip="x", settings=REMOTE)
    params.update(kw)
    return runner.run_wave(members, ctx, out, **params)


def test_stage_a_rules_arm_admits_synthetic_ledger(tmp_path):
    member, archive = _member(tmp_path)
    result = _wave([member], _ctx("stage_a_rules", stage_a=FakeStageA()), tmp_path / "wave", archive)
    assert result["status"] == "complete" and result["counts"]["admitted"] == 1 and result["counts"]["attempted"] == 1
    public = json.loads((tmp_path / "wave" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["gate"]["admitted"] and public["gate"]["anchored"] == "both" and public["rows_proposed"] == 4 and public["pages"] == 1
    assert public["timings"]["stage_a_ms"] >= 0 and len(public["page_hashes"]) == 1
    assert "fam/doc.pdf" not in json.dumps(public)
    private = json.loads((tmp_path / "wave" / "results" / f"{SHA}.private.json").read_text(encoding="utf-8"))
    assert private["rows"][0]["amount"] == "10.00" and private["meta"]["beginning_balance"] == "500.00"
    launch = json.loads((tmp_path / "wave" / "launch.json").read_text(encoding="utf-8"))
    assert launch["identity"]["checked"] and launch["identity"]["echo"]["execution_class"] == "remote_paid"
    assert launch["prompt"]["stage_b_template_sha256"] and launch["prompt"]["hybrid_prefix_template_sha256"]
    assert launch["manifest_scope"] == "synthetic" and (tmp_path / "wave" / "release.json").exists()


def test_stage_b_and_hybrid_arms(tmp_path):
    member, archive = _member(tmp_path)
    b = FakeStageB()
    result = _wave([member], _ctx("stage_b_only", stage_b=b, identity=FakeStageA()), tmp_path / "w1", archive)
    assert result["counts"]["admitted"] == 1 and b.calls == 1
    a = FakeStageA()
    result = _wave([member], _ctx("hybrid", stage_a=a, stage_b=FakeStageB()), tmp_path / "w2", archive)
    assert result["counts"]["admitted"] == 1 and a.calls == 1
    public = json.loads((tmp_path / "w2" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["agreement"]["stage_a_rows"] == 4 and public["agreement"]["matched"] == 4
    assert "account_last4_values" not in json.dumps(public) and public["stage_b_content_hashes"] == ["c" * 64]


def test_gate_refusal_is_recorded_not_raised(tmp_path):
    member, archive = _member(tmp_path)
    result = _wave([member], _ctx("stage_b_only", stage_b=FakeStageB(good=False), identity=FakeStageA()), tmp_path / "w", archive)
    assert result["counts"]["admitted"] == 0 and result["counts"]["refused_by_gate"] == 1
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert "sum_mismatch" in public["gate"]["reasons"]


def test_reader_baseline_arm_needs_no_models_or_settings(tmp_path):
    member, archive = _member(tmp_path)
    result = _wave([member], _ctx("reader_baseline"), tmp_path / "w", archive, settings=None)
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["reader_outcome"] == "validated" and result["counts"]["reader_validated"] == 1


def test_identity_refusals(tmp_path):
    member, archive = _member(tmp_path)
    with pytest.raises(runner.Refused) as exc:
        _wave([member], _ctx("stage_a_rules", stage_a=FakeStageA()), tmp_path / "w1", archive, settings=LOCAL)
    assert exc.value.code == "local_declaration_with_model_endpoints"
    with pytest.raises(runner.Refused) as exc:
        _wave([member], _ctx("stage_a_rules", stage_a=FakeStageA(provider="local", execution_class="local_free")), tmp_path / "w2", archive)
    assert exc.value.code == "vlm_identity_mismatch"
    with pytest.raises(runner.Refused) as exc:
        _wave([member], _ctx("stage_b_only", stage_b=FakeStageB()), tmp_path / "w3", archive)
    assert exc.value.code == "identity_probe_missing"
    assert not (tmp_path / "w1").exists() and not (tmp_path / "w2").exists()


def test_scope_bound_to_manifest(tmp_path):
    member, archive = _member(tmp_path)
    with pytest.raises(runner.Refused) as exc:
        _wave([member], _ctx("reader_baseline"), tmp_path / "w", archive, manifest_scope="customer", settings=None)
    assert exc.value.code == "data_scope_disagrees_with_manifest" and not (tmp_path / "w").exists()


def test_resume_retries_failures_and_wave_dir_is_never_reused(tmp_path):
    member, archive = _member(tmp_path)
    ctx = _ctx("stage_a_rules", stage_a=FakeStageA())
    _wave([member], ctx, tmp_path / "w", archive)
    with pytest.raises(runner.Refused) as exc:
        _wave([member], ctx, tmp_path / "w", archive)
    assert exc.value.code == "wave_already_attempted"
    result = _wave([member], ctx, tmp_path / "w2", archive, resume_from=tmp_path / "w")
    assert result["counts"]["skipped_existing"] == 1 and result["counts"]["attempted"] == 0

    from vlm.client import TransportError

    class Broken(FakeStageA):
        def parse_page(self, *a, **k):
            raise TransportError("connection_failed:ConnectionRefusedError")

    members = [Member(f"{i:064X}", "fam/doc.pdf", 100, 1, "fam", "digital", "failed", 1) for i in range(5)]
    first = _wave(members, _ctx("stage_a_rules", stage_a=Broken()), tmp_path / "f1", archive)
    assert first["status"] == "failed" and first["failure_code"] == "transport_failing" and first["counts"]["failed"] == 3
    second = _wave(members, _ctx("stage_a_rules", stage_a=FakeStageA()), tmp_path / "f2", archive, resume_from=tmp_path / "f1")
    assert second["counts"]["skipped_existing"] == 0 and second["counts"]["attempted"] == 5


def test_limit_is_reported_separately(tmp_path):
    _, archive = _member(tmp_path)
    members = [Member(f"{i:064X}", "fam/doc.pdf", 100, 1, "fam", "digital", "failed", 1) for i in range(4)]
    result = _wave(members, _ctx("reader_baseline"), tmp_path / "w", archive, limit=1, settings=None)
    assert result["counts"]["attempted"] == 1 and result["counts"]["skipped_existing"] == 0 and result["counts"]["limited_out"] == 3


def test_interrupted_wave_is_receipted_as_aborted(tmp_path):
    _, archive = _member(tmp_path)

    class Interrupting(FakeStageA):
        def parse_page(self, *a, **k):
            raise KeyboardInterrupt

    members = [Member(f"{i:064X}", "fam/doc.pdf", 100, 1, "fam", "digital", "failed", 1) for i in range(2)]
    with pytest.raises(KeyboardInterrupt):
        _wave(members, _ctx("stage_a_rules", stage_a=Interrupting()), tmp_path / "w", archive)
    result = json.loads((tmp_path / "w" / "result.json").read_text(encoding="utf-8"))
    release = json.loads((tmp_path / "w" / "release.json").read_text(encoding="utf-8"))
    assert result["status"] == "aborted" and result["failure_code"] == "interrupted" and release["controller_exit"] == 1


def test_authorize_is_called_with_scope(tmp_path):
    member, archive = _member(tmp_path)
    seen = []
    _wave([member], _ctx("stage_a_rules", stage_a=FakeStageA()), tmp_path / "w", archive, authorize=lambda s: seen.append(s))
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
    buf = io.BytesIO()
    merged.save(buf)
    (archive / "fam" / "three.pdf").write_bytes(buf.getvalue())
    member = Member(SHA, "fam/three.pdf", 100, 3, "fam", "digital", "validated", 1)
    ctx = _ctx("stage_b_only", stage_b=FakeStageB(), identity=FakeStageA(), long_edge=600, quality=80, concurrency=3)
    result = _wave([member], ctx, tmp_path / "w", archive)
    assert result["counts"]["attempted"] == 1
    private = json.loads((tmp_path / "w" / "results" / f"{SHA}.private.json").read_text(encoding="utf-8"))
    assert [t["page"] for t in private["stage_b"]] == [0, 1, 2]
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["pages"] == 3 and public["timings"]["prompt_tokens"] == 300 and public["timings"]["stage_b_wall_ms"] >= 0


def test_hybrid_arm_rescues_a_model_miss_with_the_parser_rows(tmp_path):
    member, archive = _member(tmp_path)

    class DroppingStageB(FakeStageB):
        def chat(self, *a, **k):
            result = super().chat(*a, **k)
            result.parsed["rows"].pop(2)   # the model misses one row; the parser's table has all four
            return result

    result = _wave([member], _ctx("hybrid", stage_a=FakeStageA(), stage_b=DroppingStageB()), tmp_path / "w", archive)
    assert result["counts"]["admitted"] == 1
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["gate"]["admitted"] and public["gate"]["admitted_candidate"] == "stage_a"
    assert public["stats"]["candidate_reasons"]["stage_b"] and public["stats"]["candidate_reasons"]["stage_a"] == []
    assert public["rows_proposed"] == 4


def test_stage_b_context_preflight_refuses_a_server_that_cannot_hold_a_dense_page(tmp_path):
    from vlm.receipts import Refused

    member, archive = _member(tmp_path)
    with pytest.raises(Refused) as exc:
        _wave([member], _ctx("stage_b_only", stage_b=FakeStageB(limit=16384), identity=FakeStageA()), tmp_path / "w-small", archive)
    assert exc.value.code == "stage_b_context_too_small"
    with pytest.raises(Refused) as exc:
        _wave([member], _ctx("stage_b_only", stage_b=FakeStageB(), identity=FakeStageA(), stage_b_model="other-vlm"), tmp_path / "w-other", archive)
    assert exc.value.code == "stage_b_model_not_served"
    _wave([member], _ctx("stage_b_only", stage_b=FakeStageB(), identity=FakeStageA()), tmp_path / "w-ok", archive)
    launch = json.loads((tmp_path / "w-ok" / "launch.json").read_text(encoding="utf-8"))
    assert launch["stage_b_context"] == {"checked": True, "max_model_len": 32768, "max_tokens": 12000, "min_prompt_tokens": 8192}
