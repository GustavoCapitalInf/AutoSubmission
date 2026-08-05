import os
import warnings
from io import BytesIO
from dataclasses import replace
import pytest
from PIL import Image, ImageDraw, ImageFont

from analysis.config import load_settings as load_analysis_settings

pytestmark = pytest.mark.live


def _synthetic_statement_image() -> Image.Image:
    image = Image.new("RGB", (1600, 1100), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 38)
    except OSError:
        font = ImageFont.load_default(size=38)
    lines = (
        "POTOMAC VALLEY COMMUNITY BANK",
        "Business Checking Account 7719",
        "Statement Period 07/01/2026 - 07/31/2026",
        "Beginning Balance $1,000.00",
        "Total Credits $500.00   Total Debits $250.00",
        "07/03 CUSTOMER DEPOSIT 500.00 1,500.00",
        "07/20 ACH PAYMENT 250.00 1,250.00",
        "Ending Balance $1,250.00",
    )
    for index, line in enumerate(lines):
        draw.text((70, 70 + index * 115), line, fill="black", font=font)
    return image


def _image_pdf(image: Image.Image) -> bytes:
    pdf = BytesIO()
    image.save(pdf, format="PDF", resolution=150.0)
    return pdf.getvalue()


@pytest.mark.skipif(not os.environ.get("OCR_BASE_URL"),
                    reason="set OCR_BASE_URL to run the live smoke test")
def test_live_single_page_returns_grounded_markdown():
    from ocr.ocr_client import ocr_page
    from ocr.gemini_document import parse_gemini_document

    image = _synthetic_statement_image()

    try:
        markdown = ocr_page(image)
    except Exception as primary_error:
        warnings.warn(
            f"Unlimited OCR unavailable ({type(primary_error).__name__}); tested paid document fallback",
            RuntimeWarning,
        )
        document = parse_gemini_document(
            _image_pdf(image),
            source_file="synthetic-live-smoke.pdf",
        )
        markdown = document.to_markdown()
        assert len(document.external_attempts) == 1
    normalized = markdown.upper().replace(",", "")

    assert "POTOMAC" in normalized
    assert "VALLEY" in normalized
    assert "1000.00" in normalized


@pytest.mark.skipif(
    not load_analysis_settings().api_key,
    reason="set GEMINI_API_KEY to run the live scanned-statement cascade",
)
def test_live_scanned_unknown_bank_cascade_is_authoritative():
    from webapp.worker import analyze_pdf

    result = analyze_pdf(
        _image_pdf(_synthetic_statement_image()),
        "synthetic-potomac-statement.pdf",
    )

    assert result.error is None
    assert result.analysis is not None
    assert result.analysis["reconciliation"]["ok"] is True
    assert result.analysis["source_validation"]["ok"] is True
    assert result.analysis["metrics"]["authoritative"] is True
    assert result.analysis["statement"]["bank"].upper() == "POTOMAC VALLEY COMMUNITY BANK"
    assert len(result.analysis["statement"]["transactions"]) == 2
    assert result.analysis["extraction"]["attempt_count"] <= 2


@pytest.mark.skipif(
    not load_analysis_settings().api_key,
    reason="set GEMINI_API_KEY to run the live generic extraction smoke test",
)
def test_live_generic_extraction_for_unseen_synthetic_bank():
    from analysis.pipeline import analyze_markdown

    settings = replace(
        load_analysis_settings(),
        request_timeout_ms=60_000,
        http_attempts=1,
    )
    markdown = """
    --- Page 1 ---
    SHENANDOAH HERITAGE BANK
    Business Checking Account 4821
    Statement Period April 1, 2026 through April 30, 2026
    Beginning Balance 10,000.00
    Total Credits 2,500.00
    Total Debits 450.25
    Ending Balance 12,049.75
    04/02 MOBILE DEPOSIT CUSTOMER CHECK 2,500.00 12,500.00
    04/10 ACH DEBIT OFFICE SUPPLY CO 425.25 12,074.75
    04/25 MONTHLY SERVICE FEE 25.00 12,049.75
    """

    report = analyze_markdown(
        markdown,
        settings=settings,
        external_attempt_budget=1,
    )

    assert report.model_used == settings.model
    assert report.reconciliation.ok
    assert report.source_validation.ok
    assert report.quality.corporate_use == "approved"
    assert len(report.statement.transactions) == 3
    assert len(report.extraction_attempts) == 1
