from __future__ import annotations
from dataclasses import dataclass, field

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
