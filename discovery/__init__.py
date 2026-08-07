"""DSC-1: the discovery runner.

Takes a directory of arbitrary PDFs and produces an intake-and-outcome report,
consuming ONLY merged platform pieces: O-1 preflight profiles, the production
intake ladder, D-3's content-addressed cache, R-3's registry dispatch, and H-3
telemetry. It owns no routing decisions, no parsers, and no financial logic of
its own.

    python -m discovery --dry-run        # the pinned 109, offline. The gate.
    python -m discovery --profile-only   # tranche 0
    python -m discovery --digital        # tranche 1
    python -m discovery --scanned        # tranche 2 (needs local tesseract)

Offline by construction in every mode: `parse_mode="deterministic"` makes the
LLM branch unreachable and `allow_visual_ocr=False` means `ocr.ocr_client` is
never even imported. Tests assert both.

Two artifacts, two audiences: H-3 telemetry records (hashes and codes, no paths
— the H-3 sensitivity invariant) and the discovery report (relative paths and
folder labels for human adjudication, account identifiers masked last-4, no
transaction-level detail). Both land in gitignored directories.
"""
from __future__ import annotations

from .inventory import (
    DedupIndex,
    Inventory,
    baseline_deviations,
    enumerate_root,
    pinned_hashes,
    pinned_manifest,
)
from .report import folder_agreement, render_report, summarize
from .runner import (
    MODE_DIGITAL,
    MODE_DRY_RUN,
    MODE_PROFILE_ONLY,
    MODE_SCANNED,
    DiscoveryRunner,
    DocumentRow,
)

__all__ = [
    "DedupIndex",
    "DiscoveryRunner",
    "DocumentRow",
    "Inventory",
    "MODE_DIGITAL",
    "MODE_DRY_RUN",
    "MODE_PROFILE_ONLY",
    "MODE_SCANNED",
    "baseline_deviations",
    "enumerate_root",
    "folder_agreement",
    "pinned_hashes",
    "pinned_manifest",
    "render_report",
    "summarize",
]
