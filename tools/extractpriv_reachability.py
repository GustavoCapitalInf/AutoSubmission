"""Is `extract_statement` reachable with parse_mode="deterministic"? (§XP6)

The structural zero-movement claim, probed rather than only read. Two runs —
the generic structurer opt-in off (production, the gate, discovery) and on —
over a document no parser claims. Both must report `calls=[]`.

HISTORY (P22-FENCE, Phase 2.2, ruling R9): this probe was written when the
answer rested on the escalation guard's `parse_mode != "deterministic"` clause
(§EXTRACTPRIV XP9 finding 2). That guard, the second extraction and the
reconciliation-based selection behind it no longer exist; the ONE hosted call
left in `analysis/pipeline.py` sits after the deterministic-mode raises and
behind the operator opt-in. The probe's question and its answer are unchanged
— `calls=[]` in both runs — and `tests/test_pipeline_escalation_fence.py` pins
the mechanism statically and dynamically.

    python -m tools.extractpriv_reachability

Offline by construction: `extract_statement` is replaced by a sentinel that
records the call and raises, so nothing can reach a hosted model even if the
answer turns out to be "yes". It analyses one string literal and publishes
nothing, which is why `corpus_gate.EXCLUDED_ANALYSIS_CALLERS` excuses it from
the sheets declaration rather than listing it as a call site.
"""
from __future__ import annotations

import os
import sys

import analysis.pipeline as pipeline

UNCLAIMED = """--- Page 1 ---
NORTHWIND MUTUAL BANK
Statement period 03/01/2026 to 03/31/2026
Beginning balance 5,000.00
Ending balance 9,999.00
Date Description Amount Balance
03/02 ORCHARD SUPPLY CO 150.00 4,850.00
03/05 CUSTOMER DEPOSIT ZEPHYR 900.00 5,750.00
03/09 TOLL BRIDGE AUTHORITY 60.00 5,690.00
03/14 QUARRY FREIGHT LLC 400.00 5,290.00
03/21 CUSTOMER DEPOSIT MARLIN 300.00 5,590.00
03/28 UTILITY DISTRICT 12 500.00 5,090.00
"""

CALLS: list[str] = []


def _sentinel(markdown, *, settings=None, model=None):
    CALLS.append(model or "<default>")
    raise RuntimeError("SENTINEL: the LLM branch was entered")


def probe(label: str, *, structurer: bool) -> None:
    CALLS.clear()
    if structurer:
        os.environ["GENERIC_STRUCTURER_ENABLED"] = "1"
    else:
        os.environ.pop("GENERIC_STRUCTURER_ENABLED", None)
    os.environ.setdefault("GEMINI_API_KEY", "")
    settings = pipeline.Settings(api_key="", model="m-cheap", escalation_model="m-strong")
    pipeline.extract_statement = _sentinel                    # type: ignore[assignment]
    try:
        report = pipeline.analyze_markdown(
            UNCLAIMED, parse_mode="deterministic", settings=settings)
        outcome = f"returned model_used={report.model_used!r}"
    except Exception as exc:                                   # noqa: BLE001
        outcome = f"{type(exc).__name__}: {exc}"
    print(f"{label}: extract_statement calls={CALLS} -> {outcome}")


def main() -> int:
    probe("structurer OFF (production default, gate, discovery)", structurer=False)
    probe("structurer ON  (opt-in, not set anywhere in production)", structurer=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
