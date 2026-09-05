"""layout — the neutral home of document-level layout understanding
(Phase 2.2 cell C: the deterministic document classifier; Phase 2.4 will
add the LayoutModel here).

Imports ONLY the standard library and `evidence` (pinned by
`tests/test_layout_boundary.py`, AST at any depth). Never `ocr`, never
`analysis`: the classifier reads evidence from any extractor, and its verdict
is consumed by the intake ladder and by analysis, so neither side may own it
(umbrella D1). It never routes and never grants anything (D2): a verdict is a
recorded fact and a proposal for an adjudicator (R3), never truth.
"""
from layout.document_class import (
    CLASSIFIER_VERSION,
    KINDS,
    DocumentClass,
    DocumentProfileFacts,
    EvidenceRef,
    Finding,
    classify_document,
)

__all__ = [
    "CLASSIFIER_VERSION",
    "KINDS",
    "DocumentClass",
    "DocumentProfileFacts",
    "EvidenceRef",
    "Finding",
    "classify_document",
]
