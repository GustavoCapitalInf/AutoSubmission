import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("NANONETS_BASE_URL"),
                    reason="set NANONETS_BASE_URL to run the live smoke test")
def test_live_single_page_returns_markdown(first_page_image):
    from ocr.ocr_client import ocr_page
    md = ocr_page(first_page_image)
    assert isinstance(md, str) and md.strip()
