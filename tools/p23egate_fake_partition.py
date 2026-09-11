"""tools/p23egate_fake_partition.py — build a SYNTHETIC research partition
with the in-process fake worker and run the census over it (P23-EGATE step 5).

    python tools/p23egate_fake_partition.py <work dir>

Why this is committed. The census numbers in the record are headline numbers,
so the thing that produced them is committed and re-runnable — including the
partition they were measured over. It writes seven synthetic documents (the
clean ledger and one per defect page) through the REAL research run mode —
the router, the research trigger, the Paddle rung, the research partition key,
the artifact cache — against `tests/paddle_fake_worker.FakeWorker`, retains
their rasters the way Phase 2.3 D2 says a research partition does, and then
runs the committed census instrument over the result.

No network, no archive, no production cache: every page is rendered from
literal strings by `tests/paddle_synthetic.py`, the "engine" answers in
process, and the work directory is created fresh under whatever path the
caller names (never a `webapp_data*` one — the census would refuse it).

The partly-covered case is the interesting one: the page is RENDERED whole
and the worker reports only its top six lines, which is what an extractor
that missed regions produces. The rotated case is the honest one: its raster
carries horizontal glyphs at rotated box positions (the fixture renderer draws
text one way only), so that page's boxes genuinely do not cover its ink and it
fires E1 as well as E3 — which is why the census reports every class a page
fired beside the one its precedence names.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Hermetic: the checkout's git-ignored `.env` carries real PADDLE_* values and
# `load_dotenv(override=False)` re-injects any that are ABSENT, so every one of
# them is set here to a value of this script's own. The worker URL is the fake
# one, on loopback, assigned below.
for _name in list(os.environ):
    if _name.startswith("PADDLE_"):
        os.environ[_name] = ""
os.environ.update({
    "PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "remote_paid",
    "PADDLE_VAST_HOST": "test-host.invalid", "PADDLE_VAST_SSH_PORT": "22",
    "PADDLE_VAST_SSH_USER": "test-user", "RECONSTRUCTION_MODE": "off",
    "OCR_MAX_WORKERS": "1",
})

from discovery.inventory import DedupIndex                         # noqa: E402
from discovery.runner import MODE_RESEARCH_PADDLE, DiscoveryRunner  # noqa: E402
from ocr.inspect import inspect_pdf                                 # noqa: E402
from ocr.paddle_config import (                                     # noqa: E402
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL,
)
from ocr.rasterize import rasterize_pdf                             # noqa: E402
from tests.paddle_fake_worker import FakeWorker                     # noqa: E402
from tests.paddle_synthetic import (                                # noqa: E402
    build_garbage_token_page, build_ledger_page, build_noise_page,
    build_repeated_letter_page, keep_first_lines, render_image_pdf,
    render_native_pdf, rotate_page_90, substitute_digit_glyphs,
    synthetic_paddle_result,
)
from tools.extraction_quality_census import main as census_main     # noqa: E402
from webapp.artifact_cache import open_cache                        # noqa: E402

PARTITION = "egate-fake-worker-a"
ROWS = 20
DPI = 300


def cases() -> dict:
    """name -> (the page RENDERED to the image PDF, the page the worker reports)."""
    clean = build_ledger_page(ROWS)
    return {
        "clean": (clean, clean),
        "partly-covered": (clean, keep_first_lines(clean, 6)),
        "noise": (build_noise_page(), build_noise_page()),
        "rotated": (rotate_page_90(clean), rotate_page_90(clean)),
        "glyph-substituted": (substitute_digit_glyphs(clean), substitute_digit_glyphs(clean)),
        "garbage-tokens": (build_garbage_token_page(), build_garbage_token_page()),
        "repeated-letters": (build_repeated_letter_page(), build_repeated_letter_page()),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit(__doc__.splitlines()[2].strip())
    work = Path(argv[0]).expanduser().resolve()
    if work.exists():
        shutil.rmtree(work)
    built = cases()

    root = work / "root"
    (root / "Synth").mkdir(parents=True)
    shas: dict[str, str] = {}
    for name, (rendered, _) in built.items():
        path = root / "Synth" / f"{name}.pdf"
        path.write_bytes(render_image_pdf(rendered, dpi=DPI))
        shas[name] = inspect_pdf(path.read_bytes()).content_sha256

    data_dir = work / "research_data"
    cache = open_cache(data_dir)
    reported = {sha: built[name][1] for name, sha in shas.items()}
    current: list[str] = []

    def result_for(page_index, image_bytes):
        return synthetic_paddle_result(reported[current[-1]], dpi=DPI)

    import ocr.pipeline as pipeline
    pipeline.parse_local_tesseract = lambda *a, **k: None   # the offline ladder produces nothing

    with FakeWorker(result_for=result_for) as fake:
        os.environ["PADDLE_WORKER_URL"] = fake.url
        os.environ[PADDLE_REMOTE_OPT_IN_ENV] = PADDLE_REMOTE_OPT_IN_LITERAL
        os.environ[PADDLE_CUSTOMER_DATA_OPT_IN_ENV] = PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL
        runner = DiscoveryRunner(root, mode=MODE_RESEARCH_PADDLE, run_id="egate-fake",
                                 dedup=DedupIndex(), cache=cache,
                                 population=frozenset(shas.values()), research_partition=PARTITION)
        print("the ROW's columns (no raster reaches a row: production keeps only raster_sha256)\n")
        for name, sha in shas.items():
            current.append(sha)
            row = runner.process(f"Synth/{name}.pdf", "Synth")
            print(f"{name:>18}: stage_extract={row.stage_extract} evidence={row.stage_evidence} "
                  f"eq_class={row.eq_class!r} eq_word_count={row.eq_word_count} "
                  f"eq_money_rate={row.eq_money_rate} eq_lexicon_rate={row.eq_lexicon_rate} "
                  f"eq_garbage_rate={row.eq_garbage_rate} eq_line_height_cv={row.eq_line_height_cv} "
                  f"eq_orientation_votes={row.eq_orientation_votes} "
                  f"eq_ink_outside_boxes={row.eq_ink_outside_boxes!r}", flush=True)

    rasters = data_dir / "rasters"      # D2: a research partition retains them
    for name, sha in shas.items():
        (rasters / sha).mkdir(parents=True, exist_ok=True)
        rasterize_pdf(render_native_pdf(built[name][0]), dpi=DPI)[0].save(rasters / sha / "0.png")

    print("\n=== the committed instrument, over that partition ===\n", flush=True)
    return census_main(["--data-dir", str(data_dir), "--research-partition", PARTITION])


if __name__ == "__main__":
    raise SystemExit(main())
