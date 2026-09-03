from __future__ import annotations
from dataclasses import dataclass, field

from evidence.canonical import ExtractionEvidence

from .config import ProvenanceTokenError, validate_model_token
from .truncation import PageIntegrity


@dataclass
class StatementMarkdown:
    source_file: str
    model: str
    pages: list[str] = field(default_factory=list)
    # O-3 truncation flags, one entry per page, in page order. Populated by the
    # intake ladder (ocr/pipeline.py) for whichever rung produced `pages`;
    # empty means "not assessed" (a StatementMarkdown built directly by an
    # extractor, e.g. by the audit scripts, rather than through the ladder).
    #
    # Why here: O-1 established two intake surfaces — DocumentProfile describes
    # the PDF *before* any parser runs, StatementMarkdown carries the result
    # *after*. Truncation is a property of a produced page, not of the source
    # PDF, and DocumentProfile is built without ever calling OCR, so it cannot
    # hold this. This is the OCR result object, so this is where the flag lives.
    page_integrity: list[PageIntegrity] = field(default_factory=list)
    # P21-ROUTING (Phase 2.1, design item 3). `page_extractor` is one
    # provenance token per page, in page order — set by the ladder for
    # WHICHEVER rung produced `pages` (native's own per-page token,
    # `"local-tesseract-ocr"`, the visual settings' model, or the Paddle
    # rung's list); empty means "not populated" (every pre-Phase-2.1 caller,
    # including a cached artifact restored from a schema-1 record). `evidence`
    # is the immutable canonical extraction evidence (`evidence.canonical.
    # ExtractionEvidence`) behind a Paddle (or, later, native-geometry) read;
    # `None` for every rung that does not produce geometry. Importing
    # `evidence.canonical` here widens no pinned boundary — `evidence/` is a
    # neutral, stdlib-only package owned by neither `ocr` nor `analysis`
    # (D1) — and this module's own import set is pinned by
    # `tests/test_escalation_tripwires.py::
    # test_ocr_document_imports_only_evidence_config_and_truncation`.
    page_extractor: list[str] = field(default_factory=list)
    evidence: ExtractionEvidence | None = None

    def __post_init__(self) -> None:
        """Close F-4(b) / MAJOR-2 at the point both fields are SET.

        `model` and `source_file` both become text in `to_markdown()`'s single
        header line, stripped whole by `admissible_text` only when the
        comment stays on one line (`SOURCE_COMMENT_RE` is MULTILINE, not
        DOTALL). Validating here means a hostile value never becomes a
        `StatementMarkdown` at all, so `to_markdown()` never needs to defend
        itself — the ONE existing guard downstream keeps doing its one job.

        Writer-side belt (PHASE2_P20SEAM_REVIEW.md §3): `source_file` also
        refuses `-->` — NOT because it can escape `SOURCE_COMMENT_RE` (it
        cannot; the guard's lazy `.*?` backtracks to the LAST `-->` on the
        line, so the comment still strips whole) but because an unbounded
        `source:` field lets `source_file` masquerade as a SECOND header
        (`... | pages: N | model: M | empty: 0 -->`) to any reader that
        parses the header left-to-right without bounding the `model` token
        to a closed charset — one such reader lands in this same phase
        (cell D's `analysis/provenance.py`). The reviewer's own measurement:
        zero cost — none of the 3,506 `source_file` values in the batch-9
        run of record contains `-->`
        (`test_no_run_of_record_source_file_contains_a_comment_close`,
        corpus-marked). This is a belt, not the closure: the closure is the
        READER bounding its own `model` field, which does not depend on
        every writer everywhere getting this right first — see this
        branch's W3 §Risks for the reader-side dependency, named.

        NEW-5 (re-review, closure 1cc759e): the belt above blocks only the
        EARLY-CLOSE shape (a `source_file` that ends the comment itself).
        The field-supplying spoof the paragraph above describes — a
        `source_file` that supplies its OWN `| model: X` text inside the
        comment, without ever closing it early — needs no `-->` at all and
        this belt does not touch it; it is closed entirely by cell D's
        reader bounding its own `model` field, which must not be assumed to
        depend on this branch.
        """
        if self.model:
            # Reserved deterministic-rung prefixes ARE allowed here: the
            # native and local-tesseract rungs set these tokens directly on
            # this class, never through the env-facing `load_settings`
            # validator that refuses impersonation.
            validate_model_token(self.model, allow_reserved=True)
        if "\n" in self.source_file or "\r" in self.source_file:
            raise ProvenanceTokenError(
                f"source_file rejected: contains a line break: {self.source_file!r}"
            )
        if "-->" in self.source_file:
            raise ProvenanceTokenError(
                "source_file rejected: contains a comment-close sequence ('-->')"
            )
        # P21-ROUTING design item 3: `page_extractor`, when populated, must
        # describe every page — one token each, in order — and every token
        # must itself be a valid provenance token (the native/tesseract/
        # visual/Paddle rungs all set reserved-prefix tokens directly here,
        # never through the env-facing validator).
        if self.page_extractor:
            if len(self.page_extractor) != len(self.pages):
                raise ProvenanceTokenError(
                    f"page_extractor has {len(self.page_extractor)} entries "
                    f"but pages has {len(self.pages)}: one token per page, or none at all"
                )
            for token in self.page_extractor:
                validate_model_token(token, allow_reserved=True)
        # `evidence`, when present, is the SAME object `pages` was derived
        # from (D9 / D6): the page count and the derived page strings must
        # match exactly, or a drift between the two is a defect this
        # construction refuses rather than silently carries.
        if self.evidence is not None:
            if not isinstance(self.evidence, ExtractionEvidence):
                raise ProvenanceTokenError(
                    "evidence must be an evidence.canonical.ExtractionEvidence or None"
                )
            if len(self.evidence.pages) != len(self.pages):
                raise ProvenanceTokenError(
                    f"evidence carries {len(self.evidence.pages)} pages but "
                    f"pages has {len(self.pages)}: they must describe the same document"
                )
            if self.evidence.page_texts() != self.pages:
                raise ProvenanceTokenError(
                    "evidence.page_texts() does not equal pages: the derived "
                    "page strings and the evidence they came from must be one object"
                )

    @property
    def truncated_pages(self) -> list[int]:
        """Page indices flagged as possibly truncated (route to re-OCR/review)."""
        return [item.page_index for item in self.page_integrity if item.truncated]

    @property
    def has_truncated_pages(self) -> bool:
        return any(item.truncated for item in self.page_integrity)

    def to_markdown(self) -> str:
        # DELIBERATELY unchanged by O-3: this string is the extraction input for
        # every parser and the committed corpus artifacts are pinned to it, so a
        # flag-only wave must not add a byte. The flags live on the object.
        empty = sum(1 for p in self.pages if not p.strip())
        header = (
            f"<!-- source: {self.source_file} | pages: {len(self.pages)} "
            f"| model: {self.model} | empty: {empty} -->"
        )
        blocks = [header, ""]
        for i, page in enumerate(self.pages, start=1):
            if page.strip():
                blocks.append(f"--- Page {i} ---")
                blocks.append(page.strip())
            else:
                blocks.append(f"--- Page {i} (empty) ---")
        return "\n\n".join(blocks) + "\n"
