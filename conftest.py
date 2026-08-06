from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent

@pytest.fixture
def samples_dir() -> Path:
    # The corpus folder name contains a space. Assert rather than return a path
    # that silently resolves to nothing if the folder is ever renamed.
    p = PROJECT_ROOT / "Bank Statements"
    assert p.is_dir(), f"missing statement corpus folder: {p}"
    return p

@pytest.fixture
def sample_pdf(samples_dir) -> Path:
    # A known, small digital PDF used across rasterize/live tests.
    p = samples_dir / "Chase" / "Chase Salomon January.pdf"
    assert p.exists(), f"missing sample: {p}"
    return p


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits the real OCR endpoint (run with -m live)")


@pytest.fixture
def first_page_image(sample_pdf):
    from ocr.rasterize import rasterize_pdf
    return rasterize_pdf(sample_pdf.read_bytes(), dpi=150)[0]
