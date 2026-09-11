"""P23-EGATE item 5: the extraction-quality census over a research partition.

The partition here is REAL in every respect except the engine: synthetic
PDFs, rendered from literal strings, read through the actual research run
mode (`--research-paddle` -> the router -> the Paddle rung) against the
in-process fake worker, cached under a real research partition key in a
temporary directory. The census then reads that cache exactly as it will
read cell W's — the same artifacts, the same shapes, the same door.

What is proven here:

* the census measures what is there, per CONFIGURATION taken from the
  evidence's own recorded identity, and counts what it could not measure
  rather than dropping it;
* its output carries counts and percentiles and NOTHING else — the synthetic
  pages' own literal strings and their document shas are grepped for in the
  rendered tables (M9);
* a production or historical `--data-dir` is refused at the door, by cell T's
  refusal, and a malformed partition id is refused before anything is read;
* the ink metric is measured when a retained raster is there and UNMEASURED,
  counted, when it is not.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from discovery.inventory import DedupIndex
from discovery.runner import MODE_RESEARCH_PADDLE, DiscoveryRunner
from ocr.inspect import inspect_pdf
from ocr.paddle_config import (
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
)
from tests.paddle_fake_worker import FakeWorker
from tests.paddle_synthetic import (
    SYNTHETIC_YEAR,
    build_ledger_page,
    render_image_pdf,
    render_native_pdf,
    synthetic_paddle_result,
)
from tools.extraction_quality_census import census, configuration_of, percentile, render

PARTITION = "egate-synthetic-a"
ROWS = 20


def _clear_paddle(monkeypatch) -> None:
    """Hermetic: the main checkout's git-ignored `.env` carries real PADDLE_*
    values and `load_dotenv(override=False)` re-injects any that are ABSENT,
    so every one of them is set to a value of this test's own."""
    for name in list(os.environ):
        if name.startswith("PADDLE_"):
            monkeypatch.setenv(name, "")
    for name in ("PADDLE_PROVIDER", "PADDLE_EXECUTION_CLASS", "PADDLE_VAST_HOST",
                 "PADDLE_VAST_SSH_PORT", "PADDLE_VAST_SSH_USER", "PADDLE_WORKER_URL",
                 "PADDLE_WORKER_PORT", "PADDLE_TUNNEL_LOCAL_PORT", "PADDLE_RUNTIME_DIR",
                 PADDLE_REMOTE_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_ENV):
        monkeypatch.setenv(name, "")


def _research_env(monkeypatch, worker_url: str) -> None:
    _clear_paddle(monkeypatch)
    monkeypatch.setenv("PADDLE_PROVIDER", "vast.ai")
    monkeypatch.setenv("PADDLE_EXECUTION_CLASS", "remote_paid")
    monkeypatch.setenv("PADDLE_VAST_HOST", "test-host.invalid")
    monkeypatch.setenv("PADDLE_VAST_SSH_PORT", "22")
    monkeypatch.setenv("PADDLE_VAST_SSH_USER", "test-user")
    monkeypatch.setenv("PADDLE_WORKER_URL", worker_url)
    monkeypatch.setenv(PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL)
    monkeypatch.setenv(PADDLE_CUSTOMER_DATA_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL)
    monkeypatch.setenv("RECONSTRUCTION_MODE", "off")
    # the offline ladder produces nothing, so every document takes the
    # recovery path and the research read is the one of record
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)


@pytest.fixture
def partition(tmp_path, monkeypatch) -> dict:
    """A research partition of two synthetic one-page ledgers, written by the
    real runner through the real research mode against the fake worker."""
    from webapp.artifact_cache import open_cache

    root = tmp_path / "root"
    (root / "SynthA").mkdir(parents=True)
    pages = {"scan-a.pdf": build_ledger_page(ROWS), "scan-b.pdf": build_ledger_page(ROWS - 2)}
    for name, page in pages.items():
        (root / "SynthA" / name).write_bytes(render_image_pdf(page))
    shas = {name: inspect_pdf((root / "SynthA" / name).read_bytes()).content_sha256 for name in pages}
    data_dir = tmp_path / "research_data"
    cache = open_cache(data_dir)

    def result_for(page_index, image_bytes):
        return synthetic_paddle_result(pages["scan-a.pdf"])

    with FakeWorker(result_for=result_for) as fake:
        _research_env(monkeypatch, fake.url)
        runner = DiscoveryRunner(root, mode=MODE_RESEARCH_PADDLE, run_id="t", dedup=DedupIndex(),
                                 cache=cache, population=frozenset(shas.values()),
                                 research_partition=PARTITION)
        rows = [runner.process(f"SynthA/{name}", "SynthA") for name in pages]
    assert all(row.research_partition == PARTITION for row in rows)
    assert all(row.stage_evidence == "present" for row in rows)
    return {"data_dir": data_dir, "shas": shas, "pages": pages, "rows": rows, "tmp": tmp_path}


