import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("OCR_BASE_URL"),
                    reason="set OCR_BASE_URL to run the live smoke test")
def test_live_single_page_returns_markdown(first_page_image):
    from ocr.ocr_client import ocr_page
    md = ocr_page(first_page_image)
    assert isinstance(md, str) and md.strip()


@pytest.mark.skipif(not os.environ.get("OCR_BASE_URL"),
                    reason="set OCR_BASE_URL to run the live smoke test")
def test_live_visual_rung_probe_agrees_with_a_real_read(first_page_image):
    """W3-5: the preflight `--scanned-visual` runs before a tranche.

    Opt-in by design (`-m live`, plus `OCR_BASE_URL`): the default suite is
    fully offline and a discovery agent must never be able to start a GPU on a
    developer's machine by running `pytest`. Run it against the local server
    before a tranche-3 run:

        OCR_BASE_URL=http://localhost:8000/v1 python -m pytest -m live

    The assertion is the CONTRACT, not the transcription: if the probe says the
    endpoint is usable then a page must actually come back, because the whole
    point of refusing to start is that a green probe means the run can proceed.
    """
    from ocr.availability import probe_visual_ocr
    from ocr.ocr_client import ocr_page

    status = probe_visual_ocr()
    assert status.usable, status.message()
    assert status.model in (status.advertised or (status.model,))
    assert ocr_page(first_page_image).strip()
