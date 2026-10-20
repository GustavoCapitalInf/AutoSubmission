"""The real statements, for the tests that read them: from `BANK_STATEMENTS_DIR`, else the test skips."""
from pathlib import Path

import pytest

from bank_statements import ENV_VAR, bank_statements_dir


def statements_dir() -> Path:
    root = bank_statements_dir()
    if root is None:
        pytest.skip(f"{ENV_VAR} is not set")
    return root