# ---------------------------------------------------------------------------
# what it measures
# ---------------------------------------------------------------------------

def test_the_census_measures_every_page_of_the_partition_per_configuration(partition):
    censuses, skipped = census(partition["data_dir"], partition=PARTITION, rasters=None)
    assert skipped["measured"] == 2
    # one engine, one configuration: the label comes from the evidence's own
    # recorded runtime, not from the command line
    assert len(censuses) == 1
    label = next(iter(censuses))
    assert "extractor=" in label and "execution_class=remote_paid" in label
    one = censuses[label]
    assert one.documents == 2 and one.pages == 2
    assert len(one.values["word_count"]) == 2
    assert one.page_classes["(none)"] == 2
    assert one.document_classes["(none)"] == 2
    assert one.page_classes_any == {}  # a clean page fires nothing at all
    # no raster was supplied: the ink metric is UNMEASURED, and counted
    assert one.rasters_absent == 2 and one.rasters_measured == 0
    assert one.values["ink_outside_boxes"] == []


def test_the_row_and_the_census_agree_about_the_same_document(partition):
    """The row's columns and the census's figures come from ONE module, so a
    document's `eq_word_count` is the same number the census counted."""
    censuses, _ = census(partition["data_dir"], partition=PARTITION, rasters=None)
    counted = sorted(next(iter(censuses.values())).values["word_count"])
    assert sorted(float(row.eq_word_count) for row in partition["rows"]) == counted
    assert {row.eq_class for row in partition["rows"]} == {""}


def test_a_retained_raster_is_measured_and_a_missing_one_is_counted(partition):
    from ocr.rasterize import rasterize_pdf

    rasters = partition["tmp"] / "rasters"
    sha = partition["shas"]["scan-a.pdf"]
    (rasters / sha).mkdir(parents=True)
    image = rasterize_pdf(render_native_pdf(partition["pages"]["scan-a.pdf"]), dpi=100)[0]
    image.save(rasters / sha / "0.png")

    censuses, _ = census(partition["data_dir"], partition=PARTITION, rasters=rasters)
    one = next(iter(censuses.values()))
    assert one.rasters_measured == 1 and one.rasters_absent == 1
    assert len(one.values["ink_outside_boxes"]) == 1
    # the evidence describes the page, so almost all of its ink is inside a box
    assert one.values["ink_outside_boxes"][0] < 0.35


# ---------------------------------------------------------------------------
# what it must never print (M9)
# ---------------------------------------------------------------------------

def test_the_output_carries_counts_and_percentiles_and_no_document_content(partition):
    censuses, skipped = census(partition["data_dir"], partition=PARTITION, rasters=None)
    text = render(PARTITION, censuses, skipped=skipped)
    page = partition["pages"]["scan-a.pdf"]
    # every word the page prints, other than the two-character row indices —
    # `05` is a substring of the `p05` column header, and a census with no
    # percentile columns would prove nothing at all
    for word in {word.text for line in page.lines for word in line.words if len(word.text) > 2}:
        assert word not in text, word
    assert str(SYNTHETIC_YEAR) not in text
    for sha in partition["shas"].values():
        assert sha not in text and sha[:16] not in text
    assert str(partition["data_dir"]) not in text
    # what it DOES carry
    assert "extraction-quality census" in text and PARTITION in text
    assert "documents 2 | pages 2" in text
    assert "| p50 |" in text and "pages by E-class" in text
    assert "pages by EVERY class that fired (overlapping; never summed)" in text
    # and it survives a console that is not UTF-8: the tables are ASCII
    assert text.isascii()


