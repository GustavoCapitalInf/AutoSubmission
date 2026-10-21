"""Layout-agnostic statement understanding (P2-1 / W3-3c).

The gap discovery measured is capability, not discipline: half the market-shaped
stream is unclaimed, and hand-writing parser #47…#400 was rejected (AD-7). This
subsystem is the generic mechanism — it knows the STRUCTURE of a bank statement
and infers each document's printing of it, filling the same `Statement` schema
every parser fills and facing the same gates.

    markdown / word geometry
            |
            v
      rows.py      columns and signs, decided by the document's own arithmetic
      summary.py   period and printed summary figures, with provenance
            |
            v
        Statement  ---> grounding.py   was it printed?   } BOTH required
            |      ---> reconcile/ADB  does it add up?   } before publication
            v
      fail closed: no opinion at all, rather than an unsupported number

What the caller sees is one function, `structure_unclaimed`, returning a
`Statement` or None. Everything else — refusal reasons, ungrounded candidates,
column hypotheses — stays in here.
"""
from __future__ import annotations

from .core import (
    PUBLISHED_SUMMARY_FIELDS,
    STRUCTURER_ENV,
    STRUCTURER_MODEL,
    StructureOutcome,
    structure_document,
    structure_unclaimed,
    structurer_enabled,
)
from .geometry import DocumentGeometry, geometry_from_pdf
from .grounding import GroundingResult, ground_statement

__all__ = [
    "DocumentGeometry",
    "GroundingResult",
    "PUBLISHED_SUMMARY_FIELDS",
    "STRUCTURER_ENV",
    "STRUCTURER_MODEL",
    "StructureOutcome",
    "geometry_from_pdf",
    "ground_statement",
    "structure_document",
    "structure_unclaimed",
    "structurer_enabled",
]
