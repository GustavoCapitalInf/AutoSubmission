"""ocr/paddle_rung.py — the Paddle rung (Phase 2.1 cell P,
`docs/agent-handoffs/P21-PADDLE.md` §4).

The ONLY thing cell R wires into the extraction ladder. `read_document` fails
closed, in order, and sends no byte before step 4:

  1. `settings = settings or load_paddle_settings()` — `PaddleConfigError`
     surfaces unchanged (CASE 17); no default host, nothing contacted.
  2. `check_remote_authorization(settings, data_scope)` — the opt-in and
     data-scope gates (CASE 13 / CASE 20); no request yet.
  3. `client.verify_identity(settings)` via `ocr.paddle_client.verify_identity`
     — the worker must echo the pins before any image is sent (D5 / CASE 16).
  4. Rasterise every page (`ocr.rasterize.rasterize_pdf`) and read each PDF
     page's own size/rotation with PyMuPDF; a raster whose scale disagrees
     with its page's dimensions FAILS THE WHOLE DOCUMENT
     (`paddle_frame_mismatch`) — never a partial page.
  5. PNG-encode each page, `client.ocr_page(...)`, adapt the result into
     canonical evidence; an adapter refusal likewise fails the whole
     document (`paddle_evidence_malformed`).
  6. Assemble the `PaddleRead`.

`PaddleTransportError` propagates unchanged from step 3 or step 5 — the
caller records `paddle_rung=failed` with the exception's class name; no
other host and no other extractor is ever tried from here (CASE 18).
`pdf_bytes` is never written to disk; page PNGs exist only in memory
(M11 — no `tempfile`, no `open(` on a path derived from a document, anywhere
in this module).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import fitz  # PyMuPDF — already an `ocr/` dependency (see ocr/native_text.py)

from evidence.canonical import ExtractionEvidence, PageFrame

from .paddle_adapter import PaddleAdapterError, evidence_from_pages, page_evidence_from_result
from .paddle_client import PaddleClient, verify_identity
from .paddle_config import (
    PADDLE_MODEL_TOKEN,
    PADDLE_RASTER_DPI,
    PaddleRefused,
    PaddleSettings,
    check_remote_authorization,
    load_paddle_settings,
)
from .rasterize import rasterize_pdf

__all__ = ["PaddleRead", "read_document"]


@dataclass(frozen=True)
class PaddleRead:
    """The rung's whole output. `pages` are D9's geometric page strings, in
    order; `evidence` is the immutable canonical evidence (cell R stores it
    on the artifact record, `document.evidence`); `page_extractor` is one
    token per page; `telemetry` is per-page timing/size figures ONLY —
    never document content."""

    pages: list[str]
    evidence: ExtractionEvidence
    page_extractor: list[str]
    telemetry: dict[str, Any]


def _runtime_block(settings: PaddleSettings, remote_identity: dict, dpi: int) -> dict:
    """Provenance for `ExtractionEvidence.runtime`: the worker's own echoed
    identity (already verified to match the pins) plus the declared
    provider/execution_class/dpi. NEVER a URL, host, port, request id or
    token (CASE 11) — `remote_identity` is `/version`'s payload, which the
    worker contract (`docs/agent-handoffs/P21-PADDLE.md` §1) defines without
    any of those fields in the first place."""
    block = dict(remote_identity)
    block["provider"] = settings.provider
    block["execution_class"] = settings.execution_class
    block["worker_contract"] = remote_identity.get("contract")
    block["dpi"] = dpi
    return block


def _empty_totals() -> dict[str, Any]:
    return {"pages": 0, "inference_ms_total": 0.0, "bytes_sent_total": 0, "bytes_received_total": 0}


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _empty_totals()
    return {
        "pages": len(rows),
        "inference_ms_total": sum(float(row["inference_ms"] or 0.0) for row in rows),
        "bytes_sent_total": sum(row["bytes_sent"] for row in rows),
        "bytes_received_total": sum(row["bytes_received"] for row in rows),
    }


def read_document(
    pdf_bytes: bytes,
    *,
    document_sha256: str,
    data_scope: str,
    settings: PaddleSettings | None = None,
    client: PaddleClient | None = None,
    dpi: int = PADDLE_RASTER_DPI,
) -> PaddleRead:
    """Read `pdf_bytes` through PaddleOCR on the configured worker. See the
    module docstring for the exact ordering and failure semantics."""
    settings = settings or load_paddle_settings()
    check_remote_authorization(settings, data_scope)
    client = client or PaddleClient(settings)
    remote_identity = verify_identity(settings, client=client)

    images = rasterize_pdf(pdf_bytes, dpi=dpi)
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_count = min(len(images), pdf_document.page_count)
        pages_evidence = []
        per_page_telemetry: list[dict[str, Any]] = []
        for index in range(page_count):
            image = images[index]
            pdf_page = pdf_document[index]
            rect = pdf_page.rect
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            png_bytes = buffer.getvalue()
            raster_sha256 = hashlib.sha256(png_bytes).hexdigest()

            try:
                frame = PageFrame.pixel(
                    page_index=index,
                    raster_width_px=image.width,
                    raster_height_px=image.height,
                    dpi=dpi,
                    pdf_width_pt=rect.width,
                    pdf_height_pt=rect.height,
                    raster_sha256=raster_sha256,
                    rotation_deg=pdf_page.rotation,
                )
            except Exception as exc:
                raise PaddleRefused("paddle_frame_mismatch", f"page {index}: {exc}") from exc

            request_id = f"{document_sha256[:16]}.p{index}"
            response = client.ocr_page(png_bytes, page_index=index, request_id=request_id)
            try:
                page_evidence = page_evidence_from_result(response["raw"], frame=frame)
            except PaddleAdapterError as exc:
                raise PaddleRefused("paddle_evidence_malformed", f"page {index}: {exc}") from exc
            pages_evidence.append(page_evidence)

            timing = response.get("timing") or {}
            per_page_telemetry.append({
                "page_index": index,
                "inference_ms": timing.get("inference_ms"),
                "total_ms": timing.get("total_ms"),
                "bytes_sent": len(png_bytes),
                "bytes_received": len(json.dumps(response)),
                "width": image.width,
                "height": image.height,
                "cold_load": bool(timing.get("cold_load", False)),
                "gpu_memory_used_mib": (response.get("gpu") or {}).get("memory_used_mib"),
            })
    finally:
        pdf_document.close()

    evidence = evidence_from_pages(
        pages_evidence, document_sha256=document_sha256,
        runtime=_runtime_block(settings, remote_identity, dpi),
    )
    return PaddleRead(
        pages=evidence.page_texts(),
        evidence=evidence,
        page_extractor=[PADDLE_MODEL_TOKEN] * len(evidence.pages),
        telemetry={"pages": per_page_telemetry, "totals": _totals(per_page_telemetry)},
    )
