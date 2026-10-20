"""tools.holdout — the sealed truth store, the unseen holdout cage and their
non-sensitive repository digest (Phase 2.2 cell H, `P22-HOLDOUT`; rulings R3
and R4; umbrella decision D9).

Standard library only. Nothing here imports `analysis`, `ocr`, `layout`,
`evidence`, `discovery`, `webapp` or `telemetry`, and none of those may import
this package or name its environment variable — `tests/test_truth_firewall.py`
is the tripwire on both directions. The store lives OUTSIDE every checkout at
`SEALED_TRUTH_DIR`; the repository sees only `docs/moneythumb-replacement/
truth/MANIFEST_DIGEST.txt` (store version, record count, chain heads, sha16
prefixes — never a verdict, figure, kind, date or name).
"""
from .store import (  # noqa: F401
    GENESIS,
    SEALED_TRUTH_DIR_ENV,
    STORE_VERSION,
    ChainError,
    RecordError,
    StoreError,
    StoreLocationError,
)

__all__ = [
    "GENESIS",
    "SEALED_TRUTH_DIR_ENV",
    "STORE_VERSION",
    "ChainError",
    "RecordError",
    "StoreError",
    "StoreLocationError",
]
