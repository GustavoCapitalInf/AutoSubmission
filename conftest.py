import os
import shutil
import tempfile
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent

# O-1 (granted exception): route WEBAPP_DATA_DIR to a per-session tmp dir so
# test suites never write the repo-root webapp_data/. The assignment must
# happen at conftest IMPORT time — webapp.app binds its durable store when the
# test modules import it (collection), which is before any fixture can run —
# and the session fixture below owns the directory's lifecycle.
_WEBAPP_TEST_DATA_DIR = tempfile.mkdtemp(prefix="webapp_data_test_")
os.environ["WEBAPP_DATA_DIR"] = _WEBAPP_TEST_DATA_DIR

# Audit 2026-10-13 (BE-1): the web app refuses uploads that would leave its data volume below a free-space floor
# (256 MB by default). The suite writes to a temporary folder on whatever disk the runner has, so it turns the floor
# off here, at import time like the line above; the floor's own tests (tests/test_webapp_disk_guard.py) set it.
os.environ["WEBAPP_MIN_FREE_MB"] = "0"

# webapp/app.py, analysis/config.py and ocr/config.py call load_dotenv() at import, so a developer's .env (a login,
# a revenue or reconstruction mode) would change what the suite tests. CI has no .env; this makes every machine match
# it. Subprocess tests inherit the variable. python-dotenv honours it from 1.2 (requirements-analysis.txt).
os.environ["PYTHON_DOTENV_DISABLED"] = "1"


@pytest.fixture(scope="session", autouse=True)
def webapp_data_dir():
    """Session-scoped WEBAPP_DATA_DIR routing (see assignment above)."""
    yield Path(_WEBAPP_TEST_DATA_DIR)
    shutil.rmtree(_WEBAPP_TEST_DATA_DIR, ignore_errors=True)

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
    config.addinivalue_line(
        "markers", "live: runs the real local Tesseract instead of a committed OCR artifact (run with -m live)")
    config.addinivalue_line(
        "markers",
        "corpus: re-audits all 109 corpus statements offline (run with -m corpus)",
    )


@pytest.fixture
def first_page_image(sample_pdf):
    from ocr.rasterize import rasterize_pdf
    return rasterize_pdf(sample_pdf.read_bytes(), dpi=150)[0]