def test_the_rasters_are_opened_one_page_at_a_time(partition, monkeypatch):
    """A 300-dpi Letter page is ~8 MB of grey and this host has ~2 GB. The
    census must never hold a whole document's pixels: the mapping it hands
    the metrics opens one page, and `document_quality` asks for the next only
    after the previous one has been measured and dropped."""
    from tools import extraction_quality_census as tool

    live = []
    real = tool.raster_for

    def counting(root, evidence, page_index):
        live.append(page_index)
        return real(root, evidence, page_index)

    monkeypatch.setattr(tool, "raster_for", counting)
    lazy = tool.LazyRasters(None, object())
    assert lazy.get(0) is None and lazy.get(0, "fallback") == "fallback"
    assert live == [0, 0]          # asked twice, cached never


def test_the_percentiles_are_nearest_rank_and_need_no_interpolation():
    values = [float(index) for index in range(1, 101)]
    assert percentile(values, 50) == 50.0
    assert percentile(values, 5) == 5.0
    assert percentile(values, 95) == 95.0
    assert percentile([7.0], 5) == 7.0


# ---------------------------------------------------------------------------
# the door
# ---------------------------------------------------------------------------

def test_a_production_or_historical_data_dir_is_refused_by_cell_ts_own_refusal(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_DATA_DIR", str(tmp_path / "prod_cache"))
    for bad in (tmp_path / "webapp_data", tmp_path / "webapp_data_train12_cold",
                tmp_path / "webapp_data_train12_cold" / "inner", tmp_path / "prod_cache"):
        with pytest.raises(ValueError):
            census(bad, partition=PARTITION, rasters=None)


def test_a_malformed_partition_id_is_refused_before_anything_is_read(tmp_path):
    for bad in ("has a space", "", "../escape", "x" * 100):
        with pytest.raises(SystemExit, match="research-partition"):
            census(tmp_path / "nowhere", partition=bad, rasters=None)


def test_a_directory_with_no_ocr_artifacts_says_so_rather_than_reporting_zero(tmp_path):
    with pytest.raises(SystemExit, match="no OCR artifacts"):
        census(tmp_path / "empty_research_dir", partition=PARTITION, rasters=None)


def test_the_census_writes_nothing_under_the_data_dir(partition):
    before = {path: path.stat().st_mtime_ns for path in partition["data_dir"].rglob("*") if path.is_file()}
    census(partition["data_dir"], partition=PARTITION, rasters=None)
    after = {path: path.stat().st_mtime_ns for path in partition["data_dir"].rglob("*") if path.is_file()}
    assert before == after


def test_an_out_path_that_is_not_git_ignored_is_refused(tmp_path):
    from tools.extraction_quality_census import main

    tracked = Path(__file__).resolve().parents[1] / "docs" / "egate_census_should_never_land_here.md"
    with pytest.raises(SystemExit, match="not git-ignored"):
        main(["--data-dir", str(tmp_path), "--research-partition", PARTITION, "--out", str(tracked)])
    assert not tracked.exists()


def test_the_configuration_label_is_built_from_the_evidence_not_from_the_caller(partition):
    """Two configurations are two tables. The label is the extractor's own
    recorded identity, so a rec-score column in one table is never the same
    measurement as the one beside it — the structural half of 'never compared
    across configurations'."""
    from evidence.canonical import ExtractionEvidence, from_json
    import json

    # the directory also holds the offline ladder's CACHED NEGATIVE results
    # (that run produced no read), which is why the census counts them rather
    # than assuming every artifact carries evidence
    payloads = [json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((partition["data_dir"] / "artifacts" / "ocr").rglob("*.json"))]
    documents = [payload["artifact"]["document"] for payload in payloads]
    assert any(document is None for document in documents), "the negative-result path is exercised"
    evidence = from_json(next(d for d in documents if d and d.get("evidence"))["evidence"])
    label = configuration_of(evidence)
    assert evidence.extractor_id in label and evidence.model_token in label
    other = ExtractionEvidence(
        document_sha256=evidence.document_sha256, extractor_id=evidence.extractor_id,
        model_token=evidence.model_token, pages=evidence.pages,
        runtime={**dict(evidence.runtime), "text_recognition_model_name": "a-different-recogniser"},
    )
    assert configuration_of(other) != label
