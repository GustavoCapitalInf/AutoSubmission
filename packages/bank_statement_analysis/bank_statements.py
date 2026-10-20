"""The bank statement folder, named by the `BANK_STATEMENTS_DIR` environment variable.

Statements are customer data and stay out of the repository. The folder is the corpus root that the pinned
manifest's paths (`docs/balance-metrics-audit-results.csv`) are relative to.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "BANK_STATEMENTS_DIR"


def bank_statements_dir() -> Path | None:
    """None when the variable is unset or empty."""
    value = os.environ.get(ENV_VAR, "")
    return Path(value) if value else None


def bank_statements_dir_or_exit() -> Path:
    root = bank_statements_dir()
    if root is None:
        raise SystemExit(f"{ENV_VAR} is not set: point it at the bank statement folder, or pass the folder explicitly.")
    return root
