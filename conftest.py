from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent

@pytest.fixture
def samples_dir() -> Path:
    return PROJECT_ROOT / "BankStatements"

@pytest.fixture
def sample_pdf(samples_dir) -> Path:
    # A known, small digital PDF used across engine/rasterize tests.
    p = samples_dir / "CHASE_BANK" / "Chase Salomon January.pdf"
    assert p.exists(), f"missing sample: {p}"
    return p
