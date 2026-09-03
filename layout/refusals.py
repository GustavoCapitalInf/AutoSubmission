"""layout/refusals.py — the L0 / L1 vocabulary of the unresolved-reason
taxonomy (Phase 2.2 cell C; umbrella §"Classifier"; plan §D.4, §J.1).

Closed tuples, nothing else. The classifier (`layout/document_class.py`)
produces exactly one `kind` per document from `KINDS`; the taxonomy cell (T)
maps `FILE_INVALID` to layer L0 and every other kind to layer L1. Every
value here is a vocabulary the reports print, so growth is a reviewed change
with a drift guard on the consuming side, never a convenience.

Reserved members
----------------
`SUB_KINDS` carries the plan's full L1 refinement list; the members the
version-1 classifier can actually produce are `PRODUCED_SUB_KINDS`. The
difference (`tax_or_id`, `other_bank_doc`, `non_bank`) is reserved for an
adjudicator's vocabulary and for later classifier versions — a verdict never
carries them today, and a consumer that sees one knows it did not come from
`CLASSIFIER_VERSION == 1`.
"""
from __future__ import annotations

__all__ = [
    "ACCOUNT_KINDS",
    "FINDING_CODES",
    "KINDS",
    "LANGUAGES",
    "MODALITIES",
    "PRODUCED_SUB_KINDS",
    "PROFILE_CLASSIFICATIONS",
    "SUB_KINDS",
    "TIERS",
]

#: The primary classification. Closed; disjoint; exactly one per document
#: (the disjoint sum over the archive and over the unresolved set is what
#: the report asserts — umbrella D2, case 8).
KINDS: tuple[str, ...] = (
    "STATEMENT_COMPLETE",
    "STATEMENT_PARTIAL",
    "STATEMENT_ILLEGIBLE",
    "ACTIVITY_EXPORT",
    "NOT_A_STATEMENT",
    "FILE_INVALID",
    "KIND_UNCERTAIN",
)

#: L1 refinements of `NOT_A_STATEMENT` (plan §D.4). See the module docstring
#: for the reserved members.
SUB_KINDS: tuple[str, ...] = (
    "cheque_image",
    "voided_cheque",
    "deposit_slip",
    "letter_or_notice",
    "card_statement",
    "loan_statement",
    "brokerage",
    "screenshot",
    "tax_or_id",
    "other_bank_doc",
    "non_bank",
)

#: The sub-kinds the version-1 rules can emit.
PRODUCED_SUB_KINDS: tuple[str, ...] = (
    "cheque_image",
    "voided_cheque",
    "deposit_slip",
    "letter_or_notice",
    "card_statement",
    "loan_statement",
    "brokerage",
    "screenshot",
)

#: Completeness findings (`STATEMENT_PARTIAL{findings}`), closed.
FINDING_CODES: tuple[str, ...] = (
    "missing_pages",
    "missing_opening",
    "missing_closing",
    "missing_period",
    "missing_first_page",
    "table_truncated",
    "page_gap",
    "balance_discontinuity_at_page_break",
)

#: `structural` — the deciding signal is geometric (an aligned money column)
#: or a MICR / aspect / page-marker / file fact; `lexical` — keywords only;
#: `uncertain` — `KIND_UNCERTAIN`.
TIERS: tuple[str, ...] = ("structural", "lexical", "uncertain")

#: How the words reached the classifier. `image_backed_text` = a scanned
#: profile whose text was recovered by OCR (Tesseract pages, or Paddle
#: evidence over a raster); `scanned` = a scanned profile with no text at
#: all; `digital` / `mixed` follow the preflight profile; `unknown` = an
#: invalid or encrypted file.
MODALITIES: tuple[str, ...] = ("digital", "scanned", "mixed", "image_backed_text", "unknown")

LANGUAGES: tuple[str, ...] = ("en", "fr", "es", "unknown")

ACCOUNT_KINDS: tuple[str, ...] = ("deposit", "card", "loan", "brokerage", "unknown")

#: The preflight profile's own vocabulary (`ocr/inspect.py::DocumentProfile.
#: classification`), restated here so the facts type can validate without
#: importing `ocr`.
PROFILE_CLASSIFICATIONS: tuple[str, ...] = ("digital", "scanned", "mixed", "unknown")
