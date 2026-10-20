"""Committed OCR source artifacts for the scanned corpus statements.

The corpus gate has to be deterministic and offline. 103 of the 109 corpus PDFs
carry native text, which extracts identically on any machine. The remaining 6
are image-only and would otherwise need a live Tesseract binary, whose output
varies with version, language data, and platform. Their OCR markdown is
therefore committed once and keyed by the SHA-256 of the source PDF, so an
artifact can never be silently paired with a different document, and a drifting
Tesseract install can never change what the gate audits.

Each artifact has TWO committed halves, both keyed by the same source PDF and
both hash-pinned:

``artifact``  the rendered markdown (``StatementMarkdown.to_markdown()``) — the
              text every reader analyses;
``pages``     the intake object's own page list (``StatementMarkdown.pages``),
              one entry per rasterised sheet.

The page list is committed SEPARATELY and not recovered by re-splitting the
markdown, because the ``--- Page N ---`` separator is an unescaped text
convention and page content is OCR output of whatever the document printed (W3
§PIPEFIX P4b.1). A document that prints that line would otherwise manufacture a
sheet, and manufacturing one unlabelled sheet is exactly what it takes to
withdraw a genuine `missing_declared_statement_page` finding. Committing the
list makes the six image-only statements analysable the way production analyses
a document it just read — the flag was previously fail-closed for them offline,
standing for the wrong reason (silence, not a genuinely absent page). Both
halves come from ONE intake run, and `tests/test_corpus_gate.py` proves the
committed list re-joins to the committed markdown byte for byte.

This module resolves source text. It interprets nothing: it imports no parser,
no metric, and no production financial code, so it cannot weaken the
independence of the audit oracles that consume it.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

DEFAULT_CACHE = Path(__file__).resolve().parent / "tests" / "corpus_cache"
MANIFEST_NAME = "manifest.json"


class ArtifactError(RuntimeError):
    """A cached artifact is missing, corrupt, or does not match its source PDF."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


@lru_cache(maxsize=8)
def _manifest(cache_root: str) -> dict[str, dict]:
    path = Path(cache_root) / MANIFEST_NAME
    if not path.is_file():
        raise ArtifactError(f"missing OCR artifact manifest: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("artifacts", [])
    by_digest = {entry["pdf_sha256"]: entry for entry in entries}
    if len(by_digest) != len(entries):
        raise ArtifactError(f"duplicate pdf_sha256 entries in {path}")
    return by_digest


def manifest_entries(cache_root: Path | str = DEFAULT_CACHE) -> dict[str, dict]:
    """Every committed artifact, keyed by the SHA-256 of its source PDF."""
    return dict(_manifest(str(cache_root)))


def cached_markdown(pdf_bytes: bytes, cache_root: Path | str = DEFAULT_CACHE) -> str | None:
    """Return the committed OCR markdown for exactly these PDF bytes.

    Returns ``None`` when the document has no cached artifact, so callers can
    tell "not a scanned statement" apart from "cache is broken". Raises
    ``ArtifactError`` when an artifact is registered but missing or altered.
    """
    entry = _manifest(str(cache_root)).get(sha256_hex(pdf_bytes))
    if entry is None:
        return None
    artifact = Path(cache_root) / entry["artifact"]
    if not artifact.is_file():
        raise ArtifactError(f"manifest references a missing artifact: {artifact}")
    text = artifact.read_text(encoding="utf-8")
    digest = sha256_hex(text.encode("utf-8"))
    if digest != entry["artifact_sha256"]:
        raise ArtifactError(
            f"cached artifact {artifact} has been altered: manifest pins "
            f"{entry['artifact_sha256']}, file is {digest}"
        )
    return text


def cached_pages(pdf_bytes: bytes, cache_root: Path | str = DEFAULT_CACHE) -> list[str] | None:
    """The committed intake page list for exactly these PDF bytes.

    The other half of :func:`cached_markdown`: one entry per rasterised sheet,
    exactly as the intake ladder produced it, so an offline reader can supply
    `sheets=` and reach the same verdict production reaches on the same bytes.

    Returns ``None`` when the document has no cached artifact AND when a cached
    artifact carries no committed page list — both are "no evidence of page
    structure", which every consumer must treat as fail-closed rather than as
    "no pages". Raises ``ArtifactError`` when a page list is registered but
    missing, altered, or not a list of strings: a page list we cannot trust is
    never silently downgraded to silence, because silence WEAKENS nothing while
    a wrong list could clear a genuine finding.
    """
    entry = _manifest(str(cache_root)).get(sha256_hex(pdf_bytes))
    if entry is None:
        return None
    relative = entry.get("pages")
    if not relative:
        return None
    path = Path(cache_root) / relative
    if not path.is_file():
        raise ArtifactError(f"manifest references a missing page list: {path}")
    text = path.read_text(encoding="utf-8")
    digest = sha256_hex(text.encode("utf-8"))
    if digest != entry.get("pages_sha256"):
        raise ArtifactError(
            f"cached page list {path} has been altered: manifest pins "
            f"{entry.get('pages_sha256')}, file is {digest}"
        )
    try:
        pages = json.loads(text).get("pages")
    except ValueError as exc:
        raise ArtifactError(f"cached page list {path} is not readable JSON: {exc}") from exc
    if not isinstance(pages, list) or not all(isinstance(page, str) for page in pages):
        raise ArtifactError(f"cached page list {path} is not a list of page strings")
    return pages
