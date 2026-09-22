from pathlib import Path

from vlm import report
from vlm.receipts import dump_new


def _wave(tmp_path: Path) -> Path:
    wave = tmp_path / "wave"
    (wave / "results").mkdir(parents=True)
    dump_new(wave / "launch.json", {"arm": "hybrid", "started_at": "t"})
    docs = [
        {"sha": "A" * 64, "arm": "hybrid", "family": "famA", "reader_outcome": "failed", "pages": 2, "rows_proposed": 10,
         "gate": {"admitted": True, "reasons": [], "chain_derived_directions": 1},
         "timings": {"total_ms": 1000.0, "stage_a_ms": 400.0, "stage_b_ms": 500.0, "render_ms": 50.0, "encode_ms": 10.0, "gate_ms": 1.0, "prompt_tokens": 2000, "completion_tokens": 400},
         "stats": {"pages_by_role": {"statement_page": 2}},
         "match": {"truth_rows": 10, "candidate_rows": 10, "matched": 9, "exact_balance": 9, "exact_description": 8, "missing": 1, "extra": 1},
         "upload_bytes": 300000, "failure": None},
        {"sha": "B" * 64, "arm": "hybrid", "family": "famA", "reader_outcome": "validated", "pages": 1, "rows_proposed": 3,
         "gate": {"admitted": False, "reasons": ["sum_mismatch", "continuity_break"], "chain_derived_directions": 0},
         "timings": {"total_ms": 3000.0, "stage_a_ms": 1000.0, "stage_b_ms": 1500.0, "render_ms": 30.0, "encode_ms": 5.0, "gate_ms": 1.0, "prompt_tokens": 1000, "completion_tokens": 200},
         "stats": {"pages_by_role": {"statement_page": 1}}, "match": None, "upload_bytes": 150000, "failure": None},
        {"sha": "C" * 64, "arm": "hybrid", "failure": {"class": "TransportError", "code": "http_500"}},
    ]
    for doc in docs:
        dump_new(wave / "results" / f"{doc['sha']}.json", doc)
    dump_new(wave / "result.json", {"arm": "hybrid", "status": "complete",
                                    "counts": {"requested": 3, "attempted": 3, "admitted": 1, "refused_by_gate": 1, "failed": 1, "skipped_existing": 0},
                                    "timings": {"pages": 3}, "wall_s": 10.0, "instance_hours": 10 / 3600, "cost_usd": "rate not measured"})
    return wave


def test_build_report_metrics(tmp_path):
    wave = _wave(tmp_path)
    rep = report.build_report(wave)
    assert rep["arm"] == "hybrid" and rep["documents"]["admitted"] == 1 and rep["admission_rate"] == 1 / 3
    assert rep["reasons"] == {"continuity_break": 1, "sum_mismatch": 1}
    assert rep["by_reader_outcome"]["failed"] == {"attempted": 1, "admitted": 1}
    assert rep["rows"]["matched"] == 9 and rep["rows"]["match_rate"] == 0.9
    assert rep["latency"]["document_total_ms"]["p50"] == 2000.0
    assert rep["latency"]["stage_b_ms_per_page"] == (500.0 + 1500.0) / 3
    assert rep["failures"] == {"http_500": 1} and rep["pages_by_role"] == {"statement_page": 3}
    assert rep["taxonomy"][0]["reasons"] == ["sum_mismatch", "continuity_break"]
    assert rep["cost_usd"] == "rate not measured" and rep["upload_bytes_per_page"] == 150000.0


def test_write_report_and_markdown(tmp_path):
    wave = _wave(tmp_path)
    path = report.write_report(wave)
    assert path.exists() and path.name.startswith("report-")
    assert any(p.name.startswith("REPORT-") and p.suffix == ".md" for p in wave.iterdir())
    text = report.render_markdown(report.build_report(wave))
    assert "hybrid" in text and "sum_mismatch" in text and "A" * 64 not in text


def test_percentiles():
    assert report.percentiles([1, 2, 3, 4], (50, 95, 99)) == {"p50": 2.5, "p95": 3.85, "p99": 3.97}
    assert report.percentiles([], (50,)) == {"p50": None}
