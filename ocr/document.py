from __future__ import annotations
from dataclasses import dataclass, field

from evidence.canonical import ExtractionEvidence

from .config import ProvenanceTokenError, validate_model_token
from .truncation import PageIntegrity


def native_evidence_describes(pages: list[str], evidence: ExtractionEvidence) -> bool:
    """THE consistency rule between a `StatementMarkdown`'s page list and a
    native evidence (P22-IDENTITY, D5): the page COUNTS agree. Deliberately
    NOT text equality — see `StatementMarkdown.native_evidence`. One
    function so `__post_init__` (a constructed object refuses a mismatch)
    and the intake ladder (which attaches only what this rule admits) can
    never disagree about what "describes" means."""
    return len(evidence.pages) == len(pages)


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
    # P22-IDENTITY (Phase 2.2, D5). `native_evidence` is the immutable
    # canonical evidence of the NATIVE reader (`evidence/native.py`: PyMuPDF
    # word boxes in the display frame) behind a native-rung read, attached
    # once per document by the intake ladder and persisted in the OCR record
    # with its sha (`EXTRACTION_SCHEMA_VERSION` 3). It is a SIBLING of
    # `evidence`, deliberately, because the D9 invariant that field carries
    # (`evidence.page_texts() == pages`) does NOT hold for the native rung:
    # the native page strings come from `ocr/native_text.py::_native_pages`
    # (PyMuPDF text BLOCKS, plus whatever a bank-specific native reader
    # appended), not from grouping these words into lines. So this field's
    # own consistency check is page COUNT only — never text equality — and
    # that asymmetry is the whole reason it is not `evidence`. `None` for
    # every rung that is not the native rung, and for a native read whose
    # PDF yields no placeable word.
    native_evidence: ExtractionEvidence | None = None
    # P23-WAVE (Phase 2.3, cell T's named STOP). The per-request TECHNICAL
    # telemetry of the read that produced `pages` — exactly what
    # `ocr.paddle_rung.PaddleRead.telemetry` already carries: a `pages` list of
    # per-page `inference_ms` / `total_ms` / `bytes_sent` / `bytes_received` /
    # raster size / `cold_load` / `gpu_memory_used_mib`, and a `totals` block.
    # Figures only: this field never holds a word, a line, a box or anything
    # else derived from the document's CONTENT, and the row projection that
    # reads it (`discovery/runner.py::_project_funnel`) writes four numeric
    # columns and nothing else.
    #
    # RULED TRANSIENT. It is deliberately NOT part of the persisted OCR record:
    # `webapp.artifact_cache.ArtifactCache.put_ocr` stores a named field list
    # and this is not in it, so a cached read restores with
    # `extraction_telemetry=None` and the four columns stay EMPTY on a
    # `cache_paddle = hit` row. That is the honest reading — a hit made no
    # request, so it measured no request — and it is why this field forces no
    # `EXTRACTION_SCHEMA_VERSION` bump and cannot move a cache key:
    # `to_markdown()` does not mention it, `ocr_settings_key` does not mention
    # it, and `analysis_input_sha` keys on the markdown, the sheets and the
    # evidence sha, none of which this touches. `tests/test_paddle_wave.py`
    # proves the payload and both keys are identical with it set and unset.
    #
    # `None` for every rung that measured nothing (native, Tesseract, visual,
    # a committed artifact, a restored cache entry).
    extraction_telemetry: dict | None = None

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
        # P22-IDENTITY (D5): `native_evidence` describes the same document
        # page for page — the ONE rule is `native_evidence_describes`, shared
        # with the intake ladder, which declines to attach an evidence that
        # fails it rather than raising in the middle of a read.
        if self.native_evidence is not None:
            if not isinstance(self.native_evidence, ExtractionEvidence):
                raise ProvenanceTokenError(
                    "native_evidence must be an evidence.canonical.ExtractionEvidence or None"
                )
            if not native_evidence_describes(self.pages, self.native_evidence):
                raise ProvenanceTokenError(
                    f"native_evidence carries {len(self.native_evidence.pages)} pages but "
                    f"pages has {len(self.pages)}: they must describe the same document"
                )
        # P23-WAVE: a dict of figures, or nothing. The type is checked here for
        # the same reason every other field's is — a wrong-shaped value must
        # not become a `StatementMarkdown` and then a malformed row column
        # three layers away — and NOT its contents, which are the extractor's
        # own measurements and belong to whoever produced them.
        if self.extraction_telemetry is not None and not isinstance(self.extraction_telemetry, dict):
            raise ProvenanceTokenError(
                "extraction_telemetry must be a dict of technical figures or None"
            )

    @property
    def native_evidence_sha256(self) -> str | None:
        """The `evidence_sha256` of the attached native evidence, or `None`.
        The lineage a row's `evidence_sha256` column carries for a native
        read (populated by the runner, not here); what a cache hit must
        reproduce byte-for-byte."""
        return None if self.native_evidence is None else self.native_evidence.evidence_sha256

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
